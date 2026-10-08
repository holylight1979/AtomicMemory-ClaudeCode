"""wg_verify_ledger.py：驗證帳本與收尾對帳（H6 帳本／Stop 對帳、H8 量尺閘）的純函式。

做什麼：
  PostToolUse 收 Bash／PowerShell 輸出裡的哨兵（`<NAME>_CHECK PASS|FAIL|DONE`、量測類 `<NAME> DONE k=v`）
  與 exit code，連同 VCS 快照、本 turn 改過的檔、驗收規格路徑，落 `workflow/verify-ledger/<sid>.jsonl`
  並進 `state["verify_receipts"][sid]`（cap 50）。
  Stop 在「宣告完成」的回合拿收據對帳：說「修好」要有本 turn 且對得上改檔的 PASS（exit 0 或無 exit）、說「量了」要有 DONE、
  說「試過」要有執行類工具呼叫、改了程式碼要有驗證 case 被改或對得上的 PASS、AEC 要有證據路徑（j）與追蹤項（k）；
  改到有量尺的部位，收尾前要有那把尺在最後一次修改之後、同 root、exit 0 且 failed=0 的 DONE（先過 runtime_gate）。

怎麼跑：被 handlers/post_tool_use.py 與 handlers/stop.py 匯入；verify 在 hooks/verify/verify_verify_ledger.py、
  verify_stop_reconcile.py。exit code 三來源：tool_response.exit_code／returncode（結構化欄優先，欄是 0 就不再看文字）
  → 文字裡 `^Exit code N`（實機 Bash 非零時 tool_response 是字串 "Error: Exit code 1\\n…"，取最後一個）→ 都沒有記 None
  （None 不當零也不當非零；對帳時標 exit_unknown）。
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Pattern, Tuple

from wg_core import WORKFLOW_DIR, find_vcs_root
from wg_evasion import CLAIM_RES, claims_completion, strip_quoted_spans

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

# ─── 哨兵 ─────────────────────────────────────────────────────────────
DEFAULT_SENTINEL_RE: Pattern = re.compile(
    r"^(?P<name>[A-Z][A-Z0-9_]*)_CHECK\s+(?P<verdict>PASS|FAIL|DONE)\b(?P<kv>(?:\s+\w+=\S+)*)", re.MULTILINE
)
# 量測類（rules/coding-style.md 自檢：`<NAME> DONE k=v k=v`）；數字是尺不是判決
DEFAULT_DONE_RE: Pattern = re.compile(
    r"^(?P<name>[A-Z][A-Z0-9_]*)\s+DONE\b(?P<kv>(?:\s+\w+=\S+)*)\s*$", re.MULTILINE
)
_EXIT_CODE_RE = re.compile(r"^(?:Error:\s*)?Exit code (\d+)\b", re.MULTILINE)
VERDICTS = ("PASS", "FAIL", "DONE")
RECEIPT_CAP = 50
LEDGER_SUBDIR = "verify-ledger"
SNAPSHOT_MAX_FILES = 200
SNAPSHOT_STAT_CHECK_EVERY = 10     # 每 10 檔查一次 deadline（50 檔×55 ms 的慢磁碟會先吃掉 2.75 s）


def compile_sentinel_rules(cfg_rules: Any) -> List[Dict[str, Any]]:
    """config `verify_ledger.sentinel_regex: [{regex, name, verdict_map}]` → 已編譯規則；壞 regex 跳過（stderr 浮一行）。"""
    out: List[Dict[str, Any]] = []
    for r in cfg_rules or []:
        if not isinstance(r, dict) or not r.get("regex"):
            continue
        try:
            rx = re.compile(str(r["regex"]), re.MULTILINE)
        except re.error as e:
            print(f"[verify-ledger] sentinel_regex 無效，略過：{r.get('regex')}（{e}）", file=sys.stderr)
            continue
        vm = r.get("verdict_map") if isinstance(r.get("verdict_map"), dict) else {}
        out.append({
            "re": rx,
            "name": str(r.get("name") or "").strip(),
            "verdict_map": {str(k): str(v).upper() for k, v in vm.items()},
        })
    return out


def _map_verdict(raw: str, verdict_map: Dict[str, str]) -> Optional[str]:
    low = raw.lower()
    for key, v in verdict_map.items():
        if key.lower() in low and v in VERDICTS:
            return v
    return raw.strip().upper() if raw.strip().upper() in VERDICTS else None


def _line_of(text: str, m: "re.Match") -> str:
    start = text.rfind("\n", 0, m.start()) + 1
    end = text.find("\n", m.end())
    return text[start: end if end >= 0 else len(text)].strip()


def _kv(raw: Optional[str]) -> Dict[str, str]:
    return dict(p.split("=", 1) for p in (raw or "").split() if "=" in p)


def parse_sentinels(text: str, rules: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """輸出文字 → [{name, verdict, line, kv}]；預設兩個 regex（_CHECK 與量測 DONE）＋ config 規則；同一行同結論只記一次。
    反例：小寫 `x_check pass`、散文「測試通過」不命中。"""
    text = text or ""
    found: List[Dict[str, Any]] = []
    seen: set = set()

    def _add(name: str, verdict: str, line: str, kv: Dict[str, str]) -> None:
        key = (name, verdict, line)
        if key in seen:
            return
        seen.add(key)
        found.append({"name": name, "verdict": verdict, "line": line[:200], "kv": kv})

    for m in DEFAULT_SENTINEL_RE.finditer(text):
        _add(m.group("name") + "_CHECK", m.group("verdict"), _line_of(text, m), _kv(m.group("kv")))
    for m in DEFAULT_DONE_RE.finditer(text):
        name = m.group("name")
        if name.endswith("_CHECK"):
            continue      # 已由上一個 regex 收
        _add(name, "DONE", _line_of(text, m), _kv(m.group("kv")))
    for rule in rules or []:
        for m in rule["re"].finditer(text):
            raw = m.groupdict().get("verdict") or m.group(0)
            verdict = _map_verdict(raw, rule["verdict_map"])
            if not verdict:
                continue
            name = rule["name"] or m.groupdict().get("name") or "CUSTOM"
            _add(name, verdict, _line_of(text, m), {})
    return found


# ─── exit code 與回應文字 ──────────────────────────────────────────────
def response_text(tool_response: Any) -> str:
    """dict → stdout+stderr；字串（實機非零 exit 時整包是 "Error: Exit code N\\n…"）→ 原文。"""
    if isinstance(tool_response, dict):
        return str(tool_response.get("stdout", "") or "") + "\n" + str(tool_response.get("stderr", "") or "")
    return "" if tool_response is None else str(tool_response)


def exit_code_of(tool_response: Any) -> Optional[int]:
    """三來源：exit_code／returncode 欄（結構化欄優先；欄是 0 就是 0，不再看文字）→ 文字 `^Exit code N`（掃整段、取最後一個）→ None。"""
    if isinstance(tool_response, dict):
        for k in ("exit_code", "returncode"):
            v = tool_response.get(k)
            if isinstance(v, bool):
                continue
            if isinstance(v, int):
                return v
            if isinstance(v, str) and v.strip().lstrip("-").isdigit():
                return int(v.strip())
    last = None
    for last in _EXIT_CODE_RE.finditer(response_text(tool_response)):
        pass
    return int(last.group(1)) if last else None


# ─── VCS 快照 ─────────────────────────────────────────────────────────
def _rev_cmd(kind: str, root: Path) -> List[str]:
    if kind == "git":
        return ["git", "-C", str(root), "rev-parse", "--short", "HEAD"]
    return ["svn", "info", "--show-item", "revision", str(root)]


def _run_rev(kind: str, root: Path, timeout_s: float) -> str:
    try:
        r = subprocess.run(_rev_cmd(kind, root), capture_output=True, text=True, timeout=timeout_s,
                           creationflags=_NO_WINDOW)
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return ""
    return (r.stdout or "").strip() if r.returncode == 0 else ""


def dirty_hash(root: Path, paths: Iterable[str], deadline: Optional[float] = None,
               _clock: Callable[[], float] = time.monotonic, _stat: Callable[[str], Any] = os.stat,
               max_files: int = SNAPSHOT_MAX_FILES) -> Tuple[str, bool]:
    """未提交雜湊：只用 os.stat（零子行程）：sorted((相對路徑, mtime_ns, size)) 的 sha1 前 12 碼。
    檔數上限 max_files、每 10 檔查一次 deadline，超過就停：回 (雜湊, truncated)；沒有檔回 ("", False)。"""
    rows: List[str] = []
    truncated = False
    r = str(root).replace("\\", "/").rstrip("/").lower()
    for i, p in enumerate(paths):
        if i >= max_files:
            truncated = True
            break
        if deadline is not None and i % SNAPSHOT_STAT_CHECK_EVERY == 0 and i and _clock() > deadline:
            truncated = True
            break
        norm = str(p).replace("\\", "/")
        if not norm.lower().startswith(r + "/"):
            continue
        rel = norm[len(r) + 1:]
        try:
            st = _stat(p)
        except OSError:
            rows.append(f"{rel}|missing")
            continue
        rows.append(f"{rel}|{st.st_mtime_ns}|{st.st_size}")
    if not rows:
        return "", truncated
    return hashlib.sha1("\n".join(sorted(rows)).encode("utf-8")).hexdigest()[:12], truncated


def _same(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return str(a).lower() == str(b).lower()


def vcs_snapshot(cwd: str, paths: Iterable[str], state: Dict[str, Any], budget_s: float = 1.5,
                 rev_cache_s: float = 60.0, subprocess_s: float = 1.0,
                 _rev: Callable[[str, Path, float], str] = _run_rev,
                 _clock: Callable[[], float] = time.monotonic,
                 _stat: Callable[[str], Any] = os.stat) -> List[Dict[str, Any]]:
    """cwd 與各 path 的 VCS 根（最多 2 個）→ [{kind, root, rev, dirty, truncated}]。
    整支函式一個 deadline＝起點＋budget_s：找 root、每個子行程（timeout＝min(subprocess_s, 剩餘)）、stat 迴圈每 10 檔
    都查 deadline；檔數上限 200；任一處超過 → 該筆 truncated=True 並停止。rev 每 root 60 s 快取在 state["vcs_rev_cache"]；非 VCS 回 []。"""
    deadline = _clock() + budget_s
    paths = [p for p in paths if p][:SNAPSHOT_MAX_FILES + 1]
    roots: List[Tuple[str, Path]] = []
    out: List[Dict[str, Any]] = []
    for i, start in enumerate([cwd, *paths]):
        if not start:
            continue
        if i and i % SNAPSHOT_STAT_CHECK_EVERY == 0 and _clock() > deadline:
            out.append({"kind": "", "root": "", "rev": "", "dirty": "", "truncated": True})
            return out
        try:
            sp = Path(start)
            hit = find_vcs_root(sp if sp.is_dir() else sp.parent)
        except OSError:
            hit = None
        if hit and all(not _same(hit[1], r) for _, r in roots):
            roots.append(hit)
        if len(roots) >= 2:
            break
    cache = state.setdefault("vcs_rev_cache", {})
    if not isinstance(cache, dict):
        cache = state["vcs_rev_cache"] = {}
    for kind, root in roots:
        key = str(root).replace("\\", "/")
        entry: Dict[str, Any] = {"kind": kind, "root": key, "rev": "", "dirty": "", "truncated": False}
        remaining = deadline - _clock()
        if remaining <= 0:
            entry["truncated"] = True
            out.append(entry)
            break
        cached = cache.get(key) if isinstance(cache.get(key), dict) else None
        now_wall = time.time()
        if cached and now_wall - float(cached.get("at", 0)) < rev_cache_s and cached.get("rev"):
            entry["rev"] = cached["rev"]
        else:
            entry["rev"] = _rev(kind, root, min(subprocess_s, remaining))
            if entry["rev"]:
                cache[key] = {"rev": entry["rev"], "at": now_wall}
            if _clock() > deadline:
                entry["truncated"] = True
                out.append(entry)
                break
        entry["dirty"], trunc = dirty_hash(root, paths, deadline, _clock, _stat)
        entry["truncated"] = entry["truncated"] or trunc
        out.append(entry)
        if trunc:
            break
    for k in list(cache):
        if time.time() - float((cache.get(k) or {}).get("at", 0)) > 3600:
            cache.pop(k, None)
    return out


# ─── 帳本與 state 收據 ─────────────────────────────────────────────────
def ledger_path(sid: str, base_dir: Optional[Path] = None) -> Path:
    return (base_dir or WORKFLOW_DIR) / LEDGER_SUBDIR / f"{sid}.jsonl"


def append_verify_ledger(sid: str, record: Dict[str, Any], base_dir: Optional[Path] = None,
                         suffix: str = "") -> Optional[Path]:
    """workflow/verify-ledger/<sid><suffix>.jsonl 追加一筆（LF；執行期檔，.gitignore 收）。失敗浮 stderr、回 None。"""
    try:
        d = (base_dir or WORKFLOW_DIR) / LEDGER_SUBDIR
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"{sid}{suffix}.jsonl"
        with open(p, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        return p
    except OSError as e:
        print(f"[verify-ledger] ledger write failed (fail-open): {e}", file=sys.stderr)
        return None


def receipts_of(state: Dict[str, Any], sid: str) -> List[Dict[str, Any]]:
    sec = (state.get("verify_receipts") or {}).get(sid)
    return [r for r in sec if isinstance(r, dict)] if isinstance(sec, list) else []


def record_receipt(state: Dict[str, Any], sid: str, receipt: Dict[str, Any], cap: int = RECEIPT_CAP) -> None:
    """state["verify_receipts"][sid] 追加，保留最近 cap 筆。"""
    allr = state.setdefault("verify_receipts", {})
    if not isinstance(allr, dict):
        allr = state["verify_receipts"] = {}
    lst = allr.setdefault(sid, [])
    lst.append(receipt)
    if len(lst) > cap:
        del lst[:-cap]


def next_event_seq(state: Dict[str, Any]) -> int:
    """session 內單調遞增序號：改檔與收據都蓋一個，同 turn 內分先後（先量後改要看得出來）。"""
    n = int(state.get("event_seq", 0) or 0) + 1
    state["event_seq"] = n
    return n


def ledger_entries_this_turn(state: Dict[str, Any], sid: str, turn_seq: int) -> List[Dict[str, Any]]:
    return [r for r in receipts_of(state, sid) if int(r.get("turn_seq", -1)) == int(turn_seq)]


def spec_paths_of(sid: str, base_dir: Optional[Path] = None) -> List[str]:
    """驗收規格（hooks/acceptance_spec.py sidecar）本 session 登記的規格檔路徑；沒有回 []。"""
    try:
        p = (base_dir or WORKFLOW_DIR) / "acceptance-spec" / f"{sid}.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        return [str(x) for x in (data.get("spec_paths") or [])]
    except (OSError, ValueError):
        return []


def modified_this_turn(own_mod_files: Iterable[Dict[str, Any]], turn_seq: int) -> List[str]:
    """本 turn 動過的檔（last_turn_seq==turn_seq）。升級前 in-flight session 的 legacy entry 沒有 turn 欄＝不知道哪回合改的，
    不算本 turn（對帳 (d) 不拿它擋人；下一次 Edit 就會補上 turn 欄）。"""
    out: List[str] = []
    for m in own_mod_files or []:
        if not isinstance(m, dict) or not m.get("path"):
            continue
        t = m.get("last_turn_seq", m.get("turn_seq"))
        if t is not None and int(t) == int(turn_seq) and m["path"] not in out:
            out.append(m["path"])
    return out


# ─── 宣稱偵測（詞表 wg_evasion.CLAIM_RES：fixed／measured／tried 各配 exclude）────
# 子句切在 ，；,;。！!與換行；問號留在子句裡給 exclude（`[?？]\s*$`）判疑問
_CLAUSE_SPLIT_RE = re.compile(r"[，；,;。！!\n]+")
# 第三方主語：同子句內、宣稱詞前 ≤8 字出現這些主語 → 是轉述不是自己的宣稱
_THIRD_PARTY_RE = re.compile(
    r"(?:使用者|對方|同事|codex|它|他|她|log|輸出|顯示)[^，。；！？\n]{0,8}$", re.IGNORECASE
)


def _claims(text: str, kind: str, phrases: Optional[Dict[str, Pattern]] = None) -> bool:
    """逐子句判：子句命中 <kind> 詞、同子句無 <kind>_exclude 詞（否定／疑問只取消同子句）、宣稱詞前沒有第三方主語；
    引號／code span 內容先剝掉（引用閘文字不算宣稱）。"""
    if not text:
        return False
    ph = phrases or CLAIM_RES
    pos, neg = ph[kind], ph[f"{kind}_exclude"]
    for clause in _CLAUSE_SPLIT_RE.split(strip_quoted_spans(text[-3000:])):
        m = pos.search(clause)
        if not m or neg.search(clause):
            continue
        if _THIRD_PARTY_RE.search(clause[:m.start()]):
            continue
        return True
    return False


def claims_fixed(text: str, phrases: Optional[Dict[str, Pattern]] = None) -> bool:
    return _claims(text, "fixed", phrases)


def claims_measured(text: str, phrases: Optional[Dict[str, Pattern]] = None) -> bool:
    return _claims(text, "measured", phrases)


def claims_tried(text: str, phrases: Optional[Dict[str, Pattern]] = None) -> bool:
    return _claims(text, "tried", phrases)


def tried_claim_without_exec(text: str, turn_tool_names: Iterable[str], exec_tools: Iterable[str],
                             receipts_this_turn: Iterable[Dict[str, Any]] = (),
                             phrases: Optional[Dict[str, Pattern]] = None) -> bool:
    """說「試過」但本 turn 沒有執行類工具呼叫（工具名清單與帳本收據都沒有）→ True。"""
    if not claims_tried(text, phrases):
        return False
    execs = {str(t) for t in exec_tools}
    if any(str(n) in execs for n in (turn_tool_names or [])):
        return False
    return not any(isinstance(r, dict) for r in receipts_this_turn)


# ─── 收據判定 ─────────────────────────────────────────────────────────
def _verdicts(receipt: Dict[str, Any]) -> List[str]:
    return [str(s.get("verdict", "")) for s in (receipt.get("sentinels") or []) if isinstance(s, dict)]


def _norm_path(p: str) -> str:
    return str(p).replace("\\", "/").rstrip("/").lower()


def _path_tokens(path: str, root: Optional[str] = None) -> List[str]:
    """一個改過的檔 → 收據 cmd 裡能對上的字樣：basename、stem、相對 root 的頂層目錄（沒 root 用上層目錄名）。"""
    norm = _norm_path(path)
    name = norm.rsplit("/", 1)[-1]
    toks = [name]
    stem = name.rsplit(".", 1)[0] if "." in name else name
    if len(stem) >= 3:
        toks.append(stem)
    top = ""
    if root and norm.startswith(_norm_path(root) + "/"):
        rel = norm[len(_norm_path(root)) + 1:]
        top = rel.split("/")[0] if "/" in rel else ""
    if not top and "/" in norm:
        top = norm.rsplit("/", 2)[-2]
    if top and len(top) >= 3:
        toks.append(top)
    return toks


def receipt_relates(receipt: Dict[str, Any], mod_paths: Iterable[str], verify_globs: Iterable[str],
                    measure_cmds: Iterable[str], root: Optional[str] = None) -> bool:
    """PASS 收據要「對得上」才能背書：cmd 提到改過的檔（basename／stem／頂層目錄）、或 cmd 裡有命中 verify_case_globs 的路徑、
    或 cmd 含部位量尺指令。"""
    cmd = _norm_path(str(receipt.get("cmd", "")))
    if not cmd:
        return False
    for p in mod_paths or []:
        if any(t in cmd for t in _path_tokens(p, root)):
            return True
    for tok in re.split(r"[\s\"'`;&|()]+", cmd):
        if ("/" in tok or tok.endswith(".py")) and is_verify_case(tok, verify_globs):
            return True
    for mc in measure_cmds or []:
        want = " ".join(str(mc).split()).lower()
        if want and want in " ".join(cmd.split()):
            return True
    return False


def pass_receipts(receipts: Iterable[Dict[str, Any]], turn_seq: Optional[int] = None) -> List[Dict[str, Any]]:
    """合格 PASS：有 PASS 哨兵且 exit_code 為 None 或 0（exit≠0 的 PASS 不算）；給 turn_seq 時只認該 turn。
    exit 為 None 的在回傳的 dict 上標 exit_unknown=True（dict／PowerShell 回應沒有 exit 欄）。"""
    out = []
    for r in receipts:
        if turn_seq is not None and int(r.get("turn_seq", -1)) != int(turn_seq):
            continue
        if "PASS" in _verdicts(r) and r.get("exit_code") in (None, 0):
            if r.get("exit_code") is None:
                r = {**r, "exit_unknown": True}
            out.append(r)
    return out


def related_pass_receipts(receipts: Iterable[Dict[str, Any]], turn_seq: Optional[int], mod_paths: Iterable[str],
                          verify_globs: Iterable[str], measure_cmds: Iterable[str] = (),
                          root: Optional[str] = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """合格 PASS 再分「對得上」與「對不上」兩堆。"""
    related, unrelated = [], []
    for r in pass_receipts(receipts, turn_seq):
        (related if receipt_relates(r, mod_paths, verify_globs, measure_cmds, root) else unrelated).append(r)
    return related, unrelated


def _failed_kv_ok(receipt: Dict[str, Any]) -> bool:
    """哨兵帶 failed=<k> 時 k 必須是 0（run_verify 的 VERIFY_CHECK DONE cases= failed=）。"""
    for s in receipt.get("sentinels") or []:
        k = (s.get("kv") or {}).get("failed") if isinstance(s, dict) else None
        if k is not None and str(k).strip() not in ("0", ""):
            return False
    return True


def _root_match(receipt: Dict[str, Any], root: Optional[str]) -> bool:
    if not root:
        return True
    want = _norm_path(str(root))
    for key in ("project_root", "cwd"):
        v = _norm_path(str(receipt.get(key) or ""))
        if v and (v == want or v.startswith(want + "/")):
            return True
    return False


def _receipt_after(receipt: Dict[str, Any], edit_at: Optional[str], edit_seq: Optional[int], edit_turn: int) -> bool:
    """收據要在該部位最後一次修改之後：先比 at（同一 _now_iso 時鐘的 ISO 字串），沒有 at 比 session 內序號，再沒有退回比 turn。"""
    r_at, r_seq = str(receipt.get("at") or ""), receipt.get("seq")
    if edit_at and r_at:
        return r_at > str(edit_at)
    if edit_seq is not None and r_seq is not None:
        return int(r_seq) > int(edit_seq)
    return int(receipt.get("turn_seq", -1)) >= int(edit_turn)


def done_receipts(receipts: Iterable[Dict[str, Any]], turn_seq: Optional[int] = None,
                  cmd_contains: str = "", min_turn: Optional[int] = None, require_ok: bool = True,
                  min_at: Optional[str] = None, min_seq: Optional[int] = None,
                  root: Optional[str] = None) -> List[Dict[str, Any]]:
    """DONE 收據；turn_seq 指定只認該 turn；min_turn／min_at／min_seq 指定要在該修改之後；cmd_contains 指定 cmd 要含該片段
    （空白正規化、不分大小寫）；require_ok：exit 要 0 或 None 且 failed=<k> 必為 0；root 指定 cwd／project_root 要在該 root 下。"""
    want = " ".join(cmd_contains.split()).lower()
    out = []
    for r in receipts:
        t = int(r.get("turn_seq", -1))
        if turn_seq is not None and t != int(turn_seq):
            continue
        if min_turn is not None and not _receipt_after(r, min_at, min_seq, min_turn):
            continue
        if "DONE" not in _verdicts(r):
            continue
        if require_ok and (r.get("exit_code") not in (None, 0) or not _failed_kv_ok(r)):
            continue
        if want and want not in " ".join(str(r.get("cmd", "")).split()).lower():
            continue
        if not _root_match(r, root):
            continue
        out.append(r)
    return out


def is_code_file(path: str, code_exts: Iterable[str]) -> bool:
    low = str(path).lower()
    return any(low.endswith(str(e).lower()) for e in code_exts)


def is_verify_case(path: str, globs: Iterable[str]) -> bool:
    norm = _norm_path(path)
    for g in globs:
        g = str(g).replace("\\", "/").lower()
        if fnmatch.fnmatch(norm, g) or fnmatch.fnmatch(norm, "*/" + g.lstrip("*/")):
            return True
        core = g.strip("*/")        # `**/verify/**` 類：目錄名出現在路徑任一段也算
        if core and "*" not in core and ("/" + core + "/") in norm:
            return True
    return False


def aec_blank(v: Any) -> bool:
    s = re.sub(r"[\s。．.,，、；;：:!！?？~～\-\u2014…]+$", "", str("" if v is None else v).strip())
    return s == "" or re.match(r"^[無无]\s*(?:[（(][^）)]*[）)])?$", s) is not None


def aec_evidence_missing(j: Any, receipts_non_empty: bool,
                         _exists: Callable[[str], bool] = os.path.exists) -> bool:
    """(j) 證據持久路徑：本 session 有收據時，j 空／「無」或任一行路徑不存在 → True。沒有收據 → False。
    MIRROR: tools/workflow-guardian-mcp/lib/anti-evasion.js aecEvidenceMissing；keep in sync。"""
    if not receipts_non_empty:
        return False
    if aec_blank(j):
        return True
    for line in str(j).splitlines():
        p = line.strip().split(" \u2014 ")[0].split(" - ")[0].strip().strip("`")
        if not p:
            continue
        if not _exists(os.path.expanduser(p)):
            return True
    return False


def aec_followups_missing(k: Any) -> bool:
    """(k) 追蹤項：空字串（只有空白）→ True；「無」或任何內容 → False。
    MIRROR: anti-evasion.js aecFollowupsMissing。"""
    return str("" if k is None else k).strip() == ""


# ─── Stop 對帳閘 ──────────────────────────────────────────────────────
RECONCILE_DEFAULTS: Dict[str, Any] = {
    "enabled": True,
    "max_blocks_per_turn": 2,
    "exec_tools": ["Bash", "PowerShell"],
    "code_exts": [".py", ".js", ".cs", ".ts", ".lua"],
    "verify_case_globs": ["**/verify/**", "**/tests/**", "**/*test*"],
}


def reconcile_cfg(config: Dict[str, Any]) -> Dict[str, Any]:
    c = dict(RECONCILE_DEFAULTS)
    sec = (config or {}).get("reconcile_gate")
    if isinstance(sec, dict):
        c.update(sec)
    return c


def _pass_why(this_turn: List[Dict[str, Any]], all_receipts: List[Dict[str, Any]], unrelated: List[Dict[str, Any]],
              mod_paths: List[str]) -> str:
    bad_exit = [r for r in this_turn if "PASS" in _verdicts(r) and r.get("exit_code") not in (None, 0)]
    stale = pass_receipts(all_receipts)
    if unrelated:
        verified = "、".join(str(r.get("cmd", ""))[:50] for r in unrelated[:2])
        changed = "、".join(Path(p).name for p in mod_paths[:3]) or "（本回合沒改檔）"
        return f"本回合有 PASS 但驗的是「{verified}」，改的是 {changed}，對不上"
    if bad_exit:
        return "本回合有 PASS 但 exit≠0（" + "、".join(
            f"{str(r.get('cmd', ''))[:40]} exit={r.get('exit_code')}" for r in bad_exit[:2]) + "）"
    if stale:
        return "只有舊回合的 PASS（turn " + "、".join(str(r.get("turn_seq")) for r in stale[-2:]) + "）"
    return "本回合沒有任何 PASS 收據"


def reconcile_gate_reason(last_text: str, receipts: List[Dict[str, Any]], turn_seq: int,
                          turn_tool_names: Iterable[str], own_mod_files: List[Dict[str, Any]],
                          cfg: Dict[str, Any], aec: Optional[Dict[str, Any]] = None,
                          aec_emitted: bool = False, sid: str = "",
                          phrases: Optional[Dict[str, Pattern]] = None,
                          measure_cmds: Iterable[str] = (), root: Optional[str] = None) -> Optional[str]:
    """只在本回合「宣告完成」時對帳（純審查／中途回覆不擋）。五條規則任一命中回擋訊息（全部列出），否則 None。純判定、不改 state。
    (a) 說修好而本 turn 無對得上改檔的合格 PASS；(b) 說量了無 DONE；(c) 說試過無執行工具；
    (d) 改了程式碼、沒改驗證 case、無對得上的 PASS；(e) AEC 已 emit：有收據而 j 缺／不存在、k 空字串。"""
    if not claims_completion(last_text):
        return None
    this_turn = [r for r in receipts if int(r.get("turn_seq", -1)) == int(turn_seq)]
    mod_turn = modified_this_turn(own_mod_files, turn_seq)
    mod_session = [m["path"] for m in own_mod_files or [] if isinstance(m, dict) and m.get("path")]
    relate_paths = mod_turn or mod_session
    globs = cfg.get("verify_case_globs") or []
    related, unrelated = related_pass_receipts(this_turn, None, relate_paths, globs, measure_cmds, root)
    hits: List[str] = []
    if claims_fixed(last_text, phrases) and not related:
        hits.append(f"(a) 說「修好」但 {_pass_why(this_turn, receipts, unrelated, relate_paths)}。"
                    "修好的證據是本回合跑「驗那個改動」的驗證（cmd 提到改的檔／verify 路徑／量尺指令）印出 `<NAME>_CHECK PASS` 且 exit 0。")
    if claims_measured(last_text, phrases) and not done_receipts(this_turn, require_ok=False):
        hits.append("(b) 說「量了」但本回合沒有 `<NAME> DONE k=v` 收據。量了就讓量尺腳本印 DONE 尾行，沒量就寫沒量。")
    if tried_claim_without_exec(last_text, turn_tool_names, cfg.get("exec_tools") or [], this_turn, phrases):
        hits.append("(c) 說「試過／跑了」但本回合沒有任何 Bash／PowerShell 執行。沒跑就寫沒跑，或現在跑。")
    code_changed = [p for p in mod_turn if is_code_file(p, cfg.get("code_exts") or [])]
    if code_changed:
        cases = [p for p in mod_turn if is_verify_case(p, globs)]
        if not cases and not related:
            names = "、".join(Path(p).name for p in code_changed[:4])
            extra = f"（{_pass_why(this_turn, receipts, unrelated, mod_turn)}）" if this_turn else ""
            hits.append(f"(d) 宣告完成且改了程式碼（{names}）但本回合沒新增／更新驗證 case、也沒有對得上的 PASS 收據{extra}：改了碼沒驗證 case。"
                        "補一個會紅的 case 再跑綠（印 PASS），或說明為何不需要。")
    # (e) 只檢本版報告（post_tool_use 一定寫入 j／k 兩鍵）；升級前 emit 的舊報告沒這兩鍵，不拿它擋
    if aec_emitted and isinstance(aec, dict) and "j_evidence_path" in aec and "k_followups" in aec:
        if aec_evidence_missing(aec.get("j_evidence_path"), bool(receipts)):
            hits.append(f"(e) 收尾檢核 (j) 證據持久路徑缺或不存在，但本 session 有 {len(receipts)} 筆驗證收據。"
                        f"填帳本路徑（{ledger_path(sid or 'SID')}）或其他真存在的證據檔。")
        if aec_followups_missing(aec.get("k_followups")):
            hits.append("(e) 收尾檢核 (k) 追蹤項是空字串。有就一行一項，沒有就寫「無」。")
    if not hits:
        return None
    note = ""
    if any(r.get("exit_unknown") for r in related):
        note = "\n註：有 PASS 收據的 exit 未知（dict 回應沒有 exit 欄），只憑哨兵認定。"
    return ("[Guardian:ReconcileGate] 收尾宣稱對不上本回合的驗證收據：\n"
            + "\n".join("  ✗ " + h for h in hits)
            + "\n收據來源：Bash／PowerShell 輸出的哨兵與 exit code（PostToolUse 落帳）。"
            "改成事實句（沒跑就說沒跑），或現在跑出對應收據再重新收尾。" + note)


# ─── 量尺閘 ───────────────────────────────────────────────────────────
MEASURE_DEFAULTS: Dict[str, Any] = {"enabled": True, "runtime_gate_timeout_s": 2}
HUB_REL = ".claude/overview-hub.json"


def measure_cfg(config: Dict[str, Any]) -> Dict[str, Any]:
    c = dict(MEASURE_DEFAULTS)
    sec = (config or {}).get("measure_gate")
    if isinstance(sec, dict):
        c.update(sec)
    return c


def load_verify_chains(root: Path) -> Dict[str, Dict[str, str]]:
    """<root>/.claude/overview-hub.json 的 `verify_chains{part:{runtime_gate,pre,run,collect,cleanup}}`；沒有回 {}。"""
    try:
        data = json.loads((Path(root) / HUB_REL).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    vc = data.get("verify_chains") if isinstance(data, dict) else None
    return {str(k): v for k, v in vc.items() if isinstance(v, dict)} if isinstance(vc, dict) else {}


def run_runtime_gate(cmd: str, timeout_s: float, cwd: Optional[str] = None) -> Tuple[bool, str]:
    """跑 runtime_gate 指令（exit 0＝環境就緒）。回 (就緒, 原因)。逾時／找不到／非零都算未就緒。"""
    try:
        argv = shlex.split(cmd.replace("\\", "/"))
    except ValueError as e:
        return False, f"runtime_gate 指令解析失敗：{e}"
    if not argv:
        return False, "runtime_gate 指令為空"
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout_s, cwd=cwd or None,
                           creationflags=_NO_WINDOW)
    except subprocess.TimeoutExpired:
        return False, f"runtime_gate 逾時 {timeout_s}s：{cmd}"
    except (FileNotFoundError, OSError) as e:
        return False, f"runtime_gate 無法啟動：{e}"
    if r.returncode != 0:
        tail = ((r.stderr or "") + (r.stdout or "")).strip().splitlines()
        return False, f"runtime_gate exit {r.returncode}：{(tail[-1] if tail else '')[:120]}"
    return True, ""


def measure_cmds_of(own_mod_files: List[Dict[str, Any]],
                    lookup: Callable[[str], Optional[Tuple[Path, Dict[str, Any]]]]) -> List[str]:
    """本 session 改過的檔命中的部位量尺指令（對帳閘「PASS 對得上」的第三種對法）。"""
    out: List[str] = []
    for m in own_mod_files or []:
        p = (m or {}).get("path", "")
        hit = lookup(p) if p else None
        if not hit:
            continue
        cmd = str(((hit[1].get("measure") or {}).get("cmd")) or "").strip()
        if cmd and cmd not in out:
            out.append(cmd)
    return out


def measure_gate_reason(own_mod_files: List[Dict[str, Any]], receipts: List[Dict[str, Any]], turn_seq: int,
                        lookup: Callable[[str], Optional[Tuple[Path, Dict[str, Any]]]], cfg: Dict[str, Any],
                        chains_of: Callable[[Path], Dict[str, Dict[str, str]]] = load_verify_chains,
                        runner: Callable[[str, float, Optional[str]], Tuple[bool, str]] = run_runtime_gate,
                        ) -> Tuple[Optional[str], List[str]]:
    """改到的部位有量尺 → 先 runtime_gate（量不了就擋並說原因）→ 找「該部位最後一次修改之後」（比 at，沒有比序號，再沒有比 turn）、
    同 root、exit 0／None 且 failed=0 的 DONE 且 cmd 含量尺指令，沒有→擋。回 (擋訊息或 None, 沒量尺的部位名清單＝提醒補)。
    小修也要重跑尺：同 turn 再改一行，之前的 DONE 就在修改之前、不算；尺太重的部位把量尺改成子集指令（表上那格）。"""
    parts: Dict[str, Dict[str, Any]] = {}
    for m in own_mod_files or []:
        p = (m or {}).get("path", "")
        if not p:
            continue
        hit = lookup(p)
        if not hit:
            continue
        root, row = hit
        key = f"{str(root).replace(chr(92), '/').lower()}|{row.get('part_short', '')}"
        _t = m.get("last_turn_seq", m.get("turn_seq"))
        edit_turn = int(_t) if _t is not None else 0      # legacy 無 turn 欄：任何時候的 DONE 都算量過
        rec = parts.setdefault(key, {"root": root, "row": row, "edit_turn": edit_turn, "edit_at": "", "edit_seq": None, "files": []})
        rec["edit_turn"] = max(rec["edit_turn"], edit_turn)
        at = str(m.get("last_at") or m.get("at") or "")
        if at > rec["edit_at"]:
            rec["edit_at"] = at
        seq = m.get("last_seq")
        if seq is not None and (rec["edit_seq"] is None or int(seq) > rec["edit_seq"]):
            rec["edit_seq"] = int(seq)
        rec["files"].append(p)
    blocks: List[str] = []
    no_measure: List[str] = []
    timeout = float(cfg.get("runtime_gate_timeout_s", 2))
    for rec in parts.values():
        row, root = rec["row"], rec["root"]
        measure = row.get("measure") or {}
        cmd = str(measure.get("cmd") or "").strip()
        part = row.get("part_short") or row.get("part") or "?"
        if not cmd:
            no_measure.append(part)
            continue
        chain = (chains_of(root) or {}).get(part) or {}
        gate = str(chain.get("runtime_gate") or "").strip()
        if gate:
            ok, why = runner(gate, timeout, str(root))
            if not ok:
                blocks.append(f"部位【{part}】有量尺（{measure.get('method') or cmd}）但執行環境未就緒：{why}。"
                              "這次量不了就不能宣告完成：寫明量不了的原因與何時能量，或讓環境就緒後跑尺。")
                continue
        ok_done = done_receipts(receipts, min_turn=rec["edit_turn"], cmd_contains=cmd, min_at=rec["edit_at"] or None,
                                min_seq=rec["edit_seq"], root=str(root))
        if ok_done:
            continue
        any_done = done_receipts(receipts, cmd_contains=cmd, require_ok=False)
        if any_done:
            last = any_done[-1]
            failed = next(((s.get("kv") or {}).get("failed") for s in last.get("sentinels") or []
                           if isinstance(s, dict) and (s.get("kv") or {}).get("failed") is not None), None)
            if last.get("exit_code") not in (None, 0) or (failed is not None and str(failed) != "0"):
                why = f"最近一次跑尺 exit={last.get('exit_code')} failed={failed}，尺沒過"
            elif not _root_match(last, str(root)):
                why = f"最近一次跑尺的 cwd／project_root（{last.get('project_root') or last.get('cwd')}）不是這個部位的 root"
            else:
                why = "最近一次跑尺在這個部位最後一次修改之前（先量後改不算）"
            blocks.append(f"部位【{part}】有量尺「{measure.get('method') or ''}｜`{cmd}`｜{measure.get('threshold') or ''}」，{why}。"
                          f"改完再跑一次 `{cmd}`（尾行 `<NAME> DONE` 或 `<NAME>_CHECK DONE`，exit 0、failed=0）再收尾。")
        else:
            blocks.append(f"部位【{part}】有量尺「{measure.get('method') or ''}｜`{cmd}`｜{measure.get('threshold') or ''}」，"
                          f"改了 {len(rec['files'])} 個檔（最後在 turn {rec['edit_turn']}）但之後沒有這把尺的 DONE 收據。"
                          f"跑 `{cmd}`（尾行要印 `<NAME> DONE` 或 `<NAME>_CHECK DONE`）再收尾。")
    reason = None
    if blocks:
        reason = "[Guardian:MeasureGate] 改到有量尺的部位，收尾前要跑過那把尺：\n" + "\n".join("  ✗ " + b for b in blocks)
    return reason, no_measure


def measure_advisory(parts_without: Iterable[str]) -> Optional[str]:
    names = sorted({p for p in parts_without if p})
    if not names:
        return None
    return ("[Guardian:MeasureGate] 改到的部位沒有量尺欄：" + "、".join(names)
            + "。在 .claude/overview-map.md 的「量尺（量法｜指令｜門檻）」欄補一把尺，收尾才有東西可對。")

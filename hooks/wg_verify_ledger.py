"""wg_verify_ledger.py：驗證帳本與收尾對帳（H6 帳本／Stop 對帳、H8 量尺閘）的純函式。

做什麼：
  PostToolUse 收 Bash／PowerShell 輸出裡的哨兵（`<NAME>_CHECK PASS|FAIL|DONE`、量測類 `<NAME> DONE k=v`）
  與 exit code，連同 VCS 快照、本 turn 改過的檔、驗收規格路徑，落 `workflow/verify-ledger/<sid>.jsonl`
  並進 `state["verify_receipts"][sid]`（cap 50）。
  Stop 對「宣告完成」的話拿收據對帳：說「修好」要有本 turn 且對得上改檔的 PASS（exit 0 或無 exit）或部位量尺的合格自寫收據、
  說「量了」要有 DONE、說「試過」要有執行類工具呼叫、AEC 要有證據路徑（j）與追蹤項（k）。
  不看措辭、每次 Stop 都判：改了程式碼要有仍存在的驗證 case 被新增或修改（PASS 不代替）；改到有量尺的部位要有那把尺在
  最後一次修改之後、同 root、exit 0 且 failed=0 的 DONE（先過 runtime_gate）。
  指令解析只有一套（lib/self_receipt：白名單語法，解析不了的指令一律不算證據）：量尺比對 cmd_matches、整體驗證 is_whole_run、
  「提到改檔」evidence_words（只看實際跑程式那幾段的參數）；收據的 cmd 存完整字串（升級前只存 200 字的舊收據不算）；
  整條指令除了精確對上的量尺片段外出現哨兵字樣，這張收據任何用途都不算。

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
from typing import Any, Callable, Dict, Iterable, List, Optional, Pattern, Tuple, Union

from wg_core import CLAUDE_DIR, WORKFLOW_DIR, find_vcs_root, resolve_project_root
from wg_evasion import CLAIM_RES, claims_completion, strip_quoted_spans


def _load_self_receipt_module():
    """lib/self_receipt.py 用本檔所在樹的那份（檔案路徑載入）：按名字 import 會依 sys.path 拿到別棵樹（live）的 lib，
    收據的指令正規化兩端就不是同一套。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_wg_self_receipt", Path(__file__).resolve().parents[1] / "lib" / "self_receipt.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_self_receipt = _load_self_receipt_module()
cmd_matches, evidence_words, is_whole_run = (_self_receipt.cmd_matches, _self_receipt.evidence_words,
                                             _self_receipt.is_whole_run)
unsupported_syntax, leading_cd = _self_receipt.unsupported_syntax, _self_receipt.leading_cd

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


def agent_receipt_key(sid: str, agent_id: str) -> str:
    """子代理的收據在 state["verify_receipts"] 裡的鍵（與主 session 的 sid 分開，主帳不混入子代理的）。"""
    return f"{sid}#agent:{agent_id}"


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
# 子句切在 ，；,;。！!與換行，再加轉折詞（但／不過／而／然而／只是／可是）之後另起子句；
# 問號留在子句裡給 exclude（`[?？]\s*$`）判疑問
_CLAUSE_SPLIT_RE = re.compile(r"[，；,;。！!\n]+|但|不過|而|然而|只是|可是")
# 第三方主語只在「第三方名詞是子句開頭主語（子句前 4 字內）」且「宣稱詞前沒有 我／本／已」時才算轉述
_THIRD_PARTY_HEAD_RE = re.compile(
    r"^[^，。；！？\n]{0,4}?(?:使用者|對方|同事|codex|它|他|她|log|輸出|顯示)", re.IGNORECASE
)
_OWN_MARK_RE = re.compile(r"[我本已]")


def _third_party_said(head: str) -> bool:
    """head＝子句裡宣稱詞之前的文字。第三方在子句開頭且沒有「我／本／已」→ 轉述。"""
    return bool(_THIRD_PARTY_HEAD_RE.search(head)) and not _OWN_MARK_RE.search(head)


def _claims(text: str, kind: str, phrases: Optional[Dict[str, Pattern]] = None) -> bool:
    """逐子句判：子句命中 <kind> 詞、同子句無 <kind>_exclude 詞（否定／疑問只取消同子句；轉折詞後另起子句）、
    不是第三方轉述（第三方名詞在子句開頭且宣稱詞前沒有我／本／已）；引號／code span 內容先剝掉（引用閘文字不算宣稱）。"""
    if not text:
        return False
    ph = phrases or CLAIM_RES
    pos, neg = ph[kind], ph[f"{kind}_exclude"]
    for clause in _CLAUSE_SPLIT_RE.split(strip_quoted_spans(text[-3000:])):
        clause = clause.strip()
        m = pos.search(clause)
        if not m or neg.search(clause):
            continue
        if _third_party_said(clause[:m.start()]):
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


_CD_RE = re.compile(r"(?:^|[\s;&|(])(?:cd|pushd|popd|set-location|push-location|pop-location|sl|chdir)(?:\s|$)",
                    re.IGNORECASE)
LEGACY_CMD_CAP = 200          # 升級前的 state 收據 cmd 只存前 200 字
_ARG_SENTINEL_RE = re.compile(r"_CHECK\s+(?:PASS|FAIL|DONE)|\w\s+DONE(?!\w)")    # 參數裡的哨兵字樣（不要求行首與名字）
_ESC_RE = re.compile(r"\\(x[0-9A-Fa-f]{1,2}|u[0-9A-Fa-f]{4}|0?[0-7]{1,3}|[abefnrtv])")
_ESC_CHARS = {"a": "\a", "b": "\b", "e": "\x1b", "f": "\f", "n": "\n", "r": "\r", "t": "\t", "v": "\v"}
_arg_res: List[Pattern] = []  # _ARG_SENTINEL_RE ＋ config sentinel_regex（去掉開頭 ^）；第一次用到才讀


def has_cd(cmd: str) -> bool:
    """cmd 任何位置含 cd／pushd／popd／Set-Location／sl／chdir token → 收據的 cwd 不可信（root_uncertain）。"""
    return bool(_CD_RE.search(str(cmd or "")))


def _shell_of(receipt: Dict[str, Any]) -> str:
    """收據是哪種 shell 跑的（PostToolUse 記的 tool）：PowerShell 依 PowerShell 規則解析，其餘依 bash。"""
    return "powershell" if str(receipt.get("tool") or "") == "PowerShell" else "bash"


def _cmd_complete(receipt: Dict[str, Any]) -> bool:
    """收據存的是完整指令：新收據帶 cmd_full；升級前的只存前 200 字，滿 200 字的不知道後面還接了什麼 → 不算證據。"""
    return bool(receipt.get("cmd_full")) or len(str(receipt.get("cmd") or "")) < LEGACY_CMD_CAP


def _trusted(receipt: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """收據的指令完整、根可信才回（開頭單一絕對路徑的 `cd <路徑> && …`：執行根 cwd 換成該路徑；路徑在原專案根之內就保留
    原專案根當樹根，否則樹根也換成它）；不完整或含其他 cd → None。
    可解析的指令只看同一套斷詞判換目錄（`c"d" C:/live; 量尺` 的 c"d" 是 cd；`量尺 # cd x` 的 cd 在註解裡不是）；
    解析不了的才退回原字串比對 has_cd 與 PostToolUse 記的 root_uncertain（那種收據本來也當不了證據）。"""
    raw, sh = str(receipt.get("cmd") or ""), _shell_of(receipt)
    if not _cmd_complete(receipt):
        return None
    cd = leading_cd(raw, sh)
    if cd:                                                        # cd 進原專案根之內：樹還是原專案根（從 tests/ 點名 ../hooks 的測試照算）
        pr = str(receipt.get("project_root") or "")
        return {**receipt, "project_root": pr if pr and _under(cd, pr) else cd, "cwd": cd, "root_uncertain": False}
    moved = (_self_receipt.changes_dir(raw, sh) if not unsupported_syntax(raw, sh)
             else bool(receipt.get("root_uncertain") or has_cd(raw)))
    return None if moved else receipt


def _arg_sentinel_res() -> List[Pattern]:
    if not _arg_res:
        _arg_res.append(_ARG_SENTINEL_RE)
        try:
            from wg_core import load_config
            rules = compile_sentinel_rules(((load_config() or {}).get("verify_ledger") or {}).get("sentinel_regex"))
        except Exception as e:  # noqa: BLE001  讀不到設定 → 只認預設格式，浮一行
            print(f"[verify-ledger] 讀不到 sentinel_regex，參數裡的哨兵字樣只認預設格式：{type(e).__name__}: {e}",
                  file=sys.stderr)
            rules = []
        for rule in rules:                                        # 輸出端的錨點拿掉：指令裡的字樣前後接了別的字也算
            _arg_res.append(re.compile(_drop_anchors(rule["re"].pattern), rule["re"].flags | re.MULTILINE))
    return _arg_res


def _drop_anchors(pat: str) -> str:
    """regex 裡所有錨點（字元類 [...] 以外、沒跳脫的 ^ $，以及 \\A \\Z \\z）拿掉，在旗標後、群組裡的也拿：
    `(?i)^X_OK$`、`^(?:X_OK$)` 都變成只找 X_OK 這串字。"""
    out, i, in_class = [], 0, False
    while i < len(pat):
        c = pat[i]
        if c == "\\" and i + 1 < len(pat):
            if in_class or pat[i + 1] not in "AZz":
                out.append(pat[i:i + 2])
            i += 2
            continue
        if in_class:
            in_class = c != "]" or (out and out[-1] in ("[", "[^"))      # 開頭緊接的 ] 是字面字元
            out.append(c)
        elif c == "[":
            in_class = True
            out.append("[^" if pat[i + 1:i + 2] == "^" else "[")
            i += 1 if pat[i + 1:i + 2] == "^" else 0
        elif c not in "^$":
            out.append(c)
        i += 1
    return "".join(out)


def _unescape(t: str) -> str:
    """echo -e／printf 會還原的跳脫（\\t \\n \\x41 \\0101 \\u0041）先還原，再找哨兵字樣。"""
    def rep(m: "re.Match") -> str:
        g = m.group(1)
        if g[0] in "xu":
            return chr(int(g[1:], 16))
        return chr(int(g, 8)) if g[0].isdigit() else _ESC_CHARS[g]
    return _ESC_RE.sub(rep, t)


_VAR_REF_RE = re.compile(r"\$(?:\{[^}]*\}|[A-Za-z_][\w:]*|[0-9@*#?$!-])")


def _prints_sentinel(raw: str, shell: str, skip: Optional[Tuple[int, int]] = None, ruler: str = "") -> bool:
    """同一條指令裡有字寫了哨兵字樣（echo X_CHECK PASS、printf、Write-Output、xargs echo、`V="X_CHECK PASS"; echo $V`、
    `$s = '… DONE'`、`PS4='… DONE '`…）：成功行只能來自被執行的驗證程式，指令裡寫好的一律不算，量尺路、一般證據路、
    整體驗證路都用這一個檢查。skip＝精確對上的量尺片段（match_span 的 [start, end)）、ruler＝表上的量尺原字串：片段裡只有
    與表上那段逐字相同的字不算（量尺自帶的 `&& echo … DONE`）；多出來或寫法不同的字照查（行內環境指定 `X='… DONE' 量尺`、
    正規化後才對上的腳本路徑 `"./X_CHECK DONE/../run_verify.py"`）。重導向目標 `2>"X_CHECK PASS"` 也照查（註解以外的字都算）。
    echo -e／printf 的跳脫先還原；變數引用（`X_CHECK$x PASS`，變數空字串時印出來就是哨兵）拿掉再找一次。"""
    table = _self_receipt.split_shell(ruler)[0] if skip else []
    for i, ch in enumerate(_self_receipt.split_shell(raw, shell)[0]):
        ws = list(ch.words)
        k = i - skip[0] if skip else -1
        if 0 <= k < len(table) and i < skip[1]:
            for w in table[k].words:                                  # 逐字扣掉表上那段的字（同一個字出現幾次扣幾次）
                if w in ws:
                    ws.remove(w)
        t = _unescape(" ".join([*ws, *ch.targets]))
        text = t + "\x00" + _VAR_REF_RE.sub("", t)          # \x00 不是空白，兩段之間湊不出哨兵
        if any(rx.search(text) for rx in _arg_sentinel_res()):
            return True
    return False


def _cwd_of(receipt: Dict[str, Any]) -> str:
    """收據的指令是從哪裡跑的（相對路徑照它解析）：cwd，沒有才用 project_root。"""
    return str(receipt.get("cwd") or receipt.get("project_root") or "")


_RUNNER_CACHE: Dict[str, Tuple[str, ...]] = {}
EXTRA_RUNNER_HINT = ("專案自製的測試工具（例：Unity 編輯器 CLI）可在 overview-hub.json 的 `extra_runner_progs` 加程式名"
                     "（與內建清單取聯集；專案層的清單會蓋掉公司層的，兩邊都要就寫在專案層）")


def _extra_runners(receipt: Dict[str, Any]) -> Tuple[str, ...]:
    """收據所在專案設定擴充的執行程式名：overview_hub 段的 extra_runner_progs，走三層合併（wg_overview._cfg，與導讀卡、
    量尺閘同一套）；行程內依根快取。設定有錯 → ValueError（寫碼查核判定錯誤一律擋，訊息列出錯誤）。"""
    root = str(receipt.get("project_root") or receipt.get("cwd") or "")
    if root not in _RUNNER_CACHE:
        from wg_core import load_config
        from wg_overview import _cfg
        c = _cfg(load_config(), Path(root) if root else None)
        if c["_errors"]:
            raise ValueError(f"overview-hub 設定錯誤（{root or '根層'}）：" + "；".join(c["_errors"][:3]))
        _RUNNER_CACHE[root] = tuple(c.get("extra_runner_progs") or ())
    return _RUNNER_CACHE[root]


def _in_tree(receipt: Dict[str, Any]) -> bool:
    """跑程式的指令沒有指到收據根以外（`python ../live/run_verify.py`、`python C:\\…\\.claude\\run_verify.py`、`../live/verify.sh`、
    `pytest C:/live/tests` 量的都是別棵樹；相對路徑照 cwd 解析；設定宣告過的工具裝在樹外照算）。收據沒根資訊 → 不比（同 _root_ok）。"""
    root = str(receipt.get("project_root") or receipt.get("cwd") or "")
    return not _self_receipt.outside_paths(str(receipt.get("cmd") or ""), _shell_of(receipt), root, _cwd_of(receipt),
                                           _extra_runners(receipt))


def _clean(receipt: Dict[str, Any]) -> bool:
    """收據的指令能當一般證據（對帳 (a) 提到改檔、(b) 量了、根層 worktree 的 pytest DONE）：完整、白名單語法、是 evidence_steps
    的形狀（cd／環境設定之後全是跑程式的指令（含設定擴充的 extra_runner_progs）、只用 && 串、stdout 沒導走、後面只准留結尾的
    過濾）、沒指到收據根以外、指令裡沒寫哨兵字樣。"""
    raw, sh = str(receipt.get("cmd") or ""), _shell_of(receipt)
    return (_cmd_complete(receipt) and not unsupported_syntax(raw, sh)
            and _self_receipt.evidence_steps(raw, sh, _extra_runners(receipt)) is not None
            and _in_tree(receipt) and not _prints_sentinel(raw, sh))


def _ruler_ran(measure_cmd: str, receipt: Dict[str, Any], part_root: str = "") -> bool:
    """收據跑了表上這把尺（match_span，依收據的 shell 解析；腳本照路徑認：收據照它的 cwd、量尺照部位根 part_root，
    沒給部位根就共用收據的）；指令要完整、沒指到收據根以外，而且量尺片段以外沒有任何字寫了哨兵字樣。"""
    raw, sh = str(receipt.get("cmd") or ""), _shell_of(receipt)
    if not str(measure_cmd).strip() or not _cmd_complete(receipt):
        return False
    span = _self_receipt.match_span(str(measure_cmd), raw, sh, _cwd_of(receipt), str(part_root or ""))
    return span is not None and not _prints_sentinel(raw, sh, span, str(measure_cmd)) and _in_tree(receipt)


_RULER_FORM = ("量尺前面只准 `cd <絕對路徑> &&` 與環境設定（`X=1`、`export X=1`、`$env:X=\"1\";`、`$x = '字面值';`；"
               "set、unset、pushd、帶 $ 的值、PS4 這類讓 shell 自己印字的變數都不算），"
               "後面只准 `| tail` 或 `| Select-Object -Last N`；請照表上原字串單獨跑。")


def _syntax_note(receipts: Iterable[Dict[str, Any]], verdict: str, rulers: Iterable[str] = ()) -> str:
    """最近一筆帶 verdict 哨兵的收據若因指令寫法不算證據 → 一句說明（是哪一種）；最近那筆寫法正常、是對上表上量尺的收據
    （量尺本身的 echo 不算寫哨兵），或沒有 → ""。"""
    rulers = list(rulers)
    for r in reversed(list(receipts)):
        if verdict not in _verdicts(r):
            continue
        raw, sh = str(r.get("cmd") or ""), _shell_of(r)
        head = f"`{' '.join(raw.split())[:60]}`"
        if not _cmd_complete(r):
            return f"最近那筆收據 {head} 是升級前只存前 200 字的舊收據，看不出整條指令，不算證據；請重跑。"
        why = unsupported_syntax(raw, sh)
        if why:
            return f"這條指令 {head} 含解析不了的語法（{why}），不算跑了量尺；請照表上原字串單獨跑。"
        if any(_ruler_ran(mc, r) for mc in rulers):
            return ""
        if _prints_sentinel(raw, sh):
            return (f"這條指令 {head} 的參數裡寫了哨兵字樣（echo／printf／Write-Output 印出來的），不算任何證據；"
                    "哨兵只能由被執行的程式印出。")
        if any(_self_receipt.ruler_in(mc, raw, sh, _cwd_of(r)) for mc in rulers):
            return f"這條指令 {head} 裡有量尺，但前後接了別的指令。{_RULER_FORM}"
        extra = _extra_runners(r)
        if _self_receipt.evidence_steps(raw, sh, extra) is None:
            others = _self_receipt.non_runners(raw, sh, extra)
            return (f"這條指令 {head} 不是單純跑驗證程式的形狀（夾了讀檔或印字的指令、用 ; 或 || 串、或把輸出導走），"
                    "印出來的哨兵分不出是誰印的、哪一段真的過了，不算證據；請單獨跑驗證程式（前面只准 cd 與環境設定、多段只用 && 串）。"
                    + (f"不算執行程式的：{'、'.join(others[:3])}；{EXTRA_RUNNER_HINT}。" if others else ""))
        if not _in_tree(r):
            outside = _self_receipt.outside_paths(raw, sh, str(r.get("project_root") or r.get("cwd") or ""), _cwd_of(r), extra)
            return f"這條指令 {head} 指到收據根以外的路徑（{'、'.join(outside[:3])}），量的不是這棵樹；請在專案根照表上原字串跑。"
        return ""
    return ""


def _stem_of(path: str) -> str:
    name = _norm_path(path).rsplit("/", 1)[-1]
    return name.rsplit(".", 1)[0] if "." in name else name


def _usable_cmd(receipt: Dict[str, Any]) -> Optional[str]:
    """「提到改的檔」只比實際跑程式那幾段的參數（lib/self_receipt.evidence_words；前置設定、cd、環境指定都不參與），
    小寫、斜線正規化、空白壓一格。指令不完整、根不可信（開頭單一 cd 以外的 cd）、不能當一般證據
    （_clean：白名單語法、只跑程式且只用 && 串、沒指到別棵樹、沒寫哨兵字樣）→ None。"""
    r = _trusted(receipt)
    if r is None or not _clean(r):
        return None
    return " ".join(_norm_path(" ".join(evidence_words(str(r.get("cmd") or ""), _shell_of(r), _extra_runners(r)))).split())


def _ruler_any(receipt: Dict[str, Any], measure_cmds: Iterable[str]) -> bool:
    """收據跑了其中一把部位量尺（_ruler_ran）：聲稱驗到該部位全部改檔。"""
    return any(_ruler_ran(mc, receipt) for mc in measure_cmds or [])


def _whole_run(receipt: Dict[str, Any]) -> bool:
    """整體驗證：執行根自己的 run_verify.py（照完整路徑身分）或不縮範圍的 pytest；只認白名單語法、前面只准前置設定、
    後面只准尾端過濾、沒指到收據根以外、整條指令沒寫哨兵字樣。涵蓋範圍見 _in_exec_root。"""
    raw, sh = str(receipt.get("cmd") or ""), _shell_of(receipt)
    return (_cmd_complete(receipt) and is_whole_run(raw, sh, _cwd_of(receipt)) and _in_tree(receipt)
            and not _prints_sentinel(raw, sh))


def _in_exec_root(receipt: Dict[str, Any], path: str) -> bool:
    """整體驗證只涵蓋實際執行根（開頭 `cd <絕對路徑>` 已換進收據 cwd，沒有就是收據 cwd）之下的改檔；不套 _root_ok 的
    上下層互通（從子專案跑 `pytest -q` 只收集子目錄的測試）。收據沒根資訊 → 不比。"""
    base = _cwd_of(receipt)
    return not _norm_path(base) or _under(path, base)


def _under(path: str, base: str) -> bool:
    """path 是 base 本身或在 base 底下（斜線、大小寫正規化後比）。"""
    p, b = _norm_path(path), _norm_path(base)
    return p == b or p.startswith(b + "/")


def _cmd_names_path(cmd: str, path: str) -> bool:
    """cmd 提到這個改檔：stem 整詞（≥3 字）、test_<stem>／verify_<stem>／<stem>_test、或改檔所在的 `<dir>/verify/`。"""
    stem = _stem_of(path).lower()
    if len(stem) >= 3 and re.search(r"(?<![a-z0-9_])" + re.escape(stem) + r"(?![a-z0-9_])", cmd):
        return True
    if stem and any(t in cmd for t in (f"test_{stem}", f"verify_{stem}", f"{stem}_test")):
        return True
    d = _norm_path(path).rsplit("/", 1)[0] if "/" in _norm_path(path) else ""
    return bool(d and (d + "/verify/" in cmd or (d.rsplit("/", 1)[-1] + "/verify/") in cmd))


def claimed_paths(receipt: Dict[str, Any], mod_paths: Iterable[str], measure_cmds: Iterable[str] = ()) -> List[str]:
    """收據聲稱驗到的改檔（不看先後）：部位量尺指令、整體驗證＝執行根之下的改檔（量尺在這裡沒有部位根可比，
    `cd 子專案 && 量尺` 對上的是子專案自己那支，只涵蓋子專案）；否則實際驗證段提到的那幾個。指令不完整或根不可信 → 沒有。"""
    r = _trusted(receipt)
    if r is None:
        return []
    paths = list(mod_paths or [])
    if _ruler_any(r, measure_cmds) or _whole_run(r):
        return [p for p in paths if _in_exec_root(r, p)]
    cmd = _usable_cmd(r)
    return [p for p in paths if _cmd_names_path(cmd, p)] if cmd else []


RootSpec = Union[None, str, Callable[[str], Optional[str]]]


def _file_root(root: RootSpec, path: str) -> Optional[str]:
    """root 是單一根字串（全部改檔同根）或「改檔 → 根」函式；None＝不比根。"""
    return root(path) if callable(root) else root


def _root_ok(receipt: Dict[str, Any], file_root: Optional[str]) -> bool:
    """收據根（project_root，沒有就 cwd）與改檔的根要在同一棵樹：相同、或互為上下層（從上層跑測試是正當驗證）；
    兩根互不包含才算對不上。收據沒有根資訊、或改檔根不可判定 → 不比（照舊）。"""
    rr = _norm_path(str(receipt.get("project_root") or receipt.get("cwd") or ""))
    if not rr or not file_root:
        return True
    fr = _norm_path(str(file_root))
    return rr == fr or rr.startswith(fr + "/") or fr.startswith(rr + "/")


def vcs_root_of(path: str) -> Optional[Path]:
    """path 所在的 VCS 根（.git／.svn，往上不設層數上限）；最近的根是家目錄或磁碟根就不算，回 None。"""
    if not path:
        return None
    p = Path(path)
    if not p.is_absolute():
        return None
    found = find_vcs_root(p if p.is_dir() else p.parent)
    if not found:
        return None
    root = found[1]
    if root.parent == root or _norm_path(str(root)) == _norm_path(str(Path.home())):
        return None
    return root


def file_root_of(path: str) -> Optional[str]:
    """改檔所屬的根（對帳閘比收據根用）：先用 lib/project_root（收據的 project_root 也是它算的，兩邊同一把尺）；
    它找不到（舊規則最多往上 4 層、~/.claude 本身不當根）再退 VCS 根；都沒有回 None＝根不可判定，不比根。"""
    if resolve_project_root is not None:
        try:
            p = Path(path)
            found = resolve_project_root(str(p if p.is_dir() else p.parent)).path
            if found:
                return str(found)
        except (OSError, ValueError) as e:
            print(f"[Guardian:ReconcileGate] project_root 判定失敗，改用 VCS 根：{type(e).__name__}: {e}", file=sys.stderr)
    vr = vcs_root_of(path)
    return str(vr) if vr else None


def receipt_relates(receipt: Dict[str, Any], mod_paths: Iterable[str], verify_globs: Iterable[str] = (),
                    measure_cmds: Iterable[str] = (), root: RootSpec = None) -> bool:
    """PASS 收據「對得上」改檔＝下列任一（verify glob 單獨不算；含 cd 的收據一律不算）：
    (a) cmd 含修改檔 stem 作整詞（stem ≥3 字）；(b) cmd 含 test_<stem>／verify_<stem>／<stem>_test；
    (c) cmd 是部位量尺指令，或執行根自己的 run_verify.py／無檔名參數的 pytest（整體驗證）；兩者都只涵蓋執行根之下的改檔；
    (d) cmd 含修改檔所在的 verify 目錄 `<dir>/verify/`。(a)(b)(d) 只看實際驗證段的參數。
    再加根要對：收據根（project_root，沒有就 cwd；開頭 `cd <根> &&` 用該路徑）與該改檔的根相同或互為上下層；任一邊沒有根資訊
    不比。指令只認白名單語法（lib/self_receipt），解析不了的不算。"""
    r = _trusted(receipt)
    if r is None:
        return False
    paths = list(mod_paths or [])
    if not paths:
        return _ruler_any(r, measure_cmds) or _whole_run(r)
    return any(_root_ok(r, _file_root(root, p)) for p in claimed_paths(r, paths, measure_cmds))


def _after_last_edit(receipt: Dict[str, Any], mod: Optional[Dict[str, Any]]) -> bool:
    """收據在這個改檔最後一次修改之後。修改紀錄沒有 at／seq（升級前的 legacy entry）→ 不比（照舊）。"""
    if not isinstance(mod, dict):
        return True
    at, seq = mod.get("last_at") or mod.get("at"), mod.get("last_seq")
    if not at and seq is None:
        return True
    turn = mod.get("last_turn_seq", mod.get("turn_seq"))
    return _receipt_after(receipt, at, seq, int(turn) if turn is not None else -1)


def pass_receipts(receipts: Iterable[Dict[str, Any]], turn_seq: Optional[int] = None) -> List[Dict[str, Any]]:
    """合格 PASS：有 PASS 哨兵、沒有 FAIL 哨兵（`pytest a; pytest b | tail` 前一段紅了不能拿後一段的綠背書）且 exit_code 為
    None 或 0（exit≠0 的 PASS 不算）；給 turn_seq 時只認該 turn。
    exit 為 None 的在回傳的 dict 上標 exit_unknown=True（dict／PowerShell 回應沒有 exit 欄）。"""
    out = []
    for r in receipts:
        if turn_seq is not None and int(r.get("turn_seq", -1)) != int(turn_seq):
            continue
        verdicts = _verdicts(r)
        if "PASS" in verdicts and "FAIL" not in verdicts and r.get("exit_code") in (None, 0):
            if r.get("exit_code") is None:
                r = {**r, "exit_unknown": True}
            out.append(r)
    return out


def related_pass_receipts(receipts: Iterable[Dict[str, Any]], turn_seq: Optional[int], mod_paths: Iterable[str],
                          verify_globs: Iterable[str], measure_cmds: Iterable[str] = (),
                          root: RootSpec = None, mod_records: Optional[Dict[str, Dict[str, Any]]] = None,
                          ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """合格 PASS 再分「對得上」與「對不上」兩堆。給 mod_records（改檔路徑 → 修改紀錄）時，收據對上的每個改檔
    都要在該檔最後一次修改之後才算對得上。對不上的標原因：other_root＝cmd 提到改檔但根不對；before_edit＝跑在修改之前的檔。"""
    paths = list(mod_paths or [])
    related, unrelated = [], []
    for r0 in pass_receipts(receipts, turn_seq):
        r = _trusted(r0) or r0
        named = claimed_paths(r, paths, measure_cmds)
        if not receipt_relates(r, paths, verify_globs, measure_cmds, root):
            unrelated.append({**r, "other_root": True} if named else r)
            continue
        claimed = [p for p in named if _root_ok(r, _file_root(root, p))]
        stale = [p for p in claimed if not _after_last_edit(r, (mod_records or {}).get(p))]
        if stale:
            unrelated.append({**r, "before_edit": stale})
        else:
            related.append(r)
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


def _to_utc(s: str):
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _receipt_after(receipt: Dict[str, Any], edit_at: Optional[str], edit_seq: Optional[int], edit_turn: int) -> bool:
    """收據要在該部位最後一次修改之後：先比 at（fromisoformat 轉 UTC 再比，不同時區 offset 也對）；at 同秒（精度到秒）比 session 內序號
    receipt.seq > edit.seq；沒有 at 直接比序號；都沒有退回比 turn。"""
    r_at, r_seq = str(receipt.get("at") or ""), receipt.get("seq")
    ra, ea = (_to_utc(r_at) if r_at else None), (_to_utc(edit_at) if edit_at else None)
    if ra is not None and ea is not None:
        if ra != ea:
            return ra > ea
        if edit_seq is not None and r_seq is not None:
            return int(r_seq) > int(edit_seq)
        return False
    if edit_seq is not None and r_seq is not None:
        return int(r_seq) > int(edit_seq)
    return int(receipt.get("turn_seq", -1)) >= int(edit_turn)


def done_receipts(receipts: Iterable[Dict[str, Any]], turn_seq: Optional[int] = None,
                  cmd_contains: str = "", min_turn: Optional[int] = None, require_ok: bool = True,
                  min_at: Optional[str] = None, min_seq: Optional[int] = None,
                  root: Optional[str] = None, *, sentinel_name: str = "", final_prog: str = "") -> List[Dict[str, Any]]:
    """DONE 收據；turn_seq 指定只認該 turn；min_turn／min_at／min_seq 指定要在該修改之後；cmd_contains 指定 cmd 要跑了該量尺
    （cmd_matches：白名單語法、與自寫收據同一套正規化）；require_ok：指令完整、根可信（開頭單一絕對路徑 cd 換成該根）、
    exit 要 0 或 None、沒有 FAIL 哨兵且 failed=<k> 必為 0；root 指定 cwd／project_root 要在該 root 下；sentinel_name 指定 DONE
    必須來自該名字的哨兵（空＝任一 DONE 哨兵）；沒給 cmd_contains 時指令要能當一般證據（_clean）；final_prog 指定跑程式的每一段
    （evidence_steps）都是這支程式。回的是根已換好的收據。"""
    want = cmd_contains.strip()
    out = []
    for r0 in receipts:
        r = _trusted(r0)
        if r is None:
            if require_ok:
                continue          # 指令不完整、或含 cd 不知道量的是哪個專案
            r = r0
        t = int(r.get("turn_seq", -1))
        if turn_seq is not None and t != int(turn_seq):
            continue
        if min_turn is not None and not _receipt_after(r, min_at, min_seq, min_turn):
            continue
        if "DONE" not in _verdicts(r):
            continue
        if sentinel_name and not any(isinstance(s, dict) and str(s.get("name", "")) == sentinel_name
                                     and str(s.get("verdict", "")) == "DONE" for s in r.get("sentinels") or []):
            continue          # DONE 要來自指定名字的哨兵（例：pytest 摘要行映射的 PYTEST_MEASURE）
        if require_ok and (r.get("exit_code") not in (None, 0) or "FAIL" in _verdicts(r) or not _failed_kv_ok(r)):
            continue
        if want:
            if not _ruler_ran(want, r, root or ""):
                continue
        elif not _clean(r):
            continue          # 沒指定量尺：指令要能當一般證據（白名單語法、只跑程式、沒寫哨兵字樣）
        if final_prog:            # 跑程式的每一段都是這支（`pytest a && pytest b` 照算；_clean 已確認形狀）
            runs = _self_receipt.evidence_steps(str(r.get("cmd") or ""), _shell_of(r), _extra_runners(r)) or []
            if not runs or any(s.cmd[0] != final_prog for s in runs):
                continue
        if not _root_match(r, root):
            continue
        out.append(r)
    return out


def is_code_file(path: str, code_exts: Iterable[str]) -> bool:
    low = str(path).lower()
    return any(low.endswith(str(e).lower()) for e in code_exts)


def is_verify_case(path: str, globs: Iterable[str], root: Optional[str] = None) -> bool:
    """path 符合 verify_case_globs 嗎。比對前轉成相對 root 的路徑（前面補一個 `/`，根目錄下的 test_x.py 也比得到）：
    glob 要認的是專案內的 verify/、tests/ 與檔名，專案根所在目錄的名字（`C:\\latest\\proj`）不能參與比對。
    root 沒給或 path 不在 root 底下 → 用絕對路徑（呼叫端負責告知，見 case_debt）。"""
    full, base = _norm_path(path), _norm_path(root or "")
    norm = full[len(base):] if base and full.startswith(base + "/") else full
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
    "code_exts": [".py", ".pyw", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".cs", ".lua", ".c", ".h", ".cc",
                  ".cpp", ".cxx", ".hpp", ".hh", ".java", ".kt", ".kts", ".go", ".rs", ".rb", ".php", ".swift", ".m",
                  ".mm", ".scala", ".dart", ".vue", ".svelte", ".ps1", ".psm1", ".sh", ".bash", ".sql", ".gd",
                  ".shader", ".hlsl", ".glsl"],
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
    before = [r for r in unrelated if r.get("before_edit")]
    if before:
        names = "、".join(Path(p).name for p in before[0]["before_edit"][:3])
        return f"本回合的 PASS（{str(before[0].get('cmd', ''))[:50]}）跑在 {names} 最後一次修改之前，改完沒重跑"
    foreign = [r for r in unrelated if r.get("other_root")]
    if foreign:
        r0 = foreign[0]
        return (f"本回合的 PASS（{str(r0.get('cmd', ''))[:50]}）是在 {r0.get('project_root') or r0.get('cwd')} 跑的，"
                "不是改檔所屬的專案根")
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


def _has_time(m: Dict[str, Any]) -> bool:
    return bool(m.get("last_at") or m.get("at")) or m.get("last_seq") is not None


def _mod_after(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """修改紀錄 a 在 b 之後（先比 at，同秒比 seq；重用 _receipt_after）。"""
    tb = b.get("last_turn_seq", b.get("turn_seq"))
    return _receipt_after({"at": a.get("last_at") or a.get("at") or "", "seq": a.get("last_seq"),
                           "turn_seq": a.get("last_turn_seq", a.get("turn_seq", -1))},
                          b.get("last_at") or b.get("at") or None, b.get("last_seq"),
                          int(tb) if tb is not None else -1)


def is_case_file(path: str, cfg: Dict[str, Any], root: Optional[str] = None) -> bool:
    """驗證案例＝符合 verify_case_globs（相對 root 比）且是程式檔（code_exts）；tests/README.md、verify/notes.txt 不算。"""
    return (is_verify_case(path, cfg.get("verify_case_globs") or [], root)
            and is_code_file(path, cfg.get("code_exts") or []))


def case_exists(path: str) -> bool:
    """案例檔在 Stop 當下還在嗎（刪掉的案例不算補了案例）。"""
    return os.path.isfile(path)


def case_debt(own_mod_files: List[Dict[str, Any]], turn_seq: int, cfg: Dict[str, Any],
              root_of: Callable[[str], Optional[str]]) -> List[str]:
    """補案例的義務（跨回合）：每個根找「本 session 最後一次改驗證案例之後還改過的程式檔」，回這些檔。
    只有 Stop 當下仍存在的案例檔才算（刪除也會記一筆修改，不能拿它清帳）。
    案例判定用相對該根的路徑；拿不到根的程式檔退回絕對路徑，每個路徑 stderr 一行（本函式每次 Stop 只跑一次）。
    修改紀錄沒有 at／seq 的 legacy entry 照舊：只在本回合改過、且本回合同根沒改案例時算。
    範圍外：改的案例是不是對應這次改動，程式判不出來，交給收尾對照（需求目標核心流程 checklist C-G3）由 LLM 判。"""
    exts = cfg.get("code_exts") or []
    by_root: Dict[str, List[Dict[str, Any]]] = {}
    for m in own_mod_files or []:
        if isinstance(m, dict) and m.get("path"):
            by_root.setdefault(str(root_of(m["path"]) or ""), []).append(m)
    owed: List[str] = []
    for root, ms in by_root.items():
        case_of = {m["path"]: is_case_file(m["path"], cfg, root) for m in ms}
        for p in [p for p in case_of if not root and is_code_file(p, exts)]:
            print(f"[verify_ledger] 找不到 {p} 的專案根，案例判定改用絕對路徑", file=sys.stderr)
        cases = [m for m in ms if case_of[m["path"]] and case_exists(m["path"])]
        last_case: Optional[Dict[str, Any]] = None
        for m in cases:
            if _has_time(m) and (last_case is None or _mod_after(m, last_case)):
                last_case = m
        case_this_turn = any(m.get("last_turn_seq", m.get("turn_seq")) is not None
                             and int(m.get("last_turn_seq", m.get("turn_seq"))) == int(turn_seq) for m in cases)
        for m in ms:
            p = m["path"]
            if not is_code_file(p, exts) or case_of[p] or p in owed:
                continue
            if _has_time(m):
                if last_case is None or _mod_after(m, last_case):
                    owed.append(p)
                continue
            t = m.get("last_turn_seq", m.get("turn_seq"))
            if t is not None and int(t) == int(turn_seq) and not case_this_turn:
                owed.append(p)
    return owed


_RECONCILE_HEAD = "[Guardian:ReconcileGate] 收尾宣稱對不上本回合的驗證收據，或改了程式碼還欠驗證案例：\n"
_RECONCILE_SOURCE = "\n收據來源：Bash／PowerShell 輸出的哨兵與 exit code（PostToolUse 落帳）。"
_RECONCILE_TAIL = _RECONCILE_SOURCE + "改成事實句（沒跑就說沒跑），或現在跑出對應收據再重新收尾。"
# 有 pending（擋滿待放行）或欠補案例時，改寫收尾文字解不了帳：只列要補的證據與放行的問法
_RECONCILE_TAIL_EVIDENCE = (_RECONCILE_SOURCE + "補上面列的證據（跑出對得上的收據、補仍存在的案例檔）；"
                            "補不了就照【收尾放行確認】問使用者，改寫收尾文字不會解帳。")


def reconcile_gate_reason(last_text: str, receipts: List[Dict[str, Any]], turn_seq: int,
                          turn_tool_names: Iterable[str], own_mod_files: List[Dict[str, Any]],
                          cfg: Dict[str, Any], aec: Optional[Dict[str, Any]] = None,
                          aec_emitted: bool = False, sid: str = "",
                          phrases: Optional[Dict[str, Pattern]] = None,
                          measure_cmds: Iterable[str] = (), root: RootSpec = None,
                          claims: Iterable[str] = (),
                          self_covered: Optional[Callable[[], Iterable[str]]] = None,
                          pending: bool = False) -> Optional[str]:
    """寫碼查核（a～d）與收尾報告欄（e）合在一則訊息；兩部分要分開處理時用 reconcile_gate_parts。"""
    code, report = reconcile_gate_parts(last_text, receipts, turn_seq, turn_tool_names, own_mod_files, cfg, aec,
                                        aec_emitted, sid, phrases, measure_cmds, root, claims, self_covered, pending)
    return "\n".join(x for x in (code, report) if x) or None


def reconcile_gate_parts(last_text: str, receipts: List[Dict[str, Any]], turn_seq: int,
                         turn_tool_names: Iterable[str], own_mod_files: List[Dict[str, Any]],
                         cfg: Dict[str, Any], aec: Optional[Dict[str, Any]] = None,
                         aec_emitted: bool = False, sid: str = "",
                         phrases: Optional[Dict[str, Pattern]] = None,
                         measure_cmds: Iterable[str] = (), root: RootSpec = None,
                         claims: Iterable[str] = (),
                         self_covered: Optional[Callable[[], Iterable[str]]] = None,
                         pending: bool = False,
                         ) -> Tuple[Optional[str], Optional[str]]:
    """回 (寫碼查核擋訊息或 None, 收尾報告欄擋訊息或 None)。純判定、不改 state。
    pending＝已擋滿待放行：擋訊息不再建議「改成事實句」（換句話不會解帳），只列證據與放行問法；(d) 欠帳也一樣。
    寫碼查核：(a) 說修好而本 turn 無對得上改檔的合格 PASS、也沒有改檔所在部位的合格自寫收據（self_covered）；
    (b) 說量了而本 turn 沒有能當證據的 DONE（跑了部位量尺，或白名單語法且參數沒寫哨兵字樣）、也沒有改檔部位的合格自寫收據；
    (c) 說試過無執行工具。(a)(b)(c) 對「宣稱」對帳：last_text 與 claims（擋滿待放行時承接的先前宣稱，
    換一句話不能讓它消失）裡宣告完成的那幾段；pending 時 (b)(c) 只叫人補證據、不叫人改措辭；
    (d) 補案例的義務：本 session 最後一次改驗證案例（仍存在的程式檔）之後同根還改過程式檔（case_debt，跨回合；PASS 不代替），
    不看措辭，有改碼紀錄就判。
    收尾報告欄：(e) last_text 宣告完成且 AEC 已 emit：有收據而 j 缺／不存在、k 空字串（屬記憶與報告類，擋滿時不走放行詢問）。
    (a) 的「對得上」要同根（root 沒給＝每個改檔用 file_root_of 判根）且收據在它對上的每個改檔最後一次修改之後。"""
    texts = [t for t in (*claims, last_text) if t and claims_completion(t)]
    if not texts and not own_mod_files:
        return None, None
    this_turn = [r for r in receipts if int(r.get("turn_seq", -1)) == int(turn_seq)]
    mod_turn = modified_this_turn(own_mod_files, turn_seq)
    mod_records = {m["path"]: m for m in own_mod_files or [] if isinstance(m, dict) and m.get("path")}
    mod_session = list(mod_records)
    relate_paths = mod_turn or mod_session
    if root is None:
        roots = {p: file_root_of(p) for p in mod_session}
        root = roots.get
    root_of: Callable[[str], Optional[str]] = root if callable(root) else (lambda p, _r=root: _r)
    globs = cfg.get("verify_case_globs") or []
    measure_cmds = list(measure_cmds or [])
    related, unrelated = ([], []) if not texts else related_pass_receipts(
        this_turn, None, relate_paths, globs, measure_cmds, root, mod_records)
    _cov: List[bool] = []

    def covered() -> bool:
        """改檔所在部位有合格的自寫收據（量尺閘同一個條件；只讀一次）。"""
        if not _cov:
            _cov.append(bool(set(relate_paths) & set(self_covered() if self_covered else ())))
        return _cov[0]

    def note(verdict: str) -> str:
        n = _syntax_note(this_turn, verdict, measure_cmds)
        return f"（{n}）" if n else ""

    hits: List[str] = []
    if any(claims_fixed(t, phrases) for t in texts) and not related and not covered():
        hits.append(f"(a) 說「修好」但 {_pass_why(this_turn, receipts, unrelated, relate_paths)}。"
                    "修好的證據是本回合跑「驗那個改動」的驗證（cmd 提到改的檔／verify 路徑／量尺指令）印出 `<NAME>_CHECK PASS` 且 exit 0，"
                    "或改完之後才開始跑、全綠、同一棵樹的部位量尺自寫收據（背景全量）。" + note("PASS"))
    measured = any("DONE" in _verdicts(r) and (_clean(r) or any(_ruler_ran(mc, r) for mc in measure_cmds))
                   for r in this_turn)
    if any(claims_measured(t, phrases) for t in texts) and not measured and not covered():
        hits.append("(b) 說「量了」但本回合沒有 `<NAME> DONE k=v` 收據，也沒有改完之後跑的部位量尺自寫收據。"
                    + ("補跑量尺讓它印 DONE 尾行。" if pending else "量了就讓量尺腳本印 DONE 尾行，沒量就寫沒量。")
                    + note("DONE"))
    if any(tried_claim_without_exec(t, turn_tool_names, cfg.get("exec_tools") or [], this_turn, phrases) for t in texts):
        hits.append("(c) 說「試過／跑了」但本回合沒有任何 Bash／PowerShell 執行。"
                    + ("現在跑出收據。" if pending else "沒跑就寫沒跑，或現在跑。"))
    owed = case_debt(own_mod_files, turn_seq, cfg, root_of)
    if owed:
        names = "、".join(Path(p).name for p in owed[:4])
        hits.append(f"(d) 改了程式碼（{names}）之後沒有新增或修改驗證 case 檔（同根、仍存在的程式檔；義務跨回合，不看收尾措辭）："
                    "改了碼沒驗證 case（PASS 不能代替）。"
                    "補一個會紅的 case 再跑綠；真的不需要補案例，就照【收尾放行確認】問使用者。")
    # (e) 只檢本版報告（post_tool_use 一定寫入 j／k 兩鍵）；升級前 emit 的舊報告沒這兩鍵，不拿它擋
    report: List[str] = []
    if (claims_completion(last_text) and aec_emitted and isinstance(aec, dict)
            and "j_evidence_path" in aec and "k_followups" in aec):
        if aec_evidence_missing(aec.get("j_evidence_path"), bool(receipts)):
            report.append(f"(e) 收尾檢核 (j) 證據持久路徑缺或不存在，但本 session 有 {len(receipts)} 筆驗證收據。"
                          f"填帳本路徑（{ledger_path(sid or 'SID')}）或其他真存在的證據檔。")
        if aec_followups_missing(aec.get("k_followups")):
            report.append("(e) 收尾檢核 (k) 追蹤項是空字串。有就一行一項，沒有就寫「無」。")
    note = ""
    if any(r.get("exit_unknown") for r in related) or any(r.get("exit_unknown") for r in unrelated):
        note = "\n註：有 PASS 收據的 exit 未知（exit 未知＝dict 回應沒有 exit 欄），只憑哨兵認定。"
    tail = _RECONCILE_TAIL_EVIDENCE if pending or owed else _RECONCILE_TAIL
    code_reason = (_RECONCILE_HEAD + "\n".join("  ✗ " + h for h in hits) + tail + note) if hits else None
    report_reason = (_RECONCILE_HEAD + "\n".join("  ✗ " + h for h in report) + _RECONCILE_TAIL) if report else None
    return code_reason, report_reason


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
    """合併後設定（hub_config 四層：預設 < config.json overview_hub < 公司根 < 專案根 overview-hub.json，經 wg_overview._cfg）
    的 `verify_chains{part:{runtime_gate,pre,run,collect,cleanup}}`；沒有回 {}。
    設定有錯（與導讀卡端同一套驗證）→ 拋 ValueError：量尺閘的判定錯誤一律擋（stop._verify_gates），不當作沒設。"""
    from wg_core import load_config
    from wg_overview import _cfg
    c = _cfg(load_config(), Path(root))
    if c["_errors"]:
        raise ValueError(f"overview-hub 設定錯誤（{root}）：" + "；".join(c["_errors"][:3]))
    vc = c.get("verify_chains")
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


ROOT_WT_SENTINEL = "PYTEST_MEASURE"      # 根層 worktree 認的尺：pytest 摘要行映射的 DONE 哨兵（config verify_ledger.sentinel_regex）


def is_root_worktree(root: Path, claude_dir: Path) -> bool:
    """root 是「根層（~/.claude）的 worktree」；判定本體在 lib/overview_hub.is_root_worktree（卡片目錄解析共用）。
    委派失敗（載到沒有這支的舊版 overview_hub 等）→ stderr 說一聲並回 False：量尺照根層規則要全量，閘保持擋。"""
    lib_dir = str(Path(__file__).resolve().parents[1] / "lib")
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)
    try:
        from overview_hub import is_root_worktree as _impl
        return bool(_impl(root, claude_dir))
    except Exception as e:  # noqa: BLE001
        msg = " ".join(str(e).split())   # 多行例外壓成一行
        print(f"[verify_ledger] is_root_worktree 委派失敗：{type(e).__name__}: {msg}；當成非 worktree（量尺照根層規則要全量）",
              file=sys.stderr)
        return False


def load_self_runs() -> List[Dict[str, Any]]:
    """run_verify 自寫的驗證收據（<CLAUDE_DIR>/workflow/verify-ledger/_runs/，格式在 lib/self_receipt.py；讀不動會浮 stderr）。"""
    return _self_receipt.load_self_receipts(CLAUDE_DIR)


def self_run_ok(runs: Iterable[Dict[str, Any]], cmd: str, root: str, edit_at: str, edit_turn: int) -> bool:
    """有一份自寫收據同時符合：argv 跑了該部位量尺（cmd_matches；argv 不經 shell 解析，沒有 argv 的舊收據才讀 cmd）；
    exit 0 且 failed 0；started_at 晚於該部位最後一次修改；收據根（受測樹 project_root）與部位根同一棵樹（_root_ok）。
    不綁 session：改完之後任何人對同一棵樹跑完的全量都算。"""
    # 防線邊界：hook 擋得住 AI 直接手寫收據（PreToolUse 對 verify-ledger/ 的 Edit／Write／重導向／PowerShell 寫檔別名一律 deny）、
    # 靠措辭避開查核（補案例義務與量尺每次 Stop 都判）、把目標不明的寫入當成沒寫（未知寫入欠帳）、舊收據或別棵樹的收據冒充
    # （started_at 要晚於最後一次修改、project_root 要同一棵樹）。擋不住 AI 刻意寫一支程式去產生假收據：AI 能執行任意程式，
    # 它讀得到的任何識別都能複製，這一層不是程式能保證的，不再為它加機制。
    # 量尺比對只認白名單語法；解析不了的指令一律不算證據（fail-closed），所以不必逐一追 shell 技巧；在白名單語法內印假哨兵的
    # 組合（引號、echo、短路、截斷）都已封住。
    for r in runs or []:
        argv = r.get("argv") if isinstance(r, dict) else None
        if not isinstance(r, dict) or not cmd.strip() or not cmd_matches(
                cmd, argv if isinstance(argv, list) and argv else str(r.get("cmd", "")),
                root=str(r.get("project_root") or ""), measure_root=str(root or "")):
            continue
        if r.get("exit_code") != 0 or str(r.get("failed")) != "0":
            continue
        if not _receipt_after({"at": r.get("started_at") or ""}, edit_at or None, None, edit_turn):
            continue
        if _root_ok(r, root):
            return True
    return False


def measure_parts(own_mod_files: List[Dict[str, Any]],
                  lookup: Callable[[str], Optional[Tuple[Path, Dict[str, Any]]]]) -> Dict[str, Dict[str, Any]]:
    """改檔依部位歸組：{根|部位: {root, row, edit_turn, edit_at, edit_seq, files}}，edit_* 是該部位最後一次修改。
    量尺閘與對帳閘 (a) 認自寫收據都用它（兩邊的「部位最後一次修改」同一個算法）。"""
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
    return parts


def self_run_covered(parts: Dict[str, Dict[str, Any]], runs: Iterable[Dict[str, Any]]) -> List[str]:
    """有合格自寫收據（self_run_ok：跑了該部位的量尺、改完之後才開始、全綠、同一棵樹）的部位，回它們的改檔。
    對帳閘 (a)「說修好」也認這份（背景全量的收據不能只接到量尺閘）。"""
    runs = list(runs or [])
    out: List[str] = []
    for rec in parts.values():
        cmd = str(((rec["row"].get("measure") or {}).get("cmd")) or "").strip()
        if cmd and self_run_ok(runs, cmd, str(rec["root"]), rec["edit_at"], rec["edit_turn"]):
            out.extend(rec["files"])
    return out


def measure_gate_reason(own_mod_files: List[Dict[str, Any]], receipts: List[Dict[str, Any]], turn_seq: int,
                        lookup: Callable[[str], Optional[Tuple[Path, Dict[str, Any]]]], cfg: Dict[str, Any],
                        chains_of: Callable[[Path], Dict[str, Dict[str, str]]] = load_verify_chains,
                        runner: Callable[[str, float, Optional[str]], Tuple[bool, str]] = run_runtime_gate,
                        self_runs: Optional[Callable[[], List[Dict[str, Any]]]] = None,
                        ) -> Tuple[Optional[str], List[str]]:
    """改到的部位有量尺 → 先 runtime_gate（量不了就擋並說原因）→ 找「該部位最後一次修改之後」（比 at，沒有比序號，再沒有比 turn）、
    同 root、exit 0／None 且 failed=0 的 DONE 且 cmd 跑了量尺指令，沒有→擋。回 (擋訊息或 None, 沒量尺的部位名清單＝提醒補)。
    不看收尾措辭：改到有量尺的部位，每次 Stop 都判（stop._verify_gates）。
    小修也要重跑尺：同 turn 再改一行，之前的 DONE 就在修改之前、不算；尺太重的部位把量尺改成子集指令（表上那格）。
    根層 worktree（is_root_worktree(root, CLAUDE_DIR)）：工作 session 不跑全量，該部位的尺改認「同 root 下、修改之後、
    exit 0 且 failed=0 的 pytest DONE 收據（哨兵 PYTEST_MEASURE）」；live 根層（root == CLAUDE_DIR）與非根層專案行為不變。
    非根層 worktree 的部位除了 session 帳本，也認 run_verify 自寫收據（self_run_ok；長跑的尺只能背景跑，帳本看不到結尾哨兵）。"""
    parts = measure_parts(own_mod_files, lookup)
    _runs: List[List[Dict[str, Any]]] = []          # 自寫收據只在需要時讀一次
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
        root_wt = is_root_worktree(root, CLAUDE_DIR)
        bad_ruler = None if root_wt else unsupported_syntax(cmd)
        if bad_ruler:             # 表上的尺本身就解析不了：任何收據都對不上，要改的是表
            blocks.append(f"部位【{part}】表上的量尺 `{cmd}` 含解析不了的語法（{bad_ruler}），任何收據都對不上；"
                          "把 .claude/overview-map.md 這格改成白名單語法（單一指令或 && 串接、引號、重導向），"
                          "改不了就照【收尾放行確認】問使用者。")
            continue
        pick = {"sentinel_name": ROOT_WT_SENTINEL, "final_prog": "pytest"} if root_wt else {"cmd_contains": cmd}
        ok_done = done_receipts(receipts, min_turn=rec["edit_turn"], min_at=rec["edit_at"] or None,
                                min_seq=rec["edit_seq"], root=str(root), **pick)
        if not root_wt:           # 量尺也只涵蓋執行根之下的改檔：`cd 部位根/tests && 量尺` 不替部位根其他改檔解帳
            ok_done = [r for r in ok_done if all(_in_exec_root(r, p) for p in rec["files"])]
        if ok_done:
            continue
        if not root_wt:
            if not _runs:
                _runs.append((self_runs or load_self_runs)() or [])
            if self_run_ok(_runs[0], cmd, str(root), rec["edit_at"], rec["edit_turn"]):
                continue
        # 已有合格收據的部位不探環境（上面 continue 掉了）；還欠收據才跑 runtime_gate，量不了就說環境原因
        chain = (chains_of(root) or {}).get(part) or {}
        gate = str(chain.get("runtime_gate") or "").strip()
        if gate:
            ok, why = runner(gate, timeout, str(root))
            if not ok:
                blocks.append(f"部位【{part}】有量尺（{measure.get('method') or cmd}）但執行環境未就緒：{why}。"
                              f"讓環境就緒後跑 `{cmd}`；現在量不了，就照【收尾放行確認】問使用者（題目寫明量不了的原因）。")
                continue
        ruler = (f"根層 worktree：認目標 verify 的 pytest DONE，不要求全量（{root} 下、exit 0、failed=0、"
                 f"哨兵 {ROOT_WT_SENTINEL}，表上的尺 `{cmd}` 不是這裡的門檻）")
        rerun = (f"在 worktree 根 `{root}` 直接跑目標 verify `python -X utf8 -m pytest -q <hooks/verify/...>`"
                 f"（不含 cd；尾行 `N passed` 會映射成 {ROOT_WT_SENTINEL} DONE）")
        any_done = done_receipts(receipts, require_ok=False, **pick)
        if any_done:
            last = any_done[-1]
            failed = next(((s.get("kv") or {}).get("failed") for s in last.get("sentinels") or []
                           if isinstance(s, dict) and (s.get("kv") or {}).get("failed") is not None), None)
            if _trusted(last) is None:
                why = "最近一次跑尺的指令含 cd（只有開頭 `cd <絕對路徑> &&` 認得出根），無法確認量測目標；請在專案根直接跑尺"
            elif last.get("exit_code") not in (None, 0) or (failed is not None and str(failed) != "0"):
                why = f"最近一次跑尺 exit={last.get('exit_code')} failed={failed}，尺沒過"
            elif not _root_match(last, str(root)):
                why = f"最近一次跑尺的 cwd／project_root（{last.get('project_root') or last.get('cwd')}）不是這個部位的 root"
            elif not root_wt and not all(_in_exec_root(last, p) for p in rec["files"]):
                why = (f"最近一次跑尺的執行根是 {_cwd_of(last)}，只涵蓋那之下的改檔"
                       f"（{next(p for p in rec['files'] if not _in_exec_root(last, p))} 不在裡面）；請在部位根 {root} 跑尺")
            else:
                why = "最近一次跑尺在這個部位最後一次修改之前（先量後改不算）"
            if root_wt:
                blocks.append(f"部位【{part}】有量尺{ruler}，{why}。改完再跑一次 {rerun} 再收尾。")
            else:
                blocks.append(f"部位【{part}】有量尺「{measure.get('method') or ''}｜`{cmd}`｜{measure.get('threshold') or ''}」，{why}。"
                              f"改完再跑一次 `{cmd}`（尾行 `<NAME> DONE` 或 `<NAME>_CHECK DONE`，exit 0、failed=0）再收尾。")
        elif root_wt:
            blocks.append(f"部位【{part}】有量尺{ruler}，"
                          f"改了 {len(rec['files'])} 個檔（最後在 turn {rec['edit_turn']}）但之後沒有這把尺的 DONE 收據。"
                          f"跑 {rerun} 再收尾。")
        else:
            blocks.append(f"部位【{part}】有量尺「{measure.get('method') or ''}｜`{cmd}`｜{measure.get('threshold') or ''}」，"
                          f"改了 {len(rec['files'])} 個檔（最後在 turn {rec['edit_turn']}）但之後沒有這把尺的 DONE 收據。"
                          f"跑 `{cmd}`（尾行要印 `<NAME> DONE` 或 `<NAME>_CHECK DONE`）再收尾。")
    reason = None
    if blocks:
        reason = ("[Guardian:MeasureGate] 改到有量尺的部位，收尾前要跑過那把尺：\n" + "\n".join("  ✗ " + b for b in blocks)
                  + "\n  要補的證據就是上面那把尺的收據；跑不了就照【收尾放行確認】問使用者，改寫收尾文字不會解帳。")
        if any("run_verify.py" in str((r["row"].get("measure") or {}).get("cmd") or "") for r in parts.values()):
            reason += ("\n  run_verify 跑超過 10 分鐘就背景跑：它跑完會自寫收據到 workflow/verify-ledger/_runs/，"
                       "改完之後才開始跑、exit 0、failed=0、同一棵樹就認得到（收據不准手寫）。")
        note = _syntax_note(receipts, "DONE", [str((r["row"].get("measure") or {}).get("cmd") or "") for r in parts.values()])
        if note:
            reason += "\n  " + note
    return reason, no_measure


def measure_advisory(parts_without: Iterable[str]) -> Optional[str]:
    names = sorted({p for p in parts_without if p})
    if not names:
        return None
    return ("[Guardian:MeasureGate] 改到的部位沒有量尺欄：" + "、".join(names)
            + "。在 .claude/overview-map.md 的「量尺（量法｜指令｜門檻）」欄補一把尺，收尾才有東西可對。")

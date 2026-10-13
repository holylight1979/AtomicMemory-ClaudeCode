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
  收據的 env 欄＝PostToolUse 落帳時 hook 行程看到的縮限變數（PYTEST_ADDOPTS、PYTHONOPTIMIZE；lib/self_receipt.env_snapshot），
  採認時與指令內的指定合併成每段程式的有效環境（父行程已設 `PYTEST_ADDOPTS=-k smoke` 時原樣跑的 pytest 只跑子集，不算；
  指令內 `PYTEST_ADDOPTS='' …` 清掉才算）；沒記 env 欄的舊收據照自寫收據的規則不算證據。

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

from wg_core import CLAUDE_DIR, WORKFLOW_DIR, find_vcs_root, find_vcs_root_ex, resolve_project_root
from wg_release_rules import (canon_path, claim_is_modifier, excluded_region, gone_verdict, in_turn,
                              owed_after_last_case, user_turn, Verdict,
                              format_hit, green_after_edit_verdict, cmd_names_file, comment_only_change, comment_only_verdict,
                              committed_refs, content_equals_committed, is_temp_path, temp_roots, norm_temp_path, vcs_unreadable_verdict)
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
env_snapshot = _self_receipt.env_snapshot          # PostToolUse 落帳時記的啟動環境（與 run_verify 自寫收據同一個函式）

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


# 歷來內建的兩條 pytest 規則用過的 regex（config 還沒有 pytest_summary 旗標的舊版本）：使用者保留舊全域 config、只更新 hooks 時，
# load_config 只做頂層合併，補不到這個旗標；照這張表認出內建規則，照樣按統計逐組解析
_BUILTIN_PYTEST_REGEXES = frozenset({
    r"^(?:=+ )?(?P<verdict>\d+ (?:passed|failed))",
    r"^(?:=+ )?(?P<verdict>\d+ (?:passed|failed|errors?)(?:, \d+ [a-z]+)*) in \d",
    r"^(?:=+ )?(?P<verdict>\d+ (?:passed|failed|errors?|skipped|xfailed|xpassed|warnings?|deselected|rerun)(?:, \d+ [a-z]+)*) in \d",
})
_BUILTIN_PYTEST_OK = {"PYTEST": "PASS", "PYTEST_MEASURE": "DONE"}       # 內建規則名 → 成功時的結論


def _builtin_pytest_rule(r: Dict[str, Any]) -> bool:
    """沒寫 pytest_summary 的規則是不是歷來內建的 PYTEST／PYTEST_MEASURE：名稱、regex、verdict_map 三樣都要對上（只同名的自訂規則不算）。"""
    ok = _BUILTIN_PYTEST_OK.get(str(r.get("name") or "").strip())
    vm = r.get("verdict_map")
    if not ok or r.get("regex") not in _BUILTIN_PYTEST_REGEXES or not isinstance(vm, dict):
        return False
    items = {(str(k), str(v).upper()) for k, v in vm.items()}
    return ("passed", ok) in items and items <= {("failed", "FAIL"), ("error", "FAIL"), ("passed", ok), ("xpassed", ok)}


def compile_sentinel_rules(cfg_rules: Any) -> List[Dict[str, Any]]:
    """config `verify_ledger.sentinel_regex: [{regex, name, verdict_map, pytest_summary?}]` → 已編譯規則；壞 regex 跳過（stderr 浮一行）。
    pytest_summary＝true 的規則按 pytest 統計逐組解析（_map_verdict），其餘照子字串映射；沒寫這個鍵的規則，是歷來內建的兩條
    pytest 規則（_builtin_pytest_rule）就當 true，明寫的值優先。"""
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
            "pytest_summary": r["pytest_summary"] is True if "pytest_summary" in r else _builtin_pytest_rule(r),
        })
    return out


_STAT_RE = re.compile(r"\b(\d+) ([a-z]+)\b")          # 統計行的「數字 狀態詞」組：5 passed, 2 skipped, 1 xfailed


def _map_verdict(raw: str, verdict_map: Dict[str, str], pytest_summary: bool = False) -> Optional[str]:
    """命中的那段文字 → verdict_map 的結論。pytest_summary（config 規則標了 `pytest_summary: true`，只有內建的 PYTEST／
    PYTEST_MEASURE 兩條）：按「數字 狀態詞」組逐組比，鍵要等於整個狀態詞（去尾 s：error 對 errors），`xfailed`／`xpassed`
    不是 `failed`／`passed`，只有計數非零的狀態詞算命中。其他規則（自訂哨兵）照子字串比，`CUSTOM_FAIL 1 item` 的 `1 item`
    不是統計。兩種都是命中多個鍵時 FAIL 優先（`1 passed, 1 error` 是 FAIL），其餘照 verdict_map 順序取第一個；兩條共用同一
    regex 的 pytest 規則因此對同一行一定得到同一種結果。"""
    low = raw.lower()
    stats = [(int(n), w.rstrip("s")) for n, w in _STAT_RE.findall(low)] if pytest_summary else []
    hits: List[str] = []
    for key, v in verdict_map.items():
        k = key.lower()
        if v not in VERDICTS:
            continue
        if pytest_summary:
            if not any(n > 0 and w == k.rstrip("s") for n, w in stats):
                continue
        elif k not in low:
            continue
        hits.append(v)
    if "FAIL" in hits:
        return "FAIL"
    if hits:
        return hits[0]
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
            verdict = _map_verdict(raw, rule["verdict_map"], rule.get("pytest_summary", False))
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
    都查 deadline；檔數上限 200；任一處超過 → 該筆 truncated=True 並停止。rev 取不到（子行程逾時、失敗、空字串）→ 該筆
    truncated=True、照樣算 dirty。每個 truncated=True 的筆都有 why 說原因（哪一步耗盡預算、或取不到 rev）。
    rev 每 root 60 s 快取在 state["vcs_rev_cache"]；非 VCS 回 []。"""
    deadline = _clock() + budget_s
    paths = [p for p in paths if p][:SNAPSHOT_MAX_FILES + 1]
    roots: List[Tuple[str, Path]] = []
    out: List[Dict[str, Any]] = []
    for i, start in enumerate([cwd, *paths]):
        if not start:
            continue
        if i and i % SNAPSHOT_STAT_CHECK_EVERY == 0 and _clock() > deadline:
            out.append({"kind": "", "root": "", "rev": "", "dirty": "", "truncated": True, "why": "找 VCS 根時已耗盡預算"})
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
            entry["why"] = "還沒取 rev 就已耗盡預算"
            out.append(entry)
            break
        cached = cache.get(key) if isinstance(cache.get(key), dict) else None
        now_wall = time.time()
        if cached and now_wall - float(cached.get("at", 0)) < rev_cache_s and cached.get("rev"):
            entry["rev"] = cached["rev"]
        else:
            limit = min(subprocess_s, remaining)
            entry["rev"] = _rev(kind, root, limit)
            if entry["rev"]:
                cache[key] = {"rev": entry["rev"], "at": now_wall}
            else:                 # 子行程逾時、失敗或回空字串：結果不完整要說出來，不能讓空 rev 看起來像正常結果
                entry["truncated"] = True
                entry["why"] = f"取不到 {kind} rev（子行程上限 {limit:.2f} 秒內逾時、失敗或回空字串）"
            if _clock() > deadline:
                entry["truncated"] = True
                entry.setdefault("why", "取完 rev 已耗盡預算，改檔雜湊沒算")
                out.append(entry)
                break
        entry["dirty"], trunc = dirty_hash(root, paths, deadline, _clock, _stat)
        if trunc:
            entry.setdefault("why", "算改檔雜湊時已耗盡預算或超過檔數上限")
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
    """本回合的收據（規則 TURN_SINCE_USER_PROMPT：使用者打字開的回合起，同伴訊息、背景通知不另開回合）。"""
    since = user_turn(state, turn_seq)
    return [r for r in receipts_of(state, sid) if in_turn(r.get("turn_seq", -1), turn_seq, since)]


def spec_paths_of(sid: str, base_dir: Optional[Path] = None) -> List[str]:
    """驗收規格（hooks/acceptance_spec.py sidecar）本 session 登記的規格檔路徑；沒有回 []。"""
    try:
        p = (base_dir or WORKFLOW_DIR) / "acceptance-spec" / f"{sid}.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        return [str(x) for x in (data.get("spec_paths") or [])]
    except (OSError, ValueError):
        return []


def modified_this_turn(own_mod_files: Iterable[Dict[str, Any]], turn_seq: int, since: Optional[int] = None) -> List[str]:
    """本回合動過的檔（last_turn_seq 落在本回合，見 in_turn）。升級前 in-flight session 的 legacy entry 沒有 turn 欄＝不知道
    哪回合改的，不算本回合（對帳 (d) 不拿它擋人；下一次 Edit 就會補上 turn 欄）。"""
    out: List[str] = []
    for m in own_mod_files or []:
        if not isinstance(m, dict) or not m.get("path"):
            continue
        t = m.get("last_turn_seq", m.get("turn_seq"))
        if t is not None and in_turn(t, turn_seq, since) and m["path"] not in out:
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
    不是第三方轉述（第三方名詞在子句開頭且宣稱詞前沒有我／本／已）；引號／code span 內容先剝掉（引用閘文字不算宣稱）；
    宣稱詞後面直接接「的＋名詞」（修好的 X）是形容詞用法，不算（規則 CLAIM_MODIFIER_NOT_OWN），同子句後面另有宣稱照算。"""
    if not text:
        return False
    ph = phrases or CLAIM_RES
    pos, neg = ph[kind], ph[f"{kind}_exclude"]
    for clause in _CLAUSE_SPLIT_RE.split(strip_quoted_spans(text[-3000:])):
        clause = clause.strip()
        if neg.search(clause):
            continue
        for m in pos.finditer(clause):
            if claim_is_modifier(clause, m.end()) or _third_party_said(clause[:m.start()]):
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


def _env_of(receipt: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """收據記下的啟動環境（PostToolUse 落帳時 hook 行程的 env_snapshot：PYTEST_ADDOPTS、PYTHONOPTIMIZE 這幾個會縮小驗證範圍的變數，
    空值也記）；升級前沒記 env 欄的收據回 None＝看不出父行程有沒有把範圍縮小，照自寫收據的規則（025 規則 2）不算證據。"""
    env = receipt.get("env")
    return env if isinstance(env, dict) else None


def _usable(receipt: Dict[str, Any]) -> bool:
    """收據能拿來當任何證據的前提：指令完整（_cmd_complete）而且記了啟動環境（_env_of）。"""
    return _cmd_complete(receipt) and _env_of(receipt) is not None


def _trusted(receipt: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """收據的指令完整、記了啟動環境、根可信才回（開頭單一絕對路徑的 `cd <路徑> && …`：執行根 cwd 換成該路徑；路徑在原專案根之內就保留
    原專案根當樹根，否則樹根也換成它）；不完整、沒記 env 或含其他 cd → None。
    可解析的指令只看同一套斷詞判換目錄（`c"d" C:/live; 量尺` 的 c"d" 是 cd；`量尺 # cd x` 的 cd 在註解裡不是）；
    解析不了的才退回原字串比對 has_cd 與 PostToolUse 記的 root_uncertain（那種收據本來也當不了證據）。"""
    raw, sh = str(receipt.get("cmd") or ""), _shell_of(receipt)
    if not _usable(receipt):
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
            src, flags = rule["re"].pattern, rule["re"].flags
            pat = _drop_anchors(src, bool(flags & re.VERBOSE))
            compiled = None
            if pat is not None:
                try:
                    compiled = re.compile(pat, flags | re.MULTILINE)
                except re.error:
                    compiled = None
            if compiled is None:                                  # 處理不了就拒用、說出來，不默默漏查
                print(f"[verify-ledger] config 哨兵 regex {src!r}（{rule.get('name') or '?'}）無法用來掃指令"
                      "（只對某一段開關 verbose 的 (?x:…)、沒閉合的 (?#…) 註解、或拿掉錨點後編譯不了）：指令裡寫了這種哨兵字樣"
                      "查不到；請改寫成不帶 verbose 註解的形式", file=sys.stderr)
                continue
            _arg_res.append(compiled)
    return _arg_res


_SCOPED_FLAGS_RE = re.compile(r"\(\?([aiLmsux]*)(?:-([imsx]*))?:")


def _drop_anchors(pat: str, verbose: bool = False) -> Optional[str]:
    """regex 裡所有錨點（字元類 [...] 以外、沒跳脫的 ^ $，以及 \\A \\Z \\z）拿掉，在旗標後、群組裡的也拿：
    `(?i)^X_OK$`、`^(?:X_OK$)` 都變成只找 X_OK 這串字。註解先拿掉：`(?#…)` 一律是註解；verbose（`(?x)` 或編譯旗標，由
    verbose 傳入）時字元類以外、沒跳脫的 `#` 到行尾是註解（註解裡的 `[`、`^` 不能當成字元類或錨點）；`(?#…)` 到第一個沒跳脫的 `)`。
    只對某一段開關 verbose 的 `(?x:…)`／`(?-x:…)` 判不出哪段的 `#` 是註解，`(?#` 沒閉合 → None（呼叫端拒用並說明）；
    註解與字元類裡的 `(?x:` 字樣不是旗標群組。字元類 `[` 或 `[^` 後面緊接的 `]` 是字面字元，之後的 `]` 才關閉（`[a[]` 是 a 或 [）。"""
    out: List[str] = []
    i, class_at = 0, -1                                           # class_at：字元類內容從 out 的第幾格開始（-1＝不在字元類裡）
    while i < len(pat):
        c = pat[i]
        if c == "\\" and i + 1 < len(pat):
            if class_at >= 0 or pat[i + 1] not in "AZz":
                out.append(pat[i:i + 2])
            i += 2
            continue
        if class_at >= 0:
            if c == "]" and len(out) > class_at:
                class_at = -1
            out.append(c)
        elif pat.startswith("(?#", i):            # 註解到第一個沒跳脫的 )：Python 的斷詞把 `\)` 當一個字元
            j = i + 3
            while j < len(pat) and pat[j] != ")":
                j += 2 if pat[j] == "\\" else 1
            if j >= len(pat):
                return None
            i = j + 1
            continue
        elif verbose and c == "#":
            j = pat.find("\n", i)
            i = len(pat) if j < 0 else j
            continue
        elif c == "(" and (m := _SCOPED_FLAGS_RE.match(pat, i)) and "x" in m.group(1) + (m.group(2) or ""):
            return None
        elif c == "[":
            neg = pat[i + 1:i + 2] == "^"
            out.append("[^" if neg else "[")
            class_at = len(out)
            i += 1 if neg else 0
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


def _in_tree(receipt: Dict[str, Any]) -> bool:
    """跑程式的指令沒有指到收據根以外（`python ../live/run_verify.py`、`python C:\\…\\.claude\\run_verify.py`、`../live/verify.sh`、
    `pytest C:/live/tests` 量的都是別棵樹；相對路徑照 cwd 解析）。收據沒根資訊 → 不比（同 _root_ok）。"""
    root = str(receipt.get("project_root") or receipt.get("cwd") or "")
    return not _self_receipt.outside_paths(str(receipt.get("cmd") or ""), _shell_of(receipt), root, _cwd_of(receipt))


def _clean(receipt: Dict[str, Any]) -> bool:
    """收據的指令能當一般證據（對帳 (a) 提到改檔、(b) 量了、根層 worktree 的 pytest DONE）：完整、記了啟動環境、白名單語法、
    是 evidence_steps 的形狀（cd／環境設定之後全是跑程式的指令、只用 && 串、stdout 沒導走、後面只准留結尾的過濾；每一段啟動時
    繼承環境＋指令內指定的有效環境沒有縮限設定）、沒指到收據根以外、指令裡沒寫哨兵字樣。"""
    raw, sh = str(receipt.get("cmd") or ""), _shell_of(receipt)
    return (_usable(receipt) and not unsupported_syntax(raw, sh)
            and _self_receipt.evidence_steps(raw, sh, _env_of(receipt)) is not None
            and _in_tree(receipt) and not _prints_sentinel(raw, sh))


def _ruler_ran(measure_cmd: str, receipt: Dict[str, Any], part_root: str = "") -> bool:
    """收據跑了表上這把尺（match_span，依收據的 shell 解析；腳本照路徑認：收據照它的 cwd、量尺照部位根 part_root，
    沒給部位根就共用收據的；有效環境從收據記下的繼承環境起算）；指令要完整、記了啟動環境、沒指到收據根以外，而且量尺片段以外
    沒有任何字寫了哨兵字樣。"""
    raw, sh = str(receipt.get("cmd") or ""), _shell_of(receipt)
    if not str(measure_cmd).strip() or not _usable(receipt):
        return False
    span = _self_receipt.match_span(str(measure_cmd), raw, sh, _cwd_of(receipt), str(part_root or ""), _env_of(receipt))
    return span is not None and not _prints_sentinel(raw, sh, span, str(measure_cmd)) and _in_tree(receipt)


_RULER_FORM = ("量尺前面只准 `cd <絕對路徑> &&` 與環境設定（`X=1`、`export X=1`、`$env:X=\"1\";`、`$x = '字面值';`；"
               "set、unset、pushd、帶 $ 的值、PS4 這類讓 shell 自己印字的變數都不算），"
               "後面只准 `| tail` 或 `| Select-Object -Last N`；請照表上原字串單獨跑。")


_TOOL_HINT = ("專案自製的測試工具請寫進部位表的量尺欄，寫 PATH 上的程式名（例：`Unity.exe -batchmode -runTests …`）並把那支程式"
              "加進 PATH；樹外完整路徑的程式不算（量的不是這棵樹）。量尺逐字比對、不經執行程式白名單，對上就涵蓋整個部位的改檔。")


def _scope_env_why(diffs: List[Tuple[str, str, str]], env: Optional[Dict[str, Any]] = None) -> str:
    """環境設定改了驗證範圍的說明（session 收據與自寫收據的擋訊息共用）。diffs＝[(名稱, 這次的值, 表上的值)]，
    表上的值空＝這次多設了；表上有值＝這次少了或值不同。env＝收據記下的繼承環境：多設的變數若是從父行程繼承來的（指令內沒寫），
    就說清楚是繼承的、要在指令內清空。"""
    inherited = {str(k).upper() for k, v in (env or {}).items() if str(v if v is not None else "") != ""}
    extra = [n for n, _, want in diffs if not want]
    differ = [f"{n}（表上是 {want!r}）" for n, _, want in diffs if want]
    from_parent = [n for n in extra if n.upper() in inherited]
    parts = ([f"用環境設定 {'、'.join(extra)} 改了驗證選項（PYTEST_ADDOPTS 會替 pytest 加 -k、路徑這類選項把範圍縮成子集，"
              "PYTHONOPTIMIZE 等於 -O）"] if extra else []) + ([f"環境設定 {'、'.join(differ)} 跟表上量尺不同"] if differ else [])
    if from_parent:
        parts.append(f"{'、'.join(from_parent)} 是從啟動 Claude Code 的父行程繼承來的（指令內沒寫也在）")
    fix = "拿掉多加的設定（要清空就設成空值），" if extra else ""
    if from_parent:
        fix = f"在指令內清空繼承值（bash `{from_parent[0]}='' …`、PowerShell `$env:{from_parent[0]}=''; …`），"
    return "；".join(parts) + f"，跑的不是表上那組選項，也不算整體驗證；{fix}照表上原字串在沒有其他這類設定的環境跑。"


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
        env = _env_of(r)
        if env is None:
            return (f"最近那筆收據 {head} 沒記啟動環境（升級前落的帳），看不出父行程有沒有用 PYTEST_ADDOPTS 這類設定把驗證範圍"
                    "縮小，不算證據；請重跑。")
        why = unsupported_syntax(raw, sh)
        if why:
            return f"這條指令 {head} 含解析不了的語法（{why}），不算跑了量尺；請照表上原字串單獨跑。"
        if any(_ruler_ran(mc, r) for mc in rulers):
            return ""
        for mc in rulers:         # 結構上就是量尺、只差環境，而且量尺自己的字以外沒寫哨兵：講真正原因
            mis = _self_receipt.ruler_env_mismatch(mc, raw, sh, _cwd_of(r), env=env)
            if mis and not _prints_sentinel(raw, sh, mis[0], mc):
                return f"這條指令 {head} {_scope_env_why(mis[1], env)}"
        if _prints_sentinel(raw, sh):
            return (f"這條指令 {head} 的參數裡寫了哨兵字樣（echo／printf／Write-Output 印出來的），不算任何證據；"
                    "哨兵只能由被執行的程式印出。")
        envs = _self_receipt.program_scope_env(raw, sh, env)
        if envs:                  # 整體驗證、一般證據：任何一段跑程式的指令啟動時帶了縮限設定（含父行程繼承的）
            return f"這條指令 {head} {_scope_env_why([(n, '', '') for n in envs], env)}"
        outside = [] if _in_tree(r) else _self_receipt.outside_paths(
            raw, sh, str(r.get("project_root") or r.get("cwd") or ""), _cwd_of(r))
        if outside and any(_self_receipt.match_span(mc, raw, sh, _cwd_of(r), env=env) is not None for mc in rulers):
            return (f"這條指令 {head} 對上了表上的量尺，但指到收據根以外的路徑（{'、'.join(outside[:3])}），量的不是這棵樹，不算；"
                    f"{_TOOL_HINT}")       # 精確對上卻因樹外被拒：講樹外，不說「前後接了別的指令」
        if any(_self_receipt.ruler_in(mc, raw, sh, _cwd_of(r)) for mc in rulers):
            return f"這條指令 {head} 裡有量尺，但前後接了別的指令。{_RULER_FORM}"
        others = _self_receipt.non_runners(raw, sh)
        if others:                # 先講這個：樹外的自製工具（Unity.exe）否則會先被說成「指到收據根以外」
            return (f"這條指令 {head} 夾了不算執行程式的指令（{'、'.join(others[:3])}：讀檔或印字的指令、或不在執行程式白名單的程式），"
                    f"印出來的哨兵分不出是誰印的，不算證據；{_TOOL_HINT}")
        if outside:
            return (f"這條指令 {head} 指到收據根以外的路徑（{'、'.join(outside[:3])}），量的不是這棵樹；"
                    "請在專案根照表上原字串跑。")
        if _self_receipt.evidence_steps(raw, sh) is None:
            return (f"這條指令 {head} 不是單純跑驗證程式的形狀（夾了讀檔或印字的指令、用 ; 或 || 串、或把輸出導走），"
                    "印出來的哨兵分不出是誰印的、哪一段真的過了，不算證據；請單獨跑驗證程式（前面只准 cd 與環境設定、多段只用 && 串）。")
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
    return " ".join(_norm_path(" ".join(evidence_words(str(r.get("cmd") or ""), _shell_of(r)))).split())


def _ruler_any(receipt: Dict[str, Any], measure_cmds: Iterable[str]) -> bool:
    """收據跑了其中一把部位量尺（_ruler_ran）：聲稱驗到該部位全部改檔。"""
    return any(_ruler_ran(mc, receipt) for mc in measure_cmds or [])


def _whole_run(receipt: Dict[str, Any]) -> bool:
    """整體驗證：執行根自己的 run_verify.py（照完整路徑身分）或不縮範圍的 pytest；只認白名單語法、前面只准前置設定、
    後面只准尾端過濾、沒指到收據根以外、整條指令沒寫哨兵字樣。涵蓋範圍見 _in_exec_root。"""
    raw, sh = str(receipt.get("cmd") or ""), _shell_of(receipt)
    return (_usable(receipt) and is_whole_run(raw, sh, _cwd_of(receipt), _env_of(receipt)) and _in_tree(receipt)
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
        if _temp_receipt(r):
            continue          # TEMP_COPY_NOT_PROJECT：暫存目錄裡跑的不當收據
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
        if "DONE" not in _verdicts(r) or _temp_receipt(r):
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
            runs = _self_receipt.evidence_steps(str(r.get("cmd") or ""), _shell_of(r)) or []
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
    "exclude_globs": ["workflow/v6-inbox/**", "memory/_staging/**", "_AIDocs/**"],
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


def is_excluded(path: str, cfg: Dict[str, Any], root: Optional[str]) -> bool:
    """規則 EXCLUDED_REGION（wg_release_rules.excluded_region）：path 落在 exclude_globs（相對專案根比，先消掉 `..`）。
    信箱、規劃暫存、文件目錄下的 .py 是素材，不是本專案的程式也不是它的案例。拿不到根或不在根底下 → 不排除（照算）。"""
    return excluded_region(path, cfg.get("exclude_globs") or [], root)


def case_exists(path: str) -> bool:
    """案例檔在 Stop 當下還在嗎（刪掉的案例不算補了案例）。"""
    return os.path.isfile(path)


def code_exists(path: str) -> bool:
    """改過的程式檔在 Stop 當下還在嗎（不在的再交給 vanished_code_paths 判是刪掉還是搬走）。"""
    return os.path.isfile(path)


VANISH_BUDGET_S = 2.0    # vanished_code_paths 整支查 git 的時間預算


def head_new_code(root: Path, cfg: Dict[str, Any], timeout_s: float = 2.0,
                  _run: Optional[Callable[..., Any]] = None) -> Tuple[str, List[str]]:
    """這個 git 根 HEAD 那筆提交新增、改名、複製進來的程式檔（相對根的路徑）與 HEAD 的 sha。PostToolUse 看到 commit 時記下來：
    搬檔後又 commit，工作樹的 status 就空了，搬過去的新路徑只留在提交裡。查不到 → ("", [])，stderr 說一聲。"""
    run = _run or subprocess.run
    try:
        r = run(["git", "-c", "core.quotepath=false", "-C", str(root), "show", "--name-status", "-M", "-C", "--format=%H", "HEAD"],
                capture_output=True, timeout=timeout_s, creationflags=_NO_WINDOW)
    except (OSError, subprocess.SubprocessError) as e:
        print(f"[verify_ledger] 在 {root} 讀不到 HEAD 的提交內容：{type(e).__name__}: {e}", file=sys.stderr)
        return "", []
    if r.returncode != 0:
        print(f"[verify_ledger] 在 {root} 讀 HEAD 的提交內容回非零", file=sys.stderr)
        return "", []
    lines = [ln for ln in r.stdout.decode("utf-8", "replace").splitlines() if ln.strip()]
    if not lines:
        return "", []
    exts = cfg.get("code_exts") or []
    new = []
    for ln in lines[1:]:
        cols = ln.split("\t")
        if cols and cols[0][:1] in "ARC" and len(cols) >= 2 and is_code_file(cols[-1], exts):
            new.append(cols[-1])
    return lines[0].strip(), new


def vanished_code_paths(paths: Iterable[str], cfg: Dict[str, Any], timeout_s: float = 2.0,
                        _run: Optional[Callable[..., Any]] = None,
                        committed_new: Optional[Dict[str, Any]] = None,
                        verdicts: Optional[Dict[str, Verdict]] = None) -> List[str]:
    """Stop 當下已不存在的改過程式檔，查事實交給 wg_release_rules.gone_verdict 判欠不欠，回不欠的那些：
    - 所在版控根：不在任何版控根內 → GONE_OUTSIDE_VCS（不欠）；svn → GONE_UNVERIFIABLE（照欠）
    - git 根：同根 status 新出現的程式檔（未追蹤、新增、改名、複製）＋本 session 在這個根的提交新加進來的程式檔
      （committed_new：PostToolUse 看到 commit 時用 head_new_code 記的）。有 → MOVED_NEW_CODE_SEEN（照欠）；沒有 → 刪除、不欠。
      搬走（mv、git mv、Rename-Item、整個目錄改名，搬完又 commit 也一樣）的程式一定會在其中一處以新路徑出現；不追搬檔寫法，只看結果。
      git 失敗或逾時、預算用完 → GONE_UNVERIFIABLE（照欠）。
    每個檔的判定 stderr 印一行（規則名＋證據）；verdicts 給了就把每個檔的 Verdict 填進去，擋訊息照印。"""
    run = _run or subprocess.run
    exts = cfg.get("code_exts") or []
    deadline = time.monotonic() + VANISH_BUDGET_S
    by_root: Dict[str, Tuple[Path, List[str]]] = {}
    found: Dict[str, Verdict] = {}
    for p in paths or []:
        hit, err = _vcs_hit_ex(str(p))
        if err:
            found[str(p)] = vcs_unreadable_verdict(Path(p).name, err)       # 讀不到 ≠ 不在版控：照欠
        elif hit and hit[0] == "git":
            by_root.setdefault(_norm_path(str(hit[1])), (hit[1], []))[1].append(str(p))
        else:
            found[str(p)] = gone_verdict(Path(p).name, hit[0] if hit else None)
    for key, (root, ps) in by_root.items():
        new_code: List[str] = list(((committed_new or {}).get(key) or {}).get("paths") or [])
        failed = ""
        left = deadline - time.monotonic()
        if new_code:
            pass                                                      # 提交裡已經看到新程式檔，不必再查 status
        elif left < _GIT_MIN_S:
            failed = f"在 {root} 沒時間查 git"
        else:
            try:
                st = run(["git", "-C", str(root), "status", "--porcelain=v1", "-z", "--untracked-files=all"],
                         capture_output=True, timeout=min(timeout_s, left), creationflags=_NO_WINDOW)
            except (OSError, subprocess.SubprocessError) as e:
                st, failed = None, f"在 {root} 查 git 失敗（{type(e).__name__}: {e}）"
            if st is not None and st.returncode != 0:
                failed = f"在 {root} 查 git 回非零"
            elif st is not None:
                fields, appeared, i = st.stdout.decode("utf-8", "replace").split("\0"), [], 0
                while i < len(fields):
                    f = fields[i]
                    if len(f) > 3:
                        if f[0] in "RC":
                            appeared.append(f[3:])
                            i += 1                                    # 改名／複製：下一欄是原路徑
                        elif "?" in f[:2] or "A" in f[:2]:
                            appeared.append(f[3:])
                    i += 1
                new_code = [n for n in appeared if is_code_file(n, exts)]
        for p in ps:
            found[p] = gone_verdict(Path(p).name, "git", new_code, failed)
    for v in found.values():
        print(f"[verify_ledger] {v.rule}：{v.why}（{'照欠補案例' if v.owed else '不欠補案例'}）", file=sys.stderr)
    if verdicts is not None:
        verdicts.update(found)
    return [p for p, v in found.items() if not v.owed]


def case_debt(own_mod_files: List[Dict[str, Any]], turn_seq: int, cfg: Dict[str, Any],
              root_of: Callable[[str], Optional[str]], gone: Iterable[str] = (),
              evidence: Optional[Dict[str, Verdict]] = None) -> List[str]:
    """補案例的義務（規則 OWED_AFTER_LAST_CASE，跨回合）：每個根找「本 session 最後一次改驗證案例之後還改過的程式檔」，回這些檔；
    evidence 給了就填每個欠的檔的 Verdict（最後一次改的案例是哪個），擋訊息照印。
    只有 Stop 當下仍存在的案例檔才算（刪除也會記一筆修改，不能拿它清帳）；gone 裡的程式檔（vanished_code_paths 判成刪除的）不欠；
    搬走的照欠，量尺閘照舊看所有改檔。同一個檔不同寫法、同一個根不同寫法都用 canon_path 比（SAME_FILE）。
    落在 exclude_globs 的檔（is_excluded：信箱素材等）兩邊都不算：不欠案例，也不能拿來替真程式清帳。
    案例判定用相對該根的路徑；拿不到根的程式檔退回絕對路徑，每個路徑 stderr 一行（本函式每次 Stop 只跑一次）。
    修改紀錄沒有 at／seq 的 legacy entry 照舊：只在本回合改過、且本回合同根沒改案例時算。
    範圍外：改的案例是不是對應這次改動，程式判不出來，交給收尾對照（需求目標核心流程 checklist C-G3）由 LLM 判。"""
    exts = cfg.get("code_exts") or []
    gone = {canon_path(p) for p in gone or ()}
    by_root: Dict[str, List[Dict[str, Any]]] = {}
    for m in own_mod_files or []:
        if isinstance(m, dict) and m.get("path"):
            r = root_of(m["path"])
            if not is_excluded(m["path"], cfg, r):
                by_root.setdefault(canon_path(r) if r else "", []).append(m)           # 同根比較用 canon_path（SAME_FILE）
    owed: List[str] = []
    owed_keys: set = set()
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
            p, k = m["path"], canon_path(m["path"])
            if not is_code_file(p, exts) or case_of[p] or k in owed_keys or k in gone:
                continue
            if _has_time(m):
                hit = last_case is None or _mod_after(m, last_case)
            else:
                t = m.get("last_turn_seq", m.get("turn_seq"))
                hit = t is not None and int(t) == int(turn_seq) and not case_this_turn
            if hit:
                owed.append(p)
                owed_keys.add(k)
                if evidence is not None:
                    evidence[p] = owed_after_last_case(Path(p).name, Path(last_case["path"]).name if last_case else None)
    return owed


def _content_sha(path: str) -> Optional[str]:
    """檔案內容的 sha256；不存在或讀不到回 None（不存在也是一種內容狀態：commit 時不在、現在也不在＝一樣）。"""
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def commit_snapshot(mods: List[Dict[str, Any]], turn_seq: int, cfg: Dict[str, Any],
                    root_of: Optional[Callable[[str], Optional[str]]] = None, prev: Any = None,
                    session_paths: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """commit 那一刻（PostToolUse 看到 git／svn commit）本 session 改過的每個檔的內容雜湊，與當時不欠案例的程式檔
    （case_debt 照當時的修改紀錄算）。Stop 拿它判 commit 之後的改動有沒有回到這個不欠案例的狀態（committed_settled_paths）。
    prev＝上一份快照：照修改時間算是欠、但對 prev 已經成立「回到不欠案例的狀態」的程式檔（committed_settled_paths；session_paths
    是同根要一起比的改檔，沒給就用 mods），新快照照算不欠：反證還原後又 commit（例：--amend 只改訊息），有效的豁免不被蓋掉。
    files／settled 的鍵是 canon_path（keys="canon"）：同一個檔被不同寫法記下也是同一筆；任一種寫法欠案例，這個檔就不算不欠。"""
    root_of = root_of or file_root_of
    paths = list(dict.fromkeys(m["path"] for m in mods or [] if isinstance(m, dict) and m.get("path")))
    owed = set(case_debt(mods, turn_seq, cfg, root_of))
    if owed and prev:
        owed -= set(committed_settled_paths(prev, owed, paths if session_paths is None else session_paths, root_of))
    owed_keys = {canon_path(p) for p in owed}
    exts = cfg.get("code_exts") or []
    settled = {canon_path(p) for p in paths
               if is_code_file(p, exts) and not is_case_file(p, cfg, root_of(p)) and canon_path(p) not in owed_keys}
    return {"turn": int(turn_seq), "keys": "canon", "files": {canon_path(p): _content_sha(p) for p in paths},
            "settled": sorted(settled)}


def committed_settled_paths(snapshot: Any, owed: Iterable[str], session_paths: Iterable[str],
                            root_of: Optional[Callable[[str], Optional[str]]] = None, deadline: Optional[float] = None,
                            _run: Optional[Callable[..., Any]] = None) -> List[str]:
    """欠案例的程式檔裡，commit 那一刻（commit_snapshot）它不欠案例、同根本 session 改過的每個檔（主 session＋所有子代理）
    現在的內容都和那一刻一樣、而且這些檔 git status 都乾淨（_root_clean，和 net_unchanged_paths 同一個條件：只把工作樹改回去、
    暫存區還留著新內容也算有差）→ 回這些檔：commit 之後做反證，把程式或案例退回舊版又還原，補案例的義務不重算。
    只免補案例，量尺照舊要跑。快照之後才改的檔（不在快照裡）、任一檔內容不同、案例被刪或還留舊版、git 有差或判不出來
    （任一相關檔不在 git 工作區、git 失敗或逾時、預算用完；deadline 給了就和 net_unchanged_paths 共用同一個整支預算）→ 不回。
    同一個專案根跨好幾個 git 根（巢狀 repo、submodule）時，比內容的那些檔落在哪幾個 git 根就每個都查，全部乾淨才算。
    路徑一律用 canon_path 比（快照成員、內容鍵、同根），同一個檔不同寫法是同一個；沒有 keys="canon" 的舊快照照原字串比。"""
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("files"), dict):
        return []
    key: Callable[[str], str] = canon_path if snapshot.get("keys") == "canon" else str
    files, settled = snapshot["files"], set(snapshot.get("settled") or [])
    root_of = root_of or file_root_of

    def root_key(q: str) -> str:
        r = root_of(q)
        return canon_path(r) if r else ""
    every = list(dict.fromkeys(str(p) for p in session_paths or []))
    cands: List[Tuple[str, List[str]]] = []               # (欠案例的程式檔, 同專案根要一起比的檔，每個檔一種寫法)
    for p in owed or []:
        if key(p) not in settled:
            continue
        r = root_key(p)
        same_root = list({key(q): q for q in [*(q for q in every if root_key(q) == r), p]}.values())
        if all(key(q) in files and _content_sha(q) == files[key(q)] for q in same_root):
            cands.append((p, same_root))
    if not cands:
        return []
    run = _run or subprocess.run
    deadline = git_deadline() if deadline is None else deadline
    git_of = {q: _git_root_of(q) for q in dict.fromkeys([*every, *(q for _, qs in cands for q in qs)])}
    clean: Dict[str, bool] = {}
    out: List[str] = []
    for p, same_root in cands:
        outside = [q for q in same_root if not git_of[q]]
        if outside:
            print(f"[verify_ledger] {Path(outside[0]).name} 不在 git 工作區，查不了暫存區，commit 之後的還原照算改了（{Path(p).name}）",
                  file=sys.stderr)
            continue
        for key, root in dict.fromkeys(git_of[q] for q in same_root):
            if key not in clean:
                in_root = [q for q, h in git_of.items() if h and h[0] == key]
                clean[key] = _root_clean(root, [p], in_root, deadline, 3.0, run)
        if all(clean[git_of[q][0]] for q in same_root):
            out.append(p)
    return out


GIT_BUDGET_S = 4.0       # 「內容回到某狀態」豁免（net_unchanged_paths＋committed_settled_paths）整支查 git 的時間預算（Guardian Stop hook 上限 10 秒，其餘留給後面的閘）
_GIT_MIN_S = 0.2         # 剩餘預算不到這麼多就不再開 git 子行程
_GIT_SPEC_CAP = 24000    # pathspec 合計字數上限（Windows 命令列 32767 字）；超過就不查，照算改了


def git_deadline(budget_s: Optional[float] = None) -> float:
    """查 git 的整支時間預算截止點（monotonic；預設 GIT_BUDGET_S 秒）。同一次 Stop 的兩種「內容回到某狀態」豁免共用一個。"""
    return time.monotonic() + (GIT_BUDGET_S if budget_s is None else float(budget_s))


def _vcs_hit_ex(path: str) -> Tuple[Optional[Tuple[str, Path]], str]:
    """改檔所在的版控根 → ((種類 git／svn, 根) 或 None, 讀不到的原因)；檔或目錄被刪了往上找還在的目錄。
    規則 VCS_ROOT_UNREADABLE：第二欄非空＝檔案系統出錯，不是「不在版控」。"""
    d = Path(path).parent
    try:
        while not d.exists() and d.parent != d:
            d = d.parent
    except OSError as e:
        return None, f"{type(e).__name__}: {e}"
    return find_vcs_root_ex(d)


def _vcs_hit(path: str) -> Optional[Tuple[str, Path]]:
    """改檔所在的版控根 → (種類 git／svn, 根)；不在任何版控根內或讀不到回 None。"""
    return _vcs_hit_ex(path)[0]


def _git_root_of(path: str) -> Optional[Tuple[str, Path]]:
    """改檔所在的 git 根 → (正規化鍵, 根)；不在 git 工作區回 None。"""
    hit = _vcs_hit(path)
    return (_norm_path(str(hit[1])), hit[1]) if hit and hit[0] == "git" else None


def _git_out(root: Path, args: List[str], deadline: float, timeout_s: float, run: Callable[..., Any]) -> Optional[bytes]:
    """在 root 跑一次帶改檔路徑的 git 查詢，只拿剩餘預算（最多 timeout_s）。pathspec 一律不分大小寫（--icase-pathspecs）：
    Windows 上 Edit 寫 `src/A.py`、git 記 `src/a.py` 是同一個檔，分大小寫會查不到、空輸出被當成乾淨；結果另用小寫鍵比回改檔。
    預算不足、逾時、失敗、回非零 → None，stderr 說哪個根、照算改了。"""
    left = deadline - time.monotonic()
    try:
        if left < _GIT_MIN_S:
            raise subprocess.TimeoutExpired(f"git {args[0]}", 0)
        r = run(["git", "-C", str(root), "--icase-pathspecs", *args], capture_output=True, timeout=min(timeout_s, left),
                creationflags=_NO_WINDOW)
    except subprocess.TimeoutExpired as e:
        print(f"[verify_ledger] 在 {root} 查 git 逾時或時間預算用完（TimeoutExpired：{e.cmd}；整支預算預設 {GIT_BUDGET_S} 秒），"
              "沒查完，這些改檔照算改了", file=sys.stderr)
        return None
    except (OSError, subprocess.SubprocessError) as e:
        print(f"[verify_ledger] 在 {root} 查 git 失敗，這些改檔照算改了：{type(e).__name__}: {e}", file=sys.stderr)
        return None
    if r.returncode != 0:
        err = (r.stderr or b"").decode("utf-8", "replace").strip()[:120]
        print(f"[verify_ledger] 在 {root} 查 git 回非零，這些改檔照算改了：{err}", file=sys.stderr)
        return None
    return r.stdout


def _root_clean(root: Path, paths: List[str], every: List[str], deadline: float, timeout_s: float,
                run: Callable[..., Any]) -> bool:
    """「內容回到某狀態」的豁免共用的 git 條件（net_unchanged_paths、committed_settled_paths 都走這裡，不各寫一套）：
    這個 git 根裡本 session 改過的每個檔（every）`git status --ignored --untracked-files=all` 都沒有輸出：改動、已暫存
    （只把工作樹改回去、暫存區還留著新內容也算）、刪除、未追蹤、被忽略都算有差。paths＝要豁免的那幾個：它們本身乾淨、
    卻被同根其他改檔拖住時 stderr 說一聲。路徑太長、預算不足、git 失敗或逾時 → False（照算改了），stderr 說哪個根。"""
    spec_all = [str(x).replace("\\", "/") for x in every]
    spec_len = sum(len(s) + 1 for s in spec_all)
    if spec_len > _GIT_SPEC_CAP:
        print(f"[verify_ledger] {root} 這次改過的檔路徑合計 {spec_len} 字（{len(spec_all)} 個檔），超過命令列可帶的 "
              f"{_GIT_SPEC_CAP} 字，查不了 git，這些改檔照算改了", file=sys.stderr)
        return False
    raw = _git_out(root, ["status", "--porcelain=v1", "-z", "--ignored", "--untracked-files=all", "--", *spec_all],
                   deadline, timeout_s, run)
    if raw is None:
        return False
    key = canon_path(str(root))
    changed, fields, i = set(), raw.decode("utf-8", "replace").split("\0"), 0
    while i < len(fields):
        f = fields[i]
        if len(f) > 3:
            changed.add(canon_path(f"{key}/{f[3:]}"))
            if f[0] in "RC" and i + 1 < len(fields):    # 改名／複製：下一欄是原路徑
                i += 1
                changed.add(canon_path(f"{key}/{fields[i]}"))
        i += 1
    dirty = [p for p in every if canon_path(p) in changed]
    if dirty and any(canon_path(p) not in changed for p in paths):
        print(f"[verify_ledger] {root} 還有本 session 改過、跟 HEAD 不同的檔（{'、'.join(Path(p).name for p in dirty[:3])}），"
              "這個根的改檔一律照算改了", file=sys.stderr)
    return not dirty


def net_unchanged_paths(mods: List[Dict[str, Any]], last_commit_turn: Any = None, timeout_s: float = 3.0,
                        _run: Optional[Callable[..., Any]] = None, session_paths: Optional[Iterable[str]] = None,
                        budget_s: Optional[float] = None, deadline: Optional[float] = None) -> List[str]:
    """改過、但現在跟 HEAD 一模一樣的檔（例：反證時暫改、又 git checkout 還原）→ 回這些檔的 path（照 modified_files 的寫法）。
    要同時成立：git 追蹤著它、本 session 從第一次改它那回合起沒跑過 commit（last_commit_turn ≥ 該檔 turn_seq：工作樹乾淨可能是
    把改動提交了，照算改了），而且同一個 git 根裡本 session 改過的每個檔（session_paths：主 session 與所有子代理的改檔，沒給就只看
    mods）git status 都沒有輸出（_root_clean）：只把程式還原、案例還留著舊版，這個根就一個都不剔除。
    時間：整支共用一個截止點（deadline；沒給就從現在起算 budget_s，預設 GIT_BUDGET_S 秒），每個 git 子行程只拿剩餘預算
    （最多 timeout_s）；預算不足沒查到的根照算改了，stderr 印根路徑。判不出來（不在 git 工作區、修改紀錄沒有回合、git 失敗或逾時）
    → 不回，照算改了（不放寬）。每個根最多兩次 git（status 有差就不再查 ls-files）。"""
    run = _run or subprocess.run
    deadline = git_deadline(budget_s) if deadline is None else deadline
    try:
        last = int(last_commit_turn) if last_commit_turn is not None else None
    except (TypeError, ValueError):
        return []
    by_root: Dict[str, Tuple[Path, List[str], List[str]]] = {}     # 鍵 → (根, 可剔除的改檔, 同根本 session 全部改檔)
    for m in mods or []:
        p, t = (m.get("path"), m.get("turn_seq")) if isinstance(m, dict) else (None, None)
        try:
            if not p or t is None or (last is not None and last >= int(t)):
                continue
        except (TypeError, ValueError):
            continue
        hit = _git_root_of(p)
        if hit:
            by_root.setdefault(hit[0], (hit[1], [], []))[1].append(p)
    if not by_root:
        return []
    for p in [*(session_paths or []), *(m["path"] for m in mods or [] if isinstance(m, dict) and m.get("path"))]:
        hit = _git_root_of(str(p))
        if hit and hit[0] in by_root and p not in by_root[hit[0]][2]:
            by_root[hit[0]][2].append(str(p))
    out: List[str] = []
    for key, (root, paths, every) in by_root.items():
        if not _root_clean(root, paths, every, deadline, timeout_s, run):
            continue
        tracked = _git_out(root, ["ls-files", "-z", "--full-name", "--", *(str(x).replace("\\", "/") for x in paths)],
                           deadline, timeout_s, run)
        if tracked is None:
            continue
        known = {canon_path(f"{key}/{f}") for f in tracked.decode("utf-8", "replace").split("\0") if f}
        out += [p for p in paths if canon_path(p) in known]
    return out


# ─── 045：已提交版本的事實（CONTENT_EQUALS_COMMITTED／COMMENT_ONLY_CHANGE／RED_WHILE_REVERTED 共用）────────
_REF_CANDIDATES = ("HEAD", "MERGE_HEAD", "main", "master")
REF_BUDGET_S = 3.5       # 典型 4 次 git（show-ref、ls-tree、hash-object、show）；負載下每次可達 0.7 秒


def _run_git(root: Path, args: List[str], timeout_s: float, _run: Optional[Callable[..., Any]] = None) -> Optional[str]:
    """跑一次 git，回 stdout（utf-8）；失敗、非零、逾時 → None（stderr 一行）。"""
    run = _run or subprocess.run
    try:
        r = run(["git", "-c", "core.quotepath=false", "-C", str(root), *args], capture_output=True,
                timeout=max(0.1, timeout_s), creationflags=_NO_WINDOW)
    except (OSError, subprocess.SubprocessError) as e:
        print(f"[verify_ledger] 在 {root} 跑 git {args[0]} 失敗：{type(e).__name__}: {e}", file=sys.stderr)
        return None
    if r.returncode != 0:
        return None
    return r.stdout.decode("utf-8", "replace")


def ref_blob_facts(root: Path, rel_paths: List[str], deadline: Optional[float] = None,
                   _run: Optional[Callable[..., Any]] = None) -> Dict[str, Any]:
    """一個 git 根的已提交事實：{"commits": {ref: sha}, "blobs": {ref: {rel: blob}}, "current": {rel: blob}}。
    ref 只看 HEAD／MERGE_HEAD／main／master（存在的才列）；current 用 `git hash-object`（套 clean filter，CRLF 不影響）。
    預算到就少查（缺的 ref 當拿不到，呼叫端照算改了）。"""
    deadline = deadline if deadline is not None else time.monotonic() + REF_BUDGET_S
    out: Dict[str, Any] = {"commits": {}, "blobs": {}, "current": {}}
    if not rel_paths:
        return out
    left = deadline - time.monotonic()
    if left < _GIT_MIN_S:
        return out
    text = _run_git(root, ["show-ref", "--head"], left, _run) or ""
    heads: Dict[str, str] = {}
    for ln in text.splitlines():
        parts = ln.split()
        if len(parts) == 2:
            heads[parts[1]] = parts[0]
    for ref in _REF_CANDIDATES:
        sha = heads.get(ref) or heads.get(f"refs/heads/{ref}")
        if sha:
            out["commits"][ref] = sha
    if "MERGE_HEAD" not in out["commits"]:
        # MERGE_HEAD 是 git 目錄裡的一行純文字（worktree 的 .git 是檔，指向 gitdir）：直接讀，省一次 git 子行程
        try:
            dot = root / ".git"
            gitdir = dot if dot.is_dir() else Path(dot.read_text(encoding="utf-8", errors="replace").split("gitdir:", 1)[-1].strip())
            gitdir = gitdir if gitdir.is_absolute() else root / gitdir
            mh = (gitdir / "MERGE_HEAD").read_text(encoding="utf-8", errors="replace").split()
            if mh and len(mh[0]) >= 7:
                out["commits"]["MERGE_HEAD"] = mh[0]
        except OSError:
            pass
    seen_sha: Dict[str, Dict[str, str]] = {}
    for ref, sha in list(out["commits"].items()):
        if sha in seen_sha:
            out["blobs"][ref] = seen_sha[sha]
            continue
        left = deadline - time.monotonic()
        if left < _GIT_MIN_S:
            break
        tree = _run_git(root, ["ls-tree", "-z", sha, "--", *rel_paths], left, _run)
        if tree is None:
            continue
        blobs: Dict[str, str] = {}
        for ent in tree.split("\0"):
            if not ent or "\t" not in ent:
                continue
            meta, rel = ent.split("\t", 1)
            cols = meta.split()
            if len(cols) >= 3:
                blobs[rel.replace("\\", "/")] = cols[2]
        out["blobs"][ref] = seen_sha[sha] = blobs
    existing = [p for p in rel_paths if (root / p).is_file()]
    left = deadline - time.monotonic()
    if existing and left >= _GIT_MIN_S:
        text = _run_git(root, ["hash-object", "--", *existing], left, _run)
        if text is not None:
            for rel, sha in zip(existing, text.split()):
                out["current"][rel] = sha
    return out


def _rel_in_root(path: str, root_key: str) -> Optional[str]:
    n = _norm_path(path)
    return n[len(root_key) + 1:] if n.startswith(root_key + "/") else None


def _comment_only_vs_head(root: Path, rel: str, path: str, deadline: float, _run: Optional[Callable[..., Any]]) -> Optional[bool]:
    """path 與 HEAD:rel 是否只差註解／docstring／空白；拿不到或判不了 → None。"""
    left = deadline - time.monotonic()
    if left < _GIT_MIN_S or not str(path).lower().endswith((".py", ".pyw")):
        return None
    head_src = _run_git(root, ["show", f"HEAD:{rel}"], left, _run)
    try:
        cur_src = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return comment_only_change(head_src, cur_src, path)


def committed_equal_paths(mods: List[Dict[str, Any]], cfg: Dict[str, Any], last_commit_turn: Any = None,
                          own_commit_shas: Optional[Dict[str, Any]] = None, budget_s: Optional[float] = None,
                          _run: Optional[Callable[..., Any]] = None,
                          session_paths: Optional[Iterable[str]] = None, deadline: Optional[float] = None) -> Dict[str, Verdict]:
    """改過的程式檔裡「不是本 session 改碼」的，回 {path: Verdict}：
    - CONTENT_EQUALS_COMMITTED：內容等於另一方已提交的版本（MERGE_HEAD／main／master；指到 HEAD 或本 session 自己提交的 commit 不算）。
    - COMMENT_ONLY_CHANGE：與 HEAD 只差註解／docstring／空白，且本 session 沒 commit 過它；同根本 session（主 session＋子代理，
      session_paths）改過的其他檔也都要等於 HEAD 或只差註解——程式與案例一起退回舊版、只還原程式時案例還是舊的，照欠
      （與 NET_UNCHANGED 同一條防線，verify_stop_reconcile 035 ⑤／037）。
    判不出來（不在 git、預算到、拿不到 ref）→ 不回，照算改了。"""
    exts = cfg.get("code_exts") or []
    # 預算：呼叫端給 deadline（stop 把 net_unchanged／快照／這裡共用同一個 git_deadline，整個 Stop 的 git 查詢加起來不超過 GIT_BUDGET_S）；
    # 沒給才自己開一把、同樣不超過 GIT_BUDGET_S（被測試或設定壓到 0 時這裡也不查、照算改了）
    if deadline is None:
        deadline = time.monotonic() + (min(REF_BUDGET_S, float(GIT_BUDGET_S)) if budget_s is None else float(budget_s))
    try:
        last = int(last_commit_turn) if last_commit_turn is not None else None
    except (TypeError, ValueError):
        last = None
    by_root: Dict[str, Tuple[Path, List[Dict[str, Any]]]] = {}
    for m in mods or []:
        p = (m or {}).get("path") if isinstance(m, dict) else None
        if not p or not is_code_file(p, exts) or not os.path.isfile(p):
            continue
        hit = _git_root_of(p)
        if hit:
            by_root.setdefault(hit[0], (hit[1], []))[1].append(m)
    if not by_root:
        return {}
    every: Dict[str, List[str]] = {}            # 根 → 同根本 session 改過的所有檔（含案例、子代理的）
    for p in [*(session_paths or []), *(m["path"] for m in mods or [] if isinstance(m, dict) and m.get("path"))]:
        hit = _git_root_of(str(p))
        if hit and hit[0] in by_root and str(p) not in every.setdefault(hit[0], []):
            every[hit[0]].append(str(p))
    out: Dict[str, Verdict] = {}
    for key, (root, ms) in by_root.items():
        rels = {p: _rel_in_root(p, key) for p in every.get(key, [])}
        rel_list = [r for r in rels.values() if r]
        if not rel_list:
            continue
        facts = ref_blob_facts(root, rel_list, deadline, _run)
        if not facts["commits"]:
            continue
        own = ((own_commit_shas or {}).get(key) or {}).get("shas") or []
        refs = committed_refs(own, facts["commits"])
        head_blobs = facts["blobs"].get("HEAD") or {}
        root_clean: Optional[bool] = None        # 同根其他改檔都等於 HEAD 或只差註解（只在需要時算一次）

        def _root_head_clean(skip: str) -> bool:
            for q, qrel in rels.items():
                if q == skip:
                    continue
                if not qrel or not os.path.isfile(q):
                    return False
                if facts["current"].get(qrel) and facts["current"].get(qrel) == head_blobs.get(qrel):
                    continue
                if _comment_only_vs_head(root, qrel, q, deadline, _run) is not True:
                    return False
            return True

        for m in ms:
            p, rel = m["path"], rels.get(m["path"])
            if not rel:
                continue
            ref_blobs = {ref: (facts["blobs"].get(ref) or {}).get(rel) for ref in refs}
            v = content_equals_committed(Path(p).name, facts["current"].get(rel), ref_blobs, refs)
            if v is not None:
                out[p] = v
                continue
            try:
                first_turn = int(m.get("turn_seq"))
            except (TypeError, ValueError):
                first_turn = None
            committed_since = first_turn is None or (last is not None and last >= first_turn)
            if committed_since or not head_blobs.get(rel):
                continue                          # commit 過它：HEAD 就是自己的碼，不拿 HEAD 比
            if facts["current"].get(rel) == head_blobs.get(rel):
                continue                          # 內容與 HEAD 一模一樣：那是 NET_UNCHANGED 的判定（它還看同根乾淨與預算），這裡不插手
            if _comment_only_vs_head(root, rel, p, deadline, _run) is not True:
                continue
            if root_clean is None:
                root_clean = _root_head_clean(p)
            if root_clean:
                out[p] = comment_only_verdict(Path(p).name, "HEAD")
            else:
                print(f"[Guardian:ReconcileGate] {Path(p).name} 與 HEAD 只差註解，但同根還有改過、與 HEAD 不同的檔，照算改了", file=sys.stderr)
    return out


def reverted_code_files(mods: List[Dict[str, Any]], cfg: Dict[str, Any], budget_s: Optional[float] = None,
                        _run: Optional[Callable[..., Any]] = None) -> Tuple[List[Tuple[str, str]], List[str]]:
    """RED_WHILE_REVERTED 的事實：回 (退回的, 還有現行改碼的)。退回＝本 session 改過、現在內容等於非 HEAD 已提交版本（MERGE_HEAD／main／master）；
    現行改碼＝本 session 改過的程式檔，內容既不等於 HEAD 也不等於任何那些 ref（自己的碼還在）。拿不到事實的檔算現行改碼（保守）。"""
    exts = cfg.get("code_exts") or []
    deadline = time.monotonic() + (REF_BUDGET_S if budget_s is None else float(budget_s))
    by_root: Dict[str, Tuple[Path, List[str]]] = {}
    for m in mods or []:
        p = (m or {}).get("path") if isinstance(m, dict) else None
        if not p or not is_code_file(p, exts) or not os.path.isfile(p):
            continue
        hit = _git_root_of(p)
        if hit:
            by_root.setdefault(hit[0], (hit[1], []))[1].append(p)
    reverted: List[Tuple[str, str]] = []
    pending: List[str] = []
    for key, (root, paths) in by_root.items():
        rels = {p: _rel_in_root(p, key) for p in paths}
        facts = ref_blob_facts(root, [r for r in rels.values() if r], deadline, _run)
        head_sha = facts["commits"].get("HEAD")
        head_blobs = facts["blobs"].get("HEAD") or {}
        for p, rel in rels.items():
            cur = facts["current"].get(rel or "")
            if not cur:
                pending.append(Path(p).name)
                continue
            if head_blobs.get(rel) == cur:
                continue                                  # 等於 HEAD：不是現行改碼，也不是退回
            hit_ref = next((ref for ref, sha in facts["commits"].items()
                            if ref != "HEAD" and sha != head_sha and (facts["blobs"].get(ref) or {}).get(rel) == cur), None)
            if hit_ref:
                reverted.append((Path(p).name, hit_ref))
            else:
                pending.append(Path(p).name)
    return reverted, pending


def green_settled_paths(owed: Iterable[str], own_mod_files: List[Dict[str, Any]], receipts: List[Dict[str, Any]],
                        cfg: Dict[str, Any], root_of: Callable[[str], Optional[str]]) -> Dict[str, Verdict]:
    """CASE_GREEN_AFTER_EDIT：欠案例的程式檔裡，改完之後有同根、仍存在、本 session 改過的案例檔被合格 PASS 收據點名跑綠的 → {path: Verdict}。"""
    mods = {m["path"]: m for m in own_mod_files or [] if isinstance(m, dict) and m.get("path")}
    cases = [p for p in mods if is_case_file(p, cfg, root_of(p)) and case_exists(p)]
    if not cases:
        return {}
    # 收據要和 (a) 同一套採認：指令完整、記了環境、根可信（_trusted），而且只有執行程式的指令（_clean：echo／cat 夾字樣不算）；
    # 「點名案例」只看實際跑程式那幾段的參數（claimed_paths），不看整條指令文字（codex 001 BLOCK 3）
    greens = []
    for r0 in pass_receipts(receipts):
        r = _trusted(r0)
        if r is not None and _clean(r):
            greens.append(r)
    out: Dict[str, Verdict] = {}
    for p in owed or []:
        root = root_of(p)
        same_root_cases = [c for c in cases if root_of(c) == root]
        if not same_root_cases:
            continue
        for r in greens:
            named = claimed_paths(r, same_root_cases)
            if not named or not _root_ok(r, root) or not _after_last_edit(r, mods.get(p)):
                continue
            out[p] = green_after_edit_verdict(Path(p).name, Path(named[0]).name, str(r.get("cmd") or ""), str(r.get("at") or ""))
            break
    return out


_TEMP_ROOTS: List[str] = []


def _temp_receipt(receipt: Dict[str, Any]) -> bool:
    """TEMP_COPY_NOT_PROJECT：收據在暫存目錄跑（cwd／project_root）或跑的是暫存目錄裡的腳本 → 不當收據。"""
    if str(os.environ.get("WG_TEMP_RULES", "")).lower() == "off":
        return False
    if not _TEMP_ROOTS:
        import tempfile
        _TEMP_ROOTS.extend(_norm_long(r) for r in temp_roots(tempdir=tempfile.gettempdir()))
    for key in ("cwd", "project_root"):
        v = str(receipt.get(key) or "")
        if v and is_temp_path(_norm_long(v), _TEMP_ROOTS):
            return True
    cmd = str(receipt.get("cmd") or "")
    for tok in re.findall(r"[A-Za-z]:[\\/][^\s\"']+|/[^\s\"']+|\\\\\?\\[^\s\"']+", cmd):
        if is_temp_path(_norm_long(tok), _TEMP_ROOTS):
            return True
    return False


def _norm_long(p: str) -> str:
    """暫存判斷兩側同一種表示：8.3 短路徵展成長路徑（handlers/_shared._comparable）再正規化。"""
    try:
        from handlers._shared import _comparable
        return norm_temp_path(_comparable(p))
    except Exception:  # noqa: BLE001
        return norm_temp_path(p)


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
                         case_settled: Optional[Callable[[List[str]], Iterable[str]]] = None,
                         committed_new: Optional[Dict[str, Any]] = None,
                         user_turn: Optional[int] = None,
                         exec_this_turn: bool = False,
                         ) -> Tuple[Optional[str], Optional[str]]:
    """回 (寫碼查核擋訊息或 None, 收尾報告欄擋訊息或 None)。純判定、不改 state。
    「本回合」的收據與改檔：user_turn（使用者打字開的回合，stop._user_turn）給了就是它到 turn_seq 之間的每個 turn_seq
    （同伴訊息、背景通知讓 turn_seq 前進，剛跑完的驗證仍算本回合）；沒給只認 turn_seq 那一個。
    exec_this_turn＝本回合跑過 Bash／PowerShell（PostToolUse 記的 exec_turn_seq 落在本回合）：(c) 不再只靠 transcript 這一段的工具名。
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
    this_turn = [r for r in receipts if in_turn(r.get("turn_seq", -1), turn_seq, user_turn)]
    mod_turn = modified_this_turn(own_mod_files, turn_seq, user_turn)
    turn_rule = (f"（規則 TURN_SINCE_USER_PROMPT：本回合＝turn {min(int(user_turn), int(turn_seq))}～{turn_seq}，"
                 f"期間收據 {len(this_turn)} 筆）" if user_turn is not None else "")
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

    hits: List[str] = []          # 每條都是 format_hit 的一行：`✗ (<字母>) <規則名>：<一句現象>｜證據：…`
    if any(claims_fixed(t, phrases) for t in texts) and not related and not covered():
        hits.append(format_hit("a", Verdict(
            "CLAIM_FIXED_NEEDS_PASS", True, f"說「修好」但 {_pass_why(this_turn, receipts, unrelated, relate_paths)}",
            (f"本回合 PASS 收據 {len(pass_receipts(this_turn))} 筆、對得上改檔的 0 筆" + turn_rule,
             "修好的證據是本回合跑「驗那個改動」的驗證（cmd 提到改的檔／verify 路徑／量尺指令）印出 `<NAME>_CHECK PASS` 且 exit 0，"
             "或改完之後才開始跑、全綠、同一棵樹的部位量尺自寫收據（背景全量）" + note("PASS")))))
    measured = any("DONE" in _verdicts(r) and (_clean(r) or any(_ruler_ran(mc, r) for mc in measure_cmds))
                   for r in this_turn)
    if any(claims_measured(t, phrases) for t in texts) and not measured and not covered():
        hits.append(format_hit("b", Verdict(
            "CLAIM_MEASURED_NEEDS_DONE", True, "說「量了」但本回合沒有 `<NAME> DONE k=v` 收據，也沒有改完之後跑的部位量尺自寫收據",
            (("補跑量尺讓它印 DONE 尾行" if pending else "量了就讓量尺腳本印 DONE 尾行，沒量就寫沒量") + note("DONE") + turn_rule,))))
    if not exec_this_turn and any(tried_claim_without_exec(t, turn_tool_names, cfg.get("exec_tools") or [], this_turn, phrases)
                                  for t in texts):
        hits.append(format_hit("c", Verdict(
            "CLAIM_TRIED_NEEDS_EXEC", True, "說「試過／跑了」但本回合沒有任何 Bash／PowerShell 執行",
            (f"本回合工具呼叫：{'、'.join(sorted(set(str(n) for n in turn_tool_names))[:6]) or '（無）'}" + turn_rule,
             "現在跑出收據" if pending else "沒跑就寫沒跑，或現在跑"))))
    exts = cfg.get("code_exts") or []
    absent = [p for p in mod_session if is_code_file(p, exts) and not is_excluded(p, cfg, root_of(p)) and not code_exists(p)]
    why: Dict[str, Verdict] = {}
    gone = vanished_code_paths(absent, cfg, committed_new=committed_new, verdicts=why) if absent else ()
    debt_why: Dict[str, Verdict] = {}
    owed = case_debt(own_mod_files, turn_seq, cfg, root_of, gone, evidence=debt_why)
    if owed and case_settled:
        done = set(case_settled(owed))
        if done:
            print("[Guardian:ReconcileGate] 規則 SNAPSHOT_SETTLED：commit 時不欠案例、之後改了又回到那時的內容，不重算補案例："
                  + "、".join(Path(p).name for p in sorted(done)[:5]), file=sys.stderr)
        owed = [p for p in owed if p not in done]
    if owed:
        green = green_settled_paths(owed, own_mod_files, receipts, cfg, root_of)
        for p, v in green.items():
            print(f"[Guardian:ReconcileGate] 規則 {v.rule}：{v.why}｜證據：{'；'.join(v.evidence)}", file=sys.stderr)
        owed = [p for p in owed if p not in green]
    if owed:
        names = "、".join(Path(p).name for p in owed[:4])
        per_file = [v for v in (why.get(p) or debt_why.get(p) for p in owed[:4]) if v]
        cases_touched = [Path(m["path"]).name for m in own_mod_files or []
                         if isinstance(m, dict) and m.get("path") and is_case_file(m["path"], cfg, root_of(m["path"]))]
        hits.append(format_hit("d", Verdict(
            per_file[0].rule if per_file else "OWED_AFTER_LAST_CASE", True,
            f"改了程式碼（{names}）之後沒有新增或修改驗證 case 檔（案例檔要和程式同根、現在還在、是程式檔；義務跨回合，不看收尾措辭）",
            (*[f"{v.rule}：{v.why}" for v in per_file],
             f"本 session 改過的案例檔：{'、'.join(cases_touched[:4]) or '（無）'}",
             "改碼之後沒有點名同根案例檔跑綠的 PASS 收據（規則 CASE_GREEN_AFTER_EDIT）",
             "改了碼沒驗證 case（PASS 不能代替）：補一個會紅的 case 再跑綠；真的不需要補案例，就照【收尾放行確認】問使用者"))))
    # (e) 只檢本版報告（post_tool_use 一定寫入 j／k 兩鍵）；升級前 emit 的舊報告沒這兩鍵，不拿它擋
    report: List[str] = []
    if (claims_completion(last_text) and aec_emitted and isinstance(aec, dict)
            and "j_evidence_path" in aec and "k_followups" in aec):
        if aec_evidence_missing(aec.get("j_evidence_path"), bool(receipts)):
            report.append(format_hit("e", Verdict(
                "AEC_EVIDENCE_PATH", True, f"收尾檢核 (j) 證據持久路徑缺或不存在，但本 session 有 {len(receipts)} 筆驗證收據",
                (f"填帳本路徑（{ledger_path(sid or 'SID')}）或其他真存在的證據檔",))))
        if aec_followups_missing(aec.get("k_followups")):
            report.append(format_hit("e", Verdict(
                "AEC_FOLLOWUPS_EMPTY", True, "收尾檢核 (k) 追蹤項是空字串", ("有就一行一項，沒有就寫「無」",))))
    note = ""
    if any(r.get("exit_unknown") for r in related) or any(r.get("exit_unknown") for r in unrelated):
        note = "\n註：有 PASS 收據的 exit 未知（exit 未知＝dict 回應沒有 exit 欄），只憑哨兵認定。"
    tail = _RECONCILE_TAIL_EVIDENCE if pending or owed else _RECONCILE_TAIL
    code_reason = (_RECONCILE_HEAD + "\n".join("  " + h for h in hits) + tail + note) if hits else None
    report_reason = (_RECONCILE_HEAD + "\n".join("  " + h for h in report) + _RECONCILE_TAIL) if report else None
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
    exit 0 且 failed 0；記下的行程環境沒有縮小驗證範圍的設定（scope_env，與 session 收據同一個判斷；沒記 env 的舊收據看不出來，
    不算）；started_at 晚於該部位最後一次修改；收據根（受測樹 project_root）與部位根同一棵樹（_root_ok）。
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
        if not isinstance(r.get("env"), dict) or _self_receipt.scope_env(r["env"].items()):
            continue
        if not _receipt_after({"at": r.get("started_at") or ""}, edit_at or None, None, edit_turn):
            continue
        if _root_ok(r, root):
            return True
    return False


def _self_run_scope_env(runs: Iterable[Dict[str, Any]], cmd: str, root: str) -> List[str]:
    """argv 對上這把量尺、但記下的環境縮小了驗證範圍的自寫收據 → 那些變數名（給量尺閘說最近那份為什麼不算）。"""
    names: List[str] = []
    for r in runs or []:
        argv = r.get("argv") if isinstance(r, dict) else None
        if not isinstance(r, dict) or not isinstance(r.get("env"), dict) or not cmd_matches(
                cmd, argv if isinstance(argv, list) and argv else str(r.get("cmd", "")),
                root=str(r.get("project_root") or ""), measure_root=str(root or "")):
            continue
        names += [n for n in _self_receipt.scope_env(r["env"].items()) if n not in names]
    return names


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
            if _env_of(last) is None:
                why = ("最近一次跑尺的收據沒記啟動環境（升級前落的帳），看不出父行程有沒有把驗證範圍縮小（PYTEST_ADDOPTS 等）；"
                       "請重跑一次")
            elif _trusted(last) is None:
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
        env_runs = [] if root_wt else _self_run_scope_env(_runs[0], cmd, str(root))
        if env_runs:
            blocks[-1] += f"run_verify 自寫收據對上了這把尺，但跑的時候{_scope_env_why([(n, '', '') for n in env_runs])}"
    reason = None
    if blocks:
        reason = ("[Guardian:MeasureGate] 改到有量尺的部位，收尾前要跑過那把尺：\n"
                  + "\n".join("  " + format_hit("m", Verdict("MEASURE_RULER_NOT_RUN", True, b.split("。", 1)[0],
                                                             tuple(x for x in b.split("。", 1)[1:] if x.strip())))
                              for b in blocks)
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

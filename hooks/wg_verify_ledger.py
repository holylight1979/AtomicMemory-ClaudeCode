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
from wg_lazy_re import lazy_re  # 模組層樣式第一次用到才編譯（HOOK_IMPORT_ON_USE）

from wg_core import CLAUDE_DIR, WORKFLOW_DIR, find_vcs_root, find_vcs_root_ex, resolve_project_root
from wg_release_rules import (canon_path, cc_config_dirs, is_git_launcher_source, is_session_scratch,
                              claim_is_modifier, excluded_region, gone_verdict, in_turn, moved_copy_candidates,
                              owed_after_last_case, user_turn, Verdict,
                              format_hit, green_after_edit_verdict, cmd_names_file, comment_only_change, comment_only_verdict,
                              committed_refs, content_equals_committed, is_temp_path, temp_roots, norm_temp_path, vcs_unreadable_verdict,
                              MOVE_TOOL, move_dir_verdict, collapse_move_chain, split_blocking,
                              parse_claim_dispositions, claim_disposition_verdict, names_item, is_generic_name, is_claim_line)
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
DEFAULT_SENTINEL_RE: Pattern = lazy_re(
    r"^(?P<name>[A-Z][A-Z0-9_]*)_CHECK[ \t]+(?P<verdict>PASS|FAIL|DONE)\b(?P<kv>(?:[ \t]+\w+=\S+)*)", re.MULTILINE
)
# 量測類（rules/coding-style.md 自檢：`<NAME> DONE k=v k=v`）；數字是尺不是判決。k=v 只收同一行（下一行的 exit=0 不是它的）
DEFAULT_DONE_RE: Pattern = lazy_re(
    r"^(?P<name>[A-Z][A-Z0-9_]*)[ \t]+DONE\b(?P<kv>(?:[ \t]+\w+=\S+)*)[ \t\r]*$", re.MULTILINE   # 行尾可帶 \r（CRLF 輸出）
)
_EXIT_CODE_RE = lazy_re(r"^(?:Error:\s*)?Exit code (\d+)\b", re.MULTILINE)
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


_STAT_RE = lazy_re(r"\b(\d+) ([a-z]+)\b")          # 統計行的「數字 狀態詞」組：5 passed, 2 skipped, 1 xfailed


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
    """輸出文字 → [{name, verdict, line, kv[, n]}]；預設兩個 regex（_CHECK 與量測 DONE）＋ config 規則；同名同結論同字的行只記一筆，
    出現在兩個以上不同的行才加 n＝行數（迴圈跑三次印三行一樣的 PASS → n=3；同一行被兩個 regex 認到不重算）；讀的人用 get("n") or 1。
    反例：小寫 `x_check pass`、散文「測試通過」不命中。"""
    text = text or ""
    found: List[Dict[str, Any]] = []
    seen: Dict[Tuple[str, str, str], Tuple[Dict[str, Any], set]] = {}

    def _add(name: str, verdict: str, m: "re.Match", kv: Dict[str, str]) -> None:
        line = _line_of(text, m)
        key = (name, verdict, line)
        at = text.rfind("\n", 0, m.start()) + 1          # 這一行的開頭位置：分得出不同行、同一行
        if key in seen:
            rec, rows = seen[key]
            rows.add(at)
            if len(rows) > 1:
                rec["n"] = len(rows)
            return
        rec = {"name": name, "verdict": verdict, "line": line[:200], "kv": kv}
        seen[key] = (rec, {at})
        found.append(rec)

    for m in DEFAULT_SENTINEL_RE.finditer(text):
        _add(m.group("name") + "_CHECK", m.group("verdict"), m, _kv(m.group("kv")))
    for m in DEFAULT_DONE_RE.finditer(text):
        name = m.group("name")
        if name.endswith("_CHECK"):
            continue      # 已由上一個 regex 收
        _add(name, "DONE", m, _kv(m.group("kv")))
    for rule in rules or []:
        for m in rule["re"].finditer(text):
            raw = m.groupdict().get("verdict") or m.group(0)
            verdict = _map_verdict(raw, rule["verdict_map"], rule.get("pytest_summary", False))
            if not verdict:
                continue
            name = rule["name"] or m.groupdict().get("name") or "CUSTOM"
            _add(name, verdict, m, {})
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
_CLAUSE_SPLIT_RE = lazy_re(r"[，；,;。！!\n]+|但|不過|而|然而|只是|可是")
# 第三方主語只在「第三方名詞是子句開頭主語（子句前 4 字內）」且「宣稱詞前沒有 我／本／已」時才算轉述
_THIRD_PARTY_HEAD_RE = lazy_re(
    r"^[^，。；！？\n]{0,4}?(?:使用者|對方|同事|codex|它|他|她|log|輸出|顯示)", re.IGNORECASE
)
_OWN_MARK_RE = lazy_re(r"[我本已]")


def _third_party_said(head: str) -> bool:
    """head＝子句裡宣稱詞之前的文字。第三方在子句開頭且沒有「我／本／已」→ 轉述。"""
    return bool(_THIRD_PARTY_HEAD_RE.search(head)) and not _OWN_MARK_RE.search(head)


def _claims(text: str, kind: str, phrases: Optional[Dict[str, Pattern]] = None) -> bool:
    """逐子句判：子句命中 <kind> 詞、同子句無 <kind>_exclude 詞（否定／疑問只取消同子句；轉折詞後另起子句）、
    不是第三方轉述（第三方名詞在子句開頭且宣稱詞前沒有我／本／已）；引號／code span 內容先剝掉（引用閘文字不算宣稱）；
    宣稱詞後面直接接「的＋名詞」（修好的 X）是形容詞用法，不算（規則 CLAIM_MODIFIER_NOT_OWN），同子句後面另有宣稱照算。
    宣稱行（「宣稱｜修好：…」）是對閘的回答，整行先拿掉（規則 CLAIM_CONDITIONAL_NOT_CLAIM）；講以後的條件句由詞表的 exclude 排除。"""
    if not text:
        return False
    ph = phrases or CLAIM_RES
    pos, neg = ph[kind], ph[f"{kind}_exclude"]
    text = "\n".join(ln for ln in text[-3000:].splitlines() if not is_claim_line(ln))
    for clause in _CLAUSE_SPLIT_RE.split(strip_quoted_spans(text)):
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


_CD_RE = lazy_re(r"(?:^|[\s;&|(])(?:cd|pushd|popd|set-location|push-location|pop-location|sl|chdir)(?:\s|$)",
                    re.IGNORECASE)
LEGACY_CMD_CAP = 200          # 升級前的 state 收據 cmd 只存前 200 字
_ARG_SENTINEL_RE = lazy_re(r"_CHECK\s+(?:PASS|FAIL|DONE)|\w\s+DONE(?!\w)")    # 參數裡的哨兵字樣（不要求行首與名字）
_ESC_RE = lazy_re(r"\\(x[0-9A-Fa-f]{1,2}|u[0-9A-Fa-f]{4}|0?[0-7]{1,3}|[abefnrtv])")
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
    return receipt                                                # 換目錄不整筆作廢（RECEIPT_NO_FORGERY_CHECK）；量哪棵樹由 _in_tree 判


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


_SCOPED_FLAGS_RE = lazy_re(r"\(\?([aiLmsux]*)(?:-([imsx]*))?:")


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


_VAR_REF_RE = lazy_re(r"\$(?:\{[^}]*\}|[A-Za-z_][\w:]*|[0-9@*#?$!-])")


def _cwd_of(receipt: Dict[str, Any]) -> str:
    """收據的指令是從哪裡跑的（相對路徑照它解析）：cwd，沒有才用 project_root。"""
    return str(receipt.get("cwd") or receipt.get("project_root") or "")


def _in_tree(receipt: Dict[str, Any]) -> bool:
    """跑程式的指令沒有指到收據根以外（`python ../live/run_verify.py`、`python C:\\…\\.claude\\run_verify.py`、`../live/verify.sh`、
    `pytest C:/live/tests` 量的都是別棵樹；相對路徑照 cwd 解析）。收據沒根資訊 → 不比（同 _root_ok）。"""
    root = str(receipt.get("project_root") or receipt.get("cwd") or "")
    return not _self_receipt.outside_paths(str(receipt.get("cmd") or ""), _shell_of(receipt), root, _cwd_of(receipt))


def _clean(receipt: Dict[str, Any]) -> bool:
    """收據的指令能當一般證據（對帳 (a) 提到改檔、(b) 量了、根層 worktree 的 pytest DONE）：完整、記了啟動環境、沒指到收據根以外。
    跑程式的那幾段啟動時沒有縮範圍的環境設定（PYTEST_ADDOPTS、PYTHONOPTIMIZE…：跑的是子集）。不查語法白名單、指令形狀與指令裡
    寫的哨兵字樣（規則 RECEIPT_NO_FORGERY_CHECK：不防偽造）。"""
    raw, sh = str(receipt.get("cmd") or ""), _shell_of(receipt)
    return _usable(receipt) and _in_tree(receipt) and not _self_receipt.program_scope_env(raw, sh, _env_of(receipt))


def _ruler_ran(measure_cmd: str, receipt: Dict[str, Any], part_root: str = "") -> bool:
    """收據跑了表上這把尺（match_span，依收據的 shell 解析；腳本照路徑認：收據照它的 cwd、量尺照部位根 part_root，
    沒給部位根就共用收據的；有效環境從收據記下的繼承環境起算）；指令要完整、記了啟動環境、沒指到收據根以外，而且量尺片段以外
    沒有任何字寫了哨兵字樣。"""
    raw, sh = str(receipt.get("cmd") or ""), _shell_of(receipt)
    if not str(measure_cmd).strip() or not _usable(receipt):
        return False
    span = _self_receipt.match_span(str(measure_cmd), raw, sh, _cwd_of(receipt), str(part_root or ""), _env_of(receipt))
    return span is not None and _in_tree(receipt)


_RULER_FORM = ("量尺前面只准 `cd <絕對路徑> &&` 與環境設定（`X=1`、`export X=1`、`$env:X=\"1\";`、`$x = '字面值';`；"
               "set、unset、pushd、帶 $ 的值、PS4 這類讓 shell 自己印字的變數都不算），"
               "後面只准 `| tail` 或 `| Select-Object -Last N`（多段量尺不准，管線會蓋掉最後一段的 exit）；要和別的測試串在一起，就用 && 把跑程式的指令接在量尺前面、"
               "量尺放最後、後面不接過濾（例：`python -m pytest -q x.py && 量尺`）；否則請照表上原字串單獨跑。")


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
        if any(_ruler_ran(mc, r) for mc in rulers):
            return ""
        for mc in rulers:         # 結構上就是量尺、只差環境，而且量尺自己的字以外沒寫哨兵：講真正原因
            mis = _self_receipt.ruler_env_mismatch(mc, raw, sh, _cwd_of(r), env=env)
            if mis:
                return f"這條指令 {head} {_scope_env_why(mis[1], env)}"
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
        if outside:
            return (f"這條指令 {head} 指到收據根以外的路徑（{'、'.join(outside[:3])}），量的不是這棵樹；"
                    "請在專案根照表上原字串跑。")
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
    raw = str(r.get("cmd") or "")
    words = evidence_words(raw, _shell_of(r)) or raw.split()
    return " ".join(_norm_path(" ".join(words)).split())


def _ruler_any(receipt: Dict[str, Any], measure_cmds: Iterable[str]) -> bool:
    """收據跑了其中一把部位量尺（_ruler_ran）：聲稱驗到該部位全部改檔。"""
    return any(_ruler_ran(mc, receipt) for mc in measure_cmds or [])


def _whole_run(receipt: Dict[str, Any]) -> bool:
    """整體驗證：執行根自己的 run_verify.py（照完整路徑身分）或不縮範圍的 pytest；只認白名單語法、前面只准前置設定、
    後面只准尾端過濾、沒指到收據根以外、整條指令沒寫哨兵字樣。涵蓋範圍見 _in_exec_root。"""
    raw, sh = str(receipt.get("cmd") or ""), _shell_of(receipt)
    return (_usable(receipt) and is_whole_run(raw, sh, _cwd_of(receipt), _env_of(receipt)) and _in_tree(receipt))


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


def copied_glob_source(path: str) -> bool:
    """搬目錄規則（MOVE_CODE_DIR_NEEDS_SCAN_AND_SAMPLE）的「來源還在＝複製」：來源寫成沒展開的萬用字元（`hooks/*.py`）時字面路徑
    不存在，要展開來看；還有符合的檔＝複製、不是搬。沒有萬用字元的來源由呼叫端照 exists() 判。"""
    import glob
    return any(ch in str(path) for ch in "*?[") and bool(glob.glob(str(path)))


def is_code_file(path: str, code_exts: Iterable[str]) -> bool:
    """副檔名在 code_exts 裡；沒有副檔名的檔看第一行是不是 `#!`（腳本）。讀不到就不算。"""
    low = str(path).lower()
    if any(low.endswith(str(e).lower()) for e in code_exts):
        return True
    p = Path(str(path))
    if p.suffix or p.name.startswith("."):
        return False
    try:
        with open(p, "rb") as fh:
            return fh.read(2) == b"#!"
    except OSError:
        return False


def is_verify_case(path: str, globs: Iterable[str], root: Optional[str] = None) -> bool:
    """path 符合 verify_case_globs 嗎。比對前轉成相對 root 的路徑（前面補一個 `/`，根目錄下的 test_x.py 也比得到）：
    glob 要認的是專案內的 verify/、tests/ 與檔名，專案根所在目錄的名字（`C:\\latest\\proj`）不能參與比對。
    root 沒給或 path 不在 root 底下 → 用絕對路徑（呼叫端負責告知，見 case_debt）。
    檔名樣式（`**/` 後面不再有 `/`，如 `**/test_*`）只比檔名：fnmatch 的 `*` 會跨 `/`，拿整條路徑比會把 test_runner/engine.py
    這種目錄名也當成測試檔名。"""
    full, base = _norm_path(path), _norm_path(root or "")
    norm = full[len(base):] if base and full.startswith(base + "/") else full
    name = norm.rsplit("/", 1)[-1]
    for g in globs:
        g = str(g).replace("\\", "/").lower()
        tail = g[3:] if g.startswith("**/") else ""
        if tail and "/" not in tail and tail != "**":
            if fnmatch.fnmatch(name, tail):
                return True
            continue
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


def aec_evidence_autofill(j: Any, receipts_non_empty: bool, ledger: str,
                          _exists: Callable[[str], bool] = os.path.exists) -> str:
    """(j) 自動帶入：本 session 有收據、j 空／「無」、帳本檔在 → 回帳本絕對路徑；其餘回原 j（模型填了別的路徑就用模型填的）。
    帳本在資料根（WG_CLAUDE_DIR）底下，跟專案 cwd 不同根，模型猜不到，所以由系統填。
    MIRROR: tools/workflow-guardian-mcp/lib/anti-evasion.js aecEvidenceAutofill；keep in sync。"""
    if receipts_non_empty and aec_blank(j) and _exists(ledger):
        return ledger
    return str("" if j is None else j)


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
                  ".mm", ".scala", ".dart", ".vue", ".svelte", ".ps1", ".psm1", ".bat", ".cmd", ".sh", ".bash", ".sql", ".gd",
                  ".shader", ".hlsl", ".glsl"],
    # 案例檔的定義：測試目錄或測試檔名慣例（不用 `**/*test*`：它把 backtest_acceptance.py、latest_build.py 這類產品檔也當案例，改了不欠補案例）
    "verify_case_globs": ["**/verify/**", "**/tests/**", "**/test/**", "**/__tests__/**", "**/*.tests/**",
                          "**/test_*", "**/*_test.*", "**/*_tests.*", "**/*.test.*", "**/*.spec.*", "**/test.*", "**/tests.*",
                          "**/conftest.py"],
}


def reconcile_cfg(config: Dict[str, Any]) -> Dict[str, Any]:
    """預設 < config.json 的 reconcile_gate 段。code_exts 是預設與設定的聯集（設定只能加不能減：程式檔不能被設定踢出寫碼類）。"""
    c = dict(RECONCILE_DEFAULTS)
    sec = (config or {}).get("reconcile_gate")
    if isinstance(sec, dict):
        c.update(sec)
        extra = sec.get("code_exts")
        if isinstance(extra, list):
            c["code_exts"] = list(dict.fromkeys(RECONCILE_DEFAULTS["code_exts"] + [str(e) for e in extra]))
        else:
            c["code_exts"] = list(RECONCILE_DEFAULTS["code_exts"])
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


def is_excluded(path: str, cfg: Dict[str, Any], root: Optional[str], ignored: Optional[set] = None) -> bool:
    """規則 EXCLUDED_REGION（wg_release_rules.excluded_region）：path 屬部位表類別 knowledge 的部位（文件、記憶、信件匣），
    或被 .gitignore 忽略／屬執行期資料 → 不是本專案的程式也不是它的案例。事實（路徑屬哪類部位、git 忽略沒）在這裡查，
    規則判排不排除。ignored＝呼叫端一次查好的被忽略路徑集合（gitignored_paths）；沒給就只查這一個。
    拿不到根、不在根底下、沒有部位表又沒被忽略、表讀不到、判法載入失敗 → 不排除（照算）。cfg 不用，留著與呼叫點同簽名。
    session 暫存區的一次性腳本（規則 SESSION_SCRATCH_NOT_CODE，session_scratch）不看根，一律排除。"""
    if session_scratch(path) or git_launcher(path):
        return True
    if not root:
        return False
    if ignored is None:
        ignored = gitignored_paths(root, [path])
    return excluded_region(path, root, _part_kind(path, root), path in ignored)


LAUNCHER_DIR = WORKFLOW_DIR / "git-launchers"     # 規則 LAUNCHER_NOT_CODE 的標記：一個啟動器一個檔（檔名＝canon 路徑雜湊）


def _launcher_marker(path: str) -> Path:
    return LAUNCHER_DIR / f"{hashlib.sha1(canon_path(path).encode('utf-8')).hexdigest()[:20]}.json"


def note_git_launcher(path: str, run: Callable[..., Any] = subprocess.run) -> Optional[bool]:
    """規則 LAUNCHER_NOT_CODE 的事實端：PostToolUse 寫完 .py 時呼叫。內容只跑 git（is_git_launcher_source）、放在版控根、
    git 沒追蹤 → 記標記、回 True；不合 → 拿掉舊標記、回 False；不是 .py、檔已不在（刪掉了）→ 標記不動、回 None。
    查 git 失敗當成有追蹤（照算程式）並浮 stderr。"""
    p = Path(str(path))
    if p.suffix.lower() != ".py":
        return None
    try:
        src = p.read_text(encoding="utf-8")
    except OSError:
        return None
    ok = is_git_launcher_source(src)
    if ok:
        vcs = find_vcs_root(p.parent)
        ok = bool(vcs and vcs[0] == "git" and canon_path(str(vcs[1])) == canon_path(str(p.parent)))
    if ok:
        try:
            r = run(["git", "-C", str(p.parent), "ls-files", "--error-unmatch", "--", p.name], capture_output=True,
                    timeout=5, creationflags=_NO_WINDOW)
            ok = r.returncode != 0
        except (OSError, subprocess.SubprocessError) as e:
            print(f"[verify_ledger] 查不到 {p.name} 有沒有進版控，當成程式照算（LAUNCHER_NOT_CODE）：{type(e).__name__}: {e}",
                  file=sys.stderr)
            ok = False
    marker = _launcher_marker(str(p))
    try:
        if ok:
            LAUNCHER_DIR.mkdir(parents=True, exist_ok=True)
            marker.write_text(json.dumps({"path": str(p), "at": time.time()}, ensure_ascii=False), encoding="utf-8",
                              newline="\n")
        else:
            marker.unlink(missing_ok=True)
    except OSError as e:
        print(f"[verify_ledger] 記不下 git 啟動器標記，{p.name} 照算程式：{type(e).__name__}: {e}", file=sys.stderr)
        return False
    return ok


def git_launcher(path: str) -> bool:
    """LAUNCHER_NOT_CODE：path 寫入時被認成一次性 git 啟動器（刪掉之後標記還在，刪除也不算改程式）。"""
    try:
        return _launcher_marker(str(path)).exists()
    except (OSError, ValueError):
        return False


def session_scratch(path: str) -> bool:
    """規則 SESSION_SCRATCH_NOT_CODE 的事實端：設定目錄與系統暫存根（temp_roots；WG_TEMP_RULES=off 時只認 jobs）兩側都展開
    8.3 短路徑（_norm_long）再交給 is_session_scratch。第二意見閘（wg_second_opinion.check）與 is_excluded 共用。"""
    import tempfile
    return is_session_scratch(_norm_long(path), [_norm_long(d) for d in cc_config_dirs()],
                              [_norm_long(r) for r in temp_roots(tempdir=tempfile.gettempdir())])


def gitignored_paths(root: str, paths: Iterable[str]) -> set:
    """被 .gitignore 忽略的路徑（規則 EXCLUDED_REGION 的事實）：與 OverviewHub 共用 wg_overview._gitignored_set，一次查一批，
    回傳的是傳進去的原字串。不在 git、逾時、出錯回空集合（當不忽略，照算程式）；判法載入失敗 stderr 說一聲。"""
    try:
        from wg_overview import _gitignored_set
        return _gitignored_set(Path(root), list(paths))
    except Exception as e:  # noqa: BLE001
        print(f"[verify_ledger] 查不了 {root} 的 git 忽略規則，照算程式：{type(e).__name__}: {e}", file=sys.stderr)
        return set()


def _part_kind(path: str, root: str) -> Optional[str]:
    """路徑屬部位表哪一類部位（lib/overview_hub.path_kind，與 OverviewHub 同一份判法；部位表找到 root 那層為止）；
    沒有部位表回 None。判法載入失敗 → stderr 說一聲、回 None（不排除）。"""
    lib_dir = str(Path(__file__).resolve().parents[1] / "lib")
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)
    try:
        from overview_hub import path_kind
        return path_kind(str(path), Path(root))
    except Exception as e:  # noqa: BLE001
        print(f"[verify_ledger] 判不出 {path} 的部位類別，照寫碼部位算：{type(e).__name__}: {e}", file=sys.stderr)
        return None


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
                        verdicts: Optional[Dict[str, Verdict]] = None,
                        last_sha: Optional[Dict[str, Optional[str]]] = None) -> List[str]:
    """Stop 當下已不存在的改過程式檔，查事實交給 wg_release_rules.gone_verdict 判欠不欠，回不欠的那些：
    - 所在版控根：不在任何版控根內 → GONE_OUTSIDE_VCS（不欠）；svn → GONE_UNVERIFIABLE（照欠）
    - git 根：同根 status 新出現的程式檔（未追蹤、新增、改名、複製）＋本 session 在這個根的提交新加進來的程式檔
      （committed_new：PostToolUse 看到 commit 時用 head_new_code 記的），交 moved_copy_candidates 挑出可能是它副本的
      （檔名相同、或內容等於它最後一次寫入時的雜湊 last_sha[canon_path]，修改紀錄的 sha 欄）。有副本 → MOVED_NEW_CODE_SEEN（照欠）；
      沒有 → 刪除、不欠。搬走（mv、git mv、Rename-Item、整個目錄改名，搬完又 commit 也一樣）的程式一定會在其中一處以新路徑、
      原內容出現；不追搬檔寫法，只看結果。git 失敗或逾時、預算用完 → GONE_UNVERIFIABLE（照欠）。
      提交紀錄裡的新程式檔現在已經不在磁碟上（之後又改名、刪掉）就不當副本候選：它自己也不在了，不會是這支搬去的地方
      （否則內容雜湊算不出來＝判不出，任何刪掉的檔都會被它拖成「可能搬走」）。
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
        if left < _GIT_MIN_S:                                         # 提交裡有新檔也要查 status：副本可能只在 status 裡
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
                new_code = list(dict.fromkeys(new_code + [n for n in appeared if is_code_file(n, exts)]))
        new_code = [n for n in new_code if (Path(root) / n).exists()]   # 自己也不在了的新檔不會是它搬去的地方
        shas: Dict[str, Optional[str]] = {}
        for p in ps:
            sha = (last_sha or {}).get(canon_path(p))
            if sha and new_code and not shas:
                shas = {n: (small_content_sha(str(Path(root) / n)) if time.monotonic() < deadline else None) for n in new_code}
            seen, other = moved_copy_candidates(Path(p).name, sha, shas or dict.fromkeys(new_code))
            found[p] = gone_verdict(Path(p).name, "git", seen, failed, other)
    for v in found.values():
        print(f"[verify_ledger] {v.rule}：{v.why}（{'照欠補案例' if v.owed else '不欠補案例'}）", file=sys.stderr)
    if verdicts is not None:
        verdicts.update(found)
    return [p for p, v in found.items() if not v.owed]


def case_debt(own_mod_files: List[Dict[str, Any]], turn_seq: int, cfg: Dict[str, Any],
              root_of: Callable[[str], Optional[str]], gone: Iterable[str] = (),
              evidence: Optional[Dict[str, Verdict]] = None,
              case_check: Optional[Callable[[str], Verdict]] = None) -> List[str]:
    """補案例的義務（跨回合）：回欠補案例的程式檔；evidence 給了就填每個欠的檔的 Verdict，擋訊息照印。
    case_check 給了（驗證範圍閘開著：wg_verify_scope.case_check）→ 規則 CASE_DECLARED_FOR_CHANGE：每個改過的程式檔問它一次，
    「由哪個案例驗」看 LLM 的宣告，這裡不猜；沒給 → 退路 OWED_AFTER_LAST_CASE：每個根找「本 session 最後一次改驗證案例之後
    還改過的程式檔」（只有 Stop 當下仍存在的案例檔才算：刪除也會記一筆修改，不能拿它清帳）。
    兩條共用的事實：案例檔本身不欠；gone 裡的程式檔（vanished_code_paths 判成刪除的）不欠，搬走的照欠，量尺閘照舊看所有改檔；
    同一個檔不同寫法、同一個根不同寫法都用 canon_path 比（SAME_FILE）；屬知識類部位、或被 .gitignore 忽略／屬執行期資料的檔
    （is_excluded）不算程式，也不能拿來清帳。git 忽略事實每個根一次查一批。案例判定用相對該根的路徑；拿不到根的程式檔退回
    絕對路徑，每個路徑 stderr 一行（本函式每次 Stop 只跑一次）。修改紀錄沒有 at／seq 的 legacy entry 只在本回合改過時算
    （退路另要本回合同根沒改案例）。"""
    exts = cfg.get("code_exts") or []
    gone = {canon_path(p) for p in gone or ()}
    rooted = [(m, root_of(m["path"])) for m in own_mod_files or [] if isinstance(m, dict) and m.get("path")]
    ignored: set = set()
    for r in dict.fromkeys(r for _, r in rooted if r):
        ignored |= gitignored_paths(r, [m["path"] for m, mr in rooted if mr == r])
    by_root: Dict[str, List[Dict[str, Any]]] = {}
    for m, r in rooted:
        if not is_excluded(m["path"], cfg, r, ignored):
            by_root.setdefault(canon_path(r) if r else "", []).append(m)               # 同根比較用 canon_path（SAME_FILE）
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
            t = m.get("last_turn_seq", m.get("turn_seq"))
            this_turn = t is not None and int(t) == int(turn_seq)
            if case_check is not None:
                v: Optional[Verdict] = case_check(p) if _has_time(m) or this_turn else None
            elif _has_time(m) and (last_case is None or _mod_after(m, last_case)) or (
                    not _has_time(m) and this_turn and not case_this_turn):
                v = owed_after_last_case(Path(p).name, Path(last_case["path"]).name if last_case else None)
            else:
                v = None
            if v is not None and v.owed:
                owed.append(p)
                owed_keys.add(k)
                if evidence is not None:
                    evidence[p] = v
    return owed


def _content_sha(path: str) -> Optional[str]:
    """檔案內容的 sha256；不存在或讀不到回 None（不存在也是一種內容狀態：commit 時不在、現在也不在＝一樣）。"""
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


SHA_SIZE_CAP = 2 * 1024 * 1024    # 修改紀錄 sha 欄與副本比對只算這麼大以內的檔


def small_content_sha(path: str) -> Optional[str]:
    """修改紀錄 sha 欄與 MOVED_NEW_CODE_SEEN 副本比對用的內容雜湊：超過 SHA_SIZE_CAP、不存在、讀不到回 None
    （寫入端不記、比對端當判不出：已不存在的檔沒有紀錄就全算副本，新檔讀不到也算副本，都是照欠）。"""
    try:
        if os.path.getsize(path) > SHA_SIZE_CAP:
            return None
    except OSError:
        return None
    return _content_sha(path)


def commit_snapshot(mods: List[Dict[str, Any]], turn_seq: int, cfg: Dict[str, Any],
                    root_of: Optional[Callable[[str], Optional[str]]] = None, prev: Any = None,
                    session_paths: Optional[Iterable[str]] = None,
                    case_check: Optional[Callable[[str], Verdict]] = None) -> Dict[str, Any]:
    """commit 那一刻（PostToolUse 看到 git／svn commit）本 session 改過的每個檔的內容雜湊，與當時不欠案例的程式檔
    （case_debt 照當時的修改紀錄與案例宣告算；case_check 與 Stop 同一份，驗證範圍閘關掉時不給）。
    Stop 拿它判 commit 之後的改動有沒有回到這個不欠案例的狀態（committed_settled_paths）。
    prev＝上一份快照：照修改時間算是欠、但對 prev 已經成立「回到不欠案例的狀態」的程式檔（committed_settled_paths；session_paths
    是同根要一起比的改檔，沒給就用 mods），新快照照算不欠：反證還原後又 commit（例：--amend 只改訊息），有效的豁免不被蓋掉。
    files／settled 的鍵是 canon_path（keys="canon"）：同一個檔被不同寫法記下也是同一筆；任一種寫法欠案例，這個檔就不算不欠。"""
    root_of = root_of or file_root_of
    paths = list(dict.fromkeys(m["path"] for m in mods or [] if isinstance(m, dict) and m.get("path")))
    owed = set(case_debt(mods, turn_seq, cfg, root_of, case_check=case_check))
    if owed and prev:
        owed -= set(committed_settled_paths(prev, owed, paths if session_paths is None else session_paths, root_of, cfg=cfg))
    owed_keys = {canon_path(p) for p in owed}
    exts = cfg.get("code_exts") or []
    settled = {canon_path(p) for p in paths
               if is_code_file(p, exts) and not is_case_file(p, cfg, root_of(p)) and canon_path(p) not in owed_keys}
    return {"turn": int(turn_seq), "keys": "canon", "files": {canon_path(p): _content_sha(p) for p in paths},
            "settled": sorted(settled)}


def exemption_peers(paths: Iterable[str], cfg: Optional[Dict[str, Any]] = None) -> List[str]:
    """「內容回到某狀態」的豁免（SNAPSHOT_SETTLED、NET_UNCHANGED、COMMENT_ONLY_CHANGE）要一起比的改檔：只留程式檔（案例檔也是
    程式檔，見 is_case_file）。規則 EXEMPTION_PEERS_CODE_ONLY：文件、紀錄檔、設定、資料改了或正被別的 session 改著，不影響程式檔
    欠不欠案例，不拿來擋豁免；程式檔或案例檔本身沒回到那個狀態照擋（分不出是誰改的）。cfg 沒給用預設的 code_exts。"""
    exts = (cfg if cfg is not None else reconcile_cfg({})).get("code_exts") or []
    return [p for p in dict.fromkeys(str(q) for q in paths or []) if is_code_file(p, exts)]


def committed_settled_paths(snapshot: Any, owed: Iterable[str], session_paths: Iterable[str],
                            root_of: Optional[Callable[[str], Optional[str]]] = None, deadline: Optional[float] = None,
                            _run: Optional[Callable[..., Any]] = None, cfg: Optional[Dict[str, Any]] = None) -> List[str]:
    """欠案例的程式檔裡，commit 那一刻（commit_snapshot）它不欠案例、同根本 session 改過的每個程式檔（主 session＋所有子代理；
    案例檔也算，文件等不算：exemption_peers）現在的內容都和那一刻一樣、而且這些檔 git status 都乾淨（_root_clean，和
    net_unchanged_paths 同一個條件：只把工作樹改回去、暫存區還留著新內容也算有差）→ 回這些檔：commit 之後做反證，
    把程式或案例退回舊版又還原，補案例的義務不重算。
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
    every = exemption_peers(session_paths, cfg)
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


def _dirty_paths(root: Path, every: List[str], deadline: float, timeout_s: float,
                 run: Callable[..., Any]) -> Optional[set]:
    """這個 git 根裡 every 哪些 `git status --ignored --untracked-files=all` 有輸出（canon_path 集合）：改動、已暫存（只把工作樹
    改回去、暫存區還留著新內容也算）、刪除、未追蹤、被忽略都算有差。路徑太長、預算不足、git 失敗或逾時 → None（呼叫端照算改了），
    stderr 說哪個根。"""
    spec_all = [str(x).replace("\\", "/") for x in every]
    spec_len = sum(len(s) + 1 for s in spec_all)
    if spec_len > _GIT_SPEC_CAP:
        print(f"[verify_ledger] {root} 這次改過的檔路徑合計 {spec_len} 字（{len(spec_all)} 個檔），超過命令列可帶的 "
              f"{_GIT_SPEC_CAP} 字，查不了 git，這些改檔照算改了", file=sys.stderr)
        return None
    raw = _git_out(root, ["status", "--porcelain=v1", "-z", "--ignored", "--untracked-files=all", "--", *spec_all],
                   deadline, timeout_s, run)
    if raw is None:
        return None
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
    return changed


def _root_clean(root: Path, paths: List[str], every: List[str], deadline: float, timeout_s: float,
                run: Callable[..., Any]) -> bool:
    """「內容回到某狀態」的豁免共用的 git 條件（committed_settled_paths；net_unchanged_paths 逐檔判，也用 _dirty_paths）：
    這個 git 根裡要一起比的改檔（every，exemption_peers 篩過的程式檔）git status 都沒有輸出。paths＝要豁免的那幾個：
    它們本身乾淨、卻被同根其他程式檔拖住時 stderr 說一聲。查不了 → False（照算改了）。"""
    changed = _dirty_paths(root, every, deadline, timeout_s, run)
    if changed is None:
        return False
    dirty = [p for p in every if canon_path(p) in changed]
    if dirty and any(canon_path(p) not in changed for p in paths):
        print(f"[verify_ledger] {root} 還有本 session 改過、跟 HEAD 不同的程式檔（{'、'.join(Path(p).name for p in dirty[:3])}），"
              "這個根的改檔一律照算改了", file=sys.stderr)
    return not dirty


def net_unchanged_paths(mods: List[Dict[str, Any]], last_commit_turn: Any = None, timeout_s: float = 3.0,
                        _run: Optional[Callable[..., Any]] = None, session_paths: Optional[Iterable[str]] = None,
                        budget_s: Optional[float] = None, deadline: Optional[float] = None,
                        cfg: Optional[Dict[str, Any]] = None) -> List[str]:
    """改過、但現在跟 HEAD 一模一樣的檔（例：反證時暫改、又 git checkout 還原）→ 回這些檔的 path（照 modified_files 的寫法）。
    要同時成立：git 追蹤著它、它自己 git status 沒有輸出、本 session 從第一次改它那回合起沒跑過 commit（last_commit_turn ≥ 該檔
    turn_seq：工作樹乾淨可能是把改動提交了，照算改了），而且同一個 git 根裡本 session 改過的每個程式檔（案例檔也算，文件等不算：
    exemption_peers；session_paths＝主 session 與所有子代理的改檔，沒給就只看 mods）git status 都沒有輸出：只把程式還原、
    案例還留著舊版，這個根就一個都不剔除。
    時間：整支共用一個截止點（deadline；沒給就從現在起算 budget_s，預設 GIT_BUDGET_S 秒），每個 git 子行程只拿剩餘預算
    （最多 timeout_s）；預算不足沒查到的根照算改了，stderr 印根路徑。判不出來（不在 git 工作區、修改紀錄沒有回合、git 失敗或逾時）
    → 不回，照算改了（不放寬）。每個根最多兩次 git（status 有差就不再查 ls-files）。"""
    run = _run or subprocess.run
    deadline = git_deadline(budget_s) if deadline is None else deadline
    try:
        last = int(last_commit_turn) if last_commit_turn is not None else None
    except (TypeError, ValueError):
        return []
    by_root: Dict[str, Tuple[Path, List[str], List[str]]] = {}     # 鍵 → (根, 可剔除的改檔, 同根本 session 改過的程式檔)
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
    for p in exemption_peers([*(session_paths or []), *(m["path"] for m in mods or [] if isinstance(m, dict) and m.get("path"))],
                             cfg):
        hit = _git_root_of(p)
        if hit and hit[0] in by_root and p not in by_root[hit[0]][2]:
            by_root[hit[0]][2].append(p)
    out: List[str] = []
    for key, (root, paths, peers) in by_root.items():
        changed = _dirty_paths(root, list(dict.fromkeys([*paths, *peers])), deadline, timeout_s, run)
        if changed is None:
            continue
        clean = [p for p in paths if canon_path(p) not in changed]
        dragged = [q for q in peers if canon_path(q) in changed]
        if dragged:
            if clean:
                print(f"[verify_ledger] {root} 還有本 session 改過、跟 HEAD 不同的程式檔（{'、'.join(Path(q).name for q in dragged[:3])}），"
                      "這個根的改檔一律照算改了", file=sys.stderr)
            continue
        if not clean:
            continue
        tracked = _git_out(root, ["ls-files", "-z", "--full-name", "--", *(str(x).replace("\\", "/") for x in clean)],
                           deadline, timeout_s, run)
        if tracked is None:
            continue
        known = {canon_path(f"{key}/{f}") for f in tracked.decode("utf-8", "replace").split("\0") if f}
        out += [p for p in clean if canon_path(p) in known]
    return out


# ─── 045：已提交版本的事實（CONTENT_EQUALS_COMMITTED／COMMENT_ONLY_CHANGE／RED_WHILE_REVERTED 共用）────────
_REF_CANDIDATES = ("HEAD", "MERGE_HEAD", "main", "master")
REF_BUDGET_S = 3.5       # 每個根典型 3 次 git（cat-file --batch-check、hash-object、cat-file --batch）；負載下每次可達 0.7 秒


def _run_git(root: Path, args: List[str], timeout_s: float, _run: Optional[Callable[..., Any]] = None,
             stdin: Optional[bytes] = None, raw: bool = False) -> Any:
    """跑一次 git，回 stdout（utf-8 字串；raw＝原位元組）；失敗、非零、逾時 → None（stderr 一行）。stdin 給 cat-file --batch 這類。"""
    run = _run or subprocess.run
    try:
        r = run(["git", "-c", "core.quotepath=false", "-C", str(root), *args], capture_output=True,
                timeout=max(0.1, timeout_s), creationflags=_NO_WINDOW, **({"input": stdin} if stdin is not None else {}))
    except (OSError, subprocess.SubprocessError) as e:
        print(f"[verify_ledger] 在 {root} 跑 git {args[0]} 失敗：{type(e).__name__}: {e}", file=sys.stderr)
        return None
    if r.returncode != 0:
        return None
    return r.stdout if raw else r.stdout.decode("utf-8", "replace")


def ref_blob_facts(root: Path, rel_paths: List[str], deadline: Optional[float] = None,
                   _run: Optional[Callable[..., Any]] = None) -> Dict[str, Any]:
    """一個 git 根的已提交事實：{"commits": {ref: sha}, "blobs": {ref: {rel: blob}}, "current": {rel: blob}}。
    ref 只看 HEAD／MERGE_HEAD／main／master（存在的才列）；ref 與每個 ref:檔 的 blob 一支 `git cat-file --batch-check` 問完
    （不再每個 ref 一支 ls-tree）；current 用 `git hash-object`（套 clean filter，CRLF 不影響）。預算到就少查（缺的 ref 當拿不到，
    呼叫端照算改了）。"""
    deadline = deadline if deadline is not None else time.monotonic() + REF_BUDGET_S
    out: Dict[str, Any] = {"commits": {}, "blobs": {}, "current": {}}
    if not rel_paths:
        return out
    left = deadline - time.monotonic()
    if left < _GIT_MIN_S:
        return out
    asks = [(ref, None) for ref in _REF_CANDIDATES] + [(ref, rel) for ref in _REF_CANDIDATES for rel in rel_paths]
    text = _run_git(root, ["cat-file", "--batch-check"], left, _run,
                    stdin="".join(f"{ref}:{rel}\n" if rel else f"{ref}\n" for ref, rel in asks).encode("utf-8"))
    if text is None:
        return out
    for (ref, rel), line in zip(asks, text.splitlines()):
        cols = line.split()
        if len(cols) != 3 or cols[1] == "missing":
            continue
        if rel is None and cols[1] == "commit":
            out["commits"][ref] = cols[0]
        elif rel is not None and cols[1] == "blob" and ref in out["commits"]:
            out["blobs"].setdefault(ref, {})[rel.replace("\\", "/")] = cols[0]
    for ref in out["commits"]:
        out["blobs"].setdefault(ref, {})
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


def _blob_texts(root: Path, shas: Iterable[str], deadline: float, _run: Optional[Callable[..., Any]]) -> Dict[str, str]:
    """一支 `git cat-file --batch` 取多個 blob 的內容 {sha: 文字}（不再每檔一支 git show）；預算不夠、git 失敗 → 空（呼叫端當拿不到）。"""
    shas = list(dict.fromkeys(s for s in shas if s))
    left = deadline - time.monotonic()
    if not shas or left < _GIT_MIN_S:
        return {}
    data = _run_git(root, ["cat-file", "--batch"], left, _run, stdin="".join(f"{s}\n" for s in shas).encode("ascii"), raw=True)
    out: Dict[str, str] = {}
    pos = 0
    while data and pos < len(data):
        nl = data.find(b"\n", pos)
        if nl < 0:
            break
        head = data[pos:nl].decode("ascii", "replace").split()
        pos = nl + 1
        if len(head) != 3 or not head[2].isdigit():
            continue                                        # "<sha> missing"
        size = int(head[2])
        out[head[0]] = data[pos:pos + size].decode("utf-8", "replace")
        pos += size + 1
    return out


def _head_after_own(root: Path, own: List[str], facts: Dict[str, Any], rel_list: List[str], deadline: float,
                    _run: Optional[Callable[..., Any]]) -> bool:
    """CONTENT_EQUALS_COMMITTED 的 HEAD 例外的事實：HEAD 不是本 session 的提交、本 session 最後一次提交是它的祖先（別人接著做的，
    例如另一個 session 或人把 main 合進這個分支），而且同根本 session 改過的每個檔現在都等於 HEAD（不在版控也不在 HEAD 的兩邊都沒有也算）。
    判不了（沒有自己的提交、預算到、git 失敗）→ False，照原規則不算 HEAD。"""
    head = str(facts["commits"].get("HEAD") or "")
    if not own or not head or head in {str(s) for s in own}:
        return False
    head_blobs = facts["blobs"].get("HEAD") or {}
    if any(facts["current"].get(r) != head_blobs.get(r) for r in rel_list):
        return False
    left = deadline - time.monotonic()
    if left < _GIT_MIN_S:
        return False
    return _run_git(root, ["merge-base", "--is-ancestor", str(own[-1]), head], left, _run) is not None


def committed_equal_paths(mods: List[Dict[str, Any]], cfg: Dict[str, Any], last_commit_turn: Any = None,
                          own_commit_shas: Optional[Dict[str, Any]] = None, budget_s: Optional[float] = None,
                          _run: Optional[Callable[..., Any]] = None,
                          session_paths: Optional[Iterable[str]] = None, deadline: Optional[float] = None) -> Dict[str, Verdict]:
    """改過的程式檔裡「不是本 session 改碼」的，回 {path: Verdict}：
    - CONTENT_EQUALS_COMMITTED：內容等於另一方已提交的版本（MERGE_HEAD／main／master；指到 HEAD 或本 session 自己提交的 commit 不算；
      HEAD 是別人接在本 session 提交之上做的、同根改檔全等於 HEAD 時 HEAD 也算，見 _head_after_own）。
    - COMMENT_ONLY_CHANGE：與 HEAD 只差註解／docstring／空白，且本 session 沒 commit 過它；同根本 session（主 session＋子代理，
      session_paths）改過的其他程式檔（案例檔也算，文件等不算：exemption_peers）也都要等於 HEAD 或只差註解。程式與案例一起
      退回舊版、只還原程式時案例還是舊的，照欠
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
    every: Dict[str, List[str]] = {}            # 根 → 同根本 session 改過的程式檔（含案例、子代理的）
    for p in exemption_peers([*(session_paths or []), *(m["path"] for m in mods or [] if isinstance(m, dict) and m.get("path"))],
                             cfg):
        hit = _git_root_of(p)
        if hit and hit[0] in by_root and p not in every.setdefault(hit[0], []):
            every[hit[0]].append(p)
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
        head_blobs = facts["blobs"].get("HEAD") or {}
        refs = committed_refs(own, facts["commits"], head_after_own=_head_after_own(root, own, facts, rel_list, deadline, _run))
        root_clean: Optional[bool] = None        # 同根其他改檔都等於 HEAD 或只差註解（只在需要時算一次）
        head_src: Optional[Dict[str, str]] = None    # HEAD 版原始碼 {blob: 文字}：同根要比註解的 .py 一次取完，取不到也不再重取

        def _comment_only(rel: str, path: str) -> Optional[bool]:
            """path 與 HEAD:rel 是否只差註解／docstring／空白；拿不到或判不了 → None。"""
            nonlocal head_src
            if not str(path).lower().endswith((".py", ".pyw")) or not head_blobs.get(rel):
                return None
            if head_src is None:
                head_src = _blob_texts(root, [head_blobs.get(r) for r in rel_list if r.lower().endswith((".py", ".pyw"))
                                              and facts["current"].get(r) != head_blobs.get(r)], deadline, _run)
            if head_blobs[rel] not in head_src:
                return None
            try:
                cur_src = Path(path).read_text(encoding="utf-8", errors="replace")
            except OSError:
                return None
            return comment_only_change(head_src[head_blobs[rel]], cur_src, path)

        def _root_head_clean(skip: str) -> bool:
            for q, qrel in rels.items():
                if q == skip:
                    continue
                if not qrel or not os.path.isfile(q):
                    return False
                if facts["current"].get(qrel) and facts["current"].get(qrel) == head_blobs.get(qrel):
                    continue
                if _comment_only(qrel, q) is not True:
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
            if _comment_only(rel, p) is not True:
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


_MOVE_ARG_RE = {k: re.compile(rf"--{k}(?:=|\s+)(\"[^\"]+\"|'[^']+'|\S+)") for k in ("old", "new", "root", "for")}
_MOVE_HITS_RE = lazy_re(r"MOVE_PATH_SCAN DONE hits=(\d+)")


def _move_tool_receipt(receipt: Dict[str, Any], sub: str) -> bool:
    """搬目錄工具的收據能不能當證據：指令完整、記了啟動環境、跑的是 move-dir-check.py <sub>、指令裡沒寫哨兵字樣。
    工具放在根層 tools/，專案 session 跑它一定指到專案根以外，所以不套 _in_tree。"""
    raw, sh = str(receipt.get("cmd") or ""), _shell_of(receipt)
    return _usable(receipt) and re.search(re.escape(MOVE_TOOL) + r"[\"']?\s+" + sub + r"(?:\s|$)", raw) is not None


def _tool_cwd(receipt: Dict[str, Any]) -> str:
    """跑搬目錄工具那一段的有效 cwd：同一條指令前面的 cd／Set-Location（沿用 pre_tool_use._vcs_segments 的換目錄解析），
    沒有就是收據的 cwd。"""
    from handlers.pre_tool_use import _resolve_run_cwd, _vcs_segments
    cwd = _cwd_of(receipt)
    segs = _vcs_segments(str(receipt.get("cmd") or ""), None, (MOVE_TOOL,), set())
    return _resolve_run_cwd(segs[0][0], cwd, _shell_of(receipt)) if segs and segs[0][0] else cwd


def _move_args(receipt: Dict[str, Any], key: str) -> List[str]:
    """收據指令裡 --old／--new／--for 的值（可重複），相對路徑照工具的 --root（本身相對工具那一段的有效 cwd）解，沒給 --root
    就照有效 cwd，解成絕對路徑後 canon_path。"""
    cmd, cwd = str(receipt.get("cmd") or ""), _tool_cwd(receipt)
    r = _MOVE_ARG_RE["root"].search(cmd)
    base = os.path.join(cwd, r.group(1).strip("'\"")) if r else cwd
    return [canon_path(v if os.path.isabs(v) else os.path.join(base, v))
            for v in (m.group(1).strip("'\"") for m in _MOVE_ARG_RE[key].finditer(cmd))]


def move_facts(move: Dict[str, Any], receipts: Iterable[Dict[str, Any]]) -> Tuple[Optional[int], bool]:
    """一筆搬目錄之後的收據事實（規則 MOVE_CODE_DIR_NEEDS_SCAN_AND_SAMPLE）：最後一次合格掃描的命中數（點名同一個舊路徑；
    舊路徑不明就認同一個新路徑），沒有回 None；有沒有 --for 點名這個新目錄的合格抽樣 PASS。收據要在搬之後：兩邊都有 session 事件序號就比序號
    （時間只到秒，同一秒分不出先後），沒有才比時間。"""
    at, seq = str(move.get("at") or ""), move.get("seq")

    def later(r: Dict[str, Any]) -> bool:
        if seq is not None and r.get("seq") is not None:
            return int(r["seq"]) > int(seq)
        return str(r.get("at") or "") > at

    old, new = canon_path(move.get("old") or "") if move.get("old") else "", canon_path(move.get("new") or "")
    after = sorted((r for r in receipts if later(r)), key=lambda r: (int(r.get("seq") or 0), str(r.get("at") or "")))
    hits: Optional[int] = None
    sample_ok = False
    for r in after:
        if _move_tool_receipt(r, "scan") and ((old in _move_args(r, "old")) if old else (new in _move_args(r, "new"))):
            for s in r.get("sentinels") or []:
                if not isinstance(s, dict) or s.get("name") != "MOVE_PATH_SCAN":
                    continue
                kv = (s.get("kv") or {}).get("hits")                 # state 收據存 kv；帳本行存 line
                m = None if kv is not None else _MOVE_HITS_RE.search(str(s.get("line") or ""))
                if kv is not None and str(kv).isdigit():
                    hits = int(kv)
                elif m:
                    hits = int(m.group(1))
        if _move_tool_receipt(r, "sample") and new in _move_args(r, "for") and any(
                isinstance(s, dict) and s.get("name") == "MOVE_SAMPLE_CHECK" and s.get("verdict") == "PASS"
                for s in r.get("sentinels") or []):
            sample_ok = True                                    # 抽樣只替 --for 點名到的新目錄清帳
    return hits, sample_ok


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
                         moves: Iterable[Dict[str, Any]] = (),
                         move_scan_hits: Optional[Dict[str, List[str]]] = None,
                         move_receipts: Optional[List[Dict[str, Any]]] = None,
                         scope_fix: Optional[Callable[[], Optional[Tuple[bool, List[str]]]]] = None,
                         case_check: Optional[Callable[[str], Verdict]] = None,
                         audit: Optional[List[Dict[str, Any]]] = None,
                         ) -> Tuple[Optional[str], Optional[str]]:
    """回 (寫碼查核擋訊息或 None, 收尾報告欄擋訊息或 None)。純判定、不改 state。
    audit＝(a)(b)(c) 命中但被 last_text 裡的宣稱行解掉的那幾筆（規則 CLAIM_WORDS_ARE_HINTS：「非本回合宣稱，因為…」或
    「收據 <ref>」對上），caller 落 guard log 留帳；None＝不收。
    scope_fix＝驗證範圍宣告給 (a) 的證據（wg_verify_scope.fix_evidence；stop 傳入，避免反向 import）：回 None＝沒宣告，
    退回下面的檔名對應；回 (有沒有, 說明行)＝有宣告，(a) 只認它。
    case_check＝(d)「由哪個案例驗」的判定（wg_verify_scope.case_check；驗證範圍閘開著時 stop 傳入）：給了就照 LLM 的案例宣告判，
    沒給退回時序判法（OWED_AFTER_LAST_CASE＋CASE_GREEN_AFTER_EDIT）。
    「本回合」的收據與改檔：user_turn（使用者打字開的回合，stop._user_turn）給了就是它到 turn_seq 之間的每個 turn_seq
    （同伴訊息、背景通知讓 turn_seq 前進，剛跑完的驗證仍算本回合）；沒給只認 turn_seq 那一個。
    exec_this_turn＝本回合跑過 Bash／PowerShell（PostToolUse 記的 exec_turn_seq 落在本回合）：(c) 不再只靠 transcript 這一段的工具名。
    pending＝已擋滿待放行：擋訊息不再建議「改成事實句」（換句話不會解帳），只列證據與放行問法；(d) 欠帳也一樣。
    寫碼查核：(a) 說修好：有驗證範圍宣告（scope_fix）而範圍內沒有一項改完之後跑綠；沒宣告時本 turn 無對得上改檔的合格 PASS、
    也沒有改檔所在部位的合格自寫收據（self_covered）；
    (b) 說量了而本 turn 沒有能當證據的 DONE（跑了部位量尺，或白名單語法且參數沒寫哨兵字樣）、也沒有改檔部位的合格自寫收據；
    (c) 說試過無執行工具。(a)(b)(c) 對「宣稱」對帳：last_text 與 claims（擋滿待放行時承接的先前宣稱，
    換一句話不能讓它消失）裡宣告完成的那幾段；pending 時 (b)(c) 只叫人補證據、不叫人改措辭；
    (d) 補案例的義務（case_debt，跨回合；PASS 不代替）：有 case_check → 每個改過的程式檔要有成立的案例宣告；沒有 → 本 session
    最後一次改驗證案例（仍存在的程式檔）之後同根還改過程式檔。不看措辭，有改碼紀錄就判。
    收尾報告欄：(e) last_text 宣告完成且 AEC 已 emit：有收據而 j 缺／不存在、k 空字串（屬記憶與報告類，擋滿時不走放行詢問）。
    (a) 的「對得上」要同根（root 沒給＝每個改檔用 file_root_of 判根）且收據在它對上的每個改檔最後一次修改之後。"""
    texts = [t for t in (*claims, last_text) if t and claims_completion(t)]
    moves = collapse_move_chain([m for m in moves or () if isinstance(m, dict) and m.get("new")])
    if not texts and not own_mod_files and not moves:
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
    # 規則 CLAIM_WORDS_ARE_HINTS：(a)(b)(c) 命中且沒證據時，先看被判的同一串文字（承接的先前宣稱＋last_text）有沒有宣稱行解掉它
    # （「非本回合宣稱，因為…」放行留帳；「收據 <ref>」要對得上本 session 一筆合格收據：CLAIM_RECEIPT_REF_MATCH）；沒有才擋，擋訊息附寫法。
    # 宣稱從承接的文字來、宣稱行只看最後一則 → 中段寫過的豁免行最後一則沒重寫就再擋一次（第五跑 B5）
    dispositions = parse_claim_dispositions("\n".join(t for t in (*claims, last_text) if t))

    def find_receipt(kind: str, ref: str) -> Optional[str]:
        """宣稱行指的收據（規則 CLAIM_RECEIPT_REF_MATCH）：ref 要指得到那條指令的一個完整 token（names_item：整個 token、檔名、
        路徑或節點尾段、帶空白的逐字片段；python／pytest 這類通用字不算）或哨兵名相同。對上的那張還要過原本的收據資格（_clean：
        指令完整、記了環境、白名單語法、沒寫哨兵字樣、同一棵樹）：修好 → 合格 PASS、同根、晚於相關改檔；量了 → DONE 且指令可信
        或跑了部位量尺；試過 → 指令可信的任一筆。"""
        key = str(ref or "").strip()
        if not key or is_generic_name(key):
            return None
        for r in receipts:
            if not isinstance(r, dict):
                continue
            named = (names_item(str(r.get("cmd") or ""), key)
                     or any(str(s.get("name") or "").strip().lower() == key.lower()
                            for s in (r.get("sentinels") or []) if isinstance(s, dict)))
            if not named:
                continue
            if kind == "measured":
                if not ("DONE" in _verdicts(r) and (_clean(r) or any(_ruler_ran(mc, r) for mc in measure_cmds))):
                    continue
            elif not _clean(r):
                continue
            if kind == "fixed" and not (pass_receipts([r]) and all(_after_last_edit(r, mod_records.get(p)) for p in relate_paths)
                                        and all(_root_ok(r, root_of(p)) for p in relate_paths)):
                continue
            return f"{str(r.get('cmd') or '')[:60]}（turn {r.get('turn_seq')}）"
        return None

    def settle(letter: str, kind: str, v: Verdict) -> None:
        dv = claim_disposition_verdict(kind, dispositions, lambda ref, _k=kind: find_receipt(_k, ref))
        if dv.owed:
            hits.append(format_hit(letter, Verdict(v.rule if dv.rule == "CLAIM_WORDS_ARE_HINTS" else dv.rule, True,
                                                   v.why if dv.rule == "CLAIM_WORDS_ARE_HINTS" else f"{v.why}；{dv.why}",
                                                   (*v.evidence, *dv.evidence))))
        elif audit is not None:
            audit.append({"letter": letter, "kind": kind, "rule": dv.rule, "why": dv.why,
                          "line": dv.evidence[0] if dv.evidence else ""})

    fixed = any(claims_fixed(t, phrases) for t in texts)
    scope = scope_fix() if fixed and scope_fix else None
    if scope is not None and not scope[0]:
        settle("a", "fixed", Verdict(
            "CLAIM_FIXED_NEEDS_PASS", True, "說「修好」但驗證範圍宣告裡沒有一項在跟它有關的最後一次改動之後跑綠",
            (*scope[1][:4], "修好的證據認你宣告的驗證範圍：範圍內任一項改完之後跑綠就算（不看回合、不比檔名）；"
                            "範圍不對就重新宣告（need_goal verify_scope）" + note("PASS"))))
    elif scope is None and fixed and not related and not covered():
        settle("a", "fixed", Verdict(
            "CLAIM_FIXED_NEEDS_PASS", True, f"說「修好」但 {_pass_why(this_turn, receipts, unrelated, relate_paths)}",
            (f"本回合 PASS 收據 {len(pass_receipts(this_turn))} 筆、對得上改檔的 0 筆" + turn_rule,
             "修好的證據是本回合跑「驗那個改動」的驗證（cmd 提到改的檔／verify 路徑／量尺指令）印出 `<NAME>_CHECK PASS` 且 exit 0，"
             # 全量改增量待補：原本括號寫「背景全量」，全量已從流程拔掉，不再當成修好的建議做法
             "或改完之後才開始跑、全綠、同一棵樹的部位量尺自寫收據（背景跑的整組 pytest）" + note("PASS"))))
    measured = any("DONE" in _verdicts(r) and (_clean(r) or any(_ruler_ran(mc, r) for mc in measure_cmds))
                   for r in this_turn)
    if any(claims_measured(t, phrases) for t in texts) and not measured and not covered():
        settle("b", "measured", Verdict(
            "CLAIM_MEASURED_NEEDS_DONE", True, "說「量了」但本回合沒有 `<NAME> DONE k=v` 收據，也沒有改完之後跑的部位量尺自寫收據",
            (("補跑量尺讓它印 DONE 尾行" if pending else "量了就讓量尺腳本印 DONE 尾行，沒量就寫沒量") + note("DONE") + turn_rule,)))
    if not exec_this_turn and any(tried_claim_without_exec(t, turn_tool_names, cfg.get("exec_tools") or [], this_turn, phrases)
                                  for t in texts):
        settle("c", "tried", Verdict(
            "CLAIM_TRIED_NEEDS_EXEC", True, "說「試過／跑了」但本回合沒有任何 Bash／PowerShell 執行",
            (f"本回合工具呼叫：{'、'.join(sorted(set(str(n) for n in turn_tool_names))[:6]) or '（無）'}" + turn_rule,
             "現在跑出收據" if pending else "沒跑就寫沒跑，或現在跑")))
    exts = cfg.get("code_exts") or []
    absent = [p for p in mod_session if is_code_file(p, exts) and not code_exists(p) and not is_excluded(p, cfg, root_of(p))]
    why: Dict[str, Verdict] = {}
    last_sha = {canon_path(p): m.get("sha") for p, m in mod_records.items()}
    gone = vanished_code_paths(absent, cfg, committed_new=committed_new, verdicts=why, last_sha=last_sha) if absent else ()
    debt_why: Dict[str, Verdict] = {}
    owed = case_debt(own_mod_files, turn_seq, cfg, root_of, gone, evidence=debt_why, case_check=case_check)
    if owed and case_settled:
        done = set(case_settled(owed))
        if done:
            print("[Guardian:ReconcileGate] 規則 SNAPSHOT_SETTLED：commit 時不欠案例、之後改了又回到那時的內容，不重算補案例："
                  + "、".join(Path(p).name for p in sorted(done)[:5]), file=sys.stderr)
        owed = [p for p in owed if p not in done]
    if owed and case_check is None:
        green = green_settled_paths(owed, own_mod_files, receipts, cfg, root_of)
        for p, v in green.items():
            print(f"[Guardian:ReconcileGate] 規則 {v.rule}：{v.why}｜證據：{'；'.join(v.evidence)}", file=sys.stderr)
        owed = [p for p in owed if p not in green]
    if owed:
        names = "、".join(Path(p).name for p in owed[:4])
        per_file = [v for v in (why.get(p) or debt_why.get(p) for p in owed[:4]) if v]
        cases_touched = [Path(m["path"]).name for m in own_mod_files or []
                         if isinstance(m, dict) and m.get("path") and is_case_file(m["path"], cfg, root_of(m["path"]))]
    if owed and case_check is not None:
        # 規則 CASE_DECLARED_FOR_CHANGE／NO_CASE_NEEDS_USER：由哪個案例驗是 LLM 的宣告，這裡只列哪一個檔哪裡不成立
        lines = list(dict.fromkeys(ln for v in per_file for ln in (f"{v.rule}：{v.why}", *v.evidence)))
        hits.append(format_hit("d", Verdict(
            per_file[0].rule if per_file else "CASE_DECLARED_FOR_CHANGE", True,
            f"改了程式碼（{names}），還沒有成立的「由哪個案例驗」宣告（義務跨回合，不看收尾措辭）",
            (*lines,
             f"本 session 新寫或改過的案例檔（宣告時可選的）：{'、'.join(dict.fromkeys(cases_touched[:6])) or '（無）'}",
             "由哪個案例驗由你判斷：改了別支測試不會替它清帳；案例跑紅再修到綠的過程只記錄、不擋"))))
    elif owed:
        hits.append(format_hit("d", Verdict(
            per_file[0].rule if per_file else "OWED_AFTER_LAST_CASE", True,
            f"改了程式碼（{names}）之後沒有新增或修改驗證 case 檔（案例檔要和程式同根、現在還在、是程式檔；義務跨回合，不看收尾措辭）",
            (*[f"{v.rule}：{v.why}" for v in per_file],
             f"本 session 改過的案例檔：{'、'.join(cases_touched[:4]) or '（無）'}",
             "改碼之後沒有點名同根案例檔跑綠的 PASS 收據（規則 CASE_GREEN_AFTER_EDIT）",
             "改了碼沒驗證 case（PASS 不能代替）：補一個會紅的 case 再跑綠；真的不需要補案例，就照【收尾放行確認】問使用者"))))
    # (v) 規則 MOVE_CODE_DIR_NEEDS_SCAN_AND_SAMPLE：搬了含程式檔的目錄，欠搬之後的路徑掃描與抽樣兩張收據（不看措辭、跨回合）
    for mv in moves:
        hits_n, sample_ok = move_facts(mv, receipts if move_receipts is None else move_receipts)
        v = move_dir_verdict(mv, hits_n, sample_ok, (move_scan_hits or {}).get(canon_path(mv.get("old") or ""), ()))
        if v.owed:
            hits.append(format_hit("v", v))
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
    # 規則 RECONCILE_BLOCK_LETTERS：沒列在 block_letters 的條目照判、只提示不擋
    hits, quiet = split_blocking(hits, cfg.get("block_letters"))
    report, quiet_report = split_blocking(report, cfg.get("block_letters"))
    for h in quiet + quiet_report:
        print(f"[Guardian:ReconcileGate] 規則 RECONCILE_BLOCK_LETTERS：只提示不擋｜{h[:200]}", file=sys.stderr)
    note = ""
    if any(r.get("exit_unknown") for r in related) or any(r.get("exit_unknown") for r in unrelated):
        note = "\n註：有 PASS 收據的 exit 未知（exit 未知＝dict 回應沒有 exit 欄），只憑哨兵認定。"
    tail = _RECONCILE_TAIL_EVIDENCE if pending or owed else _RECONCILE_TAIL
    code_reason = (_RECONCILE_HEAD + "\n".join("  " + h for h in hits) + tail + note) if hits else None
    report_reason = (_RECONCILE_HEAD + "\n".join("  " + h for h in report) + _RECONCILE_TAIL) if report else None
    return code_reason, report_reason


# ─── 部位量尺（候選材料）、驗證環境、自寫收據 ─────────────────────────────────
# 部位表的整把量尺不再是收尾必跑的門檻（該測哪些由 LLM 宣告驗證範圍，見 wg_verify_scope）：這裡留的是對帳 (a)(b) 認「跑了部位量尺」
# 與背景全量自寫收據的事實，以及驗證範圍閘要用的執行環境就緒檢查（verify_chains[部位].runtime_gate）。

def load_verify_chains(root: Path) -> Dict[str, Dict[str, str]]:
    """合併後設定（hub_config 四層：預設 < config.json overview_hub < 公司根 < 專案根 overview-hub.json，經 wg_overview._cfg）
    的 `verify_chains{part:{runtime_gate,pre,run,collect,cleanup}}`；沒有回 {}。
    設定有錯（與導讀卡端同一套驗證）→ 拋 ValueError：驗證範圍閘的判定錯誤一律擋（stop._verify_gates），不當作沒設。"""
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


# ─── 驗證範圍：收據跑了哪些、對不對得上宣告的一項（判定在 wg_release_rules.SCOPE_ITEM_RECEIPT_AFTER_EDIT） ───
_PY_RE = lazy_re(r"^python(?:\d+(?:\.\d+)*)?w?(?:\.exe)?$", re.IGNORECASE)
_PYTEST_PROGS = frozenset({"pytest", "py.test"})
_SCRIPT_RUNNERS = frozenset({"node", "bash", "sh", "pwsh", "powershell", "deno", "bun", "ruby", "perl"})
# 不改變跑哪些案的 pytest 帶值選項（值可接在 = 後或下一個字）；沒列在這裡、也不在整體驗證白名單的選項一律當「只跑一部分」
_PYTEST_SAFE_VALUE_OPTS = frozenset({"--tb", "--color", "-r", "--basetemp", "--rootdir", "-n", "--maxfail", "--durations",
                                     "--junitxml", "--timeout"})


def _abs_target(base: str, word: str) -> str:
    """指令裡的路徑字（可帶 ::節點）→ 正規化絕對路徑（照 base 解相對路徑；節點段原樣接回）。"""
    f, sep, node = str(word).partition("::")
    p = f if (os.path.isabs(f) or re.match(r"^[A-Za-z]:[\\/]", f)) else os.path.join(base or "", f)
    return canon_path(p) + (sep + node.lower() if sep else "")


def _pytest_targets(args: List[str], base: str) -> Tuple[List[str], bool]:
    """pytest 的參數 → (點名的路徑或節點, 有沒有可能只跑一部分)。選項走白名單：整體驗證准帶的（-q -v -s -x、-r…、--tb=…）、
    `-p no:…`、不改變跑哪些案的帶值選項；其他（-k、-m、-o、--deselect、--lf、連寫的 -kfoo…）一律當只跑一部分（fail-closed）。"""
    out: List[str] = []
    narrowed, i = False, 0
    while i < len(args):
        a = args[i]
        if a == "-p" and i + 1 < len(args) and args[i + 1].startswith("no:"):
            i += 2
            continue
        if not a.startswith("-"):
            out.append(_abs_target(base, a))
            i += 1
            continue
        name = a.split("=", 1)[0]
        if name in _PYTEST_SAFE_VALUE_OPTS:
            i += 1 if "=" in a else 2
            continue
        if not _self_receipt._PYTEST_WHOLE_OPT_RE.match(a):
            narrowed = True
        i += 1
    return out, narrowed


def _step_targets(st: Any, base: str) -> Tuple[List[str], bool]:
    """一段跑程式的指令真的執行了哪些路徑，以及有沒有可能只跑一部分：pytest 點名的檔、資料夾、節點；python／node 等直接執行的
    腳本檔本身；寫成路徑的程式本身。其他程式（`python -m compileall`、`-m unittest`…）的參數不算跑過的測試，要宣告成指令項目。
    python 直譯器選項只准 `-X utf8`、`-u`、`-B`（`-O` 會拿掉 assert，當只跑一部分）。"""
    words = list(st.words)
    if not words:
        return [], False
    head = Path(words[0].replace("\\", "/")).name.lower()
    head = head[:-4] if head.endswith(".exe") else head
    if _PY_RE.match(head):
        i, odd = 1, False
        while i < len(words) and words[i].startswith("-") and words[i] not in ("-m", "-c"):
            w = words[i]
            if w in ("-X", "-W"):
                odd = odd or not (w == "-X" and i + 1 < len(words) and words[i + 1] == "utf8")
                i += 2
                continue
            odd = odd or w not in ("-u", "-B", "-Xutf8")
            i += 1
        if i >= len(words) or words[i] == "-c":
            return [], odd                                    # 內嵌碼沒有路徑目標
        if words[i] == "-m":
            if i + 1 < len(words) and words[i + 1] in _PYTEST_PROGS:
                paths, narrowed = _pytest_targets(words[i + 2:], base)
                return paths, narrowed or odd
            return [], odd                                    # 別的模組：參數不是跑過的測試
        return [_abs_target(base, words[i])], odd             # python 跑腳本：腳本本身跑過，參數不算
    if head in _PYTEST_PROGS:
        return _pytest_targets(words[1:], base)
    if head in _SCRIPT_RUNNERS:
        script = next((w for w in words[1:] if not w.startswith("-")), "")
        return ([_abs_target(base, script)] if script else []), False
    if "/" in words[0] or "\\" in words[0]:
        return [_abs_target(base, words[0])], False           # 程式本身寫成路徑（./verify.sh）
    return [], False


def run_targets(receipt: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """收據實際跑了什麼：{whole: 整體驗證（涵蓋執行根之下全部）, base: 執行根, paths: 完整跑過的路徑（可帶 ::節點）,
    narrowed: 有一段可能只跑一部分}。可能只跑一部分的那段點名的路徑不進 paths（命令列點名不等於實際執行）。
    指令不完整、根不可信（換目錄）、不能當一般證據（白名單外語法、環境縮範圍、寫了哨兵字樣、指到別棵樹）→ None。"""
    r = _trusted(receipt)
    if r is None or not _clean(r):
        return None
    base = _cwd_of(r)
    if _whole_run(r):
        return {"whole": True, "base": base, "paths": [], "narrowed": False}
    paths: List[str] = []
    narrowed = False
    for st in _self_receipt.evidence_steps(str(r.get("cmd") or ""), _shell_of(r), _env_of(r)) or []:
        p, n = _step_targets(st, base)
        narrowed = narrowed or n
        if not n:
            paths += [x for x in p if x not in paths]
    return {"whole": False, "base": base, "paths": paths, "narrowed": narrowed}


def receipt_is_red(receipt: Dict[str, Any]) -> bool:
    """一輪跑紅：有 FAIL 哨兵、exit 不是 0（沒記 exit 不算）、或哨兵帶 failed=<k> 且 k 不是 0。"""
    return ("FAIL" in _verdicts(receipt) or receipt.get("exit_code") not in (None, 0) or not _failed_kv_ok(receipt))


def _scope_green(receipt: Dict[str, Any]) -> bool:
    """驗證範圍認的綠：不是暫存目錄的收據、有 PASS 或 DONE、沒跑紅。"""
    v = _verdicts(receipt)
    return not _temp_receipt(receipt) and ("PASS" in v or "DONE" in v) and not receipt_is_red(receipt)


def _red_case_under(item: Dict[str, Any], case: str, base: str) -> bool:
    """紅案（pytest 節點 id，相對 base）落在這一項底下嗎：檔案／資料夾項目看路徑包含；測試節點項目要同一檔，而且紅案就是那個節點、
    在它底下（參數化、類別裡的方法），或紅案只寫到檔（整檔收集錯誤）。紅案對不到存在的檔（pytest 的根不是 base）→ 歸不了，當落在底下。"""
    cf, _, cn = str(case).partition("::")
    red_file = os.path.join(base, cf) if base and not os.path.isabs(cf) else cf
    if not os.path.exists(red_file):
        return True
    tf, _, tn = str(item.get("abs") or "").partition("::")
    if not tn:
        return _under(red_file, tf)
    if _norm_path(red_file) != _norm_path(tf):
        return False
    return not cn or cn == tn or cn.startswith(tn + "::") or cn.startswith(tn + "[")


def _green_for_item(item: Dict[str, Any], receipt: Dict[str, Any]) -> bool:
    """規則 SCOPE_RED_ONLY_ITS_CASES：這筆收據對這一項算不算綠。整條綠就是綠；有紅時，紅案清單完整（red_known）、不是指令項目、
    不是暫存目錄的收據、exit 是 0／1／沒記，而且沒有紅案落在這一項底下 → 對這一項照算綠。"""
    if _scope_green(receipt):
        return True
    if (item.get("kind") == "cmd" or _temp_receipt(receipt) or not receipt.get("red_known")
            or receipt.get("exit_code") not in (None, 0, 1)):
        return False
    t = run_targets(receipt)
    if t is None:
        return False
    return not any(_red_case_under(item, c, t["base"]) for c in receipt.get("red_cases") or [])


def _exec_dir(receipt: Dict[str, Any]) -> str:
    """收據實際從哪個目錄跑（開頭 `cd <絕對路徑> &&` 換過的算換過之後）。"""
    return _cwd_of(_trusted(receipt) or receipt)


def _same_exec_dir(item: Dict[str, Any], receipt: Dict[str, Any]) -> bool:
    """指令項目要在宣告時的目錄跑：同一條 `pytest -q` 換到子目錄跑的是另一組。宣告或收據沒記目錄 → 不比。"""
    base, ran = _norm_path(str(item.get("base") or "")), _norm_path(_exec_dir(receipt))
    return not base or not ran or base == ran


def _item_ran(item: Dict[str, Any], receipt: Dict[str, Any]) -> bool:
    """收據跑了宣告的這一項（不看先後與紅綠）。指令項目照原字串比（_ruler_ran）且同一棵樹；路徑項目看 run_targets。"""
    if item.get("kind") == "cmd":
        trusted = _trusted(receipt)                           # 只有開頭 `cd <絕對路徑> &&` 認得出根；其他換目錄看不出跑在哪
        return (trusted is not None and _ruler_ran(str(item.get("target") or ""), receipt, str(item.get("base") or ""))
                and _root_ok(trusted, item.get("root")) and _same_exec_dir(item, receipt))
    t = run_targets(receipt)
    if t is None:
        return False
    tf, _, tn = str(item.get("abs") or "").partition("::")
    if t["whole"]:
        return _under(tf, t["base"])
    for p in t["paths"]:                                      # 只有完整跑過的那幾段（可能只跑一部分的段不進 paths）
        pf, _, pn = p.partition("::")
        if pn:
            if tn and pf == tf and (tn == pn or tn.startswith(pn + "::") or tn.startswith(pn + "[")):
                return True                                   # 點名節點（或它的上層節點）
            continue
        if _under(tf, pf):
            return True                                       # 跑了該檔、它所在的資料夾
    return False


def self_run_targets(run: Dict[str, Any]) -> List[str]:
    """自寫收據（run_verify／根 conftest）跑了哪些路徑：argv 點名的路徑（照收據 cwd 解成正規化絕對路徑；測試節點保留
    `::節點`；看起來是路徑卻不存在的也照列，免得變成「沒點名＝全部」）；沒點名（`python run_verify.py` 整體）回 []＝受測樹全部。"""
    argv = run.get("argv") if isinstance(run.get("argv"), list) else []
    cwd = str(run.get("cwd") or run.get("project_root") or "")
    out: List[str] = []
    for w in [str(x) for x in argv[1:]]:
        if w.startswith("-") or Path(w.replace("\\", "/")).name.lower() in ("run_verify.py", "pytest", "utf8"):
            continue
        f, sep, node = w.partition("::")
        p = f if (os.path.isabs(f) or re.match(r"^[A-Za-z]:[\\/]", f)) else os.path.join(cwd, f)
        looks_path = bool(sep) or "/" in f or "\\" in f or bool(re.search(r"\.\w{1,6}$", f))
        t = canon_path(p) + (sep + node.lower() if sep else "")
        if (os.path.exists(p) or looks_path) and t not in out:
            out.append(t)
    return out


def _self_run_item_ok(item: Dict[str, Any], run: Dict[str, Any], mods: List[Dict[str, Any]]) -> bool:
    """背景跑的自寫收據算不算這一項：全綠（exit 0、failed=0）、記了環境且沒縮範圍、改完之後才開始跑、同一棵樹，
    而且跑的是這一項（指令項目 argv 照原字串比；路徑項目在它點名的路徑之下，沒點名＝整棵樹）。不綁 session。
    有紅時照 SCOPE_RED_ONLY_ITS_CASES：failed_cases 筆數等於 failed（清單完整）、exit 1、不是指令項目、沒有紅案落在這一項底下 → 照算。"""
    if not isinstance(run, dict):
        return False
    if run.get("exit_code") != 0 or str(run.get("failed")) != "0":
        reds = [str(x) for x in run.get("failed_cases") or []]
        complete = run.get("exit_code") == 1 and bool(reds) and str(run.get("failed")) == str(len(reds))
        base = str(run.get("project_root") or run.get("cwd") or "")
        if not complete or item.get("kind") == "cmd" or any(_red_case_under(item, c, base) for c in reds):
            return False
    if not isinstance(run.get("env"), dict) or _self_receipt.scope_env(run["env"].items()):
        return False
    if not all(_receipt_after({"at": run.get("started_at") or ""}, (m.get("last_at") or m.get("at")) or None, None,
                              int(m.get("last_turn_seq", m.get("turn_seq", 0)) or 0)) for m in mods):
        return False
    if not _root_ok(run, item.get("root")):
        return False
    if item.get("kind") == "cmd":
        argv = run.get("argv")
        return cmd_matches(str(item.get("target") or ""), argv if isinstance(argv, list) and argv else str(run.get("cmd", "")),
                           root=str(run.get("project_root") or ""), measure_root=str(item.get("base") or ""))
    tf, sep, tn = str(item.get("abs") or "").partition("::")
    targets = self_run_targets(run)
    if not targets:
        return _under(tf, str(run.get("project_root") or ""))
    for t in targets:
        f, tsep, n = t.partition("::")
        if not tsep and _under(tf, f):
            return True                              # 這一輪整支（或整個資料夾）跑過
        if tsep and sep and canon_path(f) == canon_path(tf) and (tn == n or tn.startswith(n + "::") or tn.startswith(n + "[")):
            return True                              # 這一輪只跑某個節點：只涵蓋那個節點（含它的參數化與子節點）
    return False


def _scope_after(receipt: Dict[str, Any], mod: Dict[str, Any]) -> bool:
    """收據在這個改檔最後一次修改之後：比 at，同秒比序號，都沒有比 turn（修改紀錄連 turn 都沒有才不比）。"""
    turn = mod.get("last_turn_seq", mod.get("turn_seq"))
    return _receipt_after(receipt, mod.get("last_at") or mod.get("at") or None, mod.get("last_seq"),
                          int(turn) if turn is not None else -1)


def _mentions(item: Dict[str, Any], receipt: Dict[str, Any]) -> bool:
    """收據指令字面上提到這一項（給「為什麼不算」的說明挑收據用，不是判定）。"""
    raw = str(receipt.get("cmd") or "").replace("\\", "/").lower()
    if item.get("kind") == "cmd":
        return True
    name = Path(str(item.get("abs") or "").partition("::")[0]).name.lower()
    return bool(name) and name in raw


def scope_item_status(item: Dict[str, Any], receipts: Iterable[Dict[str, Any]],
                      mods: Iterable[Dict[str, Any]], self_runs: Iterable[Dict[str, Any]] = ()) -> Tuple[bool, str]:
    """宣告的一項有沒有合格收據：跑了這一項、綠、晚於每個要宣告的改檔最後一次修改（session 收據，或背景跑的自寫收據）。
    回 (有沒有, 沒有時的理由)。"""
    mods = list(mods or [])
    receipts = [r for r in receipts or [] if isinstance(r, dict)]
    hits = [r for r in receipts if _item_ran(item, r)]
    for r in hits:
        if _green_for_item(item, r) and all(_scope_after(r, m) for m in mods):
            return True, ""
    self_runs = [run for run in self_runs or [] if isinstance(run, dict)]
    if any(_self_run_item_ok(item, run, mods) for run in self_runs):
        return True, ""
    narrowed = [n for run in self_runs if isinstance(run.get("env"), dict) and _self_run_item_ok(item, {**run, "env": {}}, mods)
                for n in _self_receipt.scope_env(run["env"].items())]
    env_note = (f"。背景跑的自寫收據對上了這一項，但跑的時候{_scope_env_why([(n, '', '') for n in dict.fromkeys(narrowed)])}"
                if narrowed else "")
    if not hits:
        near = [r for r in receipts if _mentions(item, r)]
        rulers = [str(item.get("target") or "")] if item.get("kind") == "cmd" else []
        ran = [r for r in near if rulers and _ruler_ran(rulers[0], r, str(item.get("base") or ""))]
        if any(_trusted(r) is None for r in ran):
            note = ("指令含 cd：前面只准 `cd <絕對路徑> &&`（才認得出根），其他換目錄看不出跑在哪，不算；"
                    "請在宣告時的目錄直接跑")
        elif any(not _same_exec_dir(item, r) for r in ran):
            moved = [r for r in ran if not _same_exec_dir(item, r)]
            note = (f"執行根是 {_exec_dir(moved[-1]).replace(chr(92), '/')}，宣告時在 "
                    f"{str(item.get('base') or '').replace(chr(92), '/')}：同一條指令換了目錄跑的是另一組，請在宣告時的目錄跑")
        else:
            note = _syntax_note(near, "DONE", rulers) or _syntax_note(near, "PASS", rulers)
        return False, ("沒有跑這一項的收據（只跑一部分如 -k、指令換目錄、環境縮範圍、白名單外語法、在別棵樹跑的都不算；"
                       "背景跑的要等它寫完自寫收據）" + (f"。{note}" if note else "") + env_note)
    last = hits[-1]
    if not _green_for_item(item, last):
        return False, f"最近一次跑紅（exit={last.get('exit_code')}，結論 {'、'.join(_verdicts(last)) or '無哨兵'}）" + env_note
    stale = next((m for m in mods if not _scope_after(last, m)), None)
    name = Path(str((stale or {}).get("path") or "")).name or "改檔"
    hint = ("（這一項沒宣告 depends：任何程式改動都作廢它；宣告它用到的程式檔或資料夾，改到別的就不作廢）"
            if "depends" not in item else "")
    return False, f"最近一次跑在最後一次改動（{name}）之前：改完要重跑{hint}" + env_note


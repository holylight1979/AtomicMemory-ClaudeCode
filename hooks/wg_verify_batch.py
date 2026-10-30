"""wg_verify_batch.py：驗證批次閘（PreToolUse Bash／PowerShell）——同一批改動只驗一次、整組驗證要使用者口令。

做什麼：使用者點名的三種浪費——①各別跑完後又跑全量 ②反覆跑個別驗證 ③全量跑完又跑全量——在跑之前擋下。
  1. 辨認驗證指令（lib/self_receipt 的解析）：pytest（含 python -m pytest）、run_verify.py、直接跑 verify_*.py／test_*.py／*_test.py。
     解析不了的（heredoc、eval、bash -c）不管、放行、不留帳。
  2. 批次指紋＝「上一次同一組指令跑綠」之後，本 session（子代理看自己的）有沒有新改動：
     收據（state verify_receipts 的 seq／自寫收據的時間）對 modified_files 的 last_seq／last_at。
  3. 三條規則：VERIFY_FULL_RUN_NEEDS_USER_ORDER、VERIFY_SAME_BATCH_ALREADY_GREEN、VERIFY_BATCH_BLOCK_ONCE_PER_TURN（RULES 登在
     hooks/wg_release_rules.py 檔尾）。擋訊息格式照 format_hit：`✗ (r) <規則名>：<一句現象>｜證據：<一行一證據>`。
  4. 整組只攔「會拖時間」的（006 實測：小專案 pytest 幾秒就完也被攔＝誤傷）：同一組指令最近一筆收據的耗時 ≥ slow_run_s
     （只有自寫收據記了 started_at 能算；session 收據沒記＝不知道），或指令跑的樹底下的測試檔（reconcile_gate.verify_case_globs
     的程式檔）≥ large_suite_files（數到門檻就停、state 每根快取一筆）。兩者都不成立（含耗時不知道）→ 沒口令也放行、留帳 reason=small。
  判定（decide）是純函式：不讀檔、不改 state；check 收事實（讀自寫收據、數測試檔、擋次帳）交 decide，擋下與放行都留帳 Logs/guard-verify_batch.jsonl。
怎麼跑案例：python -X utf8 -m pytest -q hooks/verify/verify_verify_batch.py
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, NamedTuple, Optional, Sequence, Tuple

from wg_lazy_re import lazy_module

_rr = lazy_module("wg_release_rules")   # 判定結果與擋訊息格式；這條指令不是驗證指令就用不到，第一次用到才載（HOOK_IMPORT_ON_USE）

RULE_FULL = "VERIFY_FULL_RUN_NEEDS_USER_ORDER"
RULE_SAME = "VERIFY_SAME_BATCH_ALREADY_GREEN"
RULE_ONCE = "VERIFY_BATCH_BLOCK_ONCE_PER_TURN"
GATE = "verify_batch"
TAG = "[Guardian:VerifyBatch]"
LETTER = "r"
DEFAULT_FULL_RUN_KEYWORDS = ("整組", "全量", "全部測試", "run_verify")
DEFAULT_SLOW_RUN_S = 120            # 上次同一組指令跑了這麼久以上才算「會拖時間」
DEFAULT_LARGE_SUITE_FILES = 50      # 樹底下測試檔這麼多支以上才算「會拖時間」
WHY_SMALL = "整組但不會拖時間，放行"
SUITE_CACHE_KEY = "verify_batch_suite_files"   # state[該鍵][根] = {"files": n, "at": iso}；每根只數一次
_SKIP_DIRS = frozenset({"node_modules", "__pycache__", "venv", ".venv", "dist", "build", "site-packages"})
_CASE_PREFIXES = ("verify_", "test_")
_CASE_SUFFIX = "_test.py"


def _self_receipt():
    """lib/self_receipt 用本檔所在樹的那份（同 wg_verify_ledger 的理由：按名字 import 會拿到別棵樹的 lib）。"""
    import importlib.util
    name = "_wg_self_receipt"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parents[1] / "lib" / "self_receipt.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.modules[name] = mod
    return mod


class VerifyCmd(NamedTuple):
    key: Tuple[Tuple[Any, ...], ...]   # 驗證那幾段的 (程式, 參數)，同一組指令＝同一個 key；直譯器選項（-X utf8）不改測什麼、不進 key
    full: bool                         # 整組驗證（run_verify.py 不帶參數、pytest 沒點名檔）


def _is_case_script(prog: str) -> bool:
    name = Path(str(prog).replace("\\", "/")).name.lower()
    return name.endswith(".py") and (name.startswith(_CASE_PREFIXES) or name.endswith(_CASE_SUFFIX))


def _pytest_names_file(args: Iterable[str]) -> bool:
    """pytest 的位置參數有沒有點到檔（含 檔::節點）；只有目錄或沒有位置參數＝整個 verify 根。"""
    return any(".py" in a or "::" in a for a in args if a and not a.startswith("-"))


def _pytest_narrowed(args: Sequence[str]) -> bool:
    """-k／-m／--lf／--deselect 這類縮範圍選項：不是整組（self_receipt._whole_step 同一判法，這裡只看有沒有）。"""
    sr = _self_receipt()
    i = 0
    while i < len(args):
        a = args[i]
        if a == "-p" and i + 1 < len(args) and args[i + 1].startswith("no:"):
            i += 2
        elif a.startswith("-"):
            if not sr._PYTEST_WHOLE_OPT_RE.match(a):
                return True
            i += 1
        else:
            i += 1
    return False


def parse_verify_cmd(command: str, shell: str = "bash", root: str = "") -> Optional[VerifyCmd]:
    """指令裡的驗證段；沒有驗證段或解析不了（heredoc、eval、bash -c）→ None。"""
    sr = _self_receipt()
    steps = sr.parse_cmds(command, shell)
    if not steps:
        return None
    verify = [c for c in (_verify_step(st.cmd) for st in steps) if c]
    if not verify:
        return None
    full = any(_full_step(c) for c in verify) and not sr.program_scope_env(command, shell)   # PYTEST_ADDOPTS=-k … 縮了範圍不算整組
    return VerifyCmd(tuple(verify), full)


def _verify_step(cmd: Tuple[Any, ...]) -> Optional[Tuple[str, Tuple[str, ...]]]:
    """這一段是驗證嗎 → (程式, 參數)；pytest 照模組名、腳本照檔名。"""
    prog = str(cmd[0])
    name = Path(prog.replace("\\", "/")).name.lower()
    if prog == "pytest" or name == "run_verify.py":
        return name if name == "run_verify.py" else "pytest", tuple(str(a) for a in cmd[2])
    return (name, tuple(str(a) for a in cmd[2])) if _is_case_script(prog) else None


def _full_step(c: Tuple[str, Tuple[str, ...]]) -> bool:
    """整組：run_verify.py 不帶參數；pytest 沒點名檔（沒有位置參數，或只有目錄）也沒縮範圍選項。"""
    if c[0] == "run_verify.py":
        return not c[1]
    return c[0] == "pytest" and not _pytest_names_file(c[1]) and not _pytest_narrowed(c[1])


def receipt_key(receipt: Dict[str, Any], shell: str = "bash") -> Optional[Tuple[Tuple[Any, ...], ...]]:
    """收據跑的是哪一組驗證指令：session 收據看 cmd（照 tool 的 shell 解析）、自寫收據看 argv。"""
    argv = receipt.get("argv")
    if isinstance(argv, list) and argv:
        parsed = [c for c in (_verify_step(st.cmd) for st in _self_receipt().parse_cmds(argv)) if c]
        return tuple(parsed) or None
    sh = "powershell" if str(receipt.get("tool") or "") == "PowerShell" else shell
    vc = parse_verify_cmd(str(receipt.get("cmd") or ""), sh)
    return vc.key if vc else None


def receipt_green(receipt: Dict[str, Any]) -> bool:
    """跑綠：沒有 FAIL 哨兵、結束碼是 0（自寫收據另看 failed=0）；結束碼不明而有 PASS 哨兵也算。"""
    if receipt.get("source"):                       # 自寫收據
        return int(receipt.get("exit_code", 1) or 0) == 0 and int(receipt.get("failed", 0) or 0) == 0
    verdicts = [str(s.get("verdict") or "") for s in receipt.get("sentinels") or [] if isinstance(s, dict)]
    if "FAIL" in verdicts:
        return False
    code = receipt.get("exit_code")
    if code is None:
        return "PASS" in verdicts
    return int(code) == 0


def _to_utc(s: Any) -> Optional[datetime]:
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else None


def edits_after(receipt: Dict[str, Any], mods: Iterable[Dict[str, Any]]) -> List[str]:
    """收據之後改過的檔：先比事件序號（收據 seq 對改檔 last_seq），兩邊都沒序號才比時間（自寫收據的 UTC 時間對改檔 last_at）。
    改檔少了序號又少了時間＝不知道先後 → 當成有改（寧放行、不誤擋）。"""
    seq = receipt.get("seq")
    at = _to_utc(receipt.get("at"))
    out: List[str] = []
    for m in mods:
        if not isinstance(m, dict) or not m.get("path"):
            continue
        ms = m.get("last_seq")
        if isinstance(seq, int) and isinstance(ms, int):
            later = ms > seq
        else:
            ma = _to_utc(m.get("last_at") or m.get("at"))
            later = at is None or ma is None or ma > at
        if later:
            out.append(str(m["path"]))
    return out


def last_green_same(cmd: VerifyCmd, receipts: Iterable[Dict[str, Any]], shell: str = "bash") -> Optional[Dict[str, Any]]:
    """同一組指令最近一筆收據；它是綠的才回（最近一筆是紅的＝上次紅、放行）。"""
    same = [r for r in receipts if isinstance(r, dict) and receipt_key(r, shell) == cmd.key]
    if not same:
        return None
    last = max(same, key=lambda r: (str(r.get("at") or ""), int(r.get("seq") or 0)))
    return last if receipt_green(last) else None


def last_run_seconds(cmd: VerifyCmd, receipts: Iterable[Dict[str, Any]], shell: str = "bash") -> Optional[float]:
    """同一組指令最近一筆收據跑了幾秒：started_at 到 at（自寫收據有記）；沒 started_at 或時間解析不了 → None（不知道）。"""
    same = [r for r in receipts if isinstance(r, dict) and receipt_key(r, shell) == cmd.key]
    if not same:
        return None
    last = max(same, key=lambda r: (str(r.get("at") or ""), int(r.get("seq") or 0)))
    start, end = _to_utc(last.get("started_at")), _to_utc(last.get("at"))
    if start is None or end is None or end < start:
        return None
    return (end - start).total_seconds()


def _root_key(root: str) -> str:
    from wg_release_rules import canon_path
    return canon_path(root)


def suite_roots(cmd: VerifyCmd, cwd: str) -> List[str]:
    """整組指令跑的是哪幾棵樹：pytest 給了目錄就是那些目錄（相對 cwd），否則 cwd；cwd 不知道就空（檔數當不知道）。"""
    roots: List[str] = []
    for prog, args in cmd.key:
        if prog != "pytest":
            continue
        for a in args:
            if a and not a.startswith("-") and ".py" not in a and "::" not in a:
                p = Path(a) if Path(a).is_absolute() else (Path(cwd) / a if cwd else None)
                if p is not None:
                    roots.append(str(p))
    if not roots and cwd:
        roots.append(cwd)
    return roots


def _count_case_files(root: str, rc: Dict[str, Any], cap: int) -> int:
    """root 底下符合 verify_case_globs 的程式檔有幾支，數到 cap 就停（只要知道有沒有到門檻）。讀不到的目錄略過。"""
    import os
    from wg_verify_ledger import is_case_file
    n = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in _SKIP_DIRS]
        for f in filenames:
            if is_case_file(os.path.join(dirpath, f), rc, root):
                n += 1
                if n >= cap:
                    return n
    return n


def suite_files(state: Optional[Dict[str, Any]], roots: Iterable[str], rc: Dict[str, Any], cap: int) -> Tuple[int, bool]:
    """這些樹底下的測試檔數合計（每根數到 cap 就停）與 state 快取有沒有新寫入。快取 state[SUITE_CACHE_KEY][根]＝{"files","at"}。"""
    cache = state.setdefault(SUITE_CACHE_KEY, {}) if isinstance(state, dict) else {}
    if not isinstance(cache, dict):
        cache = {}
    total, wrote = 0, False
    for root in roots:
        key = _root_key(root)
        hit = cache.get(key)
        if isinstance(hit, dict) and isinstance(hit.get("files"), int):
            n = hit["files"]
        else:
            n = _count_case_files(root, rc, cap) if Path(root).is_dir() else 0
            if isinstance(state, dict):
                cache[key] = {"files": n, "at": datetime.now().astimezone().isoformat(timespec="seconds")}
                wrote = True
        total += n
    return total, wrote


def slow_reason(seconds: Optional[float], files: int, slow_run_s: float, large_suite_files: int) -> Optional[Tuple[str, ...]]:
    """會拖時間嗎：上次耗時 ≥ slow_run_s（不知道不算）或測試檔 ≥ large_suite_files → 證據；都不是 → None。"""
    if seconds is not None and seconds >= slow_run_s:
        return (f"上次耗時 {seconds:.0f} 秒 ≥ slow_run_s {slow_run_s:g}", f"測試檔 {files} 支")
    if files >= large_suite_files:
        return (f"測試檔 {files} 支 ≥ large_suite_files {large_suite_files}（數到門檻就停）",
                "上次耗時 不知道" if seconds is None else f"上次耗時 {seconds:.0f} 秒")
    return None


def keyword_hit(prompts: Iterable[str], keywords: Iterable[str]) -> Optional[str]:
    """使用者原話（已濾掉背景通知、他 session 訊息）裡有沒有整組口令；不分大小寫子字串。"""
    for p in prompts:
        low = (p or "").lower()
        for k in keywords:
            if k and k.lower() in low:
                return k
    return None


def decide(cmd: VerifyCmd, prompts: Sequence[str], keywords: Sequence[str],
           receipts: Iterable[Dict[str, Any]], mods: Iterable[Dict[str, Any]], shell: str = "bash",
           slow: Optional[Tuple[str, ...]] = None) -> _rr.Verdict:
    """純判定：owed=True 要擋。先看這批是不是已驗過（SAME），再看整組要不要口令（FULL）。
    slow＝這組整組指令會拖時間的證據（slow_reason）；None＝不會拖（含不知道）→ 整組沒口令也放行（why=WHY_SMALL）。"""
    mods = list(mods)
    green = last_green_same(cmd, receipts, shell)
    if green is not None:
        changed = edits_after(green, mods)
        if not changed:
            shown = " && ".join(" ".join((c[0], *c[1])) for c in cmd.key)
            return _rr.Verdict(RULE_SAME, True, "這批改動已驗證過",
                           (f"收據 {green.get('at')}", f"指令 {shown[:120]}", "結果 綠", f"之後改檔 0（本 session 改檔 {len(mods)}）"))
    if cmd.full:
        kw = keyword_hit(prompts, keywords)
        if kw:
            return _rr.Verdict(RULE_FULL, False, f"使用者口令「{kw}」")
        if slow is None:
            return _rr.Verdict(RULE_FULL, False, WHY_SMALL)
        return _rr.Verdict(RULE_FULL, True, "會拖時間的整組驗證要使用者本回合原話的口令",
                       (*slow, "本回合使用者原話沒有 " + "／".join(keywords), f"使用者原話 {len(prompts)} 則"))
    return _rr.Verdict(RULE_SAME, False, "第一次跑或上次之後有改檔" if green is None else "上次綠之後有改檔")


def _own_mods(state: Dict[str, Any], sid: str, agent_id: str) -> List[Dict[str, Any]]:
    if agent_id:
        lst = (state.get("agent_modified_files") or {}).get(agent_id)
        if isinstance(lst, list):
            return [m for m in lst if isinstance(m, dict)]
    return [m for m in (state.get("modified_files") or []) if isinstance(m, dict) and m.get("session_id", sid) == sid]


def _prompts(state: Dict[str, Any]) -> List[str]:
    """本回合使用者原話：同 CommitOrder——turn_prompts 是清單就用它（空＝本回合沒原話），舊 state 才退回最後一句。"""
    from wg_core import user_typed_prompts
    tp = state.get("turn_prompts")
    raw = tp if isinstance(tp, list) else list(state.get("recent_user_prompts") or [])[-1:]
    return user_typed_prompts([str(p) for p in raw])


def deny_message(v: _rr.Verdict, released: bool) -> str:
    line = _rr.format_hit(LETTER, v)
    if released:
        return f"{TAG} {line}\n本回合這條規則已擋過一次，這次放行、留帳（規則 {RULE_ONCE}）。"
    fix = ("會拖時間的整組驗證（上次耗時 ≥ slow_run_s 或測試檔 ≥ large_suite_files）只在使用者本回合原話有口令"
           "（guard.verify_batch.full_run_keywords）時跑；要驗自己這批改動就點名檔跑。"
           if v.rule == RULE_FULL else
           "同一組指令、同一批改動只驗一次：改了檔再跑，或跑別組。上次紅會放行。")
    return f"{TAG} {line}\n{fix}\n關閉本閘：workflow/config.json guard.verify_batch.enabled=false。"


def check(tool_name: str, tool_input: Dict[str, Any], config: Dict[str, Any], state: Optional[Dict[str, Any]],
          cwd: str = "", session_id: str = "", agent_id: str = "", call: Optional[Dict[str, Any]] = None,
          self_receipts: Optional[List[Dict[str, Any]]] = None) -> Optional[str]:
    """PreToolUse 入口：擋訊息或 None。收事實（state 收據、自寫收據、改檔、原話）交 decide；擋次照 wg_core.deny_cap
    每個使用者回合每條規則 1 次，第 2 次放行；擋下與放行都留帳 guard-verify_batch.jsonl。閘出錯 → 放行、留帳 error。"""
    if tool_name not in ("Bash", "PowerShell"):
        return None
    cfg = ((config or {}).get("guard") or {}).get(GATE) or {}
    if not cfg.get("enabled", True):
        return None
    command = str(tool_input.get("command") or "")
    shell = "powershell" if tool_name == "PowerShell" else "bash"
    try:
        from wg_core import append_guard_log, deny_cap, write_state
        cmd = parse_verify_cmd(command, shell, cwd)
        if cmd is None:
            return None
        st = state if isinstance(state, dict) else {}
        sid = session_id or str((st.get("session") or {}).get("id") or "")
        if self_receipts is None:
            from wg_core import CLAUDE_DIR
            self_receipts = _self_receipt().load_self_receipts(CLAUDE_DIR)
        from wg_verify_ledger import agent_receipt_key, receipts_of
        receipts = receipts_of(st, agent_receipt_key(sid, agent_id) if agent_id else sid) + list(self_receipts or [])
        keywords = [str(k) for k in (cfg.get("full_run_keywords") or DEFAULT_FULL_RUN_KEYWORDS)]
        slow = None
        if cmd.full:
            from wg_verify_ledger import reconcile_cfg
            large = int(cfg.get("large_suite_files", DEFAULT_LARGE_SUITE_FILES) or DEFAULT_LARGE_SUITE_FILES)
            files, cached = suite_files(state if isinstance(state, dict) else None, suite_roots(cmd, cwd), reconcile_cfg(config), large)
            if cached and sid:
                write_state(sid, state)
            slow = slow_reason(last_run_seconds(cmd, receipts, shell), files,
                               float(cfg.get("slow_run_s", DEFAULT_SLOW_RUN_S) or DEFAULT_SLOW_RUN_S), large)
        v = decide(cmd, _prompts(st), keywords, receipts, _own_mods(st, sid, agent_id), shell, slow)
        entry = {"session_id": sid, "agent_id": agent_id, "tool": tool_name, "cmd": command[:200], "rule": v.rule,
                 "full": cmd.full, "why": v.why[:200], "evidence": list(v.evidence)[:6]}
        if not v.owed:
            reason = {"reason": "small"} if v.why == WHY_SMALL else {}
            append_guard_log(GATE, {"event": "allowed", "allowed": True, **reason, **entry})
            return None
        deny, released = deny_cap(state if isinstance(state, dict) else None, GATE, [v.rule], cap=1, call=call)
        if isinstance(state, dict) and sid:
            write_state(sid, state)
        if released or (not deny and state is not None):
            append_guard_log(GATE, {"event": "released", "allowed": True, "release_rule": RULE_ONCE, **entry})
            try:
                sys.stderr.write(deny_message(v, True) + "\n")
            except OSError:
                pass
            return None
        append_guard_log(GATE, {"event": "denied", "allowed": False, **entry})
        return deny_message(v, False)
    except Exception as e:  # noqa: BLE001  閘自己壞不擋驗證；留帳＋stderr
        err = f"{type(e).__name__}: {e}"
        try:
            sys.stderr.write(f"{TAG} 檢查異常（放行，已留帳）：{err}\n")
        except OSError:
            pass
        try:
            from wg_core import append_guard_log
            append_guard_log(GATE, {"event": "error", "allowed": True, "rule": "GATE_SELF_ERROR", "session_id": session_id,
                                    "tool": tool_name, "cmd": command[:200], "error": err[:200]})
        except Exception:  # noqa: BLE001
            pass
        return None

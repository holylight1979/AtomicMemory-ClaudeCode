"""wg_verify_batch.py：驗證批次閘（PreToolUse Bash／PowerShell）——同一批改動只驗一次、整組驗證要使用者口令。

做什麼：使用者點名的三種浪費——①各別跑完後又跑全量 ②反覆跑個別驗證 ③全量跑完又跑全量——在跑之前擋下。
  1. 辨認驗證指令（lib/self_receipt 的解析）：pytest（含 python -m pytest）、run_verify.py、直接跑 verify_*.py／test_*.py／*_test.py。
     解析不了的（heredoc、eval、bash -c）不管、放行、不留帳。
  2. 批次指紋＝「上一次同一組指令跑綠」之後，本 session（子代理看自己的）有沒有新改動：
     收據（state verify_receipts 的 seq／自寫收據的時間）對 modified_files 的 last_seq／last_at。
  3. 三條規則：VERIFY_FULL_RUN_NEEDS_USER_ORDER、VERIFY_SAME_BATCH_ALREADY_GREEN、VERIFY_BATCH_BLOCK_ONCE_PER_TURN（RULES 登在
     hooks/wg_release_rules.py 檔尾）。擋訊息格式照 format_hit：`✗ (r) <規則名>：<一句現象>｜證據：<一行一證據>`。
  判定（decide）是純函式：不讀檔、不改 state；check 收事實（讀自寫收據、擋次帳）交 decide，擋下與放行都留帳 Logs/guard-verify_batch.jsonl。
怎麼跑案例：python -X utf8 -m pytest -q hooks/verify/verify_verify_batch.py
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, NamedTuple, Optional, Sequence, Tuple

from wg_release_rules import Verdict, format_hit

RULE_FULL = "VERIFY_FULL_RUN_NEEDS_USER_ORDER"
RULE_SAME = "VERIFY_SAME_BATCH_ALREADY_GREEN"
RULE_ONCE = "VERIFY_BATCH_BLOCK_ONCE_PER_TURN"
GATE = "verify_batch"
TAG = "[Guardian:VerifyBatch]"
LETTER = "r"
DEFAULT_FULL_RUN_KEYWORDS = ("整組", "全量", "全部測試", "run_verify")
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


def keyword_hit(prompts: Iterable[str], keywords: Iterable[str]) -> Optional[str]:
    """使用者原話（已濾掉背景通知、他 session 訊息）裡有沒有整組口令；不分大小寫子字串。"""
    for p in prompts:
        low = (p or "").lower()
        for k in keywords:
            if k and k.lower() in low:
                return k
    return None


def decide(cmd: VerifyCmd, prompts: Sequence[str], keywords: Sequence[str],
           receipts: Iterable[Dict[str, Any]], mods: Iterable[Dict[str, Any]], shell: str = "bash") -> Verdict:
    """純判定：owed=True 要擋。先看這批是不是已驗過（SAME），再看整組要不要口令（FULL）。"""
    mods = list(mods)
    green = last_green_same(cmd, receipts, shell)
    if green is not None:
        changed = edits_after(green, mods)
        if not changed:
            shown = " && ".join(" ".join((c[0], *c[1])) for c in cmd.key)
            return Verdict(RULE_SAME, True, "這批改動已驗證過",
                           (f"收據 {green.get('at')}", f"指令 {shown[:120]}", "結果 綠", f"之後改檔 0（本 session 改檔 {len(mods)}）"))
    if cmd.full:
        kw = keyword_hit(prompts, keywords)
        if not kw:
            return Verdict(RULE_FULL, True, "整組驗證要使用者本回合原話的口令",
                           ("本回合使用者原話沒有 " + "／".join(keywords), f"使用者原話 {len(prompts)} 則"))
        return Verdict(RULE_FULL, False, f"使用者口令「{kw}」")
    return Verdict(RULE_SAME, False, "第一次跑或上次之後有改檔" if green is None else "上次綠之後有改檔")


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


def deny_message(v: Verdict, released: bool) -> str:
    line = format_hit(LETTER, v)
    if released:
        return f"{TAG} {line}\n本回合這條規則已擋過一次，這次放行、留帳（規則 {RULE_ONCE}）。"
    fix = ("整組驗證只在使用者本回合原話有口令（guard.verify_batch.full_run_keywords）時跑；要驗自己這批改動就點名檔跑。"
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
        v = decide(cmd, _prompts(st), keywords, receipts, _own_mods(st, sid, agent_id), shell)
        entry = {"session_id": sid, "agent_id": agent_id, "tool": tool_name, "cmd": command[:200], "rule": v.rule,
                 "full": cmd.full, "why": v.why[:200], "evidence": list(v.evidence)[:6]}
        if not v.owed:
            append_guard_log(GATE, {"event": "allowed", "allowed": True, **entry})
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

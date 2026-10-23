"""state_rmw.py：hook 以外的寫者改 session state 的唯一入口——跟 hook 守同一把 state-<sid>.lock（規則 STATE_RMW_LOCKED）。

做什麼：update_state_locked(session_id, mutate)：鎖裡讀 → mutate(state) → 寫回；鎖、三方合併、待併帳全交 hooks/wg_core
（begin_state_rmw／read_state_status／write_state，hook 自己用的同一份）。等到期限仍拿不到鎖 → 照讀、寫回不整份覆蓋，
改留待併帳（state-<sid>.<時間>-<pid>.pending），下一支拿到鎖的 hook 照欄位分型併回。以前這些寫者自己 tmp→rename 整份覆蓋，
會把 hook 剛寫進去的那份蓋掉。回寫入結果，呼叫端（CLI、MCP 儀表板）才不會在 state 與待併帳都沒寫成時回成功。
寫者：背景萃取 worker（hooks/extract-worker.py、hooks/user-extract-worker.py、lib/ollama_extract_core.ack_then_clear）、
MCP 伺服器（tools/workflow-guardian-mcp/lib/state.js 的 applyStateChanges，Node 沒有同一種檔案鎖，spawn 本檔）。
怎麼跑（MCP 用）：python -m lib.state_rmw   stdin {"session_id": "...", "set": {"phase": "done", ...}}
  → stdout 一行 JSON {ok, outcome, state} 或 {ok:false, outcome?, error}；exit 0＝寫了／留了待併帳／沒有要改的，1＝其他。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict

_HOOKS_DIR = str(Path(__file__).resolve().parents[1] / "hooks")   # 本檔所在的樹的 hooks/（wg_core 在那裡）
OK_OUTCOMES = ("written", "pending", "unchanged")


def _comparable(state: Dict[str, Any]) -> str:
    return json.dumps({k: v for k, v in state.items() if k != "last_updated"}, ensure_ascii=False, sort_keys=True,
                      default=str)


def update_state_locked(session_id: str, mutate: Callable[[Dict[str, Any]], bool]) -> str:
    """鎖裡讀 → mutate(state) → 寫回，回寫入結果：
    written＝寫進 state 檔（別人寫過就三方合併；mutate 拿到的 dict 換成實際落盤的內容）；pending＝拿不到鎖或換不了檔，
    留了待併帳；unchanged＝mutate 回 False 或改完跟讀到的一樣（不寫）；missing＝state 不在或讀壞（不建新檔）；
    failed＝state 與待併帳都沒寫成（wg_core 已在 stderr＋guard log 浮訊號）。
    結果靠 wg_core 的帳判：寫成（含留帳）會把這支行程的基準（_STATE_READ_TEXT）推進到寫出的那份，留帳另記進 _OWN_PENDING；
    兩個都沒動＝沒寫成。已在 hook 模式的行程呼叫時不另開也不關（外層握著的鎖照握到外層結束）。"""
    if _HOOKS_DIR not in sys.path:
        sys.path.insert(0, _HOOKS_DIR)
    import wg_core
    nested = bool(wg_core._RMW.get("on"))
    if not nested:
        wg_core.begin_state_rmw()
    try:
        state, _status = wg_core.read_state_status(session_id)
        if not isinstance(state, dict):
            return "missing"
        before = _comparable(state)
        if mutate(state) is False or _comparable(state) == before:
            return "unchanged"
        key = str(wg_core.state_path((state.get("session") or {}).get("id") or session_id))   # write_state 照 session.id 轉址
        own_before = len(wg_core._OWN_PENDING.get(key, []))
        base_before = wg_core._STATE_READ_TEXT.get(key)
        wg_core.write_state(session_id, state)
        if len(wg_core._OWN_PENDING.get(key, [])) > own_before:
            return "pending"
        return "written" if wg_core._STATE_READ_TEXT.get(key) != base_before else "failed"
    finally:
        if not nested:
            wg_core.end_state_rmw()


def main() -> int:
    try:
        req = json.loads(sys.stdin.read() or "{}")
        session_id, changes = str(req.get("session_id") or ""), req.get("set")
        if not session_id or not isinstance(changes, dict):
            raise ValueError("need session_id and set{}")
    except (ValueError, AttributeError) as e:
        print(json.dumps({"ok": False, "error": f"bad input: {e}"}, ensure_ascii=False))
        return 1
    seen: Dict[str, Any] = {}

    def _apply(state: Dict[str, Any]) -> bool:
        state.update(changes)
        seen["state"] = state
        return True

    outcome = update_state_locked(session_id, _apply)
    if outcome not in OK_OUTCOMES:
        why = {"missing": f"state-{session_id}.json missing or unreadable",
               "failed": "state and pending record both failed to write (see stderr)"}.get(outcome, outcome)
        print(json.dumps({"ok": False, "outcome": outcome, "error": why}, ensure_ascii=False))
        return 1
    print(json.dumps({"ok": True, "outcome": outcome, "state": seen.get("state")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

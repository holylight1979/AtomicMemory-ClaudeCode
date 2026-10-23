"""state_rmw.py：hook 以外的寫者改 session state 的唯一入口——跟 hook 守同一把 state-<sid>.lock（規則 STATE_RMW_LOCKED）。

做什麼：update_state_locked(session_id, mutate)：鎖裡讀 → mutate(state) → 寫回；鎖、三方合併、待併帳全交 hooks/wg_core
（begin_state_rmw／read_state_status／write_state，hook 自己用的同一份）。等到期限仍拿不到鎖 → 照讀、寫回不整份覆蓋，
改留待併帳（state-<sid>.<時間>-<pid>.pending），下一支拿到鎖的 hook 照欄位分型併回。以前這些寫者自己 tmp→rename 整份覆蓋，
會把 hook 剛寫進去的那份蓋掉。
寫者：背景萃取 worker（hooks/extract-worker.py、hooks/user-extract-worker.py、lib/ollama_extract_core.ack_then_clear）、
MCP 伺服器（tools/workflow-guardian-mcp/lib/state.js 的 applyStateChanges，Node 沒有同一種檔案鎖，spawn 本檔）。
怎麼跑（MCP 用）：python -m lib.state_rmw   stdin {"session_id": "...", "set": {"phase": "done", ...}}
  → stdout 一行 JSON {ok, state} 或 {ok:false, error}；exit 0＝寫了（或留了待併帳）、1＝state 不在／讀壞／輸入不對。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict

_HOOKS_DIR = str(Path(__file__).resolve().parents[1] / "hooks")   # 本檔所在的樹的 hooks/（wg_core 在那裡）


def update_state_locked(session_id: str, mutate: Callable[[Dict[str, Any]], bool]) -> bool:
    """鎖裡讀 → mutate(state) → 寫回。mutate 回 False＝這次不用寫。state 不在或讀壞回 False（不建新檔）；
    寫回走 wg_core.write_state：鎖裡發現別人寫過就三方合併、拿不到鎖或換不了檔就留待併帳，訊號由它浮出（stderr＋guard log）。
    寫成功時 mutate 拿到的那個 dict 會換成實際落盤的內容（合併後的）。"""
    if _HOOKS_DIR not in sys.path:
        sys.path.insert(0, _HOOKS_DIR)
    import wg_core
    wg_core.begin_state_rmw()
    try:
        state, _status = wg_core.read_state_status(session_id)
        if not isinstance(state, dict):
            return False
        if mutate(state) is False:
            return True
        wg_core.write_state(session_id, state)
        return True
    finally:
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

    if not update_state_locked(session_id, _apply):
        print(json.dumps({"ok": False, "error": f"state-{session_id}.json missing or unreadable"}, ensure_ascii=False))
        return 1
    print(json.dumps({"ok": True, "state": seen["state"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

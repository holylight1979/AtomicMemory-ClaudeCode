"""
handlers/post_tool_batch.py — PostToolBatch hook handler（選配 #4：壓縮後 atom 內文復原 / 注入端）

PostToolBatch：一批（含並行）工具呼叫全解析後觸發一次，於下個 model request 前（CC 2.1.159+；
payload: tool_calls[]；反編譯實證支援 hookSpecificOutput.additionalContext）。

唯一職責：把 PostCompact stash 的 atom 復原內文「一次性」注入，閉合 mid-turn auto-compact 缺口
（壓縮後不一定有 UserPromptSubmit 可重 trigger，但隨後的工具批次會觸發本 hook）。
**每批都會跑** → idle 路徑必須極輕（讀 flag → early exit）。設計：plans/deep-wobbling-bentley.md。
"""

import sys
from typing import Any, Dict

from wg_core import _ensure_state, write_state, output_json, output_nothing


def handle_post_tool_batch(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    session_id = input_data.get("session_id", "")
    state = _ensure_state(session_id, input_data, config)
    # idle 極輕路徑：無 pending 立即退出（每批觸發，杜絕常態開銷）
    if not state or not state.get("pending_reinjection"):
        output_nothing()
        return

    try:
        blob = state.get("pending_reinjection_blob", "") or ""
        atoms = state.get("pending_reinjection_atoms", []) or []

        # 一次性：清 flag + blob
        state["pending_reinjection"] = False
        state.pop("pending_reinjection_blob", None)
        state.pop("pending_reinjection_atoms", None)
        # 復原名單 merge 回 injected_atoms（若 SessionStart(compact) 曾清空亦復原；
        # 維持 PostToolUse use 偵測 / Phase 2 效用歸因不中斷）
        if atoms:
            merged = list(dict.fromkeys((state.get("injected_atoms", []) or []) + atoms))
            state["injected_atoms"] = merged
        write_state(session_id, state)
    except Exception as e:
        print(f"[#4] post_tool_batch reinject error: {e}", file=sys.stderr)
        output_nothing()
        return

    if not blob:
        output_nothing()
        return

    output_json({
        "hookSpecificOutput": {
            "hookEventName": "PostToolBatch",
            "additionalContext": blob,
        }
    })

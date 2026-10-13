"""
handlers/post_tool_batch.py — PostToolBatch hook handler（選配 #4：壓縮後 atom 內文復原 / 注入端）

PostToolBatch：一批（含並行）工具呼叫全解析後觸發一次，於下個 model request 前（CC 2.1.159+；
payload: tool_calls[]；反編譯實證支援 hookSpecificOutput.additionalContext）。

職責：把 PostCompact stash 的 atom 復原內文、需求目標樹、部位綜觀「一次性」注入，閉合 mid-turn auto-compact 缺口
（壓縮後不一定有 UserPromptSubmit 可重 trigger，但隨後的工具批次會觸發本 hook）；另把需求目標流程的批次提醒
（讀入範圍變大、同檔改多次、PreToolUse 沒攔到的提問）合併成同一段送出。
**每批都會跑** → idle 路徑必須極輕（讀 flag → early exit）。設計：plans/deep-wobbling-bentley.md。
"""

import sys
from typing import Any, Dict

from wg_core import _ensure_state, write_state, output_json, output_nothing


def _need_goal_due(state: Dict[str, Any], input_data: Dict[str, Any]) -> bool:
    """需求目標的批次提醒要不要跑（只看 state 與這批的工具名，不讀目標檔）；模組載不進來 → stderr，當成不用跑。"""
    try:
        from wg_need_goal_points import batch_due
    except Exception as e:  # noqa: BLE001
        print(f"[NeedGoal] 需求目標模組載入失敗，批次提醒停用：{type(e).__name__}: {e}", file=sys.stderr)
        return False
    return batch_due(state, input_data.get("tool_calls"))


def handle_post_tool_batch(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    session_id = input_data.get("session_id", "")
    state = _ensure_state(session_id, input_data, config)
    # idle 極輕路徑：pending 皆無、需求目標也沒有待送立即退出（每批觸發，杜絕常態開銷）
    if not state or not (
        state.get("pending_reinjection") or state.get("pending_reinjection_overview") or state.get("pending_handoff_emit")
        or state.get("pending_reinjection_goal") or _need_goal_due(state, input_data)
    ):
        output_nothing()
        return

    parts: list = []
    try:
        ah = config.get("auto_handoff", {}) or {}

        # (1) 壓縮後 atom 內文復原（既有 #4 機制，一次性）
        if state.get("pending_reinjection"):
            blob = state.get("pending_reinjection_blob", "") or ""
            atoms = state.get("pending_reinjection_atoms", []) or []
            state["pending_reinjection"] = False
            state.pop("pending_reinjection_blob", None)
            state.pop("pending_reinjection_atoms", None)
            # 復原名單 merge 回 injected_atoms（若 SessionStart(compact) 曾清空亦復原；
            # 維持 PostToolUse use 偵測 / Phase 2 效用歸因不中斷）
            if atoms:
                merged = list(dict.fromkeys((state.get("injected_atoms", []) or []) + atoms))
                state["injected_atoms"] = merged
            if blob:
                parts.append(blob)

        # (1a) 壓縮後需求目標樹獨立重送（不依附部位綜觀）：排在 atom 內文後、綜觀前（綜觀的「主目標」指向它）；一次性 pop
        goal = state.pop("pending_reinjection_goal", None)
        if goal:
            parts.append(goal)

        # (1b) 壓縮後 OverviewHub 綜觀重注（A2.2／A2.3）：順序 atom 內文先、綜觀後；一次性 pop
        overview = state.pop("pending_reinjection_overview", None)
        state.pop("pending_reinjection_parts", None)
        if overview:
            parts.append(overview)

        # (2) Auto-Handoff 補全提示（Layer 3，與 (1) 合流同一 additionalContext）
        if state.get("pending_handoff_emit"):
            if ah.get("enabled", True) and ah.get("postbatch_emit", True):
                stub_path = state.get("handoff_stub_path", "") or "(staging)"
                parts.append(
                    f"[Auto-Handoff] 剛發生壓縮。已自動備妥 handoff stub 於 `{stub_path}`"
                    f"（客觀區塊已填）。請**補全其中 `TODO(模型補全)` 三區塊**"
                    f"（why / 做法 / 決策依據）使其達六區塊自足，"
                    f"確保下個 session `/continue` 無損接續。"
                )
            state["pending_handoff_emit"] = False  # 一次性，即使 config 關亦清旗標

        # (3) 需求目標的批次提醒（4.3 讀入範圍、同檔多次；4.4 PreToolUse 沒攔到的提問）：判不了只寫 stderr，不擋其他段
        if _need_goal_due(state, input_data):
            try:
                import wg_need_goal as _ng
                from wg_need_goal_points import batch_lines
                parts.extend(batch_lines(session_id, state, input_data.get("tool_calls"), _ng.cfg_of(config)))
            except Exception as e:  # noqa: BLE001
                print(f"[NeedGoal] post_tool_batch 提醒失敗（不擋）：{type(e).__name__}: {e}", file=sys.stderr)

        write_state(session_id, state)
    except Exception as e:
        print(f"[#4] post_tool_batch reinject error: {e}", file=sys.stderr)
        output_nothing()
        return

    if not parts:
        output_nothing()
        return

    output_json({
        "hookSpecificOutput": {
            "hookEventName": "PostToolBatch",
            "additionalContext": "\n\n".join(parts),
        }
    })

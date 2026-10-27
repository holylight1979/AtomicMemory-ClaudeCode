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

from wg_core import _ensure_state, write_state, output_json, output_nothing, v6_enabled, coding_turn


def _points_module() -> Any:
    """需求目標的批次模組；載不進來 → stderr 一行、回 None（這批的需求目標提醒全停）。"""
    try:
        import wg_need_goal_points
        return wg_need_goal_points
    except Exception as e:  # noqa: BLE001
        print(f"[NeedGoal] 需求目標模組載入失敗，批次提醒停用：{type(e).__name__}: {e}", file=sys.stderr)
        return None


def handle_post_tool_batch(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    session_id = input_data.get("session_id", "")
    state = _ensure_state(session_id, input_data, config)
    v6 = v6_enabled(config)     # 關＝只做 9e476fd0 就有的壓縮後 atom 復原與 handoff 提示
    # 子代理的工具批次（hook 輸入帶 agent_id）：目標樹是主 session 的——不送讀入範圍、同檔多次、提問、外部主張的提醒，
    # 壓縮後要重送的樹也留給主 session
    sub = bool(input_data.get("agent_id"))
    ngp = _points_module() if state and v6 and not sub and coding_turn(state, config) else None   # 規則 CODING_TURN_ONLY
    goal_due = bool(ngp) and ngp.batch_due(state, input_data.get("tool_calls"))
    # idle 極輕路徑：pending 皆無、需求目標也沒有待送立即退出（每批觸發，杜絕常態開銷；沒有目標檔的 session 只多一次 stat）
    if not state or not (
        state.get("pending_reinjection") or state.get("pending_handoff_emit")
        or (v6 and (state.get("pending_reinjection_overview") or (state.get("pending_reinjection_goal") and not sub)))
        or goal_due
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
        goal = state.pop("pending_reinjection_goal", None) if v6 and not sub else None
        if goal:
            parts.append(goal)

        # (1b) 壓縮後 OverviewHub 綜觀重注（A2.2／A2.3）：順序 atom 內文先、綜觀後；一次性 pop
        overview = state.pop("pending_reinjection_overview", None) if v6 else None
        if v6:
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
                    f"確保接手的 session 用 `/continue` 無損接續。"
                )
            state["pending_handoff_emit"] = False  # 一次性，即使 config 關亦清旗標

        # (3) 需求目標的批次提醒（4.3 讀入範圍、同檔多次、外部主張；4.4 提問審計與沒攔到的提問）：判不了只寫 stderr，不擋其他段
        if goal_due:
            try:
                import wg_need_goal as _ng
                parts.extend(ngp.batch_lines(session_id, state, input_data.get("tool_calls"),
                                             _ng.cfg_for_cwd(config, _ng.hook_cwd(input_data, state))))
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

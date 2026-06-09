"""
handlers/pre_compact.py — PreCompact hook handler

於 context 壓縮前生成 episodic atom（避免 SessionEnd 不觸發時失去 session 記憶）。
"""

import sys
from typing import Any, Dict

from wg_core import _ensure_state, output_nothing, write_state, _now_iso, resolve_staging_dir
from wg_episodic import _should_generate_episodic, _generate_episodic_atom
from wg_handoff import build_handoff_stub, should_write_stub


def handle_pre_compact(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    session_id = input_data.get("session_id", "")
    state = _ensure_state(session_id, input_data, config)
    if not state:
        output_nothing()
        return

    state["pre_compact_snapshot"] = _now_iso()
    # #4：快照壓縮前已注入 atom 名單，供 PostCompact 復原內文（免受 SessionStart(compact)
    # 清空 injected_atoms 的順序影響）。見 handlers/post_compact.py。
    state["pre_compact_injected_atoms"] = list(dict.fromkeys(state.get("injected_atoms", []) or []))

    if not state.get("episodic_checkpoint_done"):
        ep_cfg = config.get("episodic", {})
        if ep_cfg.get("auto_generate", True) and _should_generate_episodic(state, config):
            try:
                result = _generate_episodic_atom(session_id, state, config)
                if result:
                    state["episodic_checkpoint_done"] = True
                    print(f"[v2.22] episodic checkpoint: {result}", file=sys.stderr)
            except Exception as e:
                print(f"[v2.22] episodic checkpoint failed: {e}", file=sys.stderr)

    # ── Layer 2: Auto-Handoff stub（壓縮前自動備六區塊交接，核心保底）──
    # 壓縮真的發生 = 最可靠信號，不依賴 token 量測。客觀區塊自動填、主觀區塊留 TODO，
    # 由 Layer 3（post_tool_batch）注入提示叫模型補全。fail-open 不影響 PreCompact 主流程。
    ah = config.get("auto_handoff", {}) or {}
    if ah.get("enabled", True) and ah.get("precompact_stub", True):
        try:
            cwd = state.get("session", {}).get("cwd", "") or input_data.get("cwd", "")
            staging = resolve_staging_dir(cwd)
            stub_name = ah.get("stub_filename", "next-phase-auto.md")
            if should_write_stub(staging, state, stub_name):
                staging.mkdir(parents=True, exist_ok=True)
                (staging / stub_name).write_text(
                    build_handoff_stub(state, cwd), encoding="utf-8"
                )
                state["pending_handoff_emit"] = True
                state["handoff_stub_path"] = str(staging / stub_name)
                state["handoff_stub_at"] = _now_iso()
                print(f"[auto-handoff] stub written: {staging / stub_name}", file=sys.stderr)
        except Exception as e:
            print(f"[auto-handoff] precompact stub error: {e}", file=sys.stderr)

    write_state(session_id, state)
    output_nothing()

"""
handlers/pre_compact.py — PreCompact hook handler

於 context 壓縮前生成 episodic atom（避免 SessionEnd 不觸發時失去 session 記憶）。
"""

import sys
from typing import Any, Dict

from wg_core import _ensure_state, output_nothing, write_state, _now_iso
from wg_episodic import _should_generate_episodic, _generate_episodic_atom


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

    write_state(session_id, state)
    output_nothing()

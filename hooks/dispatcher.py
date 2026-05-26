"""
dispatcher.py — Workflow Guardian V5 主入口（取代 workflow-guardian.py 的 1640+ 行 dispatcher）

Claude Code hooks 的統一入口，從 stdin 讀取 JSON，根據 hook_event_name
分派到 handlers/ 目錄下對應 handler。

V5 設計：純路由 + main entry，無業務邏輯。所有 handler 在 handlers/。
"""

import json
import sys
from pathlib import Path

# 確保 hooks/ 在 sys.path（runpy.run_path 不會自動加）
sys.path.insert(0, str(Path(__file__).resolve().parent))

from wg_core import (
    WORKFLOW_DIR, load_config,
    _atom_debug_error,
)
from handlers import (
    handle_session_start,
    handle_user_prompt_submit,
    handle_pre_tool_use,
    handle_post_tool_use,
    handle_pre_compact,
    handle_stop,
    handle_session_end,
)


HANDLERS = {
    "SessionStart": handle_session_start,
    "UserPromptSubmit": handle_user_prompt_submit,
    "PreToolUse": handle_pre_tool_use,
    "PostToolUse": handle_post_tool_use,
    "PreCompact": handle_pre_compact,
    "Stop": handle_stop,
    "SessionEnd": handle_session_end,
}


def main():
    # Force UTF-8 output on Windows
    if sys.platform == "win32":
        sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', closefd=False)
        sys.stderr = open(sys.stderr.fileno(), mode='w', encoding='utf-8', closefd=False)

    WORKFLOW_DIR.mkdir(parents=True, exist_ok=True)

    try:
        raw = sys.stdin.buffer.read()
        input_data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    config = load_config()
    if not config.get("enabled", True):
        sys.exit(0)

    event = input_data.get("hook_event_name", "")
    handler = HANDLERS.get(event)
    if handler:
        try:
            handler(input_data, config)
        except Exception as e:
            print(f"[workflow-guardian] Error in {event}: {e}", file=sys.stderr)
            _atom_debug_error(f"workflow-guardian:{event}", e)
            sys.exit(0)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()

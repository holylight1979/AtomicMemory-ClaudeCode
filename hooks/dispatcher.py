"""
dispatcher.py — Workflow Guardian V5 主入口（取代 workflow-guardian.py 的 1640+ 行 dispatcher）

Claude Code hooks 的統一入口，從 stdin 讀取 JSON，根據 hook_event_name
分派到 handlers/ 目錄下對應 handler。

V5 設計：純路由 + main entry，無業務邏輯。所有 handler 在 handlers/。
"""

import importlib
import json
import os
import sys
from pathlib import Path

# 確保 hooks/ 在 sys.path（runpy.run_path 不會自動加）
sys.path.insert(0, str(Path(__file__).resolve().parent))

from wg_core import (
    WORKFLOW_DIR, load_config,
    _atom_debug_error,
)

# 惰性 import：event → (module, func)，只在該 event 觸發時 importlib 載入
# 對應 handler module，省下每次 hook（含最高頻 PostToolBatch/PreToolUse）付全量
# 9-handler import 傳遞稅（實測 ~520-639ms → ~120ms）。handlers/__init__.py 的
# __getattr__ 保 `from handlers import handle_X` 舊用法仍可用但同樣惰性。
HANDLERS = {
    "SessionStart": ("handlers.session_start", "handle_session_start"),
    "UserPromptSubmit": ("handlers.user_prompt_submit", "handle_user_prompt_submit"),
    "PreToolUse": ("handlers.pre_tool_use", "handle_pre_tool_use"),
    "PostToolUse": ("handlers.post_tool_use", "handle_post_tool_use"),
    "PreCompact": ("handlers.pre_compact", "handle_pre_compact"),
    "PostCompact": ("handlers.post_compact", "handle_post_compact"),        # 選配 #4
    "PostToolBatch": ("handlers.post_tool_batch", "handle_post_tool_batch"),  # 選配 #4
    "Stop": ("handlers.stop", "handle_stop"),
    "SessionEnd": ("handlers.session_end", "handle_session_end"),
}


def main():
    # 備援裁判子 session（judge_backend.run_claude_judge 起的 headless claude）內
    # 一律早退：那是隻唯讀的裁判，不該累積 state、注入記憶或被自家收尾閘擋住。
    if os.environ.get("CLAUDE_COMPANION_JUDGE"):
        sys.exit(0)

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
    spec = HANDLERS.get(event)
    if spec:
        try:
            module = importlib.import_module(spec[0])
            getattr(module, spec[1])(input_data, config)
        except Exception as e:
            print(f"[workflow-guardian] Error in {event}: {e}", file=sys.stderr)
            _atom_debug_error(f"workflow-guardian:{event}", e)
            sys.exit(0)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()

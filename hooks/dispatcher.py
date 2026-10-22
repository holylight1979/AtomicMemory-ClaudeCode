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
    WORKFLOW_DIR, load_config, v6_enabled,
    _atom_debug_error, begin_state_rmw, end_state_rmw,
)
import wg_hook_timing as hook_timing

# 惰性 import：event → (module, func)，只在該 event 觸發時 importlib 載入
# 對應 handler module，省下每次 hook（含最高頻 PostToolBatch/PreToolUse）付全量
# 9-handler import 傳遞稅（實測 ~520-639ms → ~120ms）。handlers/__init__.py 的
# __getattr__ 保 `from handlers import handle_X` 舊用法仍可用但同樣惰性。
HANDLERS = {
    "SessionStart": ("handlers.session_start", "handle_session_start"),
    "UserPromptSubmit": ("handlers.user_prompt_submit", "handle_user_prompt_submit"),
    "PreToolUse": ("handlers.pre_tool_use", "handle_pre_tool_use"),
    "PostToolUse": ("handlers.post_tool_use", "handle_post_tool_use"),
    "PostToolUseFailure": ("handlers.post_tool_use", "handle_post_tool_use_failure"),  # 工具失敗不送 PostToolUse：補記 Bash 寫檔
    "PreCompact": ("handlers.pre_compact", "handle_pre_compact"),
    "PostCompact": ("handlers.post_compact", "handle_post_compact"),        # 選配 #4
    "PostToolBatch": ("handlers.post_tool_batch", "handle_post_tool_batch"),  # 選配 #4
    "Stop": ("handlers.stop", "handle_stop"),
    "SubagentStop": ("handlers.stop", "handle_subagent_stop"),   # 子代理收尾只跑寫碼查核閘（對帳／量尺），擋滿放行留帳
    "SessionEnd": ("handlers.session_end", "handle_session_end"),
}

# 備援裁判子 session（judge_backend.run_claude_judge 起的 headless claude，env CLAUDE_COMPANION_JUDGE=1）：
# 不注入記憶、不跑其他閘（防裁判觸發裁判）；只留寫碼查核：PreToolUse 只擋「寫入目標判不出」（執行前就擋，不留永久欠帳），
# PostToolUse 做最小記帳（改了哪些檔、未知寫入、驗證收據），Stop 只跑對帳／量尺閘、沒人能回答放行詢問，擋滿放行留帳。其餘事件早退。
JUDGE_HANDLERS = {
    "PreToolUse": ("handlers.pre_tool_use", "handle_judge_pre_tool_use"),
    "PostToolUse": ("handlers.post_tool_use", "handle_judge_post_tool_use"),
    "PostToolUseFailure": ("handlers.post_tool_use", "handle_post_tool_use_failure"),
    "Stop": ("handlers.stop", "handle_judge_stop"),
}

# v6 守門總開關關閉（wg_core.v6_enabled）時：只分派 v6 以前（9e476fd0）就有的事件與工具；
# 裁判子 session、hook 分段計時也是 v6 才有，關閉時照舊一律早退／不計時。
PRE_V6_EVENTS = {"SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse",
                 "PreCompact", "PostCompact", "PostToolBatch", "Stop", "SessionEnd"}
PRE_V6_TOOLS = {   # 9e476fd0 settings.json 的 matcher；v6 加掛的工具（Read、PowerShell 後記、AskUserQuestion…）關閉時不進 handler
    "PreToolUse": {"Write", "Edit", "NotebookEdit", "Bash", "PowerShell", "Agent", "Task"},
    "PostToolUse": {"Edit", "Write", "MultiEdit", "NotebookEdit", "ExitPlanMode", "Bash", "Agent", "Task",
                    "mcp__workflow-guardian__anti_evasion_report", "mcp__workflow-guardian__atom_write",
                    "mcp__workflow-guardian__atom_retire", "mcp__workflow-guardian__knowledge_harvest_report"},
}


# 規則 STATE_RMW_LOCKED：每支 hook 讀到 state 就握這個 session 的鎖到 handler 結束；等鎖最多等到 hook 上限的這個比例
# （起點同分段計時＝行程建立），後一半留給 handler 跑完與超時降級（80%）。
STATE_LOCK_WAIT_RATIO = 0.5


def _state_lock_deadline(event: str, input_data: dict, timer) -> float:
    """等 state 鎖等到幾點（epoch 秒）：起點都是行程建立；有起表照它的上限，沒起表的事件（PostToolBatch、PostToolUseFailure、
    SubagentStop…）照 settings.json 這支 hook 的 timeout，讀不到當 5 秒。"""
    if timer:
        return timer.t0 + timer.limit_s * STATE_LOCK_WAIT_RATIO
    limit = hook_timing.settings_limit(event, str(input_data.get("tool_name") or "")) or 5.0
    return hook_timing._process_started() + limit * STATE_LOCK_WAIT_RATIO


def _pre_v6_skips(event: str, input_data: dict) -> bool:
    if event not in PRE_V6_EVENTS:
        return True
    tools = PRE_V6_TOOLS.get(event)
    return tools is not None and input_data.get("tool_name", "") not in tools


def main():
    judge = bool(os.environ.get("CLAUDE_COMPANION_JUDGE"))   # 事件名在 stdin 裡，讀完才知道走不走

    # Force UTF-8 output on Windows
    if sys.platform == "win32":
        sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', closefd=False)  # lf-exempt: 重包 stdio fd，不是檔案；hook 協定輸出不得改
        sys.stderr = open(sys.stderr.fileno(), mode='w', encoding='utf-8', closefd=False)  # lf-exempt: 重包 stdio fd，不是檔案；hook 協定輸出不得改

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
    v6 = v6_enabled(config)
    if not v6 and (judge or _pre_v6_skips(event, input_data)):
        sys.exit(0)
    spec = (JUDGE_HANDLERS if judge else HANDLERS).get(event)
    if spec:
        timer = hook_timing.start(event, input_data, config) if v6 else None   # Stop／PostToolUse 分段計時；過上限 80% 降級
        begin_state_rmw(_state_lock_deadline(event, input_data, timer))
        try:
            module = importlib.import_module(spec[0])
            hook_timing.lap("載入 handler")
            getattr(module, spec[1])(input_data, config)
        except Exception as e:
            print(f"[workflow-guardian] Error in {event}: {e}", file=sys.stderr)
            _atom_debug_error(f"workflow-guardian:{event}", e)
            sys.exit(0)
        finally:
            end_state_rmw()
            hook_timing.finish()
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()

"""
handlers/ — Workflow Guardian V5 event handlers

每個 hook event 對應一個 module。dispatcher.py 從本 package 載入 HANDLERS dict。
共用 regex/helper 在 _shared.py。
"""

from handlers.session_start import handle_session_start
from handlers.user_prompt_submit import handle_user_prompt_submit
from handlers.pre_tool_use import handle_pre_tool_use
from handlers.post_tool_use import handle_post_tool_use
from handlers.pre_compact import handle_pre_compact
from handlers.post_compact import handle_post_compact
from handlers.post_tool_batch import handle_post_tool_batch
from handlers.stop import handle_stop
from handlers.session_end import handle_session_end

__all__ = [
    "handle_session_start",
    "handle_user_prompt_submit",
    "handle_pre_tool_use",
    "handle_post_tool_use",
    "handle_pre_compact",
    "handle_post_compact",
    "handle_post_tool_batch",
    "handle_stop",
    "handle_session_end",
]

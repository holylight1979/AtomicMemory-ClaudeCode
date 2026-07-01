"""
handlers/ — Workflow Guardian V5 event handlers

每個 hook event 對應一個 module。dispatcher.py 以 importlib 惰性載入對應 module
（只在該 event 觸發時 import），避免每次 hook 付全量 handler import 傳遞稅
（實測 ~520-639ms → ~120ms）。共用 regex/helper 在 _shared.py。

本 __init__.py 的 __getattr__ 保 `from handlers import handle_X` 舊用法（測試/verify/
其他 caller）仍可用，但同樣惰性——只載入被存取名稱對應的 module（PEP 562，Py3.7+）。
"""
import importlib

_LAZY = {
    "handle_session_start": "handlers.session_start",
    "handle_user_prompt_submit": "handlers.user_prompt_submit",
    "handle_pre_tool_use": "handlers.pre_tool_use",
    "handle_post_tool_use": "handlers.post_tool_use",
    "handle_pre_compact": "handlers.pre_compact",
    "handle_post_compact": "handlers.post_compact",
    "handle_post_tool_batch": "handlers.post_tool_batch",
    "handle_stop": "handlers.stop",
    "handle_session_end": "handlers.session_end",
}

__all__ = list(_LAZY)


def __getattr__(name):
    target = _LAZY.get(name)
    if target is None:
        raise AttributeError(f"module 'handlers' has no attribute {name!r}")
    return getattr(importlib.import_module(target), name)

"""harness_text.py：把一則訊息裡 harness 注入的區塊剔掉，留下其餘文字（純函式；hooks 的 user_typed_text 與 Quote 清理共用）。

區塊＝HARNESS_TAGS 這些標籤成對包住的內容：
- 同名或異名巢狀照深度算，到最外層閉合為止才結束（內層的閉合標籤不會提早結束外層）。
- 閉合標籤允許空白（`</task-notification >`），標籤名不分大小寫；自閉合標籤（`<x/>`）只剔標籤本身。
- 沒閉合的區塊吃到字串尾：分不出後面哪段是使用者打的，寧可不認。
- 區塊外的孤立閉合標籤當普通文字留著。
"""
from __future__ import annotations

import re
from typing import List

HARNESS_TAGS = (
    "system-reminder", "task-notification", "cross-session-message",
    "ide_opened_file", "ide_selection", "ide_diagnostics",
    "command-name", "command-message", "command-args", "local-command-stdout", "browser_instruction",
)
_TAG_RE = re.compile(r"<\s*(/?)\s*(" + "|".join(re.escape(t) for t in HARNESS_TAGS) + r")\b[^>]*>", re.IGNORECASE)


def strip_harness_blocks(text: str, repl: str = " ") -> str:
    """剔掉所有 harness 區塊（規則見模組說明），每個區塊換成 repl。"""
    if not text:
        return ""
    out: List[str] = []
    stack: List[str] = []
    pos = 0                                           # 區塊外文字從哪裡開始
    for m in _TAG_RE.finditer(text):
        closing, name = m.group(1) == "/", m.group(2).lower()
        self_closing = m.group(0).rstrip(">").rstrip().endswith("/")
        if not stack:
            if closing:
                continue                              # 區塊外的孤立閉合標籤：普通文字
            out.append(text[pos:m.start()])
            if self_closing:
                out.append(repl)
                pos = m.end()
                continue
            stack.append(name)
            continue
        if self_closing:
            continue
        if not closing:
            stack.append(name)
            continue
        if name in stack:
            while stack.pop() != name:
                pass
        if not stack:
            out.append(repl)
            pos = m.end()
    out.append(repl if stack else text[pos:])        # 沒閉合 → 吃到字串尾
    return "".join(out)

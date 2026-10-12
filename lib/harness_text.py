"""harness_text.py：把一則訊息裡 harness 注入的區塊剔掉，留下其餘文字（純函式；hooks 的 user_typed_text、
UserPromptSubmit 入口剔 IDE 區塊、Quote 清理共用這一支）。

區塊＝下列標籤成對包住的內容：
- 標籤名完整比對（`<task-notification-example>` 不算），不分大小寫；標籤在引號外的 `>` 才結束，屬性值裡的 `>`、`/` 不算。
- 巢狀照深度算；閉合標籤只結束和最內層同名的那一層，和最內層不同名的閉合標籤當內容（保守：不提早結束任何區塊）。
- 閉合標籤允許空白（`</task-notification >`）；自閉合標籤（引號外結尾是 `/`）只剔標籤本身。
- 沒閉合的區塊吃到字串尾：分不出後面哪段是使用者打的，寧可不認。
- 區塊外的孤立閉合標籤當普通文字留著。
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Pattern, Tuple

HARNESS_TAG_NAMES = (r"system-reminder|task-notification|cross-session-message|ide_[a-z_]+|command-name|"
                     r"command-message|command-args|local-command-stdout|browser_instruction")
IDE_TAG_NAMES = r"ide_[a-z_]+"
_TAG_RES: Dict[str, Pattern[str]] = {}


def _tag_re(names: str) -> Pattern[str]:
    if names not in _TAG_RES:
        _TAG_RES[names] = re.compile(r"<\s*(/?)\s*(" + names + r")(?=[\s/>])", re.IGNORECASE)
    return _TAG_RES[names]


def _tag_end(text: str, i: int) -> Tuple[int, bool]:
    """從 i 往後找標籤結尾（引號外的 `>`）→ (結尾後一格, 是否自閉合)；找不到 → (字串長度, False)。"""
    quote, last = "", ""
    for j in range(i, len(text)):
        c = text[j]
        if quote:
            if c == quote:
                quote, last = "", c
        elif c in "\"'":
            quote = c
        elif c == ">":
            return j + 1, last == "/"
        elif not c.isspace():
            last = c
    return len(text), False


def strip_harness_blocks(text: str, repl: str = " ", names: Optional[str] = None) -> str:
    """剔掉 harness 區塊（規則見模組說明），每個區塊換成 repl；names 是標籤名的正則（預設 HARNESS_TAG_NAMES）。"""
    if not text:
        return ""
    out: List[str] = []
    stack: List[str] = []
    pos = 0          # 區塊外文字從哪裡開始
    seen_to = 0      # 已讀過的標籤到哪裡（屬性值裡的字不再當標籤）
    for m in _tag_re(names or HARNESS_TAG_NAMES).finditer(text):
        if m.start() < seen_to:
            continue
        closing, name = m.group(1) == "/", m.group(2).lower()
        end, self_closing = _tag_end(text, m.end())
        seen_to = end
        if not stack:
            if closing:
                continue                              # 區塊外的孤立閉合標籤：普通文字
            out.append(text[pos:m.start()])
            if self_closing:
                out.append(repl)
                pos = end
            else:
                stack.append(name)
            continue
        if self_closing:
            continue
        if not closing:
            stack.append(name)
        elif name == stack[-1]:
            stack.pop()
            if not stack:
                out.append(repl)
                pos = end
    out.append(repl if stack else text[pos:])        # 沒閉合 → 吃到字串尾
    return "".join(out)

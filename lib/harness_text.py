"""harness_text.py：把一則訊息裡 harness 注入的區塊剔掉，留下其餘文字（純函式；hooks 的 user_typed_text、
UserPromptSubmit 入口剔 IDE 區塊（only=IDE_TAG_NAMES）、Quote 清理共用這一支）。

區塊＝下列標籤成對包住的內容：
- 標籤名完整比對（`<task-notification-example>` 不算），不分大小寫；標籤在引號外的 `>` 才結束，屬性值裡的 `>`、`/` 不算。
- 巢狀照深度算；閉合標籤只結束和最內層同名的那一層，和最內層不同名的閉合標籤當內容（保守：不提早結束任何區塊）。
- 閉合標籤允許空白（`</task-notification >`）；自閉合標籤（引號外結尾是 `/`）只剔標籤本身。
- 沒閉合的區塊吃到字串尾：分不出後面哪段是使用者打的，寧可不認。
- 區塊外的孤立閉合標籤當普通文字留著。
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

HARNESS_TAG_NAMES = (r"system-reminder|task-notification|cross-session-message|ide_[a-z_]+|command-name|"
                     r"command-message|command-args|local-command-stdout|browser_instruction")
IDE_TAG_NAMES = r"ide_[a-z_]+"
_TAG_RE = re.compile(r"<\s*(/?)\s*(" + HARNESS_TAG_NAMES + r")(?=[\s/>])", re.IGNORECASE)


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


def strip_harness_blocks(text: str, repl: str = " ", only: Optional[str] = None) -> str:
    """剔掉 harness 區塊（規則見模組說明），每個區塊換成 repl。
    only：只剔最外層標籤名完整符合這個正則的區塊，其餘區塊原樣留著；巢狀與交錯照樣看所有 harness 標籤判斷，
    所以先用 only 剔一部分、再整則清理，和直接整則清理結果相同。"""
    if not text:
        return ""
    keep_re = re.compile(r"(?:" + only + r")\Z", re.IGNORECASE) if only else None
    out: List[str] = []
    stack: List[str] = []
    pos = 0          # 區塊外文字從哪裡開始
    seen_to = 0      # 已讀過的標籤到哪裡（屬性值裡的字不再當標籤）
    start, outer = 0, ""

    def block(end: int) -> str:
        return repl if keep_re is None or keep_re.match(outer) else text[start:end]

    for m in _TAG_RE.finditer(text):
        if m.start() < seen_to:
            continue
        closing, name = m.group(1) == "/", m.group(2).lower()
        end, self_closing = _tag_end(text, m.end())
        seen_to = end
        if not stack:
            if closing:
                continue                              # 區塊外的孤立閉合標籤：普通文字
            out.append(text[pos:m.start()])
            start, outer = m.start(), name
            if self_closing:
                out.append(block(end))
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
                out.append(block(end))
                pos = end
    out.append(block(len(text)) if stack else text[pos:])   # 沒閉合 → 吃到字串尾
    return "".join(out)

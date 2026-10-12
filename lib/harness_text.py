"""harness_text.py：從一則訊息取出「使用者本人打的字」（純函式；hooks 的權威判斷、UserPromptSubmit 入口剔 IDE 區塊、
Quote 與來源補填都用這一支，hooks 端 wg_core 只轉呼叫，不另存一份）。

harness 區塊＝下列標籤成對包住的內容：
- 標籤名完整比對（`<task-notification-example>` 不算），不分大小寫；標籤在引號外的 `>` 才結束，屬性值裡的 `>`、`/` 不算。
- 其他 Claude session 用 SendMessage 送來的 `<cross-session-message …>`：從開頭到第一個原樣 `</cross-session-message>`
  全部是同伴內容，裡面不解析任何標籤。依據（總控台 claude-2c 2026-10-12 實測）：Claude Code 只把同伴正文裡的
  `</cross-session-message>` 轉成 `<\\/cross-session-message>`，其他標籤（`</system-reminder>`、`<system-reminder>`、
  `</task-notification>`）原樣保留；所以第一個原樣閉合一定是真邊界，正文裡沒閉合的標籤也不能讓外層吃到字串尾。
- 其餘標籤巢狀照深度算；閉合標籤只結束和最內層同名的那一層，和最內層不同名的閉合標籤當內容（保守：不提早結束任何區塊）。
- 閉合標籤允許空白（`</task-notification >`）；自閉合標籤（引號外結尾是 `/`）只剔標籤本身。
- 沒閉合的區塊吃到字串尾：分不出後面哪段是使用者打的，寧可不認。
- 區塊外的孤立閉合標籤當普通文字留著（user_typed_text 會因為殘留標籤字樣整則不認）。
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

HARNESS_TAG_NAMES = (r"system-reminder|task-notification|cross-session-message|ide_[a-z_]+|command-name|"
                     r"command-message|command-args|local-command-stdout|browser_instruction")
IDE_TAG_NAMES = r"ide_[a-z_]+"
_PEER_TAG = "cross-session-message"
_TAG_RE = re.compile(r"<\s*(/?)\s*(" + HARNESS_TAG_NAMES + r")(?=[\s/>])", re.IGNORECASE)
_PEER_CLOSE_RE = re.compile(r"<\s*/\s*cross-session-message\s*>", re.IGNORECASE)
# 清理後還殘留的 harness 標籤字樣（開、閉，含同伴正文轉義的 `<\/名稱>`）：代表有區塊邊界被提早結束而漏出內容
_RESIDUE_TAG_RE = re.compile(r"<\s*\\?/?\s*(?:" + HARNESS_TAG_NAMES + r")(?=[\s/>])", re.IGNORECASE)
# 沒有標籤包住的系統通知標記行：這行起到訊息尾都是 harness 的說明與通知。只認自成一行的完整標記（不分大小寫，前後可空白）。
_SYSTEM_NOTIFICATION_RE = re.compile(r"^[ \t]*\[SYSTEM NOTIFICATION - NOT USER INPUT\][ \t]*\r?$",
                                     re.IGNORECASE | re.MULTILINE)
# hook 注入殘渣行（[Guardian:*] / [Atom:*] / [Session:Context] / [JIT:*] / [WG:*] 等 additionalContext 前綴，
# 允許行首空白、不分大小寫）：在空白折疊前逐行整行剔除，清理後的文字不會再被當成殘渣行。
HOOK_RESIDUE_LINE_RE = re.compile(
    r"^[ \t]*\[(?:Guardian|Atom|JIT|Session|Parallel|Workflow Guardian|WG|Role|AIDocs|"
    r"Context budget)[^\]]*\].*$",
    re.MULTILINE | re.IGNORECASE,
)


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
    seen_to = 0      # 已讀過的位置（標籤屬性、同伴正文裡的字不再當標籤）
    start, outer = 0, ""

    def block(end: int) -> str:
        return repl if keep_re is None or keep_re.match(outer) else text[start:end]

    for m in _TAG_RE.finditer(text):
        if m.start() < seen_to:
            continue
        closing, name = m.group(1) == "/", m.group(2).lower()
        end, self_closing = _tag_end(text, m.end())
        if name == _PEER_TAG and not closing and not self_closing:
            close = _PEER_CLOSE_RE.search(text, end)           # 同伴正文不解析：直接跳到第一個原樣閉合
            end = close.end() if close else len(text)
            seen_to = end
            if not stack:
                out.append(text[pos:m.start()])
                start, outer = m.start(), name
                out.append(block(end))
                pos = end
            continue
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


def user_typed_text(prompt: str, keep_lines: bool = False) -> str:
    """使用者本人打的字：剔掉 harness 區塊、系統通知標記行之後的內容、hook 殘渣行，空白折一格
    （keep_lines=True 時保留換行、只折行內空白，給要逐句看的萃取與 Quote 用）。
    清理後若還殘留任何 harness 標籤字樣（含 `<\\/名稱>`）→ 整則不認，回空字串：代表有區塊被提早結束而漏出內容，
    使用者自己打了標籤字樣也一併不認（要他單獨重打）。空字串＝這則不是使用者的話。
    口令、糾正、豁免、使用者決策、不要記、停用、失敗萃取、Quote 只吃這個結果（先清理、再截長）。清兩次結果不變。"""
    if not prompt:
        return ""
    text = strip_harness_blocks(prompt)
    m = _SYSTEM_NOTIFICATION_RE.search(text)
    text = HOOK_RESIDUE_LINE_RE.sub(" ", text[:m.start()] if m else text)
    if _RESIDUE_TAG_RE.search(text):
        return ""
    if not keep_lines:
        return re.sub(r"\s+", " ", text).strip()
    lines = (re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines())
    return "\n".join(ln for ln in lines if ln)

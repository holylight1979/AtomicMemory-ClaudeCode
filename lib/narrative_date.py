"""narrative_date.py：atom 知識行「敘事型日期」的唯一判式，tools/atom-date-lint.py（事後掃、--fix 清）與寫入閘（lib/atom_io）共用。

atom 收的是知識與經驗，不是某一個當下的流水帳；「使用者指正（2026-08-27）」「實踩（2026-10-05）」
這種日期每次注入都在浪費 token。判式：一行經 fix_line 會被改（剝掉日期或整行刪）＝帶敘事型日期。
不算的：metadata 行、標題、HTML 註解、code fence 內、反引號 code span 內；日期是句子的參照點（自／約／…後／起）
或日期本身就是知識（EOL／支援到／issue 編號／版本發布／資料區間）整行不動。舊式 `- Created:`／`- Updated:` 行
與變更記錄表格列算（lint 整行刪）。
寫入閘用 narrative_date_error（規則名 KNOWLEDGE_LINE_NO_NARRATIVE_DATE）；lint 用 fix_lines 逐行剝。
"""
from __future__ import annotations

import re
from typing import Iterable, List, Optional, Tuple

RULE_NAME = "KNOWLEDGE_LINE_NO_NARRATIVE_DATE"

META_PREFIX = (
    "- Scope:", "- Author:", "- Confidence:", "- Trigger:", "- Created-at:", "- Source:", "- Quote:",
    "- Status:", "- Related:", "- Last-used:", "- Depends:", "- Tags:", "- Audience:", "- Supersedes:",
    "- Pending-review-by:", "- Merge-strategy:", "- Confirmations:", "- ReadHits:",
)

# 日期 token：YYYY-MM-DD（可帶 ～MM-DD／～DD 區間）、YYYY-MM、YYYY年M月（D日）
DATE_TOKEN = re.compile(
    r"(?<![\w/.\\-])"
    r"(?:20\d\d-\d\d-\d\d(?:\s*[～~–\-]\s*(?:\d\d-)?\d\d)?"
    r"|20\d\d-\d\d(?![\d-])"
    r"|20\d\d年\d{1,2}月(?:\d{1,2}日)?)"
    r"(?![\w/\\-]|\.md|T\d)"
)
# 日期本身就是知識的句子：整行不動
KEEP_LINE = re.compile(r"EOL|支援到|截止|到期|issue\s*#|release|發布|Release|→\s*\d|累積|有效期|過期日|生效日")
# 整行刪：舊式建立／更新欄、變更記錄表格列
DROP_LINE = re.compile(r"^\s*(?:-\s*(?:Created|Updated):\s*20\d\d|\|\s*20\d\d-\d\d-\d\d\s*\|)")

# 日期後面的分隔符一起拿（「2026-09-18，svn 1.14.5」→「svn 1.14.5」）；前面只拿空白，逗號留著當分隔
_AFTER = re.compile(r"^(?:\s*[，,、]\s*|\s+)")
_BEFORE = re.compile(r"\s+$")
# 日期是句子的參照點（自／約／建於…之後／起／前）→ 拿掉會讓句子失去意義，整個 token 留著
_REF_BEFORE = re.compile(r"(?:自|約|建於|始於|從|於|到|至|截至)\s*$")
_REF_AFTER = re.compile(r"^\s*(?:後|起|前|以後|以前|之後|之前|當天|當日)")
_CJK = re.compile(r"[　-鿿＀-￯]")


def _strip_dates(line: str) -> str:
    """只動反引號之外的片段（偶數段），code span 裡的日期原樣保留。"""
    parts = line.split("`")
    for i in range(0, len(parts), 2):
        parts[i] = _strip_dates_segment(parts[i])
    return "`".join(parts)


def _strip_dates_segment(seg: str) -> str:
    out, pos = seg, 0
    while True:
        m = DATE_TOKEN.search(out, pos)
        if not m:
            return out
        head, tail = out[: m.start()], out[m.end():]
        if _REF_BEFORE.search(head) or _REF_AFTER.match(tail):
            pos = m.end()          # 參照型日期：跳過，找下一個
            continue
        head_stripped = _BEFORE.sub("", head)
        tail_stripped = _AFTER.sub("", tail)
        # 括號內只有日期 → 連括號一起拿掉：實踩（2026-10-05）：→ 實踩：
        if head_stripped.endswith(("（", "(")) and tail_stripped.startswith(("）", ")")):
            out = _join(head_stripped[:-1], tail_stripped[1:])
            continue
        # 括號開頭／結尾是日期 → 只拿日期：（2026-08-13 某專案實例）→（某專案實例）
        if head_stripped.endswith(("（", "(")) or tail_stripped.startswith(("）", ")")):
            out = head_stripped.rstrip("，,、") + tail_stripped
            continue
        out = _join(head_stripped, tail_stripped)


def _join(a: str, b: str) -> str:
    """接回兩段：中文對中文不留空白，其餘留一個空白（「使用者 2026-10-07 糾正」→「使用者糾正」、「user 2026-07 明確」→「user 明確」）。"""
    if not a or not b:
        return a + b
    if _CJK.match(a[-1]) and _CJK.match(b[0]):
        return a + b
    if a[-1] in "（(「『[*" or b[0] in "）)」』]：:，,、。":
        return a + b
    return a + " " + b


def fix_line(line: str, in_fence: bool) -> Tuple[Optional[str], bool]:
    """回 (新行 or None=刪除, 是否改動)。改動＝這行帶敘事型日期。"""
    s = line.strip()
    if in_fence or not s or s.startswith(META_PREFIX) or s.startswith("<!--") or s.startswith("#"):
        return line, False
    if KEEP_LINE.search(line):
        return line, False
    if DROP_LINE.match(line):
        return None, True
    if not DATE_TOKEN.search(line):
        return line, False
    new = _strip_dates(line)
    return new, new != line


def fix_lines(lines: Iterable[str]) -> Tuple[List[Tuple[str, Optional[str]]], List[str]]:
    """逐行跑 fix_line（追蹤 code fence）。回 (改動清單 [(舊行, 新行或 None)], 改後的行)。"""
    changes: List[Tuple[str, Optional[str]]] = []
    new_lines: List[str] = []
    in_fence = False
    for ln in lines:
        if ln.strip().startswith("```"):
            in_fence = not in_fence
            new_lines.append(ln)
            continue
        new, changed = fix_line(ln, in_fence)
        if changed:
            changes.append((ln, new))
        if new is not None:
            new_lines.append(new)
    return changes, new_lines


def narrative_date_error(lines: Iterable[str]) -> Optional[str]:
    """寫入閘：lines＝這次要寫進卡的知識行與行動行（照落檔的樣子渲染）。有敘事型日期回擋訊息，否則 None。"""
    changes, _ = fix_lines(lines)
    if not changes:
        return None
    more = f"（另有 {len(changes) - 1} 行同樣問題）" if len(changes) > 1 else ""
    return (f"{RULE_NAME}：知識行與行動行不准帶敘事日期；日期寫 Source 欄或 DevHistory，知識行只寫現況。"
            f"命中行：{changes[0][0].strip()[:120]}{more}")

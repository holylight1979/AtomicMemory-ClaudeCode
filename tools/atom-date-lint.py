#!/usr/bin/env python3
"""atom-date-lint.py — 找出（並可清掉）atom 知識行裡的敘事型日期戳。

atom 收的是知識與經驗，不是某一個當下的流水帳；「使用者指正（2026-08-27）」「實踩（2026-10-05）」
這種日期每次注入都在浪費 token。本工具掃 `_atom_index.json` 列出的每顆 atom（episodic／_distant 除外），
只動正文（metadata 行、標題、code fence 不碰），把敘事型日期拿掉、保留「日期本身就是知識」的句子
（EOL／支援到／issue 編號／版本發布／資料區間）。舊式 `- Created:`／`- Updated:` 行與變更記錄表格列整行刪除。

用法：
  python ~/.claude/tools/atom-date-lint.py            # 只列出會改的行（dry-run）
  python ~/.claude/tools/atom-date-lint.py --fix      # 實際改檔
  python ~/.claude/tools/atom-date-lint.py --check    # 有敘事型日期就 exit 1（給健檢用）
完整參數以 --help 為準。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CLAUDE_DIR = Path(__file__).resolve().parents[1]
INDEX = CLAUDE_DIR / "memory" / "_atom_index.json"

META_PREFIX = (
    "- Scope:", "- Author:", "- Confidence:", "- Trigger:", "- Created-at:", "- Source:", "- Quote:",
    "- Status:", "- Related:", "- Last-used:", "- Depends:", "- Tags:", "- Audience:", "- Supersedes:",
    "- Pending-review-by:", "- Merge-strategy:", "- Confirmations:", "- ReadHits:",
)
SKIP_PATH_MARKS = ("/episodic/", "/_distant/")

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
TABLE_HEADER = re.compile(r"^\s*\|.*\|\s*$")
TABLE_SEP = re.compile(r"^\s*\|(?:\s*:?-+:?\s*\|)+\s*$")

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


def _fix_line(line: str, in_fence: bool) -> tuple[str | None, bool]:
    """回 (新行 or None=刪除, 是否改動)。"""
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


def _drop_empty_tables(lines: list[str]) -> list[str]:
    """變更記錄表格的列全被刪掉後，只剩表頭＋分隔線 → 一起刪。"""
    out: list[str] = []
    i = 0
    while i < len(lines):
        if (i + 1 < len(lines) and TABLE_HEADER.match(lines[i]) and TABLE_SEP.match(lines[i + 1])
                and (i + 2 >= len(lines) or not TABLE_HEADER.match(lines[i + 2]))):
            i += 2
            continue
        out.append(lines[i])
        i += 1
    return out


def process(path: Path) -> tuple[list[tuple[str, str | None]], str | None]:
    """回 (改動清單 [(舊行, 新行或 None)], 新內容或 None=不變)。保留原行尾。"""
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(nl)
    changes: list[tuple[str, str | None]] = []
    new_lines: list[str] = []
    in_fence = False
    for ln in lines:
        if ln.strip().startswith("```"):
            in_fence = not in_fence
            new_lines.append(ln)
            continue
        new, changed = _fix_line(ln, in_fence)
        if changed:
            changes.append((ln, new))
        if new is not None:
            new_lines.append(new)
    if not changes:
        return [], None
    new_lines = _drop_empty_tables(new_lines)
    return changes, nl.join(new_lines)


def indexed_atoms() -> list[Path]:
    data = json.loads(INDEX.read_text(encoding="utf-8"))
    paths = []
    for a in data.get("atoms", []):
        p = Path(a["path"])
        if not p.is_absolute():
            p = CLAUDE_DIR / p
        s = p.as_posix()
        if any(m in s for m in SKIP_PATH_MARKS) or not p.is_file():
            continue
        paths.append(p)
    return paths


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--fix", action="store_true", help="實際改檔（預設只列出）")
    ap.add_argument("--check", action="store_true", help="有敘事型日期就 exit 1，不印細節")
    ap.add_argument("--path", nargs="*", help="只處理這些 atom 檔（預設：索引內全部）")
    args = ap.parse_args()
    paths = [Path(p) for p in args.path] if args.path else indexed_atoms()
    total_files = total_lines = 0
    for p in paths:
        changes, new_text = process(p)
        if not changes:
            continue
        total_files += 1
        total_lines += len(changes)
        if not args.check:
            print(f"== {p.relative_to(CLAUDE_DIR).as_posix()}")
            for old, new in changes:
                print(f"  - {old.strip()[:110]}")
                print(f"  + {(new or '<刪除整行>').strip()[:110]}")
        if args.fix and new_text is not None:
            p.write_bytes(new_text.encode("utf-8"))
    verb = "已改" if args.fix else "會改"
    print(f"{verb} {total_files} 檔 / {total_lines} 行（episodic／_distant 不掃）")
    return 1 if (args.check and total_lines) else 0


if __name__ == "__main__":
    sys.exit(main())

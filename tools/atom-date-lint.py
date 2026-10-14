#!/usr/bin/env python3
"""atom-date-lint.py — 找出（並可清掉）atom 知識行裡的敘事型日期戳。

atom 收的是知識與經驗，不是某一個當下的流水帳；「使用者指正（2026-08-27）」「實踩（2026-10-05）」
這種日期每次注入都在浪費 token。本工具掃 `_atom_index.json` 列出的每顆 atom（episodic／_distant 除外），
只動正文（metadata 行、標題、code fence 不碰），把敘事型日期拿掉、保留「日期本身就是知識」的句子
（EOL／支援到／issue 編號／版本發布／資料區間）。舊式 `- Created:`／`- Updated:` 行與變更記錄表格列整行刪除。
判式在 lib/narrative_date（寫入閘 KNOWLEDGE_LINE_NO_NARRATIVE_DATE 用同一份），本檔只管掃檔、列出與 --fix。

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

CODE_DIR = Path(__file__).resolve().parents[1]   # 程式碼根（本檔所在的樹）
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))
from lib.narrative_date import fix_line, fix_lines  # noqa: E402,F401  判式單一來源；fix_line 給 verify 直接測
from lib.project_root import claude_data_dir  # noqa: E402
CLAUDE_DIR = claude_data_dir()   # 使用者資料根（WG_CLAUDE_DIR 或 ~/.claude），和 hooks 同一支算法
INDEX = CLAUDE_DIR / "memory" / "_atom_index.json"

SKIP_PATH_MARKS = ("/episodic/", "/_distant/")
TABLE_HEADER = re.compile(r"^\s*\|.*\|\s*$")
TABLE_SEP = re.compile(r"^\s*\|(?:\s*:?-+:?\s*\|)+\s*$")


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
    changes, new_lines = fix_lines(text.split(nl))
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

#!/usr/bin/env python3
"""changelog-roll.py — _CHANGELOG.md auto-roll.

保留主檔最新 N 條 table rows，其餘 append 到 _CHANGELOG_ARCHIVE.md（新→舊序）。
Header + 非表格 preamble 原樣留主檔。原子寫入 tmp → rename。

Usage:
    python tools/changelog-roll.py [--keep N] [--dry-run] [--quiet]
    python tools/changelog-roll.py --changelog PATH --archive PATH   # 測試用

Exit codes:
    0: 成功（含 nothing-to-roll）
    2: 解析失敗 / I/O 錯誤（不動任何檔）
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

CLAUDE_DIR = Path.home() / ".claude"
DEFAULT_CHANGELOG = CLAUDE_DIR / "_AIDocs" / "_CHANGELOG.md"
DEFAULT_ARCHIVE = CLAUDE_DIR / "_AIDocs" / "_CHANGELOG_ARCHIVE.md"
DEFAULT_KEEP = 8

TABLE_HEADER_RE = re.compile(r"^\|\s*日期\s*\|\s*變更\s*\|\s*(涉及檔案|主要檔案|檔案)\s*\|\s*$")
TABLE_SEP_RE = re.compile(r"^\|\s*-+\s*\|\s*-+\s*\|\s*-+\s*\|\s*$")
DATA_ROW_RE = re.compile(r"^\|\s*(\d{4}-\d{2}-\d{2})\s*\|.*\|.*\|\s*$")

ARCHIVE_SHELL = """# 變更記錄 — 封存

> 從 `_CHANGELOG.md` 滾動淘汰的歷史記錄。

---

| 日期 | 變更 | 涉及檔案 |
|------|------|---------|
"""


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _atomic_write(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8", newline="\n")
    os.replace(str(tmp), str(path))


def _split_preamble_and_table(text: str) -> Tuple[str, int, int, List[str]]:
    """Return (preamble_text, header_line_idx, separator_line_idx, data_rows).

    preamble_text 含 header/separator 之前的所有行（保留原 trailing newline）。
    data_rows 不含 header / separator。
    Raises ValueError if no table found.
    """
    lines = text.splitlines(keepends=True)
    header_idx = -1
    for i, ln in enumerate(lines):
        if TABLE_HEADER_RE.match(ln.rstrip("\n")):
            header_idx = i
            break
    if header_idx < 0:
        raise ValueError("table header '| 日期 | 變更 | 涉及檔案 |' not found")
    if header_idx + 1 >= len(lines) or not TABLE_SEP_RE.match(lines[header_idx + 1].rstrip("\n")):
        raise ValueError(f"table separator not found after header at line {header_idx + 1}")
    sep_idx = header_idx + 1
    preamble = "".join(lines[:header_idx])
    data_rows: List[str] = []
    for ln in lines[sep_idx + 1:]:
        stripped = ln.rstrip("\n")
        if not stripped.strip():
            continue  # 跳空行，表格後不應有，但 defensive
        if DATA_ROW_RE.match(stripped):
            data_rows.append(stripped)
        else:
            # 遇到非 data row → 視為表格結束
            break
    return preamble, header_idx, sep_idx, data_rows


def _extract_date(row: str) -> str:
    m = DATA_ROW_RE.match(row)
    return m.group(1) if m else "0000-00-00"


def _sort_rows_desc(rows: List[str]) -> List[str]:
    return sorted(rows, key=_extract_date, reverse=True)


def _build_main(preamble: str, kept_rows: List[str]) -> str:
    header = "| 日期 | 變更 | 涉及檔案 |\n"
    sep = "|------|------|---------|\n"
    body = "\n".join(kept_rows) + "\n" if kept_rows else ""
    return preamble + header + sep + body


def _merge_into_archive(archive_path: Path, new_rows: List[str]) -> str:
    """Prepend new_rows to archive table data rows (keep newest-first)."""
    if not archive_path.exists():
        archive_text = ARCHIVE_SHELL
    else:
        archive_text = _read(archive_path)
    try:
        preamble, _h, _s, existing_rows = _split_preamble_and_table(archive_text)
    except ValueError:
        # Archive malformed → rebuild shell and stash existing content at end
        sys.stderr.write(
            f"[changelog-roll] WARN: archive {archive_path} 表格結構異常，重建並保留原內容於檔尾\n"
        )
        preamble = ARCHIVE_SHELL.rsplit("| 日期 |", 1)[0]
        existing_rows = []
        trailer = "\n\n---\n<!-- 原檔內容保留（格式異常） -->\n" + archive_text
    else:
        trailer = ""
    merged = _sort_rows_desc(new_rows + existing_rows)
    header = "| 日期 | 變更 | 涉及檔案 |\n"
    sep = "|------|------|---------|\n"
    body = "\n".join(merged) + "\n"
    return preamble + header + sep + body + trailer


def roll(
    changelog_path: Path = DEFAULT_CHANGELOG,
    archive_path: Path = DEFAULT_ARCHIVE,
    keep: int = DEFAULT_KEEP,
    dry_run: bool = False,
    quiet: bool = False,
) -> Tuple[int, int]:
    """Perform the roll. Return (kept_count, moved_count)."""
    if not changelog_path.exists():
        raise FileNotFoundError(f"changelog not found: {changelog_path}")
    text = _read(changelog_path)
    preamble, _h, _s, data_rows = _split_preamble_and_table(text)
    rows_sorted = _sort_rows_desc(data_rows)
    if len(rows_sorted) <= keep:
        if not quiet:
            print(
                f"[changelog-roll] Nothing to roll "
                f"(當前 {len(rows_sorted)} 條 ≤ 保留 {keep} 條)"
            )
        return len(rows_sorted), 0

    kept = rows_sorted[:keep]
    moved = rows_sorted[keep:]

    if dry_run:
        if not quiet:
            print(
                f"[changelog-roll] DRY-RUN: 會留 {len(kept)} 條 / "
                f"會搬 {len(moved)} 條到 {archive_path.name}"
            )
            print(f"  最舊搬出日期: {_extract_date(moved[-1])}")
            print(f"  最新搬出日期: {_extract_date(moved[0])}")
        return len(kept), len(moved)

    new_main = _build_main(preamble, kept)
    new_archive = _merge_into_archive(archive_path, moved)

    _atomic_write(changelog_path, new_main)
    _atomic_write(archive_path, new_archive)

    if not quiet:
        print(
            f"[changelog-roll] 主檔 {len(kept)} 條 / "
            f"搬 {len(moved)} 條到 {archive_path.name}"
        )
    return len(kept), len(moved)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--keep", type=int, default=DEFAULT_KEEP)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--changelog", type=Path, default=DEFAULT_CHANGELOG)
    p.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    args = p.parse_args(argv)
    try:
        roll(
            changelog_path=args.changelog,
            archive_path=args.archive,
            keep=args.keep,
            dry_run=args.dry_run,
            quiet=args.quiet,
        )
        return 0
    except (ValueError, FileNotFoundError, OSError) as e:
        sys.stderr.write(f"[changelog-roll] ERROR: {e}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())

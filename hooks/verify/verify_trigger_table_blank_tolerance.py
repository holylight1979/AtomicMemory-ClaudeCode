"""verify_trigger_table_blank_tolerance.py — index 表 parser 空行容忍。

防 2026-05 silent-failure 真因再現：寫入端在 `| Atom |` / `| # |` 表內留下一個
空行 → 舊 parser 即判表結束、silent 掉後續所有 atom（trigger 注入全死）。
本測鎖死 direction 1（parser 容忍空行 + skip 重複表頭、真內容才結束表）。
參考：_AIDocs/Failures/memory-pipeline-silent-failure-2026-05.md
"""
from __future__ import annotations

import sys
from pathlib import Path

VERIFY_DIR = Path(__file__).resolve().parent
CLAUDE = VERIFY_DIR.parent.parent
HOOKS = CLAUDE / "hooks"
for p in (str(CLAUDE), str(HOOKS)):
    if p not in sys.path:
        sys.path.insert(0, p)

from wg_atoms import _parse_trigger_table  # noqa: E402

HEADER = "| Atom | 說明 |\n|------|------|\n"


def _names(text: str):
    return [a[0] for a in _parse_trigger_table(text)]


def test_compact_table_all_rows():
    text = HEADER + "| a1 | p1 | t1 |\n| a2 | p2 | t2 |\n| a3 | p3 | t3 |"
    assert _names(text) == ["a1", "a2", "a3"]


def test_internal_blank_line_drops_nothing():
    """核心回歸：表中一個空行不得 silent 掉後續 atom。"""
    text = HEADER + "| a1 | p1 | t1 |\n\n| a2 | p2 | t2 |\n| a3 | p3 | t3 |"
    assert _names(text) == ["a1", "a2", "a3"]


def test_multiple_blank_lines_tolerated():
    text = HEADER + "| a1 | p1 | t1 |\n\n\n| a2 | p2 | t2 |"
    assert _names(text) == ["a1", "a2"]


def test_real_content_ends_table():
    """空行後接真內容（新區段）才視為表結束，不誤收其後的 | row。"""
    text = HEADER + "| a1 | p1 | t1 |\n\n## 下一節\n| 不該收 | x | y |"
    assert _names(text) == ["a1"]


def test_repeated_header_not_captured_as_atom():
    """多區塊表：重複表頭被 skip，不誤收為名為 'Atom' 的假 atom。"""
    text = (HEADER + "| a1 | p1 | t1 |\n\n"
            + HEADER + "| a2 | p2 | t2 |")
    names = _names(text)
    assert names == ["a1", "a2"], names
    assert "Atom" not in names


def test_real_global_index_non_zero():
    """真實 memory/_ATOM_INDEX.md 仍能解析出非零 atom（不回歸）。"""
    idx = CLAUDE / "memory" / "_ATOM_INDEX.md"
    if not idx.exists():
        return
    text = idx.read_text(encoding="utf-8-sig")
    assert len(_parse_trigger_table(text)) > 0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("all passed")

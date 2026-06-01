"""verify_memory_index_caption_preserve.py — sync-memory-index 保留人工策展描述

回歸鎖（覆轍：atom_write(global) → server.js syncMemoryIndex → sync-memory-index.py
--write → extract_atom_caption 讀 H1；funnel 建立的 atom H1=裸 kebab-name → 把
MEMORY.md 手寫描述沖回裸名）。修法：regen 時若 H1 caption 退化成裸名/空，沿用
現有較豐富的描述。精準度：描述性 H1 > 現有人工描述 > 裸名。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

CLAUDE_DIR = Path(__file__).resolve().parent.parent.parent  # tools/verify/ → ~/.claude/
SPEC = importlib.util.spec_from_file_location(
    "sync_memory_index", CLAUDE_DIR / "tools" / "sync-memory-index.py"
)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def _write_atom(root: Path, name: str, h1: str) -> None:
    (root / f"{name}.md").write_text(
        f"# {h1}\n\n- Confidence: [臨]\n", encoding="utf-8"
    )


def test_bare_h1_preserves_existing_caption(tmp_path: Path):
    """H1=裸名 + 現有有描述 → 保留人工描述（核心覆轍防護）。"""
    _write_atom(tmp_path, "foo", "foo")  # H1 == name → 裸名
    rows = [("foo", "foo.md", "global")]
    out = MOD.render_atom_section(rows, tmp_path, {"foo": "豐富的人工描述"})
    assert "| foo | 豐富的人工描述 |" in out


def test_bare_h1_no_existing_falls_back_to_bare(tmp_path: Path):
    """H1=裸名 + 無現有 → 裸名（新 atom 尚未策展的合理預設）。"""
    _write_atom(tmp_path, "foo", "foo")
    rows = [("foo", "foo.md", "global")]
    out = MOD.render_atom_section(rows, tmp_path, {})
    assert "| foo | foo |" in out


def test_descriptive_h1_wins_over_existing(tmp_path: Path):
    """描述性 H1 優先於現有人工描述（H1 是更權威的真源）。"""
    _write_atom(tmp_path, "foo", "描述性標題")
    rows = [("foo", "foo.md", "global")]
    out = MOD.render_atom_section(rows, tmp_path, {"foo": "舊的人工描述"})
    assert "| foo | 描述性標題 |" in out


def test_parse_existing_skips_header_and_separator(tmp_path: Path):
    """parse_existing_captions 跳過表頭/分隔列，只收真正的 atom 列。"""
    mem = tmp_path / "MEMORY.md"
    mem.write_text(
        "# Atom Index\n\n| Atom | 說明 |\n|------|------|\n"
        "| foo | 描述A |\n| bar | bar |\n",
        encoding="utf-8",
    )
    caps = MOD.parse_existing_captions(mem)
    assert caps == {"foo": "描述A", "bar": "bar"}
    assert "Atom" not in caps

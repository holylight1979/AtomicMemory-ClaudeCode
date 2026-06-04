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
    out = MOD.render_core_section(rows, tmp_path, {"foo": "豐富的人工描述"})
    assert "| foo | 豐富的人工描述 |" in out


def test_bare_h1_no_existing_falls_back_to_bare(tmp_path: Path):
    """H1=裸名 + 無現有 → 裸名（新 atom 尚未策展的合理預設）。"""
    _write_atom(tmp_path, "foo", "foo")
    rows = [("foo", "foo.md", "global")]
    out = MOD.render_core_section(rows, tmp_path, {})
    assert "| foo | foo |" in out


def test_descriptive_h1_wins_over_existing(tmp_path: Path):
    """描述性 H1 優先於現有人工描述（H1 是更權威的真源）。"""
    _write_atom(tmp_path, "foo", "描述性標題")
    rows = [("foo", "foo.md", "global")]
    out = MOD.render_core_section(rows, tmp_path, {"foo": "舊的人工描述"})
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


# ─── V5+ Realm：local atom 抽到側檔 _local_catalog.md（跨錯界修復） ───────────────


def _write_local_atom(root: Path, domain: str, name: str, h1: str) -> None:
    d = root / "_AIDocs" / "_atoms" / domain
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.md").write_text(f"# {h1}\n\n- Confidence: [臨]\n", encoding="utf-8")


def test_local_realm_atom_split_core_vs_side(tmp_path: Path):
    """local atom（path 落 _AIDocs/_atoms/<domain>/）抽出 core 主表 → 進側檔 catalog、依 domain 分組。
    core 段：含 core atom、不含 local 明細、不含 ## 本地範疇 標題、末尾留指標。"""
    _write_atom(tmp_path, "core-note", "核心筆記")
    _write_local_atom(tmp_path, "Tools", "gizmo-tool", "Gizmo 工具踩坑")
    rows = [
        ("core-note", "core-note.md", "global"),
        ("gizmo-tool", "_AIDocs/_atoms/Tools/gizmo-tool.md", "global"),
    ]
    core = MOD.render_core_section(rows, tmp_path, {})
    local = MOD.render_local_catalog(rows, tmp_path, {})
    # core（= @import 的 MEMORY.md）：local 明細不外漏
    assert "| core-note | 核心筆記 |" in core
    assert "gizmo-tool" not in core
    assert "## 本地範疇" not in core
    assert "_local_catalog.md" in core              # 指標（discoverability）
    # 側檔 catalog：local atom 依 domain 分組
    assert local and "### Tools" in local
    assert "| gizmo-tool | Gizmo 工具踩坑 |" in local
    assert "core-note" not in local                 # core 不進側檔


def test_no_local_atoms_no_pointer_no_side(tmp_path: Path):
    """無 local atom → core 無指標、無「本地範疇」標題；側檔 render 回 ""（caller 據此移除殘留）。"""
    _write_atom(tmp_path, "core-note", "核心筆記")
    rows = [("core-note", "core-note.md", "global")]
    core = MOD.render_core_section(rows, tmp_path, {})
    assert "## 本地範疇" not in core
    assert "_local_catalog.md" not in core
    assert MOD.render_local_catalog(rows, tmp_path, {}) == ""


def test_local_realm_bare_h1_preserves_existing_caption(tmp_path: Path):
    """local atom H1 退化成裸名 → 側檔沿用現有人工描述（與一般 atom 同 preserve 規則）。"""
    _write_local_atom(tmp_path, "World", "world-thing", "world-thing")  # H1==name → 裸名
    rows = [("world-thing", "_AIDocs/_atoms/World/world-thing.md", "global")]
    local = MOD.render_local_catalog(rows, tmp_path, {"world-thing": "腦內世界某機制"})
    assert "| world-thing | 腦內世界某機制 |" in local

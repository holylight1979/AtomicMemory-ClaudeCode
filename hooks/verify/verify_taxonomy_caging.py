"""verify_taxonomy_caging.py — 地基安全證成（_drafts 內部 taxonomy 引擎）。

釘死「軸1 歸夾 = 牢籠內子夾移動」不觸發軸2(晉升)/軸3(學詞)/軸4(注入+索引)。
不喚 LLM、不打真索引、不碰真磁碟 memory（全 tmp_path）。pytest。

對映 memory/_staging/next-phase-draft-taxonomy-engine.md §4 不變式：
  INV-DRAFT-STAYS-CAGED / INV-NO-INDEX-FOR-DRAFT / INV-SETREALM-CONFIDENCE-FROZEN /
  INV-NO-LEXICON-WRITE / INV-PROJECTS-NOT-CROSS-PROJECT / INV-CORE-PROTECTED-UNTOUCHED
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

VERIFY_DIR = Path(__file__).resolve().parent     # hooks/verify/
CLAUDE = VERIFY_DIR.parent.parent                # → ~/.claude
if str(CLAUDE) not in sys.path:
    sys.path.insert(0, str(CLAUDE))

from lib.taxonomy_jury import (  # noqa: E402
    BY_CLASS, CAGE_SEGMENT, CageEscapeError, cage_assert, relocate_within_cage,
)
from lib.game_taxonomy import (  # noqa: E402
    GAME_TAXONOMY_SEED, TAXONOMY_CATCHALL, seed_slugs,
)
from lib.atom_locations import (  # noqa: E402
    CROSS_PROJECT_LOCAL_DOMAINS, LOCAL_REALM_CORE_PROTECTED_PREFIXES,
)

DRAFT_TEXT = (
    "# foo\n\n"
    "- Author: auto-captured\n"
    "- Confidence: [臨]\n"
    "- Trigger: 測試, draft\n\n"
    "## 知識\n\n- [臨] 一條測試碎片內容\n"
)


def _make_draft(memory_dir: Path) -> Path:
    d = memory_dir / "_drafts" / "auto-capture"
    d.mkdir(parents=True, exist_ok=True)
    f = d / "foo.md"
    f.write_text(DRAFT_TEXT, encoding="utf-8")
    return f


# ── 軸4：draft 永不離開 _drafts（不入索引/注入面）─────────────────────────
def test_relocate_stays_in_drafts(tmp_path):
    mem = tmp_path / "memory"
    draft = _make_draft(mem)
    target = relocate_within_cage(draft, mem)
    rel = target.relative_to(mem)
    assert CAGE_SEGMENT in rel.parts               # 仍在牢籠
    assert BY_CLASS in rel.parts
    assert rel.parts[-2] == TAXONOMY_CATCHALL      # 全填 _Unsorted
    assert target.exists() and not draft.exists()


def test_cage_assert_blocks_escape(tmp_path):
    mem = tmp_path / "memory"
    mem.mkdir(parents=True)
    escape = mem / "_AIDocs" / "_atoms" / "projects" / "Foo" / "foo.md"
    with pytest.raises(CageEscapeError):
        cage_assert(escape, mem)


def test_relocate_refuses_escape_target(tmp_path, monkeypatch):
    """即使有人改 _drafts_root 邏輯想把 draft 搬出牢籠，cage_assert 仍硬擋、原檔不動。"""
    mem = tmp_path / "memory"
    draft = _make_draft(mem)
    import lib.taxonomy_jury as tj
    monkeypatch.setattr(tj, "_drafts_root", lambda p: mem / "_AIDocs" / "_atoms")
    with pytest.raises(CageEscapeError):
        relocate_within_cage(draft, mem)
    assert draft.exists()                          # fail-closed：未越獄前原檔保留


# ── 軸2：歸夾後 [臨] 仍 [臨]、內容 byte-identical ─────────────────────────
def test_confidence_frozen(tmp_path):
    mem = tmp_path / "memory"
    draft = _make_draft(mem)
    before = draft.read_text(encoding="utf-8")
    target = relocate_within_cage(draft, mem)
    after = target.read_text(encoding="utf-8")
    assert before == after                         # 純 mv，零改動
    assert "- Confidence: [臨]" in after


# ── 軸3：學詞庫檔不被觸碰 ───────────────────────────────────────────────
def test_lexicon_untouched(tmp_path):
    mem = tmp_path / "memory"
    lex = mem / "_meta" / "realm-lexicon-learned.json"
    lex.parent.mkdir(parents=True, exist_ok=True)
    lex.write_text('{"foo":"World"}', encoding="utf-8")
    before = (lex.read_text(encoding="utf-8"), lex.stat().st_mtime_ns)
    draft = _make_draft(mem)
    relocate_within_cage(draft, mem)
    after = (lex.read_text(encoding="utf-8"), lex.stat().st_mtime_ns)
    assert before == after


# ── 軸4 索引：_atom_index.json 不被觸碰 ─────────────────────────────────
def test_index_untouched(tmp_path):
    mem = tmp_path / "memory"
    mem.mkdir(parents=True, exist_ok=True)
    idx = mem / "_atom_index.json"
    idx.write_text('{"atoms":[]}', encoding="utf-8")
    before = (idx.read_text(encoding="utf-8"), idx.stat().st_mtime_ns)
    draft = _make_draft(mem)
    relocate_within_cage(draft, mem)
    after = (idx.read_text(encoding="utf-8"), idx.stat().st_mtime_ns)
    assert before == after


# ── CI 不變式（grep 禁用符號 + 集合斷言）────────────────────────────────
def test_jury_no_forbidden_symbols():
    """INV-NO-INDEX-FOR-DRAFT / INV-NO-LEXICON-WRITE：taxonomy_jury.py 不得引用
    索引寫入 / 詞庫學習 / realm 搬移 符號。"""
    src = (CLAUDE / "lib" / "taxonomy_jury.py").read_text(encoding="utf-8")
    for sym in ("append_learned_terms", "write_atom", "upsert_atom", "set_realm"):
        assert sym not in src, f"taxonomy_jury.py 不得出現 {sym!r}（違反四軸分離）"


def test_seed_slugs_no_protected_collision():
    """INV-CORE-PROTECTED-UNTOUCHED：taxonomy slug 命名禁撞核心保護前綴。"""
    bad = [s for s in seed_slugs()
           if s.lower().startswith(tuple(LOCAL_REALM_CORE_PROTECTED_PREFIXES))]
    assert not bad, f"taxonomy slug 撞核心保護前綴：{bad}"


def test_projects_not_cross_project():
    """INV-PROJECTS-NOT-CROSS-PROJECT：projects/ 永不跨專案注入。"""
    assert "projects" not in CROSS_PROJECT_LOCAL_DOMAINS


def test_seed_integrity():
    assert len(GAME_TAXONOMY_SEED) == 23
    assert len(seed_slugs()) == 23                 # slug 無重複
    assert all(c.scope_hint in ("project", "core", "both") for c in GAME_TAXONOMY_SEED)

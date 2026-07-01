"""taxonomy_jury.py — _drafts 內部 taxonomy 引擎（最小殼）。

目的：用可執行測試釘死「軸1 歸夾 = 牢籠內子夾移動，draft 永遠出不了
_drafts/」這個安全前提；不喚 LLM、不碰 _atom_index.json、不寫詞庫、不改
Confidence、不晉升。後續才接三路 LLM jury / 去蕪 soft-delete / 畢業閘。

硬不變式（見 memory/_staging/next-phase-draft-taxonomy-engine.md §4）：
  INV-DRAFT-STAYS-CAGED：任何歸夾/soft-delete 終點 path 必含 '_drafts' 段，
    違反即 raise（fail-closed），呼叫端據此 skip。

本檔禁止引用『索引寫入』與『詞庫學習』API（CI grep 守門，見 verify_taxonomy_caging：
INV-NO-INDEX-FOR-DRAFT / INV-NO-LEXICON-WRITE）——故本檔刻意不出現該等符號名。
"""
from __future__ import annotations

from pathlib import Path

from lib.game_taxonomy import TAXONOMY_CATCHALL

CAGE_SEGMENT = "_drafts"
BY_CLASS = "by-class"


class CageEscapeError(RuntimeError):
    """歸夾終點逃出 _drafts/ 牢籠——INV-DRAFT-STAYS-CAGED 違反。"""


def cage_assert(target: Path, memory_dir: Path) -> None:
    """移檔前硬斷言：target 必落在 memory_dir 下、且相對路徑含 '_drafts' 段。
    違反 raise CageEscapeError（fail-closed）。此為軸1↔軸4 隔離的結構性守門。"""
    t = target.resolve()
    m = memory_dir.resolve()
    try:
        rel = t.relative_to(m)
    except ValueError as e:
        raise CageEscapeError(f"target {t} 不在 memory_dir {m} 下") from e
    if CAGE_SEGMENT not in rel.parts:
        raise CageEscapeError(
            f"target '{rel}' 不含 '{CAGE_SEGMENT}' 段——draft 不得離開牢籠")


def _drafts_root(draft_path: Path) -> Path:
    """從 draft 路徑往上找名為 '_drafts' 的祖先目錄。"""
    for p in draft_path.parents:
        if p.name == CAGE_SEGMENT:
            return p
    raise CageEscapeError(f"{draft_path} 不在任何 '{CAGE_SEGMENT}/' 下")


def relocate_within_cage(draft_path: Path, memory_dir: Path,
                         slug: str = TAXONOMY_CATCHALL) -> Path:
    """把 _drafts/auto-capture/<x>.md 物理 mv 到 _drafts/by-class/<slug>/<x>.md。

    slug 預設 _Unsorted（不分類、不喚 LLM）。純物理 rename，不碰索引/
    詞庫/Confidence。移檔前過 cage_assert（INV-DRAFT-STAYS-CAGED）。回 target 路徑。
    """
    dest_dir = _drafts_root(draft_path) / BY_CLASS / slug
    target = dest_dir / draft_path.name
    cage_assert(target, memory_dir)   # 牢籠斷言先於任何 I/O（fail-closed）
    dest_dir.mkdir(parents=True, exist_ok=True)
    draft_path.rename(target)
    return target

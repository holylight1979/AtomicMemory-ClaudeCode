"""verify_skip_dirs_behavior.py — 「跳過哪些資料夾」清單補齊的三項，用行為驗：

1. atom 掃描（atom_spec.is_atom_file）：_archived/ 底下是封存的舊卡，不算 atom。
2. 定位既有 atom（atom_locations._rglob_locate）：_rejected/ 底下是被退回的卡，append／replace 不得找到它。
3. 補來源（tools/atom-provenance-backfill._iter_md）：templates/ 底下是範本，不得被寫入 Source。

每案都先斷言對照組（正常資料夾）照常被找到，避免「什麼都沒找到」也算通過。
怎麼跑：python -X utf8 -m pytest -q lib/verify/verify_skip_dirs_behavior.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from lib.atom_spec import is_atom_file  # noqa: E402
from lib.atom_locations import _rglob_locate  # noqa: E402


def _md(p: Path) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# x\n\n- Confidence: [臨]\n", encoding="utf-8")
    return p


def test_archived_is_not_an_atom(tmp_path):
    live = _md(tmp_path / "工作流" / "live.md")
    archived = _md(tmp_path / "_archived" / "2026-01-01-old.md")
    assert is_atom_file(live, tmp_path)            # 對照組：一般範疇資料夾照常算 atom
    assert not is_atom_file(archived, tmp_path)


def test_locate_skips_rejected(tmp_path):
    _md(tmp_path / "shared" / "_rejected" / "gone.md")
    _md(tmp_path / "shared" / "工具" / "kept.md")
    assert _rglob_locate(tmp_path, "kept") == [tmp_path / "shared" / "工具" / "kept.md"]   # 對照組
    assert _rglob_locate(tmp_path, "gone") == []


def test_provenance_backfill_skips_templates(tmp_path, monkeypatch):
    monkeypatch.setenv("WG_CLAUDE_DIR", str(tmp_path / "data"))
    spec = importlib.util.spec_from_file_location("_ut_backfill", ROOT / "tools" / "atom-provenance-backfill.py")
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "_ut_backfill", mod)   # dataclass 要在 sys.modules 找得到所屬模組
    spec.loader.exec_module(mod)
    mem = tmp_path / "mem"
    atom = _md(mem / "工作流" / "a.md")
    _md(mem / "templates" / "next-phase-plan-template.md")
    assert list(mod._iter_md(mem)) == [atom]

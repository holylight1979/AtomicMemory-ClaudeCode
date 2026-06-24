"""verify_selective_forget.py — Phase D selective forgetting（隔離到 _distant/）。

守住 wg_atoms.select_forget_candidates / apply_selective_forget 不變式（憲法 Forgetting
對策，_AIDocs/context-memory-governance.md）：
- 選取：score < isolate_threshold 且非核心保護清單（LOCAL_REALM_CORE_PROTECTED_EXACT）
- 預設 dry-run（enabled=false ∨ dry_run=true）→ 寫 _staging/forget-candidates.md、不搬
- 真隔離（enabled ∧ !dry_run）→ md+access 搬 _distant/（可逆），觸發 index 重產
- 缺檔 → skipped；保護清單永不選取

受控 tmp，不動磁碟既有 atom。Design: plans/cozy-sauteeing-jellyfish.md Phase D。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify/ → hooks/
CLAUDE = HOOKS_DIR.parent
for p in (str(HOOKS_DIR), str(CLAUDE), str(CLAUDE / "lib")):
    if p not in sys.path:
        sys.path.insert(0, p)

import wg_atoms  # noqa: E402
from wg_atoms import select_forget_candidates, apply_selective_forget  # noqa: E402
import lib.atom_locations as AL  # noqa: E402

CFG_DRYRUN = {"self_iteration": {"forget": {"enabled": True, "dry_run": True, "isolate_threshold": 0.3}}}
CFG_ISOLATE = {"self_iteration": {"forget": {"enabled": True, "dry_run": False, "isolate_threshold": 0.3}}}


@pytest.fixture(autouse=True)
def _no_sync(monkeypatch):
    # 隔離測試不真觸發 sync-memory-index 子程序
    monkeypatch.setattr(wg_atoms, "_trigger_sync_memory_index", lambda: None)


def _cand(atom, score, last_used="2026-01-01"):
    return {"atom": atom, "score": score, "last_used": last_used, "confirmations": 0}


def _make_atom(tmp, slug):
    (tmp / f"{slug}.md").write_text(f"# {slug}\n- [臨] x\n", encoding="utf-8")
    (tmp / f"{slug}.access.json").write_text(json.dumps({"read_hits": 1}), encoding="utf-8")


# ─── select_forget_candidates ────────────────────────────────────────────────

def test_select_filters_by_threshold():
    cands = [_cand("low", 0.1), _cand("high", 0.5)]
    out = [c["atom"] for c in select_forget_candidates(cands, CFG_DRYRUN)]
    assert out == ["low"]  # 0.5 ≥ 0.3 不選


def test_select_excludes_protected(monkeypatch):
    monkeypatch.setattr(AL, "LOCAL_REALM_CORE_PROTECTED_EXACT", frozenset({"keepme"}))
    cands = [_cand("keepme", 0.1), _cand("dropme", 0.1)]
    out = [c["atom"] for c in select_forget_candidates(cands, CFG_DRYRUN)]
    assert out == ["dropme"]  # 核心保護者永不選取


# ─── apply_selective_forget ──────────────────────────────────────────────────

def test_dryrun_writes_list_no_move(tmp_path):
    atoms = tmp_path / "atoms"; atoms.mkdir()
    staging = tmp_path / "staging"
    _make_atom(atoms, "stale")
    res = apply_selective_forget([_cand("stale", 0.1)], CFG_DRYRUN,
                                 atoms_dir=atoms, staging_dir=staging)
    assert res["mode"] == "dry_run" and res["forgotten"] == []
    assert (atoms / "stale.md").exists()  # 未搬
    assert (staging / "forget-candidates.md").exists()  # 候選清單已寫
    assert "stale" in (staging / "forget-candidates.md").read_text(encoding="utf-8")


def test_default_config_is_dry_run(tmp_path):
    atoms = tmp_path / "atoms"; atoms.mkdir()
    _make_atom(atoms, "stale")
    res = apply_selective_forget([_cand("stale", 0.1)], {}, atoms_dir=atoms)
    assert res["mode"] == "dry_run" and (atoms / "stale.md").exists()  # 預設絕不搬


def test_isolate_moves_to_distant(tmp_path):
    atoms = tmp_path / "atoms"; atoms.mkdir()
    _make_atom(atoms, "stale")
    res = apply_selective_forget([_cand("stale", 0.1)], CFG_ISOLATE, atoms_dir=atoms)
    assert res["mode"] == "isolated" and res["forgotten"] == ["stale"]
    assert not (atoms / "stale.md").exists()  # 原處已移走
    assert (atoms / "_distant" / "stale.md").exists()  # 隔離到 _distant
    assert (atoms / "_distant" / "stale.access.json").exists()  # access 一併搬（可逆）


def test_isolate_missing_file_skipped(tmp_path):
    atoms = tmp_path / "atoms"; atoms.mkdir()
    res = apply_selective_forget([_cand("ghost", 0.1)], CFG_ISOLATE, atoms_dir=atoms)
    assert res["forgotten"] == [] and res["skipped"] == ["ghost"]

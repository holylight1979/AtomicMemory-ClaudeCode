"""verify_fallback_state_rebuild.py — fallback state 注入全滅修復。

驗證 wg_core._ensure_state 的 fallback 路徑不再產出「無 atom_index 的裸 state」：
  - fallback 時經 _rebuild_min_atom_index 重建最小 global 層 index（trigger/BM25 可恢復）
  - 標 `_fallback_state_rebuilt` 旗標（UPS 消費注入一行 advisory，不靜默降級）
  - _cleanup_old_states 的 empty-working TTL 放寬為 3600s（600s 清太快＝idle session
    一回來就落入 fallback）
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify/ → hooks/
sys.path.insert(0, str(HOOKS_DIR))

import wg_core  # noqa: E402
from handlers import _shared  # noqa: E402

_INDEX_MD = """| Atom | Path | Trigger |
|------|------|---------|
| test-atom | memory/test-atom.md | alpha, beta |
| other-atom | memory/other-atom.md | gamma |
"""


@pytest.fixture
def env(tmp_path, monkeypatch):
    wdir = tmp_path / "workflow"
    mdir = tmp_path / "memory"
    wdir.mkdir()
    mdir.mkdir()
    (mdir / "_ATOM_INDEX.md").write_text(_INDEX_MD, encoding="utf-8")
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", wdir)
    monkeypatch.setattr(wg_core, "MEMORY_DIR", mdir)
    return tmp_path, wdir, mdir


def test_fallback_rebuilds_min_atom_index(env):
    """state 遺失 → fallback 自建 state 含 global 層 atom_index + 重建旗標。"""
    tmp, wdir, _mdir = env
    state = wg_core._ensure_state("sid-fb", {"cwd": str(tmp)}, {})
    assert state is not None
    names = [n for n, _p, _t in state.get("atom_index", {}).get("global", [])]
    assert "test-atom" in names and "other-atom" in names
    assert state.get("_fallback_state_rebuilt") is True
    # state 已落檔（後續 hook 讀得到 index）
    assert (wdir / "state-sid-fb.json").exists()


def test_rebuild_min_atom_index_failure_returns_empty(env, monkeypatch):
    """index 重建炸掉 → 回 {}（fail-open），state 仍建立、旗標仍在（advisory 仍浮出）。"""
    tmp, _wdir, mdir = env
    (mdir / "_ATOM_INDEX.md").unlink()  # 無任何 index 檔 → parse 回 []
    state = wg_core._ensure_state("sid-fb2", {"cwd": str(tmp)}, {})
    assert state is not None
    assert state.get("_fallback_state_rebuilt") is True
    assert "atom_index" not in state or state["atom_index"].get("global") == []


def _write_state_file(wdir: Path, sid: str, age_s: float) -> Path:
    p = wdir / f"state-{sid}.json"
    p.write_text(json.dumps({
        "phase": "working",
        "topic_tracker": {"prompt_count": 0},
    }), encoding="utf-8")
    old = time.time() - age_s
    os.utime(p, (old, old))
    return p


def test_empty_working_ttl_is_3600(tmp_path, monkeypatch):
    """empty-working state：700s 存活（舊 600s 會被清）、4000s 才清。"""
    monkeypatch.setattr(_shared, "WORKFLOW_DIR", tmp_path)
    keep = _write_state_file(tmp_path, "young", 700)
    gone = _write_state_file(tmp_path, "stale", 4000)
    _shared._cleanup_old_states()
    assert keep.exists(), "700s 的 empty-working state 不該被清（TTL 已放寬 3600s）"
    assert not gone.exists(), "4000s 的 empty-working state 應被清"

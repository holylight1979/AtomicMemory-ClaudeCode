"""verify_register_project_skips_temp.py — 暫存區假專案不得進 project-registry。

背景：verify_project_layer_smoke 用真 dispatcher 跑 <tmp>/proj，SessionStart 順手
register_project → registry 每跑一次長兩筆、dashboard「已知專案」被 pytest tmp 淹掉。
不變式：
  1. root 在系統暫存根（tempfile / TEMP / TMP）之下 → 不登記
  2. 路徑含 `pytest-of-` → 不登記（即使暫存根被改到別處）
  3. 暫存根之外的合法專案照常登記
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest  # noqa: F401

HOOKS_DIR = Path(__file__).resolve().parent.parent
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

import wg_core  # noqa: E402


def _mk_project(root: Path) -> Path:
    (root / ".git").mkdir(parents=True)
    return root


@pytest.fixture
def reg(tmp_path, monkeypatch):
    path = tmp_path / "registry" / "project-registry.json"
    monkeypatch.setattr(wg_core, "REGISTRY_PATH", path)
    return path


def _slugs(path: Path) -> set:
    if not path.exists():
        return set()
    return set(json.loads(path.read_text(encoding="utf-8")).get("projects", {}))


def test_project_under_temp_root_not_registered(tmp_path, reg, monkeypatch):
    fake_temp = tmp_path / "temp"
    monkeypatch.setattr(wg_core, "_transient_temp_dirs", lambda: [fake_temp.resolve()])
    proj = _mk_project(fake_temp / "session" / "proj")
    wg_core.register_project(str(proj))
    assert _slugs(reg) == set()


def test_pytest_of_marker_not_registered(tmp_path, reg, monkeypatch):
    monkeypatch.setattr(wg_core, "_transient_temp_dirs", lambda: [])
    proj = _mk_project(tmp_path / "pytest-of-holylight" / "pytest-1" / "proj")
    wg_core.register_project(str(proj))
    assert _slugs(reg) == set()


def test_real_project_outside_temp_registered(tmp_path, reg, monkeypatch):
    # tmp_path 本身在真暫存根且含 pytest-of-：兩道判定都 monkeypatch 掉，只驗「不在暫存根就登記」
    monkeypatch.setattr(wg_core, "_transient_temp_dirs", lambda: [(tmp_path / "temp").resolve()])
    monkeypatch.setattr(wg_core, "_TRANSIENT_PATH_MARKERS", ())
    proj = _mk_project(tmp_path / "work" / "realproj")
    wg_core.register_project(str(proj))
    slugs = _slugs(reg)
    assert len(slugs) == 1 and "realproj" in next(iter(slugs))


def test_live_tmp_path_is_transient(tmp_path):
    # pytest 的 tmp_path 本身就在系統暫存根下：真實環境判定必為 transient
    assert wg_core.is_transient_project_root(tmp_path) is True

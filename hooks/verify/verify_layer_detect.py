"""verify_layer_detect.py：判層 H9：wg_core._layer_of(cwd) 只看 cwd 與設定。

正例：<CLAUDE_DIR>/hooks/handlers＝root、tmp 公司根下＝org、tmp 專案有表＝project_mapped、
tmp 專案無表＝project_unmapped、家目錄＝none。
反例：~/.claude-foo（旁系）不是 root；零卡 repo（只有 .git）不是 root。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_layer_detect.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
os.environ.setdefault("WG_CLAUDE_DIR", str(HOOKS_DIR.parent))   # worktree 內跑：wg_core 的 lib／workflow 指本樹
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import project_root as pr  # noqa: E402
import wg_core  # noqa: E402

MAP_TEXT = "| `src/` | 主程式 | `主程式導讀` | 有 |\n"


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    """不讀本機真公司層設定；專案根解析快取每案清空。"""
    monkeypatch.setattr(wg_core, "org_memory_root", lambda: None)
    pr.clear_cache()
    yield
    pr.clear_cache()


def _write_map(root: Path) -> Path:
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    mp = root / ".claude" / "overview-map.md"
    mp.write_text(MAP_TEXT, encoding="utf-8", newline="\n")
    return mp


# ─── 正例 ──────────────────────────────────────────────────────────────────────

def test_claude_dir_subdir_is_root(monkeypatch):
    li = wg_core._layer_of(str(wg_core.CLAUDE_DIR / "hooks" / "handlers"))
    assert li.kind == "root" and li.root == wg_core.CLAUDE_DIR
    home_claude = Path.home() / ".claude"                                # 未設 WG_CLAUDE_DIR 時的實際值
    monkeypatch.setattr(wg_core, "CLAUDE_DIR", home_claude)
    li = wg_core._layer_of(str(home_claude / "hooks" / "handlers"))
    assert li.kind == "root" and li.root == home_claude
    assert wg_core._layer_of(str(home_claude)).kind == "root"           # 根本身也是 root


def test_under_company_root_is_org(tmp_path, monkeypatch):
    org = tmp_path / "company"
    (org / "shared" / "tools").mkdir(parents=True)
    monkeypatch.setattr(wg_core, "org_memory_root", lambda: org)
    li = wg_core._layer_of(str(org / "shared" / "tools"))
    assert li == ("org", org, None)
    mp = _write_map(org)
    assert wg_core._layer_of(str(org)) == ("org", org, mp)


def test_project_with_map_is_mapped_without_is_unmapped(tmp_path):
    proj = tmp_path / "proj"
    (proj / ".git").mkdir(parents=True)
    (proj / "src").mkdir()
    li = wg_core._layer_of(str(proj / "src"))
    assert li.kind == "project_unmapped" and li.root == proj and li.map_path is None
    mp = _write_map(proj)
    pr.clear_cache()
    li = wg_core._layer_of(str(proj / "src"))
    assert li.kind == "project_mapped" and li.root == proj and li.map_path == mp


def test_home_and_empty_cwd_are_none():
    assert wg_core._layer_of(str(Path.home())) == ("none", None, None)
    assert wg_core._layer_of("") == ("none", None, None)


def test_dir_without_any_marker_is_none(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    assert wg_core._layer_of(str(plain)).kind == "none"


# ─── 反例 ──────────────────────────────────────────────────────────────────────

def test_sibling_claude_foo_is_not_root(tmp_path, monkeypatch):
    assert wg_core._layer_of(str(Path.home() / ".claude-foo")).kind != "root"
    fake = tmp_path / ".claude"                                          # 假根層 + 旁系同前綴目錄
    (fake / "hooks").mkdir(parents=True)
    sibling = tmp_path / ".claude-foo"
    (sibling / ".git").mkdir(parents=True)
    monkeypatch.setattr(wg_core, "CLAUDE_DIR", fake)
    assert wg_core._layer_of(str(fake / "hooks")).kind == "root"
    li = wg_core._layer_of(str(sibling))
    assert li.kind == "project_unmapped" and li.root == sibling          # 字串前綴相同不算根層


def test_zero_card_repo_is_project_unmapped_not_root(tmp_path):
    repo = tmp_path / "fresh"
    (repo / ".git").mkdir(parents=True)
    li = wg_core._layer_of(str(repo))
    assert li.kind == "project_unmapped" and li.kind != "root" and li.root == repo


def test_layer_kind_for_root_matches_layer_of(tmp_path, monkeypatch):
    """_cfg 用的 _layer_kind_for_root 與 _layer_of 同一套判準。"""
    org = tmp_path / "company"
    org.mkdir()
    proj = tmp_path / "proj"
    (proj / ".git").mkdir(parents=True)
    assert wg_core._layer_kind_for_root(wg_core.CLAUDE_DIR / "hooks", None) == "root"
    assert wg_core._layer_kind_for_root(org, org) == "org"
    assert wg_core._layer_kind_for_root(proj, org) == "project_unmapped"
    _write_map(proj)
    assert wg_core._layer_kind_for_root(proj, org) == "project_mapped"


def test_inaccessible_path_during_root_resolution_is_none(tmp_path, monkeypatch):
    """退回 001 的 B5：resolve_project_root 對碰不得的路徑（UNC 權限）拋 OSError → none，不外洩例外。"""
    def _denied(cwd):
        raise PermissionError(5, "Access is denied", cwd)
    monkeypatch.setattr(wg_core, "resolve_project_root", _denied)
    assert wg_core._layer_of(r"\localhost\nx-share-xyz\dir") == ("none", None, None)
    assert wg_core._layer_of(str(tmp_path / "proj")) == ("none", None, None)

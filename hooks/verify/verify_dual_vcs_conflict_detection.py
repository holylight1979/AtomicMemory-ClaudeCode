"""verify_dual_vcs_conflict_detection.py — git 疊在 svn 上（同層兩個都有）時，svn 衝突不被略過。

不變式：
1. find_vcs_root 在同層雙版控回 git（既有行為不變）；find_svn_root 仍找得到 svn 工作副本根。
2. merge-atom-index --resolve：不指定 --vcs 時 svn 與 git 兩側都處理；--vcs 指定時只處理那一側。
3. SessionStart 衝突提示：同層雙版控也會報 svn 衝突；索引三檔與 atom 衝突分開報，atom 附數量。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

CLAUDE = Path(__file__).resolve().parent.parent.parent  # hooks/verify/ → repo root
sys.path.insert(0, str(CLAUDE / "hooks"))

import wg_core  # noqa: E402
from handlers import session_start as ss  # noqa: E402

_spec = importlib.util.spec_from_file_location("merge_atom_index", CLAUDE / "tools" / "merge-atom-index.py")
MAI = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(MAI)


def _dual(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".svn").mkdir()
    mem = tmp_path / ".claude" / "memory"
    mem.mkdir(parents=True)
    return mem


# ─── 1. 找根 ─────────────────────────────────────────────────────────────────


def test_dual_vcs_roots(tmp_path):
    mem = _dual(tmp_path)
    assert wg_core.find_vcs_root(mem) == ("git", tmp_path)
    assert wg_core.find_svn_root(mem) == tmp_path


def test_find_svn_root_absent_in_plain_git(tmp_path):
    (tmp_path / ".git").mkdir()
    assert wg_core.find_svn_root(tmp_path) is None


# ─── 2. --resolve 兩側 ───────────────────────────────────────────────────────


def _record(monkeypatch):
    calls = []
    monkeypatch.setattr(MAI, "_resolve_svn", lambda root, start, rep: calls.append(("svn", root)))
    monkeypatch.setattr(MAI, "_resolve_git", lambda root, rep: calls.append(("git", root)))
    return calls


def test_resolve_dual_handles_both_sides(tmp_path, monkeypatch):
    _dual(tmp_path)
    calls = _record(monkeypatch)
    rep, rc = MAI.resolve(tmp_path, quiet=True)
    assert calls == [("svn", tmp_path), ("git", tmp_path)]
    assert rc == 0 and rep["error"] is None


def test_resolve_only_svn(tmp_path, monkeypatch):
    _dual(tmp_path)
    calls = _record(monkeypatch)
    MAI.resolve(tmp_path, quiet=True, only="svn")
    assert calls == [("svn", tmp_path)]


def test_resolve_only_git(tmp_path, monkeypatch):
    _dual(tmp_path)
    calls = _record(monkeypatch)
    MAI.resolve(tmp_path, quiet=True, only="git")
    assert calls == [("git", tmp_path)]


def test_resolve_only_svn_outside_svn_reports_error(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    calls = _record(monkeypatch)
    rep, rc = MAI.resolve(tmp_path, quiet=True, only="svn")
    assert calls == [] and rc == 1 and rep["error"]


# ─── 3. SessionStart 衝突提示 ────────────────────────────────────────────────


def test_session_start_reports_svn_conflicts_in_dual_vcs(tmp_path):
    mem = _dual(tmp_path)
    (mem / "MEMORY.md.mine").write_text("x", encoding="utf-8")
    (mem / "shared" / "x").mkdir(parents=True)
    (mem / "shared" / "x" / "a.md.mine").write_text("x", encoding="utf-8")
    (mem / "shared" / "x" / "b.md.mine").write_text("x", encoding="utf-8")

    lines = ss._index_conflict_advisory(str(tmp_path))
    assert any("MEMORY.md" in ln for ln in lines)
    assert any("2 顆 atom" in ln and "a" in ln for ln in lines)


def test_session_start_quiet_without_conflicts(tmp_path):
    _dual(tmp_path)
    assert ss._index_conflict_advisory(str(tmp_path)) == []

"""verify_unpushed_advisory.py — SessionStart 的「本地 ahead > 0」提醒。

存在理由：SessionEnd 晉升自動提交把 push 丟背景，失敗時 commit 只留本地、
當下無人知 → 下個 session 開頭補可見性（可觀測性鐵律：fail-open 必告知）。

不變式：
1. ahead > 0 → 出一行 advisory 且帶筆數。
2. 已同步 → 回 []（不佔 context）。
3. 無 upstream / detached / 非 git 目錄 → 回 []（正常狀態，不吵）。
4. 唯讀：跑完不得改變 repo 狀態。
5. 自身出錯不阻斷 SessionStart。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

CLAUDE = Path(__file__).resolve().parent.parent.parent  # hooks/verify/ → ~/.claude
sys.path.insert(0, str(CLAUDE / "hooks"))

from handlers import session_start as ss  # noqa: E402


def _git(repo: Path, *args):
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, encoding="utf-8")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """local repo + 一個 bare 當 origin，已設 upstream 且同步。"""
    bare = tmp_path / "origin.git"
    _git(tmp_path, "init", "--bare", str(bare))
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-b", "main")
    _git(work, "config", "user.email", "t@t")
    _git(work, "config", "user.name", "t")
    (work / "a.md").write_text("x\n", encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "commit", "-m", "seed")
    _git(work, "remote", "add", "origin", str(bare))
    _git(work, "push", "-u", "origin", "main")
    monkeypatch.setattr(ss, "CLAUDE_DIR", work)
    return work


def test_synced_repo_is_silent(repo):
    assert ss._unpushed_advisory() == []


def test_ahead_reports_count(repo):
    for i in range(2):
        (repo / f"b{i}.md").write_text("y\n", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", f"local {i}")
    out = ss._unpushed_advisory()
    assert len(out) == 1
    assert "2 筆 commit 未 push" in out[0]
    assert "Guardian:Sync" in out[0]


def test_no_upstream_is_silent(tmp_path, monkeypatch):
    work = tmp_path / "solo"
    work.mkdir()
    _git(work, "init", "-b", "main")
    _git(work, "config", "user.email", "t@t")
    _git(work, "config", "user.name", "t")
    (work / "a.md").write_text("x\n", encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "commit", "-m", "seed")
    monkeypatch.setattr(ss, "CLAUDE_DIR", work)
    assert ss._unpushed_advisory() == []


def test_non_git_dir_is_silent(tmp_path, monkeypatch):
    monkeypatch.setattr(ss, "CLAUDE_DIR", tmp_path)
    assert ss._unpushed_advisory() == []


def test_is_read_only(repo):
    (repo / "c.md").write_text("z\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "local")
    head = _git(repo, "rev-parse", "HEAD").stdout
    status = _git(repo, "status", "--porcelain").stdout
    ss._unpushed_advisory()
    assert _git(repo, "rev-parse", "HEAD").stdout == head
    assert _git(repo, "status", "--porcelain").stdout == status


def test_internal_error_does_not_raise(monkeypatch):
    monkeypatch.setattr(ss, "CLAUDE_DIR", None)  # 觸發 AttributeError
    assert ss._unpushed_advisory() == []


def test_wired_into_session_start():
    src = (CLAUDE / "hooks" / "handlers" / "session_start.py").read_text(encoding="utf-8")
    assert "lines.extend(_unpushed_advisory())" in src

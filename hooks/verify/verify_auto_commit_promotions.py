"""verify_auto_commit_promotions.py — 晉升 sweep 的自動提交。

不變式：
1. 用 `git commit -- <paths>` pathspec 形式，**不下 git add**——別的 session 已
   stage 的檔案必須原封不動（共用工作樹安全性的核心）。
2. 只提交 sweep 自己回報的路徑；樹外 / 不存在的路徑濾掉。
3. config 開關關閉 → 完全不動 git。
4. 目標路徑無實際改動 → 不產生空 commit。
5. index.lock 競態 → 短重試；持續失敗只印 stderr、不 raise（不阻斷 SessionEnd）。
6. 任何 git 失敗都 fail-open 且**出聲**（可觀測性鐵律），改動留在工作樹。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

CLAUDE = Path(__file__).resolve().parent.parent.parent  # hooks/verify/ → ~/.claude
sys.path.insert(0, str(CLAUDE / "hooks"))

from handlers import session_end as se  # noqa: E402


def _git(repo: Path, *args):
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, encoding="utf-8")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """建一個真的 git repo 當 CLAUDE_DIR，內含兩顆 atom。"""
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "memory").mkdir()
    for n in ("alpha", "beta"):
        (tmp_path / "memory" / f"{n}.md").write_text(
            f"# {n}\n\n- Confidence: [臨]\n", encoding="utf-8")
    (tmp_path / "other.txt").write_text("untouched\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "seed")
    monkeypatch.setattr(se, "CLAUDE_DIR", tmp_path)
    return tmp_path


def _promote(repo: Path, name: str):
    p = repo / "memory" / f"{name}.md"
    p.write_text(p.read_text(encoding="utf-8").replace("[臨]", "[觀]"), encoding="utf-8")
    return {"atom": name, "path": str(p), "items": ["x"]}


CFG_ON = {"self_iteration": {"auto_commit_promotions": True,
                             "auto_push_promotions": False}}


def test_commits_only_reported_paths(repo):
    entry = _promote(repo, "alpha")
    _promote(repo, "beta")  # 改了但**不**回報 → 不該被提交
    se._auto_commit_promotions([entry], CFG_ON)
    assert _git(repo, "status", "--porcelain").stdout.splitlines() == [" M memory/beta.md"]
    assert "[觀]" in _git(repo, "show", "HEAD:memory/alpha.md").stdout


def test_does_not_touch_index_of_other_session(repo):
    """別的 session 已 stage 的檔案不得被夾帶進 commit，且須維持 staged。"""
    (repo / "other.txt").write_text("other session edit\n", encoding="utf-8")
    _git(repo, "add", "other.txt")
    entry = _promote(repo, "alpha")
    se._auto_commit_promotions([entry], CFG_ON)
    head = _git(repo, "show", "--name-only", "--format=", "HEAD").stdout.split()
    assert head == ["memory/alpha.md"], head
    assert _git(repo, "status", "--porcelain").stdout.strip() == "M  other.txt"


def test_disabled_switch_does_nothing(repo):
    entry = _promote(repo, "alpha")
    before = _git(repo, "rev-parse", "HEAD").stdout
    se._auto_commit_promotions(
        [entry], {"self_iteration": {"auto_commit_promotions": False}})
    assert _git(repo, "rev-parse", "HEAD").stdout == before
    assert " M memory/alpha.md" in _git(repo, "status", "--porcelain").stdout


def test_no_change_makes_no_empty_commit(repo):
    entry = {"atom": "alpha", "path": str(repo / "memory" / "alpha.md"), "items": []}
    before = _git(repo, "rev-parse", "HEAD").stdout
    se._auto_commit_promotions([entry], CFG_ON)
    assert _git(repo, "rev-parse", "HEAD").stdout == before


def test_paths_outside_tree_are_dropped(repo, tmp_path):
    outside = tmp_path.parent / "stray.md"
    outside.write_text("# stray\n", encoding="utf-8")
    before = _git(repo, "rev-parse", "HEAD").stdout
    se._auto_commit_promotions(
        [{"atom": "stray", "path": str(outside), "items": []}], CFG_ON)
    assert _git(repo, "rev-parse", "HEAD").stdout == before


def test_missing_file_is_dropped(repo):
    before = _git(repo, "rev-parse", "HEAD").stdout
    se._auto_commit_promotions(
        [{"atom": "ghost", "path": str(repo / "memory" / "ghost.md"), "items": []}],
        CFG_ON)
    assert _git(repo, "rev-parse", "HEAD").stdout == before


def test_non_git_dir_is_noop(tmp_path, monkeypatch):
    monkeypatch.setattr(se, "CLAUDE_DIR", tmp_path)
    (tmp_path / "memory").mkdir()
    f = tmp_path / "memory" / "a.md"
    f.write_text("x", encoding="utf-8")
    se._auto_commit_promotions([{"atom": "a", "path": str(f), "items": []}], CFG_ON)
    # 沒有 .git → 直接返回，不 raise


def test_index_lock_retries_then_gives_up(repo, capsys, monkeypatch):
    _promote(repo, "alpha")
    entry = {"atom": "alpha", "path": str(repo / "memory" / "alpha.md"), "items": []}
    monkeypatch.setattr("time.sleep", lambda s: None)
    (repo / ".git" / "index.lock").write_text("", encoding="utf-8")
    try:
        se._auto_commit_promotions([entry], CFG_ON)
    finally:
        (repo / ".git" / "index.lock").unlink()
    err = capsys.readouterr().err
    assert "index.lock" in err
    assert " M memory/alpha.md" in _git(repo, "status", "--porcelain").stdout


def test_commit_failure_is_reported_not_raised(repo, capsys, monkeypatch):
    entry = _promote(repo, "alpha")
    _git(repo, "config", "user.email", "")
    _git(repo, "config", "user.name", "")
    monkeypatch.setenv("GIT_AUTHOR_NAME", "")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "")
    se._auto_commit_promotions([entry], CFG_ON)  # 不得 raise
    # 失敗必出聲（可觀測性鐵律）或成功提交；兩者皆可，但絕不靜默失敗
    out = capsys.readouterr().err
    assert "auto-commit" in out


def test_sweep_result_carries_path():
    """wg_atoms 的 promoted 條目要帶 path，否則本函式無從定位檔案。"""
    src = (CLAUDE / "hooks" / "wg_atoms.py").read_text(encoding="utf-8")
    idx = src.find('results["promoted"].append({')
    assert idx > 0
    assert '"path": str(md_file)' in src[idx:idx + 400]

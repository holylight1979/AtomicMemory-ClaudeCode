"""verify_git_privacy_gate.py — PreToolUse git commit 隱私硬閘。

驗證 handlers/pre_tool_use.check_git_privacy：
  - staged 隱私檔（deny globs 命中）→ deny 訊息；一般檔 → 放行
  - commit -a 連 tracked modified 一起判
  - `git -C <path> commit` 的 repo 定位；非 commit 子指令（log --grep commit）不觸發
  - config privacy.enabled=false / deny_globs 追加
  - ~/.claude repo 專屬 globs 只在 git root == ~/.claude 掛上
  - fail-open：cwd 非 git repo 不擋
用真 git 子行程（tmp repo）實測，不 mock git。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

from handlers.pre_tool_use import (  # noqa: E402
    check_git_privacy, _git_commit_segments, _privacy_globs, _privacy_match,
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo)] + list(args),
        check=True, capture_output=True, text=True, timeout=10,
    )


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@t")
    _git(r, "config", "user.name", "t")
    return r


def _stage(repo: Path, rel: str, content: str = "x") -> None:
    f = repo / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content, encoding="utf-8")
    _git(repo, "add", rel)


def _check(repo: Path, command: str, config=None):
    return check_git_privacy("Bash", {"command": command}, str(repo), config or {})


# ─── deny / 放行 ─────────────────────────────────────────────────

def test_staged_env_file_denied(repo):
    _stage(repo, ".env", "SECRET=1")
    msg = _check(repo, "git commit -m 'x'")
    assert msg and "[Guardian:GitPrivacy]" in msg and ".env" in msg


def test_staged_normal_file_allowed(repo):
    _stage(repo, "main.py")
    assert _check(repo, "git commit -m 'x'") is None


def test_staged_key_in_subdir_denied(repo):
    _stage(repo, "certs/server.key")
    msg = _check(repo, "git commit -m 'x'")
    assert msg and "server.key" in msg


def test_commit_a_catches_tracked_modified(repo):
    _stage(repo, "creds.pem")
    # 先把隱私檔弄進追蹤（直接 commit 繞過本閘——閘只在 hook 層，git 本體不擋）
    _git(repo, "commit", "-q", "-m", "seed")
    (repo / "creds.pem").write_text("changed", encoding="utf-8")
    assert _check(repo, "git commit -m 'x'") is None          # 未 staged、無 -a → 不在本次 commit
    msg = _check(repo, "git commit -am 'x'")
    assert msg and "creds.pem" in msg                          # -a 會帶進去 → 擋


def test_git_dash_c_repo_targeting(repo, tmp_path):
    _stage(repo, ".env", "SECRET=1")
    other = tmp_path / "not-a-repo"
    other.mkdir()
    msg = check_git_privacy(
        "Bash", {"command": f'git -C "{repo}" commit -m x'}, str(other), {}
    )
    assert msg and ".env" in msg


# ─── 不觸發面（寧漏勿誤擋）───────────────────────────────────────

def test_non_commit_subcommand_not_gated(repo):
    _stage(repo, ".env", "SECRET=1")
    assert _check(repo, "git log --grep commit") is None
    assert _check(repo, "git add .env") is None


def test_non_git_repo_fail_open(tmp_path):
    d = tmp_path / "plain"
    d.mkdir()
    assert check_git_privacy("Bash", {"command": "git commit -m x"}, str(d), {}) is None


def test_disabled_by_config(repo):
    _stage(repo, ".env", "SECRET=1")
    assert _check(repo, "git commit -m x", {"privacy": {"enabled": False}}) is None


def test_non_bash_tool_ignored(repo):
    assert check_git_privacy("Write", {"command": "git commit"}, str(repo), {}) is None


# ─── config 追加 globs ───────────────────────────────────────────

def test_config_extra_glob_denied(repo):
    _stage(repo, "notes-private.md")
    cfg = {"privacy": {"deny_globs": ["*private*"]}}
    msg = _check(repo, "git commit -m x", cfg)
    assert msg and "notes-private.md" in msg


# ─── 純函式面 ────────────────────────────────────────────────────

def test_segments_parse_commit_variants():
    segs = _git_commit_segments('cd x && git -C "c:/r" commit -am "msg" | tee log')
    assert len(segs) == 1
    repo_cd, tokens = segs[0]
    assert repo_cd == "c:/r" and tokens[0] == "commit" and "-am" in tokens


def test_segments_skip_non_commit():
    assert _git_commit_segments("git status && git push origin main") == []


def test_claude_root_globs_only_at_claude_root(tmp_path):
    claude_root = str(Path.home() / ".claude")
    at_root = _privacy_globs({}, claude_root)
    elsewhere = _privacy_globs({}, str(tmp_path))
    assert "projects/*" in at_root and "history.jsonl" in at_root
    assert "projects/*" not in elsewhere


def test_privacy_match_path_vs_basename():
    globs = ["projects/*", "*.pem"]
    assert _privacy_match("projects/a/b.jsonl", globs) == "projects/*"
    assert _privacy_match("deep/dir/x.pem", globs) == "*.pem"
    assert _privacy_match("src/projects.md", globs) is None

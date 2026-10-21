"""verify_git_privacy_gate.py — PreToolUse git commit 隱私硬閘。

驗證 handlers/pre_tool_use.check_git_privacy：
  - staged 隱私檔（deny globs 命中）→ deny 訊息；一般檔 → 放行
  - commit -a 連 tracked modified 一起判；同一條指令前面 git add 要加進來的檔也判（add 還沒跑）
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
    check_git_privacy, _git_commit_segments, _git_commits_to_run, _git_segments, _privacy_globs, _privacy_match,
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


def test_git_add_in_same_command_is_checked(repo):
    """`git add .env && git commit`：PreToolUse 時 add 還沒跑、暫存區是空的，照樣要擋（10-20 G2 順手修的同類漏洞）。"""
    (repo / ".env").write_text("SECRET=1", encoding="utf-8")
    assert _check(repo, "git commit -m 'x'") is None                  # 前置：暫存區是空的，光 commit 沒東西進版
    msg = _check(repo, f'cd "{repo}" && git add .env && git commit -m "x"')
    assert msg is not None and ".env" in msg
    msg_all = _check(repo, "git add -A && git commit -m 'x'")
    assert msg_all is not None and ".env" in msg_all


def test_commit_through_git_alias_is_checked(repo):
    """G2(a)：`git ci`（alias.ci=commit）與直接 git commit 同一套查；口令閘、需求目標閘共用的 _git_commits_to_run 也認得。"""
    _stage(repo, ".env", "SECRET=1")
    assert _check(repo, "git commit -m x"), "前置：直接 commit 會被擋"
    _git(repo, "config", "alias.ci", "commit")
    msg = _check(repo, "git ci -m x")
    assert msg and ".env" in msg
    assert _git_commits_to_run("git ci -m x", str(repo))[2] is True
    assert _git_commits_to_run("git status", str(repo))[2] is False


def test_alias_named_like_a_git_command_is_ignored_like_git_does(repo):
    """codex 審 G2(a)：跟 git 自己指令同名的別名 git 不認（`check-ref-format` 跑的是內建），閘也不能當 commit；
    不在常見內建表上的真別名照樣認得。"""
    assert _git_commits_to_run("git -c alias.zz=commit zz -m x", str(repo))[2] is True, "前置：行內別名認得"
    assert _git_commits_to_run("git -c alias.check-ref-format=commit check-ref-format refs/heads/x",
                               str(repo))[2] is False


def test_alias_lookup_failure_at_the_commit_target_is_not_guessed(repo, tmp_path):
    """codex 審 G2(a) 第二輪：commit 落點的別名表查不到（-C 指到還不存在的目錄）時，不拿別的目錄的設定頂替；子命令不是
    git 指令 → 當可能有 commit（口令閘、需求目標閘照管）；內建子命令照常不算。"""
    nope = (tmp_path / "nope").as_posix()
    assert _git_commits_to_run(f"git -C {nope} status", str(repo))[2] is False, "前置：內建子命令不查別名"
    assert _git_commits_to_run(f"git -C {nope} zz -m x", str(repo))[2] is True


def _commit_base(repo: Path, files: dict) -> None:
    for rel, text in files.items():
        (repo / rel).write_text(text, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")


ESCAPE_FORMS = [
    ("Bash", 'git commit -m "say \\"hi\\"" -- .env'),          # 雙引號裡的 \"
    ("Bash", 'git commit -m "C:\\\\dir\\\\" -- .env'),          # 雙引號裡的 \\ 緊接收尾引號
    ("Bash", "git commit -m $'a\\nb' -- .env"),                 # ANSI-C $'…'
    ("Bash", "git commit -m 'it'\\''s' -- .env"),               # 單引號裡放單引號的 '\''
    ("Bash", "git commit -m x -- \\.env"),                      # 引號外的 \ 跳脫路徑
    ("Bash", "git add $'.env' && git commit -m x"),             # $'…' 包路徑
    ("Bash", "git add $'.e\\x6ev' && git commit -m x"),         # $'…' 裡的 \xHH
    ("Bash", 'git add $".env" && git commit -m x'),             # $"…"（locale 翻譯引號，值同雙引號）
    ("PowerShell", 'git commit -m "say `"hi`"" -- .env'),       # PowerShell 反引號
    ("PowerShell", "git commit -m 'it''s' -- .env"),            # PowerShell 單引號雙寫
]


@pytest.mark.parametrize("tool,command", ESCAPE_FORMS)
def test_escaped_message_or_path_still_finds_the_private_file(repo, tool, command):
    """G2(b)：訊息或路徑用跳脫字元時，後面的 `-- .env` 不能被吞進訊息、跳脫過的路徑要還原成 .env 再比對。"""
    _commit_base(repo, {".env": "A=1", "a.txt": "a"})
    (repo / ".env").write_text("A=2", encoding="utf-8")
    assert _check(repo, "git commit -m x") is None, "前置：沒暫存、沒 pathspec，光 commit 不會帶進 .env"
    msg = check_git_privacy(tool, {"command": command}, str(repo), {})
    assert msg and ".env" in msg, command


def test_private_name_inside_escaped_message_is_not_a_path(repo):
    """G2(b) 反例：.env 只出現在跳脫過的訊息裡、提交的是 a.txt → 不擋。"""
    _commit_base(repo, {".env": "A=1", "a.txt": "a"})
    (repo / ".env").write_text("A=2", encoding="utf-8")
    (repo / "a.txt").write_text("b", encoding="utf-8")
    assert _check(repo, "git commit -m x -- .env"), "前置：真的提交 .env 會被擋"
    command = 'git commit -m "mention \\".env\\" -- .env" -- a.txt'
    segs = _git_segments(command, {"commit"}, "bash", str(repo))
    assert segs and segs[0][1][-2:] == ["--", "a.txt"] and 'mention ".env" -- .env' in segs[0][1], segs
    assert _check(repo, command) is None


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
    from wg_core import CLAUDE_DIR
    claude_root = str(CLAUDE_DIR)   # 根層 globs 只掛在資料根 repo（一般安裝就是 ~/.claude）
    at_root = _privacy_globs({}, claude_root)
    elsewhere = _privacy_globs({}, str(tmp_path))
    assert "projects/*" in at_root and "history.jsonl" in at_root
    assert "projects/*" not in elsewhere


def test_privacy_match_path_vs_basename():
    globs = ["projects/*", "*.pem"]
    assert _privacy_match("projects/a/b.jsonl", globs) == "projects/*"
    assert _privacy_match("deep/dir/x.pem", globs) == "*.pem"
    assert _privacy_match("src/projects.md", globs) is None

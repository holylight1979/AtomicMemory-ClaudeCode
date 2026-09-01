"""verify_personal_sync_advisory.py — SessionStart 的「本人 personal atom 版控同步」提醒。

存在理由：personal 層「可上版控、僅本人可搜」；索引跟 repo 走、檔卻可能留本機（未 commit /
被 ignore）→ 他機索引懸空、兩機 hook 重建互相加回/拿掉。以前靠人傳話，這裡讓各人 CC 自己看到。

不變式：
1. personal 檔已 commit、索引一致 → []（零 context）。
2. 有 untracked / modified personal 檔 → 一行帶筆數、只算本人目錄、跳過 .access.json。
3. personal/<user>/ 被 .gitignore 擋 → 一行提示移除；此時不再重複報「未 commit」。
4. 索引列本人 personal atom 但本機無檔 → 一行「本機無檔」；他人的懸空不報。
5. 非 git 目錄 / 無 user / 無 personal 目錄且無懸空 → []；全域核心 memory dir（公開發布 repo，personal 刻意留本機）→ []。
6. 唯讀：跑完 repo 狀態不變。
7. 自身出錯不阻斷 SessionStart。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

CLAUDE = Path(__file__).resolve().parent.parent.parent  # hooks/verify/ → ~/.claude
sys.path.insert(0, str(CLAUDE / "hooks"))

from handlers import session_start as ss  # noqa: E402

USER = "u1"


def _git(repo: Path, *args):
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, encoding="utf-8")


def _index(mem: Path, *rel_paths: str):
    atoms = [{"name": Path(rp).stem, "path": rp, "triggers": ["x"],
              "scope": "personal:" + rp.split("/")[2]} for rp in rel_paths]
    (mem / "_atom_index.json").write_text(json.dumps({"version": 1, "atoms": atoms}), encoding="utf-8")


def _init_repo(root: Path):
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")


@pytest.fixture
def repo(tmp_path):
    """git repo，.claude/memory/personal/u1/a.md 已 commit，索引一致。回傳 memory dir。"""
    _init_repo(tmp_path)
    mem = tmp_path / ".claude" / "memory"
    pdir = mem / "personal" / USER
    pdir.mkdir(parents=True)
    (pdir / "a.md").write_text("# a\n", encoding="utf-8")
    _index(mem, f"memory/personal/{USER}/a.md")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "seed")
    return mem


def test_synced_is_silent(repo):
    assert ss._personal_sync_advisory(repo, USER) == []


def test_untracked_and_modified_reported(repo):
    pdir = repo / "personal" / USER
    (pdir / "b.md").write_text("# b\n", encoding="utf-8")
    (pdir / "c.md").write_text("# c\n", encoding="utf-8")
    (pdir / "a.md").write_text("# a changed\n", encoding="utf-8")
    (pdir / "b.access.json").write_text("{}", encoding="utf-8")  # 不計
    other = repo / "personal" / "someone_else"
    other.mkdir()
    (other / "zzz.md").write_text("z", encoding="utf-8")  # 他人不計
    out = ss._personal_sync_advisory(repo, USER)
    assert len(out) == 1
    assert "3 個 personal atom 尚未上版控" in out[0]
    assert "PersonalSync" in out[0]
    assert "zzz" not in out[0]


def test_ignored_dir_reports_gitignore_not_pending(repo):
    root = repo.parent.parent
    (root / ".gitignore").write_text(".claude/memory/personal/\n", encoding="utf-8")
    (repo / "personal" / USER / "b.md").write_text("# b\n", encoding="utf-8")
    out = ss._personal_sync_advisory(repo, USER)
    assert len(out) == 1
    assert ".gitignore" in out[0]
    assert "尚未上版控" not in out[0]


def test_index_dangling_only_own_user(repo):
    _index(repo, f"memory/personal/{USER}/a.md", f"memory/personal/{USER}/gone.md",
           "memory/personal/other/gone2.md")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "idx")
    out = ss._personal_sync_advisory(repo, USER)
    assert len(out) == 1
    assert "1 顆 personal atom 但本機無檔" in out[0]
    assert "gone" in out[0] and "gone2" not in out[0]


def test_dangling_without_local_dir(tmp_path):
    _init_repo(tmp_path)
    mem = tmp_path / ".claude" / "memory"
    mem.mkdir(parents=True)
    _index(mem, f"memory/personal/{USER}/only-on-other-machine.md")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "seed")
    out = ss._personal_sync_advisory(mem, USER)
    assert len(out) == 1 and "本機無檔" in out[0]


def test_non_git_is_silent(tmp_path):
    mem = tmp_path / ".claude" / "memory"
    (mem / "personal" / USER).mkdir(parents=True)
    (mem / "personal" / USER / "a.md").write_text("a", encoding="utf-8")
    assert ss._personal_sync_advisory(mem, USER) == []


def test_no_user_or_no_dir_is_silent(repo):
    assert ss._personal_sync_advisory(repo, "") == []
    assert ss._personal_sync_advisory(repo, "nobody") == []
    assert ss._personal_sync_advisory(None, USER) == []


def test_is_read_only(repo):
    (repo / "personal" / USER / "b.md").write_text("# b\n", encoding="utf-8")
    root = repo.parent.parent
    head = _git(root, "rev-parse", "HEAD").stdout
    status = _git(root, "status", "--porcelain").stdout
    ss._personal_sync_advisory(repo, USER)
    assert _git(root, "rev-parse", "HEAD").stdout == head
    assert _git(root, "status", "--porcelain").stdout == status


def test_internal_error_does_not_raise():
    assert ss._personal_sync_advisory(object(), USER) == []


def test_wired_into_session_start():
    src = (CLAUDE / "hooks" / "handlers" / "session_start.py").read_text(encoding="utf-8")
    assert "lines.extend(_personal_sync_advisory(project_mem_dir, v4_user))" in src


def test_global_memory_dir_is_silent(repo, monkeypatch):
    (repo / "personal" / USER / "b.md").write_text("# b", encoding="utf-8")
    monkeypatch.setattr(ss, "MEMORY_DIR", repo)
    assert ss._personal_sync_advisory(repo, USER) == []

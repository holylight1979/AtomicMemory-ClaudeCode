"""verify_refix_churn.py：同檔反覆 fix 的量尺（lib/refix_churn、tools/refix-churn.py）；Q12。

正例：tmp git 真 init 的排名；svn xml fixture 排名與人工標註前三一致；排除記憶目錄與收割提交；
同一 commit 同檔列兩次只算一次（refix_same_commit_pairs 開了才算兩次）；fix 判定英中；哨兵尾行三態（git／svn／none）。
反例：跨檔重修不算（A 修 X、B 修 Y → files_refixed 0）；單筆 fix 不列；超出 window 的兩筆仍列但 pairs 0。
怎麼跑：python -X utf8 -m pytest -q lib/verify/verify_refix_churn.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

CLAUDE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CLAUDE))
FIX = CLAUDE / "hooks" / "verify" / "fixtures" / "v6" / "refix"
TOOL = CLAUDE / "tools" / "refix-churn.py"
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]

from lib import refix_churn as rc  # noqa: E402


def _git(root: Path, *args: str, date: str = "") -> None:
    env = {**os.environ}
    if date:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = f"{date}T12:00:00"
    subprocess.run([*GIT, "-C", str(root), *args], check=True, capture_output=True, env=env, creationflags=NO_WINDOW)


def _commit(root: Path, msg: str, files: dict, date: str = "") -> None:
    for rel, body in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8", newline="\n")
    _git(root, "add", "--", *files)
    _git(root, "commit", "-q", "-m", msg, date=date)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    return root


def _svn_commits():
    return rc.parse_svn_xml(FIX.joinpath("svn-log.xml").read_text(encoding="utf-8"))


# ─── 判定 ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("msg,ok", [
    ("fix: login crash", True), ("Fixed the thing", True), ("hotfix prod", True), ("Bugfix #12", True),
    ("修正登入", True), ("壞掉的按鈕", True), ("錯誤訊息", True), ("a bug in x", True),
    ("docs: add readme", False), ("feat: prefix search", False), ("refactor suffix", False),
])
def test_is_fix(msg, ok):
    assert rc.is_fix(msg) is ok


# ─── git 真 init ──────────────────────────────────────────────────

def test_git_ranking_real_repo(repo):
    _commit(repo, "feat: init", {"Server/a.cs": "1", "Server/b.cs": "1", "Client/c.cs": "1"}, "2026-09-01")
    _commit(repo, "fix: a crash", {"Server/a.cs": "2"}, "2026-09-02")
    _commit(repo, "fix: a again", {"Server/a.cs": "3", "Server/b.cs": "2"}, "2026-09-05")
    _commit(repo, "修正 a", {"Server/a.cs": "4"}, "2026-09-07")
    _commit(repo, "fix: c once", {"Client/c.cs": "2"}, "2026-09-08")
    _commit(repo, "chore(memory): knowledge harvest", {".claude/memory/x.md": "k", "Server/a.cs": "5"}, "2026-09-09")
    assert rc.detect_vcs(repo) == "git" and rc.detect_vcs(repo / "Server") == "git"
    commits = rc.read_git(repo, since_days=60, now=datetime(2026, 9, 10))
    assert len(commits) == 6 and commits[0].paths == ["Server/a.cs", ".claude/memory/x.md"] or len(commits) == 6
    ranked = rc.rank_refixed(commits)
    assert ranked["commits"] == 6 and ranked["fix_commits"] == 4           # 收割提交不算 fix
    assert [f["file"] for f in ranked["files"]] == ["Server/a.cs"]           # b.cs 一筆、c.cs 一筆不列
    assert ranked["files"][0]["fix_commits"] == 3 and ranked["files"][0]["pairs_in_window"] == 3
    assert rc.hotspots_by_dir(ranked) == {"Server": 3}
    assert rc.read_git(repo, since_days=1, now=datetime(2026, 9, 10)) == []  # since 之外無資料


def test_git_fails_loudly_outside_repo(tmp_path):
    assert rc.detect_vcs(tmp_path) is None
    with pytest.raises(rc.VcsError):
        rc.read_git(tmp_path / "nope")
    assert rc.read_commits(tmp_path, None) == []


# ─── svn fixture 與人工標註 ───────────────────────────────────────

def test_svn_fixture_matches_annotation():
    ann = json.loads(FIX.joinpath("annotated.json").read_text(encoding="utf-8"))
    commits = _svn_commits()
    assert len(commits) == ann["totals"]["commits"]
    assert all(not p.startswith("/") for c in commits for p in c.paths)
    assert "trunk/Client/UI" not in [p for c in commits for p in c.paths]       # kind=dir 不收
    ranked = rc.rank_refixed(commits)
    assert ranked["fix_commits"] == ann["totals"]["fix_commits"]
    assert ranked["files_refixed"] == ann["totals"]["files_refixed"]
    assert [f["file"] for f in ranked["files"][:3]] == ann["top3"]
    for f in ranked["files"]:
        exp = ann["files"][f["file"]]
        assert (f["fix_commits"], f["pairs_in_window"], f["revs"]) == (exp["fix_commits"], exp["pairs_in_window"], exp["revs"]), f
    listed = {f["file"] for f in ranked["files"]}
    assert not listed & set(ann["excluded"])
    assert rc.hotspots_by_dir(ranked, ["Server", "Client"]) == {"Server": 7, "Client": 2}
    assert rc.hotspots_by_dir(ranked) == {"trunk": 9}


def test_exclusions_are_config(tmp_path):
    commits = _svn_commits()
    ranked = rc.rank_refixed(commits, {"refix_exclude": [], "refix_exclude_msg": []})
    files = {f["file"]: f for f in ranked["files"]}
    assert ranked["fix_commits"] == 9                                         # 收割與 atom 提交也算 fix 了
    assert files["trunk/Server/Login.cs"]["fix_commits"] == 4                 # r14 收割提交加進來
    assert "trunk/.claude/memory/_atom_index.json" not in files               # 只有一筆仍不列
    ranked = rc.rank_refixed(commits, {"refix_min_fixes": 3})
    assert [f["file"] for f in ranked["files"]] == ["trunk/Server/Login.cs"]


def test_same_commit_not_paired():
    commits = _svn_commits()
    dup = next(f for f in rc.rank_refixed(commits)["files"] if f["file"] == "trunk/Server/Dup.cs")
    assert dup["fix_commits"] == 2 and dup["pairs_in_window"] == 1 and dup["revs"] == ["18", "19"]
    dup2 = next(f for f in rc.rank_refixed(commits, {"refix_same_commit_pairs": True})["files"] if f["file"] == "trunk/Server/Dup.cs")
    assert dup2["fix_commits"] == 3 and dup2["pairs_in_window"] == 3


def test_window_and_cross_file_counterexamples():
    far = [rc.Commit("1", datetime(2026, 1, 1), "fix: x", ["a.cs"]), rc.Commit("2", datetime(2026, 3, 1), "fix: x", ["a.cs"])]
    r = rc.rank_refixed(far)
    assert r["files"][0]["fix_commits"] == 2 and r["files"][0]["pairs_in_window"] == 0   # 主尺仍列、副尺 0
    cross = [rc.Commit("1", datetime(2026, 9, 1), "fix: x", ["a.cs"]), rc.Commit("2", datetime(2026, 9, 2), "fix: y", ["b.cs"])]
    assert rc.rank_refixed(cross)["files_refixed"] == 0                                   # 反例：跨檔重修不算
    assert rc.rank_refixed(cross)["files_touched_by_fix"] == 2


def test_top_dir_of():
    assert rc.top_dir_of("Server/a.cs") == "Server" and rc.top_dir_of("a.cs") == ""
    assert rc.top_dir_of("trunk/Server/a.cs", ["server"]) == "server"
    assert rc.top_dir_of("trunk/Other/a.cs", ["Server"]) == ""


# ─── CLI 哨兵 ─────────────────────────────────────────────────────

def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-X", "utf8", str(TOOL), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", creationflags=NO_WINDOW)


def test_cli_sentinel_three_states(repo, tmp_path):
    r = _run("--svn-xml", str(FIX / "svn-log.xml"), "--top", "2")
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.rstrip().splitlines()[-1] == "REFIX_CHURN DONE vcs=svn commits=10 fix=7 files_refixed=4"
    assert "trunk/Server/Login.cs" in r.stdout and "trunk/Server/Dup.cs" not in r.stdout      # --top 2 只印兩列
    r = _run("--svn-xml", str(FIX / "svn-log.xml"), "--json")
    data = json.loads(r.stdout.rsplit("\n", 2)[0])
    assert data["files_refixed"] == 4 and data["files"][0]["file"] == "trunk/Server/Login.cs"
    _commit(repo, "fix: a", {"Server/a.cs": "1"})
    _commit(repo, "fix: a again", {"Server/a.cs": "2"})
    r = _run("--cwd", str(repo))
    assert r.returncode == 0 and r.stdout.rstrip().endswith("REFIX_CHURN DONE vcs=git commits=2 fix=2 files_refixed=1")
    plain = tmp_path / "plain"
    plain.mkdir()
    r = _run("--cwd", str(plain))
    assert r.returncode == 2 and "不是 git 工作樹" in r.stderr
    assert r.stdout.rstrip().endswith("REFIX_CHURN DONE vcs=none commits=0 fix=0 files_refixed=0")

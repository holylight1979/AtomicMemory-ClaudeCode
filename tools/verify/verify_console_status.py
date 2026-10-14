"""verify_console_status.py：總控台狀態腳本（tools/console-status.py）的輸出與尾行。

正例：暫存 git repo 兩筆 commit 落在 origin/main 之後 → unpushed=2；多一棵 worktree → worktrees=2 且列出分支；
兩軌來信各取最新一封並印「我在等」；verify log 取最後一行 exit=（多個取最後、沒有就印 pytest 總結）；
--inbox 指到別處照讀；--logs 只留最新幾份；--help 有「怎麼跑」。
反例：派工單（to-track-*）與非 verify 開頭的 log 不列；沒有 origin/main → unpushed=na；
信箱不存在 → 印訊號、tracks=0；不在 git repo → exit 2 且尾行照印。
怎麼跑：python -X utf8 -m pytest -q tools/verify/verify_console_status.py
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

CLAUDE = Path(__file__).resolve().parents[2]
TOOL = CLAUDE / "tools" / "console-status.py"
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
TAIL_RE = re.compile(r"^[A-Z][A-Z0-9_]* DONE( \w+=\S+)*$")


def _git(root: Path, *args: str) -> str:
    r = subprocess.run([*GIT, "-C", str(root), *args], check=True, capture_output=True, creationflags=NO_WINDOW)
    return r.stdout.decode("utf-8", "replace").strip()


def _commit(root: Path, name: str) -> str:
    (root / name).write_text(name, encoding="utf-8", newline="\n")
    _git(root, "add", "--", name)
    _git(root, "commit", "-q", "-m", name)
    return _git(root, "rev-parse", "HEAD")


def _write(p: Path, body: str, mtime: float) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8", newline="\n")
    os.utime(p, (mtime, mtime))


def _run(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    # 天花板設在 pytest 暫存根：「不在 repo」那案不會往上找到外層 repo
    env = {**os.environ, "GIT_CEILING_DIRECTORIES": str(cwd.parent)}
    return subprocess.run([sys.executable, "-X", "utf8", str(TOOL), *args], cwd=str(cwd), env=env,
                          capture_output=True, encoding="utf-8", creationflags=NO_WINDOW)


def _tail(r: subprocess.CompletedProcess) -> str:
    return r.stdout.rstrip().splitlines()[-1]


def _line_of(out: str, name: str) -> str:
    return next(line for line in out.splitlines() if name in line)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "update-ref", "refs/remotes/origin/main", _commit(root, "a.txt"))
    _commit(root, "b.txt")
    _commit(root, "c.txt")
    return root


def _seed_inbox(inbox: Path) -> None:
    now = time.time()
    _write(inbox / "from-track-alpha" / "001-alpha.md", "舊信\n我在等：舊的\n", now - 300)
    _write(inbox / "from-track-alpha" / "002-alpha.md", "新信\n\n我在等：調度合併\n", now - 100)
    _write(inbox / "from-track-beta" / "001-beta.md", "只有一封，沒寫等誰\n", now - 200)
    _write(inbox / "to-track-alpha" / "003-next.md", "派工單不是來信\n", now)
    con = inbox / "_console"
    _write(con / "verify_live_x.log", "HEAD: x\n100 passed in 1s\nexit=0\nSMOKE OK\n", now - 30)
    _write(con / "verify_x_snapshot_aaa.log", "exit=1\n重跑\n5 passed in 1s\nexit=0\n", now - 20)
    _write(con / "verify_y_snapshot_bbb.log", "3 failed, 9 passed in 2s\nY_CHECK FAIL\n", now - 10)
    _write(con / "codex-x.stderr.log", "exit=9\n", now)


# ─── 正例 ─────────────────────────────────────────────────────────

def test_counts_and_tail_line(repo):
    _seed_inbox(repo / "workflow" / "inbox")
    _git(repo, "worktree", "add", "-q", "-b", "track-alpha", str(repo.parent / "wt-alpha"))
    r = _run(repo)
    assert r.returncode == 0, r.stderr
    assert TAIL_RE.match(_tail(r))
    assert _tail(r) == "CONSOLE_STATUS DONE worktrees=2 unpushed=2 tracks=2 logs=3"
    assert "[track-alpha]" in r.stdout


def test_latest_letter_per_track_with_waiting_line(repo):
    _seed_inbox(repo / "workflow" / "inbox")
    out = _run(repo).stdout
    assert "002-alpha.md" in _line_of(out, "track-alpha ")
    assert "001-alpha.md" not in out
    assert "我在等：調度合併" in out and "我在等：舊的" not in out
    assert "001-beta.md" in _line_of(out, "track-beta ")
    assert "003-next.md" not in out


def test_verify_log_last_exit_line(repo):
    _seed_inbox(repo / "workflow" / "inbox")
    out = _run(repo).stdout
    assert _line_of(out, "verify_live_x.log").rstrip().endswith("exit=0")
    assert _line_of(out, "verify_x_snapshot_aaa.log").rstrip().endswith("exit=0")
    y = _line_of(out, "verify_y_snapshot_bbb.log")
    assert "無 exit 行" in y and "3 failed, 9 passed" in y
    assert "codex-x.stderr.log" not in out
    names = [n for n in ("verify_y_snapshot_bbb", "verify_x_snapshot_aaa", "verify_live_x") if n in out]
    assert [out.index(n) for n in names] == sorted(out.index(n) for n in names)   # 新的在前


def test_snapshot_log_named_exit_keys(repo):
    # 快照 log 寫 exit1=／smoke_exit=，尾段是「退回舊碼應紅」的總結；要印各 exit 鍵的最後值，不退回那行紅總結
    con = repo / "workflow" / "inbox" / "_console"
    _write(con / "verify_z_snapshot.log",
           "412 passed in 9s\nexit1=1\nexit1=0\nsmoke_exit=0\n=== 退回舊碼 ===\n31 failed, 1 passed in 2s\n", time.time())
    line = _line_of(_run(repo).stdout, "verify_z_snapshot.log").rstrip()
    assert line.endswith("exit1=0 smoke_exit=0")
    assert "31 failed" not in line


def test_logs_limit_keeps_newest(repo):
    _seed_inbox(repo / "workflow" / "inbox")
    r = _run(repo, "--logs", "1")
    assert "verify_y_snapshot_bbb.log" in r.stdout and "verify_live_x.log" not in r.stdout
    assert "共 3 份" in r.stdout
    assert _tail(r).endswith("logs=1")


def test_inbox_param_points_elsewhere(repo, tmp_path):
    other = tmp_path / "elsewhere"
    _write(other / "from-track-gamma" / "001-gamma.md", "我在等：對人裁定\n", time.time())
    r = _run(repo, "--inbox", str(other))
    assert "001-gamma.md" in r.stdout and "我在等：對人裁定" in r.stdout
    assert _tail(r).endswith("tracks=1 logs=0")


def test_help_says_how_to_run(tmp_path):
    r = _run(tmp_path, "--help")
    assert r.returncode == 0 and "怎麼跑" in r.stdout


# ─── 反例 ─────────────────────────────────────────────────────────

def test_missing_inbox_is_signalled(repo):
    r = _run(repo)
    assert r.returncode == 0
    assert "信箱不存在" in r.stdout
    assert _tail(r) == "CONSOLE_STATUS DONE worktrees=1 unpushed=2 tracks=0 logs=0"


def test_no_origin_main_gives_na(tmp_path):
    root = tmp_path / "solo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _commit(root, "a.txt")
    r = _run(root)
    assert r.returncode == 0
    assert "沒有 origin/main" in r.stdout
    assert " unpushed=na " in _tail(r)


def test_not_a_repo_exits_2_with_tail(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    r = _run(plain)
    assert r.returncode == 2
    assert _tail(r) == "CONSOLE_STATUS DONE worktrees=na unpushed=na tracks=0 logs=0"

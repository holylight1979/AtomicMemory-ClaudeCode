"""verify_sync_reminder_unpushed.py — SyncReminder「已 commit 未 push」判定。

「上GIT」＝commit＋push 一氣：模型 local commit 後 git status 乾淨、原同步閘閉嘴，
使用者卻仍未同步。驗證 handlers/stop.py：
  - _git_unpushed_roots：領先 upstream → 列 repo；已 push → 空；無 upstream → 空（fail-open）；
    路徑不存在 → 空（零子行程）
  - handle_stop：uncommitted 空但 unpushed 非空 → block 訊息「已 commit 但尚未 push」；
    config sync_reminder.unpushed=false → 不查、不擋
真 git 子行程（tmp bare upstream + clone），不 mock git。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

from handlers import stop as st  # noqa: E402

_SID = "sid"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd)] + list(args), check=True,
                   capture_output=True, text=True, timeout=15)


@pytest.fixture
def clone(tmp_path):
    """bare upstream + clone，clone 已推一個 commit（有 upstream、不領先）。"""
    bare = tmp_path / "up.git"
    _git(tmp_path, "init", "-q", "--bare", str(bare))
    work = tmp_path / "work"
    _git(tmp_path, "clone", "-q", str(bare), str(work))
    _git(work, "config", "user.email", "t@t")
    _git(work, "config", "user.name", "t")
    (work / "a.py").write_text("x", encoding="utf-8")
    _git(work, "add", "a.py")
    _git(work, "commit", "-q", "-m", "init")
    _git(work, "push", "-q", "-u", "origin", "HEAD")
    return work


def _commit_more(work: Path) -> None:
    (work / "a.py").write_text("y", encoding="utf-8")
    _git(work, "commit", "-q", "-am", "more")


# ─── _git_unpushed_roots ────────────────────────────────────────

def test_ahead_of_upstream_listed(clone):
    _commit_more(clone)
    out = st._git_unpushed_roots([{"path": str(clone / "a.py")}])
    assert len(out) == 1 and "領先 1 commit" in out[0]


def test_pushed_is_empty(clone):
    _commit_more(clone)
    _git(clone, "push", "-q")
    assert st._git_unpushed_roots([{"path": str(clone / "a.py")}]) == []


def test_no_upstream_fail_open(tmp_path):
    r = tmp_path / "solo"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@t")
    _git(r, "config", "user.name", "t")
    (r / "a.py").write_text("x", encoding="utf-8")
    _git(r, "add", "a.py")
    _git(r, "commit", "-q", "-m", "init")
    assert st._git_unpushed_roots([{"path": str(r / "a.py")}]) == []


def test_missing_path_skipped():
    assert st._git_unpushed_roots([{"path": "c:/nope/x.py"}, {}]) == []


# ─── handle_stop 控制流 ─────────────────────────────────────────

@pytest.fixture
def driven(monkeypatch):
    monkeypatch.setattr(st, "_find_session_transcript", lambda *a, **k: None)
    monkeypatch.setattr(st, "get_last_assistant_text", lambda *a, **k: "全部完成了")
    monkeypatch.setattr(st, "token_warn_payload", lambda *a, **k: "")
    monkeypatch.setattr(st, "detect_evasion", lambda *a, **k: None)
    monkeypatch.setattr(st, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(st, "_attribute_usefulness", lambda *a, **k: None)
    monkeypatch.setattr(st, "_should_deep_postmortem", lambda *a, **k: False)
    monkeypatch.setattr(st, "_maybe_spawn_user_extract_worker", lambda *a, **k: None)
    monkeypatch.setattr(st, "_detect_uncommitted_files", lambda mf: [])
    calls = []

    def fake_unpushed(mf):
        calls.append(1)
        return ["c:/repo（領先 1 commit）"]

    monkeypatch.setattr(st, "_git_unpushed_roots", fake_unpushed)

    def drive(capsys, config=None):
        state = {
            "phase": "working",
            "modified_files": [{"path": "c:/repo/x.py", "tool": "Edit", "session_id": _SID}],
            "failing_tests": [],
            "recent_user_prompts": [],
            "stop_blocked_count": 0,
            "scan_report_warned": True,
        }
        monkeypatch.setattr(st, "_ensure_state", lambda *a, **k: state)
        with pytest.raises(SystemExit):
            st.handle_stop({"session_id": _SID, "cwd": ""}, config or {})
        return capsys.readouterr().out, calls

    return drive


def test_unpushed_blocks_with_message(driven, capsys):
    out, calls = driven(capsys)
    assert calls and "已 commit 但尚未 push" in out and "commit + push 一氣" in out


def test_unpushed_disabled_by_config(driven, capsys):
    out, calls = driven(capsys, {"sync_reminder": {"unpushed": False}})
    assert not calls and "已 commit 但尚未 push" not in out

"""verify_base_red_tracked.py：改動前基底就紅、有追蹤項的紅測不算本回合欠帳（規則 BASE_RED_TRACKED_NOT_OWED）。

端到端兩段，都用真 git（tmp 裡建 repo：基底 commit → 下一個 commit）：
- PostToolUse：跑紅時記下那次在哪個 commit、已追蹤檔有沒有改動（state red_run_commits）；`cd <別處> && pytest` 記換到的目錄；
  工作樹有改動記成不乾淨；沒逐支列出失敗不記。
- Stop：收尾寫「基底紅｜<那支>：<基底 commit> 也紅；追蹤 <文件>」→ 三件事實都對得上才放行並留帳（哪一支、哪個基底、哪份追蹤）；
  反例照擋：基底綠（沒有基底的紅可對）、基底那次工作樹不乾淨、基底是自己提交的、追蹤文件本 session 改過、追蹤文件沒點名。
純函式各條缺口的案例在 verify_release_rules.py 的 008 段。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_base_red_tracked.py
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

VERIFY = Path(__file__).resolve().parent
sys.path.insert(0, str(VERIFY))

from verify_stop_reconcile import (  # noqa: E402,F401
    _SID, _CASE, _aec, _mf, _scope_ledger_isolated, _temp_rules_off, driven,
)
from handlers import post_tool_use as pt  # noqa: E402

UNIT = "hooks/verify/verify_old.py::test_legacy"
RED_OUT = f"FAILED {UNIT} - assert 0\n1 failed in 0.10s"
RED_CMD = "python -m pytest hooks/verify/verify_old.py"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), "-c", "commit.gpgsign=false", *args], capture_output=True, text=True,
                          check=True).stdout.strip()


@pytest.fixture()
def repo(tmp_path):
    """基底 commit（那支測試在這裡就紅）→ 下一個 commit（現在的 HEAD）；追蹤文件在 repo 外、點名那支。"""
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@example.invalid")
    _git(r, "config", "user.name", "t")
    (r / "a.txt").write_text("1\n", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "base")
    base = _git(r, "rev-parse", "HEAD")
    (r / "a.txt").write_text("2\n", encoding="utf-8")
    _git(r, "commit", "-qam", "next")
    track = tmp_path / "tracking.md"
    track.write_text("- 已知紅：test_legacy 在基底就紅，排下一輪修\n", encoding="utf-8")
    return r, base, track


def _session(started: str = "") -> dict:
    """session 開始時間：預設「現在」（fixture 剛建的兩個 commit 都在 session 開始前）。"""
    return {"cwd": "", "started_at": started or datetime.now(timezone.utc).isoformat()}


def _red(cwd: Path) -> dict:
    return {"cmd": RED_CMD, "summary": RED_OUT, "turn_seq": 5, "session_id": _SID, "pytest": True, "cwd": str(cwd)}


def _run_row(head: str, clean: bool = True) -> dict:
    return {"session_id": _SID, "units": [UNIT], "head": head, "clean": clean, "dir": "x", "turn_seq": 5}


def _post_red(state: dict, cwd: Path, command: str = RED_CMD) -> None:
    pt._track_test_result(state, {"session_id": _SID, "cwd": str(cwd),
                                  "tool_response": {"stdout": RED_OUT, "stderr": "", "exit_code": 1}}, command, "Bash", {})


def test_post_tool_use_records_commit_and_cleanliness(repo, tmp_path):
    """跑紅記 HEAD 與乾淨與否；`cd <基底的工作樹> && pytest` 記換到的那個目錄；已追蹤檔改了 → 不乾淨；沒逐支列出的紅不記。"""
    r, base, _ = repo
    state: dict = {"turn_seq": 5}
    _post_red(state, r)
    row = state["red_run_commits"][-1]
    assert row["head"] == _git(r, "rev-parse", "HEAD") and row["clean"] is True and row["units"] == [UNIT]
    wt = tmp_path / "base-wt"
    _git(r, "worktree", "add", "-q", "--detach", str(wt), base)
    _post_red(state, tmp_path, f"cd {wt.as_posix()} && {RED_CMD}")
    row = state["red_run_commits"][-1]
    assert row["head"] == base and row["clean"] is True and Path(row["dir"]) == wt
    (r / "a.txt").write_text("dirty\n", encoding="utf-8")
    _post_red(state, r)
    assert state["red_run_commits"][-1]["clean"] is False
    n = len(state["red_run_commits"])
    pt._track_test_result(state, {"session_id": _SID, "cwd": str(r), "tool_response": {"stdout": "boom", "exit_code": 1}},
                          RED_CMD, "Bash", {})
    assert len(state["red_run_commits"]) == n                                # 看不出是哪一支紅：不記成證據


def test_stop_releases_when_base_red_proven_and_tracked(driven, capsys, repo):
    r, base, track = repo
    text = f"全部完成了。\n基底紅｜test_legacy：{base[:10]} 也紅；追蹤 {track}"
    out, _, logs = driven(text, capsys, failing_tests=[_red(r)], red_run_commits=[_run_row(base)], session=_session(),
                          modified_files=[_mf(_CASE, 5)], anti_evasion_report=_aec(5, "無", "無"))
    assert "TestFailGate" not in out, out
    hit = [p for g, p in logs if g == "testfail_base_red"]
    assert hit and hit[0]["units"] == [UNIT] and hit[0]["base"] == [base[:10]] and hit[0]["tracking"] == [str(track)]


def test_stop_base_green_this_red_still_blocks(driven, capsys, repo):
    """反例：基底跑過是綠的（沒有基底的紅紀錄，只有現在 HEAD 這次的紅）→ 照擋，擋訊息說沒在基底跑紅過。"""
    r, base, track = repo
    head = _git(r, "rev-parse", "HEAD")
    text = f"全部完成了。\n基底紅｜test_legacy：{base[:10]} 也紅；追蹤 {track}"
    out, _, logs = driven(text, capsys, failing_tests=[_red(r)], red_run_commits=[_run_row(head)], session=_session(),
                          modified_files=[_mf(_CASE, 5)], anti_evasion_report=_aec(5, "無", "無"))
    assert "TestFailGate" in out and "沒在基底" in out and not [p for g, p in logs if g == "testfail_base_red"]


@pytest.mark.parametrize("change, why", [
    ("dirty", "沒在基底"),                    # 基底那次工作樹有改動：不算在基底跑的
    ("own_commit", "自己提交的"),             # 基底是本 session 自己提交的：不是改動前
    ("tracking_edited", "本 session 改過"),   # 追蹤項是這個 session 才寫的
    ("not_named", "沒點名"),                  # 追蹤文件沒提到這一支
    ("no_tracking", "沒寫追蹤文件"),
    ("born_after_start", "開始前就有"),        # 基底是本 session 開始後才有的 commit（例：自己做的 merge）
], ids=["dirty-base-run", "own-commit", "tracking-edited", "tracking-not-naming", "no-tracking", "born-after-start"])
def test_stop_missing_one_condition_blocks(driven, capsys, repo, change, why):
    r, base, track = repo
    rows, mods = [_run_row(base, clean=change != "dirty")], [_mf(_CASE, 5)]
    extra = {"session": _session("2000-01-01T00:00:00+00:00" if change == "born_after_start" else "")}
    if change == "own_commit":
        extra["committed_new_code"] = {str(r).lower(): {"shas": [base], "paths": []}}
    if change == "tracking_edited":
        mods.append(_mf(str(track), 5))
    if change == "not_named":
        track.write_text("- 已知紅：別的測試\n", encoding="utf-8")
    tail = "" if change == "no_tracking" else f"；追蹤 {track}"
    text = f"全部完成了。\n基底紅｜test_legacy：{base[:10]} 也紅{tail}"
    out, _, _ = driven(text, capsys, failing_tests=[_red(r)], red_run_commits=rows, modified_files=mods,
                       anti_evasion_report=_aec(5, "無", "無"), **extra)
    assert "TestFailGate" in out and why in out, out

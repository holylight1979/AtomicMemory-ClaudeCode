"""verify_usage_snapshot_align.py：usage-snapshot 的排程跟著週重置時間走。

做什麼：
- _top_weekly_limit：週額度多條取用量最高那條；非週額度、缺 resets_at 或 percent 的不算；沒有回 None。
- _reset_time：API 的 resets_at 轉本機時區、取整到分（整點前幾百毫秒算整點）。
- align_schedule：排程對齊到重置前 LEAD_MIN 分鐘；PowerShell 回 moved／same／none／失敗各一句話（不真的動排程）。
- do_snapshot：網頁那條讀到重置時間才對齊；VS Code 面板那條沒有來源，排程不動並寫明。
怎麼跑：python -X utf8 -m pytest -q tools/verify/verify_usage_snapshot_align.py
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

TREE = Path(__file__).resolve().parents[2]


@pytest.fixture
def us(tmp_path, monkeypatch):
    monkeypatch.setenv("WG_CLAUDE_DIR", str(tmp_path))
    spec = importlib.util.spec_from_file_location("usage_snapshot_align_probe",
                                                  TREE / "tools" / "usage-snapshot" / "usage_snapshot.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    yield mod
    sys.modules.pop(spec.name, None)


def _limit(percent, resets_at="2026-11-02T13:00:00+00:00", group="weekly", model=None):
    lim = {"group": group, "percent": percent, "resets_at": resets_at}
    if model:
        lim["scope"] = {"model": {"display_name": model}}
    return lim


def test_top_weekly_limit_takes_highest_weekly(us):
    api = {"limits": [_limit(40), _limit(90, model="Fable"), _limit(99, group="session"),
                      _limit(100, resets_at=None), {"group": "weekly", "resets_at": "x"}]}
    assert us._top_weekly_limit(api)["percent"] == 90
    assert us._top_weekly_limit({}) is None
    assert us._top_weekly_limit({"limits": [_limit(99, group="session")]}) is None


def test_reset_time_local_and_rounded(us):
    got = us._reset_time(_limit(1, resets_at="2026-11-02T12:59:59.700000+00:00"))
    want = datetime(2026, 11, 2, 13, 0, tzinfo=timezone.utc).astimezone()
    assert got == want and got.second == 0


def _fake_ps(stdout, rc=0, stderr=""):
    calls = []

    def run(script):
        calls.append(script)
        return subprocess.CompletedProcess([], rc, stdout=stdout, stderr=stderr)
    return run, calls


@pytest.mark.parametrize("stdout,rc,expect", [
    ("moved\n", 0, "排程改為每週 Monday 20:50"),
    ("same\n", 0, "排程維持每週 Monday 20:50"),
    ("none\n", 0, "排程沒註冊"),
    ("", 1, "排程對齊失敗"),
])
def test_align_schedule_lead_minutes(us, monkeypatch, stdout, rc, expect):
    run, calls = _fake_ps(stdout, rc, "boom" if rc else "")
    monkeypatch.setattr(us, "_powershell", run)
    reset = datetime(2026, 11, 2, 21, 0).astimezone()  # 週一 21:00
    msg = us.align_schedule(reset)
    assert expect in msg
    assert "-DaysOfWeek Monday -At 20:50" in calls[0] and us.TASK_NAME in calls[0]


def test_align_schedule_crosses_midnight_to_previous_day(us, monkeypatch):
    run, calls = _fake_ps("moved")
    monkeypatch.setattr(us, "_powershell", run)
    us.align_schedule(datetime(2026, 11, 3, 0, 5).astimezone())  # 週二 00:05 → 週一 23:55
    assert "-DaysOfWeek Monday -At 23:55" in calls[0]


def _wire(us, monkeypatch, vscode_ok: bool):
    aligned, finished = [], []

    def vscode(result, now):
        if vscode_ok:
            result.update(ok=True, file="x.png", source="vscode")
            return None
        return "找不到 VS Code"

    def web(result, now, headed):
        result.update(ok=True, file="y.png", source="web", weekly_reset="2026-11-02T21:00+08:00")

    monkeypatch.setattr(us, "VSCODE_ATTEMPTS", 1)
    monkeypatch.setattr(us, "capture_vscode", vscode)
    monkeypatch.setattr(us, "capture_web", web)
    monkeypatch.setattr(us, "_push_to_repo", lambda result: None)
    monkeypatch.setattr(us, "_finish", finished.append)
    monkeypatch.setattr(us, "align_schedule", lambda reset: aligned.append(reset) or "對齊了")
    return aligned, finished


def test_do_snapshot_web_path_aligns(us, monkeypatch):
    aligned, finished = _wire(us, monkeypatch, vscode_ok=False)
    assert us.do_snapshot(headed=True) == 0
    assert aligned == [datetime.fromisoformat("2026-11-02T21:00+08:00")]
    assert finished[0]["schedule"] == "對齊了"


def test_do_snapshot_vscode_path_leaves_schedule(us, monkeypatch):
    aligned, finished = _wire(us, monkeypatch, vscode_ok=True)
    assert us.do_snapshot(headed=True) == 0
    assert aligned == []
    assert "排程沒動" in finished[0]["schedule"]

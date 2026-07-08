"""verify_health_weekly.py — 週健檢死人開關 + health-weekly 純函式驗證。

覆蓋：
  - session_start._health_advisory：缺檔 / 逾期 / red>0 / 健康 / 壞 JSON
    五態各自浮出正確 advisory（fail-open 必告知，健康時零 context 佔用）
  - tools/health-weekly.py：_promotion_last_ts 讀尾筆 ts、write_report 輪替保留

對應：hooks/handlers/session_start.py（_health_advisory / HEALTH_RUN_STALE_DAYS）、
tools/health-weekly.py。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "hooks"))
sys.path.insert(0, str(_ROOT / "hooks" / "handlers"))

from session_start import _health_advisory, HEALTH_RUN_STALE_DAYS  # noqa: E402


def _write_last_run(tmp_path, days_ago=0, red=0):
    p = tmp_path / "health-last-run.json"
    at = (datetime.now() - timedelta(days=days_ago)).isoformat(timespec="seconds")
    p.write_text(json.dumps({"at": at, "red": red, "yellow": 0,
                             "report": "workflow/health-reports/health-x.md"}),
                 encoding="utf-8")
    return p


# ─── _health_advisory 五態 ───────────────────────────────────────────


def test_missing_file_advises(tmp_path):
    out = _health_advisory(tmp_path / "nope.json")
    assert len(out) == 1 and "排程未註冊" in out[0]


def test_stale_run_advises(tmp_path):
    p = _write_last_run(tmp_path, days_ago=HEALTH_RUN_STALE_DAYS + 5)
    out = _health_advisory(p)
    assert any("天未跑" in x for x in out)


def test_red_findings_advise(tmp_path):
    p = _write_last_run(tmp_path, days_ago=1, red=3)
    out = _health_advisory(p)
    assert any("3 項需處理" in x for x in out)


def test_healthy_is_silent(tmp_path):
    p = _write_last_run(tmp_path, days_ago=1, red=0)
    assert _health_advisory(p) == []


def test_corrupt_json_advises(tmp_path):
    p = tmp_path / "health-last-run.json"
    p.write_text("{bad", encoding="utf-8")
    out = _health_advisory(p)
    assert len(out) == 1 and "不可解析" in out[0]


# ─── health-weekly 純函式 ────────────────────────────────────────────


@pytest.fixture()
def hw(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "health_weekly_under_test", _ROOT / "tools" / "health-weekly.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "MEMORY", tmp_path)
    monkeypatch.setattr(mod, "REPORT_DIR", tmp_path / "health-reports")
    return mod


def test_promotion_last_ts_reads_tail(hw, tmp_path):
    p = tmp_path / "_promotion_audit.jsonl"
    rows = [{"ts": "2026-01-01T00:00:00", "action": "hint"},
            {"ts": "2026-06-30T12:34:56", "action": "hint"}]
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    assert hw._promotion_last_ts() == datetime(2026, 6, 30, 12, 34, 56)


def test_promotion_last_ts_missing_is_none(hw):
    assert hw._promotion_last_ts() is None


def test_write_report_rotates(hw):
    for i in range(hw.KEEP_REPORTS + 3):
        hw.write_report({"at": f"2026-01-{i + 1:02d}T00:00:00",
                         "red": [], "yellow": [], "info": []})
    left = list((hw.REPORT_DIR).glob("health-*.md"))
    assert len(left) == hw.KEEP_REPORTS

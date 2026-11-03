"""verify_usage_watch.py — tools/usage-watch.py 判定邏輯 + SessionStart 用量監控死人開關。

覆蓋：
  - analyze_account：① 突增（固定門檻／跨週期不算／歷史自適應）② 預估用完（最近 24h／退回本週平均／不報）
    ③ 里程碑只報最高階 ④ 5 小時窗、日用量（預算／歷史基線拉高門檻）、週（上週同期＋結算）
  - deltas 跨重置、fresh_alerts 冷卻、merge_ledger 同格取大
  - session_start._usage_watch_advisory：缺檔／健康／逾期／查詢失敗／通知失敗／壞 JSON

直接跑：python hooks/verify/verify_usage_watch.py → USAGE_WATCH_CHECK PASS|FAIL
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "hooks"))
sys.path.insert(0, str(_ROOT / "hooks" / "handlers"))

from session_start import _usage_watch_advisory, USAGE_WATCH_STALE_HOURS  # noqa: E402

_spec = importlib.util.spec_from_file_location("usage_watch", _ROOT / "tools" / "usage-watch.py")
uw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(uw)

TZ = timezone(timedelta(hours=8))
NOW = datetime(2026, 11, 5, 12, 0, tzinfo=TZ)
RESET = NOW + timedelta(days=3)
ARGS = argparse.Namespace(rate_alert=4.0, five_hour_alert=80.0, daily_budget=20.0, week_factor=1.5)


def rec(hours_ago: float, weekly: float, reset: datetime = RESET, five=None) -> dict:
    return {"at": (NOW - timedelta(hours=hours_ago)).isoformat(timespec="seconds"), "plan": "t",
            "weekly": weekly, "weekly_reset": reset.isoformat(),
            "five_hour": five, "five_hour_reset": (NOW + timedelta(hours=2)).isoformat() if five is not None else None}


def keys(history, cur) -> list[str]:
    return [a["key"] for a in uw.analyze_account(cur, history, NOW, ARGS)[1]]


# ─── ① 突增 ───────────────────────────────────────────

def test_rate_fixed_threshold():
    assert "rate" in keys([rec(1, 20)], rec(0, 30))
    assert "rate" not in keys([rec(1, 28)], rec(0, 30))


def test_rate_skips_too_close_sample():
    assert "rate" in keys([rec(1, 20), rec(0.1, 29)], rec(0, 30))


def test_rate_ignores_short_gap_quantization():
    # 實際 3.5%/h：23 分鐘前 6%、86 分鐘前 3%，現在 8% → 不該被短間隔放大成突增
    assert "rate" not in keys([rec(86 / 60, 3), rec(23 / 60, 6)], rec(0, 8))


def test_rate_ignores_cross_period():
    assert "rate" not in keys([rec(1, 20, reset=NOW - timedelta(hours=0.5))], rec(0, 30))


def test_rate_adaptive_threshold_from_history():
    hist = [rec(12 - i, 10 + i * 2) for i in range(12)]  # 歷史每小時 +2 → 門檻 max(4, 6)
    assert "rate" not in keys(hist, rec(0, 10 + 11 * 2 + 5))
    assert "rate" in keys(hist, rec(0, 10 + 11 * 2 + 7))


# ─── ② 預估用完 ────────────────────────────────────────

def test_pace_recent_24h_alerts():
    lines, alerts = uw.analyze_account(rec(0, 70), [rec(20, 40)], NOW, ARGS)
    assert any(a["key"] == "pace" and "最近 20h" in a["msg"] for a in alerts)


def test_pace_falls_back_to_week_average():
    lines, alerts = uw.analyze_account(rec(0, 70), [], NOW, ARGS)
    assert any(a["key"] == "pace" and "本週平均" in a["msg"] for a in alerts)


def test_pace_quiet_when_slow():
    assert keys([rec(20, 30)], rec(0, 32)) == []


# ─── ③ 里程碑 ④ 5 小時窗 ──────────────────────────────

def test_milestone_reports_highest_only():
    ks = keys([], rec(0, 80))
    assert [k for k in ks if k.startswith("milestone")] == [f"milestone75@{uw.period_key(rec(0, 80)):%Y%m%d%H}"]


def test_five_hour_window():
    assert "five_hour" in keys([], rec(0, 10, five=85))
    assert "five_hour" not in keys([], rec(0, 10, five=50))


# ─── 日、週 ───────────────────────────────────────────

def test_daily_budget_without_baseline():
    assert f"daily@{NOW.date()}" in keys([rec(2, 10)], rec(0, 32))


def test_daily_baseline_raises_threshold():
    reset = NOW + timedelta(days=1)
    hist = [rec(24 * d, 12 * (6 - d), reset=reset) for d in range(6, 0, -1)]  # 過去 5 天每天 +12 → 門檻 max(20, 24)
    assert f"daily@{NOW.date()}" not in keys(hist, rec(0, 60 + 22, reset=reset))
    assert f"daily@{NOW.date()}" in keys(hist, rec(0, 60 + 25, reset=reset))


def test_week_vs_last_and_settlement():
    prev_reset = RESET - timedelta(days=7)
    hist = [rec(24 * 7 + 1, 15, reset=prev_reset), rec(24 * 7, 20, reset=prev_reset), rec(24 * 4 + 1, 95, reset=prev_reset)]
    lines, alerts = uw.analyze_account(rec(0, 40), hist, NOW, ARGS)
    assert "week_vs_last" in [a["key"] for a in alerts]
    assert any("近幾週結算" in ln and "95%" in ln for ln in lines)
    assert "week_vs_last" not in keys(hist, rec(0, 25))


def test_deltas_across_reset():
    out = uw.deltas([rec(2, 90, reset=NOW - timedelta(hours=1)), rec(0, 4)])
    assert [d for _, d in out] == [4]


# ─── 冷卻、帳本 ───────────────────────────────────────

def test_fresh_alerts_cooldown():
    alerts = [uw.alert("rate", "x", 3), uw.alert("pace", "y", 6), uw.alert("m50@p", "z", 24 * 8)]
    log = [
        {"at": (NOW - timedelta(hours=2)).isoformat(), "key": "rate", "notified": True},
        {"at": (NOW - timedelta(hours=7)).isoformat(), "key": "pace", "notified": True},
        {"at": (NOW - timedelta(days=5)).isoformat(), "key": "m50@p", "notified": True},
        {"at": (NOW - timedelta(hours=1)).isoformat(), "key": "pace", "notified": False},
    ]
    assert [a["key"] for a in uw.fresh_alerts(alerts, log, NOW)] == ["pace"]


def test_merge_ledger_keeps_max(tmp_path, monkeypatch):
    monkeypatch.setattr(uw, "OUT_DIR", tmp_path)
    monkeypatch.setattr(uw, "LEDGER", tmp_path / "hourly.json")
    h = NOW.replace(minute=0)
    uw.merge_ledger({h: {"p": [10, 100]}})
    merged = uw.merge_ledger({h: {"p": [5, 50], "q": [1, 1]}})
    assert merged[h] == {"p": [10, 100], "q": [1, 1]}


# ─── SessionStart 死人開關 ────────────────────────────

def _last_run(tmp_path, hours_ago=0, **kw):
    p = tmp_path / "last-run.json"
    at = (datetime.now() - timedelta(hours=hours_ago)).astimezone().isoformat(timespec="seconds")
    p.write_text(json.dumps({"at": at, "ok": True, "error": None, "notify_errors": {}, **kw}), encoding="utf-8")
    return p


def test_advisory_missing_file_silent(tmp_path):
    assert _usage_watch_advisory(tmp_path / "nope.json") == []


def test_advisory_healthy_silent(tmp_path):
    assert _usage_watch_advisory(_last_run(tmp_path, 1)) == []


def test_advisory_stale_names_task(tmp_path):
    out = _usage_watch_advisory(_last_run(tmp_path, USAGE_WATCH_STALE_HOURS + 1))
    assert out and "Claude-Usage-Watch-" in out[0] and "--register" in out[0]


def test_advisory_failed_query(tmp_path):
    out = _usage_watch_advisory(_last_run(tmp_path, 1, ok=False, error="token 已過期"))
    assert out and "token 已過期" in out[0]


def test_advisory_notify_failed(tmp_path):
    out = _usage_watch_advisory(_last_run(tmp_path, 1, notify_errors={"discord": "HTTP 404"}))
    assert out and "discord" in out[0] and "HTTP 404" in out[0]


# ─── 通知管道 ─────────────────────────────────────────

def _fake_channels(monkeypatch, tmp_path, toast_err=None, discord_err=None, webhook="https://x"):
    monkeypatch.setattr(uw, "SETTINGS", tmp_path / "settings.json")
    if webhook is not None:
        (tmp_path / "settings.json").write_text(json.dumps({"discord_webhook": webhook}), encoding="utf-8")
    posts = []
    monkeypatch.setattr(uw, "toast", lambda t, b: toast_err)
    monkeypatch.setattr(uw, "discord_post", lambda u, t: posts.append(t) or discord_err)
    return posts


def test_notify_both_channels(monkeypatch, tmp_path):
    posts = _fake_channels(monkeypatch, tmp_path)
    assert uw.notify("T", "B") == (True, {})
    assert posts == ["**T**\nB"]


def test_notify_discord_alone_counts_as_sent(monkeypatch, tmp_path):
    _fake_channels(monkeypatch, tmp_path, toast_err="no session")
    assert uw.notify("T", "B") == (True, {"toast": "no session"})


def test_notify_all_failed(monkeypatch, tmp_path):
    _fake_channels(monkeypatch, tmp_path, toast_err="a", discord_err="b")
    assert uw.notify("T", "B") == (False, {"toast": "a", "discord": "b"})


def test_notify_without_webhook(monkeypatch, tmp_path):
    posts = _fake_channels(monkeypatch, tmp_path, webhook=None)
    assert uw.notify("T", "B") == (True, {}) and posts == []


def test_load_webhook_bad_json(monkeypatch, tmp_path):
    monkeypatch.setattr(uw, "SETTINGS", tmp_path / "settings.json")
    (tmp_path / "settings.json").write_text("{", encoding="utf-8")
    url, err = uw.load_webhook()
    assert url is None and "不可解析" in err


def test_report_text_has_account_block_and_alerts():
    acc_lines, alerts = ["== 帳號額度 ==", "  每週 8%"], [uw.alert("rate", "每週額度一小時漲 9%", 3)]
    text = uw.report_text(NOW, acc_lines, alerts)
    assert text.startswith("📊 **Claude 用量**（11-05 12:00）")
    assert "```\n每週 8%\n```" in text and text.endswith("⚠ 每週額度一小時漲 9%")


def test_advisory_bad_json(tmp_path):
    p = tmp_path / "last-run.json"
    p.write_text("{", encoding="utf-8")
    out = _usage_watch_advisory(p)
    assert out and "不可解析" in out[0]


if __name__ == "__main__":
    rc = pytest.main([__file__, "-q"])
    print(f"USAGE_WATCH_CHECK {'PASS' if rc == 0 else 'FAIL'}")
    sys.exit(0 if rc == 0 else 1)

"""verify_outcome_watch.py — 效用歸因遙測（outcome unknown 比率監測）。

驗證「α/β 晉升軌靜默停滯」的早期偵測閉環：
  - stop._bump_outcome_stats：outcome 三值 → success/fail/unknown 計數。
  - wg_evasion._unknown_streak：連續 window 筆 > threshold 才成立。
  - wg_evasion.flush_outcome_stats：SessionEnd 落 workflow/outcome_stats.jsonl
    （滾動 50 筆）+ 連續偏高回 advisory；turn 數 < min_turns 不計；fail-open。

對應：handlers/stop.py（_bump_outcome_stats，掛 _attribute_usefulness 內
once-per-turn 區）、wg_evasion.py（flush/_unknown_streak）、
handlers/session_end.py（flush → marker）、handlers/session_start.py（marker → 注入）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify/ → hooks/
sys.path.insert(0, str(HOOKS_DIR))

import wg_evasion  # noqa: E402
from wg_evasion import _unknown_streak, flush_outcome_stats  # noqa: E402
from handlers.stop import _bump_outcome_stats  # noqa: E402


# ─── _bump_outcome_stats ─────────────────────────────────────────────────────


def test_bump_three_values():
    state = {}
    _bump_outcome_stats(state, True)
    _bump_outcome_stats(state, False)
    _bump_outcome_stats(state, None)
    _bump_outcome_stats(state, None)
    assert state["outcome_stats"] == {"success": 1, "fail": 1, "unknown": 2}


# ─── _unknown_streak ─────────────────────────────────────────────────────────


def _e(ratio):
    return {"ratio": ratio}


def test_streak_all_high():
    assert _unknown_streak([_e(0.8), _e(0.9), _e(0.75)], 0.7, 3) is True


def test_streak_one_low_breaks():
    assert _unknown_streak([_e(0.8), _e(0.5), _e(0.9)], 0.7, 3) is False


def test_streak_insufficient_entries():
    assert _unknown_streak([_e(0.9), _e(0.9)], 0.7, 3) is False


def test_streak_only_recent_window_counts():
    """window 外的舊低值不影響（只看最近 window 筆）。"""
    assert _unknown_streak([_e(0.1), _e(0.8), _e(0.9), _e(0.75)], 0.7, 3) is True


# ─── flush_outcome_stats ─────────────────────────────────────────────────────


def _cfg(threshold=0.7, window=3, min_turns=3, enabled=True):
    return {"usefulness": {"unknown_watch": {
        "enabled": enabled, "threshold": threshold,
        "window": window, "min_turns": min_turns,
    }}}


def test_flush_below_min_turns_skipped(tmp_path, monkeypatch):
    """turn 數 < min_turns → 不落檔、回 None（小樣本無意義）。"""
    monkeypatch.setattr(wg_evasion, "OUTCOME_STATS_PATH", tmp_path / "o.jsonl")
    state = {"outcome_stats": {"success": 1, "fail": 0, "unknown": 1}}
    assert flush_outcome_stats(state, _cfg(min_turns=3), "s1") is None
    assert not (tmp_path / "o.jsonl").exists()


def test_flush_appends_entry(tmp_path, monkeypatch):
    """達 min_turns → 落一筆（session_id / unknown / total / ratio）。"""
    p = tmp_path / "o.jsonl"
    monkeypatch.setattr(wg_evasion, "OUTCOME_STATS_PATH", p)
    state = {"outcome_stats": {"success": 2, "fail": 1, "unknown": 1}}
    assert flush_outcome_stats(state, _cfg(), "s1") is None  # 單筆不足 window
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["session_id"] == "s1"
    assert rows[0]["total"] == 4 and rows[0]["unknown"] == 1
    assert abs(rows[0]["ratio"] - 0.25) < 1e-9


def test_flush_streak_returns_advisory(tmp_path, monkeypatch):
    """連續 3 session 高 unknown → 第 3 筆 flush 回 advisory 字串。"""
    p = tmp_path / "o.jsonl"
    monkeypatch.setattr(wg_evasion, "OUTCOME_STATS_PATH", p)
    high = {"outcome_stats": {"success": 1, "fail": 0, "unknown": 9}}  # 0.9
    assert flush_outcome_stats(dict(high), _cfg(), "s1") is None
    assert flush_outcome_stats(dict(high), _cfg(), "s2") is None
    msg = flush_outcome_stats(dict(high), _cfg(), "s3")
    assert msg and "[Guardian:OutcomeWatch]" in msg
    assert "unknown" in msg


def test_flush_low_ratio_no_advisory(tmp_path, monkeypatch):
    """比率低於門檻 → 連跑三次也不告警。"""
    p = tmp_path / "o.jsonl"
    monkeypatch.setattr(wg_evasion, "OUTCOME_STATS_PATH", p)
    low = {"outcome_stats": {"success": 8, "fail": 1, "unknown": 1}}  # 0.1
    for sid in ("s1", "s2", "s3"):
        assert flush_outcome_stats(dict(low), _cfg(), sid) is None


def test_flush_rolling_cap_50(tmp_path, monkeypatch):
    """滾動保留最近 50 筆。"""
    p = tmp_path / "o.jsonl"
    monkeypatch.setattr(wg_evasion, "OUTCOME_STATS_PATH", p)
    low = {"outcome_stats": {"success": 9, "fail": 0, "unknown": 1}}
    for i in range(55):
        flush_outcome_stats(dict(low), _cfg(), f"s{i}")
    rows = p.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 50
    assert json.loads(rows[-1])["session_id"] == "s54"


def test_flush_disabled(tmp_path, monkeypatch):
    """enabled=false 一鍵關 → 不落檔。"""
    p = tmp_path / "o.jsonl"
    monkeypatch.setattr(wg_evasion, "OUTCOME_STATS_PATH", p)
    state = {"outcome_stats": {"success": 0, "fail": 0, "unknown": 5}}
    assert flush_outcome_stats(state, _cfg(enabled=False), "s1") is None
    assert not p.exists()

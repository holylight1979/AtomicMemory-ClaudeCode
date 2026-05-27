#!/usr/bin/env python3
"""
test_session_evaluator.py — V4.1 P4 Session 評價機制 5 單元測試

無 LLM 呼叫，純 mock state + worker_stats，驗證：
  1. 高分 session（高 conf + 高 confirm 率）→ weighted ≥ 0.75
  2. 中分 session → weighted 落在 0.45-0.75
  3. 低分 session（稀疏 + 0 confirmed）→ weighted ≤ 0.55
  4. 無萃取 session（worker_stats=None）→ precision=1.0, density=0
  5. FIFO cap 100 → 最舊被擠掉
"""

import json
import sys
from pathlib import Path

import pytest

_HOOKS_DIR = Path.home() / ".claude" / "hooks"
sys.path.insert(0, str(_HOOKS_DIR))

import wg_session_evaluator as sev  # noqa: E402


# ─── Fixture: redirect reflection_metrics.json to a tmp file ─────────────────

@pytest.fixture(autouse=True)
def _tmp_reflection(tmp_path, monkeypatch):
    tmp_metrics = tmp_path / "reflection_metrics.json"
    monkeypatch.setattr(sev, "REFLECTION_METRICS_PATH", tmp_metrics)
    yield tmp_metrics


# ─── 1. High-score session ────────────────────────────────────────────────────

def test_high_score_session(_tmp_reflection):
    state = {"topic_tracker": {"prompt_count": 20}}
    worker_stats = {
        "processed": 10,
        "confirmed": 8,
        "dedup_hit": 0,
        "avg_l2_conf": 0.95,
        "token_used": 120,
        "l2_ran": True,
    }
    entry = sev.evaluate_session("sess-high", state, {}, worker_stats)
    s = entry["scores"]
    assert s["weighted_total"] >= 0.75, f"expected ≥ 0.75, got {s['weighted_total']}"
    assert s["precision_proxy"] == 0.95
    assert s["density"] > 0.4
    assert s["novelty"] == 1.0
    assert s["cost_efficiency"] == 0.5


# ─── 2. Medium-score session ──────────────────────────────────────────────────

def test_medium_score_session(_tmp_reflection):
    state = {"topic_tracker": {"prompt_count": 30}}
    worker_stats = {
        "processed": 5,
        "confirmed": 3,
        "dedup_hit": 1,
        "avg_l2_conf": 0.80,
        "token_used": 180,
        "l2_ran": True,
    }
    entry = sev.evaluate_session("sess-mid", state, {}, worker_stats)
    s = entry["scores"]
    assert 0.45 <= s["weighted_total"] <= 0.75, (
        f"expected 0.45-0.75, got {s['weighted_total']}"
    )
    assert s["precision_proxy"] == 0.80
    assert s["novelty"] == 0.75  # 3 / (3 + 1)


# ─── 3. Low-score session ─────────────────────────────────────────────────────

def test_low_score_session(_tmp_reflection):
    state = {"topic_tracker": {"prompt_count": 50}}
    worker_stats = {
        "processed": 1,
        "confirmed": 0,
        "dedup_hit": 0,
        "avg_l2_conf": 0.50,
        "token_used": 235,
        "l2_ran": True,
    }
    entry = sev.evaluate_session("sess-low", state, {}, worker_stats)
    s = entry["scores"]
    assert s["weighted_total"] <= 0.55, f"expected ≤ 0.55, got {s['weighted_total']}"
    assert s["precision_proxy"] == 0.50
    assert s["density"] < 0.1


# ─── 4. No-extraction session (worker_stats=None) ────────────────────────────

def test_no_extraction_session(_tmp_reflection):
    state = {"topic_tracker": {"prompt_count": 15}, "pending_user_extract": []}
    entry = sev.evaluate_session("sess-none", state, {}, worker_stats=None)
    s = entry["scores"]
    # No L2 run → precision_proxy defaults to 1.0 (don't penalize idle sessions)
    assert s["precision_proxy"] == 1.0
    assert s["density"] == 0.0
    assert s["trust"] == 1.0
    assert s["novelty"] == 1.0
    assert entry["extract_triggered"] == 0
    assert entry["extract_written"] == 0


# ─── 5. FIFO cap 100 ──────────────────────────────────────────────────────────

def test_fifo_cap_100(_tmp_reflection):
    state = {"topic_tracker": {"prompt_count": 10}}
    stats = {
        "processed": 1, "confirmed": 1, "dedup_hit": 0,
        "avg_l2_conf": 0.9, "token_used": 100, "l2_ran": True,
    }
    for i in range(105):
        sev.evaluate_session(f"sess-{i:03d}", state, {}, stats)

    data = json.loads(_tmp_reflection.read_text(encoding="utf-8"))
    scores = data["v41_extraction"]["session_scores"]
    assert len(scores) == 100, f"expected 100, got {len(scores)}"
    # Oldest (sess-000 ... sess-004) should be evicted; newest (sess-104) kept
    ids = [s["session_id"] for s in scores]
    assert "sess-000" not in ids
    assert "sess-004" not in ids
    assert "sess-005" in ids  # first kept
    assert "sess-104" in ids  # last

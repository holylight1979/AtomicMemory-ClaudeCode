"""verify_failing_tests_turn_scope.py — outcome 歸因只認本 turn 的 failing_tests。

stop._detect_turn_outcome 過去取全量累積 failing_tests——早前 turn 的舊失敗（未被
成功測試清掉）會把後續每個 turn 的 outcome 都判 fail，污染 (α,β) 歸因。修正後：
  - entry.turn_seq == state.turn_seq 才算本 turn fail 訊號
  - 舊 turn 失敗 + 本 turn 宣告完成 → True（不再被污染）
  - 無 turn_seq 的 legacy entry 保守視為本 turn（fail-open）
  - TestFailGate / sync gate 等其他消費者維持全量語意（此處不驗、不變更）
"""
from __future__ import annotations

import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

from handlers.stop import _detect_turn_outcome  # noqa: E402


def test_current_turn_failure_is_fail():
    state = {
        "turn_seq": 5,
        "failing_tests": [{"cmd": "pytest", "turn_seq": 5}],
    }
    assert _detect_turn_outcome(state, "完成") is False


def test_stale_turn_failure_does_not_pollute():
    """舊 turn 的失敗 + 本 turn 宣告完成 → success（跨 turn 污染修復核心）。"""
    state = {
        "turn_seq": 5,
        "failing_tests": [{"cmd": "pytest", "turn_seq": 3}],
    }
    assert _detect_turn_outcome(state, "完成") is True


def test_stale_failure_without_completion_is_unknown():
    state = {
        "turn_seq": 5,
        "failing_tests": [{"cmd": "pytest", "turn_seq": 3}],
    }
    assert _detect_turn_outcome(state, "繼續調查中") is None


def test_legacy_entry_without_turn_seq_treated_as_current():
    """升級前 in-flight session 的 entry 無 turn_seq → 保守視為本 turn（不漏 fail）。"""
    state = {"turn_seq": 5, "failing_tests": [{"cmd": "pytest"}]}
    assert _detect_turn_outcome(state, "完成") is False


def test_no_failures_completion_is_success():
    state = {"turn_seq": 5, "failing_tests": []}
    assert _detect_turn_outcome(state, "完成") is True

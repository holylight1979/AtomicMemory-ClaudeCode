"""verify_deep_postmortem_gate.py — Stage 3：Deep Post-Mortem Gate。

驗證 handlers/stop.py 的高 effort 失敗 → Claude 深寫指令閘：
  純判定 _should_deep_postmortem：
    - 首次擋：retry>=2 / fix_escalation_triggered 任一（AND real_failure）→ True
    - same_file_3x（同檔 edit>=3）不是 effort 訊號，單獨不觸發（edit 次數 ≠ 失敗）
    - 設旗標後放行：deep_postmortem_done=True → False
    - 無 effort 訊號 → False
    - block 預算耗盡（stop_count>=max_blocks）→ False
    - config enabled=false → False
  端到端 handle_stop：
    - 首次（有 effort 訊號）→ 設 deep_postmortem_done、emit DeepPostMortem block
    - 旗標已設 → 本 gate 不再觸發（放行，輸出不含 DeepPostMortem）

對應修補：handlers/stop.py _should_deep_postmortem / handle_stop Deep Post-Mortem
Gate + config.json deep_postmortem.enabled（補「失敗深層脈絡無人補寫」缺口）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify/ → hooks/
sys.path.insert(0, str(HOOKS_DIR))

from handlers import stop as st  # noqa: E402


# ─── 純判定 _should_deep_postmortem ──────────────────────────────────

_CFG = {}  # 預設 enabled=True
_MAX = 2


def _judge(state, stop_count=0, max_blocks=_MAX, config=_CFG, claims_done=False):
    """預設 claims_done=False（＝未宣告完成 → real_failure 成立），讓「有 effort
    訊號」的測試維持原『觸發』語意；真失敗訊號的測試另以參數覆寫。"""
    return st._should_deep_postmortem(state, stop_count, max_blocks, config, claims_done)


# effort 訊號（搭配未宣告完成的真失敗訊號）→ 觸發

def test_retry_triggers():
    """wisdom_retry_count>=2 + 未宣告完成 → 首次擋。"""
    assert _judge({"wisdom_retry_count": 2}) is True


def test_fix_escalation_triggers():
    """fix_escalation_triggered + 未宣告完成 → 首次擋。"""
    assert _judge({"fix_escalation_triggered": True}) is True


def test_same_file_3x_alone_does_not_trigger():
    """same_file_3x 不是 effort 訊號——同檔 edit>=3 但無 retry/fix_esc → 不觸發
    （即使未宣告完成；edit 次數 ≠ 失敗）。"""
    assert _judge({"edit_counts": {"hooks/foo.py": 9}}) is False


def test_no_effort_signal_skips():
    """無任何 effort 訊號 → 不觸發（即使未宣告完成）。"""
    assert _judge({"wisdom_retry_count": 1, "edit_counts": {"a.py": 2}}) is False


def test_flag_set_blocks_repeat():
    """設旗標後放行：deep_postmortem_done=True → 即使有訊號也不再觸發。"""
    assert _judge({"wisdom_retry_count": 5, "deep_postmortem_done": True}) is False


def test_budget_exhausted_skips():
    """stop_count>=max_blocks → 尊重預算不超發。"""
    assert _judge({"wisdom_retry_count": 3}, stop_count=_MAX) is False


def test_disabled_skips():
    """config deep_postmortem.enabled=false → 完全不觸發。"""
    assert _judge({"wisdom_retry_count": 3}, config={"deep_postmortem": {"enabled": False}}) is False


# ─── AND 真失敗訊號（避免高 effort 成功誤觸）─────────────────────────

def test_effort_but_success_not_triggered():
    """關鍵：effort 訊號齊備但已宣告完成且無 failing_tests/evasion → 不觸發。
    retry 可代表失敗中反覆，但 real_failure 未成立即不觸。"""
    state = {"wisdom_retry_count": 5, "failing_tests": [], "evasion_flag": None}
    assert _judge(state, claims_done=True) is False


def test_effort_with_failing_tests_triggers_even_if_claims_done():
    """effort + failing_tests 非空 → 真失敗成立，縱使宣告完成仍觸發。"""
    state = {"wisdom_retry_count": 2, "failing_tests": [{"cmd": "pytest"}]}
    assert _judge(state, claims_done=True) is True


def test_effort_with_evasion_triggers_even_if_claims_done():
    """effort（fix_escalation）+ evasion_flag → 真失敗成立，縱使宣告完成仍觸發。"""
    state = {"fix_escalation_triggered": True, "evasion_flag": {"kind": "vague"}}
    assert _judge(state, claims_done=True) is True


def test_real_failure_without_effort_skips():
    """只有真失敗訊號、無 effort → 不觸發（effort AND real_failure，非 OR）。"""
    state = {"failing_tests": [{"cmd": "pytest"}]}
    assert _judge(state, claims_done=False) is False


# ─── 端到端 handle_stop ──────────────────────────────────────────────

@pytest.fixture
def driven(monkeypatch):
    """攔掉 handle_stop 的所有外部依賴，只保留 gate 控制流。

    回傳 drive(state, config) → (stdout_text, state)；遇 output_* 的 sys.exit
    以 SystemExit 接住。state 由 _ensure_state 回傳並就地 mutate（write_state no-op）。
    """
    monkeypatch.setattr(st, "_find_session_transcript", lambda *a, **k: None)
    monkeypatch.setattr(st, "get_last_assistant_text", lambda *a, **k: "")
    monkeypatch.setattr(st, "token_warn_payload", lambda *a, **k: "")
    monkeypatch.setattr(st, "detect_evasion", lambda *a, **k: None)
    monkeypatch.setattr(st, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(st, "_attribute_usefulness", lambda *a, **k: None)
    monkeypatch.setattr(st, "_maybe_spawn_per_turn_extraction", lambda *a, **k: None)
    monkeypatch.setattr(st, "_maybe_spawn_user_extract_worker", lambda *a, **k: None)

    def drive(state, config, capsys):
        monkeypatch.setattr(st, "_ensure_state", lambda *a, **k: state)
        with pytest.raises(SystemExit):
            st.handle_stop({"session_id": "sid", "cwd": ""}, config)
        out = capsys.readouterr().out
        return out, state

    return drive


def test_handle_stop_first_time_blocks_and_sets_flag(driven, capsys):
    """首次：有 effort 訊號 + 無修改檔 → emit DeepPostMortem、設 deep_postmortem_done。"""
    state = {"phase": "working", "wisdom_retry_count": 2,
             "modified_files": [], "failing_tests": []}
    out, state = driven(state, {}, capsys)
    assert "DeepPostMortem" in out
    assert '"decision": "block"' in out
    assert state.get("deep_postmortem_done") is True


def test_handle_stop_second_time_passes(driven, capsys):
    """旗標已設 → 本 gate 不再觸發，輸出不含 DeepPostMortem（放行至無事可做）。"""
    state = {"phase": "working", "wisdom_retry_count": 2,
             "deep_postmortem_done": True,
             "modified_files": [], "failing_tests": []}
    out, _ = driven(state, {}, capsys)
    assert "DeepPostMortem" not in out

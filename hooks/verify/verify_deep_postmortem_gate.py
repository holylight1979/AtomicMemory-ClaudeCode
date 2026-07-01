"""verify_deep_postmortem_gate.py — Stage 3：Deep Post-Mortem Gate。

驗證 handlers/stop.py 的高 effort 失敗 → Claude 深寫指令閘：
  純判定 _should_deep_postmortem：
    - 首次擋：retry>=2 / fix_escalation_triggered 任一（AND real_failure）→ True
    - same_file_3x（同檔 edit>=3）不是 effort 訊號，單獨不觸發（edit 次數 ≠ 失敗）
    - 設旗標後放行：deep_postmortem_done=True → False
    - 無 effort 訊號 → False
    - ★獨立預算：不再受 stop_gate_max_blocks 綁（曾共用會餓死），僅 one-shot 自限
    - config enabled=false → False
  端到端 handle_stop：
    - 首次（有 effort 訊號）→ 設 deep_postmortem_done、emit DeepPostMortem block
    - 旗標已設 → 本 gate 不再觸發（放行，輸出不含 DeepPostMortem）
    - ★回歸：Sync+TestFail 吃光 stop_gate_max_blocks(2) 後 DPM 仍觸發（獨立預算）

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


def _judge(state, config=_CFG, claims_done=False):
    """預設 claims_done=False（＝未宣告完成 → real_failure 成立），讓「有 effort
    訊號」的測試維持原『觸發』語意；真失敗訊號的測試另以參數覆寫。

    ★DPM 已改獨立預算，_should_deep_postmortem 不再收 stop_count/max_blocks；
    共用預算餓死的回歸改在端到端 test_dpm_not_starved_by_shared_budget 驗證。"""
    return st._should_deep_postmortem(state, config, claims_done)


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


# ─── 回歸：獨立預算，不被 Sync+TestFail 吃光預算而餓死 ──────────────────

def test_dpm_not_starved_by_shared_budget(monkeypatch, capsys):
    """★回歸：DPM 獨立預算。同一「反覆修不好」session 中前兩輪 Sync + TestFail
    先吃光 stop_gate_max_blocks(2)，第 3 輪 DPM 條件成立（retry>=2 + failing_tests）
    仍須觸發——曾因共用 stop_count 預算而永不觸發（餓死），現 one-shot 獨立預算修復。

    三輪同一 state（write_state no-op、就地 mutate 累積 stop_blocked_count）：
      turn1 未宣告完成 + 有未提交檔 → SyncReminder（0→1）
      turn2 宣告完成 + failing   → TestFailGate（1→2，吃光共用預算）
      turn3 未宣告完成 + 已提交   → 其它 gate 全不觸；DPM 該觸發（獨立預算）
    """
    monkeypatch.setattr(st, "_find_session_transcript", lambda *a, **k: "T")
    monkeypatch.setattr(st, "token_warn_payload", lambda *a, **k: "")
    monkeypatch.setattr(st, "detect_evasion", lambda *a, **k: None)
    monkeypatch.setattr(st, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(st, "_attribute_usefulness", lambda *a, **k: None)
    monkeypatch.setattr(st, "_maybe_spawn_per_turn_extraction", lambda *a, **k: None)
    monkeypatch.setattr(st, "_maybe_spawn_user_extract_worker", lambda *a, **k: None)

    state = {
        "phase": "working", "wisdom_retry_count": 3,
        "failing_tests": [{"cmd": "pytest", "summary": "boom"}],
        "modified_files": [{"path": "hooks/foo.py"}, {"path": "hooks/bar.py"}],
        "stop_blocked_count": 0, "recent_user_prompts": [],
    }
    monkeypatch.setattr(st, "_ensure_state", lambda *a, **k: state)

    def turn(last_text, uncommitted):
        monkeypatch.setattr(st, "get_last_assistant_text", lambda *a, **k: last_text)
        monkeypatch.setattr(st, "_detect_uncommitted_files",
                            lambda mf: list(uncommitted) or None)
        try:
            st.handle_stop({"session_id": "sid", "cwd": "x"},
                           {"stop_gate_max_blocks": 2})
        except SystemExit:
            pass
        return capsys.readouterr().out

    o1 = turn("還在調查中，尚未完成。", ["hooks/foo.py"])   # Sync (0->1)
    o2 = turn("任務完成，全部搞定。", ["hooks/foo.py"])      # TestFail (1->2)
    o3 = turn("還在調查中，尚未完成。", [])                  # DPM 該觸發

    assert "SyncReminder" in o1
    assert "TestFailGate" in o2
    assert state.get("stop_blocked_count", 0) >= 2   # 共用預算已被吃光
    assert "DeepPostMortem" in o3                     # 曾餓死 → 現獨立預算觸發
    assert state.get("deep_postmortem_done") is True

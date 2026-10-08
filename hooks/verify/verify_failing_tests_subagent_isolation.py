#!/usr/bin/env python3
"""verify_failing_tests_subagent_isolation.py — 子代理的紅測不進主 session failing_tests。

怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_failing_tests_subagent_isolation.py
背景：sub-agent 跑 run_verify 遇 2 筆紅測 → 主 session 的 Stop 被 TestFailGate 擋（2026-09-21 實踩）。
hook 輸入在子代理內會帶 agent_id／agent_type（官方 hooks 文件「Common input fields」）。
"""
from __future__ import annotations

import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS_DIR))

from handlers.post_tool_use import _track_test_result  # noqa: E402

_RED = {"stdout": "FAILED tests/x.py::t - assert 1 == 2\n1 failed, 3 passed in 0.5s\n",
        "stderr": "", "interrupted": False}
_GREEN = {"stdout": "4 passed in 0.4s\n", "stderr": "", "interrupted": False}
_CMD = "python -m pytest -q tests/x.py"


def _ev(resp, agent_id=""):
    ev = {"tool_name": "Bash", "tool_input": {"command": _CMD}, "tool_response": resp}
    if agent_id:
        ev["agent_id"] = agent_id
        ev["agent_type"] = "general-purpose"
    return ev


def test_main_thread_red_recorded():
    st = {"turn_seq": 7}
    assert _track_test_result(st, _ev(_RED), _CMD) is True
    assert len(st["failing_tests"]) == 1 and st["failing_tests"][0]["turn_seq"] == 7


def test_subagent_red_not_recorded():
    st = {"turn_seq": 7}
    assert _track_test_result(st, _ev(_RED, agent_id="a1"), _CMD) is False
    assert "failing_tests" not in st


def test_subagent_green_does_not_clear_main_entries():
    st = {"turn_seq": 7}
    _track_test_result(st, _ev(_RED), _CMD)
    assert _track_test_result(st, _ev(_GREEN, agent_id="a1"), _CMD) is False
    assert len(st["failing_tests"]) == 1


def test_main_green_clears():
    st = {"turn_seq": 7}
    _track_test_result(st, _ev(_RED), _CMD)
    assert _track_test_result(st, _ev(_GREEN), _CMD) is True
    assert st["failing_tests"] == []


def test_non_test_command_untouched():
    st = {"turn_seq": 7}
    assert _track_test_result(st, {"tool_response": _RED}, "git status") is False


def test_powershell_red_recorded_with_tool_and_exit_code():
    """B4：PowerShell 也記；tool 欄＝PowerShell；exit code 從實機字串 "Error: Exit code 1" 抓。"""
    st = {"turn_seq": 7}
    ev = {"tool_name": "PowerShell", "tool_input": {"command": _CMD},
          "tool_response": "Error: Exit code 1\n" + _RED["stdout"]}
    assert _track_test_result(st, ev, _CMD, "PowerShell") is True
    rec = st["failing_tests"][0]
    assert rec["tool"] == "PowerShell" and rec["exit_code"] == 1 and rec["turn_seq"] == 7


def test_dict_response_without_exit_field_records_none():
    """實機成功回應是 dict 無 exit 欄 → exit_code=None（不當零也不當非零）。"""
    st = {"turn_seq": 7}
    _track_test_result(st, _ev(_RED), _CMD)
    assert st["failing_tests"][0]["exit_code"] is None and st["failing_tests"][0]["tool"] == "Bash"

# ─── BLOCK 1：條目蓋 session_id；清帳只清自己的 ──────────────────────────────

def _ev_sid(resp, sid):
    ev = _ev(resp)
    ev["session_id"] = sid
    return ev


def test_failing_tests_isolated_between_sibling_sessions_clearing():
    """A 紅、B 綠（同指令）不清 A；A 綠才清 A。沒蓋 sid 的舊條目誰都不清。"""
    st = {"turn_seq": 7, "failing_tests": [{"cmd": _CMD, "pytest": True, "summary": "legacy"}]}
    assert _track_test_result(st, _ev_sid(_RED, "A"), _CMD) is True
    assert st["failing_tests"][-1]["session_id"] == "A"
    assert _track_test_result(st, _ev_sid(_GREEN, "B"), _CMD) is False
    assert [f.get("session_id") for f in st["failing_tests"]] == [None, "A"]
    assert _track_test_result(st, _ev_sid(_GREEN, "A"), _CMD) is True
    assert [f.get("session_id") for f in st["failing_tests"]] == [None]


# ─── BLOCK 6：非零 exit 一律建紅測、且不清帳 ──────────────────────────────────

def test_nonzero_exit_creates_failing_entry():
    """輸出沒有失敗樣式（甚至印 PASS）但 exit 1 → 仍建紅測。"""
    st = {"turn_seq": 7}
    assert _track_test_result(st, _ev_sid("Error: Exit code 1\nALL_CHECK PASS\n", "A"), _CMD) is True
    e = st["failing_tests"][0]
    assert e["exit_code"] == 1 and "ALL_CHECK PASS" in e["summary"]
    st2 = {"turn_seq": 7}
    assert _track_test_result(st2, _ev_sid({"stdout": "4 passed\n", "stderr": "", "exit_code": 2}, "A"), _CMD) is True


def test_nonzero_exit_never_clears():
    st = {"turn_seq": 7}
    _track_test_result(st, _ev_sid(_RED, "A"), _CMD)
    assert _track_test_result(st, _ev_sid({"stdout": "4 passed in 0.4s\n", "stderr": "", "exit_code": 1}, "A"), _CMD) is True
    assert len(st["failing_tests"]) == 2        # 非零 exit 又記一筆，原本的也還在
    assert _track_test_result(st, _ev_sid({"stdout": "4 passed in 0.4s\n", "stderr": "", "exit_code": 0}, "A"), _CMD) is True
    assert st["failing_tests"] == []

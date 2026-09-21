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

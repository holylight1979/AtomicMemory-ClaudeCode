#!/usr/bin/env python3
"""verify_testfail_clear_replay.py — 紅測閘：綠了的要清掉、擋訊息要指對地方（重放 2026-10-27 的實帳）。

怎麼跑：python -X utf8 -m pytest -q -p no:cacheprovider hooks/verify/verify_testfail_clear_replay.py
背景：一次 pytest 點名 13 支檔跑出 20 個 FAILED；之後跑 3 支檔綠（清掉 4 支、記進 cleared_units）、再單跑 1 支綠（0 支新清）。
之後每次 Stop 的擋訊息仍寫「測試未綠（1 項失敗）」、把已經綠的 verify_locate_hint.py::… 列成失敗項（v6 關時走
pre_v6_testfail_message：印摘要第一行，不看 cleared_units），AI 被帶去重跑同一支兩次、最後重跑整個 13 支範圍。
規則：GREEN_CLEARS_ONLY_CASES_IT_RAN（綠點名整檔＝那檔的紅案全跑到，路徑分隔與大小寫不同也認得）、
RED_ITEMS_ONLY_FROM_FAILURE_LINES（擋訊息只列還沒跑綠的那幾支、算支數不算筆數、附重跑哪幾支檔就夠）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS_DIR))

import wg_release_rules as rr  # noqa: E402
from handlers import post_tool_use as ptu  # noqa: E402
from handlers import stop as st  # noqa: E402

_SID = "050c2387-replay"
_CWD = "C:/Users/holylight/.claude"
_FILES = ["verify_card_injection_slim", "verify_overview_hub", "verify_locate_hint", "verify_tracking_readback",
          "verify_overview_card_pointer", "verify_gate_mode_pre", "verify_candidates_trigger", "verify_goal_weighted_inject",
          "verify_need_goal_points", "verify_pre_tool_use_overview_gate", "verify_pull_goal_locate", "verify_cost_cut",
          "verify_scorecard"]
_RED_CMD = (f"cd {_CWD}\npython -X utf8 -m pytest -q -p no:cacheprovider "
            + " ".join(f"hooks/verify/{f}.py" for f in _FILES) + " 2>&1")
_LOCATE = "hooks/verify/verify_locate_hint.py::test_locate_hint_on_first_read_of_part_code_file_then_follow_it_no_block"
# 20 支紅：card_injection_slim 1、locate_hint 2、gate_mode_pre 1（這 4 支給第一次綠清）、其餘 10 檔各 1～2 支
_RED_UNITS = ["hooks/verify/verify_card_injection_slim.py::test_v6_off_uses_pointer_mode_not_full",
              _LOCATE, "hooks/verify/verify_locate_hint.py::test_locate_hint_ignored_not_blocked_and_not_reminded_twice",
              "hooks/verify/verify_gate_mode_pre.py::test_pre_gate_mode"]
for _f in _FILES[1:2] + _FILES[3:5] + _FILES[6:]:
    _RED_UNITS.append(f"hooks/verify/{_f}.py::test_a_{_f}")
_RED_UNITS += [f"hooks/verify/{_f}.py::test_b_{_f}" for _f in ("verify_overview_hub", "verify_tracking_readback",
                                                                "verify_overview_card_pointer", "verify_candidates_trigger",
                                                                "verify_cost_cut", "verify_scorecard")]
assert len(_RED_UNITS) == 20
_RED_OUT = "".join(f"FAILED {u} - AssertionError\n" for u in _RED_UNITS) + "20 failed, 311 passed in 41.2s\n"
_GREEN3_CMD = (f"cd {_CWD}\npython -X utf8 -m pytest -q -p no:cacheprovider hooks/verify/verify_locate_hint.py "
               "hooks/verify/verify_card_injection_slim.py hooks/verify/verify_gate_mode_pre.py 2>&1")
_GREEN1_CMD = f"cd {_CWD}\npython -X utf8 -m pytest -q -p no:cacheprovider hooks/verify/verify_locate_hint.py"
_DONE = "全部完成了，測試都跑過。"


def _ev(cmd, stdout, exit_code):
    return {"tool_name": "Bash", "session_id": _SID, "cwd": _CWD, "tool_input": {"command": cmd},
            "tool_response": {"stdout": stdout, "stderr": "", "interrupted": False, "exit_code": exit_code}}


@pytest.fixture
def quiet(monkeypatch):
    monkeypatch.setattr(ptu, "append_guard_log", lambda *a, **k: None)
    monkeypatch.setattr(ptu, "_negative_control", lambda *a, **k: rr.Verdict("NEGATIVE_CONTROL_DECLARED", True, "沒宣告", ()))
    monkeypatch.delenv("WG_V6", raising=False)


def _roundtrip(state):
    """模擬 write_state → 下一支 hook 再讀：state 經 JSON 落地再載回。"""
    return json.loads(json.dumps(state, ensure_ascii=False))


def _replay(state=None):
    """1 紅（13 支檔 20 FAILED）→ 2 綠（3 支檔）→ 3 綠（1 支檔）；每步之間 state 落地再讀。回 (state, 那筆紅)。
    紅的摘要（wg_evasion.failure_summary）要留住全部 20 支 FAILED：舊寫法只取尾 20 行，第一支（card_injection_slim）被切掉、
    永遠不在帳上（實帳因此記成「4 支＋15 支」）。20 支在帳：4 支給綠清、16 支還紅。"""
    state = state if state is not None else {"turn_seq": 33, "session": {"id": _SID}}
    assert ptu._track_test_result(state, _ev(_RED_CMD, _RED_OUT, 1), _RED_CMD) is True
    state = _roundtrip(state)
    assert ptu._track_test_result(state, _ev(_GREEN3_CMD, "45 passed in 3.1s\n", 0), _GREEN3_CMD) is True, "4 支清掉要寫回 state"
    state = _roundtrip(state)
    ptu._track_test_result(state, _ev(_GREEN1_CMD, "12 passed in 1.0s\n", 0), _GREEN1_CMD)
    state = _roundtrip(state)
    reds = [f for f in state["failing_tests"] if f["session_id"] == _SID]
    assert len(reds) == 1
    return state, reds[0]


def test_replay_13_files_red_then_3_green_then_1_green_label_lists_only_remaining(quiet):
    _, red = _replay()
    assert set(red["cleared_units"]) == set(_RED_UNITS[:4])
    assert rr.red_units(red) == _RED_UNITS[4:]
    for msg in (st.testfail_message([red]), st.pre_v6_testfail_message([red])):
        assert "verify_locate_hint" not in msg, msg
        assert "verify_card_injection_slim" not in msg and "verify_gate_mode_pre" not in msg, msg
        assert f"{_RED_UNITS[4]}、{_RED_UNITS[5]}、{_RED_UNITS[6]} 等 16 支" in msg, msg


def test_cleared_units_persist_across_post_tool_use_and_stop(quiet, monkeypatch, capsys):
    """v6 關（實帳當時的設定）：Stop 走 pre_v6 的紅測擋訊息，也要看 cleared_units；開也一樣。"""
    state, _ = _replay()
    state.update({"phase": "done", "modified_files": [], "recent_user_prompts": [], "stop_blocked_count": 0})
    for name, val in {
        "_find_session_transcript": lambda *a, **k: None, "token_warn_payload": lambda *a, **k: "",
        "detect_evasion": lambda *a, **k: None, "write_state": lambda *a, **k: None,
        "append_guard_log": lambda *a, **k: None, "_attribute_usefulness": lambda *a, **k: None,
        "_detect_uncommitted_files": lambda mf: [], "_git_unpushed_roots": lambda mf: [],
        "_should_deep_postmortem": lambda *a, **k: False, "_maybe_spawn_user_extract_worker": lambda *a, **k: None,
        "_hud_alive": lambda *a, **k: (True, {}), "get_last_assistant_text": lambda *a, **k: _DONE,
        "_code_check_text": lambda *a, **k: _DONE, "read_transcript_tail": lambda *a, **k: "",
        "harvest_gate_reason": lambda *a, **k: None, "pending_gate_reason": lambda *a, **k: None,
    }.items():
        monkeypatch.setattr(st, name, val)
    for on in (False, True):
        monkeypatch.setenv("WG_V6", "1" if on else "0")
        monkeypatch.setattr(st, "_ensure_state", lambda *a, **k: _roundtrip(state))
        with pytest.raises(SystemExit):
            st.handle_stop({"session_id": _SID, "cwd": ""}, {"harvest": {"background": True}})
        out = capsys.readouterr().out
        assert "[Guardian:TestFailGate]" in out, out
        assert "verify_locate_hint" not in out and "1 項失敗" not in out, out
        assert "還有 16 支沒跑綠（4 支已綠）" in out, out


@pytest.mark.parametrize("green_cmd", [
    "python -m pytest Hooks\\Verify\\Verify_Locate_Hint.py -q",                       # 反斜線＋大小寫
    f"cd {_CWD} && python -X utf8 -m pytest -q C:\\Users\\holylight\\.claude\\hooks\\verify\\verify_locate_hint.py",   # 絕對路徑
    "python -m pytest ./hooks/verify/verify_locate_hint.py",                           # ./ 前綴
], ids=["backslash-case", "absolute", "dot-slash"])
def test_green_whole_file_clears_all_its_red_cases_regardless_of_slash_style(green_cmd):
    red_sum = ("FAILED hooks\\verify\\verify_locate_hint.py::test_a\nFAILED hooks\\verify\\verify_locate_hint.py::test_b\n"
               "FAILED hooks/verify/verify_overview_hub.py::test_c\n3 failed, 9 passed in 1s\n")
    v, ran = rr.green_ran_cases_verdict(_RED_CMD, red_sum, green_cmd)
    assert v.owed and sorted(ran) == ["hooks/verify/verify_locate_hint.py::test_a", "hooks/verify/verify_locate_hint.py::test_b"], (v, ran)
    entry = {"summary": red_sum, "cleared_units": ran}
    assert rr.red_units(entry) == ["hooks/verify/verify_overview_hub.py::test_c"]


def test_message_counts_remaining_units_not_entries(quiet):
    _, red = _replay()
    msg = st.testfail_message([red])
    assert msg.startswith("[Guardian:TestFailGate] 測試未綠：還有 16 支沒跑綠（4 支已綠），不得宣告完成。"), msg
    assert "項失敗" not in msg
    files = [f"hooks/verify/{f}.py" for f in _FILES if f not in ("verify_card_injection_slim", "verify_locate_hint", "verify_gate_mode_pre")]
    assert "重跑這幾支檔就夠：" + "、".join(files) in msg, msg
    # 沒逐支列出的紅：整筆算 1 支、照舊附「重跑這個範圍」
    plain = {"cmd": "python -m pytest tests -q | tail -1", "summary": "1 failed, 3 passed", "session_id": _SID,
             "test_scope": {"steps": ["python -m pytest tests -q"]}}
    msg2 = st.testfail_message([red, plain])
    assert "還有 17 支沒跑綠（4 支已綠）" in msg2 and "重跑這個範圍" in msg2 and "輸出沒列出" in msg2, msg2
    solo = st.pre_v6_testfail_message([plain])
    assert solo.count("還有 1 支沒跑綠，不得宣告完成") == 1 and "支已綠" not in solo, solo     # 一支都沒綠過：不附「（0 支已綠）」


def test_summary_keeps_all_failed_lines_beyond_20():
    """20 支 FAILED＋結算行：摘要留住全部 20 支與結算行；超過 200 支只記前 200、尾端標清單不完整，red_case_facts 判不完整。"""
    import wg_evasion as ev
    summ = ev.detect_test_failure(_RED_OUT, "", False)
    assert rr.failed_units(summ) == _RED_UNITS and "20 failed, 311 passed" in summ, summ
    assert rr.red_case_facts(summ) == (_RED_UNITS, True)
    many = [f"tests/test_many.py::test_{i:03d}" for i in range(250)]
    summ = ev.detect_test_failure("".join(f"FAILED {u} - boom\n" for u in many) + "250 failed in 9s\n", "", False)
    assert rr.failed_units(summ) == many[:200] and "250 failed" in summ and "清單不完整" in summ.splitlines()[-1], summ[-300:]
    assert rr.red_case_facts(summ)[1] is False


def test_green_covering_all_remaining_files_clears_entry(quiet):
    state, red = _replay()
    files = dict.fromkeys(u.split("::", 1)[0] for u in rr.red_units(red))
    cmd = f"cd {_CWD}\npython -X utf8 -m pytest -q -p no:cacheprovider " + " ".join(files) + " 2>&1"
    assert ptu._track_test_result(state, _ev(cmd, "200 passed in 20s\n", 0), cmd) is True
    assert [f for f in state["failing_tests"] if f["session_id"] == _SID] == []


if __name__ == "__main__":
    code = pytest.main(["-q", "-p", "no:cacheprovider", __file__])
    print(f"TESTFAIL_CLEAR_REPLAY_CHECK {'PASS' if code == 0 else 'FAIL'}")
    sys.exit(0 if code == 0 else 1)

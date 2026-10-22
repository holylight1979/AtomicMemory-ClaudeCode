"""verify_red_scope_full_command.py：紅測的範圍從整條指令取（規則 RED_SCOPE_FROM_FULL_COMMAND；handlers/post_tool_use 記帳清帳、
handlers/stop 擋訊息）。

做什麼：重演一則實際的多行 Bash（範圍內測試｜tail -3、完整套件｜tail -6、幾次 cli 實跑）——輸出最後 20 行只剩 cli，
紅測摘要看不出是哪一支；cmd 只存前 200 字，剛好截在 `pytest tests -q 2>&1` 的 `2`，舊碼把 `2` 當成要跑的目錄，什麼重跑都涵蓋不到。
現在記的是解析後的目標（test_scope：每段測試子命令與換目錄），跟指令多長無關、不截斷；解析不出就判不出、不拿片段當路徑。
驗：照擋訊息重跑、涵蓋那則的範圍而且綠 → 舊紅清掉；完整套件重跑、紅而且逐支列出 → 舊紅改記那幾支（ERP 那支列得出名字，
「不做｜」才對得到）；反例：重跑沒涵蓋（只跑第一段）或還是紅 → 照留，沒涵蓋的留帳 testfail_scope；擋訊息對看不出是哪一支的紅
列出解析出的每段測試子命令（照抄重跑），看得出的不加；長指令照樣清得掉；判不出目標給「原指令完整照跑或跑整套」並留帳。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_red_scope_full_command.py
       python -X utf8 hooks/verify/verify_red_scope_full_command.py   （直接跑，尾行 RED_SCOPE_CHECK PASS／FAIL）
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import wg_release_rules as rr  # noqa: E402
from handlers import post_tool_use as ptu  # noqa: E402
from handlers import stop as st  # noqa: E402

SID = "sid-red-scope"
ERP = "tests/test_erp_contract.py::test_checkout_fields_match_erp_contract"
SCOPED = "python -m pytest tests/test_checkout.py tests/test_pricing.py tests/test_receipt.py tests/test_cli.py -q"
# 實際那則（前兩行照帳上的 cmd 原字；cli 實跑的幾行照輸出補）
GATE0_CMD = (f'echo "== 範圍內測試" && {SCOPED} 2>&1 | tail -3\n'
             'echo "== 完整套件（預期只有 ERP 合約那支紅）" && python -m pytest tests -q 2>&1 | tail -6\n'
             'echo "== 實跑 cli 帶 VIP10" && python -m orders.cli \'[{"price": 500, "qty": 1}]\' --code VIP10; echo "exit=$?"\n'
             'echo "== 實跑 cli 壞 JSON" && python -m orders.cli \'not json\'; echo "exit=$?"\n')
CLI_TAIL = "\n".join(f"小計 {n} TWD\n運費 80 TWD\nexit=0" for n in range(8)) + "\nusage: python -m orders.cli\nexit=2\n"
GATE0_OUT = (f"== 範圍內測試\n16 passed in 0.12s\n== 完整套件（預期只有 ERP 合約那支紅）\nFAILED {ERP} - ...\n"
             f"1 failed, 16 passed in 0.16s\n{CLI_TAIL}")


@pytest.fixture()
def logs(monkeypatch):
    got = []
    monkeypatch.setattr(ptu, "append_guard_log", lambda guard, payload: got.append((guard, payload)))
    return got


def _track(state, cmd, out):
    """跑一次測試指令的 PostToolUse 記帳／清帳（輸出照 Bash 工具的 dict 回應）。"""
    ptu._track_test_result(state, {"session_id": SID, "cwd": "C:/w4/qc2-orders",
                                   "tool_response": {"stdout": out, "stderr": "", "interrupted": False}}, cmd, "Bash", {})


def _gate0_red():
    state = {"failing_tests": [], "session": {"id": SID}, "turn_seq": 2}
    _track(state, GATE0_CMD, GATE0_OUT)
    (red,) = state["failing_tests"]
    assert red["cmd"].endswith("pytest tests -q 2") and not rr.red_units(red)     # 前置：cmd 截在 `2`、看不出是哪一支
    return state


def test_rerun_covering_scope_green_clears_red(logs):
    """紅案例（RED_SCOPE_FROM_FULL_COMMAND）：照擋訊息把那則的測試範圍重跑一遍（兩段都跑、不截輸出）而且綠 → 舊紅清掉、不再擋；
    只跑完整套件（目錄涵蓋第一段的四支檔）也一樣。改前 `2` 被當成目錄，兩種重跑都清不掉。"""
    state = _gate0_red()
    _track(state, f"{SCOPED}\npython -m pytest tests -q", "16 passed in 0.12s\n17 passed in 0.16s")
    assert state["failing_tests"] == []
    state = _gate0_red()
    _track(state, "python -m pytest tests -q", "17 passed in 0.16s")
    assert state["failing_tests"] == [] and not [g for g, _ in logs if g == "testfail_scope"]


def test_full_suite_rerun_red_listed_replaces_unknown_red():
    """紅案例（RED_SCOPE_FROM_FULL_COMMAND × GREEN_CLEARS_ONLY_CASES_IT_RAN 的紅那一面）：完整套件重跑仍紅、
    逐支列出（只有 ERP）→ 看不出是哪一支的舊紅改記成 ERP 那支；之後「不做｜」對得到它。改前舊紅照留，兩筆一起擋。"""
    state = _gate0_red()
    _track(state, "python -m pytest tests -q 2>&1 | tail -3",
           f"=========================== short test summary info ===========================\nFAILED {ERP} - ...\n"
           "1 failed, 16 passed in 0.16s")
    assert [rr.red_units(f) for f in state["failing_tests"]] == [[ERP]]


def test_rerun_not_covering_scope_keeps_red_and_logs(logs):
    """反例：只照第一段重跑（沒跑完整套件）而且綠 → 沒涵蓋，舊紅照留，留帳 testfail_scope（要重跑什麼、跑了什麼）。"""
    state = _gate0_red()
    _track(state, f'echo "== 範圍內測試" && {SCOPED} 2>&1', "16 passed in 0.12s")
    assert len(state["failing_tests"]) == 1
    (rec,) = [p for g, p in logs if g == "testfail_scope"]
    assert rec["event"] == "green_kept_red" and "python -m pytest tests -q 2>&1" in rec["red_scope"]["steps"]
    assert rec["rule"] == "GREEN_CLEARS_ONLY_CASES_IT_RAN"


def test_rerun_still_red_keeps_red():
    """反例：涵蓋範圍重跑但還是紅、輸出又沒列出是哪一支 → 照擋（記一筆新的紅，舊紅不被截過的輸出取代）。"""
    state = _gate0_red()
    _track(state, "python -m pytest tests -q 2>&1 | tail -1", "1 failed, 16 passed in 0.16s")
    assert len(state["failing_tests"]) == 2 and all(not rr.red_units(f) for f in state["failing_tests"])


def test_block_message_lists_full_scope_for_unknown_red():
    """RED_SCOPE_FROM_FULL_COMMAND 的出口：看不出是哪一支的紅，擋訊息列出解析出的每一段測試子命令（含 200 字之後的完整套件那段；
    不含 cli 實跑與接在後面的 tail），照抄就能重跑；看得出是哪一支的紅不加這一行。"""
    (red,) = _gate0_red()["failing_tests"]
    line = next(ln for ln in st.testfail_message([red]).splitlines() if "重跑這個範圍" in ln)
    assert f"{SCOPED} 2>&1 ； python -m pytest tests -q 2>&1；" in line and "tail -" not in line and "orders.cli" not in line
    named = {**red, "summary": f"FAILED {ERP} - x\n1 failed"}
    assert "重跑這個範圍" not in st.testfail_message([named])


_G0 = GATE0_CMD.split("\n", 2)        # 範圍內測試、完整套件、cli 實跑
LONG_TAIL = "\n".join(f"python -m pytest tests/test_m{k:03d}.py -q" for k in range(80))
LONG_CMD = f"{_G0[0]}\n{_G0[1]}\n{LONG_TAIL}\n{_G0[2]}"


def test_long_command_full_suite_green_clears():
    """紅案例（RED_SCOPE_FROM_FULL_COMMAND，長度無關）：超過 2000 字、前段有 `pytest tests -q 2>&1` 的多行指令紅了、輸出看不出是哪一支
    （cmd 照樣截在 `2`）→ 照擋訊息跑整套而且綠 → 清掉。記的是解析後的目標（每段測試子命令），不是原字串，沒有長度上限、不截斷；
    改前測試行超過 2000 字就退回截過的 cmd，`2` 又被當成目錄，整套重跑也清不掉。"""
    state = {"failing_tests": [], "session": {"id": SID}, "turn_seq": 2}
    _track(state, LONG_CMD, GATE0_OUT)
    (red,) = state["failing_tests"]
    assert len(LONG_CMD) > 2000 and red["cmd"].endswith("pytest tests -q 2") and len(red["test_scope"]["steps"]) == 82
    _track(state, "python -m pytest tests -q", "97 passed in 0.5s")
    assert state["failing_tests"] == []


def test_long_command_narrow_green_keeps_red_and_message_gives_general_path():
    """反例：同一條長指令紅了，只跑第一段綠 → 沒涵蓋，照留；範圍長過擋訊息能列的長度 → 不截一半給人照抄，改給通用出路。"""
    state = {"failing_tests": [], "session": {"id": SID}, "turn_seq": 2}
    _track(state, LONG_CMD, GATE0_OUT)
    _track(state, SCOPED, "16 passed in 0.12s")
    assert len(state["failing_tests"]) == 1
    msg = st.testfail_message(state["failing_tests"])
    assert "原指令完整照跑、別截斷輸出，或不點名檔跑整套" in msg and "重跑這個範圍" not in msg


def test_unparsed_target_never_uses_fragment_and_has_a_doable_path(logs):
    """RED_SCOPE_FROM_FULL_COMMAND 判不出目標（認不出測試子命令，例 npm test）：不拿指令片段當路徑，留帳 scope_unparsed，擋訊息給
    「原指令完整照跑或跑整套」；原樣重跑綠（空白不同也認）→ 清；換一條點名別的東西的綠 → 照留。"""
    def red():
        state = {"failing_tests": [], "session": {"id": SID}, "turn_seq": 2}
        _track(state, "npm test", "Tests: 1 failed, 9 passed")
        return state
    state = red()
    (f,) = state["failing_tests"]
    assert f["test_scope"]["unparsed"] and [p["event"] for g, p in logs if g == "testfail_scope"] == ["scope_unparsed"]
    assert "原指令完整照跑、別截斷輸出，或不點名檔跑整套" in st.testfail_message([f])
    _track(state, "npm test", "Tests: 10 passed")
    assert state["failing_tests"] == []
    state = red()
    _track(state, "npm  test", "Tests: 10 passed")
    assert state["failing_tests"] == []
    state = red()
    _track(state, "npm test -- tests/test_a.py", "Tests: 3 passed")
    assert len(state["failing_tests"]) == 1


def test_cut_legacy_red_is_unparsed_and_full_suite_clears():
    """RED_SCOPE_FROM_FULL_COMMAND 的舊條目：沒記 test_scope、cmd 剛好 200 字（可能被截過）→ 判不出，不拿片段當路徑：
    點名幾支檔的綠清不掉，跑整套（不點名檔）綠 → 清。"""
    cut = ("python -m pytest " + " ".join(f"tests/test_x{k:02d}.py" for k in range(20)) + " -q 2>&1")[:ptu.RED_CMD_KEPT]
    red = {"tool": "Bash", "session_id": SID, "cmd": cut, "pytest": True, "summary": "1 failed, 30 passed", "cwd": "C:/w4/qc2-orders"}
    state = {"failing_tests": [dict(red)], "session": {"id": SID}, "turn_seq": 2}
    _track(state, "python -m pytest tests/test_x00.py -q", "1 passed")
    assert len(state["failing_tests"]) == 1
    _track(state, "python -m pytest -q", "31 passed")
    assert state["failing_tests"] == []


def test_same_filtered_multiline_rerun_clears_both_sides_same_form():
    """反例：紅與這次的指令用同一種寫法比——多行指令裡 `pytest tests -k slow` 紅、輸出沒列案例，原樣重跑綠
    → 照「同一個篩選指令重跑」清掉。舊條目（沒記 test_scope）的 cmd 沒被截就當場解析，剛好 200 字的當判不出、不拿片段當路徑。"""
    state = {"failing_tests": [], "session": {"id": SID}, "turn_seq": 2}
    cmd = "echo setup\npython -m pytest tests -k slow"
    _track(state, cmd, "1 failed, 2 passed, 5 deselected in 0.1s")
    assert len(state["failing_tests"]) == 1
    _track(state, cmd, "3 passed, 5 deselected in 0.1s")
    assert state["failing_tests"] == []
    assert ptu._red_pair({"cmd": cmd}, cmd) == ("python -m pytest tests -k slow",) * 2
    cut = ("python -m pytest " + "tests/test_x.py " * 20)[:ptu.RED_CMD_KEPT]
    assert ptu._red_scope({"cmd": cut}) == {"unparsed": True, "sha": ""} and ptu._red_pair({"cmd": cut}, cmd)[0] == ""


def test_rerun_scope_keeps_cd_and_drops_piped_tail():
    """RED_SCOPE_FROM_FULL_COMMAND 的出口：換目錄是測試在哪裡跑的前提，要一起列出；接在後面的 tail 不列（照抄才不會又截掉輸出）。"""
    state = {"failing_tests": [], "session": {"id": SID}, "turn_seq": 2}
    tests = " ".join(f"tests/test_n{k:02d}.py" for k in range(10))
    _track(state, f"cd services/billing\necho go\npython -m pytest {tests} -q 2>&1 | tail -1", "1 failed, 40 passed")
    line = next(ln for ln in st.testfail_message(state["failing_tests"]).splitlines() if "重跑這個範圍" in ln)
    assert f"cd services/billing ； python -m pytest {tests} -q 2>&1；" in line and "echo go" not in line and "tail -" not in line


@pytest.mark.parametrize("cmd, want", [
    ("python -m pytest tests -q", {"steps": ["python -m pytest tests -q"]}),
    ("cd proj\npython -m pytest \\\n  tests/test_a.py -q\necho done", {"steps": ["cd proj", "python -m pytest tests/test_a.py -q"]}),
    ("python -m pytest tests -q; cd other", {"steps": ["python -m pytest tests -q"]}),            # 測試之後的換目錄不收
    ("cd a && npx jest src -t foo", {"steps": ["cd a", "npx jest src -t foo"]}),
    ("pytest a.py\npytest " + "b" * 3000, {"steps": ["pytest a.py", "pytest " + "b" * 3000]}),    # 沒有長度上限、不截斷
])
def test_test_scope_parses_targets(cmd, want):
    """RED_SCOPE_FROM_FULL_COMMAND 的事實：test_scope＝每一段測試子命令與它前面的換目錄（續行先併）；認不出測試子命令 → unparsed＋雜湊。"""
    assert ptu._test_scope(cmd) == want
    got = ptu._test_scope("echo hi\nnpm test")
    assert got["unparsed"] and got["sha"] == ptu._test_scope("echo hi\n npm   test")["sha"]


if __name__ == "__main__":
    import subprocess
    rc = subprocess.run([sys.executable, "-X", "utf8", "-m", "pytest", __file__, "-q", "-p", "no:cacheprovider"]).returncode
    print("RED_SCOPE_CHECK PASS" if rc == 0 else "RED_SCOPE_CHECK FAIL")
    sys.exit(0 if rc == 0 else 1)

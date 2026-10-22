"""verify_red_scope_full_command.py：紅測的範圍從整條指令取（規則 RED_SCOPE_FROM_FULL_COMMAND；handlers/post_tool_use 記帳清帳、
handlers/stop 擋訊息）。

做什麼：重演第 0 步總驗收第 2 回合那則多行 Bash（範圍內測試｜tail -3、完整套件｜tail -6、幾次 cli 實跑）——輸出最後 20 行只剩 cli，
紅測摘要看不出是哪一支；cmd 只存前 200 字，剛好截在 `pytest tests -q 2>&1` 的 `2`，舊碼把 `2` 當成要跑的目錄，什麼重跑都涵蓋不到。
驗：照擋訊息重跑、涵蓋那則的範圍而且綠 → 舊紅清掉；完整套件重跑、紅而且逐支列出 → 舊紅改記那幾支（ERP 那支列得出名字，
「不做｜」才對得到）；反例：重跑沒涵蓋（只跑第一段）或還是紅 → 照留，沒涵蓋的留帳 testfail_scope；擋訊息對看不出是哪一支的紅
列出整條指令的測試行（每段照抄重跑），看得出的不加。
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
# 第 0 步第 2 回合那則（前兩行照帳上的 cmd 原字；cli 實跑的幾行照輸出補）
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
    assert red["cmd"].endswith("pytest tests -q 2") and not rr.red_units(red)     # 前置：跟第 0 步一樣截在 `2`、看不出是哪一支
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
    """紅案例（RED_SCOPE_FROM_FULL_COMMAND × GREEN_CLEARS_ONLY_CASES_IT_RAN 的紅那一面，第 0 步第 5 回合）：完整套件重跑仍紅、
    逐支列出（只有 ERP）→ 看不出是哪一支的舊紅改記成 ERP 那支；之後「不做｜」對得到它。改前舊紅照留，兩筆一起擋。"""
    state = _gate0_red()
    _track(state, "python -m pytest tests -q 2>&1 | tail -3",
           f"=========================== short test summary info ===========================\nFAILED {ERP} - ...\n"
           "1 failed, 16 passed in 0.16s")
    assert [rr.red_units(f) for f in state["failing_tests"]] == [[ERP]]


def test_rerun_not_covering_scope_keeps_red_and_logs(logs):
    """反例：只照第一段重跑（第 0 步實際的做法，沒跑完整套件）而且綠 → 沒涵蓋，舊紅照留，留帳 testfail_scope（要重跑什麼、跑了什麼）。"""
    state = _gate0_red()
    _track(state, f'echo "== 範圍內測試" && {SCOPED} 2>&1', "16 passed in 0.12s")
    assert len(state["failing_tests"]) == 1
    (rec,) = [p for g, p in logs if g == "testfail_scope"]
    assert rec["event"] == "green_kept_red" and "pytest tests -q" in rec["red_cmd"] and rec["rule"] == "GREEN_CLEARS_ONLY_CASES_IT_RAN"


def test_rerun_still_red_keeps_red():
    """反例：涵蓋範圍重跑但還是紅、輸出又沒列出是哪一支 → 照擋（記一筆新的紅，舊紅不被截過的輸出取代）。"""
    state = _gate0_red()
    _track(state, "python -m pytest tests -q 2>&1 | tail -1", "1 failed, 16 passed in 0.16s")
    assert len(state["failing_tests"]) == 2 and all(not rr.red_units(f) for f in state["failing_tests"])


def test_block_message_lists_full_scope_for_unknown_red():
    """RED_SCOPE_FROM_FULL_COMMAND 的出口：看不出是哪一支的紅，擋訊息列出整條指令的每一段測試行（含截掉的完整套件那段、
    不含 cli 實跑），照抄就能重跑；看得出是哪一支的紅不加這一行。"""
    (red,) = _gate0_red()["failing_tests"]
    msg = st.testfail_message([red])
    line = next(ln for ln in msg.splitlines() if "重跑這個範圍" in ln)
    assert SCOPED in line and "python -m pytest tests -q 2>&1 | tail -6" in line and "orders.cli" not in line
    named = {**red, "summary": f"FAILED {ERP} - x\n1 failed"}
    assert "重跑這個範圍" not in st.testfail_message([named])


def test_over_cap_keeps_old_scope_and_narrow_green_does_not_clear():
    """反例（codex 一輪 BLOCK 1）：測試行加起來超過上限 → 不存 test_cmd（不丟後段縮小範圍），判法退回 cmd；之後只跑第一行綠
    → 第二行那組沒重跑，紅照留；擋訊息給通用出路（原指令完整照跑或跑整套）。"""
    state = {"failing_tests": [], "session": {"id": SID}, "turn_seq": 2}
    long_line = "python -m pytest " + " ".join(f"tests/test_m{k:03d}.py" for k in range(150)) + " -q"
    _track(state, f"python -m pytest tests/test_a.py -q\n{long_line}", "1 failed, 300 passed in 1.0s")
    (red,) = state["failing_tests"]
    assert red["test_cmd"] == ""
    _track(state, "python -m pytest tests/test_a.py -q", "3 passed in 0.1s")
    assert len(state["failing_tests"]) == 1
    assert "原指令完整照跑、別截斷輸出，或不點名檔跑整套" in st.testfail_message(state["failing_tests"])


def test_same_filtered_multiline_rerun_clears_both_sides_same_form():
    """反例（codex 一輪 BLOCK 2）：紅與這次的指令用同一種寫法比——多行指令裡 `pytest tests -k slow` 紅、輸出沒列案例，原樣重跑綠
    → 照「同一個篩選指令重跑」清掉（改前清得掉的，不能因為紅那邊只取測試行而清不掉）。"""
    state = {"failing_tests": [], "session": {"id": SID}, "turn_seq": 2}
    cmd = "echo setup\npython -m pytest tests -k slow"
    _track(state, cmd, "1 failed, 2 passed, 5 deselected in 0.1s")
    assert len(state["failing_tests"]) == 1
    _track(state, cmd, "3 passed, 5 deselected in 0.1s")
    assert state["failing_tests"] == []
    assert ptu._red_pair({"cmd": cmd[:200]}, cmd) == (cmd, cmd)                       # 舊條目兩邊都用原字
    assert ptu._red_pair({"test_cmd": "python -m pytest tests -k slow"}, cmd) == ("python -m pytest tests -k slow",) * 2


def test_rerun_scope_keeps_cd_line_and_is_not_cut():
    """codex 一輪 BLOCK 4：獨立一行的 cd 是測試在哪裡跑的前提，要一起列出；範圍整段列出、不截在中間。"""
    state = {"failing_tests": [], "session": {"id": SID}, "turn_seq": 2}
    long_tests = " ".join(f"tests/test_n{k:02d}.py" for k in range(40))
    _track(state, f"cd services/billing\necho go\npython -m pytest {long_tests} -q 2>&1 | tail -1", "1 failed, 40 passed")
    line = next(ln for ln in st.testfail_message(state["failing_tests"]).splitlines() if "重跑這個範圍" in ln)
    assert "cd services/billing ； python -m pytest" in line and long_tests in line and "echo go" not in line


@pytest.mark.parametrize("cmd, want", [
    ("python -m pytest tests -q", "python -m pytest tests -q"),                               # 一行：照原樣
    ("cd proj\npython -m pytest \\\n  tests/test_a.py -q\necho done", "cd proj\npython -m pytest    tests/test_a.py -q"),  # 續行併、cd 留、別的不收
    ("echo hi\nmake build", "echo hi\nmake build"),                                            # 一行測試都認不出：整條
    ("pytest a.py\n" + "pytest " + "b" * ptu.TEST_CMD_CAP, ""),                                # 超過上限：不存（不丟後段縮範圍）
])
def test_test_cmd_takes_whole_test_lines(cmd, want):
    """RED_SCOPE_FROM_FULL_COMMAND 的事實：test_cmd＝整條指令裡跑測試與換目錄的那幾行，續行先併；超過上限回空。"""
    assert ptu._test_cmd(cmd) == want


if __name__ == "__main__":
    import subprocess
    rc = subprocess.run([sys.executable, "-X", "utf8", "-m", "pytest", __file__, "-q", "-p", "no:cacheprovider"]).returncode
    print("RED_SCOPE_CHECK PASS" if rc == 0 else "RED_SCOPE_CHECK FAIL")
    sys.exit(0 if rc == 0 else 1)

"""verify_gate005_c1_e2e.py：第四跑 C-1 的紅測豁免端到端重播（閘小修 005 件 1＋件 2）。

拿 C-1 對話的真實事件（fixtures/gate005/c1_redtest_events.json：使用者原話、AI 每段文字、14 次測試指令與輸出、Stop hook 擋訊息、
17 個 Stop 點，帳號名已換掉）照原順序重播：測試指令走 PostToolUse 的紅測記帳／清帳（handlers.post_tool_use._track_test_result），
Stop 點走完整的 handlers.stop.handle_stop（別的閘換成不擋，只留紅測閘與它前面的段）。證明：
- 第 2 回合使用者說「先不用管它、跳過」、AI 只跑另外 3 支測試檔變綠——ERP 那支紅照留（GREEN_CLEARS_ONLY_CASES_IT_RAN），收尾的
  不做行對到它、豁免成立並記帳（testfail_waivers 一筆、testfail_waived via=quote、deferral_declared 一筆）；
- 第 7 回合原話早已擠出近 3 則，兩條真指令（混了 git 的那條、單獨重跑全套那條）的紅照帳放行（via=ledger），不再擋；
- 放行只對 ERP 那支：最後一次 3 支測試檔變綠之後，紅測清單裡還留著 ERP 那支（其他支被跑到的綠拿掉了）；
- 帳拿掉時（舊碼的情況）第 7 回合照擋，擋訊息列的是 ERP 節點與「引用不在近 3 則」，不是 Untracked files:／Exit code 1。
怎麼跑：set WG_CLAUDE_DIR=<worktree> && python -X utf8 -m pytest -q hooks/verify/verify_gate005_c1_e2e.py
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import wg_release_rules as rr  # noqa: E402
from handlers import post_tool_use as ptu  # noqa: E402
from handlers import stop as st  # noqa: E402

FIX = HOOKS_DIR / "verify" / "fixtures" / "gate005" / "c1_redtest_events.json"
SID = "sid-c1-e2e"
ERP = "tests/test_erp_contract.py::test_checkout_fields_match_erp_contract"
SKIP_SAID = "先不用管它、跳過"
_C1_LINE = f"不做｜test_checkout_fields_match_erp_contract：使用者說「{SKIP_SAID}」"


@pytest.fixture(autouse=True)
def _temp_rules_off(monkeypatch):
    monkeypatch.setenv("WG_TEMP_RULES", "off")


@pytest.fixture()
def replay(monkeypatch, tmp_path):
    """照 fixture 順序重播；回 run(stop_hook=None) → 每個 Stop 點的 {turn, line, out, logs, failing}，與最後的 state。
    stop_hook(state, turn, stop_no)：Stop 前改 state 的掛勾（拿掉帳模擬舊碼）。"""
    logs: list = []
    stubs = {
        "_find_session_transcript": lambda *a, **k: None, "token_warn_payload": lambda *a, **k: "",
        "detect_evasion": lambda *a, **k: None, "write_state": lambda *a, **k: None,
        "_attribute_usefulness": lambda *a, **k: None, "_detect_uncommitted_files": lambda mf: [],
        "_maybe_spawn_user_extract_worker": lambda *a, **k: None, "_hud_alive": lambda *a, **k: (True, {}),
        "harvest_gate_reason": lambda *a, **k: None, "pending_gate_reason": lambda *a, **k: None,
        "deferral_gate_reason": lambda *a, **k: None, "_record_pick": lambda *a, **k: None,
        "_acceptance_regression_hint": lambda *a, **k: "", "reading_path_note": lambda *a, **k: ("", False),
        "_should_deep_postmortem": lambda *a, **k: False, "_pick_one_prompt": lambda *a, **k: None,
        "detect_missing_aec_emission": lambda *a, **k: False,
        "leftover_cleanup_verdict": lambda *a, **k: rr.Verdict("LEFTOVER_NEEDS_CLEANUP", False, "測試關掉"),
        "append_guard_log": lambda guard, payload: logs.append((guard, payload)),
    }
    for name, fn in stubs.items():
        monkeypatch.setattr(st, name, fn)
    monkeypatch.setattr(st.aec_ledger, "collect_at_completion", lambda *a, **k: None)
    monkeypatch.delenv("CLAUDE_COMPANION_JUDGE", raising=False)
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli")
    events = json.loads(FIX.read_text(encoding="utf-8"))["events"]
    tpath = tmp_path / "transcript.jsonl"

    def _rec(obj):
        with tpath.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    def run(stop_hook=None):
        tpath.write_text("", encoding="utf-8")
        state = {"phase": "working", "modified_files": [], "failing_tests": [], "recent_user_prompts": [],
                 "stop_blocked_count": 0, "turn_seq": 0, "muted": True, "session": {"id": SID, "cwd": ""}}
        monkeypatch.setattr(st, "_ensure_state", lambda *a, **k: state)
        stops, turn, last = [], 0, ""
        cfg = {"reconcile_gate": {"enabled": False}, "aec": {"scan_report_gate": False},
               "atom_audit": {"enabled": False}, "sync_reminder": {"enabled": False}}
        for ev in events:
            if ev["kind"] == "prompt":
                turn += 1
                state["turn_seq"] = turn
                state["turn_prompts_seq"] = turn
                state["turn_open"] = True
                state["recent_user_prompts"] = [*state["recent_user_prompts"], ev["text"]][-5:]
                _rec({"type": "user", "message": {"role": "user", "content": ev["text"]}})
            elif ev["kind"] == "say":
                last = ev["text"]
                _rec({"type": "assistant", "message": {"content": [{"type": "text", "text": ev["text"]}]}})
            elif ev["kind"] == "feedback":
                _rec({"type": "user", "isMeta": True, "message": {"role": "user", "content": ev["text"]}})
            elif ev["kind"] == "bash":
                resp = ev["output"] if ev["is_error"] else {"stdout": ev["output"], "stderr": "", "interrupted": False}
                ptu._track_test_result(state, {"session_id": SID, "cwd": "C:/w4/qc2-orders", "tool_response": resp},
                                       ev["cmd"], "Bash", {})
            elif ev["kind"] == "stop":
                if stop_hook:
                    stop_hook(state, turn, len(stops))
                logs.clear()
                with pytest.raises(SystemExit):
                    st.handle_stop({"session_id": SID, "cwd": "", "transcript_path": str(tpath),
                                    "last_assistant_message": last}, cfg)
                out = run.capsys.readouterr().out
                stops.append({"turn": turn, "line": ev["line"], "out": out, "logs": list(logs),
                              "failing": copy.deepcopy(state.get("failing_tests") or [])})
        return stops, state

    return run


def _red(stop):
    return "[Guardian:TestFailGate]" in stop["out"]


def _waived(stop, via):
    return [p for g, p in stop["logs"] if g == "testfail_waived" and p.get("via") == via]


def test_c1_waiver_booked_on_turn2_and_released_on_turn7_only_for_erp(replay, capsys):
    replay.capsys = capsys
    stops, state = replay()
    assert [s["turn"] for s in stops].count(7) == 4, "前置：第 7 回合有 4 個 Stop 點（真實紀錄被擋兩次後收尾）"
    t2 = [s for s in stops if s["turn"] == 2]
    assert t2 and not any(_red(s) for s in t2), [s["out"][:300] for s in t2 if _red(s)]
    first = next(s for s in t2 if _waived(s, "quote"))
    assert _waived(first, "quote")[0]["user_said"] == SKIP_SAID
    assert any(g == "deferral_declared" and p.get("rule") == "USER_WAIVER_NEEDS_CITATION" for g, p in first["logs"])
    assert any(rr.red_units(f) == [ERP] for f in first["failing"]), "3 支測試檔變綠沒清掉 ERP 那支（舊碼整筆清掉，豁免沒機會記帳）"
    led = state.get("testfail_waivers") or []
    assert len(led) == 1 and led[0]["units"] == [ERP] and led[0]["quote"] == SKIP_SAID
    # 第 7 回合：第一次收尾 AI 還沒寫不做行（真實紀錄也是）→ 照擋，擋訊息直接給那一行；之後三次收尾都有不做行 → 照帳放行
    t7 = [s for s in stops if s["turn"] == 7]
    assert _red(t7[0]) and "帳上有" in t7[0]["out"] and _C1_LINE in t7[0]["out"], t7[0]["out"][:600]
    assert not any(_red(s) for s in t7[1:]), [s["out"][:400] for s in t7[1:] if _red(s)]
    assert all(_waived(s, "quote") or _waived(s, "ledger") for s in t7[1:]), "寫了不做行就放行（引用不再比對近 3 則）"
    # 第 6 回合回答使用者的問題時宣告完成、沒寫不做行：ERP 那支還紅，同樣照擋並給那一行（舊碼這時紅已被 3 支測試檔的綠誤清）
    t6 = [s for s in stops if s["turn"] == 6]
    assert t6 and _red(t6[0]) and _C1_LINE in t6[0]["out"]
    reds = [f for f in state["failing_tests"] if rr.red_units(f)]
    assert reds and all(rr.red_units(f) == [ERP] for f in reds), [(f["cmd"][:60], rr.red_units(f)) for f in reds]


def test_c1_turn1_block_lists_failed_nodes_not_summary_first_line(replay, capsys):
    """第 1 回合（使用者還沒說跳過）宣告做完了照擋；擋訊息列 FAILED 節點與指令實際那行，不是「# 定位…」註解或 Exit code 1。"""
    replay.capsys = capsys
    stops, _ = replay()
    blocked = [s for s in stops if s["turn"] == 1 and _red(s)]
    assert blocked, "前置：第 1 回合有紅又宣告完成，照擋"
    msg = blocked[0]["out"]
    assert ERP in msg and ": Exit code 1" not in msg and "# 定位" not in msg, msg[:800]


def _track(state, cmd, out, ok):
    resp = {"stdout": out, "stderr": "", "interrupted": False} if ok else f"Exit code 1\n{out}"
    ptu._track_test_result(state, {"session_id": SID, "cwd": "C:/w4/qc2-orders", "tool_response": resp}, cmd, "Bash", {})


def test_green_shrinks_red_per_case_and_a_new_red_is_not_masked():
    """GREEN_CLEARS_ONLY_CASES_IT_RAN 的帳隨時間演進（codex 005）：A、B 一起紅 → 只跑 A 綠（A 從那筆拿掉、B 照留）→ A 又紅（新的一筆）
    → 只跑 B 綠（舊那筆清掉）→ 剩 A 那筆，舊的清帳紀錄不會遮住新的紅。"""
    a, b = "tests/test_a.py::test_a", "tests/test_b.py::test_b"
    state = {"failing_tests": [], "session": {"id": SID}, "turn_seq": 1}
    _track(state, "python -m pytest tests -q", f"FAILED {a} - x\nFAILED {b} - y\n2 failed, 3 passed", False)
    _track(state, "python -m pytest tests/test_a.py -q", "1 passed", True)
    assert [(rr.red_units(f), f.get("cleared_units")) for f in state["failing_tests"]] == [([b], [a])]
    _track(state, "python -m pytest tests/test_a.py -q", f"FAILED {a} - z\n1 failed", False)
    _track(state, "python -m pytest tests/test_b.py -q", "1 passed", True)
    assert [rr.red_units(f) for f in state["failing_tests"]] == [[a]], state["failing_tests"]


def test_c1_without_ledger_turn7_line_still_releases(replay, capsys):
    """拿掉帳：第 7 回合第一次收尾沒寫不做行照擋（擋訊息列 ERP 節點，不列 Untracked files:）；之後寫了「不做｜…：使用者說「…」」
    的那幾次放行——引用不再比對近 3 則原話（USER_WAIVER_NEEDS_CITATION 只看不做行，留帳抽查）。"""
    replay.capsys = capsys

    def drop_ledger(state, turn, _n):
        if turn == 7:
            state["testfail_waivers"] = []

    stops, _ = replay(drop_ledger)
    t7 = [s for s in stops if s["turn"] == 7]
    assert t7 and _red(t7[0]) and ERP in t7[0]["out"] and "Untracked files" not in t7[0]["out"], t7[0]["out"][:600]
    assert not any(_red(s) for s in t7[1:]), [s["out"][:400] for s in t7[1:] if _red(s)]

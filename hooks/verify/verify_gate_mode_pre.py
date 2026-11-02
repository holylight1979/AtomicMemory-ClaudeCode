"""verify_gate_mode_pre.py：工具前守門「擋改提醒」（規則 GATE_MODE_TABLE、REMIND_ON_PRIOR_RESULT）。

v6 總開關開時，提問閘、OverviewHub 閘自己壞（P2～P10d）都不再 deny：
下一個工具結果（PostToolUse 的 additionalContext）附一行提醒，
同一條規則同一個對象一個 session 只提醒一次，沒照做不擋、也不送第二次。照擋的病形閘不動；
v6 關時每條路都跟改前一樣。都走真的 PreToolUse／PostToolUse 入口。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_gate_mode_pre.py
共用 hub_world 的資料根隔離（env／hooked）與部位世界；照擋那案借 verify_pull_tool_gates 的假專案。不碰 live。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

VERIFY = Path(__file__).resolve().parent
sys.path.insert(0, str(VERIFY))

from hub_world import (  # noqa: E402,F401
    SID, THREE2, _deny_text, _mapped_world, _ptu_run, _say, _tool_call, _two_part_world, env, hooked, pt, ptu, wg_core, wo,
)
from verify_pull_tool_gates import (  # noqa: E402,F401
    SID as PULL_SID, _pre as _pull_pre, world as pull_world,
)
import wg_release_rules as _rr  # noqa: E402

REMIND = "[Guardian:提醒]"


@pytest.fixture(autouse=True)
def _v6_on(monkeypatch):
    monkeypatch.setenv("WG_V6", "1")


@pytest.fixture
def post(hooked, monkeypatch):
    """跑一次真的 PostToolUse，回那次工具結果附的 additionalContext（沒有回空字串）。"""
    got = []
    monkeypatch.setattr(pt, "output_json", lambda d: (got.append(d), sys.exit(0)))
    monkeypatch.setattr(pt, "output_nothing", lambda: (got.append(None), sys.exit(0)))
    monkeypatch.setattr(pt, "_check_output_quality", lambda *a, **k: None)
    monkeypatch.setattr(pt, "_run_companion_hooks", lambda *a: [])
    monkeypatch.setattr(pt, "_note_commit", lambda *a, **k: None)

    def run(tool, tool_input, config=None, tool_response=None, tid="tu-post"):
        inp = {"session_id": SID, "hook_event_name": "PostToolUse", "tool_name": tool, "tool_input": tool_input,
               "tool_response": tool_response if tool_response is not None else {}, "cwd": str(hooked["proj"]),
               "transcript_path": hooked["tp"], "tool_use_id": tid}
        with pytest.raises(SystemExit):
            pt.handle_post_tool_use(inp, {"docdrift": {"enabled": False}, **(config or {})})
        return ((got[-1] or {}).get("hookSpecificOutput") or {}).get("additionalContext") or ""
    return run


def _pre(hooked, tool, tool_input, config=None):
    """跑一次真的 PreToolUse；回 (deny 文字或 None, 整個輸出)。"""
    out = _ptu_run(tool, tool_input, hooked["proj"], hooked["tp"], hooked["outputs"], config=config)
    return _deny_text(out), out


def _edit_input(f):
    return {"file_path": f, "old_string": "x", "new_string": "y"}


def _ask(labels, question="要用哪個做法？"):
    return {"questions": [{"question": question, "header": "做法", "multiSelect": False,
                           "options": [{"label": l, "description": f"{l} 的說明"} for l in labels]}]}


def _state_seed(hooked):
    wg_core.write_state(SID, {"session": {"id": SID, "cwd": str(hooked["proj"])}, "turn_seq": 1})


def _hub_events(hooked, event):
    p = hooked["tmp"] / "hub.log"
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []
    return [e for e in rows if e["event"] == event]


def _lines(ctx, rule):
    return [ln for ln in ctx.splitlines() if ln.startswith(REMIND) and rule in ln]


# ─── P2／P2c 提問閘 ─────────────────────────────────────────────────────────

def test_ask_no_recommendation_reminded_not_denied(hooked, post):
    """P2：沒附推薦的提問不擋；AskUserQuestion 的工具結果附一行（規則名＋做法）；同 session 第二題沒推薦不再提醒、也不擋。"""
    _state_seed(hooked)
    bad = _ask(["A", "B"])
    deny, out = _pre(hooked, "AskUserQuestion", bad)
    assert deny is None and out is None, out                       # 不擋、PreToolUse 不送 additionalContext
    ctx = post("AskUserQuestion", bad)
    line = _lines(ctx, "ASK_NEEDS_RECOMMENDATION")
    assert len(line) == 1 and "做法：" in line[0] and "(Recommended)" in line[0], ctx
    assert [p["rule"] for g, p in hooked["guard"] if g == "ask" and p["event"] == "remind"
            and p["rule"] == "ASK_NEEDS_RECOMMENDATION"] == ["ASK_NEEDS_RECOMMENDATION"]
    deny, _ = _pre(hooked, "AskUserQuestion", _ask(["C", "D"], "再問一題？"))
    assert deny is None
    assert not _lines(post("AskUserQuestion", bad), "ASK_NEEDS_RECOMMENDATION")


def test_ask_gate_error_not_denied(hooked, post, monkeypatch):
    """P2c：提問前檢查自己壞了 → 不擋、stderr＋留帳 ask_error（GATE_SELF_ERROR），下一個工具結果附一行提醒。"""
    _state_seed(hooked)
    monkeypatch.setitem(sys.modules, "wg_ask_gate", None)
    deny, out = _pre(hooked, "AskUserQuestion", _ask(["A", "B"]))
    assert deny is None and out is None, out
    assert [(p["event"], p.get("rule")) for g, p in hooked["guard"] if g == "ask" and p["event"] == "ask_error"] \
        == [("ask_error", "GATE_SELF_ERROR")]
    monkeypatch.delitem(sys.modules, "wg_ask_gate")
    ctx = post("AskUserQuestion", _ask(["A", "B"]))
    assert _lines(ctx, "GATE_SELF_ERROR") and "提問前檢查" in _lines(ctx, "GATE_SELF_ERROR")[0], ctx


# ─── P10d 閘自己炸 ────────────────────────────────────────────────────

def test_hub_self_error_not_denied(hooked, post, monkeypatch):
    """P10d：OverviewHub 寫入檢查自己炸 → 不擋、stderr＋留帳 gate_error（GATE_SELF_ERROR）、下一個工具結果附一行。"""
    f1 = _mapped_world(hooked)

    def boom(*a, **k):
        raise RuntimeError("模擬閘內部錯誤")
    real = wo.write_check
    monkeypatch.setattr(wo, "write_check", boom)
    deny, out = _pre(hooked, "Edit", _edit_input(f1))
    assert deny is None and out is None, out
    assert [(e.get("rule"), e.get("allowed")) for e in _hub_events(hooked, "gate_error")] == [("GATE_SELF_ERROR", True)]
    monkeypatch.setattr(wo, "write_check", real)
    ctx = post("Edit", _edit_input(f1))
    assert _lines(ctx, "GATE_SELF_ERROR") and "模擬閘內部錯誤" in _lines(ctx, "GATE_SELF_ERROR")[0], ctx


# ─── 照擋的病形閘不動 ───────────────────────────────────────────────────

def test_block_table_has_only_smell_and_red_test_classes():
    """照擋只剩兩類：病形閘、紅測（測試沒過卻說修好）；拔掉的宣告閘規則不在規則表、也不在照擋表。"""
    assert set(_rr.RULE_CLASS.values()) == {"病形", "紅測", "不在範圍"}
    for gone in ("USER_DATA_FILE_NEEDS_DECLARATION", "OLD_TEST_CHANGE_NEEDS_DECLARATION", "GATE_BYPASS_NEEDS_DECLARATION",
                 "ATOM_BYPASS_HOWTO_REFUSED", "USER_WAIVER_NEEDS_CITATION", "BASE_RED_TRACKED_NOT_OWED"):
        assert gone not in _rr.RULES and gone not in _rr.RULE_MODE, gone


def test_block_smell_has_rule_and_fix(pull_world, monkeypatch):
    """病形閘的擋訊息原樣送出（規則名＋修法）；這裡換掉病形判定本體，只驗 pre_tool_use 這條路照擋。"""
    for name in ("check_git_commit_order", "check_git_privacy", "check_merge_driver"):
        monkeypatch.setattr(ptu, name, lambda *a, **k: None)
    text = "[Guardian:SmellGate] 修法：拆掉這次提交新寫進的巢狀\n✗ (s) COMMIT_SMELL_NEW_BLOCKS：a.py 巢狀 4 層"
    monkeypatch.setattr(ptu, "check_smell_gate", lambda *a, **k: (text, None))
    r = _pull_pre(pull_world, "Bash", {"command": 'git commit -m "x"'})
    assert r.startswith(text), r
    assert _rr.gate_mode("COMMIT_SMELL_NEW_BLOCKS", True) == _rr.BLOCK


def test_smell_gate_blocks_once_per_turn_then_releases_with_note(pull_world, monkeypatch):
    """SMELL_GATE_ONCE_PER_TURN：同一回合同一個 repo 只擋第一次；修了又長新病或原樣重送，第二次放行、留帳、擋訊息改當提醒送；
    換使用者回合重新算。反例：沒有 state（記不住擋過）照擋。"""
    for name in ("check_git_commit_order", "check_git_privacy", "check_merge_driver"):
        monkeypatch.setattr(ptu, name, lambda *a, **k: None)
    text = "[Guardian:SmellGate] 這次要提交的程式新寫進了舊碼的病（1 處），commit 已擋下。\n  ✗ 控制結構巢狀太深"
    monkeypatch.setattr(ptu, "check_smell_gate", lambda *a, **k: (text, None))
    cmd = {"command": 'git commit -m "x"'}
    assert _pull_pre(pull_world, "Bash", cmd, tool_use_id="t1").startswith(text)
    assert _pull_pre(pull_world, "Bash", cmd, tool_use_id="t2") == ""                       # 原樣重送：放行
    warn = (pull_world["outputs"][-1] or {}).get("systemMessage", "")
    assert "已經擋過一次，這次放行並留帳" in warn and "AI 自己做主" in warn and text in warn
    events = [e["event"] for e in _events_of(pull_world, "smell_gate")]
    assert events == ["denied", "released"], events
    st = wg_core.read_state(PULL_SID)
    st["turn_seq"] = 2
    wg_core.write_state(PULL_SID, st)
    assert _pull_pre(pull_world, "Bash", cmd, tool_use_id="t3").startswith(text)          # 換回合：重新擋
    monkeypatch.setattr(ptu, "read_state_status", lambda sid: (None, "missing"))
    assert _pull_pre(pull_world, "Bash", cmd, tool_use_id="t4").startswith(text)          # 沒 state：照擋


def _events_of(w, guard):
    p = w["logs"] / f"guard-{guard}.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


# ─── v6 關：一字不變 ────────────────────────────────────────────────────

def test_v6_off_pre_gates_unchanged(hooked, post, monkeypatch):
    """總開關關：提問閘照擋（不讀本表）、改程式沒樹不查（9e476fd0 就沒有）、讀檔與改檔結果都沒有提醒行。"""
    monkeypatch.setenv("WG_V6", "0")
    _state_seed(hooked)
    f1 = _mapped_world(hooked)
    deny, _ = _pre(hooked, "AskUserQuestion", _ask(["A", "B"]))
    assert deny and "ASK_NEEDS_RECOMMENDATION" in deny
    assert REMIND not in post("Read", {"file_path": f1})
    deny, out = _pre(hooked, "Edit", _edit_input(f1))
    assert deny is None
    assert REMIND not in post("Edit", _edit_input(f1))
    assert not wg_core.read_state(SID).get("remind_pending") and not wg_core.read_state(SID).get("remind_sent")


if __name__ == "__main__":
    import subprocess
    rc = subprocess.run([sys.executable, "-X", "utf8", "-m", "pytest", __file__, "-q", "-p", "no:cacheprovider"]).returncode
    print("GATE_MODE_PRE_CHECK PASS" if rc == 0 else "GATE_MODE_PRE_CHECK FAIL")
    sys.exit(0 if rc == 0 else 1)


# ─── OverviewHub 綁 v6 總開關：關時 enabled 一律 False（OVERVIEW_HUB_UNDER_V6） ───
def test_v6_off_overview_hub_disabled(monkeypatch):
    import wg_overview as ovh
    import wg_release_rules as _rr
    assert "OVERVIEW_HUB_UNDER_V6" in _rr.RULES
    monkeypatch.setattr(ovh, "v6_enabled", lambda config: False)
    cfg = ovh._cfg({"overview_hub": {"enabled": True}})
    assert cfg["enabled"] is False
    monkeypatch.setattr(ovh, "v6_enabled", lambda config: True)
    cfg_on = ovh._cfg({"overview_hub": {"enabled": True}})
    assert cfg_on["enabled"] is True

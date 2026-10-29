"""verify_closing_merge.py：收尾三段一次交齊（收尾檢核 anti_evasion_report 帶 reconcile＝目標對照、harvest_items＝知識收割）。

做什麼：
  CLOSING_RECONCILE_IN_REPORT  收尾檢核的 reconcile 欄交給 wg_need_goal.apply_op（跟 need_goal reconcile 同一個入口、回覆逐字相同）；
                               一次交齊 → Stop 不再要求目標對照與知識收割；套不上只少這段、收尾檢核照收。
  CLOSING_MISSING_PART_HINT    只交收尾檢核 → (f2) 照擋，擋訊息寫明缺的是目標對照、只補這段；收尾檢核擋訊息寫一次交齊的走法。
  CLOSING_GOAL_CODING_ONLY     不是寫碼回合（樹上有改動但本回合、本 session 都沒改程式，例：續接單匯入的舊樹）→ 不要求 (f2)(f3)；
                               本回合宣告了寫碼樹 → 照要。
  CLOSING_CALL_ALL_THREE       收尾那批的認法認三支：收尾檢核、need_goal reconcile、knowledge_harvest_report。
  舊三支分開交照收；總開關關時 reconcile 欄不套用（行為同改動前）。
會紅：拿改動前的 main（f45be4ea）回放，前四類是紅（舊碼不認 reconcile 欄 → (f2) 照擋；擋訊息沒有「缺哪段」；續接單匯入的樹在非寫碼回合
  照要 (f2)；closing_call 不認 knowledge_harvest_report）。最後兩類（舊三支照收、總開關關）是守住舊行為，舊碼本來就綠。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_closing_merge.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import wg_closing_round as cr  # noqa: E402
import wg_harvest  # noqa: E402
import wg_need_goal as ng  # noqa: E402
from handlers import post_tool_use as pt  # noqa: E402
from handlers import stop as st  # noqa: E402
from verify_need_goal import ON, SID, _code_tree, _op, _stop_env, _tree, env  # noqa: E402,F401  共用 tmp 資料根與 Stop 驅動
from verify_gate_trim import stop_drive  # noqa: E402,F401


@pytest.fixture(autouse=True)
def _block_mode(monkeypatch):
    """規則 GATE_MODE_TABLE：送法只讀 wg_release_rules.RULE_MODE。這個檔的案例驗的是判定與擋訊息內容，把送法釘成 block 讓它們照驗；v6 預設的提醒送法（Stop 只留帳、提醒掛改檔那則工具結果）由 verify_gate_mode_stop.py 驗。"""
    import wg_release_rules as _rr
    monkeypatch.setattr(_rr, "mode_of", lambda rule: _rr.BLOCK)

SKIP = [{"source": "decision", "summary": "這次的取捨寫在程式註解裡", "action": "skip", "reason": "讀程式就看得到"}]
RECON = {"items": [{"id": n, "status": "none", "followup": "等使用者給格式"} for n in ("T1", "T1.1", "T1.2")], "turns": 1}
HARVEST_ON = {"harvest": {"enabled": True, "min_turns": 3, "min_accessed": 5, "min_turns_between": 3, "background": False}}
AEC_NAME = "mcp__workflow-guardian__anti_evasion_report"


def _state(proj, **extra):
    return {"turn_seq": 3, "turn_prompts_seq": 3, "session": {"id": SID, "cwd": str(proj)}, "modified_files": [],
            "need_goal_code_decl_turn": 3, **extra}


def _aec(monkeypatch, capsys, state, proj, config=None, **over):
    """跑一次收尾檢核的 PostToolUse（state 就地改）→ 送回 AI 的 additionalContext。"""
    inp = {"a": "無", "b": "無", "d": "見收割報告", "h": "可關閉", "i": "無", "j_evidence_path": "無", "k_followups": "無",
           "report": "做了什麼：改了 a。驗了什麼：verify 全綠。沒做什麼：無。追蹤項：無。", **over}
    for name, fn in (("_ensure_state", lambda *a, **k: state), ("write_state", lambda *a, **k: None),
                     ("_hud_alive", lambda *a, **k: (True, {})), ("append_guard_log", lambda *a, **k: None),
                     ("_spawn_hud_edge", lambda *a, **k: None), ("spawn_vcs_sync", lambda *a, **k: None)):
        monkeypatch.setattr(pt, name, fn, raising=False)
    with pytest.raises(SystemExit):
        pt.handle_post_tool_use({"session_id": SID, "cwd": str(proj), "tool_name": AEC_NAME, "tool_input": inp,
                                 "tool_response": {}}, {"docdrift": {"enabled": False}, "aec": {}, **ON, **(config or {})})
    out = capsys.readouterr().out.strip()
    return json.loads(out.splitlines()[-1]).get("hookSpecificOutput", {}).get("additionalContext", "") if out else ""


def _stop(monkeypatch, capsys, state, config, text="全部完成。"):
    _stop_env(None, monkeypatch, state)
    with pytest.raises(SystemExit):
        st.handle_stop({"session_id": SID, "last_assistant_message": text}, config)
    out = capsys.readouterr().out.strip()
    return json.loads(out.splitlines()[-1]) if out else {}


# ─── CLOSING_RECONCILE_IN_REPORT ────────────────────────────────────────────────

def test_one_call_carries_reconcile_and_harvest_then_stop_asks_nothing_else(env, monkeypatch, capsys):
    """規則 CLOSING_RECONCILE_IN_REPORT：收尾檢核一次帶 reconcile 與 harvest_items → 目標樹記成對照過、收割核過、收尾檢核收下；
    目標對照閘、收割閘、收尾檢核閘都開著，Stop 不再要求另外兩支（舊碼不認 reconcile 欄 → (f2) 照擋 → 紅）。"""
    proj = _code_tree(env)
    state = _state(proj)
    ctx = _aec(monkeypatch, capsys, state, proj, harvest_items=SKIP, reconcile=RECON)
    tree = _tree()
    assert tree["last_reconcile"] and tree["last_reconcile"].get("turns") == 1 and "by" not in tree["last_reconcile"]
    assert "reconcile 收下" in ctx and state["anti_evasion_report"]["reconcile"] == "applied"
    assert state["anti_evasion_report"]["need_goal"]["reconcile"]["turn"] == 3, "HUD 附的樹是這次對照後的"
    assert wg_harvest.validated_this_turn(state, SID, 3) and "d_pending" not in state["anti_evasion_report"]
    cfg = {**ON, **HARVEST_ON, "aec": {"scan_report_gate": True}}
    out = _stop(monkeypatch, capsys, state, cfg)
    reason = out.get("reason", "")
    assert "(f2)" not in reason and "[Guardian:KnowledgeHarvest]" not in reason and "[Guardian:ScanReport]" not in reason, reason


def test_reconcile_field_reply_identical_to_need_goal(env, monkeypatch, capsys):
    """同一棵樹、同一份對照：走收尾檢核 reconcile 欄跟走 need_goal reconcile 回的那段逐字相同（同一個 apply_op）。"""
    proj = _code_tree(env)
    other = "sess-goal-0002"
    _op("set", goal="A", sid=other, cwd=str(proj))
    _op("add", items=[{"text": "a1"}, {"text": "a2"}], sid=other)
    ng.stamp_edit(other, str(proj / "a.py"), "", 2, {})
    via_report, how = pt._aec_reconcile(_state(proj), SID, RECON, {"cwd": str(proj)}, ON)
    via_tool = ng.apply_op(other, 3, {"action": "reconcile", **RECON}, str(proj))["text"]
    assert how == "applied" and via_report == via_tool


def test_bad_reconcile_only_loses_that_part(env, monkeypatch, capsys):
    """reconcile 欄對不上（節點不存在）→ 收尾檢核照收、對照沒套用、回覆寫明只要補交對照；Stop 照擋 (f2)。"""
    proj = _code_tree(env)
    state = _state(proj)
    ctx = _aec(monkeypatch, capsys, state, proj, reconcile={"items": [{"id": "T9", "status": "none", "followup": "x"}]})
    assert state["anti_evasion_report"]["reconcile"] == "rejected" and pt.AEC_RECONCILE_RETRY in ctx
    assert _tree()["last_reconcile"] is None
    assert "(f2)" in _stop(monkeypatch, capsys, state, {**ON}).get("reason", "")


# ─── CLOSING_MISSING_PART_HINT ──────────────────────────────────────────────────

def test_only_closing_check_then_f2_names_missing_part(env, monkeypatch, capsys):
    """規則 CLOSING_MISSING_PART_HINT：只交收尾檢核（沒帶 reconcile）→ (f2) 照擋，擋訊息寫明收尾檢核已交、缺目標對照、只補這段
    （舊碼擋訊息沒有這行 → 紅）；還沒交收尾檢核時寫一次交齊的走法。"""
    proj = _code_tree(env)
    state = _state(proj)
    _aec(monkeypatch, capsys, state, proj)
    reason = _stop(monkeypatch, capsys, state, {**ON}).get("reason", "")
    assert "(f2)" in reason and "收尾檢核本回合已交，缺目標對照" in reason and "收尾檢核不用重交" in reason
    assert "缺目標對照。" + st.CLOSING_ONE_CALL == st.closing_reconcile_hint(False).split("收尾三段：", 1)[1]


def test_closing_check_block_says_one_call(stop_drive, capsys):
    """規則 CLOSING_MISSING_PART_HINT：收尾檢核閘擋下時寫一次交齊的走法（目標對照放 reconcile、知識收割放 harvest_items）
    （舊碼只列 (a)～(k) → 紅）。"""
    mods = [{"path": r"c:\a\.claude\hooks\x.py", "tool": "Edit", "session_id": "s-ct", "turn_seq": 5, "last_turn_seq": 5}]
    out = stop_drive(capsys, "全部完成了", mods)
    assert "[Guardian:ScanReport]" in out and "reconcile 欄" in out and "harvest_items" in out


# ─── CLOSING_GOAL_CODING_ONLY ───────────────────────────────────────────────────

def test_imported_tree_not_asked_outside_coding_turn(env, monkeypatch, capsys):
    """規則 CLOSING_GOAL_CODING_ONLY：從續接單匯入的寫碼類舊樹（樹上是上一個 session 的改動），本回合、本 session 都沒改程式、
    也沒宣告寫碼樹 → 宣告完成不要求 (f2)(f3)（舊碼照擋 → 紅）；本回合宣告了寫碼樹 → 照要（反例）。"""
    proj = env["proj"]
    old = "sess-goal-old"
    _op("set", goal="舊需求", sid=old, cwd=str(proj))
    ng.stamp_edit(old, str(proj / "a.py"), "", 2, {})
    assert ng.import_handoff(SID, ng.handoff_block(old), "續接單.md", 1)["imported"]
    assert _tree()["kind"] == "code"
    state = _state(proj)
    state.pop("need_goal_code_decl_turn")
    reason = _stop(monkeypatch, capsys, state, {**ON}).get("reason", "")
    assert "(f2)" not in reason and "(f3)" not in reason, reason
    state = _state(proj)
    assert "(f2)" in _stop(monkeypatch, capsys, state, {**ON}).get("reason", "")


def test_closing_check_after_earlier_code_edit_still_asks(env, monkeypatch, capsys):
    """規則 CLOSING_GOAL_CODING_ONLY 的界線：本 session 前幾回合改過程式，這回合不改程式、不說完成，只交了不帶 reconcile 的收尾檢核
    → 交收尾檢核就是交付邊界，(f2) 照要（只看措辭的 _coding 會漏掉這種收尾 → 修補前紅）。"""
    proj = _code_tree(env)
    state = _state(proj, modified_files=[{"path": str(proj / "a.py"), "session_id": SID, "turn_seq": 2, "last_turn_seq": 2}])
    state.pop("need_goal_code_decl_turn")
    _aec(monkeypatch, capsys, state, proj)
    reason = _stop(monkeypatch, capsys, state, {**ON},
                   text="變更內容見收尾檢核報告。").get("reason", "")
    assert "(f2)" in reason and "收尾檢核本回合已交，缺目標對照" in reason, reason


# ─── CLOSING_CALL_ALL_THREE ─────────────────────────────────────────────────────

def test_closing_call_knows_all_three():
    """規則 CLOSING_CALL_ALL_THREE：收尾檢核（一次交齊）、need_goal reconcile、knowledge_harvest_report 都是收尾那批
    （舊碼不認 knowledge_harvest_report → 紅）；need_goal 其他動作不是。"""
    assert cr.closing_call(AEC_NAME, {"reconcile": RECON})
    assert cr.closing_call("mcp__workflow-guardian__knowledge_harvest_report", {"items": []})
    assert cr.closing_call("mcp__workflow-guardian__need_goal", {"action": "reconcile"})
    assert not cr.closing_call("mcp__workflow-guardian__need_goal", {"action": "set"})


# ─── 舊走法、總開關 ──────────────────────────────────────────────────────────────

def test_old_three_calls_still_accepted(env, monkeypatch, capsys):
    """舊三支分開交照收：need_goal reconcile、knowledge_harvest_report、不帶 reconcile 的收尾檢核 → Stop 不要求任何一段。"""
    proj = _code_tree(env)
    state = _state(proj)
    assert _op("reconcile", turn=3, cwd=str(proj), **RECON)["ok"]
    for name, fn in (("_ensure_state", lambda *a, **k: state), ("write_state", lambda *a, **k: None),
                     ("spawn_vcs_sync", lambda *a, **k: None)):
        monkeypatch.setattr(pt, name, fn, raising=False)
    with pytest.raises(SystemExit):
        pt.handle_post_tool_use({"session_id": SID, "cwd": str(proj), "tool_name": "mcp__workflow-guardian__knowledge_harvest_report",
                                 "tool_input": {"items": SKIP}, "tool_response": {}}, {"docdrift": {"enabled": False}, **ON})
    capsys.readouterr()
    _aec(monkeypatch, capsys, state, proj, d="見收割報告")
    assert "reconcile" not in state["anti_evasion_report"] and "d_pending" not in state["anti_evasion_report"]
    reason = _stop(monkeypatch, capsys, state, {**ON, **HARVEST_ON, "aec": {"scan_report_gate": True}}).get("reason", "")
    assert "(f2)" not in reason and "[Guardian:KnowledgeHarvest]" not in reason, reason


def test_v6_off_reconcile_field_not_applied(env, monkeypatch, capsys):
    """總開關關：收尾檢核的 reconcile 欄不套用、報告不記這欄（同改動前；Node 端也不驗這欄，由 verify_aec_reconcile.js 驗）。"""
    monkeypatch.setenv("WG_V6", "0")
    proj = _code_tree(env)
    state = _state(proj)
    _aec(monkeypatch, capsys, state, proj, reconcile=RECON)
    assert _tree()["last_reconcile"] is None and "reconcile" not in state["anti_evasion_report"]


def test_node_side_case_script_exists():
    """Node 端（schema、驗法、說明、chip）的案例在 tools/workflow-guardian-mcp/verify/verify_aec_reconcile.js（node 直接跑，帶 WG_V6=1）。"""
    js = HOOKS_DIR.parent / "tools" / "workflow-guardian-mcp" / "verify" / "verify_aec_reconcile.js"
    assert js.is_file() and "AEC_RECONCILE_CHECK" in js.read_text(encoding="utf-8")


if __name__ == "__main__":
    rc = pytest.main(["-q", __file__])
    print("CLOSING_MERGE_CHECK PASS" if rc == 0 else "CLOSING_MERGE_CHECK FAIL")
    sys.exit(0 if rc == 0 else 1)

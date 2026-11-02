"""verify_gate_mode_stop.py：收尾守門改提醒（規則 GATE_MODE_TABLE／REMIND_ON_PRIOR_RESULT 在 Stop 與 PostToolBatch 的接法）。

做什麼：v6 開著時 Stop 只照擋三類（紅測閘、對帳 (a) 說修好要有 PASS、子代理同一套），其餘 v6 守門一律提醒：
  提醒掛在最後一次改程式檔那則工具結果（handlers/post_tool_batch），Stop 只留帳（guard log event=remind）、不擋、不續跑、
  不開放行題；總開關關時行為一字不變。
每一案拿改動前的 main（016b58b5）回放：改成提醒的那幾案紅（舊碼 Stop 照擋或續跑）、照擋的兩案與 v6 關的那案綠（回歸守門）。
怎麼跑：python -X utf8 -m pytest -q -p no:cacheprovider hooks/verify/verify_gate_mode_stop.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import wg_release_rules as rr  # noqa: E402
from handlers import post_tool_batch as ptb  # noqa: E402
from handlers import stop as st  # noqa: E402

SID = "sid-gatemode"
CODE = r"c:\proj\hooks\x.py"
DONE = "改好了，全部完成。"
DEFER_DONE = "改好了，全部完成。剩下的 verify 清理留給下個 session 處理。"
OFF = {"enabled": False}


def _mf(path=CODE, turn=5, sid=SID, seq=10):
    return {"path": path, "tool": "Edit", "session_id": sid, "turn_seq": turn, "last_turn_seq": turn, "last_seq": seq,
            "at": "2026-10-27T10:00:00", "last_at": "2026-10-27T10:00:00"}


def _payload(out: str):
    lines = [ln for ln in out.strip().splitlines() if ln.strip()]
    return json.loads(lines[-1]) if lines else {}


@pytest.fixture
def drive(monkeypatch, capsys):
    """驅動 handle_stop：拿掉會碰外部的副作用（transcript、git、HUD、state 檔），閘本身照跑。
    回 run(text, config, **state) → (輸出 JSON 或 {}, state, guard log 事件)。"""
    logs: list = []
    for name, fn in (("_find_session_transcript", lambda *a, **k: None), ("token_warn_payload", lambda *a, **k: ""),
                     ("write_state", lambda *a, **k: None), ("_attribute_usefulness", lambda *a, **k: None),
                     ("_detect_uncommitted_files", lambda mf: []), ("_git_unpushed_roots", lambda mf: []),
                     ("_maybe_spawn_user_extract_worker", lambda *a, **k: None), ("_hud_alive", lambda *a, **k: (True, {})),
                     ("_should_deep_postmortem", lambda *a, **k: False),
                     ("_acceptance_regression_hint", lambda *a, **k: ""),
                     ("estimate_context_usage", lambda *a, **k: 0.3),
                     ("append_guard_log", lambda guard, payload: logs.append((guard, payload)))):
        monkeypatch.setattr(st, name, fn)
    monkeypatch.setattr(st.aec_ledger, "collect_at_completion", lambda *a, **k: None)
    monkeypatch.delenv("CLAUDE_COMPANION_JUDGE", raising=False)
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli")

    def run(text, config=None, hook=None, **extra):
        monkeypatch.setattr(st, "get_last_assistant_text", lambda *a, **k: text)
        monkeypatch.setattr(st, "get_current_turn_visible_text", lambda *a, **k: ("", {"turn_tool_names_all": []}))
        state = {"phase": "working", "modified_files": [], "failing_tests": [], "recent_user_prompts": [],
                 "stop_blocked_count": 0, "turn_seq": 5, "turn_prompts_seq": 5, **extra}
        monkeypatch.setattr(st, "_ensure_state", lambda *a, **k: state)
        cfg = {"reconcile_gate": OFF, "aec": {"scan_report_gate": False}, "atom_audit": OFF,
               "sync_reminder": OFF, "deferral_gate": OFF,
               "knowledge_harvest": OFF, **(config or {})}
        logs.clear()
        capsys.readouterr()
        with pytest.raises(SystemExit):
            st.handle_stop({"session_id": SID, "cwd": "", "last_assistant_message": text, **(hook or {})}, cfg)
        cap = capsys.readouterr()
        run.err = cap.err
        return _payload(cap.out), state, list(logs)

    return run


def _reminds(logs, guard=None):
    return [p for g, p in logs if p.get("event") == "remind" and (guard is None or g == guard)]


# ─── 照擋的兩類：擋訊息要有規則名與做法 ─────────────────────────────────────────

def test_block_testfail_has_rule_and_fix(drive, monkeypatch):
    """S2 紅測閘照擋：本 session 跑紅、宣告完成 → decision=block，訊息列失敗項與三條出路。寫碼守門開或關，擋訊息逐字相同
    （舊版出路：修復／明確說明不修／降級任務定義；沒有「不做｜」豁免與負向對照那兩條）。"""
    red = [{"session_id": SID, "cmd": "python -m pytest -q hooks/verify/verify_x.py", "summary": "1 failed", "turn_seq": 5}]
    out, _, _ = drive(DONE, failing_tests=[dict(r) for r in red])
    assert out.get("decision") == "block", drive.err
    assert "[Guardian:TestFailGate]" in out["reason"] and "(a)" in out["reason"] and "(b)" in out["reason"]
    assert "已知 regression" in out["reason"] and "不做｜" not in out["reason"] and "負向對照" not in out["reason"]
    on_msg = out["reason"].split("\n[Guardian:AlsoOwed]")[0]
    monkeypatch.setenv("WG_V6", "0")
    off, _, _ = drive(DONE, failing_tests=[dict(r) for r in red])
    assert off.get("decision") == "block" and off["reason"].split("\n[Guardian:AlsoOwed]")[0] == on_msg


def test_block_claim_fixed_has_rule_and_fix(drive):
    """S3 對帳 (a) 照擋：說修好、沒有任何 PASS → decision=block，訊息有規則名 CLAIM_FIXED_NEEDS_PASS 與補法；
    同一批條目裡的提醒類（(b) 說量了沒 DONE）不進擋訊息、只留帳。"""
    out, _, logs = drive("閘修好了，我量了，完成。", config={"reconcile_gate": {"enabled": True}}, modified_files=[_mf()])
    assert out.get("decision") == "block", drive.err
    assert "CLAIM_FIXED_NEEDS_PASS" in out["reason"] and "(a)" in out["reason"] and "收據" in out["reason"]
    assert "CLAIM_MEASURED_NEEDS_DONE" not in out["reason"], "同一批條目裡 (b) 是提醒，不進擋訊息"
    assert [p["rule"] for p in _reminds(logs, "reconcile")] == ["CLAIM_MEASURED_NEEDS_DONE"]


# ─── 改提醒：Stop 只留帳 ─────────────────────────────────────────────────────────

def test_measured_claim_reminded_not_blocked(drive):
    """S5 (b) 說量了要有 DONE：沒說修好、只有 (b) → 不擋；guard-reconcile 留 event=remind、規則 CLAIM_MEASURED_NEEDS_DONE。"""
    out, _, logs = drive("我量了，完成。", config={"reconcile_gate": {"enabled": True}}, modified_files=[_mf()])
    assert "decision" not in out, (out, drive.err)
    rem = _reminds(logs, "reconcile")
    assert rem and rem[0]["rule"] == "CLAIM_MEASURED_NEEDS_DONE"


def test_self_error_follows_rule_mode(drive, monkeypatch):
    """S9 寫碼查核自己出錯跟所屬條目：對帳（含 (a)）判定炸了照擋。"""
    monkeypatch.setattr(st, "reconcile_gate_parts", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom-a")))
    out, _, logs = drive(DONE, config={"reconcile_gate": {"enabled": True}}, modified_files=[_mf()])
    assert out.get("decision") == "block" and "GATE_SELF_ERROR" in out["reason"] and "boom-a" in out["reason"]


def test_equivalence_reminded_not_blocked(drive):
    """S12 等值證法：意圖 refactor、改了程式、宣告完成、沒收據 → 不擋；guard-equivalence 留 event=remind 兩條規則。"""
    out, state, logs = drive(DONE, turn_intent="refactor", modified_files=[_mf()], verify_receipts={SID: []})
    assert "decision" not in out, out
    rules = {p["rule"] for p in _reminds(logs, "equivalence")}
    assert rules == {"REFACTOR_NEEDS_EQUIVALENCE", "PERF_HOT_PATH_NEEDS_MEASURE"}, logs
    assert "budget" not in (state.get("equivalence_gate") or {}).get(SID, {}), "提醒不吃擋滿預算、不開放行題"


def test_deferral_logged_not_blocked_v6(drive):
    """S16 退縮歸屬（v6 以前就有）：v6 開 → 不擋、留帳 event=remind、一回合一次的記號照記、不吃共用擋次。"""
    out, state, logs = drive(DEFER_DONE, config={"deferral_gate": {"enabled": True}}, modified_files=[_mf()])
    assert "decision" not in out, out
    assert any(p["rule"] == "DEFERRAL_OF_DOABLE_WORK" for p in _reminds(logs, "deferral"))
    assert state["deferral_gate_turn"] == 5 and state["stop_blocked_count"] == 0


def test_v6_off_stop_gates_unchanged(drive, monkeypatch):
    """總開關關：退縮閘照擋、吃共用擋次（9e476fd0 原樣）；對帳閘本來就只在 v6 跑。"""
    monkeypatch.setenv("WG_V6", "0")
    out, state, _ = drive(DEFER_DONE, config={"deferral_gate": {"enabled": True}}, modified_files=[_mf()])
    assert out.get("decision") == "block" and "[Guardian:DeferralGate]" in out["reason"]
    assert state["stop_blocked_count"] == 1


def test_subagent_same_modes(monkeypatch, capsys):
    """S22 子代理收尾同一套：(b) 說量了沒 DONE 只留帳不擋；(a) 說修好沒 PASS 照擋。"""
    logs: list = []
    monkeypatch.setattr(st, "append_guard_log", lambda guard, payload: logs.append((guard, payload)))
    monkeypatch.setattr(st, "write_state", lambda *a, **k: None)
    cfg = {"reconcile_gate": {"enabled": True}}

    def run(text):
        state = {"turn_seq": 5, "turn_prompts_seq": 5, "modified_files": [],
                 "agent_modified_files": {"ag1": [_mf(sid=SID)]}}
        monkeypatch.setattr(st, "read_state", lambda *a, **k: state)
        logs.clear()
        capsys.readouterr()
        with pytest.raises(SystemExit):
            st.handle_subagent_stop({"session_id": SID, "agent_id": "ag1", "hook_event_name": "SubagentStop",
                                     "last_assistant_message": text}, cfg)
        return _payload(capsys.readouterr().out)

    out = run("我量了，完成。")
    assert "decision" not in out, out
    assert any(p["rule"] == "CLAIM_MEASURED_NEEDS_DONE" and p.get("agent_id") == "ag1" for p in _reminds(logs, "reconcile"))
    out = run("閘修好了，完成。")
    assert out.get("decision") == "block" and "CLAIM_FIXED_NEEDS_PASS" in out["reason"]


# ─── 提醒掛在改程式檔那則工具結果（PostToolBatch） ─────────────────────────────

def _batch(monkeypatch, capsys, state, calls, config, sid=SID):
    """跑一批 PostToolBatch。state 走真實形狀：remind_sent 是清單（實跑裡讀檔的定位提示 wg_overview.remind_mark 早就寫成清單；
    造 state 不給它，舊碼 setdefault 成 dict 就測不到「清單上 .setdefault 炸」那條路）。"""
    state.setdefault("remind_sent", [])
    monkeypatch.setattr(ptb, "_ensure_state", lambda *a, **k: state)
    monkeypatch.setattr(ptb, "write_state", lambda *a, **k: None)
    capsys.readouterr()
    with pytest.raises(SystemExit):
        ptb.handle_post_tool_batch({"session_id": sid, "tool_calls": calls, "cwd": r"c:\proj"}, config)
    got = capsys.readouterr()
    _batch.err = got.err          # 這批的 stderr（案例要看有沒有「算不出」那類吞錯訊號）
    out = got.out.strip()
    return json.loads(out.splitlines()[-1])["hookSpecificOutput"]["additionalContext"] if out else ""


# ─── 提醒帳本一份清單（state remind_sent；工具前守門 remind_flush 與這裡的 closing_reminders 同一份） ─────────

_SENT_CFG = {"reconcile_gate": OFF}


def _edit_batch(monkeypatch, capsys, state):
    return _batch(monkeypatch, capsys, state, [{"tool_name": "Edit", "tool_input": {"file_path": CODE}}], _SENT_CFG)


def test_remind_sent_list_from_locate_hint_does_not_crash_and_sends(monkeypatch, capsys):
    """實跑形狀：讀檔定位提示已把 remind_sent 寫成清單（元素 remind_key）→ 改程式那批照送提醒、不炸、stderr 沒有「算不出」；
    新鍵 append 進同一份清單（不另開第二種形狀）。"""
    sent = ["LOCATE_BEFORE_EDIT|銷售報表", "CODE_EDIT_NEEDS_GOAL_TREE|"]
    state = {"turn_seq": 5, "turn_prompts_seq": 5, "modified_files": [_mf(seq=3)], "remind_sent": list(sent)}
    ctx = _edit_batch(monkeypatch, capsys, state)
    assert "[Guardian:提醒] DEFERRAL_OF_DOABLE_WORK：" in ctx, ctx
    assert "收尾類提醒算不出" not in _batch.err, _batch.err
    assert isinstance(state["remind_sent"], list) and state["remind_sent"][:2] == sent
    assert rr.remind_key("DEFERRAL_OF_DOABLE_WORK") in state["remind_sent"]


def test_remind_sent_same_object_not_resent(monkeypatch, capsys):
    """同規則同對象本 session 只送一次：第一批送了、第二批（又改程式）同一份清單判成送過，一行都不重送。"""
    state = {"turn_seq": 5, "turn_prompts_seq": 5, "modified_files": [_mf(seq=3)], "remind_sent": []}
    first = _edit_batch(monkeypatch, capsys, state)
    assert "SYNC_REMINDER_UNSYNCED" in first, first
    n = len(state["remind_sent"])
    state["modified_files"][0]["last_seq"] = 7
    second = _edit_batch(monkeypatch, capsys, state)
    assert "[Guardian:提醒]" not in second, second
    assert len(state["remind_sent"]) == n


def test_remind_sent_legacy_dict_tolerated(monkeypatch, capsys):
    """舊寫法殘留 {sid: [鍵]}：不炸、攤平成清單；攤平後舊鍵仍算送過（同對象不重送），新提醒照送。"""
    legacy = {SID: [rr.remind_key("SYNC_REMINDER_UNSYNCED")], "other": [rr.remind_key("LOCATE_BEFORE_EDIT", "x")]}
    state = {"turn_seq": 5, "turn_prompts_seq": 5, "modified_files": [_mf(seq=3)], "remind_sent": legacy}
    ctx = _edit_batch(monkeypatch, capsys, state)
    assert "收尾類提醒算不出" not in _batch.err, _batch.err
    assert isinstance(state["remind_sent"], list), state["remind_sent"]
    assert "SYNC_REMINDER_UNSYNCED" not in ctx and "DEFERRAL_OF_DOABLE_WORK" in ctx, ctx
    assert {rr.remind_key("SYNC_REMINDER_UNSYNCED"), rr.remind_key("LOCATE_BEFORE_EDIT", "x")} <= set(state["remind_sent"])


# ─── 順手一併改的：拐彎判斷只重問改到的函式 ─────────────────────────────────────


# ─── 其餘改提醒的閘：Stop 只留帳（每個 S 項一案） ─────────────────────────────────

def test_harvest_and_pending_reminded_not_blocked(drive, monkeypatch):
    """S17 知識收割、收割對帳：欠就留帳，不擋；一回合一次的記號照記。"""
    monkeypatch.setattr(st, "harvest_gate_reason", lambda *a, **k: "[Guardian:KnowledgeHarvest] 階段完工要交收割清單")
    monkeypatch.setattr(st, "pending_gate_reason", lambda *a, **k: "[Guardian:Harvest-Pending] 1 項核不過")
    out, state, logs = drive(DONE, modified_files=[_mf()])
    assert "decision" not in out, out
    assert {p["rule"] for p in _reminds(logs)} >= {"HARVEST_AT_PHASE_DONE", "HARVEST_ITEM_NEEDS_RECEIPT"}
    assert state["harvest_gate_turn"][SID] == 5 and state["harvest_pending_gate_turn"][SID] == 5


def test_scanreport_aec_pending_reminded_not_blocked(drive):
    """S18 收尾檢核與報告待寫：都只留帳；one-shot／一回合一次的記號照記、不吃共用擋次。"""
    files = [_mf(), _mf(r"c:\proj\hooks\y.py", seq=11)]
    out, state, logs = drive(DONE, config={"aec": {"scan_report_gate": True}}, modified_files=files)
    assert "decision" not in out, out
    assert "CLOSING_CHECK_REQUIRED" in {p["rule"] for p in _reminds(logs)}
    assert state["scan_report_warned"] is True and state["stop_blocked_count"] == 0
    aec = {"turn_seq": 5, "session_id": SID, "at": "2026-10-27T11:00:00", "d_pending": ["x → 尚未寫"], "j_evidence_path": "無", "k_followups": "無"}
    out, state, logs = drive(DONE, modified_files=files, anti_evasion_report=aec)
    assert "decision" not in out, out
    assert any(p["rule"] == "CLOSING_CHECK_MEMORY_NOT_DEFERRED" for p in _reminds(logs, "aec_pending"))
    assert state["aec_pending_gate_turn"] == 5


def test_sync_reload_audit_dpm_reminded_not_blocked(drive, monkeypatch, tmp_path):
    """S14 Reload、S19 同步提醒、S20 取用稽核與深度檢討：只留帳，各自的一次性記號照記，不吃共用擋次。"""
    monkeypatch.setattr(st, "_detect_uncommitted_files", lambda mf: [CODE])
    monkeypatch.setattr(st, "_session_touched_mcp", lambda *a, **k: True)
    monkeypatch.setattr(st, "_mcp_load_facts", lambda *a, **k: ([], None))
    monkeypatch.setattr(st, "reload_advice_verdict", lambda *a, **k: rr.Verdict("RELOAD_ADVICE_ALREADY_LOADED", True, "都是最新", ("x",)))
    monkeypatch.setattr(st, "_audit_pointer_atom_consumption", lambda state: ("[Guardian:AtomAudit] 2 張沒回報", ["a1", "a2"]))
    monkeypatch.setattr(st, "_should_deep_postmortem", lambda *a, **k: True)
    monkeypatch.setattr(st, "_dpm_marker", lambda sid: tmp_path / "dpm" / f"{sid}.marker")
    out, state, logs = drive("改好了，全部完成。請 Reload Window。", config={"sync_reminder": {"enabled": True}, "atom_audit": {"enabled": True}},
                             modified_files=[_mf()])
    assert "decision" not in out, out
    rules = {p["rule"] for p in _reminds(logs)}
    assert {"SYNC_REMINDER_UNSYNCED", "RELOAD_ADVICE_ALREADY_LOADED", "ATOM_CONSUMPTION_AUDIT", "DEEP_POSTMORTEM_ON_FAILURE"} <= rules, rules
    assert state["sync_reminder_count"] == 1 and state["reload_advice_turn"] == 5 and state["atom_audit_prompted"] == ["a1", "a2"]
    assert state["deep_postmortem_done"] is True and (tmp_path / "dpm" / f"{SID}.marker").exists()
    assert state["stop_blocked_count"] == 0


def test_sync_block_pending_items_reminded_not_blocked(drive):
    """S19 底部一般同步擋（待記知識）：只留帳、記成提醒過（SYNC_BLOCK_NEW_ITEMS_ONLY）、phase 收成 done。"""
    files = [_mf(), _mf(r"c:\proj\hooks\y.py", seq=11)]
    out, state, logs = drive(DONE, modified_files=files, knowledge_queue=[{"content": "k1"}])
    assert "decision" not in out, out
    assert any(p["rule"] == "SYNC_BLOCK_PENDING_ITEMS" for p in _reminds(logs, "sync_block"))
    assert state["sync_block_shown"] and state["phase"] == "done" and state["stop_blocked_count"] == 0


def test_later_gates_preview_lists_only_block_gates(drive, monkeypatch):
    """BLOCK_LISTS_LATER_GATES 的預覽：照擋的紅測閘擋下時，後面判成提醒的閘（收尾檢核、同步…）不列進「還會擋」。"""
    monkeypatch.setattr(st, "harvest_gate_reason", lambda *a, **k: "[Guardian:KnowledgeHarvest] 要交收割")
    red = [{"session_id": SID, "cmd": "python -m pytest -q t", "summary": "1 failed", "turn_seq": 5}]
    files = [_mf(str(Path(r"c:\proj\hooks") / f"m{i}.py"), seq=10 + i) for i in range(5)]
    out, _, _ = drive(DONE, config={"aec": {"scan_report_gate": True}},
                      failing_tests=red, modified_files=files)
    assert out.get("decision") == "block" and "[Guardian:TestFailGate]" in out["reason"]
    assert "[Guardian:AlsoOwed]" not in out["reason"], out["reason"]


def test_closing_batch_reminds_harvest(monkeypatch, capsys):
    """S17 的提醒點：交收尾檢核那批附知識收割欠項（設定有 harvest 段照提；再一批不重送）。"""
    import wg_harvest
    monkeypatch.setattr(wg_harvest, "harvest_gate_reason", lambda *a, **k: "[Guardian:KnowledgeHarvest] 要交收割")
    monkeypatch.setattr(wg_harvest, "pending_gate_reason", lambda *a, **k: None)
    state = {"turn_seq": 5, "turn_prompts_seq": 5, "modified_files": []}
    aec = [{"tool_name": "mcp__workflow-guardian__anti_evasion_report", "tool_input": {"a": "無"}}]
    ctx = _batch(monkeypatch, capsys, state, aec, {"harvest": {"enabled": True}})
    assert "[Guardian:提醒] HARVEST_AT_PHASE_DONE" in ctx, ctx
    ctx2 = _batch(monkeypatch, capsys, state, [{"tool_name": "Read", "tool_input": {}}], {})
    assert "HARVEST_AT_PHASE_DONE" not in ctx2


def test_code_edit_batch_reminds_deferral_sync_closing_once(monkeypatch, capsys):
    """S16／S19／S18 的提醒點：第一次改程式檔那批各附一行（退縮歸屬、同步、收尾檢核門檻），再改不重送；v6 關一行都不送。"""
    files = [_mf(seq=3), _mf(r"c:\proj\hooks\y.py", seq=4)]
    state = {"turn_seq": 5, "turn_prompts_seq": 5, "modified_files": files}
    calls = [{"tool_name": "Edit", "tool_input": {"file_path": CODE}}]
    ctx = _batch(monkeypatch, capsys, state, calls, {"reconcile_gate": OFF})
    for rule in ("DEFERRAL_OF_DOABLE_WORK", "SYNC_REMINDER_UNSYNCED", "CLOSING_CHECK_REQUIRED"):
        assert f"[Guardian:提醒] {rule}：" in ctx, (rule, ctx)
    assert all(len(ln) <= rr.REMIND_LINE_CAP for ln in ctx.splitlines() if ln.startswith("[Guardian:提醒]"))
    state["modified_files"][0]["last_seq"] = 9
    assert "[Guardian:提醒]" not in _batch(monkeypatch, capsys, state, calls, {"reconcile_gate": OFF})
    monkeypatch.setenv("WG_V6", "0")
    fresh = {"turn_seq": 5, "turn_prompts_seq": 5, "modified_files": [_mf(seq=3)]}
    assert _batch(monkeypatch, capsys, fresh, calls, {"reconcile_gate": OFF}) == ""


def test_closing_call_knows_both():
    """規則 CLOSING_CALL_ALL_THREE：收尾檢核（一次交齊）與 knowledge_harvest_report 都是收尾那批；其他工具不是（handlers/post_tool_batch.closing_call）。"""
    from handlers import post_tool_batch as ptb
    assert ptb.closing_call("mcp__workflow-guardian__anti_evasion_report")
    assert ptb.closing_call("mcp__workflow-guardian__knowledge_harvest_report")
    assert not ptb.closing_call("Bash") and not ptb.closing_call("mcp__workflow-guardian__atom_write")

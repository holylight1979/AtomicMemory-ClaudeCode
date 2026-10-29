"""verify_gate_mode_stop.py：收尾守門改提醒（規則 GATE_MODE_TABLE／REMIND_ON_PRIOR_RESULT 在 Stop 與 PostToolBatch 的接法）。

做什麼：v6 開著時 Stop 只照擋三類（紅測閘、對帳 (a) 說修好要有 PASS、子代理同一套），其餘 v6 守門一律提醒：
  提醒掛在最後一次改程式檔那則工具結果（handlers/post_tool_batch），Stop 只留帳（guard log event=remind）、不擋、不續跑、
  不開放行題；總開關關時行為一字不變。另守兩件順手改的：(d) 欠案例不比改動先後；拐彎判斷只重問改到的函式。
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
import wg_reading_path as rph  # noqa: E402
import wg_verify_ledger as vl  # noqa: E402
import wg_verify_scope as vs  # noqa: E402
from handlers import post_tool_batch as ptb  # noqa: E402
from handlers import stop as st  # noqa: E402

SID = "sid-gatemode"
CODE = r"c:\proj\hooks\x.py"
DONE = "改好了，全部完成。"
DEFER_DONE = "改好了，全部完成。剩下的 verify 清理留給下個 session 處理。"
TJ_ITEM = {"kind": "函式", "name": "x.py::f", "nums": "拐彎 3", "fp": "abc", "keys": ["x.py::f"]}
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
                     ("_should_deep_postmortem", lambda *a, **k: False), ("reading_path_note", lambda *a, **k: ("", False)),
                     ("_record_pick", lambda *a, **k: None), ("_acceptance_regression_hint", lambda *a, **k: ""),
                     ("estimate_context_usage", lambda *a, **k: 0.3),
                     ("append_guard_log", lambda guard, payload: logs.append((guard, payload)))):
        monkeypatch.setattr(st, name, fn)
    monkeypatch.setattr(st.aec_ledger, "collect_at_completion", lambda *a, **k: None)
    monkeypatch.setattr(vl, "case_exists", lambda p: True, raising=False)
    monkeypatch.setattr(vl, "code_exists", lambda p: True, raising=False)
    monkeypatch.delenv("CLAUDE_COMPANION_JUDGE", raising=False)
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli")

    def run(text, config=None, hook=None, **extra):
        monkeypatch.setattr(st, "get_last_assistant_text", lambda *a, **k: text)
        monkeypatch.setattr(st, "get_current_turn_visible_text", lambda *a, **k: ("", {"turn_tool_names_all": []}))
        state = {"phase": "working", "modified_files": [], "failing_tests": [], "recent_user_prompts": [],
                 "stop_blocked_count": 0, "turn_seq": 5, "turn_prompts_seq": 5, **extra}
        monkeypatch.setattr(st, "_ensure_state", lambda *a, **k: state)
        cfg = {"reconcile_gate": OFF, "verify_scope": OFF, "aec": {"scan_report_gate": False}, "atom_audit": OFF,
               "sync_reminder": OFF, "deferral_gate": OFF, "pick_one": OFF, "second_opinion": {"auto": OFF},
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

def test_block_testfail_has_rule_and_fix(drive):
    """S2 紅測閘照擋：本 session 跑紅、宣告完成 → decision=block，訊息列失敗項與三條出路。"""
    red = [{"session_id": SID, "cmd": "python -m pytest -q hooks/verify/verify_x.py", "summary": "1 failed", "turn_seq": 5}]
    out, _, _ = drive(DONE, failing_tests=red)
    assert out.get("decision") == "block", drive.err
    assert "[Guardian:TestFailGate]" in out["reason"] and "(a)" in out["reason"] and "(b)" in out["reason"]


def test_block_claim_fixed_has_rule_and_fix(drive):
    """S3 對帳 (a) 照擋：說修好、沒有任何 PASS → decision=block，訊息有規則名 CLAIM_FIXED_NEEDS_PASS 與補法。"""
    out, _, logs = drive("閘修好了，完成。", config={"reconcile_gate": {"enabled": True}}, modified_files=[_mf()])
    assert out.get("decision") == "block", drive.err
    assert "CLAIM_FIXED_NEEDS_PASS" in out["reason"] and "(a)" in out["reason"] and "收據" in out["reason"]
    assert "CASE_COVERS_CHANGE" not in out["reason"], "同一批條目裡 (d) 是提醒，不進擋訊息"
    assert [p["rule"] for p in _reminds(logs, "reconcile")] == ["CASE_COVERS_CHANGE"]


# ─── 改提醒：Stop 只留帳 ─────────────────────────────────────────────────────────

def test_case_debt_reminded_not_blocked(drive):
    """S5 (d) 改了程式要有案例：沒說修好、只有欠案例 → 不擋；guard-reconcile 留 event=remind、規則 CASE_COVERS_CHANGE。"""
    out, _, logs = drive(DONE, config={"reconcile_gate": {"enabled": True}}, modified_files=[_mf()])
    assert "decision" not in out, (out, drive.err)
    rem = _reminds(logs, "reconcile")
    assert rem and rem[0]["rule"] == "CASE_COVERS_CHANGE" and "x.py" in rem[0]["excerpt"]


def test_self_error_follows_rule_mode(drive, monkeypatch):
    """S9 寫碼查核自己出錯跟所屬條目：對帳（含 (a)）判定炸了照擋；驗證範圍閘判定炸了只留帳。"""
    monkeypatch.setattr(st, "reconcile_gate_parts", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom-a")))
    out, _, logs = drive(DONE, config={"reconcile_gate": {"enabled": True}}, modified_files=[_mf()])
    assert out.get("decision") == "block" and "GATE_SELF_ERROR" in out["reason"] and "boom-a" in out["reason"]
    monkeypatch.setattr(st, "reconcile_gate_parts", lambda *a, **k: (None, None))
    monkeypatch.setattr(vs, "gate_reason", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom-s")))
    out, _, logs = drive(DONE, config={"reconcile_gate": {"enabled": True}, "verify_scope": {"enabled": True}},
                         modified_files=[_mf()])
    assert "decision" not in out, out
    assert any(p["rule"] == "GATE_SELF_ERROR" and "boom-s" in p["excerpt"] for p in _reminds(logs, "reconcile"))


def test_turn_judgment_reminded_not_blocked(drive):
    """S10 拐彎判斷：背景量完的欠項、收尾沒寫五欄行 → 不擋；guard-reading_path 留 event=remind。"""
    rp = {SID: {"owed": {"items": [TJ_ITEM], "turn": 5}}}
    out, state, logs = drive(DONE, reading_path=rp, modified_files=[_mf()])
    assert "decision" not in out, out
    assert any(p["rule"] == "TURN_JUDGMENT_REQUIRED" for p in _reminds(logs, "reading_path"))
    assert state["reading_path"][SID]["blocked_turn"] == 5, "一回合一次的記號照記"


def test_equivalence_reminded_not_blocked(drive):
    """S12 等值證法：意圖 refactor、改了程式、宣告完成、沒收據 → 不擋；guard-equivalence 留 event=remind 兩條規則。"""
    out, state, logs = drive(DONE, turn_intent="refactor", modified_files=[_mf()], verify_receipts={SID: []})
    assert "decision" not in out, out
    rules = {p["rule"] for p in _reminds(logs, "equivalence")}
    assert rules == {"REFACTOR_NEEDS_EQUIVALENCE", "PERF_HOT_PATH_NEEDS_MEASURE"}, logs
    assert "budget" not in (state.get("equivalence_gate") or {}).get(SID, {}), "提醒不吃擋滿預算、不開放行題"


def test_remind_path_zero_stop_continuation(drive, monkeypatch):
    """S15 最該修：v6 開著 Stop 不續跑：該問的那一問只留帳（event=remind），不送 additionalContext；收尾前那批（PICK_ONE_PRE_CLOSE）照送。"""
    monkeypatch.setattr(st, "_pick_one_prompt", lambda *a, **k: "[Guardian:PickOne] 順手看到最該修：…")
    out, _, logs = drive(DONE, config={"pick_one": {"enabled": True}}, modified_files=[_mf()])
    assert out == {}, out
    assert any(p["rule"] == "PICK_ONE_PRE_CLOSE" for p in _reminds(logs, "pick_one"))


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
    """S22 子代理收尾同一套：(d) 欠案例只留帳不擋；(a) 說修好沒 PASS 照擋。"""
    logs: list = []
    monkeypatch.setattr(st, "append_guard_log", lambda guard, payload: logs.append((guard, payload)))
    monkeypatch.setattr(st, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(vl, "case_exists", lambda p: True, raising=False)
    monkeypatch.setattr(vl, "code_exists", lambda p: True, raising=False)
    cfg = {"reconcile_gate": {"enabled": True}, "verify_scope": OFF}

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

    out = run(DONE)
    assert "decision" not in out, out
    assert any(p["rule"] == "CASE_COVERS_CHANGE" and p.get("agent_id") == "ag1" for p in _reminds(logs, "reconcile"))
    out = run("閘修好了，完成。")
    assert out.get("decision") == "block" and "CLAIM_FIXED_NEEDS_PASS" in out["reason"]
    assert "CASE_COVERS_CHANGE" not in out["reason"]


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


def test_cleanup_reminded_at_create(monkeypatch, capsys, tmp_path):
    """S13 收尾自清：建工作樹那則 Bash 的工具結果附一行 LEFTOVER_NEEDS_CLEANUP（含是什麼、做法）；同一樣東西只提醒一次。"""
    import handlers.aec_ledger as al
    monkeypatch.setattr(al, "parse_git_artifacts", lambda cmd, cwd: [{"path": str(tmp_path / "wt"), "kind": "worktree"}])
    monkeypatch.setattr(al, "cleanup_facts", lambda sid: [{"kind": "worktree", "path": str(tmp_path / "wt"), "alive": True}])
    monkeypatch.setattr(rr, "leftover_candidates", lambda items: [{"title": "工作樹 wt", "label": "還在"}])
    state = {"turn_seq": 5, "turn_prompts_seq": 5, "modified_files": []}
    calls = [{"tool_name": "Bash", "tool_input": {"command": "git worktree add ../wt -b feat"}}]
    ctx = _batch(monkeypatch, capsys, state, calls, {})
    line = next((ln for ln in ctx.splitlines() if "LEFTOVER_NEEDS_CLEANUP" in ln), "")
    assert line.startswith("[Guardian:提醒]") and "工作樹 wt" in line and "做法：" in line, ctx
    assert _batch(monkeypatch, capsys, state, calls, {}) == "" or "LEFTOVER_NEEDS_CLEANUP" not in _batch(
        monkeypatch, capsys, state, calls, {}), "同一樣東西同一個 session 只提醒一次"


def test_code_edit_batch_reminds_case_debt_once_per_file(monkeypatch, capsys):
    """S5 的提醒點：改了程式檔那批的工具結果附一行 (d) 欠案例（每個檔一次），再改同一個檔不重送。"""
    monkeypatch.setattr(vl, "case_exists", lambda p: True, raising=False)
    monkeypatch.setattr(vl, "code_exists", lambda p: True, raising=False)
    monkeypatch.setattr(vl, "file_root_of", lambda p: r"c:\proj", raising=False)
    state = {"turn_seq": 5, "turn_prompts_seq": 5, "modified_files": [_mf(seq=3)]}
    calls = [{"tool_name": "Edit", "tool_input": {"file_path": CODE}}]
    ctx = _batch(monkeypatch, capsys, state, calls, {"reconcile_gate": {"enabled": True}, "verify_scope": OFF})
    line = next((ln for ln in ctx.splitlines() if "CASE_COVERS_CHANGE" in ln), "")
    assert line.startswith("[Guardian:提醒] CASE_COVERS_CHANGE") and "x.py" in line and "做法：" in line, ctx
    state["modified_files"][0]["last_seq"] = 4
    ctx2 = _batch(monkeypatch, capsys, state, calls, {"reconcile_gate": {"enabled": True}, "verify_scope": OFF})
    assert "CASE_COVERS_CHANGE" not in ctx2


# ─── 提醒帳本一份清單（state remind_sent；工具前守門 remind_flush 與這裡的 closing_reminders 同一份） ─────────

_SENT_CFG = {"reconcile_gate": OFF, "verify_scope": OFF}


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


# ─── 順手一併改的兩件 ─────────────────────────────────────────────────────────

def test_case_debt_covered_not_by_time_order(monkeypatch, tmp_path):
    """第 3 列：程式檔比案例檔晚改（last_seq 大）、案例檔內容提到它 → 不欠；只比有沒有覆蓋，不比先後。"""
    root = tmp_path / "proj"
    (root / "hooks" / "verify").mkdir(parents=True)
    code = root / "hooks" / "x.py"
    case = root / "hooks" / "verify" / "verify_x.py"
    code.write_text("def f():\n    return 1\n", encoding="utf-8")
    case.write_text("from hooks import x\n", encoding="utf-8")
    monkeypatch.setattr(vl, "gitignored_paths", lambda r, ps: set(), raising=False)
    mods = [_mf(str(case), seq=1), _mf(str(code), seq=9)]            # 案例先改、程式後改
    owed = vl.case_debt(mods, 5, vl.reconcile_cfg({}), lambda p: str(root))
    assert owed == [], owed
    code2 = root / "hooks" / "y.py"
    code2.write_text("z = 1\n", encoding="utf-8")
    owed = vl.case_debt(mods + [_mf(str(code2), seq=10)], 5, vl.reconcile_cfg({}), lambda p: str(root))
    assert [Path(p).name for p in owed] == ["y.py"], "沒被任何案例提到的照欠"


def test_turn_judgment_asks_only_changed_functions(tmp_path):
    """第 12 列：背景量完的一批裡，已判過且內容指紋沒變的函式不再問，只問改到（指紋變了）或新到門檻的。"""
    out = tmp_path / "r.result.json"
    job = tmp_path / "r.job.json"
    job.write_text("{}", encoding="utf-8")
    res = {"text": "[Guardian:ReadingPath] 第 5 回合", "judgment": [
        {**TJ_ITEM, "name": "x.py::same", "fp": "fp-same"},
        {**TJ_ITEM, "name": "x.py::changed", "fp": "fp-new"},
    ], "turn_judgment": {"turns": 2, "nesting": 3, "bumpy": 3, "handoff_chain": 3, "inherit_depth": 3, "max_items": 5}}
    out.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    rec = {"job": {"path": str(job), "out": str(out), "at": 0, "budget": 60, "turn": 5},
           "judged": [["x.py::same", "fp-same"], ["x.py::changed", "fp-old"]]}
    text = rph._collect(rec)
    assert [it["name"] for it in rec["owed"]["items"]] == ["x.py::changed"]
    assert "已判過、內容沒變的 1 條不再問" in text


# ─── 其餘改提醒的閘：Stop 只留帳（每個 S 項一案） ─────────────────────────────────

def test_second_opinion_reminded_not_blocked(drive, monkeypatch, tmp_path):
    """S11 第二意見事實成立（5 個程式檔）、收尾沒跑也沒宣告 → 不擋、不記 pending；guard-second_opinion 留 event=remind。"""
    files = [_mf(str(tmp_path / "proj" / f"m{i}.py"), seq=10 + i) for i in range(5)]
    out, state, logs = drive(DONE, config={"second_opinion": {"auto": {"enabled": True}}}, modified_files=files)
    assert "decision" not in out, out
    rem = _reminds(logs, "second_opinion")
    assert rem and rem[0]["rule"] == "SECOND_OPINION_REQUIRED" and rem[0]["code_files"] == 5
    assert not (state.get("pending_release") or {}).get(SID) and "second_opinion_gate_turn" not in state


def test_harvest_and_pending_reminded_not_blocked(drive, monkeypatch):
    """S17 知識收割、收割對帳：欠就留帳，不擋；一回合一次的記號照記。"""
    monkeypatch.setattr(st, "harvest_gate_reason", lambda *a, **k: "[Guardian:KnowledgeHarvest] 階段完工要交收割清單")
    monkeypatch.setattr(st, "pending_gate_reason", lambda *a, **k: "[Guardian:Harvest-Pending] 1 項核不過")
    out, state, logs = drive(DONE, modified_files=[_mf()])
    assert "decision" not in out, out
    assert {p["rule"] for p in _reminds(logs)} >= {"HARVEST_AT_PHASE_DONE", "HARVEST_ITEM_NEEDS_RECEIPT"}
    assert state["harvest_gate_turn"][SID] == 5 and state["harvest_pending_gate_turn"][SID] == 5


def test_cleanup_scanreport_aec_pending_reminded_not_blocked(drive, monkeypatch):
    """S13 收尾自清、S18 收尾檢核與報告待寫：都只留帳；one-shot／一回合一次的記號照記、不吃共用擋次。"""
    monkeypatch.setattr(st, "leftover_cleanup_verdict", lambda *a, **k: rr.Verdict("LEFTOVER_NEEDS_CLEANUP", True, "1 樣還在", ("wt",)))
    monkeypatch.setattr(st.aec_ledger, "ledger_path", lambda sid: Path(__file__))
    monkeypatch.setattr(st.aec_ledger, "cleanup_facts", lambda sid: [{"kind": "worktree"}])
    files = [_mf(), _mf(r"c:\proj\hooks\y.py", seq=11)]
    out, state, logs = drive(DONE, config={"aec": {"scan_report_gate": True}}, modified_files=files)
    assert "decision" not in out, out
    rules = {p["rule"] for p in _reminds(logs)}
    assert {"LEFTOVER_NEEDS_CLEANUP", "CLOSING_CHECK_REQUIRED"} <= rules, rules
    assert state["cleanup_gate_turn"][SID] == 5 and state["scan_report_warned"] is True and state["stop_blocked_count"] == 0
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
    """BLOCK_LISTS_LATER_GATES 的預覽：照擋的紅測閘擋下時，後面判成提醒的閘（第二意見、收尾檢核、同步…）不列進「還會擋」。"""
    monkeypatch.setattr(st, "harvest_gate_reason", lambda *a, **k: "[Guardian:KnowledgeHarvest] 要交收割")
    red = [{"session_id": SID, "cmd": "python -m pytest -q t", "summary": "1 failed", "turn_seq": 5}]
    files = [_mf(str(Path(r"c:\proj\hooks") / f"m{i}.py"), seq=10 + i) for i in range(5)]
    out, _, _ = drive(DONE, config={"aec": {"scan_report_gate": True}, "second_opinion": {"auto": {"enabled": True}}},
                      failing_tests=red, modified_files=files)
    assert out.get("decision") == "block" and "[Guardian:TestFailGate]" in out["reason"]
    assert "[Guardian:AlsoOwed]" not in out["reason"], out["reason"]


def test_closing_batch_reminds_harvest_and_turn_judgment(monkeypatch, capsys):
    """S17／S10 的提醒點：交收尾檢核那批附知識收割欠項；背景量完的欠項在之後第一批附一次（再一批不重送）。"""
    import wg_harvest
    monkeypatch.setattr(wg_harvest, "harvest_gate_reason", lambda *a, **k: "[Guardian:KnowledgeHarvest] 要交收割")
    monkeypatch.setattr(wg_harvest, "pending_gate_reason", lambda *a, **k: None)
    state = {"turn_seq": 5, "turn_prompts_seq": 5, "modified_files": [],
             "reading_path": {SID: {"owed": {"items": [TJ_ITEM], "turn": 5, "at": 1.0}}}}
    aec = [{"tool_name": "mcp__workflow-guardian__anti_evasion_report", "tool_input": {"a": "無"}}]
    ctx = _batch(monkeypatch, capsys, state, aec, {})
    assert "[Guardian:提醒] HARVEST_AT_PHASE_DONE" in ctx and "[Guardian:提醒] TURN_JUDGMENT_REQUIRED" in ctx and "x.py::f" in ctx, ctx
    ctx2 = _batch(monkeypatch, capsys, state, [{"tool_name": "Read", "tool_input": {}}], {})
    assert "TURN_JUDGMENT_REQUIRED" not in ctx2 and "HARVEST_AT_PHASE_DONE" not in ctx2


def test_code_edit_batch_reminds_deferral_sync_closing_once(monkeypatch, capsys):
    """S16／S19／S18 的提醒點：第一次改程式檔那批各附一行（退縮歸屬、同步、收尾檢核門檻），再改不重送；v6 關一行都不送。"""
    monkeypatch.setattr(vl, "case_exists", lambda p: True, raising=False)
    monkeypatch.setattr(vl, "code_exists", lambda p: True, raising=False)
    files = [_mf(seq=3), _mf(r"c:\proj\hooks\y.py", seq=4)]
    state = {"turn_seq": 5, "turn_prompts_seq": 5, "modified_files": files}
    calls = [{"tool_name": "Edit", "tool_input": {"file_path": CODE}}]
    ctx = _batch(monkeypatch, capsys, state, calls, {"reconcile_gate": OFF, "verify_scope": OFF})
    for rule in ("DEFERRAL_OF_DOABLE_WORK", "SYNC_REMINDER_UNSYNCED", "CLOSING_CHECK_REQUIRED"):
        assert f"[Guardian:提醒] {rule}：" in ctx, (rule, ctx)
    assert all(len(ln) <= rr.REMIND_LINE_CAP for ln in ctx.splitlines() if ln.startswith("[Guardian:提醒]"))
    state["modified_files"][0]["last_seq"] = 9
    assert "[Guardian:提醒]" not in _batch(monkeypatch, capsys, state, calls, {"reconcile_gate": OFF, "verify_scope": OFF})
    monkeypatch.setenv("WG_V6", "0")
    fresh = {"turn_seq": 5, "turn_prompts_seq": 5, "modified_files": [_mf(seq=3)]}
    assert _batch(monkeypatch, capsys, fresh, calls, {"reconcile_gate": OFF, "verify_scope": OFF}) == ""


def test_reminders_ask_judgment_cards_once_per_batch(monkeypatch, capsys):
    """提醒也是切入點（011 重驗：第二意見提醒送到 4 次卻沒附卡，AI 走「不需」出口）：這批的提醒行整批問一次判準卡、
    路是 post_tool_hint、卡接在提醒後面；沒卡就不多一行。"""
    import wg_entrypoint as ep
    monkeypatch.setattr(vl, "case_exists", lambda p: True, raising=False)
    monkeypatch.setattr(vl, "code_exists", lambda p: True, raising=False)
    asked: list = []

    def fake_note(text, path, **kw):
        asked.append((text, path))
        return "判準卡（E16）：第二意見分歧裁決" if "DEFERRAL_OF_DOABLE_WORK" in text else ""
    monkeypatch.setattr(ep, "entry_note", fake_note)
    state = {"turn_seq": 5, "turn_prompts_seq": 5, "modified_files": [_mf(seq=3)]}
    calls = [{"tool_name": "Edit", "tool_input": {"file_path": CODE}}]
    ctx = _batch(monkeypatch, capsys, state, calls, {"reconcile_gate": OFF, "verify_scope": OFF})
    assert len(asked) == 1 and asked[0][1] == "post_tool_hint" and "[Guardian:提醒]" in asked[0][0], asked
    assert ctx.rstrip().endswith("判準卡（E16）：第二意見分歧裁決"), ctx
    reg = json.loads((HOOKS_DIR.parent / "workflow" / "entrypoints.json").read_text(encoding="utf-8"))
    rows = {r["id"]: r for r in reg["entrypoints"]}
    for eid in ("E03", "E13", "E14", "E15", "E16"):
        assert "post_tool_hint" in rows[eid]["paths"], eid


def test_case_for_line_is_a_case_declaration(monkeypatch, capsys):
    """011 重驗 C′：AI 在 # 註解裡寫「case_for｜receipt.py：test_cli.py::test_x」說明哪支案例驗它，閘以前只收 need_goal 的宣告。
    現在三管道的這一行都算 case_for：對得到的程式檔不再提醒欠案例；對不到的照提醒。"""
    import overview_hub as oh
    monkeypatch.setattr(vl, "case_exists", lambda p: True, raising=False)
    monkeypatch.setattr(vl, "code_exists", lambda p: True, raising=False)
    monkeypatch.setattr(vl, "file_root_of", lambda p: r"c:\proj", raising=False)
    monkeypatch.setattr(vl, "_case_text", lambda p: "", raising=False)
    monkeypatch.setattr(oh, "assistant_text_after", lambda tp, off, ch="text":
                        "# case_for｜hooks/x.py：tests/test_other.py::test_a（整張收據）\ngit diff --stat" if ch == "tool_input" else "")
    assert rr.parse_case_for_decls("case_for｜a.py：t/test_b.py::test_1、t/test_c.py\n# case_for | b.py: x") == \
        [("a.py", ["t/test_b.py", "t/test_c.py"]), ("b.py", ["x"])]
    files = [_mf(seq=3), _mf(r"c:\proj\tests\test_other.py", seq=4)]
    calls = [{"tool_name": "Edit", "tool_input": {"file_path": CODE}}]
    cfg = {"reconcile_gate": {"enabled": True}, "verify_scope": OFF}
    state = {"turn_seq": 5, "turn_prompts_seq": 5, "modified_files": [dict(f) for f in files], "remind_sent": []}
    monkeypatch.setattr(ptb, "_ensure_state", lambda *a, **k: state)
    monkeypatch.setattr(ptb, "write_state", lambda *a, **k: None)
    with pytest.raises(SystemExit):
        ptb.handle_post_tool_batch({"session_id": SID, "tool_calls": calls, "cwd": r"c:\proj", "transcript_path": "x.jsonl"}, cfg)
    assert "CASE_COVERS_CHANGE" not in capsys.readouterr().out, "寫了 case_for 行：不欠"
    state2 = {"turn_seq": 5, "turn_prompts_seq": 5, "modified_files": [dict(f) for f in files]}
    ctx = _batch(monkeypatch, capsys, state2, calls, cfg)          # 沒給 transcript：讀不到那行，照提醒
    assert "CASE_COVERS_CHANGE" in ctx and "case_for｜" in ctx, ctx


def test_waived_red_tests_count_as_delivery_boundary():
    """011 重驗 C′：使用者叫跳過的那支永遠紅，「順手看到最該修」只認全綠永遠到不了。還紅的每一支都在豁免帳上 → 這批算到交付邊界；
    有一支不在帳上、或帳是空的 → 不算。"""
    red = {"seq": 1, "cmd": "python -m pytest -q tests", "exit_code": 1, "sentinels": []}
    base = {"failing_tests": [{"session_id": SID, "summary": "FAILED tests/test_erp.py::test_contract", "pytest": True}]}
    state = {**base, "verify_receipts": {SID: [red]}, "testfail_waivers": [{"item": "test_contract", "units": ["tests/test_erp.py::test_contract"]}]}
    assert ptb._test_green_batch(state, SID) == (True, True)
    state = {**base, "verify_receipts": {SID: [red]}}
    assert ptb._test_green_batch(state, SID) == (False, True)
    two = {"session_id": SID, "summary": "FAILED tests/test_erp.py::test_contract\nFAILED tests/test_a.py::test_b", "pytest": True}
    state = {"failing_tests": [two], "verify_receipts": {SID: [red]}, "testfail_waivers": [{"units": ["tests/test_erp.py::test_contract"]}]}
    assert ptb._test_green_batch(state, SID) == (False, True)
    state = {"failing_tests": [], "verify_receipts": {SID: [dict(red, exit_code=0)]}}
    assert ptb._test_green_batch(state, SID) == (True, True)

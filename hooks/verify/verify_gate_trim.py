"""verify_gate_trim.py — 關卡盤點的裁定（降成只記錄、拿掉、只問一次、只在寫碼回合啟動、開發期規矩不進產品）的行為案例。

做什麼：每道關卡一段，驗拿掉或降級的那一步真的不再擋／不再送（舊碼跑是紅的），同時驗保留的判斷入口還在。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_gate_trim.py
       python -X utf8 hooks/verify/verify_gate_trim.py   （直接跑，尾行 GATE_TRIM_CHECK PASS／FAIL）
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
ROOT = HOOKS_DIR.parent
sys.path.insert(0, str(HOOKS_DIR))

import wg_core  # noqa: E402
import wg_release_rules as rr  # noqa: E402


@pytest.fixture()
def ng_env(tmp_path, monkeypatch):
    """tmp 資料根的目標檔；回 (ng, op, receipt, edit, logs)。"""
    import wg_need_goal as ng
    logs = []
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", tmp_path / "wf")
    monkeypatch.setattr(wg_core, "append_guard_log", lambda name, rec: logs.append((name, rec)))
    proj = tmp_path / "proj"
    proj.mkdir()

    def op(action, turn=1, **kw):
        return ng.apply_op("s", turn, {"action": action, **kw}, str(proj))

    def receipt(green=True):
        def fn(doc):
            seq = ng.next_seq(doc)
            doc.setdefault("receipts", []).append({"seq": seq, "cmd": "pytest tests", "cases": [],
                                                   "verdicts": [f"pytest:{'PASS' if green else 'FAIL'}"],
                                                   "exit": 0 if green else 1, "turn": 1})
            return seq
        return ng.update_locked("s", fn)

    def edit(name="a.py"):
        ng.stamp_edit("s", str(proj / name), "", 1, {})
    return ng, op, receipt, edit, logs


# ─── 交出前先對原話（拿掉） ─────────────────────────────────────

def test_handout_check_removed_everywhere(ng_env):
    """每則訊息、完整對照收下、改計畫類文件、收尾檢核收下都不再送「交出前先對原話」。"""
    ng, op, receipt, edit, _ = ng_env
    import wg_need_goal_points as ngp
    assert not hasattr(ng, "HANDOUT_CHECK") and not hasattr(ng, "handout_check_text")
    assert not hasattr(ngp, "handout_edit_line")
    op("set", goal="改 a")
    line = ng.on_prompt("s", "再改一下", 2, {}, cwd="")
    assert "交出計畫" not in str(line)
    r = op("reconcile", items=[{"id": "T1", "status": "none", "followup": "下次"}])
    assert "交出計畫" not in r["text"]


# ─── 完整對照降成只記錄（程式照收據代填） ───────────────────────────

def test_reconcile_filled_by_program_when_gate_off(ng_env):
    """閘關著（goal_gate=false）時交付邊界由程式代填：改動之後有綠收據 → 達成；沒有 → 部分＋followup 等 AI 補（舊碼不代填 → 紅）。"""
    ng, op, receipt, edit, _ = ng_env
    op("set", goal="改 a 跟 b", items=[{"text": "a 改好"}, {"text": "b 改好"}])
    ng.update_locked("s", lambda d: d["trees"]["T1"].setdefault("kind", "code"))
    edit("a.py")
    receipt(True)
    assert ng.goal_gate_reason("s", True, {"reconcile_gate": {"goal_gate": False}}) is None
    tree = ng.active_tree(ng.load("s"))
    assert tree["last_reconcile"]["by"] == "program"
    assert tree["nodes"]["T1"]["status"] == "done" and tree["nodes"]["T1"]["evidence"][0]["by"] == "program"
    edit("b.py")                                   # 改了又沒重跑：下一次代填標部分、等 AI 補 followup
    ng.goal_gate_reason("s", True, {"reconcile_gate": {"goal_gate": False}})
    node = ng.active_tree(ng.load("s"))["nodes"]["T1"]
    assert node["status"] == "partial" and node["followup"] == ng.AUTO_FOLLOWUP


def test_program_fill_does_not_override_ai_reconcile(ng_env):
    """反例：AI 自己交了「部分」與 followup，之後程式代填不蓋它。"""
    ng, op, receipt, edit, _ = ng_env
    op("set", goal="改 a")
    ng.update_locked("s", lambda d: d["trees"]["T1"].setdefault("kind", "code"))
    edit("a.py")
    receipt(True)
    r = op("reconcile", items=[{"id": "T1", "status": "partial", "followup": "等使用者給格式",
                                "evidence": [{"kind": "receipt", "ref": "latest", "level": "measured"}]}])
    assert r["ok"], r.get("rejected")
    edit("a.py")
    receipt(True)
    ng.goal_gate_reason("s", True, {"reconcile_gate": {"goal_gate": False}})
    node = ng.active_tree(ng.load("s"))["nodes"]["T1"]
    assert node["status"] == "partial" and node["followup"] == "等使用者給格式"


def test_reconcile_description_no_longer_demands_it():
    js = (ROOT / "tools" / "workflow-guardian-mcp" / "lib" / "mcp.js").read_text(encoding="utf-8")
    assert "宣告完成、交收尾檢核、commit 前要有完整對照" not in js and "交付時程式照收據代填" in js


# ─── 收據防偽造（拿掉） ──────────────────────────────────────────

def test_receipt_shape_no_longer_disqualifies():
    """指令裡自己 echo 哨兵、管線、換目錄都照算收據（舊碼這些都不算 → 紅）；量的不是這棵樹、環境縮範圍照舊不算。"""
    import wg_verify_ledger as vl
    base = {"turn_seq": 4, "tool": "Bash", "exit_code": 0, "cwd": "c:/proj", "project_root": "c:/proj", "env": {},
            "cmd_full": True, "sentinels": [{"name": "X_CHECK", "verdict": "PASS"}]}
    for cmd in ("echo X_CHECK PASS", "python -m pytest -q tests | grep x", "cd c:/proj; python -m pytest -q tests"):
        assert vl._clean({**base, "cmd": cmd}), cmd
    assert not vl._clean({**base, "cmd": "PYTEST_ADDOPTS='-k x' python -m pytest -q tests"})


def test_verify_ledger_dir_writable():
    from handlers import pre_tool_use as pt
    assert not hasattr(pt, "check_verify_ledger_write")


# ─── 定位：兩候選保留判斷、一回合問一次；第四行節點只記錄 ──────────────

def test_two_candidates_asked_once_goal_node_only_logged(monkeypatch):
    import wg_need_goal as ng
    import wg_overview as wo
    monkeypatch.setattr(ng, "_guard", lambda *a, **k: None)
    tree = {"id": "T1", "nodes": {"T1": {"text": "列出產品", "status": "doing"}}}
    good = "合理，因為這段只做一件事；同類還可能在哪：無，因為只有這一處"
    state = {"turn_seq": 3, "turn_prompts_seq": 3}
    node, owed = wo._goal_line_check(tree, {"根因": "在 cli 層", "批判": good}, "s", state)
    assert node == "T1" and owed and owed[0].rule == "LOCATE_LINES_NEED_ROLE_AND_TWO_CANDIDATES"     # 沒第四行：掛樹根、兩候選照問
    assert wo._goal_line_check(tree, {"根因": "在 cli 層", "批判": good}, "s", state)[1] is None    # 同一回合第二次：只記
    assert wo._goal_line_check(tree, {"根因": "候選 A cli；候選 B report；選 A 因為入口在 cli", "批判": "x"}, "s", state)[1]  # 批判照擋


# ─── 收尾問一句；拿掉逐件引原句 ────────────────────────────────

def test_deferral_gate_asks_one_question():
    import wg_evasion as ev
    msg = ev.deferral_gate_reason("全部完成了。剩下的 README 補充留給下個 session 再做吧。", [], turn_seq=3, gated_turn=None,
                                  committed_this_turn=False, context_ratio=0.1, config={}, claimed=True)
    assert msg and "剩下沒做的，哪些改得快又有效？" in msg and "USER_WAIVER_NEEDS_CITATION" not in msg


def test_tracking_line_and_uncited_waiver_accepted():
    """「追蹤｜…」行算宣告；「不做｜X：使用者說「…」」不再核引用（舊碼要引到原話 → 紅）。"""
    line = "README 補充留給下個 session"
    v = rr.not_doing_verdict(line, rr.parse_not_doing("追蹤｜README 補充：要先問格式"), [])
    assert not v.owed
    v = rr.not_doing_verdict(line, rr.parse_not_doing("不做｜README 補充：使用者說「先不用」"), ["別的話"])
    assert not v.owed


def test_dismiss_skips_harvest_and_closing_check_wholesale(monkeypatch):
    """使用者近 3 則說「先這樣」→ 收割閘、收割待補、收尾檢核整件放行並留帳（舊碼要逐件引原句 → 紅）。"""
    import wg_evasion as ev
    import wg_harvest as hv
    assert ev.closing_check_waiver("全部完成", ["先這樣就好"])["item"] == ev.CLOSING_CHECK_ITEM
    state = {"recent_user_prompts": ["先這樣就好"], "knowledge_harvest": {"s": {"pending": ["card-a: 對不上"]}}}
    monkeypatch.setattr(hv, "section", lambda st, sid: st["knowledge_harvest"][sid])
    waived = []
    assert hv.pending_gate_reason(state, "s", 4, "全部完成", waived=waived) is None and waived


def test_tracking_lines_recorded(monkeypatch):
    from handlers import stop as st
    import wg_harvest
    got = []
    monkeypatch.setattr(wg_harvest, "append_tracking", lambda slug, entries: got.append(entries))
    st._record_tracking_lines("做完了。\n追蹤｜README 補充：要先問格式\n", "s", 4, "")
    assert got and "README 補充" in json.dumps(got, ensure_ascii=False)


# ─── 定位不重抄、評分不注入、提問不掛節點、未知寫入、改判準卡、子代理預算 ─────────────────────────────────────

def test_locate_lines_not_duplicated_into_tool_args():
    src = (ROOT / "lib" / "overview_hub.py").read_text(encoding="utf-8")
    assert "保險做法" not in src


def test_text_score_tail_not_injected(monkeypatch):
    import wg_text_score as wts
    monkeypatch.setattr(wts, "find_record", lambda sid, sha: {"summary": "評分 5/7", "spec": "reader-designer"})
    logs = []
    monkeypatch.setattr(wts, "append_guard_log", lambda name, rec: logs.append(rec))
    state = {"turn_seq": 3, "text_score": {"s": {"reply": {"sha": "abc", "turn": 3}}}}
    assert wts.tail_note(state, "s", {"text_score": {"enabled": True}}) == ""
    assert logs and logs[-1]["event"] == "recorded"


def test_ask_unlinked_to_goal_not_blocked(monkeypatch):
    import wg_need_goal as ng
    import wg_need_goal_points as ngp
    monkeypatch.setattr(ng, "load", lambda sid: {"active": "T1", "trees": {"T1": {"id": "T1", "kind": "code", "status": "doing",
                                                 "nodes": {"T1": {"text": "改 a", "status": "doing", "parent": None}}}}})
    monkeypatch.setattr(ngp, "_guard", lambda *a, **k: None)
    deny, hint = ngp.on_ask("s", "AskUserQuestion", {"questions": [{"question": "要用哪個資料庫？", "options": [
        {"label": "SQLite (Recommended)", "description": "x"}, {"label": "PG", "description": "y"}]}]}, {"turn_seq": 2})
    assert deny is None


def test_unknown_write_target_allowed_and_logged(monkeypatch):
    import wg_overview as wo
    logs = []
    monkeypatch.setattr(wo, "_log", lambda event, sid, **kw: logs.append((event, kw)))
    out = wo.on_edit({}, "s", "UNKNOWN:echo x > $P", "", {})
    assert out[0] is None and logs[-1][0] == "edit_unknown_target" and logs[-1][1]["allowed"] is True


def test_judge_card_change_logged_not_blocked(monkeypatch):
    import wg_judge_card as jc
    logs = []
    monkeypatch.setattr(jc, "bound_cards", lambda *a, **k: [("c:/m/card.md", ["E01"])])
    monkeypatch.setattr(jc, "declarations", lambda *a, **k: [])
    monkeypatch.setattr(jc, "append_guard_log", lambda name, rec: logs.append(rec))
    assert jc.gate("Edit", {"file_path": "c:/m/card.md"}, {"session_id": "s"}, {}) is None
    assert logs and logs[-1]["event"] == "undeclared" and logs[-1]["allowed"] is True


def test_subagent_stop_same_budget_then_released(monkeypatch, capsys):
    """子代理收尾：擋滿每回合預算就放行並留帳（舊碼擋到底 → 紅）；未知寫入只留帳。"""
    from handlers import stop as st
    state = {"turn_seq": 4, "turn_prompts_seq": 4, "agent_modified_files": {"ag": [{"path": "c:/p/a.py", "session_id": "s"}]},
             "agent_unknown_writes": {"ag": [{"cmd": "echo > $X"}]}}
    logs = []
    monkeypatch.setattr(st, "read_state", lambda sid: state)
    monkeypatch.setattr(st, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(st, "append_guard_log", lambda name, rec: logs.append(rec))
    monkeypatch.setattr(st, "_verify_gates", lambda *a, **k: ("[Guardian:ReconcileGate] x\n  ✗ (d) OWED", None, "reconcile"))
    monkeypatch.setattr(st, "entry_note", lambda *a, **k: "")
    outs = []
    monkeypatch.setattr(st, "output_block", lambda msg: outs.append("block"))
    monkeypatch.setattr(st, "output_nothing", lambda: outs.append("pass"))
    for _ in range(3):
        st.handle_subagent_stop({"session_id": "s", "agent_id": "ag"}, {"reconcile_gate": {"max_blocks_per_turn": 2}})
    assert outs == ["block", "block", "pass"], outs
    assert any(r.get("event") == "subagent_released" for r in logs) and any(r.get("event") == "unknown_writes_logged" for r in logs)


# ─── 單人單 session 也成立的形狀（目標視角觸發、回合起點、事後檢討、擋次預算、自檢評分） ──────────────

def test_external_claims_only_review_results():
    import wg_need_goal_points as ngp
    calls = [{"tool_name": "Read", "tool_input": {"file_path": "C:/x/workflow/inbox/to-track-a/001.md"}},
             {"tool_name": "Read", "tool_input": {"file_path": "C:/x/codex-review.md"}},
             {"tool_name": "mcp__workflow-guardian__second_opinion_result", "tool_input": {}}]
    assert [k for k, _ in ngp.claim_calls(calls)] == ["審查報告", "審查報告"]
    assert not hasattr(ngp, "peer_of_prompt")


def test_dispatch_message_does_not_open_turn():
    from handlers import ups_gates
    assert not hasattr(rr, "is_dispatch_message")
    state = {"turn_seq": 6, "turn_prompts_seq": 2, "turn_prompts": ["上GIT"], "turn_open": True}
    ups_gates.track_turn_prompts(state, '<cross-session-message from="x">派工 004：to-track-a/004.md</cross-session-message>')
    assert state["turn_prompts_seq"] == 2


def test_post_mortem_same_for_worktree():
    text = rr.dpm_instruction_text("重試 3 輪")
    assert "atom_write" in text and "交付信" not in text


def test_reconcile_budget_shared_per_user_turn():
    rec = rr.budget_tick(None, 3, ["*"])
    assert rr.budget_exhausted(rr.budget_tick(rec, 3, ["*"]), 3, 2, ["*"]) == ["*"]
    assert "BLOCK_BUDGET_SHARED" in rr.RULES and "BLOCK_BUDGET_PER_RULE" not in rr.RULES
    src = (HOOKS_DIR / "handlers" / "stop.py").read_text(encoding="utf-8")
    assert 'budget_exhausted(_rec, _uturn, _max, ["*"] if _code else [])' in src     # 寫碼查核整份共用鍵 "*"


def test_selfscore_not_an_entrypoint_and_lives_in_console_skill():
    """自檢評分是總控台用的開發期工具：不在切入點登錄表、整支在 skills/console/scripts/，產品 tools/ 底下沒有（舊碼在 tools/ → 紅）。"""
    reg = json.loads((ROOT / "workflow" / "entrypoints.json").read_text(encoding="utf-8"))
    assert "E36" not in {e.get("id") for e in reg["entrypoints"]}
    assert (ROOT / "skills" / "console" / "scripts" / "selfscore.py").is_file() and not (ROOT / "tools" / "selfscore.py").exists()


def test_dev_rules_not_in_product_texts():
    """開發期規矩（工作軌、交付信、工人 codex 一輪）不寫進 hook／MCP 說明；codex 一輪只留在總控台 skill。"""
    mcp = (ROOT / "tools" / "workflow-guardian-mcp" / "lib" / "mcp.js").read_text(encoding="utf-8")
    assert "交付信" not in mcp and "工作軌" not in mcp
    assert "_changelog.d" not in (ROOT / "rules" / "core.md").read_text(encoding="utf-8")
    assert (ROOT / "skills" / "console" / "scripts" / "changelog-fold.py").is_file()
    assert "Codex 只審一輪" in (ROOT / "skills" / "console" / "SKILL.md").read_text(encoding="utf-8")


# ─── 守門只在寫碼回合啟動 ────────────────────────────────────

def test_coding_turn_layer1_tool_writes_code():
    """第一層（實質行為）：這個使用者回合用工具改過程式檔（Edit、Bash 寫 .bat／.cmd 也算）或有判不出目標的寫入 → 寫碼回合；
    第一次改之前不是；只改文件不是；改的是上一個使用者回合不算。"""
    st5 = {"turn_seq": 5, "turn_prompts_seq": 5}
    assert not wg_core.coding_turn(dict(st5))                                         # 第一次 Edit 之前
    assert wg_core.coding_turn({**st5, "modified_files": [{"path": "c:/p/a.py", "tool": "Edit", "last_turn_seq": 5}]})   # 之後
    for code in ("c:/p/run.bat", "c:/p/run.cmd"):
        assert wg_core.coding_turn({**st5, "modified_files": [{"path": code, "tool": "Bash", "last_turn_seq": 5}]}), code
    assert not wg_core.coding_turn({**st5, "modified_files": [{"path": "c:/p/a.md", "tool": "Edit", "last_turn_seq": 5}]})
    assert not wg_core.coding_turn({**st5, "modified_files": [{"path": "c:/p/a.py", "last_turn_seq": 4}]})
    unk = {**st5, "unknown_writes": [{"cmd": "python -c ...", "target": "UNKNOWN:inline", "turn_seq": 5}]}
    assert wg_core.coding_turn(unk) and not wg_core.coding_turn({**unk, "unknown_writes": [{"cmd": "x", "turn_seq": 4}]})
    assert wg_core.coding_turn({"turn_seq": 5}, {"v6": {"coding_turn_only": False}})


def test_coding_turn_keyword_intent_is_not_a_switch():
    """第三層：關鍵字分類判成寫碼（turn_intent）不當開關——沒宣告、沒改檔就不是寫碼回合（舊碼吃意圖 → 紅）。"""
    assert not wg_core.coding_turn({"turn_intent": "feature", "turn_seq": 5, "turn_prompts_seq": 5})


def test_coding_turn_layer2_need_goal_declares_code_tree(ng_env):
    """第二層：本使用者回合 need_goal set（kind=code）、add、update 寫碼樹 → 還沒改檔也算寫碼回合；
    樹是前幾回合留的、本回合沒宣告 → 不算；知識類樹的宣告不算。"""
    from handlers import post_tool_use as pt
    ng = ng_env[0]

    def call(state, action, **kw):
        ti = {"action": action, **kw}
        pt._need_goal_after_tool(state, "s", "mcp__workflow-guardian__need_goal", ti, {"tool_response": {}}, {})
        return state

    st = call({"turn_seq": 3, "turn_prompts_seq": 3}, "set", goal="加匯出", kind="code")
    assert st.get("need_goal_code_decl_turn") == 3 and wg_core.coding_turn(st)           # 本回合 set 寫碼樹、還沒改檔
    later = {"turn_seq": 4, "turn_prompts_seq": 4, "need_goal_code_decl_turn": 3}
    assert not wg_core.coding_turn(later)                                                # 前幾回合留的樹、本回合沒宣告
    tid = ng.active_tree(ng.load("s"))["id"]
    assert wg_core.coding_turn(call(dict(later), "update", items=[{"id": tid, "text": "加匯出（CSV）"}]))   # 只 update
    assert wg_core.coding_turn(call(dict(later), "add", items=[{"text": "舊 JSON 不能壞"}]))           # add
    k = call({"turn_seq": 7, "turn_prompts_seq": 7}, "set", goal="整理筆記", kind="knowledge", new_task=True)
    assert not wg_core.coding_turn(k)                                                    # 知識類樹不算


def test_non_coding_turn_skips_v6_gates_at_stop():
    """收尾：不是寫碼回合、也不是「前幾回合改過程式、這則宣告完成」，退避偵測、退縮閘、收尾檢核、文字評分、閱讀路徑不跑
    （舊碼照跑 → 紅）；收割、收割待補是 v6 以前就有的，照舊每回合跑。"""
    src = (HOOKS_DIR / "handlers" / "stop.py").read_text(encoding="utf-8")
    assert "_coding = v6 and (coding_turn(state, config) or (_done(last_text) and _wrote_code(own_mod_files, config)))" in src
    for frag in ('if not state.get("evasion_flag") and (_coding or not v6):',
                 "if stop_count < max_blocks and last_text and (_coding or not v6):",
                 '(aec.get("d_pending") or []) if (_coding or not v6) else []'):
        assert frag in src, frag
    assert "waived=_hv_waived) if (_coding" not in src and "waived=_hp_waived) if (_coding" not in src


@pytest.fixture()
def stop_drive(monkeypatch):
    """驅動 handle_stop 到收尾檢核（ScanReport）；回 drive(last_text, state) → stdout。"""
    from handlers import stop as st
    for name, fn in (("_find_session_transcript", lambda *a, **k: None), ("token_warn_payload", lambda *a, **k: ""),
                     ("write_state", lambda *a, **k: None), ("_attribute_usefulness", lambda *a, **k: None),
                     ("_detect_uncommitted_files", lambda mf: []), ("_maybe_spawn_user_extract_worker", lambda *a, **k: None),
                     ("_hud_alive", lambda *a, **k: (True, {})), ("append_guard_log", lambda *a, **k: None),
                     ("_git_unpushed_roots", lambda mf: []), ("_should_deep_postmortem", lambda *a, **k: False)):
        monkeypatch.setattr(st, name, fn)
    monkeypatch.setattr(st, "_gate_mode", lambda rule, v6: st._BLOCK)   # 測判定與擋訊息內容，送法固定成擋

    def drive(capsys, last_text, mods):
        state = {"phase": "working", "modified_files": mods, "failing_tests": [], "recent_user_prompts": ["繼續"],
                 "stop_blocked_count": 0, "turn_seq": 5, "turn_prompts_seq": 5, "turn_intent": "general"}
        monkeypatch.setattr(st, "get_last_assistant_text", lambda *a, **k: last_text)
        monkeypatch.setattr(st, "_ensure_state", lambda *a, **k: state)
        with pytest.raises(SystemExit):
            st.handle_stop({"session_id": "s-ct", "cwd": ""}, {})
        drive.state = state
        return capsys.readouterr().out
    return drive


def test_docs_only_turn_skips_evasion_detection(stop_drive, capsys):
    """只改文件、沒宣告完成的回合：退避偵測不跑（舊碼照標 evasion_flag → 紅）；改了程式的回合照標（反例）。"""
    text = "文件補好了。剩下那段之後再處理。"
    doc = [{"path": r"c:\a\.claude\_AIDocs\note.md", "tool": "Edit", "session_id": "s-ct", "turn_seq": 5, "last_turn_seq": 5}]
    stop_drive(capsys, text, doc)
    assert not stop_drive.state.get("evasion_flag")
    code = [{"path": r"c:\a\.claude\hooks\x.py", "tool": "Edit", "session_id": "s-ct", "turn_seq": 5, "last_turn_seq": 5}]
    stop_drive(capsys, text, code)
    assert stop_drive.state.get("evasion_flag")


def test_docs_only_turn_skips_closing_check_unless_done_claimed(stop_drive, capsys):
    """前幾回合改了程式、這回合只動文件：沒宣告完成 → 不是寫碼回合，收尾檢核不跑；宣告完成 → 收尾檢核照查（收的是前幾回合的改動）。"""
    core = r"c:\a\.claude\hooks\x.py"
    mods = [{"path": core, "tool": "Edit", "session_id": "s-ct", "turn_seq": 3, "last_turn_seq": 3},
            {"path": r"c:\a\.claude\_AIDocs\note.md", "tool": "Edit", "session_id": "s-ct", "turn_seq": 5,
             "last_turn_seq": 5}]
    assert "[Guardian:ScanReport]" not in stop_drive(capsys, "文件補好了，接著看下一段。", mods)
    assert "[Guardian:ScanReport]" in stop_drive(capsys, "全部完成了", mods)


def test_non_coding_turn_ups_skips_goal_tree_keeps_cards(monkeypatch, tmp_path, capsys):
    """UPS：使用者剛打字時還沒宣告、還沒改程式，目標樹提示不送（原話照記）；關鍵字判寫碼的只多送一行「先立樹」、不啟動守門；
    導讀卡是 v6 以前就有的記憶注入，照舊送。"""
    from handlers import user_prompt_submit as ups
    import wg_need_goal
    import wg_overview
    seen = {"ng": 0, "hub": 0}

    def ng_on_prompt(*a, **k):
        seen["ng"] += 1
        return "[NeedGoal] 提示行"

    def hub_on_prompt(*a, **k):
        seen["hub"] += 1
        return "[Guardian:OverviewHub] 卡"
    monkeypatch.setattr(wg_need_goal, "on_prompt", ng_on_prompt)
    monkeypatch.setattr(wg_overview, "on_prompt", hub_on_prompt)
    for name, fn in (("run_pre_gates", lambda *a: None), ("build_context", lambda *a, **k: None),
                     ("collect_matched_atoms", lambda *a, **k: ([], {}, [], [], {}, set(), "general", {})),
                     ("assemble_injection", lambda *a, **k: ([], {})), ("write_state", lambda *a, **k: None),
                     ("_maybe_spawn_failure_extraction", lambda *a, **k: None), ("_update_topic_tracker", lambda *a, **k: None),
                     ("reconcile_injection_after_trim", lambda *a, **k: []), ("_truncate_context_by_activation", lambda l, *a, **k: l),
                     ("_hook_lap", lambda seg: False), ("WORKFLOW_DIR", tmp_path)):
        monkeypatch.setattr(ups, name, fn)
    out = {}
    for prompt in ("之前那個決定是什麼？", "幫我新增一個 by-product 子命令"):
        state = {"turn_seq": 4, "session": {"cwd": str(tmp_path)}, "injected_atoms": [], "modified_files": [], "knowledge_queue": []}
        monkeypatch.setattr(ups, "_ensure_state", lambda *a, _s=state, **k: _s)
        with pytest.raises(SystemExit):
            ups.handle_user_prompt_submit({"session_id": "s", "prompt": prompt, "cwd": str(tmp_path)}, {})
        cap = capsys.readouterr().out
        out[prompt] = json.loads(cap)["hookSpecificOutput"]["additionalContext"] if cap.strip() else ""
    import wg_need_goal as ng
    qa, code = out["之前那個決定是什麼？"], out["幫我新增一個 by-product 子命令"]
    assert "提示行" not in qa and ng.CODE_TREE_HINT not in qa and "OverviewHub" in qa
    assert "提示行" not in code and ng.CODE_TREE_HINT in code                   # 關鍵字判寫碼：只送先立樹一行
    assert seen["ng"] == 2 and seen["hub"] == 2                                   # 原話兩則都照記、導讀卡兩則都判


# ─── 文字評分 ──────────────────────────────────────────────────────

def _ts():
    import importlib.util
    spec = importlib.util.spec_from_file_location("text_score_tool", ROOT / "tools" / "text-score.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["text_score_tool"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_not_applicable_not_in_denominator():
    ts = _ts()
    spec = ts.load_spec("reader-designer")
    res = [ts.Result(it.id, it.must, "判定", "是" if i < 2 else "不適用", "", "") for i, it in enumerate(spec.items)]
    t = ts.tally(spec, res)
    assert t["summary"].startswith("評分 2/2") and t["total"] == 2, t["summary"]


def test_spec_goal_slot_filled_or_not_scored(capsys):
    ts = _ts()
    spec = ts.load_spec("reader-designer")
    assert ts.needs_goal(spec)
    filled = ts.with_goal(spec, "sales CLI 能列出每個產品的數量")
    assert "sales CLI" in filled.items[-1].question and not ts.needs_goal(filled)
    r = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "tools" / "text-score.py"), "-"], input="一段說明文字" * 30,
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0 and "不評：沒有當下的需求目標" in r.stdout


def test_prompt_gives_goal_first_then_asks_per_item():
    """裁判提示詞先給目標句，再問「針對這個目標，這條過不過」；每條都可答不適用（用原設計者的例子當有樹那一案）。"""
    ts = _ts()
    goal = "去除冗餘、重構特定類別與特定 cs，檔案允許延展"
    spec = ts.with_goal(ts.load_spec("reader-designer"), goal)
    p = ts.build_prompt(spec, spec.items[1], "原文", "")
    assert p.index(goal) < p.index(f"檢核項 {spec.items[1].id}：") and "針對這個目標" in p and "不適用" in p
    plain = ts.build_prompt(ts.load_spec("reader-designer"), spec.items[1], "原文", "")
    assert "當下的需求目標：" not in plain
    doc = (ROOT / "text-specs" / "reader-designer-說明.md").read_text(encoding="utf-8")
    assert goal in doc


def test_current_goal_tree_then_user_words_then_none(monkeypatch):
    """評分要對的目標：有樹用樹根；沒樹用本回合使用者原話；都沒有回空（不評）。"""
    import wg_need_goal as ng
    import wg_text_score as wts
    monkeypatch.setattr(ng, "load", lambda sid: {"active": "T1", "trees": {"T1": {"id": "T1", "nodes": {"T1": {"text": "樹根目標"}}}}})
    assert wts.current_goal({"turn_prompts": ["使用者原話"]}, "s") == "樹根目標"
    monkeypatch.setattr(ng, "load", lambda sid: {"active": None, "trees": {}})
    assert wts.current_goal({"turn_prompts": ["使用者原話"]}, "s") == "使用者原話"
    assert wts.current_goal({}, "s") == ""


def test_on_stop_without_goal_does_not_score(tmp_path, monkeypatch):
    import wg_need_goal as ng
    import wg_text_score as wts
    sent = []
    monkeypatch.setattr(wts, "JOB_DIR", tmp_path / "jobs")
    monkeypatch.setattr(wts, "_spawn_worker", lambda job: sent.append(json.loads(Path(job).read_text(encoding="utf-8"))))
    monkeypatch.setattr(ng, "load", lambda sid: {"active": None, "trees": {}})
    reply = "改了 x.py，跑過 verify。" + "說明" * 200
    cfg = {"text_score": {"enabled": True, "min_chars": 300}}
    wts.on_stop({}, "s", reply, [], 3, cfg, code_reply=True, user_turn=3)
    assert sent == []
    wts.on_stop({"turn_prompts": ["幫我修 x"]}, "s", reply + "2", [], 4, cfg, code_reply=True, user_turn=4)
    assert sent and sent[0]["tasks"][0]["goal"] == "幫我修 x"


def test_docs_scored_only_with_code_change_reply(tmp_path, monkeypatch):
    """文件類評分只在交付改程式那則（code_reply）送：純文件回合不評（舊碼本回合改過的 .md 一律送 → 紅）。"""
    import wg_text_score as wts
    sent = []
    monkeypatch.setattr(wts, "JOB_DIR", tmp_path / "jobs")
    monkeypatch.setattr(wts, "_spawn_worker", lambda job: sent.append(json.loads(Path(job).read_text(encoding="utf-8"))))
    monkeypatch.setattr(wts, "current_goal", lambda state, sid: "加匯出")
    doc = tmp_path / "proj" / "memory" / "_staging" / "g15-checklist.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("x", encoding="utf-8")
    mods = [{"path": str(doc), "session_id": "s", "last_turn_seq": 4}]
    cfg = {"text_score": {"enabled": True, "min_chars": 300,
                          "auto_targets": {"docs": ["memory/_staging/*checklist*.md"]}}}   # 出廠沒列 docs，案例自己給樣式
    assert wts.on_stop({}, "s", "短", mods, 4, cfg, code_reply=False, user_turn=4) is False and sent == []
    assert wts.on_stop({}, "s", "短", mods, 4, cfg, code_reply=True, user_turn=4) is True
    assert [t["kind"] for t in sent[0]["tasks"]] == ["docs"]


def test_hook_timing_not_recorded_in_non_coding_turn(tmp_path, monkeypatch):
    """非寫碼回合不寫 kind=run 計時帳（舊碼每次 hook 都寫 → 紅）；寫碼回合照寫；PreToolUse 看寫碼回合標記檔。"""
    import time as _t
    import wg_hook_timing as ht
    logs = []
    monkeypatch.setattr(ht, "append_guard_log", lambda g, rec: logs.append(rec))
    monkeypatch.setattr(ht, "WORKFLOW_DIR", tmp_path)

    def one(event, quiet):
        ht._CUR = ht.HookTimer(event, "s-ht", 8.0, "config", 0.8, _t.time())
        if quiet:
            ht.quiet()
        ht.finish()
    one("UserPromptSubmit", quiet=True)
    one("Stop", quiet=False)
    assert [r["event"] for r in logs if r["kind"] == "run"] == ["Stop"]
    one("PreToolUse", quiet=False)
    assert [r["event"] for r in logs if r["kind"] == "run"] == ["Stop"]          # 沒有寫碼回合標記：不記
    ht.mark_coding("s-ht", True)
    one("PreToolUse", quiet=False)
    assert [r["event"] for r in logs if r["kind"] == "run"] == ["Stop", "PreToolUse"]
    ht.mark_coding("s-ht", False)
    assert not (tmp_path / "hook-timing-coding" / "s-ht").exists()


def test_misjudged_sample_recorded():
    d = ROOT / "_AIDocs" / "DevHistory" / "v6.0-寫程式碼的進化-2026-10" / "裁判模型選型-實測"
    labels = json.loads((d / "g15_labels.json").read_text(encoding="utf-8"))
    assert (d / "g15_samples" / "S6-evaluation-no-code.md").is_file()
    assert labels["S6"]["R2"] == "是" and labels["S6"]["R4"] == "不適用"


if __name__ == "__main__":
    rc = pytest.main([__file__, "-q", "-p", "no:cacheprovider"])
    print("GATE_TRIM_CHECK PASS" if rc == 0 else "GATE_TRIM_CHECK FAIL")
    sys.exit(0 if rc == 0 else 1)

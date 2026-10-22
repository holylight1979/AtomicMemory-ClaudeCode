"""verify_cost_cut.py — 守門減量（v6.0 代價實測後的七刀）的行為案例。

做什麼：每一刀一段，驗「砍掉的重複／死重量真的不再進模型上下文或不再多擋一回合」，
  同時驗「原本在擋需要判斷的事」的那條入口還在（AI 宣告＋留帳）。
  刀6 同步提醒：UPS 的 Sync context 只留 stderr；收尾檢核 (g) 已交代時 SyncReminder 不另擋；底部一般 block 不重複擋。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_cost_cut.py
       python -X utf8 hooks/verify/verify_cost_cut.py   （直接跑，尾行 COST_CUT_CHECK PASS／FAIL）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

from handlers import stop as st  # noqa: E402
from handlers import user_prompt_submit as ups  # noqa: E402

_SID = "sid"
_A = "c:/p/docs/a.md"
_B = "c:/p/docs/b.md"


# ─── 刀6：同步提醒 ─────────────────────────────────────────────────────

@pytest.fixture()
def ups_run(monkeypatch, tmp_path):
    """跑 UserPromptSubmit 到底，其餘生產者都關掉；回 run(prompt) → (additionalContext, stderr)。"""
    import wg_friction
    import wg_need_goal
    import wg_overview
    import wg_release_rules
    state = {"turn_seq": 4, "session": {"cwd": str(tmp_path)}, "injected_atoms": [],
             "modified_files": [{"path": _A, "session_id": _SID}], "knowledge_queue": []}
    monkeypatch.setattr(ups, "_ensure_state", lambda *a, **k: state)
    monkeypatch.setattr(ups, "WORKFLOW_DIR", tmp_path)
    monkeypatch.setattr(ups, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(ups, "run_pre_gates", lambda *a: a[-1].append("閘的提示"))
    monkeypatch.setattr(ups, "build_context", lambda *a, **k: None)
    monkeypatch.setattr(ups, "collect_matched_atoms", lambda *a, **k: ([], {}, [], [], {}, set(), "general", {}))
    monkeypatch.setattr(ups, "assemble_injection", lambda *a, **k: ([], {}))
    monkeypatch.setattr(wg_need_goal, "on_prompt", lambda *a, **k: None)
    monkeypatch.setattr(wg_overview, "on_prompt", lambda *a, **k: "")
    monkeypatch.setattr(wg_friction, "record_correction", lambda *a, **k: [])
    monkeypatch.setattr(wg_release_rules, "fix_escalation_text", lambda s: "")
    monkeypatch.setattr(ups, "_maybe_spawn_failure_extraction", lambda *a, **k: None)
    monkeypatch.setattr(ups, "_update_topic_tracker", lambda *a, **k: None)
    monkeypatch.setattr(ups, "reconcile_injection_after_trim", lambda *a, **k: [])
    monkeypatch.setattr(ups, "_truncate_context_by_activation", lambda lines, *a, **k: lines)
    monkeypatch.setattr(ups, "_hook_lap", lambda seg: False)

    def run(prompt, capsys):
        with pytest.raises(SystemExit):
            ups.handle_user_prompt_submit({"session_id": _SID, "prompt": prompt, "cwd": str(tmp_path)}, {})
        cap = capsys.readouterr()
        ctx = json.loads(cap.out)["hookSpecificOutput"]["additionalContext"] if cap.out.strip() else ""
        return ctx, cap.err
    return run


def test_ups_sync_context_goes_to_stderr_only(ups_run, capsys):
    """使用者話裡有同步關鍵字（commit）且有改檔：Sync context 那塊不進模型上下文，只留 stderr 一行。"""
    ctx, err = ups_run("把改了哪些檔整理一下，先不要 commit", capsys)
    assert "Sync context" not in ctx and "Files:" not in ctx
    assert "[Guardian] Sync context: 1 files modified" in err


@pytest.fixture()
def stop_run(monkeypatch):
    """驅動 handle_stop 到同步提醒／底部一般 block；回 run(state_extra, uncommitted) → (stdout, stderr, guard_log)。"""
    logs = []
    monkeypatch.setattr(st, "_find_session_transcript", lambda *a, **k: None)
    monkeypatch.setattr(st, "get_last_assistant_text", lambda *a, **k: "全部完成了")
    monkeypatch.setattr(st, "token_warn_payload", lambda *a, **k: "")
    monkeypatch.setattr(st, "detect_evasion", lambda *a, **k: None)
    monkeypatch.setattr(st, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(st, "_attribute_usefulness", lambda *a, **k: None)
    monkeypatch.setattr(st, "_should_deep_postmortem", lambda *a, **k: False)
    monkeypatch.setattr(st, "_maybe_spawn_user_extract_worker", lambda *a, **k: None)
    monkeypatch.setattr(st, "_drop_synced", lambda mf: mf)
    monkeypatch.setattr(st, "append_guard_log", lambda name, rec: logs.append((name, rec)))

    def run(capsys, uncommitted=True, config=None, **extra):
        monkeypatch.setattr(st, "_detect_uncommitted_files",
                            (lambda mf: [m["path"] for m in mf]) if uncommitted else (lambda mf: []))
        monkeypatch.setattr(st, "_git_unpushed_roots", lambda mf: [])
        state = {"phase": "working", "turn_seq": 7,
                 "modified_files": [{"path": _A, "session_id": _SID, "turn_seq": 7, "last_at": "2026-10-22T10:00:00+08:00"},
                                    {"path": _B, "session_id": _SID, "turn_seq": 7, "last_at": "2026-10-22T10:00:00+08:00"}],
                 "failing_tests": [], "recent_user_prompts": [], "stop_blocked_count": 0, "scan_report_warned": True}
        state.update(extra)
        monkeypatch.setattr(st, "_ensure_state", lambda *a, **k: state)
        logs.clear()
        with pytest.raises(SystemExit):
            st.handle_stop({"session_id": _SID, "cwd": ""}, config or {})
        cap = capsys.readouterr()
        return cap.out, cap.err, list(logs)
    return run


def test_sync_reminder_skipped_when_closing_check_covers_it(stop_run, capsys):
    """本回合已交收尾檢核（(g) 版控收尾是必填）：未 commit 的檔不再另擋一回合，只留 stderr 與留帳。"""
    out, err, logs = stop_run(capsys, anti_evasion_report={"turn_seq": 7, "session_id": _SID, "at": "2026-10-22T10:05:00+08:00"})
    assert "[Guardian:SyncReminder]" not in out
    assert "收尾檢核 (g) 已交代" in err
    assert any(n == "sync_reminder" and r["event"] == "covered_by_aec" for n, r in logs)


def test_sync_reminder_blocks_when_edited_after_closing_check(stop_run, capsys):
    """交了收尾檢核之後又改檔：(g) 交代的是舊狀態，照擋同步提醒（codex 第二意見指出的順序）。"""
    out, _, _ = stop_run(capsys, anti_evasion_report={"turn_seq": 7, "session_id": _SID, "at": "2026-10-22T09:55:00+08:00"})
    assert "[Guardian:SyncReminder]" in out


def test_sync_reminder_still_blocks_without_closing_check(stop_run, capsys):
    """沒交收尾檢核：同步提醒照擋（AI 要說明有沒有口令、打不打算上——這是要判斷的事，入口保留）。"""
    out, _, _ = stop_run(capsys)
    assert "[Guardian:SyncReminder]" in out


def test_generic_block_not_repeated_for_modified_files(stop_run, capsys):
    """只剩「改了 N 個檔」（同步提醒已用掉額度）：底部一般 block 不再重擋同一件事，只留 stderr。"""
    out, err, _ = stop_run(capsys, uncommitted=False, sync_reminder_count=1)
    assert "[Workflow Guardian]" not in out
    assert "file(s) modified" in err


def test_generic_block_kept_for_pending_knowledge(stop_run, capsys):
    """有待記知識（knowledge_queue）時底部 block 照擋：那不是同步提醒的重複。"""
    out, _, _ = stop_run(capsys, uncommitted=False, sync_reminder_count=1,
                         knowledge_queue=[{"content": "某個坑", "classification": "[臨]"}])
    assert "[Workflow Guardian]" in out


# ─── 刀2：定位三行同一次動作就收 ───────────────────────────────────────

@pytest.fixture()
def hub(tmp_path, monkeypatch):
    """假專案（一個部位【報表】、有導讀卡）＋讀過部位檔、還沒交定位行的 state；目標樹固定成 T1→T1.1。"""
    import wg_overview as wo
    root = tmp_path / "proj"
    (root / ".claude" / "memory" / "shared").mkdir(parents=True)
    (root / ".claude" / "overview-map.md").write_text(
        "| 路徑前綴 | 範疇 | 導讀卡 | 狀態 |\n|---|---|---|---|\n| `src/` | 報表 | `報表導讀` | 有 |\n", encoding="utf-8")
    (root / ".claude" / "memory" / "shared" / "報表導讀.md").write_text("# 報表導讀\n月份歸屬在 periods", encoding="utf-8")
    (root / "src").mkdir()
    files = [str(root / "src" / n) for n in ("a.py", "b.py")]
    for f in files:
        Path(f).write_text("x = 1\n", encoding="utf-8")
    tp = tmp_path / "t.jsonl"
    tp.write_text(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "先看看。"}]}},
                             ensure_ascii=False) + "\n", encoding="utf-8")
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    tree = {"id": "T1", "nodes": {"T1": {"text": "加 by-product", "status": "doing"},
                                  "T1.1": {"text": "新子命令", "status": "todo", "parent": "T1"}}}
    monkeypatch.setattr(wo, "_goal_tree_for", lambda *a, **k: tree)
    state = {"turn_seq": 3}
    for f in files:
        wo.on_read(state, "s", "Read", {"file_path": f}, str(root), str(tp), {})
    return wo, state, files, str(tp)


def test_locate_first_deny_asks_everything_at_once(hub):
    """第一次擋就把內容要求與填好部位、節點的範例一起給（兩個候選＋選 A 因為、節點角色、合理／不合理的判斷），
    不先只給骨架、交了再擋一輪格式（現況兩跑各三輪、每輪平行四次）。"""
    wo, state, files, tp = hub
    _, deny, _ = wo.on_edit(state, "s", files[0], tp, {})
    assert deny and "選 A 因為" in deny and "定位｜目標：T1（<這一塊替 T1 做什麼>）" in deny
    assert "合理／不合理" in deny and "定位｜部位：報表——" in deny


def test_locate_same_batch_deny_is_one_line(hub):
    """同一回合、同一部位、缺的一樣（平行送出的第二個改檔）：只回一行指回上一則，不重送整段要求。"""
    wo, state, files, tp = hub
    _, first, _ = wo.on_edit(state, "s", files[0], tp, {})
    _, second, _ = wo.on_edit(state, "s", files[1], tp, {})
    assert "定位｜根因層" in first
    assert "同樣被擋" in second and "定位｜根因層" not in second and len(second) - len(files[1]) < 200


def test_locate_changed_missing_same_turn_gets_full_text(hub):
    """同一回合、缺的變了（補交了格式不對的定位行）：送新的全文，不用一行帶過，新的缺失資訊不被吞掉。"""
    wo, state, files, tp = hub
    wo.on_edit(state, "s", files[0], tp, {})
    with open(tp, "a", encoding="utf-8") as f:
        f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text":
                "定位｜部位：報表：a.py\n定位｜根因層：邏輯層\n定位｜前例：無\n定位｜目標：T1.1\n定位｜批判：還好"}]}},
                           ensure_ascii=False) + "\n")
    _, again, _ = wo.on_edit(state, "s", files[1], tp, {})
    assert "同樣被擋" not in again and "LOCATE_LINES" in again


def test_locate_new_turn_gets_full_ask_again(hub):
    """換了使用者回合，或缺的東西變了：照送全文（入口不變成永遠只有一行）。"""
    wo, state, files, tp = hub
    wo.on_edit(state, "s", files[0], tp, {})
    state["turn_seq"] = 4
    _, again, _ = wo.on_edit(state, "s", files[1], tp, {})
    assert "定位｜根因層" in again and "同樣被擋" not in again


def test_judgment_card_full_text_once_per_turn(tmp_path, monkeypatch):
    """同一個使用者回合問第二次：同一張判準卡只送一行指回，帳照記並標 repeated；換回合照送全文。"""
    import wg_core
    import wg_entrypoint as ep
    card = tmp_path / "卡.md"
    card.write_text("# 卡\n\n## 知識\n\n- [臨] 根因候選要跨層找，先往上游追資料從哪壞掉。\n", encoding="utf-8")
    reg = {"entrypoints": [{"id": "E01", "rules": ["LOCATE_X"], "paths": ["pre_tool_use"]}]}
    pool = [{"name": "卡", "file": card, "triggers": [], "entry": ["E01"]}]
    logs = []
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", tmp_path / "wf")
    monkeypatch.setattr(wg_core, "append_guard_log", lambda name, rec: logs.append(rec))
    ask = lambda turn: ep.entry_note("擋：LOCATE_X", "pre_tool_use", session_id="s", state={"turn_seq": turn},
                                     registry=reg, pool=pool)
    first, second, next_turn = ask(3), ask(3), ask(4)
    assert "往上游追" in first
    assert "往上游追" not in second and "已送過全文" in second
    assert logs[1]["repeated"] == ["卡"] and logs[1]["cards"] == ["卡"]
    assert "往上游追" in next_turn


# ─── 刀1：目標樹工具呼叫合併 ───────────────────────────────────────────

@pytest.fixture()
def ng_env(tmp_path, monkeypatch):
    """tmp 資料根的目標檔；回 (ng, op, add_receipt, edit)：op(action, **kw) 套用一次 need_goal；add_receipt(green) 蓋一筆收據；
    edit(path) 蓋一筆程式改動（待對照）。"""
    import wg_core
    import wg_need_goal as ng
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", tmp_path / "wf")
    monkeypatch.setattr(wg_core, "append_guard_log", lambda *a, **k: None)
    proj = tmp_path / "proj"
    (proj / "tests").mkdir(parents=True)
    (proj / "tests" / "test_a.py").write_text("def test_a():\n    assert True\n", encoding="utf-8")

    def op(action, turn=1, **kw):
        return ng.apply_op(_SID, turn, {"action": action, **kw}, str(proj))

    def add_receipt(green=True):
        def fn(doc):
            seq = ng.next_seq(doc)
            doc.setdefault("receipts", []).append({"seq": seq, "cmd": "pytest tests", "cases": [],
                                                   "verdicts": [f"pytest:{'PASS' if green else 'FAIL'}"],
                                                   "exit": 0 if green else 1, "turn": 1})
            return seq
        return ng.update_locked(_SID, fn)

    def edit(path="sales/cli.py"):
        ng.stamp_edit(_SID, str(proj / path), "", 1, {})
    return ng, op, add_receipt, edit


def test_set_carries_subgoals_in_one_call(ng_env):
    """set 帶 items：樹根與看得出的子目標一次寫好（現況每跑 set＋add 兩次呼叫，各自送回整棵樹）。"""
    ng, op, _, _ = ng_env
    res = op("set", goal="sales cli 能列出每個產品的數量和金額", items=[{"text": "金額兩位小數"}, {"text": "monthly 輸出不變"}])
    tree = ng.active_tree(ng.load(_SID))
    assert res["ok"] and set(tree["nodes"]) == {"T1", "T1.1", "T1.2"}


def test_set_items_validated_like_add(ng_env):
    """set 的 items 照 add 的規則驗（text 必填）：壞的整次拒收，不留半棵樹。"""
    ng, op, _, _ = ng_env
    res = op("set", goal="目標", items=[{"clarity": "open"}])
    assert not res["ok"] and any("text 必填" in r for r in res["rejected"])


def test_set_items_mirror_in_mcp_layer():
    """MCP（Node）那層驗同一組規則（MIRROR）：set 帶好的 items 收、壞的拒；舊 Node 不認 set 的 items → 壞的也收（紅）。"""
    import shutil
    import subprocess
    if not shutil.which("node"):
        pytest.skip("這台沒有 node")
    js = HOOKS_DIR.parent / "tools" / "workflow-guardian-mcp" / "lib" / "need-goal.js"
    code = (f"const {{validateArgs}}=require({json.dumps(str(js))});"
            "console.log(JSON.stringify([validateArgs({action:'set',goal:'g',items:[{text:'a'}]}),"
            "validateArgs({action:'set',goal:'g',items:[{clarity:'open'}]})]))")
    good, bad = json.loads(subprocess.run(["node", "-e", code], capture_output=True, text=True, encoding="utf-8",
                                          check=True).stdout)
    assert good == [] and any("text 必填" in e for e in bad)


def test_write_ops_send_compact_tree_not_full(ng_env):
    """刀4 重複：add／update／reconcile 不再每次送回整棵全樹（原話、收據清單、待對照）；set 照送全樹（原話與解讀並排）。"""
    ng, op, add_receipt, _ = ng_env
    first = op("set", goal="sales cli 能列出每個產品的數量和金額")
    add_receipt()
    later = op("add", items=[{"text": "金額兩位小數"}])
    assert "節點：" in first["text"]
    assert "節點：" not in later["text"] and "最近收據" not in later["text"] and "T1.1" in later["text"]


def test_reconcile_receipt_latest_filled_by_program(ng_env):
    """reconcile 收據寫 latest：程式填最近一筆綠的收據，不用先 read 整棵樹查號碼（現況每跑交付前 read 兩次）。"""
    ng, op, add_receipt, edit = ng_env
    op("set", goal="目標")
    edit()
    add_receipt(green=False)
    green = add_receipt(green=True)
    res = op("reconcile", items=[{"id": "T1", "status": "done", "evidence": [
        {"kind": "receipt", "ref": "latest", "level": "measured"},
        {"kind": "case", "ref": "tests/test_a.py", "level": "read"}]}])
    assert res["ok"], res["rejected"]
    ev = ng.active_tree(ng.load(_SID))["nodes"]["T1"]["evidence"][0]
    assert ev["ref"] == f"R{green}" and ev["auto"] is True


def test_owed_progress_recorded_by_program_not_asked(ng_env):
    """改了程式還沒交進度：收尾不再擋下要 AI 另叫 update，程式照改動與收據記一筆進度並清掉待對照（留帳 by=program）。"""
    ng, op, add_receipt, edit = ng_env
    op("set", goal="目標")
    edit()
    add_receipt()
    assert ng._owed(ng.active_tree(ng.load(_SID)))
    assert ng.goal_gate_reason(_SID, False, {}) is None
    tree = ng.active_tree(ng.load(_SID))
    assert not ng._owed(tree)
    last = tree["nodes"]["T1"]["history"][-1]
    assert last["what"] == "progress" and last["by"] == "program" and "cli.py" in last["why"]


def test_bookkeeping_runs_even_when_goal_gate_off(ng_env):
    """live 設定 reconcile_gate.goal_gate=false（目標對照不擋）：記進度與 latest 往前換是記帳不是閘，照做；收尾檢核附的樹也是現況。"""
    ng, op, add_receipt, edit = ng_env
    off = {"reconcile_gate": {"goal_gate": False}}
    op("set", goal="目標")
    edit()
    add_receipt()
    op("reconcile", items=[{"id": "T1", "status": "done", "evidence": [
        {"kind": "receipt", "ref": "latest", "level": "measured"},
        {"kind": "case", "ref": "tests/test_a.py", "level": "read"}]}])
    edit()
    newer = add_receipt()
    assert ng.goal_gate_reason(_SID, True, off) is None
    tree = ng.active_tree(ng.load(_SID))
    assert not ng._owed(tree) and tree["nodes"]["T1"]["history"][-1]["by"] == "program"
    assert tree["nodes"]["T1"]["evidence"][0]["ref"] == f"R{newer}"
    edit()
    newest = add_receipt()
    snap = ng.snapshot_for_report(_SID)
    assert snap["reconcile"]["ok"] and any(f"R{newest}" in e for e in snap["nodes"][0]["evidence"])


def test_latest_evidence_moves_forward_after_rerun(ng_env):
    """對照之後又改了程式、也重跑綠了：交付邊界自動換成最新那筆綠收據，不叫 AI 為同一件事重交對照（現況 B′ 重交 3 次）。"""
    ng, op, add_receipt, edit = ng_env
    op("set", goal="目標")
    edit()
    add_receipt()
    op("reconcile", items=[{"id": "T1", "status": "done", "evidence": [
        {"kind": "receipt", "ref": "latest", "level": "measured"},
        {"kind": "case", "ref": "tests/test_a.py", "level": "read"}]}])
    edit()
    newer = add_receipt()
    assert ng.goal_gate_reason(_SID, True, {}) is None
    assert ng.active_tree(ng.load(_SID))["nodes"]["T1"]["evidence"][0]["ref"] == f"R{newer}"


def test_latest_evidence_ignores_unrelated_green_run(ng_env):
    """對照之後改了程式、只跑了別的測試（指令不同、沒點名原本的案例）：不換過去，照擋「改完沒重跑」——不能拿不相干的綠收據頂。"""
    ng, op, add_receipt, edit = ng_env
    op("set", goal="目標")
    edit()
    add_receipt()
    op("reconcile", items=[{"id": "T1", "status": "done", "evidence": [
        {"kind": "receipt", "ref": "latest", "level": "measured"},
        {"kind": "case", "ref": "tests/test_a.py", "level": "read"}]}])
    edit()

    def other(doc):
        doc["receipts"].append({"seq": ng.next_seq(doc), "cmd": "python -m pytest other_tests", "cases": [],
                                "verdicts": ["pytest:PASS"], "exit": 0, "turn": 1})
    ng.update_locked(_SID, other)
    reason = ng.goal_gate_reason(_SID, True, {})
    assert reason and "改完沒重跑" in reason


def test_latest_evidence_still_owed_when_not_rerun(ng_env):
    """改了程式卻沒重跑：沒有更新的綠收據可換，交付邊界照擋「改完沒重跑」（入口不變成不擋）。"""
    ng, op, add_receipt, edit = ng_env
    op("set", goal="目標")
    edit()
    add_receipt()
    op("reconcile", items=[{"id": "T1", "status": "done", "evidence": [
        {"kind": "receipt", "ref": "latest", "level": "measured"},
        {"kind": "case", "ref": "tests/test_a.py", "level": "read"}]}])
    edit()
    reason = ng.goal_gate_reason(_SID, True, {})
    assert reason and "改完沒重跑" in reason


# ─── 刀3＋刀7：知識收割與目標樹記帳交背景的免費模型 ─────────────────────────

_HV_CFG = {"harvest": {"enabled": True, "min_turns": 1, "min_accessed": 0, "min_turns_between": 0}}


def test_harvest_goes_background_instead_of_blocking(stop_run, capsys, monkeypatch):
    """宣告完成、本來要擋 KnowledgeHarvest：改送背景收割，不擋寫碼 AI 一回合（現況每跑多一回合約 25 萬 token）。"""
    queued = []
    monkeypatch.setattr(st, "bg_harvest", lambda *a, **k: queued.append(a) or True)
    monkeypatch.setattr(st, "harvest_gate_reason", lambda *a, **k: "[Guardian:KnowledgeHarvest] 先收割")
    out, _, _ = stop_run(capsys, anti_evasion_report={"turn_seq": 7, "session_id": _SID}, config=_HV_CFG)
    assert "KnowledgeHarvest" not in out and len(queued) == 1


def test_harvest_blocks_when_background_cannot_start(stop_run, capsys, monkeypatch):
    """背景送不出去（起不了行程）：照舊擋下要 AI 收割，不靜默略過。"""
    monkeypatch.setattr(st, "bg_harvest", lambda *a, **k: False)
    monkeypatch.setattr(st, "harvest_gate_reason", lambda *a, **k: "[Guardian:KnowledgeHarvest] 先收割")
    out, _, _ = stop_run(capsys, anti_evasion_report={"turn_seq": 7, "session_id": _SID}, config=_HV_CFG)
    assert "KnowledgeHarvest" in out


def test_background_switch_off_keeps_old_gate(stop_run, capsys, monkeypatch):
    """harvest.background=false：照舊擋（開關在，原設計者要退回時不用改程式）。"""
    monkeypatch.setattr(st, "harvest_gate_reason", lambda *a, **k: "[Guardian:KnowledgeHarvest] 先收割")
    cfg = {"harvest": {**_HV_CFG["harvest"], "background": False}}
    out, _, _ = stop_run(capsys, anti_evasion_report={"turn_seq": 7, "session_id": _SID}, config=cfg)
    assert "KnowledgeHarvest" in out


def test_bg_worker_writes_candidates_and_progress_drafts(tmp_path, monkeypatch):
    """背景：讀 transcript 尾段問本地模型，候選卡落待審區、進度草稿寫回目標樹（by=local_llm），留帳 done。"""
    import wg_bg_harvest as bh
    import wg_core
    import wg_need_goal as ng
    logs = []
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", tmp_path / "wf")
    monkeypatch.setattr(bh, "JOB_DIR", tmp_path / "wf" / "harvest-bg")
    monkeypatch.setattr(bh, "CLAUDE_DIR", tmp_path / "data")
    monkeypatch.setattr(bh, "append_guard_log", lambda name, rec: logs.append(rec))
    proj = tmp_path / "proj"
    (proj / "tests").mkdir(parents=True)
    ng.apply_op(_SID, 7, {"action": "set", "goal": "加子命令"}, str(proj))
    ng.stamp_edit(_SID, str(proj / "cli.py"), "", 7, {})
    ng.auto_progress(_SID, 7)
    tp = tmp_path / "t.jsonl"
    tp.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in (
        {"type": "user", "message": {"content": "加 by-product，monthly 不要動"}},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "發現 monthly 用 UTC 切月。"},
                                                     {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}]}})),
                  encoding="utf-8")
    asked = []
    reply = json.dumps({"candidates": [{"title": "月報用 UTC 切月", "knowledge": "台北凌晨的單會歸到前一月", "why": "會重犯"}],
                        "progress": [{"node": "T1", "line": "子命令接上了"}, {"node": "T9", "line": "沒問的"}]},
                       ensure_ascii=False)
    bh.JOB_DIR.mkdir(parents=True)
    job = bh.JOB_DIR / "j.json"
    job.write_text(json.dumps({"session": _SID, "transcript": str(tp), "cwd": "", "turn": 7, "cfg": bh.DEFAULTS}), encoding="utf-8")
    assert bh.run_job(job, ask=lambda prompt, cfg: asked.append(prompt) or reply) == 0
    assert "UTC 切月" in asked[0] and "ls" not in asked[0] and "T1" in asked[0]
    cards = list((tmp_path / "data" / "memory" / "_staging" / "harvest-candidates").glob("harvest-*.md"))
    assert len(cards) == 1 and "台北凌晨" in cards[0].read_text(encoding="utf-8")
    last = ng.active_tree(ng.load(_SID))["nodes"]["T1"]["history"][-1]
    assert last["what"] == "progress_draft" and last["by"] == "local_llm" and last["model"] == "gemma4:e4b"
    assert logs[-1]["event"] == "done" and logs[-1]["progress_drafts"] == 1 and not job.exists()   # 沒問的 T9 不收


def test_bg_worker_empty_json_is_failed_not_done(tmp_path, monkeypatch):
    """模型回了合法 JSON 卻沒照要求作答（沒有 candidates／progress）：記 failed，不當成功。"""
    import wg_bg_harvest as bh
    logs = []
    monkeypatch.setattr(bh, "JOB_DIR", tmp_path)
    monkeypatch.setattr(bh, "append_guard_log", lambda name, rec: logs.append(rec))
    tp = tmp_path / "t.jsonl"
    tp.write_text(json.dumps({"type": "user", "message": {"content": "hi"}}), encoding="utf-8")
    job = tmp_path / "j.json"
    job.write_text(json.dumps({"session": _SID, "transcript": str(tp), "turn": 1, "cfg": bh.DEFAULTS}), encoding="utf-8")
    assert bh.run_job(job, ask=lambda p, c: "{}") == 2
    assert logs[-1]["event"] == "failed" and "沒照要求" in logs[-1]["why"]


def test_bg_worker_model_down_is_logged_not_silent(tmp_path, monkeypatch):
    """本地模型不在（回空）：留帳 failed 寫原因，不改用付費模型、不寫半成品。"""
    import wg_bg_harvest as bh
    logs = []
    monkeypatch.setattr(bh, "JOB_DIR", tmp_path)
    monkeypatch.setattr(bh, "append_guard_log", lambda name, rec: logs.append(rec))
    tp = tmp_path / "t.jsonl"
    tp.write_text(json.dumps({"type": "user", "message": {"content": "hi"}}), encoding="utf-8")
    job = tmp_path / "j.json"
    job.write_text(json.dumps({"session": _SID, "transcript": str(tp), "turn": 1, "cfg": bh.DEFAULTS}), encoding="utf-8")
    assert bh.run_job(job, ask=lambda p, c: "") == 2
    assert logs[-1]["event"] == "failed" and "沒回" in logs[-1]["why"]


# ─── 刀5：反覆驗證（第一次跑就算數） ─────────────────────────────────────

def test_scope_declare_says_which_run_shape_counts(tmp_path):
    """宣告驗證範圍的回應先講怎樣跑才算收據（測試自己一條或只用 && 串；; 串 echo／比對整條不算）。
    B′ 實測：AI 用 ; 把測試和輸出比對串一起跑，整條不算，只好同一組測試再跑一次。"""
    import wg_verify_scope as vs
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("def test_a():\n    pass\n", encoding="utf-8")
    text = vs.declare({"turn_seq": 5, "modified_files": []}, _SID,
                      {"action": "verify_scope", "items": [{"target": "tests/test_a.py", "why": "直接測"}]},
                      str(tmp_path), {}, lookup=lambda p: None)
    assert "收下" in text and "用 ; 串別的指令" in text and "&&" in text


if __name__ == "__main__":
    rc = pytest.main([__file__, "-q", "-p", "no:cacheprovider"])
    print("COST_CUT_CHECK PASS" if rc == 0 else "COST_CUT_CHECK FAIL")
    sys.exit(0 if rc == 0 else 1)

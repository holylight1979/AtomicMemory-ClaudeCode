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

    monkeypatch.setattr(st, "coding_turn", lambda *a, **k: True)   # 測閘本身：當成寫碼回合（CODING_TURN_ONLY 的案在 verify_gate_trim）

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
    """假專案（一個部位【報表】、有導讀卡）＋讀過部位檔、還沒交定位行的 state。"""
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
    state = {"turn_seq": 3}
    for f in files:
        wo.on_read(state, "s", "Read", {"file_path": f}, str(root), str(tp), {})
    assert "導讀卡現在才送" in wo.on_edit(state, "s", files[0], str(tp), {})[1]   # 卡隨第一次改檔到；那一刀擋這一輪（LOCATE_FIRST_EDIT_BLOCKS_ONCE）
    state["turn_seq"] = 4                                                        # 下一個使用者回合：這一輪結束，缺定位走一般判定（擋訊息、擋次上限）
    return wo, state, files, str(tp)


def test_locate_same_batch_deny_is_one_line(hub):
    """同一回合、同一部位、缺的一樣（平行送出的第二個改檔）：只回一行指回上一則，不重送整段要求。"""
    wo, state, files, tp = hub
    _, first, _ = wo.on_edit(state, "s", files[0], tp, {})
    _, second, _ = wo.on_edit(state, "s", files[1], tp, {})
    assert "定位｜根因層" in first
    assert "同樣被擋" in second and "定位｜根因層" not in second and len(second) - len(files[1]) < 200


def test_locate_new_turn_gets_full_ask_again(hub):
    """換了使用者回合：照送整則擋訊息、不是「同樣被擋」那一行（入口不變成永遠只有一行）。"""
    wo, state, files, tp = hub
    wo.on_edit(state, "s", files[0], tp, {})
    state["turn_seq"] = 5
    _, again, _ = wo.on_edit(state, "s", files[1], tp, {})
    assert "還沒交出定位三行" in again and "定位｜根因層" in again and "同樣被擋" not in again


# 判準卡一話題一次（原 CARD_ONCE_PER_TURN）的案例在 verify_gate_slimming.py


# ─── 刀3＋刀7：知識收割交背景的免費模型 ─────────────────────────

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


def test_bg_worker_writes_candidates(tmp_path, monkeypatch):
    """背景：讀 transcript 尾段問本地模型，候選卡落待審區，留帳 done。"""
    import wg_bg_harvest as bh
    import wg_core
    logs = []
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", tmp_path / "wf")
    monkeypatch.setattr(bh, "JOB_DIR", tmp_path / "wf" / "harvest-bg")
    monkeypatch.setattr(bh, "CLAUDE_DIR", tmp_path / "data")
    monkeypatch.setattr(bh, "append_guard_log", lambda name, rec: logs.append(rec))
    tp = tmp_path / "t.jsonl"
    tp.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in (
        {"type": "user", "message": {"content": "加 by-product，monthly 不要動"}},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "發現 monthly 用 UTC 切月。"},
                                                     {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}]}})),
                  encoding="utf-8")
    asked = []
    reply = json.dumps({"candidates": [{"title": "月報用 UTC 切月", "knowledge": "台北凌晨的單會歸到前一月", "why": "會重犯"}]},
                       ensure_ascii=False)
    bh.JOB_DIR.mkdir(parents=True)
    job = bh.JOB_DIR / "j.json"
    job.write_text(json.dumps({"session": _SID, "transcript": str(tp), "cwd": "", "turn": 7, "cfg": bh.DEFAULTS}), encoding="utf-8")
    assert bh.run_job(job, ask=lambda prompt, cfg: asked.append(prompt) or reply) == 0
    assert "UTC 切月" in asked[0] and "ls" not in asked[0]
    cards = list((tmp_path / "data" / "memory" / "_staging" / "harvest-candidates").glob("harvest-*.md"))
    assert len(cards) == 1 and "台北凌晨" in cards[0].read_text(encoding="utf-8")
    assert logs[-1]["event"] == "done" and logs[-1]["model"] == "gemma4:e4b" and not job.exists()


def test_bg_worker_empty_json_is_failed_not_done(tmp_path, monkeypatch):
    """模型回了合法 JSON 卻沒照要求作答（沒有 candidates）：記 failed，不當成功。"""
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


if __name__ == "__main__":
    rc = pytest.main([__file__, "-q", "-p", "no:cacheprovider"])
    print("COST_CUT_CHECK PASS" if rc == 0 else "COST_CUT_CHECK FAIL")
    sys.exit(0 if rc == 0 else 1)


@pytest.fixture(autouse=True)
def _block_mode(monkeypatch):
    """規則 GATE_MODE_TABLE：送法只讀 wg_release_rules.RULE_MODE。這個檔的案例驗的是判定與擋訊息內容，把送法釘成 block 讓它們照驗；
    v6 預設的提醒送法（Stop 只留帳、提醒掛改檔那則工具結果）由 verify_gate_mode_stop.py 驗。"""
    import wg_release_rules as _rr
    monkeypatch.setattr(_rr, "mode_of", lambda rule: _rr.BLOCK)

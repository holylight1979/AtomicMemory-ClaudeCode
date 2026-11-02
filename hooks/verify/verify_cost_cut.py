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

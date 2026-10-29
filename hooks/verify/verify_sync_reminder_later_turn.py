"""verify_sync_reminder_later_turn.py：第一回合收得乾淨（phase 變 done）之後，後面回合的改動照樣有同步提醒。

做什麼：同一份 state 依序跑 Stop（第 1 回合）→ UserPromptSubmit → Stop（第 2 回合）…，驗
- 規則 PROMPT_REOPENS_DONE：新的一則話把 done 改回 working（syncing、merged 不動）；第 2 回合改了檔沒提交 → 收尾提醒同步；
  收尾檢核 (g) 已交代 → 不擋只留 stderr；提醒過 1 次之後的回合不再提醒；續接（SessionEnd 設了 done、resume 沿用舊 state）照樣適用。
- 規則 SYNC_BLOCK_NEW_ITEMS_ONLY：底部一般 sync block（待記知識、文件漂移）同一筆在前面回合擋過就不再擋、有新的一筆才擋；
  同一回合照舊再擋。「還會擋」預覽用同一個判定：提醒額度還在 → 列同步；只剩改檔數 → 不列。
v6 開關兩態都跑（同步提醒是 v6 以前就有的閘）。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_sync_reminder_later_turn.py
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
from handlers import ups_gates  # noqa: E402
from handlers import session_start as ss  # noqa: E402
import wg_core  # noqa: E402

_SID = "sid-later"
_REAL_DETECT = st._detect_uncommitted_files
_A = "c:/p/docs/a.md"
_B = "c:/p/docs/b.md"
_C = "c:/p/docs/c.md"


@pytest.fixture()
def flow(monkeypatch, tmp_path):
    """一份 state 來回跑 UserPromptSubmit 與 Stop；回 (state, ups_run, stop_run)。
    ups_run(prompt) → 跑完 UPS（前置閘只留記原話與開回合 track_turn_prompts，其餘生產者關掉）；
    stop_run(capsys, text=…, uncommitted=True) → (stdout, stderr, guard_log)。改檔用 edit(state, *paths) 記在目前回合。"""
    import wg_friction
    import wg_need_goal
    import wg_overview
    import wg_release_rules
    state = {"phase": "working", "turn_seq": 0, "session": {"id": _SID, "cwd": str(tmp_path), "source": "startup"},
             "injected_atoms": [], "modified_files": [], "knowledge_queue": [], "failing_tests": [],
             "recent_user_prompts": [], "stop_blocked_count": 0, "scan_report_warned": True}
    logs: list = []
    for mod in (ups, st):
        monkeypatch.setattr(mod, "_ensure_state", lambda *a, **k: state)
        monkeypatch.setattr(mod, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(ups, "WORKFLOW_DIR", tmp_path)
    monkeypatch.setattr(ups, "run_pre_gates", lambda sid, s, cfg, clean, low, lines: ups_gates.track_turn_prompts(s, clean))
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

    monkeypatch.setattr(st, "_find_session_transcript", lambda *a, **k: None)
    monkeypatch.setattr(st, "token_warn_payload", lambda *a, **k: "")
    monkeypatch.setattr(st, "detect_evasion", lambda *a, **k: None)
    monkeypatch.setattr(st, "_attribute_usefulness", lambda *a, **k: None)
    monkeypatch.setattr(st, "_should_deep_postmortem", lambda *a, **k: False)
    monkeypatch.setattr(st, "_maybe_spawn_user_extract_worker", lambda *a, **k: None)
    monkeypatch.setattr(st, "_drop_synced", lambda mf: mf)     # 假路徑會被「檔與版控根都不在」剔掉；這裡只測回合與 phase
    monkeypatch.setattr(st, "_git_unpushed_roots", lambda mf: [])
    monkeypatch.setattr(st, "append_guard_log", lambda name, rec: logs.append((name, rec)))

    def ups_run(prompt, capsys):
        with pytest.raises(SystemExit):
            ups.handle_user_prompt_submit({"session_id": _SID, "prompt": prompt, "cwd": str(tmp_path)}, {})
        cap = capsys.readouterr()
        return json.loads(cap.out)["hookSpecificOutput"]["additionalContext"] if cap.out.strip() else ""

    def stop_run(capsys, text="先改到這裡，等你看過再說。", uncommitted=True, config=None):
        """uncommitted：True＝改過的檔都算沒提交、False＝都算提交了、None＝真的查 git／svn status。"""
        monkeypatch.setattr(st, "get_last_assistant_text", lambda *a, **k: text)
        monkeypatch.setattr(st, "_detect_uncommitted_files",
                            _REAL_DETECT if uncommitted is None
                            else (lambda mf: [m["path"] for m in mf]) if uncommitted else (lambda mf: []))
        logs.clear()
        with pytest.raises(SystemExit):
            st.handle_stop({"session_id": _SID, "cwd": ""}, config or {})
        cap = capsys.readouterr()
        return cap.out, cap.err, list(logs)

    return state, ups_run, stop_run


def edit(state, *paths):
    """本回合（目前的 turn_seq）改了這些檔，last_at 早於收尾檢核案例用的報告時間。"""
    t = int(state["turn_seq"])
    for p in paths:
        state["modified_files"].append({"path": p, "tool": "Edit", "session_id": _SID, "turn_seq": t,
                                        "last_turn_seq": t, "last_at": "2026-10-23T10:00:00+08:00"})


def _first_turn_question_only(state, ups_run, stop_run, capsys):
    """第 1 回合只問問題、不改檔：收尾把 phase 設成 done（前置，舊碼新碼都一樣）。"""
    ups_run("這個模組在做什麼？", capsys)
    out, _, _ = stop_run(capsys, text="它負責把設定讀進來。")
    assert "[Guardian:SyncReminder]" not in out and state["phase"] == "done", (out, state["phase"])


@pytest.fixture(params=[True, False], ids=["v6", "v6off"])
def v6(request, monkeypatch):
    monkeypatch.setenv("WG_V6", "1" if request.param else "0")
    return request.param


def test_second_turn_edit_gets_sync_reminder(flow, capsys, v6):
    """規則 PROMPT_REOPENS_DONE：第 1 回合收得乾淨（done）→ 第 2 回合改兩個檔沒提交 → 收尾提醒同步。舊碼 done 一路沿用（紅）。"""
    state, ups_run, stop_run = flow
    _first_turn_question_only(state, ups_run, stop_run, capsys)
    ups_run("幫我改 a 跟 b 兩份文件", capsys)
    edit(state, _A, _B)
    out, _, logs = stop_run(capsys)
    assert "[Guardian:SyncReminder]" in out and "偵測到 2 個" in out, out       # 舊碼紅在這裡：使用者看不到提醒
    assert state["sync_reminder_count"] == 1


def test_second_turn_closing_check_covers_sync(flow, capsys, v6):
    """同上，但第 2 回合交了收尾檢核（(g) 已交代、交了之後沒再改）→ 不擋，只留 stderr 與留帳（SYNC_COVERED_BY_CLOSING_CHECK 照舊）。
    舊碼連這道判定都沒走到（stderr 沒有那一行，紅）。"""
    state, ups_run, stop_run = flow
    _first_turn_question_only(state, ups_run, stop_run, capsys)
    ups_run("幫我改 a 跟 b 兩份文件", capsys)
    edit(state, _A, _B)
    state["anti_evasion_report"] = {"turn_seq": state["turn_seq"], "session_id": _SID, "at": "2026-10-23T10:05:00+08:00"}
    out, err, logs = stop_run(capsys)
    assert "[Guardian:SyncReminder]" not in out, out
    assert "收尾檢核 (g) 已交代" in err, err
    assert any(n == "sync_reminder" and r["event"] == "covered_by_aec" for n, r in logs), logs
    assert int(state.get("sync_reminder_count", 0)) == 0


def test_reminded_once_then_later_turns_quiet(flow, capsys, v6):
    """提醒過 1 次（max_reminders 預設 1）之後：同回合再收尾、下一回合又改了檔，都不再提醒同步；只剩改檔數也不走底部一般擋。"""
    state, ups_run, stop_run = flow
    _first_turn_question_only(state, ups_run, stop_run, capsys)
    ups_run("幫我改 a 跟 b 兩份文件", capsys)
    edit(state, _A, _B)
    out, _, _ = stop_run(capsys)
    assert "[Guardian:SyncReminder]" in out, out                                  # 前置：這回合真的提醒了
    out, err, _ = stop_run(capsys, text="改了 a、b 兩份，還沒提交，等你下口令。")
    assert "Guardian" not in out, out
    ups_run("再改 c", capsys)
    assert state["phase"] == "working"
    edit(state, _C)
    out, err, _ = stop_run(capsys, text="c 也改了，一樣等口令。")
    assert "[Guardian:SyncReminder]" not in out and "[Workflow Guardian]" not in out, out
    assert "3 file(s) modified" in err and state["sync_reminder_count"] == 1, err


def test_resumed_session_gets_sync_reminder(flow, capsys, v6):
    """續接：上一段 session 結束時 SessionEnd 設了 done 與 ended_at，claude -p --resume 開場沿用舊 state（phase 不動）→
    這一則話改回 working，改檔沒提交 → 收尾提醒同步。舊碼開場就印 Phase: done、之後都不提醒（紅）。
    這裡用 SessionEnd／SessionStart(resume) 留下的 state 形狀模擬；真的 SessionEnd → resume → 讀寫 state 檔那條路徑由無頭兩回合實跑驗。"""
    state, ups_run, stop_run = flow
    _first_turn_question_only(state, ups_run, stop_run, capsys)
    state.update({"ended_at": "2026-10-23T09:00:00+08:00", "session": {**state["session"], "source": "resume"}})
    ups_run("接著把 a 跟 b 改掉", capsys)
    edit(state, _A, _B)
    out, _, _ = stop_run(capsys)
    assert "[Guardian:SyncReminder]" in out, out
    assert state["phase"] == "working" and "ended_at" not in state, state.get("ended_at")   # 續接中不算已結束（面板清理不刪）


@pytest.mark.parametrize("phase", ["syncing", "merged"])
def test_prompt_keeps_syncing_and_merged(flow, capsys, phase):
    """syncing（同步進行中）、merged（轉址）不是「上一回合收乾淨」：新的一則話不動它。"""
    state, ups_run, _ = flow
    state["phase"] = phase
    ups_run("繼續", capsys)
    assert state["phase"] == phase


def _general_block_first_turn(state, ups_run, stop_run, capsys):
    """同步提醒額度已用掉、有 1 筆待記知識：第 1 回合改兩個檔 → 底部一般擋兩次（同一回合照舊再擋）→ 第 3 次擋滿放行收成 done。"""
    state["sync_reminder_count"] = 1
    state["knowledge_queue"] = [{"content": "某個坑", "classification": "[臨]"}]
    ups_run("幫我改 a 跟 b 兩份文件", capsys)
    edit(state, _A, _B)
    out, _, _ = stop_run(capsys)
    assert "[Workflow Guardian] 2 file(s) modified, 1 knowledge pending" in out, out
    out, _, _ = stop_run(capsys)
    assert "[Workflow Guardian]" in out, out
    stop_run(capsys)
    assert state["phase"] == "done"


def test_general_block_new_items_only(flow, capsys):
    """規則 SYNC_BLOCK_NEW_ITEMS_ONLY（v6 開：共用擋次每個使用者回合重算）：之後的回合同一筆不再擋（只留 stderr）；有新的一筆才擋。
    舊碼第 1 回合之後 done 一路沿用，新的一筆也不擋（紅）。"""
    state, ups_run, stop_run = flow
    _general_block_first_turn(state, ups_run, stop_run, capsys)
    ups_run("看一下 a 的第二段", capsys)
    out, err, _ = stop_run(capsys)
    assert "[Workflow Guardian]" not in out and "前面回合已提醒過" in err, (out, err)
    ups_run("再看 b", capsys)
    state["knowledge_queue"].append({"content": "另一個坑", "classification": "[臨]"})
    out, _, _ = stop_run(capsys)
    assert "[Workflow Guardian] 2 file(s) modified, 2 knowledge pending" in out, out


def test_general_block_same_prefix_new_item_still_blocks(flow, capsys):
    """待記知識前 200 字相同、後段不同是兩筆：前面回合擋過其中一筆，後面回合新來的那筆照擋（鍵用整段內容）。"""
    state, ups_run, stop_run = flow
    prefix = "坑" * 250
    _general_block_first_turn(state, ups_run, stop_run, capsys)
    state["knowledge_queue"] = [{"content": prefix + "甲", "classification": "[臨]"}]
    ups_run("看 a", capsys)
    out, _, _ = stop_run(capsys)
    assert "[Workflow Guardian]" in out, out
    for _ in range(2):
        stop_run(capsys)
    ups_run("看 b", capsys)
    state["knowledge_queue"].append({"content": prefix + "乙", "classification": "[臨]"})
    out, _, _ = stop_run(capsys)
    assert "[Workflow Guardian] 2 file(s) modified, 2 knowledge pending" in out, out


def test_general_block_chain_hold_does_not_mark_shown(flow, capsys, monkeypatch):
    """連鎖斷路器中止中（SyncBlock 這道只記錄不擋）：沒送到眼前的項目不記成擋過，下一回合照擋。"""
    state, ups_run, stop_run = flow
    state["sync_reminder_count"] = 1
    state["knowledge_queue"] = [{"content": "某個坑", "classification": "[臨]"}]
    ups_run("幫我改 a 跟 b 兩份文件", capsys)
    edit(state, _A, _B)
    monkeypatch.setattr(st, "_chain_gate", lambda sid, since, gate, *a, **k: gate == "SyncBlock")
    out, _, _ = stop_run(capsys)
    assert "[Workflow Guardian]" not in out and not state.get("sync_block_shown"), (out, state.get("sync_block_shown"))
    monkeypatch.setattr(st, "_chain_gate", lambda *a, **k: False)
    ups_run("繼續", capsys)
    out, _, _ = stop_run(capsys)
    assert "[Workflow Guardian] 2 file(s) modified, 1 knowledge pending" in out, out


def test_general_block_drift_again_after_resolved(flow, capsys):
    """文件漂移擋過、補了文件（pending 清掉）、後面回合同一個來源又改 → 新的一筆漂移照擋；解決掉的不留在 sync_block_shown。"""
    state, ups_run, stop_run = flow
    state["sync_reminder_count"] = 1
    state["docdrift_pending"] = {"docs/a.md→Arch.md": {"source": "docs/a.md", "doc": "Arch.md", "added_at": "2026-10-23T10:00:00+08:00"}}
    ups_run("幫我改 a 跟 b 兩份文件", capsys)
    edit(state, _A, _B)
    out, _, _ = stop_run(capsys)
    assert "[Workflow Guardian]" in out and "[DocDrift]" in out, out
    for _ in range(2):
        stop_run(capsys)
    ups_run("補 Arch.md", capsys)
    state["docdrift_pending"] = {}                                                 # resolve_doc_update 清掉
    state["knowledge_queue"] = [{"content": "某個坑", "classification": "[臨]"}]
    out, _, _ = stop_run(capsys)
    assert "[Workflow Guardian]" in out, out
    assert not [k for k in state["sync_block_shown"] if k.startswith("drift:")], state["sync_block_shown"]   # 解決掉的漂移不留
    for _ in range(2):
        stop_run(capsys)
    ups_run("再改 a", capsys)
    state["docdrift_pending"] = {"docs/a.md→Arch.md": {"source": "docs/a.md", "doc": "Arch.md", "added_at": "2026-10-23T11:00:00+08:00"}}
    out, _, _ = stop_run(capsys)
    assert "[Workflow Guardian]" in out and "[DocDrift]" in out, out


def test_reopen_written_before_slow_steps(flow, capsys, monkeypatch):
    """UPS 在檢索、注入途中被砍（逾時）也不留舊的 done：改回 working 那一刻就寫回 state 檔。"""
    state, ups_run, stop_run = flow
    _first_turn_question_only(state, ups_run, stop_run, capsys)
    state["ended_at"] = "2026-10-23T09:00:00+08:00"
    written = []
    monkeypatch.setattr(ups, "write_state", lambda sid, s: written.append((s.get("phase"), "ended_at" in s)))

    def killed(*a, **k):
        raise RuntimeError("hook 被砍")
    monkeypatch.setattr(ups, "build_context", killed)
    with pytest.raises(RuntimeError):
        ups.handle_user_prompt_submit({"session_id": _SID, "prompt": "改 a", "cwd": ""}, {})
    assert written and written[0] == ("working", False), written


def test_preview_lists_sync_block_even_when_closing_check_covers(flow, capsys, monkeypatch):
    """收尾檢核 (g) 已交代只免同步提醒：還有沒擋過的待記知識時，「還會擋」預覽照列（底部一般擋不看收尾檢核，之後真的會擋）。"""
    state, ups_run, stop_run = flow
    monkeypatch.setattr(st, "coding_turn", lambda *a, **k: True)
    monkeypatch.setattr(st, "deferral_gate_reason", lambda *a, **k: "[Guardian:DeferralGate] 把可做的事推給下個 session")
    monkeypatch.setattr(st, "detect_missing_aec_emission", lambda *a, **k: False)
    ups_run("幫我改 a 跟 b 兩份文件", capsys)
    edit(state, _A, _B)
    state["anti_evasion_report"] = {"turn_seq": state["turn_seq"], "session_id": _SID, "at": "2026-10-23T10:05:00+08:00"}
    out, _, _ = stop_run(capsys, text="好了。")
    assert "DeferralGate" in out and "同步：" not in out, out                     # 前置：只剩改檔數、(g) 已交代 → 不列
    state["knowledge_queue"] = [{"content": "某個坑", "classification": "[臨]"}]
    out, _, _ = stop_run(capsys, text="好了。")
    assert "DeferralGate" in out and "同步：1 筆待記知識或文件漂移" in out, out


def _rebuilt_like_session_start(existing):
    """照 session_start 專案根指紋變了的重建分支做一份新 state：new_state、_CARRY_ON_REBUILD 照搬（含回合序號）、phase 沿用。"""
    new = wg_core.new_state(_SID, existing["session"]["cwd"], "resume")
    for key in ss._CARRY_ON_REBUILD:
        if key in existing:
            new[key] = existing[key]
    new["phase"] = existing.get("phase", "working")
    return {**new, "injected_atoms": [], "failing_tests": [], "recent_user_prompts": [], "scan_report_warned": True}


def test_rebuilt_state_does_not_remind_again(flow, capsys):
    """同步提醒過、底部一般擋也擋過，之後開場重建 state（專案根指紋變了）→ 同一個 session 不再提醒同步、同一筆待記知識不再擋。
    舊碼重建時沒搬提醒額度與擋過的項目（紅）。"""
    state, ups_run, stop_run = flow
    state["knowledge_queue"] = [{"content": "某個坑", "classification": "[臨]"}]
    ups_run("幫我改 a 跟 b 兩份文件", capsys)
    edit(state, _A, _B)
    out, _, _ = stop_run(capsys)
    assert "[Guardian:SyncReminder]" in out, out
    out, _, _ = stop_run(capsys)
    assert "[Workflow Guardian]" in out, out                                       # 前置：一般擋擋過這筆待記知識
    stop_run(capsys)
    rebuilt = _rebuilt_like_session_start(state)
    state.clear()
    state.update(rebuilt)
    ups_run("再改 c", capsys)
    edit(state, _C)
    out, err, _ = stop_run(capsys)
    assert "[Guardian:SyncReminder]" not in out and "[Workflow Guardian]" not in out, out
    assert state["sync_reminder_count"] == 1 and "前面回合已提醒過" in err, err


@pytest.mark.parametrize("kq, drift, unsynced, shown, uturn, want", [
    ([], {}, 3, {}, 5, []),                                                          # 只剩改檔數：歸同步提醒
    ([], {"a.py→Arch.md": {}}, 1, {}, 5, []),                                        # 文件漂移但改檔不到門檻：不擋
    ([], {"a.py→Arch.md": {"added_at": "t1"}}, 2, {}, 5, ["drift:a.py→Arch.md@t1"]),
    (["字串項目"], {}, 0, {}, 5, ["kq:"]),                                            # 待記知識不看改檔數；字串項目也認
    ([{"content": "坑"}], {"d": {}}, 0, {}, 5, ["kq:", "drift:d@"]),                  # 有待記知識：漂移一起列
    ([{"content": "坑"}], {}, 2, "earlier", 5, []),                                  # 前面回合擋過
    ([{"content": "坑"}], {}, 2, "same", 5, ["kq:"]),                                # 同一回合擋過：照舊可再擋
])
def test_sync_block_items_cases(kq, drift, unsynced, shown, uturn, want):
    """SYNC_BLOCK_NEW_ITEMS_ONLY 的判定本身（跟原本底部三道早退同一組條件）；sync_block_shown 走一趟 JSON 照樣認。"""
    state = {"knowledge_queue": kq, "docdrift_pending": drift}
    if isinstance(shown, str):
        key = st._sync_block_items(state, unsynced, 2, uturn)[0]
        state["sync_block_shown"] = json.loads(json.dumps({key: st._turn_mark(state, uturn - 1 if shown == "earlier" else uturn)}))
    got = st._sync_block_items(state, unsynced, 2, uturn)
    assert [g if g.startswith("drift:") else g[:3] for g in got] == want, got


def test_general_block_session_budget_when_v6_off(flow, capsys, monkeypatch):
    """v6 關：共用擋次照 9e476fd0 整個 session 累計，用完之後的回合有新的一筆也不擋（phase 改回 working 不放寬這份預算）。"""
    monkeypatch.setenv("WG_V6", "0")
    state, ups_run, stop_run = flow
    _general_block_first_turn(state, ups_run, stop_run, capsys)
    ups_run("再看 b", capsys)
    state["knowledge_queue"].append({"content": "另一個坑", "classification": "[臨]"})
    out, _, _ = stop_run(capsys)
    assert "Guardian" not in out and state["phase"] == "done", out


def test_later_turn_preview_lists_sync_only_when_owed(flow, capsys, monkeypatch):
    """「還會擋」預覽（BLOCK_LISTS_LATER_GATES）在後面回合也看得到同步：提醒額度還在 → 列；額度用完、只剩改檔數 → 不列
    （底部只留 stderr，列了是誤報）。舊碼後面回合 done，額度還在也不列（紅）。"""
    state, ups_run, stop_run = flow
    _first_turn_question_only(state, ups_run, stop_run, capsys)
    monkeypatch.setattr(st, "coding_turn", lambda *a, **k: True)
    monkeypatch.setattr(st, "deferral_gate_reason", lambda *a, **k: "[Guardian:DeferralGate] 把可做的事推給下個 session")
    monkeypatch.setattr(st, "detect_missing_aec_emission", lambda *a, **k: False)
    ups_run("幫我改 a 跟 b 兩份文件", capsys)
    edit(state, _A, _B)
    out, _, _ = stop_run(capsys, text="好了。")
    assert "DeferralGate" in out and "[Guardian:AlsoOwed]" in out, out
    assert "同步：2 個改過的檔" in out.split("[Guardian:AlsoOwed]", 1)[1], out
    state["sync_reminder_count"] = 1
    out, _, _ = stop_run(capsys, text="好了。")
    assert "DeferralGate" in out and "同步：" not in out, out


def test_unknown_write_recovered_gets_sync_reminder(flow, capsys, tmp_path, monkeypatch):
    """規則 UNKNOWN_WRITE_RECOVERED：第 2 回合 AI 只用 `cd 專案 && python -I -c "…open(p,'w')…"` 改 notify/sender.py（寫入目標判不出），
    真的 PostToolUse 從 git status 補進 modified_files → 收尾照真的 git status 判未提交：對帳閘先擋（改了程式欠案例），預覽列出同步；
    對帳與驗證範圍關掉時同步提醒自己擋。舊碼：modified_files 空、兩道都不擋（紅）。（v6 開才記 Bash 的寫入目標，這案只跑 v6 開）"""
    from verify_unknown_write_recover import NOTIFY, PY_C_SENDER, bash_unknown_write, init_repo, py_c
    state, ups_run, stop_run = flow
    _first_turn_question_only(state, ups_run, stop_run, capsys)
    ups_run("把重試次數改成 6", capsys)
    repo = init_repo(tmp_path / "qs3-notify", NOTIFY)
    bash_unknown_write(monkeypatch, repo, state, py_c(repo, PY_C_SENDER), PY_C_SENDER, sid=_SID)
    out, _, _ = stop_run(capsys, uncommitted=None)
    assert "改了程式碼（sender.py）" in out and "同步：1 個改過的檔還沒 commit" in out, out
    out, _, _ = stop_run(capsys, uncommitted=None,
                         config={"reconcile_gate": {"enabled": False}})
    assert "[Guardian:SyncReminder]" in out and "偵測到 1 個" in out, out


@pytest.fixture(autouse=True)
def _block_mode(monkeypatch):
    """規則 GATE_MODE_TABLE：送法只讀 wg_release_rules.RULE_MODE。這個檔的案例驗的是判定與擋訊息內容，把送法釘成 block 讓它們照驗；
    v6 預設的提醒送法（Stop 只留帳、提醒掛改檔那則工具結果）由 verify_gate_mode_stop.py 驗。"""
    import wg_release_rules as _rr
    monkeypatch.setattr(_rr, "mode_of", lambda rule: _rr.BLOCK)

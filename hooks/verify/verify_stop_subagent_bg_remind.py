"""verify_stop_subagent_bg_remind.py：收尾跟上 Claude Code 新輸入欄位的兩件（規則 SUBAGENT_RESULT_FROM_SUBAGENT_STOP、
STOP_DEFERS_WHILE_BACKGROUND_RUNNING），加上提醒類閘在 Stop 只留帳（STOP_REMIND_LEDGER_ONLY）的回歸守門。

做什麼：
1. 子代理注入的效用帳：背景子代理的 PostToolUse(Agent) 只拿到 async_launched、沒有內容 → SubagentStop 依 agent_id 回填
   last_assistant_message；Stop 結算時還沒收到的標 waiting（不是 no_output），收到之後才結；寫碼守門關時 dispatcher 照樣分派
   SubagentStop（真入口子行程跑一次 PostToolUse＋SubagentStop）。
2. Stop 輸入帶 background_tasks／session_crons：紅測閘、寫碼查核照擋；同步閘與效用歸因延後、guard-stop_background 留 skip；
   同一個背景項目連延 5 次之後照擋（cap）；清單沒有的項目歸零。
3. 提醒類閘：Stop 只留帳（guard log event=remind），不送 hookSpecificOutput.additionalContext（官方會因此續跑一回合）；
   擋的出口也不帶；寫碼守門關照擋；子代理收尾同一套。
怎麼跑：python -X utf8 -m pytest -q -p no:cacheprovider hooks/verify/verify_stop_subagent_bg_remind.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1]
CLAUDE = HOOKS_DIR.parent
for _p in (str(HOOKS_DIR), str(CLAUDE), str(CLAUDE / "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import dispatcher  # noqa: E402
import wg_atoms  # noqa: E402
from lib import atom_access as A  # noqa: E402
from handlers import stop as st  # noqa: E402
from handlers.post_tool_use import _record_subagent_injection  # noqa: E402

SID = "sid-w1-bg"
CODE = r"c:\proj\hooks\x.py"
DONE = "改好了，全部完成。"
DEFER_DONE = "改好了，全部完成。剩下的 verify 清理留給下個 session 處理。"
OFF = {"enabled": False}
BG_SUB = {"id": "t1", "type": "subagent", "status": "running", "description": "跑 verify", "agent_type": "Explore"}
PROMPT = "[WG:SubagentMemory] 測試 atoms=atom-x\n\n實際任務"
ATOM_BODY = (
    "# atom-x\n"
    "- [臨] atom_write 兩個防護缺口：mode=replace 無閘 silent upsert；"
    "server.js 新增 findSeparatorVariant(memDir, slug) 守門，create 命中變體即擋。"
    "lib/atom_spec.py 規則唯一來源，改全域 MCP server 需重啟生效。\n"
)
USED = ("我新增了 findSeparatorVariant 到 server.js 並守住 atom_write 的 replace 路徑，"
        "編輯 tools/workflow-guardian-mcp/server.js 與 lib/atom_spec.py。")
ATTR_CFG = {"usefulness": {"enabled": True, "rare_token_min": 2, "lexical_overlap_min": 0.18, "attribution_policy": "v1"}}


def _async_post_tool_use(agent_id="ag-1"):
    """背景子代理派出那一刻的 PostToolUse(Agent)：tool_response 只有 status／agentId／prompt／outputFile，沒有 content。"""
    return {"tool_name": "Agent", "tool_use_id": "toolu_bg", "tool_input": {"prompt": PROMPT},
            "tool_response": {"status": "async_launched", "agentId": agent_id, "prompt": PROMPT, "outputFile": "o.txt"}}


def _mf(path=CODE, turn=5, sid=SID, seq=10):
    return {"path": path, "tool": "Edit", "session_id": sid, "turn_seq": turn, "last_turn_seq": turn, "last_seq": seq,
            "at": "2026-11-04T10:00:00", "last_at": "2026-11-04T10:00:00"}


def _payload(out: str):
    lines = [ln for ln in out.strip().splitlines() if ln.strip()]
    return json.loads(lines[-1]) if lines else {}


@pytest.fixture(autouse=True)
def _silence_audit(monkeypatch):
    monkeypatch.setattr(A, "_audit_log", lambda *a, **k: None)


@pytest.fixture
def atom_md(tmp_path, monkeypatch):
    p = tmp_path / "atom-x.md"
    p.write_text(ATOM_BODY, encoding="utf-8")
    monkeypatch.setattr(wg_atoms, "resolve_atom_path", lambda name: p if name == "atom-x" else None)
    return p


@pytest.fixture
def drive(monkeypatch, capsys):
    """驅動 handle_stop：拿掉碰外部的副作用（transcript、git、HUD、state 檔），閘本身照跑。
    run(text, config, hook, state=None, **state 欄位) → (輸出 JSON 或 {}, state, guard log 事件)；state 給了就沿用同一份（連續收尾）。
    run.attributed 記 _attribute_usefulness 被叫幾次。"""
    logs: list = []
    attributed: list = []
    for name, fn in (("_find_session_transcript", lambda *a, **k: None), ("token_warn_payload", lambda *a, **k: ""),
                     ("write_state", lambda *a, **k: None), ("_attribute_usefulness", lambda *a, **k: attributed.append(1)),
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

    def run(text, config=None, hook=None, state=None, **extra):
        monkeypatch.setattr(st, "get_last_assistant_text", lambda *a, **k: text)
        monkeypatch.setattr(st, "get_current_turn_visible_text", lambda *a, **k: ("", {"turn_tool_names_all": []}))
        if state is None:
            state = {"phase": "working", "modified_files": [], "failing_tests": [], "recent_user_prompts": [],
                     "stop_blocked_count": 0, "turn_seq": 5, "turn_prompts_seq": 5, **extra}
        monkeypatch.setattr(st, "_ensure_state", lambda *a, **k: state)
        cfg = {"reconcile_gate": OFF, "aec": {"scan_report_gate": False}, "atom_audit": OFF,
               "sync_reminder": OFF, "deferral_gate": OFF, "knowledge_harvest": OFF, **(config or {})}
        logs.clear()
        attributed.clear()
        capsys.readouterr()
        with pytest.raises(SystemExit):
            st.handle_stop({"session_id": SID, "cwd": "", "last_assistant_message": text, **(hook or {})}, cfg)
        cap = capsys.readouterr()
        run.err = cap.err
        run.attributed = len(attributed)
        return _payload(cap.out), state, list(logs)

    return run


def _subagent_stop(monkeypatch, capsys, state, agent_id, text, config=None):
    monkeypatch.setattr(st, "read_state", lambda *a, **k: state)
    monkeypatch.setattr(st, "write_state", lambda *a, **k: None)
    capsys.readouterr()
    with pytest.raises(SystemExit):
        st.handle_subagent_stop({"session_id": SID, "agent_id": agent_id, "hook_event_name": "SubagentStop",
                                 "last_assistant_message": text, "agent_transcript_path": ""}, config or {})
    return _payload(capsys.readouterr().out)


# ─── 1. 子代理注入的效用帳（SUBAGENT_RESULT_FROM_SUBAGENT_STOP） ─────────────────────────────

def test_subagent_stop_fills_async_launched_record(monkeypatch, capsys):
    """PostToolUse(Agent) 只拿到 async_launched → 紀錄摘要是空的；SubagentStop 依 agent_id 回填最後回覆（截 400 字）、
    status 改 completed、記收到結果的回合，沒有 skipped。"""
    state = {"turn_seq": 3, "turn_prompts_seq": 3}
    assert _record_subagent_injection(state, _async_post_tool_use())
    rec = state["subagent_injections"][0]
    assert rec["status"] == "async_launched" and rec["output_summary"] == "" and rec["agent_id"] == "ag-1"
    _subagent_stop(monkeypatch, capsys, state, "ag-1", "查完了。" + "結" * 600)
    assert rec["status"] == "completed" and rec["output_summary"].startswith("查完了。")
    assert len(rec["output_summary"]) == st.SUBAGENT_RESULT_CAP == 400
    assert rec["result_turn_seq"] == 3 and "skipped" not in rec and not rec.get("attributed")


def test_subagent_stop_unknown_agent_untouched(monkeypatch, capsys):
    """對不到 agent_id（內部子代理、沒注入卡）→ 紀錄不動。"""
    state = {"turn_seq": 3}
    _record_subagent_injection(state, _async_post_tool_use())
    _subagent_stop(monkeypatch, capsys, state, "someone-else", "別人的回覆")
    assert state["subagent_injections"][0]["status"] == "async_launched"
    assert state["subagent_injections"][0]["output_summary"] == ""


def test_stop_marks_waiting_then_attributes_when_result_arrives(atom_md):
    """Stop 結算時背景子代理還沒收尾 → 標 waiting、不結、不標 no_output；同一回合後來收到結果 → 下一次 Stop 照結
    （本 turn 已結算過也照結這筆），outcome 計數不重算。"""
    state = {"turn_seq": 3, "turn_prompts_seq": 3, "turn_injected": []}
    _record_subagent_injection(state, _async_post_tool_use())
    rec = state["subagent_injections"][0]
    before = A.read_access(atom_md)["useful_hits"]
    st._attribute_usefulness(state, ATTR_CFG, SID, None, "已完成")
    assert rec.get("waiting") is True and not rec.get("attributed") and "skipped" not in rec
    assert A.read_access(atom_md)["useful_hits"] == before
    assert st._fill_subagent_result(state, "ag-1", USED)
    st._attribute_usefulness(state, ATTR_CFG, SID, None, "已完成")
    assert rec["attributed"] is True and "skipped" not in rec and "waiting" not in rec
    assert A.read_access(atom_md)["useful_hits"] == before + 1
    assert sum(state["outcome_stats"].values()) == 1, "同一 turn 第二次結算不重算 outcome"


def test_result_in_later_user_turn_still_attributed(atom_md):
    """派出在第 3 回合、結果在使用者第 5 回合才收到 → 看收到的回合，照結（舊判法會標 stale_turn）。"""
    state = {"turn_seq": 3, "turn_prompts_seq": 3, "turn_injected": []}
    _record_subagent_injection(state, _async_post_tool_use())
    state.update(turn_seq=5, turn_prompts_seq=5)
    assert st._fill_subagent_result(state, "ag-1", USED)
    st._attribute_usefulness(state, ATTR_CFG, SID, None, "已完成")
    rec = state["subagent_injections"][0]
    assert rec["attributed"] is True and "skipped" not in rec and rec["result_turn_seq"] == 5


def test_empty_last_message_is_no_output_not_waiting(atom_md):
    """收到結果但最後回覆是空的 → 照實標 no_output（收到了、沒內容），不是 waiting。"""
    state = {"turn_seq": 3, "turn_prompts_seq": 3, "turn_injected": []}
    _record_subagent_injection(state, _async_post_tool_use())
    st._fill_subagent_result(state, "ag-1", "")
    st._attribute_usefulness(state, ATTR_CFG, SID, None, "已完成")
    rec = state["subagent_injections"][0]
    assert rec["skipped"] == "no_output" and "waiting" not in rec


def test_v6_off_subagent_stop_records_without_code_gate(monkeypatch, capsys):
    """寫碼守門關：dispatcher 分派 SubagentStop；handler 只回填效用帳，不跑寫碼查核（說修好沒 PASS 也不擋）。"""
    monkeypatch.setenv("WG_V6", "0")
    assert dispatcher._pre_v6_skips("SubagentStop", {}) is False
    state = {"turn_seq": 3, "turn_prompts_seq": 3, "agent_modified_files": {"ag-1": [_mf()]}}
    _record_subagent_injection(state, _async_post_tool_use())
    out = _subagent_stop(monkeypatch, capsys, state, "ag-1", "閘修好了，完成。", {"reconcile_gate": {"enabled": True}})
    assert out == {}, out
    assert state["subagent_injections"][0]["output_summary"] == "閘修好了，完成。"


def test_e2e_dispatcher_post_tool_use_then_subagent_stop_v6_off(tmp_path):
    """真入口子行程：守門關，PostToolUse(Agent async_launched) → SubagentStop → state 檔那筆 output_summary 非空、無 skipped；兩次都不輸出。"""
    env = {k: v for k, v in os.environ.items() if k not in ("WG_V6", "CLAUDE_COMPANION_JUDGE", "PYTEST_CURRENT_TEST")}
    env.update({"WG_CLAUDE_DIR": str(tmp_path), "WG_TEST_LOGS_DIR": str(tmp_path / "Logs"), "WG_V6": "0"})
    proj = tmp_path / "proj"
    proj.mkdir()
    sid = "sid-w1-e2e"

    def run(inp):
        r = subprocess.run([sys.executable, str(HOOKS_DIR / "workflow-guardian.py")], input=json.dumps(inp).encode(),
                           env=env, cwd=proj, capture_output=True, timeout=120)
        assert r.returncode == 0 and r.stdout.strip() == b"", (r.stdout, r.stderr[-600:])

    run({"hook_event_name": "PostToolUse", "session_id": sid, "cwd": str(proj), **_async_post_tool_use()})
    run({"hook_event_name": "SubagentStop", "session_id": sid, "cwd": str(proj), "agent_id": "ag-1",
         "agent_type": "Explore", "last_assistant_message": "查完了：三個檔都改好。", "agent_transcript_path": ""})
    recs = json.loads((tmp_path / "workflow" / f"state-{sid}.json").read_text(encoding="utf-8"))["subagent_injections"]
    assert len(recs) == 1 and recs[0]["output_summary"] == "查完了：三個檔都改好。"
    assert recs[0]["status"] == "completed" and "skipped" not in recs[0]


# ─── 2. 等背景工作（STOP_DEFERS_WHILE_BACKGROUND_RUNNING） ─────────────────────────────

def _bg_logs(logs, event=None):
    return [p for g, p in logs if g == st.BG_LOG and (event is None or p.get("event") == event)]


def test_bg_running_defers_sync_gate(drive, monkeypatch):
    """守門關（同步閘照擋的模式）：沒有背景工作 → 同步閘擋；Stop 輸入帶 running subagent → 放行、guard log 一筆 skip、
    同步提醒次數沒吃掉、效用歸因延後。"""
    monkeypatch.setenv("WG_V6", "0")
    monkeypatch.setattr(st, "_detect_uncommitted_files", lambda mf: [CODE])
    cfg = {"sync_reminder": {"enabled": True}}
    out, _, _ = drive(DONE, config=cfg, modified_files=[_mf()])
    assert out.get("decision") == "block" and "[Guardian:SyncReminder]" in out["reason"], out
    out, state, logs = drive(DONE, config=cfg, hook={"background_tasks": [BG_SUB], "session_crons": []}, modified_files=[_mf()])
    assert "decision" not in out, (out, drive.err)
    skips = _bg_logs(logs, "skip")
    assert len(skips) == 1 and skips[0]["rule"] == "STOP_DEFERS_WHILE_BACKGROUND_RUNNING" and skips[0]["counts"] == {"task:t1": 1}
    assert state["bg_defer_counts"] == {"task:t1": 1} and int(state.get("sync_reminder_count", 0)) == 0
    assert drive.attributed == 0, "效用歸因延到背景工作回報那次收尾"
    assert "STOP_DEFERS_WHILE_BACKGROUND_RUNNING" in drive.err


def test_bg_defer_cap_then_blocks_and_resets(drive, monkeypatch):
    """同一個背景項目連延 5 次 → 第 6 次照擋（guard log cap）；換一個新項目又可以延（舊的歸零）；清單空了計數拿掉。"""
    monkeypatch.setenv("WG_V6", "0")
    monkeypatch.setattr(st, "_detect_uncommitted_files", lambda mf: [CODE])
    cfg = {"sync_reminder": {"enabled": True, "max_reminders": 9}}
    state = None
    for i in range(st.BG_DEFER_MAX):
        out, state, logs = drive(DONE, config=cfg, hook={"background_tasks": [BG_SUB]}, state=state, modified_files=[_mf()])
        assert "decision" not in out and _bg_logs(logs, "skip"), (i, out)
    assert state["bg_defer_counts"] == {"task:t1": st.BG_DEFER_MAX}
    out, state, logs = drive(DONE, config=cfg, hook={"background_tasks": [BG_SUB]}, state=state)
    assert out.get("decision") == "block" and "[Guardian:SyncReminder]" in out["reason"], out
    assert _bg_logs(logs, "cap") and not _bg_logs(logs, "skip")
    cron = {"id": "c1", "schedule": "*/5 * * * *", "recurring": True, "prompt": "看信"}
    out, state, logs = drive(DONE, config=cfg, hook={"background_tasks": [], "session_crons": [cron]}, state=state)
    assert "decision" not in out and state["bg_defer_counts"] == {"cron:c1": 1}, out
    drive(DONE, config=cfg, hook={"background_tasks": [], "session_crons": []}, state=state)
    assert "bg_defer_counts" not in state


def test_bg_running_keeps_red_test_gate(drive):
    """紅測閘看的是「說了完成」：背景工作還在跑也照擋，不走延後。"""
    red = [{"session_id": SID, "cmd": "python -m pytest -q hooks/verify/verify_x.py", "summary": "1 failed", "turn_seq": 5}]
    out, _, logs = drive(DONE, hook={"background_tasks": [BG_SUB]}, failing_tests=red)
    assert out.get("decision") == "block" and "[Guardian:TestFailGate]" in out["reason"]
    assert not _bg_logs(logs)


def test_bg_running_keeps_reconcile_gate(drive):
    """寫碼查核（說修好要有 PASS）也照擋：背景工作還在跑不延。"""
    out, _, logs = drive("閘修好了，完成。", config={"reconcile_gate": {"enabled": True}},
                         hook={"background_tasks": [BG_SUB]}, modified_files=[_mf()])
    assert out.get("decision") == "block" and "CLAIM_FIXED_NEEDS_PASS" in out["reason"], out
    assert not _bg_logs(logs)


# ─── 3. 提醒類閘在 Stop 只留帳、不送（STOP_REMIND_LEDGER_ONLY） ─────────────────────────────
# Stop 的 hookSpecificOutput.additionalContext 照官方會讓回合續跑一次，代價跟擋一樣，所以提醒不走它

def _reminds(logs):
    return [p for _, p in logs if p.get("event") == "remind"]


def test_remind_logged_not_sent(drive):
    """退縮歸屬（寫碼守門開＝提醒）：不擋、不送 additionalContext（不續跑）；guard log event=remind 照寫，一回合一次的記號照記。"""
    out, state, logs = drive(DEFER_DONE, config={"deferral_gate": {"enabled": True}}, modified_files=[_mf()])
    assert out == {}, out
    assert any(p["rule"] == "DEFERRAL_OF_DOABLE_WORK" for p in _reminds(logs))
    assert state["deferral_gate_turn"] == 5 and state["stop_blocked_count"] == 0


def test_repeated_remind_never_sent(drive):
    """寫碼查核 (b) 說量了沒 DONE 每次收尾都重判：每次都只留帳，輸出一直是空的。"""
    cfg = {"reconcile_gate": {"enabled": True}}
    out, state, logs = drive("我量了，完成。", config=cfg, modified_files=[_mf()])
    assert out == {} and [p["rule"] for p in _reminds(logs)] == ["CLAIM_MEASURED_NEEDS_DONE"], (out, logs)
    out, state, logs = drive("我量了，完成。", config=cfg, state=state)
    assert out == {} and [p["rule"] for p in _reminds(logs)] == ["CLAIM_MEASURED_NEEDS_DONE"], (out, logs)


def test_block_exit_has_no_remind_context(drive):
    """同一批：(a) 說修好沒 PASS 照擋、擋訊息不含 (b)；(b) 只留帳，擋的出口也不帶 additionalContext。"""
    out, _, logs = drive("閘修好了，我量了，完成。", config={"reconcile_gate": {"enabled": True}}, modified_files=[_mf()])
    assert out.get("decision") == "block" and "CLAIM_FIXED_NEEDS_PASS" in out["reason"], out
    assert "CLAIM_MEASURED_NEEDS_DONE" not in out["reason"] and "hookSpecificOutput" not in out
    assert [p["rule"] for p in _reminds(logs)] == ["CLAIM_MEASURED_NEEDS_DONE"]


def test_v6_off_no_remind_context(drive, monkeypatch):
    """寫碼守門關：退縮閘照擋（9e476fd0 原樣），沒有 additionalContext。"""
    monkeypatch.setenv("WG_V6", "0")
    out, _, _ = drive(DEFER_DONE, config={"deferral_gate": {"enabled": True}}, modified_files=[_mf()])
    assert out.get("decision") == "block" and "[Guardian:DeferralGate]" in out["reason"]
    assert "hookSpecificOutput" not in out


def test_subagent_stop_reminds_ledger_only(monkeypatch, capsys):
    """子代理收尾的提醒同一套：只留帳，不擋、不送。"""
    logs: list = []
    monkeypatch.setattr(st, "append_guard_log", lambda guard, payload: logs.append((guard, payload)))
    state = {"turn_seq": 5, "turn_prompts_seq": 5, "modified_files": [], "agent_modified_files": {"ag1": [_mf()]}}
    out = _subagent_stop(monkeypatch, capsys, state, "ag1", "我量了，完成。", {"reconcile_gate": {"enabled": True}})
    assert out == {}, out
    assert any(p.get("rule") == "CLAIM_MEASURED_NEEDS_DONE" for p in _reminds(logs))

"""verify_v6_switch.py — 寫碼守門總開關（wg_core.v6_enabled，預設關）的案例。

做什麼：
1. 開關三態：預設關、環境變數 WG_CODING_GUARD=1 開、workflow/config.local.json 寫 coding_guard.enabled=true 開
   （WG_CODING_GUARD=0 蓋過 local）；舊名 WG_V6／舊鍵 v6.enabled 仍認、新名優先；MCP 端 lib/paths.js v6Enabled 同三態（沒裝 node 跳過）。
2. 關閉時寫碼守門的閘不擋：把閘換成「必擋」替身，關閉時分派點不呼叫（不擋）、打開時照擋——PreToolUse 動資料檔宣告閘、
   改舊測試閘，Stop 對帳閘、拐彎判斷閘，PostToolUse 需求目標提示；dispatcher 不分派 v6 才有的事件／工具／裁判子 session。
3. 關閉時寫碼守門關時也跑的處理照跑：子代理記憶注入、知識收割擋（不走背景收割）、收割驗過後 vcs-sync、語言守門。
怎麼跑：
  python -X utf8 -m pytest -q hooks/verify/verify_v6_switch.py
  python -X utf8 hooks/verify/verify_v6_switch.py          # 尾行 V6_SWITCH_CHECK PASS|FAIL
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
REPO = HOOKS_DIR.parent
sys.path.insert(0, str(HOOKS_DIR))

import dispatcher  # noqa: E402
import wg_core  # noqa: E402
from handlers import post_tool_use as ptu  # noqa: E402
from handlers import pre_tool_use as pre  # noqa: E402
from handlers import stop as st  # noqa: E402

_SID = "sid-v6"
_DONE = "全部完成了，測試都跑過。"


def _set_v6(monkeypatch, on):
    monkeypatch.setenv("WG_V6", "1" if on else "0")


# ─── 1. 開關三態 ─────────────────────────────────────────────────

@pytest.fixture
def cfg_root(monkeypatch, tmp_path):
    """load_config 改讀 tmp 的 config.json／config.local.json；WG_CODING_GUARD／WG_V6 清掉。"""
    wf = tmp_path / "workflow"
    wf.mkdir()
    (wf / "config.json").write_text(json.dumps({"enabled": True}), encoding="utf-8")
    monkeypatch.setattr(wg_core, "CONFIG_PATH", wf / "config.json")
    monkeypatch.setattr(wg_core, "CONFIG_LOCAL_PATH", wf / "config.local.json")
    monkeypatch.delenv("WG_V6", raising=False)
    monkeypatch.delenv("WG_CODING_GUARD", raising=False)
    return wf


def test_default_is_off(cfg_root):
    assert wg_core.v6_enabled(wg_core.load_config()) is False


def test_repo_config_ships_off():
    shipped = json.loads((REPO / "workflow" / "config.json").read_text(encoding="utf-8"))
    assert shipped["coding_guard"]["enabled"] is False
    assert "v6" not in shipped, "出廠設定只留新鍵 coding_guard；舊鍵 v6 只在讀取端相容"
    ignored = subprocess.run(["git", "-C", str(REPO), "check-ignore", "-q", "workflow/config.local.json"])
    assert ignored.returncode == 0, "workflow/config.local.json 要進 .gitignore"


@pytest.mark.parametrize("name", ["WG_CODING_GUARD", "WG_V6"])
def test_env_turns_on(cfg_root, monkeypatch, name):
    monkeypatch.setenv(name, "1")
    assert wg_core.v6_enabled(wg_core.load_config()) is True


def test_new_key_turns_on_and_new_env_zero_overrides(cfg_root, monkeypatch):
    """新鍵 coding_guard.enabled=true 開；WG_CODING_GUARD=0 壓過 config 關，也壓過舊名 WG_V6=1。"""
    (cfg_root / "config.local.json").write_text(json.dumps({"coding_guard": {"enabled": True}}), encoding="utf-8")
    cfg = wg_core.load_config()
    assert cfg["coding_guard"]["enabled"] is True and wg_core.v6_enabled(cfg) is True
    monkeypatch.setenv("WG_V6", "1")
    monkeypatch.setenv("WG_CODING_GUARD", "0")
    assert wg_core.v6_enabled(cfg) is False


def test_old_key_still_turns_on_beside_shipped_new_key(cfg_root):
    """出廠 config.json 已改成 coding_guard.enabled=false；舊的 config.local.json 只寫 v6.enabled=true 照樣能開（相容）。
    子鍵 coding_turn_only／slim_reminders：coding_guard 有寫就用它、沒寫才讀 v6。"""
    (cfg_root / "config.json").write_text(json.dumps({"coding_guard": {"enabled": False}}), encoding="utf-8")
    (cfg_root / "config.local.json").write_text(json.dumps({"v6": {"enabled": True, "coding_turn_only": False}}), encoding="utf-8")
    cfg = wg_core.load_config()
    assert wg_core.v6_enabled(cfg) is True
    assert wg_core.coding_guard_opt(cfg, "coding_turn_only", True) is False
    assert wg_core.coding_guard_opt({"coding_guard": {"coding_turn_only": True}, "v6": {"coding_turn_only": False}}, "coding_turn_only") is True
    assert wg_core.coding_turn({"turn_seq": 5}, {"coding_guard": {"coding_turn_only": False}})


def test_local_file_turns_on_and_env_zero_wins(cfg_root, monkeypatch):
    (cfg_root / "config.local.json").write_text(json.dumps({"v6": {"enabled": True}}), encoding="utf-8")
    cfg = wg_core.load_config()
    assert cfg["v6"]["enabled"] is True and wg_core.v6_enabled(cfg) is True
    assert cfg["enabled"] is True, "local 只蓋同名鍵，其餘照 config.json"
    monkeypatch.setenv("WG_V6", "0")
    assert wg_core.v6_enabled(cfg) is False


@pytest.mark.parametrize("raw", ["{壞".encode("utf-8"), b'{"v6": {"enabled": true}} \xff\xfe'])
def test_broken_local_file_is_loud_not_on(cfg_root, capsys, raw):
    (cfg_root / "config.local.json").write_bytes(raw)
    assert wg_core.v6_enabled(wg_core.load_config()) is False
    assert "config.local.json 讀取失敗" in capsys.readouterr().err


@pytest.mark.parametrize("local", [{"v6": True}, {"v6": {"enabled": "false"}}, {"v6": {"enabled": 1}}, {"v6": None}])
def test_only_json_true_turns_on(cfg_root, local):
    """v6 段不是物件、enabled 不是 JSON true（字串 "false"、1）→ 當關，不炸。"""
    (cfg_root / "config.local.json").write_text(json.dumps(local), encoding="utf-8")
    assert wg_core.v6_enabled(wg_core.load_config()) is False


@pytest.mark.skipif(shutil.which("node") is None, reason="沒有 node")
@pytest.mark.parametrize("env, local, want", [
    ({}, None, "false"), ({"WG_CODING_GUARD": "1"}, None, "true"), ({"WG_V6": "1"}, None, "true"),
    ({"WG_CODING_GUARD": "0", "WG_V6": "1"}, {"coding_guard": {"enabled": True}}, "false"),
    ({}, {"coding_guard": {"enabled": True}}, "true"), ({}, {"v6": {"enabled": True}}, "true"),
    ({"WG_CODING_GUARD": "0"}, {"v6": {"enabled": True}}, "false"),
    ({}, {"v6": True}, "false"), ({}, {"coding_guard": {"enabled": "false"}}, "false")])
def test_mcp_mirror_same_three_states(tmp_path, env, local, want):
    wf = tmp_path / "workflow"
    wf.mkdir()
    (wf / "config.json").write_text(json.dumps({"coding_guard": {"enabled": False}}), encoding="utf-8")
    if local:
        (wf / "config.local.json").write_text(json.dumps(local), encoding="utf-8")
    e = {k: v for k, v in os.environ.items() if k not in ("WG_V6", "WG_CODING_GUARD")}
    e["WG_CLAUDE_DIR"] = str(tmp_path)
    e.update(env)
    paths_js = (REPO / "tools" / "workflow-guardian-mcp" / "lib" / "paths.js").as_posix()
    r = subprocess.run(["node", "-e", f"process.stdout.write(String(require({json.dumps(paths_js)}).v6Enabled()))"],
                       env=e, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert r.stdout == want


# ─── 2. 關閉時 v6 閘不擋（打開時照擋：證明替身真的會擋） ──────────────

@pytest.mark.parametrize("event, tool, skip", [
    ("SubagentStop", "", True), ("PostToolUseFailure", "Bash", True),
    ("PreToolUse", "AskUserQuestion", True), ("PreToolUse", "mcp__workflow-guardian__second_opinion_start", True),
    ("PostToolUse", "Read", True), ("PostToolUse", "mcp__workflow-guardian__need_goal", True),
    ("PreToolUse", "Edit", False), ("PostToolUse", "Bash", False), ("Stop", "", False), ("UserPromptSubmit", "", False),
])
def test_dispatcher_only_routes_pre_v6_events_and_tools(event, tool, skip):
    assert dispatcher._pre_v6_skips(event, {"tool_name": tool}) is skip


@pytest.mark.parametrize("extra_env, inp", [
    ({"CLAUDE_COMPANION_JUDGE": "1"}, {"hook_event_name": "Stop", "session_id": _SID}),
    ({}, {"hook_event_name": "SubagentStop", "session_id": _SID}),
])
def test_dispatcher_off_exits_before_handler(tmp_path, extra_env, inp):
    """裁判子 session、SubagentStop：關閉時一進門就退，不輸出、不留計時帳（hook_timing 是 v6 才有）。"""
    env = {k: v for k, v in os.environ.items() if k not in ("WG_V6", "CLAUDE_COMPANION_JUDGE")}
    env.update({"WG_CLAUDE_DIR": str(tmp_path), "WG_TEST_LOGS_DIR": str(tmp_path / "Logs"), "WG_V6": "0", **extra_env})
    r = subprocess.run([sys.executable, str(HOOKS_DIR / "workflow-guardian.py")], input=json.dumps(inp).encode(),
                       env=env, cwd=tmp_path, capture_output=True, timeout=120)
    assert r.returncode == 0 and r.stdout.strip() == b""
    assert not (tmp_path / "Logs" / "guard-hook_timing.jsonl").exists()


@pytest.fixture
def pre_run(monkeypatch, tmp_path, capsys):
    """驅動 handle_pre_tool_use：Edit tmp 下的檔；state 讀不到（不落盤）。回 stdout。"""
    monkeypatch.setattr(pre, "read_state_status", lambda sid: (None, "missing"))
    monkeypatch.setattr(pre, "read_state", lambda sid: None)
    target = tmp_path / "data.json"
    target.write_text("{}", encoding="utf-8")

    def run():
        with pytest.raises(SystemExit):
            pre.handle_pre_tool_use({"session_id": _SID, "cwd": str(tmp_path), "tool_name": "Edit",
                                     "tool_input": {"file_path": str(target), "old_string": "{}", "new_string": "{\"a\": 1}"}},
                                    {})
        return capsys.readouterr().out

    return run


@pytest.mark.parametrize("gate", ["data_file", "oldtest"])
@pytest.mark.parametrize("on", [False, True])
def test_pretool_v6_gates_skipped_when_off(pre_run, monkeypatch, gate, on):
    _set_v6(monkeypatch, on)
    called = []

    def deny(*a, **k):
        called.append(gate)
        return f"[V6-{gate}] 必擋替身"

    monkeypatch.setattr(pre.wg_data_file if gate == "data_file" else pre.wg_oldtest, "gate", deny)
    if gate == "oldtest":
        monkeypatch.setattr(pre.wg_data_file, "gate", lambda *a, **k: None)
    out = pre_run()
    assert bool(called) is on
    assert (f"[V6-{gate}]" in out and '"deny"' in out) is on


@pytest.fixture
def stop_run(monkeypatch, capsys):
    """驅動 handle_stop（只留閘的控制流）：宣告完成、本 session 改過一個程式檔、沒有收割活動。"""
    for name, val in {
        "_find_session_transcript": lambda *a, **k: None, "token_warn_payload": lambda *a, **k: "",
        "detect_evasion": lambda *a, **k: None, "write_state": lambda *a, **k: None,
        "append_guard_log": lambda *a, **k: None, "_attribute_usefulness": lambda *a, **k: None,
        "_detect_uncommitted_files": lambda mf: [], "_git_unpushed_roots": lambda mf: [],
        "_should_deep_postmortem": lambda *a, **k: False, "_maybe_spawn_user_extract_worker": lambda *a, **k: None,
        "_hud_alive": lambda *a, **k: (True, {}), "get_last_assistant_text": lambda *a, **k: _DONE,
        "_code_check_text": lambda *a, **k: _DONE, "read_transcript_tail": lambda *a, **k: "",
        "harvest_gate_reason": lambda *a, **k: None, "pending_gate_reason": lambda *a, **k: None,
    }.items():
        monkeypatch.setattr(st, name, val)

    def run(state):
        monkeypatch.setattr(st, "_ensure_state", lambda *a, **k: state)
        with pytest.raises(SystemExit):
            st.handle_stop({"session_id": _SID, "cwd": ""}, {"harvest": {"background": True}})
        return capsys.readouterr().out

    return run


def _stop_state(**extra):
    s = {"phase": "done", "modified_files": [{"path": r"c:\proj\a.py", "tool": "Edit", "session_id": _SID}],
         "failing_tests": [], "recent_user_prompts": [], "stop_blocked_count": 0, "turn_seq": 5}
    s.update(extra)
    return s


@pytest.mark.parametrize("on", [False, True])
def test_stop_reconcile_gate_skipped_when_off(stop_run, monkeypatch, on):
    _set_v6(monkeypatch, on)
    called = []

    def gates(*a, **k):
        called.append(1)
        return "[Guardian:ReconcileGate] (a) 必擋替身", None, "reconcile"

    monkeypatch.setattr(st, "_verify_gates", gates)
    monkeypatch.setattr(st, "non_interactive_reason", lambda *a, **k: None)
    monkeypatch.setattr(st, "user_released", lambda *a, **k: None)
    out = stop_run(_stop_state())
    assert bool(called) is on
    assert ("ReconcileGate" in out) is on


@pytest.mark.parametrize("on", [False, True])
def test_stop_turn_judgment_gate_skipped_when_off(stop_run, monkeypatch, on):
    """開：拐彎判斷閘跑了，但 TURN_JUDGMENT_REQUIRED 是提醒（GATE_MODE_TABLE）→ 不擋、只留帳 event=remind；關：閘不跑、沒帳。"""
    _set_v6(monkeypatch, on)
    logs = []
    monkeypatch.setattr(st, "append_guard_log", lambda g, p: logs.append((g, p)))
    monkeypatch.setattr(st, "_verify_gates", lambda *a, **k: (None, None, None))
    monkeypatch.setattr(st, "turn_judgment_note", lambda *a, **k: ("[Guardian:TurnJudgment] 必擋替身", False))
    out = stop_run(_stop_state())
    assert "TurnJudgment" not in out
    assert any(g == "reading_path" and p.get("event") == "remind" and p.get("rule") == "TURN_JUDGMENT_REQUIRED" for g, p in logs) is on


def test_stop_off_testfail_message_is_pre_v6(stop_run, monkeypatch):
    """關閉時紅測閘照擋（v6 以前就有），但訊息是 9e476fd0 原文：沒有關閉時不存在的「不做｜」豁免出口。"""
    _set_v6(monkeypatch, False)
    out = stop_run(_stop_state(failing_tests=[{"cmd": "pytest -q", "summary": "1 failed", "session_id": _SID}]))
    assert "[Guardian:TestFailGate]" in out and "已知 regression" in out and "不做｜" not in out


@pytest.fixture
def ptu_run(monkeypatch, tmp_path, capsys):
    spawned = []
    for name, val in {
        "write_state": lambda *a, **k: None, "WORKFLOW_DIR": tmp_path, "_hud_alive": lambda *a, **k: (True, {}),
        "append_guard_log": lambda *a, **k: None, "_write_aec_report_file": lambda *a, **k: None,
        "_run_companion_hooks": lambda *a, **k: ([], []),
        "spawn_vcs_sync": lambda sid, cwd, reason, retired_paths=None: spawned.append(reason),
    }.items():
        monkeypatch.setattr(ptu, name, val)

    def run(state, tool_name, tool_input, tool_response=None):
        monkeypatch.setattr(ptu, "_ensure_state", lambda *a, **k: state)
        inp = {"session_id": _SID, "cwd": str(tmp_path), "tool_name": tool_name,
               "tool_input": tool_input, "tool_response": tool_response or {}}
        with pytest.raises(SystemExit):
            ptu.handle_post_tool_use(inp, {"docdrift": {"enabled": False}})
        return capsys.readouterr().out, spawned

    return run


@pytest.mark.parametrize("on", [False, True])
def test_posttool_need_goal_hint_skipped_when_off(ptu_run, monkeypatch, on):
    _set_v6(monkeypatch, on)
    monkeypatch.setattr(ptu, "_need_goal_after_tool", lambda *a, **k: ("[NeedGoal] 必送替身", False))
    out, _ = ptu_run({"turn_seq": 1}, "Bash", {"command": "echo hi"})
    assert ("[NeedGoal] 必送替身" in out) is on


@pytest.mark.parametrize("on", [False, True])
def test_write_gate_dedupe_declaration_follows_switch(monkeypatch, on):
    """MCP atom_write 的寫入閘（tools/memory-write-gate.py）：「相似要 AI 宣告」是 v6 加的擋，關閉時退回舊行為（>0.95 skip、其餘建議 update）。"""
    import importlib.util
    _set_v6(monkeypatch, on)
    spec = importlib.util.spec_from_file_location("memory_write_gate", REPO / "tools" / "memory-write-gate.py")
    mwg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mwg)
    assert mwg.load_config()["dedupe_declaration"] is on


# ─── 3. 關閉時寫碼守門關時也跑的處理照跑 ─────────────────────────────────

def test_off_subagent_memory_injection_still_runs(monkeypatch, capsys):
    _set_v6(monkeypatch, False)
    import wg_atoms
    monkeypatch.setattr(wg_atoms, "build_injection_blob", lambda prompt, **k: ("[記憶] 替身卡片", ["card-a"]))
    with pytest.raises(SystemExit):
        pre.handle_pre_tool_use({"session_id": _SID, "tool_name": "Agent",
                                 "tool_input": {"prompt": "查一下", "subagent_type": "general-purpose"}}, {})
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["updatedInput"]["prompt"] == "[記憶] 替身卡片\n\n查一下"


@pytest.mark.parametrize("on", [False, True])
def test_off_harvest_gate_blocks_instead_of_background(stop_run, monkeypatch, on):
    """收割擋是 v6 以前就有的：關閉時照擋；背景收割（wg_bg_harvest）是 v6 新增，只在打開時接手、不擋。"""
    _set_v6(monkeypatch, on)
    sent = []
    monkeypatch.setattr(st, "_verify_gates", lambda *a, **k: (None, None, None))
    monkeypatch.setattr(st, "turn_judgment_note", lambda *a, **k: (None, False))
    monkeypatch.setattr(st, "harvest_gate_reason", lambda *a, **k: "[Guardian:KnowledgeHarvest] 收割替身")
    monkeypatch.setattr(st, "bg_harvest", lambda *a, **k: sent.append(1) or True)
    out = stop_run(_stop_state())
    assert ("[Guardian:KnowledgeHarvest]" in out) is (not on)
    assert bool(sent) is on


def test_off_vcs_sync_still_spawns_after_validated_harvest(ptu_run, monkeypatch):
    _set_v6(monkeypatch, False)
    monkeypatch.setattr(ptu, "apply_report", lambda *a, **k: {
        "at": "2026-10-22T00:00:00", "validated": True, "items": [], "pending": [], "retired_paths": [], "note": ""})
    monkeypatch.setattr(ptu, "append_ledger", lambda *a, **k: None)
    _, spawned = ptu_run({"turn_seq": 3}, "mcp__workflow-guardian__knowledge_harvest_report", {"items": []})
    assert spawned == ["harvest"]


def test_off_lang_guard_still_reminds(tmp_path):
    wf = tmp_path / "workflow"
    wf.mkdir()
    (wf / "config.json").write_text(json.dumps({"lang_guard": {"enabled": True}}), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != "WG_V6"}
    env.update({"WG_CLAUDE_DIR": str(tmp_path), "WG_TEST_LOGS_DIR": str(tmp_path / "Logs")})
    inp = {"hook_event_name": "Stop", "session_id": _SID,
           "last_assistant_message": "This reply is written entirely in English so the language guard should remind "
                                     "the model to answer in Traditional Chinese next time around."}
    r = subprocess.run([sys.executable, str(HOOKS_DIR / "lang_guard.py")], input=json.dumps(inp).encode(),
                       env=env, cwd=tmp_path, capture_output=True, timeout=60)
    assert r.returncode == 0
    assert "語言守衛" in r.stdout.decode("utf-8")


if __name__ == "__main__":
    rc = pytest.main([__file__, "-q", "-p", "no:cacheprovider"])
    print("V6_SWITCH_CHECK PASS" if rc == 0 else "V6_SWITCH_CHECK FAIL")
    sys.exit(0 if rc == 0 else 1)

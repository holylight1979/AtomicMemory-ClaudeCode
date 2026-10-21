"""verify_hook_timing.py：hook 分段計時與超時降級（wg_hook_timing）、Stop／PostToolUse 降級後只記不問、dispatcher 落帳、量尺 tools/hook-timing.py。

怎麼跑：set WG_CLAUDE_DIR=<worktree> && python -X utf8 -m pytest -q hooks/verify/verify_hook_timing.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1]
ROOT = HOOKS_DIR.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(ROOT / "lib"))

import wg_hook_timing as ht  # noqa: E402
from handlers import post_tool_use as pt  # noqa: E402
from handlers import stop as st  # noqa: E402
from wg_core import DEFAULTS  # noqa: E402

_CFG = {"hook_timing": DEFAULTS["hook_timing"]}


@pytest.fixture()
def ledger(monkeypatch):
    rows = []
    monkeypatch.setattr(ht, "append_guard_log", lambda guard, rec: rows.append((guard, dict(rec))))
    monkeypatch.setattr(ht, "_CUR", None)
    return rows


def test_lap_degrades_once_past_ratio_with_ledger_and_stderr(ledger, capsys):
    """上限 10 秒、80%：7 秒打點不降級；過 8 秒那一點降級（留一筆 degraded＋stderr 一行），之後每點都回 True、不再重複留帳；
    finish 補「其餘」寫一筆 run，之後沒起表 lap 回 False。"""
    timer = ht.HookTimer("Stop", "sid", 10.0, "settings.json", 0.8, time.time() - 7.0)
    ht._CUR = timer
    assert ht.lap("甲") is False and ledger == []
    timer.t0 -= 1.5
    assert ht.lap("乙") is True
    assert [(g, r["kind"], r["degraded_at"]) for g, r in ledger] == [("hook_timing", "degraded", "乙")]
    err = capsys.readouterr().err
    assert "hook 超時降級" in err and "跑完「乙」" in err and "後面的段落這次不跑" in err
    assert ht.lap("丙") is True and len(ledger) == 1
    ht.finish()
    run = ledger[-1][1]
    assert run["kind"] == "run" and run["degraded_at"] == "乙" and [s[0] for s in run["segments"]] == ["甲", "乙", "丙", "其餘"]
    assert ht.lap("丁") is False and len(ledger) == 2


def test_start_reads_guardian_timeout_from_settings_else_config(ledger, monkeypatch, tmp_path):
    """上限取 settings.json 裡掛 workflow-guardian.py 那支（同事件其他 hook 的 timeout 不算）；沒掛退 config；沒列的事件、關掉都不計時。"""
    monkeypatch.setattr(ht, "CLAUDE_DIR", tmp_path)
    guardian = "pythonw.exe -c \"...'.claude/hooks/workflow-guardian.py'...\""
    (tmp_path / "settings.json").write_text(json.dumps({"hooks": {"Stop": [{"hooks": [
        {"type": "command", "command": "pythonw.exe codex_companion.py", "timeout": 150},
        {"type": "command", "command": guardian, "timeout": 20}]}]}}), encoding="utf-8")
    t = ht.start("Stop", {"session_id": "s1"}, _CFG)
    assert (t.limit_s, t.limit_src, t.session_id, t.segments[0][0]) == (20.0, "settings.json", "s1", "啟動")
    ht.finish()                                                                # 收表：背景鬧鐘不留到案例外
    t = ht.start("PostToolUse", {}, _CFG)
    assert (t.limit_s, t.limit_src) == (5.0, "config")
    ht.finish()
    assert ht.start("PreToolUse", {}, _CFG) is None and ht._CUR is None
    assert ht.start("Stop", {}, {"hook_timing": {**_CFG["hook_timing"], "enabled": False}}) is None


@pytest.mark.skipif(sys.platform != "win32", reason="行程建立時間只在 Windows 用 GetProcessTimes 取")
def test_process_start_is_real_creation_time():
    """起點是行程建立時間，不是呼叫當下：pytest 這個行程早就跑了一陣子（拿不到會退回現在，差距是 0）。"""
    assert time.time() - ht._process_started() > 0.05


# ─── Stop：降級後放行、不擋，state 照寫 ────────────────────────────────

@pytest.fixture()
def stop_driven(monkeypatch):
    wrote = []
    monkeypatch.setattr(st, "_find_session_transcript", lambda *a, **k: None)
    monkeypatch.setattr(st, "token_warn_payload", lambda *a, **k: "")
    monkeypatch.setattr(st, "detect_evasion", lambda *a, **k: None)
    monkeypatch.setattr(st, "write_state", lambda sid, s: wrote.append(sid))
    monkeypatch.setattr(st, "append_guard_log", lambda *a, **k: None)
    monkeypatch.setattr(st, "_attribute_usefulness", lambda *a, **k: None)
    monkeypatch.setattr(st, "_detect_uncommitted_files", lambda mf: [])
    monkeypatch.setattr(st, "_maybe_spawn_user_extract_worker", lambda *a, **k: None)
    monkeypatch.setattr(st, "estimate_context_usage", lambda *a, **k: 0.3)
    monkeypatch.setattr(st, "get_last_assistant_text", lambda *a, **k: "改好了。")

    def drive(capsys, degrade_at=None):
        laps = []

        def fake_lap(seg):
            laps.append(seg)
            return degrade_at is not None and degrade_at in laps
        monkeypatch.setattr(st, "_hook_lap", fake_lap)
        state = {"phase": "working", "modified_files": [], "recent_user_prompts": [], "stop_blocked_count": 0, "turn_seq": 7,
                 "failing_tests": [{"session_id": "sid", "cmd": "python -m pytest tests", "summary": "1 failed", "turn_seq": 7}]}
        monkeypatch.setattr(st, "_ensure_state", lambda *a, **k: state)
        wrote.clear()
        with pytest.raises(SystemExit):
            st.handle_stop({"session_id": "sid", "cwd": "", "last_assistant_message": "全部完成，測試都過了。"}, {})
        return capsys.readouterr().out, laps, list(wrote)

    return drive


def test_stop_degraded_before_testfail_gate_releases_without_block(stop_driven, capsys):
    out, laps, _ = stop_driven(capsys)
    assert "[Guardian:TestFailGate]" in out                                   # 前置：同一份 state 不降級會被紅測閘擋
    assert laps[:3] == ["讀 transcript", "殘檔帳本", "最該修記帳"]
    out, laps, wrote = stop_driven(capsys, degrade_at="token 預警與閱讀路徑")
    assert "TestFailGate" not in out and '"decision"' not in out             # 降級：後面的閘不跑、不擋
    assert laps[-1] == "token 預警與閱讀路徑" and wrote and wrote[-1] == "sid"    # 停在降級那一點，state 寫回


# ─── PostToolUse：降級後提示類段落不跑，記帳與寫 state 照做 ─────────────────

@pytest.fixture()
def ptu_driven(monkeypatch, tmp_path):
    state = {"turn_seq": 3, "session": {"cwd": r"c:\proj"}}
    wrote, companion = [], []
    monkeypatch.setattr(pt, "_ensure_state", lambda *a, **k: state)
    monkeypatch.setattr(pt, "write_state", lambda sid, s: wrote.append(sid))
    monkeypatch.setattr(pt, "WORKFLOW_DIR", tmp_path)
    monkeypatch.setattr(pt, "append_guard_log", lambda *a, **k: None)
    monkeypatch.setattr(pt, "_check_output_quality", lambda *a, **k: None)
    monkeypatch.setattr(pt, "_run_companion_hooks", lambda *a, **k: companion.append(1) or ([], ["同伴提示"]))

    def run(capsys, degrade_at=None, tool="Edit"):
        laps = []

        def fake_lap(seg):
            laps.append(seg)
            return degrade_at is not None and degrade_at in laps
        monkeypatch.setattr(pt, "_hook_lap", fake_lap)
        companion.clear()
        wrote.clear()
        inp = {"session_id": "sid", "tool_name": tool, "tool_input": {"file_path": r"c:\proj\src\a.py"},
               "tool_response": {}, "cwd": r"c:\proj"}
        with pytest.raises(SystemExit):
            pt.handle_post_tool_use(inp, {"docdrift": {"enabled": False}})
        return capsys.readouterr().out, laps, list(wrote), len(companion)

    return state, run


def test_post_tool_use_degraded_skips_prompts_keeps_ledger(ptu_driven, capsys):
    state, run = ptu_driven
    out, laps, wrote, called = run(capsys)
    assert called == 1 and "同伴提示" in out                                  # 前置：不降級時同伴檢查有跑、提示有送
    assert laps == ["讀 state", "工具記帳", "導讀卡", "綜觀與召回", "目標樹", "寫 state", "跨 session 碰撞", "同伴檢查"]
    state.pop("modified_files", None)
    out, laps, wrote, called = run(capsys, degrade_at="工具記帳")
    assert called == 0 and "同伴提示" not in out                              # 降級：提示類不跑
    assert any(m["path"].endswith("a.py") for m in state["modified_files"]) and wrote == ["sid"]   # 記帳與寫 state 照做
    out, laps, wrote, called = run(capsys, degrade_at="跨 session 碰撞")
    assert called == 0 and "同伴提示" not in out                              # 碰撞檢查跑完才過線：同伴檢查照樣不跑


def test_post_tool_use_degraded_after_overview_card_skips_depends(ptu_driven, capsys, monkeypatch):
    """導讀卡那段跑完才過線：depends 召回不跑（codex 第三輪：導讀卡後沒重新判時）。前置：不降級時 Read 會跑 depends。"""
    import wg_depends
    import wg_overview
    calls = []
    monkeypatch.setattr(wg_overview, "on_read", lambda *a, **k: None)
    monkeypatch.setattr(wg_depends, "on_read_depends", lambda *a, **k: calls.append(1) or None)
    _, run = ptu_driven
    run(capsys, tool="Read")
    assert calls == [1]
    calls.clear()
    _, laps, _, _ = run(capsys, degrade_at="導讀卡", tool="Read")
    assert calls == [] and "導讀卡" in laps


def test_settings_limit_picks_the_group_whose_matcher_fits_the_tool(monkeypatch, tmp_path):
    """同一事件兩組 matcher 不同上限：照這次的工具名整串比對（Read 20、Bash 5）；沒給工具名取第一組；寫壞的 matcher 當對不上。"""
    monkeypatch.setattr(ht, "CLAUDE_DIR", tmp_path)
    g = "x/.claude/hooks/workflow-guardian.py"
    (tmp_path / "settings.json").write_text(json.dumps({"hooks": {"PostToolUse": [
        {"matcher": "Read", "hooks": [{"command": g, "timeout": 20}]},
        {"matcher": "(", "hooks": [{"command": g, "timeout": 99}]},
        {"matcher": "Bash|PowerShell", "hooks": [{"command": g, "timeout": 5}]}]}}), encoding="utf-8")
    assert ht.settings_limit("PostToolUse", "Bash") == 5.0 and ht.settings_limit("PostToolUse", "Read") == 20.0
    assert ht.settings_limit("PostToolUse", "BashX") is None and ht.settings_limit("PostToolUse") == 20.0


def test_run_record_says_which_segment_it_ended_after(ledger):
    """閘擋下就返回、打不到下一點：run 記 ended_after＝最後打到的段名，那道閘的耗時在「其餘」。"""
    ht._CUR = ht.HookTimer("Stop", "s", 10.0, "config", 0.8, time.time())
    ht.lap("讀 transcript")
    ht.lap("紅測閘")
    ht.finish()
    run = ledger[-1][1]
    assert run["kind"] == "run" and run["ended_after"] == "紅測閘" and run["segments"][-1][0] == "其餘"


# ─── 背景鬧鐘：單一段落跑過頭、打不到點也留得下訊號 ──────────────────────────

def test_alarm_writes_overrun_when_a_segment_runs_past_95_percent(ledger, monkeypatch, capsys):
    """上限 1 秒、起點 0.9 秒前：0.05 秒後鬧鐘響，沒有任何打點也留一筆 overrun（卡在「啟動」之後）＋stderr。"""
    monkeypatch.setattr(ht, "settings_limit", lambda *a: None)
    monkeypatch.setattr(ht, "_process_started", lambda: time.time() - 0.9)
    cfg = {"hook_timing": {"enabled": True, "degrade_ratio": 0.8, "fallback_limit_s": {"Stop": 1}}}
    timer = ht.start("Stop", {"session_id": "s"}, cfg)
    timer.alarm.join(2)
    rows = [r for _, r in ledger if r["kind"] == "overrun"]
    assert len(rows) == 1 and rows[0]["stuck_after"] == "啟動" and "hook 快被取消" in capsys.readouterr().err
    ht.finish()


def test_alarm_cancelled_when_hook_finishes_in_time(ledger, monkeypatch):
    monkeypatch.setattr(ht, "settings_limit", lambda *a: None)
    monkeypatch.setattr(ht, "_process_started", lambda: time.time())
    cfg = {"hook_timing": {"enabled": True, "degrade_ratio": 0.8, "fallback_limit_s": {"Stop": 0.3}}}
    timer = ht.start("Stop", {}, cfg)
    ht.finish()
    time.sleep(0.5)                                                            # 鬧鐘原本 0.285 秒後響
    assert not timer.alarm.is_alive() and [r["kind"] for _, r in ledger] == ["run"]


# ─── dispatcher：真的起一支 hook 行程，計時帳落一筆 ─────────────────────────

def test_dispatcher_writes_one_timing_record_per_hook(tmp_path):
    root, logs = tmp_path / "root", tmp_path / "logs"
    root.mkdir()
    (root / "settings.json").write_text(json.dumps({"hooks": {"PostToolUse": [{"matcher": "Read", "hooks": [
        {"type": "command", "command": "x/.claude/hooks/workflow-guardian.py", "timeout": 7}]}]}}), encoding="utf-8")
    env = {**os.environ, "WG_CLAUDE_DIR": str(root), "WG_TEST_LOGS_DIR": str(logs)}
    env.pop("CLAUDE_COMPANION_JUDGE", None)
    inp = {"hook_event_name": "PostToolUse", "session_id": "sid-timing", "tool_name": "Read",
           "tool_input": {"file_path": str(tmp_path / "x.txt")}, "tool_response": {}, "cwd": str(tmp_path)}
    p = subprocess.run([sys.executable, str(HOOKS_DIR / "workflow-guardian.py")], input=json.dumps(inp).encode("utf-8"),
                       capture_output=True, env=env, cwd=str(tmp_path), timeout=120)
    assert p.returncode == 0, p.stderr.decode("utf-8", "replace")[-500:]
    recs = [json.loads(line) for line in (logs / "guard-hook_timing.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(recs) == 1 and recs[0]["kind"] == "run" and recs[0]["event"] == "PostToolUse"
    assert (recs[0]["limit_s"], recs[0]["limit_src"], recs[0]["session_id"]) == (7.0, "settings.json", "sid-timing")
    names = [s[0] for s in recs[0]["segments"]]
    assert names[:3] == ["啟動", "載入 handler", "讀 state"] and names[-1] == "其餘"


# ─── 量尺 tools/hook-timing.py ───────────────────────────────────────

def _tool():
    spec = importlib.util.spec_from_file_location("hook_timing_tool", ROOT / "tools" / "hook-timing.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


TAIL = re.compile(r"^HOOK_TIMING DONE events=\d+ runs=\d+ degraded=\d+ overrun=\d+$")


def test_meter_medians_degraded_and_tail(tmp_path, capsys):
    now = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    rows = [{"at": now, "kind": "run", "event": "Stop", "total_ms": t, "limit_s": 10.0, "limit_src": "settings.json",
             "degraded_at": "", "segments": [["啟動", 500], ["寫碼查核", c], ["其餘", 0]]}
            for t, c in ((3000, 2000), (9000, 6000), (5000, 4000))]
    rows.append({"at": now, "kind": "degraded", "event": "Stop", "degraded_at": "寫碼查核", "segments": []})
    rows.append({"at": now, "kind": "overrun", "event": "Stop", "stuck_after": "殘檔帳本", "segments": []})
    rows.append({"at": "2000-01-01T00:00:00+00:00", "kind": "run", "event": "Stop", "total_ms": 99999, "segments": []})   # 太舊
    (tmp_path / "guard-hook_timing.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n壞行\n", encoding="utf-8")
    tool = _tool()
    assert tool.main(["--logs", str(tmp_path), "--json"]) == 0
    out = capsys.readouterr()
    lines = out.out.strip().splitlines()
    assert TAIL.match(lines[-1]) and lines[-1] == "HOOK_TIMING DONE events=1 runs=3 degraded=1 overrun=1"
    res = json.loads("\n".join(lines[:-1]))
    stop = res["events"][0]
    assert (stop["runs"], stop["degraded"], stop["total_median_ms"], stop["total_max_ms"]) == (3, 1, 5000, 9000)
    assert [(g["name"], g["median_ms"]) for g in stop["segments"]] == [("啟動", 500), ("寫碼查核", 4000), ("其餘", 0)]
    assert stop["degraded_at"] == {"寫碼查核": 1} and stop["stuck_after"] == {"殘檔帳本": 1} and "讀不懂" in out.err


def test_meter_without_ledger_says_so(tmp_path, capsys):
    """看不到帳是獨立狀態：印「沒有計時帳」，不印成 0ms。"""
    assert _tool().main(["--logs", str(tmp_path)]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert "沒有計時帳" in lines[0] and "ms" not in lines[0] and lines[-1] == "HOOK_TIMING DONE events=0 runs=0 degraded=0 overrun=0"

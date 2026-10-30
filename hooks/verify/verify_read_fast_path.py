"""verify_read_fast_path.py：Read 事件走快路徑（規則 READ_FAST_PATH，hooks/wg_read_fast.py）。

Read 的 PostToolUse 在 dispatcher 一進門就只追加一行 read-log（不載 wg_core 等重模組）；原本靠它做的事（OverviewHub on_read 記讀過、
第一次讀該部位的一行定位提示…）改在下一個非 Read 事件（Edit 的 PreToolUse、Bash 的 PostToolUse）補帳，
結果一樣、提示晚一個事件出現；Bash 唯讀照走原路徑。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_read_fast_path.py
共用 hub_world 的資料根隔離（env／hooked）與部位世界；不碰 live。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

VERIFY = Path(__file__).resolve().parent
HOOKS_DIR = VERIFY.parent
sys.path.insert(0, str(VERIFY))

from hub_world import (  # noqa: E402,F401
    SID, _deny_text, _mapped_world, _ptu_run, _two_part_world, env, hooked, pt, wg_core, wo,
)
import wg_read_fast as rf  # noqa: E402

HEAVY = {"wg_core", "wg_hook_timing", "wg_overview", "handlers.post_tool_use", "handlers.pre_tool_use"}


@pytest.fixture(autouse=True)
def _v6_on(monkeypatch):
    monkeypatch.setenv("WG_V6", "1")
    from hub_config import HUB_DEFAULTS
    monkeypatch.setitem(HUB_DEFAULTS, "card_injection", "full")


@pytest.fixture
def fast(env, monkeypatch):
    """read-log 落到測試資料根（wg_read_fast 自己算資料根，跟 wg_core 各自換）。"""
    monkeypatch.setattr(rf, "WORKFLOW_DIR", env["wf"])
    return env


def _read_event(path, cwd, tp, agent_id=""):
    return {"hook_event_name": "PostToolUse", "session_id": SID, "tool_name": "Read", "tool_input": {"file_path": path},
            "tool_response": {"type": "text", "file": {"filePath": path, "content": "x"}}, "cwd": str(cwd), "transcript_path": tp,
            **({"agent_id": agent_id} if agent_id else {})}


@pytest.fixture
def post_tool(hooked, monkeypatch):
    """跑一次真的 PostToolUse，回這次工具結果附的 additionalContext。"""
    got = []
    monkeypatch.setattr(pt, "output_json", lambda d: (got.append(d), sys.exit(0)))
    monkeypatch.setattr(pt, "output_nothing", lambda: (got.append(None), sys.exit(0)))
    monkeypatch.setattr(pt, "_check_output_quality", lambda *a, **k: None)
    monkeypatch.setattr(pt, "_run_companion_hooks", lambda *a: ([], []))

    def run(tool="Bash", tool_input=None, config=None):
        inp = {"session_id": SID, "hook_event_name": "PostToolUse", "tool_name": tool,
               "tool_input": tool_input or {"command": "echo hi"},
               "tool_response": {"stdout": "hi", "stderr": "", "exit_code": 0}, "cwd": str(hooked["proj"]),
               "transcript_path": hooked["tp"]}
        with pytest.raises(SystemExit):
            pt.handle_post_tool_use(inp, {"docdrift": {"enabled": False}, **(config or {})})
        return ((got[-1] or {}).get("hookSpecificOutput") or {}).get("additionalContext") or ""
    return run


def _code_intent(intent="debug"):
    """使用者這則 prompt 的關鍵字判成寫碼類（state turn_intent）：補帳出來的定位提示只在有改程式意圖時送（LOCATE_HINT_ON_FIRST_READ）。"""
    st = wg_core.read_state(SID) or {}
    st["turn_intent"] = intent
    wg_core.write_state(SID, st)


def _part_reads(part="戰鬥"):
    state = wg_core.read_state(SID) or {}
    rec = next((v for k, v in (state.get("overview_hub") or {}).items() if k.endswith(f"|{part}")), None)
    return rec.get("part_files_read") if rec else None


# ─── 1. 快路徑本體：真的起一支 hook 行程，一個重模組都不載，只多一行 read-log ──────────────

def test_read_event_does_not_import_heavy_modules(tmp_path):
    root = tmp_path / "root"
    (root / "workflow").mkdir(parents=True)
    f = tmp_path / "x.txt"
    f.write_text("x", encoding="utf-8")
    code = ("import sys, json; sys.path.insert(0, sys.argv[1]); import dispatcher\n"
            "try:\n    dispatcher.main()\nexcept SystemExit:\n    pass\n"
            "print('MODS ' + json.dumps(sorted(m for m in sys.modules if m.startswith(('wg_', 'handlers')))))")
    env_ = {k: v for k, v in os.environ.items() if k != "CLAUDE_COMPANION_JUDGE"}
    env_.update({"WG_CLAUDE_DIR": str(root), "WG_TEST_LOGS_DIR": str(tmp_path / "logs"), "WG_V6": "1"})
    inp = _read_event(str(f), tmp_path, "")
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", code, str(HOOKS_DIR)], input=json.dumps(inp).encode("utf-8"),
                       capture_output=True, env=env_, cwd=str(tmp_path), timeout=120)
    assert p.returncode == 0, p.stderr.decode("utf-8", "replace")[-500:]
    mods = set(json.loads(p.stdout.decode("utf-8").strip().splitlines()[-1][5:]))
    assert mods == {"wg_read_fast"}, sorted(mods)                               # 舊碼：wg_core、handlers.post_tool_use 全載 → 紅
    lines = (root / "workflow" / f"read-log-{SID}.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["tool_input"] == {"file_path": str(f)}
    assert not (tmp_path / "logs").exists()                                     # 不計時、不留守門紀錄


# ─── 2. 每讀一次追加一筆（session、路徑、cwd、時間、結果大小） ─────────────────────────

def test_read_log_appended_per_read(fast):
    f1 = _mapped_world(fast)
    rf.log_read(_read_event(f1, fast["proj"], "tp"))
    rf.log_read({**_read_event(f1, fast["proj"], "tp", agent_id="ag-1"), "tool_response": "Error: no such file"})
    entries = [json.loads(l) for l in rf.log_path(SID).read_text(encoding="utf-8").splitlines()]
    assert [e["sid"] for e in entries] == [SID, SID]
    assert entries[0]["tool_input"] == {"file_path": f1} and entries[0]["cwd"] == str(fast["proj"]) and entries[0]["chars"] == 1
    assert entries[0]["t"] > 0 and "agent_id" not in entries[0]
    assert entries[1]["agent_id"] == "ag-1" and entries[1]["error"].startswith("Error")
    ev = rf.event_of(entries[0])
    assert ev["tool_name"] == "Read" and ev["tool_response"]["file"]["content"] == " "
    assert rf.event_of(entries[1])["tool_response"] == "Error: no such file"
    assert rf.pending(SID) and rf.drain(SID) == entries and not rf.pending(SID) and rf.drain(SID) == []


# ─── 3. 下一個事件把 read-log 交給 on_read：Edit 的 PreToolUse 先補帳（閘要讀檔證據） ────────

def test_next_event_replays_read_log_into_on_read(fast, hooked):
    f1 = _mapped_world(fast)
    _code_intent()
    rf.log_read(_read_event(f1, fast["proj"], hooked["tp"]))
    assert _part_reads() is None                                                 # 還沒補帳：state 沒有這個部位
    _ptu_run("Edit", {"file_path": f1, "old_string": "x", "new_string": "y"}, hooked["proj"], hooked["tp"], hooked["outputs"])
    assert len(_part_reads() or []) == 1 and not rf.pending(SID)                 # 讀過算讀過；log 已清
    state = wg_core.read_state(SID)
    assert any("改【戰鬥】的程式檔前" in h for h in state[rf.HINTS_KEY])          # 提示存著等下一個 PostToolUse
    # 提問前也補（提問閘看「本回合該部位讀過幾檔」）：任何工具的 PreToolUse 都先 drain
    rf.log_read(_read_event(f1, fast["proj"], hooked["tp"]))
    ask = {"questions": [{"question": "要用哪個做法？", "header": "做法", "multiSelect": False,
                          "options": [{"label": "A (Recommended)", "description": "甲"}, {"label": "B", "description": "乙"}]}]}
    _ptu_run("AskUserQuestion", ask, hooked["proj"], hooked["tp"], hooked["outputs"])
    assert not rf.pending(SID)


# ─── 4. 第一次讀該部位的一行定位提示：隨下一個工具結果到、只一次 ──────────────────────

def test_first_read_hint_arrives_on_next_tool_result(fast, hooked, post_tool):
    f1 = _mapped_world(fast)
    _code_intent()
    rf.log_read(_read_event(f1, fast["proj"], hooked["tp"]))
    ctx = post_tool()                                                            # 下一個非 Read 事件：Bash 的 PostToolUse
    hint = next(ln for ln in ctx.splitlines() if ln.startswith("[Guardian:OverviewHub] 改【戰鬥】的程式檔前"))
    assert "交定位三行" in hint and "戰鬥導讀" not in ctx                           # 跟原本 Read 當下附的一樣（READ_TOUCH_NO_CARD）
    assert _part_reads() and not rf.pending(SID)
    rf.log_read(_read_event(f1, fast["proj"], hooked["tp"]))
    assert "交定位" not in post_tool()                                           # 同部位第二次讀：不重送
    assert len(_part_reads()) == 1                                               # 同一個檔只記一次
    # PreToolUse 補出來的提示也在下一個 PostToolUse 送到、送完就清
    state = wg_core.read_state(SID)
    state[rf.HINTS_KEY] = ["[Guardian:OverviewHub] 改【介面】的程式檔前交定位三行（格式同前一則提示）。"]
    wg_core.write_state(SID, state)
    assert "改【介面】" in post_tool() and rf.HINTS_KEY not in wg_core.read_state(SID)
    assert "改【介面】" not in post_tool()


# ─── 6. Bash 唯讀照走原路徑；v6 關補帳整批丟掉 ─────────────────────────────────────

def test_bash_readonly_path_unchanged(fast, hooked, post_tool, monkeypatch):
    import dispatcher
    f1 = _mapped_world(fast)
    _code_intent()
    assert not rf.is_fast_read({"hook_event_name": "PostToolUse", "session_id": SID, "tool_name": "Bash",
                                "tool_input": {"command": f'cat "{f1}"'}})
    assert not rf.is_fast_read({"hook_event_name": "PreToolUse", "session_id": SID, "tool_name": "Read"})
    assert rf.is_fast_read(_read_event(f1, fast["proj"], ""))
    assert dispatcher._pre_v6_skips("PostToolUse", {"tool_name": "Read"})     # v6 關：Read 本來就不進 handler
    ctx = post_tool("Bash", {"command": f'cat "{f1}"'})                        # 唯讀 Bash：當下就記讀過、當下附提示
    assert "改【戰鬥】的程式檔前" in ctx and _part_reads() and not rf.pending(SID)
    monkeypatch.setenv("WG_V6", "0")
    rf.log_read(_read_event(f1, fast["proj"], hooked["tp"]))
    assert "交定位" not in post_tool() and not rf.pending(SID)                   # 關：log 清掉、什麼都不補


# ─── 7. session 結束前最後幾次 Read：SessionEnd 補完、檔清掉 ─────────────────────────

def test_session_end_replays_leftover_reads(fast, hooked, monkeypatch):
    from handlers import session_end as se
    f1 = _mapped_world(fast)
    rf.log_read(_read_event(f1, fast["proj"], hooked["tp"]))
    monkeypatch.setattr(se, "_cleanup_old_states", lambda: None)
    for name in ("build_drift_advisory",):
        if hasattr(se, name):
            monkeypatch.setattr(se, name, lambda *a, **k: None)
    with pytest.raises(SystemExit):
        se.handle_session_end({"session_id": SID, "hook_event_name": "SessionEnd", "cwd": str(hooked["proj"]),
                               "transcript_path": hooked["tp"]}, {"docdrift": {"enabled": False}, "userExtraction": {"enabled": False}})
    assert _part_reads() and not rf.pending(SID)                                 # 讀過算讀過、log 清掉

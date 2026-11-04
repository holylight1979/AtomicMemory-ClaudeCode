"""verify_subagent_start.py：SubagentStart 補「沒經過 Agent 工具的子代理」的記憶注入（規則 SUBAGENT_START_NON_AGENT_INJECT）。

做什麼：
1. 已登記的 agent_id（subagent_injections 有這筆）→ 不送，guard log decision=registered。
2. 未登記，父逐字稿最近一則 assistant 動作是 Skill（context: fork）且任務文字命中卡 → additionalContext 帶 [WG:SubagentMemory]，
   state 多一筆 status async_launched，SubagentStop 依 agent_id 回填結果。
3. 拿不到任務文字（最近一則是文字、不在表上的工具、逐字稿不在）→ 不送，decision=no_task_text。
4. 最近一則是 Agent／Task（PreToolUse 已挑過）→ 不送，decision=agent_tool_route；有文字沒挑到卡 → decision=no_match。
5. 真入口子行程（workflow-guardian.py）：SubagentStart 送卡寫 state → 同 agent_id 再跑不送 → SubagentStop 回填。
怎麼跑：python -X utf8 hooks/verify/verify_subagent_start.py（印 SUBAGENT_START_CHECK PASS／FAIL）
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
import wg_release_rules as rr  # noqa: E402
from handlers import stop as st  # noqa: E402
from handlers import subagent_start as ss  # noqa: E402

SID = "sid-w16"
RULE = "SUBAGENT_START_NON_AGENT_INJECT"


def _write_memory(root: Path) -> Path:
    """受控 memory：alpha-atom 的 trigger 是 alphakeyword。"""
    mem = root / "memory"
    mem.mkdir(parents=True, exist_ok=True)
    (mem / "alpha-atom.md").write_text(
        "# alpha-atom\n\n- Scope: global\n- Confidence: [固]\n- Trigger: alphakeyword\n- Last-used: 2026-06-01\n"
        "- Confirmations: 5\n- ReadHits: 0\n\n## 印象\n\n- alpha 的印象重點一句話。\n\n## 行動\n\n- 做 alpha 對應的動作。\n",
        encoding="utf-8")
    (mem / "_ATOM_INDEX.md").write_text(
        "| Atom | Path | Triggers |\n|------|------|----------|\n| alpha-atom | memory/alpha-atom.md | alphakeyword |\n",
        encoding="utf-8")
    return mem


def _transcript(path: Path, last: dict) -> str:
    """父 session 逐字稿：一則使用者原話，最後一則 assistant 動作是 last（content 區塊）。"""
    lines = [{"type": "user", "message": {"role": "user", "content": "幫我處理"}},
             {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "好，我來。"}]}},
             {"type": "assistant", "message": {"role": "assistant", "content": [last]}}]
    path.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in lines) + "\n", encoding="utf-8")
    return str(path)


def _tool_use(name: str, inp: dict, tid: str = "toolu_skill") -> dict:
    return {"type": "tool_use", "id": tid, "name": name, "input": inp}


SKILL_HIT = _tool_use("Skill", {"skill": "pingfork", "args": "處理 alphakeyword"})


@pytest.fixture
def run(tmp_path, monkeypatch):
    """跑 handle_subagent_start（不碰真 state、真 log）：run(state, last 區塊 或 None＝逐字稿不在, agent_id)
    → (additionalContext 或 None, guard log 的 decision 清單, write_state 次數)。"""
    monkeypatch.setattr(wg_atoms, "MEMORY_DIR", _write_memory(tmp_path))
    outs: list = []
    logs: list = []
    writes: list = []
    monkeypatch.setattr(ss, "output_json", lambda d: outs.append(d))
    monkeypatch.setattr(ss, "output_nothing", lambda: None)
    monkeypatch.setattr(ss, "append_guard_log", lambda guard, payload: logs.append((guard, payload)))
    monkeypatch.setattr(ss, "write_state", lambda sid, state: writes.append(sid))

    def _run(state, last, agent_id="ag-new"):
        monkeypatch.setattr(ss, "read_state", lambda sid: state)
        tp = _transcript(tmp_path / "parent.jsonl", last) if last is not None else str(tmp_path / "missing.jsonl")
        outs.clear(), logs.clear(), writes.clear()
        ss.handle_subagent_start({"hook_event_name": "SubagentStart", "session_id": SID, "transcript_path": tp,
                                  "agent_id": agent_id, "agent_type": "general-purpose"}, {})
        ctx = outs[0]["hookSpecificOutput"]["additionalContext"] if outs else None
        assert all(g == ss.GUARD for g, _ in logs)
        return ctx, [p["decision"] for _, p in logs], len(writes)

    _run.logs = logs
    return _run


# ─── ① 已登記的 agent_id ─────────────────────────────────────────────

def test_registered_agent_id_not_resent(run):
    """PreToolUse 路已送過的子代理續跑（agent_id 已在 subagent_injections）→ 不送、不寫 state，留帳 registered。"""
    state = {"turn_seq": 4, "subagent_injections": [{"agent_id": "ag-old", "atoms": ["alpha-atom"], "status": "completed"}]}
    ctx, decisions, writes = run(state, SKILL_HIT, agent_id="ag-old")
    assert ctx is None and decisions == ["registered"] and writes == 0
    assert len(state["subagent_injections"]) == 1


# ─── ② 未登記＋有任務文字 ─────────────────────────────────────────────

def test_skill_fork_sends_and_records(run):
    """最近一則是 Skill、args 命中 alpha → additionalContext 帶 marker 與卡名；state 多一筆等 SubagentStop 回填的紀錄。"""
    state = {"turn_seq": 4, "turn_prompts_seq": 4}
    ctx, decisions, writes = run(state, SKILL_HIT)
    assert ctx and ctx.startswith(wg_atoms.SUBAGENT_INJECT_MARKER) and "atoms=alpha-atom" in ctx
    assert decisions == ["sent"] and writes == 1
    assert run.logs[0][1]["atoms"] == ["alpha-atom"] and run.logs[0][1]["recorded"] is True
    rec = state["subagent_injections"][-1]
    assert rec["agent_id"] == "ag-new" and rec["agent_type"] == "general-purpose" and rec["atoms"] == ["alpha-atom"]
    assert rec["status"] == "async_launched" and rec["output_summary"] == "" and rec["tool_use_id"] == "toolu_skill"
    assert rec["turn_seq"] == 4
    # SubagentStop 依 agent_id 回填同一筆（規則 SUBAGENT_RESULT_FROM_SUBAGENT_STOP）
    assert st._fill_subagent_result(state, "ag-new", "fork 跑完了。")
    assert rec["status"] == "completed" and rec["output_summary"] == "fork 跑完了。" and rec["result_turn_seq"] == 4


def test_workflow_script_is_task_text(run):
    """Workflow 的 script 當任務文字。"""
    wf = _tool_use("Workflow", {"script": "export const meta = {name: 'x'}\nawait agent('查 alphakeyword')"}, "toolu_wf")
    ctx, decisions, _ = run({"turn_seq": 1}, wf)
    assert ctx and "atoms=alpha-atom" in ctx and decisions == ["sent"]


def test_no_state_still_sends_without_record(run):
    """state 讀不到 → 照送，沒地方登記（recorded=False）、不寫 state。"""
    ctx, decisions, writes = run(None, SKILL_HIT)
    assert ctx and decisions == ["sent"] and writes == 0 and run.logs[0][1]["recorded"] is False


# ─── ③ 拿不到任務文字 ─────────────────────────────────────────────

@pytest.mark.parametrize("last", [
    {"type": "text", "text": "做完了。"},                                    # 最近一則是文字：沒有派工中的工具
    _tool_use("Bash", {"command": "echo alphakeyword"}, "toolu_bash"),     # 不在表上的工具不當任務文字
    _tool_use("Skill", {}, "toolu_empty"),                                 # 欄位全空
    None,                                                                  # 逐字稿不在
])
def test_no_task_text_not_sent(run, last):
    ctx, decisions, writes = run({"turn_seq": 1}, last)
    assert ctx is None and decisions == ["no_task_text"] and writes == 0


# ─── ④ Agent 路與沒挑到卡 ─────────────────────────────────────────────

@pytest.mark.parametrize("tool", ["Agent", "Task"])
def test_agent_tool_route_left_to_pre_tool_use(run, tool):
    """Agent／Task 派的已由 PreToolUse 用同一份 prompt 挑過 → 不送（即使 prompt 命中卡）。"""
    ctx, decisions, _ = run({"turn_seq": 1}, _tool_use(tool, {"prompt": "處理 alphakeyword"}, "toolu_agent"))
    assert ctx is None and decisions == ["agent_tool_route"] and run.logs[0][1]["spawn_tool"] == tool


def test_text_without_match_not_sent(run):
    ctx, decisions, writes = run({"turn_seq": 1}, _tool_use("Skill", {"skill": "zzqq", "args": "xyzzy"}))
    assert ctx is None and decisions == ["no_match"] and writes == 0 and run.logs[0][1]["text_head"] == "zzqq\nxyzzy"


# ─── 接線與規則 ─────────────────────────────────────────────

def test_dispatcher_routes_subagent_start():
    assert dispatcher.HANDLERS["SubagentStart"] == ("handlers.subagent_start", "handle_subagent_start")
    assert RULE in rr.RULES and "handlers/subagent_start" in rr.RULES[RULE]


def test_e2e_real_entry_send_then_skip_then_fill(tmp_path):
    """真入口子行程（寫碼守門開）：SubagentStart 送卡、state 檔登記 → 同 agent_id 再跑不送 → SubagentStop 回填該筆。"""
    _write_memory(tmp_path)
    (tmp_path / "workflow").mkdir()
    state_file = tmp_path / "workflow" / f"state-{SID}.json"
    state_file.write_text(json.dumps({"turn_seq": 2, "turn_prompts_seq": 2}), encoding="utf-8")
    proj = tmp_path / "proj"
    proj.mkdir()
    tp = _transcript(tmp_path / "parent.jsonl", SKILL_HIT)
    env = {k: v for k, v in os.environ.items() if k not in ("WG_V6", "CLAUDE_COMPANION_JUDGE", "PYTEST_CURRENT_TEST")}
    env.update({"WG_CLAUDE_DIR": str(tmp_path), "WG_TEST_LOGS_DIR": str(tmp_path / "Logs"), "WG_CODING_GUARD": "1"})
    base = {"session_id": SID, "cwd": str(proj), "transcript_path": tp, "agent_id": "ag-e2e", "agent_type": "general-purpose"}

    def hook(event, **extra):
        r = subprocess.run([sys.executable, str(HOOKS_DIR / "workflow-guardian.py")],
                           input=json.dumps({"hook_event_name": event, **base, **extra}).encode(),
                           env=env, cwd=proj, capture_output=True, timeout=120)
        assert r.returncode == 0, r.stderr[-600:]
        return r.stdout.decode("utf-8").strip()

    out = json.loads(hook("SubagentStart"))["hookSpecificOutput"]
    assert out["hookEventName"] == "SubagentStart" and "atoms=alpha-atom" in out["additionalContext"]
    recs = json.loads(state_file.read_text(encoding="utf-8"))["subagent_injections"]
    assert len(recs) == 1 and recs[0]["agent_id"] == "ag-e2e" and recs[0]["status"] == "async_launched"
    assert hook("SubagentStart") == ""
    hook("SubagentStop", last_assistant_message="fork 跑完了。", agent_transcript_path="")
    recs = json.loads(state_file.read_text(encoding="utf-8"))["subagent_injections"]
    assert len(recs) == 1 and recs[0]["status"] == "completed" and recs[0]["output_summary"] == "fork 跑完了。"
    log = (tmp_path / "Logs" / "guard-subagent_start.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(x)["decision"] for x in log] == ["sent", "registered"]


if __name__ == "__main__":
    rc = subprocess.run([sys.executable, "-X", "utf8", "-m", "pytest", __file__, "-q", "-p", "no:cacheprovider"]).returncode
    print("SUBAGENT_START_CHECK PASS" if rc == 0 else "SUBAGENT_START_CHECK FAIL")
    sys.exit(0 if rc == 0 else 1)

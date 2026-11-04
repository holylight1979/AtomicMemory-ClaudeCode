"""SubagentStart handler：補「沒經過 Agent 工具的子代理」的記憶注入（規則 SUBAGENT_START_NON_AGENT_INJECT）。

Agent／Task 派的子代理由 PreToolUse 依任務 prompt 挑卡、塞進 prompt（handlers/pre_tool_use）；skill 的 context: fork、
Workflow 起的子代理不經 Agent 工具，PreToolUse 抓不到，在這裡補，用 additionalContext 送（加在子代理對話開頭）。
SubagentStart 輸入只有 agent_id、agent_type，沒有委派提示詞；子代理自己的逐字稿與 meta 檔在 hook 觸發時還沒落檔，
拿得到的任務文字只有父 session 逐字稿最近一則 assistant 動作（派工那一下的 tool_use）的輸入。

判法（先到先贏）：
1. agent_id 已在 state 的 subagent_injections（續跑的子代理、隊友收新訊息）→ 不送。
2. 最近一則 assistant 動作是 Agent／Task → PreToolUse 已用同一份 prompt 挑過 → 不送。
3. 是 Skill／Workflow → 輸入欄位當任務文字，挑卡（pre_tool_use.pick_subagent_memory，預算同子代理注入）；
   挑到就送，並在 subagent_injections 登記一筆（status async_launched＝等 SubagentStop 依 agent_id 回填結果）。
4. 其他（拿不到任務文字）→ 不送。
每次判定寫 Logs/guard-subagent_start.jsonl 一筆（decision 欄）。出錯由 dispatcher 接住：stderr＋atom-debug，不送。
"""
import json
from typing import Any, Dict, List, Optional

from wg_core import _atom_debug_log, _now_iso, append_guard_log, output_json, output_nothing, read_state, write_state

GUARD = "subagent_start"
AGENT_TOOLS = ("Agent", "Task")   # PreToolUse 已依同一份 prompt 挑過卡
# 不經 Agent 工具、會起子代理的工具 → 任務文字在哪幾個輸入欄位
SPAWN_TEXT_FIELDS = {
    "Skill": ("skill", "args"),                             # skill 的 context: fork
    "Workflow": ("name", "scriptPath", "script", "args"),   # 動態工作流程
}
TAIL_BYTES = 1_000_000   # 只讀父逐字稿尾段：派工那一下是最近一則 assistant 動作


def _last_assistant_tool_use(transcript_path: str) -> Dict[str, Any]:
    """父 session 逐字稿最近一則 assistant 動作若是 tool_use，回那個區塊（name／id／input）；是文字或讀不到回 {}。"""
    try:
        with open(transcript_path, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - TAIL_BYTES))
            data = f.read()
    except OSError:
        return {}
    for raw in reversed(data.decode("utf-8", errors="ignore").splitlines()):
        if '"assistant"' not in raw:
            continue
        try:
            obj = json.loads(raw)
        except ValueError:
            continue   # 尾段第一行可能被截半
        if not isinstance(obj, dict) or obj.get("type") != "assistant":
            continue
        blocks = [b for b in (obj.get("message") or {}).get("content") or [] if isinstance(b, dict)]
        return blocks[-1] if blocks and blocks[-1].get("type") == "tool_use" else {}
    return {}


def _task_text(tool_use: Dict[str, Any]) -> str:
    """派工 tool_use 的任務文字：照 SPAWN_TEXT_FIELDS 取輸入欄位串起來；不在表上的工具回 ""。"""
    inp = tool_use.get("input")
    if not isinstance(inp, dict):
        return ""
    values = [inp.get(k) for k in SPAWN_TEXT_FIELDS.get(str(tool_use.get("name") or ""), ()) if inp.get(k)]
    return "\n".join(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False) for v in values).strip()


def _record(state: Optional[Dict[str, Any]], session_id: str, agent_id: str, agent_type: str,
            spawn: Dict[str, Any], atoms: List[str]) -> bool:
    """subagent_injections 登記一筆（欄位同 PostToolUse(Agent) 那筆），status async_launched＝還沒收尾，
    SubagentStop 依 agent_id 回填結果、Stop 收到結果才歸因。沒有 state 或 agent_id 回 False。"""
    if state is None or not agent_id:
        return False
    from handlers.post_tool_use import _SUBAGENT_INJ_CAP   # 惰性 import：只在真的送卡時付
    injections = state.setdefault("subagent_injections", [])
    injections.append({"agent_id": agent_id, "agent_type": agent_type, "atoms": atoms, "status": "async_launched",
                       "output_summary": "", "tool_use_id": str(spawn.get("id") or ""),
                       "turn_seq": int(state.get("turn_seq", 0) or 0), "at": _now_iso()})
    state["subagent_injections"] = injections[-_SUBAGENT_INJ_CAP:]
    write_state(session_id, state)
    return True


def _skip(decision: str, log: Dict[str, Any]) -> None:
    append_guard_log(GUARD, {**log, "decision": decision})
    output_nothing()


def handle_subagent_start(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    session_id = str(input_data.get("session_id") or "")
    agent_id = str(input_data.get("agent_id") or "")
    agent_type = str(input_data.get("agent_type") or "")
    log: Dict[str, Any] = {"session_id": session_id, "agent_id": agent_id, "agent_type": agent_type}
    state = read_state(session_id) if session_id else None
    registered = {r.get("agent_id") for r in (state or {}).get("subagent_injections") or [] if isinstance(r, dict)}
    if agent_id and agent_id in registered:
        return _skip("registered", log)
    spawn = _last_assistant_tool_use(str(input_data.get("transcript_path") or ""))
    log["spawn_tool"] = str(spawn.get("name") or "")
    if log["spawn_tool"] in AGENT_TOOLS:
        return _skip("agent_tool_route", log)
    text = _task_text(spawn)
    if not text:
        return _skip("no_task_text", log)
    from handlers.pre_tool_use import pick_subagent_memory   # 惰性 import：前面幾種不送的路不付
    blob, atoms = pick_subagent_memory(text, [])
    if not atoms:
        return _skip("no_match", {**log, "text_head": text[:80]})
    recorded = _record(state, session_id, agent_id, agent_type, spawn, atoms)
    append_guard_log(GUARD, {**log, "decision": "sent", "atoms": atoms, "recorded": recorded})
    _atom_debug_log("SubagentInject", f"event=SubagentStart type={agent_type or '-'} via={log['spawn_tool']} "
                                      f"injected={atoms} blob_tokens=~{len(blob) // 4} text_head={text[:60]!r}", config)
    output_json({"hookSpecificOutput": {"hookEventName": "SubagentStart", "additionalContext": blob}})

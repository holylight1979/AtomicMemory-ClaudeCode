"""audit.py — One-shot Codex Companion assessment subprocess.

Replaces the threaded `_run_assessment` worker that used to live in
service.py (V4 daemon @ port 3850). Spawned fire-and-forget by
hooks/codex_companion.py whenever a checkpoint or turn audit fires.

Protocol:
  stdin  — JSON: { session_id, turn_index, assessment_type, cwd, context }
  stdout — DEVNULL (assessment result written via state.write_assessment)
  stderr — log lines tagged "[audit HH:MM:SS] ..."

Lifetime: bounded by codex CLI assessment_timeout (default 60s) + retry.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SERVICE_DIR))

import state as companion_state  # noqa: E402
import assessor  # noqa: E402


CLAUDE_DIR = Path.home() / ".claude"
WORKFLOW_DIR = CLAUDE_DIR / "workflow"
CONFIG_PATH = WORKFLOW_DIR / "config.json"


def _log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"[audit {ts}] {msg}", file=sys.stderr, flush=True)


def _load_config() -> dict:
    try:
        full = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return full.get("codex_companion", {})
    except (OSError, json.JSONDecodeError):
        return {}


def main() -> int:
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8")

    try:
        raw = sys.stdin.buffer.read()
        turn_data = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as e:
        _log(f"bad stdin: {e}")
        return 1

    session_id = turn_data.get("session_id", "")
    if not session_id:
        _log("session_id required")
        return 1

    turn_index = int(turn_data.get("turn_index", 0))
    assessment_type = turn_data.get("assessment_type", "turn_audit")
    cwd = turn_data.get("cwd", "")
    context = turn_data.get("context") or {}

    config = _load_config()
    st = companion_state.read_state(session_id) or {}
    tool_trace = st.get("tool_trace", [])
    if not cwd:
        cwd = st.get("cwd", "")

    # Merge context with state (mirror service.py _run_assessment)
    context.setdefault("turn_index", turn_index)
    if "last_assistant_tail" not in context:
        context["last_assistant_tail"] = st.get("last_assistant_tail", "")
    # 全審計類型共用背景/計數：user_goal（brief「背景」要件）與
    # trace_dropped（trace 計數標頭的總量分母）
    context.setdefault("user_goal", st.get("user_goal", ""))
    context.setdefault("trace_dropped", int(st.get("trace_dropped", 0) or 0))

    try:
        result = assessor.run_assessment(
            assessment_type=assessment_type,
            session_id=session_id,
            tool_trace=tool_trace,
            cwd=cwd,
            extra_context=context,
            config=config,
        )
        result["_turn_index"] = turn_index

        category = str(result.get("category", "")).lower()
        summary = str(result.get("summary", ""))
        if category == "system" and "sandbox" in summary:
            companion_state.increment_metric(session_id, "sandbox_failures")
        elif result.get("notify_next_turn"):
            companion_state.increment_metric(session_id, "empty_returns")

        companion_state.write_assessment(session_id, turn_index, assessment_type, result)
        _log(
            f"done {session_id[:8]} t{turn_index} type={assessment_type} "
            f"status={result.get('status')} attempts={result.get('_attempts', 1)}"
        )
        return 0
    except Exception as e:
        _log(f"assessment error: {e}")
        companion_state.write_assessment(session_id, turn_index, assessment_type, {
            "status": "error",
            "severity": "low",
            "category": "system",
            "summary": f"Assessment failed: {e}",
        })
        return 1


if __name__ == "__main__":
    sys.exit(main())

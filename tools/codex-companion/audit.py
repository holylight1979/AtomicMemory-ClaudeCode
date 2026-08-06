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


def _write_acceptance_audit(
    session_id: str, turn_index: int, cwd: str, context: dict,
    result: dict, diff_truncated: bool, elapsed_ms: int, config: dict,
) -> None:
    """影子期唯一的數據來源：每次 acceptance_review 落一筆 jsonl。

    `human_label` 留 null，Phase 3 開工前一次性回顧標註（Q5 precision 分母）。
    """
    import acceptance
    problems = result.get("problems") or []
    acceptance.append_audit({
        "session_id": session_id,
        "turn_index": turn_index,
        "cwd": cwd,
        "model": config.get("model", ""),
        "spec_path": context.get("spec_path", ""),
        "task_slug": context.get("task_slug", ""),
        "binding": context.get("binding", ""),
        "trigger": context.get("trigger", ""),
        "verdict": result.get("verdict", ""),
        "score": result.get("score", -1),
        "severity": result.get("severity", "low"),
        "confidence": result.get("confidence", ""),
        "summary": result.get("summary", ""),
        "problems_count": len(problems),
        "problems": problems[:10],
        "uncertain_reason": result.get("uncertain_reason", ""),
        "prompt_chars": result.get("_prompt_chars", 0),
        "diff_truncated": diff_truncated,
        "codex_attempts": result.get("_attempts", 1),
        "elapsed_ms": elapsed_ms,
    })


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

    # acceptance_review：diff 採樣在本子程序做（git subprocess 不阻塞 hook）
    diff_truncated = False
    if assessment_type == "acceptance_review":
        import acceptance
        digest, diff_truncated = acceptance.collect_diff_digest(cwd)
        context["diff_digest"] = digest

    started = time.time()
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
        if assessment_type == "acceptance_review":
            _write_acceptance_audit(
                session_id, turn_index, cwd, context, result,
                diff_truncated, int((time.time() - started) * 1000), config,
            )
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
        # 裁判崩潰也要留痕：影子數據不得因例外而無聲缺一筆
        if assessment_type == "acceptance_review":
            try:
                import acceptance
                acceptance.append_audit({
                    "session_id": session_id, "turn_index": turn_index,
                    "cwd": cwd,
                    "spec_path": context.get("spec_path", ""),
                    "task_slug": context.get("task_slug", ""),
                    "binding": context.get("binding", ""),
                    "trigger": context.get("trigger", ""),
                    "verdict": "uncertain",
                    "uncertain_reason": f"審計程序異常：{type(e).__name__}: {e}",
                    "score": -1, "problems": [], "problems_count": 0,
                })
            except Exception as e2:
                _log(f"audit jsonl on-error write failed: {e2}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

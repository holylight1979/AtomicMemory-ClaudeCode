"""state.py — Per-session state management for Codex Companion.

State files: ~/.claude/workflow/companion-state-{session_id}.json
Assessment files: ~/.claude/workflow/companion-assessment-{session_id}.json

Atomic writes: .tmp + rename (same pattern as wg_core).
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

WORKFLOW_DIR = Path.home() / ".claude" / "workflow"

_TZ = timezone(timedelta(hours=8))

_state_lock = threading.Lock()


def _now_iso() -> str:
    return datetime.now(_TZ).isoformat(timespec="seconds")


def _state_path(session_id: str) -> Path:
    return WORKFLOW_DIR / f"companion-state-{session_id}.json"


def _atomic_write(path: Path, data: Dict[str, Any]) -> None:
    """Write JSON atomically via .tmp + rename."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


# --- Session state ---

def new_state(session_id: str, cwd: str) -> Dict[str, Any]:
    return {
        "session_id": session_id,
        "cwd": cwd,
        "started_at": _now_iso(),
        "tool_trace": [],
        "checkpoints_triggered": [],
        "assessments_requested": 0,
        "assessments_by_type": {},   # Q8 配額分桶：{type: count}
        "acceptance_reviews": {},    # {spec_path: count}，同一份規格的重審上限
        "assessments_completed": 0,
        "turn_index": 0,
        "last_assistant_tail": "",
        "user_goal": "",
        "trace_dropped": 0,
        "last_updated": _now_iso(),
    }


USER_GOAL_HEAD = 1600
USER_GOAL_TAIL = 400


def set_user_goal(session_id: str, text: str) -> None:
    """Capture 使用者原始目標（首個非空 prompt，codex brief 的「背景」要件）。

    Write-once：已有值不覆寫，保「原始目標」語意。Thread-safe。

    超長採**頭尾**並附 in-band 標記：需求的紅線/禁止事項常寫在 prompt 末段，
    純頭部截斷會讓裁判看不到紅線；靜默截斷更會被誤讀成「使用者沒要求」
    （INV-EVIDENCE-PIPE-HONESTY）。
    """
    text = (text or "").strip()
    if not text:
        return
    if len(text) > USER_GOAL_HEAD + USER_GOAL_TAIL:
        text = (
            text[:USER_GOAL_HEAD]
            + f"\n…（需求原話中段省略：全文共 {len(text)} 字，此處僅含開頭 "
              f"{USER_GOAL_HEAD} 字與結尾 {USER_GOAL_TAIL} 字；"
              "此為擷取採樣，不是使用者沒說）…\n"
            + text[-USER_GOAL_TAIL:]
        )
    with _state_lock:
        st = read_state(session_id)
        if st is None:
            st = new_state(session_id, "")
        if st.get("user_goal"):
            return
        st["user_goal"] = text
        write_state(session_id, st)


def increment_turn(session_id: str) -> int:
    """Increment turn_index and return new value. Thread-safe."""
    with _state_lock:
        st = read_state(session_id)
        if st is None:
            st = new_state(session_id, "")
        st["turn_index"] = int(st.get("turn_index", 0)) + 1
        write_state(session_id, st)
        return st["turn_index"]


def update_last_assistant_tail(session_id: str, text: str) -> None:
    """Persist last assistant tail for assessor context. Thread-safe."""
    with _state_lock:
        st = read_state(session_id)
        if st is None:
            st = new_state(session_id, "")
        st["last_assistant_tail"] = (text or "")[:2000]
        write_state(session_id, st)


def read_state(session_id: str) -> Optional[Dict[str, Any]]:
    path = _state_path(session_id)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def write_state(session_id: str, state: Dict[str, Any]) -> None:
    state["last_updated"] = _now_iso()
    _atomic_write(_state_path(session_id), state)


def ensure_state(session_id: str, cwd: str = "") -> Dict[str, Any]:
    """Read existing state or create new. Thread-safe via _state_lock."""
    with _state_lock:
        st = read_state(session_id)
        if st is None:
            st = new_state(session_id, cwd)
            write_state(session_id, st)
    return st


def append_event(session_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
    """Append a tool/event record to session state. Thread-safe."""
    with _state_lock:
        st = read_state(session_id)
        if st is None:
            st = new_state(session_id, "")
        trace = st.setdefault("tool_trace", [])

        # Keep trace bounded to avoid unbounded growth。
        # 丟棄量累計在 trace_dropped：下游 prompt 的 trace 計數標頭
        # (showing last N of M) 需要總量，砍歷史不得無聲。
        MAX_TRACE = 200
        if len(trace) >= MAX_TRACE:
            keep = MAX_TRACE // 2
            st["trace_dropped"] = int(st.get("trace_dropped", 0)) + (len(trace) - keep)
            trace[:] = trace[-keep:]

        event["timestamp"] = _now_iso()
        trace.append(event)
        write_state(session_id, st)
    return st


def record_checkpoint(
    session_id: str, checkpoint_type: str, spec_path: str = ""
) -> None:
    """Record that a checkpoint was triggered. Thread-safe.

    同時累加 per-type 計數（Q8 配額分桶的依據）與 per-spec 重審計數
    （同一份驗收規格的重複審計上限）。
    """
    with _state_lock:
        st = read_state(session_id)
        if st is None:
            st = new_state(session_id, "")
        st.setdefault("checkpoints_triggered", []).append({
            "type": checkpoint_type,
            "at": _now_iso(),
        })
        st["assessments_requested"] = st.get("assessments_requested", 0) + 1
        by_type = st.setdefault("assessments_by_type", {})
        by_type[checkpoint_type] = int(by_type.get(checkpoint_type, 0)) + 1
        if spec_path:
            per_spec = st.setdefault("acceptance_reviews", {})
            key = spec_path.replace("\\", "/")
            per_spec[key] = int(per_spec.get(key, 0)) + 1
        write_state(session_id, st)


# --- Assessment cache (per-turn-id) ---

def _assessment_turn_path(session_id: str, turn_index: int, assessment_type: str) -> Path:
    return WORKFLOW_DIR / f"companion-assessment-{session_id}-t{turn_index}-{assessment_type}.json"


def write_assessment(
    session_id: str,
    turn_index: int,
    assessment_type: str,
    assessment: Dict[str, Any],
) -> None:
    """Write assessment result for pickup by UserPromptSubmit hook. Thread-safe.

    Per-turn-id naming: companion-assessment-{sid}-t{N}-{type}.json
    """
    with _state_lock:
        data = {
            "session_id": session_id,
            "turn_index": turn_index,
            "type": assessment_type,
            "assessment": assessment,
            "created_at": _now_iso(),
            "injected": False,
        }
        _atomic_write(_assessment_turn_path(session_id, turn_index, assessment_type), data)

        # Also update state counter (within same lock to prevent race with append_event)
        st = read_state(session_id)
        if st:
            st["assessments_completed"] = st.get("assessments_completed", 0) + 1
            write_state(session_id, st)


def list_pending_assessments(session_id: str) -> List[Dict[str, Any]]:
    """List all not-yet-injected assessments for a session, sorted by turn_index ASC.

    Each entry: {"path": Path, "turn_index": int, "type": str, "data": dict}
    """
    pending = []
    pattern = f"companion-assessment-{session_id}-t*.json"
    for path in WORKFLOW_DIR.glob(pattern):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if data.get("injected", False):
            continue
        assessment = data.get("assessment", {})
        if not assessment or assessment.get("status") == "error":
            continue
        pending.append({
            "path": path,
            "turn_index": int(data.get("turn_index", 0)),
            "type": data.get("type", assessment.get("_assessment_type", "review")),
            "data": data,
        })
    pending.sort(key=lambda x: (x["turn_index"], x["type"]))
    return pending


def mark_assessment_path_injected(path: Path) -> None:
    """Mark a specific assessment file as injected."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data["injected"] = True
        _atomic_write(path, data)
    except (json.JSONDecodeError, OSError):
        pass


def cleanup(session_id: str) -> None:
    """Remove state, metrics and per-turn assessment files for a session."""
    paths: List[Path] = [_state_path(session_id), _metrics_path(session_id)]
    paths.extend(WORKFLOW_DIR.glob(f"companion-assessment-{session_id}-t*.json"))
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


# --- observability metrics（獨立檔避免與 state 競爭寫入）---

def _metrics_path(session_id: str) -> Path:
    return WORKFLOW_DIR / f"companion-metrics-{session_id}.json"


_METRIC_KEYS = (
    "audits_skipped_by_score",
    "audits_skipped_no_artifact",  # plan_review 解析不到計畫 artifact → skip（不空審）
    "audits_total_attempted",  # §四 C3 ratio 分母用
    "empty_returns",
    "sandbox_failures",
    "behavior_gap_blocks",
    "quality_gap_advises",
    # acceptance_review（Phase 2 影子裁判）
    "acceptance_reviews_spawned",   # 實際發給裁判的次數
    "acceptance_unbound",           # 綁不到規格檔 → 直接記 uncertain 未發審計
    "acceptance_quota_blocked",     # 撞配額上限被擋（可觀測性：不得無聲跳過）
)


def increment_metric(session_id: str, name: str, delta: int = 1) -> None:
    """Increment a per-session counter. Best-effort, fail-silent.

    跨 process（hook + service）有微小 race window，但對觀測指標來說
    遺失 1-2 次累加可接受。獨立檔 companion-metrics-{sid}.json 避免污染
    主 state（service 主寫入路徑）。
    """
    if name not in _METRIC_KEYS:
        return
    path = _metrics_path(session_id)
    with _state_lock:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        data[name] = int(data.get(name, 0)) + delta
        try:
            _atomic_write(path, data)
        except OSError:
            pass


def read_metrics(session_id: str) -> Dict[str, int]:
    """Read all metric counters for a session (zero defaults for未累加項)。"""
    path = _metrics_path(session_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    return {k: int(data.get(k, 0)) for k in _METRIC_KEYS}

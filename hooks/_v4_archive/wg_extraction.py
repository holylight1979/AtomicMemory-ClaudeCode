"""
wg_extraction.py — Per-turn 萃取管線、Worker 管理、Failure 偵測

Transcript 讀取、per-turn 增量萃取、failure keyword 偵測、
extract-worker subprocess 管理。
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from wg_paths import CLAUDE_DIR, cwd_to_project_slug, get_transcript_path
from wg_core import (
    _now_iso, _atom_debug_log, _atom_debug_error,
    write_state,
)
from wg_atoms import _kw_match


# ─── Process Utilities ───────────────────────────────────────────────────────


def _is_pid_alive(pid: int) -> bool:
    """Check if a process is still running."""
    if not pid:
        return False
    if sys.platform == "win32":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid
        )
        if h:
            ctypes.windll.kernel32.CloseHandle(h)
            return True
        return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


# ─── Lease-based Concurrency ────────────────────────────────────────────────

_DEFAULT_LEASE_TTL = 300  # 5 minutes


def _is_lease_valid(state: dict, key: str) -> bool:
    """Check if a worker lease is still valid (not expired AND PID alive).

    Lease format in state: {key}: {"pid": int, "expires_at": float}
    Handles legacy format where {key} is a bare PID int.
    """
    import time as _time
    lease = state.get(key)
    if not lease:
        return False
    # Legacy: bare PID int → treat as expired (force migration)
    if isinstance(lease, int):
        return _is_pid_alive(lease)
    pid = lease.get("pid", 0)
    expires_at = lease.get("expires_at", 0)
    if _time.time() > expires_at:
        return False
    return _is_pid_alive(pid)


def _set_lease(state: dict, key: str, pid: int, ttl: int = _DEFAULT_LEASE_TTL) -> None:
    """Write a lease entry into state."""
    import time as _time
    state[key] = {"pid": pid, "expires_at": _time.time() + ttl}


# ─── Transcript Helpers ──────────────────────────────────────────────────────


def _find_transcript(session_id: str, cwd: str):
    """Find session transcript JSONL file."""
    return get_transcript_path(session_id, cwd)


def _count_new_assistant_chars(transcript_path, byte_offset: int) -> int:
    """Lightweight pre-scan: count assistant text chars from byte_offset."""
    total = 0
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            if byte_offset > 0:
                f.seek(byte_offset)
            for raw_line in f:
                try:
                    obj = json.loads(raw_line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if obj.get("type") != "assistant":
                    continue
                content = obj.get("message", {}).get("content", [])
                if not isinstance(content, list):
                    continue
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        t = block.get("text", "")
                        if t and len(t) > 30:
                            total += len(t)
    except (OSError, UnicodeDecodeError):
        pass
    return total


# ─── Worker Spawning ─────────────────────────────────────────────────────────


def _spawn_extract_worker(ctx_dict: dict) -> int:
    """Spawn extract-worker.py as detached subprocess. Returns PID or 0."""
    import subprocess as _sp
    worker_path = CLAUDE_DIR / "hooks" / "extract-worker.py"
    if not worker_path.exists():
        return 0
    try:
        kwargs = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = _sp.CREATE_NO_WINDOW | _sp.DETACHED_PROCESS
        else:
            kwargs["start_new_session"] = True
        worker_log = CLAUDE_DIR / "workflow" / "extract-worker.log"
        worker_log_fh = open(worker_log, "a", encoding="utf-8")
        # Force UTF-8 encoding in worker subprocess (prevents cp950 errors on CJK Windows)
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            json_ctx = json.dumps(ctx_dict, ensure_ascii=False)
            proc = _sp.Popen(
                [sys.executable, str(worker_path)],
                stdin=_sp.PIPE,
                stdout=_sp.DEVNULL,
                stderr=worker_log_fh,
                env=env,
                **kwargs,
            )
        except Exception:
            worker_log_fh.close()
            raise
        proc.stdin.write(json_ctx.encode("utf-8"))
        proc.stdin.close()
        # Close our copy of the log fd — child process has its own fd via inheritance.
        # Without this, this process holds the fd open until exit.
        worker_log_fh.close()
        return proc.pid
    except Exception as e:
        _atom_debug_error("萃取:_spawn_extract_worker", e)
        return 0


# ─── Per-turn Extraction ─────────────────────────────────────────────────────


def _maybe_spawn_per_turn_extraction(
    session_id: str, state: Dict[str, Any], config: Dict[str, Any]
) -> None:
    """Conditionally spawn per-turn incremental extraction."""
    rc = config.get("response_capture", {})
    pt = rc.get("per_turn", {})
    if not pt.get("enabled", False):
        return

    # Cooldown check
    last_at = state.get("last_per_turn_extraction_at", "")
    if last_at:
        cooldown = pt.get("cooldown_seconds", 120)
        try:
            last_t = datetime.fromisoformat(last_at)
            if (datetime.now().astimezone() - last_t).total_seconds() < cooldown:
                return
        except (ValueError, TypeError):
            pass

    # Concurrency guard (lease-based)
    if _is_lease_valid(state, "extract_worker_pid"):
        return

    # Check new content since last extraction
    cwd = state.get("session", {}).get("cwd", "")
    transcript = _find_transcript(session_id, cwd)
    if not transcript:
        return

    prev_offset = state.get("extraction_offset", 0)
    file_size = transcript.stat().st_size
    if file_size <= prev_offset:
        return

    new_chars = _count_new_assistant_chars(transcript, prev_offset)
    min_chars = pt.get("min_new_chars", 500)
    if new_chars < min_chars:
        return

    # Resolve intent
    tracker = state.get("topic_tracker", {})
    dist = tracker.get("intent_distribution", {})
    intent = max(dist, key=dist.get, default="build") if dist else "build"

    # Spawn worker
    worker_ctx = {
        "session_id": session_id,
        "cwd": cwd,
        "config": config,
        "knowledge_queue": state.get("knowledge_queue", []),
        "session_intent": intent,
        "mode": "per_turn",
        "byte_offset": prev_offset,
    }
    pid = _spawn_extract_worker(worker_ctx)
    if pid:
        _set_lease(state, "extract_worker_pid", pid)
        state["last_per_turn_extraction_at"] = _now_iso()
        write_state(session_id, state)
        print(
            f"[v2.12] per-turn extract-worker spawned (pid={pid}, offset={prev_offset}, new_chars={new_chars})",
            file=sys.stderr,
        )


# ─── Failure Detection ───────────────────────────────────────────────────────


def _detect_failure_keywords(prompt: str, config: dict) -> bool:
    """偵測使用者輸入是否含失敗回報關鍵字。"""
    fc = config.get("response_capture", {}).get("failure_extraction", {})
    if not fc.get("enabled", False):
        return False

    strong = fc.get("strong_keywords", [])
    weak = fc.get("weak_keywords", [])
    weak_min = fc.get("weak_min_match", 2)
    prompt_lower = prompt.lower()

    for kw in strong:
        if _kw_match(kw, prompt_lower):
            return True

    weak_hits = sum(1 for kw in weak if _kw_match(kw, prompt_lower))
    return weak_hits >= weak_min


def _maybe_spawn_failure_extraction(
    session_id: str, state: dict, config: dict,
    clean_prompt: str, lines: list,
) -> None:
    """偵測失敗關鍵字 → spawn extract-worker failure mode。"""
    if not _detect_failure_keywords(clean_prompt, config):
        return

    fc = config.get("response_capture", {}).get("failure_extraction", {})
    cooldown = fc.get("cooldown_seconds", 180)

    last_at = state.get("last_failure_extraction_at", "")
    if last_at:
        try:
            dt = datetime.fromisoformat(last_at)
            if (datetime.now().astimezone() - dt).total_seconds() < cooldown:
                return
        except (ValueError, TypeError):
            pass

    # Concurrency guard (lease-based)
    if _is_lease_valid(state, "failure_worker_pid"):
        return

    prev_offset = max(0, state.get("extraction_offset", 0) - 2000)
    cwd = state.get("session", {}).get("cwd", "")

    worker_ctx = {
        "session_id": session_id,
        "cwd": cwd,
        "config": config,
        "knowledge_queue": state.get("knowledge_queue", []),
        "session_intent": "debug",
        "mode": "failure",
        "byte_offset": prev_offset,
        "failure_prompt": clean_prompt[:500],
    }
    pid = _spawn_extract_worker(worker_ctx)
    if pid:
        _set_lease(state, "failure_worker_pid", pid)
        state["last_failure_extraction_at"] = _now_iso()
        lines.append("[Guardian:FailureDetect] 偵測到失敗回報，背景萃取中...")
        _atom_debug_log(
            "FailureDetect",
            f"Spawned failure extraction (pid={pid}), prompt: {clean_prompt[:100]}",
            config,
        )

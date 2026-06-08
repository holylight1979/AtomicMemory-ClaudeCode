"""
handlers/_shared.py — module-level state + 跨 handler 共用 helper

共用：
- regex 常數（_SUPERSEDES_RE / _V4_TRIGGER_LINE_RE / _MEMORY_MD_AUTO_HEADER）
- lazy import flag（WISDOM_AVAILABLE / DOCDRIFT_AVAILABLE / read_hot_cache）
- _call_project_hook（subprocess invoke project hook）
- _cleanup_old_states（state 檔 TTL 清理）
- _is_ephemeral_path（路徑過濾）
- _maybe_spawn_user_extract_worker（V4.1 user extract worker spawn）
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from wg_core import (
    CLAUDE_DIR, WORKFLOW_DIR,
    _now_iso, _atom_debug_error,
    write_state,
)
from wg_extraction import _is_lease_valid, _set_lease

# Windows: 外呼 python/git 等 console 程式時若不帶此 flag，無主控台的 hook 父行程會被配一個可見 console 視窗
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

# ─── module-level regex / 常數 ───────────────────────────────────────────────

_SUPERSEDES_RE = re.compile(r"^- Supersedes:\s*(.+)", re.MULTILINE)
_V4_TRIGGER_LINE_RE = re.compile(r"^-\s+Trigger:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
_MEMORY_MD_AUTO_HEADER = "<!-- AUTO-GENERATED: V4 role filter -->"

_EPHEMERAL_DIR_TOKENS = (
    "/pytest-of-",
    "/.pytest_cache/",
    "/__pycache__/",
)


# ─── Lazy import flags (graceful degrade) ────────────────────────────────────

try:
    from wisdom_engine import (
        classify_situation,
        get_reflection_summary,
        reflect as wisdom_reflect,
        track_retry as wisdom_track_retry,
    )
    WISDOM_AVAILABLE = True
except ImportError:
    WISDOM_AVAILABLE = False
    classify_situation = None
    get_reflection_summary = None
    wisdom_reflect = None
    wisdom_track_retry = None

try:
    from wg_extraction import read_hot_cache, mark_injected, HOT_CACHE_PATH, format_injection_line
except ImportError:
    read_hot_cache = None
    mark_injected = None
    HOT_CACHE_PATH = None
    format_injection_line = None

try:
    from wg_docdrift import (
        check_source_drift, resolve_doc_update, build_drift_advisory,
        prune_committed_entries,
    )
    DOCDRIFT_AVAILABLE = True
except ImportError:
    DOCDRIFT_AVAILABLE = False
    check_source_drift = None
    resolve_doc_update = None
    build_drift_advisory = None
    prune_committed_entries = None


# ─── Path helpers ────────────────────────────────────────────────────────────


def _is_ephemeral_path(path: str) -> bool:
    """過濾測試/快取/系統 tmp 路徑，避免污染 modified_files。"""
    if not path:
        return False
    norm = path.replace("\\", "/")
    try:
        tmp_root = tempfile.gettempdir().replace("\\", "/").rstrip("/")
        if tmp_root and norm.lower().startswith(tmp_root.lower() + "/"):
            return True
    except Exception:
        pass
    norm_low = norm.lower()
    return any(tok in norm_low for tok in _EPHEMERAL_DIR_TOKENS)


# ─── Project delegate hook (V2.21) ───────────────────────────────────────────


def _call_project_hook(project_root: Path, action: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Call project-level delegate hook via subprocess isolation.

    {project_root}/.claude/hooks/project_hooks.py
    Stdin/stdout JSON. Timeout 5s. Never raises.
    """
    hook_script = project_root / ".claude" / "hooks" / "project_hooks.py"
    if not hook_script.exists():
        return None
    try:
        result = subprocess.run(
            [sys.executable, str(hook_script), action],
            input=json.dumps(context, ensure_ascii=False),
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=_NO_WINDOW,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError, Exception) as e:
        _atom_debug_error(f"project_hook:{action}", e)
    return None


# ─── State file TTL cleanup (was _cleanup_old_states in workflow-guardian) ───


def _cleanup_old_states() -> None:
    """V3/2.2A: Tiered TTL cleanup for state files.
    age < 600s keep; merged_into → 10min; empty working → 10min; working >30min;
    done synced > 1h; done pending > 4h; anything > 7d.
    """
    now = time.time()
    for f in WORKFLOW_DIR.glob("state-*.json"):
        try:
            age = now - f.stat().st_mtime
            if age < 600:
                continue

            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except (json.JSONDecodeError, OSError):
                if age > 7 * 86400:
                    f.unlink(missing_ok=True)
                continue

            phase = data.get("phase", "")
            prompt_count = data.get("topic_tracker", {}).get("prompt_count", 0)
            merged = data.get("merged_into")
            sync_pending = data.get("sync_pending", False)

            if merged and age > 600:
                f.unlink(missing_ok=True)
            elif prompt_count == 0 and phase == "working" and age > 600:
                f.unlink(missing_ok=True)
            elif prompt_count > 0 and phase == "working" and age > 1800:
                f.unlink(missing_ok=True)
            elif phase == "done" and not sync_pending and age > 3600:
                f.unlink(missing_ok=True)
            elif phase == "done" and sync_pending and age > 14400:
                f.unlink(missing_ok=True)
            elif age > 7 * 86400:
                f.unlink(missing_ok=True)
        except OSError:
            pass


# ─── V4.1: User Extract Worker Spawning ──────────────────────────────────────


def _maybe_spawn_user_extract_worker(
    session_id: str, state: Dict[str, Any], config: Dict[str, Any],
) -> bool:
    """Spawn user-extract-worker.py as detached subprocess if conditions met.

    Returns True if spawned (worker will call session evaluator itself),
    False if skipped (caller should run fallback evaluator).
    """
    ue_config = config.get("userExtraction", {})
    if not ue_config.get("enabled", False):
        return False

    pending = state.get("pending_user_extract", [])
    if not pending:
        return False

    if _is_lease_valid(state, "user_extract_worker_pid"):
        return False

    worker_path = CLAUDE_DIR / "hooks" / "user-extract-worker.py"
    if not worker_path.exists():
        return False

    cwd = state.get("session", {}).get("cwd", "")
    user_id = state.get("user_identity", {})
    user = user_id.get("user", "holylight")

    worker_ctx = {
        "session_id": session_id,
        "cwd": cwd,
        "config": config,
        "user": user,
    }

    try:
        import subprocess as _sp
        kwargs = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = _sp.CREATE_NO_WINDOW | _sp.DETACHED_PROCESS
        else:
            kwargs["start_new_session"] = True

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        json_ctx = json.dumps(worker_ctx, ensure_ascii=False)
        proc = _sp.Popen(
            [sys.executable, str(worker_path)],
            stdin=_sp.PIPE,
            stdout=_sp.DEVNULL,
            stderr=_sp.DEVNULL,
            env=env,
            **kwargs,
        )
        proc.stdin.write(json_ctx.encode("utf-8"))
        proc.stdin.close()

        _set_lease(state, "user_extract_worker_pid", proc.pid)
        write_state(session_id, state)
        print(
            f"[v4.1] user-extract-worker spawned (pid={proc.pid}, "
            f"pending={len(pending)})",
            file=sys.stderr,
        )
        return True
    except Exception as e:
        _atom_debug_error("V4.1:spawn_user_extract_worker", e)
        return False

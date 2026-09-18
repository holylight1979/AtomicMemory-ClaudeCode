"""
handlers/_shared.py — module-level state + 跨 handler 共用 helper

共用：
- regex 常數（_SUPERSEDES_RE / _V4_TRIGGER_LINE_RE / _MEMORY_MD_AUTO_HEADER）
- lazy import flag（WISDOM_AVAILABLE / DOCDRIFT_AVAILABLE）
- _call_project_hook（subprocess invoke project hook）
- _cleanup_old_states（state 檔 TTL 清理）
- _is_ephemeral_path（路徑過濾）
- _maybe_spawn_user_extract_worker（user extract worker spawn）
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
from typing import Any, Dict, List, Optional, Tuple

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


# ─── AEC HUD 活性判定（post_tool_use 標旗 / stop 再查一次，兩端共用）─────────────


def _hud_alive(port: int, threshold_s: int) -> Tuple[bool, Dict[str, Any]]:
    """GET /api/aec/beat-status → HUD 窗活著？回 (alive, info)。

    活著 = clients ≥ 1（HUD 頁的 SSE 常駐連線在：視窗開著，即使頁面被瀏覽器凍結/節流）
        或 age_s < threshold（心跳新；舊版 Node 無 clients 欄時的退路）。
    心跳是「頁面正在渲染」的證據，Edge --app 視窗被遮住久了會停（瀏覽器休眠/凍結隱藏頁；現場實證窗開著 age 仍上百秒），
    單靠它會把開著的窗判死；連線才是「窗開著」的直接證據。
    info 一律帶實際用的 port/threshold/耗時、查到的 age_s/clients、失敗原因——呼叫端落 guard log
    （可觀測性鐵律：不可達的原因不得吞掉）。不可達 / 舊碼 404 / 逾時 → (False, info)。"""
    import urllib.request
    info: Dict[str, Any] = {"port": port, "threshold_s": threshold_s}
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/aec/beat-status", timeout=0.6
        ) as r:
            data = json.loads(r.read().decode("utf-8"))
        age = int(data.get("age_s", 10 ** 9))
        clients = int(data.get("clients", 0))
        info.update(age_s=age, clients=clients)
        alive = clients >= 1 or age < threshold_s
        info["reason"] = "" if alive else "no_hud_client_and_beat_stale"
    except Exception as e:  # 逾時 / 連線拒絕 / 404 / 非 JSON：全記原因，不分類吞掉
        alive = False
        info["reason"] = f"{type(e).__name__}: {e}"[:200]
    info["elapsed_ms"] = round((time.perf_counter() - t0) * 1000)
    return alive, info


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


# ─── Project delegate hook ───────────────────────────────────────────


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
    age < 600s keep; merged_into → 10min; empty working → 1h; working >30min;
    done synced > 1h; done pending > 4h; anything > 7d.

    empty working 取 1h：idle session（開著沒下 prompt）state 被清後，
    _ensure_state fallback 只能重建最小 index、早前脈絡不可復原——寬限放長。
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
            elif prompt_count == 0 and phase == "working" and age > 3600:
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

    # codex companion 旁路檔（companion-state/assessment/metrics-*.json）原無
    # 自帶清理，易累積。>7d 一律清（與上方 state 檔 catch-all 同標準；活躍 session <7d 不動）。
    for f in WORKFLOW_DIR.glob("companion-*.json"):
        try:
            if now - f.stat().st_mtime > 7 * 86400:
                f.unlink(missing_ok=True)
        except OSError:
            pass

    # 跨 session 協調旁路檔：warn-cache（含殘留 .tmp）同 7d 標準；observation log 30d
    for f in WORKFLOW_DIR.glob("coord-warn-cache-*.tmp"):
        try:
            if now - f.stat().st_mtime > 7 * 86400:
                f.unlink(missing_ok=True)
        except OSError:
            pass
    for f in WORKFLOW_DIR.glob("coord-warn-cache-*.json"):
        try:
            if now - f.stat().st_mtime > 7 * 86400:
                f.unlink(missing_ok=True)
        except OSError:
            pass
    for f in (WORKFLOW_DIR.parent / "Logs" / "session-coordination").glob("*.jsonl*"):
        try:
            if now - f.stat().st_mtime > 30 * 86400:
                f.unlink(missing_ok=True)
        except OSError:
            pass


# ─── User Extract Worker Spawning ──────────────────────────────────────


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
            f"user-extract-worker spawned (pid={proc.pid}, "
            f"pending={len(pending)})",
            file=sys.stderr,
        )
        return True
    except Exception as e:
        _atom_debug_error("spawn_user_extract_worker", e)
        return False

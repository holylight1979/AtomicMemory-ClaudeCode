"""
wg_hot_cache.py — Hot Cache 讀寫模組 (V3)

供 quick-extract.py（寫）和 workflow-guardian.py（讀）使用。
Schema: session_id, timestamp, source, injected, knowledge[], summary, token_estimate
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

# ─── paths ──────────────────────────────────────────────────────────────────────

_HOOKS_DIR = str(Path(__file__).resolve().parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

from wg_paths import WORKFLOW_DIR

HOT_CACHE_PATH = WORKFLOW_DIR / "hot_cache.json"

# ─── file lock helpers (best-effort, same pattern as wg_core.write_state) ──────


def _acquire_lock(lock_path: Path):
    """Acquire advisory lock. Returns (lock_fh, msvcrt_module) or (None, None)."""
    if sys.platform == "win32":
        try:
            import msvcrt
            fh = open(lock_path, "ab")
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            return fh, msvcrt
        except OSError:
            try:
                fh.close()
            except Exception:
                pass
            return None, None
    else:
        try:
            import fcntl
            fh = open(lock_path, "ab")
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fh, fcntl
        except OSError:
            try:
                fh.close()
            except Exception:
                pass
            return None, None


def _release_lock(lock_fh, lock_module, lock_path: Path):
    """Release advisory lock and clean up."""
    if lock_fh is None:
        return
    try:
        if sys.platform == "win32":
            lock_module.locking(lock_fh.fileno(), lock_module.LK_UNLCK, 1)
        else:
            lock_module.flock(lock_fh.fileno(), lock_module.LOCK_UN)
    except OSError:
        pass
    lock_fh.close()
    try:
        lock_path.unlink()
    except OSError:
        pass


# ─── public API ─────────────────────────────────────────────────────────────────

LOCK_PATH = HOT_CACHE_PATH.with_suffix(".lock")


def write_hot_cache(data: dict) -> None:
    """Atomic write hot cache with advisory lock."""
    WORKFLOW_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = HOT_CACHE_PATH.with_suffix(".tmp")
    lock_fh, lock_mod = _acquire_lock(LOCK_PATH)
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(str(tmp_path), str(HOT_CACHE_PATH))
    except OSError:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
    finally:
        _release_lock(lock_fh, lock_mod, LOCK_PATH)


def read_hot_cache(session_id: str) -> Optional[dict]:
    """Read hot cache. Returns None if missing, wrong session, or already injected."""
    if not HOT_CACHE_PATH.exists():
        return None
    lock_fh, lock_mod = _acquire_lock(LOCK_PATH)
    try:
        with open(HOT_CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    finally:
        _release_lock(lock_fh, lock_mod, LOCK_PATH)

    if data.get("session_id") != session_id:
        return None
    if data.get("injected", True):
        return None
    return data


def format_injection_line(data: dict, context: str = "") -> str:
    """Format hot cache for UserPromptSubmit/PostToolUse injection.

    Auto-extracted content is DRAFT — prefix with ⚠ tag so Claude treats it as
    unverified hypothesis, not fact. Claude must never promote these to [固] or
    cite them as established knowledge without re-verification.

    context: optional suffix appended to source tag (e.g. "mid-turn").
    """
    source = data.get("source", "?")
    summary = data.get("summary", "")
    tag = f"[HotCache:{source}"
    if context:
        tag += f"·{context}"
    tag += " ⚠AUTO-DRAFT·[臨]]"
    rule = " | 規則：auto-extract 僅供參考，未經 4+ session 驗證，禁止引用為事實、禁止以 [固]/[觀] 存入"
    return f"{tag} {summary}{rule}"


def mark_injected(session_id: str) -> bool:
    """Atomically mark hot cache as injected. Returns True on success."""
    lock_fh, lock_mod = _acquire_lock(LOCK_PATH)
    try:
        if not HOT_CACHE_PATH.exists():
            return False
        with open(HOT_CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("session_id") != session_id:
            return False
        if data.get("injected", True):
            return False
        data["injected"] = True
        tmp_path = HOT_CACHE_PATH.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(str(tmp_path), str(HOT_CACHE_PATH))
        return True
    except (OSError, json.JSONDecodeError):
        return False
    finally:
        _release_lock(lock_fh, lock_mod, LOCK_PATH)

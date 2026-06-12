"""
wg_extraction.py — Per-turn 萃取管線 / Worker / Failure / User Signal /
                   Hot Cache / Plan classify / Atom injection log（V5）

統合：
- Transcript 讀取、per-turn 增量萃取、failure keyword 偵測、worker spawn（原 wg_extraction）
- L0 User Decision Detector（前 wg_user_extract.detect_signal）
- Hot Cache 讀寫（前 wg_hot_cache）
- 內容分類 plan vs knowledge（前 wg_content_classify）
- log_injection（前 wg_atom_observation — flag-gated 觀察日誌）
"""

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from wg_core import (
    CLAUDE_DIR, WORKFLOW_DIR,
    cwd_to_project_slug, get_transcript_path,
    _now_iso, _atom_debug_log, _atom_debug_error,
    write_state,
)
from wg_atoms import _kw_match


# ─── Process Utilities ───────────────────────────────────────────────────────


def _is_pid_alive(pid: int) -> bool:
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

_DEFAULT_LEASE_TTL = 300


def _is_lease_valid(state: dict, key: str) -> bool:
    """Check if a worker lease is still valid (not expired AND PID alive)."""
    lease = state.get(key)
    if not lease:
        return False
    if isinstance(lease, int):
        return _is_pid_alive(lease)
    pid = lease.get("pid", 0)
    expires_at = lease.get("expires_at", 0)
    if time.time() > expires_at:
        return False
    return _is_pid_alive(pid)


def _set_lease(state: dict, key: str, pid: int, ttl: int = _DEFAULT_LEASE_TTL) -> None:
    state[key] = {"pid": pid, "expires_at": time.time() + ttl}


# ─── Transcript Helpers ──────────────────────────────────────────────────────


def _find_transcript(session_id: str, cwd: str):
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
    except (OSError, UnicodeDecodeError) as e:
        _atom_debug_error("extraction:count_assistant_chars", e)
        pass
    return total


# ─── Worker Spawning ─────────────────────────────────────────────────────────


def _gui_python() -> str:
    """回傳 GUI-subsystem pythonw（無 console 視窗）；找不到退回 sys.executable。

    坑：hermes venv 的 pythonw 是 **console-subsystem**（uv venv trampoline 會 re-exec
    成 base python.exe），spawn 出來會閃黑窗；且 `CREATE_NO_WINDOW | DETACHED_PROCESS`
    組合在 console 子行程上不保證壓窗。故改用穩定的 uv default-shim GUI pythonw
    （`AppData\\Local\\Python\\bin\\pythonw.exe`，路徑無版本號→ uv 升級不破）。
    與 settings.json hook interpreter 同源；見 atom
    windows-cc-hook-閃-console-pythonw-修-layer-1勿只補巢狀-creationflags。"""
    if sys.platform == "win32":
        cand = Path.home() / "AppData" / "Local" / "Python" / "bin" / "pythonw.exe"
        if cand.exists():
            return str(cand)
    return sys.executable


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
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            json_ctx = json.dumps(ctx_dict, ensure_ascii=False)
            proc = _sp.Popen(
                [_gui_python(), str(worker_path)],
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

    last_at = state.get("last_per_turn_extraction_at", "")
    if last_at:
        cooldown = pt.get("cooldown_seconds", 120)
        try:
            last_t = datetime.fromisoformat(last_at)
            if (datetime.now().astimezone() - last_t).total_seconds() < cooldown:
                return
        except (ValueError, TypeError):
            pass

    if _is_lease_valid(state, "extract_worker_pid"):
        return

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

    tracker = state.get("topic_tracker", {})
    dist = tracker.get("intent_distribution", {})
    intent = max(dist, key=dist.get, default="build") if dist else "build"

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


# ─── L0 User Decision Detector (was wg_user_extract.detect_signal) ──────────

_STRONG: List[Tuple[str, float]] = [
    ("記住", 1.0), ("永遠", 1.0), ("從此", 1.0), ("以後都要", 1.0),
    ("禁止", 1.0), ("一律", 1.0), ("統一", 1.0), ("決定", 1.0),
    ("規定", 1.0), ("約定", 1.0),
    ("remember", 1.0), ("always", 1.0), ("never", 1.0),
    ("from now on", 1.0), ("must", 1.0),
]
_MEDIUM: List[Tuple[str, float]] = [
    ("改用", 0.6), ("不要再", 0.6), ("下次", 0.6), ("固定", 0.6),
    ("偏好", 0.6), ("我要", 0.6), ("我不要", 0.6),
    ("prefer", 0.6), ("switch to", 0.6), ("stop using", 0.6),
]
_NEGATIVE: List[Tuple[str, float]] = [
    ("也許", -0.8), ("可能", -0.8), ("試試", -0.8), ("好不好", -0.8),
    ("maybe", -0.8), ("perhaps", -0.8), ("might", -0.8),
]
_ALL_KEYWORDS: List[Tuple[str, float]] = _STRONG + _MEDIUM + _NEGATIVE

_SYNTAX_MODAL = re.compile(
    r"[我我們](?:以後|之後|未來)?"
    r"(?:要|會|得|該|必須|應該|都要|一定要|不要|不再|別再)"
    r".{2,30}",
)
_SYNTAX_UNIFORM = re.compile(
    r"(?:都|一律|固定|統一|全部)"
    r"(?:用|改|換|採用|寫|設|跑|走|使用|改成)"
    r".{1,30}",
)
_SYNTAX_NEGATE = re.compile(
    r"(?:不要|不準|不可以|禁止|別|勿|停止|不用|不再)"
    r"(?:用|寫|加|改|跑|裝|使用|建立|產生)"
    r".{1,30}",
)
_SYNTAX_PATTERNS: List[Tuple[re.Pattern, str, float]] = [
    (_SYNTAX_MODAL, "syntax:modal", 0.5),
    (_SYNTAX_UNIFORM, "syntax:uniform", 0.5),
    (_SYNTAX_NEGATE, "syntax:negate", 0.5),
]

_QUESTION_END = re.compile(r"[?？]$|嗎\s*$|呢\s*$")
_CODE_FENCE = re.compile(r"^```", re.MULTILINE)
_CODE_INDENT = re.compile(r"^    \S", re.MULTILINE)


def _is_mostly_code(text: str) -> bool:
    lines = text.split("\n")
    if not lines:
        return False
    fence_count = len(_CODE_FENCE.findall(text))
    if fence_count >= 2:
        in_fence = False
        code_lines = 0
        for line in lines:
            if _CODE_FENCE.match(line):
                in_fence = not in_fence
                code_lines += 1
            elif in_fence:
                code_lines += 1
        if code_lines / len(lines) > 0.8:
            return True
    indent_lines = len(_CODE_INDENT.findall(text))
    if indent_lines / len(lines) > 0.8:
        return True
    return False


def _should_skip(prompt: str) -> bool:
    stripped = prompt.strip()
    if len(stripped) < 8 or len(stripped) > 500:
        return True
    if _QUESTION_END.search(stripped):
        return True
    if _is_mostly_code(stripped):
        return True
    return False


_SIGNAL_THRESHOLD = 0.4


def detect_signal(prompt: str) -> Dict:
    """Detect user decision/preference signals in prompt text.

    Returns {"signal": bool, "score": float, "matched": ["keyword1", "pattern2"]}
    """
    if _should_skip(prompt):
        return {"signal": False, "score": 0.0, "matched": []}

    prompt_lower = prompt.lower()
    score = 0.0
    matched: List[str] = []

    for keyword, weight in _ALL_KEYWORDS:
        if keyword in prompt_lower:
            score += weight
            matched.append(keyword)

    for pattern, name, weight in _SYNTAX_PATTERNS:
        if pattern.search(prompt):
            score += weight
            matched.append(name)

    signal = score >= _SIGNAL_THRESHOLD
    return {"signal": signal, "score": round(score, 2), "matched": matched}


# ─── Hot Cache (was wg_hot_cache) ───────────────────────────────────────────

HOT_CACHE_PATH = WORKFLOW_DIR / "hot_cache.json"
LOCK_PATH = HOT_CACHE_PATH.with_suffix(".lock")


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


def write_hot_cache(data: dict) -> None:
    """Atomic write hot cache with advisory lock."""
    WORKFLOW_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = HOT_CACHE_PATH.with_suffix(".tmp")
    lock_fh, lock_mod = _acquire_lock(LOCK_PATH)
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(str(tmp_path), str(HOT_CACHE_PATH))
    except OSError as e:
        _atom_debug_error("extraction:hot_cache_write", e)
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
    except (OSError, json.JSONDecodeError) as e:
        _atom_debug_error("extraction:hot_cache_read", e)
        return None
    finally:
        _release_lock(lock_fh, lock_mod, LOCK_PATH)

    if data.get("session_id") != session_id:
        return None
    if data.get("injected", True):
        return None
    return data


def format_injection_line(data: dict, context: str = "") -> str:
    """Format hot cache for UPS/PostToolUse injection. AUTO-DRAFT tag enforced."""
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
    except (OSError, json.JSONDecodeError) as e:
        _atom_debug_error("extraction:hot_cache_mark_injected", e)
        return False
    finally:
        _release_lock(lock_fh, lock_mod, LOCK_PATH)


# ─── Content Classify: plan vs knowledge (was wg_content_classify) ──────────

PLAN_CONTENT_RE = re.compile(
    r"(?i)"
    r"(plan|todo|roadmap|draft|wip|scratch|調查|規劃|暫存)"
    r"|phase[- _]?\d"
    r"|設計方案|待辦|草稿|下一步|next[- _]?step|action[- _]?item"
)

PLAN_FACT_RE = re.compile(
    r"(?i)"
    r"(預計|計畫|規劃|打算|下一步|將要|準備|TODO|TBD|待確認|待實作|待處理)"
    r"|(Phase\s*\d+\s*.{0,5}(預計|計畫|目標|排程))"
    r"|(下個\s*(session|階段|sprint))"
    r"|(尚未|還沒|未來|之後再)"
)


def is_plan_filename(filename: str) -> bool:
    return bool(PLAN_CONTENT_RE.search(filename))


def is_plan_content(text: str) -> bool:
    if not text or len(text) < 10:
        return False
    return bool(PLAN_FACT_RE.search(text))


def classify_extracted_item(item: dict) -> str:
    content = item.get("content", "")
    if is_plan_content(content):
        return "plan"
    return "knowledge"


# ─── Atom Injection Observation Log (was wg_atom_observation.log_injection) ──

_FLAG_PATH = CLAUDE_DIR / "memory" / "_staging" / "reg-005-observation-start.flag"
_OBS_LOG_DIR = CLAUDE_DIR / "Logs"


def _obs_flag_active() -> bool:
    try:
        return _FLAG_PATH.exists()
    except OSError:
        return False


def log_injection(
    session_id: str,
    name: str,
    classification: str,
    source: str,
) -> None:
    """Append injection record to atom-injection-injections-YYYY-MM-DD.log.

    Flag-gated（讀 reg-005-observation-start.flag）。flag 不存在 → 立即 return。
    fail-open — 任何 OSError / encode error 不 raise，沉默吞掉。
    """
    if not _obs_flag_active():
        return
    try:
        rec = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "session_id": session_id,
            "name": name,
            "classification": classification,
            "source": source,
            "event": "atom_injected",
        }
        _OBS_LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = _OBS_LOG_DIR / f"atom-injection-injections-{datetime.now().strftime('%Y-%m-%d')}.log"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except (OSError, TypeError, ValueError):
        pass

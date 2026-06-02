"""
wg_core.py — Workflow Guardian 共用基礎模組（V5）

統合：
- 常數 / 設定載入 / State I/O / Output helpers / Debug logging
- 路徑集中管理（前 wg_paths）
- PreToolUse 路徑/指令防呆（前 wg_pretool_guards）
- MCP server 健檢（前 wg_intent._check_mcp_servers）
- Log rotation（V5 P0）
- Promotion audit log
"""

import json
import math
import os
import re
import shutil
import socket
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ─── 全域路徑常數 ────────────────────────────────────────────────────────────

CLAUDE_DIR = Path.home() / ".claude"
MEMORY_DIR = CLAUDE_DIR / "memory"
EPISODIC_DIR = MEMORY_DIR / "episodic"
WORKFLOW_DIR = CLAUDE_DIR / "workflow"
CONFIG_PATH = WORKFLOW_DIR / "config.json"
MEMORY_INDEX = "MEMORY.md"
ATOM_INDEX = "_ATOM_INDEX.md"
REGISTRY_PATH = MEMORY_DIR / "project-registry.json"

# atom 物理位置 / 白名單規則來源（單一來源 lib.atom_locations）
sys.path.insert(0, str(CLAUDE_DIR / "lib"))
try:
    from atom_locations import atom_writable_dir_segments, failures_atom_stems
except ImportError:
    atom_writable_dir_segments = None
    failures_atom_stems = None

CONTEXT_BUDGET_DEFAULT = 3000

# Defaults（可被 config.json 覆寫）
DEFAULTS = {
    "enabled": True,
    "stop_gate_max_blocks": 2,
    "min_files_to_block": 2,
    "remind_after_turns": 3,
    "max_reminders": 3,
    "stale_threshold_hours": 24,
    "sync_keywords": ["同步", "sync", "commit", "提交", "結束", "收工"],
    "completion_indicators": ["已同步", "同步完成", "已更新", "已提交", "committed"],
    "session_context": {
        "enabled": True,
        "max_episodic": 3,
        "reserved_tokens": 200,
        "min_score": 0.35,
        "search_timeout_ms": 1500,
    },
    "aidocs": {
        "enabled": True,
        "max_session_start_entries": 15,
        "max_prompt_matches": 3,
    },
    "sync_reminder": {
        "enabled": True,
        "max_reminders": 1,
    },
    "docdrift": {
        "enabled": True,
        "path_mappings": {},
        "exclude_patterns": [
            "_aidocs/", "memory/", "_staging/", ".git/",
            "node_modules/", "__pycache__/", ".claude/workflow/",
        ],
        "keyword_match_threshold": 2,
        "max_pending_display": 5,
    },
    "proactive": {
        "pattern_threshold": 2,
        "migration_hint_threshold": 3,
    },
}


# ─── Config 載入 ─────────────────────────────────────────────────────────────


def load_config() -> Dict[str, Any]:
    """Load config with defaults fallback."""
    config = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                user_config = json.load(f)
            config.update(user_config)
        except (json.JSONDecodeError, OSError):
            pass
    return config


# ─── Utility ─────────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _estimate_tokens(text: str) -> int:
    """CJK-aware token estimation. Chinese ~1.5 tok/char, ASCII ~0.25 tok/word."""
    if not text:
        return 0
    cjk = sum(1 for c in text if '一' <= c <= '鿿' or '　' <= c <= '〿')
    ascii_part = len(text) - cjk
    return int(cjk * 1.5 + ascii_part * 0.25)


def rotate_log_if_oversized(log_path: Path, max_mb: int = 10, keep: int = 3) -> bool:
    """V5 P0: size-based log rotation. Fail-open.

    Rotates `log_path` to `log_path.1` (.1->.2, .2->.3) when > max_mb.
    Keeps last `keep` rotated copies. Returns True if rotated.
    Handles Windows-locked / corrupt files gracefully (returns False).
    """
    try:
        if not log_path.exists():
            return False
        size_mb = log_path.stat().st_size / (1024 * 1024)
        if size_mb < max_mb:
            return False
        for i in range(keep - 1, 0, -1):
            src = log_path.with_suffix(log_path.suffix + f".{i}")
            dst = log_path.with_suffix(log_path.suffix + f".{i+1}")
            if src.exists():
                try:
                    if dst.exists():
                        dst.unlink()
                    src.rename(dst)
                except OSError:
                    pass
        rotated = log_path.with_suffix(log_path.suffix + ".1")
        try:
            if rotated.exists():
                rotated.unlink()
            log_path.rename(rotated)
            log_path.touch()
            return True
        except OSError:
            return False
    except Exception:
        return False


# ─── Path Helpers (was wg_paths.py) ──────────────────────────────────────────


def cwd_to_project_slug(cwd: str) -> str:
    """Convert CWD to Claude Code project slug. All-lowercase to avoid C: vs c: slug split."""
    slug = cwd.replace(":", "-").replace("\\", "-").replace("/", "-").replace(".", "-")
    return slug.lower()


def find_project_root(cwd: str) -> Optional[Path]:
    """Walk up from CWD to find project root via .claude/memory/MEMORY.md / _AIDocs / .git / .svn."""
    if not cwd:
        return None
    p = Path(cwd)
    for _ in range(4):
        if (p / ".claude" / "memory" / MEMORY_INDEX).exists():
            return p
        if (p / "_AIDocs").is_dir():
            return p
        if (p / ".git").exists() or (p / ".svn").exists():
            return p
        parent = p.parent
        if parent == p:
            break
        p = parent
    return Path(cwd)


def get_project_memory_dir(cwd: str) -> Optional[Path]:
    """Get project-level memory dir. New path ({project_root}/.claude/memory/) preferred."""
    if not cwd:
        return None
    root = find_project_root(cwd)
    if root:
        try:
            if root.resolve() == CLAUDE_DIR.resolve():
                return MEMORY_DIR
        except OSError:
            pass
        new_mem = root / ".claude" / "memory"
        if new_mem.is_dir():
            if (new_mem / MEMORY_INDEX).exists():
                return new_mem
            if any((new_mem / d).is_dir() for d in ("shared", "roles", "personal")):
                return new_mem
    slug = cwd_to_project_slug(cwd)
    old_mem = CLAUDE_DIR / "projects" / slug / "memory"
    if old_mem.exists():
        return old_mem
    return None


def get_scope_dir(
    scope: str,
    cwd: str,
    user: Optional[str] = None,
    role: Optional[str] = None,
) -> Optional[Path]:
    """V4: 回傳指定 scope 的目錄，必要時自動建立。"""
    if scope == "global":
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        return MEMORY_DIR

    if scope == "role" and not role:
        return None
    if scope == "personal" and not user:
        return None
    if scope not in ("shared", "role", "personal"):
        return None

    root = find_project_root(cwd)
    if not root:
        return None
    try:
        if root.resolve() == CLAUDE_DIR.resolve():
            return None
    except OSError:
        pass
    has_marker = (
        (root / ".claude" / "memory" / MEMORY_INDEX).exists()
        or (root / "_AIDocs").is_dir()
        or (root / ".git").exists()
        or (root / ".svn").exists()
    )
    if not has_marker:
        return None

    base = root / ".claude" / "memory"
    if scope == "shared":
        target = base / "shared"
    elif scope == "role":
        target = base / "roles" / role
    else:
        target = base / "personal" / user
    target.mkdir(parents=True, exist_ok=True)
    return target


def get_project_claude_dir(cwd: str) -> Optional[Path]:
    root = find_project_root(cwd)
    if root:
        d = root / ".claude"
        if d.is_dir() and (d / "memory" / MEMORY_INDEX).exists():
            return d
    return None


def get_transcript_path(session_id: str, cwd: str) -> Optional[Path]:
    """Locate session transcript JSONL. Claude Code-managed path."""
    if not session_id or not cwd:
        return None
    slug = cwd_to_project_slug(cwd)
    candidate = CLAUDE_DIR / "projects" / slug / f"{session_id}.jsonl"
    return candidate if candidate.exists() else None


def resolve_episodic_dir(cwd: str) -> Tuple[Path, str]:
    mem = get_project_memory_dir(cwd)
    if mem:
        return mem / "episodic", f"project:{cwd_to_project_slug(cwd)}"
    return EPISODIC_DIR, "global"


def resolve_failures_dir(cwd: str) -> Path:
    mem = get_project_memory_dir(cwd)
    if mem:
        d = mem / "failures"
        d.mkdir(exist_ok=True)
        return d
    return MEMORY_DIR / "failures"


def resolve_staging_dir(cwd: str) -> Path:
    mem = get_project_memory_dir(cwd)
    if mem:
        d = mem / "_staging"
        d.mkdir(exist_ok=True)
        return d
    return MEMORY_DIR / "_staging"


def resolve_access_json(atom_name: str, atom_path: Path) -> Path:
    return atom_path.parent / f"{atom_name}.access.json"


# ─── Project Registry ────────────────────────────────────────────────────────


def _today() -> str:
    return date.today().isoformat()


def _load_registry() -> Dict[str, Any]:
    if REGISTRY_PATH.exists():
        try:
            return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"projects": {}}


def _save_registry(reg: Dict[str, Any]) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRY_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(REGISTRY_PATH)


def register_project(cwd: str) -> None:
    root = find_project_root(cwd)
    if not root:
        return
    has_marker = (
        (root / ".claude" / "memory" / MEMORY_INDEX).exists()
        or (root / "_AIDocs").is_dir()
        or (root / ".git").exists()
        or (root / ".svn").exists()
    )
    if not has_marker:
        return
    slug = cwd_to_project_slug(str(root))
    reg = _load_registry()
    entry = reg.setdefault("projects", {}).setdefault(slug, {})
    entry["root"] = str(root)
    entry["last_seen"] = _today()
    _save_registry(reg)


def get_slug_pointer_path(cwd: str) -> Path:
    slug = cwd_to_project_slug(cwd)
    return CLAUDE_DIR / "projects" / slug / "memory" / MEMORY_INDEX


def discover_all_project_memory_dirs() -> List[Tuple[str, Path]]:
    """Discover all project memory directories. Registry-first + old-path fallback."""
    seen_slugs: set = set()
    results: List[Tuple[str, Path]] = []
    reg = _load_registry()
    for slug, info in reg.get("projects", {}).items():
        root = Path(info.get("root", ""))
        if not root.is_dir():
            continue
        new_mem = root / ".claude" / "memory"
        if new_mem.is_dir() and (new_mem / MEMORY_INDEX).exists():
            results.append((slug, new_mem))
            seen_slugs.add(slug)
            continue
        old_mem = CLAUDE_DIR / "projects" / slug / "memory"
        if old_mem.is_dir():
            results.append((slug, old_mem))
            seen_slugs.add(slug)
    projects_dir = CLAUDE_DIR / "projects"
    if projects_dir.is_dir():
        for proj_dir in sorted(projects_dir.iterdir()):
            if not proj_dir.is_dir():
                continue
            slug = proj_dir.name
            if slug in seen_slugs:
                continue
            mem = proj_dir / "memory"
            # Phase 0: 要求 atom 索引 marker（MEMORY.md / _atom_index.json）才納入，
            # 避免 CC 原生 auto-memory dir（projects/<proj>/memory/）污染 cross-project 掃描。
            if mem.is_dir() and (
                (mem / MEMORY_INDEX).exists() or (mem / "_atom_index.json").exists()
            ):
                results.append((slug, mem))
    return results


def discover_v4_sublayers(slug: str, mem_dir: Path) -> List[Tuple[str, Path, str]]:
    """V4: enumerate sub scope layers under a project memory dir."""
    out: List[Tuple[str, Path, str]] = []
    shared_label = f"shared:{slug}"

    def _is_legacy_atom(p: Path) -> bool:
        if not (p.is_file() and p.suffix == ".md"):
            return False
        if p.name in (MEMORY_INDEX, ATOM_INDEX):
            return False
        if p.name.startswith("_") or p.name.startswith("SPEC_"):
            return False
        return True
    has_flat_legacy = any(_is_legacy_atom(p) for p in mem_dir.iterdir()) if mem_dir.is_dir() else False
    if has_flat_legacy:
        out.append((shared_label, mem_dir, "flat-legacy"))

    shared_dir = mem_dir / "shared"
    if shared_dir.is_dir():
        out.append((shared_label, shared_dir, "recursive"))

    roles_root = mem_dir / "roles"
    if roles_root.is_dir():
        for rd in sorted(roles_root.iterdir()):
            if rd.is_dir() and not rd.name.startswith("_"):
                out.append((f"role:{slug}:{rd.name}", rd, "recursive"))

    personal_root = mem_dir / "personal"
    if personal_root.is_dir():
        for pd in sorted(personal_root.iterdir()):
            if pd.is_dir() and not pd.name.startswith("_"):
                out.append((f"personal:{slug}:{pd.name}", pd, "recursive"))

    return out


def discover_memory_layers(
    layer_filter: Optional[str] = None,
    user: Optional[str] = None,
    role: Optional[str] = None,
) -> List[Tuple[str, Path]]:
    """Discover memory layers with optional role filter (SPEC §8.1)."""
    layers: List[Tuple[str, Path]] = []

    def _accept(label: str) -> bool:
        if not layer_filter or layer_filter == "all":
            return True
        if layer_filter == label:
            return True
        if layer_filter == "global":
            return label == "global"
        if layer_filter == "shared":
            return label.startswith("shared:")
        if layer_filter == "role":
            return label.startswith("role:")
        if layer_filter.startswith("role:") and ":" not in layer_filter[5:]:
            r = layer_filter.split(":", 1)[1]
            return label.startswith("role:") and label.endswith(f":{r}")
        if layer_filter == "personal":
            return label.startswith("personal:")
        if layer_filter.startswith("personal:") and ":" not in layer_filter[9:]:
            u = layer_filter.split(":", 1)[1]
            return label.startswith("personal:") and label.endswith(f":{u}")
        return False

    if _accept("global"):
        layers.append(("global", MEMORY_DIR))

    role_set = set()
    if role:
        role_set = {r.strip() for r in role.split(",") if r.strip()}

    user_aware = bool(user or role)

    for slug, mem_dir in discover_all_project_memory_dirs():
        for label, path, _kind in discover_v4_sublayers(slug, mem_dir):
            if user_aware:
                if label.startswith("shared:"):
                    pass
                elif label.startswith("role:"):
                    r = label.rsplit(":", 1)[1]
                    if r not in role_set:
                        continue
                elif label.startswith("personal:"):
                    u = label.rsplit(":", 1)[1]
                    if u != user:
                        continue
            if not _accept(label):
                continue
            layers.append((label, path))

    return layers


def state_file_path(session_id: str) -> Path:
    return WORKFLOW_DIR / f"state-{session_id}.json"


# ─── State File I/O ──────────────────────────────────────────────────────────


def state_path(session_id: str) -> Path:
    """Alias kept for backward compat with callers."""
    return state_file_path(session_id)


def read_state(session_id: str) -> Optional[Dict[str, Any]]:
    path = state_path(session_id)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def write_state(session_id: str, state: Dict[str, Any]) -> None:
    """Atomic write with advisory lock to prevent concurrent R-M-W races."""
    WORKFLOW_DIR.mkdir(parents=True, exist_ok=True)

    canonical_id = state.get("session", {}).get("id")
    if canonical_id and canonical_id != session_id:
        session_id = canonical_id

    state["last_updated"] = _now_iso()
    path = state_path(session_id)
    tmp_path = path.with_suffix(".tmp")
    lock_path = path.with_suffix(".lock")

    lock_fh = None
    if sys.platform == "win32":
        try:
            import msvcrt
            lock_fh = open(lock_path, "ab")
            msvcrt.locking(lock_fh.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            if lock_fh:
                lock_fh.close()
            lock_fh = None

    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        tmp_path.replace(path)
    except OSError:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
    finally:
        if lock_fh is not None:
            try:
                import msvcrt
                msvcrt.locking(lock_fh.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
            lock_fh.close()
            try:
                lock_path.unlink()
            except OSError:
                pass


def new_state(session_id: str, cwd: str, source: str) -> Dict[str, Any]:
    return {
        "schema_version": "1.1",
        "session": {
            "id": session_id,
            "started_at": _now_iso(),
            "cwd": cwd,
            "source": source,
        },
        "phase": "init",
        "modified_files": [],
        "accessed_files": [],
        "vcs_queries": [],
        "knowledge_queue": [],
        "sync_pending": False,
        "stop_blocked_count": 0,
        "remind_count": 0,
        "topic_tracker": {
            "intent_distribution": {},
            "prompt_count": 0,
            "first_prompt_summary": "",
            "keyword_signals": [],
            "related_episodic": [],
        },
        "session_context_injected": False,
        "last_updated": _now_iso(),
    }


def _find_active_sibling_state(
    cwd: str, current_session_id: str, window_seconds: int = 60
) -> Optional[Dict[str, Any]]:
    """SessionStart 去重：同 cwd + 近期活躍的兄弟 state。"""
    try:
        norm_cwd = cwd.lower().replace("\\", "/")
        best: Optional[Dict[str, Any]] = None
        best_mtime: float = 0.0
        now = datetime.now(timezone.utc).astimezone()

        for fp in WORKFLOW_DIR.glob("state-*.json"):
            if current_session_id in fp.name:
                continue
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    candidate = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

            candidate_cwd = candidate.get("session", {}).get("cwd", "")
            if candidate_cwd.lower().replace("\\", "/") != norm_cwd:
                continue

            if candidate.get("phase") != "working":
                continue
            if candidate.get("merged_into"):
                continue

            started_at_str = candidate.get("session", {}).get("started_at", "")
            if not started_at_str:
                continue
            try:
                started_at = datetime.fromisoformat(started_at_str)
                delta = (now - started_at).total_seconds()
                if delta < 0 or delta > window_seconds:
                    continue
            except (ValueError, TypeError):
                continue

            mtime = fp.stat().st_mtime
            if mtime > best_mtime:
                best = candidate
                best_mtime = mtime

        return best
    except Exception:
        return None


def _ensure_state(
    session_id: str, input_data: Dict[str, Any], config: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Read state; if missing (SessionStart was skipped), auto-create one."""
    state = read_state(session_id)
    if state:
        merged_into = state.get("merged_into")
        if merged_into:
            target = read_state(merged_into)
            if target:
                return target
            state.pop("merged_into", None)
            state["phase"] = "working"
            write_state(session_id, state)
            _atom_debug_log(
                "MergeSelfHeal",
                f"{session_id[:12]}… merged_into={merged_into[:12]}… target missing "
                f"→ self-heal to active",
                config,
            )
        return state

    cwd = input_data.get("cwd", "")

    sibling = _find_active_sibling_state(cwd, session_id, window_seconds=86400)
    if sibling:
        real_id = sibling.get("session", {}).get("id", "")
        _atom_debug_log(
            "Fallback→Sibling",
            f"{session_id[:12]}… → existing {real_id[:12] if real_id else '?'}…",
            config,
        )
        return sibling

    state = new_state(session_id, cwd, "fallback")
    state["phase"] = "working"
    write_state(session_id, state)
    _atom_debug_log(
        "Fallback",
        f"SessionStart missed for {session_id[:12]}… — auto-created state",
        config,
    )
    return state


# ─── Output Helpers ──────────────────────────────────────────────────────────


def output_json(data: Dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False))
    sys.exit(0)


def output_nothing() -> None:
    sys.exit(0)


def output_block(reason: str) -> None:
    output_json({"decision": "block", "reason": reason})


# ─── Promotion Audit Log ─────────────────────────────────────────────────────


def log_promotion_audit(action: str, atom: str, **fields: Any) -> None:
    """Append one JSONL entry to memory/_promotion_audit.jsonl."""
    try:
        entry = {"ts": datetime.now().isoformat(timespec="seconds"),
                 "action": action, "atom": atom}
        entry.update(fields)
        audit_path = MEMORY_DIR / "_promotion_audit.jsonl"
        with open(audit_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ─── Atom Debug Log ──────────────────────────────────────────────────────────


def _atom_debug_log(tag: str, content: str, config: Dict[str, Any] = None) -> None:
    """Write to atom-debug.log when atom_debug flag is on. ERROR always writes."""
    if tag != "ERROR" and not (config or {}).get("atom_debug", False):
        return
    if not content or not content.strip():
        return
    try:
        log_dir = Path.home() / ".claude" / "Logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"atom-debug-{datetime.now().strftime('%Y-%m-%d_%H')}.log"
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}][{tag}] {content.strip()}\n\n")
    except Exception:
        pass


def _atom_debug_error(source: str, exc: Exception) -> None:
    """Log error with source context. Network errors get one-line summary."""
    if isinstance(exc, (TimeoutError, OSError, ConnectionError)):
        msg = f"{type(exc).__name__}: {exc}"
    else:
        import traceback
        msg = traceback.format_exc()
        if "NoneType" in msg:
            msg = f"{type(exc).__name__}: {exc}"
    _atom_debug_log("ERROR", f"[{source}] {msg}", {"atom_debug": True})


# ─── PreToolUse Path / Command Guards (was wg_pretool_guards.py) ─────────────

_PROJECT_MEMORY_PATH_RE = re.compile(
    r"[/\\]\.claude[/\\]projects[/\\](?!_)[^/\\]+[/\\]memory[/\\]",
    re.IGNORECASE,
)
_NESTED_PROJECTS_RE = re.compile(
    r"[/\\]\.claude[/\\]projects[/\\][^/\\]+[/\\]projects[/\\][^/\\]+[/\\]memory[/\\]",
    re.IGNORECASE,
)
_DOUBLE_CLAUDE_RE = re.compile(
    r"[/\\]\.claude[/\\]\.claude[/\\]memory[/\\]",
    re.IGNORECASE,
)
_SVN_COMMIT_RE = re.compile(r"\bsvn\s+(?:ci|commit)\b", re.IGNORECASE)
_TEST_PATH_RE = re.compile(
    r"(?:^|[/\\\s])(?:tests?|__tests__)(?:[/\\\s]|$)"
    r"|[/\\][^/\\\s]*Test\.(?:cs|py|js|ts|tsx|jsx|go|java)\b",
    re.IGNORECASE,
)

_WHITELIST_BASENAMES = frozenset({
    "MEMORY.md", "_ATOM_INDEX.md", "_CHANGELOG.md", "_CHANGELOG_ARCHIVE.md",
    "_roles.md", "hot_cache.json", "atom_io_audit.jsonl",
    "_promotion_audit.jsonl", "project-registry.json", "session_score.json",
    "DESIGN.md", "role.md",
})
if atom_writable_dir_segments is not None:
    _WHITELIST_DIR_SEGMENTS = atom_writable_dir_segments()
else:
    # Fallback（lib import 失敗的極端情況；與 atom_locations 保持一致）。
    # 不含 'Failures'：Failures atom 由 _is_failures_atom_path 主動 gate，非白名單豁免。
    _WHITELIST_DIR_SEGMENTS = frozenset({
        "_meta", "_staging", "_archived", "_distant", "_reference", "_pending_review",
        "_vectordb", "_rejected", "templates", "episodic", "wisdom", "personal",
    })


def _path_under_memory_dir(fp: Path) -> bool:
    parts = [p.lower() for p in fp.parts]
    for i in range(len(parts) - 1):
        if parts[i] == ".claude" and parts[i + 1] == "memory":
            return True
    return False


def _atom_path_whitelisted(fp: Path) -> bool:
    if fp.name in _WHITELIST_BASENAMES:
        return True
    if fp.name.startswith("_") or fp.name.startswith("SPEC_"):
        return True
    parts_lower = {p.lower() for p in fp.parts}
    if parts_lower & _WHITELIST_DIR_SEGMENTS:
        return True
    return False


def _is_failures_atom_path(fp: Path) -> bool:
    """fp 是否為 `_AIDocs/Failures/` 下「已註冊的 atom」(.md)。

    `_AIDocs/Failures/` 不在 `.claude/memory/` 樹下，故上游 _path_under_memory_dir
    對其早 return None —— 這正是 funnel guard 的覆蓋缺口（feedback-* / cognitive-patterns
    / memory-pipeline-* 等失敗 atom 物理居此，直接 Write/Edit 會繞過 funnel + audit）。

    該目錄混居「註冊 atom」與「legacy 失敗筆記」（env-traps / silent-failures /
    wrong-assumptions… 未進 index，屬一般參考文件，不可誤擋），故以 failures_atom_stems()
    （index SoT）精準比對 stem。_INDEX.md（'_' 前綴）與 legacy 文件 stem 不在 index → 自然放行。

    failures_atom_stems 在 lib import 失敗時為 None → 退化為「不攔」，與既有行為一致。
    """
    if failures_atom_stems is None or fp.suffix != ".md":
        return False
    parts_lower = [p.lower() for p in fp.parts]
    for i in range(len(parts_lower) - 1):
        if parts_lower[i] == "_aidocs" and parts_lower[i + 1] == "failures":
            break
    else:
        return False
    try:
        return fp.stem in failures_atom_stems()
    except Exception:
        return False


def check_memory_path_block(
    tool_name: str, tool_input: Dict[str, Any]
) -> Optional[str]:
    """阻擋三類 memory 違規寫入：projects/{slug}/memory（P1）/ 雙層 .claude（P6）/ atom 直 Write（S3.3）。"""
    if tool_name not in ("Write", "Edit"):
        return None
    fp_str = tool_input.get("file_path", "") or ""
    if not fp_str:
        return None

    if _PROJECT_MEMORY_PATH_RE.search(fp_str) or _NESTED_PROJECTS_RE.search(fp_str):
        return (
            "[Guardian:MemoryPathBlock] 禁止寫入 `~/.claude/projects/{slug}/memory/`。"
            "原子記憶專案自治層已覆寫此路徑。\n"
            "正確做法：(1) 全域記憶 → 用 MCP `atom_write` (scope=global) 寫到 "
            "~/.claude/memory/；(2) 專案記憶 → 用 MCP `atom_write` "
            "(scope=shared/role/personal) 寫到 {project_root}/.claude/memory/。\n"
            "詳見 memory/feedback/feedback-memory-structure.md。"
        )

    if _DOUBLE_CLAUDE_RE.search(fp_str):
        return (
            "[Guardian:DoubleClaudeBlock] 禁止寫入 `~/.claude/.claude/memory/` 雙層路徑。"
            "這是 P1 雙層 bug 的殘骸 — 應寫到 `~/.claude/memory/`。"
        )

    if os.environ.get("WG_DISABLE_ATOM_GUARD") == "1":
        return None
    fp = Path(fp_str)
    # memory/ 樹下 atom，或 _AIDocs/Failures/ 下「註冊 atom」(feedback-* 等失敗 atom)
    # 皆須走 funnel；後者不在 memory 樹下，需 _is_failures_atom_path 補攔（覆蓋缺口）。
    if not _path_under_memory_dir(fp) and not _is_failures_atom_path(fp):
        return None
    if fp.suffix != ".md":
        return None
    if _atom_path_whitelisted(fp):
        return None
    return (
        "[Guardian:AtomFunnelBlock] 直接 Write/Edit atom .md 不走 funnel 被禁止。\n"
        f"路徑：{fp_str}\n"
        "正確做法：\n"
        "  (1) 用 MCP `atom_write` / `atom_promote` / `atom_move` 工具；\n"
        "      只改 Trigger/Related/Tags 元資料 → `atom_edit_meta`（外科編輯，byte-stable）\n"
        "  (2) 程式碼端：知識內容寫 lib.atom_io.write_atom() / write_raw() / edit_metadata()；\n"
        "      計數欄位（read_hits / last_used / confirmations）寫 lib.atom_access\n"
        "緊急 bypass：set 環境變數 `WG_DISABLE_ATOM_GUARD=1` 後重試。"
    )


def check_svn_test_block(
    tool_name: str, tool_input: Dict[str, Any]
) -> Optional[str]:
    """阻擋 svn commit 含 test/tests/__tests__ 路徑或 *Test.<ext> 檔。"""
    if tool_name != "Bash":
        return None
    cmd = tool_input.get("command", "") or ""
    if not _SVN_COMMIT_RE.search(cmd):
        return None
    if not _TEST_PATH_RE.search(cmd):
        return None
    return (
        "[Guardian:SvnTestBlock] svn commit 命令含 test/tests/__tests__ 路徑或 "
        "*Test.<ext> 檔案。測試/練習/新手作業檔不可上 SVN（r10854 教訓）。\n"
        "若確實要上，請 (1) 將指定檔案逐一列入命令、不用 glob；或 "
        "(2) 由使用者明確指示後再執行。"
    )


# ─── MCP Server Health Check (was wg_intent._check_mcp_servers) ──────────────


def _check_mcp_servers() -> List[str]:
    """Verify .mcp.json server entries: command + script must exist on disk."""
    issues: List[str] = []
    mcp_path = CLAUDE_DIR / ".mcp.json"
    if not mcp_path.exists():
        return []
    try:
        with open(mcp_path, "r", encoding="utf-8") as f:
            mcp_cfg = json.loads(f.read())
        servers = mcp_cfg.get("mcpServers", {})
        for name, srv in servers.items():
            cmd = srv.get("command", "")
            args = srv.get("args", [])
            if cmd and not Path(cmd).exists() and not shutil.which(cmd):
                issues.append(f"{name}: command not found ({cmd})")
            if args:
                script = args[0]
                if not Path(script).exists():
                    issues.append(f"{name}: script not found ({script})")
    except Exception as e:
        issues.append(f"parse error: {e}")
    return issues

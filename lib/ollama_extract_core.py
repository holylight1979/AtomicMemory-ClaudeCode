"""
ollama_extract_core.py — Shared extraction utilities for extract-worker.py and user-extract-worker.py.

Functions preserve the signatures used by extract-worker.py and user-extract-worker.py.
"""

import json
import re
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# ─── sys.path for ollama_client ─────────────────────────────────────────────
_CLAUDE_DIR = Path.home() / ".claude"
_TOOLS_DIR = str(_CLAUDE_DIR / "tools")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from ollama_client import get_client

VALID_TYPES = ("factual", "procedural", "architectural", "pitfall", "decision")


# ─── Token estimation ──────────────────────────────────────────────────────

def _estimate_tokens(text: str) -> int:
    """CJK-aware token estimation. CJK ~1.5 tok/char, \u5176\u9918 ~0.25 tok/char\uff08\u7686\u6309\u5b57\u5143\u8a08\uff09\u3002

    CJK \u5224\u5b9a\u6db5\u84cb\uff1a\u6f22\u5b57\uff08U+4E00-9FFF\uff09\u3001CJK \u6a19\u9ede\uff08U+3000-303F\uff09\u3001
    \u304b\u306a\uff08U+3040-30FF\uff09\u3001\u5168\u5f62/\u534a\u5f62\u5f62\u5f0f\uff08U+FF00-FFEF\uff0c\u542b\u5168\u5f62\u6a19\u9ede\uff1a\uff1f\uff01\uff08\uff09\u7b49\uff09\u3002
    """
    if not text:
        return 0
    cjk = sum(
        1 for c in text
        if '\u4e00' <= c <= '\u9fff'
        or '\u3000' <= c <= '\u303f'
        or '\u3040' <= c <= '\u30ff'
        or '\uff00' <= c <= '\uffef'
    )
    ascii_part = len(text) - cjk
    return int(cjk * 1.5 + ascii_part * 0.25)


# ─── Atom Debug Log ────────────────────────────────────────────────────────

def _atom_debug_log(tag: str, content: str, config: Dict[str, Any] = None) -> None:
    """Write to atom-debug.log when atom_debug flag is on.
    For ERROR tag, always write regardless of flag.
    Skips empty/NONE entries to reduce noise."""
    if tag != "ERROR" and not (config or {}).get("atom_debug", False):
        return
    if not content or not content.strip():
        return  # suppress empty entries
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
    """Log error with source context and stack trace."""
    tb = traceback.format_exc()
    if "NoneType" in tb:
        tb = f"{type(exc).__name__}: {exc}"
    _atom_debug_log("ERROR", f"[{source}] {tb}", {"atom_debug": True})


# ─── Ollama ────────────────────────────────────────────────────────────────

def _call_ollama(prompt: str, model: str = None, timeout: int = 120) -> str:
    try:
        client = get_client()
        # think="auto": rdchat(gemma4:e4b)=True, local(qwen3:1.7b)=False — 由 backend config 控制
        # temperature=0.0: A/B 測試 Round 2 結論，一致性最佳
        # num_predict: 由 backend config 的 llm_num_predict 控制（rdchat=4096, local=2048）
        return client.generate(
            prompt, model=model, timeout=timeout,
            think="auto", temperature=0.0,
        )
    except Exception as e:
        _atom_debug_error("萃取:_call_ollama", e)
        return ""


# ─── Parse + Dedup ─────────────────────────────────────────────────────────

def _parse_llm_response(raw: str) -> List[dict]:
    if not raw:
        return []
    items = []
    try:
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            parsed = json.loads(match.group(0))
            # Filter: only keep dict items (LLM may emit strings/ints in array)
            items = [x for x in parsed if isinstance(x, dict)]
    except (json.JSONDecodeError, ValueError):
        for m in re.finditer(r'"content"\s*:\s*"([^"]{10,150})"', raw):
            items.append({"content": m.group(1), "type": "factual"})
    return items


def _word_overlap_score(a: str, b: str) -> float:
    wa = set(a.lower().split())
    wb = set(b.lower().split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / min(len(wa), len(wb))


def _dedup_items(
    items: List[dict], existing_queue: List[dict], threshold: float = 0.80
) -> List[dict]:
    """Validate, deduplicate, and format extracted items."""
    existing_contents = [q.get("content", "") for q in existing_queue if q.get("content")]
    results = []
    now = datetime.now().astimezone().isoformat()

    for item in items[:5]:
        content = item.get("content", "").strip()
        if not content or len(content) < 10:
            continue

        # Check overlap against existing queue
        skip = False
        for ec in existing_contents:
            if _word_overlap_score(content, ec) >= threshold:
                skip = True
                break
        if skip:
            continue

        # Check overlap against already-accepted results
        for r in results:
            if _word_overlap_score(content, r["content"]) >= threshold:
                skip = True
                break
        if skip:
            continue

        kt = item.get("type", "factual")
        if kt not in VALID_TYPES:
            kt = "factual"

        results.append({
            "content": content[:150],
            "classification": "[臨]",
            "knowledge_type": kt,
            "source": "session-end",
            "confirmations": 1,
            "at": now,
        })
        existing_contents.append(content)

    return results


# ─── Ack-then-clear ──────────────────────────────────────────────────

def ack_then_clear(state_path: Path, key: str, indices: List[int]) -> bool:
    """Read state → pop specified indices from state[key] → write back（持鎖 RMW）。

    Used to clear successfully-written items from knowledge_queue / pending_user_extract
    without losing items added concurrently by other hooks.

    整段 read-modify-write 持 advisory lock（仿 atom_locations.append_learned_terms
    的 msvcrt 模式）：無鎖時兩個 worker 併發 RMW 會 lost-update——
    對方剛 append 的 queue 項被本方以舊快照整檔覆寫而永久遺失。

    Returns True on success, False on any error.
    """
    lock_path = state_path.with_suffix(".lock")
    lock_fh = None
    if sys.platform == "win32":
        try:
            import msvcrt
            lock_fh = open(lock_path, "ab")
            msvcrt.locking(lock_fh.fileno(), msvcrt.LK_LOCK, 1)
        except OSError:
            # 鎖失敗 fail-open（不阻斷清佇列），但留訊號（可觀測性鐵律）
            print(f"[ack_then_clear] advisory lock unavailable for {state_path.name}; "
                  "proceeding unlocked", file=sys.stderr)
            if lock_fh:
                lock_fh.close()
            lock_fh = None
    try:
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
        except (json.JSONDecodeError, OSError):
            return False

        queue = state.get(key, [])
        if not queue or not indices:
            return True  # nothing to clear

        # Pop indices in reverse order to maintain correctness
        for idx in sorted(indices, reverse=True):
            if 0 <= idx < len(queue):
                queue.pop(idx)

        state[key] = queue
        state["last_updated"] = datetime.now().astimezone().isoformat()

        # Atomic write: temp file → rename
        tmp = state_path.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            tmp.replace(state_path)
            return True
        except OSError:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
            return False
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


# ─── Session Budget Tracker ──────────────────────────────────────────

class SessionBudgetTracker:
    """Track token budget consumption within a session.

    Budget defaults to 240 tok.
    When exceeded, callers should degrade to L1-only or skip extraction entirely.
    """

    def __init__(self, budget: int = 240):
        self._budget = budget
        self._spent = 0

    def spend(self, tok: int) -> None:
        """Record token expenditure."""
        self._spent += tok

    def remaining(self) -> int:
        """Return remaining budget (may be negative if overspent)."""
        return self._budget - self._spent

    def is_exceeded(self) -> bool:
        """Return True if budget is fully consumed."""
        return self._spent >= self._budget

"""
quick-extract.py — Stop async hook: 快速知識萃取 → hot cache (V3)

背景執行，讀 last_assistant_message，呼叫 local LLM (qwen3:1.7b) 快篩，
結果寫入 workflow/hot_cache.json。
"""

import json
import re
import sys
import time
from pathlib import Path

# ─── sys.path + UTF-8 fix (same as extract-worker.py) ──────────────────────────

_HOOKS_DIR = str(Path(__file__).resolve().parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

_CLAUDE_DIR = Path.home() / ".claude"

# Windows cp950 → UTF-8
if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(_CLAUDE_DIR / "tools"))

# ─── imports ────────────────────────────────────────────────────────────────────

from wg_extraction import write_hot_cache

# ─── constants ──────────────────────────────────────────────────────────────────

MIN_TEXT_LEN = 100
MAX_TEXT_LEN = 2000
OLLAMA_TIMEOUT = 15

EXTRACT_PROMPT = (
    "Extract key project-specific knowledge from this AI response.\n"
    'Output JSON: [{{"content":"fact in ≤150 chars","category":"decision|architecture|tool|failure"}}]\n'
    "Output [] if nothing worth extracting. /no_think\n"
    "Text: {text}\n"
    "JSON:"
)


# ─── helpers ────────────────────────────────────────────────────────────────────


def _parse_json_array(raw: str) -> list:
    """Parse JSON array from LLM output, with regex fallback."""
    raw = raw.strip()
    # Try direct parse
    try:
        result = json.loads(raw)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass
    # Regex fallback: find first [...] block
    m = re.search(r"\[.*?\]", raw, re.DOTALL)
    if m:
        try:
            result = json.loads(m.group())
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass
    return []


# ─── main ───────────────────────────────────────────────────────────────────────


def main():
    # 1. Read stdin
    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, OSError):
        return

    session_id = hook_input.get("session_id", "")
    text = hook_input.get("last_assistant_message", "")

    if not text or len(text) < MIN_TEXT_LEN:
        return

    # 2. Truncate
    truncated = text[:MAX_TEXT_LEN]

    # 3. Call Ollama (local backend, qwen3:1.7b)
    try:
        from ollama_client import get_client

        client = get_client()
        prompt = EXTRACT_PROMPT.format(text=truncated)
        result = client.generate(
            prompt,
            timeout=OLLAMA_TIMEOUT,
            think=False,
            num_predict=512,
            temperature=0.1,
        )
    except Exception:
        return  # Ollama unavailable → silent exit

    if not result:
        return

    # 4. Parse response
    items = _parse_json_array(result)
    if not items:
        return

    # Validate items structure
    valid_items = []
    for item in items:
        if isinstance(item, dict) and "content" in item:
            valid_items.append({
                "content": str(item["content"])[:150],
                "confidence": "[臨]",
                "category": item.get("category", "decision"),
            })
    if not valid_items:
        return

    # 5. Build summary
    summary = "; ".join(item["content"][:60] for item in valid_items[:3])
    if len(summary) > 200:
        summary = summary[:197] + "..."

    # 6. Estimate tokens (~1.5 chars per token for mixed zh/en)
    total_chars = sum(len(item["content"]) for item in valid_items)
    token_estimate = int(total_chars / 1.5) + 20  # overhead

    # 7. Write hot cache
    write_hot_cache({
        "session_id": session_id,
        "timestamp": time.time(),
        "source": "quick_extract",
        "injected": False,
        "knowledge": valid_items,
        "summary": summary,
        "token_estimate": token_estimate,
    })

    # 8. Output systemMessage for async hook
    output = {"systemMessage": f"[QuickExtract] {len(valid_items)} items cached"}
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()

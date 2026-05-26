#!/usr/bin/env python3
"""
memory-session-score.py — V4.1 P4 /memory-session-score backend

Reads reflection_metrics.json `v41_extraction.session_scores[]` and displays
session evaluation breakdowns. Future V4.2 `/v41-backfill --score-threshold=0.5`
will use this data for filtering.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

HOOKS_DIR = Path.home() / ".claude" / "hooks"
sys.path.insert(0, str(HOOKS_DIR))
from wg_core import MEMORY_DIR  # noqa: E402

REFLECTION_METRICS_PATH = MEMORY_DIR / "wisdom" / "reflection_metrics.json"


def _parse_since(since_str: str) -> Optional[datetime]:
    if not since_str:
        return None
    m = re.match(r'^(\d+)\s*([hHdD])$', since_str.strip())
    if m:
        val = int(m.group(1))
        unit = m.group(2).lower()
        td = timedelta(hours=val) if unit == 'h' else timedelta(days=val)
        return datetime.now(timezone.utc) - td
    try:
        return datetime.strptime(since_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _load_scores() -> List[dict]:
    if not REFLECTION_METRICS_PATH.is_file():
        return []
    try:
        data = json.loads(REFLECTION_METRICS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data.get("v41_extraction", {}).get("session_scores", []) or []


def _filter_and_sort(
    scores: List[dict], mode: str, since: str, top_n: Optional[int],
) -> List[dict]:
    if mode == "last":
        return scores[-1:] if scores else []

    if since:
        since_dt = _parse_since(since)
        if since_dt:
            kept = []
            for s in scores:
                ts = s.get("ts", "")
                try:
                    s_dt = datetime.fromisoformat(ts)
                    if s_dt >= since_dt:
                        kept.append(s)
                except (ValueError, TypeError):
                    continue
            return kept
        return scores

    if top_n:
        sorted_scores = sorted(
            scores,
            key=lambda s: s.get("scores", {}).get("weighted_total", 0.0),
            reverse=True,
        )
        return sorted_scores[:top_n]

    # Default: show all (most recent last)
    return scores


def _format_entry(e: dict) -> str:
    sid = e.get("session_id", "?")[:12]
    ts = e.get("ts", "")
    try:
        ts_short = datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        ts_short = ts[:16]
    s = e.get("scores", {})
    lines = [
        f"[{ts_short}] session={sid}  weighted={s.get('weighted_total', 0):.2f}",
        f"  density={s.get('density', 0):.2f}  precision={s.get('precision_proxy', 0):.2f}  "
        f"novelty={s.get('novelty', 0):.2f}  cost={s.get('cost_efficiency', 0):.2f}  "
        f"trust={s.get('trust', 0):.2f}",
        f"  {e.get('prompt_count', 0)} prompts | {e.get('extract_triggered', 0)} triggered | "
        f"{e.get('extract_written', 0)} written | conf avg {e.get('avg_l2_conf', 0):.2f} | "
        f"{e.get('token_used', 0)} tok",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="V4.1 /memory-session-score backend")
    ap.add_argument("--last", action="store_true", help="Show last session only")
    ap.add_argument("--since", default="", help="Filter: '24h', '7d', or '2026-04-16'")
    ap.add_argument("--top-n", type=int, default=0, help="Top-N by weighted score")
    ap.add_argument("--json", action="store_true", help="Output JSON instead of formatted text")
    args = ap.parse_args()

    scores = _load_scores()
    if not scores:
        out = {"count": 0, "message": "尚無 session_score 紀錄。本 session 結束後會產出第一筆。"}
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    if args.last:
        mode = "last"
    elif args.since:
        mode = "since"
    elif args.top_n > 0:
        mode = "top_n"
    else:
        mode = "all"

    filtered = _filter_and_sort(scores, mode, args.since, args.top_n or None)

    if args.json:
        print(json.dumps({
            "count": len(filtered),
            "mode": mode,
            "entries": filtered,
        }, ensure_ascii=False, indent=2))
        return

    print(f"[V4.1 Session Scores — {mode} ({len(filtered)} 筆)]")
    for e in filtered:
        print(_format_entry(e))
        print("")


if __name__ == "__main__":
    main()

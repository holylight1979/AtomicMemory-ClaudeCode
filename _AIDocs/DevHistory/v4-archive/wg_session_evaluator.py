#!/usr/bin/env python3
"""
wg_session_evaluator.py — V4.1 P4 Session 評價機制

5 維度加權評分：
  density (0.15) + precision_proxy (0.35) + novelty (0.20)
  + cost_efficiency (0.15) + trust (0.15) = weighted_total ∈ [0, 1]

Pure Python, no external I/O beyond reflection_metrics.json (atomic tmp→rename).
Runs in <100ms. Appends to v41_extraction.session_scores[] (FIFO cap 100).

Called from:
  - user-extract-worker.py main() end (path A — has worker_stats)
  - workflow-guardian.py handle_session_end() (path B — worker_stats=None)
"""

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ─── Path setup ───────────────────────────────────────────────────────────────
_HOOKS_DIR = str(Path.home() / ".claude" / "hooks")
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

from wg_paths import MEMORY_DIR  # noqa: E402

REFLECTION_METRICS_PATH = MEMORY_DIR / "wisdom" / "reflection_metrics.json"

# 5 維度權重（加總 = 1.0）
WEIGHTS = {
    "density": 0.15,
    "precision_proxy": 0.35,
    "novelty": 0.20,
    "cost_efficiency": 0.15,
    "trust": 0.15,
}

TOKEN_BUDGET = 240  # v4.1 NFR ceiling
SESSION_SCORES_CAP = 100  # FIFO cap


def _clip01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def _compute_scores(
    prompt_count: int,
    extract_triggered: int,
    confirmed: int,
    dedup_hit: int,
    avg_l2_conf: float,
    token_used: int,
    total_written_24h: int,
    rejected_24h: int,
    l2_ran: bool,
) -> Dict[str, float]:
    """Compute 5 dimensions + weighted_total, all in [0, 1]."""
    pc = max(prompt_count, 1)
    density = _clip01(math.tanh(extract_triggered / pc))

    # L2 never ran → no precision signal; default to 1.0 (conservative: don't penalize)
    precision_proxy = _clip01(avg_l2_conf) if l2_ran else 1.0

    total_write_attempts = confirmed + dedup_hit
    if total_write_attempts == 0:
        novelty = 1.0  # No writes → no dedup possible; neutral high
    else:
        novelty = _clip01(confirmed / total_write_attempts)

    cost_efficiency = _clip01(1.0 - (token_used / TOKEN_BUDGET))

    # Trust = 1 - reject_rate over 24h (needs at least 1 written to compute)
    if total_written_24h <= 0:
        trust = 1.0
    else:
        trust = _clip01(1.0 - (rejected_24h / total_written_24h))

    weighted = (
        WEIGHTS["density"] * density
        + WEIGHTS["precision_proxy"] * precision_proxy
        + WEIGHTS["novelty"] * novelty
        + WEIGHTS["cost_efficiency"] * cost_efficiency
        + WEIGHTS["trust"] * trust
    )

    return {
        "density": round(density, 4),
        "precision_proxy": round(precision_proxy, 4),
        "novelty": round(novelty, 4),
        "cost_efficiency": round(cost_efficiency, 4),
        "trust": round(trust, 4),
        "weighted_total": round(weighted, 4),
    }


def _read_reflection_metrics() -> Dict[str, Any]:
    if not REFLECTION_METRICS_PATH.is_file():
        return {}
    try:
        return json.loads(REFLECTION_METRICS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_reflection_metrics_atomic(data: Dict[str, Any]) -> bool:
    try:
        REFLECTION_METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = REFLECTION_METRICS_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(REFLECTION_METRICS_PATH)
        return True
    except OSError:
        return False


def append_session_score(score_entry: Dict[str, Any]) -> bool:
    """Append a score entry to v41_extraction.session_scores[], FIFO cap SESSION_SCORES_CAP."""
    data = _read_reflection_metrics()
    v41 = data.setdefault("v41_extraction", {
        "total_written": 0,
        "total_rejected": 0,
        "reject_reasons": {
            "emotion": 0, "ambiguous": 0, "privacy": 0, "scope": 0, "other": 0,
        },
        "precision_observed": 1.0,
    })
    scores: List[Dict] = v41.setdefault("session_scores", [])
    scores.append(score_entry)
    if len(scores) > SESSION_SCORES_CAP:
        v41["session_scores"] = scores[-SESSION_SCORES_CAP:]
    return _write_reflection_metrics_atomic(data)


def evaluate_session(
    session_id: str,
    state: Dict[str, Any],
    config: Dict[str, Any],
    worker_stats: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Main entry. Returns the score entry (also appended to reflection_metrics)."""
    topic_tracker = state.get("topic_tracker", {}) or {}
    prompt_count = int(topic_tracker.get("prompt_count", 0))

    if worker_stats:
        extract_triggered = int(worker_stats.get("processed", 0))
        confirmed = int(worker_stats.get("confirmed", 0))
        dedup_hit = int(worker_stats.get("dedup_hit", 0))
        avg_l2_conf = float(worker_stats.get("avg_l2_conf", 0.0))
        token_used = int(worker_stats.get("token_used", 0))
        l2_ran = bool(worker_stats.get("l2_ran", False))
    else:
        # Path B: worker did not spawn (pending was empty). Pre-spawn pending gives triggered count.
        pending = state.get("pending_user_extract", []) or []
        extract_triggered = len(pending)
        confirmed = 0
        dedup_hit = 0
        avg_l2_conf = 0.0
        token_used = 0
        l2_ran = False

    reflection = _read_reflection_metrics()
    v41 = reflection.get("v41_extraction", {}) or {}
    total_written_24h = int(v41.get("total_written", 0))
    rejected_24h = int(v41.get("total_rejected", 0))

    scores = _compute_scores(
        prompt_count=prompt_count,
        extract_triggered=extract_triggered,
        confirmed=confirmed,
        dedup_hit=dedup_hit,
        avg_l2_conf=avg_l2_conf,
        token_used=token_used,
        total_written_24h=total_written_24h,
        rejected_24h=rejected_24h,
        l2_ran=l2_ran,
    )

    entry = {
        "session_id": session_id,
        "ts": datetime.now(timezone.utc).isoformat(),
        "prompt_count": prompt_count,
        "extract_triggered": extract_triggered,
        "extract_written": confirmed,
        "dedup_hit": dedup_hit,
        "rejected_24h": rejected_24h,
        "avg_l2_conf": round(avg_l2_conf, 4),
        "token_used": token_used,
        "scores": scores,
    }

    append_session_score(entry)
    return entry


if __name__ == "__main__":
    # CLI: evaluate a historical session by reading state file
    import argparse
    ap = argparse.ArgumentParser(description="V4.1 session evaluator")
    ap.add_argument("--session-id", required=True)
    ap.add_argument("--state-file", help="Path to state-{sid}.json", default=None)
    args = ap.parse_args()

    if args.state_file:
        state_path = Path(args.state_file)
    else:
        from wg_paths import WORKFLOW_DIR
        state_path = WORKFLOW_DIR / f"state-{args.session_id}.json"

    if not state_path.is_file():
        print(json.dumps({"error": f"state file not found: {state_path}"}))
        sys.exit(1)

    state = json.loads(state_path.read_text(encoding="utf-8"))
    result = evaluate_session(args.session_id, state, {}, worker_stats=None)
    print(json.dumps(result, ensure_ascii=False, indent=2))

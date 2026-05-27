"""wg_evasion.py — Evasion Guard + Test-Fail Gate helpers.

PostToolUse(Bash): 偵測測試/語法檢查失敗 → state["failing_tests"]
Stop: 偵測完成宣告 + failing_tests 非空 → output_block（硬阻擋）
Stop: 偵測退避詞彙 → state["evasion_flag"]
UPS: 讀 evasion_flag → 注入舉證要求，清旗標
UPS: 使用者放行關鍵字 → 清 failing_tests

V5 P4b: 禁語/放行/掃描報告/完成宣告四類 pattern 從
memory/_meta/forbidden-phrases.json 載入；fail-open 退回硬編碼 fallback。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Pattern


_TEST_CMD_RE = re.compile(
    r"(?:^|\s)(?:pytest|python\s+-m\s+pytest|npm\s+(?:run\s+)?test|jest|node\s+--check|tsc|go\s+test|cargo\s+test)(?:\s|$)"
)

_FAILURE_PATTERNS = [
    re.compile(r"^=+.*\b\d+\s+failed", re.MULTILINE),
    re.compile(r"\b\d+\s+failed[,\s]"),
    re.compile(r"^FAILED\s", re.MULTILINE),
    re.compile(r"\bSyntaxError\b"),
    re.compile(r"\berror\s+TS\d+:"),
    re.compile(r"Tests:\s+\d+\s+failed"),
    re.compile(r"^---\s+FAIL:", re.MULTILINE),
    re.compile(r"test result:\s+FAILED"),
]


# ─── V5 P4b: phrase loader (single source = memory/_meta/forbidden-phrases.json) ──

_PHRASES_JSON = Path.home() / ".claude" / "memory" / "_meta" / "forbidden-phrases.json"


_FALLBACK_EVASION_PATTERNS = [
    r"不在本[^，。\s]{0,6}範圍", r"範圍外",
    r"既有[^，。\s]{0,6}drift", r"既有[^，。\s]{0,6}問題", r"pre-?existing",
    r"留給[^，。\s]{0,4}未來", r"超出[^，。\s]{0,4}能力",
    r"非本次", r"先跳過", r"不影響[^，。\s]{0,4}主線", r"非本次改動",
    r"(?:下次|下回|下一次|之後|晚點|稍後|有空|有時間)\s*再\s*(?:處理|修|補|做|看|弄)?",
    r"未來[^，。\s]{0,3}處理", r"待後續", r"另行處理", r"另外處理",
    r"留給使用者",
]
_FALLBACK_DISMISS_PATTERNS = [
    r"先這樣", r"留著", r"不用管", r"不要管", r"跳過", r"先跳過",
    r"known\s+regression", r"confirmed\s+regression",
]
_FALLBACK_SCAN_REPORT_PATTERNS = [
    # V5 4 項收尾檢核 markers
    r"缺失發現", r"缺失發現與修補清單", r"修補清單",
    r"衍生暫存清單", r"衍生暫存",
    r"AI\s*逃避通報", r"Token\s*累積警示", r"收尾檢核",
    # 向下相容（V4 舊格式）
    r"順手修補", r"順手修", r"附帶修補",
    r"發現[^，。\n]{0,6}drift",
    r"本次[^，。\n]{0,3}(?:無|沒有)[^，。\n]{0,6}drift",
    r"無發現\s*drift", r"無\s*drift", r"no\s+drift",
    r"掃描報告", r"drift\s+(?:check|report)",
    r"需另開\s*session", r"列入\s*handoff",
]
_FALLBACK_COMPLETION_PATTERNS = [
    r"完成", r"已解決", r"全部做完", r"總結", r"收尾",
    r"done", r"finished", r"all\s+set", r"wrapped\s+up",
    r"大功告成", r"搞定",
]


def _load_phrases() -> Dict[str, List[str]]:
    """Read forbidden-phrases.json → {evasion, dismiss, scan_report, completion} pattern lists.

    Any read/parse error → empty dict (caller falls back to hardcoded constants).
    """
    try:
        data = json.loads(_PHRASES_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    evasion: List[str] = []
    for cat in data.get("categories", []) or []:
        for p in cat.get("patterns", []) or []:
            if p:
                evasion.append(p)
    dismiss = list(data.get("dismiss_keywords", {}).get("patterns", []) or [])
    scan_report = list(data.get("scan_report_markers", {}).get("patterns", []) or [])
    completion = list(data.get("completion_claim", {}).get("patterns", []) or [])
    return {
        "evasion": evasion or _FALLBACK_EVASION_PATTERNS,
        "dismiss": dismiss or _FALLBACK_DISMISS_PATTERNS,
        "scan_report": scan_report or _FALLBACK_SCAN_REPORT_PATTERNS,
        "completion": completion or _FALLBACK_COMPLETION_PATTERNS,
    }


def _compile_union(patterns: List[str], flags: int = 0) -> Pattern:
    """Compile a union regex from a pattern list. Empty → matches nothing."""
    if not patterns:
        return re.compile(r"(?!)")  # never matches
    return re.compile("(" + "|".join(patterns) + ")", flags)


_phrases = _load_phrases() or {
    "evasion": _FALLBACK_EVASION_PATTERNS,
    "dismiss": _FALLBACK_DISMISS_PATTERNS,
    "scan_report": _FALLBACK_SCAN_REPORT_PATTERNS,
    "completion": _FALLBACK_COMPLETION_PATTERNS,
}

_EVASION_RE = _compile_union(_phrases["evasion"])
_DISMISS_RE = _compile_union(_phrases["dismiss"], re.IGNORECASE)
_SCAN_REPORT_RE = _compile_union(_phrases["scan_report"], re.IGNORECASE)
_COMPLETION_CLAIM_RE = _compile_union(_phrases["completion"], re.IGNORECASE)


def is_test_command(cmd: str) -> bool:
    return bool(_TEST_CMD_RE.search(cmd or ""))


def tail_lines(s: str, n: int) -> str:
    lines = [l for l in (s or "").splitlines() if l.strip()]
    return "\n".join(lines[-n:])


def detect_test_failure(
    stdout: str, stderr: str, interrupted: bool
) -> Optional[str]:
    """Return last-20-lines summary if failure detected, else None."""
    combined = (stdout or "") + "\n" + (stderr or "")
    if interrupted:
        return tail_lines(combined, 20) or "(interrupted, no output)"
    for pat in _FAILURE_PATTERNS:
        if pat.search(combined):
            return tail_lines(combined, 20)
    return None


def claims_completion(text: str) -> bool:
    if not text:
        return False
    return bool(_COMPLETION_CLAIM_RE.search(text[-2000:]))


def detect_evasion(text: str, recent_user_prompts: List[str]) -> Optional[Dict[str, str]]:
    """Return {phrase, context_excerpt} or None.

    Escape hatch: 若近 3 則 user prompt 有明確豁免關鍵字 → 不標記。
    """
    if not text:
        return None
    m = _EVASION_RE.search(text)
    if not m:
        return None
    for p in (recent_user_prompts or [])[-3:]:
        if _DISMISS_RE.search(p or ""):
            return None
    phrase = m.group(0)
    idx = m.start()
    excerpt = text[max(0, idx - 80): idx + len(phrase) + 80]
    return {"phrase": phrase, "context_excerpt": excerpt}


def is_dismiss_prompt(prompt: str) -> bool:
    return bool(_DISMISS_RE.search(prompt or ""))


def has_scan_report(text: str) -> bool:
    """回報尾端是否含『順手修補清單/無 drift 宣告/另開 session』之一。"""
    if not text:
        return False
    return bool(_SCAN_REPORT_RE.search(text))


def detect_missing_scan_report(
    text: str,
    modified_file_count: int,
    recent_user_prompts: List[str],
) -> bool:
    """宣告完成但缺掃描報告 → 違約。

    觸發條件（全部成立）：
      1. text 含完成宣告詞
      2. modified_file_count > 0（有實際動工才要求掃描）
      3. text 不含任何 _SCAN_REPORT_RE 標記
      4. 近 3 則 user prompt 無豁免關鍵字
    """
    if not text or modified_file_count <= 0:
        return False
    if not claims_completion(text):
        return False
    if has_scan_report(text):
        return False
    for p in (recent_user_prompts or [])[-3:]:
        if _DISMISS_RE.search(p or ""):
            return False
    return True


def get_last_assistant_text(transcript_path: Optional[Path]) -> str:
    """Read JSONL transcript, return last assistant text block (or empty)."""
    if not transcript_path:
        return ""
    try:
        last = ""
        with open(transcript_path, "r", encoding="utf-8") as f:
            for raw in f:
                try:
                    obj = json.loads(raw)
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
                            last = t
        return last
    except (OSError, UnicodeDecodeError):
        return ""


# ─── V5: Session Evaluator (was wg_session_evaluator) ────────────────────────
# 4-套自評整合的一部分：5 維度加權評分，附 reflection_metrics.json 寫入。

import math
from datetime import datetime, timezone

from wg_core import (
    MEMORY_DIR, WORKFLOW_DIR, EPISODIC_DIR,
    discover_all_project_memory_dirs, get_project_memory_dir, resolve_staging_dir,
    _now_iso,
)

REFLECTION_METRICS_PATH = MEMORY_DIR / "wisdom" / "reflection_metrics.json"

EVAL_WEIGHTS = {
    "density": 0.15,
    "precision_proxy": 0.35,
    "novelty": 0.20,
    "cost_efficiency": 0.15,
    "trust": 0.15,
}
TOKEN_BUDGET = 240
SESSION_SCORES_CAP = 100


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
    pc = max(prompt_count, 1)
    density = _clip01(math.tanh(extract_triggered / pc))
    precision_proxy = _clip01(avg_l2_conf) if l2_ran else 1.0
    total_write_attempts = confirmed + dedup_hit
    novelty = 1.0 if total_write_attempts == 0 else _clip01(confirmed / total_write_attempts)
    cost_efficiency = _clip01(1.0 - (token_used / TOKEN_BUDGET))
    trust = 1.0 if total_written_24h <= 0 else _clip01(1.0 - (rejected_24h / total_written_24h))
    weighted = (
        EVAL_WEIGHTS["density"] * density
        + EVAL_WEIGHTS["precision_proxy"] * precision_proxy
        + EVAL_WEIGHTS["novelty"] * novelty
        + EVAL_WEIGHTS["cost_efficiency"] * cost_efficiency
        + EVAL_WEIGHTS["trust"] * trust
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
    """Append a score entry to v41_extraction.session_scores[]. FIFO cap."""
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


# ─── V5: Iteration metrics + oscillation + rut + review (was wg_iteration) ──
# 4-套自評整合的另一部分：collect / detect / maturity / review marker。


def _collect_iteration_metrics(state: Dict[str, Any]) -> Dict[str, Any]:
    """Collect self-iteration metrics from session state."""
    metrics = state.get("iteration_metrics", {})

    referenced = list(set(state.get("injected_atoms", [])))
    metrics["atoms_referenced"] = referenced

    modified_atoms = []
    for m in state.get("modified_files", []):
        p = m.get("path", "").replace("\\", "/")
        if "/memory/" in p and p.endswith(".md"):
            name = p.rsplit("/", 1)[-1].replace(".md", "")
            if name not in ("MEMORY", "_CHANGELOG", "_CHANGELOG_ARCHIVE"):
                modified_atoms.append(name)
    metrics["atoms_modified"] = list(set(modified_atoms))

    return metrics


def _detect_oscillation(
    state: Dict[str, Any], config: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Detect atoms modified 2+ times across last 3 sessions (oscillation)."""
    oscillation_window = config.get("self_iteration", {}).get("oscillation_window", 3)
    oscillation_threshold = config.get("self_iteration", {}).get("oscillation_threshold", 2)

    episodic_dirs = set()
    global_ep = MEMORY_DIR / "episodic"
    if global_ep.exists():
        episodic_dirs.add(global_ep)
    cwd = state.get("session", {}).get("cwd", "")
    proj_mem = get_project_memory_dir(cwd)
    if proj_mem:
        proj_ep = proj_mem / "episodic"
        if proj_ep.exists():
            episodic_dirs.add(proj_ep)

    recent_files = []
    for ep_dir in episodic_dirs:
        for f in ep_dir.glob("episodic-*.md"):
            recent_files.append((f.stat().st_mtime, f))
    recent_files.sort(key=lambda x: -x[0])
    recent_files = recent_files[:oscillation_window]

    atom_sessions = {}
    for _, ep_path in recent_files:
        try:
            text = ep_path.read_text(encoding="utf-8")
            date_match = re.search(r"Created:\s*(\d{4}-\d{2}-\d{2})", text)
            ep_date = date_match.group(1) if date_match else ep_path.stem[:15]
            for line in text.split("\n"):
                if "修改 atoms:" in line:
                    atoms_part = line.split("修改 atoms:")[-1].strip()
                    for a in atoms_part.split(","):
                        a = a.strip()
                        if a:
                            atom_sessions.setdefault(a, []).append(ep_date)
        except (OSError, UnicodeDecodeError):
            continue

    current_modified = state.get("iteration_metrics", {}).get("atoms_modified", [])
    today_str = datetime.now().strftime("%Y-%m-%d")
    for a in current_modified:
        atom_sessions.setdefault(a, []).append(today_str)

    oscillations = []
    for atom_name, sessions in atom_sessions.items():
        unique_sessions = list(set(sessions))
        if len(unique_sessions) >= oscillation_threshold:
            oscillations.append({
                "atom": atom_name,
                "sessions": unique_sessions,
                "count": len(unique_sessions),
                "recommendation": "暫停修改此 atom，等待更多證據再決定方向"
            })

    return oscillations


def _save_oscillation_state(oscillations: List[Dict[str, Any]]) -> None:
    osc_path = WORKFLOW_DIR / "oscillation_state.json"
    if oscillations:
        data = {
            "detected_at": datetime.now().isoformat(),
            "oscillations": [
                {"atom": o["atom"], "count": o["count"], "sessions": o["sessions"]}
                for o in oscillations
            ],
        }
        tmp = osc_path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(osc_path)
        except OSError:
            try:
                tmp.unlink()
            except OSError:
                pass
    elif osc_path.exists():
        osc_path.unlink()


def _load_oscillation_warnings() -> Optional[str]:
    osc_path = WORKFLOW_DIR / "oscillation_state.json"
    if not osc_path.exists():
        return None
    try:
        with open(osc_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        oscillations = data.get("oscillations", [])
        if not oscillations:
            return None
        atoms = ", ".join(o["atom"] for o in oscillations)
        return (
            f"[Guardian:Oscillation] 以下 atoms 近期被反覆修改：{atoms}。"
            f"行動：1) 暫停修改 2) Read 該 atom 確認前次意圖 3) 收集更多證據再評估"
        )
    except (json.JSONDecodeError, OSError):
        return None


def _calculate_maturity_phase(config: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate system maturity phase based on episodic atom count."""
    thresholds = config.get("self_iteration", {}).get("maturity_thresholds", {})
    learning_max = thresholds.get("learning", 15)
    stable_max = thresholds.get("stable", 50)

    total = 0
    for ep_dir in [MEMORY_DIR / "episodic"]:
        if ep_dir.exists():
            total += sum(1 for _ in ep_dir.glob("episodic-*.md"))

    for _slug, _mem_dir in discover_all_project_memory_dirs():
        ep = _mem_dir / "episodic"
        if ep.exists():
            total += sum(1 for _ in ep.glob("episodic-*.md"))

    if total < learning_max:
        phase = "learning"
        desc = f"學習期（{total}/{learning_max} sessions）— 積極學習新模式"
    elif total < stable_max:
        phase = "stable"
        desc = f"穩定期（{total}/{stable_max} sessions）— 收斂規則，減少新增"
    else:
        phase = "mature"
        desc = f"成熟期（{total} sessions）— 極少新增，專注精煉"

    return {"phase": phase, "total_sessions": total, "description": desc}


def _detect_rut_patterns(
    state: Dict[str, Any], config: Dict[str, Any]
) -> Optional[str]:
    """V2.17: Scan recent episodic atoms for repeated 覆轍信號."""
    window = config.get("self_iteration", {}).get("oscillation_window", 3)

    episodic_dirs = set()
    global_ep = MEMORY_DIR / "episodic"
    if global_ep.exists():
        episodic_dirs.add(global_ep)
    cwd = state.get("session", {}).get("cwd", "")
    proj_mem = get_project_memory_dir(cwd)
    if proj_mem:
        proj_ep = proj_mem / "episodic"
        if proj_ep.exists():
            episodic_dirs.add(proj_ep)

    recent_files = []
    for ep_dir in episodic_dirs:
        for f in ep_dir.glob("episodic-*.md"):
            recent_files.append((f.stat().st_mtime, f))
    recent_files.sort(key=lambda x: -x[0])
    recent_files = recent_files[:window]

    signal_sessions: Dict[str, int] = {}
    for _, ep_path in recent_files:
        try:
            text = ep_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line in text.split("\n"):
            if "覆轍信號:" not in line:
                continue
            signals_part = line.split("覆轍信號:")[-1].strip()
            for sig in signals_part.split(","):
                sig = sig.strip()
                if sig:
                    signal_sessions[sig] = signal_sessions.get(sig, 0) + 1

    repeated = [s for s, c in signal_sessions.items() if c >= 2]
    if not repeated:
        return None

    return (
        f"[Guardian:覆轍] 跨 session 反覆出現：{', '.join(repeated)}。"
        f"行動：1) 停止表面修復 2) 分析根因 3) 記錄到 atom 防止再犯"
    )


def _check_periodic_review_due(config: Dict[str, Any]) -> Optional[str]:
    """Check if periodic self-review is due."""
    review_interval = config.get("self_iteration", {}).get("review_interval", 6)
    marker_path = WORKFLOW_DIR / "last_review_marker.json"

    last_review_session_count = 0
    if marker_path.exists():
        try:
            with open(marker_path, "r", encoding="utf-8") as f:
                marker = json.load(f)
            last_review_session_count = marker.get("session_count", 0)
        except (json.JSONDecodeError, OSError):
            pass

    total = 0
    for ep_dir in [MEMORY_DIR / "episodic"]:
        if ep_dir.exists():
            total += sum(1 for _ in ep_dir.glob("episodic-*.md"))
    for _slug, _mem_dir in discover_all_project_memory_dirs():
        ep = _mem_dir / "episodic"
        if ep.exists():
            total += sum(1 for _ in ep.glob("episodic-*.md"))

    sessions_since_review = total - last_review_session_count
    if sessions_since_review >= review_interval:
        maturity = _calculate_maturity_phase(config)
        return (
            f"[自我迭代] 定期檢閱到期（距上次 {sessions_since_review} sessions）。"
            f"系統{maturity['description']}。"
            f"建議在適當時機進行近期 session 回顧：掃描 episodic atoms、"
            f"找出重複模式、收攏或晉升規則。"
        )
    return None


def _save_review_marker(total_sessions: int) -> None:
    """Save review marker after a periodic review is completed."""
    marker_path = WORKFLOW_DIR / "last_review_marker.json"
    marker = {
        "session_count": total_sessions,
        "reviewed_at": _now_iso(),
    }
    try:
        with open(marker_path, "w", encoding="utf-8") as f:
            json.dump(marker, f, ensure_ascii=False, indent=2)
    except OSError:
        pass

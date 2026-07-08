"""wg_evasion.py — Evasion Guard + Test-Fail Gate helpers.

PostToolUse(Bash): 偵測測試/語法檢查失敗 → state["failing_tests"]
Stop: 偵測完成宣告 + failing_tests 非空 → output_block（硬阻擋）
Stop: 偵測退避詞彙 → state["evasion_flag"]
UPS: 讀 evasion_flag → 注入舉證要求，清旗標
UPS: 使用者放行關鍵字 → 清 failing_tests

禁語/放行/掃描報告/完成宣告四類 pattern 從
memory/_meta/forbidden-phrases.json 載入；fail-open 退回硬編碼 fallback。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Pattern


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


# ─── phrase loader (single source = memory/_meta/forbidden-phrases.json) ──

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
# 進行式/否定修飾緊鄰完成詞 → 非真正終結宣告，排除（false-positive）。
_FALLBACK_COMPLETION_EXCLUDE = [
    r"(?:還沒|還未|尚未|尚待|未|沒有?|先確認|正在)[^，。！？\n]{0,8}(?:完成|做完|解決|收尾|搞定)",
    r"(?:完成|做完|解決|收尾|搞定)[^，。！？\n]{0,6}(?:尚未|還沒|還未|未完|沒完|未滿足|沒做完|未達|待補|待修)",
    r"待(?:補|修|辦|處理|確認|完善)",
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
    completion_claim = data.get("completion_claim", {}) or {}
    completion = list(completion_claim.get("patterns", []) or [])
    completion_exclude = list(
        (completion_claim.get("exclude_patterns", {}) or {}).get("patterns", []) or []
    )
    return {
        "evasion": evasion or _FALLBACK_EVASION_PATTERNS,
        "dismiss": dismiss or _FALLBACK_DISMISS_PATTERNS,
        "scan_report": scan_report or _FALLBACK_SCAN_REPORT_PATTERNS,
        "completion": completion or _FALLBACK_COMPLETION_PATTERNS,
        "completion_exclude": completion_exclude or _FALLBACK_COMPLETION_EXCLUDE,
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
    "completion_exclude": _FALLBACK_COMPLETION_EXCLUDE,
}

_EVASION_RE = _compile_union(_phrases["evasion"])
_DISMISS_RE = _compile_union(_phrases["dismiss"], re.IGNORECASE)
_SCAN_REPORT_RE = _compile_union(_phrases["scan_report"], re.IGNORECASE)
_COMPLETION_CLAIM_RE = _compile_union(_phrases["completion"], re.IGNORECASE)
_COMPLETION_EXCLUDE_RE = _compile_union(
    _phrases.get("completion_exclude") or _FALLBACK_COMPLETION_EXCLUDE, re.IGNORECASE
)


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
    """終結宣告偵測。命中完成詞後，若鄰近有進行式/否定修飾
    （還沒/尚未/未…完成、完成…尚未 等）→ 非真正終結，排除。
    偏 false-negative（少判完成→少誤阻）符合契約鬆綁方向。
    """
    if not text:
        return False
    tail = text[-2000:]
    if not _COMPLETION_CLAIM_RE.search(tail):
        return False
    if _COMPLETION_EXCLUDE_RE.search(tail):
        return False
    return True


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


_CORE_DIR_SEGMENTS = ("/hooks/", "/lib/", "/tools/", "/rules/")
_ROOT_CONFIG_FILES = frozenset({
    "claude.md", "identity.md", "user.md",
    "settings.json", "settings.local.json",
})


def is_core_file(path: str) -> bool:
    """path 是否為系統核心檔（hooks/lib/tools/rules 目錄 或 根層契約/設定檔）。

    ScanReport gate 用：動 core 檔才要求收尾檢核。判定寬鬆偏保守
    （寧可對 core-like 路徑要求收尾）；純內容/文件（_AIDocs、memory atom .md）
    不落在這些目錄段，正確被排除。
    """
    if not path:
        return False
    p = path.replace("\\", "/").lower()
    if any(seg in p for seg in _CORE_DIR_SEGMENTS):
        return True
    fname = p.rsplit("/", 1)[-1]
    if fname in _ROOT_CONFIG_FILES:
        return True
    if fname.startswith("identity-") and fname.endswith(".md"):
        return True
    return False


def _completion_gate_applies(
    text: str,
    modified_files: List[Dict[str, Any]],
    recent_user_prompts: List[str],
    min_files: int,
) -> bool:
    """收尾閘共用前置：宣告完成 +（動 core 檔 或 動 ≥min_files 檔）+ 無豁免關鍵字。

    True＝已達「該交代收尾」門檻（尚未判定用何種方式滿足）。滿足方式（prose 標記
    vs anti_evasion_report emit）由各 caller 疊上。純單檔/文件小改不達門檻。

    達門檻條件（全部成立）：
      1. text 含完成宣告詞（claims_completion）
      2. modified_files 觸及 core 檔，或 unique 檔數 ≥ min_files
      3. 近 3 則 user prompt 無豁免關鍵字
    """
    if not text or not modified_files:
        return False
    if not claims_completion(text):
        return False
    for p in (recent_user_prompts or [])[-3:]:
        if _DISMISS_RE.search(p or ""):
            return False
    unique_paths = {(m or {}).get("path", "") for m in modified_files}
    unique_paths.discard("")
    touched_core = any(is_core_file(p) for p in unique_paths)
    if not touched_core and len(unique_paths) < max(int(min_files), 1):
        return False
    return True


def detect_missing_scan_report(
    text: str,
    modified_files: List[Dict[str, Any]],
    recent_user_prompts: List[str],
    min_files: int = 2,
) -> bool:
    """宣告完成 +（動 core 檔 或 動 ≥min_files 檔）+ 缺 prose 收尾檢核標記 → 違約。

    滿足方式＝回報尾端含 _SCAN_REPORT_RE 標記（has_scan_report）。保留供既有 prose
    路徑 / 回歸測試；live 閘已改用 detect_missing_aec_emission（結構化 emit 滿足）。
    """
    if not _completion_gate_applies(text, modified_files, recent_user_prompts, min_files):
        return False
    return not has_scan_report(text)


def detect_missing_aec_emission(
    text: str,
    modified_files: List[Dict[str, Any]],
    recent_user_prompts: List[str],
    min_files: int = 2,
    emitted_this_turn: bool = False,
) -> bool:
    """鏡像 detect_missing_scan_report，唯滿足方式從 prose 標記換成「本回合是否 emit 過
    anti_evasion_report」（emitted_this_turn 由 caller 以 turn_seq+session_id 雙鍵判定）。

    回 True＝達門檻卻未 emit（block、逼補結構化收尾檢核）。門檻與豁免（core/min_files、
    dismiss 逃生門）與 scan_report 版共用 _completion_gate_applies，不重演。
    """
    if not _completion_gate_applies(text, modified_files, recent_user_prompts, min_files):
        return False
    return not emitted_this_turn


def _aec_blank(v: Optional[str]) -> bool:
    """收尾檢核欄位是否「無內容」——空、「無」/「无」、或「無（附說明）」
    （含結尾標點，如「無。」「無（本輪未動 core）」）。
    太嚴（只認裸「無」）會把 routine 報告（模型慣寫「無。」「無（說明）」）
    誤判 real-evasion → 洗 chat，defeats HUD 目的；放寬只減誤升級，
    真退避是敘述文、絕不 normalize 成「無」。
    MIRROR: tools/workflow-guardian-mcp/lib/anti-evasion.js aecBlank — keep in sync。"""
    s = (v or "").strip().rstrip("　 。．.,，、；;：:!！?？~～-—…")
    if s == "":
        return True
    return bool(re.fullmatch(r"[無无]\s*(?:[（(][^）)]*[）)])?", s))


def aec_severity(a: str, b: str, c: str, d: str) -> str:
    """tool-arg 內容 severity（Node lib/anti-evasion.js aecSeverity 同規則、single source of truth）。

      - real-evasion：(b) AI 逃避通報非空≠「無」（真偷埋自report，最嚴重）
      - notable：(a) 缺失修補清單有真修補行（b 空）
      - routine：(a)(b) 皆「無」/空
    (c) Token 警示 / (d) 衍生暫存為資訊性，不升級 severity（severity 只衡量「退避」訊號）。
    """
    if not _aec_blank(b):
        return "real-evasion"
    if not _aec_blank(a):
        return "notable"
    return "routine"


def crosscheck_aec_severity(
    sev: str, b: str, hook_evidence: List[Dict[str, Any]]
) -> tuple:
    """AEC (b) 欄 cross-check：hook 實測到退避（evasion_flag / evasion_events）
    但模型自評 (b)=「無」 → 升 severity 為 real-evasion（不信模型自評）。

    回 (severity, upgraded)。(b) 已誠實填報（非空）→ 內容 severity 本就
    real-evasion，不重複升級。純函式；證據收集（state 讀取）由 one-writer
    caller（post_tool_use）負責。
    注意：Node chip（lib/anti-evasion.js aecSeverity）為純內容判定、無 session
    state 可查，chip 顯示可能仍為 routine——升級後的 severity 以 Python 落的
    report 檔 + Stop fallback 為準（one-writer 設計的既知不對稱）。"""
    if hook_evidence and _aec_blank(b):
        return "real-evasion", True
    return sev, False


def read_transcript_tail(
    transcript_path: Optional[Path], max_bytes: int = 2_000_000
) -> str:
    """讀 transcript 尾段一次，供同一 hook 內多個消費者共用（單次 I/O 取代逐函式全檔讀）。

    檔案 ≤ max_bytes 時即全檔；超過時取尾段並捨棄首個不完整行。尾窗涵蓋 Stop
    所需的全部訊號（最後 assistant 文字 / 本 turn 活動 / 最近 usage）——2MB ≈
    數百輪文字，遠大於單 turn 規模。fail-open 回 ""。
    """
    if not transcript_path:
        return ""
    try:
        with open(transcript_path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            if size > max_bytes:
                f.seek(size - max_bytes)
                data = f.read()
                nl = data.find(b"\n")
                data = data[nl + 1:] if nl >= 0 else data
            else:
                f.seek(0)
                data = f.read()
        return data.decode("utf-8", errors="ignore")
    except OSError:
        return ""


def get_last_assistant_text(
    transcript_path: Optional[Path], *, text: Optional[str] = None
) -> str:
    """Read JSONL transcript, return last assistant text block (or empty).

    text 給定時（read_transcript_tail 共用尾段）直接掃該字串、不再開檔。
    """
    if text is None:
        if not transcript_path:
            return ""
        try:
            text = Path(transcript_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError, ValueError):
            return ""
    last = ""
    for raw in text.splitlines():
        try:
            obj = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(obj, dict) or obj.get("type") != "assistant":
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


def _is_real_user_prompt(content: Any) -> bool:
    """判斷一則 user 訊息是「真實 prompt」還是「tool_result 延續」。

    含 tool_result block → 視為延續（非新 turn 起點）；str 或含 text block → 真實 prompt。
    """
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        has_text = False
        for b in content:
            if isinstance(b, dict):
                if b.get("type") == "tool_result":
                    return False
                if b.get("type") == "text":
                    has_text = True
            elif isinstance(b, str):
                has_text = True
        return has_text
    return False


def _flatten_tool_input(inp: Any, cap: int = 2000) -> str:
    """攤平 tool_use input 的所有字串值（file_path/command/content/old/new/pattern…）。"""
    out: List[str] = []

    def _walk(v: Any) -> None:
        if isinstance(v, str):
            out.append(v)
        elif isinstance(v, dict):
            for vv in v.values():
                _walk(vv)
        elif isinstance(v, list):
            for vv in v:
                _walk(vv)

    _walk(inp)
    return " ".join(out)[:cap]


def get_current_turn_text(
    transcript_path: Optional[Path], *, max_chars: int = 8000,
    text: Optional[str] = None,
) -> str:
    """擷取「本 turn」assistant 活動文字（assistant text + tool_use input args）。

    turn 邊界 = 最後一則真實 user prompt（非 tool_result 延續）之後的所有 assistant 訊息。
    供 use 偵測比對 atom 稀有 token。text 給定時（read_transcript_tail 共用尾段）
    直接掃該字串、不再開檔。fail-open 回 ""。
    """
    if text is None:
        if not transcript_path:
            return ""
        try:
            text = Path(transcript_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError, ValueError):
            return ""
    records: List[Dict[str, Any]] = []
    for raw in text.splitlines():
        try:
            obj = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(obj, dict):
            records.append(obj)

    last_user_idx = -1
    for i, obj in enumerate(records):
        if obj.get("type") != "user":
            continue
        if _is_real_user_prompt(obj.get("message", {}).get("content")):
            last_user_idx = i

    parts: List[str] = []
    total = 0
    for obj in records[last_user_idx + 1:]:
        if obj.get("type") != "assistant":
            continue
        content = obj.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            bt = block.get("type")
            if bt == "text":
                s = block.get("text", "") or ""
            elif bt == "tool_use":
                s = (block.get("name", "") or "") + " " + _flatten_tool_input(block.get("input", {}))
            else:
                continue
            if s:
                parts.append(s)
                total += len(s)
        if total >= max_chars:
            break
    return "\n".join(parts)[:max_chars]


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


# ─── 效用歸因遙測：outcome unknown 比率監測 ──────────────────────────────────
# _detect_turn_outcome 回 None(unknown) 的 turn 不動 (α,β)；若完成語 regex 與
# 模型輸出習慣失配（如換模型後中文完成語變化），unknown 會系統性偏高 → α/β
# 晉升軌靜默停滯。此監測讓停滯浮出（可觀測性鐵律）。

OUTCOME_STATS_PATH = WORKFLOW_DIR / "outcome_stats.jsonl"


def _unknown_streak(
    entries: List[Dict[str, Any]], threshold: float, window: int
) -> bool:
    """最近 window 筆 session 的 unknown 比率是否全部 > threshold。不足 window 筆 → False。"""
    if len(entries) < window:
        return False
    return all(
        float(e.get("ratio", 0.0)) > threshold for e in entries[-window:]
    )


def flush_outcome_stats(
    state: Dict[str, Any], config: Dict[str, Any], session_id: str = ""
) -> Optional[str]:
    """SessionEnd 收尾：把本 session 的 outcome_stats（Stop 端逐 turn 累計）落一筆
    到 workflow/outcome_stats.jsonl，並檢查連續偏高 → 回 advisory 字串（無則 None）。

    turn 數 < min_turns 的 session 不計（樣本太小，unknown 比率無意義）。fail-open。"""
    try:
        uconf = (config or {}).get("usefulness", {}) or {}
        wconf = uconf.get("unknown_watch", {}) or {}
        if not wconf.get("enabled", True):
            return None
        threshold = float(wconf.get("threshold", 0.7))
        window = int(wconf.get("window", 3))
        min_turns = int(wconf.get("min_turns", 3))

        stats = state.get("outcome_stats") or {}
        total = sum(int(stats.get(k, 0)) for k in ("success", "fail", "unknown"))
        if total < min_turns:
            return None
        unknown = int(stats.get("unknown", 0))
        ratio = unknown / total

        entries: List[Dict[str, Any]] = []
        if OUTCOME_STATS_PATH.exists():
            for raw in OUTCOME_STATS_PATH.read_text(encoding="utf-8").splitlines():
                try:
                    entries.append(json.loads(raw))
                except (json.JSONDecodeError, ValueError):
                    continue
        entry = {
            "at": _now_iso(),
            "session_id": session_id,
            "unknown": unknown,
            "total": total,
            "ratio": round(ratio, 4),
        }
        entries.append(entry)
        entries = entries[-50:]  # 滾動保留最近 50 session
        tmp = OUTCOME_STATS_PATH.with_suffix(".tmp")
        tmp.write_text(
            "\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n",
            encoding="utf-8",
        )
        tmp.replace(OUTCOME_STATS_PATH)

        if _unknown_streak(entries, threshold, window):
            recent = ", ".join(
                f"{round(float(e.get('ratio', 0)) * 100)}%" for e in entries[-window:]
            )
            return (
                f"[Guardian:OutcomeWatch] 效用歸因 outcome=unknown 比率連續 "
                f"{window} session 偏高（{recent}，門檻 {round(threshold * 100)}%）。"
                f"α/β 晉升軌可能靜默停滯——常見根因：完成宣告 regex "
                f"（forbidden-phrases.json completion_claim）與目前模型的完成語慣用寫法失配。"
                f"請抽查近期 session 終版訊息比對 claims_completion 是否漏判。"
            )
        return None
    except Exception:
        return None



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
    """Scan recent episodic atoms for repeated 覆轍信號."""
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

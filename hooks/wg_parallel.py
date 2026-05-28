"""wg_parallel.py — Parallel Agent Suggestion detector.

UPS handler scans the prompt for signals that suggest the work could be split
across ≥2 sub-agents (Explore / Plan / general-purpose) for wall-clock speedup.
When score ≥ threshold and cooldown clear, returns a one-line nudge.

Three layers cooperate:
  - rules/core.md  → 原則（每 session 必載）
  - atom workflow-parallel-agents → 手冊（trigger 注入）
  - this module    → 即時 pattern 推播

Config (workflow/config.json `parallel_agents`):
  - enabled: bool
  - min_score: int (default 2)
  - cooldown_turns: int (default 3)
  - min_prompt_chars: int (default 15)
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


# 連接詞 — 暗示多個目標串聯
_CONNECTORS = [
    "、", "順便", "同時", "並且", "以及", "還有",
    "另外", "另一個", "另一塊", "再加上", "兼", "兼顧",
    " and ", " plus ", " also ", " as well as ",
]

# 批量／廣域 — 隱含對多個對象做同一件事
_BATCH_WORDS = [
    "全部", "所有", "整體", "全面", "批量", "每個",
    "逐一", "逐個", "一次處理", "通通", "都改", "都跑",
    "all of", "each of", "every ",
]

# 跨目標動詞 — 動詞本身就要看多處
_CROSS_VERBS = [
    "比較", "對照", "對拍", "對比",
    "審視", "盤點", "盤查", "稽核", "audit",
    "重構", "refactor", "梳理", "整理",
    "調查", "investigate", "exploration", "勘查",
]

# 數量詞 — 多目標的明示
_PLURAL_PATTERNS = [
    re.compile(r"[兩三四五六七八九]個"),
    re.compile(r"多個|幾個|數個"),
    re.compile(r"\b\d+\s*(?:個|files?|atoms?|hooks?|modules?)"),
    re.compile(r"\b(?:two|three|four|five|several|multiple)\s+\w+"),
]

# 路徑／檔名提及 — 多個 path → 多個目標
_PATH_RE = re.compile(
    r"(?:[a-zA-Z_][\w\-]*/)+[\w\-]+\.\w+"        # foo/bar.py
    r"|(?:[a-zA-Z_][\w\-]*\.){1,}[a-zA-Z_][\w\-]+"   # foo.bar.py
    r"|\[\[[\w\-]+\]\]"                            # [[atom-name]]
)

# 略過條件 — 不該推播的場景
_SKIP_PATTERNS = [
    re.compile(r"^\s*/\w+"),                 # 純 slash command
    re.compile(r"^\s*[ABCDE]\s*$", re.IGNORECASE),  # 選 A/B/C 之類短答
    re.compile(r"^\s*(?:好|是|對|否|不|yes|no|ok|確認|繼續)\s*[。!\.]?\s*$"),
]

# 純問句訊號（要解釋 / 諮詢，不是要動手做事）
_QUESTION_ONLY_PATTERNS = [
    re.compile(r"^(?:為什麼|為何|怎麼會|是什麼|什麼是|如何理解|可以解釋)"),
    re.compile(r"^(?:why|what is|how does|can you explain)\b", re.IGNORECASE),
]


def _count_matches(text: str, needles: List[str]) -> int:
    """字串匹配數（不重疊計次，每個 needle 只計 1 次以免單字爆量）。"""
    return sum(1 for n in needles if n in text)


def _count_regex_hits(text: str, patterns: List[re.Pattern]) -> int:
    return sum(1 for p in patterns if p.search(text))


def _count_paths(text: str) -> int:
    """獨立路徑/atom 名提及數。"""
    hits = _PATH_RE.findall(text)
    return len(set(hits))


def _is_skip(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    for p in _SKIP_PATTERNS:
        if p.match(stripped):
            return True
    return False


def _is_pure_question(text: str) -> bool:
    head = text.strip()[:30]
    return any(p.search(head) for p in _QUESTION_ONLY_PATTERNS)


def score_prompt(prompt: str) -> Tuple[int, List[str]]:
    """回傳 (score, hint_labels)。

    Scoring:
      - 連接詞    : +1 per type, cap 2
      - 批量詞    : +2 (任一命中)
      - 跨目標動詞 : +1 (任一命中)
      - 複數量詞   : +1 (任一命中)
      - 多檔提及   : +1 (path ≥ 2)
    """
    score = 0
    hints: List[str] = []

    conn_hits = _count_matches(prompt, _CONNECTORS)
    if conn_hits >= 1:
        delta = min(conn_hits, 2)
        score += delta
        hints.append(f"連接詞×{conn_hits}")

    if _count_matches(prompt, _BATCH_WORDS) >= 1:
        score += 2
        hints.append("批量詞")

    if _count_matches(prompt, _CROSS_VERBS) >= 1:
        score += 1
        hints.append("跨目標動詞")

    if _count_regex_hits(prompt, _PLURAL_PATTERNS) >= 1:
        score += 1
        hints.append("複數量詞")

    path_n = _count_paths(prompt)
    if path_n >= 2:
        score += 1
        hints.append(f"多檔×{path_n}")
    elif path_n == 1:
        # 單檔多段（重構 X 的 N 個函式）— 拆 agent 會寫衝突
        score -= 2
        hints.append("單檔-2")

    return max(score, 0), hints


def detect_parallel_opportunity(
    prompt: str, state: Dict[str, Any], config: Dict[str, Any]
) -> Optional[str]:
    """回傳要注入的 line，或 None。

    state["parallel_last_inject_turn"] 用於 cooldown；
    state["turn_count"] 不可信，故用 topic_tracker.prompt_count 為基準。
    """
    cfg = config.get("parallel_agents", {})
    if not cfg.get("enabled", True):
        return None

    min_chars = cfg.get("min_prompt_chars", 15)
    if len(prompt.strip()) < min_chars:
        return None
    if _is_skip(prompt):
        return None
    if _is_pure_question(prompt):
        return None

    min_score = cfg.get("min_score", 2)
    score, hints = score_prompt(prompt)
    if score < min_score:
        return None

    # Cooldown
    cooldown = cfg.get("cooldown_turns", 3)
    cur_turn = state.get("topic_tracker", {}).get("prompt_count", 0)
    last_inject = state.get("parallel_last_inject_turn", -10)
    if cur_turn - last_inject < cooldown:
        return None

    state["parallel_last_inject_turn"] = cur_turn

    hint_str = ", ".join(hints) if hints else "多目標"
    return (
        f"[Parallel:Suggest] 此 prompt 含並行訊號 ({hint_str}, score={score})。"
        f"建議評估拆 ≥2 sub-agent 於同 message 一次 dispatch 加速；"
        f"判準/agent 挑選詳見 [[workflow-parallel-agents]]。"
        f"不適合拆請在回應裡說明原因。"
    )

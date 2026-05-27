#!/usr/bin/env python3
"""
wg_user_extract.py — L0 Rule-based User Decision Detector (V4.1 P1)

Pure regex + dict lookup. No I/O, no heavy imports. Target: ≤5ms.

Exposed API:
    detect_signal(prompt: str) -> dict
        {"signal": bool, "score": float, "matched": ["keyword1", "pattern2"]}
"""

import re
from typing import Dict, List, Tuple

# ─── Signal keyword tables (Chinese + English) ────────────────────────────────

_STRONG: List[Tuple[str, float]] = [
    # Chinese
    ("記住", 1.0), ("永遠", 1.0), ("從此", 1.0), ("以後都要", 1.0),
    ("禁止", 1.0), ("一律", 1.0), ("統一", 1.0), ("決定", 1.0),
    ("規定", 1.0), ("約定", 1.0),
    # English
    ("remember", 1.0), ("always", 1.0), ("never", 1.0),
    ("from now on", 1.0), ("must", 1.0),
]

_MEDIUM: List[Tuple[str, float]] = [
    # Chinese
    ("改用", 0.6), ("不要再", 0.6), ("下次", 0.6), ("固定", 0.6),
    ("偏好", 0.6), ("我要", 0.6), ("我不要", 0.6),
    # English
    ("prefer", 0.6), ("switch to", 0.6), ("stop using", 0.6),
]

_NEGATIVE: List[Tuple[str, float]] = [
    # Chinese
    ("也許", -0.8), ("可能", -0.8), ("試試", -0.8), ("好不好", -0.8),
    # English
    ("maybe", -0.8), ("perhaps", -0.8), ("might", -0.8),
]

# Precompute lowercase lookup
_ALL_KEYWORDS: List[Tuple[str, float]] = _STRONG + _MEDIUM + _NEGATIVE

# ─── Syntax patterns [F27] ─────────────────────────────────────────────────────

# [我/我們] + [情態詞] + V + O
_SYNTAX_MODAL = re.compile(
    r"[我我們](?:以後|之後|未來)?"
    r"(?:要|會|得|該|必須|應該|都要|一定要|不要|不再|別再)"
    r".{2,30}",
)

# [都/一律/固定/統一] + V
_SYNTAX_UNIFORM = re.compile(
    r"(?:都|一律|固定|統一|全部)"
    r"(?:用|改|換|採用|寫|設|跑|走|使用|改成)"
    r".{1,30}",
)

# Negation [不/禁/別/勿/停] + V
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

# ─── Exclusion patterns ────────────────────────────────────────────────────────

# Question ending
_QUESTION_END = re.compile(r"[?？]$|嗎\s*$|呢\s*$")

# Code block ratio check
_CODE_FENCE = re.compile(r"^```", re.MULTILINE)
_CODE_INDENT = re.compile(r"^    \S", re.MULTILINE)


def _is_mostly_code(text: str) -> bool:
    """Return True if >80% of lines look like code blocks."""
    lines = text.split("\n")
    if not lines:
        return False
    fence_count = len(_CODE_FENCE.findall(text))
    if fence_count >= 2:
        # Has code fences — check ratio of lines inside fences
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
    """Exclusion rules: question ending, too short/long, mostly code."""
    stripped = prompt.strip()
    if len(stripped) < 8 or len(stripped) > 500:
        return True
    if _QUESTION_END.search(stripped):
        return True
    if _is_mostly_code(stripped):
        return True
    return False


# ─── Main detector ──────────────────────────────────────────────────────────────

_SIGNAL_THRESHOLD = 0.4


def detect_signal(prompt: str) -> Dict:
    """Detect user decision/preference signals in prompt text.

    Returns:
        {"signal": bool, "score": float, "matched": ["keyword1", "pattern2"]}
    """
    if _should_skip(prompt):
        return {"signal": False, "score": 0.0, "matched": []}

    prompt_lower = prompt.lower()
    score = 0.0
    matched: List[str] = []

    # Keyword matching
    for keyword, weight in _ALL_KEYWORDS:
        if keyword in prompt_lower:
            score += weight
            matched.append(keyword)

    # Syntax pattern matching
    for pattern, name, weight in _SYNTAX_PATTERNS:
        if pattern.search(prompt):
            score += weight
            matched.append(name)

    signal = score >= _SIGNAL_THRESHOLD
    return {"signal": signal, "score": round(score, 2), "matched": matched}

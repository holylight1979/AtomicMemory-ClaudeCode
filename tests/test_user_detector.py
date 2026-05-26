#!/usr/bin/env python3
"""
test_user_detector.py — Unit tests for L0 rule-based detector (V4.1 P1)

Acceptance red lines: Precision >= 0.95, Recall >= 0.55
"""

import sys
import time
from pathlib import Path

import pytest

# Ensure hooks/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))

from wg_extraction import detect_signal

# ─── Positive examples (should signal=True) ─────────────────────────────────

POSITIVE_CASES = [
    # Strong Chinese keywords
    ("記住，以後 commit message 都用英文", "記住"),
    ("永遠不要在 production 上跑 migrate", "永遠"),
    ("從此所有 API endpoint 用 snake_case", "從此"),
    ("以後都要先寫 test 再寫 code", "以後都要"),
    ("禁止在 main branch 直接 push", "禁止"),
    ("一律使用 TypeScript 不用 JavaScript", "一律"),
    ("統一用 pnpm 不要再用 npm 了", "統一"),
    ("決定了，我們用 PostgreSQL 不用 MySQL", "決定"),
    ("規定每個 PR 至少要有一個 reviewer", "規定"),
    ("約定好了，deploy 前一定要跑 lint", "約定"),
    # Strong English keywords
    ("Remember to always add type hints to Python functions", "remember"),
    ("Always use async/await instead of callbacks", "always"),
    ("Never commit .env files to the repository", "never"),
    ("From now on we use ESLint instead of TSLint", "from now on"),
    ("You must run pytest before pushing any changes", "must"),
    # Medium Chinese keywords
    ("改用 Vite 取代 Webpack 當 bundler", "改用"),
    ("不要再用 var 了，全部改 const/let", "不要再"),
    ("下次部署要先確認 migration 有跑完", "下次"),
    ("固定用 4 空格縮排", "固定"),
    ("我偏好用 dark theme", "偏好"),
    ("我要所有 log 都走 structured logging", "我要"),
    ("我不要看到 console.log 出現在 production code", "我不要"),
    # Medium English keywords
    ("I prefer tabs over spaces for indentation", "prefer"),
    ("Switch to using pnpm instead of yarn", "switch to"),
    # Syntax patterns
    ("我以後要用 black formatter 來格式化 Python", "syntax:modal"),
    ("我們必須在每個 endpoint 加 rate limiting", "syntax:modal"),
    ("一律用 camelCase 命名變數", "syntax:uniform"),
    ("統一採用 REST 不用 GraphQL", "syntax:uniform"),
    ("不要用 any type，禁止出現 any", "syntax:negate"),
    ("別再用 jQuery 了，改用 vanilla JS", "syntax:negate"),
]

# ─── Negative examples (should signal=False) ─────────────────────────────────

NEGATIVE_CASES = [
    # Questions (ending with ?)
    "要不要改用 Redis 做 cache？",
    "你覺得我們應該用 TypeScript 嗎？",
    "Maybe we should switch to GraphQL?",
    "我們是不是該用 Docker 呢？",
    "What do you think about using Rust?",
    # Emotional / opinion without decision
    "今天 debug 好累喔",
    "這個 bug 真的很煩",
    "I'm so frustrated with this error",
    "寫得不錯，繼續保持",
    "This code looks clean, nice work",
    # Short sentences (< 8 chars)
    "好的",
    "OK",
    "知道了",
    "收到",
    "Yes",
    # Long text (> 500 chars) - simulated
    "x" * 501,
    # Code blocks (>80% code)
    "```python\ndef hello():\n    print('world')\n    return 42\n\nclass Foo:\n    pass\n```",
    "    def foo():\n        pass\n    def bar():\n        pass\n    def baz():\n        pass\n    def qux():\n        pass\n    def quux():\n        pass",
    # English chitchat
    "Can you help me debug this function please",
    "Let me show you the error I'm getting",
    "Here's the traceback from the server logs",
    "I just pushed the latest changes to the branch",
    "The CI pipeline is running right now",
    # General statements without decision signal
    "這個 function 是用來處理 user authentication 的",
    "目前的架構分成三層：controller, service, repository",
    "上次的 meeting 我們討論了 database schema",
    "今天要處理的 ticket 有五個",
    "這個 API 回傳 JSON 格式的資料",
]

# ─── Edge cases (ambiguous — expected behavior documented) ────────────────────

EDGE_CASES = [
    # "這次先用 X" — temporary, should NOT trigger (no strong keyword)
    ("這次先用 mock 測試就好", False),
    # "也行" — agreement but no decision signal
    ("也行，你看著辦", False),
    # "就這樣" — closure but no actionable decision
    ("就這樣吧，先這樣", False),
    # "好不好" — question/negotiation → negative keyword
    ("我們用 Redis 好不好", False),
    # Contains "maybe" → negative
    ("Maybe we could try using GraphQL later", False),
    # "也許" + "改用" → mixed, negative should suppress
    ("也許可以改用 Vite 試試看", False),
    # Strong + question ending → skip (question exclusion wins)
    ("以後都要用 TypeScript 嗎？", False),
    # "決定" in narrative context (should still trigger — keyword present)
    ("我決定這個專案用 monorepo 架構來管理", True),
    # English strong + medium combined → high score
    ("From now on, always prefer functional components over class components", True),
    # Negation syntax hit
    ("不要用 eval，禁止在任何地方使用 eval", True),
    # "試試" alone → negative
    ("試試看能不能用 WebSocket 連線", False),
    # "可能" → negative
    ("可能之後會改用 Go 重寫這個 service", False),
]


# ─── Test functions ──────────────────────────────────────────────────────────


class TestPositiveCases:
    """Positive examples: all should have signal=True."""

    @pytest.mark.parametrize(
        "prompt,expected_match",
        POSITIVE_CASES,
        ids=[f"pos_{i}" for i in range(len(POSITIVE_CASES))],
    )
    def test_positive(self, prompt, expected_match):
        result = detect_signal(prompt)
        assert result["signal"] is True, (
            f"Expected signal=True for: {prompt!r}\n"
            f"Got: score={result['score']}, matched={result['matched']}"
        )
        assert result["score"] >= 0.4
        assert len(result["matched"]) > 0


class TestNegativeCases:
    """Negative examples: all should have signal=False."""

    @pytest.mark.parametrize(
        "prompt",
        NEGATIVE_CASES,
        ids=[f"neg_{i}" for i in range(len(NEGATIVE_CASES))],
    )
    def test_negative(self, prompt):
        result = detect_signal(prompt)
        assert result["signal"] is False, (
            f"Expected signal=False for: {prompt!r}\n"
            f"Got: score={result['score']}, matched={result['matched']}"
        )


class TestEdgeCases:
    """Edge cases: ambiguous prompts with documented expected behavior."""

    @pytest.mark.parametrize(
        "prompt,expected_signal",
        EDGE_CASES,
        ids=[f"edge_{i}" for i in range(len(EDGE_CASES))],
    )
    def test_edge(self, prompt, expected_signal):
        result = detect_signal(prompt)
        assert result["signal"] is expected_signal, (
            f"Expected signal={expected_signal} for: {prompt!r}\n"
            f"Got: score={result['score']}, matched={result['matched']}"
        )


class TestPerformance:
    """L0 detector must complete in ≤5ms."""

    def test_latency_under_5ms(self):
        prompts = [p for p, _ in POSITIVE_CASES[:10]] + NEGATIVE_CASES[:10]
        times = []
        for p in prompts:
            start = time.perf_counter()
            detect_signal(p)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
        p95 = sorted(times)[int(len(times) * 0.95)]
        assert p95 <= 5.0, f"p95 latency {p95:.2f}ms exceeds 5ms limit"


class TestOutputSchema:
    """Output must conform to expected schema."""

    def test_schema_keys(self):
        result = detect_signal("記住這個規則：一律用 UTF-8")
        assert "signal" in result
        assert "score" in result
        assert "matched" in result
        assert isinstance(result["signal"], bool)
        assert isinstance(result["score"], float)
        assert isinstance(result["matched"], list)

    def test_empty_prompt(self):
        result = detect_signal("")
        assert result["signal"] is False
        assert result["score"] == 0.0
        assert result["matched"] == []


class TestPrecisionRecall:
    """Aggregate P/R check across all labeled examples."""

    def test_precision_recall(self):
        tp = fp = fn = tn = 0

        # Positive cases
        for prompt, _ in POSITIVE_CASES:
            r = detect_signal(prompt)
            if r["signal"]:
                tp += 1
            else:
                fn += 1

        # Negative cases
        for prompt in NEGATIVE_CASES:
            r = detect_signal(prompt)
            if r["signal"]:
                fp += 1
            else:
                tn += 1

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0

        assert precision >= 0.95, (
            f"Precision {precision:.3f} < 0.95 (tp={tp}, fp={fp})"
        )
        assert recall >= 0.55, (
            f"Recall {recall:.3f} < 0.55 (tp={tp}, fn={fn})"
        )

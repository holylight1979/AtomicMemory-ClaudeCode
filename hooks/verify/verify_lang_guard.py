"""verify_lang_guard.py — P8b 英文回應漂移攔截純函式守恆。

守住 lang_guard 三純函式不變式（政策 B：只管對話散文，剝 code/inline/URL）：
- strip_noncontent 剝除 fence / inline / URL / link 目標，保留 link text
- english_ratio 只計語言字元（英文字母 + CJK），分母 0 → (0.0, 0)
- should_remind：太短(min_lang_chars)不判、ratio>=threshold 才提醒

Design: plans/kind-marinating-lerdorf.md（P8b）。受控字串輸入，零磁碟依賴。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest  # noqa: F401

HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify/ → hooks/
CLAUDE = HOOKS_DIR.parent
for p in (str(HOOKS_DIR), str(CLAUDE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import lang_guard as LG  # noqa: E402

FENCE = "```"


# ─── strip_noncontent（政策 B）──────────────────────────────────────────────


def test_strip_removes_code_fence():
    text = f"中文說明開始。\n{FENCE}python\ndef foo():\n    return 'english code'\n{FENCE}\n中文說明結束。"
    out = LG.strip_noncontent(text)
    assert "def foo" not in out
    assert "english" not in out
    assert "中文說明開始" in out and "中文說明結束" in out


def test_strip_removes_inline_and_url_and_link_target():
    text = "見 `settings.json` 與 [config.json](workflow/config.json)，網址 https://example.com/path 都不算。"
    out = LG.strip_noncontent(text)
    assert "settings.json" not in out       # inline code 剝除
    assert "workflow/config.json" not in out  # link 目標剝除
    assert "example.com" not in out          # 裸 URL 剝除
    assert "config.json" in out              # link text 保留（user-facing）


def test_strip_empty():
    assert LG.strip_noncontent("") == ""


# ─── english_ratio ──────────────────────────────────────────────────────────


def test_ratio_pure_english():
    ratio, n = LG.english_ratio("hello world this is english")
    assert ratio == 1.0
    assert n == len("helloworldthisisenglish")


def test_ratio_pure_chinese():
    ratio, n = LG.english_ratio("這是一段純繁體中文")
    assert ratio == 0.0
    assert n == 9


def test_ratio_half():
    # 5 英文字母 + 5 CJK → 恰 0.5
    ratio, n = LG.english_ratio("abcde一二三四五")
    assert ratio == pytest.approx(0.5)
    assert n == 10


def test_ratio_denominator_zero():
    # 純標點/數字/空白 → 無語言字元 → (0.0, 0) 不炸
    ratio, n = LG.english_ratio("。！？ 123 !!! ")
    assert ratio == 0.0
    assert n == 0


def test_ratio_ignores_digits_and_punct():
    # 數字/標點不進分母：3 英文 + 2 CJK → 0.6
    ratio, n = LG.english_ratio("abc中文 123!!!")
    assert n == 5
    assert ratio == pytest.approx(3 / 5)


# ─── should_remind ──────────────────────────────────────────────────────────


def test_remind_pure_english_long():
    text = ("This is a completely English response about the implementation "
            "and it has fully drifted away from Traditional Chinese here.")
    need, ratio, n = LG.should_remind(text, threshold=0.5, min_lang_chars=40)
    assert need is True
    assert ratio == 1.0


def test_no_remind_pure_chinese():
    text = "這是一段完整的繁體中文回應，說明實作細節與後續步驟，語言完全正確沒有漂移。"
    need, _, _ = LG.should_remind(text, threshold=0.5, min_lang_chars=40)
    assert need is False


def test_no_remind_chinese_with_english_code_fence():
    # 政策 B 核心案例：散文中文、fence 內全英文碼 → 剝除後不提醒
    text = (
        f"這是一段中文說明，解釋程式如何運作與設計原理。\n{FENCE}python\n"
        f"def handle_stop(data):\n    return 'a very long english code block here'\n{FENCE}\n"
        "接著繼續用中文描述測試結果與後續步驟，確保語言字元夠長觸發判定。"
    )
    need, ratio, n = LG.should_remind(text, threshold=0.5, min_lang_chars=40)
    assert n >= 40           # 中文散文本身夠長，確實進入判定（非因太短跳過）
    assert need is False      # 英文碼被剝 → 佔比低 → 不提醒
    assert ratio < 0.5


def test_no_remind_chinese_with_inline_terms():
    text = ("在 `settings.json` 的 Stop 陣列新增條目，詳見 "
            "[config.json](workflow/config.json)，這段繁體中文說明夠長可觸發判定門檻。")
    need, _, _ = LG.should_remind(text, threshold=0.5, min_lang_chars=40)
    assert need is False


def test_no_remind_short_english():
    # "Done." 太短（< min_lang_chars）→ 不判、不誤報
    need, _, n = LG.should_remind("Done.", threshold=0.5, min_lang_chars=40)
    assert n < 40
    assert need is False


def test_threshold_boundary_inclusive():
    # ratio 恰 0.5：>= 門檻 → 提醒（min 設低以隔離門檻邏輯）
    need, ratio, _ = LG.should_remind("abcde一二三四五", threshold=0.5, min_lang_chars=1)
    assert ratio == pytest.approx(0.5)
    assert need is True


def test_threshold_boundary_above():
    # ratio 0.5 < 門檻 0.51 → 不提醒
    need, _, _ = LG.should_remind("abcde一二三四五", threshold=0.51, min_lang_chars=1)
    assert need is False

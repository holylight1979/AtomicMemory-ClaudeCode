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
    text = "見 `settings.json` 與 [config guide](workflow/config.json)，網址 https://example.com/path 都不算。"
    out = LG.strip_noncontent(text)
    assert "settings.json" not in out       # inline code 剝除
    assert "workflow/config.json" not in out  # link 目標剝除
    assert "example.com" not in out          # 裸 URL 剝除
    assert "config guide" in out             # link text 保留（user-facing；寫成檔名的 link text 照檔名剝）


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


# 第二波 A′ 實跑（guard-lang.jsonl:1）：中文材料報告裡沒包反引號的路徑、檔名、規則名、旗標被算成英文 59% → 誤要求重答
A1_REPORT = (
    "材料整理如下，全部取自本 session 實際紀錄。\n"
    "改了 pricing/api.py、pricing/rates.py、tests\\test_cli.py；C:\\w4\\qa2-pricing\\pricing\\cli.py 加 --plain 選項。\n"
    "跑 python -m pytest -q tests/test_cli.py 結果 10 passed；preserve-check.py --mutation side_effect 印 PRESERVE_CHECK PASS。\n"
    "被擋訊息依序是 OLD_TEST_CHANGE_NEEDS_DECLARATION、UNMAPPED_FIRST_EDIT_NEEDS_MIN_MAP，need_goal 的 verify_scope 拒收 no_case。\n"
    "暫存目錄 /tmp/qa2eq 已刪；api.quote 用法與 calc.total 算出的金額跟改前一樣。\n"
)


def test_strip_removes_bare_paths_filenames_identifiers_and_flags():
    out = LG.strip_noncontent(A1_REPORT)
    for gone in ("pricing/api.py", "test_cli.py", "qa2-pricing", "--plain", "--mutation", "side_effect", "PRESERVE_CHECK",
                 "OLD_TEST_CHANGE_NEEDS_DECLARATION", "need_goal", "/tmp/qa2eq", "api.quote", "preserve-check.py"):
        assert gone not in out
    assert "材料整理如下" in out and "python" in out and "passed" in out    # 中文散文與一般英文字照留


def test_no_remind_chinese_report_with_bare_paths_and_commands():
    raw_ratio, _ = LG.english_ratio(A1_REPORT)
    assert raw_ratio >= 0.5                  # 前置：不剝的話英文過門檻（這段沒有反引號，舊的剝法什麼都沒剝）
    need, ratio, n = LG.should_remind(A1_REPORT, threshold=0.5, min_lang_chars=40)
    assert n >= 40 and ratio < 0.5 and need is False


def test_remind_english_paragraph_even_with_paths():
    text = ("I refactored pricing/api.py and removed the service layer, then ran the whole test suite "
            "with --plain enabled; everything passed and the output format is unchanged for callers.")
    need, ratio, _ = LG.should_remind(text, threshold=0.5, min_lang_chars=40)
    assert need is True and ratio == 1.0     # 路徑與旗標剝掉，剩下的散文仍全是英文 → 照擋


def test_remind_english_with_slash_compounds():
    """Codex：input/output、error/recovery 這種英文斜線詞不是路徑，剝掉會讓整句真英文掉到 40 字以下而漏擋。"""
    text = "Please review input/output handling and error/recovery behavior."
    out = LG.strip_noncontent(text)
    assert "input/output" in out and "error/recovery" in out
    need, _, n = LG.should_remind(text, threshold=0.5, min_lang_chars=40)
    assert n >= 40 and need is True


def test_strip_long_ascii_run_stays_linear():
    """很長的連續英數字串（base64、雜湊）不能讓碼樣正規式每個位置重試：沒錨在字首時 2 萬字要 10 秒，Stop hook 會逾時。"""
    import time
    for blob in ("a" * 50000, "a." * 25000, "a_" * 25000, "a/" * 25000):
        t = time.perf_counter()
        LG.strip_noncontent(f"中文說明 {blob} 結尾")
        assert time.perf_counter() - t < 1.0, blob[:4]


def test_strip_keeps_prose_words_around_sentence_periods():
    out = LG.strip_noncontent("Done. Next step is a well-known review.")
    assert all(w in out for w in ("Done", "Next", "well-known", "review"))   # 句點後有空格、連字號詞都不是檔名或旗標


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


# ─── handle_stop 輸出契約（模型讀得到 + 防迴圈）────────────────────────────

_EN = "This is a long english sentence that clearly exceeds the minimum language chars. " * 2
_CFG = {"english_ratio_threshold": 0.5, "min_lang_chars": 40}


def _run_stop(data, capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(LG, "TRIGGER_LOG_PATH", tmp_path / "guard-lang.jsonl")
    with pytest.raises(SystemExit) as ex:
        LG.handle_stop(data, _CFG)
    assert ex.value.code == 0
    return capsys.readouterr().out.strip()


def test_handle_stop_emits_additional_context_not_system_message(capsys, monkeypatch, tmp_path):
    # 模型只讀 hookSpecificOutput.additionalContext；systemMessage 只給使用者看
    import json
    out = _run_stop({"last_assistant_message": _EN}, capsys, monkeypatch, tmp_path)
    obj = json.loads(out)
    assert "systemMessage" not in obj
    hso = obj["hookSpecificOutput"]
    assert hso["hookEventName"] == "Stop"
    assert "[語言守衛]" in hso["additionalContext"]


def test_handle_stop_silent_when_stop_hook_active(capsys, monkeypatch, tmp_path):
    # Stop 續跑回合不再觸發 → 最多提醒一次、不迴圈
    out = _run_stop(
        {"last_assistant_message": _EN, "stop_hook_active": True}, capsys, monkeypatch, tmp_path
    )
    assert out == ""


def test_handle_stop_silent_for_chinese(capsys, monkeypatch, tmp_path):
    out = _run_stop({"last_assistant_message": "這是一段足夠長的繁體中文回應，" * 5}, capsys, monkeypatch, tmp_path)
    assert out == ""

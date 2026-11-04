"""hook 輸出字元上限（規則 HOOK_TEXT_CAP_SELF_TRUNCATE）。

官方：additionalContext／systemMessage／stdout 單一字串超過 10,000 字元會被換成「路徑＋2KB 預覽」且模型不會去讀。
驗：超過上限自己截在 9,000 內、尾行指到溢出全文檔、檔內容是原文、guard log 有一筆；沒超過原樣不動。
跑法：python -m pytest hooks/verify/verify_hook_text_cap.py -q
"""
import json
import os
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS))
os.environ.setdefault("PYTEST_CURRENT_TEST", "verify_hook_text_cap")
import wg_core  # noqa: E402


def test_short_text_untouched():
    assert wg_core.cap_hook_text("abc", "t") == "abc"
    d = {"hookSpecificOutput": {"hookEventName": "X", "additionalContext": "ok"}}
    assert wg_core.cap_hook_output(d)["hookSpecificOutput"]["additionalContext"] == "ok"


def test_long_text_truncated_with_pointer(tmp_path, monkeypatch):
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", tmp_path)
    monkeypatch.setattr(wg_core, "GUARD_LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(wg_core, "logs_dir", lambda: tmp_path / "logs")
    big = "\n".join(f"line {i} " + "x" * 60 for i in range(300))   # 約 2 萬字元
    assert len(big) > 10000
    out = wg_core.cap_hook_text(big, "unit")
    assert len(out) <= wg_core.HOOK_TEXT_CAP
    assert "[Guardian:Truncated]" in out and "hook-overflow" in out
    files = list((tmp_path / "hook-overflow").glob("unit-*.txt"))
    assert len(files) == 1 and files[0].read_text(encoding="utf-8") == big
    log = (tmp_path / "logs" / "guard-hook-text-cap.jsonl").read_text(encoding="utf-8").strip().splitlines()
    rec = json.loads(log[-1])
    assert rec["chars"] == len(big) and rec["where"] == "unit"


def test_cap_hook_output_covers_system_message(tmp_path, monkeypatch):
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", tmp_path)
    monkeypatch.setattr(wg_core, "logs_dir", lambda: tmp_path / "logs")
    d = {"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": "y" * 12000}, "systemMessage": "z" * 11000}
    wg_core.cap_hook_output(d)
    assert len(d["hookSpecificOutput"]["additionalContext"]) <= wg_core.HOOK_TEXT_CAP
    assert len(d["systemMessage"]) <= wg_core.HOOK_TEXT_CAP


if __name__ == "__main__":
    import pytest
    rc = pytest.main([__file__, "-q"])
    print("HOOK_TEXT_CAP_CHECK PASS" if rc == 0 else "HOOK_TEXT_CAP_CHECK FAIL")
    sys.exit(0 if rc == 0 else 1)

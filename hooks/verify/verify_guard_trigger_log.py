"""verify_guard_trigger_log.py — 護欄觸發 JSONL log（誤攔率可觀測）。

驗證：
  - wg_core.append_guard_log：每護欄獨立檔 Logs/guard-<name>.jsonl、含 at 時間戳、
    多筆 append、fail-open（目錄不可建不炸）。
  - lang_guard._append_trigger_log：standalone 自含版同樣行為。

對應：hooks/wg_core.py（append_guard_log）、hooks/lang_guard.py（_append_trigger_log）、
     觸發點 handlers/stop.py（evasion）/ wg_docdrift.py（drift）/ lang_guard.py。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify/ → hooks/
sys.path.insert(0, str(HOOKS_DIR))

import wg_core  # noqa: E402
import lang_guard  # noqa: E402


def test_append_guard_log_writes_jsonl(tmp_path, monkeypatch):
    """一筆觸發 → guard-<name>.jsonl 一行合法 JSON，含 at + payload。"""
    monkeypatch.setattr(wg_core, "GUARD_LOG_DIR", tmp_path)
    wg_core.append_guard_log("evasion", {"phrase": "先跳過", "session_id": "s1"})
    p = tmp_path / "guard-evasion.jsonl"
    assert p.exists()
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["phrase"] == "先跳過"
    assert rows[0]["at"]  # 時間戳必填


def test_append_guard_log_accumulates(tmp_path, monkeypatch):
    """多筆觸發累積多行（計數可統計）。"""
    monkeypatch.setattr(wg_core, "GUARD_LOG_DIR", tmp_path)
    for i in range(3):
        wg_core.append_guard_log("docdrift", {"source": f"f{i}.py", "doc": "A.md"})
    rows = (tmp_path / "guard-docdrift.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 3


def test_append_guard_log_fail_open(tmp_path, monkeypatch):
    """GUARD_LOG_DIR 指向既存檔案（mkdir 必炸）→ 不 raise（fail-open）。"""
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setattr(wg_core, "GUARD_LOG_DIR", blocker)
    wg_core.append_guard_log("evasion", {"phrase": "x"})  # 不炸即過


def test_lang_guard_trigger_log(tmp_path, monkeypatch):
    """lang_guard standalone 版：寫入 + 合法 JSONL + at。"""
    log = tmp_path / "guard-lang.jsonl"
    monkeypatch.setattr(lang_guard, "TRIGGER_LOG_PATH", log)
    lang_guard._append_trigger_log({"session_id": "s1", "ratio": 0.8, "lang_chars": 100})
    rows = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["ratio"] == 0.8
    assert rows[0]["at"]


def test_lang_guard_trigger_log_fail_open(tmp_path, monkeypatch):
    """父目錄為既存檔案 → 不 raise。"""
    blocker = tmp_path / "blocked"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setattr(lang_guard, "TRIGGER_LOG_PATH", blocker / "guard-lang.jsonl")
    lang_guard._append_trigger_log({"ratio": 0.9})  # 不炸即過

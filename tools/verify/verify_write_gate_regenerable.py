"""verify_write_gate_regenerable.py — write-gate「可再生內容」判準只出警告、不動分數與動作.

守住規則：能從最終程式碼／測試／既有文件直接讀出的內容（檔案索引、CLI 參數逐項、
簽名清單、整段程式碼）命中時，evaluate() 在 add/ask 結果附 warnings 與
regenerable_signals；quality_score 與 action 與未加判準前完全相同（不改評分公式）。
一般結論型知識不得誤命中。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

CLAUDE_DIR = Path(__file__).resolve().parent.parent.parent  # tools/verify/ → ~/.claude/
SPEC = importlib.util.spec_from_file_location(
    "memory_write_gate_regen", CLAUDE_DIR / "tools" / "memory-write-gate.py"
)
WG = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WG)

CONFIG = {
    "enabled": True,
    "auto_threshold": 0.5,
    "ask_threshold": 0.3,
    "dedup_score": 0.80,
    "skip_on_explicit_user": True,
    "knowledge_budget_bytes": 0,
}

FILE_INDEX = "\n".join([
    "# MapServer 文件索引",
    "- `Handlers/LoginHandler.cs` — 登入封包處理",
    "- `Handlers/MoveHandler.cs` — 移動同步",
    "- `Core/Session.cs` — 連線生命週期",
    "- `Core/Dispatcher.cs` — 封包分派表",
])

OPTION_LIST = "\n".join([
    "memory-audit.py 參數：",
    "- `--enforce`：自動淘汰",
    "- `--dry-run`：只列候選",
    "- `--json`：JSON 輸出",
    "- `--project-dir`：專案層",
])

CODE_DUMP = "```python\n" + "\n".join(f"x{i} = {i}" for i in range(10)) + "\n```"

CONCLUSION = (
    "PostToolUse 的 tool_response 不等於模型看到的結果：Edit 帶整份 originalFile，"
    "量 context 浪費時要按工具取可見欄位，否則會高估 3 倍以上。"
)


def _no_dedup(monkeypatch):
    monkeypatch.setattr(WG, "check_dedup", lambda content, config, layers=None: None)
    monkeypatch.setattr(WG, "write_audit_log", lambda *a, **k: None)


def test_signals_hit_file_index():
    sig = WG.regenerable_signals(FILE_INDEX)
    assert any(s.startswith("file_listing") for s in sig)
    assert "index_title" in sig


def test_signals_hit_option_list_and_code_dump():
    assert any(s.startswith("option_listing") for s in WG.regenerable_signals(OPTION_LIST))
    assert any(s.startswith("code_dump_") for s in WG.regenerable_signals(CODE_DUMP))


def test_signals_silent_on_conclusion():
    assert WG.regenerable_signals(CONCLUSION) == []
    assert WG.regenerable_signals("見 `tools/memory-audit.py` 一行錨點就夠") == []


def test_evaluate_attaches_warning_without_changing_score(monkeypatch):
    _no_dedup(monkeypatch)
    res = WG.evaluate(FILE_INDEX, config=CONFIG)
    score, reasons = WG.compute_quality_score(FILE_INDEX)
    assert res["action"] in ("add", "ask")
    assert res["quality_score"] == round(score, 2)  # 分數公式未變
    assert res["regenerable_signals"]
    assert any("可再生內容疑似" in w for w in res.get("warnings", []))


def test_evaluate_pitfall_fast_path_also_warns(monkeypatch):
    _no_dedup(monkeypatch)
    res = WG.evaluate("這是一個坑：\n" + FILE_INDEX, config=CONFIG)
    assert res["action"] == "add" and res["quality_score"] == 0.7  # pitfall 捷徑不變
    assert any("可再生內容疑似" in w for w in res["warnings"])


def test_evaluate_conclusion_has_no_regen_warning(monkeypatch):
    _no_dedup(monkeypatch)
    res = WG.evaluate(CONCLUSION, config=CONFIG)
    assert "regenerable_signals" not in res
    assert not any("可再生內容疑似" in w for w in res.get("warnings", []))

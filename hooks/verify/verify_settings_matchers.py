"""verify_settings_matchers.py：B0：PostToolUse 的 guardian matcher 要含 PowerShell 與 Read（否則帳本只收 Bash、on_read 只有 Bash 觸發）。

怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_settings_matchers.py
第一案用 fixture 字串驗判定邏輯；第二案讀真檔 settings.json：settings.json 由總控台改（共用檔），
改完前第二案是紅的（刻意：紅燈就是「matcher 還沒加」的訊號）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = ("Bash", "PowerShell", "Read", "Edit", "Write", "MultiEdit")


def guardian_post_tool_matcher(settings_text: str) -> str:
    """settings.json 文字 → PostToolUse 裡呼叫 workflow-guardian.py 那條 hook 的 matcher；沒有回 ""。"""
    data = json.loads(settings_text)
    for entry in (data.get("hooks") or {}).get("PostToolUse") or []:
        for h in entry.get("hooks") or []:
            if "workflow-guardian.py" in str(h.get("command", "")):
                return str(entry.get("matcher", ""))
    return ""


def missing_tools(matcher: str) -> list:
    have = set(matcher.split("|"))
    return [t for t in REQUIRED if t not in have]


FIXTURE_OK = json.dumps({"hooks": {"PostToolUse": [
    {"matcher": "Edit|Write|MultiEdit|NotebookEdit|ExitPlanMode|Bash|PowerShell|Read|Agent|Task",
     "hooks": [{"type": "command", "command": "pythonw.exe -c \"…workflow-guardian.py…\""}]},
    {"matcher": "Edit|Write|Bash", "hooks": [{"type": "command", "command": "codex_companion.py"}]},
]}})
FIXTURE_OLD = json.dumps({"hooks": {"PostToolUse": [
    {"matcher": "Edit|Write|MultiEdit|NotebookEdit|ExitPlanMode|Bash|Agent|Task",
     "hooks": [{"type": "command", "command": "pythonw.exe -c \"…workflow-guardian.py…\""}]},
]}})


def test_fixture_matcher_logic():
    assert missing_tools(guardian_post_tool_matcher(FIXTURE_OK)) == []
    assert missing_tools(guardian_post_tool_matcher(FIXTURE_OLD)) == ["PowerShell", "Read"]
    assert guardian_post_tool_matcher('{"hooks": {}}') == ""


def test_real_settings_json_matcher_has_powershell_and_read():
    """真檔：總控台在 settings.json:124 加 `PowerShell|Read` 前此案紅（預期）。"""
    text = (ROOT / "settings.json").read_text(encoding="utf-8")
    matcher = guardian_post_tool_matcher(text)
    assert matcher, "settings.json 找不到 PostToolUse 的 workflow-guardian hook"
    assert missing_tools(matcher) == [], f"PostToolUse guardian matcher 缺 {missing_tools(matcher)}：{matcher}"

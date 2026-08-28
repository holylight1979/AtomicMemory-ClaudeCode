"""verify_followup_check.py — 回訪檢查器（tools/followup-check.py）。

覆蓋：到期判定、INSUFFICIENT（樣本不足不標 last_shown）、PASS 自動結案、FAIL 保留、
首次整份 handoff / 之後精簡、--done 結案。全部在 tmp_path 內，不碰真登記表與真 log。
"""
from __future__ import annotations

import importlib.util
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("followup_check", TOOLS / "followup-check.py")
fc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fc)  # type: ignore[union-attr]


def _iso(d: date) -> str:
    return d.isoformat()


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(fc, "FOLLOWUPS", tmp_path / "followups.json")
    monkeypatch.setattr(fc, "INJECTION_TURNS_LOG", tmp_path / "injection-turns.jsonl")
    monkeypatch.setattr(fc, "ATOM_DEBUG_GLOB", str(tmp_path / "atom-debug-*.log"))
    # 報表模組不可用 → 該列標 n/a 且視為通過（報表壞掉不擋回訪）
    monkeypatch.setattr(fc, "CLAUDE_DIR", tmp_path)
    return tmp_path


def _item(due_offset=-1, **crit):
    today = date.today()
    return {
        "id": "t1", "title": "T", "check": "injection-budget",
        "since": _iso(today - timedelta(days=7)), "due": _iso(today + timedelta(days=due_offset)),
        "criteria": {"min_turns": 3, "full_per_turn_min": 2.5, "full_rate_min": 0.55,
                     "dropped_per_turn_max": 1.0, "exposure_tax_max": 0, **crit},
        "handoff": {"這是什麼": "x", "怎麼判": ["a", "b"]},
        "done": False, "last_shown": "", "result": "",
    }


def _write_turns(path: Path, rows):
    today = date.today().isoformat()
    path.write_text("\n".join(json.dumps({"at": f"{today}T10:00:00+08:00", **r}) for r in rows) + "\n",
                    encoding="utf-8")


def test_is_due_and_not_due():
    assert fc.is_due(_item(due_offset=-1)) is True
    assert fc.is_due(_item(due_offset=+1)) is False
    d = _item(due_offset=-1); d["done"] = True
    assert fc.is_due(d) is False


def test_insufficient_sample_does_not_mark_shown(sandbox):
    fc.save({"followups": [_item()]})
    _write_turns(sandbox / "injection-turns.jsonl", [{"ok": 3, "fallback": 0, "skip": 0}])
    lines, fails = fc.run_all(auto_close=True, brief=True, mark_shown=True)
    assert lines and "樣本不足" in lines[0] and fails == 0
    saved = fc.load()["followups"][0]
    assert saved["done"] is False and saved["last_shown"] == ""


def test_pass_auto_closes_and_first_show_has_handoff(sandbox):
    fc.save({"followups": [_item()]})
    _write_turns(sandbox / "injection-turns.jsonl",
                 [{"ok": 3, "fallback": 0, "skip": 1}] * 4)
    lines, fails = fc.run_all(auto_close=True, brief=True, mark_shown=True)
    assert fails == 0
    assert "交接（假設接手者對本題零記憶）" in lines[0]
    assert "【這是什麼】x" in lines[0] and "- a" in lines[0]
    assert "已自動結案" in lines[0]
    saved = fc.load()["followups"][0]
    assert saved["done"] is True and saved["last_shown"] == date.today().isoformat()


def test_fail_keeps_open_and_second_day_is_brief(sandbox):
    fc.save({"followups": [_item()]})
    _write_turns(sandbox / "injection-turns.jsonl",
                 [{"ok": 1, "fallback": 2, "skip": 2}] * 4)  # 1.0/回合、20% → FAIL
    lines, fails = fc.run_all(auto_close=True, brief=True, mark_shown=True)
    assert fails == 1 and "❌ 全文/回合" in lines[0] and "交接" in lines[0]
    saved = fc.load()["followups"][0]
    assert saved["done"] is False
    # 同日再跑（mark_shown）→ 今日已提醒，不重複
    lines2, _ = fc.run_all(auto_close=True, brief=True, mark_shown=True)
    assert lines2 == []
    # 改成昨天提醒過 → 精簡版（無交接區）
    data = fc.load(); data["followups"][0]["last_shown"] = _iso(date.today() - timedelta(days=1)); fc.save(data)
    lines3, _ = fc.run_all(auto_close=True, brief=True, mark_shown=True)
    assert lines3 and "交接" not in lines3[0] and "❌" in lines3[0]


def test_not_due_is_silent_unless_forced(sandbox):
    fc.save({"followups": [_item(due_offset=+3)]})
    _write_turns(sandbox / "injection-turns.jsonl", [{"ok": 3, "fallback": 0, "skip": 0}] * 4)
    assert fc.run_all(brief=True)[0] == []
    assert fc.run_all(brief=True, force=True)[0] != []


def test_dropped_counter_reads_debug_logs(sandbox):
    today = date.today().isoformat()
    (sandbox / f"atom-debug-{today}_10.log").write_text(
        "x final-trim atom=a form=dropped\ny final-trim atom=b form=pointer\nz final-trim atom=c form=dropped\n",
        encoding="utf-8")
    assert fc._count_dropped_since(date.today() - timedelta(days=1)) == 2

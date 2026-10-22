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
    # 報表模組不可用 → 該列標 n/a 且視為通過（報表壞掉不擋回訪）。報表從程式碼樹載入、讀的是資料根，
    # 兩個都指 tmp，否則會載到真的報表、讀到真家的曝光資料
    monkeypatch.setattr(fc, "CLAUDE_DIR", tmp_path)
    monkeypatch.setattr(fc, "CODE_DIR", tmp_path)
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


def _saved() -> dict:
    """登記項疊上本機執行期紀錄（結果、提醒日、自動結案寫在 followups.local.json，登記表不動）。"""
    return fc.merged(fc.load()["followups"][0], fc.load_runtime())


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
    saved = _saved()
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
    saved = _saved()
    assert saved["done"] is True and saved["last_shown"] == date.today().isoformat()


def test_fail_keeps_open_and_second_day_is_brief(sandbox):
    fc.save({"followups": [_item()]})
    _write_turns(sandbox / "injection-turns.jsonl",
                 [{"ok": 1, "fallback": 2, "skip": 2}] * 4)  # 1.0/回合、20% → FAIL
    lines, fails = fc.run_all(auto_close=True, brief=True, mark_shown=True)
    assert fails == 1 and "❌ 全文/回合" in lines[0] and "交接" in lines[0]
    saved = _saved()
    assert saved["done"] is False
    # 同日再跑（mark_shown）→ 今日已提醒，不重複
    lines2, _ = fc.run_all(auto_close=True, brief=True, mark_shown=True)
    assert lines2 == []
    # 改成昨天提醒過 → 精簡版（無交接區）
    rt = fc.load_runtime(); rt["t1"]["last_shown"] = _iso(date.today() - timedelta(days=1)); fc.save_runtime(rt)
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


# ─── closing-gates：收尾擋下次數回訪（讀根層專案的對話紀錄） ─────────────────

_SINCE = "2026-10-20T03:00:00"


def _rec(kind, ts, **kw):
    if kind == "user":
        return {"type": "user", "timestamp": ts, "message": {"role": "user", "content": kw["text"]}}
    if kind == "block":
        return {"type": "attachment", "timestamp": ts, "attachment": {
            "type": "hook_blocking_error", "hookEvent": "Stop", "blockingError": {"blockingError": kw["text"]}}}
    return {"type": "assistant", "timestamp": ts, "message": {"content": [
        {"type": "tool_use", "id": kw["id"], "name": "Bash", "input": {"command": kw["cmd"]}}]}}


def _closing_sandbox(sandbox, monkeypatch, records, folder="c--users-me--claude"):
    proj = sandbox / "projects"
    d = proj / folder
    d.mkdir(parents=True)
    (d / "s1.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")
    monkeypatch.setattr(fc, "PROJECTS_DIR", proj)
    monkeypatch.setattr(fc, "ROOT_PROJECT_PREFIX", "c--users-me--claude")


def _closing_item(**crit):
    it = _item()
    it.update(check="closing-gates", criteria={"since_utc": _SINCE, "min_turns": 2, "blocks_per_turn_max": 0.4,
                                               "reruns_per_turn_max": 0.5, **crit})
    return it


def test_closing_gates_counts_turns_blocks_and_reruns(sandbox, monkeypatch):
    """回合＝真的使用者文字（Stop hook feedback、只有系統標籤的不算）；擋下按 Stop 的 hook_blocking_error 算、同時間同內容只算一次；
    擋下之後到下一回合之間跑的 pytest／run_verify 才算重跑；since 之前的不算。"""
    recs = [
        _rec("user", "2026-10-19T01:00:00Z", text="舊的一回合"),
        _rec("block", "2026-10-19T01:01:00Z", text="[Guardian:VerifyScope] 舊擋"),
        _rec("user", "2026-10-20T04:00:00Z", text="修一下"),
        _rec("block", "2026-10-20T04:05:00Z", text="[Guardian:ReconcileGate] ✗ (a) x"),
        _rec("block", "2026-10-20T04:05:00Z", text="[Guardian:ReconcileGate] ✗ (a) x"),
        _rec("tool", "2026-10-20T04:06:00Z", id="t1", cmd="python -m pytest hooks/verify/verify_x.py"),
        _rec("user", "2026-10-20T04:10:00Z", text="Stop hook feedback: blah"),
        _rec("user", "2026-10-20T05:00:00Z", text="<system-reminder>only noise</system-reminder>"),
        _rec("user", "2026-10-20T06:00:00Z", text="再一題"),
        _rec("tool", "2026-10-20T06:01:00Z", id="t2", cmd="python -m pytest -q"),
    ]
    _closing_sandbox(sandbox, monkeypatch, recs)
    res = fc.check_closing_gates(_closing_item())
    assert (res["turns"], res["blocks"], res["reruns"]) == (2, 1, 1)
    assert res["status"] == "FAIL"                                   # 0.5 擋／回合 > 0.4、0.5 重跑／回合 ≤ 0.5
    assert [r["ok"] for r in res["rows"][:2]] == [False, True]
    assert "ReconcileGate" in res["rows"][2]["value"]


def test_closing_gates_insufficient_and_other_projects_ignored(sandbox, monkeypatch):
    """回合數不到 min_turns → INSUFFICIENT；其他專案資料夾的紀錄不算。"""
    recs = [_rec("user", "2026-10-20T04:00:00Z", text="一題")]
    _closing_sandbox(sandbox, monkeypatch, recs)
    other = sandbox / "projects" / "c--other-proj"
    other.mkdir()
    (other / "s.jsonl").write_text(json.dumps(_rec("user", "2026-10-20T04:00:00Z", text="別的專案")) + "\n", encoding="utf-8")
    res = fc.check_closing_gates(_closing_item(min_turns=2))
    assert res["status"] == "INSUFFICIENT" and res["turns"] == 1


def test_closing_gates_pass_uses_item_on_fail_text(sandbox, monkeypatch):
    """全過 → PASS；登記項自帶 on_fail 時，未過的結論句用它（不再寫死注入預算的報表）。"""
    recs = [_rec("user", "2026-10-20T04:00:00Z", text="一"), _rec("user", "2026-10-20T05:00:00Z", text="二")]
    _closing_sandbox(sandbox, monkeypatch, recs)
    assert fc.check_closing_gates(_closing_item())["status"] == "PASS"
    it = _closing_item(blocks_per_turn_max=-1)
    it["on_fail"] = "讀推進文件第七節"
    text = fc.render(it, fc.check_closing_gates(it))
    assert "讀推進文件第七節" in text and "memory-effect-report" not in text

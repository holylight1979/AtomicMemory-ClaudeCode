"""verify_scorecard_report.py：scorecard 報表與候選卡（tools/scorecard-report.py）；Q12 回路。

正例：baseline＝四週內 S1 中位數（None 忽略、沒資料 None）；below_baseline 只列改過 ≥2 session 且 S1 低於基線的部位；
candidates.json 形狀（generated_at／baseline_s1／recent_s1／below_baseline／top[part,root,edits,sessions,score,reason]）；
報表 md 落 health-reports/scorecard-<日期>.md、LF；main() 哨兵尾行；壞行跳過不炸；視窗外的行不算。
反例（回路不互換）：事先放一份 candidates.json，報表結果與沒放時一字相同（候選不回餵）；
報表模組不呼叫 wg_scorecard.append_scorecard_line。
怎麼跑：python -X utf8 -m pytest -q tools/verify/verify_scorecard_report.py
"""
from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

CLAUDE = Path(__file__).resolve().parents[2]
TOOL = CLAUDE / "tools" / "scorecard-report.py"

_spec = importlib.util.spec_from_file_location("scorecard_report_under_test", TOOL)
SR = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(SR)

NOW = datetime(2026, 10, 8, 9, 0, 0)


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    sd, rd = tmp_path / "scorecard", tmp_path / "health-reports"
    monkeypatch.setattr(SR, "SCORECARD_DIR", sd)
    monkeypatch.setattr(SR, "REPORT_DIR", rd)
    monkeypatch.setattr(SR, "CONFIG_PATH", tmp_path / "nope.json")
    return sd, rd


def _line(days_ago: int, s1, parts, sid="s"):
    at = (NOW - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%S")
    return {"at": at, "session_id": f"{sid}{days_ago}", "cwd": "C:/p", "s1": s1, "s3": s1, "s5": s1,
            "parts_injected": len(parts), "parts_edited": sum(1 for p in parts if p["edits"]), "modified_files": 1,
            "parts": [{"key": f"C:/p|{p['part']}", "root": "C:/p", "located_via": None, "card_read": False, **p} for p in parts]}


def _write(sd: Path, lines, name="202610.jsonl", extra_raw=""):
    sd.mkdir(parents=True, exist_ok=True)
    body = "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines) + extra_raw
    (sd / name).write_text(body, encoding="utf-8", newline="\n")


def _sample():
    srv_bad = {"part": "Server", "edits": 3, "reads": 0, "located": False}
    srv_ok = {"part": "Server", "edits": 1, "reads": 2, "located": True}
    cli = {"part": "Client", "edits": 2, "reads": 1, "located": True}
    docs = {"part": "Docs", "edits": 0, "reads": 0, "located": False}
    return [
        _line(1, 0.2, [srv_bad, cli]),
        _line(3, 1.0, [srv_ok]),
        _line(9, 0.5, [srv_bad, docs]),
        _line(20, None, [docs]),            # S1 None（沒改）不進中位數
        _line(40, 0.0, [srv_bad]),          # 四週外不算
    ]


def test_load_months_window_and_bad_lines(dirs):
    sd, _ = dirs
    _write(sd, _sample(), extra_raw="{bad json\n\n{\"at\": \"not-a-date\"}\n")
    rows = SR.load_months(sd, 4, NOW)
    assert [r["session_id"] for r in rows] == ["s20", "s9", "s3", "s1"]         # 排序、視窗外剔除、壞行跳過
    assert SR.load_months(sd / "missing", 4, NOW) == []


def test_baseline_median_ignores_none(dirs):
    sd, _ = dirs
    _write(sd, _sample())
    rows = SR.load_months(sd, 4, NOW)
    assert SR.baseline(rows) == 0.5                                              # 中位數(0.2, 1.0, 0.5)
    assert SR.recent_value(rows, 7, now=NOW) == 0.6                              # 近 7 天 (0.2, 1.0)
    assert SR.baseline([]) is None and SR.baseline([_line(1, None, [])]) is None


def test_below_baseline_and_candidates(dirs):
    sd, _ = dirs
    _write(sd, _sample())
    rows = SR.load_months(sd, 4, NOW)
    below = SR.below_baseline_parts(rows, SR.baseline(rows))
    assert [b["part"] for b in below] == ["Server"]                              # 3 session 改、讀過 1 → S1 0.333 < 0.5
    assert below[0]["sessions"] == 3 and below[0]["s1"] == 0.333
    assert SR.below_baseline_parts(rows, None) == []
    top = SR.next_card_candidates(rows, 5)
    assert [c["part"] for c in top] == ["Server", "Client"]                      # Docs 沒改過不當候選
    assert top[0]["edits"] == 7 and top[0]["sessions"] == 3 and "沒讀檔 2" in top[0]["reason"] and "沒交定位 2" in top[0]["reason"]
    assert set(top[0]) == {"key", "root", "part", "edits", "sessions", "score", "reason"}
    assert SR.next_card_candidates(rows, 1) == top[:1]


class _FrozenNow(datetime):
    """main() 用 datetime.now() 算視窗；樣本以 NOW 為準，這裡把「現在」釘在 NOW，案例不隨真實日期過期。"""
    @classmethod
    def now(cls, tz=None):
        return NOW


def test_outputs_shape_and_sentinel(dirs, capsys, monkeypatch):
    sd, rd = dirs
    monkeypatch.setattr(SR, "datetime", _FrozenNow)
    _write(sd, _sample())
    assert SR.main(["--weeks", "4", "--top-n", "5"]) == 0
    out = capsys.readouterr().out
    assert out.rstrip().splitlines()[-1] == "SCORECARD_REPORT DONE lines=4 candidates=2"
    cand = json.loads((sd / "candidates.json").read_text(encoding="utf-8"))
    assert {"generated_at", "weeks", "lines", "baseline_s1", "recent_s1", "baseline_s3", "baseline_s5",
            "below_baseline", "top"} <= set(cand)
    assert cand["baseline_s1"] == 0.5 and cand["top"][0]["part"] == "Server" and cand["below_baseline"][0]["part"] == "Server"
    reports = list(rd.glob("scorecard-*.md"))
    assert len(reports) == 1 and b"\r\n" not in reports[0].read_bytes()
    md = reports[0].read_text(encoding="utf-8")
    assert "## 低於基線的部位（1）" in md and "## 下一張該寫的卡（前 2）" in md and "1. Server（C:/p）" in md
    assert SR.main(["--json"]) == 0
    data = json.loads(capsys.readouterr().out.rsplit("\n", 2)[0])
    assert data["paths"]["candidates"].endswith("candidates.json")


def test_empty_data_still_writes_report(dirs, capsys):
    sd, rd = dirs
    assert SR.main([]) == 0
    assert capsys.readouterr().out.rstrip().endswith("SCORECARD_REPORT DONE lines=0 candidates=0")
    cand = json.loads((sd / "candidates.json").read_text(encoding="utf-8"))
    assert cand["baseline_s1"] is None and cand["top"] == [] and "尚無資料" in next(rd.glob("scorecard-*.md")).read_text(encoding="utf-8")


def test_loop_not_reversed(dirs):
    """反例：候選不得回餵：事先放一份 candidates.json，算出來的報表與沒放時一字相同。"""
    sd, _ = dirs
    _write(sd, _sample())
    rows = SR.load_months(sd, 4, NOW)
    clean = SR.build(rows, 4, 5, NOW)
    (sd / "candidates.json").write_text(json.dumps({"top": [{"part": "Docs", "score": 10 ** 9}], "baseline_s1": 0.01}),
                                        encoding="utf-8", newline="\n")
    assert SR.build(SR.load_months(sd, 4, NOW), 4, 5, NOW) == clean
    src = TOOL.read_text(encoding="utf-8")
    assert "import wg_scorecard" not in src and "from wg_scorecard" not in src and "append_scorecard_line(" not in src

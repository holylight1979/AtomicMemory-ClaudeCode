"""verify_selfscore.py：skills/console/scripts/selfscore.py（自檢評分，總控台用的開發期工具）——答一筆讀得回來、缺欄位記「沒答」不擋、
summary 算得對、--ask 印評分尺。

怎麼跑：python -X utf8 -m pytest -q skills/console/verify/verify_selfscore.py
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "hooks"))

import wg_core  # noqa: E402


TAIL = re.compile(r"^SELFSCORE DONE( \w+=\S+)+$")


def _tool():
    spec = importlib.util.spec_from_file_location("selfscore_ut", ROOT / "skills" / "console" / "scripts" / "selfscore.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def logs(monkeypatch, tmp_path):
    monkeypatch.setenv("WG_TEST_LOGS_DIR", str(tmp_path))
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    monkeypatch.setattr(wg_core, "MEMORY_DIR", ROOT / "memory")             # 評分規格卡讀本樹的 memory（_tool() 載入時取值）
    return tmp_path


def _rows(logs, guard):
    p = logs / f"guard-{guard}.jsonl"
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def test_record_is_written_and_read_back(logs, capsys):
    tool = _tool()
    assert tool.main(["--g", "8", "--score", "7", "--basis", "commit:6e3fced4", "--basis", "第二波 A′ 判分",
                      "--why", "專卡都送到了", "--rater", "總控台", "--session", "s1"]) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert out[-1] == "SELFSCORE DONE recorded=1 unanswered=0" and TAIL.match(out[-1])
    [rec] = _rows(logs, "selfscore")
    assert rec["at"] and rec["event"] == "score" and rec["session_id"] == "s1"
    assert (rec["g"], rec["score"], rec["basis"], rec["why"], rec["rater"], rec["unanswered"]) == \
        ("G8", 7, ["commit:6e3fced4", "第二波 A′ 判分"], "專卡都送到了", "總控台", [])


def test_missing_or_bad_fields_are_recorded_as_unanswered_not_blocked(logs, capsys, monkeypatch):
    """分數 11、其他都沒給：照記一筆，該欄「沒答」、原字留 score_raw，stderr 一行，exit 0；連 --g 都沒給也照記。
    session 沒給取 CLAUDE_CODE_SESSION_ID。"""
    tool = _tool()
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "env-sid")
    assert tool.main(["--g", "G8", "--score", "11"]) == 0
    cap = capsys.readouterr()
    assert "沒答的欄：score、basis、why、rater" in cap.err and cap.out.strip().splitlines()[-1].endswith("unanswered=4")
    assert tool.main([]) == 0
    for bad in ("²", "-1", "7.5"):                                            # Unicode 數字、負數、小數：照記沒答，不拋例外
        assert tool.main(["--g", "G8", "--score", bad, "--basis", "b", "--why", "w", "--rater", "r"]) == 0
    a, b, *rest = _rows(logs, "selfscore")
    assert (a["score"], a["score_raw"], a["basis"], a["why"], a["rater"], a["session_id"]) == \
        ("沒答", "11", "沒答", "沒答", "沒答", "env-sid")
    assert a["unanswered"] == ["score", "basis", "why", "rater"]
    assert b["g"] == "沒答" and "score_raw" not in b and b["unanswered"] == ["g", "score", "basis", "why", "rater"]
    assert [(r["score"], r["score_raw"], r["unanswered"]) for r in rest] == [("沒答", s, ["score"]) for s in ("²", "-1", "7.5")]


def test_summary_latest_trend_delta_and_window(logs, capsys):
    tool = _tool()
    for g, s in (("G8", "5"), ("G8", "7"), ("G3", "3"), ("G8", "x"), ("G8", "6")):
        tool.main(["--g", g, "--score", s, "--basis", "b", "--why", "w", "--rater", "r"])
    old = {"at": "2000-01-01T00:00:00+00:00", "event": "score", "g": "G8", "score": 0, "unanswered": []}
    with open(logs / "guard-selfscore.jsonl", "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(old) + "\n壞行\n")
    capsys.readouterr()
    assert tool.main(["--summary", "--json", "--logs", str(logs)]) == 0
    cap = capsys.readouterr()
    lines = cap.out.strip().splitlines()
    assert lines[-1] == "SELFSCORE DONE gs=2 records=5 unanswered=1" and "讀不懂" in cap.err
    res = {s["g"]: s for s in json.loads("\n".join(lines[:-1]))["gs"]}
    g8, g3 = res["G8"], res["G3"]
    assert (g8["records"], g8["latest"]["score"], g8["trend"], g8["delta"], g8["unanswered"]) == (4, 6, [5, 7, 6], -1, 1)
    assert (g3["records"], g3["latest"]["score"], g3["delta"]) == (1, 3, None)


def test_summary_latest_unanswered_has_no_delta(logs, capsys):
    """依序 5、7、沒答：最近一筆沒分數就不算差值（不把 7−5 掛在沒答那筆旁邊），走勢照列有分數的。"""
    tool = _tool()
    for s in ("5", "7", ""):
        tool.main(["--g", "G8", "--score", s, "--basis", "b", "--why", "w", "--rater", "r"])
    capsys.readouterr()
    tool.main(["--summary", "--json", "--logs", str(logs)])
    g8 = json.loads("\n".join(capsys.readouterr().out.strip().splitlines()[:-1]))["gs"][0]
    assert (g8["latest"]["score"], g8["trend"], g8["delta"]) == ("沒答", [5, 7], None)


def test_write_failure_is_not_reported_as_recorded(logs, capsys, monkeypatch):
    """帳沒寫進去（append_guard_log 失敗只記 debug log、不報錯）：stderr 說沒記到、尾行 recorded=0、exit 1。"""
    tool = _tool()
    monkeypatch.setattr(tool, "append_guard_log", lambda *a, **k: None)
    assert tool.main(["--g", "G8", "--score", "7", "--basis", "b", "--why", "w", "--rater", "r"]) == 1
    cap = capsys.readouterr()
    assert "帳沒寫進去" in cap.err and cap.out.strip().splitlines()[-1] == "SELFSCORE DONE recorded=0 unanswered=0"


def test_summary_without_ledger_says_so(logs, capsys):
    assert _tool().main(["--summary", "--logs", str(logs)]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert "沒有自檢評分帳" in lines[0] and lines[-1] == "SELFSCORE DONE gs=0 records=0 unanswered=0"


def test_ask_prints_rubric(logs, capsys):
    """--ask：印 G 名、評分規格卡的三句、可用證據與要答的三件事。找不到卡照樣問。"""
    tool = _tool()
    card = next((ROOT / "memory").rglob("g3-評分規格*.md"))
    rubric = [ln.strip()[2:] for ln in tool._knowledge(card.read_text(encoding="utf-8-sig")).splitlines()
              if ln.strip().startswith("- ")]
    assert len(rubric) == 3                                                    # 前置：規格卡就是三句
    assert tool.main(["--ask", "--g", "g3", "--session", "s2"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("[SELFSCORE_ASK] 自檢評分｜G3：") and all(r in out for r in rubric)
    assert "可用證據：" in out and "--score <0～10>" in out and out.strip().splitlines()[-1].startswith("SELFSCORE DONE asked=1")
    tool.main(["--ask", "--g", "G99"])
    assert "找不到這個 G 的評分規格卡" in capsys.readouterr().out


def test_score_logged(logs):
    """答分留帳 selfscore。"""
    tool = _tool()
    tool.main(["--g", "G8", "--session", "s3"])
    assert [r.get("g") for r in _rows(logs, "selfscore")][-1:] == ["G8"]



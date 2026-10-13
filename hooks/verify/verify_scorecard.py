"""verify_scorecard.py：每 session 一行 scorecard（hooks/wg_scorecard.py 與 session_end 掛點）。

正例：fixture state 算出 S1／S3／S5；append 一行 <100 ms（大 state）、JSON 可讀、LF；分母零 → None；
health_block 恆兩行（無報表／有報表）。
反例：無 state 不寫（連目錄都不建）；沒注入過部位不寫；state 裡塞 candidates 也不影響分數（回路不互換）；
session_end 原始碼位置：append 在 `_se_sentinel_arm` 之後、`state["ended_at"]` 之前、包在 try/except 裡。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_scorecard.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE = HOOKS_DIR.parent
os.environ.setdefault("WG_CLAUDE_DIR", str(CLAUDE))
sys.path.insert(0, str(HOOKS_DIR))
FIX = HOOKS_DIR / "verify" / "fixtures" / "v6" / "scorecard"

import wg_core  # noqa: E402
import wg_scorecard as scb  # noqa: E402


@pytest.fixture
def wdir(tmp_path, monkeypatch):
    d = tmp_path / "workflow"
    d.mkdir()
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", d)
    return d


def _state() -> dict:
    return json.loads(FIX.joinpath("state.json").read_text(encoding="utf-8"))


# ─── 算分 ─────────────────────────────────────────────────────────

def test_fixture_scores():
    s = scb.compute_session_scores(_state())
    assert (s["s1"], s["s3"], s["s5"]) == (0.5, 0.5, 0.333)
    assert s["parts_injected"] == 3 and s["parts_edited"] == 2 and s["modified_files"] == 3
    server = next(p for p in s["parts"] if p["part"] == "Server")
    assert server == {"key": "C:/p|Server", "root": "C:/p", "part": "Server", "edits": 2, "reads": 2,
                      "located": True, "located_via": "tool_input", "card_read": True, "kind": "code"}


def test_knowledge_parts_not_in_s3_denominator():
    """部位表類別 knowledge 的部位不要求定位三行：改了沒交三行不拉低 S3；S1 照算。"""
    st = _state()
    st["overview_hub"]["C:/p|派工信箱"] = {"edits": 3, "reads_after": [], "located": False, "kind": "knowledge"}
    s = scb.compute_session_scores(st)
    assert s["s3"] == 0.5 and s["parts_edited"] == 3 and s["s1"] == 0.333


def test_zero_denominator_is_none_and_garbage_tolerated():
    assert scb.compute_session_scores(None) is None
    assert scb.compute_session_scores({})["s1"] is None
    s = scb.compute_session_scores({"overview_hub": {"r|P": {"edits": 0, "reads_after": []}}, "modified_files": "junk"})
    assert s["s1"] is None and s["s3"] is None and s["s5"] == 0.0 and s["modified_files"] == 0
    s = scb.compute_session_scores({"overview_hub": "junk", "modified_files": [1, {"path": "x"}]})
    assert s["parts_injected"] == 0 and s["modified_files"] == 1


def test_loop_not_reversed_candidates_ignored(wdir):
    st = _state()
    base = scb.compute_session_scores(st)
    st["candidates"] = [{"part": "Client", "score": 10 ** 6}]
    (wdir / "scorecard").mkdir()
    (wdir / "scorecard" / "candidates.json").write_text('{"top":[{"part":"Client","score":1}]}', encoding="utf-8", newline="\n")
    assert scb.compute_session_scores(st) == base
    path = scb.append_scorecard_line(st, "sid")
    line = json.loads(path.read_text(encoding="utf-8").splitlines()[-1])
    assert (line["s1"], line["s3"], line["s5"]) == (base["s1"], base["s3"], base["s5"]) and "candidates" not in line


# ─── append ───────────────────────────────────────────────────────

def test_append_line_under_100ms(wdir):
    st = _state()
    for i in range(50):
        st["overview_hub"][f"C:/p|Part{i}"] = {"edits": i % 3, "reads_after": [f"C:/p/f{j}.cs" for j in range(40)], "located": i % 2 == 0}
    st["modified_files"] += [{"path": f"C:/p/m{i}.cs", "count": 1} for i in range(500)]
    t0 = time.perf_counter()
    path = scb.append_scorecard_line(st, "sid-big", now=1_790_000_000)
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.1, f"{elapsed:.3f}s"
    assert path == wdir / "scorecard" / f"{time.strftime('%Y%m', time.localtime(1_790_000_000))}.jsonl"
    raw = path.read_bytes()
    assert b"\r\n" not in raw and raw.endswith(b"\n")
    line = json.loads(raw.decode("utf-8").splitlines()[-1])
    assert line["session_id"] == "sid-big" and line["cwd"] == "C:/p" and len(line["parts"]) == scb.MAX_PARTS
    scb.append_scorecard_line(st, "sid-2", now=1_790_000_000)
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2                 # 單純 append


def test_no_state_or_no_parts_writes_nothing(wdir):
    assert scb.append_scorecard_line(None, "sid") is None
    assert scb.append_scorecard_line({"modified_files": [{"path": "x"}]}, "sid") is None
    assert scb.append_scorecard_line({"overview_hub": {}}, "sid") is None
    assert not (wdir / "scorecard").exists()


# ─── health_block ─────────────────────────────────────────────────

def test_health_block_two_lines_both_states(wdir):
    lines = scb.health_block()
    assert len(lines) == 2 and "尚無報表" in lines[0] and "scorecard-report.py" in lines[0]
    (wdir / "scorecard").mkdir()
    (wdir / "scorecard" / "candidates.json").write_text(json.dumps({
        "generated_at": "2026-10-08T09:00:00", "baseline_s1": 0.5, "recent_s1": 0.25,
        "below_baseline": [{"part": "Client"}], "top": [{"part": "Client"}, {"part": "Server"}],
    }), encoding="utf-8", newline="\n")
    lines = scb.health_block()
    assert len(lines) == 2
    assert lines[0] == "scorecard：2026-10-08 基線 S1 0.50／近週 S1 0.25，低於基線部位 1（Client）"
    assert lines[1].startswith("下一張該寫的卡：Client、Server（")
    (wdir / "scorecard" / "candidates.json").write_text("{bad", encoding="utf-8", newline="\n")
    lines = scb.health_block()
    assert len(lines) == 2 and "讀不出來" in lines[0]
    for bad in ("[]", "null", '{"top": [1, "x"], "below_baseline": "no", "baseline_s1": "n/a"}',
                '{"top": 1}', '{"below_baseline": true}', '{"top": {"part": "x"}}'):
        (wdir / "scorecard" / "candidates.json").write_text(bad, encoding="utf-8", newline="\n")
        lines = scb.health_block()
        assert len(lines) == 2 and lines[1].startswith("下一張該寫的卡："), bad


# ─── session_end 掛點位置 ─────────────────────────────────────────

def test_session_end_hook_position():
    src = (HOOKS_DIR / "handlers" / "session_end.py").read_text(encoding="utf-8")
    arm = src.index("    _se_sentinel_arm(session_id)\n")
    ended = src.index('    state["ended_at"] = _now_iso()\n')
    between = src[arm:ended]
    m = re.search(r"\n    try:\n(?:        .*\n)+?    except Exception as e:\n        _atom_debug_error\(", between)
    assert m, "append 必須包在 try/except 裡"
    assert "append_scorecard_line(state, session_id)" in m.group(0)
    assert "from wg_scorecard import append_scorecard_line" in m.group(0)
    assert src.count("append_scorecard_line") == 2                                      # import＋呼叫，沒第二個掛點
    assert between.strip().splitlines()[-1].startswith("        _atom_debug_error(")    # 緊接 ended_at 之前

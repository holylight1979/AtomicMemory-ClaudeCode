"""verify_entry_stats_asks.py：tools/entry-stats.py 的 --asks 逐筆輸出（每次問一筆，回應型照 hooks/wg_entrypoint.resolve_responses）。

正例：假帳 → --json 的 asks 每筆欄位齊（at、session、turn_seq、entry、path、cards、truncated、response、response_by、with），
      回應型與直接呼叫 resolve_responses 的結果逐筆相同；文字輸出每筆一行；尾行多 asks_listed=。
反例：沒給 --asks → JSON 沒有 asks、尾行一字不變（照舊讀尾行的程式不受影響）；超過 --days 的那筆不列。
怎麼跑：python -X utf8 -m pytest -q tools/verify/verify_entry_stats_asks.py
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _p in (_ROOT / "hooks", _ROOT / "lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import wg_entrypoint as ep  # noqa: E402

FIELDS = {"at", "session", "turn_seq", "entry", "path", "cards", "truncated", "response", "response_by", "with"}


def _stats():
    spec = importlib.util.spec_from_file_location("entry_stats_asks_ut", _ROOT / "tools" / "entry-stats.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["entry_stats_asks_ut"] = mod
    spec.loader.exec_module(mod)
    return mod


def _fake_logs(d: Path, sids=("s1", "s2")):
    """E20 問兩次（第一次沒過、第二次宣告）＋ E04 問一次（記進追蹤帳＝judged）＋ 30 天前一筆（不列）。"""
    d.mkdir()
    s1, s2 = sids
    now = datetime.now().astimezone()
    at = lambda s: (now + timedelta(seconds=s)).isoformat(timespec="seconds")  # noqa: E731
    asks = [{"at": at(-30), "event": "ask", "session_id": s1, "turn_seq": 1, "entry": "E20", "path": "pretool_deny",
             "cards": ["c"], "truncated": False, "with": [], "response": "none"},
            {"at": at(-20), "event": "ask", "session_id": s1, "turn_seq": 1, "entry": "E20", "path": "pretool_deny",
             "cards": ["c", "d"], "truncated": True, "with": ["E26"], "response": "none"},
            {"at": at(-10), "event": "ask", "session_id": s2, "entry": "E04", "path": "stop_piggyback", "cards": [],
             "truncated": False, "with": [], "response": "none"},
            {"at": (now - timedelta(days=30)).isoformat(timespec="seconds"), "event": "ask", "session_id": "s3",
             "entry": "E04", "path": "stop_piggyback", "cards": [], "truncated": False, "with": [], "response": "none"}]
    (d / "guard-entry.jsonl").write_text("".join(json.dumps(a, ensure_ascii=False) + "\n" for a in asks),
                                         encoding="utf-8", newline="\n")
    guards = {"data_file": [{"at": at(-15), "session_id": s1, "event": "declared"}],
              "pick_one": [{"at": at(-5), "session_id": s2, "event": "recorded"}]}
    for g, rows in guards.items():
        (d / f"guard-{g}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8", newline="\n")
    return asks[:3], guards


def test_asks_json_lists_every_ask_with_fields_and_same_responses(tmp_path, capsys):
    stats = _stats()
    d = tmp_path / "Logs"
    recent, guards = _fake_logs(d)
    assert stats.main(["--logs", str(d), "--json", "--asks"]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert re.fullmatch(r"[A-Z][A-Z0-9_]* DONE( \w+=\S+)*", lines[-1])
    assert lines[-1] == "ENTRY_STATS DONE entries=2 asks=3 cards=3 truncated=1 asks_listed=3"
    rows = json.loads("\n".join(lines[:-1]))["asks"]
    assert len(rows) == 3 and all(set(r) == FIELDS for r in rows)                        # 30 天前那筆不列
    want = ep.resolve_responses(recent, guards, ep.load_registry())                      # 同一支判法，直接呼叫的結果
    assert [(r["at"], r["session"], r["entry"], r["response"], r["response_by"]) for r in rows] == \
        [(w["at"], w["session_id"], w["entry"], w["response"], w["response_by"]) for w in want]
    assert [r["response"] for r in rows] == ["denied", "declared", "judged"]             # 前置：三型都有，不是全 none
    second, third = rows[1], rows[2]
    assert (second["turn_seq"], second["path"], second["cards"], second["truncated"], second["with"]) == \
        (1, "pretool_deny", ["c", "d"], True, ["E26"])
    assert third["turn_seq"] is None and third["cards"] == []                           # 帳上沒回合號照實給 null


def test_asks_text_one_line_per_ask_with_every_field(tmp_path, capsys):
    """文字輸出每筆一行、欄位不比 JSON 少（Codex：session 不截短、要有 response_by）；兩個 session 前八碼相同也分得出來。"""
    stats = _stats()
    d = tmp_path / "Logs"
    _fake_logs(d, sids=("sess-0001-aaaa", "sess-0001-bbbb"))
    assert stats.main(["--logs", str(d), "--asks", "--json"]) == 0
    rows = json.loads("\n".join(capsys.readouterr().out.strip().splitlines()[:-1]))["asks"]
    assert stats.main(["--logs", str(d), "--asks"]) == 0
    out = capsys.readouterr().out
    listed = [ln for ln in out.splitlines() if ln.startswith("  · ")]
    assert len(listed) == len(rows) == 3
    for ln, r in zip(listed, rows):
        turn = "?" if r["turn_seq"] is None else str(r["turn_seq"])
        for v in (r["at"], f"session {r['session']} ", f"回合 {turn} ", r["entry"], r["path"], f"回應 {r['response']}",
                  *r["cards"], *r["with"], *([r["response_by"]] if r["response_by"] else [])):
            assert v in ln, (v, ln)
        assert ("（截斷）" in ln) == r["truncated"]
    assert "sess-0001-aaaa" in listed[0] and "sess-0001-bbbb" in listed[2]
    assert out.strip().splitlines()[-1].endswith(" asks_listed=3")


def test_without_asks_flag_output_and_tail_unchanged(tmp_path, capsys):
    stats = _stats()
    d = tmp_path / "Logs"
    _fake_logs(d)
    assert stats.main(["--logs", str(d), "--json"]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[-1] == "ENTRY_STATS DONE entries=2 asks=3 cards=3 truncated=1"
    assert "asks" not in json.loads("\n".join(lines[:-1]))
    assert stats.main(["--logs", str(tmp_path / "none"), "--asks"]) == 0                 # 沒資料也 0、照列 0 筆
    assert capsys.readouterr().out.strip().splitlines()[-1] == \
        "ENTRY_STATS DONE entries=0 asks=0 cards=0 truncated=0 asks_listed=0"

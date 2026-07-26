"""verify_effect_report.py — 記憶注入效果報表（tools/memory-effect-report.py）契約。

collect()：
  - A top 有用：有 α/β 證據或 rescue 命中才入列，依 Wilson 下界排序
  - B token 稅：窗內曝光 ≥ EXPOSURE_TAX_MIN 且零證據零 rescue 才入列
  - C 死重候選：窗內零曝光
  - D 失念：recall-miss.jsonl 窗內聚合（atom × 次數 × 最近 evidence × trigger 聯集）
  - 30 天週趨勢 bucket 數 = ceil(days/7)；rescue 命中入正確 bucket
  - sidecar 缺失 / rescue log 缺失 / recall-miss log 缺失 → 不炸，計為零
render_md()：四清單 + 趨勢表 + caveat 皆呈現；D 無資料顯示（無）。

受控 tmp 環境：monkeypatch 模組常數 ATOM_INDEX / RESCUE_LOG / RECALL_MISS_LOG /
CLAUDE_DIR。
"""
from __future__ import annotations

import importlib.util
import json
import time
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

_spec = importlib.util.spec_from_file_location(
    "memory_effect_report", _ROOT / "tools" / "memory-effect-report.py")
mer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mer)

NOW = time.time()


def _setup(tmp_path, monkeypatch, atoms, sidecars=None, rescue_lines=None,
           recall_lines=None):
    """建 tmp 索引/側車/rescue log/recall-miss log 並重指模組常數。"""
    (tmp_path / "memory").mkdir(exist_ok=True)
    (tmp_path / "Logs").mkdir(exist_ok=True)
    idx = tmp_path / "memory" / "_atom_index.json"
    idx.write_text(json.dumps({"version": "1.0", "atoms": atoms},
                              ensure_ascii=False), encoding="utf-8")
    for rel, data in (sidecars or {}).items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data), encoding="utf-8")
    rl = tmp_path / "Logs" / "rescue-log.jsonl"
    if rescue_lines is not None:
        rl.write_text("\n".join(json.dumps(x) for x in rescue_lines) + "\n",
                      encoding="utf-8")
    rm = tmp_path / "Logs" / "recall-miss.jsonl"
    if recall_lines is not None:
        rm.write_text(
            "\n".join(json.dumps(x, ensure_ascii=False) for x in recall_lines) + "\n",
            encoding="utf-8")
    monkeypatch.setattr(mer, "CLAUDE_DIR", tmp_path)
    monkeypatch.setattr(mer, "ATOM_INDEX", idx)
    monkeypatch.setattr(mer, "RESCUE_LOG", rl)
    monkeypatch.setattr(mer, "RECALL_MISS_LOG", rm)


def _atom(name):
    return {"name": name, "path": f"memory/{name}.md",
            "triggers": ["特定詞A", "特定詞B"], "scope": "global"}


def test_three_lists_classification(tmp_path, monkeypatch):
    _setup(
        tmp_path, monkeypatch,
        atoms=[_atom("useful-one"), _atom("tax-one"), _atom("dead-one")],
        sidecars={
            # 有效用證據 → A
            "memory/useful-one.access.json": {
                "read_hits": 20, "timestamps": [NOW - 3600] * 5,
                "useful_hits": 5.0, "used_fail": 1.0, "last_used": "2026-07-08"},
            # 高曝光零證據 → B
            "memory/tax-one.access.json": {
                "read_hits": 30, "timestamps": [NOW - 3600] * 12,
                "useful_hits": 1.0, "used_fail": 1.0, "last_used": "2026-07-08"},
            # 窗內零曝光 → C
            "memory/dead-one.access.json": {
                "read_hits": 3, "timestamps": [NOW - 90 * 86400],
                "useful_hits": 1.0, "used_fail": 1.0, "last_used": "2026-04-01"},
        },
    )
    r = mer.collect(days=30)
    assert [x["name"] for x in r["top_useful"]] == ["useful-one"]
    assert [x["name"] for x in r["exposure_tax"]] == ["tax-one"]
    assert [x["name"] for x in r["dead_candidates"]] == ["dead-one"]
    assert r["top_useful"][0]["wilson_lb"] > 0


def test_rescue_hit_promotes_to_useful_and_blocks_tax(tmp_path, monkeypatch):
    _setup(
        tmp_path, monkeypatch,
        atoms=[_atom("rescued")],
        sidecars={"memory/rescued.access.json": {
            "read_hits": 15, "timestamps": [NOW - 3600] * 12,
            "useful_hits": 1.0, "used_fail": 1.0, "last_used": "2026-07-08"}},
        rescue_lines=[{"ts": NOW - 100, "atom": "rescued", "token": "x",
                       "evidence": "", "turn_seq": 1, "tool": "Bash"}],
    )
    r = mer.collect(days=30)
    assert [x["name"] for x in r["top_useful"]] == ["rescued"]
    assert r["top_useful"][0]["rescue_hits"] == 1
    assert not r["exposure_tax"]  # rescue 證據豁免 token 稅


def test_trend_buckets_and_rescue_placement(tmp_path, monkeypatch):
    _setup(
        tmp_path, monkeypatch,
        atoms=[_atom("a1")],
        sidecars={"memory/a1.access.json": {
            "read_hits": 2, "timestamps": [NOW - 2 * 86400, NOW - 20 * 86400],
            "useful_hits": 1.0, "used_fail": 1.0}},
        rescue_lines=[{"ts": NOW - 2 * 86400, "atom": "a1", "token": "t",
                       "evidence": "", "turn_seq": 1, "tool": "Bash"}],
    )
    r = mer.collect(days=28)
    assert len(r["trend_weekly"]) == 4
    assert sum(b["exposures"] for b in r["trend_weekly"]) == 2
    assert r["trend_weekly"][-1]["rescue_hits"] == 1  # 最近一週


def test_missing_sidecar_and_log_no_crash(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, atoms=[_atom("bare")])
    r = mer.collect(days=30)
    assert r["atom_count"] == 1
    assert [x["name"] for x in r["dead_candidates"]] == ["bare"]
    assert not r["top_useful"] and not r["exposure_tax"]


def _rm_line(atom, days_ago, evidence="pytest 紅 E155036", triggers=("svn", "工作副本")):
    from datetime import datetime, timedelta
    at = (datetime.now().astimezone() - timedelta(days=days_ago)).isoformat(
        timespec="seconds")
    return {"at": at, "session_id": "sid", "atom": atom,
            "matched_triggers": list(triggers), "evidence": evidence,
            "source": "failing_tests"}


def test_recall_miss_aggregation_window_and_order(tmp_path, monkeypatch):
    _setup(
        tmp_path, monkeypatch, atoms=[_atom("a1")],
        recall_lines=[
            _rm_line("often-missed", 5, evidence="舊 evidence"),
            _rm_line("often-missed", 1, evidence="最新 evidence", triggers=("checkin",)),
            _rm_line("rare-missed", 2),
            _rm_line("out-of-window", 90),  # 窗外不計
        ],
    )
    r = mer.collect(days=30)
    assert [x["atom"] for x in r["recall_miss"]] == ["often-missed", "rare-missed"]
    top = r["recall_miss"][0]
    assert top["count"] == 2
    assert top["last_evidence"] == "最新 evidence"          # 取最近一筆
    assert set(top["matched_triggers"]) == {"svn", "工作副本", "checkin"}  # 聯集


def test_recall_miss_render_and_empty_silent(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, atoms=[_atom("a1")],
           recall_lines=[_rm_line("missed-one", 1)])
    md = mer.render_md(mer.collect(days=30))
    assert "D. 失念" in md
    assert "missed-one" in md
    assert "trigger 是否該補詞" in md
    # 無資料 → （無），且缺檔不炸（乾淨子目錄，避免沿用上面已寫的 log）
    clean = tmp_path / "clean"
    clean.mkdir()
    _setup(clean, monkeypatch, atoms=[_atom("a1")])
    r2 = mer.collect(days=30)
    assert r2["recall_miss"] == []
    md2 = mer.render_md(r2)
    assert "D. 失念" in md2 and "（無）" in md2


def test_render_md_sections(tmp_path, monkeypatch):
    _setup(
        tmp_path, monkeypatch,
        atoms=[_atom("tax-one")],
        sidecars={"memory/tax-one.access.json": {
            "read_hits": 30, "timestamps": [NOW - 3600] * 12,
            "useful_hits": 1.0, "used_fail": 1.0}},
    )
    md = mer.render_md(mer.collect(days=30))
    for frag in ("Top 有用", "token 稅", "死重候選", "30 天週趨勢",
                 "tax-one", "trigger 收斂建議", "下限估計"):
        assert frag in md

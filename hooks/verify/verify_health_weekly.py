"""verify_health_weekly.py — 週健檢死人開關 + health-weekly 純函式驗證。

覆蓋：
  - session_start._health_advisory：缺檔 / 逾期 / red>0 / 健康 / 壞 JSON
    五態各自浮出正確 advisory（fail-open 必告知，健康時零 context 佔用）
  - tools/health-weekly.py：_promotion_last_ts 讀尾筆 ts、write_report 輪替保留、
    _recall_miss_counts 失念計數（14 天窗過濾、缺檔/壞行零計）

對應：hooks/handlers/session_start.py（_health_advisory / HEALTH_RUN_STALE_DAYS）、
tools/health-weekly.py。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "hooks"))
sys.path.insert(0, str(_ROOT / "hooks" / "handlers"))

from session_start import _health_advisory, HEALTH_RUN_STALE_DAYS  # noqa: E402


def _write_last_run(tmp_path, days_ago=0, red=0):
    p = tmp_path / "health-last-run.json"
    at = (datetime.now() - timedelta(days=days_ago)).isoformat(timespec="seconds")
    p.write_text(json.dumps({"at": at, "red": red, "yellow": 0,
                             "report": "workflow/health-reports/health-x.md"}),
                 encoding="utf-8")
    return p


# ─── _health_advisory 五態 ───────────────────────────────────────────


def test_missing_file_advises(tmp_path):
    out = _health_advisory(tmp_path / "nope.json")
    assert len(out) == 1 and "排程未註冊" in out[0]


def test_stale_run_advises(tmp_path):
    p = _write_last_run(tmp_path, days_ago=HEALTH_RUN_STALE_DAYS + 5)
    out = _health_advisory(p)
    assert any("天未跑" in x for x in out)


def test_red_findings_advise(tmp_path):
    p = _write_last_run(tmp_path, days_ago=1, red=3)
    out = _health_advisory(p)
    assert any("3 項需處理" in x for x in out)


def test_healthy_is_silent(tmp_path):
    p = _write_last_run(tmp_path, days_ago=1, red=0)
    assert _health_advisory(p) == []


def test_corrupt_json_advises(tmp_path):
    p = tmp_path / "health-last-run.json"
    p.write_text("{bad", encoding="utf-8")
    out = _health_advisory(p)
    assert len(out) == 1 and "不可解析" in out[0]


# ─── health-weekly 純函式 ────────────────────────────────────────────


@pytest.fixture()
def hw(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "health_weekly_under_test", _ROOT / "tools" / "health-weekly.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "MEMORY", tmp_path)
    monkeypatch.setattr(mod, "REPORT_DIR", tmp_path / "health-reports")
    return mod


def test_promotion_last_ts_reads_tail(hw, tmp_path):
    p = tmp_path / "_promotion_audit.jsonl"
    rows = [{"ts": "2026-01-01T00:00:00", "action": "hint"},
            {"ts": "2026-06-30T12:34:56", "action": "hint"}]
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    assert hw._promotion_last_ts() == datetime(2026, 6, 30, 12, 34, 56)


def test_promotion_last_ts_missing_is_none(hw):
    assert hw._promotion_last_ts() is None


def test_write_report_rotates(hw):
    for i in range(hw.KEEP_REPORTS + 3):
        hw.write_report({"at": f"2026-01-{i + 1:02d}T00:00:00",
                         "red": [], "yellow": [], "info": []})
    left = list((hw.REPORT_DIR).glob("health-*.md"))
    assert len(left) == hw.KEEP_REPORTS


# ─── 失念（recall-miss）黃燈計數 ─────────────────────────────────────


def _rm_rec(atom, days_ago):
    at = (datetime.now().astimezone() - timedelta(days=days_ago)).isoformat(
        timespec="seconds")
    return {"at": at, "session_id": "sid", "atom": atom,
            "matched_triggers": ["a", "b"], "evidence": "e", "source": "failing_tests"}


def test_recall_miss_counts_window_filter(hw, tmp_path, monkeypatch):
    log = tmp_path / "recall-miss.jsonl"
    rows = [_rm_rec("hot-atom", 1), _rm_rec("hot-atom", 3), _rm_rec("hot-atom", 5),
            _rm_rec("cold-atom", 2), _rm_rec("hot-atom", 60)]  # 最後一筆窗外
    log.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
                   + "\n壞行not-json\n", encoding="utf-8")
    monkeypatch.setattr(hw, "RECALL_MISS_LOG", log)
    counts = hw._recall_miss_counts(hw.RECALL_MISS_DAYS)
    assert counts == {"hot-atom": 3, "cold-atom": 1}
    # 黃燈門檻：hot-atom 達 RECALL_MISS_MIN、cold-atom 未達
    assert counts["hot-atom"] >= hw.RECALL_MISS_MIN
    assert counts["cold-atom"] < hw.RECALL_MISS_MIN


def test_recall_miss_counts_missing_log_zero(hw, tmp_path, monkeypatch):
    monkeypatch.setattr(hw, "RECALL_MISS_LOG", tmp_path / "nope.jsonl")
    assert hw._recall_miss_counts(14) == {}


# ─── H7 Depends 區塊（stale_deps 黃、依賴比卡新黃、覆蓋率 info／低於門檻黃）────


def test_depends_block_yellow_and_info(hw):
    hc = {"stale_deps": [{"atom": "a", "dep": "x"}, {"atom": "b", "dep": "y"}],
          "stale_mtime_deps": [{"atom": "c", "dep": "C:/p/q.py", "dep_mtime": "2026-10-02", "verified_at": "2026-09-01"}],
          "depends_coverage": {"with_depends": 3, "total": 10, "ratio": 0.3}}
    yellow, info = hw._depends_block(hc, 0.0)
    assert any("stale_deps 2 筆" in y for y in yellow) and any("依賴比卡新 1 筆" in y and "c←q.py" in y for y in yellow)
    assert info == ["Depends 覆蓋率 3/10 = 30.0%"] and not any("低於" in y for y in yellow)
    yellow2, _ = hw._depends_block(hc, 0.5)
    assert any("低於 depends_coverage_min 50.0%" in y for y in yellow2)


def test_depends_block_silent_without_data(hw):
    assert hw._depends_block({}, 0.0) == ([], [])


# ─── config 內建 PYTEST regex 非現行版（只更新 hooks、沒對 config 的機器）→ 黃 ────


def _cfg_with_rules(rules):
    return {"verify_ledger": {"enabled": True, "sentinel_regex": rules}}


def test_pytest_regex_block_silent_on_shipped_config(hw):
    shipped = json.loads((_ROOT / "workflow" / "config.json").read_text(encoding="utf-8"))
    assert hw._pytest_regex_block(shipped) == []


def test_pytest_regex_block_warns_on_oldest_regex(hw):
    # 036d 之前最早版的內建形狀：沒有 error 狀態詞、沒有 pytest_summary 旗標；「1 passed, 1 error」會被判 PASS
    old = r"^(?:=+ )?(?P<verdict>\d+ (?:passed|failed))"
    cfg = _cfg_with_rules([
        {"regex": old, "name": "PYTEST", "verdict_map": {"failed": "FAIL", "passed": "PASS"}},
        {"regex": old, "name": "PYTEST_MEASURE", "verdict_map": {"failed": "FAIL", "passed": "DONE"}},
    ])
    yellow = hw._pytest_regex_block(cfg)
    assert len(yellow) == 2
    assert any(y.startswith("config 內建 PYTEST regex 非現行版") and "regex" in y and "pytest_summary" in y and "判成 PASS" in y for y in yellow)
    assert any(y.startswith("config 內建 PYTEST_MEASURE regex 非現行版") and "判成 DONE" in y for y in yellow)
    assert all("Install-forAI" in y for y in yellow)


def test_pytest_regex_block_missing_rule_and_custom_rule_ignored(hw):
    shipped = json.loads((_ROOT / "workflow" / "config.json").read_text(encoding="utf-8"))
    rules = [r for r in shipped["verify_ledger"]["sentinel_regex"] if r["name"] == "PYTEST"]
    rules.append({"regex": r"^MYTOOL (?P<verdict>OK|BAD)$", "name": "MYTOOL", "verdict_map": {"OK": "PASS", "BAD": "FAIL"}})
    yellow = hw._pytest_regex_block(_cfg_with_rules(rules))
    assert yellow == ["config 內建 PYTEST_MEASURE 規則缺失（verify_ledger.sentinel_regex 沒有這條）→ 補成版控庫 workflow/config.json 的現行值"]
    assert hw._pytest_regex_block({}) and hw._pytest_regex_block({"verify_ledger": "bad"})   # 沒有區段：兩條都缺，不炸


def test_pytest_regex_block_case_only_and_junk_items(hw):
    # codex 審 8d4c4ad 提的兩個邊界：verdict_map 只差大小寫（hook 端 upper() 後同義 → 靜默）；非 dict 的規則項略過不炸
    shipped = json.loads((_ROOT / "workflow" / "config.json").read_text(encoding="utf-8"))
    rules = [dict(r) for r in shipped["verify_ledger"]["sentinel_regex"]]
    for r in rules:
        r["verdict_map"] = {k: v.lower() for k, v in r["verdict_map"].items()}
    assert hw._pytest_regex_block(_cfg_with_rules(rules)) == []
    assert hw._pytest_regex_block(_cfg_with_rules(["junk", None, 3] + rules)) == []
    # 單獨只改 verdict_map 的「內容」（少了 error→FAIL）就要報，且只報 verdict_map 那一樣
    rules[0]["verdict_map"] = {"failed": "FAIL", "passed": "PASS", "xpassed": "PASS"}
    yellow = hw._pytest_regex_block(_cfg_with_rules(rules))
    assert len(yellow) == 1 and "（verdict_map 與版控庫" in yellow[0] and yellow[0].startswith("config 內建 PYTEST regex 非現行版")

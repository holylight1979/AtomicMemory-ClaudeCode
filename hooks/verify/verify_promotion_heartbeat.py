"""verify_promotion_heartbeat.py — 晉升 audit heartbeat 驗證。

覆蓋：wg_core.log_promotion_heartbeat——
  - 缺檔 → 直接落首筆 heartbeat（含 scanned 欄）
  - 尾筆距今 < min_gap_hours → 節流跳過（audit 不被洗版）
  - 尾筆夠舊 → 追加新 heartbeat
  - 尾筆壞行 → 往前找可解析行判斷節流

對應：hooks/wg_core.py（log_promotion_heartbeat）、
hooks/wg_atoms.py（_self_iterate_atoms 無晉升事件呼叫點）、
tools/health-weekly.py §6 鮮度檢查（消「無事件誤報停擺」紅燈）。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "hooks"))

import wg_core  # noqa: E402


def _audit_lines(tmp_path):
    """回傳可解析的 JSONL 列（壞行跳過，供壞行容錯測試用）。"""
    p = tmp_path / "_promotion_audit.jsonl"
    if not p.is_file():
        return []
    rows = []
    for x in p.read_text(encoding="utf-8").strip().splitlines():
        try:
            rows.append(json.loads(x))
        except ValueError:
            continue
    return rows


def _write_last(tmp_path, hours_ago, action="auto_observe"):
    ts = (datetime.now() - timedelta(hours=hours_ago)).isoformat(timespec="seconds")
    p = tmp_path / "_promotion_audit.jsonl"
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": ts, "action": action, "atom": "x"}) + "\n")


def test_missing_file_writes_first_heartbeat(tmp_path, monkeypatch):
    monkeypatch.setattr(wg_core, "MEMORY_DIR", tmp_path)
    wg_core.log_promotion_heartbeat(scanned=42)
    rows = _audit_lines(tmp_path)
    assert len(rows) == 1
    assert rows[0]["action"] == "heartbeat" and rows[0]["scanned"] == 42


def test_recent_entry_throttles(tmp_path, monkeypatch):
    monkeypatch.setattr(wg_core, "MEMORY_DIR", tmp_path)
    _write_last(tmp_path, hours_ago=1)
    wg_core.log_promotion_heartbeat(scanned=10)
    assert len(_audit_lines(tmp_path)) == 1  # 未追加


def test_stale_entry_appends(tmp_path, monkeypatch):
    monkeypatch.setattr(wg_core, "MEMORY_DIR", tmp_path)
    _write_last(tmp_path, hours_ago=30)
    wg_core.log_promotion_heartbeat(scanned=10)
    rows = _audit_lines(tmp_path)
    assert len(rows) == 2 and rows[-1]["action"] == "heartbeat"


def test_corrupt_tail_falls_back_to_parsable_line(tmp_path, monkeypatch):
    monkeypatch.setattr(wg_core, "MEMORY_DIR", tmp_path)
    _write_last(tmp_path, hours_ago=1)
    p = tmp_path / "_promotion_audit.jsonl"
    with open(p, "a", encoding="utf-8") as f:
        f.write("{bad json\n")
    wg_core.log_promotion_heartbeat(scanned=10)
    # 壞行不可解析 → 往前找到 1 小時前那筆 → 節流跳過
    assert sum(1 for r in _audit_lines(tmp_path)) == 1

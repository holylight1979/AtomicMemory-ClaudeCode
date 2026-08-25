"""verify_aec_file_prune.py — AEC 報告/決策檔 7 天 TTL 清理（SessionStart GC）。

驗證 handlers/session_start._prune_aec_files：清 workflow/aec-report/ 與 aec-decision/
中 mtime 超過 max_age_days 的 .json（per-turn 執行期狀態檔，寫了不清會無限累積）。

  - 超過 TTL 的舊檔 → 刪；TTL 內的新檔 → 留
  - .tmp（atomic write 過渡檔）→ *.json glob 掃不到、不動
  - 兩個資料夾一起掃、回傳刪除數
  - 目錄不存在 → fail-open 回 0 不炸
  - max_age_days 可調

清理排在 SessionStart（比照 log rotation 的開機打掃）；此測只驗純函式。
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify → hooks
sys.path.insert(0, str(HOOKS_DIR))

from handlers import session_start as ss  # noqa: E402


def _touch(p: Path, age_days: float) -> None:
    p.write_text("{}", encoding="utf-8")
    ts = time.time() - age_days * 86400
    os.utime(p, (ts, ts))


@pytest.fixture
def wdir(tmp_path, monkeypatch):
    """把 session_start.WORKFLOW_DIR 導向 tmp。"""
    monkeypatch.setattr(ss, "WORKFLOW_DIR", tmp_path)
    return tmp_path


def test_prunes_old_keeps_fresh(wdir):
    """兩夾各有舊/新檔 → 只刪超過 7 天者；.tmp 不動。"""
    rep, dec = wdir / "aec-report", wdir / "aec-decision"
    rep.mkdir(); dec.mkdir()
    _touch(rep / "old.json", 10)      # >7d → 刪
    _touch(rep / "fresh.json", 1)     # <7d → 留
    _touch(dec / "old.json", 30)      # 刪
    _touch(dec / "fresh.json", 0)     # 留
    _touch(rep / "stale.tmp", 100)    # .tmp → *.json 掃不到 → 留

    n = ss._prune_aec_files(max_age_days=7)

    assert n == 2
    assert not (rep / "old.json").exists()
    assert (rep / "fresh.json").exists()
    assert not (dec / "old.json").exists()
    assert (dec / "fresh.json").exists()
    assert (rep / "stale.tmp").exists()   # atomic-write 過渡檔保留


def test_boundary_within_ttl_kept(wdir):
    """6 天 < 7 天 TTL → 保留。"""
    rep = wdir / "aec-report"; rep.mkdir()
    _touch(rep / "edge.json", 6)
    assert ss._prune_aec_files(max_age_days=7) == 0
    assert (rep / "edge.json").exists()


def test_missing_dirs_fail_open(wdir):
    """兩夾都不存在 → 回 0、不炸。"""
    assert ss._prune_aec_files(max_age_days=7) == 0


def test_custom_age(wdir):
    """max_age_days 可調：3 天檔在 2 天門檻下被刪。"""
    dec = wdir / "aec-decision"; dec.mkdir()
    _touch(dec / "d.json", 3)
    assert ss._prune_aec_files(max_age_days=2) == 1
    assert not (dec / "d.json").exists()


def test_ledger_pruned_only_when_no_path_alive(wdir, tmp_path):
    """aec-tempfiles/<sid>.jsonl：過期但帳上仍有路徑存在 → 留；全都不在 → 清。"""
    import json, os, time
    ldir = wdir / "aec-tempfiles"; ldir.mkdir()
    alive = tmp_path / "still.tmp"; alive.write_text("x")
    keep = ldir / "keep.jsonl"
    keep.write_text(json.dumps({"path": str(alive)}) + "\n" + json.dumps({"path": str(tmp_path / "gone")}) + "\n")
    drop = ldir / "drop.jsonl"
    drop.write_text(json.dumps({"path": str(tmp_path / "gone2")}) + "\nnot json\n")
    old = time.time() - 30 * 86400
    for p in (keep, drop):
        os.utime(p, (old, old))
    n = ss._prune_aec_files(max_age_days=7)
    assert keep.exists() and not drop.exists()
    assert n == 1

"""verify_aec_file_prune.py — AEC 報告/決策檔 7 天 TTL 清理（SessionStart GC）。

驗證 handlers/_shared.prune_workflow_records 照 WORKFLOW_RETENTION 清 workflow/aec-report/、aec-decision/、aec-tempfiles/：

  - aec-report、aec-decision：超過 7 天的舊檔 → 刪；7 天內 → 留
  - aec-report 的 .tmp（寫入被砍的殘檔）同樣 7 天清
  - 目錄不存在 → fail-open 不炸
  - aec-tempfiles 殘檔帳本：過期且帳上路徑全都不在才清

清理排在 SessionStart（session_start 呼叫 prune_workflow_records）；此測只驗函式。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify → hooks
sys.path.insert(0, str(HOOKS_DIR))

from handlers import _shared  # noqa: E402


def _touch(p: Path, age_days: float) -> None:
    p.write_text("{}", encoding="utf-8")
    ts = time.time() - age_days * 86400
    os.utime(p, (ts, ts))


@pytest.fixture
def wdir(tmp_path):
    d = tmp_path / "workflow"
    d.mkdir()
    return d


def _prune(wdir: Path) -> int:
    return len(_shared.prune_workflow_records(wf=wdir)["deleted"])


def test_prunes_old_keeps_fresh(wdir):
    """兩夾各有舊/新檔 → 只刪超過 7 天者；aec-report 的舊 .tmp 也清、新 .tmp 留。"""
    rep, dec = wdir / "aec-report", wdir / "aec-decision"
    rep.mkdir(); dec.mkdir()
    _touch(rep / "old.json", 10)      # >7d → 刪
    _touch(rep / "fresh.json", 1)     # <7d → 留
    _touch(dec / "old.json", 30)      # 刪
    _touch(dec / "fresh.json", 0)     # 留
    _touch(rep / "stale.tmp", 100)    # 寫入被砍的殘檔 → 刪
    _touch(rep / "young.tmp", 1)      # 可能正在寫 → 留

    n = _prune(wdir)

    assert n == 3
    assert not (rep / "old.json").exists()
    assert (rep / "fresh.json").exists()
    assert not (dec / "old.json").exists()
    assert (dec / "fresh.json").exists()
    assert not (rep / "stale.tmp").exists()
    assert (rep / "young.tmp").exists()


def test_boundary_within_ttl_kept(wdir):
    """6 天 < 7 天 TTL → 保留。"""
    rep = wdir / "aec-report"; rep.mkdir()
    _touch(rep / "edge.json", 6)
    assert _prune(wdir) == 0
    assert (rep / "edge.json").exists()


def test_missing_dirs_fail_open(wdir):
    """三夾都不存在 → 什麼都不刪、不炸。"""
    assert _prune(wdir) == 0


def test_ledger_pruned_only_when_no_path_alive(wdir, tmp_path):
    """aec-tempfiles/<sid>.jsonl：過期但帳上仍有路徑存在 → 留；全都不在 → 清。"""
    ldir = wdir / "aec-tempfiles"; ldir.mkdir()
    alive = tmp_path / "still.tmp"; alive.write_text("x")
    keep = ldir / "keep.jsonl"
    keep.write_text(json.dumps({"path": str(alive)}) + "\n" + json.dumps({"path": str(tmp_path / "gone")}) + "\n")
    drop = ldir / "drop.jsonl"
    drop.write_text(json.dumps({"path": str(tmp_path / "gone2")}) + "\nnot json\n")
    old = time.time() - 30 * 86400
    for p in (keep, drop):
        os.utime(p, (old, old))
    n = _prune(wdir)
    assert keep.exists() and not drop.exists()
    assert n == 1


def test_fresh_ledger_kept_even_if_paths_gone(wdir, tmp_path):
    """帳本未滿 7 天 → 就算路徑都不在也留（HUD 還在用）。"""
    ldir = wdir / "aec-tempfiles"; ldir.mkdir()
    fresh = ldir / "fresh.jsonl"
    fresh.write_text(json.dumps({"path": str(tmp_path / "gone")}) + "\n")
    assert _prune(wdir) == 0 and fresh.exists()

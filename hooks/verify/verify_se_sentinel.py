"""verify_se_sentinel.py — SessionEnd 哨兵（A5，比照 UPS 哨兵模式）。

契約：
- session_end._se_sentinel_arm：touch workflow/se-sentinel/<sid>.json；
  _se_sentinel_clear：移除（正常收尾走到才拆）
- session_start._check_se_sentinel_residual：>min_age_s 的殘留 → 告警一行 + 清；
  新鮮哨兵（並行 SessionEnd 進行中）不誤清不誤報
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest  # noqa: F401

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE = HOOKS_DIR.parent
for p in (str(HOOKS_DIR), str(CLAUDE), str(CLAUDE / "lib")):
    if p not in sys.path:
        sys.path.insert(0, p)

import wg_core  # noqa: E402
from handlers import session_end as se  # noqa: E402
from handlers import session_start as ss  # noqa: E402


@pytest.fixture
def wdir(tmp_path, monkeypatch):
    d = tmp_path / "workflow"
    d.mkdir()
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", d)
    return d


def test_arm_and_clear(wdir):
    se._se_sentinel_arm("sid-x")
    p = wdir / "se-sentinel" / "sid-x.json"
    assert p.exists()
    se._se_sentinel_clear("sid-x")
    assert not p.exists()


def test_empty_session_id_noop(wdir):
    se._se_sentinel_arm("")
    assert not (wdir / "se-sentinel").exists()


def test_residual_warns_and_clears(wdir):
    se._se_sentinel_arm("sid-old")
    p = wdir / "se-sentinel" / "sid-old.json"
    old = time.time() - 120
    os.utime(p, (old, old))  # 殘留超過 60s 窗
    lines: list = []
    ss._check_se_sentinel_residual(lines)
    assert len(lines) == 1
    assert "SE-Sentinel" in lines[0] and "sid-old" in lines[0]
    assert not p.exists()  # 讀後清，不重複告警
    lines2: list = []
    ss._check_se_sentinel_residual(lines2)
    assert lines2 == []


def test_fresh_sentinel_not_flagged(wdir):
    # 剛 arm（並行 SessionEnd 可能還在跑）→ 不告警不清
    se._se_sentinel_arm("sid-live")
    lines: list = []
    ss._check_se_sentinel_residual(lines)
    assert lines == []
    assert (wdir / "se-sentinel" / "sid-live.json").exists()

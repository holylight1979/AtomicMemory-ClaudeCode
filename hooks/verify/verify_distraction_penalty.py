"""verify_distraction_penalty.py — Phase A 分心懲罰（注入重排）。

守住 wg_atoms.compute_injection_rank 不變式（憲法 Context Distraction 對策，
_AIDocs/context-memory-governance.md）：
- rank = ACT-R activation − w·log10(read_hits+1)·(1−wilson_lb)
- 只罰「n≥min_n 且 Wilson 下界低（已被證明沒用）」者；新 atom/樣本不足不罰
- 關閉 / 無 access / read_hits=0 → 退回純 activation（fail-open）

受控 tmp access.json，不依賴磁碟既有 atom。Design: plans/cozy-sauteeing-jellyfish.md Phase A。
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import pytest  # noqa: F401

HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify/ → hooks/
CLAUDE = HOOKS_DIR.parent
for p in (str(HOOKS_DIR), str(CLAUDE), str(CLAUDE / "lib")):
    if p not in sys.path:
        sys.path.insert(0, p)

import wg_atoms  # noqa: E402
from lib import atom_access as A  # noqa: E402

# stability_gamma 釘 0：本檔守「分心懲罰」不變式，需與個別化 decay（會改
# activation 本身）隔離——對照組 compute_activation 不帶 config（d=0.5）。
# 個別化 decay 的行為由 verify_stability_decay.py 覆蓋。
CFG_ON = {"usefulness": {"distraction_enabled": True, "distraction_weight": 0.5,
                         "min_n": 3, "wilson_z": 1.96, "stability_gamma": 0.0}}
CFG_OFF = {"usefulness": {"distraction_enabled": False, "stability_gamma": 0.0}}

FIXED_NOW = 1_750_000_000.0


@pytest.fixture(autouse=True)
def _fixed_time(monkeypatch):
    # 固定 time.time，使 ACT-R activation 跨呼叫確定（否則時鐘跳動造成 µ 級浮點差，approx 失敗）
    monkeypatch.setattr(wg_atoms.time, "time", lambda: FIXED_NOW)


def _write_access(tmp_path, name, *, read_hits, alpha, beta, ts=None):
    now = time.time()
    data = {
        "schema": "atom-access-v3",
        "read_hits": read_hits,
        "useful_hits": alpha,
        "used_fail": beta,
        "timestamps": ts if ts is not None else [now - 100.0, now - 200.0],
        "first_seen": "2026-01-01",
    }
    (tmp_path / f"{name}.access.json").write_text(
        json.dumps(data), encoding="utf-8")


def _expected_penalty(read_hits, alpha, beta, weight=0.5, z=1.96):
    st = A.usefulness_stats({"useful_hits": alpha, "used_fail": beta}, z=z)
    return weight * math.log10(read_hits + 1) * (1.0 - st["lower_bound"])


def test_disabled_returns_pure_activation(tmp_path):
    _write_access(tmp_path, "a", read_hits=50, alpha=1, beta=5)
    act = wg_atoms.compute_activation("a", tmp_path)
    assert wg_atoms.compute_injection_rank("a", tmp_path, CFG_OFF) == act


def test_no_config_returns_pure_activation(tmp_path):
    _write_access(tmp_path, "a", read_hits=50, alpha=1, beta=5)
    act = wg_atoms.compute_activation("a", tmp_path)
    assert wg_atoms.compute_injection_rank("a", tmp_path, None) == act


def test_no_access_fail_open(tmp_path):
    # 無 access 檔 → activation=0.0（中性，新 atom 不被截斷優先犧牲）；
    # penalty 路徑讀到 read_hits=0 → 純 activation
    act = wg_atoms.compute_activation("missing", tmp_path)
    assert act == 0.0
    assert wg_atoms.compute_injection_rank("missing", tmp_path, CFG_ON) == act


def test_low_usefulness_is_penalized(tmp_path):
    # alpha=1,beta=5 → succ=0,fail=4,n=4≥min_n，lb=0 → 滿懲罰
    _write_access(tmp_path, "a", read_hits=50, alpha=1, beta=5)
    act = wg_atoms.compute_activation("a", tmp_path)
    rank = wg_atoms.compute_injection_rank("a", tmp_path, CFG_ON)
    assert rank == pytest.approx(act - _expected_penalty(50, 1, 5))
    assert rank < act  # 確實被降權


def test_insufficient_n_no_penalty(tmp_path):
    # alpha=1,beta=1 → n=0 < min_n → 不罰（保守，防壓新 atom）
    _write_access(tmp_path, "a", read_hits=50, alpha=1, beta=1)
    act = wg_atoms.compute_activation("a", tmp_path)
    assert wg_atoms.compute_injection_rank("a", tmp_path, CFG_ON) == act


def test_zero_read_hits_no_penalty(tmp_path):
    # read_hits=0（從未注入過）→ 純 activation，即使 n≥min_n
    _write_access(tmp_path, "a", read_hits=0, alpha=1, beta=5)
    act = wg_atoms.compute_activation("a", tmp_path)
    assert wg_atoms.compute_injection_rank("a", tmp_path, CFG_ON) == act


def test_high_usefulness_small_penalty(tmp_path):
    # 高效用(alpha=7,beta=1,lb≈0.61) 懲罰應遠小於低效用同 read_hits 者
    _write_access(tmp_path, "good", read_hits=50, alpha=7, beta=1)
    _write_access(tmp_path, "bad", read_hits=50, alpha=1, beta=5)
    pen_good = _expected_penalty(50, 7, 1)
    pen_bad = _expected_penalty(50, 1, 5)
    assert pen_good < pen_bad
    rank_good = wg_atoms.compute_injection_rank("good", tmp_path, CFG_ON)
    act_good = wg_atoms.compute_activation("good", tmp_path)
    assert rank_good == pytest.approx(act_good - pen_good)

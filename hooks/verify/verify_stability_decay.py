"""verify_stability_decay.py — ACT-R 個別化 decay（效用高者衰減更慢）。

守住 wg_atoms 契約：
- _decay_exponent：d = clamp(0.5 − stability_gamma·wilson_lb, 0.3, 0.5)
- 無 config（legacy caller）/ γ=0 / 無效用樣本（n=0）→ d=0.5 不變（fail-open）
- compute_activation：高效用 atom 對同一組舊 timestamps 算出的 activation
  高於固定 d=0.5（衰減更慢＝記憶更穩固）
- compute_injection_rank 把 config 傳進 activation（排序路徑吃到個別化）
"""

from __future__ import annotations

import json
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

CFG = {"usefulness": {"stability_gamma": 0.3, "wilson_z": 1.28}}
CFG_OFF = {"usefulness": {"stability_gamma": 0.0}}

FIXED_NOW = 1_750_000_000.0


@pytest.fixture(autouse=True)
def _fixed_time(monkeypatch):
    monkeypatch.setattr(wg_atoms.time, "time", lambda: FIXED_NOW)


def _write_access(tmp_path, name, *, alpha, beta, ts):
    data = {
        "schema": "atom-access-v3",
        "read_hits": 5,
        "useful_hits": alpha,
        "used_fail": beta,
        "timestamps": ts,
        "first_seen": "2026-01-01",
    }
    (tmp_path / f"{name}.access.json").write_text(json.dumps(data), encoding="utf-8")


# ─── _decay_exponent 純函式 ─────────────────────────────────────────────────


def test_no_config_keeps_default_d():
    assert wg_atoms._decay_exponent({"useful_hits": 9, "used_fail": 1}, None) == 0.5


def test_gamma_zero_disables():
    assert wg_atoms._decay_exponent({"useful_hits": 9, "used_fail": 1}, CFG_OFF) == 0.5


def test_no_evidence_keeps_default_d():
    # α=β=1（prior）→ n=0 → 不動
    assert wg_atoms._decay_exponent({"useful_hits": 1, "used_fail": 1}, CFG) == 0.5


def test_high_usefulness_lowers_d():
    d = wg_atoms._decay_exponent({"useful_hits": 9, "used_fail": 1}, CFG)
    assert 0.3 <= d < 0.5


def test_clamp_floor():
    # lb→1 的極端：0.5 − γ·1 = 0.2 → clamp 到 0.3
    cfg = {"usefulness": {"stability_gamma": 0.9, "wilson_z": 0.01}}
    d = wg_atoms._decay_exponent({"useful_hits": 1000, "used_fail": 1}, cfg)
    assert d == pytest.approx(0.3)


def test_zero_lb_keeps_default_d():
    # 全失敗（lb=0，n>0）→ d 不動
    assert wg_atoms._decay_exponent({"useful_hits": 1, "used_fail": 6}, CFG) == 0.5


# ─── compute_activation 行為 ────────────────────────────────────────────────


def test_useful_atom_decays_slower(tmp_path):
    old_ts = [FIXED_NOW - 30 * 86400, FIXED_NOW - 20 * 86400]  # 舊記憶
    _write_access(tmp_path, "useful", alpha=9, beta=1, ts=old_ts)
    _write_access(tmp_path, "plain", alpha=1, beta=1, ts=old_ts)
    act_useful = wg_atoms.compute_activation("useful", tmp_path, CFG)
    act_plain = wg_atoms.compute_activation("plain", tmp_path, CFG)
    act_useful_legacy = wg_atoms.compute_activation("useful", tmp_path)  # 無 config → d=0.5
    assert act_useful > act_plain          # 效用高者同齡記憶較強
    assert act_useful > act_useful_legacy  # 個別化 d<0.5 → 衰減慢 → activation 高
    assert act_plain == act_useful_legacy  # 無效用樣本 → 與固定 d 相同


def test_missing_sidecar_neutral(tmp_path):
    assert wg_atoms.compute_activation("nope", tmp_path, CFG) == 0.0


def test_injection_rank_uses_config_decay(tmp_path):
    old_ts = [FIXED_NOW - 30 * 86400]
    _write_access(tmp_path, "useful", alpha=9, beta=1, ts=old_ts)
    cfg = {"usefulness": {"stability_gamma": 0.3, "wilson_z": 1.28,
                          "distraction_enabled": False}}
    rank = wg_atoms.compute_injection_rank("useful", tmp_path, cfg)
    assert rank == pytest.approx(wg_atoms.compute_activation("useful", tmp_path, cfg))
    assert rank > wg_atoms.compute_activation("useful", tmp_path)  # 個別化生效


# ─── access cache 共用 ──────────────────────────────────────────────────────


def test_access_cache_shared_single_read(tmp_path):
    _write_access(tmp_path, "a", alpha=3, beta=1, ts=[FIXED_NOW - 100])
    cache: dict = {}
    first = wg_atoms.compute_activation("a", tmp_path, CFG, access_cache=cache)
    (tmp_path / "a.access.json").unlink()  # 刪檔後 cache 仍供後續呼叫
    second = wg_atoms.compute_activation("a", tmp_path, CFG, access_cache=cache)
    assert first == second != 0.0
    # 無 cache → 重讀（檔已刪）→ 中性 0.0
    assert wg_atoms.compute_activation("a", tmp_path, CFG) == 0.0

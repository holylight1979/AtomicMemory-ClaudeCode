"""verify_usefulness_access_phase2.py — Phase 2 (#2) 效用閉環 access 層守門.

守住 lib/atom_access.py 的 Phase 2 不變式：
1. schema v2→v3 冪等 migration：缺 useful_hits/used_fail → 補 prior(1)，可重入不壞既有計數。
2. record_usefulness 三值語意：used+success→α++ / used+fail→β++ / unused|unknown→no-op（不寫檔）。
3. decay_usefulness：α←1+λ(α−1); β←1+λ(β−1)；無證據(1,1)不寫；每日護欄同日 no-op。
4. Wilson 下界（z=1.28）+ usefulness_stats + 升/降資格（遲滯帶：升≥0.6 n≥3、降≤0.35 n≥5）。
5. _coerce_num：整數存 int、非整數存 float。

純函式 + tmp atom 路徑，不污染現役 access.json。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

LIB_PARENT = Path(__file__).resolve().parent.parent.parent  # lib/verify/ → ~/.claude/
if str(LIB_PARENT) not in sys.path:
    sys.path.insert(0, str(LIB_PARENT))

from lib import atom_access as A  # noqa: E402


@pytest.fixture(autouse=True)
def _silence_audit(monkeypatch):
    """避免單元測試往現役 audit log 落檔。"""
    monkeypatch.setattr(A, "_audit_log", lambda *a, **k: None)


@pytest.fixture
def atom_md(tmp_path):
    p = tmp_path / "atom-x.md"
    p.write_text("# atom-x\n- [臨] body\n", encoding="utf-8")
    return p


# ─── 1. schema v2→v3 冪等 migration ──────────────────────────────────────────


def test_normalize_v2_to_v3_adds_prior_and_marks_upgraded():
    d, up = A._normalize({"schema": "atom-access-v2", "read_hits": 7, "confirmations": 2})
    assert up is True
    assert d["schema"] == "atom-access-v3"
    assert d["useful_hits"] == A.USEFULNESS_PRIOR == 1
    assert d["used_fail"] == 1
    assert d["read_hits"] == 7 and d["confirmations"] == 2  # 既有計數保留


def test_normalize_idempotent_rerun_no_upgrade():
    d, _ = A._normalize({"schema": "atom-access-v2", "read_hits": 7})
    d2, up2 = A._normalize(dict(d))
    assert up2 is False  # 第二次不再判定為 migration


def test_normalize_preserves_existing_alpha_beta():
    d, up = A._normalize({"schema": "atom-access-v3", "useful_hits": 9, "used_fail": 4})
    assert d["useful_hits"] == 9 and d["used_fail"] == 4  # 不被重置為 prior


def test_read_access_missing_file_returns_v3_defaults(atom_md):
    acc = A.read_access(atom_md.with_suffix(".md"))  # 無 .access.json
    assert acc["useful_hits"] == 1 and acc["used_fail"] == 1
    assert acc["schema"] == "atom-access-v3"


# ─── 2. record_usefulness 三值語意 ───────────────────────────────────────────


def test_record_success_increments_alpha(atom_md):
    a, b = A.record_usefulness(atom_md, used=True, success=True, source="test")
    assert (a, b) == (2, 1)
    acc = A.read_access(atom_md)
    assert acc["useful_hits"] == 2 and acc["used_fail"] == 1


def test_record_fail_increments_beta(atom_md):
    a, b = A.record_usefulness(atom_md, used=True, success=False, source="test")
    assert (a, b) == (1, 2)


def test_record_unused_is_noop_no_file(atom_md):
    a, b = A.record_usefulness(atom_md, used=False, success=True, source="test")
    assert (a, b) == (1, 1)
    assert not A._access_path(atom_md).exists()  # no-op 不建檔


def test_record_unknown_is_noop(atom_md):
    a, b = A.record_usefulness(atom_md, used=True, success=None, source="test")
    assert (a, b) == (1, 1)


def test_record_accumulates(atom_md):
    for _ in range(4):
        A.record_usefulness(atom_md, used=True, success=True, source="test")
    A.record_usefulness(atom_md, used=True, success=False, source="test")
    acc = A.read_access(atom_md)
    assert acc["useful_hits"] == 5 and acc["used_fail"] == 2


def test_record_invalid_source_raises(atom_md):
    with pytest.raises(ValueError):
        A.record_usefulness(atom_md, used=True, success=True, source="bogus")


# ─── 3. decay_usefulness ─────────────────────────────────────────────────────


def test_decay_pulls_toward_prior(atom_md):
    for _ in range(4):
        A.record_usefulness(atom_md, used=True, success=True, source="test")  # α=5
    a, b = A.decay_usefulness(atom_md, lam=0.97, source="test")
    assert abs(a - (1 + 0.97 * 4)) < 1e-6  # 4.88
    assert b == 1


def test_decay_no_evidence_no_change(atom_md):
    a, b = A.decay_usefulness(atom_md, lam=0.97, source="test")
    assert (a, b) == (1.0, 1.0)
    assert not A._access_path(atom_md).exists()  # 無證據不建檔


def test_decay_daily_guard_same_day_noop(atom_md):
    """每日護欄：首次衰減記 last_decay_date；同日再呼叫 no-op（不重複打折）。"""
    for _ in range(4):
        A.record_usefulness(atom_md, used=True, success=True, source="test")  # α=5
    a1, b1 = A.decay_usefulness(atom_md, lam=0.97, source="test")
    acc = A.read_access(atom_md)
    assert acc.get("last_decay_date")  # 首次衰減落日期戳
    a2, b2 = A.decay_usefulness(atom_md, lam=0.97, source="test")  # 同日 → no-op
    assert (a2, b2) == (a1, b1)
    acc2 = A.read_access(atom_md)
    assert acc2["useful_hits"] == acc["useful_hits"]  # 檔上值未再衰減


def test_decay_stale_date_decays_again(atom_md):
    """last_decay_date 非今日 → 正常衰減並更新日期。"""
    for _ in range(4):
        A.record_usefulness(atom_md, used=True, success=True, source="test")  # α=5
    A.decay_usefulness(atom_md, lam=0.97, source="test")
    # 手動把日期改成昨日等效（非今日即可）
    p = A._access_path(atom_md)
    import json as _json
    raw = _json.loads(p.read_text(encoding="utf-8"))
    raw["last_decay_date"] = "2000-01-01"
    p.write_text(_json.dumps(raw), encoding="utf-8")
    a, b = A.decay_usefulness(atom_md, lam=0.97, source="test")
    assert abs(a - (1 + 0.97 * 0.97 * 4)) < 1e-6  # 二次衰減生效
    acc = A.read_access(atom_md)
    assert acc["last_decay_date"] != "2000-01-01"


def test_coerce_num_int_vs_float():
    assert A._coerce_num(3.0) == 3 and isinstance(A._coerce_num(3.0), int)
    assert abs(A._coerce_num(4.88) - 4.88) < 1e-9 and isinstance(A._coerce_num(4.88), float)


# ─── 4. Wilson / stats / 升降資格（遲滯帶）─────────────────────────────────────


def test_wilson_default_z_is_1_28():
    assert A.WILSON_Z_DEFAULT == 1.28


def test_wilson_calibrated_values_z128():
    # 校準基準點（z=1.28 實算值；python 直接算 Wilson 公式所得）
    assert abs(A.wilson_lower_bound(3, 3) - 0.6467747499) < 1e-9
    assert abs(A.wilson_lower_bound(4, 4) - 0.7094211124) < 1e-9
    assert abs(A.wilson_lower_bound(2, 3) - 0.3215087330) < 1e-9
    assert abs(A.wilson_lower_bound(3, 4) - 0.4328950624) < 1e-9


def test_wilson_monotonic_and_bounds():
    assert A.wilson_lower_bound(0, 0) == 0.0
    assert A.wilson_lower_bound(0, 3) == 0.0
    assert 0.64 < A.wilson_lower_bound(3, 3) < 0.65  # 3 連勝即過升門 0.6
    assert A.wilson_lower_bound(6, 6) >= 0.6


def test_usefulness_stats_subtracts_prior():
    st = A.usefulness_stats({"useful_hits": 5, "used_fail": 1})
    assert st["successes"] == 4 and st["failures"] == 0 and st["n"] == 4
    assert abs(st["lower_bound"] - 0.7094) < 1e-3


def test_promote_eligible_needs_lb_and_n():
    assert A.usefulness_promote_eligible({"useful_hits": 7, "used_fail": 1}) is True   # n=6 lb≈0.79
    assert A.usefulness_promote_eligible({"useful_hits": 5, "used_fail": 1}) is True   # n=4 lb≈0.71
    assert A.usefulness_promote_eligible({"useful_hits": 5, "used_fail": 3}) is False  # lb≈0.41<0.6
    assert A.usefulness_promote_eligible({"useful_hits": 3, "used_fail": 1}) is False  # n=2<3


def test_demote_candidate_needs_n_ge_5():
    assert A.DEMOTE_MIN_N_DEFAULT == 5
    assert A.usefulness_demote_candidate({"useful_hits": 1, "used_fail": 6}) is True   # lb=0 n=5
    assert A.usefulness_demote_candidate({"useful_hits": 1, "used_fail": 4}) is False  # lb=0 但 n=3<5
    assert A.usefulness_demote_candidate({"useful_hits": 1, "used_fail": 1}) is False  # n=0
    assert A.usefulness_demote_candidate({"useful_hits": 7, "used_fail": 1}) is False  # 高分不降


def test_hysteresis_gap_neither_promote_nor_demote():
    # 中間帶（lb 介於 0.35~0.6）→ 既不升也不降（遲滯，防震盪）
    acc = {"useful_hits": 5, "used_fail": 3}  # succ=4 fail=2 n=6，lb≈0.41
    assert A.usefulness_promote_eligible(acc) is False
    assert A.usefulness_demote_candidate(acc) is False

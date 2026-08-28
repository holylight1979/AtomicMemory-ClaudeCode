"""verify_injection_redundancy_gate.py — 同題去冗閘（ups_inject.redundant_with / _redundancy_cfg）。

規則：與本 turn 已全文注入者 trigger 精確重疊 ≥ min_shared → 回代表者名稱；
只比精確字串（小寫），子字串不算；自身 trigger 數不足門檻不判；門檻 ≤0 關閉。
"""
from __future__ import annotations

import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parent.parent
for p in (HOOKS, HOOKS / "handlers"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import ups_inject  # noqa: E402


def test_exact_overlap_reaches_threshold_returns_representative():
    full_seen = [("A", ups_inject._norm_triggers(["上GIT", "git status", "收尾", "staging"]))]
    hit = ups_inject.redundant_with(["收尾", "Git Status", "上git", "工作樹"], full_seen, 3)
    assert hit == "A"


def test_below_threshold_is_not_redundant():
    full_seen = [("A", ups_inject._norm_triggers(["上GIT", "git status", "收尾"]))]
    assert ups_inject.redundant_with(["收尾", "git status", "別的"], full_seen, 3) is None


def test_substring_overlap_does_not_count():
    """子字串（staging ⊂ 選擇性 staging）不採計——泛 trigger 噪音。"""
    full_seen = [("A", ups_inject._norm_triggers(["staging", "commit", "push"]))]
    assert ups_inject.redundant_with(["選擇性 staging", "git commit", "git push"], full_seen, 3) is None


def test_own_trigger_count_below_threshold_skips():
    full_seen = [("A", ups_inject._norm_triggers(["x", "y", "z"]))]
    assert ups_inject.redundant_with(["x", "y"], full_seen, 3) is None


def test_threshold_zero_disables():
    full_seen = [("A", ups_inject._norm_triggers(["x", "y", "z"]))]
    assert ups_inject.redundant_with(["x", "y", "z"], full_seen, 0) is None


def test_first_matching_representative_wins():
    full_seen = [("A", ups_inject._norm_triggers(["a", "b", "c"])),
                 ("B", ups_inject._norm_triggers(["a", "b", "c", "d"]))]
    assert ups_inject.redundant_with(["a", "b", "c", "d"], full_seen, 3) == "A"


def test_cfg_defaults_and_override():
    assert ups_inject._redundancy_cfg({}) == (True, 3)
    assert ups_inject._redundancy_cfg({"injection": {"redundancy_gate": {"enabled": False, "min_shared_triggers": 5}}}) == (False, 5)


def test_library_wide_pairs_are_few():
    """全庫精確重疊 ≥3 的 atom 對必須極少（門檻保守性守衛；超過 20 對＝trigger 詞庫漂移，該回頭看）。"""
    import itertools
    import json
    idx = HOOKS.parent / "memory" / "_atom_index.json"
    if not idx.exists():
        return
    atoms = json.loads(idx.read_text(encoding="utf-8")).get("atoms", [])
    n = 0
    for a, b in itertools.combinations(atoms, 2):
        if len(ups_inject._norm_triggers(a.get("triggers")) & ups_inject._norm_triggers(b.get("triggers"))) >= 3:
            n += 1
    assert n <= 20, f"same-topic pairs at >=3 shared triggers: {n}"

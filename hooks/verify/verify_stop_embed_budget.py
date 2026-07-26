"""verify_stop_embed_budget.py — Stop 端 embedding tiebreak 全 turn 時間預算（A4）。

契約（handlers.stop._budgeted_embed_fn）：
- 累計耗時 ≥ usefulness.embed_budget_s → 之後一律回 None（lexical fallback）
- 預算耗盡浮 stderr 一行（fail-open 必告知），且只警一次
- raw fn None → None；budget ≤ 0 → 原樣 passthrough（關閉包裝）
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest  # noqa: F401

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE = HOOKS_DIR.parent
for p in (str(HOOKS_DIR), str(CLAUDE), str(CLAUDE / "lib")):
    if p not in sys.path:
        sys.path.insert(0, p)

from handlers import stop as st  # noqa: E402


def test_none_passthrough():
    assert st._budgeted_embed_fn(None, {}) is None


def test_nonpositive_budget_passthrough():
    raw = lambda a, b: 0.9  # noqa: E731
    assert st._budgeted_embed_fn(raw, {"embed_budget_s": 0}) is raw


def test_budget_exhaustion_falls_back(monkeypatch, capsys):
    # 假時鐘：每次呼叫耗 2s → 第 1 次成功（累計 2s < 3s）、第 2 次成功（累計 4s）、
    # 第 3 次起預算已爆 → None + 單次 stderr 告警
    clock = [0.0]

    def fake_monotonic():
        return clock[0]

    monkeypatch.setattr(st.time, "monotonic", fake_monotonic)

    def raw(a, b):
        clock[0] += 2.0
        return 0.9

    fn = st._budgeted_embed_fn(raw, {"embed_budget_s": 3.0})
    assert fn("a", "b") == 0.9
    assert fn("a", "b") == 0.9   # 呼叫前 spent=2.0 < 3.0 → 仍放行
    assert fn("a", "b") is None  # spent=4.0 ≥ 3.0 → 預算爆
    assert fn("a", "b") is None
    err = capsys.readouterr().err
    assert err.count("embed tiebreak turn budget exhausted") == 1


def test_within_budget_untouched(monkeypatch):
    monkeypatch.setattr(st.time, "monotonic", lambda: 0.0)  # 零耗時
    calls = []

    def raw(a, b):
        calls.append(1)
        return 0.7

    fn = st._budgeted_embed_fn(raw, {"embed_budget_s": 3.0})
    for _ in range(5):
        assert fn("a", "b") == 0.7
    assert len(calls) == 5

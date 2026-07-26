"""verify_related_relevance_gate.py — Phase C 注入 relevance gate（related-spread 裁切）。

守住 ups_inject._filter_related_by_relevance 不變式（憲法 Context Confusion 對策，
_AIDocs/context-memory-governance.md）：
- 只動 related-spread（非 prompt 命中），主迴圈候選不受影響 → 不誤殺
- skip_demoted：剔除「已證明低效用」(demote_candidate, n≥min_n)；絕不誤殺新/未證 atom
- max_related：依注入 rank 降序保留前 N（最小高訊號集）
- 關閉 → 原樣 passthrough（kill-switch）

受控 tmp access.json，不依賴磁碟既有 atom。Design: plans/cozy-sauteeing-jellyfish.md Phase C。
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify/ → hooks/
CLAUDE = HOOKS_DIR.parent
for p in (str(HOOKS_DIR), str(CLAUDE), str(CLAUDE / "lib")):
    if p not in sys.path:
        sys.path.insert(0, p)

import wg_atoms  # noqa: E402
from handlers.ups_inject import _filter_related_by_relevance  # noqa: E402

FIXED_NOW = 1_750_000_000.0


@pytest.fixture(autouse=True)
def _fixed_time(monkeypatch):
    monkeypatch.setattr(wg_atoms.time, "time", lambda: FIXED_NOW)


def _write_access(tmp, name, *, read_hits=0, alpha=1, beta=1, ts=None):
    data = {
        "schema": "atom-access-v3", "read_hits": read_hits,
        "useful_hits": alpha, "used_fail": beta,
        "timestamps": ts if ts is not None else [], "first_seen": "2026-01-01",
    }
    (tmp / f"{name}.access.json").write_text(json.dumps(data), encoding="utf-8")


def _entry(tmp, name):
    # rel_path=f"{name}.md" → rdir = base_dir = tmp（access 檔直接放 tmp）
    return ((name, f"{name}.md", []), tmp)


def _cfg(**related_gate):
    rg = {"enabled": True, "skip_demoted": True, "max_related": 6}
    rg.update(related_gate)
    return {
        "injection": {"related_gate": rg},
        # distraction 關閉 → injection_rank == 純 activation，便於斷言 cap 排序
        "usefulness": {"min_n": 3, "wilson_z": 1.96, "demote_lb": 0.35,
                       "distraction_enabled": False},
    }


def _names(entries):
    return [e[0][0] for e in entries]


def test_disabled_passthrough(tmp_path):
    ents = [_entry(tmp_path, "a"), _entry(tmp_path, "b")]
    kept, skipped = _filter_related_by_relevance(ents, _cfg(enabled=False))
    assert kept == ents and skipped == []


def test_empty_passthrough(tmp_path):
    kept, skipped = _filter_related_by_relevance([], _cfg())
    assert kept == [] and skipped == []


def test_skip_demoted(tmp_path):
    # bad: alpha=1,beta=7 → succ=0,fail=6,n=6≥demote_min_n(5)，lb=0≤demote_lb → demote_candidate → 剔除
    _write_access(tmp_path, "bad", read_hits=20, alpha=1, beta=7)
    _write_access(tmp_path, "ok", read_hits=1, alpha=1, beta=1)  # n=0 → 不剔
    kept, skipped = _filter_related_by_relevance(
        [_entry(tmp_path, "bad"), _entry(tmp_path, "ok")], _cfg())
    assert "ok" in _names(kept) and "bad" not in _names(kept)
    assert ("bad", "demoted") in skipped


def test_new_atom_never_skipped(tmp_path):
    # 全新 atom（無 access、n=0）→ 不是 demote_candidate → 保留（不誤殺）
    kept, skipped = _filter_related_by_relevance([_entry(tmp_path, "fresh")], _cfg())
    assert _names(kept) == ["fresh"] and skipped == []


def test_max_related_cap_keeps_top_rank(tmp_path):
    # 三個 related，依 activation（時間近→高）排序，cap=2 → 保留最近兩個、最舊者 min_set_cap
    _write_access(tmp_path, "recent", ts=[FIXED_NOW - 10.0])
    _write_access(tmp_path, "mid", ts=[FIXED_NOW - 5000.0])
    _write_access(tmp_path, "old", ts=[FIXED_NOW - 5_000_000.0])
    ents = [_entry(tmp_path, "old"), _entry(tmp_path, "recent"), _entry(tmp_path, "mid")]
    kept, skipped = _filter_related_by_relevance(ents, _cfg(max_related=2))
    assert _names(kept) == ["recent", "mid"]  # rank 降序
    assert ("old", "min_set_cap") in skipped

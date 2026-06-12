"""verify_failures_routing.py — Failures 路由判定（2026-06-12 funnel 缺口修補）.

不變式：
1. feedback- 前綴 title → 路由 Failures（既有行為不變）。
2. 已註冊在 _atom_index.json、path 落 _AIDocs/Failures/ 的非 feedback- atom
   （cognitive-patterns / memory-pipeline-*）→ 也路由 Failures，append/replace
   才找得到物理檔（修補前在 memory/ 找不到而失敗，py/js 雙端同病）。
3. 一般 core atom（decisions 等）→ 不路由。

依賴本 repo 真實 _atom_index.json（Failures 9 atom 為穩定 fixture）。
"""

from __future__ import annotations

import sys
from pathlib import Path

CLAUDE = Path(__file__).resolve().parent.parent.parent  # lib/verify/ → ~/.claude
sys.path.insert(0, str(CLAUDE))

from lib.atom_locations import is_failures_routed_title  # noqa: E402
from lib.atom_io import write_atom  # noqa: E402


def test_feedback_prefix_routes():
    assert is_failures_routed_title("feedback-whatever-new") is True


def test_registered_failures_stem_routes():
    # 非 feedback- 前綴但物理在 Failures 的兩顆既有 atom
    assert is_failures_routed_title("memory-pipeline-silent-failure-2026-05") is True
    assert is_failures_routed_title("cognitive-patterns") is True


def test_plain_core_atom_not_routed():
    assert is_failures_routed_title("decisions") is False
    assert is_failures_routed_title("toolchain") is False


def test_empty_title_not_routed():
    assert is_failures_routed_title("") is False
    assert is_failures_routed_title(None) is False


def test_append_resolves_failures_atom_dry_run():
    # 修補前：Atom not found（append 在 memory/ 找檔）。修補後 dry_run ok。
    r = write_atom(
        title="memory-pipeline-silent-failure-2026-05",
        scope="global", confidence="[臨]",
        triggers=["memory-review"],
        knowledge=["[臨] dry-run probe"],
        mode="append", source="mcp", dry_run=True,
    )
    assert r.ok, f"append dry_run failed: {r.error}"

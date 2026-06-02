"""verify_failures_atom_funnel_guard.py — AtomFunnelBlock 對 _AIDocs/Failures/ 的覆蓋。

覆蓋缺口（b3b5196 commit 訊息附帶發現）：check_memory_path_block 原只攔
`.claude/memory/` 樹下的 atom .md，不攔物理居 `_AIDocs/Failures/` 的失敗 atom
（feedback-* / cognitive-patterns / memory-pipeline-*），後者直接 Write/Edit 會繞過
lib.atom_io funnel + audit。

本檔守住補攔後的不變式：
  1. Failures 下「註冊 atom」（stem 在 index）→ BLOCK
  2. Failures 下「legacy 失敗筆記 / _INDEX.md」（stem 不在 index）→ allow（不誤擋參考文件）
  3. memory/ 樹下 atom 仍 BLOCK（既有行為不回歸）、MEMORY.md 等白名單仍 allow
  4. WG_DISABLE_ATOM_GUARD=1 對 Failures atom 仍可緊急 bypass
  5. Edit 與 Write 同等攔截；非 .md 不攔
  6. failures_atom_stems 為 None（lib import 失敗）→ 退化「不攔」，不致命
  7. 結構不變式：funnel 白名單不得再含 'Failures'（避免 case-fix 復發覆蓋缺口）

以 monkeypatch 注入固定 stems，與現役 _atom_index.json 隔離。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify/ → hooks/
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

import wg_core  # noqa: E402
from wg_core import check_memory_path_block, _is_failures_atom_path  # noqa: E402


STEMS = {"feedback-foo", "cognitive-patterns", "memory-pipeline-silent-failure-2026-05"}

FAILURES = "/x/.claude/_AIDocs/Failures"
MEMORY = "/x/.claude/memory"


@pytest.fixture
def fixed_stems(monkeypatch):
    """注入固定 failures stems，與現役 index 隔離。"""
    monkeypatch.setattr(wg_core, "failures_atom_stems", lambda: set(STEMS))
    return STEMS


def _block(path, tool="Write"):
    return check_memory_path_block(tool, {"file_path": path})


# ─── 1. 註冊失敗 atom → BLOCK ─────────────────────────────────────────────────


@pytest.mark.parametrize("name", sorted(STEMS))
def test_registered_failures_atom_blocked(fixed_stems, name):
    msg = _block(f"{FAILURES}/{name}.md")
    assert msg is not None and "AtomFunnelBlock" in msg


# ─── 2. legacy 失敗筆記 / _INDEX.md（stem 不在 index）→ allow ─────────────────


@pytest.mark.parametrize("name", [
    "env-traps", "silent-failures", "wrong-assumptions",
    "codex-windows-sandbox-1385", "misdiagnosis-verify-first", "_INDEX",
])
def test_unregistered_failures_doc_allowed(fixed_stems, name):
    assert _block(f"{FAILURES}/{name}.md") is None


# ─── 3. memory/ 既有行為不回歸 ───────────────────────────────────────────────


def test_memory_atom_still_blocked(fixed_stems):
    assert _block(f"{MEMORY}/decisions.md") is not None


@pytest.mark.parametrize("name", ["MEMORY.md", "_ATOM_INDEX.md", "_atom_index.json"])
def test_memory_whitelist_still_allowed(fixed_stems, name):
    # .json 非 .md 本就放行；MEMORY.md / _ATOM_INDEX.md 白名單放行
    assert _block(f"{MEMORY}/{name}") is None


# ─── 4. 緊急 bypass 對 Failures atom 仍有效 ──────────────────────────────────


def test_disable_guard_env_bypasses_failures(fixed_stems, monkeypatch):
    monkeypatch.setenv("WG_DISABLE_ATOM_GUARD", "1")
    assert _block(f"{FAILURES}/feedback-foo.md") is None


# ─── 5. Edit 同等攔截；非 .md 不攔 ───────────────────────────────────────────


def test_edit_tool_also_blocks(fixed_stems):
    assert _block(f"{FAILURES}/feedback-foo.md", tool="Edit") is not None


def test_non_md_in_failures_not_blocked(fixed_stems):
    assert _block(f"{FAILURES}/feedback-foo.access.json") is None
    assert _block(f"{FAILURES}/feedback-foo.txt") is None


def test_non_write_edit_tool_ignored(fixed_stems):
    assert _block(f"{FAILURES}/feedback-foo.md", tool="Read") is None
    assert _block(f"{FAILURES}/feedback-foo.md", tool="Bash") is None


# ─── 6. failures_atom_stems is None → 退化不攔 ───────────────────────────────


def test_stems_none_degrades_to_allow(monkeypatch):
    monkeypatch.setattr(wg_core, "failures_atom_stems", None)
    assert _is_failures_atom_path(Path(f"{FAILURES}/feedback-foo.md")) is False
    assert _block(f"{FAILURES}/feedback-foo.md") is None


# ─── 7. _is_failures_atom_path 直測 ──────────────────────────────────────────


def test_is_failures_atom_path_predicate(fixed_stems):
    assert _is_failures_atom_path(Path(f"{FAILURES}/feedback-foo.md")) is True
    assert _is_failures_atom_path(Path(f"{FAILURES}/env-traps.md")) is False     # 不在 stems
    assert _is_failures_atom_path(Path(f"{FAILURES}/feedback-foo.txt")) is False  # 非 .md
    assert _is_failures_atom_path(Path(f"{MEMORY}/decisions.md")) is False        # 非 Failures 樹


# ─── 8. 結構不變式：funnel 白名單不得再含 'Failures' ─────────────────────────


def test_whitelist_excludes_failures_segment():
    seg = {s.lower() for s in wg_core._WHITELIST_DIR_SEGMENTS}
    assert "failures" not in seg, (
        "funnel 白名單含 'Failures' → 一旦 caller intersect 改 case-insensitive "
        "會豁免整個 Failures 目錄、廢掉本 guard（覆蓋缺口復發）"
    )

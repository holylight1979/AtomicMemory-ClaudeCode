"""verify_handoff_review.py — Codex Companion handoff 自檢（Q2）單元測試。

驗證面（2026-06-24 新增）：
  * _detect_checkpoint：next-phase / handoff 檔 Write/Edit → "handoff_review"；
    其他檔 / Read / toggle off → None；既有 plan_review 不受影響。
  * build_handoff_review_prompt：含 8 問對抗 checklist + handoff 全文 + turn_index 回抄
    + schema 含 handoff_gap category；空文件提示為缺口。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest  # noqa: F401

CLAUDE_DIR = Path(__file__).resolve().parents[3]  # verify/ → codex-companion/ → tools/ → .claude/
COMP_DIR = Path(__file__).resolve().parent.parent  # codex-companion/
sys.path.insert(0, str(COMP_DIR))
sys.path.insert(0, str(CLAUDE_DIR / "hooks"))

import codex_companion as cc  # noqa: E402
import prompts  # noqa: E402

_ON = {"soft_gate": {"handoff_review": True, "architecture_review": False}}
_OFF = {"soft_gate": {"handoff_review": False}}


# ─── _detect_checkpoint ───────────────────────────────────────────────────────


def test_next_phase_write_triggers_handoff_review():
    assert cc._detect_checkpoint("Write", "_staging/next-phase.md", _ON) == "handoff_review"


def test_next_phase_windows_path_triggers():
    p = "C:" + chr(92) + chr(92).join(["", "x", ".claude", "memory", "_staging", "next-phase-2.md"])
    assert cc._detect_checkpoint("Write", p, _ON) == "handoff_review"


def test_handoff_named_file_triggers():
    assert cc._detect_checkpoint("Edit", "_staging/handoff-foo.md", _ON) == "handoff_review"


def test_underscore_variant_triggers():
    assert cc._detect_checkpoint("Write", "next_phase_final.md", _ON) == "handoff_review"


def test_ordinary_atom_does_not_trigger():
    assert cc._detect_checkpoint("Write", "memory/toolchain.md", _ON) is None
    assert cc._detect_checkpoint("Write", "memory/_atom_index.json", _ON) is None


def test_read_does_not_trigger():
    # 只有 Write/Edit 持久化才觸發，Read 不算
    assert cc._detect_checkpoint("Read", "_staging/next-phase.md", _ON) is None


def test_toggle_off_disables():
    assert cc._detect_checkpoint("Write", "_staging/next-phase.md", _OFF) is None


def test_plan_review_unaffected():
    # 既有行為不被新分支影響
    assert cc._detect_checkpoint("ExitPlanMode", "", _ON) == "plan_review"


# ─── build_handoff_review_prompt ──────────────────────────────────────────────


def test_prompt_contains_all_eight_checks():
    p = prompts.build_handoff_review_prompt("# h\n現狀…", user_goal="修 bug", turn_index=3)
    for needle in ("為何而做", "決策理由", "未解問題", "只寫 delta",
                   "load-bearing", "假設 vs 已驗證", "顯式裁決", "首尾"):
        assert needle in p, f"缺檢核項：{needle}"


def test_prompt_echoes_turn_index_and_content():
    p = prompts.build_handoff_review_prompt("LOADBEARING_TOKEN_X", turn_index=9)
    assert "turn_index = 9" in p
    assert "LOADBEARING_TOKEN_X" in p


def test_prompt_schema_has_handoff_gap_category():
    p = prompts.build_handoff_review_prompt("x")
    assert "handoff_gap" in p


def test_empty_content_flagged_as_gap():
    p = prompts.build_handoff_review_prompt("")
    assert "空文件" in p and "嚴重缺口" in p

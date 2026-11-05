"""verify_friction_outcome.py — 使用者本回合糾正 → _detect_turn_outcome 判 fail 的契約。

守住：本回合糾正 fail；舊回合糾正不影響；usefulness.friction_as_fail=False 與 friction.enabled=False 忽略；
fail 優先於完成宣告；無糾正無完成 → None（糾正不會把 unknown 變 success）。
怎麼跑：python hooks/verify/verify_friction_outcome.py（印 FRICTION_OUTCOME_CHECK PASS／FAIL）
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE = HOOKS_DIR.parent
for p in (str(HOOKS_DIR), str(CLAUDE), str(CLAUDE / "lib")):
    if p not in sys.path:
        sys.path.insert(0, p)

from handlers.stop import _detect_turn_outcome  # noqa: E402

DONE = "已完成"


def _state(hit_turn=None):
    s = {"turn_seq": 5, "turn_prompts_seq": 5}
    if hit_turn is not None:
        s["user_correction_hits"] = [{"turn": hit_turn, "kw": ["不對"], "excerpt": "不對", "at": "", "by": "keyword"}]
    return s


def test_correction_this_turn_is_fail():
    assert _detect_turn_outcome(_state(5), "", None, {}) is False


def test_correction_in_earlier_turn_ignored():
    assert _detect_turn_outcome(_state(3), DONE, None, {}) is True


def test_switch_off_ignores_correction():
    cfg = {"usefulness": {"friction_as_fail": False}}
    assert _detect_turn_outcome(_state(5), DONE, None, cfg) is True


def test_friction_disabled_ignores_correction():
    cfg = {"friction": {"enabled": False}}
    assert _detect_turn_outcome(_state(5), DONE, None, cfg) is True


def test_correction_beats_completion_claim():
    assert _detect_turn_outcome(_state(5), DONE, None, {}) is False


def test_no_correction_no_claim_is_unknown():
    assert _detect_turn_outcome(_state(), "", None, {}) is None


if __name__ == "__main__":
    rc = pytest.main(["-q", __file__])
    print("FRICTION_OUTCOME_CHECK PASS" if rc == 0 else "FRICTION_OUTCOME_CHECK FAIL")
    sys.exit(0 if rc == 0 else 1)

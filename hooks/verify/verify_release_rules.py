"""verify_release_rules.py：wg_release_rules 每一條有名字的規則各一組案例（純函式，不碰檔案與 git）。

怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_release_rules.py
test_044_every_rule_has_a_case 檢查 RULES 的每個規則名都出現在本檔：新增規則沒補案例就紅。044 的案例叫 test_044_<規則名小寫>_…，
045 的叫 test_045_…。
端到端（工具→PostToolUse→Stop）的案例在 verify_stop_reconcile.py 的「044」段。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import wg_release_rules as rr  # noqa: E402
import wg_verify_ledger as vl  # noqa: E402


def test_044_every_rule_has_a_case():
    """RULES 的每一條規則名都要在本檔出現（有對應案例）。"""
    src = Path(__file__).read_text(encoding="utf-8").split("def test_044_every_rule_has_a_case", 1)[1]
    missing = [name for name in rr.RULES if f'"{name}"' not in src and f"_{name.lower()}" not in src]
    assert not missing, missing


# ─── SAME_FILE ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("a, b", [
    (r"C:\x\src\a.py", "C:/x/src/a.py"),
    (r"C:\x\src\a.py", r"c:\X\SRC\A.py"),
    (r"C:\x\src\a.py", "C:/x/src/../src/a.py"),
    (r"C:\x\src\a.py", "C:/x/./src/a.py"),
])
def test_044_same_file_spellings(a, b):
    """SAME_FILE：反斜線／正斜線、大小寫、`..`、`.` 都是同一個檔。"""
    assert rr.same_file(a, b) and rr.canon_path(a) == rr.canon_path(b)


def test_044_same_file_different_files():
    assert not rr.same_file(r"C:\x\src\a.py", r"C:\x\src\b.py")
    assert not rr.same_file(r"C:\x\src\a.py", r"C:\x\a.py")


# ─── TURN_SINCE_USER_PROMPT ─────────────────────────────────────────────

def test_044_turn_since_user_prompt_window():
    """TURN_SINCE_USER_PROMPT：使用者在 turn 5 打字、兩則同伴訊息後到 turn 7 → turn 5、6、7 都是本回合，4 不是。"""
    state = {"turn_seq": 7, "turn_prompts_seq": 5}
    since = rr.user_turn(state, 7)
    assert since == 5
    assert [rr.in_turn(t, 7, since) for t in (4, 5, 6, 7, 8)] == [False, True, True, True, False]
    assert rr.in_user_turn(6, state) and not rr.in_user_turn(4, state)


def test_044_turn_since_user_prompt_legacy_and_bad_values():
    """舊 state 沒有 turn_prompts_seq → 只認 turn_seq；t 不是整數（None、字串）→ 不算本回合。"""
    assert rr.user_turn({}, 7) == 7
    assert rr.user_turn({"turn_prompts_seq": True}, 7) == 7
    assert rr.in_turn(7, 7) and not rr.in_turn(6, 7)
    assert not rr.in_turn(None, 7, 5) and not rr.in_turn("x", 7, 5)


def test_044_turn_start_for_subagent_spans_user_turns():
    """子代理這一趟跨使用者回合（turn 5 開始、使用者 turn 7 又打字）→ 本回合從它自己最早一筆紀錄（turn 5）算起；主 session 不受影響。"""
    mods, rcpts = [{"turn_seq": 6}], [{"turn_seq": 5}]
    assert rr.turn_start(7, "sid#agent:a1", mods, rcpts) == 5
    assert rr.turn_start(7, "sid", mods, rcpts) == 7
    assert rr.turn_start(7, "sid#agent:a1", [], []) == 7


# ─── CLAIM_MODIFIER_NOT_OWN ─────────────────────────────────────────────

@pytest.mark.parametrize("text, claim", [
    ("claude-9f 已經把修好的 probe_codegate.py 換上去，043 交付完成。", False),     # 現場原句：轉述別人的動作
    ("換上修好的檔。", False),
    ("我把 a.py 修好了。", True),
    ("這是我修好的。", True),                                                      # 「的」後面是句尾：照算宣稱
    ("修好的檔換上去了，另外 b.py 也修好了。", True),                              # 同一段後面另有自己的宣稱
])
def test_044_claim_modifier_not_own(text, claim):
    """CLAIM_MODIFIER_NOT_OWN：宣稱詞後面直接接「的＋名詞」是形容詞用法，不算自己宣告修好。"""
    assert vl.claims_fixed(text) is claim, text


def test_044_claim_is_modifier_unit():
    clause = "已經把修好的 probe.py 換上去"
    end = clause.index("修好") + 2
    assert rr.claim_is_modifier(clause, end)
    assert not rr.claim_is_modifier("是我修好的", 5)


# ─── EXCLUDED_REGION ────────────────────────────────────────────────────

def test_044_excluded_region():
    """EXCLUDED_REGION：相對專案根比；拿不到根、不在根下、`..` 繞回 src/ 都不排除。"""
    globs = ["workflow/v6-inbox/**", "_AIDocs/**"]
    assert rr.excluded_region(r"c:\proj\workflow\v6-inbox\x\a.py", globs, r"c:\proj")
    assert not rr.excluded_region(r"c:\proj\workflow\v6-inbox\..\..\src\a.py", globs, r"c:\proj")
    assert not rr.excluded_region(r"c:\proj\workflow\v6-inbox\a.py", globs, None)
    assert not rr.excluded_region(r"c:\other\_AIDocs\a.py", globs, r"c:\proj")


# ─── 已不存在的改檔：GONE_OUTSIDE_VCS／GONE_IN_GIT_NOTHING_NEW／MOVED_NEW_CODE_SEEN／GONE_UNVERIFIABLE ─────

def test_044_gone_outside_vcs():
    """GONE_OUTSIDE_VCS：不在任何版控根內（打錯路徑寫到 worktree 外又刪、worktree 被移除）→ 不欠。"""
    v = rr.gone_verdict("need-goal.js", None)
    assert v.rule == "GONE_OUTSIDE_VCS" and v.owed is False and "need-goal.js" in v.why


def test_044_gone_in_git_nothing_new():
    """GONE_IN_GIT_NOTHING_NEW：git 根內、同根沒有新程式檔 → 刪除、不欠。"""
    v = rr.gone_verdict("a.py", "git", [])
    assert v.rule == "GONE_IN_GIT_NOTHING_NEW" and v.owed is False


def test_044_moved_new_code_seen():
    """MOVED_NEW_CODE_SEEN：同根出現新程式檔 → 可能搬走，照欠，證據列出新檔名。"""
    v = rr.gone_verdict("a.py", "git", ["src/moved.py"])
    assert v.rule == "MOVED_NEW_CODE_SEEN" and v.owed is True and "moved.py" in v.why


@pytest.mark.parametrize("kind, failed", [("svn", ""), ("git", "在 C:/r 查 git 回非零")])
def test_044_gone_unverifiable(kind, failed):
    """GONE_UNVERIFIABLE：svn 工作副本、或查 git 失敗 → 判不出去向，照欠。"""
    v = rr.gone_verdict("a.py", kind, [], failed)
    assert v.rule == "GONE_UNVERIFIABLE" and v.owed is True


# ─── OWED_AFTER_LAST_CASE ───────────────────────────────────────────────

def test_044_owed_after_last_case_evidence():
    """OWED_AFTER_LAST_CASE：證據寫出最後一次改的案例是哪個（沒有就說沒有）。"""
    assert "test_a.py" in rr.owed_after_last_case("a.py", "test_a.py").why
    v = rr.owed_after_last_case("a.py", None)
    assert v.rule == "OWED_AFTER_LAST_CASE" and v.owed and "沒有改過仍存在的案例檔" in v.why


# ─── 要查 git 的豁免：規則名登記在 RULES、條件在 wg_verify_ledger（端到端案例見 verify_stop_reconcile 的 042／044 段） ──

def test_044_snapshot_settled_and_net_unchanged_are_registered():
    """SNAPSHOT_SETTLED、NET_UNCHANGED：規則名在 RULES 有登記、說明指向 wg_verify_ledger。"""
    for name in ("SNAPSHOT_SETTLED", "NET_UNCHANGED"):
        assert "wg_verify_ledger" in rr.RULES[name]

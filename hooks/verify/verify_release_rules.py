"""verify_release_rules.py：wg_release_rules 每一條有名字的規則各一組案例（純函式，不碰檔案與 git）。

怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_release_rules.py
test_044_every_rule_has_a_case 檢查 RULES 的每個規則名都出現在本檔：新增規則沒補案例就紅。044 的案例叫 test_044_<規則名小寫>_…，
045 的叫 test_045_…。
端到端（工具→PostToolUse→Stop）的案例在 verify_stop_reconcile.py 的「044」段。
"""
from __future__ import annotations

import re
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


@pytest.mark.parametrize("rule, case_file", [
    ("JUDGE_CARD_HASH_CATCHES_INTERPRETER", "verify_judge_card_declare.py"),
    ("SECOND_OPINION_RAN_BEFORE", "verify_pull_verify_ledger.py"),
    ("CARRIED_CLAIM_ANY_TURN_RECEIPT", "verify_pull_verify_ledger.py"),
    ("RECEIPT_UNPARSED_GENERAL_ONLY", "verify_pull_verify_ledger.py"),
    ("BASH_UNREACHED_READ_NOT_COUNTED", "verify_overview_hub.py"),
    ("NEGATIVE_CONTROL_DECLARED", "verify_failing_tests_subagent_isolation.py"),
    ("EQUIVALENCE_LOOP_EXPANDED", "verify_g7_equivalence.py"),
    ("EQUIVALENCE_NA_DECLARED_ALWAYS_LOGGED", "verify_g7_equivalence.py"),
    ("COMMIT_ORDER_DECISION_ALWAYS_LOGGED", "verify_git_commit_order_gate.py"),
    ("VERIFY_FULL_RUN_NEEDS_USER_ORDER", "verify_verify_batch.py"),
    ("VERIFY_SAME_BATCH_ALREADY_GREEN", "verify_verify_batch.py"),
    ("VERIFY_BATCH_BLOCK_ONCE_PER_TURN", "verify_verify_batch.py"),
    ("NEGATED_MENTION_IS_NOT_NAMING", "verify_data_file_ask.py"),
    ("DATA_FILE_DECL_VOIDED_BY_LATER_MENTION", "verify_data_file_ask.py"),
    ("OWN_COMMIT_CHANGES_STILL_COMPARED", "verify_old_test_declare.py"),
    ("BLOCK_BUDGET_SHARED", "verify_gate_trim.py"),
    ("STATE_RMW_LOCKED", "verify_state_parallel_rmw.py"),
    ("SECOND_OPINION_RESULT_ACROSS_TURNS", "verify_g9_second_opinion.py"),
    ("SECOND_OPINION_WAITING_NOT_DONE", "verify_g9_second_opinion.py"),
    ("SECOND_OPINION_DECLINE_ACCEPTED", "verify_g9_second_opinion.py"),
    ("DECL_HINT_KEEPS_EDIT_TOOLS", "verify_data_file_ask.py"),
    ("UNKNOWN_WRITE_RECOVERED", "verify_unknown_write_recover.py"),
    ("PROJECT_RULE_WORDS_ARE_HINTS", "verify_user_extract_routing.py"),
    ("TREE_SET_VIA_TEXT", "verify_need_goal.py"),
])
def test_rules_with_end_to_end_cases_elsewhere(rule, case_file):
    """這幾條要走真入口（PreToolUse／PostToolUse／Stop）才驗得到，案例在各自的 verify 檔：核對規則有登記、案例檔真的點到規則名。"""
    assert rule in rr.RULES
    assert rule in (Path(__file__).parent / case_file).read_text(encoding="utf-8"), case_file


def test_choice_verb_is_not_a_character_inside_candidate_words():
    """codex 007：候選描述裡的「採集」不是選擇動詞，「選 B」後面沒寫理由照判沒理由；「採用候選 A 的理由是…」照判有。"""
    assert rr._has_choice_reason("候選 A 採集層，因為來源重複而出錯；候選 B 快取層；選 B") is False
    assert rr._has_choice_reason("候選 A 快取層；候選 B 索引層；採用候選 A 的理由是快取先壞") is True


def test_negative_control_declared_verdict():
    """NEGATIVE_CONTROL_DECLARED 純函式：點到的字樣在指令裡（斜線方向不分）、附理由才算；佔位、別的字樣、沒理由照記紅。"""
    cmd = r"cd C:\tmp\qa2-old && python -m pytest /c/w4/qa2-pricing/tests -q"
    ok = rr.parse_negative_controls("負向對照｜C:/tmp/qa2-old：舊碼跑新測試，預期紅")
    assert ok[0]["subject"] == "C:/tmp/qa2-old" and not rr.negative_control_verdict(cmd, ok).owed
    for line in ("負向對照｜/tmp/other：舊碼", "負向對照｜qa2-old", "負向對照｜qa2-old：<理由>"):
        assert rr.negative_control_verdict(cmd, rr.parse_negative_controls(line)).owed, line


@pytest.mark.parametrize("text, negated", [
    ("shop.json 先不要動", True), ("不要動 shop.json", True), ("折扣碼不要放 shop.json，放新檔", True),
    ("折扣碼不要寫死在程式裡，放進 shop.json", False), ("把 shop.json 的門檻改成 500", False),
])
def test_mention_negated(text, negated):
    """NEGATED_MENTION_IS_NOT_NAMING 純函式：同一子句左邊有否定字或右邊緊接否定才算；否定在前一個子句不算。"""
    i = text.index("shop.json")
    assert rr.mention_negated(text, i, i + len("shop.json")) is negated

# ─── G6 階段 5：其餘固定規則改交 AI 判（純函式；端到端案在 verify_g6_rules_to_llm.py） ─────────────

def test_g6_correction_and_veto_declarations():
    """CORRECTION_WORDS_ARE_HINTS／EXTRACT_VETO_NEEDS_JUDGMENT：宣告行只認行首、最後一條為準、佔位不算；沒回不計（owed＝計一次）。"""
    assert "EXTRACT_VETO_NEEDS_JUDGMENT" in rr.RULES
    assert rr.correction_verdict(None).owed is False                                     # 沒回：詞表不替 AI 判
    yes = rr.yes_no_declaration("- 糾正｜是：他指出我改錯檔", "糾正")
    assert rr.correction_verdict(yes).owed is True and rr.correction_verdict(yes).rule == "CORRECTION_WORDS_ARE_HINTS"
    assert rr.yes_no_declaration("不要寫『糾正｜是：x』\n糾正｜不是：在問進度", "糾正")["yes"] is False
    assert rr.yes_no_declaration("否決記憶｜是：<理由>", "否決記憶") is None


def test_g6_conflict_declared_by_ai():
    """CONFLICT_DECLARED_BY_AI：每個候選一條、why 有理由、同候選不得兩種判法；多宣告不在候選裡的卡不算錯。"""
    v, got = rr.conflict_declaration_verdict(["a"], [{"of": "a", "verdict": "not_conflict", "why": "範圍不同"}])
    assert v.rule == "CONFLICT_DECLARED_BY_AI" and not v.owed and got[0]["verdict"] == "not_conflict"
    assert rr.conflict_declaration_verdict(["a"], [])[0].owed
    assert rr.conflict_declaration_verdict(["a"], [{"of": "a", "verdict": "conflict", "why": "x 理由"},
                                                   {"of": "a", "verdict": "not_conflict", "why": "y 理由"}])[0].owed
    v, got = rr.conflict_declaration_verdict(["a"], [{"of": "a", "verdict": "conflict", "why": "x 理由"},
                                                     {"of": "b", "verdict": "conflict", "why": "y 理由"}])
    assert not v.owed and [d["of"] for d in got] == ["a"] and "不在候選" not in v.why


def test_g6_project_literal_reason_present():
    """PROJECT_LITERAL_IS_HINT：scope_reason 用 reason_present 判有沒有理由（realm_gate.literal_declared）；佔位與空白不算。"""
    assert "PROJECT_LITERAL_IS_HINT" in rr.RULES
    assert rr.reason_present("在講這個詞本身，跨專案都適用")
    assert not rr.reason_present("<一句：為什麼是跨專案的>") and not rr.reason_present("  ")


# ─── RECONCILE_BLOCK_LETTERS／CLOSING_RITUAL_SWITCHES（收尾瘦身） ─────────────────────────────

def test_reconcile_block_letters_splits_by_letter():
    """RECONCILE_BLOCK_LETTERS：只有列出的字母會擋，其餘歸只提示；沒設（不是清單）＝全擋。"""
    a = rr.format_hit("a", rr.Verdict("CLAIM_FIXED_NEEDS_PASS", True, "說修好沒 PASS", ()))
    b = rr.format_hit("b", rr.Verdict("CLAIM_MEASURED_NEEDS_DONE", True, "說量了沒 DONE", ()))
    e = rr.format_hit("e", rr.Verdict("AEC_FOLLOWUPS_EMPTY", True, "k 空字串", ()))
    assert rr.split_blocking([a, b, e], ["a", "d"]) == ([a], [b, e])
    assert rr.split_blocking([a, b, e], None) == ([a, b, e], [])          # 配對：沒設照舊全擋
    assert rr.split_blocking([b], []) == ([], [b])


def test_closing_ritual_switches_goal_gate_default_off():
    """CLOSING_RITUAL_SWITCHES：目標對照開關沒設＝不擋，設 true 才擋（端到端案在 verify_need_goal、verify_pull_goal_locate）。"""
    import wg_need_goal as ng
    assert not ng.goal_gate_on({}) and not ng.goal_gate_on({"reconcile_gate": {}})
    assert not ng.goal_gate_on({"reconcile_gate": {"goal_gate": False}})
    assert ng.goal_gate_on({"reconcile_gate": {"goal_gate": True}})


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
    """EXCLUDED_REGION：在專案根底下、部位表判 knowledge 才排除；類別 code、沒有部位表（None）、拿不到根、不在根下、
    `..` 繞出根都不排除（部位類別的判法本身在 verify_overview_hub／verify_stop_reconcile 的 know 段）。"""
    assert rr.excluded_region(r"c:\proj\workflow\inbox\x\a.py", r"c:\proj", "knowledge")
    assert not rr.excluded_region(r"c:\proj\tools\a.py", r"c:\proj", "code")
    assert not rr.excluded_region(r"c:\proj\workflow\inbox\a.py", r"c:\proj", None)
    assert not rr.excluded_region(r"c:\proj\workflow\inbox\..\..\..\src\a.py", r"c:\proj", "knowledge")   # `..` 繞出根
    assert not rr.excluded_region(r"c:\proj\workflow\inbox\a.py", None, "knowledge")
    assert not rr.excluded_region(r"c:\other\_AIDocs\a.py", r"c:\proj", "knowledge")


def test_excluded_region_gitignored_is_not_project_code():
    """EXCLUDED_REGION 收 git 忽略事實（與 RUNTIME_DATA_NO_OVERVIEW 同一個判式）：根底下被 .gitignore 忽略、在執行期資料目錄
    或快取目錄 → 排除（不欠案例、不能清帳）；追蹤中的檔、查不到（None）、不在根底下照算。"""
    assert rr.excluded_region(r"c:\proj\box\verify_x_snapshot.sh", r"c:\proj", None, gitignored=True)
    assert rr.excluded_region(r"c:\proj\box\a.py", r"c:\proj", "code", gitignored=True)        # 忽略優先於表上的 code
    assert rr.excluded_region(r"c:\proj\Logs\a.py", r"c:\proj", None, gitignored=None)         # 執行期資料目錄
    assert not rr.excluded_region(r"c:\proj\tools\x.py", r"c:\proj", None, gitignored=False)
    assert not rr.excluded_region(r"c:\proj\tools\x.py", r"c:\proj", None, gitignored=None)
    assert not rr.excluded_region(r"c:\other\box\a.py", r"c:\proj", None, gitignored=True)     # 不在根底下


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


def test_0a_moved_copy_needs_same_name_or_same_content():
    """0a（10-15 調度收尾誤擋：已刪的信箱快照腳本 vs 同 session 合進來的新測試檔）：同根新出現的程式檔裡，檔名相同（不分大小寫）、
    內容與它最後一次寫入時相同、或判不出（新檔讀不到）才算可能是它搬過去的副本；檔名與內容都不同的是別的檔。
    它沒有內容紀錄（舊 state）→ 判不出，全算（照欠）。"""
    new = {"hooks/verify/verify_workflow_retention.py": "s2", "pkg/A.sh": "s9", "tools/moved.py": "s1", "tools/unread.py": None}
    seen, other = rr.moved_copy_candidates("a.sh", "s1", new)
    assert seen == ["pkg/A.sh", "tools/moved.py", "tools/unread.py"] and other == ["hooks/verify/verify_workflow_retention.py"]
    seen, other = rr.moved_copy_candidates("a.sh", None, new)
    assert seen == list(new) and other == []
    v = rr.gone_verdict("verify_x_snapshot.sh", "git", [], unrelated=["hooks/verify/verify_workflow_retention.py"])
    assert v.rule == "GONE_IN_GIT_NOTHING_NEW" and v.owed is False and "verify_workflow_retention.py" in v.why


@pytest.mark.parametrize("kind, failed", [("svn", ""), ("git", "在 C:/r 查 git 回非零")])
def test_044_gone_unverifiable(kind, failed):
    """GONE_UNVERIFIABLE：svn 工作副本、或查 git 失敗 → 判不出去向，照欠。"""
    v = rr.gone_verdict("a.py", kind, [], failed)
    assert v.rule == "GONE_UNVERIFIABLE" and v.owed is True


# ─── GATE_SELF_ERROR ───────────────────────────────────────────────

def test_gate_self_error_stop_gate_blocks_once_then_releases():
    """收尾閘出錯：同一個使用者回合擋 1 次，之後放行（不讓 AI 一直付代價）。"""
    v = rr.gate_self_error_verdict("ReconcileGate", "stop", "KeyError: 'x'")
    assert v.rule == "GATE_SELF_ERROR" and v.owed and "擋一次" in v.why and v.evidence == ("KeyError: 'x'",)
    v = rr.gate_self_error_verdict("ReconcileGate", "stop", "KeyError: 'x'", blocked_this_turn=True)
    assert not v.owed and "放行" in v.why


def test_gate_self_error_tool_gate_releases_directly():
    """工具前閘出錯：讀不到 state 無從計次，直接放行。"""
    v = rr.gate_self_error_verdict("CommitOrder", "tool", "OSError: state 讀不到")
    assert v.rule == "GATE_SELF_ERROR" and not v.owed and "直接放行" in v.why


# ─── CASE_COVERS_CHANGE ───────────────────────────────────────────────

def test_case_covers_change_verdict_evidence():
    """CASE_COVERS_CHANGE：有覆蓋的案例 → 不欠並列出；本 session 改過的案例都沒提到 → 欠並列出那些案例；沒改過案例 → 欠。"""
    v = rr.case_cover_verdict("a.py", ["test_a.py"], ["test_a.py", "test_b.py"])
    assert v.rule == "CASE_COVERS_CHANGE" and not v.owed and "test_a.py" in v.why
    v = rr.case_cover_verdict("a.py", [], ["test_b.py"])
    assert v.owed and "test_b.py" in v.why and "case_for" in v.why
    v = rr.case_cover_verdict("a.py", [], [])
    assert v.owed and "沒有改過仍存在、同根的案例檔" in v.why


# ─── 要查 git 的豁免：規則名登記在 RULES、條件在 wg_verify_ledger（端到端案例見 verify_stop_reconcile 的 042／044 段） ──

def test_044_snapshot_settled_and_net_unchanged_are_registered():
    """SNAPSHOT_SETTLED、NET_UNCHANGED：規則名在 RULES 有登記、說明指向 wg_verify_ledger。"""
    for name in ("SNAPSHOT_SETTLED", "NET_UNCHANGED"):
        assert "wg_verify_ledger" in rr.RULES[name]


def test_exemption_peers_code_only_keeps_code_and_cases():
    """EXEMPTION_PEERS_CODE_ONLY：三個豁免共用一個判法（wg_verify_ledger.exemption_peers），要一起比的同根改檔只留程式檔與案例檔，
    文件、紀錄檔、資料不算；同一個寫法只留一次。端到端案例見 verify_stop_reconcile 的 exemption_peers 段。"""
    assert "exemption_peers" in rr.RULES["EXEMPTION_PEERS_CODE_ONLY"]
    got = vl.exemption_peers(["a/x.py", "a/notes.md", "t/test_x.py", "w/run.log", "d/rows.json", "a/x.py"], vl.reconcile_cfg({}))
    assert got == ["a/x.py", "t/test_x.py"]


def test_scope_red_only_its_cases_needs_a_complete_red_list():
    """SCOPE_RED_ONLY_ITS_CASES 的事實（red_case_facts）：紅案數等於最後結算行的 failed＋error 才算清單完整；
    輸出被截（沒有結算行）、數不合、不是 pytest → 不完整。端到端案例見 verify_verify_scope 的 SCOPE_RED_ONLY_ITS_CASES 段。"""
    full = "F.\nFAILED a/test_x.py::t1 - assert 0\nERROR a/test_y.py::t2\n1 failed, 3 passed, 1 error in 0.5s\n"
    assert rr.red_case_facts(full) == (["a/test_x.py::t1", "a/test_y.py::t2"], True)
    assert rr.red_case_facts("FAILED a/test_x.py::t1 - x\n=== 2 failed, 1 passed in 0.1s ===\n")[1] is False   # 少列一支
    assert rr.red_case_facts("FAILED a/test_x.py::t1 - x\n")[1] is False                                       # 結算行被截掉
    assert rr.red_case_facts("3 passed in 0.1s\n") == ([], False)                                              # 綠：沒有紅案


def test_scope_edit_in_declared_depends_verdict():
    """SCOPE_EDIT_IN_DECLARED_DEPENDS：宣告了 depends 的項目，程式改動只算依賴裡、點名路徑底下、共用測試設施；
    沒宣告照 SCOPE_EDIT_RELATED_TO_ITEM 一律算。"""
    v = rr.scope_edit_related_verdict
    assert v("x.py", True).owed and "沒宣告 depends" in v("x.py", True).why
    assert not v("x.py", True, declares_deps=True).owed
    assert v("x.py", True, declares_deps=True, in_deps=True).rule == "SCOPE_EDIT_IN_DECLARED_DEPENDS"
    assert v("x.py", True, declares_deps=True, in_deps=True).owed
    assert v("conftest.py", True, declares_deps=True, shared_case=True).owed
    assert v("test_y.py", True, declares_deps=True, under_item=True).owed


# ═══ 045（track-gate-rules）：清冊 B／C 組規則的案例 ═══

# ─── 擋訊息格式（契約） ───────────────────────────────────────────────────────

def test_045_format_hit_and_parse_hits_roundtrip():
    v = rr.Verdict("CASE_COVERS_CHANGE", True, "x.py 改過", ("最後一次改的案例是 verify_x.py", "x.py 在那之後還改過"))
    line = rr.format_hit("d", v)
    assert line.startswith("✗ (d) CASE_COVERS_CHANGE：x.py 改過｜證據：")
    assert "；" in line and "verify_x.py" in line
    text = "[Guardian:ReconcileGate] 頭\n  " + rr.format_hit("a", rr.Verdict("PASS_MISSING", True, "沒 PASS")) + "\n  " + line
    assert rr.parse_hits(text) == ["a", "d"]
    assert rr.parse_hit_rules(text) == [("a", "PASS_MISSING"), ("d", "CASE_COVERS_CHANGE")]


def test_045_format_hit_without_evidence_uses_why():
    assert rr.format_hit("c", rr.Verdict("R", True, "沒跑")).endswith("｜證據：沒跑")


def test_045_legacy_letters_have_rule_names():
    for n in ("CLAIM_FIXED_NEEDS_PASS", "CLAIM_MEASURED_NEEDS_DONE", "CLAIM_TRIED_NEEDS_EXEC", "AEC_EVIDENCE_PATH",
              "AEC_FOLLOWUPS_EMPTY", "SCOPE_DECLARED_FOR_CHANGE", "SCOPE_ITEM_RECEIPT_AFTER_EDIT"):
        assert n in rr.RULES and rr.RULES[n]
        assert rr.parse_hits(rr.format_hit("x", rr.Verdict(n, True, "w"))) == ["x"]


def test_045_parse_hits_ignores_prose_with_letters():
    assert rr.parse_hits("這裡提到 (d) 但不是擋條目\n✗ (x) 不是規則名") == []


# ─── B2 BLOCK_BUDGET_PER_RULE ──────────────────────────────────────────────────

def test_045_block_budget_per_rule_two_rules_once_each_not_exhausted():
    rec = rr.budget_tick(None, 7, ["a"])
    rec = rr.budget_tick(rec, 7, ["d"])
    assert rec["counts"] == {"a": 1, "d": 1} and rec["count"] == 1
    assert rr.budget_exhausted(rec, 7, 2, ["a", "d"]) == []


def test_045_block_budget_per_rule_same_rule_twice_exhausted_and_lists_all():
    rec = rr.budget_tick(None, 7, ["d"])
    rec = rr.budget_tick(rec, 7, ["a", "d"])
    assert rr.budget_exhausted(rec, 7, 2, ["a", "d"]) == ["d"]
    text = "頭\n  ✗ (a) PASS_MISSING：沒 PASS｜證據：x\n  ✗ (d) CASE_COVERS_CHANGE：欠｜證據：y"
    assert rr.exhausted_summary(text) == "✗ (a) PASS_MISSING；✗ (d) CASE_COVERS_CHANGE"


def test_045_block_budget_per_rule_new_turn_resets_and_legacy_record_is_conservative():
    rec = rr.budget_tick(None, 7, ["d", "d"])
    assert rr.budget_counts(rec, 8) == {}
    legacy = {"turn": 7, "count": 2}                                 # 升級前整場一個 count：每條都當已擋 2 次（不因升級多放）
    assert rr.budget_exhausted(legacy, 7, 2, ["a", "d"]) == ["a", "d"]
    assert rr.budget_tick(legacy, 7, ["a"])["count"] == 3


# ─── CASE_COVERS_CHANGE：案例內容提到程式檔 ──────────────────────────────────

def test_case_names_code_file_or_module_whole_word():
    assert rr.case_names_code("import wg_x as wx\n", r"c:\p\hooks\wg_x.py")
    assert rr.case_names_code('SRC = ROOT / "tools" / "Foo-Bar.py"', "tools/foo-bar.py")
    assert not rr.case_names_code("import wg_xy\n", "hooks/wg_x.py")                   # 整詞：wg_xy 不是 wg_x
    assert not rr.case_names_code("import my_wg_x\n", "hooks/wg_x.py")
    assert not rr.case_names_code("ab = 1", "hooks/ab.py")                              # 模組名不到 3 字只認檔名
    assert rr.case_names_code("run('ab.py')", "hooks/ab.py")
    assert rr.case_covers_code("hooks/verify/verify_ab.py", "", "hooks/ab.py")         # 檔名照模組取
    assert rr.case_covers_code("tests/test_ab.py", "", "src/ab.py") and rr.case_covers_code("t/ab_test.go", "", "ab.go")
    assert not rr.case_covers_code("tests/test_abc.py", "", "src/ab.py")


# ─── B3 COMMENT_ONLY_CHANGE ────────────────────────────────────────────────────

def test_045_comment_only_change_true_for_comment_docstring_whitespace():
    old = 'def f(a):\n    """舊 doc"""\n    # 舊註解\n    return a + 1\n'
    new = 'def f(a):\n    """新 doc 寫得更長"""\n\n    # 新註解\n    return a + 1   # 行尾註解\n'
    assert rr.comment_only_change(old, new) is True


def test_045_comment_only_change_false_for_identifier_or_literal():
    old = "def f(a):\n    return a + 1\n"
    assert rr.comment_only_change(old, "def f(a):\n    return a + 2\n") is False
    assert rr.comment_only_change(old, "def f(b):\n    return b + 1\n") is False


def test_045_comment_only_change_none_when_unparsable_or_not_python():
    assert rr.comment_only_change("def f(:\n", "def f():\n    pass\n") is None
    assert rr.comment_only_change("x", "x", path="a.js") is None
    assert rr.comment_only_change(None, "x") is None
    assert rr.comment_only_verdict("x.py", "HEAD").owed is False


# ─── B13 CONTENT_EQUALS_COMMITTED ──────────────────────────────────────────────

def test_045_blob_sha_matches_git_formula():
    assert rr.blob_sha(b"") == "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"
    assert rr.blob_sha(b"hello\n") == "ce013625030ba8dba906f756967f9e9ca394464a"


def test_045_content_equals_committed_merge_head_and_main_count_head_only_without_own_commit():
    refs = {"HEAD": "h1", "MERGE_HEAD": "m1", "main": "mm"}
    assert rr.committed_refs([], refs) == ["MERGE_HEAD", "main"]                            # HEAD 永遠不算（035 ⑤）
    assert rr.committed_refs(["mm"], refs) == ["MERGE_HEAD"]                                 # main 指到自己提交的 → 不算
    assert rr.committed_refs([], {"HEAD": "h1", "main": "h1"}) == []                         # main 就是 HEAD → 不算
    blobs = {"HEAD": "aaa", "MERGE_HEAD": "bbb", "main": "ccc"}
    v = rr.content_equals_committed("x.py", "bbb", blobs, ["MERGE_HEAD", "main"])
    assert v is not None and v.rule == "CONTENT_EQUALS_COMMITTED" and v.owed is False and "MERGE_HEAD" in v.why
    assert rr.content_equals_committed("x.py", "aaa", blobs, ["MERGE_HEAD", "main"]) is None   # 等於 HEAD 但 HEAD 不可用
    assert rr.content_equals_committed("x.py", "zzz", blobs, ["HEAD", "MERGE_HEAD", "main"]) is None
    assert rr.content_equals_committed("x.py", None, blobs, ["HEAD"]) is None


# ─── B4 INLINE_PY_READONLY ─────────────────────────────────────────────────────

@pytest.mark.parametrize("code", [
    "import json,sys;d=json.load(open(r'C:/x/state.json',encoding='utf-8'));print(d['turn_seq'])",
    "import json;print(json.dumps(json.load(open('a.json')),ensure_ascii=False)[:800])",
    "from pathlib import Path;print(Path('a.py').read_text(encoding='utf-8')[:100])",
    "import sys;sys.stdout.write('x\\n')",
    "import os;print(os.environ.get('TEMP'));print(os.path.exists('a'))",
    "import re;print(len(re.findall(r'x', open('a','r').read())))",
])
def test_045_inline_py_readonly_allows_pure_reads(code):
    assert rr.inline_python_verdict(code).owed is False


@pytest.mark.parametrize("code", [
    "open('a','w').write('x')",
    "import json;json.dump({}, open('a','a'))",
    "from pathlib import Path;Path('a').write_text('x')",
    "import os;os.remove('a')",
    "import shutil",
    "import subprocess;subprocess.run(['x'])",
    "exec('print(1)')",
    "m='w';open('a',m)",
    "open('a', mode='x')",
    "import os;os.rename('a','b')",
    "def f(:",
    "import sys;sys.path=[]",
    # codex 001 BLOCK 1：別名與動態呼叫一律判不了
    "f = open\nf('C:/project/x.py', 'w')",
    "import os\ngetattr(os, 'rem' + 'ove')('C:/project/x.py')",
    "import os as o;o.remove('a')",
    "from os import remove;remove('a')",
    "from os import *",
    "g = [open][0]; g('a','w')",
    "import os;w = os.remove;w('a')",
    "(lambda p: open(p,'w'))('a')",
    "import io;io.open('a','w')",
    "import json;json.load(open('a')).write('x')",
])
def test_045_inline_py_readonly_denies_writes_and_unknowns(code):
    v = rr.inline_python_verdict(code)
    assert v.owed is True and v.rule == "INLINE_PY_READONLY" and v.why


# ─── B5 GIT_READONLY_SUBCMD ────────────────────────────────────────────────────

@pytest.mark.parametrize("cmd", [
    "git hash-object C:/Users/me/.claude/settings.json",
    "git -C C:/Users/me/.claude show main:settings.json",
    "git -C C:/Users/me/.claude status --porcelain && git -C C:/Users/me/.claude log --oneline -3",
    "git -C C:/Users/me/.claude rev-parse HEAD | head -1",
    "git -C C:/Users/me/.claude diff --stat; git -C C:/Users/me/.claude ls-files hooks | wc -l",
    "git -C C:/Users/me/.claude config --get user.name",
])
def test_045_git_readonly_subcmd_allows(cmd):
    assert rr.git_readonly_verdict(cmd, []).owed is False


@pytest.mark.parametrize("cmd,targets", [
    ("git -C C:/Users/me/.claude hash-object -w x.py", []),
    ("git -C C:/Users/me/.claude add x && git -C C:/Users/me/.claude commit -m x", []),
    ("git -C C:/Users/me/.claude show main:x > C:/Users/me/.claude/hooks/x.py", ["C:/Users/me/.claude/hooks/x.py"]),
    ("git -C C:/Users/me/.claude checkout -- hooks/x.py", []),
    ("git -C C:/Users/me/.claude branch -m a b", []),
    ("git -C C:/Users/me/.claude config user.name x", []),
    ("git -C C:/Users/me/.claude worktree add ../x", []),
    ("git -C C:/Users/me/.claude", []),
    # codex 001 BLOCK 2：換行後的第二段、唯讀子命令的寫檔選項、命令替換
    ("git -C C:/Users/me/.claude status\ngit -C C:/Users/me/.claude reset --hard HEAD", []),
    ("git -C C:/Users/me/.claude diff --output=C:/Users/me/.claude/hooks/x.patch", []),
    ("git -C C:/Users/me/.claude log -oC:/x", []),
    ("git -C C:/Users/me/.claude show $(git -C C:/Users/me/.claude rev-parse HEAD)", []),
    ("git -C C:/Users/me/.claude branch -u origin/main", []),
])
def test_045_git_readonly_subcmd_denies(cmd, targets):
    v = rr.git_readonly_verdict(cmd, targets)
    assert v.owed is True and v.evidence


# ─── B6 GREP_CONTENT_IS_READ ／ BASH_COMMENT_LINES_STRIPPED ────────────────────

def test_045_grep_content_is_read_only_for_file_path_in_content_mode():
    isf = lambda p: p.endswith(".py")  # noqa: E731
    assert rr.grep_read_paths({"pattern": "x", "path": "C:/p/a.py", "output_mode": "content"}, isf) == ["C:/p/a.py"]
    assert rr.grep_read_paths({"pattern": "x", "path": "C:/p/a.py"}, isf) == []                          # 預設 files_with_matches
    assert rr.grep_read_paths({"pattern": "x", "path": "C:/p", "output_mode": "content"}, isf) == []     # 目錄：不知道讀了哪些檔
    assert rr.grep_read_paths({"pattern": "x", "output_mode": "content"}, isf) == []


def test_045_bash_comment_lines_stripped_keeps_commands_and_continuations():
    cmd = "# 定位｜部位：x\n# 定位｜根因層：y\n# 定位｜前例：z\nhead -20 hooks/x.py\necho a \\\n  # 這是接續行不是註解\nsed -n 1,3p b.py"
    out = rr.strip_comment_lines(cmd)
    assert out.splitlines()[0] == "head -20 hooks/x.py"
    assert "# 這是接續行不是註解" in out and "定位" not in out


# ─── 文字格式守門：規則模組不寫破折號（總控台對帳規則「新增行不准——」，002 對帳卡過一次） ─────

def test_045_rules_module_has_no_em_dash():
    src = (HOOKS_DIR / "wg_release_rules.py").read_text(encoding="utf-8")
    bad = [i for i, ln in enumerate(src.splitlines(), 1) if "——" in ln]
    assert not bad, f"wg_release_rules.py 第 {bad} 行有破折號，改成逗號或句號"


# ─── ⑨ hook 子行程直譯器只有一份（wg_core.hook_python_exe） ──────────────────────

def test_045_hook_python_exe_single_source(monkeypatch, tmp_path):
    import wg_core
    from handlers import pre_tool_use as ptu
    pyw = tmp_path / "pythonw.exe"
    py = tmp_path / "python.exe"
    pyw.write_bytes(b"")
    py.write_bytes(b"")
    monkeypatch.setattr(sys, "executable", str(pyw))
    assert wg_core.hook_python_exe() == str(py) and ptu._hook_python_exe() == str(py)       # pythonw → 同目錄 python.exe
    py.unlink()
    assert wg_core.hook_python_exe() == str(pyw)                                               # 沒有 python.exe → 原樣
    monkeypatch.setattr(sys, "executable", str(tmp_path / "python3.exe"))
    assert wg_core.hook_python_exe() == str(tmp_path / "python3.exe")
    import wg_reading_path as rph                                                              # 收尾附閱讀路徑影響也起 Python 子行程
    assert getattr(rph, "hook_python_exe", None) is wg_core.hook_python_exe and not hasattr(rph, "_python_exe")
    own = [p.relative_to(HOOKS_DIR).as_posix() for p in sorted(HOOKS_DIR.rglob("*.py"))
           if "verify" not in p.parts and p.name != "wg_core.py"
           and 'with_name("python.exe")' in p.read_text(encoding="utf-8", errors="replace")]
    assert own == [], f"hook 模組各自留了 pythonw→python.exe 的對應：{own}（一律呼叫 wg_core.hook_python_exe）"


# ─── ⑥ DISPATCH_OPENS_TURN ／ ⑧ VCS_ROOT_UNREADABLE ────────────────────────────

def test_045_vcs_root_unreadable_is_owed_not_outside_vcs():
    v = rr.vcs_unreadable_verdict("a.py", "PermissionError: [WinError 5]")
    assert v.rule == "VCS_ROOT_UNREADABLE" and v.owed is True and "PermissionError" in v.evidence[0]
    assert rr.gone_verdict("a.py", None).owed is False                                      # 真的不在版控才不欠


# ─── B7 WORKTREE_NO_PUSH ───────────────────────────────────────────────────────

def test_045_worktree_no_push_verdicts():
    assert rr.is_worktree_checkout("C:/live/.git/worktrees/t", "C:/live/.git") is True
    assert rr.is_worktree_checkout("C:/live/.git", "C:/live/.git") is False
    assert rr.is_worktree_checkout(None, "C:/live/.git") is False
    assert rr.push_required_verdict("C:/wt", True, True).owed is False
    assert rr.push_required_verdict("C:/solo", False, False).owed is False
    v = rr.push_required_verdict("C:/live", False, True)
    assert v.owed is True and v.rule == "WORKTREE_NO_PUSH"


# ─── B8 RUNTIME_DATA_NO_OVERVIEW ───────────────────────────────────────────────

@pytest.mark.parametrize("path,ignored", [
    ("C:/p/workflow/need-goal/", None),
    ("C:/p/workflow/state-abcd1234.json", None),
    ("C:/p/Logs/guard-x.jsonl", None),
    ("C:/p/workflow/aec-report/s1-t3.json", None),   # 資料夾名是 aec-report（曾打成 aec-reports，永遠比不中）
    ("C:/p/some/other.bin", True),
])
def test_045_runtime_data_no_overview_exempts(path, ignored):
    assert rr.runtime_data_verdict(path, "C:/p", ignored).owed is False


@pytest.mark.parametrize("path", ["C:/p/hooks/x.py", "C:/p/workflowx/a.json", "C:/other/Logs/a"])
def test_045_runtime_data_no_overview_still_requires(path):
    assert rr.runtime_data_verdict(path, "C:/p", False).owed is True


# ─── B9／B14 暫存目錄 ─────────────────────────────────────────────────────────

def test_045_temp_repo_commit_exempt_and_temp_copy_not_project():
    roots = rr.temp_roots({"TEMP": r"C:\Users\me\AppData\Local\Temp", "TMP": ""}, tempdir=r"C:\Users\me\AppData\Local\Temp")
    assert roots[0] == "c:/users/me/appdata/local/temp" and "/tmp" in roots
    assert rr.is_temp_path(r"\\?\C:\Users\me\AppData\Local\Temp\claude\x\scratchpad\repo", roots)
    assert rr.is_temp_path("/tmp/pytest-of-me/pytest-1/repo0", roots)
    assert rr.is_temp_path(r"C:\Users\HOLYLI~1\AppData\Local\Temp\claude\scratchpad\x", roots)   # 短路徑含 Temp/claude 片段
    assert not rr.is_temp_path(r"C:\project\scratchpad\x.py", roots)                  # codex 001 BLOCK 6：正式 repo 的子目錄叫 scratchpad 不算暫存
    assert not rr.is_temp_path(r"C:\Users\me\AppData\Local\Temp\..\..\..\.claude\hooks\x.py", roots)
    assert not rr.is_temp_path(r"C:\Users\me\.claude-wt\track-x\hooks\x.py", roots)
    assert rr.temp_commit_verdict(r"C:\Users\me\AppData\Local\Temp\claude\s\repo", roots).owed is False
    assert rr.temp_commit_verdict(r"C:\Users\me\.claude", roots).owed is True
    assert rr.temp_copy_verdict("/tmp/x/tools/x.py", roots).owed is False
    assert rr.temp_copy_verdict(r"C:\Users\me\.claude-wt\t\tools\x.py", roots).owed is True


def test_003_session_scratch_not_code_only_two_shapes():
    """SESSION_SCRATCH_NOT_CODE：設定目錄下 jobs/<id>/tmp/ 與 Temp/claude/…/scratchpad/ 才算暫存區；repo 裡同名的目錄、
    jobs/<id> 底下不在 tmp 的、設定目錄本身的程式照算。"""
    dirs = rr.cc_config_dirs({"CLAUDE_CONFIG_DIR": r"D:\cc"}, home=r"C:\Users\me")
    assert dirs == [r"D:\cc", r"C:\Users\me\.claude"]
    assert rr.cc_config_dirs({}, home=r"C:\Users\me") == [r"C:\Users\me\.claude"]
    roots = rr.temp_roots({"TEMP": r"C:\Users\me\AppData\Local\Temp"}, tempdir=r"C:\Users\me\AppData\Local\Temp")

    def hit(p):
        return rr.is_session_scratch(p, dirs, roots)
    assert hit(r"C:\Users\me\.claude\jobs\8bd2fa36\tmp\probe.py")
    assert hit(r"d:/CC/jobs/abc/tmp/sub/m.py")                                                 # 斜線、大小寫不影響
    assert hit(r"C:\Users\me\AppData\Local\Temp\claude\C--x\s1\scratchpad\m.py")
    assert not hit(r"C:\proj\jobs\8bd2fa36\tmp\probe.py")                                     # repo 內同名路徑
    assert not hit(r"C:\Users\me\.claude-wt\t\jobs\8bd2fa36\tmp\probe.py")                    # worktree 不是設定目錄
    assert not hit(r"C:\Users\me\.claude\jobs\8bd2fa36\state.py")                             # jobs/<id> 但不在 tmp
    assert not hit(r"C:\Users\me\.claude\hooks\wg_core.py")
    assert not hit(r"C:\project\scratchpad\x.py")                                             # 正式 repo 的子目錄叫 scratchpad
    assert not hit(r"C:\repo\Temp\claude\demo\scratchpad\service.py")                        # Codex：形狀一樣但不在暫存根下
    assert not hit(r"C:\Users\me\AppData\Local\Temp\pytest-of-me\scratchpad\x.py")           # 暫存根下但不是 claude/…/scratchpad
    assert not rr.is_session_scratch(r"C:\Users\me\AppData\Local\Temp\claude\x\scratchpad\m.py", dirs, rr.TEMP_DISABLED)


def test_003_session_scratch_not_code_scratchpad_under_real_temp_root(monkeypatch):
    """Codex 複審 NOTE：scratchpad 走實際的系統暫存根（短路徑與長路徑兩種寫法都認），經事實端 session_scratch 與 is_excluded；
    repo 裡同形狀的照算。"""
    import os
    import tempfile
    from handlers import _shared
    monkeypatch.delenv("WG_TEMP_RULES", raising=False)
    cfg = vl.reconcile_cfg({})
    for tmp in (tempfile.gettempdir(), _shared._long_path(tempfile.gettempdir())):
        p = os.path.join(tmp, "claude", "C--x", "sid1", "scratchpad", "measure.py")
        assert vl.session_scratch(p) and vl.is_excluded(p, cfg, None), p
    assert not vl.session_scratch(r"C:\repo\Temp\claude\demo\scratchpad\service.py")
    monkeypatch.setenv("WG_TEMP_RULES", "off")
    assert not vl.session_scratch(os.path.join(tempfile.gettempdir(), "claude", "x", "scratchpad", "m.py")), "暫存規則關掉時只認 jobs"


def test_003_session_scratch_not_code_excluded_from_case_debt(tmp_path, monkeypatch):
    """寫碼查核：暫存區的腳本 is_excluded（不欠補案例、不能清帳），不看根；repo 內同形狀的照算。"""
    cc = tmp_path / "cc"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(cc))
    cfg = vl.reconcile_cfg({})
    scratch = str(cc / "jobs" / "j1" / "tmp" / "probe.py")
    assert vl.is_excluded(scratch, cfg, None) and vl.is_excluded(scratch, cfg, str(tmp_path / "proj"))
    assert not vl.is_excluded(str(tmp_path / "proj" / "jobs" / "j1" / "tmp" / "probe.py"), cfg, str(tmp_path / "proj"))
    mods = [{"path": scratch, "tool": "Write", "turn_seq": 3, "last_turn_seq": 3, "last_seq": 1}]
    assert vl.case_debt(mods, 3, cfg, lambda p: None) == []


# ─── B10 DPM_WORKTREE_DELIVERY ─────────────────────────────────────────────────

def test_045_dpm_instruction_text_same_for_every_session():
    """DeepPostMortem 指令不分在不在 worktree：一律叫 atom_write 補 post-mortem；證據行接在標頭下一行。"""
    t = rr.dpm_instruction_text("失敗中反覆重試")
    assert "atom_write" in t and "交付信" not in t and "防再犯" in t
    assert "✗ 證據" in rr.dpm_instruction_text("失敗中反覆重試", "✗ 證據").splitlines()[1]


# ─── C1 RED_WHILE_REVERTED ／ RETRY_IS_RED_AGAIN ／ GREEN_SAME_CASE_CLEARS ─────

def test_045_red_while_reverted_verdicts():
    v = rr.deliberate_red_verdict([("x.py", "main")])
    assert v.owed is False and "main" in v.why and v.evidence == ("x.py == main",)
    assert rr.deliberate_red_verdict([]).owed is True
    # codex 001 BLOCK 5：退回 A、B 還留著真錯 → 不是刻意紅
    v = rr.deliberate_red_verdict([("a.py", "main")], pending=["b.py"])
    assert v.owed is True and "b.py" in v.why


def test_045_retry_counts_rerun_cycles_verdict():
    """純函式：重跑同一組（prev_red 是那組活著的紅）、那組上次跑之後改過檔（不論幾次、幾個檔）、這次又紅，才算一輪；
    不是同一組（第一次跑或別組）、沒改就重跑都不算。同一組＝點名同一個案例檔，或兩邊都沒點名檔且指令前 40 字相同。"""
    assert rr.same_test_run("npx jest tests/a.test.js", "npx jest tests/a.test.js")
    assert not rr.same_test_run("npx jest tests/a.test.js", "npx jest tests/b.test.js")
    assert rr.same_test_run("python -m pytest -q tests/x.py", "python -m pytest -q tests/x.py -k t2")
    assert rr.same_test_run("pytest -q", "pytest -q") and not rr.same_test_run("pytest -q", "pytest -q tests/x.py")
    # codex 第三輪 BLOCK：共用設定檔不能讓不同案例檔被當成同一組（要點名的檔完全相同，不是有交集）
    assert not rr.same_test_run("npx jest --config jest.config.js tests/a.test.js",
                                "npx jest --config jest.config.js tests/b.test.js")
    assert rr.same_test_run("npx jest --config jest.config.js tests/a.test.js",
                            "npx jest --config jest.config.js tests/a.test.js -t adds")
    assert rr.retry_round_verdict(None, {"src/a.py": 1}, 1, "pytest -q", ["a.py::t"]).owed is False   # 第一次紅
    assert rr.retry_round_verdict({"cmd": "x"}, {}, 1, "pytest -q", ["a.py::t"]).owed is False        # 沒改就重跑
    v = rr.retry_round_verdict({"cmd": "x"}, {"src/a.py": 5}, 3, "pytest -q tests/x.py", ["tests/x.py::t2"])
    assert v.owed is True and v.rule == "RETRY_COUNTS_RERUN_CYCLES" and "第 3 輪" in v.why
    assert any("pytest -q tests/x.py" in e for e in v.evidence) and any("tests/x.py::t2" in e for e in v.evidence)
    assert rr.red_case_names("FAILED tests/x.py::t1 - assert 1\nERROR tests/y.py::t2\n2 failed") == ["tests/x.py::t1", "tests/y.py::t2"]


# 走真的 PostToolUse 入口：紅測由 _track_test_result 記（重跑在這裡看得到），改檔由 wisdom_engine.track_retry 記
_RR_SID = "sess-retry"


def _rr_run(st, case=None, cmd="python -m pytest -q tests/x.py"):
    """跑一次測試：case 給了就是紅（FAILED <case>），沒給就是綠。"""
    from handlers import post_tool_use as ptu
    out = f"FAILED {case} - assert 1 == 2\n1 failed in 0.1s\n" if case else "3 passed in 0.1s\n"
    ev = {"session_id": _RR_SID, "tool_name": "Bash", "tool_input": {"command": cmd},
          "tool_response": {"stdout": out, "stderr": "", "interrupted": False}}
    ptu._track_test_result(st, ev, cmd)


def _rr_edit(st, path="src/a.py", n=1):
    import wisdom_engine as we
    for _ in range(n):
        we.track_retry(st, path)


def test_045_retry_counts_rerun_cycles_red_first_many_edits_then_green_is_zero():
    """紅案例先行：紅 → 同檔改 5 次 → 一跑就綠 ＝ 0 輪，FixEscalation 不跳。"""
    st = {"turn_seq": 1}
    _rr_run(st, "tests/x.py::t1")
    _rr_edit(st, n=5)
    _rr_run(st)
    assert int(st.get("wisdom_retry_count", 0)) == 0 and not st.get("retry_rounds") and not st.get("failing_tests")
    assert rr.fix_escalation_text(st) is None


@pytest.mark.parametrize("approach", ["direct", "plan"])
def test_045_retry_counts_rerun_cycles_two_red_reruns_escalate(approach):
    """紅 → 改 → 跑仍紅 → 改 → 跑仍紅 ＝ 2 輪；plan 與 direct 同門檻；訊息印第 2 輪與兩輪的指令＋紅案。"""
    st = {"turn_seq": 1, "wisdom_approach": approach}
    _rr_run(st, "tests/x.py::t1", cmd="python -m pytest -q tests/x.py")
    _rr_edit(st, n=3)
    _rr_run(st, "tests/x.py::t2", cmd="python -m pytest -q tests/x.py -k t2")
    assert int(st.get("wisdom_retry_count", 0)) == 1
    _rr_edit(st, "src/b.py")
    _rr_run(st, "tests/x.py::t3", cmd="python -m pytest -q tests/x.py -k t3")
    assert int(st.get("wisdom_retry_count", 0)) == 2 >= rr.RETRY_ESCALATE_ROUNDS
    assert [r["round"] for r in st.get("retry_rounds") or []] == [1, 2]
    text = rr.fix_escalation_text(st)
    assert text and "RETRY_COUNTS_RERUN_CYCLES" in text and "第 2 輪" in text
    assert "pytest -q tests/x.py -k t2" in text and "tests/x.py::t2" in text
    assert "pytest -q tests/x.py -k t3" in text and "tests/x.py::t3" in text


def test_045_retry_counts_rerun_cycles_rerun_without_edit_or_plan_file_edit_is_not_a_round():
    """沒改就重跑、只改計畫類檔就重跑，都不算一輪。"""
    st = {"turn_seq": 1}
    _rr_run(st, "tests/x.py::t1")
    _rr_run(st, "tests/x.py::t1")
    _rr_edit(st, "C:/p/plans/next.md", n=3)
    _rr_run(st, "tests/x.py::t1")
    assert int(st.get("wisdom_retry_count", 0)) == 0 and not st.get("retry_rounds")


def _rr_jest(st, name, red):
    """Jest 跑一組：綠只清同一個案例檔的紅（pytest 綠會清掉所有 pytest 紅，交錯的情境重現不了）。"""
    from handlers import post_tool_use as ptu
    cmd = f"npx jest tests/{name}.test.js"
    resp = (f"Error: Exit code 1\nFAIL tests/{name}.test.js\nTests: 1 failed, 1 total\n" if red
            else {"stdout": f"PASS tests/{name}.test.js\nTests: 1 passed, 1 total\n", "stderr": "", "interrupted": False})
    ptu._track_test_result(st, {"session_id": _RR_SID, "tool_name": "Bash", "tool_input": {"command": cmd},
                                "tool_response": resp}, cmd)


def test_045_retry_counts_rerun_cycles_limit_fixing_b_counts_for_unchanged_a():
    """已知限制（裁定採「同一組上次跑之後碼有改過、再跑仍紅＝一輪」，不猜意圖）：A、B 兩組都紅，修 B（改、跑仍紅＝第 1 輪；
    再改、跑綠），沒再改就重跑 A 仍紅 → A 上次跑之後碼改過，也算一輪＝2。同時修多組時對沒改到的那組多報一次提醒。"""
    st = {"turn_seq": 1}
    _rr_jest(st, "a", red=True)
    _rr_jest(st, "b", red=True)
    _rr_edit(st, "src/b.js")
    _rr_jest(st, "b", red=True)
    assert int(st.get("wisdom_retry_count", 0)) == 1
    _rr_edit(st, "src/b.js")
    _rr_jest(st, "b", red=False)
    assert [f["cmd"] for f in st["failing_tests"]] == ["npx jest tests/a.test.js"]          # B 清掉、A 還在
    _rr_jest(st, "a", red=True)
    assert int(st.get("wisdom_retry_count", 0)) == 2


def test_045_retry_counts_rerun_cycles_two_groups_red_fix_a_rerun_a_is_a_round():
    """A、B 都紅（B 較晚跑），改 A、重跑 A 仍紅 → 1 輪（改檔不只記在最近跑紅的那組）。"""
    st = {"turn_seq": 1}
    _rr_jest(st, "a", red=True)
    _rr_jest(st, "b", red=True)
    _rr_edit(st, "src/a.js")
    _rr_jest(st, "a", red=True)
    assert int(st.get("wisdom_retry_count", 0)) == 1


def test_045_retry_counts_rerun_cycles_limit_other_group_work_counts_for_unchanged_a():
    """已知限制：A 紅著時去修 B（第一次跑 B 紅、再跑綠），沒改 A 就重跑 A 仍紅 → A 上次跑之後碼改過，算一輪。"""
    st = {"turn_seq": 1}
    _rr_jest(st, "a", red=True)
    _rr_edit(st, "src/b.js")
    _rr_jest(st, "b", red=True)
    _rr_jest(st, "b", red=False)
    _rr_jest(st, "a", red=True)
    assert int(st.get("wisdom_retry_count", 0)) == 1


def test_045_retry_counts_rerun_cycles_other_green_run_between_does_not_hide_rounds():
    """codex 複審 BLOCK：修 A 時中間先跑 B 的回歸（綠）再跑 A 仍紅，兩次都要算 → 2 輪；跑別組不會把 A 的改檔取走。"""
    st = {"turn_seq": 1}
    _rr_jest(st, "a", red=True)
    for _ in range(2):
        _rr_edit(st, "src/a.js")
        _rr_jest(st, "b", red=False)
        _rr_jest(st, "a", red=True)
    assert int(st.get("wisdom_retry_count", 0)) == 2


def test_045_retry_counts_rerun_cycles_first_red_of_other_groups_is_not_a_round():
    """codex 複審 BLOCK：A 紅著，改了別處、第一次跑 B 紅、再改、第一次跑 C 紅 → 都不是重跑同一組 → 0 輪。"""
    st = {"turn_seq": 1}
    _rr_jest(st, "a", red=True)
    _rr_edit(st, "src/b.js")
    _rr_jest(st, "b", red=True)
    _rr_edit(st, "src/c.js")
    _rr_jest(st, "c", red=True)
    assert int(st.get("wisdom_retry_count", 0)) == 0


def test_045_retry_counts_rerun_cycles_round_evidence_falls_back_to_summary():
    """輸出沒有 pytest 的 FAILED 行（Jest 的 FAIL、go test 的 --- FAIL）時，證據退回失敗摘要的第一行，不只寫「沒列案例」。"""
    st = {"turn_seq": 1}
    jest = "npx jest tests/b.test.js"
    for _ in range(3):
        from handlers import post_tool_use as ptu
        ev = {"session_id": _RR_SID, "tool_name": "Bash", "tool_input": {"command": jest},
              "tool_response": "Error: Exit code 1\nFAIL tests/b.test.js\n  ● b › adds\nTests: 1 failed, 1 total\n"}
        ptu._track_test_result(st, ev, jest)
        _rr_edit(st, "src/b.js")
    assert int(st.get("wisdom_retry_count", 0)) == 2
    assert "FAIL tests/b.test.js" in rr.retry_rounds_text(st.get("retry_rounds") or [])


def _rr_pytest(st, cmd, red_case=None, passed=1):
    """pytest 跑一次：red_case 給了就是紅（FAILED <案例>），沒給就是綠。"""
    from handlers import post_tool_use as ptu
    out = (f"FAILED {red_case} - assert 0\n1 failed, {passed} passed in 0.1s\n" if red_case
           else f"{passed} passed in 0.1s\n")
    ptu._track_test_result(st, {"session_id": _RR_SID, "tool_name": "Bash", "tool_input": {"command": cmd},
                                "tool_response": {"stdout": out, "stderr": "", "interrupted": False}}, cmd)


@pytest.mark.parametrize("narrow", ["python -m pytest -q tests/test_a.py::test_ok",
                                    "python -m pytest -q tests/test_a.py -k test_ok"], ids=["node-id", "k-filter"])
def test_045_green_narrowed_keeps_uncovered_red_rounds_still_counted(narrow):
    """總控台 codex 退件：整檔紅（test_bad）後，兩次「改 → 只跑 test_ok 綠 → 跑整檔仍紅」＝2 輪。
    單案或 -k 跑綠沒涵蓋 test_bad，不能把那筆紅連同改檔紀錄清掉。"""
    whole = "python -m pytest -q tests/test_a.py"
    st = {"turn_seq": 1}
    _rr_pytest(st, whole, "tests/test_a.py::test_bad")
    for _ in range(2):
        _rr_edit(st, "src/a.py")
        _rr_pytest(st, narrow)
        assert st.get("failing_tests"), "單案綠清掉了沒涵蓋到的紅"
        _rr_pytest(st, whole, "tests/test_a.py::test_bad")
    assert int(st.get("wisdom_retry_count", 0)) == 2


def test_045_green_narrowed_keeps_uncovered_red_verdicts():
    """純函式：綠的範圍有篩選（節點 id、-k、-m、Jest -t）時，紅掉的案例都在綠點名的節點裡才清；沒篩選照既有規則。"""
    red, summary = "pytest -q tests/test_a.py", "FAILED tests/test_a.py::test_bad - assert 0\n1 failed"
    v = rr.green_covers_red_verdict(red, summary, "pytest -q tests/test_a.py::test_ok")
    assert v.rule == "GREEN_NARROWED_KEEPS_UNCOVERED_RED" and v.owed is True and "test_bad" in "；".join(v.evidence)
    assert rr.green_covers_red_verdict(red, summary, "pytest -q tests/test_a.py::test_bad").owed is False   # 紅的就是這案
    assert rr.green_covers_red_verdict(red, summary, "pytest -q tests/test_a.py -k test_bad").owed is True  # -k 判不了照留
    assert rr.green_covers_red_verdict(red, summary, "pytest -q tests/test_a.py").owed is False             # 沒篩選
    # python -m pytest 的 -m 是「跑模組」不是 pytest 的標記篩選（-m slow 才是）
    assert rr.green_covers_red_verdict(red, summary, "python -X utf8 -m pytest -q tests/test_a.py 2>&1 | tail -1").owed is False
    assert rr.green_covers_red_verdict(red, summary, "python -m pytest -q tests/test_a.py -m slow").owed is True
    assert rr.green_covers_red_verdict("pytest -q x.py -k t2", "1 failed", "pytest -q x.py -k t2").owed is False  # 同一篩選
    assert rr.green_covers_red_verdict("npx jest a.test.js", "FAIL a.test.js", "npx jest a.test.js -t adds").owed is True


def test_045_green_narrowed_single_case_that_was_red_clears():
    """對照：單案跑綠、那案就是紅掉的案 → 清帳（既有行為不變）。"""
    st = {"turn_seq": 1}
    _rr_pytest(st, "python -m pytest -q tests/test_a.py", "tests/test_a.py::test_bad")
    _rr_pytest(st, "python -m pytest -q tests/test_a.py::test_bad")
    assert not st.get("failing_tests")


def test_045_retry_counts_rerun_cycles_messages_roundtrip_parse_hits():
    """FixEscalation 與 DPM 的重試證據行用 format_hit，parse_hits／parse_hit_rules 讀得到規則名。"""
    st = {"turn_seq": 1}
    _rr_run(st, "tests/x.py::t1")
    _rr_edit(st)
    _rr_run(st, "tests/x.py::t2")
    _rr_edit(st)
    _rr_run(st, "tests/x.py::t3")
    for text in (rr.fix_escalation_text(st), rr.retry_rounds_text(st["retry_rounds"])):
        assert text.splitlines()[0].startswith("[Guardian:FixEscalation]") or "FixEscalation" not in text.splitlines()[0]
        assert rr.parse_hits(text) == ["r"] and ("r", "RETRY_COUNTS_RERUN_CYCLES") in rr.parse_hit_rules(text)
        assert "第 2 輪" in text and "tests/x.py::t3" in text


# ─── MOVE_CODE_DIR_NEEDS_SCAN_AND_SAMPLE（搬程式目錄：欠路徑掃描與抽樣兩張收據，不欠整組案例）──────────────────

_MV_TOOL = str(HOOKS_DIR.parent / "tools" / "move-dir-check.py")


def test_move_sample_run_prints_child_output_and_exit_code(tmp_path):
    """sample --run 的抽樣指令輸出要直接回到跑工具的人眼前（所以那一行豁免壓窗旗標：shell=True 帶 CREATE_NO_WINDOW
    子行程輸出會整個不見），exit code 判 PASS／FAIL。"""
    import subprocess
    (tmp_path / "pkg").mkdir()
    # 這裡也不帶壓窗旗標：工具本身被 CREATE_NO_WINDOW 叫起時，它的 shell 子行程輸出一樣會不見（跟要驗的是同一件事）
    ok = subprocess.run([sys.executable, "-X", "utf8", _MV_TOOL, "sample", "--root", str(tmp_path), "--for", "pkg",
                         "--run", f'"{sys.executable}" -c "print(\'child-out\')"'],
                        capture_output=True, text=True, encoding="utf-8")
    assert ok.returncode == 0 and "child-out" in ok.stdout and ok.stdout.strip().endswith("MOVE_SAMPLE_CHECK PASS"), ok
    bad = subprocess.run([sys.executable, "-X", "utf8", _MV_TOOL, "sample", "--root", str(tmp_path), "--for", "pkg",
                          "--run", f'"{sys.executable}" -c "raise SystemExit(3)"'],
                         capture_output=True, text=True, encoding="utf-8")
    assert bad.returncode == 1 and "exit 3" in bad.stdout and bad.stdout.strip().endswith("MOVE_SAMPLE_CHECK FAIL"), bad


def _mv_receipt(cmd, line, at, verdict="DONE", name="MOVE_PATH_SCAN", cwd="C:/p"):
    return {"at": at, "session_id": "s", "turn_seq": 3, "tool": "Bash", "cmd": cmd, "cmd_full": True, "env": {},
            "cwd": cwd, "project_root": cwd, "exit_code": 0,
            "sentinels": [{"name": name, "verdict": verdict, "line": line}]}


_MOVE = {"old": "C:/p/lib/pkg", "new": "C:/p/src/pkg", "at": "2026-10-14T10:00:00", "session_id": "s", "turn_seq": 3}


def _mv_gate(receipts, moves=(_MOVE,), scan_hits=None):
    import wg_verify_ledger as vl2
    code, _ = vl2.reconcile_gate_parts("", receipts, 3, [], [], vl2.reconcile_cfg({}), moves=list(moves),
                                       move_scan_hits=scan_hits or {})
    return code or ""


def test_045_move_code_dir_needs_scan_and_sample_missing_both():
    """搬了含 .py 的目錄、兩張收據都沒有 → 擋，訊息含規則名與兩張缺的收據名。"""
    text = _mv_gate([])
    assert ("v", "MOVE_CODE_DIR_NEEDS_SCAN_AND_SAMPLE") in rr.parse_hit_rules(text)
    assert "MOVE_PATH_SCAN" in text and "MOVE_SAMPLE_CHECK" in text and "lib/pkg" in text


def test_045_move_code_dir_needs_scan_and_sample_both_present_passes():
    """搬目錄＋掃描 hits=0＋抽樣 PASS（都在搬之後、指令乾淨）→ 放行，也不欠 (d) 案例。"""
    scan = _mv_receipt(f"python {_MV_TOOL} scan --old lib/pkg --new src/pkg", "MOVE_PATH_SCAN DONE hits=0",
                       "2026-10-14T10:01:00")
    sample = _mv_receipt(f'python {_MV_TOOL} sample --for src/pkg --run "python -c \\"import src.pkg\\""', "MOVE_SAMPLE_CHECK PASS",
                         "2026-10-14T10:02:00", verdict="PASS", name="MOVE_SAMPLE_CHECK")
    assert _mv_gate([scan, sample]) == ""


def test_045_move_code_dir_needs_scan_and_sample_state_receipts_use_kv_and_seq():
    """state 裡的收據哨兵存 kv（沒有 line）、帶 session 事件序號：hits 從 kv 讀；同一秒內的先後看序號。"""
    move = {**_MOVE, "seq": 5}
    scan = {**_mv_receipt(f"python {_MV_TOOL} scan --old lib/pkg --new src/pkg", "", _MOVE["at"]), "seq": 6,
            "sentinels": [{"name": "MOVE_PATH_SCAN", "verdict": "DONE", "kv": {"hits": "0"}}]}
    sample = {**_mv_receipt(f"python {_MV_TOOL} sample --for src/pkg --run pytest", "", _MOVE["at"], verdict="PASS",
                            name="MOVE_SAMPLE_CHECK"), "seq": 7}
    assert _mv_gate([scan, sample], moves=(move,)) == ""
    early = {**scan, "seq": 4}
    assert "MOVE_PATH_SCAN" in _mv_gate([early, sample], moves=(move,))       # 同一秒但序號在搬之前


def test_045_move_code_dir_needs_scan_and_sample_rejects_stale_forged_or_other_dir():
    """收據在搬之前、指令自己 echo 哨兵、掃的是別的舊路徑 → 都不算。"""
    sample = _mv_receipt(f"python {_MV_TOOL} sample --for src/pkg --run pytest", "MOVE_SAMPLE_CHECK PASS", "2026-10-14T10:02:00",
                         verdict="PASS", name="MOVE_SAMPLE_CHECK")
    for scan in (_mv_receipt(f"python {_MV_TOOL} scan --old lib/pkg --new src/pkg", "MOVE_PATH_SCAN DONE hits=0",
                             "2026-10-14T09:59:00"),
                 _mv_receipt("echo MOVE_PATH_SCAN DONE hits=0 lib/pkg", "MOVE_PATH_SCAN DONE hits=0", "2026-10-14T10:01:00"),
                 _mv_receipt(f"python {_MV_TOOL} scan --old lib/other --new src/pkg", "MOVE_PATH_SCAN DONE hits=0",
                             "2026-10-14T10:01:00")):
        text = _mv_gate([scan, sample])
        assert "MOVE_CODE_DIR_NEEDS_SCAN_AND_SAMPLE" in text and "MOVE_PATH_SCAN" in text, scan["cmd"]


def test_045_move_code_dir_needs_scan_and_sample_hits_listed():
    """掃描收據 hits>0 而且之後沒重掃到 0 → 擋，訊息列命中清單前幾筆。"""
    scan = _mv_receipt(f"python {_MV_TOOL} scan --old lib/pkg --new src/pkg", "MOVE_PATH_SCAN DONE hits=2",
                       "2026-10-14T10:01:00")
    sample = _mv_receipt(f"python {_MV_TOOL} sample --for src/pkg --run pytest", "MOVE_SAMPLE_CHECK PASS", "2026-10-14T10:02:00",
                         verdict="PASS", name="MOVE_SAMPLE_CHECK")
    text = _mv_gate([scan, sample], scan_hits={"c:/p/lib/pkg": ["tools/run.py:3: lib/pkg/a.py", "README.md:9: lib/pkg"]})
    assert "MOVE_CODE_DIR_NEEDS_SCAN_AND_SAMPLE" in text and "hits=2" in text and "tools/run.py:3" in text


def test_045_move_code_dir_needs_scan_and_sample_detects_only_code_dirs(tmp_path):
    """PostToolUse 記搬目錄的事實：mv、Move-Item、git mv 搬含程式檔的目錄才記；只搬文件目錄不記。"""
    from handlers import post_tool_use as ptu
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "docs2").mkdir()
    (tmp_path / "docs2" / "a.md").write_text("# a\n", encoding="utf-8")
    st = {"turn_seq": 3}
    for tool, cmd in (("Bash", "mv lib/pkg src/pkg"), ("Bash", "git mv lib/pkg src/pkg"),
                      ("PowerShell", "Move-Item lib/pkg src/pkg"), ("Bash", "mv docs docs2")):
        ptu._note_moved_code_dirs(st, "s", tool, {"command": cmd}, str(tmp_path), {})
    moves = st.get("moved_code_dirs") or []
    assert [Path(m["new"]).name for m in moves] == ["pkg", "pkg", "pkg"]
    assert all(rr.canon_path(m["old"]) == rr.canon_path(str(tmp_path / "lib" / "pkg")) for m in moves)


def test_045_move_code_dir_needs_scan_and_sample_glob_copy_is_not_a_move(tmp_path):
    """`cp hooks/*.py <暫存>/hooks/` 是複製：來源寫成萬用字元時字面路徑不存在，不能因此當成搬目錄。
    萬用字元來源展開後還有符合的檔＝複製：記錄端不記，收尾端已記下的也剔除。真的 mv 掉（展開後沒有符合）照記。"""
    from handlers import post_tool_use as ptu
    from handlers import stop as stp
    (tmp_path / "hooks").mkdir()
    (tmp_path / "hooks" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "copy" / "hooks").mkdir(parents=True)
    (tmp_path / "copy" / "hooks" / "a.py").write_text("x = 1\n", encoding="utf-8")       # cp 之後的樣子：兩邊都有
    st = {"turn_seq": 3}
    ptu._note_moved_code_dirs(st, "s", "Bash", {"command": "cp hooks/*.py copy/hooks/"}, str(tmp_path), {})
    assert not st.get("moved_code_dirs"), st.get("moved_code_dirs")
    old = str(tmp_path / "hooks" / "*.py")
    st = {"moved_code_dirs": [{"old": old, "new": str(tmp_path / "copy" / "hooks"), "session_id": "s", "seq": 1}]}
    assert stp._move_inputs(st, "s")[0] == []                                              # 舊帳上誤記的也不再欠
    (tmp_path / "hooks" / "a.py").unlink()                                                 # 真的搬走：展開後沒有符合
    assert len(stp._move_inputs(st, "s")[0]) == 1


def test_045_move_code_dir_needs_scan_and_sample_detect_git_forms_and_agent(tmp_path):
    """codex BLOCK 1～3：git mv 單一檔案進目錄不算；git -C、先 cd 再 git mv、一次搬多個來源都要記；子代理搬的也記（帶 agent_id）。"""
    from handlers import post_tool_use as ptu
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")        # 剛被 git mv a.py src/ 搬進來的檔
    for d in ("sub/new/m.py", "target/a/m.py", "target/b/m.py"):
        (tmp_path / d).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / d).write_text("x = 1\n", encoding="utf-8")

    def moved(cmd, agent_id=""):
        st = {"turn_seq": 3}
        ptu._note_moved_code_dirs(st, "s", "Bash", {"command": cmd}, str(tmp_path), {}, agent_id=agent_id)
        return [(Path(m["old"]).name, Path(m["new"]).name, m.get("agent_id", "")) for m in st.get("moved_code_dirs") or []]

    assert moved("git mv a.py src/") == []
    assert moved("git -C sub mv old new") == [("old", "new", "")]
    assert moved("cd sub && git mv old new") == [("old", "new", "")]
    assert moved("git mv a b target/") == [("a", "a", ""), ("b", "b", "")]
    assert moved("git -C sub mv old new", agent_id="a1") == [("old", "new", "a1")]


def test_045_move_code_dir_needs_scan_and_sample_root_arg_and_sample_binding():
    """codex BLOCK 4：掃描用 --root 指專案根時，--old 照 --root 解；BLOCK 5：抽樣要用 --for 點名涵蓋哪個新目錄，
    只抽 a 不能替 b 清帳。"""
    scan = _mv_receipt(f"python {_MV_TOOL} scan --root C:/p --old lib/pkg --new src/pkg", "MOVE_PATH_SCAN DONE hits=0",
                       "2026-10-14T10:01:00", cwd="C:/p/tools")
    sample = _mv_receipt(f'python {_MV_TOOL} sample --for src/pkg --run "python -c \\"import src.pkg\\""',
                         "MOVE_SAMPLE_CHECK PASS", "2026-10-14T10:02:00", verdict="PASS", name="MOVE_SAMPLE_CHECK")
    assert _mv_gate([scan, sample]) == ""
    other = {**_MOVE, "old": "C:/p/lib/other", "new": "C:/p/src/other"}
    scan_b = _mv_receipt(f"python {_MV_TOOL} scan --old lib/other --new src/other", "MOVE_PATH_SCAN DONE hits=0",
                         "2026-10-14T10:01:30")
    text = _mv_gate([scan, scan_b, sample], moves=(_MOVE, other))
    assert "lib/other" in text.replace("\\", "/") and "MOVE_SAMPLE_CHECK" in text and "lib/pkg → " not in text.replace("\\", "/")


def test_045_move_code_dir_needs_scan_and_sample_tool_csproj_and_escaped_paths(tmp_path):
    """codex BLOCK 6：C# 明列 Compile Include 的專案要看編譯項目（指向舊位置照 FAIL、用 ..\\shared 連結外部目錄算 PASS）；
    BLOCK 7：掃描要抓 JSON／程式字串裡的雙反斜線寫法。"""
    import subprocess

    def run(*args):
        r = subprocess.run([sys.executable, "-X", "utf8", _MV_TOOL, *args], cwd=str(tmp_path), capture_output=True,
                           text=True, encoding="utf-8")
        return r.stdout.strip().splitlines()[-1]

    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "A.cs").write_text("class A {}\n", encoding="utf-8")
    (tmp_path / "Old.csproj").write_text('<Project ToolsVersion="15.0"><ItemGroup><Compile Include="lib\\pkg\\A.cs" />'
                                         '</ItemGroup></Project>\n', encoding="utf-8")
    assert run("sample", "--for", "src/pkg", "--csproj-check", "src/pkg") == "MOVE_SAMPLE_CHECK FAIL"
    (tmp_path / "Old.csproj").unlink()
    (tmp_path / "shared").mkdir()
    (tmp_path / "shared" / "B.cs").write_text("class B {}\n", encoding="utf-8")
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "App.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk"><ItemGroup>'
                                                 '<Compile Include="..\\shared\\**\\*.cs" /></ItemGroup></Project>\n',
                                                 encoding="utf-8")
    assert run("sample", "--for", "shared", "--csproj-check", "shared") == "MOVE_SAMPLE_CHECK PASS"
    (tmp_path / "cfg.json").write_text('{"entry": "lib\\\\pkg\\\\a.py"}\n', encoding="utf-8")
    assert run("scan", "--old", "lib/pkg", "--new", "src/pkg") == "MOVE_PATH_SCAN DONE hits=1"


# ─── 退件 003（總控台 codex 六條）：照擋訊息做一定過得了、一般寫法不漏記 ─────────────────────────────────

def test_045_move_code_dir_needs_scan_and_sample_subagent_receipts_pair_with_its_moves():
    """BLOCK 1：子代理搬目錄、自己跑 scan／sample（收據在 sid#agent:<id>）：子代理收尾只查自己的搬移；主 session 收尾也認得。"""
    from handlers import stop
    import wg_verify_ledger as vl2
    mv = {**_MOVE, "session_id": "s", "agent_id": "a1"}
    scan = _mv_receipt(f"python {_MV_TOOL} scan --old lib/pkg --new src/pkg", "MOVE_PATH_SCAN DONE hits=0",
                       "2026-10-14T10:01:00")
    sample = _mv_receipt(f"python {_MV_TOOL} sample --for src/pkg --run pytest", "MOVE_SAMPLE_CHECK PASS",
                         "2026-10-14T10:02:00", verdict="PASS", name="MOVE_SAMPLE_CHECK")
    state = {"moved_code_dirs": [mv], "verify_receipts": {vl2.agent_receipt_key("s", "a1"): [scan, sample]}}
    for key in (vl2.agent_receipt_key("s", "a1"), "s"):
        moves, receipts = stop._move_inputs(state, key)
        assert [m["agent_id"] for m in moves] == ["a1"], key
        code, _ = vl2.reconcile_gate_parts("", [], 3, [], [], vl2.reconcile_cfg({}), moves=moves, move_receipts=receipts)
        assert not code, (key, code)
    assert stop._move_inputs(state, vl2.agent_receipt_key("s", "a2"))[0] == []           # 別的子代理不背這筆


def test_045_move_code_dir_needs_scan_and_sample_cd_before_tool():
    """BLOCK 2：先 cd 再跑工具，--old／--root 照那一段的有效 cwd 解。"""
    move = {**_MOVE, "old": "C:/p/sub/lib/pkg", "new": "C:/p/sub/src/pkg"}
    sample = _mv_receipt(f"cd C:/p/sub && python {_MV_TOOL} sample --for src/pkg --run pytest", "MOVE_SAMPLE_CHECK PASS",
                         "2026-10-14T10:02:00", verdict="PASS", name="MOVE_SAMPLE_CHECK")
    for cmd in (f"cd C:/p/sub && python {_MV_TOOL} scan --old lib/pkg --new src/pkg",
                f"cd C:/p && python {_MV_TOOL} scan --root sub --old lib/pkg --new src/pkg"):
        scan = _mv_receipt(cmd, "MOVE_PATH_SCAN DONE hits=0", "2026-10-14T10:01:00")
        assert _mv_gate([scan, sample], moves=(move,)) == "", cmd


def test_045_move_code_dir_needs_scan_and_sample_message_commands_paste_back():
    """BLOCK 3：擋訊息給的指令照 Bash／PowerShell 各一行、有引號，路徑含空白照樣解回原路徑。"""
    import shlex
    old, new = r"C:\work\My Project\lib\pkg", r"C:\work\My Project\src\pkg"
    v = rr.move_dir_verdict({"old": old, "new": new}, None, False)
    bash = [e.split("：", 1)[1] for e in v.evidence if e.startswith("掃描（Bash）")]
    ps = [e.split("：", 1)[1] for e in v.evidence if e.startswith("掃描（PowerShell）")]
    assert bash and ps
    toks = shlex.split(bash[0])
    assert toks[toks.index("--old") + 1] == old and toks[toks.index("--new") + 1] == new
    assert toks[1].replace("\\", "/").endswith("tools/move-dir-check.py")
    ps_toks = re.findall(r"'((?:[^']|'')*)'|(\S+)", ps[0])
    words = [(a.replace("''", "'") if a else b) for a, b in ps_toks]
    assert words[words.index("--old") + 1] == old and words[words.index("--new") + 1] == new


def test_045_move_code_dir_needs_scan_and_sample_tool_files_split_across_projects(tmp_path):
    """BLOCK 4：新目錄裡 A.cs 由 A.csproj、B.cs 由 B.csproj 編進去 → PASS；任何例外也要印 FAIL 尾行。"""
    import subprocess
    (tmp_path / "shared").mkdir()
    (tmp_path / "shared" / "A.cs").write_text("class A {}\n", encoding="utf-8")
    (tmp_path / "shared" / "B.cs").write_text("class B {}\n", encoding="utf-8")
    for name in ("A", "B"):
        (tmp_path / f"{name}.csproj").write_text(f'<Project ToolsVersion="15.0"><ItemGroup><Compile Include="shared\\{name}.cs" />'
                                                 '</ItemGroup></Project>\n', encoding="utf-8")
    r = subprocess.run([sys.executable, "-X", "utf8", _MV_TOOL, "sample", "--for", "shared", "--csproj-check", "shared"],
                       cwd=str(tmp_path), capture_output=True, text=True, encoding="utf-8")
    assert r.stdout.strip().splitlines()[-1] == "MOVE_SAMPLE_CHECK PASS", r.stdout + r.stderr


def test_045_move_code_dir_needs_scan_and_sample_detect_powershell_rename_and_set_location(tmp_path):
    """BLOCK 5：PowerShell 的 Rename-Item（新名字在同一層）與 Set-Location 之後的 Move-Item 都要記。"""
    from handlers import post_tool_use as ptu
    for d in ("lib/pkg2/m.py", "sub/src/pkg/m.py"):
        (tmp_path / d).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / d).write_text("x = 1\n", encoding="utf-8")

    def moved(cmd):
        st = {"turn_seq": 3}
        ptu._note_moved_code_dirs(st, "s", "PowerShell", {"command": cmd}, str(tmp_path), {})
        return [(Path(m["old"]).relative_to(tmp_path).as_posix(), Path(m["new"]).relative_to(tmp_path).as_posix())
                for m in st.get("moved_code_dirs") or []]

    assert moved("Rename-Item lib/pkg pkg2") == [("lib/pkg", "lib/pkg2")]
    assert moved("Rename-Item -Path lib/pkg -NewName pkg2") == [("lib/pkg", "lib/pkg2")]
    assert moved("Set-Location sub; Move-Item lib/pkg src/pkg") == [("sub/lib/pkg", "sub/src/pkg")]


def test_045_move_code_dir_needs_scan_and_sample_move_chain_uses_final_place():
    """BLOCK 6：搬了又搬：lib/pkg→src/pkg→lib/pkg 完整搬回不欠；lib/pkg→src/pkg→app/pkg 只欠最終位置的收據。"""
    first = {**_MOVE, "seq": 1}
    back = {"old": "C:/p/src/pkg", "new": "C:/p/lib/pkg", "at": "2026-10-14T10:00:30", "seq": 2, "session_id": "s"}
    assert _mv_gate([], moves=(first, back)) == ""
    onward = {"old": "C:/p/src/pkg", "new": "C:/p/app/pkg", "at": "2026-10-14T10:00:30", "seq": 2, "session_id": "s"}
    text = _mv_gate([], moves=(first, onward))
    assert text.count("MOVE_CODE_DIR_NEEDS_SCAN_AND_SAMPLE") == 1 and "app" in text and "src\\pkg" not in text
    scan = {**_mv_receipt(f"python {_MV_TOOL} scan --old lib/pkg --new app/pkg", "MOVE_PATH_SCAN DONE hits=0",
                          "2026-10-14T10:01:00"), "seq": 3}
    sample = {**_mv_receipt(f"python {_MV_TOOL} sample --for app/pkg --run pytest", "MOVE_SAMPLE_CHECK PASS",
                            "2026-10-14T10:02:00", verdict="PASS", name="MOVE_SAMPLE_CHECK"), "seq": 4}
    assert _mv_gate([scan, sample], moves=(first, onward)) == ""


# ─── 常見指令寫法變體（對人總控台 #36：解析指令字串的規則，每種一般寫法都要判對）──────────────────────────────

_GREEN_RED = ("pytest -q tests/test_a.py", "FAILED tests/test_a.py::test_bad - assert 0\n1 failed")


@pytest.mark.parametrize("green, keeps", [
    ("python -X utf8 -m pytest -q tests/test_a.py", False),                         # python -m pytest：不是篩選
    ("pytest -q tests/test_a.py", False),                                           # 直呼 pytest
    ("python -m pytest -q tests/test_a.py -k test_ok", True),                       # -k 判不了照留
    ("pytest tests/test_a.py::test_bad", False),                                    # :: 點名的就是紅案
    ("pytest tests/test_a.py::test_ok", True),                                      # :: 點名別案
    ("python -m pytest C:/p/tests/test_a.py::test_bad", False),                     # 絕對路徑的節點 id
    ('& "C:\\Python\\python.exe" -X utf8 -m pytest -q tests\\test_a.py', False),   # PowerShell 呼叫 python.exe
    ("Set-Location C:\\p; python.exe -m pytest tests\\test_a.py::test_ok", True),  # PowerShell Set-Location 之後
    ("Set-Location C:\\p; python.exe -m pytest tests\\test_a.py::test_bad", False),
], ids=["py-m", "pytest", "k", "node-red", "node-other", "abs-node", "ps-exe", "ps-setloc-other", "ps-setloc-red"])
def test_045_green_narrowed_keeps_uncovered_red_command_variants(green, keeps):
    """002 的篩選判定（GREEN_NARROWED_KEEPS_UNCOVERED_RED）對各種一般寫法都判對：owed＝True 是照留那筆紅。"""
    assert rr.green_covers_red_verdict(*_GREEN_RED, green).owed is keeps


@pytest.mark.parametrize("scan_cmd, sample_cmd, tool", [
    (f"python -X utf8 {_MV_TOOL} scan --old lib/pkg --new src/pkg",
     f"python -X utf8 {_MV_TOOL} sample --for src/pkg --run \"python -X utf8 -m pytest -q tests/test_pkg.py\"", "Bash"),
    ("python tools/move-dir-check.py scan --old lib/pkg --new src/pkg",
     "python tools/move-dir-check.py sample --for src/pkg --run \"pytest tests/test_pkg.py -k smoke\"", "Bash"),
    (f"python {_MV_TOOL} scan --old C:/p/lib/pkg --new C:/p/src/pkg",
     f"python {_MV_TOOL} sample --for C:/p/src/pkg --run \"pytest tests/test_pkg.py::test_import\"", "Bash"),
    (f'& "C:\\Python\\python.exe" "{_MV_TOOL}" scan --old lib\\pkg --new src\\pkg',
     f'& "C:\\Python\\python.exe" "{_MV_TOOL}" sample --for src\\pkg --run "python.exe -m pytest tests\\test_pkg.py"', "PowerShell"),
    (f'Set-Location C:\\p; python.exe "{_MV_TOOL}" scan --old lib\\pkg --new src\\pkg',
     f'Set-Location C:\\p; python.exe "{_MV_TOOL}" sample --for src\\pkg --run "pytest"', "PowerShell"),
], ids=["py-X-utf8", "relative-tool", "abs-paths", "ps-exe", "ps-setloc"])
def test_045_move_code_dir_needs_scan_and_sample_command_variants(scan_cmd, sample_cmd, tool):
    """(v) 的收據判定對各種一般寫法都判對：兩張收據配上搬移就放行。"""
    cwd = "C:/p/tools" if "Set-Location" in scan_cmd else "C:/p"
    scan = {**_mv_receipt(scan_cmd, "MOVE_PATH_SCAN DONE hits=0", "2026-10-14T10:01:00", cwd=cwd), "tool": tool}
    sample = {**_mv_receipt(sample_cmd, "MOVE_SAMPLE_CHECK PASS", "2026-10-14T10:02:00", verdict="PASS",
                            name="MOVE_SAMPLE_CHECK", cwd=cwd), "tool": tool}
    assert _mv_gate([scan, sample]) == "", scan_cmd


def test_045_move_code_dir_needs_scan_and_sample_tool_scan_and_sample(tmp_path):
    """掃描工具：舊路徑的絕對、相對寫法都算命中，--allow 的檔不算；抽樣：指令 exit 0＝PASS、C# 新目錄要在某個 .csproj 底下。"""
    import subprocess
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "run.py").write_text('P = "lib/pkg/a.py"\nQ = r"lib\\pkg"\n', encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text("moved lib/pkg to src/pkg\n", encoding="utf-8")

    def run(*args):
        r = subprocess.run([sys.executable, "-X", "utf8", _MV_TOOL, *args], cwd=str(tmp_path), capture_output=True,
                           text=True, encoding="utf-8")
        return r.returncode, r.stdout

    rc, out = run("scan", "--old", "lib/pkg", "--new", "src/pkg")
    assert out.strip().splitlines()[-1] == "MOVE_PATH_SCAN DONE hits=3" and "tools/run.py:1" in out
    rc, out = run("scan", "--old", "lib/pkg", "--new", "src/pkg", "--allow", "CHANGELOG.md", "--allow", "tools/run.py")
    assert out.strip().splitlines()[-1] == "MOVE_PATH_SCAN DONE hits=0"
    rc, out = run("sample", "--for", "src/pkg", "--run", f'"{sys.executable}" -c "print(1)"')
    assert rc == 0 and out.strip().splitlines()[-1] == "MOVE_SAMPLE_CHECK PASS"
    rc, out = run("sample", "--for", "src/pkg", "--run", f'"{sys.executable}" -c "raise SystemExit(3)"')
    assert rc == 1 and out.strip().splitlines()[-1] == "MOVE_SAMPLE_CHECK FAIL"
    (tmp_path / "src" / "pkg" / "A.cs").write_text("class A {}\n", encoding="utf-8")
    rc, out = run("sample", "--for", "src/pkg", "--csproj-check", "src/pkg")
    assert out.strip().splitlines()[-1] == "MOVE_SAMPLE_CHECK FAIL"                    # 沒有任何 .csproj 囊括
    (tmp_path / "src" / "App.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk"></Project>\n', encoding="utf-8")
    rc, out = run("sample", "--for", "src/pkg", "--csproj-check", "src/pkg")
    assert out.strip().splitlines()[-1] == "MOVE_SAMPLE_CHECK PASS"


def test_045_retry_counts_rerun_cycles_dpm_trigger_names_rounds():
    """DeepPostMortem 的觸發句也印第幾輪與每輪證據。"""
    from handlers import stop
    st = {"turn_seq": 1}
    _rr_run(st, "tests/x.py::t1")
    _rr_edit(st)
    _rr_run(st, "tests/x.py::t2")
    _rr_edit(st)
    _rr_run(st, "tests/x.py::t3")
    text = stop._dpm_instruction(st, {})
    assert text.startswith("[Guardian:DeepPostMortem]") and "第 2 輪" in text and "tests/x.py::t3" in text
    assert ("r", "RETRY_COUNTS_RERUN_CYCLES") in rr.parse_hit_rules(text)       # 證據行在標頭下一行，parse_hits 讀得到


def test_045_green_same_case_clears():
    assert rr.green_clears_red("python hooks/verify/verify_x.py", "python -X utf8 hooks/verify/verify_x.py && echo ok")
    assert rr.green_clears_red("pytest hooks/verify/verify_x.py::test_a", r"python -m pytest -q hooks\verify\verify_x.py")
    assert not rr.green_clears_red("pytest hooks/verify/verify_x.py", "pytest hooks/verify/verify_y.py")
    assert not rr.green_clears_red("pytest", "pytest -q")                     # 都沒點名檔：交給既有規則
    assert rr.case_files_in_cmd("python a/b.py c.PY") == ["a/b.py", "c.py"]   # 保留路徑，不只檔名
    # codex 001 BLOCK 4：不同目錄的同名案例不互清；給 cwd 時比絕對路徑
    assert not rr.green_clears_red("python service_a/tests/test_api.py", "python -X utf8 service_b/tests/test_api.py")
    assert not rr.green_clears_red("python tests/test_api.py", "python tests/test_api.py", "C:/svc_a", "C:/svc_b")
    assert rr.green_clears_red("python tests/test_api.py", "python -X utf8 C:/svc_a/tests/test_api.py", "C:/svc_a", "C:/other")


# ═══ C-G3／C-G10（track-goal-evidence）：需求目標樹完整對照的證據規則 ═══

def test_goal_receipt_red_and_green():
    """收據紅＝任一哨兵 FAIL 或 exit 不是 0（沒記 exit 不算紅）；綠＝有 PASS 而且沒紅。"""
    assert rr.receipt_red(["X_CHECK:FAIL"], 0) and rr.receipt_red(["X_CHECK:PASS"], 1)
    assert not rr.receipt_red(["X_CHECK:PASS"], 0) and not rr.receipt_red([], None)
    assert rr.receipt_green(["PYTEST:PASS"], 0) and rr.receipt_green(["PYTEST:PASS"], None)
    assert not rr.receipt_green(["X:DONE"], 0) and not rr.receipt_green(["A:PASS", "B:FAIL"], 0)


def test_goal_done_needs_case_or_receipt_verdicts():
    """GOAL_DONE_NEEDS_CASE_OR_RECEIPT：寫碼類樹標達成要有沒紅的收據或讀碼級案例；記憶知識類不擋；擋時證據列出現有的每一筆。"""
    file_read = ("file", "read", False, "讀碼 檔案 a.py")
    v = rr.goal_done_evidence_verdict("T1", True, [file_read])
    assert v.rule == "GOAL_DONE_NEEDS_CASE_OR_RECEIPT" and v.owed and "T1" in v.why
    assert v.evidence[0] == "T1 現有證據：讀碼 檔案 a.py"
    assert not rr.goal_done_evidence_verdict("T1", False, [file_read]).owed
    assert not rr.goal_done_evidence_verdict("T1", True, [file_read, ("case", "read", False, "c")]).owed
    assert not rr.goal_done_evidence_verdict("T1", True, [("receipt", "measured", False, "R3")]).owed
    red = rr.goal_done_evidence_verdict("T1", True, [("receipt", "measured", True, "實測 收據 R3")])
    assert red.owed and "實測 收據 R3（紅）" in red.evidence[0]
    assert rr.goal_done_evidence_verdict("T1", True, [("case", "inferred", False, "c")]).owed


def test_goal_inferred_max_partial_verdicts():
    """GOAL_INFERRED_MAX_PARTIAL：證據全是推論 → 擋（不分類別）；有一筆不是推論就不歸這條。"""
    v = rr.goal_inferred_verdict("T2", [("file", "inferred", False, "推論 檔案 a.py")])
    assert v.rule == "GOAL_INFERRED_MAX_PARTIAL" and v.owed and v.evidence == ("T2 現有證據：推論 檔案 a.py",)
    assert not rr.goal_inferred_verdict("T2", [("file", "inferred", False, "x"), ("file", "read", False, "y")]).owed
    assert not rr.goal_inferred_verdict("T2", []).owed                         # 沒證據歸「沒附證據」那條


def _cases(cmd, cwd):
    return rr.case_files_in_cmd(cmd, cwd)


@pytest.mark.parametrize("runs, want", [
    ([(1, "pytest -q verify_a.py", "C:/p/svc", True, False), (2, "pytest -q verify_a.py", "C:/p/svc", False, True)], (1, 2)),
    ([(1, "pytest -q verify_a.py", "C:/p/svc", False, True)], None),
    ([(1, "pytest -q verify_a.py", "C:/p/svc", False, True), (2, "pytest -q verify_a.py", "C:/p/svc", True, False)], None),
    ([(1, "pytest -q verify_b.py", "C:/p/svc", True, False), (2, "pytest -q verify_a.py", "C:/p/svc", False, True)], None),
    # 比絕對路徑：別的目錄的同名案例紅了不算
    ([(1, "pytest -q verify_a.py", "C:/p/other", True, False), (2, "pytest -q verify_a.py", "C:/p/svc", False, True)], None),
    ([(1, "pytest -q verify_a.py::test_x", "C:/p/svc", True, False), (2, r"pytest C:\P\svc\verify_a.py", "C:/x", False, True)],
     (1, 2)),
], ids=["red-green", "green-only", "green-red", "other-file", "other-dir-same-name", "abs-and-node-id"])
def test_goal_case_red_then_green(runs, want):
    """CASE_RED_THEN_GREEN：點名同一個案例檔的收據裡先有紅、之後有綠 → (紅的號, 綠的號)；對不上 None（只記錄，不擋）。"""
    rows = [(seq, _cases(cmd, cwd), red, green) for seq, cmd, cwd, red, green in runs]
    assert rr.red_then_green(r"C:\p\svc\verify_a.py", rows) == want


def test_goal_case_files_in_cmd_quoted_path_with_space():
    """CASE_RED_THEN_GREEN 與 GREEN_SAME_CASE_CLEARS 共用的取檔：引號裡含空白的路徑整段算一個（codex BLOCK 1）。"""
    assert rr.case_files_in_cmd('pytest -q "my tests/test_a.py"', "C:/p") == ["c:/p/my tests/test_a.py"]
    assert rr.case_files_in_cmd("pytest 'my tests/test_a.py::test_x' b.py", "C:/p") == ["c:/p/my tests/test_a.py", "c:/p/b.py"]
    assert rr.case_files_in_cmd('python -c "import x; open(\'a.py\')"') == ["a.py"]          # 引號裡不是單一路徑照舊取
    assert rr.green_clears_red('pytest "my tests/test_a.py"', 'python -m pytest -q "my tests/test_a.py"', "C:/p", "C:/p")
    assert not rr.green_clears_red('pytest "my tests/test_a.py"', "pytest tests/test_a.py", "C:/p", "C:/p")


# ─── C-G0：LOCATE_LINES_NEED_ROLE_AND_TWO_CANDIDATES／EDITED_PART_NEEDS_GOAL_NODE ───

_CG0_NODE = "共用字典不再被兩邊改"
_CG0_TWO = "候選 A 邏輯層；候選 B 存檔時序；選 A 因為字典只在邏輯層被寫"


@pytest.mark.parametrize("root, goal, owed, want", [
    (_CG0_TWO, "T1.1（共用字典的唯一寫入點）", False, ""),
    ("第一根因 共用字典被兩邊改，第二根因 存檔時序；先修第一個因為第二個是它的結果", "T1.1（唯一寫入點）", False, ""),
    ("根因在邏輯層；第二個不存在，因為只有這一處寫入", "T1.1（唯一寫入點）", False, ""),
    ("候選 A 邏輯層；候選 B 不存在因為資料層只讀", "T1.1（唯一寫入點）", False, ""),
    ("候選一 邏輯層；候選二 資料層；理由：資料層只讀", "T1.1 (唯一寫入點)", False, ""),
    ("候選 A 邏輯層，候選 B 資料層，選 A 因為只有邏輯層寫", "T1.1（唯一寫入點）", False, ""),        # 逗號分隔
    ("候選 A 快取；候選 B 時序；選 A 因為比候選 B 好重現", "T1.1（唯一寫入點）", False, ""),        # 理由裡提到候選
    ("候選 A 無鎖競爭；候選 B 沒有重試；選 A 因為只有它重現", "T1.1（唯一寫入點）", False, ""),    # 描述以「無／沒有」開頭不是不存在
    # codex BLOCK：括號外的角色、零候選只寫第二個不存在、候選描述自己的「原因」不是選擇理由
    ("候選 A 快取；候選 B 時序；選 A 因為可重現", "T1.1 —— 負責同步畫面", True, "角色"),
    ("第二個不存在因為目前只有這條線索", "T1.1（負責同步畫面）", True, "只辨識出 0 個"),
    ("候選 A 的原因是快取失效；候選 B 是寫入時序", "T1.1（負責同步畫面）", True, "選擇理由"),
    ("邏輯層", "T1.1（唯一寫入點）", True, "只辨識出 0 個"),
    ("候選 A 邏輯層", "T1.1（唯一寫入點）", True, "只辨識出 1 個"),
    ("候選 A 邏輯層；候選 B 資料層", "T1.1（唯一寫入點）", True, "選擇理由"),
    ("候選 A 根因為邏輯層；候選 B 根因為資料層", "T1.1（唯一寫入點）", True, "選擇理由"),   # 「根因為」不是理由
    ("根因在邏輯層；第二根因不存在", "T1.1（唯一寫入點）", True, "只辨識出 0 個"),          # 不存在沒寫為什麼
    (_CG0_TWO, "T1.1", True, "角色"),
    (_CG0_TWO, "T1.1（）", True, "角色"),
    (_CG0_TWO, "T1.1（這一塊在目標裡的角色）", True, "角色"),
    (_CG0_TWO, "T1.1（共用字典不再被兩邊改）", True, "照抄"),
    ("邏輯層", "T1.1", True, "角色"),
])
def test_cg0_locate_lines_need_role_and_two_candidates(root, goal, owed, want):
    """LOCATE_LINES_NEED_ROLE_AND_TWO_CANDIDATES：第四行括號內要有角色（非空、非佔位、非節點原文照抄）；根因層要兩個候選＋
    選擇理由，或一個候選＋「第二個不存在因為…」。只看結構。"""
    v = rr.locate_lines_verdict(root, goal, "T1.1", _CG0_NODE)
    assert v.rule == "LOCATE_LINES_NEED_ROLE_AND_TWO_CANDIDATES" and v.owed is owed, v
    assert want in v.why
    if owed:
        assert any(e.startswith("定位｜根因層：") for e in v.evidence) and any(e.startswith("定位｜目標：") for e in v.evidence)


_B1_GOAL = "T1.1/T1.4（by-product 輸出、用台北時間歸月）、T1.2（不碰 monthly 路徑）、T1.3（測試）"
_B1_CRIT = ("month_of 用 UTC 不合理，更好的做法是改台北時間，但需財務拍板；同類還可能在哪：month_of 唯一呼叫點是 "
            "report.monthly_totals（grep 已確認），無其他")


def test_004_locate_semantic_role_after_chained_nodes_and_reason_anywhere():
    """第三跑 B-1（擋 4 次）：第四行「T1.1/T1.4（角色）」幾個節點串在一起也認得角色；第五行把被批判的對象寫在「不合理」前面
    也算有理由。語意判：有候選、有理由、有節點與角色、有更好的做法與同類就放行，句型只當建議。"""
    assert rr.goal_role(_B1_GOAL, "T1.1") == "by-product 輸出、用台北時間歸月"
    assert rr.goal_role("T1.2、T1.3（測試）", "T1.2") == "測試"
    assert not rr.locate_lines_verdict(_CG0_TWO, _B1_GOAL, "T1.1", _CG0_NODE).owed
    assert not rr.locate_critique_verdict(_B1_CRIT).owed
    # 改造包 Q：批判行只查有沒有內容，「這段寫法不合理」這種沒指出哪裡的也放（寫得好不好是 AI 的判斷，不是閘的）
    assert not rr.locate_critique_verdict("這段寫法不合理，更好的做法是改台北時間；同類還可能在哪：無，因為只有一處").owed


def test_cg0_locate_lines_both_missing_listed_together():
    """角色與候選都缺 → 一條擋訊息列兩項（不必擋兩輪才知道）。"""
    v = rr.locate_lines_verdict("邏輯層", "T1.1", "T1.1", _CG0_NODE)
    assert v.owed and "角色" in v.why and "候選" in v.why


def test_cg0_edited_part_needs_goal_node():
    """EDITED_PART_NEEDS_GOAL_NODE：改過程式檔的部位要掛到樹裡活著的節點；沒掛的列「<部位>：<改的檔> 沒掛目標」。"""
    v = rr.edited_part_goal_verdict([("戰鬥", ["C:/p/Game/Battle/A.cs"], "linked"),
                                     ("UI", ["C:/p/Game/UI/B.cs", "C:/p/Game/UI/C.cs"], "none")])
    assert v.rule == "EDITED_PART_NEEDS_GOAL_NODE" and v.owed and "1 個" in v.why
    assert v.evidence[0].startswith("UI：C:/p/Game/UI/B.cs、C:/p/Game/UI/C.cs 沒掛目標")
    assert not any(e.startswith("戰鬥") for e in v.evidence)
    dropped = rr.edited_part_goal_verdict([("UI", ["b.cs"], "dropped:T1.2")])
    assert dropped.owed and "T1.2 已放棄" in dropped.evidence[0]
    gone = rr.edited_part_goal_verdict([("UI", ["b.cs"], "gone:T7")])
    assert gone.owed and "T7 不在目前的樹" in gone.evidence[0]
    assert not rr.edited_part_goal_verdict([("戰鬥", ["a.cs"], "linked")]).owed
    assert not rr.edited_part_goal_verdict([]).owed
    line = rr.format_hit("f3", v)
    assert rr.parse_hits(line) == ["f3"]                                     # 擋次預算單獨計次


# ─── C-G1：LOCATE_LINES_NEED_CRITIQUE（定位第五行「批判」只查有沒有寫、有沒有內容） ───

@pytest.mark.parametrize("line, owed, want", [
    ("不合理，因為字典兩邊都寫，更好的做法是只留邏輯層一個寫入點；同類還可能在哪：存檔流程也兩邊寫", False, ""),
    ("合理，因為這段只轉送事件；同類還可能在哪：無，因為只有這一個入口", False, ""),
    ("不合理，原因是用檔名猜關聯，改成直接認宣告範圍；同類別處：(b) 的 covered()", False, ""),
    # 改造包 Q（007 實測）：真批判沒有「不合理／更好的做法／同類」字樣也算交——寫得對不對是 AI 的判斷，閘只查有沒有內容
    ("README 規定月份歸屬以台北時間為準，periods.month_of 卻轉 UTC，10/01 凌晨兩筆落到 9 月", False, ""),
    ("合理，因為只轉送事件；同類還可能在哪：無。", False, ""),                                          # 同類寫「無」沒理由也不擋
    ("不合理，因為字典兩邊都寫；同類還可能在哪：存檔流程", False, ""),                                 # 不合理沒替代做法也不擋
    ("合理，這段只做一件事", False, ""),                                                                # 剛好 8 字
    ("", True, "沒交"),
    ("合理", True, "太短"),                                                                              # 兩個字不是批判
    ("還好；同類：無", True, "太短"),
])
def test_cg1_locate_lines_need_critique(line, owed, want):
    """LOCATE_LINES_NEED_CRITIQUE：第五行只查有沒有寫、去掉標點後有沒有 ≥ CRITIQUE_MIN_CHARS（8）字；不認固定字樣。
    舊碼要「合理／不合理」＋理由＋更好的做法＋同類，007 的真批判被判沒交（紅）。"""
    v = rr.locate_critique_verdict(line)
    assert v.rule == "LOCATE_LINES_NEED_CRITIQUE" and v.owed is owed, v
    assert want in v.why, v
    if owed and line:
        assert any(e.startswith("定位｜批判：") for e in v.evidence)


@pytest.mark.parametrize("vals, owed", [
    ({"部位": "戰鬥——A.cs 結算段", "根因": "候選 A 邏輯層；候選 B 存檔；選 A 因為只有它寫", "目標": "T1.1（唯一寫入點）"}, False),
    ({"部位": "UI——List<int> 排序", "根因": "Dictionary<string, int> 沒鎖"}, False),           # 程式的泛型角括號不是佔位
    ({"部位": "戰鬥——<這次改哪個檔、哪一段>"}, True),
    ({"批判": "<這段寫法合不合理、為什麼；看得出更好的做法就寫；同類還可能在哪>"}, True),
])
def test_cg1_locate_lines_no_example_placeholder(vals, owed):
    """LOCATE_LINES_NO_EXAMPLE_PLACEHOLDER：擋訊息附的範例照抄（角括號裡的中文說明沒換掉）不算交；程式的泛型角括號不算佔位。"""
    v = rr.locate_placeholder_verdict(vals)
    assert v.rule == "LOCATE_LINES_NO_EXAMPLE_PLACEHOLDER" and v.owed is owed, v
    if owed:
        assert any("<" in e for e in v.evidence)


# ─── C-判斷入口盤點 階段 2：SCOPE_EDIT_RELATED_TO_ITEM（收據只被跟這一項有關的改動作廢） ───

@pytest.mark.parametrize("kw, owed", [
    (dict(is_code=True), True),                                   # 程式檔：每一項都要晚於它
    (dict(is_code=False), False),                                 # 文件、記憶：跟這一項無關 → 不作廢
    (dict(is_code=False, same_part=True), True),                  # 同部位的文件（測試讀的資料、部位自己的文件）
    (dict(is_code=False, under_item=True), True),                 # 文件就在這一項點名的路徑底下（含它宣告的 inputs）
    (dict(is_code=False, runs_part_ruler=True), True),            # 這一項就是那個部位的量尺指令
    (dict(is_code=False, whole_or_unknown=True), True),           # 整體驗證、或看不出指令跑了什麼 → 照算
])
def test_scope_edit_related_to_item(kw, owed):
    v = rr.scope_edit_related_verdict("doc.md", **kw)
    assert v.rule == "SCOPE_EDIT_RELATED_TO_ITEM" and v.owed is owed, v




# ═══ C-G16（track-c-g16）：提問附推薦、掛目標、全貌先於拍板 ═══

REL_TAG, REL_OPTS = "【收尾放行確認】", ("放行這一回合", "繼續擋，先修好")


def _ask(*qs):
    """qs：(題目, [選項 label…])。"""
    return {"questions": [{"question": q, "header": "h", "multiSelect": False,
                           "options": [{"label": l, "description": f"{l} 的說明"} for l in labels]} for q, labels in qs]}


@pytest.mark.parametrize("tool_input, owed", [
    (_ask(("要用哪個做法？", ["A", "B"])), True),
    (_ask(("要用哪個做法？", ["A (Recommended)", "B"])), False),
    (_ask(("要用哪個做法？", ["A（recommended）", "B"])), False),
    (_ask(("要用哪個做法？建議：選 A，因為改動面最小。", ["A", "B"])), False),
    (_ask(("第一題？", ["A (Recommended)", "B"]), ("第二題？", ["C", "D"])), True),     # 每一題都要
    (_ask((f"{REL_TAG} 要放行這一回合嗎？", list(REL_OPTS))), False),                  # 放行題不是決策題
    (_ask((f"{REL_TAG} 要放行嗎？", ["放行這一回合", "其他"])), True),                  # 選項不是固定兩個就不算放行題
    ({"questions": "壞掉"}, False),                                                        # 判不了不擋（工具自己會驗）
], ids=["none", "label", "fullwidth-lower", "text-suggest", "second-missing", "release", "release-tampered", "malformed"])
def test_c_g16_ask_needs_recommendation(tool_input, owed):
    """ASK_NEEDS_RECOMMENDATION：每一題至少一個選項標 (Recommended) 或題目含「建議：」；放行確認題豁免。"""
    v = rr.ask_recommendation_verdict(tool_input, REL_TAG, REL_OPTS)
    assert v.rule == "ASK_NEEDS_RECOMMENDATION" and v.owed is owed


def test_c_g16_ask_recommendation_message_names_missing_question_and_example():
    """擋訊息印規則名、哪一題缺什麼、照抄可過的範例（label 加 (Recommended) 或題目加「建議：」）。"""
    ti = _ask(("第一題？", ["A (Recommended)", "B"]), ("要用哪個寫法？", ["甲", "乙"]))
    v = rr.ask_recommendation_verdict(ti, REL_TAG, REL_OPTS)
    hit = rr.format_hit("提問", v)
    assert "ASK_NEEDS_RECOMMENDATION" in hit and "第 2 題" in hit and "要用哪個寫法" in hit and "第 1 題" not in hit
    fix = rr.ask_recommendation_fix(ti, REL_TAG, REL_OPTS)
    assert '"label": "甲 (Recommended)"' in fix and "建議：選 甲" in fix


def test_c_g16_ask_linked_to_goal_by_id_or_fragment():
    """ASK_LINKED_TO_GOAL：節點原文連續 8 字以上算指到（編號由 wg_need_goal.node_ref 判）；短於 8 字的節點只能寫編號。"""
    nodes = {"T1": "人只做真正的決定", "T1.1": "提問的每一題都附推薦選項或建議句", "T1.2": "短節點"}
    assert rr.node_fragment_ref(nodes, "這題是為了「每一題都附推薦選項」那件事") == "T1.1"
    assert rr.node_fragment_ref(nodes, "人只做真正的決定") == "T1"               # 剛好 8 字
    assert rr.node_fragment_ref(nodes, "每一題都附推薦") is None                     # 7 字不夠
    assert rr.node_fragment_ref(nodes, "短節點相關") is None                         # 節點本身不到 8 字
    assert rr.node_fragment_ref(nodes, "人只做 真正的決定") == "T1"                 # 空白不算字
    assert not rr.ask_goal_link_verdict("code", [("第 1 題", "T1.1")]).owed
    assert rr.ask_goal_link_verdict("code", [("第 1 題", None)]).owed
    assert not rr.ask_goal_link_verdict("knowledge", [("第 1 題", None)]).owed
    assert not rr.ask_goal_link_verdict(None, [("第 1 題", None)]).owed             # 沒樹不擋
    v = rr.ask_goal_link_verdict("code", [("第 1 題", "T1"), ("第 2 題「保留多久？」", None)])
    assert v.owed and "第 2 題「保留多久？」" in rr.format_hit("提問", v) and "第 1 題" not in rr.format_hit("提問", v)
    assert rr.ask_audit_note(None, None) == "提問未掛目標（知識類）"
    assert rr.ask_audit_note("knowledge", None) == "提問未掛目標（知識類）"
    assert rr.ask_audit_note("code", None) == "提問未掛目標（寫碼類）"
    assert rr.ask_audit_note("code", "T1") is None


def test_knowledge_light_tree_and_reconcile_rules():
    """KNOWLEDGE_EDIT_NEEDS_LIGHT_TREE／KNOWLEDGE_TREE_RECONCILE_AT_DELIVERY：各一個會紅的案例＋反例。"""
    v = rr.knowledge_light_tree_verdict(["C:/p/notes.md", "C:/p/plan.md"])
    assert v.owed and v.rule == "KNOWLEDGE_EDIT_NEEDS_LIGHT_TREE" and "2 個" in v.why and "C:/p/notes.md" in v.evidence
    assert not rr.knowledge_light_tree_verdict([]).owed
    v = rr.knowledge_reconcile_verdict("knowledge", ["C:/p/notes.md"])
    assert v.owed and v.rule == "KNOWLEDGE_TREE_RECONCILE_AT_DELIVERY" and rr.parse_hits(rr.format_hit("f4", v)) == ["f4"]
    assert not rr.knowledge_reconcile_verdict("knowledge", []).owed                     # 純問答樹
    assert not rr.knowledge_reconcile_verdict("code", ["C:/p/a.py"]).owed               # 寫碼類歸 (f2)
    assert not rr.knowledge_reconcile_verdict(None, ["C:/p/notes.md"]).owed
    assert {"KNOWLEDGE_EDIT_NEEDS_LIGHT_TREE", "KNOWLEDGE_TREE_RECONCILE_AT_DELIVERY"} <= set(rr.RULES)


def test_c_g16_ask_linked_to_goal_units_per_question_without_header():
    """codex BLOCK 1／WARN：每一題各自一個單位（題目＋選項 label 與描述，不含 header）；待放行時放行題不算單位。"""
    ti = {"questions": [{"question": "要哪種格式？", "header": "T1", "options": [{"label": "CSV", "description": "掛 T1.1"}]},
                        {"question": "保留多久？", "header": "h", "options": [{"label": "7 天", "description": "x"}]}]}
    units = rr.ask_link_units(ti, False, REL_TAG, REL_OPTS)
    assert [u[0] for u in units] == ["第 1 題「要哪種格式？」", "第 2 題「保留多久？」"]
    assert "T1.1" in units[0][1] and "T1" not in units[1][1]                     # header 的 T1 不算
    rel = _ask((f"{REL_TAG} 要放行這一回合嗎？", list(REL_OPTS)), ("要哪種格式？", ["CSV"]))
    assert [u[0] for u in rr.ask_link_units(rel, True, REL_TAG, REL_OPTS)] == ["第 2 題「要哪種格式？」"]
    assert len(rr.ask_link_units(rel, False, REL_TAG, REL_OPTS)) == 2
    assert rr.ask_link_units({"questions": "壞掉"}, False, REL_TAG, REL_OPTS) == []


def test_c_g16_ask_release_only_is_structural():
    """codex BLOCK 2：整次提問全是放行題（題目含標記、選項正好固定兩個）才算；夾一般題、標記塞進一般題都不算。"""
    rel = (f"{REL_TAG} 要放行這一回合嗎？", list(REL_OPTS))
    assert rr.ask_release_only(_ask(rel), REL_TAG, REL_OPTS)
    assert not rr.ask_release_only(_ask(rel, ("要哪種格式？", ["CSV", "JSON"])), REL_TAG, REL_OPTS)
    assert not rr.ask_release_only(_ask((f"{REL_TAG} 要哪種格式？", ["CSV", "JSON"])), REL_TAG, REL_OPTS)
    assert not rr.ask_release_only({"questions": []}, REL_TAG, REL_OPTS)
    hit = rr.format_hit("提問", rr.ask_recommendation_verdict(_ask((f"{REL_TAG} 要放行嗎？", ["放行這一回合 (Recommended)", "繼續擋，先修好"])),
                                                            REL_TAG, REL_OPTS))
    assert "選項不是固定兩個" in hit                                               # 放行題寫走樣：指路照抄兩個選項


@pytest.mark.parametrize("tool, tool_input, reads, owed", [
    ("AskUserQuestion", _ask(("要用哪個改法？", ["A (Recommended)"])), 0, True),
    ("AskUserQuestion", _ask(("要用哪個改法？", ["A (Recommended)"])), 2, False),
    ("AskUserQuestion", _ask(("今天要先做哪一軌？", ["A (Recommended)"])), 0, False),     # 不是改法選擇
    ("ExitPlanMode", {"plan": "計畫"}, 0, True),                                          # 計畫本身就是改法
    ("ExitPlanMode", {"plan": "計畫"}, 1, False),
], ids=["decision-unread", "decision-read", "not-decision", "plan-unread", "plan-read"])
def test_c_g16_ask_overview_before_decision(tool, tool_input, reads, owed):
    """ASK_OVERVIEW_BEFORE_DECISION：涉及改法選擇、而 OverviewHub 的 part_files_read 全空 → 要附「先讀過部位檔再問」（只提醒）。"""
    v = rr.ask_overview_verdict(tool, tool_input, reads)
    assert v.rule == "ASK_OVERVIEW_BEFORE_DECISION" and v.owed is owed
    if owed:
        assert "先讀過部位檔再問" in rr.format_hit("提問", v)


# ─── B5 真測：表外檔綜觀、快取目錄、Bash 唯讀讀檔 ─────────────────────────────

@pytest.mark.parametrize("path, root, owed", [
    ("C:/p/tests/__pycache__", "C:/p", False),                       # rm -rf tests/__pycache__（沒 .gitignore 的專案）
    ("C:/p/tests/__pycache__/t.cpython-314.pyc", "C:/p", False),
    ("C:/p/.pytest_cache/v/cache/lastfailed", "C:/p", False),
    ("C:/p/src/.mypy_cache", None, False),                            # 沒給根：比整條路徑
    ("C:/__pycache__/proj/src/a.py", "C:/__pycache__/proj", True),    # 根以外的上層目錄名不算
    ("C:/p/src/pycache_notes.md", "C:/p", True),
])
def test_b5_runtime_data_no_overview_cache_dirs(path, root, owed):
    """RUNTIME_DATA_NO_OVERVIEW：路徑含快取目錄 → 免綜觀（gitignored=False 也算，B5 對照組 rm tests/__pycache__ 被擋的那種）。"""
    v = rr.runtime_data_verdict(path, root, False)
    assert v.rule == "RUNTIME_DATA_NO_OVERVIEW" and v.owed is owed


@pytest.mark.parametrize("need, readable, have, owed, text", [
    (1, 0, 0, False, "沒有可讀的既有檔"),          # B5：專案根只有子目錄，新建 .gitignore
    (1, 1, 0, True, "至少 1 個檔（目前 0 個）"),   # 根目錄有 README 沒讀 → 照擋，不放寬
    (1, 1, 1, False, "夠 1 個"),
    (3, 2, 1, True, "至少 2 個檔（目前 1 個）"),   # 可讀檔比設定少：要讀數降成可讀檔數
    (3, 2, 2, False, "夠 2 個"),
])
def test_b5_unmapped_edit_needs_readable_files(need, readable, have, owed, text):
    """UNMAPPED_EDIT_NEEDS_READABLE_FILES：要讀數＝min(設定, 該目錄可讀既有檔數)；擋訊息帶「該目錄既有可讀檔」。"""
    v = rr.unmapped_edit_verdict(need, readable, have)
    assert v.rule == "UNMAPPED_EDIT_NEEDS_READABLE_FILES" and v.owed is owed and text in v.why
    assert any("該目錄既有可讀檔" in e for e in v.evidence)


def test_b5_bash_readonly_counts_as_read(tmp_path):
    """BASH_READONLY_COUNTS_AS_READ：exit 0／未知、字面路徑、實檔才算；變數、glob、失敗、檔不存在不算。"""
    real = tmp_path / "a.md"
    real.write_text("x", encoding="utf-8")
    p = str(real)
    assert rr.bash_read_counts([p], 0) == [p] and rr.bash_read_counts([p], None) == [p]
    assert rr.bash_read_counts([p], 1) == []                                       # 指令失敗
    assert rr.bash_read_counts([str(tmp_path / "nope.md")], 0) == []                # 檔不存在
    for name in ("x$f.md", "a[1].md"):                                             # 檔真的在也不算：含變數、沒展開的 glob
        (tmp_path / name).write_text("x", encoding="utf-8")
        assert rr.bash_read_counts([str(tmp_path / name)], 0) == []


@pytest.mark.parametrize("green, keeps", [
    ("python -m pytest -q tests/test_a.py && python -m agenda.runner view --late", False),   # 別段跑模組的 -m 不算篩選
    ("cd /c/b5/q5-agenda && python -m pytest -q -p no:cacheprovider 2>&1 | tail -2\n"
     "python -m agenda.runner view | iconv -f cp950 -t utf-8", False),                       # B5 q5 受測 B 的寫法（換行串接）
    ("python -m agenda.runner view; pytest -q tests/test_a.py -k smoke", True),              # 篩選在 pytest 那段照算
    ("pytest -m slow tests/test_a.py", True),                                                # pytest -m slow 仍是篩選
    ("python -m pytest -q tests/test_a.py", False),                                          # 沒篩選
    ("python tools/run.py a.py::x; pytest -q tests/test_a.py", False),                       # 別段的 :: 不是節點 id
], ids=["and-run-module", "b5-q5-newline", "filter-in-pytest-seg", "pytest-m-slow", "no-filter", "other-seg-node"])
def test_b5_green_narrowed_keeps_uncovered_red_only_pytest_segment(green, keeps):
    """GREEN_NARROWED_KEEPS_UNCOVERED_RED：篩選旗標與節點 id 只看測試子命令那段、子命令之後（B5 q5 同一指令裡
    `python -m agenda.runner` 的 -m 被當 pytest 篩選，綠清不掉紅，AEC 多擋兩次）。"""
    assert rr.green_covers_red_verdict(*_GREEN_RED, green).owed is keeps


# ═══ C-G16 002（裁定 #39）：全貌提醒按題目提到的路徑對部位 ═══

_DECIDE = _ask(("要用哪個改法？", ["A (Recommended)"]))


@pytest.mark.parametrize("named, reads, owed", [
    ([("Game/Net/conn.py", "網路", 0)], 3, True),        # 讀了別的部位 3 檔，題目問的部位 0 檔 → 提醒
    ([("Game/Net/conn.py", "網路", 2)], 2, False),       # 題目問的部位讀過 → 不提醒
    ([("Game/Net/a.py", "網路", 2), ("Game/Battle/b.py", "戰鬥", 0)], 2, True),   # 提到兩個部位，一個沒讀
    ([], 2, False),                                       # 沒提到部位表上的路徑 → 退回「讀過任一部位檔」
    ([], 0, True),
], ids=["named-unread", "named-read", "one-of-two-unread", "fallback-read", "fallback-none"])
def test_c_g16_ask_overview_before_decision_by_named_part(named, reads, owed):
    """ASK_OVERVIEW_BEFORE_DECISION：題目提到的路徑對到部位，該部位讀過 0 檔才提醒；沒對到部位退回總數判定。"""
    v = rr.ask_overview_verdict("AskUserQuestion", _DECIDE, reads, named)
    assert v.owed is owed
    hit = rr.format_hit("提問", v)
    if owed and named:
        unread = [n for n in named if n[2] == 0][0]
        assert f"題目提到 {unread[0]}→部位 {unread[1]}，本回合該部位讀過 0 檔" in hit
        assert all(f"部位 {p}，" not in hit for _x, p, n in named if n)            # 讀過的部位不列
    if owed and not named:
        assert "題目沒提到部位表上的路徑" in hit


def test_c_g16_ask_paths_from_question_and_options_only():
    """路徑只從題目與選項 label／描述取（不看 header）；絕對與相對（含斜線）都取，網址、中文句子裡的斜線字不取。"""
    ti = {"questions": [{"question": r"要改 C:\proj\Game\Net\conn.py 還是 Game/Battle/hit.py？", "header": "Tools/x.py",
                         "options": [{"label": "A (Recommended)", "description": "改 hooks/wg_a.py，見 https://example.com/a/b"},
                                     {"label": "是/否", "description": "x"}]}]}
    assert rr.ask_paths(ti) == [r"C:\proj\Game\Net\conn.py", "Game/Battle/hit.py", "hooks/wg_a.py"]
    assert rr.ask_paths({"questions": "壞掉"}) == []
    noise = _ask(("2026/10/14 定的 1.2/3.4 版，T1.1/T1.2、A/B 要哪個？見 https://x.com/?next=Game/Net/c.py", ["甲 (Recommended)"]))
    assert rr.ask_paths(noise) == []                    # 日期、版本號、節點編號、單字元選項字、網址（含查詢參數）都不算路徑


@pytest.mark.parametrize("question, want", [
    ("要改Game/網路/conn.py嗎？", ["Game/網路/conn.py"]),                         # 中間段中文、前後接中文句子
    ("改 _AIDocs/DevHistory/v6.0-寫程式碼的進化/need-goal-契約.md 哪裡？", ["_AIDocs/DevHistory/v6.0-寫程式碼的進化/need-goal-契約.md"]),
    (r"改 C:\Users\me\.claude\memory\工作流\x.md 嗎", [r"C:\Users\me\.claude\memory\工作流\x.md"]),
    (r"要改 `C:\My Project\Game\Net\conn.py` 嗎", [r"C:\My Project\Game\Net\conn.py"]),   # 引號包住：含空白照原樣
    ("要改「Game/網路 設定/a.py」嗎", ["Game/網路 設定/a.py"]),
    ("TECH.md 要用哪個改法？", ["TECH.md"]),                                      # 不含斜線的根目錄檔名
    ("rr.format_hit 跟 v6.0 跟 e.g. 不是檔", []),                               # 模組.函式、版本號不算
], ids=["cjk-mid", "cjk-last-ext", "abs-cjk", "quoted-space", "quoted-cjk-space", "bare-file", "not-files"])
def test_c_g16_ask_paths_cjk_quoted_and_bare(question, want):
    """codex 002 BLOCK 1／2：中文路徑段、引號包住含空白的路徑、根目錄檔名都要取得到；一般字不誤取。"""
    assert rr.ask_paths(_ask((question, ["A (Recommended)"]))) == want


# ─── 驗證範圍：要不要驗是規則，驗哪些由 LLM 判斷（端到端案例在 verify_verify_scope.py） ───

def test_scope_declared_for_change_needs_declaration_and_every_repo():
    """SCOPE_DECLARED_FOR_CHANGE：改了程式沒宣告 → 欠（訊息叫 LLM 判斷並指路 verify_scope）；宣告了但某個 repo 沒項目 → 欠；
    都有 → 不欠；沒改 → 不欠。"""
    v = rr.scope_declared_verdict([r"c:\p\hooks\x.py"], False)
    assert v.rule == "SCOPE_DECLARED_FOR_CHANGE" and v.owed and "x.py" in v.why and "verify_scope" in v.evidence[0]
    v = rr.scope_declared_verdict([r"c:\p\a.py", r"c:\q\b.py"], True, [("c:/q", [r"c:\q\b.py"])])
    assert v.owed and "c:/q" in v.why and "b.py" in v.evidence[0]
    assert not rr.scope_declared_verdict([r"c:\p\a.py"], True).owed
    assert not rr.scope_declared_verdict([], False).owed


def test_scope_item_well_formed_target_why_and_facts():
    """SCOPE_ITEM_WELL_FORMED：目標或理由空 → 退；呼叫端查到檔不存在、節點查不到 → 退；都好 → 收。"""
    assert rr.scope_item_form_verdict("", "w").owed
    assert rr.scope_item_form_verdict("a.py", "  ").owed and "理由" in rr.scope_item_form_verdict("a.py", "").why
    v = rr.scope_item_form_verdict("a.py", "w", "不存在（c:/p/a.py）")
    assert v.owed and v.rule == "SCOPE_ITEM_WELL_FORMED" and "不存在" in v.why
    assert not rr.scope_item_form_verdict("a.py", "直接測 a").owed


def test_scope_item_receipt_after_edit_carries_reason():
    """SCOPE_ITEM_RECEIPT_AFTER_EDIT：沒合格收據 → 欠，證據是查到的理由（沒給就說沒有收據）；有 → 不欠。"""
    v = rr.scope_item_verdict("ab-S2", "hooks/verify/verify_x.py", False, "最近一次跑紅")
    assert v.owed and "ab-S2" in v.why and v.evidence == ("最近一次跑紅",)
    assert rr.scope_item_verdict("ab-S2", "t", False).evidence == ("沒有跑這一項的收據",)
    assert not rr.scope_item_verdict("ab-S2", "t", True).owed


def test_scope_leak_outside_scope_only_when_closed_between_green_and_red():
    """SCOPE_LEAK_OUTSIDE_SCOPE：範圍外、T 綠過、宣告在上次綠之後這次紅之前結案 → 記；任一不成立 → 不記。
    看到紅的 session 自己還有沒結案的改動 → 照記，證據多一行叫檢討時先查明（不憑 session 狀態丟掉）。"""
    base = dict(test="h/v/verify_y.py::test_q", scope_id="S1", in_scope=False, observer_open=False,
                last_green="2026-10-14T01:00:00Z", closed_between=True)
    assert rr.scope_leak_verdict(**base).owed
    for k, v in (("in_scope", True), ("last_green", None), ("closed_between", False)):
        assert not rr.scope_leak_verdict(**{**base, k: v}).owed, k
    busy = rr.scope_leak_verdict(**{**base, "observer_open": True})
    assert busy.owed and any("先查明" in e for e in busy.evidence)


def test_scope_covers_and_failed_in_path_logic():
    """範圍涵蓋：整個 repo、資料夾、同一支檔、節點（含參數化）；節點項目不涵蓋同檔的別的節點。紅名單：同節點或其中一邊只寫到檔。"""
    assert rr.scope_covers(["*"], "a/b.py::t")
    assert rr.scope_covers(["hooks/verify"], r"hooks\verify\verify_y.py::test_q")
    assert rr.scope_covers(["hooks/verify/verify_y.py"], "hooks/verify/verify_y.py::test_q")
    assert rr.scope_covers(["hooks/verify/verify_y.py::test_q"], "hooks/verify/verify_y.py::test_q[1]")
    assert not rr.scope_covers(["hooks/verify/verify_y.py::test_q"], "hooks/verify/verify_y.py::test_r")
    assert not rr.scope_covers(["hooks/verify/verify_x.py"], "hooks/verify/verify_y.py")
    assert not rr.scope_covers(["hooks/ver"], "hooks/verify/verify_y.py")                 # 前綴要到資料夾邊界
    assert rr.scope_failed_in(["a.py::t"], "a.py") and rr.scope_failed_in(["a.py"], "a.py::t")
    assert not rr.scope_failed_in(["a.py::t"], "a.py::u") and not rr.scope_failed_in(["b.py"], "a.py")


def test_scope_leak_review_before_declare_needs_root_cause_or_reason():
    """SCOPE_LEAK_REVIEW_BEFORE_DECLARE：每筆待檢討都要交；missed 要根因與下次怎麼改，unrelated 要理由；verdict 只收兩種。"""
    v = rr.scope_review_verdict(["L1", "L2"], [{"leak": "L1", "verdict": "unrelated", "reason": "環境壞了"}])
    assert v.owed and "L2 還沒檢討" in v.evidence
    v = rr.scope_review_verdict(["L1"], [{"leak": "L1", "verdict": "missed", "next_time": "看呼叫方"}])
    assert v.owed and "根因" in v.evidence[0]
    v = rr.scope_review_verdict(["L1"], [{"leak": "L1", "verdict": "missed", "root_cause": "只看了自己的測試"}])
    assert v.owed and "next_time" in v.evidence[0]
    assert rr.scope_review_verdict(["L1"], [{"leak": "L1", "verdict": "maybe"}]).owed
    ok = [{"leak": "L1", "verdict": "missed", "root_cause": "沒查誰讀這個常數", "next_time": "改常數先搜讀它的地方"}]
    assert not rr.scope_review_verdict(["L1"], ok).owed and not rr.scope_review_verdict([], []).owed


# ─── RELOAD_ADVICE_ALREADY_LOADED ──────────────────────────────────────

_RELOAD_NOW = 1_800_000_000.0


@pytest.mark.parametrize("text, records, disk, owed", [
    ("改完記得 Reload Window。", [(100.0, _RELOAD_NOW - 30)], 100.0, True),                # 活著的服務都已載入最新 → 多餘
    ("請重新載入視窗讓新工具生效", [(120.0, _RELOAD_NOW - 30)], 100.0, True),
    ("改完記得 Reload Window。", [(100.0, _RELOAD_NOW - 30), (90.0, _RELOAD_NOW - 30)], 100.0, False),  # 有一個舊的 → 照說
    ("改完記得 Reload Window。", [(100.0, _RELOAD_NOW - 900)], 100.0, False),             # 心跳過期（程序已關）不算 → 判不出
    ("改完記得 Reload Window。", [], 100.0, False),                                       # 沒紀錄（舊版服務沒寫）→ 判不出，放行
    ("改完記得 Reload Window。", [(100.0, _RELOAD_NOW - 30)], None, False),              # 磁碟版本讀不到 → 判不出
    ("改完記得 Reload Window。", [(100.0, _RELOAD_NOW - 30), (None, _RELOAD_NOW)], 100.0, False),  # 有在跑的服務沒紀錄（舊版）→ 判不出
    ("改完記得 Reload Window。", [(90.0, _RELOAD_NOW - 900), (100.0, _RELOAD_NOW - 30)], 100.0, False),  # codex BLOCK：在跑的舊服務
                                                                                          # 心跳過期（睡眠後）→ 判不出，不能被排除
    ("改了 MCP 啟動設定，請 Reload Window。重載原因：啟動參數改了", [(100.0, _RELOAD_NOW - 30)], 100.0, False),  # AI 寫明重載原因
    ("全部完成了。", [(100.0, _RELOAD_NOW - 30)], 100.0, False),                           # 沒叫人重載
])
def test_reload_advice_already_loaded(text, records, disk, owed):
    """使用者提案：AI 叫使用者 Reload Window 之前先查是不是真的需要。判斷依據是每個正在跑的工具服務啟動時載入的程式版本
    與磁碟上的版本（查得到的事實），不是 session 名稱（開新分頁會換名但服務不重啟）。全部有紀錄、心跳新、已最新才算多餘；
    判不出一律放行；AI 寫明「重載原因：…」（程式更新以外的理由）照它的判斷。"""
    v = rr.reload_advice_verdict(text, records, disk, _RELOAD_NOW)
    assert v.rule == "RELOAD_ADVICE_ALREADY_LOADED" and v.owed is owed, (text, records, disk)


# ─── (d) 補案例：由哪個案例驗交 LLM 宣告（判斷入口盤點 P4） ─────────────────────

def test_case_declared_for_change_needs_a_holding_case():
    """CASE_DECLARED_FOR_CHANGE：沒宣告 → 欠並指路 case_for／no_case；宣告的案例都不成立 → 欠並列每個案例的問題；
    有一個成立 → 不欠（不看其他不成立的那幾個）。宣告了不成立的案例時不退去看 no_case。"""
    v = rr.case_for_change_verdict("x.py", [])
    assert v.rule == "CASE_DECLARED_FOR_CHANGE" and v.owed and "還沒宣告" in v.why and "case_for" in v.evidence[0]
    v = rr.case_for_change_verdict("x.py", [("verify_x.py", "最近一次跑紅")], "只改字串")
    assert v.rule == "CASE_DECLARED_FOR_CHANGE" and v.owed and v.evidence == ("verify_x.py：最近一次跑紅",)
    v = rr.case_for_change_verdict("x.py", [("verify_a.py", "本 session 沒有新寫或改過這支案例"), ("verify_x.py::t", "")])
    assert not v.owed and "verify_x.py::t" in v.why


def test_no_case_needs_user_carries_reason_into_question():
    """NO_CASE_NEEDS_USER：宣告不需要新案例照擋，擋訊息把理由與【收尾放行確認】的問法帶出來；理由空白不算宣告。"""
    v = rr.case_for_change_verdict("x.py", [], "  只改了擋訊息\n的字串  ")
    assert v.rule == "NO_CASE_NEEDS_USER" and v.owed and "只改了擋訊息 的字串" in v.why
    assert "【收尾放行確認】" in v.evidence[0] and "x.py 不需要新案例" in v.evidence[0]
    assert rr.case_for_change_verdict("x.py", [], "   ").rule == "CASE_DECLARED_FOR_CHANGE"
    v = rr.case_for_change_verdict("x.py", [], "只改字串", user_approved=True)          # 使用者放行過、之後沒再改 → 不欠
    assert v.rule == "NO_CASE_NEEDS_USER" and not v.owed and "使用者已放行" in v.why
    assert rr.case_for_change_verdict("x.py", [], "", user_approved=True).owed            # 沒有 no_case 理由，記錄不算數


def test_case_decl_well_formed_lists_every_problem():
    """CASE_DECL_WELL_FORMED：有問題就整份退回並逐條列；沒問題收下。"""
    v = rr.case_decl_form_verdict(["「a」不是測試檔", "no_case 的 b.py 不存在"])
    assert v.owed and v.evidence == ("「a」不是測試檔", "no_case 的 b.py 不存在")
    assert not rr.case_decl_form_verdict([]).owed


# ─── 收尾少空轉：測試案例檔只作廢自己那一項、已同步的檔不再提醒、擋一次就列出後面還欠的閘 ───

@pytest.mark.parametrize("kw, owed", [
    (dict(is_code=True, standalone_case=True), False),                          # 獨立案例檔、這一項沒點名它 → 不作廢
    (dict(is_code=True, standalone_case=True, same_part=True), False),          # 同部位也不算：同資料夾別支測試不受影響
    (dict(is_code=True, standalone_case=True, under_item=True), True),          # 這一項點名的就是它
    (dict(is_code=True, standalone_case=True, runs_part_ruler=True), True),     # 部位量尺會跑到它
    (dict(is_code=True, standalone_case=True, whole_or_unknown=True), True),    # 整體驗證、或看不出跑了什麼
])
def test_044_scope_case_edit_only_its_item(kw, owed):
    v = rr.scope_edit_related_verdict("verify_a.py", **kw)
    assert v.rule == "SCOPE_CASE_EDIT_ONLY_ITS_ITEM" and v.owed is owed, v


def test_044_shared_case_is_still_code():
    """被同資料夾 import 的案例檔、conftest（standalone_case=False）照程式檔算：每一項都要晚於它。"""
    v = rr.scope_edit_related_verdict("probe_release_rules.py", True, standalone_case=False)
    assert v.rule == "SCOPE_EDIT_RELATED_TO_ITEM" and v.owed


def test_044_stop_flow_rules_point_to_stop_handler():
    """SYNC_BLOCK_SKIPS_SYNCED、BLOCK_LISTS_LATER_GATES：判法在 handlers/stop.py（端到端案例見 verify_stop_reconcile 的 046 段）。"""
    for name in ("SYNC_BLOCK_SKIPS_SYNCED", "SYNC_SKIPS_VANISHED_OUTSIDE_VCS", "BLOCK_LISTS_LATER_GATES"):
        assert "handlers/stop.py" in rr.RULES[name], name


def test_044_later_turn_sync_rules_point_to_handlers():
    """PROMPT_REOPENS_DONE 判法在 handlers/user_prompt_submit.py、SYNC_BLOCK_NEW_ITEMS_ONLY 在 handlers/stop.py
    （兩回合端到端案例見 verify_sync_reminder_later_turn.py）。"""
    assert "handlers/user_prompt_submit.py" in rr.RULES["PROMPT_REOPENS_DONE"]
    assert "handlers/stop.py" in rr.RULES["SYNC_BLOCK_NEW_ITEMS_ONLY"]


# ─── LEFTOVER_NEEDS_CLEANUP（收尾自清；事實由 aec_ledger.list_alive 現場查，真 git 的案例在 verify_session_artifacts） ───

def _art(kind, title, **kw):
    base = {"kind": kind, "title": title, "path": "C:/x/" + title, "label": "", "can_delete": True,
            "source": "bash", "note": "", "decision": None, "busy": ""}
    return {**base, **kw}


def test_leftover_needs_cleanup():
    """使用者原話：「要提醒 LLM，他才會去把已經用完的工作用分支從 git 上刪掉」。宣告完成時，本 session 建的工作樹、
    已合併分支（被候選工作樹用著的也算，刪完工作樹就刪得掉）、臨時 repo、專案外檔案資料夾還在又沒說要留 → 擋。
    不列：沒合併的分支、主工作樹用著的分支、暫存區、專案裡還沒進版控的新檔、gitignore 的檔、遠端分支、
    別的開著的 session 正在用的、使用者按過保留的、AI 在 (i) 寫過理由的、開場快照比對出來（來源不明）的。"""
    items = [
        _art("worktree", "wt", path="C:/x/wt"),
        _art("branch", "feat", merged=True, can_delete=False, used_by="C:/x/wt"),
        _art("branch", "idle", merged=True),
        _art("branch", "topic", merged=False, confirm="沒合併"),
        _art("branch", "onmain", merged=True, can_delete=False, used_by="C:/x/main"),
        _art("repo", "scratch"),
        _art("repo", "cwdrepo", can_delete=False),
        _art("dir", "probe", where="outside"),
        _art("file", "s.txt", where="temp"),
        _art("file", "new.py", where="untracked"),
        _art("file", "ign.log", where="ignored"),
        _art("remote_branch", "origin/feat"),
        _art("worktree", "busywt", busy="另一個開著的 session 正在用"),
        _art("worktree", "kept", decision="keep"),
        _art("dir", "noted", where="outside", note="使用者要的產出", source="aec-i"),
        _art("file", "olddecl.txt", where="outside", note="舊格式 (d) 宣告過", source="aec-d"),
        _art("branch", "snap", merged=True, source="snapshot"),
    ]
    v = rr.leftover_cleanup_verdict(True, items)
    assert v.rule == "LEFTOVER_NEEDS_CLEANUP" and v.owed and "5 樣" in v.why
    assert [c["title"] for c in rr.leftover_candidates(items)] == ["wt", "feat", "idle", "scratch", "probe"]
    assert len(v.evidence) == 5 and v.evidence[0].startswith("wt")
    assert not rr.leftover_cleanup_verdict(False, items).owed, "沒宣告完成不擋"
    rest = [it for it in items if it["title"] in ("topic", "onmain", "s.txt", "new.py", "busywt", "kept", "noted", "snap")]
    assert not rr.leftover_cleanup_verdict(True, rest).owed, "只剩不該列的 → 不擋"
    assert not rr.leftover_cleanup_verdict(True, []).owed


# ─── G6 階段 4（判斷入口盤點 P6／P7）：宣稱行、不做行、使用者引用 ─────────────────────────────

def test_p6_parse_claim_dispositions():
    text = ("修好了。\n宣稱｜修好：非本回合宣稱，因為那句在說明 CC 收尾會自己跑的行為\n"
            "宣稱｜試過：收據 verify_x.py\n宣稱｜量了：隨便寫")
    d = rr.parse_claim_dispositions(text)
    assert d["fixed"][0]["mode"] == "disclaim" and d["fixed"][0]["reason"].startswith("那句在說明")
    assert d["tried"][0]["mode"] == "receipt" and d["tried"][0]["ref"] == "verify_x.py"
    assert d["measured"][0]["mode"] == "unknown"
    assert rr.parse_claim_dispositions("沒有宣稱行") == {}


def test_p6_claim_disposition_verdict():
    found = {"verify_x.py": "python -m pytest verify_x.py（turn 5）"}
    assert not rr.reason_present("....")
    find = lambda ref: found.get(ref)  # noqa: E731
    v = rr.claim_disposition_verdict("fixed", {}, find)
    assert v.owed and v.rule == "CLAIM_WORDS_ARE_HINTS" and "宣稱｜修好" in v.evidence[0]
    ok = rr.parse_claim_dispositions("宣稱｜修好：非本回合宣稱，因為那句講的是 CC 的行為")
    assert not rr.claim_disposition_verdict("fixed", ok, find).owed
    bad = rr.parse_claim_dispositions("宣稱｜修好：非本回合宣稱，因為 <理由>")
    v = rr.claim_disposition_verdict("fixed", bad, find)
    assert v.owed and v.rule == "CLAIM_DISCLAIM_NEEDS_REASON"
    ref = rr.parse_claim_dispositions("宣稱｜修好：收據 verify_x.py")
    v = rr.claim_disposition_verdict("fixed", ref, find)
    assert not v.owed and v.rule == "CLAIM_RECEIPT_REF_MATCH" and "turn 5" in v.why
    miss = rr.parse_claim_dispositions("宣稱｜修好：收據 nothing.py")
    v = rr.claim_disposition_verdict("fixed", miss, find)
    assert v.owed and v.rule == "CLAIM_RECEIPT_REF_MATCH"
    v = rr.claim_disposition_verdict("tried", rr.parse_claim_dispositions("宣稱｜跑了：收據 verify_x.py"), find)
    assert not v.owed, "跑了／試過都對到 tried"


def test_p7_not_doing_verdict():
    decls = rr.parse_not_doing("不做｜A 清理：風險是 state 並行競寫會毀檔\n不做｜B 瘦身：使用者說「B 先這樣」\n不做｜C 整理：<理由>")
    assert [d["item"] for d in decls] == ["A 清理", "B 瘦身", "C 整理"] and decls[1]["quote"] == "B 先這樣"
    assert not rr.not_doing_verdict("A 清理留給未來處理", decls, []).owed
    v = rr.not_doing_verdict("B 瘦身先跳過", decls, ["B 先這樣吧"])
    assert not v.owed and v.rule == "NOT_DOING_DECLARED"
    v = rr.not_doing_verdict("B 瘦身先跳過", decls, ["做 B"])
    assert not v.owed, "引用不再比對使用者原話：寫了不做行就留帳放行"
    v = rr.not_doing_verdict("C 整理之後再處理", decls, [])
    assert v.owed and v.rule == "NOT_DOING_DECLARED" and "佔位" in v.why
    v = rr.not_doing_verdict("D 之後再處理", decls, [], "除非附「檢測時點 + 不修的實際風險」")
    assert v.owed and "改得快又有效" in v.evidence[1] and "追蹤｜<哪一件>" in v.evidence[1]   # 收尾那一問
    assert not rr.not_doing_verdict("不做｜A 清理：風險是 state 並行競寫會毀檔", decls, []).owed, "命中行本身就是不做行"
    dis = rr.parse_not_doing("不是退避｜既有的問題：因為那句在說明舊碼原本就有的行為，本輪已修")
    assert dis[0]["mode"] == "disclaim" and dis[0]["item"] == "既有的問題" and not dis[0]["quote"]
    v = rr.not_doing_verdict("這是既有的問題，本輪已修。", dis, [])
    assert not v.owed and "不是退避" in v.why
    assert rr.not_doing_verdict("這是既有的問題，本輪已修。", rr.parse_not_doing("不是退避｜既有的問題：..."), []).owed
    _, w = rr.waived_failures([{"cmd": "pytest verify_a.py", "summary": ""}],
                              rr.parse_not_doing("不是退避｜verify_a.py：使用者說「先這樣」"), ["先這樣"])
    assert not w, "不是退避行不能豁免紅測"
    kept, w = rr.waived_failures([{"cmd": "pytest verify_a.py", "summary": ""}],
                                 rr.parse_not_doing("不做｜verify_a.py：使用者說「先這樣」"), ["繼續"])
    assert "USER_WAIVER_NEEDS_CITATION" in rr.RULES and not kept and w   # 紅測豁免的原句不再比對使用者原話，寫了就放行留帳


def test_p7_waived_failures_only_cited_and_matching():
    failing = [{"cmd": "python -m pytest hooks/verify/verify_a.py", "summary": "1 failed", "turn_seq": 5},
               {"cmd": "python -m pytest hooks/verify/verify_b.py", "summary": "1 failed", "turn_seq": 5}]
    decls = rr.parse_not_doing("不做｜verify_a.py：使用者說「verify_a 先這樣」")
    kept, waived = rr.waived_failures(failing, decls, ["verify_a 先這樣，b 要修"])
    assert [f["cmd"] for f in kept] == [failing[1]["cmd"]] and waived[0][1]["item"] == "verify_a.py"
    kept, waived = rr.waived_failures(failing, decls, ["b 要修"])
    assert len(kept) == 1 and waived, "原句不再比對使用者原話：寫了「使用者說」就豁免那一支（留帳抽查）"
    kept, _ = rr.waived_failures(failing, rr.parse_not_doing("不做｜verify_a.py：太難了，風險高"), ["verify_a 先這樣"])
    assert len(kept) == 2, "AI 自己的理由不能豁免紅測，只有使用者引用能"
    # codex BLOCK：事項要指得到那一筆（完整 token），通用字或檔名的一截不行
    for item in ("py", "pytest", "verify", "old_verify_a.py", "verify_ab.py", "hooks"):
        kept, _ = rr.waived_failures(failing, rr.parse_not_doing(f"不做｜{item}：使用者說「先這樣」"), ["先這樣"])
        assert len(kept) == 2, item
    kept, _ = rr.waived_failures(failing, rr.parse_not_doing("不做｜hooks/verify/verify_a.py：使用者說「先這樣」"), ["先這樣"])
    assert len(kept) == 1, "完整路徑指得到"
    node = [{"cmd": "python -m pytest hooks/verify/verify_a.py::test_x", "summary": "1 failed"}]
    kept, _ = rr.waived_failures(node, rr.parse_not_doing("不做｜verify_a.py::test_x：使用者說「先這樣」"), ["先這樣"])
    assert not kept, "測試節點指得到"


def test_004_waiver_per_listed_test_ledger_same_test_and_later_mention():
    """codex 004：摘要逐支列出失敗時每支各自要有豁免（同一筆裡 A 被點名、B 沒有 → 整筆照紅；收集錯誤也算一支）；帳只認記帳那時的
    同一支（別檔同名函式不借帳）；使用者記帳後又提到這支 → 帳不算，以新的話為準（那則擠出近 3 則也一樣）。"""
    decl = rr.parse_not_doing("不做｜test_total：使用者說「test_total 先跳過」")
    two = [{"cmd": "pytest tests", "summary": "FAILED tests/a.py::test_total - x\nFAILED tests/a.py::test_other - y"}]
    kept, w = rr.waived_failures(two, decl, ["test_total 先跳過"])
    assert kept == two and not w, "test_other 沒人豁免"
    both = rr.parse_not_doing("不做｜test_total：使用者說「test_total 先跳過」\n不做｜test_other：使用者說「test_other 也先跳過」")
    kept, w = rr.waived_failures(two, both, ["test_total 先跳過，test_other 也先跳過"])
    assert not kept and sorted(u for _, h in w for u in h["units"]) == ["tests/a.py::test_other", "tests/a.py::test_total"]
    col = [{"cmd": "pytest tests", "summary": "FAILED tests/a.py::test_total - x\nERROR tests/c.py - ImportError"}]
    kept, _ = rr.waived_failures(col, decl, ["test_total 先跳過"])
    assert kept == col, "收集錯誤也是一支"
    a = [{"cmd": "pytest tests", "summary": "FAILED tests/a.py::test_total - x"}]
    _, w = rr.waived_failures(a, decl, ["test_total 先跳過"])
    assert w[0][1]["units"] == ["tests/a.py::test_total"]
    led = [{"item": "test_total", "quote": "test_total 先跳過", "said": "test_total 先跳過", "units": w[0][1]["units"],
            "cmd": "pytest tests"}]
    later = ["好", "再跑一次", "繼續"]
    kept, w = rr.waived_failures(a, decl, later, led)
    assert not kept and w[0][1]["via"] in ("quote", "ledger"), "同一支：不做行在就放行（引用或看帳）"
    b = [{"cmd": "pytest tests", "summary": "FAILED tests/b.py::test_total - y"}]
    kept, _ = rr.waived_failures(b, rr.parse_not_doing("不做｜test_total：太難了先不修"), later, led)
    assert kept == b, "別檔同名函式不借帳"
    reason_only = rr.parse_not_doing("不做｜test_total：太難了先不修")
    kept, _ = rr.waived_failures(a, reason_only, ["取消剛才的豁免，test_total 必須修好", "好", "繼續"], led)
    assert kept == a, "記帳後使用者又提到這支：帳不算；只有 AI 自己的理由也不豁免"
    kept, _ = rr.waived_failures(a, reason_only, later, led, history=["之前的話", "test_total 先跳過", *later])
    assert not kept, "記帳那則之後沒再提到：照帳"


def test_p7_reason_and_quote_need_text_not_length():
    """codex WARN／BLOCK：理由看有沒有文字內容不看字數（「風險高」算、「....」不算）；引用純標點不算、英文整詞比對。"""
    assert rr.reason_present("風險高") and rr.reason_present("不需要") and not rr.reason_present("....") and not rr.reason_present("<理由>")
    assert not rr.reason_present("<理由：風險／為什麼超出>") and not rr.reason_present("  <為什麼>  ")
    assert not rr.reason_present("留到下個 session，<理由>"), "半抄範本、留著理由佔位不算"
    assert not rr.quote_in_prompts("!!", ["請修好!!"]) and not rr.quote_in_prompts("ok", ["broken"])
    assert rr.quote_in_prompts("ok", ["ok, skip it"]) and rr.quote_in_prompts("skip it", ["ok,  skip   it"])
    assert rr.quote_in_prompts("先這樣", ["好，先 這樣吧"])
    assert rr.names_item("python -m pytest hooks/verify/verify_a.py", "verify_a.py")
    assert not rr.names_item("python -m pytest hooks/verify/verify_a.py", "python")
    assert rr.names_item("python -m pytest hooks/verify/verify_a.py -q", "pytest hooks/verify/verify_a.py"), "帶空白的逐字片段"


def test_evasion_context_exempt_boundary():
    """EVASION_CONTEXT_EXEMPT：完整案例在 verify_hud_stage2.py；這裡守邊界——剛好等於門檻不豁免（和 DeferralGate 一致）。"""
    assert rr.evasion_context_exempt_verdict(True, 0.75, 0.75, True, ["繼續"], True).owed
    assert not rr.evasion_context_exempt_verdict(True, 0.76, 0.75, True, ["繼續"], True).owed


# ─── T2.16 動資料檔 ───

def test_t216_user_data_file_needs_declaration():
    """USER_DATA_FILE_NEEDS_DECLARATION：四件事實全成立又沒宣告才擋；宣告路徑檔名完整比對；原話點名要整個檔名。完整案例在 verify_data_file_ask.py。"""
    t = "C:\\w1\\qb-report\\config\\settings.json"
    facts = {"code": False, "ext": ".json", "ext_listed": True, "existed": True, "created": False, "named": None, "prompts": 1}
    assert rr.data_file_verdict(t, "config/settings.json", facts, []).owed
    assert not rr.data_file_verdict(t, "config/settings.json", {**facts, "created": True}, []).owed
    decl = rr.parse_data_file_decls("動資料檔｜`config/settings.json`：修多逗號，幣別會變 TWD")
    assert not rr.data_file_verdict(t, "config/settings.json", facts, decl).owed
    for p in ("settings.json", "config/settings.json", "C:\\w1\\qb-report\\config\\settings.json", "./config/settings.json"):
        assert rr.decl_names_file(p, t), p
    for p in ("ettings.json", "other.json", "x/settings.json", ""):
        assert not rr.decl_names_file(p, t), p
    assert rr.parse_data_file_decls("動資料檔｜C:\\a\\b.json：理由")[0][:2] == ("C:\\a\\b.json", "理由")
    assert rr.prompt_names_file(["把settings.json的逗號修掉"], t) and rr.prompt_names_file(["改 Config/Settings.JSON"], t)
    assert not rr.prompt_names_file(["改 settings.json.bak", "看 mysettings.json", "設定檔"], t)
    zh = "C:\\p\\設定.json"
    assert not rr.prompt_names_file(["請修改「備份設定.json」", "請修改備份設定.json"], zh), "更長的中文檔名不算點名"
    assert rr.prompt_names_file(["請修改「設定.json」", "改 設定.json 的值"], zh)
    assert rr.reason_present("修正 <幣別> 標籤") and rr.reason_present("通貨を直す") and rr.reason_present("x")
    assert not any(rr.reason_present(w) for w in ("", "。。", "  ", "<為什麼要動它、動了使用者會看到什麼>"))


def test_reason_quoting_a_tag_is_still_a_reason_on_claim_and_not_doing_lines():
    """CLAIM_DISCLAIM_NEEDS_REASON／NOT_DOING_DECLARED：理由裡引用 <中文> 標籤（XML、範本名）是有理由；整段是角括號佔位才不算。"""
    disp = rr.parse_claim_dispositions("宣稱｜修好：非本回合宣稱，因為 修好的是同伴改的 <幣別> 標籤，不是我")
    assert not rr.claim_disposition_verdict("fixed", disp, lambda ref: None).owed
    disp = rr.parse_claim_dispositions("宣稱｜修好：非本回合宣稱，因為 <理由>")
    assert rr.claim_disposition_verdict("fixed", disp, lambda ref: None).owed
    line = "不做｜改 <幣別> 欄位：要使用者拍板幣別預設值"
    assert not rr.not_doing_verdict(line, rr.parse_not_doing(line), []).owed
    line = "不做｜幣別欄位：<理由：風險／為什麼超出>"
    assert rr.not_doing_verdict(line, rr.parse_not_doing(line), []).owed
# ─── T2.18 origin 核對 ───
def test_origin_user_needs_quote():
    """ORIGIN_USER_NEEDS_QUOTE：完整案例在 verify_origin_user_check.py；這裡守判式——字面子串對得到才算、同伴說的不算。"""
    said = [{"seq": 3, "turn": 1, "text": "把 audit 寫進 log 檔"}]
    origin, v, m = rr.origin_user_verdict("audit 要寫進 log 檔", "audit 寫進 log 檔", said)
    assert origin == "user" and not v.owed and m["said"]["seq"] == 3
    origin, v, m = rr.origin_user_verdict("舊報表不被弄壞", None, said)
    assert origin == "inferred" and v.owed and v.rule == "ORIGIN_USER_NEEDS_QUOTE" and m is None
    _, v, _ = rr.origin_user_verdict("x", "報表格式不能變", said, [{"from": "claude-aa", "text": "報表格式不能變喔"}])
    assert v.owed and "同伴 claude-aa" in v.why
    # 樹根版：切句後 ≥6 字、原話裡沒有的句子
    assert rr.root_unquoted_sentences("把 audit 寫進 log 檔；舊報表不被弄壞，ok", said) == ["舊報表不被弄壞"]
    assert rr.root_unquoted_sentences("把 audit 寫進 log 檔——舊報表不被弄壞", said) == ["舊報表不被弄壞"]   # 雙破折號也切
# ─── T2.17 改舊測試 ───

def test_old_test_change_needs_declaration_names_and_reason():
    """OLD_TEST_CHANGE_NEEDS_DECLARATION：完整案例在 verify_old_test_declare.py；這裡守宣告行的名字與理由對法。"""
    ch = [{"key": "TestR.test_a", "kind": "assert", "detail": "assertx==1"}, {"key": "test_b", "kind": "renamed", "detail": "", "new_key": "test_b2"}]
    v = rr.old_test_change_verdict("tests/test_r.py", ch, [])
    assert v.owed and v.rule == "OLD_TEST_CHANGE_NEEDS_DECLARATION" and "test_r.py：test_b（改名 → test_b2）" in v.evidence
    ok = rr.parse_old_test_declarations("改舊測試｜tests/test_r.py:TestR.test_a、test_b: 使用者說欄位改了")
    assert ok[0]["reason"] == "使用者說欄位改了" and not rr.old_test_change_verdict("tests/test_r.py", ch, ok).owed
    assert rr.old_test_change_verdict("tests/test_r.py", ch, rr.parse_old_test_declarations("改舊測試｜test_a、test_b2：欄位改了")).owed, \
        "改名只認舊名：新名不能替舊的那支宣告"
    for other in ("改舊測試｜tests/test_x.py:test_a、test_b：別的檔", "改舊測試｜TestOther.test_a、test_b：別的類別"):
        assert rr.old_test_change_verdict("tests/test_r.py", ch, rr.parse_old_test_declarations(other)).owed, other
    v = rr.old_test_change_verdict("tests/test_r.py", ch, rr.parse_old_test_declarations("改舊測試｜test_a：<理由>"))
    assert v.owed and any("佔位" in e for e in v.evidence) and len(v.evidence) == 3
# ─── T2.19 繞閘嫌疑 ───

def test_t219_gate_bypass_verdicts():
    """GATE_BYPASS_NEEDS_DECLARATION／ATOM_BYPASS_HOWTO_REFUSED：完整案例在 verify_gate_bypass.py；這裡守判式——
    有序列事實沒理由（或只有佔位）擋、有理由放行、沒事實不擋；卡片兩訊號都有才拒。"""
    facts = ["git restore 把 notify/retry.py 移出暫存區"]
    assert rr.gate_bypass_verdict("notify/retry.py（匿名函式疊用）", facts).owed
    assert rr.gate_bypass_verdict("x", facts, "<理由：這批檔是誰的>").owed
    v = rr.gate_bypass_verdict("x", facts, "retry.py 是別人的改動")
    assert v.rule == "GATE_BYPASS_NEEDS_DECLARATION" and not v.owed
    assert not rr.gate_bypass_verdict("x", []).owed
    assert rr.atom_bypass_verdict(["SmellGate"], ["拆三步"]).owed
    v = rr.atom_bypass_verdict(["SmellGate"], [])
    assert v.rule == "ATOM_BYPASS_HOWTO_REFUSED" and not v.owed and not rr.atom_bypass_verdict([], ["git stash"]).owed
    assert not rr.atom_bypass_verdict(["SmellGate"], ["git reset"], "這張卡寫的是禁止規避").owed     # 宣告了不是教繞閘
    assert rr.atom_bypass_verdict(["SmellGate"], ["git reset"], "<理由：這張卡在教什麼>").owed      # 佔位照拒
# ─── G14 最小地圖 ───
# 完整案例（閘、掃表預覽、快取、開關）在 hooks/verify/verify_g14_min_map.py；這裡只守 test_044「每條規則有案例」與判定骨架

def test_g14_unmapped_first_edit_needs_min_map():
    """UNMAPPED_FIRST_EDIT_NEEDS_MIN_MAP：三行齊、讀了的檔都讀過才不欠；沒交、上游空、列了沒讀的檔 → 欠。"""
    g = rr.min_map_group("地圖｜讀了：src/a.py\n地圖｜上游：無，因為是入口\n地圖｜下游：lib/b.py")
    assert rr.min_map_verdict(g, "C:/p", ["C:/p/src/a.py"]).owed is False
    v = rr.min_map_verdict(g, "C:/p", [])
    assert v.rule == "UNMAPPED_FIRST_EDIT_NEEDS_MIN_MAP" and v.owed and "src/a.py" in "；".join(v.evidence)
    assert rr.min_map_verdict(None, "C:/p", ["C:/p/src/a.py"]).owed
    assert rr.min_map_verdict({**g, "上游": ""}, "C:/p", ["C:/p/src/a.py"]).owed
# ─── G11 拐彎判斷 ─────────────────────────────────────────────────────────────

def test_g11_turn_judgment_required_needs_five_columns():
    """TURN_JUDGMENT_REQUIRED：到門檻的每一條要有五欄齊的拐彎判斷行；完整案例在 verify_g11_turns.py，這裡只守規則名與五欄。"""
    item = {"kind": "函式", "name": "y.py::b", "keys": ["y.py::b", "b"], "nums": "巢狀 4"}
    assert rr.turn_judgment_verdict([item], rr.parse_turn_judgments("拐彎判斷｜y.py::b｜不會｜只有一層｜合理，因為短")).owed is False
    v = rr.turn_judgment_verdict([item], rr.parse_turn_judgments("拐彎判斷｜y.py::b｜不會｜只有一層"))
    assert v.rule == "TURN_JUDGMENT_REQUIRED" and v.owed and "怎麼改直" in "".join(v.evidence)
# ─── G9 第二意見 ───

def test_g9_second_opinion_rules_registered():
    """SECOND_OPINION_REQUIRED／SECOND_OPINION_DECLINED：規則名登記、四行少一行就擋、空話理由照擋（完整案例在 verify_g9_second_opinion.py）。"""
    four = "## 第二意見與分歧裁決\nCodex 結論：同意\n我方結論：同意\n分歧點：無分歧\n"
    v = rr.second_opinion_verdict(True, ["程式檔 5 個 ≥ 4"], True, [("j1", "done")], four)
    assert v.rule == "SECOND_OPINION_REQUIRED" and v.owed and "裁決與理由" in v.why
    v = rr.second_opinion_verdict(True, ["程式檔 5 個 ≥ 4"], True, [], "不需第二意見｜不需要")
    assert v.rule == "SECOND_OPINION_DECLINED" and v.owed


# ─── G7 等值與熱路徑 ───

def test_g7_equivalence_and_hot_path_rules():
    """REFACTOR_NEEDS_EQUIVALENCE／PERF_HOT_PATH_NEEDS_MEASURE：完整案例（Stop 驅動、注入、意圖來源）在 verify_g7_equivalence.py；
    這裡守規則名與最小判式。"""
    eq = rr.equivalence_verdict(["order"], [])
    assert eq.rule == "REFACTOR_NEEDS_EQUIVALENCE" and eq.owed and "side_effect、boundary" in eq.why
    assert not rr.equivalence_verdict(["order", "side_effect", "boundary"], []).owed
    hot = rr.parse_equivalence_lines("熱路徑｜是｜render 迴圈")
    v = rr.hot_path_verdict(hot["hot"], hot["skip"], False)
    assert v.rule == "PERF_HOT_PATH_NEEDS_MEASURE" and v.owed
    assert not rr.hot_path_verdict(hot["hot"], hot["skip"], True).owed


# ─── 005 第四跑閘接縫：紅測失敗項、綠只清跑到的、原話核對看得到沒掛上的、宣告留帳、候選不靠固定字樣 ───

_C1_ERP = "tests/test_erp_contract.py::test_checkout_fields_match_erp_contract"
_C1_NOT_DOING = "不做｜test_checkout_fields_match_erp_contract：使用者說「先不用管它、跳過」"
_C1_SAID = "test_erp_contract 那支是 ERP 對接的舊合約測試，先不用管它、跳過。其他照做。"
# 第四跑 C-1 第 7 回合那條混了 git 與 pytest 的指令：摘要（最後 20 行）第一行是 git status 的 Untracked files:
_C1_MIXED_SUMMARY = ("Untracked files:\n  (use \"git add <file>...\" to include in what will be committed)\n"
                     "\t.gitattributes\n\tconfig/promos.json\n$ git diff --stat\n README.md | 2 +-\n"
                     " 6 files changed, 20 insertions(+), 8 deletions(-)\n$ python -m pytest tests -q\n"
                     "=========================== short test summary info ===========================\n"
                     f"FAILED {_C1_ERP} - ...\n1 failed, 14 passed in 0.16s")
_C1_MIXED_CMD = ("echo '$ git log --oneline' && git log --oneline && echo && echo '$ git status' && git status && echo "
                 "&& echo '$ python -m pytest tests -q' && python -m pytest tests -q 2>&1 | tail -3")


def test_005_red_items_only_from_failure_lines_label_and_cmd():
    """RED_ITEMS_ONLY_FROM_FAILURE_LINES：擋訊息的失敗項是 FAILED 節點、不是摘要第一行（第四跑擋訊息印的是 Untracked files:、
    Exit code 1、指令第一行的不做註解）；指令只取實際跑的部分。"""
    entry = {"cmd": _C1_MIXED_CMD, "summary": _C1_MIXED_SUMMARY}
    assert rr.red_item_label(entry) == _C1_ERP.lower()
    assert "Untracked" not in rr.red_item_label(entry)
    assert rr.cmd_run_line(f"# {_C1_NOT_DOING}\ncd /c/w4/qc2-orders && python -m pytest tests -q") == \
        "cd /c/w4/qc2-orders && python -m pytest tests -q"
    failed = {"cmd": "python -m pytest tests -q", "summary": "Exit code 1\n......F\n1 failed, 14 passed"}
    assert "沒列出" in rr.red_item_label(failed), "沒有節點行就明說沒列出，不拿 Exit code 行當失敗項"
    go = {"cmd": "go test ./...", "summary": "--- FAIL: TestTotal (0.00s)\nFAIL\nok  other 0.1s"}
    assert rr.red_item_label(go).startswith("--- FAIL: TestTotal")


def test_005_unlisted_red_not_waived_by_comment_or_git_output():
    """RED_ITEMS_ONLY_FROM_FAILURE_LINES：摘要沒列節點時整筆當一支，比對文字只有指令實際跑的部分與失敗行——AI 寫在指令註解裡的
    不做行、git status 列出的測試檔都不能讓不做行「對到」（舊碼拿指令全文＋整段摘要比，兩種都會誤放）。"""
    decls = rr.parse_not_doing("不做｜test_erp_contract.py：使用者說「先不用管它、跳過」")
    commented = {"cmd": "# 跳過 test_erp_contract.py 照紅\npython -m pytest tests -q 2>&1 | tail -1", "summary": "1 failed, 14 passed"}
    kept, waived = rr.waived_failures([commented], decls, [_C1_SAID])
    assert kept and not waived, "輸出沒列是哪一支，指令註解裡寫的檔名不算（要不截斷重跑）"
    noisy = {"cmd": "python -m pytest -q", "summary": "Untracked files:\n\ttests/test_legacy.py\n1 failed"}
    kept, waived = rr.waived_failures([noisy], rr.parse_not_doing("不做｜test_legacy.py：使用者說「先不用管它、跳過」"),
                                      [_C1_SAID])
    assert kept and not waived, "git status 列出的檔不是失敗項"
    # 反例：指令實際點名那個案例檔、或失敗行帶名字 → 照對得到
    named = {"cmd": "python -m pytest tests/test_erp_contract.py -q | tail -1", "summary": "1 failed"}
    kept, waived = rr.waived_failures([named], rr.parse_not_doing("不做｜test_erp_contract.py：使用者說「先不用管它、跳過」"),
                                      [_C1_SAID])
    assert not kept and waived
    go = {"cmd": "go test ./...", "summary": "--- FAIL: TestErpContract (0.00s)\nFAIL"}
    kept, waived = rr.waived_failures([go], rr.parse_not_doing("不做｜TestErpContract：使用者說「先不用管它、跳過」"), [_C1_SAID])
    assert not kept and waived


def test_005_waiver_miss_notes_say_why_the_line_did_not_count():
    """RED_ITEMS_ONLY_FROM_FAILURE_LINES：不做行對到了那支、卻只寫自己的理由（沒有使用者說）→ 擋訊息說出這件事；對不到的不說。"""
    entry = {"cmd": _C1_MIXED_CMD, "summary": _C1_MIXED_SUMMARY}
    later = ["收尾時順便跟我說一下", "交材料：把這一題的目標樹整理成一則回覆給我"]
    own = _C1_NOT_DOING.split("：使用者說")[0] + "：太難了先不修"
    kept, _ = rr.waived_failures([entry], rr.parse_not_doing(own), later)
    notes = rr.waiver_miss_notes(kept, rr.parse_not_doing(own), later)
    assert len(notes) == 1 and _C1_ERP.lower() in notes[0] and "只寫了自己的理由" in notes[0], notes
    assert rr.waiver_miss_notes(kept, rr.parse_not_doing("不做｜test_total：使用者說「先不用管它、跳過」"), later) == []
    # 帳上有這支、收尾沒寫不做行 → 給那一行照抄；帳上是別支 → 不說
    led = [{"item": "test_checkout_fields_match_erp_contract", "quote": "先不用管它、跳過", "units": [_C1_ERP.lower()]}]
    notes = rr.waiver_miss_notes(kept, [], later, led)
    assert len(notes) == 1 and "帳上有" in notes[0] and f"「{_C1_NOT_DOING}」" in notes[0], notes
    assert rr.waiver_miss_notes(kept, [], later, [{**led[0], "units": ["tests/test_cart.py::test_total"]}]) == []


_C1_THREE = "cd /c/w4/qc2-orders && python -m pytest tests/test_pricing.py tests/test_checkout.py tests/test_cli.py -q"


def test_005_green_clears_only_cases_it_ran():
    """GREEN_CLEARS_ONLY_CASES_IT_RAN：第四跑 C-1 跑另外 3 支測試檔變綠，就把全套那筆 ERP 紅整筆清掉、收尾放行；綠只清它跑到的那幾支。"""
    red_cmd, red_sum = "python -m pytest tests -q", f"FAILED {_C1_ERP} - ..."
    v, ran = rr.green_ran_cases_verdict(red_cmd, red_sum, _C1_THREE)
    assert v.rule == "GREEN_CLEARS_ONLY_CASES_IT_RAN" and v.owed and ran == []
    mixed = f"FAILED tests/test_pricing.py::test_free_shipping_at_threshold - x\nFAILED {_C1_ERP} - y"
    v, ran = rr.green_ran_cases_verdict(red_cmd, mixed, _C1_THREE)
    assert v.owed and ran == ["tests/test_pricing.py::test_free_shipping_at_threshold"], "只跑到一部分：跑到的那支拿掉、其餘照留"
    v, ran = rr.green_ran_cases_verdict(red_cmd, mixed, _C1_THREE, cleared=ran)
    assert v.owed and ran == [], "已拿掉的不再算"
    # 反例：跑到了就清（整檔、節點、整套）
    assert not rr.green_ran_cases_verdict(red_cmd, red_sum, "python -m pytest tests/test_erp_contract.py -q")[0].owed
    assert not rr.green_ran_cases_verdict(red_cmd, red_sum, f"python -m pytest {_C1_ERP}")[0].owed
    assert not rr.green_ran_cases_verdict(red_cmd, red_sum, "python -m pytest -q")[0].owed
    # 紅沒列案例：紅點名的檔綠都跑了才清
    assert not rr.green_ran_cases_verdict("pytest tests/test_a.py | tail -1", "1 failed", "pytest tests/test_a.py tests/test_b.py")[0].owed
    assert rr.green_ran_cases_verdict("pytest tests/test_a.py | tail -1", "1 failed", "pytest tests/test_b.py")[0].owed
    # 有 -k 篩選照 GREEN_NARROWED_KEEPS_UNCOVERED_RED
    v, _ = rr.green_ran_cases_verdict(red_cmd, red_sum, "python -m pytest tests -k pricing")
    assert v.rule == "GREEN_NARROWED_KEEPS_UNCOVERED_RED" and v.owed


def test_005_codex_green_dirs_and_narrowed_after_partial_clear():
    """GREEN_CLEARS_ONLY_CASES_IT_RAN（codex 005）：點名目錄也是範圍（跑 tests/unit 綠不清 tests/ 下別處的紅；基底連同整套一起清）；
    選項的值不當目錄；之前已清掉的那支不再擋篩選綠（本輪新開的誤擋）。"""
    red_cmd, red_sum = "python -m pytest tests -q", f"FAILED {_C1_ERP} - ..."
    assert rr.green_ran_cases_verdict(red_cmd, red_sum, "python -m pytest tests/unit -q")[0].owed
    assert rr.green_ran_cases_verdict(red_cmd, red_sum, "python -m pytest -n 4 tests/unit")[0].owed
    assert not rr.green_ran_cases_verdict(red_cmd, red_sum, "python -m pytest -q tests")[0].owed
    assert not rr.green_ran_cases_verdict(red_cmd, red_sum, "python -m pytest --basetemp /tmp/x -q")[0].owed, "選項的值不是範圍"
    assert not rr.green_ran_cases_verdict("pytest tests -q | tail -1", "1 failed", "pytest tests -q")[0].owed, "同一組點名重跑"
    two = "FAILED tests/test_a.py::test_a - x\nFAILED tests/test_b.py::test_b - y"
    v, ran = rr.green_ran_cases_verdict(red_cmd, two, "python -m pytest tests/test_b.py::test_b -k test_b",
                                        cleared=["tests/test_a.py::test_a"])
    assert not v.owed and ran == ["tests/test_b.py::test_b"], v


def test_005_codex_unlisted_units_ignore_trailing_comment_echo_and_split_per_failure():
    """RED_ITEMS_ONLY_FROM_FAILURE_LINES（codex 005，基底同樣誤放）：沒列節點時，行尾註解、echo 這類別段的檔名不算；
    go／unittest 一行一支的失敗各自要有豁免，只豁免一支整筆照紅；結算行（FAIL、FAIL\t<套件>）不是一支。"""
    decl = rr.parse_not_doing("不做｜test_erp_contract.py：使用者說「先不用管它、跳過」")
    for cmd in ("python -m pytest tests -q # test_erp_contract.py", "echo test_erp_contract.py && python -m pytest tests -q"):
        kept, waived = rr.waived_failures([{"cmd": cmd, "summary": "1 failed, 14 passed"}], decl, [_C1_SAID])
        assert kept and not waived, cmd
    go = {"cmd": "go test ./...", "summary": "--- FAIL: TestErpContract (0.00s)\n    --- FAIL: TestErpContract/fields (0.00s)\n"
                                              "--- FAIL: TestPayment (0.00s)\nFAIL\nFAIL\tgithub.com/x/pkg\t0.01s"}
    assert rr.failure_units(go["summary"]) == ["TestErpContract", "TestPayment"]
    kept, _ = rr.waived_failures([go], rr.parse_not_doing("不做｜TestErpContract：使用者說「先不用管它、跳過」"), [_C1_SAID])
    assert kept, "付款那支沒豁免，整筆照紅"
    both = "不做｜TestErpContract：使用者說「先不用管它、跳過」\n不做｜TestPayment：使用者說「先不用管它、跳過」"
    kept, waived = rr.waived_failures([go], rr.parse_not_doing(both), [_C1_SAID])
    assert not kept and sorted(u for _f, h in waived for u in h["units"]) == ["TestErpContract", "TestPayment"]
    ut = "FAIL: test_contract (tests.test_erp.ErpCase)\n----\nFAILED (failures=1)"
    assert rr.failure_units(ut) == ["test_contract"]


def test_005_codex_miss_notes_skip_tests_already_waived_by_ledger():
    """codex 005（本輪新開）：ERP 照帳豁免了、整筆還紅是因為付款那支——不再對 ERP 說「帳上也沒有」。"""
    entry = {"cmd": "python -m pytest tests -q", "summary": f"FAILED {_C1_ERP} - x\nFAILED tests/test_pay.py::test_pay - y"}
    decls = rr.parse_not_doing(_C1_NOT_DOING)
    led = [{"item": "test_checkout_fields_match_erp_contract", "quote": "先不用管它、跳過", "units": [_C1_ERP.lower()]}]
    kept, _ = rr.waived_failures([entry], decls, ["好"], led, ["好"])
    assert kept and rr.waiver_miss_notes(kept, decls, ["好"], led) == []


def test_005_origin_said_includes_unattached():
    """ORIGIN_SAID_INCLUDES_UNATTACHED：樹結束時收的原話（said_log attached=false）也是核對來源；已掛上別棵樹的不重複算。"""
    import wg_need_goal as ng
    said = "不對，折扣碼不要放 shop.json，改成另外開一個新檔 config/promos.json 放；shop.json 只留門檻那一個改動。"
    tree = {"said_all": [{"seq": 1, "turn": 1, "text": "訂單要支援折扣碼"}], "user_said": []}
    doc = {"said_log": [{"seq": 88, "turn": 5, "text": said, "attached": False},
                        {"seq": 2, "turn": 2, "text": "別棵樹的話", "attached": True}]}
    quote = "改成另外開一個新檔 config/promos.json 放；shop.json 只留門檻那一個改動"
    assert rr.origin_user_verdict("折扣碼放新檔", quote, ng._said_for_check(tree))[0] == "inferred", "前置：只看樹上的對不到"
    origin, v, match = rr.origin_user_verdict("折扣碼放新檔", quote, ng._said_for_check(tree, doc))
    assert origin == "user" and match["said"]["seq"] == 88 and v.rule == "ORIGIN_USER_NEEDS_QUOTE"
    assert [s["seq"] for s in ng._said_for_check(tree, doc)] == [1, 88]


def test_005_second_opinion_declared_always_logged_registered():
    """SECOND_OPINION_DECLARED_ALWAYS_LOGGED：宣告行的判法（行首、理由過 second_opinion_decline_ok）；Stop 端留帳案例在
    verify_g9_second_opinion.py 的 005 段。"""
    assert rr.second_opinion_decline("不需第二意見｜這一輪沒有改任何程式，只做搜尋和實測確認。") == "這一輪沒有改任何程式，只做搜尋和實測確認。"
    assert rr.second_opinion_decline_ok("這一輪沒有改任何程式，只做搜尋和實測確認。")
    assert not rr.second_opinion_decline_ok("不需要")
    assert "SECOND_OPINION_DECLARED_ALWAYS_LOGGED" in rr.RULES


# 第四跑 B-1 第一版根因層：兩個跨層候選用 ①② 列，沒寫「候選 A」
_B1_V1 = ("新功能非修 bug；附帶根因①邏輯層 periods.month_of 以 UTC 切月違反 README 台北時間；②測試層 monthly 期望值照 UTC 算鎖住錯誤；"
          "資料讀入層 ts 保留 +08:00 沒壞")


def test_005_locate_candidates_without_fixed_labels():
    """LOCATE_CANDIDATES_WITHOUT_FIXED_LABELS：沒寫「候選 A」時，①② 列舉或兩個以上不同的「X 層」也算候選（第四跑 B-1 第一版判成
    0 個、第三版改成固定字樣才過）；選擇理由照樣要寫。"""
    assert rr.root_candidates(_B1_V1) == [1, 2]
    v = rr.locate_lines_verdict(_B1_V1, _B1_GOAL, "T1.1", _CG0_NODE)
    assert v.owed and "辨識出 2 個候選，但沒寫選擇理由" in v.why, v
    assert not rr.locate_lines_verdict(_B1_V1 + "；選①因為②只是照①的輸出寫的", _B1_GOAL, "T1.1", _CG0_NODE).owed
    layers = "month_of 在邏輯層用 UTC 切月；測試層期望值照 UTC 鎖住；先修邏輯層因為測試只是照輸出寫"
    assert len(rr.root_candidates(layers)) == 2 and not rr.locate_lines_verdict(layers, _B1_GOAL, "T1.1", _CG0_NODE).owed
    # 反例：只有一層、一個列舉、泛稱、函式呼叫的括號數字 → 照舊 0 個
    for one in ("根因在邏輯層；這層以外沒問題", "①邏輯層 month_of 用 UTC", "第二層、每層都看過", "f(1) 與 g(2) 都呼叫 month_of",
                "根因層在邏輯層", "根因在邏輯層；先修邏輯層因為只有這一處寫", "第四層、第五層；先修第四層因為錯誤從這裡開始"):
        assert rr.root_candidates(one) == [], one
    # codex 005：名稱尾段相同的兩層（資料讀取／設定讀取）是兩層
    assert len(rr.root_candidates("資料讀取層解析錯誤；設定讀取層覆蓋錯誤；先修資料讀取層因為設定沿用其輸出")) == 2
    assert rr.root_candidates("候選 A 邏輯層；候選 B 不存在因為資料層只讀") == [1], "有固定標記就只看標記"


@pytest.mark.parametrize("root, want", [
    # 修前判反的四句：逗號拆開的候選描述、第一個候選前的前言 → 不算；「選候選 A」「採用候選 A」→ 算
    ("候選 A 快取層，因為重啟後沒清所以失效；候選 B 索引層；選 A", False),
    ("新功能，所以不算修壞；候選 A 快取層；候選 B 索引層；選 A", False),
    ("候選 A 快取層；候選 B 索引層；選候選 A 因為 B 只是症狀", True),
    ("候選 A 快取層；候選 B 索引層；採用候選 A 的理由是 B 只讀", True),
    # 反例保持原判
    ("候選 A 壞在快取層因為沒清；候選 B 索引層；選 A", False),
    ("候選 A 的原因是快取失效；候選 B 是寫入時序", False),
    ("第一根因 共用字典被兩邊改；第二根因 存檔時序；先修第一個因為第二個是它的結果", True),
    ("候選一 邏輯層；候選二 資料層；理由：資料層只讀", True),
    ("理由：資料層只讀", True),
    ("候選 A 邏輯層，候選 B 資料層，選 A 因為只有邏輯層寫", True),        # 逗號分隔的選擇句照算
    ("候選 A 快取層，因為沒清；候選 B 索引層，選它因為好重現", True),     # 同句裡後面那個因為前面有「選」
])
def test_007_choice_reason_belongs_to_choice(root, want):
    """CHOICE_REASON_BELONGS_TO_CHOICE：理由詞要屬於選擇才算選擇理由——只以「；;。」切句，句裡前面有選／採，或句裡前面沒有候選標記
    且在第一個候選標記之後。修前逗號也切段（描述的「因為」被當理由）、「選候選 A 因為」被當描述擋下。"""
    assert "CHOICE_REASON_BELONGS_TO_CHOICE" in rr.RULES
    if not want:          # 前置：判「沒理由」的句子真的有兩個候選，擋下是因為判到理由這一步、不是候選不夠
        assert len(rr.root_candidates(root)) >= 2, root
    assert rr._has_choice_reason(root) is want, root
    v = rr.locate_lines_verdict(root, "T1.1（唯一寫入點）", "T1.1", _CG0_NODE)
    assert ("沒寫選擇理由" in v.why) is (not want and len(rr.root_candidates(root)) >= 2), v


# ─── 閘小修 006 ─────────────────────────────────────────────────────────────────────────────


def test_006_judge_card_change_needs_declaration():
    """JUDGE_CARD_CHANGE_NEEDS_DECLARATION（裁定 #53）：綁 Entry 的卡要有點名這張、附理由的宣告；沒綁 Entry 不管。
    四條出口與留帳的端到端案例在 verify_judge_card_declare.py。"""
    decls = rr.parse_judge_card_decls("改判準卡｜卡-a：使用者說判準錯了\n改判準卡｜卡-b：<為什麼要改這張量尺>")
    assert not rr.judge_card_verdict("卡-a", ["E29"], decls).owed
    v = rr.judge_card_verdict("卡-b", ["E29"], decls)
    assert v.owed and any("沒附理由" in e for e in v.evidence), v
    assert rr.judge_card_verdict("卡-c", ["E29"], decls).owed
    assert not rr.judge_card_verdict("卡-c", [], decls).owed
    assert "JUDGE_CARD_CHANGE_NEEDS_DECLARATION" in rr.RULES


def test_006_inline_flag_before_program():
    """INLINE_FLAG_BEFORE_PROGRAM：內嵌碼旗標只認直譯器選項位置；Bash 解析的案例在 verify_write_targets.py 的 006 段。"""
    import wg_core
    assert wg_core._inline_flag_at("python", ["x.py", "-C", "C:/p"]) == -1
    assert wg_core._inline_flag_at("python", ["-X", "utf8", "-c", "print(1)"]) == 2
    assert wg_core._inline_flag_at("pwsh", ["-NoProfile", "-C", "x"]) == 1
    assert "INLINE_FLAG_BEFORE_PROGRAM" in rr.RULES


def test_006_shell_literal_var_expanded():
    """SHELL_LITERAL_VAR_EXPANDED：同指令字面指定之後的 $S 代換；Bash 解析案例在 verify_write_targets.py 006 段、
    閘的端到端在 verify_pre_tool_use_overview_gate.py 006 段。"""
    import wg_core
    got = wg_core.write_paths_from_tool("Bash", {"command": "S='C:/tmp/sp' && echo x > \"$S/a.py\""}, "C:/w")
    assert got == [str(Path("C:/tmp/sp/a.py"))], got
    assert wg_core.write_paths_from_tool("Bash", {"command": "echo x > \"$S/a.py\""}, "C:/w")[0].startswith("UNKNOWN:")
    assert "SHELL_LITERAL_VAR_EXPANDED" in rr.RULES


def test_006_claim_conditional_not_claim():
    """CLAIM_CONDITIONAL_NOT_CLAIM：條件句與宣稱行不算宣稱；三份詞表與 B5 重播在 verify_verify_ledger.py 的 006 段。"""
    assert not vl.claims_fixed("追蹤系統裡這件事重複記了 3 筆，修好之後一起結案。")
    assert not vl.claims_fixed("宣稱｜修好：非本回合宣稱，因為那句是講以後的條件")
    assert vl.claims_fixed("修好之後重跑了，全綠")
    assert "CLAIM_CONDITIONAL_NOT_CLAIM" in rr.RULES


def test_006_tracking_same_item_not_rewritten(tmp_path, monkeypatch):
    """TRACKING_SAME_ITEM_NOT_REWRITTEN：同一句不重記；「同追蹤項」對到唯一一筆就換新說法。B5 重播與反例在 verify_pick_one.py 006 段。"""
    import wg_harvest as wh
    monkeypatch.setattr(wh, "WORKFLOW_DIR", tmp_path)
    wh.append_tracking("s006", wh.tracking_entries("sid", 1, "[報表] monthly 用 UTC 切月份"))
    wh.append_tracking("s006", wh.tracking_entries("sid", 1, "[報表] monthly 用 UTC 切月份"))
    wh.append_tracking("s006", wh.tracking_entries("sid", 2, "[報表] month_of 改台北時間｜同追蹤項：monthly 用 UTC 切月份"))
    opens = wh.open_tracking_items(wh.read_tracking("s006"))
    assert [o["text"] for o in opens] == ["month_of 改台北時間"]
    assert "TRACKING_SAME_ITEM_NOT_REWRITTEN" in rr.RULES


def test_launcher_not_code_source_shapes():
    """LAUNCHER_NOT_CODE：整支只用 subprocess 跑 git 才算一次性啟動器；多一個別的呼叫或 import 就照算程式。"""
    assert "LAUNCHER_NOT_CODE" in rr.RULES
    ok = ['import subprocess\nsubprocess.run(["git", "status"])\n',
          'import subprocess, sys\nr = subprocess.run(["git", "-C", "x", "commit", "-qm", "m"], capture_output=True, text=True)\n'
          'print(r.stdout)\nsys.exit(r.returncode)\n',
          'import subprocess\nfor c in [["git", "add", "-A"], ("git", "commit", "-qm", "m")]:\n    subprocess.check_call(c)\n']
    bad = ['print("hi")\n',                                                          # 沒跑 git
           'import subprocess\nsubprocess.run(["python", "x.py"])\n',               # 跑的不是 git
           'import subprocess, json\nsubprocess.run(["git", "status"])\n',          # 多 import
           'import subprocess\nsubprocess.run(["git", "status"])\nopen("a", "w").write("b")\n',   # 多寫檔
           'import subprocess\ncmd = ["git", "status"]\nsubprocess.run(cmd)\n',      # 參數不是字面值、也不是 for 走過的
           'import subprocess\nsubprocess.run("git status", shell=True)\n',          # 字串指令
           'def (:\n']                                                               # 解析不了
    assert all(rr.is_git_launcher_source(s) for s in ok)
    assert not any(rr.is_git_launcher_source(s) for s in bad)


# ─── 別處實作的規則：登記在 RULES、指到真正驗它的案例 ──────────────────────────
# 案例函式在各自的 verify 檔（走真入口才驗得到）；這裡只核對規則有登記、對照的案例檔與函式真的在。

_ELSEWHERE_CASES = {
    "GATE_DENY_CAP": [("verify_pull_tool_gates.py", "test_deny_cap_counts_each_item_per_user_turn"),
                      ("verify_pull_goal_locate.py", "test_locate_gate_same_gap_blocks_twice_then_passes_with_log"),
                      ("verify_pull_goal_locate.py", "test_unmapped_gate_same_gap_blocks_twice_then_passes_with_log")],
    "DENY_CAP_PER_REPLY": [("verify_pull_tool_gates.py", "test_deny_cap_per_reply_counts_one_reply_once"),
                           ("verify_pull_tool_gates.py", "test_data_file_gate_parallel_edits_in_one_reply_count_once"),
                           ("verify_pre_tool_use_overview_gate.py", "test_parallel_edits_in_one_reply_all_denied_then_locate_passes"),
                           ("verify_g14_min_map.py", "test_parallel_unmapped_edits_in_one_reply_count_once")],
    "PICK_ONCE_PER_USER_TURN": [("verify_pick_one.py", "test_stop_continuation_after_red_test_block_still_asks_once")],
    "SVN_TEST_BLOCK_OPT_IN": [("verify_pull_tool_gates.py", "test_svn_test_block_off_by_default"),
                              ("verify_pull_tool_gates.py", "test_svn_test_block_on_looks_only_at_commit_paths"),
                              ("verify_pull_tool_gates.py", "test_svn_test_block_user_sentence_this_turn_allows")],
    "GATE_BYPASS_NAMED_FILES_MERGED": [
        ("verify_pull_tool_gates.py", "test_excluded_named_file_still_needs_declaration_after_other_file_fixed"),
        ("verify_pull_tool_gates.py", "test_declaration_after_a_named_still_counts_for_a"),
        ("verify_pull_tool_gates.py", "test_declaration_before_b_named_does_not_cover_b")],
    # 收尾閘那一批：案例在 verify_pull_stop_gates.py，每支 docstring 開頭寫「規則：<名>」
    "PENDING_SAME_USER_TURN": [("verify_pull_stop_gates.py", "test_1_pending_from_previous_user_turn_gives_fresh_budget"),
                               ("verify_pull_stop_gates.py", "test_9_second_opinion_pending_from_previous_turn_not_exhausted")],
    "RELEASE_COVERS_SHOWN_ITEMS": [
        ("verify_pull_stop_gates.py", "test_1_released_item_not_asked_again_next_turn_until_cause_gone"),
        ("verify_pull_stop_gates.py", "test_release_binds_to_items_the_user_was_shown"),
        ("verify_pull_stop_gates.py", "test_unformatted_new_reason_is_not_swallowed_by_released_item"),
        ("verify_pull_stop_gates.py", "test_8_released_red_tests_do_not_cover_a_new_failure")],
    "NONINTERACTIVE_RELEASE_AT_BUDGET": [
        ("verify_pull_stop_gates.py", "test_3_headless_main_session_releases_on_third_and_never_says_cannot_release"),
        ("verify_pull_stop_gates.py", "test_3_subagent_block_message_does_not_say_cannot_release"),
        ("verify_pull_stop_gates.py", "test_3_headless_equivalence_exhausted_releases_and_logs"),
        ("verify_pull_stop_gates.py", "test_8_testfail_third_stop_releases_and_logs_headless")],
    "ORDER_UNTIL_PUSH": [("verify_pull_stop_gates.py", "test_4_order_survives_commit_and_notification_for_gate_forced_fix"),
                         ("verify_pull_stop_gates.py", "test_4_user_new_message_in_continuation_needs_new_order"),
                         ("verify_pull_stop_gates.py", "test_4_push_done_spends_order_even_within_same_turn"),
                         ("verify_pull_stop_gates.py", "test_4_echo_or_dry_run_is_not_a_push"),
                         ("verify_pull_stop_gates.py", "test_4_push_then_commit_before_any_stop_needs_new_order"),
                         ("verify_pull_stop_gates.py", "test_4_push_result_written_after_scan_is_still_paired"),
                         ("verify_pull_stop_gates.py", "test_v6_off_order_spent_by_commit_and_kept_on_continuation_typing"),
                         ("verify_pull_stop_gates.py", "test_v6_off_stop_does_not_scan_push_and_commit_gate_ignores_it")],
    "RELOAD_ADVICE_MCP_EDITS_ONLY": [("verify_pull_stop_gates.py", "test_6_reload_advice_not_judged_without_mcp_edits")],
    "DEFERRAL_COVERS_EVASION_SENTENCE": [
        ("verify_pull_stop_gates.py", "test_7_deferral_block_clears_evasion_flag_for_same_sentence"),
        ("verify_pull_stop_gates.py", "test_7_other_sentence_keeps_evasion_flag"),
        ("verify_pull_stop_gates.py", "test_v6_off_deferral_block_keeps_evasion_flag")],
    # 紅測範圍：案例在 verify_red_scope_full_command.py（真的 PostToolUse 記帳清帳與 Stop 擋訊息）
    "RED_SCOPE_FROM_FULL_COMMAND": [
        ("verify_red_scope_full_command.py", "test_rerun_covering_scope_green_clears_red"),
        ("verify_red_scope_full_command.py", "test_long_command_full_suite_green_clears"),
        ("verify_red_scope_full_command.py", "test_unparsed_target_never_uses_fragment_and_has_a_doable_path"),
        ("verify_red_scope_full_command.py", "test_rerun_not_covering_scope_keeps_red_and_logs")],
    # 寫碼回合才跑 v6 守門：案例在 verify_gate_trim.py
    "CODING_TURN_ONLY": [("verify_gate_trim.py", "test_coding_turn_layer1_tool_writes_code"),
                         ("verify_gate_trim.py", "test_coding_turn_keyword_intent_is_not_a_switch"),
                         ("verify_gate_trim.py", "test_coding_turn_layer2_need_goal_declares_code_tree"),
                         ("verify_gate_trim.py", "test_non_coding_turn_skips_v6_gates_at_stop")],
}


def _case_function_source(text: str, fn: str) -> str:
    """案例檔裡 def fn 那一段（到下一個頂層 def／裝飾器／註解分段為止）；找不到回空字串。"""
    m = re.search(rf"^def {re.escape(fn)}\(.*?(?=^(?:def |@|# ─))", text + "\n# ─", re.MULTILINE | re.DOTALL)
    return m.group(0) if m else ""


@pytest.mark.parametrize("rule", sorted(_ELSEWHERE_CASES))
def test_rules_registered_with_case_functions_elsewhere(rule):
    """規則有登記、對照的案例函式真的在；收尾閘那一批（verify_pull_stop_gates.py）另核那支案例自己點到規則名。"""
    assert rule in rr.RULES
    for case_file, fn in _ELSEWHERE_CASES[rule]:
        text = (Path(__file__).parent / case_file).read_text(encoding="utf-8")
        assert f"def {fn}(" in text, (rule, case_file, fn)
        if case_file == "verify_pull_stop_gates.py":
            assert f"規則：{rule}" in _case_function_source(text, fn), (rule, fn)


def test_deny_cap_old_names_folded_into_gate_deny_cap():
    """GATE_DENY_CAP 收斂：舊稱不另立條目，說明裡寫明併入。"""
    assert "DECL_GATE_DENY_CAP" not in rr.RULES and "LOCATE_DENY_CAP" not in rr.RULES
    assert "DECL_GATE_DENY_CAP" in rr.RULES["GATE_DENY_CAP"] and "LOCATE_DENY_CAP" in rr.RULES["GATE_DENY_CAP"]


def test_decl_hints_do_not_steer_to_bash_writes():
    """規則 DECL_HINT_KEEPS_EDIT_TOOLS：擋 Edit／Write 要先交宣告行的閘，擋訊息不准再用會被讀成「改用 Bash 寫檔」的說法
    （補題第一版：AI 照「或寫成 Bash 指令開頭的 # 註解」全程用 python -c 改檔，改檔紀錄整個 session 是空的）。掃 hooks 全部
    原始碼；繞閘宣告（擋的就是那條 Bash 指令，寫「這條」指令的註解）不在此列。"""
    banned = ("或寫成 Bash／PowerShell 指令開頭的 `#` 註解", "或寫成下一個 Bash／PowerShell 指令開頭的", "下一個 Bash 開頭",
              "下一個工具呼叫的參數（Bash 開頭的註解）")
    hits = []
    for p in sorted(HOOKS_DIR.rglob("*.py")):
        if "verify" in p.relative_to(HOOKS_DIR).parts:
            continue
        src = p.read_text(encoding="utf-8")
        hits += [f"{p.relative_to(HOOKS_DIR).as_posix()}：{b}" for b in banned if b in src]
    assert not hits, hits
    assert "照常用 Edit／Write" in rr.DECL_KEEP_EDIT and "不寫檔" in rr.DECL_VIA_COMMENT


# ─── 閘小修 008 A：規則名登錄、對照的案例真的在、案例點到規則名 ───
_008A_CASES = {
    "OLD_TEST_COMPARED_ON_FAILED_COMMAND": ("verify_old_test_declare.py",
                                            "test_failed_command_changing_old_test_still_compared_and_blocks_next_call"),
    "USER_TURN_KEY_KEPT": ("verify_user_turn_key.py", "test_rebuilt_state_three_peer_messages_pick_one_asks_once"),
    "COMPLETION_CLAIM_PER_SENTENCE": ("verify_evasion_guard.py", "test_completion_exclude_only_cancels_its_own_sentence"),
    "OPENING_NOTICE_NOT_TODO": ("verify_opening_notice.py",
                                "test_harvest_staged_line_says_who_decides_and_relay_only_when_user_wants_else"),
    "GATE_TEXT_AVOIDS_EVASION_WORDS": ("verify_evasion_guard.py", "test_gate_texts_do_not_trip_evasion_detector"),
    "SUBPROCESS_RUN_LOOKED_UP_AT_CALL": ("verify_subprocess_run_default.py", "test_no_parameter_defaults_to_subprocess_run"),
}


@pytest.mark.parametrize("rule", sorted(_008A_CASES))
def test_008a_rules_registered_with_cases(rule):
    case_file, fn = _008A_CASES[rule]
    text = (Path(__file__).parent / case_file).read_text(encoding="utf-8")
    assert rule in rr.RULES and f"def {fn}(" in text, (rule, case_file, fn)
    assert rule in text, (rule, case_file)                     # 案例檔（模組說明或案例說明）點到規則名


# ─── 008 C：跨層判定的切段（端到端案例在 verify_cross_realm_bash_guard.py 的 008 段） ──────────

def test_008_segments_split_like_shell():
    """SEGMENTS_SPLIT_LIKE_SHELL：引號裡的換行留在同一段、引號外照切；黏著的 ; && | 也切；到最後引號沒收才回 None。"""
    assert rr._shlex_segments('git log -1\npython -c "\nprint(1)\n"') == [["git", "log", "-1"], ["python", "-c", "\nprint(1)\n"]]
    assert rr._shlex_segments("git status;git commit -m x") == [["git", "status"], ["git", "commit", "-m", "x"]]
    assert rr._shlex_segments("echo 'a;b' && git log") == [["echo", "a;b"], ["git", "log"]]
    assert rr._shlex_segments('git log "unclosed\nstill') is None
    assert rr.git_readonly_verdict("cd x;git commit -am y", []).owed is True                # 黏著的分隔後面的 commit 照擋
    assert rr._shlex_segments('git status; echo ";&" git reset --hard') == [["git", "status"], ["echo", ";&", "git", "reset", "--hard"]]
    assert rr._shlex_segments('git status; echo "" git reset') == [["git", "status"], ["echo", "", "git", "reset"]]
    assert rr._shlex_segments(r"echo 'a\' ; git log") == [["echo", "a\\"], ["git", "log"]]   # 單引號裡的反斜線照字面
    assert "UNKNOWN_PART_KEEPS_KNOWN_TARGETS" in rr.RULES and "_shell_write_paths" in rr.RULES["UNKNOWN_PART_KEEPS_KNOWN_TARGETS"]


def test_008_shell_keyword_prefix_stripped():
    """SHELL_KEYWORD_PREFIX_STRIPPED：段首 do／then／else／{／! 剝掉才是命令；不在段首的照當參數。"""
    assert rr._shlex_segments("if x; then git status; else git log; fi") == [
        ["x"], ["git", "status"], ["git", "log"], ["fi"]]
    assert rr._shlex_segments("{ git diff; }") == [["git", "diff"], ["}"]]
    assert rr._shlex_segments("git log -- do") == [["git", "log", "--", "do"]]
    assert rr.git_readonly_verdict("for r in a; do git push; done", []).owed is True
    assert rr.git_readonly_verdict("if true; then git status; fi", []).owed is False
    assert {"DOT_GIT_PATH_NOT_GIT_CALL", "SEGMENTS_SPLIT_LIKE_SHELL", "SHELL_KEYWORD_PREFIX_STRIPPED"} <= set(rr.RULES)


def test_008_delete_and_dir_target_rules_registered():
    """DELETE_FORMS_SAME_ACROSS_SHELLS、DIR_TARGET_JUDGED_BY_CONTAINER：判定在 wg_core 掃描器與 wg_overview，案例在
    verify_dir_target_root.py（兩種 shell 的刪除寫法、殘留資料夾放行、專案裡的子資料夾照擋）與 verify_cross_realm_bash_guard.py。"""
    assert "wg_core._scan_segment" in rr.RULES["DELETE_FORMS_SAME_ACROSS_SHELLS"]
    assert "wg_overview.write_target_root" in rr.RULES["DIR_TARGET_JUDGED_BY_CONTAINER"]


def test_008_base_red_tracked_not_owed():
    """BASE_RED_TRACKED_NOT_OWED：三件都對得上才放行；缺一照算紅並說缺哪件；沒有基底紅行對到的紅原樣留著、不附註。"""
    d = rr.parse_base_red("收尾\n基底紅｜test_a：ABCDEF1234 也紅；追蹤 `docs/known red.md:12`\n基底紅｜test_b：沒寫雜湊")
    assert d[0]["item"] == "test_a" and d[0]["base"] == "abcdef1234" and d[0]["tracking"] == "docs/known red.md"
    assert d[1]["base"] == "" and d[1]["tracking"] == ""
    assert rr.parse_base_red("基底紅｜test_a：abcdef1 也紅；追蹤｜x/t.md")[0]["tracking"] == "x/t.md"
    unit_a, unit_b = "t.py::test_a", "t.py::test_b"
    red = {"cmd": "pytest t.py", "summary": f"FAILED {unit_a} - x\nFAILED {unit_b} - y", "cwd": "C:/r"}
    runs = [{"clean": True, "head": "abcdef1234" + "0" * 30, "units": [unit_a, unit_b]}]
    track = {"k.md": {"exists": True, "doc": True, "own_edit": False, "text": "test_a test_b 基底就紅"}}
    both = rr.parse_base_red("基底紅｜test_a：abcdef1234 也紅；追蹤 k.md\n基底紅｜test_b：abcdef1234 也紅；追蹤 k.md")
    ok = {"runs": runs, "ancestry": {("abcdef1234", "C:/r"): True}, "own_shas": [], "base_times": {"abcdef1234": 100.0},
          "started": 200.0, "tracking": track}
    kept, based, notes = rr.base_red_failures([red], both, ok)
    assert not kept and not notes and [r["unit"] for r in based[0][1]] == [unit_a, unit_b]
    kept, based, notes = rr.base_red_failures([red], both[:1], ok)                      # 兩支只宣告一支 → 整筆照紅
    assert kept and not based and any("沒有對到它的基底紅行" in n and unit_b in n for n in notes)
    kept, _, notes = rr.base_red_failures([red], both, {**ok, "ancestry": {("abcdef1234", "C:/r"): False}})
    assert kept and any("不是現在 HEAD 的祖先" in n for n in notes)
    kept, _, notes = rr.base_red_failures([red], both, {**ok, "runs": [{**runs[0], "units": [unit_a]}]})   # 基底只紅 a、b 是這次才紅
    assert kept and any(unit_b in n and "沒在基底" in n for n in notes)
    kept, _, notes = rr.base_red_failures([red], both, {**ok, "tracking": {"k.md": {**track["k.md"], "doc": False}}})
    assert kept and any("不是 .md" in n for n in notes)
    unlisted = {"cmd": "pytest t.py", "summary": "1 failed", "cwd": "C:/r"}
    kept, _, notes = rr.base_red_failures([unlisted], rr.parse_base_red("基底紅｜t.py：abcdef1234 也紅；追蹤 k.md"), ok)
    assert kept and any("逐支列得出" in n for n in notes)
    kept, based, notes = rr.base_red_failures([red], [], ok)
    assert kept == [red] and not based and not notes
    other = {"k.md": {**track["k.md"], "text": "known: test_a_other test_b_other"}}         # 只提到名字更長的別支 → 沒點名
    kept, _, notes = rr.base_red_failures([red], both, {**ok, "tracking": other})
    assert kept and any("沒點名 test_a" in n for n in notes)
    for over, why in (({"base_times": {"abcdef1234": 300.0}}, "早於本 session 開始"), ({"base_times": {}}, "查不到時間"),
                      ({"started": None}, "早於本 session 開始"), ({"own_shas": ["ABCDEF1234ffff"]}, "自己提交的")):
        kept, _, notes = rr.base_red_failures([red], both, {**ok, **over})   # 本 session 開始後才有的 commit（自己的 merge）、自己的提交
        assert kept and any(why in n for n in notes), (over, notes)
    assert rr.listed_red_units(f"FAILED {unit_a} - x") == [unit_a] and rr.listed_red_units("1 failed") == []


# ─── 閘的三件設計題：規則名登錄、對照的案例真的在、案例點到規則名 ───
_GATE_DESIGN_CASES = {
    "CHAIN_HEADLESS_KEEPS_DATA_GATES": ("verify_chain_wiring.py",
                                        "test_headless_after_alarm_data_file_blocked_code_file_record_only"),
    "SHELL_READ_COUNTS_LIKE_READ": ("verify_overview_hub.py", "test_shell_read_counts_like_read"),
    "SHELL_WRITE_COMMAND_NOT_A_READ": ("verify_overview_hub.py", "test_shell_write_command_not_a_read"),
    "EPHEMERAL_WRITE_NOTED_ONCE": ("verify_ephemeral_path.py", "test_temp_project_write_not_noted_but_said_once_per_root"),
    "CHAIN_NO_EDIT_NO_EDGE": ("verify_chain_breaker.py", "test_no_edit_actions_between_same_gate_do_not_link"),
    "CHAIN_ABORT_SHOWS_REPLACED_BLOCK": ("verify_chain_wiring.py",
                                         "test_rerun_only_no_alarm_then_edit_alarm_carries_replaced_block"),
    "INJECT_TRIGGER_READ_COUNTED": ("verify_overview_hub.py", "test_inject_trigger_read_counted"),
    "LOCATE_BLOCK_ONCE_PER_USER_TURN": ("verify_overview_hub.py", "test_locate_block_once_per_user_turn"),
    "LOCATE_NOT_IN_THINKING": ("verify_overview_hub.py", "test_locate_deny_says_thinking_is_not_read"),
    "GOAL_VIEW_ONE_LINE": ("verify_need_goal_points.py", "test_goal_view_resend_is_one_line_read_first_then_tree"),
    "LOCATE_EXAMPLE_ONCE_PER_SESSION": ("verify_pull_goal_locate.py", "test_locate_example_full_once_per_session_then_short"),
    "CARD_READ_WITH_EDIT_FILES": ("verify_overview_card_pointer.py", "test_card_read_hint_says_read_edit_files_with_the_card"),
}


@pytest.mark.parametrize("rule", sorted(_GATE_DESIGN_CASES))
def test_gate_design_rules_registered_with_cases(rule):
    case_file, fn = _GATE_DESIGN_CASES[rule]
    text = (Path(__file__).parent / case_file).read_text(encoding="utf-8")
    assert rule in rr.RULES and f"def {fn}(" in text and rule in text, (rule, case_file, fn)
    if rule.startswith("CHAIN_"):
        import wg_chain
        assert rule in wg_chain.RULES                                # 判定在斷路器，兩邊同名


def test_quote_from_user_opened_turn_registered():
    """QUOTE_FROM_USER_OPENED_TURN：判定在 hooks/wg_provenance._turn_quote，案例在 verify_quote_user_turn.py
    （續跑回合、子代理派出的回合、貼上內容、回填同一套）。"""
    assert "wg_provenance._turn_quote" in rr.RULES["QUOTE_FROM_USER_OPENED_TURN"]
    assert (Path(__file__).resolve().parent / "verify_quote_user_turn.py").is_file()


# ─── 需求目標提示減量：規則名登錄、對照的案例真的在、案例點到規則名 ───
_GOAL_REMINDER_CASES = {
    "CRITIQUE_CASES_ONCE_PER_SESSION": ("verify_pull_goal_locate.py", "test_critique_cases_full_once_per_session_then_pointer"),
    "TREE_LINE_IN_HINTS": ("verify_pull_goal_locate.py", "test_hook_prompts_carry_only_current_node_line"),
}


@pytest.mark.parametrize("rule", sorted(_GOAL_REMINDER_CASES))
def test_goal_reminder_rules_registered_with_cases(rule):
    case_file, fn = _GOAL_REMINDER_CASES[rule]
    text = (Path(__file__).parent / case_file).read_text(encoding="utf-8")
    assert rule in rr.RULES and "v6.slim_reminders" in rr.RULES[rule], rule
    assert f"def {fn}(" in text and rule in text, (rule, case_file, fn)


def test_inject_lean_rules_registered_with_cases():
    """CODING_TURN_FULL_ONLY_ON_TRIGGER／POINTER_NO_NAME_ECHO／NO_RESEND_AFTER_RESUME：判定在 hooks/handlers/ups_inject.py，
    案例在 verify_inject_lean.py（每條至少一支、案例檔點到規則名）。"""
    text = (Path(__file__).resolve().parent / "verify_inject_lean.py").read_text(encoding="utf-8")
    for rule, fn in (("CODING_TURN_FULL_ONLY_ON_TRIGGER", "test_coding_turn_full_only_on_trigger"),
                     ("POINTER_NO_NAME_ECHO", "test_cold_line_drops_name_echo"),
                     ("NO_RESEND_AFTER_RESUME", "test_resume_does_not_resend_full_card")):
        assert rule in rr.RULES and rule in text and f"def {fn}(" in text, rule


# ─── 擋訊息與判準卡瘦身、讀到資料檔就先提示：規則名登錄、對照的案例真的在、案例點到規則名 ───
_SLIM_CASES = {
    "DENY_TEXT_SLIM": ("verify_data_file_ask.py", "test_deny_text_slim_rule_fix_and_hit_only"),
    "CARD_FULL_ONCE_PER_SESSION": ("verify_gate_slimming.py", "test_card_full_once_per_session_then_names_only"),
    "DATA_FILE_READ_HINT": ("verify_data_file_ask.py", "test_read_hint_on_first_read_of_data_file"),
}


@pytest.mark.parametrize("rule", sorted(_SLIM_CASES))
def test_slim_rules_registered_with_cases(rule):
    case_file, fn = _SLIM_CASES[rule]
    text = (Path(__file__).parent / case_file).read_text(encoding="utf-8")
    assert rule in rr.RULES and f"def {fn}(" in text and rule in text, (rule, case_file, fn)


@pytest.mark.parametrize("rule", ["READING_PATH_EARLY_START", "TURN_JUDGMENT_PRE_CLOSE", "PICK_ONE_PRE_CLOSE",
                                  "PICK_ONE_WITH_TURN_JUDGMENT", "SECOND_OPINION_BACKGROUND", "SECOND_OPINION_DONE_NOTICE"])
def test_closing_round_rules_cased_in_closing_round(rule):
    """收尾只跑一輪、第二意見背景跑的規則：端到端案例在 verify_closing_round.py（PostToolBatch→Stop）。"""
    assert rule in rr.RULES
    assert rule in (Path(__file__).parent / "verify_closing_round.py").read_text(encoding="utf-8")


@pytest.mark.parametrize("rule", ["CLOSING_RECONCILE_IN_REPORT", "CLOSING_MISSING_PART_HINT", "CLOSING_GOAL_CODING_ONLY",
                                  "CLOSING_CALL_ALL_THREE"])
def test_closing_merge_rules_cased_in_closing_merge(rule):
    """收尾三段一次交齊的規則：端到端案例在 verify_closing_merge.py（PostToolUse→Stop）。"""
    assert rule in rr.RULES
    assert rule in (Path(__file__).parent / "verify_closing_merge.py").read_text(encoding="utf-8")


# ─── 定位與立樹先提示後擋：規則名登錄、對照的案例真的在、案例點到規則名 ───
def test_locate_hint_rule_registered_with_case():
    text = (Path(__file__).parent / "verify_locate_hint.py").read_text(encoding="utf-8")
    fn = "test_locate_hint_on_first_read_of_part_code_file_then_follow_it_no_block"
    assert "LOCATE_HINT_ON_FIRST_READ" in rr.RULES and f"def {fn}(" in text and "LOCATE_HINT_ON_FIRST_READ" in text


# ─── 第二意見看事實觸發：規則名登錄、案例真的在、案例點到規則名 ───
_SO_FACT_CASES = {
    "SECOND_OPINION_FACT_TRIGGER": ("verify_g9_second_opinion.py", "test_fact_trigger_owed_without_completion_words"),
    "SECOND_OPINION_EXIT_FINGERPRINT": ("verify_g9_second_opinion.py", "test_exit_fingerprint_once_per_change_set"),
    "SECOND_OPINION_PRE_CLOSE": ("verify_closing_round.py", "test_so_pre_close_attaches_same_text_then_stop_passes"),
}


@pytest.mark.parametrize("rule", sorted(_SO_FACT_CASES))
def test_so_fact_trigger_rules_registered_with_cases(rule):
    case_file, fn = _SO_FACT_CASES[rule]
    text = (Path(__file__).parent / case_file).read_text(encoding="utf-8")
    assert rule in rr.RULES and f"def {fn}(" in text and rule in text, (rule, case_file, fn)


# ─── 擋或提醒（RULE_MODE）：每條規則有 mode、三類照擋、其餘提醒、總開關關一律照舊 ───
_BLOCK_RULES = ("COMMIT_SMELL_NEW_BLOCKS", "GATE_BYPASS_NEEDS_DECLARATION", "USER_DATA_FILE_NEEDS_DECLARATION",
                "OLD_TEST_CHANGE_NEEDS_DECLARATION", "RED_TEST_BLOCKS_COMPLETION", "CLAIM_FIXED_NEEDS_PASS")
_REMIND_RULES = ("CODE_EDIT_NEEDS_GOAL_TREE", "OVERVIEW_CARD_BEFORE_EDIT", "OVERVIEW_CARD_MISSING", "OVERVIEW_PART_FILES_READ",
                 "COMMIT_GOAL_RECONCILED", "DEFERRAL_OF_DOABLE_WORK", "HARVEST_AT_PHASE_DONE", "HARVEST_ITEM_NEEDS_RECEIPT",
                 "CLOSING_CHECK_REQUIRED", "CLOSING_CHECK_MEMORY_NOT_DEFERRED", "SYNC_REMINDER_UNSYNCED",
                 "SYNC_BLOCK_PENDING_ITEMS", "DEEP_POSTMORTEM_ON_FAILURE", "ATOM_CONSUMPTION_AUDIT",
                 "EVASION_FLAG_NEXT_PROMPT", "CASE_COVERS_CHANGE", "ASK_NEEDS_RECOMMENDATION",
                 "REMIND_ON_PRIOR_RESULT", "GATE_MODE_TABLE")


def test_rule_mode_covers_every_rule_with_block_or_remind():
    """規則 GATE_MODE_TABLE：RULES 的每一條都在 RULE_MODE，值只有 block／remind；沒登的規則名當 block。"""
    assert set(rr.RULE_MODE) == set(rr.RULES)
    assert set(rr.RULE_MODE.values()) <= {rr.BLOCK, rr.REMIND}
    assert rr.mode_of("NOT_A_RULE_NAME") == rr.BLOCK


@pytest.mark.parametrize("rule", _BLOCK_RULES)
def test_three_classes_block_when_v6_on(rule):
    assert rule in rr.RULES and rr.RULE_CLASS[rule] in ("病形", "宣告", "紅測")
    assert rr.gate_mode(rule, True) == rr.BLOCK


@pytest.mark.parametrize("rule", _REMIND_RULES)
def test_other_v6_gates_remind_when_v6_on_and_block_when_off(rule):
    assert rule in rr.RULES
    assert rr.gate_mode(rule, True) == rr.REMIND
    assert rr.gate_mode(rule, False) == rr.BLOCK


def test_out_of_scope_rules_stay_block():
    for rule in ("COMMIT_ORDER_DECISION_ALWAYS_LOGGED", "ORDER_UNTIL_PUSH", "SVN_TEST_BLOCK_OPT_IN"):
        assert rr.RULE_CLASS[rule] == "不在範圍" and rr.gate_mode(rule, True) == rr.BLOCK


def test_hit_mode_follows_letter_main_rule():
    """寫碼查核的字母：(a) 照擋、(d) 提醒，就算擋訊息帶的是判宣稱的共用規則名。"""
    assert rr.hit_mode("a", "CLAIM_WORDS_ARE_HINTS", True) == rr.BLOCK
    assert rr.hit_mode("d", "SAME_FILE", True) == rr.REMIND
    assert rr.hit_mode("d", "SAME_FILE", False) == rr.BLOCK


def test_remind_line_one_line_with_rule_and_fix_and_cap():
    line = rr.remind_line("CASE_COVERS_CHANGE", "改了 a.py\n沒案例", "補 verify_a.py")
    assert line.startswith("[Guardian:提醒] CASE_COVERS_CHANGE：") and "\n" not in line and "做法：補 verify_a.py" in line
    long = rr.remind_line("X", "y" * 500, "z")
    assert len(long) <= rr.REMIND_LINE_CAP and long.endswith("…")


def test_remind_key_and_due_once_per_object():
    k = rr.remind_key("OVERVIEW_CARD_BEFORE_EDIT", r"C:\proj\hooks\a.py")
    assert k == rr.remind_key("OVERVIEW_CARD_BEFORE_EDIT", "c:/proj/hooks/a.py")
    assert rr.remind_due([], "OVERVIEW_CARD_BEFORE_EDIT", "c:/proj/hooks/a.py")
    assert not rr.remind_due([k], "OVERVIEW_CARD_BEFORE_EDIT", "C:/proj/hooks/a.py")
    assert rr.remind_due([k], "OVERVIEW_CARD_BEFORE_EDIT", "c:/proj/hooks/b.py")
    assert rr.remind_key("HARVEST_AT_PHASE_DONE") == "HARVEST_AT_PHASE_DONE|"


# ─── 工具前守門改提醒（P2～P10d）登的規則名：送法在表上、對象鍵一 session 一次（送法案例在 verify_gate_mode_pre.py） ───

def test_pre_gate_remind_rules_registered_with_mode():
    """LOCATE_BEFORE_EDIT 與 REMIND_PENDING_IN_STATE 是 v6 守門（remind）；OVERVIEW_READONLY_PATHS 不在範圍（block）；
    v6 關全部 block。"""
    for rule in ("LOCATE_BEFORE_EDIT", "REMIND_PENDING_IN_STATE", "OVERVIEW_CARD_BEFORE_EDIT", "CODE_EDIT_NEEDS_GOAL_TREE",
                 "COMMIT_GOAL_RECONCILED", "UNMAPPED_FIRST_EDIT_NEEDS_MIN_MAP", "ASK_NEEDS_RECOMMENDATION", "GATE_SELF_ERROR"):
        assert rule in rr.RULES and rr.gate_mode(rule, True) == rr.REMIND and rr.gate_mode(rule, False) == rr.BLOCK, rule
    assert rr.RULE_CLASS["OVERVIEW_READONLY_PATHS"] == "不在範圍" and rr.gate_mode("OVERVIEW_READONLY_PATHS", True) == rr.BLOCK
    assert rr.remind_key("LOCATE_BEFORE_EDIT", "戰鬥") == "LOCATE_BEFORE_EDIT|戰鬥"
# ─── 收尾改提醒：Stop 只留帳（STOP_REMIND_LEDGER_ONLY）、(f2) 交付前對照（GOAL_RECONCILE_AT_DELIVERY）；入口案例在 verify_gate_mode_stop.py ───
@pytest.mark.parametrize("rule", ("STOP_REMIND_LEDGER_ONLY", "GOAL_RECONCILE_AT_DELIVERY", "TURN_JUDGMENT_REQUIRED",
                                  "SECOND_OPINION_REQUIRED", "REFACTOR_NEEDS_EQUIVALENCE", "LEFTOVER_NEEDS_CLEANUP",
                                  "RELOAD_ADVICE_ALREADY_LOADED", "SCOPE_DECLARED_FOR_CHANGE", "AEC_EVIDENCE_PATH",
                                  "EDITED_PART_NEEDS_GOAL_NODE", "KNOWLEDGE_EDIT_NEEDS_LIGHT_TREE", "GATE_SELF_ERROR"))
def test_stop_remind_rules_are_remind_when_v6_on(rule):
    """Stop 改提醒的那幾道閘：規則名在表上、v6 開是 remind、關是 block（照舊）；(a)（CLAIM_FIXED_NEEDS_PASS）照擋見上面的三類案。"""
    assert rule in rr.RULES and rr.gate_mode(rule, True) == rr.REMIND and rr.gate_mode(rule, False) == rr.BLOCK
    assert (Path(__file__).parent / "verify_gate_mode_stop.py").is_file()


def test_overview_hub_under_v6_rule_registered():
    assert "OVERVIEW_HUB_UNDER_V6" in rr.RULES and rr.gate_mode("OVERVIEW_HUB_UNDER_V6", True) == rr.REMIND


def test_locate_first_edit_blocks_once_rule_registered():
    """第一次改擋一次：規則登了、v6 開仍是 block（不在三類，但也不是提醒）。"""
    assert "LOCATE_FIRST_EDIT_BLOCKS_ONCE" in rr.RULES and rr.gate_mode("LOCATE_FIRST_EDIT_BLOCKS_ONCE", True) == rr.BLOCK
# ─── 目標樹只立一次（GOAL_TREE_SET_ONCE）：v6 守門（remind）、判定不動；改檔那則與 Stop 的行為案例在 verify_goal_tree_once.py ───
def test_goal_tree_set_once_registered_and_noted():
    """規則登在表上、v6 開是 remind、關是 block；被它改掉送法的那幾條說明都補了現況，而且是在 RULE_MODE 算完之後補（不影響送法表）。"""
    assert "GOAL_TREE_SET_ONCE" in rr.RULES and rr.gate_mode("GOAL_TREE_SET_ONCE", True) == rr.REMIND
    assert rr.gate_mode("GOAL_TREE_SET_ONCE", False) == rr.BLOCK
    for rule in ("SCOPE_DECLARED_FOR_CHANGE", "GOAL_RECONCILE_AT_DELIVERY", "EDITED_PART_NEEDS_GOAL_NODE",
                 "KNOWLEDGE_TREE_RECONCILE_AT_DELIVERY", "CODE_EDIT_NEEDS_GOAL_TREE", "CLOSING_CHECK_REQUIRED"):
        assert "GOAL_TREE_SET_ONCE" in rr.RULES[rule], rule
        assert rr.gate_mode(rule, True) == rr.REMIND and rr.gate_mode(rule, False) == rr.BLOCK, rule
    assert (Path(__file__).parent / "verify_goal_tree_once.py").is_file()

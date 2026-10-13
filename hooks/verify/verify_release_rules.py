"""verify_release_rules.py：hooks/wg_release_rules.py 每條規則的會紅案例（045 track-gate-rules；044 的案例由 track-e8 以 test_044_ 併入）。

怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_release_rules.py
每條規則至少兩案：誠實流程過得了、繞過寫法過不了。守門案 test_every_rule_has_a_case：RULES 每個名字都要在本檔出現。
退回 main（沒有模組）→ import 紅；退回只有 044 草稿 → 045 的每個 test_045_ 紅在 AttributeError／斷言。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS_DIR))

import wg_release_rules as rr  # noqa: E402

THIS = Path(__file__).read_text(encoding="utf-8")


def test_every_rule_has_a_case():
    """守門：RULES 每個規則名都要在本檔以 "名字" 或 _名字小寫 出現。"""
    missing = [n for n in rr.RULES if f'"{n}"' not in THIS and f"_{n.lower()}" not in THIS]
    assert not missing, f"沒有案例的規則：{missing}"


# ─── 044 基底規則的最小案（track-e8 的完整案例以 test_044_ 併入；這裡只保守門） ──

def test_045_base_same_file_and_turn_since_user_prompt():
    assert rr.same_file(r"C:\P\a\..\X.py", "c:/p/x.py")                        # SAME_FILE
    assert rr.in_turn(5, 7, since=4) and not rr.in_turn(3, 7, since=4)        # TURN_SINCE_USER_PROMPT
    assert rr.user_turn({"turn_prompts_seq": 4}, 7) == 4 and rr.user_turn({}, 7) == 7
    assert rr.turn_start(5, "sid#agent:a", [{"turn_seq": 2}]) == 2


def test_045_base_claim_modifier_excluded_region_gone_and_owed():
    assert rr.claim_is_modifier("換上修好的 probe", 4) and not rr.claim_is_modifier("我修好了。", 4)   # "CLAIM_MODIFIER_NOT_OWN"
    assert rr.excluded_region("C:/p/workflow/v6-inbox/a.py", ["workflow/v6-inbox/*"], "C:/p")       # "EXCLUDED_REGION"
    assert rr.gone_verdict("x.py", None).rule == "GONE_OUTSIDE_VCS"
    assert rr.gone_verdict("x.py", "git").rule == "GONE_IN_GIT_NOTHING_NEW"
    assert rr.gone_verdict("x.py", "git", ["y.py"]).rule == "MOVED_NEW_CODE_SEEN"
    assert rr.gone_verdict("x.py", "svn").rule == "GONE_UNVERIFIABLE"
    assert rr.owed_after_last_case("x.py", "verify_x.py").owed is True
    assert "SNAPSHOT_SETTLED" in rr.RULES and "NET_UNCHANGED" in rr.RULES         # 判定在 wg_verify_ledger，案在 verify_stop_reconcile
    assert "SAME_FILE" in rr.RULES and "TURN_SINCE_USER_PROMPT" in rr.RULES


# ─── 擋訊息格式（契約） ───────────────────────────────────────────────────────

def test_045_format_hit_and_parse_hits_roundtrip():
    v = rr.Verdict("OWED_AFTER_LAST_CASE", True, "x.py 改過", ("最後一次改的案例是 verify_x.py", "x.py 在那之後還改過"))
    line = rr.format_hit("d", v)
    assert line.startswith("✗ (d) OWED_AFTER_LAST_CASE：x.py 改過｜證據：")
    assert "；" in line and "verify_x.py" in line
    text = "[Guardian:ReconcileGate] 頭\n  " + rr.format_hit("a", rr.Verdict("PASS_MISSING", True, "沒 PASS")) + "\n  " + line
    assert rr.parse_hits(text) == ["a", "d"]
    assert rr.parse_hit_rules(text) == [("a", "PASS_MISSING"), ("d", "OWED_AFTER_LAST_CASE")]


def test_045_format_hit_without_evidence_uses_why():
    assert rr.format_hit("c", rr.Verdict("R", True, "沒跑")).endswith("｜證據：沒跑")


def test_045_legacy_letters_have_rule_names():
    for n in ("CLAIM_FIXED_NEEDS_PASS", "CLAIM_MEASURED_NEEDS_DONE", "CLAIM_TRIED_NEEDS_EXEC", "AEC_EVIDENCE_PATH",
              "AEC_FOLLOWUPS_EMPTY", "MEASURE_RULER_NOT_RUN"):
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
    text = "頭\n  ✗ (a) PASS_MISSING：沒 PASS｜證據：x\n  ✗ (d) OWED_AFTER_LAST_CASE：欠｜證據：y"
    assert rr.exhausted_summary(text) == "(a) PASS_MISSING；(d) OWED_AFTER_LAST_CASE"


def test_045_block_budget_per_rule_new_turn_resets_and_legacy_record_is_conservative():
    rec = rr.budget_tick(None, 7, ["d", "d"])
    assert rr.budget_counts(rec, 8) == {}
    legacy = {"turn": 7, "count": 2}                                 # 升級前整場一個 count：每條都當已擋 2 次（不因升級多放）
    assert rr.budget_exhausted(legacy, 7, 2, ["a", "d"]) == ["a", "d"]
    assert rr.budget_tick(legacy, 7, ["a"])["count"] == 3


# ─── B1 CASE_GREEN_AFTER_EDIT ──────────────────────────────────────────────────

def test_045_case_green_after_edit_verdict_and_cmd_names_file():
    v = rr.green_after_edit_verdict("x.py", "verify_x.py", "python -m pytest -q hooks/verify/verify_x.py", "2026-10-13T10:00:00")
    assert v.rule == "CASE_GREEN_AFTER_EDIT" and v.owed is False and len(v.evidence) == 2
    assert rr.cmd_names_file("python -m pytest -q hooks/verify/verify_x.py", r"c:\p\hooks\verify\verify_x.py")
    assert rr.cmd_names_file("pytest hooks/verify/verify_x.py::test_a", "verify_x.py")
    assert not rr.cmd_names_file("pytest hooks/verify/verify_xy.py", "verify_x.py")     # 整詞：verify_xy 不是 verify_x
    assert not rr.cmd_names_file("pytest hooks/verify", "verify_x.py")


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
    assert rr.committed_refs([], refs, committed_since_edit=False) == ["HEAD", "MERGE_HEAD", "main"]
    assert rr.committed_refs([], refs, committed_since_edit=True) == ["MERGE_HEAD", "main"]
    assert rr.committed_refs(["mm"], refs, committed_since_edit=True) == ["MERGE_HEAD"]      # main 指到自己提交的 → 不算
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
])
def test_045_inline_py_readonly_denies_writes_and_unknowns(code):
    v = rr.inline_python_verdict(code)
    assert v.owed is True and v.rule == "INLINE_PY_READONLY" and v.why


def test_045_inline_code_hint_points_the_way():
    assert "腳本檔" in rr.inline_code_hint("node") and "json.tool" in rr.inline_code_hint("python")
    assert ".ps1" in rr.inline_code_hint("pwsh")


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
    assert rr.is_temp_path(r"C:\Users\HOLYLI~1\AppData\Local\Temp\claude\scratchpad\x", roots)   # 短路徑含 scratchpad 片段
    assert not rr.is_temp_path(r"C:\Users\me\AppData\Local\Temp\..\..\..\.claude\hooks\x.py", roots)
    assert not rr.is_temp_path(r"C:\Users\me\.claude-wt\track-x\hooks\x.py", roots)
    assert rr.temp_commit_verdict(r"C:\Users\me\AppData\Local\Temp\claude\s\repo", roots).owed is False
    assert rr.temp_commit_verdict(r"C:\Users\me\.claude", roots).owed is True
    assert rr.temp_copy_verdict("/tmp/x/tools/x.py", roots).owed is False
    assert rr.temp_copy_verdict(r"C:\Users\me\.claude-wt\t\tools\x.py", roots).owed is True


# ─── B10 DPM_WORKTREE_DELIVERY ─────────────────────────────────────────────────

def test_045_dpm_worktree_delivery_text():
    wt = rr.dpm_instruction_text("失敗中反覆重試", True)
    live = rr.dpm_instruction_text("失敗中反覆重試", False)
    assert "DPM_WORKTREE_DELIVERY" in wt and "交付信" in wt and "請用 atom_write" not in wt
    assert "atom_write" in live and "交付信" not in live
    assert "防再犯" in wt and "防再犯" in live


# ─── C1 RED_WHILE_REVERTED ／ RETRY_IS_RED_AGAIN ／ GREEN_SAME_CASE_CLEARS ─────

def test_045_red_while_reverted_verdicts():
    v = rr.deliberate_red_verdict([("x.py", "main")])
    assert v.owed is False and "main" in v.why and v.evidence == ("x.py == main",)
    assert rr.deliberate_red_verdict([]).owed is True


def test_045_retry_counts_edits_since_red():
    assert rr.retry_bump(1, 2) is False                                      # 紅之後第一次改：修，不是重試
    assert rr.retry_bump(2, 2) is True and rr.retry_bump(3, 2) is True       # 第二次起每次都算
    assert rr.retry_bump(3, 4) is False                                      # plan 模式門檻 4


def test_045_green_same_case_clears():
    assert rr.green_clears_red("python hooks/verify/verify_x.py", "python -X utf8 hooks/verify/verify_x.py && echo ok")
    assert rr.green_clears_red("pytest hooks/verify/verify_x.py::test_a", r"python -m pytest -q hooks\verify\verify_x.py")
    assert not rr.green_clears_red("pytest hooks/verify/verify_x.py", "pytest hooks/verify/verify_y.py")
    assert not rr.green_clears_red("pytest", "pytest -q")                     # 都沒點名檔：交給既有規則
    assert rr.case_files_in_cmd("python a/b.py c.PY") == ["b.py", "c.py"]

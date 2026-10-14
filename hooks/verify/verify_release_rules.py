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
    assert rr.excluded_region(r"c:\proj\workflow\v6-inbox\x\a.py", r"c:\proj", "knowledge")
    assert not rr.excluded_region(r"c:\proj\tools\a.py", r"c:\proj", "code")
    assert not rr.excluded_region(r"c:\proj\workflow\v6-inbox\a.py", r"c:\proj", None)
    assert not rr.excluded_region(r"c:\proj\workflow\v6-inbox\..\..\..\src\a.py", r"c:\proj", "knowledge")   # `..` 繞出根
    assert not rr.excluded_region(r"c:\proj\workflow\v6-inbox\a.py", None, "knowledge")
    assert not rr.excluded_region(r"c:\other\_AIDocs\a.py", r"c:\proj", "knowledge")


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


# ═══ 045（track-gate-rules）：清冊 B／C 組規則的案例 ═══

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
    assert rr.exhausted_summary(text) == "✗ (a) PASS_MISSING；✗ (d) OWED_AFTER_LAST_CASE"


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

def test_045_dispatch_opens_turn_only_for_dispatch_marked_peer_messages():
    assert rr.is_dispatch_message(["派工：045 B 組規則，派工單在 workflow/v6-inbox/to-track-x/001-prompt.md"])
    assert rr.is_dispatch_message(["【派工】接續單"])
    assert rr.is_dispatch_message(["派工單在 C:\\Users\\me\\.claude\\workflow\\v6-inbox\\to-track-gate-rules\\000-prompt.md，照做"])   # 首行含派工＋路徑
    # codex 001 BLOCK 7：正文其他地方引用派工單路徑（交付、進度、審查通知）不算派工
    assert not rr.is_dispatch_message(["已完成，交付依據 to-track-gate-rules/001-prompt.md；請審查結果。"])
    assert not rr.is_dispatch_message(["主旨與其他字\n看 C:\\Users\\me\\.claude\\workflow\\v6-inbox\\to-track-gate-rules\\000-prompt.md 照做"])
    assert not rr.is_dispatch_message(["對帳過了，上GIT"])                                   # 一般同伴訊息
    assert not rr.is_dispatch_message(["from-track-a6/006-false-block.md 收到"])          # from-track 是交付，不是派工
    assert not rr.is_dispatch_message([]) and not rr.is_dispatch_message([""])


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

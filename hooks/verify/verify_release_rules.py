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


def test_045_retry_counts_edits_since_red():
    assert rr.retry_bump(1, 2) is False                                      # 紅之後第一次改：修，不是重試
    assert rr.retry_bump(2, 2) is True and rr.retry_bump(3, 2) is True       # 第二次起每次都算
    assert rr.retry_bump(3, 4) is False                                      # plan 模式門檻 4


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

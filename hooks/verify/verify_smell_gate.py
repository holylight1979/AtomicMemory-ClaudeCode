"""verify_smell_gate.py — commit 前病形閘（G2：帶病的改動上不了版）。

驗證 handlers/pre_tool_use.check_smell_gate 與 tools/project-smells.py 的 commit 前病形檢查：
  - 查的是「這次真的會進版的內容」：暫存區、`git commit -a` 的已追蹤改動、`git commit <路徑>`、同一條指令前面
    `git add` 才要加進來的檔（PreToolUse 時 add 還沒跑）、svn commit 的工作副本改動；不看本 session 改了哪些檔
  - 新寫進的病 → 擋，訊息點名病名、檔、行號與那一行；舊碼原本就有、這次沒碰的 → 不擋、只列出；同一行原樣搬動不算新病
  - 內建病形：匿名函式疊用（本體裡再套匿名函式；並列的不算）、匿名回呼套三層以上、只有建構子加一個方法的類別；
    字串與註解裡的字不算；C# switch 運算式的 `=>` 不算匿名函式；測試檔的單方法類別是替身不算
  - 專案部位表「病灶清單」欄指的病灶文件，每條 `shape:` 當 regex 掃新寫進的行，病名取「症狀」欄
  - 那一行寫 `smell-ok: <理由>` → 不擋、列在放行清單；沒寫理由不算
  - 只看程式檔（現行程式副檔名清單）；拆不出 commit 落點（包在 bash -c 裡）→ 判不了一律擋
git／svn 子程序走錄製重播（lib/git_cassette.py）；改了呼叫 git 的方式要 `pytest --git-record` 重錄。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_smell_gate.py
"""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
TREE = HOOKS_DIR.parent
sys.path.insert(0, str(HOOKS_DIR))

from handlers.pre_tool_use import check_smell_gate  # noqa: E402


def _load_smells():
    spec = importlib.util.spec_from_file_location("project_smells", TREE / "tools" / "project-smells.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["project_smells"] = mod
    spec.loader.exec_module(mod)
    return mod


ps = _load_smells()


@pytest.fixture(autouse=True)
def _cassette(git_cassette, monkeypatch):
    monkeypatch.setitem(sys.modules, "project_smells", ps)     # hook 端拿的是同一個模組（別的測試檔也會註冊自己那份）
    monkeypatch.setattr(ps, "_hub_inputs", lambda: ({}, None))
    git_cassette()


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "core.autocrlf=false", *args],
                          cwd=str(repo), capture_output=True, text=True, encoding="utf-8", check=True)


def _repo(tmp_path: Path, files: dict) -> Path:
    repo = tmp_path / "proj"
    repo.mkdir()
    _git(repo, "init", "-q")
    for rel, text in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
    if files:
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "base")
    return repo


def _write(repo: Path, rel: str, text: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")


def _gate(repo: Path, command: str):
    return check_smell_gate("Bash", {"command": command}, str(repo), {})


CLEAN_PY = "def f(a):\n    return sorted(a, key=lambda p: p[0])\n"
STACKED = "x = sorted(a, key=lambda p: g(lambda q: q))\n"


# ─── 擋新病、點名 ─────────────────────────────────────────────────

def test_new_stacked_lambda_in_staged_change_is_blocked(tmp_path):
    repo = _repo(tmp_path, {"src/a.py": CLEAN_PY})
    _write(repo, "src/a.py", CLEAN_PY + STACKED)
    _git(repo, "add", "src/a.py")
    deny, _advice = _gate(repo, 'git commit -m "x"')
    assert deny and "匿名函式疊用" in deny
    assert "src/a.py" in deny and "第 3 行" in deny and "lambda q: q" in deny


def test_single_idiomatic_lambda_is_not_a_smell(tmp_path):
    repo = _repo(tmp_path, {"src/a.py": "x = 1\n"})
    _write(repo, "src/a.py", CLEAN_PY)
    _git(repo, "add", "src/a.py")
    deny, _advice = _gate(repo, 'git commit -m "x"')
    assert deny is None


def test_old_untouched_smell_listed_not_blocked(tmp_path):
    repo = _repo(tmp_path, {"src/a.py": STACKED + "y = 1\n"})
    _write(repo, "src/a.py", STACKED + "y = 2\n")
    _git(repo, "add", "src/a.py")
    deny, advice = _gate(repo, 'git commit -m "x"')
    assert deny is None
    assert advice and "舊碼原本就有" in advice and "src/a.py" in advice and "第 1 行" in advice


def test_moved_line_is_not_a_new_smell(tmp_path):
    repo = _repo(tmp_path, {"src/a.py": STACKED + "y = 1\nz = 2\n"})
    _write(repo, "src/a.py", "y = 1\nz = 2\n" + STACKED)
    _git(repo, "add", "src/a.py")
    deny, _advice = _gate(repo, 'git commit -m "x"')
    assert deny is None


def test_file_added_by_git_add_in_same_command_is_checked(tmp_path):
    """PreToolUse 時前面的 git add 還沒跑：要把它要加進來的檔算進這次的提交（未追蹤的新檔也算）。"""
    repo = _repo(tmp_path, {"src/a.py": CLEAN_PY})
    _write(repo, "src/new.py", STACKED)
    assert _git(repo, "diff", "--cached", "--name-only").stdout == ""      # 前置：暫存區是空的
    deny, _advice = _gate(repo, f'cd "{repo}" && git add src/new.py && git commit -m "x"')
    assert deny and "src/new.py" in deny


def test_commit_all_flag_includes_tracked_unstaged(tmp_path):
    repo = _repo(tmp_path, {"src/a.py": CLEAN_PY})
    _write(repo, "src/a.py", CLEAN_PY + STACKED)
    assert _gate(repo, 'git commit -m "x"')[0] is None       # 沒暫存、不帶 -a：這次什麼都不會進版
    deny, _advice = _gate(repo, 'git commit -am "x"')
    assert deny and "src/a.py" in deny


def test_commit_with_pathspec_checks_those_paths(tmp_path):
    repo = _repo(tmp_path, {"src/a.py": CLEAN_PY, "src/b.py": CLEAN_PY})
    _write(repo, "src/a.py", CLEAN_PY + STACKED)
    _write(repo, "src/b.py", CLEAN_PY + "z = 3\n")
    assert _gate(repo, 'git commit -m "x" src/b.py')[0] is None
    deny, _advice = _gate(repo, 'git commit -m "x" -- src/a.py')
    assert deny and "src/a.py" in deny


# ─── Codex 審查補的漏洞（10-20）──────────────────────────────────

def test_smell_formed_by_editing_another_line_is_new(tmp_path):
    """病形的錨點行沒改、改的是同一個病形的另一行（外層 lambda 那行）→ 仍是新寫進的。"""
    repo = _repo(tmp_path, {"src/a.py": "f = (\n    lambda x: x\n)\n"})
    _write(repo, "src/a.py", "f = lambda y: (\n    lambda x: x\n)\n")
    _git(repo, "add", "src/a.py")
    deny, _advice = _gate(repo, 'git commit -m "x"')
    assert deny and "匿名函式疊用" in deny


def test_copying_an_existing_smell_line_is_new(tmp_path):
    """舊版有一行病碼、原行保留再複製一份 → 多出來的那份是新寫進的（不能當搬動）。"""
    repo = _repo(tmp_path, {"src/a.py": STACKED})
    _write(repo, "src/a.py", STACKED + "y = 1\n" + STACKED)
    _git(repo, "add", "src/a.py")
    deny, _advice = _gate(repo, 'git commit -m "x"')
    assert deny and "第 3 行" in deny


def test_too_many_files_is_blocked_not_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(ps, "MAX_COMMIT_FILES", 1)
    repo = _repo(tmp_path, {"src/a.py": "x = 1\n"})
    _write(repo, "src/b.py", "y = 1\n")
    _write(repo, "src/c.py", "z = 1\n")
    _git(repo, "add", "-A")
    deny, _advice = _gate(repo, 'git commit -m "x"')
    assert deny and "拆" in deny


def test_cjk_file_name_is_checked(tmp_path):
    """git 預設 core.quotePath=true 會把中文檔名輸出成帶引號的八進位跳脫；要用 -z 拿到真檔名。"""
    repo = _repo(tmp_path, {"src/a.py": "x = 1\n"})
    _git(repo, "config", "core.quotePath", "true")         # 本機全域可能設成 false，這裡釘回預設值
    _write(repo, "src/計算.py", STACKED)
    _git(repo, "add", "-A")
    deny, _advice = _gate(repo, 'git commit -m "x"')
    assert deny and "src/計算.py" in deny


def test_pathspec_from_file_cannot_be_judged(tmp_path):
    repo = _repo(tmp_path, {"src/a.py": "x = 1\n"})
    deny, _advice = _gate(repo, 'git commit --pathspec-from-file=paths.txt -m "x"')
    assert deny and "判不了" in deny


def test_git_dir_override_cannot_be_judged(tmp_path):
    repo = _repo(tmp_path, {"src/a.py": "x = 1\n"})
    deny, _advice = _gate(repo, f'git --git-dir="{repo}/.git" --work-tree="{repo}" commit -m "x"')
    assert deny and "判不了" in deny


def test_git_add_restoring_head_content_drops_staged_smell(tmp_path):
    """暫存區有病碼、工作樹已改回 HEAD：`git add a.py` 會把暫存區改回乾淨，這次不會提交病碼。"""
    repo = _repo(tmp_path, {"src/a.py": CLEAN_PY})
    _write(repo, "src/a.py", CLEAN_PY + STACKED)
    _git(repo, "add", "src/a.py")
    _write(repo, "src/a.py", CLEAN_PY)
    assert _gate(repo, 'git commit -m "x"')[0]                                 # 前置：只看暫存區會擋
    assert _gate(repo, 'git add src/a.py && git commit -m "x"')[0] is None


def test_commit_all_with_deleted_worktree_file_drops_staged_smell(tmp_path):
    repo = _repo(tmp_path, {"src/a.py": CLEAN_PY})
    _write(repo, "src/a.py", CLEAN_PY + STACKED)
    _git(repo, "add", "src/a.py")
    (repo / "src" / "a.py").unlink()
    assert _gate(repo, 'git commit -am "x"')[0] is None


# ─── 內建病形的精準度 ─────────────────────────────────────────────

def test_lambda_words_in_strings_and_comments_are_not_smells(tmp_path):
    repo = _repo(tmp_path, {"src/a.py": "x = 1\n"})
    _write(repo, "src/a.py", 'x = "lambda a: lambda b: b"  # lambda lambda\n')
    _git(repo, "add", "src/a.py")
    assert _gate(repo, 'git commit -m "x"')[0] is None


def test_nested_lambda_across_lines_is_blocked(tmp_path):
    repo = _repo(tmp_path, {"src/a.py": "x = 1\n"})
    _write(repo, "src/a.py", "h = lambda a: (\n    lambda b: a + b\n)\n")
    _git(repo, "add", "src/a.py")
    deny, _advice = _gate(repo, 'git commit -m "x"')
    assert deny and "匿名函式疊用" in deny


JS_NEST3 = ("load(function (a) {\n"
            "  parse(a, function (b) {\n"
            "    save(b, (c) => {\n"
            "      done(c);\n"
            "    });\n"
            "  });\n"
            "});\n")
JS_NEST2 = ("load(function (a) {\n"
            "  parse(a, (b) => {\n"
            "    done(b);\n"
            "  });\n"
            "});\n")


def test_callback_nested_three_levels_is_blocked(tmp_path):
    repo = _repo(tmp_path, {"web/app.js": "var x = 1;\n"})
    _write(repo, "web/app.js", JS_NEST3)
    _git(repo, "add", "web/app.js")
    deny, _advice = _gate(repo, 'git commit -m "x"')
    assert deny and "匿名回呼套三層以上" in deny and "第 3 行" in deny


def test_callback_nested_two_levels_is_fine(tmp_path):
    repo = _repo(tmp_path, {"web/app.js": "var x = 1;\n"})
    _write(repo, "web/app.js", JS_NEST2)
    _git(repo, "add", "web/app.js")
    assert _gate(repo, 'git commit -m "x"')[0] is None


def test_csharp_switch_expression_arrows_are_not_lambdas(tmp_path):
    repo = _repo(tmp_path, {"Game/A.cs": "class A {}\n"})
    _write(repo, "Game/A.cs", 'class A { string N(int x) => x switch { 1 => "a", _ => "b" }; }\n')
    _git(repo, "add", "Game/A.cs")
    assert _gate(repo, 'git commit -m "x"')[0] is None


def test_csharp_stacked_lambdas_blocked(tmp_path):
    repo = _repo(tmp_path, {"Game/A.cs": "class A {}\n"})
    _write(repo, "Game/A.cs", "class A { void F() { list.ForEach(x => x.Items.ForEach(y => Use(y))); } }\n")
    _git(repo, "add", "Game/A.cs")
    deny, _advice = _gate(repo, 'git commit -m "x"')
    assert deny and "Game/A.cs" in deny


def test_sibling_lambdas_on_one_line_are_not_stacked(tmp_path):
    """並列的匿名函式（LINQ 串接、一排替身）不是疊用；只有本體裡再套的才算（10-20 校準：全 repo 53 筆並列誤命中）。"""
    repo = _repo(tmp_path, {"Game/A.cs": "class A {}\n", "src/a.py": "x = 1\n"})
    _write(repo, "Game/A.cs", "class A { void F() { var q = rows.Where(r => r.Ok).OrderBy(r => r.Id).ToList(); } }\n")
    _write(repo, "src/a.py", 'fakes = {"a": lambda x: None, "b": lambda *a: [], "c": lambda: 0}\n')
    _git(repo, "add", "-A")
    assert _gate(repo, 'git commit -m "x"')[0] is None


def test_js_multiline_template_string_is_not_code(tmp_path):
    repo = _repo(tmp_path, {"web/page.js": "var x = 1;\n"})
    _write(repo, "web/page.js", "a(() => {\n  b(() => {\n    const html = `\n      <script>c(() => { d(); })</script>\n    `;\n  });\n});\n")
    _git(repo, "add", "web/page.js")
    assert _gate(repo, 'git commit -m "x"')[0] is None


ONE_METHOD = ("class Runner:\n"
              "    def __init__(self, cfg):\n"
              "        self.cfg = cfg\n"
              "\n"
              "    def run(self):\n"
              "        return self.cfg\n")


def test_one_method_class_is_blocked(tmp_path):
    repo = _repo(tmp_path, {"src/a.py": "x = 1\n"})
    _write(repo, "src/a.py", ONE_METHOD)
    _git(repo, "add", "src/a.py")
    deny, _advice = _gate(repo, 'git commit -m "x"')
    assert deny and "只有建構子加一個方法的類別" in deny and "第 1 行" in deny


def test_one_method_class_with_base_is_fine(tmp_path):
    repo = _repo(tmp_path, {"src/a.py": "x = 1\n"})
    _write(repo, "src/a.py", ONE_METHOD.replace("class Runner:", "class Runner(Base):"))
    _git(repo, "add", "src/a.py")
    assert _gate(repo, 'git commit -m "x"')[0] is None


def test_one_method_class_in_test_file_is_a_test_double(tmp_path):
    repo = _repo(tmp_path, {"tests/test_a.py": "x = 1\n"})
    _write(repo, "tests/test_a.py", ONE_METHOD.replace("Runner", "_FakeRunner"))
    _git(repo, "add", "tests/test_a.py")
    assert _gate(repo, 'git commit -m "x"')[0] is None


def test_non_code_file_is_ignored(tmp_path):
    repo = _repo(tmp_path, {"docs/a.md": "x\n"})
    _write(repo, "docs/a.md", STACKED)
    _git(repo, "add", "docs/a.md")
    assert _gate(repo, 'git commit -m "x"') == (None, None)


def test_windows_batch_file_is_code(tmp_path):
    """.bat／.cmd 算程式（10-20 定）：專案病灶清單的形狀會掃到它。"""
    repo = _repo(tmp_path, {"scripts/run.bat": "@echo off\n"})
    _map(repo, "goto\\s+:eof")
    _write(repo, "scripts/run.bat", "@echo off\ngoto :eof\n")
    _git(repo, "add", "scripts/run.bat")
    deny, _advice = _gate(repo, 'git commit -m "x"')
    assert deny and "scripts/run.bat" in deny


# ─── 專案病灶清單 ─────────────────────────────────────────────────

def _map(repo: Path, shape: str) -> None:
    _write(repo, ".claude/overview-map.md",
           "| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 病灶清單 |\n|---|---|---|---|---|\n"
           "| `src/` | 程式 | 無 | 無 | `docs/defects.md` |\n"
           "| `scripts/` | 腳本 | 無 | 無 | `docs/defects.md` |\n")
    _write(repo, "docs/defects.md",
           "| 位置 | 症狀 | 根因 | 修法 | 狀態 | 規格 | 形狀 |\n|---|---|---|---|---|---|---|\n"
           f"| `src/` | 吞掉例外 | 沒人擁有錯誤路徑 | 明寫錯誤訊號 | 未修 | 待規格：錯誤碼表未定 | `shape: {shape}` |\n")


def test_defects_doc_shape_names_the_symptom(tmp_path):
    repo = _repo(tmp_path, {"src/a.py": "x = 1\n"})
    _map(repo, "except\\s*:\\s*pass\\b")
    _write(repo, "src/a.py", "x = 1\ntry:\n    f()\nexcept: pass\n")
    _git(repo, "add", "src/a.py")
    deny, _advice = _gate(repo, 'git commit -m "x"')
    assert deny and "吞掉例外" in deny and "第 4 行" in deny


# ─── 介入入口 ─────────────────────────────────────────────────────

def test_smell_ok_with_reason_passes_and_is_listed(tmp_path):
    repo = _repo(tmp_path, {"src/a.py": "x = 1\n"})
    _write(repo, "src/a.py", STACKED.rstrip("\n") + "  # smell-ok: 第三方 API 只收巢狀回呼\n")
    _git(repo, "add", "src/a.py")
    deny, advice = _gate(repo, 'git commit -m "x"')
    assert deny is None and advice and "smell-ok" in advice and "第三方 API" in advice


def test_smell_ok_without_reason_still_blocked(tmp_path):
    repo = _repo(tmp_path, {"src/a.py": "x = 1\n"})
    _write(repo, "src/a.py", STACKED.rstrip("\n") + "  # smell-ok:\n")
    _git(repo, "add", "src/a.py")
    assert _gate(repo, 'git commit -m "x"')[0]


# ─── 判不了就擋、不觸發的情況 ─────────────────────────────────────

def test_wrapped_commit_cannot_be_judged_is_blocked(tmp_path):
    repo = _repo(tmp_path, {"src/a.py": "x = 1\n"})
    deny, _advice = _gate(repo, 'bash -c "git commit -m x"')
    assert deny and "判不了" in deny


def test_non_commit_commands_not_triggered(tmp_path):
    repo = _repo(tmp_path, {"src/a.py": "x = 1\n"})
    assert _gate(repo, "git log --grep commit") == (None, None)
    assert check_smell_gate("Edit", {"command": "git commit"}, str(repo), {}) == (None, None)


def test_disabled_by_config(tmp_path):
    repo = _repo(tmp_path, {"src/a.py": "x = 1\n"})
    _write(repo, "src/a.py", STACKED)
    _git(repo, "add", "src/a.py")
    cfg = {"guard": {"smell_gate": {"enabled": False}}}
    assert check_smell_gate("Bash", {"command": 'git commit -m "x"'}, str(repo), cfg) == (None, None)


# ─── svn ──────────────────────────────────────────────────────────

@pytest.mark.skipif(not (shutil.which("svn") and shutil.which("svnadmin")), reason="本機沒有 svn／svnadmin")
def test_svn_commit_checks_working_copy_changes(tmp_path):
    srv = tmp_path / "srv"
    subprocess.run(["svnadmin", "create", str(srv)], check=True, capture_output=True)
    wc = tmp_path / "wc"
    url = "file:///" + str(srv).replace("\\", "/").lstrip("/")
    subprocess.run(["svn", "checkout", "-q", url, str(wc)], check=True, capture_output=True)
    _write(wc, "a.py", CLEAN_PY)
    subprocess.run(["svn", "add", "-q", "a.py"], cwd=str(wc), check=True, capture_output=True)
    subprocess.run(["svn", "commit", "-q", "-m", "base"], cwd=str(wc), check=True, capture_output=True)
    _write(wc, "a.py", CLEAN_PY + STACKED)
    deny, _advice = check_smell_gate("Bash", {"command": 'svn commit -m "x"'}, str(wc), {})
    assert deny and "a.py" in deny and "第 3 行" in deny
    _write(wc, "a.py", CLEAN_PY + "z = 1\n")
    assert check_smell_gate("Bash", {"command": 'svn commit -m "x"'}, str(wc), {})[0] is None


@pytest.mark.skipif(not (shutil.which("svn") and shutil.which("svnadmin")), reason="本機沒有 svn／svnadmin")
def test_svn_depth_and_targets_scope_what_is_checked(tmp_path):
    """`--depth empty .` 不提交子檔 → 不查；`--targets` 檔列出的路徑 → 查。"""
    srv = tmp_path / "srv"
    subprocess.run(["svnadmin", "create", str(srv)], check=True, capture_output=True)
    wc = tmp_path / "wc"
    url = "file:///" + str(srv).replace("\\", "/").lstrip("/")
    subprocess.run(["svn", "checkout", "-q", url, str(wc)], check=True, capture_output=True)
    _write(wc, "a.py", CLEAN_PY)
    subprocess.run(["svn", "add", "-q", "a.py"], cwd=str(wc), check=True, capture_output=True)
    subprocess.run(["svn", "commit", "-q", "-m", "base"], cwd=str(wc), check=True, capture_output=True)
    _write(wc, "a.py", CLEAN_PY + STACKED)
    assert check_smell_gate("Bash", {"command": 'svn commit --depth empty . -m "x"'}, str(wc), {})[0] is None
    _write(wc, "targets.txt", "a.py\n")
    deny, _advice = check_smell_gate("Bash", {"command": 'svn commit --targets targets.txt -m "x"'}, str(wc), {})
    assert deny and "a.py" in deny

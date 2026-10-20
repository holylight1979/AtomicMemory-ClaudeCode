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
    repo.mkdir(parents=True)
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


def _gate(repo: Path, command: str, tool: str = "Bash"):
    return check_smell_gate(tool, {"command": command}, str(repo), {})


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


# 009：第二波無頭題 A 的 notify/retry.py 原文（C:\w2\qa-repro，AI 用 git commit --amend 提交進去、閘沒擋）
QA_RETRY = ('from notify import dispatch\n\nRETRY = {\n'
            '    "once": lambda k, p: dispatch.dispatch(k, p) or dispatch.dispatch(k, p),\n'
            '    "twice": lambda k, p: dispatch.dispatch(k, p) or dispatch.dispatch(k, p) or dispatch.dispatch(k, p),\n'
            '}\n\n\ndef retry(policy, kind, payload):\n    try:\n        return RETRY[policy](kind, payload)\n'
            '    except:\n        return False\n')
# 第一波受測專案 C:\w1\qa-notify 的部位表與病灶清單（前綴有反引號、病灶欄指檔案）
QA_DEFECTS = ("| 位置 | 症狀 | 根因 | 修法 | 狀態 | 規格 | 形狀 |\n|---|---|---|---|---|---|---|\n"
              "| `notify/dispatch.py` | 回呼用 lambda 塞進 dict 分派，讀的人要跳回去查每個 lambda 包了誰 | 早期想省幾行 | "
              "改成有名字的函式直接放 dict，或 register() 單一入口 | 未修 | `待規格：管道註冊方式沒人拍板` | `shape: :\\s*lambda\\b` |\n")


def _qa_map(repo: Path, backticked: bool) -> None:
    """backticked＝第一波（w1）寫法；False＝第二波 kit 的寫法（前綴沒反引號、病灶欄寫散文）。"""
    row = ("| `notify/` | 通知分派 | 無 | 部分 | notify/defects.md |" if backticked else
           "| notify/ | 通知分派 | 無 | 部分 | 回呼用 lambda 塞進 dict 分派，讀的人要跳回去查每個 lambda 包了誰 |")
    _write(repo, ".claude/overview-map.md", "| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 病灶清單 |\n|---|---|---|---|---|\n" + row + "\n")
    if backticked:
        _write(repo, "notify/defects.md", QA_DEFECTS)


def test_qa_retry_dict_lambda_blocked_when_part_table_is_readable(tmp_path):
    """部位表照第一波寫法（前綴有反引號、病灶清單指 defects.md）：第二波 AI 寫的 retry.py 一樣擋，點名第 4 行與症狀。"""
    repo = _repo(tmp_path, {"notify/__init__.py": "", "notify/dispatch.py": "def dispatch(k, p):\n    return True\n"})
    _qa_map(repo, backticked=True)
    _write(repo, "notify/retry.py", QA_RETRY)
    _git(repo, "add", "notify/retry.py")
    deny, _advice = _gate(repo, 'git commit -m "add retry"')
    assert deny and "回呼用 lambda 塞進 dict 分派" in deny and "notify/retry.py 第 4 行" in deny


def test_part_table_rows_without_backticks_are_reported_not_silently_dropped(tmp_path):
    """第二波 kit 的部位表前綴沒反引號，parse_map 整列略過、病灶清單不套：以前什麼都不說（「都沒有病形」），現在要說出來。"""
    repo = _repo(tmp_path, {"notify/__init__.py": "", "notify/dispatch.py": "def dispatch(k, p):\n    return True\n"})
    _qa_map(repo, backticked=False)
    _write(repo, "notify/retry.py", QA_RETRY)
    _git(repo, "add", "notify/retry.py")
    deny, advice = _gate(repo, 'git commit -m "add retry"')
    assert not deny, "前置：表沒讀到時內建病形不中這份 retry.py（沒有套層 lambda）"
    assert advice and "沒用反引號包" in advice and "| notify/ | 通知分派" in advice


@pytest.mark.parametrize("how", ["staged_then_amend", "sick_already_in_head"])
def test_commit_amend_checks_against_head_parent(tmp_path, how):
    """git commit --amend：比對基準是 HEAD^。staged 的病檔要擋；病已經在被 amend 的那個提交裡、這次只改訊息也要擋（amend 等於重提交它）。"""
    repo = _repo(tmp_path, {"src/a.py": CLEAN_PY})
    _write(repo, "src/b.py", "y = 1\n")
    _git(repo, "add", "src/b.py")
    _git(repo, "commit", "-q", "-m", "add b")
    _write(repo, "src/b.py", "y = 1\n" + STACKED)
    if how == "sick_already_in_head":
        _git(repo, "add", "src/b.py")
        _git(repo, "commit", "-q", "-m", "sick b")
        _git(repo, "reset", "-q", "--soft", "HEAD~1")
        _git(repo, "commit", "-q", "--amend", "-m", "add b (sick)")
        command = 'git commit --amend -m "reword"'
    else:
        _git(repo, "add", "src/b.py")
        command = "git commit --amend --no-edit"
    deny, _advice = _gate(repo, command)
    assert deny and "匿名函式疊用" in deny and "src/b.py 第 2 行" in deny, how


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


# ─── commit 指令的寫法（驗收題 A：多行訊息／here-string 把 `-- <路徑>` 切到另一段，整條無聲放行）──────
# 每種寫法：帶 pathspec（病碼只在工作樹、沒暫存，只有 pathspec 會把它帶進提交）與不帶 pathspec（病碼在暫存區）都要點名那一行。

MESSAGE_FORMS = [
    ("Bash", "多行雙引號", 'git commit -m "notify: add webhook\n\nCo-Authored-By: X <x@y>"'),
    ("PowerShell", "多行雙引號", 'git commit -m "notify: add webhook\n\nCo-Authored-By: X <x@y>"'),
    ("PowerShell", "here-string 單引號", "git commit -m @'\nit's \"quoted\"; -- not/a/path.py\n'@"),
    ("PowerShell", "here-string 雙引號", 'git commit -m @"\nsay "hi" && -- not/a/path.py\n"@'),
    ("Bash", "-F 檔", "git commit -F msg.txt"),
    ("PowerShell", "-F 檔", "git commit -F msg.txt"),
    ("Bash", "多個 -m", 'git commit -m "a" -m "b; -- not/a/path.py"'),
    ("PowerShell", "多個 -m", 'git commit -m "a" -m "b; -- not/a/path.py"'),
]
_FORM_IDS = [f"{tool}-{name}" for tool, name, _cmd in MESSAGE_FORMS]


@pytest.mark.parametrize("tool,_name,commit", MESSAGE_FORMS, ids=_FORM_IDS)
def test_message_forms_with_pathspec_check_those_paths(tmp_path, tool, _name, commit):
    repo = _repo(tmp_path, {"src/a.py": CLEAN_PY, "src/b.py": CLEAN_PY})
    _write(repo, "src/a.py", CLEAN_PY + STACKED)
    assert _git(repo, "diff", "--cached", "--name-only").stdout == ""      # 前置：暫存區是空的
    deny, _advice = _gate(repo, commit + " -- src/b.py src/a.py && git log --oneline -1", tool)
    assert deny and "src/a.py 第 3 行" in deny


@pytest.mark.parametrize("tool,_name,commit", MESSAGE_FORMS, ids=_FORM_IDS)
def test_message_forms_without_pathspec_check_staged(tmp_path, tool, _name, commit):
    repo = _repo(tmp_path, {"src/a.py": CLEAN_PY})
    _write(repo, "src/a.py", CLEAN_PY + STACKED)
    _git(repo, "add", "src/a.py")
    deny, _advice = _gate(repo, commit, tool)
    assert deny and "src/a.py 第 3 行" in deny


def test_acceptance_a_verbatim_command_is_blocked(tmp_path):
    """驗收 transcript 裡 AI 實際下的指令原樣（授權註解＋雙引號多行訊息＋pathspec＋&& git log）。"""
    files = {"notify/channels.py": "x = 1\n", "notify/dispatch.py": CLEAN_PY, "tests/test_dispatch.py": "y = 1\n"}
    repo = _repo(tmp_path, files)
    _write(repo, "notify/dispatch.py", CLEAN_PY + STACKED)
    command = ('# 授權原句：「寫完測試，然後把這次的改動 commit。」\n'
               'git commit -m "notify: add webhook channel (urllib POST text to url)\n\n'
               'Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" -- notify/channels.py notify/dispatch.py '
               'tests/test_dispatch.py && git log --oneline -2')
    deny, _advice = _gate(repo, command)
    assert deny and "notify/dispatch.py 第 3 行" in deny


def test_herestring_pathspec_without_new_smell_passes_and_lists_old(tmp_path):
    repo = _repo(tmp_path, {"src/a.py": STACKED + "y = 1\n"})
    _write(repo, "src/a.py", STACKED + "y = 2\n")
    deny, advice = _gate(repo, "git commit -m @'\nfix y\n'@ -- src/a.py", "PowerShell")
    assert deny is None
    assert advice and "舊碼原本就有" in advice and "src/a.py 第 1 行" in advice


JUDGEABLE_FORMS = [      # 看起來有展開、其實拆得準的寫法：要照常查（點名那一行），不能當成拆不出
    ("Bash", "git commit -m \"$(cat <<'EOF'\nit's \"x\" -- not/a/path.py\nEOF\n)\" -- src/a.py"),
    ("Bash", "git commit -F - -- src/a.py <<'EOF'\nmsg\nEOF"),
    ("Bash", "git commit -m $'line1\\nline2' -- src/a.py"),
    ("PowerShell", "$msg = @'\nfix\n'@; git commit -m $msg -- src/a.py"),
    ("PowerShell", 'git commit -m "x" -- src/a.py 2>$null'),
    ("PowerShell", 'git commit -m "$(Get-Date)" -- src/a.py'),
    ("Bash", "git commit 2>&1 -m x -- src/a.py"),                       # 重導向裡的 & 不是分隔（Codex BLOCK 1）
    ("Bash", "git add 2>&1 src/a.py && git commit -m x"),
    ("Bash", 'git commit -m "fix \\"a; b\\"" -- src/a.py'),            # 跳脫的引號：分號在訊息裡（Codex BLOCK 2）
    ("PowerShell", 'git commit -m "fix `"a; b`"" -- src/a.py'),
]


@pytest.mark.parametrize("tool,command", JUDGEABLE_FORMS)
def test_judgeable_expansions_are_checked_not_refused(tmp_path, tool, command):
    repo = _repo(tmp_path, {"src/a.py": CLEAN_PY})
    _write(repo, "src/a.py", CLEAN_PY + STACKED)
    deny, _advice = _gate(repo, command, tool)
    assert deny and "src/a.py 第 3 行" in deny


UNPARSEABLE_FORMS = [    # 拆不出要提交什麼：一律擋並說為什麼，不能無聲放行
    ("Bash", "git commit -m $(cat msg.txt) -- src/a.py", "引號外有展開"),
    ("Bash", 'git commit $(printf -- "-m x") -- src/a.py', "引號外有展開"),
    ("PowerShell", "git commit -m $(Get-Content msg.txt) -- src/a.py", "引號外有展開"),
    ("Bash", 'git commit -m "unclosed -- src/a.py', "引號沒有閉合"),
    ("PowerShell", "git commit -m @'\nno closing line\n -- src/a.py", "沒有行首的結束行"),
    ("Bash", 'git commit -m "x" -- "$f"', "是變數或命令替換"),
    ("PowerShell", 'git commit -m "x" -- $files', "是變數或命令替換"),
    ("Bash", 'git add "$f" && git commit -m "x"', "是變數或命令替換"),
    ("Bash", 'cd "$REPO" && git commit -m "x" -- src/a.py', "落點"),
    ("Bash", "git commit -m x -- src/{1..3}.py", "引號外有展開"),       # 序列展開（Codex BLOCK 3）
]


@pytest.mark.parametrize("tool,command,why", UNPARSEABLE_FORMS)
def test_unparseable_commit_shape_is_blocked_with_reason(tmp_path, tool, command, why):
    repo = _repo(tmp_path, {"src/a.py": CLEAN_PY})
    _write(repo, "src/a.py", CLEAN_PY + "z = 1\n")       # 改動本身沒病：擋的理由只能是寫法拆不出
    deny, _advice = _gate(repo, command, tool)
    assert deny and "判不了" in deny and why in deny


@pytest.mark.parametrize("tool", ["Bash", "PowerShell"])
def test_literal_dollar_in_quoted_file_name_is_checked_not_refused(tmp_path, tool):
    """單引號裡的 `$` 是字面檔名（Remix 路由 `users.$id.tsx` 這類）：照查，不能當成變數擋掉（Codex BLOCK 5）。"""
    repo = _repo(tmp_path, {"src/$name.py": CLEAN_PY})
    _write(repo, "src/$name.py", CLEAN_PY + STACKED)
    deny, _advice = _gate(repo, "git commit -m x -- 'src/$name.py'", tool)
    assert deny and "src/$name.py 第 3 行" in deny


def test_relative_cd_and_dash_c_accumulate_to_the_real_repo(tmp_path):
    """連續 cd、cd 之後的 git -C、多個 -C 都相對前一個落點：查真正落到的 repo，不是把最後一段接在 tool cwd 後面。"""
    repo = _repo(tmp_path, {"src/a.py": CLEAN_PY})
    _write(repo, "src/a.py", CLEAN_PY + STACKED)
    (tmp_path / "src").mkdir()                    # 接錯的話落在這個不是 repo 的目錄，看成沒東西要提交
    for command in ('cd proj && cd src && git commit -m "x" -- a.py', 'cd proj && git -C src commit -m "x" -- a.py',
                    'git -C proj -C src commit -m "x" -- a.py'):
        deny, _advice = check_smell_gate("Bash", {"command": command}, str(tmp_path), {})
        assert deny and "src/a.py 第 3 行" in deny, command


def test_svn_multiline_message_keeps_paths_in_the_commit_segment():
    from handlers.pre_tool_use import _svn_segments
    assert _svn_segments('svn commit -m "a\n\nb; c" x.py', {"commit"}) == [("", ["commit", "-m", "a\n\nb; c", "x.py"])]


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


# ─── 擴充病形（派工 003：提案 002 第 1～7 列核可的部分）────────────

def _stage(tmp_path, rel, old, new):
    repo = _repo(tmp_path, {rel: old})
    _write(repo, rel, new)
    _git(repo, "add", rel)
    return repo


def _body(n: int, indent: str = "    ") -> str:
    return "".join(f"{indent}step{i}();\n" for i in range(n))


def test_long_anonymous_callback_body_is_blocked(tmp_path):
    repo = _stage(tmp_path, "web/app.js", "var x = 1;\n", "load(function (a) {\n" + _body(22) + "});\n")
    deny, _advice = _gate(repo, 'git commit -m "x"')
    assert deny and "匿名函式本體過長" in deny and "web/app.js 第 1 行" in deny


def test_medium_anonymous_body_is_only_listed(tmp_path):
    repo = _stage(tmp_path, "web/app.js", "var x = 1;\n", "load((a) => {\n" + _body(12) + "});\n")
    deny, advice = _gate(repo, 'git commit -m "x"')
    assert deny is None and advice and "匿名函式本體過長" in advice and "只提醒" in advice


def test_long_test_framework_callback_is_not_counted(tmp_path):
    src = 'describe("cart", () => {\n' + _body(25) + "});\n"
    repo = _stage(tmp_path, "web/suite.js", "var x = 1;\n", src)
    assert _gate(repo, 'git commit -m "x"')[0] is None


def test_long_java_anonymous_class_is_blocked(tmp_path):
    src = "class A {\n  void f() {\n    run(new Runnable() {\n      public void run() {\n" + _body(20, "        ") + "      }\n    });\n  }\n}\n"
    repo = _stage(tmp_path, "src/A.java", "class A {}\n", src)
    deny, _advice = _gate(repo, 'git commit -m "x"')
    assert deny and "匿名函式本體過長" in deny and "src/A.java 第 3 行" in deny


def test_anonymous_body_threshold_is_configurable(tmp_path):
    repo = _stage(tmp_path, "web/app.js", "var x = 1;\n", "load((a) => {\n" + _body(6) + "});\n")
    assert _gate(repo, 'git commit -m "x"')[0] is None
    cfg = {"guard": {"smell_gate": {"anon_body_block_lines": 5, "anon_body_list_lines": 3}}}
    deny, _advice = check_smell_gate("Bash", {"command": 'git commit -m "x"'}, str(repo), cfg)
    assert deny and "匿名函式本體過長" in deny


def test_python_lambda_assignment_is_blocked(tmp_path):
    repo = _stage(tmp_path, "src/a.py", "x = 1\n", "square = lambda v: v * v\n")
    deny, _advice = _gate(repo, 'git commit -m "x"')
    assert deny and "lambda 指派給變數" in deny and "src/a.py 第 1 行" in deny


def test_lambda_assignment_inside_except_is_import_fallback(tmp_path):
    src = "try:\n    from fast import run\nexcept ImportError:\n    run = lambda *a: None\n"
    repo = _stage(tmp_path, "src/a.py", "x = 1\n", src)
    assert _gate(repo, 'git commit -m "x"')[0] is None


def test_test_framework_callbacks_do_not_count_as_nesting(tmp_path):
    src = 'describe("a", () => {\n  it("b", () => {\n    run(() => {\n      x();\n    });\n  });\n});\n'
    repo = _stage(tmp_path, "web/suite.js", "var x = 1;\n", src)
    assert _gate(repo, 'git commit -m "x"')[0] is None


def test_promise_callback_using_outer_variable_does_not_count_as_nesting(tmp_path):
    src = ("load(function (a) {\n"
           "  fetchIt(a).then(function (r) {\n"
           "    r.json().then(function (j) {\n"
           "      use(r, j);\n"
           "    });\n"
           "  });\n"
           "});\n")
    repo = _stage(tmp_path, "web/app.js", "var x = 1;\n", src)
    assert _gate(repo, 'git commit -m "x"')[0] is None
    repo2 = _stage(tmp_path / "b", "web/app.js", "var x = 1;\n", src.replace("use(r, j)", "use(j)"))
    assert _gate(repo2, 'git commit -m "x"')[0]                                    # 內層沒用到外層變數 → 照算三層


DEEP4 = ("def f(xs):\n"
         "    for x in xs:\n"
         "        if x:\n"
         "            while x:\n"
         "                if x > 1:\n"
         "                    x -= 1\n")
DEEP3 = DEEP4.replace("                if x > 1:\n                    x -= 1\n", "                x -= 1\n")


def test_new_function_nested_four_levels_is_blocked(tmp_path):
    repo = _stage(tmp_path, "src/a.py", "x = 1\n", DEEP4)
    deny, _advice = _gate(repo, 'git commit -m "x"')
    assert deny and "控制結構巢狀太深" in deny and "f 巢狀 4 層" in deny


def test_deepening_existing_function_to_four_levels_is_blocked(tmp_path):
    repo = _stage(tmp_path, "src/a.py", DEEP3, DEEP4)
    deny, _advice = _gate(repo, 'git commit -m "x"')
    assert deny and "控制結構巢狀太深" in deny


def test_old_deep_function_touched_without_deepening_is_only_listed(tmp_path):
    repo = _stage(tmp_path, "src/a.py", DEEP4, DEEP4.replace("x -= 1", "x -= 2"))
    deny, advice = _gate(repo, 'git commit -m "x"')
    assert deny is None and advice and "控制結構巢狀太深" in advice


def test_elif_chain_does_not_count_as_nesting(tmp_path):
    src = ("def g(x):\n    if x == 1:\n        return 1\n    elif x == 2:\n        return 2\n"
           "    elif x == 3:\n        return 3\n    elif x == 4:\n        return 4\n")
    repo = _stage(tmp_path, "src/a.py", "x = 1\n", src)
    assert _gate(repo, 'git commit -m "x"')[0] is None


def test_python_nested_ternary_is_blocked(tmp_path):
    repo = _stage(tmp_path, "src/a.py", "x = 1\n", "y = a if b else (c if d else e)\n")
    deny, _advice = _gate(repo, 'git commit -m "x"')
    assert deny and "巢狀三元" in deny
    repo2 = _stage(tmp_path / "b", "src/a.py", "x = 1\n", "y = a if b else c\n")
    assert _gate(repo2, 'git commit -m "x"')[0] is None


UNITY = "using UnityEngine;\npublic class Player : MonoBehaviour\n{\n%s}\n"


def test_empty_unity_message_is_blocked(tmp_path):
    repo = _stage(tmp_path, "Game/Player.cs", UNITY % "", UNITY % "    void Update()\n    {\n    }\n")
    deny, _advice = _gate(repo, 'git commit -m "x"')
    assert deny and "空的 Unity 訊息方法" in deny and "Game/Player.cs 第 4 行" in deny


def test_empty_virtual_unity_message_is_a_hook_for_subclasses(tmp_path):
    repo = _stage(tmp_path, "Game/Player.cs", UNITY % "", UNITY % "    protected virtual void Update() { }\n")
    assert _gate(repo, 'git commit -m "x"')[0] is None


def test_expensive_lookup_in_update_is_blocked(tmp_path):
    body = '    void Update()\n    {\n        var e = GameObject.Find("Enemy");\n        e.Hit();\n    }\n'
    repo = _stage(tmp_path, "Game/Player.cs", UNITY % "", UNITY % body)
    deny, _advice = _gate(repo, 'git commit -m "x"')
    assert deny and "每幀方法裡做昂貴查找" in deny and "Game/Player.cs 第 6 行" in deny


def test_lazy_cached_lookup_in_update_is_fine(tmp_path):
    body = ('    GameObject enemy;\n    void Update()\n    {\n        if (enemy == null)\n'
            '            enemy = GameObject.Find("Enemy");\n        enemy.SendMessage("Hit");\n    }\n')
    repo = _stage(tmp_path, "Game/Player.cs", UNITY % "", UNITY % body)
    assert _gate(repo, 'git commit -m "x"')[0] is None


def test_lookup_in_editor_only_region_or_start_is_fine(tmp_path):
    body = ('    void Start() { var e = GameObject.Find("Enemy"); }\n'
            '    void Update()\n    {\n#if UNITY_EDITOR\n        var t = typeof(Player).GetMethod("Hit");\n#endif\n'
            '        Move();\n    }\n')
    repo = _stage(tmp_path, "Game/Player.cs", UNITY % "", UNITY % body)
    assert _gate(repo, 'git commit -m "x"')[0] is None


def test_non_unity_update_method_is_not_a_unity_message(tmp_path):
    """校準實例：伺服器程式的模組類別也有 public void Update()，但不是 Unity 訊息；檔裡沒用 UnityEngine 就不查 Unity 規則。"""
    src = "public class ActivityModule : BaseModule\n{\n    public void Update()\n    {\n    }\n}\n"
    repo = _stage(tmp_path, "Server/ActivityModule.cs", "class A {}\n", src)
    assert _gate(repo, 'git commit -m "x"')[0] is None


def test_csharp_expression_bodied_member_is_not_a_lambda(tmp_path):
    """校準實例：`型別 名稱 => 運算式` 是運算式主體的屬性／方法，不是 lambda；裡面再寫一個 lambda 不算匿名套匿名。"""
    src = "class P {\n    public IEnumerable<uint> Ids => _all.Where(x => x.IsInZone).Select(x => x.Id);\n}\n"
    repo = _stage(tmp_path, "Server/P.cs", "class P {}\n", src)
    assert _gate(repo, 'git commit -m "x"')[0] is None


def test_allman_braced_lazy_cache_in_update_is_fine(tmp_path):
    """Codex 003-1：C# 慣用大括號換行，`if (enemy == null)` 與 `{` 分兩行時也是延遲快取。"""
    body = ('    GameObject enemy;\n    void Update()\n    {\n        if (enemy == null)\n        {\n'
            '            enemy = GameObject.Find("Enemy");\n        }\n    }\n')
    repo = _stage(tmp_path, "Game/Player.cs", UNITY % "", UNITY % body)
    assert _gate(repo, 'git commit -m "x"')[0] is None


def test_lookup_in_else_branch_of_unity_editor_is_blocked(tmp_path):
    """Codex 003-2：`#if UNITY_EDITOR … #else …` 的 else 是正式版本跑的；`#if !UNITY_EDITOR` 也是正式版本。"""
    body = ('    void Update()\n    {\n#if UNITY_EDITOR\n        Debug.Log("editor");\n#else\n'
            '        var e = GameObject.Find("Enemy");\n#endif\n    }\n')
    repo = _stage(tmp_path, "Game/Player.cs", UNITY % "", UNITY % body)
    assert _gate(repo, 'git commit -m "x"')[0]
    body2 = '    void Update()\n    {\n#if !UNITY_EDITOR\n        var e = GameObject.Find("Enemy");\n#endif\n    }\n'
    repo2 = _stage(tmp_path / "b", "Game/Player.cs", UNITY % "", UNITY % body2)
    assert _gate(repo2, 'git commit -m "x"')[0]


def test_anonymous_body_growing_past_block_threshold_is_blocked(tmp_path):
    """Codex 003-3：舊版 12 行（只提醒）長到 22 行（該擋），不能被舊版那份抵掉。"""
    repo = _stage(tmp_path, "web/app.js", "load(() => {\n" + _body(12) + "});\n", "load(() => {\n" + _body(22) + "});\n")
    deny, _advice = _gate(repo, 'git commit -m "x"')
    assert deny and "匿名函式本體過長" in deny


def test_same_function_name_in_another_file_does_not_offset_new_deep_nesting(tmp_path):
    """Codex 003-4：a.py 的舊 f 不能替同次提交新增的 b.py 的 f 抵銷。"""
    repo = _repo(tmp_path, {"src/a.py": DEEP4})
    _write(repo, "src/a.py", DEEP4.replace("x -= 1", "x -= 2"))
    _write(repo, "src/b.py", DEEP4)
    _git(repo, "add", "-A")
    deny, _advice = _gate(repo, 'git commit -m "x"')
    assert deny and "src/b.py" in deny


def test_csharp_parameterless_delegate_body_is_measured(tmp_path):
    """Codex 003-5：`delegate {` 沒有參數列，本體照樣要量長度。"""
    src = "class H {\n  void Run() {\n    System.Action f = delegate {\n" + _body(22, "      ") + "    };\n    f();\n  }\n}\n"
    repo = _stage(tmp_path, "Server/H.cs", "class H {}\n", src)
    deny, _advice = _gate(repo, 'git commit -m "x"')
    assert deny and "匿名函式本體過長" in deny


def test_promise_callback_using_any_outer_parameter_does_not_count(tmp_path):
    """Codex 003-6：then 回呼用到的是再外一層的參數（a），也算用到外層變數。"""
    src = "load(a => {\n  run(b => {\n    fetchIt().then(c => {\n      use(a, c);\n    });\n  });\n});\n"
    repo = _stage(tmp_path, "web/app.js", "var x = 1;\n", src)
    assert _gate(repo, 'git commit -m "x"')[0] is None


def test_live_config_carries_the_documented_limits():
    """workflow/config.json 的 guard.smell_gate 門檻要讀得到、等於提案的預設值（改門檻就改這裡與 _doc 的依據）。"""
    import json
    cfg = json.loads((TREE / "workflow" / "config.json").read_text(encoding="utf-8"))
    assert ps.limits_of(cfg) == ps.DEFAULT_LIMITS == {"anon_body_block_lines": 20, "anon_body_list_lines": 10,
                                                      "nesting_block_depth": 4}
    assert "S1188" in cfg["guard"]["smell_gate"]["_doc"]


def test_unclean_strip_downgrades_brace_rules_to_list(tmp_path):
    """字串、註解剝不乾淨（例：JS 正則字面值裡的大括號）→ 大括號類規則判不準，只列不擋。"""
    repo = _stage(tmp_path, "web/app.js", "var x = 1;\n", "var re = /\\{/;\n" + JS_NEST3)
    deny, advice = _gate(repo, 'git commit -m "x"')
    assert deny is None and advice and "判不準" in advice and "匿名回呼套三層以上" in advice


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

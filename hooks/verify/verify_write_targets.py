"""verify_write_targets.py：wg_core.write_paths_from_tool（OverviewHub 閘的寫入目標擷取，A4.4）。

正例：Bash `>`／`>>`／tee／sed -i／cp／mv；PowerShell Set-Content／Out-File／Add-Content；Edit／Write／NotebookEdit 的 file_path。
反例：`/dev/null`／`$null`／`2>&1`／`>&2` 不算目標；相對路徑補成絕對；非寫入工具回 []。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_write_targets.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
os.environ.setdefault("WG_CLAUDE_DIR", str(HOOKS_DIR.parent))
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

from wg_core import write_paths_from_tool, write_sources_from_tool  # noqa: E402

CWD = "C:/Work/Proj"


def _n(paths):
    return [p.replace("\\", "/") for p in paths]


@pytest.mark.parametrize("cmd,expected", [
    ('echo hi > "C:/Work/Proj/src/a.txt"', ["C:/Work/Proj/src/a.txt"]),
    ("echo hi >> C:/Work/Proj/src/a.txt", ["C:/Work/Proj/src/a.txt"]),
    ("cat x | tee C:/Work/Proj/out.log C:/Work/Proj/out2.log", ["C:/Work/Proj/out.log", "C:/Work/Proj/out2.log"]),
    ("sed -i 's/a/b/' C:/Work/Proj/src/a.py C:/Work/Proj/src/b.py", ["C:/Work/Proj/src/a.py", "C:/Work/Proj/src/b.py"]),
    ("sed -i -e 's/a/b/' C:/Work/Proj/src/a.py", ["C:/Work/Proj/src/a.py"]),
    ("cp C:/Work/Proj/src/a.py C:/Work/Proj/src/c.py", ["C:/Work/Proj/src/c.py"]),
    ("mv -f C:/Work/Proj/src/a.py C:/Work/Proj/src/d.py", ["C:/Work/Proj/src/d.py"]),
    ("cat > C:/Work/Proj/n.txt <<'EOF'\nhello\nEOF", ["C:/Work/Proj/n.txt"]),
])
def test_bash_write_targets(cmd, expected):
    assert _n(write_paths_from_tool("Bash", {"command": cmd}, CWD)) == expected


@pytest.mark.parametrize("cmd,expected", [
    ('Set-Content -Path "C:/Work/Proj/a.txt" -Value "x"', ["C:/Work/Proj/a.txt"]),
    ("Set-Content C:/Work/Proj/a.txt -Value x -Encoding utf8", ["C:/Work/Proj/a.txt"]),
    ("Get-Content x | Out-File -FilePath C:/Work/Proj/b.txt -Append", ["C:/Work/Proj/b.txt"]),
    ("Add-Content -LiteralPath C:/Work/Proj/c.txt -Value y -NoNewline", ["C:/Work/Proj/c.txt"]),
    ('"abc" > C:/Work/Proj/d.txt', ["C:/Work/Proj/d.txt"]),
])
def test_powershell_write_targets(cmd, expected):
    assert _n(write_paths_from_tool("PowerShell", {"command": cmd}, CWD)) == expected


@pytest.mark.parametrize("cmd", [
    "python x.py > /dev/null 2>&1",
    "cmd 2>&1 | grep err",
    "echo x >&2",
    "Set-Content -Path $null -Value x",
    "echo x > NUL",
    "sed -n 1,5p C:/Work/Proj/src/a.py",      # 唯讀 sed
    "cp onlyone",                               # 只有一個位置參數不是複製
    "git commit -m 'x'",                        # 不是檔案寫入
])
def test_bash_non_targets(cmd):
    assert write_paths_from_tool("Bash", {"command": cmd}, CWD) == []


def test_037_git_path_restore_is_a_write_target(tmp_path):
    """037：git 指定路徑還原會改寫工作樹的檔 → 是寫入目標（寫碼查核靠它記最後一次改檔的時間）：`checkout [<rev>] -- 路徑`、
    `checkout <rev> 路徑`、只給一個且是現存檔的 `checkout 檔`、`restore [--source／-s <rev>] [--worktree] 路徑`，`-C` 改解析基準；
    PowerShell 同。切分支、建分支、`restore --staged`（只動暫存區）、其他 git 子指令不算；萬用字元、pathspec 魔術字、目錄、
    --pathspec-from-file、--git-dir／--work-tree → 目標不明。"""
    (tmp_path / "src").mkdir()
    (tmp_path / "a.py").write_text("x", encoding="utf-8")
    cwd = str(tmp_path)
    a, b = os.path.normpath(str(tmp_path / "a.py")), os.path.normpath(str(tmp_path / "src" / "b.py"))
    fwd = cwd.replace("\\", "/")
    ok = [
        ("git checkout HEAD~1 -- a.py src/b.py", [a, b]),
        ("git checkout -- a.py", [a]),
        ("git checkout HEAD a.py", [a]),
        ("git checkout a.py", [a]),
        (f"git -C {fwd} checkout v6/x -- a.py", [a]),
        (f"cd {fwd} && git checkout d59ee37 -- a.py src/b.py", [a, b]),
        ("git restore a.py", [a]),
        ("git restore --source HEAD~1 a.py", [a]),
        ("git restore -s HEAD~1 -- a.py", [a]),
        ("git restore --staged --worktree a.py", [a]),
        ("git restore -SW a.py", [a]),
    ]
    for cmd, want in ok:
        assert write_paths_from_tool("Bash", {"command": cmd}, cwd) == want, cmd
    assert write_paths_from_tool("PowerShell", {"command": "git checkout HEAD -- a.py"}, cwd) == [a]
    for cmd in ("git checkout main", "git checkout -b feat", "git checkout -B feat HEAD~1", "git restore --staged a.py",
                "git restore -S a.py", "git switch main", "git commit -m x", "git checkout HEAD~1", "git status -- a.py"):
        assert write_paths_from_tool("Bash", {"command": cmd}, cwd) == [], cmd
    for cmd in ("git checkout HEAD -- '*.py'", "git checkout -- .", "git checkout HEAD -- src", "git restore :/a.py",
                "git --git-dir=x checkout -- a.py", "git restore --pathspec-from-file=list.txt"):
        got = write_paths_from_tool("Bash", {"command": cmd}, cwd)
        assert len(got) == 1 and got[0].startswith("UNKNOWN:"), (cmd, got)


def test_039_whole_directory_restore_is_unknown_not_silent(tmp_path):
    """039（038 codex BLOCK）：只給一個參數而它是現存目錄的 checkout（`git checkout .`、`git -C src checkout .`、`git checkout src`）
    還原整個目錄、不知道動了哪些檔 → 目標不明，不是 []；`checkout -- .`、`restore .` 同樣目標不明；真的切分支、不存在的名字仍是 []。"""
    (tmp_path / "src").mkdir()
    cwd, fwd = str(tmp_path), str(tmp_path).replace("\\", "/")
    for cmd in ("git checkout .", f"git -C {fwd}/src checkout .", f"git -C {fwd} -C src checkout .", "git checkout src",
                "git checkout -- .", "git restore .", f"cd {fwd}/src && git checkout ."):
        got = write_paths_from_tool("Bash", {"command": cmd}, cwd)
        assert len(got) == 1 and got[0].startswith("UNKNOWN:"), (cmd, got)
    for cmd in ("git checkout main", "git checkout v6/track-e6", "git checkout -"):
        assert write_paths_from_tool("Bash", {"command": cmd}, cwd) == [], cmd


def test_040_git_mv_destination_is_a_write_target(tmp_path):
    """040：已不存在的程式檔不再欠補案例，所以搬檔的新路徑必須記成寫入：`git mv 來源 目標` 的目標同 mv（目標是現存目錄＝目錄/來源檔名，
    -C 改解析基準）；只有一個參數不算；--git-dir 判不出來。"""
    (tmp_path / "src").mkdir()
    (tmp_path / "pkg").mkdir()
    cwd, fwd = str(tmp_path), str(tmp_path).replace("\\", "/")
    b, pa = os.path.normpath(str(tmp_path / "src" / "b.py")), os.path.normpath(str(tmp_path / "pkg" / "a.py"))
    assert write_paths_from_tool("Bash", {"command": "git mv src/a.py src/b.py"}, cwd) == [b]
    assert write_paths_from_tool("Bash", {"command": f"git -C {fwd} mv -f src/a.py src/b.py"}, cwd) == [b]
    assert write_paths_from_tool("Bash", {"command": "git mv src/a.py pkg"}, cwd) == [pa]
    assert write_paths_from_tool("PowerShell", {"command": "git mv src/a.py src/b.py"}, cwd) == [b]
    assert write_paths_from_tool("Bash", {"command": "git mv src/a.py"}, cwd) == []
    got = write_paths_from_tool("Bash", {"command": "git --git-dir=x mv src/a.py src/b.py"}, cwd)
    assert len(got) == 1 and got[0].startswith("UNKNOWN:"), got


def test_040_rename_item_records_old_and_new_path(tmp_path):
    """040 codex 第二輪：PowerShell Rename-Item 的新名字也是寫入目標（落在舊路徑的同一個目錄）；-NewName 具名或第二個位置參數、
    rni／ren 別名都一樣。舊碼只記舊路徑，改名走的程式在新路徑沒有修改紀錄。"""
    cwd = str(tmp_path)
    a, b = os.path.normpath(str(tmp_path / "src" / "a.py")), os.path.normpath(str(tmp_path / "src" / "b.py"))
    for cmd in ("Rename-Item -Path src/a.py -NewName b.py", "Rename-Item src/a.py b.py", "rni src/a.py -NewName b.py",
                "ren -LiteralPath src/a.py -NewName b.py", "Rename-Item -Path src/a.py b.py",
                "Rename-Item -LiteralPath src/a.py b.py"):          # 040 codex 第三輪：來源具名、新名字是位置參數
        assert write_paths_from_tool("PowerShell", {"command": cmd}, cwd) == [a, b], cmd


def test_relative_paths_resolve_against_cwd():
    got = _n(write_paths_from_tool("Bash", {"command": "echo a > src/a.txt; tee logs/x.log"}, CWD))
    assert got == ["C:/Work/Proj/src/a.txt", "C:/Work/Proj/logs/x.log"]
    got = _n(write_paths_from_tool("Bash", {"command": "echo a > /c/Work/Proj/m.txt"}, CWD))   # MSYS 路徑
    assert got == ["C:/Work/Proj/m.txt"]
    for p in write_paths_from_tool("Bash", {"command": "echo a > rel.txt"}):                    # 沒給 cwd 用行程 cwd
        assert Path(p).is_absolute()


def test_edit_write_notebook_and_other_tools():
    assert _n(write_paths_from_tool("Edit", {"file_path": "C:/Work/Proj/a.py"})) == ["C:/Work/Proj/a.py"]
    assert _n(write_paths_from_tool("Write", {"file_path": "C:/Work/Proj/a.py"})) == ["C:/Work/Proj/a.py"]
    assert _n(write_paths_from_tool("NotebookEdit", {"notebook_path": "C:/Work/Proj/n.ipynb"})) == ["C:/Work/Proj/n.ipynb"]
    assert write_paths_from_tool("Read", {"file_path": "C:/Work/Proj/a.py"}) == []
    assert write_paths_from_tool("Grep", {"pattern": "x"}) == []
    assert write_paths_from_tool("Edit", {}) == []


def test_dedup_same_target_twice():
    got = _n(write_paths_from_tool("Bash", {"command": "echo a > C:/Work/Proj/a.txt && echo b >> C:/Work/Proj/a.txt"}, CWD))
    assert got == ["C:/Work/Proj/a.txt"]


# ─── 退回 001 BLOCK 4／5：漏判、算錯、誤報，各一案 ───────────────────────────────

def test_write_targets_home_var_in_double_quotes():
    home = str(Path.home()).replace("\\", "/")
    assert _n(write_paths_from_tool("Bash", {"command": 'echo x > "$HOME/a b.txt"'}, CWD)) == [f"{home}/a b.txt"]
    assert _n(write_paths_from_tool("Bash", {"command": "echo x > ~/n.txt"}, CWD)) == [f"{home}/n.txt"]


def test_write_targets_sed_combined_flags():
    assert _n(write_paths_from_tool("Bash", {"command": "sed -ni 's/a/b/p' a.py"}, CWD)) == ["C:/Work/Proj/a.py"]
    assert _n(write_paths_from_tool("Bash", {"command": "sed -i.bak 's/a/b/' a.py"}, CWD)) == ["C:/Work/Proj/a.py"]
    assert write_paths_from_tool("Bash", {"command": "sed -nE '1,5p' a.py"}, CWD) == []            # 沒 i 不是寫入


def test_write_targets_cd_updates_cwd_for_later_segments():
    assert _n(write_paths_from_tool("Bash", {"command": "cd src && echo x > a.py"}, CWD)) == ["C:/Work/Proj/src/a.py"]
    assert _n(write_paths_from_tool("Bash", {"command": "echo x > a.py; cd src; echo y > b.py"}, CWD)) == ["C:/Work/Proj/a.py", "C:/Work/Proj/src/b.py"]


def test_write_targets_cp_into_directory():
    assert _n(write_paths_from_tool("Bash", {"command": "cp src.py dest/"}, CWD)) == ["C:/Work/Proj/dest/src.py"]
    assert _n(write_paths_from_tool("Bash", {"command": "mv a.py b.py c/"}, CWD)) == ["C:/Work/Proj/c/a.py", "C:/Work/Proj/c/b.py"]
    assert _n(write_paths_from_tool("Bash", {"command": "cp -t dest a.py b.py"}, CWD)) == ["C:/Work/Proj/dest/a.py", "C:/Work/Proj/dest/b.py"]
    assert _n(write_paths_from_tool("Bash", {"command": "cp --target-directory=dest a.py"}, CWD)) == ["C:/Work/Proj/dest/a.py"]


def test_write_targets_cp_into_existing_directory(tmp_path):
    (tmp_path / "out").mkdir()
    got = _n(write_paths_from_tool("Bash", {"command": "cp a.py out"}, str(tmp_path)))
    assert got == [str(tmp_path / "out" / "a.py").replace("\\", "/")]


def _srcs(tool, cmd):
    return {k.replace("\\", "/"): _n(v) for k, v in write_sources_from_tool(tool, {"command": cmd}, CWD).items()}


def test_write_sources_map_each_copy_target_to_its_source():
    """需求目標判「搬的是不是程式」用：目的地還不存在時看來源。一對一、多來源進目錄、-t、Move-Item 都對得上；
    沒有來源的寫入（重導向）、非 shell 工具、算不出目標的命令回空；寫入目標本身跟以前一樣。"""
    assert _srcs("Bash", "mv src pkg") == {"C:/Work/Proj/pkg": ["C:/Work/Proj/src"]}
    assert _srcs("Bash", "mv a.py b.py c/") == {"C:/Work/Proj/c/a.py": ["C:/Work/Proj/a.py"],
                                                "C:/Work/Proj/c/b.py": ["C:/Work/Proj/b.py"]}
    assert _srcs("Bash", "cp -t dest a.py") == {"C:/Work/Proj/dest/a.py": ["C:/Work/Proj/a.py"]}
    assert _srcs("PowerShell", "Move-Item -Path src -Destination pkg") == {"C:/Work/Proj/pkg": ["C:/Work/Proj/src"]}
    assert _srcs("Bash", "echo x > out.txt") == {}
    assert write_sources_from_tool("Write", {"file_path": "C:/Work/Proj/x.py"}, CWD) == {}
    assert _srcs("Bash", "cp src $DEST") == {}
    assert _n(write_paths_from_tool("Bash", {"command": "cp -t dest"}, CWD)) == []          # 沒來源的 -t：不多出目標


def test_write_targets_edit_relative_path_is_absolutized():
    assert _n(write_paths_from_tool("Edit", {"file_path": "rel/a.py"}, CWD)) == ["C:/Work/Proj/rel/a.py"]
    assert _n(write_paths_from_tool("Write", {"file_path": "C:/Work/Proj/x.py"}, CWD)) == ["C:/Work/Proj/x.py"]


def test_write_targets_quoted_gt_is_not_redirect():
    assert write_paths_from_tool("Bash", {"command": "echo 'x > out.md'"}, CWD) == []
    assert write_paths_from_tool("Bash", {"command": 'echo "a > b" | grep x'}, CWD) == []


def test_write_targets_heredoc_body_is_not_scanned():
    assert write_paths_from_tool("Bash", {"command": "cat <<EOF\nprint(1 > 0)\nEOF"}, CWD) == []
    assert write_paths_from_tool("Bash", {"command": "git commit -F - <<'EOF'\nmsg > x\nEOF"}, CWD) == []
    got = _n(write_paths_from_tool("Bash", {"command": "cat > n.txt <<'EOT'\nhello > z\nEOT"}, CWD))
    assert got == ["C:/Work/Proj/n.txt"]                                                   # 標記行本身的 > 仍算
    got = write_paths_from_tool("Bash", {"command": "python - <<EOF\nprint(1 > 0)\nEOF"}, CWD)
    assert got == []                                                                        # 直譯器吃 heredoc 碼：交 ast 判，純讀放行


def test_write_targets_tee_to_devnull_has_no_phantom():
    assert _n(write_paths_from_tool("Bash", {"command": "tee out.md > /dev/null"}, CWD)) == ["C:/Work/Proj/out.md"]
    assert _n(write_paths_from_tool("Bash", {"command": "tee -a C:/Work/Proj/l.log 2>&1 | head"}, CWD)) == ["C:/Work/Proj/l.log"]


@pytest.mark.parametrize("cmd", [
    "echo x > $OUT/a",                 # 展不開的變數
    "echo x > %TEMP%/a",               # Windows 變數
    'eval "echo x > a"',               # eval 裡含寫入
    "cd - && echo x > a",              # cd - 之後的相對目標
    "cd $DIR && echo x > a",           # cd 到變數之後的相對目標
    "echo x >",                        # 孤兒重導向
    "Set-Content -Path $env:TEMP/a -Value x",
])
def test_write_targets_unparseable_is_unknown(cmd):
    got = write_paths_from_tool("Bash", {"command": cmd}, CWD)
    assert len(got) == 1 and got[0].startswith("UNKNOWN:"), got


# ─── 退回 002 R0～R5：每條指令一案 ─────────────────────────────────────────────

def _bash(cmd):
    return _n(write_paths_from_tool("Bash", {"command": cmd}, CWD))


def _unknown(cmd):
    got = write_paths_from_tool("Bash", {"command": cmd}, CWD)
    return len(got) == 1 and got[0].startswith("UNKNOWN:")


# BLOCK 1（R2 重導向黏連）
def test_r2_ampersand_gt():
    assert _bash("echo x &> a.py") == ["C:/Work/Proj/a.py"]


def test_r2_glued_gt():
    assert _bash("echo x>a.py") == ["C:/Work/Proj/a.py"]


def test_r2_glued_append():
    assert _bash("echo x>>a.py") == ["C:/Work/Proj/a.py"]


def test_r2_gt_quoted_target():
    assert _bash('echo x >"a.py"') == ["C:/Work/Proj/a.py"]


def test_r2_clobber_pipe_is_redirect_not_unknown():
    assert _bash("echo x >| a.py") == ["C:/Work/Proj/a.py"]


def test_r2_fd_dup_and_nulls_are_not_targets():
    assert _bash("cmd 2>&1 | grep err") == [] and _bash("echo x >&2") == [] and _bash("echo x 1>&2") == []
    assert _bash("python x.py > /dev/null 2>&1") == [] and _bash("echo x > NUL") == []


# BLOCK 2（R3 寫檔命令表／R4 直譯器）
def test_r3_dd_of():
    assert _bash("dd if=/dev/zero of=x bs=1") == ["C:/Work/Proj/x"]


def test_r3_install_with_mode():
    assert _bash("install -m 644 a b") == ["C:/Work/Proj/b"]


def test_r3_rsync_into_dir():
    assert _bash("rsync a b/") == ["C:/Work/Proj/b/a"]


def test_r3_ln_symlink():
    assert _bash("ln -sf a b") == ["C:/Work/Proj/b"]


def test_r3_sed_glued_expression_flag():
    assert _bash("sed -i -es/a/b/ a.py") == ["C:/Work/Proj/a.py"]
    assert _bash("sed -es/i/x/ a.py") == []                                        # expression 裡的 i 不是 -i


def test_r3_sed_w_command_writes_file():
    assert _bash('sed -n "w a.py" b.py') == ["C:/Work/Proj/a.py"]
    assert _bash("sed -n 's/a/b/w out.txt' in.txt") == ["C:/Work/Proj/out.txt"]


def test_r3_touch_mkdir_rm_truncate_sort():
    assert _bash("touch a b") == ["C:/Work/Proj/a", "C:/Work/Proj/b"]
    assert _bash("mkdir -p out/sub") == ["C:/Work/Proj/out/sub"]
    assert _bash("rm -rf build") == ["C:/Work/Proj/build"]
    assert _bash("truncate -s 0 log.txt") == ["C:/Work/Proj/log.txt"]
    assert _bash("sort -o out.txt in.txt") == ["C:/Work/Proj/out.txt"] and _bash("sort in.txt") == []


def test_r3_env_assignment_and_wrapper_skipped():
    assert _bash("FOO=1 tee a.py") == ["C:/Work/Proj/a.py"] and _bash("sudo cp a b") == ["C:/Work/Proj/b"]


def test_r4_python_inline_code_is_unknown():
    assert _unknown("python -c \"open('x','w').write('1')\"")
    assert _unknown("node -e \"fs.writeFileSync('x','1')\"") and _unknown("node -e \"console.log(1)\"")   # node 判不了照擋
    assert _unknown("pwsh -Command \"Set-Content a b\"")
    assert _bash("python - <<'EOF'\nprint(1)\nEOF") == []                                                   # heredoc 交 ast 判：純讀放行
    assert _unknown("python - <<'EOF'\nopen('x','w').write('1')\nEOF")                                     # 寫檔照擋
    assert _bash("python x.py --out a.py") == []                                    # 跑腳本不是內嵌碼


def test_006_inline_flag_only_before_the_program():
    """規則 INLINE_FLAG_BEFORE_PROGRAM（閘小修 006 件 6；005 工作 session 真被擋的指令 `python _vcs_run.py -C <路徑> status`）：
    程式（腳本、-m 模組）之後的 -C／-c／- 是程式的參數；python／node 分大小寫、帶值選項連值跳過；pwsh 不分大小寫、-File 之後停。"""
    assert _bash("python _vcs_run.py -C C:/Users/holylight/.claude status --porcelain") == []
    assert _bash("python tools/report.py -C C:/w4/qc2-orders") == []
    assert _bash("python x.py -") == [] and _bash("python x.py -c config.ini") == []
    assert _bash("python -m pytest -c a.ini -q") == []                                  # -m 之後是 pytest 的 -c
    assert _bash("node b.js -e prod") == [] and _bash("node -C dev b.js") == []
    assert _bash("pwsh -File a.ps1 -c x") == []
    assert _unknown("python -X utf8 -c \"open('x','w')\"")                              # 帶值選項跳過後的 -c 照判
    assert _unknown("python -W ignore -c \"open('x','w')\"")
    assert _unknown("node -r ./setup.js -e \"fs.writeFileSync('x','1')\"")
    assert _unknown("pwsh -ExecutionPolicy Bypass -Command \"Set-Content a b\"")
    assert _unknown("pwsh -NoProfile -C \"Set-Content a b\"")                            # PowerShell 不分大小寫


_C5_SCRATCH = "C:\\Users\\HOLYLI~1\\AppData\\Local\\Temp\\claude\\C--w4-qc2-orders\\b9537e60\\scratchpad"
# 第五跑 C-1 第 4 回合原指令（transcript 22:27:41，被擋 edit_unknown_target）：scratchpad 用變數 S 指定再寫進去
_C5_CMD = (f"S='{_C5_SCRATCH}' && git show 27a294f:orders/pricing.py > \"$S/old_pricing.py\" && python -c \"import importlib.util, sys; "
           "spec = importlib.util.spec_from_file_location('old', sys.argv[1]); m = importlib.util.module_from_spec(spec); "
           "spec.loader.exec_module(m); print(m.subtotal)\" \"$S/old_pricing.py\"; rm \"$S/old_pricing.py\"; git status --short")


def test_006_shell_literal_var_expanded():
    """規則 SHELL_LITERAL_VAR_EXPANDED（閘小修 006 件 5）：同指令獨立一段的字面指定，之後的 $S／${S} 代換再算目標。"""
    want = _C5_SCRATCH.replace("\\", "/") + "/old_pricing.py"
    assert _bash(f"S='{_C5_SCRATCH}' && git show HEAD:a.py > \"$S/old_pricing.py\"") == [want]
    assert _bash(f"S='{_C5_SCRATCH}'; cp a.py ${{S}}/old_pricing.py") == [want]
    assert _bash(f"export S='{_C5_SCRATCH}'\nrm \"$S/old_pricing.py\"") == [want]
    assert _bash("OUT=out && echo x > \"$OUT/a.txt\"") == ["C:/Work/Proj/out/a.txt"]          # 相對值照 cwd 補
    # 反例：判不出的照判不出
    assert _unknown("echo x > \"$S/a\"")                                                       # 沒指定過
    assert _unknown("S=\"$(pwd)/x\" && echo x > \"$S/a\"")                                     # 值不是字面（$TMP 這類改照 SHELL_ENV_VAR_EXPANDED 代換，見 007）
    assert _unknown(f"S='{_C5_SCRATCH}' | echo x > \"$S/a\"")                                  # 管線：子 shell
    assert _unknown(f"(S='{_C5_SCRATCH}') && echo x > \"$S/a\"")                               # 子 shell 不外溢
    assert _unknown(f"S='{_C5_SCRATCH}' && echo x > '$S/a'")                                   # 單引號裡的 $ 是字面
    assert _unknown(f"S='{_C5_SCRATCH}' && unset S && echo x > \"$S/a\"")
    assert _unknown(f"S='{_C5_SCRATCH}' echo x > \"$S/a\"")                                    # 前綴指定：$S 在指定前就展開
    # codex 006：條件式指定（前面接 &&／||）跑不跑看前一段，不能拿來代換——否則真正寫的舊值目標被算成 scratchpad
    assert _unknown(f"S=C:/repo/memory; false && S='{_C5_SCRATCH}'; printf x > \"$S/卡.md\"")
    assert _unknown(f"cd sub || S='{_C5_SCRATCH}'; echo x > \"$S/a\"")


def test_006_c5_command_blames_the_inline_code_segment():
    """C5 原指令修完後：scratchpad 那幾段算得出目標（上一案）；整條仍被擋（python -c 用 importlib 跑檔，INLINE_PY_READONLY 照擋），
    但判不出的段與原因都指到 python -c 那段，不再是 git show 那段配上「內嵌碼：importlib」。算得出的目標照列、UNKNOWN 那一筆
    在最後（規則 UNKNOWN_PART_KEEPS_KNOWN_TARGETS：舊碼有 UNKNOWN 就只回那一筆，把同一條指令明確的目標蓋掉）。"""
    got = write_paths_from_tool("Bash", {"command": _C5_CMD}, CWD)
    unknown = [g for g in got if g.startswith("UNKNOWN:")]
    assert len(unknown) == 1 and got[-1] == unknown[0] and unknown[0].startswith("UNKNOWN:python -c"), got
    assert "內嵌碼：內嵌碼匯入 importlib" in unknown[0] and any(g.endswith("old_pricing.py") for g in got), got
    got = write_paths_from_tool("Bash", {"command": "echo x > \"$Q/a\"; python -c \"import shutil\""}, CWD)
    assert len(got) == 1 and got[0].startswith("UNKNOWN:echo") and "內嵌碼" not in got[0], got


def test_004_python_heredoc_and_import_alias_judged_by_ast():
    """第三跑 B-1／B-2：`python - <<'EOF'` 的內文、`import x as y` 取別名都交 ast 判（規則 INLINE_PY_READONLY）：純讀放行；
    寫檔照 UNKNOWN 並帶出 ast 判出的原因；shell 會展開的 heredoc（定界符沒引號又含 $）判不準照擋。"""
    assert _bash("python - <<'EOF'\nimport json\nprint(json.load(open('a.json'))['k'])\nEOF") == []
    assert _bash("python -c \"import tests.test_report as t\nprint(t.__doc__)\"") == []                     # B-1 第 262 行（多行）
    assert _bash("python -c \"import inspect, sales.store as s\nprint(inspect.getsource(s.load))\"") == []    # B-2 第 66 行第二段
    got = write_paths_from_tool("Bash", {"command": "python - <<'EOF'\nimport json\nopen('x','w')\nEOF"}, CWD)
    assert len(got) == 1 and got[0].startswith("UNKNOWN:python -") and "內嵌碼：open(…, 'w') 會寫檔" in got[0], got
    assert _unknown("python - <<EOF\nprint('$HOME')\nEOF")
    assert _unknown("python -c \"import builtins as b\nb.exec('1')\"")                                      # 取別名的動態執行照擋
    assert _unknown("python -c \"import builtins;builtins.exec('1')\"")


def test_004_python_stdin_heredoc_judged_only_when_it_is_the_program():
    """codex 004：`python -` 的程式是最後一份 heredoc、`<` 也會換掉它；有多份 heredoc 或另有輸入重導向就判不了（照 UNKNOWN），
    不拿第一份去判（第一份唯讀、第二份寫檔時會漏擋）。只有一份照 ast 判。"""
    assert _unknown("python - <<'A' <<'B'\nprint(1)\nA\nopen('x.txt','w').write('1')\nB\n")
    assert _unknown("python - <<'A' < other.py\nprint(1)\nA\n")
    assert _bash("python - <<'A'\nprint(1)\nA\n") == []


def test_045_inline_py_readonly_python_c_pure_read_is_not_a_write():
    """規則 INLINE_PY_READONLY：python -c 只讀（ast 判）→ 沒有寫入訊號；有寫檔／刪搬／子行程 → 照 UNKNOWN。"""
    assert _bash("python3 -c 'print(1)'") == []
    assert _bash("python -X utf8 -c \"import json;print(json.load(open('a.json'))['k'])\"") == []
    assert _bash("python -c \"import json;print(1)\" | head -3") == []
    assert _unknown("python -c \"import os;os.remove('a')\"")
    assert _unknown("python -c \"import shutil;print(1)\"")
    assert _unknown("python -c \"import subprocess;subprocess.run(['x'])\"")
    assert _unknown("python -c \"from pathlib import Path;Path('a').write_text('x')\"")
    assert _bash("python -c \"print(1)\" > out.txt") == ["C:/Work/Proj/out.txt"]                     # 重導向照算目標


def test_r4_iofile_static_call_is_unknown():
    got = write_paths_from_tool("PowerShell", {"command": "[IO.File]::WriteAllText('x','y')"}, CWD)
    assert len(got) == 1 and got[0].startswith("UNKNOWN:")


# BLOCK 3（R4 子 shell／替換；R5 作用域）
def test_r5_subshell_targets_counted():
    assert _bash("(tee a.py)") == ["C:/Work/Proj/a.py"]


def test_r4_command_substitution_with_write_is_unknown():
    assert _unknown("echo $(tee a.py)") and _unknown("echo `tee a.py`")
    assert _bash("echo $(pwd)") == [] and _bash("echo `date` > a.py") == ["C:/Work/Proj/a.py"]


def test_r4_cd_then_pipe_is_unknown():
    assert _unknown("cd src | cat; echo x > a.py")


def test_r4_cd_then_or_is_unknown():
    assert _unknown("cd src || echo x > a.py")


def test_r5_subshell_cd_does_not_leak():
    assert _bash("(cd src; echo x > a.py); echo y > b.py") == ["C:/Work/Proj/src/a.py", "C:/Work/Proj/b.py"]
    assert _bash("(cd src); echo x > a.py") == ["C:/Work/Proj/a.py"]


def test_r5_cd_applies_after_semicolon_and_and():
    assert _bash("cd src; echo x > a.py") == ["C:/Work/Proj/src/a.py"]
    assert _bash("cd src && echo x > a.py") == ["C:/Work/Proj/src/a.py"]
    assert _bash("cd src\necho x > a.py") == ["C:/Work/Proj/src/a.py"]


def test_r5_cd_on_right_of_or_or_pipe_does_not_leak():
    assert _bash("true || cd src; echo x > a.py") == ["C:/Work/Proj/a.py"]
    assert _bash("cat f | cd src; echo x > a.py") == ["C:/Work/Proj/a.py"]


# BLOCK 4／5（R1 前處理）
def test_r1_quoted_heredoc_marker_is_not_heredoc():
    assert _bash('echo "<<EOF"; echo x > a.py') == ["C:/Work/Proj/a.py"]
    assert _bash("echo '<<EOF' > a.py") == ["C:/Work/Proj/a.py"]


def test_r1_line_continuation_joins_target():
    assert _bash("echo x > \\\na.py") == ["C:/Work/Proj/a.py"]


def test_r1_comment_stripped_before_scan():
    assert _bash("echo ok # > $x\necho y > b.py") == ["C:/Work/Proj/b.py"]
    assert _bash("echo a#b > c.py") == ["C:/Work/Proj/c.py"]                     # 字中間的 # 不是註解


# BLOCK 6（R0 沒有寫入訊號一律 []）
def test_r0_cd_var_then_ls_is_empty():
    assert _bash("cd $DIR && ls") == []


def test_r0_cd_dash_is_empty():
    assert _bash("cd -") == []


def test_r0_eval_without_write_is_empty():
    assert _bash('eval "pwd"') == []


def test_r0_comment_with_redirect_is_empty():
    assert _bash("echo ok # > $x") == []


def test_r0_readonly_commands_with_gt_in_quotes_are_empty():
    assert _bash("ls | grep '>'") == [] and _bash("git log --format='%H > %s'") == []


def test_unknown_target_is_allowed_and_logged(tmp_path, monkeypatch):
    """規則 UNKNOWN_TARGET_LOGGED：判不出寫入目標 → 放行並留帳（不擋）。"""
    import wg_overview as wo
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    warn, deny, hit = wo.write_check("s", "UNKNOWN:echo x > $OUT/a", {})
    assert deny is None and hit is None
    log = (tmp_path / "hub.log").read_text(encoding="utf-8")
    assert '"edit_unknown_target"' in log and '"allowed": true' in log


# ─── 007 T1.3：跨層閘把寫到 $TEMP 當成寫根層（A3 A-1 transcript 第 85 行）────────────────

def test_007_shell_env_var_expanded(monkeypatch):
    """規則 SHELL_ENV_VAR_EXPANDED：指令裡沒碰過的環境變數照 hook 行程的環境值代換（同 $HOME 理），算得出寫到暫存目錄；
    碰過（條件式指定、for、read）、環境裡沒有、大小寫不同、PWD 這類 shell 自己改的、source 之後、PowerShell 照舊判不出。
    反例都先把 TEMP／PWD 設進環境：判不出是因為規則，不是因為環境裡本來就沒有。"""
    tmp = "C:/Users/me/AppData/Local/Temp"
    monkeypatch.setenv("TEMP", tmp)
    monkeypatch.setenv("PWD", "C:/Elsewhere")
    monkeypatch.delenv("NOPE_NOT_SET", raising=False)
    assert _bash('mkdir -p "$TEMP/qa2-old"') == [tmp + "/qa2-old"]
    assert _bash("cp a.py ${TEMP}/b.py") == [tmp + "/b.py"]
    assert _bash('cd "$TEMP" && echo x > a.txt') == [tmp + "/a.txt"]                       # cd 到環境變數之後的相對目標
    assert _bash('S=C:/w/sp && echo x > "$S/a" && echo y > "$TEMP/b"') == ["C:/w/sp/a", tmp + "/b"]   # 與字面指定並用
    assert _bash('S="$TEMP/old" && echo x > "$S/a"') == [tmp + "/old/a"]                     # 指定值裡的環境變數先代換，S 就是字面
    # 反例：判不出的照判不出
    assert _unknown('false && TEMP=~/.claude/hooks; mkdir -p "$TEMP/x"')     # 條件式指定過（跑不跑看前一段）
    assert _unknown('for TEMP in ~/.claude/hooks; do echo x > "$TEMP/x"; done')
    assert _unknown('read -r TEMP; echo x > "$TEMP/a"')
    assert _unknown('mkdir -p "$NOPE_NOT_SET/x"')                            # 環境裡沒有
    assert _unknown('mkdir -p "$temp/x"')                                    # 大小寫不同
    assert _unknown('cd C:/Work && echo x > "$PWD/a"')                       # cd 會改 PWD
    assert _unknown('source env.sh; mkdir -p "$TEMP/x"')                     # source 讀進來的檔可能改任何變數
    ps = write_paths_from_tool("PowerShell", {"command": 'New-Item -Path "$TEMP/x"'}, CWD)
    assert len(ps) == 1 and ps[0].startswith("UNKNOWN:"), ps                 # PowerShell 的 $TEMP 是 PS 變數


def test_008_unknown_part_keeps_known_targets():
    """UNKNOWN_PART_KEEPS_KNOWN_TARGETS：同段的參數像內嵌碼、或別段的目標展不開，看得懂的目標照列，UNKNOWN 那一筆在最後。"""
    got = write_paths_from_tool("Bash", {"command": "rm -rf /x/keep.py '[System.IO.Directory]::'"}, "/x")
    assert got[0].endswith("keep.py") and got[-1].startswith("UNKNOWN:") and len(got) == 3, got   # 那個參數本身也是 rm 的目標
    got = write_paths_from_tool("Bash", {"command": 'rm /x/a.py; echo hi > "$NOPE_X_008/out"'}, "/x")
    assert len(got) == 2 and got[0].endswith("a.py") and got[1].startswith("UNKNOWN:echo"), got

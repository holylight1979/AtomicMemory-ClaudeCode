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

from wg_core import write_paths_from_tool  # noqa: E402

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


def test_write_targets_cp_into_existing_directory(tmp_path):
    (tmp_path / "out").mkdir()
    got = _n(write_paths_from_tool("Bash", {"command": "cp a.py out"}, str(tmp_path)))
    assert got == [str(tmp_path / "out" / "a.py").replace("\\", "/")]


def test_write_targets_edit_relative_path_is_absolutized():
    assert _n(write_paths_from_tool("Edit", {"file_path": "rel/a.py"}, CWD)) == ["C:/Work/Proj/rel/a.py"]
    assert _n(write_paths_from_tool("Write", {"file_path": "C:/Work/Proj/x.py"}, CWD)) == ["C:/Work/Proj/x.py"]


def test_write_targets_quoted_gt_is_not_redirect():
    assert write_paths_from_tool("Bash", {"command": "echo 'x > out.md'"}, CWD) == []
    assert write_paths_from_tool("Bash", {"command": 'echo "a > b" | grep x'}, CWD) == []


def test_write_targets_heredoc_body_is_not_scanned():
    assert write_paths_from_tool("Bash", {"command": "python - <<EOF\nprint(1 > 0)\nEOF"}, CWD) == []
    got = _n(write_paths_from_tool("Bash", {"command": "cat > n.txt <<'EOT'\nhello > z\nEOT"}, CWD))
    assert got == ["C:/Work/Proj/n.txt"]                                                   # 標記行本身的 > 仍算


def test_write_targets_tee_to_devnull_has_no_phantom():
    assert _n(write_paths_from_tool("Bash", {"command": "tee out.md > /dev/null"}, CWD)) == ["C:/Work/Proj/out.md"]
    assert _n(write_paths_from_tool("Bash", {"command": "tee -a C:/Work/Proj/l.log 2>&1 | head"}, CWD)) == ["C:/Work/Proj/l.log"]


@pytest.mark.parametrize("cmd", [
    "echo x > $OUT/a",                 # 展不開的變數
    "echo x > %TEMP%/a",               # Windows 變數
    "eval echo x > a",                 # eval
    "cd - && echo x > a",              # cd -
    "echo x >",                        # 孤兒重導向
    "Set-Content -Path $env:TEMP/a -Value x",
])
def test_write_targets_unparseable_is_unknown(cmd):
    got = write_paths_from_tool("Bash", {"command": cmd}, CWD)
    assert len(got) == 1 and got[0].startswith("UNKNOWN:"), got


def test_unknown_target_is_denied(tmp_path, monkeypatch):
    import wg_overview as wo
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    warn, deny, changed = wo.on_edit({}, "s", "UNKNOWN:echo x > $OUT/a", "", {})
    assert deny and "改用 Edit／Write" in deny and not changed
    assert '"deny_reason": "unknown_target"' in (tmp_path / "hub.log").read_text(encoding="utf-8")

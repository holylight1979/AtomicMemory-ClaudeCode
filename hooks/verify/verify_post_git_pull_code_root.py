"""verify_post_git_pull_code_root.py：post-git-pull.sh 跑的 memory-conflict-detector 來自腳本自己的樹；找不到才用家目錄，該出聲就出聲。

做什麼：把本樹的 post-git-pull.sh 複製進 tmp 程式碼樹（路徑含空白），tmp/code/tools/ 與 tmp家/.claude/tools/ 各放一支
探針 detector（只寫「誰被跑」的標記）；curl 換成一跑就失敗的替身（不碰本機的向量服務）。
- 直接跑程式碼樹那份（路徑含空白）→ 跑程式碼樹那支，不出聲。
- 複製安裝到專案 .git/hooks/post-merge（旁邊本來就沒有 tools/）→ 跑家目錄那支，不出聲（一般安裝不變）。
- readlink -f 失敗（替身 readlink 一跑就失敗）＋複製安裝 → 跑家目錄那支，stderr 一行「符號連結解析失敗…改用 <路徑>」。
- 真符號連結指向程式碼樹 → 跑程式碼樹那支；指向沒有 tools/ 的樹 → 家目錄那支並出聲。需要建符號連結的權限，沒有就跳過。
反例：退回舊碼（DETECTOR 寫死 ${HOME}/.claude/tools，或解析失敗不出聲）→ 直接跑案、解析失敗案紅。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_post_git_pull_code_root.py（需要 Git Bash）
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TREE = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash")
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
PROBE = "open(r'{marks}', 'a', encoding='utf-8').write('{who}\\n')\n"
needs_git_bash = pytest.mark.skipif(not BASH or "system32" in BASH.lower(), reason="需要 Git Bash（不用 WSL 的 bash）")


@pytest.fixture
def world(tmp_path):
    marks = tmp_path / "ran.txt"
    code = tmp_path / "code tree with space"
    (code / "hooks").mkdir(parents=True)
    (code / "tools").mkdir()
    shutil.copyfile(TREE / "hooks" / "post-git-pull.sh", code / "hooks" / "post-git-pull.sh")
    (code / "tools" / "memory-conflict-detector.py").write_text(PROBE.format(marks=marks, who="code-tree"), encoding="utf-8")
    home = tmp_path / "home"
    (home / ".claude" / "tools").mkdir(parents=True)
    (home / ".claude" / "tools" / "memory-conflict-detector.py").write_text(PROBE.format(marks=marks, who="home"),
                                                                           encoding="utf-8")
    proj = tmp_path / "proj"
    (proj / ".claude" / "memory" / "shared").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(proj)], check=True, capture_output=True, creationflags=NO_WINDOW)
    shim = tmp_path / "shim"
    shim.mkdir()
    (shim / "curl").write_bytes(b"#!/bin/sh\nexit 7\n")                                  # 不碰本機向量服務
    broken = tmp_path / "shim-readlink"
    broken.mkdir()
    (broken / "readlink").write_bytes(b"#!/bin/sh\nexit 1\n")                            # readlink -f 失敗
    return {"marks": marks, "code": code, "home": home, "proj": proj, "shim": shim, "broken": broken}


def _run(w, script: Path, extra_path: Path = None):
    w["marks"].unlink(missing_ok=True)
    env = {k: v for k, v in os.environ.items() if k != "WG_CLAUDE_DIR"}
    path = os.pathsep.join(str(p) for p in (extra_path, w["shim"]) if p) + os.pathsep + os.environ.get("PATH", "")
    env.update({"HOME": str(w["home"]), "USERPROFILE": str(w["home"]), "PATH": path})
    r = subprocess.run([BASH, script.as_posix()], cwd=str(w["proj"]), env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120, creationflags=NO_WINDOW)
    assert r.returncode == 0, r.stderr[-2000:]
    ran = w["marks"].read_text(encoding="utf-8").split() if w["marks"].exists() else []
    return ran, [ln for ln in r.stderr.splitlines() if "post-merge：" in ln]


def _installed_copy(w) -> Path:
    dst = w["proj"] / ".git" / "hooks" / "post-merge"
    shutil.copyfile(w["code"] / "hooks" / "post-git-pull.sh", dst)
    return dst


@needs_git_bash
def test_direct_run_uses_script_tree_even_with_spaces_and_copy_install_uses_home_silently(world):
    assert _run(world, world["code"] / "hooks" / "post-git-pull.sh") == (["code-tree"], [])   # 反例：舊碼跑家目錄那支
    assert _run(world, _installed_copy(world)) == (["home"], [])                              # 複製安裝：一般安裝不變、不出聲


@needs_git_bash
def test_readlink_failure_falls_back_to_home_with_one_stderr_line(world):
    ran, notes = _run(world, _installed_copy(world), extra_path=world["broken"])
    assert ran == ["home"]
    assert len(notes) == 1 and "符號連結解析失敗" in notes[0], notes                         # 反例：舊碼靜默改用家目錄
    assert ".claude/tools/memory-conflict-detector.py" in notes[0], notes                  # 說明改用哪支


@needs_git_bash
def test_real_symlink_follows_target_tree_or_says_why(world, tmp_path):
    link = world["proj"] / ".git" / "hooks" / "post-merge"
    try:
        os.symlink(world["code"] / "hooks" / "post-git-pull.sh", link)
    except OSError as e:                                                                 # Windows 沒開開發人員模式沒有權限
        pytest.skip(f"這台機器不能建符號連結：{e}")
    assert _run(world, link) == (["code-tree"], [])
    bare = tmp_path / "bare tree" / "hooks"
    bare.mkdir(parents=True)
    shutil.copyfile(world["code"] / "hooks" / "post-git-pull.sh", bare / "post-git-pull.sh")
    link.unlink()
    os.symlink(bare / "post-git-pull.sh", link)
    ran, notes = _run(world, link)
    assert ran == ["home"] and len(notes) == 1 and "沒有 tools/" in notes[0], notes

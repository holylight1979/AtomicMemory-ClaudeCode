"""verify_post_git_pull_code_root.py：post-git-pull.sh 跑的 memory-conflict-detector 來自腳本自己的樹；複製安裝才用家目錄。

做什麼：把本樹的 post-git-pull.sh 複製進 tmp 程式碼樹（tmp/code/hooks/），tmp/code/tools/ 與 tmp家/.claude/tools/ 各放一支
探針 detector（只寫「誰被跑」的標記）；curl 換成一跑就失敗的替身（不碰本機的向量服務）。
- 直接跑 tmp/code/hooks/post-git-pull.sh → 跑的是 tmp 程式碼樹那支。
- 複製安裝到專案 .git/hooks/post-merge（旁邊沒有 tools/）→ 跑的是家目錄那支（一般安裝不變）。
反例：退回舊碼（DETECTOR 寫死 ${HOME}/.claude/tools）→ 直接跑也跑到家目錄那支。
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


@pytest.mark.skipif(not BASH or "system32" in BASH.lower(), reason="需要 Git Bash（不用 WSL 的 bash）")
def test_detector_comes_from_script_tree_and_copy_install_falls_back_to_home(tmp_path):
    marks = tmp_path / "ran.txt"
    code = tmp_path / "code"
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
    env = {k: v for k, v in os.environ.items() if k != "WG_CLAUDE_DIR"}
    env.update({"HOME": str(home), "USERPROFILE": str(home), "PATH": str(shim) + os.pathsep + os.environ.get("PATH", "")})

    def run(script: Path) -> list:
        marks.unlink(missing_ok=True)
        r = subprocess.run([BASH, script.as_posix()], cwd=str(proj), env=env, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120, creationflags=NO_WINDOW)
        assert r.returncode == 0, r.stderr[-2000:]
        return marks.read_text(encoding="utf-8").split() if marks.exists() else []

    assert run(code / "hooks" / "post-git-pull.sh") == ["code-tree"]                    # 反例：舊碼跑家目錄那支
    installed = proj / ".git" / "hooks" / "post-merge"
    shutil.copyfile(code / "hooks" / "post-git-pull.sh", installed)
    assert run(installed) == ["home"]                                                   # 複製安裝：一般安裝不變

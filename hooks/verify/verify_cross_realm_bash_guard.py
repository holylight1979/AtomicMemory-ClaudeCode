"""verify_cross_realm_bash_guard.py — Cross-Realm Bash Block 守門。

實證破口（2026-09-01）：CrossRealmWriteBlock 只看 Write/Edit；專案 session 以
`cd ~/.claude && python - <<EOF … write_text` 改根層 hooks、再 `git add && git commit`，整條沒被擋。

不變式：
1. 專案 session：根層上下文（cd ~/.claude／git -C／命令列指到核心路徑）× 動手操作
   （heredoc、內嵌 python、redirect、sed -i、cp/mv/rm、git add/commit/push、PowerShell 寫入 cmdlet）→ deny。
2. 專案 session 純跑根層工具（`python ~/.claude/tools/x.py …`，不 cd 進去）→ 放行；
   而且「跑根層工具」不構成根層上下文——同一條命令裡用 heredoc python／cp rm／git add push
   動**自己專案**的 .claude/memory 也放行（只有命令其餘部分仍指到根層路徑才擋）。
   grep 樣式裡的 `<<<<<<<` 衝突標記不是 heredoc。
3. 專案 session 在根層上下文做唯讀（sed -n / grep / cat）→ 放行。
4. 寫專案自己的 .claude 層、寫 ~/.claude/memory（atom funnel 管）→ 放行。
5. 核心 session（cwd ∈ ~/.claude）→ 一律放行；config guard.cross_realm_bash.enabled=false／allowlist 命中 → 放行。
6. 非 Bash/PowerShell 工具、cwd 缺失 → fail-open。
"""
from __future__ import annotations

import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

from wg_core import check_cross_realm_bash  # noqa: E402

HOME_CLAUDE = (Path.home() / ".claude").as_posix()
PROJ = "C:/FakeProj/game-x" if sys.platform == "win32" else "/tmp/fakeproj/game-x"
CFG = {"guard": {"cross_realm_bash": {"enabled": True, "allowlist": []}}}


def _b(cmd: str) -> dict:
    return {"command": cmd}


def _denied(cmd: str, cwd: str = PROJ, cfg=CFG, tool: str = "Bash") -> bool:
    msg = check_cross_realm_bash(tool, _b(cmd), cwd, cfg)
    return bool(msg and "CrossRealmBashBlock" in msg)


def test_inline_python_heredoc_after_cd_root_denied():
    assert _denied("cd ~/.claude && export PYTHONIOENCODING=utf-8 && python - <<'EOF'\nfrom pathlib import Path\nPath('hooks/x.py').write_text('x')\nEOF")


def test_root_git_commit_from_project_denied():
    assert _denied("cd ~/.claude && git add hooks/handlers/session_start.py && git commit -m x")
    assert _denied(f"git -C {HOME_CLAUDE} commit -am x")
    assert _denied("cd ~/.claude && git push origin main")


def test_direct_core_path_write_ops_denied():
    assert _denied(f"echo hi > {HOME_CLAUDE}/hooks/wg_core.py")
    assert _denied(f"sed -i 's/a/b/' {HOME_CLAUDE}/lib/atom_io.py")
    assert _denied(f"cp foo.py {HOME_CLAUDE}/tools/")
    assert _denied("python -c \"open(r'C:/Users/me/.claude/skills/x/SKILL.md','w')\"")
    assert _denied(f"cat > {HOME_CLAUDE}/settings.json <<'EOF'\n{{}}\nEOF")


def test_powershell_write_cmdlets_denied():
    assert _denied(f"Set-Content -Path {HOME_CLAUDE}/hooks/x.py -Value 'y'", tool="PowerShell")
    assert _denied("Set-Location ~/.claude; Copy-Item a.py hooks/", tool="PowerShell")


def test_running_root_tools_without_cd_allowed():
    assert not _denied(f"python {HOME_CLAUDE}/tools/sync-atom-index.py --memory-dir C:/FakeProj/game-x/.claude/memory --check")
    assert not _denied(f"python {HOME_CLAUDE}/tools/classify-project-scope.py plan")
    # fd 複製（2>&1 / >&2）不是寫檔；&>/>&+檔案 才是真重導寫檔
    assert not _denied(f"python {HOME_CLAUDE}/tools/classify-project-scope.py plan 2>&1 | head -60")
    assert not _denied(f"python {HOME_CLAUDE}/tools/atom-categorize.py plan --memory-dir D:/Proj/.claude/memory 2>&1 | head -80")
    assert not _denied(f"python {HOME_CLAUDE}/tools/x.py >&2")
    assert _denied(f"python {HOME_CLAUDE}/tools/x.py &> {HOME_CLAUDE}/hooks/out.txt")
    assert _denied(f"python {HOME_CLAUDE}/tools/x.py >& {HOME_CLAUDE}/hooks/out.txt")
    assert not _denied(f"PYTHONIOENCODING=utf-8 python {HOME_CLAUDE}/tools/health-weekly.py")


def test_root_tool_plus_project_memory_write_allowed():
    """實錄（專案 session cwd=C:\\Projects 刪錯誤 atom）：一條命令跑根層索引工具＋動自己專案的
    .claude/memory，整條被當成改根層誤擋。跑根層工具不算根層上下文。"""
    # grep 樣式的衝突標記 `<<<<<<<` 不是 heredoc
    assert not _denied("ls ~/.claude/tools/*.py 2>/dev/null | grep -i index; "
                       "for f in .claude/memory/MEMORY.md; do echo \"$f: $(grep -c '^<<<<<<<' \"$f\")\"; done")
    # heredoc python 動專案索引 + 跑根層 sync 工具
    assert not _denied("python - <<'EOF'\nimport json\nprint(1)\nEOF\n"
                       f"python {HOME_CLAUDE}/tools/sync-memory-index.py --write --memory-dir C:/FakeProj/game-x/.claude/memory 2>&1 | tail -1")
    # python -c 純讀 + 根層工具 + 專案 repo 的 git add/push（不是根層 repo）
    assert not _denied("python -c \"import json;json.load(open(r'.claude/memory/_atom_index.json'))\" && "
                       f"python {HOME_CLAUDE}/tools/sync-memory-index.py --write --memory-dir C:/FakeProj/game-x/.claude/memory && "
                       "git add .claude/memory/MEMORY.md && git push origin master")
    # cp/rm 專案 atom + 引號包住的根層工具絕對路徑
    assert not _denied("BAD=\"c:/FakeProj/game-x/.claude/memory/shared/x.md\"\ncp \"$BAD\" \"C:/Users/ME~1/AppData/Local/Temp/b.md\"\nrm \"$BAD\"\n"
                       f"python \"{HOME_CLAUDE}/tools/sync-atom-index.py\" --project-cwd \"c:/FakeProj/game-x\" 2>&1 | tail -8")
    # 根層工具輸出 pipe 進 python -c
    assert not _denied(f"python {HOME_CLAUDE}/tools/sync-atom-index.py --memory-dir c:/FakeProj/game-x/.claude/memory --check 2>&1 | "
                       "python -c \"import sys;print(sys.stdin.read()[:10])\"")
    # 跑完根層工具後命令其餘部分仍指到根層路徑 → 照擋
    assert _denied(f"python {HOME_CLAUDE}/tools/x.py > {HOME_CLAUDE}/hooks/out.txt")
    assert _denied(f"python {HOME_CLAUDE}/tools/x.py && cp a.py {HOME_CLAUDE}/hooks/")
    assert _denied(f"python {HOME_CLAUDE}/tools/x.py && git -C {HOME_CLAUDE} commit -am x")


def test_readonly_in_root_context_allowed():
    assert not _denied("cd ~/.claude && sed -n 1,40p hooks/wg_core.py")
    assert not _denied("cd ~/.claude/hooks && grep -rn 'get_current_user' . | head")
    assert not _denied(f"cat {HOME_CLAUDE}/lib/atom_io.py | head -50")
    assert not _denied("cd ~/.claude && git status --short && git log --oneline -3")


def test_project_own_layer_and_memory_allowed():
    assert not _denied("cd C:/FakeProj/game-x && python - <<'EOF'\nprint(1)\nEOF")
    assert not _denied(f"echo x > {HOME_CLAUDE}/memory/personal/me/note.md")
    assert not _denied("git add .claude/memory && git commit -m 'memory'")


def test_core_session_and_config_escape():
    cmd = "cd ~/.claude && python - <<'EOF'\nprint(1)\nEOF"
    assert not _denied(cmd, cwd=HOME_CLAUDE + "/hooks")
    assert not _denied(cmd, cfg={"guard": {"cross_realm_bash": {"enabled": False}}})
    assert not _denied(cmd, cfg={"guard": {"cross_realm_bash": {"enabled": True, "allowlist": ["print(1)"]}}})
    assert not _denied(cmd, cwd="")


def test_non_shell_tools_ignored():
    assert check_cross_realm_bash("Write", {"file_path": HOME_CLAUDE + "/hooks/x.py"}, PROJ, CFG) is None
    assert check_cross_realm_bash("Bash", {}, PROJ, CFG) is None

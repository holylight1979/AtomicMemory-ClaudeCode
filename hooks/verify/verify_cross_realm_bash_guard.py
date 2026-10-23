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

from wg_core import CLAUDE_DIR, check_cross_realm_bash  # noqa: E402

HOME_CLAUDE = (Path.home() / ".claude").as_posix()
PROJ = "C:/FakeProj/game-x" if sys.platform == "win32" else "/tmp/fakeproj/game-x"
CFG = {"guard": {"cross_realm_bash": {"enabled": True, "allowlist": []}}}


def _b(cmd: str) -> dict:
    return {"command": cmd}


def _denied(cmd: str, cwd: str = PROJ, cfg=CFG, tool: str = "Bash") -> bool:
    msg = check_cross_realm_bash(tool, _b(cmd), cwd, cfg)
    return bool(msg and "CrossRealmBashBlock" in msg)


def test_inline_python_heredoc_after_cd_root_allowed_and_logged(tmp_path, monkeypatch):
    """規則 UNKNOWN_TARGET_LOGGED：cd 進根層後跑內嵌 python 寫檔，寫入目標判不出 → 放行並留帳 unknown_allowed（不再擋）。"""
    import json
    import wg_core
    monkeypatch.setattr(wg_core, "GUARD_LOG_DIR", tmp_path)
    cmd = "cd ~/.claude && export PYTHONIOENCODING=utf-8 && python - <<'EOF'\nfrom pathlib import Path\nPath('hooks/x.py').write_text('x')\nEOF"
    assert not _denied(cmd)
    rows = [json.loads(ln) for ln in (tmp_path / "guard-crossrealm.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert rows and rows[-1]["event"] == "unknown_allowed" and rows[-1]["allowed"] is True


def test_root_git_commit_from_project_denied():
    assert _denied("cd ~/.claude && git add hooks/handlers/session_start.py && git commit -m x")
    assert _denied(f"git -C {HOME_CLAUDE} commit -am x")
    assert _denied("cd ~/.claude && git push origin main")


def test_direct_core_path_write_ops_denied():
    assert _denied(f"echo hi > {HOME_CLAUDE}/hooks/wg_core.py")
    assert _denied(f"sed -i 's/a/b/' {HOME_CLAUDE}/lib/atom_io.py")
    assert _denied(f"cp foo.py {HOME_CLAUDE}/tools/")
    assert not _denied("python -c \"open(r'C:/Users/me/.claude/skills/x/SKILL.md','w')\"")   # 內嵌碼判不出目標：放行留帳
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
    """實錄（某專案 session 刪錯誤 atom）：一條命令跑根層索引工具＋動自己專案的
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
    assert not _denied(cmd, cwd=CLAUDE_DIR.as_posix() + "/hooks")   # 核心 session＝cwd 在資料根底下
    assert not _denied(cmd, cfg={"guard": {"cross_realm_bash": {"enabled": False}}})
    assert not _denied(cmd, cfg={"guard": {"cross_realm_bash": {"enabled": True, "allowlist": ["print(1)"]}}})
    assert not _denied(cmd, cwd="")


def test_045_git_readonly_subcmd_rule(tmp_path, monkeypatch):
    """規則 GIT_READONLY_SUBCMD：根層上下文裡的 git 每段都是唯讀子命令且寫入目標不在根層 → 放行；會寫的 git（hash-object -w、
    worktree add、branch -m：寫入訊號 regex 沒列到也算）→ 擋；PowerShell 換過目錄（Set-Location）後的相對寫入照擋；擋就留 guard-crossrealm.jsonl。"""
    import json
    import wg_core
    monkeypatch.setattr(wg_core, "GUARD_LOG_DIR", tmp_path)
    assert not _denied("git -C ~/.claude hash-object ~/.claude/hooks/x.py")
    assert not _denied("git -C ~/.claude show HEAD:hooks/x.py > C:/tmp/x.py && diff C:/tmp/x.py ~/.claude/hooks/x.py")
    assert _denied("git -C ~/.claude hash-object -w ~/.claude/hooks/x.py")
    assert _denied("git -C ~/.claude worktree add ../x")
    assert _denied("git -C ~/.claude branch -m a b")
    assert _denied("git -C ~/.claude show HEAD:hooks/x.py > ~/.claude/hooks/y.py")
    assert _denied("Set-Location ~/.claude; Copy-Item a.py hooks/", tool="PowerShell")      # 換過目錄的相對目標算不準，照擋
    log = tmp_path / "guard-crossrealm.jsonl"
    rows = [json.loads(ln) for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(rows) == 5 and all(r.get("rule") == "GIT_READONLY_SUBCMD" for r in rows) and rows[0].get("why")


def test_non_shell_tools_ignored():
    assert check_cross_realm_bash("Write", {"file_path": HOME_CLAUDE + "/hooks/x.py"}, PROJ, CFG) is None
    assert check_cross_realm_bash("Bash", {}, PROJ, CFG) is None


# ─── 007 T1.3：A3 表外誤擋（跨層閘把寫到 $TEMP 當成寫根層）────────────────────────────
# 原指令（A3 A-1 transcript 第 85 行，cwd 換成假專案）：看根層 skill 腳本的說明，再把專案 repo 的舊版 archive 到 $TEMP
_A3_CMD = (f"ls {HOME_CLAUDE}/skills/behavior-preservation/scripts/ && "
           f"python {HOME_CLAUDE}/skills/behavior-preservation/scripts/preserve-check.py --help; echo \"exit=$?\"; echo ---; "
           "mkdir -p \"$TEMP/qa2-old\" && cd /c/FakeProj/qa2-pricing && git archive HEAD pricing | tar -x -C \"$TEMP/qa2-old\" "
           "&& ls \"$TEMP/qa2-old/pricing\"; echo \"$TEMP/qa2-old\"")


def test_007_temp_target_and_project_repo_git_allowed(tmp_path, monkeypatch):
    """T1.3：寫到 $TEMP（SHELL_ENV_VAR_EXPANDED 照環境值代換）＋cd 到專案 repo 之後的 git archive（GIT_READONLY_SUBCMD 只算
    repo 在根層的 git 段）→ 放行、不留擋紀錄。兩個根因各自都會擋：只修一個照樣擋（下面兩條各留一個根因）。"""
    import wg_core
    monkeypatch.setattr(wg_core, "GUARD_LOG_DIR", tmp_path)
    monkeypatch.setenv("TEMP", "C:/Users/me/AppData/Local/Temp")
    assert not _denied(_A3_CMD)
    assert not (tmp_path / "guard-crossrealm.jsonl").exists()
    msg = check_cross_realm_bash("Bash", _b(_A3_CMD.replace("cd /c/FakeProj/qa2-pricing", "cd ~/.claude")), PROJ, CFG)
    assert msg and "git archive 不是唯讀子命令" in msg                          # git 段改在根層 repo：照擋
    monkeypatch.delenv("TEMP")
    assert check_cross_realm_bash("Bash", _b(_A3_CMD), PROJ, CFG) is None      # $TEMP 不在環境：算不出 → 放行留帳
    assert (tmp_path / "guard-crossrealm.jsonl").exists()                      # 前置：這個設定下會留紀錄（上面的「沒紀錄」才有意義）


def test_007_crossrealm_still_denies_and_logs_session_id(tmp_path, monkeypatch):
    """反例照擋：根層 repo 的 git archive、專案 repo 的 git 把檔寫進根層、eval 裡藏的 git（掃描器看不到，退回整條判）、
    mkdir／touch 進根層（預篩 regex 沒列、掃描器有寫入訊號）；條件式指定過的 TEMP、環境裡沒有的變數算不出目標 → 放行留帳。
    擋與放行的紀錄都帶 session_id。"""
    import json
    import wg_core
    monkeypatch.setattr(wg_core, "GUARD_LOG_DIR", tmp_path)
    monkeypatch.setenv("TEMP", "C:/Users/me/AppData/Local/Temp")
    monkeypatch.delenv("NOPE_NOT_SET", raising=False)
    unknown = ['false && TEMP=~/.claude/hooks; mkdir -p "$TEMP/x"', 'ls ~/.claude/hooks/ && mkdir -p "$NOPE_NOT_SET/x"']
    for cmd in unknown:
        assert check_cross_realm_bash("Bash", _b(cmd), PROJ, CFG, "sid-007") is None, cmd
    cmds = [
        "cd ~/.claude && git archive -o hooks/x.zip HEAD",
        "cd /c/FakeProj/qa2-pricing && git archive -o ~/.claude/hooks/x.zip HEAD",
        'ls ~/.claude/skills/ && eval "cd ~/.claude && git commit -am x"',
        "mkdir -p ~/.claude/hooks/x",
        "touch ~/.claude/hooks/x.py",
    ]
    for cmd in cmds:
        msg = check_cross_realm_bash("Bash", _b(cmd), PROJ, CFG, "sid-007")
        assert msg and "CrossRealmBashBlock" in msg, cmd
    rows = [json.loads(ln) for ln in (tmp_path / "guard-crossrealm.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(rows) == len(cmds) + len(unknown) and all(r.get("session_id") == "sid-007" for r in rows), rows
    assert [r.get("event") for r in rows[:len(unknown)]] == ["unknown_allowed"] * len(unknown)


def test_git_arg_flag_value_parsing(tmp_path):
    """_git_arg_reaches_root 的旗標取值（巢狀三元拆成 if／elif 之後行為不變）：長旗標取 = 後面、短旗標取黏著的值或 = 後面、
    單獨旗標沒有值；值是根層路徑才算碰到根層，repo 底下的相對路徑碰不到。"""
    import wg_core
    repo = str(tmp_path / "proj")
    root_x = str(CLAUDE_DIR / "hooks" / "x.zip").replace("\\", "/")
    cases = {f"--output={root_x}": True, "--output": False, f"-o{root_x}": True, f"-o={root_x}": True, "-o": False, "-": False,
             "--output=out/x.zip": False, "-oout/x.zip": False, root_x: True, "out/x.zip": False}
    got = {a: wg_core._git_arg_reaches_root(a, repo) for a in cases}
    assert got == cases, got


# ─── 008：唯讀指令不再誤擋（DOT_GIT_PATH_NOT_GIT_CALL、SEGMENTS_SPLIT_LIKE_SHELL）、迴圈與分支裡的寫入看得到（SHELL_KEYWORD_PREFIX_STRIPPED）

READONLY_PROBE_CMD = (
    'echo "=== project .git/hooks (non-sample)"; ls /c/w4/qc2-orders/.git/hooks | grep -v \'\.sample$\' || echo "(none)"; '
    'echo "=== ~/.claude/settings.json hook events"; python -c "\nimport json,pathlib\n'
    "p=pathlib.Path.home()/'.claude/settings.json'\nd=json.loads(p.read_text(encoding='utf-8'))\n"
    "for ev,arr in (d.get('hooks') or {}).items():\n    print(ev, len(arr))\n\""
)


def test_008_dot_git_path_and_multiline_quote_readonly_allowed():
    """實際誤擋過的唯讀指令：ls 專案的 .git/hooks、echo 提到 ~/.claude/settings.json、多行 python -c 讀它 → 放行。
    舊碼把 `.git` 當成 git 字樣（多於掃描器認到的 0 段 git）退回整條切段，又在多行引號的第一行切斷 →「引號不完整」照擋。"""
    import wg_core
    import wg_release_rules as rr
    assert not _denied(READONLY_PROBE_CMD)
    assert wg_core._GIT_WORD_RE.findall("ls a/.git/hooks; cat .git/HEAD; git status; git.exe log") == ["git", "git.exe"]
    segs = rr._shlex_segments('git log -1\npython -c "\nimport json\nprint(1)\n"\ngit status')
    assert segs == [["git", "log", "-1"], ["python", "-c", "\nimport json\nprint(1)\n"], ["git", "status"]]
    assert rr._shlex_segments('git status\necho "never closed') is None                   # 到最後引號仍不完整才算解析不了
    ro = 'cd ~/.claude && git log -1 && python -c "\nprint(1)\n" && echo $(date)'           # $( ) 退回整條判的那條路
    assert rr.git_readonly_verdict(ro, []).owed is True                                    # 命令替換照判不了（不是這次放寬的）
    assert rr.git_readonly_verdict('git log -1\npython -c "\nprint(1)\n"', []).owed is False
    assert rr.git_readonly_verdict('git log -1\npython -c "\nprint(1)\n"\ngit commit -m x', []).owed is True   # 引號後面的寫照擋


def test_008_shell_keyword_prefix_writes_seen(tmp_path, monkeypatch):
    """for／while 本體、if 分支、{ } 群組、! 開頭的段：剝掉保留字再認命令。寫到根層的照擋；目標帶迴圈變數 → 掃描器認得到、
    判不出目標，照 UNKNOWN_TARGET_LOGGED 放行留帳（舊碼整段沒看到，留帳也沒有）；if 分支裡的唯讀 git 放行。"""
    import json
    import wg_core
    import wg_release_rules as rr
    monkeypatch.setattr(wg_core, "GUARD_LOG_DIR", tmp_path)
    for cmd in ["if true; then mkdir ~/.claude/hooks/newdir; fi", "{ touch ~/.claude/hooks/x.py; }",
                "for f in a; do install -m644 /tmp/a ~/.claude/hooks/a.py; done", "! cp /tmp/a ~/.claude/hooks/a.py",
                "while true; do ln -sf /tmp/a ~/.claude/hooks/a.py; break; done"]:
        assert _denied(cmd), cmd
    loop = "cd ~/.claude && for f in hooks/a.py hooks/b.py; do sed -i 's/x/y/' $f; done"
    assert not _denied(loop)
    rows = [json.loads(ln) for ln in (tmp_path / "guard-crossrealm.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert rows[-1]["event"] == "unknown_allowed" and rows[-1]["cmd"] == loop
    assert wg_core.write_paths_from_tool("Bash", {"command": f"for f in a b; do rm {PROJ}/x.py; done"}, cwd=PROJ) == [
        str(Path(PROJ) / "x.py")]
    assert wg_core.write_paths_from_tool("Bash", {"command": "echo do then; printf '{'"}, cwd=PROJ) == []   # 參數裡的保留字不動
    assert not _denied("cd ~/.claude && if true; then git status; fi")
    assert rr._shlex_segments("for r in a; do git -C x status; done") == [["for", "r", "in", "a"], ["git", "-C", "x", "status"], ["done"]]


def test_008_delete_forms_into_root_denied():
    """DELETE_FORMS_SAME_ACROSS_SHELLS：rm -r（舊碼把 -r 當帶值旗標吃掉目標、整條放過）、PowerShell 的 rd／ri／del 別名刪根層 → 擋。"""
    assert _denied("rm -r ~/.claude/hooks/x.py")
    for cmd in ("rd -r ~/.claude/hooks", "ri ~/.claude/hooks/x.py", "del ~/.claude/hooks/x.py"):
        assert _denied(cmd, tool="PowerShell"), cmd
    assert not _denied("rm -r ./build", cwd=PROJ)

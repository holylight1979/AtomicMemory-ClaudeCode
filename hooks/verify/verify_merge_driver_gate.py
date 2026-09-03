"""verify_merge_driver_gate.py — PreToolUse 索引三檔合併驅動閘（advisory-only）。

驗證 handlers/pre_tool_use.check_merge_driver 與拆段器 _git_segments：
  - 拆段：quoted `-C "C:\\My Repo"`、`cd X && git …` 的 repo_cd 回退、`git.exe`、非目標子指令不出段
  - 省錢階梯：`git status`／`git add`／非 git 指令／auto_*:false → 零子行程（monkeypatch 計數）
  - PowerShell 與 Bash 同觸發
  - (B) 真 git：無驅動 merge 卡在三檔衝突 → `git commit` 前自動 --resolve → ls-files -u 清空、內容正確
  - 順序：check_merge_driver 在 handle_pre_tool_use 內排在 check_git_privacy 之前；resolver stage 三檔後
    隱私閘仍能 deny
  - (A) 真 git：乾淨 repo 跑 `git pull` → 自動 --install（GIT_CONFIG_GLOBAL／XDG_CONFIG_HOME 隔離）；
    第二次已裝 → None
  - 逾時：子行程 TimeoutExpired → 回 ⚠ advisory、不 raise；每次子行程 timeout ≤ 2.5s 總預算
真 git 題複用 tools/verify/verify_merge_atom_index.py 的 repo 建構 helper（複製，不跨目錄 import），
不裝任何 driver config、只掛 .gitattributes 的 merge=atomindex 屬性。
依賴 tools/merge-atom-index.py 的 CLI 契約（--resolve / --is-installed / --install --quiet）。
"""
from __future__ import annotations

import inspect
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

import handlers.pre_tool_use as ptu  # noqa: E402
from handlers.pre_tool_use import (  # noqa: E402
    _git_segments, _is_svn_resolve_trigger, _svn_segments, check_git_privacy, check_merge_driver,
    handle_pre_tool_use,
)

_NO_WINDOW = {"creationflags": 0x08000000} if os.name == "nt" else {}
INDEX_NAMES = ("MEMORY.md", "_ATOM_INDEX.md", "_atom_index.json")
CFG_ON = {"merge_driver": {"auto_install": True, "auto_resolve": True}}


# ─── 拆段（純函式）───────────────────────────────────────────────────────────

def test_segments_quoted_dash_c_path():
    segs = _git_segments('git -C "C:\\My Repo" pull --rebase', {"pull"})
    assert segs == [("C:\\My Repo", ["pull", "--rebase"])]


def test_segments_cd_fallback():
    segs = _git_segments("cd repo && git pull", {"pull"})
    assert segs == [("repo", ["pull"])]
    segs = _git_segments("cd repo; git pull", {"pull"})
    assert segs[0][0] == "repo"


def test_segments_git_exe_and_case():
    segs = _git_segments("git.exe rebase --continue", {"rebase"})
    assert segs == [("", ["rebase", "--continue"])]
    segs = _git_segments("GIT Rebase --continue", {"rebase"})
    assert segs and segs[0][1][0].lower() == "rebase"


def test_segments_non_target_subcommands_yield_nothing():
    merge_class = {"pull", "merge", "rebase", "cherry-pick", "stash", "commit"}
    assert _git_segments("git status", merge_class) == []
    assert _git_segments("git add x && git log --grep pull", merge_class) == []
    assert _git_segments("echo pull", merge_class) == []


def test_dash_c_wins_over_cd():
    segs = _git_segments('cd x && git -C "c:/r" commit -am "msg" | tee log', {"commit"})
    assert segs == [("c:/r", ["commit", "-am", "msg"])]


# ─── 省錢階梯（monkeypatch 子行程 helper 計數）──────────────────────────────

class _Spy:
    def __init__(self, rc=0, stdout="", stderr="", raise_exc=None):
        self.calls = []
        self.rc, self.stdout, self.stderr, self.raise_exc = rc, stdout, stderr, raise_exc

    def __call__(self, args, cwd, timeout):
        self.calls.append((list(args), cwd, timeout))
        if self.raise_exc:
            raise self.raise_exc
        return subprocess.CompletedProcess(args, self.rc, stdout=self.stdout, stderr=self.stderr)


@pytest.fixture
def spy(monkeypatch):
    s = _Spy()
    monkeypatch.setattr(ptu, "_run_capture", s)
    return s


def test_no_subprocess_for_non_trigger_commands(spy, tmp_path):
    for cmd in ("git status", "git add x", "git add .claude/memory/_atom_index.json",
                "git log --oneline", "ls -la", "git push origin main"):
        assert check_merge_driver("Bash", {"command": cmd}, str(tmp_path), CFG_ON) is None
    assert spy.calls == []


def test_non_shell_tool_ignored(spy, tmp_path):
    assert check_merge_driver("Write", {"command": "git pull"}, str(tmp_path), CFG_ON) is None
    assert spy.calls == []


def test_powershell_triggers_like_bash(spy, tmp_path):
    check_merge_driver("PowerShell", {"command": "git pull"}, str(tmp_path), CFG_ON)
    check_merge_driver("Bash", {"command": "git pull"}, str(tmp_path), CFG_ON)
    assert len(spy.calls) == 2
    assert all("--is-installed" in c[0] for c in spy.calls)


def test_auto_flags_off_means_zero_subprocess(spy, tmp_path):
    off = {"merge_driver": {"auto_install": False, "auto_resolve": False}}
    for cmd in ("git pull", "git rebase --continue", "git commit -m x", "git stash pop"):
        assert check_merge_driver("Bash", {"command": cmd}, str(tmp_path), off) is None
    assert spy.calls == []
    only_resolve = {"merge_driver": {"auto_install": False, "auto_resolve": True}}
    assert check_merge_driver("Bash", {"command": "git pull"}, str(tmp_path), only_resolve) is None
    assert spy.calls == []


def test_already_installed_returns_none(spy, tmp_path):
    assert check_merge_driver("Bash", {"command": "git pull"}, str(tmp_path), CFG_ON) is None
    assert len(spy.calls) == 1 and "--is-installed" in spy.calls[0][0]


def test_timeout_is_fail_open_with_warning(monkeypatch, tmp_path):
    s = _Spy(raise_exc=subprocess.TimeoutExpired(cmd="x", timeout=1))
    monkeypatch.setattr(ptu, "_run_capture", s)
    msg = check_merge_driver("Bash", {"command": "git pull"}, str(tmp_path), CFG_ON)
    assert msg and "⚠" in msg and "[Guardian:MergeDriver]" in msg
    msg = check_merge_driver("Bash", {"command": "git rebase --continue"}, str(tmp_path), CFG_ON)
    assert msg and "⚠" in msg and "[Guardian:IndexConflict]" in msg
    assert all(c[2] <= 2.5 for c in s.calls)


def test_generic_exception_is_silent_fail_open(monkeypatch, tmp_path, capsys):
    s = _Spy(raise_exc=RuntimeError("boom"))
    monkeypatch.setattr(ptu, "_run_capture", s)
    assert check_merge_driver("Bash", {"command": "git pull"}, str(tmp_path), CFG_ON) is None
    assert "fail-open" in capsys.readouterr().err


# ─── 順序：merge gate 在 privacy 之前 ─────────────────────────────────────

def test_merge_gate_runs_before_privacy_in_handler():
    body = inspect.getsource(handle_pre_tool_use)
    i_merge = body.index("check_merge_driver(")
    i_priv = body.index("check_git_privacy(")
    assert i_merge < i_priv
    assert '"allow"' not in body.split("check_merge_driver(")[1].split("check_git_privacy(")[0]


# ─── 真 git helpers（複製自 tools/verify/verify_merge_atom_index.py，不裝 driver）─────

def _index(*atoms):
    return {"version": "1.0", "atoms": [
        {"name": n, "path": p, "triggers": list(t), "scope": "shared"} for n, p, t in atoms]}


def _json_text(d, eol="\n"):
    return json.dumps(d, ensure_ascii=False, indent=2).replace("\n", eol)


def _md_table(*atoms):
    head = ["# Atom Trigger Index — Global", "", "> **Deprecated mirror.** Machine source: `_atom_index.json`.",
            "", "| Atom | Path | Trigger | Scope |", "|------|------|---------|-------|"]
    rows = [f"| {n} | {p} | {', '.join(t)} | shared |" for n, p, t in atoms]
    return "\n".join(head + rows) + "\n"


def _memory_md(counts, free_text="人寫的說明段。"):
    rows = "\n".join(f"| {k} | {v} | `memory/shared/{k}/` |" for k, v in counts.items())
    return (f"# Atom Index — Project\n\n{free_text}\n\n<!-- atom-catalog -->\n> 範疇目錄（自動生成）\n\n"
            f"| 範疇 | atom 數 | 深入 |\n|------|------|------|\n{rows}\n<!-- /atom-catalog -->\n")


A = ("a", "memory/shared/Server/a.md", ("port", "架構"))
B = ("b", "memory/shared/Server/b.md", ("build",))
C = ("c", "memory/shared/Tools/c.md", ("jenkins",))


def _git(repo, *args, check=True):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=20, **_NO_WINDOW)
    if check and r.returncode:
        raise AssertionError(f"git {' '.join(args)} failed rc={r.returncode}\n{r.stdout}\n{r.stderr}")
    return r


def _write_index_set(mem: Path, atoms, counts, json_eol="\n"):
    (mem / "_atom_index.json").write_bytes(_json_text(_index(*atoms), eol=json_eol).encode("utf-8"))
    (mem / "_ATOM_INDEX.md").write_bytes(_md_table(*atoms).encode("utf-8"))
    (mem / "MEMORY.md").write_bytes(_memory_md(counts).encode("utf-8"))
    for n, p, _t in atoms:
        f = mem.parent.parent / p.replace("memory/", ".claude/memory/", 1)
        f.parent.mkdir(parents=True, exist_ok=True)
        if not f.exists():
            f.write_text(f"# {n}\n", encoding="utf-8")


def _make_repo(tmp_path: Path) -> Path:
    """兩分支在索引三檔同區塊各加一列（必衝突）；不裝 driver config，只掛 attributes。"""
    repo = tmp_path / "proj"
    mem = repo / ".claude" / "memory"
    mem.mkdir(parents=True)
    _git(tmp_path, "init", "-q", "-b", "master", str(repo))
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "core.autocrlf", "false")
    (repo / ".gitattributes").write_text(
        "".join(f".claude/memory/{n} merge=atomindex text eol=lf\n" for n in INDEX_NAMES), encoding="utf-8")
    _write_index_set(mem, [A], {"Server": 1})
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "checkout", "-qb", "A")
    _write_index_set(mem, [A, B], {"Server": 2})
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "A adds b")
    _git(repo, "checkout", "-q", "master")
    _write_index_set(mem, [A, C], {"Server": 1, "Tools": 1}, json_eol="\r\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "master adds c")
    return repo


def _unmerged_paths(repo: Path) -> set:
    out = _git(repo, "ls-files", "-u", "-z").stdout
    return {e.split("\t", 1)[1] for e in out.split("\0") if "\t" in e}


@pytest.fixture
def isolated_git(monkeypatch, tmp_path):
    """global/system git config 隔離：測試不碰本機真設定，也不受本機已 --install 影響。"""
    gcfg = tmp_path / "gitconfig"
    gcfg.write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gcfg))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    return gcfg


def _cfg_get_global(key: str) -> str:
    return subprocess.run(["git", "config", "--global", "--get", key], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **_NO_WINDOW).stdout.strip()


# ─── (B) 真 git：merge 卡衝突 → git commit 前自動 --resolve ────────────────

def _conflicted_merge(tmp_path: Path) -> Path:
    repo = _make_repo(tmp_path)
    r = _git(repo, "merge", "A", "-m", "merge A", check=False)
    assert r.returncode != 0 and "CONFLICT" in r.stdout + r.stderr
    assert {f".claude/memory/{n}" for n in INDEX_NAMES} <= _unmerged_paths(repo)
    return repo


def test_resolve_before_commit_on_conflicted_merge(isolated_git, tmp_path, monkeypatch):
    """hook 邏輯題（解析／訊息／stage 結果）：預算放寬，與 resolver 本身快慢脫鉤——
    速度由 test_resolver_fits_hook_budget 單獨守。"""
    repo = _conflicted_merge(tmp_path)
    monkeypatch.setattr(ptu, "_MERGE_GATE_BUDGET_S", 30.0)
    msg = check_merge_driver("Bash", {"command": "git commit -m x"}, str(repo), CFG_ON)
    assert msg and "[Guardian:IndexConflict]" in msg, msg
    if "⚠" in msg:
        pytest.fail(
            "check_merge_driver 收到 resolver 失敗回報（多半是 tools/merge-atom-index.py 尚未實作 "
            f"--resolve 契約，非 hook 邏輯錯）：{msg}")
    assert not ({f".claude/memory/{n}" for n in INDEX_NAMES} & _unmerged_paths(repo))
    mem = repo / ".claude" / "memory"
    d = json.loads((mem / "_atom_index.json").read_text(encoding="utf-8"))
    assert sorted(a["name"] for a in d["atoms"]) == ["a", "b", "c"]
    mm = (mem / "MEMORY.md").read_text(encoding="utf-8")
    assert "| Server | 2 |" in mm and "| Tools | 1 |" in mm and "<<<<<<<" not in mm
    md = (mem / "_ATOM_INDEX.md").read_text(encoding="utf-8")
    assert "| b |" in md and "| c |" in md and "<<<<<<<" not in md

    # 順序面：resolver 已 stage 三檔 → 隱私閘在其後仍看得到、仍能 deny
    priv = check_git_privacy("Bash", {"command": "git commit -m x"}, str(repo),
                             {"privacy": {"deny_globs": ["_atom_index.json"]}})
    assert priv and "[Guardian:GitPrivacy]" in priv and "_atom_index.json" in priv


def test_resolver_fits_hook_budget(isolated_git, tmp_path):
    """真實預算題：hook 總時限 2.5s（整條 PreToolUse 鏈只有 5s），--resolve 在「未裝驅動＋三檔全衝突」
    的最差常見情境必須跑得完；跑不完 = 使用者每次都只會看到 ⚠ 逾時、自動化形同虛設。
    失敗時是 tools/merge-atom-index.py 的 git 呼叫次數問題（每次 spawn 在 Windows 約 0.1s），非 hook 邏輯。"""
    import time
    # 量兩次取最快（機器同時在跑別的東西時單次會被拖慢），兩次都超過才算真的太慢
    best, last_msg = 99.0, ""
    for n in range(2):
        sub = tmp_path / f"run{n}"
        sub.mkdir()
        repo = _conflicted_merge(sub)
        t0 = time.monotonic()
        msg = check_merge_driver("Bash", {"command": "git commit -m x"}, str(repo), CFG_ON)
        elapsed = time.monotonic() - t0
        assert msg and "[Guardian:IndexConflict]" in msg
        best, last_msg = min(best, elapsed), msg
        if "⚠" not in msg and elapsed <= ptu._MERGE_GATE_BUDGET_S + 0.5:
            break
    assert "⚠" not in last_msg and best <= ptu._MERGE_GATE_BUDGET_S + 0.5, (
        f"--resolve 未在 hook 預算 {ptu._MERGE_GATE_BUDGET_S}s 內完成（最快 {best:.2f}s）：{last_msg}")


def test_resolve_then_privacy_no_exception_even_if_unresolved(isolated_git, tmp_path):
    """不論 --resolve 是否成功，隱私閘接在後面都不得 raise（fail-open 鏈）。"""
    repo = _conflicted_merge(tmp_path)
    check_merge_driver("Bash", {"command": "git commit -m x"}, str(repo), CFG_ON)
    priv = check_git_privacy("Bash", {"command": "git commit -m x"}, str(repo), {})
    assert priv is None or "[Guardian:GitPrivacy]" in priv


def test_no_conflict_commit_does_not_spawn_resolver(isolated_git, tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    real = ptu._run_capture
    calls = []

    def rec(args, cwd, timeout):
        calls.append(list(args))
        return real(args, cwd, timeout)
    monkeypatch.setattr(ptu, "_run_capture", rec)
    assert check_merge_driver("Bash", {"command": "git commit -m x"}, str(repo), CFG_ON) is None
    assert calls and all(c[:3] == ["git", "ls-files", "-u"] for c in calls)


# ─── (A) 真 git：乾淨 repo 跑 git pull → 自動 --install ─────────────────────

def test_auto_install_on_pull_isolated(isolated_git, tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    assert _cfg_get_global("merge.atomindex.driver") == ""
    msg = check_merge_driver("Bash", {"command": "git pull"}, str(repo), CFG_ON)
    assert msg and "[Guardian:MergeDriver]" in msg and "⚠" not in msg, msg
    drv = _cfg_get_global("merge.atomindex.driver")
    assert "merge-atom-index.py" in drv and drv.endswith("%O %A %B %P")
    assert (tmp_path / "xdg" / "git" / "attributes").exists()

    real = ptu._run_capture
    calls = []

    def rec(args, cwd, timeout):
        calls.append(list(args))
        return real(args, cwd, timeout)
    monkeypatch.setattr(ptu, "_run_capture", rec)
    second = check_merge_driver("Bash", {"command": "git pull"}, str(repo), CFG_ON)
    assert second is None, (
        "第二次 git pull 應因 --is-installed 回 0 而靜默；若仍回 advisory，多半是 "
        f"tools/merge-atom-index.py 尚未實作 --is-installed 契約：{second}")
    assert len(calls) == 1 and "--is-installed" in calls[0]


def test_hook_python_exe_prefers_console_python(monkeypatch, tmp_path):
    fake_w = tmp_path / "pythonw.exe"
    fake_c = tmp_path / "python.exe"
    fake_w.write_bytes(b"")
    fake_c.write_bytes(b"")
    monkeypatch.setattr(ptu.sys, "executable", str(fake_w))
    assert ptu._hook_python_exe() == str(fake_c)
    fake_c.unlink()
    assert ptu._hook_python_exe() == str(fake_w)



# ─── SessionStart 開場 advisory ─────────────────────────────────────────────

def test_session_start_index_conflict_advisory(isolated_git, tmp_path):
    from handlers.session_start import _index_conflict_advisory
    repo = _make_repo(tmp_path)
    assert _index_conflict_advisory(str(repo)) == []           # 乾淨 repo：零行
    assert _index_conflict_advisory(str(tmp_path)) == []       # 非 repo：零行
    _git(repo, "merge", "A", "-m", "merge A", check=False)
    lines = _index_conflict_advisory(str(repo))
    assert len(lines) == 1 and "[Guardian:IndexConflict]" in lines[0]
    assert all(n in lines[0] for n in INDEX_NAMES) and "--resolve" in lines[0]
    sub = repo / ".claude" / "memory"
    assert _index_conflict_advisory(str(sub)) == lines         # 子目錄啟動也認得（--git-dir 絕對路徑）


# ─── SVN：拆段／觸發詞（純函式）＋ 真 svn 工作副本 e2e ───────────────────────────

SVN_OK = shutil.which("svn") is not None and shutil.which("svnadmin") is not None
svn_only = pytest.mark.skipif(not SVN_OK, reason="svn／svnadmin 不在 PATH")
_SVN_SUBS = {"commit", "ci", "resolve", "resolved"}


def test_svn_segments_and_triggers():
    assert _svn_segments("svn commit -m x", _SVN_SUBS) == [("", ["commit", "-m", "x"])]
    assert _svn_segments("cd wc && svn.exe ci -m x", _SVN_SUBS) == [("wc", ["ci", "-m", "x"])]
    assert _svn_segments('"C:/Program Files/svn.exe" resolve --accept working f', _SVN_SUBS) == [
        ("", ["resolve", "--accept", "working", "f"])]
    assert _svn_segments("svn --username u resolved f", _SVN_SUBS) == [("", ["resolved", "f"])]
    assert _svn_segments("svn update && svn status", _SVN_SUBS) == []
    assert _svn_segments("git svn dcommit", _SVN_SUBS) == []
    assert _is_svn_resolve_trigger(["commit", "-m", "x"]) and _is_svn_resolve_trigger(["ci"])
    assert _is_svn_resolve_trigger(["resolve", "--accept", "working", "f"])
    assert _is_svn_resolve_trigger(["resolve", "--accept=postpone", "f"])
    assert _is_svn_resolve_trigger(["resolved", "f"])
    assert not _is_svn_resolve_trigger(["resolve", "--accept", "theirs-full", "f"])
    assert not _is_svn_resolve_trigger(["resolve", "--accept=mine-full", "f"])
    assert not _is_svn_resolve_trigger(["update"])


def test_unmerged_index_files_recognizes_derived_index(monkeypatch, tmp_path):
    """根層衍生索引檔（各層 _INDEX.md、_local_catalog.md）也算索引檔 → commit 前會觸發 --resolve。"""
    entries = ["100644 a 1\tmemory/Server/_INDEX.md", "100644 a 3\tmemory/_local_catalog.md", "100644 a 2\tREADME.md"]
    s = _Spy(stdout="\x00".join(entries) + "\x00")  # 別用 "\0100644"：\010 會被當八進位跳脫吃掉
    monkeypatch.setattr(ptu, "_run_capture", s)
    assert ptu._unmerged_index_files(str(tmp_path), 1.0) == ["memory/Server/_INDEX.md", "memory/_local_catalog.md"]


def test_svn_commit_outside_svn_wc_spawns_nothing(spy, tmp_path):
    """純檔案系統判定不是 svn WC → 零子行程（git 段亦無）。"""
    assert check_merge_driver("Bash", {"command": "svn commit -m x"}, str(tmp_path), CFG_ON) is None
    assert check_merge_driver("PowerShell", {"command": "svn ci -m x"}, str(tmp_path), CFG_ON) is None
    assert spy.calls == []


def _svn(cwd, *args, check=True):
    r = subprocess.run(["svn", "--non-interactive", *args], cwd=str(cwd), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=60, **_NO_WINDOW)
    if check and r.returncode:
        raise AssertionError(f"svn {' '.join(args)} failed rc={r.returncode}\n{r.stdout}\n{r.stderr}")
    return r


CS = ("c", "memory/shared/Server/c.md", ("jenkins",))
D = ("d", "memory/shared/Server/d.md", ("deploy",))


def _svn_conflicted_wc(tmp_path: Path) -> Path:
    """svnadmin 本地倉＋兩個 wc：a 加 b、d（Server 3）提交；b 加 c（Server 2）後 `svn up --accept postpone`
    → 三檔 C（兩側都改同一列計數，svn 的 diff3 才會判 MEMORY.md 衝突）。回 wc b。"""
    subprocess.run(["svnadmin", "create", str(tmp_path / "repo")], check=True, capture_output=True, **_NO_WINDOW)
    url = "file:///" + str(tmp_path / "repo").replace("\\", "/")
    a, b = tmp_path / "a", tmp_path / "b"
    _svn(tmp_path, "co", "-q", url, str(a))
    _svn(tmp_path, "co", "-q", url, str(b))
    mem_a = a / ".claude" / "memory"
    mem_a.mkdir(parents=True)
    _write_index_set(mem_a, [A], {"Server": 1})
    _svn(a, "add", "-q", "--force", ".claude")
    _svn(a, "ci", "-q", "-m", "base")
    _svn(b, "up", "-q")
    _write_index_set(mem_a, [A, B, D], {"Server": 3})
    _svn(a, "add", "-q", "--force", ".claude")
    _svn(a, "ci", "-q", "-m", "a adds b d")
    _write_index_set(b / ".claude" / "memory", [A, CS], {"Server": 2}, json_eol="\r\n")
    _svn(b, "add", "-q", "--force", ".claude")
    r = _svn(b, "up", "--accept", "postpone", check=False)
    assert "Text conflicts: 3" in r.stdout, r.stdout + r.stderr
    return b


def _svn_conflicted_count(wc: Path) -> int:
    return _svn(wc, "status", "--xml").stdout.count('item="conflicted"')


@svn_only
def test_svn_resolve_before_commit_on_conflicted_wc(tmp_path, monkeypatch):
    wc = _svn_conflicted_wc(tmp_path)
    monkeypatch.setattr(ptu, "_MERGE_GATE_BUDGET_S", 30.0)
    msg = check_merge_driver("Bash", {"command": "svn commit -m x"}, str(wc), CFG_ON)
    assert msg and "[Guardian:IndexConflict]" in msg and "⚠" not in msg, msg
    assert "標記 resolved" in msg and all(n in msg for n in INDEX_NAMES)
    assert _svn_conflicted_count(wc) == 0
    mem = wc / ".claude" / "memory"
    d = json.loads((mem / "_atom_index.json").read_text(encoding="utf-8"))
    assert sorted(x["name"] for x in d["atoms"]) == ["a", "b", "c", "d"]
    mm = (mem / "MEMORY.md").read_text(encoding="utf-8")
    assert "| Server | 4 |" in mm and "<<<<<<<" not in mm  # 3 + 2 − 1
    _svn(wc, "ci", "-q", "-m", "merged")  # 真的能提交

    real = ptu._run_capture
    calls = []

    def rec(args, cwd, timeout):
        calls.append(list(args))
        return real(args, cwd, timeout)
    monkeypatch.setattr(ptu, "_run_capture", rec)
    assert check_merge_driver("Bash", {"command": "svn commit -m y"}, str(wc), CFG_ON) is None
    assert calls and all(c[:3] == ["svn", "--non-interactive", "status"] for c in calls)  # 無衝突只查 status


@svn_only
def test_svn_update_and_explicit_accept_never_trigger(spy, tmp_path):
    wc = _svn_conflicted_wc(tmp_path)
    for cmd in ("svn update", "svn up --accept postpone", "svn resolve --accept theirs-full .claude/memory/MEMORY.md",
                "svn status", "svn add x.md"):
        assert check_merge_driver("Bash", {"command": cmd}, str(wc), CFG_ON) is None, cmd
    assert spy.calls == []


@svn_only
def test_svn_resolver_fits_hook_budget(tmp_path):
    import time
    best, last_msg = 99.0, ""
    for n in range(2):
        sub = tmp_path / f"run{n}"
        sub.mkdir()
        wc = _svn_conflicted_wc(sub)
        t0 = time.monotonic()
        msg = check_merge_driver("Bash", {"command": "svn commit -m x"}, str(wc), CFG_ON)
        elapsed = time.monotonic() - t0
        assert msg and "[Guardian:IndexConflict]" in msg
        best, last_msg = min(best, elapsed), msg
        if "⚠" not in msg and elapsed <= ptu._MERGE_GATE_BUDGET_S + 0.5:
            break
    assert "⚠" not in last_msg and best <= ptu._MERGE_GATE_BUDGET_S + 0.5, (
        f"svn --resolve 未在 hook 預算 {ptu._MERGE_GATE_BUDGET_S}s 內完成（最快 {best:.2f}s）：{last_msg}")


@svn_only
def test_session_start_svn_index_conflict_advisory(tmp_path):
    from handlers.session_start import _index_conflict_advisory
    wc = _svn_conflicted_wc(tmp_path)
    lines = _index_conflict_advisory(str(wc))
    assert len(lines) == 1 and "SVN" in lines[0] and all(n in lines[0] for n in INDEX_NAMES), lines
    assert _index_conflict_advisory(str(wc / ".claude" / "memory")) == lines
    assert _index_conflict_advisory(str(tmp_path / "a")) == []  # 另一個乾淨 wc：零行
    check_merge_driver("Bash", {"command": "svn commit -m x"}, str(wc), CFG_ON)
    assert _index_conflict_advisory(str(wc)) == []  # 解完 .mine 消失 → 零行


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))

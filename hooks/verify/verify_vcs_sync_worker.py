"""verify_vcs_sync_worker.py — 記憶庫背景上版控（wg_vcs_sync.sync_targets_inline）實倉測試。

全部用 tmp 的 `git init` / `svnadmin create` 實倉，直接呼叫同步主邏輯，不 spawn worker、不碰真實 repo。

不變式：
git — untracked 新 atom 進 commit；exclude（*.access.json、memory/_meta/**）不進，已追蹤被改的 exclude 檔也不進；
      exclude 含 "/" 的 pattern 只比完整路徑（不截尾段比 basename）；記憶路徑外已 stage 的檔不被動到也不進 commit；
      待推歷史全是「pathspec 內且不被 exclude」的 commit 才 push，且推的是檢查時固定的 OID（檢查後插進來的
      commit 不推）；diff-tree 失敗 → 不推；含程式碼或 exclude 路徑的 commit → 不 push + `.unpushed`；detached／
      MERGE_HEAD → 跳過且不碰索引；索引同步失敗 → 不 commit + `.unpushed`；remote 領先 → push 被拒 → `.unpushed`。
鎖  — OS 互斥：同時 acquire 只有一個成功；持有者死亡 OS 自動釋放；被鎖拒 → 請求留在 `.req/` 不丟；
      roots.lock 取不到 → roots.json 不被改寫。
請求 — 持鎖者每輪把 `.req/` 全部請求領取到 `.req/inflight/`（pathspecs 聯集），該輪成功才刪；中途 _Stop →
      請求留在 inflight，下次重跑連同殘留一起消費；跑完若又有新請求再跑一輪。
svn — 新 atom add + `--depth empty` commit；exclude 不 add；pathspec 外（或祖先目錄下）別人 svn add 的檔不被帶走；
      只有 validated ledger 內 retired 的 missing 檔才 delete；out-of-date → update 後重試一次成功；真衝突 → 不重試。
SessionStart advisory — roots.json 逐 root：git 領先 upstream、`.unpushed`（查詢成功且 ahead=0 → 自動清標記＋
      last_error，HEAD 不必變；git 查詢 rc≠0 → 仍報且不清）、last_error（skip）、`.req/` 無人消費；
      拉側：last_pull／pulled_commits>0 → 「拉入 N 筆」、`.behind` → 「落後未併入」；首次讀索引前 spawn(reason="pull")。
拉（git）— 純記憶 incoming 在髒程式碼樹 → ref＋pathspec 同步、程式碼髒檔原封不動、上游刪檔也同步、無反向 staged；
      含程式碼 incoming：髒樹 → `.behind` 且 HEAD 不動，乾淨樹 → ff-only；分叉純記憶 → 隔離 worktree rebase，主樹
      其他 staged／未追蹤檔不動、tmp worktree 清掉；索引 JSON 兩側各加一條 → resolver 自動解；atom 本文衝突 → abort
      ＋`.behind`＋HEAD 不動；本地 ahead 含程式碼 → 不 rebase；fetch 逾時 → `.behind` 但 push 段照跑；拉成功後
      觸發向量增量索引；pull 開關關掉 → 不 fetch（push 被拒路徑仍在）；restore 失敗 → `.recover.json` 留下、下輪不
      commit（上游新增 atom 不會被當成本地刪除提交）、restore 修好後恢復並刪檔；fetch 後分支被切走 → 不 update-ref
      不 restore（ff-only 路徑同）；worktree add 失敗／remove 第一次失敗 → 無殘留；ls-files -u rc≠0 → rebase abort／
      _git_check 跳過；同一 atom 同一 scalar 欄位兩側異改 → 取上游；reason=pull 在 cooldown 內且無本地變更 → 不 fetch。
      recover 在時切到別的分支 → 記憶路徑相對目前 HEAD 乾淨才刪檔，否則不 commit 直到手動對齊；恢復／拉取期間的新編輯
      （檔既非 from 版也非目標版）→ 不 restore、recover 留著；隔離 rebase 期間改了記憶檔 → update-ref 前擋下；
      ref 前進後他 session 又 commit → 以 HEAD 為源 restore；ref 退到非後代 → 交人。
拉（svn）— update 非零或起不了程序 → pull_error／`.behind`，不進 push 的 last_error。
SessionStart advisory 拉側「拉入 N 筆」同一 last_pull 只報一次（pull_reported_at）。
拉（svn）— retired missing 先 schedule-delete 再 update；其他 missing → 不 update、`.behind`、本輪照常提交；
      update 衝突只在索引檔 → resolver 解開後提交；在 atom 本文 → `.behind`、不 commit。
全部 git 測試隔離 HOME／GIT_CONFIG_GLOBAL／GIT_CONFIG_NOSYSTEM／XDG_CONFIG_HOME：resolver 順手 --install 寫的是 tmp 的全域設定。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import textwrap
import threading
from pathlib import Path

import pytest

CLAUDE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CLAUDE / "hooks"))

import wg_vcs_sync as vs  # noqa: E402

CFG = {"vcs_sync": {"enabled": True, "push": True, "exclude": ["**/*.access.json"], "timeout_s": 60}}
CFG_NOPUSH = {"vcs_sync": {"enabled": True, "push": False, "exclude": ["**/*.access.json"], "timeout_s": 60}}
CFG_NOPULL = {"vcs_sync": {"enabled": True, "push": True, "exclude": ["**/*.access.json"], "timeout_s": 60,
                           "pull": {"enabled": False}}}
INDEX_JSON = {"version": "1.0", "atoms": [{"name": "seed", "path": "memory/seed.md", "triggers": ["seed"], "scope": "global"}]}
GITATTRS = ("memory/MEMORY.md merge=atomindex text eol=lf\nmemory/_ATOM_INDEX.md merge=atomindex text eol=lf\n"
            "memory/_atom_index.json merge=atomindex text eol=lf\n")
SVN = vs._svn_exe()
HAS_SVN = shutil.which(SVN) is not None or Path(SVN).exists()


@pytest.fixture(autouse=True)
def sync_dir(tmp_path, monkeypatch):
    d = tmp_path / "_sync"
    monkeypatch.setattr(vs, "SYNC_DIR", d)
    monkeypatch.setattr(vs, "LEDGER_DIR", tmp_path / "_ledger")
    home = tmp_path / "_home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / ".gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    vs._held_locks.clear()
    yield d
    for lk in list(vs._held_locks.values()):
        lk.release()
    vs._held_locks.clear()


def _logs():
    out = []
    return out, out.append


@pytest.fixture(autouse=True)
def vector_calls(monkeypatch):
    """拉成功後的向量增量索引只驗「被請求」，不打真服務（本機服務在跑時會真的重建索引）。"""
    import wg_atoms
    calls = []
    monkeypatch.setattr(wg_atoms, "_trigger_incremental_index", lambda cfg: calls.append(cfg))
    return calls


# ─── git ─────────────────────────────────────────────────────────────────────

def _git(repo: Path, *args, check=True):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=vs.worker_env())
    if check and r.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {r.stderr}")
    return r


def _git_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q", "-b", "main")
    _git(path, "config", "user.email", "t@t")
    _git(path, "config", "user.name", "t")
    _git(path, "config", "core.quotepath", "false")   # 全域設定已隔離：CJK 路徑在 ls-files 不得被 \ooo 轉義
    (path / "memory").mkdir()
    (path / "memory" / "seed.md").write_text("# seed\n", encoding="utf-8")
    _write_index(path / "memory", INDEX_JSON)
    (path / ".gitattributes").write_text(GITATTRS, encoding="utf-8", newline="\n")
    (path / "code.py").write_text("print(1)\n", encoding="utf-8")
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", "seed")
    return path


def _write_index(mem: Path, idx: dict) -> None:
    """索引三檔最小合法內容（resolver 的格式檢查：JSON 有 atoms 列表；md 有表頭）。"""
    (mem / "_atom_index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=2) + "\n",
                                          encoding="utf-8", newline="\n")
    rows = "".join(f"| {a['name']} | {a['path']} | {', '.join(a['triggers'])} | {a['scope']} |\n" for a in idx["atoms"])
    (mem / "_ATOM_INDEX.md").write_text("# Atom Trigger Index\n\n| Atom | Path | Trigger | Scope |\n|---|---|---|---|\n" + rows,
                                        encoding="utf-8", newline="\n")
    (mem / "MEMORY.md").write_text("# Atom Index\n\n| 範疇 | atom 數 | 深入 |\n|---|---|---|\n| memory | "
                                   f"{len(idx['atoms'])} | memory/ |\n", encoding="utf-8", newline="\n")


def _add_atom(mem: Path, name: str) -> None:
    idx = json.loads((mem / "_atom_index.json").read_text(encoding="utf-8"))
    idx["atoms"].append({"name": name, "path": f"memory/{name}.md", "triggers": [name], "scope": "global"})
    (mem / f"{name}.md").write_text(f"# {name}\n", encoding="utf-8", newline="\n")
    _write_index(mem, idx)


def _clone(tmp_path: Path, bare: Path, name: str = "other") -> Path:
    other = tmp_path / name
    _git(tmp_path, "clone", "-q", str(bare), str(other))
    _git(other, "config", "user.email", "o@o")
    _git(other, "config", "user.name", "o")
    return other


def _push_from_other(other: Path, msg: str) -> str:
    _git(other, "add", "-A")
    _git(other, "commit", "-q", "-m", msg)
    _git(other, "push", "-q", "origin", "main")
    return _git(other, "rev-parse", "HEAD").stdout.strip()


def _status_set(repo: Path) -> set:
    return {ln for ln in _git(repo, "status", "--porcelain").stdout.splitlines() if ln.strip()}


def _worktrees(repo: Path) -> int:
    return _git(repo, "worktree", "list", "--porcelain").stdout.count("worktree ")


@pytest.fixture
def repo(tmp_path):
    return _git_repo(tmp_path / "repo")


@pytest.fixture
def repo_with_remote(tmp_path, repo):
    bare = tmp_path / "remote.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(bare))
    _git(repo, "remote", "add", "origin", str(bare))
    _git(repo, "push", "-q", "-u", "origin", "main")
    return repo, bare


def _target(repo: Path, kind="git", specs=("memory",)) -> vs.SyncTarget:
    return vs.SyncTarget(kind, repo.resolve(), list(specs), [(repo / s).resolve() for s in specs])


def _head_files(repo: Path):
    return set(_git(repo, "show", "--name-only", "--format=", "HEAD").stdout.split())


def test_git_untracked_atom_committed_exclude_skipped(repo):
    (repo / "memory" / "new.md").write_text("# new\n", encoding="utf-8")
    (repo / "memory" / "new.access.json").write_text("{}", encoding="utf-8")
    (repo / "memory" / "sub").mkdir()
    (repo / "memory" / "sub" / "deep.access.json").write_text("{}", encoding="utf-8")
    logs, log = _logs()
    res = vs.sync_targets_inline([_target(repo)], CFG_NOPUSH, log=log)
    assert res[0]["status"] == "ok" and res[0]["committed"] == 1, (res, logs)
    assert _head_files(repo) == {"memory/new.md"}
    status = _git(repo, "status", "--porcelain").stdout
    assert "?? memory/new.access.json" in status and "?? memory/sub/" in status
    assert not vs.lock_is_live(repo)
    assert vs.pending_requests(repo) == 0
    roots = vs.load_roots()
    assert roots[repo.resolve().as_posix()]["vcs"] == "git"
    assert roots[repo.resolve().as_posix()]["last_sync"]


def test_git_tracked_excluded_file_modified_not_committed(repo):
    """W4：已追蹤的 *.access.json 改了 → 不進 commit（add 與 commit 都只用允許路徑集合）。"""
    (repo / "memory" / "x.access.json").write_text("{}", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "track access")
    (repo / "memory" / "x.access.json").write_text('{"n":1}', encoding="utf-8")
    (repo / "memory" / "new.md").write_text("# new\n", encoding="utf-8")
    res = vs.sync_targets_inline([_target(repo)], CFG_NOPUSH, log=lambda m: None)
    assert res[0]["status"] == "ok" and res[0]["committed"] == 1, res
    assert _head_files(repo) == {"memory/new.md"}
    assert _git(repo, "status", "--porcelain").stdout.rstrip() == " M memory/x.access.json"


def test_git_deleted_and_cjk_paths_committed(repo):
    (repo / "memory" / "seed.md").unlink()
    (repo / "memory" / "中文 atom[1].md").write_text("# 中\n", encoding="utf-8")
    res = vs.sync_targets_inline([_target(repo)], CFG_NOPUSH, log=lambda m: None)
    assert res[0]["status"] == "ok" and res[0]["committed"] == 2, res
    assert _git(repo, "status", "--porcelain").stdout.strip() == ""
    assert "memory/seed.md" not in _git(repo, "ls-files").stdout
    assert "中文 atom[1].md" in _git(repo, "ls-files").stdout


def test_git_tracked_but_ignored_file_deleted_is_committed(repo):
    """已追蹤但路徑被 .gitignore 蓋到的檔（memory/personal/ 下 role.md）刪除後仍能 add+commit；
    沒有 -f 時 git add 回 rc≠0「paths are ignored」，worker 會整輪停住。"""
    (repo / "memory" / "personal" / "u").mkdir(parents=True)
    (repo / "memory" / "personal" / "u" / "role.md").write_text("- Role: programmer\n", encoding="utf-8")
    _git(repo, "add", "-f", "memory/personal/u/role.md")
    (repo / ".gitignore").write_text("memory/personal/\n", encoding="utf-8")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-q", "-m", "track ignored role.md")
    (repo / "memory" / "personal" / "u" / "role.md").unlink()
    (repo / "memory" / "personal" / "u" / "scratch.md").write_text("# ignored untracked\n", encoding="utf-8")
    res = vs.sync_targets_inline([_target(repo)], CFG_NOPUSH, log=lambda m: None)
    assert res[0]["status"] == "ok" and res[0]["committed"] == 1, res
    assert "memory/personal/u/role.md" not in _git(repo, "ls-files").stdout
    # -f 只作用在 status 列出的變更檔；被忽略的未追蹤檔不得被順手加進來
    assert "scratch.md" not in _git(repo, "ls-files").stdout


def test_git_already_staged_deletion_is_committed(repo):
    """前一輪 add 已把刪除 stage 進 index 後 _Stop（path 不在工作樹也不在 index）→ 這輪不得再 add 它，
    直接進 commit pathspec。"""
    _git(repo, "rm", "-q", "--cached", "memory/seed.md")
    (repo / "memory" / "seed.md").unlink()
    (repo / "memory" / "new.md").write_text("# new" + chr(10), encoding="utf-8")
    res = vs.sync_targets_inline([_target(repo)], CFG_NOPUSH, log=lambda m: None)
    assert res[0]["status"] == "ok" and res[0]["committed"] == 2, res
    assert "memory/seed.md" not in _git(repo, "ls-files").stdout
    assert _git(repo, "status", "--porcelain").stdout.strip() == ""


def test_git_other_path_staged_is_untouched(repo):
    (repo / "code.py").write_text("print(2)\n", encoding="utf-8")
    _git(repo, "add", "code.py")
    (repo / "memory" / "new.md").write_text("# new\n", encoding="utf-8")
    res = vs.sync_targets_inline([_target(repo)], CFG_NOPUSH, log=lambda m: None)
    assert res[0]["status"] == "ok"
    assert _head_files(repo) == {"memory/new.md"}
    assert _git(repo, "status", "--porcelain").stdout.strip() == "M  code.py"


def test_git_nothing_to_commit(repo):
    before = _git(repo, "rev-parse", "HEAD").stdout
    res = vs.sync_targets_inline([_target(repo)], CFG_NOPUSH, log=lambda m: None)
    assert res[0]["status"] == "ok" and res[0]["committed"] == 0
    assert _git(repo, "rev-parse", "HEAD").stdout == before


def test_git_push_when_pending_all_memory(repo_with_remote):
    repo, bare = repo_with_remote
    (repo / "memory" / "new.md").write_text("# new\n", encoding="utf-8")
    logs, log = _logs()
    res = vs.sync_targets_inline([_target(repo)], CFG, log=log)
    assert res[0]["status"] == "ok" and res[0]["pushed"], (res, logs)
    assert _git(bare, "rev-parse", "main").stdout == _git(repo, "rev-parse", "HEAD").stdout
    assert not vs.marker_path(repo, "unpushed").exists()


def test_git_push_uses_fixed_snapshot_not_commit_injected_before_push(repo_with_remote, monkeypatch):
    """B1：待推歷史檢查後、push 前插進一個程式碼 commit → 推的是固定 OID，新 commit 不出去。"""
    repo, bare = repo_with_remote
    (repo / "memory" / "new.md").write_text("# new\n", encoding="utf-8")
    orig = vs._run
    injected = {}

    def run(cmd, cwd, timeout, env, text=True):
        if cmd[:2] == ["git", "push"] and not injected:
            (repo / "code.py").write_text("print(99)\n", encoding="utf-8")
            _git(repo, "commit", "-q", "-am", "late code")
            injected["head"] = _git(repo, "rev-parse", "HEAD").stdout.strip()
        return orig(cmd, cwd, timeout, env, text)
    monkeypatch.setattr(vs, "_run", run)
    res = vs.sync_targets_inline([_target(repo)], CFG, log=lambda m: None)
    assert res[0]["status"] == "ok" and res[0]["pushed"], res
    remote_head = _git(bare, "rev-parse", "main").stdout.strip()
    assert remote_head != injected["head"]
    assert remote_head == _git(repo, "rev-parse", "HEAD~1").stdout.strip()
    assert "memory/new.md" in _git(bare, "show", "--name-only", "--format=", "main").stdout


def test_git_diff_tree_failure_blocks_push(repo_with_remote, monkeypatch):
    repo, bare = repo_with_remote
    remote_before = _git(bare, "rev-parse", "main").stdout
    (repo / "memory" / "new.md").write_text("# new\n", encoding="utf-8")
    orig = vs._run

    def run(cmd, cwd, timeout, env, text=True):
        if cmd[:2] == ["git", "diff-tree"]:
            return subprocess.CompletedProcess(cmd, 128, "", "fatal: bad object")
        return orig(cmd, cwd, timeout, env, text)
    monkeypatch.setattr(vs, "_run", run)
    res = vs.sync_targets_inline([_target(repo)], CFG, log=lambda m: None)
    assert res[0]["status"] == "unpushed" and "diff-tree" in res[0]["reason"], res
    assert _git(bare, "rev-parse", "main").stdout == remote_before
    rec = vs.read_unpushed_record(repo)
    assert rec["head_oid"] == _git(repo, "rev-parse", "HEAD").stdout.strip()


def test_git_no_push_when_code_commit_pending(repo_with_remote):
    repo, bare = repo_with_remote
    remote_before = _git(bare, "rev-parse", "main").stdout
    (repo / "code.py").write_text("print(3)\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "code change")
    (repo / "memory" / "new.md").write_text("# new\n", encoding="utf-8")
    res = vs.sync_targets_inline([_target(repo)], CFG, log=lambda m: None)
    assert res[0]["status"] == "unpushed", res
    assert "非記憶" in res[0]["reason"]
    assert _head_files(repo) == {"memory/new.md"}            # commit 仍在本地
    assert _git(bare, "rev-parse", "main").stdout == remote_before
    assert "非記憶" in vs.read_unpushed(repo)


def test_under_pathspecs_dot_matches_everything():
    assert vs._under_pathspecs("a/b.md", ["."])
    assert vs._under_pathspecs("memory/x.md", ["memory"])
    assert vs._under_pathspecs("memory", ["memory/"])
    assert not vs._under_pathspecs("memory2/x.md", ["memory"])


def test_excluded_real_config_dir_pattern_does_not_eat_everything():
    """N1：實際 config 的 exclude（**/*.access.json + memory/_meta/**）——含 "/" 的 pattern 只比完整路徑；
    截尾段 `**` 比 basename 會把所有檔排除，記憶庫從此永遠零 commit。"""
    cfg = json.loads((CLAUDE / "workflow" / "config.json").read_text(encoding="utf-8"))
    exclude = cfg["vcs_sync"]["exclude"]
    assert "memory/_meta/**" in exclude and "**/*.access.json" in exclude
    for rel in ("memory/new.md", "_AIDocs/_atoms/Tools/new.md", ".claude/memory/shared/new.md"):
        assert not vs._excluded(rel, exclude), rel
    for rel in ("memory/_meta/x.json", "memory/_meta/sub/y.md", "memory/a/b.access.json", "new.access.json"):
        assert vs._excluded(rel, exclude), rel


def test_git_no_push_when_excluded_path_commit_pending(repo_with_remote):
    """N2：待推歷史含被 exclude 的路徑（使用者手動 commit 的 memory/_meta 設定檔）→ 不 push + `.unpushed`。"""
    repo, bare = repo_with_remote
    cfg = {"vcs_sync": {"enabled": True, "push": True,
                        "exclude": ["**/*.access.json", "memory/_meta/**"], "timeout_s": 60}}
    remote_before = _git(bare, "rev-parse", "main").stdout
    (repo / "memory" / "_meta").mkdir()
    (repo / "memory" / "_meta" / "x.json").write_text("{}", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "manual meta")
    (repo / "memory" / "new.md").write_text("# new\n", encoding="utf-8")
    res = vs.sync_targets_inline([_target(repo)], cfg, log=lambda m: None)
    assert res[0]["status"] == "unpushed" and "memory/_meta/x.json" in res[0]["reason"], res
    assert _head_files(repo) == {"memory/new.md"}
    assert _git(bare, "rev-parse", "main").stdout == remote_before
    assert "memory/_meta/x.json" in vs.read_unpushed(repo)


def test_git_detached_head_skipped(repo):
    _git(repo, "checkout", "-q", "--detach")
    (repo / "memory" / "new.md").write_text("# new\n", encoding="utf-8")
    res = vs.sync_targets_inline([_target(repo)], CFG_NOPUSH, log=lambda m: None)
    assert res[0]["status"] == "skipped" and "detached" in res[0]["reason"]
    assert "?? memory/new.md" in _git(repo, "status", "--porcelain").stdout


def test_git_merge_in_progress_skipped_without_touching_index(repo, monkeypatch):
    """W1：拒跑狀態檢查在索引同步之前——MERGE_HEAD 存在時 catalog 不得被改寫。"""
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    (repo / ".git" / "MERGE_HEAD").write_text(head + "\n", encoding="utf-8")
    (repo / "memory" / "new.md").write_text("# new\n", encoding="utf-8")
    (repo / "memory" / "_atom_index.json").write_text("{}", encoding="utf-8")

    def boom(*a, **k):
        raise AssertionError("合併中不得跑索引同步")
    monkeypatch.setattr(vs, "_sync_indexes", boom)
    res = vs.sync_targets_inline([_target(repo)], CFG_NOPUSH, log=lambda m: None, pre_sync=True)
    assert res[0]["status"] == "skipped" and "MERGE_HEAD" in res[0]["reason"]
    assert "?? memory/new.md" in _git(repo, "status", "--porcelain").stdout
    assert vs.load_roots()[repo.resolve().as_posix()]["last_error"].startswith("skip:")


def test_index_sync_failure_stops_before_commit(repo, tmp_path, monkeypatch):
    """W1：sync-memory-index --write 失敗 → 本輪不 commit，`.unpushed` 寫「索引同步失敗」。"""
    fake = tmp_path / "fake_claude"
    (fake / "tools").mkdir(parents=True)
    (fake / "tools" / "sync-memory-index.py").write_text("import sys; sys.exit(3)\n", encoding="utf-8")
    monkeypatch.setattr(vs, "CLAUDE_DIR", fake)
    (repo / "memory" / "_atom_index.json").write_text("{}", encoding="utf-8")
    (repo / "memory" / "new.md").write_text("# new\n", encoding="utf-8")
    before = _git(repo, "rev-parse", "HEAD").stdout
    res = vs.sync_targets_inline([_target(repo)], CFG_NOPUSH, log=lambda m: None, pre_sync=True)
    assert res[0]["status"] == "unpushed" and "索引同步失敗" in res[0]["reason"], res
    assert _git(repo, "rev-parse", "HEAD").stdout == before
    assert "索引同步失敗" in vs.read_unpushed(repo)


def test_git_remote_ahead_push_rejected_when_pull_disabled(tmp_path, repo_with_remote):
    repo, bare = repo_with_remote
    other = _clone(tmp_path, bare)
    (other / "memory" / "theirs.md").write_text("# theirs\n", encoding="utf-8")
    _push_from_other(other, "theirs")
    (repo / "memory" / "new.md").write_text("# new\n", encoding="utf-8")
    res = vs.sync_targets_inline([_target(repo)], CFG_NOPULL, log=lambda m: None)
    assert res[0]["status"] == "unpushed" and "push 被拒" in res[0]["reason"], res
    assert res[0]["pull"]["status"] == "disabled"
    assert _head_files(repo) == {"memory/new.md"}
    assert vs.read_unpushed(repo)
    assert not vs.marker_path(repo, "behind").exists()


# ─── git 拉 ──────────────────────────────────────────────────────────────────

def test_pull_pure_memory_into_dirty_code_tree_syncs_ref_and_pathspec(tmp_path, repo_with_remote, vector_calls):
    """純記憶 incoming（含上游刪檔）＋本地程式碼樹髒 → ref＋pathspec 同步；程式碼髒檔原封不動、無反向 staged。"""
    repo, bare = repo_with_remote
    other = _clone(tmp_path, bare)
    (other / "memory" / "theirs.md").write_text("# theirs\n", encoding="utf-8")
    (other / "memory" / "seed.md").unlink()
    remote_head = _push_from_other(other, "theirs + delete seed")
    (repo / "code.py").write_text("print(2)\n", encoding="utf-8")          # 未提交的程式碼改動
    (repo / "scratch.txt").write_text("x\n", encoding="utf-8")               # 未追蹤
    logs, log = _logs()
    res = vs.sync_targets_inline([_target(repo)], CFG, log=log)
    assert res[0]["status"] == "ok" and res[0]["pull"]["status"] == "pulled", (res, logs)
    assert res[0]["pull"]["pulled_commits"] == 1
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == remote_head
    assert (repo / "memory" / "theirs.md").exists() and not (repo / "memory" / "seed.md").exists()
    assert _status_set(repo) == {" M code.py", "?? scratch.txt"}
    assert (repo / "code.py").read_text(encoding="utf-8") == "print(2)\n"
    assert not vs.marker_path(repo, "behind").exists()
    rec = vs.load_roots()[repo.resolve().as_posix()]
    assert rec["last_pull"] and rec["pulled_commits"] == 1 and rec["pull_error"] is None
    assert vector_calls == [CFG]


def test_pull_with_extra_pathspec_absent_then_added_upstream(tmp_path, repo_with_remote):
    """公司層的非記憶 pathspec（usage-snapshots）：兩邊都還沒有這個目錄時拉取照常；上游放進檔後算純記憶 commit，
    本地程式碼樹髒也拉得進來。"""
    repo, bare = repo_with_remote
    target = vs.SyncTarget("git", repo.resolve(), ["memory", "usage-snapshots"], [(repo / "memory").resolve()])
    other = _clone(tmp_path, bare)
    (other / "memory" / "theirs.md").write_text("# theirs\n", encoding="utf-8")
    _push_from_other(other, "theirs")
    (repo / "code.py").write_text("print(2)\n", encoding="utf-8")
    logs, log = _logs()
    res = vs.sync_targets_inline([target], CFG, log=log)
    assert res[0]["status"] == "ok" and res[0]["pull"]["status"] == "pulled", (res, logs)
    assert (repo / "memory" / "theirs.md").exists()

    (other / "usage-snapshots").mkdir()
    (other / "usage-snapshots" / "usage-20260101-a.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    remote_head = _push_from_other(other, "snapshot")
    res = vs.sync_targets_inline([target], CFG, log=log)
    assert res[0]["status"] == "ok" and res[0]["pull"]["status"] == "pulled", (res, logs)
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == remote_head
    assert (repo / "usage-snapshots" / "usage-20260101-a.png").read_bytes() == b"\x89PNG\r\n\x1a\n"
    assert _status_set(repo) == {" M code.py"}


def test_pull_code_commit_into_dirty_tree_marks_behind_head_unchanged(tmp_path, repo_with_remote, vector_calls):
    repo, bare = repo_with_remote
    other = _clone(tmp_path, bare)
    (other / "code.py").write_text("print(9)\n", encoding="utf-8")
    _push_from_other(other, "code")
    (repo / "scratch.txt").write_text("x\n", encoding="utf-8")
    (repo / "code.py").write_text("print(2)\n", encoding="utf-8")
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    res = vs.sync_targets_inline([_target(repo)], CFG, log=lambda m: None)
    assert res[0]["status"] == "ok" and res[0]["pull"]["status"] == "behind", res
    assert "非記憶" in res[0]["pull"]["reason"]
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == head
    rec = vs.read_behind_record(repo)
    assert rec and "非記憶" in rec["reason"] and rec["at"]
    assert vs.load_roots()[repo.resolve().as_posix()]["pull_error"] == res[0]["pull"]["reason"]
    assert vs.load_roots()[repo.resolve().as_posix()]["last_error"] is None      # push 欄位不受影響
    assert vector_calls == []


def test_pull_code_commit_into_clean_tree_ff_only(tmp_path, repo_with_remote):
    repo, bare = repo_with_remote
    other = _clone(tmp_path, bare)
    (other / "code.py").write_text("print(9)\n", encoding="utf-8")
    (other / "memory" / "theirs.md").write_text("# theirs\n", encoding="utf-8")
    remote_head = _push_from_other(other, "code + memory")
    res = vs.sync_targets_inline([_target(repo)], CFG, log=lambda m: None)
    assert res[0]["status"] == "ok" and res[0]["pull"]["status"] == "pulled", res
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == remote_head
    assert (repo / "code.py").read_text(encoding="utf-8") == "print(9)\n"
    assert _status_set(repo) == set()
    assert not vs.marker_path(repo, "behind").exists()


def test_pull_diverged_pure_memory_rebases_in_isolated_worktree(tmp_path, repo_with_remote):
    """分叉純記憶 → 隔離 worktree rebase；主樹其他 staged／未追蹤檔原封不動、tmp worktree 清掉、之後 push 成功。"""
    repo, bare = repo_with_remote
    other = _clone(tmp_path, bare)
    (other / "memory" / "theirs.md").write_text("# theirs\n", encoding="utf-8")
    remote_head = _push_from_other(other, "theirs")
    (repo / "memory" / "new.md").write_text("# new\n", encoding="utf-8")
    (repo / "code.py").write_text("print(2)\n", encoding="utf-8")
    _git(repo, "add", "code.py")                                               # 記憶路徑外 staged
    (repo / "scratch.txt").write_text("x\n", encoding="utf-8")
    logs, log = _logs()
    res = vs.sync_targets_inline([_target(repo)], CFG, log=log)
    assert res[0]["status"] == "ok" and res[0]["pull"]["status"] == "pulled" and res[0]["pushed"], (res, logs)
    assert _git(repo, "rev-parse", "HEAD~1").stdout.strip() == remote_head
    assert _head_files(repo) == {"memory/new.md"}
    assert (repo / "memory" / "theirs.md").exists() and (repo / "memory" / "new.md").exists()
    assert _status_set(repo) == {"M  code.py", "?? scratch.txt"}
    assert _worktrees(repo) == 1
    assert not list(Path(vs.tempfile.gettempdir()).glob("vcs-sync-wt-*"))
    assert _git(bare, "rev-parse", "main").stdout == _git(repo, "rev-parse", "HEAD").stdout


def test_pull_diverged_index_json_conflict_auto_resolved(tmp_path, repo_with_remote):
    """索引 _atom_index.json 兩側各加一條 → rebase 衝突由 merge-atom-index.py --resolve 解開。"""
    repo, bare = repo_with_remote
    other = _clone(tmp_path, bare)
    _add_atom(other / "memory", "theirs")
    remote_head = _push_from_other(other, "theirs atom")
    _add_atom(repo / "memory", "mine")
    logs, log = _logs()
    res = vs.sync_targets_inline([_target(repo)], CFG, log=log)
    assert res[0]["status"] == "ok" and res[0]["pull"]["status"] == "pulled", (res, logs)
    assert _git(repo, "rev-parse", "HEAD~1").stdout.strip() == remote_head
    idx = json.loads((repo / "memory" / "_atom_index.json").read_text(encoding="utf-8"))
    assert {a["name"] for a in idx["atoms"]} == {"seed", "theirs", "mine"}
    assert _status_set(repo) == set()
    assert _worktrees(repo) == 1
    assert not vs.marker_path(repo, "behind").exists()


def test_pull_diverged_atom_body_conflict_aborts_and_marks_behind(tmp_path, repo_with_remote):
    repo, bare = repo_with_remote
    other = _clone(tmp_path, bare)
    (other / "memory" / "seed.md").write_text("# seed (theirs)\n", encoding="utf-8")
    _push_from_other(other, "theirs edit")
    (repo / "memory" / "seed.md").write_text("# seed (mine)\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "mine edit")
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    res = vs.sync_targets_inline([_target(repo)], CFG, log=lambda m: None)
    assert res[0]["pull"]["status"] == "behind" and "非索引檔" in res[0]["pull"]["reason"], res
    assert res[0]["status"] == "unpushed" and "push 被拒" in res[0]["reason"]        # push 段仍跑、被拒照報
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == head
    assert (repo / "memory" / "seed.md").read_text(encoding="utf-8") == "# seed (mine)\n"
    assert _worktrees(repo) == 1
    assert not list(Path(vs.tempfile.gettempdir()).glob("vcs-sync-wt-*"))
    assert not (repo / ".git" / "rebase-merge").exists()
    assert "非索引檔" in vs.read_behind_record(repo)["reason"]


def test_pull_local_ahead_with_code_commit_not_rebased(tmp_path, repo_with_remote):
    repo, bare = repo_with_remote
    other = _clone(tmp_path, bare)
    (other / "memory" / "theirs.md").write_text("# theirs\n", encoding="utf-8")
    _push_from_other(other, "theirs")
    (repo / "code.py").write_text("print(2)\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "local code")
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    res = vs.sync_targets_inline([_target(repo)], CFG, log=lambda m: None)
    assert res[0]["pull"]["status"] == "behind" and "本地 ahead" in res[0]["pull"]["reason"], res
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == head
    assert not (repo / "memory" / "theirs.md").exists()
    assert _worktrees(repo) == 1


def test_pull_fetch_timeout_marks_behind_but_push_still_runs(repo_with_remote, monkeypatch):
    repo, bare = repo_with_remote
    (repo / "memory" / "new.md").write_text("# new\n", encoding="utf-8")
    orig = vs._run

    def run(cmd, cwd, timeout, env, text=True):
        if cmd[0] == "git" and "fetch" in cmd:
            raise subprocess.TimeoutExpired(cmd, timeout)
        return orig(cmd, cwd, timeout, env, text)
    monkeypatch.setattr(vs, "_run", run)
    res = vs.sync_targets_inline([_target(repo)], CFG, log=lambda m: None)
    assert res[0]["status"] == "ok" and res[0]["pushed"], res
    assert res[0]["pull"]["status"] == "behind" and "fetch 逾時" in res[0]["pull"]["reason"]
    assert _git(bare, "rev-parse", "main").stdout == _git(repo, "rev-parse", "HEAD").stdout
    assert "fetch 逾時" in vs.read_behind_record(repo)["reason"]
    rec = vs.load_roots()[repo.resolve().as_posix()]
    assert rec["pull_error"] and rec["last_error"] is None and rec["last_sync"]


def _inject(monkeypatch, pred, fake):
    """vs._run 攔截：pred(cmd, cwd) 為真時回 fake(cmd, orig_result_or_None)；其餘走真實 git。"""
    orig = vs._run

    def run(cmd, cwd, timeout, env, text=True):
        if pred(cmd, cwd):
            return fake(cmd, lambda: orig(cmd, cwd, timeout, env, text))
        return orig(cmd, cwd, timeout, env, text)
    monkeypatch.setattr(vs, "_run", run)
    return orig


def test_pull_restore_failure_persists_recover_and_blocks_commit_until_recovered(tmp_path, repo_with_remote, monkeypatch):
    """B1：update-ref 成功、restore 失敗 → `.recover.json` 留下；下輪恢復仍失敗 → skipped、不把上游新增 atom 當本地刪除
    提交；restore 修好 → 恢復成功、刪檔、樹乾淨、不多出 commit。"""
    repo, bare = repo_with_remote
    other = _clone(tmp_path, bare)
    (other / "memory" / "theirs.md").write_text("# theirs\n", encoding="utf-8")
    remote_head = _push_from_other(other, "theirs")
    orig = _inject(monkeypatch, lambda cmd, cwd: cmd[:2] == ["git", "restore"],
                   lambda cmd, run: subprocess.CompletedProcess(cmd, 1, "", "simulated restore failure"))
    res = vs.sync_targets_inline([_target(repo)], CFG, log=lambda m: None)
    assert res[0]["status"] == "ok" and res[0]["pull"]["status"] == "behind", res
    assert "restore 記憶路徑失敗" in res[0]["pull"]["reason"]
    rec = vs.read_recover(repo)
    assert rec and rec["branch"] == "main" and rec["to"] == remote_head and rec["pathspecs"] == ["memory"]
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == remote_head
    assert not (repo / "memory" / "theirs.md").exists()
    assert "D  memory/theirs.md" in _status_set(repo)          # 沒恢復前，commit 會把它當本地刪除
    res = vs.sync_targets_inline([_target(repo)], CFG, log=lambda m: None)
    assert res[0]["status"] == "skipped" and "記憶路徑恢復未完成" in res[0]["reason"], res
    assert "記憶路徑恢復未完成" in vs.read_behind_record(repo)["reason"]
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == remote_head   # 沒有新 commit
    assert _git(bare, "rev-parse", "main").stdout.strip() == remote_head
    assert vs.recover_path(repo).exists()
    monkeypatch.setattr(vs, "_run", orig)
    logs, log = _logs()
    res = vs.sync_targets_inline([_target(repo)], CFG, log=log)
    assert res[0]["status"] == "ok" and res[0]["committed"] == 0 and res[0]["pull"]["status"] == "up-to-date", (res, logs)
    assert any("恢復完成" in m for m in logs), logs
    assert not vs.recover_path(repo).exists()
    assert (repo / "memory" / "theirs.md").exists() and _status_set(repo) == set()
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == remote_head
    assert not vs.marker_path(repo, "behind").exists()


def test_recover_file_dropped_when_head_left_branch(repo):
    """B1：HEAD 已不在 recover 記的 branch 且記憶路徑相對目前 HEAD 乾淨 → 已對齊、刪檔、照常跑。"""
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    vs.write_recover(repo, "main", head, head, ["memory"])
    _git(repo, "checkout", "-q", "-b", "feature")
    logs, log = _logs()
    res = vs.sync_targets_inline([_target(repo)], CFG_NOPUSH, log=log)
    assert res[0]["status"] == "ok", (res, logs)
    assert not vs.recover_path(repo).exists()
    assert any("放棄記憶路徑恢復" in m for m in logs), logs


def _half_recovered(tmp_path, repo_with_remote):
    """製造「ref 已到 U、index／工作樹還在 H」的半完成狀態＋recover 檔（update-ref 成功、restore 沒跑）。回 (repo, H, U)。"""
    repo, bare = repo_with_remote
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    other = _clone(tmp_path, bare)
    (other / "memory" / "theirs.md").write_text("# theirs\n", encoding="utf-8")
    upstream = _push_from_other(other, "theirs")
    _git(repo, "fetch", "-q", "origin")
    _git(repo, "update-ref", "refs/heads/main", upstream, head)
    vs.write_recover(repo, "main", head, upstream, ["memory"])
    assert "D  memory/theirs.md" in _status_set(repo)
    return repo, head, upstream


def test_recover_kept_on_other_branch_until_memory_clean(tmp_path, repo_with_remote):
    """N1：半完成狀態下切到 feature（index 仍是 H 的記憶樹）→ 不 commit、recover 仍在、`.behind`；
    手動 restore 對齊後再跑 → 刪檔、正常。"""
    repo, head, upstream = _half_recovered(tmp_path, repo_with_remote)
    _git(repo, "checkout", "-q", "-b", "feature")
    res = vs.sync_targets_inline([_target(repo)], CFG_NOPUSH, log=lambda m: None)
    assert res[0]["status"] == "skipped" and "記憶路徑恢復未完成" in res[0]["reason"] and "分支已切換" in res[0]["reason"], res
    assert vs.recover_path(repo).exists()
    assert "分支已切換" in vs.read_behind_record(repo)["reason"]
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == upstream           # feature 上沒有新 commit
    assert "D  memory/theirs.md" in _status_set(repo)
    _git(repo, "restore", "--source=HEAD", "--staged", "--worktree", "--", "memory")
    logs, log = _logs()
    res = vs.sync_targets_inline([_target(repo)], CFG_NOPUSH, log=log)
    assert res[0]["status"] == "ok" and res[0]["committed"] == 0, (res, logs)
    assert not vs.recover_path(repo).exists()
    assert any("放棄記憶路徑恢復" in m for m in logs), logs
    assert (repo / "memory" / "theirs.md").exists() and _status_set(repo) == set()


def test_recover_does_not_overwrite_edit_made_meanwhile(tmp_path, repo_with_remote):
    """N2：recover 期間他 session 改了 memory/seed.md（既非 from 版也非 to 版）→ 不 restore、recover 仍在、`.behind`
    「未提交編輯」；編輯內容原封不動。手動對齊後再跑 → 恢復完成。"""
    repo, head, upstream = _half_recovered(tmp_path, repo_with_remote)
    (repo / "memory" / "seed.md").write_text("# seed edited\n", encoding="utf-8")
    res = vs.sync_targets_inline([_target(repo)], CFG_NOPUSH, log=lambda m: None)
    assert res[0]["status"] == "skipped" and "未提交編輯" in res[0]["reason"] and "seed.md" in res[0]["reason"], res
    assert vs.recover_path(repo).exists()
    assert (repo / "memory" / "seed.md").read_text(encoding="utf-8") == "# seed edited\n"
    assert not (repo / "memory" / "theirs.md").exists()
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == upstream
    _git(repo, "restore", "--source=HEAD", "--staged", "--worktree", "--", "memory")
    logs, log = _logs()
    res = vs.sync_targets_inline([_target(repo)], CFG_NOPUSH, log=log)
    assert res[0]["status"] == "ok" and res[0]["committed"] == 0, (res, logs)
    assert not vs.recover_path(repo).exists() and any("恢復完成" in m for m in logs), logs
    assert _status_set(repo) == set()


def test_pull_edit_after_update_ref_not_overwritten(tmp_path, repo_with_remote, monkeypatch):
    """N2：拉取期間（update-ref 之後、restore 之前）他 session 改了 memory/seed.md → 放棄本輪不覆蓋、recover 留著。"""
    repo, bare = repo_with_remote
    other = _clone(tmp_path, bare)
    (other / "memory" / "theirs.md").write_text("# theirs\n", encoding="utf-8")
    upstream = _push_from_other(other, "theirs")

    def fake(cmd, run):
        r = run()
        (repo / "memory" / "seed.md").write_text("# seed edited\n", encoding="utf-8")
        return r
    _inject(monkeypatch, lambda cmd, cwd: cmd[:2] == ["git", "update-ref"], fake)
    res = vs.sync_targets_inline([_target(repo)], CFG, log=lambda m: None)
    assert res[0]["pull"]["status"] == "behind" and "未提交編輯" in res[0]["pull"]["reason"], res
    assert _git(repo, "rev-parse", "refs/heads/main").stdout.strip() == upstream
    assert (repo / "memory" / "seed.md").read_text(encoding="utf-8") == "# seed edited\n"
    assert not (repo / "memory" / "theirs.md").exists()
    assert vs.recover_path(repo).exists()
    assert "未提交編輯" in vs.read_behind_record(repo)["reason"]


def test_pull_edit_during_isolated_rebase_aborts_before_update_ref(tmp_path, repo_with_remote, monkeypatch):
    """N2：分叉純記憶在隔離 worktree rebase 期間他 session 改了記憶檔 → update-ref 之前重驗、不動 ref、無 recover。"""
    repo, bare, head = _diverged_pure_memory(tmp_path, repo_with_remote)

    def fake(cmd, run):
        r = run()
        (repo / "memory" / "seed.md").write_text("# seed edited\n", encoding="utf-8")
        return r
    _inject(monkeypatch, lambda cmd, cwd: cmd[:3] == ["git", "worktree", "add"], fake)
    res = vs.sync_targets_inline([_target(repo)], CFG, log=lambda m: None)
    assert res[0]["pull"]["status"] == "behind" and "未提交編輯" in res[0]["pull"]["reason"], res
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == head
    assert not vs.recover_path(repo).exists() and _worktrees(repo) == 1
    assert (repo / "memory" / "seed.md").read_text(encoding="utf-8") == "# seed edited\n"


def test_pull_restore_uses_head_when_other_session_committed_after_update_ref(tmp_path, repo_with_remote, monkeypatch):
    """N3：ref 前進到 U 後、restore 前，他 session 在 main 又 commit C（只改 memory/seed.md）→ restore 以 HEAD=C 為源：
    index／工作樹＝C（上游新增的 theirs.md 到位）、無反向 staged、HEAD 仍是 C。"""
    repo, bare = repo_with_remote
    other = _clone(tmp_path, bare)
    (other / "memory" / "theirs.md").write_text("# theirs\n", encoding="utf-8")
    upstream = _push_from_other(other, "theirs")
    state = {}

    def fake(cmd, run):
        r = run()
        (repo / "memory" / "seed.md").write_text("# seed by C\n", encoding="utf-8")
        _git(repo, "commit", "-q", "-m", "C", "--", "memory/seed.md")
        state["c"] = _git(repo, "rev-parse", "HEAD").stdout.strip()
        return r
    _inject(monkeypatch, lambda cmd, cwd: cmd[:2] == ["git", "update-ref"], fake)
    res = vs.sync_targets_inline([_target(repo)], CFG, log=lambda m: None)
    assert res[0]["status"] == "ok" and res[0]["pull"]["status"] == "pulled", res
    c = state["c"]
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == c and c != upstream
    assert _git(repo, "rev-parse", f"{c}^").stdout.strip() == upstream
    assert (repo / "memory" / "theirs.md").exists()
    assert (repo / "memory" / "seed.md").read_text(encoding="utf-8") == "# seed by C\n"
    assert _status_set(repo) == set()
    assert not vs.recover_path(repo).exists()


def test_recover_ref_moved_to_non_descendant_waits_for_human(tmp_path, repo_with_remote):
    """N3：恢復時 ref 已離開 to 且不是 to 的後代（被 reset）→ 不 restore、recover 仍在、交人。"""
    repo, head, upstream = _half_recovered(tmp_path, repo_with_remote)
    _git(repo, "update-ref", "refs/heads/main", head, upstream)     # 退回 H：U 不是 H 的祖先
    res = vs.sync_targets_inline([_target(repo)], CFG_NOPUSH, log=lambda m: None)
    assert res[0]["status"] == "skipped" and "非其後代" in res[0]["reason"], res
    assert vs.recover_path(repo).exists()


def test_recover_untracked_file_named_like_upstream_added_not_overwritten(tmp_path, repo_with_remote):
    """B1：半完成狀態下他 session 建了未追蹤的 memory/theirs.md（U 新增、H 沒有）→ 不 restore（會被 U 版蓋掉）、
    內容原封不動、recover 仍在、`.behind`；刪掉該檔後再跑 → 恢復完成。"""
    repo, head, upstream = _half_recovered(tmp_path, repo_with_remote)
    (repo / "memory" / "theirs.md").write_text("# mine untracked\n", encoding="utf-8")
    res = vs.sync_targets_inline([_target(repo)], CFG_NOPUSH, log=lambda m: None)
    assert res[0]["status"] == "skipped" and "未提交編輯" in res[0]["reason"] and "theirs.md" in res[0]["reason"], res
    assert vs.recover_path(repo).exists()
    assert "未提交編輯" in vs.read_behind_record(repo)["reason"]
    assert (repo / "memory" / "theirs.md").read_text(encoding="utf-8") == "# mine untracked\n"
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == upstream
    (repo / "memory" / "theirs.md").unlink()
    logs, log = _logs()
    res = vs.sync_targets_inline([_target(repo)], CFG_NOPUSH, log=log)
    assert res[0]["status"] == "ok" and res[0]["committed"] == 0, (res, logs)
    assert not vs.recover_path(repo).exists() and any("恢復完成" in m for m in logs), logs
    assert (repo / "memory" / "theirs.md").read_text(encoding="utf-8") == "# theirs\n"
    assert _status_set(repo) == set()


def _restore_lock_once(monkeypatch, between):
    """第一次 `git restore` 假裝撞到 index.lock（rc 1），回傳前先跑 between()（模擬等待期間他 session 的動作）；
    之後的 restore 走真實 git。回 restore 呼叫次數的 list。"""
    calls = []

    def fake(cmd, run):
        calls.append(cmd)
        if len(calls) == 1:
            between()
            return subprocess.CompletedProcess(cmd, 1, "", "fatal: Unable to create '.git/index.lock': File exists.")
        return run()
    _inject(monkeypatch, lambda cmd, cwd: cmd[:2] == ["git", "restore"], fake)
    monkeypatch.setattr(vs.time, "sleep", lambda s: None)
    return calls


def test_recover_restore_lock_retry_revalidates_edit_made_while_waiting(tmp_path, repo_with_remote, monkeypatch):
    """B2：restore 第一次撞 index.lock，等待期間他 session 改了 memory/seed.md → 重試前重驗、不再 restore、
    編輯保留、recover 仍在。"""
    repo, head, upstream = _half_recovered(tmp_path, repo_with_remote)
    calls = _restore_lock_once(monkeypatch, lambda: (repo / "memory" / "seed.md").write_text("# seed edited\n", encoding="utf-8"))
    res = vs.sync_targets_inline([_target(repo)], CFG_NOPUSH, log=lambda m: None)
    assert res[0]["status"] == "skipped" and "未提交編輯" in res[0]["reason"] and "seed.md" in res[0]["reason"], res
    assert len(calls) == 1, calls
    assert vs.recover_path(repo).exists()
    assert (repo / "memory" / "seed.md").read_text(encoding="utf-8") == "# seed edited\n"
    assert not (repo / "memory" / "theirs.md").exists()
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == upstream


def test_recover_restore_lock_retry_uses_new_head_commit_as_source(tmp_path, repo_with_remote, monkeypatch):
    """B2：restore 第一次撞 index.lock，等待期間他 session 在 main 多 commit C（只改 memory/seed.md）→ 第二次以 HEAD=C
    為源：theirs.md 到位、seed.md 是 C 版、無反向 staged、recover 刪除。"""
    repo, head, upstream = _half_recovered(tmp_path, repo_with_remote)
    state = {}

    def commit_c():
        (repo / "memory" / "seed.md").write_text("# seed by C\n", encoding="utf-8")
        _git(repo, "commit", "-q", "-m", "C", "--", "memory/seed.md")
        state["c"] = _git(repo, "rev-parse", "HEAD").stdout.strip()
    calls = _restore_lock_once(monkeypatch, commit_c)
    logs, log = _logs()
    res = vs.sync_targets_inline([_target(repo)], CFG_NOPUSH, log=log)
    assert res[0]["status"] == "ok" and res[0]["committed"] == 0, (res, logs)
    assert len(calls) == 2 and calls[1][2] == f"--source={state['c']}", calls
    c = state["c"]
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == c and _git(repo, "rev-parse", f"{c}^").stdout.strip() == upstream
    assert (repo / "memory" / "theirs.md").exists()
    assert (repo / "memory" / "seed.md").read_text(encoding="utf-8") == "# seed by C\n"
    assert _status_set(repo) == set()
    assert not vs.recover_path(repo).exists() and any("恢復完成" in m for m in logs), logs


def test_pull_restore_failure_after_rebase_skips_push_until_recovered(tmp_path, repo_with_remote, monkeypatch):
    """B3：分叉純記憶 → 隔離 rebase 成功 → CAS 後 restore 失敗（recover 留著）→ 本輪不 push（upstream 仍是 U）；
    下輪恢復成功後才 push R。"""
    repo, bare, head = _diverged_pure_memory(tmp_path, repo_with_remote)
    upstream = _git(bare, "rev-parse", "main").stdout.strip()
    orig = _inject(monkeypatch, lambda cmd, cwd: cmd[:2] == ["git", "restore"],
                   lambda cmd, run: subprocess.CompletedProcess(cmd, 1, "", "simulated restore failure"))
    logs, log = _logs()
    res = vs.sync_targets_inline([_target(repo)], CFG, log=log)
    assert res[0]["status"] == "ok" and res[0]["pushed"] is False and res[0]["pull"]["status"] == "behind", (res, logs)
    assert res[0]["pull"]["recover_pending"] is True and "restore 記憶路徑失敗" in res[0]["pull"]["reason"]
    assert any("本輪不 push" in m for m in logs), logs
    rebased = _git(repo, "rev-parse", "HEAD").stdout.strip()
    assert rebased not in (head, upstream) and _git(repo, "rev-parse", f"{rebased}^").stdout.strip() == upstream
    assert _git(bare, "rev-parse", "main").stdout.strip() == upstream          # R 沒被推上去
    assert vs.recover_path(repo).exists()
    monkeypatch.setattr(vs, "_run", orig)
    logs, log = _logs()
    res = vs.sync_targets_inline([_target(repo)], CFG, log=log)
    assert res[0]["status"] == "ok" and res[0]["committed"] == 0 and res[0]["pushed"] is True, (res, logs)
    assert any("恢復完成" in m for m in logs), logs
    assert not vs.recover_path(repo).exists()
    assert _git(bare, "rev-parse", "main").stdout.strip() == rebased
    assert (repo / "memory" / "theirs.md").exists() and (repo / "memory" / "mine.md").exists()
    assert _status_set(repo) == set()


def _switch_branch_after_fetch(monkeypatch, repo):
    done = {}

    def fake(cmd, run):
        r = run()
        if not done:
            done["x"] = True
            _git(repo, "checkout", "-q", "-b", "feature")
        return r
    _inject(monkeypatch, lambda cmd, cwd: cmd[0] == "git" and "fetch" in cmd, fake)


def test_pull_branch_switched_after_fetch_skips_update_ref_and_restore(tmp_path, repo_with_remote, monkeypatch):
    """B2：fetch 後他 session 把倉切到 feature → 純記憶路徑不 update-ref、不 restore、無 recover 檔。"""
    repo, bare = repo_with_remote
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    other = _clone(tmp_path, bare)
    (other / "memory" / "theirs.md").write_text("# theirs\n", encoding="utf-8")
    _push_from_other(other, "theirs")
    _switch_branch_after_fetch(monkeypatch, repo)
    res = vs.sync_targets_inline([_target(repo)], CFG, log=lambda m: None)
    assert res[0]["pull"]["status"] == "behind" and "分支已切換" in res[0]["pull"]["reason"], res
    assert _git(repo, "rev-parse", "refs/heads/main").stdout.strip() == head
    assert _git(repo, "symbolic-ref", "HEAD").stdout.strip() == "refs/heads/feature"
    assert not (repo / "memory" / "theirs.md").exists()
    assert not vs.recover_path(repo).exists()
    assert "分支已切換" in vs.read_behind_record(repo)["reason"]


def test_pull_branch_switched_after_fetch_skips_ff_only(tmp_path, repo_with_remote, monkeypatch):
    """B2：含程式碼 incoming 的 ff-only 路徑同樣先驗分支。"""
    repo, bare = repo_with_remote
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    other = _clone(tmp_path, bare)
    (other / "code.py").write_text("print(9)\n", encoding="utf-8")
    _push_from_other(other, "code")
    _switch_branch_after_fetch(monkeypatch, repo)
    res = vs.sync_targets_inline([_target(repo)], CFG, log=lambda m: None)
    assert res[0]["pull"]["status"] == "behind" and "分支已切換" in res[0]["pull"]["reason"], res
    assert _git(repo, "rev-parse", "refs/heads/main").stdout.strip() == head
    assert (repo / "code.py").read_text(encoding="utf-8") == "print(1)\n"


def _diverged_pure_memory(tmp_path, repo_with_remote):
    repo, bare = repo_with_remote
    other = _clone(tmp_path, bare)
    _add_atom(other / "memory", "theirs")
    _push_from_other(other, "theirs atom")
    _add_atom(repo / "memory", "mine")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "mine atom")
    return repo, bare, _git(repo, "rev-parse", "HEAD").stdout.strip()


def test_worktree_add_failure_leaves_no_residue(tmp_path, repo_with_remote, monkeypatch):
    """B3：worktree add 真的建了目錄但回 rc≠0 → 清理仍跑：無目錄殘留、worktree list 不含它。"""
    repo, bare, head = _diverged_pure_memory(tmp_path, repo_with_remote)
    _inject(monkeypatch, lambda cmd, cwd: cmd[1:3] == ["worktree", "add"],
            lambda cmd, run: (run(), subprocess.CompletedProcess(cmd, 128, "", "simulated add failure"))[1])
    res = vs.sync_targets_inline([_target(repo)], CFG, log=lambda m: None)
    assert res[0]["pull"]["status"] == "behind" and "worktree add 失敗" in res[0]["pull"]["reason"], res
    assert "殘留" not in res[0]["pull"]["reason"]
    assert _worktrees(repo) == 1
    assert not list(Path(vs.tempfile.gettempdir()).glob("vcs-sync-wt-*"))
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == head


def test_worktree_remove_retry_succeeds_second_time(tmp_path, repo_with_remote, monkeypatch):
    """B3：remove 第一次 rc≠0（Windows 檔鎖）、第二次成功 → 拉成功且無殘留。"""
    repo, bare, head = _diverged_pure_memory(tmp_path, repo_with_remote)
    calls = []

    def fake(cmd, run):
        calls.append(1)
        if len(calls) == 1:
            return subprocess.CompletedProcess(cmd, 1, "", "simulated lock")
        return run()
    _inject(monkeypatch, lambda cmd, cwd: cmd[1:3] == ["worktree", "remove"], fake)
    res = vs.sync_targets_inline([_target(repo)], CFG, log=lambda m: None)
    assert res[0]["status"] == "ok" and res[0]["pull"]["status"] == "pulled", res
    assert len(calls) == 2
    assert _worktrees(repo) == 1
    assert not list(Path(vs.tempfile.gettempdir()).glob("vcs-sync-wt-*"))
    assert (repo / "memory" / "theirs.md").exists() and (repo / "memory" / "mine.md").exists()


def test_ls_files_u_failure_in_rebase_aborts(tmp_path, repo_with_remote, monkeypatch):
    """B4：隔離 worktree 內 ls-files -u rc≠0 → 視為失敗：abort、清 worktree、HEAD 不動。"""
    repo, bare, head = _diverged_pure_memory(tmp_path, repo_with_remote)
    _inject(monkeypatch, lambda cmd, cwd: cmd[1:3] == ["ls-files", "-u"] and "-z" in cmd,
            lambda cmd, run: subprocess.CompletedProcess(cmd, 128, "", "fatal: simulated"))
    res = vs.sync_targets_inline([_target(repo)], CFG, log=lambda m: None)
    assert res[0]["pull"]["status"] == "behind" and "ls-files -u 失敗" in res[0]["pull"]["reason"], res
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == head
    assert _worktrees(repo) == 1
    assert not list(Path(vs.tempfile.gettempdir()).glob("vcs-sync-wt-*"))


def test_ls_files_u_failure_in_check_skips(repo, monkeypatch):
    """B4：_git_check 的 ls-files -u rc≠0 → _Skip（不確定有無衝突就不動）。"""
    _inject(monkeypatch, lambda cmd, cwd: cmd[1:3] == ["ls-files", "-u"] and "-z" not in cmd,
            lambda cmd, run: subprocess.CompletedProcess(cmd, 128, "", "fatal: simulated"))
    (repo / "memory" / "new.md").write_text("# new\n", encoding="utf-8")
    res = vs.sync_targets_inline([_target(repo)], CFG_NOPUSH, log=lambda m: None)
    assert res[0]["status"] == "skipped" and "ls-files -u 失敗" in res[0]["reason"], res
    assert "?? memory/new.md" in _git(repo, "status", "--porcelain").stdout


def test_pull_diverged_same_scalar_field_takes_upstream(tmp_path, repo_with_remote):
    """W3：同一 atom 同一 scalar 欄位（confidence）兩側各改不同值 → 隔離 rebase 成功，結果取上游值。"""
    repo, bare = repo_with_remote
    other = _clone(tmp_path, bare)

    def set_conf(mem: Path, val: str):
        idx = json.loads((mem / "_atom_index.json").read_text(encoding="utf-8"))
        idx["atoms"][0]["confidence"] = val
        _write_index(mem, idx)
    set_conf(other / "memory", "[固]")
    remote_head = _push_from_other(other, "theirs conf")
    set_conf(repo / "memory", "[觀]")
    _git(repo, "commit", "-q", "-am", "mine conf")
    logs, log = _logs()
    res = vs.sync_targets_inline([_target(repo)], CFG, log=log)
    assert res[0]["status"] == "ok" and res[0]["pull"]["status"] == "pulled", (res, logs)
    # 本地 commit 只改這個欄位，取上游後變空 commit，rebase 丟掉 → HEAD 就是上游
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == remote_head
    idx = json.loads((repo / "memory" / "_atom_index.json").read_text(encoding="utf-8"))
    assert idx["atoms"][0]["confidence"] == "[固]"
    assert _status_set(repo) == set() and _worktrees(repo) == 1


def test_parse_check_attr_z():
    out = "memory/a b.json\0merge\0atomindex\0memory/x.md\0merge\0unspecified\0"
    assert vs._parse_check_attr_z(out) == {"memory/a b.json": "atomindex", "memory/x.md": "unspecified"}
    assert vs._parse_check_attr_z("") == {}


def test_pull_reason_within_cooldown_skips_fetch(repo_with_remote, monkeypatch):
    """W1：全部請求都是 reason=pull、last_pull 在 cooldown 內且記憶路徑無變更 → 不 fetch；有變更／非 pull／過期 → 照拉。"""
    repo, bare = repo_with_remote
    fetches = []
    _inject(monkeypatch, lambda cmd, cwd: cmd[0] == "git" and "fetch" in cmd,
            lambda cmd, run: fetches.append(1) or run())
    vs.update_root_record(_target(repo), last_pull=vs._now_iso())
    logs, log = _logs()
    res = vs.sync_targets_inline([_target(repo)], CFG, log=log, reason="pull")
    assert res[0]["status"] == "ok" and res[0]["pull"]["status"] == "cooldown", (res, logs)
    assert fetches == [] and any("cooldown" in m for m in logs)
    (repo / "memory" / "new.md").write_text("# new\n", encoding="utf-8")
    res = vs.sync_targets_inline([_target(repo)], CFG, log=lambda m: None, reason="pull")
    assert res[0]["committed"] == 1 and res[0]["pull"]["status"] == "up-to-date" and fetches == [1], res
    res = vs.sync_targets_inline([_target(repo)], CFG, log=lambda m: None, reason="harvest")
    assert res[0]["pull"]["status"] == "up-to-date" and len(fetches) == 2, res
    vs.update_root_record(_target(repo), last_pull="2020-01-01T00:00:00")
    res = vs.sync_targets_inline([_target(repo)], CFG, log=lambda m: None, reason="pull")
    assert res[0]["pull"]["status"] == "up-to-date" and len(fetches) == 3, res
    cfg = {"vcs_sync": {**CFG["vcs_sync"], "pull": {"cooldown_s": 0}}}
    vs.update_root_record(_target(repo), last_pull=vs._now_iso())
    res = vs.sync_targets_inline([_target(repo)], cfg, log=lambda m: None, reason="pull")
    assert res[0]["pull"]["status"] == "up-to-date" and len(fetches) == 4, res


def test_pull_up_to_date_clears_behind_marker(repo_with_remote, vector_calls):
    repo, bare = repo_with_remote
    vs.write_behind(repo, "舊標記")
    res = vs.sync_targets_inline([_target(repo)], CFG, log=lambda m: None)
    assert res[0]["status"] == "ok" and res[0]["pull"]["status"] == "up-to-date", res
    assert not vs.marker_path(repo, "behind").exists()
    assert vs.load_roots()[repo.resolve().as_posix()]["pulled_commits"] == 0
    assert vector_calls == []


# ─── 鎖（OS 互斥） ───────────────────────────────────────────────────────────

def test_lock_concurrent_threads_only_one_wins(repo):
    path = vs.marker_path(repo, "lock")
    locks = [vs.FileLock(path) for _ in range(8)]
    start = threading.Barrier(8)
    won = []

    def go(lk):
        start.wait()
        if lk.acquire():
            won.append(lk)
    ts = [threading.Thread(target=go, args=(lk,)) for lk in locks]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert len(won) == 1
    assert vs.FileLock.is_held(path)
    assert path.read_text(encoding="utf-8") == str(os.getpid())
    won[0].release()
    assert not vs.FileLock.is_held(path)
    assert path.read_text(encoding="utf-8") == "0"


_HOLDER = textwrap.dedent("""
    import sys, time
    from pathlib import Path
    sys.path.insert(0, sys.argv[1])
    import wg_vcs_sync as vs
    vs.SYNC_DIR = Path(sys.argv[2])
    ok = vs.acquire_lock(Path(sys.argv[3]))
    print("locked" if ok else "failed", flush=True)
    time.sleep(60)
""")


def _spawn_holder(sync_dir: Path, root: Path) -> subprocess.Popen:
    p = subprocess.Popen([sys.executable, "-c", _HOLDER, str(CLAUDE / "hooks"), str(sync_dir), str(root)],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
    line = p.stdout.readline().strip()
    assert line == "locked", (line, p.stderr.read())
    return p


def _kill_holder(p: subprocess.Popen, root: Path) -> None:
    """sys.executable 可能是 shim：真正持鎖的是鎖檔記錄的 pid，兩個都殺，再等 OS 釋放。"""
    import signal
    import time
    try:
        os.kill(int(vs.marker_path(root, "lock").read_text(encoding="utf-8")), signal.SIGTERM)
    except (OSError, ValueError):
        pass
    p.kill()
    p.wait(10)
    for _ in range(100):
        if not vs.lock_is_live(root):
            return
        time.sleep(0.05)


def test_lock_held_by_other_process_then_released_on_death(repo, sync_dir):
    holder = _spawn_holder(sync_dir, repo)
    try:
        assert vs.lock_is_live(repo)
        assert not vs.acquire_lock(repo)
        pid = int(vs.marker_path(repo, "lock").read_text(encoding="utf-8"))
        assert pid > 0 and pid != os.getpid()   # 持有者 pid（sys.executable 可能是 shim，與 holder.pid 不必相同）
    finally:
        _kill_holder(holder, repo)
    assert not vs.lock_is_live(repo)
    assert vs.acquire_lock(repo)
    vs.release_lock(repo)


def test_locked_root_keeps_request_for_holder(repo, sync_dir):
    """B3：被鎖拒 → 不跑、請求留在 .req/；持鎖者（下一輪 inline）接手消費。"""
    holder = _spawn_holder(sync_dir, repo)
    try:
        (repo / "memory" / "new.md").write_text("# new\n", encoding="utf-8")
        res = vs.sync_targets_inline([_target(repo)], CFG_NOPUSH, log=lambda m: None)
        assert res[0]["status"] == "locked" and res[0]["pending"] == 1
        assert "?? memory/new.md" in _git(repo, "status", "--porcelain").stdout
        assert vs.pending_requests(repo) == 1
    finally:
        _kill_holder(holder, repo)
    res = vs.sync_targets_inline([_target(repo)], CFG_NOPUSH, log=lambda m: None, enqueue=False)
    assert res[0]["status"] == "ok" and res[0]["committed"] == 1
    assert vs.pending_requests(repo) == 0


# ─── 請求交接 ────────────────────────────────────────────────────────────────

def test_requests_merged_across_pathspecs_and_consumed(repo):
    """B3：.req/ 內另一請求帶不同 pathspec → 一輪聯集提交；跑完請求檔全被消費。"""
    (repo / "docs").mkdir()
    (repo / "docs" / "d.md").write_text("# d\n", encoding="utf-8")
    (repo / "memory" / "new.md").write_text("# new\n", encoding="utf-8")
    vs.write_request(repo, ["docs"], reason="other-session", session_id="s2")
    res = vs.sync_targets_inline([_target(repo)], CFG_NOPUSH, log=lambda m: None)
    assert res[0]["status"] == "ok" and res[0]["committed"] == 2 and res[0]["rounds"] == 1, res
    assert _head_files(repo) == {"memory/new.md", "docs/d.md"}
    assert vs.pending_requests(repo) == 0
    assert vs.pending_requests(repo, include_inflight=True) == 0   # inflight 空目錄可留，請求檔不可留


def test_request_arriving_during_run_triggers_second_round(repo, monkeypatch):
    (repo / "memory" / "first.md").write_text("# 1\n", encoding="utf-8")
    orig = vs._git_sync
    calls = []

    def wrapped(t, cfg, env, log, branch, *a, **k):
        calls.append(1)
        r = orig(t, cfg, env, log, branch, *a, **k)
        if len(calls) == 1:
            (repo / "memory" / "second.md").write_text("# 2\n", encoding="utf-8")
            vs.write_request(t.root, ["memory"], reason="late")
        return r
    monkeypatch.setattr(vs, "_git_sync", wrapped)
    res = vs.sync_targets_inline([_target(repo)], CFG_NOPUSH, log=lambda m: None)
    assert res[0]["rounds"] == 2 and len(calls) == 2
    assert _head_files(repo) == {"memory/second.md"}
    assert "second.md" not in _git(repo, "status", "--porcelain").stdout
    assert vs.pending_requests(repo) == 0


def test_read_retired_paths_only_validated(tmp_path):
    led = vs.LEDGER_DIR
    led.mkdir(parents=True)
    rows = [
        {"validated": True, "items": [{"action": "retired", "path": "memory/a.md"}]},
        {"validated": False, "items": [{"action": "retired", "path": "memory/b.md"}]},
        {"items": [{"action": "retired", "path": "memory/c.md"}]},
        {"validated": True, "items": [{"action": "created", "path": "memory/d.md"}]},
    ]
    (led / "sid1.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    assert vs.read_retired_paths("sid1") == ["memory/a.md"]


def test_roots_record_concurrent_updates_all_survive(tmp_path):
    """W5：多執行緒同時讀改寫 roots.json（共用 roots.lock）→ 沒有一筆被蓋掉。"""
    targets = [vs.SyncTarget("git", tmp_path / f"r{i}", ["memory"]) for i in range(12)]
    ts = [threading.Thread(target=vs.update_root_record, args=(t,), kwargs={"touch_sync": True}) for t in targets]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert set(vs.load_roots()) == {t.root.as_posix() for t in targets}


def test_roots_lock_timeout_leaves_roots_json_untouched(tmp_path, monkeypatch):
    """N6：roots.lock 取不到 → 不讀改寫（無鎖寫入會整份蓋掉別人剛寫的）、回 False。"""
    t = vs.SyncTarget("git", tmp_path / "r0", ["memory"])
    assert vs.update_root_record(t, touch_sync=True) is True
    before = (vs.SYNC_DIR / "roots.json").read_text(encoding="utf-8")
    monkeypatch.setattr(vs.FileLock, "acquire", lambda self, wait_s=0.0: False)
    assert vs.update_root_record(t, last_error="x") is False
    assert (vs.SYNC_DIR / "roots.json").read_text(encoding="utf-8") == before


def test_request_survives_stop_midway_and_is_redone_next_run(repo, monkeypatch):
    """N5：請求先領取到 inflight，同步中途 _Stop → 請求仍在；下次重跑連同殘留一起消費、成功後才刪。"""
    (repo / "memory" / "new.md").write_text("# new\n", encoding="utf-8")
    vs.write_request(repo, ["memory"], reason="harvest", session_id="s1")
    orig = vs._git_sync

    def boom(t, cfg, env, log, branch, *a, **k):
        raise vs._Stop("模擬中途失敗")
    monkeypatch.setattr(vs, "_git_sync", boom)
    res = vs.sync_targets_inline([_target(repo)], CFG_NOPUSH, log=lambda m: None, enqueue=False)
    assert res[0]["status"] == "unpushed"
    assert vs.pending_requests(repo) == 0                          # 已領取，不再是「未領取」
    assert vs.pending_requests(repo, include_inflight=True) == 1   # 但沒丟
    assert vs.read_unpushed(repo) == "模擬中途失敗"
    monkeypatch.setattr(vs, "_git_sync", orig)
    res = vs.sync_targets_inline([_target(repo)], CFG_NOPUSH, log=lambda m: None, enqueue=False)
    assert res[0]["status"] == "ok" and res[0]["committed"] == 1, res
    assert vs.pending_requests(repo, include_inflight=True) == 0


def test_spawn_failure_marks_unpushed_and_keeps_request(repo, monkeypatch):
    import wg_core
    monkeypatch.setattr(wg_core, "resolve_project_root", None)
    monkeypatch.setattr(vs, "collect_sync_targets", lambda cwd, cfg, claude_dir=None: [_target(repo)])
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(OSError("no pythonw")))
    assert vs.spawn_vcs_sync("sid", str(repo), "test", config=CFG) == 0
    assert vs.pending_requests(repo) == 1
    assert "worker 起不來" in vs.read_unpushed(repo)
    assert "worker 起不來" in vs.load_roots()[repo.resolve().as_posix()]["last_error"]


def test_collect_targets_groups_by_vcs_root(tmp_path, monkeypatch):
    claude = _git_repo(tmp_path / "claude")
    (claude / "_AIDocs" / "_atoms").mkdir(parents=True)
    proj = _git_repo(tmp_path / "proj")
    (proj / ".claude" / "memory").mkdir(parents=True)
    import wg_core
    monkeypatch.setattr(wg_core, "resolve_project_root", None)
    targets = vs.collect_sync_targets(str(proj), CFG, claude_dir=claude)
    by_root = {t.root: t for t in targets}
    # 預設 root_extra_pathspecs（計數標記檔）接在記憶 pathspec 之後；git 不要求檔案已存在
    assert by_root[claude.resolve()].pathspecs == [
        "memory", "_AIDocs/_atoms", "TECH.md", "_AIDocs/_INDEX.md", "_AIDocs/DocIndex-System.md"]
    assert by_root[proj.resolve()].pathspecs == [".claude/memory"]


def test_collect_targets_root_extra_pathspecs_join_root_target_only(tmp_path, monkeypatch):
    """根層計數標記檔（TECH.md 等）進根層 pathspec、不進 mem_dirs；git 不要求檔案已存在；專案層不受影響。"""
    claude = _git_repo(tmp_path / "claude")
    proj = _git_repo(tmp_path / "proj")
    (proj / ".claude" / "memory").mkdir(parents=True)
    import wg_core
    monkeypatch.setattr(wg_core, "resolve_project_root", None)
    cfg = {"vcs_sync": {**CFG["vcs_sync"], "root_extra_pathspecs": ["TECH.md", "_AIDocs/_INDEX.md"]}}
    by_root = {t.root: t for t in vs.collect_sync_targets(str(proj), cfg, claude_dir=claude)}
    root_t = by_root[claude.resolve()]
    assert root_t.pathspecs == ["memory", "TECH.md", "_AIDocs/_INDEX.md"]
    assert [p.name for p in root_t.mem_dirs] == ["memory"]
    assert by_root[proj.resolve()].pathspecs == [".claude/memory"]


# ─── svn ─────────────────────────────────────────────────────────────────────

def _svn(cwd: Path, *args, check=True):
    r = subprocess.run([SVN, "--non-interactive", *args], cwd=str(cwd), capture_output=True)
    if check and r.returncode != 0:
        raise AssertionError(f"svn {' '.join(args)} failed: {r.stderr.decode('utf-8', 'replace')}")
    return r


def _svn_url(repo_dir: Path) -> str:
    return "file:///" + repo_dir.resolve().as_posix().lstrip("/")


@pytest.fixture
def svn_wc(tmp_path):
    if not HAS_SVN:
        pytest.skip("svn 不在本機")
    repo_dir = tmp_path / "svnrepo"
    subprocess.run([str(Path(SVN).with_name("svnadmin" + Path(SVN).suffix)), "create", str(repo_dir)],
                   check=True, capture_output=True)
    wc = tmp_path / "wc"
    _svn(tmp_path, "checkout", "-q", _svn_url(repo_dir), str(wc))
    (wc / "memory").mkdir()
    (wc / "memory" / "a.md").write_text("".join(f"line {i}\n" for i in range(1, 11)), encoding="utf-8")
    _write_index(wc / "memory", INDEX_JSON)
    _svn(wc, "add", "-q", "memory")
    _svn(wc, "commit", "-q", "-m", "seed", "memory")
    return wc, repo_dir


def _svn_ls(repo_dir: Path, sub="memory"):
    """repo 內 sub 的檔名集合，去掉 fixture 固定帶的索引三檔（每個測試都有、不是測試對象）。"""
    names = set(_svn(repo_dir, "ls", f"{_svn_url(repo_dir)}/{sub}").stdout.decode().split())
    return names - {"MEMORY.md", "_ATOM_INDEX.md", "_atom_index.json"}


def test_svn_new_atom_added_and_committed_exclude_skipped(svn_wc):
    wc, repo_dir = svn_wc
    (wc / "memory" / "new.md").write_text("# 新\n", encoding="utf-8")
    (wc / "memory" / "new.access.json").write_text("{}", encoding="utf-8")
    (wc / "memory" / "sub").mkdir()
    (wc / "memory" / "sub" / "deep.md").write_text("# deep\n", encoding="utf-8")
    (wc / "memory" / "sub" / "deep.access.json").write_text("{}", encoding="utf-8")
    logs, log = _logs()
    res = vs.sync_targets_inline([_target(wc, "svn")], CFG, log=log)
    assert res[0]["status"] == "ok" and res[0]["added"] == 2, (res, logs)
    assert _svn_ls(repo_dir) == {"a.md", "new.md", "sub/"}
    assert _svn_ls(repo_dir, "memory/sub") == {"deep.md"}
    st = _svn(wc, "status", "--xml", "memory").stdout
    assert b"new.access.json" in st and b"deep.access.json" in st
    assert not vs.marker_path(wc, "unpushed").exists()


def test_svn_precise_targets_leave_sibling_added_file_uncommitted(svn_wc):
    """B5：`.claude/settings.json` 已 svn add 未 commit；worker 只提交 `.claude/memory/a.md` 與必要祖先。"""
    wc, repo_dir = svn_wc
    (wc / ".claude" / "memory").mkdir(parents=True)
    (wc / ".claude" / "settings.json").write_text("{}", encoding="utf-8")
    (wc / ".claude" / "memory" / "a.md").write_text("# a\n", encoding="utf-8")
    _svn(wc, "add", "-q", "--parents", ".claude/settings.json")   # .claude（depth empty）+ settings.json 皆 added
    t = vs.SyncTarget("svn", wc.resolve(), [".claude/memory"], [(wc / ".claude" / "memory").resolve()])
    logs, log = _logs()
    res = vs.sync_targets_inline([t], CFG, log=log)
    assert res[0]["status"] == "ok" and res[0]["added"] == 1, (res, logs)
    assert _svn_ls(repo_dir, ".claude") == {"memory/"}
    assert _svn_ls(repo_dir, ".claude/memory") == {"a.md"}
    entries = vs._svn_entries(_svn(wc, "status", "--xml", ".claude").stdout)
    assert [i for p, i, _ in entries if p.endswith("settings.json")] == ["added"]


def _svn_wc2(tmp_path: Path, repo_dir: Path) -> Path:
    wc2 = tmp_path / "wc2"
    _svn(tmp_path, "checkout", "-q", _svn_url(repo_dir), str(wc2))
    return wc2


def test_svn_retired_missing_deleted_other_missing_skips_update(svn_wc, tmp_path):
    """其他 missing（未登記退役）→ 本輪不 update（update 會把檔補回）、`.behind`；退役的照刪、提交照常。"""
    wc, repo_dir = svn_wc
    (wc / "memory" / "old.md").write_text("# old\n", encoding="utf-8")
    (wc / "memory" / "keep.md").write_text("# keep\n", encoding="utf-8")
    _svn(wc, "add", "-q", "memory/old.md", "memory/keep.md")
    _svn(wc, "commit", "-q", "-m", "two", "memory")
    wc2 = _svn_wc2(tmp_path, repo_dir)
    (wc2 / "memory" / "from2.md").write_text("# 2\n", encoding="utf-8")
    _svn(wc2, "add", "-q", "memory/from2.md")
    _svn(wc2, "commit", "-q", "-m", "wc2 adds", "memory")
    (wc / "memory" / "old.md").unlink()
    (wc / "memory" / "keep.md").unlink()
    res = vs.sync_targets_inline([_target(wc, "svn")], CFG, log=lambda m: None,
                                 retired_paths=[str(wc / "memory" / "old.md")])
    assert res[0]["status"] == "ok" and res[0]["deleted"] == 1 and res[0]["pull"]["status"] == "skipped", res
    assert _svn_ls(repo_dir) == {"a.md", "keep.md", "from2.md"}
    assert not (wc / "memory" / "from2.md").exists()                      # 沒 update
    assert "keep.md" in vs.read_behind_record(wc)["reason"]
    entries = vs._svn_entries(_svn(wc, "status", "--xml", "memory").stdout)
    assert [i for p, i, _ in entries if p.endswith("keep.md")] == ["missing"]


def test_svn_retired_missing_deleted_then_updated(svn_wc, tmp_path):
    """validated retired 且 missing → 先 schedule-delete 再 update：退役檔不會被 update 補回，上游新檔拉進來。"""
    wc, repo_dir = svn_wc
    (wc / "memory" / "old.md").write_text("# old\n", encoding="utf-8")
    _svn(wc, "add", "-q", "memory/old.md")
    _svn(wc, "commit", "-q", "-m", "old", "memory")
    wc2 = _svn_wc2(tmp_path, repo_dir)
    (wc2 / "memory" / "from2.md").write_text("# 2\n", encoding="utf-8")
    _svn(wc2, "add", "-q", "memory/from2.md")
    _svn(wc2, "commit", "-q", "-m", "wc2 adds", "memory")
    (wc / "memory" / "old.md").unlink()
    res = vs.sync_targets_inline([_target(wc, "svn")], CFG, log=lambda m: None,
                                 retired_paths=[str(wc / "memory" / "old.md")])
    assert res[0]["status"] == "ok" and res[0]["deleted"] == 1 and res[0]["pull"]["status"] == "ok", res
    assert (wc / "memory" / "from2.md").exists() and not (wc / "memory" / "old.md").exists()
    assert "old.md" not in _svn_ls(repo_dir) and "from2.md" in _svn_ls(repo_dir)
    assert not vs.marker_path(wc, "behind").exists()
    assert vs.load_roots()[wc.resolve().as_posix()]["last_pull"]


def test_svn_upfront_update_merges_then_commits(svn_wc, tmp_path):
    wc, repo_dir = svn_wc
    wc2 = _svn_wc2(tmp_path, repo_dir)
    a2 = wc2 / "memory" / "a.md"
    a2.write_text(a2.read_text(encoding="utf-8").replace("line 1\n", "line 1 (wc2)\n"), encoding="utf-8")
    _svn(wc2, "commit", "-q", "-m", "wc2 edits top", "memory")
    a1 = wc / "memory" / "a.md"
    a1.write_text(a1.read_text(encoding="utf-8").replace("line 10\n", "line 10 (wc1)\n"), encoding="utf-8")
    logs, log = _logs()
    res = vs.sync_targets_inline([_target(wc, "svn")], CFG, log=log)
    assert res[0]["status"] == "ok" and res[0]["pull"]["status"] == "ok", (res, logs)
    assert not any("update 後重試" in m for m in logs), logs
    head = _svn(repo_dir, "cat", f"{_svn_url(repo_dir)}/memory/a.md").stdout.decode("utf-8")
    assert "line 1 (wc2)" in head and "line 10 (wc1)" in head
    assert not vs.marker_path(wc, "unpushed").exists()


def test_svn_out_of_date_update_then_retry_when_pull_disabled(svn_wc, tmp_path):
    wc, repo_dir = svn_wc
    wc2 = _svn_wc2(tmp_path, repo_dir)
    a2 = wc2 / "memory" / "a.md"
    a2.write_text(a2.read_text(encoding="utf-8").replace("line 1\n", "line 1 (wc2)\n"), encoding="utf-8")
    _svn(wc2, "commit", "-q", "-m", "wc2 edits top", "memory")
    a1 = wc / "memory" / "a.md"
    a1.write_text(a1.read_text(encoding="utf-8").replace("line 10\n", "line 10 (wc1)\n"), encoding="utf-8")
    logs, log = _logs()
    res = vs.sync_targets_inline([_target(wc, "svn")], CFG_NOPULL, log=log)
    assert res[0]["status"] == "ok", (res, logs)
    assert any("update 後重試" in m for m in logs), logs
    head = _svn(repo_dir, "cat", f"{_svn_url(repo_dir)}/memory/a.md").stdout.decode("utf-8")
    assert "line 1 (wc2)" in head and "line 10 (wc1)" in head
    assert not vs.marker_path(wc, "unpushed").exists()


def test_svn_update_index_conflict_resolved_then_committed(svn_wc, tmp_path):
    """update 衝突只在 _atom_index.json（兩側各加一條）→ resolver 解開 → 提交含兩側 atom。"""
    wc, repo_dir = svn_wc
    wc2 = _svn_wc2(tmp_path, repo_dir)
    _add_atom(wc2 / "memory", "theirs")
    _svn(wc2, "add", "-q", "memory/theirs.md")
    _svn(wc2, "commit", "-q", "-m", "theirs atom", "memory")
    _add_atom(wc / "memory", "mine")
    logs, log = _logs()
    res = vs.sync_targets_inline([_target(wc, "svn")], CFG, log=log)
    assert res[0]["status"] == "ok" and res[0]["pull"]["status"] == "ok", (res, logs)
    assert any("resolver 解開" in m for m in logs), logs
    head = json.loads(_svn(repo_dir, "cat", f"{_svn_url(repo_dir)}/memory/_atom_index.json").stdout.decode("utf-8"))
    assert {a["name"] for a in head["atoms"]} == {"seed", "theirs", "mine"}
    assert "mine.md" in _svn_ls(repo_dir) and "theirs.md" in _svn_ls(repo_dir)
    assert not vs.marker_path(wc, "behind").exists()


def test_svn_update_atom_body_conflict_marks_behind_no_commit(svn_wc, tmp_path):
    wc, repo_dir = svn_wc
    wc2 = _svn_wc2(tmp_path, repo_dir)
    a2 = wc2 / "memory" / "a.md"
    a2.write_text(a2.read_text(encoding="utf-8").replace("line 5\n", "line 5 (wc2)\n"), encoding="utf-8")
    _svn(wc2, "commit", "-q", "-m", "wc2 same line", "memory")
    a1 = wc / "memory" / "a.md"
    a1.write_text(a1.read_text(encoding="utf-8").replace("line 5\n", "line 5 (wc1)\n"), encoding="utf-8")
    rev_before = _svn(repo_dir, "info", "--show-item", "revision", _svn_url(repo_dir)).stdout.strip()
    logs, log = _logs()
    res = vs.sync_targets_inline([_target(wc, "svn")], CFG, log=log)
    assert res[0]["status"] == "unpushed" and "a.md(text)" in res[0]["reason"], (res, logs)
    assert _svn(repo_dir, "info", "--show-item", "revision", _svn_url(repo_dir)).stdout.strip() == rev_before
    assert "a.md(text)" in vs.read_behind_record(wc)["reason"]
    assert "衝突" in vs.read_unpushed(wc)
    assert [p for p, k in vs._svn_conflicts(_svn(wc, "status", "--xml", "memory").stdout)] and \
           {k for _, k in vs._svn_conflicts(_svn(wc, "status", "--xml", "memory").stdout)} == {"text"}


def test_svn_update_failure_goes_to_pull_error_not_last_error(svn_wc, monkeypatch):
    """W2：svn update 非零 → `.behind` + pull_error；push 側 last_error 與 `.unpushed` 不碰，本輪照常（沒東西可 commit）。"""
    wc, repo_dir = svn_wc
    orig = vs._run

    def run(cmd, cwd, timeout, env, text=True):
        if cmd[0] == SVN and "update" in cmd:
            return subprocess.CompletedProcess(cmd, 1, b"", b"svn: E170013: Unable to connect to a repository\n")
        return orig(cmd, cwd, timeout, env, text)
    monkeypatch.setattr(vs, "_run", run)
    res = vs.sync_targets_inline([_target(wc, "svn")], CFG, log=lambda m: None)
    assert res[0]["status"] == "ok" and res[0]["pull"]["status"] == "error", res
    assert "svn update 失敗" in vs.read_behind_record(wc)["reason"] and "E170013" in vs.read_behind_record(wc)["reason"]
    rec = vs.load_roots()[wc.resolve().as_posix()]
    assert "svn update 失敗" in rec["pull_error"] and rec["last_error"] is None
    assert not vs.marker_path(wc, "unpushed").exists()


def test_svn_update_exe_missing_goes_to_pull_error(svn_wc, monkeypatch):
    """W2：svn update 起不了程序（執行檔不存在 → FileNotFoundError）→ 同非零：`.behind` + pull_error，last_error 不碰。"""
    wc, repo_dir = svn_wc
    orig = vs._run

    def run(cmd, cwd, timeout, env, text=True):
        if cmd[0] == SVN and "update" in cmd:
            raise FileNotFoundError(2, "No such file or directory", cmd[0])
        return orig(cmd, cwd, timeout, env, text)
    monkeypatch.setattr(vs, "_run", run)
    res = vs.sync_targets_inline([_target(wc, "svn")], CFG, log=lambda m: None)
    assert res[0]["status"] == "ok" and res[0]["pull"]["status"] == "error", res
    assert "FileNotFoundError" in vs.read_behind_record(wc)["reason"]
    rec = vs.load_roots()[wc.resolve().as_posix()]
    assert "FileNotFoundError" in rec["pull_error"] and rec["last_error"] is None
    assert not vs.marker_path(wc, "unpushed").exists()


def test_svn_conflicts_parser_distinguishes_text_property_tree():
    xml = b"""<?xml version="1.0"?><status><target path="memory">
      <entry path="memory/a.md"><wc-status item="conflicted" props="none"/></entry>
      <entry path="memory/b.md"><wc-status item="normal" props="conflicted"/></entry>
      <entry path="memory/c.md"><wc-status item="normal" props="none" tree-conflicted="true"/></entry>
      <entry path="memory/d.md"><wc-status item="modified" props="none"/></entry>
    </target></status>"""
    assert vs._svn_conflicts(xml) == [("memory/a.md", "text"), ("memory/b.md", "property"), ("memory/c.md", "tree")]


# ─── SessionStart advisory ───────────────────────────────────────────────────

@pytest.fixture
def ss(monkeypatch, tmp_path):
    from handlers import session_start as mod
    monkeypatch.setattr(mod, "CLAUDE_DIR", tmp_path / "no-git-here")
    return mod


def test_unpushed_advisory_covers_roots_json(tmp_path, repo_with_remote, ss):
    repo, bare = repo_with_remote
    (repo / "memory" / "new.md").write_text("# new\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "ahead")
    svn_root = tmp_path / "svnroot"
    svn_root.mkdir()
    vs.update_root_record(_target(repo))
    vs.update_root_record(_target(svn_root, "svn"))
    vs.write_unpushed(svn_root, "svn commit 失敗 ['E160024']: tree conflict")
    lines = ss._unpushed_advisory()
    assert len(lines) == 2, lines
    assert any(repo.resolve().as_posix() in ln and "1 筆 commit 未 push" in ln for ln in lines)
    assert any(svn_root.as_posix() in ln and "E160024" in ln for ln in lines)


def test_unpushed_advisory_clears_when_query_ok_and_nothing_ahead(repo_with_remote, ss):
    """N7：查詢成功且 ahead=0 → 已解決：清標記＋roots.json last_error，HEAD 不必變（使用者補推原 HEAD 也算）。"""
    repo, bare = repo_with_remote
    (repo / "memory" / "m.md").write_text("# m\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "memory")
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    vs.update_root_record(_target(repo), last_error="git push 被拒: rejected")
    vs.write_unpushed(repo, "git push 被拒: rejected", head_oid=head)
    lines = ss._unpushed_advisory()
    assert len(lines) == 1 and "1 筆 commit 未 push" in lines[0], lines   # ahead=1 → 報、不清
    assert vs.marker_path(repo, "unpushed").exists()
    _git(repo, "push", "-q", "origin", "main")                              # 使用者直接推原 HEAD
    assert ss._unpushed_advisory() == []
    assert not vs.marker_path(repo, "unpushed").exists()
    assert vs.load_roots()[repo.resolve().as_posix()]["last_error"] is None


def test_unpushed_advisory_git_query_failure_keeps_marker(repo, ss):
    """N7：rev-list rc≠0（無 upstream）不得當 ahead=0 → 標記照報、不刪。"""
    vs.update_root_record(_target(repo))
    vs.write_unpushed(repo, "git push 被拒: rejected", head_oid=_git(repo, "rev-parse", "HEAD").stdout.strip())
    lines = ss._unpushed_advisory()
    assert len(lines) == 1 and "git push 被拒" in lines[0], lines
    assert vs.marker_path(repo, "unpushed").exists()


def test_unpushed_advisory_surfaces_skip_and_orphan_requests(repo, ss):
    vs.update_root_record(_target(repo), last_error="skip: MERGE_HEAD 存在（合併／rebase 進行中）")
    vs.write_request(repo, ["memory"], reason="harvest")
    lines = ss._unpushed_advisory()
    assert len(lines) == 2, lines
    assert "MERGE_HEAD" in lines[0] and "1 筆同步請求無人處理" in lines[1]


def test_pull_advisory_reports_pulled_once_and_behind(repo, ss):
    """「拉入 N 筆」同一 last_pull 只報一次（pull_reported_at）；新的 last_pull 再報；`.behind` 每次都報。"""
    vs.update_root_record(_target(repo), last_pull="2026-10-01T10:00:00", pulled_commits=3, pull_error=None)
    lines = ss._unpushed_advisory()
    assert len(lines) == 1 and "拉入 3 筆 commit" in lines[0] and "候選池" in lines[0], lines
    assert vs.load_roots()[repo.resolve().as_posix()]["pull_reported_at"] == "2026-10-01T10:00:00"
    assert ss._unpushed_advisory() == []                                       # 同一次拉入不再報
    vs.write_behind(repo, "上游含非記憶 commit abc12345（code.py）且本地有未提交改動")
    lines = ss._unpushed_advisory()
    assert len(lines) == 1 and "落後未併入" in lines[0] and "code.py" in lines[0], lines
    vs.update_root_record(_target(repo), last_pull="2026-10-01T11:00:00", pulled_commits=2, pull_error=None)
    lines = ss._unpushed_advisory()
    assert len(lines) == 2 and "拉入 2 筆" in lines[0], lines                   # 新的 last_pull → 再報一次
    vs.update_root_record(_target(repo), last_pull="2026-10-01T12:00:00", pulled_commits=0, pull_error=None)
    vs.clear_behind(repo)
    assert ss._unpushed_advisory() == []


def test_pull_advisory_fields_survive_unpushed_clear(repo_with_remote, ss):
    """解除 `.unpushed` 只清 last_error；pull 欄位與 `.behind` 不碰。"""
    repo, bare = repo_with_remote
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    vs.update_root_record(_target(repo), last_error="git push 被拒", last_pull="2026-10-01T10:00:00",
                          pulled_commits=2, pull_error="fetch 逾時")
    vs.write_unpushed(repo, "git push 被拒", head_oid=head)
    vs.write_behind(repo, "fetch 逾時 20s")
    lines = ss._unpushed_advisory()
    rec = vs.load_roots()[repo.resolve().as_posix()]
    assert rec["last_error"] is None and rec["pull_error"] == "fetch 逾時" and rec["pulled_commits"] == 2
    assert not vs.marker_path(repo, "unpushed").exists() and vs.marker_path(repo, "behind").exists()
    assert [ln for ln in lines if "拉入 2 筆" in ln] and [ln for ln in lines if "fetch 逾時 20s" in ln], lines


def test_session_start_spawns_pull_sync_before_index_read(ss, monkeypatch):
    calls = []
    monkeypatch.setattr(vs, "spawn_vcs_sync", lambda sid, cwd, reason, retired_paths=None, config=None:
                        calls.append((sid, cwd, reason)) or 42)
    assert ss._spawn_pull_sync("sid", "c:/proj", CFG) == 42
    assert calls == [("sid", "c:/proj", "pull")]
    assert ss._spawn_pull_sync("sid", "c:/proj", CFG_NOPULL) == 0
    assert ss._spawn_pull_sync("sid", "c:/proj", {"vcs_sync": {"enabled": False}}) == 0
    assert len(calls) == 1
    src = (CLAUDE / "hooks" / "handlers" / "session_start.py").read_text(encoding="utf-8")
    assert src.index("_spawn_pull_sync(session_id, cwd, config)") < src.index("global_atoms = parse_memory_index(MEMORY_DIR)")


def test_post_git_pull_sh_syntax_and_status_keys():
    sh = CLAUDE / "hooks" / "post-git-pull.sh"
    r = subprocess.run(["bash", "-n", str(sh)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    src = sh.read_text(encoding="utf-8")
    assert "index_job" in src and "'indexing'" not in src


def test_pull_restore_exception_after_rebase_also_skips_push(tmp_path, repo_with_remote, monkeypatch):
    """restore 不是回傳非零而是整個拋例外（逾時／OSError）：ref 已換、記憶路徑未對齊，同樣要留 recover 且本輪不 push。"""
    repo, bare, head = _diverged_pure_memory(tmp_path, repo_with_remote)
    upstream = _git(bare, "rev-parse", "main").stdout.strip()

    def boom(cmd, run):
        raise subprocess.TimeoutExpired(cmd, 1)
    _inject(monkeypatch, lambda cmd, cwd: cmd[:2] == ["git", "restore"], boom)
    logs, log = _logs()
    res = vs.sync_targets_inline([_target(repo)], CFG, log=log)
    assert res[0]["pushed"] is False and res[0]["pull"]["status"] == "behind", (res, logs)
    assert res[0]["pull"]["recover_pending"] is True, res
    assert any("本輪不 push" in m for m in logs), logs
    assert vs.recover_path(repo).exists()
    assert _git(bare, "rev-parse", "main").stdout.strip() == upstream

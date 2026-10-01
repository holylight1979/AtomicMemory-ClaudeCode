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
      last_error，HEAD 不必變；git 查詢 rc≠0 → 仍報且不清）、last_error（skip）、`.req/` 無人消費。
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
SVN = vs._svn_exe()
HAS_SVN = shutil.which(SVN) is not None or Path(SVN).exists()


@pytest.fixture(autouse=True)
def sync_dir(tmp_path, monkeypatch):
    d = tmp_path / "_sync"
    monkeypatch.setattr(vs, "SYNC_DIR", d)
    monkeypatch.setattr(vs, "LEDGER_DIR", tmp_path / "_ledger")
    vs._held_locks.clear()
    yield d
    for lk in list(vs._held_locks.values()):
        lk.release()
    vs._held_locks.clear()


def _logs():
    out = []
    return out, out.append


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
    (path / "memory").mkdir()
    (path / "memory" / "seed.md").write_text("# seed\n", encoding="utf-8")
    (path / "code.py").write_text("print(1)\n", encoding="utf-8")
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", "seed")
    return path


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


def test_git_remote_ahead_push_rejected(tmp_path, repo_with_remote):
    repo, bare = repo_with_remote
    other = tmp_path / "other"
    _git(tmp_path, "clone", "-q", str(bare), str(other))
    _git(other, "config", "user.email", "o@o")
    _git(other, "config", "user.name", "o")
    (other / "memory" / "theirs.md").write_text("# theirs\n", encoding="utf-8")
    _git(other, "add", "-A")
    _git(other, "commit", "-q", "-m", "theirs")
    _git(other, "push", "-q", "origin", "main")
    (repo / "memory" / "new.md").write_text("# new\n", encoding="utf-8")
    res = vs.sync_targets_inline([_target(repo)], CFG, log=lambda m: None)
    assert res[0]["status"] == "unpushed" and "push 被拒" in res[0]["reason"], res
    assert _head_files(repo) == {"memory/new.md"}
    assert vs.read_unpushed(repo)


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

    def wrapped(t, cfg, env, log, branch):
        calls.append(1)
        r = orig(t, cfg, env, log, branch)
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

    def boom(t, cfg, env, log, branch):
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
    assert by_root[claude.resolve()].pathspecs == ["memory", "_AIDocs/_atoms"]
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
    _svn(wc, "add", "-q", "memory")
    _svn(wc, "commit", "-q", "-m", "seed", "memory")
    return wc, repo_dir


def _svn_ls(repo_dir: Path, sub="memory"):
    return set(_svn(repo_dir, "ls", f"{_svn_url(repo_dir)}/{sub}").stdout.decode().split())


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


def test_svn_retired_missing_deleted_other_missing_untouched(svn_wc):
    wc, repo_dir = svn_wc
    (wc / "memory" / "old.md").write_text("# old\n", encoding="utf-8")
    (wc / "memory" / "keep.md").write_text("# keep\n", encoding="utf-8")
    _svn(wc, "add", "-q", "memory/old.md", "memory/keep.md")
    _svn(wc, "commit", "-q", "-m", "two", "memory")
    (wc / "memory" / "old.md").unlink()
    (wc / "memory" / "keep.md").unlink()
    res = vs.sync_targets_inline([_target(wc, "svn")], CFG, log=lambda m: None,
                                 retired_paths=[str(wc / "memory" / "old.md")])
    assert res[0]["status"] == "ok" and res[0]["deleted"] == 1, res
    assert _svn_ls(repo_dir) == {"a.md", "keep.md"}
    entries = vs._svn_entries(_svn(wc, "status", "--xml", "memory").stdout)
    assert [i for p, i, _ in entries if p.endswith("keep.md")] == ["missing"]


def test_svn_out_of_date_update_then_retry(svn_wc, tmp_path):
    wc, repo_dir = svn_wc
    wc2 = tmp_path / "wc2"
    _svn(tmp_path, "checkout", "-q", _svn_url(repo_dir), str(wc2))
    a2 = wc2 / "memory" / "a.md"
    a2.write_text(a2.read_text(encoding="utf-8").replace("line 1\n", "line 1 (wc2)\n"), encoding="utf-8")
    _svn(wc2, "commit", "-q", "-m", "wc2 edits top", "memory")
    a1 = wc / "memory" / "a.md"
    a1.write_text(a1.read_text(encoding="utf-8").replace("line 10\n", "line 10 (wc1)\n"), encoding="utf-8")
    logs, log = _logs()
    res = vs.sync_targets_inline([_target(wc, "svn")], CFG, log=log)
    assert res[0]["status"] == "ok", (res, logs)
    assert any("update 後重試" in m for m in logs), logs
    head = _svn(repo_dir, "cat", f"{_svn_url(repo_dir)}/memory/a.md").stdout.decode("utf-8")
    assert "line 1 (wc2)" in head and "line 10 (wc1)" in head
    assert not vs.marker_path(wc, "unpushed").exists()


def test_svn_real_conflict_stops_without_retry(svn_wc, tmp_path):
    wc, repo_dir = svn_wc
    wc2 = tmp_path / "wc2"
    _svn(tmp_path, "checkout", "-q", _svn_url(repo_dir), str(wc2))
    a2 = wc2 / "memory" / "a.md"
    a2.write_text(a2.read_text(encoding="utf-8").replace("line 5\n", "line 5 (wc2)\n"), encoding="utf-8")
    _svn(wc2, "commit", "-q", "-m", "wc2 same line", "memory")
    a1 = wc / "memory" / "a.md"
    a1.write_text(a1.read_text(encoding="utf-8").replace("line 5\n", "line 5 (wc1)\n"), encoding="utf-8")
    rev_before = _svn(repo_dir, "info", "--show-item", "revision", _svn_url(repo_dir)).stdout.strip()
    logs, log = _logs()
    res = vs.sync_targets_inline([_target(wc, "svn")], CFG, log=log)
    assert res[0]["status"] == "unpushed" and "衝突" in res[0]["reason"], (res, logs)
    assert _svn(repo_dir, "info", "--show-item", "revision", _svn_url(repo_dir)).stdout.strip() == rev_before
    assert "衝突" in vs.read_unpushed(wc)
    entries = vs._svn_entries(_svn(wc, "status", "--xml", "memory").stdout)
    assert "conflicted" in {i for _, i, _ in entries}


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

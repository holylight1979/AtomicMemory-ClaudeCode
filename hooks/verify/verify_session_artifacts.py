"""verify_session_artifacts.py — 產出物帳本（handlers/aec_ledger.py 的 git／檔案擴充）與 HUD 執行端。

契約：
  - PostToolUse 的工具呼叫進帳：Write 寫的檔、Bash 寫入目標（mkdir、轉向…）、git 建立的工作樹／分支／臨時 repo／遠端分支。
  - 「還在不在、能不能刪」現場查（git 與檔案系統）；進了版控的檔掉出清單；使用中的分支、主分支、session 工作目錄不能刪。
  - 刪除當場執行：要確認的東西（沒合併的分支、有改動的工作樹、遠端分支、整個 repo）沒帶 force 不動手；帳上沒有的 key 不碰。
  - tools/session-artifacts.py 與 Node 端點（anti-evasion.js）照同一份帳本工作。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_session_artifacts.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
TREE = HOOKS_DIR.parent
sys.path.insert(0, str(HOOKS_DIR))

from handlers import aec_ledger as L  # noqa: E402
from handlers import _shared  # noqa: E402

_SID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "init.defaultBranch=main"]


def git(repo, *args, check=True):
    return subprocess.run([*_GIT, "-C", str(repo), *args], capture_output=True, text=True, check=check)


def make_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    git(path, "init", "-q")
    (path / "a.txt").write_text("a", encoding="utf-8")
    git(path, "add", "a.txt")
    git(path, "commit", "-q", "-m", "init")
    return path


def items_by_kind(sid=_SID):
    out = {}
    for it in L.list_alive(sid):
        out.setdefault(it["kind"], []).append(it)
    return out


@pytest.fixture
def wdir(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "WORKFLOW_DIR", tmp_path / "workflow")
    monkeypatch.setattr(L, "_tempdir", lambda: str(tmp_path / "systemp"))
    return tmp_path


def run_and_record(cmd: str, cwd: Path):
    subprocess.run(cmd, shell=True, cwd=str(cwd), capture_output=True, check=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"})
    return L.record_tool_artifacts(_SID, "Bash", {"command": cmd}, str(cwd))


# ─── 指令解析 ────────────────────────────────────────────────────────────────


def test_parse_git_commands_into_artifacts(tmp_path, monkeypatch):
    repo = make_repo(tmp_path / "r")
    other = tmp_path / "elsewhere"; other.mkdir()
    wt = tmp_path / "wt"
    kinds = lambda cmd, cwd=repo: [(e["kind"], e.get("name") or Path(e["path"]).name) for e in L.parse_git_artifacts(cmd, str(cwd))]
    assert kinds(f"git worktree add -b feat {wt} HEAD") == [("worktree", "wt"), ("branch", "feat")]
    assert kinds("git checkout -b b1") == [("branch", "b1")]
    assert kinds("git switch -c b2") == [("branch", "b2")]
    assert kinds("git branch b3 main") == [("branch", "b3")]
    for listing in ("git branch", "git branch -d b3", "git branch --list", "git branch -vv", "git checkout main"):
        assert kinds(listing) == [], listing
    assert kinds(f"git -C {repo} checkout -b b4", other) == [("branch", "b4")], "-C 指定 repo"
    assert kinds(f"cd {repo} && git switch -c b5", other) == [("branch", "b5")], "cd 換目錄"
    assert kinds("git push -u origin feat") == [("remote_branch", "feat")]
    assert kinds("git push origin feat:topic") == [("remote_branch", "topic")]
    for skip in ("git push origin main", "git push origin --delete feat", "git push", "git push --tags origin"):
        assert kinds(skip) == [], skip
    assert kinds(f"git clone https://x.example/y.git {tmp_path / 'yy'}") == [("repo", "yy")]
    assert kinds("git clone git@host:org/z.git", other) == [("repo", "z")]
    assert kinds("git checkout -b nope", other) == [], "不是 repo 的地方查不到根就不收"
    fresh = tmp_path / "fresh"; fresh.mkdir(); git(fresh, "init", "-q")
    assert kinds(f"git init {fresh}", tmp_path) == [("repo", "fresh")]
    monkeypatch.setattr(L, "_fresh_git_dir", lambda p, within_s=600: False)
    assert kinds(f"git init {repo}", tmp_path) == [], "對既有 repo 重新 init 不收（免得把真專案列成可刪）"


def test_fresh_git_dir_window(tmp_path):
    repo = make_repo(tmp_path / "r")
    assert L._fresh_git_dir(str(repo)) is True
    assert L._fresh_git_dir(str(repo), within_s=-1) is False
    assert L._fresh_git_dir(str(tmp_path)) is False, "沒有 .git"


@pytest.mark.skipif(os.name != "nt", reason="Git Bash 路徑只在 Windows 換")
def test_git_bash_drive_paths_resolved(tmp_path):
    repo = make_repo(tmp_path / "r")
    wt = tmp_path / "wt2"
    msys = "/" + str(wt)[0].lower() + str(wt)[2:].replace("\\", "/")
    got = L.parse_git_artifacts(f"git worktree add {msys}", str(repo))
    assert got and L._key(got[0]["path"]) == L._key(str(wt))


# ─── 工作樹與分支：列出、能不能刪、刪 ───────────────────────────────────────


def test_worktree_and_branch_lifecycle(wdir):
    repo = make_repo(wdir / "r")
    wt = wdir / "wt"
    run_and_record(f"git worktree add -b feat {wt}", repo)
    got = items_by_kind()
    assert got["worktree"][0]["label"].startswith("乾淨") and got["worktree"][0]["confirm"] is None
    br = got["branch"][0]
    assert br["title"] == "feat" and br["can_delete"] is False and "正在用" in br["label"]
    assert L.act(_SID, br["key"], "delete")["ok"] is False, "使用中的分支不能刪"

    (wt / "dirty.txt").write_text("x", encoding="utf-8")
    wt_item = items_by_kind()["worktree"][0]
    assert "未提交" in wt_item["label"] and wt_item["confirm"]
    res = L.act(_SID, wt_item["key"], "delete")
    assert res["ok"] is False and res["needs_confirm"] and wt.exists(), "要確認的沒帶 force 不動手"
    assert L.act(_SID, wt_item["key"], "delete", force=True)["ok"] is True
    assert not wt.exists() and str(wt).replace("\\", "/").lower() not in git(repo, "worktree", "list").stdout.lower()

    br = items_by_kind()["branch"][0]
    assert br["label"] == "已合併" and br["can_delete"] and br["confirm"] is None
    assert L.act(_SID, br["key"], "delete")["ok"] is True
    assert git(repo, "show-ref", "--verify", "refs/heads/feat", check=False).returncode != 0
    assert "branch" not in items_by_kind() and "worktree" not in items_by_kind()


def test_unmerged_branch_needs_confirm_and_main_is_protected(wdir):
    repo = make_repo(wdir / "r")
    run_and_record("git checkout -q -b topic && echo b> b.txt && git add b.txt && git commit -q -m b && git checkout -q main", repo)
    L.ledger_append(_SID, [{"kind": "branch", "path": str(repo), "repo": str(repo), "name": "main", "source": "bash"}])
    got = {it["title"]: it for it in items_by_kind()["branch"]}
    assert got["main"]["can_delete"] is False and "主分支" in got["main"]["label"]
    topic = got["topic"]
    assert "沒合併（多 1 個 commit）" == topic["label"] and topic["confirm"]
    assert L.act(_SID, topic["key"], "delete")["needs_confirm"]
    assert git(repo, "show-ref", "--verify", "refs/heads/topic", check=False).returncode == 0
    assert L.act(_SID, topic["key"], "delete", force=True)["ok"] is True
    assert git(repo, "show-ref", "--verify", "refs/heads/topic", check=False).returncode != 0
    rec = next(r for r in L.ledger_read(_SID) if r.get("name") == "topic")
    assert rec["decision"] == "deleted" and "已刪除" in rec["decision_message"]


def test_remote_branch_delete_needs_confirm(wdir):
    remote = wdir / "remote.git"
    subprocess.run([*_GIT, "init", "-q", "--bare", str(remote)], check=True)
    repo = make_repo(wdir / "r")
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-q", "origin", "main")
    run_and_record("git checkout -q -b feat && git push -q -u origin feat", repo)
    rb = items_by_kind()["remote_branch"][0]
    assert rb["title"] == "origin/feat" and rb["confirm"] and "遠端" in rb["confirm"]
    assert L.act(_SID, rb["key"], "delete")["needs_confirm"]
    assert L.act(_SID, rb["key"], "delete", force=True)["ok"] is True
    assert subprocess.run(["git", "-C", str(remote), "show-ref", "--verify", "refs/heads/feat"],
                          capture_output=True).returncode != 0


def test_temp_repo_and_cwd_guard(wdir):
    repo = make_repo(wdir / "r")
    run_and_record("git init -q scratch-repo", wdir)
    item = items_by_kind()["repo"][0]
    assert item["title"].endswith("scratch-repo") and item["confirm"]
    assert L.act(_SID, item["key"], "delete", force=True)["ok"] is True and not (wdir / "scratch-repo").exists()
    L.ledger_append(_SID, [{"kind": "repo", "path": str(repo), "cwd": str(repo), "source": "bash"}])
    guarded = items_by_kind()["repo"][0]
    assert guarded["can_delete"] is False and "工作目錄" in guarded["label"]


def test_post_tool_use_entry_records_bash_git_artifacts(wdir, monkeypatch):
    """經 PostToolUse 入口（handle_post_tool_use 的 Bash）：指令跑完後建的分支與資料夾都進帳。"""
    from handlers import post_tool_use as pt
    repo = make_repo(wdir / "r")
    git(repo, "branch", "via-entry")
    (repo / "out_dir").mkdir()
    state = {"turn_seq": 4, "session": {"cwd": str(repo)}}
    monkeypatch.setattr(pt, "_ensure_state", lambda *a, **k: state)
    monkeypatch.setattr(pt, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(pt, "append_guard_log", lambda *a, **k: None)
    monkeypatch.setattr(pt, "_check_output_quality", lambda *a, **k: None)
    with pytest.raises(SystemExit):
        pt.handle_post_tool_use({"session_id": _SID, "tool_name": "Bash",
                                 "tool_input": {"command": "git branch via-entry && mkdir out_dir"},
                                 "tool_response": {"stdout": "", "stderr": ""}, "cwd": str(repo)},
                                {"docdrift": {"enabled": False}})
    recs = L.ledger_read(_SID)
    assert {(r.get("kind"), r.get("name") or Path(r["path"]).name) for r in recs} >= {("branch", "via-entry"), ("dir", "out_dir")}
    assert all(r.get("turn_seq") == 4 for r in recs)


# ─── 檔案與資料夾 ─────────────────────────────────────────────────────────────


def test_files_dirs_labels_and_tracked_drop_out(wdir):
    repo = make_repo(wdir / "r")
    (repo / ".gitignore").write_text("ignored.log\n", encoding="utf-8")
    new = repo / "probe.py"; new.write_text("x", encoding="utf-8")
    L.record_tool_artifacts(_SID, "Write", {"file_path": str(new)}, str(repo))
    (repo / "ignored.log").write_text("x", encoding="utf-8")
    L.record_tool_artifacts(_SID, "Write", {"file_path": "ignored.log"}, str(repo))
    outside = wdir / "outside" / "probe_dir"
    outside.mkdir(parents=True)   # 指令本身由 Bash 跑；這裡只驗「跑完之後」的進帳
    L.record_tool_artifacts(_SID, "Bash", {"command": f"mkdir -p {outside.as_posix()}"}, str(wdir))
    mem = repo / "memory"; mem.mkdir(); (mem / "a.md").write_text("x", encoding="utf-8")
    L.record_tool_artifacts(_SID, "Write", {"file_path": str(mem / "a.md")}, str(repo))
    got = {it["title"]: it for it in L.list_alive(_SID)}
    assert "還沒進版控" in got["r/probe.py"]["label"]
    assert ".gitignore" in got["r/ignored.log"]["label"]
    assert got["outside/probe_dir"]["kind"] == "dir" and got["outside/probe_dir"]["label"] == "專案外"
    assert "memory/a.md" not in got, "受保護路徑不進帳"
    assert L.act(_SID, got["outside/probe_dir"]["key"], "delete")["ok"] is True and not outside.exists()
    git(repo, "add", "probe.py"); git(repo, "commit", "-q", "-m", "probe")
    assert "r/probe.py" not in {it["title"] for it in L.list_alive(_SID)}, "進了版控＝正式產出，掉出清單"


def test_edit_only_records_tempdir_and_unknown_key_refused(wdir):
    tmp = wdir / "systemp"; tmp.mkdir()
    (tmp / "s.txt").write_text("x", encoding="utf-8")
    proj = wdir / "proj"; proj.mkdir(); (proj / "real.py").write_text("x", encoding="utf-8")
    L.record_tool_artifacts(_SID, "Edit", {"file_path": str(tmp / "s.txt")}, str(proj))
    L.record_tool_artifacts(_SID, "Edit", {"file_path": str(proj / "real.py")}, str(proj))
    assert [Path(r["path"]).name for r in L.ledger_read(_SID)] == ["s.txt"]
    assert L.act(_SID, "C:/Windows/System32", "delete")["ok"] is False, "帳上沒有的 key 不碰"
    assert L.act(_SID, L.entry_key({"path": str(tmp / "s.txt")}), "keep")["ok"] is True
    assert L.list_alive(_SID)[0]["decision"] == "keep"


def test_deleted_then_recreated_is_a_new_entry(wdir):
    tmp = wdir / "systemp"; tmp.mkdir()
    f = tmp / "again.txt"; f.write_text("x", encoding="utf-8")
    L.record_tool_artifacts(_SID, "Write", {"file_path": str(f)}, str(wdir))
    key = L.list_alive(_SID)[0]["key"]
    assert L.act(_SID, key, "delete")["ok"] is True
    f.write_text("y", encoding="utf-8")
    L.record_tool_artifacts(_SID, "Write", {"file_path": str(f)}, str(wdir))
    item = L.list_alive(_SID)[0]
    assert item["decision"] is None, "刪過又出現的不帶舊的「已刪除」"


def test_prune_keeps_ledger_while_branch_alive(wdir):
    repo = make_repo(wdir / "r")
    git(repo, "branch", "keepme")
    d = wdir / "workflow" / "aec-tempfiles"; d.mkdir(parents=True)
    p = d / f"{_SID}.jsonl"
    p.write_text(json.dumps({"kind": "branch", "path": str(repo), "repo": str(repo), "name": "keepme"}) + "\n", encoding="utf-8")
    future = time.time() + 30 * 86400
    res = {"deleted": [], "failed": []}
    _shared._prune_aec_tempfiles(d, 7, future, False, res)
    assert p.exists(), "分支還在，帳本要留"
    git(repo, "branch", "-D", "keepme")
    _shared._prune_aec_tempfiles(d, 7, future, False, res)
    assert not p.exists(), "全都不在了才清"


# ─── 執行端：CLI 與 Node 端點 ──────────────────────────────────────────────────


def _data_root(wdir: Path, sid: str, recs) -> dict:
    data = wdir / "data"
    (data / "workflow" / "aec-tempfiles").mkdir(parents=True)
    (data / "workflow" / "aec-tempfiles" / f"{sid}.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in recs), encoding="utf-8")
    return {**os.environ, "WG_CLAUDE_DIR": str(data)}


def test_cli_list_and_act(wdir):
    f = wdir / "outside" / "leftover.txt"; f.parent.mkdir(); f.write_text("x", encoding="utf-8")
    env = _data_root(wdir, _SID, [{"path": str(f), "kind": "file", "source": "bash"}])
    cli = [sys.executable, "-X", "utf8", str(TREE / "tools" / "session-artifacts.py")]
    r = subprocess.run([*cli, "list", "--sid", _SID, "--json"], capture_output=True, text=True, encoding="utf-8", env=env)
    lines = r.stdout.strip().splitlines()
    items = json.loads(lines[0])["items"]
    assert [i["title"] for i in items] == ["outside/leftover.txt"] and lines[-1].startswith("SESSION_ARTIFACTS DONE")
    r = subprocess.run([*cli, "act", "--sid", _SID, "--key", items[0]["key"], "--action", "delete", "--json"],
                       capture_output=True, text=True, encoding="utf-8", env=env)
    assert json.loads(r.stdout.splitlines()[0])["ok"] is True and not f.exists()


_NODE = r"""
const ae = require(process.argv[1]);
const sid = process.argv[2];
function fakeRes(tag) { return { writeHead() {}, setHeader() {}, end(b) { console.log(tag + " " + b); } }; }
function fakeReq(body) {
  const h = {}; return { on(ev, cb) { h[ev] = cb; if (ev === "end") { h.data && h.data(body); cb(); } } };
}
ae.apiAecTempfiles({}, fakeRes("LIST"), sid);
setTimeout(() => {
  ae.apiAecDecisionPost(fakeReq(JSON.stringify({ sid, key: process.argv[3], action: "delete" })), fakeRes("ACT"));
}, 4000);
"""


@pytest.mark.skipif(not shutil.which("node"), reason="node not available")
def test_node_endpoints_call_python_tool(wdir):
    f = wdir / "outside" / "n.txt"; f.parent.mkdir(); f.write_text("x", encoding="utf-8")
    env = _data_root(wdir, _SID, [{"path": str(f), "kind": "file", "source": "bash"}])
    key = L.entry_key({"path": str(f)})
    r = subprocess.run(["node", "-e", _NODE, str(TREE / "tools" / "workflow-guardian-mcp" / "lib" / "anti-evasion.js"), _SID, key],
                       capture_output=True, text=True, encoding="utf-8", env=env, timeout=60)
    out = {line.split(" ", 1)[0]: json.loads(line.split(" ", 1)[1]) for line in r.stdout.splitlines() if line[:4] in ("LIST", "ACT ")}
    assert [i["title"] for i in out["LIST"]["items"]] == ["outside/n.txt"], r.stderr
    assert out["ACT"]["ok"] is True and not f.exists(), r.stderr

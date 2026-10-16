"""verify_session_artifacts.py — 產出物帳本（handlers/aec_ledger.py 的 git／檔案擴充）與 HUD 執行端。

契約：
  - PostToolUse 的工具呼叫進帳：Write 寫的檔、Bash 寫入目標（mkdir、轉向…）、git 建立的工作樹／分支／臨時 repo／遠端分支。
  - 「還在不在、能不能刪」現場查（git 與檔案系統）；進了版控的檔掉出清單；使用中的分支、主分支、session 工作目錄不能刪。
  - 刪除當場執行：要確認的東西（沒合併的分支、有改動的工作樹、遠端分支、整個 repo）沒帶 force 不動手；帳上沒有的 key 不碰。
  - tools/session-artifacts.py 與 Node 端點（anti-evasion.js）照同一份帳本工作。
  - 收尾自清（Stop 的 LEFTOVER_NEEDS_CLEANUP 閘）：宣告完成時列出本 session 建的、還在、能刪、沒說要留的東西，每個使用者回合擋一次。
  - (i) 可宣告分支留著（`branch:<名> — 理由`）；別的開著的 session 正在用的不列；開場快照比對出來的標來源不明、不進閘。
  - 全機殘留：list --all 掃全部帳本、依 session 分組、附 session 還開著沒有；整組清只刪不用再確認的。
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
import wg_release_rules as rr  # noqa: E402

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


# ─── 收尾自清（Stop 的 LEFTOVER_NEEDS_CLEANUP 閘）：事實端與閘 ─────────────────────


def _tail(title: str) -> str:
    return title.rsplit("/", 1)[-1]


def _state_file(wdir: Path, sid: str, data: dict, age_s: float = 0) -> Path:
    p = wdir / "workflow" / f"state-{sid}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data), encoding="utf-8")
    if age_s:
        t = time.time() - age_s
        os.utime(p, (t, t))
    return p


def test_status_facts_and_cleanup_candidates(wdir):
    """判定吃結構化事實（where／merged／used_by），不讀白話 label。候選＝工作樹、它用著的已合併分支、已合併分支、
    臨時 repo、專案外資料夾；沒合併的分支、暫存區檔、專案裡還沒進版控的新檔不列。"""
    repo = make_repo(wdir / "r")
    run_and_record(f"git worktree add -b feat {wdir / 'wt'}", repo)
    run_and_record("git branch topic && git branch idle", repo)
    git(repo, "checkout", "-q", "topic")
    (repo / "t.txt").write_text("t", encoding="utf-8")
    git(repo, "add", "t.txt"); git(repo, "commit", "-q", "-m", "t"); git(repo, "checkout", "-q", "main")
    run_and_record("git init -q scratch-repo", wdir)
    out = wdir / "outside" / "probe_dir"; out.mkdir(parents=True)
    L.record_tool_artifacts(_SID, "Bash", {"command": f"mkdir -p {out.as_posix()}"}, str(wdir))
    tmp = wdir / "systemp"; tmp.mkdir(); (tmp / "s.txt").write_text("x", encoding="utf-8")
    L.record_tool_artifacts(_SID, "Write", {"file_path": str(tmp / "s.txt")}, str(wdir))
    (repo / "probe.py").write_text("x", encoding="utf-8")
    L.record_tool_artifacts(_SID, "Write", {"file_path": str(repo / "probe.py")}, str(repo))
    by = {_tail(it["title"]): it for it in L.list_alive(_SID)}
    assert by["feat"]["merged"] is True and L._key(by["feat"]["used_by"]) == L._key(str(wdir / "wt"))
    assert by["topic"]["merged"] is False and by["idle"]["merged"] is True and by["idle"]["used_by"] == ""
    assert (by["probe_dir"]["where"], by["s.txt"]["where"], by["probe.py"]["where"]) == ("outside", "temp", "untracked")
    got = {(c["kind"], _tail(c["title"])) for c in rr.leftover_candidates(list(by.values()))}
    assert got == {("worktree", "wt"), ("branch", "feat"), ("branch", "idle"), ("repo", "scratch-repo"), ("dir", "probe_dir")}


def test_cleanup_facts_only_query_git_for_possible_candidates(wdir, monkeypatch):
    """帳越長收尾越慢（同伴 session 回報）：收尾自清閘只為可能成為候選的那幾筆查 git——暫存區檔、專案裡的檔
    （未進版控、已提交、gitignore）、遠端分支一律不跑 ls-files／check-ignore；選出來的候選和完整查法（list_alive）一樣。"""
    repo = make_repo(wdir / "r")
    (repo / ".gitignore").write_text("*.log\n", encoding="utf-8")
    tmp = wdir / "systemp"; tmp.mkdir()
    for i in range(6):
        for f in (repo / f"new{i}.py", repo / f"run{i}.log", tmp / f"s{i}.txt", repo / f"done{i}.py"):
            f.write_text("x", encoding="utf-8")
            L.record_tool_artifacts(_SID, "Write", {"file_path": str(f)}, str(repo))
    git(repo, "add", "."); git(repo, "commit", "-q", "-m", "done")   # done*.py、new*.py 進了版控＝正式產出
    (repo / "fresh.py").write_text("x", encoding="utf-8")
    L.record_tool_artifacts(_SID, "Write", {"file_path": str(repo / "fresh.py")}, str(repo))
    out = wdir / "outside" / "probe_dir"; out.mkdir(parents=True)
    L.ledger_append(_SID, [{"kind": "dir", "path": str(out), "source": "bash", "cwd": str(wdir)}])
    git(repo, "branch", "merged1")
    L.record_tool_artifacts(_SID, "Bash", {"command": "git branch merged1"}, str(repo))
    L.ledger_append(_SID, [{"kind": "remote_branch", "path": str(repo), "repo": str(repo), "remote": "origin",
                            "name": "merged1", "source": "bash"}])

    cmds: list = []
    real_run = subprocess.run

    def counting_run(cmd, *a, **k):
        cmds.append(" ".join(map(str, cmd)))
        return real_run(cmd, *a, **k)

    monkeypatch.setattr(L.subprocess, "run", counting_run)
    full = rr.leftover_candidates(L.list_alive(_SID))
    assert sum(("ls-files" in c or "check-ignore" in c) for c in cmds) >= 6, "前置：完整查法確實逐筆跑 git"
    cmds.clear()
    facts = L.cleanup_facts(_SID)
    assert not [c for c in cmds if "ls-files" in c or "check-ignore" in c], cmds
    assert len(cmds) <= 5, cmds
    assert {c["key"] for c in rr.leftover_candidates(facts)} == {c["key"] for c in full}
    assert {_tail(c["title"]) for c in full} == {"probe_dir", "merged1"}


def test_declared_keep_reasons_take_items_out_of_cleanup(wdir):
    """AI 在 (i) 寫理由＝說要留：路徑照寫、分支寫 `branch:<名> — 理由`；帳上沒有的分支拒收並說原因；使用者按保留也算。"""
    repo = make_repo(wdir / "r")
    wt = wdir / "wt"
    run_and_record(f"git worktree add -b feat {wt}", repo)
    run_and_record("git branch done1 && git branch done2", repo)
    assert len(rr.leftover_candidates(L.list_alive(_SID))) == 4, "前置：工作樹、feat、done1、done2 都是候選"
    rejected: list = []
    L.collect_at_completion(_SID, str(repo), f"{wt} — 下一階段還要用\nbranch:done1 — 等使用者看過再刪\nbranch:nope — 打錯名",
                            7, rejected=rejected)
    by = {_tail(it["title"]): it for it in L.list_alive(_SID)}
    assert by["wt"]["note"] == "下一階段還要用" and by["done1"]["note"] == "等使用者看過再刪" and by["done1"]["source"] == "aec-i"
    assert [r["path"] for r in rejected] == ["branch:nope"] and "帳上沒有" in rejected[0]["reason"]
    assert {c["title"] for c in rr.leftover_candidates(list(by.values()))} == {"done2"}, "feat 被留著的工作樹用著 → 不列"
    L.act(_SID, by["done2"]["key"], "keep")
    assert rr.leftover_candidates(L.list_alive(_SID)) == []


def test_worktree_in_use_by_another_open_session_is_left_alone(wdir):
    """總控台建的工作樹交給工作 session 用：別的開著的 session（30 分鐘內有動靜）改過或讀過裡面的檔、或工作目錄在裡面
    → 標正在用、刪除要再確認、不進自清閘；自己的工作目錄在裡面不算；那個 session 沒動靜了才回到候選。"""
    repo = make_repo(wdir / "r")
    wt = wdir / "wt"
    run_and_record(f"git worktree add -b feat {wt}", repo)
    other = _state_file(wdir, "other-sid", {"session": {"id": "other-sid", "cwd": str(repo)},
                                             "modified_files": [{"path": str(wt / "x.py")}]})
    _state_file(wdir, _SID, {"session": {"id": _SID, "cwd": str(wt)}})
    item = next(it for it in L.list_alive(_SID) if it["kind"] == "worktree")
    assert item["busy"] and "另一個開著的 session" in item["label"] and item["confirm"]
    assert rr.leftover_candidates(L.list_alive(_SID)) == []
    os.utime(other, (time.time() - 2 * 3600,) * 2)
    item = next(it for it in L.list_alive(_SID) if it["kind"] == "worktree")
    assert not item["busy"] and item["confirm"] is None
    assert {c["kind"] for c in rr.leftover_candidates(L.list_alive(_SID))} == {"worktree", "branch"}


def test_snapshot_catches_what_command_parsing_cannot(wdir):
    """python 腳本裡開的工作樹與分支，指令解析看不到：開場快照比對補進帳、標來源不明、不進自清閘；
    本 session 有建立指令的照舊；開場就有的不收；每次 Stop 都比但不重複進帳。"""
    repo = make_repo(wdir / "r")
    git(repo, "branch", "pre")
    snap = L.git_snapshot(str(repo))
    assert snap and L._key(snap["repo"]) == L._key(str(repo)) and "pre" in snap["branches"] and len(snap["worktrees"]) == 1
    git(repo, "worktree", "add", "-q", "-b", "byscript", str(wdir / "wt-script"))
    git(repo, "branch", "made")
    run_and_record("git branch mine", repo)
    L.collect_at_completion(_SID, str(repo), None, 3, snapshot=snap)
    L.collect_at_completion(_SID, str(repo), None, 4, snapshot=snap)
    assert len(L.ledger_path(_SID).read_text(encoding="utf-8").splitlines()) == 4
    by = {_tail(it["title"]): it for it in L.list_alive(_SID)}
    assert {k for k, v in by.items() if v["source"] == "snapshot"} == {"wt-script", "byscript", "made"}
    assert "來源不明" in by["made"]["origin"] and by["mine"]["origin"] == "" and "pre" not in by
    assert {c["title"] for c in rr.leftover_candidates(list(by.values()))} == {"mine"}


def test_list_all_groups_sessions_with_liveness(wdir):
    """全機殘留：掃全部帳本、只列還在的、依 session 分組；同一樣東西由有建立紀錄的 session 認領（快照比對的讓出）；
    session 狀態看 state 檔：30 分鐘內有動靜＝開著、更久＝多半已關、收過 SessionEnd 或檔不在＝已關。"""
    repo = make_repo(wdir / "r")
    sid_a, sid_b, sid_c = "aaaa-1", "bbbb-2", "cccc-3"
    git(repo, "branch", "a1")
    L.record_tool_artifacts(sid_a, "Bash", {"command": "git branch a1"}, str(repo))
    L.ledger_append(sid_b, [{"kind": "branch", "path": str(repo), "repo": str(repo), "name": "a1", "source": "snapshot"}])
    outside = wdir / "outside"; outside.mkdir()
    for sid, name in ((sid_b, "b.txt"), (sid_c, "c.txt"), (sid_c, "gone.txt")):
        (outside / name).write_text("x", encoding="utf-8")
        L.ledger_append(sid, [{"kind": "file", "path": str(outside / name), "source": "bash"}])
    (outside / "gone.txt").unlink()
    _state_file(wdir, sid_a, {"session": {"id": sid_a}})
    _state_file(wdir, sid_b, {"session": {"id": sid_b}}, age_s=2 * 3600)
    res = L.list_all()
    groups = {s["sid"]: s for s in res["sessions"]}
    assert [it["title"] for it in groups[sid_a]["items"]] == ["a1"]
    assert [it["title"] for it in groups[sid_b]["items"]] == ["outside/b.txt"]
    assert [it["title"] for it in groups[sid_c]["items"]] == ["outside/c.txt"]
    assert (groups[sid_a]["state"], groups[sid_b]["state"], groups[sid_c]["state"]) == ("open", "idle", "closed")
    assert res["total"] == 3 and all(s["label"] for s in res["sessions"])
    _state_file(wdir, sid_a, {"session": {"id": sid_a}, "ended_at": L._now_iso()})
    assert L.session_liveness(sid_a)["state"] == "closed"


def test_act_all_safe_only_deletes_items_needing_no_confirmation(wdir):
    """整組清：只刪不用再確認的（暫存檔、專案外資料夾、已合併分支…）；沒合併的分支、按過保留的、來源不明的不動。"""
    repo = make_repo(wdir / "r")
    tmp = wdir / "systemp"; tmp.mkdir()
    t, k = tmp / "s.txt", tmp / "keep.txt"
    for f in (t, k):
        f.write_text("x", encoding="utf-8")
        L.record_tool_artifacts(_SID, "Write", {"file_path": str(f)}, str(wdir))
    L.act(_SID, L.entry_key({"path": str(k)}), "keep")
    out = wdir / "outside" / "d"; out.mkdir(parents=True)
    L.ledger_append(_SID, [{"kind": "dir", "path": str(out), "source": "bash"}])
    run_and_record("git checkout -q -b topic && echo b> b.txt && git add b.txt && git commit -q -m b && git checkout -q main", repo)
    git(repo, "branch", "merged1")
    L.record_tool_artifacts(_SID, "Bash", {"command": "git branch merged1"}, str(repo))
    git(repo, "branch", "snapb")
    L.ledger_append(_SID, [{"kind": "branch", "path": str(repo), "repo": str(repo), "name": "snapb", "source": "snapshot"}])
    res = L.act_all_safe(_SID)
    assert res["ok"] is True and res["deleted"] == 3, res
    assert not t.exists() and not out.exists() and k.exists()
    has = lambda b: git(repo, "show-ref", "--verify", f"refs/heads/{b}", check=False).returncode == 0
    assert not has("merged1") and has("topic") and has("snapb")


def test_cli_list_all_and_all_safe(wdir):
    f = wdir / "outside" / "leftover.txt"; f.parent.mkdir(); f.write_text("x", encoding="utf-8")
    env = _data_root(wdir, _SID, [{"path": str(f), "kind": "file", "source": "bash"}])
    cli = [sys.executable, "-X", "utf8", str(TREE / "tools" / "session-artifacts.py")]
    r = subprocess.run([*cli, "list", "--all", "--json"], capture_output=True, text=True, encoding="utf-8", env=env)
    lines = r.stdout.strip().splitlines()
    data = json.loads(lines[0])
    assert [s["sid"] for s in data["sessions"]] == [_SID], r.stderr
    assert data["sessions"][0]["items"][0]["title"] == "outside/leftover.txt" and lines[-1].startswith("SESSION_ARTIFACTS DONE cmd=list")
    r = subprocess.run([*cli, "act", "--sid", _SID, "--all-safe", "--action", "delete", "--json"],
                       capture_output=True, text=True, encoding="utf-8", env=env)
    assert json.loads(r.stdout.splitlines()[0])["deleted"] == 1 and not f.exists(), r.stderr


_NODE_ALL = r"""
const ae = require(process.argv[1]);
const sid = process.argv[2];
function fakeRes(tag, next) { return { writeHead() {}, setHeader() {}, end(b) { console.log(tag + " " + b); if (next) next(); } }; }
function fakeReq(body) {
  const h = {}; return { on(ev, cb) { h[ev] = cb; if (ev === "end") { h.data && h.data(body); cb(); } } };
}
ae.apiAecTempfilesAll({}, fakeRes("ALL", () =>
  ae.apiAecDecisionPost(fakeReq(JSON.stringify({ sid, all_safe: true, action: "delete" })), fakeRes("BULK"))));
"""


@pytest.mark.skipif(not shutil.which("node"), reason="node not available")
def test_node_all_endpoint_and_bulk_decision(wdir):
    f = wdir / "outside" / "m.txt"; f.parent.mkdir(); f.write_text("x", encoding="utf-8")
    env = _data_root(wdir, _SID, [{"path": str(f), "kind": "file", "source": "bash"}])
    r = subprocess.run(["node", "-e", _NODE_ALL, str(TREE / "tools" / "workflow-guardian-mcp" / "lib" / "anti-evasion.js"), _SID],
                       capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)
    out = {line.split(" ", 1)[0]: json.loads(line.split(" ", 1)[1]) for line in r.stdout.splitlines() if line[:4] in ("ALL ", "BULK")}
    assert [s["sid"] for s in out["ALL"]["sessions"]] == [_SID], r.stderr
    assert out["BULK"]["deleted"] == 1 and not f.exists(), r.stderr


@pytest.fixture
def stop_driven(wdir, monkeypatch):
    """驅動 handle_stop（比照 verify_knowledge_harvest_gate 的 driven：只留閘的控制流）；帳本走 wdir。"""
    from handlers import stop as st
    for name, val in (("_find_session_transcript", lambda *a, **k: None), ("token_warn_payload", lambda *a, **k: ""),
                      ("detect_evasion", lambda *a, **k: None), ("write_state", lambda *a, **k: None),
                      ("append_guard_log", lambda *a, **k: None), ("_attribute_usefulness", lambda *a, **k: None),
                      ("_detect_uncommitted_files", lambda mf: []), ("_git_unpushed_roots", lambda mf: []),
                      ("_should_deep_postmortem", lambda *a, **k: False),
                      ("_maybe_spawn_user_extract_worker", lambda *a, **k: None), ("_hud_alive", lambda *a, **k: (True, {}))):
        monkeypatch.setattr(st, name, val)

    def drive(capsys, state, last_text="全部完成了"):
        monkeypatch.setattr(st, "get_last_assistant_text", lambda *a, **k: last_text)
        monkeypatch.setattr(st, "_ensure_state", lambda *a, **k: state)
        with pytest.raises(SystemExit):
            st.handle_stop({"session_id": _SID, "cwd": ""}, {})
        return capsys.readouterr().out

    return drive


def test_stop_cleanup_gate_blocks_once_per_user_turn(stop_driven, wdir, capsys):
    """收尾自清閘：宣告完成、帳上有該清的 → 擋一次，列每一項與刪除指令（走 session-artifacts.py，結果記回帳本）、
    教怎麼寫留的理由；不吃 stop_blocked_count、同一個使用者回合不再擋；沒宣告完成不擋；清乾淨就不擋。"""
    repo = make_repo(wdir / "r")
    run_and_record(f"git worktree add -b feat {wdir / 'wt'}", repo)
    state = {"phase": "working", "modified_files": [], "failing_tests": [], "recent_user_prompts": [],
             "stop_blocked_count": 0, "turn_seq": 5}
    assert "[Guardian:Cleanup]" not in stop_driven(capsys, state, last_text="我先查一下工作樹的狀態，查完再回報給你看看。")
    out = stop_driven(capsys, state)
    assert "[Guardian:Cleanup]" in out and "LEFTOVER_NEEDS_CLEANUP" in out
    assert "session-artifacts.py" in out and f"--sid {_SID}" in out and "branch:<名>" in out
    assert state["stop_blocked_count"] == 0 and state["cleanup_gate_turn"][_SID] == 5
    assert "[Guardian:Cleanup]" not in stop_driven(capsys, state), "同一個使用者回合只擋一次"
    state["turn_seq"] = 6
    for it in L.list_alive(_SID):
        assert L.act(_SID, it["key"], "delete")["ok"] is True, it
    assert "[Guardian:Cleanup]" not in stop_driven(capsys, state)


def test_server_routes_all_machine_endpoint():
    """server.js 把 GET /api/aec/tempfiles-all 交給 apiAecTempfilesAll（Node 端點的行為案例在 test_node_all_endpoint_and_bulk_decision）。"""
    src = (TREE / "tools" / "workflow-guardian-mcp" / "server.js").read_text(encoding="utf-8")
    i = src.index('pathname === "/api/aec/tempfiles-all"')
    assert "antiEvasion.apiAecTempfilesAll(req, res)" in src[i:i + 200]


def test_post_tool_use_reports_unmatched_branch_declaration(wdir, monkeypatch, capsys):
    """收尾檢核 (i) 寫了帳上沒有的分支 → PostToolUse 回告「沒收下」與原因；不是受保護路徑就不附受保護的說明。"""
    from handlers import post_tool_use as pt
    repo = make_repo(wdir / "r")
    git(repo, "branch", "real")
    L.record_tool_artifacts(_SID, "Bash", {"command": "git branch real"}, str(repo))
    state = {"turn_seq": 4, "session": {"cwd": str(repo)}}
    for name, val in (("_ensure_state", lambda *a, **k: state), ("write_state", lambda *a, **k: None),
                      ("append_guard_log", lambda *a, **k: None), ("_check_output_quality", lambda *a, **k: None),
                      ("_write_aec_report_file", lambda *a, **k: None), ("_maybe_spawn_hud", lambda *a, **k: None)):
        monkeypatch.setattr(pt, name, val)
    tool_input = {k: "無" for k in ("a", "b", "c", "d", "e", "f", "g", "h", "j_evidence_path", "k_followups")}
    tool_input["i"] = "branch:real — 等使用者看過\nbranch:nope — 打錯名"
    with pytest.raises(SystemExit):
        pt.handle_post_tool_use({"session_id": _SID, "tool_name": "mcp__workflow-guardian__anti_evasion_report",
                                 "tool_input": tool_input, "tool_response": {"content": [{"type": "text", "text": "ok"}]},
                                 "cwd": str(repo)}, {"docdrift": {"enabled": False}, "aec": {}})
    out = capsys.readouterr().out
    assert "沒收下" in out and "branch:nope" in out and "帳上沒有" in out and "受保護路徑" not in out
    assert next(r for r in L.ledger_read(_SID) if r.get("name") == "real")["note"] == "等使用者看過"


@pytest.mark.skipif(os.name != "nt", reason="8.3 短檔名只在 Windows")
def test_short_and_long_names_are_the_same_place(wdir, monkeypatch):
    """系統暫存區常是 8.3 短檔名（C:\\Users\\ABCDEF~1\\…），AI 用長檔名寫進去的檔仍要認成暫存區（不然會被當專案外、
    進收尾自清閘）；同一個地方兩種寫法是同一筆帳。"""
    import ctypes
    longdir = wdir / "systemp-with-a-long-name"
    longdir.mkdir()
    buf = ctypes.create_unicode_buffer(1024)
    n = ctypes.windll.kernel32.GetShortPathNameW(str(longdir), buf, 1024)
    if not n or buf.value.lower() == str(longdir).lower():
        pytest.skip("這個磁碟沒有 8.3 短檔名")
    monkeypatch.setattr(L, "_tempdir", lambda: buf.value)
    f = longdir / "s.txt"; f.write_text("x", encoding="utf-8")
    assert L.is_under_tempdir(str(f)) and L._key(str(Path(buf.value) / "s.txt")) == L._key(str(f))
    L.record_tool_artifacts(_SID, "Write", {"file_path": str(f)}, str(wdir))
    assert [it["where"] for it in L.list_alive(_SID)] == ["temp"]


def test_session_start_snapshot_taken_once(wdir):
    """SessionStart 記下 cwd 所在 repo 的工作樹與本地分支；compact／resume 沿用開場那份；不是 repo 就不記。"""
    from handlers import session_start as ss
    repo = make_repo(wdir / "r")
    state: dict = {}
    ss._take_git_snapshot(state, str(repo))
    first = state["git_snapshot"]
    assert first["branches"] == ["main"] and len(first["worktrees"]) == 1
    git(repo, "branch", "later")
    ss._take_git_snapshot(state, str(repo))
    assert state["git_snapshot"] is first
    empty: dict = {}
    (wdir / "plain").mkdir()
    ss._take_git_snapshot(empty, str(wdir / "plain"))
    assert "git_snapshot" not in empty

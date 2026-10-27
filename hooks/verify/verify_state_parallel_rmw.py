"""verify_state_parallel_rmw.py：平行工具呼叫的 hook 同時讀改寫同一份 session state，誰的紀錄都不能掉（規則 STATE_RMW_LOCKED）。

背景：同一則回覆平行送出幾個工具呼叫時，每支 hook 行程都「讀 state → 加上自己那筆 → 寫回」。以前鎖只包寫檔那一下，
平行的 hook 各自讀到同一份舊 state，最後寫的蓋掉其他人加的那筆：平行讀了 4 個部位檔，部位紀錄只剩 1 筆，定位閘照擋。
案例 1～4 用真的子行程並行（不在同一個行程裡模擬）：
1. 真 hook 入口 hooks/workflow-guardian.py：先讀一個部位檔讓導讀卡注入，再同時起 4 支 PostToolUse（Read 4 個不同的部位檔）
   → 部位紀錄 part_files_read、reads_after 4 筆都在。
2. 同時起 4 支 PostToolUse（Write 4 個不同的檔）→ modified_files 4 筆都在，event_seq 配的 last_seq 不重號。
3. 兩個子行程直接用 wg_core 對同一個 sid 各做 30 次「讀 → 加一筆 → 寫回」：一種走 hook 模式（begin_state_rmw，
   讀到寫整段握鎖），一種不進 hook 模式（寫回時在鎖裡發現檔被別人改過 → 照欄位分型併進去）→ 60 筆都在。
4. 拿不到鎖不准無鎖寫：父行程握著鎖，子行程等到期限 → 不改 state 檔、留一份待併帳＋stderr [state:lock-timeout]；
   鎖放掉之後下一支 hook 讀 state 時把待併帳併回、刪帳。
5～8 在同一個行程裡用另一個 handle 握同一個 byte 當「別支 hook 握著鎖」，排出退路的交錯（子規則 STATE_PENDING_MERGED）：
5. 三方合併分型：一次性鍵消費後不復活、清單聯集、modified_files 逐筆併 count 相加、計數歸零不變負、分版本整組、判不出留磁碟那份。
6. 讀不到不等於遺失：fallback 重建的 state 不蓋掉已存在的檔、fallback 的整份帳遇到已存在的 state 丟掉。
7. 拿鎖時併了別人的帳不偷換基準、同一支多次留帳是增量、併過刪不掉不重套、讀到檔不在的兩份帳逐欄併、fallback 旗標被消費後
   不讓第二份帳蓋掉真的 state、別的 session 的帳不會被撈到、sibling 等鎖期間收尾就不認領。
8. 自己的帳沒落盤前不直接寫、併過名單不截斷且重建 state 也帶著、fallback 收到轉址 stub 跟到目標、stub 上的帳不碰目標、
   刪不掉的舊帳不擋新帳。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_state_parallel_rmw.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1]
TREE = HOOKS_DIR.parent
_WIN = sys.platform == "win32"
PART_MAP = """# 部位表（並行案例用）

| 路徑前綴 | 部位 | 導讀卡 | 狀態 |
|---|---|---|---|
| `orders/` | 訂單結帳 | `訂單導讀` | 有 |
"""
CONFIG_OFF = {
    "vector_search": {"enabled": False, "auto_start_service": False, "auto_index_on_change": False},
    "vcs_sync": {"enabled": False},
    "codex_companion": {"enabled": False},
    "provenance": {"enabled": False},
    "response_capture": {"enabled": False},
}


class Sandbox:
    """tmp 資料根、家目錄、系統暫存、Logs 與一個有部位表的專案；hook 子行程全導到這裡。tree＝受測樹（量測探針拿來比新舊程式）。"""

    def __init__(self, base: Path, tree: Path = TREE):
        self.dir, self.tree = base, tree
        self.entry = tree / "hooks" / "workflow-guardian.py"
        self.data, self.home, self.systmp, self.logs = base / "data", base / "home", base / "systmp", base / "logs"
        for d in (self.data / "workflow", self.home / ".claude" / "memory" / "_meta", self.systmp, self.logs):
            d.mkdir(parents=True, exist_ok=True)
        cfg = json.loads((tree / "workflow" / "config.json").read_text(encoding="utf-8"))
        for sec, vals in CONFIG_OFF.items():
            if isinstance(cfg.setdefault(sec, {}), dict):
                cfg[sec].update(vals)
        (self.data / "workflow" / "config.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        for dst in (self.home / ".claude" / "memory" / "_meta", self.data / "memory" / "_meta"):
            shutil.copytree(tree / "memory" / "_meta", dst, dirs_exist_ok=True)
        self.proj = base / "proj"
        (self.proj / ".claude" / "memory" / "shared").mkdir(parents=True)
        (self.proj / "_AIDocs").mkdir()
        (self.proj / ".claude" / "overview-map.md").write_text(PART_MAP, encoding="utf-8")
        (self.proj / ".claude" / "memory" / "shared" / "訂單導讀.md").write_text(
            "# 訂單導讀\n\n## 知識\n\n- [臨] **已知病灶**：折扣與稅的先後\n", encoding="utf-8")
        (self.proj / "orders").mkdir()
        for name in ("a", "b", "c", "d", "e"):
            (self.proj / "orders" / f"{name}.py").write_text(f"{name} = 1\n", encoding="utf-8")
        self.sid = f"par-{uuid.uuid4().hex[:12]}"
        slug = str(self.proj).replace(":", "-").replace("\\", "-").replace("/", "-").replace(".", "-").lower()
        self.transcript = self.data / "projects" / slug / f"{self.sid}.jsonl"
        self.transcript.parent.mkdir(parents=True)
        self.transcript.touch()
        self._n = 0

    def env(self) -> dict:
        e = dict(os.environ)
        e.pop("CLAUDE_COMPANION_JUDGE", None)
        e.update({
            "WG_CLAUDE_DIR": str(self.data), "HOME": str(self.home), "USERPROFILE": str(self.home),
            "TEMP": str(self.systmp), "TMP": str(self.systmp), "TMPDIR": str(self.systmp),
            "WG_TEST_LOGS_DIR": str(self.logs), "WG_TEMP_RULES": "off", "WG_V6": "1",
            "PYTHONPATH": os.pathsep.join([str(self.tree / "lib"), str(self.tree / "tools"), str(self.tree)]),
            "CLAUDE_CODE_ENTRYPOINT": "cli", "PYTHONIOENCODING": "utf-8",
        })
        return e

    def state(self) -> dict:
        return json.loads((self.data / "workflow" / f"state-{self.sid}.json").read_text(encoding="utf-8"))

    def payload(self, event: dict) -> bytes:
        return json.dumps({"session_id": self.sid, "cwd": str(self.proj), "transcript_path": str(self.transcript), **event},
                          ensure_ascii=False).encode("utf-8")

    def _tid(self) -> str:
        self._n += 1
        return f"toolu_par_{self._n:03d}"

    def read_event(self, path: Path) -> dict:
        return {"hook_event_name": "PostToolUse", "tool_name": "Read", "tool_use_id": self._tid(),
                "tool_input": {"file_path": str(path)},
                "tool_response": {"type": "text", "file": {"filePath": str(path), "content": "…"}}}

    def write_event(self, path: Path) -> dict:
        content = f"# {path.stem}\nx = 2\n"
        path.write_text(content, encoding="utf-8", newline="\n")
        return {"hook_event_name": "PostToolUse", "tool_name": "Write", "tool_use_id": self._tid(),
                "tool_input": {"file_path": str(path), "content": content},
                "tool_response": {"type": "create", "filePath": str(path), "content": content}}

    def run(self, event: dict) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-X", "utf8", str(self.entry)], input=self.payload(event), capture_output=True,
                              env=self.env(), cwd=str(self.proj), timeout=120)

    def run_parallel(self, events: list) -> list:
        """同時起每支 hook（像 Claude Code 對同一批工具呼叫那樣：一起起、起好就送 stdin），讀改寫自然撞在一起。
        每支一條執行緒收輸出（不讓握著鎖的那支卡在寫 stdout）；回 [(結束碼, stdout, stderr, 起行程到結束的牆鐘毫秒)]。"""
        import threading
        t0 = time.monotonic()
        procs = [subprocess.Popen([sys.executable, "-X", "utf8", str(self.entry)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, env=self.env(), cwd=str(self.proj)) for _ in events]
        out: list = [None] * len(procs)

        def wait(i: int, p: subprocess.Popen, data: bytes) -> None:
            o, e = p.communicate(data, timeout=120)
            out[i] = (p.returncode, o.decode("utf-8", "replace"), e.decode("utf-8", "replace"), int((time.monotonic() - t0) * 1000))
        threads = [threading.Thread(target=wait, args=(i, p, self.payload(ev))) for i, (p, ev) in enumerate(zip(procs, events))]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return out


@pytest.fixture
def sb():
    """沙箱不放 pytest 的 tmp_path：那裡的路徑含 /pytest-of-，改檔紀錄照設計當暫存檔略過（_is_ephemeral_path）。"""
    base = Path(tempfile.mkdtemp(prefix="state-rmw-"))
    try:
        yield Sandbox(base)
    finally:
        shutil.rmtree(base, ignore_errors=True)


def _start(sb: Sandbox) -> None:
    r = sb.run({"hook_event_name": "SessionStart", "source": "startup"})
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    with open(sb.transcript, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"type": "user", "message": {"role": "user", "content": "訂單結帳加折扣碼"}, "sessionId": sb.sid,
                            "uuid": uuid.uuid4().hex, "entrypoint": "cli", "isSidechain": False}, ensure_ascii=False) + "\n")
    r = sb.run({"hook_event_name": "UserPromptSubmit", "prompt": "訂單結帳加折扣碼"})
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")


def _names(paths) -> set:
    return {Path(str(p)).name.lower() for p in paths or []}


def _part_rec(state: dict) -> dict:
    return next(v for k, v in (state.get("overview_hub") or {}).items() if k.endswith("|訂單結帳"))


# ─── 1. 4 支平行 Read 的 PostToolUse：部位讀檔紀錄 4 筆都在 ─────────────────────────────

def test_four_parallel_reads_all_recorded(sb):
    _start(sb)
    r = sb.run(sb.read_event(sb.proj / "orders" / "a.py"))            # 第一個部位檔：注入導讀卡、建部位紀錄（注入那次也算讀，INJECT_TRIGGER_READ_COUNTED）
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    assert _names(_part_rec(sb.state())["part_files_read"]) == {"a.py"}
    files = [sb.proj / "orders" / f"{n}.py" for n in ("b", "c", "d", "e")]
    results = sb.run_parallel([sb.read_event(f) for f in files])
    assert all(rc == 0 for rc, _, _, _ in results), results
    assert not any("[workflow-guardian] Error" in e for _, _, e, _ in results), results
    rec = _part_rec(sb.state())
    assert _names(rec["part_files_read"]) == {"a.py", "b.py", "c.py", "d.py", "e.py"}, rec["part_files_read"]
    assert {"b.py", "c.py", "d.py", "e.py"} <= _names(rec["reads_after"]), rec["reads_after"]
    assert not list((sb.data / "workflow").glob(f"state-{sb.sid}.*.pending")), "沒撞到期限不該留待併帳"


# ─── 2. 4 支平行 Write 的 PostToolUse：modified_files 4 筆都在 ───────────────────────────

def test_four_parallel_writes_all_recorded(sb):
    _start(sb)
    files = [sb.proj / "orders" / f"w{i}.py" for i in range(4)]
    results = sb.run_parallel([sb.write_event(f) for f in files])
    assert all(rc == 0 for rc, _, _, _ in results), results
    st = sb.state()
    mods = [m for m in st.get("modified_files") or [] if isinstance(m, dict)]
    assert _names(m["path"] for m in mods) >= {"w0.py", "w1.py", "w2.py", "w3.py"}, mods
    seqs = [m["last_seq"] for m in mods if Path(m["path"]).name.startswith("w")]
    assert len(seqs) == len(set(seqs)) == 4, seqs                      # 序號在同一把鎖裡配：不重號


# ─── 3. 兩個子行程直接對同一個 sid 讀改寫 ─────────────────────────────────────────────

_CHILD = r'''
import json, os, sys, time
sys.path.insert(0, sys.argv[-1])
mode, sid, tag, n, sync_dir = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5]
import wg_core
open(os.path.join(sync_dir, tag + "_ready"), "w").close()
while not os.path.exists(os.path.join(sync_dir, "go")):
    time.sleep(0.002)
for i in range(n):
    hook = mode == "hook" and hasattr(wg_core, "begin_state_rmw")
    if hook:
        wg_core.begin_state_rmw()                     # dispatcher 進 handler 前做的事：之後讀 state 就握鎖到 end
    st = wg_core.read_state(sid)
    st.setdefault("accessed_files", []).append(f"{tag}-{i}")
    st[f"count_{tag}"] = st.get(f"count_{tag}", 0) + 1
    time.sleep(0.003)                                 # 讀到寫之間的處理時間（hook 實測 50～80ms，這裡縮短加快）
    wg_core.write_state(sid, st)
    if hook:
        wg_core.end_state_rmw()
print("done")
'''


def _two_writers(tmp_path: Path, mode: str, n: int = 30) -> dict:
    data, sync = tmp_path / "data", tmp_path / "sync"
    (data / "workflow").mkdir(parents=True)
    sync.mkdir()
    sid = "sid-two-rmw"
    (data / "workflow" / f"state-{sid}.json").write_text(
        json.dumps({"session": {"id": sid}, "accessed_files": [], "turn_seq": 1}), encoding="utf-8")
    env = {**os.environ, "WG_CLAUDE_DIR": str(data), "PYTHONIOENCODING": "utf-8"}
    procs = [subprocess.Popen([sys.executable, "-X", "utf8", "-c", _CHILD, mode, sid, tag, str(n), str(sync), str(HOOKS_DIR)],
                              env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
             for tag in ("A", "B")]
    deadline = time.time() + 30
    while not all((sync / f"{t}_ready").exists() for t in ("A", "B")):
        assert time.time() < deadline, "children never got ready"
        time.sleep(0.005)
    (sync / "go").write_text("", encoding="utf-8")
    for p in procs:
        out, err = p.communicate(timeout=120)
        assert p.returncode == 0 and "done" in out, (out, err)
        assert "[state:lock-timeout]" not in err, err
    return json.loads((data / "workflow" / f"state-{sid}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("mode", ["hook", "plain"])
def test_two_processes_read_modify_write_same_sid_keep_every_append(tmp_path, mode):
    st = _two_writers(tmp_path, mode)
    want = {f"{t}-{i}" for t in ("A", "B") for i in range(30)}
    assert set(st["accessed_files"]) == want, sorted(want - set(st["accessed_files"]))[:10]
    assert st["count_A"] == 30 and st["count_B"] == 30


# ─── 4. 拿不到鎖：不無鎖寫、留待併帳，下一支拿到鎖的 hook 併回（子規則 STATE_PENDING_MERGED）──────────────

@pytest.mark.skipif(not _WIN, reason="msvcrt 鎖只在 Windows")
def test_lock_timeout_leaves_pending_then_next_hook_merges_it(sb):
    import msvcrt
    _start(sb)
    assert sb.run(sb.read_event(sb.proj / "orders" / "a.py")).returncode == 0      # 注入導讀卡
    state_file = sb.data / "workflow" / f"state-{sb.sid}.json"
    before = state_file.read_text(encoding="utf-8")
    fh = open(state_file.with_suffix(".lock"), "ab")
    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)                                  # 別人握著鎖不放
    try:
        t0 = time.time()
        r = sb.run(sb.read_event(sb.proj / "orders" / "b.py"))
        waited = time.time() - t0
    finally:
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        fh.close()
    err = r.stderr.decode("utf-8", "replace")
    assert r.returncode == 0, err
    assert "[state:lock-timeout]" in err and "[state:pending-written]" in err, err
    assert waited < 5.0, waited                                                     # 等到期限（上限的一半）就走，不等到被砍
    assert state_file.read_text(encoding="utf-8") == before                         # 沒有無鎖寫
    pend = list(state_file.parent.glob(f"{state_file.stem}.*.pending"))
    assert len(pend) == 1, pend
    r = sb.run(sb.read_event(sb.proj / "orders" / "c.py"))                         # 下一支拿到鎖：先併回再記自己那筆
    err = r.stderr.decode("utf-8", "replace")
    assert r.returncode == 0 and "[state:pending-merged]" in err, err
    assert _names(_part_rec(sb.state())["part_files_read"]) == {"a.py", "b.py", "c.py"}           # a.py 是觸發注入那次
    assert not list(state_file.parent.glob(f"{state_file.stem}.*.pending"))
    log = (sb.logs / "guard-state_lock.jsonl").read_text(encoding="utf-8")
    assert '"kind": "pending_written"' in log and '"kind": "pending_merged"' in log


# ─── 5. 三方合併照欄位分型（只在沒全程握鎖、待併帳時用到）──────────────────────────────────

sys.path.insert(0, str(HOOKS_DIR))
import wg_core  # noqa: E402


def _merge(base, ours, theirs):
    return wg_core._merge_state(base, ours, theirs)


def test_merge_only_one_side_changed_takes_that_side_and_consumed_one_shot_stays_gone():
    base = {"a": 1, "_hint": "x", "pending_reinjection": True, "keep": [1]}
    ours = {"a": 2, "_hint": "x", "pending_reinjection": True, "keep": [1]}         # 自己只改 a
    theirs = {"a": 1, "keep": [1]}                                                  # 別人消費掉一次性的鍵
    out, conflicts = _merge(base, ours, theirs)
    assert out == {"a": 2, "keep": [1]} and conflicts == []                         # 消費過的不被舊快照救活


def test_merge_lists_union_and_removal_by_ours_respected():
    base = {"reads": ["a", "old"]}
    ours = {"reads": ["a", "b"]}            # 自己加 b、刪 old（截斷）
    theirs = {"reads": ["a", "old", "c"]}   # 別人加 c
    out, _ = _merge(base, ours, theirs)
    assert out["reads"] == ["a", "c", "b"]


def test_merge_modified_files_keyed_by_path_counts_add():
    rec = lambda p, n, seq: {"path": p, "session_id": "s", "count": n, "last_seq": seq, "tool": "Edit"}
    base = {"modified_files": [rec("C:/p/x.py", 1, 1)], "event_seq": 1}
    ours = {"modified_files": [rec("C:/p/x.py", 2, 2), rec("C:/p/y.py", 1, 3)], "event_seq": 3}
    theirs = {"modified_files": [rec("C:/p/../p/X.py", 2, 2), rec("C:/p/z.py", 1, 3)], "event_seq": 3}
    out, _ = _merge(base, ours, theirs)
    by = {Path(m["path"]).name.lower(): m for m in out["modified_files"]}
    assert set(by) == {"x.py", "y.py", "z.py"}
    assert by["x.py"]["count"] == 3                                                  # 讀到 1，兩邊各 +1
    assert out["event_seq"] == 3                                                     # 序號取大，之後配號不倒退


def test_merge_counters_add_and_markers_take_max_and_times_take_newest():
    base = {"edit_counts": {"x": 1}, "exec_turn_seq": {"s": 3}, "at": "2026-10-23T02:00:00+08:00"}
    ours = {"edit_counts": {"x": 2}, "exec_turn_seq": {"s": 4}, "at": "2026-10-23T02:00:05+08:00"}
    theirs = {"edit_counts": {"x": 3}, "exec_turn_seq": {"s": 5}, "at": "2026-10-23T02:00:03+08:00"}
    out, conflicts = _merge(base, ours, theirs)
    assert out["edit_counts"]["x"] == 4 and out["exec_turn_seq"]["s"] == 5
    assert out["at"] == "2026-10-23T02:00:05+08:00" and conflicts == []


def test_merge_version_group_newer_wins_whole_and_same_version_merges_fields():
    old = {"injected_turn": 1, "reads_after": ["a"], "edits": 0, "located": False}
    base = {"overview_hub": {"k": old}}
    reinjected = {"injected_turn": 2, "reads_after": [], "edits": 0, "located": False}
    out, _ = _merge(base, {"overview_hub": {"k": {**old, "reads_after": ["a", "b"]}}}, {"overview_hub": {"k": reinjected}})
    assert out["overview_hub"]["k"] == reinjected                                    # 重新注入＝新版本，整組勝
    out, _ = _merge(base, {"overview_hub": {"k": {**old, "reads_after": ["a", "b"], "edits": 1}}},
                    {"overview_hub": {"k": {**old, "reads_after": ["a", "c"], "edits": 1}}})
    assert out["overview_hub"]["k"]["reads_after"] == ["a", "c", "b"] and out["overview_hub"]["k"]["edits"] == 2


def test_merge_undecidable_scalar_keeps_disk_and_reports_conflict():
    out, conflicts = _merge({"intent": "a"}, {"intent": "b"}, {"intent": "c"})
    assert out["intent"] == "c" and conflicts == ["intent"]
    out, conflicts = _merge({"commit_snapshot": {"h": 1}}, {"commit_snapshot": {"h": 2}}, {"commit_snapshot": {"h": 3}})
    assert out["commit_snapshot"] == {"h": 3} and conflicts == ["commit_snapshot"]   # 整組綁定的不逐欄拼


# ─── 6. 讀不到不等於遺失：fallback 重建的 state 不蓋掉鎖裡已存在的檔 ─────────────────────────────

def test_fallback_state_never_overwrites_existing_state(tmp_path, monkeypatch):
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", tmp_path)
    monkeypatch.setattr(wg_core, "_STATE_READ_TEXT", {})
    monkeypatch.setattr(wg_core, "_STATE_READ_SIG", {})
    sid = "sid-fallback"
    assert wg_core.read_state_status(sid) == (None, "missing")             # 這支看到檔不在
    real = {"session": {"id": sid}, "turn_seq": 7, "modified_files": [{"path": "C:/p/a.py", "session_id": sid, "count": 1}]}
    wg_core.state_path(sid).write_text(json.dumps(real), encoding="utf-8")  # 別支在這之間建好真的 state
    fb = {**wg_core.new_state(sid, "C:/p", "fallback"), "_fallback_state_rebuilt": True}
    wg_core.write_state(sid, fb)
    disk = json.loads(wg_core.state_path(sid).read_text(encoding="utf-8"))
    assert disk["turn_seq"] == 7 and disk["modified_files"] == real["modified_files"]
    assert fb["turn_seq"] == 7 and "_fallback_state_rebuilt" not in fb      # 呼叫端拿到的是磁碟那份


def test_fallback_pending_dropped_when_state_exists_but_real_whole_pending_applies(tmp_path, monkeypatch):
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", tmp_path)
    monkeypatch.setattr(wg_core, "_STATE_READ_TEXT", {})
    monkeypatch.setattr(wg_core, "_STATE_READ_SIG", {})
    monkeypatch.setattr(wg_core, "append_guard_log", lambda *a, **k: None)
    sid = "sid-pend"
    path = wg_core.state_path(sid)
    path.write_text(json.dumps({"session": {"id": sid}, "turn_seq": 3}), encoding="utf-8")
    wg_core._write_pending(path, None, {"session": {"id": sid}, "turn_seq": 1, "_fallback_state_rebuilt": True}, "lock-timeout")
    wg_core._merge_pending(path)
    assert json.loads(path.read_text(encoding="utf-8"))["turn_seq"] == 3   # fallback 那份丟掉
    assert not list(tmp_path.glob("*.pending"))
    wg_core._write_pending(path, None, {"session": {"id": sid}, "turn_seq": 9, "phase": "merged"}, "lock-timeout")
    wg_core._merge_pending(path)
    assert json.loads(path.read_text(encoding="utf-8"))["phase"] == "merged"   # 沒讀過就整份寫的（轉址）照整份換


# ─── 7. 待併帳退路的交錯（拿另一個 handle 握鎖＝別支 hook 握著；同一行程內就重現得出來）────────────────

@pytest.fixture
def wf(tmp_path, monkeypatch):
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", tmp_path)
    monkeypatch.setattr(wg_core, "_STATE_READ_TEXT", {})
    monkeypatch.setattr(wg_core, "_STATE_READ_SIG", {})
    monkeypatch.setattr(wg_core, "append_guard_log", lambda *a, **k: None)
    yield tmp_path
    wg_core.end_state_rmw()


class _Held:
    """別支 hook 握著這個 session 的鎖（另開一個 handle 鎖同一個 byte）。"""

    def __init__(self, sid):
        import msvcrt
        self.fh = open(wg_core.state_path(sid).with_suffix(".lock"), "ab")
        msvcrt.locking(self.fh.fileno(), msvcrt.LK_NBLCK, 1)

    def release(self):
        import msvcrt
        msvcrt.locking(self.fh.fileno(), msvcrt.LK_UNLCK, 1)
        self.fh.close()


def _seed(sid, st):
    wg_core.state_path(sid).write_text(json.dumps({"session": {"id": sid}, **st}), encoding="utf-8")


def _hook(fn, wait=0.05):
    """一支 hook：開 hook 模式（等鎖 wait 秒）、跑 fn、結束放鎖。"""
    wg_core.begin_state_rmw(time.time() + wait)
    try:
        return fn()
    finally:
        wg_core.end_state_rmw()


def _disk(sid):
    return json.loads(wg_core.state_path(sid).read_text(encoding="utf-8"))


win_only = pytest.mark.skipif(not _WIN, reason="msvcrt 鎖只在 Windows")


@win_only
def test_late_lock_merges_others_pending_instead_of_overwriting(wf):
    sid = "s-late"
    _seed(sid, {"accessed_files": []})
    held = _Held(sid)

    def b():
        st = wg_core.read_state(sid)
        st["accessed_files"].append("b")
        wg_core.write_state(sid, st)                    # 拿不到鎖：留待併帳
    _hook(b)

    def a():
        st = wg_core.read_state(sid)                    # 讀時拿不到鎖：沒上鎖的那份
        held.release()                                  # 寫回前鎖放掉了：寫回時拿得到、先併 b 的帳
        st["accessed_files"].append("a")
        wg_core.write_state(sid, st)
    _hook(a)
    assert sorted(_disk(sid)["accessed_files"]) == ["a", "b"]


@win_only
def test_several_pending_writes_in_one_hook_are_incremental(wf):
    sid = "s-multi"
    _seed(sid, {"edit_counts": {"x": 0}})
    held = _Held(sid)

    def h():
        st = wg_core.read_state(sid)
        st["edit_counts"]["x"] = 1
        wg_core.write_state(sid, st)
        st["other"] = 1
        wg_core.write_state(sid, st)
        st["_hint"] = "h"                                # 一次性的鍵：加了又消費掉
        wg_core.write_state(sid, st)
        del st["_hint"]
        wg_core.write_state(sid, st)
    _hook(h)
    held.release()
    _hook(lambda: wg_core.read_state(sid))
    d = _disk(sid)
    assert d["edit_counts"]["x"] == 1 and d["other"] == 1 and "_hint" not in d


@win_only
def test_pending_merged_but_not_deleted_is_not_applied_twice(wf):
    sid = "s-twice"
    _seed(sid, {"edit_counts": {"x": 0}})
    held = _Held(sid)

    def h():
        st = wg_core.read_state(sid)
        st["edit_counts"]["x"] = 1
        wg_core.write_state(sid, st)
    _hook(h)
    held.release()
    pend = list(wf.glob(f"state-{sid}.*.pending"))
    keep = open(pend[0], "r", encoding="utf-8")         # 別的讀者開著：併完刪不掉
    try:
        _hook(lambda: wg_core.read_state(sid))
    finally:
        keep.close()
    _hook(lambda: wg_core.read_state(sid))
    assert _disk(sid)["edit_counts"]["x"] == 1
    assert not list(wf.glob(f"state-{sid}.*.pending"))


@win_only
def test_pending_from_missing_state_merges_by_field_not_last_wins(wf):
    sid = "s-missing"
    held = _Held(sid)
    for name in ("a.py", "b.py"):
        def h(name=name):
            st = wg_core.read_state(sid) or {"session": {"id": sid}, "turn_seq": 0, "judge": True}
            st.setdefault("modified_files", []).append({"path": f"C:/p/{name}", "session_id": sid, "count": 1})
            wg_core.write_state(sid, st)
        _hook(h)
    held.release()
    _seed(sid, {"turn_seq": 0})                          # 鎖放掉前握鎖那支建好了 state
    _hook(lambda: wg_core.read_state(sid))
    assert {Path(m["path"]).name for m in _disk(sid)["modified_files"]} == {"a.py", "b.py"}


@win_only
def test_consumed_fallback_flag_does_not_let_second_pending_overwrite_real_state(wf):
    sid = "s-ups"
    held = _Held(sid)

    def ups():
        st = wg_core._ensure_state(sid, {"cwd": "C:/p"}, {})          # 讀到檔不在：建 fallback（拿不到鎖：留帳）
        st.pop("_fallback_state_rebuilt", None)                        # UPS 消費旗標、注入一行
        st["turn_seq"] = st.get("turn_seq", 0) + 1
        wg_core.write_state(sid, st)
    _hook(ups)
    real = {"turn_seq": 7, "modified_files": [{"path": "C:/p/real.py", "session_id": sid, "count": 1}]}
    _seed(sid, real)                                     # 握鎖那支（開場）建好了真的 state
    held.release()
    _hook(lambda: wg_core.read_state(sid))
    d = _disk(sid)
    assert d["modified_files"] == real["modified_files"] and d["turn_seq"] >= 7
    assert "_fallback_state_rebuilt" not in d


def test_merge_reset_counter_does_not_go_negative_and_legacy_count_defaults_to_one():
    out, _ = _merge({"stop_blocked_turn": 1, "stop_blocked_count": 2},
                    {"stop_blocked_turn": 2, "stop_blocked_count": 0}, {"stop_blocked_turn": 2, "stop_blocked_count": 0})
    assert out["stop_blocked_count"] == 0
    rec = {"path": "C:/p/x.py", "session_id": "s"}
    out, _ = _merge({"modified_files": [rec]}, {"modified_files": [{**rec, "count": 2, "at": "2026-10-23T01:00:01"}]},
                    {"modified_files": [{**rec, "count": 2, "at": "2026-10-23T01:00:02"}]})
    assert out["modified_files"][0]["count"] == 3                    # 沒有 count 的舊紀錄算 1 次


def test_pending_glob_does_not_take_another_sessions_pending(wf):
    wg_core._write_pending(wg_core.state_path("a.b"), "{}", {"session": {"id": "a.b"}, "x": 1}, "lock-timeout")
    _seed("a", {"x": 0})
    wg_core._merge_pending(wg_core.state_path("a"))
    assert _disk("a")["x"] == 0 and len(list(wf.glob("state-a.b.*.pending"))) == 1


def test_sibling_that_ended_while_waiting_is_not_claimed(wf, monkeypatch):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    sib = {"session": {"id": "sib", "cwd": "C:/p", "started_at": now}, "phase": "working"}
    wg_core.state_path("sib").write_text(json.dumps(sib), encoding="utf-8")
    real_read = wg_core.read_state_status
    monkeypatch.setattr(wg_core, "read_state_status",
                        lambda s: ({**sib, "phase": "done"}, "ok") if s == "sib" else real_read(s))   # 等鎖期間它收尾了
    assert wg_core._find_active_sibling_state("C:/p", "me", window_seconds=3600) is None
    monkeypatch.setattr(wg_core, "read_state_status", lambda s: (None, "error") if s == "sib" else real_read(s))
    got = wg_core._find_active_sibling_state("C:/p", "me", window_seconds=3600)
    assert got == sib and wg_core._STATE_READ_TEXT[str(wg_core.state_path("sib"))] == json.dumps(sib)   # 重讀不到：掃描那份當基準


# ─── 8. 留帳後轉成直接寫、併過名單、重建 state、轉址 stub、隊首卡住 ──────────────────────

def _lockless_edit(sid, key, value):
    """別人握鎖時的一支 hook：讀（沒上鎖）→ 改一個鍵 → 寫回（留帳）。"""
    def h():
        st = wg_core.read_state(sid)
        st[key] = value
        wg_core.write_state(sid, st)
    _hook(h)


@win_only
def test_direct_write_after_own_pending_merges_that_pending_first(wf):
    sid = "s-own"
    _seed(sid, {"edit_counts": {"x": 0}})

    def h():
        st = wg_core.read_state(sid)                     # 握著鎖
        keep = open(wg_core.state_path(sid), "r", encoding="utf-8")   # 別的讀者開著 state：換不掉 → 留帳
        try:
            st["edit_counts"]["x"] = 1
            st["_hint"] = "h"
            wg_core.write_state(sid, st)
        finally:
            keep.close()
        st["edit_counts"]["x"] = 2                       # 同一支再寫：這次換得掉
        del st["_hint"]
        wg_core.write_state(sid, st)
    _hook(h, wait=1.0)
    _hook(lambda: wg_core.read_state(sid))
    d = _disk(sid)
    assert d["edit_counts"]["x"] == 2 and "_hint" not in d
    assert not list(wf.glob(f"state-{sid}.*.pending"))


@win_only
def test_applied_receipt_kept_while_pending_file_still_exists(wf):
    sid = "s-cap"
    _seed(sid, {"x": 0, "edit_counts": {"x": 0}})
    held = _Held(sid)
    _lockless_edit(sid, "edit_counts", {"x": 1})
    held.release()
    first = list(wf.glob(f"state-{sid}.*.pending"))[0]
    keep = open(first, "r", encoding="utf-8")            # 併過但刪不掉
    try:
        _hook(lambda: wg_core.read_state(sid))
        for i in range(60):                             # 之後又併了 60 份別的帳
            held = _Held(sid)
            _lockless_edit(sid, f"k{i}", i)
            held.release()
            _hook(lambda: wg_core.read_state(sid))
    finally:
        keep.close()
    _hook(lambda: wg_core.read_state(sid))
    d = _disk(sid)
    assert d["edit_counts"]["x"] == 1 and d["k59"] == 59
    assert not list(wf.glob(f"state-{sid}.*.pending"))


@win_only
def test_rebuilt_state_without_receipt_key_does_not_reapply_pending(wf):
    sid = "s-rebuild"
    _seed(sid, {"edit_counts": {"x": 0}, "turn_seq": 1})
    held = _Held(sid)
    _lockless_edit(sid, "edit_counts", {"x": 1})
    held.release()
    p = list(wf.glob(f"state-{sid}.*.pending"))[0]
    keep = open(p, "r", encoding="utf-8")
    try:
        def rebuild():                                   # 開場重建：新 state 只搬幾個鍵，沒有併過名單
            old = wg_core.read_state(sid)
            wg_core.write_state(sid, {"session": {"id": sid}, "edit_counts": old["edit_counts"], "turn_seq": 1})
        _hook(rebuild)
    finally:
        keep.close()
    _hook(lambda: wg_core.read_state(sid))
    assert _disk(sid)["edit_counts"]["x"] == 1


def test_fallback_adopting_a_redirect_stub_follows_it_to_the_target(wf, monkeypatch):
    sid, tgt = "s-stub", "s-target"
    _seed(tgt, {"phase": "working", "turn_seq": 4})

    def sibling_appears(*a, **k):                        # 掃描期間別支寫好了轉址 stub
        _seed(sid, {"phase": "merged", "merged_into": tgt})
        return None
    monkeypatch.setattr(wg_core, "_find_active_sibling_state", sibling_appears)
    monkeypatch.setattr(wg_core, "_rebuild_min_atom_index", lambda cwd: {})
    monkeypatch.setattr(wg_core, "_atom_debug_log", lambda *a, **k: None)
    st = wg_core._ensure_state(sid, {"cwd": "C:/p"}, {})
    assert st["session"]["id"] == tgt and st["turn_seq"] == 4


@win_only
def test_pending_on_redirect_stub_stays_on_stub_and_never_touches_target(wf, capsys):
    sid, tgt = "s-stub2", "s-target2"
    target_rec = [{"path": "C:/p/t.py", "session_id": tgt, "count": 3}]
    held = _Held(sid)

    def h():
        st = wg_core.read_state(sid) or {"session": {"id": sid}}
        st["modified_files"] = [{"path": "C:/p/a.py", "session_id": sid, "count": 1}]
        wg_core.write_state(sid, st)                     # 從空的建起的帳
    _hook(h)
    wg_core._write_pending(wg_core.state_path(sid), None,  # 沒讀過就整份寫的帳（開場轉址換不掉檔時留的）
                           {"session": {"id": sid}, "phase": "merged", "merged_into": tgt, "modified_files": []}, "replace-failed")
    held.release()
    _seed(tgt, {"phase": "working", "modified_files": target_rec, "edit_counts": {"x": 2}})
    _seed(sid, {"phase": "merged", "merged_into": tgt})
    capsys.readouterr()
    _hook(lambda: wg_core.read_state(sid))               # 拿到 stub 的鎖：帳併進 stub 本身
    _hook(lambda: wg_core.read_state(tgt))
    t = _disk(tgt)
    assert t["session"]["id"] == tgt and t["modified_files"] == target_rec and t["edit_counts"] == {"x": 2}   # 目標沒被動
    assert "轉址 stub" in capsys.readouterr().err                                     # 看不到的那幾筆有訊號
    assert not list(wf.glob("state-*.pending"))


_REAL_REPLACE = wg_core._replace_text


def _fail_state_replace(monkeypatch, sid, times):
    """接下來 times 次換 state 檔都失敗（像別的讀者開著）；帳檔照寫。回剩幾次的計數器。"""
    left = {"n": times}

    def fake(path, text):
        if path == wg_core.state_path(sid) and left["n"] > 0:
            left["n"] -= 1
            return "replace-failed：模擬讀者開著", None
        return _REAL_REPLACE(path, text)
    monkeypatch.setattr(wg_core, "_replace_text", fake)
    return left


def test_own_pending_not_yet_on_disk_forces_another_pending_not_a_direct_write(wf, monkeypatch):
    sid = "s-own2"
    _seed(sid, {"edit_counts": {"x": 0}, "_hint": None})
    real_merge = wg_core._merge_pending

    def h():
        st = wg_core.read_state(sid)                     # 握著鎖
        left = _fail_state_replace(monkeypatch, sid, 1)
        st["edit_counts"]["x"] = 1
        st["_hint"] = "h"
        wg_core.write_state(sid, st)                     # 換不掉 → 留帳 P
        assert left["n"] == 0
        monkeypatch.setattr(wg_core, "_merge_pending", lambda path: set())   # 這次併不進去（之後直接寫卻換得掉）
        st["edit_counts"]["x"] = 2
        st["_hint"] = None
        wg_core.write_state(sid, st)
        monkeypatch.setattr(wg_core, "_merge_pending", real_merge)
    _hook(h)
    _hook(lambda: wg_core.read_state(sid))
    d = _disk(sid)
    assert d["edit_counts"]["x"] == 2 and d["_hint"] is None
    assert not list(wf.glob(f"state-{sid}.*.pending"))


def test_more_own_pendings_than_one_merge_takes_still_add_up(wf, monkeypatch):
    sid = "s-own21"
    monkeypatch.setattr(wg_core, "_PENDING_MAX_PER_MERGE", 2)
    _seed(sid, {"edit_counts": {"x": 0}})

    def h():
        st = wg_core.read_state(sid)                     # 握著鎖
        _fail_state_replace(monkeypatch, sid, 100)       # 前 3 次寫回（連同順手併帳）都換不掉：留 3 份帳
        for i in range(3):
            st["edit_counts"]["x"] = i + 1
            wg_core.write_state(sid, st)
        _fail_state_replace(monkeypatch, sid, 0)
        st["edit_counts"]["x"] = 4                     # 這次換得掉，但一次只併得了 2 份
        wg_core.write_state(sid, st)
    _hook(h)
    for _ in range(3):
        _hook(lambda: wg_core.read_state(sid))
    assert _disk(sid)["edit_counts"]["x"] == 4
    assert not list(wf.glob(f"state-{sid}.*.pending"))


@win_only
def test_undeletable_applied_pendings_do_not_block_newer_ones(wf):
    sid = "s-hol"
    _seed(sid, {})
    keeps = []
    try:
        held = _Held(sid)
        for i in range(wg_core._PENDING_MAX_PER_MERGE):
            _lockless_edit(sid, f"k{i}", i)
        held.release()
        keeps = [open(p, "r", encoding="utf-8") for p in wf.glob(f"state-{sid}.*.pending")]   # 前 20 份併得了、刪不掉
        _hook(lambda: wg_core.read_state(sid))
        assert len(list(wf.glob(f"state-{sid}.*.pending"))) == wg_core._PENDING_MAX_PER_MERGE
        held = _Held(sid)
        _lockless_edit(sid, "late", 1)
        held.release()
        _hook(lambda: wg_core.read_state(sid))
        assert _disk(sid).get("late") == 1
    finally:
        for k in keeps:
            k.close()

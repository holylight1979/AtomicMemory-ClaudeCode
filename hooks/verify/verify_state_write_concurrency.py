"""verify_state_write_concurrency.py：同 sid 多行程同時 write_state，state 檔永遠是合法 JSON、且等於其中一方的完整內容。

怎麼跑：set WG_CLAUDE_DIR=<worktree> && python -X utf8 -m pytest -q hooks/verify/verify_state_write_concurrency.py
背景（2026-10-12 根層 session ccffc32e 實證）：以前所有 hook 行程共用 state-<sid>.tmp、鎖拿不到就照寫，
  兩支並行 hook 一長一短同時 open(tmp,'w')，短的從 offset 0 蓋掉長的前段、尾巴殘留 → replace 後「Extra data」，
  該 session 餘生每支 hook 都 [state:unreadable] 跳過。
正例：兩個子行程對同一 sid 各寫 50 次長短交錯 → 每次寫完 json.loads 都成功且內容是兩方之一的完整 dict。
反例（證明本案抓得到舊 bug）：子行程內把 tmp 檔名改回共用（os.getpid→0）且鎖永遠拿不到，用檔案同步點排出
  「兩邊都 open 後、長的先寫完、短的再寫」的交錯 → 必重現 Extra data；同交錯只保留 tmp 每行程唯一 → 仍合法。
鎖逾時：父行程長持 .lock → 子行程重試後仍寫出合法 JSON，stderr 有 [state:lock-timeout]。
replace 失敗：父行程開著 state 檔（Windows 無 FILE_SHARE_DELETE 換不掉）→ 不留 tmp、原 state 仍合法、stderr 有 [state:replace-failed]。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1]
_SID = "sid-concurrent"
_WIN = sys.platform == "win32"

# 子行程腳本：argv = mode sid n tag sync_dir；mode ∈ {burst, race-shared, race-unique}
_CHILD = r'''
import json, os, sys, time
sys.path.insert(0, sys.argv[-1])
mode, sid, n, tag, sync_dir = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5]
import wg_core

def signal(name):
    open(os.path.join(sync_dir, name), "w").close()

def wait(name, timeout=10):
    t = time.time()
    while not os.path.exists(os.path.join(sync_dir, name)):
        if time.time() - t > timeout:
            raise SystemExit(f"wait timeout: {name}")
        time.sleep(0.002)

def state_of(i):
    big = (i % 2 == 0) if tag == "A" else (i % 2 == 1)
    return {"session": {"id": sid}, "writer": tag, "i": i, "pad": "x" * (40000 if big else 8)}

def read_valid():
    """讀回 state：暫時讀不到（另一方正 replace）就重試；JSON 壞就回錯誤字串。"""
    p = wg_core.state_path(sid)
    for _ in range(50):
        try:
            with open(p, "r", encoding="utf-8") as f:
                d = json.load(f)
        except (PermissionError, FileNotFoundError):
            time.sleep(0.002)
            continue
        except json.JSONDecodeError as e:
            return f"BAD_JSON:{e}"
        keys = set(d) - {"last_updated"}
        if keys != {"session", "writer", "i", "pad"} or d["pad"] != "x" * len(d["pad"]):
            return f"NOT_ONE_WRITER:{sorted(keys)}"
        return "OK"
    return "UNREADABLE"

if mode == "burst":
    wait("go")
    bad = []
    for i in range(n):
        wg_core.write_state(sid, state_of(i))
        r = read_valid()
        if r != "OK":
            bad.append(f"{tag}#{i}:{r}")
    print(json.dumps({"tag": tag, "bad": bad}))
    raise SystemExit(0)

# race-*：鎖永遠拿不到；race-shared 再把 tmp 檔名退回「所有行程共用」（舊 bug 的兩個條件）
wg_core._acquire_state_lock = lambda lock_path: None
if mode == "race-shared":
    os.getpid = lambda: 0
real_open = open

def hooked_open(p, *a, **k):
    fh = real_open(p, *a, **k)
    if str(p).endswith(".tmp"):
        signal(f"{tag}_opened")
        wait("A_opened"); wait("B_opened")          # 兩邊都 open（都已 truncate）後才開始寫
        if tag == "B":
            wait("A_done")                           # 長的先整個寫完＋replace，短的再寫
    return fh

wg_core.open = hooked_open
state = {"session": {"id": sid}, "writer": tag, "i": 0, "pad": "x" * (40000 if tag == "A" else 8)}   # A 長、B 短
wg_core.write_state(sid, state)
signal(f"{tag}_done")
print(json.dumps({"tag": tag}))
'''


def _spawn(mode: str, tag: str, n: int, sync_dir: Path, claude_dir: Path) -> subprocess.Popen:
    env = {**os.environ, "WG_CLAUDE_DIR": str(claude_dir), "PYTHONIOENCODING": "utf-8"}
    return subprocess.Popen([sys.executable, "-X", "utf8", "-c", _CHILD, mode, _SID, str(n), tag, str(sync_dir), str(HOOKS_DIR)],
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")


def _state_file(claude_dir: Path) -> Path:
    return claude_dir / "workflow" / f"state-{_SID}.json"


def _signal(sync_dir: Path, name: str) -> None:
    (sync_dir / name).write_text("", encoding="utf-8", newline="\n")


def _run_race(mode: str, tmp_path: Path):
    sync = tmp_path / "sync"
    sync.mkdir()
    a = _spawn(mode, "A", 1, sync, tmp_path)
    b = _spawn(mode, "B", 1, sync, tmp_path)
    oa, ea = a.communicate(timeout=30)
    ob, eb = b.communicate(timeout=30)
    assert a.returncode == 0 and b.returncode == 0, (oa, ea, ob, eb)
    return _state_file(tmp_path).read_text(encoding="utf-8"), ea + eb


# ─── 正例：兩行程各 50 次長短交錯 ─────────────────────────────────────────

def test_two_processes_interleaved_writes_always_valid_json(tmp_path):
    sync = tmp_path / "sync"
    sync.mkdir()
    a = _spawn("burst", "A", 50, sync, tmp_path)
    b = _spawn("burst", "B", 50, sync, tmp_path)
    time.sleep(0.3)                     # 兩邊都 import 完再放行，確保真的並行
    _signal(sync, "go")
    p = _state_file(tmp_path)
    samples, bad_samples = 0, []
    deadline = time.time() + 30
    while (a.poll() is None or b.poll() is None) and time.time() < deadline:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            samples += 1
            if set(d) - {"last_updated"} != {"session", "writer", "i", "pad"}:
                bad_samples.append(sorted(d))
        except (OSError, json.JSONDecodeError) as e:
            if isinstance(e, json.JSONDecodeError):
                bad_samples.append(str(e))
        time.sleep(0.003)
    oa, ea = a.communicate(timeout=30)
    ob, eb = b.communicate(timeout=30)
    assert a.returncode == 0 and b.returncode == 0, (oa, ea, ob, eb)
    ra, rb = json.loads(oa.strip().splitlines()[-1]), json.loads(ob.strip().splitlines()[-1])
    assert ra["bad"] == [] and rb["bad"] == [], (ra, rb)
    assert bad_samples == [], bad_samples
    final = json.loads(p.read_text(encoding="utf-8"))
    assert final["writer"] in ("A", "B") and final["i"] == 49
    assert not list((tmp_path / "workflow").glob("*.tmp"))       # 不留 tmp
    assert "[state:unreadable]" not in ea + eb


# ─── 反例：舊條件（共用 tmp＋無鎖）在可控交錯下必重現 Extra data ──────────

def test_counterexample_shared_tmp_without_lock_reproduces_extra_data(tmp_path):
    text, err = _run_race("race-shared", tmp_path)
    with pytest.raises(json.JSONDecodeError, match="Extra data"):
        json.loads(text)
    assert "[state:replace-failed]" in err       # A 換不掉被 B 握著的 tmp（舊碼靜默吞掉；現在浮訊號）


def test_same_interleaving_with_unique_tmp_stays_valid(tmp_path):
    """同一套交錯、鎖一樣拿不到，只靠 tmp 每行程唯一 → 檔仍是某一方（B，後寫）的完整 JSON。"""
    text, _ = _run_race("race-unique", tmp_path)
    d = json.loads(text)
    assert d["writer"] == "B" and d["pad"] == "x" * 8
    assert not list((tmp_path / "workflow").glob("*.tmp"))


# ─── 鎖逾時與 replace 失敗 ─────────────────────────────────────────────────

@pytest.mark.skipif(not _WIN, reason="msvcrt 鎖只在 Windows")
def test_lock_held_by_other_process_times_out_then_writes_valid_json(tmp_path):
    import msvcrt
    wf = tmp_path / "workflow"
    wf.mkdir()
    lock = wf / f"state-{_SID}.lock"
    fh = open(lock, "ab")
    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
    try:
        sync = tmp_path / "sync"
        sync.mkdir()
        _signal(sync, "go")
        a = _spawn("burst", "A", 1, sync, tmp_path)
        oa, ea = a.communicate(timeout=30)
    finally:
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        fh.close()
    assert a.returncode == 0, (oa, ea)
    assert "[state:lock-timeout]" in ea
    assert json.loads(oa.strip().splitlines()[-1])["bad"] == []
    d = json.loads(_state_file(tmp_path).read_text(encoding="utf-8"))
    assert d["writer"] == "A" and d["i"] == 0
    assert not list(wf.glob("*.tmp"))


@pytest.mark.skipif(not _WIN, reason="Windows 才會因開著的 handle 讓 replace 失敗")
def test_replace_blocked_by_open_handle_leaves_no_tmp_and_keeps_old_state(tmp_path):
    wf = tmp_path / "workflow"
    wf.mkdir()
    p = _state_file(tmp_path)
    before = json.dumps({"session": {"id": _SID}, "writer": "old", "i": -1, "pad": "x"})
    p.write_text(before, encoding="utf-8", newline="\n")
    holder = open(p, "r", encoding="utf-8")          # 開著不放：MoveFileEx 換不掉
    try:
        sync = tmp_path / "sync"
        sync.mkdir()
        _signal(sync, "go")
        a = _spawn("burst", "A", 1, sync, tmp_path)
        oa, ea = a.communicate(timeout=30)
    finally:
        holder.close()
    assert a.returncode == 0, (oa, ea)
    assert "[state:replace-failed]" in ea
    assert p.read_text(encoding="utf-8") == before
    assert json.loads(before)["writer"] == "old"
    assert not list(wf.glob("*.tmp"))
    assert not list(wf.glob("*.lock"))

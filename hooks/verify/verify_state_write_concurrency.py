"""verify_state_write_concurrency.py：同 sid 多行程同時 write_state，state 檔永遠是合法 JSON、且等於其中一方的完整內容。

怎麼跑：set WG_CLAUDE_DIR=<worktree> && python -X utf8 -m pytest -q hooks/verify/verify_state_write_concurrency.py
背景（2026-10-12 根層 session ccffc32e 實證）：以前所有 hook 行程共用 state-<sid>.tmp、鎖拿不到就照寫，
  兩支並行 hook 一長一短同時 open(tmp,'w')，短的從 offset 0 蓋掉長的前段、尾巴殘留 → replace 後「Extra data」，
  該 session 餘生每支 hook 都 [state:unreadable] 跳過。
正例：兩個子行程對同一 sid 各寫 50 次長短交錯 → 每次寫完 json.loads 都成功且內容是兩方之一的完整 dict。
反例（證明本案抓得到舊 bug）：子行程內把 tmp 檔名改回共用（os.getpid→0）且鎖形同虛設（兩邊都以為拿到），用檔案同步點排出
  「兩邊都 open 後、長的先寫完、短的再寫」的交錯 → 必重現 Extra data；同交錯只保留 tmp 每行程唯一 → 仍合法。
鎖拿不到（規則 STATE_RMW_LOCKED）：父行程長持 .lock → 子行程等到期限、不無鎖寫，state 檔不動、留一份整份換掉的待併帳，
  stderr 有 [state:lock-timeout]／[state:pending-written]；鎖放掉後下一個握鎖讀 state 的行程併回、刪帳。
replace 失敗：父行程開著 state 檔（Windows 無 FILE_SHARE_DELETE 換不掉）→ 不留 tmp、原 state 仍合法、stderr 有 [state:replace-failed]，
  這次的內容改留待併帳（不丟）。
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

def expected(writer, i):
    """writer 在第 i 次會寫出的完整 dict（A 偶數大、B 奇數大；去 last_updated）。"""
    big = (i % 2 == 0) if writer == "A" else (i % 2 == 1)
    return {"session": {"id": sid}, "writer": writer, "i": i, "pad": "x" * (40000 if big else 8)}

def one_writer(d):
    """d 必須「等於兩方之一會寫出的完整 dict」：用 writer＋i 重建預期後 == 比對。"""
    if not isinstance(d, dict) or d.get("writer") not in ("A", "B") or not isinstance(d.get("i"), int) or not 0 <= d["i"] < n:
        return "NOT_ONE_WRITER:" + json.dumps(d)[:80]
    body = {k: v for k, v in d.items() if k != "last_updated"}
    return "OK" if body == expected(d["writer"], d["i"]) else "NOT_ONE_WRITER:" + json.dumps(body)[:80]

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
        return one_writer(d)
    return "UNREADABLE"

if mode == "check":
    # 反例：把 tag 槽的 JSON 原樣寫進 state 檔，印 read_valid 的判定（證明檢查器抓得到假 dict）
    os.makedirs(os.path.dirname(wg_core.state_path(sid)), exist_ok=True)
    with open(wg_core.state_path(sid), "w", encoding="utf-8", newline="\n") as f:
        f.write(tag)
    print(read_valid())
    raise SystemExit(0)

if mode == "rmw-read":
    # 下一個握鎖讀 state 的行程（hook 模式）：讀之前併回待併帳
    wg_core.begin_state_rmw()
    st = wg_core.read_state(sid)
    wg_core.end_state_rmw()
    print(json.dumps({"state": st}))
    raise SystemExit(0)

if mode == "burst":
    signal(f"{tag}_ready")
    wait("go")
    bad = []
    for i in range(n):
        wg_core._STATE_READ_TEXT.clear()      # 每次都當沒讀過、整份寫：本案驗寫入原子性（讀改寫的合併見 verify_state_parallel_rmw）
        wg_core.write_state(sid, expected(tag, i))
        r = read_valid()
        if r != "OK":
            bad.append(f"{tag}#{i}:{r}")
    print(json.dumps({"tag": tag, "bad": bad}))
    raise SystemExit(0)

# race-*：鎖形同虛設（兩邊都以為拿到，等於沒有互斥）；race-shared 再把 tmp 檔名退回「所有行程共用」（舊 bug 的兩個條件）
wg_core._acquire_state_lock = lambda lock_path, deadline: open(os.devnull, "ab")
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
wg_core.write_state(sid, expected(tag, 0))            # A 長（40000）、B 短（8）
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


def _wait(sync_dir: Path, *names: str, timeout: float = 10) -> None:
    deadline = time.time() + timeout
    while not all((sync_dir / n).exists() for n in names):
        assert time.time() < deadline, f"wait timeout: {names}"
        time.sleep(0.005)


def _expected(writer: str, i: int, n: int = 50) -> dict:
    """父行程側的同一份「兩方各自會寫出的完整 dict」定義（與子行程 expected 一致）。"""
    big = (i % 2 == 0) if writer == "A" else (i % 2 == 1)
    return {"session": {"id": _SID}, "writer": writer, "i": i, "pad": "x" * (40000 if big else 8)}


def _one_writer(d, n: int = 50) -> bool:
    if not isinstance(d, dict) or d.get("writer") not in ("A", "B") or not isinstance(d.get("i"), int) or not 0 <= d["i"] < n:
        return False
    return {k: v for k, v in d.items() if k != "last_updated"} == _expected(d["writer"], d["i"], n)


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
    _wait(sync, "A_ready", "B_ready")   # barrier：兩邊都 import 完、站在起跑線上才放 go
    _signal(sync, "go")
    p = _state_file(tmp_path)
    samples, bad_samples = 0, []
    deadline = time.time() + 30
    while (a.poll() is None or b.poll() is None) and time.time() < deadline:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            samples += 1
            if not _one_writer(d):
                bad_samples.append(json.dumps(d)[:80])
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
    assert samples > 0                                           # 父行程真的有在兩邊寫的期間讀到檔
    final = json.loads(p.read_text(encoding="utf-8"))
    assert final["i"] == 49 and _one_writer(final)
    assert not list((tmp_path / "workflow").glob("*.tmp"))       # 不留 tmp
    assert "[state:unreadable]" not in ea + eb


def test_counterexample_fake_dict_is_rejected_by_checker(tmp_path):
    """檢查器餵一個鍵齊全但不是兩方任一會寫出的 dict → 父行程與子行程兩邊都判壞（證明正例不是只看鍵集合）。"""
    fake = {"session": "wrong", "writer": "C", "i": 999, "pad": "xxx"}
    assert _one_writer(fake) is False
    for bad in ({"session": {"id": _SID}, "writer": "A", "i": 0, "pad": "x" * 8},       # A 第 0 次該是 40000
                {"session": {"id": "other"}, "writer": "B", "i": 1, "pad": "x" * 40000}):
        assert _one_writer(bad) is False, bad
    assert _one_writer(_expected("A", 0)) and _one_writer(_expected("B", 1))
    sync = tmp_path / "sync"
    sync.mkdir()
    c = _spawn("check", json.dumps(fake), 50, sync, tmp_path)
    out, err = c.communicate(timeout=30)
    assert c.returncode == 0, (out, err)
    assert out.strip().startswith("NOT_ONE_WRITER"), out


# ─── 反例：舊條件（共用 tmp＋無鎖）在可控交錯下必重現 Extra data ──────────

def test_counterexample_shared_tmp_without_lock_reproduces_extra_data(tmp_path):
    text, err = _run_race("race-shared", tmp_path)
    with pytest.raises(json.JSONDecodeError, match="Extra data"):
        json.loads(text)
    assert "[state:replace-failed]" in err       # A 換不掉被 B 握著的 tmp（舊碼靜默吞掉；現在浮訊號）
    assert "[state:tmp-left]" in err             # A 的 tmp 也刪不掉（B 握著）→ 浮訊號不吞


def test_same_interleaving_with_unique_tmp_stays_valid(tmp_path):
    """同一套交錯、鎖一樣拿不到，只靠 tmp 每行程唯一 → 檔仍是某一方（B，後寫）的完整 JSON。"""
    text, _ = _run_race("race-unique", tmp_path)
    d = json.loads(text)
    assert {k: v for k, v in d.items() if k != "last_updated"} == _expected("B", 0)
    assert not list((tmp_path / "workflow").glob("*.tmp"))


# ─── 鎖逾時與 replace 失敗 ─────────────────────────────────────────────────

@pytest.mark.skipif(not _WIN, reason="msvcrt 鎖只在 Windows")
def test_lock_held_by_other_process_no_lockless_write_leaves_pending(tmp_path):
    import msvcrt
    wf = tmp_path / "workflow"
    wf.mkdir()
    p = _state_file(tmp_path)
    before = json.dumps({"session": {"id": _SID}, "writer": "old", "i": -1, "pad": "x"})
    p.write_text(before, encoding="utf-8", newline="\n")
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
    assert "[state:lock-timeout]" in ea and "[state:pending-written]" in ea, ea
    assert p.read_text(encoding="utf-8") == before                       # 拿不到鎖不無鎖寫
    assert len(list(wf.glob(f"state-{_SID}.*.pending"))) == 1
    r = _spawn("rmw-read", "R", 1, sync, tmp_path)
    out, err = r.communicate(timeout=30)
    assert r.returncode == 0 and "[state:pending-merged]" in err, (out, err)
    d = json.loads(out.strip().splitlines()[-1])["state"]
    applied = d.pop("_state_pending_applied")                         # 併過的帳名跟合併結果同一次落盤（不會套兩次）
    assert len(applied) == 1 and applied[0].endswith(".pending")
    assert {k: v for k, v in d.items() if k != "last_updated"} == _expected("A", 0, 1)   # 沒讀過就整份寫＝整份換掉
    assert not list(wf.glob("*.pending")) and not list(wf.glob("*.tmp"))


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
    assert "[state:replace-failed]" in ea and "[state:pending-written]" in ea
    assert p.read_text(encoding="utf-8") == before
    assert json.loads(before)["writer"] == "old"
    assert len(list(wf.glob(f"state-{_SID}.*.pending"))) == 1          # 換不掉也不丟：這次的內容留待併帳
    assert not list(wf.glob("*.tmp"))
    assert not list(wf.glob("*.lock"))

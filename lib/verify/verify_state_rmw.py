"""verify_state_rmw.py：hook 以外寫 session state 的三個寫者守 hook 同一把 state-<sid>.lock（規則 STATE_RMW_LOCKED）。

寫者：背景萃取 worker 的逐回合寫回（hooks/extract-worker._per_turn_writeback）、清佇列（lib/ollama_extract_core.ack_then_clear，
兩個 worker 共用）、MCP 伺服器儀表板的 signal 端點（tools/workflow-guardian-mcp/server.js → lib/state.js）。
以前前一個和最後一個完全不拿鎖（tmp→rename 整份覆蓋），ack_then_clear 拿不到鎖就無鎖照寫，會蓋掉 hook 剛寫的那份。
驗的性質：另一個行程（模擬 hook）握著鎖時，寫者不准直接改 state 檔；握的人放掉後才寫，兩邊的改動都在。
拿不到鎖等到期限 → 不寫 state 檔、留待併帳，下一支拿到鎖的 hook 併回。
資料根由根 conftest 隔離（WG_CLAUDE_DIR → 暫存），子行程（握鎖者、node 伺服器）繼承同一個資料根。
怎麼跑：python -X utf8 -m pytest -q lib/verify/verify_state_rmw.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import pytest

TREE = Path(__file__).resolve().parents[2]
HOOKS = TREE / "hooks"
for p in (str(TREE), str(HOOKS)):
    if p not in sys.path:
        sys.path.insert(0, p)

import wg_core  # noqa: E402

SID = "rmw00000-1111-2222-3333-444455556666"
HOLDER = r"""
import sys, time
sys.path.insert(0, sys.argv[1])
import wg_core
sid, hold = sys.argv[2], float(sys.argv[3])
wg_core.begin_state_rmw(time.time() + 10)
st = wg_core.read_state(sid)
print("LOCKED", flush=True)
time.sleep(hold)
st["hook_mark"] = "hook"
wg_core.write_state(sid, st)
wg_core.end_state_rmw()
"""


def _state_path() -> Path:
    return wg_core.state_path(SID)


def _seed(**extra) -> Path:
    p = _state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    for old in p.parent.glob(f"state-{SID}*"):
        old.unlink()
    st = {"session": {"id": SID, "cwd": str(TREE)}, "phase": "working", "knowledge_queue": [{"content": "q0"}, {"content": "q1"}],
          "last_updated": "2026-10-23T00:00:00+08:00", **extra}
    p.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
    return p


def _hold_lock(seconds: float) -> subprocess.Popen:
    """另一個行程照 hook 的方式握這個 session 的 state 鎖 seconds 秒，放掉前寫一個 hook_mark（像 hook 讀改寫）。"""
    proc = subprocess.Popen([sys.executable, "-c", HOLDER, str(HOOKS), SID, str(seconds)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
    assert proc.stdout.readline().strip() == "LOCKED", proc.stderr.read()
    return proc


def _load_extract_worker():
    spec = importlib.util.spec_from_file_location("extract_worker_rmw", HOOKS / "extract-worker.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["extract_worker_rmw"] = mod
    spec.loader.exec_module(mod)
    return mod


def _read() -> dict:
    return json.loads(_state_path().read_text(encoding="utf-8"))


def _ack(key: str, indices, sid: str = SID):
    """ack_then_clear 第一個參數改過（state 路徑 → session id）：照簽名傳，同一支案例拿舊碼回放也走同一個入口。"""
    import inspect
    from lib import ollama_extract_core as oec
    first = next(iter(inspect.signature(oec.ack_then_clear).parameters))
    return oec.ack_then_clear(wg_core.state_path(sid) if first == "state_path" else sid, key, indices)


def test_008_extract_worker_per_turn_waits_for_hook_lock():
    p = _seed()
    before = p.read_bytes()
    ew = _load_extract_worker()
    holder = _hold_lock(1.5)
    t = threading.Thread(target=ew._per_turn_writeback,
                         args=({"session_id": SID}, {"extracted_items": [{"content": "new"}], "final_offset": 42}))
    t.start()
    time.sleep(0.7)
    mid = p.read_bytes()
    t.join(15)
    holder.wait(15)
    assert mid == before, "hook 握著 state 鎖時，worker 直接改了 state 檔（沒守同一把鎖，會蓋掉 hook 剛寫的那份）"
    st = _read()
    assert st.get("hook_mark") == "hook" and st.get("extraction_offset") == 42 and st.get("extract_worker_pid") == 0, st
    assert [q["content"] for q in st["knowledge_queue"]] == ["q0", "q1", "new"], st["knowledge_queue"]


def test_008_ack_then_clear_lock_timeout_leaves_pending_not_overwrite(monkeypatch):
    p = _seed()
    before = p.read_bytes()
    monkeypatch.setattr(wg_core, "_STATE_LOCK_WAIT_S", 0.3)
    holder = _hold_lock(15)
    try:
        _ack("knowledge_queue", [0])
        assert p.read_bytes() == before, "拿不到 state 鎖時 ack_then_clear 無鎖整份寫了 state 檔"
        pending = list(p.parent.glob(f"state-{SID}.*.pending"))
        assert len(pending) == 1, "拿不到鎖要留一份待併帳給下一支 hook 併回"
    finally:
        holder.kill()
        holder.wait(10)
    # 下一支 hook 拿到鎖讀 state → 併回待併帳：q0 清掉、q1 還在
    wg_core.begin_state_rmw(time.time() + 5)
    try:
        st = wg_core.read_state(SID)
    finally:
        wg_core.end_state_rmw()
    assert [q["content"] for q in st["knowledge_queue"]] == ["q1"], st["knowledge_queue"]
    assert not list(p.parent.glob(f"state-{SID}.*.pending"))


def test_008_ack_then_clear_keeps_items_added_concurrently():
    """沒人握鎖：鎖裡讀改寫，pop 只拿掉指定那筆；空 indices 不寫檔。"""
    p = _seed()
    before = p.read_bytes()
    assert _ack("knowledge_queue", []) is True and p.read_bytes() == before
    assert _ack("knowledge_queue", [1]) is True
    assert [q["content"] for q in _read()["knowledge_queue"]] == ["q0"]
    assert _ack("knowledge_queue", [0], sid="no-such-session") is False


def test_008_state_rmw_cli_contract():
    _seed()
    run = lambda payload: subprocess.run([sys.executable, "-m", "lib.state_rmw"], input=payload, capture_output=True,
                                         text=True, encoding="utf-8", cwd=str(TREE), timeout=30)
    r = run(json.dumps({"session_id": SID, "set": {"muted": True}}))
    assert r.returncode == 0 and json.loads(r.stdout.strip().splitlines()[-1])["state"]["muted"] is True, r.stdout + r.stderr
    assert _read()["muted"] is True
    r = run(json.dumps({"session_id": "no-such-session", "set": {"muted": True}}))
    assert r.returncode == 1 and json.loads(r.stdout)["ok"] is False
    r = run("not json")
    assert r.returncode == 1 and "bad input" in json.loads(r.stdout)["error"]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def mcp_server():
    port = _free_port()
    env = {**os.environ, "WG_DASHBOARD_PORT": str(port)}
    proc = subprocess.Popen(["node", str(TREE / "tools" / "workflow-guardian-mcp" / "server.js")], env=env,
                            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, cwd=str(TREE))
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                break
        except OSError:
            time.sleep(0.1)
    else:
        proc.kill()
        pytest.fail("MCP 伺服器沒起來：" + proc.stderr.read().decode("utf-8", "replace")[-800:])
    yield port
    proc.kill()
    proc.wait(10)


def test_008_mcp_signal_endpoint_waits_for_hook_lock(mcp_server):
    p = _seed()
    before = p.read_bytes()
    holder = _hold_lock(1.5)
    reply = {}

    def post():
        req = urllib.request.Request(f"http://127.0.0.1:{mcp_server}/api/sessions/{SID}/signal",
                                     data=json.dumps({"signal": "mute"}).encode(), method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            reply.update(json.loads(r.read().decode("utf-8")))

    t = threading.Thread(target=post)
    t.start()
    time.sleep(0.8)
    mid = p.read_bytes()
    t.join(30)
    holder.wait(15)
    assert mid == before, "hook 握著 state 鎖時，MCP signal 端點直接改了 state 檔（沒守同一把鎖）"
    st = _read()
    assert reply.get("ok") is True and st.get("muted") is True and st.get("hook_mark") == "hook", (reply, st)

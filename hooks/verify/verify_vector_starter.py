"""verify_vector_starter.py — Vector Service 啟動器/自癒契約。

starter.ensure_service（tools/memory-vector-service/starter.py）：
- 服務活著（health ok）→ 回寫 flag、action=already_up、不 spawn
- health timeout + port 被占（hang 死）→ kill service.pid 舊程序後重啟
- spawn lock 新鮮（他 session 剛 spawn）→ 只等不重複 spawn（action=wait_other）
- 就緒後寫 flag、補打增量索引（納入 pull 進來的新 atom）、清 spawn lock；
  等待窗到期未就緒 → ready=False 且不寫 flag、不打索引
- _rotate_log：>max_bytes 輪替 .old，未超過不動
- _health：timeout / refused / ok 三態分類（hang 死與冷啟動需區分對待）

wg_atoms._ensure_vector_ready（UPS 端 re-kick）：
- flag 存在 → (True, False) 不 spawn
- flag 缺 + marker 新鮮（cooldown 內）→ 不 spawn
- flag 缺 + marker 過期 → spawn starter、kicked=True
- 短等待期間 flag 出現 → ready=True

全程 tmp_path 受控路徑 + monkeypatch，不打真實 port / 不動真實 flag。
"""

from __future__ import annotations

import socket
import sys
import time
import urllib.request
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE = HOOKS_DIR.parent
for p in (str(HOOKS_DIR), str(CLAUDE), str(CLAUDE / "lib"),
          str(CLAUDE / "tools" / "memory-vector-service")):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest  # noqa: E402

import starter  # noqa: E402
import wg_atoms  # noqa: E402


@pytest.fixture(autouse=True)
def kick_calls(monkeypatch):
    """攔下就緒後的增量索引補打（不打真實 port），記錄呼叫的 port 供斷言。"""
    calls = []
    monkeypatch.setattr(starter, "_kick_incremental_index", lambda port: calls.append(port))
    return calls


def _paths(tmp_path):
    return dict(
        flag_path=tmp_path / "vector_ready.flag",
        pid_file=tmp_path / "service.pid",
        service_script=tmp_path / "service.py",
        log_path=tmp_path / "vector-service.log",
        lock_path=tmp_path / "vector_starting.lock",
        ready_wait_s=0.3,
        poll_interval_s=0.05,
    )


# ── ensure_service ──────────────────────────────────────────────────────────

def test_already_up_writes_flag_no_spawn(tmp_path, monkeypatch, kick_calls):
    monkeypatch.setattr(starter, "_health", lambda *a, **k: "ok")
    spawned = []
    monkeypatch.setattr(starter, "_spawn_service", lambda *a, **k: spawned.append(1) or True)
    kw = _paths(tmp_path)
    res = starter.ensure_service(3849, **kw)
    assert res["ready"] and res["action"] == "already_up"
    assert kw["flag_path"].read_text(encoding="utf-8") == "ready"
    assert not spawned
    assert kick_calls == [3849]  # 暖路徑也補打增量索引（pull 進來的新 atom 立即入庫）


def test_hung_service_killed_then_respawned(tmp_path, monkeypatch):
    states = ["timeout"]  # 首查 hang；spawn 後就緒
    monkeypatch.setattr(
        starter, "_health", lambda *a, **k: states.pop(0) if states else "ok")
    monkeypatch.setattr(starter, "_port_free", lambda *a, **k: False)
    killed = []
    monkeypatch.setattr(
        starter, "_kill_stale_pid", lambda *a, **k: killed.append(4321) or 4321)
    monkeypatch.setattr(starter, "_spawn_service", lambda *a, **k: True)
    monkeypatch.setattr(time, "sleep", lambda s: None)
    res = starter.ensure_service(3849, **_paths(tmp_path))
    assert killed == [4321]
    assert res["ready"] and res["action"] == "spawned" and res["killed_pid"] == 4321


def test_fresh_spawn_lock_waits_without_respawn(tmp_path, monkeypatch):
    states = ["refused"]
    monkeypatch.setattr(
        starter, "_health", lambda *a, **k: states.pop(0) if states else "ok")
    spawned = []
    monkeypatch.setattr(starter, "_spawn_service", lambda *a, **k: spawned.append(1) or True)
    kw = _paths(tmp_path)
    kw["lock_path"].write_text(str(time.time()), encoding="utf-8")  # 他人剛 spawn
    res = starter.ensure_service(3849, **kw)
    assert res["action"] == "wait_other" and res["ready"]
    assert not spawned


def test_ready_clears_spawn_lock(tmp_path, monkeypatch, kick_calls):
    states = ["refused"]
    monkeypatch.setattr(
        starter, "_health", lambda *a, **k: states.pop(0) if states else "ok")
    monkeypatch.setattr(starter, "_spawn_service", lambda *a, **k: True)
    kw = _paths(tmp_path)
    res = starter.ensure_service(3849, **kw)
    assert res["ready"] and res["action"] == "spawned"
    assert not kw["lock_path"].exists()
    assert kick_calls == [3849]  # 冷啟動就緒後同樣補打增量索引


def test_timeout_no_flag_written(tmp_path, monkeypatch, kick_calls):
    monkeypatch.setattr(starter, "_health", lambda *a, **k: "refused")
    monkeypatch.setattr(starter, "_spawn_service", lambda *a, **k: True)
    kw = _paths(tmp_path)
    res = starter.ensure_service(3849, **kw)
    assert not res["ready"]
    assert not kw["flag_path"].exists()
    assert not kick_calls  # 未就緒不打索引（服務不在，打了也是白打）


# ── 輔助函式 ────────────────────────────────────────────────────────────────

def test_rotate_log_over_max(tmp_path):
    log = tmp_path / "v.log"
    log.write_text("x" * 100, encoding="utf-8")
    assert starter._rotate_log(log, max_bytes=50) is True
    assert not log.exists() and Path(str(log) + ".old").exists()


def test_rotate_log_under_max_noop(tmp_path):
    log = tmp_path / "v.log"
    log.write_text("x" * 10, encoding="utf-8")
    assert starter._rotate_log(log, max_bytes=50) is False
    assert log.exists()


def test_health_classifies_timeout_vs_refused(monkeypatch):
    def _raise_timeout(*a, **k):
        raise urllib.error.URLError(socket.timeout("timed out"))

    def _raise_refused(*a, **k):
        raise urllib.error.URLError(ConnectionRefusedError("refused"))

    import urllib.error
    monkeypatch.setattr(urllib.request, "urlopen", _raise_timeout)
    assert starter._health(3849) == "timeout"
    monkeypatch.setattr(urllib.request, "urlopen", _raise_refused)
    assert starter._health(3849) == "refused"
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: None)
    assert starter._health(3849) == "ok"


# ── wg_atoms._ensure_vector_ready（UPS re-kick）─────────────────────────────

def test_rekick_flag_exists_short_circuits(tmp_path):
    flag = tmp_path / "vector_ready.flag"
    flag.write_text("ready", encoding="utf-8")
    ready, kicked = wg_atoms._ensure_vector_ready(
        "sid", flag_path=flag, marker_path=tmp_path / "m", spawn=False, wait_s=0)
    assert ready and not kicked


def test_rekick_spawns_when_marker_stale(tmp_path, monkeypatch):
    import subprocess
    spawned = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: spawned.append(a[0]))
    marker = tmp_path / "m"
    ready, kicked = wg_atoms._ensure_vector_ready(
        "sid", flag_path=tmp_path / "f", marker_path=marker, wait_s=0)
    assert kicked and not ready
    assert spawned and "starter.py" in str(spawned[0])
    assert marker.exists()  # cooldown 已標記


def test_rekick_cooldown_blocks_respawn(tmp_path, monkeypatch):
    import subprocess
    spawned = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: spawned.append(1))
    marker = tmp_path / "m"
    marker.write_text(str(time.time()), encoding="utf-8")  # 新鮮 marker
    ready, kicked = wg_atoms._ensure_vector_ready(
        "sid", flag_path=tmp_path / "f", marker_path=marker, wait_s=0)
    assert not kicked and not ready and not spawned


def test_rekick_flag_appears_during_wait(tmp_path):
    flag = tmp_path / "f"
    import threading
    threading.Timer(0.1, lambda: flag.write_text("ready", encoding="utf-8")).start()
    ready, _ = wg_atoms._ensure_vector_ready(
        "sid", flag_path=flag, marker_path=tmp_path / "m", spawn=False, wait_s=0.5)
    assert ready

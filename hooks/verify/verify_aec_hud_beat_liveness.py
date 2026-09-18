"""verify_aec_hud_beat_liveness.py — AEC HUD「窗活著」判定不得誤判、不得吞失敗原因。

背景：HUD 頁在 Edge --app 視窗被遮住久了會被瀏覽器休眠/凍結，心跳（/api/aec/beat）
全停；單看心跳 age_s 會把開著的窗判死，每次 notable 都改回 chat 吵人。現制：
  - Node beat-status 回 {age_s, clients}；clients = HUD 頁 SSE 常駐連線數（窗開著的直接證據）
  - handlers/_shared._hud_alive：clients ≥ 1 或 age_s < 門檻 → 活；其餘（含逾時/拒連/404）
    → 死，info 帶 port/threshold/age/clients/elapsed_ms/reason，呼叫端落 guard-aec_hud.jsonl
  - post_tool_use._maybe_spawn_hud：死才標 aec_hud_fallback + 落 log
  - stop：消費旗標前再查一次，活了就不吵 chat

覆蓋：窗活著（連線在、心跳舊）不得 fallback；Node 忙碌慢回 → 判死但原因/耗時必留；
拒連/404 原因必留；Stop 再查活了 → 不印 fallback；真 Node 的 SSE 連線計數（node 不在則 skip）。
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))
ROOT = HOOKS_DIR.parent
SERVER_JS = ROOT / "tools" / "workflow-guardian-mcp" / "server.js"

from handlers import _shared  # noqa: E402
from handlers import post_tool_use as pt  # noqa: E402
from handlers import stop as st  # noqa: E402

_SID = "sid-hud"


# ─── 假 Node：可指定 beat-status 回應與延遲 ─────────────────────────────────

def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _FakeNode:
    """threading HTTPServer，/api/aec/beat-status 回 body（或 404），可先 sleep 模擬 Node 忙碌。"""

    def __init__(self, body, delay_s: float = 0.0, status: int = 200):
        self.port = _free_port()
        body_bytes = json.dumps(body).encode("utf-8")

        class H(BaseHTTPRequestHandler):
            def do_GET(self_inner):  # noqa: N805
                if delay_s:
                    time.sleep(delay_s)
                self_inner.send_response(status)
                self_inner.send_header("Content-Type", "application/json")
                self_inner.end_headers()
                self_inner.wfile.write(body_bytes)

            def log_message(self_inner, *a):  # noqa: N805
                pass

        self.srv = HTTPServer(("127.0.0.1", self.port), H)
        self.t = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.t.start()

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()


@pytest.fixture
def fake_node():
    made = []

    def make(body, delay_s=0.0, status=200):
        n = _FakeNode(body, delay_s, status)
        made.append(n)
        return n

    yield make
    for n in made:
        n.close()


# ─── _hud_alive 純判定 ───────────────────────────────────────────────────────

def test_client_connected_with_stale_beat_is_alive(fake_node):
    """窗開著但頁被凍結（clients=1、age_s 遠超門檻）→ 活，不得 fallback。"""
    n = fake_node({"age_s": 999, "clients": 1})
    alive, info = _shared._hud_alive(n.port, 30)
    assert alive is True
    assert info["clients"] == 1 and info["age_s"] == 999 and info["reason"] == ""


def test_fresh_beat_without_clients_field_is_alive(fake_node):
    """舊版 Node（無 clients 欄）心跳新 → 活（退路仍有效）。"""
    n = fake_node({"age_s": 3})
    alive, info = _shared._hud_alive(n.port, 30)
    assert alive is True and info["clients"] == 0


def test_no_client_and_stale_beat_is_dead_with_reason(fake_node):
    """無連線且心跳舊 → 死；info 帶實際 port/門檻/age/clients/原因（可稽核）。"""
    n = fake_node({"age_s": 200, "clients": 0})
    alive, info = _shared._hud_alive(n.port, 30)
    assert alive is False
    assert info["reason"] == "no_hud_client_and_beat_stale"
    assert info["port"] == n.port and info["threshold_s"] == 30
    assert info["age_s"] == 200 and info["clients"] == 0
    assert isinstance(info["elapsed_ms"], int)


def test_busy_node_slow_reply_times_out_with_reason(fake_node):
    """Node 忙碌 1.5s 才回（> 0.6s 逾時）→ 判死，但原因與耗時必留，不得吞掉。"""
    n = fake_node({"age_s": 1, "clients": 1}, delay_s=1.5)
    alive, info = _shared._hud_alive(n.port, 30)
    assert alive is False
    assert info["reason"], "逾時原因不得為空"
    assert "timed out" in info["reason"].lower() or "timeout" in info["reason"].lower()
    assert 500 <= info["elapsed_ms"] < 1500


def test_unreachable_port_keeps_reason():
    """port 沒人聽 → 死，reason 帶連線錯誤型別。"""
    alive, info = _shared._hud_alive(_free_port(), 30)
    assert alive is False
    assert info["reason"].startswith("URLError")


def test_old_node_404_keeps_reason(fake_node):
    """舊碼沒有 beat-status 路由（404）→ 死，reason 帶 HTTPError。"""
    n = fake_node({}, status=404)
    alive, info = _shared._hud_alive(n.port, 30)
    assert alive is False and info["reason"].startswith("HTTPError")


# ─── post_tool_use：活不標旗；死標旗 + 落 guard log ──────────────────────────

def _spawn(monkeypatch, alive_info, sev="notable", cfg=None):
    logged = []
    monkeypatch.setattr(pt, "_hud_alive", lambda *a, **k: alive_info)
    monkeypatch.setattr(pt, "append_guard_log", lambda g, p: logged.append((g, p)))
    monkeypatch.setattr(pt, "_spawn_hud_edge", lambda *a, **k: None)
    state = {}
    pt._maybe_spawn_hud(sev, state, cfg or {"aec": {"hud_stale_s": 30}}, _SID)
    return state, logged


def test_ptu_alive_no_fallback_no_log(monkeypatch):
    """窗活著 → 不標 aec_hud_fallback、不落 log。"""
    state, logged = _spawn(monkeypatch, (True, {"clients": 1, "age_s": 500, "reason": ""}))
    assert not state.get("aec_hud_fallback") and logged == []


def test_ptu_dead_notable_flags_and_logs_reason(monkeypatch):
    """窗死 + notable → 標旗；guard-aec_hud 記 where/session/severity + 判死 info。"""
    info = {"port": 3848, "threshold_s": 30, "reason": "URLError: refused", "elapsed_ms": 2}
    state, logged = _spawn(monkeypatch, (False, info))
    assert state.get("aec_hud_fallback") is True
    assert len(logged) == 1 and logged[0][0] == "aec_hud"
    p = logged[0][1]
    assert p["where"] == "post_tool_use" and p["session_id"] == _SID and p["severity"] == "notable"
    assert p["reason"] == "URLError: refused" and p["port"] == 3848


def test_ptu_dead_routine_logs_but_no_flag(monkeypatch):
    """routine 窗死只落 disk：記 log 但不標旗（不打擾）。"""
    state, logged = _spawn(monkeypatch, (False, {"reason": "x"}), sev="routine")
    assert not state.get("aec_hud_fallback") and len(logged) == 1


# ─── stop：消費旗標前再查一次 ──────────────────────────────────────────────

_CORE = r"c:\a\.claude\hooks\x.py"


@pytest.fixture
def driven(monkeypatch):
    """驅動 handle_stop 到 AEC fallback 段（比照 verify_aec_emission_gate.driven）。"""
    monkeypatch.setattr(st, "_find_session_transcript", lambda *a, **k: None)
    monkeypatch.setattr(st, "get_last_assistant_text", lambda *a, **k: "全部完成了")
    monkeypatch.setattr(st, "token_warn_payload", lambda *a, **k: "")
    monkeypatch.setattr(st, "detect_evasion", lambda *a, **k: None)
    monkeypatch.setattr(st, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(st, "_attribute_usefulness", lambda *a, **k: None)
    monkeypatch.setattr(st, "_detect_uncommitted_files", lambda mf: [])
    monkeypatch.setattr(st, "_maybe_spawn_user_extract_worker", lambda *a, **k: None)
    logged = []
    monkeypatch.setattr(st, "append_guard_log", lambda g, p: logged.append((g, p)))

    def drive(alive_info, capsys):
        monkeypatch.setattr(st, "_hud_alive", lambda *a, **k: alive_info)
        state = {
            "phase": "working",
            "modified_files": [{"path": _CORE, "tool": "Edit", "session_id": _SID}],
            "failing_tests": [], "recent_user_prompts": [], "stop_blocked_count": 0,
            "turn_seq": 5,
            "anti_evasion_report": {
                "session_id": _SID, "turn_seq": 5, "severity": "notable",
                "a": "- x.py:10 — 修了 y", "b": "無", "at": "2026-09-18T00:00:00+08:00",
            },
            "aec_hud_fallback": True,
        }
        monkeypatch.setattr(st, "_ensure_state", lambda *a, **k: state)
        with pytest.raises(SystemExit):
            st.handle_stop({"session_id": _SID, "cwd": ""}, {})
        return capsys.readouterr().out, state, logged

    return drive


def test_stop_recheck_alive_suppresses_fallback(driven, capsys):
    """emit 時判死、Stop 再查活了（例如 HUD 頁重連完成）→ 不印 fallback，旗標仍消費，log 記 alive。"""
    out, state, logged = driven((True, {"clients": 1, "age_s": 400, "reason": ""}), capsys)
    assert "[Guardian:AEC] HUD" not in out
    assert state["aec_hud_fallback"] is False
    assert any(g == "aec_hud" and p["where"] == "stop" and p["alive"] is True for g, p in logged)


def test_stop_recheck_dead_prints_reason(driven, capsys):
    """Stop 再查仍死 → 印 fallback，訊息帶判死原因（不再只寫「心跳逾時」）。"""
    out, state, logged = driven((False, {"reason": "URLError: refused", "age_s": None}), capsys)
    assert "[Guardian:AEC] HUD 不可達（URLError: refused）" in out
    assert "缺失修補" in out
    assert any(g == "aec_hud" and p["where"] == "stop" and p["alive"] is False for g, p in logged)


# ─── 真 Node：SSE 連線計數 ─────────────────────────────────────────────────

@pytest.mark.skipif(not shutil.which("node"), reason="node not available")
def test_real_node_counts_sse_clients():
    """server.js 於臨時 port：開一條 /api/aec/stream 連線 → clients=1；斷線 → 0；
    期間 beat-status 仍毫秒級回應（SSE 不占事件迴圈）。"""
    port = _free_port()
    env = dict(os.environ, WG_DASHBOARD_PORT=str(port))
    proc = subprocess.Popen(
        ["node", str(SERVER_JS)], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, env=env, cwd=str(ROOT),
    )
    try:
        info = {}
        for _ in range(50):
            alive, info = _shared._hud_alive(port, 30)
            if "age_s" in info:
                break
            time.sleep(0.2)
        assert "age_s" in info, f"node 未就緒: {info}"
        assert alive is False and info["clients"] == 0

        s = socket.create_connection(("127.0.0.1", port), timeout=3)
        s.sendall(b"GET /api/aec/stream HTTP/1.1\r\nHost: 127.0.0.1\r\nAccept: text/event-stream\r\n\r\n")
        head = s.recv(4096).decode("utf-8", "replace")
        assert "200" in head.splitlines()[0] and "text/event-stream" in head
        alive, info = _shared._hud_alive(port, 30)
        assert alive is True and info["clients"] == 1 and info["elapsed_ms"] < 600

        s.close()
        for _ in range(20):
            alive, info = _shared._hud_alive(port, 30)
            if info.get("clients") == 0:
                break
            time.sleep(0.1)
        assert alive is False and info["clients"] == 0
    finally:
        proc.kill()

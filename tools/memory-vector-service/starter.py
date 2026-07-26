"""starter.py — Vector Service 啟動器 + 自癒（SessionStart 與 UPS re-kick 共用入口）。

職責（對症三類就緒空窗）：
1. 服務活著只是 flag 遺失 → 首次 health 成功即回寫 flag（毫秒級恢復）。
2. 服務 hang 死佔 port（health timeout + port 被占）→ kill service.pid 舊程序後重啟。
3. 冷啟動慢（Ollama 不在 → bge-m3 fallback 載入可遠超 15s）→ 等待窗 120s，
   並以 spawn lock 防多 session 同時各起一隻重複載入 embedder。

可觀測性：service.py 的 stdout/stderr 落 `Logs/vector-service.log`（>5MB 輪替 .old），
starter 自身動作也以時間戳行寫入同檔；結果一行 JSON 寫 vector-observation-probe.log
（欄位相容舊 session_start 內嵌版，新增 phase / action / wait_s）。

用法：python starter.py [--phase sessionstart|ups_rekick|manual] [--session-id X]
（呼叫端 fire-and-forget spawn；本身無 daemon、跑完即退。）
"""

from __future__ import annotations

import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

CLAUDE_DIR = Path.home() / ".claude"
WORKFLOW_DIR = CLAUDE_DIR / "workflow"
LOGS_DIR = CLAUDE_DIR / "Logs"
SERVICE_SCRIPT = Path(__file__).resolve().parent / "service.py"
SERVICE_LOG = LOGS_DIR / "vector-service.log"
PROBE_LOG = LOGS_DIR / "vector-observation-probe.log"
FLAG_PATH = WORKFLOW_DIR / "vector_ready.flag"
PID_FILE = CLAUDE_DIR / "memory" / "_vectordb" / "service.pid"
SPAWN_LOCK = WORKFLOW_DIR / "vector_starting.lock"

DEFAULT_PORT = 3849
READY_WAIT_S = 120.0     # 冷啟動需容納 fallback embedder（bge-m3）的分鐘級載入
SPAWN_LOCK_TTL_S = 150.0  # lock 新鮮期：期間內其他 starter 只等不重複 spawn
LOG_MAX_BYTES = 5 * 1024 * 1024


def _slog(msg: str, log_path: Path = SERVICE_LOG) -> None:
    """Starter 動作記錄：時間戳行附加到 service log（失敗不擋流程）。"""
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} [starter] {msg}\n")
    except Exception:
        pass


def _health(port: int, timeout: float = 2.0) -> str:
    """回 'ok' | 'refused' | 'timeout' | 'error'。timeout 是 hang 死訊號，需區分。"""
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=timeout)
        return "ok"
    except Exception as e:
        cause = getattr(e, "reason", e)
        if isinstance(cause, (socket.timeout, TimeoutError)) or "timed out" in str(e):
            return "timeout"
        if isinstance(cause, ConnectionRefusedError) or "refused" in str(e).lower():
            return "refused"
        return "error"


def _port_free(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


# pid 身分指紋：cmdline 必須同時含這兩段才視為本服務
# （單獨 "service.py" 太寬——verify_vector_service.py 等檔名也含該子字串）。
_SERVICE_CMDLINE_MARKS = ("memory-vector-service", "service.py")


def _pid_cmdline(pid: int) -> Optional[str]:
    """取 pid 的 command line；取不到回 None（呼叫端保守不殺）。

    Windows 免 psutil：PowerShell CIM 為主，wmic 為備（部分 Win11 已移除 wmic）。
    POSIX：讀 /proc/<pid>/cmdline。
    """
    if sys.platform == "win32":
        candidates = [
            ["powershell", "-NoProfile", "-Command",
             f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').CommandLine"],
            ["wmic", "process", "where", f"processid={pid}", "get", "commandline"],
        ]
        for cmd in candidates:
            try:
                out = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=10,
                    creationflags=0x08000000,  # CREATE_NO_WINDOW
                ).stdout.strip()
                if out:
                    return out
            except Exception:
                continue
        return None
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
        return raw.replace(b"\0", b" ").decode("utf-8", "replace").strip() or None
    except OSError:
        return None


def _kill_stale_pid(pid_file: Path = PID_FILE) -> Optional[int]:
    """殺掉 pid file 指向的 hang 死服務。回被殺的 pid；無 pid file / 失敗 / 身分不符回 None。

    殺前驗證 pid 身分（Windows PID 會重用，殘留 pid file 可能指向無辜程序）：
    cmdline 須含 memory-vector-service + service.py 才殺；取不到 cmdline →
    保守不殺 + 落 log；cmdline 屬他程序 → 不殺、清掉過期 pid file。
    """
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
    except Exception:
        return None
    cmdline = _pid_cmdline(pid)
    if cmdline is None:
        _slog(f"pid {pid} cmdline unverifiable; refusing to kill (fail-safe)")
        return None
    if not all(mark in cmdline for mark in _SERVICE_CMDLINE_MARKS):
        _slog(f"pid {pid} belongs to another process ({cmdline[:120]!r}); "
              "not killing; removing stale pid file")
        try:
            pid_file.unlink()
        except OSError:
            pass
        return None
    try:
        os.kill(pid, signal.SIGTERM)
        return pid
    except Exception:
        return None


def _rotate_log(log_path: Path = SERVICE_LOG, max_bytes: int = LOG_MAX_BYTES) -> bool:
    """>max_bytes 輪替為 .old（單代）。服務運行中持有 handle 時 replace 失敗屬預期，
    fail-open 續 append（輪替會在下次服務不在時成功）。"""
    try:
        if log_path.exists() and log_path.stat().st_size > max_bytes:
            os.replace(str(log_path), str(log_path) + ".old")
            return True
    except Exception:
        pass
    return False


def _spawn_lock_fresh(lock_path: Path = SPAWN_LOCK, ttl_s: float = SPAWN_LOCK_TTL_S) -> bool:
    try:
        return (time.time() - lock_path.stat().st_mtime) < ttl_s
    except Exception:
        return False


def _spawn_service(port: int, service_script: Path = SERVICE_SCRIPT,
                   log_path: Path = SERVICE_LOG) -> bool:
    """起 service.py，stdout/stderr 附加到 vector-service.log（可觀測性鐵律：
    啟動失敗原因不再進 DEVNULL 黑洞）。"""
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_f = open(log_path, "a", encoding="utf-8")
        kw: Dict[str, Any] = {
            "stdin": subprocess.DEVNULL, "stdout": log_f, "stderr": log_f,
        }
        if sys.platform == "win32":
            kw["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
        else:
            kw["start_new_session"] = True
        subprocess.Popen([sys.executable, str(service_script)], **kw)
        log_f.close()  # 子程序已繼承 handle
        return True
    except Exception as e:
        _slog(f"spawn failed: {e}", log_path)
        return False


def ensure_service(
    port: int = DEFAULT_PORT,
    *,
    flag_path: Path = FLAG_PATH,
    pid_file: Path = PID_FILE,
    service_script: Path = SERVICE_SCRIPT,
    log_path: Path = SERVICE_LOG,
    lock_path: Path = SPAWN_LOCK,
    ready_wait_s: float = READY_WAIT_S,
    poll_interval_s: float = 0.5,
) -> Dict[str, Any]:
    """主流程。回 {ready, action, wait_s, killed_pid}。"""
    t0 = time.time()
    h = _health(port)
    if h == "ok":
        _write_flag(flag_path)
        return {"ready": True, "action": "already_up", "wait_s": 0.0, "killed_pid": None}

    killed_pid = None
    if h == "timeout" and not _port_free(port):
        killed_pid = _kill_stale_pid(pid_file)
        _slog(f"health timeout + port occupied → killed stale pid={killed_pid}", log_path)
        time.sleep(1.0)

    if _spawn_lock_fresh(lock_path):
        action = "wait_other"  # 他 session 剛 spawn，等它就緒即可，避免重複載 embedder
    else:
        try:
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            lock_path.write_text(str(time.time()), encoding="utf-8")
        except Exception:
            pass
        _rotate_log(log_path)
        action = "spawned" if _spawn_service(port, service_script, log_path) else "spawn_failed"
        _slog(f"action={action} port={port}", log_path)

    ready = False
    if action != "spawn_failed":
        deadline = t0 + ready_wait_s
        while time.time() < deadline:
            if _health(port) == "ok":
                ready = True
                break
            time.sleep(poll_interval_s)

    wait_s = round(time.time() - t0, 1)
    if ready:
        _write_flag(flag_path)
        try:
            lock_path.unlink(missing_ok=True)
        except Exception:
            pass
    _slog(f"result ready={ready} action={action} wait_s={wait_s}", log_path)
    return {"ready": ready, "action": action, "wait_s": wait_s, "killed_pid": killed_pid}


def _write_flag(flag_path: Path = FLAG_PATH) -> None:
    try:
        flag_path.parent.mkdir(parents=True, exist_ok=True)
        flag_path.write_text("ready", encoding="utf-8")
    except Exception:
        pass


def _log_probe(rec: Dict[str, Any], probe_log: Path = PROBE_LOG) -> None:
    try:
        probe_log.parent.mkdir(parents=True, exist_ok=True)
        with open(probe_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _sessionstart_probe(port: int) -> Dict[str, Any]:
    """沿用舊內嵌版的 A/B 對照探針：vector ranked 查詢 vs memory/ 關鍵字命中數。"""
    probe_q = "workflow guardian SessionStart 機制"
    vec_count = -1
    try:
        urllib.request.urlopen(
            f"http://127.0.0.1:{port}/search?q=warmup&top_k=1&min_score=0.99", timeout=15)
    except Exception:
        pass
    try:
        params = urllib.parse.urlencode({"q": probe_q, "top_k": 5, "min_score": 0.5})
        with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/search/ranked?{params}", timeout=10) as r:
            data = json.loads(r.read())
            vec_count = len(data) if isinstance(data, list) else 0
    except Exception:
        vec_count = -1

    kw_count = 0
    try:
        pattern = re.compile("workflow|guardian|SessionStart", re.IGNORECASE)
        for md in (CLAUDE_DIR / "memory").rglob("*.md"):
            try:
                if pattern.search(md.read_text(encoding="utf-8", errors="ignore")):
                    kw_count += 1
            except Exception:
                pass
    except Exception:
        pass
    return {"result_count": vec_count, "kw_count": kw_count, "probe_q": probe_q}


def main(argv: Optional[list] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", default="manual",
                    choices=["sessionstart", "ups_rekick", "manual"])
    ap.add_argument("--session-id", default="")
    ap.add_argument("--port", type=int, default=0)
    args = ap.parse_args(argv)

    port = args.port
    if not port:
        try:
            cfg = json.loads((WORKFLOW_DIR / "config.json").read_text(encoding="utf-8"))
            port = cfg.get("vector_search", {}).get("service_port", DEFAULT_PORT)
        except Exception:
            port = DEFAULT_PORT

    try:
        res = ensure_service(port)
    except Exception as e:
        _slog(f"ensure_service crashed: {e!r}")
        res = {"ready": False, "action": "starter_error", "wait_s": 0.0, "killed_pid": None}

    rec: Dict[str, Any] = {
        "ts": time.time(),
        "session_id": args.session_id,
        "fn": "session_start_probe" if args.phase == "sessionstart" else f"{args.phase}_probe",
        "flag_state": "ready" if res["ready"] else "no_flag",
        "result_count": -1,
        "fallback_used": not res["ready"],
        "phase": args.phase,
        "action": res["action"],
        "wait_s": res["wait_s"],
    }
    if res.get("killed_pid"):
        rec["killed_pid"] = res["killed_pid"]
    if args.phase == "sessionstart" and res["ready"]:
        rec.update(_sessionstart_probe(port))
        rec["fallback_used"] = rec["result_count"] < 0
    _log_probe(rec)
    return 0 if res["ready"] else 1


if __name__ == "__main__":
    sys.exit(main())

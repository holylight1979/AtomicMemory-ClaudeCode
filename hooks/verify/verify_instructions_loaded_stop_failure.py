"""verify_instructions_loaded_stop_failure.py — InstructionsLoaded／StopFailure 兩支記帳 handler。

怎麼跑：python hooks/verify/verify_instructions_loaded_stop_failure.py（印 INSTRUCTIONS_STOPFAIL_CHECK PASS，exit 0）
案例：官方格式輸入 → 子行程跑 handler 檔（目標 <100 ms）斷言落帳；dispatcher 路由；有待結算注入時標 aborted。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hooks"))
sys.path.insert(0, str(ROOT / "lib"))
H = ROOT / "hooks"


def run(script: Path, payload: dict, data: Path) -> float:
    env = {**os.environ, "WG_CLAUDE_DIR": str(data), "WG_CODING_GUARD": "1"}   # 守門開：dispatcher 才會分派這兩個事件
    env.pop("WG_TEST_LOGS_DIR", None)
    t = time.time()
    r = subprocess.run([sys.executable, "-I", str(script)], input=json.dumps(payload).encode(), env=env,
                       capture_output=True, timeout=60)
    dt = time.time() - t
    assert r.returncode == 0 and r.stdout == b"", (r.returncode, r.stdout, r.stderr)
    return dt


def lines(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()]


def main() -> None:
    il = {"session_id": "s1", "transcript_path": "/t.jsonl", "cwd": "/p", "hook_event_name": "InstructionsLoaded",
          "file_path": "/h/.claude/CLAUDE.md", "memory_type": "User", "load_reason": "compact"}
    sf = {"session_id": "s1", "cwd": "/p", "hook_event_name": "StopFailure", "error": "rate_limit",
          "error_details": "429 Too Many Requests", "last_assistant_message": "API Error: Rate limit reached"}
    with tempfile.TemporaryDirectory() as d:
        data = Path(d)
        (data / "workflow").mkdir()
        # 1 InstructionsLoaded 直接跑：落帳、無輸出
        dt = run(H / "handlers" / "instructions_loaded.py", il, data)
        rec = lines(data / "Logs" / "instructions-loaded.jsonl")[0]
        assert rec["session_id"] == "s1" and rec["load_reason"] == "compact" and rec["file_path"].endswith("CLAUDE.md"), rec
        print(f"instructions_loaded 子行程總耗時 {dt*1000:.0f} ms（含直譯器啟動約 100 ms）")
        # 2 StopFailure 無 state：落帳、不標
        dt = run(H / "handlers" / "stop_failure.py", sf, data)
        rec = lines(data / "Logs" / "guard-stop_failure.jsonl")[0]
        assert rec["error"] == "rate_limit" and rec["pending_attribution"] is False and rec["aborted"] is False, rec
        print(f"stop_failure(無待結算) 子行程總耗時 {dt*1000:.0f} ms")
        # handler 本身 <100 ms（行程內計時，不含直譯器啟動）
        import handlers.instructions_loaded as m_il, handlers.stop_failure as m_sf
        os.environ["WG_TEST_LOGS_DIR"] = str(data / "Logs")
        for fn, pl in ((m_il.handle_instructions_loaded, il), (m_sf.handle_stop_failure, sf)):
            t = time.time(); fn(pl, {}); ms = (time.time() - t) * 1000
            assert ms < 100, (fn.__name__, ms)
            print(f"{fn.__name__} 行程內 {ms:.1f} ms")
        os.environ.pop("WG_TEST_LOGS_DIR")
        # 3 StopFailure 有待結算注入：標 aborted、Stop 的歸因會跳過本回合
        sp = data / "workflow" / "state-s1.json"
        sp.write_text(json.dumps({"session_id": "s1", "turn_seq": 4, "turn_injected": [{"name": "a", "path": "x"}]}), encoding="utf-8")
        run(H / "handlers" / "stop_failure.py", sf, data)
        st = json.loads(sp.read_text(encoding="utf-8"))
        assert st["turn_aborted_seq"] == 4 and st["usefulness_attributed_seq"] == 4, st
        rec = lines(data / "Logs" / "guard-stop_failure.jsonl")[-1]
        assert rec["pending_attribution"] is True and rec["aborted"] is True and rec["turn_seq"] == 4, rec
        # 4 dispatcher 路由兩個事件
        for ev, payload, logname in (("InstructionsLoaded", {**il, "load_reason": "include"}, "instructions-loaded.jsonl"),
                                     ("StopFailure", {**sf, "error": "overloaded"}, "guard-stop_failure.jsonl")):
            n0 = len(lines(data / "Logs" / logname))
            run(H / "dispatcher.py", payload, data)
            got = lines(data / "Logs" / logname)
            assert len(got) == n0 + 1, (ev, got)
        assert lines(data / "Logs" / "guard-stop_failure.jsonl")[-1]["error"] == "overloaded"
        assert lines(data / "Logs" / "instructions-loaded.jsonl")[-1]["load_reason"] == "include"
    # 5 週健檢一行
    import importlib.util
    spec = importlib.util.spec_from_file_location("hw", ROOT / "tools" / "health-weekly.py")
    hw = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hw)
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "Logs").mkdir()
        from datetime import datetime
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        rows = [{"at": now, "session_id": "s", "load_reason": "session_start", "file_path": "/x/CLAUDE.md"},
                {"at": now, "session_id": "s", "load_reason": "compact", "file_path": "/x/CLAUDE.md"}]
        (Path(d) / "Logs" / "instructions-loaded.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        hw.CLAUDE_DIR = Path(d)
        out = hw._instructions_loaded_block()
        assert "compact 1" in out[0] and "CLAUDE.md 1 場" in out[1] and "MEMORY.md 0 場" in out[1], out
    print("INSTRUCTIONS_STOPFAIL_CHECK PASS")


if __name__ == "__main__":
    main()

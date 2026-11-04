"""stop_failure.py — StopFailure（回合因 API 錯誤結束，取代 Stop）只留帳，不輸出。

做什麼：官方在這種回合不跑 Stop，所以 Stop 的整串閘與效用歸因都不會跑。這裡
1. 追加一行到 Logs/guard-stop_failure.jsonl：錯誤類型、錯誤細節、回合序號、這回合有沒有待結算的注入歸因、有沒有標 aborted；
2. 若本回合有待結算的注入歸因（turn_injected 還沒結），把 state 標 turn_aborted_seq=本回合、並把 usefulness_attributed_seq 設成本回合：
   下一次 Stop 就不會拿這個被打斷的回合去算「用過／沒用」（兩邊都不計）。
官方丟棄此 hook 的輸出，所以什麼都不印。無待結算時只用標準庫（目標 <100 ms）；要改 state 才惰性載 wg_core，走它的鎖與寫回。
settings.json 可直接指向本檔（__main__ 讀 stdin），也可由 dispatcher 路由進 handle_stop_failure。

規則：STOP_FAILURE_ABORTED（hooks/wg_release_rules.py）。
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
from project_root import claude_data_dir  # noqa: E402

LOG_NAME = "guard-stop_failure.jsonl"


def _logs_dir() -> Path:
    override = os.environ.get("WG_TEST_LOGS_DIR")
    return Path(override) if override else claude_data_dir() / "Logs"


def _peek_state(session_id: str) -> dict:
    """不上鎖、不載 wg_core 的唯讀快看；讀不到當沒有 state。"""
    try:
        return json.loads((claude_data_dir() / "workflow" / f"state-{session_id}.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}


def _pending(state: dict) -> bool:
    seq = int(state.get("turn_seq", 0) or 0)
    if seq and state.get("usefulness_attributed_seq") != seq and state.get("turn_injected"):
        return True
    return False


def _mark_aborted(session_id: str) -> bool:
    """標 aborted（走 wg_core 的鎖與寫回）；回是否真的標到。"""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import wg_core
    state = wg_core.read_state(session_id)
    if not state or not _pending(state):
        return False
    seq = int(state.get("turn_seq", 0))
    state["turn_aborted_seq"] = seq
    state["usefulness_attributed_seq"] = seq
    wg_core.write_state(session_id, state)
    return True


def handle_stop_failure(input_data: dict, config: dict | None = None) -> None:
    sid = str(input_data.get("session_id") or "")
    state = _peek_state(sid) if sid else {}
    pending = _pending(state)
    aborted = False
    if pending:
        try:
            aborted = _mark_aborted(sid)
        except Exception as e:   # 標記失敗留在帳上，不擋
            print(f"[workflow-guardian] StopFailure 標 aborted 失敗: {e}", file=sys.stderr)
    rec = {"at": datetime.now().astimezone().isoformat(timespec="seconds"), "session_id": sid,
           "error": input_data.get("error", ""), "error_details": input_data.get("error_details", ""),
           "turn_seq": int(state.get("turn_seq", 0) or 0), "pending_attribution": pending, "aborted": aborted}
    try:
        d = _logs_dir()
        d.mkdir(parents=True, exist_ok=True)
        with open(d / LOG_NAME, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"[workflow-guardian] StopFailure 記帳失敗: {e}", file=sys.stderr)


if __name__ == "__main__":
    try:
        data = json.loads(sys.stdin.buffer.read())
    except ValueError:
        sys.exit(0)
    handle_stop_failure(data)

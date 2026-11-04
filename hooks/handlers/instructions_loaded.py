"""instructions_loaded.py — InstructionsLoaded（CLAUDE.md、rules、@include 載入）只記帳，不輸出。

做什麼：官方在 CLAUDE.md／`.claude/rules/*.md` 載入時（開場、碰到有 paths: 的規則、壓縮後重載）各觸發一次；
這裡把「哪個檔、為什麼載、哪個 session」追加一行到 Logs/instructions-loaded.jsonl，供週健檢對帳「以為有載」。
官方說這個事件不支援決策、輸出被丟棄，所以什麼都不印。只用標準庫（行程啟動不載 wg_core，目標 <100 ms）。
settings.json 可直接指向本檔（__main__ 讀 stdin），也可由 dispatcher 路由進 handle_instructions_loaded。

規則：INSTRUCTIONS_LOADED_LEDGER（hooks/wg_release_rules.py）。
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
from project_root import claude_data_dir  # noqa: E402

LOG_NAME = "instructions-loaded.jsonl"
_FIELDS = ("file_path", "memory_type", "load_reason", "globs", "trigger_file_path", "parent_file_path", "agent_type")


def logs_dir() -> Path:
    override = os.environ.get("WG_TEST_LOGS_DIR")
    return Path(override) if override else claude_data_dir() / "Logs"


def handle_instructions_loaded(input_data: dict, config: dict | None = None) -> None:
    rec = {"at": datetime.now().astimezone().isoformat(timespec="seconds"), "session_id": input_data.get("session_id", "")}
    rec.update({k: input_data[k] for k in _FIELDS if input_data.get(k)})
    try:
        d = logs_dir()
        d.mkdir(parents=True, exist_ok=True)
        with open(d / LOG_NAME, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError as e:   # 記帳失敗不能擋載入，但要浮訊號
        print(f"[workflow-guardian] instructions-loaded 記帳失敗: {e}", file=sys.stderr)


if __name__ == "__main__":
    try:
        data = json.loads(sys.stdin.buffer.read())
    except ValueError:
        sys.exit(0)
    handle_instructions_loaded(data)

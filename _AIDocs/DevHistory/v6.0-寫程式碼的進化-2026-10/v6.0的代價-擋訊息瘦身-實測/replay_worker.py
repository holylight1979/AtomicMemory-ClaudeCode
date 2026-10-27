"""replay_worker.py：在指定的程式版本裡，把 004 一跑第一回合的每一次「問」依序交給 wg_entrypoint.entry_note
（動資料檔那幾筆先用真輸入交 wg_data_file.gate 重組擋訊息本文），印出每一筆產出的 JSON。
跑法：python -X utf8 replay_worker.py --code <程式碼根> --asks <asks.json> --root <資料根複本> --config <config.json> --out <輸出.json>
（WG_CLAUDE_DIR 由呼叫端設成資料根複本；本檔不碰 live。）"""
import argparse
import json
import sys
from pathlib import Path

ap = argparse.ArgumentParser()
for k in ("--code", "--asks", "--config", "--out"):
    ap.add_argument(k, required=True)
a = ap.parse_args()
sys.path[:0] = [str(Path(a.code) / "hooks"), str(Path(a.code) / "lib")]
import wg_entrypoint as ep  # noqa: E402
import wg_data_file as df  # noqa: E402

cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
out = []
for ask in json.loads(Path(a.asks).read_text(encoding="utf-8")):
    q = ask["question"]
    if ask.get("gate"):
        g = ask["gate"]
        if ask.get("state"):
            import wg_core
            wg_core.write_state(ask["sid"], ask["state"])
        q = df.gate(g["tool_name"], g["tool_input"], g["input_data"], cfg) or ""
    note = ep.entry_note(q, ask["path"], session_id=ask["sid"], config=cfg)
    out.append({"i": ask["i"], "question": q, "note": note})
Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"REPLAY_WORKER DONE asks={len(out)}")

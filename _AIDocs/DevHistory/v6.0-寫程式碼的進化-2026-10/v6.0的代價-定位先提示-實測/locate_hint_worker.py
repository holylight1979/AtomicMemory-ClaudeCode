"""locate_hint_worker.py：在指定的程式版本裡，把 004 一跑第一回合的讀檔、改檔、need_goal 呼叫照順序重播（同一批輸入交給那一版的函式）。

每個事件先把假 transcript 寫成「那個時點的前綴」（＋反事實插入的列），再交：
  read → wg_overview.on_read（PostToolUse）；edit → 每個寫入目標先 wg_need_goal.edit_gate 再 wg_overview.on_edit（PreToolUse 同順序）；
  goal → handlers.post_tool_use._need_goal_after_tool（PostToolUse 套用 need_goal 並清已定位）。
跑法：python -X utf8 locate_hint_worker.py --code <程式碼根> --events <events.json> --data <資料根複本> --out <輸出.json>
（WG_CLAUDE_DIR 由本檔設成資料根複本；寫入只落複本與假 transcript，不碰 live。）
"""
import argparse
import inspect
import json
import os
import sys
from pathlib import Path

ap = argparse.ArgumentParser()
for k in ("--code", "--events", "--data", "--out", "--transcript"):
    ap.add_argument(k, required=True)
a = ap.parse_args()
os.environ.update(WG_CLAUDE_DIR=a.data, WG_V6="1", WG_TEMP_RULES="off")
sys.path[:0] = [str(Path(a.code) / "hooks"), str(Path(a.code) / "lib")]
import wg_core  # noqa: E402
import wg_need_goal as ng  # noqa: E402
import wg_overview as wo  # noqa: E402
from handlers import post_tool_use as pt  # noqa: E402

wo.LOG_PATH = Path(a.data) / "workflow" / "_overview-hub.log"
cfg = wg_core.load_config()
spec = json.loads(Path(a.events).read_text(encoding="utf-8"))
raw = Path(a.transcript).read_text(encoding="utf-8").splitlines(keepends=True)
tp = Path(a.data) / "t.jsonl"
sid = spec["sid"]
state = {"turn_seq": 1, "turn_prompts_seq": 1, "turn_intent": spec["intent"], "session": {"id": sid, "cwd": spec["cwd"]}}
has_tid = "tool_use_id" in inspect.signature(wo.on_edit).parameters
out = []
for ev in spec["events"]:
    tp.write_text("".join(raw[:ev["cut"]]) + "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in ev.get("insert") or []),
                  encoding="utf-8")
    rec = {"line": ev["line"], "kind": ev["kind"], "tool": ev.get("tool")}
    if ev["kind"] == "goal":
        pt._need_goal_after_tool(state, sid, "mcp__workflow-guardian__need_goal", ev["input"],
                                 {"tool_response": {}, "transcript_path": str(tp), "cwd": spec["cwd"]}, cfg)
    elif ev["kind"] == "read":
        rec["text"] = wo.on_read(state, sid, ev["tool"], ev["input"], spec["cwd"], str(tp), cfg, exit_code=ev["exit"])
    elif ev["kind"] == "edit":
        deny = None
        targets = wg_core.write_paths_from_tool(ev["tool"], ev["input"], spec["cwd"])
        rec["targets"] = len(targets)
        for t in targets:
            src = wg_core.write_sources_from_tool(ev["tool"], ev["input"], spec["cwd"]).get(t, ())
            deny = ng.edit_gate(sid, t, cfg, src, ev["input"].get("content") if ev["tool"] == "Write" else None)
            if deny:
                break
            kw = {"tool_use_id": ev["tid"]} if has_tid else {}
            _w, deny, _c = wo.on_edit(state, sid, t, str(tp), cfg, **kw)
            if deny:
                break
        rec["deny"] = deny
    out.append(rec)
Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"LOCATE_HINT_WORKER DONE events={len(out)}")

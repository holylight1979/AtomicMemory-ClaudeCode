"""closing_baseline.py — 收尾時間這一刀的砍前數字（只讀 004 實跑帳）。

做什麼：
  1. 計時帳（B-1/logs/_this_session/guard-hook_timing.jsonl kind=run）落在第一回合窗口（turns/B-1-t1.json _meta started～ended）的每筆
     hook：各事件次數與總毫秒、>500ms 的段（段名、毫秒、哪個事件）、每次 Stop 的段。
  2. 共用量尺 first_turn_breakdown.py --json 的輸出：PickOne／ReadingPath／第二意見的額外呼叫（token、送出到回完秒、到下一次送出秒）。
  3. 第二意見：transcript 裡 second_opinion_start／result 的 tool_use 次數、SecondOpinion 字樣行數。
怎麼跑：python -X utf8 closing_baseline.py <ftb.json> [run ...]（run 預設 2026-10-23-CCon-R1 2026-10-23-CCon-R2）
尾行：CLOSING_BASELINE DONE k=v …
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(os.environ.get("CB_BASE", r"C:\Users\holylight\.claude\workflow\inbox\wave2-kit\results"))
SEG_MS = 500


def window(run: str):
    meta = json.loads((BASE / run / "B-1" / "turns" / "B-1-t1.json").read_text(encoding="utf-8"))["_meta"]
    f = lambda s: datetime.fromisoformat(s).timestamp()
    return f(meta["started"]), f(meta["ended"])


def timing_rows(run: str):
    p = BASE / run / "B-1" / "logs" / "_this_session" / "guard-hook_timing.jsonl"
    if not p.exists():
        p = BASE / run / "B-1" / "logs" / "guard-hook_timing.jsonl"
    t0, t1 = window(run)
    out = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        r = json.loads(ln)
        at = datetime.fromisoformat(r["at"]).replace(tzinfo=None).timestamp()
        if r.get("kind") == "run" and t0 - 1 <= at <= t1 + 1:
            out.append(r)
    return out


def so_counts(run: str):
    n_call = n_line = 0
    for tp in (BASE / run / "B-1" / "transcript").glob("*.jsonl"):
        txt = tp.read_text(encoding="utf-8")
        n_call += txt.count('"name":"mcp__workflow-guardian__second_opinion_start"') + \
            txt.count('"name":"mcp__workflow-guardian__second_opinion_result"')
        n_line += sum(1 for ln in txt.splitlines() if "[Guardian:SecondOpinion]" in ln)
    return n_call, n_line


def main():
    runs = sys.argv[1:] or ["2026-10-23-CCon-R1", "2026-10-23-CCon-R2"]
    kv = {}
    for run in runs:
        rows = timing_rows(run)
        print(f"\n## {run}")
        by_ev = {}
        for r in rows:
            e = by_ev.setdefault(r["event"], [0, 0])
            e[0] += 1
            e[1] += r["total_ms"]
        print("| 事件 | 次數 | 總毫秒 |")
        print("|---|---|---|")
        for ev, (n, ms) in sorted(by_ev.items(), key=lambda x: -x[1][1]):
            print(f"| {ev} | {n} | {ms} |")
        big = [(r["event"], s, ms) for r in rows for s, ms in r["segments"] if ms > SEG_MS]
        print(f"\n>{SEG_MS}ms 的段：" + ("；".join(f"{e}「{s}」{ms}" for e, s, ms in big) or "無"))
        stops = [r for r in rows if r["event"] == "Stop"]
        for i, r in enumerate(stops):
            segs = "、".join(f"{s} {ms}" for s, ms in r["segments"] if ms >= 50)
            print(f"Stop#{i + 1} {r['at'][11:19]} total {r['total_ms']}ms ended_after={r.get('ended_after')}：{segs}")
        tag = run.rsplit("-", 1)[-1]
        n_call, n_line = so_counts(run)
        print(f"第二意見：start／result 呼叫 {n_call} 次、SecondOpinion 字樣行 {n_line}")
        kv[f"{tag}_stops"] = len(stops)
        kv[f"{tag}_stop_ms"] = sum(r["total_ms"] for r in stops)
        kv[f"{tag}_hook_ms"] = sum(r["total_ms"] for r in rows)
        kv[f"{tag}_big"] = len(big)
        kv[f"{tag}_so_calls"] = n_call
    print("CLOSING_BASELINE DONE " + " ".join(f"{k}={v}" for k, v in kv.items()))


if __name__ == "__main__":
    main()

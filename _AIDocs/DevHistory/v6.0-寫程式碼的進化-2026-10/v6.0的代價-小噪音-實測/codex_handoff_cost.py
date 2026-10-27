"""codex_handoff_cost.py — 從 Logs/codex-audit.log 算接續單自檢（handoff_review）在背景跑的次數、秒數、prompt 字數（唯讀）。
怎麼跑：python -X utf8 codex_handoff_cost.py [--log <codex-audit.log>] [--since 2026-10-01]；尾行 CODEX_HANDOFF DONE k=v …"""
import argparse, re
from datetime import datetime, timedelta
from pathlib import Path
ap = argparse.ArgumentParser()
ap.add_argument("--log", default=str(Path.home() / ".claude" / "Logs" / "codex-audit.log"))
ap.add_argument("--since", default="2026-10-01")
a = ap.parse_args()
lines = Path(a.log).read_text(encoding="utf-8", errors="replace").splitlines()
# 檔內只有時分秒；日期從檔尾往前推（時分秒倒退＝跨過午夜往前一天）。
PAT = re.compile(r"^\[(assessor|audit) (\d\d:\d\d:\d\d)\] (.*)$")
day = datetime.fromtimestamp(Path(a.log).stat().st_mtime).date()
prev = None
stamped = []
for ln in reversed(lines):
    m = PAT.match(ln)
    if not m:
        continue
    t = datetime.strptime(m.group(2), "%H:%M:%S").time()
    if prev is not None and t > prev:
        day -= timedelta(days=1)
    prev = t
    stamped.append((datetime.combine(day, t), m.group(1), m.group(3)))
stamped.reverse()
since = datetime.fromisoformat(a.since)
runs, cur = [], None
for ts, who, msg in stamped:
    if ts < since:
        continue
    m = re.match(r"Prompt built for (\w+) \(t\d+\): (\d+) chars", msg)
    if m:
        cur = {"type": m.group(1), "chars": int(m.group(2)), "start": None}
    elif msg.startswith("Running:") and cur:
        cur["start"] = ts
    elif msg.startswith("codex exec exit code") and cur and cur.get("start"):
        cur["secs"] = (ts - cur["start"]).total_seconds()
        runs.append(cur)
        cur = None
ho = [r for r in runs if r["type"] == "handoff_review"]
allt = {}
for r in runs:
    allt.setdefault(r["type"], []).append(r["secs"])
for k, v in sorted(allt.items()):
    print(f"{k}: {len(v)} 次，平均 {sum(v) / len(v):.0f} 秒，合計 {sum(v) / 60:.0f} 分")
n = len(ho)
print(f"CODEX_HANDOFF DONE runs={n} avg_s={(sum(r['secs'] for r in ho) / n if n else 0):.0f} "
      f"total_min={sum(r['secs'] for r in ho) / 60:.0f} avg_prompt_chars={(sum(r['chars'] for r in ho) / n if n else 0):.0f}")

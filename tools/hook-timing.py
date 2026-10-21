#!/usr/bin/env python3
"""hook-timing.py — hook 分段耗時量尺（唯讀）：每個事件跑了幾次、降級幾次、總耗時與各段耗時的中位數。

做什麼：讀 `Logs/guard-hook_timing.jsonl`（含輪替留下的 .1、.2；hooks/wg_hook_timing 每次 Stop／PostToolUse 結束寫一筆
kind=run，過上限 80% 降級時另寫一筆 kind=degraded，到上限 95% 還沒跑完的另寫一筆 kind=overrun）。中位數只算 kind=run；段落照第一次出現的順序列。
只讀這台機器的帳（遙測是各機本地衍生）；讀了哪個檔、幾筆都印出來，沒帳就印「沒有計時帳」，不印成 0。

怎麼跑：
  python tools/hook-timing.py                  # 近 7 天、全部事件
  python tools/hook-timing.py --event Stop --days 30 --json
  python tools/hook-timing.py --logs <Logs 目錄>   # 讀別處的帳（測試、別台機器的副本）
尾行：`HOOK_TIMING DONE events=<有帳的事件數> runs=<筆數> degraded=<降級次數> overrun=<快逾時次數>`；exit 0（沒資料也 0）。
完整參數以 --help 為準。
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

CODE_DIR = Path(__file__).resolve().parent.parent   # 程式碼根（本檔所在的樹）
if str(CODE_DIR / "hooks") not in sys.path:
    sys.path.insert(0, str(CODE_DIR / "hooks"))

from wg_core import CLAUDE_DIR  # noqa: E402
from wg_hook_timing import GUARD  # noqa: E402


def _read_jsonl(p: Path) -> List[Dict[str, Any]]:
    """一行一筆；壞行跳過並計數印 stderr（不靜默吞掉）。"""
    rows, bad = [], 0
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    for line in lines:
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            bad += 1
            continue
        if isinstance(rec, dict):
            rows.append(rec)
    if bad:
        print(f"[hook-timing] {p.name} 有 {bad} 行讀不懂，已跳過", file=sys.stderr)
    return rows


def _at(rec: Dict[str, Any]) -> datetime:
    try:
        t = datetime.fromisoformat(str(rec.get("at") or "").replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return t if t.tzinfo else t.astimezone()


def collect(logs: Path, days: int, event: str = "") -> Dict[str, Any]:
    base = logs / f"guard-{GUARD}.jsonl"
    files = [p for p in (base, base.with_suffix(".jsonl.1"), base.with_suffix(".jsonl.2")) if p.exists()]
    cut = datetime.now().astimezone() - timedelta(days=days)
    recs = [r for p in files for r in _read_jsonl(p) if _at(r) >= cut and (not event or r.get("event") == event)]
    per: Dict[str, Dict[str, Any]] = {}
    for r in recs:
        ev = str(r.get("event") or "?")
        s = per.setdefault(ev, {"event": ev, "runs": 0, "degraded": 0, "overrun": 0, "totals": [], "segments": {},
                                "degraded_at": {}, "stuck_after": {}, "limit_s": None, "limit_src": ""})
        if r.get("kind") == "overrun":
            s["overrun"] += 1
            at = str(r.get("stuck_after") or "?")
            s["stuck_after"][at] = s["stuck_after"].get(at, 0) + 1
            continue
        if r.get("kind") == "degraded":
            s["degraded"] += 1
            at = str(r.get("degraded_at") or "?")
            s["degraded_at"][at] = s["degraded_at"].get(at, 0) + 1
            continue
        if r.get("kind") != "run":
            continue
        s["runs"] += 1
        s["totals"].append(int(r.get("total_ms") or 0))
        s["limit_s"], s["limit_src"] = r.get("limit_s"), r.get("limit_src") or ""
        for name, ms in r.get("segments") or []:
            s["segments"].setdefault(str(name), []).append(int(ms or 0))
    rows = []
    for s in sorted(per.values(), key=lambda s: s["event"]):
        t = s.pop("totals")
        s["total_median_ms"] = int(statistics.median(t)) if t else None
        s["total_max_ms"] = max(t) if t else None
        s["segments"] = [{"name": n, "n": len(v), "median_ms": int(statistics.median(v)), "max_ms": max(v)}
                         for n, v in s["segments"].items()]
        rows.append(s)
    return {"days": days, "files": [str(p) for p in files], "records": len(recs), "events": rows,
            "totals": {"events": sum(1 for s in rows if s["runs"]), "runs": sum(s["runs"] for s in rows),
                       "degraded": sum(s["degraded"] for s in rows), "overrun": sum(s["overrun"] for s in rows)}}


def main(argv: List[str] = None) -> int:
    ap = argparse.ArgumentParser(description="hook 分段耗時量尺（唯讀；Logs/guard-hook_timing.jsonl）")
    ap.add_argument("--days", type=int, default=7, help="只看近幾天（預設 7）")
    ap.add_argument("--logs", default=str(CLAUDE_DIR / "Logs"), help="Logs 目錄（預設資料根的 Logs）")
    ap.add_argument("--event", default="", help="只看這個事件（Stop、PostToolUse）")
    ap.add_argument("--json", action="store_true", help="輸出 JSON（尾行仍是 DONE 行）")
    args = ap.parse_args(argv)
    res = collect(Path(args.logs), args.days, args.event)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif not res["records"]:
        print(f"近 {args.days} 天沒有計時帳（{Path(args.logs) / f'guard-{GUARD}.jsonl'}）")
    else:
        print(f"近 {args.days} 天 hook 計時帳（{'、'.join(res['files'])}，{res['records']} 筆）：")
        for s in res["events"]:
            limit = f"上限 {s['limit_s']:g} 秒（{s['limit_src']}）" if s["limit_s"] else "上限不明"
            total = (f"總耗時中位數 {s['total_median_ms']}ms、最長 {s['total_max_ms']}ms" if s["runs"] else "沒有跑完的紀錄")
            print(f"- {s['event']}：跑 {s['runs']} 次｜降級 {s['degraded']} 次｜快逾時 {s['overrun']} 次｜{total}｜{limit}")
            if s["degraded_at"]:
                print("  降級時跑到：" + "、".join(f"{k}×{v}" for k, v in s["degraded_at"].items()))
            if s["stuck_after"]:
                print("  快逾時卡在這段之後：" + "、".join(f"{k}×{v}" for k, v in s["stuck_after"].items()))
            for g in s["segments"]:
                print(f"  · {g['name']}：中位數 {g['median_ms']}ms、最長 {g['max_ms']}ms（{g['n']} 筆）")
    t = res["totals"]
    print(f"HOOK_TIMING DONE events={t['events']} runs={t['runs']} degraded={t['degraded']} overrun={t['overrun']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

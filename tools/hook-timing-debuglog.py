#!/usr/bin/env python3
"""hook-timing-debuglog.py — 讀官方偵錯日誌，量每支 hook 命令的全程耗時（唯讀）。

做什麼：官方偵錯日誌（Claude Code v2.1.296+）每支命令 hook 結束留一行
`Hooks: <事件>[:<比對值>] [<命令>] finished with status N (<ms>ms)`；本工具抽出這行，
按「事件 × handler」聚合次數、p50、p95、最大。這個耗時含行程啟動（直譯器＋import），
而自家 `tools/hook-timing.py` 的帳從 Python 已跑起來才開始算；兩者中位數相減 ≈「Python 啟動前的那段」。
只對得上守門開時有帳的事件（見 hook-timing.py）；沒帳的事件只列官方耗時，不印差值。
格式不是正式契約：認不出的 Hooks: 行、沒有耗時的 completed 行、cancelled 等收尾，都計數印 stderr，不靜默跳過。
`timed out after Nms` 算進耗時。

怎麼跑：
  python tools/hook-timing-debuglog.py                       # 讀 ~/.claude/debug/ 最新一份
  python tools/hook-timing-debuglog.py <日誌...>              # 指定一或多份（--debug-file 產的）
  python tools/hook-timing-debuglog.py --json <日誌>
產日誌：`claude -p "say ok" --debug-file <path>`（或互動 session 以 `claude --debug-file <path>` 開）。
尾行：`HOOK_TIMING_DEBUGLOG DONE hooks=<hook 筆數> p50_ms=<全體> p95_ms=<全體>`；沒資料 hooks=0 且 exit 0。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
DEBUG_DIR = Path.home() / ".claude" / "debug"

LINE = re.compile(r"Hooks: (?P<event>[A-Za-z]+)(?::(?P<match>\S*))? \[(?P<cmd>.*)\] (?P<tail>.*)$")
DUR = re.compile(r"(?:finished with status -?\d+ \(|timed out after )(\d+)ms")
RUNPY = re.compile(r"hooks/([\w.-]+\.py)")
SCRIPT = re.compile(r"([\w.-]+\.py)\"?(?:\s+(\S+))?\s*$")


def handler_of(cmd: str) -> str:
    """命令字串 → 短名：runpy 包的取腳本名；run-bash-hidden 帶上被轉跑的檔；其餘取前 60 字。"""
    m = RUNPY.search(cmd.replace("\\", "/"))
    if m and not m.group(1).startswith("run-bash-hidden"):
        return m.group(1)
    m = SCRIPT.search(cmd.replace("\\", "/").rsplit("/", 1)[-1])
    if m:
        return m.group(1) + (f" {m.group(2)}" if m.group(2) else "")
    return cmd[:60]


def pct(v: List[int], p: float) -> int:
    s = sorted(v)
    return s[max(0, math.ceil(p / 100 * len(s)) - 1)]


def parse(paths: List[Path]) -> Dict[str, Any]:
    groups: Dict[tuple, List[int]] = {}
    skipped = {"unknown": 0, "no_duration": 0}
    for p in paths:
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if "Hooks:" not in line:
                continue
            m = LINE.search(line)
            if not m:
                continue                       # 不是 hook 結束行（例如 Hooks: 的其他訊息）
            d = DUR.search(m.group("tail"))
            if d:
                groups.setdefault((m.group("event"), handler_of(m.group("cmd"))), []).append(int(d.group(1)))
            elif m.group("tail").startswith("completed with status"):
                skipped["no_duration"] += 1
            else:
                skipped["unknown"] += 1
    return {"groups": groups, "skipped": skipped}


def guard_medians() -> Dict[str, Optional[int]]:
    """自家 hook-timing 帳的各事件總耗時中位數（近 7 天）；載入失敗或沒帳回空，並印 stderr。"""
    try:
        spec = importlib.util.spec_from_file_location("hook_timing_tool", HERE / "hook-timing.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        res = mod.collect(mod.CLAUDE_DIR / "Logs", 7)
    except Exception as e:                      # noqa: BLE001  對照是附加資訊，失敗要出訊號但不擋主量測
        print(f"[hook-timing-debuglog] 讀不到自家計時帳，略過對照：{e!r}", file=sys.stderr)
        return {}
    return {s["event"]: s["total_median_ms"] for s in res["events"] if s["runs"]}


def main(argv: List[str] = None) -> int:
    ap = argparse.ArgumentParser(description="官方偵錯日誌 hook 耗時量尺（唯讀；Hooks: 行）")
    ap.add_argument("logs", nargs="*", help=f"偵錯日誌檔（預設 {DEBUG_DIR} 最新一份）")
    ap.add_argument("--json", action="store_true", help="輸出 JSON（尾行仍是 DONE 行）")
    args = ap.parse_args(argv)
    paths = [Path(x) for x in args.logs]
    if not paths and DEBUG_DIR.is_dir():
        found = sorted(DEBUG_DIR.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)[:1]
        paths = found
    paths = [p for p in paths if p.is_file()]
    if not paths:
        print(f"沒有偵錯日誌可讀（{DEBUG_DIR} 無 *.txt，也沒指定檔）；用 claude --debug-file <path> 產一份")
        print("HOOK_TIMING_DEBUGLOG DONE hooks=0 p50_ms=0 p95_ms=0")
        return 0
    res = parse(paths)
    for k, n in res["skipped"].items():
        if n:
            print(f"[hook-timing-debuglog] {n} 行 {k}（認不出格式或無耗時），未計入", file=sys.stderr)
    guard = guard_medians()
    rows, allv = [], []
    for (ev, h), v in sorted(res["groups"].items()):
        allv += v
        rows.append({"event": ev, "handler": h, "n": len(v), "p50_ms": int(statistics.median(v)),
                     "p95_ms": pct(v, 95), "max_ms": max(v)})
    # 事件牆鐘：同事件平行執行，取該事件各 handler 中位數的最大值；減自家帳總耗時 ≈ Python 啟動前那段
    startup = {}
    for ev, g in guard.items():
        evp = [r["p50_ms"] for r in rows if r["event"] == ev]
        if evp and g is not None:
            startup[ev] = {"debuglog_slowest_p50_ms": max(evp), "guard_total_median_ms": g, "gap_ms": max(evp) - g}
    p50, p95 = (int(statistics.median(allv)), pct(allv, 95)) if allv else (0, 0)
    if args.json:
        print(json.dumps({"files": [str(p) for p in paths], "rows": rows, "startup_gap": startup,
                          "skipped": res["skipped"]}, ensure_ascii=False, indent=2))
    else:
        print(f"讀 {len(paths)} 份日誌：{'、'.join(str(p) for p in paths)}")
        print(f"{'事件':<18}{'handler':<42}{'次數':>5}{'p50':>8}{'p95':>8}{'最大':>8}  (ms)")
        for r in rows:
            print(f"{r['event']:<18}{r['handler']:<42}{r['n']:>5}{r['p50_ms']:>8}{r['p95_ms']:>8}{r['max_ms']:>8}")
        if startup:
            print("與自家 hook-timing 帳對照（官方最慢 handler 中位數 − 自家近 7 天總耗時中位數 ≈ Python 啟動前的那段；兩邊場次不同，日誌越少越粗）：")
            for ev, s in startup.items():
                print(f"- {ev}：官方 {s['debuglog_slowest_p50_ms']}ms、自家 {s['guard_total_median_ms']}ms、差 {s['gap_ms']}ms")
        else:
            print("自家 hook-timing 帳沒有可對的事件（守門關時沒帳），只列官方耗時")
    print(f"HOOK_TIMING_DEBUGLOG DONE hooks={len(allv)} p50_ms={p50} p95_ms={p95}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

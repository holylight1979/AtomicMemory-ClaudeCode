#!/usr/bin/env python3
"""entry-stats.py — 切入點留帳統計（唯讀）：每個切入點問了幾次、送了幾張判準卡、截斷幾次、AI 回應各型幾筆。

做什麼：讀 `Logs/guard-entry.jsonl`（hooks/wg_entrypoint.entry_note 每次問寫一筆），回應型照各閘自己的留帳推
（登錄表 workflow/entrypoints.json 每列的 responses，判法在 hooks/wg_entrypoint.resolve_responses）。
第二波判分與 G15 週彙總讀它。只讀不寫。

怎麼跑：
  python tools/entry-stats.py                 # 近 7 天
  python tools/entry-stats.py --days 30 --json
  python tools/entry-stats.py --asks --json        # 另列每次問一筆（at、session、turn_seq、entry、path、cards、truncated、
                                                   # response、response_by、with），回應型就是 resolve_responses 那一支判的
  python tools/entry-stats.py --logs <Logs 目錄>   # 讀別處的帳（測試、別台機器的副本）
尾行：`ENTRY_STATS DONE entries=<有問過的切入點數> asks=<問幾次> cards=<送卡張數> truncated=<截斷次數>`，給了 --asks 再加
`asks_listed=<列了幾筆>`；exit 0（沒資料也 0）。
完整參數以 --help 為準。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

CODE_DIR = Path(__file__).resolve().parent.parent   # 程式碼根（本檔所在的樹）
if str(CODE_DIR / "hooks") not in sys.path:
    sys.path.insert(0, str(CODE_DIR / "hooks"))

import wg_entrypoint as ep  # noqa: E402
from wg_core import CLAUDE_DIR  # noqa: E402


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
        print(f"[entry-stats] {p.name} 有 {bad} 行讀不懂，已跳過", file=sys.stderr)
    return rows


def collect(logs: Path, days: int, registry: Dict[str, Any]) -> Dict[str, Any]:
    cut = datetime.now().astimezone() - timedelta(days=days)
    asks = [a for a in _read_jsonl(logs / f"guard-{ep.LEDGER}.jsonl") if a.get("event") == "ask" and ep._ts(a) >= cut]
    guards = {str(rule.get("guard")) for r in registry["entrypoints"] for rule in r.get("responses") or []}
    resolved = ep.resolve_responses(asks, {g: _read_jsonl(logs / f"guard-{g}.jsonl") for g in guards}, registry)
    names = {str(r["id"]): r.get("name", "") for r in registry["entrypoints"]}
    per: Dict[str, Dict[str, Any]] = {}
    for a in resolved:
        eid = str(a.get("entry"))
        s = per.setdefault(eid, {"id": eid, "name": names.get(eid, "（登錄表沒有這個代號）"), "asks": 0,
                                 "asks_with_cards": 0, "cards": 0, "truncated": 0,
                                 "responses": {t: 0 for t in ep.RESPONSE_TYPES}, "with": Counter(), "paths": Counter()})
        s["asks"] += 1
        s["cards"] += len(a.get("cards") or [])
        s["asks_with_cards"] += 1 if a.get("cards") else 0
        s["truncated"] += 1 if a.get("truncated") else 0
        s["responses"][a["response"]] += 1
        s["with"].update(a.get("with") or [])
        s["paths"].update([str(a.get("path", ""))])
    order = {str(r["id"]): i for i, r in enumerate(registry["entrypoints"])}
    rows = sorted(per.values(), key=lambda s: order.get(s["id"], len(order)))
    for s in rows:
        s["with"], s["paths"] = dict(s["with"]), dict(s["paths"])
    asks_out = [{"at": a.get("at"), "session": ep._event_session(a), "turn_seq": a.get("turn_seq"), "entry": str(a.get("entry")),
                 "path": a.get("path", ""), "cards": list(a.get("cards") or []), "truncated": bool(a.get("truncated")),
                 "response": a["response"], "response_by": a["response_by"], "with": list(a.get("with") or [])}
                for a in resolved]
    return {"days": days, "logs": str(logs), "entries": rows, "asks": asks_out,
            "totals": {"entries": len(rows), "asks": sum(s["asks"] for s in rows),
                       "cards": sum(s["cards"] for s in rows), "truncated": sum(s["truncated"] for s in rows)}}


def main(argv: List[str] = None) -> int:
    ap = argparse.ArgumentParser(description="切入點留帳統計（唯讀；Logs/guard-entry.jsonl＋各閘留帳推回應型）")
    ap.add_argument("--days", type=int, default=7, help="只看近幾天（預設 7）")
    ap.add_argument("--logs", default=str(CLAUDE_DIR / "Logs"), help="Logs 目錄（預設資料根的 Logs）")
    ap.add_argument("--registry", default=None, help="登錄表路徑（預設程式碼根的 workflow/entrypoints.json）")
    ap.add_argument("--json", action="store_true", help="輸出 JSON（尾行仍是 DONE 行）")
    ap.add_argument("--asks", action="store_true", help="另列每次問一筆（JSON 多 asks 欄；尾行多 asks_listed=）")
    args = ap.parse_args(argv)
    registry = ep.load_registry(Path(args.registry) if args.registry else None)
    res = collect(Path(args.logs), args.days, registry)
    asks = res.pop("asks")
    if args.asks:
        res["asks"] = asks
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif not res["entries"]:
        print(f"近 {args.days} 天沒有切入點留帳（{res['logs']}）")
    else:
        print(f"近 {args.days} 天切入點留帳（{res['logs']}）：")
        for s in res["entries"]:
            resp = " ".join(f"{t} {n}" for t, n in s["responses"].items())
            line = (f"- {s['id']} {s['name']}：問 {s['asks']}｜有卡 {s['asks_with_cards']}（送 {s['cards']} 張）｜"
                    f"截斷 {s['truncated']}｜{resp}")
            if s["with"]:
                line += "｜同一問句也認出：" + "、".join(f"{k}×{v}" for k, v in s["with"].items())
            print(line)
    if args.asks and not args.json and asks:
        print("逐筆：")
        for a in asks:
            cards = "、".join(a["cards"]) or "無"
            turn = "?" if a["turn_seq"] is None else a["turn_seq"]
            by = f"（{a['response_by']}）" if a["response_by"] else ""
            line = (f"  · {a['at']} session {a['session']} 回合 {turn} {a['entry']} {a['path']}｜卡：{cards}"
                    f"{'（截斷）' if a['truncated'] else ''}｜回應 {a['response']}{by}")
            if a["with"]:
                line += "｜同句也認出 " + "、".join(a["with"])
            print(line)
    t = res["totals"]
    tail = f"ENTRY_STATS DONE entries={t['entries']} asks={t['asks']} cards={t['cards']} truncated={t['truncated']}"
    print(tail + (f" asks_listed={len(asks)}" if args.asks else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""text-score-weekly.py：讀 text-score 的留帳（Logs/guard-text_score.jsonl），出每份規格的週彙總（G15）。

做什麼：最近 N 個 ISO 週（含本週），每份規格列：評了幾則、裁判不在幾則、實際回答的裁判各幾則（每台裁判不同，過率要分得出來自誰；
  舊紀錄沒有這欄記「沒記」）、種類各幾則（final_reply／docs 是收尾自動評，manual 是手動）；每一條的每週過率（是 ÷（是＋否），
  不適用另計）、最近兩週有資料的趨勢（百分點）、期間作廢數。規格雜湊不只一版時標出來（條目可能改過，過率不完全可比）。
  只讀不寫；壞掉的留帳行跳過並計數。
怎麼跑：
  python tools/text-score-weekly.py                  # 最近 4 週，Markdown 印到 stdout
  python tools/text-score-weekly.py --weeks 8 --json # 一行 JSON（再接尾行）
  python tools/text-score-weekly.py --log <檔>       # 讀別的留帳檔
尾行：`TEXT_SCORE_WEEKLY DONE weeks=<n> records=<n> unscored=<n> void=<n> bad=<n>`（數字是尺不是判決）。完整參數以 --help 為準。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CODE_DIR = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("text_score", CODE_DIR / "tools" / "text-score.py")
TS = importlib.util.module_from_spec(_spec)
sys.modules["text_score"] = TS   # dataclass 解析型別註記要找得到模組
_spec.loader.exec_module(TS)
LOG_PATH = TS.LOG_PATH   # 留帳位置只在 text-score.py 定義一次

COUNTED = ("是", "否", "不適用", "作廢", "未評")


def week_label(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def recent_weeks(n: int, today: date) -> List[str]:
    return [week_label(today - timedelta(weeks=i)) for i in range(n - 1, -1, -1)]


def load_records(path: Path) -> Tuple[List[Dict[str, Any]], int]:
    if not path.exists():
        return [], 0
    records, bad = [], 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
            datetime.fromisoformat(rec["ts"])
            items = rec.get("items")
            usable = (isinstance(rec.get("spec"), str) and isinstance(items, list)
                      and all(isinstance(it, dict) and isinstance(it.get("id"), str) for it in items))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError, AttributeError):
            usable = False
        if not usable:
            bad += 1
            continue
        records.append(rec)
    return records, bad


def item_key(it: Dict[str, Any]) -> str:
    return it.get("verdict") if it.get("status") == "判定" else it.get("status", "未評")


def summarize(records: List[Dict[str, Any]], weeks: List[str]) -> Dict[str, Any]:
    specs: Dict[str, Dict[str, Any]] = {}
    for rec in records:
        wk = week_label(datetime.fromisoformat(rec["ts"]).date())
        if wk not in weeks:
            continue
        s = specs.setdefault(rec["spec"], {"records": 0, "unscored": 0, "shas": set(), "order": [],
                                           "judges": Counter(), "kinds": Counter(),
                                           "items": defaultdict(lambda: defaultdict(lambda: dict.fromkeys(COUNTED, 0)))})
        s["records"] += 1
        s["unscored"] += rec.get("overall") == "未評"
        s["shas"].add(rec.get("spec_sha"))
        used = rec.get("models_used")
        s["judges"].update([str(m) for m in used] if isinstance(used, list) and used
                           else ["沒回答" if isinstance(used, list) else "沒記"])
        s["kinds"][str(rec.get("kind") or "沒記")] += 1
        for it in rec["items"]:
            key = item_key(it)
            if key in COUNTED:
                s["items"][it["id"]][wk][key] += 1
            if it["id"] not in s["order"]:
                s["order"].append(it["id"])
    out: Dict[str, Any] = {}
    for code, s in specs.items():
        rows = []
        for iid in s["order"]:
            per_week = s["items"][iid]
            rates = [_rate(per_week[wk]) if wk in per_week else None for wk in weeks]
            rows.append({"id": iid, "rates": rates, "trend": _trend(rates),
                         "void": sum(c["作廢"] for c in per_week.values()),
                         "counts": {k: sum(c[k] for c in per_week.values()) for k in COUNTED}})
        out[code] = {"records": s["records"], "unscored": s["unscored"], "spec_versions": len(s["shas"]),
                     "judges": dict(s["judges"].most_common()), "kinds": dict(s["kinds"].most_common()), "items": rows}
    return out


def _rate(c: Dict[str, int]) -> Optional[float]:
    judged = c["是"] + c["否"]
    return round(c["是"] / judged, 3) if judged else None


def _trend(rates: List[Optional[float]]) -> Optional[int]:
    """最近兩個有過率的週相減（百分點）；不到兩週回 None。"""
    have = [r for r in rates if r is not None]
    return round((have[-1] - have[-2]) * 100) if len(have) >= 2 else None


def render(summary: Dict[str, Any], weeks: List[str]) -> str:
    if not summary:
        return f"text-score 週彙總（{weeks[0]}～{weeks[-1]}）：期間沒有評分紀錄"
    lines = [f"# text-score 週彙總（{weeks[0]}～{weeks[-1]}）", "", "過率＝是 ÷（是＋否）；不適用、作廢、未評不進分母。"]
    for code, s in summary.items():
        lines += ["", f"## {code}（{s['records']} 則，裁判不在 {s['unscored']} 則）", "",
                  "裁判（實際回答）：" + "、".join(f"{k} {v}" for k, v in s["judges"].items())
                  + "｜種類：" + "、".join(f"{k} {v}" for k, v in s["kinds"].items())]
        if s["spec_versions"] > 1:
            lines.append(f"> 期間規格改過（{s['spec_versions']} 個版本），各週過率不完全可比")
        lines += ["", "| 條目 | " + " | ".join(weeks) + " | 趨勢 | 作廢 | 是／否／不適用／未評 |",
                  "|---|" + "---|" * len(weeks) + "---|---|---|"]
        for row in s["items"]:
            rates = " | ".join("—" if r is None else f"{round(r * 100)}%" for r in row["rates"])
            t = row["trend"]
            trend = "—" if t is None else ("→0" if t == 0 else (f"↑{t}" if t > 0 else f"↓{-t}"))
            c = row["counts"]
            lines.append(f"| {row['id']} | {rates} | {trend} | {row['void']} | "
                         f"{c['是']}／{c['否']}／{c['不適用']}／{c['未評']} |")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="text-score 留帳的週彙總：每條過率、趨勢、作廢數")
    ap.add_argument("--weeks", type=int, default=4, help="看最近幾個 ISO 週（含本週），預設 4")
    ap.add_argument("--log", default=str(LOG_PATH), help="留帳檔（預設資料根的 Logs/guard-text_score.jsonl）")
    ap.add_argument("--json", action="store_true", help="改印一行 JSON，再接尾行")
    args = ap.parse_args(argv)

    weeks = recent_weeks(max(args.weeks, 1), date.today())
    records, bad = load_records(Path(args.log))
    if bad:
        print(f"text-score-weekly：{args.log} 有 {bad} 行讀不懂，已跳過", file=sys.stderr)
    summary = summarize(records, weeks)
    print(json.dumps({"weeks": weeks, "specs": summary}, ensure_ascii=False) if args.json else render(summary, weeks))
    in_range = sum(s["records"] for s in summary.values())
    print(f"TEXT_SCORE_WEEKLY DONE weeks={len(weeks)} records={in_range} "
          f"unscored={sum(s['unscored'] for s in summary.values())} "
          f"void={sum(r['void'] for s in summary.values() for r in s['items'])} bad={bad}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

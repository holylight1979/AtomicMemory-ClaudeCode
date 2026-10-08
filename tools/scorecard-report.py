#!/usr/bin/env python3
"""scorecard-report.py：把每 session 的 scorecard 行彙整成報表，挑「下一張該寫的卡」候選（G0 量尺、G5 回路）。

做什麼：讀 `workflow/scorecard/*.jsonl`（hooks/wg_scorecard.py 每 session 收尾 append 一行），算 S1 四週中位數當基線、
找連續低於基線的部位、按編輯次數與缺卡證據排出前 N 個部位當候選卡；寫
`workflow/health-reports/scorecard-<yyyymmdd>.md` 與 `workflow/scorecard/candidates.json`（M4 project-smells builtin 讀它）。
回路單向：本工具讀 scorecard 行、寫候選；wg_scorecard 不讀候選。

怎麼跑：
  python ~/.claude/tools/scorecard-report.py            # 預設 baseline 4 週、top 5
  python ~/.claude/tools/scorecard-report.py --weeks 4 --top-n 5 --json
尾行：`SCORECARD_REPORT DONE lines=<n> candidates=<n>`；exit 0（沒資料也 0，報表寫「尚無資料」）。
設定：`workflow/config.json` 的 `scorecard` 段（scorecard_baseline_weeks 4、scorecard_top_n 5）。完整參數以 --help 為準。
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

CLAUDE_DIR = Path(__file__).resolve().parent.parent
WORKFLOW_DIR = CLAUDE_DIR / "workflow"
SCORECARD_DIR = WORKFLOW_DIR / "scorecard"
REPORT_DIR = WORKFLOW_DIR / "health-reports"
CONFIG_PATH = WORKFLOW_DIR / "config.json"
DEFAULTS = {"scorecard_baseline_weeks": 4, "scorecard_top_n": 5}
KEEP_REPORTS = 8
MIN_SESSIONS_FOR_BELOW = 2


def load_cfg() -> Dict[str, Any]:
    out = dict(DEFAULTS)
    try:
        sec = json.loads(CONFIG_PATH.read_text(encoding="utf-8")).get("scorecard") or {}
    except FileNotFoundError:
        return out
    except (OSError, ValueError) as e:
        print(f"[scorecard-report] config.json 讀不出來，用預設值：{e}", file=sys.stderr)
        return out
    for k in out:
        if sec.get(k) is not None:
            out[k] = sec[k]
    return out


def _parse_at(s: Any) -> Optional[datetime]:
    try:
        return datetime.strptime(str(s)[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None


def load_months(scorecard_dir: Path, weeks: int, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """最近 weeks 週內的 scorecard 行（壞行跳過並計數到 stderr），依時間排序。"""
    now = now or datetime.now()
    cutoff = now - timedelta(weeks=int(weeks))
    rows: List[Dict[str, Any]] = []
    bad = 0
    for p in sorted(scorecard_dir.glob("*.jsonl")) if scorecard_dir.is_dir() else []:
        for raw in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if not raw.strip():
                continue
            try:
                d = json.loads(raw)
            except ValueError:
                bad += 1
                continue
            at = _parse_at(d.get("at")) if isinstance(d, dict) else None
            if at is None:
                bad += 1
                continue
            if at >= cutoff:
                d["_at"] = at
                rows.append(d)
    if bad:
        print(f"[scorecard-report] 跳過 {bad} 行壞資料", file=sys.stderr)
    rows.sort(key=lambda d: d["_at"])
    return rows


def baseline(lines: List[Dict[str, Any]], key: str = "s1") -> Optional[float]:
    """S1 的中位數（忽略 None）；沒資料 → None。"""
    vals = [float(d[key]) for d in lines if isinstance(d.get(key), (int, float))]
    return round(statistics.median(vals), 3) if vals else None


def recent_value(lines: List[Dict[str, Any]], days: int = 7, key: str = "s1",
                 now: Optional[datetime] = None) -> Optional[float]:
    now = now or datetime.now()
    recent = [d for d in lines if d["_at"] >= now - timedelta(days=days)]
    return baseline(recent, key)


def _part_stats(lines: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """按 `<root>|<part>` 聚合：sessions（有改的 session 數）、edits、reads_before_edit、located、no_read。"""
    stats: Dict[str, Dict[str, Any]] = {}
    for d in lines:
        for p in d.get("parts") or []:
            if not isinstance(p, dict) or not p.get("key"):
                continue
            s = stats.setdefault(p["key"], {"key": p["key"], "root": p.get("root", ""), "part": p.get("part", ""),
                                            "sessions": 0, "edits": 0, "read_sessions": 0, "located_sessions": 0,
                                            "card_read_sessions": 0, "injected_sessions": 0})
            s["injected_sessions"] += 1
            if p.get("card_read"):
                s["card_read_sessions"] += 1
            if int(p.get("edits", 0) or 0) <= 0:
                continue
            s["sessions"] += 1
            s["edits"] += int(p.get("edits", 0) or 0)
            if int(p.get("reads", 0) or 0) > 0:
                s["read_sessions"] += 1
            if p.get("located"):
                s["located_sessions"] += 1
    for s in stats.values():
        s["s1"] = round(s["read_sessions"] / s["sessions"], 3) if s["sessions"] else None
        s["s3"] = round(s["located_sessions"] / s["sessions"], 3) if s["sessions"] else None
    return stats


def below_baseline_parts(lines: List[Dict[str, Any]], base: Optional[float]) -> List[Dict[str, Any]]:
    """有改 ≥2 個 session 且部位自己的 S1 低於基線的部位（基線 None → []）。"""
    if base is None:
        return []
    out = [s for s in _part_stats(lines).values()
           if s["sessions"] >= MIN_SESSIONS_FOR_BELOW and s["s1"] is not None and s["s1"] < base]
    out.sort(key=lambda s: (s["s1"], -s["edits"], s["part"]))
    return out


def next_card_candidates(lines: List[Dict[str, Any]], top_n: int = 5) -> List[Dict[str, Any]]:
    """下一張該寫的卡：改得多、卻沒讀卡／沒交定位三行的部位排前；每筆附理由。"""
    out: List[Dict[str, Any]] = []
    for s in _part_stats(lines).values():
        if s["sessions"] <= 0:
            continue
        no_read = s["sessions"] - s["read_sessions"]
        no_locate = s["sessions"] - s["located_sessions"]
        score = s["edits"] * (1 + no_read + no_locate)
        reason = f"改 {s['edits']} 次／{s['sessions']} session；沒讀檔 {no_read}、沒交定位 {no_locate}、讀過卡 {s['card_read_sessions']}"
        out.append({"key": s["key"], "root": s["root"], "part": s["part"], "edits": s["edits"],
                    "sessions": s["sessions"], "score": score, "reason": reason})
    out.sort(key=lambda c: (-c["score"], -c["edits"], c["part"]))
    return out[:int(top_n)]


def build(lines: List[Dict[str, Any]], weeks: int, top_n: int, now: Optional[datetime] = None) -> Dict[str, Any]:
    now = now or datetime.now()
    base = baseline(lines)
    return {
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%S"), "weeks": int(weeks), "lines": len(lines),
        "baseline_s1": base, "recent_s1": recent_value(lines, now=now),
        "baseline_s3": baseline(lines, "s3"), "baseline_s5": baseline(lines, "s5"),
        "below_baseline": [{k: v for k, v in s.items()} for s in below_baseline_parts(lines, base)],
        "top": next_card_candidates(lines, top_n),
    }


def render_report(r: Dict[str, Any]) -> str:
    fmt = lambda v: "無" if v is None else f"{v:.2f}"  # noqa: E731
    lines = [f"# scorecard 報表 {r['generated_at']}", "",
             f"- 視窗：{r['weeks']} 週，{r['lines']} 個 session 有量",
             f"- 基線（中位數）：S1 {fmt(r['baseline_s1'])}／S3 {fmt(r['baseline_s3'])}／S5 {fmt(r['baseline_s5'])}；近 7 天 S1 {fmt(r['recent_s1'])}",
             "", f"## 低於基線的部位（{len(r['below_baseline'])}）"]
    lines += [f"- {s['part']}（{s['root']}）：S1 {fmt(s['s1'])}，改 {s['edits']} 次／{s['sessions']} session → 建議把導讀卡升級"
              for s in r["below_baseline"]] or ["- ✓ 無"]
    lines += ["", f"## 下一張該寫的卡（前 {len(r['top'])}）"]
    lines += [f"{i}. {c['part']}（{c['root']}）：{c['reason']}" for i, c in enumerate(r["top"], 1)] or ["- 尚無資料"]
    return "\n".join(lines) + "\n"


def write_outputs(r: Dict[str, Any], report_dir: Path, scorecard_dir: Path) -> Dict[str, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    scorecard_dir.mkdir(parents=True, exist_ok=True)
    day = r["generated_at"][:10].replace("-", "")
    report = report_dir / f"scorecard-{day}.md"
    report.write_text(render_report(r), encoding="utf-8", newline="\n")
    cand = scorecard_dir / "candidates.json"
    cand.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    for old in sorted(report_dir.glob("scorecard-*.md"))[:-KEEP_REPORTS]:
        old.unlink(missing_ok=True)
    return {"report": report, "candidates": cand}


def main(argv=None) -> int:
    cfg = load_cfg()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--weeks", type=int, default=int(cfg["scorecard_baseline_weeks"]))
    ap.add_argument("--top-n", type=int, default=int(cfg["scorecard_top_n"]))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    lines = load_months(SCORECARD_DIR, args.weeks)
    r = build(lines, args.weeks, args.top_n)
    paths = write_outputs(r, REPORT_DIR, SCORECARD_DIR)
    if args.json:
        print(json.dumps({**r, "paths": {k: str(v) for k, v in paths.items()}}, ensure_ascii=False, indent=1))
    else:
        print(render_report(r), end="")
        print(f"→ {paths['report']}\n→ {paths['candidates']}")
    print(f"SCORECARD_REPORT DONE lines={len(lines)} candidates={len(r['top'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""memory-effect-report.py — 記憶注入效果報表（唯讀，零模型判斷）。

彙總四資料源，回答「注入的記憶到底有沒有用」：
  1. <atom>.access.json — 曝光（read_hits/timestamps）+ 效用 α/β（Wilson 下界）
  2. Logs/rescue-log.jsonl — 工具呼叫命中注入 token 的直接使用證據
  3. Logs/recall-miss.jsonl — 失念證據（踩坑時庫有可防 atom 但未被注入）
  4. memory/_atom_index.json — atom 清單 + trigger（SoT）

輸出四清單 + 30 天週趨勢：
  A. top 有用（α/β 證據 + rescue 命中）
  B. 高曝光零使用（token 稅，附 trigger 收斂建議）
  C. 零曝光死重候選
  D. 失念（該想起而未想起，附 trigger 補詞建議）
接入點：/memory health 與 tools/health-weekly.py 週健檢。

用法：python tools/memory-effect-report.py [--json] [--days 30] [--top 10]
注意：timestamps 上限 50 筆/atom，超高頻 atom 的窗內曝光為下限估計。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

CLAUDE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CLAUDE_DIR / "lib"))
sys.path.insert(0, str(CLAUDE_DIR))

from lib.atom_access import USEFULNESS_PRIOR, wilson_lower_bound  # noqa: E402

ATOM_INDEX = CLAUDE_DIR / "memory" / "_atom_index.json"
RESCUE_LOG = CLAUDE_DIR / "Logs" / "rescue-log.jsonl"
RECALL_MISS_LOG = CLAUDE_DIR / "Logs" / "recall-miss.jsonl"
INJECTION_TURNS_LOG = CLAUDE_DIR / "Logs" / "injection-turns.jsonl"  # ups_inject 每 turn 一行


def _load_injection_turns(since_ts: float) -> list[dict]:
    """讀 injection-turns.jsonl 窗內記錄（每回合 ok/fallback/skip/cold 顆數）。缺檔/壞行計為零。"""
    if not INJECTION_TURNS_LOG.exists():
        return []
    out: list[dict] = []
    with INJECTION_TURNS_LOG.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                ts = datetime.fromisoformat(rec["at"]).timestamp()
            except (ValueError, KeyError, TypeError):
                continue
            if ts >= since_ts:
                rec["_ts"] = ts
                out.append(rec)
    return out

EXPOSURE_TAX_MIN = 10   # 窗內曝光 ≥ 此值且零使用證據 → token 稅
TOP_N_DEFAULT = 10


def _load_atoms() -> list[dict]:
    try:
        data = json.loads(ATOM_INDEX.read_text(encoding="utf-8"))
        return data.get("atoms", [])
    except Exception:
        return []


def _load_rescue_hits(since_ts: float) -> dict[str, list[dict]]:
    hits: dict[str, list[dict]] = {}
    if not RESCUE_LOG.exists():
        return hits
    try:
        for line in RESCUE_LOG.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if float(rec.get("ts", 0)) >= since_ts:
                hits.setdefault(str(rec.get("atom", "")), []).append(rec)
    except OSError:
        pass
    return hits


def _load_recall_misses(since_ts: float) -> list[dict]:
    """讀 recall-miss.jsonl 窗內記錄（"at" 為 ISO 字串）。缺檔/壞行計為零。"""
    recs: list[dict] = []
    if not RECALL_MISS_LOG.exists():
        return recs
    try:
        for line in RECALL_MISS_LOG.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                ts = datetime.fromisoformat(str(rec.get("at", ""))).timestamp()
            except (json.JSONDecodeError, ValueError, TypeError):
                continue
            if ts >= since_ts:
                recs.append(rec)
    except OSError:
        pass
    return recs


def _aggregate_recall_misses(recs: list[dict]) -> list[dict]:
    """atom × 次數 × 最近 evidence × 命中 trigger 聯集，依次數降冪。

    次數口徑 = distinct session 數：偵測端每 (session, atom) 一筆，但 resume 後
    多次 SessionEnd 的舊 log 可能同 session 重複落檔——聚合端以 session 去重，
    避免「同 session 記兩輪」呈現成兩次獨立失念。
    """
    agg: dict[str, dict] = {}
    for i, rec in enumerate(recs):
        atom = str(rec.get("atom", ""))
        if not atom:
            continue
        row = agg.setdefault(atom, {
            "atom": atom, "_sessions": set(), "matched_triggers": set(),
            "last_at": "", "last_evidence": "", "last_source": "",
        })
        # 無 session_id 的異常記錄以序號代替，退回逐筆計數
        row["_sessions"].add(str(rec.get("session_id") or f"_rec{i}"))
        row["matched_triggers"].update(rec.get("matched_triggers") or [])
        at = str(rec.get("at", ""))
        if at >= row["last_at"]:  # ISO 字串序 == 時間序
            row["last_at"] = at
            row["last_evidence"] = str(rec.get("evidence", ""))
            row["last_source"] = str(rec.get("source", ""))
    for r in agg.values():
        r["count"] = len(r.pop("_sessions"))
    rows = sorted(agg.values(), key=lambda r: (-r["count"], r["atom"]))
    for r in rows:
        r["matched_triggers"] = sorted(r["matched_triggers"])
    return rows


def collect(days: int = 30, top_n: int = TOP_N_DEFAULT) -> dict:
    now = time.time()
    since = now - days * 86400
    rescue = _load_rescue_hits(since)
    rows: list[dict] = []
    for entry in _load_atoms():
        name = entry.get("name", "")
        rel = entry.get("path", "")
        md = CLAUDE_DIR / rel if rel else None
        acc: dict = {}
        if md is not None:
            sidecar = md.with_suffix(".access.json")
            try:
                acc = json.loads(sidecar.read_text(encoding="utf-8"))
            except Exception:
                acc = {}
        stamps = [t for t in (acc.get("timestamps") or []) if t >= since]
        alpha = float(acc.get("useful_hits") or USEFULNESS_PRIOR)
        beta = float(acc.get("used_fail") or USEFULNESS_PRIOR)
        succ = max(0.0, alpha - USEFULNESS_PRIOR)
        fail = max(0.0, beta - USEFULNESS_PRIOR)
        n = succ + fail
        rows.append({
            "name": name,
            "triggers": entry.get("triggers", []),
            "read_hits_total": int(acc.get("read_hits") or 0),
            "exposures_window": len(stamps),
            "stamps": stamps,
            "alpha": round(alpha, 3),
            "beta": round(beta, 3),
            "evidence_n": round(n, 2),
            "wilson_lb": round(wilson_lower_bound(succ, n), 3) if n > 0 else 0.0,
            "rescue_hits": len(rescue.get(name, [])),
            "last_used": acc.get("last_used"),
        })

    # A. top 有用：有效用證據或 rescue 命中者，依 (wilson_lb, rescue_hits) 排序
    useful = sorted(
        (r for r in rows if r["evidence_n"] > 0 or r["rescue_hits"] > 0),
        key=lambda r: (r["wilson_lb"], r["rescue_hits"], r["exposures_window"]),
        reverse=True,
    )[:top_n]

    # B. 高曝光零使用（token 稅）：窗內曝光高、α/β 零證據、rescue 零命中
    tax = sorted(
        (r for r in rows
         if r["exposures_window"] >= EXPOSURE_TAX_MIN
         and r["evidence_n"] == 0 and r["rescue_hits"] == 0),
        key=lambda r: r["exposures_window"], reverse=True,
    )

    # C. 零曝光死重候選：窗內完全未注入
    dead = sorted(
        (r for r in rows if r["exposures_window"] == 0),
        key=lambda r: (r["last_used"] or ""),
    )

    # 30 天週趨勢：曝光 / rescue 命中（各 bucket 為 7 天，最舊在前）
    n_buckets = max(1, (days + 6) // 7)
    trend = []
    all_rescue_ts = [float(rec["ts"]) for hits in rescue.values() for rec in hits]
    turn_recs = _load_injection_turns(since)
    for b in range(n_buckets):
        lo = since + b * 7 * 86400
        hi = min(lo + 7 * 86400, now + 1)
        wk = [t for t in turn_recs if lo <= t["_ts"] < hi]
        n_turns = len(wk)
        full = sum(int(t.get("ok", 0)) for t in wk)
        hot = full + sum(int(t.get("fallback", 0)) + int(t.get("skip", 0)) for t in wk)
        redundant = sum(int(t.get("redundant", 0)) for t in wk)  # 同題去冗降節錄顆數（不計入全文率分母）
        trend.append({
            "week_of": datetime.fromtimestamp(lo).strftime("%m-%d"),
            "exposures": sum(1 for r in rows for t in r["stamps"] if lo <= t < hi),
            "rescue_hits": sum(1 for t in all_rescue_ts if lo <= t < hi),
            # 每回合平均全文注入顆數 / 熱 atom 全文率（ok ÷ (ok+fallback+skip)）；無紀錄 → None
            "turns": n_turns,
            "full_per_turn": round(full / n_turns, 2) if n_turns else None,
            "full_rate": round(full / hot, 2) if hot else None,
            "redundant": redundant,
        })

    # D. 失念：踩坑時庫有可防 atom（trigger 命中失敗證據 ≥2 詞）但未被注入
    recall_miss = _aggregate_recall_misses(_load_recall_misses(since))

    for r in rows:
        r.pop("stamps", None)
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "window_days": days,
        "atom_count": len(rows),
        "top_useful": useful,
        "exposure_tax": tax,
        "dead_candidates": dead,
        "recall_miss": recall_miss,
        "trend_weekly": trend,
        "caveat": "timestamps 上限 50/atom，超高頻 atom 窗內曝光為下限估計",
    }


def render_md(result: dict) -> str:
    L = [f"# 記憶注入效果報表（近 {result['window_days']} 天，"
         f"{result['atom_count']} atoms，{result['generated_at']}）", ""]

    L.append("## A. Top 有用（α/β 效用證據 + rescue 直接使用證據）")
    if result["top_useful"]:
        L.append("| atom | Wilson下界 | 證據n | α/β | rescue命中 | 窗內曝光 |")
        L.append("|------|-----------|-------|-----|-----------|---------|")
        for r in result["top_useful"]:
            L.append(f"| {r['name']} | {r['wilson_lb']} | {r['evidence_n']} "
                     f"| {r['alpha']}/{r['beta']} | {r['rescue_hits']} "
                     f"| {r['exposures_window']} |")
    else:
        L.append("（無任何效用證據——效用閉環或 rescue 管線可能未運作）")

    L.append("")
    L.append(f"## B. 高曝光零使用（token 稅；窗內曝光 ≥{EXPOSURE_TAX_MIN} 且零證據）")
    if result["exposure_tax"]:
        for r in result["exposure_tax"]:
            trig = ", ".join(r["triggers"][:6])
            L.append(f"- **{r['name']}**（曝光 {r['exposures_window']}）— "
                     f"trigger 收斂建議：檢視過寬詞 [{trig}]，"
                     f"考慮刪高頻泛詞或轉 cold 1-line")
    else:
        L.append("（無）")

    L.append("")
    L.append("## C. 零曝光死重候選（窗內未注入）")
    if result["dead_candidates"]:
        for r in result["dead_candidates"]:
            L.append(f"- {r['name']}（last_used: {r['last_used'] or '從未'}，"
                     f"累計曝光 {r['read_hits_total']}）")
    else:
        L.append("（無）")

    L.append("")
    L.append("## D. 失念（該想起而未想起；踩坑時庫有可防 atom 但檢索未命中）")
    if result.get("recall_miss"):
        L.append("| atom | 次數 | 命中 trigger | 最近 evidence |")
        L.append("|------|------|-------------|--------------|")
        for r in result["recall_miss"]:
            trig = ", ".join(r["matched_triggers"][:5])
            ev = r["last_evidence"][:60].replace("|", "\\|").replace("\n", " ")
            L.append(f"| {r['atom']} | {r['count']} | {trig} | {ev} |")
        L.append("")
        L.append("> 建議：檢視上列 atom 的 trigger 是否該補詞"
                 "（失敗證據已能匹配部分 trigger，卻不足以在當下 prompt 觸發注入）")
    else:
        L.append("（無）")

    L.append("")
    L.append("## 30 天週趨勢")
    L.append("| 週起 | 曝光 | rescue 命中 | 有注入回合 | 全文/回合 | 熱 atom 全文率 | 同題節錄 |")
    L.append("|------|------|------------|-----------|----------|--------------|---------|")
    for t in result["trend_weekly"]:
        fpt = "—" if t.get("full_per_turn") is None else f"{t['full_per_turn']:.2f}"
        fr = "—" if t.get("full_rate") is None else f"{int(round(t['full_rate'] * 100))}%"
        L.append(f"| {t['week_of']} | {t['exposures']} | {t['rescue_hits']} | {t.get('turns', 0)} | {fpt} | {fr} | {t.get('redundant', 0)} |")
    L.append("")
    L.append("> 「全文/回合」= 每個有注入的回合平均完整唸入的 atom 顆數；「熱 atom 全文率」= 全文 ÷ (全文+降級+跳過)。"
             "兩欄來自 Logs/injection-turns.jsonl（ups_inject 每回合自動落檔），是「注入變弱 vs 工作量波動」的分辨依據。")
    L.append("")
    L.append(f"> {result['caveat']}")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--top", type=int, default=TOP_N_DEFAULT)
    args = ap.parse_args()
    result = collect(days=args.days, top_n=args.top)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
        print(render_md(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())

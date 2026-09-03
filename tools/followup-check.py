#!/usr/bin/env python3
"""followup-check.py — 回訪檢查器：到期後由 SessionStart 自動跑，把「改了東西一週後看數據」變成程式判定。

登記表 workflow/followups.json：
  {"followups": [{"id", "title", "due": "YYYY-MM-DD", "since": "YYYY-MM-DD",
                  "check": "<檢查名>", "criteria": {...}, "context": "<一句：改了什麼、為何回訪>",
                  "done": false, "last_shown": "", "result": ""}]}

用法：
  python tools/followup-check.py --list                 列出全部（含未到期）
  python tools/followup-check.py --run [--force]        跑所有到期未結案項（--force 忽略到期日）
  python tools/followup-check.py --run --auto-close     PASS 者自動標 done
  python tools/followup-check.py --run --brief --mark-shown   SessionStart 用：精簡輸出 + 記錄今日已提醒
  python tools/followup-check.py --done <id>            手動結案
  python tools/followup-check.py --add <json>           登記一筆（JSON 物件字串）

檢查名（check）現有：
  injection-budget — 讀 Logs/injection-turns.jsonl（since 起）算 全文/回合、熱 atom 全文率；
                     讀 Logs/atom-debug-*.log 算 final-trim dropped/回合；
                     讀 memory-effect-report.collect 的 exposure_tax 顆數。
狀態：PASS（全過）/ FAIL（有未過）/ INSUFFICIENT（樣本回合數 < criteria.min_turns）。
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

CLAUDE_DIR = Path(__file__).resolve().parent.parent
FOLLOWUPS = CLAUDE_DIR / "workflow" / "followups.json"
INJECTION_TURNS_LOG = CLAUDE_DIR / "Logs" / "injection-turns.jsonl"
ATOM_DEBUG_GLOB = str(CLAUDE_DIR / "Logs" / "atom-debug-*.log")


# ─── 登記表 IO ───────────────────────────────────────────────────────────────

def load() -> dict:
    if not FOLLOWUPS.exists():
        return {"followups": []}
    try:
        return json.loads(FOLLOWUPS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"followups": []}


def save(data: dict) -> None:
    FOLLOWUPS.parent.mkdir(parents=True, exist_ok=True)
    FOLLOWUPS.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


def _d(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def is_due(item: dict, today: date | None = None) -> bool:
    today = today or date.today()
    try:
        return not item.get("done") and _d(item["due"]) <= today
    except (KeyError, ValueError):
        return False


# ─── 檢查：injection-budget ─────────────────────────────────────────────────

def _load_turns(since: date) -> list[dict]:
    out: list[dict] = []
    if not INJECTION_TURNS_LOG.exists():
        return out
    for line in INJECTION_TURNS_LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            if datetime.fromisoformat(rec["at"]).date() >= since:
                out.append(rec)
        except (ValueError, KeyError, TypeError):
            continue
    return out


def _count_dropped_since(since: date) -> int:
    """atom-debug log 中 final-trim form=dropped 行數（since 起，依檔名日期粗篩）。"""
    n = 0
    for p in glob.glob(ATOM_DEBUG_GLOB):
        m = re.search(r"atom-debug-(\d{4}-\d{2}-\d{2})", p)
        if not m or _d(m.group(1)) < since:
            continue
        try:
            for line in Path(p).read_text(encoding="utf-8", errors="replace").splitlines():
                if "final-trim" in line and "form=dropped" in line:
                    n += 1
        except OSError:
            continue
    return n


def check_injection_budget(item: dict) -> dict:
    c = item.get("criteria", {})
    since = _d(item["since"])
    turns = _load_turns(since)
    n = len(turns)
    min_turns = int(c.get("min_turns", 10))
    rows: list[dict] = []
    if n < min_turns:
        return {"status": "INSUFFICIENT", "turns": n, "min_turns": min_turns, "rows": rows}

    full = sum(int(t.get("ok", 0)) for t in turns)
    hot = full + sum(int(t.get("fallback", 0)) + int(t.get("skip", 0)) for t in turns)
    fpt = full / n
    fr = (full / hot) if hot else 0.0
    dropped_pt = _count_dropped_since(since) / n

    def row(name, value, op, thr, fmt="{:.2f}"):
        ok = (value >= thr) if op == ">=" else (value <= thr)
        rows.append({"name": name, "value": fmt.format(value), "threshold": f"{op} {fmt.format(thr)}", "ok": ok})

    row("全文/回合", fpt, ">=", float(c.get("full_per_turn_min", 2.5)))
    row("熱 atom 全文率", fr, ">=", float(c.get("full_rate_min", 0.55)))
    row("final-trim dropped/回合", dropped_pt, "<=", float(c.get("dropped_per_turn_max", 1.0)))

    tax = None
    try:
        sys.path.insert(0, str(CLAUDE_DIR / "tools"))
        import importlib.util
        spec = importlib.util.spec_from_file_location("mer", CLAUDE_DIR / "tools" / "memory-effect-report.py")
        mer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mer)  # type: ignore[union-attr]
        days = max(1, (date.today() - since).days)
        tax = len(mer.collect(days=days).get("exposure_tax", []))
        row("高曝光零使用 atom 數", float(tax), "<=", float(c.get("exposure_tax_max", 0)), fmt="{:.0f}")
    except Exception as e:  # noqa: BLE001 — 報表壞掉不擋回訪，標示即可
        rows.append({"name": "高曝光零使用 atom 數", "value": f"n/a ({e.__class__.__name__})",
                     "threshold": f"<= {c.get('exposure_tax_max', 0)}", "ok": True})

    status = "PASS" if all(r["ok"] for r in rows) else "FAIL"
    return {"status": status, "turns": n, "min_turns": min_turns, "rows": rows}


CHECKS = {"injection-budget": check_injection_budget}


# ─── 輸出 ──────────────────────────────────────────────────────────────────

def render(item: dict, res: dict, brief: bool = False, first_show: bool = False) -> str:
    """交接前提：接手的 session 什麼都不記得。首次推送（或非 brief）整份 handoff 進 context，
    之後每日精簡版只給結果與結案指令。"""
    L = []
    head = f"[Guardian:Followup] ⏰ 回訪到期：{item.get('title', item['id'])}（登記 {item.get('since')} → 到期 {item.get('due')}）"
    L.append(head)
    if res["status"] == "INSUFFICIENT":
        L.append(f"  樣本不足：since 起僅 {res['turns']} 個有注入回合（需 ≥{res['min_turns']}）——多用幾次 CC 後會自動再檢，無需動作。")
        return "\n".join(L)
    if (first_show or not brief) and item.get("handoff"):
        L.append("  ── 交接（假設接手者對本題零記憶）──")
        for k, v in item["handoff"].items():
            if isinstance(v, list):
                L.append(f"  【{k}】")
                L.extend(f"    - {x}" for x in v)
            else:
                L.append(f"  【{k}】{v}")
        L.append("  ── 檢查結果 ──")
    elif not brief and item.get("context"):
        L.append(f"  背景：{item['context']}")
    for r in res["rows"]:
        L.append(f"  {'✅' if r['ok'] else '❌'} {r['name']}：{r['value']}（通過線 {r['threshold']}）")
    if res["status"] == "PASS":
        L.append(f"  結論：全過，{'已自動結案' if item.get('done') else '可結案：python tools/followup-check.py --done ' + item['id']}。")
    else:
        L.append(f"  結論：未全過 → 本 session 先看 `python tools/memory-effect-report.py` 找原因；處理完 `python tools/followup-check.py --done {item['id']}`。")
    return "\n".join(L)


def run_all(force: bool = False, auto_close: bool = False, brief: bool = False, mark_shown: bool = False,
            only_id: str | None = None) -> tuple[list[str], int]:
    data = load()
    out: list[str] = []
    today = date.today().isoformat()
    changed = False
    fails = 0
    for item in data.get("followups", []):
        if only_id and item.get("id") != only_id:
            continue
        if item.get("done"):
            continue
        if not force and not is_due(item):
            continue
        if mark_shown and item.get("last_shown") == today:
            continue  # 今日已提醒
        fn = CHECKS.get(item.get("check", ""))
        if fn is None:
            out.append(f"[Guardian:Followup] ⚠ {item.get('id')}：未知檢查名 {item.get('check')!r}")
            continue
        res = fn(item)
        first_show = not item.get("last_shown")
        item["result"] = f"{today} {res['status']}"
        if res["status"] == "PASS" and auto_close:
            item["done"] = True
            item["done_at"] = today
        if res["status"] == "FAIL":
            fails += 1
        if mark_shown and res["status"] != "INSUFFICIENT":
            item["last_shown"] = today  # 樣本不足不算「已提醒」，補足後仍要整份推
        changed = True
        out.append(render(item, res, brief=brief, first_show=first_show))
    if changed:
        save(data)
    return out, fails


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--id", default=None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--auto-close", action="store_true")
    ap.add_argument("--brief", action="store_true")
    ap.add_argument("--mark-shown", action="store_true")
    ap.add_argument("--done", default=None)
    ap.add_argument("--add", default=None, help="JSON 物件字串")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if args.add:
        data = load()
        item = json.loads(args.add)
        for k in ("id", "title", "due", "since", "check"):
            if k not in item:
                print(f"缺欄位 {k}", file=sys.stderr)
                return 2
        item.setdefault("done", False)
        item.setdefault("criteria", {})
        data.setdefault("followups", []).append(item)
        save(data)
        print(f"added {item['id']} (due {item['due']})")
        return 0
    if args.done:
        data = load()
        for item in data.get("followups", []):
            if item.get("id") == args.done:
                item["done"] = True
                item["done_at"] = date.today().isoformat()
                save(data)
                print(f"done {args.done}")
                return 0
        print(f"not found: {args.done}", file=sys.stderr)
        return 1
    if args.list:
        for item in load().get("followups", []):
            flag = "done" if item.get("done") else ("DUE" if is_due(item) else "pending")
            print(f"{flag:8} {item['id']}  due={item.get('due')}  last={item.get('result', '')}")
        return 0
    if args.run:
        lines, fails = run_all(force=args.force, auto_close=args.auto_close, brief=args.brief,
                               mark_shown=args.mark_shown, only_id=args.id)
        if lines:
            print("\n".join(lines))
        return 1 if fails else 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())

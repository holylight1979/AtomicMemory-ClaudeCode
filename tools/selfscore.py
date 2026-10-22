#!/usr/bin/env python3
"""selfscore.py — 自檢評分：打「這個 G 幾分」時，問三件事、答完記一筆帳（手動工具，不是切入點、不接判準卡）。

做什麼：
  --ask   問的那一刻：印 G 名、評分規格卡（memory 裡的 g<N>-評分規格*.md）的評分尺三句、可用證據清單與要答的三件事。
  （預設）答一筆：分數 0～10、依據材料（可重複）、理由、評的人 → Logs/guard-selfscore.jsonl 一行（event=score）。
          缺欄位或分數不是 0～10 的整數照記，該欄寫「沒答」、列進 unanswered，stderr 印一行，不擋（exit 0）。
  --summary 每個 G 最近一筆、最近五個分數的走勢、比上一次差多少；只讀。
帳本不是卡：不注入、不過期；從帳本淬鍊出的判準才寫卡。session 預設取 Claude Code 給工具子行程的 CLAUDE_CODE_SESSION_ID。

怎麼跑：
  python tools/selfscore.py --ask --g G8
  python tools/selfscore.py --g G8 --score 7 --basis commit:6e3fced4 --basis "第二波 A′ 判分" --why "…" --rater 總控台
  python tools/selfscore.py --summary [--days 30] [--json] [--logs <Logs 目錄>]
尾行：問 `SELFSCORE DONE asked=1 cards=<判準卡張數>`；答 `SELFSCORE DONE recorded=1 unanswered=<沒答欄數>`；
統計 `SELFSCORE DONE gs=<有帳的 G 數> records=<筆數> unanswered=<有沒答欄的筆數>`。exit 0（沒資料也 0）。
完整參數以 --help 為準。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

CODE_DIR = Path(__file__).resolve().parent.parent   # 程式碼根（本檔所在的樹）
if str(CODE_DIR / "hooks") not in sys.path:
    sys.path.insert(0, str(CODE_DIR / "hooks"))

import wg_entrypoint as ep  # noqa: E402
from wg_core import append_guard_log, logs_dir  # noqa: E402

GUARD = "selfscore"
UNANSWERED = "沒答"
EVIDENCE = "檔:行、commit、題號（例：第二波 A′）、收據 R 號、guard log 路徑——依據要查得到，不收印象"


def norm_g(raw: str) -> str:
    """G8／g8／8 → G8；認不出照原字（去頭尾空白）。"""
    s = (raw or "").strip()
    m = re.fullmatch(r"[Gg]?(\d+)", s)
    return f"G{m.group(1)}" if m else s


def find_spec(g: str) -> Optional[Dict[str, Any]]:
    """g<N>-評分規格*.md（memory 底下任一層）→ {name, file, title, rubric:[句]}；找不到回 None。"""
    m = re.fullmatch(r"G(\d+)", g)
    if not m:
        return None
    hits = sorted(ep.MEMORY_DIR.rglob(f"g{m.group(1)}-評分規格*.md"))
    if not hits:
        return None
    path = hits[0]
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None
    title = next((ln[2:].strip() for ln in text.splitlines() if ln.startswith("# ")), path.stem)
    knowledge = ep._knowledge({"file": str(path)})
    rubric = [ln.strip()[2:].strip() for ln in knowledge.splitlines() if ln.strip().startswith("- ")]
    return {"name": path.stem, "file": str(path), "title": title, "rubric": rubric}


def ask_text(g: str, spec: Optional[Dict[str, Any]]) -> str:
    head = f"[SELFSCORE_ASK] 自檢評分｜{g}：{spec['title'] if spec else '（找不到這個 G 的評分規格卡）'}"
    lines = [head]
    if spec:
        lines.append(f"評分尺（評分規格卡 {spec['name']}）：")
        lines += [f"- {r}" for r in spec["rubric"]] or ["- （卡的知識段是空的）"]
    lines.append(f"可用證據：{EVIDENCE}")
    lines.append("要答三件事：幾分（0～10）、依據哪些材料、為什麼。答完跑："
                 f"python tools/selfscore.py --g {g} --score <0～10> --basis <材料>（可重複）--why \"<理由>\" --rater <總控台／軌名>")
    return "\n".join(lines)


def record(g: str, score: Optional[str], basis: List[str], why: str, rater: str, session_id: str) -> Dict[str, Any]:
    """答一筆：缺的欄寫「沒答」、列進 unanswered；分數只收 0～10 的整數，其他照記原字在 score_raw。"""
    unanswered: List[str] = []
    # 時間記到微秒：同一秒內答好幾筆也排得出先後
    rec: Dict[str, Any] = {"at": datetime.now().astimezone().isoformat(), "event": "score", "session_id": session_id}
    rec["g"] = g or UNANSWERED
    raw = (score or "").strip()
    if re.fullmatch(r"[0-9]|10", raw):                        # 只收 ASCII 0～10（isdigit 會放過「²」這類字、int() 再炸掉）
        rec["score"] = int(raw)
    else:
        rec["score"] = UNANSWERED
        if raw:
            rec["score_raw"] = raw
    items = [b.strip() for b in basis if b and b.strip()]
    rec["basis"] = items or UNANSWERED
    rec["why"] = why.strip() or UNANSWERED
    rec["rater"] = rater.strip() or UNANSWERED
    for key in ("g", "score", "basis", "why", "rater"):
        if rec[key] == UNANSWERED:
            unanswered.append(key)
    rec["unanswered"] = unanswered
    path = logs_dir() / f"guard-{GUARD}.jsonl"
    before = path.stat().st_size if path.exists() else -1
    append_guard_log(GUARD, rec)                               # 這支寫不進去只記 debug log，不報錯；所以寫完比大小
    rec["written"] = path.exists() and path.stat().st_size != before
    return rec


def _read(logs: Path) -> List[Dict[str, Any]]:
    """guard-selfscore.jsonl 與輪替的 .1、.2；壞行跳過並計數印 stderr。"""
    rows, bad = [], 0
    base = logs / f"guard-{GUARD}.jsonl"
    for p in (base.with_suffix(".jsonl.2"), base.with_suffix(".jsonl.1"), base):
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                bad += 1
                continue
            if isinstance(rec, dict) and rec.get("event") == "score":
                rows.append(rec)
    if bad:
        print(f"[selfscore] 帳本有 {bad} 行讀不懂，已跳過", file=sys.stderr)
    return rows


def _at(rec: Dict[str, Any]) -> datetime:
    try:
        t = datetime.fromisoformat(str(rec.get("at") or "").replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return t if t.tzinfo else t.astimezone()


def summary(logs: Path, days: int) -> Dict[str, Any]:
    cut = datetime.now().astimezone() - timedelta(days=days)
    rows = sorted((r for r in _read(logs) if _at(r) >= cut), key=_at)
    per: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        per.setdefault(str(r.get("g") or UNANSWERED), []).append(r)
    out = []
    for g, recs in sorted(per.items()):
        nums = [r["score"] for r in recs if isinstance(r.get("score"), int)]
        last = recs[-1]
        has_score = isinstance(last.get("score"), int)              # 最新一筆沒答：不拿前兩次的差值掛在它旁邊
        out.append({"g": g, "records": len(recs), "latest": {k: last.get(k) for k in ("at", "score", "basis", "why", "rater")},
                    "trend": nums[-5:], "delta": nums[-1] - nums[-2] if has_score and len(nums) >= 2 else None,
                    "unanswered": sum(1 for r in recs if r.get("unanswered"))})
    return {"days": days, "logs": str(logs), "gs": out,
            "totals": {"gs": len(out), "records": len(rows), "unanswered": sum(s["unanswered"] for s in out)}}


def main(argv: List[str] = None) -> int:
    ap = argparse.ArgumentParser(description="自檢評分：--ask 問、答一筆、--summary 統計")
    ap.add_argument("--ask", action="store_true", help="問的那一刻：印評分尺與要答的三件事")
    ap.add_argument("--summary", action="store_true", help="每個 G 最近一筆與走勢（唯讀）")
    ap.add_argument("--g", default="", help="評哪個 G（G8／g8／8 都收）")
    ap.add_argument("--score", default=None, help="分數 0～10 的整數")
    ap.add_argument("--basis", action="append", default=[], help="依據材料（檔:行、commit、題號…）；可重複")
    ap.add_argument("--why", default="", help="理由")
    ap.add_argument("--rater", default="", help="評的人（總控台／軌名）")
    ap.add_argument("--session", default=None, help="session id（預設環境變數 CLAUDE_CODE_SESSION_ID）")
    ap.add_argument("--days", type=int, default=30, help="--summary 只看近幾天（預設 30）")
    ap.add_argument("--logs", default=None, help="--summary 讀哪個 Logs 目錄（預設資料根的 Logs）")
    ap.add_argument("--json", action="store_true", help="--summary 輸出 JSON（尾行仍是 DONE 行）")
    args = ap.parse_args(argv)
    session_id = args.session if args.session is not None else os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    g = norm_g(args.g)

    if args.summary:
        res = summary(Path(args.logs) if args.logs else logs_dir(), args.days)
        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        elif not res["gs"]:
            print(f"近 {args.days} 天沒有自檢評分帳（{res['logs']}）")
        else:
            print(f"近 {args.days} 天自檢評分（{res['logs']}）：")
            for s in res["gs"]:
                lt = s["latest"]
                delta = "" if s["delta"] is None else f"（比上次 {s['delta']:+d}）"
                print(f"- {s['g']}：最近 {lt['score']} 分{delta}｜{lt['at']}｜{lt['rater']}｜走勢 {s['trend']}｜"
                      f"{s['records']} 筆、有沒答欄 {s['unanswered']} 筆")
        t = res["totals"]
        print(f"SELFSCORE DONE gs={t['gs']} records={t['records']} unanswered={t['unanswered']}")
        return 0

    if args.ask:
        text = ask_text(g, find_spec(g))
        print(text)
        print("SELFSCORE DONE asked=1")
        return 0

    rec = record(g, args.score, args.basis, args.why, args.rater, session_id)
    if not rec.pop("written"):
        print(f"[selfscore] 帳沒寫進去（{logs_dir() / f'guard-{GUARD}.jsonl'}），這一筆沒記到", file=sys.stderr)
        print("SELFSCORE DONE recorded=0 unanswered=0")
        return 1
    if rec["unanswered"]:
        print(f"[selfscore] 這一筆有沒答的欄：{'、'.join(rec['unanswered'])}（照記，不擋）", file=sys.stderr)
    print(f"記下 {rec['g']}：{rec['score']} 分｜依據 {rec['basis']}｜理由 {rec['why']}｜{rec['rater']}")
    print(f"SELFSCORE DONE recorded=1 unanswered={len(rec['unanswered'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

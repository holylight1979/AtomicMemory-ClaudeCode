#!/usr/bin/env python3
"""token_usage.py — 量一場或多場 Claude Code session 實際處理了多少 token（不換算美金）。

做什麼：每個目標算一列：回覆數、輸入（未快取＋讀快取＋建快取）、輸出、合計、子代理檔數、分鐘。
  目標＝session id（完整或前綴）或 transcript .jsonl 路徑；同一則回覆拆成多行只算一次，子代理一起算（lib/transcript_tokens.py）。
  沒給目標 → 目前 session（環境變數 CLAUDE_CODE_SESSION_ID）；沒有這變數 → cwd 對應的專案資料夾裡最近改過的 transcript，並印出選了哪個。
怎麼跑：python token_usage.py [目標 ...] [--json]；完整參數看 --help。
  尾行 TOKENS DONE sessions=<n>；有目標找不到 exit 1（印原因），意外錯誤 exit 2（原因在 stderr）。
"""
import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

# Windows Python 預設 cp950 stdout 中文會亂碼 → 強制 UTF-8
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

_CODE_ROOT = Path(__file__).resolve().parents[3]   # 程式碼根（skills/token/scripts/ 往上三層）
if str(_CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(_CODE_ROOT))
from lib.transcript_tokens import find_transcripts, projects_dir, session_totals  # noqa: E402

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


class TargetError(Exception):
    """目標找不到或對到不只一份 transcript。"""


def resolve(target: str) -> Path:
    hits = find_transcripts(target)
    if not hits:
        raise TargetError(f"找不到 {target}：不是存在的 .jsonl，也不是 {projects_dir()} 底下的 session id 或前綴")
    if len(hits) > 1:
        names = "、".join(h.stem for h in hits[:5])
        raise TargetError(f"{target} 對到 {len(hits)} 份 transcript（{names}），給長一點的前綴")
    return hits[0]


def current_session() -> tuple[Path, str]:
    """回傳 (transcript, 怎麼選的)。"""
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID", "").strip()
    if sid:
        return resolve(sid), f"目前 session（CLAUDE_CODE_SESSION_ID={sid}）"
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(Path.cwd())).lower()
    root = projects_dir()
    dirs = [d for d in root.iterdir() if d.is_dir() and d.name.lower() == slug] if root.is_dir() else []
    files = [f for d in dirs for f in d.glob("*.jsonl")]
    if not files:
        raise TargetError(f"沒有 CLAUDE_CODE_SESSION_ID，{root} 底下也沒有對應 cwd 的資料夾（{slug}）或裡面沒有 transcript")
    latest = max(files, key=lambda f: f.stat().st_mtime)
    return latest, f"沒有 CLAUDE_CODE_SESSION_ID，改用 {latest.parent.name} 裡最近改過的 {latest.name}"


def _width(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def _pad(s: str, width: int, right: bool) -> str:
    fill = " " * (width - _width(s))
    return fill + s if right else s + fill


def print_table(rows: list[dict]) -> None:
    head = ["session", "回覆", "輸入", "未快取", "讀快取", "建快取", "輸出", "合計", "子代理檔", "分鐘"]
    keys = ["replies", "input", "input_uncached", "cache_read", "cache_create", "output", "total", "subagent_files"]
    body = []
    for r in rows:
        minutes = "-" if r["minutes"] is None else f"{r['minutes']:g}"
        body.append([r["label"]] + [f"{r[k]:,}" for k in keys] + [minutes])
    widths = [max(_width(line[i]) for line in [head] + body) for i in range(len(head))]
    for line in [head] + body:
        print("  ".join(_pad(cell, widths[i], right=i > 0) for i, cell in enumerate(line)))
    print("輸入＝未快取＋讀快取＋建快取；合計＝輸入＋輸出；分鐘＝第一筆到最後一筆紀錄相隔。")
    for r in rows:
        print(f"{r['label']} → {r['transcript']}")


def main() -> int:
    p = argparse.ArgumentParser(description="量 Claude Code session 實際處理了多少 token（含子代理，不換算美金）")
    p.add_argument("targets", nargs="*", help="session id（完整或前綴）或 transcript .jsonl 路徑；不給＝目前 session")
    p.add_argument("--json", action="store_true", help="輸出 JSON（尾行仍是 TOKENS DONE）")
    args = p.parse_args()
    try:
        if args.targets:
            picked = [(resolve(t), f"目標 {t}") for t in args.targets]
        else:
            picked = [current_session()]
            if not args.json:
                print(picked[0][1])
        rows = []
        for path, how in picked:
            stem = path.stem
            rows.append({"label": stem[:8] if UUID_RE.match(stem) else stem, "transcript": str(path),
                         "picked": how, **session_totals(path)})
        if args.json:
            print(json.dumps({"sessions": rows}, ensure_ascii=False, indent=2))
        else:
            print_table(rows)
        print(f"TOKENS DONE sessions={len(rows)}")
        return 0
    except TargetError as e:
        print(e)
        return 1
    except Exception as e:  # noqa: BLE001 — 意外錯誤照實報、不吞
        print(f"token_usage 意外錯誤：{type(e).__name__}: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

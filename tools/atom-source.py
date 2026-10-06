#!/usr/bin/env python3
"""atom-source.py — 這張卡片哪來的？回看 atom 的原句與原對話前後文。

做什麼：
  讀 atom 的 Source／Quote 行，Source 指向的 session transcript 還在就把原句與前後一則對話撈出來
  （live）；transcript 已清掉只剩落檔時的 Quote（quote_only）；都沒有（commit:/unknown）→ unrecoverable。
  只讀不寫（lib/provenance.py 單源）。

怎麼跑：
  python ~/.claude/tools/atom-source.py "<atom 名或絕對路徑>"
  python ~/.claude/tools/atom-source.py "<atom>" --cwd C:/proj --json     # 專案層 atom 給 --cwd；機器讀用 --json
  找不到 atom → exit 1、原因在 stderr。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CLAUDE_DIR = Path(__file__).resolve().parent.parent
if str(CLAUDE_DIR) not in sys.path:
    sys.path.insert(0, str(CLAUDE_DIR))

from lib.provenance import atom_source  # noqa: E402


def format_human(result: dict) -> str:
    out = [f"{result['atom']} — {result['state']}"]
    out.append(f"Source: {result['source'] or '(無)'}")
    out.append(f"Quote: {'「' + result['quote'] + '」' if result['quote'] else '(無)'}")
    for item in result.get("context") or []:
        text = item["text"].replace("\n", " ")
        out.append(f"[{item['role']} {item['ts']}] {text}")
    out.extend(f"⚠ {w}" for w in result.get("warnings") or [])
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="回看 atom 的來源原句與對話前後文")
    ap.add_argument("atom", help="atom 名（檔名 slug）或 .md 絕對路徑")
    ap.add_argument("--cwd", default=None, help="專案根（找專案層 atom 時給）")
    ap.add_argument("--json", action="store_true", help="輸出 JSON")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    result = atom_source(args.atom, cwd=args.cwd)
    if "error" in result:
        print(f"[atom-source] {result['error']}", file=sys.stderr)
        for w in result.get("warnings") or []:
            print(f"[atom-source] ⚠ {w}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else format_human(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())

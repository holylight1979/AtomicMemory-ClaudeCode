#!/usr/bin/env python3
"""memory-search.py — 命令列一句話查原子記憶（唯讀）。

做什麼：走與 hook 注入同一條檢索管線（候選池→trigger/BM25/vector→RRF），印人讀表格或 JSON。
給非 Claude Code 人員／腳本用：裝好 ~/.claude 後直接跑。
怎麼跑：
  python ~/.claude/tools/memory-search.py "git commit 前要看 diff"
  python ~/.claude/tools/memory-search.py "問題" --cwd <專案根> --json --no-vector --top-k 5
與 rag-engine.py search 的分工：rag-engine 是純向量相似度（直接打向量服務、不看 scope 可見性、不融合
trigger/BM25）；本工具是記憶系統的正式讀取端（可見性收窄、三路融合、穩定 schema），日常查記憶用這支。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.memory_search import search, default_identity, format_table  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="一句話查原子記憶（唯讀）；完整參數以 --help 為準")
    ap.add_argument("query", help="要查的問題或關鍵字")
    ap.add_argument("--cwd", default=os.getcwd(), help="以哪個專案目錄的視角查（預設目前目錄）")
    ap.add_argument("--json", action="store_true", help="輸出原始 JSON（schema_version=1）")
    ap.add_argument("--no-vector", action="store_true", help="不走向量路（離線／快）")
    ap.add_argument("--top-k", type=int, default=8, help="最多回幾筆（預設 8）")
    ap.add_argument("--user", default=None, help="以誰的身份查（預設現用 OS 帳號；給 unknown 則不讀 personal）")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    user, roles = default_identity(args.cwd)
    if args.user is not None:
        user = args.user
    try:
        result = search(args.query, args.cwd, user=user, roles=roles,
                        top_k=args.top_k, use_vector=not args.no_vector)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else format_table(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())

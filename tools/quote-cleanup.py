#!/usr/bin/env python3
"""quote-cleanup.py：找出 `- Quote:` 被自動回填成一兩個字回覆（預設「A」）的卡，刪掉那一行。

做什麼：
  掃記憶卡（預設資料根的 memory/ 與 _AIDocs/_atoms/，--memory-dir 可再加專案層、公司層），`- Quote: 「<值>」` 的值
  整個等於 --value（預設 A）的卡列出來；加 --apply 才刪掉那一行（只刪那一行，其餘位元組原樣，BOM 照留）。
  寫入走 lib.atom_io.write_raw（source=tool:quote-cleanup，留稽核帳），不直接改 .md。
  _atom_index.json 與 MEMORY.md 不存 Quote，刪行不必寫索引。
  起因：PostToolUse 回填拿最近一則使用者訊息當 Quote，那一則是「A」時整批卡都被填成「A」；回填規則已改成太短不填
  （lib/provenance.usable_quote），這支清已經填進去的。

怎麼跑：
  python tools/quote-cleanup.py                          # dry-run：只列，不改
  python tools/quote-cleanup.py --apply                  # 真刪
  python tools/quote-cleanup.py --value 好 --memory-dir <專案>/.claude/memory --json
  完整參數見 --help。尾行：QUOTE_CLEANUP DONE matched=<n> changed=<n> failed=<n> dry_run=<0|1>（有寫失敗 exit 1）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

CODE_DIR = Path(__file__).resolve().parent.parent   # 程式碼根：lib.* 從本樹載
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from lib.atom_io import write_raw  # noqa: E402
from lib.atom_spec import iter_atom_files  # noqa: E402
from lib.project_root import claude_data_dir  # noqa: E402

SOURCE = "tool:quote-cleanup"
_QUOTE_RE = re.compile(r"^-[ \t]*Quote:[ \t]*「(.*)」[ \t]*(?:\r?\n|\Z)", re.MULTILINE)
_SECTION_RE = re.compile(r"^## ", re.MULTILINE)


def default_roots() -> List[Path]:
    data = claude_data_dir()
    return [data / "memory", data / "_AIDocs" / "_atoms"]


def strip_quote(text: str, value: str) -> Optional[str]:
    """中繼資料區（第一個 `## ` 段之前）的 Quote 行，值整個等於 value → 回刪掉那一行的全文；沒有這種行回 None。
    知識段裡同字樣的句子不算。"""
    sec = _SECTION_RE.search(text)
    m = _QUOTE_RE.search(text, 0, sec.start() if sec else len(text))
    if not m or m.group(1).strip() != value:
        return None
    return text[:m.start()] + text[m.end():]


def scan(roots: List[Path], value: str, apply: bool) -> Dict[str, List[Dict[str, str]]]:
    out: Dict[str, List[Dict[str, str]]] = {"matched": [], "failed": []}
    seen = set()
    for root in roots:
        for path in iter_atom_files(Path(root)):
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            raw = path.read_bytes()
            bom = raw.startswith(b"\xef\xbb\xbf")
            new = strip_quote(raw.decode("utf-8-sig"), value)
            if new is None:
                continue
            out["matched"].append({"path": str(path)})
            if not apply:
                continue
            res = write_raw(path, ("﻿" if bom else "") + new, source=SOURCE, op="quote-cleanup")
            if not res.ok:
                out["failed"].append({"path": str(path), "error": res.error or "write failed"})
                print(f"[quote-cleanup] 寫不進 {path}：{res.error}", file=sys.stderr)
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="刪掉 Quote 被回填成一兩個字回覆（預設「A」）的那一行；預設 dry-run。")
    ap.add_argument("--value", default="A", help="Quote 「」裡的值整個等於它才算（預設 A）")
    ap.add_argument("--memory-dir", action="append", default=[], help="再加一個要掃的記憶目錄（可重複；專案層、公司層）")
    ap.add_argument("--only-given", action="store_true", help="只掃 --memory-dir 給的目錄，不掃資料根預設兩處")
    ap.add_argument("--apply", action="store_true", help="真的刪；沒給只列")
    ap.add_argument("--json", action="store_true", help="結果印成 JSON（尾行照印）")
    args = ap.parse_args(argv)
    roots = ([] if args.only_given else default_roots()) + [Path(p) for p in args.memory_dir]
    res = scan(roots, args.value.strip(), args.apply)
    changed = len(res["matched"]) - len(res["failed"]) if args.apply else 0
    if args.json:
        print(json.dumps({"value": args.value, "apply": args.apply, "roots": [str(r) for r in roots], **res},
                         ensure_ascii=False, indent=2))
    else:
        verb = "已刪 Quote 行" if args.apply else "會刪 Quote 行（dry-run，加 --apply 才改）"
        for m in res["matched"]:
            print(f"{verb}：{m['path']}")
    print(f"QUOTE_CLEANUP DONE matched={len(res['matched'])} changed={changed} failed={len(res['failed'])} "
          f"dry_run={0 if args.apply else 1}")
    return 1 if res["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())

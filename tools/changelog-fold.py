#!/usr/bin/env python3
"""changelog-fold.py — 把各工作軌寫的 CHANGELOG 片段收進 _AIDocs/_CHANGELOG.md（規則 CHANGELOG_PER_TRACK）。

做什麼：多軌並行時每軌都往 _CHANGELOG.md 檔頭插一段，合併必撞檔頭衝突。改成每軌只寫自己的片段
  `_AIDocs/_changelog.d/<軌名>-<NNN>.md`（內容同主檔一段：`## YYYY-MM-DD 標題` 起頭＋條列），總控台合完再跑本工具：
  片段依日期新到舊（同日依檔名）插在主檔第一個 `---` 之後，收完刪掉片段。
怎麼跑：
  python tools/changelog-fold.py --check        # 只列待收的片段、檢查格式；尾行 CHANGELOG_FOLD_CHECK PASS／FAIL
  python tools/changelog-fold.py --write        # 收進主檔並刪片段；尾行 CHANGELOG_FOLD DONE folded=<n>
  --dir／--changelog 換片段資料夾與主檔（測試用）。
exit：0 完成；1 --check 有格式錯；2 主檔讀不到、找不到 `---` 分隔、片段格式錯（--write 一個都不動）。
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import List, Tuple

CODE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CHANGELOG = CODE_DIR / "_AIDocs" / "_CHANGELOG.md"
DEFAULT_DIR = CODE_DIR / "_AIDocs" / "_changelog.d"
HEAD_RE = re.compile(r"^## (\d{4}-\d{2}-\d{2}) \S")


def fragments(frag_dir: Path) -> Tuple[List[Tuple[str, Path, str]], List[str]]:
    """(日期, 路徑, 內容) 依日期新到舊、同日依檔名；格式錯的列進第二個回傳值。"""
    good: List[Tuple[str, Path, str]] = []
    bad: List[str] = []
    for p in sorted(frag_dir.glob("*.md")) if frag_dir.is_dir() else []:
        text = p.read_text(encoding="utf-8").strip("\n")
        m = HEAD_RE.match(text)
        if not m:
            bad.append(f"{p.name}：第一行要是「## YYYY-MM-DD 標題」")
            continue
        good.append((m.group(1), p, text))
    good.sort(key=lambda g: (g[0], g[1].name), reverse=True)
    return good, bad


def fold(changelog: Path, frags: List[Tuple[str, Path, str]]) -> str:
    """片段插在主檔第一個 `---` 行之後；回新的主檔內容。找不到分隔行丟 ValueError。"""
    lines = changelog.read_text(encoding="utf-8").split("\n")
    try:
        at = next(i for i, ln in enumerate(lines) if ln.strip() == "---")
    except StopIteration:
        raise ValueError(f"{changelog.name} 找不到 --- 分隔行") from None
    block = [ln for _, _, text in frags for ln in text.split("\n")]
    return "\n".join(lines[:at + 1] + block + lines[at + 1:])


def main() -> int:
    for stream in (sys.stdout, sys.stderr):     # 片段檔名、訊息是中文：Windows 主控台預設 cp950 會亂碼
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    ap.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    ap.add_argument("--changelog", type=Path, default=DEFAULT_CHANGELOG)
    args = ap.parse_args()
    frags, bad = fragments(args.dir)
    for b in bad:
        print(f"[changelog-fold] {b}", file=sys.stderr)
    if args.check:
        for d, p, _ in frags:
            print(f"待收：{p.name}（{d}）")
        print("CHANGELOG_FOLD_CHECK FAIL" if bad else "CHANGELOG_FOLD_CHECK PASS")
        return 1 if bad else 0
    if bad:
        print("CHANGELOG_FOLD DONE folded=0")
        return 2
    if not frags:
        print("CHANGELOG_FOLD DONE folded=0")
        return 0
    try:
        new = fold(args.changelog, frags)
    except (OSError, ValueError) as e:
        print(f"[changelog-fold] {e}；一個都沒收", file=sys.stderr)
        print("CHANGELOG_FOLD DONE folded=0")
        return 2
    tmp = args.changelog.with_suffix(".md.tmp")
    tmp.write_text(new, encoding="utf-8", newline="\n")
    os.replace(tmp, args.changelog)
    for _, p, _ in frags:
        p.unlink()
    print(f"CHANGELOG_FOLD DONE folded={len(frags)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""compact-reinject-report.py — 壓縮後卡片內文是誰送回去的（唯讀量尺，不判 PASS／FAIL）。

掃最近 N 場主 session 逐字稿（~/.claude/projects/*/<session>.jsonl，子代理逐字稿不算：子代理壓縮不跑 SessionStart），
每個壓縮點（system 列 subtype=compact_boundary）到下一個壓縮點之間，看 hook 送進對話的附件（attachment type=hook_additional_context）：
  - 第一筆附件來自 SessionStart 且帶卡片內文（含 `[Atom:`）→ 算 via_session_start（壓縮後第一時間就有卡）
  - 有 PostToolBatch 附件帶 `[Atom Recovery]` → 算 via_batch（等到下一批工具結束才補上）
  - 有任何 SessionStart 附件 → 算 session_start_ran（SessionStart(compact) 有跑）
ratio＝via_session_start／total。每個壓縮點印一行明細，結尾一行 `COMPACT_REINJECT DONE ...`。

用法：python tools/compact-reinject-report.py [--last 400] [--root ~/.claude/projects] [--quiet]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterator, List

BOUNDARY_MARK = '"compact_boundary"'
HOOK_CTX_MARK = '"hook_additional_context"'


def _recent_transcripts(root: Path, last: int) -> List[Path]:
    """主 session 逐字稿依修改時間由新到舊取前 last 份。"""
    files = [p for p in root.glob("*/*.jsonl") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:last]


def _attachment_text(att: Dict[str, Any]) -> str:
    content = att.get("content")
    if isinstance(content, list):
        return "\n".join(str(c) for c in content)
    return str(content or "")


def _windows(path: Path) -> Iterator[Dict[str, Any]]:
    """逐字稿裡每個壓縮點一筆：時間、觸發方式、之後到下一個壓縮點之間的 hook 附件（事件名, 內文）。"""
    win = None
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if BOUNDARY_MARK not in line and HOOK_CTX_MARK not in line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("subtype") == "compact_boundary":
                if win:
                    yield win
                meta = row.get("compactMetadata") or {}
                win = {"ts": row.get("timestamp", ""), "trigger": meta.get("trigger", "?"), "hooks": []}
                continue
            att = row.get("attachment") or {}
            if win is None or att.get("type") != "hook_additional_context":
                continue
            win["hooks"].append((str(att.get("hookEvent") or att.get("hookName") or "?"), _attachment_text(att)))
    if win:
        yield win


def _classify(win: Dict[str, Any]) -> Dict[str, Any]:
    hooks = win["hooks"]
    first_event = hooks[0][0] if hooks else "-"
    first_has_cards = bool(hooks) and first_event == "SessionStart" and "[Atom:" in hooks[0][1]
    return {
        "first": first_event,
        "via_session_start": first_has_cards,
        "via_batch": any(ev == "PostToolBatch" and "[Atom Recovery]" in txt for ev, txt in hooks),
        "session_start_ran": any(ev == "SessionStart" for ev, _ in hooks),
    }


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="壓縮後卡片內文由 SessionStart 或 PostToolBatch 送回的比例（唯讀量尺）")
    ap.add_argument("--last", type=int, default=400, help="掃最近幾場主 session（預設 400）")
    ap.add_argument("--root", default=str(Path.home() / ".claude" / "projects"), help="逐字稿根目錄")
    ap.add_argument("--quiet", action="store_true", help="不印每個壓縮點的明細")
    args = ap.parse_args()

    counts = {"total": 0, "via_session_start": 0, "via_batch": 0, "session_start_ran": 0}
    for path in _recent_transcripts(Path(args.root), args.last):
        try:
            if BOUNDARY_MARK not in path.read_text(encoding="utf-8", errors="replace"):
                continue
            wins = list(_windows(path))
        except OSError as e:
            print(f"[skip] 讀不到 {path}: {e}", file=sys.stderr)
            continue
        for win in wins:
            c = _classify(win)
            counts["total"] += 1
            for key in ("via_session_start", "via_batch", "session_start_ran"):
                counts[key] += int(c[key])
            if not args.quiet:
                print(f"{path.stem[:8]} {win['ts'][:19]} {win['trigger']:<6} first={c['first']:<14} "
                      f"ss_cards={int(c['via_session_start'])} batch={int(c['via_batch'])} ss_ran={int(c['session_start_ran'])}")

    ratio = f"{counts['via_session_start'] / counts['total']:.2f}" if counts["total"] else "n/a"
    print(f"COMPACT_REINJECT DONE total={counts['total']} via_session_start={counts['via_session_start']} "
          f"via_batch={counts['via_batch']} session_start_ran={counts['session_start_ran']} ratio={ratio}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

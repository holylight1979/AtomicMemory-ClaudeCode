"""dup_check.py — 查 live transcript 之間有沒有重複的列（同一 uuid 出現在多支檔＝resume 複製歷史），只看七種提示的附件列。"""
import json, sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import notice_replay as nr
since = datetime.fromisoformat("2026-10-01").timestamp()
where = defaultdict(set)
for tp in (Path.home() / ".claude" / "projects").glob("*/*.jsonl"):
    if tp.stat().st_mtime < since:
        continue
    for line in tp.open(encoding="utf-8", errors="replace"):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        a = r.get("attachment") or {}
        if a.get("type") != "hook_additional_context":
            continue
        if any(nr.kind_of(b) for t in a.get("content") or [] for b in nr.blocks(t)):
            where[r.get("uuid")].add(tp.name)
multi = {u: f for u, f in where.items() if len(f) > 1}
print(f"附件列 {len(where)} 筆，出現在多支 transcript 的 {len(multi)} 筆")
print("DUP_CHECK DONE rows=%d dup=%d" % (len(where), len(multi)))

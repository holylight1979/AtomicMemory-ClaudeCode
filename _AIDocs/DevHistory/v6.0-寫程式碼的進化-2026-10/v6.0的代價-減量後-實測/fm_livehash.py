"""fm_livehash.py — 量測前後核 live 程式沒被動：hooks/ lib/ tools/ skills/ settings.json workflow/config.json 逐檔 sha256 合成一個總雜湊。
怎麼跑：python -X utf8 fm_livehash.py [--live C:/Users/holylight/.claude] [--save <json>] [--diff <之前存的 json>]
尾行 FM_LIVEHASH DONE files=<n> digest=<前 16 碼> changed=<跟 --diff 比變了幾檔或 na>
"""
import argparse
import hashlib
import json
from pathlib import Path

PARTS = ("hooks", "lib", "tools", "skills")
FILES = ("settings.json", "workflow/config.json")
SKIP = ("__pycache__", "node_modules", "_vectordb")

ap = argparse.ArgumentParser()
ap.add_argument("--live", default="C:/Users/holylight/.claude")
ap.add_argument("--save")
ap.add_argument("--diff")
a = ap.parse_args()
live = Path(a.live)
paths = [live / f for f in FILES] + [p for d in PARTS for p in sorted((live / d).rglob("*"))
                                       if p.is_file() and not any(s in p.parts for s in SKIP)]
cur = {str(p.relative_to(live)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}
digest = hashlib.sha256(json.dumps(cur, sort_keys=True).encode()).hexdigest()
changed = "na"
if a.diff:
    old = json.loads(Path(a.diff).read_text(encoding="utf-8"))["files"]
    diff = sorted(k for k in set(old) | set(cur) if old.get(k) != cur.get(k))
    changed = len(diff)
    for k in diff:
        print(f"  變了：{k}")
if a.save:
    Path(a.save).write_text(json.dumps({"digest": digest, "files": cur}, ensure_ascii=False, indent=0), encoding="utf-8")
print(f"FM_LIVEHASH DONE files={len(cur)} digest={digest[:16]} changed={changed}")

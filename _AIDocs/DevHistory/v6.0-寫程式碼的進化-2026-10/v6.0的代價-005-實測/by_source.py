"""by_source.py — 每跑第一回合多出的 token 照來源（a1/a2/b/c/d1/d2|來源）列，004 R1/R2 對 005 現況三跑，平均並列（宣稱 vs 實際歸因用）。
怎麼跑：python by_source.py；尾行 BY_SOURCE DONE sources=<n>"""
import json
from collections import defaultdict
A = json.load(open("logs/ftb-004.json", encoding="utf-8"))
B = json.load(open("logs/ftb-005.json", encoding="utf-8"))
g004 = ["2026-10-23-CCon-R1", "2026-10-23-CCon-R2"]
g004x = ["2026-10-23-CCon-1", "2026-10-23-CCon-2", "2026-10-23-CCon-3"]
g005 = ["2026-10-27-005-CCon-1", "2026-10-27-005-CCon-2", "2026-10-27-005-CCon-3"]
tab = defaultdict(dict)
def add(d, runs, col):
    for k in {k for r in runs for k in d[r]["acc"] if not k.startswith("base")}:
        tab[k][col] = sum(d[r]["acc"].get(k, 0) for r in runs) / len(runs)
add(A, g004, "004R"); add(A, g004x, "004x"); add(B, g005, "005")
rows = sorted(tab.items(), key=lambda kv: -max(kv[1].values()))
print("| 類｜來源 | 004 R1/R2 平均 | 004 現況1～3 平均 | 005 現況1～3 平均 | 005−004R |")
print("|---|---|---|---|---|")
for k, v in rows:
    a, x, b = v.get("004R", 0), v.get("004x", 0), v.get("005", 0)
    if max(a, x, b) < 3000: continue
    print(f"| {k} | {a/1e4:.2f} | {x/1e4:.2f} | {b/1e4:.2f} | {(b-a)/1e4:+.2f} |")
print(f"BY_SOURCE DONE sources={len(rows)}")

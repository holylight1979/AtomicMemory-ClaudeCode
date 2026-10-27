"""main_table.py — 主表數字：讀 004 與 005 的串跑總表（_fm-series-<日>.json）與各跑 _fm/measure.json，印逐跑原始數、各組平均、倍數、回合別輸入平均。
怎麼跑：python main_table.py；尾行 MAIN_TABLE DONE runs=<n>
"""
import json
from pathlib import Path
RES = Path("C:/Users/holylight/.claude/workflow/inbox/wave2-kit/results")
rows = []
for day in ("2026-10-23", "2026-10-27-005"):
    for r in json.loads((RES / f"_fm-series-{day}.json").read_text(encoding="utf-8")):
        m = json.loads((RES / r["name"] / "_fm" / "measure.json").read_text(encoding="utf-8"))
        r["segs"] = {k: [(t["in"], t["out"], t["wall_s"]) for t in v["turns"]] for k, v in m["segments"].items()}
        rows.append(dict(r, day=day))
avg = lambda xs: sum(xs) / len(xs) if xs else float("nan")
for r in rows:
    t = r["total"]
    print(f"{r['name']:<24} in={t['in']:>9,} out={t['out']:>7,} wall={t['wall_s']:>5.0f} turns={t['num_turns']:>3} calls={t['api_calls']:>3} deny={t['denials']} "
          f"cost={t['cost']:.2f} void={r['void']} segs={ {k: [x[0] for x in v] for k, v in r['segs'].items()} }")
grp = {}
for r in rows:
    if not r["void"]:
        grp.setdefault((r["day"], r["cls"], r["grp"]), []).append(r)
print()
for (day, cls, g), rs in sorted(grp.items()):
    f = lambda k: avg([x["total"][k] for x in rs])
    seg_avg = {}
    for x in rs:
        for k, v in x["segs"].items():
            for i, t in enumerate(v):
                seg_avg.setdefault(f"{k}t{i+1}", []).append(t[0])
    print(f"{day} {cls} {g} n={len(rs)} in={f('in')/1e4:.1f}萬 out={f('out')/1e4:.2f}萬 io={(f('in')+f('out'))/1e4:.1f}萬 wall={f('wall_s')/60:.2f}分 "
          f"turns={f('num_turns'):.1f} deny={f('denials'):.1f} cost={f('cost'):.2f} seg_in={ {k: round(avg(v)/1e4,1) for k, v in seg_avg.items()} }")
print(f"MAIN_TABLE DONE runs={len(rows)}")

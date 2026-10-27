"""ftb_split.py — 從 first_turn_breakdown --json 拆「少叫幾次」與「每次少多少」：每跑額外呼叫次數（a／d）、a1+d1 合計與每次平均、
b（擋訊息被重讀）、c（注入被重讀）、a2+d2（額外呼叫留下的內容被重讀）、e（其餘）。
怎麼跑：python ftb_split.py <ftb.json> <run>…；尾行 FTB_SPLIT DONE runs=<n>
"""
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
off = d["_meta"]["off_avg"]
for run in sys.argv[2:]:
    r = d[run]
    n_extra = sum(1 for c in r["cls"] if c in ("a", "d"))
    s = {"a1": 0.0, "d1": 0.0, "a2": 0.0, "d2": 0.0, "b": 0.0, "c": 0.0, "base": 0.0}
    for k, v in r["acc"].items():
        cat = k.split("|")[0]
        s[cat] = s.get(cat, 0.0) + v
    ex = r["total"] - off
    e = ex - (s["a1"] + s["d1"] + s["a2"] + s["d2"] + s["b"] + s["c"])
    per = (s["a1"] + s["d1"]) / n_extra if n_extra else 0
    print(f"{run} calls={r['calls']} extra={n_extra} (a={r['cls'].count('a')} d={r['cls'].count('d')}) a1d1={(s['a1']+s['d1'])/1e4:.1f}萬 "
          f"per_call={per/1e4:.2f}萬 a2d2={(s['a2']+s['d2'])/1e4:.1f} b={s['b']/1e4:.1f} c={s['c']/1e4:.1f} e={e/1e4:.1f} extra_total={ex/1e4:.1f} total={r['total']/1e4:.1f} off={off/1e4:.1f}")
print(f"FTB_SPLIT DONE runs={len(sys.argv) - 2}")

"""rj_table.py — 重新判分的 token／耗時表：讀各跑 _fm/measure.json，印逐跑原始數、平均、各回合輸入，跟 004 的全關／現況平均並列。
怎麼跑：python -X utf8 rj_table.py [--new 2026-10-23-CCon-R1,2026-10-23-CCon-R2] [--json <輸出>]
尾行 RJ_TABLE DONE new=<跑數> in_avg=<萬> out_avg=<萬> wall_avg=<分> vs_on_in=<相對 004 現況%> vs_off_in=<相對 004 全關%>
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

RES = Path.home() / ".claude" / "workflow" / "inbox" / "wave2-kit" / "results"
OLD_OFF = [f"2026-10-23-CCoff-{n}" for n in (1, 2, 3)]
OLD_ON = [f"2026-10-23-CCon-{n}" for n in (1, 2, 3)]
STAGE = {("B-1", "first"): "第一段：加子命令", ("B-1", "final"): "第一段：交材料", ("B-2", "first"): "第二段：新 session 問狀況"}


def load(name):
    d = json.loads((RES / name / "_fm" / "measure.json").read_text(encoding="utf-8"))
    tot = d["run"]["total"]
    stages = defaultdict(int)
    for seg, sm in d["segments"].items():
        for t in sm["turns"]:
            stages[STAGE.get((seg, t["id"]), f"{seg}:{t['id']}")] += t["in"]
    return {"name": name, "void": d["run"]["void"], "why": d["run"]["why"], "in": tot["in"], "out": tot["out"],
            "wall_s": tot["wall_s"], "num_turns": tot["num_turns"], "api_calls": tot["api_calls"], "denials": tot["denials"],
            "cost": tot["cost"], "hook_cancelled": tot["hook_cancelled"], "hook_traces": d["run"]["hook_traces"],
            "effort": d["run"]["effort"], "stages": dict(stages)}


def avg(rows, k):
    return sum(r[k] for r in rows) / len(rows)


def stage_avg(rows):
    keys = sorted({k for r in rows for k in r["stages"]}, key=lambda k: list(STAGE.values()).index(k) if k in STAGE.values() else 99)
    return {k: sum(r["stages"].get(k, 0) for r in rows) / len(rows) for k in keys}


def pct(a, b):
    return (a - b) / b * 100


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--new", default="2026-10-23-CCon-R1,2026-10-23-CCon-R2")
    ap.add_argument("--json")
    a = ap.parse_args()
    off, on = [load(n) for n in OLD_OFF], [load(n) for n in OLD_ON]
    new = [load(n) for n in a.new.split(",")]
    print("| 跑 | 輸入 | 輸出 | 牆鐘（秒） | 模型輪數 | 模型呼叫 | 被拒 | 美金 | hook 痕跡 | effort | 作廢 |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in off + on + new:
        print(f"| {r['name'][11:]} | {r['in']:,} | {r['out']:,} | {r['wall_s']:.0f} | {r['num_turns']} | {r['api_calls']} | {r['denials']} | "
              f"{r['cost']:.2f} | {r['hook_traces']} | {r['effort']} | {r['why'] or '否'} |")
    groups = {"004 全關平均": off, "004 現況平均": on, "這次現況平均": new}
    print()
    for g, rows in groups.items():
        print(f"{g}: in={avg(rows, 'in') / 1e4:.1f}萬 out={avg(rows, 'out') / 1e4:.2f}萬 wall={avg(rows, 'wall_s') / 60:.1f}分 "
              f"turns={avg(rows, 'num_turns'):.1f} denials={avg(rows, 'denials'):.1f} cost={avg(rows, 'cost'):.2f} stages="
              + json.dumps({k: round(v / 1e4, 1) for k, v in stage_avg(rows).items()}, ensure_ascii=False))
    ni, no, nw = avg(new, "in"), avg(new, "out"), avg(new, "wall_s")
    for g in ("004 全關平均", "004 現況平均"):
        rows = groups[g]
        tok_old = avg(rows, "in") + avg(rows, "out")
        print(f"這次 vs {g}: 輸入 {pct(ni, avg(rows, 'in')):+.0f}% 輸出 {pct(no, avg(rows, 'out')):+.0f}% "
              f"輸入＋輸出 {pct(ni + no, tok_old):+.0f}% 牆鐘 {pct(nw, avg(rows, 'wall_s')):+.0f}%")
    if len(new) >= 2:
        t = [r["in"] + r["out"] for r in new[:2]]
        w = [r["wall_s"] for r in new[:2]]
        print(f"R1 vs R2 相差：token {abs(t[0] - t[1]) / (sum(t) / 2):.0%} 牆鐘 {abs(w[0] - w[1]) / (sum(w) / 2):.0%}")
    if a.json:
        Path(a.json).write_text(json.dumps({"off": off, "on": on, "new": new}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"RJ_TABLE DONE new={len(new)} in_avg={ni / 1e4:.1f} out_avg={no / 1e4:.2f} wall_avg={nw / 60:.1f} "
          f"vs_on_in={pct(ni, avg(on, 'in')):+.0f}% vs_off_in={pct(ni, avg(off, 'in')):+.0f}%")


if __name__ == "__main__":
    main()

"""compare_inject.py — 對帳 replay_inject.py 的兩份輸出：main 重播 vs transcript 逐字比（重播可信度），分支 vs main 量砍後。

怎麼跑：python -X utf8 compare_inject.py <replay_main.json> <replay_branch.json>
token 估算＝量尺 first_turn_breakdown.py 的式子 1.321×中日韓字＋0.534×其他字（每段 −8.8 兩邊段數相同、相減抵消）。
第一回合輸入少多少＝每次呼叫少的 × 第一回合呼叫次數（記憶卡段在每一次呼叫的輸入裡）；c 類＝× 照常呼叫次數（量尺口徑）。
"""
import json
import sys
from datetime import datetime
from pathlib import Path

RES = Path(r"C:\Users\holylight\.claude\workflow\inbox\wave2-kit\results")
NORMAL = {"2026-10-23-CCon-R1": 11, "2026-10-23-CCon-R2": 12}   # 量尺：R1 22 次（額外 11）、R2 24 次（額外 12）


def est(t):
    cjk = sum(1 for ch in t if ord(ch) >= 0x2E80)
    return 1.321 * cjk + 0.534 * (len(t) - cjk)


def transcript(run):
    p = next((RES / run / "B-1" / "transcript").glob("*.jsonl"))
    rows = [json.loads(line) for line in p.open(encoding="utf-8")]
    ups = []
    for r in rows:
        a = r.get("attachment") or {}
        if r.get("type") == "attachment" and a.get("type") == "hook_additional_context" and a.get("hookEvent") == "UserPromptSubmit":
            text = "\n".join(a.get("content") or [])
            s, e = text.find("[Atom:"), text.rfind("\n[Context budget")
            ups.append(text[s:e] if s >= 0 else "")
    meta = json.loads((RES / run / "B-1" / "turns" / "B-1-t1.json").read_text(encoding="utf-8"))["_meta"]
    end = datetime.fromisoformat(meta["ended"])
    ids, n1 = set(), 0
    for r in rows:
        if r.get("type") == "assistant" and r["message"].get("id") not in ids:
            ids.add(r["message"].get("id"))
            ts = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
            n1 += ts <= end
    return ups, n1


main = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
branch = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
fidelity = True
tot = {}
for run in main:
    ups, n1 = transcript(run)
    print(f"== {run}  第一回合呼叫 {n1} 次")
    for t in ("t1", "t2"):
        m, b = "\n".join(main[run][t]["blocks"]), "\n".join(branch[run][t]["blocks"])
        same = m == ups[int(t[1]) - 1]
        fidelity &= same
        d = est(m) - est(b)
        print(f"  {t} intent={main[run][t]['intent']} main重播==transcript:{same}  估 main {est(m):.0f} → 分支 {est(b):.0f}  每次呼叫少 {d:.0f}")
        print("    分支 forms:", [(n[:24], s, f) for n, s, f in branch[run][t]["forms"]])
        if t == "t1":
            tot[run] = (d, n1)
    for blk in branch[run]["t1"]["blocks"]:
        print("    分支 t1 區塊：", blk.split("\n", 1)[0][:160])
print("== 第一回合合計")
for run, (d, n1) in tot.items():
    c = f"，c 類（照常呼叫 {NORMAL[run]} 次）少 {d * NORMAL[run]:.0f}" if run in NORMAL else ""
    print(f"  {run}: 每次少 {d:.0f} × {n1} 次 ＝ 第一回合輸入少 {d * n1:.0f}{c}")
d_main = [tot[r][0] * tot[r][1] for r in NORMAL]
print(f"INJECT_REPLAY DONE fidelity={'ok' if fidelity else 'MISMATCH'} r1_saved={d_main[0]:.0f} r2_saved={d_main[1]:.0f} "
      f"avg_saved={sum(d_main) / 2:.0f}")

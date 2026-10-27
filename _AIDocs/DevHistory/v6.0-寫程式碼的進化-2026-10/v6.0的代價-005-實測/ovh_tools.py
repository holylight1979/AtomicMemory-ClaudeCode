"""ovh_tools.py — 每跑第一回合：定位閘擋下的是哪種工具（Write／Edit／Bash 寫檔），以及 AI 第一次寫 sales/ 程式檔用什麼工具、那次有沒有被擋。
怎麼跑：python ovh_tools.py <跑名>…"""
import json, glob, sys, re
from collections import Counter
R = "C:/Users/holylight/.claude/workflow/inbox/wave2-kit/results/"
for run in sys.argv[1:]:
    tx = glob.glob(R + run + "/B-1/transcript/*.jsonl")[0]
    recs = [json.loads(l) for l in open(tx, encoding="utf-8")]
    uses, denied = {}, {}
    t = 0
    for r in recs:
        m = r.get("message") or {}
        if r.get("type") == "user" and isinstance(m.get("content"), str) and not r.get("isMeta"):
            t += 1
        if t != 1 or not isinstance(m.get("content"), list):
            continue
        for c in m["content"]:
            if c.get("type") == "tool_use":
                uses[c["id"]] = (c["name"], json.dumps(c["input"], ensure_ascii=False))
            if c.get("type") == "tool_result":
                txt = c.get("content") if isinstance(c.get("content"), str) else json.dumps(c.get("content"), ensure_ascii=False)
                if "PreToolUse" in txt and "hook error" in txt:
                    denied[c["tool_use_id"]] = re.findall(r"\[Guardian:(\w+)\]|\[(NeedGoal)\]", txt)[:1]
    ovh = Counter(uses[i][0] for i, g in denied.items() if i in uses and g and "OverviewHub" in g[0])
    first = next(((i, n, s) for i, (n, s) in uses.items() if re.search(r"sales[\/]+\w+\.py", s) and
                  (n in ("Write", "Edit") or (n == "Bash" and re.search(r"cat >|open\(|write_text|>\s*sales", s)))), None)
    fd = "被擋" if first and first[0] in denied else "沒擋"
    print(run, "定位閘擋下的工具", dict(ovh), "｜第一次寫 sales/ 程式：", (first[1] + " " + fd + " " + first[2][:80]) if first else "無")

"""loc_where.py — 表 6 核對：第二次擋到第三次擋之間（transcript 行區間），AI 的 text／thinking 有沒有寫「定位｜」、用了哪些工具。
怎麼跑：python loc_where.py <跑名> <起行> <迄行>"""
import json, glob, sys
R = "C:/Users/holylight/.claude/workflow/inbox/wave2-kit/results/"
tx = glob.glob(R + sys.argv[1] + "/B-1/transcript/*.jsonl")[0]
a, b = int(sys.argv[2]), int(sys.argv[3])
for i, l in enumerate(open(tx, encoding="utf-8"), 1):
    if not (a <= i <= b):
        continue
    r = json.loads(l)
    if r.get("type") != "assistant":
        continue
    for c in r["message"].get("content") or []:
        t = c.get("type")
        if t == "text":
            print(i, "TEXT", ("有定位行 " if "定位｜" in c["text"] else ""), c["text"][:160].replace("\n", " / "))
        elif t == "thinking":
            th = c.get("thinking") or ""
            print(i, "THINK", len(th), ("有定位行" if "定位｜" in th else ""), "redacted" if not th else "")
        elif t == "tool_use":
            print(i, "TOOL", c["name"], json.dumps(c["input"], ensure_ascii=False)[:90])

"""blocktext.py — 照斷路器帳的 event（tool_use_id）到 transcript 撈擋訊息全文與 AI 同則／下一則的文字與工具呼叫（表 6 核對用）。
怎麼跑：python blocktext.py <跑名> <帳行號>…"""
import json, glob, sys
R = "C:/Users/holylight/.claude/workflow/inbox/wave2-kit/results/"
run = sys.argv[1]
led = glob.glob(R + run + "/_fm/root-Logs/chain-*.jsonl")[0]
rows = [json.loads(l) for l in open(led, encoding="utf-8")]
tx = glob.glob(R + run + "/B-1/transcript/*.jsonl")[0]
recs = [json.loads(l) for l in open(tx, encoding="utf-8")]
for ln in map(int, sys.argv[2:]):
    ev = rows[ln - 1]["event"]
    for i, r in enumerate(recs):
        for c in ((r.get("message") or {}).get("content") or []) if isinstance((r.get("message") or {}).get("content"), list) else []:
            if c.get("type") == "tool_result" and c.get("tool_use_id") == ev:
                t = c.get("content")
                t = t if isinstance(t, str) else json.dumps(t, ensure_ascii=False)
                print(f"===== {run} 帳:{ln} transcript:{i+1}\n{t[:1600]}\n")
            if c.get("type") == "tool_use" and c.get("id") == ev:
                print(f"----- 被擋的呼叫 transcript:{i+1} {c['name']} {json.dumps(c['input'], ensure_ascii=False)[:200]}")
                # 同則前面的文字
                for j in range(max(0, i - 3), i + 1):
                    for cc in (recs[j].get("message") or {}).get("content") or []:
                        if isinstance(cc, dict) and cc.get("type") == "text":
                            print(f"   [AI 文字 transcript:{j+1}] {cc['text'][:500]}")

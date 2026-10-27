"""offchk.py — 全關組第一回合：transcript 依 message.id 合併的輸入合計 vs 回合 JSON usage，找差額來源（子代理、未落 transcript 的呼叫）。"""
import json, glob, sys
R = "C:/Users/holylight/.claude/workflow/inbox/wave2-kit/results/"
for run in sys.argv[1:]:
    tj = glob.glob(R + run + "/**/B-1-t1.json", recursive=True)
    d = json.load(open(tj[0], encoding="utf-8"))
    u = d.get("usage") or {}
    tot = sum(int(u.get(k) or 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    mu = {k: sum(int(v.get(x) or 0) for x in ("inputTokens", "cacheReadInputTokens", "cacheCreationInputTokens")) for k, v in (d.get("modelUsage") or {}).items()}
    tx = glob.glob(R + run + "/B-1/transcript/*.jsonl")[0]
    seen, calls, tools = {}, 0, []
    for l in open(tx, encoding="utf-8"):
        r = json.loads(l)
        if r.get("type") != "assistant":
            continue
        m = r["message"]
        for c in m.get("content") or []:
            if c.get("type") == "tool_use":
                tools.append(c["name"])
        uu = m.get("usage") or {}
        seen[m.get("id")] = sum(int(uu.get(k) or 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    print(run, "turns_usage", tot, "modelUsage", mu, "num_turns", d.get("num_turns"), "tx_calls", len(seen), "tx_in", sum(seen.values()), "tools", tools)

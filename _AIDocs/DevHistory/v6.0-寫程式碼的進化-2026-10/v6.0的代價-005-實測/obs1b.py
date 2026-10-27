"""obs1b.py — 觀察 1 細分：第一段每個使用者回合裡 anti_evasion_report、PickOne 提示、SyncReminder 擋各出現在第幾回合。"""
import json, glob, sys
R = "C:/Users/holylight/.claude/workflow/inbox/wave2-kit/results/"
for run in sys.argv[1:]:
    for tx in glob.glob(R + run + "/B-1/transcript/*.jsonl"):
        t, ev = 0, []
        for l in open(tx, encoding="utf-8"):
            r = json.loads(l)
            m = r.get("message") or {}
            if r.get("type") == "user" and isinstance(m.get("content"), str) and not r.get("isMeta"):
                t += 1
            if r.get("type") == "assistant":
                for c in m.get("content") or []:
                    if c.get("type") == "tool_use" and "anti_evasion_report" in c.get("name", ""):
                        ev.append(f"T{t}:aec@{r['timestamp'][11:19]}")
            a = r.get("attachment") or {}
            s = json.dumps(a, ensure_ascii=False)
            if a.get("type") == "hook_additional_context" and "[Guardian:PickOne]" in s:
                ev.append(f"T{t}:pick")
            if a.get("type") == "hook_blocking_error":
                g = s.split("[Guardian:")[1].split("]")[0] if "[Guardian:" in s else "?"
                ev.append(f"T{t}:stopblock:{g}@{r['timestamp'][11:19]}")
        print(run, " ".join(ev))

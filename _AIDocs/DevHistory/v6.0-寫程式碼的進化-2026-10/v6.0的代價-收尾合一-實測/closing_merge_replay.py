"""closing_merge_replay.py — 收尾三段合一這一刀的砍前→砍後（只讀 004 實跑帳，事件帳重播）。

做什麼：
  1. 每跑 B-1 的 transcript，第一個使用者回合：assistant 列依 message.id 合成一次模型呼叫；輸入 T＝input＋cache_creation＋cache_read
     （usage，實測，同 first_turn_breakdown.py 口徑）；秒＝這次呼叫前最後一筆 api-request 列到這次回應最後一列（實測）。
  2. 收尾呼叫＝這次呼叫的工具全是收尾類：need_goal(action=reconcile)、anti_evasion_report、knowledge_harvest_report，
     或載入的全是收尾檢核／收割報告的 ToolSearch（可夾一段文字；跟 need_goal 一起在開頭載入的不算）。砍前＝收尾呼叫幾次（同一次呼叫裡平行叫兩支只算一次）。
  3. 砍後重播（合一後的走法：anti_evasion_report 一次帶 reconcile 與 harvest_items）：
     嚴格＝照這跑實際載入工具的時點——收尾檢核在第一次收尾呼叫之前已經載入 → 收尾只剩 1 次；同一批才載入 → 載入 1 次＋交 1 次＝2 次。
     提早載入＝照工具說明的新提示（還沒載入就趁別的工具呼叫同一批先載入）→ 1 次。
     省下的是最早的那幾次收尾呼叫：省的重讀量＝那幾次的 T 加總，省的秒＝那幾次的秒加總。
     沒算進去的（偏保守）：被拿掉那次自己的思考與文字輸出、工具呼叫外殼，之後每次呼叫的輸入也少這一點。
  4. 收尾類的 Stop 擋（ScanReport／ReconcileGate (f2)／KnowledgeHarvest）次數：數 hook_blocking_error 裡這幾個標籤。
怎麼跑：python -X utf8 closing_merge_replay.py [run ...]（預設 2026-10-23-CCon-R1 2026-10-23-CCon-R2；CM_BASE 指 results 根）
尾行：CLOSING_MERGE DONE k=v …
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(os.environ.get("CM_BASE", r"C:\Users\holylight\.claude\workflow\inbox\wave2-kit\results"))
NG = "mcp__workflow-guardian__need_goal"
AEC = "mcp__workflow-guardian__anti_evasion_report"
HV = "mcp__workflow-guardian__knowledge_harvest_report"
CLOSING_LOAD = ("anti_evasion_report", "knowledge_harvest_report")
STOP_TAGS = ("[Guardian:ScanReport]", "(f2)", "[Guardian:KnowledgeHarvest]")


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def first_turn_calls(path):
    """→ [{id, T, out, secs, tools:[(name, input)], text}]，只到第二個使用者 prompt 之前。"""
    rows = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    calls, by_id, last_req, prompts, stops = [], {}, None, 0, 0
    for r in rows:
        t, m = r.get("type"), r.get("message") or {}
        if t == "user" and isinstance(m.get("content"), str) and not m["content"].startswith("Stop hook feedback"):
            prompts += 1
            if prompts > 1:
                break
        if t == "api-request" and r.get("timestamp"):
            last_req = ts(r["timestamp"])
        if t == "attachment" and (r.get("attachment") or {}).get("type") == "hook_blocking_error":
            s = json.dumps(r["attachment"], ensure_ascii=False)
            stops += any(tag in s for tag in STOP_TAGS)
        if t != "assistant":
            continue
        mid = m.get("id")
        if mid not in by_id:
            by_id[mid] = {"id": mid, "tools": [], "text": False, "start": last_req, "end": None}
            calls.append(by_id[mid])
        c = by_id[mid]
        u = m.get("usage") or {}
        c["T"] = u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
        c["out"] = u.get("output_tokens", 0)
        c["end"] = ts(r["timestamp"]) if r.get("timestamp") else c["end"]
        for b in m.get("content") or []:
            if b.get("type") == "tool_use":
                c["tools"].append((b["name"], b.get("input") or {}))
            elif b.get("type") == "text":
                c["text"] = True
    for c in calls:
        c["secs"] = round(c["end"] - c["start"], 1) if c["start"] and c["end"] else 0.0
    return calls, stops


def is_closing_tool(name, inp):
    if name == NG:
        return inp.get("action") == "reconcile"
    if name in (AEC, HV):
        return True
    if name != "ToolSearch":
        return False
    picked = [p.strip() for p in str(inp.get("query") or "").removeprefix("select:").split(",") if p.strip()]
    return bool(picked) and all(any(p.endswith(k) for k in CLOSING_LOAD) for p in picked)   # 跟 need_goal 一起早載入的不算


def loads_aec(name, inp):
    return name == "ToolSearch" and "anti_evasion_report" in str(inp.get("query"))


def replay(run):
    tp = next((BASE / run / "B-1" / "transcript").glob("*.jsonl"))
    calls, stops = first_turn_calls(tp)
    closing = [i for i, c in enumerate(calls) if c["tools"] and all(is_closing_tool(n, x) for n, x in c["tools"])]
    if not closing:
        return {"run": run, "before": 0, "strict": 0, "preload": 0, "saved_T_strict": 0, "saved_T_preload": 0,
                "saved_s_strict": 0.0, "saved_s_preload": 0.0, "stops": stops, "rows": []}
    loaded_before = any(loads_aec(n, x) for c in calls[:closing[0]] for n, x in c["tools"])
    strict = 1 if loaded_before else 2
    before = len(closing)

    def saved(after):
        # 合一後留最後一次（交收尾檢核）；嚴格且沒提早載入時另留第一次（只剩載入）
        gone = closing[:-1] if after == 1 else closing[1:-1]
        return sum(calls[i]["T"] for i in gone), round(sum(calls[i]["secs"] for i in gone), 1)
    st_T, st_s = saved(min(strict, before))
    pl_T, pl_s = saved(1)
    rows = [(i, calls[i]["T"], calls[i]["out"], calls[i]["secs"],
             "+".join(n.split("__")[-1] + (f"({x.get('action')})" if n == NG else "") for n, x in calls[i]["tools"]))
            for i in closing]
    return {"run": run, "before": before, "strict": min(strict, before), "preload": 1, "saved_T_strict": st_T,
            "saved_T_preload": pl_T, "saved_s_strict": st_s, "saved_s_preload": pl_s, "stops": stops, "rows": rows,
            "loaded_before": loaded_before, "turn_T": sum(c["T"] for c in calls), "turn_calls": len(calls)}


def main():
    runs = sys.argv[1:] or ["2026-10-23-CCon-R1", "2026-10-23-CCon-R2"]
    res = [replay(r) for r in runs]
    print("| 跑 | 第一回合呼叫數／輸入合計 | 收尾呼叫（第幾次呼叫、T、輸出、秒、工具） | 收尾檢核提早載入 | 砍前 | 砍後 嚴格／提早載入 | 省 T 嚴格／提早載入 | 省秒 嚴格／提早載入 | 收尾類 Stop 擋 |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in res:
        detail = "；".join(f"#{i} T={T} out={o} {s}s {n}" for i, T, o, s, n in r["rows"]) or "無"
        print(f"| {r['run']} | {r.get('turn_calls', 0)}／{r.get('turn_T', 0)} | {detail} | {'是' if r.get('loaded_before') else '否'} | "
              f"{r['before']} | {r['strict']}／{r['preload']} | {r['saved_T_strict']}／{r['saved_T_preload']} | "
              f"{r['saved_s_strict']}／{r['saved_s_preload']} | {r['stops']} |")
    kv = {}
    for r in res:
        tag = r["run"].rsplit("-", 1)[-1]
        kv.update({f"{tag}_before": r["before"], f"{tag}_after_strict": r["strict"], f"{tag}_after_preload": r["preload"],
                   f"{tag}_saved_T_strict": r["saved_T_strict"], f"{tag}_saved_T_preload": r["saved_T_preload"],
                   f"{tag}_saved_s_strict": r["saved_s_strict"], f"{tag}_saved_s_preload": r["saved_s_preload"],
                   f"{tag}_stops": r["stops"]})
    print("CLOSING_MERGE DONE " + " ".join(f"{k}={v}" for k, v in kv.items()))


if __name__ == "__main__":
    main()

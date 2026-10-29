"""逐例列出：改前窗根層，收尾擋下後到下一次收尾之間有改程式／文件的例子（「真的抓到問題」的候選）。
跑法：python -X utf8 catch_cases.py
每例印：session、時間、第一個閘、✗ 規則行、擋下後模型第一段文字、改了哪些檔。
"""
import glob, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stop_measure as sm

GATES = {"Guardian:ReconcileGate", "Guardian:MeasureGate", "Guardian:AtomAudit", "Guardian:ScanReport",
         "Guardian:VerifyScope", "Guardian:KnowledgeHarvest"}


def scan(fp):
    """事件序列：turn / block / tool / text（assistant 文字）"""
    ev, seen = [], set()
    with open(fp, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("isSidechain"):
                continue
            ts = (d.get("timestamp") or "")[:19]
            a = d.get("attachment")
            if d.get("type") == "attachment" and isinstance(a, dict) and a.get("type") == "hook_blocking_error" and a.get("hookEvent") == "Stop":
                be = a.get("blockingError")
                text = be.get("blockingError", "") if isinstance(be, dict) else str(be)
                if (ts, text) in seen:
                    continue
                seen.add((ts, text))
                ev.append(("block", ts, text))
            elif d.get("type") == "user" and isinstance(d.get("message"), dict):
                if sm.user_text(d["message"]):
                    ev.append(("turn", ts))
            elif d.get("type") == "assistant" and isinstance(d.get("message"), dict):
                for b in d["message"].get("content") or []:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "tool_use" and ("t", b.get("id")) not in seen:
                        seen.add(("t", b.get("id")))
                        ev.append(("tool", ts, b.get("name", ""), b.get("input") or {}))
                    elif b.get("type") == "text" and b.get("text", "").strip():
                        ev.append(("text", ts, b["text"]))
    return ev


def main():
    n = 0
    for fp in sorted(glob.glob(sm.ROOT + "/*/*.jsonl")):
        proj = os.path.basename(os.path.dirname(fp))
        if not proj.lower().startswith("c--users-holylight--claude"):
            continue
        ev = scan(fp)
        sid = os.path.basename(fp)[:8]
        cur = None
        for e in ev + [("turn", "9999")]:
            if e[0] in ("turn", "block"):
                if cur:
                    edits = [p for p in cur["edits"] if sm.path_kind(p) == "code_doc"]
                    if edits and cur["gate"] in GATES:
                        n += 1
                        print(f"\n#{n} [{cur['gate']}] {sid} {cur['ts']}")
                        for r in cur["rules"]:
                            print("   規則:", r[:220])
                        if not cur["rules"]:
                            print("   訊息:", cur["text"][:300].replace("\n", " ｜ "))
                        print("   模型回應:", (cur["first_text"] or "(無文字)")[:350].replace("\n", " ｜ "))
                        print("   改檔:", sorted({os.path.basename(p) for p in edits}))
                    cur = None
                if e[0] == "block" and sm.W0 <= e[1] < sm.W1:
                    m = sm.TAG.search(e[2])
                    cur = dict(gate=m.group(1) if m else "", ts=e[1], text=e[2], edits=[], first_text="",
                               rules=re.findall(r"✗ \(\w+\) [^\n]+", e[2]))
                continue
            if not cur:
                continue
            if e[0] == "text" and not cur["first_text"]:
                cur["first_text"] = e[2]
            elif e[0] == "tool" and e[2] in ("Edit", "Write", "NotebookEdit"):
                cur["edits"].append(e[3].get("file_path", ""))
    print(f"\nCATCH_CASES DONE cases={n}")


if __name__ == "__main__":
    main()

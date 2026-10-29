"""收尾擋下重量：掃 projects/**/*.jsonl（排除 subagents），分改前／改後兩窗出同口徑數字。
跑法：python -X utf8 stop_measure.py [--json out.json]
"""
import json, re, sys, glob, os
from collections import Counter, defaultdict
from datetime import datetime, timezone

ROOT = r"C:/Users/holylight/.claude/projects"
W0 = "2026-10-14T00:00:00"
W1 = "2026-10-16T05:20:00"
STRIP = re.compile(r"<(system-reminder|task-notification|cross-session-message|ide_[a-z_]+)[^>]*>.*?</\1>", re.S)
TAG = re.compile(r"\[(Guardian:[A-Za-z]+|Workflow Guardian|驗收裁判|receipt)\]")
VS_KINDS = ["改完要重跑", "最近一次跑紅", "沒有跑這一項", "還沒宣告驗證範圍", "還沒宣告由哪個案例驗"]
RITUAL = {"Guardian:KnowledgeHarvest", "Guardian:ScanReport", "Guardian:AtomAudit"}


def win(ts):
    if ts < W0:
        return None
    return "before" if ts < W1 else "after"


def user_text(msg):
    c = msg.get("content")
    if isinstance(c, str):
        texts = [c]
    elif isinstance(c, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c):
            return ""
        texts = [b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text"]
    else:
        return ""
    t = "\n".join(texts)
    if t.lstrip().startswith("Stop hook feedback"):
        return ""
    return STRIP.sub("", t).strip()


def path_kind(p):
    p = (p or "").replace("\\", "/").lower()
    if "/temp/" in p or "scratchpad" in p:
        return "scratch"
    if "/memory/" in p:
        return "memory"
    return "code_doc"


def scan_file(fp, proj):
    """回傳事件序列：('turn', ts) / ('block', ts, text) / ('tool', ts, name, input)"""
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
            if not ts:
                continue
            a = d.get("attachment")
            if d.get("type") == "attachment" and isinstance(a, dict) and a.get("type") == "hook_blocking_error" and a.get("hookEvent") == "Stop":
                be = a.get("blockingError")
                text = be.get("blockingError", "") if isinstance(be, dict) else str(be)
                key = (ts, text)
                if key in seen:
                    continue
                seen.add(key)
                ev.append(("block", ts, text))
            elif d.get("type") == "user" and isinstance(d.get("message"), dict):
                if user_text(d["message"]):
                    ev.append(("turn", ts))
            elif d.get("type") == "assistant" and isinstance(d.get("message"), dict):
                for b in d["message"].get("content") or []:
                    if isinstance(b, dict) and b.get("type") == "tool_use":
                        key = ("tool", b.get("id"))
                        if key in seen:
                            continue
                        seen.add(key)
                        ev.append(("tool", ts, b.get("name", ""), b.get("input") or {}))
    return ev


def new_stats():
    return dict(turns=0, blocked_turns=0, blocks=0, gate=Counter(), chain=Counter(), same_gate_2plus=0,
                vs_block=Counter(), vs_item=Counter(), vs_first_tag=Counter(), rp_attached=0, rp_timeout=0,
                rp_followups=[], manual_rp=0, after=defaultdict(Counter), vs_items=0, vs_items_dep=0,
                vs_decl=0, vs_decl_dep=0, ts_min="9999", ts_max="0000", gate_turns=Counter(),
                cont_sec=Counter(), cont_list=[], rules=Counter(), rerun_after=Counter(), edit_after=Counter(), active_sec=0.0, sessions=Counter())


def classify_after(actions):
    """擋下之後、下一則擋下或使用者回合之前，模型做了什麼。"""
    kinds = set()
    for name, inp, _ts in actions:
        if name in ("Edit", "Write", "NotebookEdit"):
            kinds.add("edit_" + path_kind(inp.get("file_path")))
        elif name.endswith("atom_write"):
            kinds.add("atom_write")
        elif name == "Bash" or name == "PowerShell":
            cmd = inp.get("command", "")
            if re.search(r"pytest|run_verify|verify_|_CHECK|--check", cmd):
                kinds.add("run_test")
            elif re.search(r"\bgit (commit|push)", cmd):
                kinds.add("git")
            else:
                kinds.add("shell_other")
        elif name.startswith("mcp__workflow-guardian__"):
            kinds.add("mcp:" + name.split("__")[-1])
        elif name == "AskUserQuestion":
            kinds.add("ask_user")
        else:
            kinds.add("other:" + name)
    return kinds


def main():
    S = {"root": {"before": new_stats(), "after": new_stats()}, "other": {"before": new_stats(), "after": new_stats()}}
    files = [p for p in glob.glob(ROOT + "/*/*.jsonl")]
    for fp in files:
        proj = os.path.basename(os.path.dirname(fp))
        if proj.startswith("_"):
            continue
        grp = "root" if proj.lower().startswith("c--users-holylight--claude") else "other"
        ev = scan_file(fp, proj)
        ev.sort(key=lambda e: e[1])
        sid = os.path.basename(fp)[:8]
        cur_win, cur_gates, cur_blocks = None, Counter(), 0
        pend = None  # (gate set, win, ts, text, actions)

        def flush_pending():
            nonlocal pend
            if pend:
                gates, w, ts, text, acts = pend
                st = S[grp][w]
                kinds = classify_after(acts)
                end = max([a[2] for a in acts] or [ts])
                secs = (datetime.fromisoformat(end) - datetime.fromisoformat(ts)).total_seconds()
                first = TAG.search(text)
                fg = first.group(1) if first else "(無標籤)"
                st["cont_sec"][fg] += secs
                st["cont_sec"]["_all"] += secs
                st["cont_list"].append((round(secs / 60), fg, sid, ts, len(acts), sum(1 for a in acts if a[0] in ("Bash", "PowerShell") and re.search(r"pytest|run_verify", a[1].get("command", "")))))
                if "run_test" in kinds:
                    st["rerun_after"][fg] += 1
                if "edit_code_doc" in kinds:
                    st["edit_after"][fg] += 1
                for g in gates:
                    for k in kinds or {"text_only"}:
                        st["after"][g][k] += 1
                    st["after"][g]["_n"] += 1
                if "[Guardian:ReadingPath]" in text:
                    handled = any(
                        (n in ("Bash", "PowerShell") and "reading-path" in inp.get("command", ""))
                        or (n in ("Edit", "Write") and "reading" in (inp.get("file_path") or "").lower())
                        for n, inp, _ts in acts)
                    st["rp_followups"].append((sid, ts, handled, sorted(kinds)))
                pend = None

        def close_turn():
            nonlocal cur_gates, cur_blocks
            if cur_win:
                st = S[grp][cur_win]
                if cur_blocks:
                    st["blocked_turns"] += 1
                    st["chain"][cur_blocks] += 1
                    if any(v >= 2 for v in cur_gates.values()):
                        st["same_gate_2plus"] += 1
                    for g in cur_gates:
                        st["gate_turns"][g] += 1
            cur_gates, cur_blocks = Counter(), 0

        prev_ts = None
        for e in ev:
            ts = e[1]
            w_ev = win(ts)
            if w_ev and prev_ts and win(prev_ts) == w_ev:
                gap = (datetime.fromisoformat(ts) - datetime.fromisoformat(prev_ts)).total_seconds()
                if gap < 1800:
                    S[grp][w_ev]["active_sec"] += gap
            prev_ts = ts
            if e[0] == "turn":
                if win(ts):
                    S[grp][win(ts)]["sessions"][sid] += 1
                flush_pending()
                close_turn()
                cur_win = win(ts)
                if cur_win:
                    st = S[grp][cur_win]
                    st["turns"] += 1
                    st["ts_min"] = min(st["ts_min"], ts)
                    st["ts_max"] = max(st["ts_max"], ts)
                continue
            if cur_win is None:
                continue
            st = S[grp][cur_win]
            st["ts_max"] = max(st["ts_max"], ts)
            if e[0] == "block":
                flush_pending()
                text = e[2]
                m = TAG.search(text)
                g = m.group(1) if m else "(無標籤)"
                st["blocks"] += 1
                st["gate"][g] += 1
                cur_gates[g] += 1
                cur_blocks += 1
                all_tags = set(TAG.findall(text))
                for r in set(re.findall(r"✗ \(\w+\) ([A-Z][A-Z0-9_]+)", text)):
                    st["rules"][r] += 1
                if "[Guardian:ReadingPath]" in text:
                    st["rp_attached"] += 1
                    if "逾時" in text or "量不完" in text:
                        st["rp_timeout"] += 1
                hit = False
                for k in VS_KINDS:
                    n = text.count(k)
                    if n:
                        hit = True
                        st["vs_block"][k] += 1
                        st["vs_item"][k] += n
                if hit:
                    st["vs_first_tag"][g] += 1
                pend = (all_tags | {g}, cur_win, ts, text, [])
            elif e[0] == "tool":
                name, inp = e[2], e[3]
                if pend:
                    pend[4].append((name, inp, ts))
                if name in ("Bash", "PowerShell"):
                    cmd = inp.get("command", "")
                    if "reading-path.py" in cmd and "--before" in cmd:
                        st["manual_rp"] += 1
                if name.endswith("need_goal") and inp.get("action") == "verify_scope":
                    items = inp.get("items") or []
                    if isinstance(items, str):
                        try:
                            items = json.loads(items)
                        except Exception:
                            items = []
                    st["vs_decl"] += 1
                    nd = sum(1 for it in items if isinstance(it, dict) and it.get("depends"))
                    st["vs_items"] += len(items)
                    st["vs_items_dep"] += nd
                    if nd:
                        st["vs_decl_dep"] += 1
        flush_pending()
        close_turn()

    out = {}
    for grp, ws in S.items():
        for w, st in ws.items():
            lo = W0 if w == "before" else W1
            hi = W1 if w == "before" else st["ts_max"]
            days = (datetime.fromisoformat(hi) - datetime.fromisoformat(lo)).total_seconds() / 86400 if hi > lo else 0
            st["days"] = round(days, 2)
            st["window"] = f"{lo}Z ~ {hi}Z"
            out[f"{grp}/{w}"] = st

    for key, st in out.items():
        t, b, d = st["turns"], st["blocks"], st["days"] or 1
        print(f"\n===== {key}  {st['window']}  天數={st['days']}")
        print(f"使用者回合={t}  被擋={b}  每天={b/d:.1f}  每回合={b/max(t,1):.2f}  被擋回合={st['blocked_turns']}({st['blocked_turns']/max(t,1):.0%})")
        print(f"連擋分布={dict(sorted(st['chain'].items()))}  同閘≥2回合={st['same_gate_2plus']}")
        print("閘（第一個標籤）:", dict(st["gate"].most_common()))
        print("閘出現的回合數:", dict(st["gate_turns"].most_common()))
        rit = sum(v for k, v in st["gate"].items() if k in RITUAL)
        print(f"收尾儀式(Harvest/ScanReport/AtomAudit)={rit} ({rit/max(b,1):.0%})")
        print("VerifyScope 分項(擋下則數):", dict(st["vs_block"]), " 項目數:", dict(st["vs_item"]), " 所在閘:", dict(st["vs_first_tag"]))
        rr = st["vs_block"]["改完要重跑"]
        print(f"改完要重跑 每天={rr/d:.1f} 每回合={rr/max(t,1):.3f}")
        print(f"閱讀路徑附={st['rp_attached']} 逾時={st['rp_timeout']} 手動跑={st['manual_rp']}")
        for x in st["rp_followups"]:
            print("   RP例:", x)
        print(f"verify_scope 宣告={st['vs_decl']}（帶depends的宣告={st['vs_decl_dep']}） 項目={st['vs_items']} 帶depends={st['vs_items_dep']}")
        hrs = st["active_sec"] / 3600
        print(f"活躍時數={hrs:.1f}h  每活躍小時被擋={b/max(hrs,0.01):.1f}  session回合={dict(st['sessions'])}")
        print(f"擋下後續跑總時間={st['cont_sec']['_all']/60:.0f}分")
        for g, s in st["cont_sec"].most_common():
            if g == "_all":
                continue
            n = st["gate"][g]
            print(f"   {g}: 擋{n} 續跑{s/60:.0f}分 後跑測試{st['rerun_after'][g]} 後改程式/文件{st['edit_after'][g]}")
        print("   續跑最長10例(分,閘,session,時間,動作數,pytest次數):", sorted(st["cont_list"], reverse=True)[:10])
        pt = Counter()
        for m, g, *_rest, n_py in st["cont_list"]:
            pt[g] += n_py
        print("   擋下後 pytest/run_verify 次數（每閘）:", dict(pt.most_common()))
        print("   ✗ 規則（擋下則數）:", dict(st["rules"].most_common(15)))
        print("擋下後動作（每閘）：")
        for g, c in sorted(st["after"].items(), key=lambda kv: -kv[1]["_n"]):
            n = c.pop("_n")
            print(f"   {g} n={n}: " + ", ".join(f"{k}={v}" for k, v in c.most_common()))
            c["_n"] = n
    if "--json" in sys.argv:
        with open(sys.argv[sys.argv.index("--json") + 1], "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1, default=lambda o: dict(o) if isinstance(o, Counter) else str(o))
    print("\nSTOP_MEASURE DONE files=%d" % len(files))


if __name__ == "__main__":
    main()

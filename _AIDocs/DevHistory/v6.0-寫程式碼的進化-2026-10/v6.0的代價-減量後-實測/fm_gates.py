"""fm_gates.py — 每道閘擋幾次：讀連鎖斷路器的帳（Logs/chain-<session>.jsonl）＋受測 transcript，逐道閘數三欄、抽核兩邊對不對得上。

做什麼
  1. 回合＝transcript 裡使用者送出的一則新話（Stop 擋訊息 isMeta、工具結果、背景通知都不算新回合）；帳的每筆照時間歸到回合。
  2. 三欄（門檻只看③）：
     ① 檢查執行：資料根 guard-hook_timing.jsonl 每個（事件, 分段）跑了幾次（hook 跑過那道判斷；分段名對閘名是近似，另表列）。
     ② 條件命中但只記錄或只提示：帳上 record_only=true 的閘筆數＋transcript 裡 hook 附加提示（hook_additional_context）帶這道閘標記的次數。
     ③ 實際擋下或記一筆欠帳：帳上 type=gate、record_only=false 的筆數（raw）；其中「觸發」＝這回合這道閘第一次，
        或跟這道閘上一次之間 AI 有動作（帳上 type=action）——同一批平行呼叫、原樣重試、只改寫回覆的再擋不算觸發（照計數口徑）。
  3. 同一回合同一道閘觸發 >1 → 列出每次的擋訊息原文（帳上 what 是截短的，原文從 transcript 對 tool_use_id／時間取）與前後各一個工具呼叫。
  4. 抽核：transcript 的工具前擋（tool_result 以「PreToolUse:… hook error」開頭）與收尾擋（hook_blocking_error, Stop）逐道閘數，
     跟帳上同 hook 的筆數比；斷路器自己的停手擋與經過表（ChainBreaker）不算閘觸發，另列。
怎麼跑
  python -X utf8 fm_gates.py --run <results 底下那跑的資料夾> [--seg-re "B-\\d"] [--chain-dir <帳所在資料夾>] [--md <輸出 md>] [--json <輸出 json>]
  帳預設找 <run>/_fm/root-Logs/chain-*.jsonl；transcript 找 <run>/<段>/transcript/*.jsonl；計時帳找 <run>/<段>/logs/_this_session/guard-hook_timing.jsonl。
尾行 FM_GATES DONE run=<名> gates=<有③的閘數> max_per_turn=<觸發數最大值> over1=<觸發 >1 的（回合,閘）數> alarms=<警報數> mismatch=<抽核對不上的閘數>
"""
import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

KIT = Path("C:/Users/holylight/.claude/workflow/inbox/wave2-kit")
TAG_RE = re.compile(r"\[(?:Guardian:)?([A-Za-z][\w\-]*)\]")
DENY_RE = re.compile(r"^PreToolUse:(\w+) hook error:\s*")
STOP_LINE_RE = re.compile(r"^\s*✗ \(([^)]+)\) ([^：:]+)[：:]", re.M)
LOCAL_TZ = datetime.now().astimezone().tzinfo


def ts_of(s):
    dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    return dt.timestamp()


def text_of(content):
    if isinstance(content, str):
        return content
    out = []
    for b in content or []:
        if isinstance(b, dict):
            if b.get("type") == "text":
                out.append(b.get("text") or "")
            elif b.get("type") == "tool_result":
                c = b.get("content")
                out.append(c if isinstance(c, str) else text_of(c))
    return "\n".join(out)


def first_tag(text, hook="PreToolUse"):
    """擋訊息第一個標記＝閘名（同 wg_chain.gate_name）；沒標記時斷路器記成呼叫端預設名（PreToolUse／Stop），
    這裡再用第一行「✗ (字母) 規則名」分開，免得不同的無標記閘被算成同一道。"""
    m = TAG_RE.search(text or "")
    if m:
        return m.group(1)
    r = STOP_LINE_RE.search(text or "")
    return f"{hook}〔{r.group(1)}〕" if r else hook


def gate_key(r):
    g = str(r.get("gate") or "")
    if g in ("PreToolUse", "Stop", "SubagentStop"):
        return first_tag(r.get("what") or "", g)
    return g


def load_jsonl(p):
    rows = []
    for line in Path(p).read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def read_transcript(paths):
    """回 (使用者回合起點 [(ts, 前 60 字)], 工具呼叫 [(ts, id, name, input 摘要)], 工具前擋 {tool_use_id: (ts, 原文)},
    收尾擋 [(ts, 原文)], 附加提示標記 Counter, hook 被砍次數)。"""
    turns, calls, denies, stops, hints, cancelled, tid2msg = [], [], {}, [], Counter(), 0, {}
    for p in paths:
        for r in load_jsonl(p):
            at = ts_of(r["timestamp"]) if r.get("timestamp") else None
            msg = r.get("message") or {}
            content = msg.get("content")
            if r.get("type") == "user" and not r.get("isMeta"):
                if isinstance(content, str) or (isinstance(content, list) and not any(
                        isinstance(b, dict) and b.get("type") == "tool_result" for b in content)):
                    t = text_of(content).strip()
                    notif = (r.get("origin") or {}).get("kind") == "task-notification" or t.startswith("<task-notification>")
                    if t and not notif and at:
                        turns.append((at, t[:60]))
            if r.get("type") == "assistant" and isinstance(content, list):
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "tool_use":
                        tid2msg[b.get("id")] = msg.get("id")
                        calls.append((at, b.get("id"), b.get("name"), json.dumps(b.get("input") or {}, ensure_ascii=False)[:160]))
            if r.get("type") == "user" and isinstance(content, list):
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        body = b.get("content")
                        body = body if isinstance(body, str) else text_of(body)
                        m = DENY_RE.match(body or "")
                        if m:
                            denies[b.get("tool_use_id")] = (at, body[m.end():].strip())
            a = (r.get("attachment") or {}) if r.get("type") == "attachment" else {}
            if a.get("type") == "hook_blocking_error" and a.get("hookEvent") in ("Stop", "SubagentStop"):
                stops.append((at, (a.get("blockingError") or {}).get("blockingError", "")))
            if a.get("type") == "hook_additional_context":
                for x in a.get("content") or []:
                    if isinstance(x, str):
                        for t in set(TAG_RE.findall(x)):
                            hints[t] += 1
            if a.get("type") == "hook_cancelled":
                cancelled += 1
    turns.sort()
    calls.sort(key=lambda c: c[0] or 0)
    stops.sort(key=lambda s: s[0] or 0)
    return turns, calls, denies, stops, hints, cancelled, tid2msg


def turn_no(turns, ts):
    n = 0
    for i, (t0, _) in enumerate(turns):
        if ts >= t0 - 1:
            n = i + 1
    return n


def around(calls, ts, tool_use_id=None):
    """前一個與後一個工具呼叫（被擋的那個本身另列）。"""
    idx = next((i for i, c in enumerate(calls) if tool_use_id and c[1] == tool_use_id), None)
    if idx is None:
        before = [c for c in calls if c[0] is not None and c[0] <= ts]
        after = [c for c in calls if c[0] is not None and c[0] > ts]
        return (before[-1] if before else None), None, (after[0] if after else None)
    return (calls[idx - 1] if idx > 0 else None), calls[idx], (calls[idx + 1] if idx + 1 < len(calls) else None)


def fmt_call(c):
    return f"{c[2]} `{c[3][:120]}`" if c else "（無）"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--seg-re", default=r"[A-Z]-\d")
    ap.add_argument("--chain-dir")
    ap.add_argument("--md")
    ap.add_argument("--json")
    a = ap.parse_args()
    run = KIT / "results" / a.run if not Path(a.run).is_absolute() else Path(a.run)
    segs = sorted(p for p in run.iterdir() if p.is_dir() and re.fullmatch(a.seg_re, p.name))
    chain_dir = Path(a.chain_dir) if a.chain_dir else run / "_fm" / "root-Logs"
    ledgers = sorted(chain_dir.glob("chain-*.jsonl"))
    out = {"run": run.name, "segments": {}, "ledgers": [p.name for p in ledgers]}
    md = [f"# 每道閘擋幾次：{run.name}", ""]
    totals = {"gates": set(), "max": 0, "over1": 0, "alarms": 0, "mismatch": 0}
    for seg in segs:
        txs = sorted((seg / "transcript").glob("*.jsonl"))
        sid = txs[0].stem if txs else ""
        led = chain_dir / f"chain-{sid}.jsonl"
        rows = load_jsonl(led) if led.is_file() else []
        turns, calls, denies, stops, hints, cancelled, tid2msg = read_transcript(txs)
        gates = [r for r in rows if r.get("type") == "gate"]
        by_tg = defaultdict(list)
        for i, r in enumerate(rows):
            r["_turn"] = turn_no(turns, r["ts"])
            r["_g"] = gate_key(r) if r.get("type") == "gate" else ""
            # 讓警報響的那一筆帳上記 record_only=true，但那個工具呼叫／那次收尾其實被中止通知擋下了：算③
            nxt = rows[i + 1] if i + 1 < len(rows) else {}
            r["_alarm_hit"] = r.get("type") == "gate" and nxt.get("type") == "alarm" and nxt.get("turn") == r.get("turn")
            r["_live"] = r.get("type") == "gate" and (not r.get("record_only") or r["_alarm_hit"])
        last_gate_seq = {}
        for r in sorted(rows, key=lambda x: (x["ts"], x.get("seq", 0))):
            if r.get("type") != "gate":
                continue
            by_tg[(r["_turn"], r["_g"])].append(r)
        col3_raw, col3_trig, col2, maxper, batch_false = Counter(), Counter(), Counter(), Counter(), Counter()
        detail = []
        for (tn, g), rs in sorted(by_tg.items()):
            live = [r for r in rs if r["_live"]]
            col2[g] += len(rs) - len(live)
            col3_raw[g] += len(live)
            trig, prev, batch_only = [], None, 0
            for r in live:
                between = [x for x in rows if x.get("type") == "action" and prev is not None
                           and prev["ts"] <= x["ts"] <= r["ts"] and x["_turn"] == tn]
                pm = tid2msg.get(prev.get("event")) if prev is not None else None
                # 同一則回覆（同一批平行工具）裡的動作不是看了擋訊息才做的：AI 還沒看到前一次擋，不算「動作讓閘再擋」
                acted = [x for x in between if pm is None or tid2msg.get(x.get("event")) != pm]
                if prev is None or acted:
                    trig.append(r)
                elif between:
                    batch_only += 1
                prev = r
            batch_false[g] += batch_only
            col3_trig[g] += len(trig)
            maxper[g] = max(maxper[g], len(trig))
            if len(trig) > 1:
                totals["over1"] += 1
                items = []
                for r in trig:
                    tid = r.get("event") if str(r.get("event", "")).startswith("toolu_") else None
                    if tid and tid in denies:
                        raw = denies[tid][1]
                    else:
                        near = [s for s in stops if s[0] and abs(s[0] - r["ts"]) < 30]
                        raw = near[0][1] if near else r.get("what", "")
                    b, me, af = around(calls, r["ts"], tid)
                    items.append({"seq": r.get("seq"), "at": r.get("at"), "hook": r.get("hook"), "depth": r.get("depth"),
                                  "same": r.get("same"), "link": r.get("link"), "raw": raw, "before": fmt_call(b),
                                  "blocked": fmt_call(me), "after": fmt_call(af)})
                detail.append({"turn": tn, "gate": g, "triggers": items})
        alarms = [r for r in rows if r.get("type") == "alarm"]
        totals["alarms"] += len(alarms)
        tx_pre = Counter(first_tag(t) for _, t in denies.values())
        tx_stop = Counter(first_tag(t, "Stop") for _, t in stops)
        led_pre = Counter(r["_g"] for r in gates if r.get("hook") == "PreToolUse" and r["_live"])
        led_stop = Counter(r["_g"] for r in gates if r.get("hook") in ("Stop", "SubagentStop") and r["_live"])
        # 讓警報響的那一次：工具被斷路器的中止通知擋下（transcript 標記是 ChainBreaker）、收尾被經過表擋下；抽核時歸回 ChainBreaker
        for r in gates:
            if r.get("_alarm_hit"):
                (led_pre if r.get("hook") == "PreToolUse" else led_stop)[r["_g"]] -= 1
        mism = {}
        for g in set(tx_pre) | set(led_pre):
            if g != "ChainBreaker" and tx_pre[g] != led_pre[g]:
                mism[f"PreToolUse:{g}"] = {"transcript": tx_pre[g], "ledger": led_pre[g]}
        for g in set(tx_stop) | set(led_stop):
            if g != "ChainBreaker" and tx_stop[g] != led_stop[g]:
                mism[f"Stop:{g}"] = {"transcript": tx_stop[g], "ledger": led_stop[g]}
        totals["mismatch"] += len(mism)
        timing = Counter()
        tp = seg / "logs" / "_this_session" / "guard-hook_timing.jsonl"
        if tp.is_file():
            for r in load_jsonl(tp):
                if r.get("kind") == "run":
                    for name, _ms in r.get("segments") or []:
                        timing[f"{r.get('event')}:{name}"] += 1
        stop_lines = Counter(f"({m.group(1)}) {m.group(2).strip()}" for _, t in stops for m in STOP_LINE_RE.finditer(t))
        for g in col3_raw:
            totals["gates"].add(g)
        totals["max"] = max([totals["max"], *maxper.values()])
        segd = {"session": sid, "ledger": led.name if led.is_file() else None, "user_turns": len(turns),
                "col1_timing_runs": dict(timing), "col2_record_only": dict(col2), "col2_hints": dict(hints),
                "col3_raw": dict(col3_raw), "col3_triggers": dict(col3_trig), "batch_only_regates": dict(batch_false), "max_triggers_per_turn": dict(maxper),
                "over1": detail, "alarms": alarms, "actions": sum(1 for r in rows if r.get("type") == "action"),
                "tx_pretool_denies": dict(tx_pre), "tx_stop_blocks": dict(tx_stop), "tx_stop_lines": dict(stop_lines),
                "ledger_pretool": dict(led_pre), "ledger_stop": dict(led_stop), "mismatch": mism, "hook_cancelled": cancelled,
                "notices": [r for r in rows if r.get("type") in ("notice", "shown", "halted", "answer", "reset", "restore")]}
        out["segments"][seg.name] = segd
        md += [f"## {seg.name}（session `{sid[:8]}`，使用者回合 {len(turns)}，帳 {len(rows)} 筆{'' if led.is_file() else '：帳不在'}）", "",
               "| 閘 | ①檢查執行（近似，見計時表） | ②只記錄＋只提示 | ③擋下或記欠（筆數） | ③觸發（有動作間隔） | 同一回合最多觸發 |",
               "|---|---|---|---|---|---|"]
        for g in sorted(set(col3_raw) | set(col2) | {t for t in hints if t in col3_raw}):
            mark = " **⚠ >1**" if maxper[g] > 1 else ""
            md.append(f"| {g} | — | {col2[g]}＋{hints.get(g, 0)} | {col3_raw[g]} | {col3_trig[g]} | {maxper[g]}{mark} |")
        md += ["", f"- 同批平行呼叫裡「中間有動作」的再擋（斷路器會算成同閘第 2 次，本表不算觸發）：{json.dumps(dict(batch_false), ensure_ascii=False)}",
               f"- 斷路器警報 {len(alarms)} 次" + (
            "：" + "；".join(f"回合 {r['_turn']} 深度 {r.get('depth')} 命中 {r.get('hits')}" for r in alarms) if alarms else ""),
               f"- AI 動作筆數 {segd['actions']}；hook 被砍 {cancelled} 次",
               f"- 抽核（transcript 對帳上，同 hook）：{'全對上' if not mism else json.dumps(mism, ensure_ascii=False)}",
               f"- 只提示的標記（transcript 附加提示）：{json.dumps(dict(hints.most_common()), ensure_ascii=False)}", ""]
        for d in detail:
            md += [f"### 回合 {d['turn']}・{d['gate']} 觸發 {len(d['triggers'])} 次", ""]
            for it in d["triggers"]:
                md += [f"- 步序 {it['seq']}（{it['at']}，{it['hook']}，depth={it['depth']} same={it['same']} link={it['link']}）",
                       f"  - 前一個工具呼叫：{it['before']}", f"  - 被擋的呼叫：{it['blocked']}", f"  - 後一個工具呼叫：{it['after']}",
                       "  - 擋訊息原文：", "", "```", it["raw"][:3000], "```", ""]
        md += ["<details><summary>① 計時帳：每個（事件:分段）跑幾次</summary>", "",
               *[f"- {k} ×{v}" for k, v in sorted(timing.items())], "", "</details>", ""]
    if a.md:
        Path(a.md).write_text("\n".join(md) + "\n", encoding="utf-8")
    if a.json:
        Path(a.json).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"FM_GATES DONE run={run.name} gates={len(totals['gates'])} max_per_turn={totals['max']} over1={totals['over1']} "
          f"alarms={totals['alarms']} mismatch={totals['mismatch']}")


if __name__ == "__main__":
    main()

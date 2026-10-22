"""b6_measure.py — 量 v6.0 hook 與注入的代價：題 B′「hook 全關」對「現況」各兩跑，從 wave2-kit 收好的材料算數字。

做什麼
  1. 每回合（一次 claude -p）：牆鐘秒數（_meta 起訖）、輸入／輸出 token（回合 JSON 的 usage，是單次呼叫的量；
     輸入＝input＋cache_creation＋cache_read，即模型實際讀過的 token，不受快取冷熱影響）、num_turns、被擋次數。
     modelUsage／total_cost_usd 是整個 session 的累計，只拿來核對加總。
  2. hook 耗時：資料根留帳 logs/_this_session/guard-hook_timing.jsonl（kind=run，workflow-guardian.py 一支的逐事件逐分段 ms）
     ＋ transcript 的 stop_hook_summary（Stop 時其他 hook：codex_companion、lang_guard）與 hook_success 的 durationMs（其他事件的
     非 guardian hook，只有留了附件的才算得到）。同一事件幾支 hook 並行跑，逐支加總會大於實際多等的時間；實際多等以牆鐘差為準。
  3. 注入量：transcript 裡 hook 送進對話的文字（hook_additional_context、hook_blocking_error、PreToolUse 擋訊息），依行首標籤切塊、
     歸到項目；token 用 live 的 wg_core._estimate_tokens 估（系統自己的口徑，中文約 1.5 token／字）——推論級。
  4. 項目表：每個項目＝計時分段＋注入標籤，對到 G 目標（ITEMS）；沒歸到的分段與標籤列在 unmapped，不吞。
  5. guard-entry 切入點帳：各 E 代號問幾次、送幾張卡、幾次截斷。
  6. AI 為系統多做的事：transcript 裡 mcp__workflow-guardian__* 工具呼叫次數，和含這些呼叫的回覆輸出 token（推論級，整則歸給它）。

怎麼跑
  python -X utf8 b6_measure.py --runs off:2026-10-22-B6off-1,on:2026-10-22-B6on-1,off:2026-10-22-B6off-2,on:2026-10-22-B6on-2 \\
      [--kit C:/Users/holylight/.claude/workflow/inbox/wave2-kit] [--live C:/Users/holylight/.claude] [--out <json>]
  stdout 印 Markdown 表（每回合、整題、項目、逐跑原始數字）；尾行 B6_MEASURE DONE runs=… off_in=… on_in=… off_wall_s=… on_wall_s=…
"""
import argparse
import json
import re
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_KIT = "C:/Users/holylight/.claude/workflow/inbox/wave2-kit"
DEFAULT_LIVE = "C:/Users/holylight/.claude"
GUARDIAN = "workflow-guardian"

# 項目：名稱、對照的 G 目標、計時分段（事件, 分段；事件 * ＝任何事件、分段 * ＝該事件其餘分段）、注入標籤、其他 hook（腳本名, 事件）
ITEMS = [
    ("每次 hook 起動與載入", "不對應 G（基礎開銷）", [("*", "啟動"), ("*", "載入 handler")], [], []),
    ("各 hook 未細分的其餘時間", "不對應 G（帳上沒再拆）", [("*", "其餘")], [], []),
    ("開場：未結追蹤項提示", "G13", [("SessionStart", "追蹤提示")], ["Guardian:Tracking"], []),
    ("開場：索引、健檢、公司層、git 快照", "不對應 G（記憶系統本業）",
     [("SessionStart", "*")], ["Workflow Guardian", "Role", "Org", "Guardian:HealthCheck", "Guardian:Resume", "AIDocs", "Realm"],
     [("run-bash-hidden", "SessionStart"), ("ensure-mcp", "SessionStart")]),
    ("使用者訊息時注入記憶卡與相關文件", "不對應 G（記憶系統本業）",
     [("UserPromptSubmit", "脈絡"), ("UserPromptSubmit", "檢索"), ("UserPromptSubmit", "注入組裝"),
      ("UserPromptSubmit", "前置閘"), ("UserPromptSubmit", "收尾提示")],
     ["Atom", "Atom Recovery", "Session", "Context budget", "Parallel", "Proactive", "Guardian:AIDocs"], []),
    ("需求目標樹與目標視角重看", "G1（目標視角）", [("UserPromptSubmit", "目標樹"), ("PostToolUse", "目標樹")], ["NeedGoal"], []),
    ("動手前定位三行與導讀卡", "G0／G1", [("PreToolUse", "寫入閘"), ("PostToolUse", "導讀卡"), ("PostToolUse", "綜觀與召回"),
                                    ("UserPromptSubmit", "導讀卡")], ["Guardian:OverviewHub"], []),
    ("改資料檔／改舊測試先宣告", "根治 T2.16／T2.17", [("PreToolUse", "舊測試閘")],
     ["Guardian:DataFileAsk", "Guardian:OldTest", "Guardian:OldTestAsk"], []),
    ("交付時點出最該修", "G4／G5", [("Stop", "點出最該修"), ("Stop", "最該修記帳")], ["Guardian:PickOne"], []),
    ("收尾寫碼查核（驗證範圍、收據、對照）", "G3／G10",
     [("Stop", "寫碼查核"), ("Stop", "紅測閘"), ("Stop", "閉環歸因")],
     ["Guardian:VerifyScope", "Guardian:AEC-Evidence", "Guardian:ReconcileGate", "Guardian:AlsoOwed", "Guardian:AcceptanceSpec",
      "Guardian:CodingAudit", "Guardian:TestFailGate"], []),
    ("收尾檢核與退避偵測", "G6", [("Stop", "收尾檢核"), ("Stop", "殘檔帳本"), ("Stop", "退縮歸屬"), ("Stop", "報告待寫"),
                             ("Stop", "報告視窗"), ("Stop", "深度檢討")],
     ["Guardian:AEC", "Guardian:Evasion", "Guardian:DeferralGate", "Guardian:ClaimGate", "Guardian:Retreat"], []),
    ("拐彎判斷與閱讀路徑", "G11", [("Stop", "拐彎判斷"), ("Stop", "token 預警與閱讀路徑")], ["Guardian:ReadingPath", "Guardian:TurnJudge"], []),
    ("等值證法與熱路徑", "G7", [("Stop", "等值證法")], ["Guardian:Preserve", "Guardian:Equivalence"], []),
    ("第二意見", "G9", [("Stop", "第二意見")], ["Guardian:SecondOpinion", "Codex Companion"], [("codex_companion", "*")]),
    ("文字評分", "G15", [("Stop", "文字評分")], ["Guardian:TextScore"], []),
    ("病形閘（新碼不抄舊病）", "G2", [], ["Guardian:SmellGate"], []),
    ("知識收割與同步提醒", "不對應 G（記憶系統本業）",
     [("Stop", "知識收割"), ("Stop", "收割對帳"), ("Stop", "取用稽核"), ("Stop", "同步提醒")],
     ["Guardian:KnowledgeHarvest", "Guardian:SyncReminder", "Guardian:AtomAudit", "Guardian", "Guardian:Sync"], []),
    ("語言守門", "不對應 G", [], [], [("lang_guard", "*")]),
    ("工具記帳、狀態讀寫、跨 session 協調", "不對應 G（基礎開銷）",
     [("PostToolUse", "工具記帳"), ("PostToolUse", "寫 state"), ("PostToolUse", "讀 state"), ("PostToolUse", "同伴檢查"),
      ("PostToolUse", "跨 session 碰撞"), ("PreToolUse", "前置提示"), ("PreToolUse", "跨 session 衝突"),
      ("Stop", "讀 transcript"), ("Stop", "Reload 建議"), ("Stop", "收尾自清")],
     ["Guardian:CoordWarn"], [("plan_bash_guard", "*")]),
]
OTHER = "其他（未歸類）"
# AI 呼叫的系統工具歸哪個項目（這次呼叫模型是為了填它）
SYS_TOOL_ITEM = {
    "need_goal": "需求目標樹與目標視角重看",
    "anti_evasion_report": "收尾檢核與退避偵測",
    "knowledge_harvest_report": "知識收割與同步提醒", "atom_write": "知識收割與同步提醒", "atom_retire": "知識收割與同步提醒",
    "second_opinion_start": "第二意見", "second_opinion_result": "第二意見",
    "memory_search": "使用者訊息時注入記憶卡與相關文件",
}
# 消耗來源（④）：hook 從哪條路把東西送進對話、或讓 AI 多跑了哪些回合
SRC_OPEN, SRC_UPS, SRC_TOOL = "開場注入", "每回合使用者訊息注入", "工具前後的提示"
SRC_DENY, SRC_STOP, SRC_SO, SRC_TS = "擋訊息與被擋重做", "收尾擋下與多跑的回合", "第二意見", "文字評分"
SRC_SYS, SRC_REST = "AI 照規則呼叫系統工具", "其他（任務走法不同、對話變長）"
SOURCES = [SRC_OPEN, SRC_UPS, SRC_TOOL, SRC_DENY, SRC_STOP, SRC_SO, SRC_TS, SRC_SYS]
EVENT_SOURCE = {"SessionStart": SRC_OPEN, "UserPromptSubmit": SRC_UPS, "Stop": SRC_STOP, "SubagentStop": SRC_STOP,
                "SessionEnd": SRC_STOP}
TAG_RE = re.compile(r"\[(Atom|Guardian:[\w\-]+|[A-Za-z][\w ]*?)[\]:]")
BLOCK_SPLIT = re.compile(r"\n(?=\S{0,4}\[[A-Za-z])")
LOCAL_TZ = datetime.now().astimezone().tzinfo


def load_estimator(live):
    sys.path.insert(0, str(Path(live) / "hooks"))
    from wg_core import _estimate_tokens   # 系統自己的估算口徑；import 不到就讓它丟例外，不退回別的算法
    return _estimate_tokens


def item_for_seg(event, seg):
    for name, _g, segs, _tags, _ext in ITEMS:
        if (event, seg) in segs or ("*", seg) in segs:
            return name
    for name, _g, segs, _tags, _ext in ITEMS:
        if (event, "*") in segs:
            return name
    return None


def item_for_tag(tag):
    for name, _g, _segs, tags, _ext in ITEMS:
        if tag in tags:
            return name
    return None


def item_for_ext(script, event):
    for name, _g, _segs, _tags, ext in ITEMS:
        if (script, event) in ext or (script, "*") in ext:
            return name
    return None


def source_of(src, event, item):
    """注入或擋訊息屬哪個消耗來源：src＝ctx（additionalContext）／deny（PreToolUse 擋）／block:<事件>（擋收尾）。"""
    if item in (SRC_TS, SRC_SO):
        return item
    if src == "deny":
        return SRC_DENY
    if src.startswith("block:"):
        return SRC_STOP
    return EVENT_SOURCE.get(event, SRC_TOOL)


def timing_source(event, seg):
    if seg in (SRC_TS, SRC_SO):
        return seg
    return EVENT_SOURCE.get(event, SRC_TOOL)


def script_of(command):
    m = re.search(r"hooks/([\w\-]+)\.py", command or "")
    return m.group(1) if m else (command or "?")[:30]


def local_naive(ts):
    """ISO 時間 → 本地無時區（回合起訖本來就是本地無時區；留帳帶 +08:00；transcript 是 UTC 的 Z）。"""
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return dt.astimezone(LOCAL_TZ).replace(tzinfo=None) if dt.tzinfo else dt


def turn_index(turns, at):
    for i, t in enumerate(turns):
        if t["_start"] <= at <= t["_end"]:
            return i
    return None


def hook_texts(row):
    """這一列 transcript 裡 hook 送進對話的文字：[(來源, 文字)]。"""
    out = []
    if row.get("type") == "attachment":
        a = row.get("attachment") or {}
        if a.get("type") == "hook_additional_context":
            out += [("ctx", x) for x in a.get("content") or [] if isinstance(x, str)]
        elif a.get("type") == "hook_blocking_error":
            out.append((f"block:{a.get('hookEvent')}", (a.get("blockingError") or {}).get("blockingError", "")))
    content = (row.get("message") or {}).get("content")
    if isinstance(content, list):
        for b in content:
            if isinstance(b, dict) and b.get("type") == "tool_result":
                c = b.get("content")
                text = c if isinstance(c, str) else "\n".join(x.get("text", "") for x in c or [] if isinstance(x, dict))
                if "hook error" in text:
                    out.append(("deny", text))
    return out


def measure_segment(seg_dir, est):
    """一段（B-1／B-2）：回合、hook 耗時、注入、切入點帳、系統工具呼叫。"""
    turns = []
    for p in sorted((seg_dir / "turns").glob("*.json"), key=lambda p: int(re.search(r"-t(\d+)", p.stem).group(1))):
        d = json.loads(p.read_text(encoding="utf-8"))
        m, u = d["_meta"], d.get("usage") or {}
        turns.append({
            "file": p.name, "id": m.get("id"), "hooks": m.get("hooks", "on"),
            "_start": local_naive(m["started"]), "_end": local_naive(m["ended"]),
            "wall_s": (local_naive(m["ended"]) - local_naive(m["started"])).total_seconds(),
            "in": (u.get("input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0),
            "out": u.get("output_tokens") or 0,
            "cache_read": u.get("cache_read_input_tokens") or 0,
            "num_turns": d.get("num_turns") or 0, "denials": len(d.get("permission_denials") or []),
            "duration_ms": d.get("duration_ms") or 0, "duration_api_ms": d.get("duration_api_ms") or 0,
            "cost_cum": float(d.get("total_cost_usd") or 0), "rc": m.get("rc"),
            "hook_ms": 0, "inject_tok": 0, "load": m.get("load"),
        })
    cum_mu = {}
    if turns:
        last = json.loads((seg_dir / "turns" / turns[-1]["file"]).read_text(encoding="utf-8"))
        cum_mu = last.get("modelUsage") or {}
    item_ms, item_tok, item_inject_n = Counter(), Counter(), Counter()
    unmapped_seg, unmapped_tag = Counter(), Counter()
    event_ms, src_ms = Counter(), Counter()
    timing = seg_dir / "logs" / "_this_session" / "guard-hook_timing.jsonl"
    if timing.is_file():
        for line in timing.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r.get("kind") != "run":
                continue
            event_ms[r["event"]] += r.get("total_ms") or 0
            i = turn_index(turns, local_naive(r["at"]))
            if i is not None:
                turns[i]["hook_ms"] += r.get("total_ms") or 0
            for name, ms in r.get("segments") or []:
                it = item_for_seg(r["event"], name)
                if it is None:
                    unmapped_seg[f"{r['event']}:{name}"] += ms
                    it = OTHER
                item_ms[it] += ms
                src_ms[timing_source(r["event"], name)] += ms
    ext_ms = Counter()
    cancelled = 0
    tool_calls, tool_out = Counter(), Counter()
    seen_msg = set()
    # 逐次模型呼叫（message id 去重）：觸發它的 hook（前一個擋訊息／Stop 擋）或它呼叫的系統工具 → 歸項目
    calls = {}           # id → {"cause": (來源, 項目) 或 None, "sys": [工具], "in": 輸入, "out": 輸出, "t0"／"t1": 送出與寫完的時間}
    cause = None
    injections = []      # (注入當下已有幾次呼叫, token, 項目, (來源, 項目))：之後每次呼叫都會再讀一遍
    prev_at = None       # 上一筆不是 assistant 的列的時間：assistant 第一列減它＝這次呼叫等了幾秒
    tx_files = sorted((seg_dir / "transcript").glob("*.jsonl"))
    for tx in tx_files:
        for line in tx.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("type") == "user" and isinstance((r.get("message") or {}).get("content"), str) and not r.get("isMeta"):
                cause = None   # 使用者說話：之後的呼叫是回應使用者。一般工具結果不清——同一批平行工具裡有一個被擋，下一次呼叫就是在回應它
            at = local_naive(r["timestamp"]) if r.get("timestamp") else None
            a = (r.get("attachment") or {}) if r.get("type") == "attachment" else {}
            if a.get("type") == "hook_cancelled":
                cancelled += 1
            if a.get("type") == "hook_success" and GUARDIAN not in (a.get("command") or ""):
                script = script_of(a.get("command"))
                ext_ms[item_for_ext(script, a.get("hookEvent")) or OTHER] += a.get("durationMs") or 0
                src_ms[SRC_SO if script == "codex_companion" else EVENT_SOURCE.get(a.get("hookEvent"), SRC_TOOL)] += a.get("durationMs") or 0
            if r.get("type") == "system" and r.get("subtype") == "stop_hook_summary":
                for h in r.get("hookInfos") or []:
                    if GUARDIAN not in (h.get("command") or ""):
                        script = script_of(h.get("command"))
                        ext_ms[item_for_ext(script, "Stop") or OTHER] += h.get("durationMs") or 0
                        src_ms[SRC_SO if script == "codex_companion" else SRC_STOP] += h.get("durationMs") or 0
            event = a.get("hookEvent") or "PreToolUse"   # 擋訊息在 tool_result 裡，沒有附件欄，一律是 PreToolUse
            for src, text in hook_texts(r):
                first = None
                for block in BLOCK_SPLIT.split(text):
                    m = TAG_RE.search(block[:200])
                    tag = m.group(1).strip() if m else "(無標籤)"
                    tok = est(block)
                    # 開場與 Stop 同用 [Workflow Guardian]：Stop 擋訊息裡的是「N 個檔改過」同步提醒
                    it = "知識收割與同步提醒" if (tag, src) == ("Workflow Guardian", "block:Stop") else item_for_tag(tag)
                    if it is None:
                        unmapped_tag[tag] += tok
                        it = OTHER
                    key = (source_of(src, event, it), it)
                    first = first or key
                    item_tok[it] += tok
                    item_inject_n[it] += 1
                    injections.append((len(calls), tok, it, key))
                    i = turn_index(turns, at) if at else None
                    if i is not None:
                        turns[i]["inject_tok"] += tok
                if src != "ctx":
                    cause = first   # 被擋（PreToolUse 擋、Stop 擋）之後那次呼叫是在回應這個 hook
            msg = r.get("message") or {}
            if r.get("type") != "assistant" and at:
                prev_at = at
            if r.get("type") == "assistant" and isinstance(msg.get("content"), list):
                names = [b.get("name") for b in msg["content"] if isinstance(b, dict) and b.get("type") == "tool_use"]
                sys_names = [n.replace("mcp__workflow-guardian__", "") for n in names if n and n.startswith("mcp__workflow-guardian__")]
                tool_calls.update(sys_names)
                if sys_names and msg.get("id") not in seen_msg:
                    seen_msg.add(msg.get("id"))
                    tool_out[sys_names[0]] += (msg.get("usage") or {}).get("output_tokens") or 0
                u = msg.get("usage") or {}
                if msg.get("id") not in calls:
                    calls[msg.get("id")] = {"cause": cause, "sys": [], "out": u.get("output_tokens") or 0,
                                            "in": (u.get("input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0)
                                            + (u.get("cache_creation_input_tokens") or 0),
                                            "t0": prev_at or at, "t1": at}
                    cause = None   # 這次呼叫已經回應了那個 hook，之後的呼叫另算
                c = calls[msg.get("id")]
                c["sys"] += sys_names
                c["t1"] = at or c["t1"]   # 這次呼叫從送出（前一筆非 assistant 列）到最後一列寫完；同批平行工具的執行時間也算在內
    react_n, react_in, react_out, reread = Counter(), Counter(), Counter(), Counter()
    src_tok, src_lat = Counter(), Counter()   # 鍵「來源｜項目」：多耗 token（被叫去多跑的呼叫整筆＋注入在其他呼叫被重讀）、多跑呼叫等的秒數
    call_list = list(calls.values())
    for c in call_list:
        c["lat"] = (c["t1"] - c["t0"]).total_seconds() if c["t0"] and c["t1"] else 0
        sys_item = next((SYS_TOOL_ITEM.get(s, OTHER) for s in c["sys"]), None)
        c["key"] = c["cause"] or ((SRC_SYS, sys_item) if sys_item else None)
        it = sys_item or (c["cause"][1] if c["cause"] else None)
        if it:
            react_n[it] += 1
            react_in[it] += c["in"]
            react_out[it] += c["out"]
        if c["key"]:
            src_tok["｜".join(c["key"])] += c["in"] + c["out"]
            src_lat["｜".join(c["key"])] += c["lat"]
    for before, tok, it, key in injections:
        reread[it] += tok * (len(calls) - before)
        # 被叫去多跑的呼叫已整筆算給觸發它的來源；注入只算在其他呼叫裡被重讀的量，不重複計
        src_tok["｜".join(key)] += tok * sum(1 for c in call_list[before:] if not c["key"])
    item_ms.update(ext_ms)
    entry, entry_cards, entry_trunc = Counter(), Counter(), Counter()
    ep = seg_dir / "logs" / "_this_session" / "guard-entry.jsonl"
    if ep.is_file():
        for line in ep.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r.get("event") != "ask":
                continue
            entry[r["entry"]] += 1
            entry_cards[r["entry"]] += len(r.get("cards") or [])
            entry_trunc[r["entry"]] += int(bool(r.get("truncated")))
    for t in turns:
        t["started"], t["ended"] = t.pop("_start").isoformat(), t.pop("_end").isoformat()
    return {
        "turns": turns, "transcripts": len(tx_files), "hook_cancelled": cancelled,
        "cost": max([t["cost_cum"] for t in turns] or [0]),
        "model_usage_cum": {k: {"in": v.get("inputTokens", 0) + v.get("cacheReadInputTokens", 0) + v.get("cacheCreationInputTokens", 0),
                                "out": v.get("outputTokens", 0)} for k, v in cum_mu.items()},
        "guardian_event_ms": dict(event_ms), "ext_hook_ms": dict(ext_ms),
        "item_ms": dict(item_ms), "item_tok": dict(item_tok), "item_inject_n": dict(item_inject_n),
        "unmapped_seg_ms": dict(unmapped_seg), "unmapped_tag_tok": dict(unmapped_tag),
        "entry_asks": dict(entry), "entry_cards": dict(entry_cards), "entry_truncated": dict(entry_trunc),
        "sys_tool_calls": dict(tool_calls), "sys_tool_out_tok": dict(tool_out),
        "api_calls": len(calls), "calls_s": sum(c["lat"] for c in call_list), "react_n": dict(react_n), "react_in": dict(react_in), "react_out": dict(react_out),
        "reread_tok": dict(reread), "src_tok": dict(src_tok), "src_lat": dict(src_lat), "src_ms": dict(src_ms),
    }


def measure_run(res_dir, est):
    segs = {p.name: measure_segment(p, est) for p in sorted(res_dir.iterdir()) if p.is_dir() and re.fullmatch(r"B-\d", p.name)}
    turns = [t for s in segs.values() for t in s["turns"]]
    items_ms, items_tok, items_n, calls, calls_out = Counter(), Counter(), Counter(), Counter(), Counter()
    react_n, react_in, react_out, reread = Counter(), Counter(), Counter(), Counter()
    src_tok, src_lat, src_ms = Counter(), Counter(), Counter()
    for s in segs.values():
        src_tok.update(s["src_tok"])
        src_lat.update(s["src_lat"])
        src_ms.update(s["src_ms"])
        items_ms.update(s["item_ms"])
        items_tok.update(s["item_tok"])
        items_n.update(s["item_inject_n"])
        calls.update(s["sys_tool_calls"])
        calls_out.update(s["sys_tool_out_tok"])
        react_n.update(s["react_n"])
        react_in.update(s["react_in"])
        react_out.update(s["react_out"])
        reread.update(s["reread_tok"])
    return {
        "segments": segs,
        "total": {
            "user_turns": len(turns), "num_turns": sum(t["num_turns"] for t in turns),
            "in": sum(t["in"] for t in turns), "out": sum(t["out"] for t in turns),
            "cache_read": sum(t["cache_read"] for t in turns),
            "wall_s": sum(t["wall_s"] for t in turns), "denials": sum(t["denials"] for t in turns),
            "cost": sum(s["cost"] for s in segs.values()),
            "hook_ms_guardian": sum(sum(s["guardian_event_ms"].values()) for s in segs.values()),
            "hook_ms_ext": sum(sum(s["ext_hook_ms"].values()) for s in segs.values()),
            "inject_tok": sum(items_tok.values()), "hook_cancelled": sum(s["hook_cancelled"] for s in segs.values()),
            "sys_tool_calls": sum(calls.values()), "sys_tool_out_tok": sum(calls_out.values()),
            "api_calls": sum(s["api_calls"] for s in segs.values()),
            "react_n": sum(react_n.values()), "react_in": sum(react_in.values()), "react_out": sum(react_out.values()),
            "reread_tok": sum(reread.values()),
        },
        "items_ms": dict(items_ms), "items_tok": dict(items_tok), "items_n": dict(items_n),
        "react_n": dict(react_n), "react_in": dict(react_in), "react_out": dict(react_out), "reread_tok": dict(reread),
        "src_tok": dict(src_tok), "src_lat": dict(src_lat), "src_ms": dict(src_ms),
        "sys_tool_calls": dict(calls), "sys_tool_out_tok": dict(calls_out),
    }


def mean(xs):
    return statistics.mean(xs) if xs else 0


def fmt_k(n):
    return f"{n / 1000:,.1f}k" if abs(n) >= 1000 else f"{n:,.0f}"


def pct(a, b):
    return f"{(b - a) / a * 100:+.0f}%" if a else "—"


def source_tables(off, on, gmap, tot):
    """④ 消耗來源：每個「來源｜項目」多耗的 token 與秒數＝現況兩跑平均 − 全關兩跑平均；對不上的列「其他」。"""
    extra_tok = tot(on, "in") + tot(on, "out") - tot(off, "in") - tot(off, "out")
    extra_s = tot(on, "wall_s") - tot(off, "wall_s")
    keys = sorted({k for r in off + on for k in r["src_tok"]} | {k for r in off + on for k in r["src_lat"]})
    detail = []
    for k in keys:
        tok = mean([r["src_tok"].get(k, 0) for r in on]) - mean([r["src_tok"].get(k, 0) for r in off])
        lat = mean([r["src_lat"].get(k, 0) for r in on]) - mean([r["src_lat"].get(k, 0) for r in off])
        src, item = k.split("｜", 1)
        detail.append((src, item, tok, lat))
    by_src = {s: [0.0, 0.0, None] for s in SOURCES}
    for s in SOURCES:
        by_src[s][1] = mean([r["src_ms"].get(s, 0) for r in on]) / 1000   # hook 本身跑的秒數（全關是 0）
    for src, item, tok, lat in detail:
        row = by_src.setdefault(src, [0.0, 0.0, None])
        row[0] += tok
        row[1] += lat
        if row[2] is None or tok > row[2][1]:
            row[2] = (item, tok)
    rest_tok = extra_tok - sum(v[0] for v in by_src.values())
    rest_s = extra_s - sum(v[1] for v in by_src.values())
    lines = ["", f"## 消耗來源（現況兩跑平均 − 全關兩跑平均；多出 {fmt_k(extra_tok)} token、{extra_s:.0f} 秒）", "",
             "| 來源 | 多耗 token | 佔多出部分 | 多耗秒 | 裡面最大的一項（對照 G） |", "|---|---|---|---|---|"]
    for s, (tok, sec, top) in sorted(by_src.items(), key=lambda kv: -kv[1][0]):
        top_txt = f"{top[0]}（{gmap.get(top[0], '—')}）" if top and top[1] > 0 else "—"
        lines.append(f"| {s} | {fmt_k(tok)} | {tok / extra_tok * 100:.1f}% | {sec:.0f} | {top_txt} |")
    lines.append(f"| {SRC_REST} | {fmt_k(rest_tok)} | {rest_tok / extra_tok * 100:.1f}% | {rest_s:.0f} | — |")
    lines += ["", "### 消耗來源明細（來源｜項目）", "", "| 來源 | 項目 | 對照 G | 多耗 token | 佔多出部分 | 多跑呼叫的秒數 |",
              "|---|---|---|---|---|---|"]
    for src, item, tok, lat in sorted(detail, key=lambda d: -d[2]):
        lines.append(f"| {src} | {item} | {gmap.get(item, '—')} | {fmt_k(tok)} | {tok / extra_tok * 100:.1f}% | {lat:.0f} |")
    per_item = Counter()
    per_item_lat = Counter()
    for _src, item, tok, lat in detail:
        per_item[item] += tok
        per_item_lat[item] += lat
    lines += ["", "### 各項目合計（同上口徑：各來源加總）", "",
              "| 項目 | 對照 G | hook 本身秒 | 多跑呼叫的秒數 | 多耗 token | 佔多出部分 |", "|---|---|---|---|---|---|"]
    for item, tok in per_item.most_common():
        hook_s = mean([r["items_ms"].get(item, 0) for r in on]) / 1000
        lines.append(f"| {item} | {gmap.get(item, '—')} | {hook_s:.1f} | {per_item_lat[item]:.0f} | {fmt_k(tok)} | "
                     f"{tok / extra_tok * 100:.1f}% |")
    return lines


def report(runs):
    off = [r for arm, _d, r in runs if arm == "off"]
    on = [r for arm, _d, r in runs if arm == "on"]
    keys = []
    for r in off + on:
        for sname, s in r["segments"].items():
            for t in s["turns"]:
                if (sname, t["id"]) not in keys:
                    keys.append((sname, t["id"]))

    def per_turn(rs, k, field):
        return mean([sum(t[field] for t in r["segments"].get(k[0], {"turns": []})["turns"] if t["id"] == k[1]) for r in rs])

    def tot(rs, field):
        return mean([r["total"][field] for r in rs])
    lines = ["## 每回合（兩跑平均；原本＝hook 全關，後來＝現況）", "",
             "| 回合 | 輸入 token 原本→後來 | 輸出 token 原本→後來 | 牆鐘秒 原本→後來 | 其中 guardian hook 秒（後來） | 注入 token（後來，估） |",
             "|---|---|---|---|---|---|"]
    for k in keys:
        lines.append(f"| {k[0]} {k[1]} | {fmt_k(per_turn(off, k, 'in'))}→{fmt_k(per_turn(on, k, 'in'))} | "
                     f"{fmt_k(per_turn(off, k, 'out'))}→{fmt_k(per_turn(on, k, 'out'))} | "
                     f"{per_turn(off, k, 'wall_s'):.0f}→{per_turn(on, k, 'wall_s'):.0f} | {per_turn(on, k, 'hook_ms') / 1000:.0f} | "
                     f"{fmt_k(per_turn(on, k, 'inject_tok'))} |")
    lines.append(f"| **整題** | {fmt_k(tot(off, 'in'))}→{fmt_k(tot(on, 'in'))}（{pct(tot(off, 'in'), tot(on, 'in'))}） | "
                 f"{fmt_k(tot(off, 'out'))}→{fmt_k(tot(on, 'out'))}（{pct(tot(off, 'out'), tot(on, 'out'))}） | "
                 f"{tot(off, 'wall_s'):.0f}→{tot(on, 'wall_s'):.0f}（{pct(tot(off, 'wall_s'), tot(on, 'wall_s'))}） | "
                 f"{tot(on, 'hook_ms_guardian') / 1000:.0f}（其他 hook {tot(on, 'hook_ms_ext') / 1000:.0f}） | {fmt_k(tot(on, 'inject_tok'))} |")
    user_turns = mean([r["total"]["user_turns"] for r in on]) or 1
    lines += ["", f"## 項目（現況兩跑平均，每回合＝整題÷{user_turns:g} 回合；hook 秒與注入在全關時都是 0）", "",
              "| 項目 | 對照 G | 每回合多耗秒 | 整題多耗秒 | 注入 token（估） | 注入×之後重讀（估） | 為它多做的呼叫 全關→現況 | 那些呼叫的輸入／輸出 token（現況） |",
              "|---|---|---|---|---|---|---|---|"]
    gmap = {i[0]: i[1] for i in ITEMS} | {OTHER: "—"}
    for n in [i[0] for i in ITEMS] + [OTHER]:
        ms, tok = mean([r["items_ms"].get(n, 0) for r in on]), mean([r["items_tok"].get(n, 0) for r in on])
        rn_off, rn_on = mean([r["react_n"].get(n, 0) for r in off]), mean([r["react_n"].get(n, 0) for r in on])
        if ms == 0 and tok == 0 and rn_on == 0 and rn_off == 0:
            continue
        lines.append(f"| {n} | {gmap[n]} | {ms / 1000 / user_turns:.1f} | {ms / 1000:.1f} | {fmt_k(tok)} | "
                     f"{fmt_k(mean([r['reread_tok'].get(n, 0) for r in on]))} | {rn_off:g}→{rn_on:g} | "
                     f"{fmt_k(mean([r['react_in'].get(n, 0) for r in on]))}／{fmt_k(mean([r['react_out'].get(n, 0) for r in on]))} |")
    lines.append(f"| **合計** | | {mean([sum(r['items_ms'].values()) for r in on]) / 1000 / user_turns:.1f} | "
                 f"{mean([sum(r['items_ms'].values()) for r in on]) / 1000:.1f} | {fmt_k(tot(on, 'inject_tok'))} | "
                 f"{fmt_k(tot(on, 'reread_tok'))} | {tot(off, 'react_n'):g}→{tot(on, 'react_n'):g} | "
                 f"{fmt_k(tot(on, 'react_in'))}／{fmt_k(tot(on, 'react_out'))} |")
    lines.append(f"\n模型呼叫次數（兩跑平均）：全關 {tot(off, 'api_calls'):g} → 現況 {tot(on, 'api_calls'):g}")
    lines += source_tables(off, on, gmap, tot)
    lines += ["", "## AI 呼叫系統工具（mcp__workflow-guardian__*；兩跑平均）", "", "| 工具 | 全關 | 現況 | 現況含這些呼叫的回覆輸出 token（推論） |",
              "|---|---|---|---|"]
    tools = sorted({k for r in off + on for k in r["sys_tool_calls"]})
    for k in tools:
        lines.append(f"| {k} | {mean([r['sys_tool_calls'].get(k, 0) for r in off]):g} | {mean([r['sys_tool_calls'].get(k, 0) for r in on]):g} | "
                     f"{fmt_k(mean([r['sys_tool_out_tok'].get(k, 0) for r in on]))} |")
    lines += ["", "## 逐跑原始數字", "",
              "| 跑 | 回合 | num_turns | 輸入 | 其中讀快取 | 輸出 | 牆鐘秒 | guardian hook 秒 | 其他 hook 秒 | 注入 token（估） | 被擋 | hook_cancelled | 美元（參考） |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for arm, d, r in runs:
        t = r["total"]
        lines.append(f"| {d}（{arm}） | {t['user_turns']} | {t['num_turns']} | {t['in']:,} | {t['cache_read']:,} | {t['out']:,} | "
                     f"{t['wall_s']:.0f} | {t['hook_ms_guardian'] / 1000:.1f} | {t['hook_ms_ext'] / 1000:.1f} | "
                     f"{t['inject_tok']:,} | {t['denials']} | {t['hook_cancelled']} | {t['cost']:.2f} |")
    lines += ["", "## 逐跑逐回合", "", "| 跑 | 段 | 回合 | 輸入 | 輸出 | 牆鐘秒 | num_turns | 被擋 | guardian hook 秒 | 注入 token（估） |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for arm, d, r in runs:
        for sname, s in r["segments"].items():
            for t in s["turns"]:
                lines.append(f"| {d}（{arm}） | {sname} | {t['id']} | {t['in']:,} | {t['out']:,} | {t['wall_s']:.0f} | {t['num_turns']} | "
                             f"{t['denials']} | {t['hook_ms'] / 1000:.1f} | {t['inject_tok']:,} |")
    lines += ["", "## 切入點帳（現況各跑：E 代號 問幾次／送幾張卡／截斷幾次）", ""]
    for arm, d, r in runs:
        if arm != "on":
            continue
        e = Counter()
        for s in r["segments"].values():
            for k, v in s["entry_asks"].items():
                e[k] += v
        parts = []
        for k in sorted(e):
            cards = sum(s["entry_cards"].get(k, 0) for s in r["segments"].values())
            trunc = sum(s["entry_truncated"].get(k, 0) for s in r["segments"].values())
            parts.append(f"{k} {e[k]}／{cards}／{trunc}")
        lines.append(f"- {d}：" + ("、".join(parts) or "無帳"))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", required=True, help="逗號分隔的 組:日期資料夾，組＝off／on")
    ap.add_argument("--kit", default=DEFAULT_KIT)
    ap.add_argument("--live", default=DEFAULT_LIVE)
    ap.add_argument("--out", help="完整數字寫成 JSON")
    a = ap.parse_args()
    est = load_estimator(a.live)
    runs = []
    for spec in a.runs.split(","):
        arm, d = spec.split(":", 1)
        if arm not in ("off", "on"):
            ap.error(f"組只收 off／on：{spec}")
        res = Path(a.kit) / "results" / d
        if not res.is_dir():
            ap.error(f"找不到材料 {res}")
        runs.append((arm, d, measure_run(res, est)))
    print(report(runs))
    unmapped = Counter()
    for _arm, _d, r in runs:
        for s in r["segments"].values():
            unmapped.update({f"分段 {k}": v for k, v in s["unmapped_seg_ms"].items()})
            unmapped.update({f"標籤 {k}": v for k, v in s["unmapped_tag_tok"].items()})
    if unmapped:
        print("\n⚠ 沒歸到項目的（分段＝ms、標籤＝token）：" + "；".join(f"{k} {v}" for k, v in unmapped.most_common()))
    if a.out:
        Path(a.out).write_text(json.dumps([{"arm": arm, "date": d, **r} for arm, d, r in runs], ensure_ascii=False, indent=1,
                                          default=str), encoding="utf-8")
    off = [r["total"] for arm, _d, r in runs if arm == "off"]
    on = [r["total"] for arm, _d, r in runs if arm == "on"]
    print(f"B6_MEASURE DONE runs={len(runs)} off_in={mean([t['in'] for t in off]):.0f} on_in={mean([t['in'] for t in on]):.0f} "
          f"off_wall_s={mean([t['wall_s'] for t in off]):.0f} on_wall_s={mean([t['wall_s'] for t in on]):.0f}")


if __name__ == "__main__":
    main()

"""first_turn_breakdown.py — 改 code 題（B′）第一回合「加子命令」：v6 守門全開比全關多出的輸入 token，拆到來源與閘。

做什麼
  只讀 wave2-kit 收好的無頭實跑紀錄（各跑 B-1/transcript/*.jsonl、B-1/turns/B-1-t1.json），只看第一個使用者回合。
  1. 模型呼叫：transcript 的 assistant 列依 message.id 合併成一次呼叫；輸入 T＝input＋cache_creation＋cache_read（usage，實測）。
     回合合計對帳 turns JSON 的 usage（rj_table／b6_measure 同口徑）。
  2. 相鄰兩次呼叫的輸入差 D_k＝T_k−T_{k−1}＝上一次的輸出 O_{k−1}（output_tokens，實測）＋這中間新進 context 的東西 R_k
     （工具結果、hook 注入、擋訊息、CC 自己的提醒）。R_k 總量是實測；R_k 分給各段用估算比例（中日韓字×A＋其他字×B＋每段×C，
     A/B/C 拿全部跑的 R_k 迴歸），段內分配是推論。ToolSearch 載入的工具定義看不到字，用單獨載入那幾次的殘差量成定值。
     第一次呼叫裡的開場注入（SessionStart＋UserPromptSubmit）＝現況 T_0−全關 T_0 平均（實測差）。
  3. 呼叫分類（每次呼叫只進一類）：
     a 被擋重做：所有工具都被 PreToolUse 擋的那次、它之後到「下一次寫檔成功」之前只做讀檔／宣告／need_goal 的呼叫；
       Stop 擋（hook_blocking_error）之後被迫重寫收尾的那次。
     d 守門要求的額外動作：只呼叫 need_goal（或只載入它）的呼叫、只交宣告行（Bash 的 # 定位｜／動資料檔｜／改舊測試｜）的呼叫、
       本回合定位閘擋過之後只用 Read 讀檔的呼叫（全關三跑第一回合 Read 0 次）、Stop 注入（不擋）引出的那次重寫。
     其餘＝照常呼叫。
  4. 記帳（每格「呼叫×context 段」只進一類，不重複）：
     a／d 呼叫 → 整次輸入記 a1／d1；
     照常呼叫 → 輸入拆成 context 裡各段：PreToolUse 擋訊息與 Stop 擋訊息 → b；hook 注入（additionalContext）→ c；
       a／d 呼叫留下的輸出與工具結果、照常呼叫裡 need_goal 的那幾塊與 need_goal 工具定義 → a2／d2；其餘 → 照常。
  5. e＝照常合計−全關平均（AI 自己多讀多寫、多跑的照常呼叫；可為負）。多出＝a＋b＋c＋d＋e，恆等。
  6. 秒數（實測）：每次呼叫的送出＝transcript 的 api-request 列時間，回完＝這次回應最後一個區塊寫入的時間；
     另算「送出到下一次送出」（含這次的工具執行與 PostToolUse／PreToolUse hook；最後一次算到回合結束，含 Stop hook）。
     來源的秒＝它的額外呼叫（a1／d1）加總。回合牆鐘＝回合 JSON _meta 起訖（004 口徑），對帳 _fm/measure.json。

怎麼跑
  python -X utf8 first_turn_breakdown.py [--runs 2026-10-23-CCon-R1,2026-10-23-CCon-R2] [--cross 2026-10-23-CCon-1,…]
      [--off 2026-10-23-CCoff-1,…] [--calls] [--denies] [--json <輸出>]
  --calls 印每次呼叫的分類（稽核用）；--denies 印主樣本定位閘每一筆擋的理由分類與 transcript 行號（規則見 ovh_denies）。
  尾行 FIRST_TURN DONE runs=… off_avg=… r1=… r2=… extra_avg=… a=… b=… c=… d=… e=… top1=… wall_off=<秒> wall_extra=<秒> secs=<秒> selfcheck=…
  （token 以萬為單位；wall_extra＝主樣本回合牆鐘減全關平均；secs＝主樣本額外呼叫送出到回完的合計平均）
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

RES = Path.home() / ".claude" / "workflow" / "inbox" / "wave2-kit" / "results"
DEF_RUNS = "2026-10-23-CCon-R1,2026-10-23-CCon-R2"
DEF_CROSS = "2026-10-23-CCon-1,2026-10-23-CCon-2,2026-10-23-CCon-3"
DEF_OFF = "2026-10-23-CCoff-1,2026-10-23-CCoff-2,2026-10-23-CCoff-3"
NEED_GOAL = "mcp__workflow-guardian__need_goal"
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
WINDOW_OK = {"Read", "Grep", "Glob", "ToolSearch", NEED_GOAL}
DECL_MARK = {"定位｜": "Guardian:OverviewHub", "動資料檔｜": "Guardian:DataFileAsk", "改舊測試｜": "Guardian:OldTest"}
OVH = "Guardian:OverviewHub"
DOC_EXT = {".md", ".txt", ".rst", ".json", ".csv", ".toml", ".yaml", ".yml", ".ini", ".cfg"}
TAG_RE = re.compile(r"\[(Guardian:[\w\-]+|NeedGoal|Atom[^\]]*|[A-Za-z][\w :\-]*?)\]")
BLOCK_SPLIT = re.compile(r"\n(?=\S{0,4}\[[A-Za-z])")
DENY_RE = re.compile(r"^(PreToolUse|PermissionRequest):\w+ hook error")
LOCAL_TZ = datetime.now().astimezone().tzinfo
CATS = ["a1", "a2", "b", "c", "d1", "d2"]
CAT_NAME = {"a": "a 被擋後重做", "b": "b 擋訊息被重讀", "c": "c 注入被重讀", "d": "d 守門要求的額外動作", "e": "e 其餘（AI 自己的走法）"}


def local_naive(ts):
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return dt.astimezone(LOCAL_TZ).replace(tzinfo=None) if dt.tzinfo else dt


def is_cjk(ch):
    return ord(ch) >= 0x2E80


def feats(text):
    cjk = sum(1 for ch in text if is_cjk(ch))
    return cjk, len(text) - cjk


def first_tag(text):
    m = TAG_RE.search(text or "")
    if not m:
        return "?"
    t = m.group(1)
    return "Atom（記憶卡）" if t.startswith("Atom") else t


def tr_text(content):
    if isinstance(content, str):
        return content
    return "\n".join(x.get("text", "") for x in content or [] if isinstance(x, dict))


def ng_action(inp):
    return f"need_goal（{(inp or {}).get('action', '?')}）"


def decl_gate(tu):
    if tu["name"] not in ("Bash", "PowerShell"):
        return None
    for line in (tu.get("input") or {}).get("command", "").splitlines():
        s = line.strip()
        if s.startswith("#"):
            for mark, gate in DECL_MARK.items():
                if mark in s:
                    return gate
    return None


def toolsearch_targets(tu):
    q = ((tu.get("input") or {}).get("query") or "")
    return [x.strip() for x in q[len("select:"):].split(",")] if q.startswith("select:") else []


class Piece:
    """context 裡的一段：k＝從第幾次呼叫起在輸入裡；cat＝a2/b/c/d2/base；src＝來源標籤；est＝估算；tok＝實測量分下來的 token。"""
    __slots__ = ("k", "cat", "src", "cjk", "oth", "est", "tok", "kind", "owner", "event")

    def __init__(self, k, kind, src, text="", cat=None, owner=None, event=None):
        self.k, self.kind, self.src, self.cat, self.owner, self.event = k, kind, src, cat, owner, event
        self.cjk, self.oth = feats(text)
        self.est = self.tok = 0.0


def parse_session(path):
    """transcript → 模型呼叫序列；每次呼叫帶 before（上一次呼叫之後進 context 的段）。"""
    rows = [json.loads(line) for line in path.open(encoding="utf-8")]
    calls, by_id, tool_uses, pending, reqs = [], {}, {}, [], []
    for r in rows:
        t = r.get("type")
        if t == "api-request":
            reqs.append(local_naive(r["timestamp"]))
        if t == "assistant":
            m = r["message"]
            mid = m.get("id")
            if mid not in by_id:
                u = m.get("usage") or {}
                c = {"id": mid, "ts": local_naive(r["timestamp"]), "blocks": [], "before": pending,
                     "T": (u.get("input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0),
                     "O": u.get("output_tokens") or 0,
                     "think": ((u.get("output_tokens_details") or {}).get("thinking_tokens") or 0)}
                by_id[mid] = c
                calls.append(c)
                pending = []
            by_id[mid]["last"] = local_naive(r["timestamp"])     # 最後一個回應區塊寫入的時間＝這次呼叫回完
            for b in m.get("content", []):
                by_id[mid]["blocks"].append(b)
                if b.get("type") == "tool_use":
                    tool_uses[b["id"]] = (len(calls) - 1, b)
        elif t in ("user", "attachment"):
            pending.append(r)
    # 送出時間：api-request 列（每次呼叫一列）。數量對得上就照順序配；對不上就取這次呼叫第一個區塊之前最近的那一列
    for k, c in enumerate(calls):
        if len(reqs) == len(calls) and reqs[k] <= c["ts"]:
            c["req"] = reqs[k]
        else:
            before = [q for q in reqs if q <= c["ts"]]
            c["req"] = before[-1] if before else None
    return calls, tool_uses


def before_pieces(k, rows, tool_uses):
    """上一次呼叫之後新進 context 的段。"""
    out = []
    for r in rows:
        if r.get("type") == "attachment":
            a = r["attachment"]
            if not r.get("rendered"):
                continue
            rendered = "\n".join(x.get("content", "") if isinstance(x.get("content"), str) else json.dumps(x.get("content"), ensure_ascii=False)
                                 for x in r["rendered"])
            if a["type"] == "hook_additional_context":
                ev = a.get("hookEvent")
                for text in a.get("content") or []:
                    for blk in BLOCK_SPLIT.split(text):
                        out.append(Piece(k, "inject", f"{ev}｜{first_tag(blk)}", blk, cat="c", event=ev))
            elif a["type"] == "hook_blocking_error":
                text = (a.get("blockingError") or {}).get("blockingError", "")
                out.append(Piece(k, "block", f"{first_tag(text)}（Stop 擋，system 那份）", rendered, cat="b", event=a.get("hookEvent")))
            else:
                out.append(Piece(k, "cc", f"CC 提醒（{a['type']}）", rendered, cat="base"))
            continue
        content = r["message"]["content"]
        if isinstance(content, str):
            if r.get("isMeta") and content.startswith("Stop hook feedback:"):
                out.append(Piece(k, "block", f"{first_tag(content)}（Stop 擋，使用者訊息那份）", content, cat="b", event="Stop"))
            else:
                out.append(Piece(k, "prompt", "使用者訊息", content, cat="base"))
            continue
        for b in content:
            if b.get("type") != "tool_result":
                out.append(Piece(k, "prompt", "使用者訊息", json.dumps(b, ensure_ascii=False), cat="base"))
                continue
            owner, tu = tool_uses.get(b.get("tool_use_id"), (None, {}))
            text = tr_text(b.get("content"))
            if b.get("is_error") and DENY_RE.match(text):
                gate = first_tag(text)
                main, *cards = text.split("\n判準卡（")
                out.append(Piece(k, "deny", f"{gate}｜擋訊息本文", main, cat="b", owner=owner))
                if cards:
                    out.append(Piece(k, "deny", f"{gate}｜擋訊息附的判準卡", "\n判準卡（".join(cards), cat="b", owner=owner))
            elif tu.get("name") == "ToolSearch":
                p = Piece(k, "schema", "工具定義", "", cat=None, owner=owner)
                p.src = "+".join(toolsearch_targets(tu))
                out.append(p)
            elif tu.get("name") == NEED_GOAL:
                out.append(Piece(k, "ng_result", ng_action(tu.get("input")), text, cat=None, owner=owner))
            else:
                out.append(Piece(k, "result", f"工具結果（{tu.get('name', '?')}）", text, cat=None, owner=owner))
    return out


def load_segment(name):
    seg = RES / name / "B-1"
    tj = json.loads((seg / "turns" / "B-1-t1.json").read_text(encoding="utf-8"))
    meta, u = tj["_meta"], tj.get("usage") or {}
    assert meta.get("id") == "first", f"{name}: B-1-t1 不是 first 回合"
    paths = sorted((seg / "transcript").glob("*.jsonl"))
    assert len(paths) == 1, f"{name}: transcript 應只有一支，找到 {len(paths)}"
    calls, tool_uses = parse_session(paths[0])
    for k, c in enumerate(calls):
        c["pieces"] = before_pieces(k, c["before"], tool_uses)
    start, end = local_naive(meta["started"]), local_naive(meta["ended"])
    turn = [k for k, c in enumerate(calls) if start <= c["ts"] <= end]
    assert turn == list(range(len(turn))), f"{name}: 第一回合的呼叫不是從頭連續"
    # 秒數：model_s＝送出到回完（實測）；slot_s＝送出到下一次送出（最後一次到回合結束），含這次的工具執行與 hook（實測）
    n = len(turn)
    for k in range(n):
        c = calls[k]
        nxt = calls[k + 1]["req"] if k + 1 < n and calls[k + 1].get("req") else end
        c["model_s"] = (c["last"] - c["req"]).total_seconds() if c.get("req") else 0.0
        c["slot_s"] = (nxt - c["req"]).total_seconds() if c.get("req") else 0.0
    return {"name": name, "calls": calls, "turn_n": n, "tool_uses": tool_uses,
            "wall_s": (end - start).total_seconds(),
            "pre_s": (calls[0]["req"] - start).total_seconds() if n and calls[0].get("req") else 0.0,
            "turn_in": (u.get("input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0)}


# ─── 估算係數：R_k ≈ A·中日韓字＋B·其他字＋C·段數（全部跑、整段 session 的相鄰呼叫，不含 ToolSearch 那幾次）─────
def fit_estimator(runs):
    X, y = [], []
    for run in runs:
        calls = run["calls"]
        for k in range(1, len(calls)):
            ps = calls[k]["pieces"]
            if not ps or any(p.kind == "schema" for p in ps):
                continue
            R = calls[k]["T"] - calls[k - 1]["T"] - calls[k - 1]["O"]
            X.append([sum(p.cjk for p in ps), sum(p.oth for p in ps), len(ps)])
            y.append(R)
    X, y = np.array(X, float), np.array(y, float)
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    pred = X @ coef
    rel = np.abs(pred - y).sum() / np.abs(y).sum()
    return coef, len(y), float(rel)


def est_of(p, coef, schema_size):
    if p.kind == "schema":
        return sum(schema_size.get(t, 0.0) for t in p.src.split("+"))
    return max(coef[0] * p.cjk + coef[1] * p.oth + coef[2], 1.0)


def fit_schema(runs, coef):
    """ToolSearch 單獨載入一支工具的那幾次：R_k − 其他段估算 ＝ 那支工具定義的 token 數（實測殘差）。"""
    got = defaultdict(list)
    for run in runs:
        calls = run["calls"]
        for k in range(1, len(calls)):
            ps = calls[k]["pieces"]
            sch = [p for p in ps if p.kind == "schema"]
            if len(sch) != 1 or "+" in sch[0].src:
                continue
            R = calls[k]["T"] - calls[k - 1]["T"] - calls[k - 1]["O"]
            got[sch[0].src].append(R - sum(est_of(p, coef, {}) for p in ps if p.kind != "schema"))
    return {t: sum(v) / len(v) for t, v in got.items()}, {t: v for t, v in got.items()}


# ─── 呼叫分類 ───────────────────────────────────────────────────────────
def classify(run):
    calls, n = run["calls"], run["turn_n"]
    # 被擋的 tool_use：從 deny 段回推（tool_result 的 tool_use_id）
    denied = {}
    for k, c in enumerate(calls[:n + 1]):
        for r in c["before"]:
            if r.get("type") != "user" or isinstance(r["message"]["content"], str):
                continue
            for b in r["message"]["content"]:
                if b.get("type") == "tool_result" and b.get("is_error") and DENY_RE.match(tr_text(b.get("content"))):
                    denied[b["tool_use_id"]] = first_tag(tr_text(b.get("content")))
    run["denied"] = denied
    cls, gate = [], []
    window, seen_ovh = None, False
    for k in range(n):
        c = calls[k]
        tus = [b for b in c["blocks"] if b.get("type") == "tool_use"]
        stop_block = [p for p in c["pieces"] if p.kind == "block" and p.event == "Stop"]
        stop_inj = [p for p in c["pieces"] if p.kind == "inject" and p.event == "Stop"]
        dn = [t for t in tus if t["id"] in denied]
        if stop_block:
            cls.append("a"); gate.append(stop_block[0].src.split("（")[0])
        elif stop_inj:
            cls.append("d"); gate.append(stop_inj[0].src.split("｜")[1])
        elif tus and len(dn) == len(tus):
            cls.append("a"); gate.append(denied[dn[0]["id"]])
            window = denied[dn[0]["id"]]
        elif window and tus and all(t["name"] in WINDOW_OK or decl_gate(t) for t in tus):
            cls.append("a"); gate.append(window)
        else:
            window = None
            if tus and all(t["name"] == NEED_GOAL or (t["name"] == "ToolSearch" and toolsearch_targets(t) == [NEED_GOAL]) for t in tus):
                ng = [t for t in tus if t["name"] == NEED_GOAL]
                cls.append("d"); gate.append(ng_action(ng[0]["input"]) if ng else "need_goal（載入工具）")
            elif tus and all(decl_gate(t) for t in tus):
                cls.append("d"); gate.append(f"{decl_gate(tus[0])}｜交宣告行")
            elif tus and all(t["name"] == "Read" for t in tus) and seen_ovh:
                docs = all(Path((t.get("input") or {}).get("file_path", "")).suffix.lower() in DOC_EXT for t in tus)
                cls.append("d"); gate.append(f"{OVH}｜擋過後先 Read" + ("（文件檔，推論較弱）" if docs else "（程式檔）"))
            else:
                cls.append("base"); gate.append("")
            if dn:
                window = denied[dn[0]["id"]]
        if any(denied.get(t["id"]) == OVH for t in tus):
            seen_ovh = True
    run["cls"], run["gate"] = cls, gate


def output_pieces(run, k, coef):
    """第 k 次呼叫的輸出（O_k，實測）在第 k+1 次起進 context：依區塊分類；thinking 照可見區塊的比例跟著分。"""
    c, cls, gate = run["calls"][k], run["cls"][k], run["gate"][k]
    O, think = c["O"], min(c["think"], c["O"])
    if cls in ("a", "d"):
        p = Piece(k + 1, "output", gate)
        p.cat, p.tok = cls + "2", float(O)
        return [p]
    vis = []
    for b in c["blocks"]:
        if b.get("type") == "thinking":
            continue
        text = b.get("text", "") if b.get("type") == "text" else json.dumps(b.get("input"), ensure_ascii=False)
        cjk, oth = feats(text)
        e = max(coef[0] * cjk + coef[1] * oth + coef[2], 1.0)
        if b.get("type") == "tool_use" and b["name"] == NEED_GOAL:
            vis.append(("d2", ng_action(b.get("input")), e))
        elif b.get("type") == "tool_use" and b["id"] in run["denied"]:
            vis.append(("a2", run["denied"][b["id"]], e))
        else:
            vis.append(("base", "AI 輸出", e))
    if not vis:
        vis = [("base", "AI 輸出", 1.0)]
    tot = sum(e for *_, e in vis)
    out = []
    for cat, src, e in vis:
        p = Piece(k + 1, "output", src)
        p.cat, p.tok = cat, O * e / tot
        out.append(p)
    return out


def allocate(run, coef, schema_size, off_T0):
    """把每次呼叫的輸入拆到段上，每段標類別；回傳全部段（含基底與輸出）。"""
    calls, n, cls, gate = run["calls"], run["turn_n"], run["cls"], run["gate"]
    pieces = []
    # 第 0 次：基底＋開場注入
    T0 = calls[0]["T"]
    inj = [p for p in calls[0]["pieces"] if p.kind == "inject"]
    inj0 = max(T0 - off_T0, 0.0) if inj else 0.0
    for p in inj:
        p.est = est_of(p, coef, schema_size)
    tot = sum(p.est for p in inj)
    for p in inj:
        p.tok = inj0 * p.est / tot
    base = Piece(0, "base", "系統基底（system prompt、工具清單、CLAUDE.md、技能清單、首則訊息）")
    base.cat, base.tok = "base", T0 - inj0
    pieces += [base] + inj
    run["inj0"], run["inj0_est"] = inj0, tot
    unexplained = 0.0
    for k in range(1, n):
        prev, c = calls[k - 1], calls[k]
        pieces += output_pieces(run, k - 1, coef)
        R = c["T"] - prev["T"] - prev["O"]
        ps = c["pieces"]
        for p in ps:
            p.est = est_of(p, coef, schema_size)
            owner_cls = cls[p.owner] if p.owner is not None and p.owner < n else "base"
            owner_gate = gate[p.owner] if p.owner is not None and p.owner < n else ""
            if p.kind in ("result", "ng_result", "schema"):
                if owner_cls in ("a", "d"):
                    p.cat, p.src = owner_cls + "2", owner_gate
                elif p.kind == "ng_result":
                    p.cat = "d2"
                elif p.kind == "schema" and NEED_GOAL in p.src.split("+"):
                    p.cat = "schema_split"
                else:
                    p.cat = "base"
        tot = sum(p.est for p in ps)
        if R <= 0 or tot <= 0:
            for p in ps:
                p.tok = 0.0
            if R != 0:
                q = Piece(k, "unexplained", "對不到段的差額")
                q.cat, q.tok = "base", float(R)
                pieces.append(q)
                unexplained += R
        else:
            for p in ps:
                p.tok = R * p.est / tot
        for p in ps:
            if p.cat == "schema_split":      # 一次載入 need_goal＋別支：need_goal 那份記 d2，別支照常
                share = schema_size.get(NEED_GOAL, 0.0) / max(p.est, 1.0)
                q = Piece(k, "schema", "need_goal 工具定義")
                q.cat, q.tok = "d2", p.tok * share
                p.cat, p.src, p.tok = "base", f"工具定義（{p.src.replace(NEED_GOAL + '+', '').replace('+' + NEED_GOAL, '')}）", p.tok * (1 - share)
                pieces.append(q)
            elif p.kind == "schema" and p.cat == "base":
                p.src = f"工具定義（{p.src}）"
        pieces += ps
    run["unexplained"] = unexplained
    return pieces


def account(run, pieces):
    """每次呼叫：a／d 整次輸入記 a1／d1；照常呼叫把當下 context 各段記到段的類別。回傳 {(cat, src): tok}、照常呼叫數。"""
    calls, n, cls, gate = run["calls"], run["turn_n"], run["cls"], run["gate"]
    acc = defaultdict(float)
    secs = defaultdict(lambda: [0.0, 0.0])      # 來源鍵 → [模型秒, 連同工具與 hook 的時段秒]，只算額外呼叫
    check = 0.0
    for j in range(n):
        if cls[j] in ("a", "d"):
            acc[(cls[j] + "1", gate[j])] += calls[j]["T"]
            s = secs[source_key(cls[j] + "1", gate[j])]
            s[0] += calls[j]["model_s"]
            s[1] += calls[j]["slot_s"]
            continue
        s = 0.0
        for p in pieces:
            if p.k <= j:
                acc[(p.cat, p.src)] += p.tok
                s += p.tok
        check = max(check, abs(s - calls[j]["T"]))
    run["max_call_err"] = check
    run["secs"] = secs
    return acc


def cat_letter(cat):
    return "e" if cat == "base" else cat[0]


def source_key(cat, src):
    """前 5 大來源的歸併鍵：閘或注入名（不分 1／2 與子項）。"""
    if cat == "base":
        return None
    s = src
    if s.startswith("need_goal") or s == "need_goal 工具定義" or "NeedGoal" in s:
        return "NeedGoal 目標樹（need_goal 呼叫、工具定義、回饋注入）"
    m = re.search(r"Guardian:[\w\-]+", s)
    if m:
        return m.group(0)
    if s.startswith("UserPromptSubmit"):
        return "UserPromptSubmit 注入（記憶卡、Session:Context 等）"
    if s.startswith("SessionStart"):
        return "SessionStart 注入"
    return s


def wan(x):
    return f"{x / 1e4:.1f} 萬"


def analyze(name, coef, schema_size, off_T0):
    run = load_segment(name)
    classify(run)
    pieces = allocate(run, coef, schema_size, off_T0)
    run["acc"] = account(run, pieces)
    run["total"] = sum(run["calls"][j]["T"] for j in range(run["turn_n"]))
    run["base_by_src"] = defaultdict(float)
    for (cat, src), v in run["acc"].items():
        if cat == "base":
            run["base_by_src"][src.split("（")[0] if src.startswith("工具結果") or src.startswith("CC 提醒") else src] += v
    run["occ"] = occurrences(run)
    return run


def occurrences(run):
    """每跑出現幾次：擋（PreToolUse 擋訊息每筆 tool_result、Stop 擋每次）、注入段、額外呼叫。鍵＝(種類, 來源)。"""
    occ = defaultdict(int)
    n = run["turn_n"]
    for k in range(n):
        for p in run["calls"][k]["pieces"]:
            if (p.kind == "deny" and "本文" in p.src) or (p.kind == "block" and "system" in p.src):
                occ[("擋", source_key("b", p.src))] += 1
            elif p.kind == "inject":
                occ[("注入", source_key("c", p.src))] += 1
        if run["cls"][k] in ("a", "d"):
            occ[("額外呼叫", source_key(run["cls"][k] + "1", run["gate"][k]))] += 1
    return occ


def ovh_denies(name):
    """定位閘每一筆擋：transcript 行號（1 起算）、擋的理由、同一則回覆（落盤後的完整區塊）有沒有定位行、AI 下一則怎麼說。
    自動分類：陪擋＝「同樣被擋」那種一行短訊息 → d；擋訊息含「還沒讀過這個部位的檔」→ a；同一則回覆的文字或平行工具參數有「定位｜」
    → c；下一則文字說「讀不到」（AI 自認寫了，但同一則回覆裡看不到）→ e1；其餘 → b。"""
    path = sorted((RES / name / "B-1" / "transcript").glob("*.jsonl"))[0]
    rows = [json.loads(line) for line in path.open(encoding="utf-8")]
    blocks, order, msg_of = {}, [], {}
    for i, r in enumerate(rows, 1):
        if r.get("type") == "assistant":
            mid = r["message"]["id"]
            if mid not in blocks:
                blocks[mid] = []
                order.append(mid)
            for b in r["message"]["content"]:
                blocks[mid].append((i, b))
                if b.get("type") == "tool_use":
                    msg_of[b["id"]] = mid
    out = []
    for i, r in enumerate(rows, 1):
        if r.get("type") != "user" or isinstance(r["message"]["content"], str):
            continue
        for b in r["message"]["content"]:
            text = tr_text(b.get("content")) if b.get("type") == "tool_result" else ""
            if not (b.get("is_error") and DENY_RE.match(text) and OVH in text[:80]):
                continue
            mid = msg_of[b["tool_use_id"]]
            k = order.index(mid)
            tline, tu = next((li, x) for li, x in blocks[mid] if x.get("type") == "tool_use" and x["id"] == b["tool_use_id"])
            fp = tu["input"].get("file_path")
            target = (fp.replace("\\", "/").split("/")[-1] if fp
                      else "Bash：" + tu["input"].get("command", "").splitlines()[0][:30].replace("|", "｜"))
            same_text = [x.get("text", "") for _, x in blocks[mid] if x.get("type") == "text"]
            same_tools = [json.dumps(x.get("input"), ensure_ascii=False) for _, x in blocks[mid] if x.get("type") == "tool_use"]
            nxt = [x.get("text", "") for _, x in blocks[order[k + 1]] if x.get("type") == "text"] if k + 1 < len(order) else []
            short = "同樣被擋" in text[:200]
            if short:
                cat = "d"
            elif "還沒讀過這個部位的檔" in text:
                cat = "a"
            elif any("定位｜" in t for t in same_text + same_tools):
                cat = "c"
            elif any("讀不到" in t for t in nxt):
                cat = "e1"
            else:
                cat = "b"
            out.append({"line": i, "tool_line": tline, "call": k, "tool": tu["name"], "target": target.strip(), "cat": cat,
                        "loc_missing": "還沒交出定位" in text, "reads_missing": "還沒讀過這個部位的檔" in text,
                        "text_blocks": len(same_text), "thinking_blocks": sum(1 for _, x in blocks[mid] if x.get("type") == "thinking"),
                        "next": (nxt[0][:50] if nxt else "")})
    return path.name, out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", default=DEF_RUNS, help="主樣本（現況）")
    ap.add_argument("--cross", default=DEF_CROSS, help="交叉對照（004 現況）；給空字串跳過")
    ap.add_argument("--off", default=DEF_OFF, help="全關基準")
    ap.add_argument("--calls", action="store_true", help="印每次呼叫的分類")
    ap.add_argument("--denies", action="store_true", help="印主樣本定位閘每一筆擋的理由分類與 transcript 行號")
    ap.add_argument("--json")
    a = ap.parse_args()
    main_names = [x for x in a.runs.split(",") if x]
    cross_names = [x for x in a.cross.split(",") if x]
    off_names = [x for x in a.off.split(",") if x]
    all_names = off_names + main_names + cross_names
    raw = [load_segment(nm) for nm in all_names]
    coef, n_fit, rel = fit_estimator(raw)
    schema_size, schema_n = fit_schema(raw, coef)
    off_T0 = sum(r["calls"][0]["T"] for r in raw[:len(off_names)]) / len(off_names)
    print("## 估算係數（推論用；總量都是實測）")
    print(f"- R_k ≈ {coef[0]:.3f}×中日韓字 ＋ {coef[1]:.3f}×其他字 ＋ {coef[2]:.1f}×段數；{n_fit} 個相鄰呼叫差，平均絕對誤差 {rel:.1%}")
    print("- ToolSearch 載入的工具定義（單獨載入那幾次：實測差額−其他段估算）：" +
          "；".join(f"{t.split('__')[-1]} ≈ {v:,.0f} tok（{len(schema_n[t])} 次：{'、'.join(f'{x:,.0f}' for x in schema_n[t])}）"
                   for t, v in schema_size.items()))
    print(f"- 全關第一次呼叫輸入 T_0 平均 {off_T0:,.0f}")

    runs = {nm: analyze(nm, coef, schema_size, off_T0) for nm in all_names}
    print("- 估算式驗證：開場注入實測（現況 T_0−全關 T_0）對估算式算出的值：" +
          "；".join(f"{nm[11:]} {runs[nm]['inj0']:,.0f} 對 {runs[nm]['inj0_est']:,.0f}" for nm in main_names + cross_names))
    off = [runs[nm] for nm in off_names]
    off_avg = sum(r["total"] for r in off) / len(off)
    off_calls = sum(r["turn_n"] for r in off) / len(off)
    off_base_src = defaultdict(float)
    for r in off:
        for s, v in r["base_by_src"].items():
            off_base_src[s] += v / len(off)
    selfcheck = []
    print("\n## 每跑第一回合（實測）")
    print("| 跑 | 模型呼叫 | 輸入合計 | 回合 JSON 對帳 | 比全關平均 | 其中額外呼叫（a／d） | 開場注入 T_0 差 | 對不到段的差額 |")
    print("|---|---|---|---|---|---|---|---|")
    for nm in all_names:
        r = runs[nm]
        ok = r["total"] == r["turn_in"]
        if not ok:
            selfcheck.append(f"{nm} transcript {r['total']} ≠ turns {r['turn_in']}")
        na = sum(1 for x in r["cls"] if x == "a")
        nd = sum(1 for x in r["cls"] if x == "d")
        print(f"| {nm[11:]} | {r['turn_n']} | {r['total']:,}（{wan(r['total'])}） | {'相同' if ok else '不同'} | "
              f"{r['total'] - off_avg:+,.0f} | {na}／{nd} | {r['inj0']:,.0f} | {r['unexplained']:,.0f} |")
    print(f"\n全關平均 {off_avg:,.0f}（{wan(off_avg)}），呼叫 {off_calls:.1f} 次")
    for nm, want in (("2026-10-23-CCon-R1", 148.5), ("2026-10-23-CCon-R2", 166.4)):
        if nm in runs and round(runs[nm]["total"] / 1e4, 1) != want:
            selfcheck.append(f"{nm} {runs[nm]['total'] / 1e4:.1f} 萬 ≠ 報告 {want}")
    if round(off_avg / 1e4, 1) != 45.8:
        selfcheck.append(f"全關平均 {off_avg / 1e4:.1f} 萬 ≠ 報告 45.8")
    max_err = max(r["max_call_err"] for r in runs.values())
    if max_err > 1:
        selfcheck.append(f"逐呼叫拆段加總與 T 最大差 {max_err:.1f}")

    # 牆鐘：回合從送出到回完（回合 JSON _meta 起訖，004 口徑），對帳 _fm/measure.json 的同一回合 wall_s
    off_wall = sum(r["wall_s"] for r in off) / len(off)
    print("\n## 牆鐘（第一回合；實測）")
    print("| 跑 | 回合牆鐘（秒） | 比全關平均 | 額外呼叫：送出到回完合計 | 額外呼叫：連同工具與 hook 的時段合計 | 第一次送出前（開場 hook 等） | measure.json 對帳 |")
    print("|---|---|---|---|---|---|---|")
    for nm in all_names:
        r = runs[nm]
        try:
            mj = json.loads((RES / nm / "_fm" / "measure.json").read_text(encoding="utf-8"))
            mw = next(t["wall_s"] for t in mj["segments"]["B-1"]["turns"] if t["id"] == "first")
        except (OSError, KeyError, StopIteration, ValueError) as e:
            mw = None
            selfcheck.append(f"{nm} measure.json 讀不到第一回合 wall_s：{type(e).__name__}")
        if mw is not None and abs(mw - r["wall_s"]) > 1:
            selfcheck.append(f"{nm} 回合牆鐘 {r['wall_s']:.0f} ≠ measure.json {mw:.0f}")
        xm = sum(m for m, _ in r["secs"].values())
        xs = sum(s for _, s in r["secs"].values())
        r["x_model_s"], r["x_slot_s"] = xm, xs
        print(f"| {nm[11:]} | {r['wall_s']:.0f} | {r['wall_s'] - off_wall:+.0f} | {xm:.0f} | {xs:.0f} | {r['pre_s']:.0f} | "
              f"{'相同' if mw is not None and abs(mw - r['wall_s']) <= 1 else '不同'} |")
    print(f"\n全關平均 {off_wall:.0f} 秒；開場 hook 前置全關平均 {sum(r['pre_s'] for r in off) / len(off):.0f} 秒")

    def cat_table(names, title):
        print(f"\n## 分類表：{title}（多出＝該跑−全關平均；每類 token、佔多出的百分比）")
        print("| 類別 | " + " | ".join(nm[11:] for nm in names) + " | 平均 | 佔多出 |")
        print("|---|" + "---|" * (len(names) + 2))
        extra = {nm: runs[nm]["total"] - off_avg for nm in names}
        rows = {}
        for L in "abcde":
            vals = {}
            for nm in names:
                acc = runs[nm]["acc"]
                if L == "e":
                    vals[nm] = sum(v for (cat, _), v in acc.items() if cat == "base") - off_avg
                else:
                    vals[nm] = sum(v for (cat, _), v in acc.items() if cat_letter(cat) == L)
            rows[L] = vals
            avg = sum(vals.values()) / len(names)
            ex = sum(extra.values()) / len(names)
            print(f"| {CAT_NAME[L]} | " + " | ".join(f"{vals[nm]:,.0f}" for nm in names) + f" | {avg:,.0f} | {avg / ex:.0%} |")
            for sub in ("1", "2"):
                if L in "ad":
                    sv = {nm: sum(v for (cat, _), v in runs[nm]["acc"].items() if cat == L + sub) for nm in names}
                    lab = "　額外呼叫本身的輸入" if sub == "1" else "　它們的輸出／工具結果被之後照常呼叫重讀"
                    print(f"| {lab} | " + " | ".join(f"{sv[nm]:,.0f}" for nm in names) + f" | {sum(sv.values()) / len(names):,.0f} | |")
        ex = sum(extra.values()) / len(names)
        print("| **多出合計** | " + " | ".join(f"{extra[nm]:,.0f}" for nm in names) + f" | {ex:,.0f} | 100% |")
        return rows, extra

    def src_table(names, title):
        print(f"\n## 來源明細：{title}（類別×來源，平均 token；1＝額外呼叫本身、2＝它們留下的內容被重讀）")
        agg = defaultdict(float)
        for nm in names:
            for (cat, src), v in runs[nm]["acc"].items():
                if cat != "base":
                    agg[(cat, src)] += v / len(names)
        print("| 類別 | 來源 | 平均 token |")
        print("|---|---|---|")
        for (cat, src), v in sorted(agg.items(), key=lambda x: -x[1]):
            if v >= 500:
                print(f"| {cat} | {src} | {v:,.0f} |")
        top = defaultdict(lambda: defaultdict(float))
        per_run = defaultdict(lambda: defaultdict(float))
        for (cat, src), v in agg.items():
            top[source_key(cat, src)][cat] += v
        for nm in names:
            for (cat, src), v in runs[nm]["acc"].items():
                if cat != "base":
                    per_run[source_key(cat, src)][nm] += v
        ex = sum(runs[nm]["total"] - off_avg for nm in names) / len(names)
        print(f"\n## 前幾大來源：{title}（同一閘／注入跨類別加總；token 為平均，各跑另列；次數＝每跑：擋／注入段／額外呼叫；"
              "秒＝這個來源的額外呼叫，各次送出到回完加總，各跑／平均，括號內連同工具與 hook 的時段）")
        print("| 來源 | 平均合計 | 佔多出 | " + " | ".join(nm[11:] for nm in names) + " | a1 | a2 | b | c | d1 | d2 | 次數（" +
              "；".join(nm[11:] for nm in names) + "） | 秒（" + "／".join(nm[11:] for nm in names) + "／平均） |")
        print("|---|---|---|" + "---|" * len(names) + "---|---|---|---|---|---|---|---|")
        ranked = sorted(top.items(), key=lambda x: -sum(x[1].values()))
        for key, d in ranked:
            occ = "；".join("/".join(str(runs[nm]["occ"].get((kind, key), 0)) for kind in ("擋", "注入", "額外呼叫")) for nm in names)
            ms = [runs[nm]["secs"].get(key, [0.0, 0.0]) for nm in names]
            sec = ("／".join(f"{m:.0f}" for m, _ in ms) + f"／{sum(m for m, _ in ms) / len(ms):.0f}"
                   + f"（{'／'.join(f'{s:.0f}' for _, s in ms)}／{sum(s for _, s in ms) / len(ms):.0f}）")
            print(f"| {key} | {sum(d.values()):,.0f} | {sum(d.values()) / ex:.0%} | " +
                  " | ".join(f"{per_run[key][nm]:,.0f}" for nm in names) + " | " +
                  " | ".join(f"{d.get(c, 0):,.0f}" for c in CATS) + f" | {occ} | {sec} |")
        return ranked

    rows_main, extra_main = cat_table(main_names, "主樣本（現況兩跑）")
    ranked = src_table(main_names, "主樣本（現況兩跑）")
    print("\n## e 的組成（照常部分 − 全關平均，依段；主樣本平均）")
    srcs = set(off_base_src)
    for nm in main_names:
        srcs |= set(runs[nm]["base_by_src"])
    print("| 段 | 現況照常（平均） | 全關（平均） | 差 |")
    print("|---|---|---|---|")
    for s in sorted(srcs, key=lambda s: -abs(sum(runs[nm]["base_by_src"].get(s, 0) for nm in main_names) / len(main_names) - off_base_src.get(s, 0))):
        on_v = sum(runs[nm]["base_by_src"].get(s, 0) for nm in main_names) / len(main_names)
        print(f"| {s} | {on_v:,.0f} | {off_base_src.get(s, 0):,.0f} | {on_v - off_base_src.get(s, 0):+,.0f} |")
    nb = sum(sum(1 for x in runs[nm]["cls"] if x == "base") for nm in main_names) / len(main_names)
    print(f"照常呼叫：現況平均 {nb:.1f} 次；全關平均 {off_calls:.1f} 次")
    if cross_names:
        cat_table(cross_names, "交叉對照（004 現況三跑）")
        src_table(cross_names, "交叉對照（004 現況三跑）")
    if a.calls:
        for nm in main_names + cross_names + off_names:
            r = runs[nm]
            print(f"\n### 每次呼叫：{nm}")
            print("| # | 時間 | 輸入 T | 輸出 O | 送出到回完（秒） | 到下一次送出（秒） | 類別 | 閘／動作 | 工具 |")
            print("|---|---|---|---|---|---|---|---|---|")
            for k in range(r["turn_n"]):
                c = r["calls"][k]
                tools = ",".join(("✗" if b["id"] in r["denied"] else "") + b["name"].replace("mcp__workflow-guardian__", "")
                                 for b in c["blocks"] if b.get("type") == "tool_use") or "（文字）"
                print(f"| {k} | {c['ts']:%H:%M:%S} | {c['T']:,} | {c['O']:,} | {c['model_s']:.1f} | {c['slot_s']:.1f} | "
                      f"{r['cls'][k]} | {r['gate'][k]} | {tools} |")
    if a.denies:
        for nm in main_names:
            fname, ds = ovh_denies(nm)
            print(f"\n### 定位閘每一筆擋：{nm}（{fname}；行號 1 起算）")
            print("| 擋訊息行 | 工具呼叫行 | 呼叫 # | 工具 | 檔 | 缺讀檔 | 缺定位 | 同一則文字區塊數 | 同一則 thinking 區塊數 | 下一則開頭 | 分類 |")
            print("|---|---|---|---|---|---|---|---|---|---|---|")
            for d in ds:
                print(f"| {d['line']} | {d['tool_line']} | {d['call']} | {d['tool']} | {d['target']} | {'是' if d['reads_missing'] else ''} | "
                      f"{'是' if d['loc_missing'] else ''} | {d['text_blocks']} | {d['thinking_blocks']} | {d['next']} | {d['cat']} |")
    if a.json:
        out = {nm:{"total": r["total"], "turn_in": r["turn_in"], "calls": r["turn_n"], "cls": r["cls"], "gate": r["gate"],
                    "acc": {f"{c}|{s}": v for (c, s), v in r["acc"].items()}} for nm, r in runs.items()}
        out["_meta"] = {"coef": list(coef), "fit_rel_err": rel, "schema": schema_size, "off_avg": off_avg}
        Path(a.json).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for s in selfcheck:
        print(f"[自檢不符] {s}", file=sys.stderr)
    ex = sum(extra_main.values()) / len(main_names)
    parts = " ".join(f"{L}={sum(rows_main[L].values()) / len(main_names) / 1e4:.1f}" for L in "abcde")
    r1 = runs.get("2026-10-23-CCon-R1", {}).get("total", 0) / 1e4
    r2 = runs.get("2026-10-23-CCon-R2", {}).get("total", 0) / 1e4
    wall_extra = sum(runs[nm]["wall_s"] - off_wall for nm in main_names) / len(main_names)
    secs = sum(runs[nm]["x_model_s"] for nm in main_names) / len(main_names)
    print(f"FIRST_TURN DONE runs={len(main_names)} off_avg={off_avg / 1e4:.1f} r1={r1:.1f} r2={r2:.1f} extra_avg={ex / 1e4:.1f} {parts} "
          f"top1={(ranked[0][0].split('（')[0].replace(' ', '_') if ranked else 'none')} "
          f"wall_off={off_wall:.0f} wall_extra={wall_extra:.0f} secs={secs:.0f} selfcheck={'ok' if not selfcheck else 'mismatch'}")


if __name__ == "__main__":
    main()

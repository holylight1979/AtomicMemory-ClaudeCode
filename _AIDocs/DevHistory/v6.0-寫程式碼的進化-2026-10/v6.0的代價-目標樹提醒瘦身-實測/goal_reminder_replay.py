"""goal_reminder_replay.py — 目標樹提醒瘦身（三種情況一次全文、提示附樹一行）在改 code 題第一回合省了多少：事件帳重播。

做什麼
  只讀 wave2-kit 收好的無頭實跑紀錄（預設 004 現況兩跑 2026-10-23-CCon-R1、-R2 的 B-1 第一回合）。
  1. 拆段與 token 用共用量尺 first_turn_breakdown.py（--ruler）：每段 hook 注入在第幾次呼叫進 context、它的 token
     （相鄰呼叫輸入差的實測總量依估算式分到段；輸入＝input＋cache_creation＋cache_read）。
  2. 認出第一回合每段 [NeedGoal] 注入是哪一種：導讀卡附樹、目標視角重看、讀入範圍、外部主張、糾正、每則訊息（這刀改的），
     need_goal 寫入的回覆（送全樹，這刀不改）、要改碼先立樹那一行（不改）。
  3. 同一串事件（同一句使用者訊息、同一個 set 輸入、同部位、同回合）在 repo 外的暫存資料根裡分別交舊碼（--old-tree）與
     新碼（--new-tree，預設本 repo）產生文字；新 token＝實測 token×估算式（新文字）÷估算式（舊碼重播的文字）。
     舊碼重播的字數對帳 transcript 那段的字數（印差幾 %，程式文字自 10-23 以來的小改會有幾字差）。
  4. 這段的花費＝token×之後被重讀幾次（第一回合從它進 context 那次起的每一次呼叫，含被擋重做與守門要求的額外呼叫）。
  5. 擋次：第一回合 PreToolUse／Stop 擋訊息裡 NeedGoal 開頭的筆數；秒：這刀不增減模型呼叫，額外呼叫秒數不變（印 0）。

怎麼跑
  舊碼樹先另外解出來（不在本 repo 裡改）：在 repo 根 `git archive 5ccf44d2 | tar -x -C <空目錄>`。
  python -X utf8 goal_reminder_replay.py --old-tree <那個目錄> [--new-tree <repo 根>] [--runs 2026-10-23-CCon-R1,…]
      [--ruler <first_turn_breakdown.py>] [--keep] [--pieces]
  --pieces 印每段的重播文字（稽核用）；--keep 留下暫存資料根（預設跑完刪）。完整參數以 --help 為準。
  尾行 GOAL_REMINDER_REPLAY DONE runs=… src_before=<萬> hints_before=<萬> hints_after=<萬> saved=<萬> saved_r1=<萬> saved_r2=<萬>
      blocks_before=… blocks_after=… secs_saved=0 drift_max=<%>
"""
import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RES = Path.home() / ".claude" / "workflow" / "inbox" / "wave2-kit" / "results"
RULER = (Path.home() / ".claude" / "_AIDocs" / "DevHistory" / "v6.0-寫程式碼的進化-2026-10" / "v6.0的代價-第一回合分布-實測"
         / "first_turn_breakdown.py")
NEW_TREE = Path(__file__).resolve().parents[4]
DEF_RUNS = "2026-10-23-CCon-R1,2026-10-23-CCon-R2"
HOOK_TURN = 0          # 第一個使用者回合裡 hook 看到的 turn_seq（收尾才加一）
BLOCK_SPLIT = re.compile(r"\n(?=\S{0,4}\[[A-Za-z])")
BRACKETS = re.compile(r"【([^】]+)】")
CHANGED = ("goal_block", "goal_view", "scope", "claim", "correction", "prompt")
KIND_NAME = {"goal_block": "導讀卡附樹", "goal_view": "目標視角重看", "scope": "讀入範圍", "claim": "外部主張", "correction": "糾正",
             "prompt": "每則訊息", "write": "need_goal 寫入的回覆（送全樹，不改）", "code_hint": "要改碼先立樹（不改）"}

# 子行程：在暫存資料根裡用某一份程式碼樹重播事件，印每個事件產生的文字（JSON）
CHILD = r"""
import json, sys
tree, payload = sys.argv[1], json.loads(open(sys.argv[2], encoding="utf-8").read())
sys.path[:0] = [tree + "/hooks", tree + "/lib"]
import wg_need_goal as ng, wg_need_goal_points as ngp, wg_overview as wo
out = {}
for run in payload:
    sid, root, turn = run["sid"], run["root"], run["turn"]
    ng.on_prompt(sid, run["prompt"], 1, {}, cwd=root)
    ng.apply_op(sid, 1, run["set"], root)
    cfg = ng.cfg_of({})
    texts = []
    for ev in run["events"]:
        kind = ev["kind"]
        if kind == "goal_block":
            texts.append(wo._goal_block(sid, wo._cfg({}), root + "|" + ev["part"], turn))
        elif kind == "goal_view":
            texts.append(ngp.goal_view_text(sid, ev["part"], part_key=root + "|" + ev["part"]))
        elif kind == "scope":
            for p in ev["prev"] + ev["parts"]:
                ngp.scope_growth_line(sid, root + "|" + p, cfg)
            for d in ev["dirs"]:
                ngp.scope_dir_line(sid, root + "|" + d, cfg)
            lines = ngp.batch_lines(sid, {"turn_seq": turn, "need_goal_batch": True}, [], cfg)
            texts.append(lines[0] if lines else "")
        else:
            raise SystemExit(f"重播不支援這種提示：{kind}")
    out[run["name"]] = texts
print(json.dumps(out, ensure_ascii=False))
"""


def load_ruler(path):
    spec = importlib.util.spec_from_file_location("first_turn_breakdown", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def first_turn_blocks(ftb, name, n):
    """第一回合每段 hook 注入（跟量尺同一套切法），帶它所在 attachment 的下一段（導讀卡附樹要從那段認部位）。"""
    seg = RES / name / "B-1"
    rows = [json.loads(line) for line in sorted((seg / "transcript").glob("*.jsonl"))[0].open(encoding="utf-8")]
    out, k, seen = [], 0, set()
    for r in rows:
        if r.get("type") == "assistant":
            mid = r["message"]["id"]
            if mid not in seen:
                seen.add(mid)
                k += 1
            continue
        if r.get("type") != "attachment" or r["attachment"]["type"] != "hook_additional_context" or not r.get("rendered"):
            continue
        for text in r["attachment"].get("content") or []:
            blks = BLOCK_SPLIT.split(text)
            for i, blk in enumerate(blks):
                out.append({"k": k, "text": blk, "next": blks[i + 1] if i + 1 < len(blks) else ""})
    return [b for b in out if b["k"] < n]


def kind_of(text):
    t = text
    if not t.startswith("[NeedGoal]"):
        return None
    if t.startswith("[NeedGoal] 目前的需求目標（") or t.startswith("[NeedGoal] 改這個部位的程式檔時"):
        return "goal_block"
    if t.startswith("[NeedGoal] 目標改了，用目標視角重看"):
        return "goal_view"
    if t.startswith("[NeedGoal] 讀入範圍變大"):
        return "scope"
    if t.startswith("[NeedGoal] 收到外部主張"):
        return "claim"
    if t.startswith("[NeedGoal] 使用者糾正了"):
        return "correction"
    if t.startswith("[NeedGoal] 目前需求目標 "):
        return "prompt"
    if t.startswith("[NeedGoal] 這則看起來要改程式"):
        return "code_hint"
    if re.match(r"\[NeedGoal\] (set|add|update|reconcile|read) (收下|拒收)|\[NeedGoal\] 樹根這幾句原話裡沒有|\[NeedGoal\] 目標樹 T", t):
        return "write"
    raise SystemExit(f"認不出這段 NeedGoal 注入（重播不支援，先補 kind_of）：{t[:80]}")


def event_of(kind, blk):
    """從 transcript 那段的字面還原事件參數：部位名、讀入範圍的先前部位／新部位／頂層目錄（標籤去掉專案根名）。"""
    strip = lambda s: s.split("/", 1)[1] if "/" in s else s       # noqa: E731  「qb2-sales/測試」→「測試」
    if kind == "goal_block":
        m = re.search(r"第一次碰到【([^】]+)】部位", blk["next"])
        if not m:
            raise SystemExit(f"導讀卡附樹那段後面找不到部位名：{blk['next'][:80]}")
        return {"kind": kind, "part": m.group(1)}
    if kind == "goal_view":
        return {"kind": kind, "part": BRACKETS.search(blk["text"]).group(1)}
    if kind == "scope":
        t = blk["text"]
        parts = [strip(p) for p in BRACKETS.findall(t.split("擴到部位", 1)[1].split("；")[0].split("。")[0])] if "擴到部位" in t else []
        m = re.search(r"跨了 \d+ 個頂層目錄（([^）]+)）", t)
        dirs = [strip(d) for d in m.group(1).split("、")] if m else []
        pm = re.search(r"先前在((?:【[^】]+】)+)的判斷", t)
        prev = [strip(p) for p in BRACKETS.findall(pm.group(1))] if pm else []
        if len(prev) > 1:
            raise SystemExit(f"讀入範圍事件的先前部位超過一個，重播不支援：{prev}")
        return {"kind": kind, "parts": parts, "dirs": dirs, "prev": prev}
    raise SystemExit(f"重播不支援這種提示：{kind}")


def run_tree(tree, payload, keep):
    data = Path(tempfile.mkdtemp(prefix="goal-reminder-replay-"))
    (data / "workflow").mkdir()
    pf = data / "payload.json"
    pf.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    env = {**os.environ, "WG_CLAUDE_DIR": str(data), "WG_V6": "1"}
    try:
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", CHILD, str(tree), str(pf)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=env, cwd=str(data), timeout=300)
        if r.returncode != 0:
            raise SystemExit(f"{tree} 重播失敗：\n{r.stderr[-3000:]}")
        return json.loads(r.stdout.strip().splitlines()[-1])
    finally:
        if keep:
            print(f"（暫存資料根留著：{data}）")
        else:
            shutil.rmtree(data, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--old-tree", required=True, help="舊碼樹（git archive 解出的目錄）")
    ap.add_argument("--new-tree", default=str(NEW_TREE), help="新碼樹（預設本 repo 根）")
    ap.add_argument("--runs", default=DEF_RUNS)
    ap.add_argument("--ruler", default=str(RULER), help="共用量尺 first_turn_breakdown.py")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--pieces", action="store_true")
    a = ap.parse_args()
    ftb = load_ruler(a.ruler)
    names = [x for x in a.runs.split(",") if x]
    off = ftb.DEF_OFF.split(",")
    raw = [ftb.load_segment(n) for n in off + names + ftb.DEF_CROSS.split(",")]
    coef, _n, _rel = ftb.fit_estimator(raw)
    schema, _ = ftb.fit_schema(raw, coef)
    off_t0 = sum(r["calls"][0]["T"] for r in raw[:len(off)]) / len(off)
    est = lambda s: max(coef[0] * sum(1 for c in s if ftb.is_cjk(c)) + coef[1] * sum(1 for c in s if not ftb.is_cjk(c)) + coef[2], 1.0)  # noqa: E731

    runs, payload = {}, []
    for nm in names:
        run = ftb.analyze(nm, coef, schema, off_t0)
        n = run["turn_n"]
        pieces = [p for k in range(n) for p in run["calls"][k]["pieces"] if p.kind == "inject" and "NeedGoal" in p.src]
        blks = [b for b in first_turn_blocks(ftb, nm, n) if b["text"].startswith("[NeedGoal]")]
        if len(pieces) != len(blks) or any(p.k != b["k"] or (p.cjk, p.oth) != ftb.feats(b["text"]) for p, b in zip(pieces, blks)):
            raise SystemExit(f"{nm}：量尺的 NeedGoal 段跟 transcript 對不齊（{len(pieces)} 對 {len(blks)}）")
        rows = [json.loads(line) for line in sorted((RES / nm / "B-1" / "transcript").glob("*.jsonl"))[0].open(encoding="utf-8")]
        first = next(r for r in rows if r.get("type") == "user")
        set_in = next(b["input"] for r in rows if r.get("type") == "assistant" for b in r["message"]["content"]
                      if b.get("type") == "tool_use" and b["name"].endswith("need_goal") and (b.get("input") or {}).get("action") == "set")
        items = []
        for p, b in zip(pieces, blks):
            kind = kind_of(b["text"])
            items.append({"k": p.k, "tok": p.tok, "reread": n - p.k, "kind": kind, "text": b["text"],
                          "event": event_of(kind, b) if kind in CHANGED else None})
        blocks = sum(1 for k in range(n) for p in run["calls"][k]["pieces"] if p.kind in ("deny", "block") and "NeedGoal" in p.src)
        runs[nm] = {"n": n, "items": items, "blocks": blocks}
        payload.append({"name": nm, "sid": f"replay-{nm[-2:]}", "root": first.get("cwd") or "C:\\w4\\qb2-sales", "turn": HOOK_TURN,
                        "prompt": first["message"]["content"], "set": set_in,
                        "events": [it["event"] for it in items if it["event"]]})

    old = run_tree(Path(a.old_tree), payload, a.keep)
    new = run_tree(Path(a.new_tree), payload, a.keep)
    tot = {"src_before": 0.0, "hints_before": 0.0, "hints_after": 0.0}
    saved_by, drift_max = {}, 0.0
    for nm in names:
        r = runs[nm]
        evs = iter(zip(old[nm], new[nm]))
        print(f"\n## {nm}（第一回合 {r['n']} 次呼叫；token＝實測分攤，花費＝token×之後被重讀次數）")
        print("| 呼叫 # | 種類 | 字數（帳上／舊碼重播／新碼） | token（帳上→砍後） | 重讀次數 | 花費（砍前→砍後） |")
        print("|---|---|---|---|---|---|")
        saved = 0.0
        for it in r["items"]:
            before = it["tok"] * it["reread"]
            tot["src_before"] += before if it["kind"] != "code_hint" else 0.0
            if it["event"] is None:
                print(f"| {it['k']} | {KIND_NAME[it['kind']]} | {len(it['text'])} | {it['tok']:,.0f} | {it['reread']} | {before:,.0f}（不改） |")
                continue
            o, w = next(evs)
            drift = abs(len(o) - len(it["text"])) / max(len(it["text"]), 1)
            drift_max = max(drift_max, drift)
            tok_new = it["tok"] * est(w) / est(o)
            after = tok_new * it["reread"]
            tot["hints_before"] += before
            tot["hints_after"] += after
            saved += before - after
            print(f"| {it['k']} | {KIND_NAME[it['kind']]} | {len(it['text'])}／{len(o)}／{len(w)} | {it['tok']:,.0f}→{tok_new:,.0f} | "
                  f"{it['reread']} | {before:,.0f}→{after:,.0f} |")
            if a.pieces:
                print(f"\n舊碼重播：\n{o}\n\n新碼：\n{w}\n")
        saved_by[nm] = saved
        print(f"\n{nm}：這刀改的提示砍前 {sum(i['tok'] * i['reread'] for i in r['items'] if i['event']):,.0f} → 省 {saved:,.0f} token；"
              f"擋 {r['blocks']} 筆（NeedGoal 擋訊息）")
    k = len(names)
    blocks = sum(r["blocks"] for r in runs.values())
    print(f"\n平均每跑：來源合計（提示＋寫入回覆，不含先立樹一行）{tot['src_before'] / k:,.0f}；這刀改的提示 {tot['hints_before'] / k:,.0f}"
          f" → {tot['hints_after'] / k:,.0f}，省 {(tot['hints_before'] - tot['hints_after']) / k:,.0f}；舊碼重播字數對帳最大差 {drift_max:.1%}")
    w = lambda x: f"{x / 1e4:.2f}"  # noqa: E731
    print(f"GOAL_REMINDER_REPLAY DONE runs={k} src_before={w(tot['src_before'] / k)} hints_before={w(tot['hints_before'] / k)} "
          f"hints_after={w(tot['hints_after'] / k)} saved={w((tot['hints_before'] - tot['hints_after']) / k)} "
          + " ".join(f"saved_{nm[-2:].lower()}={w(v)}" for nm, v in saved_by.items())
          + f" blocks_before={blocks} blocks_after={blocks} secs_saved=0 drift_max={drift_max * 100:.1f}")


if __name__ == "__main__":
    main()

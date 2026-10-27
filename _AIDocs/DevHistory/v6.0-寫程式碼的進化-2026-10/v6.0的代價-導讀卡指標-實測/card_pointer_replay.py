r"""card_pointer_replay.py — 導讀卡指標制（overview_hub.card_injection）省多少：事件帳重播，不跑模型。

做什麼
  A 組（004 題）：讀 004 五跑（CCon-R1／R2／1／2／3）第一回合的 OverviewHub 事件帳（B-1/workflow/_overview-hub.log，
    限 B-1/turns/B-1-t1.json _meta 起訖內），照原順序交給 --tree 那棵樹的程式重播：inject 事件 → 用 Read 讀同一個檔（on_read，
    意圖照事件帳記的），edit 事件 → on_edit 同一個檔；部位表用受測專案 --proj 的。
    1. 先證重播對得上：重播的 full 注入對 transcript 裡的原注入（additionalContext 的 OverviewHub 那段）逐字相同；
       目標視角重送（要目標樹，事件帳沒有可重播的輸入）用 _goal_view 同一支組字、同一組參數重組再比。
    2. 再比 pointer 對 full：每段注入逐字相同否、每次改檔擋不擋與擋訊息相同否、指標制多要 Read 的卡幾張。
  B 組（補充，不是 004 題）：--tree 根層部位表上有卡的 code 部位，算 feature 意圖（004 第一回合的意圖）整張注入、指標兩行、
    改那塊時 Read 卡回來的內容（cat -n 格式）各多少 token；重讀次數用 R1 的兩個位置（注入後被 20 次、13 次呼叫重讀），
    改了的部位假設讀卡跟別的讀檔同一則送（不多一次呼叫）。
  token 估算＝first_turn_breakdown.py 的係數：1.321×中日韓字＋0.534×其他字−8.8（每段），口徑同 004（輸入＝input＋cache_creation＋cache_read）。
  唯讀輸入：--results（004 帳）、--proj（受測專案）、--tree 的程式、部位表與卡。寫入只在 --data（repo 外的空目錄：資料根、log、假 transcript）。

怎麼跑
  python -X utf8 card_pointer_replay.py --tree <受測的程式樹> --results <workflow/inbox/wave2-kit/results> \
      --proj C:\w4\qb2-sales --data <repo 外的空目錄>
  參數以 --help 為準。輸出 markdown 兩張表到 stdout（本資料夾的 card_pointer_replay-輸出.md 是 2026-10-27 那次）。
  尾行 CARD_POINTER DONE a_runs=… a_orig=… a_orig_same=… a_inject=… a_text_same=… a_edits=… a_deny_same=… a_card_body=…
       a_card_reads_needed=… b_parts=… b_full_tok=… b_ptr_tok=… b_read_tok=… b_skip_saved20=… b_edit_delta20=… a_identical=yes|no
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

RUNS = ("2026-10-23-CCon-R1", "2026-10-23-CCon-R2", "2026-10-23-CCon-1", "2026-10-23-CCon-2", "2026-10-23-CCon-3")
COEF = (1.321, 0.534, -8.8)
REREAD = (20, 13)          # R1：銷售報表注入後被第 2～21 次呼叫重讀、測試注入後被第 9～21 次重讀


def tok(text: str) -> float:
    cjk = sum(1 for ch in text if ord(ch) >= 0x2E80)
    return max(COEF[0] * cjk + COEF[1] * (len(text) - cjk) + COEF[2], 0.0)


def read_view(path: Path) -> str:
    """Read 工具回給模型的樣子：每行「行號<tab>內容」。"""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(f"{i:>6}\t{l}" for i, l in enumerate(lines, 1))


def first_turn_events(run: Path):
    meta = json.loads((run / "B-1" / "turns" / "B-1-t1.json").read_text(encoding="utf-8"))["_meta"]
    t0, t1 = (datetime.fromisoformat(meta[k]) for k in ("started", "ended"))
    out = []
    for line in (run / "B-1" / "workflow" / "_overview-hub.log").read_text(encoding="utf-8").splitlines():
        e = json.loads(line)
        if e["event"] in ("inject", "edit", "edit_before_inject") and t0 <= datetime.fromisoformat(e["ts"].replace(" ", "T")) <= t1:
            out.append(e)
    return out


_MARK = "[Guardian:OverviewHub] 本 session 第一次碰到"


def transcript_injections(run: Path):
    """transcript 裡 PostToolUse／UserPromptSubmit 的 additionalContext 中 OverviewHub 注入那段（從標記到結尾），照出現順序、去重。"""
    out = []
    for f in sorted((run / "B-1" / "transcript").glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if _MARK not in line:
                continue
            stack = [json.loads(line)]
            while stack:
                o = stack.pop()
                if isinstance(o, dict):
                    stack.extend(o.values())
                elif isinstance(o, list):
                    stack.extend(o)
                elif isinstance(o, str) and o.startswith('{"hookSpecificOutput"'):
                    ctx = json.loads(o)["hookSpecificOutput"].get("additionalContext") or ""
                    if _MARK in ctx:
                        seg = ctx[ctx.index(_MARK):]
                        if seg not in out:
                            out.append(seg)
    return out


def replay(wo, events, proj: Path, mode: str, tp: str):
    cfg = {"overview_hub": {"card_injection": mode}}
    state: dict = {"turn_seq": 1}
    got = []
    for e in events:
        if e.get("intent"):
            state["turn_intent"] = e["intent"]          # 事件帳記了當時的意圖（004 第一回合＝feature），照它選視角與先問
        if e["event"] == "inject":
            got.append(("read", wo.on_read(state, "replay", "Read", {"file_path": e["path"]}, str(proj), tp, cfg)))
        else:
            warn, deny, _ = wo.on_edit(state, "replay", e["path"], tp, cfg)
            got.append(("edit", deny))
    unread = sum(len(wo._unread_cards(state, r)) for k, r in (state.get("overview_hub") or {}).items() if "(unmapped)" not in k)
    return got, unread


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tree", required=True, help="受測的程式樹（hooks／lib 從這裡載入；B 組的部位表與卡也用它）")
    ap.add_argument("--results", required=True, help="004 帳的 results 資料夾（唯讀）")
    ap.add_argument("--proj", required=True, help="受測專案根（唯讀；A 組的部位表）")
    ap.add_argument("--data", required=True, help="repo 外的空目錄（資料根、log、假 transcript 寫這裡）")
    a = ap.parse_args()
    tree, data = Path(a.tree).resolve(), Path(a.data).resolve()
    (data / "workflow").mkdir(parents=True, exist_ok=True)
    os.environ["WG_CLAUDE_DIR"] = str(data)
    os.environ["WG_V6"] = "1"
    sys.path[:0] = [str(tree / "hooks"), str(tree / "lib")]
    import overview_hub as oh
    import wg_overview as wo
    wo.LOG_PATH = data / "workflow" / "_overview-hub.log"
    tp = data / "t.jsonl"
    tp.write_text(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "x"}]}}) + "\n", encoding="utf-8")

    print("## A 組：004 五跑第一回合 OverviewHub 事件重播（pointer 對 full）\n")
    print("| 跑 | 事件 | 重播 full 對 transcript 原注入（逐字相同） | 注入 pointer 對 full（逐字相同） | 改檔（擋不擋、擋訊息相同） | 注入裡有卡正文 | 指標制多要讀的卡 |")
    print("|---|---|---|---|---|---|---|")
    tot = {"events": 0, "text_same": 0, "inject": 0, "deny_same": 0, "edits": 0, "card_reads": 0, "card_body": 0,
           "orig_same": 0, "orig": 0}
    for name in RUNS:
        ev = first_turn_events(Path(a.results) / name)
        p, unread_p = replay(wo, ev, Path(a.proj), "pointer", str(tp))
        f, _ = replay(wo, ev, Path(a.proj), "full", str(tp))
        orig = transcript_injections(Path(a.results) / name)
        got_full = [y[1] for y in f if y[0] == "read"]
        inj = [(x, y) for x, y in zip(p, f) if x[0] == "read"]
        for o in orig:
            if o in got_full or "視角：" + wo.GOAL_VIEW_LENS not in o:
                continue
            # 目標視角重送（事件帳沒有可重播的輸入：要目標樹）：用 _goal_view 同一支組字、同一組參數，兩種送法各組一次
            hit = o[o.index("（") + 1:o.index("）")]
            row = oh.match_row(hit, Path(a.proj), oh.parse_map((Path(a.proj) / ".claude" / "overview-map.md").read_text(encoding="utf-8")))
            gcfg = wo._cfg({}, Path(a.proj))
            cps, _miss = wo._resolve_row_cards(Path(a.proj), row, gcfg)
            gargs = (row, cps, hit, int(gcfg["max_card_chars"]), wo._locate_template(gcfg), None, [], wo.GOAL_VIEW_LENS, "")
            gfull = oh.build_injection_ex(*gargs)[0]
            got_full.append(gfull)
            inj.append((("read", oh.build_injection_ex(*gargs, pointer=True)[0]), ("read", gfull)))
        orig_same = sum(1 for o in orig if o in got_full)
        tot.update(orig=tot["orig"] + len(orig), orig_same=tot["orig_same"] + orig_same)
        eds = [(x, y) for x, y in zip(p, f) if x[0] == "edit"]
        same_t = sum(1 for x, y in inj if x[1] == y[1])
        same_d = sum(1 for x, y in eds if x[1] == y[1])
        body = sum(1 for _, y in inj if y[1] and "---- 導讀卡" in y[1])
        tot.update(events=tot["events"] + len(ev), inject=tot["inject"] + len(inj), text_same=tot["text_same"] + same_t,
                   edits=tot["edits"] + len(eds), deny_same=tot["deny_same"] + same_d, card_reads=tot["card_reads"] + unread_p,
                   card_body=tot["card_body"] + body)
        print(f"| {name} | {len(ev)} | {orig_same}/{len(orig)} | {same_t}/{len(inj)} | {same_d}/{len(eds)} | {body} | {unread_p} |")

    print("\n## B 組（補充，不是 004 題）：根層有卡的 code 部位，feature 意圖\n")
    print("| 部位 | 卡數 | 整張注入 tok | 指標注入 tok | Read 卡回來 tok | 沒改這塊省（×20／×13） | 改了這塊省（×20／×13） |")
    print("|---|---|---|---|---|---|---|")
    root = tree
    wo.CLAUDE_DIR = tree                 # 只為查卡：根層 worktree 的卡在 <資料根>/memory（card_mem_dir），這裡唯讀
    cfg = wo._cfg({}, root)
    gw = cfg["goal_weights"]["feature"]
    rows = [r for r in oh.parse_map((root / ".claude" / "overview-map.md").read_text(encoding="utf-8"))
            if (r.get("kind") or "code") != "knowledge"]
    seen, b = set(), []
    for r in rows:
        cps = wo._cards_for(root, r, cfg)
        key = tuple(str(c) for c in cps)
        if not cps or key in seen:
            continue
        seen.add(key)
        args = (r, cps, str(root / "x.py"), int(cfg["max_card_chars"]), wo._locate_template(cfg), None,
                list(gw.get("slices") or []), str(gw.get("lens") or ""), str(gw.get("ask_first") or ""))
        full = tok(oh.build_injection_ex(*args, extra=str(gw.get("extra") or ""))[0])
        ptr = tok(oh.build_injection_ex(*args, extra=str(gw.get("extra") or ""), pointer=True)[0])
        rd = sum(tok(read_view(c)) for c in cps)
        skip = [(full - ptr) * k for k in REREAD]
        edit = [(full - ptr) * k - rd * (k - 1) for k in REREAD]
        b.append((full, ptr, rd, skip, edit))
        print(f"| {r['part_short']} | {len(cps)} | {full:,.0f} | {ptr:,.0f} | {rd:,.0f} | "
              f"{skip[0]:,.0f}／{skip[1]:,.0f} | {edit[0]:,.0f}／{edit[1]:,.0f} |")
    n = len(b)
    avg = [sum(x[i] for x in b) / n for i in range(3)]
    s20 = sum(x[3][0] for x in b) / n
    e20 = sum(x[4][0] for x in b) / n
    print(f"\n平均：整張 {avg[0]:,.0f}、指標 {avg[1]:,.0f}、Read 卡 {avg[2]:,.0f} tok；沒改的部位每個省 {s20:,.0f}（×20），"
          f"改了的部位每個省 {e20:,.0f}（×20；負＝多花，假設讀卡跟別的讀檔同一則送）")
    ok = tot["text_same"] == tot["inject"] and tot["deny_same"] == tot["edits"] and tot["orig_same"] == tot["orig"]
    print(f"\nCARD_POINTER DONE a_runs={len(RUNS)} a_events={tot['events']} a_orig={tot['orig']} a_orig_same={tot['orig_same']} "
          f"a_inject={tot['inject']} a_text_same={tot['text_same']} "
          f"a_edits={tot['edits']} a_deny_same={tot['deny_same']} a_card_body={tot['card_body']} a_card_reads_needed={tot['card_reads']} "
          f"b_parts={n} b_full_tok={avg[0]:.0f} b_ptr_tok={avg[1]:.0f} b_read_tok={avg[2]:.0f} b_skip_saved20={s20:.0f} "
          f"b_edit_delta20={e20:.0f} a_identical={'yes' if ok else 'no'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

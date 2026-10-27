"""deny_slim_replay.py — 擋訊息與判準卡瘦身、讀到資料檔就先提示：拿 004 的 transcript 帳重播，量第一回合砍前→砍後。

做什麼
  沿用共用量尺 first_turn_breakdown.py（下稱 ftb）的拆段與估算式（同一組 8 跑迴歸、同一口徑：輸入＝input＋cache_creation＋cache_read），
  每跑第一回合：
  1. 文字（實測總量＋推論分段）：每一段 PreToolUse 擋訊息本文、附的判準卡、其他帶「判準卡（」的段（MCP 回覆、Stop 注入），
     照新規則重組——DataFileAsk 擋訊息換成 slim_deny（DENY_TEXT_SLIM）；判準卡照 CARD_FULL_ONCE_PER_SESSION（session 內送過的卡
     併成一行「判準卡：<卡名>、…」，拿過卡的切入點不再收新卡）。新段 token＝原段實測分到的 token × 新估算／舊估算；
     省下的×之後每次呼叫（含這次）＝少讀的 token。另列只算照常呼叫的部分（＝ftb 的 b 類口徑）。
  2. 讀檔提示（反事實，推論）：照時間順序把每次 Read／Bash／Grep 交給工作樹的 wg_data_file.read_hint（真的程式，假 state：
     使用者原話取 transcript 第一則），算出提示出在哪一次呼叫、點名哪些檔、多少字；假設 AI 在改檔前一則的文字照格式寫宣告
     （兩跑 AI 在那則都已寫了一句改 README 的意圖，只差格式），被擋那次 Edit 直接過：
     去掉「補宣告」與「重送 Edit」兩次呼叫，之後每次呼叫少讀 D＝T(重送 Edit)−T(被擋 Edit)，加回提示與宣告句被之後重讀的量。
  秒：被省掉的兩次呼叫照 ftb 的 model_s（送出到回完）與 slot_s（含工具與 hook）。
  文字那段以同目錄 replay_fn.py 為準（同一批輸入交給分支函式組裝、當時版逐字對上 transcript）；本檔的文字重組是照規則模擬，兩者差約 1%，本檔主要用來算讀檔提示的反事實。
怎麼跑
  python -X utf8 deny_slim_replay.py [--runs 2026-10-23-CCon-R1,2026-10-23-CCon-R2] [--wt <工作樹>] [--show]
  尾行 DENY_SLIM_REPLAY DONE r1_text=… r2_text=… r1_df=… r2_df=… avg_total=… blocks_before=… blocks_after=… secs=…（token 以萬為單位）
"""
import argparse
import importlib.util
import json
import os
import re
import sys
import tempfile
from pathlib import Path

FTB = (Path.home() / ".claude" / "_AIDocs" / "DevHistory" / "v6.0-寫程式碼的進化-2026-10" / "v6.0的代價-第一回合分布-實測"
       / "first_turn_breakdown.py")
CARD_RE = re.compile(r"判準卡（([^）]*)）：([^\n]+)")
OLD_REPEAT = "（這個話題前面已送過全文，照那張判）"


def load_ftb():
    spec = importlib.util.spec_from_file_location("ftb", FTB)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)

    class P(m.Piece):                      # 讓段記住原文（ftb 的 Piece 只記字數）
        __slots__ = ("text",)

        def __init__(self, k, kind, src, text="", **kw):
            super().__init__(k, kind, src, text, **kw)
            self.text = text
    m.Piece = P
    return m


def split_cards(text):
    """一段文字 → (卡之前的字, [(代號集, 卡名, 原塊文字, 舊指回行?)])；卡塊從「判準卡（」到下一個「\n\n判準卡（」或結尾。"""
    starts = [m.start() for m in CARD_RE.finditer(text)]
    if not starts:
        return text, []
    head, blocks = text[:starts[0]], []
    for i, s in enumerate(starts):
        blk = text[s:starts[i + 1]] if i + 1 < len(starts) else text[s:]
        m = CARD_RE.match(blk)
        name = m.group(2)
        old_rep = name.endswith(OLD_REPEAT)
        blocks.append((set(m.group(1).split("、")), name.replace(OLD_REPEAT, ""), blk.rstrip("\n"), old_rep))
    return head, blocks


def new_cards(blocks, seen, served):
    """CARD_FULL_ONCE_PER_SESSION 重組一段的卡：送過的→卡名一行；全部代號都拿過卡的新卡→不送；其餘照原塊。更新 seen／served。"""
    names, kept, got = [], [], set()
    for ents, name, blk, _ in blocks:
        if name in seen:
            names.append(name)
            got |= ents
        elif ents <= served:
            continue
        else:
            kept.append(blk)
            got |= ents
    seen |= {CARD_RE.match(b).group(2) for b in kept}
    served |= got
    parts = ([f"判準卡：{'、'.join(names)}"] if names else []) + kept
    return "\n\n".join(parts)


def slim_df_body(text, rr):
    """DataFileAsk 舊擋訊息本文 → slim_deny（DENY_TEXT_SLIM）；hook 錯誤前綴照留。"""
    prefix = text[:text.index("[Guardian:DataFileAsk]")]
    hits = [ln for ln in text.splitlines() if ln.startswith("✗ (df) ")]
    rels = re.findall(r"入口行範例：動資料檔｜(.+?)：", text)
    return prefix + f"[Guardian:DataFileAsk] 修法：{rr.data_file_fix(rels)}\n" + "\n".join(hits)


def est(ftb, coef, text):
    c, o = ftb.feats(text)
    return max(coef[0] * c + coef[1] * o + coef[2], 1.0)


def replay_text(ftb, run, coef, rr, show):
    """文字重組：回 (全部呼叫少讀, 照常呼叫少讀, 明細)。"""
    calls, n, cls = run["calls"], run["turn_n"], run["cls"]
    seen, served = set(), set()
    total = base_only = 0.0
    before = {"deny_all": 0.0, "deny_base": 0.0, "other_all": 0.0, "other_base": 0.0}   # 砍前：擋訊息（PreToolUse＋Stop）與其他帶判準卡的段原本被讀的總量
    rows = []
    for k in range(n):
        ps = calls[k]["pieces"]
        snap = (set(seen), set(served))      # 同一則 Stop 擋訊息 CC 會印兩份（使用者訊息＋system），兩份是同一次問
        for i, p in enumerate(ps):
            text = getattr(p, "text", "") or ""
            if p.kind == "deny" and p.src.endswith("擋訊息附的判準卡"):
                text = "判準卡（" + text
            readers = range(k, n)
            if p.kind in ("deny", "block") or "判準卡（" in text:
                key = "deny" if p.kind in ("deny", "block") else "other"
                before[key + "_all"] += p.tok * len(readers)
                before[key + "_base"] += p.tok * sum(1 for j in readers if cls[j] == "base")
            if "判準卡（" not in text and not (p.kind == "deny" and "DataFileAsk｜擋訊息本文" in p.src):
                continue
            new = text
            if p.kind == "deny" and "DataFileAsk｜擋訊息本文" in p.src:
                new = slim_df_body(text, rr)
            elif "判準卡（" in text:
                head, blocks = split_cards(text)
                if p.kind == "block":
                    s2, v2 = set(snap[0]), set(snap[1])
                    cards = new_cards(blocks, s2, v2)
                    seen |= s2
                    served |= v2
                else:
                    cards = new_cards(blocks, seen, served)
                new = head + cards if head.strip() else cards
            if new == text or p.tok <= 0:
                continue
            new_tok = p.tok * est(ftb, coef, new) / max(p.est, 1.0)
            d = p.tok - new_tok
            total += d * len(readers)
            base_only += d * sum(1 for j in readers if cls[j] == "base")
            rows.append((k, p.src, round(p.tok), round(new_tok), len(readers)))
            if show:
                print(f"--- call {k} {p.src}：{p.tok:.0f}→{new_tok:.0f} tok，被讀 {len(readers)} 次\n舊：{text[:300]}\n新：{new[:300]}\n")
    return total, base_only, rows, before


def replay_hint(ftb, run, coef, wt, show):
    """讀檔提示反事實：回 dict(移除的呼叫、每次少讀 D、提示與宣告句加回、反事實第一回合合計、秒)。"""
    sys.path[:0] = [str(Path(wt) / "hooks"), str(Path(wt) / "lib")]
    import wg_data_file as df
    calls, n = run["calls"], run["turn_n"]
    denied = [k for k in range(n) if run["cls"][k] == "a" and run["gate"][k] == "Guardian:DataFileAsk"]
    if not denied:
        return None
    kd = denied[0]                         # 被擋的 Edit；kd+1 補宣告；kd+2 重送 Edit
    first_user = next(r for r in calls[0]["before"] if r.get("type") == "user")["message"]["content"]
    first_user = first_user if isinstance(first_user, str) else " ".join(b.get("text", "") for b in first_user if isinstance(b, dict))
    state = {"session": {"id": "replay"}, "recent_user_prompts": [first_user], "turn_prompts": [first_user]}
    hints = []                             # (提示進 context 的呼叫, 文字)
    for k in range(kd):
        for b in calls[k]["blocks"]:
            if b.get("type") != "tool_use" or b["name"] not in ("Read", "Bash", "PowerShell", "Grep"):
                continue
            h = df.read_hint(state, b["name"], b.get("input") or {}, r"C:\w4\qb2-sales", 0, {})
            if h:
                hints.append((k + 1, h))
    D = calls[kd + 2]["T"] - calls[kd]["T"]
    decl = "動資料檔｜README.md：在「跑法」補上 by-product 的用法，讓使用者文件跟新子命令一致；只加說明文字，對程式輸出沒有影響"
    before = sum(calls[j]["T"] for j in range(n))
    after = sum(calls[j]["T"] for j in range(kd + 1)) + sum(calls[j]["T"] - D for j in range(kd + 3, n))
    n_after = kd + 1 + (n - kd - 3)        # 反事實第一回合的呼叫數
    add = 0.0
    for k, h in hints:                     # 提示從第 k 次起每次呼叫都讀（反事實時間線上 k ≤ kd，之後的呼叫數照少兩次算）
        add += est(ftb, coef, h) * (n_after - k)
    decl_tok = est(ftb, coef, decl)
    add += decl_tok * (n_after - (kd - 1) - 1)   # 宣告句寫在改檔前一則（kd−1）的輸出，從 kd 起被讀
    after += add
    secs = (calls[kd]["model_s"] + calls[kd + 1]["model_s"], calls[kd]["slot_s"] + calls[kd + 1]["slot_s"])
    if show:
        for k, h in hints:
            print(f"--- 提示進 context：call {k}（{est(ftb, coef, h):.0f} tok）：{h}")
    return {"kd": kd, "D": D, "removed_T": calls[kd + 1]["T"] + calls[kd + 2]["T"], "hints": hints, "add": add,
            "before": before, "after": after, "saved": before - after, "secs": secs, "decl_tok": decl_tok}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", default="2026-10-23-CCon-R1,2026-10-23-CCon-R2")
    ap.add_argument("--wt", default=r"C:\Users\holylight\.claude-wt\deny-text-slim")
    ap.add_argument("--show", action="store_true", help="印每段舊→新的文字與提示")
    a = ap.parse_args()
    os.environ["WG_CLAUDE_DIR"] = tempfile.mkdtemp(prefix="deny-slim-replay-")   # 留帳落暫存，不碰 live 資料根
    sys.path[:0] = [str(Path(a.wt) / "hooks"), str(Path(a.wt) / "lib")]
    import wg_release_rules as rr
    ftb = load_ftb()
    main_names = [x for x in a.runs.split(",") if x]
    all_names = ftb.DEF_OFF.split(",") + ftb.DEF_RUNS.split(",") + ftb.DEF_CROSS.split(",")
    raw = [ftb.load_segment(nm) for nm in all_names]
    coef, _, rel = ftb.fit_estimator(raw)
    schema_size, _ = ftb.fit_schema(raw, coef)
    off = all_names[:3]
    off_T0 = sum(r["calls"][0]["T"] for r in raw[:3]) / 3
    print(f"估算式（同 ftb）：{coef[0]:.3f}×中日韓字＋{coef[1]:.3f}×其他字＋{coef[2]:.1f}×段數，平均絕對誤差 {rel:.1%}")
    res = {}
    for nm in main_names:
        run = ftb.analyze(nm, coef, schema_size, off_T0)
        t_all, t_base, rows, bef = replay_text(ftb, run, coef, rr, a.show)
        h = replay_hint(ftb, run, coef, a.wt, a.show)
        deny_n = sum(1 for k in range(run["turn_n"]) for p in run["calls"][k]["pieces"] if p.kind == "deny" and "本文" in p.src)
        df_n = sum(1 for k in range(run["turn_n"]) for p in run["calls"][k]["pieces"]
                   if p.kind == "deny" and "DataFileAsk｜擋訊息本文" in p.src)
        res[nm] = (run, t_all, t_base, rows, h, deny_n, df_n)
        print(f"砍前（被之後每次呼叫重讀的總量）：擋訊息本文＋附卡（PreToolUse＋Stop 兩份）全部呼叫 {bef['deny_all']:,.0f}、只算照常 {bef['deny_base']:,.0f}；"
              f"其他帶判準卡的段（MCP 回覆、注入）全部呼叫 {bef['other_all']:,.0f}、只算照常 {bef['other_base']:,.0f}")
        print(f"\n## {nm}：第一回合 {run['turn_n']} 次呼叫、輸入 {run['total']:,}；PreToolUse 擋 {deny_n} 筆（DataFileAsk {df_n}）")
        print("| 呼叫 | 段 | 舊 tok | 新 tok | 被讀幾次 |")
        print("|---|---|---|---|---|")
        for k, src, o, nw, r in rows:
            print(f"| {k} | {src} | {o:,} | {nw:,} | {r} |")
        print(f"文字少讀：全部呼叫 {t_all:,.0f}；只算照常呼叫（ftb b 口徑）{t_base:,.0f}")
        if h:
            print(f"讀檔提示：被擋 Edit 在 call {h['kd']}；去掉 call {h['kd'] + 1}、{h['kd'] + 2}（輸入 {h['removed_T']:,}），之後每次少讀 D={h['D']:,}；"
                  f"提示 {len(h['hints'])} 則＋宣告句（{h['decl_tok']:.0f} tok）被重讀加回 {h['add']:,.0f}；"
                  f"第一回合 {h['before']:,} → {h['after']:,.0f}，省 {h['saved']:,.0f}；秒（模型／含工具與 hook）{h['secs'][0]:.1f}／{h['secs'][1]:.1f}")
    # 合計：讀檔提示生效時 DataFileAsk 擋訊息不存在，它的文字瘦身不重複算
    print("\n## 合計（砍後＝文字瘦身＋讀檔提示生效；讀檔提示沒生效時只算文字瘦身）")
    out = {}
    for nm, (run, t_all, t_base, rows, h, deny_n, df_n) in res.items():
        df_text = sum((o - nw) * r for k, src, o, nw, r in rows if "DataFileAsk｜擋訊息本文" in src)
        hint_case = (t_all - df_text) + (h["saved"] if h else 0.0)
        out[nm] = {"text": t_all, "text_base": t_base, "df": h["saved"] if h else 0.0, "total": hint_case,
                   "blocks_before": deny_n, "blocks_after": deny_n - df_n if h else deny_n,
                   "secs": h["secs"] if h else (0.0, 0.0), "before": run["total"]}
        print(f"- {nm[11:]}：第一回合 {run['total']:,} → 讀檔提示生效 {run['total'] - hint_case:,.0f}（省 {hint_case:,.0f}）；"
              f"只靠文字 {run['total'] - t_all:,.0f}（省 {t_all:,.0f}）；擋 {deny_n} → {out[nm]['blocks_after']}")
    avg = sum(v["total"] for v in out.values()) / len(out)
    secs = sum(v["secs"][0] for v in out.values()) / len(out)
    k1, k2 = (main_names + main_names)[:2]
    print(f"DENY_SLIM_REPLAY DONE r1_text={out[k1]['text'] / 1e4:.2f} r2_text={out[k2]['text'] / 1e4:.2f} "
          f"r1_df={out[k1]['df'] / 1e4:.2f} r2_df={out[k2]['df'] / 1e4:.2f} avg_total={avg / 1e4:.2f} "
          f"blocks_before={sum(v['blocks_before'] for v in out.values())} blocks_after={sum(v['blocks_after'] for v in out.values())} "
          f"secs={secs:.1f}")


if __name__ == "__main__":
    main()

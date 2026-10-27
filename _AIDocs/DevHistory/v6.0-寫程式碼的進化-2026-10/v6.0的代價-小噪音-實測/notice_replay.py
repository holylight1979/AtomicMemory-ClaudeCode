"""notice_replay.py — 事件帳重播：七種「跟手上事情無關的提示」在 transcript 裡實際送了幾段，套「v6 開時一個 session 只送一次」後剩幾段。

做什麼
  唯讀掃 transcript（*.jsonl），只看 hook_additional_context 附件（Claude Code 把 hook 的 additionalContext 落成這種列）。
  每段注入照 [標籤] 切塊，認七種：
    Parallel:Suggest、JIT:InternalPipeline → 每 session 只留第一段；
    Guardian:Oscillation、Guardian:覆轍 → 依清單項目，列過的 atom／信號從之後的段刪掉，整段沒剩項目就整段拿掉；
    Guardian:AIDocs Relevant project docs → 依文件，指過的文件從之後的段刪掉，整段沒剩文件就整段拿掉；
    Guardian:AIDocs 暫時性檔名提醒（PostToolUse）→ 依檔名，同一個檔只留第一段；
    Guardian:CoordWarn 同檔預警（「也改過此檔」）→ 依檔，同一個檔只留第一段；寫後偵測、git 收尾預警不動；
    Codex Companion: Handoff 自檢 → v6 開時不再觸發，整段拿掉。
  token 估算＝量尺 first_turn_breakdown.py 的係數：1.321×中日韓字＋0.534×其他字−8.8（每段）；
  重讀成本＝這段的 token × 它之後（到下一次 compact 或 session 結束）的模型呼叫次數（assistant 列依 message.id 合併），
  口徑同 004：輸入＝input＋cache_creation＋cache_read，每次呼叫整份 context 都算進輸入。
  第一回合：wave2-kit 的跑另依 B-1/turns/B-1-t1.json 的起訖只算第一回合。

怎麼跑
  python -X utf8 notice_replay.py [--live <projects 目錄>] [--since 2026-10-01] [--md <輸出.md>]
  尾行 NOTICE_REPLAY DONE k=v …（數字是尺不是判決）
"""
import argparse
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

RES = Path.home() / ".claude" / "workflow" / "inbox" / "wave2-kit" / "results"
A, B, C = 1.321, 0.534, -8.8
LOCAL_TZ = datetime.now().astimezone().tzinfo
BLOCK_START = re.compile(r"^\S{0,3}\s?\[[^\]\s][^\]]*\]")
KINDS = ["Parallel:Suggest", "JIT:InternalPipeline", "Guardian:Oscillation", "Guardian:覆轍",
         "AIDocs 相關文件", "AIDocs 暫時性檔名提醒", "CoordWarn 同檔預警", "Codex 接續單自檢"]
AIDOC_LINE = re.compile(r"→ Read `([^`]+)`")
COORD_FILE = re.compile(r"也改過此檔：(.+?)（最近")
ADVISORY_FILE = re.compile(r"\[Guardian:AIDocs\]\s*⚠\s*(\S+) 看起來是暫時性文件")


def tok(text):
    cjk = sum(1 for ch in text if ord(ch) >= 0x2E80)
    return max(A * cjk + B * (len(text) - cjk) + C, 1.0)


def local(ts):
    d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return d.astimezone(LOCAL_TZ).replace(tzinfo=None) if d.tzinfo else d


def blocks(text):
    out, cur = [], []
    for line in text.split("\n"):
        if BLOCK_START.match(line) and cur:
            out.append("\n".join(cur))
            cur = []
        cur.append(line)
    if cur:
        out.append("\n".join(cur))
    return out


def kind_of(blk):
    if "[Parallel:Suggest]" in blk:
        return "Parallel:Suggest"
    if "[JIT:InternalPipeline]" in blk:
        return "JIT:InternalPipeline"
    if "[Guardian:Oscillation]" in blk:
        return "Guardian:Oscillation"
    if "[Guardian:覆轍]" in blk:
        return "Guardian:覆轍"
    if "[Guardian:AIDocs] Relevant project docs" in blk:
        return "AIDocs 相關文件"
    if ADVISORY_FILE.search(blk):
        return "AIDocs 暫時性檔名提醒"
    if "[Guardian:CoordWarn]" in blk and "也改過此檔" in blk:
        return "CoordWarn 同檔預警"
    if "[Codex Companion: Handoff 自檢" in blk:
        return "Codex 接續單自檢"
    return None


def after_cut(kind, blk, seen):
    """新規則下這段還剩什麼（""＝整段不送）。seen：本 session 已送過的鍵。"""
    if kind == "Codex 接續單自檢":
        return ""
    if kind in ("Parallel:Suggest", "JIT:InternalPipeline"):
        if kind in seen:
            return ""
        seen.add(kind)
        return blk
    if kind in ("Guardian:Oscillation", "Guardian:覆轍"):
        head, sep, rest = blk.partition("：")
        items_part, dot, tail = rest.partition("。行動")
        items = [x.strip() for x in items_part.split(",") if x.strip()]
        new = [x for x in items if (kind, x) not in seen]
        seen.update((kind, x) for x in new)
        return f"{head}{sep}{', '.join(new)}{dot}{tail}" if new else ""
    if kind == "AIDocs 相關文件":
        lines = blk.split("\n")
        keep = [lines[0]]
        for ln in lines[1:]:
            m = AIDOC_LINE.search(ln)
            key = ("doc", m.group(1)) if m else None
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            keep.append(ln)
        return "\n".join(keep) if len(keep) > 1 else ""
    m = (COORD_FILE if kind == "CoordWarn 同檔預警" else ADVISORY_FILE).search(blk)
    key = (kind, m.group(1).strip().replace("\\", "/").casefold()) if m else (kind, blk)
    if key in seen:
        return ""
    seen.add(key)
    return blk


def replay(path, window=None):
    """回 {kind: [前段數, 前字數, 前 token, 前重讀 token, 後段數, 後字數, 後 token, 後重讀 token]}、模型呼叫數。"""
    rows = []
    for line in path.open(encoding="utf-8", errors="replace"):
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    if window:
        rows = [r for r in rows if r.get("timestamp") and window[0] <= local(r["timestamp"]) <= window[1]]
    # 每一列之後（到下一個 compact 邊界）還有幾次模型呼叫
    calls_after = [0] * (len(rows) + 1)
    seen_ids = set()
    n = 0
    for i in range(len(rows) - 1, -1, -1):
        r = rows[i]
        if r.get("type") == "system" and r.get("subtype") == "compact_boundary":
            n, seen_ids = 0, set()
        if r.get("type") == "assistant":
            mid = (r.get("message") or {}).get("id")
            if mid not in seen_ids:
                seen_ids.add(mid)
                n += 1
        calls_after[i] = n
    total_calls = len({(r.get("message") or {}).get("id") for r in rows if r.get("type") == "assistant"})
    acc = defaultdict(lambda: [0.0] * 8)
    seen = set()
    for i, r in enumerate(rows):
        a = r.get("attachment") or {}
        if a.get("type") != "hook_additional_context":
            continue
        reread = calls_after[i + 1] if i + 1 < len(rows) else 0
        for text in a.get("content") or []:
            for blk in blocks(text):
                kind = kind_of(blk)
                if not kind:
                    continue
                left = after_cut(kind, blk, seen)
                v = acc[kind]
                t0 = tok(blk)
                v[0] += 1; v[1] += len(blk); v[2] += t0; v[3] += t0 * reread
                if left:
                    t1 = tok(left)
                    v[4] += 1; v[5] += len(left); v[6] += t1; v[7] += t1 * reread
    return acc, total_calls


def first_turn_window(run):
    tj = json.loads((RES / run / "B-1" / "turns" / "B-1-t1.json").read_text(encoding="utf-8"))["_meta"]
    return local(tj["started"]), local(tj["ended"])


def add(dst, src):
    for k, v in src.items():
        for j, x in enumerate(v):
            dst[k][j] += x


def table(title, acc, sessions, lines):
    lines.append(f"\n## {title}（{sessions} 個 session）")
    lines.append("| 來源 | 砍前 段／字／token／含重讀 | 砍後 段／字／token／含重讀 | 省 段／含重讀 token |")
    lines.append("|---|---|---|---|")
    tot = [0.0] * 8
    for k in KINDS:
        v = acc.get(k, [0.0] * 8)
        for j in range(8):
            tot[j] += v[j]
        lines.append(f"| {k} | {v[0]:.0f}／{v[1]:,.0f}／{v[2]:,.0f}／{v[3]:,.0f} | {v[4]:.0f}／{v[5]:,.0f}／{v[6]:,.0f}／{v[7]:,.0f} | "
                     f"{v[0] - v[4]:.0f}／{v[3] - v[7]:,.0f} |")
    lines.append(f"| **合計** | {tot[0]:.0f}／{tot[1]:,.0f}／{tot[2]:,.0f}／{tot[3]:,.0f} | {tot[4]:.0f}／{tot[5]:,.0f}／{tot[6]:,.0f}／{tot[7]:,.0f} | "
                 f"{tot[0] - tot[4]:.0f}／{tot[3] - tot[7]:,.0f} |")
    return tot


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--live", default=str(Path.home() / ".claude" / "projects"))
    ap.add_argument("--since", default="2026-10-01")
    ap.add_argument("--md")
    a = ap.parse_args()
    out = []

    # ① 004 兩跑＋交叉三跑的第一回合
    ft = defaultdict(lambda: [0.0] * 8)
    runs = ["2026-10-23-CCon-R1", "2026-10-23-CCon-R2", "2026-10-23-CCon-1", "2026-10-23-CCon-2", "2026-10-23-CCon-3"]
    for run in runs:
        tp = sorted((RES / run / "B-1" / "transcript").glob("*.jsonl"))[0]
        acc, _ = replay(tp, first_turn_window(run))
        add(ft, acc)
    t_first = table("① 004 改程式題第一回合（CCon-R1、R2＋交叉 CCon-1～3，B-1-t1 起訖）", ft, len(runs), out)

    # ①b wave2-kit 全部無頭紀錄、所有回合
    hl = defaultdict(lambda: [0.0] * 8)
    hl_n = 0
    for tp in RES.rglob("*.jsonl"):
        if "transcript" not in tp.parts:
            continue
        acc, _ = replay(tp)
        add(hl, acc)
        hl_n += 1
    t_hl = table("①b wave2-kit 全部無頭紀錄（所有回合）", hl, hl_n, out)

    # ② 真實 session（live transcript 唯讀；since 之後改過的）
    since = datetime.fromisoformat(a.since).timestamp()
    groups = {"~/.claude 本身": defaultdict(lambda: [0.0] * 8), "其他專案": defaultdict(lambda: [0.0] * 8)}
    counts = {"~/.claude 本身": [0, 0, 0], "其他專案": [0, 0, 0]}      # session 數、有噪音的 session 數、模型呼叫數
    per_session = []
    for tp in Path(a.live).glob("*/*.jsonl"):
        if tp.stat().st_mtime < since:
            continue
        slug = tp.parent.name.lower()
        if slug.startswith(("c--w4", "c--b5")) or "temp" in slug:
            continue                                    # 無頭受測專案與暫存探針不算真實 session
        g = "~/.claude 本身" if slug in ("c--users-holylight--claude",) or slug.startswith("c--users-holylight--claude-wt") else "其他專案"
        acc, calls = replay(tp)
        add(groups[g], acc)
        counts[g][0] += 1
        counts[g][2] += calls
        if acc:
            counts[g][1] += 1
            pre = sum(v[3] for v in acc.values())
            post = sum(v[7] for v in acc.values())
            per_session.append((pre - post, pre, post, sum(v[0] for v in acc.values()), sum(v[4] for v in acc.values()), calls, tp.parent.name, tp.stem[:8]))
    tots = {}
    for g in groups:
        tots[g] = table(f"② 真實 session：{g}（{a.since} 之後；有這幾種提示的 {counts[g][1]} 個，模型呼叫共 {counts[g][2]:,} 次）",
                        groups[g], counts[g][0], out)
    per_session.sort(reverse=True)
    out.append("\n## ② 省最多的 10 個 session（含重讀 token）")
    out.append("| 專案 slug | session | 模型呼叫 | 段 前→後 | 含重讀 token 前→後 | 省 |")
    out.append("|---|---|---|---|---|---|")
    for saved, pre, post, s0, s1, calls, slug, sid in per_session[:10]:
        out.append(f"| {slug} | {sid} | {calls} | {s0:.0f}→{s1:.0f} | {pre:,.0f}→{post:,.0f} | {saved:,.0f} |")
    noisy = [x for x in per_session]
    if noisy:
        avg_pre = sum(x[1] for x in noisy) / len(noisy)
        avg_post = sum(x[2] for x in noisy) / len(noisy)
        out.append(f"\n有這幾種提示的 session 平均：含重讀 {avg_pre:,.0f} → {avg_post:,.0f} token（省 {avg_pre - avg_post:,.0f}）；"
                   f"段數平均 {sum(x[3] for x in noisy) / len(noisy):.1f} → {sum(x[4] for x in noisy) / len(noisy):.1f}")
    text = "\n".join(out)
    print(text)
    if a.md:
        Path(a.md).write_text(text + "\n", encoding="utf-8")
    real = sum(tots[g][3] - tots[g][7] for g in tots)
    n_noisy = sum(counts[g][1] for g in counts)
    print(f"NOTICE_REPLAY DONE first_turn_pre={t_first[3]:.0f} first_turn_post={t_first[7]:.0f} "
          f"headless_saved_segs={t_hl[0] - t_hl[4]:.0f} headless_saved_tok={t_hl[3] - t_hl[7]:.0f} "
          f"real_sessions={sum(c[0] for c in counts.values())} real_noisy={n_noisy} real_saved_tok={real:.0f} "
          f"real_saved_per_noisy={(real / n_noisy if n_noisy else 0):.0f}")


if __name__ == "__main__":
    main()

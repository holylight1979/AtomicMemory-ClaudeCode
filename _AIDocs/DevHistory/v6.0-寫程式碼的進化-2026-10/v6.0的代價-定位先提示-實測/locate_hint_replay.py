r"""locate_hint_replay.py — 定位與立樹「讀到就先提示」（規則 LOCATE_HINT_ON_FIRST_READ）：拿 004 的 transcript 帳重播，量第一回合砍前→砍後。

做什麼
  1. 事件帳（實測）：從 004 一跑（R1／R2）第一回合的 transcript 照順序抽出讀檔（Read／Bash／PowerShell／Grep 的工具結果）、改檔
     （Write／Edit／Bash 寫檔的工具呼叫）、need_goal 呼叫，各帶「那個時點的 transcript 前綴」，交 locate_hint_worker.py 在三版程式裡重播：
     --old（f5b30c9e，004 跑的當下 live main）、--main（f45be4ea，派工時的 main）、--new（分支工作樹）。受測專案用 --proj
     （C:\w4\qb2-sales 的 c727214 匯出），資料根用 --root 的複本（卡、config 跟當時同一批；寫入只落複本）。
  2. 先證重播對得上：當時版（--old）每則 OverviewHub 注入（從「本 session 第一次碰到」起）逐字出現在 transcript 那次工具結果的
     additionalContext 裡；每次改檔擋不擋、OverviewHub／NeedGoal 擋訊息本文（判準卡之前）逐字等於 transcript。一筆不同 selfcheck 就 FAIL。
  3. 分支版（--new）對 main：每次改檔擋不擋、擋訊息逐字相同（判定與文字不動）；提示出在哪一次讀檔結果、在第一個被擋的改檔之前沒有。
  4. 反事實（判定是實測、「AI 照不照做」是推論）：AI 照提示做＝被擋那批改檔的前一則回覆文字交了四行（取 AI 後來自己交過的那組，
     原本寫在 Bash 的 # 註解）、改檔用它後來成功的那批 Edit／Write → 用分支版重播那批改檔，記擋不擋（main 版同一批照跑對照）。
  5. 量差（推論，沿用 first_turn_breakdown 的拆段與估算式）：照提示做時被擋那段（ftb 分類 a、閘 OverviewHub 的連續呼叫）整段不發生——
     省「那幾次呼叫本身的輸入」＋「之後每次呼叫少讀它們留下的量 D＝T(成功那次)−T(第一次被擋)」，加回提示與四行被之後重讀的量。
     秒＝被省掉的呼叫 ftb 的 model_s（送出到回完）與 slot_s（含工具與 hook）。
怎麼跑
  先匯出兩版程式（hooks、lib、workflow/config.json）與受測專案：git archive <commit> hooks lib workflow/config.json，解到各自目錄；
  python -X utf8 locate_hint_replay.py --old <f5b30c9e 匯出> --main <f45be4ea 匯出> --proj <c727214 匯出>
      [--new <分支工作樹>] [--root C:\w4\qb2-sales-root] [--runs 2026-10-23-CCon-R1,2026-10-23-CCon-R2] [--show]
  尾行 LOCATE_HINT_REPLAY_CHECK PASS／FAIL（當時版逐字對上 transcript、分支版判定與擋訊息同 main、反事實那批分支版不擋＝PASS）；
  上一行 LOCATE_HINT_REPLAY DONE r1_saved=… r2_saved=…（萬）blocks_before=… blocks_after=… calls_saved=… secs=…
"""
import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FTB = HERE.parent / "v6.0的代價-第一回合分布-實測" / "first_turn_breakdown.py"
RES = Path.home() / ".claude" / "workflow" / "inbox" / "wave2-kit" / "results"      # 004 帳，唯讀
ORIG = "C:\\w4\\qb2-sales"
NG = "mcp__workflow-guardian__need_goal"
MARK = "[Guardian:OverviewHub] 本 session 第一次碰到"
HINT = "[Guardian:OverviewHub] 改【"
CARD = "\n判準卡（"
READ_TOOLS = ("Read", "Bash", "PowerShell", "Grep")
EDIT_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit", "Bash", "PowerShell")


def load_ftb():
    spec = importlib.util.spec_from_file_location("ftb", FTB)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def tr_text(c):
    return c if isinstance(c, str) else "\n".join(x.get("text", "") for x in c or [] if isinstance(x, dict))


def remap(obj, src, dst):
    if isinstance(obj, str):
        return obj.replace(src, dst).replace(src.replace("\\", "/"), dst.replace("\\", "/"))
    if isinstance(obj, list):
        return [remap(x, src, dst) for x in obj]
    if isinstance(obj, dict):
        return {k: remap(v, src, dst) for k, v in obj.items()}
    return obj


def build(name, ftb, proj):
    """第一回合事件（實際時間線）＋transcript 的對照材料。"""
    seg = ftb.load_segment(name)
    end_ts = seg["calls"][seg["turn_n"] - 1]["ts"]
    tpath = sorted((RES / name / "B-1" / "transcript").glob("*.jsonl"))[0]
    rows = [json.loads(x) for x in tpath.read_text(encoding="utf-8").splitlines()]
    sid = next(r["sessionId"] for r in rows if r.get("sessionId"))
    log = (RES / name / "B-1" / "workflow" / "_overview-hub.log").read_text(encoding="utf-8").splitlines()
    intent = next(json.loads(x).get("intent") for x in log if '"inject"' in x)
    uses, results, ctx = {}, {}, {}
    for i, r in enumerate(rows, 1):
        t = r.get("type")
        if t == "assistant":
            for b in r["message"]["content"]:
                if b.get("type") == "tool_use":
                    uses[b["id"]] = (i, b, r["message"]["id"])
        elif t == "user" and not isinstance(r["message"]["content"], str):
            for b in r["message"]["content"]:
                if b.get("type") == "tool_result":
                    results[b["tool_use_id"]] = (i, b)
        elif t == "attachment" and r["attachment"].get("hookEvent") == "PostToolUse" and r["attachment"].get("toolUseID"):
            ctx.setdefault(r["attachment"]["toolUseID"], []).extend(r["attachment"].get("content") or [])
    events = []
    for tid, (li, b, mid) in uses.items():
        if ftb.local_naive(rows[li - 1]["timestamp"]) > end_ts:
            continue
        res_line, res = results.get(tid, (None, {}))
        text = tr_text(res.get("content"))
        denied = bool(res.get("is_error")) and bool(ftb.DENY_RE.match(text))
        inp = remap(b.get("input") or {}, ORIG, str(proj))
        base = {"tid": tid, "tool": b["name"], "input": inp, "mid": mid, "tool_line": li}
        if b["name"] == NG:
            events.append({**base, "kind": "goal", "line": res_line, "cut": res_line - 1})
            continue
        if b["name"] in EDIT_TOOLS:
            events.append({**base, "kind": "edit", "line": li, "cut": li - 1, "expect_denied": denied,
                           "expect": text.split("hook error: ", 1)[1].split(CARD, 1)[0] if denied else None})
        if b["name"] in READ_TOOLS and res_line and not denied:
            events.append({**base, "kind": "read", "line": res_line, "cut": res_line - 1,
                           "exit": 1 if res.get("is_error") else 0, "expect_ctx": "\n".join(ctx.get(tid, []))})
    events.sort(key=lambda e: (e["line"], e["kind"] != "edit"))
    return {"name": name, "sid": sid, "intent": intent, "tpath": tpath, "rows": rows, "events": events, "seg": seg}


def run_worker(code, root, run, events, proj, tag):
    data = Path(tempfile.mkdtemp(prefix=f"locate-hint-{tag}-"))
    shutil.copytree(root / "memory", data / "memory")
    (data / "workflow").mkdir()
    shutil.copy2(root / "workflow" / "config.json", data / "workflow" / "config.json")
    ev_path, out = data / "events.json", data / "out.json"
    ev_path.write_text(json.dumps({"sid": run["sid"], "intent": run["intent"], "cwd": str(proj), "events": events},
                                  ensure_ascii=False), encoding="utf-8")
    p = subprocess.run([sys.executable, "-X", "utf8", str(HERE / "locate_hint_worker.py"), "--code", str(code), "--events", str(ev_path),
                        "--data", str(data), "--out", str(out), "--transcript", str(run["tpath"])],
                       capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        raise SystemExit(f"worker {tag} 失敗：{p.stderr[-3000:]}")
    got = json.loads(out.read_text(encoding="utf-8"))
    shutil.rmtree(data, ignore_errors=True)
    return [remap(g, str(proj), ORIG) for g in got]


def gate_of(text):
    return "OverviewHub" if text and "[Guardian:OverviewHub]" in text[:200] else ("NeedGoal" if text and text.startswith("[NeedGoal]") else "other")


def fidelity(run, old):
    """當時版對 transcript：注入段逐字在、改檔擋不擋與擋訊息本文逐字同。回 (相同筆數, 比過筆數, 不同的說明)。"""
    same = total = 0
    bad = []
    for ev, g in zip(run["events"], old):
        if ev["kind"] == "read" and g.get("text") and MARK in g["text"]:
            total += 1
            seg = g["text"][g["text"].index(MARK):]
            if seg in ev["expect_ctx"]:
                same += 1
            else:
                bad.append(f"行 {ev['line']} 注入不在 transcript 那則工具結果裡：重播「{seg[:80]}」")
        elif ev["kind"] == "read" and MARK in ev["expect_ctx"]:
            total += 1
            bad.append(f"行 {ev['line']} transcript 有注入、重播沒有")
        elif ev["kind"] == "edit":
            if ev["expect_denied"] and gate_of(ev["expect"]) == "other":
                continue                                   # 別的閘（動資料檔…）擋的：不在這次重播範圍
            total += 1
            if (g["deny"] or None) == ev["expect"]:
                same += 1
            else:
                bad.append(f"行 {ev['line']} {ev['tool']} 擋訊息不同：transcript「{(ev['expect'] or '放行')[:80]}」／重播「{(g['deny'] or '放行')[:80]}」")
    return same, total, bad


def counterfactual_events(run):
    """AI 照提示做：第一則被定位閘擋的改檔那則回覆之前插一則回覆文字（AI 後來自己交的那組定位行），改檔換成它後來成功的那批。"""
    evs = run["events"]
    first = next(e for e in evs if e["kind"] == "edit" and e["expect_denied"] and gate_of(e["expect"]) == "OverviewHub")
    first_row = next(i for i, r in enumerate(run["rows"], 1) if r.get("type") == "assistant" and r["message"]["id"] == first["mid"])
    decl = next(e for e in evs if e["kind"] == "edit" and e["line"] > first["line"] and e["tool"] in ("Bash", "PowerShell")
                and "# 定位｜" in e["input"].get("command", ""))
    lines = [ln.strip()[1:].strip() for ln in decl["input"]["command"].splitlines() if ln.strip().startswith("# 定位｜")]
    ok = next(e for e in evs if e["kind"] == "edit" and e["line"] > decl["line"] and not e["expect_denied"]
              and e["tool"] not in ("Bash", "PowerShell"))
    batch = [e for e in evs if e["kind"] == "edit" and e["mid"] == ok["mid"]]
    text_row = {"type": "assistant", "message": {"id": "counterfactual-locate", "role": "assistant",
                                                 "content": [{"type": "text", "text": "\n".join(lines)}]}}
    before = [e for e in evs if e["line"] < first_row]
    cf = before + [{**e, "cut": first_row - 1, "insert": [text_row], "line": first_row} for e in batch]
    return cf, "\n".join(lines), first, ok, batch


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--old", required=True)
    ap.add_argument("--main", required=True)
    ap.add_argument("--new", default=str(HERE.parents[3]))
    ap.add_argument("--proj", required=True)
    ap.add_argument("--root", default=r"C:\w4\qb2-sales-root")
    ap.add_argument("--runs", default="2026-10-23-CCon-R1,2026-10-23-CCon-R2")
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()
    ftb = load_ftb()
    names = ftb.DEF_OFF.split(",") + ftb.DEF_RUNS.split(",") + ftb.DEF_CROSS.split(",")
    raw = [ftb.load_segment(x) for x in names]
    coef, _, _ = ftb.fit_estimator(raw)
    ss, _ = ftb.fit_schema(raw, coef)
    T0 = sum(r["calls"][0]["T"] for r in raw[:3]) / 3

    def est(text):
        c, o = ftb.feats(text)
        return max(coef[0] * c + coef[1] * o + coef[2], 1.0)

    proj, root = Path(a.proj).resolve(), Path(a.root)
    problems, done = [], {}
    for name in [x for x in a.runs.split(",") if x]:
        run = build(name, ftb, proj)
        evs = run["events"]
        old = run_worker(a.old, root, run, evs, proj, "old")
        main_ = run_worker(a.main, root, run, evs, proj, "main")
        new = run_worker(a.new, root, run, evs, proj, "new")
        same, total, bad = fidelity(run, old)
        problems += [f"{name[-2:]} {b}" for b in bad]
        # 分支對 main：判定與擋訊息逐字相同；注入段只多提示那一行
        drift = []
        for ev, m, n in zip(evs, main_, new):
            if ev["kind"] == "edit" and m["deny"] != n["deny"]:
                drift.append(f"行 {ev['line']} 擋訊息分支與 main 不同")
            if ev["kind"] == "read" and (m.get("text") or "") != "\n\n".join(
                    x for x in (n.get("text") or "").split("\n\n") if not x.startswith(HINT)):
                drift.append(f"行 {ev['line']} 讀檔結果分支除了提示以外跟 main 不同")
        problems += [f"{name[-2:]} {d}" for d in drift]
        hints = [(ev, x) for ev, n in zip(evs, new) if ev["kind"] == "read"
                 for x in (n.get("text") or "").split("\n\n") if x.startswith(HINT)]
        first_edit = next(ev["line"] for ev, n in zip(evs, new) if ev["kind"] == "edit" and n["targets"])   # 第一個真的有寫入目標的改檔
        if not hints or hints[0][0]["line"] > first_edit:
            problems.append(f"{name[-2:]} 第一則提示沒有出在第一個改檔（行 {first_edit}）之前")
        deny_main = [(ev, m["deny"]) for ev, m in zip(evs, main_) if ev["kind"] == "edit" and m["deny"]]
        deny_old = [(ev, o["deny"]) for ev, o in zip(evs, old) if ev["kind"] == "edit" and o["deny"]]
        cf, decl, first, ok, batch = counterfactual_events(run)
        cf_new = run_worker(a.new, root, run, cf, proj, "cf-new")
        cf_main = run_worker(a.main, root, run, cf, proj, "cf-main")
        cf_new_deny = [g["deny"] for g in cf_new[-len(batch):] if g["deny"]]
        cf_main_deny = [g["deny"] for g in cf_main[-len(batch):] if g["deny"]]
        if cf_new_deny:
            problems.append(f"{name[-2:]} 反事實那批分支版仍擋：{cf_new_deny[0][:100]}")
        # 量差（ftb 口徑）
        seg = ftb.analyze(name, coef, ss, T0)
        calls, n, cls, gate = seg["calls"], seg["turn_n"], seg["cls"], seg["gate"]
        kd = next(k for k in range(n) if cls[k] == "a" and gate[k] == "Guardian:OverviewHub")
        ke = next(k for k in range(kd + 1, n) if cls[k] != "a")
        removed = sum(calls[j]["T"] for j in range(kd, ke))
        D = calls[ke]["T"] - calls[kd]["T"]
        n_after = n - (ke - kd)
        line_call = {}
        for k, c in enumerate(calls[:n]):
            for b in c["blocks"]:
                if b.get("type") == "tool_use":
                    line_call[b["id"]] = k
        add = 0.0
        hint_rows = []
        for ev, h in hints:
            k = line_call[ev["tid"]] + 1                   # 讀檔結果進下一次呼叫的輸入
            k_cf = k if k <= kd else k - (ke - kd)
            add += est(h) * max(n_after - k_cf, 0)
            hint_rows.append((ev["line"], k, round(est(h)), h))
        decl_tok = est(decl)
        add += decl_tok * (n_after - kd)                   # 四行寫在被擋那批的前一則回覆，從第 kd 次起被讀
        before_total = sum(calls[j]["T"] for j in range(n))
        after_total = sum(calls[j]["T"] for j in range(kd)) + sum(calls[j]["T"] - D for j in range(ke, n)) + add
        secs = (sum(calls[j]["model_s"] for j in range(kd, ke)), sum(calls[j]["slot_s"] for j in range(kd, ke)))
        ovh_a1 = sum(v for (c, s), v in seg["acc"].items() if c == "a1" and s == "Guardian:OverviewHub")
        ovh_a2 = sum(v for (c, s), v in seg["acc"].items() if c == "a2" and s == "Guardian:OverviewHub")
        ovh_b = sum(v for (c, s), v in seg["acc"].items() if c == "b" and s.startswith("Guardian:OverviewHub"))
        ng_deny = [e for e in evs if e["kind"] == "edit" and e["expect_denied"] and gate_of(e["expect"]) == "NeedGoal"]
        ovh_deny = [e for e in evs if e["kind"] == "edit" and e["expect_denied"] and gate_of(e["expect"]) == "OverviewHub"]
        done[name] = dict(before=before_total, after=after_total, saved=before_total - after_total, removed=removed, D=D,
                          add=add, calls=ke - kd, secs=secs, blocks_before=len(ovh_deny) + len(ng_deny),
                          blocks_after=len(cf_new_deny))
        print(f"\n## {name}（{run['tpath'].name}）")
        print(f"- 當時版重播對 transcript：{same}/{total} 筆逐字相同（注入段＋改檔擋不擋與擋訊息本文）")
        print(f"- 砍前（004 帳）：第一回合 {n} 次呼叫、輸入 {before_total:,}；沒樹被擋 {len(ng_deny)} 次；缺定位被擋 {len(ovh_deny)} 次"
              f"（第一次在第 {kd} 次呼叫、行 {first['line']}）；定位閘擋過後到改成功前多 {ke - kd} 次呼叫（第 {kd}～{ke - 1} 次）；"
              f"OverviewHub a1 {ovh_a1:,.0f}、a2 {ovh_a2:,.0f}、擋訊息被重讀 b {ovh_b:,.0f}")
        print(f"- main 版同一批輸入：改檔擋 {len(deny_main)} 次（當時版 {len(deny_old)} 次）；第一次擋的缺件："
              f"{(deny_main[0][1].splitlines()[1][:70] if deny_main else '無')}")
        print(f"- 分支版：判定與擋訊息同 main（{'是' if not drift else '否：' + '；'.join(drift)}）；提示 {len(hints)} 則：")
        for line, k, t, h in hint_rows:
            print(f"  - 行 {line}（進第 {k} 次呼叫的輸入，約 {t} tok）：{h}")
        print(f"- 反事實（推論：AI 照提示做）：被擋那批前一則回覆交四行（{decl_tok:.0f} tok，AI 自己後來交的那組），改檔換成行 {ok['line']} 起成功的那批 "
              f"{len(batch)} 筆 → 分支版擋 {len(cf_new_deny)} 次、main 版擋 {len(cf_main_deny)} 次")
        print(f"- 量差（推論）：去掉第 {kd}～{ke - 1} 次呼叫（輸入 {removed:,}）、之後每次少讀 D={D:,}；加回提示與四行被重讀 {add:,.0f}；"
              f"第一回合 {before_total:,} → {after_total:,.0f}，省 {before_total - after_total:,.0f}；"
              f"秒（模型／含工具與 hook）{secs[0]:.1f}／{secs[1]:.1f}")
        if a.show:
            print(f"  四行：{decl}")
    for p in problems:
        print("[不同] " + p)
    k1, k2 = list(done)[:2] if len(done) > 1 else (list(done) * 2)[:2]
    calls_saved = sum(v["calls"] for v in done.values())
    secs = sum(v["secs"][0] for v in done.values()) / len(done)
    print(f"LOCATE_HINT_REPLAY DONE r1_saved={done[k1]['saved'] / 1e4:.2f} r2_saved={done[k2]['saved'] / 1e4:.2f} "
          f"blocks_before={sum(v['blocks_before'] for v in done.values())} blocks_after={sum(v['blocks_after'] for v in done.values())} "
          f"calls_saved={calls_saved} secs={secs:.1f}")
    print("LOCATE_HINT_REPLAY_CHECK " + ("PASS" if not problems else "FAIL"))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())

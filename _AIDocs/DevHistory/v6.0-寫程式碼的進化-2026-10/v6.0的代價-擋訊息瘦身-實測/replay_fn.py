"""replay_fn.py — 函式級事件帳重播：同一批輸入交給「當時的程式」與「分支的程式」組裝，先證當時的逐字等於 transcript，再量分支省多少。

做什麼
  1. 從 004 一跑（R1／R2）的 transcript 抽出第一回合每一次「問」：PreToolUse 擋訊息（問句＝擋訊息本文，判準卡＝其後）、
     PostToolUse／Stop 注入裡接了判準卡的那段、Stop 擋訊息（使用者訊息那份）。動資料檔那筆另帶真輸入（Edit 參數、
     cwd、截到被擋那則之前的 transcript 複本）交 wg_data_file.gate 重組本文。
  2. 各開一個子行程（replay_worker.py）跑兩版程式：--old（預設 f5b30c9e 的匯出，004 跑的當下 live main）與 --new（分支工作樹），
     資料根各用一份 C:\\w4\\qb2-sales-root 的複本（卡池、config 跟當時同一批；寫入只落複本）。
  3. 逐字比：當時版的「問句＋判準卡」對 transcript 原文，一筆不同就印出來、selfcheck 記 mismatch。
  4. 量差：沿用 first_turn_breakdown（ftb）的拆段與估算式；每段的新 token＝原段實測分到的 token × 新估算／舊估算，
     省下的 × 之後每次呼叫（含這次）＝少讀的 token；另列只算照常呼叫（＝ftb b 類口徑）。
  讀檔提示省掉的兩次呼叫另見 deny_slim_replay.py（反事實，推論），本檔只量文字（實測總量＋推論分段）。
怎麼跑
  先匯出當時版：在 repo 裡 git archive --format=tar -o old.tar f5b30c9e，解到 <匯出目錄>
  python -X utf8 replay_fn.py --old <匯出目錄> [--runs 2026-10-23-CCon-R1,2026-10-23-CCon-R2] [--new <程式碼根>]
  尾行 REPLAY_FN_CHECK PASS／FAIL（當時版逐字對得上 transcript＝PASS）＋ 上一行 REPLAY_FN DONE r1=… r2=…（文字少讀，萬）
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
RES = Path.home() / ".claude" / "workflow" / "inbox" / "wave2-kit" / "results"
ROOT = Path(r"C:\w4\qb2-sales-root")
PROJ = r"C:\w4\qb2-sales"
CARD = "\n判準卡（"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def tr_text(c):
    return c if isinstance(c, str) else "\n".join(x.get("text", "") for x in c or [] if isinstance(x, dict))


def extract(name, ftb, tmp):
    """第一回合每一次問 → [{i, sid, path, question, expect_note, gate?, line}]；i＝transcript 行號（1 起算）。"""
    seg = ftb.load_segment(name)
    n = seg["turn_n"]
    tp = sorted((RES / name / "B-1" / "transcript").glob("*.jsonl"))[0]
    raw = tp.read_text(encoding="utf-8").splitlines(keepends=True)
    rows = [json.loads(x) for x in raw]
    sid = next(r["sessionId"] for r in rows if r.get("sessionId"))
    end_ts = seg["calls"][n - 1]["ts"]           # 第一回合最後一次呼叫：它之後進來的不算
    tool_uses = {}
    asks = []
    for i, r in enumerate(rows, 1):
        t = r.get("type")
        if t == "assistant":
            for b in r["message"]["content"]:
                if b.get("type") == "tool_use":
                    tool_uses[b["id"]] = (i, b)
            if ftb.local_naive(r["timestamp"]) > end_ts:
                break
        if t == "user" and not isinstance(r["message"]["content"], str):
            for b in r["message"]["content"]:
                if b.get("type") != "tool_result" or not b.get("is_error"):
                    continue
                text = tr_text(b.get("content"))
                if not ftb.DENY_RE.match(text):
                    continue
                full = text.split("hook error: ", 1)[1]
                q, _, rest = full.partition(CARD)
                ask = {"i": i, "sid": sid, "path": "pretool_deny", "question": q, "expect_note": ("判準卡（" + rest) if rest else ""}
                if "[Guardian:DataFileAsk]" in q:
                    li, tu = tool_uses[b["tool_use_id"]]
                    cut = tmp / f"{name}-to-{li}.jsonl"
                    cut.write_text("".join(raw[:li - 1]), encoding="utf-8")     # 被擋那則工具呼叫之前
                    first = next(x for x in rows if x.get("type") == "user" and isinstance(x["message"]["content"], str))
                    ask["state"] = {"session": {"id": sid, "cwd": PROJ}, "turn_seq": 1,       # 當時 state 也記了原話（(d) 的則數）
                                    "recent_user_prompts": [first["message"]["content"]], "turn_prompts": [first["message"]["content"]]}
                    ask["gate"] = {"tool_name": tu["name"], "tool_input": tu["input"],
                                   "input_data": {"session_id": sid, "cwd": PROJ, "transcript_path": str(cut),
                                                  "tool_name": tu["name"], "tool_input": tu["input"], "tool_use_id": tu["id"]}}
                asks.append(ask)
        elif t == "user" and isinstance(r["message"]["content"], str) and r.get("isMeta") \
                and r["message"]["content"].startswith("Stop hook feedback:") and "判準卡（" in r["message"]["content"]:
            body = r["message"]["content"].split("Stop hook feedback:\n", 1)[1]
            q, _, rest = body.partition(CARD)
            asks.append({"i": i, "sid": sid, "path": "stop_piggyback", "question": q, "expect_note": "判準卡（" + rest})
        elif t == "attachment" and r["attachment"]["type"] == "hook_additional_context":
            for text in r["attachment"].get("content") or []:
                if CARD not in text:
                    continue
                q, _, rest = text.partition(CARD)
                path = "stop_piggyback" if r["attachment"].get("hookEvent") == "Stop" else "mcp_reply"
                asks.append({"i": i, "sid": sid, "path": path, "question": q, "expect_note": "判準卡（" + rest})
    return seg, asks


def run_worker(code, asks_path, tag):
    root = Path(tempfile.mkdtemp(prefix=f"replay-{tag}-"))
    shutil.copytree(ROOT / "memory", root / "memory")
    (root / "workflow").mkdir()
    cfg = ROOT / "workflow" / "config.json"
    shutil.copy2(cfg, root / "workflow" / "config.json")
    out = root / "out.json"
    env = {**os.environ, "WG_CLAUDE_DIR": str(root), "WG_V6": "1"}
    p = subprocess.run([sys.executable, "-X", "utf8", str(HERE / "replay_worker.py"), "--code", str(code), "--asks", str(asks_path),
                        "--config", str(cfg), "--out", str(out)], env=env, capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        raise SystemExit(f"worker {tag} 失敗：{p.stderr[-2000:]}")
    return {x["i"]: x for x in json.loads(out.read_text(encoding="utf-8"))}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", default="2026-10-23-CCon-R1,2026-10-23-CCon-R2")
    ap.add_argument("--old", required=True, help="當時版程式的匯出目錄（git archive f5b30c9e | tar -x -C <目錄>）")
    ap.add_argument("--new", default=r"C:\Users\holylight\.claude-wt\deny-text-slim")
    a = ap.parse_args()
    rp = load(HERE / "deny_slim_replay.py", "rp")
    ftb = rp.load_ftb()
    names = ftb.DEF_OFF.split(",") + ftb.DEF_RUNS.split(",") + ftb.DEF_CROSS.split(",")
    raw = [ftb.load_segment(x) for x in names]
    coef, _, _ = ftb.fit_estimator(raw)
    ss, _ = ftb.fit_schema(raw, coef)
    T0 = sum(r["calls"][0]["T"] for r in raw[:3]) / 3
    tmp = Path(tempfile.mkdtemp(prefix="replay-fn-"))
    mismatch, done = [], {}
    for name in [x for x in a.runs.split(",") if x]:
        _, asks = extract(name, ftb, tmp)
        ap_ = tmp / f"{name}-asks.json"
        ap_.write_text(json.dumps(asks, ensure_ascii=False), encoding="utf-8")
        old, new = run_worker(a.old, ap_, "old"), run_worker(a.new, ap_, "new")
        same = 0
        for ask in asks:
            o = old[ask["i"]]
            if o["question"] != ask["question"] or o["note"] != ask["expect_note"]:
                which = "問句" if o["question"] != ask["question"] else "判準卡"
                exp, got = (ask["question"], o["question"]) if which == "問句" else (ask["expect_note"], o["note"])
                k = next((j for j in range(min(len(exp), len(got))) if exp[j] != got[j]), min(len(exp), len(got)))
                mismatch.append(f"{name[-2:]} 行 {ask['i']} {ask['path']} {which}不同，第 {k} 字起：transcript「{exp[k:k + 60]}」／重播「{got[k:k + 60]}」")
            else:
                same += 1
        # 量差：ftb 的段（帶原文）逐段換成分支版的文字
        run = ftb.analyze(name, coef, ss, T0)
        n, cls = run["turn_n"], run["cls"]
        swaps = []
        for ask in asks:
            o, w = old[ask["i"]], new[ask["i"]]
            if o["question"] != w["question"]:
                swaps.append((o["question"], w["question"]))
            if o["note"] != w["note"]:
                swaps.append((o["note"], w["note"]))
        total = base = 0.0
        rows = []
        for k in range(n):
            for p in run["calls"][k]["pieces"]:
                text = p.text or ""
                if p.kind == "deny" and p.src.endswith("擋訊息附的判準卡"):
                    text = "判準卡（" + text
                new_text = text
                for o_, w_ in swaps:
                    if o_ and o_ in new_text:
                        new_text = new_text.replace(o_, w_)
                if new_text == text or p.tok <= 0:
                    continue
                nt = p.tok * rp.est(ftb, coef, new_text) / max(p.est, 1.0)
                d = (p.tok - nt)
                total += d * (n - k)
                base += d * sum(1 for j in range(k, n) if cls[j] == "base")
                rows.append((k, p.src, p.tok, nt, n - k))
        done[name] = (total, base)
        print(f"\n## {name}：第一回合的問 {len(asks)} 筆，當時版逐字相同 {same} 筆")
        print("| 呼叫 | 段 | 舊 tok | 新 tok | 被讀幾次 |")
        print("|---|---|---|---|---|")
        for k, src, o_, nt, r in rows:
            print(f"| {k} | {src} | {o_:,.0f} | {nt:,.0f} | {r} |")
        print(f"文字少讀（分支函式組裝）：全部呼叫 {total:,.0f}；只算照常呼叫 {base:,.0f}")
        for ask in asks:
            if old[ask["i"]] != new[ask["i"]] and (old[ask["i"]]["note"] != new[ask["i"]]["note"] or old[ask["i"]]["question"] != new[ask["i"]]["question"]):
                print(f"- 行 {ask['i']} {ask['path']}：問句 {len(old[ask['i']]['question'])}→{len(new[ask['i']]['question'])} 字、"
                      f"判準卡 {len(old[ask['i']]['note'])}→{len(new[ask['i']]['note'])} 字；新判準卡：{new[ask['i']]['note'][:120]!r}")
    for m in mismatch:
        print("[不同] " + m)
    vals = " ".join(f"{nm[-2:].lower()}={t / 1e4:.2f} {nm[-2:].lower()}_base={b / 1e4:.2f}" for nm, (t, b) in done.items())
    print(f"REPLAY_FN DONE {vals} mismatch={len(mismatch)}")
    print("REPLAY_FN_CHECK " + ("PASS" if not mismatch else "FAIL"))
    sys.exit(0 if not mismatch else 1)


if __name__ == "__main__":
    main()

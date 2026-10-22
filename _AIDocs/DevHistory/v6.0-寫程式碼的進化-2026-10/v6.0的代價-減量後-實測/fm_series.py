"""fm_series.py — 減量後最後量測的 8 跑串跑器：兩類題 ×（hook 全關／現況）× 兩跑，一律串行、無人值守，照規則加跑。

做什麼
  1. 順序：改 code 題（題 B′）全關1→現況1→全關2→現況2，判加跑；再非改 code 題（B5 題四，fm_nc.py）同樣四跑，判加跑。
  2. 每跑前重建 C:\\w4：w2_build_env --selfcheck --cards-from <卡集清單>（每跑帶同一批卡），尾行要 PASS；再 fm_snap.py apply
     把三個資料根的 memory/ 換成卡內容快照（每跑卡的內容也相同），尾行要 PASS；非改 code 題再跑 fm_nc.py build。
  3. 跑：改 code 題 w2_run_all --only B --date <日>-CC{off,on}-<n> [--hooks-off]；非改 code 題 fm_nc.py run --date <日>-NC…。
     環境照呼叫端（WG_V6=1 由呼叫端設；兩組都設）。輸出落 <kit>/results/<那跑>/_fm/。
  4. 跑完：資料根 Logs\\ 整包（含連鎖斷路器帳 chain-<session>.jsonl；w2_collect 只收 guard-*.jsonl）複製到 _fm/root-Logs/；
     全關組核 hook 紀錄 0（transcript 沒有 hook 附件與 stop_hook_summary、資料根 Logs 空）；用 b6_measure.measure_segment 量每段，
     寫 _fm/measure.json（輸入＝input＋cache_creation＋cache_read，同上一輪口徑）。
  5. 作廢與加跑：一跑沒跑完（failed>0）或現況某跑 hook 被系統砍掉（transcript 的 hook_cancelled）→ 那跑作廢；
     一類題四跑後，有作廢、或現況兩跑「輸入＋輸出 token」或「牆鐘」相差超過 25%（差 ÷ 兩跑平均）→ 加跑一對（全關3→現況3），只加一次。
怎麼跑（放在 w2_*.py、fm_nc.py 同一個目錄；先跑完一次 w2_build_env 拿到卡集清單）
  WG_V6=1 python -X utf8 fm_series.py --day 2026-10-23 --cards <卡集清單.json> --snap <卡內容快照資料夾> [--only CC,NC] [--dest C:/w4]
尾行 FM_SERIES DONE runs=<跑數> void=<作廢數> extra=<加跑的類> ；建環境連兩次 FAIL 印 FM_SERIES FAIL reason=…（exit 1）
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIVE = Path("C:/Users/holylight/.claude")
KIT = LIVE / "workflow" / "inbox" / "wave2-kit"
MEASURE_DIR = Path("C:/Users/holylight/.claude-wt/final-measure/_AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/v6.0的代價-實測")
CLASSES = {"CC": {"project": "qb2-sales", "seg_re": r"B-\d"}, "NC": {"project": "qn4-release-guide", "seg_re": r"N-\d"}}
DIFF_LIMIT = 0.25

sys.path.insert(0, str(MEASURE_DIR))
import b6_measure  # noqa: E402

EST = b6_measure.load_estimator(str(LIVE))


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def sh(args, out_file):
    """跑一支 python 腳本、輸出整份存檔，回 (rc, 尾行)。"""
    r = subprocess.run([sys.executable, "-X", "utf8", *args], cwd=str(HERE), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(r.stdout + ("\n--- stderr ---\n" + r.stderr if r.stderr.strip() else ""), encoding="utf-8")
    lines = [x for x in r.stdout.strip().splitlines() if x.strip()]
    return r.returncode, (lines[-1] if lines else "")


def rebuild(cls, dest, cards, snap, fm):
    for attempt in (1, 2):
        rc, tail = sh(["w2_build_env.py", "--dest", str(dest), "--selfcheck", "--cards-from", str(cards)], fm / f"build-{attempt}.log")
        if tail == "W2_ENV_BUILD_CHECK PASS":
            break
        log(f"  建環境第 {attempt} 次沒過：{tail}")
    else:
        return False, tail
    rc, tail = sh(["fm_snap.py", "apply", "--snap", str(snap), "--cards", str(cards), "--dest", str(dest)], fm / "snap.log")
    if tail != "FM_SNAP_CHECK PASS":
        return False, tail
    if cls == "NC":
        rc, tail = sh(["fm_nc.py", "build", "--dest", str(dest)], fm / "nc-build.log")
        if not tail.startswith("FM_NC DONE"):
            return False, tail
    return True, tail


def hook_traces(seg_dirs):
    """全關組要是 0：transcript 裡 hook 附件（hook_*）、stop_hook_summary、hook_success 的筆數。"""
    n = 0
    for s in seg_dirs:
        for tx in (s / "transcript").glob("*.jsonl"):
            for line in tx.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                a = r.get("attachment") or {}
                if str(a.get("type", "")).startswith("hook_") or r.get("subtype") == "stop_hook_summary":
                    n += 1
    return n


def efforts(seg_dirs):
    out = {}
    for s in seg_dirs:
        for tx in (s / "transcript").glob("*.jsonl"):
            for line in tx.read_text(encoding="utf-8", errors="replace").splitlines():
                m = re.search(r'"effort": ?"(\w+)"', line)
                if m:
                    out[m.group(1)] = out.get(m.group(1), 0) + 1
    return out


def one_run(cls, grp, n, day, dest, cards, snap):
    name = f"{day}-{cls}{grp}-{n}"
    res = KIT / "results" / name
    fm = res / "_fm"
    log(f"{name}：重建環境")
    built_at = datetime.now().isoformat(timespec="seconds")
    ok, tail = rebuild(cls, dest, cards, snap, fm)
    if not ok:
        return {"name": name, "cls": cls, "grp": grp, "n": n, "void": True, "why": f"建環境沒過：{tail}", "fatal": True}
    log(f"{name}：開跑")
    t0 = datetime.now()
    if cls == "CC":
        args = ["w2_run_all.py", "--only", "B", "--date", name] + (["--hooks-off"] if grp == "off" else [])
        rc, tail = sh(args, fm / "run.log")
        m = re.search(r"failed=(\d+)", tail)
        failed = int(m.group(1)) if m and tail.startswith("W2_RUN_ALL DONE") else 1
    else:
        args = ["fm_nc.py", "run", "--date", name, "--dest", str(dest)] + (["--hooks-off"] if grp == "off" else [])
        rc, tail = sh(args, fm / "run.log")
        m = re.search(r"failed=(\d+)", tail)
        failed = int(m.group(1)) if m and tail.startswith("FM_NC DONE") else 1
    t1 = datetime.now()
    root_logs = dest / f"{CLASSES[cls]['project']}-root" / "Logs"
    if root_logs.is_dir():
        shutil.copytree(root_logs, fm / "root-Logs", dirs_exist_ok=True)
    root_log_files = [p.name for p in root_logs.rglob("*") if p.is_file()] if root_logs.is_dir() else []
    segs = sorted(p for p in res.iterdir() if p.is_dir() and re.fullmatch(CLASSES[cls]["seg_re"], p.name))
    seg_m = {s.name: b6_measure.measure_segment(s, EST) for s in segs}
    tot = {"in": 0, "out": 0, "wall_s": 0.0, "num_turns": 0, "user_turns": 0, "api_calls": 0, "cost": 0.0, "hook_cancelled": 0,
           "denials": 0}
    for sm in seg_m.values():
        for t in sm["turns"]:
            tot["in"] += t["in"]
            tot["out"] += t["out"]
            tot["wall_s"] += t["wall_s"]
            tot["num_turns"] += t["num_turns"]
            tot["denials"] += t["denials"]
            tot["user_turns"] += 1
        tot["api_calls"] += sm["api_calls"]
        tot["cost"] += sm["cost"]
        tot["hook_cancelled"] += sm["hook_cancelled"]
    traces = hook_traces(segs)
    why = []
    if failed:
        why.append(f"沒跑完（尾行：{tail}）")
    if grp == "on" and tot["hook_cancelled"]:
        why.append(f"hook 被系統砍掉 {tot['hook_cancelled']} 次")
    if grp == "off" and (traces or root_log_files):
        why.append(f"全關組卻有 hook 紀錄（transcript {traces} 筆、資料根 Logs {len(root_log_files)} 檔）")
    build_warn = [x.strip() for p in sorted(fm.glob("build-*.log"))
                  for x in p.read_text(encoding="utf-8", errors="replace").splitlines() if x.lstrip().startswith("WARN")]
    rec = {"name": name, "cls": cls, "grp": grp, "n": n, "void": bool(why), "why": "；".join(why), "tail": tail,
           "built_at": built_at, "build_warn": build_warn,
           "series_wall_s": (t1 - t0).total_seconds(), "segments": [s.name for s in segs], "total": tot,
           "hook_traces": traces, "root_log_files": root_log_files, "effort": efforts(segs)}
    (fm / "measure.json").write_text(json.dumps({"run": rec, "segments": seg_m}, ensure_ascii=False, indent=1, default=str),
                                     encoding="utf-8")
    log(f"{name}：完 in={tot['in']} out={tot['out']} wall={tot['wall_s']:.0f}s cancelled={tot['hook_cancelled']} "
        f"traces={traces} void={rec['void']} {rec['why']}")
    return rec


def rel_diff(a, b):
    m = (a + b) / 2
    return abs(a - b) / m if m else 0.0


def need_extra(recs):
    on = [r for r in recs if r["grp"] == "on" and not r["void"]]
    if any(r["void"] for r in recs):
        return "有作廢的跑：" + "；".join(f"{r['name']} {r['why']}" for r in recs if r["void"])
    if len(on) == 2:
        tok = rel_diff(*(r["total"]["in"] + r["total"]["out"] for r in on))
        wall = rel_diff(*(r["total"]["wall_s"] for r in on))
        if tok > DIFF_LIMIT or wall > DIFF_LIMIT:
            return f"現況兩跑相差 token {tok:.0%}、牆鐘 {wall:.0%}（門檻 {DIFF_LIMIT:.0%}）"
    return ""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--day", required=True)
    ap.add_argument("--cards", required=True)
    ap.add_argument("--snap", required=True)
    ap.add_argument("--only", default="CC,NC")
    ap.add_argument("--dest", default="C:/w4")
    a = ap.parse_args()
    if os.environ.get("WG_V6") != "1":
        print("FM_SERIES FAIL reason=WG_V6 沒設成 1（兩組都要設）")
        sys.exit(1)
    dest, cards, snap = Path(a.dest), Path(a.cards), Path(a.snap)
    all_recs, extra = [], []
    summary = KIT / "results" / f"_fm-series-{a.day}.json"
    for cls in a.only.split(","):
        recs = []
        for grp, n in (("off", 1), ("on", 1), ("off", 2), ("on", 2)):
            r = one_run(cls, grp, n, a.day, dest, cards, snap)
            recs.append(r)
            all_recs.append(r)
            summary.write_text(json.dumps(all_recs, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
            if r.get("fatal"):
                print(f"FM_SERIES FAIL reason={r['why']}")
                sys.exit(1)
        why = need_extra(recs)
        if why:
            log(f"{cls} 加跑一對：{why}")
            extra.append(f"{cls}（{why}）")
            for grp in ("off", "on"):
                r = one_run(cls, grp, 3, a.day, dest, cards, snap)
                r["extra_reason"] = why
                all_recs.append(r)
                summary.write_text(json.dumps(all_recs, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
                if r.get("fatal"):
                    print(f"FM_SERIES FAIL reason={r['why']}")
                    sys.exit(1)
    summary.write_text(json.dumps(all_recs, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"FM_SERIES DONE runs={len(all_recs)} void={sum(r['void'] for r in all_recs)} extra={'|'.join(extra) or 'none'}")


if __name__ == "__main__":
    main()

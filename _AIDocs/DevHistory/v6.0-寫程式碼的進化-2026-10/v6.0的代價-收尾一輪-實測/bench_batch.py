"""bench_batch.py — 收尾一輪加在 PostToolBatch 的耗時（行程內計時，不含直譯器啟動與載入 handler；那兩段每支 hook 都有）。

做什麼：資料根用 CT-3 資料根的複本（WG_CLAUDE_DIR 指暫存，不碰 live 與受測原件）、state 用 CT-3 收尾時那份，
分三種批次各跑 N 次 wg_closing_round.on_batch：
  idle   寫碼回合、程式檔沒變、沒有在量（最常見）
  kick   程式檔指紋變了 → 交背景量（git ls-files＋起背景行程）
  close  完整對照那批：附拐彎判斷結果＋最該修材料（git grep 呼叫點、判準卡）
怎麼跑：python -X utf8 bench_batch.py
尾行：BENCH_BATCH DONE idle_ms=… kick_ms=… close_ms=…（中位數）
"""
import copy
import glob
import json
import os
import shutil
import statistics
import sys
import time
from pathlib import Path

TMP = Path(r"C:/Users/holylight/.claude/jobs/778a48b3/tmp")
TREE = Path(r"C:/Users/holylight/.claude-wt/closing-time")
ROOT = TMP / "bench-root"
if ROOT.exists():
    shutil.rmtree(ROOT)
shutil.copytree(Path(r"C:/w4/closing-time/3/qb2-sales-root"), ROOT)
os.environ.update(WG_CLAUDE_DIR=str(ROOT), WG_TEST_LOGS_DIR=str(ROOT / "Logs"), WG_V6="1")
sys.path[:0] = [str(TREE / "hooks"), str(TREE / "lib")]

import wg_closing_round as cr  # noqa: E402
import wg_reading_path as rph  # noqa: E402
from wg_core import load_config  # noqa: E402

N = 5
config = load_config()
src = json.loads(Path(glob.glob(str(TMP / "results/2026-10-27-CT-3/B-1/workflow/state-*.json"))[0]).read_text(encoding="utf-8"))
sid = src["session"]["session_id"] if "session_id" in (src.get("session") or {}) else Path(
    glob.glob(str(TMP / "results/2026-10-27-CT-3/B-1/workflow/state-*.json"))[0]).stem[len("state-"):]
spawned = []
rph._spawn_worker = lambda p: spawned.append(p)        # 起背景行程另計：量 Popen 本身下面單獨量


def files_fp(st):
    own = [m for m in st.get("modified_files") or [] if (m or {}).get("session_id", sid) == sid]
    files = rph.code_files(own, rph.reconcile_cfg(config).get("code_exts") or [], int(st.get("turn_seq", 0)))
    return json.dumps(rph._fingerprint(files), ensure_ascii=False)


def run(kind):
    out = []
    for _ in range(N):
        st = copy.deepcopy(src)
        st.pop("pick_one", None)
        rec = st.setdefault("reading_path", {}).setdefault(sid, {})
        rec.pop("job", None)
        rec.pop("pending", None)
        calls = [{"tool_name": "Bash", "tool_input": {"command": "pytest"}}]
        if kind == "idle":
            rec["early_fp"] = files_fp(st)
        elif kind == "kick":
            rec["early_fp"], rec["key"] = "", ""
        else:
            rec["early_fp"] = files_fp(st)
            rec[rph.EARLY_NOTE] = "[Guardian:ReadingPath] 量好的結果\n  拐彎判斷｜x｜…"
            calls = [{"tool_name": "mcp__workflow-guardian__need_goal", "tool_input": {"action": "reconcile"}}]
        t0 = time.perf_counter()
        parts, _ = cr.on_batch(st, sid, {"session_id": sid, "tool_calls": calls, "cwd": src["session"].get("cwd", "")}, config)
        out.append((time.perf_counter() - t0) * 1000)
        if kind == "close":
            assert any("[Guardian:PickOne]" in p for p in parts), parts
    return statistics.median(out), out


res = {k: run(k) for k in ("idle", "kick", "close")}
import subprocess  # noqa: E402
t0 = time.perf_counter()
subprocess.Popen([sys.executable, "-c", "pass"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                 creationflags=rph._DETACHED).wait()
popen_ms = (time.perf_counter() - t0) * 1000
for k, (med, all_) in res.items():
    print(f"{k}: 中位數 {med:.0f} ms（{', '.join(f'{x:.0f}' for x in all_)}）")
print(f"起背景行程（Popen，kick 另加一次）：{popen_ms:.0f} ms；kick 這段共起了 {len(spawned)} 次")
shutil.rmtree(ROOT, ignore_errors=True)
print(f"BENCH_BATCH DONE idle_ms={res['idle'][0]:.0f} kick_ms={res['kick'][0]:.0f} close_ms={res['close'][0]:.0f} popen_ms={popen_ms:.0f}")

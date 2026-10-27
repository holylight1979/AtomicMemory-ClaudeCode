"""gate0_run.py — 005 第 0 步總驗收串跑：建環境（--cards-from 004 卡集清單）→ 換卡快照 → dry-run → 題 C′ → 補題 qs3-notify（--named）四回合；
每題跑完把資料根 Logs/、workflow/ 整包收進 _fm/，再跑 fm_gates 計數。比照 004 的 gate0_5_run.py，只改跑名、加建環境與環境變數清理。
環境：清掉指揮 session 帶的 CLAUDE_EFFORT／入口／訊息通道／session id 等，明設 CLAUDE_EFFORT=xhigh（調度 10-27 裁）、WG_V6=1。
怎麼跑：python -X utf8 gate0_run.py [--sup-only]
尾行 GATE0_005 DONE c_tail=… sup_tail=…；建環境沒過印 GATE0_005 FAIL reason=…
"""
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

KIT_DIR = Path(__file__).resolve().parent / "kit"
RES = Path("C:/Users/holylight/.claude/workflow/inbox/wave2-kit/results")
SNAP = RES / "2026-10-23-FM-cards-snapshot"
CARDS = SNAP / "fm-cards.json"
DEST = Path("C:/w4")
C_RUN = "2026-10-27-005-GATE0"
S_RUN = "2026-10-27-005-GATE0-SUP"
DROP_ENV = ("CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_MESSAGING_SOCKET", "CLAUDE_CODE_MESSAGING_TOKEN", "CLAUDE_CODE_SESSION_ID",
            "CLAUDE_JOB_DIR", "CLAUDE_PID", "CLAUDE_CODE_CHILD_SESSION", "CLAUDE_CODE_SESSION_ATTENDED", "CLAUDE_EFFORT",
            "CLAUDE_COMPANION_JUDGE")
for k in DROP_ENV:
    os.environ.pop(k, None)
os.environ["CLAUDE_EFFORT"] = "xhigh"
os.environ["WG_V6"] = "1"


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def py(args, out):
    r = subprocess.run([sys.executable, "-X", "utf8", *args], cwd=str(KIT_DIR), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(r.stdout + ("\n--- stderr ---\n" + r.stderr if r.stderr.strip() else ""), encoding="utf-8")
    lines = [x for x in r.stdout.strip().splitlines() if x.strip()]
    return r.returncode, (lines[-1] if lines else "")


def harvest(root_name, run):
    fm = RES / run / "_fm"
    for sub in ("Logs", "workflow"):
        src = DEST / root_name / sub
        if src.is_dir():
            shutil.copytree(src, fm / f"root-{sub}", dirs_exist_ok=True)
    pend = sorted(p.name for p in (DEST / root_name / "workflow").glob("*.pending"))
    log(f"{run}：收資料根 {root_name}（跑完留著的待併帳檔 {len(pend)} 個：{pend[:5]}）")


def rm_tree(p):
    if p.exists():
        shutil.rmtree(p, onexc=lambda fn, q, e: (os.chmod(q, 0o666), fn(q)))


fm0 = RES / C_RUN / "_fm"
c_tail = "略過（--sup-only）"
if "--sup-only" not in sys.argv:
    for stale in (DEST / "qs3-notify", DEST / "qs3-notify-root", DEST / "qn4-release-guide", DEST / "qn4-release-guide-root"):
        rm_tree(stale)
    rc, tail = py(["w2_build_env.py", "--dest", str(DEST), "--selfcheck", "--cards-from", str(CARDS)], fm0 / "build.log")
    log(f"建環境：{tail}")
    if tail != "W2_ENV_BUILD_CHECK PASS":
        print(f"GATE0_005 FAIL reason=建環境 {tail}")
        sys.exit(1)
    rc, tail = py(["fm_snap.py", "apply", "--snap", str(SNAP), "--cards", str(CARDS), "--dest", str(DEST)], fm0 / "snap.log")
    log(f"換卡快照：{tail}")
    if tail != "FM_SNAP_CHECK PASS":
        print(f"GATE0_005 FAIL reason=換卡快照 {tail}")
        sys.exit(1)
    rc, tail = py(["w2_run_all.py", "--dry-run"], fm0 / "dryrun.log")
    log(f"dry-run：{tail}")
    # 只放行一條：複本 w2_run_all.py 改了 claude.exe 路徑（2.1.304→2.1.310，這台只剩新版），跟 kit 正本逐位元組不同是預期的
    fails = [x.strip() for x in (fm0 / "dryrun.log").read_text(encoding="utf-8").splitlines() if x.lstrip().startswith("FAIL")]
    other = [x for x in fails if "w2_run_all.py 跟 kit" not in x]
    if tail != "W2_RUN_ALL_CHECK PASS" and other:
        print(f"GATE0_005 FAIL reason=dry-run {other}")
        sys.exit(1)
    log(f"dry-run 放行（唯一 FAIL 是 w2_run_all.py 複本改了 claude.exe 路徑：{fails}）")
    log("題 C′ 開跑")
    rc, c_tail = py(["w2_run_all.py", "--only", "C", "--date", C_RUN], fm0 / "run.log")
    log(f"題 C′ 完：rc={rc} {c_tail}")
    harvest("qc2-orders-root", C_RUN)
    rc, g_tail = py(["fm_gates.py", "--run", C_RUN, "--md", str(fm0 / "gates.md"), "--json", str(fm0 / "gates.json")],
                    fm0 / "gates.log")
    log(f"題 C′ 計數：{g_tail}")

log("補題建置")
rm_tree(DEST / "qs3-notify")
rm_tree(DEST / "qs3-notify-root")
rc, b_tail = py(["fm_sup.py", "build", "--dest", str(DEST)], RES / S_RUN / "_fm" / "build.log")
log(f"補題建置：rc={rc} {b_tail}")
s_tail = "沒跑（建置失敗）"
if rc == 0:
    log("補題開跑")
    rc, s_tail = py(["fm_sup.py", "run", "--date", S_RUN, "--dest", str(DEST), "--named"], RES / S_RUN / "_fm" / "run.log")
    log(f"補題完：rc={rc} {s_tail}")
    harvest("qs3-notify-root", S_RUN)
    rc, g2_tail = py(["fm_gates.py", "--run", S_RUN, "--md", str(RES / S_RUN / "_fm" / "gates.md"),
                      "--json", str(RES / S_RUN / "_fm" / "gates.json")], RES / S_RUN / "_fm" / "gates.log")
    log(f"補題計數：{g2_tail}")
print(f"GATE0_005 DONE c_tail={c_tail!r} sup_tail={s_tail!r}")

"""run_ct.py — 題 B′ 第一回合無頭實跑一次，hook 與 MCP 跑 closing-time worktree 的程式碼（不是 live）。

做什麼：
  1. 從 C:/w4/closing-time 建好的 qb2-sales／qb2-sales-root（w2_build_env.py --dest C:\\w4\\closing-time）各複製一份到
     C:/w4/closing-time/<run>/（種子不動）。
  2. settings：照 live ~/.claude/settings.json 抄（事件、matcher、timeout 同 004），hook 路徑換成 worktree 的 hooks/，
     拿掉 user-init.sh（寫 live USER.md）與 ensure-mcp.py（合併 ~/.claude.json）、statusLine；`--setting-sources project,local`
     不載使用者層（否則 live hook 會一起跑）。MCP：`--strict-mcp-config --mcp-config` 只掛 worktree 的 workflow-guardian server.js。
  3. claude -p 送 004 R1 同一句（從 R1 的回合 JSON 讀），WG_CLAUDE_DIR／WG_TEST_LOGS_DIR 指 <run> 的資料根、WG_V6=1，
     入口讓 claude 自設 sdk-cli（同 004 題 B′）。
  4. 收：回合 JSON（_meta id=first、起訖）、這個 session 的 transcript（從 live projects 搬出、刪掉自己的 slug 目錄）、資料根 Logs、
     _overview-hub.log、_fm/measure.json，排成 first_turn_breakdown.py 讀得懂的 results/<run>/B-1/ 版面。
怎麼跑：python -X utf8 run_ct.py <run 名，例 2026-10-27-CT-1>
尾行：RUN_CT DONE run=<名> rc=<碼> sid=<session> wall_s=<秒> slug_removed=<0|1>
"""
import json
import os
import shutil
import stat
import subprocess
import sys
from datetime import datetime
from pathlib import Path

TREE = Path(r"C:/Users/holylight/.claude-wt/closing-time")
SEED = Path(r"C:/w4/closing-time")
TMP = Path(r"C:/Users/holylight/.claude/jobs/778a48b3/tmp")
LIVE = Path.home() / ".claude"
R1_TURN = LIVE / "workflow/inbox/wave2-kit/results/2026-10-23-CCon-R1/B-1/turns/B-1-t1.json"
CLAUDE = r"C:\Users\holylight\.vscode\extensions\anthropic.claude-code-2.1.310-win32-x64\resources\native-binary\claude.exe"
PYW = r"C:\Users\holylight\AppData\Local\Python\bin\pythonw.exe"
NODE = r"C:\Program Files\nodejs\node.exe"
DROP_ENV = ("CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_MESSAGING_SOCKET", "CLAUDE_CODE_MESSAGING_TOKEN", "CLAUDE_CODE_SESSION_ID",
            "CLAUDE_JOB_DIR", "CLAUDE_PID", "CLAUDE_CODE_CHILD_SESSION", "CLAUDE_CODE_SESSION_ATTENDED", "CLAUDE_EFFORT",
            "CLAUDE_COMPANION_JUDGE")


def _rm(p: Path) -> None:
    def onerr(fn, path, _):
        os.chmod(path, stat.S_IWRITE)
        fn(path)
    if p.exists():
        shutil.rmtree(p, onerror=onerr)


def settings_file(out: Path) -> Path:
    live = json.loads((LIVE / "settings.json").read_text(encoding="utf-8"))
    live.pop("statusLine", None)
    hooks_dir = (TREE / "hooks").as_posix()
    for ev, groups in list(live["hooks"].items()):
        keep = []
        for g in groups:
            hs = [h for h in g["hooks"] if "user-init.sh" not in h.get("command", "") and "ensure-mcp.py" not in h.get("command", "")]
            for h in hs:
                h["command"] = (h["command"].replace("pathlib.Path.home()/'.claude/hooks/", f"pathlib.Path(r'{hooks_dir}')/'")
                                .replace("$HOME/.claude/hooks/", f"{hooks_dir}/"))
                assert ".claude/hooks" not in h["command"].replace(".claude-wt", ""), h["command"]
            if hs:
                keep.append({**g, "hooks": hs})
        live["hooks"][ev] = keep
    p = out / "settings-ct.json"
    p.write_text(json.dumps(live, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def mcp_file(out: Path, root: Path) -> Path:
    mcp = {"mcpServers": {"workflow-guardian": {"type": "stdio", "command": PYW, "args": [
        str(TREE / "hooks" / "run-hidden.py"), NODE, str(TREE / "tools" / "workflow-guardian-mcp" / "server.js")],
        "env": {"WG_CLAUDE_DIR": str(root)}}}}
    p = out / "mcp-ct.json"
    p.write_text(json.dumps(mcp, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def main(run: str) -> int:
    base = SEED / run.rsplit("-", 1)[-1]
    proj, root = base / "qb2-sales", base / "qb2-sales-root"
    _rm(base)
    shutil.copytree(SEED / "qb2-sales", proj)
    shutil.copytree(SEED / "qb2-sales-root", root)
    out = TMP / "results" / run
    _rm(out)
    seg = out / "B-1"
    for d in ("turns", "transcript", "logs", "workflow"):
        (seg / d).mkdir(parents=True)
    (out / "_fm").mkdir()
    prompt = json.loads(R1_TURN.read_text(encoding="utf-8"))["_meta"]["prompt"]
    env = {k: v for k, v in os.environ.items() if k not in DROP_ENV}
    env.update(WG_CLAUDE_DIR=str(root), WG_TEST_LOGS_DIR=str(root / "Logs"), WG_V6="1")
    cmd = [CLAUDE, "-p", prompt, "--permission-mode", "bypassPermissions", "--output-format", "json", "--max-turns", "120",
           "--setting-sources", "project,local", "--settings", str(settings_file(out)),
           "--strict-mcp-config", "--mcp-config", str(mcp_file(out, root))]
    projects = LIVE / "projects"
    before = {p.name for p in projects.iterdir()}
    started = datetime.now()
    r = subprocess.run(cmd, cwd=str(proj), env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=45 * 60)
    ended = datetime.now()
    (out / "stdout.txt").write_text(r.stdout, encoding="utf-8")
    (out / "stderr.txt").write_text(r.stderr, encoding="utf-8")
    lines = [ln for ln in r.stdout.strip().splitlines() if ln.strip().startswith("{")]
    data = json.loads(lines[-1]) if lines else {}
    data["_meta"] = {"prompt": prompt, "entrypoint": "sdk-cli（claude 自設）", "hooks": "worktree closing-time",
                     "started": started.isoformat(timespec="seconds"), "ended": ended.isoformat(timespec="seconds"),
                     "rc": r.returncode, "stderr_tail": r.stderr[-1500:], "q": "B", "seg": "1", "n": 1, "id": "first"}
    (seg / "turns" / "B-1-t1.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    sid = str(data.get("session_id") or "")
    slug_name = "C--" + str(proj)[3:].replace("\\", "-").replace("/", "-")      # Claude Code 的專案資料夾名：非英數換 -
    new = sorted({p.name for p in projects.iterdir()} - before)
    removed = 0
    slug = projects / slug_name
    if slug.is_dir() and slug_name in new:
        for f in slug.rglob("*.jsonl"):
            dst = seg / "transcript" / f.relative_to(slug)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), dst)
        _rm(slug)
        removed = 1
    shutil.copytree(root / "Logs", seg / "logs" / "_this_session", dirs_exist_ok=True)
    for name in ("_overview-hub.log",):
        if (root / "workflow" / name).exists():
            shutil.copyfile(root / "workflow" / name, seg / "workflow" / name)
    for sub in ("reading-path", "second-opinion"):
        if (root / "workflow" / sub).is_dir():
            shutil.copytree(root / "workflow" / sub, seg / "workflow" / sub, dirs_exist_ok=True)
    for st in root.glob("workflow/state-*.json"):
        shutil.copyfile(st, seg / "workflow" / st.name)
    wall = (ended - started).total_seconds()
    (out / "_fm" / "measure.json").write_text(json.dumps({"segments": {"B-1": {"turns": [{"id": "first", "wall_s": wall}]}}}),
                                              encoding="utf-8")
    print(f"new_slugs={new}")
    print(f"RUN_CT DONE run={run} rc={r.returncode} sid={sid} wall_s={wall:.0f} slug_removed={removed}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))

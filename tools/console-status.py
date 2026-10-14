#!/usr/bin/env python3
"""console-status.py：總控台一眼看全軌現況（唯讀，不改任何檔、不動版控狀態）。

做什麼：在目前資料夾所屬的 git repo 印四段——
  【worktree】`git worktree list` 原樣；
  【未推】origin/main..main 的 commit 數（沒有 origin/main 就印訊號、記 na）；
  【各軌最新來信】信箱下每個 from-track-* 資料夾最新一封（依修改時間），信裡有「我在等：…」就跟著印；
  【verify log】信箱 _console/ 下 verify*.log 最近 N 份，各印每個 exit 鍵（exit=、exit1=、smoke_exit=…）的最後值；
               都沒有才印「無 exit 行」＋最後一行 pytest 總結。

怎麼跑：
  python ~/.claude/tools/console-status.py                       # 信箱預設 <repo 根>/workflow/inbox
  python ~/.claude/tools/console-status.py --inbox D:/x/inbox --logs 5
尾行：`CONSOLE_STATUS DONE worktrees=<n|na> unpushed=<n|na> tracks=<n> logs=<n>`
exit：0 完成（信箱不存在也算，會印「信箱不存在」）；2 不在 git repo 裡或叫不到 git。完整參數以 --help 為準。
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
WAITING_RE = re.compile(r"我在等[:：]")
PYTEST_SUMMARY_RE = re.compile(r"\d+ (passed|failed)")
EXIT_RE = re.compile(r"^(\w*exit\w*)=(-?\d+)$")


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    """跑 git，輸出以 bytes 收再 UTF-8 解碼（中文路徑與訊息不因系統碼頁亂碼）。"""
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, creationflags=NO_WINDOW)
    r.stdout = r.stdout.decode("utf-8", "replace")
    r.stderr = r.stderr.decode("utf-8", "replace")
    return r


def stamp(p: Path) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(p.stat().st_mtime))


def newest_first(paths) -> list:
    return sorted(paths, key=lambda p: (p.stat().st_mtime, p.name), reverse=True)


def read_lines(p: Path) -> list:
    return p.read_text(encoding="utf-8", errors="replace").splitlines()


def show_worktrees(repo: Path) -> str:
    rows = [line for line in git(repo, "worktree", "list").stdout.splitlines() if line.strip()]
    print(f"【worktree】{len(rows)} 棵")
    for line in rows:
        print(f"  {line}")
    return str(len(rows))


def show_unpushed(repo: Path) -> str:
    if git(repo, "rev-parse", "--verify", "-q", "origin/main").returncode != 0:
        print("【未推】沒有 origin/main，算不出未推數")
        return "na"
    r = git(repo, "rev-list", "--count", "origin/main..main")
    if r.returncode != 0:
        print(f"【未推】算不出未推數：{r.stderr.strip()}")
        return "na"
    n = r.stdout.strip()
    print(f"【未推】origin/main..main = {n}")
    return n


def show_letters(inbox: Path) -> int:
    print(f"【各軌最新來信】信箱 {inbox}")
    tracks = sorted(d for d in inbox.glob("from-track-*") if d.is_dir())
    for d in tracks:
        track = d.name[len("from-"):]
        letters = newest_first(f for f in d.iterdir() if f.is_file())
        if not letters:
            print(f"  {track}  （還沒有來信）")
            continue
        latest = letters[0]
        print(f"  {track}  {latest.name}  {stamp(latest)}")
        waiting = [line.strip() for line in read_lines(latest) if WAITING_RE.search(line)]
        if waiting:
            print(f"    {waiting[-1]}")
    return len(tracks)


def last_result(log: Path) -> str:
    """每個 exit 鍵（exit=、exit1=、smoke_exit=…）取最後值；都沒有才退回最後一行 pytest 總結。"""
    lines = [line.strip() for line in read_lines(log)]
    exits = {}
    for line in lines:
        m = EXIT_RE.match(line)
        if m:
            exits[m.group(1)] = m.group(2)
    if exits:
        return " ".join(f"{k}={v}" for k, v in exits.items())
    summaries = [line for line in lines if PYTEST_SUMMARY_RE.search(line)]
    return "無 exit 行" + (f"｜{summaries[-1]}" if summaries else "")


def show_logs(inbox: Path, limit: int) -> int:
    logs = newest_first((inbox / "_console").glob("verify*.log"))
    shown = logs[:limit]
    print(f"【verify log】共 {len(logs)} 份，列最近 {len(shown)} 份")
    for log in shown:
        print(f"  {log.name}  {stamp(log)}  {last_result(log)}")
    return len(shown)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inbox", help="信箱資料夾（預設 <repo 根>/workflow/inbox）")
    ap.add_argument("--logs", type=int, default=10, help="verify log 列最近幾份（預設 10）")
    args = ap.parse_args(argv)

    try:
        top = git(Path.cwd(), "rev-parse", "--show-toplevel")
        problem = None if top.returncode == 0 else f"{Path.cwd()} 不在 git repo 裡"
    except OSError as e:
        problem = f"叫不到 git：{e}"
    if problem:
        print(f"[console-status] {problem}", file=sys.stderr)
        print("CONSOLE_STATUS DONE worktrees=na unpushed=na tracks=0 logs=0")
        return 2

    repo = Path(top.stdout.strip())
    inbox = Path(args.inbox) if args.inbox else repo / "workflow" / "inbox"
    print(f"== 總控台現況：{repo} ==")
    worktrees = show_worktrees(repo)
    unpushed = show_unpushed(repo)
    tracks = logs = 0
    if inbox.is_dir():
        tracks = show_letters(inbox)
        logs = show_logs(inbox, args.logs)
    else:
        print(f"信箱不存在：{inbox}（來信與 verify log 兩段略過）")
    print(f"CONSOLE_STATUS DONE worktrees={worktrees} unpushed={unpushed} tracks={tracks} logs={logs}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

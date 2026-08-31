#!/usr/bin/env python3
"""publish-remotes.py — 把 main 推到兩個遠端，Install.md 的版控庫網址各留各的。

為什麼不是 origin 掛兩個 push URL：同一顆 commit 推到兩邊內容必然相同，
Install.md 就得同時列 GitHub 與公司 GitLab 網址。使用者要「各自只留自己的網址」，
所以每個遠端各維護一條發布分支 publish/<name>（= main 合併進來 + 一顆網址替換 commit），
只往前長、永不 force：GitLab main 有 pre-receive force 保護，non-ff 會被擋。

流程（每個遠端）：
  1. 在 TEMP 建暫時 worktree checkout publish/<name>（不存在就從 main 開）
  2. git merge main（衝突只可能在 Install.md 網址區塊 → 取 main 版再重套替換）
  3. 把 Install.md 的 <!-- repo-url --> … <!-- /repo-url --> 區塊改成只剩該遠端的網址
  4. 有變更就 commit，然後 push publish/<name>:main
  5. 移除暫時 worktree
主工作樹全程不動，可在 SessionEnd 背景跑。

用法：
  python tools/publish-remotes.py            # 推兩邊
  python tools/publish-remotes.py --only github
  python tools/publish-remotes.py --dry-run  # 只做 merge + 替換，不 push（worktree 保留供檢視）
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude"
INSTALL_MD = "Install.md"
BLOCK_RE = re.compile(r"<!-- repo-url -->.*?<!-- /repo-url -->", re.S)

# 遠端名稱 → (git remote 名, Install.md 區塊內容)
TARGETS = {
    "github": (
        "origin",
        "* GitHub：`https://github.com/holylight1979/AtomicMemory-ClaudeCode.git`",
    ),
    "gitlab": (
        "gitlab",
        "* GitLab（公司內網）：`https://gitlab.uj.com.tw/holylight/ClaudeCode-AtomMemory.git`",
    ),
}


def git(*args: str, cwd: Path = CLAUDE_DIR, check: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失敗：{(r.stderr or r.stdout).strip()[:400]}")
    return r


def branch_exists(name: str) -> bool:
    return git("rev-parse", "--verify", "--quiet", f"refs/heads/{name}", check=False).returncode == 0


def rewrite_block(path: Path, line: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if not BLOCK_RE.search(text):
        raise RuntimeError(f"{path.name} 缺 <!-- repo-url --> 區塊標記，不敢替換")
    new = BLOCK_RE.sub(f"<!-- repo-url -->\n{line}\n<!-- /repo-url -->", text)
    if new == text:
        return False
    path.write_text(new, encoding="utf-8", newline="\n")
    return True


def publish(name: str, dry_run: bool, quiet: bool) -> None:
    remote, line = TARGETS[name]
    branch = f"publish/{name}"
    log = (lambda *_: None) if quiet else (lambda *a: print(f"[{name}]", *a))

    if git("remote", "get-url", remote, check=False).returncode != 0:
        raise RuntimeError(f"remote `{remote}` 不存在；先 git remote add {remote} <url>")

    wt = Path(tempfile.mkdtemp(prefix=f"publish-{name}-"))
    try:
        if branch_exists(branch):
            git("worktree", "add", "--quiet", str(wt), branch)
        else:
            git("worktree", "add", "--quiet", "-b", branch, str(wt), "main")
            log(f"新建 {branch}（自 main）")

        m = git("merge", "--no-edit", "main", cwd=wt, check=False)
        if m.returncode != 0:
            # 衝突只允許發生在 Install.md（網址區塊 vs main 的改動）：取 main 版，替換後一起提交
            conflicted = git("diff", "--name-only", "--diff-filter=U", cwd=wt).stdout.split()
            if conflicted != [INSTALL_MD]:
                git("merge", "--abort", cwd=wt, check=False)
                raise RuntimeError(f"merge main 衝突不只 Install.md：{conflicted}")
            git("checkout", "--theirs", "--", INSTALL_MD, cwd=wt)
            rewrite_block(wt / INSTALL_MD, line)
            git("add", INSTALL_MD, cwd=wt)
            git("commit", "--no-edit", "-m", f"merge main（Install.md 取 main 版並重套 {name} 網址）", cwd=wt)
            log("merge main：Install.md 衝突已以 main 版 + 網址替換解決")
        else:
            log("merge main：ok")

        if rewrite_block(wt / INSTALL_MD, line):
            git("add", INSTALL_MD, cwd=wt)
            git("commit", "-m", f"docs(install): Install.md 只留 {name} 版控庫網址", cwd=wt)
            log("Install.md 網址區塊已替換並提交")
        else:
            log("Install.md 網址區塊已是目標內容")

        if dry_run:
            log(f"dry-run：不 push；worktree 保留在 {wt}")
            return
        p = git("push", remote, f"{branch}:main", cwd=wt)
        log("push", remote, "main:", (p.stderr or p.stdout).strip().splitlines()[-1] if (p.stderr or p.stdout).strip() else "ok")
    finally:
        if not dry_run:
            git("worktree", "remove", "--force", str(wt), check=False)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", choices=sorted(TARGETS), help="只推一個遠端")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() != "main":
        print("請在 main 分支執行（發布分支由本腳本自管）", file=sys.stderr)
        return 2
    names = [args.only] if args.only else list(TARGETS)
    failed = 0
    for n in names:
        try:
            publish(n, args.dry_run, args.quiet)
        except RuntimeError as e:
            failed += 1
            print(f"[{n}] 失敗：{e}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

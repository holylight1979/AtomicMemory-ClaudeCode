#!/usr/bin/env python3
"""replay-guard.py — 回放實驗的洩題守門（跑前檢查提示詞與材料，跑後掃執行紀錄）。

怎麼跑：
  跑前  python ~/.claude/tools/replay-guard.py pre  --prompt <提示詞檔> --sandbox <暫存根目錄> [--sealed <封存答案檔>]
  跑後  python ~/.claude/tools/replay-guard.py post --log <codex 的 stderr 紀錄檔> --sandbox <暫存根目錄>
  結果一律印一整行哨兵：REPLAY_GUARD_CHECK PASS 或 REPLAY_GUARD_CHECK FAIL（exit 0／1）。

它擋的是三方守門討論裡實際發生過的三種洩題：
  1. 出題者把答案寫進「回覆」或提示詞（跑前：提示詞不得含封存答案檔裡的關鍵字）。
  2. 材料指到真工作副本，審查者讀到修正後的文件或記憶卡片（跑前：提示詞不得含暫存目錄以外的絕對路徑；跑後：紀錄不得出現暫存目錄以外的路徑、信箱、記憶目錄、svn 查詢）。
  3. Codex 自己的持久記憶記了案例（跑前：~/.codex/memories 不得含封存關鍵字）。
提示詞本身「催它做被測的行為」這種洩題程式擋不了，見 atom「回放實驗洩題三型」的未解部分。
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

CODEX_MEMORY = Path.home() / ".codex" / "memories"
# 跑後紀錄裡只要出現這些就算讀出界
FORBIDDEN_IN_LOG = [
    r"[/\\]inbox[/\\]",
    r"\.claude[/\\]memory",
    r"_AIDocs[/\\]_atoms",
    r"\bsvn\s+(?:log|cat|diff|info|blame)\b",
    r"\bgit\s+(?:log|show|diff|blame)\b",
]
ABS_PATH = re.compile(r"[A-Za-z]:[/\\][^\s\"'`)\]]+")


def sentinel(ok: bool, reasons: list[str]) -> int:
    for r in reasons:
        print("  - " + r)
    print("REPLAY_GUARD_CHECK " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def load_keywords(sealed: Path | None) -> list[str]:
    """封存答案檔每行一個關鍵字；空行與 # 開頭略過。"""
    if sealed is None:
        return []
    words = []
    for line in sealed.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        words.append(s)
    return words


def norm(p: str) -> str:
    return p.replace("\\", "/").lower().rstrip("/")


def expand(p: str) -> str:
    """把紀錄裡的路徑變成可比對的長路徑：去掉雙反斜線跳脫、去掉 :行號、8.3 短名（HOLYLI~1）展開。"""
    p = p.replace("\\\\", "\\")
    p = re.sub(r":\d+$", "", p)
    try:
        return os.path.realpath(p)
    except OSError:
        return p


def paths_outside(text: str, sandbox: Path) -> list[str]:
    root = norm(os.path.realpath(str(sandbox)))
    found = []
    for m in ABS_PATH.finditer(text):
        p = norm(expand(m.group(0)))
        if p.startswith(root):
            continue
        if p.startswith(norm(str(Path.home())) + "/.codex"):
            continue  # codex 自己的設定檔
        if p.startswith(norm(str(Path.home())) + "/appdata"):
            continue  # 工具安裝路徑
        if re.match(r"^[a-z]:/program", p) or "/windows/" in p:
            continue  # 工具安裝路徑（紀錄裡 "Program Files" 會在空白處被截成 "C:\Program"）
        found.append(m.group(0))
    return sorted(set(found))


def cmd_pre(args: argparse.Namespace) -> int:
    reasons: list[str] = []
    prompt = Path(args.prompt).read_text(encoding="utf-8")
    sandbox = Path(args.sandbox)
    words = load_keywords(Path(args.sealed) if args.sealed else None)

    hits = [w for w in words if w.lower() in prompt.lower()]
    if hits:
        reasons.append("提示詞含封存答案關鍵字（出題者洩題）：" + "、".join(hits))

    outside = paths_outside(prompt, sandbox)
    if outside:
        reasons.append("提示詞指到暫存目錄以外的路徑：" + "、".join(outside[:5]))

    if words and CODEX_MEMORY.exists():
        mem_hits = []
        for f in CODEX_MEMORY.rglob("*.md"):
            t = f.read_text(encoding="utf-8", errors="replace").lower()
            for w in words:
                if w.lower() in t:
                    mem_hits.append(f"{f.name}:{w}")
        if mem_hits:
            reasons.append("Codex 持久記憶含封存關鍵字：" + "、".join(mem_hits[:5]))

    return sentinel(not reasons, reasons)


def command_lines(log: str) -> str:
    """只取紀錄裡「實際執行的指令」那些行；模型引述文件內容的行不算讀檔。
    codex exec 的 stderr 把每個指令印成 `"...pwsh.exe" -Command "..." in <cwd>`。"""
    picked = []
    for line in log.splitlines():
        if "-Command" in line or "exec_command" in line or line.startswith("$ "):
            picked.append(line)
    return "\n".join(picked)


def cmd_post(args: argparse.Namespace) -> int:
    reasons: list[str] = []
    log = Path(args.log).read_text(encoding="utf-8", errors="replace")
    sandbox = Path(args.sandbox)
    cmds = command_lines(log)
    if not cmds:
        reasons.append("紀錄裡找不到任何指令行（格式變了？），無法判定")

    for pat in FORBIDDEN_IN_LOG:
        if re.search(pat, cmds, flags=re.IGNORECASE):
            reasons.append("指令命中禁區樣式：" + pat)

    outside = paths_outside(cmds, sandbox)
    if outside:
        reasons.append("紀錄出現暫存目錄以外的路徑：" + "、".join(outside[:8]))

    return sentinel(not reasons, reasons)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    pre = sub.add_parser("pre", help="跑前：檢查提示詞、材料路徑、Codex 記憶")
    pre.add_argument("--prompt", required=True)
    pre.add_argument("--sandbox", required=True)
    pre.add_argument("--sealed", help="封存答案關鍵字檔，每行一個")
    post = sub.add_parser("post", help="跑後：掃 codex stderr 紀錄有沒有讀出界")
    post.add_argument("--log", required=True)
    post.add_argument("--sandbox", required=True)
    args = ap.parse_args()
    if args.cmd == "pre":
        return cmd_pre(args)
    return cmd_post(args)


if __name__ == "__main__":
    sys.exit(main())

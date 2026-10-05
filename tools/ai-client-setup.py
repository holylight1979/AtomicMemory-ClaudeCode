#!/usr/bin/env python3
"""ai-client-setup.py — 其他 AI 客戶端（Codex／Gemini CLI／Antigravity）輕量接上公司記憶：只註冊 workflow-guardian MCP，不裝 hooks。

做什麼：給不用 Claude Code 的人（企劃／美術）。四步，全部可重跑：
  1. 檢查 Node（MCP server 用 node 跑；Python 就是跑本腳本的這一個）
  2. 更新 ~/.claude（git pull --ff-only；工作樹有改動或拉不下來就略過並說明）
  3. 接上公司層記憶（org-memory.py --join；已接上就跳過）
  4. 把 workflow-guardian MCP 寫進偵測到的客戶端設定：
     Codex → ~/.codex/config.toml；Gemini CLI → ~/.gemini/settings.json；
     Antigravity → ~/.gemini/config/mcp_config.json
     已註冊就不動；偵測不到客戶端就印出片段讓人自己貼
裝完重開該 AI，用講的：「查公司記憶：<問題>」（memory_search）、「把這條記到公司層」（atom_write scope=org）。
沒有 hooks 就沒有「每句話自動帶入記憶」，要主動說「查記憶」。網頁版 AI 接不到本機工具，不在本腳本範圍。
怎麼跑：
  python ~/.claude/tools/ai-client-setup.py            # 全自動
  python ~/.claude/tools/ai-client-setup.py --dry-run  # 只說會做什麼，不寫任何檔
  完整參數以 --help 為準。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

CLAUDE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CLAUDE_DIR / "hooks"))

import wg_core  # noqa: E402

SERVER_NAME = "workflow-guardian"
SERVER_JS = CLAUDE_DIR / "tools" / "workflow-guardian-mcp" / "server.js"
ORG_MEMORY = CLAUDE_DIR / "tools" / "org-memory.py"
CODEX_CONFIG = Path.home() / ".codex" / "config.toml"
GEMINI_SETTINGS = Path.home() / ".gemini" / "settings.json"
ANTIGRAVITY_DIR = Path.home() / ".gemini" / "antigravity"
ANTIGRAVITY_CONFIG = Path.home() / ".gemini" / "config" / "mcp_config.json"
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def find_node() -> Optional[str]:
    found = shutil.which("node")
    if found:
        return found
    for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
        exe = Path(base) / "nodejs" / "node.exe" if base else None
        if exe and exe.exists():
            return str(exe)
    return None


def _write_lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def server_entry(node: str) -> Dict[str, object]:
    """MCP 註冊內容；WG_PYTHON 指定 server 內部要用的 python（免得它在別人機器上猜錯直譯器）。"""
    return {"command": node, "args": [str(SERVER_JS)], "env": {"WG_PYTHON": sys.executable}}


def codex_block(entry: Dict[str, object]) -> str:
    """TOML 區塊。JSON 字串的跳脫規則是 TOML 基本字串的子集，直接借用 json.dumps。"""
    q = lambda s: json.dumps(str(s), ensure_ascii=False)  # noqa: E731
    args = ", ".join(q(a) for a in entry["args"])  # type: ignore[union-attr]
    env = "".join(f"{k} = {q(v)}\n" for k, v in entry["env"].items())  # type: ignore[union-attr]
    return (f"[mcp_servers.{SERVER_NAME}]\ncommand = {q(entry['command'])}\nargs = [ {args} ]\n\n"
            f"[mcp_servers.{SERVER_NAME}.env]\n{env}")


def register_codex(path: Path, entry: Dict[str, object], *, dry_run: bool) -> str:
    """缺 [mcp_servers.workflow-guardian] 才在檔尾補一段；既有內容一個字不動。"""
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if f"[mcp_servers.{SERVER_NAME}]" in text:
        return f"Codex：已註冊，不動（{path}）"
    if dry_run:
        return f"[dry-run] Codex：會在 {path} 檔尾加上 {SERVER_NAME}"
    sep = "" if not text else ("\n" if text.endswith("\n") else "\n\n")
    _write_lf(path, text + sep + codex_block(entry))
    return f"Codex：已寫入 {path}"


def register_json(label: str, path: Path, entry: Dict[str, object], *, dry_run: bool) -> str:
    """JSON 設定檔（Gemini CLI settings.json、Antigravity mcp_config.json）的 mcpServers 缺 workflow-guardian 才加；
    其他鍵原樣保留。壞檔不碰，回「失敗」。"""
    data: Dict[str, object] = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            return f"失敗 {label}：{path} 不是合法 JSON（{e}），沒有動它；請手動貼下面的片段"
        if not isinstance(data, dict):
            return f"失敗 {label}：{path} 最外層不是物件，沒有動它；請手動貼下面的片段"
    servers = data.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        return f"失敗 {label}：{path} 的 mcpServers 不是物件，沒有動它；請手動貼下面的片段"
    if SERVER_NAME in servers:
        return f"{label}：已註冊，不動（{path}）"
    if dry_run:
        return f"[dry-run] {label}：會在 {path} 的 mcpServers 加上 {SERVER_NAME}"
    servers[SERVER_NAME] = entry
    _write_lf(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return f"{label}：已寫入 {path}"


def detect_clients() -> List[str]:
    """~/.gemini 是 Gemini CLI 與 Antigravity 共用的家：有 antigravity 子目錄算 Antigravity，
    Gemini CLI 則要執行檔在 PATH 上，或有 settings.json 且這台沒裝 Antigravity。"""
    found = []
    if CODEX_CONFIG.parent.is_dir() or shutil.which("codex"):
        found.append("codex")
    if shutil.which("gemini") or (GEMINI_SETTINGS.exists() and not ANTIGRAVITY_DIR.is_dir()):
        found.append("gemini")
    if ANTIGRAVITY_DIR.is_dir():
        found.append("antigravity")
    return found


def snippets(entry: Dict[str, object]) -> str:
    return ("—— Codex（~/.codex/config.toml）——\n" + codex_block(entry)
            + "\n—— Gemini CLI、Antigravity 與其他吃 mcpServers JSON 的客戶端 ——\n"
            + json.dumps({"mcpServers": {SERVER_NAME: entry}}, ensure_ascii=False, indent=2))


def update_repo(*, dry_run: bool) -> str:
    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(CLAUDE_DIR), *args], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=120, creationflags=_NO_WINDOW)
    try:
        dirty = git("status", "--porcelain", "--untracked-files=no")
        if dirty.returncode != 0:
            return f"略過更新：{CLAUDE_DIR} 不是 git 工作區"
        if dirty.stdout.strip():
            return "略過更新：~/.claude 有未提交的改動（不影響接上；要更新請先處理那些改動）"
        if dry_run:
            return "[dry-run] 會執行 git pull --ff-only 更新 ~/.claude"
        pull = git("pull", "--ff-only")
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"略過更新：git 執行不了（{e}）"
    if pull.returncode != 0:
        return f"略過更新：git pull 沒成功（{(pull.stderr or pull.stdout).strip()[-200:]}）"
    return "~/.claude 已是最新"


def join_org(*, dry_run: bool) -> str:
    """回一行訊息；「失敗」開頭表示公司層沒接上。"""
    root = wg_core.org_memory_root()
    if root is not None and (root / ".claude" / "memory").is_dir():
        return f"公司層記憶：已接上（{root}）"
    if dry_run:
        return "[dry-run] 會執行 org-memory.py --join 接上公司層記憶"
    r = subprocess.run([sys.executable, str(ORG_MEMORY), "--join"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", creationflags=_NO_WINDOW)
    if r.returncode != 0:
        return f"失敗 公司層記憶沒接上（exit {r.returncode}）：{(r.stderr or r.stdout).strip()[-300:]}"
    return f"公司層記憶：已接上（{wg_core.org_memory_root()}）"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="其他 AI 客戶端輕量接上公司記憶（只註冊 MCP，不裝 hooks）；完整參數以 --help 為準")
    ap.add_argument("--client", choices=["codex", "gemini", "antigravity"], action="append",
                    help="指定要註冊的客戶端（可重複）；省略＝自動偵測這台裝了哪些")
    ap.add_argument("--dry-run", action="store_true", help="只說會做什麼，不寫任何檔、不 pull、不 join")
    ap.add_argument("--no-update", action="store_true", help="不更新 ~/.claude")
    ap.add_argument("--no-join", action="store_true", help="不接公司層記憶（只註冊 MCP）")
    args = ap.parse_args()

    node = find_node()
    if not node:
        print("[ai-client-setup] 找不到 Node.js：請先安裝（https://nodejs.org 的 LTS 版），裝完重跑本腳本", file=sys.stderr)
        return 2
    entry = server_entry(node)
    msgs = [f"Node：{node}；Python：{sys.executable}"]
    if not args.no_update:
        msgs.append(update_repo(dry_run=args.dry_run))
    if not args.no_join:
        msgs.append(join_org(dry_run=args.dry_run))

    clients = args.client or detect_clients()
    if "codex" in clients:
        msgs.append(register_codex(CODEX_CONFIG, entry, dry_run=args.dry_run))
    if "gemini" in clients:
        msgs.append(register_json("Gemini", GEMINI_SETTINGS, entry, dry_run=args.dry_run))
    if "antigravity" in clients:
        msgs.append(register_json("Antigravity", ANTIGRAVITY_CONFIG, entry, dry_run=args.dry_run))

    print("[ai-client-setup] 結果：")
    for m in msgs:
        print(f"  - {m}")
    failed = [m for m in msgs if m.startswith("失敗")]
    if not clients:
        print("這台沒偵測到 Codex、Gemini CLI 或 Antigravity。用別的客戶端的話，把下面片段貼進它的 MCP 設定：")
    if not clients or failed:
        print(snippets(entry))
    if failed:
        print(f"[ai-client-setup] {len(failed)} 項失敗（見上）", file=sys.stderr)
        return 1
    if clients and not args.dry_run:
        print("下一步：重開你的 AI 工具，然後直接用講的——「查公司記憶：<問題>」或「把這條記到公司層：<內容>」")
    return 0


if __name__ == "__main__":
    sys.exit(main())

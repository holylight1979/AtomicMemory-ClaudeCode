#!/usr/bin/env python3
"""ensure-mcp.py — SessionStart hook: ensure MCP servers installed & configured.

Fast path (hook, <3s): check files exist → 缺或版本舊的 server 呼叫官方 `claude mcp add-json` 註冊（不手改 ~/.claude.json）。
Slow path (--install, detached): npm i -g missing packages + TTL version check.

Flow:
  1. Node.js 存在？ 否 → 寫 flag 檔供 Claude 提醒使用者，結束
  2. 讀 mcp-servers.template.json，逐一確認 JS entry point 是否在磁碟上
  3. 存在的 → 缺整塊才補 or template version 較新才覆寫，一律呼叫 claude CLI（覆寫先 remove 再 add）；
     CLI 找不到或失敗 → stderr 一行＋旗標檔，不退回手改 JSON
  4. 不存在的 → spawn detached installer（npm i -g），下次 session 才寫入 config
  5. TTL 7 天到期 → detached 執行 npm outdated + update

規則：MCP_ENTRY_HIDDEN_LAUNCHER（hooks/wg_release_rules.py）。
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────
CODE_DIR = Path(__file__).resolve().parents[1]   # 程式碼根：樣板與 MCP server 入口（{claude_dir}）在這棵樹
if str(CODE_DIR / "lib") not in sys.path:
    sys.path.insert(0, str(CODE_DIR / "lib"))
from project_root import claude_data_dir, claude_global_config  # noqa: E402

CLAUDE_DIR = claude_data_dir()   # 使用者資料根（WG_CLAUDE_DIR 或 ~/.claude）：workflow 旗標與版本快取
CLAUDE_JSON = claude_global_config()   # Claude Code 自己的 .claude.json：CLAUDE_CONFIG_DIR 或家目錄底下
TEMPLATE = CODE_DIR / "mcp-servers.template.json"
VERSION_CACHE = CLAUDE_DIR / "workflow" / "mcp-version-cache.json"
FLAG_NEEDS_NODE = CLAUDE_DIR / "workflow" / "mcp-needs-node.flag"
FLAG_CLI_FAILED = CLAUDE_DIR / "workflow" / "mcp-cli-failed.flag"
TEMPLATE_VERSION_FILE = CLAUDE_DIR / "workflow" / "mcp-template-version.json"   # 已套用的樣板版本（不放進 Claude Code 自己的 .claude.json）
CLI_TIMEOUT = 20
TTL_SECONDS = 7 * 86400  # 7 days

# Windows: 避免 npm.cmd 在 detached 父進程下另開 cmd 視窗
_NPM_FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


# ── Helpers ──────────────────────────────────────────────────────────────
def _log_err(source, exc):
    """Always-on 錯誤通報（standalone：不依賴 wg_core，寫 stderr）。"""
    try:
        sys.stderr.write(f"[{source}] {type(exc).__name__}: {exc}\n")
    except OSError:
        pass


def _find_node():
    """Return node.exe absolute path or None. Fast: check common paths first."""
    # Common Windows locations
    for base in [
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
    ]:
        p = Path(base) / "nodejs" / "node.exe"
        if p.exists():
            return str(p)
    # Fallback: where/which
    cmd = ["where", "node"] if sys.platform == "win32" else ["which", "node"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=3,
                           creationflags=_NPM_FLAGS)
        if r.returncode == 0:
            return r.stdout.strip().splitlines()[0]
    except Exception as e:
        _log_err("ensure_mcp:find_node", e)
        pass
    return None


def _npm_global_prefix():
    """Return npm global node_modules parent. On Windows, use APPDATA shortcut."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        p = Path(appdata) / "npm"
        if p.exists():
            return str(p)
    try:
        r = subprocess.run(["npm", "prefix", "-g"],
                           capture_output=True, text=True, timeout=5,
                           creationflags=_NPM_FLAGS)
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception as e:
        _log_err("ensure_mcp:npm_prefix", e)
        pass
    return None


def _load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")


def _stored_version(claude):
    """已套用的樣板版本：優先讀自己的小檔；沒有檔時沿用舊版寫在 .claude.json 的鍵（只讀，避免升級後整批重註冊）。"""
    v = _load_json(TEMPLATE_VERSION_FILE).get("version")
    return v if isinstance(v, int) else claude.get("_mcpTemplateVersion", 0)


def _find_claude():
    """claude CLI 絕對路徑或 None：PATH → 原生安裝位置 ~/.local/bin。"""
    found = shutil.which("claude")
    if found:
        return found
    p = Path.home() / ".local" / "bin" / ("claude.exe" if sys.platform == "win32" else "claude")
    return str(p) if p.exists() else None


def _apply_via_cli(to_apply):
    """逐一呼叫 `claude mcp [remove +] add-json <name> <json> --scope user`；全成功回 True。
    失敗（CLI 不在／非 0／逾時）→ stderr 一行＋旗標檔，不退回手改 JSON（避免與 Claude Code 同時寫檔）。"""
    cli = _find_claude()
    fail = None if cli else "找不到 claude CLI（PATH 與 ~/.local/bin 皆無）"
    for name, entry, overwrite in to_apply:
        if fail:
            break
        steps = ([["mcp", "remove", name, "--scope", "user"]] if overwrite else []) + [
            ["mcp", "add-json", name, json.dumps(entry, ensure_ascii=False), "--scope", "user"]]
        for step in steps:
            try:
                r = subprocess.run([cli] + step, capture_output=True, text=True, timeout=CLI_TIMEOUT,
                                   creationflags=_NPM_FLAGS)
            except Exception as e:
                fail = f"{name}: {type(e).__name__}: {e}"
                break
            if r.returncode != 0:
                fail = f"{name}: `{' '.join(step[:2])}` rc={r.returncode} {(r.stderr or r.stdout).strip()[:200]}"
                break
    if fail:
        msg = f"MCP 註冊失敗：{fail}。手動：claude mcp add-json <name> '<json>' --scope user"
        sys.stderr.write(f"[ensure_mcp:cli] {msg}\n")
        FLAG_CLI_FAILED.parent.mkdir(parents=True, exist_ok=True)
        FLAG_CLI_FAILED.write_text(msg + "\n", encoding="utf-8", newline="\n")
        return False
    FLAG_CLI_FAILED.unlink(missing_ok=True)
    return True


def _resolve_entry(server_def, npm_prefix):
    """Resolve JS entry point. Returns (absolute_path_str, exists_bool)."""
    if "entry_absolute" in server_def:
        p = Path(server_def["entry_absolute"].replace("{claude_dir}", str(CODE_DIR)))
        return str(p), p.exists()
    if npm_prefix and "entry_relative" in server_def:
        p = Path(npm_prefix) / "node_modules" / server_def["entry_relative"]
        return str(p), p.exists()
    return None, False


GUI_PYTHONW = Path.home() / "AppData" / "Local" / "Python" / "bin" / "pythonw.exe"   # 與 settings.json hook 同一支 GUI pythonw（路徑無版本號）
RUN_HIDDEN = CODE_DIR / "hooks" / "run-hidden.py"   # 隱窗外殼：claude.exe 直接起 node 會閃黑窗


def _hidden_launcher():
    """Windows 的隱窗外殼 [pythonw, run-hidden.py]；非 Windows 不需要回 None。
    Windows 缺任一檔 → stderr 一行、回 None（退回直接起 node，會閃黑窗）。"""
    if sys.platform != "win32":
        return None
    if GUI_PYTHONW.exists() and RUN_HIDDEN.exists():
        return [str(GUI_PYTHONW), str(RUN_HIDDEN)]
    sys.stderr.write(f"[ensure_mcp:hidden] 缺 {GUI_PYTHONW} 或 {RUN_HIDDEN}，MCP 改直接起 node（啟動會閃黑窗）\n")
    return None


def _build_server_entry(server_def, node_path, entry_path):
    """組一筆 mcpServers：Windows 是 `pythonw run-hidden.py node <js>`（與 live 註冊同形），其他平台 `node <js>`。"""
    entry = {}
    if server_def.get("type"):
        entry["type"] = server_def["type"]
    launcher = _hidden_launcher()
    if launcher:
        entry["command"], entry["args"] = launcher[0], launcher[1:] + [node_path, entry_path]
    else:
        entry["command"], entry["args"] = node_path, [entry_path]
    if "env" in server_def:
        entry["env"] = server_def["env"]
    return entry


# ── Fast Path (hook) ─────────────────────────────────────────────────────
def fast_path():
    """Hook entry: check + merge. Target <3s."""
    # 1. Node.js check
    node = _find_node()
    if not node:
        FLAG_NEEDS_NODE.parent.mkdir(parents=True, exist_ok=True)
        FLAG_NEEDS_NODE.write_text(
            "Node.js not found.\n"
            "Install: winget install OpenJS.NodeJS.LTS\n"
        , newline="\n")
        return
    if FLAG_NEEDS_NODE.exists():
        FLAG_NEEDS_NODE.unlink()

    # Load template
    if not TEMPLATE.exists():
        return
    template = _load_json(TEMPLATE)
    if not template:
        return

    npm_prefix = _npm_global_prefix()

    # 讀 ~/.claude.json 只為看目前註冊了什麼（必須已存在，我們不建立）；寫入一律走 claude CLI
    if not CLAUDE_JSON.exists():
        return
    claude = _load_json(CLAUDE_JSON)
    if not claude:
        return

    current_servers = claude.get("mcpServers", {})
    stored_ver = _stored_version(claude)
    tmpl_ver = template.get("_version", 0)

    to_apply = []   # (name, entry, overwrite)
    missing_packages = []

    for name, sdef in template.get("servers", {}).items():
        entry_path, exists = _resolve_entry(sdef, npm_prefix)

        if not exists:
            # JS file not on disk → queue npm install, skip config for now
            pkg = sdef.get("npm_package")
            if pkg:
                missing_packages.append(pkg)
            continue

        server_entry = _build_server_entry(sdef, node, entry_path)

        if name not in current_servers:
            to_apply.append((name, server_entry, False))   # 缺整塊 → 補上
        elif tmpl_ver > stored_ver:
            to_apply.append((name, server_entry, True))    # Template 版本較新 → 覆寫
        # else: 已存在且 template 沒更新 → 不動（尊重使用者自訂）

    if to_apply and _apply_via_cli(to_apply):
        TEMPLATE_VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        TEMPLATE_VERSION_FILE.write_text(json.dumps({"version": tmpl_ver}), encoding="utf-8", newline="\n")

    # 3. Spawn background installer for missing packages
    if missing_packages:
        _spawn_background("--install", ",".join(missing_packages))

    # 4. TTL version check (spawn if expired)
    installed_pkgs = [
        sdef["npm_package"]
        for sdef in template.get("servers", {}).values()
        if sdef.get("npm_package") and sdef["npm_package"] not in missing_packages
    ]
    if installed_pkgs:
        cache = _load_json(VERSION_CACHE)
        if time.time() - cache.get("last_check", 0) >= TTL_SECONDS:
            _spawn_background("--update", ",".join(installed_pkgs))


# ── Slow Path (detached subprocess) ─────────────────────────────────────
def _spawn_background(flag, packages_csv):
    """Spawn self as detached process for slow npm operations."""
    cmd = [sys.executable, str(Path(__file__).resolve()), flag, packages_csv]
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
    except Exception as e:
        _log_err("ensure_mcp:spawn_background", e)
        pass


def slow_install(packages_csv):
    """Background: npm i -g missing packages."""
    packages = [p for p in packages_csv.split(",") if p]
    if not packages:
        return
    try:
        subprocess.run(
            ["npm", "i", "-g"] + packages,
            timeout=180,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=_NPM_FLAGS,
        )
    except Exception as e:
        _log_err("ensure_mcp:npm_install", e)
        pass


def slow_update(packages_csv):
    """Background: npm outdated + update for our packages. Update TTL cache."""
    packages = set(p for p in packages_csv.split(",") if p)
    if not packages:
        return
    try:
        r = subprocess.run(
            ["npm", "outdated", "-g", "--json"],
            capture_output=True, text=True, timeout=30,
            creationflags=_NPM_FLAGS,
        )
        if r.stdout.strip():
            outdated = set(json.loads(r.stdout).keys())
            to_update = list(outdated & packages)
            if to_update:
                subprocess.run(
                    ["npm", "update", "-g"] + to_update,
                    timeout=180,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=_NPM_FLAGS,
                )
    except Exception as e:
        _log_err("ensure_mcp:npm_update", e)
        pass

    # Update TTL cache
    cache = _load_json(VERSION_CACHE)
    cache["last_check"] = time.time()
    _save_json(VERSION_CACHE, cache)


# ── Entry Point ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        arg = sys.argv[2] if len(sys.argv) > 2 else ""
        if mode == "--install":
            slow_install(arg)
        elif mode == "--update":
            slow_update(arg)
    else:
        fast_path()

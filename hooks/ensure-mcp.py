#!/usr/bin/env python3
"""ensure-mcp.py — SessionStart hook: ensure MCP servers installed & configured.

Fast path (hook, <3s): check files exist → merge config to ~/.claude.json.
Slow path (--install, detached): npm i -g missing packages + TTL version check.

Flow:
  1. Node.js 存在？ 否 → 寫 flag 檔供 Claude 提醒使用者，結束
  2. 讀 mcp-servers.template.json，逐一確認 JS entry point 是否在磁碟上
  3. 存在的 → 合併到 ~/.claude.json（缺整塊才補 or template version 較新才覆寫）
  4. 不存在的 → spawn detached installer（npm i -g），下次 session 才寫入 config
  5. TTL 7 天到期 → detached 執行 npm outdated + update
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────
CLAUDE_DIR = Path.home() / ".claude"
CLAUDE_JSON = Path.home() / ".claude.json"
TEMPLATE = CLAUDE_DIR / "mcp-servers.template.json"
VERSION_CACHE = CLAUDE_DIR / "workflow" / "mcp-version-cache.json"
FLAG_NEEDS_NODE = CLAUDE_DIR / "workflow" / "mcp-needs-node.flag"
TTL_SECONDS = 7 * 86400  # 7 days

# Windows: 避免 npm.cmd 在 detached 父進程下另開 cmd 視窗
_NPM_FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


# ── Helpers ──────────────────────────────────────────────────────────────
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
    except Exception:
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
    except Exception:
        pass
    return None


def _load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _resolve_entry(server_def, npm_prefix):
    """Resolve JS entry point. Returns (absolute_path_str, exists_bool)."""
    if "entry_absolute" in server_def:
        p = Path(server_def["entry_absolute"].replace("{claude_dir}", str(CLAUDE_DIR)))
        return str(p), p.exists()
    if npm_prefix and "entry_relative" in server_def:
        p = Path(npm_prefix) / "node_modules" / server_def["entry_relative"]
        return str(p), p.exists()
    return None, False


def _build_server_entry(server_def, node_path, entry_path):
    """Build a mcpServers JSON entry."""
    entry = {}
    if server_def.get("type"):
        entry["type"] = server_def["type"]
    entry["command"] = node_path
    entry["args"] = [entry_path]
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
        )
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

    # Load ~/.claude.json (must already exist — we don't create it)
    if not CLAUDE_JSON.exists():
        return
    claude = _load_json(CLAUDE_JSON)
    if not claude:
        return

    current_servers = claude.get("mcpServers", {})
    stored_ver = claude.get("_mcpTemplateVersion", 0)
    tmpl_ver = template.get("_version", 0)

    changed = False
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
            # 缺整塊 → 補上
            current_servers[name] = server_entry
            changed = True
        elif tmpl_ver > stored_ver:
            # Template 版本較新 → 覆寫
            current_servers[name] = server_entry
            changed = True
        # else: 已存在且 template 沒更新 → 不動（尊重使用者自訂）

    if changed:
        claude["mcpServers"] = current_servers
        claude["_mcpTemplateVersion"] = tmpl_ver
        _save_json(CLAUDE_JSON, claude)

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
    except Exception:
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
    except Exception:
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
    except Exception:
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

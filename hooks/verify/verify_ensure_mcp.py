#!/usr/bin/env python3
"""verify_ensure_mcp.py — ensure-mcp 只經官方 claude CLI 註冊 MCP，不手改 ~/.claude.json；組出的 entry 與 live 註冊同形。
跑法：python hooks/verify/verify_ensure_mcp.py（假 subprocess，不呼叫真 CLI、不寫真設定；live 對拍只讀 ~/.claude.json）。"""
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "ensure-mcp.py"


def load_module(name):
    spec = importlib.util.spec_from_file_location(name, SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


em = load_module("ensure_mcp_under_test")
fails = []


def check(name, cond):
    if not cond:
        fails.append(name)
    print(("ok   " if cond else "FAIL ") + name)


# 0. live 對拍：樣板經 _build_server_entry 組出的每筆 == ~/.claude.json 裡同名的 live 註冊（樣板 _version 升了覆寫也不會洗掉隱窗外殼）。
#    只讀、不呼叫 CLI；要在後面案例換掉 subprocess.run 之前跑。live 沒有該 server 就印 skip。
live_mod = load_module("ensure_mcp_live")
live_servers = live_mod._load_json(live_mod.CLAUDE_JSON).get("mcpServers", {})
live_node, live_prefix = live_mod._find_node(), live_mod._npm_global_prefix()
for name, sdef in live_mod._load_json(live_mod.TEMPLATE).get("servers", {}).items():
    if name not in live_servers:
        print(f"skip live 對拍 {name}：{live_mod.CLAUDE_JSON} 沒有這個 server")
        continue
    entry_path, _ = live_mod._resolve_entry(sdef, live_prefix)
    built = live_mod._build_server_entry(sdef, live_node, entry_path)
    same = built == live_servers[name]
    check(f"樣板組出的 {name} 與 live 註冊同形", same)
    if not same:
        print(f"     樣板組出：{json.dumps(built, ensure_ascii=False)}\n     live 現狀：{json.dumps(live_servers[name], ensure_ascii=False)}")


def run_case(servers, stored_file_ver, tmpl_ver, cli="claude-fake", rc=0, legacy_ver=None, launcher=("PYW", "HIDE")):
    """在暫存目錄跑一次 fast_path；回傳 (CLI 呼叫清單, stderr, tmp 目錄, claude.json 前後是否相同)。"""
    tmp = Path(tempfile.mkdtemp())
    entry_js = tmp / "server.js"
    entry_js.write_text("//", encoding="utf-8")
    (tmp / "tmpl.json").write_text(json.dumps({"_version": tmpl_ver, "servers": {
        "srv": {"entry_absolute": str(entry_js), "type": "stdio"}}}), encoding="utf-8")
    cj = {"mcpServers": servers}
    if legacy_ver is not None:
        cj["_mcpTemplateVersion"] = legacy_ver
    (tmp / ".claude.json").write_text(json.dumps(cj), encoding="utf-8")
    before = (tmp / ".claude.json").read_bytes()
    if stored_file_ver is not None:
        (tmp / "ver.json").write_text(json.dumps({"version": stored_file_ver}), encoding="utf-8")
    em.TEMPLATE, em.CLAUDE_JSON = tmp / "tmpl.json", tmp / ".claude.json"
    em.TEMPLATE_VERSION_FILE, em.FLAG_CLI_FAILED = tmp / "ver.json", tmp / "cli-failed.flag"
    em.FLAG_NEEDS_NODE, em.VERSION_CACHE = tmp / "needs-node.flag", tmp / "cache.json"
    em._find_node = lambda: "NODE"
    em._npm_global_prefix = lambda: None
    em._spawn_background = lambda *a: None
    em._find_claude = lambda: cli
    em._hidden_launcher = lambda: list(launcher) if launcher else None
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, rc, "", "boom" if rc else "")
    em.subprocess.run = fake_run
    err, old = io.StringIO(), sys.stderr
    sys.stderr = err
    try:
        em.fast_path()
    finally:
        sys.stderr = old
    return calls, err.getvalue(), tmp, before == (tmp / ".claude.json").read_bytes()


# 1. 已註冊且版本相同 → 不呼叫 CLI
calls, err, tmp, same = run_case({"srv": {}}, 1, 1)
check("沒事可做不呼叫 CLI", calls == [] and same)

# 2. 舊鍵 _mcpTemplateVersion 當 fallback：已註冊、舊鍵版本相同 → 不重註冊
calls, err, tmp, same = run_case({"srv": {}}, None, 1, legacy_ver=1)
check("沒有版本小檔時沿用舊鍵，不重註冊", calls == [])

# 3. 缺 server → 只 add-json（user scope、list 參數）；entry 包隱窗外殼：pythonw run-hidden.py node <js>
calls, err, tmp, same = run_case({}, 1, 1)
exp = {"type": "stdio", "command": "PYW", "args": ["HIDE", "NODE", str(tmp / "server.js")]}
check("缺 server 只呼叫一次 add-json", len(calls) == 1 and calls[0][:4] == ["claude-fake", "mcp", "add-json", "srv"])
check("add-json 的 JSON 與旗標", json.loads(calls[0][4]) == exp and calls[0][5:] == ["--scope", "user"])
check("成功寫版本小檔、不手改 .claude.json", json.loads((tmp / "ver.json").read_text())["version"] == 1 and same)
check("成功無旗標檔", not (tmp / "cli-failed.flag").exists())

# 4. 樣板版本較新 → 先 remove 再 add
calls, err, tmp, same = run_case({"srv": {}}, 1, 2)
check("版本較新先 remove 再 add",
      [c[2] for c in calls] == ["remove", "add-json"] and calls[0][3:] == ["srv", "--scope", "user"])
check("覆寫成功版本小檔升到 2", json.loads((tmp / "ver.json").read_text())["version"] == 2 and same)

# 5. CLI 不在 → stderr＋旗標檔，不寫版本、不碰 .claude.json
calls, err, tmp, same = run_case({}, 1, 1, cli=None)
check("CLI 不在：stderr 一行", err.count("\n") == 1 and "找不到 claude CLI" in err)
check("CLI 不在：旗標檔在、無呼叫、.claude.json 不變", (tmp / "cli-failed.flag").exists() and calls == [] and same)

# 6. CLI 回非 0 → 同上，版本不前進
calls, err, tmp, same = run_case({}, 0, 1, rc=1)
check("CLI 失敗：旗標檔＋stderr，版本小檔仍是 0", (tmp / "cli-failed.flag").exists() and "boom" in err
      and json.loads((tmp / "ver.json").read_text())["version"] == 0 and same)

# 7. 沒有隱窗外殼（非 Windows）→ 直接 node <js>
calls, err, tmp, same = run_case({}, 1, 1, launcher=None)
check("沒外殼時 entry 直接起 node",
      json.loads(calls[0][4]) == {"type": "stdio", "command": "NODE", "args": [str(tmp / "server.js")]})

# 8. 外殼檔案判定：Windows 缺 pythonw → stderr 一行、回 None；兩檔都在 → [pythonw, run-hidden.py]
probe = load_module("ensure_mcp_launcher")
real_pyw = probe.GUI_PYTHONW
probe.GUI_PYTHONW = tmp / "no-such-pythonw.exe"
err, old = io.StringIO(), sys.stderr
sys.stderr = err
try:
    got = probe._hidden_launcher()
finally:
    sys.stderr = old
if sys.platform == "win32":
    check("缺 pythonw：回 None＋stderr 一行", got is None and err.getvalue().count("\n") == 1 and "[ensure_mcp:hidden]" in err.getvalue())
    probe.GUI_PYTHONW = tmp / "server.js"   # 任一存在的檔代替
    check("兩檔都在：回 [pythonw, run-hidden.py]", probe._hidden_launcher() == [str(tmp / "server.js"), str(probe.RUN_HIDDEN)])
else:
    check("非 Windows 不包外殼", got is None and err.getvalue() == "")

print("ENSURE_MCP_CHECK " + ("FAIL" if fails else "PASS"))
sys.exit(1 if fails else 0)

"""verify_mcp_funnel_hardening.py — MCP server (js) funnel 硬化守門.

守住曾是已驗證缺陷的不變式（tools/workflow-guardian-mcp/lib/）：
1. **vector reindex 端點**：service.py 只有 `/index/incremental`，`/reindex` 是 404
   死信；且失敗必浮訊號（crashLog），不得 `req.on("error", ()=>{})` 全吞。
2. **write-gate 無 shell 注入面**：payload 走 spawn + stdin（script 的 pipe 模式），
   不得用 `echo ${手工轉義} | python` shell 管線；fail-open 放行但 crashLog 記
   gate unavailable。
3. **spawn 皆有 timeout**：spawnAtomCli / spawnAtomAccess / spawnEditMetadata /
   spawnIndexDelete / execWriteGate 都要有 setTimeout + kill 護欄（無 timeout 的
   python 子程序卡死 = MCP tool call 永久 pending）。

純檔案讀取 + regex，無重依賴。
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

CLAUDE = Path(__file__).resolve().parents[2]  # hooks/verify/ → ~/.claude
if str(CLAUDE) not in sys.path:
    sys.path.insert(0, str(CLAUDE))

MCP_LIB = "tools/workflow-guardian-mcp/lib"


def _read(rel: str) -> str:
    return (CLAUDE / rel).read_text(encoding="utf-8")


def test_reindex_endpoint_and_error_surfacing():
    funnel = _read(f"{MCP_LIB}/funnel.js")
    service = _read("tools/memory-vector-service/service.py")
    assert "/index/incremental" in funnel, "funnel.js 應打 /index/incremental"
    assert "3849/reindex" not in funnel, "殘留死信端點 /reindex（service 無此路由）"
    assert "/index/incremental" in service, "前提失效：service.py 路由表無 /index/incremental"
    # 錯誤不得靜默吞掉（可觀測性鐵律）
    fn = funnel[funnel.index("function triggerVectorReindex"):]
    fn = fn[:fn.index("\n}") + 2]
    assert 'req.on("error", () => {})' not in fn, "reindex error handler 不得空吞"
    assert "crashLog" in fn, "reindex 失敗應 crashLog 浮訊號"


def test_write_gate_no_shell_injection():
    funnel = _read(f"{MCP_LIB}/funnel.js")
    assert "echo ${" not in funnel and not re.search(r"\| python", funnel), \
        "execWriteGate 不得用 echo | python shell 管線（注入面）"
    fn = funnel[funnel.index("function execWriteGate"):]
    fn = fn[:fn.index("\n}") + 2]
    assert ".spawn(" in fn and "stdin.write" in fn, \
        "execWriteGate 應 spawn + stdin 寫 payload"
    assert "crashLog" in fn, "gate unavailable 應 crashLog（fail-open 但不靜默）"


def _fn_body(src: str, marker: str) -> str:
    body = src[src.index(marker):]
    return body[:body.index("\n}") + 2]


def test_spawn_sites_have_timeout():
    funnel = _read(f"{MCP_LIB}/funnel.js")
    access = _read(f"{MCP_LIB}/atom-access.js")
    tools = _read(f"{MCP_LIB}/atom-tools.js")
    for src, marker in [
        (funnel, "function spawnAtomCli"),
        (funnel, "function execWriteGate"),
        (access, "function spawnAtomAccess"),
        (tools, "function spawnEditMetadata"),
        (tools, "function spawnIndexDelete"),
    ]:
        body = _fn_body(src, marker)
        assert "setTimeout" in body and "kill()" in body, f"{marker} 缺 timeout+kill 護欄"
        assert "clearTimeout" in body, f"{marker} 缺 clearTimeout（timer 洩漏）"


def test_merge_to_preferences_archives_sidecar_and_index():
    tools = _read(f"{MCP_LIB}/atom-tools.js")
    assert "手動移除 _ATOM_INDEX.md" not in tools, \
        "merge_to_preferences 不得再留「手動移除索引」過時指引"
    assert "spawnIndexDelete" in tools and "delete_atom" in tools, \
        "merge_to_preferences 應實際走 lib.atom_index_json.delete_atom 移除索引條目"
    assert '.access.json")' in tools and "accSrc" in tools, \
        "歸檔應同步搬 .access.json sidecar"


def test_dedup_layers_for_matches_indexer_layer_labels():
    """write-gate 去重層清單：global 只比 global+本地；專案 scope 再加當前專案自己的層，
    slug 對拍 wg_core.cwd_to_project_slug（c:/Work → c--work；路徑用正斜線寫，projectSlugOf 兩種斜線都吃）。"""
    import json as _json
    import subprocess
    lib = os.path.join(os.path.expanduser("~"), ".claude", "tools", "workflow-guardian-mcp", "lib", "realm.js")
    script = (
        "const r=require(process.argv[1]);"
        "console.log(JSON.stringify(["
        "r.dedupLayersFor('global', 'C:/Users/x/.claude/memory'),"
        "r.dedupLayersFor('shared', 'c:/Work/.claude/memory'),"
        "r.dedupLayersFor('personal', 'c:/GAMEA/.claude/memory', {user:'holylight'}),"
        "r.dedupLayersFor('role', 'd:/WORK-AREA/demo-projs/AppBViewer/.claude/memory', {role:'programmer'}),"
        "]))"
    )
    out = subprocess.run(["node", "-e", script, lib], capture_output=True, text=True, check=True).stdout
    g, s, p, ro = _json.loads(out)
    assert g == ["global", "extra:local-atoms"]
    assert s == ["global", "extra:local-atoms", "shared:c--work"]
    assert p == ["global", "extra:local-atoms", "shared:c--gamea", "personal:c--gamea:holylight"]
    assert ro == ["global", "extra:local-atoms", "shared:d--work-area-demo-projs-appbviewer",
                  "role:d--work-area-demo-projs-appbviewer:programmer"]


# ─── v6 M1／M2：寫入閘分型 payload、append/replace 叫閘、org realm 先於改寫 ─────────


def test_write_gate_payload_has_v6_keys():
    """funnel.execWriteGate(..., opts) 把 mode/existing_path/actions/depends/kind_hint 透傳給 py stdin（同名鍵）。"""
    funnel = _read(f"{MCP_LIB}/funnel.js")
    body = _fn_body(funnel, "function execWriteGate")
    assert "opts" in body and "GATE_OPT_KEYS" in funnel
    for k in ("mode", "existing_path", "actions", "depends", "kind_hint"):
        assert f'"{k}"' in funnel, f"GATE_OPT_KEYS 缺 {k}"
    assert "stdin.write(JSON.stringify(payload))" in body


def test_atom_tools_append_and_replace_call_write_gate():
    """create／append／replace 三分支都叫閘（mode 各自標明）；拒寫句子只來自 py reason（gateRejectText 單點）。"""
    tools = _read(f"{MCP_LIB}/atom-tools.js")
    create = tools[tools.index("// ── Mode: create ──"):tools.index("// ── Mode: append ──")]
    append_ = tools[tools.index("// ── Mode: append ──"):tools.index("// ── Mode: replace ──")]
    replace = tools[tools.index("// ── Mode: replace ──"):]
    assert 'mode: "create"' in create and "execWriteGate(" in create
    assert 'mode: "append"' in append_ and "execWriteGate(" in append_ and "existing_path: filePath" in append_
    assert 'mode: "replace"' in replace and "execWriteGate(" in replace and "existing_path: filePath" in replace
    # append 的閘在 dry_run 回傳之前（閘一律擋、沒有 dry_run 豁免）
    assert append_.index("execWriteGate(") < append_.index("if (dry_run)")
    # js 不另寫拒寫句：Write-gate rejected 只出現在 gateRejectText 一處
    assert tools.count("Write-gate rejected:") == 1 and "function gateRejectText" in tools
    assert "gateRejectText(" in create and "gateRejectText(" in append_ and "gateRejectText(" in replace
    # skip_gate 不再整段跳過閘（只透傳給 py 跳 dedup/quality）
    assert "if (!skip_gate) {" not in create and "skip_gate: !!skip_gate" in create


def test_org_realm_check_runs_before_rewrite_to_shared():
    tools = _read(f"{MCP_LIB}/atom-tools.js")
    org_check = tools.index('scope: "org", project_cwd: project_cwd || process.cwd()')
    rewrite = tools.index('    scope = "shared";\n    project_cwd = orgRoot;')
    assert org_check < rewrite, "org realm 檢查必須在 org→shared 改寫之前"
    assert tools.index('spawnAtomCli("realm_check", {\n      scope: "org"') < rewrite


def test_no_spawn_site_without_timeout():
    """新加的 spawn 也要有 timeout+kill：掃 funnel.js／atom-tools.js 所有含 .spawn( 的函式。"""
    for rel in (f"{MCP_LIB}/funnel.js", f"{MCP_LIB}/atom-tools.js"):
        src = _read(rel)
        starts = [m.start() for m in re.finditer(r"^(?:async )?function \w+\(", src, re.MULTILINE)]
        for i, st in enumerate(starts):
            end = starts[i + 1] if i + 1 < len(starts) else len(src)
            body = src[st:end]
            if ".spawn(" not in body:
                continue
            name = body[:body.index("(")]
            # 既有 fire-and-forget（detached + unref，背景重產目錄）不在此列；新加的 spawn 一律要 timeout
            if name.endswith("syncMemoryIndex") and "unref()" in body:
                continue
            assert "setTimeout" in body and "kill()" in body, f"{rel}:{name} 缺 timeout+kill"

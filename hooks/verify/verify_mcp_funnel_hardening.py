"""verify_mcp_funnel_hardening.py — MCP server (js) funnel 硬化守門.

守住曾是已驗證缺陷的不變式（tools/workflow-guardian-mcp/lib/）：
1. **vector reindex 端點**：service.py 只有 `/index/incremental`，`/reindex` 是 404
   死信；且失敗必浮訊號（crashLog），不得 `req.on("error", ()=>{})` 全吞。
2. **write-gate 無 shell 注入面**：payload 走 spawn + stdin（script 的 pipe 模式），
   不得用 `echo ${手工轉義} | python` shell 管線；fail-open 放行但 crashLog 記
   gate unavailable。
3. **spawn 皆有 timeout**：spawnAtomCli / spawnAtomAccess / spawnEditMetadata /
   spawnIndexDelete / execWriteGate / spawnPrepare（second-opinion.js）/ spawnSmells
   （project-smells.js）都要有 setTimeout + kill 護欄（無 timeout 的
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
    second = _read(f"{MCP_LIB}/second-opinion.js")
    smells = _read(f"{MCP_LIB}/project-smells.js")
    for src, marker in [
        (funnel, "function spawnAtomCli"),
        (funnel, "function execWriteGate"),
        (access, "function spawnAtomAccess"),
        (tools, "function spawnEditMetadata"),
        (tools, "function spawnIndexDelete"),
        (second, "function spawnPrepare"),
        (smells, "function spawnSmells"),
    ]:
        body = _fn_body(src, marker)
        assert "setTimeout" in body and "kill()" in body, f"{marker} 缺 timeout+kill 護欄"
        assert "clearTimeout" in body, f"{marker} 缺 clearTimeout（timer 洩漏）"


# 刻意不設 timeout 的 spawn 點（例外清單）：登記理由，並由 test_spawn_exempt_sites_are_detached 驗「真的是 detached 且理由在註解裡」。
SPAWN_TIMEOUT_EXEMPT = {
    ("second-opinion.js", "function spawnExecute"):
        "detached 跑 codex（60～300 s），MCP 回應不等它；上限在 py 側三處（run_guard 60 s、探針與正式 codex 的 "
        "wait(timeout)+kill）加 js readResult 逾 timeout_s+90 s 回 failed，不會永遠掛",
}


def test_spawn_exempt_sites_are_detached():
    for (fname, marker), why in SPAWN_TIMEOUT_EXEMPT.items():
        src = _read(f"{MCP_LIB}/{fname}")
        body = _fn_body(src, marker)
        assert "detached: true" in body and ".unref()" in body, f"{marker} 登記為例外但不是 detached+unref：{why}"
        head = src[max(0, src.index(marker) - 600):src.index(marker)]
        assert "setTimeout" in head and "readResult" in head, f"{marker} 上方註解要寫明為何沒 timeout 與上限在哪"
    # 兩個新檔的其他 spawn( 呼叫點都要在 timeout 清單或例外清單裡
    for fname, timed in (("second-opinion.js", {"function spawnPrepare"}), ("project-smells.js", {"function spawnSmells"})):
        src = _read(f"{MCP_LIB}/{fname}")
        fn_names = set(re.findall(r"^function (\w+)\(", src, flags=re.M))
        spawning = {n for n in fn_names if "spawn(" in _fn_body(src, f"function {n}")}
        allowed = {m.split()[1] for m in timed} | {m.split()[1] for (f, m) in SPAWN_TIMEOUT_EXEMPT if f == fname}
        assert spawning <= allowed, f"{fname} 有未登記的 spawn 點：{spawning - allowed}"


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

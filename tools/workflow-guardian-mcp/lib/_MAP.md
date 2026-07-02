# lib/ 模組地圖（workflow-guardian-mcp）

> `server.js` 由 4394 行單檔拆為「進入點 + 11 lib 模組」。純機械拆分、行為保留、零新依賴。
> 進入點 `server.js` 只剩：requires/wiring、MCP stdio 轉接、HTTP route table、埠自癒、boot block、parity export 面。

## 相依方向（DAG；唯一環：mcp ↔ atom-tools，由 mcp.handleToolCall 對 atom-tools 的 lazy-require 化解）

```
paths ← log, state, realm, atom-access, funnel, atom-tools, mcp, http-api, server
log   ← funnel, atom-tools, mcp, server
state ← mcp, http-api, server
realm ← atom-tools
atom-access ← atom-tools, http-api
funnel ← atom-tools
atom-render ← server(re-export)
dashboard-html ← server
mcp ⇄ atom-tools     (mcp 對 atom-tools 用 lazy require；atom-tools 對 mcp 取 sendToolResult)
http-api ← server
```

## 模組 → 職責 → py 鏡像

| 模組 | 職責 | py 鏡像 / SYNC |
|------|------|----------------|
| `paths.js` | 路徑錨（CLAUDE/WORKFLOW/MEMORY/TOOLS/CONFIG/REGISTRY/VERSION）＋ config/registry/version 載入。零內部相依葉。 | — |
| `log.js` | crash 記錄與致命錯誤守門（crashLog / onFatal）。全域 `process.on` handler 留 server.js 呼叫本檔。 | — |
| `state.js` | `workflow/state-*.json` 讀寫＋會期 3-tier auto-cleanup。 | — |
| `realm.js` | 範疇/路由分類（classifyRealm / cleanRealmSegment / resolveMemDir / applyFeedback·LocalRouting / slugify …）。 | `lib/atom_locations.py`（parity test_14/17/22 讀本檔原始碼 eval） |
| `atom-render.js` | atom 內容構造/渲染/驗證（buildAtomContent / renderKnowledgeLines / isBlockKnowledge / validateAtomContent）。 | `lib/atom_spec.py`（byte-identical；test_13 require server.js re-export） |
| `atom-access.js` | `<atom>.access.json` 遙測讀取＋效用 Wilson 下界（usefulnessStats / wilsonLowerBound / enrichAtomWithAccess）。 | `lib/atom_access.py`（SYNC；verify_promotion_gate 讀本檔） |
| `funnel.js` | python subprocess 橋接群（conflict-detector / write-gate / atom_io_cli / access）。 | `lib/atom_io*.py` / `lib/atom_access.py`（spawn 面） |
| `atom-tools.js` | 4 個 MCP tool 業務（atom_write / atom_promote / atom_edit_meta / atom_move）。 | `lib/atom_io.py` toolAtomWrite 對拍（test_25 讀本檔 delegation guard） |
| `mcp.js` | MCP stdio JSON-RPC transport；`buffer` 私有其內；4 個 dead IPC handler 隨此搬。handleToolCall lazy-require atom-tools。 | — |
| `http-api.js` | dashboard 唯讀 API 端點群（含 http-util helpers: jsonRes/pyCmd/makeJobRunner/execJson/readJsonBody）。私有可變 state 只透過本檔 handler 存取。 | — |
| `dashboard-html.js` | dashboard HTML 模板；匯出 `render(versions)→string`。內層瀏覽器端 const 為前端 JS，勿 hoist。 | — |
| `server.js` | 進入點：requires/wiring、MCP 轉接、HTTP route table + createServer、埠自癒（C1：`__filename`/`SELF_MTIME_AT_BOOT`/relinquish 鎖此）、boot block、`require.main` guard + re-export（C4）。 | — |

## 拆分不可動的地雷（保留約束）

- **C1**：埠自癒的「同檔判舊」靠 `SELF_MTIME_AT_BOOT` + `__filename` → `httpServer` bootstrap / 埠綁定 / relinquish / boot block **留 server.js**。
- **C2**：MCP stdin `buffer` 私有於 `mcp.js`（transport 與 handleMessage 同檔）。
- **C4**：`server.js` 保留 `require.main===module` guard，並 re-export `buildAtomContent/renderKnowledgeLines/isBlockKnowledge`（verify_atom_io_equivalence test_13 bare require）。
- **C7**：`dashboard-html.js` 內 3188-3889 的 const 是瀏覽器端 JS，非模組 state，勿 hoist。

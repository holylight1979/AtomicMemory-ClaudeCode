# lib/ 模組地圖（workflow-guardian-mcp）

> `server.js` 為「進入點 + 14 lib 模組」。進入點 `server.js` 只剩：requires/wiring、MCP stdio 轉接、
> HTTP route table、埠自癒、boot block、parity export 面。
> （原 4394 行單檔純機械拆分為進入點+11 模組；後續 Anti-Evasion HUD 加 `anti-evasion.js`+`aec-hud-html.js`。）

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
mcp ⇄ harvest        (同 atom-tools 模式：mcp lazy require；harvest 對 mcp 取 sendToolResult)
mcp ⇄ anti-evasion   (同上；anti-evasion 另相依 paths)
http-api ← server
```

## 模組 → 職責 → py 鏡像

| 模組 | 職責 | py 鏡像 / SYNC |
|------|------|----------------|
| `paths.js` | 路徑錨（CLAUDE/WORKFLOW/MEMORY/TOOLS/CONFIG/REGISTRY/VERSION）＋ config/registry/version 載入。零內部相依葉。 | — |
| `log.js` | crash 記錄與致命錯誤守門（crashLog / onFatal）。全域 `process.on` handler 留 server.js 呼叫本檔。 | — |
| `state.js` | `workflow/state-*.json` 讀寫＋會期 3-tier auto-cleanup。 | — |
| `realm.js` | 範疇/路由分類（classifyRealm / cleanRealmSegment / resolveMemDir / applyFeedback·LocalRouting / slugify …）。詞庫/保護清單/權重讀 `memory/_meta/realm-lexicon.json`（單一來源，py 同檔；缺失 fallback＋stderr）。`orgMemoryRoot()` 公司層根（MIRROR `hooks/wg_core.py:org_memory_root`：enabled 且 roots 恰 1 → root；缺鍵／空／>1 → null＋stderr）；`dedupLayersFor("org")`＝global + `shared:<org slug>`。 | `lib/atom_locations.py`（parity test_14/14b/17 require 實跑＋schema 守法；test_22 讀本檔原始碼 eval） |
| `atom-render.js` | atom 內容構造/渲染/驗證（buildAtomContent / renderKnowledgeLines / isBlockKnowledge / validateAtomContent）。buildAtomContent 收 `supersedes`：Related 之後輸出 `- Supersedes: a, b`，未給／空陣列不輸出任何行；收 `provenance` → `- Source:`（Author 後）、`depends` → `- Depends:`（Created-at 後、Related 前），未給／空不輸出。 | `lib/atom_spec.py`（byte-identical；test_13 require server.js re-export） |
| `atom-access.js` | `<atom>.access.json` 遙測讀取＋效用 Wilson 下界（usefulnessStats / wilsonLowerBound / enrichAtomWithAccess）。 | `lib/atom_access.py`（SYNC；verify_promotion_gate 讀本檔） |
| `funnel.js` | python subprocess 橋接群（conflict-detector / write-gate / atom_io_cli / access）＋ `syncMemoryIndex([memoryDir])`：無參數刷全域 catalog，帶專案 memory dir 則 `--memory-dir` 只 upsert 該專案 MEMORY.md 的 `<!-- atom-catalog -->` 區塊。 | `lib/atom_io*.py` / `lib/atom_access.py`（spawn 面）；`tools/sync-memory-index.py` |
| `harvest.js` | MCP tool `knowledge_harvest_report` handler：驗 items schema（action≠skip 必 atom+path、skip 必 reason）、回 chip `[Harvest] N 寫入／M 退役／K 不寫`（items=[] → `本場無新知識`）；**不碰 state、不寫檔**（one-writer）。 | `hooks/handlers/post_tool_use.py`（items ↔ receipt 核對、state.knowledge_harvest／ledger 唯一寫者） |
| `atom-tools.js` | 6 個 MCP tool 業務（atom_write / atom_promote / atom_edit_meta / atom_move / atom_retire / memory_search）。`memory_search`：`spawnAtomCli("search")` 唯讀、排版 table|json、warnings 併入回覆、不寫 state 無 receipt。scope=org 語法糖：`atom_write`／`atom_retire` 改寫成 shared + project_cwd=`orgMemoryRoot()`，未啟用即拒。atom_write `provenance`／`depends` 三態同 supersedes（replace 讀舊檔 `- Source:`／`- Depends:` 回填）。atom_write／atom_retire 成功時結果文字最後一行 `receipt: {op, ok, atom, path, index_ok, supersedes | old_path, new_path}`（retire 失敗亦附 `ok:false` + steps_done/steps_failed）。atom_write `supersedes` 三態：未給＝replace 保留原 `- Supersedes:` 行（js 讀舊檔回填）、`[]`＝清除、非空＝替換；自指 js 先拒，目標存在／循環／核心保護由 py build 裁決。atom_retire 全交 py `atom_io_cli` action=retire（locate → memory-audit.delete_atom(project_dir)），js 只轉述＋receipt＋專案層 `syncMemoryIndex(memRoot)`。atom_write scope=global：所有 mode 先 spawn py `realm_check`（`lib/realm_gate.py`，專名命中即拒、`skip_gate` 跳不過；缺 `project_cwd` 退用進程 cwd）；create：缺 `domain` 不 spawn；atom_move 回報以 `formatAtomMoveReport` 把本次結果與 `index_preexisting_issues`（既有 validate 錯誤）分開；落點由 py `locate(mode=create)` 回的 `target_dir/category` 決定（js 不重作路由）；`dry_run` 透傳 py `create_atom`（append/replace 定位後短路）；shared create/replace 後 `syncMemoryIndex(baseDir)`。 | `lib/atom_io.py` toolAtomWrite 對拍（test_25 讀本檔 delegation guard） |
| `mcp.js` | MCP stdio JSON-RPC transport；`buffer` 私有其內；4 個 dead IPC handler 隨此搬。TOOL_DEFINITIONS 8 個 tool：atom_write / atom_promote / atom_move / atom_edit_meta / anti_evasion_report / knowledge_harvest_report / atom_retire / memory_search（scope enum 含 `org` 語法糖）。handleToolCall lazy-require atom-tools / anti-evasion / harvest。 | — |
| `http-api.js` | dashboard 唯讀 API 端點群（含 http-util helpers: jsonRes/pyCmd/makeJobRunner/execJson/readJsonBody）。私有可變 state 只透過本檔 handler 存取。 | — |
| `dashboard-html.js` | dashboard HTML 模板；匯出 `render(versions)→string`。內層瀏覽器端 const 為前端 JS，勿 hoist。 | — |
| `anti-evasion.js` | Anti-Evasion HUD 的 Node 面：MCP tool `anti_evasion_report` handler（只回 chip、**不碰 state**；one-writer）＋ HUD 唯讀 API（`apiAecReports`/`apiAecReport` glob disk 上 Python 落的 `aec-report/*.json` 子夾）＋ 窗活性（`apiAecStream` SSE 常駐連線計數＝窗開著的證據、`apiAecBeat` 心跳＝正在渲染、`apiAecBeatStatus` 回 `{age_s, clients}` 供 Python `_hud_alive`）＋ `aecSeverity` ＋ `aecPendingItems`（(d)/(h) 把記憶寫入推到之後 → chip 附 ⛔）。 | `hooks/wg_evasion.py::aec_severity` / `aec_pending_items`（same-rule mirror；parity test 在 verify_aec_emission_gate）＋ `hooks/handlers/post_tool_use.py`（state/檔唯一寫者） |
| `aec-hud-html.js` | Anti-Evasion HUD 頁模板；匯出 `render()→string`。dark 單頁：最新收尾檢核卡 (a)(b)(c)(d) + 近 N 回合 severity 歷史格；輪詢 1.5s（非 SSE）。內層瀏覽器端 JS 勿 hoist（C7）。 | — |
| `server.js` | 進入點：requires/wiring、MCP 轉接、HTTP route table + createServer、埠自癒（C1：`__filename`/`SELF_MTIME_AT_BOOT`/relinquish 鎖此）、boot block、`require.main` guard + re-export（C4）。 | — |

## 拆分不可動的地雷（保留約束）

- **C1**：埠自癒的「同檔判舊」靠 `SELF_MTIME_AT_BOOT` + `__filename` → `httpServer` bootstrap / 埠綁定 / relinquish / boot block **留 server.js**。
- **C2**：MCP stdin `buffer` 私有於 `mcp.js`（transport 與 handleMessage 同檔）。
- **C4**：`server.js` 保留 `require.main===module` guard，並 re-export `buildAtomContent/renderKnowledgeLines/isBlockKnowledge`（verify_atom_io_equivalence test_13 bare require）。
- **C7**：`dashboard-html.js` 內 3188-3889 的 const、`aec-hud-html.js` 內 `<script>` 區塊皆為瀏覽器端 JS，非模組 state，勿 hoist（後者另刻意用字串串接、不用 template literal，避免 nested-backtick）。
- **一寫者（one-writer spine）**：`anti-evasion.js`、`harvest.js` 的 MCP tool handler **全程不碰 state**；state 寫入/持久化/HUD spawn 由 Python `post_tool_use.py`（帶原始 session_id + turn_seq）獨佔——解 MCP 進程無 session 身份 + Node `writeState` 無鎖 race。Stop 閘以 **turn_seq+session_id 雙鍵**判 emit 滿足（sibling 隔離）。`knowledge_harvest_report` 的 items 核對與 `atom_write`／`atom_retire` 的 receipt 行同樣由 Python PostToolUse 消費（記進 `state.atom_ops[<sid>]`／`state.knowledge_harvest[<sid>]`），Node 側只產 receipt、只回 chip。
- **MCP 介面 smoke**：`verify/smoke_mcp_stdio.js` 以 stdio JSON-RPC 起 server.js（`WG_DASHBOARD_PORT=38499` 隔離埠）驗 tools/list（8 tool）與 harvest／supersedes／retire／memory_search 真查／scope=org dry_run 的 js 層契約；不在 `run_verify.py` 掃描範圍，手動 `node tools/workflow-guardian-mcp/verify/smoke_mcp_stdio.js`。

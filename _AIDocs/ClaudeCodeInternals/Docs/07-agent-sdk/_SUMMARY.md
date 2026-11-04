# 07-agent-sdk 導讀（Agent SDK，32 頁）

> 來源：code.claude.com/docs/zh-TW/agent-sdk/*（harvested 2026-11-04）。每頁一張卡，依 subsection 分組。

## 先看這裡：只有 SDK 才有、CLI 沒有的能力（含記憶系統接點）

| 能力 | SDK 做法 | 出處頁 |
| - | - | - |
| 程式化 hook callback | `options.hooks` 註冊 Python/TS 函式，回傳 `permissionDecision`/`updatedInput`/`additionalContext`/`updatedToolOutput`；`onFailure:"block"` 可失敗即阻擋；CLI 的 hook 只能是 command/http/mcp_tool/prompt | hooks |
| 逐次核准回呼 | `canUseTool` 回呼可允許（可改寫輸入）或拒絕，並接 `AskUserQuestion`；CLI 只有互動彈窗 | user-input、permissions |
| session 儲存位置客製 | `sessionStore` 配接器（`append`/`load`）把逐字稿鏡像到自己的 DB/物件儲存；CLI 固定寫 `~/.claude/projects/`；另可用 `CLAUDE_CONFIG_DIR` 改根目錄 | session-storage、hosting |
| system prompt 修改 | `systemPrompt` 可用 `claude_code` preset + `append`、完整自訂字串/檔案、`excludeDynamicSections`、`snapshot`、`SYSTEM_PROMPT_DYNAMIC_BOUNDARY`；預設為最小 prompt（非 Claude Code 版） | modifying-system-prompts、migration-guide |
| 檔案系統設定隔離 | `settingSources: []` 不載入 user/project/local；`settings`/`managedSettings` 程式端覆寫；`projectConfigRoot` | claude-code-features、configuration、hosting |
| 程式內註冊 MCP 工具 | `tool()` + `createSdkMcpServer()`（同程序，無獨立 server） | custom-tools |
| 程式化子代理 | `agents` 參數定義 `AgentDefinition`（含 `memory`、`skills`、`maxTurns`） | subagents |
| 執行中控制 | `Query` 方法：`setPermissionMode`、`setModel`、`interrupt`、`reloadPlugins`、`rewindFiles`、`getContextUsage`、`updateSettings`（TS） | typescript |
| 預熱／自訂程序啟動 | `startup()`、`prewarm()`、`spawnClaudeCodeProcess` | typescript |
| 檔案回溯與結構化輸出 | `enableFileCheckpointing`+`rewindFiles()`；`outputFormat` JSON Schema | file-checkpointing、structured-outputs |
| 成本與遙測 | `total_cost_usd`/`modelUsage`；以 `env` 啟用 OpenTelemetry | cost-tracking、observability |

### 記憶系統接點總覽
- SDK 預設載入 `~/.claude`（CLAUDE.md、rules、skills、settings、settings 內 hooks），所以 SessionStart／UserPromptSubmit 類 shell hook 與 `~/.claude` 記憶注入在 SDK 工作階段內預設仍會運作；`settingSources: []` 可全部關閉。
- Python SDK 的 callback hook 只有 10 種事件，不含 `SessionStart`/`SessionEnd`（這兩者在 Python 只能走 settings.json 的 shell hook）；TS SDK 約 33 種事件，另有 `InstructionsLoaded`、`PostCompact`、`FileChanged`、`ConfigChange` 等。
- hook 注入上下文的欄位是 `additionalContext`（UserPromptSubmit/PostToolUse 等），以 system-reminder 形式進對話，不改 system prompt。
- 自動記憶 `~/.claude/projects/<project>/memory/` 不受 `settingSources` 控制，需 `autoMemoryEnabled:false` 或 `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` 關閉；多租戶另設 `CLAUDE_CONFIG_DIR`。
- 子代理只繼承 Agent 工具 prompt 字串、專案 CLAUDE.md 與工具定義；`AgentDefinition.memory` 欄位可選 user/project/local。
- 壓縮前後有 `PreCompact`/`PostCompact` hook 與 `compact_boundary` 訊息；resume 時 system prompt 以首次請求快照重用（`snapshot`）。

### API 變化重點（migration-guide、typescript-v2-preview）
- 改名：`@anthropic-ai/claude-code`→`@anthropic-ai/claude-agent-sdk`；`claude-code-sdk`→`claude-agent-sdk`；`ClaudeCodeOptions`→`ClaudeAgentOptions`。
- v0.1.0：不再預設 Claude Code system prompt；settingSources 預設曾改為不載入、之後已還原（省略＝全載入）。
- V2 session API（`unstable_v2_createSession`/`resumeSession`/`prompt`、`SDKSession`）在 TS 0.3.142 移除，0.2.x 是最後版本；改用 `query()` + `AsyncIterable<SDKUserMessage>` 或 `options.resume`。


## Agent SDK 入門（Agent SDK）

### Agent SDK 概述（`agent-sdk/overview`）
- 檔案：[agent-sdk__overview.md](agent-sdk__overview.md)｜https://code.claude.com/docs/zh-TW/agent-sdk/overview｜lastmod 2026-09-22｜7KB
- 一句話：Agent SDK 是把 Claude Code 引擎當成 Python/TS 函式庫嵌入自己的程式。
- 何時讀：想判斷該用 SDK、CLI、Client SDK 還是 Managed Agents 時。
- 關鍵內容：
  - 四選一：Agent SDK（自己程序內嵌入）／CLI／Client SDK（自寫工具迴圈）／Managed Agents（Anthropic 託管）
  - SDK 實際是執行 Claude Code 二進位檔的庫，功能同 CLI：內建工具、hooks、子代理、MCP、權限、sessions
  - Skills、命令、記憶從專案 `.claude/` 與 `~/.claude/` 自動載入，與 CLI 相同
  - Plugins 以本機路徑載入；非 Python/TS 語言改用 `claude -p --output-format json` 子程序
  - 第三方產品不得提供 claude.ai 登入或其速率限制，須用 API 金鑰驗證
  - 品牌：可稱 "Claude Agent"，不可稱 "Claude Code" 或仿其 ASCII 藝術
- 新名詞：`Agent SDK` ＝ 把 Claude Code 當函式庫嵌進自己程式的套件；`Managed Agents` ＝ Anthropic 雲端託管代理迴圈的服務
- 記憶系統接點：SDK 與 CLI 共用同一引擎，`~/.claude`（CLAUDE.md、skills、hooks、settings）在 SDK 內預設也會生效，現有注入機制可被沿用

### 快速開始（`agent-sdk/quickstart`）
- 檔案：[agent-sdk__quickstart.md](agent-sdk__quickstart.md)｜https://code.claude.com/docs/zh-TW/agent-sdk/quickstart｜lastmod 2026-10-27｜15KB
- 一句話：用 Python/TS 十來行建出會讀程式、找 bug 並自動修的代理。
- 何時讀：第一次安裝 SDK、跑出第一個代理時。
- 關鍵內容：
  - 前置：Node.js 18.14+ 或 Python 3.10+
  - 安裝：`npm install @anthropic-ai/claude-agent-sdk` 或 `pip install claude-agent-sdk`
  - 驗證：設 `ANTHROPIC_API_KEY` 環境變數
  - 核心呼叫：`query(prompt, options)` 回傳非同步訊息串流
  - `allowedTools`（Read/Edit/Glob…）決定可用工具，`permissionMode` 決定是否需核准
  - 可在選項調整 system prompt、工具集、權限與模型
- 新名詞：`query()` ＝ SDK 的主入口，回傳訊息串流
- 記憶系統接點：無

### 遷移至 Claude Agent SDK（`agent-sdk/migration-guide`）
- 檔案：[agent-sdk__migration-guide.md](agent-sdk__migration-guide.md)｜https://code.claude.com/docs/zh-TW/agent-sdk/migration-guide｜lastmod 2026-10-09｜7KB
- 一句話：Claude Code SDK 改名 Claude Agent SDK 的套件、匯入與破壞性變更對照。
- 何時讀：舊專案要從 claude-code-sdk 升級，或查 v0.1.0 行為變更時。
- 關鍵內容：
  - TS 套件 `@anthropic-ai/claude-code` → `@anthropic-ai/claude-agent-sdk`；Python `claude-code-sdk` → `claude-agent-sdk`
  - Python `ClaudeCodeOptions` 改名 `ClaudeAgentOptions`，匯入 `claude_code_sdk` → `claude_agent_sdk`
  - 破壞性變更一：不再預設用 Claude Code system prompt，要 `systemPrompt: {type:'preset',preset:'claude_code'}` 才還原
  - 破壞性變更二：settingSources 預設曾短暫改為不載入，後已還原；省略即載入 user/project/local
  - 隔離檔案系統設定：`settingSources: []`（Python `setting_sources=[]`，0.1.59 以前空清單等同省略）
  - 隔離對 CI/CD、多租戶、測試環境特別重要
- 新名詞：`preset: claude_code` ＝ 沿用 Claude Code CLI 那份完整 system prompt 的選項
- 記憶系統接點：system prompt 預設已非 Claude Code 版；CLAUDE.md/規則注入仍靠 settingSources，與 system prompt 設定互不相干

### 排除 Agent SDK 的故障（`agent-sdk/troubleshooting`）
- 檔案：[agent-sdk__troubleshooting.md](agent-sdk__troubleshooting.md)｜https://code.claude.com/docs/zh-TW/agent-sdk/troubleshooting｜lastmod 2026-10-20｜14KB
- 一句話：SDK 啟動失敗、CLI 程序退出與結構化輸出為空的錯誤對照表。
- 何時讀：遇到 CLINotFoundError、ProcessError 或 structured_output 為 None 時。
- 關鍵內容：
  - `CLINotFoundError`：找不到 `claude` 執行檔，可用 `cli_path` 指定
  - Windows 上 `.bat/.cmd` 填充程式會觸發 `CLIConnectionError: Refusing to execute batch script`
  - `CLIConnectionError: Not connected`：`ClaudeSDKClient` 未連線或已斷開就呼叫方法
  - `ProcessError: Command failed with exit code`：CLI 非零退出
  - `Claude Code returned an error result`：CLI 退出前已回報錯誤結果，兩 SDK 以此取代退出錯誤
  - `success` 但 `structured_output` 為空：執行完成但無驗證過的輸出
- 新名詞：`CLIConnectionError` ＝ SDK 連不上或啟動不了 CLI 子程序的錯誤
- 記憶系統接點：無

## 核心概念（Core concepts）

### 代理程式迴圈如何運作（`agent-sdk/agent-loop`）
- 檔案：[agent-sdk__agent-loop.md](agent-sdk__agent-loop.md)｜https://code.claude.com/docs/zh-TW/agent-sdk/agent-loop｜lastmod 2026-11-03｜41KB
- 一句話：說明代理迴圈：回合、五種訊息、工具執行、上下文累積與自動壓縮。
- 何時讀：想理解一個 query 內部怎麼跑、何時停、context 怎麼長大時。
- 關鍵內容：
  - 回合＝Claude 輸出→執行工具→結果回饋，直到無工具呼叫才結束
  - 五種訊息：`SystemMessage`（init/compact_boundary/informational…）、`AssistantMessage`、`UserMessage`、`StreamEvent`、`ResultMessage`
  - 唯讀工具（Read/Glob/Grep）可並行；Edit/Write/Bash 序列執行
  - 上限：`maxTurns`、`maxBudgetUsd`，終止子類型 `error_max_turns`/`error_max_budget_usd`/`error_during_execution`
  - `effort` 控制推理深度；`permissionMode` 控制核准
  - 接近上限自動壓縮並發 `system/compact_boundary`；系統提示、CLAUDE.md 等穩定內容自動走 prompt cache
  - 省 context：子代理只回傳摘要、限縮 `tools`、MCP 工具搜尋、低 effort
- 新名詞：`turn（回合）` ＝ Claude 一次輸出加工具執行的往返；`compact_boundary` ＝ 自動壓縮發生時串流中的系統訊息
- 記憶系統接點：SDK 支援 `PreCompact`/`PostCompact` hook 與 compact_boundary 訊息，可在壓縮前後介入；CLAUDE.md 穩定內容走 prompt cache

### 在 SDK 中使用 Claude Code 功能（`agent-sdk/claude-code-features`）
- 檔案：[agent-sdk__claude-code-features.md](agent-sdk__claude-code-features.md)｜https://code.claude.com/docs/zh-TW/agent-sdk/claude-code-features｜lastmod 2026-10-29｜21KB
- 一句話：SDK 如何載入 CLAUDE.md、rules、skills、hooks 等檔案系統功能，及 settingSources 控制。
- 何時讀：要決定 SDK 代理吃不吃使用者/專案設定，或選哪種擴充機制時。
- 關鍵內容：
  - `settingSources`: `"user"`(~/.claude)、`"project"`(<cwd>/.claude)、`"local"`(settings.local.json)；省略＝全載入，`[]`＝隔離
  - CLAUDE.md 各層累加無硬優先序：專案根、父目錄、子目錄(按需)、`CLAUDE.local.md`、`~/.claude/CLAUDE.md`、`~/.claude/rules/*.md`
  - 不受 settingSources 控制：受管政策、`~/.claude.json`、自動記憶 `~/.claude/projects/<p>/memory/`、claude.ai MCP 連接器
  - 自動記憶預設載入 system prompt，關閉用 `autoMemoryEnabled:false` 或 `CLAUDE_CODE_DISABLE_AUTO_MEMORY`
  - Hooks 兩種並行：檔案系統(settings.json: command/http/mcp_tool/prompt)與程式化 callback
  - 選擇表：CLAUDE.md＝慣例、Skills＝按需知識、子代理＝隔離子任務、Hooks＝確定性邏輯、MCP＝外部工具
- 新名詞：`settingSources` ＝ 指定 SDK 要載入哪幾層檔案系統設定的選項
- 記憶系統接點：SDK 預設載入 `~/.claude/CLAUDE.md`、rules、skills、settings 與其 hooks，現有記憶注入 hook 在 SDK 內也會觸發；`settingSources:[]` 可整個隔離；自動記憶路徑不受控須另用 env 關閉

### 使用 sessions（`agent-sdk/sessions`）
- 檔案：[agent-sdk__sessions.md](agent-sdk__sessions.md)｜https://code.claude.com/docs/zh-TW/agent-sdk/sessions｜lastmod 2026-10-10｜23KB
- 一句話：Session 是 SDK 自動寫磁碟的對話歷史，可 continue、resume、fork。
- 何時讀：要在多個 query 間延續上下文、分支探索或跨主機恢復時。
- 關鍵內容：
  - 三選項：continue（最近一個）、`resume`（指定 ID）、`forkSession`（複製歷史另開新 ID）
  - Python `ClaudeSDKClient` 自動沿用同 session；TS 用 `continue: true`
  - session ID 取自 `ResultMessage.session_id`（TS 也在 init SystemMessage）
  - 檔案位置 `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`，只在建立它的機器上
  - 跨主機三法：`sessionStore` 配接器、搬 jsonl 檔、不依賴恢復而把結果傳入新 prompt
  - 管理函式：`listSessions()`、`getSessionMessages()`、`getSessionInfo()`、`renameSession()`、`tagSession()`、`forkSession()`
- 新名詞：`fork` ＝ 複製既有 session 歷史成新 session，原本不變
- 記憶系統接點：session 逐字稿存 `~/.claude/projects/` 的 jsonl，SDK 有 list/get/rename/tag API 可程式化讀取

### 將工作階段持久化到外部儲存（`agent-sdk/session-storage`）
- 檔案：[agent-sdk__session-storage.md](agent-sdk__session-storage.md)｜https://code.claude.com/docs/zh-TW/agent-sdk/session-storage｜lastmod 2026-10-29｜24KB
- 一句話：用 SessionStore 介面把 session 逐字稿鏡像到自己的物件儲存/資料庫。
- 何時讀：容器或多主機部署需要 session 可跨機恢復、或要客製存放位置時。
- 關鍵內容：
  - `SessionStore` 兩必要方法 `append`、`load`；四選用 `listSessions`、`listSessionSummaries`、`delete`、`listSubkeys`
  - 選項 `sessionStore` / Python `session_store`；`sessionStoreFlush`: `batched`(預設)/`eager`
  - 雙寫：CLI 子程序先寫本機磁碟，SDK 再轉發 `append()`，儲存區是鏡像非替代
  - append 失敗重試最多共 3 次，仍失敗發 `{type:'system',subtype:'mirror_error'}` 並丟棄該批
  - resume 時 SDK 先向儲存區取逐字稿再產生子程序；`loadTimeoutMs` 預設 60000
  - `getSessionMessages` 回傳壓縮後鏈；完整原始用 `store.load(key)`；子代理逐字稿在 `subagents/agent-<id>`
  - SDK 不自動刪資料，保留期限由配接器負責；自帶 `InMemorySessionStore`、一致性測試套件
- 新名詞：`SessionStore` ＝ SDK 定義的 session 逐字稿外部儲存介面；`mirror_error` ＝ 鏡像寫入失敗時串流中的系統訊息
- 記憶系統接點：SDK 專屬：可把 transcript 寫到自訂後端（含 DB），CLI 固定寫 `~/.claude/projects`；`CLAUDE_CONFIG_DIR` 亦可改位置

## 建構代理（Build agents）

### 設定您的代理（`agent-sdk/configuration`）
- 檔案：[agent-sdk__configuration.md](agent-sdk__configuration.md)｜https://code.claude.com/docs/zh-TW/agent-sdk/configuration｜lastmod 2026-10-27｜19KB
- 一句話：彙整 options 物件、設定檔、模型、env、cwd、預算等組態入口。
- 何時讀：要查某功能對應哪個選項，或調整模型/環境/上限時。
- 關鍵內容：
  - 選項對照表：`permissionMode`、`allowedTools`、`canUseTool`、`systemPrompt`、`settingSources`、`mcpServers`、`agents`、`hooks`、`skills`、`plugins`、`outputFormat`、`resume`、`sessionStore`、`enableFileCheckpointing`、`effort`、`sandbox`
  - `settings` 選項接路徑或內嵌 JSON，覆蓋 user/project/local，只輸給受管政策
  - `fallbackModel` 主模型過載時切備援，可逗號分隔多個
  - `env` 在 TS 取代子程序環境（需展開 `...process.env`），Python 為合併
  - `cwd` 無 setter，換目錄需另開 session
  - `maxTurns`/`maxBudgetUsd` 預設關閉；串流輸入可中途切換模型與權限模式
- 新名詞：`fallbackModel` ＝ 主模型不可用時自動切換的備援模型
- 記憶系統接點：`settings`/`env`/`settingSources` 可在程式端覆寫分層；`CLAUDE_CONFIG_DIR` 重定位設定根目錄

### 範例（`agent-sdk/examples`）
- 檔案：[agent-sdk__examples.md](agent-sdk__examples.md)｜https://code.claude.com/docs/zh-TW/agent-sdk/examples｜lastmod 2026-10-21｜2KB
- 一句話：指向官方範例專案與 Cookbook 配方的導覽頁。
- 何時讀：想找可直接複製的完整 SDK 範例時。
- 關鍵內容：
  - 示範應用在 `claude-agent-sdk-demos` 儲存庫（含 hello-world）
  - Cookbook Agent SDK 系列為 Python 筆記本，由單行研究代理到多代理系統
  - 另有 Claude for commerce 參考實作（購物/商家代理）
- 新名詞：`Cookbook` ＝ Anthropic 的配方筆記本集合
- 記憶系統接點：無

## 以工具擴充（Extend with tools）

### 為 Claude 提供自訂工具（`agent-sdk/custom-tools`）
- 檔案：[agent-sdk__custom-tools.md](agent-sdk__custom-tools.md)｜https://code.claude.com/docs/zh-TW/agent-sdk/custom-tools｜lastmod 2026-10-26｜42KB
- 一句話：用同程序 MCP 伺服器在 SDK 內定義 Claude 可呼叫的自訂工具。
- 何時讀：想讓代理呼叫自己的函式（DB、API、領域邏輯）時。
- 關鍵內容：
  - TS `tool()` + `createSdkMcpServer()`；Python `@tool` + `create_sdk_mcp_server()`；經 `mcpServers` 傳入
  - 工具全名 `mcp__<server>__<tool>`，`allowedTools` 可用 `mcp__weather__*` 萬用字元
  - 工具由 name、description、input schema、handler 四部分組成；可附 annotations（`readOnlyHint:true` 允許並行）
  - handler 例外被捕捉成錯誤結果，用 `isError:true` 控制 Claude 看到的訊息
  - 結果 `content` 支援 text/image/audio/resource/resource_link，另有 `structuredContent`
  - TS 可設 `permission_policy: always_ask/always_deny` 強制每次核准或封鎖
- 新名詞：`in-process MCP server` ＝ 與應用同程序執行、不需獨立子程序的 MCP 伺服器
- 記憶系統接點：SDK 專屬：可在程式內直接註冊 MCP 工具（無需獨立 server 程序）；工具名遵循 mcp__ 前綴，與現有 MCP 權限命名一致

### 使用 MCP 連接外部工具（`agent-sdk/mcp`）
- 檔案：[agent-sdk__mcp.md](agent-sdk__mcp.md)｜https://code.claude.com/docs/zh-TW/agent-sdk/mcp｜lastmod 2026-10-22｜41KB
- 一句話：在 SDK 設定 MCP 伺服器：傳輸類型、授權、工具搜尋、逾時與錯誤處理。
- 何時讀：要把外部服務接進代理，或排查 MCP 連線失敗、輸出過大時。
- 關鍵內容：
  - 設定來源：`mcpServers` 選項，或 `settingSources` 含 project 時載入 `.mcp.json`
  - 傳輸：stdio、HTTP、SSE，以及 SDK 同程序伺服器；`strictMcpConfig` 只認傳入的伺服器
  - 權限：MCP 工具須在 `allowedTools` 明列（`mcp__server__*`）否則看得到但不能呼叫
  - 連線時序：`init` 訊息含伺服器狀態；`CLAUDE_CODE_MCP_STARTUP_WAIT_MS` 調首輪等待；`MCP_TIMEOUT`(連線預設 30 秒)、`MCP_TOOL_TIMEOUT`
  - 工具結果超過 25,000 token 會存成檔案並回傳路徑提示
  - SDK 不開瀏覽器；OAuth2 遇授權挑戰時由應用處理，header/env 可傳憑證
- 新名詞：`MCP 工具搜尋` ＝ 隱藏 MCP 工具定義、每回合只載入需要者以省 context
- 記憶系統接點：MCP 工具命名 `mcp__<server>__<tool>` 可被 PreToolUse matcher 與 allowedTools 比對；`.mcp.json` 於 project 來源自動載入

### SDK 中的子代理（`agent-sdk/subagents`）
- 檔案：[agent-sdk__subagents.md](agent-sdk__subagents.md)｜https://code.claude.com/docs/zh-TW/agent-sdk/subagents｜lastmod 2026-10-21｜42KB
- 一句話：在 SDK 以 agents 參數定義子代理，隔離上下文、並行與限制工具。
- 何時讀：要把子任務委派給獨立上下文的代理、或調整子代理權限/預算時。
- 關鍵內容：
  - 建立：`agents` 參數程式化（推薦）或 `.claude/agents/*.md`；程式化定義優先於同名檔案
  - `AgentDefinition` 欄位：`description`、`prompt`、`tools`、`disallowedTools`、`model`、`skills`、`memory`(user/project/local)、`mcpServers`、`initialPrompt`、`maxTurns`、`autoCompactWindow`
  - 需在主代理 `allowedTools` 含 `Agent`；以 `tool_use` 名稱為 `Agent` 偵測呼叫
  - 子代理上下文全新：只收到 Agent 工具的 prompt 字串，加專案 CLAUDE.md 與工具定義，不含父對話
  - 預設背景執行；可 resume 保留完整歷史；fork 型子代理複製目前對話(v2.1.302+)
  - 子代理輸出會被掃描：中和 `<system-reminder>` 仿冒標籤、`Human:`/`Assistant:` 回合標記(v2.1.210+)
  - `AskUserQuestion` 在子代理內不可用；成本計入 `total_cost_usd`，需限深度/並行/支出
  - 權限模式 plan/acceptEdits/auto/bypassPermissions 會被子代理繼承
- 新名詞：`fork subagent` ＝ 複製目前對話內容再開始的子代理；`AgentDefinition` ＝ SDK 內定義子代理的設定物件
- 記憶系統接點：`AgentDefinition.memory`（user/project/local）可指定子代理記憶來源；子代理只靠 prompt 字串傳遞上下文，hook 輸入帶 `agent_id`/`agent_type` 可區分來源；SubagentStart/Stop 為 hook 事件

### 使用工具搜尋擴展到許多工具（`agent-sdk/tool-search`）
- 檔案：[agent-sdk__tool-search.md](agent-sdk__tool-search.md)｜https://code.claude.com/docs/zh-TW/agent-sdk/tool-search｜lastmod 2026-10-21｜12KB
- 一句話：工具搜尋讓代理在數百到上萬工具中按需發現、載入，不撐爆 context。
- 何時讀：掛了大量 MCP/自訂工具、context 被工具定義吃掉時。
- 關鍵內容：
  - 預設開啟；環境變數 `ENABLE_TOOL_SEARCH`：未設/`true`/`auto`/`auto:N`/`false`
  - `auto:5` 表示可延遲定義達 context 5% 才啟用
  - 上限：目錄最多 10,000 工具；每次搜尋預設回最多 5 個
  - 適用遠端 MCP 與 SDK 同程序 MCP 伺服器
  - `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS` 會使其保持關閉
  - 工具名與描述含具體關鍵字，搜尋命中率較高
- 新名詞：`tool search` ＝ 以搜尋方式延後載入工具定義的機制
- 記憶系統接點：工具定義延後載入可降低常駐 context；與 MCP 工具搜尋同機制

## 客製行為（Customize behavior）

### 修改系統提示詞（`agent-sdk/modifying-system-prompts`）
- 檔案：[agent-sdk__modifying-system-prompts.md](agent-sdk__modifying-system-prompts.md)｜https://code.claude.com/docs/zh-TW/agent-sdk/modifying-system-prompts｜lastmod 2026-10-27｜36KB
- 一句話：SDK 修改 system prompt 的四法：CLAUDE.md、輸出樣式、preset append、完全自訂。
- 何時讀：要改代理人格/指令，或最佳化跨使用者 prompt cache 時。
- 關鍵內容：
  - 三起點：最小預設（省略時，無安全指令）、`{type:'preset',preset:'claude_code'}`、自訂字串
  - `append` 在 preset 後追加；自訂字串整個取代並遺失內建工具指令與安全指令
  - `excludeDynamicSections:true` 把自動記憶位置等每人不同內容移到首個 user 訊息，改善 cache 共用
  - TS 可傳字串陣列，用 `SYSTEM_PROMPT_DYNAMIC_BOUNDARY` 分靜態/動態段
  - `snapshot` 預設記錄首次請求的 system prompt，resume 時改 append 不生效直到壓縮；`snapshot:false` 每次重建
  - CLAUDE.md、hook `additionalContext`、skills/子代理清單、檔案變更備註以 system-reminder 注入對話而非 system prompt
  - 關內建上下文：`includeGitInstructions:false`、`CLAUDE_CODE_DISABLE_CLAUDE_MDS`、`CLAUDE_CODE_DISABLE_ATTACHMENTS`、`CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS`
  - 輸出樣式存於 `~/.claude/output-styles/` 或專案 `.claude/output-styles/`
- 新名詞：`system-reminder` ＝ Claude Code 插在對話中的上下文提示訊息（非 system prompt）；`output style（輸出樣式）` ＝ 存成 markdown 的角色/語氣/格式指令組
- 記憶系統接點：SDK 專屬：可程式化 append/取代 system prompt、`snapshot` 與 dynamic boundary；hook 回傳的 `additionalContext` 走 system-reminder 路徑，與 CLAUDE.md 同層注入；自動記憶位置會寫進 preset 影響 cache

### SDK 中的 Plugins（`agent-sdk/plugins`）
- 檔案：[agent-sdk__plugins.md](agent-sdk__plugins.md)｜https://code.claude.com/docs/zh-TW/agent-sdk/plugins｜lastmod 2026-10-26｜13KB
- 一句話：在 SDK 以本機路徑載入 plugins（skills、agents、hooks、MCP 伺服器）。
- 何時讀：要在 SDK 代理中重用打包好的擴充，或排查 plugin 未載入時。
- 關鍵內容：
  - `plugins: [{type:'local', path:'./my-plugin'}]`，`type` 只接受 `"local"`
  - 路徑可相對或絕對；可同時載入多個來源
  - TS 可在執行中呼叫 `Query.reloadPlugins()` 並以 `addPlugins` 追加
  - plugin skills 加命名空間 `/plugin-name:skill-name`
  - 結構：`.claude-plugin/plugin.json`（可省略，會自動探索元件）
  - 載入結果在 init 訊息的 `plugins` 列表，失敗看 `plugin_errors`
- 新名詞：`plugin` ＝ 可打包 skills/agents/hooks/MCP 的擴充單位
- 記憶系統接點：plugin 內可帶 hooks 與 MCP，與 settingSources 載入的 hooks 並行；SDK 僅支援本機路徑載入

### 使用 Skills 擴展 Agent（`agent-sdk/skills`）
- 檔案：[agent-sdk__skills.md](agent-sdk__skills.md)｜https://code.claude.com/docs/zh-TW/agent-sdk/skills｜lastmod 2026-10-23｜28KB
- 一句話：在 SDK 控制 skills 的探索與叫用，並介紹 SDK 會話中的斜線命令。
- 何時讀：要限制 Claude 能用哪些 skill，或用程式派送 `/command` 時。
- 關鍵內容：
  - Skills 是檔案系統成品 `SKILL.md`（`.claude/skills/<name>/`），SDK 沒有程式化註冊 API
  - `skills` 選項：省略＝探索到的皆啟用、`'all'`、名稱清單、`[]`＝全禁；設定後自動把 `Skill` 加進 `allowedTools`
  - 需 `settingSources` 含 user/project 才會探索；init 訊息的 `skills` 陣列可確認
  - 命令：init 訊息的 `slash_commands` 列出；送 `/<name>` 即派送，不受 `skills` 清單限制
  - `/compact` 壓縮歷史（發 `compact_boundary`）、`/clear` 重設上下文（舊對話仍可 resume）
  - 需互動終端的命令(`/theme`等)不可用；叫用未列名 skill 回 allowlist 錯誤
- 新名詞：`slash_commands` ＝ init 訊息中列出會話可用命令的欄位
- 記憶系統接點：skills 從 `~/.claude/skills` 與專案載入，僅描述常駐、全文按需載入；SDK 可用 `skills` 白名單縮限，可程式化送 `/compact`、`/clear` 管理 context

## 輸入與輸出（Input and output）

### 即時串流回應（`agent-sdk/streaming-output`）
- 檔案：[agent-sdk__streaming-output.md](agent-sdk__streaming-output.md)｜https://code.claude.com/docs/zh-TW/agent-sdk/streaming-output｜lastmod 2026-10-27｜15KB
- 一句話：開啟 partial messages 即時串流文字與工具呼叫的增量事件。
- 何時讀：要做即時打字效果或顯示工具進度 UI 時。
- 關鍵內容：
  - 選項 `includePartialMessages`(TS) / `include_partial_messages`(Python)=true
  - 會多出 `StreamEvent`（TS `SDKPartialAssistantMessage`）包裝原始 API 串流事件
  - 預設每完成一個非空內容區塊才發一次 `AssistantMessage`
  - 工具呼叫的輸入以 `input_json_delta` 逐步串流
  - 串流中斷時仍會收到該訊息的 `message_stop`
  - 限制：結構化輸出時 JSON 以未驗證 delta 串流，僅最終 `ResultMessage.structured_output` 為驗證後結果
- 新名詞：`StreamEvent` ＝ 啟用部分訊息時封裝原始 API 串流事件的訊息
- 記憶系統接點：無

### 串流輸入（`agent-sdk/streaming-vs-single-mode`）
- 檔案：[agent-sdk__streaming-vs-single-mode.md](agent-sdk__streaming-vs-single-mode.md)｜https://code.claude.com/docs/zh-TW/agent-sdk/streaming-vs-single-mode｜lastmod 2026-10-02｜9KB
- 一句話：比較串流輸入（持久互動 session）與單一訊息輸入兩種模式。
- 何時讀：決定 query 的 prompt 該傳字串還是 AsyncIterable 時。
- 關鍵內容：
  - 串流輸入為推薦：prompt 傳 `AsyncIterable<SDKUserMessage>`
  - 優點：影像上傳、佇列訊息可中斷、完整工具與自訂 MCP、即時回饋、上下文持久
  - 單一訊息輸入：一次性、無狀態環境（如 Lambda）適用
  - 單一訊息不支援影像附件、動態訊息佇列、中斷
  - 單次 `query()` 遇錯誤結果(如 `error_max_turns`)會在產出結果訊息後拋例外，需 try 包住
- 新名詞：`streaming input` ＝ 以非同步生成器持續餵入使用者訊息的輸入模式
- 記憶系統接點：串流輸入模式才能在 session 中途切換模型/權限模式、接收中斷

### 從代理獲取結構化輸出（`agent-sdk/structured-outputs`）
- 檔案：[agent-sdk__structured-outputs.md](agent-sdk__structured-outputs.md)｜https://code.claude.com/docs/zh-TW/agent-sdk/structured-outputs｜lastmod 2026-10-21｜22KB
- 一句話：用 JSON Schema/Zod/Pydantic 要求代理最終輸出經驗證的 JSON。
- 何時讀：要讓代理結果能直接進程式邏輯、資料庫或 UI 時。
- 關鍵內容：
  - 選項 `outputFormat: {type:'json_schema', schema}`；Python `output_format`
  - Zod 與 Pydantic 可產 schema 並回解析成型別物件
  - 結果在 `ResultMessage.structured_output`
  - 串流中會出現非自訂的 `StructuredOutput` 工具呼叫
  - 失敗子類型 `error_max_structured_output_retries`；`success` 卻無 `structured_output` 也視為失敗
  - 多步驟工具使用後最終仍回符合 schema 的 JSON
- 新名詞：`StructuredOutput 工具` ＝ Claude Code 自動加入、用來回傳結構化結果的內部工具
- 記憶系統接點：SDK 端會驗證 JSON Schema，可作為輸出格式驗證手段

### 處理批准和使用者輸入（`agent-sdk/user-input`）
- 檔案：[agent-sdk__user-input.md](agent-sdk__user-input.md)｜https://code.claude.com/docs/zh-TW/agent-sdk/user-input｜lastmod 2026-10-25｜35KB
- 一句話：用 canUseTool 回呼與 AskUserQuestion 把核准請求與澄清問題交給使用者。
- 何時讀：要在自己的 UI 處理工具核准或 Claude 的提問時。
- 關鍵內容：
  - `canUseTool` 回呼：權限流程前面步驟都未決定時才觸發（dontAsk 不呼叫）
  - 回應：允許 `{behavior:'allow', updatedInput}` / `PermissionResultAllow(updated_input)`；拒絕 `{behavior:'deny', message}`
  - `AskUserQuestion` 工具以 `toolName` 觸發回呼，回傳 `answers` 物件（question→label）
  - TS `toolConfig.askUserQuestion.previewFormat` 為選項加預覽
  - 支援自由文字輸入
  - 限制：子代理內 `AskUserQuestion` 不可用
  - 其他管道：串流輸入、自訂工具
- 新名詞：`canUseTool` ＝ SDK 專屬的工具核准回呼函式
- 記憶系統接點：SDK 專屬：核准決策可由程式回呼完成（可改寫輸入），CLI 只有互動彈窗與 hook

## 控制與可觀測性（Control and observability）

### 追蹤成本和使用量（`agent-sdk/cost-tracking`）
- 檔案：[agent-sdk__cost-tracking.md](agent-sdk__cost-tracking.md)｜https://code.claude.com/docs/zh-TW/agent-sdk/cost-tracking｜lastmod 2026-11-02｜27KB
- 一句話：說明 usage、total_cost_usd、modelUsage 與 prompt cache 的成本追蹤規則。
- 何時讀：要統計花費、拆模型成本或處理平行工具導致重複計數時。
- 關鍵內容：
  - `ResultMessage.total_cost_usd`、`usage`、`modelUsage`（TS）/`model_usage`（Python）
  - 層級：query() 呼叫、步驟(單次請求/回應)、session(以 resume 串起)
  - 平行工具會有多個助手訊息共用同 `id`，要依 ID 去重避免膨脹
  - 助手訊息的 `output_tokens` 是 message_start 預留值，真實值看結果訊息
  - `usage` 排除子代理，`modelUsage` 含子代理的各模型成本
  - CLI 程序當機時最終 `error_during_execution` 可能歸零，需自行復原已累計值
  - 快取欄位：`cache_creation_input_tokens`、`cache_read_input_tokens`；可延長 TTL 到一小時
- 新名詞：`modelUsage` ＝ 結果訊息中按模型拆分的 token 與成本；`cache_read_input_tokens` ＝ 從 prompt cache 讀入的 token 數
- 記憶系統接點：`total_cost_usd` 與 token 可從 ResultMessage 取得，可作為 session 成本記帳來源

### 使用 checkpointing 回溯檔案變更（`agent-sdk/file-checkpointing`）
- 檔案：[agent-sdk__file-checkpointing.md](agent-sdk__file-checkpointing.md)｜https://code.claude.com/docs/zh-TW/agent-sdk/file-checkpointing｜lastmod 2026-10-22｜28KB
- 一句話：啟用檔案 checkpoint，把 Write/Edit/NotebookEdit 改過的檔案回溯到某訊息時狀態。
- 何時讀：代理改壞檔案想一鍵還原，或要做多個還原點時。
- 關鍵內容：
  - 啟用 `enableFileCheckpointing` / `enable_file_checkpointing`
  - 從 user 訊息的 `uuid` 取得 checkpoint；呼叫 `rewindFiles(uuid)` / `rewind_files()`
  - 只追蹤 Write/Edit/NotebookEdit，不追蹤 Bash 造成的變更
  - 不追蹤子代理編輯、目錄建立/移動/刪除、遠端檔案；checkpoint 綁同一 session
  - 串流迭代結束後呼叫會出 `ProcessTransport is not ready for writing`，需 resume 後再 rewind
  - 錯誤：`No file checkpoint found for this message`、`File rewinding is not enabled`；CLI 有 `--rewind-files`
- 新名詞：`checkpoint` ＝ 在檔案被修改前保留的備份還原點
- 記憶系統接點：檔案回溯與 git 工作樹無關，只看 Write/Edit 工具

### 使用 hooks 攔截和控制代理行為（`agent-sdk/hooks`）
- 檔案：[agent-sdk__hooks.md](agent-sdk__hooks.md)｜https://code.claude.com/docs/zh-TW/agent-sdk/hooks｜lastmod 2026-11-03｜48KB
- 一句話：SDK 程式化 hook callback：在 Python/TS 函式中攔截、改寫或阻止代理行為。
- 何時讀：要用程式碼做權限決策、改寫工具輸入、注入上下文或審計時。
- 關鍵內容：
  - 註冊於選項 `hooks`：`{ PreToolUse: [{matcher:'Bash', hooks:[cb], timeout, onFailure}] }`；callback 收 (input, tool_use_id, context)
  - 兩 SDK 皆有：PreToolUse/PostToolUse/PostToolUseFailure/UserPromptSubmit/Stop/SubagentStart/SubagentStop/PreCompact/PermissionRequest/Notification
  - 僅 TS：SessionStart、SessionEnd、Setup、PostToolBatch、PostCompact、PreModelSwitch/PostModelSwitch、TaskCreated/TaskCompleted、Elicitation、ConfigChange、MessageDisplay 等
  - 輸出：`hookSpecificOutput.permissionDecision`(allow/deny/ask/defer)、`updatedInput`、`additionalContext`、`updatedToolOutput`；頂層 `systemMessage`、`continue`
  - 多 hook 並行；衝突時 deny > defer > ask > allow
  - 失敗預設放行並發 `hook_callback_failed`；`onFailure:'block'` 可改為阻擋(TS ≥0.3.317/Python ≥0.2.177)
  - 逾時預設 600 秒，UserPromptSubmit/Pre-PostModelSwitch 30 秒，MessageDisplay 10 秒
  - matcher 只比對工具名稱，檔案路徑須在 callback 內查 `tool_input.file_path`
  - 非同步輸出可讓 agent 立刻繼續；檔案系統 hook(settings.json)與程式化 hook 並行，子代理內也會執行
- 新名詞：`hook callback` ＝ 註冊在選項裡的程式化函式，非 shell 命令；`onFailure` ＝ callback 失敗時選擇放行或阻擋的設定
- 記憶系統接點：SDK 專屬：in-process callback 可直接回傳 `additionalContext`/`updatedInput`/`updatedToolOutput`；Python 無 SessionStart/SessionEnd callback 只能走 settings.json 的 shell hook；`PermissionRequest`、`PreCompact` 可介入；`UserPromptSubmit` 在子代理觸發須防遞迴

### 使用 OpenTelemetry 進行可觀測性（`agent-sdk/observability`）
- 檔案：[agent-sdk__observability.md](agent-sdk__observability.md)｜https://code.claude.com/docs/zh-TW/agent-sdk/observability｜lastmod 2026-10-23｜18KB
- 一句話：用 OpenTelemetry 匯出 SDK 代理的 traces、metrics、log events。
- 何時讀：上線代理要監控 token/成本、工具耗時與追蹤鏈路時。
- 關鍵內容：
  - 啟用：env `CLAUDE_CODE_ENABLE_TELEMETRY=1` 加匯出器（`OTEL_TRACES_EXPORTER`/`OTEL_METRICS_EXPORTER`/`OTEL_LOGS_EXPORTER`=otlp）
  - traces 為 beta，需 `CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1`
  - span：`claude_code.interaction`、`.llm_request`、`.tool`(含 `tool.blocked_on_user`/`tool.execution`)、`.hook`
  - SDK 自動把 W3C `TRACEPARENT`/`TRACESTATE` 注入子程序
  - 預設 `service.name=claude-code`，可覆寫並加資源屬性
  - 內容預設不輸出；開啟用 `OTEL_LOG_USER_PROMPTS`、`OTEL_LOG_TOOL_DETAILS`、`OTEL_LOG_TOOL_CONTENT`、`OTEL_LOG_RAW_API_BODIES`
  - 短命程序需降低匯出間隔以免 span 遺失
- 新名詞：`OTLP` ＝ OpenTelemetry 傳輸協定；`span` ＝ 追蹤中的單一步驟紀錄
- 記憶系統接點：遙測是 CLI 內建，SDK 以 env 傳入；提示與工具內容預設不匯出，需顯式開關（隱私邊界）

### 設定權限（`agent-sdk/permissions`）
- 檔案：[agent-sdk__permissions.md](agent-sdk__permissions.md)｜https://code.claude.com/docs/zh-TW/agent-sdk/permissions｜lastmod 2026-10-27｜34KB
- 一句話：SDK 權限評估六步流程、allow/deny 規則與六種權限模式。
- 何時讀：要設計代理能自動做什麼、何時需核准，或除錯為何 canUseTool 沒被呼叫時。
- 關鍵內容：
  - 評估順序：Hooks → deny 規則 → ask 規則 → 權限模式 → allow 規則 → `canUseTool`
  - 模式：`default`、`dontAsk`（提示一律轉拒絕）、`acceptEdits`、`bypassPermissions`、`plan`、`auto`（分類器模型審查）
  - `allowedTools`/`disallowedTools` 加入 allow/deny 規則；單純名稱 deny 會把工具移出 context
  - `bypassPermissions` 需 `allowDangerouslySkipPermissions`；仍擋關鍵路徑 `rm`，hook 仍會執行
  - 子代理繼承 plan/acceptEdits/auto/bypassPermissions
  - `plan` 模式編輯永遠不自動核准，改走 `canUseTool`
  - TS 若 canUseTool 被 bypass 或裸名稱 allowedTools 遮蔽，發 `CLAUDE_SDK_CAN_USE_TOOL_SHADOWED` 警告
  - `permissionPrompts:'none'`(TS) 時回呼不被呼叫
- 新名詞：`canUseTool shadowed` ＝ 回呼因更早步驟已核准而永遠不會被呼叫的狀況
- 記憶系統接點：PreToolUse 回 allow 不能跳過 deny/ask 規則；hook 在所有規則之前先執行，可作為寫入閘或審計入口

### 追蹤待辦事項（`agent-sdk/todo-tracking`）
- 檔案：[agent-sdk__todo-tracking.md](agent-sdk__todo-tracking.md)｜https://code.claude.com/docs/zh-TW/agent-sdk/todo-tracking｜lastmod 2026-10-20｜19KB
- 一句話：在 SDK 監看 TaskCreate/TaskUpdate/TodoWrite 的待辦清單進度。
- 何時讀：要把 Claude 的進度條或待辦列表顯示在自己應用時。
- 關鍵內容：
  - 預設只有 Opus 4.7、Sonnet 4.6、Haiku 4.5 及更早模型提供 Task 工具
  - 工具：`TodoWrite`、`TaskCreate`、`TaskGet`、`TaskUpdate`、`TaskList`；`CLAUDE_CODE_ENABLE_TASKS=0` 改用 TodoWrite
  - 監控方式：觀察助手訊息串流中的 `tool_use` 區塊
  - hook 事件 `TaskCreated`/`TaskCompleted`（僅 TS）可攔截
  - 多回合未更新時 Claude Code 會以 system-reminder 提示更新
- 新名詞：`TaskCreate/TaskUpdate` ＝ 新版任務追蹤工具，取代 TodoWrite
- 記憶系統接點：`TaskCreated`/`TaskCompleted` hook 可強制命名約定或要求測試通過；待辦提醒屬 system-reminder

## 部署（Deployment）

### 代理 SDK 的託管（`agent-sdk/hosting`）
- 檔案：[agent-sdk__hosting.md](agent-sdk__hosting.md)｜https://code.claude.com/docs/zh-TW/agent-sdk/hosting｜lastmod 2026-10-27｜24KB
- 一句話：說明 SDK 子程序模型，及容器部署時的 session 持久化、資源與多租戶隔離。
- 何時讀：要把代理部署成服務、規劃容器與狀態儲存時。
- 關鍵內容：
  - SDK 為每個 `query()` 產生獨立 `claude` CLI 子程序，經 stdio 溝通，持有 shell、工作目錄與 JSONL session
  - 預設本機磁碟狀態：session 逐字稿 `~/.claude/projects/`、CLAUDE.md 記憶、工作目錄成品，重啟即失
  - 四種 session 模式：短暫、長期執行、混合（容器啟動時從 SessionStore 補水）、多代理容器
  - 起始資源建議每代理 1 GiB 記憶體、5 GiB 磁碟、1 CPU；需出站 HTTPS 至 api.anthropic.com
  - 多租戶：`settingSources: []`、`CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`、每租戶 `CLAUDE_CONFIG_DIR`、各自 `cwd`、出站規則
  - 限制：無頂層 session 逾時（用 `maxTurns`）、長 session 記憶體成長、無子代理牆鐘截止（`CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS`）
- 新名詞：`subprocess model` ＝ SDK 以子程序方式驅動 CLI 的架構
- 記憶系統接點：`CLAUDE_CONFIG_DIR` 可移動整個設定/記憶根；自動記憶無視 settingSources 須用 env 關；記憶檔與工作成品需自備跨主機儲存

### 安全部署 AI 代理（`agent-sdk/secure-deployment`）
- 檔案：[agent-sdk__secure-deployment.md](agent-sdk__secure-deployment.md)｜https://code.claude.com/docs/zh-TW/agent-sdk/secure-deployment｜lastmod 2026-10-06｜20KB
- 一句話：AI 代理安全部署指南：威脅模型、隔離技術、認證代理與檔案系統配置。
- 何時讀：要把 Claude Code/SDK 放進高安全環境、避免提示注入外洩憑證時。
- 關鍵內容：
  - 威脅：提示注入與模型錯誤；原則：安全邊界、最小權限、深度防禦
  - 隔離技術：sandbox-runtime（OS 層）、容器、gVisor、虛擬機，強度與成本各異
  - 憑證管理建議用代理模式：代理在邊界外，替出站請求注入憑證
  - Claude Code 可經 `ANTHROPIC_BASE_URL` 或 `HTTP_PROXY/HTTPS_PROXY` 走代理
  - 其他服務憑證用自訂工具/MCP 在邊界外代呼叫
  - 檔案系統：唯讀程式碼掛載、可寫位置（tmpfs 或掛載卷）
- 新名詞：`sandbox-runtime` ＝ Anthropic 的 OS 級檔案系統/網路限制工具；`gVisor` ＝ 在使用者空間攔截系統呼叫的容器隔離層
- 記憶系統接點：無

## SDK 參考（SDK references）

### Agent SDK 參考 - Python（`agent-sdk/python`）
- 檔案：[agent-sdk__python.md](agent-sdk__python.md)｜https://code.claude.com/docs/zh-TW/agent-sdk/python｜lastmod 2026-11-03｜162KB
- 一句話：Python Agent SDK 完整 API 參考：函式、ClaudeSDKClient、型別、hooks、錯誤與沙箱。
- 何時讀：查 Python 側 query()、ClaudeAgentOptions 欄位或 hook 型別時。
- 關鍵內容：
  - `query()`（單次）vs `ClaudeSDKClient`（持續對話、支援 interrupt、自動延續 session）
  - 函式：`tool()`、`create_sdk_mcp_server()`、`list_sessions()`、`get_session_messages()`、`get_session_info()`、`rename_session()`、`tag_session()`、`fork_session()`
  - `ClaudeAgentOptions` 含 `system_prompt`（str/`SystemPromptPreset`/`SystemPromptCustom`/`SystemPromptFile`）、`setting_sources`、`session_store`、`can_use_tool`、`hooks`、`output_format`
  - Python `HookEvent` 僅 10 種：PreToolUse、PostToolUse、PostToolUseFailure、UserPromptSubmit、Stop、SubagentStop、PreCompact、Notification、SubagentStart、PermissionRequest
  - 錯誤型別：`ClaudeSDKError`、`CLINotFoundError`、`CLIConnectionError`、`ProcessError`、`CLIJSONDecodeError`
  - 訊息型別：`UserMessage`、`AssistantMessage`、`SystemMessage`、`ResultMessage`、`StreamEvent`、`TaskStartedMessage` 等
  - 含各內建工具輸入/輸出型別與 `SandboxSettings`
- 新名詞：`ClaudeSDKClient` ＝ Python 持續對話用的客戶端類別；`SystemPromptFile` ＝ 從檔案載入 system prompt 的設定型別
- 記憶系統接點：Python 的 hook callback 缺 SessionStart/SessionEnd；`SystemPromptFile` 對應 CLI `--system-prompt-file`

### Agent SDK 參考 - TypeScript（`agent-sdk/typescript`）
- 檔案：[agent-sdk__typescript.md](agent-sdk__typescript.md)｜https://code.claude.com/docs/zh-TW/agent-sdk/typescript｜lastmod 2026-11-03｜328KB
- 一句話：TypeScript Agent SDK 完整 API 參考：query()、Options、Query 控制方法、訊息與 hook 型別。
- 何時讀：查 TS 選項、Query 方法、hook 事件型別或工具輸入輸出 schema 時。
- 關鍵內容：
  - 函式：`query()`、`startup()`（預熱子程序）、`prewarm()`(alpha)、`tool()`、`createSdkMcpServer()`、`listSessions()`、`getSessionMessages()`、`getSessionInfo()`、`renameSession()`、`tagSession()`、`forkSession()`、`resolveSettings()`(alpha)
  - `Options` 專屬欄位：`sessionStore`、`systemPrompt`(字串陣列/preset)、`settings`、`managedSettings`、`projectConfigRoot`、`spawnClaudeCodeProcess`、`toolAliases`、`verbatimPrompts`、`planModeInstructions`、`taskBudget`
  - `Query` 物件方法：`interrupt`、`setPermissionMode`、`setModel`、`setMcpServers`、`reloadPlugins`、`reloadSkills`、`rewindFiles`、`getContextUsage`、`streamInput`、`updateSettings` 等
  - `HookEvent` 約 33 種，含 SessionStart/SessionEnd/InstructionsLoaded/CwdChanged/FileChanged/WorktreeCreate 等
  - 訊息型別 `SDKMessage` 聯合，含 hook 事件、task 通知、rate limit、permission denied 等
  - 附 30+ 內建工具輸入/輸出 schema（Agent、Bash、Edit、Workflow、Cron* 等）與 `SandboxSettings`
  - 約 330KB，宜依標題分段查閱：函式 61 行、Options 495、Query 599、Hook 2495、工具輸入 3237
- 新名詞：`startup()/prewarm()` ＝ 預先啟動 CLI 子程序以縮短首回應延遲；`spawnClaudeCodeProcess` ＝ 自訂如何在 VM/容器產生 CLI 程序的回呼
- 記憶系統接點：TS 最完整：`InstructionsLoaded`、`FileChanged`、`CwdChanged`、`ConfigChange` 等 hook 事件、`resolveSettings()` 預覽設定合併、`getContextUsage()` 查 context 使用、`updateSettings()` 執行中改設定

### TypeScript SDK V2 會話 API（已移除）（`agent-sdk/typescript-v2-preview`）
- 檔案：[agent-sdk__typescript-v2-preview.md](agent-sdk__typescript-v2-preview.md)｜https://code.claude.com/docs/zh-TW/agent-sdk/typescript-v2-preview｜lastmod 2026-09-10｜13KB
- 一句話：已移除的 V2 session API（createSession/send/stream）歷史參考。
- 何時讀：舊程式碼用到 unstable_v2_* 要遷移時。
- 關鍵內容：
  - V2 在 TS SDK 0.3.142 移除；0.2.x 為最後含 V2 的版本（固定 `@0.2`）
  - 被移除項目：`unstable_v2_createSession`、`unstable_v2_resumeSession`、`unstable_v2_prompt`、`SDKSession`、`SDKSessionOptions`
  - V2 概念：`send()` 送訊息、`stream()` 收回應、`close()`，支援 `await using`
  - 遷移：改用 `query()`；多輪傳 `AsyncIterable<SDKUserMessage>`，續接用 `options.resume`
  - V2 本就不支援 `forkSession` 與部分進階串流輸入
- 新名詞：`V2 session API` ＝ 已移除的實驗性 send/stream 會話介面
- 記憶系統接點：無

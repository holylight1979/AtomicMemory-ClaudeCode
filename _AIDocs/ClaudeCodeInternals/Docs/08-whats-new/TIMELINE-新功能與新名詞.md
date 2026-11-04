# Claude Code 2026 新功能與新名詞（TIMELINE）

> 資料來源：官方 changelog（`01-getting-started/changelog.md`，涵蓋 2.1.0 起至 2.1.318，2026-01-07 ～ 2026-11-04）＋ `08-whats-new/` 每週摘要（w13～w37，官方無 w31）。
> 週次＝ISO 週，與 what's new 同編號；w38 以後官方尚無週摘要，只有 changelog。`★` ＝ 跟 hooks／settings／memory／context／subagent／plugin／MCP 有關。
> 本檔只處理 2026 年版本；每版只挑 3～8 條代表項，bug 修復、效能微調、雲端／Gateway／VS Code 專屬項大多略過，需要細節請回 changelog 原文。只有修復的版本（如 2.1.291、2.1.294、2.1.303、2.1.306、2.1.308）不列。
> 對應頁 slug 見 `Docs/_manifest.json`；頁面檔案路徑 = manifest 的 `path`。

## 一、新名詞速查

| 名詞 | 白話 | 首次出現（版本・週） | 對應頁 slug |
|---|---|---|---|
| skills 熱重載／`context: fork` | skill 檔改了立刻生效；skill 可在分叉子代理中跑 | v2.1.0（01-07・w2） | skills |
| skill 與 slash command 合併 | 兩者並成同一個心智模型，行為不變 | v2.1.3（01-09・w2） | skills, commands |
| agent／skill frontmatter hooks | hook 可寫在 agent 或 skill 檔頭，只在其生命週期有效 | v2.1.0（01-07・w2） | hooks, skills, sub-agents |
| MCP tool search（自動） | MCP 工具描述超過 context 10% 時改成按需載入 | v2.1.7（01-14・w3） | mcp, agent-sdk/tool-search |
| Tasks 任務系統（TaskCreate 等） | 內建任務清單工具（後來在新模型移除） | v2.1.19（01-23・w4） | tools-reference |
| agent teams | 多個 Claude session 組隊協作（實驗性，需環境變數） | v2.1.32（02-05・w6） | agent-teams |
| auto memory（自動記憶） | Claude 工作時自動記錄與回想記憶 | v2.1.32（02-05・w6） | memory |
| agent `memory` frontmatter | agent 可帶 user／project／local 範圍的持久記憶 | v2.1.33（02-06・w6） | sub-agents, memory |
| `TeammateIdle`／`TaskCompleted` hooks | 隊友閒置、任務完成時觸發的 hook 事件 | v2.1.33（02-06・w6） | hooks, agent-teams |
| `--worktree`／`isolation: worktree` | 在獨立 git worktree 開 session 或讓 agent 在其中跑 | v2.1.49（02-19・w8） | worktrees |
| `ConfigChange` hook | 設定檔在 session 中被改動時觸發 | v2.1.49（02-19・w8） | hooks |
| `WorktreeCreate`／`WorktreeRemove` hooks | worktree 建立／移除時的客製 VCS 設定 hook | v2.1.50（02-20・w8） | hooks, worktrees |
| `claude remote-control` | 把本機 session 變成可從其他裝置接手的 Remote Control | v2.1.51（02-24・w9） | remote-control |
| managed settings（plist／Registry） | 由 macOS plist 或 Windows 登錄檔佈署管理設定 | v2.1.51（02-24・w9） | managed-settings |
| HTTP hooks | hook 直接 POST JSON 到 URL，不跑 shell | v2.1.63（02-28・w9） | hooks |
| `InstructionsLoaded` hook | CLAUDE.md 或 rules 載入 context 時觸發 | v2.1.69（03-05・w10） | hooks, memory |
| `/reload-plugins` | 不重啟就套用 plugin 變更 | v2.1.69（03-05・w10） | plugins/install |
| `/loop`＋cron 排程工具 | 在 session 內定時重跑 prompt 或指令 | v2.1.71（03-07・w10） | scheduled-tasks |
| MCP elicitation／`Elicitation` hooks | MCP server 中途要結構化輸入，hook 可攔截回應 | v2.1.76（03-14・w11） | mcp, hooks |
| `/effort` 與努力等級 | 調整模型思考力道（low/medium/high，後增 xhigh、max） | v2.1.76（03-14・w11） | model-config |
| `PostCompact` hook | 壓縮完成後觸發 | v2.1.76（03-14・w11） | hooks |
| `--channels`（channels） | 讓 MCP server 把訊息推進執行中的 session | v2.1.80（03-19・w12） | channels, channels-reference |
| `--bare` | 腳本化 `-p` 的極簡啟動，跳過 hooks、LSP、plugin 同步 | v2.1.81（03-20・w12） | headless, cli-reference |
| `managed-settings.d/` | 管理設定的分片目錄，多團隊各放政策片段 | v2.1.83（03-25・w13） | managed-settings |
| `CwdChanged`／`FileChanged` hooks | 工作目錄或檔案變動時觸發（direnv 式環境管理） | v2.1.83（03-25・w13） | hooks |
| PowerShell 工具 | Windows 原生 PowerShell 工具（先 opt-in，後預設） | v2.1.84（03-26・w13） | tools-reference |
| `TaskCreated` hook | 任務被建立時觸發 | v2.1.84（03-26・w13） | hooks |
| hook `if` 條件欄位 | 用權限規則語法限定 hook 何時啟動 | v2.1.85（03-26・w13） | hooks |
| auto mode（自動模式） | 分類器代審權限提示，擋危險操作 | w13（v2.1.83–85 週，研究預覽） | permission-modes, auto-mode-config |
| Computer use | Claude 看螢幕、點擊操作桌面 App（Desktop→CLI→背景） | w13 Desktop／w14 CLI | computer-use, desktop |
| `PermissionDenied` hook／`defer` 決策 | 分類器拒絕時觸發可重試；PreToolUse 可暫停待外部決定 | v2.1.89（04-01・w14） | hooks |
| 無閃爍渲染（fullscreen） | 虛擬化捲動的替代螢幕渲染器（`CLAUDE_CODE_NO_FLICKER`） | v2.1.89（04-01・w14） | fullscreen |
| `/powerup` | 終端內互動式功能課程 | v2.1.90（04-01・w14） | commands |
| plugin `bin/` 可執行檔 | plugin 內放執行檔，啟用後進 Bash 的 PATH | v2.1.91（04-02・w14） | plugins/components |
| `anthropic/maxResultSizeChars` | MCP 工具自訂結果截斷上限（至 500K） | v2.1.91（04-02・w14） | mcp |
| Monitor 工具 | 背景監看程序、事件串流進對話 | v2.1.98（04-09・w15） | tools-reference |
| Ultraplan（已移除） | 終端起雲端規劃模式 | w15 | （無專頁；2.1.222 移除） |
| `/team-onboarding` | 由本機用法產生團隊入職指南 | v2.1.101（04-10・w15） | commands |
| `/recap` | 回到 session 時的一行離開摘要 | v2.1.108（04-14・w16） | commands |
| 行動推播 | Claude 在長任務完成時推通知到手機 | v2.1.110（04-15・w16） | mobile, remote-control |
| `/ultrareview` | 雲端平行多代理深度程式碼審查 | v2.1.111（04-16・w16） | ultrareview |
| `xhigh` 努力等級 | 介於 high 與 max 的新等級 | v2.1.111（04-16・w16） | model-config |
| Routines | 雲端排程／事件／API 觸發的範本化 agent | w16 | routines |
| advisor（顧問工具） | 讓較強模型在困難決策提供建議（先實驗） | v2.1.117（04-22・w17） | advisor |
| fork subagent（`subagent_type: fork`） | 繼承完整對話與 prompt cache 的分叉子代理 | v2.1.117（04-22・w17）（2.1.232 起預設開） | sub-agents |
| hook `type: "mcp_tool"` | hook 直接呼叫 MCP 工具 | v2.1.118（04-23・w17） | hooks |
| 自訂主題 | 命名色彩主題，plugin 可提供 | v2.1.118（04-23・w17） | terminal-config |
| `/usage`（合併 /cost、/stats） | 單一用量面板，含歸因與細目 | v2.1.118（04-23・w17） | costs, analytics |
| MCP `alwaysLoad` | 該 server 的工具不被 tool search 延遲 | v2.1.121（04-28・w18） | mcp |
| PostToolUse `updatedToolOutput` | hook 可改寫任何工具的輸出 | v2.1.121（04-28・w18） | hooks |
| `claude project purge`→`claude purge` | 刪除專案全部本地狀態 | v2.1.126（05-01・w18）（更名 2.1.288） | cli-reference |
| `--plugin-url`／plugin zip | 從 URL 或 .zip 載入 plugin | v2.1.129（05-06・w19） | plugins/cli-reference |
| `worktree.baseRef` | 新 worktree 從遠端預設分支或本機 HEAD 分出 | v2.1.133（05-07・w19） | worktrees, settings-reference |
| `autoMode.hard_deny` | auto mode 中無條件封鎖的規則 | v2.1.136（05-08・w19） | auto-mode-config |
| agent view（`claude agents`） | 一個畫面管理全部 session | v2.1.139（05-11・w20） | agent-view |
| `/goal` | 設完成條件讓 Claude 跨回合持續工作 | v2.1.139（05-11・w20） | goal |
| hook exec form（`args`）／`continueOnBlock` | 免 shell 的 hook 寫法；PostToolUse 拒絕理由回饋後繼續回合 | v2.1.139（05-11・w20） | hooks |
| usage credits | 舊稱 extra usage，額外用量額度 | v2.1.144（05-19・w21） | costs |
| `/code-review` | 依努力等級回報正確性問題；可背景、可 `--fix`、`--comment` | v2.1.147（05-21・w21） | code-review-local |
| `/reload-skills`／SessionStart `reloadSkills` | 不重啟重掃 skill 目錄 | v2.1.152（05-27・w22） | skills, hooks |
| `MessageDisplay` hook | 轉換或隱藏助手訊息的顯示文字 | v2.1.152（05-27・w22） | hooks |
| dynamic workflows（`/workflows`） | Claude 寫腳本、背景協調大量子代理 | v2.1.154（05-28・w22） | workflows |
| `ultracode` | workflows 的觸發關鍵字（原 workflow）；後成 `/effort` 內獨立開關 | v2.1.160（06-02・w23） | workflows, model-config |
| `requiredMinimumVersion`／`requiredMaximumVersion` | 管理員限制可執行的版本範圍 | v2.1.163（06-04・w23） | managed-settings |
| `fallbackModel` | 主模型過載時依序嘗試的備援模型（至多三個） | v2.1.166（06-06・w23） | model-config |
| `/cd`、`--safe-mode` | 換工作目錄不破快取；關閉全部自訂項啟動 | v2.1.169（06-08・w24） | commands, debug-your-config |
| nested subagents（巢狀子代理） | 子代理可再生子代理 | v2.1.172（06-10・w24） | sub-agents |
| Artifacts | 從 session 發佈的即時互動頁面 | w25（v2.1.178–183） | artifacts |
| 權限規則 `Tool(param:value)` | 依工具輸入參數比對的規則語法 | v2.1.178（06-15・w25） | permissions |
| `/config key=value` | 從提示直接改設定 | v2.1.181（06-17・w25） | settings |
| `claude mcp login/logout` | 在 shell 完成 MCP OAuth | v2.1.186（06-22・w26） | mcp |
| `sandbox.credentials` | 阻止沙箱命令讀憑證檔與祕密環境變數 | v2.1.187（06-23・w26） | sandboxing |
| 子代理預設背景 | 子代理跑時主對話不暫停 | v2.1.198（07-01・w27） | sub-agents |
| Claude in Chrome（GA） | 以擴充功能驅動真實 Chrome | v2.1.198（07-01・w27） | chrome |
| `/doctor`（完整檢查）／`/checkup` | 診斷並修復設定；找未用 skills／MCP | v2.1.205（07-08・w28） | troubleshooting |
| 螢幕閱讀器模式 | 純文字線性輸出（`--ax-screen-reader`） | v2.1.208（07-14・w29） | accessibility |
| `/subtask` | session 內分叉子代理（原 /fork 舊義） | w29（v2.1.212） | sub-agents |
| `DirectoryAdded` hook | `/add-dir` 註冊新目錄後觸發 | v2.1.219（07-24・w30） | hooks |
| Claude Security plugin | 多代理漏洞掃描 | w30 | claude-security |
| cross-session messaging | `ListAgents`＋`SendMessage` 讓 session 互傳訊息 | v2.1.224（08-07・w32） | cross-session-messaging |
| self-hosted environments | 在自家基礎設施跑雲端 session | v2.1.224（08-07・w32） | self-hosted-environments |
| `/design` | 以 Artifacts 產出可編輯 UI 畫板 | w34 | （無專頁；見 w34 摘要） |
| `SendFeedback` 工具 | Claude 自行草擬回饋報告 | v2.1.247（08-26・w35） | commands |
| `--restricted` | 移除可執行命令的內建工具啟動 | v2.1.248（08-27・w35） | cli-reference |
| `PreModelSwitch`／`PostModelSwitch` hooks | 模型切換前（可阻擋）後觸發 | v2.1.251（08-28・w35） | hooks, model-config |
| `managedMcpServers` | 管理員提供給所有人的 HTTP/SSE MCP server | v2.1.259（09-02・w36） | managed-mcp |
| `/skill-doctor` | 各 skill 的上下文成本與使用率 | v2.1.261（09-04・w36） | skills, plugins/measure |
| `maxEffortLevel` | 限制努力等級上限 | v2.1.267（09-09・w37） | settings-reference |
| `claude plugin eval` | 對 plugin 跑測試案例並評分 | v2.1.269（09-11・w37） | plugin-evals |
| AGENTS.md 支援 | 專案無 CLAUDE.md 時讀 AGENTS.md | v2.1.277（09-18・w38） | memory |
| Claude apps gateway | 組織自架、轉接 Bedrock／Vertex 等的 Claude app 閘道 | 2.1.281 已有大量更新（2026-09-23，首見版本未逐版追） | claude-apps-gateway |
| Claude Mods | plugin 可修改更深層行為（面板、狀態列、hook 等） | v2.1.287（10-01・w40） | plugins/mods/overview |
| You should know（內建 mod） | 旁邊 agent 提醒你遺漏的事 | v2.1.287（10-01・w40） | plugins/mods/overview |
| idle compaction（閒置壓縮） | 閒置的 200K+ token 對話在快取過期前先壓縮 | v2.1.299（10-14・w42） | context-window, prompt-caching |
| `ultrathink` | 提示關鍵字，單回合拉高到 xhigh | 2.1.311 重定義（v2.1.311（10-26・w44）） | model-config |
| 模型世代 | Opus 4.6（2.1.32）→Sonnet 4.6（2.1.45）→Opus 4.7（w16）→Opus 4.8（2.1.154）→Sonnet 5（w27）→Opus 5（2.1.219）→Fable 5.1（2.1.257）→Opus 5.5（2.1.280）→Sonnet 5.5（2.1.284）→Haiku 5.5（2.1.293） | 見左 | model-config |

## 二、時間線（版本大到小）

## v2.1.318 · 2026-11-04 · w45
- ★ 模組（mod）的 `prompt.submit` 附加內容留在使用者回合，不再當 system message 送出
- ★ 背景子代理的 shell 指令 3 分鐘後移到背景（避免 prompt cache 過期）；子代理在「被標記時切換模型」設為每次詢問時改為停止
- ★ `deniedMcpServers` URL 條目也擋上游 URL 相符的 Anthropic 提供 server
- 新增：`claude auth status` 顯示登入到期日；`claude -p` 到期前 10 天 stderr 警告
- 移除：2.1.288 保留早期 thinking 的 resume 修正

## v2.1.317 · 2026-11-03 · w45
- 新增：web／shell 工具呼叫要把帳號 email 送上網路前先詢問
- ★ Agent SDK hook callback 支援 `onFailure: "block"`（失敗即阻擋）
- ★ 不同模型的子代理／隊友改用該模型自己儲存的 effort；SendMessage 給執行中背景 agent 更早送達
- ★ 移除 Read 的「檔案自上次讀取未變」stub，重讀會回內容
- 新增：`CLAUDE_CODE_DISABLE_NESTED_SESSION_ID`（self-hosted runner）

## v2.1.316 · 2026-10-31 · w44
- 變更：Opus 4.8 快速模式 10/30 起 deprecated，預計 11/30 移除
- ★ `CLAUDE_CODE_SUBAGENT_EFFORT`：子代理預設 effort
- 新增：`CLAUDE_CODE_DISABLE_ULTRATHINK`；Gateway 群組共用預算、`policy_mode: layered`
- ★ auto mode：`autoMode.allow` 沒寫 `"$defaults"` 不再移除排程任務的內建規則
- ★ 伺服器管理設定（Team／Enterprise）從 API 取得的設定不再需要核准提示

## v2.1.314 · 2026-10-30 · w44
- ★ `permissions.blockWritesOutsideWorkingDirectories`：Write／Edit／NotebookEdit 拒絕工作目錄外路徑（所有模式）
- ★ VS Code／Desktop Code 分頁加入閒置壓縮（200K+ token 閒置後摘要）
- ★ hook `if` 條件如 `Monitor(tail *)` 現在像 Bash 一樣比對 Monitor 的 shell 指令
- ★ Claude 的檔案工具編輯本機伺服器管理設定副本前先詢問
- 變更：`/ultrareview` 先檢查 workspace trust

## v2.1.312 · 2026-10-27 · w44
- ★ prompt／agent hooks 每 session 同時最多 24 個（另有最多 12 個等待超過事件時限者）
- ★ 子代理 `autoCompactWindow` 可壓低 `CLAUDE_CODE_AUTO_COMPACT_WINDOW`
- 新增：Gateway `oidc.user_id_claim`；全螢幕點「to send now」直接送出
- 移除：不再送 `claude_code.safety_event` OTel 事件

## v2.1.311 · 2026-10-26 · w44
- 變更：`ultrathink` 在互動終端以 xhigh 跑該回合（Opus 5.5／Sonnet 5.5／Haiku 5.5／Fable 5.1）
- ★ `DISABLE_COMPACT` 在設定檔與 mod 的 `$.env.set` 只能關閉壓縮、不能再打開
- ★ 以 `CLAUDE_CODE_SYNC_SKILLS` 同步 claude.ai skills 時可重用 10 分鐘內快取
- 變更：模型名稱去掉無作用的 `[1m]` 後綴；`claude purge` 說明僅刪本機資料

## v2.1.310 · 2026-10-23 · w43
- ★ Monitor 工具與 plugin monitors 可用於 Bedrock／Vertex／Foundry 及關閉遙測時

## v2.1.307 · 2026-10-21 · w43
- 新增：`/claude-api api-version`；`claude_code.safety_event` OTel 事件
- ★ `axScreenReader` 設定只從 user／managed／`--settings` 層生效

## v2.1.305 · 2026-10-20 · w43
- 新增：`sandbox.allowNestedUserNamespaces`（Linux 沙箱可建 user namespace）
- ★ `allowedMcpServers` 不再過濾以 `${VAR}` 只放 env 的 managed-mcp.json stdio server
- ★ mod 側 docked pane 寬度上限 45%

## v2.1.304 · 2026-10-19 · w43
- ★ 新增 `/auto-mode-setup`：讀專案與近期 session 引導設定 auto mode
- ★ 工具搜尋在自訂 `ANTHROPIC_BASE_URL` 後預設開啟（400／422 時退回不用）
- ★ 壓縮後重新送出 skill 清單；`/reload-skills` 只送新增或變更的 skill
- ★ 同一來源（repo／資料夾／plugin）的 skill 最多註冊 1,024 個 hooks、16,384 比對字元
- ★ mod `settings.read` hook 可讀各設定層並改寫合併後設定

## v2.1.302 · 2026-10-16 · w42
- ★ `CLAUDE_CODE_AUTO_MODE_MODEL`：指定 client 端 auto mode 分類器模型
- ★ 新增 `/config` 的 Idle compaction 開關；prompt／agent hooks 同事件最多 12 個同時跑
- ★ fork subagent 在 `claude -p`、Agent SDK、Desktop、VS Code 預設開啟；Desktop／VS Code 主對話子代理一律背景
- 變更：`claude -p` 與 SDK 在第三方 provider／遙測關閉時無權限模式則以 default 模式啟動

## v2.1.301 · 2026-10-15 · w42
- 新增：vim `%` 動作；mod `Input` 的 `rows`；OTel `tool_decision` 增 `classifier_verdict`／`permission_mode`／`classifier_category`
- ★ mod hook 的 `.catch` 只在 hook 丟例外或逾時時執行
- ★ `CLAUDE_CODE_RETRY_WATCHDOG_MAX_USAGE_LIMIT_WAIT_MS`：無人值守重試模式的用量上限等待上限

## v2.1.300 · 2026-10-14 · w42
- ★ 本機 session transcript 也記錄每個 API 請求的 system prompt、tools、參數（可重現問題）
- ★ hooks：PreToolUse／PermissionRequest 回的 `updatedInput` 會被驗證（未知鍵丟掉）
- ★ mod：`prompt.change`、`$.ui.view({agentId})`、可改寫 workflow agent 的 `agent.spawn`
- 新增：`/advisor` 於 Claude Platform on AWS；OTel `cache_creation_5m/1h_tokens`
- 移除：`claude remote-control` 的 `--sandbox`／`--no-sandbox`（無作用，傳入即報錯）

## v2.1.299 · 2026-10-14 · w42
- ★ 閒置壓縮：200K+ token 對話閒置約 54 分鐘即在 1 小時快取過期前壓縮；`CLAUDE_CODE_IDLE_COMPACT_MIN_TOKENS`、`"idleCompaction": false`
- ★ `UserPromptSubmit` hooks 改為在 skill／自訂斜線命令展開前執行；skill 自己 frontmatter 的該 hook 從下一個 prompt 起算
- ★ MCP allow 規則只針對所指名 server（`mcp__a` 不再放行 `a__b`）；agent `tools:` 同理
- ★ `turn.start` mod hook 也聽到子代理與隊友回合（用 `e.agentId` 區分）
- 新增：`CLAUDE_CODE_DISABLE_FILE_MENTIONS`；`/usage` 警告（max effort、workflows、常駐 context、大型工具結果）；plugin hook 值巢狀超過 28,000 層即拒絕
- 變更：`claude plugin eval` 加 `--disallow-tools`；MCP 協議 2026-07-28 於 claude.ai 連接器預設協商

## v2.1.296 · 2026-10-09 · w41
- ★ 子代理 frontmatter 與 `--agents` 新增 `autoCompactWindow`
- ★ `CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL`：所有 workflow agent 同一模型
- ★ MCP 工具描述／server instructions 預設上限由 2,048 改 4,096 字元
- 新增：Read 工具 `allow_large`；`/plugin` 對同名 plugin hooks 被略過的提示

## v2.1.295 · 2026-10-08 · w41
- ★ 指令／HTTP hooks 新增 `onFailure: "block"`（啟不來、逾時、非預期退出碼即阻擋動作）
- ★ 子代理最多預載 32 個 `skills`；經 tool search 載入的 MCP 工具描述上限 16,384 字元
- 新增：Program Status Protocol（OSC 7501）讓終端顯示 Claude 在做事／等待／完成
- 變更：scheduled／Run now routine 在遙測關閉時可不詢問發佈 artifact

## v2.1.293 · 2026-10-07 · w41
- 新增：Claude Haiku 5.5（`claude-haiku-5-5`，1M context）
- ★ mod `$.tool.register` 的 `isDeferred`；`subagentStatusLine` payload 加 `agentType`

## v2.1.292 · 2026-10-06 · w41
- ★ Agent 工具新增 `effort` 參數
- ★ `claude plugin install --marketplace <source>`；`prompt.autocomplete` mod 事件
- 變更：本機 stdio MCP 預設協商協議 2026-07-28；agent 名稱上限 256 字元

## v2.1.290 · 2026-10-05 · w41
- ★ plugin hooks `tool.check` 事件帶 `agentId`；`ceiling`（組織要求的核准層級）
- 新增：`claude attach <name>`、`claude logs <name>`（名稱可部分比對）
- 變更：Claude in Chrome 專案設定不能再開啟；`pyright` 不再視為唯讀；`CLAUDE_CODE_DISABLE_ATTACHMENTS` 不能由 repo 設定

## v2.1.289 · 2026-10-03 · w40
- ★ plugin hook 事件跨事件共用 agent id；`agent.spawn` 涵蓋隊友；`$.agent.list()` 有閒置／等待狀態

## v2.1.288 · 2026-10-02 · w40
- 變更：`claude project purge` 更名 `claude purge`（舊名仍可用）
- ★ `/autocompact` 依模型分別儲存壓縮視窗；`/code-review --max-findings`
- ★ 背景指令時限僅用於無人值守 session

## v2.1.287 · 2026-10-01 · w40
- ★ 新增 Claude Mods：plugin 可修改更深層行為；內建 mod「You should know」
- ★ MCP `alwaysLoad: false` 讓該 server 全部工具延遲載入（tool search）
- ★ 2025-11-25 協議的 MCP URL 提示（如登入）；`prompt_text` 加入 OTel `user_prompt`
- 變更：Opus 4.7+ 與 Fable 在 Bedrock／Vertex／Foundry／Gateway 預設 1M context

## v2.1.286 · 2026-09-30 · w40
- 變更：`--bare` 只連線命令列指定的 MCP server、不送 system reminders、不啟背景任務
- ★ `/hooks` 改開成依事件分組的單一清單
- 變更：plugin 從 npm 安裝拒絕 git／資料夾來源，依賴只從 registry 裝
- 移除：`/ultrareview` 輸出的瀏覽器連結

## v2.1.285 · 2026-09-29 · w40
- ★ 新增 `allowedProviders` 受管設定（限制可用 API provider）
- ★ `CLAUDE_CODE_DISABLE_WEB_FETCH`；`claude plugin configure`；`claude --desktop`
- ★ `/memory`：背景 session 或 Claude Code 自己工具啟動的 session 不能再開啟 Auto-memory
- 變更：背景 Bash 指令有時限（預設 30 分，最長 2 小時）

## v2.1.284 · 2026-09-28 · w40
- 新增：Claude Sonnet 5.5（1M context）
- ★ 互動終端與 VS Code 在未設權限模式時所有方案與 provider 都以 auto mode 啟動
- ★ Ultracode 成為 `/effort` 內獨立開關，不再強制 xhigh
- 新增：`/mcp reconnect all`

## v2.1.283 · 2026-09-25 · w39
- ★ 受管設定 `availableModelsMatch`（`exact`）、`deniedModels`
- ★ `/doctor prompt-audit`：審查 CLAUDE.md、skills、agents、commands 的提示寫法
- 新增：Gateway `mantle` upstream、`load_test_mode`
- 變更：`--system-prompt` 與 `-file` 形式可並用

## v2.1.282 · 2026-09-24 · w39
- ★ 專案設定中的遙測／OTel 變數被忽略並提示；`sandbox.excludedCommands` 在受管政策下忽略專案項
- 變更：`anthropic-skills`／`claude-ai` 命名空間的 skill、command、workflow 不再載入
- 新增：`maxProseWidth`；`allowClaudeInChromeWithManagedMcp`

## v2.1.281 · 2026-09-23 · w39
- 新增：`"attribution": false` 可隱藏全部 commit／PR 署名
- ★ MCP URL-mode elicitation（2026-07-28 協議）；`claude plugin validate` 檢查 `.mcp.json`
- 變更：send-now（ctrl+enter）改為把執行中工具移背景而非取消回合
- 移除：`/agents` 殘留的 "(removed)" 項

## v2.1.280 · 2026-09-22 · w39
- 新增：Claude Opus 5.5（`claude-opus-5-5`，預設 Opus，1M）
- 變更：Pro 與 Team Standard 預設模型由 Sonnet 改為 Opus
- ★ `CLAUDE_CODE_MAX_MCP_DESCRIPTION_LENGTH`（原上限 2,048）
- ★ agent 型 hook 不再用於 `PermissionRequest`

## v2.1.277 · 2026-09-18 · w38
- ★ AGENTS.md 支援：專案沒有 CLAUDE.md 時改讀 AGENTS.md
- 移除：TaskOutput 工具（改用 Read 讀背景任務輸出檔）；當時 `taskOutputMaxChars`／`TASK_MAX_OUTPUT_LENGTH` 失效（2.1.261 另有新增 `taskOutputMaxChars`，以最新文件為準）
- ★ 子代理結果以標示「子代理輸出」的標頭交給主代理

## v2.1.275 · 2026-09-17 · w38
- ★ send-now 鍵（ctrl+enter）：打斷當前回合並一次送出全部佇列訊息
- 新增：同步 claude.ai 帳號已啟用的 skills 與 plugins 到終端 session（`syncClaudeAiSkills: false`／`syncClaudeAiPlugins: false` 可 opt out）
- ★ `/plugin install <plugin> --marketplace <source>`

## v2.1.274 · 2026-09-17 · w38
- 新增：記憶體吃緊的可見警告；`CLAUDE_CODE_MCP_STARTUP_WAIT_MS`；`claude_code.managed_settings_resolved` OTel 事件
- ★ `"type": "sdk"` 的 MCP 條目在 `.mcp.json`／設定／plugin／agent 檔中被略過並警告

## v2.1.273 · 2026-09-15 · w38
- 新增：多個 `x-claude-code-*` 閘道提示標頭；MCP server 中途斷線自動重連放棄時通知
- 新增：可從 Claude app 分叉以 `--remote-control` 啟動的 session

## v2.1.271 · 2026-09-14 · w38
- ★ `omitClaudeMd`：custom／plugin 子代理可不載入 user／project／local CLAUDE.md
- ★ 新增 `--accept-command <sha256>` 供 `plugin install/update`
- ★ Monitor 一律有期限（上限 30 分鐘）並通知 Claude 重新佈署
- 變更：預設動態 workflow 規模於 Pro 方案改 small（medium 指引由 15 降 10 個 agent）

## v2.1.269 · 2026-09-11 · w37（w37）
- ★ 新增 `claude plugin eval`（JSON＋HTML 報告）
- 新增：`/output-style [name]`；Bash 工具結果可附檔案 diff（`bashEditDiff`）
- 新增：`CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS`（1–256）
- 變更：`/ultrareview --post` 直接發 PR 評論

## v2.1.268 · 2026-09-10 · w37
- ★ `claude plugin install/uninstall/update/enable/disable` 新增 `--json`
- ★ 任務追蹤工具（TaskCreate／TodoWrite 等）只留給舊模型（Claude 3.x、Opus 4.0–4.7、Sonnet 4.x…）
- 新增：已發佈 artifact 的瀏覽器分頁圖示

## v2.1.267 · 2026-09-09 · w37
- ★ `maxEffortLevel`（頂層或 `modelSettings` 每模型）限制努力等級
- 新增：`--system-prompt-snapshot off`

## v2.1.265 · 2026-09-08 · w37
- ★ `--plugin-dir` 可指向含多個 plugin 的資料夾
- ★ 工具結果存檔上限 1 GB；預覽會註明已截斷

## v2.1.261 · 2026-09-04 · w36（w36）
- ★ `/skill-doctor`：未使用的 skill 與其 context 成本
- ★ `bashOutputMaxChars`、`taskOutputMaxChars`（至 128,000）
- ★ 提示的字詞編輯鍵改為 readline 式（`keybindingFlavor` 設定不再作用）
- 新增：`--append-subagent-system-prompt-file`；`/status` 的「Organization policy」行

## v2.1.260 · 2026-09-03 · w36
- ★ `/cost` 與狀態列顯示 prompt cache miss 的可能原因
- ★ 新增 `/reload-plugins` 進 headless session；`/advisor` 文字形式
- 變更：還原 2.1.259「Read() deny 套用到 Bash 參數」
- 移除：背景指令的 1 小時時限（子代理起的背景指令）

## v2.1.259 · 2026-09-02 · w36
- ★ `managedMcpServers` 受管設定
- ★ `--permission-prompts none`（無人值守 headless：要詢問的一律拒絕）
- 新增：辨識 `glab mr …` 並顯示 `MR !N`

## v2.1.257 · 2026-09-01 · w36
- 新增：Claude Fable 5.1（1M）
- ★ `CLAUDE_CODE_SUBAGENT_MODEL_FORCE`；`timeFormat`／`timeZone` 設定
- ★ auto mode 增 Containment Escape 規則；工作目錄外首次讀取詢問
- 變更：專案設定的 `defaultMode: "bypassPermissions"` 被忽略

## v2.1.251 · 2026-08-28 · w35（w35）
- ★ 新增 `PreModelSwitch`／`PostModelSwitch` hook 事件；SessionStart resume hooks 收到 session 過期程度與預估重新快取成本
- ★ `/cost` 增每 session 的 prompt cache 行（命中率、miss、warm/cold）與狀態列 `prompt_cache`
- ★ `CLAUDE_CODE_SUBAGENT_MODEL` 改為「預設子代理模型」而非覆蓋全部
- 變更：預設 effort 依模型個別儲存；座位制 Enterprise 預設 Opus 5

## v2.1.248 · 2026-08-27 · w35
- ★ `--restricted`／`CLAUDE_CODE_RESTRICTED=1` 受限模式
- ★ agent frontmatter `experimental.cacheTtl`（每 agent 的 prompt cache TTL）
- ★ 新增 Bedrock／Vertex／Foundry 上跨 session 傳訊（`SendMessage`／`ListAgents`）

## v2.1.247 · 2026-08-26 · w35
- 新增：`SendFeedback` 工具
- ★ Bash 權限提示加「Yes, and switch to auto mode」
- ★ 子代理在 Sonnet 5 的預設自動壓縮視窗為完整 1M

## v2.1.246 · 2026-08-25 · w35
- ★ `/permissions` 新增 Auto mode 分頁（檢視編輯分類器規則）
- ★ `/goal`：長時間背景工作的 check-in 每個 goal 最多三次
- 新增：回合結束行顯示完成時間

## v2.1.243 · 2026-08-25 · w35
- ★ `modelPicker`、`promptCacheTtl`、`subagentPromptCacheTtl` 設定
- ★ `/usage` 的 Loops 細目；`modelPricing` 受管設定
- 新增：`/login` 的 Console 帳戶免金鑰登入

## v2.1.239 · 2026-08-21 · w34
- ★ `/goal`：背景工作 check-in 逐次退避（30 分→1 小時→2 小時）；resume 時恢復進行中的 goal
- ★ `ListAgents` 列出隊友並告知自己的名稱
- 變更：成本估算含資料落地工作區 1.1 倍加成

## v2.1.238 · 2026-08-20 · w34
- ★ `keybindingFlavor: "readline"` 設定
- ★ marketplace `headersHelper`（取得短效 HTTP 標頭）；MCP `headersHelper` 在專案 `.mcp.json` 需信任資料夾

## v2.1.236 · 2026-08-19 · w34
- ★ `ANTHROPIC_DEFAULT_MODEL`；`SendMessage` 的 `notify_when_idle`
- 變更：Remote Control 在 CLI 結束後數秒內標記離線

## v2.1.235 · 2026-08-18 · w34
- 新增：選用 `spellcheck` 設定（用 aspell／hunspell／ispell）
- ★ `SendMessage` 對過大訊息先行拒絕而非靜默丟棄

## v2.1.234 · 2026-08-17 · w34（w34）
- ★ claude.ai 用量上限重置後自動續跑 session（`/config` 可關）
- ★ `/permissions` 與 `/add-dir` 可在 Claude 工作中開啟，變更套用到本回合其餘部分
- ★ 新增 `CLAUDE_CODE_PROJECT_DIR_NAME`
- 新增：GitLab MR 頁尾徽章
- 移除：`/config` 的 "Default teammate model"（隊友改用 leader 模型）

## v2.1.233 · 2026-08-14 · w33
- ★ `--worktree` 與 `claude agents` 支援 GitLab MR URL
- ★ TaskCreate／TodoWrite 在 Opus 4.8、Sonnet 5、Fable 5 等新模型不再提供
- 新增：`CLAUDE_CODE_TOOL_MEMORY_LIMIT`（Linux cgroup）

## v2.1.232 · 2026-08-13 · w33（w33）
- ★ 子代理 fork 預設開啟
- ★ 提示中 `@` 提及另一個 session；同機 session 名稱唯一
- ★ `additionalMarketplaces`／`allowedMarketplaces` 別名；marketplace 支援 gitlab.com
- ★ `/plugin install plugin@marketplace` 先刷新 marketplace

## v2.1.229 · 2026-08-12 · w33
- ★ plugin marketplace `command` 來源（本機指令印出 plugin 目錄）
- 變更：`/commit-push-pr` 危險旗標（`--force`、`--amend`、`--no-verify`）不再自動允許

## v2.1.228 · 2026-08-11 · w33
- ★ 從 claude.ai 同步的 skills 強化（不覆蓋本機命令或 MCP prompts）
- ★ 新模型 Write 可覆寫未讀過的既有檔案（與 Edit 規則一致）

## v2.1.225 · 2026-08-08 · w32
- 新增：`claude agents` 對未信任目錄的 workspace trust 提示
- ★ SendMessage 可用名稱對其他機器的 Remote Control session 開對話

## v2.1.224 · 2026-08-07 · w32（w32）
- ★ 跨 session `SendMessage`／`ListAgents`；`crossSessionInbound`、`dialogExpiry` 設定
- ★ 移除每 session 200 個子代理上限
- ★ marketplace `archive` 來源（zip over HTTPS，可釘 SHA-256）
- 新增：沙箱憑證遮罩 `extract`／`decode: "jwt"`

## v2.1.223 · 2026-08-06 · w32
- 變更：`/review` 成為 `/code-review` 別名；`/code-review` 無等級時沿用上次
- ★ `CLAUDE_CODE_DISABLE_1M_CONTEXT` 讓所有原生 1M 模型改為 200K 自動壓縮
- 新增：`strictKnownMarketplaces`／`blockedMarketplaces` 的 `owner/*` 萬用字元

## v2.1.222 · 2026-08-04 · w32
- 移除：Ultraplan
- ★ 專案層設定（`.claude/settings*.json`）不能再開啟 Remote Control 自動啟動

## v2.1.221 · 2026-08-04 · w32
- ★ 背景 session 改程式碼後預設 commit＋push，必要時才開草稿 PR，並遵循 CLAUDE.md git 指示
- ★ `/plugin install` 若 marketplace 過期會自動刷新重試；plugin 安裝後安全時立即啟用
- ★ `/fork` 建立的 session 用自己的 worktree
- 新增：sandbox `mode: "mask"`（Linux／WSL）

## v2.1.219 · 2026-07-24 · w30（w30）
- 新增：Claude Opus 5（`claude-opus-5`，預設 Opus）
- ★ 新增 `DirectoryAdded` hook
- ★ 子代理可巢狀生成，預設深度 3（`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`）
- ★ `workflowSizeGuideline` 設定；預設 workflow 規模 medium
- 變更：快速模式移除 Opus 4.7

## v2.1.218 · 2026-07-22 · w30
- ★ `/code-review` 改為背景子代理執行；`/deep-research` 僅手動叫用
- ★ skill `context: fork` 預設背景（`background: false` 可關）
- ★ agent markdown 名稱不可含 `:`（保留給 plugin 命名空間）

## v2.1.217 · 2026-07-21 · w30
- ★ 同時執行子代理上限預設 20（`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`）
- 新增：emoji 短碼補全；transcript 寫入失敗警告

## v2.1.216 · 2026-07-20 · w30
- ★ `sandbox.filesystem.disabled`（略過檔案系統隔離、保留網路出口控制）
- ★ `/rewind` 不再透過 symlink／hardlink 還原或刪檔

## v2.1.214 · 2026-07-18 · w29
- ★ memory 檔案 frontmatter 新增 ISO `modified` 時間戳
- 新增：`EndConversation` 工具；長時間工具呼叫的進度心跳
- ★ SessionStart hook 在 session 以 fork 開始時回報 source `"fork"`
- ★ 單段 `dir/**` 的 hook `if:` 只比對 `<cwd>/dir`（任意深度要寫 `**/dir/**`）

## v2.1.212 · 2026-07-17 · w29（w29）
- ★ `/fork` 改為複製對話成新背景 session
- ★ MCP 工具呼叫超過 2 分鐘自動移背景
- ★ 每 session WebSearch 上限 200、子代理生成上限 200
- 新增：`claude auto-mode reset`
- 變更：Task 工具 `mode` 參數 deprecated（子代理繼承父權限模式）

## v2.1.211 · 2026-07-15 · w29
- ★ 「一律允許」權限規則存在 repo 根，git worktree 中授予的核准可跨 worktree 沿用
- 新增：`--forward-subagent-text`／`CLAUDE_CODE_FORWARD_SUBAGENT_TEXT`

## v2.1.210 · 2026-07-14 · w29
- ★ memory 寫入使 MEMORY.md 索引超過讀取上限時改為明確錯誤（不再靜默截斷）
- ★ Agent 工具防範經子代理讀取內容的間接提示注入

## v2.1.208 · 2026-07-14 · w29
- 新增：螢幕閱讀器模式（`--ax-screen-reader`）；`vimInsertModeRemaps`
- ★ `CLAUDE_CODE_PROCESS_WRAPPER`（企業啟動器）
- 變更：session transcript 縮小（編輯密集 session 最多 79 倍）、checkpoint 空間受控

## v2.1.207 · 2026-07-11 · w28
- ★ auto mode 在 Bedrock／Vertex／Foundry 不再需 `CLAUDE_CODE_ENABLE_AUTO_MODE`
- ★ auto mode 不再讀 repo 內 `.claude/settings.local.json` 的 `autoMode`
- ★ plugin hooks／monitors／headersHelper 的 shell 形式命令中 `${user_config.*}` 被拒絕（防注入）；`pluginConfigs` 不再讀專案層

## v2.1.206 · 2026-07-09 · w28
- 新增：`/cd` 目錄路徑建議
- ★ `/doctor` 檢查可建議精簡簽入的 CLAUDE.md
- ★ `EnterWorktree` 進入專案 `.claude/worktrees/` 外的 worktree 前先確認

## v2.1.205 · 2026-07-08 · w28（w28）
- ★ `/doctor` 變完整設定檢查（別名 `/checkup`）
- ★ auto mode 新增阻擋篡改 session transcript 檔
- 變更：背景任務通知明示「無人類輸入」，防偽造核准

## v2.1.203 · 2026-07-07 · w28
- ★ 新增 MCP `roots/list` 含 session 的額外工作目錄
- 新增：登入將到期警告；手動權限模式頁尾 ⏸ 徽章

## v2.1.202 · 2026-07-06 · w28
- ★ `/config` 的「Dynamic workflow size」
- 變更：`/review <pr>` 回到快速單次審查

## v2.1.200 · 2026-07-03 · w27
- 變更：`AskUserQuestion` 對話不再預設自動繼續（可於 `/config` 設閒置逾時）

## v2.1.199 · 2026-07-02 · w27
- ★ 堆疊 skill 呼叫（`/skill-a /skill-b …`）載入全部前導 skill（至多 5 個）
- ★ `CLAUDE_CODE_RETRY_WATCHDOG` 提高非容量暫時性錯誤重試次數

## v2.1.198 · 2026-07-01 · w27（w27）
- ★ 子代理預設在背景執行
- ★ `claude agents` 中需輸入或完成的 session 會觸發 `Notification` hook
- ★ 內建 Explore 代理繼承主 session 模型（上限 Opus）
- 新增：Claude in Chrome GA
- 移除：`/agents` 精靈（改請 Claude 建立／編輯子代理）

## v2.1.196 · 2026-06-29 · w27
- 新增：組織預設模型（`Org default`）；session 自動命名
- ★ `claude mcp list/get` 不再啟動 repo 自行核准的 `.mcp.json` server
- 變更：串流閒置監視器對所有 provider 預設開啟

## v2.1.193 · 2026-06-25 · w26（w26）
- ★ `autoMode.classifyAllShell`；auto mode 拒絕原因顯示在 transcript／toast／`/permissions`
- 新增：`!` 模式檔案路徑補全；閒置背景 shell 記憶體壓力回收

## v2.1.191 · 2026-06-24 · w26
- 新增：`/rewind` 可從 `/clear` 之前恢復

## v2.1.187 · 2026-06-23 · w26
- ★ `sandbox.credentials`；組織設定的模型限制套用到選擇器與 `--model`

## v2.1.186 · 2026-06-22 · w26
- ★ `claude mcp login`／`logout`
- ★ `!` bash 指令輸出會觸發 Claude 回應（`respondToBashCommands`）
- ★ 背景子代理的權限提示改顯示在主 session（不再自動拒絕）
- 變更：`CLAUDE_CODE_MAX_RETRIES` 上限 15

## v2.1.183 · 2026-06-19 · w25
- 新增：`attribution.sessionUrl`；`/config --help`；模型被 deprecated 的警告
- 變更：`/config` 切換 Enter／Space 皆可，Esc 存檔關閉
- 移除：啟動時 "setup issues" 行（改看 `/doctor`）

## v2.1.181 · 2026-06-17 · w25（w25）
- ★ `/config key=value`（互動、`-p`、Remote Control 皆可）
- 新增：`sandbox.allowAppleEvents`、`CLAUDE_CLIENT_PRESENCE_FILE`
- 變更：內建 Bun 升至 1.4

## v2.1.178 · 2026-06-15 · w25
- ★ 權限規則 `Tool(param:value)`（例 `Agent(model:opus)`）
- ★ agent teams：移除 `TeamCreate`／`TeamDelete`，設 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` 時每個 session 有隱含團隊
- ★ 巢狀 `.claude/skills` 在處理該處檔案時載入，衝突時以 `<dir>:<name>`；最接近工作目錄的 agent／workflow／output-style 優先
- 變更：workflow 提示關鍵字顯示紫色高亮，僅明確字句觸發

## v2.1.176 · 2026-06-12 · w24
- 新增：`footerLinksRegexes`
- 變更：session 標題依對話語言產生（`language` 可釘選）

## v2.1.172 · 2026-06-10 · w24（w24）
- ★ 子代理可生成子代理（至多 5 層）
- ★ Bedrock 在未設 `AWS_REGION` 時讀 `~/.aws` 區域
- 新增：`/plugin` marketplace 瀏覽搜尋列

## v2.1.169 · 2026-06-08 · w24
- ★ `/cd`；`--safe-mode`／`CLAUDE_CODE_SAFE_MODE`
- ★ `disableBundledSkills`／`CLAUDE_CODE_DISABLE_BUNDLED_SKILLS`
- ★ 「CLAUDE.md 太長」警告門檻隨模型 context window 縮放

## v2.1.166 · 2026-06-06 · w23
- ★ `fallbackModel`（至多三個）；deny 規則工具名位置可用 glob
- ★ 他 session 經 `SendMessage` 轉送的訊息不帶使用者授權

## v2.1.163 · 2026-06-04 · w23（w23）
- ★ `requiredMinimumVersion`／`requiredMaximumVersion`
- ★ Stop／SubagentStop hooks 可回 `hookSpecificOutput.additionalContext` 保持回合進行
- 新增：`/plugin list`；`/btw` 的 `c` 複製

## v2.1.162 · 2026-06-03 · w23
- 變更：Windsurf 更名 Devin Desktop；啟動訊息更安靜；`claude agents --json` 含 `waitingFor`

## v2.1.161 · 2026-06-02 · w23
- ★ 平行工具批次中失敗的 Bash 不再取消其他呼叫
- 變更：`OTEL_RESOURCE_ATTRIBUTES` 成為指標標籤

## v2.1.160 · 2026-06-02 · w23
- ★ acceptEdits 寫入 shell 啟動檔、`~/.config/git/`、`.npmrc` 等可執行設定前提示
- 變更：動態 workflow 觸發詞由 `workflow` 改為 `ultracode`
- 移除：`CLAUDE_CODE_OPUS_4_6_FAST_MODE_OVERRIDE`

## v2.1.157 · 2026-05-29 · w22
- 新增：`claude plugin init <name>`；`.claude/skills` 內 plugin 自動載入
- ★ `/config` 的「Workflow keyword trigger」開關

## v2.1.154 · 2026-05-28 · w22（w22）
- ★ 動態 workflows 上線；Opus 4.8（預設 high effort）
- ★ plugin `defaultEnabled: false`；`/plugin` Discover 依目錄推薦 plugin
- ★ 精簡 system prompt 預設用於 Haiku／Sonnet／Opus 4.7 及更早以外的模型
- ★ `claude agents` 中 `! <command>` 以背景 session 執行 shell
- 變更：`/simplify` 變為只清理（reuse／simplification／efficiency）並直接套用修正

## v2.1.153 · 2026-05-28 · w22
- 新增：plugin marketplace `skipLfs`；`claude doctor` 顯示上次更新結果
- 變更：`/model` 選擇預設存為新 session 預設，`s` 僅限本 session；keybinding `modelPicker:setAsDefault` 更名 `modelPicker:thisSessionOnly`

## v2.1.152 · 2026-05-27 · w22
- ★ `/reload-skills`；SessionStart `reloadSkills: true`、`hookSpecificOutput.sessionTitle`
- ★ `MessageDisplay` hook；skill／command frontmatter `disallowed-tools`
- ★ `pluginSuggestionMarketplaces` 受管設定
- 變更：`--fallback-model` 在主模型找不到時整個 session 改用

## v2.1.149 · 2026-05-22 · w21（w21）
- ★ `allowAllClaudeAiMcps` 受管設定
- ★ `/usage` 依 skills／subagents／plugins／MCP 分類歸因
- 新增：Markdown 任務清單核取方塊渲染

## v2.1.147 · 2026-05-21 · w21
- 變更：`/simplify` 更名 `/code-review`（報告正確性 bug，可指定 effort）
- ★ 釘選（Ctrl+T）的背景 session 閒置時保持存活

## v2.1.145 · 2026-05-19 · w21
- ★ `claude agents --json`；Stop／SubagentStop hook 輸入含 `background_tasks`、`session_crons`
- ★ `/plugin` Discover 顯示 plugin 的 commands／agents／skills／hooks／MCP／LSP 內容

## v2.1.144 · 2026-05-19 · w21
- ★ `/resume` 支援背景 session；背景子代理完成通知含經過時間
- 變更：「extra usage」更名 usage credits，`/extra-usage`→`/usage-credits`
- ★ `/model` 僅變更本 session，`d` 設預設；resume 的 session 保持原模型

## v2.1.143 · 2026-05-15 · w20
- ★ plugin 依賴強制：被依賴時 `plugin disable` 拒絕
- ★ `/plugin` 顯示預估 context 成本；`worktree.bgIsolation: "none"`
- 變更：Windows 的 PowerShell 工具在 Bedrock／Vertex／Foundry 預設啟用

## v2.1.142 · 2026-05-14 · w20
- 變更：快速模式預設用 Opus 4.7
- ★ plugin 根目錄有 `SKILL.md` 且無 `skills/` 時視為 skill
- 新增：`claude agents` 派發旗標

## v2.1.141 · 2026-05-13 · w20
- ★ hook JSON 輸出 `terminalSequence`（桌面通知、視窗標題、鈴聲）
- 新增：Rewind「Summarize up to here」
- ★ 背景 agent 以 `/bg` 或 `←←` 保留目前權限模式

## v2.1.139 · 2026-05-11 · w20（w20）
- ★ agent view（`claude agents`）、`/goal`
- ★ hook `args: string[]` exec 形式、PostToolUse `continueOnBlock`
- ★ MCP stdio 得到 `CLAUDE_PROJECT_DIR`；壓縮提示要求保留敏感使用者指令
- 新增：`claude plugin details <name>`（元件與預估每 session token 成本）

## v2.1.136 · 2026-05-08 · w19
- ★ `settings.autoMode.hard_deny`
- 變更：plugin marketplace 移除鍵由 `r` 改 `d`

## v2.1.133 · 2026-05-07 · w19（w19）
- ★ `worktree.baseRef`；`sandbox.bwrapPath`／`socatPath` 受管設定
- ★ `parentSettingsBehavior`；hooks 取得 `effort.level`／`$CLAUDE_EFFORT`

## v2.1.132 · 2026-05-06 · w19
- ★ `CLAUDE_CODE_SESSION_ID` 進入 Bash 工具子程序環境

## v2.1.129 · 2026-05-06 · w19
- ★ `--plugin-url`；plugin manifest 的 `themes`／`monitors` 改宣告於 `experimental`
- ★ `skillOverrides` 設定可用（`off`／`user-invocable-only`／`name-only`）
- 變更：Ctrl+R 預設搜全部專案提示

## v2.1.128 · 2026-05-04 · w19
- ★ `--plugin-dir` 接受 `.zip`；MCP server 名稱 `workspace` 保留
- ★ 子程序（Bash／hooks／MCP／LSP）不再繼承 `OTEL_*`
- ★ `--channels` 可用於 console（API key）驗證

## v2.1.126 · 2026-05-01 · w18（w18）
- ★ `claude project purge`
- ★ `--dangerously-skip-permissions` 改為略過 `.claude/`、`.git/`、`.vscode/`、shell 設定等的寫入提示
- 新增：`claude auth login` 可貼 OAuth 碼

## v2.1.122 · 2026-04-28 · w18
- 新增：`/resume` 貼 PR URL；`ANTHROPIC_BEDROCK_SERVICE_TIER`

## v2.1.121 · 2026-04-28 · w18
- ★ MCP `alwaysLoad`；PostToolUse `updatedToolOutput` 適用所有工具
- ★ `claude plugin prune`；MCP 啟動暫時性錯誤自動重試 3 次
- 變更：`--dangerously-skip-permissions` 不再於 `.claude/skills|agents|commands/` 詢問

## v2.1.120 · 2026-04-28 · w18
- 新增：`claude ultrareview [target]` 非互動子命令
- ★ skill 內容可用 `${CLAUDE_EFFORT}`；子程序設 `AI_AGENT`

## v2.1.119 · 2026-04-23 · w17（w17）
- ★ `/config` 設定寫入 `~/.claude/settings.json` 並參與專案／本機／政策優先序
- ★ `PostToolUse`／`PostToolUseFailure` hook 輸入含 `duration_ms`
- ★ `--print` 模式遵循 agent 的 `tools:`／`disallowedTools:`
- 新增：`prUrlTemplate`；statusline 輸入含 `effort.level`、`thinking.enabled`
- 變更：Vertex AI 預設關閉 tool search

## v2.1.118 · 2026-04-23 · w17
- ★ hook `type: "mcp_tool"`；`/cost`＋`/stats` 併入 `/usage`
- ★ `wslInheritsWindowsSettings`；auto mode 規則可含 `"$defaults"`
- 新增：vim 視覺模式；自訂主題；`claude plugin tag`；`DISABLE_UPDATES`

## v2.1.117 · 2026-04-22 · w17
- ★ `CLAUDE_CODE_FORK_SUBAGENT=1` 可在外部版本啟用分叉子代理
- ★ agent frontmatter `mcpServers` 在 `--agent` 主執行緒載入；`cleanupPeriodDays` 清掃涵蓋 tasks／shell-snapshots／backups
- ★ 受管 `blockedMarketplaces`／`strictKnownMarketplaces` 於 install／update／autoupdate 一律強制
- 變更：原生 macOS／Linux 版以 bfs／ugrep 取代 Glob／Grep；Pro／Max 在 Opus 4.6／Sonnet 4.6 預設 effort 改 high；advisor 工具（實驗）

## v2.1.116 · 2026-04-20 · w17
- ★ agent frontmatter `hooks:` 在 `--agent` 主執行緒生效
- ★ `/reload-plugins` 與背景自動更新會自動裝缺的依賴
- 新增：`/doctor` 可在 Claude 回應時開啟；Bash 工具 gh API rate limit 提示

## v2.1.113 · 2026-04-17 · w16（w16）
- 變更：CLI 改 spawn 原生每平台二進位檔
- ★ `sandbox.network.deniedDomains`
- ★ 停滯超過 10 分鐘的子代理以明確錯誤失敗
- ★ Bash deny 規則可比對 `env`／`sudo`／`watch` 等包裝後的命令；`find` allow 規則不再自動核准 `-exec`／`-delete`

## v2.1.111 · 2026-04-16 · w16
- 新增：`xhigh`；`/ultrareview`；自動（符合終端）主題；`/less-permission-prompts`（官方週摘要稱 `/fewer-permission-prompts`）
- ★ auto mode 開放 Max（Opus 4.7）且不需 `--enable-auto-mode`
- 變更：`/effort` 無引數開互動滑桿

## v2.1.110 · 2026-04-15 · w16
- 新增：行動推播工具
- ★ `--resume`／`--continue` 恢復未過期的排程任務
- 變更：Ctrl+O 只切換 normal／verbose；focus view 改 `/focus`

## v2.1.108 · 2026-04-14 · w16
- ★ `ENABLE_PROMPT_CACHING_1H`；啟動時 prompt caching 被關閉的警告
- 新增：`/recap`
- ★ 模型可透過 Skill 工具發現並呼叫內建斜線命令（`/init`、`/review`、`/security-review`）；`/undo` 為 `/rewind` 別名

## v2.1.105 · 2026-04-13 · w16
- ★ `PreCompact` hook 可 exit 2 或回 `{"decision":"block"}` 阻擋壓縮
- ★ plugin 頂層 `monitors` manifest 鍵（session 開始或 skill 叫用時自動啟動背景監看）
- 新增：`EnterWorktree` 的 `path`；`/proactive` 為 `/loop` 別名

## v2.1.101 · 2026-04-10 · w15（w15）
- 新增：`/team-onboarding`；預設信任 OS CA 憑證存放區
- 變更：遠端 session 功能自動建立預設雲端環境

## v2.1.98 · 2026-04-09 · w15
- ★ Monitor 工具
- 新增：`--exclude-dynamic-system-prompt-sections`；statusline `workspace.git_worktree`；Perforce 模式
- ★ Linux 子程序 PID namespace 隔離（`CLAUDE_CODE_SUBPROCESS_ENV_SCRUB`）

## v2.1.97 · 2026-04-08 · w15
- 新增：focus view（NO_FLICKER 下 Ctrl+O）；statusline `refreshInterval`；`/agents` 的「N running」

## v2.1.94 · 2026-04-07 · w15
- ★ `UserPromptSubmit` hook 可回 `hookSpecificOutput.sessionTitle`
- 新增：Bedrock Mantle（`CLAUDE_CODE_USE_MANTLE=1`）；plugin output style `keep-coding-instructions`
- 變更：API key／3P／Team／Enterprise 預設 effort 由 medium 改 high

## v2.1.92 · 2026-04-04 · w14
- ★ `forceRemoteSettingsRefresh`（啟動阻塞至遠端管理設定取得）
- 新增：Bedrock 設定精靈；`/cost` 增模型與快取細分
- 移除：`/tag`、`/vim`（改用 `/config` 的 Editor mode）

## v2.1.91 · 2026-04-02 · w14（w14）
- ★ MCP `anthropic/maxResultSizeChars`；`disableSkillShellExecution`
- ★ plugin `bin/` 可執行檔

## v2.1.90 · 2026-04-01 · w14
- 新增：`/powerup`；`CLAUDE_CODE_PLUGIN_KEEP_MARKETPLACE_ON_FAILURE`；`.husky` 加入受保護目錄
- 變更：`--resume` 選單不再顯示 `claude -p`／SDK 建立的 session

## v2.1.89 · 2026-04-01 · w14
- ★ `PreToolUse` 新決策 `"defer"`；`PermissionDenied` hook
- ★ hook 輸出超過 10,000 字元改存檔，只注入路徑＋2,000 字預覽
- ★ `cleanupPeriodDays: 0` 現在驗證失敗（以往靜默關閉 transcript 保存）
- 新增：`CLAUDE_CODE_NO_FLICKER=1`；`TaskCreated` hook 文件化
- 變更：思考摘要在互動 session 預設不產生（`showThinkingSummaries: true` 恢復）

## v2.1.86 · 2026-03-27 · w13
- 新增：`X-Claude-Code-Session-Id` 請求標頭；VCS 排除加 `.jj`、`.sl`
- ★ Read 改緊湊行號格式並對未變更重讀去重；`/skills` 描述上限 250 字元

## v2.1.85 · 2026-03-26 · w13（w13）
- ★ hook `if`（權限規則語法）；PreToolUse 可用 `updatedInput` 滿足 `AskUserQuestion`
- ★ MCP OAuth 遵循 RFC 9728；`headersHelper` 得到 `CLAUDE_CODE_MCP_SERVER_NAME`／`_URL`
- 變更：組織政策封鎖的 plugin 不可安裝或啟用

## v2.1.84 · 2026-03-26 · w13
- 新增：PowerShell 工具（preview）；`TaskCreated` hook；`WorktreeCreate` 支援 `type: "http"`
- ★ `allowedChannelPlugins` 受管設定；MCP 工具描述與 server instructions 上限 2KB
- ★ 本地與 claude.ai 重複的 MCP server 去重（本地優先）
- 新增：閒置 75 分鐘後提示 `/clear`

## v2.1.83 · 2026-03-25 · w13
- ★ `managed-settings.d/`；`CwdChanged`／`FileChanged` hooks
- ★ plugin `manifest.userConfig`；agent `initialPrompt`
- 新增：transcript 搜尋；`CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1`；`sandbox.failIfUnavailable`
- ★ `MEMORY.md` 索引除 200 行外另有 25KB 截斷
- 變更：Deprecated TaskOutput 工具

## v2.1.81 · 2026-03-20 · w12
- ★ `--bare`；`--channels` 權限轉送（channel server 可轉發工具核准提示）
- 變更：MCP OAuth 支援 CIMD（SEP-991）；plan mode 預設隱藏「清除 context」

## v2.1.80 · 2026-03-19 · w12
- ★ `--channels`（研究預覽）；`source: 'settings'` plugin marketplace；skill／command `effort` frontmatter
- 新增：statusline `rate_limits` 欄位

## v2.1.78 · 2026-03-17 · w12
- ★ `StopFailure` hook；`${CLAUDE_PLUGIN_DATA}`（plugin 持久狀態，更新後保留）
- ★ plugin agent 支援 `effort`／`maxTurns`／`disallowedTools` frontmatter
- 新增：`ANTHROPIC_CUSTOM_MODEL_OPTION`

## v2.1.77 · 2026-03-17 · w12
- 變更：`/fork` 更名 `/branch`（`/fork` 為別名）
- ★ Agent 工具移除 `resume` 參數（改 `SendMessage({to: agentId})` 續用）；`SendMessage` 自動恢復已停止的 agent
- 新增：`allowRead` 沙箱檔案系統設定

## v2.1.76 · 2026-03-14 · w11
- ★ MCP elicitation；`Elicitation`／`ElicitationResult` hooks；`PostCompact` hook
- 新增：`/effort`；`-n/--name`；`worktree.sparsePaths`

## v2.1.75 · 2026-03-13 · w11
- ★ memory 檔案加最後修改時間戳（讓 Claude 判斷新舊）
- 移除（breaking）：舊 Windows 管理設定路徑 `C:\ProgramData\ClaudeCode\managed-settings.json`
- 新增：Opus 4.6 預設 1M context（Max／Team／Enterprise）；`/color`

## v2.1.74 · 2026-03-12 · w11
- ★ `autoMemoryDirectory` 設定（自訂 auto-memory 儲存目錄）
- 新增：`/context` 提供可行動建議（找出吃 context 的工具與記憶膨脹）

## v2.1.73 · 2026-03-11 · w11
- ★ `modelOverrides` 設定
- 變更：`/output-style` deprecated（輸出風格 session 開始即固定，利於 prompt cache）

## v2.1.72 · 2026-03-10 · w11
- 新增：`ExitWorktree` 工具；`/plan <描述>`；`CLAUDE_CODE_DISABLE_CRON`
- 變更：effort 簡化為 low/medium/high；CLAUDE.md 的 HTML 註解自動注入時對 Claude 隱藏

## v2.1.71 · 2026-03-07 · w10
- 新增：`/loop`、cron 排程工具；`voice:pushToTalk` keybinding
- 變更：`/debug` 改為 session 中才開啟 debug log（預設不再寫入）

## v2.1.69 · 2026-03-05 · w10
- ★ `InstructionsLoaded` hook；hook 事件加 `agent_id`／`agent_type`
- ★ `/reload-plugins`；`${CLAUDE_SKILL_DIR}`；plugin source type `git-subdir`
- ★ `includeGitInstructions`／`CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS`
- 新增：Voice STT 增至 20 語言；`pluginTrustMessage`

## v2.1.63 · 2026-02-28 · w9
- ★ HTTP hooks（POST JSON）；專案設定與 auto memory 在同 repo 的 git worktree 間共用
- 新增：`/simplify`、`/batch`；`ENABLE_CLAUDEAI_MCP_SERVERS=false`

## v2.1.51 · 2026-02-24 · w9
- 新增：`claude remote-control` 子命令；managed settings 可由 macOS plist／Windows Registry 佈署
- ★ 工具結果超過 50K 字元即存檔（原 100K）；`CLAUDE_CODE_PLUGIN_GIT_TIMEOUT_MS`

## v2.1.50 · 2026-02-20 · w8
- ★ `WorktreeCreate`／`WorktreeRemove` hooks；agent `isolation: worktree`
- 新增：`claude agents`（列出已設定 agents）；`CLAUDE_CODE_DISABLE_1M_CONTEXT`

## v2.1.49 · 2026-02-19 · w8
- ★ `--worktree`；`ConfigChange` hook；agent `background: true`
- ★ plugin 可附 `settings.json` 提供預設設定

## v2.1.47 · 2026-02-18 · w8
- ★ Stop／SubagentStop hook 輸入含 `last_assistant_message`
- 新增：statusline `added_dirs`；config 備份移到 `~/.claude/backups/`

## v2.1.45 · 2026-02-17 · w8
- 新增：Claude Sonnet 4.6；`spinnerTipsOverride`；讀取 `--add-dir` 的 `enabledPlugins`／`extraKnownMarketplaces`

## v2.1.41 · 2026-02-13 · w7
- 新增：`claude auth login/status/logout`；Windows ARM64 原生版；防止在 Claude Code 內再啟動 Claude Code

## v2.1.33 · 2026-02-06 · w6
- ★ `TeammateIdle`／`TaskCompleted` hooks；agent `memory` frontmatter（user／project／local）
- ★ 以 `Task(agent_type)` 限制可生成的子代理

## v2.1.32 · 2026-02-05 · w6
- ★ agent teams（研究預覽，需 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`）；Claude 自動記錄與回想記憶（auto memory）
- ★ skill 字元預算隨 context window 縮放（2%）；`--add-dir` 內的 skills 自動載入
- 新增：Claude Opus 4.6；「Summarize from here」

## v2.1.30 · 2026-02-03 · w6
- 新增：Read 工具 PDF `pages` 參數；`/debug`；MCP 預設 OAuth 憑證（Slack 等）；Task 結果增 token／時間指標

## v2.1.20 · 2026-01-27 · w5
- ★ `--add-dir` 內的 `CLAUDE.md` 載入（需設環境變數）；TaskUpdate 可刪任務
- 變更：背景 agents 啟動前先詢問工具權限；設定備份帶時間戳並輪替保留 5 份

## v2.1.19 · 2026-01-23 · w4
- 新增：`$0`、`$1` 位置參數；`CLAUDE_CODE_ENABLE_TASKS`
- 變更：`$ARGUMENTS.0` 改 `$ARGUMENTS[0]`；無額外權限／hooks 的 skills 免核准

## v2.1.14 · 2026-01-20 · w4
- 新增：plugin 可釘到 git commit SHA；bash 模式歷史補全

## v2.1.7 · 2026-01-14 · w3
- ★ MCP tool search 自動模式對所有人預設開啟（工具描述超過 context 10% 時）
- 新增：`showTurnDuration`；agent 最終回應在任務通知中內嵌

## v2.1.6 · 2026-01-13 · w3
- ★ 自動發現巢狀 `.claude/skills`；statusline `context_window.used_percentage`／`remaining_percentage`
- 移除：@-mention MCP server 啟停（改 `/mcp enable <name>`）

## v2.1.3 · 2026-01-09 · w2
- ★ slash commands 與 skills 合併；hook 逾時由 60 秒改 10 分鐘
- 新增：發行通道（stable／latest）切換；無法觸及的權限規則偵測警告

## v2.1.2 · 2026-01-09 · w2
- ★ SessionStart hook 輸入加 `agent_type`
- 變更：大型 Bash／工具輸出存檔而非截斷；Windows 管理設定舊路徑 deprecated

## v2.1.0 · 2026-01-07 · w2
- ★ skills 熱重載；`context: fork`；skill／agent／command frontmatter hooks；hook `once: true`
- ★ `language` 設定；Bash 權限萬用字元（`Bash(npm *)`）；`agent` 欄位指定 skill 執行 agent
- 新增：`/plan`；`/teleport`、`/remote-env`；MCP `list_changed`；Ctrl+B 統一背景化

## 三、已移除或改名

| 舊 | 新／處置 | 版本 |
|---|---|---|
| `$ARGUMENTS.0` | `$ARGUMENTS[0]`（括號語法） | v2.1.19（01-23・w4） |
| slash command 與 skill 兩套 | 合併為同一模型 | v2.1.3（01-09・w2） |
| 舊 Windows 管理設定 `C:\ProgramData\ClaudeCode\managed-settings.json` | deprecated→移除（breaking），改新路徑 | 2.1.2 → v2.1.75（03-13・w11） |
| @-mention MCP server 啟停 | `/mcp enable <name>` | v2.1.6（01-13・w3） |
| Agent 工具 `resume` 參數 | `SendMessage({to: agentId})` | v2.1.77（03-17・w12） |
| `/fork` | `/branch`（2.1.77）；後 `/fork` 另改為「複製成背景 session」（2.1.212），session 內分叉子代理改 `/subtask` | v2.1.77（03-17・w12）／v2.1.212（07-17・w29） |
| `/output-style` | deprecated 改 `/config`（2.1.73）；2.1.269 又加回 `/output-style [name]` | v2.1.73（03-11・w11） / v2.1.269（09-11・w37） |
| effort 最高 `max`（曾移除） | 2.1.72 簡化為 low/medium/high；2.1.111 新增 xhigh | v2.1.72（03-10・w11） |
| `TaskOutput` 工具 | Read 背景任務輸出檔；deprecated→移除 | v2.1.83（03-25・w13） → v2.1.277（09-18・w38） |
| `Ctrl+F` 停所有背景 agents | `Ctrl+X Ctrl+K` | v2.1.83（03-25・w13） |
| `/vim`、`/tag` | 移除（改 `/config` Editor mode） | v2.1.92（04-04・w14） |
| `/buddy` | 愚人節限定，已不可用 | v2.1.89（04-01・w14） |
| 原生版 `Glob`／`Grep` 工具 | 內嵌 `bfs`／`ugrep`（經 Bash 使用） | v2.1.117（04-22・w17） |
| `/cost`、`/stats` | 併入 `/usage`（仍可輸入舊名開對應分頁） | v2.1.118（04-23・w17） |
| `/undo` | `/rewind` 別名；`/proactive` = `/loop` 別名 | v2.1.105（04-13・w16） / v2.1.108（04-14・w16） |
| `--enable-auto-mode`、auto mode opt-in | 不再需要 | v2.1.111（04-16・w16）、v2.1.152（05-27・w22） |
| `claude project purge` | `claude purge` | v2.1.288（10-02・w40） |
| `/simplify` | `/code-review`（2.1.147）；`/simplify` 之後另作「只清理」（2.1.154）；`/review` 為 `/code-review` 別名（2.1.223） | v2.1.147（05-21・w21） |
| "extra usage"／`/extra-usage` | "usage credits"／`/usage-credits` | v2.1.144（05-19・w21） |
| `CLAUDE_CODE_OPUS_4_6_FAST_MODE_OVERRIDE` | deprecated→移除 | v2.1.154（05-28・w22） → v2.1.160（06-02・w23） |
| 動態 workflow 觸發詞 `workflow` | `ultracode`；2.1.284 起 Ultracode 為 `/effort` 內獨立開關 | v2.1.160（06-02・w23） |
| Windsurf（`/ide`、`/terminal-setup`） | Devin Desktop | v2.1.162（06-03・w23） |
| `TeamCreate`／`TeamDelete` | 移除；`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` 時每 session 有隱含團隊 | v2.1.178（06-15・w25） |
| 「default」權限模式 | 顯示名稱改 Manual（`--permission-mode manual` 與 `default` 並收） | v2.1.200（07-03・w27）|
| `/agents` 精靈 | 移除；請 Claude 建立子代理或直接編輯 `.claude/agents/` | v2.1.198（07-01・w27） |
| `/fork` 內的 session 子代理 | `/subtask` | v2.1.212（07-17・w29） |
| 快速模式支援 Opus 4.7 | 移除（改 Opus 5、Opus 4.8） | v2.1.219（07-24・w30） |
| Task 工具 `mode` 參數 | deprecated，改繼承父權限模式 | v2.1.212（07-17・w29） |
| Ultraplan（`/ultraplan`） | 移除，改用 plan mode 或 Web 版 | v2.1.222（08-04・w32） |
| `TaskCreate`／`TaskUpdate`／`TodoWrite` | 新模型不再提供（`CLAUDE_CODE_ENABLE_TODO_TOOLS=1` 可重啟用） | v2.1.233（08-14・w33） |
| `/config` 的 "Default teammate model" | 移除（隊友用 leader 模型） | v2.1.234（08-17・w34） |
| `keybindingFlavor` 設定 | 2.1.261 起提示字詞鍵一律 readline 式，設定無作用 | v2.1.261（09-04・w36） |
| 專案層 `defaultMode: "bypassPermissions"` | 被忽略（改在 user／managed 或 `--permission-mode`） | v2.1.257（09-01・w36） |
| `/ultrareview` 瀏覽器連結 | 移除 | v2.1.286（09-30・w40） |
| 模型名後綴 `[1m]` | 無作用時不再顯示（仍接受） | v2.1.311（10-26・w44） |
| `--sandbox`／`--no-sandbox`（`claude remote-control`） | 移除（傳入即報錯） | v2.1.300（10-14・w42） |
| Read 的「file unchanged」stub | 移除，重讀回傳內容 | v2.1.317（11-03・w45） |
| Opus 4.8 快速模式 | 2026-10-30 deprecated，預計 2026-11-30 移除 | v2.1.316（10-31・w44） |
| 獨立 Claude Design（claude.ai/design） | 2026-12-14 關閉（`/design-sync`、`/design-login` 通知） | v2.1.302（10-16・w42） |

# 現況對帳：原子記憶系統用到的 Claude Code 原生機制

> 用途：給後續「依官方最新文件分析可進化點」的 agent 當起點。只記**現況**，不下結論、不提建議。
> 真源順序：程式碼與設定（`settings.json`、`hooks/`、`skills/`、`tools/workflow-guardian-mcp/`）＞ TECH／Architecture 文件。文件跟程式不一致的地方，以程式為準並在行內標「文件差」。
> 官方對照：同資料夾 `Docs/`（zh-TW 官方頁鏡像，hooks.md lastmod 2026-11-03）。上一次對照官方的紀錄是 [`../cc-native-memory-hooks-mcp.md`](../cc-native-memory-hooks-mcp.md)（查證日 2026-08-28），反編譯實測在 [`../cc-hook-system.md`](../cc-hook-system.md)。
> 連結都是相對本檔的路徑（`../../../` ＝ repo 根 `~/.claude`）。

---

## 1. Hook 事件使用表

### 1.1 入口鏈與共通形狀

- 真源：[`settings.json`](../../../settings.json) 的 `hooks` 區。
- 所有 handler 都是 `type: "command"`，指令用 shell 形式：`"$LOCALAPPDATA/Python/bin/pythonw.exe" -c "import runpy…run_path(~/.claude/hooks/xxx.py)"`；bash 腳本經 [`hooks/run-bash-hidden.py`](../../../hooks/run-bash-hidden.py) 轉跑。
- guardian 主線：[`hooks/workflow-guardian.py`](../../../hooks/workflow-guardian.py)（shim）→ [`hooks/dispatcher.py`](../../../hooks/dispatcher.py)（依 `hook_event_name` 惰性 import）→ [`hooks/handlers/<event>.py`](../../../hooks/handlers/)。
- dispatcher 另有兩種縮減路由：
  - 寫碼守門關閉（`coding_guard.enabled=false`）時，`PostToolUseFailure`、`SubagentStop` 不分派，工具也照 `PRE_V6_TOOLS` 收窄。
  - 裁判子 session（環境變數 `CLAUDE_COMPANION_JUDGE=1`）走 `JUDGE_HANDLERS`，只留寫碼查核。
- **沒用到的 handler 型別與欄位**：`http`、`mcp_tool`、`prompt`、`agent` 型 hook；`if` 欄位。`async`／`asyncRewake` 由 Codex 審查 hook 使用。
- 背景工作一律由 hook 自己 spawn detached 子程序（[`hooks/run-hidden.py`](../../../hooks/run-hidden.py)、[`hooks/extract-worker.py`](../../../hooks/extract-worker.py)、[`hooks/vcs-sync-worker.py`](../../../hooks/vcs-sync-worker.py)、codex audit），沒用 `async`。
- 全部 hook 都不用 exit code 2（grep `exit(2)` 為 0）；擋或注入一律走 stdout JSON。

### 1.2 官方 33 個事件逐列

官方事件名取自 [`06-reference/hooks.md`](06-reference/hooks.md) 的事件總表。用到 14 個，沒用到 19 個。

| 事件 | 狀態 | handler 檔 | 做什麼（一句） | 回傳欄位 | timeout（秒）／matcher |
|---|---|---|---|---|---|
| `SessionStart` | 用 | [`hooks/user-init.sh`](../../../hooks/user-init.sh) | 從 `USER-<帳號>.md`／template 生出 `USER.md`，`IDENTITY.md` 不見時從 template 還原 | 無（只有檔案副作用） | 12／無 |
| 〃 | 用 | [`hooks/handlers/session_start.py`](../../../hooks/handlers/session_start.py) | 建立或複用 session state；`source` 分成 startup、resume、compact；spawn 記憶庫拉取 worker、vector 啟動器；送開場 advisory | `hookSpecificOutput.additionalContext` | 20／無 |
| 〃 | 用 | [`hooks/ensure-mcp.py`](../../../hooks/ensure-mcp.py) | 照 template 把 MCP server 合併進 `~/.claude.json`，背景 npm 安裝與更新 | 無 | 5／無 |
| 〃 | 用 | [`hooks/codex_companion.py`](../../../hooks/codex_companion.py) | 建 companion state；沒有可用的裁判後端時，每台機器揭露一次 | `additionalContext` | 5／無 |
| `Setup` | 未用 | — | — | — | — |
| `UserPromptSubmit` | 用 | [`hooks/handlers/user_prompt_submit.py`](../../../hooks/handlers/user_prompt_submit.py)，接著跑 `ups_gates`、`ups_context`、`ups_search`、`ups_inject` | **記憶注入主路徑**（trigger＋BM25＋vector→RRF→預算裁切），外加 guard 提醒、episodic、_AIDocs 指標 | `additionalContext` | 8／無 |
| 〃 | 用 | [`hooks/codex_companion.py`](../../../hooks/codex_companion.py) | 把背景 Codex 審查結果（`companion-assessment-*.json`）帶進來 | `additionalContext` | 3／無 |
| `UserPromptExpansion` | 評估後未用：輸入只有指令那一行，改在 UPS 接交接單 | —（目前沒掛 hook） | `/continue` 的檢索查詢改由 UserPromptSubmit 接交接單前 30 行（[`ups_search.retrieval_query`](../../../hooks/handlers/ups_search.py)，規則 CONTINUE_QUERY_FROM_HANDOFF） | — | — |
| `MessageDisplay` | 未用 | — | — | — | — |
| `PreToolUse` | 用 | [`hooks/plan_bash_guard.py`](../../../hooks/plan_bash_guard.py) | 只在 `permission_mode=="plan"` 時動作，擋掉一定會彈權限窗的 Bash 寫法 | `permissionDecision: deny`＋`permissionDecisionReason` | 5／`Bash` |
| 〃 | 用 | [`hooks/handlers/pre_tool_use.py`](../../../hooks/handlers/pre_tool_use.py) | 寫入守門（含 `MemoryPathBlock`）、跨 session 同檔預警、索引合併閘、git 隱私閘、commit 口令閘、提問閘；**子代理記憶注入** | `deny`＋`permissionDecisionReason`；`updatedInput`（改寫 Agent 的 prompt）；預警時同時送 `additionalContext` 與 `systemMessage`；從不回 `allow` | 5／`Write\|Edit\|MultiEdit\|NotebookEdit\|Bash\|PowerShell\|Agent\|Task\|AskUserQuestion\|ExitPlanMode\|mcp__workflow-guardian__atom_{write,edit_meta,retire,move}` |
| `PermissionRequest` | 未用 | —（`defaultMode: bypassPermissions`） | — | — | — |
| `PermissionDenied` | 未用 | — | — | — | — |
| `PostToolUse` | 用 | [`hooks/handlers/post_tool_use.py`](../../../hooks/handlers/post_tool_use.py) | 改檔追蹤、增量索引、紅測偵測、changelog 自動滾動、收割回報核對、Depends 指標、Source／Quote 自動回填、skill 索引同步；Read 走快路徑，只追加 read-log | `additionalContext`＋`systemMessage` | 5／`Edit\|Write\|MultiEdit\|NotebookEdit\|ExitPlanMode\|Bash\|PowerShell\|Read\|Agent\|Task\|mcp…anti_evasion_report\|atom_write\|atom_retire\|knowledge_harvest_report` |
| 〃 | 用 | [`hooks/codex_companion.py`](../../../hooks/codex_companion.py) | 記事件，到檢查點就在背景 spawn audit | 無 | 3／`Edit\|Write\|Bash\|ExitPlanMode\|EnterPlanMode` |
| `PostToolUseFailure` | 用（守門開才分派） | `post_tool_use.handle_post_tool_use_failure` | 失敗指令造成的改檔與紅測照樣記帳，不擋 | 無 | 5／`Bash\|PowerShell` |
| `PostToolBatch` | 用 | [`hooks/handlers/post_tool_batch.py`](../../../hooks/handlers/post_tool_batch.py) | 壓縮後一次性重注入 atom 內文；提示補完 handoff stub；送收尾類提醒；提問閘的事後提醒 | `additionalContext` | 5／無 |
| `Notification` | 未用 | — | — | — | — |
| `SubagentStart` | 已用 | `hooks/handlers/subagent_start.py` | 補位注入子代理記憶（`additionalContext`） | `additionalContext` | — |
| `SubagentStop` | 用 | `stop.handle_subagent_stop`（[`hooks/handlers/stop.py`](../../../hooks/handlers/stop.py)） | 子代理寫碼查核（守門開才跑）；擋滿預算就放行並留帳；回填子代理效用帳（守門關也進） | `decision: block`＋`reason` | 20／無 |
| `TaskCreated` | 未用 | — | — | — | — |
| `TaskCompleted` | 未用 | — | — | — | — |
| `Stop` | 用 | [`hooks/handlers/stop.py`](../../../hooks/handlers/stop.py) | 收尾閘序：紅測→對帳→退避→收割→收尾檢核→同步…；token 用量 ≥0.85 時把預警附在擋訊息上 | `decision: block`＋`reason`；`systemMessage` | 20／無 |
| 〃 | 用 | [`hooks/codex_companion.py`](../../../hooks/codex_companion.py) | 軟閘只寫說明檔、不擋；驗收裁判在背景 spawn、不等結果 | 無 | 20／無 |
| 〃 | 用 | [`hooks/lang_guard.py`](../../../hooks/lang_guard.py) | 英文佔比超過門檻就讓模型續跑一回合、改用繁中重答；看 `stop_hook_active` 防無限續跑 | `additionalContext` | 5／無 |
| `StopFailure` | 已用 | [`hooks/handlers/stop_failure.py`](../../../hooks/handlers/stop_failure.py) | 記 `Logs/guard-stop_failure.jsonl`；待結算的注入歸因標 aborted | 無 | — |
| `TeammateIdle` | 未用 | — | — | — | — |
| `InstructionsLoaded` | 已用 | [`hooks/handlers/instructions_loaded.py`](../../../hooks/handlers/instructions_loaded.py) | 只記帳 `Logs/instructions-loaded.jsonl`（含壓縮後 `load_reason=compact` 重載） | 無 | — |
| `ConfigChange` | 未用 | — | — | — | — |
| `CwdChanged` | 未用 | — | — | — | — |
| `DirectoryAdded` | 未用 | — | — | — | — |
| `FileChanged` | 未用 | — | — | — | — |
| `WorktreeCreate` | 未用 | —（console 自己跑 `git worktree add`） | — | — | — |
| `WorktreeRemove` | 未用 | — | — | — | — |
| `PreCompact` | 用 | [`hooks/handlers/pre_compact.py`](../../../hooks/handlers/pre_compact.py) | 快照壓縮前已注入的 atom 名單；生成 episodic；寫 handoff stub（Auto-Handoff 第 2 層） | 無 | 5／無 |
| `PostCompact` | 用 | [`hooks/handlers/post_compact.py`](../../../hooks/handlers/post_compact.py) | 把 atom 緊湊內文 stash 起來（≤800 tok），設 `pending_reinjection` flag | 無（認定 PostCompact 不支援注入） | 5／無 |
| `PreModelSwitch` | 未用 | — | — | — | — |
| `PostModelSwitch` | 未用 | — | — | — | — |
| `SessionEnd` | 用 | [`hooks/handlers/session_end.py`](../../../hooks/handlers/session_end.py) | spawn 萃取 worker、episodic、decay、recall-miss、vcs-sync worker、GC | 只寫 stderr | 30／無 |
| 〃 | 用 | [`hooks/codex_companion.py`](../../../hooks/codex_companion.py) | 寫出 reflection metrics | 無 | 5／無 |
| `Elicitation` | 未用 | — | — | — | — |
| `ElicitationResult` | 未用 | — | — | — | — |

### 1.3 系統的認知跟官方現行文件對不上的點（只列事實，給後續 agent 判）

| 主題 | 系統文件寫法 | 官方現行頁寫法 |
|---|---|---|
| SessionEnd 時間（已修正：文件改為個別 `timeout` 可拉到最多 60 秒） | [TECH §6.3](../../../TECH.md)、[`../cc-native-memory-hooks-mcp.md`](../cc-native-memory-hooks-mcp.md) §8：全部 hook 共 1.5 秒硬牆，`timeout: 30` 無效，所以萃取改走 detached | [`hooks.md`](06-reference/hooks.md) 通用欄位 `timeout` 列：共用 1.5 秒，但個別 hook 設了更長的 `timeout` 時，預算會跟著拉高，最多 60 秒 |
| 事件數 | 上次對照列 30 個事件（標題寫 28 種） | 33 個，多了 `Setup`、`PreModelSwitch`、`PostModelSwitch` |
| UPS 上限 | 官方 30 秒，本機設 8 秒 | 相同（command 型預設降到 30 秒） |
| additionalContext 長度 | 預算用 token 算（每回合 1200、總額最多 3000） | 單一值超過 10,000 字元就改寫成檔案，只送路徑與前 2,000 字元預覽 |
| 注入文字的語氣 | 注入大量 `[Guardian:…] 禁止…` 這種命令句 | 官方建議寫成事實陳述，命令式的帶外文字可能觸發 prompt injection 防禦 |
| Stop 續跑 | 自己管擋次（`stop_gate_max_blocks` 2、`reconcile_gate.max_blocks_per_turn`） | 原生有 `stop_hook_active`＋連續 8 次續跑上限；另有 `additionalContext` 這條「非錯誤回饋」路，跟 `decision: block` 分開 |
| PreToolUse 舊欄位（已修正：`webfetch-guard.sh` 已移除） | `webfetch-guard.sh` 曾在 `hookSpecificOutput` 裡用 `reason` | 頂層 `decision`／`reason` 已棄用，應改用 `permissionDecisionReason` |

---

## 2. 設定與分層

### 2.1 用到的 settings 鍵（[`settings.json`](../../../settings.json)）

| 鍵 | 值 | 備註 |
|---|---|---|
| `permissions.allow` | 約 40 條（`Bash(python *)`、`Edit(*)`、`Read(//**)`、部分 MCP tool…） | — |
| `permissions.defaultMode` | `bypassPermissions` | 搭配 `skipDangerousModePermissionPrompt: true` |
| `hooks` | 14 個事件（§1） | 會由 [`tools/install.py`](../../../tools/install.py) 的 `merge_settings` 合併進使用者既有的 settings |
| `statusLine` | command 型，跑 [`tools/statusline.py`](../../../tools/statusline.py)，`refreshInterval: 10` | 用 `python.exe`，不是 pythonw |
| `language` | `繁體中文` | 同時另有 `lang_guard` Stop hook |
| `effortLevel`／`modelSettings.<model>.effortLevel` | high；opus-5-5 用 xhigh；fable-5-1 用 medium | — |
| `model` | `fable` | — |
| `tui`／`theme` | `fullscreen`／`light` | — |
| `idleCompaction` | `false` | — |
| `switchModelsOnFlag`／`agentPushNotifEnabled` | false／true | — |
| `autoMemoryEnabled` | `false` | 關掉原生 auto memory |
| `crossSessionInbound` | `accept` | 接受跨 session 訊息 |
| `cleanupPeriodDays` | `14` | 逐字稿保留天數 |
| `worktree.baseRef` | `head` | 原生 worktree 從目前 HEAD 起 |
| `claudeMdExcludes` | `["C:/Users/holylight/AGENTS.md"]` | 不載入家目錄 AGENTS.md |

**沒用到的鍵**（官方 settings 文件裡有）：`env`、`enabledPlugins`、`extraKnownMarketplaces`、`autoMemoryDirectory`、`outputStyle`、`attribution`、`teammateMode`、`disableAllHooks`、`allowManagedHooksOnly`。

### 2.2 分層現況

| 層 | 用了沒 | 現況 |
|---|---|---|
| managed settings／managed policy CLAUDE.md | 無 | `C:/ProgramData/ClaudeCode` 不存在；程式 grep 也沒有 |
| 使用者層 `~/.claude/settings.json` | 用 | **`~/.claude` 本身就是 git repo**，`settings.json` 進版控，多台機器靠 git 同步同一份使用者設定 |
| 專案層 `.claude/settings.json` | 無 | cwd=`~/.claude` 時，專案層應該是 `~/.claude/.claude/`，那裡只有 local 檔 |
| local `.claude/settings.local.json` | 有檔、內容空 | [`.claude/settings.local.json`](../../../.claude/settings.local.json) 只有 `allow: []` |
| `~/.claude.json` | 用 | `mcpServers`（user scope）由 `ensure-mcp.py` 寫入；console-spawn 會替 worktree 補信任紀錄 |
| 系統自己的設定層 | 用（非 CC 機制） | `workflow/config.json` → `config.local.json` → 環境變數 `WG_*`（[TECH §12](../../../TECH.md)、[`TECH/config.md`](../../../TECH/config.md)） |

### 2.3 指令檔（CLAUDE.md、rules、auto memory）

| 機制 | 用了沒 | 現況 |
|---|---|---|
| `~/.claude/CLAUDE.md` + `@import` | 用 | [`CLAUDE.md`](../../../CLAUDE.md) 只有 4 行：`@IDENTITY.md @USER.md @memory/MEMORY.md`。atom 索引就是靠這條常駐，壓縮後也會重載 |
| 使用者級 rules `~/.claude/rules/` | 用 | [`rules/core.md`](../../../rules/core.md) 沒有 `paths:`，每場都載；[`rules/code-thinking.md`](../../../rules/code-thinking.md)、[`rules/coding-style.md`](../../../rules/coding-style.md) 用 `paths:` 限定程式檔副檔名 |
| 每場固定代價 | — | 約 4,970 tok；碰到程式檔再加約 3,560 tok（[TECH §11.1](../../../TECH.md)） |
| `CLAUDE.local.md` | 無 | 個人化改由 `user-init.sh` 從 `USER-<帳號>.md` 複製出 `USER.md` |
| `AGENTS.md` | 間接 | 家目錄 `C:/Users/holylight/AGENTS.md`（給 Codex 用）在 cwd 位於家目錄底下時，會被當成上層專案指令載入（本 session 的 context 可見）；這個檔不在 repo 裡 |
| auto memory `~/.claude/projects/<slug>/memory/` | 用（只放橋接） | 原生 `MEMORY.md` 只有 1 行，指向 `atom-index-bridge.md`；橋接檔內容只有指標 |
| auto memory 寫入 | 關閉＋被擋 | 模型用 Write／Edit 寫 `projects/*/memory/` 時，PreToolUse 的 `MemoryPathBlock`（[`hooks/wg_core.py`](../../../hooks/wg_core.py)）會擋下，導去 `atom_write`；另以 `autoMemoryEnabled: false` 關掉原生功能 |
| 專案層記憶（非原生） | 用 | `{專案}/.claude/memory/`（shared／personal）、公司層 org repo；三層 scope 見 [TECH §4.4](../../../TECH.md) |

---

## 3. 擴充機制

### 3.1 Skills（[`skills/`](../../../skills/)，31 個在用）

- frontmatter 用到的鍵：`name`、`description`、`disable-model-invocation`（13 個）、`user-invocable`（11 個）。
- 自訂、非原生的鍵：`triggers`（12 個）、`pattern`（12 個）。hook 程式沒讀這兩個鍵（推論：只給人看，或給 skill-creator 慣例用）。
- 沒用到的原生鍵：`allowed-tools`、`argument-hint`、`when_to_use`、`paths`、`model`、`context: fork`、`agent`、`hooks`。
- 其他：
  - 計數鏡像 [`skills/_skill_index.json`](../../../skills/_skill_index.json)：由 [`tools/skill-index.py`](../../../tools/skill-index.py) 生成，PostToolUse 改到 SKILL.md 時自動重生。
  - `skills/_archived/`：init-roles、conflict-review。
  - `skills/synced/`：claude.ai 同步下來的 skill，gitignore，不算進 31 個。
  - `commands/` 已不存在，全部遷成 skill。

| skill | 誰能叫 | 一句用途 |
|---|---|---|
| atom-debug | 只有使用者 | 切換注入／萃取 debug log |
| atom-source | 兩者 | 回看 atom 的 Source／Quote 原句 |
| behavior-preservation | 兩者 | 重構等值證法 |
| browse-sprites | 只有使用者 | 批次圖片拼貼預覽 |
| changelog-debug | 只有使用者 | 手動滾動 _CHANGELOG |
| codex | 兩者 | 叫 Codex 當第二意見或施工者 |
| codex-companion | 只有使用者 | 切換 Codex 監督開關 |
| conflict | 兩者（預設） | atom 衝突偵測、待審草稿 |
| consciousness-stream | 兩者（預設） | 識流：連續對話流的記憶寫入 |
| console | 只有使用者 | 多 session 總控台、開工作軌 |
| continue | 只有使用者 | 讀 `_staging/next-phase*.md` 續接 |
| extract | 只有使用者 | 手動知識萃取 |
| fix-escalation | 只有使用者 | 反覆修不好時的升級協議 |
| generate-episodic | 只有使用者 | 手動生成 episodic atom |
| handoff | 兩者（預設） | 六區塊交接 prompt |
| harvest | 只有使用者 | Playwright 抓網頁、Docs |
| heal-review | 只有使用者 | 記憶自癒失敗佇列裁決 |
| journal | 只有使用者 | 從 atom＋git＋transcript 產工作日誌 |
| karpathy-guidelines | 兩者（預設） | 寫碼行為準則 |
| mailbox | 兩者 | 網路共用資料夾信箱（跨人、跨專案） |
| meeting | 兩者 | 會議錄音→摘要→寫進 shared 記憶 |
| memory | 兩者（預設） | health／review／score／classify |
| org | 兩者 | 公司層記憶接入與工具卡 |
| read-project | 兩者（預設） | 跨檔讀專案、寫 DocIndex |
| refile | 兩者 | 把 md 依 realm 分類歸檔 |
| skill-creator | 兩者 | 建立與稽核 skill |
| text-score | 兩者 | 文字規格評分（小模型裁判） |
| token | 兩者 | 量 session 的 token 用量 |
| upgrade | 只有使用者 | schema migration |
| usage-watch | 兩者 | 帳號用量監控、Discord 通知、排程 |
| vector | 兩者（預設） | Vector Service 管理 |

### 3.2 MCP

| server | 來源與註冊 | 層級 | 備註 |
|---|---|---|---|
| `workflow-guardian` | repo 內建 [`tools/workflow-guardian-mcp/server.js`](../../../tools/workflow-guardian-mcp/server.js)；SessionStart 的 `ensure-mcp.py` 照 [`mcp-servers.template.json`](../../../mcp-servers.template.json) 寫進 `~/.claude.json` | user | JSON-RPC 手寫（[`lib/mcp.js`](../../../tools/workflow-guardian-mcp/lib/mcp.js)），`protocolVersion 2025-11-25`；**只宣告 `tools`**，沒有 resources、prompts、server `instructions`、elicitation；同一個行程還開 `:3848` Dashboard 與 AEC HUD |
| `MCPControl` | npm `computer-use-mcp`，ensure-mcp 安裝 | user | 桌面截圖與操控 |
| `playwright` | npm `@playwright/mcp`，ensure-mcp 安裝 | user | 瀏覽器自動化 |
| `excel` | 在 `~/.claude.json` 裡，但不在 template | user | 手動加的 |
| `UnityMCP` | `~/.claude.json` 的 projects[`C:/Projects`] | local | 專案用 |
| `.mcp.json`（project scope） | 無 | — | — |

workflow-guardian 的 9 個 tool（[Architecture §MCP](../../Architecture.md)、[TECH §6.1](../../../TECH.md)）：

| tool | 一句 |
|---|---|
| `atom_write` | 建立、append、replace atom；過整條寫入閘，回 receipt |
| `atom_promote` | 改信心等級（[臨]→[觀]→[固]） |
| `atom_move` | 搬移 atom（含搬進 secret） |
| `atom_edit_meta` | 改 metadata 欄位 |
| `atom_retire` | 退役 atom |
| `anti_evasion_report` | 收尾報告（反退避） |
| `knowledge_harvest_report` | 階段收割回報；PostToolUse 拿 receipt 核對 |
| `memory_search` | 唯讀檢索，跟 hook 注入共用同一條管線 |
| `atom_source` | 唯讀回看卡片來源 |

### 3.3 其他擴充點

| 機制 | 用了沒 | 現況 |
|---|---|---|
| 自訂 subagent（`.claude/agents/`、`~/.claude/agents/`） | 無 | 兩處都不存在；只用內建 Agent 型別（含 `fork`） |
| plugin（把本系統打包成 plugin） | 無 | 本系統靠 git clone `~/.claude`＋[`tools/install.py`](../../../tools/install.py) 安裝 |
| 安裝的第三方 plugin | 有紀錄 | `plugins/installed_plugins.json`：`superpowers@claude-plugins-official` 7.0.0，user scope；`settings.json` 沒有 `enabledPlugins`，啟用狀態未確認；`plugins/` 不進版控 |
| output styles | 無 | 沒有 `output-styles/`，也沒有 `outputStyle` 鍵 |
| statusLine | 用 | [`tools/statusline.py`](../../../tools/statusline.py)：讀 state、`vector_ready.flag`、AEC 報告，加上 CC 送進來的 `context_window`、`prompt_cache` |
| headless `claude -p` | 用 | 驗收裁判 [`tools/codex-companion/judge_backend.py`](../../../tools/codex-companion/judge_backend.py)；console-spawn `--method print` |
| 排程 | 用 Windows 工作排程器（非 CC） | 週健檢 [`tools/health-weekly.py`](../../../tools/health-weekly.py)（schtasks）；[`tools/usage-watch.py`](../../../tools/usage-watch.py)（Register-ScheduledTask）。理由見 [Architecture §常駐可觀測層](../../Architecture.md)：CronCreate／Routines 是雲端，碰不到本機 |
| mods（plugin-authoring 面板） | 無 | 可視化走自架 `:3848` 網頁與 `world.html` |

---

## 4. 多 session／多 agent

### 4.1 用到的原生機制

| 原生機制 | 怎麼用 | 位置 |
|---|---|---|
| `SendMessage`／`ListAgents`（跨 session 訊息） | 總控台與工作軌互報到、交付信（全文經 SendMessage 傳）、轉送更新 | [`skills/console/SKILL.md`](../../../skills/console/SKILL.md)、[`references/kickoff.md`](../../../skills/console/references/kickoff.md)、[MultiSession §5](../../MultiSessionCollaboration.md) |
| `claude --bg --name <名> "<開工句>" --permission-mode --model --settings` | 自動開背景工作軌 | [`skills/console/scripts/console-spawn.py`](../../../skills/console/scripts/console-spawn.py) |
| `claude agents --json`／`attach`／`stop` | 輪詢報到、看是否卡在問人、收掉 session | 同上 |
| `--worktree`／`worktree.baseRef: head` | 原生 worktree（落在 `.claude/worktrees/`）；工作軌隔離，交付走 SendMessage |
| `/goal <完成條件>` | 長任務自動續跑 |
| `EnterWorktree(<已存在路徑>)` | 工作軌切進既有 worktree；交付因隔離只能改走 SendMessage | [MultiSession §6](../../MultiSessionCollaboration.md) |
| Agent 工具（含 `subagent_type: fork`） | 子代理；PreToolUse 在 prompt 前面注入記憶（fork 只補父對話沒有的） | [`hooks/handlers/pre_tool_use.py`](../../../hooks/handlers/pre_tool_use.py) |
| Monitor（背景監看） | 檔案信箱喚醒（約 2 秒級） | atom `並行llm即時通訊-inbox機制`（[`memory/工作流/協作與並行/`](../../../memory/工作流/協作與並行/)） |
| Bash `run_in_background` 短 sleep 當鬧鐘 | 等 SendMessage 回覆時叫醒自己 | [MultiSession §5](../../MultiSessionCollaboration.md) |

### 4.2 自製的替代品與周邊

| 自製物 | 做什麼 | 位置 |
|---|---|---|
| `/console` 雙總控台＋工作軌 | 對人與調度兩種角色、派工、對帳、合併、推送 | [`skills/console/`](../../../skills/console/)、[TECH §13.4](../../../TECH.md) |
| 派工信箱 `workflow/inbox/` | 派工單 `to-track-*`、交付信 `from-track-*`、裁定帳；本機、不進版控 | `workflow/inbox/` |
| 原生 worktree | console-spawn 以 `--worktree`＋`--name` 開工作軌，不再手動 `git worktree add`；console-spawn 補 `~/.claude.json` 信任 | [`skills/console/references/dispatch.md`](../../../skills/console/references/dispatch.md) |
| 根層↔專案信箱協議 | 專案 `.claude/inbox/` 的 `root-link/` 雙槽、`tri-link/` 三槽 | [MultiSession §5](../../MultiSessionCollaboration.md) |
| 跨模型檔案信箱 | `~/.grok/.ai-inbox/`（`to-grok`／`to-claude`／`to-opus`／`to-fable`），一信一檔，靠 Monitor 喚醒 | atom `並行llm即時通訊-inbox機制` |
| `mailbox` skill | 網路共用資料夾信箱，跨人（企劃／程式）、不依賴 CC | [`skills/mailbox/`](../../../skills/mailbox/) |
| 跨 session 同檔預警 | 別的活 session 已改過的檔再被改，或有人要做 `git add -A` 這類收尾指令時，只警告不擋 | [`hooks/wg_coordination.py`](../../../hooks/wg_coordination.py) |
| state 檔鎖 `STATE_RMW_LOCKED` | 平行 hook／子代理共用 `workflow/state-<sid>.json` 時的讀改寫鎖與待併帳 | [`hooks/wg_core.py`](../../../hooks/wg_core.py)、[TECH §3.1](../../../TECH.md) |
| `codex` skill／codex_companion | Codex 當第二意見或施工者；背景審查結果下一則 UPS 帶回 | [`skills/codex/`](../../../skills/codex/)、[`hooks/codex_companion.py`](../../../hooks/codex_companion.py) |
| 並行與研究 fan-out 建議 | UPS 依分數提示「可開子代理」 | [`hooks/wg_parallel.py`](../../../hooks/wg_parallel.py)、[`hooks/wg_research.py`](../../../hooks/wg_research.py) |

---

## 5. 記憶注入與 context

| 時機（事件） | 注入什麼 | 預算 | 回傳方式 | 位置 |
|---|---|---|---|---|
| 啟動（CLAUDE.md `@import`） | IDENTITY、USER、`memory/MEMORY.md` 範疇目錄、`rules/core.md` | 約 4,970 tok 常駐 | 原生載入 | [TECH §11.1](../../../TECH.md) |
| SessionStart（startup） | 開場 advisory（未 push、拉取結果、健檢、ScopeLayout…）、_AIDocs 一行指標 | 無硬頂；清單類只送一次 | `additionalContext` | [`session_start.py`](../../../hooks/handlers/session_start.py) |
| SessionStart（resume／compact） | 指紋相同就複用 state、清空 `injected_atoms`、列出壓縮前的 atom 名稱、`[Guardian:Resume]` 指向最新 `next-phase-*.md`；resume 遇到同 cwd 的活 sibling 就標 merged | 約 30 tok 名單 | `additionalContext` | 同上 |
| UserPromptSubmit | atom（全文、節錄或一行指標）、episodic（首則，≤3 筆、600 字）、_AIDocs 指標、JIT 管線說明、guard 提醒 | 每回合硬頂 `TURN_BUDGET_LIMIT` 1200；總額依 prompt 長度 1000、2000、3000 tok；尾行 `[Context budget: x/y]` | `additionalContext` | [`ups_inject.py`](../../../hooks/handlers/ups_inject.py)、[`wg_core.py`](../../../hooks/wg_core.py)、[TECH §5](../../../TECH.md) |
| PreToolUse（Agent／Task） | `[WG:SubagentMemory]` 緊湊 atom | 700 tok（`_SUBAGENT_INJECT_BUDGET`） | `updatedInput.prompt` 前置 | [`pre_tool_use.py`](../../../hooks/handlers/pre_tool_use.py) |
| PostToolUse | `[Guardian:Depends]`：讀到某卡的壞滅緣檔時給一行卡指標；碰到 authority_map 時給地圖 | 一行一卡 | `additionalContext` | [`hooks/wg_depends.py`](../../../hooks/wg_depends.py) |
| PreCompact | 快照 `pre_compact_injected_atoms`；生成 episodic；寫 handoff stub（`next-phase-auto.md`） | — | 無 | [`pre_compact.py`](../../../hooks/handlers/pre_compact.py) |
| PostCompact | stash atom 緊湊內文（PostToolBatch 補位用），設 `pending_reinjection` | 800 tok（`atoms.post_compact_budget`） | 無 | [`post_compact.py`](../../../hooks/handlers/post_compact.py) |
| PostToolBatch | 壓縮後第一批工具結束時一次性重注入，加上 stub 補完提示 | 同上 | `additionalContext` | [`post_tool_batch.py`](../../../hooks/handlers/post_tool_batch.py) |
| Stop | 讀 transcript 的 `message.usage` 算用量比（分母 `context_window_tokens`，預設 1M），≥0.85 就附 token 預警 | 一次性 | 附在擋訊息上 | [`stop.py`](../../../hooks/handlers/stop.py)、[`hooks/wg_handoff.py`](../../../hooks/wg_handoff.py) |
| SessionEnd | 直接結束且沒交接時補寫 stub（Auto-Handoff 第 4 層） | — | 無 | [`session_end.py`](../../../hooks/handlers/session_end.py) |

補充：
- **壓縮怎麼接**：`idleCompaction: false`。壓縮順序實測是 PreCompact → SessionStart(compact) → PostCompact，主路是 SessionStart(compact) 直送 PreCompact 快照內文，PostToolBatch 補位（[`../cc-hook-system.md`](../cc-hook-system.md)）。atom 索引靠 CLAUDE.md `@import` 在壓縮後由原生重載，系統不重送。
- **auto memory 橋接**：auto memory 的原生目錄只放指標檔，模型寫進去會被擋；atom 的真源與檢索都在原子記憶系統（§2.3）。
- **subagent**：記憶主路是 PreToolUse 改寫 prompt 字串，SubagentStart 的 `additionalContext` 補位（[`../cc-hook-system.md`](../cc-hook-system.md)）。
- **resume 重播**：官方說 UPS、PostToolUse 這類中途事件注入的文字，resume 時直接重播、不重跑 hook；SessionStart 會以 `source=resume` 再跑（atom `sessionstart在resume與compact每次都再跑…` 已記錄）。
- **可觀測**：每回合的注入記在 `Logs/injection-turns.jsonl`；hook 分段計時用 [`hooks/wg_hook_timing.py`](../../../hooks/wg_hook_timing.py)，UPS 用到 80% 時間就降級，95% 由背景鬧鐘代送（守門開時）。

---

## 6. 自製、但原生可能已有類似機制的候選

> 只列「看起來像」，不判斷該不該換。對照欄是後續 agent 該讀的官方頁。

| # | 自製功能（位置） | 看起來像的原生機制 | 對照官方頁 | 處置 |
|---|---|---|---|---|
| 1 | 子代理記憶注入：PreToolUse `updatedInput` 改寫 Agent prompt（[`pre_tool_use.py`](../../../hooks/handlers/pre_tool_use.py)） | `SubagentStart` hook 的 `additionalContext`（壓縮後會再注入） | [`06-reference/hooks.md`](06-reference/hooks.md) SubagentStart、[`02-build/sub-agents.md`](02-build/sub-agents.md) | 做（SubagentStop 回填） |
| 2 | 壓縮後復原：PostCompact stash → PostToolBatch 注入（[`post_compact.py`](../../../hooks/handlers/post_compact.py)、[`post_tool_batch.py`](../../../hooks/handlers/post_tool_batch.py)） | SessionStart matcher `compact` 的 `additionalContext`；InstructionsLoaded(`compact`) | [`hooks.md`](06-reference/hooks.md) SessionStart／PostCompact、[`01-getting-started/context-window.md`](01-getting-started/context-window.md) | 做（SessionStart(compact)） |
| 3 | hook 自己 spawn detached worker（`run-hidden.py`、`extract-worker.py`、`vcs-sync-worker.py`、codex audit） | hook 的 `async: true`、`asyncRewake` | [`hooks.md`](06-reference/hooks.md)「在背景執行 hooks」 | async／asyncRewake（Codex 審查已用） |
| 4 | 「SessionEnd 1.5 秒硬牆」的前提（[TECH §6.3](../../../TECH.md)） | 個別 hook 設 `timeout` 時預算可拉到最多 60 秒 | [`hooks.md`](06-reference/hooks.md) 通用欄位 | 文件更正 |
| 5 | Stop 擋次預算與續跑控制（`stop_gate_max_blocks`、`reconcile_gate.max_blocks_per_turn`） | `stop_hook_active`＋連續 8 次上限；Stop 的 `additionalContext` 非錯誤回饋 | [`hooks.md`](06-reference/hooks.md) Stop 決策控制 | 自管預算保留；提醒不走 additionalContext（原生續跑代價同擋） |
| 6 | 驗收裁判／Codex 第二意見（[`codex_companion.py`](../../../hooks/codex_companion.py)、`judge_backend.py` 起 headless `claude -p`） | `type: "agent"`／`"prompt"` hook；advisor 模型 | [`hooks.md`](06-reference/hooks.md)「基於代理的 hooks」、[`05-configuration/advisor.md`](05-configuration/advisor.md) | 不採（同步擋流程） |
| 7 | `lang_guard` 防英文漂移（[`hooks/lang_guard.py`](../../../hooks/lang_guard.py)） | settings `language`（已設）、output styles | [`05-configuration/settings-reference.md`](05-configuration/settings-reference.md)、[`05-configuration/output-styles.md`](05-configuration/output-styles.md) | 不動 |
| 8 | `/console` 雙總控台＋派工信箱＋console-spawn（[`skills/console/`](../../../skills/console/)） | agent teams（共享任務、隊員互傳訊息、`TeammateIdle`／`TaskCreated` hook）、agent view、dynamic workflows | [`02-build/agent-teams.md`](02-build/agent-teams.md)、[`02-build/agent-view.md`](02-build/agent-view.md)、[`02-build/workflows.md`](02-build/workflows.md)、[`02-build/agents.md`](02-build/agents.md) | agent teams 不採 |
| 9 | 手動 `git worktree add` 到 `~/.claude-wt/`＋替 worktree 補 `~/.claude.json` 信任 | `--worktree` 旗標、`worktree.*` 設定（`location`、`bgIsolation`、`symlinkDirectories`…）、`.worktreeinclude`、`WorktreeCreate` hook | [`02-build/worktrees.md`](02-build/worktrees.md) | 做（`--worktree`） |
| 10 | 檔案信箱（`~/.grok/.ai-inbox/to-opus` 等、`root-link`／`tri-link`、`mailbox` skill） | 跨 session 訊息（含其他機器、雲端 session）、channels（MCP 推訊息進 session） | [`02-build/cross-session-messaging.md`](02-build/cross-session-messaging.md)、[`02-build/channels.md`](02-build/channels.md) | 做（SendMessage；mailbox 保留） |
| 11 | 跨 session 同檔預警（[`wg_coordination.py`](../../../hooks/wg_coordination.py)） | worktree 隔離、agent view 的總覽 | [`02-build/worktrees.md`](02-build/worktrees.md)、[`02-build/agent-view.md`](02-build/agent-view.md) | 保留預警，附對方名 |
| 12 | handoff／continue／`next-phase-auto.md`＋auto-continue watcher（headless `/continue`） | `--continue`／`--resume`、`/goal` 完成條件、`/loop` 與排程、checkpointing 摘要 | [`02-build/goal.md`](02-build/goal.md)、[`02-build/scheduled-tasks.md`](02-build/scheduled-tasks.md)、[`06-reference/checkpointing.md`](06-reference/checkpointing.md) | 做（`/goal`） |
| 13 | 收尾閘的「宣告完成」檢核、need-goal | `/goal`（模型判定完成條件） | [`02-build/goal.md`](02-build/goal.md) | need-goal 已退役 |
| 14 | episodic atom（SessionEnd／PreCompact 產生的 session 摘要，TTL 24 天）、`journal` skill | 原生 auto memory、transcript、checkpointing summarize | [`01-getting-started/memory.md`](01-getting-started/memory.md)、[`06-reference/checkpointing.md`](06-reference/checkpointing.md) | 不動 |
| 15 | 擋掉原生 auto memory 寫入（`MemoryPathBlock`）＋橋接檔 | `autoMemoryEnabled`、`autoMemoryDirectory`（可指到別處） | [`01-getting-started/memory.md`](01-getting-started/memory.md)「自動記憶」 | 做（`autoMemoryEnabled: false`） |
| 16 | `ensure-mcp.py` 每次 SessionStart 改寫 `~/.claude.json` 的 `mcpServers` | `claude mcp add --scope user`、project `.mcp.json`、plugin 內附 MCP | [`02-build/mcp.md`](02-build/mcp.md)、[`03-plugins/plugins__components.md`](03-plugins/plugins__components.md) | 做（`claude mcp add-json`；自我修復保留） |
| 17 | 散佈方式：git clone `~/.claude`＋`install.py` 合併 hooks；公司層 org repo；`user-init.sh` 依帳號產 USER.md | plugin 打包（hooks、skills、MCP 一包）＋marketplace、組織 plugin、managed settings、`CLAUDE.local.md`／家目錄 import | [`03-plugins/plugins__overview.md`](03-plugins/plugins__overview.md)、[`03-plugins/plugins__org.md`](03-plugins/plugins__org.md)、[`04-administration/`](04-administration/)、[`01-getting-started/memory.md`](01-getting-started/memory.md) | 不打包 plugin |
| 18 | skill 自訂 frontmatter `triggers`／`pattern`，加 `_skill_index.json` 計數 | 原生 `description`／`when_to_use`、skill `paths:`、plugin relevance | [`02-build/skills.md`](02-build/skills.md)、[`03-plugins/plugins__relevance.md`](03-plugins/plugins__relevance.md) | 做（`when_to_use`） |
| 19 | `memory` skill 的 health、規則檔一致性檢查、[`tools/config-consistency.py`](../../../tools/config-consistency.py) | `/doctor prompt-audit`（審查 CLAUDE.md、rules、skills 的過時與衝突） | [`01-getting-started/memory.md`](01-getting-started/memory.md)「審計您的指令檔案」 | 做（官方三件健檢接週健檢） |
| 20 | hook 計時帳、guard JSONL、Dashboard／AEC HUD `:3848` | `/hooks` 選單、debug log、OTEL 監控、mods 側欄面板 | [`hooks.md`](06-reference/hooks.md)「偵錯 hooks」、[`03-plugins/plugins__mods__overview.md`](03-plugins/plugins__mods__overview.md)、[`04-administration/`](04-administration/) | 做（debug log 量尺） |
| 21 | Windows 工作排程器跑週健檢、用量監控 | Desktop scheduled tasks（本機）、`/loop`、Routines | [`01-getting-started/desktop-scheduled-tasks.md`](01-getting-started/desktop-scheduled-tasks.md)、[`02-build/scheduled-tasks.md`](02-build/scheduled-tasks.md) | 不搬 |
| 22 | 背景軌不准發 AskUserQuestion（派工單規矩）、提問閘 `wg_ask_gate` | PreToolUse `defer`（把工具呼叫延到稍後）、`-p` 無人回應時的拒絕行為 | [`hooks.md`](06-reference/hooks.md)「將工具呼叫延遲到稍後」、[`02-build/headless.md`](02-build/headless.md) | 做（CLAUDE_JOB_DIR） |
| 23 | `plan_bash_guard` 繞開 plan mode 的權限彈窗 | 權限規則、auto mode、sandbox | [`05-configuration/permissions.md`](05-configuration/permissions.md)、[`05-configuration/permission-modes.md`](05-configuration/permission-modes.md) | 不動 |
| 24 | `webfetch-guard.sh` 用 curl 先探 URL，防止卡住 | WebFetch 本身的逾時與錯誤處理（未查） | [`06-reference/tools-reference.md`](06-reference/tools-reference.md) | 做（webfetch-guard 拆） |
| 25 | 自寫 MCP server 只開 tools | MCP server `instructions`、resources、prompts、elicitation（`Elicitation` hook） | [`02-build/mcp.md`](02-build/mcp.md) | 做：initialize 對非 Claude Code 客戶端送 instructions，memory_search 標開場載入 |

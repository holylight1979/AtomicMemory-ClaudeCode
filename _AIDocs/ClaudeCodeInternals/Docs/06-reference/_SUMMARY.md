# 06-reference 導讀（10 頁）

> 來源：code.claude.com/docs/zh-TW，harvested 2026-11-04。八頁屬 Reference、一頁 Glossary、一頁 Resources。
> 查 hook 事件、旗標、工具、指令、環境變數、快捷鍵時先翻這夾。

## Reference

### Hooks 參考（`hooks`）
- 檔案：[hooks.md](hooks.md)｜https://code.claude.com/docs/zh-TW/hooks｜lastmod 2026-11-03｜278 KB
- 一句話：所有 hook 事件、設定結構、stdin JSON 輸入、退出碼與 JSON 輸出、可回傳的決定欄位，一頁講完。
- 何時讀：寫或除錯任何 hook（含記憶系統的注入、寫入閘、收尾守門）前。
- 關鍵內容：
  1. **33 個事件**（節奏）：每工作階段 `SessionStart`／`SessionEnd`；每回合 `UserPromptSubmit`／`Stop`／`StopFailure`；每工具呼叫 `PreToolUse`／`PostToolUse`（`EndConversation` 除外）。
  2. 事件全表：`SessionStart` `Setup` `UserPromptSubmit` `UserPromptExpansion` `PreToolUse` `PermissionRequest` `PermissionDenied` `PostToolUse` `PostToolUseFailure` `PostToolBatch` `Notification` `MessageDisplay` `SubagentStart` `SubagentStop` `TaskCreated` `TaskCompleted` `Stop` `StopFailure` `TeammateIdle` `InstructionsLoaded` `ConfigChange` `CwdChanged` `DirectoryAdded` `FileChanged` `WorktreeCreate` `WorktreeRemove` `PreCompact` `PostCompact` `PreModelSwitch` `PostModelSwitch` `Elicitation` `ElicitationResult` `SessionEnd`。
  3. 通用輸入欄位（stdin JSON；HTTP hook 為 POST body）：`session_id` `prompt_id` `transcript_path` `cwd` `scratchpad_dir` `permission_mode` `effort.level` `hook_event_name`，子代理內另有 `agent_id` `agent_type`。transcript 是非同步寫入，可能落後；要本回合最後一句用 `last_assistant_message`（Stop／SubagentStop）。沒有 `$CLAUDE_MODEL` 環境變數；只有 `SessionStart` 可能帶 `model`。
  4. 事件專屬輸入重點：`SessionStart`＝`source`(startup/resume/clear/compact/fork)、`model`、`session_title`、恢復時的 `context_tokens`／`prompt_cache_likely_expired`；`Setup`＝`trigger`(init/maintenance)；`UserPromptSubmit`＝`prompt`；`UserPromptExpansion`＝`expansion_type` `command_name` `command_args`；`PreToolUse`＝`tool_name` `tool_input` `tool_use_id`；`PostToolUse`＝再加 `tool_response` `duration_ms`；`PostToolUseFailure`＝`error` `is_interrupt`；`PostToolBatch`＝`tool_calls[]`。
  5. 更多輸入：`Stop`＝`stop_hook_active` `last_assistant_message` `background_tasks` `session_crons`；`SubagentStop`＝再加 `agent_transcript_path`；`StopFailure`＝`error`(rate_limit/overloaded/authentication_failed…) `error_details`；`PreCompact`＝`trigger`(manual/auto) `custom_instructions`；`SessionEnd`＝`reason`(clear/resume/logout/prompt_input_exit/other)；`InstructionsLoaded`＝`file_path` `memory_type` `load_reason`；`FileChanged`＝`file_path` `event`(change/add/unlink)；`ConfigChange`＝來源 user/project/local/policy_settings/skills；`Elicitation`＝`mcp_server_name` `message` `mode` `requested_schema`；`PreModelSwitch`／`PostModelSwitch`＝`from_model` `to_model` `source`。
  6. 通用 JSON 輸出（exit 0 時印到 stdout）：`continue`(false＝整個停) `stopReason` `systemMessage`(給使用者看的警告) `terminalSequence`(OSC 通知／標題／BEL) `suppressOutput`(無效果)。巢狀 `hookSpecificOutput` 必須帶 `hookEventName`。
  7. **`additionalContext`** 注入 Claude 上下文（包成系統提醒）：支援 `SessionStart` `SubagentStart` `UserPromptSubmit` `UserPromptExpansion` `PreToolUse` `PostToolUse` `PostToolUseFailure` `PostToolBatch` `Stop` `SubagentStop` `PostModelSwitch`。`additionalContext`／`systemMessage`／`initialUserMessage`／純 stdout 各上限 10,000 字元，超過改存檔，只送路徑＋前 2,000 字預覽。多個 hook 的值全部送達。
  8. 決定控制分類：頂層 `decision:"block"`＋`reason`（`UserPromptSubmit` `UserPromptExpansion` `PostToolUse` `PostToolUseFailure` `PostToolBatch` `Stop` `SubagentStop` `ConfigChange` `PreCompact` `TaskCreated`）；`PreToolUse` 用 `hookSpecificOutput.permissionDecision`(allow/deny/ask/defer)＋`permissionDecisionReason`；`PermissionRequest` 用 `decision.behavior`(allow/deny)；`PermissionDenied` 用 `retry:true`；`WorktreeCreate` 用 stdout 路徑；`MessageDisplay` 用 `displayContent`；`PreModelSwitch` 用 `permissionDecision` 或 `decision:"block"`；`Elicitation`／`ElicitationResult` 用 `action`(accept/decline/cancel)＋`content`。
  9. 無決定控制、只能做副作用：`Setup` `Notification` `SessionEnd` `PostCompact` `InstructionsLoaded` `StopFailure` `CwdChanged` `DirectoryAdded` `FileChanged`。`SessionStart`／`SubagentStart`／`PostModelSwitch` 只能加上下文，不能擋。
  10. 改內容：`PreToolUse` 的 `updatedInput`（整個取代工具輸入）；`PermissionRequest` 的 `decision.updatedInput`／`updatedPermissions`(addRules/replaceRules/removeRules/setMode/addDirectories…，destination 為 session/localSettings/projectSettings/userSettings)；`PostToolUse` 的 `updatedToolOutput`／`updatedMCPToolOutput`／`classifierContext`。`UserPromptSubmit` 不能改 prompt，只能旁邊加 `additionalContext`／`sessionTitle`。
  11. `SessionStart` 專屬輸出：`additionalContext` `initialUserMessage`(-p 模式首句) `sessionTitle` `watchPaths`(之後觸發 FileChanged) `reloadSkills`。可寫 `CLAUDE_ENV_FILE` 保存環境變數給後續 Bash。`CwdChanged`／`FileChanged` 可回 `watchPaths`。
  12. 退出碼：0＝成功並解析 JSON；**2＝阻擋**（stderr 為原因，JSON 無法覆寫）；其他＝非阻擋錯誤。exit 2 可擋的事件：`PreToolUse` `UserPromptSubmit` `UserPromptExpansion` `Stop` `SubagentStop` `TeammateIdle` `TaskCreated` `TaskCompleted` `ConfigChange` `PostToolBatch` `PreCompact` `PreModelSwitch` `Elicitation` `ElicitationResult` `WorktreeCreate`／`WorktreeRemove`。不能擋：`PermissionRequest` `PostToolUse`(stderr 給 Claude) `Notification` `SessionStart` `SessionEnd` `StopFailure` 等。
  13. **timeout 預設（秒）**：`command`／`http`／`mcp_tool`＝600，`prompt`＝30，`agent`＝60；`UserPromptSubmit`／`PreModelSwitch`／`PostModelSwitch` 降為 30；`MessageDisplay` 為 10；`SessionEnd` 全體共用 1.5 秒預算（個別 `timeout` 可拉高到 60；環境變數 `CLAUDE_CODE_SESSIONEND_HOOKS_TIMEOUT_MS`）。逾時＝取消、無決定（`PreModelSwitch` 逾時會擋切換）。`Stop` hook 連續擋 8 次後強制結束（`CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`）。
  14. 五種 handler：`command`（`command`/`args`/`async`/`asyncRewake`/`shell`/`onFailure`）、`http`、`mcp_tool`、`prompt`（回 `{ok,reason,impossible}`）、`agent`（實驗性）。通用欄位 `type` `if`(權限規則語法，只對工具事件有效) `timeout` `statusMessage` `once`(僅 skill frontmatter)。符合的 hook 平行執行，相同 handler 去重；prompt／agent hook 同時最多 12 個。
  15. 位置與合併：`~/.claude/settings.json`、`.claude/settings.json`、`.claude/settings.local.json`、受管政策、外掛 `hooks/hooks.json`、skill／subagent frontmatter。各層合併不覆蓋。matcher：空／`*`＝全部；純字母數字與 `_-,|`＝精確比對清單；其他＝JS 正規表示式。`allowManagedHooksOnly`、`disableAllHooks`、`allowedHttpHookUrls` 控管。`async:true` 背景執行不擋、不能做決定，結果下回合以 `additionalContext`／`systemMessage` 送達。
- 新名詞：`hook event／matcher group／handler` ＝ 時間點／篩選條件／實際執行的東西，三層結構；`additionalContext` ＝ hook 往 Claude 上下文塞的一段文字；`updatedInput` ＝ 在工具執行前改寫其參數；`defer` ＝ PreToolUse 決定，暫停工具呼叫交給外部程式回答（-p／SDK 用）；`asyncRewake` ＝ 背景 hook 以 exit 2 喚醒 Claude；`terminalSequence` ＝ hook 要求 Claude Code 代發的終端機通知碼；`scratchpad_dir` ＝ 工作階段暫存目錄路徑；`stop_hook_active` ＝ 這回合已因 stop hook 繼續過。
- 記憶系統接點：`SessionStart`／`UserPromptSubmit`／`PostToolUse` 等可回 `additionalContext` 注入記憶；`Stop`／`PreToolUse` 可擋；`PreCompact`／`PostCompact`／`SessionEnd`／`InstructionsLoaded`／`ConfigChange` 為純副作用點；`mcp_tool` hook 可直接呼叫 MCP 工具；注入上限 10,000 字元；`SessionEnd` 預算僅 1.5 秒；`Stop` 連擋上限 8 次與記憶系統的「擋滿」計次機制並存。

### CLI 參考（`cli-reference`）
- 檔案：[cli-reference.md](cli-reference.md)｜https://code.claude.com/docs/zh-TW/cli-reference｜lastmod 2026-11-03｜50 KB
- 一句話：`claude` 指令與子指令、全部命令列旗標的對照表，加系統提示詞旗標說明。
- 何時讀：要寫啟動腳本、`claude -p` 自動化、背景工作階段管理，或查某旗標做什麼。
- 關鍵內容：
  1. 啟動與恢復：`claude`、`claude "query"`、`claude -p`（SDK 模式）、`claude -c`（續最近）、`claude -r "<session>"`、`--continue`／`--resume`／`--fork-session`／`--session-id`／`--name`。
  2. 子指令：`update` `install [version]` `auth login|logout|status` `doctor` `mcp`(含 `login`/`logout`) `plugin` `agents` `attach` `logs` `respawn` `rm` `stop` `daemon run|status|stop|logs` `auto-mode defaults|reset` `import` `purge` `remote-control` `self-hosted-runner` `setup-token` `ultrareview` `gateway`。
  3. 權限／工具旗標：`--permission-mode` `--allowedTools` `--disallowedTools` `--tools`(`""`／`default`／清單) `--dangerously-skip-permissions` `--allow-dangerously-skip-permissions` `--permission-prompt-tool` `--enable-auto-mode`。
  4. 設定與隔離旗標：`--settings`(檔案或內嵌 JSON，≤2 MiB) `--setting-sources user,project,local` `--bare`(跳過 hooks／skills／MCP／auto memory／CLAUDE.md 探索) `--safe-mode`(停用所有自訂供疑難排解) `--strict-mcp-config` `--mcp-config` `--plugin-dir` `--add-dir` `--worktree`／`-w`。
  5. 系統提示詞旗標：`--system-prompt` `--system-prompt-file` `--append-system-prompt` `--append-system-prompt-file` `--append-subagent-system-prompt(-file)` `--system-prompt-snapshot` `--exclude-dynamic-system-prompt-sections`。
  6. 非互動輸出：`--output-format`(text/json/stream-json) `--input-format` `--json-schema` `--include-hook-events` `--include-partial-messages` `--replay-user-messages` `--max-turns` `--max-budget-usd` `--no-session-persistence` `--fallback-model`。
  7. 背景／遠端：`--bg`／`--background`、`--exec`(shell 命令當背景工作)、`--remote`、`--remote-control`、`--teleport`、`--cloud`、`--environment`、`--tmux`、`--teammate-mode`。
  8. 其他：`--model` `--effort` `--agent` `--agents` `--channels` `--chrome`／`--no-chrome` `--ide` `--init`／`--init-only`／`--maintenance`(觸發 Setup hook) `--debug`／`--debug-file` `--verbose` `--betas` `--from-pr` `--version`。
- 新名詞：`print mode` ＝ `-p` 一次執行後退出；`agent 檢視` ＝ `claude agents` 監控多個背景工作階段；`監督程序 (supervisor)` ＝ 管理背景工作階段的 daemon；`ultrareview` ＝ 雲端多 agent 程式碼審查。
- 記憶系統接點：`--bare`／`--safe-mode`／`CLAUDE_CODE_SIMPLE` 會讓 hooks 與自動記憶全不載入；`--include-hook-events` 可在串流輸出看到 hook 生命週期；`--settings`／`--setting-sources` 影響 hook 來源；`--init`／`--maintenance` 觸發 Setup hook。

### Commands（`commands`）
- 檔案：[commands.md](commands.md)｜https://code.claude.com/docs/zh-TW/commands｜lastmod 2026-11-03｜55 KB
- 一句話：工作階段內所有內建 `/` 指令與內附 skill／workflow 的清單與說明。
- 何時讀：想知道某個斜線指令是否存在、做什麼、別名是什麼。
- 關鍵內容：
  1. 指令只在訊息開頭被辨識；Claude 回應中送出的指令會排隊，`/status` `/tasks` `/usage` 立即執行。
  2. 工作階段／上下文：`/clear` `/compact` `/context` `/resume` `/branch` `/fork` `/rewind`(別名 `/checkpoint`) `/rename` `/recap` `/export` `/copy` `/cd` `/add-dir` `/exit`(`/quit`) `/restart` `/focus` `/diff` `/btw` `/background` `/subtask` `/tasks` `/stop`。
  3. 設定／管理：`/config` `/model` `/effort`(原文提及) `/permissions` `/hooks` `/memory` `/mcp`(原文提及) `/agents` `/skills` `/plugin` `/reload-plugins` `/reload-skills` `/output-style` `/theme` `/keybindings` `/statusline` `/terminal-setup` `/sandbox` `/ide` `/privacy-settings` `/init` `/doctor` `/status` `/help` `/login` `/logout` `/upgrade`。
  4. 帳號用量：`/usage`(別名 `/cost` `/stats`) `/usage-credits` `/rate-limit-options` `/passes` `/insights` `/skill-doctor` `/heapdump` `/release-notes` `/feedback` `/bug`。
  5. 內附 skill：`/batch` `/code-review`(工作流段落提及) `/simplify` `/loop` `/debug` `/run` `/verify` `/fewer-permission-prompts` `/update-config` `/security-review` `/claude-in-chrome` `/dataviz` `/design` `/design-sync` `/slides` `/artifact-capabilities` `/artifact-diagramming` `/workflow-authoring` `/plugin-authoring` `/run-skill-generator` `/team-onboarding`。
  6. 工作流／雲端：`/deep-research` `/workflows` `/schedule` `/autofix-pr` `/ultrareview` `/teleport` `/desktop` `/remote-control` `/remote-env` `/web-setup` `/artifacts` `/design-login` `/auto-mode-setup`。
  7. 已移除或換名：`/pr-comments`(v2.1.91 移除) `/vim`(v2.1.92 移除，改 `/config` Editor mode) `/ultraplan`(移除，改 plan mode)；其他小工具 `/radio` `/stickers` `/mobile` `/powerup` `/install-github-app` `/install-slack-app` `/setup-bedrock` `/setup-vertex` `/list-agents` `/plan` `/scroll-speed`。
  8. MCP 伺服器的 prompts 也會以指令出現；選單有拼字比對，部分指令（如 `/heapdump`）刻意隱藏。
- 新名詞：`bundled skill` ＝ 隨 Claude Code 附帶、以提示詞為本的劇本型指令；`背景 agent` ＝ 用 `/background`／`/fork` 脫離終端機持續跑的工作階段。
- 記憶系統接點：`/hooks` 唯讀檢視 hook 設定；`/memory` 管 CLAUDE.md 與自動記憶；`/compact`、`/clear`、`/resume` 會分別觸發 PreCompact／SessionEnd／SessionStart(source 不同)；`/reload-skills` 可在工作階段內重掃 skill。

### 工具參考（`tools-reference`）
- 檔案：[tools-reference.md](tools-reference.md)｜https://code.claude.com/docs/zh-TW/tools-reference｜lastmod 2026-11-02｜87 KB
- 一句話：Claude 可呼叫的全部內建工具、各自是否需權限，與主要工具的行為與數字限制。
- 何時讀：寫 matcher／權限規則要知道工具名；查 Bash 逾時、輸出上限、Read 大檔行為。
- 關鍵內容：
  1. 工具名全表：`Agent` `Artifact` `AskUserQuestion` `Bash` `CronCreate` `CronDelete` `CronList` `Edit` `EndConversation` `EnterPlanMode` `EnterWorktree` `ExitPlanMode` `ExitWorktree` `Glob` `Grep` `ListAgents` `ListMcpResourcesTool` `LSP` `Monitor` `NotebookEdit` `PowerShell` `PushNotification` `Read` `ReadMcpResourceTool` `RemoteTrigger` `ReportFindings` `ScheduleWakeup` `SendFeedback` `SendMessage` `SendUserFile` `ShareOnboardingGuide` `Skill` `SubagentHandback` `TaskCreate` `TaskGet` `TaskList` `TaskOutput`(v2.1.277 移除) `TaskStop` `TaskUpdate` `TodoWrite` `ToolSearch` `WaitForMcpServers` `WebFetch` `WebSearch` `Workflow` `Write`。
  2. 需權限者（例）：`Bash` `Edit` `Write` `NotebookEdit` `PowerShell` `Skill` `WebFetch` `WebSearch` `Workflow` `ExitPlanMode`；唯讀如 `Read` `Glob` `Grep` `LSP` 不需。macOS／Linux／WSL 預設不含 `Glob`／`Grep`（改用 shell 搜尋）。
  3. Bash：預設逾時 2 分鐘（`BASH_DEFAULT_TIMEOUT_MS`）、上限 10 分鐘（`BASH_MAX_TIMEOUT_MS`）；有效輸出內聯約 30,000 字元，超過存檔給路徑＋2,000 字預覽；失敗輸出約 10,000 字元；輸出 >5 GB 終止；`BASH_MAX_OUTPUT_LENGTH` 硬上限 150,000。
  4. 背景命令時限：無人看管工作階段（-p、SDK、CI、雲端）預設 30 分鐘、最多 2 小時（-p 文字提示預設 10 分鐘）；cd 與環境在命令間保留。
  5. Read：單次最多 25,000 token（`CLAUDE_CODE_FILE_READ_MAX_OUTPUT_TOKENS`）、全檔 >256 KB 要用 offset／limit；PDF >10 頁需 `pages`、一次最多 20 頁；圖片 >128 MB 拒讀；二進位副檔名（`.xlsx` `.zip` 等）拒讀。
  6. Task 追蹤工具（`TaskCreate` 等）預設只在 Opus 4.7／Sonnet 4.6／Haiku 4.5 及更早模型出現；`CLAUDE_CODE_ENABLE_TODO_TOOLS=1` 或 `--allowedTools` 可選用。
  7. `PreToolUse`／`PostToolUse` 等 matcher 以此處工具名為準；MCP 工具名格式 `mcp__<server>__<tool>`；Bash 拒絕規則也會關閉 `PowerShell`。
  8. 其他專章：Monitor（背景命令每行回饋、WebSocket 來源）、EndConversation、SendFeedback、LSP、WebFetch／WebSearch 限制、檢查可用工具的方法。
- 新名詞：`Monitor` ＝ 背景跑命令並把每行輸出餵回 Claude；`ToolSearch` ＝ 延遲載入 MCP 工具定義的搜尋工具；`ScheduleWakeup` ＝ 自調節 /loop 的下次喚醒；`SubagentHandback` ＝ 子代理交付最終報告的工具；`ReportFindings` ＝ 以結構化清單回報審查發現。
- 記憶系統接點：hook `matcher` 與 `if` 用這裡的工具名；`ToolSearch` 說明延遲工具的載入方式；Bash／hook 輸出大小上限與 hook `additionalContext` 的 10,000 字元上限同源概念；`Skill`、`Agent` 工具是 skills／子代理呼叫入口。

### 環境變數（`env-vars`）
- 檔案：[env-vars.md](env-vars.md)｜https://code.claude.com/docs/zh-TW/env-vars｜lastmod 2026-11-04｜183 KB
- 一句話：控制 Claude Code 行為的 400 多個環境變數對照表。
- 何時讀：要用環境變數開關功能、調逾時、設代理、停用某機制。
- 關鍵內容：
  1. 設定方式：shell export，或 settings.json 的 `env` 區塊（可設但不能移除，用空字串覆寫）；設定檔值會取代 shell 值；受管設定優先；專案／本機設定不可設部分變數（如 `CLAUDE_CONFIG_DIR`）。
  2. 路徑：`CLAUDE_CONFIG_DIR`(預設 `~/.claude`)、`CLAUDE_CODE_PROJECT_DIR_NAME`、`CLAUDE_ENV_FILE`(每個 Bash 命令前 source)、`CLAUDE_CODE_PLUGIN_DIRS`／`PLUGIN_CACHE_DIR`、`CLAUDE_CODE_TASK_LIST_ID`。
  3. 精簡／停用類：`CLAUDE_CODE_SIMPLE`(最小提示詞，停用 hook／skill／MCP／自動記憶)、`CLAUDE_CODE_DISABLE_AUTO_MEMORY`、`CLAUDE_CODE_DISABLE_CLAUDE_MDS`、`CLAUDE_CODE_DISABLE_BUNDLED_SKILLS`、`CLAUDE_CODE_DISABLE_FILE_CHECKPOINTING`、`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS`、`DISABLE_COMPACT`／`DISABLE_AUTO_COMPACT`。
  4. 壓縮與上下文：`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`(只能降低閾值)、`CLAUDE_CODE_AUTO_COMPACT_WINDOW`、`CLAUDE_CODE_MAX_CONTEXT_TOKENS`、`CLAUDE_CODE_IDLE_COMPACT_MIN_TOKENS`、`CLAUDE_CODE_DISABLE_1M_CONTEXT`。
  5. Hook 相關：`CLAUDE_CODE_SESSIONEND_HOOKS_TIMEOUT_MS`、`CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`、`CLAUDE_CODE_DISABLE_PERMISSION_PROMPT_NOTIFY_HOOKS`、`CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1`(hook／Bash／stdio MCP 子程序移除憑證)。
  6. MCP：`MCP_TIMEOUT` `MCP_TOOL_TIMEOUT` `MAX_MCP_OUTPUT_TOKENS` `MCP_CONNECT_TIMEOUT_MS` `MCP_DISCOVERY_CACHE*` `CLAUDE_CODE_MCP_STARTUP_WAIT_MS` `ENABLE_CLAUDEAI_MCP_SERVERS`。
  7. 子代理與任務：`CLAUDE_CODE_SUBAGENT_MODEL` `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` `CLAUDE_CODE_FORK_SUBAGENT` `CLAUDE_CODE_ENABLE_TASKS`／`TODO_TOOLS`。
  8. 模型與 API：`ANTHROPIC_API_KEY` `ANTHROPIC_BASE_URL` `ANTHROPIC_MODEL`(旗標／`/model` 可覆寫)、`API_TIMEOUT_MS`、`CLAUDE_CODE_EFFORT_LEVEL`(覆寫 `--effort`)、Bedrock／Vertex 系列；Bash 逾時 `BASH_DEFAULT_TIMEOUT_MS`／`BASH_MAX_TIMEOUT_MS`／`BASH_MAX_OUTPUT_LENGTH`。
- 新名詞：`env 區塊` ＝ settings.json 裡替每個工作階段設環境變數的欄位；`子程序環境清除 (SUBPROCESS_ENV_SCRUB)` ＝ 啟動子程序時自動剝除憑證類變數。
- 記憶系統接點：`CLAUDE_CODE_DISABLE_AUTO_MEMORY`／`CLAUDE_CODE_DISABLE_CLAUDE_MDS`／`CLAUDE_CODE_SIMPLE` 影響原生記憶載入；`CLAUDE_CONFIG_DIR` 改變 `~/.claude` 位置（hook 路徑、記憶根）；`CLAUDE_ENV_FILE` 是 SessionStart hook 傳環境給 Bash 的通道；`SUBPROCESS_ENV_SCRUB` 會影響 hook 子程序拿得到的變數。

### 互動模式（`interactive-mode`）
- 檔案：[interactive-mode.md](interactive-mode.md)｜https://code.claude.com/docs/zh-TW/interactive-mode｜lastmod 2026-11-03｜77 KB
- 一句話：互動工作階段的快捷鍵、輸入前綴、Vim 模式與一堆小功能的使用說明。
- 何時讀：查快捷鍵、排隊訊息、背景 Bash、`!` shell 模式、`/btw`、工作清單等操作。
- 關鍵內容：
  1. 一般快捷鍵：`Ctrl+C` 中斷／清除、`Ctrl+D` 退出、`Ctrl+O` 文字記錄檢視器、`Ctrl+R` 反向搜歷史、`Ctrl+B` 背景執行、`Ctrl+T` 工作清單、`Ctrl+G` 開外部編輯器、`Esc`／`Esc Esc` 中斷／回溯、`Shift+Tab` 循環權限模式。
  2. 切換：`Option+P`／`Alt+P` 換模型、`Alt+T` 延伸思考、`Alt+O` 快速模式、`Ctrl+X Ctrl+K` 停所有背景 subagent。
  3. 輸入前綴：`/` 指令或 skill、`!` shell 模式、`@` 檔案提及、`:` emoji 代碼、`?` 快捷鍵說明。
  4. 排隊訊息：Claude 工作時按 `Enter` 會排隊，`Ctrl+Enter` 立即送出。
  5. Vim 編輯器模式：NORMAL／INSERT／視覺模式、文字物件、重新對應 INSERT 序列。
  6. 其他功能：提示建議、You should know 建議、拼寫檢查、`/diff` 檢視器、`/btw` 側問、工作階段摘要（離開 ≥3 分鐘回來顯示）、等待用量上限重設後自動繼續、PR 審查狀態。
  7. 工作清單跨壓縮保留；`CLAUDE_CODE_TASK_LIST_ID` 可跨工作階段共用。
- 新名詞：`transcript viewer` ＝ `Ctrl+O` 開的詳細工具輸出檢視；`queued message` ＝ 回應中先排隊稍後送的訊息；`shell mode` ＝ 以 `!` 開頭直接執行命令。
- 記憶系統接點：`Ctrl+O` 可看到被抑制的 async hook 完成通知；`/btw` 側問不進對話；排隊訊息的送達時機會影響 UserPromptSubmit 觸發點。

### Channels 參考（`channels-reference`）
- 檔案：[channels-reference.md](channels-reference.md)｜https://code.claude.com/docs/zh-TW/channels-reference｜lastmod 2026-10-28｜44 KB
- 一句話：寫一個 MCP 伺服器，把 webhook、警報、聊天訊息推進執行中的 Claude Code 工作階段的合約。
- 何時讀：要自製 channel 外掛（Telegram／Discord 橋接、CI 告警接收器）或做遠端權限批准。
- 關鍵內容：
  1. channel＝本機子程序 MCP 伺服器，stdio 通訊；單向（只推事件）或雙向（另公開回覆工具）。
  2. 宣告能力：`capabilities.experimental['claude/channel']: {}`（必要）；`claude/channel/permission` 選填，表示可接收權限中繼；`instructions` 建議填，告訴 Claude 如何處理事件。
  3. 推事件：`mcp.notification({method:'notifications/claude/channel', params:{content, meta}})`；`meta` 的鍵變成 `<channel>` 標籤屬性。
  4. 權限中繼：Claude Code 發 `notifications/claude/channel/permission_request`（含短要求 ID），遠端回覆後伺服器回 permission 通知；本機對話框同時開著，先答者勝；不含專案信任與 MCP 同意。
  5. 入站訊息要做寄件者閘道（allowlist）以防提示注入。
  6. 研究預覽；Team／Enterprise 須明確啟用；CLI 旗標 `--channels`；可打包為外掛。
- 新名詞：`channel` ＝ 把外部事件推進工作階段的 MCP 伺服器；`permission relay` ＝ 把批准提示轉發到手機／聊天；`sender gating` ＝ 只接受白名單寄件者的訊息。
- 記憶系統接點：channel 事件以 `<channel>` 標籤進上下文，與 hook 注入的 `additionalContext` 並列的另一條外部內容入口；`instructions` 欄位在連線時進 Claude 上下文。

### Checkpointing（`checkpointing`）
- 檔案：[checkpointing.md](checkpointing.md)｜https://code.claude.com/docs/zh-TW/checkpointing｜lastmod 2026-10-28｜9 KB
- 一句話：每個提示詞自動存檔案快照，可用 `/rewind` 回復程式碼、對話或做摘要壓縮。
- 何時讀：想撤銷 Claude 的編輯、回到先前對話點，或用「從這裡摘要」釋放上下文。
- 關鍵內容：
  1. 每個開啟新回合的提示詞建立一個檢查點；每工作階段保留最近 100 個；快照約 30 天後清理。
  2. 開啟：`/rewind`（別名 `/checkpoint`）或提示框為空時按 `Esc Esc`。
  3. 選項：Restore code and conversation／Restore conversation／Restore code／Summarize from here／Summarize up to here／Never mind。
  4. 限制：Bash 命令造成的變更、subagent 的編輯、外部變更、回合中途送的訊息、符號連結不會被追蹤或還原；不能取代版本控制。
  5. 停用：`CLAUDE_CODE_DISABLE_FILE_CHECKPOINTING`。
- 新名詞：`checkpoint` ＝ 每回合開始前的檔案還原點。
- 記憶系統接點：「Summarize from here」是另一條壓縮路徑；Bash 改動不被追蹤，與 hook 執行的檔案寫入同理不可回復。

## Glossary

### 詞彙表（`glossary`）
- 檔案：[glossary.md](glossary.md)｜https://code.claude.com/docs/zh-TW/glossary｜lastmod 2026-10-30｜29 KB
- 一句話：Claude Code 專有名詞的官方定義表，含已改名舊詞對照。
- 何時讀：碰到不熟的術語（compaction、harness、channel、dispatch…）時。
- 關鍵內容：
  1. 約 55 個詞條，A–Z 排序，各附連結互相參照。
  2. 結尾「已棄用和重新命名的術語」表：Headless mode→Non-interactive mode；Web session→Cloud session；Custom commands→Skills；Slash commands→Commands。
  3. 設定層級由高到低：受管政策→`--settings`→`.claude/settings.local.json`→`.claude/settings.json`→`~/.claude/settings.json`。
  4. 權限規則評估順序：deny→ask→allow，先符合者勝。
  5. CLAUDE.md 於每個工作階段開始時作為系統提示後的使用者訊息載入。
- 新名詞（全列）：
  - `AGENTS.md` ＝ 給 AI 編碼代理的專案指示檔；沒有 CLAUDE.md 時 Claude 會讀它
  - `Agent teams` ＝ 多個獨立 Claude 工作階段協作，有共享任務清單與互傳訊息
  - `Agentic coding` ＝ AI 自主讀檔、跑命令、改程式，你只需看著或離開
  - `Agentic harness` ＝ 把語言模型變成編碼代理的工具＋上下文管理＋執行環境；Claude Code 是 harness
  - `Agentic loop` ＝ 蒐集上下文→行動→驗證→重複直到完成的循環
  - `Artifact` ＝ 發佈到 claude.ai 私人網址的互動網頁
  - `Auto memory` ＝ Claude 依你的更正與偏好自己寫的筆記，存 `~/.claude/projects/`
  - `Auto mode` ＝ 由分類器模型代替你審核動作的權限模式
  - `Bare mode` ＝ `--bare`，不載入 hooks／skills／MCP／記憶等的最簡啟動
  - `Bundled skills` ＝ 隨附的提示型劇本，如 `/batch` `/debug` `/loop`
  - `Channel` ＝ 把事件推進執行中工作階段的 MCP 伺服器
  - `Checkpoint` ＝ 每個提示詞前建立的還原點
  - `.claude 目錄` ＝ 放設定、hooks、skills、subagents、rules、自動記憶的資料夾
  - `CLAUDE.md` ＝ 你寫給 Claude 的持久指示 markdown
  - `Cloud session` ＝ 跑在雲端基礎設施、關機後仍繼續的工作階段
  - `Command` ＝ 輸入 `/name` 叫用的可重用指示
  - `Compaction` ＝ 上下文快滿時自動摘要對話
  - `Connector` ＝ 加在 claude.ai 帳戶而非 Claude Code 本機的 MCP 伺服器
  - `Context window` ＝ 工作階段的工作記憶（對話、檔案、輸出、CLAUDE.md、skills…）
  - `Dispatch` ＝ 從手機 App 派編碼任務，在 Desktop 開工作階段的路由器
  - `Effort level` ＝ 控制自適應推理深淺的設定
  - `Extended thinking` ＝ 回應前的可見逐步推理
  - `Frontmatter` ＝ Markdown 檔頂端 `---` 夾住的 YAML 設定區
  - `Hook` ＝ 在生命週期特定點自動執行的使用者定義處理程式
  - `Managed settings` ＝ IT 管理員強制套用的組織級設定
  - `MCP (Model Context Protocol)` ＝ 連接 AI 與外部資料／服務的開放標準
  - `MCP server` ＝ 透過 MCP 提供工具、提示或資源的程式
  - `MCP Tool Search` ＝ 把 MCP 工具定義延遲到需要才載入的省 context 機制
  - `Non-interactive mode` ＝ `-p` 單次執行後退出（舊稱 headless）
  - `Output style` ＝ 改變 Claude 回應語氣／格式的設定
  - `Permission mode` ＝ 工作階段的基線批准行為（default／acceptEdits／plan／auto／dontAsk／bypassPermissions）
  - `Permission rule` ＝ 依工具名與參數允許／詢問／拒絕的設定條目
  - `Plan mode` ＝ 只研究、提議、不改檔的權限模式
  - `Plugin` ＝ skills＋hooks＋subagents＋MCP 的可安裝套件
  - `Project trust` ＝ 載入專案設定前的信任對話框
  - `Prompt injection` ＝ 藏在檔案／網頁裡想劫持 Claude 的敵對指令
  - `Remote Control` ＝ 從手機或瀏覽器遙控本機工作階段
  - `Rules` ＝ `.claude/rules/` 的模組化指示，可用 `paths:` 限定路徑
  - `沙箱機制 (Sandbox)` ＝ Bash 的 OS 層級檔案系統與網路隔離
  - `工作階段 (Session)` ＝ 綁定目前目錄、有獨立上下文的對話
  - `設定層級` ＝ 設定來源的優先順序階層
  - `Skill` ＝ 含指令／知識／流程的 `SKILL.md`
  - `Subagent` ＝ 獨立上下文、獨立權限的專門助理
  - `使用介面 (Surface)` ＝ CLI、VS Code、JetBrains、Desktop、claude.ai 等入口
  - `系統提示詞` ＝ 每次請求在對話前送出的指令
  - `系統提醒 (system reminder)` ＝ harness 塞進對話的訊息，用來給 Claude 上下文
  - `Teleport` ＝ `/teleport` 把雲端工作階段拉回本機終端
  - `Tool` ＝ Claude 能採取的動作（讀檔、跑命令、搜網路…）
  - `Transcript` ＝ 工作階段的儲存紀錄檔，預設 `~/.claude/projects/<project>/`
  - `Turn` ＝ 從你送訊息到 Claude 完成回應的一整輪
  - `Verification loop` ＝ 給 Claude 可執行的檢查（測試、建置）以確認完成
  - `Worktree isolation` ＝ 在 `.claude/worktrees/` 的獨立 git worktree 中執行
- 記憶系統接點：「系統提醒」就是 hook `additionalContext` 的包裝形式；Auto memory／CLAUDE.md／Rules／Transcript 的定義與位置，是區分原生記憶與原子記憶的依據。

## Resources

### 法律和合規（`legal-and-compliance`）
- 檔案：[legal-and-compliance.md](legal-and-compliance.md)｜https://code.claude.com/docs/zh-TW/legal-and-compliance｜lastmod 2026-10-30｜6 KB
- 一句話：使用條款、商業協議、醫療合規（BAA）、使用政策與安全回報管道。
- 何時讀：要把 Claude Code 放進自家產品、或問合規／認證用法時。
- 關鍵內容：
  1. Team／Enterprise／API 適用商業條款；Free／Pro／Max／Ultra 適用消費者服務條款。
  2. 預裝或內嵌 Claude Code 於產品需另行同意：不得修改二進位、不得代使用者付費轉售。
  3. 名稱與標誌只能純文字準確描述，不可當自家品牌使用。
  4. 含醫療保健合規（BAA）、可接受使用、驗證與憑證使用規範、安全漏洞報告。
- 新名詞：`BAA` ＝ 醫療資料用的業務夥伴協議。
- 記憶系統接點：無

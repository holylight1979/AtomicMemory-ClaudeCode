<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/tools-reference | lastmod: 2026-11-02 | section: Reference / Reference -->
> 來源：https://code.claude.com/docs/zh-TW/tools-reference（官方 zh-TW，lastmod 2026-11-02）｜分類：Reference › Reference｜EN 摘要：Complete reference for the tools Claude Code can use, including permission requirements and per-tool behavior.

# 工具參考

> Claude Code 可以使用的工具完整參考，包括權限要求和各工具行為。

Claude Code 可以存取一組內建工具，幫助它理解和修改您的程式碼庫。工具名稱是您在[權限規則](https://code.claude.com/docs/zh-TW/permissions.md#tool-specific-permission-rules)、[subagent 工具清單](https://code.claude.com/docs/zh-TW/sub-agents.md)和 [hook matcher](https://code.claude.com/docs/zh-TW/hooks.md) 中使用的確切字串。

若要控制 Claude 可以使用哪些工具以及何時要求先詢問，請在您的設定、[hook](https://code.claude.com/docs/zh-TW/hooks.md) 或 [subagent 的工具清單](https://code.claude.com/docs/zh-TW/sub-agents.md#supported-frontmatter-fields)中設定[權限規則](https://code.claude.com/docs/zh-TW/permissions.md#tool-specific-permission-rules)。請參閱[使用權限規則和 hook 設定工具](#configure-tools-with-permission-rules-and-hooks)以了解接受工具名稱的各個位置。

若要新增自訂工具，請連接 [MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md)。若要使用可重複使用的提示詞型工作流程擴展 Claude，請撰寫 [skill](https://code.claude.com/docs/zh-TW/skills.md)，它透過現有的 `Skill` 工具執行，而不是新增工具項目。

> [!NOTE]
>
> 在[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)中，分類器決定大多數權限提示，而不是您。「需要權限」欄顯示工具是否在[手動模式](https://code.claude.com/docs/zh-TW/permission-modes.md)中針對工作目錄內的路徑提示。標記為「否」的檔案存取工具，包括 `Read`、`Grep` 和 `Glob`，仍會針對[工作目錄和其他目錄](https://code.claude.com/docs/zh-TW/permissions.md#working-directories)外的路徑提示。`Bash` 標記為「是」，但執行內建的[唯讀命令](https://code.claude.com/docs/zh-TW/permissions.md#read-only-commands)而不提示。

| 工具 | 說明 | 需要權限 |
| :- | :- | :- |
| `Agent` | 生成一個 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md)，具有自己的上下文視窗來處理任務。啟用 [agent team](https://code.claude.com/docs/zh-TW/agent-teams.md) 後，帶有 `name` 的呼叫可以改為啟動[隊友](https://code.claude.com/docs/zh-TW/agent-teams.md#how-claude-starts-agent-teams)。請參閱 [Agent 工具行為](#agent-tool-behavior) | 否 |
| `Artifact` | 將 HTML 或 Markdown 檔案發佈到 claude.ai 成為 [artifact](https://code.claude.com/docs/zh-TW/artifacts.md)：一個私人的互動頁面。您可以透過公開連結分享，或在 Team 和 Enterprise 方案上於您的組織內分享，其中公開分享需要擁有者[啟用它](https://code.claude.com/docs/zh-TW/artifacts.md#control-public-sharing)。需要 Pro、Max、Ultra、Team 或 Enterprise 方案以及 `/login` 身分驗證；請參閱[可用性](https://code.claude.com/docs/zh-TW/artifacts.md#availability) | 是 |
| `AskUserQuestion` | 詢問多選題以收集需求或澄清歧義。預設情況下，問題保持開放直到您回答。請參閱 [AskUserQuestion 工具行為](#askuserquestion-tool-behavior) | 否 |
| `Bash` | 在您的環境中執行 shell 命令。請參閱 [Bash 工具行為](#bash-tool-behavior) | 是 |
| `CronCreate` | 在目前工作階段內排程重複或一次性提示詞。任務的範圍限於工作階段，如果未過期，在 `--resume` 或 `--continue` 時會復原。請參閱[工作階段範圍的排程任務](https://code.claude.com/docs/zh-TW/scheduled-tasks.md) | 否 |
| `CronDelete` | 按 ID 取消工作階段範圍的排程任務 | 否 |
| `CronList` | 列出所有工作階段範圍的排程任務 | 否 |
| `Edit` | 對特定檔案進行目標編輯。請參閱 [Edit 工具行為](#edit-tool-behavior) | 是 |
| `EndConversation` | 結束工作階段，在持續濫用輸入的罕見情況下或當您要求 Claude 演示該工具時。請參閱 [EndConversation 工具行為](#endconversation-tool-behavior) | 否 |
| `EnterPlanMode` | 切換到 plan mode 以在編碼前設計方法 | 否 |
| `EnterWorktree` | 建立隔離的 [git worktree](https://code.claude.com/docs/zh-TW/worktrees.md) 並切換到其中，或切換到現有的 worktree。請參閱 [EnterWorktree 工具行為](#enterworktree-tool-behavior) | 是 |
| `ExitPlanMode` | 呈現計畫以供核准並退出 plan mode | 是 |
| `ExitWorktree` | 退出 worktree 工作階段並返回原始目錄。不適用於已在自己的工作目錄中執行的 subagent，例如 [`isolation: worktree`](https://code.claude.com/docs/zh-TW/sub-agents#supported-frontmatter-fields)。一旦 [`permissions.blockWritesOutsideWorkingDirectories`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-blockwritesoutsideworkingdirectories) 開啟，便會被移除或拒絕 | 否 |
| `Glob` | 根據模式匹配尋找檔案。預設情況下在 macOS、Linux 和 WSL 上不存在。請參閱 [Glob 工具行為](#glob-tool-behavior) | 否 |
| `Grep` | 在檔案內容中搜尋模式。預設情況下在 macOS、Linux 和 WSL 上不存在。請參閱 [Grep 工具行為](#grep-tool-behavior) | 否 |
| `ListAgents` | 列出 Claude 可以使用 `SendMessage` 傳訊的 agent：工作階段中的 subagent、[agent team](https://code.claude.com/docs/zh-TW/agent-teams.md) 隊友、您的其他本機 Claude Code 工作階段，以及當此工作階段連接到 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 時，您的[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)和您在其他機器上的 Remote Control 工作階段。支援 `/list-agents` 命令。請參閱[跨工作階段傳訊](https://code.claude.com/docs/zh-TW/cross-session-messaging.md)。需要 Claude Code v2.1.224 或更新版本，且僅在[啟用跨工作階段傳訊](https://code.claude.com/docs/zh-TW/cross-session-messaging.md#availability)的工作階段中出現。隊友列和顯示此工作階段自己名稱的第一行需要 v2.1.239 或更新版本 | 否 |
| `ListMcpResourcesTool` | 列出連接的 [MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md)公開的資源，不包括 [MCP Apps UI 資源](https://code.claude.com/docs/zh-TW/mcp.md#reference-mcp-resources)，這些是供主機應用程式呈現的頁面 | 否 |
| `LSP` | 透過語言伺服器的程式碼智慧：跳到定義、尋找參考、報告型別錯誤和警告。請參閱 [LSP 工具行為](#lsp-tool-behavior) | 否 |
| `Monitor` | 在背景執行命令並將每個輸出行回饋給 Claude，以便它可以在對話中途對日誌項目、檔案變更或輪詢狀態做出反應。也可以開啟 WebSocket 並將每個傳入訊息視為事件。請參閱 [Monitor 工具](#monitor-tool) | 是 |
| `NotebookEdit` | 修改 Jupyter notebook 儲存格。請參閱 [NotebookEdit 工具行為](#notebookedit-tool-behavior) | 是 |
| `PowerShell` | 原生執行 PowerShell 命令。請參閱 [PowerShell 工具](#powershell-tool)以了解可用性 | 是 |
| `PushNotification` | 傳送桌面通知，以及當 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 連接時的手機推播，以便長時間執行的任務或[工作階段範圍的排程任務](https://code.claude.com/docs/zh-TW/scheduled-tasks.md)可以在您離開時聯繫您。推播傳遞透過 Anthropic 託管的基礎設施執行，無法從 Amazon Bedrock、Claude Platform on AWS、Google Cloud 的 Agent Platform 或 Microsoft Foundry 存取 | 否 |
| `Read` | 讀取檔案的內容。請參閱 [Read 工具行為](#read-tool-behavior) | 否 |
| `ReadMcpResourceTool` | 按 URI 讀取特定 MCP 資源 | 否 |
| `RemoteTrigger` | 在 claude.ai 上建立、更新、執行和列出[雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md)（前身為 routine）。支援 `/schedule` 命令。[`RemoteTrigger` 輸入參考](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#remotetrigger)記錄每個動作和移除工具的組織政策。雲端排程任務位於 claude.ai 上並需要 Pro、Max、Ultra、Team 或 Enterprise 方案，因此此工具無法從 Amazon Bedrock、Claude Platform on AWS、Google Cloud 的 Agent Platform 或 Microsoft Foundry 存取 | 否 |
| `ReportFindings` | 將程式碼審查發現報告為結構化清單，每個發現都有檔案、摘要和失敗情景，以便 Claude Code 可以呈現它們而不是將其列印為文字。當有效的程式碼審查指示要求時，Claude 會呼叫它。發現也可以帶有選用的 `category` slug，例如 `correctness` 或 `test-coverage`，顯示在呈現清單中的檔案位置旁邊 | 否 |
| `ScheduleWakeup` | 重新排程[自我調整 `/loop`](https://code.claude.com/docs/zh-TW/scheduled-tasks#let-claude-choose-the-interval) 的下一次迭代。Claude 在每次迭代結束時呼叫此工具以選擇下一次執行的時間，介於一分鐘到一小時之間；您不直接呼叫它。若要改為結束迴圈，Claude 使用 `stop: true` 呼叫它，這會取消待處理的喚醒。待處理的喚醒出現在 [Stop hook 輸入](https://code.claude.com/docs/zh-TW/hooks.md#stop-input)中的 `session_crons` 中 | 否 |
| `SendFeedback` | 起草關於 Claude Code 的回饋報告，涵蓋產品問題或 Claude 在工作階段中的自身行為，並在您的機器上排隊供您審查。Claude Code 在您選擇傳送草稿之前不會傳送任何內容。請參閱 [SendFeedback 工具行為](#sendfeedback-tool-behavior)。需要 Claude Code v2.1.238 或更新版本 | 否 |
| `SendMessage` | 傳送訊息給另一個 agent：[agent team](https://code.claude.com/docs/zh-TW/agent-teams.md) 隊友、[它按 agent ID 或名稱恢復的 subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#resume-subagents)，或 您的其他 Claude Code 工作階段之一，在此機器上或超越它。傳訊其他工作階段需要 Claude Code v2.1.224 或更新版本。[跨工作階段傳訊](https://code.claude.com/docs/zh-TW/cross-session-messaging.md)涵蓋 Claude 可以到達的工作階段、[訊息到達時的樣子](https://code.claude.com/docs/zh-TW/cross-session-messaging.md#what-a-message-looks-like)以及 [Claude 如何在另一個工作階段閒置時收到通知](https://code.claude.com/docs/zh-TW/cross-session-messaging.md#get-a-notice-when-another-session-goes-idle)。Claude 可以包含可選的 `summary` 輸入，通常 5-10 個字，Claude Code 顯示為單行預覽。當 Claude 在[純文字訊息](https://code.claude.com/docs/zh-TW/cross-session-messaging.md#limitations)上省略它時，Claude Code 使用訊息的第一行作為摘要。Claude Code 使用省略號截斷超過 200 個字元的摘要 | 否 |
| `SendUserFile` | 從工作階段傳送檔案給您，帶有選用的說明文字，以便生成的報告、圖表、螢幕擷取畫面或建置產物到達您的裝置，而不是僅在逐字稿中提及。選用的 `display` 輸入控制呈現方式：`render` 在用戶端中內嵌開啟檔案，`attach` 僅顯示下載卡，未設定時由用戶端根據檔案型別決定。當 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 用戶端連接或在[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)中時可用。傳遞透過 Anthropic 託管的基礎設施執行，因此該工具在 Amazon Bedrock、Google Cloud 的 Agent Platform 或 Microsoft Foundry 上不可用 | 否 |
| `ShareOnboardingGuide` | 上傳 `ONBOARDING.md` 並返回隊友可以在 Claude Code 中開啟的分享連結。在指南寫入後從 `/team-onboarding` 呼叫。適用於 Team 和 Enterprise 方案上的 claude.ai 訂閱者 | 是 |
| `Skill` | 在主對話中執行 [skill](https://code.claude.com/docs/zh-TW/skills.md#control-who-invokes-a-skill) | 是 |
| `SubagentHandback` | 將 subagent 的最終報告傳遞給接收該 subagent 結果的任何對話。僅在[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)中提供，給 Agent 工具在本機執行的 subagent，除了[分支](https://code.claude.com/docs/zh-TW/sub-agents.md#fork-the-current-conversation)，並在終端機 CLI、IDE 擴充功能、雲端工作階段和 Agent SDK 中可用；分類器在傳遞報告前審查它。需要 Claude Code v2.1.271 或更新版本 | 否 |
| `TaskCreate` | 在任務清單中建立新任務。預設情況下僅在[任務工具可用性](#task-tool-availability)下列出的模型上提供，在其他模型上當您選擇加入時提供 | 否 |
| `TaskGet` | 檢索特定任務的完整詳細資訊。預設情況下僅在[任務工具可用性](#task-tool-availability)下列出的模型上提供，在其他模型上當您選擇加入時提供 | 否 |
| `TaskList` | 列出所有任務及其目前狀態。預設情況下僅在[任務工具可用性](#task-tool-availability)下列出的模型上提供，在其他模型上當您選擇加入時提供 | 否 |
| `TaskOutput` | 已在 v2.1.277 中移除。先前用於檢索背景任務的輸出；Claude 現在改用 `Read` 讀取背景任務的[輸出檔案](https://code.claude.com/docs/zh-TW/interactive-mode.md#how-backgrounding-works) | 否 |
| `TaskStop` | 按 ID 停止執行中的背景任務。它也接受 [agent team 隊友](https://code.claude.com/docs/zh-TW/agent-teams.md)或按 agent ID 或名稱指定的具名背景 agent。當沒有任務符合 ID 時，錯誤會列出執行中的背景 agent（按 ID 和說明），包括另一個 agent 生成的 agent | 否 |
| `TaskUpdate` | 更新任務狀態、相依性、詳細資訊或刪除任務。預設情況下僅在[任務工具可用性](#task-tool-availability)下列出的模型上提供，在其他模型上當您選擇加入時提供 | 否 |
| `TodoWrite` | 管理工作階段任務檢查清單。預設情況下停用，改為使用 `TaskCreate`、`TaskGet`、`TaskList` 和 `TaskUpdate`。設定 `CLAUDE_CODE_ENABLE_TASKS=0` 以在[具有任務追蹤工具的工作階段](#task-tool-availability)中重新啟用它 | 否 |
| `ToolSearch` | 當[工具搜尋](https://code.claude.com/docs/zh-TW/mcp.md#scale-with-mcp-tool-search)啟用時，搜尋並載入延遲工具 | 否 |
| `WaitForMcpServers` | 等待一個或多個仍在背景連接的 [MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md)，以便請求可以使用它們的工具而無需重新啟動工作階段。當需要的伺服器尚未連接時，Claude 會呼叫它。僅在[工具搜尋](https://code.claude.com/docs/zh-TW/mcp.md#scale-with-mcp-tool-search)停用時出現，因為啟用時 `ToolSearch` 處理等待 | 否 |
| `WebFetch` | 從指定的 URL 擷取內容。請參閱 [WebFetch 工具行為](#webfetch-tool-behavior) | 是 |
| `WebSearch` | 執行網路搜尋。請參閱 [WebSearch 工具行為](#websearch-tool-behavior) | 是 |
| `Workflow` | 執行[動態工作流程](https://code.claude.com/docs/zh-TW/workflows.md)：一個在背景協調許多 subagent 並返回一個統一結果的指令碼 | 是 |
| `Write` | 建立或覆寫檔案。請參閱 [Write 工具行為](#write-tool-behavior) | 是 |

## 使用權限規則和 hooks 設定工具

在大多數情況下，Claude 會決定何時使用這些工具，您在與 Claude 互動時不需要自己命名它們。您在定義權限和其他設定時直接參考工具名稱：

* 在設定中的 [`permissions.allow`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-allow) 和 [`permissions.deny`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-deny)，以及 `/permissions` 介面
* 在 `--allowedTools` 和 `--disallowedTools` [CLI 旗標](https://code.claude.com/docs/zh-TW/cli-reference.md)
* 在 Agent SDK 的 [`allowedTools` 和 `disallowedTools`](https://code.claude.com/docs/zh-TW/agent-sdk/permissions#allow-and-deny-rules) 選項
* 在 [skill 的 `allowed-tools`](https://code.claude.com/docs/zh-TW/skills#frontmatter-reference) frontmatter
* 在 hook 的 [`if` 條件](https://code.claude.com/docs/zh-TW/hooks-guide#filter-by-tool-name-and-arguments-with-the-if-field)

所有這些都接受相同的規則格式 `ToolName(specifier)`。specifier 取決於工具，多個工具共享一種格式：

| 規則格式 | 適用於 | 詳細資訊 |
| :- | :- | :- |
| `Bash(npm run *)` | Bash、Monitor | [命令模式匹配](https://code.claude.com/docs/zh-TW/permissions.md#bash) |
| `PowerShell(Get-ChildItem *)` | PowerShell | [命令模式匹配](https://code.claude.com/docs/zh-TW/permissions.md#powershell) |
| `Read(~/secrets/**)` | Read、Grep、Glob、LSP | [路徑模式匹配](https://code.claude.com/docs/zh-TW/permissions.md#read-and-edit) |
| `Edit(/src/**)` | Edit、Write、NotebookEdit | [路徑模式匹配](https://code.claude.com/docs/zh-TW/permissions.md#read-and-edit) |
| `Skill(deploy *)` | Skill | [Skill 名稱匹配](https://code.claude.com/docs/zh-TW/skills.md#restrict-claude%E2%80%99s-skill-access) |
| `Agent(Explore)` | Agent | [Subagent 類型匹配](https://code.claude.com/docs/zh-TW/permissions.md#agent-subagents) |
| `WebFetch(domain:example.com)` | WebFetch | [網域匹配](https://code.claude.com/docs/zh-TW/permissions.md#webfetch) |
| `WebSearch` | WebSearch | 無 specifier；允許或拒絕整個工具 |

此處未列出的工具，例如 `ExitPlanMode` 或 `ShareOnboardingGuide`，只接受不帶 specifier 的裸工具名稱。

`Edit(...)` 允許規則也會授予對相同路徑的讀取存取權，因此您不需要匹配的 `Read(...)` 規則。`Read(...)` 拒絕規則也會在相同路徑上阻止 Edit 和 Write 工具，包括在該處建立新檔案，因為兩個工具都會變更 Claude 必須能夠讀回的內容。對於 Write 工具，`Read` 拒絕檢查需要 Claude Code v2.1.228 或更新版本。

Hook `matcher` 欄位使用裸工具名稱，而不是括號化的規則格式。請參閱 [matcher 模式](https://code.claude.com/docs/zh-TW/hooks.md#matcher-patterns) 以了解匹配規則。如需每個工具在 hooks 中傳遞給 `tool_input` 的欄位名稱，請參閱 [PreToolUse 輸入參考](https://code.claude.com/docs/zh-TW/hooks.md#pretooluse-input)。

## Agent 工具行為

Agent 工具在獨立的上下文視窗中生成一個 subagent。subagent 自主地完成其任務，然後向父對話返回其結果。父對話看不到 subagent 的中間工具呼叫或輸出，只能看到最終結果。同一個工具也可以啟動 teammate 或 fork：

* **Teammate**：啟用 [agent teams](https://code.claude.com/docs/zh-TW/agent-teams.md) 時，帶有 `name` 的呼叫可以改為啟動一個 [teammate](https://code.claude.com/docs/zh-TW/agent-teams.md#how-claude-starts-agent-teams)，它透過團隊訊息而不是返回結果來回報
* **Fork**：在 [fork 模式](https://code.claude.com/docs/zh-TW/sub-agents.md#turn-fork-mode-on-or-off)開啟的任何地方，此工具都可以啟動一個 [forked subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#fork-the-current-conversation)，它會繼承完整的父對話，而不是從頭開始

若要限制子代理執行的回合數，請在 [subagent definition](https://code.claude.com/docs/zh-TW/sub-agents.md#supported-frontmatter-fields) 中設定 `maxTurns`。當子代理達到限制時，Claude Code 會將返回的結果標記為部分輸出，Claude 可以 [resume the subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#resume-subagents) 以繼續。

非 fork 子代理可以使用哪些工具取決於 [subagent definition](https://code.claude.com/docs/zh-TW/sub-agents.md) 中的 `tools` 和 `disallowedTools` 欄位：

* **兩個欄位都未設定**：子代理繼承每個 [tool available to subagents](https://code.claude.com/docs/zh-TW/sub-agents.md#available-tools)。
* **僅設定 `tools`**：子代理只獲得列出的工具。
* **僅設定 `disallowedTools`**：子代理獲得除了列出的工具外的每個父工具。
* **兩者都設定**：`disallowedTools` 優先。同時列在兩者中的工具會被移除。

在每種情況下，解析的集合都限於 [tools available to subagents](https://code.claude.com/docs/zh-TW/sub-agents.md#available-tools)：不可用於子代理的工具永遠不會被授予，即使在 `tools` 中列出也是如此。在 `SubagentHandback` 工具表項目中的條件成立的地方，Claude Code 也會給予子代理該工具，即使您將其留在 `tools` 之外或在 `disallowedTools` 中列出它。

如果子代理的 `tools` 列表中的每個項目都無法匹配可用工具，Agent 工具通常會返回一個錯誤，命名這些項目而不是啟動子代理；請參閱 [Agent would be spawned with zero tools](https://code.claude.com/docs/zh-TW/errors.md#agent-would-be-spawned-with-zero-tools) 以了解訊息和如何修復每個項目。

啟動子代理本身不會提示權限。Claude Code 在執行時根據您的權限規則檢查子代理自己的工具呼叫。

您看到子代理權限提示的位置取決於它是在前景還是背景中執行。Claude Code 預設在背景中執行子代理，除了 [cases that run in the foreground](https://code.claude.com/docs/zh-TW/sub-agents.md#run-subagents-in-foreground-or-background) 外。

* **前景子代理**顯示您在主對話中會看到的相同權限提示，在每個工具呼叫發生時。
* **背景 subagent** 會在您的主工作階段中顯示權限提示。提示會指出是哪個 subagent 在詢問，按 Esc 會拒絕該次工具呼叫，而不會停止 subagent。

若要 [limit what a subagent can reach](https://code.claude.com/docs/zh-TW/sub-agents.md#control-subagent-capabilities)，請首先縮小其 `tools` 欄位，例如透過將 Bash 留在列表之外，或在您的設定中設定拒絕規則。

## AskUserQuestion 工具行為

Claude 使用 `AskUserQuestion` 在需要決策或澄清時向您提出多選題。透過選擇選項來回答，或透過 `Other` 列或備註欄位輸入您自己的文字。

當您透過輸入自己的文字來回答時，Claude Code 會以中立的措辭轉達答案，以便 Claude 遵循您所寫的內容，包括等待或先解釋的請求。

### 問題自動繼續逾時

問題會保持開啟，直到您回答為止。如果您想讓未回答的問題最終關閉並讓 Claude 在沒有您的情況下繼續，請在您的使用者 `settings.json` 中或從 `/config` 中的 **Question auto-continue timeout** 列將 [`askUserQuestionTimeout`](https://code.claude.com/docs/zh-TW/settings-reference#askuserquestiontimeout) 設定為 `60s`、`5m` 或 `10m`。

問題閒置該時間長度而沒有輸入後，對話框會自動關閉：它會提交您已選擇的任何選項，並告訴 Claude 您可能離開了鍵盤，因此 Claude 會根據自己的判斷進行，稍後可以重新提問。您會看到最後 20 秒的倒數計時。按任何鍵即可重新啟動計時器。當您的終端機回報其視窗處於焦點狀態時，計時器不會倒數。

對於 Claude 在[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)中、在[螢幕閱讀器模式](https://code.claude.com/docs/zh-TW/accessibility.md)下，或工作階段連線至 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 時提出的問題，計時器永遠不會啟動。這些問題會一直等待，直到您回答為止。逾時僅適用於 `AskUserQuestion` 的多選題；權限提示（包括計畫核准）在閒置時永遠不會自動解決。

## Bash 工具行為

Bash 工具在單獨的程序中執行每個命令。

### 命令之間保留的內容

* 當 Claude 在主工作階段中執行 `cd` 時，新的工作目錄會延續到後續的 Bash 命令，只要它保持在專案目錄或您使用 `--add-dir`、`/add-dir` 或設定中的 `additionalDirectories` 新增的[額外工作目錄](https://code.claude.com/docs/zh-TW/permissions.md#working-directories)內。這包括 Claude 為回應您後續訊息而執行的命令。
  * subagent 工作階段永遠不會延續工作目錄變更。
  * 如果 `cd` 落在這些目錄之外，Claude Code 會重設為專案目錄，並在工具結果中附加 `Shell cwd was reset to <dir>`。
  * 若要停用此延續功能，使每個 Bash 命令都在專案目錄中啟動，請設定 `CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR=1`。
* 環境變數不會保留。一個命令中的 `export` 在下一個命令中將無法使用。
* 在您的 shell 啟動檔案中定義的別名和 shell 函式可用。在工作階段啟動時，Claude Code 會根據您的 shell 來源 `~/.zshrc`、`~/.bashrc` 或 `~/.profile`，擷取產生的別名、函式和 shell 選項，並將其套用到每個 Bash 命令。

在啟動 Claude Code 之前啟動您的 virtualenv 或 conda 環境。若要使環境變數在 Bash 命令之間保留，請在啟動 Claude Code 之前將 [`CLAUDE_ENV_FILE`](https://code.claude.com/docs/zh-TW/env-vars) 設定為 shell 指令碼，或使用 [SessionStart hook](https://code.claude.com/docs/zh-TW/hooks.md#persist-environment-variables) 動態填入它。

### 逾時和輸出限制

每個命令都在逾時限制下執行，Claude 管理它：當它需要比命令的預設值更長的時間時，它會使用該呼叫傳遞 `timeout` 參數。您永遠不會設定每個命令的逾時。

兩個[環境變數](https://code.claude.com/docs/zh-TW/env-vars.md)控制 Claude 獲得的內容，用於在前景執行的命令：

* `BASH_DEFAULT_TIMEOUT_MS` — 當 Claude 不傳遞逾時時的預設值；預設為兩分鐘
* `BASH_MAX_TIMEOUT_MS` — 使用預設值時，設定上限以限制 Claude 要求的任何內容：有效上限是兩者中較大的，預設為十分鐘

在具有[背景命令時間限制](#time-limit-for-background-commands)的工作階段中，對於 Claude 在背景啟動的命令，`timeout` 改為設定命令可在背景執行的時間長度，並適用該限制單獨的預設值和最大值。[PowerShell 工具](#powershell-tool)遵循相同的逾時規則並讀取相同的兩個變數。

#### 輸出限制

Claude Code 在命令執行時將命令的輸出串流到工作檔案；輸出超過 5 GB 的命令會被終止。命令完成後，Claude Code 從該檔案讀回輸出，最多到下面描述的讀回視窗。輸出有多少到達 Claude 內聯取決於 Claude Code 是否將結果視為失敗：

| 結果 | Claude 獲得的內容 |
| :- | :- |
| 有效 | 內聯最多約 30,000 個字元（預設）；超過該值，為儲存到工作階段目錄的檔案的路徑（檔案超過 64 MiB 的部分會被截斷），加上最多前 2,000 個字元的預覽，Claude 在需要其餘部分時讀取或搜尋該檔案 |
| 失敗 | 內聯最多約 10,000 個字元；超過該值，從讀回視窗中切割的該大小的頭尾摘錄，沒有檔案路徑 |

命令退出碼為 1 只有在 Claude Code 將退出碼 1 識別為該命令的良性結果時，才算作 Bash 工具的有效結果：`grep`、`rg`、`egrep`、`fgrep`、`find`、`diff`、`test` 和 `[`，加上 `git diff` 和 `git grep`。每個其他退出碼為 1 的命令都算作失敗，即使退出碼 1 是良性的資訊結果：`pgrep` 和 `jq -e` 沒有符合項，`cmp` 的檔案不同。

[`BASH_MAX_OUTPUT_LENGTH`](https://code.claude.com/docs/zh-TW/env-vars) 設定 Claude Code 從工作檔案讀回到命令結果中的輸出字元數：預設 30,000，最多硬上限 150,000。當您的命令經常超過該視窗時提高它，例如詳細的建置或完整的測試套件日誌。提高它會擴大讀回視窗，這也是失敗命令的摘錄被切割的視窗。它不會提高內聯上限：超過內聯上限的有效結果會作為檔案路徑加預覽到達，無論此變數如何。

若要變更有效結果中 Claude 內聯接收的數量，請改為設定 [`bashOutputMaxChars`](https://code.claude.com/docs/zh-TW/settings-reference#bashoutputmaxchars) 設定，最多 128,000 個字元。它同時調整內聯上限和讀回視窗的大小，Claude Code 隨後會忽略 `BASH_MAX_OUTPUT_LENGTH`。需要 Claude Code v2.1.261 或更新版本。

### 背景命令

對於長時間執行的程序（例如開發伺服器或監視建置），Claude 可以設定 `run_in_background: true` 以將命令作為背景任務啟動並在其執行時繼續工作。使用 `/tasks` 列出並停止背景任務。在您從那裡停止一個後，或從連接的用戶端（例如桌面應用程式）停止後，Claude 會繼續而不是等待。如果 subagent 啟動了命令，則是該 subagent 繼續。

#### 背景命令何時停止

[前景 subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#run-subagents-in-foreground-or-background) 啟動的命令在該 subagent 的執行結束時停止，無論它完成、失敗或被中斷。主對話或背景 subagent 啟動的命令在最終回應後繼續執行，直到它退出、被停止或達到其[時間限制](#time-limit-for-background-commands)。

當主對話啟動的命令仍在執行時，使用 `-p` 旗標的非互動模式執行會[在其結果之後保持開啟](https://code.claude.com/docs/zh-TW/headless.md#background-tasks-at-exit)，直到該命令退出或達到其時間限制。背景 subagent 啟動的命令會在執行退出時被停止。

#### 背景命令的時間限制

在無人看管執行的工作階段中，例如使用 `-p` 旗標的執行、Agent SDK 應用程式、CI 作業或雲端工作階段，背景 Bash 和 PowerShell 命令有時間限制。您從終端機、桌面應用程式或 VS Code 擴充功能中操作的本機工作階段，對背景命令沒有時間限制。

時間限制需要 Claude Code v2.1.285 或更新版本。在 v2.1.288 之前，它適用於每個工作階段。

時間限制從命令進入背景的時刻開始計算：

* Claude 在背景啟動的命令獲得 30 分鐘，或 Claude 使用 `run_in_background` 傳遞的 `timeout`，最多 2 小時
* 在前景啟動然後移至背景的命令，例如在其逾時時，從移動時獲得 30 分鐘

在使用 `-p` 旗標、且提示詞以文字傳遞而非使用 `--input-format stream-json` 的執行中，兩個預設值都是 10 分鐘而非 30 分鐘，因為該執行會[在其結果之後等待背景命令](https://code.claude.com/docs/zh-TW/headless.md#background-tasks-at-exit)。

當背景命令達到其時間限制時，Claude Code 會停止它並告訴 Claude 原因，Claude 可以使用更長的 `timeout` 重新啟動命令，如果工作仍然需要的話。停止通知讀作 `Background command "<description>" was stopped after reaching its background time limit`。

#### 提高背景命令的時間限制

兩個[環境變數](https://code.claude.com/docs/zh-TW/env-vars.md)提高這些限制，對於 Bash 和 PowerShell 命令一樣。兩者都採用毫秒，且都不能縮短限制：較低的值會保留預設值和 2 小時的最大值。

* 將 `BASH_DEFAULT_TIMEOUT_MS` 設定為高於 `1800000` 以用該值替換 30 分鐘的預設值，無論是對於 Claude 啟動時不帶 `timeout` 的命令還是對於移動的命令。在提示詞以文字傳遞的 `-p` 執行中，任何高於 `600000` 的值都會替換其 10 分鐘的預設值
* 將 `BASH_MAX_TIMEOUT_MS` 設定為高於 `7200000` 以將 2 小時的最大值提高到該值。將 `BASH_DEFAULT_TIMEOUT_MS` 設定為高於 `7200000` 以相同方式提高最大值

#### 移至背景的前景命令

當前景命令在未完成的情況下達到其逾時時，Claude Code 會將其移至背景而不是停止它，除非命令以 `sleep` 開頭。移動的命令的[時間限制](#time-limit-for-background-commands)從移動時開始計算，前景 subagent 的移動命令仍然在該 subagent 的執行結束時停止。

設定 [`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1`](https://code.claude.com/docs/zh-TW/env-vars#variables) 或在 [bare 模式](https://code.claude.com/docs/zh-TW/headless.md#start-faster-with-bare-mode)中執行，會停用自動背景化，因此達到逾時的命令會改為停止。

移至背景的命令的結果說明發生了什麼：

* 當逾時觸發移動時，結果明確報告它：`Command did not complete within its 120s timeout and was moved to the background`，秒數與應用的逾時相符，後跟任務 ID 和輸出正在寫入的檔案路徑。
* 移至背景的命令內的 `cd`、`pushd`、`popd` 或 `chdir` 永遠不會延續：結果說明 `Session cwd remains <dir>; directory changes made by the backgrounded command do not apply to subsequent commands.`，所以 Claude 不會對未發生的目錄變更採取行動。

### Linux 和 WSL 上的記憶體限制

在 Linux 和 WSL 上，將 [`CLAUDE_CODE_TOOL_MEMORY_LIMIT`](https://code.claude.com/docs/zh-TW/env-vars#variables) 設定為大小（例如 `4G`）以限制 Bash、PowerShell 和 [Monitor](#monitor-tool) 工具命令可以使用的記憶體，使一個失控的建置無法佔用工作階段其餘部分需要的記憶體。需要 Claude Code v2.1.233 或更新版本。在 v2.1.246 之前，Monitor 工具命令在上限之外執行。

* 將大小寫成位元組數或帶有 `K`、`M`、`G` 或 `T` 後綴。設定 `0`、`off`、`false`、`no` 或 `none` 以關閉上限。Claude Code 會忽略任何無法讀取為大小的其他值，例如 `4e9`。
* Claude Code 將工作階段的所有 Bash、PowerShell 和 Monitor 命令計入一個上限，而不是每個命令各自計入。
* Claude Code 使用記憶體 cgroup 套用上限。當無法設定 cgroup 時，命令在沒有上限的情況下執行，來自 `claude --debug` 的偵錯日誌會說明原因。
* 在 Claude Code 啟動的第一個程序已開啟上限或因為關閉值或失敗的 cgroup 設定而關閉上限後，Claude Code 會保留該結果直到您重新啟動。若要套用已變更或移除的值或修正後的設定，請再次啟動 `claude`。
* 當命令無法保持在上限以下時，核心會終止命令，其結果中沒有任何內容指出上限。

Claude Code 也可以將它啟動的其他類型的程序計入相同的限制。將 [`CLAUDE_CODE_TOOL_MEMORY_CGROUP_EXCLUDE`](https://code.claude.com/docs/zh-TW/env-vars#variables) 設定為要從上限中豁免的類型的逗號分隔清單；Claude Code 將上限套用到不在您清單上的每種類型。將其設定為 `none` 以限制每種類型，或設定為 `all-new` 以僅限制 Bash、PowerShell 和 Monitor 工具命令。需要 Claude Code v2.1.246 或更新版本。您可以指定的類型：

* `mcp`: 本機 [MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md)
* `lsp`: [語言伺服器](#lsp-tool-behavior)
* `hooks`: [hook](https://code.claude.com/docs/zh-TW/hooks.md) 命令
* `plugin`: [外掛](https://code.claude.com/docs/zh-TW/plugins/overview.md)執行的命令
* `helper`: Claude Code 自己的協助程式命令，例如 `git`
* `agent`: 子 Claude Code 程序，例如 [agent 隊友](https://code.claude.com/docs/zh-TW/agent-teams.md)

無論您列出什麼，這些規則都適用：

* **未知名稱**：Claude Code 會忽略它不識別的名稱
* **變數未設定**：Claude Code 從 Anthropic 從伺服器傳遞的設定中取得其他限制類型的集合，該集合可能隨時間變化，因此當您需要不變的集合時設定變數
* **權限閘控 hook**：即使每種類型都受限，Claude Code 也會從上限中排除可以阻止或變更動作結果的 hook，以及任何此類 hook 呼叫的 MCP 伺服器，因此核心終止權限閘控 hook 無法允許它正在阻止的動作

## Edit 工具行為

Edit 工具執行精確的字串替換。它接受 `old_string` 和 `new_string`，並用後者替換前者。它不使用正規表達式或模糊匹配。

編輯要應用必須通過這些檢查。在任何檢查之前，由 [`Read` 拒絕規則](https://code.claude.com/docs/zh-TW/permissions#tool-specific-permission-rules)匹配的路徑會被拒絕，包括在該處建立新檔案。

* **編輯前讀取**：Claude 在編輯檔案前在目前對話中讀取該檔案，而以 [`PARTIAL view` 通知](#large-files)中斷的讀取不計算在內。Claude Opus 4.6、Claude Haiku 4.5 和較舊的模型始終需要讀取。較新的模型可以在讀取不需要權限提示且 Read 工具可用時編輯未讀檔案。
* **匹配**：`old_string` 必須在檔案中完全按照書寫方式出現。單一個空白字元或縮排差異足以導致不匹配。
* **唯一性**：`old_string` 必須恰好出現一次。當它出現多次時，Claude 要麼提供更長的字串，其中包含足夠的周圍內容以確定一個出現位置，要麼設定 `replace_all: true` 以替換所有出現位置。

在 Claude 最後讀取檔案後，磁碟上變更的檔案仍然可以編輯，當 `old_string` 與目前內容完全且明確匹配，且 Claude Code 可以讀取檔案而無需提示時。針對檔案的目前內容進行匹配可保持安全，結果會注意到檔案包含其他變更，因此 Claude 在依賴周圍內容的編輯前重新讀取它。在任何其他情況下，例如過時的 `old_string` 或不使用 `replace_all` 而匹配多次的情況，Claude 在編輯前再次讀取檔案。

Claude 使用 `cat` 或 `grep` 等 Bash 命令檢視檔案後，也可以在不另外執行 Read 的情況下編輯該檔案。這些命令為 `cat`、`nl`、`bat`、`batcat`、`head`、`tail`、`sed -n 'X,Yp'`、`grep`、`egrep`、`fgrep` 和 `rg`，且每個命令都須在單一檔案上執行，沒有管道或重新導向。如果命令未輸出檔案的任何文字，例如搜尋沒有匹配任何內容時，編輯前讀取檢查仍然適用。

當 Claude 以這種方式檢視檔案時，Claude Code 也會載入適用於該檔案的任何[子目錄 `CLAUDE.md`](https://code.claude.com/docs/zh-TW/memory#how-claude-md-files-load) 和[路徑範圍規則](https://code.claude.com/docs/zh-TW/memory.md#path-specific-rules)。請參閱 [Read 和 Edit 權限規則](https://code.claude.com/docs/zh-TW/permissions.md#read-and-edit)，了解您的 `Read` 和 `Edit` 拒絕規則涵蓋哪些 Bash 命令。

### 非 UTF-8 檔案

Claude 無法對不是有效 UTF-8 的檔案使用 [NotebookEdit](#notebookedit-tool-behavior)。Edit 也是如此，除非檔案以小端序 UTF-16 位元組順序標記開頭。當 Claude 嘗試時，工具會拒絕變更並保持檔案不變。被拒絕的檔案包括以 Windows-1252 或 Shift-JIS 等舊式編碼儲存的非 ASCII 文字、二進位檔案，以及包含無效位元組序列的 UTF-8 檔案。

這些工具之所以拒絕，是因為它們會將整個檔案以 UTF-8 存回，這會把每個無法解碼的位元組替換為替換字元 `U+FFFD`。取而代之的是，[Claude 收到的錯誤](https://code.claude.com/docs/zh-TW/errors.md#file-is-not-valid-utf-8)會指示它使用能保留檔案編碼的 shell 命令來進行變更，或先詢問您是否要將檔案轉換為 UTF-8。

Claude 仍可使用 Write 取代此類檔案，除非新內容包含 `U+FFFD`，也就是 Read 在無法解碼的位元組位置向 Claude 顯示的字元。此防護機制可防止 Claude 將其讀取到的亂碼文字寫回。當 Write 確實取代檔案時，會以 UTF-8 儲存新內容，因此檔案的原始編碼會遺失。

## EndConversation 工具行為

EndConversation 工具會結束目前的工作階段。Claude 只在兩種情況下使用它：

* 作為對持續濫用輸入的最後手段，在嘗試重新導向對話失敗且在較早的訊息中發出明確警告之後
* 當您明確要求查看工具演示並確認您想要結束工作階段時

一般的挫折感、粗言穢語或任務進行不順利都不符合條件，對有害內容的請求也不符合，Claude 會拒絕這些請求而不是結束工作階段。Claude Code 遵循與 claude.ai 相同的方法，後者可以[結束少數聊天](https://www.anthropic.com/research/end-subset-conversations)。

Claude 結束互動式工作階段後，工作階段會被鎖定。新的提示和大多數命令會傳回 `Claude ended this conversation. Start a new session (or /clear) to continue.`，只有 `/clear`、`/resume`、`/help`、`/exit` 和 `/feedback` 仍然可以執行。Claude Code 會在工作階段的文字記錄中記錄結束，因此恢復已結束的工作階段會恢復鎖定；工作階段的歷史記錄不會被刪除。

在[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)中使用 `-p` 旗標恢復已結束的工作階段會出錯並以代碼 1 結束，因此指令碼不會將已結束的執行讀取為成功。

該工具永遠不會提示要求權限，[PreToolUse hooks](https://code.claude.com/docs/zh-TW/hooks.md#pretooluse) 也不會為其執行。只要任何其他工具仍然存在，您就無法阻止它：命名 `EndConversation` 的[拒絕和要求規則](https://code.claude.com/docs/zh-TW/permissions.md#tool-specific-permission-rules)無效，`--disallowedTools` 和 `--tools` 清單都無法移除它。此豁免是刻意的：該工具除了結束對話外什麼都不做，永遠不會讀取或修改檔案或資料，這種保障措施只有在應用它的工作階段無法將其關閉時才能成立。當您的拒絕規則移除所有其他工具並且也符合 `EndConversation` 時（如 `"*"` 所做的那樣），Claude Code 也會移除它，而不是將其作為唯一的工具，除非允許規則明確命名 `EndConversation`。移除所有其他工具但不符合 `EndConversation` 的拒絕清單會將其保留在原位。

[子代理](https://code.claude.com/docs/zh-TW/sub-agents.md)永遠不會獲得該工具。共享主對話工具清單的背景工作會看到它，但在那裡呼叫它不會結束任何東西。

該工具只在以下所有條件都成立時才會出現：

* **模型**：工作階段的模型是 Claude Opus 4.8、Claude Sonnet 5、Claude Fable 5 或這些系列之一的更新版本。
* **介面**：互動式終端工作階段，包括 IDE 整合終端中的 `claude` 工作階段，這是 [JetBrains 外掛程式](https://code.claude.com/docs/zh-TW/jetbrains.md)執行它的方式。其他介面不包括該工具，例如：
  * 非互動式 `-p` 執行
  * 透過 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) TypeScript 和 Python 套件的工作階段
  * [VS Code 擴充功能](https://code.claude.com/docs/zh-TW/vs-code.md)面板，它包含自己的 CLI
  * [GitHub Actions](https://code.claude.com/docs/zh-TW/github-actions.md)
  * [雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)
* **啟動模式**：不是 [`--bare`](https://code.claude.com/docs/zh-TW/headless#start-faster-with-bare-mode) 工作階段。裸機模式只載入 shell 和檔案工具，因此該工具永遠不會在那裡註冊。
* **提供者**：在 [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md)、[AWS 上的 Claude Platform](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md)、[Google Cloud 的 Agent Platform](https://code.claude.com/docs/zh-TW/google-vertex-ai.md) 或 [Microsoft Foundry](https://code.claude.com/docs/zh-TW/microsoft-foundry.md) 上不可用，或在透過[雲端閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)登入的工作階段上不可用。

## EnterWorktree 工具行為

EnterWorktree 工具會建立一個隔離的 [Git worktree](https://code.claude.com/docs/zh-TW/worktrees.md) 並切換進入其中。若提供 `path`，它會切換進入現有的 worktree，而不是建立新的 worktree。

* **`path` 可指定哪些 worktree**：首次進入時，目標可以是目前儲存庫的 worktree。在包含其他儲存庫的儲存庫中，目標也可以是巢狀於其中之儲存庫的 worktree。
* **何時會出現提示**：位於 `.claude/worktrees/` 之外的 `path` 在進入前會提示要求您核准，因為這會將工作階段的工作目錄與寫入權限移至該位置。建立新 worktree 以及 `.claude/worktrees/` 底下的路徑不會出現提示。在 v2.1.206 之前，Claude 進入 `.claude/worktrees/` 之外的路徑時不會出現提示。
* **從 worktree 內部**：在 worktree 工作階段中，只能使用 `path` 形式，且目標必須位於該工作階段所屬儲存庫的 `.claude/worktrees/` 底下。對於具有固定工作目錄的 subagent（例如 [`isolation: worktree`](https://code.claude.com/docs/zh-TW/sub-agents#supported-frontmatter-fields)）也是如此。
* **當工具不存在時**：一旦啟用 [`permissions.blockWritesOutsideWorkingDirectories`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-blockwritesoutsideworkingdirectories)，Claude Code 會移除 `EnterWorktree` 與 `ExitWorktree`，或拒絕對它們的呼叫。若要繼續在 worktree 中工作，請參閱 [Claude 沒有 `EnterWorktree` 工具](https://code.claude.com/docs/zh-TW/worktrees#claude-has-no-enterworktree-tool)。

## Glob 工具行為

Glob 工具按名稱模式尋找檔案。在 Windows 上，它是預設工具集的一部分。在 macOS、Linux 和 WSL 上，Claude Code 會將 Glob 和 [Grep](#grep-tool-behavior) 排除在預設工具集之外，Claude 改為透過 Bash 工具使用 `find` 和 `grep` 進行搜尋。在 Claude 的 shell 中，這兩個命令會執行 `bfs` 和 `ugrep` 的嵌入版本，搜尋會透過 `Bash` 呼叫到達您的 hook 和權限規則。

在 macOS、Linux 和 WSL 上，您可以在以下情況下取回 Glob 和 Grep 工具：

* 您在啟動工作階段時在 [`--tools` 或 `--allowedTools`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 中命名 `Glob` 或 `Grep`，或在等效的 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 選項中命名。使用 `--tools` 時，您會取得列出的工具，在 `--allowedTools` 中命名任一工具會同時復原兩者。設定檔中的允許規則沒有此效果。
* 權限 [拒絕規則](https://code.claude.com/docs/zh-TW/permissions.md#match-all-uses-of-a-tool)、`--disallowedTools` 旗標或 [`--restricted`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 會從工作階段中移除 `Bash`。
* [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#available-tools) 在其 `tools` 欄位中列出 `Glob` 或 `Grep` 並排除 `Bash`。列出的工具僅針對該 subagent 返回，或當它透過 [`--agent`](https://code.claude.com/docs/zh-TW/sub-agents#invoke-subagents-explicitly) 或 `agent` 設定作為主工作階段 agent 執行時，針對整個工作階段返回。

Glob 支援標準 glob 語法，包括 `**` 用於遞迴目錄匹配：

* `**/*.js` 符合任何深度的所有 `.js` 檔案
* `src/**/*.ts` 符合 `src/` 下的所有 `.ts` 檔案
* `*.{json,yaml}` 符合目前目錄中的 `.json` 和 `.yaml` 檔案

結果按修改時間排序，上限為 100 個檔案。如果達到上限，Claude 會在結果中看到截斷旗標，並可以縮小模式。

Glob 預設不遵守 `.gitignore`，因此它會找到被 gitignore 的檔案以及追蹤的檔案。這與 [Grep](#grep-tool-behavior) 不同，後者會跳過被 gitignore 的檔案。若要讓 Glob 遵守 `.gitignore`，請在啟動 Claude Code 前設定 `CLAUDE_CODE_GLOB_NO_IGNORE=false`。

Claude Code 在檢查搜尋目錄是否存在之前，會先決定 Glob 呼叫的權限。它仍會對 [工作目錄](https://code.claude.com/docs/zh-TW/permissions.md#working-directories) 外遺失的 `path` 執行讀取權限檢查，因此路徑的權限提示並不表示該路徑存在。

包含空位元組的 `pattern` 或 `path` 值會傳回錯誤，要求 Claude 移除它。

## Grep 工具行為

Grep 工具搜尋檔案內容中的模式。[Glob](#glob-tool-behavior) 按名稱尋找檔案，而 Grep 在檔案內尋找行。在 macOS、Linux 和 WSL 上，Grep 在與 Glob 相同的條件下預設不存在。請參閱 [Glob 工具行為](#glob-tool-behavior)，了解何時兩種工具都可用。

Grep 是基於 [ripgrep](https://github.com/BurntSushi/ripgrep) 建立的，並使用 ripgrep 的正規表達式語法，而不是 POSIX grep。包含正規表達式元字元的模式需要逃脫。例如，在 Go 程式碼中尋找 `interface{}` 需要使用模式 `interface\{\}`。

ripgrep 拒絕的模式、glob 或檔案類型會傳回包含 ripgrep 診斷的錯誤，以便 Claude 可以更正輸入並再次搜尋。在 v2.1.208 之前，Claude Code 將被拒絕的輸入報告為 `No files found`，而不是錯誤，即使搜尋的文字存在於目標檔案中。

三種輸出模式控制傳回的內容：

* `files_with_matches`：僅檔案路徑，無行內容。這是預設值。
* `content`：匹配的行及檔案和行號。當工具的 `offset` 參數指向模式的最後一個匹配項之後（該模式有匹配項時），Grep 會傳回 `No entries at this offset`，因此 Claude 會擴大或重設 offset，而不是得出模式不匹配的結論。
* `count`：每個檔案的匹配計數，後面是所有匹配檔案的總計。即使工具的 `head_limit` 或 `offset` 參數截斷了列出的每個檔案項目，總計仍涵蓋每個匹配項。

Claude 可以使用 `glob` 參數（例如 `**/*.tsx`）按檔案範圍限制結果，或使用 `type` 參數（例如 `py` 或 `rust`）按語言限制結果。預設情況下，模式在單一行內匹配。Claude 可以設定 `multiline: true` 以跨越行邊界進行匹配。

Grep 遵守 `.gitignore`，因此被 gitignore 的檔案會被跳過。若要搜尋被 gitignore 的檔案，Claude 會直接傳遞其路徑。

Claude Code 在檢查搜尋 `path` 是否存在之前決定 Grep 呼叫的權限。它仍會對 [工作目錄](https://code.claude.com/docs/zh-TW/permissions.md#working-directories) 外的遺失 `path` 執行讀取權限檢查，因此路徑的權限提示並不意味著該路徑存在。

## LSP tool 行為

LSP tool 從執行中的語言伺服器為 Claude 提供程式碼智慧。在每次檔案編輯後，它會自動報告型別錯誤和警告，讓 Claude 可以在沒有單獨建置步驟的情況下修復問題。Claude 也可以直接呼叫它來導覽程式碼：

* 跳至符號的定義
* 尋找符號的所有參考
* 取得位置的型別資訊
* 列出檔案中的符號
* 在工作區中按名稱搜尋符號
* 尋找介面的實作
* 追蹤呼叫階層

Claude Code 會保持 tool 為非作用中狀態，直到您為您的語言安裝[程式碼智慧 plugin](https://code.claude.com/docs/zh-TW/plugins/code-intelligence.md)。在[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)中，Claude Code 不會啟動 plugin 語言伺服器，所以 LSP tool 在那裡保持非作用中。Claude Code 從 plugin 取得語言伺服器的設定，您需要自行安裝伺服器二進位檔。

Claude Code 會針對無法啟動其語言伺服器的檔案上的每個 LSP 呼叫傳回錯誤結果。

## Monitor 工具

Monitor 工具讓 Claude 在背景中監視某些內容，並在其變更時做出反應，而無需暫停對話。請要求 Claude：

* 追蹤日誌檔案並在錯誤出現時標記
* 輪詢 PR 或 CI 工作，並在其狀態變更時報告
* 監視目錄中的檔案變更
* 追蹤您指向的任何長時間執行指令碼的輸出
* 連接到 WebSocket 摘要並在每條訊息到達時報告

對於大多數監視，Claude 會編寫一個小指令碼，在背景中執行它，並在每行輸出到達時接收。對於已經推送事件的伺服器，Claude 可以開啟 [WebSocket](#websocket-source) 而不是執行指令碼。

您可以在同一工作階段中繼續工作，Claude 會在事件到達時插入。

Claude 啟動的每個監視都有一個截止時間：預設為 5 分鐘，最多 30 分鐘，在 [非互動式](https://code.claude.com/docs/zh-TW/headless.md) 執行中使用單一提示詞搭配 `-p` 時最多 10 分鐘。

在截止時間時，監視結束。Claude 會收到一個通知，因此如果仍然需要，它可以重新啟動監視。

透過要求 Claude 取消監視或結束工作階段來停止監視。當您停止啟動監視的 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md)（例如來自 `/tasks`）時，這些監視會隨之停止。

當 Monitor 執行命令時，它使用與 [Bash 相同的權限規則](https://code.claude.com/docs/zh-TW/permissions.md#tool-specific-permission-rules)，因此您為 Bash 設定的 `allow` 和 `deny` 模式也適用於此處。當 [自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode) 處於活動狀態時，Claude Code 會擱置命名 `Monitor` 本身的允許規則，以及它捨棄的其他 [廣泛允許規則](https://code.claude.com/docs/zh-TW/permission-modes.md#how-the-classifier-evaluates-actions)，因此分類器以與檢查 Bash 命令相同的方式檢查 Monitor 命令。

[WebSocket 來源](#websocket-source) 有其自己的核准提示，分類器也會在自動模式中決定。

在下列情況中，Monitor 需要最低版本或 Git Bash：

* **最低版本**：在 Amazon Bedrock、Claude Platform on AWS、Google Cloud 的 Agent Platform 或 Microsoft Foundry 上，或設定了 `DISABLE_TELEMETRY` 或 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` 時，Monitor 需要 Claude Code v2.1.310 或更新版本。此要求適用於 [功能旗標擷取](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching) 關閉時
* **Windows**：只有在安裝 [Git Bash](https://code.claude.com/docs/zh-TW/setup.md#set-up-on-windows) 時才能使用該工具

外掛程式可以宣告在外掛程式處於活動狀態時自動啟動的監視，而不是要求 Claude 啟動它們。請參閱 [外掛程式監視](https://code.claude.com/docs/zh-TW/plugins/components.md#monitors)。

### WebSocket 來源

當伺服器已經透過 WebSocket 推送事件時，Claude 可以直接連接到它，而不是編寫輪詢指令碼。每種套接字活動要麼變成一個事件，要麼結束監視：

* **文字訊息**：每一條都變成一個事件，即使訊息跨越多行。
* **二進位訊息**：不會通過。Claude 會收到一個佔位符行，例如 `[binary frame, 512 bytes]`。
* **大於 1 MiB 的訊息**：監視結束，因此請訂閱存在的篩選摘要。
* **套接字關閉**：監視結束，Claude 會收到關閉代碼。

WebSocket 監視採用 `ws` 輸入代替 `command`，單一 Monitor 呼叫無法結合兩者。`ws` 輸入有兩個欄位：

| 欄位 | 必要 | 說明 |
| :- | :- | :- |
| `url` | 是 | 要連接的端點。必須是 `ws://` 或 `wss://` URL，不含嵌入的憑證或空白字元，僅使用 ASCII 字元 |
| `protocols` | 否 | 在握手期間提供的 WebSocket 子協議名稱。每個項目必須是有效的子協議 token，且清單不能包含重複項 |

`timeout_ms` 截止時間也適用於 WebSocket 監視：監視在截止時間結束，`TaskStop` 會提前取消它。

開啟 WebSocket 會提示核准；在 [自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode) 中，分類器會改為決定。提示不提供跳過相同主機的未來提示的選項。

Claude Code 拒絕指向私人、連結本機或雲端中繼資料位址的 URL，包括解析為該位址的主機名稱。它也拒絕 `sandbox.network.deniedDomains` 中的主機，以及當在受管設定中設定 [`allowManagedDomainsOnly`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-network-allowmanageddomainsonly) 時，任何在受管允許清單外的主機。

## NotebookEdit 工具行為

NotebookEdit 一次修改一個 Jupyter notebook 儲存格，按其 `cell_id` 定位儲存格。它不像 [Edit](#edit-tool-behavior) 在純文字檔案上那樣跨 notebook 執行字串替換。

三個編輯模式控制目標儲存格發生的情況：

* `replace`：覆寫儲存格的來源。這是預設值。
* `insert`：在目標後新增新儲存格。沒有 `cell_id` 時，新儲存格位於 notebook 的開始。需要 `cell_type` 設定為 `code` 或 `markdown`。
* `delete`：移除目標儲存格。

對於無法以 UTF-8 解碼的 notebook 檔案，NotebookEdit 會依據[與 Edit 相同的規則](#non-utf-8-files)拒絕處理，且不會寫入任何內容。

權限規則使用 `Edit(...)` 路徑格式。像 `Edit(notebooks/**)` 這樣的規則涵蓋該目錄中檔案上的 NotebookEdit 呼叫。

## PowerShell 工具

PowerShell 工具讓 Claude 能夠原生執行 PowerShell 命令。在 Windows 上，這表示命令在 PowerShell 中執行，而不是透過 Git Bash 路由。工具的可用性取決於您的平台：

* **Windows 未安裝 Git Bash**：工具會自動啟用。
* **Windows 已安裝 Git Bash**：工具在 claude.ai 和 Console 帳戶上預設為開啟；在 Amazon Bedrock、Google Cloud 的 Agent Platform 和 Microsoft Foundry 工作階段中，設定 `CLAUDE_CODE_USE_POWERSHELL_TOOL=1` 以啟用它，或設定 `0` 以關閉它。
* **Linux、macOS 和 WSL**：工具是選擇性加入。

您的 [PreToolUse hooks](https://code.claude.com/docs/zh-TW/hooks.md#powershell) 在 `tool_input.command` 中接收工具的命令字串，欄位與 Bash 工具相同。

在檢查 shell 命令的 hooks 中比對 `Bash|PowerShell`；[PowerShell hook 輸入部分](https://code.claude.com/docs/zh-TW/hooks.md#powershell)說明為什麼單獨比對 `Bash` 是不夠的。

### 啟用 PowerShell 工具

在您的環境或 `settings.json` 中設定 `CLAUDE_CODE_USE_POWERSHELL_TOOL=1`：

```json theme={null}
{
  "env": {
    "CLAUDE_CODE_USE_POWERSHELL_TOOL": "1"
  }
}
```

在 Windows 上，將變數設定為 `0` 以關閉工具。在 Linux、macOS 和 WSL 上，工具需要 PowerShell 7 或更新版本：安裝 `pwsh` 並確保它在您的 `PATH` 中。

在 Windows 上，Claude Code 會自動偵測 PowerShell 7+ 的 `pwsh.exe`，並回退到 PowerShell 5.1 的 `powershell.exe`。啟用工具時，Claude 會將 PowerShell 視為主要 shell。當安裝了 Git Bash 時，Bash 工具仍可用於 POSIX 指令碼。

Claude Code 以程序範圍只啟動 PowerShell 搭配 `-ExecutionPolicy Bypass`，因此 `.ps1` 指令碼和模組匯入可在預設 Windows 安裝上運作，無需變更機器的原則。程序範圍略過不會覆寫群組原則 `MachinePolicy` 或 `UserPolicy`，因此企業原則仍然適用。若要改為遵守機器的有效執行原則，請設定 `CLAUDE_CODE_POWERSHELL_RESPECT_EXECUTION_POLICY=1`。

### Bash 拒絕規則也會關閉 PowerShell 工具

在已安裝 Git Bash 的 Windows 上，拒絕 Bash 也會在該工作階段中關閉 PowerShell 工具。這適用於範圍限定的規則（例如 `Bash(git push *)`）以及單獨的 `Bash`，也適用於來自您任一設定檔或 `--disallowedTools` 的規則。Claude Code 這樣做是因為 `Bash` 規則不會限制 PowerShell 工具，後者有[自己的權限規則](https://code.claude.com/docs/zh-TW/permissions.md#powershell)。若 PowerShell 保持開啟，Claude 可能會在其中執行您的規則在 Bash 中所拒絕的操作。

若要在有 Bash 拒絕規則的同時保持 PowerShell 工具開啟，請執行下列任一操作：

* 在您的環境或設定檔的 `env` 區塊中設定 `CLAUDE_CODE_USE_POWERSHELL_TOOL=1`，如[啟用 PowerShell 工具](#enable-the-powershell-tool)所示。
* 在設定檔中新增範圍限定的 [`PowerShell` 權限規則](https://code.claude.com/docs/zh-TW/permissions#powershell)，例如 `PowerShell(git push *)` 拒絕規則。

若沒有其中任何一項，範圍限定的 Bash 拒絕規則會讓 Bash 工具保持可用，而 Claude Code 會在沒有警告的情況下關閉 PowerShell。移除整個 Bash 工具的規則會讓 Claude 在該工作階段中沒有任何 shell 工具。

### 設定、hooks 和 skills 中的 shell 選擇

三個額外的設定控制 PowerShell 的使用位置：

* [`settings.json`](https://code.claude.com/docs/zh-TW/settings-reference#all-settings) 中的 `"defaultShell": "powershell"`：透過 PowerShell 路由互動式 `!` 命令。需要啟用 PowerShell 工具。
* 個別 [command hooks](https://code.claude.com/docs/zh-TW/hooks.md#command-hook-fields) 上的 `"shell": "powershell"`：在 PowerShell 中執行該 hook。Hooks 直接啟動 PowerShell，因此無論 `CLAUDE_CODE_USE_POWERSHELL_TOOL` 為何都能運作。
* [skill frontmatter](https://code.claude.com/docs/zh-TW/skills.md#frontmatter-reference) 中的 `shell: powershell`：在 PowerShell 中執行 `` !`command` `` 區塊。需要啟用 PowerShell 工具。

PowerShell 命令遵循與 Bash 命令[相同的主工作階段工作目錄重設行為](#what-persists-between-commands)，包括 `CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR` 環境變數。

PowerShell 命令也會接收 hook 透過 `CLAUDE_ENV_FILE` 保存的變數，條件如 [PowerShell 命令中的保存變數](https://code.claude.com/docs/zh-TW/hooks.md#persisted-variables-in-powershell-commands)所述。需要 Claude Code v2.1.296 或更新版本。

### PowerShell 中來自搜尋和 `git diff` 的結束代碼 1

如果 Claude 在 PowerShell 工具中執行的 `grep` 或 `rg` 搜尋沒有符合任何項目並顯示 `Error: Exit code 1`，表示該搜尋並未失敗。您不需要採取任何動作。當搜尋是較長命令的一部分時，就可能出現此錯誤。例如，當 `rg` 以結束代碼 1 結束時，`rg foo | Out-Null` 會顯示此錯誤，而 `rg foo` 則不會。

PowerShell 工具可以將來自 `grep`、`rg`、`egrep`、`fgrep`、`findstr`、`git grep` 和 `git diff` 的結束代碼 1 視為正常結果。這些搜尋使用結束代碼 1 來回報無符合項目。來自 `git diff` 的結束代碼 1 表示檔案不同。在具有 `shell: powershell` 的 skill 中，Claude 執行時顯示此錯誤的命令會[視為失敗](https://code.claude.com/docs/zh-TW/skills.md#when-an-injected-command-fails)。

### Windows 編碼和結束代碼

* 使用 `>` 和 `>>` 的重新導向在 PowerShell 5.1 上寫入 UTF-8 檔案
* Claude Code 將管道傳送到原生命令標準輸入的文字編碼為 UTF-8
* Claude Code 擷取錯誤輸出而不含 ANSI 逸出序列
* 其子程序等待標準輸入的命令會收到檔案結尾而不是掛起
* 如果 `where.exe` 找不到符合項目，或 `fc.exe` 或 `diff.exe` 發現檔案不同，結果可能會顯示 `Error: Exit code 1`，但命令並未失敗。您不需要採取任何動作。
* 如果 `robocopy` 的結束代碼 1 到 7 顯示為錯誤，表示複製並未失敗，您不需要採取任何動作。`robocopy` 以結束代碼 0 到 7 回報結果（例如已複製的檔案），並在失敗時以 8 或更高的代碼結束。

### 預覽限制

PowerShell 工具在預覽期間有下列已知限制：

* PowerShell 設定檔未載入
* 在 Windows 上，不支援沙箱化

## Read 工具行為

Read 工具接受檔案路徑並傳回包含行號的內容。Claude 被指示始終傳遞絕對路徑。

讀取空檔案會傳回通知，說明檔案存在但內容為空，而超過最後一行的 `offset` 會傳回通知，提供檔案的行數。

Read 處理純文字以外的多種檔案類型：

* **影像**：PNG、JPEG、GIF 和 WebP 檔案會以 Claude 可以看到的視覺內容形式傳回，而不是原始位元組。Claude Code 會在傳送前調整大小並重新壓縮大型影像以符合模型的影像大小限制，因此 Claude 可能會看到大型螢幕擷取畫面的縮小版本。

  如果 Claude 在大型影像中遺漏了細微的像素級細節，請要求它裁剪您關心的區域，例如透過 Bash 使用 ImageMagick，然後再讀取裁剪後的影像。

  Read 會拒絕讀取大於 128 MB 的影像檔案，並傳回錯誤，告訴 Claude 調整影像大小或匯出較小的副本，然後讀取該副本。如果 Claude 在遇到錯誤時停止，而沒有這樣做，請參閱 [File is too large to read as an image](https://code.claude.com/docs/zh-TW/errors.md#file-is-too-large-to-read-as-an-image)。
* **PDF**：Claude 會完整讀取短 `.pdf` 檔案。對於超過 10 頁的 PDF，它會使用 `pages` 參數（例如 `"1-5"`）按範圍讀取，一次最多 20 頁。頁面範圍讀取會使用 poppler-utils 中的 `pdftoppm` 呈現頁面，因此在 macOS 上使用 `brew install poppler` 安裝，或在 Debian 和 Ubuntu 上使用 `apt-get install poppler-utils` 安裝。在 Windows 和其他平台上，安裝將 `pdftoppm` 放在您的 `PATH` 上的 poppler 組建。沒有它，頁面範圍讀取會失敗並顯示 `pdftoppm is not installed`。
* **Jupyter 筆記本**：`.ipynb` 檔案會傳回所有儲存格及其輸出，包括程式碼、markdown 和視覺化。儲存格總計超過 256 KB 或超過 [token 限制](#large-files)的筆記本會改為傳回錯誤。Claude Code 拒絕讀取超過 100 MB 的筆記本檔案；錯誤會告訴 Claude 如何改為讀取筆記本的一部分，例如使用 shell 命令讀取儲存格的切片。

Read 只讀取檔案，不讀取目錄。Claude 使用 shell 命令（例如 `ls`）列出目錄內容。

Read 會拒絕讀取副檔名被視為二進位格式的檔案，例如 `.xlsx`、`.parquet`、`.heic` 或 `.zip`。Claude 在遭到拒絕後會繼續工作：錯誤會建議適用於該檔案類型的 skill（如果有的話），否則會建議可讀取該格式的 shell 命令或指令碼。如果您 [`@`-提及](https://code.claude.com/docs/zh-TW/common-workflows#reference-files-and-directories) 一個 Read 會拒絕讀取的檔案，Claude 會收到該檔案的路徑，但不會收到其內容。

### 大型檔案

Claude 可以讀取大於單次 Read 呼叫所能傳回內容的文字檔案。根據預設，單次呼叫最多傳回 25,000 個 token，或您在 [`CLAUDE_CODE_FILE_READ_MAX_OUTPUT_TOKENS`](https://code.claude.com/docs/zh-TW/env-vars) 中設定的值，並會拒絕讀取超過 256 KB 的整個檔案，因此 Claude 會使用 `offset` 和 `limit` 分頁讀取較大的檔案。在 Claude Code v2.1.296 或更新版本中，Claude 可以在需要時（例如您要求讀取整個檔案）設定 `allow_large: true`，改為在單次呼叫中讀取整個檔案或較長的行範圍。該讀取會依據工作階段[上下文視窗](https://code.claude.com/docs/zh-TW/context-window.md)中剩餘的空間來決定大小，而不是依據預設限制。影像、PDF 和筆記本仍維持其限制。

當讀取超過預設限制時，Claude 會收到的內容：

* **整個檔案超過 token 限制**：檔案的第一頁，並附上 `PARTIAL view` 通知，說明它收到了多少檔案內容，以及如何使用 `offset` 和 `limit` 讀取更多內容
* **整個檔案超過 256 KB，或 `offset` 或 `limit` 讀取超過 token 限制**：錯誤，告訴它使用 `offset` 和 `limit` 讀取一部分，或改為使用 [Grep](#grep-tool-behavior) 搜尋特定內容

## SendFeedback 工具行為

Claude 起草的回饋是 Claude 為您撰寫的關於 Claude Code 的回饋報告。它需要 Claude Code v2.1.238 或更新版本。Claude Code 會將每份草稿保存在您的機器上的 `~/.claude/feedback/drafts/` 下，在您發送之前，任何內容都不會到達 Anthropic。Claude 在以下情況下會使用 SendFeedback 工具起草一份：

* 工具或命令持續失敗
* 它無法幫助您要求的事項
* 您指出它犯的錯誤，或它自己發現了一個
* 您要求它提交回饋

### 當 Claude 起草時您看到的內容

Claude 將草稿加入佇列後，您會在提示上方看到一張卡片，顯示草稿的標題。按 `1` 查看草稿，按 `2` 兩次以按原樣發送，或按 `0` 關閉它。已關閉的草稿會保留在您的佇列中。關閉卡片後，Claude Code 會詢問是否關閉 Claude 起草的回饋。一旦您拒絕兩次，它就會停止詢問。

預設情況下，您在一個工作階段中最多看到三張卡片；Anthropic 可以從伺服器調整該限制，無需發佈。超過限制後，以及每當您將 [`feedbackDrafts`](https://code.claude.com/docs/zh-TW/settings-reference#feedbackdrafts) 設定為 `quiet` 時，您只會在提示頁尾看到佇列中草稿的計數。

### 查看和編輯草稿

執行不帶引數的 `/feedback` 以開啟您的佇列。它列出來自所有工作階段的每份佇列中的草稿，包括您關閉或從未看到其卡片的草稿。選擇一份草稿以開啟它進行查看，您可以：

* 編輯標題、區域和詳細資訊
* 將 **Send transcript** 設定為 `yes` 或 `no`。當 Claude 將草稿加入佇列的工作階段中的文字記錄仍然可用時，它會以 `yes` 開始，這會將該對話發送給 Anthropic；`no` 只發送報告
* 發送草稿、捨棄它，或將其保留在佇列中以供稍後使用

若要自己撰寫報告，請按 `w` 以開啟標準回饋對話框。`/feedback` 後面跟著文字，以及 `/bug`，會直接開啟該對話框。

### 發送草稿

當您發送草稿時，Claude Code 會以與 `/feedback` 報告相同的方式提交它，具有相同的[保留期](https://code.claude.com/docs/zh-TW/data-usage.md#feedback-using-the-%2Ffeedback-command)，並從您的機器中刪除草稿。當您從卡片發送時，它會顯示 `✓ Sent`；當您從佇列發送時，它會關閉並顯示收據 ID。

報告包含：

* 您的標題、區域和詳細資訊
* 環境資訊，例如您的 Claude Code 版本、作業系統和模型
* 最近 API 請求的 ID
* 對話文字記錄，當您在查看畫面上將 **Send transcript** 保留為 `yes` 時。從卡片發送永遠不會包含文字記錄

Claude Code 會將您的工作目錄保留在本機草稿中，以便它可以找到文字記錄，並且不會發送該目錄。

在[零資料保留的組織](https://code.claude.com/docs/zh-TW/zero-data-retention.md#features-disabled-under-zdr)中，以及已套用 [HIPAA 設定](https://code.claude.com/docs/zh-TW/hipaa-setup.md)的組織中，Claude Code 會將 SendFeedback 工具排除在您的工作階段之外。如果零資料保留組織中的工作階段仍然提供該工具，草稿會保留在您的機器上，發送會失敗並顯示 `Feedback collection is not available for organizations with custom data retention policies.`

### 捨棄或保留草稿

當您捨棄草稿時，Claude Code 會從您的機器中刪除它。您在佇列中保留的草稿會在 30 天後過期，或在 [`cleanupPeriodDays`](https://code.claude.com/docs/zh-TW/settings-reference#cleanupperioddays) 更短時過期。佇列在所有工作階段中最多保留 10 份草稿，當 Claude 將第 11 份加入佇列時，Claude Code 會刪除最舊的。當您執行 `/exit` 且工作階段中的草稿仍在佇列中時，Claude Code 會詢問您是否在退出前查看或捨棄它們。

### 關閉 Claude 起草的回饋

在 `/config` 中將 **Claude-drafted feedback** 設定為 `off`，這會寫入 [`feedbackDrafts`](https://code.claude.com/docs/zh-TW/settings-reference#feedbackdrafts) 設定，或為一個工作階段設定 [`CLAUDE_CODE_SEND_FEEDBACK=0`](https://code.claude.com/docs/zh-TW/env-vars)。使用任一方式，Claude 都無法將草稿加入佇列。若要在沒有卡片的情況下繼續起草，請改為將 `feedbackDrafts` 設定為 `quiet`。管理員可以在[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)中設定 `feedbackDrafts`，這優先於您自己的設定。

### 沒有 Claude 起草回饋的工作階段

Claude Code 在使用 Claude API 而非雲端提供者的您自己機器上的互動式終端工作階段中包含該工具。它將該工具排除在外：

* 非互動式 `-p` 執行和[代理 SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 工作階段，這些沒有螢幕來查看佇列
* [雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)，無法寫入您機器上的佇列
* [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md)、[Claude Platform on AWS](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md)、[Google Cloud's Agent Platform](https://code.claude.com/docs/zh-TW/google-vertex-ai.md) 或 [Microsoft Foundry](https://code.claude.com/docs/zh-TW/microsoft-foundry.md) 上的工作階段
* 您設定 [`CLAUDE_CODE_SEND_FEEDBACK=0`](https://code.claude.com/docs/zh-TW/env-vars) 或 [`DISABLE_FEEDBACK_COMMAND=1`](https://code.claude.com/docs/zh-TW/env-vars) 的工作階段，將 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` 設定為任何非空值，或關閉[功能旗標擷取](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)
* 已關閉產品回饋的組織、[零資料保留的組織](https://code.claude.com/docs/zh-TW/zero-data-retention.md#features-disabled-under-zdr)，以及已套用 [HIPAA 設定](https://code.claude.com/docs/zh-TW/hipaa-setup.md)的組織

## Task 工具可用性

Task 追蹤工具 `TaskCreate`、`TaskGet`、`TaskUpdate`、`TaskList` 和 `TodoWrite` 預設僅在 Opus 4.7、Sonnet 4.6、Haiku 4.5 及更早的模型上可用。只要工具可用，您就會獲得四個 Task 工具，或當您設定 [`CLAUDE_CODE_ENABLE_TASKS=0`](https://code.claude.com/docs/zh-TW/env-vars) 時改為 `TodoWrite`。

在所有其他模型上，Claude Code 會排除這些工具，除非您選擇加入。同樣的情況也適用於 Claude Code 無法識別的模型 ID，例如透過 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)提供的自訂模型名稱。在較新的模型上，Claude 可以在沒有書面檢查清單的情況下追蹤多步驟工作，而工具的定義和提醒會佔用上下文。沒有這些工具，Claude 在工作時不會向[任務清單](https://code.claude.com/docs/zh-TW/interactive-mode.md#task-list)添加任何內容。

如果您想在預設情況下沒有這些工具的模型上使用它們，請執行以下其中一項操作：

* 在啟動 Claude Code 之前匯出 [`CLAUDE_CODE_ENABLE_TODO_TOOLS=1`](https://code.claude.com/docs/zh-TW/env-vars)，例如 `CLAUDE_CODE_ENABLE_TODO_TOOLS=1 claude`。Claude Code 隨後會在每個模型和每個提供者上提供相同的工具
* 在 [`--allowedTools`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 中命名其中一個工具，例如 `claude --allowedTools TaskCreate`
* 在 [`--tools`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 中列出工具，這會將工作階段的內建工具限制為其命名的工具。將您想要的工具與您使用的其他內建工具一起包含
* 在 Agent SDK 中，[`allowedTools` 和 `tools` 選項](https://code.claude.com/docs/zh-TW/agent-sdk/todo-tracking#model-availability)的工作方式與這兩個旗標相同

在[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)和[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)中，Claude Code 在每個模型上提供相同的工具，無論是否列出。

此處描述的預設集合適用於 Claude Code v2.1.268 及更新版本。

### Subagent 與 agent team 中的 Task 追蹤工具

只有當您的工作階段具有 Task 追蹤工具時，subagent 才會擁有這些工具，無論 subagent 執行哪個模型。同程序的 [agent team](https://code.claude.com/docs/zh-TW/agent-teams.md) 隊友在您的工作階段具有 Task 追蹤工具時也會擁有這些工具。[分割窗格](https://code.claude.com/docs/zh-TW/agent-teams.md#choose-a-display-mode)隊友是一個獨立的 Claude Code 程序，它會[繼承](https://code.claude.com/docs/zh-TW/agent-teams.md#permissions)您的 `--tools` 清單和拒絕規則，而非 `--allowedTools`，因此請檢查您的設定：

* **沒有 `--tools` 清單或拒絕規則，且未為隊友設定 `CLAUDE_CODE_ENABLE_TODO_TOOLS`**：隊友會擁有其自身模型預設具備的 Task 追蹤工具。
* **在您的 shell 中匯出了 `CLAUDE_CODE_ENABLE_TODO_TOOLS`**：Claude Code 會傳遞給隊友一組固定的環境變數，其中不包含您匯出的那一個。若也要為隊友設定它，請在您的 shell 中執行 `claude --settings '{"env":{"CLAUDE_CODE_ENABLE_TODO_TOOLS":"1"}}'` 來啟動工作階段。隊友也會取得您的 [`--settings`](https://code.claude.com/docs/zh-TW/settings#change-a-setting-for-one-session) 值。
* **`--tools` 中命名了 Task 追蹤工具**：隊友在任何模型上都會擁有這些工具。
* **某個 Task 追蹤工具未列於 `--tools` 中，或在拒絕規則中被指定**：隊友不會擁有該工具。

沒有 Task 工具時，agent 會透過訊息而非[共用任務清單](https://code.claude.com/docs/zh-TW/agent-teams.md#assign-and-claim-tasks)與其團隊協調。

## WebFetch 工具行為

WebFetch 接受一個 URL 以及一個描述要擷取哪些內容的提示詞。它會擷取該頁面，並在伺服器傳回 HTML 時將回應轉換為 Markdown。對於大多數擷取作業，它接著會在另一個獨立的模型呼叫中，針對內容執行該提示詞，而 Claude 收到的是該呼叫的結果，而非原始頁面。轉換步驟無法設定。

這使得 WebFetch 在設計上就是有損的。擷取提示詞決定了哪些內容會傳達給 Claude，因此若結果表示某個頁面未提及某事，可能只代表提示詞沒有詢問到它。請要求 Claude 使用更具體的提示詞再次擷取，或透過 Bash 使用 `curl` 取得未經處理的頁面。

有幾項行為會影響 Claude 收到的回應：

* WebFetch 會在發出請求之前，拒絕 `localhost` 以及任何不含點的主機名稱，例如單純的內部網路名稱。它[傳回的錯誤](https://code.claude.com/docs/zh-TW/errors.md#webfetch-cannot-fetch-localhost)會告訴 Claude 改為透過 Bash 使用 `curl` 存取本機伺服器。
* HTTP URL 會自動升級為 HTTPS。
* WebFetch 每次呼叫最多讀取頁面內容的 100,000 個字元。在 Claude Code v2.1.290 或更新版本中，較長頁面的結果會告知 Claude 有多少內容未被讀取，讓 Claude 可以擷取下一部分。
* WebFetch 預設會將每個回應快取 15 分鐘，因此重複擷取相同 URL 時會快速傳回。在 Claude Code v2.1.233 或更新版本中，可設定 [`CLAUDE_CODE_WEBFETCH_CACHE_TTL_MS`](https://code.claude.com/docs/zh-TW/env-vars#variables) 來變更 WebFetch 保留每個回應的時間長度。
* 若頁面在五分鐘內未完成下載（包括 WebFetch 追蹤的任何重新導向），則會因期限錯誤而失敗。在 Claude Code v2.1.268 或更新版本中，可設定 [`CLAUDE_CODE_WEBFETCH_DEADLINE_MS`](https://code.claude.com/docs/zh-TW/env-vars#variables) 來變更此限制，或設為 `0` 以移除限制。
* 當 URL 重新導向至不同的主機時，WebFetch 不會追蹤該重新導向，而是傳回一個列出原始 URL 與重新導向目標的文字結果。接著 Claude 會以第二次 WebFetch 呼叫擷取新的 URL。
* 當擷取步驟遇到過載的 API 時，Claude Code 會以退避方式重試；若擷取仍然失敗，則會傳回錯誤結果。

在 Manual 與 `acceptEdits` [權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md)下，WebFetch 會在擷取前顯示權限提示，但您的[權限規則](https://code.claude.com/docs/zh-TW/permissions.md#manage-permissions)已允許或拒絕的網域，以及一組內建、會直接擷取而不顯示提示的預先核准文件網域除外。無論您的規則允許什麼，擷取作業都會先通過 [WebFetch 網域安全性檢查](https://code.claude.com/docs/zh-TW/data-usage.md#webfetch-domain-safety-check)；該章節說明了檢查所傳送的內容以及可略過檢查的設定。權限提示提供三個選項：

* **Yes**：僅核准此次擷取。下一次 WebFetch 呼叫會再次顯示提示，即使是相同網域也是如此。
* **Yes, and don't ask again for `<domain>`**：核准此次擷取，並將該網域的 `WebFetch(domain:...)` 允許規則儲存至該儲存庫的 `.claude/settings.local.json`。請參閱[已儲存的核准如何保留](https://code.claude.com/docs/zh-TW/permissions.md#permission-system)。當您的組織設定了 [`allowManagedPermissionRulesOnly`](https://code.claude.com/docs/zh-TW/permissions#managed-only-settings) 時，Claude Code 會隱藏此選項。
* **No, and tell Claude what to do differently**：拒絕此次擷取。

若要事先允許某個網域而不顯示提示，請新增類似 `WebFetch(domain:example.com)` 的允許規則；`WebFetch(domain:*)` 則會允許所有網域。`auto` 與 `bypassPermissions` [權限模式](https://code.claude.com/docs/zh-TW/permissions.md#permission-modes)會略過提示，但符合明確 `ask` 規則的網域除外。

在 `deny`、`ask` 或 `allow` 中明確設定的 `WebFetch(domain:...)` 規則優先於預先核准的網域集合，因此您可以封鎖某個預先核准的網域，或要求對其顯示提示。

當 URL 是 claude.ai [artifact](https://code.claude.com/docs/zh-TW/artifacts.md) 連結時，Claude Code 也可能要求核准以讀取該 artifact 本身。關於會要求核准的情況，請參閱[讀取與您分享的 artifact](https://code.claude.com/docs/zh-TW/artifacts.md#read-an-artifact-shared-with-you)。

WebFetch 會設定以 `Claude-User` 開頭的 `User-Agent` 標頭，以及偏好 Markdown 而非 HTML 的 `Accept` 標頭，讓支援內容協商的伺服器可以直接傳回 Markdown。

沙箱化的命令不會繼承 WebFetch 內建的預先核准文件網域集合。若要讓沙箱化的命令在不顯示提示的情況下存取某個網域，請將該網域新增至 [`allowedDomains`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-network-alloweddomains)，或以 `WebFetch(domain:...)` 規則允許它，[沙箱也會遵循](https://code.claude.com/docs/zh-TW/sandboxing.md#network-isolation)此規則。反之，WebFetch 從不讀取沙箱允許清單，因此將網域新增至沙箱或組織的網路允許清單，並不會讓 WebFetch 停止對該網域顯示提示。

### WebFetch 可用性

在 Claude Code v2.1.285 或更新版本中，將 [`CLAUDE_CODE_DISABLE_WEB_FETCH`](https://code.claude.com/docs/zh-TW/env-vars#variables) 設為 `1` 即可關閉 WebFetch。

如果您使用 Team 或 Enterprise claude.ai 帳戶登入，且未透過 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)連線，WebFetch 也會取決於您組織的政策，Claude Code 會在工作階段開始時向 `api.anthropic.com` 請求該政策。對於 Claude Code 無法判斷其方案的工作階段也是如此，例如在由其他應用程式提供的 claude.ai token 下執行的工作階段。

如果工作階段中缺少 WebFetch，請在該工作階段中執行 `/status`。如果其 `Organization policy` 行顯示政策未載入，並將 web fetch 列為等待該政策的功能之一，表示 Claude Code 正在暫緩提供 WebFetch，直到能確認您的組織允許它為止。在工作階段之外，`claude doctor` 會自行發出請求並顯示相同的行。一旦允許 WebFetch 的政策載入完成，該工具就會恢復可用，無需重新啟動。

## WebSearch 工具行為

WebSearch 針對 Anthropic 的[網路搜尋](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)後端執行查詢，並傳回結果標題和 URL。它不會擷取結果頁面。若要讀取 Claude 在搜尋結果中找到的頁面，它會後續使用 [WebFetch](#webfetch-tool-behavior)。

該工具每次呼叫最多可發出八個後端搜尋，在傳回結果前在內部精煉搜尋。Claude 可以使用 `allowed_domains` 限制結果範圍以僅包含特定主機，或使用 `blocked_domains` 排除它們。這兩個清單無法在單一呼叫中結合。

當搜尋請求擊中過載的 API 時，Claude Code 會以退避方式重試；仍然失敗的呼叫會傳回錯誤結果。

WebSearch 權限規則不採用指定符。`allow` 或 `deny` 中的單純 `WebSearch` 項目是唯一形式。

搜尋後端不可設定。若要使用不同的提供者進行搜尋，請新增公開搜尋工具的 [MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md)。

> [!NOTE]
>
> WebSearch 在 Claude API、[AWS 上的 Claude Platform](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md) 和 Microsoft Foundry 上可用。在 Google Cloud 的 Agent Platform 上，它適用於 Opus 4、Sonnet 4、Haiku 4.5 及更新版本的模型。Amazon Bedrock 不公開伺服器端網路搜尋工具。

### 工作階段搜尋限制

互動式終端機工作階段的 WebSearch 呼叫限制為 200 次。來自主對話和 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 的搜尋（例如平行研究展開）都會計入相同的限制。

當工作階段達到限制時，搜尋在對話中會顯示為未執行任何操作的呼叫。Claude 會收到通知，告訴它繼續使用已經收集的資訊、在回答中說明此情況，並且如果需要更多搜尋，則要求您提高限制。

若要取得更多搜尋次數，請提高上限、等待限制回補，或開始新的對話：

* **提高上限**：將 [`CLAUDE_CODE_MAX_WEB_SEARCHES_PER_SESSION`](https://code.claude.com/docs/zh-TW/env-vars#variables) 環境變數設定為正整數，例如 `500`。上限可以提高但無法關閉。
* **等待回補**：在 Claude Code v2.1.290 或更新版本中，互動式終端機工作階段的限制大約每小時回補 100 次呼叫。若要變更速率，請將 [`CLAUDE_CODE_WEB_SEARCH_REFILLS_PER_HOUR`](https://code.claude.com/docs/zh-TW/env-vars#variables) 設定為每小時的呼叫次數，例如 `50`。
* **開始新的對話**：在 Claude Code 提示字元執行 [`/clear`](https://code.claude.com/docs/zh-TW/commands#all-commands) 也會重設計數。如果仍然可以產生 subagent 的工作（例如執行中的工作流程）在清除後存留，計數則會延續。

在使用 `-p` 的[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)以及 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 中，限制是以每個回合計算，而非每個工作階段。一個回合從您傳送訊息開始，直到 Claude 完成回應為止。當您在那之後傳送下一則訊息，或開始新的 `claude -p` 執行時，限制即會重設，即使使用 [`--continue` 或 `--resume`](https://code.claude.com/docs/zh-TW/headless#continue-conversations) 亦然。若要取得更多搜尋次數，請提高 [`CLAUDE_CODE_MAX_WEB_SEARCHES_PER_SESSION`](https://code.claude.com/docs/zh-TW/env-vars#variables)，或使用 [`CLAUDE_CODE_WEB_SEARCH_REFILLS_PER_HOUR`](https://code.claude.com/docs/zh-TW/env-vars#variables) 設定回補速率。

## Write 工具行為

Write 工具會建立新檔案或以提供的完整內容覆寫現有檔案。它不會附加或合併。Write 也會覆寫位元組無法解碼的現有檔案，並將新內容儲存為 UTF-8，如[非 UTF-8 檔案](#non-utf-8-files)中所述。

Claude 是否必須在目前對話中讀取現有檔案後才能覆寫該檔案，取決於模型和檔案：

* Claude Opus 4.6、Claude Haiku 4.5 和較舊的模型始終需要讀取，因此對未讀取的現有檔案進行 Write 會失敗並出現錯誤。
* 較新的模型可以在與[讀取前編輯](#edit-tool-behavior)相同的條件下覆寫他們在此工作階段中從未讀取的檔案：讀取它不需要權限提示，且 Read 工具可用。
* Jupyter 筆記本和 Claude 僅部分讀取且帶有[`PARTIAL view` 通知](#large-files)的檔案，在每個模型上都需要讀取。

此限制不適用於新檔案。在 v2.1.228 之前，每個模型都需要在覆寫現有檔案前進行讀取。

使用 Bash 檢視檔案也滿足此要求，遵循[編輯工具行為](#edit-tool-behavior)中描述的相同規則。

對於現有檔案的部分變更，Claude 使用 Edit 而不是 Write。

## 檢查哪些工具可用

您的確切工具集取決於您的提供者、平台和設定。若要檢查在執行中的工作階段中載入了什麼，請直接詢問 Claude：

```text theme={null}
What tools do you have access to?
```

Claude 提供對話摘要。如需確切的 MCP 工具名稱，請執行 `/mcp`。

> [!NOTE]
>
> [advisor tool](https://code.claude.com/docs/zh-TW/advisor.md) 是一個 [server tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/advisor-tool)，由 API 執行，而不是 Claude Code 實作的工具。它沒有您可以在權限規則或 hook 匹配器中參考的名稱。

## 另請參閱

* [MCP servers](https://code.claude.com/docs/zh-TW/mcp.md)：透過連接外部伺服器新增自訂工具
* [權限](https://code.claude.com/docs/zh-TW/permissions.md)：權限系統、規則語法和工具特定模式
* [Subagents](https://code.claude.com/docs/zh-TW/sub-agents.md)：為 subagents 設定工具存取
* [Hooks](https://code.claude.com/docs/zh-TW/hooks-guide.md)：在工具執行前後執行自訂命令

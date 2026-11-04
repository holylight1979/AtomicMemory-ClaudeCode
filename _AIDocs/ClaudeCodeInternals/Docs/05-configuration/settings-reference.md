<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/settings-reference | lastmod: 2026-11-04 | section: Configuration / Settings -->
> 來源：https://code.claude.com/docs/zh-TW/settings-reference（官方 zh-TW，lastmod 2026-11-04）｜分類：Configuration › Settings｜EN 摘要：Complete reference for every Claude Code settings.json key: where each one goes, its type and default, and a paste-ready example, with an index of every key.

# 所有設定

> Claude Code settings.json 的完整參考：每個鍵的位置、類型和預設值，以及隨時可貼上的範例，包含每個鍵的索引。

[Back to index](#all-settings)

本參考頁面列出 Claude Code 從設定檔讀取的每個鍵，以及它保存在 `~/.claude.json` 中的[簡短鍵組](#global-config-settings)。若要選擇檔案或檢查優先順序，請從[設定檔和優先順序](https://code.claude.com/docs/zh-TW/settings.md)開始。

## 設定索引

下方每個鍵都連結至其條目。範圍列出該鍵可放置的[檔案](https://code.claude.com/docs/zh-TW/settings.md#settings-files-and-who-they-affect)：`使用者` 是 `~/.claude/settings.json`，`專案` 是 `.claude/settings.json`，`本機` 是 `.claude/settings.local.json`，而 `受管` 是[您的組織所部署的內容](https://code.claude.com/docs/zh-TW/managed-settings.md)。`任何檔案` 表示以上四者皆可，而 `全域設定` 表示 [`~/.claude.json`](#global-config-settings)。

| Key | Description | Topic | Scope |
| :- | :- | :- | :- |
| [`advisorModel`](#advisormodel) | 選擇當 Claude 詢問 [advisor 工具](https://code.claude.com/docs/zh-TW/advisor.md)時由哪個模型回答 | 模型與回應 | 任何檔案 |
| [`agent`](#agent) | 讓每個工作階段都以具名的 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 啟動，並使用其提示詞、工具和模型 | Agent、工作階段與 worktree | 任何檔案 |
| [`agentPushNotifEnabled`](#agentpushnotifenabled) | 讓 Claude 在其決定時[傳送推播通知至您的手機](https://code.claude.com/docs/zh-TW/remote-control.md#mobile-push-notifications) | 遠端、桌面與通知 | 任何檔案 |
| [`allowAllClaudeAiMcps`](#allowallclaudeaimcps) | 在已部署 [`managed-mcp.json`](https://code.claude.com/docs/zh-TW/managed-mcp#exclusive-control-with-managed-mcp-json) 的情況下，仍載入 Claude Code 自行擷取的 [claude.ai 連接器](https://code.claude.com/docs/zh-TW/mcp.md) | MCP | 受管 |
| [`allowClaudeInChromeWithManagedMcp`](#allowclaudeinchromewithmanagedmcp) | 在已部署 [`managed-mcp.json`](https://code.claude.com/docs/zh-TW/managed-mcp#exclusive-control-with-managed-mcp-json) 的情況下，仍讓內建的 [Claude in Chrome](https://code.claude.com/docs/zh-TW/chrome.md) 伺服器執行 | MCP | 受管 |
| [`allowedChannelPlugins`](#allowedchannelplugins) | 取代可推送訊息之[頻道外掛](https://code.claude.com/docs/zh-TW/channels.md#restrict-which-channel-plugins-can-run)的預設允許清單 | 外掛與 skill | 受管 |
| [`allowedHttpHookUrls`](#allowedhttphookurls) | 限制 [HTTP hook](https://code.claude.com/docs/zh-TW/hooks.md) 可以指向哪些 URL | Hook 與自動化 | 任何檔案 |
| [`allowedMcpServers`](#allowedmcpservers) | 以允許清單限定使用者可以新增哪些 [MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md) | MCP | 任何檔案 |
| [`allowedProviders`](#allowedproviders) | 限制機器可以使用哪些 [API 供應商](https://code.claude.com/docs/zh-TW/third-party-integrations.md) | 身分驗證與供應商 | 受管 |
| [`allowManagedHooksOnly`](#allowmanagedhooksonly) | 僅執行您的組織所部署的 [hook](https://code.claude.com/docs/zh-TW/hooks.md) | Hook 與自動化 | 受管 |
| [`allowManagedMcpServersOnly`](#allowmanagedmcpserversonly) | 讓受管的 [MCP](https://code.claude.com/docs/zh-TW/mcp.md) 允許清單成為唯一適用的允許清單 | MCP | 受管 |
| [`allowManagedPermissionRulesOnly`](#allowmanagedpermissionrulesonly) | 讓[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)成為[權限規則](https://code.claude.com/docs/zh-TW/permissions.md#managed-settings)的唯一設定來源 | 權限設定 | 受管 |
| [`alwaysThinkingEnabled`](#alwaysthinkingenabled) | 為每個工作階段關閉[延伸思考](https://code.claude.com/docs/zh-TW/model-config.md#extended-thinking) | 模型與回應 | 任何檔案 |
| [`apiKeyHelper`](#apikeyhelper) | 使用您自己的命令產生 [API 憑證](https://code.claude.com/docs/zh-TW/authentication.md#credential-management) | 身分驗證與供應商 | 任何檔案 |
| [`askUserQuestionTimeout`](#askuserquestiontimeout) | 讓未回答的問題在閒置一段時間後[自動繼續](https://code.claude.com/docs/zh-TW/tools-reference.md#question-auto-continue-timeout) | 介面與終端機 | 使用者或受管 |
| [`appendPlugins`](#appendplugins) | 在使用者安裝的每個 mod 之後執行您組織的 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md) | 外掛與 skill | 使用者或受管 |
| [`attribution`](#attribution) | 自訂 Claude Code 加入提交和 pull request 的署名 | Git 與署名 | 任何檔案 |
| [`attribution.commit`](#attribution-commit) | 變更或隱藏 Claude Code 加入提交的 trailer | Git 與署名 | 任何檔案 |
| [`attribution.pr`](#attribution-pr) | 變更或隱藏 pull request 說明中的署名行 | Git 與署名 | 任何檔案 |
| [`attribution.sessionUrl`](#attribution-sessionurl) | 從[雲端](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)和 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 提交中省略 claude.ai 工作階段連結 | Git 與署名 | 任何檔案 |
| [`autoCompactEnabled`](#autocompactenabled) | 關閉或開啟[自動壓縮](https://code.claude.com/docs/zh-TW/context-window.md) | 記憶與上下文 | 任何檔案 |
| [`autoCompactWindow`](#autocompactwindow) | 設定上下文填滿到什麼程度時 Claude Code 會進行[壓縮](https://code.claude.com/docs/zh-TW/context-window.md) | 記憶與上下文 | 任何檔案 |
| [`autoConnectIde`](#autoconnectide) | 從外部終端機自動連線至執行中的 [VS Code](https://code.claude.com/docs/zh-TW/vs-code.md) 或 [JetBrains](https://code.claude.com/docs/zh-TW/jetbrains.md#from-external-terminals) IDE | 全域設定項目 | 全域設定 |
| [`autoContinueAtUsageLimit`](#autocontinueatusagelimit) | 在開啟的工作階段中等待，並在 claude.ai 用量上限重設後[自動繼續工作](https://code.claude.com/docs/zh-TW/interactive-mode.md#wait-for-a-usage-limit-to-reset) | 介面與終端機 | 使用者或受管 |
| [`autoInstallIdeExtension`](#autoinstallideextension) | 讓 `/ide` 從外部終端機安裝 [IDE 擴充功能](https://code.claude.com/docs/zh-TW/vs-code.md#install-the-extension) | 全域設定項目 | 全域設定 |
| [`autoMemoryDirectory`](#automemorydirectory) | 將[自動記憶](https://code.claude.com/docs/zh-TW/memory.md#auto-memory)儲存在您選擇的目錄中 | 記憶與上下文 | 任何檔案 |
| [`autoMemoryEnabled`](#automemoryenabled) | 關閉或開啟[自動記憶](https://code.claude.com/docs/zh-TW/memory.md#auto-memory) | 記憶與上下文 | 任何檔案 |
| [`autoMode`](#automode) | 將您自己的允許和拒絕規則加入[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)分類器 | 權限設定 | 使用者或受管 |
| [`autoMode.classifyAllShell`](#automode-classifyallshell) | 將每個 shell 命令都送交[自動模式分類器](https://code.claude.com/docs/zh-TW/permission-modes.md#what-the-classifier-blocks-by-default)，即使是符合範圍狹窄之允許規則的命令也一樣 | 權限設定 | 使用者或受管 |
| [`autoScrollEnabled`](#autoscrollenabled) | 在全螢幕呈現中[跟隨新輸出](https://code.claude.com/docs/zh-TW/fullscreen.md#auto-follow)捲動至底部 | 介面與終端機 | 任何檔案 |
| [`autoUpdatesChannel`](#autoupdateschannel) | 跟隨 stable [發布通道](https://code.claude.com/docs/zh-TW/setup.md#configure-release-channel)，而非 latest | 更新與版本 | 任何檔案 |
| [`availableModels`](#availablemodels) | [限制使用者可以選擇哪些模型](https://code.claude.com/docs/zh-TW/model-config.md#restrict-model-selection) | 模型與回應 | 任何檔案 |
| [`availableModelsMatch`](#availablemodelsmatch) | 讓每個 `availableModels` 模型 ID 項目[僅允許其所指名的版本](https://code.claude.com/docs/zh-TW/model-config.md#block-specific-models-or-versions) | 模型與回應 | 受管 |
| [`awaySummaryEnabled`](#awaysummaryenabled) | 關閉您回到終端機時顯示的[工作階段回顧](https://code.claude.com/docs/zh-TW/interactive-mode.md#session-recap) | 遠端、桌面與通知 | 任何檔案 |
| [`awsAuthRefresh`](#awsauthrefresh) | 使用您自己的命令重新整理 `.aws` 中已過期的 [Bedrock 憑證](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#advanced-credential-configuration) | 身分驗證與供應商 | 任何檔案 |
| [`awsCredentialExport`](#awscredentialexport) | 從您自己的命令以 JSON 提供 [Bedrock 憑證](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#advanced-credential-configuration) | 身分驗證與供應商 | 任何檔案 |
| [`axScreenReader`](#axscreenreader) | 呈現[適合螢幕閱讀器的輸出](https://code.claude.com/docs/zh-TW/accessibility.md) | 介面與終端機 | 使用者或受管 |
| [`bashEditDiffEnabled`](#basheditdiffenabled) | 在每種權限模式中記錄 [Bash 命令執行期間變更的檔案](https://code.claude.com/docs/zh-TW/hooks.md#bash) | 介面與終端機 | 使用者或受管 |
| [`bashOutputMaxChars`](#bashoutputmaxchars) | 設定 Claude 以內嵌方式接收多少成功命令的[輸出](https://code.claude.com/docs/zh-TW/tools-reference.md#output-limits) | 記憶與上下文 | 任何檔案 |
| [`blockedMarketplaces`](#blockedmarketplaces) | 為您的組織封鎖[外掛市集](https://code.claude.com/docs/zh-TW/plugins/overview.md)來源 | 外掛與 skill | 受管 |
| [`browserExternalPageTools`](#browserexternalpagetools) | 讓 Claude 的工具不作用於[桌面版](https://code.claude.com/docs/zh-TW/desktop.md)瀏覽器窗格中的外部頁面 | 工具 | 受管 |
| [`channelsEnabled`](#channelsenabled) | 為您的組織允許[頻道](https://code.claude.com/docs/zh-TW/channels.md#enable-channels-for-your-organization) | 外掛與 skill | 受管 |
| [`claudeInChromeDefaultEnabled`](#claudeinchromedefaultenabled) | 在互動式 CLI 和 VS Code 擴充功能中，於工作階段開始時開啟 [Chrome 整合](https://code.claude.com/docs/zh-TW/chrome.md) | 全域設定項目 | 全域設定 |
| [`claudeMd`](#claudemd) | 從受管設定注入全組織的 [CLAUDE.md](https://code.claude.com/docs/zh-TW/memory.md#deploy-organization-wide-claude-md) 指令 | 記憶與上下文 | 受管 |
| [`claudeMdExcludes`](#claudemdexcludes) | 在載入記憶時略過特定的 [CLAUDE.md](https://code.claude.com/docs/zh-TW/memory.md#exclude-specific-claude-md-files) 檔案 | 記憶與上下文 | 任何檔案 |
| [`cleanupPeriodDays`](#cleanupperioddays) | 選擇 Claude Code 在刪除[逐字稿](https://code.claude.com/docs/zh-TW/data-usage.md#data-retention)前保留多少天 | 隱私與遙測 | 任何檔案 |
| [`companyAnnouncements`](#companyannouncements) | 在啟動時顯示您組織的公告 | 介面與終端機 | 任何檔案 |
| [`copyFullResponse`](#copyfullresponse) | 讓 [`/copy`](https://code.claude.com/docs/zh-TW/commands) 直接複製完整回應而不顯示選擇器 | 全域設定項目 | 全域設定 |
| [`copyOnSelect`](#copyonselect) | 關閉在[全螢幕呈現](https://code.claude.com/docs/zh-TW/fullscreen.md#use-the-mouse)和 agent 檢視中自動複製您以滑鼠選取的文字 | 全域設定項目 | 全域設定 |
| [`crossSessionInbound`](#crosssessioninbound) | 選擇 Claude Code 要傳遞[來自您其他工作階段的訊息](https://code.claude.com/docs/zh-TW/cross-session-messaging.md#control-inbound-messages)、僅顯示通知而不傳遞，或是拒絕這些訊息 | Agent、工作階段與 worktree | 任何檔案 |
| [`defaultShell`](#defaultshell) | 選擇由 Bash 或 PowerShell 執行您以 [`!` 前綴](https://code.claude.com/docs/zh-TW/interactive-mode#shell-mode-with-prefix)輸入的 shell 命令 | 介面與終端機 | 任何檔案 |
| [`defaultToAgentsView`](#defaulttoagentsview) | 在不帶引數執行 `claude` 時開啟 [agent 檢視](https://code.claude.com/docs/zh-TW/agent-view.md)，而非新的對話 | 全域設定項目 | 全域設定 |
| [`deniedMcpServers`](#deniedmcpservers) | 依 URL、命令或名稱封鎖特定的 [MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md) | MCP | 任何檔案 |
| [`deniedModels`](#deniedmodels) | [封鎖特定模型](https://code.claude.com/docs/zh-TW/model-config.md#block-specific-models-or-versions)，即使是 `availableModels` 所允許的模型也一樣 | 模型與回應 | 受管 |
| [`desktopSessionCleanupPeriodDays`](#desktopsessioncleanupperioddays) | 以天數設定 [Claude Desktop 和 Cowork 逐字稿](https://code.claude.com/docs/zh-TW/claude-directory.md#cleaned-up-automatically)的保留期限 | 隱私與遙測 | 使用者或受管 |
| [`dialogExpiry`](#dialogexpiry) | 設定 Claude Code 等待 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 或 SDK 主機回應轉送的對話方塊多久之後取消該對話方塊 | 介面與終端機 | 使用者或受管 |
| [`diffTool`](#difftool) | 選擇 Claude 提議的檔案變更要在 [VS Code](https://code.claude.com/docs/zh-TW/vs-code.md) 或 [JetBrains](https://code.claude.com/docs/zh-TW/jetbrains.md#features) 差異檢視器中開啟，還是留在終端機中 | 全域設定項目 | 全域設定 |
| [`disableAgentView`](#disableagentview) | 關閉背景 agent 和 [agent 檢視](https://code.claude.com/docs/zh-TW/agent-view.md) | Agent、工作階段與 worktree | 任何檔案 |
| [`disableAllHooks`](#disableallhooks) | 一次關閉 [hook](https://code.claude.com/docs/zh-TW/hooks.md)、自訂[狀態列](https://code.claude.com/docs/zh-TW/statusline.md)和自訂 [`@` 檔案建議](https://code.claude.com/docs/zh-TW/interactive-mode#quick-commands)命令 | Hook 與自動化 | 任何檔案 |
| [`disableArtifact`](#disableartifact) | 已棄用；請使用 `enableArtifact` 關閉 [Artifact 工具](https://code.claude.com/docs/zh-TW/artifacts.md) | 遠端、桌面與通知 | 任何檔案 |
| [`disableAutoMode`](#disableautomode) | 從權限模式循環中移除[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode) | 權限設定 | 任何檔案 |
| [`disableBrowserExternalNavigation`](#disablebrowserexternalnavigation) | 將使用者和 Claude 在[桌面版](https://code.claude.com/docs/zh-TW/desktop.md)瀏覽器窗格中的存取限制為 localhost | 工具 | 受管 |
| [`disableBundledSkills`](#disablebundledskills) | 關閉 Claude Code 隨附的 [skill](https://code.claude.com/docs/zh-TW/skills.md#bundled-skills) 和[工作流程](https://code.claude.com/docs/zh-TW/workflows.md) | 外掛與 skill | 任何檔案 |
| [`disableClaudeAiConnectors`](#disableclaudeaiconnectors) | 關閉 [claude.ai 連接器](https://code.claude.com/docs/zh-TW/mcp.md#disable-claude-ai-connectors)，讓 Claude Code 不擷取它們 | MCP | 任何檔案 |
| [`disableCommandPluginSources`](#disablecommandpluginsources) | 封鎖透過執行市集所宣告之命令來安裝的[外掛](https://code.claude.com/docs/zh-TW/plugins/overview.md) | 外掛與 skill | 受管 |
| [`disableDeepLinkRegistration`](#disabledeeplinkregistration) | 阻止 Claude Code 註冊 [`claude-cli://` 處理常式](https://code.claude.com/docs/zh-TW/deep-links) | 遠端、桌面與通知 | 任何檔案 |
| [`disableDesktopLocalSessions`](#disabledesktoplocalsessions) | 關閉在裝置上執行的 [Desktop Code 工作階段](https://code.claude.com/docs/zh-TW/desktop.md#local-sessions-on-managed-devices)，僅保留透過 SSH 連線至其他主機和雲端的方式 | 遠端、桌面與通知 | 受管 |
| [`disabledMcpjsonServers`](#disabledmcpjsonservers) | 拒絕專案 [`.mcp.json`](https://code.claude.com/docs/zh-TW/mcp#project-scope) 中的特定伺服器 | MCP | 任何檔案 |
| [`disableMobileSimulatorTools`](#disablemobilesimulatortools) | 在[桌面版](https://code.claude.com/docs/zh-TW/desktop.md) iOS Simulator 窗格中封鎖 Claude 的工具 | 工具 | 受管 |
| [`disableRemoteControl`](#disableremotecontrol) | 在所有可啟動 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 的地方將其關閉 | 遠端、桌面與通知 | 任何檔案 |
| [`disableSideloadFlags`](#disablesideloadflags) | 拒絕側載[外掛](https://code.claude.com/docs/zh-TW/plugins/overview.md)、[subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 和 [MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md)的 CLI 旗標 | 企業與受管設定 | 受管 |
| [`disableSkillShellExecution`](#disableskillshellexecution) | 阻止 [skill](https://code.claude.com/docs/zh-TW/skills.md) 和自訂命令執行內嵌 shell | 外掛與 skill | 任何檔案 |
| [`disableWorkflows`](#disableworkflows) | 為所有人關閉[動態工作流程](https://code.claude.com/docs/zh-TW/workflows.md)；若只針對您自己，請使用 `enableWorkflows` | Hook 與自動化 | 任何檔案 |
| [`editorMode`](#editormode) | 在輸入提示中使用 [vim 按鍵繫結](https://code.claude.com/docs/zh-TW/interactive-mode.md#vim-editor-mode) | 介面與終端機 | 任何檔案 |
| [`effortLevel`](#effortlevel) | 為沒有自己儲存之等級的模型設定預設 [effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level) | 模型與回應 | 任何檔案 |
| [`emojiCompletionEnabled`](#emojicompletionenabled) | 關閉提示輸入中的 [`:shortcode:` 表情符號建議與取代](https://code.claude.com/docs/zh-TW/interactive-mode#emoji-shortcodes) | 介面與終端機 | 任何檔案 |
| [`enableAllProjectMcpServers`](#enableallprojectmcpservers) | 不經提示即核准專案 [`.mcp.json`](https://code.claude.com/docs/zh-TW/mcp#project-server-approvals-and-workspace-trust) 檔案中的每個伺服器 | MCP | 任何檔案 |
| [`enableArtifact`](#enableartifact) | 在任何檔案中設為 `false` 即可關閉 [Artifact 工具](https://code.claude.com/docs/zh-TW/artifacts.md)；任何檔案都無法將其重新開啟 | 遠端、桌面與通知 | 任何檔案 |
| [`enabledMcpjsonServers`](#enabledmcpjsonservers) | 核准專案 [`.mcp.json`](https://code.claude.com/docs/zh-TW/mcp#project-server-approvals-and-workspace-trust) 中的特定伺服器 | MCP | 任何檔案 |
| [`enabledPlugins`](#enabledplugins) | 依範圍開啟或關閉個別[外掛](https://code.claude.com/docs/zh-TW/plugins/overview.md) | 外掛與 skill | 任何檔案 |
| [`enableWorkflows`](#enableworkflows) | 相對於您方案的預設值，開啟或關閉[動態工作流程](https://code.claude.com/docs/zh-TW/workflows.md) | Hook 與自動化 | 任何檔案 |
| [`enforceAvailableModels`](#enforceavailablemodels) | 讓 [`/model` 的 Default 選項](https://code.claude.com/docs/zh-TW/model-config#enforce-the-allowlist-for-the-default-model)維持在您的 `availableModels` 允許清單之內 | 模型與回應 | 任何檔案 |
| [`env`](#env) | 為每個工作階段及其子程序設定[環境變數](https://code.claude.com/docs/zh-TW/env-vars.md#in-settings-files) | 記憶與上下文 | 任何檔案 |
| [`externalEditorContext`](#externaleditorcontext) | 當您按下 [Ctrl+G](https://code.claude.com/docs/zh-TW/interactive-mode.md#general-controls) 進行編輯時，以註解形式顯示 Claude 的最後一個回應 | 全域設定項目 | 全域設定 |
| [`extraKnownMarketplaces`](#extraknownmarketplaces) | 為儲存庫或組織註冊[市集](https://code.claude.com/docs/zh-TW/plugins/overview.md) | 外掛與 skill | 任何檔案 |
| [`fallbackModel`](#fallbackmodel) | 指定主要模型過載時使用的[備用模型](https://code.claude.com/docs/zh-TW/model-config.md#fallback-model-chains) | 模型與回應 | 任何檔案 |
| [`fastMode`](#fastmode) | 在可用的工作階段中開啟[快速模式](https://code.claude.com/docs/zh-TW/fast-mode.md) | 模型與回應 | 任何檔案 |
| [`fastModePerSessionOptIn`](#fastmodepersessionoptin) | 要求使用者在每個工作階段中各自開啟[快速模式](https://code.claude.com/docs/zh-TW/fast-mode.md) | 模型與回應 | 任何檔案 |
| [`feedbackDrafts`](#feedbackdrafts) | 控制 Claude 是否將[意見回饋草稿](https://code.claude.com/docs/zh-TW/tools-reference.md#sendfeedback-tool-behavior)排入佇列供您檢閱 | 隱私與遙測 | 使用者或受管 |
| [`feedbackSurveyRate`](#feedbacksurveyrate) | 變更[工作階段品質調查](https://code.claude.com/docs/zh-TW/data-usage.md#session-quality-surveys)出現的頻率 | 隱私與遙測 | 任何檔案 |
| [`fileCheckpointingEnabled`](#filecheckpointingenabled) | 關閉或開啟 [`/rewind`](https://code.claude.com/docs/zh-TW/checkpointing) 所還原的檔案快照 | 記憶與上下文 | 任何檔案 |
| [`fileSuggestion`](#filesuggestion) | 從您自己的命令提供 [`@` 檔案自動完成](https://code.claude.com/docs/zh-TW/interactive-mode#quick-commands) | 介面與終端機 | 任何檔案 |
| [`footerLinksRegexes`](#footerlinksregexes) | 將輸出中的 issue 或審查 ID 轉為輸入框下方的[可點擊連結](https://code.claude.com/docs/zh-TW/statusline.md#clickable-links) | 介面與終端機 | 使用者或受管 |
| [`forceLoginGatewayUrl`](#forcelogingatewayurl) | 設定登入畫面所連線的[閘道 URL](https://code.claude.com/docs/zh-TW/claude-apps-gateway#set-the-gateway-url) | 身分驗證與供應商 | 使用者或受管 |
| [`forceLoginMethod`](#forceloginmethod) | 將[登入限制](https://code.claude.com/docs/zh-TW/authentication.md#restrict-login-to-your-organization)為 claude.ai、Claude Console 或[雲端閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway) | 身分驗證與供應商 | 任何檔案 |
| [`forceLoginOrgUUID`](#forceloginorguuid) | [將 claude.ai 登入固定至您的組織](https://code.claude.com/docs/zh-TW/authentication.md#restrict-login-to-your-organization)；僅受管來源會強制執行此設定 | 身分驗證與供應商 | 任何檔案 |
| [`forceRemoteSettingsRefresh`](#forceremotesettingsrefresh) | 封鎖啟動，直到完成重新擷取最新的[伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)為止 | 企業與受管設定 | 受管 |
| [`gatewayInternalNetworks`](#gatewayinternalnetworks) | 讓 `/login` 能連線至位於您組織內部使用之公用 IPv4 位址空間上的[雲端閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway#allow-a-gateway-on-public-address-space-you-own) | 身分驗證與供應商 | 受管 |
| [`gcpAuthRefresh`](#gcpauthrefresh) | 使用您自己的命令重新整理 [Google Cloud 憑證](https://code.claude.com/docs/zh-TW/google-vertex-ai.md#advanced-credential-configuration) | 身分驗證與供應商 | 任何檔案 |
| [`hooks`](#hooks) | 在 Claude Code 生命週期的特定時間點，以 [hook](https://code.claude.com/docs/zh-TW/hooks.md) 形式執行您自己的命令 | Hook 與自動化 | 任何檔案 |
| [`httpHookAllowedEnvVars`](#httphookallowedenvvars) | 限制 [HTTP hook](https://code.claude.com/docs/zh-TW/hooks.md) 可以將哪些環境變數放入標頭 | Hook 與自動化 | 任何檔案 |
| [`idleCompaction`](#idlecompaction) | 阻止 Claude Code 壓縮您已暫時離開的冗長對話 | 記憶與上下文 | 任何檔案 |
| [`includeCoAuthoredBy`](#includecoauthoredby) | 已棄用；請使用 `attribution` 隱藏或變更提交和 PR 署名 | Git 與署名 | 任何檔案 |
| [`includeGitInstructions`](#includegitinstructions) | 從 Claude 的上下文中移除內建的提交和 PR 指令 | Git 與署名 | 任何檔案 |
| [`inputNeededNotifEnabled`](#inputneedednotifenabled) | 在 Claude 等待您時收到[推播通知](https://code.claude.com/docs/zh-TW/remote-control.md#mobile-push-notifications) | 遠端、桌面與通知 | 任何檔案 |
| [`isolatePeerMachines`](#isolatepeermachines) | 在 Claude [傳送訊息給您在另一台機器上的工作階段](https://code.claude.com/docs/zh-TW/cross-session-messaging.md#require-approval-for-cross-machine-messages)之前先詢問您 | Agent、工作階段與 worktree | 任何檔案 |
| [`keybindingFlavor`](#keybindingflavor) | 已棄用且不再有作用；文字編輯快捷鍵一律[遵循 readline 慣例](https://code.claude.com/docs/zh-TW/interactive-mode.md#make-ctrl-w-delete-back-to-whitespace) | 介面與終端機 | 任何檔案 |
| [`language`](#language) | 讓 Claude 以英文以外的語言回應 | 模型與回應 | 任何檔案 |
| [`leftArrowOpensAgents`](#leftarrowopensagents) | 關閉[將工作階段移至背景並開啟 agent 檢視](https://code.claude.com/docs/zh-TW/agent-view.md#switch-sessions-without-leaving-the-terminal)的 `←` 快捷鍵 | 全域設定項目 | 全域設定 |
| [`managedMcpServers`](#managedmcpservers) | 除了使用者自行新增的伺服器之外，再為每位使用者提供遠端 [MCP 伺服器](https://code.claude.com/docs/zh-TW/managed-mcp.md#provide-servers-through-managed-settings) | MCP | 受管 |
| [`managedSourcesBehavior`](#managedsourcesbehavior) | 組合您部署的每個[受管來源](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)，而非僅使用優先順序最高的來源 | 企業與受管設定 | 受管 |
| [`maxEffortLevel`](#maxeffortlevel) | 在每個供應商上，為所有模型或個別模型設定 [effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)上限 | 模型與回應 | 任何檔案 |
| [`maxProseWidth`](#maxprosewidth) | 在寬終端機中限制 Claude 回應中文字段落的最大寬度 | 介面與終端機 | 任何檔案 |
| [`minimumVersion`](#minimumversion) | 防止[自動更新](https://code.claude.com/docs/zh-TW/setup.md#pin-a-minimum-version)安裝低於某個版本的任何版本 | 更新與版本 | 任何檔案 |
| [`model`](#model) | 變更 Claude Code 啟動時使用的[模型](https://code.claude.com/docs/zh-TW/model-config.md#set-a-default-model-for-new-sessions) | 模型與回應 | 任何檔案 |
| [`modelOverrides`](#modeloverrides) | 將[模型 ID 對應](https://code.claude.com/docs/zh-TW/model-config.md#override-model-ids-per-version)至您供應商的 ID，例如 Bedrock ARN | 模型與回應 | 任何檔案 |
| [`modelPicker`](#modelpicker) | 選擇 [`/model` 選擇器](https://code.claude.com/docs/zh-TW/model-config#available-models)要列出哪些模型，並使用您自己的順序和標籤 | 模型與回應 | 使用者或受管 |
| [`modelPricing`](#modelpricing) | 以您組織的合約費率而非牌價回報花費 | 模型與回應 | 受管 |
| [`modelSettings`](#modelsettings) | 為每個模型保留已儲存的 [effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)或[自動壓縮視窗](https://code.claude.com/docs/zh-TW/model-config.md#set-the-auto-compact-window)，或為某個模型設定 effort 上限 | 模型與回應 | 任何檔案 |
| [`otelHeadersHelper`](#otelheadershelper) | 使用您自己的命令產生輪替的 [OpenTelemetry](https://code.claude.com/docs/zh-TW/monitoring-usage.md#dynamic-headers) 標頭 | 身分驗證與供應商 | 任何檔案 |
| [`outputStyle`](#outputstyle) | 以[輸出風格](https://code.claude.com/docs/zh-TW/output-styles.md)變更 Claude 的角色、語氣和輸出格式 | 模型與回應 | 任何檔案 |
| [`parentSettingsBehavior`](#parentsettingsbehavior) | 在您部署[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)時，套用或捨棄 [SDK 或 IDE 主機](https://code.claude.com/docs/zh-TW/managed-settings.md#let-an-embedding-host-add-policy)所傳遞的限制 | 企業與受管設定 | 受管 |
| [`permissionExplainerEnabled`](#permissionexplainerenabled) | 已於 v2.1.257 移除，連同 shell 權限提示上的 `Ctrl+E` 命令說明一併移除 | 全域設定項目 | 全域設定 |
| [`permissions`](#permissions) | 設定允許、詢問和拒絕規則，以及起始[權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md) | 權限設定 | 任何檔案 |
| [`permissions.additionalDirectories`](#permissions-additionaldirectories) | 讓 Claude 能存取[目前目錄以外之目錄](https://code.claude.com/docs/zh-TW/permissions.md#working-directories)中的檔案 | 權限設定 | 任何檔案 |
| [`permissions.allow`](#permissions-allow) | 不經提示即核准列出的[工具使用](https://code.claude.com/docs/zh-TW/permissions.md#permission-rule-syntax) | 權限設定 | 任何檔案 |
| [`permissions.ask`](#permissions-ask) | 在列出的[工具使用](https://code.claude.com/docs/zh-TW/permissions.md#permission-rule-syntax)之前一律提示 | 權限設定 | 任何檔案 |
| [`permissions.blockReadsOutsideWorkingDirectories`](#permissions-blockreadsoutsideworkingdirectories) | 讓檔案工具在每種權限模式下都拒絕讀取[工作目錄](https://code.claude.com/docs/zh-TW/permissions.md#working-directories)以外的內容 | 權限設定 | 任何檔案 |
| [`permissions.blockWritesOutsideWorkingDirectories`](#permissions-blockwritesoutsideworkingdirectories) | 讓 `Write`、`Edit` 和 `NotebookEdit` 工具在每種權限模式下都拒絕[工作目錄](https://code.claude.com/docs/zh-TW/permissions.md#working-directories)以外的路徑，但 [Claude Code 本身的部分檔案](#what-the-write-block-refuses-and-what-stays-writable)除外 | 權限設定 | 任何檔案 |
| [`permissions.defaultMode`](#permissions-defaultmode) | 設定新工作階段起始時的[權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md#which-mode-a-session-starts-in) | 權限設定 | 任何檔案 |
| [`permissions.deny`](#permissions-deny) | 封鎖列出的[工具使用](https://code.claude.com/docs/zh-TW/permissions.md#permission-rule-syntax)，包括讀取存放機密的檔案 | 權限設定 | 任何檔案 |
| [`permissions.disableBypassPermissionsMode`](#permissions-disablebypasspermissionsmode) | 防止任何人進入 [bypassPermissions 模式](https://code.claude.com/docs/zh-TW/permission-modes.md#skip-all-checks-with-bypasspermissions-mode) | 權限設定 | 任何檔案 |
| [`plansDirectory`](#plansdirectory) | 選擇 [plan mode](https://code.claude.com/docs/zh-TW/permission-modes.md#analyze-before-you-edit-with-plan-mode) 寫入計畫檔案的位置 | 記憶與上下文 | 任何檔案 |
| [`pluginConfigs`](#pluginconfigs) | 儲存您在[外掛](https://code.claude.com/docs/zh-TW/plugins/overview.md)設定對話方塊中提供的答案 | 外掛與 skill | 使用者或受管 |
| [`pluginSuggestionMarketplaces`](#pluginsuggestionmarketplaces) | 選擇哪些[市集](https://code.claude.com/docs/zh-TW/plugins/org.md#restrict-what-users-can-install)可以在 `/plugin` 中顯示外掛安裝建議 | 外掛與 skill | 受管 |
| [`pluginTrustMessage`](#plugintrustmessage) | 在[外掛](https://code.claude.com/docs/zh-TW/plugins/overview.md)信任警告中加入您自己的文字 | 外掛與 skill | 受管 |
| [`policyHelper`](#policyhelper) | 在啟動時執行計算[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md#compute-the-policy-with-a-helper-program)的可執行檔 | 企業與受管設定 | 受管 |
| [`policyHelper.path`](#policyhelper-path) | 指定 Claude Code 執行的[輔助可執行檔](https://code.claude.com/docs/zh-TW/managed-settings.md#compute-the-policy-with-a-helper-program) | 企業與受管設定 | 受管 |
| [`policyHelper.refreshIntervalMs`](#policyhelper-refreshintervalms) | 依間隔在背景重新執行[輔助程式](https://code.claude.com/docs/zh-TW/managed-settings.md#compute-the-policy-with-a-helper-program) | 企業與受管設定 | 受管 |
| [`policyHelper.timeoutMs`](#policyhelper-timeoutms) | 設定 Claude Code 等待[輔助程式](https://code.claude.com/docs/zh-TW/managed-settings.md#compute-the-policy-with-a-helper-program)的時間 | 企業與受管設定 | 受管 |
| [`preferredNotifChannel`](#preferrednotifchannel) | 選擇工作完成時使用[終端機鈴聲或桌面通知](https://code.claude.com/docs/zh-TW/terminal-config.md#get-a-terminal-bell-or-notification) | 遠端、桌面與通知 | 任何檔案 |
| [`prefersReducedMotion`](#prefersreducedmotion) | [減少或關閉](https://code.claude.com/docs/zh-TW/accessibility.md#accessibility-settings)旋轉指示器、微光和閃爍動畫 | 介面與終端機 | 任何檔案 |
| [`prependPlugins`](#prependplugins) | 在使用者安裝的每個 mod 之前執行您組織的 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md) | 外掛與 skill | 使用者或受管 |
| [`processWrapper`](#processwrapper) | 在 macOS 和 Linux 上透過[企業啟動器](https://code.claude.com/docs/zh-TW/corporate-launcher.md)執行 Claude Code 的背景程序 | Agent、工作階段與 worktree | 使用者或受管 |
| [`promptCacheTtl`](#promptcachettl) | 選擇主要對話的[提示快取存留期](https://code.claude.com/docs/zh-TW/prompt-caching.md#cache-lifetime) | 模型與回應 | 任何檔案 |
| [`promptSuggestionEnabled`](#promptsuggestionenabled) | 隱藏輸入框中灰色的[提示詞建議](https://code.claude.com/docs/zh-TW/interactive-mode.md#prompt-suggestions) | 介面與終端機 | 任何檔案 |
| [`prStatusFooterEnabled`](#prstatusfooterenabled) | 關閉提示頁尾的 [PR 審查狀態](https://code.claude.com/docs/zh-TW/interactive-mode.md#pr-review-status)徽章及其背後的 pull request 檢查 | 全域設定項目 | 全域設定 |
| [`prUrlTemplate`](#prurltemplate) | 將 PR 連結指向內部程式碼審查工具，而非 github.com | Git 與署名 | 任何檔案 |
| [`remote.defaultEnvironmentId`](#remote-defaultenvironmentid) | 為 `claude --cloud` 選擇預設的[雲端環境](https://code.claude.com/docs/zh-TW/cloud-environments.md)；自行託管的 `ccpool_` ID 僅會從使用者設定、受管設定和 `--settings` 讀取 | 遠端、桌面與通知 | 任何檔案 |
| [`remoteControlAtStartup`](#remotecontrolatstartup) | 在工作階段開始時自動連線 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md#enable-remote-control-for-all-sessions) | 遠端、桌面與通知 | 任何檔案 |
| [`requiredMaximumVersion`](#requiredmaximumversion) | 在版本比您組織允許的版本更新時[拒絕啟動](https://code.claude.com/docs/zh-TW/setup.md#pin-a-minimum-version) | 更新與版本 | 受管 |
| [`requiredMinimumVersion`](#requiredminimumversion) | 在版本比您組織要求的版本更舊時[拒絕啟動](https://code.claude.com/docs/zh-TW/setup.md#pin-a-minimum-version) | 更新與版本 | 受管 |
| [`respectGitignore`](#respectgitignore) | 讓被 gitignore 的檔案不出現在 [`@` 檔案選擇器](https://code.claude.com/docs/zh-TW/interactive-mode#quick-commands)中 | 介面與終端機 | 任何檔案 |
| [`respondToBashCommands`](#respondtobashcommands) | 阻止 Claude 在 [`!` shell 命令](https://code.claude.com/docs/zh-TW/interactive-mode#shell-mode-with-prefix)執行後回應 | 介面與終端機 | 任何檔案 |
| [`sandbox`](#sandbox) | 在 macOS、Linux 和 WSL2 上[將 Bash 命令與您的檔案系統和網路隔離](https://code.claude.com/docs/zh-TW/sandboxing.md) | 沙箱設定 | 任何檔案 |
| [`sandbox.allowAppleEvents`](#sandbox-allowappleevents) | 讓[沙箱中](https://code.claude.com/docs/zh-TW/sandboxing.md)的命令在 macOS 上傳送 Apple Events | 沙箱設定 | 使用者或受管 |
| [`sandbox.allowNestedUserNamespaces`](#sandbox-allownestedusernamespaces) | 讓[沙箱中](https://code.claude.com/docs/zh-TW/sandboxing.md#chromium-or-rootless-podman-fails-inside-the-sandbox-on-linux)的命令在 Linux 和 WSL2 上建立使用者命名空間 | 沙箱設定 | 使用者或受管 |
| [`sandbox.allowUnsandboxedCommands`](#sandbox-allowunsandboxedcommands) | 讓 Claude 在[沙箱](https://code.claude.com/docs/zh-TW/sandboxing.md#the-unsandboxed-retry-escape-hatch)外重試被封鎖的命令，或禁止此行為 | 沙箱設定 | 任何檔案 |
| [`sandbox.autoAllowBashIfSandboxed`](#sandbox-autoallowbashifsandboxed) | 不經權限提示即執行[沙箱中](https://code.claude.com/docs/zh-TW/sandboxing.md#auto-allow-mode)的命令 | 沙箱設定 | 任何檔案 |
| [`sandbox.bwrapPath`](#sandbox-bwrappath) | 將[沙箱](https://code.claude.com/docs/zh-TW/sandboxing.md)指向 `PATH` 以外的 bubblewrap 二進位檔 | 沙箱設定 | 受管 |
| [`sandbox.credentials`](#sandbox-credentials) | 在[沙箱](https://code.claude.com/docs/zh-TW/sandboxing.md#protect-credentials)內隱藏或遮蔽憑證檔案和變數 | 沙箱設定 | 任何檔案 |
| [`sandbox.credentials.allowPlaintextInject`](#sandbox-credentials-allowplaintextinject) | 讓[已遮蔽的憑證](https://code.claude.com/docs/zh-TW/sandboxing.md#mask-credentials)能在受信任的測試網路上傳送至純 HTTP 服務 | 沙箱設定 | 使用者或受管 |
| [`sandbox.credentials.awsPairs`](#sandbox-credentials-awspairs) | 將自訂名稱的 AWS 金鑰變數連結為單一憑證以進行[重新簽署](https://code.claude.com/docs/zh-TW/sandboxing.md#re-sign-aws-requests) | 沙箱設定 | 使用者或受管 |
| [`sandbox.credentials.envVars`](#sandbox-credentials-envvars) | 在[沙箱](https://code.claude.com/docs/zh-TW/sandboxing.md#mask-environment-variables)內取消設定或遮蔽環境變數 | 沙箱設定 | 任何檔案 |
| [`sandbox.credentials.files`](#sandbox-credentials-files) | 在[沙箱](https://code.claude.com/docs/zh-TW/sandboxing.md#mask-credential-files)內封鎖或遮蔽對憑證檔案的讀取 | 沙箱設定 | 任何檔案 |
| [`sandbox.credentials.sigv4`](#sandbox-credentials-sigv4) | 選擇串流、預先簽署或 [SigV4A AWS 請求](https://code.claude.com/docs/zh-TW/sandboxing.md#re-sign-aws-requests)要失敗還是直接通過 | 沙箱設定 | 使用者或受管 |
| [`sandbox.enabled`](#sandbox-enabled) | 在 macOS、Linux 和 WSL2 上開啟 [Bash 沙箱機制](https://code.claude.com/docs/zh-TW/sandboxing.md#get-started) | 沙箱設定 | 任何檔案 |
| [`sandbox.enableWeakerNestedSandbox`](#sandbox-enableweakernestedsandbox) | 在非特權容器內執行 Linux [沙箱](https://code.claude.com/docs/zh-TW/sandboxing.md) | 沙箱設定 | 任何檔案 |
| [`sandbox.enableWeakerNetworkIsolation`](#sandbox-enableweakernetworkisolation) | 在 macOS 上讓 `gh`、`gcloud` 和 `terraform` 能在[沙箱](https://code.claude.com/docs/zh-TW/sandboxing.md#go-based-clis-fail-tls-verification-on-macos)內的 MITM 代理伺服器後方驗證 TLS | 沙箱設定 | 任何檔案 |
| [`sandbox.excludedCommands`](#sandbox-excludedcommands) | 指定 Claude Code 可以在[沙箱](https://code.claude.com/docs/zh-TW/sandboxing.md)外執行的命令 | 沙箱設定 | 任何檔案 |
| [`sandbox.failIfUnavailable`](#sandbox-failifunavailable) | 在[沙箱](https://code.claude.com/docs/zh-TW/sandboxing.md)無法啟動時拒絕啟動，而非在沒有沙箱的情況下執行 | 沙箱設定 | 任何檔案 |
| [`sandbox.filesystem`](#sandbox-filesystem) | 控制[沙箱中](https://code.claude.com/docs/zh-TW/sandboxing.md#filesystem-isolation)的命令可以讀取和寫入哪些路徑 | 沙箱設定 | 任何檔案 |
| [`sandbox.filesystem.allowManagedReadPathsOnly`](#sandbox-filesystem-allowmanagedreadpathsonly) | 阻止開發人員重新開放[您組織所封鎖的讀取路徑](https://code.claude.com/docs/zh-TW/sandboxing.md#keep-developers-from-widening-the-policy) | 沙箱設定 | 受管 |
| [`sandbox.filesystem.allowRead`](#sandbox-filesystem-allowread) | 在 [`denyRead`](#sandbox-filesystem-denyread) 封鎖的區域內重新開放讀取 | 沙箱設定 | 任何檔案 |
| [`sandbox.filesystem.allowWrite`](#sandbox-filesystem-allowwrite) | 新增[沙箱中](https://code.claude.com/docs/zh-TW/sandboxing.md)的命令可以寫入的路徑 | 沙箱設定 | 任何檔案 |
| [`sandbox.filesystem.denyRead`](#sandbox-filesystem-denyread) | 封鎖[沙箱中](https://code.claude.com/docs/zh-TW/sandboxing.md)的命令讀取特定路徑 | 沙箱設定 | 任何檔案 |
| [`sandbox.filesystem.denyWrite`](#sandbox-filesystem-denywrite) | 封鎖[沙箱中](https://code.claude.com/docs/zh-TW/sandboxing.md)的命令寫入特定路徑 | 沙箱設定 | 任何檔案 |
| [`sandbox.filesystem.disabled`](#sandbox-filesystem-disabled) | [關閉檔案系統隔離](https://code.claude.com/docs/zh-TW/sandboxing.md#disable-filesystem-isolation)，同時保留網路隔離 | 沙箱設定 | 使用者或受管 |
| [`sandbox.ignoreViolations`](#sandbox-ignoreviolations) | 針對命令預期會探查的路徑，不顯示違規報告 | 沙箱設定 | 任何檔案 |
| [`sandbox.network`](#sandbox-network) | 控制[沙箱中](https://code.claude.com/docs/zh-TW/sandboxing.md#network-isolation)的命令可以連線至哪些主機、連接埠和通訊端 | 沙箱設定 | 任何檔案 |
| [`sandbox.network.allowAllUnixSockets`](#sandbox-network-allowallunixsockets) | 讓[沙箱中](https://code.claude.com/docs/zh-TW/sandboxing.md)的命令連線至所有 Unix 通訊端 | 沙箱設定 | 任何檔案 |
| [`sandbox.network.allowedDomains`](#sandbox-network-alloweddomains) | 預先允許網域，讓[沙箱中](https://code.claude.com/docs/zh-TW/sandboxing.md)的命令不會為其提示 | 沙箱設定 | 任何檔案 |
| [`sandbox.network.allowLocalBinding`](#sandbox-network-allowlocalbinding) | 在 macOS 上讓[沙箱中](https://code.claude.com/docs/zh-TW/sandboxing.md)的命令監聽網路連接埠並連線至 localhost | 沙箱設定 | 任何檔案 |
| [`sandbox.network.allowMachLookup`](#sandbox-network-allowmachlookup) | 讓 macOS 上[沙箱中](https://code.claude.com/docs/zh-TW/sandboxing.md)的工具（例如 iOS Simulator 或 Playwright）能連線至其 XPC 服務 | 沙箱設定 | 任何檔案 |
| [`sandbox.network.allowManagedDomainsOnly`](#sandbox-network-allowmanageddomainsonly) | 將網路允許清單鎖定為[受管設定](https://code.claude.com/docs/zh-TW/sandboxing.md#keep-developers-from-widening-the-policy) | 沙箱設定 | 受管 |
| [`sandbox.network.allowUnixSockets`](#sandbox-network-allowunixsockets) | 列出在 macOS 上[沙箱中](https://code.claude.com/docs/zh-TW/sandboxing.md)的命令可以使用的 Unix 通訊端路徑 | 沙箱設定 | 任何檔案 |
| [`sandbox.network.deniedDomains`](#sandbox-network-denieddomains) | 為[沙箱中](https://code.claude.com/docs/zh-TW/sandboxing.md)的命令封鎖網域，即使該網域位於允許的萬用字元範圍內也一樣 | 沙箱設定 | 任何檔案 |
| [`sandbox.network.httpProxyPort`](#sandbox-network-httpproxyport) | 透過您自己的代理伺服器路由[沙箱](https://code.claude.com/docs/zh-TW/sandboxing.md#custom-proxy-configuration)的 HTTP 流量 | 沙箱設定 | 任何檔案 |
| [`sandbox.network.socksProxyPort`](#sandbox-network-socksproxyport) | 透過您自己的代理伺服器路由[沙箱](https://code.claude.com/docs/zh-TW/sandboxing.md#custom-proxy-configuration)的 SOCKS 流量 | 沙箱設定 | 任何檔案 |
| [`sandbox.network.strictAllowlist`](#sandbox-network-strictallowlist) | 拒絕[允許清單](https://code.claude.com/docs/zh-TW/sandboxing.md#network-isolation)以外的主機，而非提示 | 沙箱設定 | 使用者或受管 |
| [`sandbox.network.tlsTerminate`](#sandbox-network-tlsterminate) | 讓[沙箱](https://code.claude.com/docs/zh-TW/sandboxing.md#network-isolation)代理伺服器終止 TLS，以便讀取 HTTPS 請求 | 沙箱設定 | 使用者或受管 |
| [`sandbox.ripgrep`](#sandbox-ripgrep) | 在[沙箱](https://code.claude.com/docs/zh-TW/sandboxing.md)內使用您自己的 ripgrep 二進位檔 | 沙箱設定 | 使用者或受管 |
| [`sandbox.socatPath`](#sandbox-socatpath) | 將[沙箱](https://code.claude.com/docs/zh-TW/sandboxing.md)代理伺服器指向 `PATH` 以外的 `socat` 二進位檔 | 沙箱設定 | 受管 |
| [`showClearContextOnPlanAccept`](#showclearcontextonplanaccept) | 在[計畫接受畫面](https://code.claude.com/docs/zh-TW/permission-modes.md#review-and-approve-a-plan)上顯示「清除上下文」選項 | 介面與終端機 | 任何檔案 |
| [`showThinkingSummaries`](#showthinkingsummaries) | 查看 Claude [思考](https://code.claude.com/docs/zh-TW/model-config.md#extended-thinking)的摘要，而非摺疊的簡短標示 | 模型與回應 | 任何檔案 |
| [`showTurnDuration`](#showturnduration) | 隱藏每個回應後的「Cooked for」持續時間 | 介面與終端機 | 任何檔案 |
| [`skillListingBudgetFraction`](#skilllistingbudgetfraction) | 為 [skill 清單](https://code.claude.com/docs/zh-TW/skills.md#skill-descriptions-are-cut-short)保留更多或更少的上下文 | 記憶與上下文 | 任何檔案 |
| [`skillListingMaxDescChars`](#skilllistingmaxdescchars) | 限制 [skill 清單](https://code.claude.com/docs/zh-TW/skills.md#skill-descriptions-are-cut-short)中每個 skill 的說明長度 | 記憶與上下文 | 任何檔案 |
| [`skillOverrides`](#skilloverrides) | 無須編輯 SKILL.md 即可[隱藏或摺疊 skill](https://code.claude.com/docs/zh-TW/skills.md#override-skill-visibility-from-settings) | 外掛與 skill | 任何檔案 |
| [`skipAutoPermissionPrompt`](#skipautopermissionprompt) | 略過您首次自行（而非透過內建預設值）進入[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)時 Claude Code 所顯示的一次性通知 | 權限設定 | 使用者或受管 |
| [`skipDangerousModePermissionPrompt`](#skipdangerousmodepermissionprompt) | 略過進入 [bypassPermissions 模式](https://code.claude.com/docs/zh-TW/permission-modes.md#skip-all-checks-with-bypasspermissions-mode)前的確認對話方塊 | 權限設定 | 使用者、本機或受管 |
| [`skipWebFetchPreflight`](#skipwebfetchpreflight) | 在無法連線至 Anthropic 時略過 [WebFetch 主機名稱檢查](https://code.claude.com/docs/zh-TW/tools-reference.md#webfetch-tool-behavior) | 隱私與遙測 | 任何檔案 |
| [`spellcheck`](#spellcheck) | 使用您安裝的[拼字檢查工具](https://code.claude.com/docs/zh-TW/interactive-mode.md#check-spelling-as-you-type)，在提示輸入中為拼錯的字加上底線 | 介面與終端機 | 使用者或受管 |
| [`spinnerTipsEnabled`](#spinnertipsenabled) | 在 Claude 工作時隱藏旋轉指示器中的提示 | 介面與終端機 | 任何檔案 |
| [`spinnerTipsOverride`](#spinnertipsoverride) | 將您自己的提示加入旋轉指示器的輪播，或取代內建提示 | 介面與終端機 | 任何檔案 |
| [`spinnerVerbs`](#spinnerverbs) | 新增或取代回合執行期間顯示的動詞 | 介面與終端機 | 任何檔案 |
| [`sshConfigs`](#sshconfigs) | 將 [SSH 連線](https://code.claude.com/docs/zh-TW/desktop.md#pre-configure-ssh-connections-for-your-team)加入 Desktop 環境選擇器 | 遠端、桌面與通知 | 使用者或受管 |
| [`sshHostAllowlist`](#sshhostallowlist) | 限制 [Desktop SSH 工作階段](https://code.claude.com/docs/zh-TW/desktop.md#restrict-which-ssh-hosts-users-can-connect-to)可以連線至哪些主機 | 遠端、桌面與通知 | 受管 |
| [`sshHostCommands`](#sshhostcommands) | 將[主機來自命令的 SSH 連線](https://code.claude.com/docs/zh-TW/desktop.md#create-an-ssh-connection-from-a-command)加入 Desktop 環境選擇器 | 遠端、桌面與通知 | 使用者或受管 |
| [`statusLine`](#statusline) | 執行您自己的命令，在提示下方呈現[狀態列](https://code.claude.com/docs/zh-TW/statusline.md) | 介面與終端機 | 任何檔案 |
| [`strictKnownMarketplaces`](#strictknownmarketplaces) | 以允許清單限定使用者可以新增並從中安裝的[市集](https://code.claude.com/docs/zh-TW/plugins/overview.md)來源 | 外掛與 skill | 受管 |
| [`strictPluginOnlyCustomization`](#strictpluginonlycustomization) | 封鎖來自使用者和專案來源的 [skill](https://code.claude.com/docs/zh-TW/skills.md)、[agent](https://code.claude.com/docs/zh-TW/sub-agents.md)、[hook](https://code.claude.com/docs/zh-TW/hooks.md) 和 [MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md) | 外掛與 skill | 受管 |
| [`strictPluginOnlyCustomization.agents`](#strictpluginonlycustomization-agents) | 將 [agent](https://code.claude.com/docs/zh-TW/sub-agents.md) 鎖定為外掛和受管來源 | 外掛與 skill | 受管 |
| [`strictPluginOnlyCustomization.hooks`](#strictpluginonlycustomization-hooks) | 將 [hook](https://code.claude.com/docs/zh-TW/hooks.md) 鎖定為外掛和受管來源 | 外掛與 skill | 受管 |
| [`strictPluginOnlyCustomization.mcp`](#strictpluginonlycustomization-mcp) | 將 [MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md)鎖定為外掛和受管來源 | 外掛與 skill | 受管 |
| [`strictPluginOnlyCustomization.skills`](#strictpluginonlycustomization-skills) | 將 [skill](https://code.claude.com/docs/zh-TW/skills.md) 鎖定為外掛和受管來源 | 外掛與 skill | 受管 |
| [`subagentPromptCacheTtl`](#subagentpromptcachettl) | 選擇 subagent 及主要對話以外其他請求的[提示快取存留期](https://code.claude.com/docs/zh-TW/prompt-caching.md#cache-lifetime) | 模型與回應 | 任何檔案 |
| [`subagentStatusLine`](#subagentstatusline) | 使用您自己的命令改寫 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 工作顯示中的列 | 介面與終端機 | 任何檔案 |
| [`switchModelsOnFlag`](#switchmodelsonflag) | 在[安全分類器](https://code.claude.com/docs/zh-TW/model-config.md#ask-before-switching)標記請求時自動切換模型或暫停 | 模型與回應 | 任何檔案 |
| [`syncClaudeAiPlugins`](#syncclaudeaiplugins) | 停止載入[在您 claude.ai 帳戶上啟用的外掛](https://code.claude.com/docs/zh-TW/plugins/loading.md#synced-plugins)，並停止下載新的外掛 | 外掛與 skill | 使用者、本機或受管 |
| [`syncClaudeAiSkills`](#syncclaudeaiskills) | 停止載入[在您 claude.ai 帳戶上啟用的 skill](https://code.claude.com/docs/zh-TW/skills.md#how-synced-skills-behave)，並停止下載新的 skill | 外掛與 skill | 使用者、本機或受管 |
| [`syntaxHighlightingDisabled`](#syntaxhighlightingdisabled) | 關閉差異和程式碼區塊中的語法醒目提示 | 介面與終端機 | 任何檔案 |
| [`taskOutputMaxChars`](#taskoutputmaxchars) | 已於 v2.1.277 移除，連同其所設定大小的 `TaskOutput` 工具一併移除 | 記憶與上下文 | 任何檔案 |
| [`teammateDefaultModel`](#teammatedefaultmodel) | 已於 v2.1.234 移除；關於 Claude Code 如何選擇隊員的模型，請參閱[指定隊員與模型](https://code.claude.com/docs/zh-TW/agent-teams.md#specify-teammates-and-models) | 全域設定項目 | 全域設定 |
| [`teammateMode`](#teammatemode) | 選擇 [agent team 隊員的顯示方式](https://code.claude.com/docs/zh-TW/agent-teams.md#choose-a-display-mode) | Agent、工作階段與 worktree | 任何檔案 |
| [`terminalProgressBarEnabled`](#terminalprogressbarenabled) | 在支援終端機進度列的終端機中將其隱藏 | 介面與終端機 | 任何檔案 |
| [`terminalTitleFromRename`](#terminaltitlefromrename) | 阻止 [`/rename`](https://code.claude.com/docs/zh-TW/sessions#name-your-sessions) 和 `--name` 變更終端機分頁標題 | 介面與終端機 | 任何檔案 |
| [`theme`](#theme) | 選擇介面的[色彩主題](https://code.claude.com/docs/zh-TW/terminal-config.md#match-the-color-theme)，可為內建或自訂 | 介面與終端機 | 任何檔案 |
| [`timeFormat`](#timeformat) | 以 12 小時制或 24 小時制、UTC 或 strftime 格式顯示介面中的時間 | 介面與終端機 | 任何檔案 |
| [`timeZone`](#timezone) | 以系統時區以外的時區顯示介面中的時間 | 介面與終端機 | 任何檔案 |
| [`tui`](#tui) | 選擇[全螢幕](https://code.claude.com/docs/zh-TW/fullscreen.md)或傳統終端機呈現器 | 介面與終端機 | 任何檔案 |
| [`ultracode`](#ultracode) | 讓 Claude 無須要求即為每項實質工作規劃[工作流程](https://code.claude.com/docs/zh-TW/workflows.md#let-claude-decide-with-ultracode) | 模型與回應 | 任何檔案 |
| [`useAutoModeDuringPlan`](#useautomodeduringplan) | 讓[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)分類器在 [plan mode](https://code.claude.com/docs/zh-TW/permission-modes.md#analyze-before-you-edit-with-plan-mode) 中審查 shell 命令；設為 `false` 則改為顯示提示 | 權限設定 | 使用者、本機或受管 |
| [`verbose`](#verbose) | 顯示[完整的工具輸出](https://code.claude.com/docs/zh-TW/cli-reference.md#cli-flags)，而非截斷的摘要；若兩者皆有設定，則 `viewMode` 優先 | 介面與終端機 | 任何檔案 |
| [`viewMode`](#viewmode) | 讓每個工作階段以[預設、詳細或專注檢視](https://code.claude.com/docs/zh-TW/cli-reference.md#cli-flags)啟動 | 介面與終端機 | 任何檔案 |
| [`vimInsertModeRemaps`](#viminsertmoderemaps) | 將雙鍵 [INSERT 模式序列](https://code.claude.com/docs/zh-TW/interactive-mode.md#remap-insert-mode-key-sequences)（例如 `jj`）對應至 Escape | 介面與終端機 | 使用者或受管 |
| [`voice`](#voice) | 開啟[語音聽寫](https://code.claude.com/docs/zh-TW/voice-dictation.md)並選擇按住或輕觸模式 | 介面與終端機 | 任何檔案 |
| [`voiceEnabled`](#voiceenabled) | 以較舊的單一鍵形式開啟[語音聽寫](https://code.claude.com/docs/zh-TW/voice-dictation.md) | 介面與終端機 | 任何檔案 |
| [`wheelScrollAccelerationEnabled`](#wheelscrollaccelerationenabled) | 在全螢幕呈現中關閉[滑鼠滾輪加速](https://code.claude.com/docs/zh-TW/fullscreen.md#mouse-wheel-scrolling) | 介面與終端機 | 任何檔案 |
| [`workflowKeywordTriggerEnabled`](#workflowkeywordtriggerenabled) | 讓提示詞中的 `ultracode` 一詞啟動[工作流程](https://code.claude.com/docs/zh-TW/workflows.md)；設為 `false` 即可輸入該詞而不啟動工作流程 | Hook 與自動化 | 任何檔案 |
| [`workflowSizeGuideline`](#workflowsizeguideline) | 設定 Claude 在[動態工作流程](https://code.claude.com/docs/zh-TW/workflows.md)中目標的 agent 數量 | Hook 與自動化 | 任何檔案 |
| [`worktree`](#worktree) | 設定 Claude Code 建立 git [worktree](https://code.claude.com/docs/zh-TW/worktrees.md) 的方式 | Agent、工作階段與 worktree | 任何檔案 |
| [`worktree.baseRef`](#worktree-baseref) | 從遠端預設分支或您的本機 HEAD 建立新 [worktree](https://code.claude.com/docs/zh-TW/worktrees.md) 的分支 | Agent、工作階段與 worktree | 任何檔案 |
| [`worktree.bgIsolation`](#worktree-bgisolation) | 讓背景工作階段不使用 [worktree](https://code.claude.com/docs/zh-TW/worktrees.md) 即可編輯工作副本 | Agent、工作階段與 worktree | 任何檔案 |
| [`worktree.location`](#worktree-location) | 選擇 [Desktop SSH 工作階段](https://code.claude.com/docs/zh-TW/desktop.md#ssh-sessions)在遠端機器上建立其 worktree 的位置 | Agent、工作階段與 worktree | 使用者 |
| [`worktree.sparsePaths`](#worktree-sparsepaths) | 在每個 [worktree](https://code.claude.com/docs/zh-TW/worktrees.md) 中僅簽出您需要的目錄 | Agent、工作階段與 worktree | 任何檔案 |
| [`worktree.symlinkDirectories`](#worktree-symlinkdirectories) | 以符號連結將大型目錄連結至每個 [worktree](https://code.claude.com/docs/zh-TW/worktrees.md)，而非複製它們 | Agent、工作階段與 worktree | 任何檔案 |
| [`wslInheritsWindowsSettings`](#wslinheritswindowssettings) | 讓 WSL 從 Windows 原則鏈讀取[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md) | 企業與受管設定 | 受管 |

## 模型與回應

選擇 Claude Code 使用哪些模型以及其回應方式。關於這些設定如何與 `/model` 命令及環境變數互動，請參閱[模型設定](https://code.claude.com/docs/zh-TW/model-config.md)。

### `advisorModel`

選擇當 Claude 呼叫伺服器端 [advisor 工具](https://code.claude.com/docs/zh-TW/advisor.md)時由哪個模型回答。取消設定即可關閉 advisor。advisor 的能力必須至少與您的主要模型相當。請參閱[選擇 advisor 模型](https://code.claude.com/docs/zh-TW/advisor.md#choose-an-advisor-model)，了解可接受的組合，以及選擇不被接受的組合時會發生什麼情況。

通常不需要手動編輯此鍵。執行 `/advisor` 會開啟一個選擇器，顯示目前的選擇、可擔任 advisor 的模型，以及 **No advisor**。Claude Code 會將您的選擇儲存到 `~/.claude/settings.json` 中的此鍵。如果您是從 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 用戶端，或在連接至遠端 worker 的工作階段中進行選擇，該選擇僅套用於該工作階段，不會變更此鍵。

如果您的帳戶需要[用量點數同意](https://code.claude.com/docs/zh-TW/advisor.md#fable-advisor-and-usage-credits)，請先執行 `/model fable` 接受同意。在您接受之前，於 `/advisor` 中選擇 Fable 不會儲存任何內容，且 Claude Code 會提示您先執行 `/model fable`。

* **範圍**：[`Any file`](#scopes)
* **類型**：字串，為別名 `"fable"`、`"opus"` 或 `"sonnet"` 之一（會解析為 Claude Code 目前該模型系列的預設版本），或完整的模型 ID，例如 `"claude-opus-5-5"`
* **預設值**：未設定，因此 advisor 為關閉狀態
* **每個工作階段的覆寫**：`--advisor` 在單一工作階段中優先於此鍵。[`CLAUDE_CODE_DISABLE_ADVISOR_TOOL`](https://code.claude.com/docs/zh-TW/env-vars) 會關閉 advisor，且此鍵無法將其重新開啟

```json settings.json theme={null}
{
  "advisorModel": "opus"
}
```

在 advisor [無法使用](https://code.claude.com/docs/zh-TW/advisor.md#requirements)的供應商上，此鍵不會產生作用，例如 Amazon Bedrock 和 Claude Platform on AWS。`"fable"` 需要 [Fable 存取權](https://code.claude.com/docs/zh-TW/advisor.md#choose-an-advisor-model)。

### `alwaysThinkingEnabled`

將此設為 `false`，即可在每個工作階段中關閉[延伸思考](https://code.claude.com/docs/zh-TW/model-config.md#extended-thinking)。思考預設為開啟，因此 `true` 不會改變任何事情。大多數人透過 `/config` 設定此項，而不是直接編輯檔案。

在始終進行思考的模型上，例如 Opus 5.5、Sonnet 5.5、Haiku 5.5 以及 Fable 模型，`false` 不會產生作用。在[第三方供應商](https://code.claude.com/docs/zh-TW/third-party-integrations.md)上，Claude Code 會省略 `thinking` 參數而非關閉思考，因此自適應推理模型仍可能進行思考。在 Anthropic API 上關閉思考時，對於 Claude Code 已知[不接受該組合](https://code.claude.com/docs/zh-TW/errors.md#effort-isnt-available-with-thinking-turned-off)的模型（例如 Opus 5），Claude Code 會傳送 effort `high` 而非更高的等級。

* **範圍**：[`Any file`](#scopes)
* **類型**：Boolean
  * `true`：沒有作用；思考已開啟
  * `false`：Claude Code 在每個工作階段中關閉延伸思考
* **預設值**：未設定，因此支援思考的模型會開啟思考
* **每個工作階段的覆寫**：[`MAX_THINKING_TOKENS`](https://code.claude.com/docs/zh-TW/env-vars) 在單一工作階段中優先於此鍵：`0` 會關閉思考，受與 `false` 相同的模型和供應商限制；正值則會開啟思考，即使此鍵為 `false` 亦然。在自適應推理模型上，數值本身會被忽略

```json settings.json theme={null}
{
  "alwaysThinkingEnabled": false
}
```

### `availableModels`

限制使用者可為主要工作階段、[subagent](https://code.claude.com/docs/zh-TW/sub-agents.md)、[skill](https://code.claude.com/docs/zh-TW/skills.md) 以及 [advisor](https://code.claude.com/docs/zh-TW/advisor.md) 選擇哪些模型。受管清單會限制 `/model`、`--model`，以及開發者自己檔案中的 `model` 鍵；清單以外的模型無法被選擇。在預設的前綴比對下，此鍵本身不會影響 Default 選項；若要影響該選項，請搭配 [`enforceAvailableModels`](#enforceavailablemodels) 使用。

* **範圍**：[`Any file`](#scopes)。將其部署於受管設定中，即可為組織強制執行。
* **類型**：模型別名或 ID 的陣列
* **預設值**：未設定，因此所有模型皆可使用

此範例讓使用者只能選擇 Sonnet 和 Haiku 模型：

```json settings.json theme={null}
{
  "availableModels": ["sonnet", "haiku"]
}
```

像 `"claude-opus-5"` 這樣的模型 ID 項目，也會允許延伸自該 ID 的後續版本，例如 Opus 5.5。若要封鎖其中某個版本，請使用 [`deniedModels`](#deniedmodels)。若要讓每個模型 ID 項目只允許其所指定的版本，請使用 [`availableModelsMatch`](#availablemodelsmatch)。請參閱[限制模型選擇](https://code.claude.com/docs/zh-TW/model-config.md#restrict-model-selection)。關於第三方供應商的 ID，請參閱[為第三方部署固定模型](https://code.claude.com/docs/zh-TW/model-config.md#pin-models-for-third-party-deployments)。

### `availableModelsMatch`

選擇 [`availableModels`](#availablemodels) 項目如何比對模型 ID。預設情況下，模型 ID 項目也會允許延伸自該 ID 的後續版本，因此 `"claude-opus-5"` 會允許 Opus 5.5。使用 `"exact"` 時，每個模型 ID 項目只允許其所指定的版本，因此該模型的較新版本在您將其列出之前都會保持封鎖。需要 Claude Code v2.1.283 或更新版本。

* **範圍**：[`Managed`](#scopes)。Claude Code 會忽略使用者、專案及本機設定中以及 `--settings` 中的此鍵，並顯示警告
* **類型**：字串，為下列之一：
  * `"prefix"`：模型 ID 項目允許其版本，以及任何以另一個片段延伸該 ID 的模型 ID
  * `"exact"`：模型 ID 項目只允許其所指定的版本，因此 `"claude-opus-5"` 允許 Opus 5 但不允許 `claude-opus-5-5`。像 `"claude-opus-4-5"` 這樣的項目也會允許其帶日期的 Anthropic 模型 ID `claude-opus-4-5-20251101`。像 `"opus"` 這樣的系列別名仍會允許整個系列，而 `best`、`opusplan` 和 `default` 項目會被忽略
* **預設值**：`"prefix"`

此範例允許 Opus 5 和 Sonnet 5，但不允許兩者的任何後續版本：

```json managed-settings.json theme={null}
{
  "availableModels": ["claude-opus-5", "claude-sonnet-5"],
  "availableModelsMatch": "exact"
}
```

使用 `"exact"` 時，只要清單至少列出一個模型或系列，Default 選項也會被限制在所列出的模型中。請參閱[封鎖特定模型或版本](https://code.claude.com/docs/zh-TW/model-config.md#block-specific-models-or-versions)。

### `deniedModels`

封鎖特定模型，無論是否有 [`availableModels`](#availablemodels) 允許清單，且即使該清單允許這些模型亦然。Claude Code 會在 `/model` 選擇器中隱藏被封鎖的模型，且在任何強制執行 `availableModels` 的地方都無法選擇該模型。使用 Default 選項的工作階段也不會執行被封鎖的模型，如[封鎖特定模型或版本](https://code.claude.com/docs/zh-TW/model-config.md#block-specific-models-or-versions)所述。需要 Claude Code v2.1.283 或更新版本。

* **範圍**：[`Managed`](#scopes)。Claude Code 會忽略使用者、專案及本機設定中以及 `--settings` 中的此鍵，並顯示警告
* **類型**：模型別名或 ID 的陣列
  * 像 `"opus"` 這樣的系列別名會封鎖該系列中的所有模型
  * 像 `"claude-opus-5-5"` 這樣的模型 ID 會封鎖該版本的所有寫法，包括帶日期的 ID 和供應商特定的 ID
  * 沒有次版本號的模型 ID，例如 `"claude-opus-5"`，也會封鎖後續的次版本，例如 Opus 5.5。若只要封鎖 Opus 5，請寫成 `"claude-opus-5-0"`
  * `best`、`opusplan` 和 `default` 項目會被忽略
* **預設值**：未設定，因此不會封鎖任何模型

此範例允許 Opus 和 Sonnet 模型，並封鎖 Opus 5.5：

```json managed-settings.json theme={null}
{
  "availableModels": ["opus", "sonnet"],
  "deniedModels": ["claude-opus-5-5"]
}
```

請參閱[封鎖特定模型或版本](https://code.claude.com/docs/zh-TW/model-config.md#block-specific-models-or-versions)。

### `effortLevel`

為尚未儲存等級的模型設定預設的 [effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)。較低的等級在簡單任務上更快且更便宜，較高的等級則會針對複雜問題進行更深入的推理。

當您在本機的互動式工作階段中執行 `/effort low`、`medium`、`high` 或 `xhigh` 時，Claude Code 會將該等級儲存在 [`modelSettings`](#modelsettings) 中目前使用的模型之下，而不是寫入此鍵。在 v2.1.251 之前，`/effort` 會寫入此鍵。

在同一個設定檔中，Claude Code 會使用模型已儲存的等級，而非此鍵。[`modelSettings`](#modelsettings) 說明了跨檔案的優先順序。

在連接至遠端 worker 的工作階段、`-p` 執行以及 Agent SDK 中，`/effort` 只會套用於該工作階段。[調整 effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)列出了同樣只套用於該工作階段的互動式選擇。`/effort` 所顯示的訊息會說明實際發生的情況。

* **範圍**：[`Any file`](#scopes)
* **類型**：字串，為下列之一：
  * `"low"`：最少的推理，適用於簡短、範圍明確、對延遲敏感且不需要高度智慧的任務
  * `"medium"`：為對成本敏感、可犧牲部分智慧的工作減少 token 使用量
  * `"high"`：在 token 使用量與智慧之間取得平衡
  * `"xhigh"`：以較高的 token 花費進行更深入的推理
* **預設值**：未設定
* **每個工作階段的覆寫**：`--effort` 在單一工作階段中優先於此鍵，而 [`CLAUDE_CODE_EFFORT_LEVEL`](https://code.claude.com/docs/zh-TW/env-vars) 則優先於兩者

```json settings.json theme={null}
{
  "effortLevel": "xhigh"
}
```

在您的使用者設定檔 `~/.claude/settings.json` 中，此鍵是 `/effort` 在依模型儲存等級之前所寫入的舊格式，並會繼續套用於先前套用的地方，即 Opus 5、Fable 5.1 及更早的模型。Opus 5.5 以及在其之後發布的模型會忽略此鍵，並以其自身的預設值開始，直到您為其儲存等級為止，而 `/effort` 會將該等級寫入 [`modelSettings`](#modelsettings) 之下。在專案、本機及受管設定中，以及使用 `--settings` 時，此鍵會套用於所有模型。

### `enforceAvailableModels`

`/model` 選擇器有一個 **Default** 選項，而 [`default` 模型設定](https://code.claude.com/docs/zh-TW/model-config#default-model-setting)描述了它所解析的模型。[`availableModels`](#availablemodels) 允許清單會限制您可以指定的模型，但在預設的[前綴比對](#availablemodelsmatch)下，它不會重新對應您帳戶類型的預設值，因此 **Default** 仍可能解析為清單以外的模型。此鍵可補上這個缺口。需要 Claude Code v2.1.175 或更新版本。

當您的組織部署任何受管設定時，Claude Code 只會從受管來源讀取此鍵，並忽略您其他檔案中的此鍵。

關於此鍵如何套用於啟動時的模型檢查，請參閱 [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#when-your-organization-enforces-a-model-allowlist) 和 [Google Cloud's Agent Platform](https://code.claude.com/docs/zh-TW/google-vertex-ai.md#when-your-organization-enforces-a-model-allowlist)。

* **範圍**：[`Any file`](#scopes)
* **類型**：Boolean
  * `true`：當 **Default** 會解析為 `availableModels` 以外的模型時，Claude Code 會將其解析為清單中第一個可用的模型
  * `false`：此鍵不會改變 **Default** 的解析方式
* **預設值**：`false`

此範例將指定的選擇限制為 Sonnet 和 Haiku 模型，並讓 **Default** 解析為其中第一個可用的模型：

```json settings.json theme={null}
{
  "availableModels": ["sonnet", "haiku"],
  "enforceAvailableModels": true
}
```

當 `availableModels` 未設定或為空時，此鍵不會產生作用。請參閱[為 Default 模型強制執行允許清單](https://code.claude.com/docs/zh-TW/model-config.md#enforce-the-allowlist-for-the-default-model)。需要 Claude Code v2.1.175 或更新版本。

### `fallbackModel`

指定當您的主要模型過載或無法使用時，Claude Code 依序嘗試的備援模型。Claude Code 會在該回合的剩餘部分切換至鏈中下一個可用的模型，並顯示通知。若沒有設定鏈，Claude Code 會重試同一個模型，然後顯示伺服器的錯誤，由您自行重試或切換模型。

一次切換代表在備援模型上會有一個[提示快取](https://code.claude.com/docs/zh-TW/prompt-caching.md#switching-models)為冷狀態的回合；您的下一則訊息會再次先嘗試主要模型。

* **範圍**：[`Any file`](#scopes)
* **類型**：模型別名或 ID 的陣列；`"default"` 會展開為預設模型
* **預設值**：未設定，因此失敗的請求不會在其他模型上重試
* **每個工作階段的覆寫**：`--fallback-model` 在單一工作階段中優先於此鍵

此範例在主要模型失敗時，先嘗試 Sonnet 5，再嘗試 Haiku 4.5：

```json settings.json theme={null}
{
  "fallbackModel": ["claude-sonnet-5", "claude-haiku-4-5"]
}
```

與大多數陣列設定不同，此鍵不會跨設定檔合併：定義此鍵且優先順序最高的檔案會提供整個鏈。如果您的專案檔案設定為 `["claude-sonnet-5"]`，而使用者檔案設定為 `["claude-haiku-4-5"]`，則鏈僅為 `["claude-sonnet-5"]`。Claude Code 最多保留清單中三個不同的允許模型，並忽略其餘模型。請參閱[備援模型鏈](https://code.claude.com/docs/zh-TW/model-config.md#fallback-model-chains)。

### `fastMode`

在可使用[快速模式](https://code.claude.com/docs/zh-TW/fast-mode.md)的工作階段中開啟快速模式，適用於快速迭代或即時除錯等互動式工作，讓您以較高的每 token 成本換取速度。通常不需要手動編輯此鍵：執行 `/fast` 會將 `fastMode: true` 寫入 `~/.claude/settings.json`，再次執行以關閉快速模式則會移除此鍵。快速模式只能在 Opus 5.5、Opus 5 和 Opus 4.8 上執行：從其他模型開啟快速模式會將您切換至 Opus，而切換至不支援的模型則會關閉快速模式。請參閱[在快速模式開啟時切換模型](https://code.claude.com/docs/zh-TW/fast-mode.md#switch-models-while-fast-mode-is-on)。

* **範圍**：[`Any file`](#scopes)
* **類型**：Boolean
  * `true`：Claude Code 在可使用快速模式的工作階段中開啟快速模式
  * `false`：快速模式保持關閉
* **預設值**：未設定，因此快速模式為關閉狀態
* **每個工作階段的覆寫**：[`CLAUDE_CODE_DISABLE_FAST_MODE`](https://code.claude.com/docs/zh-TW/env-vars) 會在單一工作階段中關閉快速模式，且此鍵無法將其重新開啟

```json settings.json theme={null}
{
  "fastMode": true
}
```

### `fastModePerSessionOptIn`

通常，執行 `/fast` 會將 [`fastMode`](#fastmode) 儲存到使用者的使用者設定中，因此在之後每個工作階段開始時快速模式都會開啟。將此鍵設為 `true` 即可停止此行為：已儲存的 `fastMode: true` 不再於工作階段開始時開啟快速模式，每位使用者都必須在需要的每個工作階段中執行 `/fast`。Claude Code 會保留其檔案中的 `fastMode` 鍵，因此關閉此鍵即可恢復舊有行為。

Team 或 Enterprise 方案的擁有者可以透過[伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)在整個組織中部署此鍵。當受管設定設定了此鍵時，`/fast on` 在互動式終端機工作階段以外會被拒絕，並回報您的組織已停用快速模式。這包括[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)、[VS Code 擴充功能](https://code.claude.com/docs/zh-TW/vs-code.md)以及[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)。

* **範圍**：[`Any file`](#scopes)
* **類型**：Boolean
  * `true`：已儲存的 `fastMode: true` 不再於工作階段開始時開啟快速模式，因此每位使用者需在需要的每個工作階段中執行 `/fast`；除非受管設定設定了此鍵，否則透過 `--settings` 傳入的 `fastMode: true` 仍會對該工作階段生效
  * `false`：已儲存的 `fastMode: true` 會在之後每個工作階段開始時開啟快速模式
* **預設值**：`false`

```json settings.json theme={null}
{
  "fastModePerSessionOptIn": true
}
```

請參閱[要求每個工作階段選擇加入](https://code.claude.com/docs/zh-TW/fast-mode.md#require-per-session-opt-in)。

### `language`

讓 Claude 預設以英文以外的語言回應。回應語言沒有固定清單：Claude Code 會將此值原封不動地傳給 Claude，作為始終以該語言回應的指令，因此任何 Claude 能讀懂的語言名稱都可使用。Claude Code 不會檢查此值，因此拼錯的名稱會原樣傳給 Claude，而不會產生錯誤。同一個值也會設定[語音聽寫](https://code.claude.com/docs/zh-TW/voice-dictation.md#change-the-dictation-language)的語言（語音聽寫確實有固定的[支援聽寫語言](https://code.claude.com/docs/zh-TW/voice-dictation.md#change-the-dictation-language)清單），以及自動產生的工作階段標題的語言。

* **範圍**：[`Any file`](#scopes)
* **類型**：字串，任何語言名稱，例如 `"japanese"`、`"spanish"` 或 `"french"`；Claude Code 不會驗證此值
* **預設值**：未設定；此時工作階段標題會與您對話的語言一致

```json settings.json theme={null}
{
  "language": "japanese"
}
```

### `maxEffortLevel`

為工作階段可使用的 [effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)設定上限，較低的等級仍可使用。任何較高的等級都會改以上限執行，包括來自 `/effort`、`/model` 選擇器、`--effort`、[`CLAUDE_CODE_EFFORT_LEVEL`](https://code.claude.com/docs/zh-TW/env-vars)、skill 或 subagent 的 `effort` frontmatter，或模型自身預設值的等級。Claude Code 會在每次請求前自行套用上限，因此在所有供應商上都有效，包括 Amazon Bedrock、Google Cloud's Agent Platform 和 Microsoft Foundry。需要 Claude Code v2.1.267 或更新版本。

* **範圍**：[`Any file`](#scopes)。將其部署於受管設定中，即可為組織強制執行。當多個範圍設定了上限時，會套用最低的上限，因此在某個範圍設定的上限無法從另一個範圍提高
* **類型**：字串，為 `"low"`、`"medium"`、`"high"`、`"xhigh"` 或 `"max"` 之一。`"max"` 值表示不設上限
* **預設值**：未設定，因此不套用任何上限
* **每個模型的上限**：在模型的 [`modelSettings`](#modelsettings) 項目中加入 `maxEffortLevel`。該項目只會在同時設定兩者的設定來源中（例如您的使用者設定或某一個[受管來源](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)），針對該模型取代此鍵。在該處設定 `"max"` 可讓該模型免受該來源的上限限制；Claude Code 仍會套用其他來源的上限

此範例將所有模型的上限設為 `medium`，並讓 Sonnet 4.6 免受限制：

```json settings.json theme={null}
{
  "maxEffortLevel": "medium",
  "modelSettings": {
    "claude-sonnet-4-6": {
      "maxEffortLevel": "max"
    }
  }
}
```

當您的組織也為某個模型設定了 [effort 限制](https://code.claude.com/docs/zh-TW/model-config.md#organization-effort-limits)時，會套用兩個上限中較低者。

### `model`

設定每個新工作階段使用的模型，這樣您就不必每次都用 `/model` 選擇。在此設定不會妨礙您在工作階段中途切換模型。如果您的管理員設定了[組織預設模型](https://code.claude.com/docs/zh-TW/model-config.md#organization-default-model)來覆寫使用者的選擇，即使您在使用者、專案或本機設定中設定了此鍵，您仍會使用該模型。

* **範圍**：[`Any file`](#scopes)
* **類型**：字串，模型別名或完整的模型 ID
* **預設值**：未設定，因此 Claude Code 會使用您帳戶的預設模型
* **每個工作階段的覆寫**：`--model` 優先於 [`ANTHROPIC_MODEL`](https://code.claude.com/docs/zh-TW/env-vars)，而兩者在單一工作階段中都優先於此鍵，包括優先於受管的 `model`；[`availableModels`](#availablemodels) 清單仍會套用於所選模型

```json settings.json theme={null}
{
  "model": "claude-sonnet-5"
}
```

此處的值優先於 [`ANTHROPIC_DEFAULT_MODEL`](https://code.claude.com/docs/zh-TW/model-config#set-a-default-model-for-new-sessions)，Claude Code 只在沒有其他項目選擇模型時才會使用後者。

### `modelOverrides`

將 Anthropic 模型 ID 對應至供應商特定的模型 ID，例如 Amazon Bedrock 推論設定檔 ARN。模型選擇器中的每個項目在呼叫供應商 API 時，就會使用其對應的值。管理員會在 [Amazon Bedrock、Google Cloud's Agent Platform 和 Microsoft Foundry](https://code.claude.com/docs/zh-TW/model-config.md#override-model-ids-per-version) 上使用此設定，將每個模型版本導向特定的推論設定檔、版本名稱或部署，以用於治理、成本分攤或區域路由。

* **範圍**：[`Any file`](#scopes)
* **類型**：將模型 ID 對應至供應商模型 ID 的物件
* **預設值**：未設定

此範例將所有 Opus 4.6 的呼叫導向指定的 Bedrock 推論設定檔：

```json settings.json theme={null}
{
  "modelOverrides": {
    "claude-opus-4-6": "arn:aws:bedrock:us-east-1:123456789012:inference-profile/example"
  }
}
```

請參閱[依版本覆寫模型 ID](https://code.claude.com/docs/zh-TW/model-config.md#override-model-ids-per-version)。

### `modelPicker`

列出 `/model` 選擇器所提供的模型，依您撰寫的順序並使用您選擇的標籤，讓選擇器在內建陣容之後或取代內建陣容，列出您組織所執行的模型。每一列的 `model` 會原封不動地採用，因此它接受任何 `--model` 接受的值：像 `opus` 這樣的別名、Anthropic 模型 ID，或適用於 Amazon Bedrock、Google Cloud's Agent Platform、Microsoft Foundry 或 LLM 閘道的供應商格式 ID。需要 Claude Code v2.1.242 或更新版本。

* **範圍**：[`User or managed`](#scopes)。Claude Code 會從受管設定、`--settings` 和使用者設定讀取此鍵，並忽略專案及本機設定中的此鍵，以免您複製的儲存庫重新標記選擇器。這三者中設定了此鍵且優先順序最高者會提供整個陣容，Claude Code 絕不會合併來自兩個來源的陣容。
* **類型**：包含列組成的 `options` 陣列以及選用的 `replaceBuiltInOptions` Boolean 的物件
* **預設值**：未設定，因此選擇器會顯示內建陣容

此範例在內建陣容之後新增兩個 Bedrock 部署，並使用您團隊認得的名稱：

```json managed-settings.json theme={null}
{
  "modelPicker": {
    "options": [
      { "model": "us.anthropic.claude-opus-4-8", "label": "Opus (production)" },
      {
        "model": "us.anthropic.claude-sonnet-4-6",
        "label": "Sonnet (production)",
        "description": "Day-to-day work"
      }
    ]
  }
}
```

#### `modelPicker` 的欄位

此鍵接受兩個欄位，一個用於列本身，另一個用於決定這些列是取代內建陣容還是加入其中。

| 欄位 | 類型 | 作用 |
| :- | :- | :- |
| `options` | 列的陣列，每一列都有必要的 `model` 以及選用的 `label`、`description` 和 `behavesAs` | 選擇器依此順序顯示的列，但顯示為灰色的列會移至最下方。若沒有 `label`，對於 Claude Code 已知的模型，會以內建名稱作為該列的標題，否則使用模型 ID；若沒有 `description`，則會寫入一般性的第二行 |
| `replaceBuiltInOptions` | Boolean，預設為 `false` | 設為 `true` 時，只會顯示這些列、**Default**，以及工作階段目前正在使用之模型的一列。保持未設定則會將這些列加在內建陣容之後 |

`options` 中的項目也可以在其 `model` 旁加上選用的 `behavesAs` 字串，這需要 v2.1.257 或更新版本。在 `model` 比您的 Claude Code 版本更新的項目上，將其設為您的 Claude Code 版本已知的模型 ID，例如 `claude-opus-4-8`。Claude Code 就會將該已知模型的能力和 effort 預設值套用至該項目，而不是將其模型視為未知。項目的標籤以及 Claude Code 在請求中傳送的模型 ID 不會改變。

開啟 `replaceBuiltInOptions` 時，Claude Code 會隱藏所有其他列：內建陣容、它為 [`availableModels`](#availablemodels) 項目新增的列、[閘道探索](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md#model-discovery)找到的模型，以及 [`ANTHROPIC_CUSTOM_MODEL_OPTION`](https://code.claude.com/docs/zh-TW/model-config#add-a-custom-model-option)。關閉時，Claude Code 會略過內建陣容已涵蓋的列出模型。標籤會改變選擇器顯示的內容，而不會改變 Claude Code 執行的模型。

[`availableModels`](#availablemodels) 允許清單仍會套用於這些列。在將列出的模型加入允許清單之前，請閱讀[合併行為](https://code.claude.com/docs/zh-TW/model-config.md#merge-behavior)：特定的模型 ID 會縮小其系列的萬用字元項目。Claude Code 也會在顯示選擇器之前，針對工作階段檢查每一列：

* **捨棄**：Claude Code 無法提供的列，例如已淘汰的模型，或您的組織沒有存取權的模型
* **顯示為灰色**：您目前尚無法選擇的列，並顯示原因
* **沒有任何列保留**：Claude Code 會保留內建陣容，並如常依允許清單篩選

Claude Code 會捨棄無法解析的列並保留其餘列。請參閱[修正損壞的設定檔](https://code.claude.com/docs/zh-TW/settings.md#fix-a-broken-settings-file)。

### `modelPricing`

以您組織實際支付的費率而非牌價回報花費。當您的組織有合約費率時設定此項，讓開發者看到的金額與您的帳單一致。Claude Code 會在 `/usage`、[狀態列](https://code.claude.com/docs/zh-TW/statusline.md)、Agent SDK 的 `total_cost_usd`、[`--max-budget-usd`](https://code.claude.com/docs/zh-TW/cli-reference) 限制，以及 [OpenTelemetry](https://code.claude.com/docs/zh-TW/monitoring-usage.md) 成本指標和事件中套用這些費率。費率由您提供：Claude Code 不會從您的合約或 Claude Console 讀取。需要 Claude Code v2.1.242 或更新版本。

* **範圍**：[`Managed`](#scopes)。透過伺服器受管設定、MDM 政策、`managed-settings.json` 檔案或[政策輔助程式](https://code.claude.com/docs/zh-TW/managed-settings.md#compute-the-policy-with-a-helper-program)部署此鍵。Claude Code 會忽略使用者、專案及本機設定中、`--settings` 中，以及 Windows 上使用者可寫入的 [HKCU 登錄](https://code.claude.com/docs/zh-TW/managed-settings.md#where-each-mechanism-stores-the-policy)中的此鍵。使用伺服器受管設定時，每個工作階段會以牌價回報成本，直到該工作階段的[設定擷取](https://code.claude.com/docs/zh-TW/server-managed-settings.md#fetch-and-caching-behavior)確認此設定為止。嵌入 Claude Code 並設定 [`CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST`](https://code.claude.com/docs/zh-TW/env-vars) 的主機應用程式，可以透過 SDK 的 [`managedSettings`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#options) 選項提供自己的費率表，Claude Code 只會在沒有受管來源設定此鍵時使用該費率表，且僅限 Claude Code v2.1.246 或更新版本。
* **類型**：包含選用的 `multiplier` 和選用的 `overrides` 對應的物件
* **預設值**：未設定，因此除非主機應用程式提供費率表，否則 Claude Code 會回報牌價

單獨設定 `multiplier` 可套用統一的折扣或加價，單獨設定 `overrides` 可套用各模型的費率，也可兩者都設定。

此範例為 Sonnet 4.6 設定合約費率，然後將所有金額（包括 Sonnet 該列）減少 15%：

```json managed-settings.json theme={null}
{
  "modelPricing": {
    "multiplier": 0.85,
    "overrides": {
      "claude-sonnet-4-6": {
        "input": 2.4,
        "output": 12,
        "cacheRead": 0.24,
        "cacheWrite": 3
      }
    }
  }
}
```

將 `multiplier` 設為大於 1、最高 10 的值，即可將所有金額加價。加價需要 Claude Code v2.1.271 或更新版本。較早的版本會忽略大於 1 的 `multiplier` 並顯示警告，同時保留設定的其餘部分。

關於相關步驟，包括如何確認費率已生效，請參閱[以您的合約費率回報花費](https://code.claude.com/docs/zh-TW/costs.md#report-spend-at-your-contracted-rates)。

#### `modelPricing` 的欄位

| 欄位 | 類型 | 作用 |
| :- | :- | :- |
| `multiplier` | 大於 0 且最多為 10 的數字 | 縮放 Claude Code 計算的每一筆成本，無論是否有 `overrides` 列涵蓋。小於 1 為折扣，大於 1 為加價 |
| `overrides` | 將模型 ID 對應至費率物件的對應，費率物件包含 `input`、`output`、`cacheRead` 和 `cacheWrite`，每項皆為 0 到 10000 | 該模型每百萬 token 的美元費率，四項皆為必要。`cacheWrite` 同時涵蓋五分鐘和一小時的快取寫入。請參閱[一列適用於哪些模型](#which-models-a-modelpricing-row-applies-to) |

Claude Code 會完全依照您撰寫的方式使用一列的費率，不會加上快速模式附加費或[僅限美國推論的費率](https://platform.claude.com/docs/en/about-claude/pricing)。如果您也設定了 `multiplier`，Claude Code 會在該列的費率之上套用它。Claude Code 會捨棄包含無法解析之費率的列，或無法解析的 `multiplier`，並保留其餘部分；請參閱[修正損壞的設定檔](https://code.claude.com/docs/zh-TW/settings.md#fix-a-broken-settings-file)。

#### `modelPricing` 的一列適用於哪些模型

Claude Code 會根據列的鍵來決定該列適用於哪些模型：

* **內建模型的 ID**：Claude Code 本身用於內建模型的鍵，無論該鍵是模型自身的 ID（例如 `claude-sonnet-4-6`），還是其 Bedrock、Agent Platform 或 Foundry ID。Claude Code 會將該列套用至該模型的每個帶日期快照 ID 和供應商特定 ID。
* **任何其他鍵**：不是內建模型 ID 的鍵，例如閘道模型別名。Claude Code 只會將該列套用至那一個 ID。當某個模型 ID 與您的某個鍵完全相符，同時也屬於以內建模型 ID 為鍵的列時，Claude Code 會使用完全相符者。
* **Bedrock 應用程式推論設定檔**：一旦 Claude Code 透過您的 [`modelOverrides`](#modeloverrides) 對應或 [`bedrock:GetInferenceProfile` 查詢](https://code.claude.com/docs/zh-TW/amazon-bedrock#iam-configuration)，將該設定檔解析為其路由到的模型，Claude Code 就會將該模型的列套用至該設定檔。

### `modelSettings`

為您使用的每個模型儲存 [effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)。需要 Claude Code v2.1.251 或更新版本。

在本機的互動式工作階段中，當您使用 `/effort` 或 `/model` 選擇器的 effort 滑桿將 `low`、`medium`、`high` 或 `xhigh` 儲存為預設值時，Claude Code 會將該等級寫入此處您正在使用的模型之下，因此您很少需要自行編輯此鍵。當您在 [VS Code 擴充功能的模型選擇器](https://code.claude.com/docs/zh-TW/vs-code.md#use-the-prompt-box)中選擇其中一個等級時，Claude Code 也會以相同方式將其儲存於此。[`effortLevel`](#effortlevel) 項目列出了 `/effort` 只套用於該工作階段的工作階段。

手動編輯此鍵即可變更或移除您已儲存的等級。

此處模型的 `effortLevel` 優先於同一個設定檔中頂層的 [`effortLevel`](#effortlevel)。跨檔案時，Claude Code 會分別解析每個模型：設定了該模型的 `effortLevel`，或設定了[適用於該模型](#effortlevel)的頂層 `effortLevel`，且優先順序最高的[設定檔](https://code.claude.com/docs/zh-TW/settings.md#settings-precedence)會決定結果，因此受管設定中的 `effortLevel` 優先於您在使用者設定中儲存的等級。[調整 effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)列出了其他可覆寫已儲存等級的項目，例如啟動時的 `--effort`。

若要為某個模型的 effort 設定上限而非設定其等級，請在該模型的項目中加入 [`maxEffortLevel`](#maxeffortlevel) 欄位。此欄位需要 Claude Code v2.1.267 或更新版本。

* **範圍**：[`Any file`](#scopes)
* **類型**：將模型名稱對應至物件的物件，該物件可包含下列任一欄位：
  * `effortLevel`：`"low"`、`"medium"`、`"high"` 或 `"xhigh"` 之一
  * [`maxEffortLevel`](#maxeffortlevel)：該模型可執行的最高 effort 等級
  * `autoCompactWindow`：從 `100000` 到 `1000000` 的 token 數量，或 `"auto"` 表示針對該模型調整的視窗。[`/autocompact`](https://code.claude.com/docs/zh-TW/model-config#set-the-auto-compact-window) 會儲存於此。對於該模型，此值優先於同一個設定檔中頂層的 [`autoCompactWindow`](#autocompactwindow)。需要 Claude Code v2.1.288 或更新版本
* **預設值**：未設定

Claude Code 會以模型的標準名稱（例如 `claude-opus-5-5`）寫入每個項目，並將該模型的別名、帶日期後綴的 ID、`[1m]` 以及可辨識的供應商特定 ID 對應至同一個項目。

此範例讓 Opus 5.5 保持在 `high`，而其他模型則使用其自身已儲存的等級或預設等級：

```json settings.json theme={null}
{
  "modelSettings": {
    "claude-opus-5-5": {
      "effortLevel": "high"
    }
  }
}
```

執行 `/effort auto` 即可清除您正在使用之模型的已儲存等級。Claude Code 會保留其他項目以及任何頂層的 `effortLevel`。

### `outputStyle`

依名稱選擇[輸出風格](https://code.claude.com/docs/zh-TW/output-styles.md)。輸出風格是一組已儲存的指令，可改變 Claude 的角色、語氣和輸出格式，例如內建的 Explanatory 和 Learning 風格，或您自己撰寫的風格。

如果您在工作階段期間變更此鍵，Claude 會從您的下一則訊息開始使用新風格。關於該訊息在提示快取方面的成本，請參閱[變更輸出風格](https://code.claude.com/docs/zh-TW/prompt-caching.md#changing-output-style)。在 v2.1.251 之前，此編輯只會在您執行 `/clear` 或開始新的工作階段後才生效。

* **範圍**：[`Any file`](#scopes)
* **類型**：字串，[內建](https://code.claude.com/docs/zh-TW/output-styles.md#built-in-output-styles)或[自訂](https://code.claude.com/docs/zh-TW/output-styles.md#create-a-custom-output-style)輸出風格的名稱
* **預設值**：未設定，因此 Claude Code 會使用預設風格

此範例選擇內建的 Explanatory 風格，它會在任務之間加入教育性的見解：

```json settings.json theme={null}
{
  "outputStyle": "Explanatory"
}
```

### `promptCacheTtl`

選擇[提示快取](https://code.claude.com/docs/zh-TW/prompt-caching.md)保留主要對話的時間長度。此鍵套用於您的互動式、`-p` 以及 Agent SDK 回合，以及 Claude Code 與其一同內嵌執行的輔助程式。一小時的存留期可在較長的中斷期間保持快取為熱狀態，而 API 會以高於五分鐘存留期的[費率對每次快取寫入計費](https://platform.claude.com/docs/en/build-with-claude/prompt-caching#pricing)。需要 Claude Code v2.1.242 或更新版本。

* **範圍**：[`Any file`](#scopes)
* **類型**：字串，為下列之一：
  * `"5m"`：快取保留五分鐘
  * `"1h"`：快取保留一小時
* **預設值**：未設定，因此每個主要對話請求會取得[其預設存留期](https://code.claude.com/docs/zh-TW/prompt-caching.md#which-ttl-each-request-gets)
* **每個工作階段的覆寫**：[`FORCE_PROMPT_CACHING_5M`](https://code.claude.com/docs/zh-TW/env-vars) 優先於其他所有項目，其次是 [`CLAUDE_CODE_PROMPT_CACHE_TTL`](https://code.claude.com/docs/zh-TW/env-vars)，然後是此鍵，最後是 [`ENABLE_PROMPT_CACHING_1H`](https://code.claude.com/docs/zh-TW/env-vars)

此範例讓主要對話使用一小時的存留期，並讓 subagent 保持五分鐘：

```json settings.json theme={null}
{
  "promptCacheTtl": "1h",
  "subagentPromptCacheTtl": "5m"
}
```

關於各存留期的成本，請參閱[快取存留期](https://code.claude.com/docs/zh-TW/prompt-caching.md#cache-lifetime)。

### `showThinkingSummaries`

在互動式工作階段中查看 Claude [延伸思考](https://code.claude.com/docs/zh-TW/model-config.md#extended-thinking)的摘要。如果您希望在使用 `Ctrl+O` 展開思考時看到完整摘要，請設定此項。未設定或為 `false` 時，Anthropic API 會遮蔽思考區塊，而 Claude Code 會顯示一個摺疊的虛設區塊。

* **範圍**：[`Any file`](#scopes)
* **類型**：Boolean
  * `true`：使用 `Ctrl+O` 展開思考時，您會看到完整的思考摘要
  * `false`：Anthropic API 會遮蔽思考區塊，而 Claude Code 會顯示一個摺疊的虛設區塊
* **預設值**：`false`

```json settings.json theme={null}
{
  "showThinkingSummaries": true
}
```

遮蔽只會改變您看到的內容，而不會改變模型產生的內容。若要減少思考花費，請改為[降低預算或停用思考](https://code.claude.com/docs/zh-TW/model-config.md#extended-thinking)。

### `subagentPromptCacheTtl`

選擇[提示快取](https://code.claude.com/docs/zh-TW/prompt-caching.md)保留 Claude Code 在主要對話以外發出之請求的時間長度。此鍵套用於 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md)、[工作流程](https://code.claude.com/docs/zh-TW/workflows.md)，以及 Claude Code 自身的背景和輔助請求，例如壓縮和工作階段標題。一小時的存留期可在較長的中斷期間保持快取為熱狀態，而 API 會以高於五分鐘存留期的[費率對每次快取寫入計費](https://platform.claude.com/docs/en/build-with-claude/prompt-caching#pricing)。需要 Claude Code v2.1.242 或更新版本。

* **範圍**：[`Any file`](#scopes)
* **類型**：字串，為下列之一：
  * `"5m"`：快取保留五分鐘
  * `"1h"`：快取保留一小時
* **預設值**：未設定，因此這些請求各自取得[其預設存留期](https://code.claude.com/docs/zh-TW/prompt-caching.md#which-ttl-each-request-gets)
* **每個工作階段的覆寫**：[`FORCE_PROMPT_CACHING_5M`](https://code.claude.com/docs/zh-TW/env-vars) 優先於其他所有項目，其次是 [`CLAUDE_CODE_SUBAGENT_PROMPT_CACHE_TTL`](https://code.claude.com/docs/zh-TW/env-vars)，然後是此鍵，再來是 [`ENABLE_PROMPT_CACHING_1H`](https://code.claude.com/docs/zh-TW/env-vars)，它會要求每個請求都使用一小時的存留期。關於 subagent 自身 frontmatter 值的優先順序，請參閱[自行選擇 TTL](https://code.claude.com/docs/zh-TW/prompt-caching.md#choose-the-ttl-yourself)

此範例讓 subagent 以及主要對話以外的其他請求使用一小時的存留期：

```json settings.json theme={null}
{
  "subagentPromptCacheTtl": "1h"
}
```

此鍵涵蓋 [`promptCacheTtl`](#promptcachettl) 未涵蓋的請求，因此同時設定兩者即可為 Claude Code 發出的每個請求選擇存留期。關於 subagent 的快取與主要對話快取的差異，請參閱[Subagent 與快取](https://code.claude.com/docs/zh-TW/prompt-caching.md#subagents-and-the-cache)。

### `switchModelsOnFlag`

選擇當[安全分類器標記請求](https://code.claude.com/docs/zh-TW/model-config.md#automatic-model-fallback)時會發生什麼：切換至備援模型並繼續，或暫停讓您在切換與編輯提示詞之間做選擇。

* **範圍**：[`Any file`](#scopes)。在 `/config` 中顯示為 **Switch models when a message is flagged**，選項為 **Switch automatically** 和 **Ask each time**。
* **類型**：Boolean
  * `true`：Claude Code 切換至備援模型並繼續
  * `false`：在互動式工作階段中，Claude Code 會暫停讓您在切換與編輯提示詞之間做選擇；在無法顯示對話方塊的情況下（例如 `-p` 執行），被標記的請求會以錯誤結束
* **預設值**：未設定。Claude Code 會自動切換，但在互動式工作階段中可能會[先詢問](https://code.claude.com/docs/zh-TW/model-config.md#ask-before-switching)

```json settings.json theme={null}
{
  "switchModelsOnFlag": false
}
```

請參閱[切換前詢問](https://code.claude.com/docs/zh-TW/model-config.md#ask-before-switching)。

### `ultracode`

以開啟 [ultracode](https://code.claude.com/docs/zh-TW/workflows.md#let-claude-decide-with-ultracode) 的狀態啟動工作階段。開啟後，Claude 會為每個實質性任務規劃工作流程，而不是等待您要求。只有在您啟用了[動態工作流程](https://code.claude.com/docs/zh-TW/workflows.md)且您的模型支援 `xhigh` effort 時，Claude 才會規劃工作流程。此鍵不會改變工作階段的 effort 等級：ultracode 會以工作階段所使用的任何等級執行。Claude Code 會讀取此鍵但絕不會寫入：`/effort ultracode` 只會在目前工作階段中開啟 ultracode。

* **範圍**：[`Any file`](#scopes)
* **類型**：Boolean
  * `true`：當您啟用了動態工作流程且您的模型支援 `xhigh` 時，工作階段會以開啟 ultracode 的狀態啟動
  * `false`：工作階段會以關閉 ultracode 的狀態啟動
* **預設值**：未設定，因此 ultracode 為關閉狀態
* **每個工作階段的覆寫**：`/effort ultracode` 會在沒有此鍵的情況下於單一工作階段中開啟 ultracode，而當此鍵為 `true` 時，`/effort ultracode off` 會在單一工作階段中將其關閉。`--effort ultracode` 旗標也會以 `xhigh` effort 在單一工作階段中開啟 ultracode

```json settings.json theme={null}
{
  "ultracode": true
}
```

工作階段的 effort 等級來自 [`effortLevel`](#effortlevel)、[`modelSettings`](#modelsettings) 以及其他 [effort 來源](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)，而 [effort 上限](https://code.claude.com/docs/zh-TW/model-config.md#organization-effort-limits)（例如 [`maxEffortLevel`](#maxeffortlevel)）會降低該等級，但不會關閉 ultracode。此行為以及 `/effort ultracode off` 形式需要 Claude Code v2.1.284 或更新版本。在 v2.1.284 之前，`ultracode: true` 會以 `xhigh` effort 執行工作階段，而低於 `xhigh` 的 effort 上限會讓 ultracode 保持關閉。Agent SDK 的 `apply_flag_settings` 控制請求也接受此鍵。

## 權限設定

決定 Claude 可以在不詢問的情況下執行的操作、工作階段啟動時的權限模式，以及自動模式分類器允許的內容。如需規則語法和權限模型，請參閱[設定權限](https://code.claude.com/docs/zh-TW/permissions.md)。

### `allowManagedPermissionRulesOnly`

使受管設定成為權限規則的唯一設定來源。Claude Code 隨後會忽略使用者、專案、本機和 `--settings` 檔案中的 `allow`、`ask` 和 `deny` 規則，忽略 `--allowedTools`，隱藏權限提示中的永遠允許選項，並停止儲存新規則。

當[來自嵌入主機的父設定](https://code.claude.com/docs/zh-TW/managed-settings.md#let-an-embedding-host-add-policy)適用時，Claude Code 會將其視為受管層級的一部分。它捨棄其 `allow` 規則和 `additionalDirectories`，並保留其 `deny` 和 `ask` 規則，除了模式以 `!` 開頭的 `Read` 和 `Edit` 規則。主機無法使用 `!` 規則從受管規則中切割出路徑，無論您是否設定此設定鍵。

`--disallowedTools` 規則和目前工作階段的 `deny` 和 `ask` 規則仍然適用，包括在 Claude Code 於工作階段中途重新載入設定之後。它們只會限制，因此無法擴大受管規則授予的權限。在 v2.1.257 之前，Claude Code 在第一次設定重新載入時會捨棄這些命令列和工作階段規則。

如需 `--disallowedTools` 或工作階段規則中的 `!` 模式可以切割出什麼，請參閱 [Read 和 Edit 規則](https://code.claude.com/docs/zh-TW/permissions.md#read-and-edit)。

設定此設定鍵時，Claude Code v2.1.282 或更新版本也會忽略來自下列來源的 skill 和 `.claude/commands/` 檔案中的 [`allowed-tools`](https://code.claude.com/docs/zh-TW/skills#pre-approve-tools-for-a-skill) frontmatter：

* 儲存庫的 `.claude/` 目錄
* 您的 `~/.claude/skills/` 和 `~/.claude/commands/` 目錄，包括[從 claude.ai 同步的 skill](https://code.claude.com/docs/zh-TW/skills.md#where-synced-skills-load)
* `--add-dir` 目錄
* 位於 `~/.claude/skills/` 或專案的 `.claude/skills/` 內、[以 `.claude-plugin` 資訊清單宣告的外掛](https://code.claude.com/docs/zh-TW/plugins/loading#plugins-shared-through-a-repository)
* 僅為單一工作階段載入、其 id 以 [`@inline`](https://code.claude.com/docs/zh-TW/plugins/loading#find-where-a-plugin-came-from) 結尾的外掛，且下列條件全部成立時：
  * 該工作階段是由 Claude Desktop 應用程式本身啟動 Claude Code 的 [Code 工作階段](https://code.claude.com/docs/zh-TW/desktop.md#environment-configuration)或 [Cowork 工作階段](https://code.claude.com/docs/zh-TW/managed-settings.md#where-and-when-a-policy-applies)，雲端工作階段除外
  * 此設定鍵由您的受管設定設定，而不僅是由嵌入主機的[父設定](https://code.claude.com/docs/zh-TW/managed-settings.md#let-an-embedding-host-add-policy)設定
  * 該工作階段執行 Claude Code v2.1.305 或更新版本

來自受管設定的 skill 和隨附 skill 會保留其 `allowed-tools`。這些 Desktop 工作階段之外的 `@inline` 外掛也會保留其 `allowed-tools`，但名為 [`anthropic-skills`](https://code.claude.com/docs/zh-TW/skills#names-reserved-for-synced-skills) 的外掛除外。skill 的 `disallowed-tools` 仍然適用。如需 Claude Code 忽略此欄位時開發人員會看到的內容，請參閱[僅套用受管權限規則時](https://code.claude.com/docs/zh-TW/skills.md#when-only-managed-permission-rules-apply)。

* **範圍**：[`Managed`](#scopes)
* **類型**：布林值
  * `true`：受管設定成為權限規則的唯一設定來源
  * `false`：Claude Code 除了套用受管規則外，還會套用來自使用者、專案、本機和 `--settings` 檔案的權限規則
* **預設值**：未設定，因此 Claude Code 會套用來自使用者、專案和本機設定以及 `--settings` 的權限規則，以及受管規則

```json managed-settings.json theme={null}
{
  "allowManagedPermissionRulesOnly": true
}
```

此設定鍵不會鎖定 MCP 伺服器允許清單；若要執行此操作，請設定 [`allowManagedMcpServersOnly`](#allowmanagedmcpserversonly)。請參閱[僅受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md#managed-only-settings)。

### `autoMode`

將您自己的規則新增至[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)分類器封鎖和允許的內容。使用它來告訴分類器您的組織信任哪些儲存庫、貯體和網域，以便它停止封鎖例行的內部操作。分類器隨附[內建的允許和拒絕規則](https://code.claude.com/docs/zh-TW/auto-mode-config.md#inspect-the-defaults-and-your-effective-config)。在陣列中包含字面字串 `"$defaults"` 以在該位置保留這些內建規則，並在其周圍新增您的規則；省略它以用您的規則取代它們。

* **範圍**：[`User or managed`](#scopes)
* **類型**：物件，包含 `environment`、`allow`、`soft_deny` 和 `hard_deny` 散文規則陣列，加上 [`classifyAllShell`](#automode-classifyallshell) 布林值
* **預設值**：未設定，因此分類器僅使用其[內建規則](https://code.claude.com/docs/zh-TW/auto-mode-config.md#inspect-the-defaults-and-your-effective-config)

此範例透過 `"$defaults"` 保留內建的 `soft_deny` 規則，並新增一個封鎖 `terraform apply` 的規則：

```json settings.json theme={null}
{
  "autoMode": {
    "soft_deny": ["$defaults", "Never run terraform apply"]
  }
}
```

當多個檔案設定相同的陣列時，Claude Code 會連接這些項目。如需規則格式以及如何套用每個陣列，請參閱[設定自動模式](https://code.claude.com/docs/zh-TW/auto-mode-config.md)。

### `autoMode.classifyAllShell`

在自動模式啟用時，將每個 Bash 和 PowerShell 命令傳送到自動模式分類器。根據預設，自動模式只會暫停可能執行任意程式碼的允許規則：工具範圍和萬用字元規則（例如 `Bash(*)`）以及解譯器或 shell 包裝器前綴（例如 `Bash(python *)`）。與其他允許規則相符的命令（例如 `Bash(npm test)`）會跳過分類器，除非它帶有[每個命令允許的網域](https://code.claude.com/docs/zh-TW/sandboxing.md#per-command-allowed-domains-in-auto-mode)。當它跳過時，規則的前綴未預期的破壞性引數可能會通過而不被看到。設定此設定鍵會暫停工作階段的每個 shell 允許規則，以便分類器看到每個命令。需要 Claude Code v2.1.193 或更新版本。

* **範圍**：[`User or managed`](#scopes)。讀取位置與 [`autoMode`](#automode) 相同。
* **類型**：布林值
  * `true`：在自動模式啟用時，Claude Code 會將每個 Bash 和 PowerShell 命令傳送到分類器，並暫停您的 shell 允許規則；在自動模式外，規則仍然適用
  * `false`：自動模式只會暫停可能執行任意程式碼的允許規則，例如 `Bash(*)` 和 `Bash(python *)`；與任何其他允許規則相符的命令會跳過分類器，除非它帶有[每個命令允許的網域](https://code.claude.com/docs/zh-TW/sandboxing.md#per-command-allowed-domains-in-auto-mode)，每個其他 shell 命令都會通過它
* **預設值**：`false`

```json settings.json theme={null}
{
  "autoMode": {
    "classifyAllShell": true
  }
}
```

請參閱[將所有 shell 命令路由到分類器](https://code.claude.com/docs/zh-TW/auto-mode-config.md#route-all-shell-commands-through-the-classifier)。

### `disableAutoMode`

從 `Shift+Tab` 循環中移除[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)。任何原本會[以自動模式啟動](https://code.claude.com/docs/zh-TW/permission-modes.md#which-mode-a-session-starts-in)的工作階段（無論是來自 `--permission-mode auto`、設定檔或內建預設值）都會改為以 `default` 啟動。管理員在受管設定中設定它，以防止其組織中的開發人員使用自動模式。

* **範圍**：[`Any file`](#scopes)。最適合在[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)中使用，使用者無法覆寫它。也接受在 `permissions` 下作為 `permissions.disableAutoMode`。
* **類型**：字串 `"disable"`
* **預設值**：未設定

```json settings.json theme={null}
{
  "disableAutoMode": "disable"
}
```

### `permissions`

控制 Claude 可以在不詢問的情況下使用哪些工具、哪些工具始終提示，以及哪些工具被封鎖，並設定工作階段啟動時的[權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md)。下面的每個 `permissions.*` 設定鍵都巢狀在此物件下。

* **範圍**：[`Any file`](#scopes)
* **類型**：物件，包含 `allow`、`ask`、`deny`、`additionalDirectories`、`blockReadsOutsideWorkingDirectories`、`blockWritesOutsideWorkingDirectories`、`defaultMode`、`disableBypassPermissionsMode` 和 `disableAutoMode`
* **預設值**：未設定

此範例在不詢問的情況下核准 `npm run` 命令，在 `git push` 前提示，封鎖 `.env` 的讀取，並以 `acceptEdits` 啟動工作階段：

```json settings.json theme={null}
{
  "permissions": {
    "allow": ["Bash(npm run *)"],
    "ask": ["Bash(git push *)"],
    "deny": ["Read(./.env)"],
    "defaultMode": "acceptEdits"
  }
}
```

三個規則陣列共享一個語法；請參閱 `permissions.allow` 下的[權限規則語法](#permission-rule-syntax)。如需來自不同檔案的權限規則如何組合，請參閱[權限規則如何跨範圍合併](https://code.claude.com/docs/zh-TW/permissions.md#settings-precedence)；如需設定鍵的一般組合方式，請參閱設定指南上的[設定優先順序](https://code.claude.com/docs/zh-TW/settings.md#settings-precedence)。

### `useAutoModeDuringPlan`

選擇 Claude Code 是否在 plan mode 中使用自動模式分類器來檢查 shell 命令。使用預設值 `true`，分類器在規劃期間檢查每個命令（當自動模式可用且您看不到提示時），除了[關鍵路徑移除](https://code.claude.com/docs/zh-TW/permission-modes.md#critical-paths)。設定 `false` 以針對內建唯讀集之外的每個命令獲得權限提示。在 `/config` 中顯示為**在計畫期間使用自動模式**。

* **範圍**：[`User, local, or managed`](#scopes)。儲存庫無法為您關閉它。
  * 這些檔案中任一個或 `--settings` 中的 `false` 都會將其關閉，除非您使用 [`--setting-sources`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 等選項排除該使用者或本機檔案。忽略被排除的檔案需要 Claude Code v2.1.314 或更新版本
* **類型**：布林值
  * `true`：與未設定相同；當自動模式可用時，分類器會在規劃期間檢查 shell 命令
  * `false`：您會針對內建唯讀集之外的每個命令獲得權限提示
* **預設值**：`true`

```json settings.json theme={null}
{
  "useAutoModeDuringPlan": false
}
```

### `permissions.allow`

列出 Claude Code 在不詢問您的情況下核准的工具使用。在 MCP 規則中，`*` 只能出現在 `mcp__<server>__` 前綴之後的工具名稱中，例如 `mcp__github__get_*`；它不能出現在伺服器名稱中。

* **範圍**：[`Any file`](#scopes)
* **類型**：權限規則字串陣列
* **預設值**：未設定
* **每個工作階段的覆寫**：`--allowedTools` 為一個工作階段新增允許規則，任何設定檔中的拒絕規則仍然會封鎖它命名的工具

此範例核准 `git diff` 並讓 Claude Code 在不詢問的情況下讀取您的 `.zshrc`：

```json settings.json theme={null}
{
  "permissions": {
    "allow": ["Bash(git diff *)", "Read(~/.zshrc)"]
  }
}
```

Claude Code 只有在您接受該資料夾的[工作區信任對話](https://code.claude.com/docs/zh-TW/permissions.md#project-allow-rules-and-workspace-trust)後，才會套用專案 `.claude/settings.json` 中的 `allow` 規則。

#### 權限規則語法

權限規則遵循格式 `Tool` 或 `Tool(specifier)`。Claude Code 首先評估 `deny` 規則，然後 `ask`，然後 `allow`，第一個相符項決定結果，無論每個規則的具體程度如何；請參閱[權限規則評估順序](https://code.claude.com/docs/zh-TW/permissions.md#manage-permissions)。

每一列顯示一個規則形狀及其相符的內容。

| 規則 | 相符的內容 |
| :- | :- |
| `Bash` | 每個 Bash 命令 |
| `Bash(npm run *)` | 以 `npm run` 開頭的命令 |
| `Read(./.env)` | `.env` 檔案的讀取 |
| `WebFetch(domain:example.com)` | 對 example.com 的擷取請求 |

如需完整的規則語法，包括萬用字元行為、Read、Edit、WebFetch、MCP 和 Agent 規則的工具特定模式，以及 Bash 模式的安全限制，請參閱[權限規則語法](https://code.claude.com/docs/zh-TW/permissions.md#permission-rule-syntax)。

### `permissions.ask`

列出即使在原本會核准它們的權限模式（例如 `acceptEdits` 或 `bypassPermissions`）中也會提示您確認的工具使用。在 `dontAsk` 模式中，Claude Code 會拒絕相符的工具使用，而不是提示。

* **範圍**：[`Any file`](#scopes)
* **類型**：權限規則字串陣列
* **預設值**：未設定

```json settings.json theme={null}
{
  "permissions": {
    "ask": ["Bash(git push *)"]
  }
}
```

### `permissions.deny`

列出 Claude Code 封鎖的工具使用。將其用於保存 API 金鑰、機密或環境值的檔案：Claude Code 會從檔案探索和搜尋結果中排除相符的檔案，拒絕讀取它們，並在相符的路徑上封鎖 [Edit 和 Write 工具](https://code.claude.com/docs/zh-TW/permissions.md#read-and-edit)。

Read 和 Edit 拒絕規則適用於 Claude 的內建檔案工具、Claude Code 在 Bash 中識別的檔案命令（例如 `cat`、`head`、`tail`、`sed` 和 `tee`）以及 Bash [重新導向](https://code.claude.com/docs/zh-TW/permissions.md#redirections)的目標（例如 `> file` 和 `< file`）；它們不適用於讀取檔案而不命名它們的命令（例如 `grep -r pattern .`）或任意子程序，因此如需作業系統層級的強制執行，請[啟用沙箱](https://code.claude.com/docs/zh-TW/sandboxing.md)。

* **範圍**：[`Any file`](#scopes)
* **類型**：權限規則字串陣列
* **預設值**：未設定
* **每個工作階段的覆寫**：`--disallowedTools` 在此設定鍵之外為一個工作階段新增拒絕規則

此範例拒絕讀取 `.env` 檔案、`secrets` 目錄和憑證檔案，並封鎖 `curl` 命令：

```json settings.json theme={null}
{
  "permissions": {
    "deny": [
      "Read(./.env)",
      "Read(./.env.*)",
      "Read(./secrets/**)",
      "Read(./config/credentials.json)",
      "Bash(curl *)"
    ]
  }
}
```

工具名稱接受 glob 模式，因此 `"*"` 拒絕每個工具，`"mcp__*"` 拒絕每個 MCP 工具。只要任何其他工具仍然可供 Claude 使用，Claude Code 就會忽略 [`EndConversation`](https://code.claude.com/docs/zh-TW/tools-reference#endconversation-tool-behavior) 工具的拒絕規則。`Bash` 拒絕規則與 Claude 寫入的命令相符，因此 `Bash(curl *)` 不會停止 `/usr/bin/curl` 或 `sh -c 'curl …'`；請參閱[Bash 規則不相符的內容](https://code.claude.com/docs/zh-TW/permissions.md#bash-rule-limits)。此設定鍵取代已棄用的 `ignorePatterns` 設定。

### `permissions.additionalDirectories`

給予 Claude 檔案存取權限，以存取您啟動的目錄之外的目錄，作為額外的[工作目錄](https://code.claude.com/docs/zh-TW/permissions.md#working-directories)。大多數 `.claude/` 設定[未從這些目錄探索](https://code.claude.com/docs/zh-TW/permissions.md#additional-directories-grant-file-access-not-configuration)。

* **範圍**：[`Any file`](#scopes)，專案和本機項目所給予的[沙箱寫入存取權有其限制](https://code.claude.com/docs/zh-TW/sandboxing.md#repository-settings-under-an-admin-required-sandbox)
* **類型**：目錄路徑陣列
* **預設值**：未設定
* **每個工作階段的覆寫**：`--add-dir` 和 `/add-dir` 在此設定鍵之外為一個工作階段新增目錄

```json settings.json theme={null}
{
  "permissions": {
    "additionalDirectories": ["../docs/"]
  }
}
```

與 `allow` 規則一樣，專案 `.claude/settings.json` 中的項目只有在您接受該資料夾的[工作區信任對話](https://code.claude.com/docs/zh-TW/permissions.md#project-allow-rules-and-workspace-trust)後才會生效。

### `permissions.blockReadsOutsideWorkingDirectories`

使 Claude 的檔案工具在每個權限模式（包括 `bypassPermissions`）中拒絕讀取您的[工作目錄](https://code.claude.com/docs/zh-TW/permissions.md#working-directories)之外的路徑。Claude Code 拒絕對這些路徑的 `Read`、`Grep`、`Glob` 和 `LSP` 呼叫，並告訴 Claude 要求您使用 `/add-dir` 新增目錄。Claude Code 本身需要的檔案保持可讀，例如您的 skill、外掛、規則、agent、命令以及 `~/.claude/` 下的 `CLAUDE.md` 記憶檔案。需要 Claude Code v2.1.257 或更新版本。

Claude Code 不會以相同方式拒絕 shell 命令：

* [沒有任何模式自動核准的操作](https://code.claude.com/docs/zh-TW/permission-modes.md#actions-no-mode-auto-approves)涵蓋讀取此類路徑的 shell 命令何時提示您
* [區塊下的沙箱化命令](#sandboxed-commands-under-the-block)涵蓋沙箱化命令可以讀取的內容

shell 解析器無法追蹤的 Bash 命令（例如多次變更目錄或執行子 shell 的命令）即使在自動模式和 `bypassPermissions` 模式中也會提示您。即使命令未命名工作目錄外的任何路徑，提示仍然會出現。當命令在[沙箱](https://code.claude.com/docs/zh-TW/sandboxing.md)中執行且沙箱強制執行封鎖時，此提示不適用。

Claude Code 也會在此處寫入 `true`，當您選擇在[自動模式的提示中封鎖此類讀取（在第一次讀取工作目錄外之前）](https://code.claude.com/docs/zh-TW/permission-modes.md#first-read-outside-the-working-directories)時。

* **範圍**：[`Any file`](#scopes)。如果任何檔案設定 `true`，則區塊適用，因此儲存庫可以為自己開啟區塊，但無法解除您設定的區塊。
* **類型**：布林值
  * `true`：Claude 的檔案工具拒絕讀取工作目錄之外的路徑
  * `false`：與未設定相同；另一個檔案中的 `true` 仍然會套用區塊
* **預設值**：未設定，因此工作目錄外的讀取遵循您的[權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md)

```json settings.json theme={null}
{
  "permissions": {
    "blockReadsOutsideWorkingDirectories": true
  }
}
```

若要解除區塊，請從設定它的每個設定檔中移除此設定鍵，然後重新啟動每個執行中的工作階段。

您使用 `--add-dir`、`/add-dir` 或您的使用者或受管設定中的 `additionalDirectories` 新增的目錄計為區塊的工作目錄。僅在儲存庫設定中新增的目錄不計：`.claude/settings.json` 中的目錄，以及 `.claude/settings.local.json` 中的目錄，除非 git 報告該檔案為未追蹤。在不是 git 儲存庫的目錄中，或當 git 追蹤該檔案時，Claude Code 將 `.claude/settings.local.json` 視為儲存庫設定，因此請改為在您的使用者設定中放置您想保持可讀的目錄。

當 [`autoMemoryDirectory`](#automemorydirectory) 來自專案的 `.claude/settings.json`，或來自被[視為儲存庫提供](https://code.claude.com/docs/zh-TW/permissions.md#when-your-local-settings-file-needs-trust)的 `.claude/settings.local.json` 時，Claude Code 不會從該目錄載入任何[自動記憶](https://code.claude.com/docs/zh-TW/memory.md#storage-location)，也不會將任何儲存到其中。

#### 區塊下的沙箱化命令

當[沙箱機制](https://code.claude.com/docs/zh-TW/sandboxing.md)開啟時，區塊也涵蓋沙箱化命令。Claude Code 拒絕它們對您的家目錄和保存使用者檔案的其他根目錄的讀取存取：`/Users`、`/home`、`/root`、`/Volumes`、`/mnt`、`/media`、`/run/media` 和 `/srv`。然後它重新開啟工作目錄、[Claude Code 在工作階段中建立的 worktree](https://code.claude.com/docs/zh-TW/worktrees.md)、工作階段暫存目錄，以及 `~/.claude` 中命令需要的部分，例如 skill 和外掛。當區塊生效時，來自儲存庫設定的 `allowRead` 和 `allowWrite` 項目不計。

當工作階段的工作目錄是連結的 [git worktree](https://code.claude.com/docs/zh-TW/worktrees.md)（包括 Claude Code 在工作階段中途進入的）時，儲存庫的通用 `.git` 目錄對沙箱化命令保持可讀和可寫，因此 git 在該處保持運作。

在這些情況下，區塊不會到達沙箱化命令，而 Claude 的檔案工具保持強制執行它：

* 檔案系統隔離透過 [`sandbox.filesystem.disabled`](#sandbox-filesystem-disabled) 關閉
* [`allowManagedReadPathsOnly`](#sandbox-filesystem-allowmanagedreadpathsonly) 已設定
* 您啟動 Claude Code 的目錄路徑包含 glob 字元，例如 `*`、`?` 或 `[`

在區塊下，Claude Code 重新開啟您的全域 git 設定檔到沙箱化命令，以便 `git` 保持您的身分和設定：

* `~/.gitconfig`
* `$XDG_CONFIG_HOME/git` 下的 `config`、`ignore` 和 `attributes` 檔案，預設為 `~/.config/git`
* 您的全域 git 設定透過 `[include]`、`[includeIf]`、`core.excludesFile` 或 `core.attributesFile` 命名的檔案

Claude Code 分別判斷每個檔案。當檔案位於沙箱化命令可以寫入的位置（直接或透過符號連結）時，Claude Code 不會重新開啟它命名的檔案。

在 Linux 和 WSL2 上，作為符號連結的設定檔可以在其自己的路徑上保持不可讀，然後 `git` 在沒有它的情況下執行。`~/.git-credentials` 和 `$XDG_CONFIG_HOME/git/credentials` 保持被區塊。

如果重新開啟的檔案保存機密，例如 `http.extraHeader` token，請將其路徑新增到 [`sandbox.filesystem.denyRead`](#sandbox-filesystem-denyread)。涵蓋檔案的 `denyRead` 項目始終優先於此重新開啟。

### `permissions.blockWritesOutsideWorkingDirectories`

使 `Write`、`Edit` 和 `NotebookEdit` 工具在每個權限模式（包括 `bypassPermissions`）中拒絕您的[工作目錄](https://code.claude.com/docs/zh-TW/permissions.md#working-directories)之外的路徑，但 [Claude Code 自身的部分檔案](#what-the-write-block-refuses-and-what-stays-writable)除外。此設定鍵不會限制 shell 命令、MCP 工具或 hook 執行的程式。若要限制 shell 命令寫入的位置，請開啟[沙箱機制](https://code.claude.com/docs/zh-TW/sandboxing.md)。需要 Claude Code v2.1.314 或更新版本。

開啟此設定鍵後，Claude Code 也會移除 `EnterWorktree` 和 `ExitWorktree` 工具，或拒絕對它們的呼叫。若要繼續在 worktree 中工作，請依照 [Claude 沒有 `EnterWorktree` 工具](https://code.claude.com/docs/zh-TW/worktrees#claude-has-no-enterworktree-tool)的說明操作。

* **範圍**：[`Any file`](#scopes)。只要工作階段載入的任何檔案設定 `true`，封鎖就會適用，因此儲存庫可以為自己開啟封鎖，但無法解除您設定的封鎖。在[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)中，Claude Code 可能不會套用此設定鍵，因為檔案工具在本身即為邊界的容器中執行。
* **類型**：布林值
  * `true`：開啟封鎖
  * `false`：與未設定相同；另一個檔案中的 `true` 仍然會套用封鎖
* **預設值**：未設定，因此工作目錄外的寫入遵循您的[權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md)。當 Claude Code 無法讀取您[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md#keys-that-fail-closed)中的 `permissions` 物件時，封鎖也會開啟。

```json settings.json theme={null}
{
  "permissions": {
    "blockWritesOutsideWorkingDirectories": true
  }
}
```

若要測試封鎖，請要求 Claude 使用 Write 工具在您的工作目錄之外建立檔案，例如 `~/block-test.txt`（如果您的家目錄不屬於工作目錄）。Claude Code 會拒絕該呼叫，且拒絕訊息會說明[設定封鎖了工作目錄之外的寫入](https://code.claude.com/docs/zh-TW/errors.md#setting-blocks-writes-outside-the-working-directories)。

若要解除封鎖，請從設定它的每個設定檔中移除此設定鍵，然後重新啟動 Claude Code。

#### 寫入封鎖拒絕的內容以及保持可寫入的內容

Claude Code 自身的部分檔案保持可寫入，例如計畫檔案、[暫存區](https://code.claude.com/docs/zh-TW/claude-directory.md#session-scratchpad-directory)、[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)的 `tmp` 目錄，以及此專案[自動記憶](https://code.claude.com/docs/zh-TW/memory.md#storage-location)中的 `.md` 檔案。

除了您自己位於工作目錄之外的檔案，封鎖也會拒絕寫入：

* **Claude Code 設定檔**：即使在工作目錄內，Claude Code 也會[拒絕這些寫入](https://code.claude.com/docs/zh-TW/errors.md#writes-to-claude-code-settings-files-are-blocked)，因為設定檔可以解除封鎖。請自行編輯設定檔。
* **僅由儲存庫設定新增的目錄**：僅在 `.claude/settings.json` 中，或在 `.claude/settings.local.json` 中（除非 git 報告該檔案為未追蹤）由 [`additionalDirectories`](#permissions-additionaldirectories) 列出的目錄
* **subagent 的 worktree**：當 [`isolation: worktree`](https://code.claude.com/docs/zh-TW/worktrees#isolate-subagents-with-worktrees) subagent 的 worktree 位於工作目錄之外時，其檔案編輯會被拒絕
* **儲存庫選擇之目錄中的自動記憶**：儲存庫設定中 [`autoMemoryDirectory`](#automemorydirectory) 所指定的目錄

無論您新增什麼，設定檔都會保持被拒絕。若要讓其他任一情況中的寫入通過，請[新增工作目錄](#let-one-directory-through-the-read-or-write-block)。`/add-dir` 需要已存在的目錄，因此對於 subagent worktree，請指定儲存庫根目錄下的 `.claude/worktrees` 目錄。

#### 讓單一目錄通過讀取或寫入封鎖

若要在 `blockReadsOutsideWorkingDirectories` 或 `blockWritesOutsideWorkingDirectories` 為 `true` 時讓 Claude 存取專案之外的某個目錄，請將其新增為工作目錄。在工作階段中執行 `/add-dir <directory>`、在啟動 Claude Code 時傳入 `--add-dir <directory>`，或在您的使用者或受管設定中的 `additionalDirectories` 下列出它。沒有任何[允許規則](https://code.claude.com/docs/zh-TW/permissions.md#read-and-edit)能讓 Claude 的檔案工具通過任一封鎖。

### `permissions.defaultMode`

設定新工作階段啟動時的[權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md)。當您將其保留為未設定時，工作階段會以您的使用介面的[內建預設值](https://code.claude.com/docs/zh-TW/permission-modes.md#which-mode-a-session-starts-in)啟動。

* **範圍**：[`Any file`](#scopes)。`auto` 和 `bypassPermissions` 不會從專案或本機設定生效，因此請改為在 `~/.claude/settings.json` 中設定它們。在 v2.1.257 之前，`bypassPermissions` 會從任何檔案生效。對於 VS Code 擴充功能啟動的對話，Claude Code 只讀取使用者、受管和 `--settings` 值。
* **類型**：字串，其中之一：
  * `"default"`：Claude Code 只在不詢問的情況下執行讀取
  * `"acceptEdits"`：Claude Code 也在不詢問的情況下執行檔案編輯和常見的檔案系統命令，例如 `mkdir` 和 `mv`
  * `"plan"`：Claude Code 讀取和計畫，但在您核准計畫之前封鎖編輯
  * `"auto"`：Claude Code 在沒有例行提示的情況下執行；在 shell 命令和網路請求等操作執行之前，背景分類器會檢查它們是否符合您的請求
  * `"dontAsk"`：Claude Code 自動拒絕每個原本會提示的呼叫，不過您安裝的 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md) 仍可核准[其中部分呼叫](https://code.claude.com/docs/zh-TW/permissions.md#precedence-among-rules-hooks-and-mods)。工作目錄內的檔案讀取、不需要核准的其他操作以及預先核准的工具仍然執行，但從[網路路徑](https://code.claude.com/docs/zh-TW/permissions.md#network-paths)的讀取除外
  * `"bypassPermissions"`：Claude Code 在不詢問的情況下執行所有操作
  * `"manual"`：`"default"` 的別名
* **預設值**：未設定
* **每個工作階段的覆寫**：`--permission-mode` 及其 `bypassPermissions` 的等效項 `--dangerously-skip-permissions` 對一個工作階段優先於此設定鍵

```json settings.json theme={null}
{
  "permissions": {
    "defaultMode": "acceptEdits"
  }
}
```

權限規則分層在每個模式之上：`deny` 規則在每個模式中封鎖，包括 `bypassPermissions`。請參閱[權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md)。在雲端工作階段中，Claude Code 只從此設定鍵中接受 `acceptEdits`、`plan`、`default` 和 `auto`。對於 VS Code 擴充功能啟動的對話，請參閱[擴充功能為啟動權限模式讀取的設定](https://code.claude.com/docs/zh-TW/permission-modes.md#switch-permission-modes)。

### `permissions.disableBypassPermissionsMode`

防止任何人進入 `bypassPermissions` 模式。Claude Code 隨後會拒絕 `--dangerously-skip-permissions` 旗標，並忽略 [agent 定義](https://code.claude.com/docs/zh-TW/sub-agents.md#permission-modes)中的 `permissionMode: bypassPermissions`，因此 subagent 會以父工作階段的權限模式執行。

* **範圍**：[`Any file`](#scopes)。通常在[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)中設定以強制執行組織原則。
* **類型**：字串 `"disable"`
* **預設值**：未設定
* **每個工作階段的覆寫**：此設定鍵優先於 `--dangerously-skip-permissions`，在設定此設定鍵時 Claude Code 會拒絕它

```json settings.json theme={null}
{
  "permissions": {
    "disableBypassPermissionsMode": "disable"
  }
}
```

在 v2.1.223 之前，Claude Code 即使在停用繞過時也會套用 frontmatter 權限模式。

### `skipAutoPermissionPrompt`

跳過 Claude Code 在您自己進入自動模式時顯示的一次性通知，描述[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)，例如透過您自己的設定或模式選擇器，而不是當內建預設值在其中啟動工作階段時。Claude Code 顯示該通知一次，然後記錄它已顯示，因此此設定鍵只在通知尚未出現的地方重要。

* **範圍**：[`User or managed`](#scopes)。儲存庫無法為您設定它。
* **類型**：布林值
  * `true`：Claude Code 跳過通知
  * `false`：與未設定相同；除非這些檔案中的另一個設定 `true`，否則通知會出現一次
* **預設值**：未設定，因此通知會出現一次

```json settings.json theme={null}
{
  "skipAutoPermissionPrompt": true
}
```

### `skipDangerousModePermissionPrompt`

跳過 Claude Code 在工作階段進入 `bypassPermissions` 模式前顯示的確認對話，無論是來自 `--dangerously-skip-permissions` 還是 `defaultMode: "bypassPermissions"`。當您接受該對話一次時，Claude Code 會在您的使用者設定中寫入 `true`。

* **範圍**：[`User, local, or managed`](#scopes)。不受信任的儲存庫無法為您跳過對話。
* **類型**：布林值
  * `true`：Claude Code 在工作階段進入 `bypassPermissions` 模式前跳過確認對話
  * `false`：與未設定相同；除非這些檔案中的另一個設定 `true`，否則對話會出現
* **預設值**：未設定，因此對話會出現

```json settings.json theme={null}
{
  "skipDangerousModePermissionPrompt": true
}
```

## 沙箱設定

將 Claude 執行的命令與您的檔案系統、網路和憑證隔離。關於沙箱機制的運作方式和平台需求，請參閱[沙箱機制](https://code.claude.com/docs/zh-TW/sandboxing.md)。

### `sandbox`

透過[沙箱機制](https://code.claude.com/docs/zh-TW/sandboxing.md)將 Claude 執行的 Bash 命令與您的檔案系統和網路隔離。使用 `enabled` 開啟沙箱，再透過 `filesystem`、`network` 和 `credentials` 子物件縮小或擴大沙箱化命令可存取的範圍。沙箱可在 macOS、Linux 和 WSL2 上執行。

* **範圍**：[`Any file`](#scopes)
* **類型**：包含 `enabled`、`failIfUnavailable`、`autoAllowBashIfSandboxed`、`excludedCommands`、`allowUnsandboxedCommands`、`enableWeakerNestedSandbox`、`enableWeakerNetworkIsolation`、`allowAppleEvents`、`allowNestedUserNamespaces`、`bwrapPath`、`socatPath`、`ignoreViolations` 和 `ripgrep`，以及 `filesystem`、`network` 和 `credentials` 物件的物件
* **預設值**：未設定，因此 Claude Code 會在沒有沙箱的情況下執行命令

以下設定會開啟沙箱、略過沙箱化命令的權限提示、在沙箱外執行 `docker`、開放兩個額外的寫入路徑、隱藏您的 AWS 憑證檔案，並預先允許 GitHub 和 npm：

```json settings.json theme={null}
{
  "sandbox": {
    "enabled": true,
    "autoAllowBashIfSandboxed": true,
    "excludedCommands": ["docker *"],
    "filesystem": {
      "allowWrite": ["/tmp/build", "~/.kube"],
      "denyRead": ["~/.aws/credentials"]
    },
    "network": {
      "allowedDomains": ["github.com", "*.npmjs.org"]
    }
  }
}
```

當受管設定設定了 `enabled` 或 `failIfUnavailable` 等布林值鍵時，該值會覆寫開發人員所設定的任何值。Claude Code 會在工作階段載入的所有設定範圍之間合併陣列鍵，因此開發人員可以附加項目；關於僅限受管設定的鎖定，請參閱[防止開發人員擴大政策](https://code.claude.com/docs/zh-TW/sandboxing.md#keep-developers-from-widening-the-policy)。若要為組織強制要求沙箱，請參閱[使用受管設定強制執行沙箱機制](https://code.claude.com/docs/zh-TW/sandboxing.md#enforce-sandboxing-with-managed-settings)。

### `sandbox.enabled`

為 Bash 命令開啟[沙箱機制](https://code.claude.com/docs/zh-TW/sandboxing.md)。當您在 `/sandbox` 面板中選擇模式時，Claude Code 會將此鍵寫入目前專案的 `.claude/settings.local.json`；若要讓每個專案都使用沙箱，請在 `~/.claude/settings.json` 中設定。

* **範圍**：[`Any file`](#scopes)，但[對專案和本機設定有所限制](https://code.claude.com/docs/zh-TW/sandboxing.md#repository-settings-under-an-admin-required-sandbox)
* **類型**：布林值
  * `true`：Claude Code 會將 Bash 命令沙箱化
  * `false`：Bash 命令在沙箱外執行
* **預設值**：`false`

```json settings.json theme={null}
{
  "sandbox": {
    "enabled": true
  }
}
```

在 Linux 和 WSL2 上，沙箱需要 `bubblewrap` 和 `socat`；請參閱[設定 Linux 和 WSL2](https://code.claude.com/docs/zh-TW/sandboxing.md#set-up-linux-and-wsl2)。當沙箱無法啟動時，Claude Code 會在沙箱外執行命令，除非您也設定了 [`failIfUnavailable`](#sandbox-failifunavailable)。

### `sandbox.failIfUnavailable`

當 `sandbox.enabled` 為 `true`，但由於平台不支援或相依性檢查失敗而導致沙箱無法啟動時，讓 Claude Code 在啟動時以錯誤結束。若未設定此鍵，Claude Code 會不經沙箱執行命令。將沙箱機制視為安全關卡的受管部署可以使用此設定。

在沙箱不支援的平台上，開啟此鍵時 Claude Code 不會啟動。請參閱[使用受管設定強制執行沙箱機制](https://code.claude.com/docs/zh-TW/sandboxing.md#enforce-sandboxing-with-managed-settings)。

* **範圍**：[`Any file`](#scopes)，但[對專案和本機設定有所限制](https://code.claude.com/docs/zh-TW/sandboxing.md#repository-settings-under-an-admin-required-sandbox)
* **類型**：Boolean
  * `true`：當 `sandbox.enabled` 為 `true` 但沙箱無法啟動時，Claude Code 會在啟動時以錯誤結束。若沙箱通過該檢查後初始化失敗，工作階段會繼續執行，而 Claude Code 會[拒絕每個沙箱化命令](https://code.claude.com/docs/zh-TW/sandboxing.md#commands-refused-with-sandbox-is-required)
  * `false`：當沙箱無法啟動時，Claude Code 會在沙箱外執行命令
* **預設值**：`false`

以下設定會為受管機器開啟沙箱，並將 `failIfUnavailable` 設為 `true`：

```json managed-settings.json theme={null}
{
  "sandbox": {
    "enabled": true,
    "failIfUnavailable": true
  }
}
```

請參閱[使用受管設定強制執行沙箱機制](https://code.claude.com/docs/zh-TW/sandboxing.md#enforce-sandboxing-with-managed-settings)。

### `sandbox.autoAllowBashIfSandboxed`

讓 Claude Code 在不顯示權限提示的情況下執行沙箱化的 Bash 命令。無法在沙箱中執行的命令仍會經過一般權限流程，且 `deny` 規則和限定內容的 `ask` 規則（例如 `Bash(git push *)`）仍然適用；單純的 `Bash` ask 規則則會對沙箱化命令略過。將其設為 `false` 可讓沙箱化命令也經過一般權限流程，`/sandbox` 的 **Mode** 分頁將此稱為一般權限模式。

* **範圍**：[`Any file`](#scopes)
* **類型**：布林值
  * `true`：Claude Code 會在不顯示權限提示的情況下執行沙箱化的 Bash 命令，但[自動允許模式](https://code.claude.com/docs/zh-TW/sandboxing.md#auto-allow-mode)所述的情況除外；`CLAUDE_CODE_SUBPROCESS_ENV_SCRUB` 會關閉自動允許
  * `false`：沙箱化命令會經過一般權限流程，因此由您的允許規則和權限模式決定。`/sandbox` 的 **Mode** 分頁將此稱為一般權限模式
* **預設值**：`true`

以下設定會保持沙箱開啟，並讓沙箱化命令經過一般權限流程：

```json settings.json theme={null}
{
  "sandbox": {
    "enabled": true,
    "autoAllowBashIfSandboxed": false
  }
}
```

關於自動允許模式仍會針對哪些情況提示，以及它在 plan mode 中的行為，請參閱[自動允許模式](https://code.claude.com/docs/zh-TW/sandboxing.md#auto-allow-mode)。

### `sandbox.excludedCommands`

指定 Claude Code 要在沙箱外執行的命令，例如無法在沙箱下運作的工具。每個項目使用與 `Bash(...)` [權限規則](https://code.claude.com/docs/zh-TW/permissions.md#permission-rule-syntax)內容相同的語法：確切的命令、前綴（例如 `docker *`）或萬用字元模式。不含萬用字元的模式為確切比對，因此 `docker` 只會比對不帶任何引數的 `docker`。

只有當您的項目涵蓋某個 Bash 呼叫中的每一個命令時，才會將該呼叫移出沙箱，而且即使如此，某些呼叫形式仍會保持沙箱化。僅有 `docker *` 項目並不會將 `npm ci && docker build .` 移出沙箱。

* **範圍**：[`Any file`](#scopes)，但[對專案和本機設定有所限制](https://code.claude.com/docs/zh-TW/sandboxing.md#repository-settings-under-an-admin-required-sandbox)
* **類型**：命令模式的陣列
* **預設值**：未設定，因此不排除任何命令

```json settings.json theme={null}
{
  "sandbox": {
    "excludedCommands": ["docker *"]
  }
}
```

當 Bash 呼叫具有下列形式之一（以及其他形式）時，Claude Code 會將其保持沙箱化：

* 以 `sudo`、`eval` 或 `xargs` 開頭的命令
* `cd`、`pushd` 或 `popd`，無論出現在呼叫中的何處
* 命令替換、子 shell，或 `if`、`for` 等控制流程區塊
* 重新導向，例如 `docker build . > build.log` 或 `<<EOF` heredoc，但僅複製檔案描述元的重新導向（如 `2>&1`）除外
* 命令名稱來自變數
* 帶有絕對路徑、以 `~` 開頭或包含 `..` 區段之路徑引數的 `git clone`、`git init`、`git worktree add`、`git worktree move` 或 `git bundle create`

例如，在 `docker *` 項目下，`cd build && docker compose up` 仍會保持沙箱化，而新增 `cd` 項目也不會改變這一點。在 `git *` 項目下，`git clone <url> vendor/lib` 會在沙箱外執行，但 `git clone <url> ~/tools` 會保持沙箱化。複製操作會在目的地路徑所指之處寫入整個檔案樹，其中可能包含可執行檔。

被排除的命令仍會經過一般權限流程。排除只是為了方便，而非安全邊界：當工具只需要寫入特定位置時，[`filesystem.allowWrite`](#sandbox-filesystem-allowwrite) 可讓它保持沙箱化。

除非沙箱為[管理員強制要求](https://code.claude.com/docs/zh-TW/sandboxing.md#repository-settings-under-an-admin-required-sandbox)，否則來自工作階段載入之各設定範圍的項目會合併為單一清單。在管理員強制要求的情況下，Claude Code 會忽略 `.claude/settings.json` 和 `.claude/settings.local.json` 中的項目，因此複製下來的儲存庫無法將命令移出沙箱。受管設定、`--settings` 和您的 `~/.claude/settings.json` 中的項目仍然適用，且此清單沒有僅限受管設定的鎖定。

### `sandbox.allowUnsandboxedCommands`

讓 Claude 在沙箱封鎖命令後，使用 `dangerouslyDisableSandbox` 參數在沙箱外重試該命令。設為 `false` 時，Claude Code 會忽略該參數。此時在沙箱執行期間，Claude 執行的命令都會沙箱化，除非它們符合 [`excludedCommands`](#sandbox-excludedcommands) 項目。`/sandbox` 的 **Overrides** 分頁會將此狀態顯示為 **Strict sandbox mode**。受管設定中的 `false` 會為其涵蓋的開發人員開啟嚴格沙箱模式。

* **範圍**：[`Any file`](#scopes)，但[對專案和本機設定有所限制](https://code.claude.com/docs/zh-TW/sandboxing.md#turn-off-the-retry-with-strict-sandbox-mode)
* **類型**：布林值
  * `true`：Claude 可在沙箱封鎖命令後，使用 `dangerouslyDisableSandbox` 參數在沙箱外重試該命令
  * `false`：Claude Code 會忽略該參數，因此在沙箱執行期間，Claude 執行的命令都會沙箱化，除非它們符合 `excludedCommands` 項目
* **預設值**：`true`

以下設定會為受管設定涵蓋的所有人強制執行嚴格沙箱模式：

```json managed-settings.json theme={null}
{
  "sandbox": {
    "enabled": true,
    "allowUnsandboxedCommands": false
  }
}
```

來自受管設定或 `--settings` 的 `false` 也會讓沙箱成為[管理員強制要求](https://code.claude.com/docs/zh-TW/sandboxing.md#repository-settings-under-an-admin-required-sandbox)。您使用者設定中的 `false` 會優先於專案的 `true`，但不會讓沙箱成為管理員強制要求。優先於專案值的行為需要 Claude Code v2.1.285 或更新版本。

由誰核准在沙箱外重試，取決於您的權限模式和允許規則。請參閱[在沙箱外重試的逃生出口](https://code.claude.com/docs/zh-TW/sandboxing.md#the-unsandboxed-retry-escape-hatch)。

若要了解您自己在 [`!` shell 模式提示字元](https://code.claude.com/docs/zh-TW/interactive-mode#shell-mode-with-prefix)中輸入的命令何時會沙箱化執行，請參閱[嚴格沙箱模式](https://code.claude.com/docs/zh-TW/sandboxing.md#turn-off-the-retry-with-strict-sandbox-mode)。

### `sandbox.filesystem`

控制沙箱化命令可以讀取和寫入哪些路徑。預設情況下，它們可以寫入工作目錄、每位使用者的暫存目錄，以及您透過 `--add-dir`、`/add-dir` 或 `permissions.additionalDirectories` 新增的目錄，並且可以讀取檔案系統的其餘部分，包括憑證檔案。您可以使用四個路徑清單擴大或縮小此範圍，或使用 `disabled` 關閉檔案系統層。關於預設邊界，請參閱[檔案系統隔離](https://code.claude.com/docs/zh-TW/sandboxing.md#filesystem-isolation)。

* **範圍**：[`Any file`](#scopes)
* **類型**：包含 `allowWrite`、`denyWrite`、`denyRead` 和 `allowRead` 陣列，以及 `allowManagedReadPathsOnly` 和 `disabled` 布林值的物件
* **預設值**：未設定，因此套用預設的讀取和寫入邊界

以下設定讓沙箱化命令可以寫入建置目錄和您的 kubeconfig，並隱藏您的 AWS 憑證檔案：

```json settings.json theme={null}
{
  "sandbox": {
    "filesystem": {
      "allowWrite": ["/tmp/build", "~/.kube"],
      "denyRead": ["~/.aws/credentials"]
    }
  }
}
```

Claude Code 在作業系統沙箱邊界上強制執行這些清單，因此它們適用於沙箱化命令所啟動的每個子程序，例如 `kubectl`、`terraform` 或 `npm`。Claude Code 會將您的[權限規則](https://code.claude.com/docs/zh-TW/sandboxing.md#permission-rules)加入相同的清單：`Edit` 允許和拒絕規則加入 `allowWrite` 和 `denyWrite`，`Read` 拒絕規則加入 `denyRead`，而 `WebFetch(domain:...)` 允許和拒絕規則則加入 [`network`](#sandbox-network) 網域清單。

除非有鎖定適用，否則 Claude Code 會在工作階段載入的所有設定檔之間合併這些清單。[`allowManagedReadPathsOnly`](#sandbox-filesystem-allowmanagedreadpathsonly) 會將 `allowRead` 限制為來自受管設定的項目，而 [`allowManagedDomainsOnly`](#sandbox-network-allowmanageddomainsonly) 則對允許的網域執行相同的限制。[儲存庫鎖定](https://code.claude.com/docs/zh-TW/sandboxing.md#repository-settings-under-an-admin-required-sandbox)會排除來自儲存庫設定檔的項目。

[設定沙箱機制](https://code.claude.com/docs/zh-TW/sandboxing.md#configure-sandboxing)涵蓋您使用 `--setting-sources` 排除的來源。當您在工作階段期間編輯清單時，Claude Code 會[將變更套用至執行中的工作階段](https://code.claude.com/docs/zh-TW/settings.md#when-edits-take-effect)。

#### 沙箱路徑前綴

`allowWrite`、`denyWrite`、`denyRead`、`allowRead` 和 [`credentials.files`](#sandbox-credentials-files) 中的路徑會依其前綴解析：

| 前綴 | 意義 | 範例 |
| :- | :- | :- |
| `/` | 從檔案系統根目錄起算的絕對路徑 | `/tmp/build` 維持為 `/tmp/build` |
| `~/` | 相對於家目錄 | `~/.kube` 變成 `$HOME/.kube` |
| `./` 或無前綴 | 在專案設定中相對於專案根目錄，在使用者設定中相對於 `~/.claude` | `.claude/settings.json` 中的 `./output` 解析為 `<project-root>/output` |

絕對路徑使用 `//path` 前綴也可以。如果您使用單斜線 `/path` 並期望以專案相對方式解析，請改用 `./path`。此語法與 [Read 和 Edit 權限規則](https://code.claude.com/docs/zh-TW/permissions.md#read-and-edit)不同，後者使用 `//path` 表示絕對路徑，`/path` 表示專案相對路徑：沙箱檔案系統路徑使用標準慣例，因此 `/tmp/build` 是絕對路徑。

Claude Code 會移除目錄路徑結尾的斜線，因此 `~/.aws` 和 `~/.aws/` 會比對到相同的目錄。在 v2.1.224 之前，Claude Code 會將結尾斜線原樣傳給沙箱，因此對於以結尾斜線撰寫的 `denyRead` 或 `denyWrite` 項目，Claude 仍可讀取或寫入其下的路徑。

##### 萬用字元在沙箱路徑中的適用之處

萬用字元 `*`、`?` 和 `**` 在 macOS 上適用於全部四個 `sandbox.filesystem` 路徑清單，在 Linux 和 WSL2 上則適用於較少的位置：

| `sandbox.filesystem` 清單 | 在 Linux 和 WSL2 上可用的寫法 | 在 Linux 和 WSL2 上無效的範例 | 應改寫為 |
| :- | :- | :- | :- |
| `denyRead`、`allowRead` | 結尾的 `/**` 可用，因此 `~/build/**` 涵蓋與 `~/build` 相同的目錄。其他萬用字元只有在項目[完整路徑](#sandbox-path-prefixes)的第一個目錄名稱之後才有效。 | `denyRead` 中的 `/**/*.pem` 不涵蓋任何內容，因此不會封鎖任何讀取 | `/srv/**/*.pem`，每個最上層目錄各一個項目 |
| `allowWrite`、`denyWrite` | 只有結尾的 `/**` 可用，因此 `~/build/**` 涵蓋與 `~/build` 相同的目錄 | `./src/*` 只涵蓋 `src` 中本身名為 `*` 的檔案或目錄，若不存在則不涵蓋任何內容 | `./src`，涵蓋 `src` 底下的所有內容，或每個路徑各一個項目 |

在 `~/keys/*.pem` 中，萬用字元位於第一個目錄名稱之後；對於家目錄為 `/home/alice` 的情況，第一個目錄名稱為 `home`：

```text theme={null}
~/keys/*.pem              the entry
/home/alice/keys/*.pem    its full path
 ^^^^                     the first directory name, home
```

在 Linux 和 WSL2 上，工作階段中 `/sandbox` 的 **Config** 分頁會對包含結尾 `/**` 以外萬用字元的 `Edit` 權限規則發出警告。這些萬用字元對沙箱化命令無效。請將規則應涵蓋的每個路徑，或包含它們的目錄，加入 `allowWrite`（對應允許規則）或 `denyWrite`（對應拒絕規則）。

##### 名稱包含方括號、大括號或圓括號的目錄

若要允許或封鎖名稱包含方括號的目錄，請照原樣寫出名稱，例如 `./app/[slug]`。在該項目中，`[slug]` 是目錄的實際名稱，包含方括號：

```text theme={null}
app/
└── [slug]/
    └── page.tsx
```

該項目會涵蓋目錄底下的所有內容，因此請勿加上結尾的 `/**`。在 macOS 以及 Linux 和 WSL2 上，`app/[slug]` 目錄必須在沙箱化命令啟動時就已存在。

* **如 `[slug]` 的方括號**：在 macOS 的每個清單中，以及 Linux 和 WSL2 的 `denyRead` 和 `allowRead` 中，`./app/[slug]` 中的方括號同時也是一個模式。此時該項目也會比對 `app` 底下以 `slug` 中任一字元命名的路徑，例如 `app/s` 或 `app/g`。當該項目位於 `allowRead` 中，或在 macOS 上位於 `allowWrite` 中時，沙箱化命令也能存取這些路徑。請重新命名任何它們不應存取的路徑。
* **如 `[user-id]` 或 `[post-id]` 的方括號，其中連字號左側字元的排序在右側字元之後**：`./app/[user-id]` 在每個平台的每個清單中都只涵蓋名稱完全相同的目錄。在 v2.1.304 之前，當 `denyRead` 或 `allowRead` 包含此類項目時，Linux 和 WSL2 上的沙箱化命令會無法啟動。
* **大括號和圓括號**：這些是一般字元，因此 `~/data/{keys,tokens}` 涵蓋一個名為 `{keys,tokens}` 的目錄，而非兩個替代選項。若要涵蓋 `~/data/keys` 和 `~/data/tokens`，請將兩者各自新增為獨立項目。

### `sandbox.filesystem.allowWrite`

新增沙箱化命令可以寫入的路徑，範圍超出工作目錄、每位使用者的暫存目錄，以及您透過 `--add-dir`、`/add-dir` 或 `permissions.additionalDirectories` 新增的目錄。當 `kubectl` 或建置工具等子程序需要寫入專案外部時，請使用此項。

* **範圍**：[`Any file`](#scopes)，但[對專案和本機設定有所限制](https://code.claude.com/docs/zh-TW/sandboxing.md#repository-settings-under-an-admin-required-sandbox)
* **類型**：路徑字串的陣列，使用[沙箱路徑前綴](#sandbox-path-prefixes)
* **預設值**：未設定，因此沙箱化命令可以寫入工作目錄、每位使用者的暫存目錄、您透過 `--add-dir` 或 `/add-dir` 新增的目錄，以及 [`permissions.additionalDirectories`](#permissions-additionaldirectories) 中的目錄

以下設定讓建置可以寫入 `/tmp/build` 底下，並讓 `kubectl` 更新您的 kubeconfig：

```json settings.json theme={null}
{
  "sandbox": {
    "filesystem": {
      "allowWrite": ["/tmp/build", "~/.kube"]
    }
  }
}
```

Claude Code 會在工作階段載入的所有設定範圍之間合併 `allowWrite` 項目，以及您 `Edit(...)` 允許權限規則中的路徑；當 [`permissions.blockReadsOutsideWorkingDirectories`](#sandboxed-commands-under-the-block) 開啟時，會排除來自儲存庫設定的項目。[儲存庫鎖定](https://code.claude.com/docs/zh-TW/sandboxing.md#repository-settings-under-an-admin-required-sandbox)也可能排除儲存庫的項目。`allowWrite` 項目無法解除[受保護路徑](https://code.claude.com/docs/zh-TW/sandboxing.md#protected-paths)的限制。

### `sandbox.filesystem.denyWrite`

封鎖沙箱化命令寫入特定路徑，包括原本可寫入之目錄內的路徑。

* **範圍**：[`Any file`](#scopes)
* **類型**：路徑字串的陣列，使用[沙箱路徑前綴](#sandbox-path-prefixes)
* **預設值**：未設定

以下設定可防止沙箱化命令變更系統設定或安裝二進位檔：

```json settings.json theme={null}
{
  "sandbox": {
    "filesystem": {
      "denyWrite": ["/etc", "/usr/local/bin"]
    }
  }
}
```

Claude Code 會在工作階段載入的所有設定範圍之間合併項目，並加入您 `Edit(...)` 拒絕權限規則中的路徑。

### `sandbox.filesystem.denyRead`

封鎖沙箱化命令讀取特定路徑，例如預設讀取政策原本會公開的憑證檔案。若要保護憑證檔案，同時讓它仍可透過沙箱代理伺服器使用，請改為參閱 [`sandbox.credentials`](#sandbox-credentials)。

* **範圍**：[`Any file`](#scopes)
* **類型**：路徑字串的陣列，使用[沙箱路徑前綴](#sandbox-path-prefixes)
* **預設值**：未設定，因此沙箱化命令保有[預設讀取存取權](https://code.claude.com/docs/zh-TW/sandboxing.md#filesystem-isolation)，其中包括 `~/.aws/credentials` 等憑證檔案

```json settings.json theme={null}
{
  "sandbox": {
    "filesystem": {
      "denyRead": ["~/.aws/credentials"]
    }
  }
}
```

Claude Code 會在工作階段載入的所有設定範圍之間合併項目，並加入您 `Read(...)` 拒絕權限規則中的路徑。當 [`filesystem.disabled`](#sandbox-filesystem-disabled) 為 `true` 時，Claude Code 不會強制執行這些項目。

### `sandbox.filesystem.allowRead`

在 [`denyRead`](#sandbox-filesystem-denyread) 封鎖的區域內重新開放特定路徑的讀取，以建立僅限工作區的讀取存取權。確切或萬用字元形式的 `denyRead` 項目即使位於範圍更廣的 `allowRead` 內，仍會保持封鎖，如[重疊表](https://code.claude.com/docs/zh-TW/sandboxing.md#configure-sandboxing)所示。當 `~/**/.env` 等萬用字元 `denyRead` 項目比對到某個目錄時，Claude Code 也會封鎖對其內容的讀取。在 v2.1.236 之前的 macOS 上，只要範圍更廣的 `allowRead` 項目涵蓋了萬用字元 `denyRead` 項目所比對到的路徑，Claude Code 就會重新開放這些路徑，並讓被比對到之目錄的內容保持可讀取。

* **範圍**：[`Any file`](#scopes)，但[對專案和本機設定有所限制](https://code.claude.com/docs/zh-TW/sandboxing.md#repository-settings-under-an-admin-required-sandbox)
* **類型**：路徑字串的陣列，使用[沙箱路徑前綴](#sandbox-path-prefixes)
* **預設值**：未設定

以下設定會封鎖對家目錄的讀取，但專案本身除外：

```json settings.json theme={null}
{
  "sandbox": {
    "filesystem": {
      "denyRead": ["~/"],
      "allowRead": ["."]
    }
  }
}
```

Claude Code 在專案設定中會將 `.` 項目解析為專案根目錄，在使用者設定中則解析為 `~/.claude`。除非設定了 [`allowManagedReadPathsOnly`](#sandbox-filesystem-allowmanagedreadpathsonly)，否則 Claude Code 會在工作階段載入的所有設定檔之間合併項目；當 [`permissions.blockReadsOutsideWorkingDirectories`](#sandboxed-commands-under-the-block) 開啟時，會排除來自儲存庫設定的項目。[儲存庫鎖定](https://code.claude.com/docs/zh-TW/sandboxing.md#repository-settings-under-an-admin-required-sandbox)也可能排除儲存庫的項目。

### `sandbox.filesystem.allowManagedReadPathsOnly`

僅採用來自受管設定的 [`allowRead`](#sandbox-filesystem-allowread) 項目，讓開發人員無法重新開放您組織已封鎖之路徑的讀取存取權。Claude Code 仍會合併工作階段載入之所有設定範圍中的 `denyRead` 項目。

* **範圍**：[`Managed`](#scopes)
* **類型**：布林值
  * `true`：Claude Code 僅採用來自受管設定的 `allowRead` 項目
  * `false`：來自其他設定檔的 `allowRead` 項目可以合併進來
* **預設值**：`false`

以下設定會封鎖對家目錄的讀取、重新開放 `~/work`，並阻止開發人員重新開放任何其他路徑：

```json managed-settings.json theme={null}
{
  "sandbox": {
    "filesystem": {
      "denyRead": ["~/"],
      "allowRead": ["~/work"],
      "allowManagedReadPathsOnly": true
    }
  }
}
```

請參閱[防止開發人員擴大政策](https://code.claude.com/docs/zh-TW/sandboxing.md#keep-developers-from-widening-the-policy)。

### `sandbox.filesystem.disabled`

略過檔案系統隔離，同時保留網路隔離。沙箱化命令可不受限制地讀取和寫入主機檔案系統，而其網路輸出流量仍限於 [`network.allowedDomains`](#sandbox-network-alloweddomains)。當您使用沙箱是為了控制命令連線的目的地，而非它們寫入的內容時，請使用此設定。

* **範圍**：[`User or managed`](#scopes)。當受管設定有任何 `sandbox.filesystem` 設定，或列出 `"mode": "deny"` 的 `sandbox.credentials.files` 項目時，只有受管設定能設定此項。
* **類型**：布林值
  * `true`：Claude Code 略過檔案系統隔離，並保留網路隔離
  * `false`：檔案系統隔離保持開啟
* **預設值**：`false`，因此檔案系統隔離保持開啟

以下設定會讓檔案系統保持開放，並將網路輸出流量限制在 GitHub 和 npm：

```json settings.json theme={null}
{
  "sandbox": {
    "enabled": true,
    "filesystem": {
      "disabled": true
    },
    "network": {
      "allowedDomains": ["github.com", "*.npmjs.org"]
    }
  }
}
```

關閉此層後，Claude Code 不會強制執行 `denyRead` 或 `credentials.files` 的 `deny` 項目，而 `credentials.envVars` 項目和已套用的 `mask` 項目則會繼續運作。[`autoAllowBashIfSandboxed`](#sandbox-autoallowbashifsandboxed) 的預設值仍為 `true`，因此若要繼續提示，請將其設為 `false`。關於可設定此鍵的完整來源清單以及關閉隔離後的變化，請參閱 [停用檔案系統隔離](https://code.claude.com/docs/zh-TW/sandboxing.md#disable-filesystem-isolation)。

### `sandbox.ignoreViolations`

針對您預期命令會探測並遭拒的路徑（例如在啟動時檢查 `/etc/hosts` 的工具），隱藏沙箱違規報告，讓這些拒絕不會顯示為違規，也不會出現在 Claude 看到的內容中。沙箱仍會封鎖該存取；只有報告會被隱藏。鍵是用來比對命令的子字串，`*` 會比對所有命令；值則是該命令要忽略之違規的子字串，例如檔案系統路徑。

* **範圍**：[`Any file`](#scopes)，但[對專案和本機設定有所限制](https://code.claude.com/docs/zh-TW/sandboxing.md#repository-settings-under-an-admin-required-sandbox)
* **類型**：將命令子字串對應到違規子字串（通常為路徑）陣列的物件
* **預設值**：未設定，因此會回報每個違規

```json settings.json theme={null}
{
  "sandbox": {
    "ignoreViolations": {
      "*": ["/etc/hosts"]
    }
  }
}
```

### `sandbox.enableWeakerNestedSandbox`

在無特權的 Docker 容器內執行 Linux 沙箱，在這種環境中 bubblewrap 無法掛載新的 `/proc`。取而代之的是，內層沙箱會 bind-mount 容器現有的 `/proc`，這會公開新掛載原本會隱藏的程序資訊。這會降低安全性；請僅在外層容器已提供您所需的隔離時使用。

* **範圍**：[`Any file`](#scopes)，但[對專案和本機設定有所限制](https://code.claude.com/docs/zh-TW/sandboxing.md#repository-settings-under-an-admin-required-sandbox)
* **類型**：布林值
  * `true`：內層沙箱會 bind-mount 容器現有的 `/proc`，而不是掛載新的 `/proc`
  * `false`：沙箱會掛載新的 `/proc`，這在無特權的 Docker 容器中無法運作
* **預設值**：`false`

```json settings.json theme={null}
{
  "sandbox": {
    "enabled": true,
    "enableWeakerNestedSandbox": true
  }
}
```

僅限 Linux 和 WSL2。請參閱[Bubblewrap 無法在容器內啟動](https://code.claude.com/docs/zh-TW/sandboxing.md#bubblewrap-fails-to-start-inside-a-container)。

### `sandbox.enableWeakerNetworkIsolation`

讓 macOS 上的沙箱化命令可以存取系統 TLS 信任服務 `com.apple.trustd.agent`。當您將 [`network.httpProxyPort`](#sandbox-network-httpproxyport) 與 MITM 代理伺服器和自訂 CA 搭配使用時，`gh`、`gcloud` 和 `terraform` 等以 Go 撰寫的工具需要此項才能驗證 TLS 憑證。這會透過信任服務開啟潛在的資料外洩途徑，因而降低安全性。

* **範圍**：[`Any file`](#scopes)，但[對專案和本機設定有所限制](https://code.claude.com/docs/zh-TW/sandboxing.md#repository-settings-under-an-admin-required-sandbox)
* **類型**：布林值
  * `true`：macOS 上的沙箱化命令可以存取 `com.apple.trustd.agent`
  * `false`：macOS 上的沙箱化命令無法存取系統 TLS 信任服務
* **預設值**：`false`

```json settings.json theme={null}
{
  "sandbox": {
    "enabled": true,
    "enableWeakerNetworkIsolation": true
  }
}
```

如果您沒有使用 MITM 代理伺服器，請改為將失敗的工具列於 [`excludedCommands`](#sandbox-excludedcommands) 中；請參閱[以 Go 撰寫的 CLI 在 macOS 上 TLS 驗證失敗](https://code.claude.com/docs/zh-TW/sandboxing.md#go-based-clis-fail-tls-verification-on-macos)。

### `sandbox.allowAppleEvents`

讓 macOS 上的沙箱化命令可以傳送 Apple Events，`open`、`osascript` 以及在瀏覽器中開啟 URL 的工具都需要此功能；若未設定，它們會以錯誤 `-600` 失敗。這會移除程式碼執行隔離：沙箱化命令可以在沒有使用者提示的情況下於沙箱外啟動其他應用程式，並可以向執行中的應用程式（例如 Terminal）傳送 AppleScript 命令，但仍受各應用程式的 macOS 自動化同意提示（TCC）約束。

* **範圍**：[`User or managed`](#scopes)
* **類型**：布林值
  * `true`：macOS 上的沙箱化命令可以傳送 Apple Events
  * `false`：macOS 上的沙箱化命令無法傳送 Apple Events，因此 `open` 和 `osascript` 會以錯誤 `-600` 失敗
* **預設值**：`false`

```json settings.json theme={null}
{
  "sandbox": {
    "enabled": true,
    "allowAppleEvents": true
  }
}
```

若要保留隔離，同時仍能執行某個此類工具，請改為將其加入 [`excludedCommands`](#sandbox-excludedcommands)。請參閱[macOS 上的 Apple Events](https://code.claude.com/docs/zh-TW/sandboxing.md#security-limitations)。

### `sandbox.allowNestedUserNamespaces`

讓 Linux 和 WSL2 上的沙箱化命令可以建立使用者命名空間，Chromium 和 Electron 本身的沙箱、巢狀 bubblewrap 以及 `unshare` 都需要它。如果您將此鍵設為 `true`，就會關閉一道安全邊界：來自沙箱化命令的程式碼最終可能在沙箱外執行。對於 rootless Podman 或 Buildah，請改用 [`excludedCommands`](#sandbox-excludedcommands)，因為沙箱也會以其他方式阻擋它們。需要 Claude Code v2.1.305 或更新版本。

* **範圍**：[`User or managed`](#scopes)。`true` 僅在來自 `~/.claude/settings.json`、透過 `--settings` 傳入的 JSON 或[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)時有效。Claude Code 會忽略專案的 `.claude/settings.json` 或 `.claude/settings.local.json` 中的 `true`。在 [`CLAUDE_CODE_SUBPROCESS_ENV_SCRUB`](https://code.claude.com/docs/zh-TW/env-vars#variables) 設為 `1` 的工作階段中，Claude Code 會忽略來自所有來源的 `true`。`false` 來自任何檔案皆有效，依[設定優先順序](https://code.claude.com/docs/zh-TW/settings.md#settings-precedence)決定。
* **類型**：Boolean
  * `true`：沙箱化命令可以建立使用者命名空間
  * `false`：此鍵不額外允許任何事項，套用沙箱的預設行為
* **預設值**：`false`

```json settings.json theme={null}
{
  "sandbox": {
    "enabled": true,
    "allowNestedUserNamespaces": true
  }
}
```

開啟此鍵時，請勿依賴沙箱的任何限制（包括[受保護路徑](https://code.claude.com/docs/zh-TW/sandboxing.md#protected-paths)和 [`credentials.files`](#sandbox-credentials-files) 項目）來阻止惡意命令。在[自動允許模式](https://code.claude.com/docs/zh-TW/sandboxing.md#auto-allow-mode)下，該命令可以在沒有權限提示的情況下執行。如果您的組織有資安團隊，請在開啟此鍵前與他們確認。

若要找到適用於您工具的修正方法，請參閱[Chromium 或 rootless Podman 在 Linux 上的沙箱內失敗](https://code.claude.com/docs/zh-TW/sandboxing.md#chromium-or-rootless-podman-fails-inside-the-sandbox-on-linux)。

### `sandbox.ripgrep`

讓沙箱使用您自己的 ripgrep 二進位檔，而非 Claude Code 使用的那一個，例如當您的平台需要以不同方式建置的 `rg` 時。

* **範圍**：[`User or managed`](#scopes)
* **類型**：包含 `command`（ripgrep 二進位檔的路徑）和選用 `args`（要前置的引數陣列）的物件
* **預設值**：未設定，因此沙箱使用與 Claude Code 相同的 ripgrep 二進位檔。除非您將 [`USE_BUILTIN_RIPGREP`](https://code.claude.com/docs/zh-TW/env-vars) 設為 `0`，否則即為內建的二進位檔

```json settings.json theme={null}
{
  "sandbox": {
    "ripgrep": {
      "command": "/usr/local/bin/rg"
    }
  }
}
```

### `sandbox.bwrapPath`

讓沙箱使用安裝在 `PATH` 以外的 bubblewrap 二進位檔，例如離線主機上的內附副本。Claude Code 在啟動時的相依性檢查以及包裝每個沙箱化命令時都會使用此路徑。

* **範圍**：[`Managed`](#scopes)。Claude Code 只從受管設定讀取此項，使使用者、專案或本機檔案無法讓沙箱指向不同的二進位檔。
* **類型**：字串，必須是絕對路徑；Claude Code 會捨棄相對路徑並改用 `PATH` 查找
* **預設值**：未設定，因此 Claude Code 會在 `PATH` 上尋找 `bwrap`

```json managed-settings.json theme={null}
{
  "sandbox": {
    "enabled": true,
    "bwrapPath": "/opt/admin/bwrap"
  }
}
```

僅限 Linux 和 WSL2。

### `sandbox.socatPath`

讓沙箱網路代理伺服器使用安裝在 `PATH` 以外的 `socat` 二進位檔。

* **範圍**：[`Managed`](#scopes)
* **類型**：字串，必須是絕對路徑；Claude Code 會捨棄相對路徑並改用 `PATH` 查找
* **預設值**：未設定，因此 Claude Code 會在 `PATH` 上尋找 `socat`

```json managed-settings.json theme={null}
{
  "sandbox": {
    "enabled": true,
    "socatPath": "/opt/admin/socat"
  }
}
```

僅限 Linux 和 WSL2。

### `sandbox.credentials`

宣告要[防止沙箱化命令存取](https://code.claude.com/docs/zh-TW/sandboxing.md#protect-credentials)的憑證檔案和環境變數。每個項目指定一個檔案 `path` 或變數 `name` 以及一個 `mode`：`deny` 會在沙箱內隱藏該憑證，而 `mask` 會向沙箱化命令顯示預留位置值，並由[沙箱代理伺服器](https://code.claude.com/docs/zh-TW/sandboxing.md#mask-credentials)在外送請求中替換為真實值。Claude Code 只會保護您列出的項目；沒有內建的憑證拒絕清單。

* **範圍**：[`Any file`](#scopes)。Claude Code 只會採用來自使用者設定、受管設定和 `--settings` 旗標的 `mask` 項目、`allowPlaintextInject`、`awsPairs` 和 `sigv4`。
* **類型**：包含 `files`、`envVars`、`allowPlaintextInject`、`awsPairs` 和 `sigv4` 的物件
* **預設值**：未設定，因此不保護任何憑證

以下設定會隱藏您的 AWS 憑證檔案，並從沙箱化命令中移除 `GITHUB_TOKEN`：

```json settings.json theme={null}
{
  "sandbox": {
    "credentials": {
      "files": [{ "path": "~/.aws/credentials", "mode": "deny" }],
      "envVars": [{ "name": "GITHUB_TOKEN", "mode": "deny" }]
    }
  }
}
```

`deny` 檔案保護屬於檔案系統層，因此當您[停用檔案系統隔離](https://code.claude.com/docs/zh-TW/sandboxing.md#disable-filesystem-isolation)時不適用；環境變數保護則仍然適用。

#### 受管設定中的無效憑證項目

當受管的 `sandbox.credentials` 項目未通過驗證時，Claude Code 會盡可能持續保護該憑證：

* `files` 或 `envVars` 中仍具有有效 `path` 或 `name`，且 `mode` 為 `mask` 或 `deny` 的項目（例如其 `extract` 模式沒有擷取群組），會被降級為 `mode: "deny"` 並顯示警告，因此在您修正該項目之前，憑證會保持封鎖而非遮罩。降級的 `files` 項目會像明確的 `deny` 項目一樣鎖定 [`filesystem.disabled`](https://code.claude.com/docs/zh-TW/sandboxing#disable-filesystem-isolation)，且警告會註明，若受管設定關閉檔案系統隔離，其讀取封鎖將不會強制執行。
* 具有未知 `mode` 或無效 `path` 或 `name` 的項目會被移除。
* 每種情況都會發出警告；無論項目是被降級或移除，其餘有效項目仍會強制執行。

適用於 v2.1.191 及更新版本；在 v2.1.221 之前，每個無效項目都會被移除。關於其他具有逐欄位處理方式的受管鍵，請參閱[受管設定中的無效項目](https://code.claude.com/docs/zh-TW/managed-settings.md#invalid-entries-in-managed-settings)。

### `sandbox.credentials.files`

保護憑證檔案或目錄，使沙箱化命令無法存取。使用 `"mode": "deny"` 時，Claude Code 會在沙箱內封鎖對該路徑的讀取，與 [`sandbox.filesystem.denyRead`](#sandbox-filesystem-denyread) 的讀取封鎖相同。使用 `"mode": "mask"` 時，Linux 和 WSL2 上的沙箱化命令會讀取該檔案的哨兵副本，並由沙箱代理伺服器在送往該項目 `injectHosts` 的外送請求中替換為真實值；在 macOS 上，該檔案在沙箱內則無法讀取。`"mode": "mask"` 需要 Claude Code v2.1.221 或更新版本。

* **範圍**：[`Any file`](#scopes)。Claude Code 會捨棄來自專案 `.claude/settings.json` 和本機 `.claude/settings.local.json` 的 `mask` 項目。
* **類型**：物件陣列，每個物件包含 `path` 和值為 `"deny"` 或 `"mask"` 的 `mode`，以及選用的[檔案遮罩欄位](#mask-fields-for-files)
* **預設值**：未設定，因此不保護任何憑證檔案

以下設定會隱藏您的 AWS 憑證檔案並遮罩 `gh` hosts 檔案，僅在送往 `api.github.com` 的請求中替換為真實值：

```json settings.json theme={null}
{
  "sandbox": {
    "credentials": {
      "files": [
        { "path": "~/.aws/credentials", "mode": "deny" },
        { "path": "~/.config/gh/hosts.yml", "mode": "mask", "injectHosts": ["api.github.com"] }
      ]
    }
  }
}
```

路徑使用與 `sandbox.filesystem.*` 設定相同的[前綴](#sandbox-path-prefixes)，且 Claude Code 會合併工作階段載入之所有設定範圍中的陣列。[保護憑證](https://code.claude.com/docs/zh-TW/sandboxing.md#protect-credentials)說明了對於您使用 `--setting-sources` 排除的來源，哪些設定仍然適用。`mask` 項目需要 Claude Code v2.1.221 或更新版本。

`mask` 替換只會透過沙箱代理伺服器執行，因此請設定 [`sandbox.network.tlsTerminate`](#sandbox-network-tlsterminate)，或針對純 HTTP 測試網路設定 [`allowPlaintextInject`](#sandbox-credentials-allowplaintextinject)。`mask` 適用於單一檔案，因此請個別列出每個憑證檔案。Claude Code 接受但會忽略 `deny` 項目上的 `mask` 欄位。[遮罩憑證](https://code.claude.com/docs/zh-TW/sandboxing.md#mask-credentials)說明了會採用哪些設定來源，而[遮罩憑證檔案](https://code.claude.com/docs/zh-TW/sandboxing.md#mask-credential-files)說明了項目何時會退回為 `deny`。

#### 檔案遮罩欄位

`mask` 項目接受下列選用欄位。若沒有 `extract` 或 `decode`，Claude Code 會以單一哨兵值取代整個檔案內容。在開啟檔案系統隔離的 macOS 上，Claude Code 會在 `extract` 或 `decode` 執行之前將 `mask` 項目當作 `deny` 套用；請參閱[遮罩憑證檔案](https://code.claude.com/docs/zh-TW/sandboxing.md#mask-credential-files)。

| 欄位 | 類型 | 作用 |
| :- | :- | :- |
| `extract` | 字串，至少包含一個擷取群組的正規表示式 | 只遮罩每個比對中群組 1 擷取到的文字，讓檔案的其餘部分仍可剖析。若同時設定了 `decode`，Claude Code 會檢查每個擷取內容是否可能是 JWT，而非直接取代。需要 v2.1.221 或更新版本 |
| `onExtractNoMatch` | `"warn"`、`"deny"` 或 `"error"`；預設為 `"warn"` | 當 `extract` 或 `decode` 找不到要遮罩的內容時會發生什麼。`warn` 會讓檔案在沙箱內維持原樣可讀取，`deny` 會讓檔案無法讀取，而 `error` 會停止沙箱設定，直到您修正設定為止。當讀取封鎖不會被強制執行時（因為您[停用檔案系統隔離](https://code.claude.com/docs/zh-TW/sandboxing.md#disable-filesystem-isolation)，或 [`sandbox.filesystem.allowRead`](#sandbox-filesystem-allowread) 項目重新開放了該路徑），Claude Code 會將 `deny` 視為 `error`。需要 v2.1.221 或更新版本；`decode` 的情況需要 v2.1.224 或更新版本 |
| `decode` | 字串 `"jwt"` | 使用內建模式（或在設定時使用 `extract`）在檔案中尋找 JSON Web Token（JWT），驗證每個候選項目，並以結構有效的假 token 取代，讓沙箱內解碼該 token 的程式碼能繼續運作。當沒有任何候選項目通過驗證時，由 `onExtractNoMatch` 決定結果。需要 v2.1.224 或更新版本 |
| `maskClaims` | 字串陣列，至少包含一個 claim 名稱；需要 `decode` | 只遮罩每個已驗證 JWT 中指定的頂層 payload claim，並以修改後的 payload 重建 token，讓其他 claim 保持可讀。當沒有任何指定的 claim 符合時，由 `onExtractNoMatch` 決定結果。需要 v2.1.224 或更新版本 |
| `maskDuplicates` | 布林值，預設為 `false` | 同時取代檔案中其他位置每個遮罩值的逐字副本，例如貼在註解中的密鑰。Claude Code 比對的是原始子字串，因此請僅將其用於長且高熵的密鑰。僅在設定了 `extract` 或 `decode` 時才會參考。需要 v2.1.221 或更新版本 |
| `injectHosts` | 字串陣列，每個都是 [`sandbox.network.allowedDomains`](#sandbox-network-alloweddomains) 也允許的主機 | 縮小沙箱代理伺服器替換為真實值的主機範圍。未設定時，代理伺服器會在送往 `sandbox.network.allowedDomains` 中每個主機的請求中進行替換。需要 v2.1.221 或更新版本 |

以下設定只會遮罩 `gh` hosts 檔案中的 `oauth_token` 值、取代檔案中它的所有其他副本、在模式比對不到任何內容時讓檔案無法讀取，並僅在送往 `api.github.com` 的請求中替換為真實 token：

```json settings.json theme={null}
{
  "sandbox": {
    "credentials": {
      "files": [
        {
          "path": "~/.config/gh/hosts.yml",
          "mode": "mask",
          "extract": "oauth_token:\\s*(\\S+)",
          "maskDuplicates": true,
          "onExtractNoMatch": "deny",
          "injectHosts": ["api.github.com"]
        }
      ]
    }
  }
}
```

### `sandbox.credentials.envVars`

保護環境變數，使沙箱化命令無法存取。使用 `"mode": "deny"` 時，Claude Code 會從沙箱化命令的環境中移除該變數。使用 `"mode": "mask"` 時，沙箱化命令會看到每個工作階段專屬的哨兵值，並由沙箱代理伺服器在送往該項目 `injectHosts` 的外送請求中替換為真實值，因此 `gh` 和 `npm` 等工具可以在從不持有真實憑證的情況下持續通過驗證。

* **範圍**：[`Any file`](#scopes)。Claude Code 會捨棄來自專案 `.claude/settings.json` 和本機 `.claude/settings.local.json` 的 `mask` 項目。
* **類型**：物件陣列，每個物件包含 `name` 和值為 `"deny"` 或 `"mask"` 的 `mode`，以及選用的[環境變數遮罩欄位](#mask-fields-for-environment-variables)
* **預設值**：未設定，因此不保護任何環境變數

以下設定會從沙箱化命令中移除 `NPM_TOKEN` 並遮罩 `GITHUB_TOKEN`，僅在送往 `api.github.com` 的請求中替換為真實值：

```json settings.json theme={null}
{
  "sandbox": {
    "credentials": {
      "envVars": [
        { "name": "NPM_TOKEN", "mode": "deny" },
        { "name": "GITHUB_TOKEN", "mode": "mask", "injectHosts": ["api.github.com"] }
      ]
    }
  }
}
```

`name` 必須以字母或底線開頭，且只能包含字母、數字和底線。Claude Code 會合併工作階段載入之所有設定範圍中的陣列，當同一個變數同時以兩種模式出現時，會套用 `deny`。[保護憑證](https://code.claude.com/docs/zh-TW/sandboxing.md#protect-credentials)說明了對於您使用 `--setting-sources` 排除的來源，哪些設定仍然適用。

`mask` 替換只會透過沙箱代理伺服器執行，因此請設定 [`sandbox.network.tlsTerminate`](#sandbox-network-tlsterminate)，或針對純 HTTP 測試網路設定 [`allowPlaintextInject`](#sandbox-credentials-allowplaintextinject)；請參閱[遮罩憑證](https://code.claude.com/docs/zh-TW/sandboxing.md#mask-credentials)。Claude Code 接受但會忽略 `deny` 項目上的 `mask` 欄位。

#### 環境變數遮罩欄位

`mask` 項目接受下列選用欄位。若沒有 `extract` 或 `decode`，Claude Code 會以單一哨兵值取代整個值。`extract` 和 `decode` 不能在同一個項目上合併使用。

| 欄位 | 類型 | 作用 |
| :- | :- | :- |
| `extract` | 字串，至少包含一個擷取群組的正規表示式 | 只遮罩每個比對中群組 1 擷取到的文字，例如 `DATABASE_URL` 連線字串中的密碼，讓值的其餘部分仍可剖析。需要 v2.1.224 或更新版本 |
| `onExtractNoMatch` | `"warn"`、`"deny"` 或 `"error"`；預設為 `"warn"`。在具有 `decode` 的項目上，只接受 `"warn"` | 當 `extract` 比對不到任何內容時會發生什麼。`warn` 會讓變數未經遮罩直接傳遞，`deny` 會在沙箱內取消設定該變數，而 `error` 會停止沙箱設定，直到您修正設定為止。需要 v2.1.224 或更新版本 |
| `decode` | 字串 `"jwt"` | 驗證整個值是否為 JWT，並以結構有效的假 token 取代，讓沙箱內解碼該 token 的程式碼能繼續運作；代理伺服器會在輸出時替換為完整的真實 token。未通過驗證的值會未經遮罩直接傳遞並顯示警告。需要 v2.1.224 或更新版本 |
| `maskClaims` | 字串陣列，至少包含一個 claim 名稱；需要 `decode` | 只遮罩解碼後 JWT 中指定的頂層 payload claim，並以修改後的 payload 重建 token，讓其他 claim 保持可讀。當沒有任何指定的 claim 符合時，變數會未經遮罩直接傳遞並顯示警告。需要 v2.1.224 或更新版本 |
| `injectHosts` | 字串陣列，每個都是 [`sandbox.network.allowedDomains`](#sandbox-network-alloweddomains) 也允許的主機 | 縮小沙箱代理伺服器替換為真實值的主機範圍。未設定時，代理伺服器會在送往 `sandbox.network.allowedDomains` 中每個主機的請求中進行替換。IPv6 目的地請寫成不含括號的壓縮位址，例如 `"::1"`，而非加括號的形式；請參閱[`injectHosts` 中的 IPv6 目的地](https://code.claude.com/docs/zh-TW/sandboxing#ipv6-destinations-in-injecthosts) |

以下設定只會遮罩 `DATABASE_URL` 中的密碼、在模式比對不到任何內容時取消設定該變數，並遮罩 `SERVICE_JWT` 中的 JWT，同時讓 `api_key` 以外的所有 claim 保持可讀：

```json settings.json theme={null}
{
  "sandbox": {
    "credentials": {
      "envVars": [
        {
          "name": "DATABASE_URL",
          "mode": "mask",
          "extract": "://[^:]+:([^@]+)@",
          "onExtractNoMatch": "deny"
        },
        {
          "name": "SERVICE_JWT",
          "mode": "mask",
          "decode": "jwt",
          "maskClaims": ["api_key"]
        }
      ]
    }
  }
}
```

### `sandbox.credentials.allowPlaintextInject`

除了 TLS 終止的 HTTPS 之外，也允許在純 HTTP 請求上進行 `mask` 替換。在純 HTTP 上，上游身分未經驗證，且憑證會以明文傳輸，因此在受信任的測試網路以外請保持關閉。

* **範圍**：[`User or managed`](#scopes)
* **類型**：布林值
  * `true`：Claude Code 除了 TLS 終止的 HTTPS 之外，也允許在純 HTTP 請求上進行 `mask` 替換
  * `false`：Claude Code 僅允許在 TLS 終止的 HTTPS 上進行 `mask` 替換
* **預設值**：`false`

```json settings.json theme={null}
{
  "sandbox": {
    "credentials": {
      "allowPlaintextInject": true
    }
  }
}
```

### `sandbox.credentials.awsPairs`

當您的憑證存放在非標準名稱的變數中時，將構成一組 AWS 憑證的遮罩環境變數組合起來，以進行 [SigV4 重新簽署](https://code.claude.com/docs/zh-TW/sandboxing.md#re-sign-aws-requests)。當您遮罩傳統的 `AWS_ACCESS_KEY_ID`、`AWS_SECRET_ACCESS_KEY` 和 `AWS_SESSION_TOKEN` 三者的完整值時，Claude Code 會自動將它們連結，因此只有在使用其他名稱時才需要此鍵。需要 Claude Code v2.1.224 或更新版本。

* **範圍**：[`User or managed`](#scopes)
* **類型**：物件陣列，每個物件包含 `accessKeyIdVar`、`secretAccessKeyVar` 和選用的 `sessionTokenVar`，指定 `sandbox.credentials.envVars` 項目
* **預設值**：未設定，因此只會配對傳統的三者

以下設定會將三個自訂名稱的變數連結成一組 AWS 憑證以進行重新簽署：

```json settings.json theme={null}
{
  "sandbox": {
    "credentials": {
      "awsPairs": [
        {
          "accessKeyIdVar": "MY_KEY_ID",
          "secretAccessKeyVar": "MY_SECRET_KEY",
          "sessionTokenVar": "MY_SESSION_TOKEN"
        }
      ]
    }
  }
}
```

每個指定的變數都必須是 [`sandbox.credentials.envVars`](#sandbox-credentials-envvars) 中不含 `extract` 或 `decode` 的完整值 `mask` 項目，且在所有配對中只能填入一個欄位。以下規則也適用：

* 代理伺服器會在存取金鑰 ID 項目的 `injectHosts` 所列出的主機上重新簽署請求
* 設定 `sessionTokenVar` 時，代理伺服器會在重新簽署的請求中以 `x-amz-security-token` 傳送真實 token
* 在配對中指定任何傳統變數，都會取代自動配對

### `sandbox.credentials.sigv4`

選擇沙箱代理伺服器如何處理其[無法重新簽署](https://code.claude.com/docs/zh-TW/sandboxing.md#re-sign-aws-requests)的 AWS 請求形式：`streaming` 用於 aws-chunked 串流上傳，`presigned` 用於預先簽署的 URL，`sigv4a` 用於 SigV4A 非對稱簽章。這只適用於以遮罩配對之預留位置存取金鑰 ID 簽署的請求。需要 Claude Code v2.1.224 或更新版本。

* **範圍**：[`User or managed`](#scopes)
* **類型**：包含 `streaming`、`presigned` 和 `sigv4a` 的物件，每個值為下列其中之一：
  * `"deny"`：代理伺服器讓請求失敗
  * `"passthrough"`：代理伺服器轉送以遮罩預留位置值簽署的請求，因此工具會收到 AWS 本身的拒絕回應
* **預設值**：未設定，因此每種形式都是 `"deny"`

以下設定會轉送串流上傳，而不是在代理伺服器讓它們失敗：

```json settings.json theme={null}
{
  "sandbox": {
    "credentials": {
      "sigv4": {
        "streaming": "passthrough"
      }
    }
  }
}
```

使用 `deny` 時，代理伺服器會讓請求失敗。使用 `passthrough` 時，代理伺服器會轉送以遮罩預留位置值計算簽章的請求，因此 AWS 會拒絕它，呼叫端工具會收到 AWS 本身的回應，而不是代理伺服器錯誤。

### `sandbox.network`

控制沙箱化命令可以存取哪些主機、連接埠和 socket。沙箱會將外送流量透過強制執行這些清單的代理伺服器轉送；關於代理伺服器如何決定以及何時提示，請參閱[網路隔離](https://code.claude.com/docs/zh-TW/sandboxing.md#network-isolation)。

* **範圍**：[`Any file`](#scopes)。`strictAllowlist`、`allowManagedDomainsOnly` 和 `tlsTerminate` 讀取的來源較少，如其各自項目所述。
* **類型**：包含下列子鍵的物件
* **預設值**：未設定，因此不預先允許任何網域，並由您的權限模式決定[每個新主機的處理方式](https://code.claude.com/docs/zh-TW/sandboxing.md#hosts-outside-your-allowed-domains)

以下設定會預先允許 GitHub 和 npm、封鎖 `uploads.github.com`，並讓命令可以繫結到 localhost：

```json settings.json theme={null}
{
  "sandbox": {
    "network": {
      "allowedDomains": ["github.com", "*.npmjs.org"],
      "deniedDomains": ["uploads.github.com"],
      "allowLocalBinding": true
    }
  }
}
```

Claude Code 會在設定範圍之間合併陣列子鍵，因此除非有[儲存庫鎖定](https://code.claude.com/docs/zh-TW/sandboxing.md#repository-settings-under-an-admin-required-sandbox)適用，否則專案可以將網域加入您的使用者清單。`WebFetch(domain:...)` 允許和拒絕[權限規則](https://code.claude.com/docs/zh-TW/sandboxing.md#permission-rules)會加入相同的允許和拒絕清單。

### `sandbox.network.allowUnixSockets`

列出 macOS 上沙箱化命令可以連線的 Unix socket 路徑。Claude Code 在 Linux 和 WSL2 上會忽略此清單，因為 seccomp 篩選器無法檢查 socket 路徑；在這些平台上請改用 [`allowAllUnixSockets`](#sandbox-network-allowallunixsockets)。

* **範圍**：[`Any file`](#scopes)，但[對專案和本機設定有所限制](https://code.claude.com/docs/zh-TW/sandboxing.md#repository-settings-under-an-admin-required-sandbox)
* **類型**：字串陣列，每個都是 socket 路徑
* **預設值**：未設定，因此 macOS 沙箱會封鎖每個 Unix socket

```json settings.json theme={null}
{
  "sandbox": {
    "network": {
      "allowUnixSockets": ["~/.ssh/agent-socket"]
    }
  }
}
```

socket 路徑可能授予廣泛的存取權：例如，允許 `/var/run/docker.sock` 會讓沙箱化命令能夠控制 Docker daemon。請參閱[安全性限制](https://code.claude.com/docs/zh-TW/sandboxing.md#security-limitations)。

### `sandbox.network.allowAllUnixSockets`

讓沙箱化命令可以連線到每個 Unix socket。在 Linux 和 WSL2 上，沙箱的 [seccomp 篩選器](https://code.claude.com/docs/zh-TW/sandboxing.md#set-up-linux-and-wsl2)會封鎖 `socket(AF_UNIX, ...)` 呼叫，因此這是在這些平台上允許 Unix socket 的唯一方式。當篩選器不存在時（`/sandbox` 會在其 Dependencies 分頁中回報），沙箱不會封鎖 Unix socket 呼叫。關於篩選器的來源，請參閱[設定 Linux 和 WSL2](https://code.claude.com/docs/zh-TW/sandboxing.md#set-up-linux-and-wsl2)。

* **範圍**：[`Any file`](#scopes)，但[對專案和本機設定有所限制](https://code.claude.com/docs/zh-TW/sandboxing.md#repository-settings-under-an-admin-required-sandbox)
* **類型**：布林值
  * `true`：沙箱化命令可以連線到每個 Unix socket。在 Linux 和 WSL2 上，它們也可以連線到 VM socket，即 `AF_VSOCK` 位址系列
  * `false`：沙箱會封鎖 Unix socket 連線：在 macOS 上，`allowUnixSockets` 中的路徑除外；在 Linux 和 WSL2 上，則在 seccomp 過濾器存在時透過它封鎖
* **預設值**：`false`

```json settings.json theme={null}
{
  "sandbox": {
    "network": {
      "allowAllUnixSockets": true
    }
  }
}
```

在 WSL2 上，`true` 也會重新開放用來啟動 `cmd.exe` 和 `powershell.exe` 等 Windows 二進位檔的 interop socket。

### `sandbox.network.allowLocalBinding`

讓 macOS 上的沙箱化命令可以監聽網路連接埠（例如用來啟動開發伺服器），並連線到 localhost 上的任何連接埠。在非 loopback 位址上監聽的命令會接受來自其他機器的連線。此鍵在 Linux 和 WSL2 上沒有作用，因為在這些平台上每個沙箱化命令都有自己的 loopback 介面。若要從 Linux 或 WSL2 存取主機上的伺服器，請參閱[命令無法存取 localhost 上的伺服器](https://code.claude.com/docs/zh-TW/sandboxing.md#a-command-fails-to-reach-a-server-on-localhost)。

* **範圍**：[`Any file`](#scopes)，但[對專案和本機設定有所限制](https://code.claude.com/docs/zh-TW/sandboxing.md#repository-settings-under-an-admin-required-sandbox)
* **類型**：布林值
  * `true`：macOS 上的沙箱化命令可以在任何本機位址上監聽，並連線到 localhost 上的任何連接埠
  * `false`：macOS 上的沙箱化命令無法監聽連接埠，也無法直接連線到 localhost 上的伺服器
* **預設值**：`false`

```json settings.json theme={null}
{
  "sandbox": {
    "network": {
      "allowLocalBinding": true
    }
  }
}
```

### `sandbox.network.allowMachLookup`

列出 macOS 沙箱可查找的其他 XPC 與 Mach 服務名稱。透過 XPC 通訊的工具（例如 iOS Simulator 或 Playwright）需要將其服務列在此處。沙箱化命令可以存取沙箱外您所列出的每個服務，而沙箱[不會限制這些服務為這些命令執行的操作](https://code.claude.com/docs/zh-TW/sandboxing.md#security-limitations)。

* **範圍**：[`Any file`](#scopes)，但[對專案和本機設定有所限制](https://code.claude.com/docs/zh-TW/sandboxing.md#repository-settings-under-an-admin-required-sandbox)
* **類型**：字串陣列，每個都是服務名稱；單一結尾的 `*` 會比對前綴，單獨的 `"*"` 則會比對所有服務
* **預設值**：未設定

以下設定允許 `com.apple.CoreSimulator.` 前綴下的所有服務：

```json settings.json theme={null}
{
  "sandbox": {
    "network": {
      "allowMachLookup": ["com.apple.CoreSimulator.*"]
    }
  }
}
```

### `sandbox.network.allowedDomains`

預先允許沙箱化命令外送流量的網域，使沙箱不會針對這些網域顯示提示。`*.example.com` 等萬用字元會比對子網域，選用的 `:port` 後綴會將項目限制在單一連接埠；沒有連接埠的項目會比對所有連接埠。

* **範圍**：[`Any file`](#scopes)，但[對專案和本機設定有所限制](https://code.claude.com/docs/zh-TW/sandboxing.md#repository-settings-under-an-admin-required-sandbox)。設定了 [`allowManagedDomainsOnly`](#sandbox-network-allowmanageddomainsonly) 時，僅限受管設定。
* **類型**：字串陣列，每個都是網域、萬用字元模式或 IP 常值，可附加選用的 `:port` 後綴
* **預設值**：未設定，因此由您的權限模式決定[每個新主機的處理方式](https://code.claude.com/docs/zh-TW/sandboxing.md#hosts-outside-your-allowed-domains)

以下設定會在所有連接埠上預先允許 GitHub、每個 npm 子網域，以及僅在連接埠 443 上的一個 API 主機：

```json settings.json theme={null}
{
  "sandbox": {
    "network": {
      "allowedDomains": ["github.com", "*.npmjs.org", "api.example.com:443"]
    }
  }
}
```

IPv6 常值請以括號包住，並可附加選用的連接埠：`"[::1]"` 允許所有連接埠，`"[::1]:443"` 則允許單一連接埠。加括號的形式需要 Claude Code v2.1.229 或更新版本。請參閱[網域清單中的 IPv6 位址](https://code.claude.com/docs/zh-TW/sandboxing.md#ipv6-addresses-in-domain-lists)。

### `sandbox.network.deniedDomains`

封鎖沙箱化命令外送流量的網域，使用與 [`allowedDomains`](#sandbox-network-alloweddomains) 相同的萬用字元、連接埠和 IPv6 語法。即使 `allowedDomains` 項目也比對到某個被拒絕的網域，該網域仍會保持封鎖。

* **範圍**：[`Any file`](#scopes)
* **類型**：字串陣列，每個都是網域、萬用字元模式或 IP 常值，可附加選用的 `:port` 後綴
* **預設值**：未設定

```json settings.json theme={null}
{
  "sandbox": {
    "network": {
      "deniedDomains": ["sensitive.cloud.example.com"]
    }
  }
}
```

即使設定了 `allowManagedDomainsOnly`，Claude Code 仍會合併工作階段載入之所有設定來源中的此清單，因此開發人員始終可以收緊拒絕清單。關於 IPv6 常值，請參閱[網域清單中的 IPv6 位址](https://code.claude.com/docs/zh-TW/sandboxing.md#ipv6-addresses-in-domain-lists)。

以標示完整網域名稱的結尾句點撰寫的項目（例如 `example.com.`），會封鎖與 `example.com` 相同的連線。

### `sandbox.network.strictAllowlist`

拒絕沙箱化命令存取允許清單以外的主機，而不是提示要求核准。允許清單為 [`allowedDomains`](#sandbox-network-alloweddomains) 加上來自 `WebFetch(domain:...)` 允許規則的網域；設定了 [`allowManagedDomainsOnly`](#sandbox-network-allowmanageddomainsonly) 時，則僅為受管設定中的項目。[不需管理員強制要求沙箱即適用的鎖定](https://code.claude.com/docs/zh-TW/sandboxing.md#locks-that-apply-without-an-admin-required-sandbox)說明了儲存庫項目的處理方式。需要 Claude Code v2.1.219 或更新版本。

* **範圍**：[`User or managed`](#scopes)。儲存庫無法開啟或關閉此項。
* **類型**：布林值
  * `true`：Claude Code 拒絕沙箱化命令存取允許清單以外的主機
  * `false`：除非另一個受信任的設定檔設定了 `true`，否則 Claude Code 會依權限模式決定允許清單以外的主機，而不是直接拒絕：在自動模式中，它會依據命令的[每個命令允許的網域](https://code.claude.com/docs/zh-TW/sandboxing.md#per-command-allowed-domains-in-auto-mode)檢查該主機；在 `dontAsk` 模式中會拒絕；在 `bypassPermissions` 模式以及可使用略過功能的互動式終端機 plan mode 工作階段中會允許；其他情況則會詢問您
* **預設值**：`false`

```json settings.json theme={null}
{
  "sandbox": {
    "network": {
      "strictAllowlist": true
    }
  }
}
```

Claude Code 僅對沙箱化命令強制執行此項；`WebFetch` 等程序內工具仍遵循其[權限規則](https://code.claude.com/docs/zh-TW/sandboxing.md#permission-rules)。當任何被採用的來源將其設為 `true` 時，它就會保持開啟。請參閱[網路隔離](https://code.claude.com/docs/zh-TW/sandboxing.md#network-isolation)。需要 Claude Code v2.1.219 或更新版本。

### `sandbox.network.allowManagedDomainsOnly`

將網路允許清單鎖定為受管設定所定義的內容。此時 Claude Code 僅採用來自受管設定的 `allowedDomains` 和 `WebFetch(domain:...)` 允許規則，忽略來自使用者、專案、本機和 `--settings` 設定的網域，並自動封鎖未允許的網域而不顯示提示。

* **範圍**：[`Managed`](#scopes)
* **類型**：布林值
  * `true`：Claude Code 僅採用來自受管設定的 `allowedDomains` 和 `WebFetch(domain:...)` 允許規則，並封鎖未允許的網域而不顯示提示
  * `false`：來自其他設定檔的網域可以合併到允許清單中
* **預設值**：`false`

以下設定會將允許清單鎖定為 GitHub 和 npm，並忽略開發人員新增的任何網域：

```json managed-settings.json theme={null}
{
  "sandbox": {
    "network": {
      "allowManagedDomainsOnly": true,
      "allowedDomains": ["github.com", "*.npmjs.org"]
    }
  }
}
```

當此鍵為 `true` 時，沙箱為[管理員強制要求](https://code.claude.com/docs/zh-TW/sandboxing.md#repository-settings-under-an-admin-required-sandbox)，且只有受管設定能設定[代理伺服器連接埠](#sandbox-network-httpproxyport)。

被拒絕的網域仍會從工作階段載入的所有來源合併。請參閱[防止開發人員擴大政策](https://code.claude.com/docs/zh-TW/sandboxing.md#keep-developers-from-widening-the-policy)。

### `sandbox.network.httpProxyPort`

讓沙箱使用您自己的 HTTP 代理伺服器，而非 Claude Code 執行的代理伺服器。組織會這麼做來檢查 HTTPS 流量、套用自己的篩選規則，或記錄請求。您的代理伺服器會接手篩選工作，而 Claude Code 會停止對送往該處的流量套用其網域清單和網路提示。未設定時，Claude Code 會為 HTTP 流量啟動自己的代理伺服器。

* **範圍**：[`Any file`](#scopes)，除非[其他沙箱設定限制了哪些檔案可以設定連接埠](https://code.claude.com/docs/zh-TW/sandboxing.md#custom-proxy-configuration)
* **類型**：數字，本機 TCP 連接埠
* **預設值**：未設定，因此 Claude Code 會執行自己的代理伺服器

```json settings.json theme={null}
{
  "sandbox": {
    "network": {
      "httpProxyPort": 8080
    }
  }
}
```

如果您的代理伺服器也應承載 SOCKS 流量，請一併設定 [`socksProxyPort`](#sandbox-network-socksproxyport)；若只設定其中一個，Claude Code 仍會為另一種協定執行自己的代理伺服器。請參閱[自訂代理伺服器設定](https://code.claude.com/docs/zh-TW/sandboxing.md#custom-proxy-configuration)。

### `sandbox.network.socksProxyPort`

讓沙箱使用您自己的 SOCKS5 代理伺服器，而非 Claude Code 執行的代理伺服器。您的代理伺服器會接手篩選工作，而 Claude Code 會停止對送往該處的流量套用其網域清單和網路提示。未設定時，Claude Code 會為 SOCKS 流量啟動自己的代理伺服器。

* **範圍**：[`Any file`](#scopes)，除非[其他沙箱設定限制了哪些檔案可以設定連接埠](https://code.claude.com/docs/zh-TW/sandboxing.md#custom-proxy-configuration)
* **類型**：數字，本機 TCP 連接埠
* **預設值**：未設定，因此 Claude Code 會執行自己的代理伺服器

```json settings.json theme={null}
{
  "sandbox": {
    "network": {
      "socksProxyPort": 8081
    }
  }
}
```

請參閱[自訂代理伺服器設定](https://code.claude.com/docs/zh-TW/sandboxing.md#custom-proxy-configuration)。

### `sandbox.network.tlsTerminate`

讓沙箱代理伺服器終止 TLS，以便讀取 HTTPS 請求的內容。這是實驗性功能，且 `mask` [憑證替換](https://code.claude.com/docs/zh-TW/sandboxing.md#mask-credentials)需要此功能。設定 `{}` 可為工作階段產生臨時的憑證授權單位，或設定 `caCertPath` 和 `caKeyPath` 以使用您自己的憑證授權單位。

* **範圍**：[`User or managed`](#scopes)。儲存庫無法開啟此項或提供憑證授權單位。
* **類型**：包含選用 `caCertPath` 和 `caKeyPath` 字串（每個都是檔案路徑）的物件
* **預設值**：未設定，因此代理伺服器不會終止或檢查 TLS

```json settings.json theme={null}
{
  "sandbox": {
    "network": {
      "tlsTerminate": {}
    }
  }
}
```

當有多個被採用的來源設定此項時，Claude Code 會使用優先順序最高之來源的值：受管設定，其次是 `--settings` 旗標，再來是使用者設定。

## 記憶與上下文

控制 Claude Code 載入上下文的內容、如何壓縮以及在何處保存記憶和計畫。請參閱[管理上下文](https://code.claude.com/docs/zh-TW/context-window.md)和[記憶](https://code.claude.com/docs/zh-TW/memory.md)。

### `autoCompactEnabled`

當上下文接近限制時，讓 Claude Code [自動壓縮對話](https://code.claude.com/docs/zh-TW/context-window.md#when-your-context-fills-up)。在 `/config` 中顯示為**自動壓縮**，在那裡切換它會將此鍵寫入您的使用者設定。

* **範圍**：[`任何檔案`](#scopes)
* **類型**：布林值
  * `true`：當上下文接近限制時，Claude Code 自動壓縮對話
  * `false`：Claude Code 不自動壓縮
* **預設**：`true`
* **每個工作階段的覆蓋**：[`DISABLE_AUTO_COMPACT`](https://code.claude.com/docs/zh-TW/env-vars) 關閉一個工作階段的自動壓縮；無論哪一個關閉它，另一個都無法將其重新開啟

```json settings.json theme={null}
{
  "autoCompactEnabled": false
}
```

手動 `/compact` 命令在自動壓縮關閉時繼續工作。如果您關閉自動壓縮，[閒置壓縮](#idlecompaction)也會隨之關閉。

### `autoCompactWindow`

設定在 Claude Code [自動壓縮](https://code.claude.com/docs/zh-TW/context-window.md#when-your-context-fills-up)之前上下文視窗有多滿。

* **範圍**：[`任何檔案`](#scopes)
* **類型**：權杖數量，從 `100000` 到 `1000000`。Claude Code 將值上限設定為您的模型的上下文視窗；[模型概覽](https://platform.claude.com/docs/en/about-claude/models/overview)列出每個模型的視窗
* **預設**：未設定，因此 Claude Code 選擇為您的模型調整的視窗
* **每個工作階段的覆寫**：[`--autocompact`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 在一個工作階段內優先於此鍵，[`CLAUDE_CODE_AUTO_COMPACT_WINDOW`](https://code.claude.com/docs/zh-TW/env-vars) 優先於兩者，除非 Claude Code [忽略該變數的值](https://code.claude.com/docs/zh-TW/model-config.md#claude_code_auto_compact_window-values)

```json settings.json theme={null}
{
  "autoCompactWindow": 500000
}
```

[`/autocompact`](https://code.claude.com/docs/zh-TW/commands#all-commands) 命令會將目前模型的視窗保存在 [`modelSettings`](#modelsettings) 下，對於該模型，它優先於同一檔案中的此鍵。[設定自動壓縮視窗](https://code.claude.com/docs/zh-TW/model-config.md#set-the-auto-compact-window)涵蓋命令、旗標、變數和設定如何相互作用。

### `autoMemoryDirectory`

將[自動記憶](https://code.claude.com/docs/zh-TW/memory.md#storage-location)儲存在您選擇的目錄中，而不是每個專案的預設值。

* **範圍**：[`任何檔案`](#scopes)
* **類型**：字串，絕對路徑或 `~/` 前綴的目錄路徑
* **預設**：未設定，因此 Claude Code 使用 `~/.claude/projects/<project>/memory/`

```json settings.json theme={null}
{
  "autoMemoryDirectory": "~/my-memory-dir"
}
```

從專案或本機設定，Claude Code 在與 [hooks 相同的工作區信任規則](https://code.claude.com/docs/zh-TW/permissions.md#what-runs-before-you-trust-a-folder)下遵守此鍵，因為複製的儲存庫可以提供這些檔案。

### `autoMemoryEnabled`

開啟或關閉[自動記憶](https://code.claude.com/docs/zh-TW/memory.md#enable-or-disable-auto-memory)。當為 `false` 時，Claude 不會從自動記憶目錄讀取或寫入。您也可以在工作階段期間使用 `/memory` 切換它，這會將此鍵寫入您的使用者設定。

* **範圍**：[`任何檔案`](#scopes)
* **類型**：布林值
  * `true`：與未設定相同；自動記憶保持開啟，除非優先於此鍵的內容為工作階段關閉它，例如 `--bare`、安全模式或 `CLAUDE_CODE_DISABLE_AUTO_MEMORY`
  * `false`：Claude 不會從自動記憶目錄讀取或寫入
* **預設**：`true`
* **每個工作階段的覆蓋**：[`CLAUDE_CODE_DISABLE_AUTO_MEMORY`](https://code.claude.com/docs/zh-TW/env-vars) 在一個工作階段內優先於此鍵，無論哪個方向

```json settings.json theme={null}
{
  "autoMemoryEnabled": false
}
```

### `bashOutputMaxChars`

設定成功的 Bash 或 PowerShell 命令的[輸出 Claude 內聯接收](https://code.claude.com/docs/zh-TW/tools-reference.md#output-limits)的字元數。當輸出超過限制時，Claude Code 將其保存到檔案，Claude 接收簡短預覽加上檔案的路徑。當命令輸出（例如詳細的建置或完整的測試套件日誌）經常超過預設值，且您希望 Claude 在不打開檔案的情況下讀取它時，請提高限制。需要 Claude Code v2.1.261 或更高版本。

* **範圍**：[`任何檔案`](#scopes)
* **類型**：字元數，正整數。Claude Code 將值限制在 `4000` 到 `128000` 的範圍內
* **預設**：未設定，因此 Claude 內聯接收最多 30,000 個字元

```json settings.json theme={null}
{
  "bashOutputMaxChars": 100000
}
```

當您設定此鍵時，Claude Code 忽略 [`BASH_MAX_OUTPUT_LENGTH`](https://code.claude.com/docs/zh-TW/env-vars) 環境變數。

### `claudeMd`

注入 CLAUDE.md 風格的指示作為組織管理的記憶，無需部署單獨的檔案。Claude Code 將文字作為受管記憶條目載入，位於使用者和專案 CLAUDE.md 檔案之前。

* **範圍**：[`受管`](#scopes)
* **類型**：字串，CLAUDE.md 檔案的文字；按照您編寫檔案的方式編寫，包括 Markdown，換行符為 `\n`
* **預設**：未設定

此範例將兩個規則部署為簡短的 Markdown 清單：

```json managed-settings.json theme={null}
{
  "claudeMd": "# Engineering rules\n\n- Always run make lint before committing.\n- Never push directly to main."
}
```

請參閱[部署組織範圍的 CLAUDE.md](https://code.claude.com/docs/zh-TW/memory.md#deploy-organization-wide-claude-md)。

### `claudeMdExcludes`

在 Claude Code 載入[記憶](https://code.claude.com/docs/zh-TW/memory.md#exclude-specific-claude-md-files)時跳過特定的 `CLAUDE.md` 檔案。在大型單一儲存庫中，使用它跳過與您的工作無關的其他團隊的 CLAUDE.md 檔案；[排除無關的 CLAUDE.md 檔案](https://code.claude.com/docs/zh-TW/large-codebases.md#exclude-irrelevant-claude-md-files)在大型程式碼庫指南中介紹了該情況。模式與絕對檔案路徑匹配。

* **範圍**：[`任何檔案`](#scopes)
* **類型**：字串陣列，每個都是 glob 模式或絕對路徑
* **預設**：未設定，因此 Claude Code 載入它找到的每個 CLAUDE.md

```json settings.json theme={null}
{
  "claudeMdExcludes": ["**/vendor/**/CLAUDE.md"]
}
```

排除僅適用於使用者、專案和本機記憶檔案；受管原則 CLAUDE.md 檔案無法被排除。

### `env`

為每個工作階段和 Claude Code 從中啟動的子程序設定環境變數。[環境變數參考](https://code.claude.com/docs/zh-TW/env-vars.md)中的大多數變數都可以放在這裡，這是如何將其應用於每個工作階段或將其推出到您的團隊的方式。專案和本機設定無法設定[其中一些](#variables-claude-code-ignores-in-env)。

* **範圍**：[`任何檔案`](#scopes)
* **類型**：將變數名稱對應到字串值的物件
* **預設**：未設定

此範例關閉自動壓縮並通過代理路由 API 請求：

```json settings.json theme={null}
{
  "env": {
    "DISABLE_AUTO_COMPACT": "1",
    "ANTHROPIC_BASE_URL": "https://proxy.example.com"
  }
}
```

#### `env` 值如何與您的 shell 相互作用

* 此處的值會覆蓋在您的 shell 中匯出的相同變數，當多個設定檔設定一個變數時，[最高優先級](https://code.claude.com/docs/zh-TW/settings.md#settings-precedence)的值適用。[Claude Code 在 `env` 中忽略的變數](#variables-claude-code-ignores-in-env)列出專案和本機設定的例外。
* 當 Claude Desktop 應用程式或[自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)執行器啟動工作階段時，它建置的啟動環境優先：Claude Code 忽略任何設定檔中的 `env` 值，用於啟動環境已經設定的變數。[偵錯日誌](https://code.claude.com/docs/zh-TW/debug-your-config.md)命名每個被忽略的變數。
* 要取消 shell 匯出，請將變數設定為 `""`。Claude Code 將空值視為未設定以進行提供者選擇，子程序繼承空值。
* `NO_COLOR` 和 `FORCE_COLOR` 在此設定只到達子程序。要更改 Claude Code 自己的介面顏色，請在啟動 `claude` 之前在您的 shell 中設定它們。
* 此處的值是設定檔中的純文字，到達 Claude Code 啟動的每個子程序。對於輪換的 OTLP 持有人令牌，使用 [`otelHeadersHelper`](#otelheadershelper)；對於 API 認證，使用 [`apiKeyHelper`](#apikeyhelper)。

#### Claude Code 何時應用 `env` 值

* 從使用者設定、`--settings` 和受管設定：在啟動時，以及在執行中的工作階段中當保存的變更改變合併的 `env` 時。
* 從專案和本機設定：在您信任工作區後，或在 `-p` 模式下啟動時（不顯示信任對話），以及當保存的變更改變合併的 `env` 時。
* Claude Code 分類為安全的變數，例如模型選擇、逾時和限制、功能切換：在啟動時從每個設定檔，除了[專案和本機設定無法設定的變數](#variables-claude-code-ignores-in-env)。
* 在您在 v2.1.246 或更高版本上使用 `/cd` [移動工作階段](https://code.claude.com/docs/zh-TW/permissions.md#move-the-session-to-another-directory)後：新目錄的專案和本機 `env` 值，加上前一個目錄的。

#### Claude Code 在 `env` 中忽略的變數

* 專案和本機設定無法設定已簽出的儲存庫不應控制的變數；改為在您的 shell、使用者設定或受管設定中設定這些變數。Claude Code 刪除每個變數，除了幾個關閉遙測的值，並記錄您可以使用 `claude --debug` 看到的警告。它們包括：

  * 選擇 Claude Code 儲存或寫入其自己檔案的位置的變數：`CLAUDE_CONFIG_DIR`、`CLAUDE_CODE_TMPDIR` 和作業系統目錄變數，例如 `HOME`、`TMPDIR`、`TMP`、`TEMP` 和 `XDG_*` 系列。
  * 為 Claude Code 啟動的程序選擇程式和整台機器設定的 Windows 變數，例如 `SystemRoot`、`ComSpec`、`ProgramData`、`LOCALAPPDATA`、`PATHEXT`、`PSModulePath` 和 `ProgramFiles` 系列。
  * 匯出工作階段內容的變數：[`OTEL_LOG_RAW_API_BODIES`](https://code.claude.com/docs/zh-TW/env-vars#variables) 和詳細的測試版追蹤對 `ENABLE_BETA_TRACING_DETAILED` 和 `BETA_TRACING_ENDPOINT`。
  * [OpenTelemetry 匯出器](https://code.claude.com/docs/zh-TW/monitoring-usage.md)變數，開啟遙測、選擇它的去向或選擇它捕獲的內容：

    * `CLAUDE_CODE_ENABLE_TELEMETRY`，加上增強遙測測試版對 `CLAUDE_CODE_ENHANCED_TELEMETRY_BETA` 和 `ENABLE_ENHANCED_TELEMETRY_BETA`
    * 匯出器選擇器 `OTEL_LOGS_EXPORTER`、`OTEL_METRICS_EXPORTER` 和 `OTEL_TRACES_EXPORTER`
    * 內容變數 `OTEL_LOG_USER_PROMPTS`、`OTEL_LOG_ASSISTANT_RESPONSES`、`OTEL_LOG_TOOL_CONTENT` 和 `OTEL_LOG_TOOL_DETAILS`
    * `OTEL_EXPORTER_OTLP_*` 變數，其名稱以 `_ENDPOINT`、`_HEADERS`、`_PROTOCOL`、`_CERTIFICATE`、`_CLIENT_KEY` 或 `_INSECURE` 結尾，以通用和每個信號形式，例如 `OTEL_EXPORTER_OTLP_ENDPOINT` 和 `OTEL_EXPORTER_OTLP_METRICS_HEADERS`
    * `OTEL_EXPORTER_PROMETHEUS_HOST` 和 `OTEL_EXPORTER_PROMETHEUS_PORT`

    只有這些值仍然適用於專案和本機設定，因為它們關閉某些內容：三個匯出器選擇器的 `none`，以及 `OTEL_LOG_USER_PROMPTS`、`OTEL_LOG_TOOL_CONTENT` 和 `OTEL_LOG_TOOL_DETAILS` 的關閉值，例如 `0`。這樣的值會覆蓋您的使用者設定中的相同變數，但不會覆蓋您啟動 Claude Code 的環境、`--settings` 檔案或受管設定設定的變數。

    當專案或本機設定檔設定此群組中的變數時，本機互動式工作階段在啟動時顯示通知。執行 `/status` 或 `claude doctor` 以查看 Claude Code 忽略了哪些以及哪些關閉了遙測；兩者都列出名稱，從不列出值。非互動式執行（使用 `-p`）或 Agent SDK 工作階段不顯示通知，因此在升級後檢查您的收集器是否仍然接收資料。如果沒有，請在您的使用者設定、受管設定、工作的環境或您使用 `--settings` 傳遞的檔案中設定變數。

    在專案和本機設定中忽略此群組需要 Claude Code v2.1.282 或更高版本。
  * 改變 Claude Code 如何啟動或同步的變數，例如 `CLAUDE_CODE_PROCESS_WRAPPER`、`CLAUDE_CODE_SYNC_SKILLS`、`CLAUDE_CODE_SYNC_PLUGINS`、`CLAUDE_CODE_PLUGIN_CACHE_DIR` 和 `CLAUDE_CODE_PLUGIN_SEED_DIR`。
  * 設定您 claude.ai 登入的變數，例如 [`CLAUDE_CODE_OAUTH_TOKEN`、`CLAUDE_CODE_OAUTH_REFRESH_TOKEN` 和 `CLAUDE_CODE_OAUTH_SCOPES`](https://code.claude.com/docs/zh-TW/env-vars#variables)。
  * [螢幕閱讀器模式](https://code.claude.com/docs/zh-TW/accessibility.md)變數 `CLAUDE_AX_SCREEN_READER`，以及其他名稱以 `CLAUDE_AX_` 開頭的變數，例如 [`CLAUDE_AX_STARTUP_QUIET_MS`](https://code.claude.com/docs/zh-TW/env-vars#variables)。
  * [`CLAUDE_CODE_USER_DIALOG_TIMEOUT_MS`](https://code.claude.com/docs/zh-TW/env-vars#variables)，它會設定未回應對話框的計時器。
  * [`CLAUDE_CODE_DISABLE_ATTACHMENTS`](https://code.claude.com/docs/zh-TW/env-vars#variables)，它會關閉附件處理。
  * [`CLAUDE_CODE_DISABLE_FILE_MENTIONS`](https://code.claude.com/docs/zh-TW/env-vars#variables)，它會阻止 Claude Code 展開檔案和目錄的 `@` 提及。

  在 v2.1.251 之前，專案和本機設定也可以設定此清單中選擇 Claude Code 寫入其檔案位置或匯出工作階段內容的變數，除了 `HOME` 和 `XDG_CONFIG_HOME`。在 v2.1.290 之前，它們也可以設定對話框計時器變數和 `CLAUDE_CODE_DISABLE_ATTACHMENTS`。
* Claude Code 的託管環境擁有的身份變數，例如 `CLAUDE_CODE_REMOTE` 和 `CLAUDE_CODE_ACCOUNT_UUID`，從每個檔案中被忽略。
* [`CLAUDE_CODE_MESSAGING_SOCKET` 和 `CLAUDE_CODE_MESSAGING_TOKEN`](https://code.claude.com/docs/zh-TW/env-vars#variables)，Claude Code 自己匯出的，從每個檔案中被忽略。忽略 socket 變數需要 Claude Code v2.1.224 或更高版本，忽略令牌需要 v2.1.228 或更高版本。
* [`CLAUDE_CODE_PROJECT_DIR_NAME`](https://code.claude.com/docs/zh-TW/sessions#name-the-project-directory-yourself)，Claude Code 僅從啟動環境讀取，從每個檔案中被忽略；需要 v2.1.234 或更高版本。
* [`CLAUDE_CODE_RESTRICTED`](https://code.claude.com/docs/zh-TW/env-vars#variables)，Claude Code 僅從啟動環境讀取，從每個檔案中被忽略。
* [`CLAUDE_CODE_DISABLE_POWERSHELL_CMD_RM_DENY`](https://code.claude.com/docs/zh-TW/env-vars#variables)，Claude Code 僅從啟動環境讀取，從每個檔案中被忽略。此變數需要 Claude Code v2.1.283 或更高版本。
* [`CLAUDE_CODE_DISABLE_DANGEROUS_RM_TIMEOUT`、`CLAUDE_CODE_DISABLE_SUBSTITUTION_RM_PROMPT`、`CLAUDE_CODE_DISABLE_INLINE_SHELL_RM_PROMPT` 和 `CLAUDE_CODE_DISABLE_MOUNTED_DRIVE_RM_PROMPT`](https://code.claude.com/docs/zh-TW/env-vars#variables)，Claude Code 僅從啟動環境讀取，從每個檔案中被忽略。
* [`CLAUDE_CODE_EVEN_MORE_DANGEROUSLY_SKIP_PERMISSIONS`](https://code.claude.com/docs/zh-TW/env-vars#variables)，Claude Code 僅從啟動環境讀取，從每個檔案中被忽略。
* [`CLAUDE_CODE_WARN_DISK_FREE_GIB` 和 `CLAUDE_CODE_WARN_MEMORY_FREE_GIB`](https://code.claude.com/docs/zh-TW/env-vars#variables)，Claude Code 僅從啟動環境讀取，從每個檔案中被忽略。這些變數需要 Claude Code v2.1.304 或更高版本。

### `fileCheckpointingEnabled`

讓 Claude Code 在每次編輯前快照檔案，以便 [`/rewind`](https://code.claude.com/docs/zh-TW/checkpointing) 可以還原它們。在 `/config` 中顯示為**倒帶程式碼（檢查點）**，在那裡切換它會將此鍵寫入您的使用者設定。

* **範圍**：[`任何檔案`](#scopes)
* **類型**：布林值
  * `true`：Claude Code 在每次編輯前快照檔案，以便 `/rewind` 可以還原它們
  * `false`：Claude Code 不快照檔案，因此 `/rewind` 無法還原它們
* **預設**：`true`
* **每個工作階段的覆蓋**：[`CLAUDE_CODE_DISABLE_FILE_CHECKPOINTING`](https://code.claude.com/docs/zh-TW/env-vars) 關閉一個工作階段的檢查點；無論哪一個關閉它，另一個都無法將其重新開啟

```json settings.json theme={null}
{
  "fileCheckpointingEnabled": false
}
```

在 `-p` 執行或 Agent SDK 工作階段中，Claude Code 忽略此鍵。SDK 使用其 `enableFileCheckpointing` 選項開啟檢查點，裸 `-p` 執行需要 `CLAUDE_CODE_ENABLE_SDK_FILE_CHECKPOINTING=true`。請參閱 [Agent SDK 中的檔案檢查點](https://code.claude.com/docs/zh-TW/agent-sdk/file-checkpointing.md)。

### `idleCompaction`

閒置壓縮會[壓縮](https://code.claude.com/docs/zh-TW/context-window.md#what-survives-compaction)您已離開的長對話。接著您的下一則訊息會傳送摘要，而不是整個對話。壓縮完成後，對話會顯示一則通知：

* **終端機**：一行以 `Compacted while idle, before the prompt cache expired` 開頭的訊息
* **[VS Code 聊天面板](#idle-compaction-in-vs-code-and-the-desktop-app)**：包含 `a summary written while you were away` 的通知
* **[桌面應用程式](#idle-compaction-in-vs-code-and-the-desktop-app)**：相同的通知，位於標籤包含 `Claude Code notice` 的列中。如果您沒有看到該列或其文字，請切換到 [Verbose 檢視模式](https://code.claude.com/docs/zh-TW/desktop.md#switch-view-modes)。

對於符合以下所有條件的對話，閒置壓縮預設為開啟：

* **工作階段**：您處於互動式終端機工作階段中、VS Code 擴充功能的聊天面板中，或是在工作階段於您的機器上或透過 SSH 執行時處於桌面應用程式的 Code 分頁中
* **自動壓縮**：[`autoCompactEnabled`](#autocompactenabled) 已開啟
* **提示快取**：對話使用[一小時提示快取 TTL](https://code.claude.com/docs/zh-TW/prompt-caching.md#which-ttl-each-request-gets)
* **大小**：對話的上下文已達到 token 閾值，您可以從其預設值 200,000 [變更](#change-the-idle-compaction-threshold)此閾值
* **閒置時間**：自上次請求以來已經過約一小時，且您的電腦在那之前保持喚醒狀態

若要關閉閒置壓縮，請將此鍵設定為 `false`。

* **範圍**：[`任何檔案`](#scopes)
* **類型**：布林值
  * `true`：Claude Code 壓縮符合條件的閒置對話
  * `false`：Claude Code 不會在您的工作階段閒置時進行壓縮
* **預設**：`true`
* **每個工作階段的覆寫**：[`DISABLE_AUTO_COMPACT`](https://code.claude.com/docs/zh-TW/env-vars) 會連同自動壓縮一起關閉閒置壓縮

```json settings.json theme={null}
{
  "idleCompaction": false
}
```

若要在終端機工作階段內關閉或開啟閒置壓縮，請執行 `/config` 並變更**閒置壓縮**列。您的選擇會儲存到您的使用者設定並立即套用。此列需要 Claude Code v2.1.302 或更高版本。如果您執行的是這些版本之一，但 `/config` 未顯示此列，請檢查以下原因：

* **另一個設定來源設定了此鍵**：受管設定、`--settings` 旗標，或專案或本機設定檔中的值會覆寫您的使用者設定。請改為在該來源中變更此鍵
* **在 v2.1.314 之前的版本上功能旗標無法使用**：在 Claude Code 無法[從 Anthropic 擷取功能旗標](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)的情況下，閒置壓縮不會執行，因此沒有可關閉的內容

此鍵需要 Claude Code v2.1.290 或更高版本。在會忽略此鍵的較早版本上，請關閉 [`autoCompactEnabled`](#autocompactenabled) 以停止閒置壓縮。

#### 變更閒置壓縮閾值

將 [`CLAUDE_CODE_IDLE_COMPACT_MIN_TOKENS`](https://code.claude.com/docs/zh-TW/env-vars) 設定為對話的上下文必須達到的 token 數量，之後閒置壓縮才會套用到該對話。請使用正整數。低於 `100000` 的值會提高到最低閾值 `100000`。

在預設值下，使用 200K 上下文視窗的對話會在達到 200,000 個 token 之前自動壓縮。此範例將閾值降低到 150,000，讓這些對話符合條件：

```json settings.json theme={null}
{
  "env": {
    "CLAUDE_CODE_IDLE_COMPACT_MIN_TOKENS": "150000"
  }
}
```

#### VS Code 與桌面應用程式中的閒置壓縮

類似以下的通知表示 Claude Code 已[將您先前的對話替換為摘要](https://code.claude.com/docs/zh-TW/context-window.md#what-survives-compaction)，Claude 現在會以該摘要為基礎繼續工作：

```text theme={null}
Compacted using a summary written while you were away · turn off with "idleCompaction": false in settings.json
```

您不需要採取任何動作。若要關閉閒置壓縮，請在工作階段執行所在的機器或 WSL 發行版上的 `~/.claude/settings.json`，或其他[設定檔](https://code.claude.com/docs/zh-TW/settings.md#settings-files-and-who-they-affect)中，將 `idleCompaction` 設定為 `false`。

### `plansDirectory`

選擇 Claude Code 在 [plan mode](https://code.claude.com/docs/zh-TW/permission-modes.md#analyze-before-you-edit-with-plan-mode) 中寫入的計畫檔案的儲存位置。Claude Code 相對於專案根目錄解析路徑。

* **範圍**：[`任何檔案`](#scopes)
* **類型**：字串，相對於專案根目錄的路徑
* **預設**：未設定，因此 Claude Code 使用 `~/.claude/plans`

```json settings.json theme={null}
{
  "plansDirectory": "./plans"
}
```

在以下這類情況中，Claude Code 會將計畫儲存在 `~/.claude/plans`，而非您設定的目錄：

* **位於專案根目錄之外**：路徑解析到專案根目錄之外，例如 `"../plans"`。
* **在 macOS、Linux 和 WSL 上使用反斜線**：解析後的路徑包含反斜線，例如 Windows 風格的 `"docs\\plans"`。請改寫為 `"docs/plans"`，這在 Windows 上也適用。

### `skillListingBudgetFraction`

每個回合，Claude 看到[您的 skills 清單](https://code.claude.com/docs/zh-TW/skills.md#skill-descriptions-are-cut-short)及其描述，Claude Code 將該清單上限設定為上下文視窗的一部分。當清單超過上限時，Claude Code 保留每個 skill 的名稱，但刪除最少使用 skills 的描述，因此 Claude 仍然可以呼叫這些 skills，但不太可能自己選擇一個。提高此鍵以保持更多描述可見，代價是每個回合更多上下文。

* **範圍**：[`任何檔案`](#scopes)
* **類型**：數字，大於 `0` 且最多 `1` 的分數
* **預設**：`0.01`，保留上下文視窗的 1%

```json settings.json theme={null}
{
  "skillListingBudgetFraction": 0.02
}
```

要查看清單使用多少上下文以及哪些 skills 貢獻最多，請執行 `/doctor`。

### `skillListingMaxDescChars`

每個回合，Claude 看到[您的 skills 清單](https://code.claude.com/docs/zh-TW/skills.md#skill-descriptions-are-cut-short)，顯示每個 skill 的 `description` 和 `when_to_use` 文字。此鍵限制 Claude Code 每個 skill 顯示多少字元的該文字；較長的文字在上限處被切割。

* **範圍**：[`任何檔案`](#scopes)
* **類型**：字元數，正整數
* **預設**：`1536`

```json settings.json theme={null}
{
  "skillListingMaxDescChars": 2048
}
```

提高它以保持長描述完整，代價是每個回合更多上下文；降低它以在 [`skillListingBudgetFraction`](#skilllistingbudgetfraction) 下適應更多 skills。

### `taskOutputMaxChars`

> [!WARNING]
>
> 在 v2.1.277 中移除，連同它調整大小的 `TaskOutput` 工具一起。設定它對目前版本沒有影響。Claude 改為使用 `Read` 讀取背景工作的[輸出檔案](https://code.claude.com/docs/zh-TW/tools-reference.md#background-commands)。

透過 v2.1.276，您設定此鍵為[背景工作](https://code.claude.com/docs/zh-TW/tools-reference.md#background-commands)的輸出字元數，當 Claude 使用 `TaskOutput` 工具讀取工作時，Claude 內聯接收。

## 介面與終端機

變更 Claude Code 在終端機中的外觀與行為：主題、編輯器模式、狀態列、旋轉指示器、工作階段內的通知，以及協助工具。請參閱[終端機設定](https://code.claude.com/docs/zh-TW/terminal-config.md)。

### `askUserQuestionTimeout`

讓未獲回答的 [`AskUserQuestion`](https://code.claude.com/docs/zh-TW/tools-reference) 對話框在閒置一段時間後自動繼續，並提交您已選取的選項。當您暫時離開並希望 Claude 在沒有您的情況下繼續時，請設定此項目。使用預設值時，問題會一直等待直到您回答。關於計時器何時暫停或永不啟動，請參閱[問題自動繼續逾時](https://code.claude.com/docs/zh-TW/tools-reference.md#question-auto-continue-timeout)。

* **範圍**：[`User or managed`](#scopes)
* **類型**：字串，為 `"60s"`、`"5m"`、`"10m"` 或 `"never"` 之一
* **預設值**：`"never"`

```json settings.json theme={null}
{
  "askUserQuestionTimeout": "5m"
}
```

在 `/config` 中顯示為 **Question auto-continue timeout**，會將此設定鍵寫入使用者設定；當受管設定或 `--settings` 旗標設定了此設定鍵時，Claude Code 會隱藏該列。

### `autoContinueAtUsageLimit`

當 claude.ai 用量上限停止您的工作階段後，在開啟的工作階段中等待，並於重設後自動繼續任務。請參閱[關閉自動繼續](https://code.claude.com/docs/zh-TW/interactive-mode.md#turn-automatic-continue-off)。需要 Claude Code v2.1.234 或更新版本。

* **範圍**：[`User or managed`](#scopes)。僅從使用者設定、`--settings` 與受管設定讀取。當這些都未設定此設定鍵時，設定了此設定鍵的專案或本機設定檔會關閉此功能，而非被忽略。
* **類型**：Boolean
  * `true`：當 claude.ai 用量上限停止您的工作階段後，Claude Code 會在開啟的工作階段中等待，並於重設後自動繼續任務
  * `false`：Claude Code 不會自行開始等待。您仍可從用量上限選項選單中[自行開始等待](https://code.claude.com/docs/zh-TW/interactive-mode.md#start-a-wait-yourself)
* **預設值**：`true`

```json settings.json theme={null}
{
  "autoContinueAtUsageLimit": false
}
```

在 `/config` 中顯示為 **Continue automatically at usage limit**，會將此設定鍵寫入使用者設定；當受管設定或 `--settings` 旗標設定了此設定鍵時，Claude Code 會隱藏該列。

### `autoScrollEnabled`

在[全螢幕渲染](https://code.claude.com/docs/zh-TW/fullscreen.md)中，跟隨新輸出捲動至對話底部。關閉此項目後，當 Claude 持續工作時，畫面會停留在您捲動到的位置；權限提示仍會捲動進入可見範圍。

* **範圍**：[`Any file`](#scopes)
* **類型**：Boolean
  * `true`：對話會跟隨新輸出捲動至底部
  * `false`：當 Claude 持續工作時，畫面停留在您捲動到的位置；權限提示仍會出現在逐字稿下方
* **預設值**：`true`

```json settings.json theme={null}
{
  "autoScrollEnabled": false
}
```

當全螢幕渲染開啟時，在 `/config` 中顯示為 **Auto-scroll**，會將此設定鍵寫入使用者設定。

### `axScreenReader`

渲染適合螢幕閱讀器的輸出：沒有裝飾性邊框或動畫的純文字。螢幕閱讀器模式使用經典渲染器，因此在其啟用期間 `tui` 設定沒有作用；附加的[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)仍會以全螢幕渲染。

* **範圍**：[`User or managed`](#scopes)。您也可以在透過 `--settings` 傳入的檔案中設定此設定鍵。Claude Code 會忽略專案與本機設定中的此設定鍵，因此無論是儲存庫或您自己的 `.claude/settings.local.json` 都無法開啟或關閉螢幕閱讀器模式。
* **類型**：Boolean
  * `true`：Claude Code 使用經典渲染器，渲染沒有裝飾性邊框或動畫的純文字
  * `false`：Claude Code 正常渲染
* **預設值**：未設定，因此螢幕閱讀器模式為關閉
* **個別工作階段覆寫**：[`--ax-screen-reader`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 優先於 [`CLAUDE_AX_SCREEN_READER`](https://code.claude.com/docs/zh-TW/env-vars)，且兩者在單一工作階段中皆優先於此設定鍵

```json settings.json theme={null}
{
  "axScreenReader": true
}
```

### `bashEditDiffEnabled`

選擇 Claude Code 是否在 Bash 命令執行期間記錄 Git 儲存庫中有哪些檔案變更。記錄時，您會在命令執行後於終端機中看到它們的差異，而您的 [PostToolUse Bash hook](https://code.claude.com/docs/zh-TW/hooks.md#bash) 會收到變更檔案清單。

列出的檔案不一定是該命令所變更的。在命令執行期間由其他程式或其他 Bash 呼叫所做的變更也可能出現在其中。

將此設定鍵設為 `true` 即可在每種權限模式中記錄。需要 Claude Code v2.1.269 或更新版本。

* **範圍**：[`User or managed`](#scopes)。`true` 僅在來自您的使用者設定、以 `--settings` 傳入的 JSON，或[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)時才有效，因此儲存庫的 `.claude/settings.json` 或 `.claude/settings.local.json` 中的 `true` 無法開啟記錄。任一儲存庫檔案中的 `false` 仍會將其關閉，除非有[優先順序更高](https://code.claude.com/docs/zh-TW/settings.md#settings-precedence)的檔案設定了 `true`。
* **類型**：Boolean
* **預設值**：未設定，因此 Claude Code 會在自動模式和 `bypassPermissions` 模式中，當其指示 Claude 透過 Bash 編輯檔案時記錄變更
* **個別工作階段覆寫**：[`CLAUDE_CODE_BASH_EDIT_DIFF`](https://code.claude.com/docs/zh-TW/env-vars) 在單一工作階段中優先於此設定鍵

```json settings.json theme={null}
{
  "bashEditDiffEnabled": true
}
```

### `companyAnnouncements`

在啟動時向使用者顯示您組織的公告。當您列出多則公告時，Claude Code 會為每個工作階段隨機挑選一則；在某人第一次啟動時，則會顯示第一則。

* **範圍**：[`Any file`](#scopes)
* **類型**：字串陣列
* **預設值**：未設定，因此不會顯示公告

```json settings.json theme={null}
{
  "companyAnnouncements": [
    "Welcome to Acme Corp! Review our code guidelines at docs.example.com"
  ]
}
```

### `defaultShell`

選擇由 Bash 或 PowerShell 執行您在輸入框中以 [`!` 前綴](https://code.claude.com/docs/zh-TW/interactive-mode#shell-mode-with-prefix)輸入的 shell 命令，也就是 Claude Code 直接執行並加入工作階段的那些命令。

`"powershell"` 僅在 [PowerShell 工具](https://code.claude.com/docs/zh-TW/tools-reference.md#powershell-tool)開啟時有效。在沒有 Git Bash 的 Windows 上，以及在有 Git Bash 的 Windows 上使用 claude.ai 和 Console 帳戶時，此工具預設為開啟。在 Amazon Bedrock、Google Cloud's Agent Platform 和 Microsoft Foundry 工作階段中，以及在 macOS、Linux 和 WSL 上，請設定 `CLAUDE_CODE_USE_POWERSHELL_TOOL=1` 以開啟此工具。將該變數設為 `0` 則會關閉此工具。

* **範圍**：[`Any file`](#scopes)
* **類型**：字串，為下列之一：
  * `"bash"`：Claude Code 在 Bash 中執行您的 `!` 命令
  * `"powershell"`：Claude Code 在 PowerShell 中執行您的 `!` 命令
* **預設值**：`"bash"`，或在 Bash 無法使用的 Windows 上為 `"powershell"`

```json settings.json theme={null}
{
  "defaultShell": "powershell"
}
```

如果您指定的 shell 無法使用，Claude Code 會改用另一個：當 PowerShell 工具關閉時，`"powershell"` 會退回使用 Bash；當未安裝 Bash 時，`"bash"` 會退回使用 PowerShell。

### `dialogExpiry`

設定 Claude Code [轉送至遠端用戶端](https://code.claude.com/docs/zh-TW/remote-control.md#limitations)（例如 Remote Control 或 SDK 主機）之對話框的期限，以及[被保留的跨工作階段訊息](https://code.claude.com/docs/zh-TW/cross-session-messaging.md#control-inbound-messages)之核准對話框的期限。在 Claude Code v2.1.236 或更新版本中，同一期限也會限制在可能無人位於終端機前的工作階段中，於工作階段途中出現的 [Fable 用量點數同意提示](https://code.claude.com/docs/zh-TW/model-config.md#fable-and-usage-credits)。若在期限前未收到回答，Claude Code 會取消該對話框，並以其不採取動作的預設值繼續。需要 Claude Code v2.1.224 或更新版本。

* **範圍**：[`User or managed`](#scopes)
* **類型**：字串，為 `"60s"`、`"5m"`、`"10m"` 或停用期限的 `"never"` 之一
* **預設值**：`"5m"`
* **個別工作階段覆寫**：[`CLAUDE_CODE_USER_DIALOG_TIMEOUT_MS`](https://code.claude.com/docs/zh-TW/env-vars) 在單一工作階段中優先於此設定鍵

```json settings.json theme={null}
{
  "dialogExpiry": "10m"
}
```

權限提示與 [`AskUserQuestion`](https://code.claude.com/docs/zh-TW/tools-reference#askuserquestion-tool-behavior) 問題使用各自的流程，不受此期限約束。在 `/config` 中顯示為 **Dialog expiry**，會將此設定鍵寫入使用者設定；該列需要 Claude Code v2.1.232 或更新版本，且當受管設定或 `--settings` 旗標設定了此設定鍵時，Claude Code 會隱藏該列。

### `editorMode`

選擇輸入提示詞的按鍵綁定模式。

* **範圍**：[`Any file`](#scopes)
* **類型**：字串，為下列之一：
  * `"normal"`：提示詞輸入中的標準按鍵綁定
  * `"vim"`：具有 NORMAL、INSERT 和 VISUAL 模式的 vim 風格編輯
* **預設值**：`"normal"`

```json settings.json theme={null}
{
  "editorMode": "vim"
}
```

在 `/config` 中顯示為 **Editor mode**，會將此設定鍵寫入使用者設定。

### `emojiCompletionEnabled`

當您在提示詞輸入中輸入 `:` 加上簡碼時顯示表情符號建議，並將完整的簡碼（例如 `:heart:`）替換為其表情符號。將其設為 `false` 可同時關閉兩者。

* **範圍**：[`Any file`](#scopes)
* **類型**：Boolean
  * `true`：Claude Code 在 `:` 之後顯示表情符號建議，並將完整的簡碼替換為其表情符號
  * `false`：Claude Code 既不建議表情符號，也不替換簡碼
* **預設值**：`true`

```json settings.json theme={null}
{
  "emojiCompletionEnabled": false
}
```

請參閱[表情符號簡碼](https://code.claude.com/docs/zh-TW/interactive-mode.md#emoji-shortcodes)。

### `fileSuggestion`

執行您自己的命令來提供 `@` 檔案路徑自動完成，取代內建的檔案建議。內建建議使用快速的檔案系統走訪；大型 monorepo 使用專案專屬的索引（例如預先建置的檔案索引）可能效果更好。

* **範圍**：[`Any file`](#scopes)。在[狀態列與檔案建議閘門](#status-line-and-file-suggestion-gates)下，Claude Code 會關閉該命令或僅執行受管值，並在不發出警告的情況下略過您的命令。
* **類型**：物件，包含 `type`（一律為 `"command"`）和 `command`（要執行的 shell 命令）
* **預設值**：未設定，因此 Claude Code 使用內建的檔案建議

```json settings.json theme={null}
{
  "fileSuggestion": {
    "type": "command",
    "command": "~/.claude/file-suggestion.sh"
  }
}
```

儲存後，在提示詞中輸入 `@` 加上部分路徑：建議會來自您命令的輸出。

#### 命令輸入與輸出

Claude Code 會以與 [hook](https://code.claude.com/docs/zh-TW/hooks.md) 相同的環境變數（包括 `CLAUDE_PROJECT_DIR`）執行該命令，並在五秒後停止等待。該命令會在 stdin 上收到 JSON，其中的 `query` 欄位包含您目前已輸入的內容：

```json theme={null}
{"query": "src/comp"}
```

將以換行分隔的檔案路徑輸出到 stdout。Claude Code 最多顯示 15 個：

```text theme={null}
src/components/Button.tsx
src/components/Modal.tsx
src/components/Form.tsx
```

以下指令碼會讀取查詢並將其交給儲存庫檔案索引：

```bash theme={null}
#!/bin/bash
query=$(cat | jq -r '.query')
# Replace your-repo-file-index with your own file search command
your-repo-file-index --query "$query" | head -20
```

### `footerLinksRegexes`

當正規表示式比對到回合輸出時，在輸入框下方的頁尾中渲染額外的可點擊徽章；回合輸出包括工具結果（含檔案內容與擷取的頁面）以及 Claude 本身的回應。可用來將專案 CLI（例如審查工具與問題追蹤器）輸出的 ID 轉換為工作階段連結。

* **範圍**：[`User or managed`](#scopes)
* **類型**：物件陣列，每個物件包含設為 `"regex"` 的 `type`、一個 `pattern` 正規表示式、一個 `url` 範本，以及選用的 `label`；`url` 和 `label` 中的 `{name}` 預留位置會以 `pattern` 中的具名擷取群組填入
* **預設值**：未設定，因此不會渲染徽章

此範例會比對 `PROJ-1234` 之類的問題鍵，並以擷取到的鍵建立每個連結：

```json settings.json theme={null}
{
  "footerLinksRegexes": [
    {
      "type": "regex",
      "pattern": "\\b(?<key>PROJ-\\d+)\\b",
      "url": "https://issues.example.com/browse/{key}",
      "label": "{key}"
    }
  ]
}
```

完成此設定後，當 `PROJ-1234` 出現在工具結果或 Claude 的回覆中時，頁尾會出現一個連結至 `https://issues.example.com/browse/PROJ-1234` 的 `PROJ-1234` 徽章。

#### 徽章限制

每個項目的 URL、標籤與徽章數量受到以下限制：

| 限制 | 行為 |
| :- | :- |
| URL 來源 | 擷取的值會經過 URL 編碼，且建構出的 URL 必須與範本的字面來源相同。擷取值可以填入路徑區段或查詢值，但無法變更連結指向的位置 |
| URL 長度 | 超過 2048 個字元的建構 URL 會被捨棄 |
| URL 配置 | 必須是 `https`、`http`，或可識別的編輯器或工作區深層連結配置：`vscode`、`vscode-insiders`、`cursor`、`windsurf`、`zed`、`jetbrains`、`idea`、`slack`、`linear`、`notion`、`figma` |
| 標籤 | 預設為比對到的文字，並截斷為 28 個顯示欄位 |
| 徽章數量 | 最多渲染 5 個徽章。最舊的會被較新的比對結果取代，而 `/clear` 會移除它們 |

當回合完成時，Claude Code 會在主執行緒上以每個項目的 `pattern` 正規表示式比對回合輸出，因此較慢的正規表示式會阻塞 UI 直到完成。巢狀量詞（例如 `(a+)+$`）在特定輸入下可能耗費指數級的時間並凍結工作階段，因此請讓每個 `pattern` 保持線性，並避免巢狀使用 `+` 或 `*`。

當設定了[自訂狀態列](https://code.claude.com/docs/zh-TW/statusline.md)時，頁尾徽章會與其並列渲染；兩者不會互相取代。若要以指令碼驅動、從工作階段資料自行計算內容的一列，請使用狀態列；若要在不使用指令碼的情況下將對話中的 ID 轉換為連結，請使用頁尾徽章。

### `keybindingFlavor`

> [!WARNING]
>
> 自 v2.1.261 起已棄用且沒有作用。提示詞的文字編輯按鍵一律[遵循 readline 慣例](https://code.claude.com/docs/zh-TW/interactive-mode.md#make-ctrl-w-delete-back-to-whitespace)，與 Bash 相同。Claude Code 仍接受 `keybindingFlavor`，因此設定了它的設定檔仍然有效。

在 v2.1.238 至 v2.1.260 中，將其設為 `"readline"` 會讓 `Ctrl+W` 刪除至前一個空白字元，而非僅刪除前一個單字。

* **範圍**：[`Any file`](#scopes)
* **類型**：字串，`"classic"` 或 `"readline"`
* **預設值**：未設定

### `maxProseWidth`

限制 Claude 回應中文字段落的寬度，讓行在寬終端機中仍保持易讀。段落、標題、清單與引用區塊會在此欄數內換行，而表格與程式碼區塊則保持完整的終端機寬度。需要 Claude Code v2.1.282 或更新版本。

* **範圍**：[`Any file`](#scopes)
* **類型**：終端機欄數，為整數，最小值為 `40`。Claude Code 會忽略任何其他值
* **預設值**：未設定，因此文字段落會在終端機邊緣換行

```json settings.json theme={null}
{
  "maxProseWidth": 80
}
```

### `prefersReducedMotion`

減少或關閉介面動畫，例如旋轉指示器、微光與閃爍效果。在 `/config` 中顯示為 **Reduce motion**。

* **範圍**：[`Any file`](#scopes)
* **類型**：Boolean
  * `true`：Claude Code 會減少或關閉介面動畫，例如旋轉指示器、微光與閃爍效果
  * `false`：與未設定相同；Claude Code 會顯示其動畫
* **預設值**：`false`

```json settings.json theme={null}
{
  "prefersReducedMotion": true
}
```

### `promptSuggestionEnabled`

顯示或隱藏[提示詞建議](https://code.claude.com/docs/zh-TW/interactive-mode.md#prompt-suggestions)，也就是出現在提示詞輸入中的灰色預測內容。將其設為 `false`，或在 `/config` 中關閉 **Prompt suggestions**，即可隱藏它們。

* **範圍**：[`Any file`](#scopes)
* **類型**：Boolean
  * `true`：您會在提示詞輸入中看到提示詞建議
  * `false`：Claude Code 會隱藏提示詞建議
* **預設值**：`true`
* **個別工作階段覆寫**：[`CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION`](https://code.claude.com/docs/zh-TW/env-vars) 在單一工作階段中優先於此設定鍵

```json settings.json theme={null}
{
  "promptSuggestionEnabled": false
}
```

提示詞建議需要開啟遙測的 claude.ai 或 Console 帳戶。在 Amazon Bedrock、Google Cloud's Agent Platform 和 Microsoft Foundry 上，或在關閉遙測時（例如透過 [`DISABLE_TELEMETRY`](https://code.claude.com/docs/zh-TW/env-vars)），此設定鍵沒有作用，只有 `CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION=1` 能開啟它們。

### `respectGitignore`

控制 `@` 檔案選擇器是否排除符合 `.gitignore` 模式的檔案。在 `/config` 中顯示為 **Respect .gitignore in file picker**。

* **範圍**：[`Any file`](#scopes)。當沒有設定檔設定此項目時，Claude Code 會退回使用 `~/.claude.json` 中的 `respectGitignore`，也就是 `/config` 切換開關所寫入的位置。
* **類型**：Boolean
  * `true`：`@` 檔案選擇器會排除符合 `.gitignore` 模式的檔案
  * `false`：`@` 檔案選擇器會包含符合 `.gitignore` 模式的檔案
* **預設值**：`true`

```json settings.json theme={null}
{
  "respectGitignore": false
}
```

### `respondToBashCommands`

選擇在您於輸入框中以 [`!` 前綴](https://code.claude.com/docs/zh-TW/interactive-mode#shell-mode-with-prefix)執行 shell 命令後，Claude 是否回應。預設情況下，Claude Code 會將命令的輸出加入對話，而 Claude 會對其回覆。將此設定鍵設為 `false` 可將輸出加入上下文而不回覆，讓您可以執行多個命令後再一併詢問。

* **範圍**：[`Any file`](#scopes)
* **類型**：Boolean
  * `true`：Claude Code 將命令的輸出加入對話，而 Claude 會對其回覆
  * `false`：Claude Code 將輸出加入上下文而不回覆
* **預設值**：`true`

```json settings.json theme={null}
{
  "respondToBashCommands": false
}
```

請參閱[使用 `!` 前綴的 shell 模式](https://code.claude.com/docs/zh-TW/interactive-mode#shell-mode-with-prefix)。

### `showClearContextOnPlanAccept`

當 Claude 在 [plan mode](https://code.claude.com/docs/zh-TW/permission-modes.md#review-and-approve-a-plan) 中完成計畫時，會顯示核准選單。規劃可能使用大量上下文，因此此設定鍵會在該選單中加入第一個選項 **Yes, clear context and …**，用於核准計畫、清除對話上下文，並僅依據計畫開始實作。標籤的其餘部分會指出工作階段將以哪種權限模式繼續，並顯示規劃使用了多少上下文。

* **範圍**：[`Any file`](#scopes)
* **類型**：Boolean
  * `true`：計畫核准選單會出現第一個選項 **Yes, clear context and …**，用於核准計畫並清除對話上下文
  * `false`：計畫核准選單不會顯示清除上下文的選項
* **預設值**：`false`

```json settings.json theme={null}
{
  "showClearContextOnPlanAccept": true
}
```

### `showTurnDuration`

顯示或隱藏每次回應後的回合時間訊息，例如「Cooked for 1m 6s · done 6:05 PM」。「done」之後的時鐘顯示回合結束的時間；[`timeFormat`](#timeformat) 和 [`timeZone`](#timezone) 控制其格式與時區。在 `/config` 中顯示為 **Show turn duration**。

* **範圍**：[`Any file`](#scopes)。當沒有設定檔設定此項目時，會套用舊版本在 `~/.claude.json` 中的值。
* **類型**：Boolean
  * `true`：您會在每次回應後看到回合時間訊息
  * `false`：Claude Code 會隱藏回合時間訊息
* **預設值**：`true`

```json settings.json theme={null}
{
  "showTurnDuration": false
}
```

### `spellcheck`

使用您安裝的拼字檢查器，在您輸入時於提示詞輸入中為拼錯的單字加上底線。Claude Code 只檢查輸入框中的文字。[輸入時檢查拼字](https://code.claude.com/docs/zh-TW/interactive-mode.md#check-spelling-as-you-type)說明了如何安裝 aspell、hunspell 或 ispell，以及檢查器涵蓋的範圍。需要 Claude Code v2.1.235 或更新版本。

* **範圍**：[`User or managed`](#scopes)。會整體套用設定了此項目之最高層級的區塊。
* **類型**：物件，包含 `enabled`（Boolean）、`checker`（`"aspell"`、`"hunspell"`、`"ispell"` 或 `"auto"`）、`language`（字串，作為字典名稱傳給檢查器）和 `color`（字串，為終端機色彩名稱、`#rrggbb`、`rgb(r,g,b)`、`ansi256(n)` 或 `ansi:<name>`）
* **預設值**：未設定，因此拼字檢查為關閉；`checker` 預設為 `"auto"`，即在 `PATH` 上找到的三者中的第一個；`language` 預設為檢查器本身的字典；`color` 預設為主題的錯誤色彩

```json settings.json theme={null}
{
  "spellcheck": { "enabled": true, "language": "en_GB" }
}
```

### `spinnerTipsEnabled`

當 Claude 工作時，旋轉指示器那一行會輪流顯示關於 Claude Code 功能的簡短提示，例如「Use Plan Mode to prepare for a complex request before making changes. Press Shift+Tab twice to enable.」。將此設定鍵設為 `false` 即可隱藏它們。在 `/config` 中顯示為 **Show tips**。

* **範圍**：[`Any file`](#scopes)
* **類型**：Boolean
  * `true`：當 Claude 工作時，您會在旋轉指示器中看到提示
  * `false`：Claude Code 會隱藏旋轉指示器提示
* **預設值**：`true`

```json settings.json theme={null}
{
  "spinnerTipsEnabled": false
}
```

### `spinnerTipsOverride`

將您自己的提示加入 Claude Code 在 Claude 工作時顯示的[旋轉指示器提示](#spinnertipsenabled)，或以您的提示取代內建提示。Claude Code 會將您的提示放入與內建提示相同的輪替中。

如果您將 [`spinnerTipsEnabled`](#spinnertipsenabled) 設為 `false`，Claude Code 會隱藏所有提示，包括您的提示。

* **範圍**：[`Any file`](#scopes)。Claude Code 會採用來自使用者設定、`--settings` 旗標與受管設定的提示物件、`tipsFile`、`label` 和 `excludeDefault`；從專案和本機設定中則只讀取純字串提示。
* **類型**：物件，包含 `tips`、`tipsFile`、`label` 和 `excludeDefault` 欄位，皆為選用
* **預設值**：未設定，因此 Claude Code 只顯示內建提示

提示物件、`tipsFile`、`label`，以及範圍說明中專案與本機設定只提供純字串的規則，需要 Claude Code v2.1.247 或更新版本。

每個 `tips` 項目都是純字串，或是包含下列欄位的物件：

| 欄位 | 必要 | 說明 |
| :- | :- | :- |
| `id` | 是 | 最多 64 個字母、數字、`.`、`_` 或 `-`。Claude Code 以其作為提示顯示記錄的鍵，因此重新排列清單後提示的冷卻時間仍會保留。若有兩個項目的 id 相同，Claude Code 會使用第一個 |
| `text` | 是 | 提示內容，一行，最多 500 個字元。Claude Code 會移除 ANSI 跳脫序列與控制字元，並合併空白字元 |
| `cooldownSessions` | 否 | Claude Code 再次顯示此提示前要等待的工作階段數，`0` 至 `1000`，預設為 `0` |
| `priority` | 否 | 在未顯示時間相同的提示之間的順序，數值較高者優先，`-10` 至 `10`，預設為 `0` |

Claude Code 會將純字串視為具有上述預設值和依位置產生之 id 的提示，因此當您重新排列清單時，其顯示記錄會重設。為提示指定 `id` 可在編輯之間保留其記錄。

Claude Code 在 `tips` 和 `tipsFile` 中合計最多讀取 200 個提示，並會以除錯警告捨棄無效的項目，而非拒絕整個設定檔。

使用其餘欄位來指定提示檔案、設定前綴，以及隱藏內建提示：

* `tipsFile`：指向本機 JSON 檔案的絕對路徑或 `~/` 路徑，該檔案包含相同項目的陣列，或包含 `tips` 陣列的物件，最大 256 KB。Claude Code 每個程序只讀取該檔案一次，因此會在下次啟動時載入您的編輯。您無法透過[伺服器管理設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)設定此項目；請在那裡部署內嵌的 `tips`，或在磁碟上的 `managed-settings.json` 中部署該路徑。
* `label`：Claude Code 在來自使用者設定、`--settings` 與受管設定之提示前顯示的前綴，最多 40 個字元。預設為 `Tip`，與內建提示的前綴相同，而來自專案和本機設定的提示一律使用此前綴。
* `excludeDefault`：設為 `true` 可隱藏內建提示，只顯示您的提示。當 Claude Code 無法載入您的任何提示時（例如 `tipsFile` 不存在或每個項目都無效），它會保留內建的輪替，而非顯示空白的旋轉指示器。

當有多個設定檔設定此設定鍵時，Claude Code 會顯示所有設定檔中的提示，並從受管設定、`--settings` 旗標與使用者設定中，針對每個欄位取用設定了該欄位且優先順序最高者的 `tipsFile`、`label` 和 `excludeDefault`。

此範例位於您的使用者設定中，會以 `Acme tip` 前綴將一個純字串提示和一個物件提示加入輪替：

```json settings.json theme={null}
{
  "spinnerTipsOverride": {
    "label": "Acme tip",
    "tips": [
      "Run /review before opening a PR",
      {
        "id": "gateway-errors",
        "text": "Seeing 5xx errors? Check the gateway status page first",
        "cooldownSessions": 5,
        "priority": 2
      }
    ]
  }
}
```

範例中的每個欄位都會改變 Claude Code 顯示提示方式的一個面向：

* `label`：Claude Code 會將兩個提示都顯示為 `Acme tip: ...`，而非 `Tip: ...`。
* 純字串：Claude Code 會為其套用預設值，因此它可能在下一個工作階段就再次出現。
* `id`：Claude Code 以 `gateway-errors` 作為第二個提示顯示記錄的鍵，因此在您新增或重新排列提示後，其冷卻時間仍然適用。
* `cooldownSessions`：Claude Code 顯示 `gateway-errors` 提示後，要到五個工作階段之後才會再次顯示該提示。
* `priority`：當 `gateway-errors` 提示與另一個提示未顯示的工作階段數相同時（例如兩者都尚未顯示過），Claude Code 會先顯示 `gateway-errors`。純字串提示具有預設優先順序 `0`。

當 Claude 工作時，Claude Code 會在旋轉指示器中以您的前綴顯示您的提示，例如 `Acme tip: Run /review before opening a PR`。

### `spinnerVerbs`

回合進行期間，旋轉指示器會顯示輪替的動詞，例如「Accomplishing」、「Architecting」或「Baking」。使用此設定鍵可將您自己的動詞加入該輪替，或以您的動詞取代內建清單。

* **範圍**：[`Any file`](#scopes)
* **類型**：物件，包含字串陣列 `verbs` 和 `mode`，`mode` 為下列之一：
  * `"append"`：Claude Code 將您的動詞加入內建集合
  * `"replace"`：Claude Code 只顯示您的動詞
* **預設值**：未設定，因此 Claude Code 使用內建動詞

此範例會將兩個動詞加入內建集合：

```json settings.json theme={null}
{
  "spinnerVerbs": {
    "mode": "append",
    "verbs": ["Pondering", "Crafting"]
  }
}
```

在 `"replace"` 模式下若 `verbs` 陣列為空，Claude Code 會保留內建動詞。

### `statusLine`

執行您自己的命令，在提示詞下方渲染[狀態列](https://code.claude.com/docs/zh-TW/statusline.md)，顯示模型、成本或 git 分支等上下文資訊。選用欄位可調整間距、加入定期重新執行，並在您的指令碼自行渲染 `vim.mode` 時隱藏內建的 vim 模式指示器。

* **範圍**：[`Any file`](#scopes)。當 [`allowManagedHooksOnly`](#allowmanagedhooksonly) 開啟，或在受管設定之外設定了 [`disableAllHooks`](#disableallhooks) 時，只會執行受管設定的值。
* **類型**：物件，包含設為 `"command"` 的 `type` 和 `command` 字串，以及選用的 `padding`（字元數）、`refreshInterval`（秒數，最小值為 `1`）和 `hideVimModeIndicator`（Boolean）
* **預設值**：未設定，因此沒有狀態列

此範例會輸出模型名稱與上下文使用量，並加入兩個字元的水平間距：

```json settings.json theme={null}
{
  "statusLine": {
    "type": "command",
    "command": "jq -r '\"[\\(.model.display_name)] \\(.context_window.used_percentage // 0)% context\"'",
    "padding": 2
  }
}
```

此範例需要安裝 [`jq`](https://jqlang.org/)，並在 shell 中執行。關於 PowerShell 與 Git Bash 的對應寫法，請參閱 [Windows 設定](https://code.claude.com/docs/zh-TW/statusline.md#windows-configuration)；完整的設定方式請參閱[手動設定狀態列](https://code.claude.com/docs/zh-TW/statusline.md#manually-configure-a-status-line)。

### `subagentStatusLine`

當 Claude 執行 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 時，Claude Code 會在提示詞下方的任務顯示區中列出它們，每個 subagent 一列，顯示 `name · description · token count`。此設定鍵讓您執行自己的命令來改寫這些列，例如以百分比顯示每個 subagent 的上下文使用量。每次重新整理時，Claude Code 會將可見的列以一個 JSON 物件透過 stdin 傳送，其中的 `tasks` 陣列包含每個 subagent 的 `id`、`name`、`status`、`model`、`tokenCount` 等資訊，並以您回寫為 `{"id", "content"}` 行的內容取代對應 `id` 的列。您未回寫的列會保留預設渲染。

* **範圍**：[`Any file`](#scopes)。當 [`allowManagedHooksOnly`](#allowmanagedhooksonly) 開啟，或在受管設定之外設定了 [`disableAllHooks`](#disableallhooks) 時，只會執行受管設定的值。
* **類型**：物件，包含設為 `"command"` 的 `type` 和 `command` 字串
* **預設值**：未設定，因此 Claude Code 渲染預設的列

```json settings.json theme={null}
{
  "subagentStatusLine": {
    "type": "command",
    "command": "jq -c '.tasks[] | {id, content: \"\\(.name): \\(.tokenCount) tokens\"}'"
  }
}
```

請參閱 [Subagent 狀態列](https://code.claude.com/docs/zh-TW/statusline.md#subagent-status-lines)。

### `syntaxHighlightingDisabled`

Claude Code 會以其內建的語法突顯器，依語言為終端機中顯示的差異、程式碼區塊與檔案預覽上色；不涉及任何外掛或語言伺服器。將此設定鍵設為 `true` 即可改以純文字顯示，例如當色彩與您的終端機主題衝突或拖慢螢幕閱讀器時。

* **範圍**：[`Any file`](#scopes)
* **類型**：Boolean
  * `true`：Claude Code 會關閉差異、程式碼區塊與檔案預覽中的語法突顯
  * `false`：Claude Code 會突顯語法
* **預設值**：`false`

```json settings.json theme={null}
{
  "syntaxHighlightingDisabled": true
}
```

### `terminalProgressBarEnabled`

部分終端機可以在分頁或工作列上顯示其中執行之程式的進度指示器。當 Claude 工作時，Claude Code 會向終端機回報進行中的狀態，讓您可以從其他分頁或視窗看出工作階段是否仍在忙碌。當回合結束後仍有[背景 subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#run-subagents-in-foreground-or-background) 或[動態工作流程](https://code.claude.com/docs/zh-TW/workflows.md)在執行時，指示器會保持顯示，並在工作階段閒置後清除。

Claude Code 只在支援此指示器的終端機中回報：ConEmu、Ghostty 1.2.0 或更新版本，以及 iTerm2 3.6.6 或更新版本。將此設定鍵設為 `false` 可讓 Claude Code 停止回報。在 `/config` 中顯示為 **Terminal progress bar**。

* **範圍**：[`Any file`](#scopes)。當沒有設定檔設定此項目時，會套用舊版本在 `~/.claude.json` 中的值。
* **類型**：Boolean
  * `true`：您會在支援的終端機中看到終端機進度列
  * `false`：Claude Code 會隱藏終端機進度列
* **預設值**：`true`

```json settings.json theme={null}
{
  "terminalProgressBarEnabled": false
}
```

### `terminalTitleFromRename`

Claude Code 會設定您終端機分頁的標題。預設情況下，它會使用從對話產生的標題，而一旦您以 `/rename` 或 `--name` 為工作階段[命名](https://code.claude.com/docs/zh-TW/sessions.md#name-your-sessions)，分頁就會改為顯示該名稱。將此設定鍵設為 `false`，即使在您為工作階段命名後，分頁仍會保留產生的標題。名稱本身仍然生效，因此 `/resume <name>` 和工作階段選擇器都能找到它。

* **範圍**：[`Any file`](#scopes)
* **類型**：Boolean
  * `true`：終端機分頁標題會顯示您設定的工作階段名稱
  * `false`：分頁會保留 Claude Code 從您的對話產生的標題
* **預設值**：`true`

```json settings.json theme={null}
{
  "terminalTitleFromRename": false
}
```

若要讓 Claude Code 完全停止更新終端機標題，請改為將 [`CLAUDE_CODE_DISABLE_TERMINAL_TITLE`](https://code.claude.com/docs/zh-TW/env-vars) 設為 `1`。

### `theme`

選擇介面的色彩主題。在 `/config` 中顯示為 **Theme**。

* **範圍**：[`Any file`](#scopes)。當沒有設定檔設定此項目時，會套用舊版本在 `~/.claude.json` 中的值。
* **類型**：字串，為下列之一：
  * `"auto"`：配合您終端機的淺色或深色背景
  * `"dark"`：深色主題
  * `"light"`：淺色主題
  * `"dark-daltonized"`：使用色盲友善色彩的深色主題
  * `"light-daltonized"`：使用色盲友善色彩的淺色主題
  * `"dark-ansi"`：僅使用您終端機 ANSI 色盤的深色主題
  * `"light-ansi"`：僅使用您終端機 ANSI 色盤的淺色主題
  * `"custom:<slug>"` 或 `"custom:<plugin-name>:<slug>"`：來自 `~/.claude/themes/` 或外掛的自訂主題
* **預設值**：`"dark"`

```json settings.json theme={null}
{
  "theme": "light-daltonized"
}
```

請參閱[建立自訂主題](https://code.claude.com/docs/zh-TW/terminal-config.md#create-a-custom-theme)。

### `timeFormat`

選擇 Claude Code 如何書寫其在介面中顯示的時間，例如每則回合時間訊息結尾的 `done 6:05 PM`，以及[逐字稿檢視器](https://code.claude.com/docs/zh-TW/interactive-mode.md#transcript-viewer)中的時間戳記。若要選擇預設格式，請執行 `/config` 並設定 **Time format**。需要 Claude Code v2.1.257 或更新版本。

* **範圍**：[`Any file`](#scopes)
* **類型**：字串，為下列之一：
  * `"auto"`：與未設定相同；每個時間保留其內建格式，回合時間訊息會依循您的地區設定
  * `"12-hour"`：12 小時制
  * `"24-hour"`：24 小時制
  * `"24-hour-utc"`：UTC 的 24 小時制，分鐘後加上 `Z`，例如 `18:05Z`；此預設格式下 Claude Code 會忽略 [`timeZone`](#timezone)
  * strftime 模式，例如 `"%H:%M"`：Claude Code 以該模式書寫每個時間。任何包含 `%` 的值都是模式，而預設格式以外的任何其他值都視為 `"auto"`
* **預設值**：`"auto"`

```json settings.json theme={null}
{
  "timeFormat": "24-hour"
}
```

`/config` 只提供預設格式，因此若要使用 strftime 模式，請將此設定鍵加入設定檔。此範例會以兩位數的 24 小時制顯示每個時間：

```json settings.json theme={null}
{
  "timeFormat": "%H:%M"
}
```

回合時間訊息與逐字稿檢視器接著會顯示 `18:05` 之類的時間。在逐字稿檢視器中，模式即為完整的時間戳記，因此若您希望在其中顯示日期，請加入日期指令。此範例會將日期放在時鐘前面：

```json settings.json theme={null}
{
  "timeFormat": "%Y-%m-%d %H:%M"
}
```

相同的介面接著會顯示 `2026-09-01 18:05` 之類的時間。

### `timeZone`

以系統時區以外的時區顯示介面中的時間。將其設為 [IANA 時區名稱](https://www.iana.org/time-zones)，例如 `"UTC"` 或 `"Europe/Dublin"`。[`timeFormat`](#timeformat) 所控制的時間便會以此時區顯示。如果 `timeFormat` 為 `"24-hour-utc"`，時間會維持 UTC，且 Claude Code 會忽略此設定鍵。`/config` 中沒有此設定鍵的列，因此請在設定檔中設定。需要 Claude Code v2.1.257 或更新版本。

* **範圍**：[`Any file`](#scopes)
* **類型**：字串，為 IANA 時區名稱。當 Claude Code 無法識別該名稱時，會使用您的系統時區
* **預設值**：未設定，因此時間以您的系統時區顯示

```json settings.json theme={null}
{
  "timeZone": "Europe/Dublin"
}
```

### `tui`

選擇終端機 UI 渲染器。使用 `"fullscreen"` 以採用具有虛擬化捲動記錄、無閃爍的[替代畫面渲染器](https://code.claude.com/docs/zh-TW/fullscreen.md)，或使用 `"default"` 以採用經典的主畫面渲染器。執行 `/tui fullscreen` 或 `/tui default` 會為您寫入此設定鍵。

* **範圍**：[`Any file`](#scopes)
* **類型**：字串，為下列之一：
  * `"default"`：經典的主畫面渲染器
  * `"fullscreen"`：具有虛擬化捲動記錄、無閃爍的替代畫面渲染器
* **預設值**：未設定，因此 Claude Code 會[為您選擇渲染器](https://code.claude.com/docs/zh-TW/fullscreen.md#fullscreen-by-default)
* **個別工作階段覆寫**：[`CLAUDE_CODE_NO_FLICKER`](https://code.claude.com/docs/zh-TW/env-vars) 和 [`CLAUDE_CODE_DISABLE_ALTERNATE_SCREEN`](https://code.claude.com/docs/zh-TW/env-vars) 在單一工作階段中優先於此設定鍵：`CLAUDE_CODE_NO_FLICKER=1` 會開啟全螢幕，而 `CLAUDE_CODE_NO_FLICKER=0` 或 `CLAUDE_CODE_DISABLE_ALTERNATE_SCREEN=1` 會將其關閉；當兩者都設定時，Claude Code 會將其關閉

```json settings.json theme={null}
{
  "tui": "fullscreen"
}
```

在 tmux `-CC` 下或透過 SSH 連線至 Windows 時，除非您設定 `CLAUDE_CODE_NO_FLICKER=1`，否則 Claude Code 會保留經典渲染器。從 [agent view](https://code.claude.com/docs/zh-TW/agent-view.md) 開啟的背景工作階段一律使用全螢幕渲染器，不受此設定影響。

### `verbose`

預設情況下，逐字稿會將每個工具呼叫收合為簡短摘要，例如 Claude 執行的命令及其輸出的行數，當您需要詳細資訊時，按下 `Ctrl+O` 即可將整份逐字稿切換為展開檢視。將此設定鍵設為 `true`，即可在每個工具呼叫發生時以內嵌方式顯示其完整的輸入與輸出，這在您為 hook、MCP 伺服器或冗長的 shell 命令除錯時很有用。在 `/config` 中顯示為 **Verbose output**。

* **範圍**：[`Any file`](#scopes)。當沒有設定檔設定此項目時，會套用舊版本在 `~/.claude.json` 中的值。
* **類型**：Boolean
  * `true`：您會看到完整的工具輸出
  * `false`：您會看到截斷的工具輸出摘要
* **預設值**：`false`
* **個別工作階段覆寫**：[`--verbose`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 在單一工作階段中優先於此設定鍵

```json settings.json theme={null}
{
  "verbose": true
}
```

[`viewMode`](#viewmode) 值或持續生效的 `/focus` 選擇會在每個工作階段覆寫此設定鍵。

### `viewMode`

設定 Claude Code 啟動時的逐字稿檢視：`"default"`、`"verbose"` 或 `"focus"`。設定後，它會同時覆寫持續生效的 `/focus` 選擇與 [`verbose`](#verbose) 設定。

* **範圍**：[`Any file`](#scopes)
* **類型**：字串，為下列之一：
  * `"default"`：工具輸出被截斷的一般逐字稿
  * `"verbose"`：含有完整工具輸出的逐字稿
  * `"focus"`：僅顯示您最後的提示詞、附有編輯差異統計的工具呼叫單行摘要，以及最終回應。Focus 檢視需要[全螢幕渲染器](#tui)
* **預設值**：未設定，因此套用 `verbose` 設定與您最後一次的 `/focus` 選擇
* **個別工作階段覆寫**：[`--verbose`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 在單一工作階段中優先於此設定鍵

```json settings.json theme={null}
{
  "viewMode": "focus"
}
```

### `vimInsertModeRemaps`

在 [vim 編輯器模式](https://code.claude.com/docs/zh-TW/interactive-mode.md#vim-editor-mode)中，將兩鍵的 INSERT 模式序列對應至 Escape。每個鍵都必須是依序輸入的恰好兩個可列印字元，且 `"<Esc>"` 是唯一支援的目標；Claude Code 會忽略其他項目。

* **範圍**：[`User or managed`](#scopes)。儲存庫無法重新對應您的按鍵。
* **類型**：將兩字元序列對應至 `"<Esc>"` 的物件
* **預設值**：未設定

```json settings.json theme={null}
{
  "vimInsertModeRemaps": {
    "jj": "<Esc>"
  }
}
```

除非 `editorMode` 為 `"vim"`，否則沒有作用。請參閱[重新對應 INSERT 模式按鍵序列](https://code.claude.com/docs/zh-TW/interactive-mode.md#remap-insert-mode-key-sequences)。

### `voice`

開啟[語音聽寫](https://code.claude.com/docs/zh-TW/voice-dictation.md)並選擇聽寫鍵的行為方式。當您執行 `/voice` 時，Claude Code 會為您寫入此物件。

* **範圍**：[`Any file`](#scopes)
* **類型**：物件，包含 Boolean 的 `enabled`、僅在按住模式下適用的 Boolean `autoSubmit`，以及 `mode`，`mode` 為下列之一：
  * `"hold"`：說話時按住聽寫鍵，放開即停止
  * `"tap"`：按一下鍵開始錄音，再按一下即傳送
* **預設值**：未設定，因此聽寫為關閉；當 `enabled` 為 `true` 且 `mode` 未設定時，Claude Code 使用 `"hold"`

此範例會開啟聽寫，並讓按鍵以按一下開始錄音、再按一下傳送的方式運作：

```json settings.json theme={null}
{
  "voice": {
    "enabled": true,
    "mode": "tap"
  }
}
```

`autoSubmit` 會在按住模式下您放開按鍵時傳送提示詞。語音聽寫需要 claude.ai 帳戶。

### `voiceEnabled`

> [!WARNING]
>
> 自 v2.1.92 起已棄用，當時已由 [`voice`](#voice) 物件取代。Claude Code 仍會讀取它，讓較舊的設定檔能繼續運作，但新的設定應設定 `voice.enabled`。

以早於 `voice` 物件的單一 Boolean 形式開啟語音聽寫。當兩者都設定時，套用 `voice.enabled`。

* **範圍**：[`Any file`](#scopes)
* **類型**：Boolean
  * `true`：當您以 claude.ai 帳戶登入且您組織的政策允許語音時，語音聽寫為開啟，除非已設定 `voice.enabled`
  * `false`：語音聽寫為關閉，除非已設定 `voice.enabled`
* **預設值**：未設定

```json settings.json theme={null}
{
  "voiceEnabled": true
}
```

### `wheelScrollAccelerationEnabled`

在[全螢幕渲染](https://code.claude.com/docs/zh-TW/fullscreen.md#mouse-wheel-scrolling)中快速捲動時加速滑鼠滾輪的捲動速度。將其設為 `false` 可讓每個滾輪刻度以固定速率捲動。

* **範圍**：[`Any file`](#scopes)
* **類型**：Boolean
  * `true`：Claude Code 在快速捲動時加速滑鼠滾輪的捲動速度
  * `false`：Claude Code 以每個滾輪刻度固定的速率捲動
* **預設值**：`true`

```json settings.json theme={null}
{
  "wheelScrollAccelerationEnabled": false
}
```

## Git 和歸屬

控制 Claude Code 新增至提交和拉取請求的歸屬，以及它如何與 git 搭配運作。

### `attribution`

自訂 Claude Code 新增至 git 提交和拉取請求的歸屬。提交預設會取得 [git trailer](https://git-scm.com/docs/git-interpret-trailers)，例如 `Co-Authored-By`；拉取請求描述會取得純文字。使用下方的子鍵分別設定每個部分。

* **Scope**: [`Any file`](#scopes)
* **Type**: 包含 `commit` 和 `pr` 字串以及 `sessionUrl` 布林值的物件，或 `false` 以隱藏所有歸屬。`false` 值需要 Claude Code v2.1.281 或更新版本；較早版本會拒絕它，並[略過整個使用者、專案或本機設定檔](https://code.claude.com/docs/zh-TW/settings.md#fix-a-broken-settings-file)
* **Default**: 未設定，因此 Claude Code 使用每個子鍵下方顯示的標準歸屬

若要隱藏所有歸屬，請將 `attribution` 設定為 `false`。在較早版本也會讀取的設定檔中，改為將 [`commit`](#attribution-commit) 和 [`pr`](#attribution-pr) 設定為空字串，並將 [`sessionUrl`](#attribution-sessionurl) 設定為 `false`。

此範例會取代提交歸屬、移除拉取請求歸屬，並捨棄工作階段連結：

```json settings.json theme={null}
{
  "attribution": {
    "commit": "Generated with AI\n\nCo-Authored-By: AI <ai@example.com>",
    "pr": "",
    "sessionUrl": false
  }
}
```

一旦您設定 `commit` 或 `pr`，Claude Code 就會忽略已棄用的 `includeCoAuthoredBy` 設定，並對您未設定的兩者使用其預設文字。

Claude Code 告訴 Claude，您自己關於歸屬的指示（例如 CLAUDE.md 或[記憶](https://code.claude.com/docs/zh-TW/memory.md)規則）優先於這些提交和 PR 行，除非該行在[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)中設定。

### `includeCoAuthoredBy`

> [!WARNING]
>
> 自 v2.0.62 起已棄用，當時 [`attribution`](#attribution) 取代了它。Claude Code 仍會讀取它，但新設定應該設定 `attribution`。

改用 [`attribution`](#attribution)，它會取代此鍵並讓您分別變更或隱藏提交 trailer、拉取請求文字和工作階段連結。Claude Code 仍會接受來自早於 `attribution` 的設定檔中的 `includeCoAuthoredBy: false`，但一旦您設定 `attribution.commit` 或 `attribution.pr`，就會忽略它。

* **Scope**: [`Any file`](#scopes)
* **Type**: 布林值
  * `true`: 與未設定相同；Claude Code 新增提交 trailer 和拉取請求歸屬文字
  * `false`: Claude Code 會省略提交 trailer 和拉取請求歸屬文字，除非 `attribution` 設定 `commit` 或 `pr`，在這種情況下會套用 [`attribution`](#attribution) 規則
* **Default**: `true`

```json settings.json theme={null}
{
  "includeCoAuthoredBy": false
}
```

若要隱藏所有歸屬，請參閱 [`attribution`](#attribution)。

### `includeGitInstructions`

Claude Code 給予 Claude 兩個與 git 相關的內容片段：其內建的提交和拉取請求撰寫方式說明（在 Bash 工具的描述中），以及您存放庫的 git 狀態快照。快照保存目前分支、主要分支、`git status` 輸出和最近的提交。Claude Code 在對話開始時讀取它。

將此鍵設定為 `false` 以將兩者都排除，例如當您使用自己的 git 工作流程技能時。

* **Scope**: [`Any file`](#scopes)
* **Type**: 布林值
  * `true`: Claude Code 包含其內建的提交和拉取請求工作流程說明和 git 狀態快照。雲端工作階段永遠不會包含快照
  * `false`: Claude Code 將兩者都排除
* **Default**: `true`
* **Per-session overrides**: [`CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS`](https://code.claude.com/docs/zh-TW/env-vars) 對此鍵優先

```json settings.json theme={null}
{
  "includeGitInstructions": false
}
```

若您在[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)或 Agent SDK 中取代系統提示詞，即使此鍵為 `true`，工作階段也會在沒有快照的情況下開始：

* **`-p` 執行**：當您傳遞 [`--system-prompt`](https://code.claude.com/docs/zh-TW/cli-reference#system-prompt-flags) 或 `--system-prompt-file` 時，即會取代提示詞。當您執行具有自己提示詞的自訂 agent（透過 [`--agent`](https://code.claude.com/docs/zh-TW/sub-agents#invoke-subagents-explicitly) 或 [`agent`](#agent) 設定選取）時，也會取代提示詞。在 [bare 模式](https://code.claude.com/docs/zh-TW/headless.md#start-faster-with-bare-mode)之外，若要保留快照，請在不使用自訂 agent 的情況下執行，並使用 [`--append-system-prompt`](https://code.claude.com/docs/zh-TW/cli-reference#system-prompt-flags) 新增您的指示，而不是取代提示詞。
* **[Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/modifying-system-prompts.md)**：您會以自訂系統提示詞或自訂主執行緒 agent 取代提示詞。若您未設定系統提示詞，SDK 會使用其最精簡的預設值，工作階段同樣會在沒有快照的情況下開始。在 [bare 模式](https://code.claude.com/docs/zh-TW/headless.md#start-faster-with-bare-mode)之外，若要保留快照，請使用 `claude_code` 預設集，且不使用自訂 `agent`。

### `prUrlTemplate`

將 Claude Code 呈現的 PR 連結（在頁尾徽章和工具結果摘要中）指向內部程式碼審查工具，而不是 `github.com`。Claude Code 會從 PR URL 替換 `{host}`、`{owner}`、`{repo}`、`{number}` 和 `{url}`。[GitLab 合併請求](https://code.claude.com/docs/zh-TW/interactive-mode.md#gitlab-merge-requests)連結在兩個表面上都保持其 GitLab URL。

* **Scope**: [`Any file`](#scopes)
* **Type**: 字串，使用五個預留位置中任何一個的 URL 範本
* **Default**: 未設定

```json settings.json theme={null}
{
  "prUrlTemplate": "https://reviews.example.com/{owner}/{repo}/pull/{number}"
}
```

Claude Code 只會將範本套用至它自己呈現的連結；Claude 在訊息中撰寫的 PR 編號（例如 `#123`）會保持 Claude 撰寫的樣子。沒有 `/pull/<number>` 形狀的 URL 會保持不變。

### `attribution.commit`

設定 Claude Code 新增至 git 提交的歸屬文字，包括任何 trailer。將其設定為空字串以隱藏提交歸屬。

* **Scope**: [`Any file`](#scopes)
* **Type**: 字串
* **Default**: 未設定，因此 Claude Code 新增 `Co-Authored-By: <name> <noreply@anthropic.com>`。名稱是工作階段的作用中模型，例如 `Claude Sonnet 5`。當[子代理](https://code.claude.com/docs/zh-TW/sub-agents.md)進行提交時，trailer 會命名子代理的模型。
  * 當 Claude Code 識別模型為 Claude 模型但無法確認其確切版本時，它會單獨寫入 `Claude`。
  * 當它無法將模型 ID 符合至任何 Claude 模型（例如透過自訂 [`ANTHROPIC_BASE_URL`](https://code.claude.com/docs/zh-TW/env-vars) 提供的第三方模型）時，它會寫入 `Claude Code`。

此範例會將預設 trailer 取代為自訂行和自訂 `Co-Authored-By` trailer：

```json settings.json theme={null}
{
  "attribution": {
    "commit": "Generated with AI\n\nCo-Authored-By: AI <ai@example.com>"
  }
}
```

### `attribution.pr`

設定 Claude Code 新增至拉取請求描述的歸屬文字。將其設定為空字串以隱藏拉取請求歸屬。

* **Scope**: [`Any file`](#scopes)
* **Type**: 字串
* **Default**: 未設定，因此 Claude Code 新增 `🤖 Generated with [Claude Code](https://claude.com/claude-code)`

```json settings.json theme={null}
{
  "attribution": {
    "pr": ""
  }
}
```

### `attribution.sessionUrl`

選擇 Claude Code 是否在從[雲端](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)或 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 工作階段提交或開啟拉取請求時附加 claude.ai 工作階段連結。Claude Code 在提交上新增連結作為 `Claude-Session` trailer，並在拉取請求描述中作為連結。將其設定為 `false` 以省略連結。

* **Scope**: [`Any file`](#scopes)
* **Type**: 布林值
  * `true`: Claude Code 在從雲端或 Remote Control 工作階段提交或開啟拉取請求時附加 claude.ai 工作階段連結
  * `false`: Claude Code 省略連結
* **Default**: `true`

```json settings.json theme={null}
{
  "attribution": {
    "sessionUrl": false
  }
}
```

## Hook 與自動化

註冊 hook、限制哪些 hook 執行，以及控制工作流程。如需 hook 事件和 payload，請參閱 [hooks 參考](https://code.claude.com/docs/zh-TW/hooks.md)。

### `allowedHttpHookUrls`

限制 [HTTP hook](https://code.claude.com/docs/zh-TW/hooks.md#http-hook-fields) 可以指向的 URL。當您定義此設定鍵時，Claude Code 只有在 HTTP hook 的 URL 符合其中一個模式時才會執行該 hook，並阻止其餘的而不執行它們；空陣列會阻止每個 HTTP hook。

* **範圍**：[`Any file`](#scopes)。陣列會跨設定檔合併。
* **類型**：URL 模式陣列，以 `*` 作為萬用字元
* **預設**：未設定，因此允許任何 URL

此範例允許 `https://hooks.example.com/` 下的任何 URL 和任何 `http://localhost` URL：

```json settings.json theme={null}
{
  "allowedHttpHookUrls": ["https://hooks.example.com/*", "http://localhost:*"]
}
```

主機名稱比對不區分大小寫，並將 `hooks.example.com.`（帶有標記完整網域名稱的尾端點）視為與 `hooks.example.com` 相同，這與 DNS 的處理方式一致。允許清單適用於來自每個來源的 hook，包括受管設定。

在 Agent SDK 的 `managedSettings` 選項中，當此設定鍵的清單有項目時，Claude Code 會忽略它，因此請改為在 SDK 的 [`settings` 選項](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#options)中傳入該清單。請參閱[空清單在父設定中的作用](https://code.claude.com/docs/zh-TW/claude-apps-gateway#how-hook-and-skill-keys-in-parent-settings-take-effect)。

### `allowManagedHooksOnly`

將 hook 執行限制為您的組織部署的 hook。

* **範圍**：[`Managed`](#scopes)
* **類型**：布林值
  * `true`：只有受管 hook 執行，加上 Agent SDK hook 和您的受管設定強制啟用的外掛中的 hook。請參閱 [在 `allowManagedHooksOnly` 下執行的內容](#what-runs-under-allowmanagedhooksonly)
  * `false`：來自每個設定範圍和外掛的 hook 都會執行
* **預設**：未設定，因此來自每個設定範圍和外掛的 hook 都會執行

```json managed-settings.json theme={null}
{
  "allowManagedHooksOnly": true
}
```

#### 在 `allowManagedHooksOnly` 下執行的內容

當您將其設定為 `true` 時，Claude Code 會變更載入哪些 hook 和類似 hook 的命令：

* **受管和 SDK hook 執行**：來自受管設定的 hook，以及 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 在程序中註冊的 hook
* **強制啟用的外掛 hook 執行**：來自您的受管設定透過 [`enabledPlugins`](#enabledplugins) 強制啟用之外掛的 hook。Claude Code 以完整的 `plugin@marketplace` ID 進行比對，因此來自不同市集的同名外掛仍會被阻止。這讓您可以透過組織市集分發經過審核的 hook，同時阻止其他所有內容。此類外掛中的 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md) 只有在[被視為您組織的 mod](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md#install-your-organizations-mods) 時才會載入
* **來自其他外掛的監視器被阻止**：除非外掛被強制啟用，否則外掛的[監視器](https://code.claude.com/docs/zh-TW/plugins/components.md#monitors)不會啟動。需要 Claude Code v2.1.310 或更新版本
* **其他所有內容被阻止**：使用者、專案和本機 hook、來自其他已安裝外掛的 hook 和 mod，以及在 agent frontmatter 中宣告的 hook。[內建於 Claude Code 的 mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md#mods-built-into-claude-code) 會繼續執行。若只要阻止使用者的 mod，請改為設定 [`allowManagedModsOnly`](https://code.claude.com/docs/zh-TW/plugins/mods/admin#set-options-on-the-built-in-guard)。
* **命令來源的外掛被停用**：Claude Code 也會停用具有 [`command` 來源](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference#command-plugin-source)的外掛，包括在受管 `enabledPlugins` 中強制啟用的外掛，除非您明確將 [`disableCommandPluginSources`](#disablecommandpluginsources) 設定為 `false`
* **市集 `headersHelper` 命令被阻止**：Claude Code 也會阻止市集 [`headersHelper` 命令](https://code.claude.com/docs/zh-TW/plugins/host-marketplace#authenticate-archive-downloads)，除非 [`disableCommandPluginSources`](#disablecommandpluginsources) 明確設定為 `false`，但受管設定本身宣告的市集除外。需要 Claude Code v2.1.238 或更新版本
* **狀態列和檔案建議縮限為受管設定**：Claude Code 只從受管設定讀取 [`statusLine`](https://code.claude.com/docs/zh-TW/statusline)、[`fileSuggestion`](#filesuggestion) 和 [`subagentStatusLine`](https://code.claude.com/docs/zh-TW/statusline#subagent-status-lines)，遵循[狀態列和檔案建議閘道](#status-line-and-file-suggestion-gates)

設定此設定鍵時，[`/goal`](https://code.claude.com/docs/zh-TW/goal) 命令無法執行，因為它依賴於 hook。

### `disableAllHooks`

關閉 [hook](https://code.claude.com/docs/zh-TW/hooks.md#disable-or-remove-hooks)、任何自訂[狀態列](https://code.claude.com/docs/zh-TW/statusline.md)和任何自訂[檔案建議](#filesuggestion)命令。使用它可以暫時關閉所有這些項目，而無需從您的設定中刪除它們。

* **範圍**：[`Any file`](#scopes)。只有受管設定可以停用受管 hook。
* **類型**：布林值
  * `true`：Claude Code 關閉 hook、任何自訂狀態列和任何自訂檔案建議命令
  * `false`：hook、狀態列和檔案建議命令都會執行
* **預設**：未設定，因此 hook 會執行

```json settings.json theme={null}
{
  "disableAllHooks": true
}
```

影響範圍取決於哪個檔案包含此設定鍵：

* **在受管設定中**：Claude Code 停用每個已設定的 hook，包括受管 hook，並繼續執行 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 在程序中註冊的 hook
* **在 Agent SDK 的 `managedSettings` 選項中**：在管理員部署受管設定的機器上，除非管理員[允許嵌入主機新增政策](https://code.claude.com/docs/zh-TW/managed-settings.md#let-an-embedding-host-add-policy)，否則 Claude Code 會忽略此設定鍵。在此設定鍵生效的情況下，使用者、專案、本機和外掛 hook 會停止，SDK 的 `settings` 選項中的任何 hook 也會停止。管理員的受管 hook、[強制啟用](#enabledplugins)之外掛的 hook，以及您的 [SDK hook 回呼](https://code.claude.com/docs/zh-TW/agent-sdk/hooks.md)會繼續執行。需要 Claude Code v2.1.309 或更新版本。
* **在任何其他設定檔中**：Claude Code 停用使用者、專案、本機和外掛 hook；受管 hook、Agent SDK hook，以及在受管 [`enabledPlugins`](#enabledplugins) 中強制啟用之外掛的 hook 會繼續執行

此設定鍵也會停止 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md)，也就是其程式碼會註冊 hook 的外掛：

* **在受管設定中**：每個已安裝外掛中的 mod 都會停止，包括您組織的 mod
* **在任何其他設定檔中**：您安裝的 mod 會停止，而[您組織的 mod](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md#install-your-organizations-mods) 會繼續執行

在這兩種情況下，內建於 Claude Code 的 mod 都會繼續執行。每個內建 mod 都有[各自的開關](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md#mods-built-into-claude-code)。

當受管設定設定此設定鍵時，要讓 Agent SDK hook 繼續執行需要 Claude Code v2.1.242 或更新版本。

當 hook 被停用時，[`/goal`](https://code.claude.com/docs/zh-TW/goal) 命令無法執行，且 `/hooks` 選單會顯示通知，而不是您的 hook。

#### 狀態列和檔案建議閘道

Claude Code 會依下列順序，為 `statusLine`、`fileSuggestion` 和 `subagentStatusLine` 做出兩項決定：

* **完全關閉**：當受管設定設定了 `disableAllHooks` 時，或當資料夾在與[設定檔中的 hook 相同的工作區信任規則](https://code.claude.com/docs/zh-TW/permissions.md#what-runs-before-you-trust-a-folder)下不受信任時
* **縮限為受管設定**：當設定了 [`allowManagedHooksOnly`](#allowmanagedhooksonly) 時、當套用[設定優先順序](https://code.claude.com/docs/zh-TW/hooks.md#disable-or-remove-hooks)後 `disableAllHooks` 在受管設定以外為 `true` 時，或當您使用 `--safe-mode` 啟動 Claude Code 時

在縮限情況下，如果部署了受管值，Claude Code 會執行該值。否則它會跳過您的值而不發出警告：狀態列會被停用，`@` 自動完成會退回使用內建的檔案建議。

### `disableWorkflows`

為您的設定所涵蓋的每個人（例如透過受管設定涵蓋的組織）關閉[動態工作流程](https://code.claude.com/docs/zh-TW/workflows.md#turn-workflows-off)和內建的工作流程命令。若只要為自己開啟或關閉工作流程，請改用 [`enableWorkflows`](#enableworkflows)，`/config` 中的 **Dynamic workflows** 切換開關會將其寫入您的使用者設定。

* **範圍**：[`Any file`](#scopes)
* **類型**：布林值
  * `true`：Claude Code 為您的設定所涵蓋的每個人關閉動態工作流程和內建的工作流程命令
  * `false`：與未設定相同；工作流程是否開啟則取決於 [`enableWorkflows`](#enableworkflows) 和您方案的預設值
* **預設**：`false`
* **每個工作階段覆寫**：[`CLAUDE_CODE_DISABLE_WORKFLOWS`](https://code.claude.com/docs/zh-TW/env-vars) 會為單一工作階段關閉工作流程；無論兩者中哪一個關閉了工作流程，另一個都無法將其重新開啟

```json settings.json theme={null}
{
  "disableWorkflows": true
}
```

### `enableWorkflows`

當您方案的預設值不符合您的需求時，為自己開啟或關閉[動態工作流程](https://code.claude.com/docs/zh-TW/workflows.md)。在 `/config` 中顯示為 **Dynamic workflows**，它會將此設定鍵寫入您的使用者設定，並在您切換回方案預設值時再次移除它。若要從受管設定為每個人關閉工作流程，請改用 [`disableWorkflows`](#disableworkflows)。

* **範圍**：[`Any file`](#scopes)
* **類型**：布林值
  * `true`：Claude Code 為您開啟動態工作流程
  * `false`：Claude Code 為您關閉動態工作流程
* **預設**：未設定，因此工作流程為開啟，除非您使用 Pro 方案，此時為關閉
* **每個工作階段覆寫**：[`CLAUDE_CODE_DISABLE_WORKFLOWS`](https://code.claude.com/docs/zh-TW/env-vars) 會為單一工作階段關閉工作流程，在其設定期間，此處的 `true` 無法將工作流程重新開啟

```json settings.json theme={null}
{
  "enableWorkflows": true
}
```

[`disableWorkflows`](#disableworkflows) 和您組織的工作流程政策也優先於此設定：只要有任何來源關閉工作流程，`enableWorkflows: true` 就無法將其重新開啟。當您的使用者設定以外的來源設定了 `enableWorkflows`，或將 `disableWorkflows` 設定為 `true` 時，Claude Code 會隱藏 `/config` 中的該列。

### `hooks`

在 Claude Code 生命週期中的特定時點（例如工具呼叫之前或工作階段啟動時），以 [hook](https://code.claude.com/docs/zh-TW/hooks.md) 的形式執行您自己的命令、提示詞、agent、HTTP 請求或 MCP 工具；[hooks 參考](https://code.claude.com/docs/zh-TW/hooks.md#hook-events)列出了每個事件、其 payload 和其退出碼。每個事件對應到一個 matcher 群組清單，每個群組列出當 matcher 適用時要執行的處理程式。

* **範圍**：[`Any file`](#scopes)。Hook 會跨檔案合併而非相互取代，且來自受管設定的 hook 無法從其他檔案中移除。
* **類型**：以 [hook 事件](https://code.claude.com/docs/zh-TW/hooks.md#hook-events)為鍵的物件；每個值都是 `{ "matcher", "hooks" }` 群組的陣列，其 `hooks` 項目的 `type` 為 `"command"`、`"prompt"`、`"agent"`、`"http"` 或 `"mcp_tool"`
* **預設**：未設定，因此不會執行任何 hook

此範例在每次 Bash 工具呼叫之前執行一個指令碼：

```json settings.json theme={null}
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "~/.claude/hooks/check-bash.sh" }
        ]
      }
    ]
  }
}
```

如需每個事件、matcher 模式和處理程式欄位，請參閱 [hooks 參考](https://code.claude.com/docs/zh-TW/hooks.md#configuration)。若要關閉 hook，請參閱 [`disableAllHooks`](#disableallhooks)；若要將 hook 限制為您的組織部署的 hook，請參閱 [`allowManagedHooksOnly`](#allowmanagedhooksonly)。

### `httpHookAllowedEnvVars`

[HTTP hook](https://code.claude.com/docs/zh-TW/hooks.md#http-hook-fields) 可以將環境變數的值放入請求標頭中，例如 `Authorization: Bearer $HOOK_TOKEN` 標頭，但僅限於該 hook 在其自己的 `allowedEnvVars` 中列出的變數。此設定鍵為每個 HTTP hook 的該清單設定外部限制：只有當 hook 自己的 `allowedEnvVars` 和此設定鍵都列出某個變數時，hook 才能使用該變數。使用它可以防止 hook 讀取不應讀取的祕密，即使 hook 的定義要求讀取也一樣。

* **範圍**：[`Any file`](#scopes)。陣列會跨設定檔合併。
* **類型**：環境變數名稱陣列
* **預設**：未設定，因此套用每個 hook 自己的 `allowedEnvVars` 清單

此範例將標頭插值限制為 `MY_TOKEN` 和 `HOOK_SECRET`：

```json settings.json theme={null}
{
  "httpHookAllowedEnvVars": ["MY_TOKEN", "HOOK_SECRET"]
}
```

允許清單適用於來自每個來源的 hook，包括受管設定。

在 Agent SDK 的 `managedSettings` 選項中，當此設定鍵的清單有項目時，Claude Code 會忽略它，因此請改為在 SDK 的 [`settings` 選項](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#options)中傳入該清單。請參閱[空清單在父設定中的作用](https://code.claude.com/docs/zh-TW/claude-apps-gateway#how-hook-and-skill-keys-in-parent-settings-take-effect)。

### `workflowKeywordTriggerEnabled`

選擇在提示詞中輸入關鍵字 `ultracode` 是否會觸發[動態工作流程](https://code.claude.com/docs/zh-TW/workflows.md#ask-for-a-workflow-in-your-prompt)。將其設定為 `false`，即可輸入該字而不觸發工作流程。

* **範圍**：[`Any file`](#scopes)。在 `/config` 中顯示為 **Ultracode keyword trigger**。
* **類型**：布林值
  * `true`：在提示詞中輸入 `ultracode` 會觸發動態工作流程
  * `false`：您可以輸入該字而不觸發工作流程
* **預設**：`true`

```json settings.json theme={null}
{
  "workflowKeywordTriggerEnabled": false
}
```

`ultracode` effort 設定、`/workflows` 和已儲存的工作流程命令不受影響。

### `workflowSizeGuideline`

設定 [Claude 在其撰寫的動態工作流程中所瞄準的 agent 數量](https://code.claude.com/docs/zh-TW/workflows.md#set-a-size-guideline)。Claude Code 將此值作為建議而非強制上限傳送給 Claude：`"small"` 要求少於 5 個 agent，`"medium"` 少於 10 個，`"large"` 少於 50 個。當您想要限制工作流程的花費時，請選擇 `"small"`。

* **範圍**：[`Any file`](#scopes)。設定檔中的值優先於 `/config` 中的 **Dynamic workflow size** 選項（Claude Code 將其儲存在 `~/.claude.json` 中），且當設定檔設定此設定鍵時，Claude Code 會隱藏該列。
* **類型**：字串，為下列其中之一：
  * `"unrestricted"`：無指引，因此 Claude 會依任務調整工作流程規模
  * `"small"`：Claude 以少於 5 個 agent 為目標
  * `"medium"`：Claude 以少於 10 個 agent 為目標
  * `"large"`：Claude 以少於 50 個 agent 為目標
* **預設**：`"medium"`，或 當您以 Pro 方案登入且使用 Claude Code v2.1.271 或更新版本時為 `"small"`

```json settings.json theme={null}
{
  "workflowSizeGuideline": "small"
}
```

## 外掛與 skill

啟用 plugins，註冊 marketplaces，限制組織允許的 plugin 來源，以及控制哪些 skills 載入。如需安裝和建置 plugins，請參閱 [Plugins](https://code.claude.com/docs/zh-TW/plugins/overview.md)。

### `disableBundledSkills`

關閉 Claude Code 隨附的 [skills](https://code.claude.com/docs/zh-TW/skills.md) 和工作流程。Claude Code 會完全移除捆綁的 skills 和工作流程，而內建命令（例如 `/init`）仍可輸入但會對模型隱藏。

* **Scope**: [`Any file`](#scopes)
* **Type**: Boolean
  * `true`: Claude Code 移除捆綁的 skills 和工作流程，並對模型隱藏內建命令（例如 `/init`）
  * `false`: 捆綁的 skills 載入
* **Default**: 未設定，因此捆綁的 skills 載入
* **Per-session overrides**: [`CLAUDE_CODE_DISABLE_BUNDLED_SKILLS`](https://code.claude.com/docs/zh-TW/env-vars) 設定為 `1` 會在一個工作階段中關閉捆綁的 skills；無論哪一個關閉它們，另一個都無法將其重新開啟

```json settings.json theme={null}
{
  "disableBundledSkills": true
}
```

來自 plugins、`.claude/skills/` 和 `.claude/commands/` 的 skills 不受影響。`/doctor` 仍可輸入，就像內建命令一樣；若要隱藏它，請改為設定 [`DISABLE_DOCTOR_COMMAND`](https://code.claude.com/docs/zh-TW/env-vars)。

### `disableSkillShellExecution`

關閉 [skills](https://code.claude.com/docs/zh-TW/skills.md) 和來自使用者、專案、plugin 或其他目錄來源的自訂命令中 `` !`...` `` 和 ` ```! ` 區塊的內嵌 shell 執行。Claude Code 會用 `[shell command execution disabled by policy]` 取代每個命令，而不是執行它。

* **Scope**: [`Any file`](#scopes)。受管設定中的 `true` 無法被其他地方的 `false` 覆寫。
* **Type**: Boolean
  * `true`: Claude Code 用 `[shell command execution disabled by policy]` 取代每個內嵌 shell 命令，而不是執行它
  * `false`: 內嵌 shell 執行
* **Default**: 未設定，因此內嵌 shell 執行

```json settings.json theme={null}
{
  "disableSkillShellExecution": true
}
```

捆綁的 skills 和透過受管設定部署的 skills 不受影響。

### `skillOverrides`

隱藏或摺疊 [skill](https://code.claude.com/docs/zh-TW/skills.md#override-skill-visibility-from-settings)，無需編輯其 `SKILL.md`。Claude Code 會將每個 skill 名稱下的值套用到 Claude 看到的 skill 清單和您的 `/` 自動完成。

* **Scope**: [`Any file`](#scopes)。`/skills` 功能表寫入 `.claude/settings.local.json`。
* **Type**: 將 skill 名稱對應到以下其中之一的物件：
  * `"on"`: Claude 看到該 skill，您可以輸入 `/name`
  * `"name-only"`: Claude 按名稱看到該 skill，但不看到其描述
  * `"user-invocable-only"`: Claude 看不到該 skill，但您仍可輸入 `/name`
  * `"off"`: Claude 看不到該 skill，且 `/name` 在自動完成中隱藏
* **Default**: 未設定，因此每個 skill 都是 `"on"`

此範例將 `legacy-context` 按名稱列出給 Claude，並從 Claude 和 `/` 自動完成中隱藏 `deploy`：

```json settings.json theme={null}
{
  "skillOverrides": {
    "legacy-context": "name-only",
    "deploy": "off"
  }
}
```

覆寫不適用於 plugin skills，您可以透過 `/plugin` 管理這些。

在受管設定和使用 `--settings` 傳遞的檔案中，捆綁 skill 的別名上的鍵（例如 `/doctor` 的 `checkup`）也適用於該 skill；請參閱[別名鍵如何與 skill 自身名稱上的鍵結合](https://code.claude.com/docs/zh-TW/skills.md#override-skill-visibility-from-settings)。

### `syncClaudeAiSkills`

關閉 [為您的 claude.ai 帳戶啟用的 skills](https://code.claude.com/docs/zh-TW/skills.md#how-synced-skills-behave) 的下載。Claude Code 會在[您使用 claude.ai 帳戶登入的終端機工作階段](https://code.claude.com/docs/zh-TW/skills.md#where-synced-skills-load)（互動式或非互動式）以及 Cowork 和雲端工作階段中，將它們下載到 `~/.claude/skills/synced/`。設定 `false` 以停止該下載並停止載入已同步的 skills。Claude Code 僅接受 `false`：`true` 與未設定相同，不會在其他情況下關閉的地方開啟同步。

* **Scope**: [`User, local, or managed`](#scopes)，以及使用 `--settings` 傳遞的檔案。儲存庫無法為您關閉它。
* **Type**: Boolean
  * `false`: Claude Code 停止下載同步的 skills，並停止載入 `~/.claude/skills/synced/` 中已有的 skills。在使用者或受管設定中，它也會將它們移至 `~/.claude/skills/.trash/`
  * `true`: 與未設定相同
* **Default**: 未設定，因此使用 claude.ai 帳戶登入的工作階段會同步您的 skills

此範例防止機器在任何工作階段中下載帳戶的 skills：

```json settings.json theme={null}
{
  "syncClaudeAiSkills": false
}
```

### `syncClaudeAiPlugins`

關閉 [為您的 claude.ai 帳戶啟用的 plugins](https://code.claude.com/docs/zh-TW/plugins/loading.md#synced-plugins) 的下載。Claude Code 會在您使用 claude.ai 帳戶登入的終端機工作階段開始時和 Cowork 工作階段中，將它們下載到 `~/.claude/plugins/synced/`，並將每個載入為 `<name>@synced`。設定 `false` 以停止該下載並停止載入已同步的 plugins。Claude Code 僅接受 `false`：`true` 與未設定相同，不會在其他情況下關閉的地方開啟同步。需要 Claude Code v2.1.273 或更新版本。

* **Scope**: [`User, local, or managed`](#scopes)，以及使用 `--settings` 傳遞的檔案。儲存庫無法為您關閉它。
* **Type**: Boolean
  * `false`: Claude Code 停止下載同步的 plugins，並停止載入 `~/.claude/plugins/synced/` 中已有的 plugins。在使用者或受管設定中，它也會將它們移至 `~/.claude/plugins/.trash/`
  * `true`: 與未設定相同
* **Default**: 未設定，因此使用 claude.ai 帳戶登入的工作階段會同步您的 plugins

若要關閉一個同步的 plugin 而不是全部，請在 [`enabledPlugins`](#enabledplugins) 中設定 `"<name>@synced": false`。

此範例防止機器在任何工作階段中下載帳戶的 plugins：

```json settings.json theme={null}
{
  "syncClaudeAiPlugins": false
}
```

### `allowedChannelPlugins`

選擇哪些 [channel](https://code.claude.com/docs/zh-TW/channels.md) plugins 可以將訊息推送到您組織中的工作階段。當您設定它時，Claude Code 會使用您的清單取代預設的 Anthropic 允許清單；每個項目命名一個 plugin 和它來自的 marketplace。

* **Scope**: [`Managed`](#scopes)
* **Type**: 物件陣列，每個物件都有 `marketplace` 和 `plugin` 字串。項目可以改為 `"plugin@marketplace"` 字串，例如 `"telegram@claude-plugins-official"`，Claude Code 會將其視為等效物件。字串形式需要 Claude Code v2.1.267 或更新版本；較早版本在 `allowedChannelPlugins` 包含一個時會拒絕整個值
* **Default**: 未設定，因此 Claude Code 使用預設的 Anthropic 允許清單

此範例開啟 channels 並僅允許來自官方 Anthropic marketplace 的 Telegram plugin：

```json managed-settings.json theme={null}
{
  "channelsEnabled": true,
  "allowedChannelPlugins": [
    { "marketplace": "claude-plugins-official", "plugin": "telegram" }
  ]
}
```

空陣列會阻止每個 channel plugin。

此鍵在 channels 通過帳戶的 [`channelsEnabled`](#channelsenabled) 閘道後生效：在 Team 和 Enterprise 方案上，以及在具有受管設定的 Console 帳戶上，這表示 `channelsEnabled: true`。請參閱[限制哪些 channel plugins 可以執行](https://code.claude.com/docs/zh-TW/channels.md#restrict-which-channel-plugins-can-run)。

### `blockedMarketplaces`

為您的組織阻止 plugin marketplace 來源。Claude Code 在 marketplace 新增和 plugin 安裝、更新、重新整理和自動更新時檢查封鎖清單，因此有人在您設定原則之前新增的 marketplace 也無法用於擷取 plugins。在下載前檢查被阻止的來源，因此它們永遠不會接觸檔案系統。

如果您在 [claude.ai 管理員主控台](https://code.claude.com/docs/zh-TW/server-managed-settings.md) 中設定此鍵，claude.ai 也會在您組織中的任何人從 claude.ai 上的 git 儲存庫新增 marketplace 時套用它，如[限制如何運作](https://code.claude.com/docs/zh-TW/plugins/org.md#restrict-what-users-can-install)所述。

* **Scope**: [`Managed`](#scopes)
* **Type**: marketplace 來源物件的陣列，形式與 [`strictKnownMarketplaces`](#allowed-source-types) 相同
* **Default**: 未設定，因此沒有 marketplace 被阻止

此範例阻止一個 GitHub 儲存庫作為 marketplace 來源：

```json managed-settings.json theme={null}
{
  "blockedMarketplaces": [
    { "source": "github", "repo": "untrusted/plugins" }
  ]
}
```

`github` 項目可能使用[所有者萬用字元形式](#owner-wildcards) `"owner/*"` 來阻止該 GitHub 所有者下的每個儲存庫，這需要 Claude Code v2.1.223 或更新版本。新增 `{ "source": "skills-dir" }` 以停止 Claude Code 從 `~/.claude/skills/` 和專案的 `.claude/skills/` 載入 [`@skills-dir` plugins](https://code.claude.com/docs/zh-TW/plugins/loading#plugins-shared-through-a-repository)，而不限制任何 marketplace。請參閱[受管 marketplace 限制](https://code.claude.com/docs/zh-TW/plugins/org.md#restrict-what-users-can-install)。

### `channelsEnabled`

為您的組織允許 [channels](https://code.claude.com/docs/zh-TW/channels.md)。在 claude.ai Team 和 Enterprise 方案上，Claude Code 會阻止 channels，直到您將其設定為 `true`。對於使用 API 金鑰進行驗證的 [Anthropic Console](https://code.claude.com/docs/zh-TW/authentication.md#claude-console-authentication) 帳戶，預設允許 channels。如果您的組織部署受管設定，Claude Code 也會在這些帳戶上阻止 channels，直到您將此鍵設定為 `true`。

* **Scope**: [`Managed`](#scopes)
* **Type**: Boolean
  * `true`: Claude Code 為您的組織允許 channels
  * `false`: 與未設定相同；channels 是否被阻止取決於您的方案，如「Default」所述
* **Default**: 未設定；channels 在 Team 和 Enterprise 方案上以及在具有受管設定的 Console 帳戶上被阻止，在 Pro、Max 和 Ultra 方案上以及在沒有受管設定的 Console 帳戶上被允許

```json managed-settings.json theme={null}
{
  "channelsEnabled": true
}
```

若要限制哪些 plugins 可以在啟用後註冊為 channels，請設定 [`allowedChannelPlugins`](#allowedchannelplugins)。請參閱[企業控制](https://code.claude.com/docs/zh-TW/channels.md#enterprise-controls)。

### `disableCommandPluginSources`

阻止 [`command` plugin 來源](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference#command-plugin-source)，它透過在使用者的機器上執行 marketplace 宣告的命令來安裝 plugin。當您將其設定為 `true` 時，Claude Code 永遠不會執行該命令，不會安裝或更新命令來源的 plugins，並停止載入已安裝的 plugins。設定為 `false` 以明確允許它們。每當它阻止命令來源時，無論您將其設定為 `true` 還是在 [`allowManagedHooksOnly`](#allowmanagedhooksonly) 下保持未設定，它也會阻止 marketplace [`headersHelper` 命令](https://code.claude.com/docs/zh-TW/plugins/host-marketplace#authenticate-archive-downloads)，除了受管設定本身宣告的 marketplace。需要 Claude Code v2.1.229 或更新版本，`headersHelper` 阻止需要 v2.1.238 或更新版本。

* **Scope**: [`Managed`](#scopes)
* **Type**: Boolean
  * `true`: Claude Code 永遠不會執行 marketplace 宣告的命令，不會安裝或更新命令來源的 plugins，並停止載入已安裝的 plugins
  * `false`: Claude Code 明確允許命令來源的 plugins
* **Default**: 未設定，因此 Claude Code 遵循 [`allowManagedHooksOnly`](#allowmanagedhooksonly)：限制 hook 執行到受管設定的組織也會禁用命令來源。在 Agent SDK 的 `managedSettings` 選項中傳遞 [`disableAllHooks: true`](#disableallhooks) 的應用程式，本身並不會禁用命令來源。

```json managed-settings.json theme={null}
{
  "disableCommandPluginSources": true
}
```

需要 Claude Code v2.1.229 或更新版本。

### `pluginSuggestionMarketplaces`

命名其 plugins 可以作為內容相關安裝建議出現的 marketplaces，在微調提示和釘選在 `/plugin` **Discover** 標籤頂部。內建的第一方前端設計提示不受影響。建議來自每個 plugin 在其 marketplace 項目中的 `relevance` 宣告。

* **Scope**: [`Managed`](#scopes)
* **Type**: marketplace 名稱的陣列
* **Default**: 未設定，因此沒有 marketplace 宣告的建議出現

```json managed-settings.json theme={null}
{
  "pluginSuggestionMarketplaces": ["acme-corp-plugins"]
}
```

名稱僅在 marketplace 在機器上註冊且其註冊來源也在相同受管設定中宣告時生效，作為該名稱的 [`extraKnownMarketplaces`](#extraknownmarketplaces) 項目或作為 [`strictKnownMarketplaces`](#strictknownmarketplaces) 的項目。Claude Code 忽略從不同來源在允許清單名稱下註冊的 marketplace。官方 marketplace 豁免於來源要求：僅允許清單其名稱就足夠了，因為該名稱只能從官方 Anthropic 來源註冊。請參閱[按內容建議 plugins](https://code.claude.com/docs/zh-TW/plugins/relevance.md)。

### `pluginTrustMessage`

將您組織自己的文字新增到 Claude Code 在安裝前顯示的 plugin 信任警告中，例如確認來自您內部 marketplace 的 plugins 已經過審查。

* **Scope**: [`Managed`](#scopes)
* **Type**: 字串
* **Default**: 未設定，因此 Claude Code 僅顯示標準警告

```json managed-settings.json theme={null}
{
  "pluginTrustMessage": "All plugins from our marketplace are approved by IT"
}
```

### `strictKnownMarketplaces`

限制您組織中的人員可以新增和安裝 plugins 的 plugin marketplace 來源。Claude Code 在 marketplace 新增和 plugin 安裝、更新、重新整理和自動更新時強制執行允許清單，在任何網路或檔案系統操作之前，因此有人在您設定原則之前新增的 marketplace 一旦其來源不再符合就無法用於擷取 plugins。被阻止的使用者會看到命名受管原則的錯誤。

如果您在 [claude.ai 管理員主控台](https://code.claude.com/docs/zh-TW/server-managed-settings.md) 中設定此鍵，claude.ai 也會在您組織中的任何人從 claude.ai 上的 git 儲存庫新增 marketplace 時套用它，如[限制如何運作](https://code.claude.com/docs/zh-TW/plugins/org.md#restrict-what-users-can-install)所述。

* **Scope**: [`Managed`](#scopes)
* **Type**: marketplace 來源物件的陣列；請參閱[允許的來源類型](#allowed-source-types)
* **Default**: 未設定，因此使用者可以新增任何 marketplace。空陣列是完全鎖定，會阻止每個 marketplace 來源，包括官方 Anthropic marketplace

此範例允許兩個 GitHub 儲存庫，一個釘選到 `v2.0` ref，一個託管 `marketplace.json` URL：

```json managed-settings.json theme={null}
{
  "strictKnownMarketplaces": [
    { "source": "github", "repo": "acme-corp/approved-plugins" },
    { "source": "github", "repo": "acme-corp/security-tools", "ref": "v2.0" },
    { "source": "url", "url": "https://plugins.example.com/marketplace.json" }
  ]
}
```

您也可以將此鍵寫為 `allowedMarketplaces`；[Marketplace 鍵別名](#marketplace-key-aliases)描述 Claude Code 如何處理別名以及哪個版本接受它。此鍵是原則閘道：它控制使用者可能新增的內容，但不註冊任何內容。若要在一個檔案中限制和預先註冊，請參閱[與 `extraKnownMarketplaces` 結合](#combine-with-extraknownmarketplaces)。如需使用者面向的檢視，請參閱[受管 marketplace 限制](https://code.claude.com/docs/zh-TW/plugins/org.md#restrict-what-users-can-install)。

#### 允許的來源類型

下面每個項目顯示每個來源類型的一個允許清單項目及其接受的欄位。大多數類型完全符合；`hostPattern` 和 `pathPattern` 按 regex 符合，`github` 項目可以使用[所有者萬用字元](#owner-wildcards)。

| Source | Example entry | Fields |
| :- | :- | :- |
| `github` | `{ "source": "github", "repo": "acme-corp/plugins", "ref": "main", "path": "marketplace" }` | `repo` 必需；`ref` 是分支或標籤；`path` 是子目錄 |
| `git` | `{ "source": "git", "url": "https://gitlab.example.com/tools/plugins.git", "ref": "production" }` | `url` 必需；`ref` 和 `path` 如 `github` |
| `url` | `{ "source": "url", "url": "https://plugins.example.com/marketplace.json", "headers": { "Authorization": "Bearer ${TOKEN}" } }` | `url` 必需；`headers` 為已驗證存取新增 HTTP 標頭 |
| `file` | `{ "source": "file", "path": "/opt/acme-corp/plugins/marketplace.json" }` | `path` 必需，`marketplace.json` 檔案的絕對路徑 |
| `directory` | `{ "source": "directory", "path": "/opt/acme-corp/approved-marketplaces" }` | `path` 必需，包含 `.claude-plugin/marketplace.json` 的目錄的絕對路徑 |
| `hostPattern` | `{ "source": "hostPattern", "hostPattern": "^github\\.example\\.com$" }` | `hostPattern` 必需，在 marketplace 主機中任何地方符合的 regex；用 `^` 和 `$` 錨定以符合整個主機 |
| `pathPattern` | `{ "source": "pathPattern", "pathPattern": "^/opt/approved/" }` | `pathPattern` 必需，在 `file` 和 `directory` 來源的 `path` 中任何地方符合的 regex；以 `^` 開始以釘選前綴 |
| `skills-dir` | `{ "source": "skills-dir" }` | 無欄位 |

部分來源類型帶有超出表格的規則：

* **`url`**: URL marketplace 僅下載 `marketplace.json` 檔案，Claude Code 不會從該伺服器按相對路徑擷取 plugin 檔案，因此其 plugins 必須使用 [plugin 來源](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#plugin-sources)，而不是相對路徑，例如存檔 URL，可以在同一主機上。對於具有相對路徑的 plugins，請改用基於 Git 的 marketplace。請參閱[URL 型 marketplaces 中的相對路徑 plugins 失敗](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#plugins-with-relative-paths-fail-in-url-based-marketplaces)。
* **`hostPattern`**: 使用它允許內部 GitHub Enterprise 或 GitLab 伺服器上的每個 marketplace，而無需列出每個儲存庫。Claude Code 針對 `github.com` 符合 `github` 來源，從 `url` 來源取得主機名稱，並根據 [git URL](https://git-scm.com/docs/git-clone#_git_urls) 的形式從 `git` 來源取得它：

  * 具有方案的 URL，例如 `https://` 或 `ssh://`：URL 中的主機名稱。
  * 沒有方案的 SSH 位址，採用 git 的 `user@host:path` 形式，例如 `git@git.example.com:tools/plugins.git`：`@` 和 `:` 之間的主機，這是 git 連接到的主機。
  * 任何其他沒有方案的形式：沒有主機，因此沒有 `strictKnownMarketplaces` `hostPattern` 項目符合它。對於 `blockedMarketplaces` `hostPattern`，Claude Code 從更廣泛的形式集合中取得主機，因此封鎖清單項目仍可符合此類形式。在 v2.1.234 之前，`strictKnownMarketplaces` `hostPattern` 也符合 git 不視為 SSH 位址的某些形式。

  `file` 和 `directory` 來源沒有主機，永遠不符合 `hostPattern` 項目。
* **`pathPattern`**: 使用它允許檔案系統 marketplaces 與網路來源的 `hostPattern` 項目一起。`".*"` 允許每個本機路徑；較窄的模式（例如 `"^/opt/approved/"`）限制到目錄。
* **`skills-dir`**: 任何允許清單，即使是空的，也會停止 Claude Code 從 `~/.claude/skills/` 和專案的 `.claude/skills/` 載入 [`@skills-dir` plugins](https://code.claude.com/docs/zh-TW/plugins/loading#plugins-shared-through-a-repository)。若要繼續載入它們，請新增 `{ "source": "skills-dir" }` 項目，並保持 [`strictPluginOnlyCustomization`](#strictpluginonlycustomization) 未設定。該項目在此鍵和 `blockedMarketplaces` 之外沒有意義。

#### 所有者萬用字元

`github` 項目，其 `repo` 值為 `"<owner>/*"`，符合該 GitHub 所有者下的每個儲存庫。所有者萬用字元需要 Claude Code v2.1.223 或更新版本，僅在 `strictKnownMarketplaces` 和 `blockedMarketplaces` 中運作。在 `github` 來源出現的其他地方，例如 `extraKnownMarketplaces` 或 `/plugin marketplace add`，`repo` 值必須命名單個儲存庫。在 v2.1.223 之前，Claude Code 按字面比較項目，因此允許清單項目不符合任何儲存庫，封鎖清單項目不阻止任何內容；單儲存庫項目在每個版本上強制執行。

此項目允許 `acme-corp` 組織中的任何 marketplace 儲存庫：

```json managed-settings.json theme={null}
{
  "strictKnownMarketplaces": [
    { "source": "github", "repo": "acme-corp/*" }
  ]
}
```

只有整個儲存庫名稱位置可以是萬用字元。Claude Code 忽略項目（例如 `*`、`*/plugins` 或 `acme-corp/tools-*`）作為無效，因此它們不符合任何儲存庫。

兩個設定之間的符合規則不同：

| Rule | `strictKnownMarketplaces` | `blockedMarketplaces` |
| - | - | - |
| 符合來源拼寫 | 僅 `owner/repo` 形式。複製相同儲存庫的 git URL 不符合 | 任何拼寫，包括解析為相同 github.com 儲存庫的 git URL |
| 所有者大小寫 | 區分大小寫 | 不區分大小寫 |
| `ref` | 遵循精確項目規則：具有 `ref` 的項目僅符合具有該精確 ref 的來源，沒有項目的項目僅符合不指定 ref 的來源 | 沒有 `ref` 的項目阻止它符合的儲存庫的所有 refs |
| `path` | 比精確項目規則更寬鬆：具有 `path` 的項目需要該精確值，而沒有的項目符合儲存庫內的任何路徑 | 沒有 `path` 的項目阻止它符合的儲存庫的所有路徑 |

#### 精確符合

對於除所有者萬用字元 `github` 項目和 regex 符合的 `hostPattern` 和 `pathPattern` 項目之外的每個來源類型，Claude Code 僅在 marketplace 來源完全符合項目時允許使用者的新增。對於基於 git 的來源 `github` 和 `git`，精確符合包括可選欄位：

* `repo` 或 `url` 必須完全符合
* `ref` 欄位必須完全符合，或兩者都未定義
* `path` 欄位必須完全符合，或兩者都未定義

例如，Claude Code 將下面的每一對視為兩個不同的來源：

* `{ "source": "github", "repo": "acme-corp/plugins" }` 和 `{ "source": "github", "repo": "acme-corp/plugins", "ref": "main" }`
* `{ "source": "github", "repo": "acme-corp/plugins", "path": "marketplace" }` 和 `{ "source": "github", "repo": "acme-corp/plugins" }`

#### 僅允許官方 marketplace

若要僅允許官方 Anthropic marketplace，列出其儲存庫：

```json managed-settings.json theme={null}
{
  "strictKnownMarketplaces": [
    { "source": "github", "repo": "anthropics/claude-plugins-official" }
  ]
}
```

使用此項目，Claude Code 保持已註冊的官方 marketplace 可用，並在新機器上，在您第一次啟動互動式終端機工作階段時自動註冊 marketplace。自動註冊最常遺漏：

* 在機器的第一個互動式終端機工作階段之前執行的非互動式環境。
* Claude Code 僅透過 VS Code 擴充功能執行的機器。
* Claude Code 已在阻止 marketplace 的原則下執行互動式終端機工作階段的機器，例如空陣列鎖定。Claude Code 記錄被阻止的嘗試，不會在原則變更後重試。

在這些機器上，將 marketplace 新增到相同 `managed-settings.json` 中的 [`extraKnownMarketplaces`](#extraknownmarketplaces)，以便 Claude Code 自動註冊它，或執行 `claude plugin marketplace add anthropics/claude-plugins-official`。

#### 與 `extraKnownMarketplaces` 結合

兩個鍵執行不同的工作。此表比較它們：

| Aspect | `strictKnownMarketplaces` | `extraKnownMarketplaces` |
| - | - | - |
| 目的 | 組織原則強制執行 | 團隊便利 |
| 設定檔 | 僅受管設定 | 任何設定檔 |
| 行為 | 阻止非允許清單新增 | 註冊遺漏的 marketplaces |
| 何時強制執行 | 在網路和檔案系統操作之前 | 立即從使用者或受管設定；在儲存庫檔案的工作區信任對話框之後 |
| 可以被覆寫 | 否，最高優先順序 | 是，由更高優先順序的設定 |
| 來源格式 | 直接來源物件 | 具有巢狀 `source` 物件的命名 marketplace |

若要同時限制和預先為所有使用者註冊 marketplace，請在 `managed-settings.json` 中設定兩者：

```json managed-settings.json theme={null}
{
  "strictKnownMarketplaces": [
    { "source": "github", "repo": "acme-corp/plugins" }
  ],
  "extraKnownMarketplaces": {
    "acme-tools": {
      "source": { "source": "github", "repo": "acme-corp/plugins" }
    }
  }
}
```

僅設定 `strictKnownMarketplaces` 時，使用者仍可使用 `/plugin marketplace add` 自行新增允許的 marketplace。官方 Anthropic marketplace 是 Claude Code 自動註冊的唯一 marketplace，僅當允許清單允許時。[僅允許官方 marketplace](#allow-only-the-official-marketplace) 列出它遺漏的機器。

### `strictPluginOnlyCustomization`

阻止 skills、agents、hooks 和 MCP 伺服器來自使用者和專案來源，因此它們只能來自 plugins 或受管設定。將其與 [`strictKnownMarketplaces`](#strictknownmarketplaces) 結合以控制完整的自訂供應鏈：marketplace 允許清單控制使用者可以安裝哪些 plugins。

* **Scope**: [`Managed`](#scopes)
* **Type**: `true` 以鎖定所有四種自訂，或命名要鎖定的種類的陣列，來自 `"skills"`、`"agents"`、`"hooks"` 和 `"mcp"`
* **Default**: 未設定，因此沒有任何內容被鎖定

此範例鎖定 skills 和 hooks，並保持 agents 和 MCP 伺服器解鎖：

```json managed-settings.json theme={null}
{
  "strictPluginOnlyCustomization": ["skills", "hooks"]
}
```

如果您鎖定任何表面，Claude Code 也會停止載入 [skills 目錄 plugins](https://code.claude.com/docs/zh-TW/plugins/loading.md#skills-directory-plugins-blocked-by-managed-settings)，也就是使用者保存在 `~/.claude/skills/` 或 `.claude/skills/` 下的 plugin 資料夾。這些資料夾由使用者自行放置，而不是從 marketplace 安裝，因此 Claude Code 在此設定下將它們視為使用者自訂。

下面的四個子鍵項目列出每個表面阻止的內容以及仍然載入的內容。Claude Code 忽略它不識別的表面名稱，而不是使設定檔失敗，因此您可以在每個用戶端更新之前新增新的表面名稱。

### `strictPluginOnlyCustomization.skills`

鎖定 `skills` 表面。Claude Code 停止載入來自 `~/.claude/skills/` 和 `.claude/skills/` 的 skills、來自 `~/.claude/commands/` 和 `.claude/commands/` 的自訂命令、`--add-dir` 目錄下的 skills 和命令，以及從您的 claude.ai 帳戶同步的 skills。它繼續載入隨附的 skills、受管原則目錄中的 skills，以及來自 [skills 目錄 plugins](https://code.claude.com/docs/zh-TW/plugins/loading.md#skills-directory-plugins-blocked-by-managed-settings) 以外之 plugins 的 skills。

* **Scope**: [`Managed`](#scopes)
* **Type**: [`strictPluginOnlyCustomization`](#strictpluginonlycustomization) 陣列中的字串 `"skills"`
* **Default**: 未鎖定

```json managed-settings.json theme={null}
{
  "strictPluginOnlyCustomization": ["skills"]
}
```

### `strictPluginOnlyCustomization.agents`

鎖定 `agents` 表面。Claude Code 停止從 `~/.claude/agents/`、`.claude/agents/` 和 `--add-dir` 目錄載入 agents。它繼續載入內建 agents、受管原則目錄中的 agents，以及來自 [skills 目錄 plugins](https://code.claude.com/docs/zh-TW/plugins/loading.md#skills-directory-plugins-blocked-by-managed-settings) 以外之 plugins 的 agents。

* **Scope**: [`Managed`](#scopes)
* **Type**: [`strictPluginOnlyCustomization`](#strictpluginonlycustomization) 陣列中的字串 `"agents"`
* **Default**: 未鎖定

```json managed-settings.json theme={null}
{
  "strictPluginOnlyCustomization": ["agents"]
}
```

### `strictPluginOnlyCustomization.hooks`

鎖定 `hooks` 表面：

* **停止執行**：
  * 來自使用者、專案和本機 `settings.json` 的 hook
  * skills、自訂命令和 agents 中的 frontmatter hook，範圍為 [`skills`](#strictpluginonlycustomization-skills) 或 [`agents`](#strictpluginonlycustomization-agents) 鎖定會阻止的來源
* **繼續執行**：受管設定中的 hook，以及來自 [skills 目錄 plugins](https://code.claude.com/docs/zh-TW/plugins/loading.md#skills-directory-plugins-blocked-by-managed-settings) 以外之 plugins 的 hook

frontmatter hook 停止執行的 skills、自訂命令和 agents，在其自身的表面未鎖定時仍會載入。

在 frontmatter 中宣告 `hooks` 的個人或專案 [skill](https://code.claude.com/docs/zh-TW/skills.md#where-skills-live) 也會失去其 [`allowed-tools`](https://code.claude.com/docs/zh-TW/skills#pre-approve-tools-for-a-skill) 預先核准，因此您的使用者會在使用該欄位所列的工具時收到權限提示。當此類 skill 透過 [`context: fork`](https://code.claude.com/docs/zh-TW/skills#run-skills-in-a-subagent) 在 subagent 中執行時，它會保留預先核准。未宣告 `hooks` 的 skill 也會保留其預先核准。

* **Scope**: [`Managed`](#scopes)
* **Type**: [`strictPluginOnlyCustomization`](#strictpluginonlycustomization) 陣列中的字串 `"hooks"`
* **Default**: 未鎖定

```json managed-settings.json theme={null}
{
  "strictPluginOnlyCustomization": ["hooks"]
}
```

### `strictPluginOnlyCustomization.mcp`

鎖定 `mcp` 表面。Claude Code 停止從 `~/.claude.json` 和 `.mcp.json` 載入 MCP 伺服器。它繼續載入 [`managed-mcp.json`](https://code.claude.com/docs/zh-TW/managed-mcp) 伺服器、來自 [`managedMcpServers`](#managedmcpservers) 的伺服器，以及來自 [skills 目錄 plugins](https://code.claude.com/docs/zh-TW/plugins/loading.md#skills-directory-plugins-blocked-by-managed-settings) 以外之 plugins 的 MCP 伺服器。

* **Scope**: [`Managed`](#scopes)
* **Type**: [`strictPluginOnlyCustomization`](#strictpluginonlycustomization) 陣列中的字串 `"mcp"`
* **Default**: 未鎖定

```json managed-settings.json theme={null}
{
  "strictPluginOnlyCustomization": ["mcp"]
}
```

### `enabledPlugins`

按 `plugin-name@marketplace-name` 開啟或關閉個別 [plugins](https://code.claude.com/docs/zh-TW/plugins/overview.md)。沒有任何範圍項目的 plugin 會回退到其 [`defaultEnabled`](https://code.claude.com/docs/zh-TW/plugins/manifest-reference#fields) 值。當您使用 `/plugin` 或 `claude plugin enable` 啟用或禁用 plugin 時，Claude Code 會為您寫入此鍵。

* **Scope**: [`Any file`](#scopes)
* **Type**: 將 `plugin-name@marketplace-name` 對應到 Boolean 的物件
* **Default**: 未設定，因此每個 plugin 遵循其 `defaultEnabled` 值

此範例啟用來自 `team-tools` marketplace 的兩個 plugins，並禁用來自 `personal` 的一個：

```json settings.json theme={null}
{
  "enabledPlugins": {
    "code-formatter@team-tools": true,
    "deployment-tools@team-tools": true,
    "experimental-features@personal": false
  }
}
```

每個範圍服務不同的目的：

* **使用者設定**: 您的個人 plugin 偏好設定
* **專案設定**: 與儲存庫中的每個人共享的 plugins
* **本機設定**: 每台機器的覆寫，當 Claude Code 在那裡儲存設定時被 gitignored
* **受管設定**: 組織範圍的原則。設定為 `false` 的 plugin 在每個範圍都被阻止安裝，並從 marketplace 隱藏

專案設定優先於使用者設定，因此在 `~/.claude/settings.json` 中將 plugin 設定為 `false` 不會禁用專案的 `.claude/settings.json` 啟用的 plugin。若要在您的機器上選擇退出專案啟用的 plugin，請改為在 `.claude/settings.local.json` 中將其設定為 `false`。由受管設定強制啟用的 Plugins 無法以此方式禁用，因為受管設定覆寫本機設定。

在專案的 `.claude/settings.json` 中啟用來自外部來源（例如 GitHub 儲存庫或 npm 套件）的 plugin 不會為其他人安裝它。在載入 plugins 的每個路徑上，Claude Code 報告 plugin 未安裝，直到每個使用者[自行安裝它](https://code.claude.com/docs/zh-TW/plugins/org.md#require-plugins-per-repository)。

### `extraKnownMarketplaces`

按名稱註冊其他 plugin marketplaces，以便開啟儲存庫的人或受管設定到達的每個人都能獲得 marketplace，而無需自行新增。Claude Code 註冊它尚不知道的每個 marketplace。[`enabledPlugins`](#enabledplugins) 從它命名的 plugin 是否安裝取決於 plugin 的來源和哪個檔案啟用它；該項目有規則。

* **Scope**: [`Any file`](#scopes)。Claude Code 僅在您接受該資料夾的工作區信任對話框後，才接受儲存庫的 `.claude/settings.json` 或 `.claude/settings.local.json` 中的項目；在您未信任的資料夾中，包括 `-p` 執行，它會忽略它們而不顯示訊息。
* **Type**: 將 marketplace 名稱對應到具有 `source` 物件和可選 `autoUpdate` Boolean 的物件的物件
* **Default**: 未設定

此範例註冊 GitHub marketplace 和來自自託管 git URL 的 marketplace：

```json settings.json theme={null}
{
  "extraKnownMarketplaces": {
    "acme-tools": {
      "source": {
        "source": "github",
        "repo": "acme-corp/claude-plugins"
      }
    },
    "security-plugins": {
      "source": {
        "source": "git",
        "url": "https://git.example.com/security/plugins.git"
      }
    }
  }
}
```

[在您信任資料夾之前執行的內容](https://code.claude.com/docs/zh-TW/permissions.md#what-runs-before-you-trust-a-folder)將信任閘道與儲存庫可以提供的其他內容進行比較。您也可以將此鍵寫為 `additionalMarketplaces`；請參閱 [Marketplace 鍵別名](#marketplace-key-aliases)。

在 `source` 旁邊設定 `"autoUpdate": true` 以使 Claude Code 在啟動後在背景中重新整理該 marketplace 並更新其已安裝的 plugins。省略時，`claude-plugins-official` 和大多數其他官方 Anthropic marketplaces 預設為 `true`，第三方 marketplaces 預設為 `false`。請參閱[配置自動更新](https://code.claude.com/docs/zh-TW/plugins/install.md#keep-plugins-updated)。

當多個設定檔在相同名稱下定義 marketplace 項目時，Claude Code 使用來自[最高優先順序檔案](https://code.claude.com/docs/zh-TW/settings.md#settings-precedence)的項目。該項目取代較低優先順序的項目，不繼承其任何欄位，因此重新定義無法將一個檔案的 `source.headers` 認證與另一個檔案控制的 URL 結合。在 v2.1.228 之前，Claude Code 逐欄位合併相同名稱的項目，因此較高優先順序檔案中的項目可能繼承它未設定的欄位，包括另一個檔案的 `headers`。

#### Marketplace 來源類型

`source` 物件採用以下形式之一：

* **`github`**: GitHub 儲存庫，具有 `repo`
* **`git`**: 任何 git URL，具有 `url`
* **`url`**: 直接 URL 到 `marketplace.json` 檔案，具有 `url` 和可選 `headers` 和 `headersHelper` 用於已驗證存取。`headersHelper` 命名列印標頭的命令，其值太短暫而無法在 `headers` 中列出，並需要 Claude Code v2.1.238 或更新版本
* **`file`**: 到 `marketplace.json` 檔案的本機路徑，具有 `path`
* **`directory`**: 本機檔案系統路徑，具有 `path`。用於開發，或用於您的組織[部署到每台機器](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md#install-your-organizations-mods)的 marketplace。
* **`settings`**: 直接在設定檔中宣告的內嵌 marketplace，無需託管儲存庫，具有 `name` 和 `plugins`

`git` 來源類型適用於任何 git 託管服務，包括自託管 GitLab 和 Bitbucket。Claude Code 使用 `git clone` 在該機器上使用的相同驗證複製儲存庫：已配置的認證助手或 SSH 金鑰。提供者令牌（例如 `GITHUB_TOKEN`）透過讀取它的認證助手生效。請參閱[私人儲存庫](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md#grant-access-to-a-private-marketplace)以取得設定詳細資訊。

對於 `github` 和 `git` 來源，Claude Code 在複製 marketplace 儲存庫以新增或更新它時永遠不會下載 [Git LFS](https://git-lfs.com) 內容。LFS 追蹤的檔案簽出為指標檔案，新增或更新輸出報告有多少。

`source` 物件內的 `skipLfs` 欄位被接受且沒有效果。在 v2.1.274 之前，Claude Code 下載 LFS 內容，除非您設定 `"skipLfs": true`。

對於 `url` 來源，當 `headers` 中的認證過期且命令必須產生新的認證時，在 `source` 物件內設定 `headersHelper`。需要 Claude Code v2.1.238 或更新版本。如需命令必須列印的內容以及 Claude Code 執行它的位置，請參閱[編寫 headersHelper 命令](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md#write-the-headershelper-command)，以及 Claude Code 不執行它的情況，請參閱[何時 Claude Code 跳過 headersHelper 命令或丟棄其輸出](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md#when-claude-code-skips-a-headershelper-command-or-drops-its-output)。一旦您在 `https://` marketplace URL 上設定 `headersHelper`，Claude Code 在兩個點執行命令，重複使用一次執行的輸出長達 60 秒：

* 在該 marketplace 的 `marketplace.json` 的每次擷取之前，包括稍後的重新整理。Claude Code 使用該擷取傳送列印的標頭。
* 在 marketplace URL 來源上的每個 plugin 存檔下載之前，意味著相同的方案、主機和連接埠。Claude Code 使用該下載傳送輸出，沒有其他下載獲得標頭。

Claude Code 忽略在您使用 [`--add-dir`](https://code.claude.com/docs/zh-TW/permissions#what-runs-before-you-trust-a-folder) 新增的目錄的 `.claude/settings.json` 或 `.claude/settings.local.json` 中設定的任何 `headersHelper`，在 `url` 來源和內嵌 plugin 項目上，並僅傳送在該檔案中設定的固定 `headers`。[使用者如何接受 headersHelper 命令](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md#how-users-accept-a-headershelper-command)涵蓋其他設定檔。

`settings` 來源中列出的 Plugins 必須參考外部來源（例如 GitHub 或 npm），`name` 必須符合 marketplace 鍵。您仍然在 `enabledPlugins` 中分別啟用每個 plugin。此範例內嵌宣告一個 plugin：

```json settings.json theme={null}
{
  "extraKnownMarketplaces": {
    "team-tools": {
      "source": {
        "source": "settings",
        "name": "team-tools",
        "plugins": [
          {
            "name": "code-formatter",
            "source": {
              "source": "github",
              "repo": "acme-corp/code-formatter"
            }
          }
        ]
      }
    }
  }
}
```

`source: 'settings'` 下其自身 `source` 是 [`archive`](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference#archive-plugin-source) 的 plugin 項目可以為存檔下載設定 `headers`。如果您要放在 `headers` 中的值是短暫的，例如您的登錄機構應要求時鑄造的令牌，請改為設定 `headersHelper` 命令。項目可能同時設定兩者。兩個欄位都需要 Claude Code v2.1.238 或更新版本。

Claude Code 傳送項目的 `headers` 和命令列印的任何內容，與該 plugin 的存檔下載以及沒有其他下載。Claude Code 僅在使用者[自行安裝或更新該一個 plugin](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md#how-users-accept-a-headershelper-command) 時執行命令。三個進一步的規則取決於哪個檔案持有項目：

* **`strict`**: 與 marketplace 的 `marketplace.json` 中的項目不同，設定檔中的項目不需要 `"strict": false`，因為設定檔不帶有要內嵌的清單欄位。請參閱[嚴格模式](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#strict-mode)。
* **資料夾信任**: 對於專案的 `.claude/settings.json` 或 `.claude/settings.local.json` 中的項目，Claude Code 僅在使用者也[信任該資料夾](https://code.claude.com/docs/zh-TW/permissions.md#what-runs-before-you-trust-a-folder)後執行命令。
* **標頭篩選**: Claude Code 從專案的 `.claude/settings.json` 或 `.claude/settings.local.json` 中的項目丟棄[請求路由和用戶端身份標頭名稱](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md#when-claude-code-skips-a-headershelper-command-or-drops-its-output)，因為儲存庫可以提供這些檔案。Claude Code 將相同的篩選套用到目錄項目和 `--add-dir` 目錄的設定中的項目，並且不篩選您的使用者設定、`--settings` 檔案或受管設定中的項目。

#### Marketplace 鍵別名

在 Claude Code v2.1.232 或更新版本上，您可以將 `extraKnownMarketplaces` 寫為 `additionalMarketplaces`，將 `strictKnownMarketplaces` 寫為 `allowedMarketplaces`。Claude Code 按如下方式處理每個別名：

* 較早版本忽略別名，因此在較舊版本也讀取的檔案中保持規範拼寫，例如具有混合 Claude Code 版本的機隊的受管設定檔案。
* 在接受規範鍵的任何設定檔中，Claude Code 完全按照讀取規範鍵的方式讀取別名。
* Claude Code 在更新檔案時可能將 `additionalMarketplaces` 重寫為 `extraKnownMarketplaces`。
* 如果您在一個檔案中設定兩個拼寫，Claude Code 使用規範值並忽略別名。

### `pluginConfigs`

儲存您為 plugin 的 [`userConfig`](https://code.claude.com/docs/zh-TW/plugins/manifest-reference#user-configuration) 配置對話框提供的非敏感答案，以 plugin ID 為鍵。當您填寫對話框時，Claude Code 將此鍵寫入您的使用者設定，因此您無需手動編輯它。Claude Code 將敏感選項儲存在 macOS Keychain 中，當 Keychain 拒絕寫入時回退到 `~/.claude/.credentials.json`；在沒有支援的 keychain 的平台上，它將它們儲存在 `~/.claude/.credentials.json` 中。

* **Scope**: [`User or managed`](#scopes)
* **Type**: 將 plugin ID 對應到具有 `options` 欄位的物件的物件，將每個選項名稱對應到字串、數字、Boolean 或字串陣列，以及可選的 `mcpServers` 欄位，以相同形狀持有每伺服器使用者配置值
* **Default**: 未設定

此範例儲存來自 `acme-tools` 的 `deployer` plugin 的 `api_endpoint` 選項：

```json settings.json theme={null}
{
  "pluginConfigs": {
    "deployer@acme-tools": {
      "options": {
        "api_endpoint": "https://api.example.com"
      }
    }
  }
}
```

內建 plugins 在相同鍵下儲存其選項，帶有 `@builtin` 後綴。例如，控制 Claude Code 是否讀取 `AGENTS.md` 檔案的[**專案指示**](https://code.claude.com/docs/zh-TW/memory.md#choose-which-instruction-files-load)設定是 `pluginConfigs["cc-plugin-agents-md@builtin"].options.instructionFiles`。在 v2.1.285 之前，該 plugin 的 ID 是 `agents-md@builtin`。較新版本會讀取任一 ID 下的項目。

Claude Code 忽略專案和本機項目，因為它將這些值替換到 plugin hook、MCP 和 LSP 設定中，複製的儲存庫不得能夠提供它們。

### `prependPlugins`

列出受管 plugins，其 [mods](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md) 在使用者安裝的每個 mod 之前執行，按列出的順序。當您在受管設定中設定此鍵時，在清單中命名 `sec-default@builtin` 以保持內建守衛。在受管設定中，Claude Code 跳過其 plugin 不計為您組織的 id。請參閱[安裝您組織的 mods 並設定順序](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md#install-your-organizations-mods)以取得這些條件以及兩個排序鍵如何一起運作。

* **Scope**: [`User or managed`](#scopes)。Claude Code 從受管設定讀取鍵。它僅在沒有受管設定的機器上、在憑證不是 Team 或 Enterprise `/login` 的工作階段中，才從使用者設定讀取鍵。它忽略專案和本機設定以及 `--settings` 檔案中的鍵。
* **Type**: `plugin-name@marketplace-name` 字串的陣列
* **Default**: 未設定

```json managed-settings.json theme={null}
{
  "extraKnownMarketplaces": {
    "acme-tools": {
      "source": { "source": "directory", "path": "/opt/acme/claude-plugins" }
    }
  },
  "enabledPlugins": { "acme-guard@acme-tools": true },
  "prependPlugins": ["acme-guard@acme-tools", "sec-default@builtin"]
}
```

### `appendPlugins`

列出受管 plugins，其 [mods](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md) 在使用者安裝的每個 mod 之後執行，按列出的順序。在 `prependPlugins` 和 `appendPlugins` 中列出的 id 被前置。在受管設定中，Claude Code 跳過其 plugin 不[計為您組織的](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md#install-your-organizations-mods) id。

* **Scope**: [`User or managed`](#scopes)。Claude Code 從受管設定讀取鍵。它僅在沒有受管設定的機器上、在憑證不是 Team 或 Enterprise `/login` 的工作階段中，才從使用者設定讀取鍵。它忽略專案和本機設定以及 `--settings` 檔案中的鍵。
* **Type**: `plugin-name@marketplace-name` 字串的陣列
* **Default**: 未設定

```json managed-settings.json theme={null}
{
  "extraKnownMarketplaces": {
    "acme-tools": {
      "source": { "source": "directory", "path": "/opt/acme/claude-plugins" }
    }
  },
  "enabledPlugins": { "acme-audit@acme-tools": true },
  "appendPlugins": ["acme-audit@acme-tools"]
}
```

## MCP

控制 Claude Code 連接到哪些 MCP 伺服器，以及組織允許哪些伺服器。請參閱[使用 MCP 連接到外部工具](https://code.claude.com/docs/zh-TW/mcp.md)和[受管 MCP 設定](https://code.claude.com/docs/zh-TW/managed-mcp.md)。

### `allowAllClaudeAiMcps`

載入 [claude.ai 連接器](https://code.claude.com/docs/zh-TW/mcp.md#use-mcp-servers-from-claude-ai)，Claude Code 會在部署的 `managed-mcp.json` 旁邊自行擷取這些連接器。沒有此金鑰，`managed-mcp.json` 會獨佔控制 MCP 伺服器並抑制這些連接器。

* **範圍**：[`Managed`](#scopes)。使用者無法重新啟用獨佔控制所抑制的連接器。
* **類型**：布林值
  * `true`：Claude Code 會在部署的 `managed-mcp.json` 旁邊載入 claude.ai 連接器
  * `false`：部署的 `managed-mcp.json` 獨佔控制 MCP 伺服器並抑制 claude.ai 連接器 [Claude Code 自行擷取](https://code.claude.com/docs/zh-TW/mcp.md#how-connectors-reach-claude-code)
* **預設**：`false`，因此部署的 `managed-mcp.json` 會抑制 Claude Code 自行擷取的 claude.ai 連接器

```json managed-settings.json theme={null}
{
  "allowAllClaudeAiMcps": true
}
```

[`allowedMcpServers`](#allowedmcpservers) 和 [`deniedMcpServers`](#deniedmcpservers) 仍然適用於此金鑰載入的連接器。傳遞到[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)的連接器，其主機帶有 `managed-mcp.json`（例如自託管執行器），會保持被抑制。請參閱[允許 claude.ai 連接器與受管集合並存](https://code.claude.com/docs/zh-TW/managed-mcp.md#allow-claude-ai-connectors-alongside-the-managed-set)。

### `allowClaudeInChromeWithManagedMcp`

讓內建的 [Chrome 中的 Claude](https://code.claude.com/docs/zh-TW/chrome.md) 伺服器在部署的 `managed-mcp.json` 旁邊執行。沒有此金鑰，部署的 `managed-mcp.json` 會在終端工作階段中阻止 Chrome 中的 Claude。需要 Claude Code v2.1.282 或更新版本。

* **範圍**：[`Managed`](#scopes)，僅來自裝置自己的受管設定：MDM 部署的 plist 或 HKLM 登錄機碼，或系統 `managed-settings.json` 檔案。Claude Code 在伺服器受管設定、使用者可寫入的 HKCU 登錄和使用者或專案設定中忽略它。
* **類型**：布林值
  * `true`：內建的 Chrome 中的 Claude 伺服器可以在部署的 `managed-mcp.json` 旁邊執行
  * `false`：部署的 `managed-mcp.json` 會在終端工作階段中阻止 Chrome 中的 Claude
* **預設**：`false`，因此部署的 `managed-mcp.json` 會在終端工作階段中阻止 Chrome 中的 Claude

```json managed-settings.json theme={null}
{
  "allowClaudeInChromeWithManagedMcp": true
}
```

[`deniedMcpServers`](#deniedmcpservers) 中的 `claude-in-chrome` 條目仍然會在此金鑰開啟時阻止伺服器。請參閱[允許 Chrome 中的 Claude 與受管集合並存](https://code.claude.com/docs/zh-TW/managed-mcp.md#allow-claude-in-chrome-alongside-the-managed-set)。

### `allowedMcpServers`

允許清單列出人員可以新增的 MCP 伺服器。Claude Code 會阻止任何不符合條目的伺服器，無論在何處定義，包括外掛程式伺服器、使用 `--mcp-config` 傳遞的伺服器，以及來自 claude.ai 的伺服器。

內建伺服器（例如 Chrome 中的 Claude、Claude Code 在執行中的 [VS Code](https://code.claude.com/docs/zh-TW/vs-code.md#the-built-in-ide-mcp-server) 或 [JetBrains](https://code.claude.com/docs/zh-TW/jetbrains.md#the-built-in-ide-mcp-server) IDE 中連接的 `ide` 伺服器，以及 CLI 本身設定的伺服器）不受允許清單限制，拒絕清單仍然適用於它們。在 Claude Code v2.1.268 或更新版本上，[Claude Tag](https://code.claude.com/docs/zh-TW/claude-tag.md) 工作階段的 Slack 工具也不受允許清單限制，拒絕清單仍然適用於它們。同處理程序 `type: "sdk"` 伺服器不受兩個清單的限制；[啟動工作階段的應用程式](https://code.claude.com/docs/zh-TW/mcp.md#how-connectors-reach-claude-code)會註冊它們。

您的組織提供的伺服器也不受允許清單限制，拒絕清單仍然適用於它們。豁免涵蓋每個 [`managedMcpServers`](#managedmcpservers) 條目，以及任何其值[未在 `env` 以外使用 `${VAR}` 擴展](https://code.claude.com/docs/zh-TW/managed-mcp#how-allowlists-and-denylists-apply-to-the-managed-set)的 [`managed-mcp.json`](https://code.claude.com/docs/zh-TW/managed-mcp#exclusive-control-with-managed-mcp-json) 條目。請參閱[如何評估伺服器](https://code.claude.com/docs/zh-TW/managed-mcp.md#how-a-server-is-evaluated)以了解完整的檢查順序。在 v2.1.259 之前，來自 `managed-mcp.json` 的伺服器也必須符合。

* **範圍**：[`Any file`](#scopes)。來自每個檔案的條目會合併為一個允許清單，除非設定了 [`allowManagedMcpServersOnly`](#allowmanagedmcpserversonly)。在受管設定中部署它以強制執行。
* **類型**：物件陣列，每個物件恰好包含一個鍵。使用 `serverName`，這是一個僅限字母、數字、連字號和底線的字串；`serverCommand`，這是由命令及其引數組成的陣列，須完全相符；或 `serverUrl`，這是可使用 `*` 萬用字元的 URL 模式
* **預設**：未設定，因此允許每個伺服器；空陣列會阻止使用者新增的每個伺服器

此範例僅允許列出的 `npx` 命令啟動的 stdio 伺服器：

```json settings.json theme={null}
{
  "allowedMcpServers": [
    { "serverCommand": ["npx", "-y", "@modelcontextprotocol/server-filesystem"] }
  ]
}
```

[`deniedMcpServers`](#deniedmcpservers) 條目優先，因此同時在兩個清單上的伺服器會被阻止。一旦清單包含任何 `serverCommand` 條目，stdio 伺服器必須符合 `serverCommand` 條目，一旦它包含任何 `serverUrl` 條目，遠端伺服器必須符合 `serverUrl` 條目：`serverName` 相符不再允許該類伺服器。請參閱[使用允許清單和拒絕清單進行基於原則的控制](https://code.claude.com/docs/zh-TW/managed-mcp.md#policy-based-control-with-allowlists-and-denylists)。

### `allowManagedMcpServersOnly`

使受管允許清單成為唯一適用的清單。Claude Code 然後僅從受管設定讀取 [`allowedMcpServers`](#allowedmcpservers)，並忽略使用者、專案和本機設定中的允許清單；[`deniedMcpServers`](#deniedmcpservers) 仍然從每個設定範圍合併，因此使用者仍然可以為自己阻止伺服器。管理員設定它，以便使用者自己的設定無法擴大受管允許清單允許的內容。

* **範圍**：[`Managed`](#scopes)
* **類型**：布林值
  * `true`：Claude Code 僅從受管設定讀取 `allowedMcpServers`，並忽略使用者、專案和本機設定中的允許清單
  * `false`：來自每個設定範圍的允許清單合併
* **預設**：`false`，因此來自每個設定範圍的允許清單合併

此範例將允許清單鎖定到受管設定，並僅允許名為 `github` 的伺服器：

```json managed-settings.json theme={null}
{
  "allowManagedMcpServersOnly": true,
  "allowedMcpServers": [
    { "serverName": "github" }
  ]
}
```

使用者仍然可以新增自己的 MCP 伺服器；只有符合受管允許清單的伺服器才會載入。請參閱[將允許清單限制為僅受管設定](https://code.claude.com/docs/zh-TW/managed-mcp.md#restrict-the-allowlist-to-managed-settings-only)。

### `deniedMcpServers`

阻止特定的 MCP 伺服器。Claude Code 拒絕載入符合的伺服器，無論在何處定義，包括外掛程式伺服器、使用 `--mcp-config` 傳遞的伺服器、來自 `managed-mcp.json` 的伺服器、來自 [`managedMcpServers`](#managedmcpservers) 的伺服器，以及 [它自行擷取](https://code.claude.com/docs/zh-TW/mcp.md#how-connectors-reach-claude-code)的 claude.ai 連接器。同處理程序 `type: "sdk"` 伺服器不受限制；啟動工作階段的應用程式會註冊它們。

* **範圍**：[`Any file`](#scopes)。來自每個檔案的條目會合併為一個拒絕清單，[`allowManagedMcpServersOnly`](#allowmanagedmcpserversonly) 不會改變這一點。在受管設定中部署它以強制執行。
* **類型**：物件陣列，每個物件恰好有一個金鑰：`serverName`（字串，因此 claude.ai 連接器的顯示名稱（例如 `"claude.ai Slack"`）有效）；`serverCommand`（命令及其引數的陣列，完全相符）；或 `serverUrl`（具有 `*` 萬用字元的 URL 模式）
* **預設**：未設定，因此不會阻止任何伺服器；空陣列也不會阻止任何內容

```json settings.json theme={null}
{
  "deniedMcpServers": [
    { "serverName": "filesystem" }
  ]
}
```

拒絕清單優先於 [`allowedMcpServers`](#allowedmcpservers)，因此同時在兩個清單上的伺服器會被阻止。請參閱[使用允許清單和拒絕清單進行基於原則的控制](https://code.claude.com/docs/zh-TW/managed-mcp.md#policy-based-control-with-allowlists-and-denylists)。

### `disableClaudeAiConnectors`

關閉 [claude.ai MCP 連接器](https://code.claude.com/docs/zh-TW/mcp.md#use-mcp-servers-from-claude-ai) [Claude Code 自行擷取](https://code.claude.com/docs/zh-TW/mcp.md#how-connectors-reach-claude-code)，因此它既不擷取也不連接它們。任何設定檔案中的 `true` 都適用：簽入的專案 `.claude/settings.json` 可以選擇退出存放庫中的這些連接器，但專案層級的 `false` 無法覆蓋使用者或受管層級的 `true`。

* **範圍**：[`Any file`](#scopes)
* **類型**：布林值
  * `true`：Claude Code 既不擷取也不連接這些連接器
  * `false`：與未設定相同；Claude Code 會擷取您的連接器，除非另一個設定檔案或 `ENABLE_CLAUDEAI_MCP_SERVERS` 將其關閉
* **預設**：`false`，因此 Claude Code 會擷取您的連接器
* **每個工作階段的覆蓋**：[`ENABLE_CLAUDEAI_MCP_SERVERS`](https://code.claude.com/docs/zh-TW/env-vars) 設定為 `false` 會在一個工作階段中關閉連接器；無論兩者中哪一個將其關閉，另一個都無法將其重新開啟

```json settings.json theme={null}
{
  "disableClaudeAiConnectors": true
}
```

您使用 `--mcp-config` 明確傳遞的伺服器不受影響。若要阻止個別連接器而不是全部，請使用 [`deniedMcpServers`](#deniedmcpservers)。請參閱[禁用 claude.ai 連接器](https://code.claude.com/docs/zh-TW/mcp.md#disable-claude-ai-connectors)。

### `disabledMcpjsonServers`

拒絕專案 `.mcp.json` 檔案中定義的特定伺服器，以便 Claude Code 永遠不會連接它們或要求您批准它們。任何設定檔案中的拒絕都適用，包括簽入存放庫的專案 `.claude/settings.json`。

* **範圍**：[`Any file`](#scopes)
* **類型**：字串陣列，伺服器名稱如 `.mcp.json` 中所示
* **預設**：未設定

```json settings.json theme={null}
{
  "disabledMcpjsonServers": ["filesystem"]
}
```

當您在批准對話方塊中拒絕伺服器時，Claude Code 會將此金鑰寫入 `.claude/settings.local.json`。`claude mcp get <name>` 將被拒絕的伺服器顯示為 `✘ Rejected (see disabledMcpjsonServers in settings)`。拒絕優先於 [`enabledMcpjsonServers`](#enabledmcpjsonservers) 和 [`enableAllProjectMcpServers`](#enableallprojectmcpservers)。

### `enableAllProjectMcpServers`

批准專案 `.mcp.json` 檔案中定義的每個 MCP 伺服器，無需提示。當您在批准對話方塊中選擇批准所有伺服器時，Claude Code 會將此金鑰寫入 `.claude/settings.local.json`。

* **範圍**：[`Any file`](#scopes)。在您尚未接受信任對話方塊的資料夾中，Claude Code 從使用者設定、受管設定和 `--settings` 中遵守它，並在共用專案檔案中忽略它，無論在工作階段中還是對於 `claude mcp list` 和 `claude mcp get`；[專案伺服器批准和工作區信任](https://code.claude.com/docs/zh-TW/mcp.md#project-server-approvals-and-workspace-trust)說明何時未追蹤的 `.claude/settings.local.json` 也計算在內。
* **類型**：布林值
  * `true`：Claude Code 批准專案 `.mcp.json` 檔案中定義的每個 MCP 伺服器，無需提示
  * `false`：Claude Code 要求您批准每個伺服器。在受信任的資料夾中，較高優先順序檔案中的 `false` 會覆蓋較低優先順序檔案中的 `true`；在您尚未信任的資料夾中，任何受尊重檔案中的 `true` 就足夠了
* **預設**：未設定，因此 Claude Code 要求您批准每個伺服器

```json settings.json theme={null}
{
  "enableAllProjectMcpServers": true
}
```

[`disabledMcpjsonServers`](#disabledmcpjsonservers) 條目仍然會拒絕伺服器。

### `enabledMcpjsonServers`

批准專案 `.mcp.json` 檔案中定義的特定伺服器，以便 Claude Code 連接它們而無需詢問。當您在批准對話方塊中批准伺服器時，Claude Code 會將此金鑰寫入 `.claude/settings.local.json`。

* **範圍**：[`Any file`](#scopes)。在您尚未接受信任對話方塊的資料夾中，Claude Code 從使用者設定、受管設定和 `--settings` 中遵守它，並在共用專案檔案中忽略它，無論在工作階段中還是對於 `claude mcp list` 和 `claude mcp get`；[專案伺服器批准和工作區信任](https://code.claude.com/docs/zh-TW/mcp.md#project-server-approvals-and-workspace-trust)說明何時未追蹤的 `.claude/settings.local.json` 也計算在內。
* **類型**：字串陣列，伺服器名稱如 `.mcp.json` 中所示
* **預設**：未設定

此範例批准專案 `.mcp.json` 中的 `memory` 和 `github` 伺服器：

```json settings.json theme={null}
{
  "enabledMcpjsonServers": ["memory", "github"]
}
```

[`disabledMcpjsonServers`](#disabledmcpjsonservers) 條目仍然會拒絕伺服器。

### `managedMcpServers`

從受管設定為每個使用者提供遠端 MCP 伺服器。使用者保留他們自己新增的伺服器，無法編輯或移除您提供的伺服器。需要 Claude Code v2.1.259 或更新版本。

* **範圍**：[`Managed`](#scopes)。Claude Code 在使用者、專案和本機設定中以警告方式捨棄該金鑰，並且不在第三方部署上的 Claude Desktop 應用程式的 Code 標籤中或在應用程式的 Cowork 工作階段中讀取它，其中 Claude Desktop 會供應並鎖定這些工作階段的 MCP 伺服器本身。
* **類型**：以伺服器名稱為鍵的物件。每個條目都具有 `http` 或 `sse` 伺服器的 `.mcp.json` 形狀：必需的 `https://` `url`，以及可選的 `headers`、`oauth` 和其他 HTTP 和 SSE 選項。Claude Code 捨棄驗證失敗的條目，[條目可以包含的內容](https://code.claude.com/docs/zh-TW/managed-mcp.md#what-an-entry-can-contain)列出了條件
* **預設**：未設定，因此受管設定不提供伺服器

此範例提供一個名為 `search` 的 HTTP 伺服器：

```json managed-settings.json theme={null}
{
  "managedMcpServers": {
    "search": {
      "type": "http",
      "url": "https://search.example.com/mcp"
    }
  }
}
```

有關優先順序、提供的伺服器如何與 `managed-mcp.json` 和允許和拒絕清單結合，以及使用者看到的內容，請參閱[通過受管設定提供伺服器](https://code.claude.com/docs/zh-TW/managed-mcp.md#provide-servers-through-managed-settings)。

## Agent、工作階段與 worktree

設定預設代理程式、控制隊友和跨工作階段訊息，以及設定 worktrees。請參閱 [Subagents](https://code.claude.com/docs/zh-TW/sub-agents.md) 和 [Worktrees](https://code.claude.com/docs/zh-TW/worktrees.md)。

### `agent`

將主執行緒作為具名 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#invoke-subagents-explicitly) 執行，以便 Claude Code 將該 subagent 的系統提示、工具限制和模型套用到您的工作階段。相同的金鑰會為您從 `claude agents` 分派的工作階段設定預設代理程式。

* **Scope**: [`Any file`](#scopes)
* **Type**: string，內建或自訂代理程式的名稱
* **Default**: 未設定，因此主執行緒以 Claude Code 的預設代理程式執行
* **Per-session overrides**: `--agent` 對一個工作階段優先於此金鑰

```json settings.json theme={null}
{
  "agent": "code-reviewer"
}
```

外掛程式自己的 `settings.json` 也可以提供此金鑰；請參閱 [Ship default settings with your plugin](https://code.claude.com/docs/zh-TW/plugins/components.md#default-settings)。

### `crossSessionInbound`

選擇此工作階段如何處理 [來自您其他 Claude Code 工作階段的訊息](https://code.claude.com/docs/zh-TW/cross-session-messaging.md#control-inbound-messages)。當沒有值適用時，Claude Code 會根據兩個工作階段的權限模式類別逐個訊息決定。需要 Claude Code v2.1.224 或更新版本。

* **Scope**: [`Any file`](#scopes)。專案或本機值僅在其比受管設定、`--settings` 旗標或使用者設定提供的值更嚴格時才適用。
* **Type**: string，其中之一：
  * `"accept"`: Claude Code 將訊息傳遞給 Claude
  * `"hold"`: Claude Code 顯示訊息的通知而不傳遞它
  * `"refuse"`: Claude Code 丟棄訊息
* **Default**: 未設定，因此 Claude Code 逐個訊息決定

```json settings.json theme={null}
{
  "crossSessionInbound": "hold"
}
```

Claude Code 首先讀取受管設定，然後是 `--settings` 旗標，然後是使用者設定，並套用找到的第一個值。`refuse` 比 `hold` 更嚴格，`hold` 比 `accept` 更嚴格。當沒有受信任的來源設定值時，專案或本機 `hold` 或 `refuse` 仍然適用，取代逐個訊息的預設值。在具有跨工作階段訊息的工作階段中，此金鑰在 `/config` 中顯示為 **Messages from your other sessions**，它將其寫入使用者設定；該列需要 Claude Code v2.1.232 或更新版本，當 `--settings` 旗標或受管設定設定金鑰時，Claude Code 會隱藏它。

Claude Code [warns](https://code.claude.com/docs/zh-TW/errors.md#crosssessioninbound-must-be-one-of-accept-hold-refuse) 當您設定它無法識別的值時。當該值存在於使用者、專案、本機或 `--settings` 檔案中時，Claude Code 會保留入站訊息，即使優先的來源設定 `accept` 也是如此。另一個來源設定的 `refuse` 仍然適用。修復或移除該值以清除保留。

當無法識別的值在 [managed settings](https://code.claude.com/docs/zh-TW/managed-settings.md) 中時，Claude Code 改為將其視為 `refuse`，直到管理員修復它。在 v2.1.248 之前，Claude Code 會忽略無法識別的值而不發出警告。

### `disableAgentView`

關閉 [background agents and agent view](https://code.claude.com/docs/zh-TW/agent-view.md)：`claude agents`、`--bg`、`/background` 和隨需主管。在 [managed settings](https://code.claude.com/docs/zh-TW/managed-settings.md) 中設定它以對組織強制執行。

* **Scope**: [`Any file`](#scopes)
* **Type**: Boolean
  * `true`: Claude Code 關閉 `claude agents`、`--bg`、`/background` 和隨需主管
  * `false`: agent view 可用
* **Default**: 未設定，因此 agent view 可用
* **Per-session overrides**: [`CLAUDE_CODE_DISABLE_AGENT_VIEW`](https://code.claude.com/docs/zh-TW/env-vars) 對一個工作階段關閉 agent view；無論哪一個關閉它，另一個都無法將其重新開啟

```json settings.json theme={null}
{
  "disableAgentView": true
}
```

### `isolatePeerMachines`

在 Claude 的 `SendMessage` 到達此機器之外的您的工作階段之前，需要您的明確批准；請參閱 [Require approval for cross-machine messages](https://code.claude.com/docs/zh-TW/cross-session-messaging.md#require-approval-for-cross-machine-messages)。即使在 [`bypassPermissions` mode](https://code.claude.com/docs/zh-TW/permission-modes#skip-all-checks-with-bypasspermissions-mode) 中，批准提示也會出現。

* **Scope**: [`Any file`](#scopes)。來自任何範圍的 `true` 都適用，因此簽入的專案檔案可以開啟要求但不能關閉。
* **Type**: Boolean
  * `true`: Claude Code 在 Claude 的 `SendMessage` 到達此機器之外的您的工作階段之前要求您的批准
  * `false`: 跨機器訊息不提示
* **Default**: 未設定，因此跨機器訊息不提示

```json settings.json theme={null}
{
  "isolatePeerMachines": true
}
```

跨機器 `SendMessage` 批准需要 Claude Code v2.1.224 或更新版本。

### `processWrapper`

在 macOS 和 Linux 上，在 [Claude Code 啟動的背景程序](https://code.claude.com/docs/zh-TW/corporate-launcher.md#what-the-launcher-covers) 前面放置公司啟動器命令。Claude Code 使用其自己的命令列附加執行啟動器，因此啟動器必須執行到 Claude Code；請參閱 [Run Claude Code behind a corporate launcher](https://code.claude.com/docs/zh-TW/corporate-launcher.md) 以了解啟動器合約。需要 Claude Code v2.1.210 或更新版本。

* **Scope**: [`User or managed`](#scopes)
* **Type**: string，啟動器命令作為 argv 前綴，例如具有選擇性引數的絕對路徑
* **Default**: 未設定，因此背景程序啟動時不包裝
* **Per-session overrides**: [`CLAUDE_CODE_PROCESS_WRAPPER`](https://code.claude.com/docs/zh-TW/env-vars) 對一個工作階段優先於此金鑰

```json settings.json theme={null}
{
  "processWrapper": "/opt/corp/launcher --profile claude"
}
```

Claude Code 在 Windows 上忽略啟動器並啟動每個程序時不包裝。需要 Claude Code v2.1.210 或更新版本。

### `teammateMode`

選擇 Claude Code 顯示 [agent team](https://code.claude.com/docs/zh-TW/agent-teams.md) 隊友的位置：在您的主終端窗格內，或在您的終端支援時在分割窗格中。請參閱 [Choose a display mode](https://code.claude.com/docs/zh-TW/agent-teams.md#choose-a-display-mode)。

* **Scope**: [`Any file`](#scopes)。Claude Code 也會讀取舊版本在 `~/.claude.json` 中留下的值。
* **Type**: string，其中之一：
  * `"in-process"`: 隊友在您的主終端窗格內執行
  * `"auto"`: 當您在 tmux 內執行時分割窗格，或在 iTerm2 內執行且 `it2` 在您的 `PATH` 上或安裝了 tmux；否則為 in-process
  * `"tmux"`: 使用 tmux 或 iTerm2 分割窗格，從您的終端偵測
  * `"iterm2"`: iTerm2 原生分割窗格透過 `it2` CLI
* **Default**: `"in-process"`
* **Per-session overrides**: `--teammate-mode` 對一個工作階段優先於此金鑰

```json settings.json theme={null}
{
  "teammateMode": "auto"
}
```

### `worktree`

設定 Claude Code 如何為 `--worktree`、`EnterWorktree` 工具和隔離的 subagents 和背景工作階段建立和管理 [git worktrees](https://code.claude.com/docs/zh-TW/worktrees.md)。

* **Scope**: [`Any file`](#scopes)
* **Type**: object with `baseRef`, `symlinkDirectories`, `sparsePaths`, and `bgIsolation`
* **Default**: 未設定

此範例從您目前的 `HEAD` 分支新的 worktrees，並將 `node_modules` 符號連結到每一個：

```json settings.json theme={null}
{
  "worktree": {
    "baseRef": "head",
    "symlinkDirectories": ["node_modules"]
  }
}
```

若要將 gitignored 檔案（如 `.env`）複製到新的 worktrees，請改為在專案根目錄中新增 [`.worktreeinclude` 檔案](https://code.claude.com/docs/zh-TW/worktrees#copy-gitignored-files-into-worktrees)，而不是設定。

### `worktree.baseRef`

選擇新的 worktrees 從哪個 ref 分支。`"fresh"` 從 `origin/<default-branch>` 分支以獲得與遠端相符的乾淨樹；`"head"` 從您目前的本機 `HEAD` 分支，因此未推送的提交和功能分支狀態存在於 worktree 中。

* **Scope**: [`Any file`](#scopes)
* **Type**: string，其中之一：
  * `"fresh"`: 新的 worktrees 從 `origin/<default-branch>` 分支
  * `"head"`: 新的 worktrees 從您目前的本機 `HEAD` 分支，包括未推送的提交
* **Default**: `"fresh"`

```json settings.json theme={null}
{
  "worktree": {
    "baseRef": "head"
  }
}
```

在連結的 worktree 內，`"head"` 解析為該 worktree 的 `HEAD`，而不是主簽出的。

### `worktree.symlinkDirectories`

將目錄從主儲存庫符號連結到每個 worktree，以便您不會在磁碟上複製大型目錄。

* **Scope**: [`Any file`](#scopes)
* **Type**: array of strings，相對於儲存庫根目錄的目錄路徑
* **Default**: 未設定，因此 Claude Code 不符號連結任何目錄

此範例將 `node_modules` 和 `.cache` 從主儲存庫符號連結到每個新的 worktree：

```json settings.json theme={null}
{
  "worktree": {
    "symlinkDirectories": ["node_modules", ".cache"]
  }
}
```

### `worktree.sparsePaths`

透過 git sparse-checkout 在每個 worktree 中僅簽出列出的目錄。Claude Code 僅將這些目錄加上根層級檔案寫入磁碟，在大型 monorepos 中速度更快；請參閱 [Check out only the directories you need](https://code.claude.com/docs/zh-TW/large-codebases.md#check-out-only-the-directories-you-need)。

* **Scope**: [`Any file`](#scopes)
* **Type**: array of strings，相對於儲存庫根目錄的目錄路徑
* **Default**: 未設定，因此每個 worktree 簽出整個樹

請在清單中包含 `.claude`，讓每個 worktree 也具有儲存庫的 `.claude/settings.json` 和 `.claude/rules/`。此範例在每個 worktree 中僅簽出 `.claude`、`packages/my-app` 和 `shared/utils`，加上根層級檔案：

```json settings.json theme={null}
{
  "worktree": {
    "sparsePaths": [".claude", "packages/my-app", "shared/utils"]
  }
}
```

當稀疏 worktree 存在時，git 在儲存庫的共用 `.git/config` 中啟用 `extensions.worktreeConfig`。

### `worktree.bgIsolation`

選擇 [background sessions](https://code.claude.com/docs/zh-TW/agent-view.md#how-file-edits-are-isolated) 如何隔離其檔案編輯。如果您使用 `←` 或 `/background` 將工作階段移至背景，無論此設定鍵如何設定，該工作階段都會就地編輯檔案。使用 `"worktree"`，Claude Code 會阻止主簽出中的 `Edit` 和 `Write`，直到工作階段呼叫 `EnterWorktree`；使用 `"none"`，背景工作會直接編輯工作副本。對於 git worktrees 不實用的儲存庫，設定 `"none"`。

* **Scope**: [`Any file`](#scopes)
* **Type**: string，其中之一：
  * `"worktree"`: Claude Code 會阻止主簽出中的 `Edit` 和 `Write`，直到工作階段呼叫 `EnterWorktree`
  * `"none"`: 背景工作會直接編輯工作副本
* **Default**: `"worktree"`

```json settings.json theme={null}
{
  "worktree": {
    "bgIsolation": "none"
  }
}
```

在 git 儲存庫外，失敗的 [`WorktreeCreate` hook](https://code.claude.com/docs/zh-TW/worktrees#non-git-version-control) 會解除阻止，以便工作階段可以就地編輯工作目錄。

### `worktree.location`

選擇遠端機器上 [Desktop SSH 工作階段](https://code.claude.com/docs/zh-TW/desktop.md#choose-where-ssh-session-worktrees-go) 建立其 worktrees 的資料夾，以取代 `<project-root>/.claude/worktrees/`。只有桌面應用程式會讀取此設定鍵：`--worktree`、`EnterWorktree` 工具、隔離的 subagents 和背景工作階段都會忽略它。需要 Claude Desktop v1.44121.0 或更新版本。

* **Scope**: [`User`](#scopes)，位於遠端機器上的 `~/.claude/settings.json` 中
* **Type**: string，絕對路徑或以 `~/` 開頭的路徑
* **Default**: 未設定，因此 worktrees 會放在專案內

此範例將資料夾設定為 `~/worktrees`：

```json settings.json theme={null}
{
  "worktree": {
    "location": "~/worktrees"
  }
}
```

在 Desktop 中於 SSH 連線上設定的 **Worktree folder** 優先於此設定鍵。如果您的組織限制工作階段可使用的資料夾，Desktop 會將 worktrees 保留在專案內。

## 遠端、桌面與通知

設定遠端控制、雲端環境、桌面應用程式，以及 Claude Code 在需要您時傳送的通知。請參閱[遠端控制](https://code.claude.com/docs/zh-TW/remote-control.md)。

### `agentPushNotifEnabled`

允許 Claude 在決定值得傳送時，向您的手機傳送推播通知，例如當長時間任務完成時。Claude 可以在 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 連線時傳送通知。在 `/config` 中顯示為**Claude 決定時推播**。當您在那裡變更此設定時，Claude Code 也會將該值儲存到您的帳戶。

* **範圍**：[`任何檔案`](#scopes)。Claude Code 也會讀取舊版本在 `~/.claude.json` 中留下的值。
* **類型**：布林值
  * `true`：Claude 可以在決定值得傳送時，向您的手機傳送推播通知
  * `false`：Claude 不傳送這些通知
* **預設**：`false`

```json settings.json theme={null}
{
  "agentPushNotifEnabled": true
}
```

如果您在 [`claude remote-control`](https://code.claude.com/docs/zh-TW/remote-control#start-a-remote-control-session) 伺服器下執行工作階段，這些工作階段會遵循儲存在您帳戶中的值，而非此金鑰。若要變更該值，請在終端機中的 Claude Code 工作階段執行 `/config`，並將**Claude 決定時推播**開啟或關閉。如果切換開關已顯示您想要的值，請先將其變更再改回，讓 Claude Code 將該值儲存到您的帳戶。

請參閱[行動推播通知](https://code.claude.com/docs/zh-TW/remote-control.md#mobile-push-notifications)。

### `awaySummaryEnabled`

當您在離開終端機幾分鐘後返回時，顯示一行工作階段摘要。將其設定為 `false`，或在 `/config` 中關閉**工作階段摘要**，以停止摘要。

* **範圍**：[`任何檔案`](#scopes)
* **類型**：布林值
  * `true`：當您在離開幾分鐘後返回時，您會看到一行工作階段摘要
  * `false`：Claude Code 不顯示摘要
* **預設**：未設定，因此摘要已開啟
* **每個工作階段的覆寫**：[`CLAUDE_CODE_ENABLE_AWAY_SUMMARY`](https://code.claude.com/docs/zh-TW/env-vars) 在一個工作階段中優先於此金鑰，無論哪個方向

```json settings.json theme={null}
{
  "awaySummaryEnabled": false
}
```

Claude Code 在非互動模式中永遠不會顯示摘要。

### `disableArtifact`

> [!WARNING]
>
> 已棄用，已由 [`enableArtifact`](#enableartifact) 取代。Claude Code 仍然將 `disableArtifact: true` 視為等同於 `enableArtifact: false`，並忽略 `disableArtifact: false`。

改用 [`enableArtifact`](#enableartifact) 來關閉 [Artifact](https://code.claude.com/docs/zh-TW/artifacts.md) 工具，該工具將工作階段輸出發佈為 claude.ai 上的私人網頁。當您在 `/config` 中關閉 **Artifacts** 列時，Claude Code 會將 `enableArtifact` 寫入您的使用者設定，並清除此金鑰。

* **範圍**：[`任何檔案`](#scopes)
* **類型**：布林值
  * `true`：Claude Code 為該檔案適用的每個工作階段關閉 Artifact 工具，且沒有其他檔案將其重新開啟
  * `false`：忽略；若要保持工具開啟，請移除該金鑰
* **預設**：未設定，因此工具遵循您帳戶的[可用性](https://code.claude.com/docs/zh-TW/artifacts.md#availability)
* **每個工作階段的覆寫**：[`CLAUDE_CODE_DISABLE_ARTIFACT`](https://code.claude.com/docs/zh-TW/env-vars) 設定為 `1` 會為一個工作階段關閉工具

```json settings.json theme={null}
{
  "disableArtifact": true
}
```

[停用 artifacts](https://code.claude.com/docs/zh-TW/artifacts.md#disable-artifacts) 列出關閉工具的每一種方式。

### `disableDeepLinkRegistration`

停止 Claude Code 向作業系統註冊 `claude-cli://` 協定處理程式。[深層連結](https://code.claude.com/docs/zh-TW/deep-links.md)讓外部工具使用預先填入的提示詞開啟 Claude Code 工作階段。在協定處理程式註冊受限或單獨管理的環境中設定此項。

* **範圍**：[`任何檔案`](#scopes)
* **類型**：字串 `"disable"`
* **預設**：未設定，因此 Claude Code 會註冊處理程式

```json settings.json theme={null}
{
  "disableDeepLinkRegistration": "disable"
}
```

### `disableDesktopLocalSessions`

在[桌面應用程式](https://code.claude.com/docs/zh-TW/desktop.md#local-sessions-on-managed-devices)中關閉在裝置上執行的 Code 工作階段，適用於開發人員應該透過 SSH 在遠端機器上工作的部署。將此金鑰設定為 `true` 時，使用者會在 Code 標籤中看到以下情況：

* **環境選擇器**：使用者電腦的項目呈灰色且無法選擇，工具提示顯示 **Disabled by your organization**。在 Windows 上，WSL 項目以相同方式呈灰色，儘管 WSL 工作階段是否在受管理裝置上執行[由另外管理](https://code.claude.com/docs/zh-TW/admin-setup.md#wsl-sessions-in-claude-code-desktop)。
* **新工作階段**：預設為第一個 [SSH 連線](https://code.claude.com/docs/zh-TW/desktop.md#ssh-sessions)（如果已設定）
* **裝置上的工作階段**：應用程式拒絕在裝置上啟動或繼續工作階段，包括回到同一機器的 SSH 連線
* **到其他主機的 SSH 工作階段和雲端工作階段**：不受影響

桌面應用程式讀取此金鑰；終端機 CLI 忽略它。需要 Claude Desktop v1.37937.0 或更新版本。

* **範圍**：[`受管理`](#scopes)。預設情況下，桌面應用程式會從[單一受管理來源](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)讀取此金鑰。
* **類型**：布林值；只有 JSON 布林值 `true` 才會生效
  * `true`：桌面應用程式不提供裝置上的 Code 工作階段；現有本機工作階段保留在列表中但無法繼續
  * `false`：本機工作階段保持可用
* **預設**：未設定，因此本機工作階段可用

```json managed-settings.json theme={null}
{
  "disableDesktopLocalSessions": true
}
```

桌面應用程式忽略任何其他值，非布林值的值（例如字串 `"true"` 或 `1`）也會記錄警告。將其與 [`sshConfigs`](#sshconfigs) 配對，以便使用者登陸工作連線，並與 [`sshHostAllowlist`](#sshhostallowlist) 配對以限制他們可以到達的主機。請參閱[受管理裝置上的本機工作階段](https://code.claude.com/docs/zh-TW/desktop.md#local-sessions-on-managed-devices)。

Claude Desktop 為 Code 工作階段提供源自您桌面設定的原則，例如第三方部署中的出口允許清單、檔案系統沙箱和 MCP 限制。每當存在[管理員來源](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)時，Claude Code 會忽略這些父設定：伺服器管理的設定、MDM 或作業系統層級原則，或受管理設定檔。在之前沒有任何設定的裝置上透過其中一個部署此金鑰（如在第三方部署中），因此會停止套用桌面衍生的原則。[讓嵌入主機新增原則](https://code.claude.com/docs/zh-TW/managed-settings.md#let-an-embedding-host-add-policy)涵蓋何時父設定仍可合併；這適用於您以這種方式部署的任何金鑰，不僅限於此金鑰。

### `disableRemoteControl`

關閉[遠端控制](https://code.claude.com/docs/zh-TW/remote-control.md)：Claude Code 隨後拒絕 `claude remote-control`、`--remote-control` 旗標、自動啟動和工作階段內切換，並報告您的組織原則已停用它。將其放在[受管理設定](https://code.claude.com/docs/zh-TW/managed-settings.md)中以進行每個裝置的 MDM 強制執行。

* **範圍**：[`任何檔案`](#scopes)
* **類型**：布林值
  * `true`：Claude Code 拒絕 `claude remote-control`、`--remote-control` 旗標、自動啟動和工作階段內切換
  * `false`：遠端控制保持可用
* **預設**：`false`

```json settings.json theme={null}
{
  "disableRemoteControl": true
}
```

### `enableArtifact`

關閉 [Artifact](https://code.claude.com/docs/zh-TW/artifacts.md) 工具，該工具將工作階段輸出發佈為 claude.ai 上的私人網頁。當您在 `/config` 中關閉 **Artifacts** 列時，Claude Code 會將此金鑰寫入您的使用者設定，因此您通常不會手動編輯它。

* **範圍**：[`任何檔案`](#scopes)。每個檔案都可以關閉工具，但沒有任何檔案可以將其重新開啟。
* **類型**：布林值
  * `false`：Claude Code 為該檔案適用的每個工作階段關閉 Artifact 工具
  * `true`：與保留金鑰未設定相同，因為它永遠不會覆寫來自另一個檔案的 `false`、[`CLAUDE_CODE_DISABLE_ARTIFACT`](https://code.claude.com/docs/zh-TW/env-vars) 或您的組織[管理員設定](https://code.claude.com/docs/zh-TW/artifacts.md#manage-artifacts-for-your-organization)
* **預設**：未設定，因此工具遵循您帳戶的[可用性](https://code.claude.com/docs/zh-TW/artifacts.md#availability)

```json settings.json theme={null}
{
  "enableArtifact": false
}
```

當您自己的使用者設定以外的來源保持工具關閉時，Claude Code 會在 `/config` 中隱藏 **Artifacts** 列，因為在那裡開啟它不會改變任何事情。[停用 artifacts](https://code.claude.com/docs/zh-TW/artifacts.md#disable-artifacts) 列出關閉工具的每一種方式。

### `inputNeededNotifEnabled`

當權限提示或問題等待您的輸入時，在您的手機上獲得推播通知。Claude Code 只在[遠端控制](https://code.claude.com/docs/zh-TW/remote-control.md)連線時傳送這些通知。在 `/config` 中顯示為**需要操作時推播**。

* **範圍**：[`任何檔案`](#scopes)。Claude Code 也會讀取舊版本在 `~/.claude.json` 中留下的值。
* **類型**：布林值
  * `true`：當權限提示或問題等待時，您會在手機上獲得推播通知，而遠端控制已連線
  * `false`：Claude Code 不傳送此類通知
* **預設**：`false`

```json settings.json theme={null}
{
  "inputNeededNotifEnabled": true
}
```

請參閱[行動推播通知](https://code.claude.com/docs/zh-TW/remote-control.md#mobile-push-notifications)。

### `preferredNotifChannel`

選擇 Claude Code 在任務完成或權限提示等待時如何通知您。[mod 的通知](https://code.claude.com/docs/zh-TW/plugins/mods/api.md#show-something-without-starting-a-turn)也使用相同的設定。在 `/config` 中顯示為**本機通知**。

* **範圍**：[`任何檔案`](#scopes)。Claude Code 也會讀取舊版本在 `~/.claude.json` 中留下的值。
* **類型**：字串，其中之一：
  * `"auto"`：Claude Code 在 iTerm2、Ghostty 和 Kitty 中傳送桌面通知，在 Terminal.app 中只有在其可聽鈴聲關閉時才響鈴，在其他地方不執行任何操作
  * `"terminal_bell"`：Claude Code 在任何終端機中響鈴字元
  * `"iterm2"`：Claude Code 傳送 iTerm2 桌面通知
  * `"iterm2_with_bell"`：Claude Code 傳送 iTerm2 桌面通知並響鈴
  * `"kitty"`：Claude Code 傳送 Kitty 桌面通知
  * `"ghostty"`：Claude Code 傳送 Ghostty 桌面通知
  * `"notifications_disabled"`：Claude Code 不傳送通知
* **預設**：`"auto"`

```json settings.json theme={null}
{
  "preferredNotifChannel": "terminal_bell"
}
```

使用 `"auto"` 時，Claude Code 在 iTerm2、Ghostty 和 Kitty 中傳送桌面通知。在 Terminal.app 中，只有當您已關閉 Terminal 的可聽鈴聲時，它才會響鈴字元，在其他終端機中不執行任何操作。設定 `"terminal_bell"` 以在任何終端機中響鈴字元。請參閱[獲得終端機鈴聲或通知](https://code.claude.com/docs/zh-TW/terminal-config.md#get-a-terminal-bell-or-notification)。

### `remote.defaultEnvironmentId`

為您從 CLI 建立的雲端工作階段（例如使用 `claude --cloud`）選擇預設[雲端環境](https://code.claude.com/docs/zh-TW/cloud-environments.md)。當您使用 [`/remote-env`](https://code.claude.com/docs/zh-TW/cloud-environments#select-an-environment-from-the-cli) 選擇環境時，Claude Code 會將此金鑰寫入您的使用者設定。

* **範圍**：[`任何檔案`](#scopes)。對於自託管環境 ID，僅限使用者或受管理設定，或 `--settings` 旗標。
* **類型**：字串，環境 ID，例如 `env_...` 或 `ccpool_...`
* **預設**：未設定，因此當您的清單中有 Anthropic 託管環境時 Claude Code 會使用它，否則使用清單中不是[遠端控制橋接環境](https://code.claude.com/docs/zh-TW/cloud-environments.md#the-default-environment)的第一個環境，或當每個環境都是橋接環境時使用第一個環境
* **每個工作階段的覆寫**：`--environment` 優先於此金鑰，用於它建立的一個雲端工作階段

```json settings.json theme={null}
{
  "remote": {
    "defaultEnvironmentId": "env_0123abcd"
  }
}
```

Anthropic 託管環境 ID（以 `env_` 開頭）遵循標準設定優先順序，因此儲存庫的專案設定中的值會覆寫您的使用者層級選擇。[自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments) ID（以 `ccpool_` 開頭）只能從使用者設定、受管理設定和 `--settings` 旗標中獲得；Claude Code 忽略儲存庫的專案或本機設定中的一個，`/remote-env` 顯示它忽略了哪個值，因此簽入的檔案無法將工作階段引導到您未選擇的自託管環境。

### `remoteControlAtStartup`

當每個互動工作階段啟動時自動連線[遠端控制](https://code.claude.com/docs/zh-TW/remote-control.md)，而不是等待 `/remote-control`。將其設定為 `true` 以開啟自動連線，`false` 以關閉。在 `/config` 中顯示為**為所有工作階段啟用遠端控制**。

* **範圍**：[`任何檔案`](#scopes)。Claude Code 也會讀取舊版本在 `~/.claude.json` 中留下的值。
* **類型**：布林值
  * `true`：Claude Code 在每個互動工作階段啟動時自動連線遠端控制
  * `false`：Claude Code 等待 `/remote-control`
* **預設**：未設定，因此[自動連線預設](https://code.claude.com/docs/zh-TW/remote-control.md#enable-remote-control-for-all-sessions)適用
* **每個工作階段的覆寫**：`--remote-control` 即使此金鑰為 `false` 也會為一個工作階段開啟遠端控制，沒有旗標會為一個工作階段關閉它

```json settings.json theme={null}
{
  "remoteControlAtStartup": true
}
```

Claude Code 忽略來自專案或本機設定的 `true`，因此儲存庫可以為其簽出關閉自動連線，但無法開啟。如需完整的每個範圍行為，請參閱[為所有工作階段啟用遠端控制](https://code.claude.com/docs/zh-TW/remote-control.md#enable-remote-control-for-all-sessions)和[較嚴格值適用的安全金鑰](https://code.claude.com/docs/zh-TW/settings.md#security-keys-where-the-stricter-value-applies)。

### `sshConfigs`

將 SSH 連線新增到[桌面](https://code.claude.com/docs/zh-TW/desktop.md#pre-configure-ssh-connections-for-your-team)環境選擇器。管理員使用 `sshConfigs` 向團隊分發共用連線。使用者可以選擇受管理的連線，並為其[設定自己的 **Worktree 資料夾**](https://code.claude.com/docs/zh-TW/desktop.md#set-the-worktree-folder-on-an-existing-connection)。他們無法在應用程式中編輯其其他欄位或刪除它。

* **範圍**：[`使用者或受管理`](#scopes)。桌面應用程式讀取此金鑰。預設情況下，它會從[單一受管理來源](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)讀取受管理的連線。
* **類型**：物件陣列，每個物件具有必需的 `id`、`name` 和 `sshHost` 以及選用的 `sshPort` 和 `sshIdentityFile`
* **預設**：未設定

此範例新增一個名為 `Dev VM` 的連線，連線到 `user@dev.example.com`：

```json settings.json theme={null}
{
  "sshConfigs": [
    {
      "id": "dev-vm",
      "name": "Dev VM",
      "sshHost": "user@dev.example.com"
    }
  ]
}
```

### `sshHostAllowlist`

限制[桌面 SSH 工作階段](https://code.claude.com/docs/zh-TW/desktop.md#restrict-which-ssh-hosts-users-can-connect-to)可以連線到的主機。只有桌面應用程式讀取此金鑰；CLI 不讀取。模式不區分大小寫：`*` 符合任何主機，`*.example.com` 符合 `example.com` 和每個子網域，其他任何內容都是針對 `~/.ssh/config` 解析後的主機名稱的精確符合。空陣列會關閉 SSH 工作階段。

使用 Claude Desktop v3.1623.0 或更新版本時，工作階段的[跳板主機](https://code.claude.com/docs/zh-TW/desktop.md#allow-jump-hosts)也必須符合某個模式。

* **範圍**：[`受管理`](#scopes)。預設情況下，Desktop 會從[單一受管理來源](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)讀取此金鑰。
* **類型**：主機名稱模式陣列
* **預設**：未設定，因此允許任何主機

此範例允許 `devboxes.example.com` 及其子網域，加上精確主機 `bastion.example.com`：

```json managed-settings.json theme={null}
{
  "sshHostAllowlist": ["*.devboxes.example.com", "bastion.example.com"]
}
```

Desktop 無法讀取為主機清單的值（例如 `true` 或物件），在您修正之前會被視為空陣列，但 `null` 除外，它會被視為未設定。需要 Claude Desktop v2.26454.0 或更新版本。

如果您在排名最高的來源中將 [`managedSourcesBehavior`](#managedsourcesbehavior) 設定為 `"merge"`，Desktop 會合併來自每個[管理員來源](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)的清單，並允許符合其中任何一個清單的主機。如果您在某個來源中設定空陣列，對於另一個來源所列出的主機，SSH 工作階段仍會保持開啟。

### `sshHostCommands`

將主機來自命令的 SSH 連線新增到[桌面](https://code.claude.com/docs/zh-TW/desktop.md#create-an-ssh-connection-from-a-command)環境選擇器。當您建立連線或為其建立另一台機器時，Desktop 會在您的電腦上執行該項目的命令，並連線到該命令所輸出的主機。

需要在 macOS 或 Linux 上使用 Claude Desktop v3.6556.0 或更新版本，或在 Windows 上使用 v4.16336.0 或更新版本，並以 Claude 帳戶登入。在 Windows 上，Desktop 也必須[透過 OpenSSH 用戶端連線](https://code.claude.com/docs/zh-TW/desktop.md#use-your-ssh-configuration)。

* **範圍**：[`使用者或受管理`](#scopes)。只有桌面應用程式讀取此金鑰。它會從電腦上的[單一受管理設定檔或 MDM 原則](https://code.claude.com/docs/zh-TW/desktop.md#distribute-commands-to-your-team)讀取受管理的項目，並忽略[伺服器管理的設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)中的此金鑰。
* **類型**：物件陣列，每個物件具有必需的 `id`、`name` 和 `command` 以及選用的 `sshIdentityFile` 和 `startDirectory`。Desktop 不會將 `command` 當作 shell 語法讀取，因此管線和變數無法運作：[請將其寫成程式及其引數](https://code.claude.com/docs/zh-TW/desktop.md#write-the-command)。
* **預設**：未設定

此範例新增一個名為 `Dev box` 的連線，其中 `acme-dev create` 代表您自己的工具：

```json settings.json theme={null}
{
  "sshHostCommands": [
    {
      "id": "devbox",
      "name": "Dev box",
      "command": "acme-dev create"
    }
  ]
}
```

在 Windows 上，像 `acme-dev` 這樣的單純名稱無法運作，因此請[以程式的完整路徑作為命令開頭](https://code.claude.com/docs/zh-TW/desktop.md#write-the-command-on-windows)。

在 Claude Code v2.1.307 之前，Edit 工具會拒絕將此金鑰新增到有效設定檔的變更，並顯示錯誤 `Unrecognized field: sshHostCommands`。在這些版本上，請改用文字編輯器新增此金鑰；Claude Code 會載入包含此金鑰的檔案。在 Desktop 中，起作用的是 [Code 標籤的 Claude Code 版本](https://code.claude.com/docs/zh-TW/desktop.md#claude-code-version-in-the-code-tab)，而非您終端機的版本。

## 身分驗證和提供者

透過協助指令碼提供憑證，對於組織，強制執行登入方法或組織。請參閱[身分驗證](https://code.claude.com/docs/zh-TW/authentication.md)。

### `allowedProviders`

列出機器可能透過其到達 Claude 的服務，例如 Anthropic API、Amazon Bedrock 或 LLM 閘道。未列出的提供者上的工作階段在啟動時、登入時以及下次聯絡 API 時被拒絕，因此在工作階段中期切換到未列出的提供者也被拒絕。[拒絕訊息](https://code.claude.com/docs/zh-TW/errors.md#managed-settings-dont-allow-this-api-provider)會命名選擇提供者的內容和繼續的步驟。需要 Claude Code v2.1.285 或更新版本。

* **範圍**：[`受管`](#scopes)。機器自己的管理員來源設定的清單、MDM 原則和受管設定檔，在伺服器受管設定也提供一個時繼續適用：工作階段可能只使用兩個清單上的提供者，因此伺服器受管清單可以縮小機器允許的內容，但永遠無法擴大它。哪個機器來源的 `allowedProviders` 計數遵循[Claude Code 如何結合受管來源](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)。透過伺服器受管設定單獨提供的清單僅到達[擷取伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md#platform-availability)的工作階段。
* **類型**：字串陣列，每個都是以下之一：
  * `"anthropic"`：Anthropic 自己的主機上的 Anthropic API，透過 claude.ai 或 Console 登入或 API 金鑰。將其與 [`forceLoginMethod`](#forceloginmethod) 或 [`forceLoginOrgUUID`](#forceloginorguuid) 配對以也限制登入
  * `"bedrock"`：[Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md)
  * `"vertex"`：[Google Cloud 的 Agent Platform](https://code.claude.com/docs/zh-TW/google-vertex-ai.md)，前身為 Vertex AI
  * `"foundry"`：[Microsoft Foundry](https://code.claude.com/docs/zh-TW/microsoft-foundry.md)
  * `"anthropicAws"`：[AWS 上的 Claude Platform](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md)
  * `"mantle"`：Amazon Bedrock [Mantle 端點](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#use-the-mantle-endpoint)。[在 Invoke API 旁邊執行 Mantle](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#run-mantle-alongside-the-invoke-api) 的工作階段使用兩個提供者，因此將 `"bedrock"` 和 `"mantle"` 一起列出
  * `"customEndpoint"`：Anthropic API 或雲端提供者的 API 傳送到另一個主機，例如由 `ANTHROPIC_BASE_URL` 或提供者的端點變數（例如 `ANTHROPIC_BEDROCK_BASE_URL`）命名的 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)。Claude Code 僅針對受管 [`env`](#env) 區塊固定的確切值允許它
  * `"gateway"`：[Cloud 閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)登入
* **預設**：未設定，所以可以使用任何提供者

```json managed-settings.json theme={null}
{
  "allowedProviders": ["anthropic", "bedrock"]
}
```

每個雲端提供者的項目表示該提供者自己的服務，包括其區域、FIPS 和私人端點。

Claude Code 不認識為提供者名稱的項目被丟棄並報告，清單的其餘部分保持強制執行。使用空清單，或其每個項目都無法識別的清單，Claude Code 拒絕每個提供者，不在機器上啟動。

#### 需要在受管 `env` 中固定的端點

固定是在受管 [`env`](#env) 區塊中設定的端點變數值。當工作階段將提供者的流量傳送到該提供者自己的服務以外的地方時，Claude Code 僅在工作階段的值與固定值相同時允許它。這些端點需要一個：

* **`"customEndpoint"` 工作階段**：命名主機的變數，例如 `ANTHROPIC_BASE_URL`
* **Amazon Bedrock**：AWS SDK 的 `AWS_ENDPOINT_URL`、`AWS_ENDPOINT_URL_BEDROCK` 和 `AWS_ENDPOINT_URL_BEDROCK_RUNTIME` 變數，當它們指向 Bedrock 自己的服務以外時。工作階段保持在 `"bedrock"` 下而不是 `"customEndpoint"`
* **閘道登入的 URL**：工作階段保持在 `"gateway"` 下，[`forceLoginGatewayUrl`](#forcelogingatewayurl) 也計為固定

哪些 `env` 區塊計為固定取決於清單設定的位置：

* **機器上的管理員來源設定清單**：僅機器自己的管理員來源的 `env` 區塊計為固定
* **僅伺服器受管設定設定清單**：這些伺服器受管設定中的 `env` 值也計為固定

清單不判斷雲端提供者的憑證和租賃變數或網路路徑，例如 `HTTPS_PROXY` 和 TLS 憑證設定。在受管 `env` 區塊中為整個機隊設定這些。

### `apiKeyHelper`

執行您自己的命令來產生 Claude Code 隨著模型請求傳送的憑證。Claude Code 透過系統 shell 執行命令，在 macOS 和 Linux 上為 `/bin/sh`，在 Windows 上為 `cmd`，並將其輸出作為 `X-Api-Key` 和 `Authorization: Bearer` 標頭傳送。將其用於動態或輪換憑證，例如從保管庫擷取的短期權杖。

* **範圍**：[`任何檔案`](#scopes)
* **類型**：字串，shell 命令列
* **預設**：未設定，所以 Claude Code 不執行協助程式

```json settings.json theme={null}
{
  "apiKeyHelper": "/bin/generate_temp_api_key.sh"
}
```

Claude Code 快取該值，並在以下情況下重新執行命令：

* 在快取生命週期之後，預設為五分鐘，或您使用 [`CLAUDE_CODE_API_KEY_HELPER_TTL_MS`](https://code.claude.com/docs/zh-TW/env-vars) 設定的間隔。
* 當對 Anthropic API 的請求（直接或透過 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)）失敗並出現 `401` 或 `403` 時。
* 在傳送對 Anthropic API 的請求之前（直接或透過 LLM 閘道），當快取的輸出是協助程式產生後過期的 JWT 時。需要 Claude Code v2.1.246 或更新版本。

最後兩種情況僅在協助程式的輸出是 Claude Code 傳送的憑證且未設定 `ANTHROPIC_AUTH_TOKEN` 時適用。

在互動式工作階段中，當命令來自專案或本機設定時，Claude Code 在您接受工作區信任提示之前不會執行它。請參閱[憑證管理](https://code.claude.com/docs/zh-TW/authentication.md#credential-management)。

### `awsAuthRefresh`

執行您自己的命令（例如 `aws sso login`），以在 Claude Code 對 [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md) 的憑證停止運作時重新整理 `.aws` 目錄中的憑證。Claude Code 首先根據 STS 檢查目前憑證，僅在該檢查失敗時執行命令，然後讀取重新整理的 `.aws` 目錄。

當使用相同命令和憑證的多個 Claude Code 程序（例如不同的終端機或 IDE 視窗）同時檢查失敗時，由一個程序執行命令，其餘程序會等待該次執行，而不會各自啟動自己的執行。已等待 60 秒且有請求待處理的程序會自行執行命令。若要關閉此行為，請將 [`CLAUDE_CODE_DISABLE_AUTH_REFRESH_LOCK`](https://code.claude.com/docs/zh-TW/env-vars) 設定為 `1`。

* **範圍**：[`任何檔案`](#scopes)
* **類型**：字串，shell 命令列
* **預設**：未設定，所以 Claude Code 不為您重新整理 AWS 憑證

```json settings.json theme={null}
{
  "awsAuthRefresh": "aws sso login --profile myprofile"
}
```

當您的重新整理流程寫入 `.aws` 時使用此金鑰；當它改為列印憑證時使用 [`awsCredentialExport`](#awscredentialexport)。請參閱[進階憑證設定](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#advanced-credential-configuration)。

### `awsCredentialExport`

執行您自己的命令，該命令將 AWS 憑證列印為 JSON，以便 Claude Code 可以使用不存在於 `.aws` 目錄中的憑證呼叫 [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md)。Claude Code 接受 `aws sts` 輸出形狀和平面 `aws configure export-credentials` 形狀，並將憑證範圍限定於其自己的 Bedrock 用戶端，因此 Claude 執行的 shell 命令仍然會看到您的環境憑證。

* **範圍**：[`任何檔案`](#scopes)
* **類型**：字串，shell 命令列
* **預設**：未設定，所以 Claude Code 使用環境 AWS 憑證鏈

```json settings.json theme={null}
{
  "awsCredentialExport": "/bin/generate_aws_grant.sh"
}
```

與 [`awsAuthRefresh`](#awsauthrefresh) 不同，Claude Code 在設定此命令時總是執行它，而不先檢查環境憑證。請參閱[進階憑證設定](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#advanced-credential-configuration)。

### `forceLoginMethod`

限制人員可以使用哪種帳戶登入。設定 `"claudeai"` 以僅允許 claude.ai 帳戶，設定 `"console"` 以僅允許 Claude Console 帳戶，或設定 `"gateway"` 以將人員傳送到 [cloud gateway](https://code.claude.com/docs/zh-TW/claude-apps-gateway) 而不是第一方登入。管理員在受管設定中設定它，並將其與 [`forceLoginOrgUUID`](#forceloginorguuid) 配對，以將開發人員的 claude.ai 登入保持在一個組織內。

如果您在任何設定檔中將其設定為 `"claudeai"`，Claude Code 也會停止在該檔案適用的工作階段中提供[無金鑰 Console 登入](https://code.claude.com/docs/zh-TW/authentication.md#sign-in-without-an-api-key)。若僅設定 `"console"`，人員在登入失敗後仍可使用無金鑰登入。若要讓 Claude Code 停止提供此選項，請參閱[在受管機器上停止提供無金鑰登入](https://code.claude.com/docs/zh-TW/authentication.md#stop-offering-the-keyless-sign-in-on-managed-machines)，其中也列出了 `forceLoginOrgUUID` 會變更的其他項目。

* **範圍**：[`任何檔案`](#scopes)。Claude Code 從與 [`forceLoginGatewayUrl`](#forcelogingatewayurl) 相同的來源接受 `"gateway"`，並在其他所有位置將其視為未設定。
* **類型**：字串，其中之一：
  * `"claudeai"`：僅 claude.ai 帳戶可以登入
  * `"console"`：僅 Claude Console 帳戶可以登入
  * `"gateway"`：Claude Code 將人員傳送到 cloud gateway 而不是第一方登入
* **預設**：未設定，所以人員選擇登入方法

```json settings.json theme={null}
{
  "forceLoginMethod": "claudeai"
}
```

每個第一方登入路徑都適用限制，包括 [VS Code 擴充功能](https://code.claude.com/docs/zh-TW/vs-code.md)、Agent SDK、`claude setup-token` 和 `/install-github-app`，除了終端機的互動式登入畫面（透過 `/login` 或首次執行上線到達），它預先選擇方法而不強制執行。在 v2.1.212 之前，僅終端機登入適用它。請參閱[限制登入到您的組織](https://code.claude.com/docs/zh-TW/authentication.md#restrict-login-to-your-organization)，了解每個登入路徑、環境憑證和第三方提供者的處理方式。

當機器上的受管來源設定 `"gateway"` 時，Claude Code 不使用剩餘登入、API 金鑰或 `apiKeyHelper` 憑證。請參閱[管理員原則需要 Cloud gateway 登入](https://code.claude.com/docs/zh-TW/errors.md#administrator-policy-requires-a-cloud-gateway-sign-in)，了解每一種情況產生的訊息。如果您透過 `CLAUDE_CODE_USE_BEDROCK` 或類似環境變數選擇 cloud 提供者，工作階段不需要 gateway 登入。在 v2.1.261 之前，Claude Code 在這些機器上使用剩餘登入。

### `forceLoginGatewayUrl`

設定 `/login` Cloud gateway 畫面連線到的 gateway URL，以便人員可以到達您的 [cloud gateway](https://code.claude.com/docs/zh-TW/claude-apps-gateway) 而無需輸入其位址。該畫面沒有 URL 欄位：設定此金鑰時，它會顯示您的 gateway URL，並在人員按下 Enter 時連線；不設定時，它會告訴他們聯絡其 IT 管理員。

在受管設定中，此金鑰或 `forceLoginMethod: "gateway"` 中的任一個都會使機器僅限 gateway，但使用 `CLAUDE_CODE_USE_*` 選擇雲端提供者的工作階段除外。`/login` 接著會在 Cloud gateway 畫面上開啟，沒有登入方法選擇器。請參閱[管理員原則需要 Cloud gateway 登入](https://code.claude.com/docs/zh-TW/errors.md#administrator-policy-requires-a-cloud-gateway-sign-in)，了解剩餘第一方登入或 API 金鑰會發生什麼。設定兩個金鑰，以便畫面連線而不是顯示錯誤。

* **範圍**：[`使用者或受管`](#scopes)。從機器上的受管來源讀取：`managed-settings.json`、macOS plist 或 Windows HKLM 登錄，或原則協助程式。在沒有上述任何來源的機器上，Claude Code v2.1.295 或更新版本也會從[使用者設定](https://code.claude.com/docs/zh-TW/claude-apps-gateway#set-the-gateway-url-in-user-settings)讀取它。Claude Code 在 HKCU 和伺服器受管設定中忽略它。
* **類型**：字串，包括協定（scheme）的完整 URL
* **預設**：未設定，所以 Cloud gateway 畫面顯示錯誤，告訴人員聯絡其 IT 管理員

```json managed-settings.json theme={null}
{
  "forceLoginGatewayUrl": "https://claude-gateway.example.com"
}
```

如果值不是有效的 URL，登入畫面會報告它，受管設定檔的其餘部分仍然適用。請參閱[設定 gateway URL](https://code.claude.com/docs/zh-TW/claude-apps-gateway#set-the-gateway-url)。

### `forceLoginOrgUUID`

從受管來源，要求 claude.ai 帳戶登入屬於一個 Anthropic 組織（以單一 UUID 給定）或屬於多個組織中的任一個（以陣列給定）。從任何設定檔，Claude Code 也使用單一 UUID 在 claude.ai 或 Claude Console 登入期間預先選擇該組織，而對於陣列則不預先選擇任何組織。如果您在任何設定檔中設定此鍵，Claude Code 也會停止在該檔案適用的工作階段中提供[無金鑰 Console 登入](https://code.claude.com/docs/zh-TW/authentication.md#sign-in-without-an-api-key)，並改為建立 API 金鑰。

* **範圍**：[`任何檔案`](#scopes)。僅受管來源強制執行限制；任何其他設定檔中的單一 UUID 在登入期間預先選擇組織而不限制它。
* **類型**：字串，一個 UUID，或字串陣列，多個 UUID
* **預設**：未設定，所以任何組織都可以登入

此範例接受來自兩個組織之一的登入，而不預先選擇一個：

```json managed-settings.json theme={null}
{
  "forceLoginOrgUUID": ["xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx", "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy"]
}
```

如果受管來源設定空陣列，或設定不是字串也不是字串陣列的值，使用 Anthropic 帳戶登入的使用者將無法啟動 Claude Code 或完成登入。他們會看到一則指名 `forceLoginOrgUUID` 並告訴他們聯絡管理員的訊息。若是 [`policyHelper`](#policyhelper) 輸出錯誤類型的值，則會改為[使其執行失敗](#helper-failures)。

請參閱[限制登入到您的組織](https://code.claude.com/docs/zh-TW/authentication.md#restrict-login-to-your-organization)，了解 Claude Code 如何處理 Claude Console 登入、其他登入路徑和環境憑證。

### `gatewayInternalNetworks`

宣告您的組織編號其內部網路的公開 IPv4 區塊，以便 `/login` 在那裡接受 [cloud gateway](https://code.claude.com/docs/zh-TW/claude-apps-gateway)。需要 Claude Code v2.1.268 或更新版本。

沒有此金鑰，`/login` 連線到私人位址上的任何 gateway，別無其他。有了它，`/login` 也接受列出區塊內的 gateway，僅透過直接連線。該連線上機器自己的位址也必須在同一區塊內。

* **範圍**：[`受管`](#scopes)。僅從機器上的來源讀取：`managed-settings.json`、macOS plist 或 Windows HKLM 登錄，或原則協助程式。Claude Code 在 HKCU 和伺服器受管設定中忽略它。
* **類型**：字串陣列，最多四個 IPv4 CIDR 區塊，每個 `/8` 到 `/32`，彼此不重疊，且都不與私人空間重疊。
* **預設**：未設定，所以 `/login` 僅接受私人位址上的 gateway

```json managed-settings.json theme={null}
{
  "gatewayInternalNetworks": ["203.0.113.0/24"]
}
```

將範例中的文件範圍替換為您自己的區塊。Claude Code 拒絕文件範圍、VPN 和 NAT64 用戶端在本機使用的範圍，以及沒有網路編號的保留空間，例如多播。

如果項目無效，或值不是字串清單，`/login` 會命名問題，並拒絕機器上的每個新 gateway 登入，直到您修正值。現有登入繼續運作。請參閱[允許 gateway 在您擁有的公開位址空間上](https://code.claude.com/docs/zh-TW/claude-apps-gateway#allow-a-gateway-on-public-address-space-you-own)，了解完整規則以及開發人員看到的內容。

### `gcpAuthRefresh`

執行您自己的命令，以在 Claude Code 發現 Google Cloud Application Default Credentials 已過期或無法載入時重新整理它們，以便 [Google Cloud 的 Agent Platform](https://code.claude.com/docs/zh-TW/google-vertex-ai.md) 請求在您不手動重新驗證的情況下繼續運作。

當使用相同命令和憑證的多個 Claude Code 程序（例如不同的終端機或 IDE 視窗）同時發現憑證已過期時，由一個程序執行命令，其餘程序會等待該次執行，而不會各自啟動自己的執行。已等待 60 秒且有請求待處理的程序會自行執行命令。若要關閉此行為，請將 [`CLAUDE_CODE_DISABLE_AUTH_REFRESH_LOCK`](https://code.claude.com/docs/zh-TW/env-vars) 設定為 `1`。

* **範圍**：[`任何檔案`](#scopes)
* **類型**：字串，shell 命令列
* **預設**：未設定，所以 Claude Code 的憑證錯誤會告訴您自己執行 `gcloud auth application-default login`

```json settings.json theme={null}
{
  "gcpAuthRefresh": "gcloud auth application-default login"
}
```

請參閱[進階憑證設定](https://code.claude.com/docs/zh-TW/google-vertex-ai.md#advanced-credential-configuration)。

### `otelHeadersHelper`

執行您自己的命令來產生 Claude Code 隨著 OpenTelemetry 匯出傳送的標頭，適用於權杖輪換的後端。Claude Code 在啟動時執行它，之後定期執行，並期望在 stdout 上看到字串標頭值的 JSON 物件。

* **範圍**：[`任何檔案`](#scopes)
* **類型**：字串，可執行路徑或 shell 命令列
* **預設**：未設定，所以 Claude Code 不新增協助程式產生的標頭

```json settings.json theme={null}
{
  "otelHeadersHelper": "/bin/generate_otel_headers.sh"
}
```

使用 [`CLAUDE_CODE_OTEL_HEADERS_HELPER_DEBOUNCE_MS`](https://code.claude.com/docs/zh-TW/env-vars) 設定重新整理間隔。請參閱[動態標頭](https://code.claude.com/docs/zh-TW/monitoring-usage.md#dynamic-headers)，了解指令碼需求以及協助程式失敗時會發生什麼。

## 更新和版本控制

選擇更新頻道，並針對組織，固定人員可以執行的版本。請參閱[更新 Claude Code](https://code.claude.com/docs/zh-TW/setup.md#update-claude-code)。

### `autoUpdatesChannel`

選擇[發行頻道](https://code.claude.com/docs/zh-TW/setup.md#configure-release-channel)背景自動更新和 `claude update` 遵循的頻道。設定 `"stable"` 以取得通常約一週舊的版本，並跳過具有重大迴歸的發行版本，或設定 `"latest"` 以取得最新發行版本。

* **範圍**：[`Any file`](#scopes)。在受管設定中設定以在整個組織中強制執行一個頻道。
* **類型**：字串，其中之一：
  * `"latest"`：更新遵循最新發行版本
  * `"stable"`：更新遵循通常約一週舊的版本，並跳過具有重大迴歸的發行版本
* **預設**：未設定，因此 Claude Code 遵循 `"latest"`

```json settings.json theme={null}
{
  "autoUpdatesChannel": "stable"
}
```

當您在 `/config` 中的**自動更新頻道**下選擇時，Claude Code 會將 `"stable"` 寫入您的使用者設定，並在您在該處切換回最新版本時移除該金鑰。`claude install stable` 和 `claude install latest` 也會儲存您命名的頻道。在 `/config` 中從 `"latest"` 切換到 `"stable"` 時，會詢問是否允許降級或保持在目前版本；保持設定會設定 [`minimumVersion`](#minimumversion)。Homebrew 安裝會忽略此金鑰：`claude-code` cask 追蹤穩定版本，`claude-code@latest` 追蹤最新版本，而 `claude update` 遵循 `brew upgrade`。若要完全關閉自動更新，請在 `env` 中設定 [`DISABLE_AUTOUPDATER`](https://code.claude.com/docs/zh-TW/setup#disable-auto-updates)。

### `minimumVersion`

防止背景自動更新和 `claude update` 安裝低於此版本的任何版本，因此移至 `"stable"` 頻道不會從較新的 `"latest"` 組建中降級您。當您在 `/config` 中選擇在切換頻道時保持在目前版本時，Claude Code 會為您寫入此金鑰，並在您切換回 `"latest"` 時清除它。

* **範圍**：[`Any file`](#scopes)。在受管設定中設定以固定組織範圍的最小值，使用者和專案設定無法降低。
* **類型**：字串，版本號碼，例如 `"2.1.100"`；不是有效版本的值會被忽略
* **預設**：未設定，因此更新可以安裝頻道提供的任何版本

此範例遵循穩定頻道，並拒絕安裝低於 2.1.100 的任何版本：

```json settings.json theme={null}
{
  "autoUpdatesChannel": "stable",
  "minimumVersion": "2.1.100"
}
```

此金鑰僅限制更新。若要讓 Claude Code 拒絕在版本以下啟動，請改用 [`requiredMinimumVersion`](#requiredminimumversion)。請參閱[固定最小版本](https://code.claude.com/docs/zh-TW/setup.md#pin-a-minimum-version)。

### `requiredMaximumVersion`

設定您的組織允許啟動的最新 Claude Code 版本。當執行中的版本較新時，Claude Code 在啟動時退出，並告訴使用者透過您組織的核准方法安裝核准的版本；`claude install <version>` 也可能有效。需要 Claude Code v2.1.163 或更新版本。

* **範圍**：[`Managed`](#scopes)。Claude Code 在其他地方忽略金鑰時不會發出警告。
* **類型**：字串，版本號碼，例如 `"2.1.150"`；不是有效版本的值會被忽略
* **預設**：未設定，因此不適用上限

```json managed-settings.json theme={null}
{
  "requiredMaximumVersion": "2.1.150"
}
```

背景自動更新和 `claude update` 會跳過上限以上的版本，因此範圍內的安裝會保持在範圍內。`claude update`、`claude install` 和 `claude doctor` 在上限以上繼續運作，以便使用者可以復原。將其與 [`requiredMinimumVersion`](#requiredminimumversion) 配對以強制執行範圍。

### `requiredMinimumVersion`

設定您的組織允許啟動的最舊 Claude Code 版本。當執行中的版本較舊時，Claude Code 在啟動時退出，並告訴使用者透過您組織的核准方法進行更新。檢查僅在啟動時執行，因此已執行的工作階段會繼續。需要 Claude Code v2.1.163 或更新版本。

* **範圍**：[`Managed`](#scopes)。Claude Code 在其他地方忽略金鑰時不會發出警告。
* **類型**：字串，版本號碼，例如 `"2.1.150"`；不是有效版本的值會被忽略
* **預設**：未設定，因此不適用下限

```json managed-settings.json theme={null}
{
  "requiredMinimumVersion": "2.1.150"
}
```

`claude update`、`claude install` 和 `claude doctor` 在下限以下繼續運作，以便使用者可以復原。與僅防止降級的 [`minimumVersion`](#minimumversion) 不同，此金鑰會阻止啟動。將其與 [`requiredMaximumVersion`](#requiredmaximumversion) 配對以強制執行範圍。

## 工具

在 [Claude Code 桌面應用程式](https://code.claude.com/docs/zh-TW/desktop.md)中關閉特定工具。終端 CLI 會忽略這些金鑰。如需了解工具本身，請參閱 [Claude 可用的工具](https://code.claude.com/docs/zh-TW/tools-reference.md)。

### `browserExternalPageTools`

防止 Claude 在桌面應用程式的 [Browser 窗格](https://code.claude.com/docs/zh-TW/desktop.md#browse-external-sites)中使用其工具來讀取或作用於外部頁面。您組織中的人員仍然可以自行開啟外部網站，本機開發伺服器預覽會繼續與 Claude 的工具搭配運作。桌面應用程式會讀取此金鑰；終端 CLI 會忽略它。

* **範圍**：[`Managed`](#scopes)
* **類型**：字串，`"disabled"`；桌面應用程式也接受 `"disable"`，在任一情況下
* **預設**：未設定，因此 Claude 的工具可在外部頁面上運作

```json managed-settings.json theme={null}
{
  "browserExternalPageTools": "disabled"
}
```

任何其他值都會讓 Claude 的工具保持開啟，非空字串若不是兩個接受的值之一，會記錄警告。若要同時為人員和 Claude 封鎖外部網站，請改為設定 [`disableBrowserExternalNavigation`](#disablebrowserexternalnavigation)。請參閱 [限制您組織的外部瀏覽](https://code.claude.com/docs/zh-TW/desktop.md#restrict-external-browsing-for-your-organization)。

### `disableBrowserExternalNavigation`

在桌面應用程式的 [Browser 窗格](https://code.claude.com/docs/zh-TW/desktop.md#browse-external-sites)中為人員和 Claude 關閉外部瀏覽。Localhost 開發伺服器預覽會繼續運作。桌面應用程式會讀取此金鑰；終端 CLI 會忽略它。

* **範圍**：[`Managed`](#scopes)
* **類型**：布林值；只有 JSON 布林值 `true` 會生效
  * `true`：桌面應用程式為人員和 Claude 關閉 Browser 窗格中的外部瀏覽；localhost 預覽會繼續運作
  * `false`：外部瀏覽保持開啟
* **預設**：未設定，因此外部瀏覽是開啟的

```json managed-settings.json theme={null}
{
  "disableBrowserExternalNavigation": true
}
```

桌面應用程式會忽略任何其他值，非布林值（例如字串 `"true"` 或 `1`）也會記錄警告。若要保持外部瀏覽開啟但讓 Claude 的工具在外部頁面上關閉，請改為設定 [`browserExternalPageTools`](#browserexternalpagetools)。請參閱 [限制您組織的外部瀏覽](https://code.claude.com/docs/zh-TW/desktop.md#restrict-external-browsing-for-your-organization)。

### `disableMobileSimulatorTools`

封鎖 Claude 對桌面應用程式 [iOS Simulator 窗格](https://code.claude.com/docs/zh-TW/desktop-ios-simulator.md#turn-off-simulator-access)的工具。人員保留對窗格的手動使用；只有 Claude 的存取被移除，沒有人可以從應用程式內部將其重新開啟。桌面應用程式會讀取此金鑰；終端 CLI 會忽略它。

* **範圍**：[`Managed`](#scopes)
* **類型**：布林值；只有 JSON 布林值 `true` 會生效
  * `true`：桌面應用程式封鎖 Claude 對 iOS Simulator 窗格的工具
  * `false`：Claude 的模擬器工具遵循桌面應用程式中每個人的設定切換
* **預設**：未設定，因此 Claude 的模擬器工具遵循桌面應用程式中每個人的設定切換

```json managed-settings.json theme={null}
{
  "disableMobileSimulatorTools": true
}
```

桌面應用程式會忽略任何其他值，非布林值（例如字串 `"true"` 或 `1`）也會記錄警告。

## 隱私與遙測

控制 Claude Code 保留工作階段資料的時間長度以及它傳送的內容。關閉使用量指標和錯誤報告的開關是環境變數，而不是設定鍵：在 [`env`](#env) 鍵或殼層中設定 `DISABLE_TELEMETRY`、`DISABLE_ERROR_REPORTING` 或 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`。[遙測服務](https://code.claude.com/docs/zh-TW/data-usage.md#telemetry-services)說明每個開關會停止什麼。兩個例外可從設定檔關閉：下面的 [`feedbackDrafts`](#feedbackdrafts) 用於 Claude 起草的回饋，以及下面的 [`feedbackSurveyRate`](#feedbacksurveyrate) 用於工作階段調查。

### `cleanupPeriodDays`

設定 Claude Code 在刪除之前保留[工作階段文字記錄和其他應用程式資料](https://code.claude.com/docs/zh-TW/claude-directory.md#cleaned-up-automatically)的天數。Claude Code 在工作階段開始後作為背景掃描執行刪除，只要它能安全地確定保留期間。掃描會刪除文字記錄而不顯示訊息，因此您未使用超過保留期間的工作階段不再出現在 [`/resume`](https://code.claude.com/docs/zh-TW/sessions#resume-a-session) 選擇器中。

* **範圍**：[`Any file`](#scopes)
* **類型**：天數，整數，最小值 `1`
* **預設值**：`30`

```json settings.json theme={null}
{
  "cleanupPeriodDays": 20
}
```

設定 `0` 會驗證失敗，因此請選擇較大的值，例如 `3650` 以進行長期保留。若要停止 Claude Code 完全寫入文字記錄，請參閱[純文字儲存](https://code.claude.com/docs/zh-TW/claude-directory.md#plaintext-storage)。

### `desktopSessionCleanupPeriodDays`

為您在 Claude Desktop 或 Cowork 中啟動或最近繼續的工作階段逐字稿設定天數年齡限制。沒有此鍵，Claude Code [會以任何年齡保留這些逐字稿](https://code.claude.com/docs/zh-TW/claude-directory.md#cleaned-up-automatically)。Claude Code 在每個逐字稿的年齡超過此限制和 [`cleanupPeriodDays`](#cleanupperioddays) 時刪除它，因此當 `cleanupPeriodDays` 處於其預設值 30 時，值 `7` 仍會保留它們 30 天。[自動清理](https://code.claude.com/docs/zh-TW/claude-directory.md#cleaned-up-automatically)列出了改為適用 `cleanupPeriodDays` 且 Claude Code 忽略此鍵的情況。需要 Claude Code v2.1.248 或更新版本。

* **範圍**：[`User or managed`](#scopes)。Claude Code 也會從您使用 `--settings` 傳遞的檔案中讀取該鍵，並在專案和本機設定中忽略它。
* **類型**：天數，整數，最小值 `0`
* **預設值**：`0`，不設定年齡限制

```json settings.json theme={null}
{
  "desktopSessionCleanupPeriodDays": 90
}
```

### `feedbackDrafts`

控制 [Claude 起草的回饋](https://code.claude.com/docs/zh-TW/tools-reference.md#sendfeedback-tool-behavior)：Claude 是否可以將回饋草稿排隊供您審查，以及 Claude Code 在 Claude 排隊時是否顯示卡片。

* **範圍**：[`User or managed`](#scopes)
* **類型**：字串，`"notify"`、`"quiet"` 或 `"off"` 之一
  * `"notify"`：當 Claude 排隊草稿時，Claude Code 在提示上方顯示卡片，預設情況下[一個工作階段中最多三張卡片](https://code.claude.com/docs/zh-TW/tools-reference.md#what-you-see-when-claude-drafts)
  * `"quiet"`：Claude 起草而不顯示卡片。您在提示頁尾看到排隊草稿的計數，並在 `/feedback` 中審查它們
  * `"off"`：Claude Code 移除 SendFeedback 工具，因此 Claude 無法排隊草稿
* **預設值**：`"notify"`
* **每個工作階段覆蓋**：[`CLAUDE_CODE_SEND_FEEDBACK`](https://code.claude.com/docs/zh-TW/env-vars) 設定為 `0` 會關閉一個工作階段的功能

```json settings.json theme={null}
{
  "feedbackDrafts": "quiet"
}
```

在 `/config` 中顯示為 **Claude-drafted feedback**，它將此鍵寫入您的使用者設定。您只在 Claude [可以起草回饋](https://code.claude.com/docs/zh-TW/tools-reference.md#sessions-without-claude-drafted-feedback)的工作階段中看到 `/config` 列；設定 `"off"` 不會隱藏它，因此您可以從同一列重新開啟功能。受管設定中的值優先於您的使用者設定，因此當管理員設定此鍵時，該列顯示受管值，更改它無效。Claude Code 在專案和本機設定中忽略此鍵。

### `feedbackSurveyRate`

設定[工作階段品質調查](https://code.claude.com/docs/zh-TW/data-usage.md#session-quality-surveys)在工作階段符合條件時出現的機率。設定 `0` 以防止調查出現。

* **範圍**：[`Any file`](#scopes)
* **類型**：`0` 到 `1` 之間的數字
* **預設值**：未設定，因此 Claude Code 使用 Anthropic 遠端設定的速率，或在 Amazon Bedrock、Google Cloud 的 Agent Platform 和 Microsoft Foundry 上的內建速率 `0.005`，它們不接收遠端設定
* **每個工作階段覆蓋**：[`CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY`](https://code.claude.com/docs/zh-TW/env-vars) 設定為 `1` 會關閉一個工作階段的調查，無論此鍵設定的速率如何

```json settings.json theme={null}
{
  "feedbackSurveyRate": 0.05
}
```

相同的速率適用於 VS Code 擴充功能中的調查。

### `skipWebFetchPreflight`

跳過 [WebFetch 網域安全檢查](https://code.claude.com/docs/zh-TW/data-usage.md#webfetch-domain-safety-check)，它在擷取之前將每個請求的主機名稱傳送到 `api.anthropic.com`。在阻止流量到 Anthropic 的環境中設定 `true`，例如 Amazon Bedrock、Google Cloud 的 Agent Platform 或具有限制性出口的 Microsoft Foundry 部署。

* **範圍**：[`Any file`](#scopes)
* **類型**：布林值
  * `true`：Claude Code 跳過 WebFetch 網域安全檢查
  * `false`：檢查在工作階段中首次擷取每個主機名稱之前執行，以及對於其先前檢查被阻止或失敗的主機名稱再次執行
* **預設值**：未設定，因此檢查在工作階段中首次擷取每個主機名稱之前執行

```json settings.json theme={null}
{
  "skipWebFetchPreflight": true
}
```

跳過檢查後，WebFetch 嘗試任何 URL 而不查詢封鎖清單，因此如果您需要限制 Claude 可以到達的網域，請將其與 [`WebFetch` 權限規則](https://code.claude.com/docs/zh-TW/permissions#webfetch)配對。

## 企業與受管設定

組織用來計算、重新整理和合併受管設定的金鑰。請參閱[設定受管設定](https://code.claude.com/docs/zh-TW/admin-setup.md)。

### `disableSideloadFlags`

在啟動時拒絕 `--plugin-dir`、`--plugin-url`、`--agents` 和 `--mcp-config` CLI 旗標，使用者否則可能會傳遞這些旗標來繞過 [`strictKnownMarketplaces`](#strictknownmarketplaces) 進行單次執行。Claude Code 會以錯誤結束並列出被拒絕的旗標。在[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)中，Claude Code 會啟動工作階段並捨棄伺服器傳遞的每個 `--mcp-config` 項目，除了進程內 `type: "sdk"` 項目和 [Claude Tag](https://code.claude.com/docs/zh-TW/claude-tag.md) 工作階段的 Slack 工具外。需要 Claude Code v2.1.193 或更新版本。

* **範圍**: [`Managed`](#scopes)
* **類型**: 布林值
  * `true`: Claude Code 在啟動時拒絕 `--plugin-dir`、`--plugin-url`、`--agents` 和 `--mcp-config`，並以錯誤結束並列出它們。在雲端工作階段中，它會啟動工作階段並捨棄伺服器傳遞的每個 `--mcp-config` 項目，除了進程內 `type: "sdk"` 項目和 Claude Tag 工作階段的 Slack 工具外
  * `false`: Claude Code 接受這些旗標
* **預設**: `false`

```json managed-settings.json theme={null}
{
  "disableSideloadFlags": true
}
```

Claude Code 仍然接受其伺服器全部為進程內 `type: "sdk"` 項目的 `--mcp-config`，因此 Agent SDK 和 VS Code 擴充功能可繼續運作。使用者仍然可以使用 `claude mcp add` 或 `.mcp.json` 檔案新增伺服器；如需個別伺服器控制，也請設定 [`allowedMcpServers`](https://code.claude.com/docs/zh-TW/managed-mcp)。需要 Claude Code v2.1.193 或更新版本。

`disableSideloadFlags` 也會拒絕來自下列來源的外掛程式資料夾：

* **[`CLAUDE_CODE_PLUGIN_DIRS`](https://code.claude.com/docs/zh-TW/env-vars#variables) 環境變數**：當變數指定外掛程式資料夾時，Claude Code 會在啟動時以錯誤結束，錯誤會指出該變數並說明要取消設定它。需要 Claude Code v2.1.280 或更新版本
* **Agent SDK [`addPlugins`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#load-more-plugin-folders-with-addplugins) 選項**：當應用程式在 `addPlugins` 中將外掛程式資料夾傳遞給 `reloadPlugins()` 時，該呼叫會以錯誤失敗。工作階段會以已有的外掛程式繼續執行。需要 Claude Code v2.1.301 或更新版本

在雲端工作階段中，Claude Code 也會忽略伺服器傳遞的中途 MCP 更新，即雲端工作階段設定和 SDK `setMcpServers()` 呼叫背後的路徑，這些呼叫會到達這些工作階段。進程內 `type: "sdk"` 項目和 Claude Tag 工作階段的 Slack 工具在那裡也保持豁免。在 v2.1.268 之前，此捨棄和啟動捨棄也移除了 Claude Tag 工作階段的 Slack 工具。在 v2.1.239 之前，伺服器傳遞的 `--mcp-config` 會阻止雲端工作階段啟動。

桌面應用程式自行管理某些外掛程式，包括從 claude.ai 同步的外掛程式和您的組織透過應用程式部署的外掛程式。如果您透過 MDM、OS 層級原則或受管設定檔案將此金鑰部署到裝置，桌面應用程式不會將這些外掛程式傳遞給該裝置上的下列工作階段：

* **[使用者機器上的程式碼工作階段](https://code.claude.com/docs/zh-TW/desktop.md#environment-configuration)**: 它們也會在沒有為使用者的 claude.ai 帳戶啟用的技能的情況下啟動。Claude Code 從您受管設定中的市場安裝的外掛程式仍然會載入。在 [Claude Desktop on 3P](https://claude.com/docs/third-party/claude-desktop/overview) 中，您部署到裝置 `org-plugins` 目錄的外掛程式中的 MCP 伺服器仍然可用，因為桌面應用程式自己連接到它們。在 Claude Desktop v1.37937.0 之前，這些工作階段在啟動時失敗。
* **[使用者機器上的 Cowork 工作階段](https://code.claude.com/docs/zh-TW/managed-settings.md#where-and-when-a-policy-applies)**: 這些外掛程式內的技能和為使用者的 claude.ai 帳戶啟用的技能仍然可用。在 [Claude Desktop on 3P](https://claude.com/docs/third-party/claude-desktop/overview) 中，您部署到裝置 `org-plugins` 目錄的外掛程式中的 MCP 伺服器仍然可用，因為桌面應用程式自己連接到它們。在 Claude Desktop v1.44121.0 之前，這些工作階段在啟動時失敗。

### `forceRemoteSettingsRefresh`

阻止 CLI 啟動，直到 Claude Code 已重新整理地擷取[伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)。如果擷取失敗，Claude Code 會結束而不是繼續使用快取或無設定。當您的環境無法接受即使是短暫的時間窗口（在該窗口中工作階段執行時沒有其受管原則）時，請設定它。

當金鑰未設定時，Claude Code 不會在擷取時阻止啟動，但當開發人員在啟動時登入時，它會等待最多五秒鐘以進行擷取。雲端閘道工作階段始終會等待，如果無法到達閘道則會結束。

* **範圍**: [`Managed`](#scopes)。Claude Code 會接受來自任何受管理員控制的受管來源的 `true`，即使該來源不是最高優先順序的來源。
* **類型**: 布林值
  * `true`: Claude Code 會阻止啟動，直到它已重新整理地擷取伺服器受管設定，如果擷取失敗則會結束
  * `false`: Claude Code 不會在擷取時阻止啟動，但在登入啟動時會等待最多五秒鐘以進行擷取
* **預設**: `false`

```json managed-settings.json theme={null}
{
  "forceRemoteSettingsRefresh": true
}
```

在 MDM 設定檔或受管設定檔案中設定它，以在第一個伺服器承載到達之前強制執行失敗關閉啟動。Claude Code 只在擷取伺服器受管設定的工作階段中套用檢查，因此[不擷取它們](https://code.claude.com/docs/zh-TW/server-managed-settings.md#platform-availability)的工作階段會在不等待的情況下啟動。`claude auth` 子命令是豁免的，因此使用者可以在過期認證是擷取失敗原因時重新驗證。請參閱[強制執行失敗關閉啟動](https://code.claude.com/docs/zh-TW/server-managed-settings.md#enforce-fail-closed-startup)。

### `managedSourcesBehavior`

選擇 Claude Code 是否只套用您的組織傳遞的最高優先順序[受管來源](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)，或合併它傳遞的每個管理員來源。根據預設，Claude Code 會採用攜帶[原則金鑰](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)的最高優先順序來源並忽略其餘的。原則金鑰是除了此金鑰和 `wslInheritsWindowsSettings` 之外的任何設定金鑰。在該預設下，一旦伺服器受管設定或 MDM 原則傳遞原則金鑰，`managed-settings.json` 檔案只會貢獻 [Claude Code 從每個管理員來源讀取的金鑰](https://code.claude.com/docs/zh-TW/managed-settings.md#keys-read-from-every-admin-source)。使用 `"merge"`，您傳遞的每個管理員來源都會將其金鑰貢獻給一個合併的原則。需要 Claude Code v2.1.242 或更新版本。

只在您[排名](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)在最高優先順序下方的每個來源都在管理員控制下時設定 `"merge"`，因為 Claude Code 會從較低的來源（例如 `permissions.allow` 規則）新增項目到原則。

* **範圍**: [`Managed`](#scopes)。Claude Code 從攜帶此金鑰或原則金鑰的最高優先順序來源讀取此金鑰，並忽略排名較低的每個來源中的此金鑰，因此較低的來源無法選擇自己合併到上方的來源。Windows HKCU 登錄和[來自嵌入主機的父設定](https://code.claude.com/docs/zh-TW/managed-settings.md#let-an-embedding-host-add-policy)都不參與合併。
* **類型**: 字串，其中之一：
  * `"first-wins"`: 攜帶原則金鑰的最高優先順序來源提供原則，較低的來源只貢獻 [Claude Code 從每個管理員來源讀取的金鑰](https://code.claude.com/docs/zh-TW/managed-settings.md#keys-read-from-every-admin-source)
  * `"merge"`: 您傳遞的每個管理員來源都貢獻其金鑰，按以下規則合併
* **預設**: `"first-wins"`

在您部署的最高優先順序來源中傳遞金鑰。從未接收伺服器受管設定的機器也需要在其 MDM 設定檔中有金鑰，因為 Claude Code 從攜帶它或原則金鑰的最高優先順序來源讀取金鑰。`managed-settings.json` 檔案是排名最低的管理員來源，因此在那裡設定的 `"merge"` 沒有下方的來源可合併。在伺服器受管設定中，金鑰看起來像這樣：

```json theme={null}
{
  "managedSourcesBehavior": "merge"
}
```

在 `"merge"` 下，Claude Code 按其種類合併每個金鑰。此表格為每種金鑰提供規則。限制允許清單、整體取值和最高來源專用列列出它們涵蓋的每個金鑰，其他列提供範例：

| 金鑰種類 | Claude Code 如何合併它 | 金鑰 |
| :- | :- | :- |
| 清單 | 合併來自每個來源的項目 | [`permissions.allow`](#permissions-allow)、[`sandbox.network.allowedDomains`](#sandbox-network-alloweddomains) 和其他清單金鑰 |
| 鎖定 | 套用任何來源設定的最嚴格值。當沒有來源設定嚴格值時，只從最高來源套用較寬鬆的值 | [`allowManagedPermissionRulesOnly`](#allowmanagedpermissionrulesonly)、[`permissions.disableBypassPermissionsMode`](#permissions-disablebypasspermissionsmode) 和其他布林值或列舉鎖定 |
| 限制允許清單 | 從設定它的最高來源整體取得清單，不從較低的來源新增項目。當最高來源未設定時，從下一個較低的來源整體取得 | [`availableModels`](#availablemodels)、[`allowedMcpServers`](#allowedmcpservers)、[`allowedProviders`](#allowedproviders)、[`strictKnownMarketplaces`](#strictknownmarketplaces)、[`allowedChannelPlugins`](#allowedchannelplugins) 和 [`fallbackModel`](#fallbackmodel) 鏈 |
| 整體取值 | 從設定它的最高來源整體取得值，不合併來自較低來源的項目或欄位。當最高來源未設定時，從下一個較低的來源整體取得 | [`sandbox.credentials.awsPairs`](#sandbox-credentials-awspairs)、[`sandbox.ripgrep`](#sandbox-ripgrep) |
| 提供的 MCP 伺服器 | 合併來自每個來源的伺服器名稱。當兩個來源設定相同名稱時，套用較高來源的整體項目 | [`managedMcpServers`](#managedmcpservers) |
| 只從最高優先順序來源讀取 | 只從攜帶原則金鑰的最高優先順序來源讀取金鑰，因此即使最高來源未設定任何值，較低來源的值也會被忽略 | [`apiKeyHelper`](#apikeyhelper)、[`awsAuthRefresh`](#awsauthrefresh)、[`awsCredentialExport`](#awscredentialexport)、[`gcpAuthRefresh`](#gcpauthrefresh)、[`otelHeadersHelper`](#otelheadershelper)、`proxyAuthHelper`、[`parentSettingsBehavior`](#parentsettingsbehavior)、[`modelPicker`](#modelpicker)、[`policyHelper`](#policyhelper)、[`permissions.defaultMode`](#permissions-defaultmode) |
| `env` | [在管理員來源間按變數合併](https://code.claude.com/docs/zh-TW/managed-settings.md#keys-read-from-every-admin-source)，在 `"first-wins"` 和 `"merge"` 下都是如此 | [`env`](#env) |
| 每個其他金鑰 | 從設定它的最高來源取得值 | [`cleanupPeriodDays`](#cleanupperioddays)、[`model`](#model) |

整體取得 `sandbox.credentials.awsPairs` 和 `sandbox.ripgrep` 需要 Claude Code v2.1.257 或更新版本。

少數金鑰新增表格未顯示的條件：

* **[`policyHelper`](#policyhelper)**: Claude Code 只在攜帶原則金鑰的最高來源是 MDM 原則或受管設定檔案時接受它，因此在伺服器受管設定下它不適用。
* **[`modelOverrides`](#modeloverrides)**: 與 `availableModels` 配對。Claude Code 從設定它的最高來源取得 `modelOverrides`，除非較高的來源設定 `availableModels` 而不設定 `modelOverrides`。在這種情況下，它會忽略來自每個來源的 `modelOverrides`。
* **[`forceLoginGatewayUrl`](#forcelogingatewayurl)、[`gatewayInternalNetworks`](#gatewayinternalnetworks) 和 [`forceLoginMethod`](#forceloginmethod) 的 `"gateway"` 值**: Claude Code 從不從伺服器受管設定讀取它們中的任何一個，因此那裡的值既不適用也不隱藏在 MDM 原則或受管設定檔案中設定的值。在機器上的管理員來源中，只有攜帶原則金鑰的排名最高的來源提供它們，無論伺服器受管設定是否也存在。
* **[`forceLoginOrgUUID`](#forceloginorguuid) 以及 [`forceLoginMethod`](#forceloginmethod) 的 `"claudeai"` 和 `"console"` 值**: 請在[哪個受管來源提供登入金鑰](https://code.claude.com/docs/zh-TW/managed-settings.md#which-managed-source-supplies-login-keys)中查詢套用的值，而不是在表格中查詢。
* **[`allowedProviders`](#allowedproviders)**: 在表格的規則之後，機器本身的清單仍然限制結果，如其項目的範圍附註所述。

若要確認機器上合併了哪些來源，請執行 `/status` 並[讀取 `Setting sources` 行](https://code.claude.com/docs/zh-TW/managed-settings#read-the-source-in-/status)。

### `parentSettingsBehavior`

選擇 Claude Code 是否套用由嵌入主機程序（例如 Agent SDK 或 IDE 擴充功能）提供的受管設定，當管理員部署的受管層級也存在時。使用 `"first-wins"`，Claude Code 會捨棄主機提供的設定；使用 `"merge"`，它會透過限制性專用篩選器在管理員層級下套用它們。當主機需要將其自己的限制傳遞給它啟動的工作階段時，設定 `"merge"`，例如 Claude Desktop 傳遞閘道的出口允許清單。

* **範圍**: [`Managed`](#scopes)。Claude Code 從最高優先順序的管理員控制受管來源讀取它。
* **類型**: 字串，其中之一：
  * `"first-wins"`: 當管理員部署的受管層級存在時，Claude Code 會捨棄主機提供的設定
  * `"merge"`: Claude Code 透過限制性專用篩選器在管理員層級下套用主機提供的設定
* **預設**: `"first-wins"`

```json managed-settings.json theme={null}
{
  "parentSettingsBehavior": "merge"
}
```

當不存在管理員部署的受管層級時，此金鑰無效：主機的設定然後套用為唯一的受管層級，仍然篩選為限制性值。如需篩選器的限制以及受管來源如何互動，請參閱[來自嵌入主機的父設定](https://code.claude.com/docs/zh-TW/managed-settings.md#parent-settings-from-embedding-hosts)和[限制父設定](https://code.claude.com/docs/zh-TW/claude-apps-gateway#restrict-parent-settings)。

### `policyHelper`

執行您部署的可執行檔，在啟動時計算受管設定，因此您可以從裝置狀態、身分識別或遠端服務衍生原則，而不是靜態檔案。Claude Code 在接受第一個提示之前執行協助程式，並將其發出的設定視為工作階段的受管設定。

* **範圍**: [`Managed`](#scopes)。從 macOS plist、Windows HKLM 登錄或受管設定檔案讀取。Claude Code 從攜帶[原則金鑰](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)的最高優先順序受管來源讀取金鑰，並只在該來源是這三個之一時執行協助程式；它會忽略伺服器受管設定、HKCU 登錄和主機提供的父設定中的金鑰。
* **類型**: 具有 `path`、`timeoutMs` 和 `refreshIntervalMs` 的物件
* **預設**: 未設定，因此不執行協助程式

當伺服器受管設定在啟動時傳遞原則時，它們優先於協助程式的來源，協助程式不執行。

如果稍後的設定擷取報告伺服器受管設定已移除，Claude Code 會在該點執行協助程式，而不是等待下一次啟動。其輸出控制工作階段的其餘部分，失敗的執行會以與[失敗的啟動執行](#helper-failures)相同的訊息結束工作階段。

此範例以 5 秒逾時執行協助程式，並每五分鐘重新執行一次：

```json managed-settings.json theme={null}
{
  "policyHelper": {
    "path": "/usr/local/bin/claude-policy",
    "timeoutMs": 5000,
    "refreshIntervalMs": 300000
  }
}
```

#### 寫入協助程式輸出

Claude Code 執行協助程式時不帶任何引數，在其環境中設定 `CLAUDE_CODE_VERSION`，並從 stdout 讀取 JSON 信封，上限為 1 MiB。

將設定放在 `managedSettings` 金鑰下。沒有 `managedSettings` 金鑰的裸設定物件會以 `managedSettings` 未定義的方式解析並不套用任何內容，Claude Code 不報告任何錯誤：

```json theme={null}
{
  "managedSettings": {
    "permissions": { "deny": ["Read(//etc/secrets/**)"] }
  }
}
```

當協助程式發出 `managedSettings` 時，該物件成為執行的唯一受管設定來源：Claude Code 會忽略 MDM、檔案和 HKCU 來源，只從協助程式的輸出讀取[跨來源金鑰](https://code.claude.com/docs/zh-TW/managed-settings.md#keys-read-from-every-admin-source)，並從不合併[父設定](https://code.claude.com/docs/zh-TW/managed-settings.md#parent-settings-from-embedding-hosts)。

啟動 `forceRemoteSettingsRefresh` 檢查在協助程式之前執行，並讀取任何管理員來源。以 `0` 結束且信封省略 `managedSettings` 的協助程式不貢獻受管設定，其他來源照常套用。

#### 協助程式失敗

協助程式執行在以下情況下失敗：

* `path` 違反 [`policyHelper.path`](#policyhelper-path) 中的規則。
* `path` 處沒有一般檔案。Claude Code 在啟動協助程式之前檢查檔案，在相同的 `timeoutMs` 預算內，因此無回應的網路掛載可能導致執行失敗。
* 協助程式以非零結束、在 `timeoutMs` 經過時仍在執行，或根本無法啟動，例如因為它不可執行。
* 協助程式寫入超過 1 MiB 到 stdout 或 stderr。
* stdout 不是單一 JSON 物件，或其 `managedSettings` 有 [Claude Code 無法修復的結構描述違反](https://code.claude.com/docs/zh-TW/managed-settings.md#find-entries-claude-code-dropped)。

當啟動執行失敗時，Claude Code 會列印原因並拒絕啟動。在非零結束後，原因包括協助程式的 stderr，或當 stderr 為空時的 stdout。在逾時後，原因會命名 `timeoutMs` 限制，不包括協助程式輸出的任何部分。拒絕涵蓋互動式工作階段、`claude -p`、Agent SDK 工作階段、[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md) 和大多數子命令。

拒絕是刻意的，因此需要中斷復原能力的協助程式應該從其自己的快取提供並以 `0` 結束。

當背景重新整理失敗時，Claude Code 會保持最後成功的原則有效，`/status` 會顯示失敗的重新整理及其原因，直到重新整理成功。每次重新整理在與啟動執行相同的 `timeoutMs` 和失敗規則下執行。

使用 `--debug`，Claude Code 會將協助程式的 stderr 從每次執行寫入[偵錯日誌](https://code.claude.com/docs/zh-TW/debug-your-config.md)。

Claude Code 將無效的 `policyHelper` 值報告為[捨棄的項目](https://code.claude.com/docs/zh-TW/managed-settings.md#find-entries-claude-code-dropped)，並在剩餘的受管設定上啟動工作階段，不執行協助程式。無效值包括裸路徑字串和低於[其最小值](#policyhelper-timeoutms)的 `timeoutMs`。

若要關閉協助程式，請從設定它的來源移除金鑰。

### `policyHelper.path`

命名 Claude Code 執行的協助程式可執行檔。如需路徑違反下列規則時發生的情況，請參閱[協助程式失敗](#helper-failures)。

* **範圍**: [`Managed`](#scopes)。從 macOS plist、Windows HKLM 登錄或受管設定檔案讀取，無論 [`policyHelper`](#policyhelper) 在何處讀取。
* **類型**: 字串，標準化形式的絕對路徑，不含 `.` 或 `..` 段；在 Windows 上，以 `.exe` 結尾的磁碟機代號或 UNC 路徑
* **預設**: 無；設定 `policyHelper` 時為必需

```json managed-settings.json theme={null}
{
  "policyHelper": {
    "path": "/usr/local/bin/claude-policy"
  }
}
```

### `policyHelper.timeoutMs`

設定 Claude Code 在將執行視為失敗之前等待協助程式的時間。逾時的執行失敗方式與非零結束相同，因此在啟動時 Claude Code 拒絕啟動。

* **範圍**: [`Managed`](#scopes)。從 macOS plist、Windows HKLM 登錄或受管設定檔案讀取，無論 [`policyHelper`](#policyhelper) 在何處讀取。
* **類型**: 整數，毫秒，最小 `1000`
* **預設**: `10000`

```json managed-settings.json theme={null}
{
  "policyHelper": {
    "path": "/usr/local/bin/claude-policy",
    "timeoutMs": 5000
  }
}
```

### `policyHelper.refreshIntervalMs`

讓 Claude Code 在背景按間隔重新執行協助程式，以便原則變更到達執行中的工作階段。當重新整理成功時，其輸出會取代先前的受管設定，不需要重新啟動；當重新整理失敗時，Claude Code 會保持它已有的原則。

* **範圍**: [`Managed`](#scopes)。從 macOS plist、Windows HKLM 登錄或受管設定檔案讀取，無論 [`policyHelper`](#policyhelper) 在何處讀取。
* **類型**: 整數，毫秒：`0` 以停用重新整理，否則至少 `60000`
* **預設**: 未設定，因此 Claude Code 只在啟動時執行協助程式一次

此範例每五分鐘重新執行協助程式：

```json managed-settings.json theme={null}
{
  "policyHelper": {
    "path": "/usr/local/bin/claude-policy",
    "refreshIntervalMs": 300000
  }
}
```

### `wslInheritsWindowsSettings`

讓 WSL 上的 Claude Code 從 Windows 原則鏈讀取受管設定，HKLM 和 Windows 受管設定檔案優先於 `/etc/claude-code` 和下方的 HKCU。當鏈開啟時，Claude Code 只在 [HKLM 登錄值或 `C:\Program Files\ClaudeCode\` 資料夾中不存在 Windows 管理員文件](https://code.claude.com/docs/zh-TW/managed-settings#present-admin-documents)時讀取 `/etc/claude-code`。設定它以將您已在 Windows 上部署的原則擴充到同一機器上的 WSL 工作階段，使它們遵循與主機工作階段相同的規則。Claude Code 只在 HKLM 登錄金鑰或受管設定檔案或 `C:\Program Files\ClaudeCode\` 下的放入式中設定時接受它，兩者都需要 Windows 管理員才能寫入。

* **範圍**: [`Managed`](#scopes)。在管理員控制的 Windows 來源中。
* **類型**: 布林值
  * `true`: WSL 上的 Claude Code 從 Windows 原則鏈讀取受管設定，只在不存在 Windows 管理員文件時讀取 `/etc/claude-code`
  * `false`: WSL 只讀取 `/etc/claude-code`
* **預設**: `false`，因此 WSL 只讀取 `/etc/claude-code`

```json managed-settings.json theme={null}
{
  "wslInheritsWindowsSettings": true
}
```

一旦管理員來源開啟鏈，HKCU 原則只在 HKCU 也將金鑰設定為 `true` 時才加入 WSL 上的鏈。該副本不會自行開啟鏈。只包含此金鑰的 Windows 來源（設定為 `true` 或 `false`）不計為原則來源，因此較低優先順序的來源仍然提供原則。此金鑰對原生 Windows 無效。

Claude Code 讀取帶或不帶引號的 `true` 和 `false`，並將 `null` 讀取為移除金鑰。包含任何其他值的管理員控制 Windows 來源計為[存在的管理員文件](https://code.claude.com/docs/zh-TW/managed-settings.md#present-admin-documents)，鏈開啟：`/etc/claude-code` 和 HKCU 都不適用，啟動警告會命名金鑰。存在但無法讀取的 HKLM 值或 Windows 資料夾檔案也會防止 `/etc/claude-code` 套用，無論鏈是否開啟。需要 Claude Code v2.1.282 或更新版本。

## 全域設定

將這些金鑰儲存在 `~/.claude.json` 中，而不是在設定檔中。Claude Code 會忽略其他地方的設定。Claude Code 和 `/config` 會為您寫入大部分設定，您也可以手動編輯它們。

### `autoConnectIde`

當您從外部終端啟動 Claude Code 時，自動連接到執行中的 IDE。當您在 VS Code 或 JetBrains 終端外執行 Claude Code 時，會在 `/config` 中顯示為**自動連接到 IDE（外部終端）**。

* **範圍**：[`全域設定`](#scopes)
* **類型**：布林值
  * `true`：當您從外部終端啟動 Claude Code 時，它會自動連接到執行中的 IDE
  * `false`：Claude Code 不會從外部終端自動連接；在 VS Code 或 JetBrains 終端內，或使用 `--ide` 時，它仍會連接
* **預設值**：`false`
* **每個工作階段的覆寫**：[`CLAUDE_CODE_AUTO_CONNECT_IDE`](https://code.claude.com/docs/zh-TW/env-vars) 在任一方向上優先於此金鑰，持續一個工作階段

```json ~/.claude.json theme={null}
{
  "autoConnectIde": true
}
```

Claude Code 會忽略 `settings.json` 中的此金鑰。

### `autoInstallIdeExtension`

當您從外部終端機執行 [`/ide`](https://code.claude.com/docs/zh-TW/commands) 命令時，讓它在執行中的 VS Code、Cursor 或 Devin Desktop 中安裝 Claude Code IDE 擴充功能。Claude Code 在啟動時不會安裝此擴充功能。當您在 VS Code 或 JetBrains 終端機內執行 Claude Code 時，會在 `/config` 中顯示為 **Auto-install IDE extension**。

* **範圍**：[`全域設定`](#scopes)
* **類型**：布林值
  * `true`：`/ide` 會安裝擴充功能
  * `false`：`/ide` 不會安裝擴充功能
* **預設值**：`true`
* **每個工作階段的覆寫**：[`CLAUDE_CODE_IDE_SKIP_AUTO_INSTALL`](https://code.claude.com/docs/zh-TW/env-vars) 設定為 `1` 會跳過安裝一個工作階段，即使此金鑰為 `true`

```json ~/.claude.json theme={null}
{
  "autoInstallIdeExtension": false
}
```

Claude Code 會忽略 `settings.json` 中的此金鑰。

### `claudeInChromeDefaultEnabled`

啟動每個互動式 CLI 工作階段時，[Chrome 整合](https://code.claude.com/docs/zh-TW/chrome.md)預設開啟，無需每次都傳遞 `--chrome`。如果您執行 [`claude remote-control`](https://code.claude.com/docs/zh-TW/remote-control)，它為您的其中一個[專案](https://code.claude.com/docs/zh-TW/claude-projects.md)執行緒啟動的工作階段也會遵循此金鑰，除了在 `bypassPermissions` 模式中。在 Claude Code v2.1.287 或更新版本中，此金鑰也適用於 [VS Code 擴充功能](https://code.claude.com/docs/zh-TW/vs-code.md#automate-browser-tasks-with-chrome)中的工作階段：請參閱[預設啟用 Chrome](https://code.claude.com/docs/zh-TW/chrome.md#enable-chrome-by-default)。

執行 `/chrome` 並選擇 **Enabled by default** 會為您設定此設定鍵，回應[「Claude in Chrome extension detected」對話框](https://code.claude.com/docs/zh-TW/chrome.md#answer-the-startup-dialog)也會如此。會在 `/config` 中顯示為 **Claude in Chrome enabled by default**。

* **範圍**：[`全域設定`](#scopes)
* **類型**：布林值
  * `true`：當互動式 CLI 工作階段啟動時，Claude Code 會開啟 Chrome 整合，就像您傳遞 `--chrome` 時一樣。在 VS Code 擴充功能中，工作階段會在啟動時連接到瀏覽器
  * `false`：互動式 CLI 工作階段啟動時 Chrome 整合關閉，Claude Code 停止[提供設定它](https://code.claude.com/docs/zh-TW/chrome.md#install-the-extension-when-claude-asks)。傳遞 `--chrome` 以在一個互動式工作階段中開啟它。在 VS Code 擴充功能中，工作階段會在您輸入 `@browser` 時連接，與未設定此金鑰時相同
* **預設值**：未設定，因此 Chrome 整合關閉，Claude Code 仍可提供設定它
* **每個工作階段的覆寫**：`--chrome` 和 [`--no-chrome`](https://code.claude.com/docs/zh-TW/cli-reference) 在一個互動式工作階段中優先於此金鑰

```json ~/.claude.json theme={null}
{
  "claudeInChromeDefaultEnabled": true
}
```

Claude Code 會忽略 `settings.json` 中的此金鑰。

### `copyFullResponse`

讓 [`/copy`](https://code.claude.com/docs/zh-TW/commands) 每次都複製完整回應，無需顯示選擇器。在該選擇器中選擇**始終複製完整回應**會將此金鑰設定為 `true`。會在 `/config` 中顯示為**略過 /copy 選擇器**。

* **範圍**：[`全域設定`](#scopes)
* **類型**：布林值
  * `true`：`/copy` 複製完整回應，無需顯示選擇器
  * `false`：當回應包含程式碼區塊或引用區塊時，`/copy` 顯示一個選擇器，您可以在其中選擇一個區塊或完整回應
* **預設值**：`false`

```json ~/.claude.json theme={null}
{
  "copyFullResponse": true
}
```

Claude Code 會忽略 `settings.json` 中的此金鑰。

### `copyOnSelect`

當您在[全螢幕呈現](https://code.claude.com/docs/zh-TW/fullscreen.md#use-the-mouse)或[代理程式檢視](https://code.claude.com/docs/zh-TW/agent-view.md)中用滑鼠完成文字選取時，自動將文字複製到您的剪貼簿。當全螢幕呈現開啟時，會在 `/config` 中顯示為**選取時複製**。

* **範圍**：[`全域設定`](#scopes)
* **類型**：布林值
  * `true`：當您完成選取文字時，Claude Code 會將文字複製到您的剪貼簿
  * `false`：選取文字不會改變您的剪貼簿，您改為[使用快捷鍵複製選取項目](https://code.claude.com/docs/zh-TW/fullscreen.md#use-the-mouse)
* **預設值**：`true`

```json ~/.claude.json theme={null}
{
  "copyOnSelect": false
}
```

Claude Code 會忽略 `settings.json` 中的此金鑰。

### `defaultToAgentsView`

當您執行不帶引數的 `claude` 時，開啟[代理程式檢視](https://code.claude.com/docs/zh-TW/agent-view.md)而不是新對話。會在 `/config` 中顯示為**預設開啟代理程式檢視**，除非代理程式檢視[已關閉](#disableagentview)。

* **範圍**：[`全域設定`](#scopes)
* **類型**：布林值
  * `true`：不帶引數的 `claude` 開啟代理程式檢視，除非代理程式檢視[已關閉](#disableagentview)
  * `false`：不帶引數的 `claude` 啟動新對話
* **預設值**：`false`

```json ~/.claude.json theme={null}
{
  "defaultToAgentsView": true
}
```

Claude Code 會忽略 `settings.json` 中的此金鑰。

### `diffTool`

選擇 Claude Code 在連接 [VS Code](https://code.claude.com/docs/zh-TW/vs-code.md) 或 [JetBrains](https://code.claude.com/docs/zh-TW/jetbrains.md#features) IDE 時，顯示其提議的 `Edit` 或 `Write` 變更的差異的位置：`"auto"` 在 IDE 的差異檢視器中開啟它，`"terminal"` 將其保留在終端中。僅當 Claude Code 連接到 VS Code 或 JetBrains IDE 時，才會在 `/config` 中顯示為**差異工具**。

* **範圍**：[`全域設定`](#scopes)
* **類型**：字串，其中之一：
  * `"auto"`：當連接 VS Code 或 JetBrains IDE 時，Claude Code 在 IDE 的差異檢視器中開啟差異
  * `"terminal"`：Claude Code 將差異保留在終端中
* **預設值**：`"auto"`

```json ~/.claude.json theme={null}
{
  "diffTool": "terminal"
}
```

Claude Code 會忽略 `settings.json` 中的此金鑰。

### `externalEditorContext`

當您按下 `Ctrl+G` 時，Claude Code 會在您的[外部編輯器](https://code.claude.com/docs/zh-TW/interactive-mode.md#general-controls)中開啟您正在輸入的提示。啟用此金鑰時，編輯器緩衝區會以 Claude 的前一個回應作為 `#` 註解行開始，因此您可以在寫入時讀取它，Claude Code 會在您儲存時移除這些行。會在 `/config` 中顯示為**在外部編輯器中顯示最後回應**。

* **範圍**：[`全域設定`](#scopes)
* **類型**：布林值
  * `true`：編輯器緩衝區以 Claude 的前一個回應作為 `#` 註解行開始，Claude Code 會在您儲存時移除這些行
  * `false`：編輯器緩衝區僅以您的提示開啟
* **預設值**：`false`

```json ~/.claude.json theme={null}
{
  "externalEditorContext": true
}
```

啟用此功能時，Claude Code 開啟的緩衝區看起來像這樣，只有標記行下方的文字會作為您的提示發送：

```text theme={null}
# ─── Claude's last response (for reference; removed on save) ───
# I added the retry loop to fetchUser in src/api.ts and a test
# for the timeout case. Want me to wire the same retry into
# fetchOrders?
# ─── Write your reply below this line ──────────────────────────

Yes, and cap it at three attempts.
```

Claude Code 保留回應的最後 50 行，並用 `# … (earlier output truncated)` 標記截斷。

Claude Code 會忽略 `settings.json` 中的此金鑰。

### `leftArrowOpensAgents`

在空提示上按 `←` 以[背景化工作階段並開啟代理程式檢視](https://code.claude.com/docs/zh-TW/agent-view.md#switch-sessions-without-leaving-the-terminal)。將此金鑰設定為 `false` 以關閉快捷鍵。當代理程式檢視可用時，會在 `/config` 中顯示為\*\*← 開啟代理程式\*\*。

* **範圍**：[`全域設定`](#scopes)
* **類型**：布林值
  * `true`：在您在終端中啟動的工作階段中，在空提示上按 `←` 會背景化它並開啟代理程式檢視
  * `false`：Claude Code 關閉快捷鍵；在您[從代理程式檢視附加到的工作階段](https://code.claude.com/docs/zh-TW/agent-view.md#attach-to-a-session)中，在空提示上按 `←` 仍會分離
* **預設值**：`true`

```json ~/.claude.json theme={null}
{
  "leftArrowOpensAgents": false
}
```

Claude Code 會忽略 `settings.json` 中的此金鑰。

### `permissionExplainerEnabled`

> [!WARNING]
>
> 在 v2.1.257 中移除，連同 Bash 和 PowerShell 權限提示上的 `Ctrl+E` 命令說明一起移除。在目前版本中設定此項無效。

在 v2.1.256 及更早版本中，您可以在 Bash 或 PowerShell 權限提示上按 `Ctrl+E` 以查看模型產生的命令說明，並將此金鑰設定為 `false` 以關閉該快捷鍵。

* **範圍**：[`全域設定`](#scopes)。在 v2.1.256 及更早版本上。
* **類型**：布林值
* **預設值**：`true`

### `prStatusFooterEnabled`

在提示頁尾中顯示目前分支的開啟提取要求或合併要求的徽章，並帶有顯示其[狀態](https://code.claude.com/docs/zh-TW/interactive-mode.md#pr-review-status)的彩色底線。會在 `/config` 中顯示為**顯示 PR 狀態頁尾**。

* **範圍**：[`全域設定`](#scopes)
* **類型**：布林值
  * `true`：頁尾在 [PR 審查狀態](https://code.claude.com/docs/zh-TW/interactive-mode.md#pr-review-status)中的條件下顯示徽章
  * `false`：Claude Code 跳過頁尾的提取要求和合併要求檢查，不顯示該徽章。您[從代理程式檢視附加到的工作階段](https://code.claude.com/docs/zh-TW/agent-view.md#attach-to-a-session)仍可顯示[連結到它的](https://code.claude.com/docs/zh-TW/agent-view.md#pull-request-status)提取要求的純連結
* **預設值**：`true`

```json ~/.claude.json theme={null}
{
  "prStatusFooterEnabled": false
}
```

Claude Code 會忽略 `settings.json` 中的此金鑰。

### `teammateDefaultModel`

> [!WARNING]
>
> 在 v2.1.234 中移除，連同其 `/config` 列**預設隊友模型**一起移除。在目前版本中設定此項無效。

在 v2.1.233 及更早版本中，您將此金鑰設定為[代理程式團隊](https://code.claude.com/docs/zh-TW/agent-teams.md#specify-teammates-and-models)隊友的模型，您的提示未為其命名模型：一個別名，例如 `"sonnet"`，或 `null` 以遵循領導者的模型。如需 Claude Code 現在為此類隊友選擇的模型，請參閱[指定隊友和模型](https://code.claude.com/docs/zh-TW/agent-teams.md#specify-teammates-and-models)。

* **範圍**：[`全域設定`](#scopes)。在 v2.1.233 及更早版本上。
* **類型**：字串，模型別名或完整模型 ID，或 `null`
* **預設值**：未設定

## 另請參閱

* [設定權限](https://code.claude.com/docs/zh-TW/permissions.md)：規則語法、權限模式和工作區信任
* [環境變數](https://code.claude.com/docs/zh-TW/env-vars.md)：Claude Code 讀取的每個 `CLAUDE_*`、`ANTHROPIC_*` 和提供者變數
* [Claude 可用的工具](https://code.claude.com/docs/zh-TW/tools-reference.md)：內建工具及哪些需要核准
* [設定檔範例](https://code.claude.com/docs/zh-TW/settings-example.md)：個人檔案、團隊檔案和組織的受管檔案
* [設定受管設定](https://code.claude.com/docs/zh-TW/admin-setup.md)：組織如何決定要強制執行的內容
* [部署受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)：傳遞機制、受管層級內的優先順序和受管設定中的無效項目
* [偵錯您的設定](https://code.claude.com/docs/zh-TW/debug-your-config.md)：`claude doctor` 和設定錯誤對話框

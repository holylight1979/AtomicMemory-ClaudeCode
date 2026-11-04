# 04-administration 導讀（36 頁）

> 官方 Claude Code 文件「企業管理」夾導讀。原文在同夾 `<slug>.md`；機器索引見 [_keywords.json](_keywords.json)。
> 注意：`self-hosted-environments*`、`cloud-environments`、`auto-mode-classifier-billing`、`legal-and-compliance` 不在本夾（分別在 `05-configuration/`、`06-reference/`），本夾頁面只是對它們交叉連結。

## 速查：受管設定分層與可鎖鍵（出自 managed-settings / server-managed-settings / managed-mcp / claude-apps-gateway）

**1. 全域優先序**：受管層（managed）> 命令列/`--settings`/本機/專案/使用者。受管值使用者、專案、本機、`--settings` 都蓋不掉；例外是少數安全敏感鍵，較低層「更嚴格」的值仍算（如 `maxEffortLevel` 取最低、`enableArtifact: false`、`useAutoModeDuringPlan: false`、`attribution` 提交預告片退出）。受管 `model`、`autoCompactWindow` 只是預設，`--model`、`ANTHROPIC_MODEL`、`--autocompact` 仍可蓋。

**2. 受管層內的來源序（高到低）**：①遠端（claude.ai server-managed，或 Claude apps gateway 下發）②MDM/OS 原則（macOS plist `com.anthropic.claudecode`、Windows `HKLM\SOFTWARE\Policies\ClaudeCode` 的 `Settings` 值）③檔案 `managed-settings.d/*.json`（字母序）+ `managed-settings.json`（macOS `/Library/Application Support/ClaudeCode/`、Linux/WSL `/etc/claude-code/`、Windows `C:\Program Files\ClaudeCode\`）④HKCU（使用者可寫，只在無管理員文件時使用）。另有 `(parent process)`（嵌入主機）與 `(helper)`（`policyHelper`）兩種來源標籤。

**3. 預設 `first-wins`**：只用第一個「含政策鍵」的來源，其餘整個忽略（不是逐鍵合併）。`managedSourcesBehavior: "merge"`（v2.1.242+）才合併：列表聯集、鎖定取最嚴、限制型允許清單（`availableModels`、`allowedMcpServers`、`strictKnownMarketplaces`）整體取最高來源、`env` 逐變數合併、`modelPicker`/`permissions.defaultMode`/`apiKeyHelper` 只讀最高來源。

**4. 跨來源例外鍵（first-wins 下仍讀所有管理員來源）**：`sandbox.network.allowManagedDomainsOnly`、`sandbox.filesystem.allowManagedReadPathsOnly`、`allowManagedMcpServersOnly`、`deniedMcpServers`、`allowAllClaudeAiMcps`、`disableClaudeAiConnectors`、sandbox 二進位路徑與 `sandbox.filesystem.disabled`、`useAutoModeDuringPlan`/`syncClaudeAiSkills`/`syncClaudeAiPlugins`（任一來源 `false` 即關）、`maxEffortLevel`、`forceRemoteSettingsRefresh`、`env`（逐變數）。登入鍵（`forceLoginOrgUUID`、`forceLoginMethod` 的 claudeai/console、閘道登入鍵）要放在 MDM/檔案，不能靠 server-managed。

**5. 只有受管來源才讀的鍵（放使用者/專案檔無效）**：`allowManagedHooksOnly`、`allowManagedMcpServersOnly`、`allowManagedPermissionRulesOnly`、`sandbox.network.allowManagedDomainsOnly`、`sandbox.filesystem.allowManagedReadPathsOnly`、`allowAllClaudeAiMcps`、`allowedChannelPlugins`、`channelsEnabled`、`blockedMarketplaces`、`strictKnownMarketplaces`、`strictPluginOnlyCustomization`、`disableSideloadFlags`、`disableCommandPluginSources`、`forceRemoteSettingsRefresh`、`managedMcpServers`、`managedSourcesBehavior`、`parentSettingsBehavior`、`pluginSuggestionMarketplaces`、`pluginTrustMessage`、`policyHelper`、`wslInheritsWindowsSettings`。`allowManaged*Only` 鎖會讓 Claude Code 忽略開發者自己的同類項目（權限規則、hooks、MCP 允許清單、沙箱網域/讀路徑）；鎖與其管理的允許清單要放同一來源。

**6. 只能 MDM/檔案、不能 server-managed 的鍵**：`policyHelper`、`wslInheritsWindowsSettings`、閘道登入鍵（`forceLoginGatewayUrl`、`gatewayInternalNetworks`、`forceLoginMethod: "gateway"`）；`managed-mcp.json` 是獨立檔，也不能經 server-managed 下發。

**7. 檔案型 drop-in 合併**：`managed-settings.json` 先、`managed-settings.d/*.json` 依字母序後；單值後蓋前、列表聯集去重、巢狀區塊逐鍵合併、`fallbackModel`/`modelPicker`/`extraKnownMarketplaces`/`managedMcpServers` 同名後者整項取代。

**8. 閘道 `managed` 區塊（claude-apps-gateway-config）**：以 IdP `groups` 或 `email_domain` 比對；預設 first_match 再疊到 `match: {}` 基礎層（允許清單取代、拒絕清單與 hooks 聯集、`env` 淺合併）；`policy_mode: layered`（v2.1.316+）疊加所有符合者。閘道設定在受管層排名最高，但只送給 `/login` 登入的用戶端；Claude Desktop 內嵌工作階段要靠 `parentSettingsBehavior: "merge"` 與 `desktop` 鍵。

**9. 驗證工具**：`/status`（`Setting sources`、`Skipped sources`）、`claude doctor`（`Organization policy` 行、無效項目清單）、`claude --debug-file <path>` 搜 `Remote settings`、OTel 事件 `claude_code.managed_settings_resolved`。壞 JSON 的受管檔會拒絕啟動；單項 schema 錯誤逐項丟棄；`allowManagedPermissionRulesOnly` 等單一限制值鍵讀不懂時「失敗關閉」視為限制。

**10. 對本地 `~/.claude/settings.json` 的含意**：使用者層位於最低位階；若機器有任何管理員來源，使用者層的 `forceLoginMethod`/`forceLoginGatewayUrl` 會被忽略；`autoMode` 只從使用者/受管/`--settings` 讀、不從專案層讀；OTel 變數不從專案層讀；`env` 在受管層逐變數合併。

---

## Setup and access（設定與存取）

### 進階設定（`setup`）
- 檔案：[setup.md](setup.md)｜https://code.claude.com/docs/zh-TW/setup｜lastmod 2026-11-03｜33.5 KB
- 一句話：系統需求、各平台安裝、更新通道、版本固定與卸載。
- 何時讀：安裝失敗、要鎖版本或通道、要停自動更新時。
- 關鍵內容：
  - 需求：macOS 13+、Win10 1809+、Ubuntu 20.04+、Debian 10+、Alpine 3.19+、4GB RAM
  - 原生安裝 `curl -fsSL https://claude.ai/install.sh | bash`；Windows 用 `irm https://claude.ai/install.ps1 | iex`
  - 啟動器 `~/.local/bin/claude` 為符號連結，指向 `~/.local/share/claude/versions/`
  - `autoUpdatesChannel`：`latest`（預設）或 `stable`（約舊一週）
  - `minimumVersion` 只擋降級；受管層可強制；`requiredMinimumVersion`/`requiredMaximumVersion` 直接拒絕啟動
  - `DISABLE_AUTOUPDATER=1` 只停背景檢查；`DISABLE_UPDATES` 停所有更新路徑；`claude doctor` 看更新結果
  - Homebrew/WinGet/apt/dnf/apk 預設不自動更新；`CLAUDE_CODE_PACKAGE_MANAGER_AUTO_UPDATE=1` 可選擇加入
- 新名詞：`release channel` ＝ 更新通道，latest 即時、stable 延遲約一週並跳過重大迴歸版
- 記憶系統接點：`env` 鍵可放 `DISABLE_AUTOUPDATER`；`minimumVersion` 放受管層會壓過使用者/專案層（見設定分層）。

### 為您的組織設定 Claude Code（`admin-setup`）
- 檔案：[admin-setup.md](admin-setup.md)｜https://code.claude.com/docs/zh-TW/admin-setup｜lastmod 2026-11-03｜28.7 KB
- 一句話：管理員部署決策地圖：選 API 提供者、設定如何到裝置、要強制什麼、看用量、查資料處理。
- 何時讀：第一次替組織規劃 Claude Code 部署，想找哪個控制對應哪個設定鍵時。
- 關鍵內容：
  - 五個決策：API 提供者、設定傳遞、強制項目、用量可見性、資料處理
  - 四個受管來源由高到低：server-managed、plist/HKLM、檔案型 managed-settings.json、HKCU
  - 路徑：macOS `/Library/Application Support/ClaudeCode/`、Linux/WSL `/etc/claude-code/`、Windows `C:\Program Files\ClaudeCode\`
  - HKCU 使用者可寫，只當方便預設，不算強制通道
  - WSL 預設只讀 `/etc/claude-code`；`wslInheritsWindowsSettings: true` 才繼承 Windows 政策
  - 強制表：`permissions.*`、`allowManagedPermissionRulesOnly`、`sandbox.*`、`allowedMcpServers`、`strictPluginOnlyCustomization`、`allowManagedHooksOnly`、`forceLoginMethod`、`allowedProviders`、`availableModels`、`maxEffortLevel`、`minimumVersion`
  - 受管 CLAUDE.md 為給 Claude 的指引，非用戶端強制規則
- 新名詞：`managed policy CLAUDE.md` ＝ 組織層 CLAUDE.md，只是指引、不被程式強制；`customization lockdown` ＝ `strictPluginOnlyCustomization`：skills/agents/hooks/MCP 只能來自外掛或受管設定
- 記憶系統接點：表列出能把 hooks、MCP、skills 鎖成「只准受管來源」的鍵（`allowManagedHooksOnly`、`strictPluginOnlyCustomization`），會改變本機 hooks/skills 是否載入。

### 驗證（`authentication`）
- 檔案：[authentication.md](authentication.md)｜https://code.claude.com/docs/zh-TW/authentication｜lastmod 2026-11-03｜35.3 KB
- 一句話：登入方式、團隊認證、憑證儲存與優先順序、限制登入組織。
- 何時讀：要設定 SSO/Console/雲端登入、除錯誰的憑證生效、鎖定登入組織時。
- 關鍵內容：
  - 登入類型：Pro/Max/Ultra、Teams/Enterprise、Console、雲端提供者、Cloud gateway
  - 認證優先序：雲端提供者 > `ANTHROPIC_AUTH_TOKEN` > `ANTHROPIC_API_KEY` > `apiKeyHelper` > `CLAUDE_CODE_OAUTH_TOKEN` > Anthropic 設定檔 > `/login` OAuth
  - 憑證存放：macOS Keychain；Linux/Windows `~/.claude/.credentials.json`（0600）；`CLAUDE_CONFIG_DIR` 會改位置
  - `forceLoginMethod`（`claudeai`/`console`/`gateway`）與 `forceLoginOrgUUID`（可為陣列）限制登入
  - 設了 force 鍵後，`ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN`/`apiKeyHelper` 啟動時被拒
  - `allowedProviders` 限制機器可用的 API 供應商（如 `["anthropic","bedrock"]`）
  - `claude setup-token` 產一年期 token 供 CI（`CLAUDE_CODE_OAUTH_TOKEN`），僅能做模型請求
  - `apiKeyHelper` 超過 10 秒顯示慢速提示；連失敗 3 次報錯
- 新名詞：`apiKeyHelper` ＝ 回傳 API 金鑰的 shell 腳本設定，用於輪替/保管庫憑證；`Workload Identity Federation` ＝ 用外部身分換短期憑證的免金鑰認證
- 記憶系統接點：認證來源優先序與 `CLAUDE_CONFIG_DIR` 決定憑證檔位置；與本地 settings 的 `env` 區塊互動。

### 設定自動模式（`auto-mode-config`）
- 檔案：[auto-mode-config.md](auto-mode-config.md)｜https://code.claude.com/docs/zh-TW/auto-mode-config｜lastmod 2026-11-02｜33.3 KB
- 一句話：設定自動模式分類器：受信任基礎設施、覆蓋規則、檢視拒絕。
- 何時讀：自動模式老是擋你信任的 repo/網域，或要調整分類器規則時。
- 關鍵內容：
  - `autoMode.environment` 宣告受信任 repo/bucket/網域；預設只信任工作目錄與目前 repo 遠端
  - `autoMode` 只從 `~/.claude/settings.json`、受管設定、`--settings`/SDK 讀；不讀專案 `.claude/settings*.json`
  - 各範圍項目合併；開發者能擴充但不能移除受管提供的項目
  - `hard_deny`（無條件）> `soft_deny`（使用者意圖可清）> `allow`（例外）> 明確使用者意圖
  - 字串 `"$defaults"` 可在陣列中保留內建規則
  - `permissions.ask` 在分類器前評估，可在自動模式下強制提示（如 `Bash(git push *)`）
  - `autoMode.classifyAllShell: true` 讓每個 shell 命令都過分類器；`claude auto-mode defaults` 印內建規則
  - `/auto-mode-setup` 產生 environment 草稿；受管 `permissions.deny` 在分類器前阻擋
- 新名詞：`auto mode classifier` ＝ 替你審查工具呼叫並擋掉不安全操作的另一個模型；`hard_deny / soft_deny` ＝ 硬阻擋（不可覆蓋）與軟阻擋（使用者意圖或 allow 可放行）
- 記憶系統接點：分類器讀與 Claude 相同的 CLAUDE.md；專案層不讀 autoMode 是刻意防止 repo 注入規則。

### 部署受管設定（`managed-settings`）
- 檔案：[managed-settings.md](managed-settings.md)｜https://code.claude.com/docs/zh-TW/managed-settings｜lastmod 2026-11-03｜62.9 KB
- 一句話：部署受管設定：四種傳遞機制、來源優先序、可鎖鍵、驗證方式。
- 何時讀：要在機隊強制政策，或查「為什麼某設定沒生效」時，這是核心頁。
- 關鍵內容：
  - 受管層位於所有層之上；使用者/專案/本機/`--settings` 都蓋不掉，僅少數安全例外（較嚴的低層值仍算）
  - 來源高到低：①遠端(server-managed 或 gateway) ②MDM(plist/HKLM) ③檔案 `managed-settings.d/*.json`+`managed-settings.json` ④HKCU
  - 預設 `managedSourcesBehavior: "first-wins"`：只用第一個含政策鍵的來源，其餘忽略；`"merge"`（v2.1.242+）才全部合併
  - merge 規則：列表聯集、鎖定取最嚴、限制型允許清單整體取最高來源、`env` 逐變數合併、`model` 等取最高來源
  - drop-in：`managed-settings.json` 先合併，再依字母序合併 `managed-settings.d/*.json`；單值後蓋前、列表去重聯集、巢狀逐鍵合併
  - 跨來源讀取的鍵（即使 first-wins 也從所有管理員來源讀）：`sandbox.network.allowManagedDomainsOnly`、`sandbox.filesystem.allowManagedReadPathsOnly`、`allowManagedMcpServersOnly`、`deniedMcpServers`、`allowAllClaudeAiMcps`、`maxEffortLevel`(取最低)、`forceRemoteSettingsRefresh`、`env`
  - 只有受管來源讀的鍵：`allowManagedHooksOnly`、`allowManagedPermissionRulesOnly`、`strictKnownMarketplaces`、`blockedMarketplaces`、`strictPluginOnlyCustomization`、`disableSideloadFlags`、`managedMcpServers`、`policyHelper`、`parentSettingsBehavior`、`channelsEnabled`
  - 讀取時機：MDM/檔案啟動讀、MDM 每 30 分檢查、檔案變更重載；`model`/`autoCompactWindow` 受管值只是預設，`--model` 仍可蓋
  - 驗證：`/status` 的 `Setting sources` 與 `Skipped sources`；`claude doctor`；壞 JSON 會拒絕啟動，單項無效則逐項丟棄並警告
  - 失敗關閉鍵：`allowManagedPermissionRulesOnly`、`disableAutoMode` 等讀不懂時視為限制值
- 新名詞：`first-wins / merge` ＝ 多個受管來源並存時的處理：只取最高一個，或全部合併；`policy key` ＝ 除 `wslInheritsWindowsSettings`、`managedSourcesBehavior` 外的任何設定鍵，才算該來源有提供政策；`parent settings` ＝ 嵌入主機（Desktop/IDE/SDK 用 `managedSettings`）傳進來的設定；有管理員來源時預設被忽略；`policyHelper` ＝ 啟動時執行並輸出 `managedSettings` 物件的可執行檔，輸出取代其他受管來源
- 記憶系統接點：設定分層：受管層 > 命令列/本機/專案/使用者；受管層內有自己的來源序。本機 `~/.claude/settings.json` 的 hooks/permissions/env 在 `allowManaged*Only` 下會被忽略；`ConfigChange` hook 可記錄 managed-settings.json 的本機編輯。

### 設定伺服器管理的設定（`server-managed-settings`）
- 檔案：[server-managed-settings.md](server-managed-settings.md)｜https://code.claude.com/docs/zh-TW/server-managed-settings｜lastmod 2026-11-04｜47.6 KB
- 一句話：透過 claude.ai 管理主控台集中下發設定（Teams/Enterprise），免 MDM。
- 何時讀：沒有 MDM、想從網頁後台統一管理，或要查擷取/快取/核准行為時。
- 關鍵內容：
  - 位置：claude.ai **Organization settings > Claude Code > Managed settings**；需 Teams/Enterprise 與 Owner/Primary Owner 角色；需連 `api.anthropic.com`
  - 與端點受管同在最高層；受管層內預設先檢查 server-managed，再端點來源（first-wins）
  - 限制：全組織統一、尚不支援依群組；不能下發 `managed-mcp.json`，改用 `allowedMcpServers`/`managedMcpServers`；`policyHelper`、`wslInheritsWindowsSettings` 與閘道登入鍵不被接受
  - 擷取：啟動時拉、執行中每小時輪詢；首次無快取最多等 5 秒；快取在 `~/.claude/remote-settings.json`
  - 快取啟動時暫緩 proxy/TLS/API 路由/憑證類 `env`（`HTTPS_PROXY`、`ANTHROPIC_BASE_URL`、`CLAUDE_CONFIG_DIR` 等）直到伺服器確認 payload
  - `forceRemoteSettingsRefresh: true`：擷取失敗就退出（失敗即關閉），會自我延續到本機快取
  - 需使用者核准的項目：shell 命令類設定(`apiKeyHelper`/`statusLine`)、sandbox 二進位與網路設定、危險 `env`、任何 hook；非互動(`-p`/SDK)只在該次執行套用
  - 略過條件：設了 `CLAUDE_CODE_USE_*` 或非預設 `ANTHROPIC_BASE_URL`、用 Console API key、Cowork 工作階段
  - 定位是用戶端控制而非安全邊界：使用者可改快取、跑舊版或改二進位
- 新名詞：`server-managed settings` ＝ Anthropic 伺服器（或閘道）下發的受管設定，啟動拉取並每小時刷新；`security approval dialog` ＝ 下發含 hook/shell 命令等高風險設定時要求使用者明確同意的對話框
- 記憶系統接點：下發的 hooks 需使用者核准才執行；`ConfigChange` hook 可記錄設定到達；快取檔 `~/.claude/remote-settings.json` 位於同一 `.claude` 目錄。

### 控制組織的 MCP 伺服器存取（`managed-mcp`）
- 檔案：[managed-mcp.md](managed-mcp.md)｜https://code.claude.com/docs/zh-TW/managed-mcp｜lastmod 2026-10-28｜46.2 KB
- 一句話：控制組織可用的 MCP 伺服器：固定集、提供集、允許/拒絕清單。
- 何時讀：要限制或預先配置員工能連的 MCP 伺服器時。
- 關鍵內容：
  - 八種模式：停用/固定部署/提供的伺服器/已核准目錄/僅外掛伺服器/軟性允許清單/僅拒絕清單/無限制
  - `managed-mcp.json`（系統路徑）獨佔控制：只載入該檔、`managedMcpServers`、同行程 SDK 伺服器；擋 `--mcp-config` 與外掛伺服器，不能經 server-managed 下發
  - `--strict-mcp-config` 與 managed-mcp.json 並存會啟動即退出
  - `managedMcpServers`（受管設定，v2.1.259+）：給每人遠端 HTTP/SSE 伺服器，使用者仍可加自己的；標頭內容使用者可讀
  - `allowedMcpServers`/`deniedMcpServers` 項目可比對 `serverName`/`serverCommand`/`serverUrl`
  - 評估順序：合併清單 → 檢查拒絕（無可覆蓋）→ 檢查允許；未設 allowedMcpServers 則全載入
  - `allowManagedMcpServersOnly: true` 才讓允許清單只認受管；拒絕清單永遠跨範圍合併
  - `allowClaudeInChromeWithManagedMcp`、`allowAllClaudeAiMcps` 讓 Chrome/claude.ai 連接器與固定集並存
  - `OTEL_LOG_TOOL_DETAILS=1` 可在遙測看 MCP 呼叫
- 新名詞：`exclusive control` ＝ 部署 `managed-mcp.json` 後，只有受管集合能用，使用者無法新增
- 記憶系統接點：MCP 伺服器來源有多範圍（使用者/專案/本機/外掛/claude.ai）；`.mcp.json` 專案伺服器受允許/拒絕清單過濾。


## Deployment（部署）

### 企業部署概述（`third-party-integrations`）
- 檔案：[third-party-integrations.md](third-party-integrations.md)｜https://code.claude.com/docs/zh-TW/third-party-integrations｜lastmod 2026-10-06｜11.2 KB
- 一句話：企業部署總覽：Teams/Enterprise、Console、Bedrock、Vertex、Foundry 比較與最佳實踐。
- 何時讀：在直連 Anthropic 與各雲端之間做選擇、設計代理/閘道架構時。
- 關鍵內容：
  - 預設建議 Claude for Teams/Enterprise；Console 為 API 優先；三大雲繼承各自合規與計費
  - 代理與 LLM 閘道可併用：公司代理走 `HTTPS_PROXY`，閘道處理認證與路由
  - CMEK 不適用於走 LLM 閘道或自訂 `ANTHROPIC_BASE_URL` 的流量
  - 雲端提供者建議釘選模型版本（`ANTHROPIC_DEFAULT_*_MODEL`）
  - `allowedProviders` 可只允許某部署選項（如 `["bedrock"]`）
  - 最佳實踐：投資 CLAUDE.md 文件、一鍵安裝、引導式起步、集中 MCP 設定
- 新名詞：無
- 記憶系統接點：組織層 CLAUDE.md 與 `.mcp.json` 簽入是官方建議的組織知識分發方式。

### Amazon Bedrock 上的 Claude Code（`amazon-bedrock`）
- 檔案：[amazon-bedrock.md](amazon-bedrock.md)｜https://code.claude.com/docs/zh-TW/amazon-bedrock｜lastmod 2026-11-03｜44.8 KB
- 一句話：在 Amazon Bedrock 上設定 Claude Code：登入、AWS 憑證、模型釘選、IAM、Mantle。
- 何時讀：公司走 Bedrock、要處理 SSO/區域/模型 ID/IAM 時。
- 關鍵內容：
  - 啟用：`CLAUDE_CODE_USE_BEDROCK=1`、`AWS_REGION`；登入精靈選 3rd-party platform → Amazon Bedrock
  - 憑證：`aws configure`、環境變數、SSO 設定檔、Bedrock API 金鑰；`awsAuthRefresh` 於過期才執行（先 STS GetCallerIdentity 確認）、`awsCredentialExport`
  - 釘選：`ANTHROPIC_DEFAULT_OPUS/SONNET/HAIKU_MODEL`；未釘則別名會跟版本漂移並按 Opus 價計
  - 跨區推論前綴 `us.`/`eu.`/`us-gov.` 等；可映射到應用程式推論設定檔 ARN
  - 啟動模型檢查：驗證帳號可呼叫；拒絕結果在本機記住一天；受管 `env` 內的釘選不檢查
  - IAM 需 `bedrock:InvokeModel`、`InvokeModelWithResponseStream`、`CountTokens`
  - Mantle 端點：`CLAUDE_CODE_USE_MANTLE=1`，可與 Invoke API 並行；`ANTHROPIC_BEDROCK_BASE_URL` 走閘道
  - 支援 Guardrails、服務層級、1M token context
- 新名詞：`Mantle` ＝ Bedrock 上以原生 Anthropic API 形狀提供 Claude 的端點；`inference profile` ＝ Bedrock 的跨區域/應用程式推論設定檔，決定實際呼叫的模型 ID
- 記憶系統接點：受管 `env` 內的模型釘選不觸發更新提示（v2.1.314 前有 bug）；與設定分層的 `env` 區塊相關。

### Google Cloud 的 Agent Platform 上的 Claude Code（`google-vertex-ai`）
- 檔案：[google-vertex-ai.md](google-vertex-ai.md)｜https://code.claude.com/docs/zh-TW/google-vertex-ai｜lastmod 2026-11-03｜21.3 KB
- 一句話：在 Google Cloud Agent Platform（原 Vertex AI）上設定 Claude Code。
- 何時讀：公司走 GCP、要設定區域、專案 ID、模型存取與 IAM 時。
- 關鍵內容：
  - 啟用：`CLAUDE_CODE_USE_VERTEX=1`、`CLOUD_ML_REGION`（預設回退 `us-east5`，可設 `global`）、`ANTHROPIC_VERTEX_PROJECT_ID`
  - 請求一律送往 `ANTHROPIC_VERTEX_PROJECT_ID` 指定的專案，不看 `GCLOUD_PROJECT` 等
  - 不支援全域端點的模型可用 `VERTEX_REGION_CLAUDE_*` 覆寫區域
  - `ANTHROPIC_VERTEX_BASE_URL` 可指向閘道
  - 需啟用 Agent Platform API、向 Model Garden 申請模型存取
  - 釘選：`ANTHROPIC_DEFAULT_*_MODEL`；模型 ID 形如 `claude-haiku-4-5@20251001`
  - 具備啟動模型檢查（與 Bedrock 同機制）與 1M context
- 新名詞：無
- 記憶系統接點：無。

### Microsoft Foundry 上的 Claude Code（`microsoft-foundry`）
- 檔案：[microsoft-foundry.md](microsoft-foundry.md)｜https://code.claude.com/docs/zh-TW/microsoft-foundry｜lastmod 2026-10-14｜9.8 KB
- 一句話：在 Microsoft Foundry 上設定 Claude Code：資源、認證、RBAC。
- 何時讀：公司走 Azure/Foundry 時。
- 關鍵內容：
  - 啟用：`CLAUDE_CODE_USE_FOUNDRY=1`、`ANTHROPIC_FOUNDRY_RESOURCE`（只填資源名稱）或 `ANTHROPIC_FOUNDRY_BASE_URL`
  - 認證三選一：`ANTHROPIC_FOUNDRY_API_KEY`、Entra ID（Azure SDK 預設憑證鏈，兩個變數都不設）、`ANTHROPIC_FOUNDRY_AUTH_TOKEN`（優先）
  - 模型釘選用 `ANTHROPIC_DEFAULT_*_MODEL`；需 Azure RBAC 角色
  - 有 1M token context 與疑難排解章節
- 新名詞：無
- 記憶系統接點：無。

### AWS 上的 Claude Platform 上的 Claude Code（`claude-platform-on-aws`）
- 檔案：[claude-platform-on-aws.md](claude-platform-on-aws.md)｜https://code.claude.com/docs/zh-TW/claude-platform-on-aws｜lastmod 2026-10-28｜11.8 KB
- 一句話：經 AWS 認證/計費使用 Anthropic 營運的 Claude API（Claude Platform on AWS）。
- 何時讀：用 AWS Marketplace 購買、但要走 Anthropic API 功能集時。
- 關鍵內容：
  - 啟用：`CLAUDE_CODE_USE_ANTHROPIC_AWS=1`、`ANTHROPIC_AWS_WORKSPACE_ID`（必填，帶 `anthropic-workspace-id` 標頭）、`AWS_REGION`
  - 基礎 URL 自動算為 `https://aws-external-anthropic.{region}.api.aws`
  - 認證：SigV4 AWS 憑證或工作區 API 金鑰；Bedrock/Foundry 優先序較高
  - 模型 ID 與直連 API 相同；別名 `fable/opus/sonnet/haiku` 建議用 `ANTHROPIC_DEFAULT_*_MODEL` 釘選
  - `ENABLE_PROMPT_CACHING_1H=1` 請求 1 小時快取 TTL（預設 5 分鐘）
  - 支援 Agent SDK 與公司代理
- 新名詞：`workspace ID` ＝ Claude Platform on AWS 的工作區識別，每次請求必帶
- 記憶系統接點：無。

### 在公司啟動程式後面執行 Claude Code（`corporate-launcher`）
- 檔案：[corporate-launcher.md](corporate-launcher.md)｜https://code.claude.com/docs/zh-TW/corporate-launcher｜lastmod 2026-10-28｜14.7 KB
- 一句話：用 `CLAUDE_CODE_PROCESS_WRAPPER` 讓 Claude Code 自行啟動的所有程序都經公司啟動器。
- 何時讀：公司規定所有程序必須經沙箱/網路控制/憑證注入啟動器時。
- 關鍵內容：
  - `CLAUDE_CODE_PROCESS_WRAPPER` 或 `processWrapper` 設定（v2.1.208+）；Windows 上被忽略
  - 涵蓋：背景服務、agent view 工作階段、更新後重啟、Remote Control(v2.1.210+)、agent teams 的 tmux/iTerm2 窗格
  - 不涵蓋：自己在終端啟動的 `claude`、`claude-cli://` 深層連結、Claude in Chrome 原生訊息主機
  - 合約：結尾 `exec "$@"`、不改引數、傳遞全部繼承環境、約 3 秒內 exec、不讀 stdin、不寫 stdout、用絕對路徑
  - 值格式：絕對路徑，可接空白分隔引數，或 `[` 開頭的 JSON 字串陣列；不支援 shell 語法
  - 啟動器無法執行時拒絕啟動程序；與 `CLAUDE_CODE_SHELL_PREFIX` 不同（後者包裝命令）
- 新名詞：`process wrapper / launcher` ＝ 包住 Claude Code 自己衍生程序的公司啟動腳本
- 記憶系統接點：背景服務/子程序會被包裝；hooks 與 MCP 子程序是否經此包裝以 `CLAUDE_CODE_SHELL_PREFIX` 區分。

### 開發容器（`devcontainer`）
- 檔案：[devcontainer.md](devcontainer.md)｜https://code.claude.com/docs/zh-TW/devcontainer｜lastmod 2026-10-28｜17.7 KB
- 一句話：在 dev container 內跑 Claude Code：安裝 Feature、保留認證、套組織政策、出口防火牆。
- 何時讀：要給團隊一致隔離環境，或想在容器裡無人值守跑時。
- 關鍵內容：
  - 用 Claude Code Dev Container Feature 安裝（永遠最新版；要固定版本改 Dockerfile `npm install -g`）
  - 保留認證：`~/.claude` 掛命名磁碟區並設 `CLAUDE_CONFIG_DIR` 同路徑
  - 組織政策：Dockerfile 複製 `managed-settings.json` 到 `/etc/claude-code/`；但 repo 內可被改，需不可繞過則用 server-managed
  - `containerEnv` 可設 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`、`DISABLE_AUTOUPDATER`
  - 參考容器 `init-firewall.sh` 限制出站只到允許網域
  - 非 root 容器可配 `--dangerously-skip-permissions`，但惡意專案仍可讀容器內憑證；勿掛 `~/.ssh`/雲端憑證
- 新名詞：`dev container` ＝ 用 devcontainer.json 定義、可在本機或 Codespaces 重現的容器開發環境
- 記憶系統接點：`CLAUDE_CONFIG_DIR` 決定 `.claude` 位置，容器內可獨立於主機記憶/設定。

### 功能可用性（`feature-availability`）
- 檔案：[feature-availability.md](feature-availability.md)｜https://code.claude.com/docs/zh-TW/feature-availability｜lastmod 2026-10-30｜25.7 KB
- 一句話：各功能在訂閱方案與各雲端提供者的可用性比較。
- 何時讀：查「這功能在 Bedrock/Console/Team 上有沒有」時。
- 關鍵內容：
  - 本機執行的 CLI 功能在所有提供者行為相同（subagent、hooks、skills、CLAUDE.md、外掛、MCP、沙箱、OTel、受管設定檔）
  - claude.ai 連接器只在 claude.ai 訂閱為有效認證時載入
  - 雲端工作階段、Routines、Code Review、Remote Control 等需 claude.ai 帳戶
  - `/design-sync`、`/import` 在 Bedrock/Vertex/Foundry/AWS 平台不可用；`/voice` 需 claude.ai
  - 方案表：Code Review、分析儀表板、server-managed、SSO 需 Team+；SCIM/Compliance API/ZDR 僅 Enterprise
  - Remote Control、Channels 在 Team/Enterprise 需管理員啟用；Computer use 僅 Pro/Max/Ultra
  - Ultra 為 Max 20x 新名，功能與 Max 相同
- 新名詞：無
- 記憶系統接點：subagent、hooks、skills、MCP 在所有提供者皆可用；可確認跨環境行為一致。

### 企業網路設定（`network-config`）
- 檔案：[network-config.md](network-config.md)｜https://code.claude.com/docs/zh-TW/network-config｜lastmod 2026-11-03｜33.9 KB
- 一句話：企業網路：代理、CA、mTLS、串流監視狗、必須放行的網址。
- 何時讀：公司有 proxy/TLS 檢查、要設防火牆允許清單或串流逾時時。
- 關鍵內容：
  - `HTTPS_PROXY`/`HTTP_PROXY`/`NO_PROXY`；不支援 SOCKS；localhost WebSocket 不走代理
  - CA：預設信任 Mozilla 內建+OS 存放區；`CLAUDE_CODE_CERT_STORE=bundled,system`；`NODE_EXTRA_CA_CERTS` 加自訂 CA
  - mTLS：`CLAUDE_CODE_CLIENT_CERT`/`CLAUDE_CODE_CLIENT_KEY`
  - 串流監視狗四計時器：首位元組期限、事件層級、位元組層級、本體閒置(5 分)；調整 `CLAUDE_STREAM_IDLE_TIMEOUT_MS`、`API_TIMEOUT_MS`
  - 必放行：`api.anthropic.com`、`claude.ai`、`platform.claude.com`、`sso.claude.com`、`mcp-proxy.anthropic.com`、`downloads.claude.ai`、`github.com`、`registry.npmjs.org`
  - Datadog 兩個進入主機只攜帶選用遙測，`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` 可關
  - 背景 agent 的網路變數要寫在設定而非 shell
- 新名詞：`byte watchdog` ＝ 網路層沒位元組到達（含 SSE ping）就中止串流的計時器
- 記憶系統接點：網路變數可放 settings `env`；背景 agent 不繼承 shell 環境。


## Gateways（閘道）

### 透過閘道執行 Claude Code（`gateways`）
- 檔案：[gateways.md](gateways.md)｜https://code.claude.com/docs/zh-TW/gateways｜lastmod 2026-10-20｜8.9 KB
- 一句話：閘道概觀：架構、選 Claude apps gateway 或自有 LLM 閘道、與訂閱互動。
- 何時讀：評估是否要在 Claude Code 與模型提供者之間加閘道時。
- 關鍵內容：
  - 兩種認證：開發者憑證（閘道簽發）與提供者憑證（閘道持有）
  - Claude apps gateway 內建於 `claude` 二進位，與每版同測，自動轉發 `anthropic-beta` 與請求欄位
  - 閘道登入是瀏覽器 SSO，無服務 token 流程，CI 不能用
  - 經閘道認證時用量按 API 費率計到組織提供者帳戶，不扣 claude.ai 訂閱
  - 僅設 `ANTHROPIC_BASE_URL` 而無閘道認證時，仍用已存 claude.ai 登入（計訂閱）
  - 模型選擇、遙測等需另外設定
- 新名詞：`gateway` ＝ 組織自管、位於 Claude Code 與模型提供者之間的代理
- 記憶系統接點：無。

### 其他 LLM 閘道（`llm-gateway`）
- 檔案：[llm-gateway.md](llm-gateway.md)｜https://code.claude.com/docs/zh-TW/llm-gateway｜lastmod 2026-10-01｜7.0 KB
- 一句話：使用既有 LLM 閘道的入口：能提供什麼、推出順序、三個子頁導覽。
- 何時讀：組織已有 LiteLLM 類閘道，想知道從哪頁讀起時。
- 關鍵內容：
  - 任何公開支援 API 格式的閘道都可用；Anthropic 不背書也不審計第三方閘道
  - 閘道提供：憑證隔離、用量追蹤、成本控制、審計日誌、提供者切換
  - 權衡：閘道成為你要維護的基礎設施，需追隨 Claude Code 新功能
  - 推出四步：部署閘道→發開發者憑證→用受管設定分發→開發者驗證
  - 導覽：開發者讀 connect、管理員讀 rollout、閘道廠商讀 protocol
- 新名詞：無
- 記憶系統接點：無。

### 將 Claude Code 連接到 LLM 閘道（`llm-gateway-connect`）
- 檔案：[llm-gateway-connect.md](llm-gateway-connect.md)｜https://code.claude.com/docs/zh-TW/llm-gateway-connect｜lastmod 2026-10-27｜43.2 KB
- 一句話：開發者把 Claude Code 連到既有 LLM 閘道：檢查、設定、各介面、疑難。
- 何時讀：你是開發者，需要自己設定或驗證閘道連線時。
- 關鍵內容：
  - 檢查：`/status` 看 `Anthropic base URL` 與 `Auth token`/`API key`；出現 claude.ai `Login method` 表示憑證未分發
  - 變數：`ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN`(Authorization: Bearer)/`ANTHROPIC_API_KEY`(x-api-key)/`apiKeyHelper`(兩者)
  - 閘道憑證變數優先於已存 claude.ai 登入；取消變數即回到登入
  - 各介面：VS Code、桌面應用程式、GitHub Actions、Agent SDK、Slack/雲端/Remote Control 各有設法
  - `ANTHROPIC_CUSTOM_HEADERS` 加標頭；`CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY` 把閘道模型加進 `/model`
  - `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` 關閘道外流量，但會停自動更新、快速模式檢查
  - 路由雲端：`ANTHROPIC_BEDROCK_BASE_URL`/`ANTHROPIC_VERTEX_BASE_URL`/`ANTHROPIC_FOUNDRY_BASE_URL`/`ANTHROPIC_AWS_BASE_URL`
- 新名詞：無
- 記憶系統接點：`apiKeyHelper` 與 `env` 設定位置影響閘道憑證來源。

### Claude Code 閘道相容性指南（`llm-gateway-protocol`）
- 檔案：[llm-gateway-protocol.md](llm-gateway-protocol.md)｜https://code.claude.com/docs/zh-TW/llm-gateway-protocol｜lastmod 2026-11-03｜49.7 KB
- 一句話：閘道相容性規格：端點、標頭、功能傳遞、模型發現。
- 何時讀：要寫或調整閘道，使其不破壞 Claude Code 新功能時。
- 關鍵內容：
  - 三種格式：Anthropic Messages(`/v1/messages`)、Bedrock InvokeModel、Vertex rawPredict；Foundry/AWS 平台用 Messages 格式
  - 選擇者：`ANTHROPIC_BASE_URL` / `ANTHROPIC_BEDROCK_BASE_URL`+`CLAUDE_CODE_USE_BEDROCK` / `ANTHROPIC_VERTEX_BASE_URL`+`CLAUDE_CODE_USE_VERTEX`
  - 必須原樣轉發 `anthropic-version` 與 `anthropic-beta`，勿把個別 beta 值列白名單
  - Claude Code 附 `x-claude-code-session-id`、`x-claude-code-agent-id`、`x-claude-code-parent-agent-id` 標頭
  - gateway hint headers（v2.1.273+）由 `CLAUDE_CODE_GATEWAY_HINT_HEADERS` 開啟
  - token 計數端點是唯一可選端點；`HEAD /api/hello` 為預熱探測
  - 被拒絕 beta 值會重試並暫時排除；`CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS` 可停預發佈功能
  - 模型發現：`/v1/models` 填入選擇器
- 新名詞：`gateway hint headers` ＝ Claude Code 附的路由/排程提示標頭，供閘道分類請求
- 記憶系統接點：請求標頭帶 session/agent id，可讓外部系統聚合同一 session 的呼叫。

### 為您的組織推出 LLM 閘道（`llm-gateway-rollout`）
- 檔案：[llm-gateway-rollout.md](llm-gateway-rollout.md)｜https://code.claude.com/docs/zh-TW/llm-gateway-rollout｜lastmod 2026-11-02｜28.3 KB
- 一句話：管理員推出 LLM 閘道：需求、發憑證、測試、分發設定、維護。
- 何時讀：要把閘道分發給全公司開發者時。
- 關鍵內容：
  - 先確認閘道轉發 beta 標頭/欄位、路由你的模型，再發每位開發者憑證
  - 分發變數：`ANTHROPIC_BASE_URL`（必）、`apiKeyHelper`/token、`ANTHROPIC_CUSTOM_HEADERS`、`CLAUDE_CODE_GATEWAY_HINT_HEADERS`、`CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY`
  - 經受管設定 `env` 傳遞的 `ANTHROPIC_BASE_URL` 被強制，使用者 shell 蓋不掉
  - 勿同時下發 `forceLoginMethod`/`forceLoginOrgUUID`/`forceLoginGatewayUrl` 與閘道認證
  - server-managed 需直連 `api.anthropic.com`，到不了閘道路由的工作階段；桌面應用程式另需 MDM 部署其第三方推理設定
  - 透過閘道的工作階段不符合 HIPAA 設定資格
  - 維護：新 Claude Code 版加 beta 值→開發者見 `400`；新模型→`404`；上游憑證過期→`401`；客戶端重試 429 最多 10 次
- 新名詞：無
- 記憶系統接點：受管設定 `env` 強制 `ANTHROPIC_BASE_URL` 是設定分層的實例。

### Amazon Bedrock、Claude Platform on AWS、Google Cloud 和 Microsoft Foundry 的 Claude 應用程式閘道（`claude-apps-gateway`）
- 檔案：[claude-apps-gateway.md](claude-apps-gateway.md)｜https://code.claude.com/docs/zh-TW/claude-apps-gateway｜lastmod 2026-11-02｜60.9 KB
- 一句話：Claude apps gateway：內建於 `claude` 二進位的自託管閘道，提供 IdP 登入、群組模型存取、受管設定下發、OTLP 遙測。
- 何時讀：公司需資料駐留/自有雲端路由，並要 SSO 與依群組管理設定時；本頁含「設定分層」重點。
- 關鍵內容：
  - 啟動：`claude gateway --config gateway.yaml`；開發者以 IdP 瀏覽器登入換短期 bearer token（預設 1 小時）
  - 用戶端受管設定三鍵：`forceLoginMethod: "gateway"`、`forceLoginGatewayUrl`、`parentSettingsBehavior: "merge"`（放 MDM/檔案，不放閘道 `managed` 區塊）
  - 用戶端首次連線釘選 TLS 憑證指紋（SHA-256），憑證輪替會再次提示
  - 閘道遠端受管設定在受管層排名最高（高於 MDM/檔案）；但只送給 `/login` 登入的用戶端
  - 閘道工作階段不抓 claude.ai 的 server-managed settings，兩者擇一
  - `allowedProviders: ["gateway"]` 防止繞過閘道（雲端變數或自設 `ANTHROPIC_BASE_URL`）
  - 限制父設定：五個 `allowManaged*Only` 鎖（權限規則/MCP/hooks/sandbox 網域/sandbox 讀路徑）要與允許清單一起放高優先來源
  - 鎖未涵蓋：`forceLoginOrgUUID`、`allowedMcpServers`、`availableModels`、`allowedProviders`、`strictKnownMarketplaces` 在勝出來源未設時會採父設定值；`strictPluginOnlyCustomization` 永遠通過
  - 使用者設定 `~/.claude/settings.json` 內的 `forceLoginMethod`/`forceLoginGatewayUrl`（v2.1.295+）只在機器無受管設定時有效，不讀專案層
  - 強制項：模型存取伺服器端 400、遙測導向閘道、閘道 token 為唯一憑證、閘道不可達時啟動約 10 秒後失敗退出
  - 不可用：伺服器端 WebSearch、Remote Control、`/design-sync`、需 feature flag 的功能、OTLP/gRPC、SAML/LDAP、多租戶、Windows 伺服器
- 新名詞：`Claude apps gateway` ＝ Anthropic 提供、內建於 claude 二進位的自託管閘道；`IdP group policy` ＝ 依 OIDC token 的 groups 宣告套用不同受管設定與模型允許清單
- 記憶系統接點：受管設定經閘道下發 hook/env 需使用者核准一次（每閘道一筆）；閘道原則套用於所有 `claude -p` 與 SDK 衍生工作階段。

### Claude 應用程式閘道設定（`claude-apps-gateway-config`）
- 檔案：[claude-apps-gateway-config.md](claude-apps-gateway-config.md)｜https://code.claude.com/docs/zh-TW/claude-apps-gateway-config｜lastmod 2026-11-04｜151.3 KB
- 一句話：gateway.yaml 完整設定參考：listen/oidc/session/store/upstreams 與 managed、telemetry 等。
- 何時讀：要寫或除錯 gateway.yaml，尤其是 `managed` 政策合併規則時。
- 關鍵內容：
  - 五個必要區段：`listen`、`oidc`、`session`、`store`（PostgreSQL）、`upstreams`；未知鍵會讓啟動失敗
  - 選用：`admin`、`enforcement`、`pricing`、`models`、`managed`、`telemetry`、`access_control`/`limits`/`timeouts`/`rate_limits`、`load_test_mode`
  - `session.jwt_secret` 至少 32 bytes，陣列可輪換（索引 0 簽發）；`ttl_hours` 預設 1
  - `managed.policies[]`：以 `match: {groups|email_domain}` 比對，預設 first_match，再合併到最後的 `match: {}` 基礎層
  - 基礎層合併：允許清單（`availableModels`、`permissions.allow`）整體取代；拒絕清單與 hooks 陣列取聯集；`env`/`modelOverrides`/`skillOverrides` 淺合併
  - `policy_mode: layered`（v2.1.316+）套用所有符合政策；layered 下 `Read`/`Edit` 的 `!` 否定、非全包政策的 `disableAllHooks` 會讓閘道拒絕啟動
  - 政策設定放 `code`（建議，也涵蓋 Desktop Code 分頁）或舊鍵 `cli`，兩者不可並存；`desktop` 鍵為 Claude Desktop 疊加層
  - 內容是完整的 `managed-settings.json` schema（YAML 表示）；未知頂層鍵啟動失敗
  - `availableModels` 在 `/v1/messages` 伺服器端強制，被拒模型回 400；`enforceAvailableModels` 約束預設模型
  - 與其他受管來源：閘道設定排名第一；跨來源鍵（沙箱鎖等）仍從其他管理員來源讀
  - 群組成員變更在下次靜默刷新生效（受 `session.ttl_hours` 限制）；政策編輯於下一小時輪詢到達
  - `telemetry`：OTLP/HTTP 扇出、群組變更、直接匯出到自家收集器；`pricing` 合約費率乘數
- 新名詞：`layered policy_mode` ＝ 多群組政策疊加套用，而非只取第一個符合者；`match: {} 基礎層` ＝ 對所有已驗證使用者生效的預設政策，其他政策從它繼承
- 記憶系統接點：`hooks` 事件陣列在 managed 政策中取聯集，組織稽核 hook 不會被群組政策取代。

### Claude 應用程式閘道部署和運營（`claude-apps-gateway-deploy`）
- 檔案：[claude-apps-gateway-deploy.md](claude-apps-gateway-deploy.md)｜https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy｜lastmod 2026-11-02｜75.0 KB
- 一句話：部署與營運閘道：IdP 註冊、容器、Kubernetes/Cloud Run、日誌、升級、安全。
- 何時讀：實際上線閘道、處理大規模登入或疑難時。
- 關鍵內容：
  - IdP：註冊機密 OIDC 應用，redirect URI 為 `https://<gateway>/oauth/callback`；需 discovery、授權碼流程（PKCE 預設開）、`email`/`groups`
  - Okta 用組織授權伺服器需 `oidc.userinfo_fallback: true`；Entra 群組為 GUID；Google 無 groups claim
  - IdP 需發 refresh token 才有靜默更新與取消佈建效果
  - 大規模推出：設 `listen.trusted_proxies`；預設每 IP 每 10 分 30 次登入開始、10 次 code 提交，可調 `rate_limits`
  - 營運章節：日誌、健康(`/readyz`)、並行上游請求、首位元組期限、`readiness_grace_seconds`、JWT 密鑰輪換、Postgres 連線池、升級
  - 安全：資料流、威脅模型、使用者代碼暴力破解抵抗、合規態勢
  - 疑難：標頭過大、長時間思考被代理逾時（調 `API_TIMEOUT_MS`）
- 新名詞：無
- 記憶系統接點：無。

### 在 AWS 上部署 Claude apps gateway（`claude-apps-gateway-on-aws`）
- 檔案：[claude-apps-gateway-on-aws.md](claude-apps-gateway-on-aws.md)｜https://code.claude.com/docs/zh-TW/claude-apps-gateway-on-aws｜lastmod 2026-11-02｜49.0 KB
- 一句話：AWS 上部署閘道實例：ECS Fargate/EKS、RDS、Secrets Manager、Terraform。
- 何時讀：要照範例在 AWS 蓋閘道並做成本歸屬時。
- 關鍵內容：
  - 架構：ECS Fargate 或 EKS、ECR、私有 RDS PostgreSQL、Secrets Manager、內部 ALB、IAM 角色
  - IAM 需 `bedrock:InvokeModel`、`InvokeModelWithResponseStream`、`CountTokens`；EKS 用 IRSA
  - 上游可為 Bedrock 或 Claude Platform on AWS
  - 完整 Terraform 範例與故障排除
  - 成本歸屬：`assume_role` 依開發者、或應用程式推論設定檔依團隊；支援讓開發者選計費團隊
- 新名詞：`IRSA` ＝ EKS 上讓 Pod 取得 IAM 角色的機制
- 記憶系統接點：無。

### 在 Google Cloud 上部署 Claude 應用程式閘道（`claude-apps-gateway-on-gcp`）
- 檔案：[claude-apps-gateway-on-gcp.md](claude-apps-gateway-on-gcp.md)｜https://code.claude.com/docs/zh-TW/claude-apps-gateway-on-gcp｜lastmod 2026-10-22｜21.0 KB
- 一句話：Google Cloud 上部署閘道：Cloud Run/GKE、Cloud SQL、Secret Manager、Terraform。
- 何時讀：要照範例在 GCP 蓋閘道時。
- 關鍵內容：
  - 元件：Cloud Run 或 GKE、Artifact Registry、私有 IP Cloud SQL PostgreSQL、Secret Manager
  - 服務帳戶需 `roles/aiplatform.user`；GKE 用 Workload Identity
  - HTTPS 前端（內部 ALB 或 `gce-internal` Ingress）需自備
  - 含 Terraform 與疑難排解
- 新名詞：無
- 記憶系統接點：無。

### Claude 應用程式閘道支出限制（`claude-apps-gateway-spend-limits`）
- 檔案：[claude-apps-gateway-spend-limits.md](claude-apps-gateway-spend-limits.md)｜https://code.claude.com/docs/zh-TW/claude-apps-gateway-spend-limits｜lastmod 2026-10-25｜16.3 KB
- 一句話：閘道的每開發者日/週/月支出上限與 Admin API。
- 何時讀：要用閘道限制個別開發者花費時。
- 關鍵內容：
  - `gateway.yaml` 設 `admin:` 區塊後開 `/v1/organizations/spend_limits`；寫入/讀取各有 API key
  - 範圍：組織預設、群組分層、個別；超限回 `429` `error.type: billing_error`
  - UTC 邊界重設：每日 00:00、每週一、每月 1 日；`count_tokens` 不被擋
  - 每次 `/v1/messages` 一次 Postgres 查詢；`enforcement.fail_closed_on_error` 決定失敗行為
  - `/effective` 與 `/audit` 端點；`admin.blocked_message` 自訂訊息
  - 資料生命週期：`audit_retention_days`、`spend_retention_months`
- 新名詞：無
- 記憶系統接點：無。


## Usage and costs（用量與成本）

### 有效管理成本（`costs`）
- 檔案：[costs.md](costs.md)｜https://code.claude.com/docs/zh-TW/costs｜lastmod 2026-11-02｜45.6 KB
- 一句話：追蹤與降低 token 成本：`/usage`、組織層支出管理、節省策略。
- 何時讀：想知道花多少、怎麼限額、怎麼省 token 時。
- 關鍵內容：
  - 企業平均約每位開發者每活躍日 $13、每月 $150-250；90% 使用者低於 $30/日
  - `/usage` Session 區塊顯示 token 與成本、`Prompt cache (main)` 行（命中率、misses、expected rebuilds、warm/cold）
  - `modelPricing` 受管設定可改成合約價；`/clear` 重置工作階段總計
  - 支出管理三類：Teams/Enterprise（座位額度、extra usage、支出報告 CSV）、Console（工作區限額）、雲端（預算控制+OTel/閘道）
  - 省 token：`/clear`、`/compact <指示>`、CLAUDE.md 的 `# Compact instructions`、換 Sonnet、停用不用的 MCP、hook 預處理、把指示從 CLAUDE.md 移到 skill
  - 長時間 session 變貴的原因：長上下文、快取過期未命中、排程任務、跨 session 訊息、subagent、agent team、壓縮
- 新名詞：`prompt cache miss` ＝ 快取已過期或失效，整段前綴需重新處理並重寫入快取
- 記憶系統接點：含 hook/skill 預處理與 CLAUDE.md 瘦身的省 token 建議；快取失效與 `/compact` 的成本說明可對照 context 管理。

### 使用分析追蹤團隊使用情況（`analytics`）
- 檔案：[analytics.md](analytics.md)｜https://code.claude.com/docs/zh-TW/analytics｜lastmod 2026-11-02｜11.4 KB
- 一句話：分析儀表板：採用、貢獻指標（PR 歸因）、排行榜與 API。
- 何時讀：要衡量團隊採用與 ROI 時。
- 關鍵內容：
  - Teams/Enterprise：claude.ai/analytics/claude-code；API 客戶：platform.claude.com/claude-code
  - 指標：接受行數、建議接受率、DAU、工作階段；貢獻指標需連 GitHub 且為公測
  - PR 歸因：比對合併 PR 與 Claude Code 工作階段；視窗為合併前 21 天至後 2 天
  - 含 AI 協助行的 PR 在 GitHub 標 `claude-code-assisted`
  - ZDR 組織無貢獻指標；每人 token/成本請用 OTel 或支出報告
  - Enterprise Analytics API 可程式化存取
- 新名詞：`contribution metrics` ＝ 把合併 PR 的程式行對應到 Claude Code 工作階段的歸因指標
- 記憶系統接點：無。

### 監控（`monitoring-usage`）
- 檔案：[monitoring-usage.md](monitoring-usage.md)｜https://code.claude.com/docs/zh-TW/monitoring-usage｜lastmod 2026-11-03｜165.6 KB
- 一句話：OpenTelemetry 監控：啟用、受管鎖定 OTLP、指標、事件、追蹤與安全稽核。
- 何時讀：要把 Claude Code 用量/事件/追蹤匯到自家可觀測性堆疊或 SIEM 時。
- 關鍵內容：
  - 啟用：`CLAUDE_CODE_ENABLE_TELEMETRY=1`、`OTEL_METRICS_EXPORTER`/`OTEL_LOGS_EXPORTER`（otlp/prometheus/console/none）、`OTEL_EXPORTER_OTLP_PROTOCOL`/`_ENDPOINT`/`_HEADERS`
  - 管理員用受管設定 `env` 設定；受管設了 `OTEL_EXPORTER_OTLP_*` 會移除開發者衝突的端點/協議/認證；忽略 repo `.claude/settings*.json` 的 OTel 變數；不把 `OTEL_*` 傳給子程序
  - 指標：`claude_code.session.count`、`lines_of_code.count`、`pull_request.count`、`commit.count`、`cost.usage`、`token.usage`、`code_edit_tool.decision`、`active_time.total`
  - 事件約 29 種：`user_prompt`、`tool_result`、`tool_decision`、`api_request`、`api_error`、`hook_execution_start/complete`、`skill_activated`、`compaction`、`managed_settings_resolved`(v2.1.274+) 等
  - 隱私預設：不含提示/回應/工具參數；以 `OTEL_LOG_USER_PROMPTS`、`OTEL_LOG_ASSISTANT_RESPONSES`、`OTEL_LOG_TOOL_DETAILS`、`OTEL_LOG_TOOL_CONTENT`、`OTEL_LOG_RAW_API_BODIES`（可 `file:<dir>`）選擇加入
  - `prompt.id` 串起單一提示的所有事件；`OTEL_LOG_MANAGED_SETTINGS` 讓事件帶遮蔽後設定與 SHA-256
  - 動態標頭 `otelHeadersHelper`（預設 29 分鐘刷新）、mTLS、Traces 測試版、多團隊屬性
  - 稽核章節：安全事件對應、MCP 活動、保留清理 `retention_sweep`、送 SIEM
  - 除錯：`claude --debug-file <path>` 看 `[3P telemetry]` 錯誤；預設匯出間隔 metrics 60000ms、logs 5000ms
- 新名詞：`OTLP` ＝ OpenTelemetry Protocol，遙測傳輸協定（Claude Code 支援 grpc/http）；`prompt.id` ＝ UUID，連結同一提示觸發的所有事件
- 記憶系統接點：事件含 `hook_registered`/`hook_execution_*`、`skill_activated`、`compaction`、`mcp_server_connection`，可觀測 hooks/skills/MCP/context 壓縮行為；與 hooks 注入記憶互補。


## Security and data（安全與資料）

### 安全性（`security`）
- 檔案：[security.md](security.md)｜https://code.claude.com/docs/zh-TW/security｜lastmod 2026-10-30｜14.5 KB
- 一句話：安全性：權限架構、內建保護、提示注入防護、MCP/IDE/雲端安全與最佳實踐。
- 何時讀：做安全審查或決定權限/沙箱策略時。
- 關鍵內容：
  - 權限模式：自動模式（分類器審查）、手動模式（唯讀起手，需要時詢問）
  - 內建保護：沙箱化 bash（`/sandbox`）、工作目錄邊界、Accept Edits 模式、`/permissions` 審計
  - 提示注入防護：網路命令（curl/wget）不自動批准、WebFetch 另跑獨立模型摘要、命令注入偵測、信任驗證對話框
  - `-p` 工作階段不顯示信任提示；家目錄啟動信任不寫磁碟
  - 憑證儲存：macOS Keychain，Linux 0600 檔，Windows 繼承使用者資料夾 ACL
  - 雲端工作階段：隔離 VM、預設受限網路、GitHub 憑證不進 VM、審計日誌
  - Windows 勿啟 WebDAV；敏感程式碼用 devcontainer 或沙箱
- 新名詞：無
- 記憶系統接點：專案 `.mcp.json` 伺服器有獨立核准；hook/MCP 執行前的信任流程與 `-p` 模式差異。

### 資料使用（`data-usage`）
- 檔案：[data-usage.md](data-usage.md)｜https://code.claude.com/docs/zh-TW/data-usage｜lastmod 2026-10-30｜18.2 KB
- 一句話：資料政策：訓練、保留、遙測服務、各 API 提供者預設行為。
- 何時讀：要回答法遵/隱私問題、決定要關哪些遙測時。
- 關鍵內容：
  - 商業方案（Team/Enterprise/API）：預設不用於訓練；保留標準 30 天；消費者依設定 5 年或 30 天
  - 本機逐字稿預設以純文字存於 `~/.claude/projects/` 30 天，`cleanupPeriodDays` 可調
  - 遙測兩類：指標（`DISABLE_TELEMETRY=1`）、錯誤報告（`DISABLE_ERROR_REPORTING=1`）；`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` 一次全關
  - `/feedback`、`/bug`、`/share` 會送出對話；`DISABLE_FEEDBACK_COMMAND=1` 關；調查用 `CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY=1`
  - Bedrock/Vertex/Foundry/AWS 平台預設關閉指標與錯誤報告，但調查與 WebFetch 網域檢查例外
  - WebFetch 網域安全檢查只送主機名到 `api.anthropic.com`；`skipWebFetchPreflight: true` 可關，不受 DISABLE_NONESSENTIAL_TRAFFIC 影響
- 新名詞：`telemetry services` ＝ Anthropic 自己的營運遙測（指標、錯誤報告），不同於客戶端 OTel 匯出
- 記憶系統接點：本機逐字稿在 `~/.claude/projects/`、`cleanupPeriodDays` 影響保留；與記憶系統讀取歷史相關。

### 零資料保留（`zero-data-retention`）
- 檔案：[zero-data-retention.md](zero-data-retention.md)｜https://code.claude.com/docs/zh-TW/zero-data-retention｜lastmod 2026-10-16｜7.5 KB
- 一句話：Claude for Enterprise 的 ZDR：範圍、不涵蓋項目、被停用的功能。
- 何時讀：評估是否需要 ZDR 或查 ZDR 下哪些功能不能用時。
- 關鍵內容：
  - 僅 Claude for Enterprise 合格帳戶，需 Anthropic 個別啟用，且逐組織啟用
  - 涵蓋模型推理的提示與回應；不涵蓋 claude.ai 聊天、Cowork、分析中繼資料、座位管理、第三方整合
  - 後端停用：雲端工作階段、Chat/Cowork 整合、Claude Tag、Artifacts、`/feedback`/`/bug`/`/share`、Remote Control
  - 分析儀表板在 ZDR 下無貢獻指標
  - Fable 5.1/5 預設需資料保留，ZDR 下不可用，`best` 別名改解析為 Opus
  - 政策違規時 Anthropic 可保留輸入輸出最長 2 年
  - 僅直連 Anthropic 平台；Bedrock/Vertex/Foundry 看各平台政策
- 新名詞：`ZDR` ＝ Zero Data Retention，提示與回應處理完即不保留
- 記憶系統接點：無。

### 為 HIPAA-ready 組織設定 Claude Code（本機模式）（`hipaa-setup`）
- 檔案：[hipaa-setup.md](hipaa-setup.md)｜https://code.claude.com/docs/zh-TW/hipaa-setup｜lastmod 2026-10-29｜22.2 KB
- 一句話：為 HIPAA-ready 組織準備開發者電腦（Claude Code 本機模式）。
- 何時讀：有 BAA/PHI、要套 HIPAA 組織設定時。
- 關鍵內容：
  - 僅在 Claude Enterprise 登入且直連 Claude API 的本機工作階段生效；VS Code/JetBrains 擴充不在範圍；閘道工作階段不符資格
  - 受管設定範例四鍵：`forceLoginMethod: claudeai`、`forceLoginOrgUUID`、`allowedProviders: ["anthropic"]`、`cleanupPeriodDays`
  - `forceLoginOrgUUID` 填錯會使 claude.ai 登入者啟動即退出
  - `cleanupPeriodDays` 設在受管層時忽略開發者自己的值
  - 範例儲存庫有 `settings-hipaa.json` 含沙箱、網路允許清單、憑證保護
  - 本機資料：`~/.claude/projects/` 逐字稿；`claude purge --all --yes`（v2.1.288+）或 `claude project purge`（v2.1.126-287）
  - 保留清理只在有人啟動 Claude Code 時執行；套用後 Code 分頁預設關閉直到 Owner 重開
- 新名詞：`HIPAA configuration` ＝ Enterprise 方案的組織設定，用於處理 PHI 並簽有 BAA
- 記憶系統接點：`claude purge` 會刪逐字稿、自動記憶、tasks、debug、file-history、history.jsonl；本機逐字稿保留由 `cleanupPeriodDays` 控制。


## Adoption（推廣）

### Champion kit（`champion-kit`）
- 檔案：[champion-kit.md](champion-kit.md)｜https://code.claude.com/docs/zh-TW/champion-kit｜lastmod 2026-10-03｜15.1 KB
- 一句話：內部推廣者手冊：分享什麼、怎麼答疑、30 天行動計畫。
- 何時讀：你想在團隊內推動 Claude Code 採用時。
- 關鍵內容：
  - 三種行為：分享發現、成為被請教的人、擴大圈子
  - 回答問題用提示詞而非解釋，指向功能而非文件
  - 30 天計畫：W1 播種頻道、W2 每週 show-and-tell、W3 配對+常見問題整合、W4 找第二位推廣者並交接
  - 每週信號：有人回覆或貼出自己的例子、同批同事回來重複使用
  - 含回應常見疑慮與快速參考表
- 新名詞：無
- 記憶系統接點：無。

### 通訊工具包（`communications-kit`）
- 檔案：[communications-kit.md](communications-kit.md)｜https://code.claude.com/docs/zh-TW/communications-kit｜lastmod 2026-10-03｜21.2 KB
- 一句話：推出公告、滴灌式提示與常見問答範本。
- 何時讀：管理員要對工程團隊發佈 Claude Code 時。
- 關鍵內容：
  - 發送前檢查清單：建立 `#claude-code` 頻道、至少一台機器測試安裝命令等
  - 公告含執行贊助商變體、試點小組變體、推廣者招募直訊
  - 滴灌主題：開始使用、專案記憶、控制與安全、連接工具、自動化、日常開發、分享擴展、安全管理
  - 含 FAQ 回應與提示範本
  - 全部視為草稿，須用自家語氣與實際程式碼重寫
- 新名詞：無
- 記憶系統接點：專案記憶（CLAUDE.md）為滴灌主題之一。


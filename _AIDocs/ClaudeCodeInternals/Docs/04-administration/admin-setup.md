<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/admin-setup | lastmod: 2026-11-03 | section: Administration / Setup and access -->
> 來源：https://code.claude.com/docs/zh-TW/admin-setup（官方 zh-TW，lastmod 2026-11-03）｜分類：Administration › Setup and access｜EN 摘要：A decision map for administrators deploying Claude Code, covering API providers, managed settings, policy enforcement, usage monitoring, and data handling.

# 為您的組織設定 Claude Code

> 管理員部署 Claude Code 的決策地圖，涵蓋 API 提供者、受管設定、政策執行、使用情況監控和資料處理。

Claude Code 透過受管設定來執行組織政策，這些設定優先於本地開發人員配置。您可以從 Claude 管理員控制台、行動裝置管理 (MDM) 系統或磁碟上的檔案傳遞這些設定。這些設定控制 Claude 可以存取的工具、命令、伺服器和網路目的地。

本頁按順序介紹部署決策。每一行都連結到下面的部分和該區域的參考頁面。

> [!NOTE]
>
> SSO、SCIM 佈建和座位分配在 Claude 帳戶級別進行配置。有關這些步驟，請參閱 [Claude 企業管理員指南](https://claude.com/resources/tutorials/claude-enterprise-administrator-guide) 和 [座位分配](https://support.claude.com/en/articles/11845131-use-claude-code-with-your-team-or-enterprise-plan)。

| 決策 | 您正在選擇什麼 | 參考 |
| :- | :- | :- |
| [選擇您的 API 提供者](#choose-your-api-provider) | Claude Code 驗證的位置以及如何計費 | [Authentication](https://code.claude.com/docs/zh-TW/authentication.md)、[Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md)、[Google Cloud's Agent Platform](https://code.claude.com/docs/zh-TW/google-vertex-ai.md)、[Microsoft Foundry](https://code.claude.com/docs/zh-TW/microsoft-foundry.md) |
| [決定設定如何到達裝置](#decide-how-settings-reach-devices) | 受管政策如何到達開發人員機器 | [Server-managed settings](https://code.claude.com/docs/zh-TW/server-managed-settings.md)、[Delivery mechanisms](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms) |
| [決定要執行什麼](#decide-what-to-enforce) | 允許哪些工具、命令和整合 | [Permissions](https://code.claude.com/docs/zh-TW/permissions.md)、[Sandboxing](https://code.claude.com/docs/zh-TW/sandboxing.md) |
| [設定使用情況可見性](#set-up-usage-visibility) | 您如何追蹤支出和採用情況 | [Analytics](https://code.claude.com/docs/zh-TW/analytics.md)、[Monitoring](https://code.claude.com/docs/zh-TW/monitoring-usage.md)、[Costs](https://code.claude.com/docs/zh-TW/costs.md) |
| [檢查資料處理](#review-data-handling) | 資料保留和合規狀況 | [Data usage](https://code.claude.com/docs/zh-TW/data-usage.md)、[Security](https://code.claude.com/docs/zh-TW/security.md) |

## 選擇您的 API 提供者

Claude Code 透過多個 API 提供者之一連接到 Claude。您的選擇會影響計費、驗證、您繼承的合規狀況，以及您的開發人員可以使用的 Claude Code 功能。

| 提供者 | 在以下情況下選擇此選項 |
| :- | :- |
| Claude for Teams / Enterprise | 您希望 Claude Code 和 claude.ai 在一個按座位訂閱下，無需執行基礎設施。這是預設建議。 |
| Claude Console | 您是 API 優先或希望按使用量付費計費 |
| Amazon Bedrock | 您希望繼承現有的 AWS 合規控制和計費 |
| Google Cloud's Agent Platform | 您希望繼承現有的 GCP 合規控制和計費 |
| Microsoft Foundry | 您希望繼承現有的 Azure 合規控制和計費 |

某些 Claude Code 功能需要 claude.ai 帳戶。[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)、[雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md)、[Code Review](https://code.claude.com/docs/zh-TW/code-review.md)、[Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 和 [Chrome extension](https://code.claude.com/docs/zh-TW/chrome.md) 無法僅透過 Console API 金鑰或雲端提供者憑證使用。如果您透過 Amazon Bedrock、Google Cloud's Agent Platform 或 Microsoft Foundry 部署，請規劃開發人員是否也需要 Claude for Teams 或 Enterprise 座位。每個功能頁面都列出其計畫要求。

有關涵蓋驗證、區域和功能奇偶性的完整提供者比較，請參閱 [企業部署概述](https://code.claude.com/docs/zh-TW/third-party-integrations.md)。每個提供者的驗證設定位於 [Authentication](https://code.claude.com/docs/zh-TW/authentication.md)。

無論提供者如何，[網路配置](https://code.claude.com/docs/zh-TW/network-config.md) 中的代理和防火牆要求都適用。如果您想要在多個提供者前面有單一端點或集中式請求日誌記錄，請參閱 [LLM gateway](https://code.claude.com/docs/zh-TW/llm-gateway)。

## 決定設定如何到達裝置

受管設定定義組織政策。Claude Code 按優先順序檢查下表中的四個來源。[Claude Code 如何合併受管來源](https://code.claude.com/docs/zh-TW/managed-settings.md#precedence-within-the-managed-tier)說明其中哪些適用、政策協助程式變更的內容，以及如何組成每個來源。該表是決策地圖。

| 機制 | 傳遞 | 優先順序 | 平台 |
| :- | :- | :- | :- |
| Server-managed | claude.ai 管理員控制台，或用於閘道登入的自託管 [Claude apps gateway](https://code.claude.com/docs/zh-TW/claude-apps-gateway) | 最高 | 全部 |
| plist / registry policy | macOS：`com.anthropic.claudecode` plist Windows：`HKLM\SOFTWARE\Policies\ClaudeCode` | 高 | macOS、Windows |
| File-based managed | macOS：`/Library/Application Support/ClaudeCode/managed-settings.json` Linux 和 WSL：`/etc/claude-code/managed-settings.json` Windows：`C:\Program Files\ClaudeCode\managed-settings.json` | 中 | 全部 |
| Windows user registry | `HKCU\SOFTWARE\Policies\ClaudeCode` | 最低 | 僅 Windows |

Claude Code 在啟動時擷取 server-managed 設定，並在工作階段期間每小時重新整理一次，無需部署端點基礎設施。透過 claude.ai 管理員控制台傳遞需要 Claude for Teams 或 Enterprise 計畫。在 Amazon Bedrock、Google Cloud 的 Agent Platform 或 Microsoft Foundry 上的部署可以透過執行 [Claude apps gateway](https://code.claude.com/docs/zh-TW/claude-apps-gateway) 獲得相同的遠端傳遞，或改用其中一個基於檔案或作業系統級別的機制。

如果您的組織混合使用提供者，請為 claude.ai 使用者設定 [server-managed settings](https://code.claude.com/docs/zh-TW/server-managed-settings.md) 加上 [基於檔案或 plist/registry 的備援](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)，以便其他使用者仍然接收受管政策。

plist 和 HKLM 登錄位置適用於任何提供者，並且由於需要管理員權限才能寫入，因此可以抵抗篡改。Windows 使用者登錄中的 HKCU 無需提升即可寫入，因此將其視為便利預設值而不是執行通道。

根據預設，WSL 僅讀取 `/etc/claude-code` 的 Linux 檔案路徑。若要將您的 Windows 登錄和 `C:\Program Files\ClaudeCode` 政策擴展到同一機器上的 WSL，請在這些僅限管理員的 Windows 來源之一中設定 [`wslInheritsWindowsSettings: true`](https://code.claude.com/docs/zh-TW/settings-reference#wslinheritswindowssettings)。

無論您選擇哪種機制，受管值都優先於使用者和專案設定，除了少數安全敏感的[例外](https://code.claude.com/docs/zh-TW/settings.md#exceptions-to-managed-settings-precedence)。陣列設定（例如 `permissions.allow` 和 `permissions.deny`）會合併來自所有來源的項目，因此開發人員可以擴展受管清單但無法從中移除。對於 `fallbackModel`、`availableModels` 和 [`modelPicker`](https://code.claude.com/docs/zh-TW/settings-reference#modelpicker)，受管值會取代較低層級而不是合併。

### Claude Code Desktop 中的 WSL 工作階段

在 Windows 上，[Claude Code Desktop 可以在 WSL 2 發行版內執行 Code 工作階段](https://code.claude.com/docs/zh-TW/desktop-wsl.md)。工作階段的 Claude Code 程序在發行版內執行，因此它透過上述 WSL 探索路徑解析受管設定：除非部署了 `wslInheritsWindowsSettings: true`，否則僅限 Windows 的來源無法到達它。

Claude Desktop 在偵測到裝置為組織受管的裝置上預設關閉 WSL 工作階段，例如當 `C:\Program Files\ClaudeCode\managed-settings.json` 存在時。若要開啟它們，請部署 Windows 登錄政策，這需要 Claude Desktop v1.19367.0 或更新版本：

* 在 `HKLM\SOFTWARE\Policies\Claude` 下建立名為 `disableWslSessions` 的值，並將其設定為 `REG_SZ` 字串 `false` 或 `REG_DWORD` `0`。此值位於 Claude Desktop 政策金鑰下，與包含受管設定的 `ClaudeCode` 金鑰分開。在 HKLM 下部署該值，這需要管理員權限才能寫入。HKCU 下的值不會啟用 WSL 工作階段。
* 如果您部署 `C:\Program Files\ClaudeCode\managed-settings.json`，請保留它。一旦 HKLM 下的 `disableWslSessions` 為 `false`，Desktop 即使該檔案存在也允許 WSL 工作階段。

Desktop 在每次 WSL 工作階段啟動時讀取政策，因此您無需在部署後重新啟動應用程式。

如果裝置仍然拒絕 WSL 工作階段，請在該裝置上的 Claude Desktop 中開啟 **Help > Troubleshooting > Show Logs in File Explorer**，這會將其日誌資料夾的副本儲存到 Downloads。在該副本中搜尋 `main.log` 以查找 `[wslPolicyGate] denying WSL session`。拒絕的原因在括號中，例如 `(cli-file-present)`。

啟用 WSL 工作階段後，將您的受管設定擴展到它們：

* 透過 HKLM 登錄或 `C:\Program Files\ClaudeCode` 檔案部署 `wslInheritsWindowsSettings: true`，以便 WSL 工作階段繼承與主機工作階段相同的政策。
* 透過在 WSL 工作階段內執行 `/status` 進行驗證，並讀取 `Setting sources` 行。若要解釋它列出的內容，請參閱[在 /status 中讀取來源](https://code.claude.com/docs/zh-TW/managed-settings.md#read-the-source-in-/status)。

如果 WSL 工作階段在設有 Claude Desktop [`allowedWorkspaceFolders`](https://claude.com/docs/third-party/claude-desktop/configuration#allowedworkspacefolders) 清單的裝置上啟動，`~` 項目代表發行版內的家目錄。

WSL 2 公用程式 VM 內的程序對 Windows 端端點偵測感應器不可見。若要觀察發行版內的程序和檔案活動，請檢查您的端點偵測廠商的 WSL 指南，以取得您可以在發行版內執行的 Linux 感應器及其需要的排除項目。Claude Code 的 [OpenTelemetry 工具執行遙測](https://code.claude.com/docs/zh-TW/monitoring-usage.md)對 WSL 和原生工作階段的發出方式相同。

## 決定要執行什麼

受管設定可以鎖定工具、沙箱執行、限制 MCP 伺服器和外掛程式來源，以及控制哪些 hooks 執行。每一行都是一個控制表面，具有驅動它的設定鍵。

| 控制 | 它的作用 | 關鍵設定 |
| :- | :- | :- |
| [Permission rules](https://code.claude.com/docs/zh-TW/permissions.md) | 允許、詢問或拒絕特定工具和命令 | `permissions.allow`、`permissions.deny` |
| [Permission lockdown](https://code.claude.com/docs/zh-TW/permissions.md#managed-only-settings) | 使受管設定成為[唯一的權限規則設定來源](https://code.claude.com/docs/zh-TW/settings-reference.md#allowmanagedpermissionrulesonly)。禁用 `--dangerously-skip-permissions` | `allowManagedPermissionRulesOnly`、`permissions.disableBypassPermissionsMode` |
| [Starting permission mode](https://code.claude.com/docs/zh-TW/permission-modes.md#which-mode-a-session-starts-in) | 選擇開發人員終端會話啟動時的權限模式，而不是內建的啟動權限模式，或移除自動模式。[切換權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md#switch-permission-modes)列出 VS Code 擴充功能讀取您設定的 `defaultMode` 的時機 | `permissions.defaultMode`、`permissions.disableAutoMode` |
| [Sandboxing](https://code.claude.com/docs/zh-TW/sandboxing.md) | 作業系統級別的檔案系統和網路隔離，具有網域允許清單 | `sandbox.enabled`、`sandbox.network.allowedDomains` |
| [Managed policy CLAUDE.md](https://code.claude.com/docs/zh-TW/memory.md#deploy-organization-wide-claude-md) | 為 Claude 提供的組織範圍行為指引，而非由用戶端強制執行的規則 | 受管政策路徑中的檔案 |
| [MCP server control](https://code.claude.com/docs/zh-TW/managed-mcp.md) | 限制使用者可以新增或連接的 MCP 伺服器、部署固定集合，或為每個使用者提供遠端伺服器以及他們自己的伺服器 | `allowedMcpServers`、`deniedMcpServers`、`allowManagedMcpServersOnly`、`managedMcpServers`，或已部署的 `managed-mcp.json` 檔案 |
| [Plugin marketplace control](https://code.claude.com/docs/zh-TW/plugins/org.md#restrict-what-users-can-install) | 限制使用者可以新增和安裝的市集來源，並拒絕為單次執行側載外掛程式、agent 和 MCP 伺服器的 CLI 旗標。阻止[`command` 外掛程式來源](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference#command-plugin-source)，並以允許清單指定哪些市集的外掛程式可以在終端機中被建議 | `strictKnownMarketplaces`、`blockedMarketplaces`、`disableSideloadFlags`、`disableCommandPluginSources`、`pluginSuggestionMarketplaces` |
| [Customization lockdown](https://code.claude.com/docs/zh-TW/settings-reference.md#strictpluginonlycustomization) | 阻止 skills、agents、hooks 和 MCP 伺服器來自使用者和專案來源，使其只能來自外掛程式或受管設定。鎖定 skills 也會停止[您的開發人員在 claude.ai 上啟用的 skills](https://code.claude.com/docs/zh-TW/skills.md#where-synced-skills-load)同步 | `strictPluginOnlyCustomization` |
| [Disable claude.ai sync](https://code.claude.com/docs/zh-TW/settings-reference.md#syncclaudeaiskills) | 停止 Claude Code 載入[skills](https://code.claude.com/docs/zh-TW/skills.md#how-synced-skills-behave)和[外掛程式](https://code.claude.com/docs/zh-TW/plugins/loading.md#synced-plugins)您的開發人員在 claude.ai 上啟用。如果您為組織關閉 claude.ai 上的 Skills，Claude Code 會停止同步兩者，在 v2.1.273 或更新版本上，它也會移除已同步的。若要在不關閉 Skills 的情況下停止其中任一個，請在受管設定中將其鍵設定為 `false` | `syncClaudeAiSkills`、`syncClaudeAiPlugins` |
| [Hook restrictions](https://code.claude.com/docs/zh-TW/settings-reference.md#allowmanagedhooksonly) | 限制哪些 hooks 執行並限制 HTTP hook URL；請參閱[在 `allowManagedHooksOnly` 下執行的內容](https://code.claude.com/docs/zh-TW/settings-reference#what-runs-under-allowmanagedhooksonly)以了解完整的效果清單 | `allowManagedHooksOnly`、`allowedHttpHookUrls` |
| [Login enforcement](https://code.claude.com/docs/zh-TW/settings-reference.md#forceloginmethod) | 限制登入為特定方法或 Anthropic 組織。方法限制適用於 VS Code 擴充功能、Agent SDK、`claude setup-token` 和 `/install-github-app`，而終端的互動式登入畫面（透過 `/login` 或首次執行上線到達）則會預先選擇該方法而不強制執行；Claude Code 驗證終端、VS Code 擴充功能和 Agent SDK 中 claude.ai 帳戶登入的組織，不檢查 Claude Console 登入或[閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)登入。在 v2.1.212 之前，只有終端登入應用任一鍵。設定時，由 `ANTHROPIC_API_KEY`、`ANTHROPIC_AUTH_TOKEN` 或 `apiKeyHelper` 驗證的會話在啟動時被阻止；雲端提供者會話不受影響，除非這些認證之一或由較早的 Claude Console 登入儲存的 API 金鑰也存在 | `forceLoginMethod`、`forceLoginOrgUUID` |
| [Provider restrictions](https://code.claude.com/docs/zh-TW/settings-reference.md#allowedproviders) | 限制機器可能使用的 API 提供者。不在列表中的提供者上的會話在啟動時、登入時以及下次聯絡 API 時被拒絕。需要 Claude Code v2.1.285 或更新版本 | `allowedProviders` |
| [Disable agent view](https://code.claude.com/docs/zh-TW/agent-view.md#how-background-sessions-are-hosted) | 關閉 `claude agents`、`--bg`、`/background` 和隨選監督員 | `disableAgentView` |
| [Configure the corporate launcher](https://code.claude.com/docs/zh-TW/corporate-launcher.md) | 使用必需的公司啟動器作為[背景代理監督員](https://code.claude.com/docs/zh-TW/agent-view.md#how-background-sessions-are-hosted)、其工作者和[其他涵蓋的背景程序](https://code.claude.com/docs/zh-TW/corporate-launcher.md#what-the-launcher-covers)的前綴，而不是關閉代理檢視 | `processWrapper` |
| [Model restrictions](https://code.claude.com/docs/zh-TW/model-config.md#restrict-model-selection) | `availableModels` 篩選模型選擇器中出現的模型。新增 `enforceAvailableModels` 也會限制自動選擇的預設模型。請參閱[表面涵蓋範圍](https://code.claude.com/docs/zh-TW/model-config.md#surface-coverage)以了解此設定如何到達 CLI、網頁和 IDE | `availableModels`、`enforceAvailableModels` |
| [Effort cap](https://code.claude.com/docs/zh-TW/settings-reference.md#maxeffortlevel) | 為所有模型或個別模型限制[工作量級別](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)，適用於每個提供者 | `maxEffortLevel` |
| [Version floor](https://code.claude.com/docs/zh-TW/settings-reference.md#minimumversion) | 防止自動更新安裝低於組織範圍最小值的版本 | `minimumVersion` |
| [Required version range](https://code.claude.com/docs/zh-TW/settings-reference.md#requiredminimumversion) | 當執行版本超出組織核准範圍時，完全拒絕啟動。比 `minimumVersion` 更強大，後者只會阻止降級 | `requiredMinimumVersion`、`requiredMaximumVersion` |
| [Telemetry opt-out](https://code.claude.com/docs/zh-TW/data-usage.md#telemetry-services) | 在每個裝置上關閉 Anthropic 繫結的使用量指標、錯誤報告和調查 | `env` 設定 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` 為 `1`；連結的部分列出了各類別變數 |

如果您的成員透過 claude.ai 或 Anthropic API 登入，且您使用 Claude Enterprise 方案，您也可以從組織的管理設定中管理模型，而無需部署任何內容：

* [Organization model restrictions](https://code.claude.com/docs/zh-TW/model-config.md#organization-model-restrictions)：停用個別模型。在伺服器端執行。
* [Organization default model](https://code.claude.com/docs/zh-TW/model-config.md#organization-default-model)：設定新工作階段啟動時使用的模型。成員仍可切換模型。若要在啟動時將他們恢復為您的預設模型，請開啟該節所述的覆寫設定。若要限制他們可選擇的模型，請使用[組織模型限制](https://code.claude.com/docs/zh-TW/model-config.md#organization-model-restrictions)。
* [Organization effort limits](https://code.claude.com/docs/zh-TW/model-config.md#organization-effort-limits)：按角色限制工作量級別。在伺服器端執行。

這些控制都不會到達 Amazon Bedrock、Google Cloud 的 Agent Platform、Microsoft Foundry 或 [Claude Platform on AWS](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md) 上的會話。在這些提供者上，改用受管設定：`availableModels` 用於限制、`model` 用於預設值，以及 [`maxEffortLevel`](https://code.claude.com/docs/zh-TW/settings-reference#maxeffortlevel) 用於工作量限制。

[Cloud sessions](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md) 在 claude.ai 上有其專屬的管理介面：

* **Cloud environments 頁面**：擁有者建立[組織共享環境](https://code.claude.com/docs/zh-TW/cloud-environments.md#organization-shared-environments)，設定成員雲端工作階段的[網路存取級別](https://code.claude.com/docs/zh-TW/cloud-environments.md#network-access)、環境變數和設定指令碼。
* **預設環境**：擁有者在 [claude.ai/admin-settings/claude-code](https://claude.ai/admin-settings/claude-code) 另外選擇組織的預設環境。
* **Git providers 頁面**：請參閱[已連結的 GitHub 帳戶](#connected-github-accounts)，以了解連結至您組織的 GitHub 帳戶。

權限規則和沙箱涵蓋不同的層。拒絕 WebFetch 會阻止 Claude 的 fetch 工具，但如果允許 Bash，`curl` 和 `wget` 仍然可以到達任何 URL。沙箱透過在作業系統級別執行的網路網域允許清單來彌補這一差距。

有關這些控制防禦的威脅模型，請參閱 [Security](https://code.claude.com/docs/zh-TW/security.md)。

### 已連結的 GitHub 帳戶

在 Team 和 Enterprise 方案中，[**Organization settings > Git providers**](https://claude.ai/admin-settings/source-control) 的 GitHub 區段會列出透過 [Claude GitHub App](https://github.com/apps/claude) 連結至您 Claude 組織的 GitHub 組織和個人帳戶。Claude Code、[Claude Tag](https://claude.com/docs/claude-tag/admins/configure-github) 和 Claude Security 共用此清單。開啟此頁面需要您在 Claude 組織中具備[擁有者角色](https://code.claude.com/docs/zh-TW/server-managed-settings.md#access-control)。管理員角色無法開啟此頁面。

任何人都可以從 Git providers 頁面或透過將 GitHub 連接至 Claude 來連結帳戶：

* **擁有者連線**：擁有者在該區段中點擊 **Connect**，或在已連結帳戶後點擊 **Add organization**，並在 GitHub 組織上安裝 Claude GitHub App。以此方式連結組織，需要一位同時是您 Claude 組織擁有者及該 GitHub 組織擁有者的人員。
* **成員連線**：當成員將其 GitHub 帳戶連接至 Claude 時（例如在[設定雲端工作階段](https://code.claude.com/docs/zh-TW/web-quickstart.md#connect-github)期間），Claude 會連結該成員所擁有、且已安裝 Claude GitHub App 的 GitHub 帳戶。這可能包括其個人帳戶以及其擁有的 GitHub 組織。

標示為 **Not linked** 的列來自您自己的 GitHub 登入。這是您在 GitHub 上可以看到、且已安裝 Claude GitHub App 的帳戶。

若要將帳戶從您的 Claude 組織取消連結，請開啟該列的選單並選取 **Unlink from this workspace**。取消連結後，Claude GitHub App 仍會保留安裝在 GitHub 上，而當該帳戶的任一擁有者下次將 GitHub 連接至 Claude 時，該帳戶會再次被連結。若要避免其再次被連結，請在 GitHub 上從該帳戶解除安裝 Claude GitHub App。

在 Enterprise 方案中，用於連結和取消連結的 [Compliance API](https://platform.claude.com/docs/en/api/compliance/activities/list) 活動類型為 `github_app_installation_linked` 和 `github_app_installation_unlinked`。

## 設定使用情況可見性

根據您需要報告的內容選擇監控。儀表板、API 和支出控制在 Claude for Teams 或 Enterprise 計畫與 Claude Console 組織之間有所不同，因此在根據功能規劃報告之前，請檢查「可用性」欄。

| 功能 | 您獲得什麼 | 可用性 | 從哪裡開始 |
| :- | :- | :- | :- |
| Usage monitoring | 會話、工具和令牌的 OpenTelemetry 匯出 | 所有提供者 | [Monitoring usage](https://code.claude.com/docs/zh-TW/monitoring-usage.md) |
| Analytics dashboard | Teams / Enterprise 上具有排行榜的採用和貢獻指標；Console 上的每個使用者使用情況和支出指標 | Teams / Enterprise 在 [claude.ai/analytics](https://claude.ai/analytics/claude-code)，Console 在 [platform.claude.com/claude-code](https://platform.claude.com/claude-code) | [Analytics](https://code.claude.com/docs/zh-TW/analytics.md) |
| Programmatic reporting | 透過 API 的每個使用者使用情況和成本資料 | Enterprise 的 [Enterprise Analytics API](https://platform.claude.com/docs/en/api/admin/analytics)，Console 的 [Claude Code Analytics API](https://platform.claude.com/docs/en/build-with-claude/claude-code-analytics-api) | [Costs](https://code.claude.com/docs/zh-TW/costs.md#manage-costs-for-your-organization) |
| Spend controls | 支出限制和速率限制 | Teams / Enterprise 的組織設定、Console 的工作區限制；在第三方雲端上，雲端預算控制或具有每個使用者[支出限制](https://code.claude.com/docs/zh-TW/claude-apps-gateway-spend-limits.md)的 [Claude 應用程式閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway) | [Costs](https://code.claude.com/docs/zh-TW/costs.md#manage-costs-for-your-organization) |

在 Teams 和 Enterprise 上，每個使用者的使用情況和支出數字來自您組織分析設定中的[支出報告](https://support.claude.com/en/articles/12883420-view-usage-analytics-for-team-and-enterprise-plans)，而不是分析儀表板。雲端提供者透過 AWS Cost Explorer、GCP Billing 或 Azure Cost Management 公開支出。如需規劃跨 Claude chat、Claude Code 和 Cowork 的企業預算，請參閱 [Claude Enterprise 消費指南](https://support.claude.com/en/articles/14782391-claude-enterprise-consumption-guide)。

## 檢查資料處理

在 Team、Enterprise、Claude API 和雲端提供者計畫上，Anthropic 不會在您的程式碼或提示上訓練模型。您的 API 提供者決定保留和合規狀況。

| 主題 | 需要了解的內容 | 從哪裡開始 |
| :- | :- | :- |
| Data usage policy | Anthropic 收集什麼、保留多長時間、永遠不會用於訓練的內容 | [Data usage](https://code.claude.com/docs/zh-TW/data-usage.md) |
| Zero Data Retention (ZDR) | 請求完成後不儲存任何內容。適用於 Claude for Enterprise 上符合資格的帳戶 | [Zero data retention](https://code.claude.com/docs/zh-TW/zero-data-retention.md) |
| HIPAA configuration | 適用於已啟用 HIPAA 的 Claude for Enterprise 組織。部分 Claude Code（本機模式）功能會被關閉，其他功能則預設為關閉 | [Set up Claude Code (local mode) for a HIPAA-ready organization](https://code.claude.com/docs/zh-TW/hipaa-setup.md) |
| Security architecture | 網路模型、加密、驗證、稽核追蹤 | [Security](https://code.claude.com/docs/zh-TW/security.md) |

如果您需要請求層級的稽核日誌記錄或依資料敏感性路由流量，我們建議您在開發人員和您的提供者之間放置閘道：自行託管的 [Claude apps gateway](https://code.claude.com/docs/zh-TW/claude-apps-gateway) 會記錄包含 IdP 身分的每個請求稽核日誌，或者您也可以使用另一個 [LLM gateway](https://code.claude.com/docs/zh-TW/llm-gateway)。透過閘道進行的工作階段不適用於 HIPAA 設定。[檢查開發人員如何登入和連線](https://code.claude.com/docs/zh-TW/hipaa-setup.md#check-how-developers-sign-in-and-connect)列出了哪些登入和連線方式適用。有關法規要求和認證，請參閱 [Legal and compliance](https://code.claude.com/docs/zh-TW/legal-and-compliance.md)。

## 驗證和上線

配置受管設定後，讓開發人員在 Claude Code 內執行 `/status`。在 **Status** 標籤上，`Setting sources` 行顯示 `Enterprise managed settings` 後面跟著括號中的來源；[驗證強制執行](https://code.claude.com/docs/zh-TW/managed-settings.md#verify-enforcement)列出標籤。

分享這些資源以幫助開發人員入門：

* [快速入門](https://code.claude.com/docs/zh-TW/quickstart.md)：從安裝到使用專案的首次會話逐步說明
* [常見工作流程](https://code.claude.com/docs/zh-TW/common-workflows.md)：日常任務的模式，例如程式碼審查、重構和除錯
* [Claude Code 101](https://academy.claude.com/courses/claude-code-101) 和 [Claude Code in Action](https://academy.claude.com/courses/claude-code-in-action)：[Claude Academy](https://academy.claude.com/) 上的免費自進度課程

對於登入問題，請將開發人員指向 [驗證疑難排解](https://code.claude.com/docs/zh-TW/troubleshoot-install.md#login-and-authentication)。最常見的修復是：

* 執行 `/logout` 然後 `/login` 以切換帳戶
* 如果缺少企業驗證選項，執行 `claude update`
* 更新後重新啟動終端

如果開發人員看到「您尚未被新增到您的組織」，他們的座位不包括 Claude Code 存取權限，需要在管理員控制台中更新。

## 後續步驟

選擇提供者和傳遞機制後，繼續進行詳細設定：

* [Server-managed settings](https://code.claude.com/docs/zh-TW/server-managed-settings.md)：從 Claude 管理員控制台傳遞受管政策
* [All settings](https://code.claude.com/docs/zh-TW/settings-reference.md)：每個設定鍵、檔案位置和範例
* [Which value Claude Code uses](https://code.claude.com/docs/zh-TW/settings.md#which-value-claude-code-uses)：跨受管、專案、本機和使用者設定的優先級規則
* [Manage plugins for your organization](https://code.claude.com/docs/zh-TW/plugins/org.md)：透過受管設定在每部機器上安裝共用外掛
* [Monorepos and large repos](https://code.claude.com/docs/zh-TW/large-codebases.md)：為部署到 monorepo 的組織提供的每個目錄設定模式
* [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md)、[Google Cloud's Agent Platform](https://code.claude.com/docs/zh-TW/google-vertex-ai.md)、[Microsoft Foundry](https://code.claude.com/docs/zh-TW/microsoft-foundry.md)：提供者特定部署
* [Claude Enterprise Administrator Guide](https://claude.com/resources/tutorials/claude-enterprise-administrator-guide)：SSO、SCIM、座位管理和推出劇本

<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/server-managed-settings | lastmod: 2026-11-04 | section: Administration / Setup and access -->
> 來源：https://code.claude.com/docs/zh-TW/server-managed-settings（官方 zh-TW，lastmod 2026-11-04）｜分類：Administration › Setup and access｜EN 摘要：Centrally configure Claude Code for your organization through server-delivered settings, without requiring device management infrastructure.

# 設定伺服器管理的設定

> 透過伺服器傳遞的設定在您的組織中集中設定 Claude Code，無需裝置管理基礎設施。

伺服器管理的設定允許組織擁有者透過 claude.ai 主控台中的 [**Organization settings > Claude Code > Managed settings**](https://claude.ai/admin-settings/claude-code) 集中設定 Claude Code。當使用者在支援伺服器管理傳遞的平台上使用符合條件的憑證進行身分驗證時，Claude Code 用戶端會自動擷取這些設定。請參閱[平台可用性](#platform-availability)以了解符合條件的憑證和平台。

> [!NOTE]
>
> 伺服器管理的設定適用於 [Claude for Teams](https://claude.com/pricing?utm_source=claude_code\&utm_medium=docs\&utm_content=server_settings_teams#team-&-enterprise) 和 [Claude for Enterprise](https://anthropic.com/contact-sales?utm_source=claude_code\&utm_medium=docs\&utm_content=server_settings_enterprise) 客戶。

## 需求

若要使用伺服器管理的設定，您需要：

* Claude for Teams 或 Claude for Enterprise 方案
* 您的 Claude 組織中的擁有者或主要擁有者角色，以檢視和編輯配置
* 對 `api.anthropic.com` 的網路存取

## 在伺服器管理和端點管理的設定之間選擇

Claude Code 支援兩種集中設定方法。伺服器管理的設定從 Anthropic 的伺服器傳遞設定。[端點管理的設定](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms) 透過原生作業系統原則 (macOS 受管偏好設定、Windows 登錄) 或受管設定檔直接部署到裝置。

| 方法 | 最適合 | 安全模型 |
| :- | :- | :- |
| **伺服器管理的設定** | 沒有 MDM 的組織，或非受管裝置上的使用者 | Claude Code 在啟動時從 Anthropic 伺服器擷取的設定，並在工作階段期間每小時重新整理 |
| **[端點管理的設定](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)** | 具有 MDM 或端點管理的組織 | 透過 MDM 設定檔、登錄原則或受管設定檔部署到裝置的設定 |

如果您的裝置已在 MDM 或端點管理解決方案中註冊，端點管理的設定提供更強的安全保證，因為設定檔可以在作業系統層級受到保護，防止使用者修改。端點管理的設定不會到達 [雲端工作階段](https://code.claude.com/docs/zh-TW/model-config.md#surface-coverage) 在 Anthropic 代管的環境中，因此在網路上使用 Claude Code 的組織也應該設定伺服器管理的設定。[自我代管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments) 中的工作階段也會讀取執行器映像中的受管設定檔。下面的 [設定優先順序](#settings-precedence) 說明該檔案何時適用。

## 設定伺服器管理的設定

**1. 開啟管理員主控台**

在 claude.ai 主控台中，前往 [**Organization settings > Claude Code > Managed settings**](https://claude.ai/admin-settings/claude-code)。

在 Team 或 Enterprise 組織中，如果頁面顯示您沒有存取權，請要求[擁有者或主要擁有者](#access-control)進行變更。

**2. 定義您的設定**

將您的設定新增為 JSON。支援 [`settings.json` 中提供的所有設定](https://code.claude.com/docs/zh-TW/settings-reference#all-settings)，除了限制於作業系統層級原則傳遞的設定外；請參閱[目前的限制](#current-limitations)以取得該簡短清單。這包括 [hooks](https://code.claude.com/docs/zh-TW/hooks.md)、[環境變數](https://code.claude.com/docs/zh-TW/env-vars.md) 和[僅限受管的設定](https://code.claude.com/docs/zh-TW/managed-settings.md#managed-only-settings)，例如 `allowManagedPermissionRulesOnly`。

此範例強制執行權限拒絕清單，防止使用者繞過權限，並將權限規則限制為在受管設定中定義的規則。`Bash(curl *)` 規則符合 `curl` [如 Claude 所寫的](https://code.claude.com/docs/zh-TW/permissions.md#bash-rule-limits)，而不是 `/usr/bin/curl` 或 `sh -c 'curl …'`；對於不依賴命令文字的網路強制執行，請新增 [`sandbox` 區塊搭配 `allowManagedDomainsOnly`](https://code.claude.com/docs/zh-TW/sandboxing#configure-the-sandbox-for-your-organization)。

```json theme={null}
{
  "permissions": {
    "deny": [
      "Bash(curl *)",
      "Read(./.env)",
      "Read(./.env.*)",
      "Read(./secrets/**)"
    ],
    "disableBypassPermissionsMode": "disable"
  },
  "allowManagedPermissionRulesOnly": true
}
```

Hooks 使用與 `settings.json` 中相同的格式。

此範例在整個組織中的每次檔案編輯後執行稽核指令碼：

```json theme={null}
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          { "type": "command", "command": "/usr/local/bin/audit-edit.sh" }
        ]
      }
    ]
  }
}
```

因為 hooks 執行 shell 命令，使用者在互動式工作階段中會在 Claude Code 套用它們之前看到[安全核准對話方塊](#security-approval-dialogs)。

若要設定 [auto mode](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode) 分類器，使其知道您的組織信任哪些儲存庫、儲存桶和網域，請以相同方式傳遞 `autoMode` 區塊；請參閱[設定 auto mode](https://code.claude.com/docs/zh-TW/auto-mode-config.md)，了解 `autoMode` 項目如何影響分類器阻止的內容，以及關於 `environment`、`allow`、`soft_deny` 和 `hard_deny` 欄位的重要警告。

**3. 儲存並部署**

儲存您的變更。Claude Code 用戶端在下次啟動或每小時輪詢週期時會接收更新的設定。

編輯器會根據已發布的 Claude Code 設定 JSON schema 檢查您的 JSON。如果在可解析的 JSON 中發現問題，它會顯示警告並變更儲存按鈕的標籤。當設定已儲存時，標籤為 **Update with errors**；尚未儲存任何設定時，標籤為 **Add with errors**。該按鈕仍會儲存，因為 schema 警告不會阻止儲存。

schema [可能落後於最新版本](https://code.claude.com/docs/zh-TW/settings.md#edit-a-settings-file)，因此編輯器可能會標記[設定參考](https://code.claude.com/docs/zh-TW/settings-reference.md#all-settings)中有記載的鍵或值。Claude Code 會接收您儲存的鍵和值，並在載入時執行[其自身的驗證](#invalid-entries-in-delivered-settings)。

### 驗證設定傳遞

若要確認設定正在套用，請要求使用者重新啟動 Claude Code。如果設定包含觸發[安全核准對話方塊](#security-approval-dialogs)的設定，使用者會在 Claude Code 下次擷取設定時看到描述受管設定的提示：在下次啟動時，或在執行中的互動式工作階段中的一小時內。您也可以透過讓使用者執行 `/permissions` 來檢視其有效的權限規則，以驗證受管權限規則是否處於作用中。

若要檢查特定機器上的擷取結果，請讓使用者執行 `claude doctor` 並讀取 `Managed settings (remote)` 行。需要 Claude Code v2.1.248 或更新版本。該行報告以下四個結果之一：

* 已傳遞的設定已載入
* 您的組織未設定伺服器管理的設定
* 擷取失敗，包含原因以及是否仍然套用快取原則
* Claude Code 略過了擷取，包含原因。請參閱[平台可用性](#platform-availability)以了解略過擷取的提供者和設定

在擷取仍在進行中時，該行會改為報告該狀態。

在執行中的工作階段中，`/status` 在擷取失敗後會顯示相同的行，對於某些略過擷取的原因（例如第三方提供者變數或使用者 shell 中匯出的自訂 `ANTHROPIC_BASE_URL`），也會顯示。

### 存取控制

以下角色可以管理伺服器管理的設定：

* **主要擁有者**
* **擁有者**

限制對受信任人員的存取，因為設定變更會套用到組織中的所有使用者。

### 僅限受管的設定

大多數[設定金鑰](https://code.claude.com/docs/zh-TW/settings-reference.md#all-settings)可在任何範圍中運作。少數金鑰只能從受管設定中讀取，在放置於使用者或專案設定檔中時無效。請參閱[僅限受管的設定](https://code.claude.com/docs/zh-TW/managed-settings.md#managed-only-settings)以取得權限和外掛程式控制項，或讀取[所有設定](https://code.claude.com/docs/zh-TW/settings-reference.md#all-settings)索引的 Scope 欄以取得完整集合。

### 目前的限制

伺服器管理的設定有以下限制：

* 設定統一套用到組織中的所有使用者。尚不支援每個群組的設定。
* 您無法透過伺服器管理的設定分發 [`managed-mcp.json`](https://code.claude.com/docs/zh-TW/managed-mcp) 檔案。改為在該處傳遞 `allowedMcpServers` 和 `deniedMcpServers` 原則金鑰。在 Claude Code v2.1.259 或更新版本上，您也可以透過 [`managedMcpServers`](https://code.claude.com/docs/zh-TW/managed-mcp#provide-servers-through-managed-settings) 提供遠端伺服器，其僅接受 `http` 和 `sse` 伺服器，且不會以檔案的方式進行獨佔控制。

  Claude Code 在其[系統路徑](https://code.claude.com/docs/zh-TW/managed-mcp.md#exclusive-control-with-managed-mcp-json)部署的 `managed-mcp.json` 與受管設定層級分開讀取，因此當伺服器管理的設定生效時，檔案仍然適用。
* 限制於作業系統層級原則來源的設定，例如 `policyHelper` 和 `wslInheritsWindowsSettings`，不會被接受。改為透過 MDM 或系統 `managed-settings.json` 檔案部署它們。`policyHelper` 以該方式部署時，只有在其來源是在[受管層級內的優先順序](https://code.claude.com/docs/zh-TW/managed-settings.md#precedence-within-the-managed-tier)下選擇的來源時，才會執行。

## 設定傳遞

### 設定優先順序

伺服器受管設定與[端點受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)同樣位於 Claude Code [設定階層](https://code.claude.com/docs/zh-TW/settings.md#settings-precedence)的最高層級。在此設定的鍵優先於使用者自己的設定檔或 `--settings` 值中的相同鍵，但[受管設定優先順序的例外](https://code.claude.com/docs/zh-TW/settings.md#exceptions-to-managed-settings-precedence)除外。

在受管層級內，Claude Code 預設會使用第一個傳遞至少一個政策鍵的來源，先檢查伺服器受管設定，再檢查端點受管設定，但[接下來說明的例外鍵](#per-key-exceptions-across-managed-sources)除外。[Claude Code 如何組合受管來源](https://code.claude.com/docs/zh-TW/managed-settings.md#precedence-within-the-managed-tier)提供完整的排序、控制鍵的例外規定，以及套用所有來源的選擇性啟用方式。

如果所選來源是 MDM 政策或受管設定檔，且其 [`policyHelper`](https://code.claude.com/docs/zh-TW/settings-reference#policyhelper) 提供受管設定，則該 helper 的輸出會取代該來源，成為此次執行唯一的受管組態。當伺服器受管設定傳遞了政策鍵時，Claude Code 不會參考在 MDM 或檔案型設定中設定的 `policyHelper`。

如果之後的擷取發現伺服器受管設定已被移除，Claude Code 會立即執行該 helper，而不是等到下次啟動。[`policyHelper`](https://code.claude.com/docs/zh-TW/settings-reference#policyhelper) 項目說明了該次執行失敗時會發生什麼情況。

如果您在管理主控台中清除伺服器受管組態，打算改為回退至端點受管的 plist 或登錄檔政策，請注意[快取的設定](#fetch-and-caching-behavior)會保留在用戶端電腦上，直到下一次成功擷取為止，而[僅在下次啟動時套用](#fetch-and-caching-behavior)的鍵（例如 `model`）在每個用戶端重新啟動之前都會持續生效。執行 `/status` 可查看目前生效的受管來源。

### 跨受管來源的個別鍵例外

以下鍵是不合併規則的例外：

* **跨來源鎖定鍵**：一小組鍵，例如沙箱允許清單鎖定，[列於受管設定頁面](https://code.claude.com/docs/zh-TW/managed-settings.md#precedence-within-the-managed-tier)。只要任何由管理員控制的受管來源設定了這些鍵，Claude Code 就會遵循；使用者可寫入的 HKCU 登錄檔層級則排除在外。

  當 [`policyHelper`](https://code.claude.com/docs/zh-TW/settings-reference#policyhelper) 提供受管設定時，其輸出是這些檢查唯一讀取的來源，但 [`forceRemoteSettingsRefresh`](https://code.claude.com/docs/zh-TW/settings-reference#forceremotesettingsrefresh) 除外，Claude Code 會在啟動時直接從管理來源讀取該鍵。
* **`env` 區塊**：除了遙測單元以及與憑證鍵配對的路由變數（兩者都在下方說明）之外，此區塊會在由管理員控制的來源之間逐鍵合併。對於每個環境變數，定義該變數的最高優先順序來源勝出，而較低的管理來源會補上較高來源未設定的變數。因此，只要伺服器受管組態未設定某個變數，或該變數的快取伺服器值正[等待伺服器確認而被暫緩](#fetch-and-caching-behavior)，端點受管的 `env` 項目就會套用。需要 Claude Code v2.1.223 或更新版本。在 v2.1.223 之前，Claude Code 只會套用所選來源的整個 `env` 區塊。
  * **遙測單元**：`OTEL_EXPORTER_OTLP_*` 匯出器鍵、`OTEL_LOG_*` 內容擷取切換、`OTEL_LOGS_EXPORTER`，以及 beta 追蹤變數 `ENABLE_BETA_TRACING_DETAILED` 和 `BETA_TRACING_ENDPOINT`，會以單元形式跟隨設定其中任一項的最高來源。傳遞 `otelHeadersHelper` 憑證鍵的來源也會佔據此單元，但只有在它是所選來源時才會套用這些變數：未被選取但傳遞了該鍵的來源不會提供其中任何變數，且仍會阻止較低來源補上這些變數。無論哪種情況，來自某個來源的匯出器端點都絕不會與來自另一個來源的憑證配對。
  * **與憑證配對的路由**：將路由變數與僅限所選來源的憑證鍵（例如 `apiKeyHelper` 或 `otelHeadersHelper`）配對的來源，只有在贏得該位置時才會提供這些路由變數。
* **`allowedProviders`**：在電腦上設定的清單與伺服器受管清單，會依照[其項目的範圍說明](https://code.claude.com/docs/zh-TW/settings-reference.md#allowedproviders)所述方式組合。需要 Claude Code v2.1.285 或更新版本
* **第一方登入鍵**：[`forceLoginOrgUUID`](https://code.claude.com/docs/zh-TW/settings-reference#forceloginorguuid) 以及 [`forceLoginMethod`](https://code.claude.com/docs/zh-TW/settings-reference#forceloginmethod) 的 `"claudeai"` 和 `"console"` 值。如果您也部署了 MDM 政策或受管設定檔，請在每個用戶端都執行 v2.1.299 或更新版本之前，同時在該處以及 claude.ai 的伺服器受管設定中設定這些鍵。關於之後應在何處設定這些鍵，以及套用哪個來源的值，請參閱[哪個受管來源提供登入鍵](https://code.claude.com/docs/zh-TW/managed-settings.md#which-managed-source-supplies-login-keys)。
* **閘道登入鍵**：Claude Code 絕不會從伺服器受管設定讀取 [`forceLoginGatewayUrl`](https://code.claude.com/docs/zh-TW/settings-reference#forcelogingatewayurl)、[`gatewayInternalNetworks`](https://code.claude.com/docs/zh-TW/settings-reference#gatewayinternalnetworks) 或 [`forceLoginMethod`](https://code.claude.com/docs/zh-TW/settings-reference#forceloginmethod) 的 `"gateway"` 值，因此在那裡設定的值既不會套用，也不會遮蔽在 MDM 政策或受管設定檔中設定的值。[`managedSourcesBehavior` 項目](https://code.claude.com/docs/zh-TW/settings-reference#managedsourcesbehavior)說明了由電腦上的哪個管理來源提供這些值。

#### 當電腦的 `apiKeyHelper` 未生效時

當您的伺服器受管設定是所選來源時，電腦受管設定檔或 MDM 政策中的 `apiKeyHelper` 不會生效。此時，只要下列兩項條件都成立，Claude Code 就會在會使用已儲存 claude.ai 登入的工作階段中[拒絕提示詞](https://code.claude.com/docs/zh-TW/errors.md#claude-code-didnt-send-your-claude-ai-login)：

* 該檔案或政策啟用了雲端提供者，或任何來源設定了 Anthropic 以外的 API 位址
* 伺服器受管設定未設定 helper，也未指定 Anthropic 的 API 位址

若要解除拒絕，請讓 helper 及其 API 位址保持生效、在伺服器受管設定中指定 Anthropic 的 API 位址，或從電腦的政策中移除該 helper。此拒絕行為需要 Claude Code v2.1.314 或更新版本。

### 擷取與快取行為

Claude Code 會在啟動時從 Anthropic 的伺服器擷取設定，並在作用中的工作階段期間每小時輪詢更新。

透過 [Claude apps 閘道](#platform-availability)登入的用戶端會從閘道擷取設定，並在工作階段開始前等待該擷取完成，因此下列清單中的擷取不適用於此類用戶端。[強制失敗即關閉的啟動](#enforce-fail-closed-startup)說明了該擷取失敗時會發生什麼情況。

**沒有快取設定的首次啟動：**

* 當開發人員在啟動時登入，例如首次執行或執行 `/logout` 之後，Claude Code 會在開啟工作階段之前等待擷取最多五秒。若政策及時送達，Claude Code 會從第一個畫面就強制執行該政策，並在該畫面上顯示您的 [`companyAnnouncements`](https://code.claude.com/docs/zh-TW/settings-reference#companyannouncements)。若 payload 需要[安全性核准](#security-approval-dialogs)，Claude Code 會結束等待，並在開發人員核准後套用該 payload
* 在任何其他啟動情況下，以及五秒等待逾時時，Claude Code 會在擷取持續進行的同時開啟工作階段，因此在設定載入且限制生效之前會有一段短暫的空窗期
* 如果擷取失敗，Claude Code 會在沒有伺服器受管設定的情況下繼續執行，並在互動式工作階段以及 [Claude Desktop 的 Code 分頁](https://code.claude.com/docs/zh-TW/desktop.md)中警告沒有套用任何遠端政策；端點受管設定仍會套用。如果受管來源設定了 [`forceRemoteSettingsRefresh`](#enforce-fail-closed-startup)，Claude Code 則會改為結束

**具有快取設定的後續啟動：**

* 快取的設定會在啟動時立即套用，但以下項目除外：快取的 `modelPricing` 和 `managedMcpServers` 值；Claude Code 在伺服器確認 payload 之前暫緩的環境變數；快取的外掛清單對[內建防護](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md#know-what-happens-by-default)所做的移除、重新定位或停用；以及在端點受管來源自行列出或啟用外掛的電腦上，僅由快取清單啟用之外掛的[組織歸屬](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md#install-your-organizations-mods)
* 快取的 [`modelPricing`](https://code.claude.com/docs/zh-TW/settings-reference#modelpricing) 在工作階段的擷取確認 payload 之前不會套用。在那之前，開發人員在 `/usage` 和狀態列中看到的費用數字皆為定價
* 快取的 [`managedMcpServers`](https://code.claude.com/docs/zh-TW/settings-reference#managedmcpservers) 區塊在工作階段的擷取確認 payload 之前不會套用。Claude Code 會在連線 MCP 伺服器之前等待該擷取最多 30 秒。如果擷取失敗或逾時，工作階段會在沒有組織伺服器的情況下啟動，`/status` 會註明此情況，而這些伺服器會在之後的擷取確認它們後連線。如需完整行為（包括首次啟動），請參閱[提供的伺服器何時連線](https://code.claude.com/docs/zh-TW/managed-mcp.md#when-provided-servers-connect)。需要 Claude Code v2.1.259 或更新版本
* 快取的 [`prependPlugins`](https://code.claude.com/docs/zh-TW/settings-reference#prependplugins)、[`appendPlugins`](https://code.claude.com/docs/zh-TW/settings-reference#appendplugins) 或 [`enabledPlugins`](https://code.claude.com/docs/zh-TW/settings-reference#enabledplugins) 值，在工作階段的擷取確認 payload 之前，無法移除內建防護、變更其位置或將其關閉
* 在[端點受管來源](https://code.claude.com/docs/zh-TW/managed-settings.md#choose-a-delivery-mechanism)自行列出或啟用外掛的電腦上，僅由快取清單啟用的外掛在擷取確認 payload 之前，會被視為[使用者的](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md#install-your-organizations-mods)外掛，而非您組織的外掛
* Claude Code 會在背景擷取最新設定
* 快取的設定在網路故障期間會持續保留。如果啟動時的擷取失敗，Claude Code 會在互動式工作階段以及 Code 分頁中警告目前生效的是快取的政策
* 在擷取成功之前，啟動時暫緩的值會持續暫緩

Claude Code 會暫緩快取 `env` 區塊中的數類變數，直到伺服器確認該工作階段的 payload 為止。這可防止快取的代理伺服器、憑證授權單位、端點或憑證值重新導向、攔截或重新驗證用來確認 payload 的設定擷取。此強化措施僅適用於從伺服器擷取的設定快取：透過 MDM 或 `managed-settings.json` 部署的[端點受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)不受影響。暫緩的類別包括：

* 代理伺服器與 TLS 組態，例如 `HTTPS_PROXY`、`NODE_EXTRA_CA_CERTS`，以及 mTLS 用戶端憑證變數 `CLAUDE_CODE_CLIENT_CERT` 和 `CLAUDE_CODE_CLIENT_KEY`
* API 路由與提供者選擇，包括 `ANTHROPIC_BASE_URL`、提供者選擇變數（例如 `CLAUDE_CODE_USE_BEDROCK` 和 `CLAUDE_CODE_USE_VERTEX`），以及提供者端點 URL（例如 `ANTHROPIC_BEDROCK_BASE_URL`）
* 身分驗證憑證，例如 `ANTHROPIC_API_KEY`、`ANTHROPIC_AUTH_TOKEN` 和 `CLAUDE_CODE_OAUTH_TOKEN`
* 設定目錄選擇器 `CLAUDE_CONFIG_DIR`
* 憑證來源與設定目錄選擇器（Claude Code v2.1.223 或更新版本）：Workload Identity Federation 變數（例如 `ANTHROPIC_FEDERATION_RULE_ID` 和 `ANTHROPIC_IDENTITY_TOKEN`）、設定檔與設定目錄選擇器 `ANTHROPIC_PROFILE` 和 `ANTHROPIC_CONFIG_DIR`，以及作業系統目錄變數 `HOME`、`XDG_CONFIG_HOME`、`APPDATA` 和 `USERPROFILE`

Claude Code 只在啟動時讀取 Workload Identity Federation 變數以及 `ANTHROPIC_PROFILE` 和 `ANTHROPIC_CONFIG_DIR` 選擇器，因此即使擷取成功，伺服器傳遞的這些值也不會切換工作階段的憑證來源。若要在 Claude Code v2.1.223 或更新版本上傳遞這些選擇器，請使用[端點受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)，例如 MDM 或 `managed-settings.json`。對於 `CLAUDE_CONFIG_DIR` 和作業系統目錄變數，暫緩本身就是保護措施：快取的值在伺服器確認 payload 之前都不會進入環境。

快取 `env` 區塊中的其他所有鍵都會在啟動時套用。一旦伺服器確認了 payload，且若該 payload 需要[安全性核准](#security-approval-dialogs)而您已核准，暫緩的變數就會在工作階段的剩餘時間內套用。

如果您的組織需要透過代理伺服器才能連線到 `api.anthropic.com`，暫緩只會影響伺服器傳遞的 `env` 區塊本身：透過 MDM 或 `managed-settings.json` 在[端點受管](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms) `env` 區塊中設定的代理伺服器、在 shell 環境中設定的代理伺服器，或在[使用者設定](https://code.claude.com/docs/zh-TW/settings.md#where-settings-live)中設定的代理伺服器，都能用於設定擷取。端點受管來源需要 Claude Code v2.1.223 或更新版本：快取的伺服器受管代理伺服器值在擷取確認之前會被暫緩，因此端點受管的值會逐鍵補上，並用於擷取本身。在 v2.1.223 之前，請使用 shell 環境或使用者設定，讓代理伺服器能與快取的伺服器 payload 一起套用。首次啟動時沒有快取，因此初次擷取仍需要端點受管來源、shell 環境或使用者設定。

Claude Code 會在不需重新啟動的情況下，將大多數設定更新套用至執行中的工作階段。部分更新僅在下次啟動時套用，包括 OpenTelemetry 匯出器組態、`model` 鍵，以及從 `env` 區塊中移除變數。

### 傳遞設定中的無效項目

當 payload 的一部分未通過 schema 驗證時，Claude Code 會顯示驗證錯誤，並套用其餘所有有效的設定；[受管設定中的無效項目](https://code.claude.com/docs/zh-TW/managed-settings.md#invalid-entries-in-managed-settings)說明了它會捨棄哪些內容，以及哪些鍵會回退至較嚴格的值。需要 Claude Code v2.1.169 或更新版本。

伺服器受管傳遞另外具有以下行為：

* 以 `~/.claude/remote-settings.json` 快取執行的啟動，會以寫入該快取的擷取相同的方式處理無效項目：
  * 未通過驗證的項目會持續被捨棄。
  * [失敗即關閉的鍵](https://code.claude.com/docs/zh-TW/managed-settings.md#keys-that-fail-closed)會保留其較嚴格的值。
  * 無效的 `cleanupPeriodDays` 或 `desktopSessionCleanupPeriodDays` 值會保留在快取副本中，且永遠不會套用。
* 當以下三項條件全部成立時，Claude Code 不會套用 payload 中的任何內容，並保持快取不變：

  * payload 中的每個設定都未通過驗證。
  * 其中沒有任何設定回退至較嚴格的值。
  * payload 包含上述兩個保留期鍵以外的鍵。

  此時啟動通知、`/status` 和 `claude doctor` 會回報[載入失敗](https://code.claude.com/docs/zh-TW/errors.md#remote-managed-settings-failed-to-load)，原因為 `no setting in the server response could be applied as written`，且該項目會說明工作階段執行時所依據的政策。[強制失敗即關閉的啟動](#enforce-fail-closed-startup)的用戶端則會改為在啟動時結束。
* [安全性核准對話框](#security-approval-dialogs)會評估挽救後的 payload，因此被移除的無效項目永遠不會呈現供核准，也永遠不會執行。

若要偵錯傳遞問題，請執行 `claude --debug-file <path>` 並在日誌中搜尋 `Remote settings`。在將 payload 變更推出至組織之前，請先在測試電腦上使用 `claude doctor` 驗證。

### 強制失敗即關閉的啟動

預設情況下，如果遠端設定擷取在啟動時失敗，CLI 會使用上次成功擷取時快取的設定繼續執行，但 Claude Code 在擷取成功前[暫緩的值](#fetch-and-caching-behavior)除外。在從未擷取過設定的電腦上，CLI 會在沒有伺服器受管設定的情況下繼續執行，並仍會套用裝置上的任何[端點受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)。

若要阻止用戶端在快取或缺少伺服器受管設定的情況下啟動，請在受管設定中設定 `forceRemoteSettingsRefresh: true`。

透過 [Claude apps 閘道](#platform-availability)登入的用戶端無論是否設定此項，都會等待啟動時的擷取，並依下列方式處理失敗的擷取：

* 如果閘道以 `401` 回應有人操作的互動式啟動，且此設定為關閉，表示閘道已結束該次登入。Claude Code 會顯示 [`Cloud gateway session expired — run /login to reconnect.`](https://code.claude.com/docs/zh-TW/errors#cloud-gateway-session-expired)，並在使用者執行 `/login` 之前以登出閘道的狀態開啟工作階段。
* 當擷取以其他任何方式失敗，或在 `claude auth` 子命令以外的任何其他類型的啟動中失敗時，用戶端會以錯誤結束。

當此設定在擷取伺服器受管設定的工作階段中生效時，CLI 會在啟動時阻擋，直到重新擷取到遠端設定為止。如果擷取失敗，CLI 會結束，而不是在沒有政策的情況下繼續。此設定會自我延續：一旦從伺服器傳遞，它也會在本機快取，因此後續啟動在新工作階段首次成功擷取之前，也會強制執行相同的行為。[不擷取伺服器受管設定](#platform-availability)的工作階段則會直接啟動，不會等待。

若要啟用此功能，請將該鍵加入您的受管設定組態：

```json theme={null}
{
  "forceRemoteSettingsRefresh": true
}
```

您也可以在[端點受管](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)的 MDM 設定檔或系統 `managed-settings.json` 檔案中設定此鍵，以便在任何伺服器 payload 送達之前的首次啟動時強制執行失敗即關閉的行為。此旗標是上述[優先順序規則](#settings-precedence)的例外：只要任何由管理員控制的受管來源設定了此旗標，Claude Code 就會遵循，即使同時存在快取的伺服器受管 payload 也是如此，因此當伺服器受管設定存在時，它不會忽略由 MDM 傳遞的值。

當 [`policyHelper`](https://code.claude.com/docs/zh-TW/settings-reference#policyhelper) 提供受管設定時，對於 Claude Code 在啟動後讀取的鍵，其輸出會取代所有其他受管來源。關於 Claude Code 從哪些來源讀取此鍵，請參閱[其設定項目](https://code.claude.com/docs/zh-TW/settings-reference.md#forceremotesettingsrefresh)。`policyHelper` 項目說明了 Claude Code 從哪些來源讀取該 helper 以及其執行時機。

設定擷取也會傳送 `Cache-Control: no-cache` 標頭，以免中介的 HTTP 代理伺服器提供過時的回應。

啟用此設定之前，請確認您的網路政策允許連線至 `api.anthropic.com`。如果無法連線至該端點，CLI 會在啟動時結束，使用者將無法啟動 Claude Code。

`claude auth` 子命令（例如 `claude auth login`）不受此檢查及閘道啟動結束的限制，因此當憑證過期是設定擷取失敗的原因時，使用者仍可重新驗證。

### 安全性核准對話框

某些可能帶來安全風險的設定，在 Claude Code 於互動式工作階段中套用之前，需要使用者明確核准：

* **Shell 命令設定**：執行 shell 命令的設定，例如 `apiKeyHelper`、`statusLine` 和 `otelHeadersHelper`
* **沙箱二進位檔設定**：`sandbox.bwrapPath`、`sandbox.socatPath` 和 `sandbox.ripgrep`。這些設定各自指向一個可執行檔，而 Claude Code 會執行該可執行檔
* **沙箱網路與隔離設定**：讓沙箱代理伺服器能讀取、重新路由或驗證流量，或削弱沙箱隔離的[沙箱](https://code.claude.com/docs/zh-TW/sandboxing.md)設定：`sandbox.network.tlsTerminate`、`sandbox.network.httpProxyPort`、`sandbox.network.socksProxyPort`、`sandbox.credentials`、`sandbox.allowAppleEvents`、`sandbox.allowNestedUserNamespaces`、`sandbox.enableWeakerNestedSandbox`、`sandbox.enableWeakerNetworkIsolation`、`sandbox.filesystem.disabled`、`sandbox.network.allowAllUnixSockets`、`sandbox.network.allowUnixSockets` 和 `sandbox.network.allowMachLookup`。僅包含 `deny` 規則的 `sandbox.credentials` 區塊不需要核准，因為它只是限制沙箱，並未提供憑證給代理伺服器。在 v2.1.251 之前，Claude Code 會在未經核准的情況下套用這些設定
* **自訂環境變數**：需要使用者核准的傳遞 `env` 變數，例如代理伺服器與 base-URL 變數；請參閱[環境變數與核准對話框](#environment-variables-and-the-approval-dialog)
* **Hook 組態**：任何 hook 定義

當這些設定存在時，使用者會看到一個安全性對話框，說明正在設定的內容。使用者必須核准才能繼續。如果使用者拒絕這些設定，Claude Code 會結束。

透過 [`claudeMd`](https://code.claude.com/docs/zh-TW/settings-reference#claudemd) 鍵傳遞的受管 CLAUDE.md 不需要核准，因為它是給 Claude 的指令文字，而不是 Claude Code 執行的命令。Claude Code 仍會檢查 Claude 在遵循這些指令時所使用工具的[權限](https://code.claude.com/docs/zh-TW/permissions.md)。在 v2.1.260 之前，`claudeMd` 值也需要核准。

#### 核准記憶

Claude Code 會將您的核准記錄在您的設定目錄中，除非您設定了 [`CLAUDE_CONFIG_DIR`](https://code.claude.com/docs/zh-TW/env-vars)，否則該目錄為 `~/.claude`。它記錄的內容取決於設定擷取所使用的憑證：

* **由 `/login` 或 `claude auth login` 儲存的 claude.ai 登入，或[無金鑰 Console 登入](https://code.claude.com/docs/zh-TW/authentication.md#sign-in-without-an-api-key)**：每個組織一個核准，由最近一次核准的帳戶持有。
* **[Claude apps 閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)登入**：每個閘道一個核准。

  如果您登出後再登入同一個閘道，只要需要核准的設定未變更，Claude Code 就不會再次顯示對話框。當這些設定變更、您登入不同的閘道，或您為同一個閘道接受新的憑證時，Claude Code 會再次顯示對話框。

  對於透過純 HTTP 連線的本機迴路開發閘道，Claude Code 不會儲存核准，因此每次登入後都會再次出現對話框。
* **任何其他憑證**，例如 API 金鑰或 `CLAUDE_CODE_OAUTH_TOKEN`：對傳遞的設定一個核准，與該設定目錄中的設定快取副本一起保存。當需要核准的設定變更時，以及在您執行 `/logout` 或 `claude auth logout`（兩者都會刪除快取副本）之後，Claude Code 會再次顯示對話框。

對 `sandbox.credentials` 或 `sandbox.network.tlsTerminate` 的核准，也涵蓋同一份傳遞設定中的 [`sandbox.network.allowedDomains`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-network-alloweddomains) 項目，因為這兩個設定都作用於該允許清單。當您的管理員新增或移除其中一個項目時，對話框會再次出現，即使 `sandbox.network.allowedDomains` 本身不需要核准。

使用已儲存的 claude.ai 登入時：

* 如果您登出後再登入，或切換到另一個組織後再返回，只要這些設定未變更，Claude Code 就不會再次顯示對話框，除非在此期間另一個帳戶已在同一個設定目錄中為該組織核准過這些設定。
* 如果您使用不同的帳戶登入同一個組織，即使設定未變更，Claude Code 也會再次顯示對話框。該帳戶的核准會取代先前的核准，因此當您切換回來時，Claude Code 會再顯示一次對話框。

Claude Code 並非總是能顯示對話框。以下每種情況都說明了無法顯示時套用哪些設定，以及您下次何時會看到對話框：

* **無法顯示對話框的互動式工作階段**：Claude Code 不會套用傳遞的設定，並保留上次核准的設定。對話框會出現在下一個能顯示它的工作階段中。
* **`claude install` 或 `claude update`**：Claude Code 在這兩個命令執行期間都不會顯示對話框。命令會以上次核准的設定執行，對話框則會出現在您的下一個互動式工作階段中。如果 Claude Code 在啟動時等待設定擷取，例如設定了 [`forceRemoteSettingsRefresh`](#enforce-fail-closed-startup) 或在 [Claude apps 閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)部署上，它會改為在命令執行期間顯示對話框，而從管道執行的安裝會失敗；請參閱[安裝期間出現 `Raw mode is not supported`](https://code.claude.com/docs/zh-TW/troubleshoot-install#raw-mode-is-not-supported-during-install)。在 v2.1.246 之前，Claude Code 也會嘗試在這兩個命令執行期間顯示對話框。
* **輸出至終端機但無法從鍵盤讀取的 `claude plugin` 命令**：當 Claude Code 未在啟動時等待設定擷取時，該命令不會套用傳遞的設定。若沒有[快取的設定](#fetch-and-caching-behavior)，變更您的外掛或市集的命令會[以錯誤停止](https://code.claude.com/docs/zh-TW/errors.md#managed-settings-need-your-approval)。若有快取的設定，命令會以上次核准的設定執行。對話框會在您下次於終端機中執行 `claude` 時出現。

  當您以管道傳送或重新導向該命令的輸入，且在 macOS 和 Linux 上它也無法開啟 `/dev/tty` 時，該命令就無法從鍵盤讀取。如果您也以管道傳送或重新導向其輸出，該次執行則會改為非互動式，而傳遞的設定只會在該次執行中套用。
* **錯誤在您回答之前關閉了對話框**：Claude Code 不會套用傳遞的設定，並保留上次核准的設定。它會在下一個能顯示對話框的工作階段中再次顯示。
* **非互動式執行**，例如 `claude -p`、Agent SDK 工作階段，或 VS Code 擴充功能聊天面板或桌面應用程式 Code 分頁中的工作階段：Claude Code 無法顯示對話框。當傳遞的設定需要核准時，這些設定只會在該次執行中套用。

  Claude Code 不會將這些設定記錄為已核准，也不會將其寫入[本機快取](#fetch-and-caching-behavior)，而下一個互動式工作階段會顯示對話框。在使用者於互動式工作階段中核准之前，每次非互動式執行都會在啟動時再次擷取設定。

#### 環境變數與核准對話框

Claude Code 會在不向使用者顯示核准對話框的情況下套用部分傳遞的 `env` 變數，包括：

* 功能與命令切換
* 模型選擇與行為設定，例如 `ANTHROPIC_MODEL`、`DISABLE_PROMPT_CACHING` 和 `CLAUDE_CODE_EFFORT_LEVEL`
* 上下文視窗與壓縮設定，例如 `DISABLE_AUTO_COMPACT`，但不包括 `CLAUDE_CODE_DISABLE_1M_CONTEXT`
* 終端機 UI 與無障礙選項
* 數值限制、預算與逾時

其他傳遞的變數可能需要使用者核准才會生效。例如，在互動式工作階段中，以下變數只要是非空值就一律需要核准：

* 代理伺服器或 base-URL 變數
* `OTEL_EXPORTER_OTLP_ENDPOINT`
* `CLAUDE_CODE_DISABLE_1M_CONTEXT`

當傳遞的變數需要核准時，對話框會列出其名稱，讓使用者確切看到政策要求設定的內容。

Claude Code 會依據傳遞的值而非變數名稱，來決定四個隱私切換是否需要核准：`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`、`DISABLE_ERROR_REPORTING`、`DISABLE_TELEMETRY` 和 `DO_NOT_TRACK`。真值（例如 `1` 或 `true`）只會關閉追蹤、回報或其他非必要流量，因此 Claude Code 會在不詢問使用者的情況下套用。對於任何其他非空值，Claude Code 會顯示對話框。

Claude Code 也會依據傳遞的值來決定 [`API_FORCE_IDLE_TIMEOUT`](https://code.claude.com/docs/zh-TW/env-vars) 是否需要核准：真值只會開啟[主體閒置逾時](https://code.claude.com/docs/zh-TW/network-config.md#streaming-idle-watchdogs)，因此 Claude Code 會在不詢問使用者的情況下套用。對於任何其他非空值，Claude Code 會顯示對話框。在 v2.1.248 之前，任何非空值都會觸發對話框。

[`ANTHROPIC_CUSTOM_HEADERS`](https://code.claude.com/docs/zh-TW/env-vars#variables) 是否需要核准也取決於傳遞的值。僅用於標記請求的標頭（例如 `Accept-Language`）無需對話框即可套用。指定憑證、組織或租用戶選擇器、路由或主機覆寫，或 API 行為標頭的行（例如 `Authorization`、`X-Api-Key`、`Host`、`anthropic-beta` 或 `X-Amzn-Bedrock-*` 標頭）需要核准。當某行的名稱不是有效的 HTTP 標頭 token，或其值包含 HTTP 標頭無法承載的字元時，該行也需要核准。此檢查會比對標頭名稱內的字詞，因此包含 `client` 和 `version` 的 `X-Client-Version` 也需要核准。在 v2.1.251 之前，任何 `ANTHROPIC_CUSTOM_HEADERS` 值都無需核准即可套用。

[`ENABLE_BETA_TRACING_DETAILED`](https://code.claude.com/docs/zh-TW/env-vars#variables) 或 [`OTEL_LOG_RAW_API_BODIES`](https://code.claude.com/docs/zh-TW/env-vars#variables) 的假值（例如 `0` 或 `false`）無需對話框即可套用，因為它只會關閉詳細追蹤或原始 API 主體擷取。這兩個變數的任何其他非空值都需要核准。

## 平台可用性

伺服器受管設定需要直接連線至 `api.anthropic.com`。傳遞設定還需要工作階段使用下列其中一種憑證進行身分驗證：

* Team 或 Enterprise OAuth 登入
* 透過 `CLAUDE_CODE_OAUTH_TOKEN` 提供的 OAuth token
* 直接設定的 API 金鑰
* `user_oauth` [Anthropic 設定檔](https://code.claude.com/docs/zh-TW/authentication.md#anthropic-profiles-and-federation-credentials)，除非該設定檔將 `base_url` 設為 Anthropic API 以外的位址。需要 Claude Code v2.1.257 或更新版本。

由 [`apiKeyHelper`](https://code.claude.com/docs/zh-TW/settings-reference#apikeyhelper) 指令碼傳回的金鑰，以及 [Workload Identity Federation](https://platform.claude.com/docs/en/manage-claude/workload-identity-federation) 憑證，都不會觸發設定擷取。

工作階段會收到其用於身分驗證之憑證所屬組織的受管設定。來自 [Claude Console](https://platform.claude.com) 的 API 金鑰屬於建立該金鑰的 Console 組織，而該組織與您的 claude.ai Team 或 Enterprise 組織是不同的組織。因此，您在 claude.ai 管理設定中設定的內容，不會套用至使用該金鑰進行身分驗證的工作階段，例如使用貴公司 Console API 金鑰的 CI 作業。若要將這些設定套用至該作業，請使用下列其中一個選項。OAuth token 選項不適用於以 [`--bare`](https://code.claude.com/docs/zh-TW/headless#start-faster-with-bare-mode) 執行的作業，因為 bare 模式不會讀取 `CLAUDE_CODE_OAUTH_TOKEN`。

* **OAuth token**：使用 [`claude setup-token`](https://code.claude.com/docs/zh-TW/authentication#generate-a-long-lived-token) 產生 token，為您的 Team 或 Enterprise 組織授權該 token，並在作業的環境中將其設為 `CLAUDE_CODE_OAUTH_TOKEN`。從該環境中移除任何[優先於](https://code.claude.com/docs/zh-TW/authentication.md#authentication-precedence)該 token 的憑證，例如 `ANTHROPIC_API_KEY`。
* **端點受管設定**：將[受管設定檔](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)部署至執行該作業的機器。

在 Claude Desktop 應用程式的 [Cowork](https://claude.com/docs/cowork/overview) 工作階段中，即使使用者以 Team 或 Enterprise 帳戶登入，Claude Code 也不會從 claude.ai 管理主控台擷取伺服器受管設定。[政策的套用位置與時機](https://code.claude.com/docs/zh-TW/managed-settings.md#where-and-when-a-policy-applies)說明了哪些政策會套用至使用者機器上的 Cowork 工作階段以及遠端 Cowork 工作階段。當 Cowork 使用者在 claude.ai 上從 git 儲存庫新增市集，或從 Cowork 中的 **Customize** 新增市集時，claude.ai 仍會自行套用您的 [`strictKnownMarketplaces`](https://code.claude.com/docs/zh-TW/settings-reference#strictknownmarketplaces) 和 [`blockedMarketplaces`](https://code.claude.com/docs/zh-TW/settings-reference#blockedmarketplaces) 清單。[限制的運作方式](https://code.claude.com/docs/zh-TW/plugins/org.md#restrict-what-users-can-install)說明了該檢查。

如果您在 shell 中匯出 `CLAUDE_CODE_USE_*` 提供者變數或非預設的 `ANTHROPIC_BASE_URL`，Claude Code 會為您的工作階段略過設定擷取。[`claude doctor` 和 `/status` 會回報已略過的擷取及其原因](#verify-settings-delivery)。

您無法使用伺服器受管的 `env` 區塊清除該匯出，因為該區塊是透過被該匯出阻止的擷取而送達的。[端點受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)的 `env` 區塊也無法恢復擷取：Claude Code 會在套用受管 `env` 區塊之前檢查資格，因此端點受管的值會變更工作階段的提供者選擇，但擷取仍會被略過。

若要恢復伺服器受管的傳遞，請從您的 shell 中移除該匯出，或在您的使用者設定 `env` 區塊中將該變數設為 `""`，該區塊會在資格檢查之前套用。若要在不依賴使用者變更其 shell 的情況下強制執行政策，請改為透過端點受管頻道傳遞設定。

對於 Amazon Bedrock、Google Cloud 的 Agent Platform、Microsoft Foundry 以及 [Claude Platform on AWS](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md) 部署，自行託管的 [Claude apps 閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)提供等效的遠端受管設定傳遞：透過閘道登入的用戶端會從閘道而非 `api.anthropic.com` 擷取受管設定。啟動時的失敗處理方式有所不同：無法連線至閘道的閘道用戶端會以錯誤結束，而不會退回使用快取的設定；而每小時的背景重新整理在兩個頻道上都採用失敗開放（fail-open）模式，也就是重新整理失敗時仍允許工作階段繼續運作。

## 稽核記錄

設定變更的稽核記錄事件可透過合規性 API 或稽核記錄匯出取得。請聯絡您的 Anthropic 帳戶團隊以取得存取權。

稽核事件包括執行的動作類型、執行動作的帳戶和裝置，以及對先前和新值的參考。

## 安全考量

伺服器管理的設定提供集中式原則強制執行，但它們作為用戶端控制運作，而非安全邊界。在非受管裝置上，使用者不需要管理員或 sudo 存取權就能略過它們。

| 情況 | 行為 |
| :- | :- |
| 使用者編輯快取的設定檔 | 篡改的檔案在啟動時套用，但 Claude Code 會[保留某些值](#fetch-and-caching-behavior)直到伺服器確認承載。下次伺服器擷取會還原正確的設定，但[只在下次啟動時套用的金鑰](#fetch-and-caching-behavior)（例如 `model` 或新增至 `env` 區塊的變數）會保持有效，直到重新啟動 |
| 使用者刪除快取的設定檔 | [首次啟動行為](#fetch-and-caching-behavior)發生 |
| 使用者執行修改過的 Claude Code 二進位檔 | 能夠執行修改過用戶端的使用者可以略過任何用戶端控制 |
| 使用者執行較舊的 Claude Code 版本 | 早於伺服器管理設定的版本不會擷取或套用它們 |
| API 無法使用 | 如果可用，快取設定會套用，但 Claude Code 會[保留某些值](#fetch-and-caching-behavior)直到擷取成功。沒有快取的情況下，Claude Code 在下次成功擷取之前不會強制執行任何伺服器管理的設定，但仍會在裝置上套用任何[端點管理的設定](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)。使用 `forceRemoteSettingsRefresh: true` 時，CLI 會結束而不是繼續，但 [`claude auth` 子命令](#enforce-fail-closed-startup)除外。透過[Claude 應用程式閘道](#platform-availability)登入的用戶端在啟動時會結束而沒有該設定，具有相同的 `claude auth` 豁免 |
| 使用者使用不同的組織進行身份驗證 | 不會為受管組織外的帳戶傳遞設定，包括使用 [Console API 金鑰](#platform-availability)進行身份驗證的工作階段 |
| 使用者設定[第三方模型提供者](#platform-availability) | 伺服器管理的設定會被略過。這包括設定 `CLAUDE_CODE_USE_BEDROCK`、`CLAUDE_CODE_USE_MANTLE`、`CLAUDE_CODE_USE_VERTEX`、`CLAUDE_CODE_USE_FOUNDRY`、`CLAUDE_CODE_USE_ANTHROPIC_AWS` 或非預設的 `ANTHROPIC_BASE_URL` |
| 網路流量被攔截或重新導向 | 停用的 TLS 驗證或攔截的流量可以改變用戶端接收的設定 |

若要記錄本機設定檔的編輯，包括 `managed-settings.json`，請使用 [`ConfigChange` hooks](https://code.claude.com/docs/zh-TW/hooks#configchange)。當伺服器管理的設定到達或重新整理時，或當 MDM 設定檔或登錄原則變更時，Claude Code 不會執行它們，且 hook 無法阻止 `policy_settings` 變更。

若要限制使用者可以使用用戶端提供的認證存取的組織，請參閱 Claude 說明中心中的[使用租戶限制強制執行網路層級存取控制](https://support.claude.com/en/articles/13198485-enforce-network-level-access-control-with-tenant-restrictions)。如需更強的強制執行保證，請在已在 MDM 解決方案中註冊的裝置上使用[端點管理的設定](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)。

## 另請參閱

用於管理 Claude Code 設定的相關頁面：

* [所有設定](https://code.claude.com/docs/zh-TW/settings-reference.md)：每個設定鍵
* [Endpoint-managed settings](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)：由 IT 部門部署到裝置的受管設定
* [Authentication](https://code.claude.com/docs/zh-TW/authentication.md)：設定使用者對 Claude Code 的存取
* [Security](https://code.claude.com/docs/zh-TW/security.md)：安全保護措施和最佳實踐

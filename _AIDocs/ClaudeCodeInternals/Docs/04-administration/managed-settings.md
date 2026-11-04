<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/managed-settings | lastmod: 2026-11-03 | section: Administration / Setup and access -->
> 來源：https://code.claude.com/docs/zh-TW/managed-settings（官方 zh-TW，lastmod 2026-11-03）｜分類：Administration › Setup and access｜EN 摘要：Deploy managed settings to every developer's machine: delivery mechanisms per OS, how Claude Code combines managed sources, and how to verify enforcement.

# 部署受管設定

> 將受管設定部署到每個開發者的機器：每個作業系統的傳遞機制、Claude Code 如何結合受管來源，以及如何驗證強制執行。

受管設定是您的組織部署到每個開發者機器的設定。Claude Code 將它們應用於所有其他層級之上，因此沒有使用者、專案、本機或 `--settings` 值可以覆蓋它們，除了少數[安全敏感的例外](https://code.claude.com/docs/zh-TW/settings.md#exceptions-to-managed-settings-precedence)，其中來自較低層級的更嚴格值仍然適用。

本頁面適用於部署受管設定或偵錯為什麼某個設定未應用的管理員。若要決定要強制執行什麼，請從[決定要強制執行什麼](https://code.claude.com/docs/zh-TW/admin-setup.md#decide-what-to-enforce)表開始。如需 claude.ai 主控台路徑，請參閱[伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)。如需開發者自己的值放在哪個檔案中，請參閱[設定](https://code.claude.com/docs/zh-TW/settings.md)。

## 部署受管設定檔案

這是在每台機器上放置原則的最快方式：一個 `managed-settings.json` 檔案。如果您還沒有選擇如何傳遞受管設定，或您的裝置在 MDM 下或開發者執行雲端工作階段，請先閱讀[選擇傳遞機制](#choose-a-delivery-mechanism)。

**1. 編寫 managed-settings.json**

編寫一個 `managed-settings.json`，其中包含您決定要強制執行的金鑰，採用與 `settings.json` 相同的 JSON 形狀。[決定要強制執行什麼](https://code.claude.com/docs/zh-TW/admin-setup.md#decide-what-to-enforce)表列出每個控制項後面的金鑰，[設定參考](https://code.claude.com/docs/zh-TW/settings-reference.md)中的每個項目都說明受管來源是否可以設定它。此檔案會阻止兩個檔案讀取、關閉略過模式，並使 Claude Code 忽略來自使用者、專案和本機檔案以及 `--allowedTools` 的權限規則：

```json managed-settings.json theme={null}
{
  "permissions": {
    "deny": [
      "Read(./.env)",
      "Read(./secrets/**)"
    ],
    "disableBypassPermissionsMode": "disable"
  },
  "allowManagedPermissionRulesOnly": true
}
```

如需顯示更多受管金鑰形狀的更完整範例，包括登入方法、模型、MCP 伺服器和市場，請參閱[組織的受管設定](https://code.claude.com/docs/zh-TW/settings-example.md#an-organizations-managed-settings)。

**2. 將檔案放在每台機器上**

使用已經在您的機隊上放置檔案的任何工具，將檔案儲存為 `managed-settings.json` 在作業系統的系統目錄中：

* **macOS**: `/Library/Application Support/ClaudeCode/managed-settings.json`
* **Linux 和 WSL**: `/etc/claude-code/managed-settings.json`
* **Windows**: `C:\Program Files\ClaudeCode\managed-settings.json`

**3. 確認原則已應用**

在一台機器上，在 Claude Code 內執行 `/status`。`Setting sources` 行顯示 `Enterprise managed settings (file)`。在此之後推出到機隊的其餘部分；當該行遺失時，[檢查原則是否有效](#check-that-a-policy-is-in-force)涵蓋要查看的內容。

## 選擇傳遞機制

上述步驟中的檔案是將受管設定部署到機器上的四種方式之一。每種機制所承載的政策鍵都與 `settings.json` 檔案相同，因此[設定參考](https://code.claude.com/docs/zh-TW/settings-reference.md)適用於所有機制。少數鍵與特定來源綁定，每個項目的「範圍」一行會說明是哪些來源：

* **傳遞控制**：[`policyHelper`](https://code.claude.com/docs/zh-TW/settings-reference#policyhelper)、[`wslInheritsWindowsSettings`](https://code.claude.com/docs/zh-TW/settings-reference#wslinheritswindowssettings) 和 [`managedSourcesBehavior`](https://code.claude.com/docs/zh-TW/settings-reference#managedsourcesbehavior)
* **閘道登入鍵**：[`forceLoginGatewayUrl`](https://code.claude.com/docs/zh-TW/settings-reference#forcelogingatewayurl)、[`gatewayInternalNetworks`](https://code.claude.com/docs/zh-TW/settings-reference#gatewayinternalnetworks)，以及 [`forceLoginMethod`](https://code.claude.com/docs/zh-TW/settings-reference#forceloginmethod) 的 `"gateway"` 值

受管設定檔、MDM 設定描述檔或 claude.ai 主控台會將同一套政策套用到其涵蓋的每個人。若要為某一群開發人員提供不同的政策，請將不同的檔案或描述檔部署到該群組；claude.ai 主控台[目前還無法以群組為目標](https://code.claude.com/docs/zh-TW/server-managed-settings.md#current-limitations)，而自行託管的 [Claude apps 閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)則可依 IdP 群組傳遞受管設定。

當多個機制將政策傳遞到同一台機器時，Claude Code 預設只會使用其中一個並忽略其他機制。[Claude Code 如何組合受管來源](#how-claude-code-combines-managed-sources)說明了其順序，以及讓 Claude Code 套用所有來源的選擇性啟用設定。

MDM 和檔案這兩列合稱為端點受管設定，因為政策儲存在開發人員的裝置上；相對地，伺服器受管這一列則是由 Claude Code 擷取政策。

請依照您目前管理裝置的方式，使用下表選擇機制。

| 機制 | 傳遞方式 | Claude Code 讀取時機 | 適用情境 |
| :- | :- | :- | :- |
| [伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md) | 在 claude.ai 管理主控台中，或在自行託管的 [Claude apps 閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)上 | 在啟動時擷取並每小時輪詢一次；請參閱[需要核准的變更](#where-and-when-a-policy-applies) | 您希望在單一位置變更 claude.ai 組織的政策，而不必逐一處理每台機器 |
| MDM 或作業系統層級政策 | 透過 Jamf、Intune、群組原則或類似工具，以 macOS 設定描述檔或 Windows `HKLM` 登錄值的形式傳遞；請參閱[各機制儲存政策的位置](#where-each-mechanism-stores-the-policy) | 在啟動時讀取，並每 30 分鐘檢查一次變更 | 您已使用 MDM 或群組原則管理裝置 |
| 檔案型 | 以 `managed-settings.json` 的形式放在每台機器的系統目錄中；請參閱[各機制儲存政策的位置](#where-each-mechanism-stores-the-policy) | 在啟動時讀取，並在檔案變更時重新載入 | 沒有 MDM 的機器、Linux 主機，或您自行建置的映像檔 |
| HKCU 登錄，Windows 和 WSL | 以 Windows `HKCU` 登錄值的形式傳遞；請參閱[各機制儲存政策的位置](#where-each-mechanism-stores-the-policy) | 在啟動時讀取，並每 30 分鐘檢查一次變更；只有在[其上層沒有管理文件](#present-admin-documents)且沒有[主機提供的父層設定](#let-an-embedding-host-add-policy)提供限制性鍵時，Claude Code 才會使用它 | 您無法寫入機器層級的 `HKLM` 鍵 |

適用於 Jamf、Iru、Intune 和群組原則的入門範本位於 [MDM 範例儲存庫](https://github.com/anthropics/claude-code/tree/main/examples/mdm)。

如果您的組織已套用 [HIPAA 設定](https://code.claude.com/docs/zh-TW/hipaa-setup.md#deploy-managed-settings)，請參閱[設定範例儲存庫](https://github.com/anthropics/claude-code/tree/main/examples/settings)中的 `settings-hipaa.json` 和 `README-hipaa.md`，其中提供更完整的 `managed-settings.json`，包含沙箱機制、網路允許清單、憑證保護和本機資料保留。

關於受管 MCP 伺服器（您可透過 `managed-mcp.json` 與上述任一機制一併部署，或透過 [`managedMcpServers`](https://code.claude.com/docs/zh-TW/settings-reference#managedmcpservers) 鍵提供），請參閱[受管 MCP 設定](https://code.claude.com/docs/zh-TW/managed-mcp.md)。

### 政策套用的位置與時機

已部署的政策會以下列方式影響開發人員的工作階段：

* **使用介面**：在開發人員的機器上，終端機、VS Code 和 JetBrains 擴充功能、桌面應用程式的 Code 分頁，以及 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md) 工作階段都會讀取上述所有來源。即使 `settingSources` 排除了使用者、專案和本機檔案，Agent SDK 工作階段仍會載入受管設定。
* **雲端工作階段**：在 Anthropic 託管環境中的工作階段不會讀取裝置的 MDM 設定描述檔或檔案，因此其政策必須來自伺服器受管設定。在[自行託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)中的工作階段也會讀取其執行器映像檔中的受管設定檔，但預設只有在伺服器受管設定未傳遞任何政策鍵時才會讀取，[Claude Code 從每個管理來源讀取的鍵](#keys-read-from-every-admin-source)除外。[Claude Code 如何組合受管來源](#how-claude-code-combines-managed-sources)說明了讓兩者同時套用的選擇性啟用設定。
* **Claude Tag 工作階段**：[Claude Tag](https://claude.com/docs/claude-tag/overview) 工作階段在雲端環境中執行，但不會接收伺服器受管設定。在[自行託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)中，它們仍會讀取執行器映像檔中的受管設定檔。請在 [Claude Tag 管理設定](https://claude.com/docs/claude-tag/admins/customize)中設定 Claude Tag 本身。
* **Cowork 工作階段**：Claude Desktop 應用程式中的 [Cowork](https://claude.com/docs/cowork/overview) 在 Claude Code 上執行其工作階段。在 Cowork 工作階段中，即使使用者以 Team 或 Enterprise 帳戶登入，Claude Code 也永遠不會從 claude.ai 管理主控台擷取伺服器受管設定，因此套用哪個政策取決於工作階段的執行位置：

  * **在使用者的機器上**：預設情況下，Cowork 工作階段中的 Claude Code 會讀取該裝置上的 MDM 或作業系統層級政策以及受管設定檔，因此請在該處部署政策。
  * **在完整 VM 沙箱中**：當您的 Claude Desktop 受管設定設定了 [`requireCoworkFullVmSandbox`](https://claude.com/docs/third-party/claude-desktop/configuration#requirecoworkfullvmsandbox) 時，Claude Code 會在虛擬機器內執行，而該處不存在裝置的 MDM 政策和受管設定檔。
  * **遠端 Cowork 工作階段**：這些工作階段在 Anthropic 管理的 VM 上執行，Claude Code 在該處沒有可讀取的裝置政策。

  無論工作階段在何處執行，當任何人在 claude.ai 上或從 Cowork 中的 **Customize** 從 git 儲存庫新增市集時，claude.ai 都會自行套用管理主控台的 [`strictKnownMarketplaces`](https://code.claude.com/docs/zh-TW/settings-reference#strictknownmarketplaces) 和 [`blockedMarketplaces`](https://code.claude.com/docs/zh-TW/settings-reference#blockedmarketplaces) 清單。[限制的運作方式](https://code.claude.com/docs/zh-TW/plugins/org.md#restrict-what-users-can-install)說明了該檢查。[使用介面涵蓋範圍](https://code.claude.com/docs/zh-TW/model-config.md#surface-coverage)表格比較了 Cowork 與其他使用介面。
* **執行中的工作階段**：大多數變更會依照[傳遞機制表格](#choose-a-delivery-mechanism)中的時程送達執行中的工作階段，無需重新啟動。
  * 對 [`forceRemoteSettingsRefresh`](https://code.claude.com/docs/zh-TW/settings-reference#forceremotesettingsrefresh)、[`requiredMinimumVersion`](https://code.claude.com/docs/zh-TW/settings-reference#requiredminimumversion) 和[部分使用者可編輯的鍵](https://code.claude.com/docs/zh-TW/settings.md#when-edits-take-effect)所做的變更，會在下一次工作階段啟動時生效。
  * 新增或變更的 [`policyHelper`](https://code.claude.com/docs/zh-TW/settings-reference#policyhelper) 項目會在下一次啟動時生效。如果在該次啟動時伺服器受管設定遮蔽了該 helper，則一旦擷取結果回報這些設定已移除，helper 就會立即執行。
* **需要核准的變更**：除了[等待下一次啟動的更新](https://code.claude.com/docs/zh-TW/server-managed-settings.md#fetch-and-caching-behavior)之外，對[需要核准](https://code.claude.com/docs/zh-TW/server-managed-settings.md#security-approval-dialogs)之設定（例如 hook 或 `env` 變數）所做的伺服器受管變更，在互動式工作階段中會等待開發人員接受對話方塊，而在由 IDE 擴充功能或 Agent SDK 託管的工作階段中則會套用於目前的執行。其他伺服器受管變更會在下一次輪詢時套用。
* **長時間存在的工作階段**：開啟數週的工作階段仍可能落後於推出的變更。[`requiredMinimumVersion`](https://code.claude.com/docs/zh-TW/settings-reference#requiredminimumversion) 會阻止過時的二進位檔啟動，但不會結束已在執行中的工作階段。

### 各機制儲存政策的位置

各處的鍵都相同，但每種機制會以不同的位置和形式儲存它們：

* **伺服器受管**：由 Anthropic 的伺服器或您的閘道保存政策。Claude Code 會保留一份本機快取，在啟動時套用，並[在每次成功擷取時取代](https://code.claude.com/docs/zh-TW/server-managed-settings.md#security-considerations)。
* **macOS 設定描述檔**：`com.anthropic.claudecode` 受管偏好設定網域。使用與 `managed-settings.json` 相同的頂層鍵，巢狀設定使用字典，清單則使用 plist 陣列。
* **Windows HKLM 登錄**：JSON 以名為 `Settings` 的 `REG_SZ` 或 `REG_EXPAND_SZ` 值存放於 `HKLM\SOFTWARE\Policies\ClaudeCode` 下。
* **檔案型**：系統目錄中的 `managed-settings.json`、選用的 `managed-settings.d/` 目錄和 `managed-mcp.json`：macOS 上為 `/Library/Application Support/ClaudeCode/`，Linux 和 WSL 上為 `/etc/claude-code/`，Windows 上為 `C:\Program Files\ClaudeCode\`。Claude Code 不會讀取舊版 Windows 路徑 `C:\ProgramData\ClaudeCode\managed-settings.json`。

  您可以將上述任一檔案部署為符號連結，Claude Code 會讀取連結所指向的檔案。當連結指向系統目錄之外，或 Claude Code 無法確認其位於目錄內時，政策仍會套用。此時 `/status` 和 `claude doctor` 中會出現指名該檔案的警告。若要清除警告，請將連結指向系統目錄內的目標。
* **Windows HKCU 登錄**：`HKCU\SOFTWARE\Policies\ClaudeCode` 下相同的 `Settings` 值。

### 在多個團隊之間拆分檔案型政策

如果多個團隊各自負責同一政策的不同部分，請將每個部分放在 `managed-settings.d/` 中各自的檔案裡（該目錄與 `managed-settings.json` 位於同一系統目錄），而不是編輯同一個共用檔案。

Claude Code 會先合併 `managed-settings.json`，然後依字母順序合併該目錄中的每個 `*.json` 檔案。請使用數字前綴為檔案命名以控制順序，例如 `10-telemetry.json` 和 `20-security.json`。Claude Code 會忽略隱藏檔案以及結尾不是 `.json` 的檔案。

當兩個檔案設定相同的鍵時，Claude Code 會依下列規則組合它們：

* **單一值**，例如 `"model": "opus"` 或 `"cleanupPeriodDays": 7`：較後檔案的值會取代較早的值
* **清單**，例如 `permissions.deny` 或 `sandbox.network.allowedDomains`：兩份清單會合併，並移除重複項目
* **巢狀區塊**，例如 `env` 或 `sandbox`：兩個區塊會逐鍵合併，且其中每個鍵都遵循相同的規則
* **`fallbackModel`**：較後的鏈會整個取代較早的鏈
* **[`extraKnownMarketplaces`](https://code.claude.com/docs/zh-TW/settings-reference#extraknownmarketplaces) 和 [`managedMcpServers`](https://code.claude.com/docs/zh-TW/settings-reference#managedmcpservers)**：名稱相同的較後項目會整個取代較早的項目
* **[`modelPicker`](https://code.claude.com/docs/zh-TW/settings-reference#modelpicker)**：較後的陣容會整個取代較早的陣容

## Claude Code 如何結合受管來源

當您的組織向同一台機器提供多個受管來源時，[`managedSourcesBehavior`](https://code.claude.com/docs/zh-TW/settings-reference#managedsourcesbehavior) 金鑰決定 Claude Code 對其他來源的處理方式：

* **`"first-wins"`，預設值**：Claude Code 使用提供至少一個原則金鑰的最高排名來源，並忽略其餘來源，而不是合併它們，除了 [從每個管理員來源讀取的金鑰](#keys-read-from-every-admin-source) 中的金鑰。Claude Code 不會對它跳過的來源顯示警告；`/status` [命名它使用的來源和跳過的來源](#read-the-source-in-/status)。
* **`"merge"`**：Claude Code 應用提供原則金鑰的每個管理員來源，並按金鑰類型結合它們：在大多數金鑰上，較高排名來源的值適用，列表聯合，鎖定採用最嚴格的值。[組合每個受管來源](#compose-every-managed-source) 說明在何處設定金鑰以及每種金鑰類型如何結合。需要 Claude Code v2.1.242 或更新版本。

兩個設定以相同方式排名來源。這些術語在本節中重複出現：

* **原則金鑰**：除了兩個控制金鑰 [`wslInheritsWindowsSettings`](https://code.claude.com/docs/zh-TW/settings-reference#wslinheritswindowssettings) 和 [`managedSourcesBehavior`](https://code.claude.com/docs/zh-TW/settings-reference#managedsourcesbehavior) 之外的任何設定金鑰。只包含這些的受管設定檔或 MDM 原則不計算，Claude Code 會移至下一個來源。
* **管理員來源**：下面前三個來源之一。HKCU 登錄是使用者可寫的，不是其中之一。

Claude Code 按此順序檢查來源，最高優先順序優先：

1. 遠端設定，從 claude.ai 作為 [伺服器管理的設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md) 或通過 [Claude 應用程式閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway) 提供。Claude Code 僅在工作階段使用 [符合條件的憑證](https://code.claude.com/docs/zh-TW/server-managed-settings.md#platform-availability) 直接向 Anthropic 的 API 進行身份驗證、使用 `/login` 登入閘道，或在 Claude Desktop 的 Code 分頁中於 [為該工作階段提供設定](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#apply-code-settings-in-the-code-tab) 的閘道後方執行時，才會擷取此來源。在其他提供者上，或當 `ANTHROPIC_BASE_URL` 指向 Anthropic API 以外的地方時，它從下一個來源開始
2. MDM 或作業系統層級原則：macOS plist 或 HKLM 登錄金鑰
3. 受管設定檔，`managed-settings.d/*.json` 和 `managed-settings.json` 合併在一起
4. HKCU 登錄，在 Windows 上，以及在 WSL 上，一旦 HKLM 登錄或 Windows 受管設定檔開啟 [`wslInheritsWindowsSettings`](https://code.claude.com/docs/zh-TW/settings-reference#wslinheritswindowssettings) 並且 HKCU 值也設定它。Claude Code 僅在 [其上方沒有存在的管理員文件](#present-admin-documents) 且沒有 [主機提供的父設定](#let-an-embedding-host-add-policy) 提供限制性金鑰時才讀取它

此圖表顯示排名，以及 Claude Code 在任一設定下從前三個來源讀取的跨來源金鑰示例：

![圖表顯示四個受管設定來源的排名，從頂部的遠端設定到 MDM、受管設定檔和底部的 HKCU 登錄。預設情況下，具有原則金鑰的第一個來源提供原則，其餘的被跳過；將 managedSourcesBehavior 設定為合併時，每個具有原則金鑰的管理員來源都會貢獻，按金鑰類型結合，HKCU 登錄保持不變。側面板顯示跨來源金鑰（如沙箱鎖、forceRemoteSettingsRefresh 和每個變數 env 合併）從每個管理員來源讀取，不包括 HKCU 登錄。](https://mintcdn.com/claude-code/zuWID2B-Rxm8DEC8/images/managed-source-precedence.svg?fit=max\&auto=format\&n=zuWID2B-Rxm8DEC8\&q=85\&s=53f6be49f06eff48e01422c8ae1bc2e6)

### 管理員文件何時視為存在

在 [受管來源的排名](#how-claude-code-combines-managed-sources) 中，Claude Code 永遠不會在存在的管理員文件下方應用使用者可寫的 HKCU 登錄。符合以下情況時，文件即視為存在：

* 它將任何原則金鑰設定為 `null` 以外的值，即使是 Claude Code 無法讀取的值
* 它是存在但無法讀取的 HKLM 值、受管設定檔或 `managed-settings.d` 目錄

在 WSL 上，`/etc/claude-code` 也是使用者可寫的，[`wslInheritsWindowsSettings`](https://code.claude.com/docs/zh-TW/settings-reference#wslinheritswindowssettings) 項目說明 Windows 文件何時位於其上方。

### 從每個管理員來源讀取的金鑰

在預設的 `"first-wins"` 設定下，Claude Code 僅從 [它選擇的來源](#how-claude-code-combines-managed-sources) 讀取大多數金鑰，並忽略較低排名來源中的值，即使選定的來源未設定該金鑰。

少數金鑰的工作方式不同。Claude Code 從每個管理員來源讀取它們，因此當選定的來源不設定時，較低排名的 MDM 原則或受管設定檔仍然可以設定它們。Claude Code 將使用者可寫的 HKCU 登錄排除在該掃描之外；當 HKCU 是唯一的來源且沒有主機提供父設定時，HKCU 像任何選定的來源一樣應用。

跨來源金鑰包括：

* `sandbox.network.allowManagedDomainsOnly` 和 `sandbox.filesystem.allowManagedReadPathsOnly`：任何管理員來源中的 `true` 會開啟鎖定。當鎖定開啟時，Claude Code 聯合它鎖定的允許清單，`sandbox.network.allowedDomains` 與 `WebFetch(domain:...)` 允許規則，或 `sandbox.filesystem.allowRead`，跨每個管理員來源。沒有鎖定，Claude Code 將允許清單視為任何其他金鑰，因此在 `"first-wins"` 下，未選定的管理員來源的允許清單被忽略
* `allowAllClaudeAiMcps`
* `allowManagedMcpServersOnly`：任何管理員來源中的 `true` 會開啟 MCP 允許清單鎖定。當鎖定開啟時，受管的 `allowedMcpServers` 列表來自設定列表的最高排名管理員來源。伺服器管理的列表替換較低來源的列表，而不是與其結合。

  如果沒有管理員來源設定列表，每個通過拒絕清單的伺服器都會載入，除非 [父設定](#let-an-embedding-host-add-policy) 提供列表。

  沒有鎖定，Claude Code 從它應用的受管來源讀取 `allowedMcpServers`，因此在 `"first-wins"` 下，未選定的管理員來源的列表被忽略。需要 Claude Code v2.1.273 或更新版本
* `deniedMcpServers` 和 [`disableClaudeAiConnectors`](https://code.claude.com/docs/zh-TW/settings-reference#disableclaudeaiconnectors)：任何管理員來源中的項目或 `true` 適用。需要 Claude Code v2.1.273 或更新版本
* 沙箱二進位路徑 `sandbox.bwrapPath` 和 `sandbox.socatPath`
* 沙箱 `ripgrep` 二進位，[`sandbox.ripgrep`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-ripgrep)
* `sandbox.filesystem.disabled` 和 `sandbox.network.strictAllowlist`
* [`useAutoModeDuringPlan`](https://code.claude.com/docs/zh-TW/settings-reference#useautomodeduringplan)、[`syncClaudeAiSkills`](https://code.claude.com/docs/zh-TW/settings-reference#syncclaudeaiskills) 和 [`syncClaudeAiPlugins`](https://code.claude.com/docs/zh-TW/settings-reference#syncclaudeaiplugins)，其中任何管理員來源的 `false` 會關閉行為。每個金鑰只能拒絕：
  * 開發人員的使用者或本機設定中的 `false` 也會關閉它
  * 對於 `useAutoModeDuringPlan`，開發人員使用 [`--setting-sources`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 等選項排除的使用者或本機檔案中的 `false` 不計算。忽略被排除的檔案需要 Claude Code v2.1.314 或更新版本
* [`enableArtifact`](https://code.claude.com/docs/zh-TW/settings-reference#enableartifact)，其中任何管理員來源的 `false` 會關閉 [Artifact 工具](https://code.claude.com/docs/zh-TW/artifacts.md)。開發人員的使用者、專案或本機設定中的 `false` 也會關閉它，沒有來源會將其開啟；請參閱 [哪些較低層級的值仍然計算](https://code.claude.com/docs/zh-TW/settings.md#exceptions-to-managed-settings-precedence)。需要 Claude Code v2.1.242 或更新版本
* [`maxEffortLevel`](https://code.claude.com/docs/zh-TW/settings-reference#maxeffortlevel)，其中任何管理員來源中的最低上限適用。如果開發人員在自己的設定或使用 `--settings` 中設定較低的上限，Claude Code 會應用該上限；沒有來源可以提高上限。需要 Claude Code v2.1.267 或更新版本
* `attribution` 中的提交預告片選擇退出，或在已棄用的 `includeCoAuthoredBy` 中，來自任何層級
* [`forceRemoteSettingsRefresh`](https://code.claude.com/docs/zh-TW/server-managed-settings)
* `env`，跨管理員來源按變數合併：每個變數來自定義它的最高優先順序來源，因此較低來源填充較高來源未設定的變數。少數變數遵循自己的規則；[跨受管來源的每個金鑰例外](https://code.claude.com/docs/zh-TW/server-managed-settings.md#per-key-exceptions-across-managed-sources) 命名每一個。需要 Claude Code v2.1.223 或更新版本。在 v2.1.223 之前，Claude Code 僅應用選定來源的整個 `env` 區塊

[`allowedProviders`](https://code.claude.com/docs/zh-TW/settings-reference#allowedproviders) 有自己的規則：其項目的 Scope 備註說明機器上設定的列表如何與伺服器管理的列表結合。需要 Claude Code v2.1.285 或更新版本。

當管理員來源設定 `allowManagedMcpServersOnly` 或 `allowedMcpServers` 列表且該值不是生效的值時，`/status` 和 `claude doctor` 命名該來源和金鑰。

#### 哪個受管來源提供登入金鑰

在具有 MDM 原則或受管設定檔的機器上，Claude Code 會從該原則或檔案取得登入金鑰，即使是 [遠端設定](#how-claude-code-combines-managed-sources) 也設定的金鑰亦然。來自 claude.ai 管理主控台的設定屬於遠端設定，因此請在 MDM 原則或檔案中設定登入金鑰，例如 [`forceLoginOrgUUID`](https://code.claude.com/docs/zh-TW/settings-reference#forceloginorguuid)。

如果機器同時具有 MDM 原則和受管設定檔，請使用 MDM 原則。當該原則設定任何 [原則金鑰](#how-claude-code-combines-managed-sources) 時，Claude Code 會忽略檔案中的登入金鑰，[即使在 `managedSourcesBehavior: "merge"` 下亦然](#compose-every-managed-source)。

登入金鑰為：

* `forceLoginOrgUUID`，以及設定為 `"claudeai"` 或 `"console"` 的 `forceLoginMethod`：如果原則或檔案省略任一金鑰，則適用遠端設定中的值。在每個用戶端都執行 v2.1.299 或更新版本之前，也請在 claude.ai 的 [伺服器管理的設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md) 中設定這些金鑰
* [閘道登入金鑰](#choose-a-delivery-mechanism)：Claude Code 不會將遠端設定中的值用於閘道登入

### 組合每個受管來源

要讓 Claude Code 應用您的組織提供的每個管理員來源，請在您部署的最高排名來源中將 [`managedSourcesBehavior`](https://code.claude.com/docs/zh-TW/settings-reference#managedsourcesbehavior) 設定為 `"merge"`。Claude Code 僅從具有金鑰或原則金鑰的最高排名來源讀取該金鑰，因此較低來源無法選擇自己合併到上面的來源，永遠不會接收伺服器管理設定的機器也需要在其 MDM 設定檔中有該金鑰。使用者可寫的 HKCU 登錄永遠不會與另一個來源合併。需要 Claude Code v2.1.242 或更新版本。

在 `"merge"` 下，Claude Code 添加較低來源的列表項目，例如 `permissions.allow` 規則和 hook，到原則，因此僅在排名低於最高來源的每個來源都在管理員控制下時才開啟它。

此表格顯示 Claude Code 在 `"merge"` 下如何結合每種金鑰。[`managedSourcesBehavior` 項目](https://code.claude.com/docs/zh-TW/settings-reference#managedsourcesbehavior) 命名三行中的每個金鑰：限制允許清單、整體採用的值和僅從最高排名來源讀取的金鑰。

| 金鑰類型 | Claude Code 如何結合它 | 示例 |
| :- | :- | :- |
| 列表 | 結合來自每個來源的項目 | `permissions.allow`、`hooks`、`sandbox.network.allowedDomains`、`deniedMcpServers`、`deniedModels` |
| 鎖定 | 應用任何來源設定的最嚴格值；較寬鬆的值僅從最高排名來源適用 | `allowManagedHooksOnly`、`permissions.disableBypassPermissionsMode`、`crossSessionInbound`、`availableModelsMatch` |
| 限制允許清單 | 從設定它的最高排名來源整體採用列表，不添加來自較低來源的項目 | `availableModels`、`allowedMcpServers`、`strictKnownMarketplaces`、`allowedChannelPlugins` 和 `fallbackModel` 鏈 |
| 整體採用的值 | 從設定它的最高排名來源整體採用值，不結合來自較低來源的項目或欄位 | `sandbox.credentials.awsPairs`、`sandbox.ripgrep` |
| 提供的 MCP 伺服器 | 結合來自每個來源的伺服器名稱；當兩個來源設定相同名稱時，應用較高排名來源的整個項目 | `managedMcpServers` |
| 僅從最高排名來源讀取的金鑰 | 忽略每個較低來源中的金鑰，即使最高排名來源未設定它 | `modelPicker`、`permissions.defaultMode`，以及憑證幫助程式，例如 `apiKeyHelper` |
| `env` | 在任一設定下跨管理員來源按變數合併，如 [從每個管理員來源讀取的金鑰](#keys-read-from-every-admin-source) 所述 | |
| 登入金鑰 | 在任一設定下，從 MDM 原則或受管設定檔中帶有 [原則金鑰](#how-claude-code-combines-managed-sources) 的較高排名者取得，[優先於遠端設定](#which-managed-source-supplies-login-keys) | `forceLoginOrgUUID`、`forceLoginMethod` 和 [閘道登入金鑰](#choose-a-delivery-mechanism) |
| 所有其他金鑰 | 從設定它的最高排名來源採用值 | `model`、`cleanupPeriodDays` |

要確認機器上結合了哪些來源，[讀取 `/status` 中的 `Setting sources` 行](#read-the-source-in-/status)；該部分說明每個標籤的含義。

### 使用幫助程式計算原則

[`policyHelper`](https://code.claude.com/docs/zh-TW/settings-reference#policyhelper) 是您的 MDM 原則或受管設定檔命名的可執行檔，Claude Code 在啟動時運行它以計算受管設定。當選定的來源配置一個並且幫助程式發出 `managedSettings` 物件時，該輸出改變 Claude Code 讀取的內容：

* **發出的 `managedSettings` 物件是工作階段的唯一受管設定**，包括 [它在其他情況下從每個管理員來源讀取的金鑰](#keys-read-from-every-admin-source)，除了 [`forceRemoteSettingsRefresh`，它有自己的啟動規則](https://code.claude.com/docs/zh-TW/settings-reference#forceremotesettingsrefresh)

有關哪些幫助程式運行失敗，以及 Claude Code 在失敗時的處理方式，請參閱 [幫助程式失敗](https://code.claude.com/docs/zh-TW/settings-reference.md#helper-failures)。

### 讓嵌入主機添加原則

當另一個應用程式啟動 Claude Code 時，例如 Claude Desktop、IDE 擴充功能或 Agent SDK 應用程式，該主機可以通過 SDK `managedSettings` 選項傳遞自己的受管設定。Claude Code 將這些稱為父設定。

預設情況下，只要存在管理員來源，Claude Code 就會忽略父設定：伺服器管理的設定、MDM 或作業系統層級原則或受管設定檔。

要讓 Claude Code 將父設定與管理員來源合併，請在最高優先順序受管來源中將 [`parentSettingsBehavior`](https://code.claude.com/docs/zh-TW/settings-reference#parentsettingsbehavior) 設定為 `"merge"`；Claude Code 僅從該來源讀取金鑰。

Claude Code 然後僅保留限制 Claude 可以做什麼的主機值，有一個需要了解的間隙：除非您也設定 `allowManaged*Only` 鎖定，主機的權限允許規則和沙箱允許清單仍然適用。請參閱 [限制父設定](https://code.claude.com/docs/zh-TW/claude-apps-gateway#restrict-parent-settings) 以了解鎖定。

[`policyHelper`](https://code.claude.com/docs/zh-TW/settings-reference#policyhelper) 可以關閉父合併，無論此金鑰如何；其項目說明何時。

Claude Code 也對父提供的值本身應用這些檢查：

* 當任何管理員來源設定 `allowManagedPermissionRulesOnly` 時，Claude Code 在讀取時刪除 [父提供的](https://code.claude.com/docs/zh-TW/claude-apps-gateway#restrict-parent-settings) 權限允許規則和 `additionalDirectories`，即使較高優先順序來源未設定金鑰。金鑰對您自己的權限規則的影響來自 Claude Code 應用的受管設定，或來自您選擇合併的父設定
* Claude Code 強制執行它應用的受管設定中的 `forceLoginOrgUUID` 或 `allowedMcpServers` 值，並阻止父提供的值。如果您提供多個受管來源，請參閱 [哪個來源提供 `forceLoginOrgUUID`](#which-managed-source-supplies-login-keys)。

  在 Claude Code v2.1.273 或更新版本上，當 `allowManagedMcpServersOnly` 開啟時，來自設定列表的最高排名管理員來源的 `allowedMcpServers` 列表適用並阻止父的，作為 [跨來源金鑰](#keys-read-from-every-admin-source)。父的列表僅在沒有管理員來源設定列表時適用。[`managedSourcesBehavior`](https://code.claude.com/docs/zh-TW/settings-reference#managedsourcesbehavior) 項目說明在 `"merge"` 下哪個來源提供每個金鑰。在 v2.1.223 之前，任何管理員來源中的值阻止父的
* 對於 `availableModels`，Claude Code 強制執行它應用的受管設定中的值，並阻止父提供的列表
* 對於 `strictKnownMarketplaces`，Claude Code 同樣強制執行它應用的受管設定中的列表，並阻止父提供的列表。父的列表僅在沒有應用的受管來源設定列表時適用。需要 Claude Code v2.1.282 或更新版本
* 對於 `allowedProviders`，[選定的受管來源](#which-managed-source-claude-code-uses) 中的列表會阻止父提供的列表，而在 [`managedSourcesBehavior`](https://code.claude.com/docs/zh-TW/settings-reference#managedsourcesbehavior) `"merge"` 選擇加入下，任何管理員來源中的列表都會阻止父提供的列表。需要 Claude Code v2.1.285 或更新版本
* 父提供的 `blockedMarketplaces` 除了受管來源設定的任何拒絕清單外還適用。需要 Claude Code v2.1.282 或更新版本

#### 當僅應用受管規則時保持 Cowork 資料夾存取

[Cowork](https://claude.com/docs/cowork/overview) 在 Claude Desktop 應用程式中在 Claude Code 上運行其工作階段，並通過它在啟動工作階段時提供的允許規則授予每個工作階段對其工作資料夾（例如使用者連接的資料夾）的存取權限。當您的受管原則設定 [`allowManagedPermissionRulesOnly`](https://code.claude.com/docs/zh-TW/settings-reference#allowmanagedpermissionrulesonly) 時，Claude Code 僅保留受管原則中的允許規則：它刪除主機作為父設定、`--allowedTools` 或設定檔提供的允許規則，因此對這些資料夾的寫入失去預先批准。在要求編輯前的 Cowork 工作階段中，Cowork 無法顯示權限提示，Claude 將每次寫入報告為被阻止，因為路徑解析為受保護的位置或連接資料夾外的路徑。

要恢復寫入，請為這些資料夾添加允許規則到 Claude Code [選擇](#precedence-within-the-managed-tier) 的受管來源在這些機器上：在 MDM 管理的車隊上，那是 MDM 原則而不是單獨的受管設定檔。此示例使用檔案形式，MDM 原則採用相同的金鑰。它保持 `allowManagedPermissionRulesOnly` 設定並允許在每個使用者家目錄中的 `CoworkProjects` 資料夾下編輯；將路徑替換為您的使用者連接的資料夾：

```json managed-settings.json theme={null}
{
  "allowManagedPermissionRulesOnly": true,
  "permissions": {
    "allow": [
      "Edit(~/CoworkProjects/**)"
    ]
  }
}
```

部署原則後，Claude 可以在新 Cowork 工作階段中的該資料夾下保存檔案。[Read 和 Edit 規則](https://code.claude.com/docs/zh-TW/permissions.md#read-and-edit) 涵蓋路徑語法，包括絕對路徑的 `//` 形式。

### 開發人員可以更改的內容

開發人員自己的設定檔、`--settings` 值和專案檔案永遠不會覆寫受管值；[例外](https://code.claude.com/docs/zh-TW/settings.md#exceptions-to-managed-settings-precedence) 僅允許較嚴格的較低層級值計算。這些情況位於該規則之外：

* **工作階段的模型**：受管 `model` 是預設值，不是鎖定。`--model` 和 `ANTHROPIC_MODEL` 仍然為該工作階段選擇模型，因此部署 [`availableModels`](https://code.claude.com/docs/zh-TW/settings-reference#availablemodels) 以限制選擇。
* **工作階段的自動壓縮視窗**：受管 [`autoCompactWindow`](https://code.claude.com/docs/zh-TW/settings-reference#autocompactwindow) 同樣是預設值。`--autocompact` 旗標和 `CLAUDE_CODE_AUTO_COMPACT_WINDOW` 變數仍然會為該工作階段設定 [自動壓縮視窗](https://code.claude.com/docs/zh-TW/model-config.md#set-the-auto-compact-window)。
* **本機管理員權限**：作為機器上管理員的開發人員可以編輯受管來源本身，這就是為什麼 MDM 工具可以按計劃重新部署設定檔或檔案，以及為什麼 HKLM 登錄和 macOS 受管偏好設定域存在。
* **伺服器管理的快取**：伺服器管理的設定來自 Anthropic 的伺服器，對本機快取的編輯 [僅持續到下一次成功擷取](https://code.claude.com/docs/zh-TW/server-managed-settings.md#security-considerations)。
* **其他工具**：受管設定僅綁定 Claude Code。從另一個工具呼叫 API 的開發人員不受它們約束。

## 檢查政策是否生效

開發人員報告政策未應用，或者您想在將其推送到整個機隊之前確認推出已完成。該機器上的兩個命令可以回答這個問題：`/status` 顯示 Claude Code 選擇了哪個受管理的來源，而 `claude doctor` 列出它丟棄的內容。

### 在 /status 中讀取來源

在開發人員的機器上，在 Claude Code 內執行 `/status` 並讀取 `Setting sources` 行。當受管理的來源生效時，該行列出 `Enterprise managed settings`，並在括號中顯示 Claude Code 選擇的來源：

* `(remote)`：來自 claude.ai 或閘道的伺服器管理設定
* `(plist)` 或 `(HKLM)`：MDM 或作業系統政策
* `(file)`、`(drop-ins)` 或 `(file + drop-ins)`：`managed-settings.json`、drop-in 目錄或兩者
* `(remote + file, merged)` 或其他以 `, merged` 結尾的列表：您的組織[組合每個受管理的來源](#compose-every-managed-source)，Claude Code 將列出的來源合併到政策中。較低的來源仍然可以提供 `env` 變數而不出現在列表中。需要 Claude Code v2.1.242 或更新版本
* `(HKCU)`：使用者可寫的登錄檔備用方案
* `(parent process)`：[嵌入主機](#let-an-embedding-host-add-policy)提供的限制性設定
* `(helper)`：由選定的 MDM 或檔案來源配置的 [`policyHelper`](https://code.claude.com/docs/zh-TW/settings-reference#policyhelper)

當 Claude Code 在機器上找到受管理的來源但未選擇它時，第二行 `Skipped sources` 會列出每個這樣的來源。讀取它以區分政策從未到達機器的情況和政策到達但被更高優先級來源覆蓋的情況。需要 Claude Code v2.1.242 或更新版本。

當政策未應用時，`Setting sources` 行會告訴您您有以下兩個問題中的哪一個：

* **該行缺失**：Claude Code 找不到傳遞政策金鑰的受管理來源。

  如果您部署了受管理設定檔案，請檢查它是否位於作業系統的路徑中，以及它是否包含[政策金鑰](#how-claude-code-combines-managed-sources)而不僅僅是控制金鑰。不是有效 JSON 的檔案不會產生此狀態；Claude Code [拒絕啟動](#find-entries-claude-code-dropped)。

  當您改為通過伺服器管理設定部署時，執行 `claude doctor`，它會報告[擷取結果](https://code.claude.com/docs/zh-TW/server-managed-settings.md#verify-settings-delivery)。
* **該行命名的來源不是您部署的來源**：存在更高優先級的來源，Claude Code 忽略了您的來源，`Skipped sources` 列出了它。[Claude Code 如何組合受管理來源](#how-claude-code-combines-managed-sources)給出了順序。

### 尋找 Claude Code 丟棄的項目

如果受管理設定檔案、MDM 設定檔、登錄檔值或伺服器管理 payload 未通過 schema 驗證，Claude Code 首先跳過它可以修復的個別項目（例如一個無效的權限規則），並為每個項目發出警告。Claude Code 然後丟棄任何仍然失敗的值，除非該值屬於[失敗關閉](#keys-that-fail-closed)的金鑰之一。

Claude Code 對 [`policyHelper`](https://code.claude.com/docs/zh-TW/settings-reference#policyhelper) 發出的 `managedSettings` 更加嚴格：它進行相同的項目修復，但任何倖存的 schema 違規都會導致整個 helper 執行失敗，在啟動時 Claude Code 拒絕啟動，與 helper 以非零狀態退出的情況相同。

當受管理設定檔案、drop-in 檔案、MDM plist 或 HKLM 登錄檔值存在但無法解析為 JSON 物件時，Claude Code 拒絕啟動並列印[命名來源的錯誤](https://code.claude.com/docs/zh-TW/errors.md#managed-settings-document-could-not-be-parsed)，即使另一個管理員來源提供有效政策也是如此。每個來源在以下情況下以這種方式失敗：

* **受管理設定檔案或 drop-in 檔案**：檔案不是有效的 JSON，或其頂級不是物件
* **MDM plist**：macOS 的 `plutil` 報告 plist 格式不正確，或其轉換的內容不是 JSON 物件
* **HKLM 登錄檔值**：`Settings` 值不是字串、為空或不包含 JSON 物件

三個來源狀態不會導致此拒絕：

* 缺失的檔案、設定檔或登錄檔值不是失敗；Claude Code 在沒有該來源的情況下執行。
* 空的受管理設定檔案計為 `{}`。
* 使用者可寫的 HKCU 登錄檔金鑰中的格式不正確的值永遠不會阻止啟動。Claude Code 將其報告為 `/status` 和 `claude doctor` 中的通知。

當受管理設定檔案、drop-in 檔案、`managed-settings.d/` 目錄、MDM 設定檔或 HKLM 登錄檔值存在但無法讀取，且沒有管理員來源提供政策時，發生的情況取決於讀取失敗的原因：

* 如果作業系統拒絕讀取，例如在僅限根目錄的檔案上，每個工作階段都會在沒有該來源政策的情況下啟動。`/status` 和 `claude doctor` 記錄失敗，使用 `-p` 執行也會將其列印到 stderr。
* 對於任何其他讀取失敗，例如 I/O 錯誤，每個工作階段都會在啟動時退出，並顯示[聯絡管理員的訊息](https://code.claude.com/docs/zh-TW/errors.md#unable-to-read-managed-policy-settings)。

要尋找丟棄的項目，請查看以下三個位置之一：

* 互動式工作階段在啟動時顯示列出無效項目的對話框。
* 使用 `-p` 的非互動式執行會將摘要列印到 stderr。
* [`claude doctor`](https://code.claude.com/docs/zh-TW/debug-your-config) 列出每個無效項目及其來源和欄位。

#### 失敗關閉的金鑰

當受管理來源設定具有單一限制性值的頂級金鑰（例如 `allowManagedPermissionRulesOnly`、`disableAutoMode` 或 `skipDangerousModePermissionPrompt`）為 Claude Code 無法讀取的內容時，該金鑰讀取為該值，直到您修復它。報告說該金鑰 `was present but invalid`，並命名 Claude Code 將其視為的值。對於 `sandbox` 內的金鑰，請參閱[`sandbox` 內的無效值](#invalid-values-inside-sandbox)。

這些情況不會失敗關閉：

* `null` 移除金鑰。
* 無效的 `disableAllHooks`（即使是引號的布林值）被丟棄並發出警告，因為強制執行 `true` 也會卸載您自己的受管理設定部署的 hook。
* 對於規則涵蓋的每個其他布林金鑰，字串 `"true"` 或 `"false"` 讀取為該布林值，在 `/status` 中發出通知要求您移除引號。

Claude Code 按欄位而不是整體丟棄來修復 `permissions`、`autoMode`、`worktree` 和 `attribution` 區塊：

* 其中的鎖（例如 `permissions.disableBypassPermissionsMode`）讀取為其限制性值。
* 無效的 `permissions.defaultMode` 讀取為 `default`。
* 當 `permissions` 中的 `deny` 或 `ask` 列表根本無法讀取時，Claude Code 扣留 `allow` 和 `additionalDirectories`，因此授予永遠不會應用而沒有寫在旁邊的限制。報告命名每個扣留的授予和無法讀取的列表。
* 在 `autoMode` 中，無法讀取的 `soft_deny` 或 `hard_deny` 列表，或失去無效項目的列表，以相同方式扣留 `allow` 和 `environment`。

具有單一限制性值的金鑰的失敗關閉規則和按欄位修復需要 Claude Code v2.1.282 或更新版本。

這些金鑰有自己的備用方案：

| 欄位 | 存在但無效時的行為 |
| :- | :- |
| `allowedMcpServers` | 強制執行為空的允許清單，直到修復該值，因此使用者添加的任何 MCP 伺服器都不被允許。您的組織通過 [`managedMcpServers`](https://code.claude.com/docs/zh-TW/settings-reference#managedmcpservers) 提供的伺服器仍然會載入，`managed-mcp.json` 伺服器根據[跳過允許清單檢查的伺服器](https://code.claude.com/docs/zh-TW/managed-mcp.md#servers-that-skip-the-allowlist-check)載入。個別無效項目被剝離，有效子集被強制執行。 |
| [`allowedProviders`](https://code.claude.com/docs/zh-TW/settings-reference#allowedproviders) | 強制執行為空的允許清單，直到修復該值，因此每個 API 提供者都被拒絕，Claude Code 不會在機器上啟動。如果只有個別項目不是已知的提供者名稱，Claude Code 會丟棄並報告該項目，並強制執行其餘項目。 |
| `allowedHttpHookUrls` | Claude Code 強制執行空的受管理[允許清單](https://code.claude.com/docs/zh-TW/settings-reference.md#allowedhttphookurls)，直到您修復該值，因此 HTTP hook 只有在另一個設定檔案列出其 URL 時才會執行。如果只有個別項目無效，Claude Code 會剝離該項目並強制執行其餘項目。 |
| `httpHookAllowedEnvVars` | Claude Code 強制執行空的受管理[允許清單](https://code.claude.com/docs/zh-TW/settings-reference.md#httphookallowedenvvars)，直到您修復該值，因此標頭變數只有在另一個設定檔案命名它時才會被插值。如果只有個別項目無效，Claude Code 會剝離該項目並強制執行其餘項目。 |
| `allowedChannelPlugins` | Claude Code 強制執行空的允許清單，直到您修復該值，因此傳遞給 `--channels` 的任何頻道外掛都不被允許。如果只有個別項目無效，它會剝離該項目並強制執行其餘項目。 |
| `strictKnownMarketplaces` | 強制執行為空的允許清單，直到修復該值，因此沒有[市集來源](https://code.claude.com/docs/zh-TW/plugins/org.md#restrict-what-users-can-install)被允許。無效或無法強制執行的個別項目（例如無法編譯的 `hostPattern` 正規表達式）被剝離，有效子集被強制執行。 |
| `availableModels` | 強制執行為空的允許清單直到修復，因此只有預設模型可用；非字串項目被剝離，有效子集被強制執行。 |
| [`availableModelsMatch`](https://code.claude.com/docs/zh-TW/settings-reference#availablemodelsmatch) | 視為 `exact` 直到修復該值。 |
| `forceLoginOrgUUID` | 直到修復該值，不允許任何組織登入。 |
| `gatewayInternalNetworks` | 當無效值來自機器上最高的受管理來源時，`/login` 拒絕該機器上的每個新[雲端閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway#allow-a-gateway-on-public-address-space-you-own)登入，直到修復該值。 |
| `crossSessionInbound` | 視為 `refuse`（最限制性的值），因此入站[跨工作階段訊息](https://code.claude.com/docs/zh-TW/cross-session-messaging.md#control-inbound-messages)被拒絕，直到修復該值。開發人員看到[警告](https://code.claude.com/docs/zh-TW/errors.md#crosssessioninbound-must-be-one-of-accept-hold-refuse)。 |
| `deniedMcpServers` | 個別無效項目被剝離，有效子集被強制執行。完全無效的值被丟棄並發出警告，因為拒絕每個伺服器會阻止政策從未命名的伺服器。 |
| [`deniedModels`](https://code.claude.com/docs/zh-TW/settings-reference#deniedmodels) | 非字串項目被剝離，清單的其餘部分被強制執行。完全無效的值被丟棄並發出警告，在修復前不會阻止任何模型。 |
| `blockedMarketplaces` | 個別無效項目被剝離，有效子集被強制執行。解析但永遠無法匹配的項目（例如無法編譯的 `hostPattern` 正規表達式）被保留並發出警告。它在修復前不會阻止任何內容，但[市集限制](https://code.claude.com/docs/zh-TW/plugins/org.md#restrict-what-users-can-install)保持活躍。完全無效的值被丟棄並發出警告，因為阻止每個市集會阻止政策從未命名的來源。 |
| `sandbox` | 當區塊內的一個值無效時，Claude Code 不會丟棄整個區塊。對於每種無效欄位發生的情況，請參閱[`sandbox` 內的無效值](#invalid-values-inside-sandbox)。 |
| `sandbox.credentials` | 可恢復的無效項目被降級為 `mode: "deny"` 並發出警告；無法恢復的項目被剝離；有效項目保持強制執行。請參閱[受管理設定中的無效憑證項目](https://code.claude.com/docs/zh-TW/settings-reference.md#invalid-credential-entries-in-managed-settings)。 |
| `strictPluginOnlyCustomization` | 視為 `true`（鎖定所有四個使用介面），當該值既不是布林值也不是陣列時。此版本不識別為使用介面的陣列項目不鎖定任何內容；狀態注意計算此類項目，以便您可以檢查它們是否有拼寫錯誤。 |
| `enabledPlugins` | 無效項目被丟棄並發出警告，其他項目保持強制執行。不是外掛 ID 的映射，或其每個項目都無效的值被整體丟棄並發出警告。 |

`allowedHttpHookUrls` 和 `httpHookAllowedEnvVars` 跨設定檔案合併，因此您的使用者、專案或本機設定中的項目在受管理清單為空時仍然適用。

這兩個金鑰和 `allowedChannelPlugins` 的備用方案需要 Claude Code v2.1.267 或更新版本；較早的版本在其值或任何項目無效時丟棄整個金鑰。`strictKnownMarketplaces` 和 `blockedMarketplaces` 備用方案需要 Claude Code v2.1.277 或更新版本；較早的版本在其值或任何項目無效時丟棄整個金鑰。`strictPluginOnlyCustomization` 和 `enabledPlugins` 備用方案需要 Claude Code v2.1.282 或更新版本。

`requiredMinimumVersion` 和 `requiredMaximumVersion` 按設計開放失敗：無效值被丟棄而不是強制執行。

此容差僅適用於受管理設定。使用者、專案和本機設定檔案保持嚴格：JSON 或頂級形狀驗證失敗的檔案被整體拒絕並報告，失敗的個別項目（例如格式不正確的權限規則）被跳過並發出警告，而檔案的其餘部分適用。

#### `sandbox` 內的無效值

當您的受管理 `sandbox` 區塊中的一個值無效時，Claude Code 不會丟棄整個區塊，因為它會單獨驗證每個欄位。這種按欄位處理需要 Claude Code v2.1.283 或更新版本。在 v2.1.283 之前的版本上，當 `credentials` 外的值無效時，Claude Code 會丟棄除 [`credentials`](https://code.claude.com/docs/zh-TW/settings-reference#invalid-credential-entries-in-managed-settings) 外的每個 `sandbox` 欄位。

您為無效欄位獲得的警告會命名該欄位並告訴您它發生了什麼。發生的情況取決於該欄位控制的內容：

* 如果您將布林金鑰設定為引號的 `"true"` 或 `"false"`，該值計為該布林值。而不是警告，`/status` 顯示通知要求您移除引號。
* 如果 `failIfUnavailable` 無效，Claude Code 會丟棄該值而不是將其視為 `true`，因此無法讀取的值永遠不會停止整個機隊中的工作階段啟動。
* Claude Code 將每個其他無效布林視為保持沙箱最嚴格的值，直到您修復它。打開沙箱或其限制之一的金鑰（例如 `enabled` 或 `network.allowManagedDomainsOnly`）計為 `true`。鬆散它的金鑰（例如 `allowUnsandboxedCommands`）計為 `false`。
* 在 `credentials` 外的列表中，例如 `excludedCommands` 或 `network.allowedDomains`，Claude Code 會丟棄無效項目並保留清單的其餘部分。不是陣列的列表，或沒有有效項目的列表，根本不適用。
* 當 `network.deniedDomains` 或其中任何項目無效時，Claude Code 也會扣留 `network.allowedDomains`，因此受管理允許清單不會授予任何內容，直到您修復拒絕清單。
* 當 `filesystem.denyRead`、`filesystem.denyWrite` 或其中任何項目無效時，Claude Code 也會扣留 `filesystem.allowRead` 和 `filesystem.allowWrite`，直到您修復拒絕清單。

## 只有受管理來源可以設定的金鑰

Claude Code 只從受管理來源讀取以下金鑰；將它們放在使用者或專案設定檔中沒有效果。

其中大多數是鎖定：鎖定所管理的值，例如權限規則或 `sandbox.network.allowedDomains`，是任何層級都可以設定的普通金鑰，而鎖定會告訴 Claude Code 只遵守受管理的值。

該表涵蓋權限、外掛程式和傳遞控制。對於此處未列出的任何金鑰，[設定參考](https://code.claude.com/docs/zh-TW/settings-reference.md#all-settings)索引的「範圍」欄會說明它是否為僅受管理。

| 設定 | 說明 |
| :- | :- |
| [`allowAllClaudeAiMcps`](https://code.claude.com/docs/zh-TW/settings-reference#allowallclaudeaimcps) | 載入 Claude Code 自行擷取的 claude.ai 連接器，與已部署的 `managed-mcp.json` 一起，而不是抑制它們 |
| [`allowedChannelPlugins`](https://code.claude.com/docs/zh-TW/settings-reference#allowedchannelplugins) | 可能推送訊息的頻道外掛程式的允許清單。設定時會取代預設的 Anthropic 允許清單。需要 `channelsEnabled: true`。請參閱[限制哪些頻道外掛程式可以執行](https://code.claude.com/docs/zh-TW/channels.md#restrict-which-channel-plugins-can-run) |
| [`allowManagedHooksOnly`](https://code.claude.com/docs/zh-TW/settings-reference#allowmanagedhooksonly) | 當為 `true` 時，限制哪些 hooks 執行；請參閱[在 `allowManagedHooksOnly` 下執行的內容](https://code.claude.com/docs/zh-TW/settings-reference#what-runs-under-allowmanagedhooksonly)以取得完整效果清單 |
| [`allowManagedMcpServersOnly`](https://code.claude.com/docs/zh-TW/settings-reference#allowmanagedmcpserversonly) | 當為 `true` 時，只有來自受管理設定的 `allowedMcpServers` 會被遵守。`deniedMcpServers` 仍會從所有來源合併。請參閱[從每個管理員來源讀取的金鑰](#keys-read-from-every-admin-source)以了解哪些受管理來源可以設定它，以及[受管理 MCP 配置](https://code.claude.com/docs/zh-TW/managed-mcp.md) |
| [`allowManagedPermissionRulesOnly`](https://code.claude.com/docs/zh-TW/settings-reference#allowmanagedpermissionrulesonly) | 使受管理設定成為權限規則的唯一設定來源。該項目列出它忽略的每個來源 |
| [`blockedMarketplaces`](https://code.claude.com/docs/zh-TW/settings-reference#blockedmarketplaces) | 市集來源的封鎖清單。在下載前檢查被封鎖的來源，因此它們永遠不會接觸檔案系統。請參閱[受管理市集限制](https://code.claude.com/docs/zh-TW/plugins/org.md#restrict-what-users-can-install) |
| [`channelsEnabled`](https://code.claude.com/docs/zh-TW/settings-reference#channelsenabled) | 允許組織使用[頻道](https://code.claude.com/docs/zh-TW/channels.md)。請參閱[企業控制](https://code.claude.com/docs/zh-TW/channels.md#enterprise-controls)以了解每個方案的預設值 |
| [`disableCommandPluginSources`](https://code.claude.com/docs/zh-TW/settings-reference#disablecommandpluginsources) | 當為 `true` 時，完全封鎖[`command` 外掛程式來源](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference#command-plugin-source)，因此市集宣告的命令永遠不會執行。也會封鎖市集[`headersHelper` 命令](https://code.claude.com/docs/zh-TW/plugins/host-marketplace#authenticate-archive-downloads)，除了受管理設定本身宣告的市集。未設定時，遵循 `allowManagedHooksOnly`。需要 Claude Code v2.1.229 或更新版本，而 `headersHelper` 封鎖需要 v2.1.238 或更新版本 |
| [`disableSideloadFlags`](https://code.claude.com/docs/zh-TW/settings-reference#disablesideloadflags) | 在啟動時拒絕 `--plugin-dir`、`--plugin-url`、`--agents` 和 `--mcp-config` 旗標。在雲端工作階段中，Claude Code 會捨棄伺服器透過 `--mcp-config` 傳遞的 MCP 伺服器，除了其[參考項目](https://code.claude.com/docs/zh-TW/settings-reference.md#disablesideloadflags)列出的例外。需要 Claude Code v2.1.193 或更新版本 |
| [`forceRemoteSettingsRefresh`](https://code.claude.com/docs/zh-TW/settings-reference#forceremotesettingsrefresh) | 當為 `true` 時，會封鎖 CLI 啟動，直到遠端受管理設定被新鮮擷取，如果擷取失敗則退出。請參閱[失敗關閉強制執行](https://code.claude.com/docs/zh-TW/server-managed-settings.md#enforce-fail-closed-startup) |
| [`managedMcpServers`](https://code.claude.com/docs/zh-TW/settings-reference#managedmcpservers) | 提供給每個使用者的遠端 MCP 伺服器，與他們自己的伺服器一起。它提供伺服器而不是鎖定任何東西。請參閱[透過受管理設定提供伺服器](https://code.claude.com/docs/zh-TW/managed-mcp.md#provide-servers-through-managed-settings)。需要 Claude Code v2.1.259 或更新版本 |
| [`managedSourcesBehavior`](https://code.claude.com/docs/zh-TW/settings-reference#managedsourcesbehavior) | Claude Code 是否只應用最高優先級的受管理來源或[組合每一個](#compose-every-managed-source) |
| [`parentSettingsBehavior`](https://code.claude.com/docs/zh-TW/settings-reference#parentsettingsbehavior) | 主機提供的父設定是否在受管理原則下合併 |
| [`pluginSuggestionMarketplaces`](https://code.claude.com/docs/zh-TW/settings-reference#pluginsuggestionmarketplaces) | Claude Code 可能在終端機中向使用者建議其外掛程式的市集 |
| [`pluginTrustMessage`](https://code.claude.com/docs/zh-TW/settings-reference#plugintrustmessage) | 附加到安裝前顯示的外掛程式信任警告的自訂訊息 |
| [`policyHelper`](https://code.claude.com/docs/zh-TW/settings-reference#policyhelper) | 在啟動時計算受管理設定的可執行檔；請參閱[使用原則協助程式計算受管理設定](https://code.claude.com/docs/zh-TW/settings-reference.md#policyhelper) |
| [`sandbox.filesystem.allowManagedReadPathsOnly`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-filesystem-allowmanagedreadpathsonly) | 當為 `true` 時，只有來自受管理設定的 `filesystem.allowRead` 路徑會被遵守。`denyRead` 仍會從所有來源合併 |
| [`sandbox.network.allowManagedDomainsOnly`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-network-allowmanageddomainsonly) | 只遵守受管理的 `allowedDomains` 和 `WebFetch(domain:...)` 允許規則；封鎖其他網域而不提示 |
| [`strictKnownMarketplaces`](https://code.claude.com/docs/zh-TW/settings-reference#strictknownmarketplaces) | 控制使用者可以新增和安裝外掛程式的外掛程式市集來源。請參閱[受管理市集限制](https://code.claude.com/docs/zh-TW/plugins/org.md#restrict-what-users-can-install) |
| [`strictPluginOnlyCustomization`](https://code.claude.com/docs/zh-TW/settings-reference#strictpluginonlycustomization) | 從使用者和專案來源封鎖技能、代理程式、hooks 和 MCP 伺服器；`true` 鎖定全部四個，陣列命名哪個 |
| [`wslInheritsWindowsSettings`](https://code.claude.com/docs/zh-TW/settings-reference#wslinheritswindowssettings) | 當在 HKLM 登錄或 `C:\Program Files\ClaudeCode` 下的檔案中設定時，讓 WSL 讀取 Windows 原則鏈，並且只在[沒有 Windows 管理員文件存在](#present-admin-documents)時才讀取 `/etc/claude-code`；該項目給出順序 |

> [!NOTE]
>
> 在 Team 和 Enterprise 方案上，擁有者在 [Claude Code 管理員設定](https://claude.ai/admin-settings/claude-code)中為整個組織啟用或停用 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 和[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)。當擁有者關閉 Remote Control 時，執行 Claude Code v2.1.286 或更新版本的已連線工作階段也會中斷連線。每個工作階段會在下次重新整理您組織的原則時中斷連線，大約每小時一次。若要了解這些工作階段中會發生的情況，請參閱 [`Remote Control was turned off by your organization's policy`](https://code.claude.com/docs/zh-TW/remote-control#remote-control-was-turned-off-by-your-organizations-policy)。
>
> Remote Control 還可以透過 [`disableRemoteControl`](https://code.claude.com/docs/zh-TW/settings-reference#disableremotecontrol) 設定按裝置停用。雲端工作階段沒有按裝置的受管理設定金鑰。
>
> 若要檢查這些組織設定是否到達指定的機器，請在該處執行 `claude doctor`，並讀取 `Organization policy` 行，該行會說明 Claude Code 從何處載入原則或為什麼沒有載入。需要 Claude Code v2.1.261 或更新版本。在執行中的工作階段中，當原則未載入時，`/status` 會顯示相同的行。

## 為您的組織關閉遙測

Claude Code 預設在使用 Anthropic API 的工作階段上發送 Anthropic 操作[遙測](https://code.claude.com/docs/zh-TW/data-usage.md#telemetry-services)，無論是直接、透過 LLM 閘道還是透過自訂 `ANTHROPIC_BASE_URL`；[按 API 提供者的預設行為](https://code.claude.com/docs/zh-TW/data-usage.md#default-behaviors-by-api-provider)說明哪些提供者發送它。若要為每個開發者關閉它而不依賴每個人的 shell，請透過受管設定的 `env` 區塊傳遞 `DISABLE_TELEMETRY`。此範例為原則到達的每個人設定 `DISABLE_TELEMETRY`：

```json theme={null}
{
  "env": {
    "DISABLE_TELEMETRY": "1"
  }
}
```

Claude Code 應用 `1` 的值而不向使用者顯示[批准對話](https://code.claude.com/docs/zh-TW/server-managed-settings.md#environment-variables-and-the-approval-dialog)。

如果您關閉遙測，Claude Code 停止發送為原則到達的開發者提供您的組織[分析儀表板](https://code.claude.com/docs/zh-TW/analytics.md)的使用資料。變數也關閉[功能標誌擷取](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)，適用於這些開發者。如需遠端控制，請參閱[遠端控制需求](https://code.claude.com/docs/zh-TW/remote-control.md#requirements)。

[原則應用的位置和時間](#where-and-when-a-policy-applies)說明哪個傳遞機制到達每個表面，[平台可用性](https://code.claude.com/docs/zh-TW/server-managed-settings.md#platform-availability)說明哪些工作階段跳過伺服器受管設定擷取。

如果您的組織使用客戶受管加密金鑰並透過閘道路由 Claude Code，[設定代理和閘道](https://code.claude.com/docs/zh-TW/third-party-integrations.md#configure-proxies-and-gateways)說明為什麼這些工作階段需要此變數。

## 另請參閱

* [為您的組織設定 Claude Code](https://code.claude.com/docs/zh-TW/admin-setup.md)：決定要強制執行什麼以及如何強制執行
* [伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)：從 claude.ai 主控台或閘道傳遞原則
* [受管 MCP 設定](https://code.claude.com/docs/zh-TW/managed-mcp.md)：控制開發者可以使用哪些 MCP 伺服器
* [所有設定](https://code.claude.com/docs/zh-TW/settings-reference.md)：每個金鑰，以及受管來源是否可以設定它
* [範例設定檔案](https://code.claude.com/docs/zh-TW/settings-example.md#an-organizations-managed-settings)：完整的 `managed-settings.json` 顯示受管金鑰的形狀

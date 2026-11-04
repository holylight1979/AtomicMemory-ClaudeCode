<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/hipaa-setup | lastmod: 2026-10-29 | section: Administration / Security and data -->
> 來源：https://code.claude.com/docs/zh-TW/hipaa-setup（官方 zh-TW，lastmod 2026-10-29）｜分類：Administration › Security and data｜EN 摘要：Prepare developers' computers to run Claude Code (local mode) under the HIPAA configuration. Covers versions, network access, managed settings, and local data.

# 為 HIPAA-ready 組織設定 Claude Code（本機模式）

> 準備開發人員的電腦，以在 HIPAA 設定下執行 Claude Code（本機模式）。涵蓋版本、網路存取、受管設定及本機資料。

HIPAA 設定是 Claude Enterprise 方案上的一項組織設定，適用於處理受保護健康資訊（PHI）並與 Anthropic 簽訂[商業夥伴協議（BAA）](https://support.claude.com/en/articles/8114513-business-associate-agreements-baa-for-commercial-customers)的組織。此設定適用於 Claude Code（本機模式）和 Cowork（本機模式），並會限制這兩項產品中的功能。

> [!NOTE]
>
> 「（本機模式）」是指本機工作階段，而非[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)。本機工作階段在下列其中一處執行：
>
> * 終端機中的 Claude Code
> * Claude Desktop 的 Code 分頁中的 Claude Code
> * Claude Desktop 中的 Cowork
>
> VS Code 和 JetBrains 的 Claude Code 擴充功能不屬於（本機模式）。套用 HIPAA 設定後，這些擴充功能仍可繼續運作，但您的 BAA 不涵蓋它們。如需完整的合格服務清單，請參閱[實作指南](https://trust.anthropic.com/resources?s=l1wrssd9hsbi4gak0tp5a6\&name=%5Banthropic%5D-hipaa-ready-offering-implementation-guide)。

本頁面適用於負責準備開發人員電腦的 IT 或安全管理員。設定本身由您 Claude 組織的主要擁有者（Primary Owner）套用。[在 HIPAA-ready Enterprise 方案上使用 Claude Code（本機模式）和 Cowork（本機模式）](https://support.claude.com/en/articles/17318731)說明了您的 BAA 包含哪些內容、設定如何套用，以及如何排定套用日期。

如果您組織的成員也使用 Cowork，請同時依照[為 HIPAA-ready 組織設定 Cowork（本機模式）](https://claude.com/docs/cowork/hipaa-setup)進行操作。該文件涵蓋 Claude Desktop 政策及 Cowork 的本機資料。

下表列出各項設定工作的執行時機：

| 時機 | 執行事項 |
| :- | :- |
| 套用設定之前 | [準備電腦](#prepare-computers-before-the-hipaa-configuration-is-applied)：檢查開發人員的連線方式、更新應用程式、允許網路存取、部署受管設定，並限制 Claude Desktop 登入 |
| 套用之後 | Code 分頁會保持關閉，直到擁有者（Owner）重新開啟。[在電腦上確認設定](#confirm-the-configuration-on-a-computer) |
| 持續進行 | [管理本機工作階段資料](#manage-local-session-data) |

## 在套用 HIPAA 設定之前準備電腦

我們建議您從本節的工作開始，並在套用設定之前完成這些工作。

### 檢查開發人員的登入與連線方式

HIPAA 設定僅在開發人員以 Claude Enterprise 帳戶登入，且 Claude Code 直接連線至 Claude API 的工作階段中生效。在任何其他連線方式下，開發人員仍可繼續使用 Claude Code，但不會套用 [HIPAA 設定](#what-developers-see-in-claude-code)。

下表列出哪些連線方式符合資格。若要了解您的 BAA 是否涵蓋「否」列中的工作階段，請參閱[在 HIPAA-ready Enterprise 方案上使用 Claude Code（本機模式）和 Cowork（本機模式）](https://support.claude.com/en/articles/17318731)。

| Claude Code 的連線方式 | 是否符合 HIPAA 設定資格 |
| :- | :- |
| Claude Enterprise 帳戶，直接連線至 Claude API | 是 |
| Amazon Bedrock、Google Cloud 的 Agent Platform、Microsoft Foundry、Claude Platform on AWS，或 [Claude apps 閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway) | 否 |
| [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)或任何其他自訂的 `ANTHROPIC_BASE_URL` | 否 |
| 在沒有 Claude Enterprise 登入的電腦上使用 `ANTHROPIC_AUTH_TOKEN` 或 `apiKeyHelper` | 否 |
| Claude Console API 金鑰或[聯合憑證](https://code.claude.com/docs/zh-TW/authentication.md#anthropic-profiles-and-federation-credentials) | 否。這些工作階段屬於 Claude Console 組織，該組織有其自己的協議與設定 |

#### 檢查電腦的連線方式

在電腦上開啟終端機，執行 `claude`，並在提示字元中輸入 `/status`。**Status** 分頁會顯示以下各行：

| 行 | 出現時機 |
| :- | :- |
| `Login method` 和 `Organization` | 工作階段以 claude.ai 帳戶登入。若為 Claude Enterprise 帳戶，`Login method` 會顯示 `Claude Enterprise account`，而 `Organization` 會顯示您的組織 |
| `API provider` | 僅在工作階段使用雲端供應商或 Claude apps 閘道時出現 |
| `Anthropic base URL` | 僅在設定了 `ANTHROPIC_BASE_URL` 時出現 |

如果電腦使用的連線方式不符合 HIPAA 設定資格，您可以使用[受管設定](#deploy-managed-settings)來封鎖雲端供應商、閘道，以及透過 `ANTHROPIC_API_KEY`、`ANTHROPIC_AUTH_TOKEN` 或 `apiKeyHelper` 設定的憑證。

### 更新 Claude Code 和 Claude Desktop

HIPAA 設定需要 Claude Code v2.1.285 或更新版本，以及 Claude Desktop v2.19675.0 或更新版本。如果您的組織同時使用終端機和 [Claude Desktop 應用程式](https://code.claude.com/docs/zh-TW/desktop.md)，請兩者都更新。

若要查看已安裝的 Claude Code 版本，請在終端機中執行此命令。此命令在 Bash、Zsh 和 PowerShell 中皆相同：

```bash theme={null}
claude --version
```

受支援的安裝會輸出 `2.1.285 (Claude Code)` 或更高的版本號。

若要查看已安裝的 Claude Desktop 版本，請參閱[檢查您的版本](https://code.claude.com/docs/zh-TW/desktop.md#check-your-version)。

#### 開發人員在舊版本上會看到的情況

對於套用 HIPAA 設定的組織，Anthropic 的伺服器會拒絕來自低於最低版本的請求。Anthropic 會隨時間提高最低版本，您不需要進行任何設定。

| 應用程式 | 開發人員在舊版本上會看到的情況 |
| :- | :- |
| Claude Code | 每個請求都會失敗並顯示 [`API Error`](https://code.claude.com/docs/zh-TW/errors#claude-code-does-not-support-this-model)，說明該版本低於您組織政策所要求的最低版本 |
| Claude Desktop | 出現 **Update required** 對話方塊，告知開發人員須更新 Claude Desktop 才能繼續使用 **Code** 分頁 |

若要讓開發人員維持在受支援的版本，請[持續更新 Claude Code](https://code.claude.com/docs/zh-TW/setup.md#update-claude-code)。關於 Claude Desktop，請參閱[更新 Claude Desktop](https://claude.com/docs/cowork/hipaa-setup#update-claude-desktop)。

### 允許網路存取

請透過您的代理伺服器和防火牆，允許下表中的主機透過 HTTPS 連接埠 443 連線。請允許整個主機，而非個別路徑。

| 主機 | 用途 |
| :- | :- |
| `api.anthropic.com` | Claude API 請求、遙測，以及告知 Claude Code 已開啟 HIPAA 設定的組織政策 |
| `claude.ai`、`claude.com`、`platform.claude.com` | 登入及 token 重新整理 |
| `sso.claude.com` | 登入（當您的組織使用單一登入時） |
| `downloads.claude.ai` | 原生安裝程式及其更新 |
| `mcp-proxy.anthropic.com` | [來自 claude.ai 的連接器](https://code.claude.com/docs/zh-TW/mcp.md#use-mcp-servers-from-claude-ai) |

此表列出原生安裝的 Claude Code 在終端機中登入、執行和更新所需的主機。其餘主機列於下列頁面：

* **其他安裝方式與選用功能**：[網路存取需求](https://code.claude.com/docs/zh-TW/network-config.md#network-access-requirements)列出 npm 和 Homebrew 安裝檢查更新時使用的主機，以及外掛安裝等功能所需的主機
* **Code 分頁與 Cowork**：[Desktop 網路存取需求](https://code.claude.com/docs/zh-TW/desktop.md#network-access-requirements)列出 Claude Desktop 額外需要的主機
* **檢查 TLS 的代理伺服器**：[自訂 CA 憑證](https://code.claude.com/docs/zh-TW/network-config.md#custom-ca-certificates)說明如何信任您代理伺服器的憑證

透過企業 HTTPS 代理伺服器的工作階段仍符合 HIPAA 設定資格，只要該代理伺服器能連線至表中的主機即可。

Claude Code 會在啟動時，以及工作階段使用期間約每小時一次，從 `api.anthropic.com` 擷取您組織的政策，藉此得知您的組織已套用 HIPAA 設定。該政策記錄了您組織的 HIPAA 狀態及隨之而來的功能限制。

若要檢查某台電腦是否已擷取政策，請參閱[在電腦上確認設定](#confirm-the-configuration-on-a-computer)。

### 部署受管設定

您可以使用[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)來引導開發人員以 Claude Enterprise 帳戶登入、封鎖雲端供應商和閘道，以及設定每台電腦保留本機工作階段資料的天數。無論 HIPAA 設定是否生效，這些設定都會套用。

本節中的設定是我們建議作為起點的範例。您的組織須自行決定其環境的需求，並確認其設定符合這些需求。

以下範例設定了四個設定鍵，您可以將其加入組織部署的[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md#choose-a-delivery-mechanism)中：

```json theme={null}
{
  "forceLoginMethod": "claudeai",
  "forceLoginOrgUUID": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "allowedProviders": ["anthropic"],
  "cleanupPeriodDays": 30
}
```

若要取得包含沙箱機制、網路允許清單、憑證保護及本機資料保留設定的更完整 `managed-settings.json`，請參閱[設定範例儲存庫](https://github.com/anthropics/claude-code/tree/main/examples/settings)中的 `settings-hipaa.json` 和 `README-hipaa.md`。

#### 各設定鍵的作用

下表列出各設定鍵應設定的值，以及 Claude Code 對其強制執行的內容。

| 設定鍵 | 設定值 | Claude Code 強制執行的內容 |
| :- | :- | :- |
| [`forceLoginMethod`](https://code.claude.com/docs/zh-TW/settings-reference#forceloginmethod) | `"claudeai"` | Claude Code 引導開發人員使用 claude.ai 登入，而非 Claude Console |
| [`forceLoginOrgUUID`](https://code.claude.com/docs/zh-TW/settings-reference#forceloginorguuid) | 您的組織 ID，[擁有者](https://code.claude.com/docs/zh-TW/server-managed-settings.md#access-control)可從 [claude.ai 管理設定](https://claude.ai/admin-settings/organization)中複製 | 當 claude.ai 登入屬於其他組織時，Claude Code 會在啟動時結束 |
| [`allowedProviders`](https://code.claude.com/docs/zh-TW/settings-reference#allowedproviders) | `["anthropic"]` | Claude Code 拒絕在雲端供應商或閘道上啟動 |
| [`cleanupPeriodDays`](https://code.claude.com/docs/zh-TW/settings-reference#cleanupperioddays) | 您的記錄政策允許電腦保留工作階段資料的天數 | 每台電腦都會在相同天數後刪除舊的工作階段資料 |

> [!WARNING]
>
> 部署前請檢查 `forceLoginOrgUUID` 的值。如果它與您的組織 ID 不符，所有以 claude.ai 帳戶登入的開發人員在啟動 Claude Code 時都會直接結束。

HIPAA 設定不會限制 `cleanupPeriodDays`，因此開發人員可以在自己的設定中調高此值。當您在受管設定中設定它時，Claude Code 會忽略開發人員設定的值。

設定了 `forceLoginMethod` 或 `forceLoginOrgUUID` 後，Claude Code 也會拒絕以 `ANTHROPIC_API_KEY`、`ANTHROPIC_AUTH_TOKEN` 或 `apiKeyHelper` 進行身分驗證的工作階段。

#### 確認設定已載入

在具有這些設定的電腦上執行 `claude`，以 Claude Enterprise 帳戶登入，然後輸入 `/status`。`Setting sources` 行會列出 `Enterprise managed settings`，後面以括號標示來源，例如 `(file)`，而 `Allowed providers` 行會顯示 `Anthropic API (managed allowedProviders)`。如果 `Setting sources` 未列出該項，或缺少 `Allowed providers` 行，請參閱[檢查政策是否生效](https://code.claude.com/docs/zh-TW/managed-settings.md#check-that-a-policy-is-in-force)。

#### 受管設定鍵無法封鎖的工作階段

即使部署了這些設定鍵，某些工作階段仍可在沒有 HIPAA 設定的情況下執行：

* **Claude Console 登入和聯合憑證**：`forceLoginOrgUUID` 僅檢查 claude.ai 登入。[將登入限制為您的組織](https://code.claude.com/docs/zh-TW/authentication.md#restrict-login-to-your-organization)列出了 Claude Code 針對各登入途徑和憑證所檢查的內容。
* **伺服器受管設定**：如果您的組織也使用[伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)，請讓擁有者在其中加入相同的設定鍵。[Claude Code 如何合併受管來源](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)說明了套用哪個來源。
* **早於 v2.1.285 的版本**：這些版本會忽略 `allowedProviders`，因此仍可在雲端供應商或閘道上啟動。若要讓 v2.1.163 至 v2.1.284 拒絕啟動，您可以在與[範例設定鍵](#deploy-managed-settings)相同的受管設定中，加入設為 `"2.1.285"` 的 [`requiredMinimumVersion`](https://code.claude.com/docs/zh-TW/settings-reference#requiredminimumversion)。早於 v2.1.163 的版本除了 `allowedProviders` 之外也會忽略 `requiredMinimumVersion`，因此請[更新這些電腦](#update-claude-code-and-claude-desktop)。

若要了解您的 BAA 是否涵蓋在沒有 HIPAA 設定的情況下執行的工作階段，請參閱[在 HIPAA-ready Enterprise 方案上使用 Claude Code（本機模式）和 Cowork（本機模式）](https://support.claude.com/en/articles/17318731)。

### 限制 Claude Desktop 登入

如果開發人員使用 Claude Desktop 的 Code 分頁，也請在 Claude Desktop 政策中設定 `forceLoginOrgUUID`，如[將登入限制為您的組織](https://code.claude.com/docs/zh-TW/desktop.md#restrict-sign-in-to-your-organization)所述。在受管設定中部署 `forceLoginMethod` 和 `forceLoginOrgUUID` 不會變更 Claude Desktop 的登入畫面。

## 在電腦上確認設定

在設定套用至您的組織後，請在一台受管電腦上執行此檢查。

**1. 重新啟動 Claude Code**

結束任何執行中的工作階段，開啟終端機，然後執行 `claude`。使用中的執行中工作階段約在一小時內即可取得設定，無須重新啟動。重新啟動時，Claude Code 會立即擷取設定。

**2. 檢查啟動通知**

確認 Claude Code 啟動時會輸出 `Per your organization's policy, some features are limited · /status for details`。

**3. 檢查頁尾**

確認提示字元下方的頁尾右側出現 `HIPAA configured` 標籤。在 v2.1.286 之前，該標籤顯示為 `HIPAA`。

**4. 執行 /status**

在提示字元中輸入 `/status`。確認 **Status** 分頁在 `Organization configuration` 行上列出 `HIPAA`。

**5. 檢查 Claude Desktop**

套用 HIPAA 設定會關閉您組織的 Code 分頁。如果您的組織有使用此分頁，請請擁有者前往 [**Organization settings > Claude Code**](https://claude.ai/admin-settings/claude-code) 並開啟 **Desktop** 切換開關。關於 Cowork，請參閱[在 Claude Desktop 中確認 HIPAA 設定](https://claude.com/docs/cowork/hipaa-setup#confirm-the-hipaa-configuration-in-claude-desktop)。

重新載入 Claude Desktop 或重新登入。確認標題列顯示 **HIPAA configured** 標籤。在 Mac 上，請開啟側邊欄以查看此標籤。

如果 `/status` 中缺少 `HIPAA`，請依序檢查以下原因：

1. **帳戶或連線方式錯誤**：確認 `/status` 在 `Organization` 行上顯示您的組織，且沒有 `API provider` 或 `Anthropic base URL` 行。[檢查開發人員的登入與連線方式](#check-how-developers-sign-in-and-connect)列出了不符合設定資格的登入與連線方式。
2. **政策擷取遭到封鎖**：在 `/status` 中尋找 `Organization policy` 行，該行會說明原因。在工作階段之外，請執行 `claude doctor` 並查看同一行，該行會說明 Claude Code 從何處載入政策，或政策為何未載入。請透過您的代理伺服器允許 `api.anthropic.com`，然後重新啟動 Claude Code。
3. **設定尚未套用**：詢問主要擁有者是否已套用設定。

## 開發人員在 Claude Code 中會看到的情況

套用 HIPAA 設定後，部分 Claude Code 功能在終端機中會關閉或運作方式有所不同。下表列出開發人員最可能向您詢問的變更。[HIPAA 功能可用性表](https://support.claude.com/en/articles/8114513-business-associate-agreements-baa-for-commercial-customers)列出了所有 Claude Code 和 Cowork 功能，包括擁有者可以重新開啟的功能。

| 開發人員注意到的情況 | 原因 |
| :- | :- |
| WebFetch 工具無法使用 | WebFetch 已關閉。網頁搜尋仍可運作 |
| `--cloud`、`/teleport` 和 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 遭到拒絕 | [雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)和 Remote Control 已關閉 |
| `/feedback` 和 `/bug` 無法使用 | 意見回饋提交已關閉 |
| Claude 無法發佈 [artifact](https://code.claude.com/docs/zh-TW/artifacts.md) | Artifact 發佈已關閉 |
| MCP 工具會預先載入至上下文 | [MCP Tool Search](https://code.claude.com/docs/zh-TW/mcp.md#configure-tool-search) 已關閉。`ENABLE_TOOL_SEARCH` 和受管設定都無法將其重新開啟 |
| 讀取 `ANTHROPIC_API_KEY` 的 MCP 伺服器或 hook 無法再進行身分驗證 | Claude Code 會從其啟動的程序中[移除 Anthropic 憑證](#anthropic-credentials-in-commands-hooks-and-mcp-servers) |
| 以 `/login` 登入其他組織後限制仍然存在 | HIPAA 狀態會持續到 Claude Code 重新啟動為止 |

### 命令、hook 和 MCP 伺服器中的 Anthropic 憑證

套用 HIPAA 設定後，Claude Code 會從其啟動的 shell 命令、hook 和 MCP 伺服器的環境中，移除其用來連線 Anthropic 的憑證，例如 `ANTHROPIC_API_KEY` 和 `ANTHROPIC_AUTH_TOKEN`。

HIPAA 設定不會移除雲端供應商或 GitHub 憑證，因此推送至 GitHub 或呼叫其他服務的命令仍會以該開發人員的存取權限運作。您與 Anthropic 簽訂的 BAA 不涵蓋其傳送至這些服務的資料。如需完整的合格服務清單，請參閱[實作指南](https://trust.anthropic.com/resources?s=l1wrssd9hsbi4gak0tp5a6\&name=%5Banthropic%5D-hipaa-ready-offering-implementation-guide)。

若要限制 Claude 可使用的命令和主機，請參閱[權限規則](https://code.claude.com/docs/zh-TW/permissions.md)和[沙箱](https://code.claude.com/docs/zh-TW/sandboxing.md)。

## 管理本機工作階段資料

Claude Code（本機模式）和 Cowork（本機模式）會將工作階段資料儲存在每位開發人員的電腦上。保護和刪除這些資料是您組織的責任。

### Claude Code 資料

[應用程式資料](https://code.claude.com/docs/zh-TW/claude-directory.md#application-data)列出了 Claude Code（本機模式）在電腦上儲存的內容、其保留清除作業在 `cleanupPeriodDays` 之後會刪除哪些內容，以及哪些內容會保留到有人將其刪除為止。同一頁面也說明了在套用 HIPAA 設定的組織中有何不同。

保留清除作業僅在有人啟動 Claude Code 時執行，因此沒有人啟動 Claude Code 的電腦會保留其資料。

### Code 分頁資料

Code 分頁會將資料儲存在以下位置：

* **逐字稿**：位於 `~/.claude/projects/`，與終端機逐字稿放在一起。[自動清除](https://code.claude.com/docs/zh-TW/claude-directory.md#cleaned-up-automatically)說明了保留清除作業何時會刪除這些逐字稿。
* **Claude Desktop 資料資料夾**：在 macOS 上為 `~/Library/Application Support/Claude`。在 Windows 上為 `%APPDATA%\Claude`，若是從 Anthropic 下載的安裝程式則為 `%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude`，因此請兩者都檢查。套用 HIPAA 設定後，Claude Desktop 會刪除閒置時間超過 `cleanupPeriodDays` 的本機 Code 分頁工作階段，包括已加上星號的工作階段。它只會在執行期間刪除這些工作階段。Claude Desktop 會以下列其中一種方式處理已刪除工作階段的 worktree：
  * **沒有未提交的變更、工作階段未加上星號或釘選，且沒有其他工作階段正在使用該 worktree**：Claude Desktop 會移除該 worktree
  * **其他任何情況**：worktree 會保留在電腦上

在 Windows 上，`~` 代表 `%USERPROFILE%`。

### Cowork 資料

[管理每台電腦上的 Cowork 資料](https://claude.com/docs/cowork/hipaa-setup#manage-cowork-data-on-each-computer)列出了 Cowork（本機模式）儲存資料的位置，以及 Claude Desktop 會刪除的內容。

### 立即刪除工作階段資料

如果您的組織需要在保留清除作業刪除之前移除某位開發人員的工作階段資料，您可以用一個命令移除其中大部分資料。以該開發人員的身分登入電腦，開啟任何 shell，並執行與已安裝的 Claude Code 版本對應的命令。

在 Claude Code v2.1.288 或更新版本上，執行 `claude purge`：

```bash theme={null}
claude purge --all --yes
```

在 v2.1.126 至 v2.1.287 上，執行 `claude project purge`，它接受相同的旗標：

```bash theme={null}
claude project purge --all --yes
```

這兩個命令都會刪除每個專案的逐字稿和自動記憶、`tasks/`、`debug/` 和 `file-history/` 中的項目、`history.jsonl`，以及 `~/.claude.json` 中的專案項目。若未加上 `--yes`，它會先輸出計畫並詢問確認。

清除作業會留下其他可能包含工作階段內容的路徑，例如 `paste-cache/` 中貼上的文字。[清除本機資料](https://code.claude.com/docs/zh-TW/claude-directory.md#clear-local-data)列出了您可以手動刪除的路徑。若要完全清除一台電腦，例如在重新指派之前，請[抹除該電腦](#offboard-a-developer)。

### 開發人員離職處理

移除開發人員的席位或帳戶不會刪除其電腦上的任何內容，`/logout` 也不會刪除工作階段資料。若要移除所有資料，您可以使用裝置管理工具抹除該電腦。

## 相關資源

* [為 HIPAA-ready 組織設定 Cowork（本機模式）](https://claude.com/docs/cowork/hipaa-setup)
* [部署受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)
* [HIPAA 設定範例](https://github.com/anthropics/claude-code/tree/main/examples/settings)
* [企業網路設定](https://code.claude.com/docs/zh-TW/network-config.md)
* [零資料保留](https://code.claude.com/docs/zh-TW/zero-data-retention.md)
* [法律與合規](https://code.claude.com/docs/zh-TW/legal-and-compliance.md)
* [資料使用](https://code.claude.com/docs/zh-TW/data-usage.md)

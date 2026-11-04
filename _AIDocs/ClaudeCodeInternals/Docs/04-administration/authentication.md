<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/authentication | lastmod: 2026-11-03 | section: Administration / Setup and access -->
> 來源：https://code.claude.com/docs/zh-TW/authentication（官方 zh-TW，lastmod 2026-11-03）｜分類：Administration › Setup and access｜EN 摘要：Log in to Claude Code and configure authentication for individuals, teams, and organizations.

# 驗證

> 登入 Claude Code 並為個人、團隊和組織配置驗證。

Claude Code 支援多種驗證方法，具體取決於您的設定。個人使用者可以使用 claude.ai 帳戶登入，而團隊可以使用 Claude for Teams 或 Enterprise、Claude Console 或雲端提供商（如 Amazon Bedrock、Google Cloud 的 Agent Platform 或 Microsoft Foundry）。

## 登入 Claude Code

[安裝 Claude Code](https://code.claude.com/docs/zh-TW/setup.md#install-claude-code) 後，在您的終端機中執行 `claude`。首次啟動時，Claude Code 會為您開啟瀏覽器視窗以供登入，但在下列這類情況下，Claude Code 可以略過登入提示：

* **API 金鑰**：您已設定 `ANTHROPIC_API_KEY` 環境變數，且在 Claude Code 詢問是否使用該金鑰時予以核准
* **先前的登入**：您在第一個工作階段之前已在 shell 中執行 [`claude auth login`](https://code.claude.com/docs/zh-TW/cli-reference#cli-commands)，或您重建了將憑證保存在 [volume](https://code.claude.com/docs/zh-TW/devcontainer.md#persist-authentication-and-settings-across-rebuilds) 中的 dev container。如果您仍然看到登入提示，請[檢查可能造成此情況的原因](#login-prompt-still-appears-after-an-earlier-sign-in)。

如果瀏覽器未自動開啟，請按 `c` 將登入 URL 複製到您的剪貼簿，然後將其貼到您的瀏覽器中。

如果您的瀏覽器在您登入後顯示登入代碼而不是重新導向回來，請將其貼到終端機的 `Paste code here if prompted` 提示處。

登入完成時，終端機會顯示 `Login successful`，並提示您按 `Enter` 繼續。

您可以使用以下任何帳戶類型進行驗證：

* **Claude Pro、Max 或 Ultra 訂閱**：使用您的 claude.ai 帳戶登入。在 [claude.com/pricing](https://claude.com/pricing?utm_source=claude_code\&utm_medium=docs\&utm_content=authentication_pro_max) 訂閱。
* **Claude for Teams 或 Enterprise**：使用您的團隊管理員邀請您的 claude.ai 帳戶登入。
* **Claude Console**：使用您的 Console 認證登入。您的管理員必須先 [邀請您](#claude-console-authentication)。您可以在有或沒有 [建立 API 金鑰](#sign-in-without-an-api-key) 的情況下登入。
* **雲端提供商**：如果您的組織使用 [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md)、[Google Cloud 的 Agent Platform](https://code.claude.com/docs/zh-TW/google-vertex-ai.md) 或 [Microsoft Foundry](https://code.claude.com/docs/zh-TW/microsoft-foundry.md)，請在執行 `claude` 之前設定所需的環境變數，或在登入提示符處選擇 **3rd-party platform**，這會為 Bedrock 和 Vertex AI 啟動互動式設定精靈。不需要瀏覽器登入。
* **Cloud gateway**：如果您的組織執行自託管的 [Claude 應用程式閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)，請透過 `/login` 使用公司 SSO 登入。閘道簽發的權杖是工作階段的唯一認證。

管理員可以指示開發人員使用哪種登入方法，並要求 claude.ai 登入屬於特定組織；請參閱 [限制登入到您的組織](#restrict-login-to-your-organization)。

若要登出並重新驗證，請在 Claude Code 提示符處輸入 `/logout`。登出也會重設您的首次啟動設定狀態，因此下次您執行 `claude` 時，它會再次引導您完成登入和設定。

如果您在登入時遇到問題，請參閱 [驗證疑難排解](https://code.claude.com/docs/zh-TW/troubleshoot-install.md#login-and-authentication)。

### 先前已登入後仍出現登入提示

如果您先前已登入，但首次啟動設定仍顯示登入提示，而不是[略過它](#log-in-to-claude-code)，請檢查下列這類原因：

* **登入已過期**：您先前的登入已過期，且 Claude Code 無法重新整理它。請在提示處再次登入。
* **登入限制於特定組織**：管理員在受管設定中設定了 [`forceLoginOrgUUID`](https://code.claude.com/docs/zh-TW/settings-reference#forceloginorguuid)，以[要求來自特定組織的登入](#restrict-login-to-your-organization)。無論您的帳戶是否屬於其中某個組織，都會出現此提示。請使用屬於所需組織的帳戶登入。如果您沒有這樣的帳戶，請要求您的管理員將您加入。
* **必要的登入方式**：您的登入並非設定檔中 [`forceLoginMethod`](https://code.claude.com/docs/zh-TW/settings-reference#forceloginmethod) 所要求的類型。設為 `"claudeai"` 時，先前 Claude Console 登入所產生的 API 金鑰不算是既有的登入。設為 `"console"` 時，claude.ai 帳戶不算。請使用該設定所指定類型的帳戶登入。
* **較舊的版本**：在 v2.1.290 之前，無論您是否已登入，設定期間都會出現此提示。[更新 Claude Code](https://code.claude.com/docs/zh-TW/setup.md#update-claude-code) 即可略過它。

### 使用多個帳戶登入

若要同時保持登入多個帳戶（例如工作和個人帳戶），請為每個帳戶提供自己的設定目錄。當您啟動 `claude` 時，將 [`CLAUDE_CONFIG_DIR`](https://code.claude.com/docs/zh-TW/env-vars#variables) 環境變數設定為您要使用的帳戶的目錄。每個目錄都有自己的設定、工作階段歷史記錄和 claude.ai 登入或 API 金鑰。例如，在 Bash 或 Zsh 中，將此別名新增到 `~/.bashrc` 或 `~/.zshrc`，以便 `claude-work` 使用您的工作帳戶，而 `claude` 保留您的個人帳戶：

```bash theme={null}
alias claude-work='CLAUDE_CONFIG_DIR=~/.claude-work claude'
```

在您開啟新終端機並首次執行 `claude-work` 後，Claude Code 會引導您完成新目錄的登入和設定。由於 Claude Code 將該類登入儲存在設定目錄外，單獨的目錄無法將兩個 Claude Console 登入 [不使用 API 金鑰](#sign-in-without-an-api-key) 分開。

## 設定團隊身分驗證

對於團隊和組織，您可以透過以下其中一種方式設定 Claude Code 存取權：

* [Claude for Teams 或 Enterprise](#claude-for-teams-or-enterprise)，建議大多數團隊使用
* [Claude Console](#claude-console-authentication)
* [Claude apps 閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)，一種自行託管的閘道，會透過您的 IdP 讓開發人員登入，並將推論路由至您設定的雲端供應商
* [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md)
* [Google Cloud's Agent Platform](https://code.claude.com/docs/zh-TW/google-vertex-ai.md)
* [Microsoft Foundry](https://code.claude.com/docs/zh-TW/microsoft-foundry.md)

### Claude for Teams 或 Enterprise

[Claude for Teams](https://claude.com/pricing?utm_source=claude_code\&utm_medium=docs\&utm_content=authentication_teams#team-&-enterprise) 和 [Claude for Enterprise](https://anthropic.com/contact-sales?utm_source=claude_code\&utm_medium=docs\&utm_content=authentication_enterprise) 為使用 Claude Code 的組織提供最佳體驗。團隊成員可同時存取 Claude Code 和網頁版 Claude，並享有集中計費與團隊管理。

* **Claude for Teams**：自助式方案，提供協作功能、管理工具、SSO、計費管理，以及用於全組織 Claude Code 設定的[伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)。最適合較小的團隊。
* **Claude for Enterprise**：增加網域擷取、角色型權限和合規 API。最適合有安全性與合規需求的大型組織。

**1. 訂閱**

訂閱 [Claude for Teams](https://claude.com/pricing?utm_source=claude_code\&utm_medium=docs\&utm_content=authentication_teams_step#team-&-enterprise)，或聯絡業務團隊洽詢 [Claude for Enterprise](https://anthropic.com/contact-sales?utm_source=claude_code\&utm_medium=docs\&utm_content=authentication_enterprise_step)。

**2. 邀請團隊成員**

從管理儀表板邀請團隊成員。

**3. 安裝並登入**

團隊成員安裝 Claude Code，並使用其 claude.ai 帳戶登入。

### Claude Console 身分驗證

對於偏好以 API 為基礎計費的組織，您可以透過 Claude Console 設定存取權。

**1. 建立或使用 Console 帳戶**

使用您現有的 Claude Console 帳戶或建立新帳戶。

**2. 新增使用者**

您可以透過以下任一方法新增使用者：

* 從 Console 的 Members 頁面 [platform.claude.com/settings/members](https://platform.claude.com/settings/members) 大量邀請使用者：點擊 **Invite**
* [設定 SSO](https://support.claude.com/en/articles/13132885-setting-up-single-sign-on-sso)

**3. 指派角色**

邀請使用者時，指派以下其中一種角色：

* **Claude Code** 角色：使用者只能建立 Claude Code API 金鑰
* **Developer** 角色：使用者可以建立任何類型的 API 金鑰

**4. 使用者完成設定**

每位受邀使用者需要：

* 接受 Console 邀請
* [檢查系統需求](https://code.claude.com/docs/zh-TW/setup.md#system-requirements)
* [安裝 Claude Code](https://code.claude.com/docs/zh-TW/setup.md#install-claude-code)
* 使用 Console 帳戶憑證登入

#### 不使用 API 金鑰登入

您可以在不建立 API 金鑰的情況下登入 Console 帳戶，即使您的組織不允許開發人員建立 API 金鑰也可以。在 `/login` 提示中選擇 Anthropic Console 帳戶，Claude Code 便會詢問您要如何登入。需要 Claude Code v2.1.242 或更新版本。兩種方式都會在瀏覽器中讓您登入 Console，差別在於 Claude Code 之後儲存的內容：

* **使用您的 Console 帳戶登入**，標示為 `(recommended)`：Claude Code 會保留該次登入取得的 OAuth token，並將其儲存為 [Anthropic 設定檔](#anthropic-profiles-and-federation-credentials)。不會建立任何 API 金鑰
* **建立 API 金鑰**，標示為 `(legacy)`：Claude Code 會為您建立 Console API 金鑰，並將其與您的其他憑證一起儲存

實際上，設定檔儲存的是 OAuth 登入，而 API 金鑰則是靜態憑證。Claude Code 會自動重新整理設定檔的登入，當重新整理失敗時，請求會因[設定檔登入已過期錯誤](https://code.claude.com/docs/zh-TW/errors.md#anthropic-profile-login-expired)而失敗，直到您重新登入為止。

並非每台機器都會提供這個選擇。在以下情況中，Claude Code 會直接建立 API 金鑰而不詢問：

* 您透過雲端供應商執行，例如 [Amazon Bedrock、Google Cloud's Agent Platform 或 Microsoft Foundry](https://code.claude.com/docs/zh-TW/third-party-integrations.md)，或 [Claude Platform on AWS](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md)
* 任何設定檔設定了 [`forceLoginOrgUUID`](#restrict-login-to-your-organization)，或將 `forceLoginMethod` 設為 `"claudeai"`
* `forceLoginMethod` 為 `"console"` 且沒有任何設定檔設定 `forceLoginOrgUUID`，直到您在登入失敗後從錯誤畫面重試為止
* 您機器上的某個受管設定來源（例如受管設定檔、MDM 設定檔或快取的伺服器受管設定）存在，但 Claude Code [無法讀取](https://code.claude.com/docs/zh-TW/managed-settings.md#invalid-entries-in-managed-settings)，且沒有其他受管來源提供政策

在不使用金鑰登入之前，請先取消設定 `ANTHROPIC_API_KEY`。

在不使用金鑰登入後，您擁有的是設定檔，而非已儲存的 API 金鑰：

* **寫入哪個設定檔**：Claude Code 會寫入 `ANTHROPIC_PROFILE` 所指定的設定檔，或您目前使用中的設定檔，或 `default`。如果該設定檔是聯合設定檔，Claude Code 會拒絕此次登入，而不會覆寫它
* **會將您登出哪些登入**：Claude Code 會將您登出此機器上儲存的任何 claude.ai 登入
* **如何復原**：執行 `/logout`，這會移除並撤銷此次登入所寫入的憑證

設定檔的其他所有行為都適用於此登入方式，包括它與您其他憑證之間的優先順序、您在 `/status` 中看到的 `Profile` 列，以及需要 claude.ai 登入的功能。請參閱 [Anthropic 設定檔與聯合憑證](#anthropic-profiles-and-federation-credentials)。

#### 在受管機器上停止提供免金鑰登入

若要讓 Claude Code 停止提供[免金鑰登入](#sign-in-without-an-api-key)，請使用您的裝置管理工具，將[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)中的 [`forceLoginOrgUUID`](https://code.claude.com/docs/zh-TW/settings-reference#forceloginorguuid) 部署到每位開發人員的機器。將其設為您的 [Console 組織 ID](https://platform.claude.com/settings/organization)。部署之前，請確認每位開發人員都擁有[可以建立 API 金鑰的角色](#claude-console-authentication)。部署之後，沒有該角色的開發人員將無法在 `/login` 登入 Console。

若只將 `forceLoginMethod` 設為 `"console"`，開發人員可以重試失敗的登入並選擇免金鑰選項。部署 `forceLoginOrgUUID` 後，登入畫面會移除該選項，但開發人員仍可使用他們已有的或透過 [`ant auth login`](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/authentication) 建立的 [Anthropic 設定檔](#anthropic-profiles-and-federation-credentials)。部署之後，請在每台機器上處理以下憑證與登入：

* **免金鑰登入**：若要讓開發人員改用 API 金鑰，請讓他們登出後再次登入 Console，這會建立金鑰。若是免金鑰登入，他們需在 shell 中執行 `claude auth logout`。若是 `ant auth login` 設定檔，他們需執行 `ant auth logout`。如果機器上同時存在設定檔與 API 金鑰，Claude Code 會拒絕工作階段，因此他們必須先登出。
* **環境與輔助程式憑證**：Claude Code 會拒絕使用 `ANTHROPIC_API_KEY`、`ANTHROPIC_AUTH_TOKEN` 或 `apiKeyHelper` 進行身分驗證的工作階段，即使這些憑證是由受管設定提供的也一樣。請移除這些憑證，然後讓開發人員執行 `/login` 以建立已儲存的 API 金鑰。
* **claude.ai 登入**：Claude Code 會[拒絕登入](#restrict-login-to-your-organization)您未列出的組織，包括機器上已在使用中的組織。若要保留某個組織，請將其加入 `forceLoginOrgUUID` 陣列。

### 雲端供應商身分驗證

對於使用 Amazon Bedrock、Google Cloud's Agent Platform 或 Microsoft Foundry 的團隊：

**1. 依照供應商設定**

請依照 [Amazon Bedrock 文件](https://code.claude.com/docs/zh-TW/amazon-bedrock.md)、[Google Cloud's Agent Platform 文件](https://code.claude.com/docs/zh-TW/google-vertex-ai.md)或 [Microsoft Foundry 文件](https://code.claude.com/docs/zh-TW/microsoft-foundry.md)進行設定。

**2. 發佈設定**

將環境變數以及產生雲端憑證的說明發佈給您的使用者。進一步了解如何[在此管理設定](https://code.claude.com/docs/zh-TW/settings.md)。

**3. 安裝 Claude Code**

使用者可以[安裝 Claude Code](https://code.claude.com/docs/zh-TW/setup.md#install-claude-code)。

### 將登入限制於您的組織

若要要求開發人員的 claude.ai 登入屬於特定的 Anthropic 組織，請在[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)中設定 [`forceLoginMethod`](https://code.claude.com/docs/zh-TW/settings-reference#forceloginmethod) 和 [`forceLoginOrgUUID`](https://code.claude.com/docs/zh-TW/settings-reference#forceloginorguuid)。將 `forceLoginOrgUUID` 設為您的組織 ID，對於 Claude for Teams 或 Enterprise 組織，該 ID 顯示於 [claude.ai 管理設定](https://claude.ai/admin-settings/organization)中。對於登入任何其他組織的 claude.ai 登入，Claude Code 會回報錯誤；如果使用中的 claude.ai 憑證屬於未列出的組織，Claude Code 會在啟動時結束。

對於 Claude Console 登入，當您將 `forceLoginOrgUUID` 設為單一 Console 組織 ID（顯示於 [platform.claude.com/settings/organization](https://platform.claude.com/settings/organization)）時，Claude Code 會使用它在 Console 登入頁面上預先選取該組織。無論在登入時或啟動時，它都不會檢查所產生的 Console 憑證屬於哪個組織。在您部署這些設定鍵之前就已使用 Console 帳戶登入的開發人員會保持登入狀態，而該已儲存的金鑰在同時要求[閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)登入的機器上，或在選擇雲端供應商的工作階段中，會遭到封鎖。

如果您在任何設定檔中設定了 `forceLoginOrgUUID`，Claude Code 會在該檔案適用的工作階段中停止提供[免金鑰 Console 登入](#sign-in-without-an-api-key)，改為建立 API 金鑰。若要引導開發人員改用 claude.ai 登入，請將 `forceLoginMethod` 設為 `"claudeai"`。

在 Claude Code v2.1.212 或更新版本中，此處列出的每條登入路徑都會套用 `forceLoginMethod`。在終端機的互動式登入畫面（透過 `/login` 或首次執行的引導流程進入）上，Claude Code 會預先選取 `claudeai` 或 `console` 方式但不會強制執行，因此即使將 `forceLoginMethod` 設為 `"claudeai"`，開發人員仍可在該處完成 Console 登入。

各路徑在 `forceLoginOrgUUID` 上的處理方式不同：

* **終端機、[VS Code 擴充功能](https://code.claude.com/docs/zh-TW/vs-code.md)和 Agent SDK 登入**：會針對 claude.ai 帳戶登入驗證 `forceLoginOrgUUID`
* **`claude setup-token` 和 `/install-github-app`**：只強制執行 `forceLoginMethod`，因此可以在不同的組織中產生 token
* **[閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)登入**：由 `forceLoginMethod: "gateway"` 選取而非受其限制，且不會針對 Anthropic 組織進行身分驗證，因此 `forceLoginOrgUUID` 不適用；請使用您的閘道身分識別提供者來限制存取

請透過您的裝置管理工具部署 `forceLoginMethod` 和 `forceLoginOrgUUID`。開發人員只有在向您的組織完成身分驗證後才會收到[伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)，因此您無法使用這些設定來重新導向首次登入。如果您也從 claude.ai 發佈伺服器受管設定，請在所有用戶端都執行 v2.1.299 或更新版本之前，也在該處設定這兩個設定鍵。關於之後應在何處設定這些設定鍵，以及套用哪個來源的值，請參閱[哪個受管來源提供登入設定鍵](https://code.claude.com/docs/zh-TW/managed-settings.md#which-managed-source-supplies-login-keys)。

在[閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)部署中，也請勿將 `forceLoginMethod` 和 `forceLoginOrgUUID` 放入[閘道提供的設定](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#managed)中。

這些設定鍵也會決定不使用登入憑證的工作階段能否啟動。完整行為請參閱設定參考中的 [`forceLoginOrgUUID`](https://code.claude.com/docs/zh-TW/settings-reference#forceloginorguuid)。

* **`ANTHROPIC_API_KEY`、`ANTHROPIC_AUTH_TOKEN` 或 `apiKeyHelper`**：在啟動時遭到封鎖。在 `forceLoginOrgUUID` 之下，無法驗證環境憑證的組織成員資格；而在 `forceLoginMethod` 之下，該憑證會取代必要的登入。當受管設定也要求[閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)登入時，Claude Code 會以相同方式封鎖先前 Claude Console 登入所儲存的 API 金鑰。請參閱 [Administrator policy requires a Cloud gateway sign-in](https://code.claude.com/docs/zh-TW/errors.md#administrator-policy-requires-a-cloud-gateway-sign-in)
* **雲端供應商工作階段，例如 Amazon Bedrock**：只有在機器上仍存在 `ANTHROPIC_API_KEY`、`ANTHROPIC_AUTH_TOKEN` 或 `apiKeyHelper` 憑證，或先前 Claude Console 登入所儲存的 API 金鑰時，才會遭到封鎖。移除後，工作階段即可啟動。這些工作階段會向您的雲端供應商進行身分驗證，並受其存取政策管轄
* **[Anthropic 設定檔或聯合憑證](#anthropic-profiles-and-federation-credentials)**：不會遭到封鎖，除非機器上同時存在 `ANTHROPIC_API_KEY`、`ANTHROPIC_AUTH_TOKEN` 或 `apiKeyHelper` 憑證，或先前 Claude Console 登入所儲存的 API 金鑰。這些設定鍵不會檢查設定檔屬於哪個組織

### 限制機器可使用的 API 供應商

[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)中的 [`allowedProviders`](https://code.claude.com/docs/zh-TW/settings-reference#allowedproviders) 會列出受管機器可透過哪些服務存取 Claude，例如 Anthropic API、Amazon Bedrock 或 LLM 閘道。它與 `forceLoginMethod` 和 `forceLoginOrgUUID` 互補，後兩者管轄工作階段與 Anthropic 通訊時使用哪個帳戶。需要 Claude Code v2.1.285 或更新版本。

```json managed-settings.json theme={null}
{
  "forceLoginMethod": "claudeai",
  "forceLoginOrgUUID": ["xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"],
  "allowedProviders": ["anthropic", "bedrock"]
}
```

使用此檔案時，已登入您 claude.ai 組織或已設定為使用 Amazon Bedrock 的開發人員可正常啟動。設定為任何其他供應商的工作階段會在啟動時遭到拒絕，而切換至其他供應商的執行中工作階段會在下一個請求時遭到拒絕。[Managed settings don't allow this API provider](https://code.claude.com/docs/zh-TW/errors.md#managed-settings-dont-allow-this-api-provider) 列出了每則訊息。

* **允許 LLM 閘道或代理伺服器**：列出 `"customEndpoint"`，並在同一來源的受管 `env` 區塊中設定閘道的 URL。[設定參考](https://code.claude.com/docs/zh-TW/settings-reference.md#allowedproviders)列出了每個值，並說明哪些端點變數需要在受管 `env` 中固定。
* **在受管機器上部署**：將清單放在承載您其餘政策的受管來源中。該項目的[範圍說明](https://code.claude.com/docs/zh-TW/settings-reference.md#allowedproviders)說明了伺服器受管清單如何與其合併。
* **僅限伺服器受管設定**：僅在[伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)中設定的清單，只會套用到擷取您組織設定的工作階段，因此請將其視為對無法透過裝置管理觸及的機器的便利措施，而非強制執行手段。[平台可用性](https://code.claude.com/docs/zh-TW/server-managed-settings.md#platform-availability)列出了哪些工作階段會擷取這些設定。

## 認證管理

Claude Code 安全地管理您的驗證認證：

* **儲存位置**：
  * 在 macOS 上，認證儲存在加密的 macOS Keychain 中。當 Keychain 拒絕寫入時，例如在 SSH 工作階段中被鎖定時，Claude Code 會改為將您的登入儲存在 `~/.claude/.credentials.json` 中，檔案模式為 `0600`，這與它在 Linux 上使用的儲存方式相同。使用建立 API 金鑰的 Console 登入會失敗，直到 Keychain 可寫入。若要將您的登入移回 Keychain，請遵循[復原步驟](https://code.claude.com/docs/zh-TW/troubleshoot-install.md#not-logged-in-or-token-expired)。
  * 在 Linux 上，認證儲存在 `~/.claude/.credentials.json` 中，檔案模式為 `0600`。
  * 在 Windows 上，認證儲存在 `%USERPROFILE%\.claude\.credentials.json` 中，並繼承您的使用者設定檔目錄的存取控制，預設情況下將檔案限制為您的使用者帳戶。
  * 如果您設定了 `CLAUDE_CONFIG_DIR` 環境變數，Claude Code 會將 `.credentials.json` 檔案保存在該目錄下，包括 macOS 後備寫入的檔案，並讓 macOS Keychain 項目也以該目錄為鍵，因此具有不同 `CLAUDE_CONFIG_DIR` 的工作階段會讀取不同的項目。
  * Claude Code 透過 `/login` 和 `/logout` 管理 `.credentials.json`。若要透過自訂 API 端點路由請求，請改為設定 [`ANTHROPIC_BASE_URL`](https://code.claude.com/docs/zh-TW/env-vars) 環境變數。
* **支援的驗證類型**：claude.ai 認證、Claude API 認證、Microsoft Foundry Auth、Bedrock Auth、Vertex Auth、Anthropic 設定檔和 [Workload Identity Federation](https://platform.claude.com/docs/en/manage-claude/workload-identity-federation) 認證，以及 [Claude apps gateway](https://code.claude.com/docs/zh-TW/claude-apps-gateway) 工作階段令牌。
* **自訂認證指令碼**：設定 [`apiKeyHelper`](https://code.claude.com/docs/zh-TW/settings-reference#apikeyhelper) 設定以執行傳回 API 金鑰的 shell 指令碼。
* **重新整理間隔**：請參閱 [`apiKeyHelper`](https://code.claude.com/docs/zh-TW/settings-reference#apikeyhelper) 以了解 Claude Code 重新執行協助程式的情況。
* **緩慢協助程式通知**：如果 `apiKeyHelper` 花費超過 10 秒的時間傳回金鑰，Claude Code 會在提示符列中顯示警告通知，顯示經過的時間。如果您經常看到此通知，請檢查您的認證指令碼是否可以最佳化。
* **協助程式失敗**：當指令碼以錯誤結束、逾時或不列印任何內容時，請求在三次嘗試內失敗，並顯示 [`Your apiKeyHelper script is failing`](https://code.claude.com/docs/zh-TW/errors#your-apikeyhelper-script-is-failing)。

`apiKeyHelper`、`ANTHROPIC_API_KEY` 和 `ANTHROPIC_AUTH_TOKEN` 適用於 CLI 和包裝它的介面，包括 VS Code 擴充功能、Agent SDK 和 GitHub Actions。Claude Desktop 和雲端工作階段不會呼叫 `apiKeyHelper` 或讀取這些環境變數：它們使用 OAuth，除了執行[第三方推論配置](https://code.claude.com/docs/zh-TW/llm-gateway-connect.md#desktop-app)的桌面工作階段外，該工作階段使用該配置的認證進行驗證。

### 續約即將過期的登入

當您使用 `/login` 建立的登入在三天內即將過期時，Claude Code 會在啟動時顯示警告：`Your login expires in 3 days · run /login to renew`。

執行 `/login` 以續約。警告僅供參考，永遠不會阻止請求：驗證會持續運作，直到登入實際過期。

一旦儲存的登入過期且無法重新整理，每個模型請求都會失敗，並顯示 [`Login expired · Please run /login`](https://code.claude.com/docs/zh-TW/errors#login-expired)，直到您再次登入。

您可以在請求失敗之前檢查此狀態：[`/status`](https://code.claude.com/docs/zh-TW/commands) 顯示 `Login` 列讀取 `Expired — log in again`，加上它為過期登入儲存的組織和電子郵件。該列僅在儲存的 claude.ai 登入是有效認證時出現。該列需要 Claude Code v2.1.210 或更新版本。

警告僅在 claude.ai 登入是有效認證時出現，而不是在雲端提供商、`ANTHROPIC_API_KEY`、`ANTHROPIC_AUTH_TOKEN` 或 `apiKeyHelper` 提供認證時出現。

對於執行無人值守的工作階段，提前續約最為重要。在[代理檢視中的背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)或[遠端控制](https://code.claude.com/docs/zh-TW/remote-control.md)工作階段一旦超過登入生命週期，一旦認證過期就會停止進行，在您再次登入之前無法復原。

### 驗證優先順序

當存在多個認證時，Claude Code 按此順序選擇一個：

1. 雲端提供商認證，當設定了 `CLAUDE_CODE_USE_BEDROCK`、`CLAUDE_CODE_USE_VERTEX` 或 `CLAUDE_CODE_USE_FOUNDRY` 時。請參閱[第三方整合](https://code.claude.com/docs/zh-TW/third-party-integrations.md)以取得設定。
2. `ANTHROPIC_AUTH_TOKEN` 環境變數。作為 `Authorization: Bearer` 標頭傳送。當透過[LLM 閘道或代理](https://code.claude.com/docs/zh-TW/llm-gateway)路由時使用此選項，該閘道或代理使用持有人令牌而不是 Anthropic API 金鑰進行驗證。
3. `ANTHROPIC_API_KEY` 環境變數。作為 `X-Api-Key` 標頭傳送。用於直接 Anthropic API 存取，使用來自 [Claude Console](https://platform.claude.com) 的金鑰。在互動模式下，系統會提示您一次以核准或拒絕金鑰，您的選擇會被記住。若要稍後變更，請使用 `/config` 中的「使用自訂 API 金鑰」切換。該切換僅在 `ANTHROPIC_API_KEY` 在您的環境中設定時出現。在非互動模式 (`-p`) 中，當金鑰存在時始終使用該金鑰。
4. [`apiKeyHelper`](https://code.claude.com/docs/zh-TW/settings-reference#apikeyhelper) 指令碼輸出。用於動態或輪換認證，例如從保管庫擷取的短期令牌。
5. `CLAUDE_CODE_OAUTH_TOKEN` 環境變數。由 [`claude setup-token`](#generate-a-long-lived-token) 產生的長期 OAuth token。用於 CI 管道和指令碼，其中瀏覽器登入不可用。如果您在設定變數時執行 `/login`，Claude Code 會將目前工作階段切換到新登入。若要在新工作階段中保留該登入，請從您的 shell 設定檔以及[可設定它的設定檔](https://code.claude.com/docs/zh-TW/settings-reference.md#variables-claude-code-ignores-in-env)（例如您的使用者設定）中移除該變數。
6. Anthropic 設定檔和聯盟認證，`ant` CLI 和 Workload Identity Federation 使用的認證。`ant auth login` 寫入的設定檔僅在您在 `ANTHROPIC_PROFILE` 中命名它時才排名在此處；否則它排名在 `/login` 下方。請參閱 [Anthropic 設定檔和聯盟認證](#anthropic-profiles-and-federation-credentials)。
7. 來自 `/login` 的訂閱 OAuth 憑證。這是 Claude Pro、Max、Ultra、Team 和 Enterprise 使用者的預設值。

已簽署的 [Claude apps gateway](https://code.claude.com/docs/zh-TW/claude-apps-gateway) 工作階段位於此清單之外：它是一個提供商選擇，如 Amazon Bedrock 或 Google Cloud 的 Agent Platform，並且優先於它們。當閘道工作階段存在時，CLI 使用閘道令牌進行驗證，即使設定了 `CLAUDE_CODE_USE_BEDROCK`、`CLAUDE_CODE_USE_VERTEX` 或 `CLAUDE_CODE_USE_FOUNDRY`，上面的持有人令牌、API 金鑰、`apiKeyHelper` 和設定檔等認證來源也不會被使用。

如果您機器的[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)將 [`forceLoginMethod`](https://code.claude.com/docs/zh-TW/settings-reference#forceloginmethod) 設定為 `"gateway"` 或設定 [`forceLoginGatewayUrl`](https://code.claude.com/docs/zh-TW/settings-reference#forcelogingatewayurl)，且您未透過 `CLAUDE_CODE_USE_BEDROCK` 或 `CLAUDE_CODE_USE_VERTEX` 等變數選擇雲端提供商，您的工作階段僅使用閘道登入。Claude Code 會跳過其他認證來源，並要求您使用 `/login` 登入。請參閱[系統管理員原則需要雲端閘道登入](https://code.claude.com/docs/zh-TW/errors.md#administrator-policy-requires-a-cloud-gateway-sign-in)以了解您在每個剩餘認證中看到的內容。需要 Claude Code v2.1.261 或更新版本，或在僅設定 `forceLoginGatewayUrl` 的機器上需要 v2.1.265 或更新版本。

如果您有有效的 Claude 訂閱，但您的環境中也設定了 `ANTHROPIC_API_KEY`，則 API 金鑰在核准後優先。如果金鑰屬於已停用或過期的組織，這可能會導致驗證失敗。

執行 `unset ANTHROPIC_API_KEY` 以回退到您的訂閱，並檢查 `/status` 以確認哪種方法處於活動狀態。當登入和 API 金鑰都已設定時，`/status` 會標記未使用的認證。

[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)始終使用您的訂閱認證。如果您在雲端環境中設定 `ANTHROPIC_API_KEY` 或 `ANTHROPIC_AUTH_TOKEN`，它不會覆蓋您的訂閱認證。

#### Anthropic 設定檔和聯盟認證

設定檔是您的 [Anthropic 設定目錄](https://platform.claude.com/docs/en/manage-claude/wif-reference#configuration-directory)中的具名認證設定檔，在 macOS 和 Linux 上預設為 `~/.config/anthropic`，在 Windows 上為 `%APPDATA%\Anthropic`。當您為 [Workload Identity Federation (WIF)](https://platform.claude.com/docs/en/manage-claude/workload-identity-federation) 設定設定檔時，其驗證模式為 `oidc_federation`，或當 [`ant auth login`](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/authentication) 寫入它或您[在沒有 API 金鑰的情況下登入 Console 帳戶](#sign-in-without-an-api-key)時為 `user_oauth`。

Claude Code 不會在[裸模式](https://code.claude.com/docs/zh-TW/headless.md#start-faster-with-bare-mode)、Claude Desktop 或雲端工作階段中讀取設定檔或聯盟變數。在這些工作階段中，`/status` 不顯示 `Profile` 列。

Claude Code 按此順序檢查三個來源，並在第一個設定的來源處停止。該表格顯示設定每個來源的內容以及它相對於您的 `/login` 認證的排名。

| 來源 | 設定者 | 相對於 `/login` 的排名 |
| :- | :- | :- |
| 具名設定檔 | `ANTHROPIC_PROFILE` | 上方，無論設定檔具有什麼驗證模式 |
| 聯盟變數 | `ANTHROPIC_FEDERATION_RULE_ID` 和 `ANTHROPIC_ORGANIZATION_ID`，兩者都設定 | 上方 |
| 有效設定檔 | 您設定目錄中的 [`active_config` 檔案](https://platform.claude.com/docs/en/manage-claude/wif-reference#active-profile)，或名為 `default` 的設定檔 | 當其驗證模式為 `oidc_federation` 時上方；當其驗證模式為 `user_oauth` 時在有效的 `/login` 認證下方 |

對於聯盟變數，Claude Code 在交換您的身份令牌時也會讀取 [WIF 參考](https://platform.claude.com/docs/en/manage-claude/wif-reference#environment-variables)中的其他變數，例如 `ANTHROPIC_IDENTITY_TOKEN_FILE`。對於設定檔檔案格式，請參閱 [WIF 參考](https://platform.claude.com/docs/en/manage-claude/wif-reference#profile-configuration-file)。

若要確認 Claude Code 選擇了哪個來源，請執行 `/status`。`Profile` 列會命名來源以代替 `Login method` 列，當設定檔是使用中的認證時，`Organization` 和 `Email` 列會顯示其帳戶。

當 `user_oauth` 設定檔的登入已過期且 Claude Code 無法續約時，請求會失敗，並顯示[設定檔登入過期錯誤](https://code.claude.com/docs/zh-TW/errors.md#anthropic-profile-login-expired)。

需要您的 claude.ai 登入的功能，例如 [claude.ai connectors](https://code.claude.com/docs/zh-TW/mcp.md#use-mcp-servers-from-claude-ai) 和 [`/schedule`](https://code.claude.com/docs/zh-TW/routines)，在選擇這些來源之一時不可用。若要停止 Claude Code 選擇來源：

* **具名設定檔或聯盟變數**：取消設定 `ANTHROPIC_PROFILE`，或取消設定任一聯盟變數
* **有效設定檔**：對於您透過[在沒有 API 金鑰的情況下登入 Console 帳戶](#sign-in-without-an-api-key)寫入其目前認證的 `user_oauth` 設定檔執行 `/logout`，對於 `ant auth login` 寫入其目前認證的設定檔執行 `ant auth logout`，或對於任一驗證模式從您設定目錄中的 `configs/` 刪除設定檔的檔案

### 產生長期令牌

對於 CI 管道、指令碼或其他互動式瀏覽器登入不可用的環境，使用 `claude setup-token` 產生一年期 OAuth 令牌：

```bash theme={null}
claude setup-token
```

該命令會開啟與 `/login` 相同的瀏覽器授權流程，在您在瀏覽器中核准存取後，令牌會列印到終端機。它不會將令牌儲存在任何地方；複製它並將其設定為您想要驗證的任何地方的 `CLAUDE_CODE_OAUTH_TOKEN` 環境變數：

> [tab] macOS, Linux, WSL
>
> ```bash theme={null}
> export CLAUDE_CODE_OAUTH_TOKEN=your-token
> ```

> [tab] Windows PowerShell
>
> ```powershell theme={null}
> $env:CLAUDE_CODE_OAUTH_TOKEN = "your-token"
> ```

> [tab] Windows CMD
>
> ```batch theme={null}
> set CLAUDE_CODE_OAUTH_TOKEN=your-token
> ```

此 token 使用您的 Claude 訂閱進行驗證，需要 Pro、Max、Ultra、Team 或 Enterprise 方案。它只能進行模型請求，因此無法建立 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 工作階段或擷取 [claude.ai 連接器](https://code.claude.com/docs/zh-TW/mcp.md#use-mcp-servers-from-claude-ai)。您在本機設定的 MCP 伺服器仍然可以運作。

[裸模式](https://code.claude.com/docs/zh-TW/headless.md#start-faster-with-bare-mode)不讀取 `CLAUDE_CODE_OAUTH_TOKEN`。如果您的指令碼傳遞 `--bare`，請改用 `ANTHROPIC_API_KEY` 或 `apiKeyHelper` 進行驗證。

<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/data-usage | lastmod: 2026-10-30 | section: Administration / Security and data -->
> 來源：https://code.claude.com/docs/zh-TW/data-usage（官方 zh-TW，lastmod 2026-10-30）｜分類：Administration › Security and data｜EN 摘要：Learn about Anthropic's data usage policies for Claude

# 資料使用

> 了解 Anthropic 對 Claude 資料使用政策

## 資料政策

### 資料訓練政策

**消費者使用者（Free、Pro、Max 和 Ultra 方案）**：
我們讓您選擇是否允許您的資料用於改進未來的 Claude 模型。當此設定開啟時，我們將使用來自 Free、Pro、Max 和 Ultra 帳戶的資料訓練新模型（包括您從這些帳戶使用 Claude Code 時）。

**商業使用者**：（Team 和 Enterprise 方案、API、第三方平台以及 Claude Gov）維持現有政策：Anthropic 不會使用在商業條款下傳送至 Claude Code 的程式碼或提示詞來訓練生成式模型，除非客戶已選擇向我們提供其資料以用於模型改進（例如 [Developer Partner Program](https://support.claude.com/en/articles/11174108-about-the-development-partner-program)）。

### Development Partner Program

如果您明確選擇加入向我們提供訓練素材的方式，例如透過 [Development Partner Program](https://support.claude.com/en/articles/11174108-about-the-development-partner-program)，我們可能會使用所提供的素材來訓練我們的模型。組織管理員可以明確為其組織選擇加入 Development Partner Program。請注意，此計畫僅適用於 Anthropic 第一方 API，不適用於 Amazon Bedrock 或 Google Cloud's Agent Platform 使用者。

### 使用 `/feedback` 命令提供意見回饋

如果您選擇使用 `/feedback` 命令向我們傳送關於 Claude Code 的意見回饋，我們可能會使用您的意見回饋來改進我們的產品和服務。透過 `/feedback`，或透過經由相同路徑回報的 `/bug` 和 `/share` 分享的逐字稿，將保留 5 年。

透過 [Claude 草擬的意見回饋](https://code.claude.com/docs/zh-TW/tools-reference.md#sendfeedback-tool-behavior)，Claude 也可以草擬意見回饋報告，並將其排入您電腦上的佇列供您審閱。在您選擇傳送草稿之前，Claude Code 不會傳送任何內容，而已傳送的草稿會經過與其他 `/feedback` 報告相同的提交路徑和保留期限。

### 工作階段品質調查

當您在 Claude Code 中看到「How is Claude doing this session?」提示時，回應此調查（包括選擇「Dismiss」）只會記錄您的評分。我們不會在評分提示本身中收集或儲存任何對話逐字稿、輸入、輸出或其他工作階段資料。與按讚/倒讚意見回饋或 `/feedback` 報告不同，此工作階段品質調查是一項簡單的產品滿意度指標。

在評分提示之後，您可能會看到另一個後續問題，詢問「Can Anthropic look at your session transcript to help us improve Claude Code?」。這是與評分不同的選擇性第二步驟：

* **Yes**：將您的對話逐字稿、任何 subagent 逐字稿以及磁碟上的原始工作階段日誌檔案上傳至 Anthropic。已知的 API 金鑰和 token 模式會在上傳前遮蔽。原始碼、檔案內容和其他對話內容會按原樣上傳。分享的逐字稿最多保留 6 個月。在 Amazon Bedrock、Google Cloud's Agent Platform、Microsoft Foundry 以及已登入的 [Claude apps 閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)工作階段中，選擇 Yes 會將相同的 payload 寫入 `~/.claude/feedback-bundles/` 下的本機封存檔，而非上傳；在您轉寄該檔案之前，不會有任何內容離開您的電腦。
* **No**：拒絕且不傳送任何內容
* **Don't ask again**：拒絕並讓此後續問題不再出現在未來的工作階段中

除非您明確選擇 **Yes**，否則不會上傳任何內容。啟用[零資料保留](https://code.claude.com/docs/zh-TW/zero-data-retention.md)的組織、產品意見回饋已被組織政策停用的組織，或已設定 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` 的環境，永遠不會看到此後續問題。您對此調查的回應（包括在評分提示後提交的工作階段逐字稿）不會影響您的資料訓練偏好，也不能用於訓練我們的 AI 模型。

若要停用這些調查，請設定 `CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY=1`。當設定了 `DISABLE_TELEMETRY`、`DO_NOT_TRACK` 或 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` 時，調查也會停用。封鎖非必要流量但透過自己的 [OpenTelemetry collector](https://code.claude.com/docs/zh-TW/monitoring-usage.md) 擷取調查回應的組織，可以透過設定 `CLAUDE_CODE_ENABLE_FEEDBACK_SURVEY_FOR_OTEL=1` 重新啟用調查。之後調查只會將評分記錄到已設定的 collector。逐字稿分享後續問題以及所有其他傳送至 Anthropic 的意見回饋流量則維持停用。若要控制頻率而非停用，請在您的設定檔中將 [`feedbackSurveyRate`](https://code.claude.com/docs/zh-TW/settings-reference#feedbacksurveyrate) 設定為介於 `0` 和 `1` 之間的機率。

### 資料保留

Anthropic 會根據您的帳戶類型和偏好保留 Claude Code 資料。

**消費者使用者（Free、Pro、Max 和 Ultra 方案）**：

* 允許將資料用於模型改進的使用者：5 年保留期，以支援模型開發和安全性改進
* 不允許將資料用於模型改進的使用者：30 天保留期
* 隱私設定可隨時在 [claude.ai/settings/data-privacy-controls](https://claude.ai/settings/data-privacy-controls) 變更。

**商業使用者（Team、Enterprise 和 API）**：

* 標準：30 天保留期
* [零資料保留](https://code.claude.com/docs/zh-TW/zero-data-retention.md)：適用於 Claude for Enterprise 上 Claude Code 的合格帳戶。ZDR 不包含在標準 Enterprise 方案中；它會在確認資格後由您的帳戶團隊依組織逐一啟用
* 本機快取：Claude Code 用戶端預設會將工作階段逐字稿以純文字形式在本機 `~/.claude/projects/` 下儲存 30 天，以便恢復工作階段。可使用 `cleanupPeriodDays` 調整期間。請參閱[應用程式資料](https://code.claude.com/docs/zh-TW/claude-directory.md#application-data)，了解儲存了哪些內容以及如何清除。

  在 Claude Desktop 或 Cowork 中啟動或最近一次繼續的工作階段逐字稿，[預設不受該限制](https://code.claude.com/docs/zh-TW/claude-directory.md#cleaned-up-automatically)。

您可以隨時刪除個別雲端工作階段。刪除工作階段會永久移除該工作階段的事件資料。如需刪除工作階段的操作說明，請參閱[刪除工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#delete-sessions)。

在我們的[隱私中心](https://privacy.anthropic.com/)進一步了解資料保留做法。

如需完整詳細資訊，請查閱我們的[商業服務條款](https://www.anthropic.com/legal/commercial-terms)（適用於 Team、Enterprise 和 API 使用者）或[消費者條款](https://www.anthropic.com/legal/consumer-terms)（適用於 Free、Pro、Max 和 Ultra 使用者）以及[隱私權政策](https://www.anthropic.com/legal/privacy)。

## 資料存取

對於所有第一方使用者，您可以了解更多有關為[本機 Claude Code](#local-claude-code-data-flow-and-dependencies) 和[遠端 Claude Code](#cloud-execution-data-flow-and-dependencies) 記錄的資料。[遠端控制](https://code.claude.com/docs/zh-TW/remote-control.md)工作階段遵循本機資料流，因為所有執行都在您的機器上進行；連接時，工作階段文字記錄也會儲存在 Anthropic 伺服器上，以便在裝置間同步對話，如[連接和安全性](https://code.claude.com/docs/zh-TW/remote-control.md#connection-and-security)中所述。請注意，對於遠端 Claude Code，Claude 會存取您啟動 Claude Code 工作階段的儲存庫。Claude 不會存取您已連接但尚未在其中啟動工作階段的儲存庫。

## 本機 Claude Code：資料流和相依性

下圖顯示 Claude Code 在安裝和正常操作期間如何連接到外部服務。實線表示必需的連接，而虛線表示可選或使用者啟動的資料流。

![顯示 Claude Code 外部連接的圖表：安裝/更新連接到發佈伺服器，使用者請求連接到 Anthropic 的 Console 驗證和 public-api，以及可選的遙測流量將指標和錯誤報告傳送到 Anthropic 和第三方服務。透過 /feedback 傳送的意見反應會傳送到 Google Cloud Storage，並可選擇性地建立 GitHub 議題](https://mintcdn.com/claude-code/YR4DRZyI3CdsXkiT/images/claude-code-data-flow.svg?fit=max\&auto=format\&n=YR4DRZyI3CdsXkiT\&q=85\&s=2846ea92cfc2297b8620c31c82b482ad)

Claude Code 在本機執行。為了與 LLM 互動，Claude Code 透過網路發送資料。此資料包括所有使用者提示和模型輸出，在傳輸中透過 TLS 1.2+ 加密。Claude Code 與大多數流行的 VPN 和 LLM 代理相容。

靜止時的加密取決於您的模型提供者：

| 提供者 | 靜止時加密 |
| - | - |
| Anthropic API | 基礎設施層級磁碟加密 (AES-256)。啟用[零資料保留](https://code.claude.com/docs/zh-TW/zero-data-retention.md)以避免伺服器端持久化。 |
| Amazon Bedrock | AES-256 搭配 AWS 管理的金鑰。客戶管理的金鑰可透過 AWS KMS 取得。 |
| Google Cloud 的 Agent Platform | Google 管理的加密金鑰。CMEK 可用。 |
| Microsoft Foundry | 取決於部署的[託管選項](https://platform.claude.com/docs/en/build-with-claude/claude-in-microsoft-foundry#hosting-options)。對於在 Azure 上託管的部署，提示和完成內容保留在 Azure 內；只有使用情況中繼資料和由 Anthropic 安全系統標記的內容會流出到 Anthropic。對於在 Anthropic 上託管的部署，請求路由到 Anthropic 基礎設施，具有 AES-256 磁碟加密。 |

Claude Code 建立在 Anthropic 的 API 上。有關 API 安全控制的詳細資訊，包括 API 記錄程序，請參閱 [Anthropic 信任中心](https://trust.anthropic.com)中的合規性文件。

### 雲端執行：資料流和相依性

[網路上的 Claude Code](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)工作階段預設在 Anthropic 管理的虛擬機器中執行，而不是在本機執行。您的組織路由到[自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)的工作階段在您控制的基礎設施上執行；有關哪些內容保留在您的機器上以及哪些內容仍然流向 Anthropic，請參閱[哪些內容保留在您的基礎設施上](https://code.claude.com/docs/zh-TW/self-hosted-environments#what-stays-on-your-infrastructure)。在 Anthropic 託管的雲端工作階段中：

* \*\*程式碼和資料儲存：\*\*您的儲存庫被複製到工作階段的隔離 VM。Anthropic 儲存工作階段文字記錄，以便您稍後可以返回該工作階段。程式碼和工作階段資料受您帳戶類型的[保留和使用政策](#data-retention)約束
* \*\*認證：\*\*GitHub 認證在 Anthropic 的伺服器上加密儲存，永遠不會進入 VM。來自 VM 的 GitHub 流量透過 Anthropic 代理進行，該代理在伺服器端附加認證
* \*\*網路流量：\*\*所有出站流量都透過安全代理進行，用於稽核記錄和濫用防止
* \*\*工作階段資料：\*\*提示、程式碼變更和輸出遵循與本機 Claude Code 使用相同的資料政策

有關雲端執行的安全詳細資訊，請參閱[安全性](https://code.claude.com/docs/zh-TW/security.md#cloud-execution-security)。

## 遙測服務

Claude Code 傳送兩種操作遙測：使用指標和錯誤報告。您可以使用下面的環境變數分別關閉每一種，或透過設定 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` 一次停用所有非必要流量。設定 `DISABLE_TELEMETRY` 或 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` 也會停用 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md#requirements) 所依賴的功能旗標評估；`DISABLE_ERROR_REPORTING` 則不會。

**指標**：延遲、可靠性和使用模式，透過 TLS 傳送至 Anthropic 和第三方日誌基礎設施。指標永遠不包括您的程式碼、提示或檔案路徑。設定 `DISABLE_TELEMETRY=1` 以選擇退出。

**錯誤報告**：Claude Code 內部的錯誤訊息和堆疊追蹤，透過 TLS 傳送至第三方錯誤追蹤服務。Claude Code 在任何內容離開您的機器之前，會編輯已知的機密、檔案路徑、電子郵件地址和其他個人資訊模式。設定 `DISABLE_ERROR_REPORTING=1` 以選擇退出。

錯誤報告僅在以下所有情況都適用時才開啟：

* 您使用 Claude Pro、Max 或 Ultra 訂閱登入
* 您執行的是 Claude Code v2.1.198 或更新版本
* 您直接連接到 Claude API
* 您的組織沒有零資料保留或 HIPAA 協議

當您執行 `/feedback` 命令時，您的對話歷史記錄（包括程式碼）的副本會發送到 Anthropic。`/bug` 和 `/share` 命令透過相同的路徑提交。在從回饋對話框提交報告之前，您可以選擇要包含多少歷史記錄：僅限目前工作階段（預設值），或也包括同一專案在過去 24 小時或 7 天內的其他工作階段。Claude Code 透過相同的路徑提交 [Claude 起草的回饋](https://code.claude.com/docs/zh-TW/tools-reference.md#sendfeedback-tool-behavior)，包括您在草稿的檢閱畫面上選擇包含的文字記錄。資料在傳輸中使用 TLS 加密，並儲存在 Google Cloud Storage 中，預設情況下會加密靜止的資料。可選地，在公開儲存庫中建立 GitHub 問題。若要選擇退出，請設定 `DISABLE_FEEDBACK_COMMAND` 環境變數為 `1`。

當使用者使用第三方提供者（例如 Amazon Bedrock 或 Google Cloud 的 Agent Platform）或未設定 Anthropic 認證時，`/feedback` 會將報告寫入 `~/.claude/feedback-bundles/` 下的本機封存，而不是將其發送到 Anthropic。已知的 API 金鑰和權杖模式在寫入封存前會被編輯。在使用者將該檔案發送給 Anthropic 帳戶代表或將其附加到支援請求之前，任何內容都不會離開使用者的機器。

## 按 API 提供者的預設行為

根據預設，當使用 Amazon Bedrock、Google Cloud 的 Agent Platform、Microsoft Foundry 或 Claude Platform on AWS 時，錯誤報告、遙測和錯誤報告會停用。工作階段品質調查和 WebFetch 網域安全檢查是例外，無論提供者為何都會執行。在已登入的 [Claude apps gateway](https://code.claude.com/docs/zh-TW/claude-apps-gateway) 工作階段上，使用分析、錯誤報告和對 Anthropic 的調查評分會由閘道認證本身停用，沒有重新啟用的設定。您可以透過設定 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` 一次選擇退出所有非必要流量，包括調查。此變數不會影響 WebFetch 檢查或官方外掛程式市集自動安裝；每個都有其自己的選擇退出：[設定](https://code.claude.com/docs/zh-TW/settings.md)中的 `skipWebFetchPreflight` 用於 WebFetch，以及 `CLAUDE_CODE_DISABLE_OFFICIAL_MARKETPLACE_AUTOINSTALL` 用於市集。以下是完整的預設行為：

| 服務 | Claude API | Google Cloud 的 Agent Platform API | Amazon Bedrock API | Microsoft Foundry API | Claude Platform on AWS |
| - | - | - | - | - | - |
| **Metrics** | 預設開啟。 `DISABLE_TELEMETRY=1` 以停用。 | 預設關閉。 `CLAUDE_CODE_USE_VERTEX` 必須為 1。 | 預設關閉。 `CLAUDE_CODE_USE_BEDROCK` 必須為 1。 | 預設關閉。 `CLAUDE_CODE_USE_FOUNDRY` 必須為 1。 | 預設關閉。 `CLAUDE_CODE_USE_ANTHROPIC_AWS` 必須為 1。 |
| **Error reports** | Pro、Max 和 Ultra 登入在 v2.1.198+ 上預設開啟，否則關閉。 `DISABLE_ERROR_REPORTING=1` 以停用。 | 預設關閉。 `CLAUDE_CODE_USE_VERTEX` 必須為 1。 | 預設關閉。 `CLAUDE_CODE_USE_BEDROCK` 必須為 1。 | 預設關閉。 `CLAUDE_CODE_USE_FOUNDRY` 必須為 1。 | 預設關閉。 `CLAUDE_CODE_USE_ANTHROPIC_AWS` 必須為 1。 |
| **Claude API（`/feedback` 報告）** | 預設開啟。 `DISABLE_FEEDBACK_COMMAND=1` 以停用。 | 預設關閉。 `CLAUDE_CODE_USE_VERTEX` 必須為 1。 | 預設關閉。 `CLAUDE_CODE_USE_BEDROCK` 必須為 1。 | 預設關閉。 `CLAUDE_CODE_USE_FOUNDRY` 必須為 1。 | 預設關閉。 `CLAUDE_CODE_USE_ANTHROPIC_AWS` 必須為 1。 |
| **工作階段品質調查** | 預設開啟。 `CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY=1` 以停用。 | 預設開啟。 `CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY=1` 以停用。 | 預設開啟。 `CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY=1` 以停用。 | 預設開啟。 `CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY=1` 以停用。 | 預設開啟。 `CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY=1` 以停用。 |
| **WebFetch 網域安全檢查** | 預設開啟。 [設定](https://code.claude.com/docs/zh-TW/settings.md)中的 `skipWebFetchPreflight: true` 以停用。 | 預設開啟。 [設定](https://code.claude.com/docs/zh-TW/settings.md)中的 `skipWebFetchPreflight: true` 以停用。 | 預設開啟。 [設定](https://code.claude.com/docs/zh-TW/settings.md)中的 `skipWebFetchPreflight: true` 以停用。 | 預設開啟。 [設定](https://code.claude.com/docs/zh-TW/settings.md)中的 `skipWebFetchPreflight: true` 以停用。 | 預設開啟。 [設定](https://code.claude.com/docs/zh-TW/settings.md)中的 `skipWebFetchPreflight: true` 以停用。 |

所有環境變數都可以簽入 `settings.json`（請參閱[設定參考](https://code.claude.com/docs/zh-TW/settings-reference.md)）。

當主機平台設定 `CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST` 時，Google Cloud 的 Agent Platform、Amazon Bedrock、Microsoft Foundry 和 Claude Platform on AWS 上的指標預設為開啟，並遵循標準 `DISABLE_TELEMETRY` 選擇退出。錯誤報告和 `/feedback` 報告在這些提供者上仍預設為關閉。

### WebFetch 網域安全檢查

在擷取 URL 之前，WebFetch 工具會將請求的主機名稱發送到 `api.anthropic.com`，以根據 Anthropic 維護的安全封鎖清單進行檢查。只會發送主機名稱，不會發送完整 URL、路徑或頁面內容。Claude Code 會將通過檢查的主機名稱快取五分鐘，並在下一個請求時重新檢查被封鎖或失敗的主機名稱。

無論您使用哪個模型提供者，此檢查都會執行，並且不受 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` 影響。如果您的網路封鎖 `api.anthropic.com`，WebFetch 請求會失敗，直到您允許清單該網域或在[設定](https://code.claude.com/docs/zh-TW/settings.md)中設定 `skipWebFetchPreflight: true`。停用檢查意味著 WebFetch 會嘗試擷取任何 URL，而不查詢封鎖清單，因此如果您需要限制 Claude 可以存取的網域，請將其與 [`WebFetch` 權限規則](https://code.claude.com/docs/zh-TW/permissions#webfetch)結合。

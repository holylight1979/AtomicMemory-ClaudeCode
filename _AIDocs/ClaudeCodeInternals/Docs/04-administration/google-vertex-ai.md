<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/google-vertex-ai | lastmod: 2026-11-03 | section: Administration / Deployment -->
> 來源：https://code.claude.com/docs/zh-TW/google-vertex-ai（官方 zh-TW，lastmod 2026-11-03）｜分類：Administration › Deployment｜EN 摘要：Learn about configuring Claude Code through Google Cloud's Agent Platform, formerly Vertex AI, including setup, IAM configuration, and troubleshooting.

# Google Cloud 的 Agent Platform 上的 Claude Code

> 了解如何透過 Google Cloud 的 Agent Platform（前身為 Vertex AI）設定 Claude Code，包括設定、IAM 設定和故障排除。

**Deploying Claude Code across your organization?** Talk to sales about enterprise plans, SSO, and centralized billing.

View plans
Contact sales

## 先決條件

在使用 Google Cloud 的 Agent Platform（前身為 Vertex AI）設定 Claude Code 之前，請確保您具有：

* 已啟用計費的 Google Cloud Platform (GCP) 帳戶
* 已啟用 Google Cloud 的 Agent Platform API 的 GCP 專案
* 存取所需的 Claude 模型（例如 Claude Sonnet 4.6）
* 已安裝並設定 Google Cloud SDK (`gcloud`)
* 在所需的 GCP 區域中分配的配額

若要使用您自己的 Google Cloud 的 Agent Platform 認證登入，請遵循下方的[使用 Google Cloud 的 Agent Platform 登入](#sign-in-with-agent-platform)。若要在整個團隊中部署 Claude Code，請使用[手動設定](#set-up-manually)步驟並在推出前[固定您的模型版本](#5-pin-model-versions)。

## 使用 Agent Platform 登入

如果您擁有 Google Cloud 憑證，並希望開始透過 Google Cloud's Agent Platform 使用 Claude Code，登入精靈會引導您完成設定。GCP 端的先決條件每個專案只需完成一次；Claude Code 端則由精靈處理。

**1. 在您的 GCP 專案中啟用 Claude 模型**

為您的專案[啟用 Google Cloud's Agent Platform API](#1-enable-agent-platform-api)，然後在 [Google Cloud's Agent Platform Model Garden](https://console.cloud.google.com/vertex-ai/model-garden) 中請求存取您想使用的 Claude 模型。如需了解您的帳戶所需的權限，請參閱 [IAM 設定](#iam-configuration)。

**2. 啟動 Claude Code 並選擇 Google Cloud's Agent Platform**

執行 `claude`。在登入提示中，選擇 **3rd-party platform**，然後選擇 **Google Vertex AI**，這是登入提示目前仍用於 Google Cloud's Agent Platform 的標籤。如果您已經登入，請執行 `/login` 以開啟相同的選單。

**3. 依照精靈提示操作**

選擇您向 Google Cloud 進行身分驗證的方式：來自 `gcloud` 的 Application Default Credentials、服務帳戶金鑰檔案，或環境中既有的憑證。精靈會詢問您的專案和區域，驗證您的專案可以呼叫哪些 Claude 模型，並讓您固定這些模型。精靈會將結果儲存到您的[使用者設定檔](https://code.claude.com/docs/zh-TW/settings.md)的 `env` 區塊中，因此您不需要自行匯出環境變數。

登入後，您可以隨時執行 `/setup-vertex` 重新開啟精靈，以變更您的憑證、專案、區域或模型固定設定。模型固定步驟會從您目前已固定的模型開始。精靈會寫入 `~/.claude/settings.json`，若已設定 [`CLAUDE_CONFIG_DIR`](https://code.claude.com/docs/zh-TW/env-vars#variables)，則會寫入 `$CLAUDE_CONFIG_DIR/settings.json`。

## 區域設定

Claude Code 支援 Google Cloud 的 Agent Platform [全球](https://cloud.google.com/blog/products/ai-machine-learning/global-endpoint-for-claude-models-generally-available-on-vertex-ai)、多區域和區域端點。將 `CLOUD_ML_REGION` 設定為 `global`、多區域位置（例如 `eu` 或 `us`）或特定區域（例如 `us-east5`）。Claude Code 為每種形式選擇正確的 Google Cloud 的 Agent Platform 主機名稱，包括多區域位置的 `aiplatform.eu.rep.googleapis.com` 和 `aiplatform.us.rep.googleapis.com` 主機。

> [!NOTE]
>
> Google Cloud 的 Agent Platform 可能不支援每個端點類型上的 Claude Code 預設模型。模型可用性在[特定區域](https://cloud.google.com/vertex-ai/generative-ai/docs/learn/locations#genai-partner-models)、多區域位置和[全球端點](https://cloud.google.com/vertex-ai/generative-ai/docs/partner-models/use-partner-models#supported_models)之間有所不同。您可能需要切換到支援的位置或指定支援的模型。

## 手動設定

若要透過環境變數而非精靈來設定 Google Cloud 的 Agent Platform，例如在 CI 或指令碼化企業推出中，請遵循下列步驟。

### 啟用 Agent Platform API

在您的 GCP 專案中啟用 Google Cloud 的 Agent Platform API。將 `YOUR-PROJECT-ID` 替換為您的 GCP 專案 ID，並在下方的設定步驟中使用：

```bash theme={null}
# 設定您的專案 ID
gcloud config set project YOUR-PROJECT-ID

# 啟用 Agent Platform API
gcloud services enable aiplatform.googleapis.com
```

### 要求模型存取權

要求在 Google Cloud 的 Agent Platform 中存取 Claude 模型：

1. 前往 [Google Cloud 的 Agent Platform Model Garden](https://console.cloud.google.com/vertex-ai/model-garden)
2. 搜尋「Claude」模型
3. 要求存取所需的 Claude 模型（例如 Claude Sonnet 4.6）
4. 等待核准（可能需要 24-48 小時）

### 設定 GCP 認證

Claude Code 使用標準 Google Cloud 驗證。

如需詳細資訊，請參閱 [Google Cloud 驗證文件](https://cloud.google.com/docs/authentication)。

Claude Code 透過相同的 Application Default Credentials 鏈支援 [X.509 憑證型 Workload Identity Federation](https://cloud.google.com/iam/docs/workload-identity-federation-with-x509-certificates)。將 `GOOGLE_APPLICATION_CREDENTIALS` 設定為您的認證設定檔路徑。

> [!NOTE]
>
> Claude Code 將 Google Cloud 的 Agent Platform 要求定址到 `ANTHROPIC_VERTEX_PROJECT_ID` 中的專案，即使 `GCLOUD_PROJECT`、`GOOGLE_CLOUD_PROJECT` 或 `GOOGLE_APPLICATION_CREDENTIALS` 參考的認證檔案包含不同的專案。

#### 進階認證設定

Claude Code 透過 `gcpAuthRefresh` 設定支援 GCP 的自動認證重新整理。將其新增至您的 Claude Code [設定檔](https://code.claude.com/docs/zh-TW/settings.md)，例如 `~/.claude/settings.json`。當 Claude Code 偵測到您的 GCP 認證已過期或無法載入時，它會執行已設定的命令以在重試要求前取得新認證。

```json theme={null}
{
  "gcpAuthRefresh": "gcloud auth application-default login",
  "env": {
    "ANTHROPIC_VERTEX_PROJECT_ID": "your-project-id"
  }
}
```

在執行命令前，Claude Code 會使用您目前的認證要求存取權杖，以確認認證確實已過期，並在認證仍然有效時略過命令。

如果檢查未在五秒內完成，Claude Code 也會略過命令，並僅在要求因認證錯誤而失敗後才執行。在 v2.1.261 之前，逾時的檢查會被視為過期的認證，因此即使您的認證仍然有效，命令也可能在啟動時開啟您的瀏覽器。

Claude Code 會向您顯示命令的輸出，但無法傳送命令互動式輸入。這適用於 CLI 顯示 URL 且您在瀏覽器中完成驗證的瀏覽器型驗證流程。如果驗證未完成，重新整理命令會在三分鐘後逾時。如果您在專案設定（例如 `.claude/settings.json`）中設定 `gcpAuthRefresh`，Claude Code 會在與設定檔中 hooks 相同的[工作區信任規則](https://code.claude.com/docs/zh-TW/permissions.md#what-runs-before-you-trust-a-folder)下執行，其中包括您從未信任的資料夾中的 `-p` 工作階段。

### 設定 Claude Code

設定下列環境變數：

```bash theme={null}
# 啟用 Agent Platform 整合
export CLAUDE_CODE_USE_VERTEX=1
export CLOUD_ML_REGION=global
export ANTHROPIC_VERTEX_PROJECT_ID=YOUR-PROJECT-ID

# 選用：覆寫 Agent Platform 端點 URL 以用於自訂端點或閘道
# export ANTHROPIC_VERTEX_BASE_URL=https://aiplatform.googleapis.com

# 當 CLOUD_ML_REGION=global 時，覆寫不支援全域端點的模型的區域
export VERTEX_REGION_CLAUDE_HAIKU_4_5=us-east5
export VERTEX_REGION_CLAUDE_4_6_SONNET=europe-west1
```

大多數模型版本都有對應的 `VERTEX_REGION_CLAUDE_*` 變數。請參閱[環境變數參考](https://code.claude.com/docs/zh-TW/env-vars.md#variables)以取得完整清單。檢查 [Google Cloud 的 Agent Platform Model Garden](https://console.cloud.google.com/vertex-ai/model-garden) 以判斷哪些模型支援全域端點與僅限區域端點。

如果區域值的格式不像區域或位置名稱，Claude Code 會將其視為未設定。例如，Claude Code 會將包含斜線、點或空格的值視為未設定。Claude Code 會針對每個變數回退到不同的來源：

* `VERTEX_REGION_CLAUDE_*`：Claude Code 回退到 `CLOUD_ML_REGION`。
* `CLOUD_ML_REGION`：Claude Code 回退到 `us-east5`。

[Prompt caching](https://code.claude.com/docs/zh-TW/prompt-caching.md) 會自動啟用。若要停用，請設定 `DISABLE_PROMPT_CACHING=1`。若要要求 1 小時快取 TTL 而非 5 分鐘預設值，請設定 `ENABLE_PROMPT_CACHING_1H=1`；具有 1 小時 TTL 的快取寫入會以更高的費率計費。若要為您的主要對話和 Claude Code 在其外部進行的要求設定不同的 TTL，請[自行選擇 TTL](https://code.claude.com/docs/zh-TW/prompt-caching.md#choose-the-ttl-yourself)。

若要提高您的速率限制，請聯絡 Google Cloud 支援。使用 Google Cloud 的 Agent Platform 時，`/logout` 命令無法使用，因為驗證是透過 Google Cloud 認證處理。

Claude Code 根據模型世代在 [MCP 工具搜尋](https://code.claude.com/docs/zh-TW/mcp.md#scale-with-mcp-tool-search)和預先載入之間決定：

* **Claude Opus 4.5、Sonnet 4.5、Haiku 4.5 及更新版本**：Claude Code 預設啟用工具搜尋。
* **較早的模型**：Claude Code 預先載入 MCP 工具定義，因為其 Agent Platform 服務堆疊拒絕所需的 beta 標頭。設定 `ENABLE_TOOL_SEARCH=true` 不會覆寫此設定。

設定 `ENABLE_TOOL_SEARCH=false` 以在每個模型上停用工具搜尋。在 v2.1.221 之前，Claude Code 在 Google Cloud 的 Agent Platform 上停用所有模型的工具搜尋，除非您設定 `ENABLE_TOOL_SEARCH=true`。

### 釘選模型版本

> [!WARNING]
>
> 在部署到多個使用者時釘選特定模型版本。不釘選的情況下，模型別名（例如 `sonnet` 和 `opus`）會解析為 Claude Code 針對 Google Cloud 的 Agent Platform 的內建預設值，這可能會落後最新版本，且可能尚未在您的專案中啟用。Claude Code 在啟動時會在預設值無法使用時[回退](#startup-model-checks)到較早或較低階的模型，但釘選可讓您控制使用者何時移至新模型。

將這些環境變數設定為特定 Google Cloud 的 Agent Platform 模型 ID。

不使用 `ANTHROPIC_DEFAULT_OPUS_MODEL` 的情況下，Google Cloud 的 Agent Platform 上的 `opus` 別名會解析為 Opus 5.5，不使用 `ANTHROPIC_DEFAULT_SONNET_MODEL` 的情況下，`sonnet` 別名會解析為 Sonnet 4.5。此範例將每個別名釘選到特定版本：

```bash theme={null}
export ANTHROPIC_DEFAULT_OPUS_MODEL='claude-opus-4-8'
export ANTHROPIC_DEFAULT_SONNET_MODEL='claude-sonnet-5'
export ANTHROPIC_DEFAULT_HAIKU_MODEL='claude-haiku-4-5@20251001'
```

如需目前和舊版模型 ID，請參閱[模型概觀](https://platform.claude.com/docs/en/about-claude/models/overview)。請參閱[模型設定](https://code.claude.com/docs/zh-TW/model-config.md#pin-models-for-third-party-deployments)以取得完整的環境變數清單。

未設定釘選變數時，Claude Code 會使用這些預設模型：

| 模型類型 | 預設值 |
| :- | :- |
| 主要模型 | `claude-opus-5-5` |
| 小型/快速模型 | `claude-sonnet-4-5@20250929` |

在 v2.1.280 之前，Google Cloud 的 Agent Platform 上的主要模型預設為 Opus 5，`opus` 別名從 v2.1.219 起解析為 Opus 5。

背景工作（例如工作階段標題產生）使用小型/快速模型，通常是 Haiku 級模型。在 Google Cloud 的 Agent Platform 上，Claude Code 針對背景工作使用預設 Sonnet 模型，因為 Haiku 可能未在每個專案或區域中啟用。兩個選項會變更哪個模型執行它們：

* 當您使用 `--model`、`ANTHROPIC_MODEL` 或 `model` 設定選擇主要模型時，背景工作會使用該模型。當 Claude Code 在您使用 [`ANTHROPIC_DEFAULT_MODEL`](https://code.claude.com/docs/zh-TW/model-config#set-a-default-model-for-new-sessions) 設定的模型上啟動工作階段時，背景工作也會使用該模型。設定 `ANTHROPIC_DEFAULT_OPUS_MODEL` 而不設定 `ANTHROPIC_DEFAULT_SONNET_MODEL` 也會計為選擇，因為內建 Sonnet 模型可能未在引導其自身 Opus 的專案中啟用。
* 若要針對背景工作使用 Haiku，請將 `ANTHROPIC_DEFAULT_HAIKU_MODEL` 設定為您的專案中可用的模型 ID。

> [!WARNING]
>
> Opus 模型的每 token 價格高於 Sonnet 模型，因此如果您不釘選主要模型，將會以 Opus 費率計費。若要使用 Sonnet 4.5 作為主要模型，請將 `ANTHROPIC_MODEL` 設定為其完整模型 ID。以 `ANTHROPIC_DEFAULT_SONNET_MODEL` 引導預設值且未設定 `ANTHROPIC_DEFAULT_OPUS_MODEL` 的部署會將其引導的 Sonnet 模型保持為預設值。

若要進一步自訂模型：

```bash theme={null}
export ANTHROPIC_MODEL='claude-opus-4-8'
export ANTHROPIC_DEFAULT_HAIKU_MODEL='claude-haiku-4-5@20251001'
```

### 驗證您的設定

啟動 Claude Code 並執行 `/status` 以確認設定。`API provider` 行顯示 `Google Vertex AI`，`GCP project`、`Default region` 和 `Model` 行顯示您的專案 ID、區域和已解析的模型。如果提供者行遺失，環境變數未到達程序。確認它們已在您啟動 `claude` 的殼層中匯出，或在您的[設定檔](https://code.claude.com/docs/zh-TW/settings.md)的 `env` 區塊中設定。

## 啟動模型檢查

當 Claude Code 以 Google Cloud 的 Agent Platform 設定啟動時，它會驗證它打算使用的模型在您的專案中是否可存取。

您可能已固定了比目前 Claude Code 預設值更舊的模型版本。如果您的專案可以呼叫較新版本，Claude Code 會提示您更新固定：

* **如果您接受**：Claude Code 會將新模型 ID 寫入您的[使用者設定檔](https://code.claude.com/docs/zh-TW/settings.md)並重新啟動
* **如果您拒絕**：Claude Code 會記住您的選擇，直到下一次預設版本變更

對於位於[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)之 `env` 區塊中的固定，Claude Code 不會執行檢查，也不會顯示提示。如果針對此固定仍出現更新提示，請將 Claude Code 更新至 v2.1.314 或更新版本。在 v2.1.314 之前，受管固定在您接受後仍會持續生效，因此提示會在下次啟動時再次出現。

如果您尚未固定模型，且目前預設值在您的專案中無法使用，Claude Code 會在目前工作階段中回退並顯示通知。它會先嘗試預設模型的較早版本，當預設為 Opus 模型且沒有可用的 Opus 版本時，會回退到預設 Sonnet 模型。回退不會被保留。在 [Model Garden](https://console.cloud.google.com/vertex-ai/model-garden) 中啟用較新模型或[固定版本](#5-pin-model-versions)以使選擇永久化。

### 在特定模型上啟動工作階段

當您在特定 Sonnet 或 Opus 版本上啟動工作階段時，例如使用 `--model`、`ANTHROPIC_MODEL` 或 [`model` 設定](https://code.claude.com/docs/zh-TW/settings-reference#model)，該版本會作為工作階段針對相符 `sonnet` 或 `opus` 別名的固定預設值。Claude Code 會略過您設定的模型所取代之內建預設值的可用性檢查，並在您設定的模型上啟動，不會有回退通知。

當您以模型別名（例如 `opus`）或 Claude Code 無法識別的模型 ID 啟動工作階段時，該值不會作為固定。

### 記住的模型拒絕

當啟動模型檢查發現您的專案無法呼叫的模型時，Claude Code 可以在此機器上記住該拒絕長達一天。在距離上次檢查已過十分鐘後，Claude Code 會在啟動時再次檢查目前預設模型的記住拒絕。您的管理員重新啟用的預設值便會恢復。若要關閉此記憶功能，請設定 [`CLAUDE_CODE_SKIP_MODEL_ACCESS_MEMORY=1`](https://code.claude.com/docs/zh-TW/env-vars)。

### 當您的組織強制執行模型允許清單時

如果您在受管設定中設定 [`enforceAvailableModels`](https://code.claude.com/docs/zh-TW/model-config#enforce-the-allowlist-for-the-default-model)，啟動模型檢查只會使用您的 `availableModels` 清單所允許的模型。這需要 Claude Code v2.1.287 或更新版本。未搭配 `enforceAvailableModels` 的清單不會限制這些檢查。

這些檢查會將每個項目與其將傳送至 Agent Platform 的模型 ID 進行比較，因此請以這些 ID 撰寫清單。此範例允許 Opus 4.8 和 Sonnet 4.5：

```json theme={null}
{
  "availableModels": ["claude-opus-4-8", "claude-sonnet-4-5@20250929"],
  "enforceAvailableModels": true
}
```

關於別名、版本前綴和 `modelOverrides` 項目，請參閱[為第三方部署固定模型](https://code.claude.com/docs/zh-TW/model-config.md#pin-models-for-third-party-deployments)。

### 當模型在工作階段中被停用時

如果您的專案失去對工作階段執行所在模型的存取權，例如因為管理員在 [Model Garden](https://console.cloud.google.com/vertex-ai/model-garden) 中停用它，Claude Code 會將工作階段切換到另一個模型，而不是讓每個請求都失敗，並顯示 `Switched to <fallback> because <model> is not available`。它會嘗試與啟動回退相同的模型：先嘗試相同層級的較早版本，對於沒有可用 Opus 版本的 Opus 工作階段，則嘗試預設 Sonnet 模型。

切換僅適用於您未固定的層級，這與啟動回退的條件相同。在您選擇的特定版本上的工作階段會保持其模型，且沒有回退模型鏈，請求會失敗。在 [auto mode](https://code.claude.com/docs/zh-TW/permission-modes.md#enable-auto-mode-on-bedrock-agent-platform-or-foundry) 中，Claude Code 只會切換到 Agent Platform 上 auto mode 支援的模型。如果這些模型都無法使用，請求會失敗。

您設定的[回退模型鏈](https://code.claude.com/docs/zh-TW/model-config.md#fallback-model-chains)會取代層級切換：在這些拒絕上，Claude Code 會切換到您設定的回退。若要讓被拒絕的請求失敗而不是切換，請設定 [`CLAUDE_CODE_DISABLE_MODEL_ACCESS_FALLBACK=1`](https://code.claude.com/docs/zh-TW/env-vars)。您設定的回退鏈仍會在這些拒絕上切換；如果您想讓每個被拒絕的請求都失敗，也請移除該鏈。

## IAM 設定

指派 `roles/aiplatform.user` 角色，其中包含所需的權限：

* `aiplatform.endpoints.predict` - 模型呼叫和權杖計數所需

如需更嚴格的權限，請建立只包含上述權限的自訂角色。

如需詳細資訊，請參閱 [Google Cloud 的 Agent Platform IAM 文件](https://cloud.google.com/vertex-ai/docs/general/access-control)。

> [!NOTE]
>
> 為 Claude Code 建立專用的 GCP 專案，以簡化成本追蹤和存取控制。

## 1M token context window

Fable 模型、Sonnet 5 及更新版本，以及 Opus 4.7 及更新版本，在 Google Cloud 的 Agent Platform 上預設以 [1M token 上下文視窗](https://platform.claude.com/docs/zh-TW/build-with-claude/context-windows#context-window-sizes-by-model)執行，無需 `[1m]` 後綴。若要改為維持 200K 視窗，請設定 [`CLAUDE_CODE_DISABLE_1M_CONTEXT=1`](https://code.claude.com/docs/zh-TW/model-config#turn-off-1m-context)。

Opus 4.6 和 Sonnet 4.6 在您選擇其 `[1m]` 變體時可使用 1M 視窗。[設定精靈](#sign-in-with-agent-platform)在固定模型時提供 1M context 選項。若要改為手動固定的模型啟用它，請在模型 ID 後附加 `[1m]`。如需詳細資訊，請參閱[為第三方部署固定模型](https://code.claude.com/docs/zh-TW/model-config.md#pin-models-for-third-party-deployments)，包括如何在不變更固定設定的情況下使用 1M 視窗。

在 v2.1.287 之前，Fable 模型以及 Opus 4.7 及更新版本在 Google Cloud 的 Agent Platform 上預設以 200K 視窗執行，並透過 `[1m]` 後綴使用 1M 視窗。

## 故障排除

如果您遇到「無法載入預設認證」錯誤：

* 執行 `gcloud auth application-default login` 以設定應用程式預設認證
* 將 `GOOGLE_APPLICATION_CREDENTIALS` 設定為服務帳戶金鑰檔案路徑
* 請參閱 [設定 GCP 認證](#3-configure-gcp-credentials) 以了解所有選項

如果您遇到配額問題：

* 透過 [Cloud Console](https://cloud.google.com/docs/quotas/view-manage) 檢查目前配額或要求增加配額

如果您遇到「找不到模型」404 錯誤：

* 確認模型在 [Model Garden](https://console.cloud.google.com/vertex-ai/model-garden) 中已啟用
* 驗證模型在您指定的位置中可用。某些模型僅在 `global` 或多區域位置（例如 `eu` 和 `us`）上提供，不在特定區域中
* 如果使用 `CLOUD_ML_REGION=global`，請檢查您的模型是否在 [Model Garden](https://console.cloud.google.com/vertex-ai/model-garden) 中的「支援的功能」下支援全球端點。對於不支援全球端點的模型，請執行下列其中一項：
  * 透過 `ANTHROPIC_MODEL` 或 `ANTHROPIC_DEFAULT_HAIKU_MODEL` 指定支援的模型，或
  * 使用該模型的 `VERTEX_REGION_CLAUDE_*` 變數設定區域或多區域位置，這些變數列於[環境變數參考](https://code.claude.com/docs/zh-TW/env-vars.md#variables)中

如果您遇到 429 錯誤：

* 對於區域端點，請確保主要模型和小型/快速模型在您選擇的區域中受支援
* 考慮切換到 `CLOUD_ML_REGION=global` 以獲得更好的可用性

## 其他資源

* [Google Cloud 的 Agent Platform 文件](https://cloud.google.com/vertex-ai/docs)
* [Google Cloud 的 Agent Platform 定價](https://cloud.google.com/vertex-ai/pricing)
* [Google Cloud 的 Agent Platform 配額和限制](https://cloud.google.com/vertex-ai/docs/quotas)

<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/microsoft-foundry | lastmod: 2026-10-14 | section: Administration / Deployment -->
> 來源：https://code.claude.com/docs/zh-TW/microsoft-foundry（官方 zh-TW，lastmod 2026-10-14）｜分類：Administration › Deployment｜EN 摘要：Learn about configuring Claude Code through Microsoft Foundry, including setup, configuration, and troubleshooting.

# Microsoft Foundry 上的 Claude Code

> 了解如何透過 Microsoft Foundry 配置 Claude Code，包括設定、配置和故障排除。

**Deploying Claude Code across your organization?** Talk to sales about enterprise plans, SSO, and centralized billing.

View plans
Contact sales

## 先決條件

在使用 Microsoft Foundry 配置 Claude Code 之前，請確保您具有：

* 具有 Microsoft Foundry 存取權限的 Azure 訂閱
* 建立 Microsoft Foundry 資源和部署的 RBAC 權限
* 已安裝並配置 Azure CLI（選用 - 僅在您沒有其他取得認證機制時才需要）

> [!NOTE]
>
> 如果您要將 Claude Code 部署給多個使用者，請[固定您的模型版本](#4-pin-model-versions)以防止在 Anthropic 發佈新模型時發生中斷。

## 設定

### 佈建 Microsoft Foundry 資源

首先，在 Azure 中建立 Claude 資源：

1. 瀏覽至 [Microsoft Foundry 入口網站](https://ai.azure.com/)
2. 建立新資源，並記下您的資源名稱
3. 為 Claude 模型建立部署，並記下您為每個部署指定的部署名稱；您將在步驟 4 中將這些名稱設定為模型變數：

   * Claude Opus
   * Claude Sonnet
   * Claude Haiku

   當您設定部署時，您也會選擇其[託管選項](https://platform.claude.com/docs/en/build-with-claude/claude-in-microsoft-foundry#hosting-options)，這決定推論是在 Azure 上執行還是在 Anthropic 基礎設施上執行。

### 設定 Azure 憑證

Claude Code 支援 Microsoft Foundry 的三種驗證方法。選擇最適合您安全性要求的方法：

* [API 金鑰](#use-an-api-key)：您從 Microsoft Foundry 入口網站複製金鑰，並將其設定為 `ANTHROPIC_FOUNDRY_API_KEY`
* [Microsoft Entra ID](#use-microsoft-entra-id)：Claude Code 透過 Azure SDK 預設憑證鏈取得 token，例如從 `az login` 工作階段取得，因此不需要儲存 API 金鑰
* [Bearer 權杖](#use-a-bearer-token)：由另一個程序取得 Microsoft Entra ID 存取權杖，您再透過 `ANTHROPIC_FOUNDRY_AUTH_TOKEN` 傳入

> [!NOTE]
>
> 使用 Microsoft Foundry 時，`/logout` 命令無法使用，因為身分驗證是透過 Azure 憑證處理的。

#### 使用 API 金鑰

從 Microsoft Foundry 入口網站複製金鑰，然後將其設定為環境變數：

1. 在 Microsoft Foundry 入口網站中瀏覽至您的資源
2. 開啟 **端點和金鑰** 部分
3. 複製 **API 金鑰**
4. 設定環境變數，將 `your-azure-api-key` 替換為您複製的金鑰：

```bash theme={null}
export ANTHROPIC_FOUNDRY_API_KEY=your-azure-api-key
```

#### 使用 Microsoft Entra ID

請勿設定 `ANTHROPIC_FOUNDRY_API_KEY` 和 `ANTHROPIC_FOUNDRY_AUTH_TOKEN`。Claude Code 接著會使用 Azure SDK [預設憑證鏈](https://learn.microsoft.com/en-us/azure/developer/javascript/sdk/authentication/credential-chains#defaultazurecredential-overview)。
這支援多種方法來驗證本機和遠端工作負載。

在本機上，使用 Azure CLI 登入：

```bash theme={null}
az login
```

如需您的身分所需的角色，請參閱 [Azure RBAC 設定](#azure-rbac-configuration)。

#### 使用 Bearer 權杖

Claude Code 在每個請求上將 `ANTHROPIC_FOUNDRY_AUTH_TOKEN` 的值作為 `Authorization: Bearer` 標頭傳送。當另一個程序（例如主應用程式或登入指令碼）已為您取得存取權杖時，請使用此選項。

將變數設定為 Microsoft Entra ID 為您的資源簽發的 Bearer 權杖：

```bash theme={null}
export ANTHROPIC_FOUNDRY_AUTH_TOKEN=your-entra-access-token
```

`ANTHROPIC_FOUNDRY_AUTH_TOKEN` 優先於 `ANTHROPIC_FOUNDRY_API_KEY` 和預設憑證鏈。

### 設定 Claude Code

設定下列環境變數以啟用 Microsoft Foundry：

```bash theme={null}
# 啟用 Microsoft Foundry 整合
export CLAUDE_CODE_USE_FOUNDRY=1

# Azure 資源名稱（將 {resource} 替換為您的資源名稱）
export ANTHROPIC_FOUNDRY_RESOURCE={resource}
# 或提供完整的基礎 URL：
# export ANTHROPIC_FOUNDRY_BASE_URL=https://{resource}.services.ai.azure.com/anthropic
```

將 `ANTHROPIC_FOUNDRY_RESOURCE` 僅設定為資源名稱，例如 `my-resource`。在您傳送訊息時，Claude Code 會[拒絕 URL 或主機名稱](https://code.claude.com/docs/zh-TW/errors.md#anthropic-foundry-resource-must-be-a-foundry-resource-name)。

### 固定模型版本

> [!WARNING]
>
> 為每個部署固定特定的模型版本。如果不固定版本，模型別名（例如 `sonnet` 和 `opus`）會解析為 Claude Code 針對 Microsoft Foundry 的內建預設值，這可能會落後最新版本，且可能尚未在您的帳戶中提供。Microsoft Foundry 沒有啟動模型檢查，因此當預設值無法使用時，請求會失敗。建立 Azure 部署時，請選擇特定的模型版本，而不是「自動更新至最新版本」。

設定模型變數以符合您在步驟 1 中建立的部署名稱。

如果沒有 `ANTHROPIC_DEFAULT_OPUS_MODEL`，Microsoft Foundry 上的 `opus` 別名會解析為 Opus 4.6。將其設定為較新 Opus 模型的 ID，例如 Opus 4.8：

```bash theme={null}
export ANTHROPIC_DEFAULT_OPUS_MODEL='claude-opus-4-8'
export ANTHROPIC_DEFAULT_SONNET_MODEL='claude-sonnet-5'
export ANTHROPIC_DEFAULT_HAIKU_MODEL='claude-haiku-4-5'
```

背景任務（例如工作階段標題生成）使用小型/快速模型，通常是 Haiku 級別的模型。在 Microsoft Foundry 上，Claude Code 預設使用主要模型，因為並非每個帳戶都有 Haiku 部署。若要為背景任務使用 Haiku，請將 `ANTHROPIC_DEFAULT_HAIKU_MODEL` 設定為您帳戶中可用的 Haiku 部署，如上所示。

如需目前和舊版模型 ID，請參閱[模型概覽](https://platform.claude.com/docs/en/about-claude/models/overview)。如需完整的環境變數清單，請參閱[模型設定](https://code.claude.com/docs/zh-TW/model-config.md#pin-models-for-third-party-deployments)。

[提示快取](https://code.claude.com/docs/zh-TW/prompt-caching.md)會自動啟用。若要請求 1 小時的快取 TTL 而不是 5 分鐘的預設值，請設定下列變數；具有 1 小時 TTL 的快取寫入會以更高的費率計費：

```bash theme={null}
export ENABLE_PROMPT_CACHING_1H=1
```

若要為您的主要對話和 Claude Code 在其外部進行的請求設定不同的 TTL，請[自行選擇 TTL](https://code.claude.com/docs/zh-TW/prompt-caching.md#choose-the-ttl-yourself)。

### 執行 Claude Code

設定環境變數後，從您的專案目錄啟動 Claude Code：

```bash theme={null}
claude
```

Claude Code 從環境中讀取 `CLAUDE_CODE_USE_FOUNDRY` 和其他 Microsoft Foundry 變數，並在第一個提示詞時連接到您的 Azure 資源。與 Amazon Bedrock 和 Google Cloud 的 Agent Platform 不同，Microsoft Foundry 沒有互動式設定精靈，因此步驟 3 和 4 中的環境變數是唯一的設定路徑。

若要驗證您的設定，請在 Claude Code 中執行 `/status`。API 提供者行會顯示 `Microsoft Foundry`，以及您設定的資源名稱或基礎 URL。

## Azure RBAC 配置

`Azure AI User` 和 `Cognitive Services User` 預設角色包含叫用 Claude 模型所需的所有權限。

如需更嚴格的權限，請建立具有以下內容的自訂角色：

```json theme={null}
{
  "permissions": [
    {
      "dataActions": [
        "Microsoft.CognitiveServices/accounts/providers/*"
      ]
    }
  ]
}
```

如需詳細資訊，請參閱 [Microsoft Foundry RBAC 文件](https://learn.microsoft.com/en-us/azure/ai-foundry/concepts/rbac-azure-ai-foundry)。

## 1M token 上下文視窗

在 Microsoft Foundry 上，當 Claude Code 能夠判斷您的部署所提供的模型時，Fable 模型、Sonnet 5 及更新版本，以及 Opus 4.7 及更新版本預設會以 [1M token 上下文視窗](https://platform.claude.com/docs/en/build-with-claude/context-windows#context-window-sizes-by-model)執行，無需加上 `[1m]` 後綴。Claude Code 會從模型變數中的部署名稱讀取模型。請以模型 ID 為每個部署命名，例如 `claude-opus-4-8`，或使用 [`modelOverrides`](https://code.claude.com/docs/zh-TW/model-config#override-model-ids-per-version) 將模型對應到您的部署名稱。對於無法對應到任何模型的部署名稱，Claude Code 會假設為 200K 視窗，除非您[宣告不同的視窗大小](https://code.claude.com/docs/zh-TW/model-config.md#correct-the-window-for-a-gateway-or-custom-model-id)。

以下 `settings.json` 項目會告知 Claude Code，名為 `team-opus-prod` 的部署提供的是 Opus 4.8：

```json theme={null}
{
  "modelOverrides": {
    "claude-opus-4-8": "team-opus-prod"
  }
}
```

若要改為保留 200K 視窗，請設定 [`CLAUDE_CODE_DISABLE_1M_CONTEXT=1`](https://code.claude.com/docs/zh-TW/model-config#turn-off-1m-context)。

當您在 `ANTHROPIC_DEFAULT_OPUS_MODEL` 或 `ANTHROPIC_DEFAULT_SONNET_MODEL` 中的部署名稱後方加上 `[1m]` 時，Opus 4.6 與 Sonnet 4.6 即可使用 1M 視窗，詳見[為第三方部署固定模型](https://code.claude.com/docs/zh-TW/model-config.md#pin-models-for-third-party-deployments)的說明。在 v2.1.287 之前，Fable 模型以及 Opus 4.7 及更新版本在 Microsoft Foundry 上同樣需要該後綴，若未加上則預設以 200K 視窗執行。

## 故障排除

如果您收到錯誤「Failed to get token from azureADTokenProvider: ChainedTokenCredential authentication failed」：

* 在環境中配置 Entra ID，或設定 `ANTHROPIC_FOUNDRY_API_KEY`。

如果請求在第一個提示上重複出現連線錯誤而失敗：

* 檢查 `ANTHROPIC_FOUNDRY_RESOURCE` 是否設定為您的實際資源名稱，而不是預留位置。Claude Code 從此值建立端點 URL，因此不正確的名稱會指向不存在的主機。

## 其他資源

* [Microsoft Foundry 文件](https://learn.microsoft.com/en-us/azure/ai-foundry/what-is-azure-ai-foundry)
* [Microsoft Foundry 模型](https://ai.azure.com/explore/models)
* [Microsoft Foundry 定價](https://azure.microsoft.com/en-us/pricing/details/ai-foundry/)

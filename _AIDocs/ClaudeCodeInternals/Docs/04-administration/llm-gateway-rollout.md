<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/llm-gateway-rollout | lastmod: 2026-11-02 | section: Administration / Gateways -->
> 來源：https://code.claude.com/docs/zh-TW/llm-gateway-rollout（官方 zh-TW，lastmod 2026-11-02）｜分類：Administration › Gateways｜EN 摘要：Deploy a gateway product for Claude Code: configure it to forward what Claude Code sends, issue developer credentials, distribute the configuration through managed settings, and verify the rollout.

# 為您的組織推出 LLM 閘道

> 為 Claude Code 部署閘道產品：配置它以轉發 Claude Code 發送的內容、發放開發者認證、透過受管設定分發配置，並驗證推出。

本頁面引導管理員為 Claude Code 推出 LLM 閘道。它假設您已部署符合[閘道要求](#gateway-requirements)的閘道產品。本頁面不涵蓋部署或操作任何特定產品；請按照您的供應商文件部署您的產品。

> [!NOTE]
>
> * 若要將您自己機器上的 Claude Code 連接到現有閘道，請參閱[將 Claude Code 連接到 LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway-connect.md)
> * 若要了解 Claude Code 發送到閘道的內容以及要轉發的內容，請參閱[閘道相容性指南](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md)

## 先決條件

若要完成推出，您需要：

* 在您的基礎設施上部署的閘道，在您將分發給開發者的確切位址上提供 HTTPS，而不是重定向到它的位址，並配置為將 Claude 模型名稱路由到您的提供者
* 閘道轉發的提供者認證：
  * 對於 Anthropic API：來自 [Claude 控制台](https://platform.claude.com/settings/keys)的 API 金鑰
  * 對於雲端提供者：具有模型存取權限的雲端認證。請參閱 [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#prerequisites)、[Google Cloud 的 Agent Platform](https://code.claude.com/docs/zh-TW/google-vertex-ai.md#prerequisites) 或 [Microsoft Foundry](https://code.claude.com/docs/zh-TW/microsoft-foundry.md#prerequisites) 頁面上的先決條件
* 一種將設定檔案傳遞到開發者機器的方式，例如 MDM 或配置管理
  * 如果您還沒有，[設定如何到達裝置](https://code.claude.com/docs/zh-TW/admin-setup.md#decide-how-settings-reach-devices)會比較各選項

### 閘道要求

無論哪個產品提供閘道，它必須：

* **接受支援的 API 格式**：[API 格式表](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md#api-formats)中的格式之一。下面的推出步驟假設 Anthropic Messages API 位於 `POST /v1/messages`，大多數閘道都提供此格式
* **串流回應**：按到達時傳遞伺服器發送的事件，包括保活 ping，而不是緩衝整個回應；[串流](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md#streaming)涵蓋了什麼緩衝或剝離的 ping 會破壞
* **路由 Claude 模型名稱**：將開發者使用的每個名稱對應到上游模型。Claude Code 在每個請求中發送模型名稱，例如 `claude-sonnet-4-6`；在大多數閘道產品中，對應是閘道自己配置中的模型清單或路由表
* **轉發標頭和正文不變**：在兩個方向上傳遞 `anthropic-beta`、`anthropic-version` 和請求正文；[功能傳遞表](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md#feature-pass-through)將每個對應到沒有它就會中斷的功能
* **返回未修改的上游錯誤**：Claude Code 的自動恢復與錯誤措辭相符，因此在閘道自己的信封中包裝錯誤會破壞它，除非信封的訊息包含 [Claude 應用程式閘道為雲端提供者的錯誤措辭替換](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#upstream-error-messages)的 `capability_rejected:` 權杖之一
* **豁免路徑免受請求正文 WAF 檢查**：Claude Code 提示包含原始程式碼和 XML 樣式標籤，與跨網站指令碼正文規則相符；閘道前面的 WAF 在真實工作階段上返回 `403`，而短測試請求通過

可選地，提供 `GET /v1/models` 以便 Claude Code 可以使用[模型發現](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md#model-discovery)從您的閘道填充模型選擇器。

## 推出步驟

推出分為五個步驟，每個步驟都有一個檢查點：

1. [確認閘道路由您的模型](#confirm-the-gateway-routes-your-models)
2. [為每個開發者發放認證](#issue-developer-credentials)
3. [針對閘道測試 Claude Code](#test-claude-code-against-the-gateway)
4. [分發基本 URL 和認證](#distribute-the-configuration)
5. [從開發者機器驗證](#verify-the-rollout)

這些步驟涉及三個不同的認證，檢查點使用佔位符命名它們，以便您可以在出現問題時判斷哪一個有問題：

| 認證 | 誰持有它 | 檢查點中的佔位符 |
| :- | :- | :- |
| 提供者認證 | 閘道，它將其轉發給上游提供者 | 在閘道上配置；從不出現在用戶端命令中 |
| 閘道管理認證 | 您，如果您的閘道產品為其管理或測試介面發放一個 | `<gateway-key>` |
| 開發者金鑰 | 每個開發者，由閘道在[發放開發者認證](#issue-developer-credentials)中發放 | `<developer-key>` |

### 確認閘道路由您的模型

您的閘道應該已經配置了您的提供者認證，在其基本 URL 上監聽，並將請求轉發到您的提供者的 API。使用最小請求測試路徑是否端到端工作，替換您的部署中的兩個值：

* `<gateway-key>` 是任何讓您現在呼叫閘道的認證：管理金鑰、測試金鑰或您自己的開發者金鑰（如果您已經發放了一個）。並非每個閘道產品都有單獨的管理認證；如果您的沒有，請先在[發放開發者認證](#issue-developer-credentials)中為自己發放開發者金鑰
* `model` 是您的閘道配置為路由的 Claude 模型名稱。範例使用 `claude-sonnet-4-6`；替換為您配置的名稱

> [tab] Bash 或 Zsh
>
> ```bash theme={null}
> curl -X POST "https://llm-gateway.example.com/v1/messages" \
>   -H "Authorization: Bearer <gateway-key>" \
>   -H "anthropic-version: 2023-06-01" \
>   -H "content-type: application/json" \
>   -d '{"model": "claude-sonnet-4-6", "max_tokens": 1, "messages": [{"role": "user", "content": "."}]}'
> ```

> [tab] PowerShell
>
> ```powershell theme={null}
> Invoke-RestMethod -Method Post -Uri "https://llm-gateway.example.com/v1/messages" `
>   -Headers @{ "Authorization" = "Bearer <gateway-key>"; "anthropic-version" = "2023-06-01" } `
>   -ContentType "application/json" `
>   -Body '{"model": "claude-sonnet-4-6", "max_tokens": 1, "messages": [{"role": "user", "content": "."}]}'
> ```

**檢查點**：帶有 `content` 欄位的 `200` 表示閘道以該模型名稱到達提供者。`404` 表示該名稱未在閘道上路由；來自提供者的 `401` 表示閘道的提供者認證有誤。

針對您的閘道路由配置中的每個 Claude 模型名稱重複請求一次。閘道未路由的名稱會向選擇它的任何開發者返回 `404`，因此在推出前測試每個名稱。

> [!NOTE]
>
> 避免在重定向後提供閘道。重定向可能會在推理請求上丟棄請求正文或去除認證標頭，[模型發現](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md#model-discovery)將任何重定向視為失敗，因此認證無法洩露到重定向目標。

### 發放開發者認證

每個開發者需要自己的閘道金鑰進行身份驗證。按照您的產品的認證管理文件，在閘道上為每個開發者建立認證。

使用與[確認閘道路由您的模型](#confirm-the-gateway-routes-your-models)相同的請求確認新發放的金鑰對閘道有效，將 `<gateway-key>` 替換為新的 `<developer-key>`：

> [tab] Bash 或 Zsh
>
> ```bash theme={null}
> curl -X POST "https://llm-gateway.example.com/v1/messages" \
>   -H "Authorization: Bearer <developer-key>" \
>   -H "anthropic-version: 2023-06-01" \
>   -H "content-type: application/json" \
>   -d '{"model": "claude-sonnet-4-6", "max_tokens": 1, "messages": [{"role": "user", "content": "."}]}'
> ```

> [tab] PowerShell
>
> ```powershell theme={null}
> Invoke-RestMethod -Method Post -Uri "https://llm-gateway.example.com/v1/messages" `
>   -Headers @{ "Authorization" = "Bearer <developer-key>"; "anthropic-version" = "2023-06-01" } `
>   -ContentType "application/json" `
>   -Body '{"model": "claude-sonnet-4-6", "max_tokens": 1, "messages": [{"role": "user", "content": "."}]}'
> ```

**檢查點**：帶有 `content` 欄位的 `200` 表示開發者金鑰到達閘道，閘道轉發它。當[前一步](#confirm-the-gateway-routes-your-models)成功時，此處的 `401` 表示開發者金鑰有誤或尚未在閘道上生效。

為每個開發者發放一個金鑰而不是共用金鑰是使每個開發者的使用歸因和個別離職工作的原因。持有金鑰的環境變數取決於閘道讀取的標頭。對於在 `Authorization: Bearer` 標頭中檢查認證的閘道，開發者在 `ANTHROPIC_AUTH_TOKEN` 中設定他們的金鑰。對於從 `x-api-key` 標頭讀取金鑰的閘道，開發者改為設定 `ANTHROPIC_API_KEY`；[認證表](https://code.claude.com/docs/zh-TW/llm-gateway-connect.md#set-the-credential-variable)涵蓋對應。

### 針對閘道測試 Claude Code

在分發任何內容之前，使用推出將交付的相同配置自己透過閘道執行 Claude Code。直接在終端中輸入這些，而不是在 `.env` 或設定檔案中；它們僅在此終端工作階段中持續，因此關閉它會將您的機器返回到其正常配置。如果您的閘道讀取 `x-api-key` 標頭，請使用 `ANTHROPIC_API_KEY` 而不是 `ANTHROPIC_AUTH_TOKEN`：

> [tab] Bash 或 Zsh
>
> ```bash theme={null}
> export ANTHROPIC_BASE_URL=https://llm-gateway.example.com
> export ANTHROPIC_AUTH_TOKEN="<developer-key>"
> ```

> [tab] PowerShell
>
> ```powershell theme={null}
> $env:ANTHROPIC_BASE_URL = "https://llm-gateway.example.com"
> $env:ANTHROPIC_AUTH_TOKEN = "<developer-key>"
> ```

然後透過閘道發送一次性提示：

```bash theme={null}
claude -p "Reply with one word: connected"
```

**檢查點**：提示返回回應，請求出現在閘道的日誌中，作為對 `/v1/messages` 路徑的 `POST`，狀態為 `200`。Claude Code 附加查詢字串，例如 `?beta=true`，因此匹配路徑，而不是完整 URL。兩個失敗訊息指向不同的方向：

* `Not logged in`：檢查閘道日誌以區分兩個原因。如果它是空的，沒有認證到達工作階段，沒有請求離開機器；在您測試的殼層中重新執行匯出。如果它顯示被拒絕的請求，在 `401` 正文中有 `x-api-key`，閘道期望金鑰在該標頭中；改為切換到 `ANTHROPIC_API_KEY`
* `Failed to authenticate. API Error: 401` 表示認證已發送並被拒絕，閘道日誌說明位置：命名 `api.anthropic.com` 或您的提供者端點的 `401` 表示閘道到達上游但其提供者認證被拒絕，因此開發者金鑰有效，閘道持有的提供者認證有誤或是佔位符

錯誤或無法到達的基本 URL 會產生不同的症狀：Claude Code [以退避方式重試連接](https://code.claude.com/docs/zh-TW/errors.md#automatic-retries)，在報告錯誤之前可能會坐著沒有輸出幾分鐘。如果命令似乎掛起，請檢查閘道日誌而不是等待；沒有到達的請求表示 `ANTHROPIC_BASE_URL` 未指向閘道。

### 分發配置

每個開發者機器都需要閘道位址和認證。您可以透過[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)集中分發它們，因此開發者無需配置任何內容，或者將值交給開發者自己設定。

#### 要分發的內容

無論您選擇哪條路徑，相同的變數集都適用。大多數推出只需要 `ANTHROPIC_BASE_URL` 和認證；當您的閘道設定需要時，包括條件列。

| 變數或設定 | 它的作用 | 包括時機 |
| :- | :- | :- |
| `ANTHROPIC_BASE_URL` | 將 Claude Code 的 API 請求發送到閘道，而不是 `api.anthropic.com` | 總是 |
| `apiKeyHelper`，或 `ANTHROPIC_AUTH_TOKEN` 或 `ANTHROPIC_API_KEY` 中的認證 | 驗證對閘道的每個請求。幫助程式執行命令以擷取金鑰；變數持有靜態金鑰，分別作為 `Authorization: Bearer` 和 `x-api-key` 發送 | 總是；三者之一 |
| `ANTHROPIC_CUSTOM_HEADERS` | 將額外的 HTTP 標頭新增到每個 API 請求 | 您的閘道在每個請求上需要租戶或路由標頭 |
| `CLAUDE_CODE_GATEWAY_HINT_HEADERS` | 發送[閘道提示標頭](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md#gateway-hint-headers)，它們為閘道的路由和排程決策分類每個請求。需要 Claude Code v2.1.273 或更新版本 | 您的閘道讀取提示標頭 |
| `CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY` | 在啟動時查詢閘道的 `/v1/models` 並將返回的名稱新增到 `/model` 選擇器 | 您的閘道提供 `/v1/models` 並且您希望開發者的選擇器從中填充 |
| `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS` | 停止 Claude Code 發送預發行功能標頭和正文欄位。[停用預發行功能](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md#disable-pre-release-capabilities)涵蓋確切的範圍 | 您的閘道轉發到拒絕測試版欄位的 Amazon Bedrock 或 Google Cloud 的 Agent Platform 上游。請參閱[閘道要求](#gateway-requirements) |
| `CLAUDE_CODE_SKIP_FAST_MODE_NETWORK_ERRORS` 或 `CLAUDE_CODE_SKIP_FAST_MODE_ORG_CHECK` | 當其可用性檢查（直接呼叫 `api.anthropic.com` 而不是遵循 `ANTHROPIC_BASE_URL`）失敗、被攔截或因缺少 Anthropic 認證而被跳過時，恢復[快速模式](https://code.claude.com/docs/zh-TW/fast-mode.md) | 您的組織使用快速模式，開發者僅使用 `ANTHROPIC_AUTH_TOKEN` 進行身份驗證，在 `ANTHROPIC_API_KEY` 中有閘道發放的金鑰或來自 `apiKeyHelper`，或您的網路阻止或攔截對 `api.anthropic.com` 的直接請求；[在代理和 LLM 閘道後面使用快速模式](https://code.claude.com/docs/zh-TW/fast-mode.md#use-fast-mode-behind-proxies-and-llm-gateways)涵蓋哪個變數符合您的配置 |
| `ANTHROPIC_MODEL` 或 [`ANTHROPIC_DEFAULT_HAIKU_MODEL`](https://code.claude.com/docs/zh-TW/model-config) | 設定 Claude Code 為主工作階段和背景流量請求的模型名稱 | 您的閘道路由與 Claude Code 預設值不符的模型名稱，或您將[背景功能](https://code.claude.com/docs/zh-TW/model-config.md#environment-variables)路由到不同的模型。請同時路由覆寫名稱，以及 Claude Code 在未設定覆寫時請求的內建模型 ID，因為某些背景子呼叫無論覆寫如何都會請求內建 ID |
| `ANTHROPIC_BEDROCK_BASE_URL`、`ANTHROPIC_VERTEX_BASE_URL`、`ANTHROPIC_FOUNDRY_BASE_URL` 或 `ANTHROPIC_AWS_BASE_URL` 以及[該提供者的變數](https://code.claude.com/docs/zh-TW/llm-gateway-connect.md#route-to-a-cloud-provider-through-a-gateway) | 透過提供者特定的基本 URL 將 Claude Code 指向閘道。Amazon Bedrock 和 Google Cloud 的 Agent Platform 也切換到這些提供者的原生請求格式 | 您的閘道前置 Amazon Bedrock、Google Cloud 的 Agent Platform、Microsoft Foundry 或 AWS 上的 Claude 平台；請參閱 [API 格式](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md#api-formats) |

#### 透過受管設定分發

透過由 MDM、登錄原則或配置管理推送的[受管設定檔案](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)的 `env` 區塊傳遞變數：

```json theme={null}
{
  "env": {
    "ANTHROPIC_BASE_URL": "https://llm-gateway.example.com"
  },
  "apiKeyHelper": "/usr/local/bin/get-gateway-key"
}
```

將表中的條件變數新增到相同的 `env` 區塊。受管 `ANTHROPIC_BASE_URL` 被強制執行，無法被開發者的殼層匯出覆蓋，因為 Claude Code 在程序環境和較低優先順序設定上應用它。

不要在受管設定中包括 `forceLoginMethod`、`forceLoginOrgUUID` 或 `forceLoginGatewayUrl` 以及閘道認證。`forceLoginMethod` 或 `forceLoginOrgUUID`，任一金鑰在啟動時阻止 `ANTHROPIC_API_KEY`、`ANTHROPIC_AUTH_TOKEN` 和 `apiKeyHelper`，開發者無法繼續。他們看到 `This machine's managed settings require a first-party login`，或當檔案將 `forceLoginMethod` 設定為 `"gateway"` 或設定 `forceLoginGatewayUrl` 時看到 [`Administrator policy requires a Cloud gateway sign-in`](https://code.claude.com/docs/zh-TW/errors#administrator-policy-requires-a-cloud-gateway-sign-in)。

[伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md#platform-availability)傳遞需要直接連接到 `api.anthropic.com`，因此無法到達閘道路由的工作階段。閘道部署使用此檔案型受管設定路徑，它強制執行相同的金鑰。

對於認證，在受管設定檔案中分發一個 [`apiKeyHelper`](https://code.claude.com/docs/zh-TW/llm-gateway-connect#rotate-credentials-with-apikeyhelper) 命令，如上所示；該命令作為本地開發者驗證到您的秘密存放區，因此每個機器接收自己的金鑰。或者，透過您現有的秘密程序向每個開發者傳遞他們的金鑰，並讓他們自己設定 `ANTHROPIC_AUTH_TOKEN`。

某些環境需要單獨的傳遞：

* 桌面應用程式從其第三方推理配置讀取閘道路由，而不是從受管設定；透過 MDM 部署該檔案以及受管設定，以便桌面工作階段也透過閘道路由。請參閱[桌面第三方配置文件](https://claude.com/docs/third-party/claude-desktop/configuration)和[桌面閘道文件](https://claude.com/docs/third-party/claude-desktop/gateway)
* CI 執行器需要在[執行器的環境](https://code.claude.com/docs/zh-TW/llm-gateway-connect.md#configure-each-surface)中設定 `ANTHROPIC_BASE_URL` 和認證
* 受管 Windows 機器上的 WSL 僅在 [`wslInheritsWindowsSettings`](https://code.claude.com/docs/zh-TW/settings-reference#wslinheritswindowssettings) 為 `true` 時讀取 Windows 受管設定

#### 閘道後方的 HIPAA 設定

透過閘道的工作階段不符合 HIPAA 設定的資格。[檢查開發者的登入與連線方式](https://code.claude.com/docs/zh-TW/hipaa-setup.md#check-how-developers-sign-in-and-connect)列出了哪些登入和連線方式符合資格。

若要在受管設定檔中限制這些工作階段的功能，請使用[將輸出路徑對應到受管控制項和事件](https://code.claude.com/docs/zh-TW/monitoring-usage.md#map-egress-paths-to-managed-controls-and-events)中的設定鍵。這些設定鍵不會使工作階段符合 HIPAA 設定的資格，也無法涵蓋該設定所變更的所有內容。例如：

* **雲端工作階段**：沒有任何受管設定鍵可以關閉它們。請參閱[管理主控台控制項](https://code.claude.com/docs/zh-TW/desktop.md#admin-console-controls)
* **子程序中的 Anthropic 憑證**：該設定會從 Claude Code 啟動的程序中[移除它們](https://code.claude.com/docs/zh-TW/hipaa-setup.md#anthropic-credentials-in-commands-hooks-and-mcp-servers)，而沒有任何設定鍵只執行這項動作

請勿使用 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` 取代這些設定鍵。它會關閉其中部分功能，但同時也會關閉自動更新程式，且仍會保留 WebFetch 開啟。

#### 將值交給開發者自己設定

如果您沒有受管設定分發，請向每個開發者發送他們需要的內容，以遵循[連接頁面](https://code.claude.com/docs/zh-TW/llm-gateway-connect.md#configure-claude-code-yourself)：

* 閘道 URL
* 他們的個人認證
* **將認證放在哪個變數中**：對於承載令牌閘道為 `ANTHROPIC_AUTH_TOKEN`，或對於 `x-api-key` 閘道為 `ANTHROPIC_API_KEY`。告訴開發者哪一個可以節省他們在[連接頁面](https://code.claude.com/docs/zh-TW/llm-gateway-connect.md#set-the-credential-variable)上描述的試錯
* [要分發的內容表](#what-to-distribute)中的任何條件變數，以及它們的值

[連接頁面](https://code.claude.com/docs/zh-TW/llm-gateway-connect.md#configure-claude-code-yourself)引導開發者設定每一個。

**檢查點**：在開發者機器上，`claude` 啟動工作階段而不顯示登入畫面，因為分發的認證滿足身份驗證。然後執行 `/status` 並開啟 **Status** 標籤：`Anthropic base URL` 行顯示閘道位址，對於受管分發，`Setting sources` 行包括受管設定。登入畫面或缺少 `Anthropic base URL` 行表示配置未到達機器。

### 驗證推出

從開發者機器（而不是閘道主機）確認一切正常，以便測試涵蓋開發者使用的網路路徑。發送串流請求，它一次檢查端點、串流傳遞和模型路由：

> [tab] Bash 或 Zsh
>
> ```bash theme={null}
> curl -N -X POST "https://llm-gateway.example.com/v1/messages" \
>   -H "Authorization: Bearer <developer-key>" \
>   -H "anthropic-version: 2023-06-01" \
>   -H "content-type: application/json" \
>   -d '{"model": "claude-sonnet-4-6", "max_tokens": 16, "stream": true, "messages": [{"role": "user", "content": "count to 3"}]}'
> ```

> [tab] PowerShell
>
> ```powershell theme={null}
> $body = '{"model": "claude-sonnet-4-6", "max_tokens": 16, "stream": true, "messages": [{"role": "user", "content": "count to 3"}]}'
> $body | curl.exe -N -X POST "https://llm-gateway.example.com/v1/messages" `
>   -H "Authorization: Bearer <developer-key>" `
>   -H "anthropic-version: 2023-06-01" `
>   -H "content-type: application/json" `
>   --data-binary '@-'
> ```

您應該看到 `data:` 行逐漸到達。整個回應在暫停後一次到達表示閘道正在緩衝，這會停滯 Claude Code；`404` 表示模型名稱未路由。針對每個模型名稱重複。

然後啟動 `claude` 並發送訊息。此步驟的每個症狀都有一個原因：

* 登入提示表示認證間隙。執行 `/status` 並開啟 **Status** 標籤：當 `Setting sources` 行不包括受管設定時，分發未到達機器；當它包括時，開發者認證未被傳遞，因此設定 `ANTHROPIC_AUTH_TOKEN` 或 `apiKeyHelper`
* `Failed to authenticate` 錯誤表示閘道拒絕請求；其日誌說明哪個認證失敗。閘道自己記錄的拒絕命名開發者金鑰，而來自 `api.anthropic.com` 或您的提供者端點的 `401` 表示閘道持有的提供者認證被拒絕
* 當閘道期望金鑰在 `x-api-key` 標頭中時，首次使用時的一次性核准提示是預期的，設定為 `ANTHROPIC_API_KEY`。使用 `ANTHROPIC_AUTH_TOKEN`，不會出現提示，變數會無聲地接管；先前保存的 claude.ai 登入對該工作階段無效

如果您的組織使用[快速模式](https://code.claude.com/docs/zh-TW/fast-mode.md)，請在此處也執行 `/fast`：可用性檢查直接呼叫 `api.anthropic.com` 而不是遵循閘道基本 URL，因此閘道路由的工作階段可以報告快速模式為不可用或已停用，即使推理有效。[在代理和 LLM 閘道後面使用快速模式](https://code.claude.com/docs/zh-TW/fast-mode.md#use-fast-mode-behind-proxies-and-llm-gateways)將每個訊息對應到恢復它的變數，與[配置的其餘部分](#distribute-the-configuration)一起分發。

最後，檢查閘道的日誌以查看您發送的訊息：認證識別開發者，[`x-claude-code-session-id` 標頭](https://code.claude.com/docs/zh-TW/llm-gateway-protocol#request-headers)按工作階段分組請求。如果功能因[故障排除症狀](https://code.claude.com/docs/zh-TW/llm-gateway-connect.md#troubleshoot-gateway-errors)而失敗，閘道正在去除標頭或重寫錯誤；請參閱上面的[閘道要求](#gateway-requirements)。

## 維護閘道

推出後，三種變更會隨著時間到達閘道。每一種都有一個症狀要注意和一個要採取的行動。

| 變更 | 當閘道未跟上時的症狀 | 行動 |
| :- | :- | :- |
| 新的 Claude Code 版本新增 `anthropic-beta` 值和請求正文欄位 | 開發者在更新 Claude Code 後報告 `400` 錯誤，命名新欄位；請參閱[功能傳遞](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md#feature-pass-through) | 逐字轉發 `anthropic-*` 標頭和請求正文，而不是允許清單；在新 Claude Code 版本到達開發者之前針對閘道測試它們，檢查[規劃 Claude Code 版本升級](#plan-claude-code-version-upgrades)中的區域 |
| 新的 Claude 模型變得可用 | 開發者選擇新模型名稱時得到 `404`；`/model` 選擇器未列出它 | 將模型名稱新增到閘道的路由設定，然後重新執行[路由檢查](#confirm-the-gateway-routes-your-models)。如果您分發 `ANTHROPIC_MODEL` 或預設模型變數，請更新受管設定 |
| 認證過期或需要輪換 | 所有開發者請求開始因來自上游的 `401` 而失敗 | 按照自己的時間表輪換閘道的提供者認證；開發者金鑰在閘道上輪換，[`apiKeyHelper`](https://code.claude.com/docs/zh-TW/llm-gateway-connect#rotate-credentials-with-apikeyhelper) 處理每個開發者的輪換，無需重新分發設定 |

在調整每個金鑰的速率限制時，考慮用戶端[重試暫時性失敗](https://code.claude.com/docs/zh-TW/errors.md#automatic-retries)，包括 `429` 回應，最多 10 次，帶有退避，尊重 `Retry-After`。將[相容性指南](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md)保持為每個 Claude Code 版本發送內容的參考。

### 規劃 Claude Code 版本升級

某些 Claude Code 行為內建於已安裝的版本中，而不是在您的閘道設定，因此將開發者移至新版本可以在閘道設定未變更的情況下改變整個部署的行為。若要控制何時發生這種情況，請使用 [`requiredMaximumVersion`](https://code.claude.com/docs/zh-TW/settings-reference#requiredmaximumversion) 將開發者釘選到已測試的版本，或如果您透過自己的通道分發 Claude Code，請使用 [`DISABLE_UPDATES`](https://code.claude.com/docs/zh-TW/setup#disable-auto-updates)。在您提高釘選之前，請閱讀新版本的[變更日誌](https://code.claude.com/docs/en/changelog.md)項目並[針對閘道測試它](#test-claude-code-against-the-gateway)。

當您測試版本時，閘道拒絕的新標頭或請求欄位會顯示為[維護閘道](#maintain-the-gateway)中描述的 `400` 錯誤。下表涵蓋不會產生錯誤的版本相依變更，以及保持每個變更在升級期間保持不變的設定。

| 區域 | 開發者升級時可能變更的內容 | 保持其不變的設定 |
| :- | :- | :- |
| 功能旗標預設值 | [不從 Anthropic 擷取功能旗標](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)的工作階段，例如雲端提供者上的工作階段或關閉遙測的工作階段，使用內建於已安裝版本中的旗標預設值。當版本變更其中一個預設值時，這些開發者的行為會在他們升級時立即變更 | 版本釘選本身，`requiredMaximumVersion` 或 `DISABLE_UPDATES` |
| 模型功能假設 | 已安裝版本無法識別的模型 ID，例如閘道別名 `prod-opus`，會根據[自適應推理](https://code.claude.com/docs/zh-TW/model-config.md#adaptive-reasoning-and-fixed-thinking-budgets)、努力參數和[內容視窗](https://code.claude.com/docs/zh-TW/model-config.md#correct-the-window-for-a-gateway-or-custom-model-id)的預設假設執行，直到更新版本識別該 ID 或您對其進行對應 | 在閘道路由 Anthropic 模型 ID，或新增 [`modelOverrides`](https://code.claude.com/docs/zh-TW/model-config#override-model-ids-per-version) 項目，將 Anthropic 模型 ID 對應到您的別名。在雲端提供者連線上，您可以改為[宣告釘選模型的功能](https://code.claude.com/docs/zh-TW/model-config.md#customize-pinned-model-display-and-capabilities) |
| 預設模型和別名 | 新工作階段預設啟動的模型，以及別名（例如 `opus` 和 `sonnet`）解析為的模型，[內建於每個版本](https://code.claude.com/docs/zh-TW/model-config.md#pin-models-for-third-party-deployments)中，開發者升級時可能變更 | [`ANTHROPIC_DEFAULT_MODEL`](https://code.claude.com/docs/zh-TW/model-config#set-a-default-model-for-new-sessions) 用於新工作階段啟動的模型，以及 [`ANTHROPIC_DEFAULT_*_MODEL` 變數](https://code.claude.com/docs/zh-TW/model-config#environment-variables)（例如 `ANTHROPIC_DEFAULT_OPUS_MODEL`）用於每個別名解析為的內容。`ANTHROPIC_DEFAULT_MODEL` 需要 Claude Code v2.1.236 或更新版本 |

## 相關資源

* [將 Claude Code 連接到 LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway-connect.md)：開發者面向的設定步驟，具有每個表面的配置和故障排除表，您可以交給開發者
* [閘道相容性指南](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md)：閘道操作員的參考資料，涵蓋端點、要轉發的標頭和功能傳遞表
* [Claude Code 使用的值](https://code.claude.com/docs/zh-TW/settings.md#which-value-claude-code-uses)：受管、專案和使用者設定如何組合
* [傳遞機制](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)：受管檔案在每個平台上的位置
* [為您的組織設定 Claude Code](https://code.claude.com/docs/zh-TW/admin-setup.md)：此閘道是其中一部分的更廣泛推出，包括原則強制執行、使用可見性和資料處理

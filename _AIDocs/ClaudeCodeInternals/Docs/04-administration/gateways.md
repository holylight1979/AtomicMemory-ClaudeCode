<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/gateways | lastmod: 2026-10-20 | section: Administration / Gateways -->
> 來源：https://code.claude.com/docs/zh-TW/gateways（官方 zh-TW，lastmod 2026-10-20）｜分類：Administration › Gateways｜EN 摘要：Route Claude Code through a self-hosted gateway for centralized credentials, usage tracking, and cost controls. Covers the architecture, Anthropic's Claude apps gateway, and using other gateway products.

# 透過閘道執行 Claude Code

> 透過自託管閘道路由 Claude Code，以實現集中式認證、使用情況追蹤和成本控制。涵蓋架構、Anthropic 的 Claude 應用程式閘道和使用其他閘道產品。

閘道是您的組織在 Claude Code 和模型提供者之間執行的代理。Claude Code 將 API 流量傳送到閘道，而不是直接傳送到提供者，閘道使用您的組織持有的認證轉發流量。開發人員向閘道進行身份驗證，而不是持有提供者認證，因此身份驗證、使用情況追蹤、預算和稽核日誌都在您控制的一個地方進行。

Claude Code 包含一個自託管閘道，[Claude 應用程式閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)，在 `claude` 二進位檔案中，因此您不必採用單獨的閘道產品來執行一個。如果您的組織已經執行 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)，Claude Code 也可以與之配合使用。

本頁涵蓋：

* [閘道如何位於 Claude Code 和您的提供者之間](#how-a-gateway-works)
* [在 Claude 應用程式閘道和您已經執行的閘道之間進行選擇](#choose-a-gateway)
* [閘道如何與 claude.ai 訂閱互動](#subscriptions-and-gateways)
* [與閘道分開配置的內容](#configure-separately-from-the-gateway)

## 閘道如何運作

每個開發人員的 Claude Code 都指向閘道的位址，並使用閘道簽發的認證進行身份驗證。

閘道對開發人員進行身份驗證，應用您配置的任何存取和預算規則，並使用組織的認證將請求轉發給您的提供者。提供者可以是 Anthropic 的 API 或 [雲端提供者](https://code.claude.com/docs/zh-TW/third-party-integrations.md)，例如 Amazon Bedrock、Google Cloud 的 Agent Platform 或 Microsoft Foundry；閘道的配置決定了這一點。使用 Claude 應用程式閘道或另一個公開單一 Anthropic 格式端點的閘道，更改提供者不需要觸及開發人員機器。

![顯示 Claude Code 透過閘道路由的圖表。在開發人員機器區域中，Claude Code CLI 和 VS Code 擴充功能使用每個開發人員的認證將請求傳送到閘道位址。在標記為您的基礎設施的區域中，閘道處理身份驗證、使用情況追蹤、預算和路由，並使用您的組織認證轉發請求。在模型提供者區域中，實線箭頭指向您配置的提供者（顯示為 Anthropic API），虛線箭頭指向其他提供者選項，以 Amazon Bedrock、Google Cloud 和 Microsoft Foundry 為例。](https://mintcdn.com/claude-code/-uq-4JE0W_JO5Er5/images/llm-gateway-flow.svg?fit=max\&auto=format\&n=-uq-4JE0W_JO5Er5\&q=85\&s=1c1a8dcc0cfcc3a58652cc8e28cd3e20)

涉及兩種認證：

* **開發人員認證**：每個開發人員持有自己的認證，由閘道簽發。它向閘道驗證他們的身份，並在使用情況追蹤中識別他們
* **提供者認證**：閘道為您的提供者帳戶持有一個認證，由所有轉發的流量共享

## 選擇閘道

Claude Code 可與 Anthropic 自己的閘道或您的組織已經執行的閘道配合使用。

### Claude 應用程式閘道

Claude 應用程式閘道是 Anthropic 的自託管閘道，包含在 `claude` 二進位檔案中。它路由到 Amazon Bedrock、Claude Platform on AWS、Google Cloud、Microsoft Foundry 或 Anthropic API 作為上游。開發人員透過 `/login` 使用您的公司身份提供者登入，閘道按 IdP 群組強制執行模型存取和 [受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)，並向您自己的可觀測性堆疊發出 [OpenTelemetry Protocol (OTLP)](https://code.claude.com/docs/zh-TW/monitoring-usage.md) 使用情況指標。

因為它與每個 Claude Code 版本一起構建和測試，所以它轉發 Claude Code 傳送的 `anthropic-beta` 值和請求欄位。單獨維護的閘道需要隨著這些值和欄位在每個版本中的變化而 [更新其轉發規則](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md#forward-as-open-lists)；Claude 應用程式閘道與 CLI 一起發佈，因此沒有清單需要保持最新。有關在閘道工作階段上行為不同的小功能集，請參閱 [可用性和限制](https://code.claude.com/docs/zh-TW/claude-apps-gateway#availability-and-limitations)。

閘道登入是瀏覽器 SSO 步驟，沒有服務令牌流，因此沒有開發人員批准登入的 CI 管道無法透過它進行身份驗證；直接針對您的提供者配置這些。Agent SDK 工作階段和在開發人員已登入的機器上執行的 `claude -p` 使用該機器的閘道工作階段，並受其原則管制。請參閱 [CI 管道和遠端機器](https://code.claude.com/docs/zh-TW/claude-apps-gateway#ci-pipelines-and-remote-machines)。

請參閱 [Claude 應用程式閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway) 以部署它。

### 其他閘道

如果您的組織已經執行 LLM 閘道或 API 閘道，您可以改用它。Anthropic 不認可、維護或審計其他閘道產品，也不支援透過任何閘道將 Claude Code 路由到非 Claude 模型。有關管理員推出檢查清單、閘道必須實現的內容以及如何將 Claude Code 指向它，請參閱 [其他 LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)。

## 訂閱和閘道

當開發人員透過具有閘道認證的閘道連接時，使用情況按 API 費率計費到您的組織提供者帳戶，他們的 claude.ai 訂閱不被使用或收費。為您執行的閘道設定 [`ANTHROPIC_AUTH_TOKEN`](https://code.claude.com/docs/zh-TW/env-vars)，或使用 `/login` 登入 Claude 應用程式閘道，會關閉該工作階段的訂閱登入。在該認證下轉發的每個請求都計費到閘道提供者認證背後的帳戶。

例外是僅設定 `ANTHROPIC_BASE_URL`，沒有閘道認證。請求仍然透過閘道路由，但已保存的 claude.ai 登入保持為活動認證，因此訂閱的使用限制和計費適用。[其他 LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway#subscriptions-and-gateways) 涵蓋該配置以及閘道必須轉發的內容才能使其正常運作。

## 與閘道分開配置

閘道路由模型 API 請求。您可能期望它處理的一些事情在其他地方配置：

* **哪個模型回答**：使用 `/model` 命令或 [模型環境變數](https://code.claude.com/docs/zh-TW/model-config.md#setting-your-model) 選擇模型。閘道決定請求的去向，而不是開發人員選擇的模型。Claude 應用程式閘道可以使用每個群組的 `availableModels` 允許清單限制選擇，但開發人員仍在其中進行選擇。
* **其他網路流量**：Claude Code 本身將版本檢查和下載直接傳送到 Anthropic，與閘道路徑分開。您的網路仍然需要對 [必需網域](https://code.claude.com/docs/zh-TW/network-config.md) 的出口，或設定 [`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`](https://code.claude.com/docs/zh-TW/env-vars) 以關閉可選流。
* **用戶端遙測**：當工作階段登入 Claude 應用程式閘道時，Claude Code 會停用其 Anthropic 繫結的用戶端分析。若要同時關閉登入前啟動分析，請在每個裝置上的 [用戶端側受管設定](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#client-side-managed-settings) 中傳遞 [`DISABLE_TELEMETRY`](https://code.claude.com/docs/zh-TW/managed-settings#turn-telemetry-off-for-your-organization)。
* **其他閘道上的用戶端遙測**：Claude Code 是否傳送可選用戶端遙測流取決於您的提供者，[遙測預設值表](https://code.claude.com/docs/zh-TW/data-usage.md#default-behaviors-by-api-provider) 涵蓋每種情況。
* **遙測目的地**：Claude Code 傳送閘道工作階段遙測的位置取決於工作階段如何登入，[開發人員上強制執行的項目](https://code.claude.com/docs/zh-TW/claude-apps-gateway#whats-enforced-on-developers) 說明每種工作階段的匯出位置。
* **公司 HTTP 代理**：`HTTPS_PROXY` 位於 Claude Code 和它與之通訊的每個伺服器之間，包括閘道。如果您的網路需要一個，[配置代理](https://code.claude.com/docs/zh-TW/network-config.md) 以及閘道。對於您託管的 Claude 應用程式閘道，[登入檢查代理主機也在私人網路上](https://code.claude.com/docs/zh-TW/claude-apps-gateway#prerequisites)；如果不是，將閘道主機新增到 `NO_PROXY`，以便 CLI 直接連接到它。

## 後續步驟

下一頁取決於誰執行閘道。Anthropic 的閘道從 `claude` 二進位檔案執行，有自己的設定指南；您的組織已經執行的閘道有要實現的協議和管理員推出檢查清單。

* [Claude 應用程式閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway) 以部署 Anthropic 的自託管閘道，具有 SSO 登入和 OTLP 遙測
* [其他 LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway) 用於您的組織已經執行的閘道必須實現的內容，以及如何將 Claude Code 指向它
* [為您的組織設定 Claude Code](https://code.claude.com/docs/zh-TW/admin-setup.md) 用於閘道是其中一部分的更廣泛推出決策

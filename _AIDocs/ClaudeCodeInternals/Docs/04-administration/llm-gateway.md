<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/llm-gateway | lastmod: 2026-10-01 | section: Administration / Gateways -->
> 來源：https://code.claude.com/docs/zh-TW/llm-gateway（官方 zh-TW，lastmod 2026-10-01）｜分類：Administration › Gateways｜EN 摘要：Route Claude Code through an LLM gateway your organization already runs. Covers connecting Claude Code to a gateway, rolling one out for your organization, and what Claude Code sends to a gateway.

# 其他 LLM 閘道

> 透過貴組織已執行的 LLM 閘道路由 Claude Code。涵蓋將 Claude Code 連接到閘道、為貴組織推出閘道，以及 Claude Code 傳送到閘道的內容。

本節涵蓋使用貴組織已執行的閘道產品，而非 [Claude 應用程式閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)。如需了解什麼是閘道、它如何位於 Claude Code 和您的提供者之間，以及如何在 Claude 應用程式閘道和其他產品之間進行選擇，請參閱 [閘道概述](https://code.claude.com/docs/zh-TW/gateways.md)。

> [!NOTE]
>
> * 如果您是連接到現有閘道的開發人員：[將 Claude Code 連接到您的閘道](https://code.claude.com/docs/zh-TW/llm-gateway-connect.md)
> * 如果您是為貴組織推出閘道的管理員：[部署和分發閘道](https://code.claude.com/docs/zh-TW/llm-gateway-rollout.md)
> * 如果您正在配置閘道產品：[閘道相容性指南](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md)

任何公開 [支援的 API 格式](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md#api-formats) 的閘道都可以運作。Anthropic 不認可、維護或審計第三方閘道產品，也不支援透過任何閘道將 Claude Code 路由到非 Claude 模型。按照其自身文件部署閘道，然後使用下方的 [推出步驟](#roll-out-a-gateway) 完成 Claude Code 端的設定。

## gateway 提供的功能

gateway 為您的組織提供一個地方來管理：

* **憑證**：提供商金鑰保留在伺服器端；開發人員改為持有 gateway 憑證
* **使用情況追蹤**：按開發人員或團隊歸屬使用情況，無論哪個提供商處理請求
* **成本控制**：在一個地方強制執行預算和速率限制
* **審計日誌**：記錄每個模型請求以進行合規性檢查
* **提供商切換**：在 gateway 配置中更改提供商，無需觸及開發人員機器

除了提供商切換外，所有這些都適用於上游是 Anthropic API 還是[雲提供商](https://code.claude.com/docs/zh-TW/third-party-integrations.md)。提供商切換而無需重新配置開發人員機器也取決於 gateway 公開單一 [Anthropic 格式端點](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md#api-formats)，無論上游如何；公開提供商自己格式的 gateway 將客戶端配置與該提供商綁定，並改變 [Claude Code 傳送的內容以及它應用的預設值](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md#how-the-connection-method-changes-client-behavior)。

權衡是 gateway 成為您的組織運營的基礎設施。Claude Code 在每個版本中添加功能，不轉發這些功能的 gateway 會破壞相應的功能，因此 gateway 產品需要隨著 Claude Code 的發展而保持更新。[gateway 相容性指南](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md)涵蓋要轉發的內容。

## 推出 gateway

當您準備好為組織推出 LLM gateway 時，無論您選擇哪個 gateway 產品，順序都是相同的：

1. 部署 gateway 並給予它您的提供商憑證，以便它可以對它轉發的請求進行身份驗證。
2. 為每個開發人員發行 gateway 憑證，以便使用情況歸屬於開發人員，離職時撤銷一個憑證。
3. 透過[受管設定檔](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)和您的機密工具分發配置，以便每台機器都接收基本 URL 和憑證。當兩者都分發時，開發人員無需配置任何內容。如果您沒有設定分發，開發人員按照[連接頁面](https://code.claude.com/docs/zh-TW/llm-gateway-connect.md)自己設置變數。
4. 讓每個開發人員[檢查 Claude Code 中的配置](https://code.claude.com/docs/zh-TW/llm-gateway-connect.md#check-for-an-existing-configuration)，以便分發問題在他們依賴 gateway 之前浮出水面。

[為您的組織推出 LLM gateway](https://code.claude.com/docs/zh-TW/llm-gateway-rollout.md)逐步介紹每個步驟，並顯示在每個步驟分發的配置檔案。gateway 是組織設置的一部分；有關政策強制執行、使用情況可見性和資料處理決策，請參閱[為您的組織設置 Claude Code](https://code.claude.com/docs/zh-TW/admin-setup.md)。

若要讓透過 `ANTHROPIC_BASE_URL` 到達的 gateway 成為受管機器唯一可以使用的目的地，請在相同的受管設定檔中將 [`allowedProviders`](https://code.claude.com/docs/zh-TW/settings-reference#allowedproviders) 設定為 `["customEndpoint"]`，並將 gateway 的 `ANTHROPIC_BASE_URL` 放在該檔案的 `env` 區塊中。Claude Code 隨後會拒絕指向其他任何地方的工作階段，包括直接指向 Anthropic 或開發人員自己的代理，並且只接受 `ANTHROPIC_BASE_URL` 具有您在該處設定的值。對於透過提供商特定端點變數（例如 `ANTHROPIC_BEDROCK_BASE_URL`）到達的 gateway，`allowedProviders` 項目會指定要固定的變數。需要 Claude Code v2.1.285 或更新版本。

## 訂閱和 gateway

當[gateway 憑證變數](https://code.claude.com/docs/zh-TW/llm-gateway-connect.md#set-the-credential-variable)或 `apiKeyHelper` 處於活動狀態時，請求會使用該憑證，而不是開發人員的 claude.ai 訂閱登錄，且訂閱的使用限制不適用於這些請求。Claude Code 在機器上保存了 claude.ai 登錄，但不會在這些請求中發送它。該流量按令牌計費給擁有 gateway 轉發的憑證的人，例如您的組織的 Anthropic Console 帳戶，或當 gateway 路由到那裡時您的 Amazon Bedrock、Google Cloud 的 Agent Platform 或 Microsoft Foundry 帳戶。

[`ANTHROPIC_BASE_URL`](https://code.claude.com/docs/zh-TW/llm-gateway-connect#set-the-base-url-and-credential)是指向 Claude Code 指向 gateway 的變數。僅設置該變數而不設置 gateway 憑證不會替換訂閱。請求仍然透過 gateway 路由，但保存的 claude.ai 登錄保持活動憑證，因此其使用限制和計費適用。將此流量轉發給 Anthropic 的 gateway 必須轉發 `anthropic-beta` 中的 OAuth 功能；請參閱[請求標頭參考](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md#request-headers)。

## 相關頁面

* [Gateway 概述](https://code.claude.com/docs/zh-TW/gateways.md)：gateway 如何運作以及如何在 Claude apps gateway 和其他產品之間進行選擇
* [Claude apps gateway](https://code.claude.com/docs/zh-TW/claude-apps-gateway)：Anthropic 的自託管 gateway，具有 SSO 登錄和 OTLP 遙測
* [將 Claude Code 連接到 LLM gateway](https://code.claude.com/docs/zh-TW/llm-gateway-connect.md)：在您自己的機器上設置基本 URL 和憑證，具有每個表面的配置和故障排除表
* [為您的組織推出 LLM gateway](https://code.claude.com/docs/zh-TW/llm-gateway-rollout.md)：部署 gateway、發行開發人員憑證和分發受管設定的管理員檢查清單
* [Gateway 相容性指南](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md)：Claude Code 發送到 gateway 的內容，供配置 gateway 的操作人員使用，涵蓋端點、要轉發的標頭和功能傳遞

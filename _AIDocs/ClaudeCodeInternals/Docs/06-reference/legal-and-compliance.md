<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/legal-and-compliance | lastmod: 2026-10-30 | section: Resources / Resources -->
> 來源：https://code.claude.com/docs/zh-TW/legal-and-compliance（官方 zh-TW，lastmod 2026-10-30）｜分類：Resources › Resources｜EN 摘要：Legal agreements, compliance certifications, and security information for Claude Code.

# 法律和合規

> Claude Code 的法律協議、合規認證和安全資訊。

## 法律協議

### 許可證

您對 Claude Code 的使用受以下條款約束：

* [商業條款](https://www.anthropic.com/legal/commercial-terms) - 適用於 Team、Enterprise 和 Claude API 使用者
* [消費者服務條款](https://www.anthropic.com/legal/consumer-terms) - 適用於 Free、Pro、Max 和 Ultra 使用者

### 商業協議

無論您是直接使用 Claude API（1P）還是通過 Amazon Bedrock 或 Google Cloud 的 Agent Platform（3P）存取，您現有的商業協議將適用於 Claude Code 使用，除非我們已相互同意另行安排。

### 客戶可以在他們的產品中提供 Claude Code 嗎？

除非我們已相互同意另行安排，否則在您的產品或服務中預先安裝或執行 Claude Code（例如在託管沙箱或其他代理基礎設施中）需要同意我們的[商業條款](https://www.anthropic.com/legal/commercial-terms)並遵守以下條件：

* **Claude Code 二進位檔案不得被修改。** Claude Code 必須按照 Anthropic 發佈的方式安裝和執行，客戶不得移除、停用或限制其中內建的任何身份驗證方法（包括允許使用 Claude 帳戶或使用者自己的 API 金鑰登入的方法）。
* **客戶不得代表其終端使用者支付、轉售或中介 Claude 使用。** 每個終端使用者必須使用自己的 Anthropic API 金鑰、Claude 訂閱方案認證或第三方推論提供者認證（Amazon Bedrock、Google Cloud 的 Agent Platform、Microsoft Foundry）進行身份驗證。該使用量將直接按照終端使用者與 Anthropic 的協議或對於第三方推論提供者，按照適用提供者的協議向終端使用者計費。

**使用 Claude Code 名稱和標誌。** 您可以準確地以純文字說明您的產品已預先安裝 Claude Code 或它執行 Claude Code。但您不能將 Claude Code 或 Anthropic 名稱或標誌用作您自己的產品、功能或公司名稱的一部分，在您自己的標誌中，或以暗示 Anthropic 建立、認可或與您的產品合作的方式使用。Anthropic 名稱或標誌的任何其他使用受我們的[商標指南](https://www.anthropic.com/legal/trademark-guidelines)管轄，需要我們的書面許可。

Claude Code 仍受 Anthropic 的標準條款管轄（請參閱上面的許可證和商業協議部分），無論透過哪個平台存取。

## 合規

### 醫療保健合規（BAA）

如果客戶已與 Anthropic 簽訂業務關聯協議（BAA），該 BAA 將依據貴組織可使用的選項，擴展至以下兩種設定下的 Claude Code：

* **HIPAA 設定**：搭配 Claude for Enterprise 帳戶使用的 Claude Code CLI 或 Claude Desktop 中的 Code 分頁。該組織必須已啟用 HIPAA，並已將 HIPAA 設定套用至 Claude Code（本機模式）與 Cowork（本機模式）。請參閱[為符合 HIPAA 要求的組織設定 Claude Code（本機模式）](https://code.claude.com/docs/zh-TW/hipaa-setup.md)。
* **零資料保留**：已為相關組織啟用[零資料保留（ZDR）](https://code.claude.com/docs/zh-TW/zero-data-retention.md)的 Claude Code。ZDR 並非適用於所有組織。

在 HIPAA 設定下，雲端工作階段、Remote Control、Claude 行動應用程式中的 Claude Code，以及透過第三方雲端供應商或閘道路由的 Claude Code 均不在涵蓋範圍內。請查閱[實施指南](https://trust.anthropic.com/resources?s=l1wrssd9hsbi4gak0tp5a6\&name=%5Banthropic%5D-hipaa-ready-offering-implementation-guide)以取得完整的合格服務清單。

## 使用政策

### 可接受的使用

Claude Code 的使用受 [Anthropic 使用政策](https://www.anthropic.com/legal/aup)約束。Pro、Max 和 Ultra 計劃的公告用量上限假設 Claude Code 和 Agent SDK 的普通個人使用。

### 身份驗證和認證使用

Claude Code 使用 OAuth 令牌或 API 金鑰向 Anthropic 的伺服器進行身份驗證。這些身份驗證方法有不同的用途：

* **OAuth 身分驗證**專門用於 Claude Free、Pro、Max、Ultra、Team 和 Enterprise 訂閱計劃的購買者，旨在支援 Claude Code 和其他原生 Anthropic 應用程式的普通使用。有關登入步驟，請參閱[登入您的 Claude 帳戶](https://support.claude.com/en/articles/13189465-logging-in-to-your-claude-account)；有關 Claude Code 如何執行 OAuth 身分驗證，請參閱[身分驗證](https://code.claude.com/docs/zh-TW/authentication.md)。
* **開發人員**構建與 Claude 功能互動的產品或服務，包括使用 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 的產品或服務，應通過 [Claude Console](https://platform.claude.com/) 或受支援的雲端提供商使用 API 金鑰身分驗證。Anthropic 不允許第三方開發人員提供 Claude.ai 登入到他們自己的應用程式，或代表其使用者通過 Free、Pro、Max 或 Ultra 計劃憑證路由請求。此外，開發人員不得收集、儲存或中介 Claude.ai 憑證或工作階段 token — 登入 Claude 帳戶必須通過 Anthropic 自己的流程完成。

這不會限制客戶如何配置和管理他們自己的 API 金鑰或第三方推論提供商認證 — 例如，在開發環境、機密管理器或機器映像中配置 API 金鑰供客戶自己的授權使用者使用 — 前提是所產生的使用根據金鑰擁有者與 Anthropic（或適用提供商）的協議計費，並且不會如上所述被轉售或中介。它也不會阻止終端使用者使用他們自己的 Claude 訂閱登入未修改的 Claude Code 二進位檔案，包括平台託管 Claude Code 的情況，如上面\*客戶可以在他們的產品中提供 Claude Code 嗎？\*所述。

Anthropic 保留採取措施執行這些限制的權利，並可能在不事先通知的情況下執行。

如果您對適用於您的使用案例的允許身份驗證方法有疑問，請[聯絡銷售](https://www.anthropic.com/contact-sales?utm_source=claude_code\&utm_medium=docs\&utm_content=legal_compliance_contact_sales)。

## 安全和信任

### 信任和安全

您可以在 [Anthropic 信任中心](https://trust.anthropic.com)和[透明度中心](https://www.anthropic.com/transparency)找到更多資訊。

### 安全漏洞報告

Anthropic 通過 HackerOne 管理我們的安全計劃。[使用此表單報告漏洞](https://hackerone.com/4f1f16ba-10d3-4d09-9ecc-c721aad90f24/embedded_submissions/new)。

***

© Anthropic PBC。版權所有。使用受適用的 Anthropic 服務條款約束。

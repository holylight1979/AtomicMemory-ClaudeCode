<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/zero-data-retention | lastmod: 2026-10-16 | section: Administration / Security and data -->
> 來源：https://code.claude.com/docs/zh-TW/zero-data-retention（官方 zh-TW，lastmod 2026-10-16）｜分類：Administration › Security and data｜EN 摘要：Learn about Zero Data Retention (ZDR) for Claude Code, available to qualified accounts on Claude for Enterprise, including scope, disabled features, and how to request enablement.

# 零資料保留

> 了解 Claude for Enterprise 合格帳戶可用的 Claude Code 零資料保留 (ZDR)，包括範圍、停用的功能，以及如何請求啟用。

Claude Code 的零資料保留 (ZDR) 適用於 Claude for Enterprise 上的合格帳戶。啟用 ZDR 後，Claude Code 工作階段期間產生的提示詞和模型回應會即時處理，在回應返回後不會由 Anthropic 儲存，除非需要遵守法律或防止濫用。

> [!NOTE]
>
> ZDR 不包含在標準 Claude for Enterprise 方案中，也無法從您的管理員設定中啟用。它適用於合格帳戶，需要由 Anthropic 進行單獨啟用。如果您的組織需要 ZDR，請[聯絡銷售](https://www.anthropic.com/contact-sales?utm_source=claude_code\&utm_medium=docs\&utm_content=zero_data_retention_request)或您的 Anthropic 帳戶團隊以確認資格。

已啟用 HIPAA 的 Claude for Enterprise 組織，在將 HIPAA 設定套用至 Claude Code（本機模式）和 Cowork（本機模式）後，即可在不使用 ZDR 的情況下，將 Claude Code CLI 和 Claude Desktop 中的 Code 分頁納入其商業夥伴協議 (BAA) 的涵蓋範圍。請參閱[為符合 HIPAA 要求的組織設定 Claude Code（本機模式）](https://code.claude.com/docs/zh-TW/hipaa-setup.md)。未採用 HIPAA 設定的組織仍需要 ZDR，才能讓 Claude Code 獲得 BAA 涵蓋。如需合格服務清單，請參閱[實施指南](https://trust.anthropic.com/resources?s=l1wrssd9hsbi4gak0tp5a6\&name=%5Banthropic%5D-hipaa-ready-offering-implementation-guide)。

Claude for Enterprise 上的 ZDR 為企業客戶提供了使用 Claude Code 並實現零資料保留的能力，以及存取管理功能：

* 每位使用者的成本控制
* [分析](https://code.claude.com/docs/zh-TW/analytics.md)儀表板
* [伺服器管理的設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)
* 稽核日誌

Claude for Enterprise 上的 Claude Code ZDR 僅適用於 Anthropic 的直接平台。對於在 Amazon Bedrock、Google Cloud 的 Agent Platform 或 Microsoft Foundry 上的 Claude 部署，請參考這些平台的資料保留政策。

## ZDR 範圍

ZDR 涵蓋 Claude for Enterprise 上的 Claude Code 推理。

> [!WARNING]
>
> ZDR 在每個組織的基礎上啟用。每個新組織都需要由您的 Anthropic 帳戶團隊單獨啟用 ZDR。ZDR 不會自動應用於在同一帳戶下創建的新組織。請聯繫您的帳戶團隊為任何新組織啟用 ZDR。

### 將 Claude Code 流量路由到您的 ZDR 組織

ZDR 適用於向啟用 ZDR 的組織進行身份驗證的請求。如果開發人員使用個人帳戶或來自不同組織的 API 金鑰登入 Claude Code，這些會話不受保護。若要要求開發人員的 claude.ai 登入屬於您的 ZDR 組織，請部署 `forceLoginMethod` 和 `forceLoginOrgUUID` 受管設定；請參閱[限制登入到您的組織](https://code.claude.com/docs/zh-TW/authentication.md#restrict-login-to-your-organization)，其中也說明了這些金鑰如何處理 Claude Console 登入。

### ZDR 涵蓋的內容

ZDR 涵蓋通過 Claude for Enterprise 上的 Claude Code 進行的模型推理呼叫。當您在終端中使用 Claude Code 時，您發送的提示和 Claude 生成的回應不會由 Anthropic 保留。這適用於 ZDR 組織可用的每個模型。某些模型預設需要資料保留；請參閱 [ZDR 下的模型可用性](#model-availability-under-zdr)。

### ZDR 不涵蓋的內容

即使對於啟用了 ZDR 的組織，ZDR 也不適用於以下內容。這些功能遵循[標準資料保留政策](https://code.claude.com/docs/zh-TW/data-usage.md#data-retention)：

| 功能 | 詳情 |
| - | - |
| claude.ai 上的聊天 | 通過 Claude for Enterprise 網頁介面的聊天對話不受 ZDR 保護。 |
| Cowork | Cowork 會話不受 ZDR 保護。 |
| Claude Code 分析 | 不存儲提示或模型回應，但收集生產力中繼資料，例如帳戶電子郵件和使用統計資訊。對於 ZDR 組織，貢獻指標不可用；[分析儀表板](https://code.claude.com/docs/zh-TW/analytics.md)僅顯示使用指標。 |
| 使用者和座位管理 | 管理資料（例如帳戶電子郵件和座位分配）根據標準政策保留。 |
| 第三方整合 | 由第三方工具、MCP servers 或其他外部整合處理的資料不受 ZDR 保護。請獨立審查這些服務的資料處理實踐。 |

## ZDR 下停用的功能

當 Claude for Enterprise 上的 Claude Code 組織啟用 ZDR 時，某些需要儲存提示或完成內容的功能會在後端層級自動停用：

| 功能 | 原因 |
| - | - |
| [Cloud sessions](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)，包括從 [Desktop app](https://code.claude.com/docs/zh-TW/desktop.md#cloud-sessions) 啟動的工作階段 | 需要伺服器端儲存工作階段資料，包括包含提示和完成內容的對話歷史記錄。 |
| [Chat 和 Cowork 整合](https://support.claude.com/en/articles/17444462-set-up-and-manage-the-new-unified-claude-experience-for-your-enterprise-organization) | 需要雲端工作階段。 |
| [Claude Tag](https://claude.com/docs/claude-tag) | 保留頻道記憶和工作階段文字記錄。 |
| [Artifacts](https://code.claude.com/docs/zh-TW/artifacts.md) | 需要在 Anthropic 營運的基礎設施上儲存已發佈的頁面內容。 |
| 意見反饋提交（`/feedback`、`/bug`、`/share`） | 提交意見反饋會將對話資料傳送至 Anthropic。 |
| [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) | 在 Anthropic 伺服器上儲存工作階段文字記錄，以跨裝置同步對話。 |

無論用戶端顯示如何，這些功能都會在後端被封鎖。如果您在啟動期間在 Claude Code 終端中看到停用的功能，嘗試使用它會傳回一個錯誤，指示組織的政策不允許該操作。

未來的功能如果需要儲存提示或完成內容，也可能被停用。

### ZDR 下的模型可用性

Claude Fable 5.1 和 Fable 5 是[涵蓋的模型](https://support.claude.com/en/articles/15425695-covered-models)，[預設需要資料保留](https://platform.claude.com/docs/en/manage-claude/api-and-data-retention#model-specific-data-retention-requirements)，ZDR 組織或工作區是否可以使用它們由涵蓋的模型政策而非 Claude Code 管理。如果您的組織無法使用它們，這些模型要麼在 `/model` 選擇器中不存在，要麼顯示為停用，伺服器會拒絕針對它們的請求，無論用戶端設定如何。

其他模型在 ZDR 下仍然可用。Fable 模型不是預設值，`best` 別名（在可用的地方解析為最新的 Fable 模型）在無法使用的組織中解析為 Opus。

## 政策違規的資料保留

即使啟用 ZDR，Anthropic 仍可能在法律要求或為了解決使用政策違規時保留資料。如果工作階段因政策違規而被標記，Anthropic 可能會保留相關的輸入和輸出長達 2 年，與 Anthropic 的標準 ZDR 政策一致。

## 請求 ZDR

要為 Claude for Enterprise 上的 Claude Code 請求 ZDR，請[聯繫銷售](https://www.anthropic.com/contact-sales?utm_source=claude_code\&utm_medium=docs\&utm_content=zero_data_retention_request)或您的 Anthropic 帳戶團隊。您的帳戶團隊將在內部提交請求，Anthropic 將在確認符合條件後在您的組織上審查並啟用 ZDR。所有啟用操作都會被審計記錄。

如果您目前通過按使用量付費的 API 密鑰使用 Claude Code 的 ZDR，您可以過渡到 Claude for Enterprise 以獲得管理功能的訪問權限，同時為 Claude Code 保持 ZDR。請聯繫您的帳戶團隊以協調遷移。

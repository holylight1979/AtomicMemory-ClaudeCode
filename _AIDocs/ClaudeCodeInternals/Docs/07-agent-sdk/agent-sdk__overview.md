<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/agent-sdk/overview | lastmod: 2026-09-22 | section: Agent SDK / Agent SDK -->
> 來源：https://code.claude.com/docs/zh-TW/agent-sdk/overview（官方 zh-TW，lastmod 2026-09-22）｜分類：Agent SDK › Agent SDK｜EN 摘要：Build production AI agents with Claude Code as a library

# Agent SDK 概述

> 使用 Claude Code 作為程式庫構建生產級 AI 代理

代理是一種應用程式，它通過規劃自己的步驟並呼叫讀取檔案、執行命令或編輯程式碼的工具來完成任務。Agent SDK 提供與 Claude Code 相同的工具、[代理迴圈](https://code.claude.com/docs/zh-TW/agent-sdk/agent-loop.md)和上下文管理，可在 Python 和 TypeScript 中進行程式設計。

## 將 Agent SDK 與其他 Claude 工具進行比較

Agent SDK、CLI、Client SDK 和 Managed Agents 在誰執行代理、內建功能以及如何存取方面有所不同。找到符合您想要構建和執行方式的列。

| 您想要 | 使用 | 您會獲得 |
| - | - | - |
| 在您自己操作的程序中，將 Claude Code 的代理嵌入到您自己的 Python 或 TypeScript 應用程式中 | **Agent SDK** | 一個執行 Claude Code 二進位檔的庫，具有 Claude Code 的[功能](#capabilities)，例如內建工具、權限、工作階段和 hooks。 |
| 進行互動式開發或從終端執行一次性任務 | [**Claude Code CLI**](https://code.claude.com/docs/zh-TW/overview.md) | 終端介面，為日常互動使用而構建。 |
| 直接從您自己的程式碼呼叫 Claude API | [**Client SDK**](https://platform.claude.com/docs/en/cli-sdks-libraries/overview) | 從任何 Client SDK 語言直接存取 Claude API。您自己撰寫工具迴圈，或讓 Client SDK 的測試版[工具執行器](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-runner)驅動它。 |
| 讓 Anthropic 託管代理，透過 Claude API 進行設定 | [**Managed Agents**](https://platform.claude.com/docs/en/managed-agents/overview) | 一個託管代理工具，執行代理迴圈，在 Anthropic 管理的雲端沙箱或您自己基礎設施上的[自託管沙箱](https://platform.claude.com/docs/en/managed-agents/self-hosted-sandboxes)中具有工作階段。從[您語言的 SDK](https://platform.claude.com/docs/en/managed-agents/quickstart#install-the-sdk)、`ant` CLI 或 REST API 使用它。 |

若要從 Python 或 TypeScript 以外的語言驅動相同的代理迴圈，請[以子程序的形式執行 CLI](https://code.claude.com/docs/zh-TW/headless.md)，使用 `-p` 旗標和 `--output-format json`。

## 功能

這些 Claude Code 功能可在 SDK 中使用：

| 功能 | 功能說明 | 深入了解 |
| - | - | - |
| 內建工具 | 讀取、寫入、編輯檔案、執行命令和搜尋網路 | [工具參考](https://code.claude.com/docs/zh-TW/tools-reference.md) |
| Hooks | 在代理生命週期的關鍵點執行自訂程式碼 | [Hooks](https://code.claude.com/docs/zh-TW/agent-sdk/hooks.md) |
| 子代理 | 生成專門的代理來處理集中的子任務 | [子代理](https://code.claude.com/docs/zh-TW/agent-sdk/subagents.md) |
| MCP | 透過 Model Context Protocol 連接外部工具和資料來源 | [MCP](https://code.claude.com/docs/zh-TW/agent-sdk/mcp.md) |
| 權限 | 控制哪些工具自動執行、哪些需要批准 | [權限](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md) |
| 工作階段 | 在多次交換中保持上下文、稍後恢復或分叉 | [工作階段](https://code.claude.com/docs/zh-TW/agent-sdk/sessions.md) |
| Skills、命令和記憶 | 從您的專案的 `.claude/` 和 `~/.claude/` 自動載入，與 Claude Code 相同 | [Skills](https://code.claude.com/docs/zh-TW/agent-sdk/skills.md)、[命令](https://code.claude.com/docs/zh-TW/agent-sdk/skills.md#commands-in-agent-sdk-sessions)、[記憶](https://code.claude.com/docs/zh-TW/agent-sdk/modifying-system-prompts.md)、[設定載入](https://code.claude.com/docs/zh-TW/agent-sdk/claude-code-features.md) |
| Plugins | 封裝 skills、代理、hooks 和 MCP 伺服器，並按本機路徑載入 | [Plugins](https://code.claude.com/docs/zh-TW/agent-sdk/plugins.md) |

## 開始使用

按照 [快速入門](https://code.claude.com/docs/zh-TW/agent-sdk/quickstart.md) 安裝 SDK、設定您的 API 金鑰，並建立您的第一個代理，該代理可以找到並修復現有程式碼中的錯誤。

> [!NOTE]
>
> 除非事先獲得批准，否則 Anthropic 不允許第三方開發人員為其產品（包括基於 Claude Agent SDK 建立的代理）提供 claude.ai 登入或速率限制。請改用 [快速入門](https://code.claude.com/docs/zh-TW/agent-sdk/quickstart.md) 中描述的 API 金鑰驗證方法。

## 變更日誌

查看完整的變更日誌以了解 SDK 更新、錯誤修復和新功能：

* **TypeScript SDK**：[檢視 CHANGELOG.md](https://github.com/anthropics/claude-agent-sdk-typescript/blob/main/CHANGELOG.md)
* **Python SDK**：[檢視 CHANGELOG.md](https://github.com/anthropics/claude-agent-sdk-python/blob/main/CHANGELOG.md)

## 報告錯誤

如果您遇到 Agent SDK 的錯誤或問題：

* **TypeScript SDK**：[在 GitHub 上報告問題](https://github.com/anthropics/claude-agent-sdk-typescript/issues)
* **Python SDK**：[在 GitHub 上報告問題](https://github.com/anthropics/claude-agent-sdk-python/issues)

## 品牌指南

對於整合 Claude Agent SDK 的合作夥伴，使用 Claude 品牌是可選的。在您的產品中引用 Claude 時：

**允許：**

* "Claude Agent"（下拉選單的首選）
* "Claude"（當已在標記為"Agents"的選單中時）
* "\{YourAgentName} Powered by Claude"（如果您有現有的代理名稱）

**不允許：**

* "Claude Code" 或 "Claude Code Agent"
* Claude Code 品牌的 ASCII 藝術或模仿 Claude Code 的視覺元素

您的產品應保持自己的品牌，不應顯示為 Claude Code 或任何 Anthropic 產品。有關品牌合規性的問題，請聯絡 Anthropic [銷售團隊](https://www.anthropic.com/contact-sales)。

## 許可證和條款

Claude Agent SDK 的使用受 [Anthropic 商業服務條款](https://www.anthropic.com/legal/commercial-terms)管制，包括當您使用它為您自己的客戶和最終使用者提供的產品和服務提供動力時，除非特定元件或依賴項受到該元件 LICENSE 檔案中指示的不同許可證的保護。

## 後續步驟

這些資源涵蓋了使用 Agent SDK 構建的更深入的技術細節和範例專案。

* [快速入門](https://code.claude.com/docs/zh-TW/agent-sdk/quickstart.md)：構建您的第一個代理，用於尋找和修復錯誤
* [遷移指南](https://code.claude.com/docs/zh-TW/agent-sdk/migration-guide.md)：從 Claude Code SDK 套件遷移到 Agent SDK
* [代理迴圈](https://code.claude.com/docs/zh-TW/agent-sdk/agent-loop.md)：Claude 如何規劃、呼叫工具以及決定何時任務完成
* [範例代理](https://github.com/anthropics/claude-agent-sdk-demos)：用於本地開發的示範應用程式
* [TypeScript SDK](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md)：完整的 TypeScript API 參考和範例
* [Python SDK](https://code.claude.com/docs/zh-TW/agent-sdk/python.md)：完整的 Python API 參考和範例
* [Agent harness 設計](https://claude.com/blog/a-harness-for-every-task-dynamic-workflows-in-claude-code)：Claude Code 團隊如何使用動態工作流程來同時協調許多子代理

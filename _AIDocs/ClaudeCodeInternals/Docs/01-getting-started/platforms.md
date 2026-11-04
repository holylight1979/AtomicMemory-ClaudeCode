<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/platforms | lastmod: 2026-10-30 | section: Getting started / Platforms and integrations -->
> 來源：https://code.claude.com/docs/zh-TW/platforms（官方 zh-TW，lastmod 2026-10-30）｜分類：Getting started › Platforms and integrations｜EN 摘要：Choose where to run Claude Code and what to connect it to. Compare the CLI, Desktop, VS Code, JetBrains, web, mobile, and integrations like Chrome, Slack, and CI/CD.

# 平台和整合

> 選擇在何處執行 Claude Code 以及要連接什麼。比較 CLI、Desktop、VS Code、JetBrains、Web 和 Chrome、Slack 和 CI/CD 等整合。

Claude Code 在各處執行相同的底層引擎，但每個介面都針對不同的工作方式進行了調整。此頁面幫助您為工作流程選擇合適的平台，並連接您已經使用的工具。

## 在何處執行 Claude Code

根據您喜歡的工作方式和專案所在位置選擇平台。

| 平台 | 最適合 | 您將獲得 |
| :- | :- | :- |
| [CLI](https://code.claude.com/docs/zh-TW/quickstart.md) | 終端機工作流程、指令碼、遠端伺服器 | 完整功能集、[Agent SDK](https://code.claude.com/docs/zh-TW/headless.md)、macOS 上的[電腦使用](https://code.claude.com/docs/zh-TW/computer-use.md)（Pro、Max 和 Ultra）、第三方提供商 |
| [Desktop](https://code.claude.com/docs/zh-TW/desktop.md) | 視覺審查、並行工作階段、託管設定 | 差異檢視器、應用程式預覽、Pro、Max 和 Ultra 上的[電腦使用](https://code.claude.com/docs/zh-TW/desktop.md#let-claude-use-your-computer)和 [Dispatch](https://code.claude.com/docs/zh-TW/desktop.md#sessions-from-dispatch) |
| [VS Code](https://code.claude.com/docs/zh-TW/vs-code.md) | 在 VS Code 內工作而無需切換到終端 | 內聯 diff、整合終端、檔案上下文 |
| [JetBrains](https://code.claude.com/docs/zh-TW/jetbrains.md) | 在 IntelliJ、PyCharm、WebStorm 或其他 JetBrains IDE 內工作 | Diff 檢視器、選擇共享、終端會話 |
| [Web](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md) | 不需要太多操控的長時間執行任務，或應該在您離線時繼續進行的工作 | 雲端、Anthropic 託管（預設）；在您斷開連接後繼續 |
| [Mobile](https://code.claude.com/docs/zh-TW/mobile.md) | 在遠離電腦時啟動和監控任務 | iOS 和 Android 版 Claude 應用程式的雲端工作階段、用於本機工作階段的 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md)、Pro、Max 和 Ultra 上的 [Dispatch](https://code.claude.com/docs/zh-TW/desktop.md#sessions-from-dispatch) 到 Desktop |

CLI 是終端原生工作的最完整介面：指令碼和 Agent SDK 僅限 CLI。第三方提供商也可在 [VS Code](https://code.claude.com/docs/zh-TW/vs-code.md#use-third-party-providers) 和 [JetBrains](https://code.claude.com/docs/zh-TW/feature-availability.md#features-available-on-every-provider) 中使用，其在您 IDE 的終端中執行 CLI。企業 [Desktop](https://code.claude.com/docs/zh-TW/desktop.md) 部署支援 Google Cloud 的 Agent Platform，Desktop 支援[閘道提供商](https://code.claude.com/docs/zh-TW/llm-gateway-connect.md#desktop-app)；對於 Amazon Bedrock 或 Microsoft Foundry，請改用 CLI 或 IDE 擴充功能，或 [Claude Desktop on 3P](https://claude.com/docs/third-party/claude-desktop/overview)，其在這些提供商上執行 Code 標籤。Desktop 和 IDE 擴充功能用視覺審查和更緊密的編輯器整合來交換一些僅限 CLI 的功能。Web 在雲端中執行，因此任務在您斷開連接後會繼續進行。Mobile 是進入這些相同雲端會話或透過 Remote Control 進入本地會話的瘦用戶端，並可以透過 Dispatch 將任務發送到 Desktop。

您可以在同一專案上混合使用介面。配置、專案記憶體和 MCP 伺服器在本地介面之間共享。

## 連接您的工具

整合讓 Claude 與程式碼庫外的服務協作。

| 整合 | 它的作用 | 用途 |
| :- | :- | :- |
| [Chrome](https://code.claude.com/docs/zh-TW/chrome.md) | 使用您已登入的會話控制您的瀏覽器 | 測試 Web 應用程式、填寫表單、自動化沒有 API 的網站 |
| [GitHub Actions](https://code.claude.com/docs/zh-TW/github-actions.md) | 在您的 CI 管道中執行 Claude | 自動化 PR 審查、問題分類、排程維護 |
| [GitLab CI/CD](https://code.claude.com/docs/zh-TW/gitlab-ci-cd.md) | 與 GitHub Actions 相同，但用於 GitLab | GitLab 上的 CI 驅動自動化 |
| [Code Review](https://code.claude.com/docs/zh-TW/code-review.md) | 自動審查每個 PR | 在人工審查之前捕捉錯誤 |
| [Slack](https://code.claude.com/docs/zh-TW/slack.md) | 以您自己的帳戶回應您的頻道中的 `@Claude` 提及 | 在 Pro、Max 和 Ultra 方案上，將團隊聊天中的錯誤報告轉換為 pull request |
| [Claude Tag](https://claude.com/docs/claude-tag) | 以您組織的共享身分執行 `@Claude`，具有管理員設定的存取權限 | Team 和 Enterprise 方案上的共享團隊存取，而不是按使用者的 Slack 會話 |

對於此處未列出的整合，[MCP servers](https://code.claude.com/docs/zh-TW/mcp.md) 和[連接器](https://code.claude.com/docs/zh-TW/desktop.md#connect-external-tools)讓您連接幾乎任何東西：Linear、Notion、Google Drive 或您自己的內部 API。

## 當您遠離終端時工作

Claude Code 提供了多種方式讓您在不在終端機時進行工作。它們在觸發工作的方式、Claude 執行的位置以及您需要設定的程度上有所不同。

| | 觸發 | Claude 執行位置 | 設定 | 最適合 |
| :- | :- | :- | :- | :- |
| [Dispatch](https://code.claude.com/docs/zh-TW/desktop.md#sessions-from-dispatch) | 從 Claude 行動應用程式傳送任務訊息 | 您的機器 (Desktop) | [將行動應用程式與 Desktop 配對](https://support.claude.com/en/articles/13947068) | 在您不在時委派工作，最少設定 |
| [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) | 從 [claude.ai/code](https://claude.ai/code) 或 Claude 行動應用程式驅動執行中的工作階段 | 您的機器 (CLI、Desktop 或 VS Code) | 執行 [`claude remote-control` 或 `/remote-control`](https://code.claude.com/docs/zh-TW/remote-control#start-a-remote-control-session) | 從另一個裝置控制進行中的工作 |
| [Channels](https://code.claude.com/docs/zh-TW/channels.md) | 從聊天應用程式 (如 Telegram 或 Discord) 或您自己的伺服器推送事件 | 您的機器 (CLI) | [安裝頻道外掛程式](https://code.claude.com/docs/zh-TW/channels.md#quickstart) 或 [建立您自己的](https://code.claude.com/docs/zh-TW/channels-reference.md) | 對外部事件 (如 CI 失敗或聊天訊息) 做出反應 |
| [Slack](https://code.claude.com/docs/zh-TW/slack.md) | 在團隊頻道中提及 `@Claude` | Anthropic 雲端 | [安裝 Slack 應用程式](https://code.claude.com/docs/zh-TW/slack.md#setting-up-claude-code-in-slack) 並啟用 [網路上的 Claude Code](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)，適用於 Pro、Max 和 Ultra 方案 | 從團隊聊天進行 PR 和審查 |
| [Self-hosted environments](https://code.claude.com/docs/zh-TW/self-hosted-environments) | 啟動 [雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md) 並選擇您組織的環境 | 您組織的基礎設施 | [部署執行器](https://code.claude.com/docs/zh-TW/self-hosted-environments-quickstart.md)，在 Team 和 Enterprise 方案上 | 必須在您的網路內執行的雲端工作階段 |
| [Scheduled tasks](https://code.claude.com/docs/zh-TW/scheduled-tasks.md) | 設定排程 | [CLI](https://code.claude.com/docs/zh-TW/scheduled-tasks.md)、[Desktop](https://code.claude.com/docs/zh-TW/desktop-scheduled-tasks.md) 或 [雲端](https://code.claude.com/docs/zh-TW/routines.md) | 選擇頻率 | 定期自動化 (如每日審查) |

如果您不確定從何處開始，[安裝 CLI](https://code.claude.com/docs/zh-TW/quickstart.md) 並在專案目錄中執行它。如果您不想使用終端，[Desktop](https://code.claude.com/docs/zh-TW/desktop-quickstart.md) 為您提供相同的引擎和圖形介面。

## 相關資源

### 平台

* [CLI 快速入門](https://code.claude.com/docs/zh-TW/quickstart.md)：在終端中安裝並執行您的第一個命令
* [Desktop](https://code.claude.com/docs/zh-TW/desktop.md)：視覺 diff 審查、並行會話、電腦使用和 Dispatch
* [VS Code](https://code.claude.com/docs/zh-TW/vs-code.md)：編輯器內的 Claude Code 擴充功能
* [JetBrains](https://code.claude.com/docs/zh-TW/jetbrains.md)：IntelliJ、PyCharm 和其他 JetBrains IDE 的擴充功能
* [Web](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)：在您斷開連接時繼續執行的雲端會話，位於 claude.ai/code
* [Projects](https://code.claude.com/docs/zh-TW/claude-projects.md)：一個對話，Claude 在其中協調許多雲端會話以完成一項工作並回報結果
* [Mobile](https://code.claude.com/docs/zh-TW/mobile.md)：用於在遠離電腦時啟動和監控任務的 [iOS](https://apps.apple.com/us/app/claude-by-anthropic/id6473753684) 和 [Android](https://play.google.com/store/apps/details?id=com.anthropic.claude) 版 Claude 應用程式

### 整合

* [Chrome](https://code.claude.com/docs/zh-TW/chrome.md)：使用您已登入的會話自動化瀏覽器任務
* [Computer use](https://code.claude.com/docs/zh-TW/computer-use.md)：讓 Claude 在 macOS 上開啟應用程式並控制您的螢幕
* [GitHub Actions](https://code.claude.com/docs/zh-TW/github-actions.md)：在您的 CI 管道中執行 Claude
* [GitLab CI/CD](https://code.claude.com/docs/zh-TW/gitlab-ci-cd.md)：GitLab 的相同功能
* [Code Review](https://code.claude.com/docs/zh-TW/code-review.md)：每個拉取請求上的自動審查
* [Slack](https://code.claude.com/docs/zh-TW/slack.md)：從團隊聊天發送任務，取回 PR，適用於 Pro、Max 和 Ultra 方案
* [Claude Tag](https://claude.com/docs/claude-tag)：在 Team 和 Enterprise 方案上執行 `@Claude` 作為您組織的共享身分

### 遠端存取

* [Dispatch](https://code.claude.com/docs/zh-TW/desktop.md#sessions-from-dispatch)：從您的手機傳送任務，它可以生成 Desktop 會話
* [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md)：從您的手機或瀏覽器驅動執行中的會話
* [Channels](https://code.claude.com/docs/zh-TW/channels.md)：將來自聊天應用程式或您自己的伺服器的事件推送到會話中
* [排程選項](https://code.claude.com/docs/zh-TW/scheduled-tasks.md#compare-scheduling-options)：按定期排程執行提示詞

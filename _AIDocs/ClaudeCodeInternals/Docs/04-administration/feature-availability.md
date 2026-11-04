<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/feature-availability | lastmod: 2026-10-30 | section: Administration / Deployment -->
> 來源：https://code.claude.com/docs/zh-TW/feature-availability（官方 zh-TW，lastmod 2026-10-30）｜分類：Administration › Deployment｜EN 摘要：Compare which Claude Code features are available across Anthropic subscription plans, the Anthropic Console, Amazon Bedrock, Claude Platform on AWS, Google Cloud's Agent Platform, and Microsoft Foundry.

# 功能可用性

> 比較 Claude Code 功能在 Anthropic 訂閱計畫、Anthropic Console、Amazon Bedrock、AWS 上的 Claude Platform、Google Cloud 的 Agent Platform 和 Microsoft Foundry 中的可用性。

Claude Code CLI 和所有在本地執行的功能在每個提供者上的運作方式完全相同。如需每個提供者的設定說明，請參閱[企業部署概述](https://code.claude.com/docs/zh-TW/third-party-integrations.md)。若要直接跳到您的提供者上缺少的功能，請參閱[按提供者摘要](#summary-by-provider)標籤。

在下表中，✓ 表示可用，✗ 表示不可用，「請參閱備註」連結到部分支援的註腳。✓ 後面的限定詞會將可用性縮小到該子集，「管理員啟用」表示該功能處於關閉狀態，直到組織管理員將其開啟。

## 依模型供應商區分的可用性

身分驗證的方式決定了 Claude Code 能使用哪些功能。若要查看您的供應商缺少哪些功能的單一清單，請參閱[依供應商摘要](#summary-by-provider)分頁。若要在下列表格中找到對應的欄位：

* **Claude 訂閱**：您使用 Pro、Max、Ultra、Team 或 Enterprise 方案的 claude.ai 帳戶登入
* **Anthropic Console**：您使用 Anthropic API 金鑰進行身分驗證，或[在沒有 API 金鑰的情況下登入 Console 帳戶](https://code.claude.com/docs/zh-TW/authentication.md#sign-in-without-an-api-key)
* **Amazon Bedrock**：您使用 Amazon Bedrock 模型目錄中的 Claude 模型，並設定 `CLAUDE_CODE_USE_BEDROCK`。[Mantle 端點](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#use-the-mantle-endpoint)（`CLAUDE_CODE_USE_MANTLE`）也包含在此欄位中
* **Claude Platform on AWS**：您透過 AWS Marketplace 購買 Claude，但呼叫 Anthropic API，並設定 `CLAUDE_CODE_USE_ANTHROPIC_AWS`
* **Google Cloud's Agent Platform**：由 Google 營運；您設定 `CLAUDE_CODE_USE_VERTEX`
* **Microsoft Foundry**：由 Anthropic 營運；您設定 `CLAUDE_CODE_USE_FOUNDRY`

### 所有供應商皆可使用的功能

以下功能在每個供應商上皆可使用：

* [CLI](https://code.claude.com/docs/zh-TW/quickstart.md) 與 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md)
* [VS Code](https://code.claude.com/docs/zh-TW/vs-code.md) 與 [JetBrains](https://code.claude.com/docs/zh-TW/jetbrains.md) 擴充功能
* [Subagent](https://code.claude.com/docs/zh-TW/sub-agents.md)、[hook](https://code.claude.com/docs/zh-TW/hooks-guide.md)、[命令](https://code.claude.com/docs/zh-TW/commands.md)與 [skill](https://code.claude.com/docs/zh-TW/skills.md)
* [CLAUDE.md 記憶](https://code.claude.com/docs/zh-TW/memory.md)、[外掛](https://code.claude.com/docs/zh-TW/plugins/overview.md)與 [MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md)
* [檢查點](https://code.claude.com/docs/zh-TW/checkpointing.md)、[沙箱機制](https://code.claude.com/docs/zh-TW/sandboxing.md)與 [Workflows](https://code.claude.com/docs/zh-TW/workflows.md)
* [OpenTelemetry 指標](https://code.claude.com/docs/zh-TW/monitoring-usage.md)與[受管設定檔](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)

以下功能在不同供應商之間有所差異：

* **MCP 伺服器**：只有當您的 claude.ai 訂閱是目前使用中的身分驗證方式時，才會載入[來自 claude.ai 的連接器](https://code.claude.com/docs/zh-TW/mcp.md#use-mcp-servers-from-claude-ai)。Microsoft Foundry [託管於 Azure 的部署](https://platform.claude.com/docs/en/build-with-claude/claude-in-microsoft-foundry#hosting-options)不支援[工具搜尋](https://code.claude.com/docs/zh-TW/mcp.md#configure-tool-search)。在 Google Cloud's Agent Platform 上，早於 Claude Opus 4.5、Claude Sonnet 4.5 與 Claude Haiku 4.5 的模型不支援工具搜尋
* **Subagent**：當主要對話執行 Fable 時，若使用 Claude 訂閱、Anthropic Console 帳戶，或透過 `ANTHROPIC_BASE_URL` 連線的 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)，內建的 [Explore subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#built-in-subagents) 會在 Opus 上執行。在其他供應商上（包括 Claude Platform on AWS），它會在 Fable 上執行
* **[命令](https://code.claude.com/docs/zh-TW/commands.md#all-commands)**：
  * `/design-sync` 與 `/import`（及其 `claude import` 子命令形式）在 Amazon Bedrock、Google Cloud's Agent Platform、Microsoft Foundry 與 Claude Platform on AWS 上無法使用，透過 [Claude apps 閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway#availability-and-limitations)也無法使用
  * `/voice` 需要 claude.ai 帳戶
  * `/list-agents` 及其別名 `/peers` 僅在[已啟用跨工作階段訊息傳遞](https://code.claude.com/docs/zh-TW/cross-session-messaging.md#availability)的工作階段中可用

### 需要 Claude 訂閱的功能

以下功能需要使用 claude.ai 帳戶登入，無法透過 Anthropic Console API 金鑰或第三方供應商使用：

* [雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)與行動裝置上的 Claude Code
* [Slack 中的 Claude Code](https://code.claude.com/docs/zh-TW/slack.md)：Pro、Max 與 Ultra 方案
* [Claude Code Desktop](https://code.claude.com/docs/zh-TW/desktop.md)
* [雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md)（`/schedule`）
* [Ultrareview](https://code.claude.com/docs/zh-TW/ultrareview.md)
* [Code Review](https://code.claude.com/docs/zh-TW/code-review.md)：Team 與 Enterprise 方案
* [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md)
* [Chrome 擴充功能](https://code.claude.com/docs/zh-TW/chrome.md)
* [電腦操作](https://code.claude.com/docs/zh-TW/computer-use.md)：Pro、Max 與 Ultra 方案
* [Artifact](https://code.claude.com/docs/zh-TW/artifacts.md)：Pro、Max、Ultra、Team 與 Enterprise 方案
* [語音聽寫](https://code.claude.com/docs/zh-TW/voice-dictation.md)

Desktop 是部分例外：[閘道路由可以在應用程式中設定，或由管理員設定](https://code.claude.com/docs/zh-TW/llm-gateway-connect.md#desktop-app)。[Claude Desktop on 3P](https://claude.com/docs/third-party/claude-desktop/overview) 也能在 Amazon Bedrock、Google Cloud's Agent Platform、Microsoft Foundry 或自行託管的 LLM 閘道上執行 Code 分頁。它也能搭配 Anthropic Console API 金鑰，在 [Claude API](https://claude.com/docs/third-party/claude-desktop/claude-api) 上執行 Code 分頁。如需這些功能在各方案中的可用性，請參閱[依訂閱方案區分的可用性](#availability-by-subscription-plan)。

### 因供應商而異的 CLI 功能

這些功能可在本機 CLI 中使用，但依賴並非每個供應商都提供的伺服器端功能。

<table>
  <thead>
    <tr>
      <th>功能</th>
      <th>Claude 訂閱</th>
      <th>Anthropic Console</th>
      <th>Amazon Bedrock</th>
      <th>Claude Platform on AWS</th>
      <th>Google Cloud's Agent Platform</th>
      <th>Microsoft Foundry</th>
    </tr>
  </thead>

  <tbody>
    <tr>
      <td>[網頁搜尋](https://code.claude.com/docs/zh-TW/tools-reference.md#websearch-tool-behavior)</td>
      <td>✓</td>
      <td>✓</td>
      <td>✗</td>
      <td>✓</td>
      <td>請參閱附註 <sup>[1](#fn1)</sup></td>
      <td>✓</td>
    </tr>

    <tr>
      <td>[快速模式](https://code.claude.com/docs/zh-TW/fast-mode.md)</td>
      <td>✓（Team 與 Enterprise 需[由擁有者啟用](https://code.claude.com/docs/zh-TW/fast-mode.md#enable-fast-mode-for-your-organization)）</td>
      <td>✓（Opus 5 與 4.8 需要佈建）</td>
      <td>✗</td>
      <td>✗</td>
      <td>✗</td>
      <td>✗</td>
    </tr>

    <tr>
      <td>[自動模式](https://code.claude.com/docs/zh-TW/auto-mode-config.md)</td>
      <td>✓</td>
      <td>✓</td>
      <td>請參閱附註 <sup>[2](#fn2)</sup></td>
      <td>✓</td>
      <td>請參閱附註 <sup>[2](#fn2)</sup></td>
      <td>請參閱附註 <sup>[2](#fn2)</sup></td>
    </tr>

    <tr>
      <td>[Advisor](https://code.claude.com/docs/zh-TW/advisor.md)</td>
      <td>✓</td>
      <td>✓</td>
      <td>✗</td>
      <td>✗</td>
      <td>✗</td>
      <td>✗</td>
    </tr>

    <tr>
      <td>[跨工作階段訊息傳遞](https://code.claude.com/docs/zh-TW/cross-session-messaging.md)</td>
      <td>✓ <sup>[5](#fn5)</sup></td>
      <td>✓（同一台機器）<sup>[5](#fn5)</sup></td>
      <td>✓（同一台機器）<sup>[5](#fn5)</sup></td>
      <td>✓（同一台機器）<sup>[5](#fn5)</sup></td>
      <td>✓（同一台機器）<sup>[5](#fn5)</sup></td>
      <td>✓（同一台機器）<sup>[5](#fn5)</sup></td>
    </tr>

    <tr>
      <td>[頻道](https://code.claude.com/docs/zh-TW/channels.md)</td>
      <td>✓</td>
      <td>✓</td>
      <td>✗</td>
      <td>✗</td>
      <td>✗</td>
      <td>✗</td>
    </tr>

    <tr>
      <td>[GitHub Actions](https://code.claude.com/docs/zh-TW/github-actions.md)</td>
      <td>✓</td>
      <td>✓</td>
      <td>✓</td>
      <td>✗</td>
      <td>✓</td>
      <td>✓</td>
    </tr>

    <tr>
      <td>[GitLab CI/CD](https://code.claude.com/docs/zh-TW/gitlab-ci-cd.md)</td>
      <td>✓</td>
      <td>✓</td>
      <td>✓</td>
      <td>✓</td>
      <td>✓</td>
      <td>✗</td>
    </tr>
  </tbody>
</table>

### 管理與分析

組織層級的控制與使用情況可見性。

<table>
  <thead>
    <tr>
      <th>功能</th>
      <th>Claude 訂閱</th>
      <th>Anthropic Console</th>
      <th>Amazon Bedrock</th>
      <th>Claude Platform on AWS</th>
      <th>Google Cloud's Agent Platform</th>
      <th>Microsoft Foundry</th>
    </tr>
  </thead>

  <tbody>
    <tr>
      <td>[分析儀表板與 API](https://code.claude.com/docs/zh-TW/analytics.md)</td>
      <td>✓（儀表板：Team 與 Enterprise；API：Enterprise）</td>
      <td>✓ <sup>[4](#fn4)</sup></td>
      <td>✗</td>
      <td>✗</td>
      <td>✗</td>
      <td>✗</td>
    </tr>

    <tr>
      <td>[伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)</td>
      <td>✓（Team 與 Enterprise）</td>
      <td>請參閱[平台可用性](https://code.claude.com/docs/zh-TW/server-managed-settings.md#platform-availability)</td>
      <td>✗</td>
      <td>✗</td>
      <td>✗</td>
      <td>✗</td>
    </tr>

    <tr>
      <td>[零資料保留](https://code.claude.com/docs/zh-TW/zero-data-retention.md)</td>
      <td>✓（符合資格的 Enterprise 帳戶）</td>
      <td>✓（符合資格的帳戶）</td>
      <td>請參閱附註 <sup>[3](#fn3)</sup></td>
      <td>✓（符合資格的帳戶）</td>
      <td>請參閱附註 <sup>[3](#fn3)</sup></td>
      <td>請參閱附註 <sup>[3](#fn3)</sup></td>
    </tr>
  </tbody>
</table>

<sup>1</sup> 在 Google Cloud's Agent Platform 上，網頁搜尋適用於 Opus 4、Sonnet 4、Haiku 4.5 及更新的模型。\

<sup>2</sup> 在這些供應商上，自動模式僅支援 Claude Sonnet 5 或更新版本、Opus 4.7 或更新版本、Haiku 5.5 以及 Fable 模型。請參閱[自動模式設定](https://code.claude.com/docs/zh-TW/auto-mode-config.md)。如需這些供應商上的工作階段以哪種權限模式啟動，請參閱[工作階段以哪種模式啟動](https://code.claude.com/docs/zh-TW/permission-modes.md#which-mode-a-session-starts-in)。\

<sup>3</sup> 取決於您與雲端供應商的合約。\

<sup>4</sup> 僅限儀表板與 API。[貢獻指標](https://code.claude.com/docs/zh-TW/analytics.md#enable-contribution-metrics)需要 claude.ai Team 或 Enterprise 組織。\

<sup>5</sup> 在 macOS 與 Linux（包括 WSL 2 中的 Linux）上需要 Claude Code v2.1.224 或更新版本。在原生 Windows 上，需要 Claude Code v2.1.234 或更新版本。使用 API 金鑰身分驗證時，訊息傳遞僅限同一台機器。在 Amazon Bedrock、Claude Platform on AWS、Google Cloud's Agent Platform 與 Microsoft Foundry 上，訊息傳遞僅限同一台機器，且需要 Claude Code v2.1.248 或更新版本。Claude 只能從已連線至 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 的工作階段中找到您的[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)以及您在其他機器上的工作階段。若要連線，您需要 claude.ai 登入，並符合其他 [Remote Control 需求](https://code.claude.com/docs/zh-TW/remote-control.md#requirements)。請參閱[傳送訊息至其他機器上的工作階段](https://code.claude.com/docs/zh-TW/cross-session-messaging.md#message-sessions-on-other-machines)。

> [!NOTE]
>
> 若您透過 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)進行身分驗證，功能可用性會與閘道所轉送的底層供應商相同，但 Claude Code 本身關閉的功能除外。只要 `ANTHROPIC_BASE_URL` 指向 `api.anthropic.com` 以外的主機，無論閘道轉送至何處，Claude Code 都會關閉 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md#requirements) 與[伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md#platform-availability)等功能。部分 Anthropic 專屬功能（例如 [Advisor](https://code.claude.com/docs/zh-TW/advisor.md)）僅在閘道將請求完整轉送至 Anthropic API 時才能運作。
>
> 如需了解 Claude Code 在 Amazon Bedrock 或 Agent Platform 格式的閘道、`ANTHROPIC_BASE_URL` 閘道，以及 Claude apps 閘道登入之間所傳送的請求有何不同，請參閱[依連線方式區分的用戶端行為](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md#how-the-connection-method-changes-client-behavior)。

### 依供應商摘要

每個分頁列出該供應商上無法使用或僅部分支援的功能，並在有替代方案時一併列出。除了上述的[供應商特定差異](#features-available-on-every-provider)之外，未列出的功能皆與 Claude 訂閱上的運作方式相同。在 Amazon Bedrock、Google Cloud's Agent Platform、Microsoft Foundry 與 Claude Platform on AWS 上，傳送至 Anthropic 的錯誤回報與遙測預設為關閉。請參閱[依 API 供應商區分的預設行為](https://code.claude.com/docs/zh-TW/data-usage.md#default-behaviors-by-api-provider)，了解哪些流量仍會傳送至 Anthropic 以及如何選擇退出。

> [tab] Amazon Bedrock
>
> \*\*無法使用：\*\*所有[需要 Claude 訂閱的功能](#features-that-require-a-claude-subscription)，以及[網頁搜尋](https://code.claude.com/docs/zh-TW/tools-reference.md#websearch-tool-behavior)、[快速模式](https://code.claude.com/docs/zh-TW/fast-mode.md)、[Advisor](https://code.claude.com/docs/zh-TW/advisor.md)、[頻道](https://code.claude.com/docs/zh-TW/channels.md)、[分析儀表板](https://code.claude.com/docs/zh-TW/analytics.md)、[伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)，以及 [`/design-sync` 與 `/import` 命令](https://code.claude.com/docs/zh-TW/commands#all-commands)。
>
> **部分支援：**
>
> * [Desktop](https://code.claude.com/docs/zh-TW/desktop.md)：僅能透過 [Claude Desktop on 3P](https://claude.com/docs/third-party/claude-desktop/overview)
> * [自動模式](https://code.claude.com/docs/zh-TW/auto-mode-config.md)：僅限 Sonnet 5 或更新版本、Opus 4.7 或更新版本、Haiku 5.5 以及 Fable 模型
> * [跨工作階段訊息傳遞](https://code.claude.com/docs/zh-TW/cross-session-messaging.md)：僅限此機器上您的工作階段之間 <sup>[5](#fn5)</sup>
> * [零資料保留](https://code.claude.com/docs/zh-TW/zero-data-retention.md)：取決於您與 AWS 的合約
>
> \*\*替代方案：\*\*排程方面，請使用 [`/loop`](https://code.claude.com/docs/zh-TW/scheduled-tasks) 取代 `/schedule`。雲端工作階段方面，請使用 [GitHub Actions](https://code.claude.com/docs/zh-TW/github-actions.md) 或 [GitLab CI/CD](https://code.claude.com/docs/zh-TW/gitlab-ci-cd.md)。網頁查詢方面，請搭配特定 URL 使用 [WebFetch 工具](https://code.claude.com/docs/zh-TW/tools-reference.md#webfetch-tool-behavior)。

> [tab] Claude Platform on AWS
>
> \*\*無法使用：\*\*所有[需要 Claude 訂閱的功能](#features-that-require-a-claude-subscription)，以及[快速模式](https://code.claude.com/docs/zh-TW/fast-mode.md)、[Advisor](https://code.claude.com/docs/zh-TW/advisor.md)、[頻道](https://code.claude.com/docs/zh-TW/channels.md)、[GitHub Actions](https://code.claude.com/docs/zh-TW/github-actions.md)、[分析儀表板](https://code.claude.com/docs/zh-TW/analytics.md)、[伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)，以及 [`/design-sync` 與 `/import` 命令](https://code.claude.com/docs/zh-TW/commands#all-commands)。
>
> **Amazon Bedrock 不支援但此處可用：**[網頁搜尋](https://code.claude.com/docs/zh-TW/tools-reference.md#websearch-tool-behavior)。
>
> **部分支援：**
>
> * [跨工作階段訊息傳遞](https://code.claude.com/docs/zh-TW/cross-session-messaging.md)：僅限此機器上您的工作階段之間 <sup>[5](#fn5)</sup>
>
> \*\*替代方案：\*\*排程方面，請使用 [`/loop`](https://code.claude.com/docs/zh-TW/scheduled-tasks) 取代 `/schedule`。雲端工作階段方面，請使用 [GitLab CI/CD](https://code.claude.com/docs/zh-TW/gitlab-ci-cd.md)。

> [tab] Google Cloud's Agent Platform
>
> \*\*無法使用：\*\*所有[需要 Claude 訂閱的功能](#features-that-require-a-claude-subscription)，以及[快速模式](https://code.claude.com/docs/zh-TW/fast-mode.md)、[Advisor](https://code.claude.com/docs/zh-TW/advisor.md)、[頻道](https://code.claude.com/docs/zh-TW/channels.md)、[分析儀表板](https://code.claude.com/docs/zh-TW/analytics.md)、[伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)，以及 [`/design-sync` 與 `/import` 命令](https://code.claude.com/docs/zh-TW/commands#all-commands)。
>
> **部分支援：**
>
> * [Desktop](https://code.claude.com/docs/zh-TW/desktop.md)：透過[受管設定](https://claude.com/docs/third-party/claude-desktop/configuration)或 [Claude Desktop on 3P](https://claude.com/docs/third-party/claude-desktop/overview)
> * [網頁搜尋](https://code.claude.com/docs/zh-TW/tools-reference.md#websearch-tool-behavior)：Opus 4、Sonnet 4、Haiku 4.5 及更新的模型
> * [自動模式](https://code.claude.com/docs/zh-TW/auto-mode-config.md)：僅限 Sonnet 5 或更新版本、Opus 4.7 或更新版本、Haiku 5.5 以及 Fable 模型
> * [跨工作階段訊息傳遞](https://code.claude.com/docs/zh-TW/cross-session-messaging.md)：僅限此機器上您的工作階段之間 <sup>[5](#fn5)</sup>
> * [零資料保留](https://code.claude.com/docs/zh-TW/zero-data-retention.md)：取決於您與 Google Cloud 的合約
>
> \*\*替代方案：\*\*排程方面，請使用 [`/loop`](https://code.claude.com/docs/zh-TW/scheduled-tasks) 取代 `/schedule`。雲端工作階段方面，請使用 [GitHub Actions](https://code.claude.com/docs/zh-TW/github-actions.md) 或 [GitLab CI/CD](https://code.claude.com/docs/zh-TW/gitlab-ci-cd.md)。

> [tab] Microsoft Foundry
>
> \*\*無法使用：\*\*所有[需要 Claude 訂閱的功能](#features-that-require-a-claude-subscription)，以及[快速模式](https://code.claude.com/docs/zh-TW/fast-mode.md)、[Advisor](https://code.claude.com/docs/zh-TW/advisor.md)、[頻道](https://code.claude.com/docs/zh-TW/channels.md)、[GitLab CI/CD](https://code.claude.com/docs/zh-TW/gitlab-ci-cd.md)、[分析儀表板](https://code.claude.com/docs/zh-TW/analytics.md)、[伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)，以及 [`/design-sync` 與 `/import` 命令](https://code.claude.com/docs/zh-TW/commands#all-commands)。
>
> **部分支援：**
>
> * [Desktop](https://code.claude.com/docs/zh-TW/desktop.md)：僅能透過 [Claude Desktop on 3P](https://claude.com/docs/third-party/claude-desktop/overview)
> * [自動模式](https://code.claude.com/docs/zh-TW/auto-mode-config.md)：僅限 Sonnet 5 或更新版本、Opus 4.7 或更新版本、Haiku 5.5 以及 Fable 模型
> * [跨工作階段訊息傳遞](https://code.claude.com/docs/zh-TW/cross-session-messaging.md)：僅限此機器上您的工作階段之間 <sup>[5](#fn5)</sup>
> * [零資料保留](https://code.claude.com/docs/zh-TW/zero-data-retention.md)：取決於您與 Azure 的合約
>
> \*\*替代方案：\*\*排程方面，請使用 [`/loop`](https://code.claude.com/docs/zh-TW/scheduled-tasks) 取代 `/schedule`。雲端工作階段方面，請使用 [GitHub Actions](https://code.claude.com/docs/zh-TW/github-actions.md)。

> [tab] Anthropic Console
>
> \*\*無法使用：\*\*所有[需要 Claude 訂閱的功能](#features-that-require-a-claude-subscription)。
>
> [因供應商而異的 CLI 功能](#cli-capabilities-that-vary-by-provider)中的所有功能皆可使用，但搭配 Claude Opus 5 或 Claude Opus 4.8 的[快速模式](https://code.claude.com/docs/zh-TW/fast-mode.md)需要[佈建存取權](https://code.claude.com/docs/zh-TW/fast-mode.md#enable-fast-mode-for-your-organization)。您在 claude.ai Team 或 Enterprise 組織中設定的[伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)不會套用到使用 Console API 金鑰進行身分驗證的工作階段。請參閱[平台可用性](https://code.claude.com/docs/zh-TW/server-managed-settings.md#platform-availability)，了解如何涵蓋這些工作階段。
>
> **部分支援：**
>
> * [Desktop](https://code.claude.com/docs/zh-TW/desktop.md)：透過[搭配 Claude API 的 Claude Desktop on 3P](https://claude.com/docs/third-party/claude-desktop/claude-api)

## 按訂閱計畫的可用性

如果您透過 Amazon Bedrock、Google Cloud 的 Agent Platform、Microsoft Foundry 或 Anthropic Console API 金鑰進行驗證，本節不適用於您。當您使用 claude.ai 帳戶登入時，您的計畫決定了下列功能中哪些可用。

在已套用 [HIPAA 設定](https://code.claude.com/docs/zh-TW/hipaa-setup.md)的 Enterprise 組織中，此表格中的部分功能會被關閉。

| 功能 | Pro | Max | Ultra | Team | Enterprise |
| :- | :- | :- | :- | :- | :- |
| [Cloud sessions](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md) | ✓ | ✓ | ✓ | ✓ | ✓ <sup>[6](#fn6)</sup> |
| [雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md) | ✓ | ✓ | ✓ | ✓ | ✓ |
| [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) | ✓ | ✓ | ✓ | 管理員啟用 | 管理員啟用 |
| [Channels](https://code.claude.com/docs/zh-TW/channels.md) | ✓ | ✓ | ✓ | 管理員啟用 | 管理員啟用 |
| [Computer use](https://code.claude.com/docs/zh-TW/computer-use.md) | ✓ | ✓ | ✓ | ✗ | ✗ |
| Dispatch ([Desktop](https://code.claude.com/docs/zh-TW/desktop.md#sessions-from-dispatch)) | ✓ | ✓ | ✓ | ✗ | ✗ |
| [Code Review](https://code.claude.com/docs/zh-TW/code-review.md) | ✗ | ✗ | ✗ | ✓ | ✓ |
| [Artifacts](https://code.claude.com/docs/zh-TW/artifacts.md) | ✓ | ✓ | ✓ | ✓ | ✓ |
| [分析儀表板和貢獻指標](https://code.claude.com/docs/zh-TW/analytics.md) | ✗ | ✗ | ✗ | ✓ | ✓ |
| [Enterprise Analytics API](https://code.claude.com/docs/zh-TW/analytics.md#access-data-programmatically) | ✗ | ✗ | ✗ | ✗ | ✓ |
| [伺服器管理的設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md) | ✗ | ✗ | ✗ | ✓ | ✓ |
| [SSO](https://support.claude.com/en/articles/9266767-what-is-the-team-plan) | ✗ | ✗ | ✗ | ✓ | ✓ |
| SCIM | ✗ | ✗ | ✗ | ✗ | ✓ |
| [Compliance API](https://platform.claude.com/docs/en/api/compliance) | ✗ | ✗ | ✗ | ✗ | ✓ |
| [Zero Data Retention](https://code.claude.com/docs/zh-TW/zero-data-retention.md) | ✗ | ✗ | ✗ | ✗ | ✓ <sup>[7](#fn7)</sup> |

<sup>6</sup> 在 Enterprise 上，需要進階座位或 Chat + Claude Code 座位。請參閱[在雲端上使用 Claude Code](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)。\

<sup>7</sup> 不包含在標準 Enterprise 計畫中。需要 Anthropic 為符合條件的帳戶進行單獨啟用。請參閱 [Zero Data Retention](https://code.claude.com/docs/zh-TW/zero-data-retention.md)。

如需定價和完整計畫比較，請參閱 [Team 計畫](https://support.claude.com/en/articles/9266767-what-is-the-team-plan)和 [Enterprise 計畫](https://support.claude.com/en/articles/9797531-what-is-the-enterprise-plan)。

### Ultra 計畫

Ultra 是 Max 20x 計畫的新名稱，而 Max 是 Max 5x 的新名稱。若要確認您目前使用的計畫，請在 claude.ai 上查看您的訂閱。

在 Claude Code 中，Max 和 Ultra 具有相同的功能，列於[可用性表格](#availability-by-subscription-plan)的 Max 和 Ultra 欄位中。如需用量上限和定價資訊，請參閱 [Claude 定價頁面](https://claude.com/pricing)。

## 模型可用性

如需每個提供者和地區可用的 Claude 模型和內容視窗大小，請參閱[模型配置](https://code.claude.com/docs/zh-TW/model-config.md)和[模型概述](https://platform.claude.com/docs/en/about-claude/models/overview)。Vision、PDF 輸入和擴展思考是模型功能而非 Claude Code 功能，在提供該模型的每個提供者上都有效。[Prompt caching](https://code.claude.com/docs/zh-TW/prompt-caching.md) 在大多數提供者上的運作方式相同；在 Amazon Bedrock 上，支援因模型而異。

## 相關資源

* [企業部署概述](https://code.claude.com/docs/zh-TW/third-party-integrations.md)：比較提供者之間的驗證、計費和地區
* 提供者設定指南：[Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md)、[AWS 上的 Claude Platform](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md)、[Google Cloud 的 Agent Platform](https://code.claude.com/docs/zh-TW/google-vertex-ai.md)、[Microsoft Foundry](https://code.claude.com/docs/zh-TW/microsoft-foundry.md)
* [平台和整合](https://code.claude.com/docs/zh-TW/platforms.md)：Claude Code 執行的位置，包括 CLI、Desktop、IDE 擴充功能、網頁、行動和 CI/CD

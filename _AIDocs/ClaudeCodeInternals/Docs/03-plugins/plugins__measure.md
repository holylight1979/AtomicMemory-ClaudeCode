<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/plugins/measure | lastmod: 2026-10-30 | section: Plugins / Create plugins -->
> 來源：https://code.claude.com/docs/zh-TW/plugins/measure（官方 zh-TW，lastmod 2026-10-30）｜分類：Plugins › Create plugins｜EN 摘要：Measure a Claude Code plugin's token cost, find out whether people still use it, and pick the telemetry events for organization-wide plugin questions.

# 測量外掛程式成本和使用情況

> 測量 Claude Code 外掛程式的權杖成本，了解人們是否仍在使用它，並為組織範圍的外掛程式問題選擇遙測事件。

啟用外掛程式的每個工作階段都會在 Claude 的上下文中包含其技能、代理和命令的名稱和描述，這些權杖會計入使用者的使用量，無論外掛程式是否被使用。本頁面說明如何查看外掛程式的該數字、如果您維護外掛程式如何減少它，以及使用情況在何處顯示，以便您可以判斷外掛程式是否仍在被使用。

本頁面適用於外掛程式作者和維護者。如果您為組織管理 Claude Code，[跨機隊測量](#measure-across-a-fleet)涵蓋了每台機器上的相同問題。

> [!NOTE]
>
> 這些情況在其他頁面上涵蓋：
>
> * **測試外掛程式如何可靠地改變 Claude 的行為**：請參閱[使用評估測試外掛程式](https://code.claude.com/docs/zh-TW/plugin-evals.md)
> * **修剪您自己工作階段的上下文**：請參閱[管理已安裝的外掛程式](https://code.claude.com/docs/zh-TW/plugins/install.md#manage-installed-plugins)和[上下文視窗](https://code.claude.com/docs/zh-TW/context-window.md)頁面

從[測量外掛程式的成本](#measure-what-a-plugin-costs)開始。

## 測量外掛程式的成本

要查看外掛程式對 Claude 上下文的影響，請使用外掛程式的名稱執行 [`claude plugin details`](https://code.claude.com/docs/zh-TW/plugins/cli-reference#plugin-details)。您在 shell 中執行它，而不是在執行中的 Claude Code 工作階段的提示符處。外掛程式必須被載入：已安裝、在技能目錄中，或在同一命令中使用 `--plugin-dir` 傳遞，如 `claude --plugin-dir ./formatter plugin details formatter`。

此範例讀取一個名為 `formatter` 的已安裝外掛程式，該外掛程式有兩個技能、一個命令、一個代理、一個 hook 和一個 MCP 伺服器：

```bash theme={null}
claude plugin details formatter
```

```text theme={null}
formatter 1.0.0
  Description: Formats and lints code on save
  Source: formatter@my-marketplace

Component inventory
  Skills (3)  format-all, format-code, lint-fix
  Agents (1)  style-reviewer
  Hooks (1)  PostToolUse  (harness-only — no model context cost)
  MCP servers (1)  formatter-tools  (tool schemas resolved at runtime; not counted)
  LSP servers (0)

Projected token cost
  Always-on:   ~146 tok   added to every session

Per-component (rounded)
  component       always-on  on-invoke
  format-code           ~40        ~30
  lint-fix              ~50        ~30
  style-reviewer        ~40        ~40
  format-all           < 20        ~30

  On-invoke cost is paid each time a skill or agent fires.
  Token counts are estimates and may differ from actual usage.
```

輸出的每個部分回答了不同的問題：

* **Component inventory**：Claude Code 在外掛程式中找到的內容。命令與技能一起計算，因此 `format-all` 出現在 `Skills` 下。Hooks 和 MCP 伺服器沒有成本估計和每個元件行；要查看外掛程式的 MCP 工具添加了什麼，請在啟用外掛程式的工作階段中執行 `/context`，並閱讀 `MCP tools` 類別。
* **Always-on**：外掛程式的技能、代理和命令的名稱和描述添加到啟用外掛程式的每個工作階段的權杖，無論是否有任何內容執行。這是每個使用者都會承載的數字，也是要減少的數字。
* **Per-component**：每一行將一個技能、代理或命令分為其 always-on 份額和其 on-invoke 成本，後者是僅在該元件執行時載入的主體。使用 always-on 列來找出哪個元件貢獻最多。

### 降低 always-on 數字

如果您維護外掛程式，這些更改會減少它對每個工作階段的添加。如果您只是使用它，您的選項是禁用或卸載它；請參閱[管理已安裝的外掛程式](https://code.claude.com/docs/zh-TW/plugins/install.md#manage-installed-plugins)。

always-on 數字計算每個元件的名稱加上其 `description` 和 `when_to_use` frontmatter。要降低它：

* 縮短技能和代理描述。
* 分割大型外掛程式，以便使用者只安裝他們需要的元件。

技能的描述也是 Claude 匹配請求的內容，因此較短的描述可以阻止技能觸發。修剪描述後，使用評估套件中的 [`tool_used: Skill` grader](https://code.claude.com/docs/zh-TW/plugin-evals#create-your-first-eval-suite) 檢查觸發。

有關每個元件類型的貢獻，請參閱[外掛程式元件](https://code.claude.com/docs/zh-TW/plugins/components.md)。

### 安裝前向使用者顯示的成本

官方市場中的外掛程式在安裝前向使用者顯示其成本。在 `/plugin` 中，當使用者瀏覽市場的外掛程式列表並選擇外掛程式時，詳細資訊窗格會顯示一個**Context cost**部分，其中包含 `Every turn:` 行和 `When invoked:` 行。當 always-on 數字為 2,000 個權杖或更多時，`Every turn:` 行會顯示突出顯示。

您自己市場中的外掛程式沒有**Context cost**部分。

## 檢查外掛程式是否被使用

Claude Code 不會向其作者報告外掛程式的使用情況。使用情況記錄在安裝外掛程式的每個人的機器上，因此您可以了解的內容取決於您與這些人的關係：

* **您為其組織管理 Claude Code**：OpenTelemetry 事件和 Analytics API 計算每台機器上的安裝和技能啟動。請參閱[跨機隊測量](#measure-across-a-fleet)。
* **他們是您可以詢問的隊友**：每個使用者自己的 Claude Code 在四個地方向他們顯示他們是否仍在使用外掛程式：[`/plugin` 面板](#not-used-recently-in-/plugin)、[`/skill-doctor`](#find-skills-that-never-run)、[`/doctor`](#unused-plugins-in-/doctor) 和 [`/usage`](#usage-share-in-/usage)。所有四個都是使用者在自己機器上的工作階段中在 Claude Code 提示符處執行的命令。
* **都不是**：您沒有來自 Claude Code 的該外掛程式的使用信號。

如需了解 Anthropic 目錄中列出的外掛程式的使用情況，請參閱 claude.com 上的[追蹤已發佈的外掛程式使用情況](https://claude.com/docs/connectors/building/after-publishing#track-published-plugin-usage)。

### `/plugin` 中最近未使用

在 `/plugin` 的**Installed**標籤上，使用者從市場安裝的外掛程式在至少 14 天和 10 個工作階段未使用後，會移到**Not used recently**標題下。外掛程式的詳細資訊也會顯示 `Last used:` 行。有關使用者對該標題和行的操作，請參閱[尋找您不再使用的外掛程式](https://code.claude.com/docs/zh-TW/plugins/install.md#find-plugins-you-no-longer-use)。

**Not used recently**標題永遠不會出現在：

* 使用 `--plugin-dir` 或從技能目錄載入的外掛程式
* 通過受管設定啟用或從[種子目錄](https://code.claude.com/docs/zh-TW/plugins/org.md#seed-containers-and-ci)掛載的外掛程式
* 包含主題、輸出樣式、監視器或工作流的外掛程式，因為這些在沒有追蹤的啟動的情況下使用

外掛程式的[語言伺服器](https://code.claude.com/docs/zh-TW/plugins/components.md#lsp-servers)在傳遞診斷或回答代碼導航請求時計為已使用，因此伺服器在您的工作階段中活躍的 LSP 外掛程式不會列為未使用。

當使用者的組織設定 [`strictKnownMarketplaces`](https://code.claude.com/docs/zh-TW/plugins/org#restrict-what-users-can-install) 時，標題和 `Last used:` 行都不會出現。

### 尋找永遠不執行的技能

執行 `/skill-doctor` 以查看您的每個技能的成本以及它被使用的頻率。它標記在 Claude 的技能列表中但從未被啟動的技能，包括來自外掛程式的技能。

在互動式工作階段中，報告在 `/plugin` 管理器的**Stats**標籤中打開。請參閱[尋找未使用的技能](https://code.claude.com/docs/zh-TW/skills.md#find-unused-skills)以了解報告涵蓋的內容以及它在何處可用。

### `/doctor` 中未使用的外掛程式

`/doctor` 檢查列出每個使用者安裝的技能、MCP 伺服器和外掛程式，並建議禁用未使用的外掛程式。請參閱[命令參考中的 `/doctor`](https://code.claude.com/docs/zh-TW/commands#all-commands)。

### `/usage` 中的使用情況份額

在 Pro、Max、Ultra、Team 或 Enterprise 方案上，`/usage` 細分會將最近的使用情況歸因於 skill、subagent、外掛程式和 MCP 伺服器，作為總數的份額。請參閱[使用 `/usage` 命令](https://code.claude.com/docs/zh-TW/costs#using-the-/usage-command)。

## 跨機隊測量

如果您為組織管理 Claude Code，您可以從以下任一來源跨每台機器測量外掛程式成本和使用情況：

* **OpenTelemetry 事件**：Claude Code 在您[配置匯出器](https://code.claude.com/docs/zh-TW/monitoring-usage.md)後將這些匯出到您自己的後端。請參閱[外掛程式安裝和使用的 OpenTelemetry 事件](#pick-the-opentelemetry-event-for-each-question)。
* **Analytics API**：由 Anthropic 的記錄提供，無需匯出器。請參閱[查詢 Analytics API](#query-the-analytics-api)。

### 外掛程式安裝和使用的 OpenTelemetry 事件

這些 OpenTelemetry 事件和屬性從您的後端回答每個外掛程式問題：

| 問題 | OpenTelemetry 事件或屬性 |
| :- | :- |
| 安裝了哪些外掛程式，來自何處 | [`claude_code.plugin_installed`](https://code.claude.com/docs/zh-TW/monitoring-usage#plugin-installed-event)，每次安裝一個 |
| 哪些外掛程式在多少個工作階段中活躍 | [`claude_code.plugin_loaded`](https://code.claude.com/docs/zh-TW/monitoring-usage#plugin-loaded-event)，工作階段開始時每個啟用的外掛程式一個 |
| 哪些技能啟動，哪個外掛程式擁有它們 | [`claude_code.skill_activated`](https://code.claude.com/docs/zh-TW/monitoring-usage#skill-activated-event)，帶有外掛程式技能的 `plugin.name` 和 `marketplace.name` |
| 外掛程式的 hooks 報告什麼 | [`claude_code.hook_plugin_metrics`](https://code.claude.com/docs/zh-TW/monitoring-usage#hook-plugin-metrics-event)，僅針對官方市場外掛程式中的 hooks 發出 |
| 外掛程式在 API 支出中的成本 | [成本計數器](https://code.claude.com/docs/zh-TW/monitoring-usage.md#cost-counter)上的 `plugin.name` 和 `marketplace.name`，在活躍技能或子代理屬於外掛程式時設定 |

### 後端中的編輯外掛程式名稱

來自官方市場的外掛程式將其外掛程式名稱和市場名稱逐字報告到您的後端。所有其他外掛程式的名稱預設被編輯或省略，包括來自您組織自己市場的外掛程式。外掛程式的[信任層級](https://code.claude.com/docs/zh-TW/plugins/security.md#find-plugins-in-telemetry)決定了哪個。

要在某些事件上獲取真實名稱，請在匯出遙測的機器上將 [`OTEL_LOG_TOOL_DETAILS`](https://code.claude.com/docs/zh-TW/monitoring-usage#common-configuration-variables) 環境變數設定為 `1`，例如在配置匯出器的相同[受管設定](https://code.claude.com/docs/zh-TW/monitoring-usage.md#administrator-configuration)的 `env` 塊中：

| 事件 | 預設 | 使用 `OTEL_LOG_TOOL_DETAILS=1` |
| :- | :- | :- |
| `plugin_loaded` | `plugin.name` 和 `marketplace.name` 是字面字符串 `third-party` | 真實名稱 |
| `plugin_installed`、`skill_activated` | `plugin.name` 和 `marketplace.name` 省略；在 `skill_activated` 上，`skill.name` 是 `custom_skill` | 真實名稱 |
| 成本計數器 | `plugin.name` 是 `third-party`；`marketplace.name` 不存在 | 真實 `plugin.name`；`marketplace.name` 仍然不存在 |

在 `plugin_loaded` 上，`plugin_id_hash` 仍然預設識別每個外掛程式，因此您可以計算不同的第三方外掛程式。

### 查詢 Analytics API

在 Enterprise 計劃上，Analytics API 從 Anthropic 的記錄中回答「我的組織安裝和啟動哪些外掛程式」，無需匯出器。[`GET /v1/organizations/analytics/plugins`](https://platform.claude.com/docs/en/api/admin/analytics/plugins/list) 返回跨 Claude Code 和 Cowork 的每個外掛程式、每天的安裝和啟動計數，您可以按使用者、RBAC 群組或產品進行分組。

到達 Anthropic 而沒有外掛程式名稱的外掛程式活動出現在一個聚合 `third-party` 行中。[在遙測中尋找外掛程式](https://code.claude.com/docs/zh-TW/plugins/security.md#find-plugins-in-telemetry)說明 Claude Code 按名稱報告的外掛程式。

使用具有 `read:analytics` 範圍的 API 金鑰驗證請求，主要所有者按[以程式設計方式存取資料](https://code.claude.com/docs/zh-TW/analytics.md#access-data-programmatically)下所述建立。

有關參數和回應欄位，請參閱[端點參考](https://platform.claude.com/docs/en/api/admin/analytics/plugins/list)。

## 後續步驟

* [使用評估測試外掛程式](https://code.claude.com/docs/zh-TW/plugin-evals.md)：測量外掛程式如何可靠地引導 Claude，而不僅僅是它的成本
* [降低 always-on 數字](#lower-the-always-on-figure)：在外掛程式中更改什麼以減少其每轉成本
* [外掛程式安全性和信任](https://code.claude.com/docs/zh-TW/plugins/security.md#find-plugins-in-telemetry)：哪些遙測欄位攜帶外掛程式名稱以及何時被編輯
* [監視使用情況](https://code.claude.com/docs/zh-TW/monitoring-usage.md)：完整的 OpenTelemetry 事件參考

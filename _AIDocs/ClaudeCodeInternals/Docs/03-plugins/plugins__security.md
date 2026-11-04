<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/plugins/security | lastmod: 2026-10-28 | section: Plugins / Use plugins -->
> 來源：https://code.claude.com/docs/zh-TW/plugins/security（官方 zh-TW，lastmod 2026-10-28）｜分類：Plugins › Use plugins｜EN 摘要：Decide whether to trust a plugin before you install it, from what a plugin can do on your machine to how to review one and remove it.

# Plugin 安全性和信任

> 在安裝 plugin 之前決定是否信任它，從 plugin 在您的機器上可以執行的操作，到如何檢查它和移除它。

您安裝的 Claude Code plugin 可以使用您的使用者權限在您的機器上執行任意程式碼。

您從一個 marketplace 安裝 plugin，marketplace 是 Claude Code 從中取得它的目錄。某些 marketplace 名稱是[為 Anthropic 自己的 marketplace 保留的](#marketplace-tiers)，其他所有 marketplace 都是第三方的。Marketplace 的名稱告訴您誰發佈了該目錄，而不是其中每個 plugin 的功能，所以無論它來自哪個 marketplace，都要[在安裝前檢查 plugin](#review-a-plugin-before-you-install)。

如果您正在決定是否安裝 plugin，或者您在您的團隊可以使用工具之前檢查它們，請閱讀此頁面。

> [!NOTE]
>
> 這些情況在其他頁面上涵蓋：
>
> * **Claude Code 自己的安全模型**：請參閱[安全性](https://code.claude.com/docs/zh-TW/security.md)
> * **限制或要求組織的 plugin**：請參閱[為您的組織管理 plugin](https://code.claude.com/docs/zh-TW/plugins/org.md)
> * **`security-guidance` 或 `claude-security` plugin**：此頁面不是關於它們的。請參閱[`security-guidance`](https://code.claude.com/docs/zh-TW/security-guidance) 和 [`claude-security`](https://code.claude.com/docs/zh-TW/claude-security)

從[plugin 可以執行的操作](#understand-what-a-plugin-can-do)和[哪些 marketplace 是 Anthropic 的](#marketplace-tiers)開始，然後[在安裝前檢查 plugin](#review-a-plugin-before-you-install)。

## 了解 plugin 可以執行的操作

Plugin 可以攜帶在您的機器上使用您的使用者權限執行程式碼的內容，以及進入 Claude 上下文作為指令的內容，所以[在安裝前檢查 plugin](#review-a-plugin-before-you-install)。以下是已安裝的 plugin 可以執行的操作：

* **Hooks**：plugin 的 [hooks](https://code.claude.com/docs/zh-TW/hooks.md) 在 Claude Code 生命週期中的特定點（例如工具呼叫之前或之後）作為 shell 命令執行。
* **Monitors**：plugin 的 [monitors](https://code.claude.com/docs/zh-TW/plugins/components.md#monitors) 作為背景 shell 命令執行，Claude Code 會在工作階段開始時、您重新載入 plugin 時，或指定的 skill 首次執行時自行啟動它們。
* **Mods**：plugin 的 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md) 在 Claude Code 內使用您的權限執行 JavaScript。要在安裝前列出 mod 執行的操作，請參閱[決定是否信任 mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md#decide-whether-to-trust-a-mod)。
* **MCP 和 LSP 伺服器**：Claude Code 連接到已啟用的 plugin 聲明的 [MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md)，並為 Claude 提供它們的工具。Stdio MCP 伺服器作為 Claude Code 在您的機器上啟動的程序執行。Claude Code 也啟動 plugin 聲明的語言伺服器。
* **`bin/` 目錄**：Claude Code 將每個已啟用的 plugin 的 `bin/` 目錄新增到 Bash 工具的 shell 的 `PATH`，所以 Claude 的 Bash 命令可以執行那裡的任何可執行檔。Claude 使用 [PowerShell 工具](https://code.claude.com/docs/zh-TW/tools-reference.md#powershell-tool)執行的命令，在[沙箱](https://code.claude.com/docs/zh-TW/sandboxing.md)外執行時，其 `PATH` 會包含這些目錄；在沙箱內執行時則不會。
* **Skills、commands 和 agents**：這些進入 Claude 的上下文作為指令，所以它們影響 Claude 對它已有的工具執行的操作。
* **更新**：當您安裝 plugin 的 marketplace 啟用自動更新時，Claude Code 在背景更新該 plugin，所以您檢查的檔案可能會在磁碟上變更。[何時自動更新執行](https://code.claude.com/docs/zh-TW/plugins/loading.md#when-auto-update-runs)有時間安排。要按 marketplace 開啟或關閉自動更新，請參閱[保持 plugin 更新](https://code.claude.com/docs/zh-TW/plugins/install.md#keep-plugins-updated)。

Claude Code 的[權限規則](https://code.claude.com/docs/zh-TW/permissions.md)和[沙箱](https://code.claude.com/docs/zh-TW/sandboxing.md)涵蓋 Claude 進行的工具呼叫，而不是 plugin 自己執行的程式碼：

* **Hooks、monitors 和伺服器程序**：命令 hooks 和 monitors 是使用您的完整使用者權限執行的 shell 命令。Claude Code 在沙箱外執行 hooks、monitors、MCP 伺服器、LSP 伺服器，以及 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md#what-a-mod-can-reach) 啟動的程序。
* **Claude 的工具呼叫**：對 plugin 的 MCP 工具之一的呼叫，以及執行 plugin 的 `bin/` 中的可執行檔的 Bash 命令，都是工具呼叫，所以您的權限規則適用於它們。如需 mod 可以對工具呼叫執行的操作，請參閱[決定是否信任 mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md#decide-whether-to-trust-a-mod)。

安裝 plugin 也會啟用它，除非其 manifest 或 marketplace 項目設定了 [`defaultEnabled: false`](https://code.claude.com/docs/zh-TW/plugins/install#choose-an-install-scope)，且您自己還沒有啟用它。

要移除您不再信任的 plugin，請參閱[移除您不再信任的 plugin](#remove-a-plugin-you-no-longer-trust)。

## 按名稱識別 Anthropic 的 marketplace

Marketplace 的名稱將其放在三個層級之一中：官方、社群或第三方。Claude Code 僅接受來自 `github.com/anthropics/` 儲存庫的官方和社群名稱用於 marketplace，所以第三方 marketplace 無法將自己呈現為 Anthropic 的。同事或您的組織發佈的 marketplace 是第三方的。

該表列出了每個層級中的 marketplace 名稱：

| 層級 | 哪些 marketplace |
| :- | :- |
| 官方 | [官方 marketplace 名稱](#official-marketplace-names)，例如 `claude-plugins-official` |
| 社群 | `claude-community`、`claude-plugins-community` 和 `healthcare` |
| 第三方 | 所有其他 marketplace |

其中 `claude-community` 目錄將 plugin 固定到提交 SHA，幾乎每個項目都這樣做，Claude Code 拒絕安裝不同的提交。

### 官方 marketplace 名稱

這些 marketplace 名稱組成官方層級：

* `claude-plugins-official`
* `claude-code-marketplace`
* `claude-code-plugins`
* `anthropic-marketplace`
* `anthropic-plugins`
* `agent-skills`
* `anthropic-agent-skills`
* `life-sciences`
* `knowledge-work-plugins`
* `claude-for-legal`
* `claude-for-financial-services`
* `financial-services-plugins`
* `first-party-plugins`
* `claude-tag-plugins`

有關官方和社群 marketplace 的差異以及在哪裡瀏覽每個 marketplace 列出的內容，請參閱 [Anthropic 的 marketplace](https://code.claude.com/docs/zh-TW/plugins/anthropic-marketplaces.md)。

## 在安裝前檢查 plugin

在安裝 plugin 之前，查看它新增的內容以及它來自何處。

**1. 檢查 marketplace 的來源**

在您的 shell 中，執行 `claude plugin marketplace list` 以列印每個 marketplace 的新增來源，例如 GitHub 儲存庫或目錄。

**2. 閱讀詳細資訊窗格**

在 Claude Code 工作階段中，執行 `/plugin` 並選擇 plugin。詳細資訊窗格顯示一個**將安裝**部分，列出 plugin 的命令、agents、skills、hooks 和 MCP 及 LSP 伺服器。對於 Anthropic 沒有已發佈元件資料的 plugin，該部分顯示 marketplace 項目聲明的內容，或一個注意：`Components will be discovered at installation` 用於儲存在 marketplace 內的 plugin，或 `Component summary not available for remote plugin` 用於從其他地方取得的 plugin。

**3. 閱讀 plugin 的來源**

在詳細資訊窗格中，選擇安裝選項下方的**開啟首頁**或**在 GitHub 上檢視**。如果窗格不提供任何一個，請開啟您在第一步中找到的 marketplace 儲存庫。在那裡找到 plugin 的目錄。**將安裝**部分顯示 hook 存在但不顯示它執行的內容，所以請在 plugin 的目錄中閱讀這些檔案：

* **`hooks/hooks.json`**：每個 hook 執行的命令
* **`.mcp.json`**：每個伺服器的命令或 URL
* **`bin/`**：目錄中的每個檔案

**4. 列出 plugin 包含的內容**

複製保存 plugin 目錄的儲存庫，然後在您的 shell 中執行 `claude --plugin-dir <plugin directory> plugin details <plugin name>` 以查看 Claude Code 在其中找到的內容。該命令讀取 plugin 的檔案而不啟動工作階段，並列印一個 `Component inventory` 列出 plugin 的 skills 和 commands、agents、hooks（每個 hook 的事件）以及 MCP 和 LSP 伺服器。

安裝 plugin 後，在您的 shell 中執行 `claude plugin details <plugin name>` 以為 `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/` 下的已安裝副本列印相同的 `Component inventory`。

### 移除您不再信任的 plugin

在您的 shell 中，使用您安裝它的 `--scope` 執行 [`claude plugin uninstall <plugin>`](https://code.claude.com/docs/zh-TW/plugins/cli-reference#plugin-uninstall)。然後檢查卸載移除了什麼以及它留下了什麼：

* **持久資料**：預設情況下，當那是最後一個安裝 plugin 的範圍時，卸載也會刪除 plugin 的持久資料目錄。對於 `--keep-data` 和其他它保留的情況，請參閱 [plugin uninstall](https://code.claude.com/docs/zh-TW/plugins/cli-reference.md#plugin-uninstall)。
* **快取檔案**：plugin 的檔案保留在 `~/.claude/plugins/cache/` 下的磁碟上 14 天，然後[背景掃描移除它們](https://code.claude.com/docs/zh-TW/plugins/loading.md#cleanup-of-previous-versions)。卸載您的最後一個 plugin 後，孤立目錄保留到您安裝另一個。要立即刪除檔案，請自己移除 `~/.claude/plugins/cache/<marketplace>/<plugin>/` 下的 plugin 目錄。
* **Marketplace**：如果您也不信任 marketplace 的擁有者，[移除 marketplace](https://code.claude.com/docs/zh-TW/plugins/install.md#manage-marketplaces) 也會卸載您從它安裝的每個 plugin。

## 識別 Claude Code 何時拒絕或警告

您從 `/plugin` 中的**探索**或**Marketplace** 標籤開啟的詳細資訊窗格為每個 plugin 顯示相同的信任警告。Claude Code 在[不受信任的 marketplace 來源和失敗的完整性檢查](#untrusted-marketplace-sources-and-failed-integrity-checks)下的情況下拒絕而不是警告。

### 安裝前的信任警告

警告讀起來相同，無論 plugin 來自哪個 marketplace：

```text theme={null}
Make sure you trust a plugin before installing, updating, or using it. Anthropic does not control what MCP servers, files, or other software are included in plugins and cannot verify that they will work as intended or that they won't change. See each plugin's homepage for more information.
```

如果您的組織在[受管設定](https://code.claude.com/docs/zh-TW/plugins/org.md)中設定了 `pluginTrustMessage`，Claude Code 會將該文字附加到警告中。

### 不受信任的 marketplace 來源和失敗的完整性檢查

Claude Code 在這些情況下拒絕載入 marketplace 或安裝 plugin，每種情況都有自己的錯誤訊息：

* **不受信任的 marketplace 來源**：當 marketplace 使用官方或社群名稱但其來源在 `github.com/anthropics/` 之外時，Claude Code 停止載入 marketplace 和您從它安裝的 plugin。錯誤是[Marketplace is registered from an untrusted source](https://code.claude.com/docs/zh-TW/errors.md#marketplace-is-registered-from-an-untrusted-source)。
* **存檔完整性**：當 marketplace 項目將 [`archive` 來源](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference#archive-plugin-source)固定到 `sha256` 摘要，且下載的檔案的摘要不符合時，Claude Code 拒絕安裝。錯誤是[Plugin archive integrity check failed](https://code.claude.com/docs/zh-TW/errors.md#plugin-archive-integrity-check-failed)。

`sha256` 固定與社群目錄的提交 SHA 固定分開，後者選擇要檢出的 git 提交。

## 為您的組織強制執行 plugin 控制

使用[受管設定](https://code.claude.com/docs/zh-TW/plugins/org.md)，管理員可以強制執行這些 plugin 控制：

* 允許清單或封鎖清單 marketplace 來源
* 強制啟用 plugin
* 關閉 `--plugin-dir` 和 `--plugin-url` 旗標以及 `CLAUDE_CODE_PLUGIN_DIRS` 變數
* 將 hooks 限制為來自受管設定和強制啟用的 plugin 的 hooks
* 停止成員 claude.ai 帳戶中的 plugin 在 Claude Code 中載入，使用 [`syncClaudeAiPlugins`](https://code.claude.com/docs/zh-TW/plugins/org#control-matrix)

[控制矩陣](https://code.claude.com/docs/zh-TW/plugins/org.md#control-matrix)說明每個金鑰執行和不涵蓋的內容。

## 在遙測中尋找 plugin

如果您的組織將 Claude Code 的 [OpenTelemetry 事件](https://code.claude.com/docs/zh-TW/monitoring-usage.md)匯出到其自己的後端，[marketplace 層級](#marketplace-tiers)決定哪些 plugin 名稱出現在那裡：

* **[Plugin loaded 事件](https://code.claude.com/docs/zh-TW/monitoring-usage.md#plugin-loaded-event)**：事件按原樣報告官方層級的 plugin 和 marketplace 名稱。對於社群和第三方層級，`plugin.name` 和 `marketplace.name` 是字面字串 `third-party`，除非您設定 `OTEL_LOG_TOOL_DETAILS=1`。
* **Plugin 範圍**：載入事件的 `plugin.scope` 仍然報告 plugin 來自何處，例如 `org` 用於您的受管設定啟用的 plugin 或 `user-local` 用於任何其他第三方 plugin。[Plugin loaded 事件](https://code.claude.com/docs/zh-TW/monitoring-usage.md#plugin-loaded-event)列出每個值。
* **[Plugin installed 事件](https://code.claude.com/docs/zh-TW/monitoring-usage.md#plugin-installed-event)**：除非您設定 `OTEL_LOG_TOOL_DETAILS=1`，否則事件會省略非官方 plugin 的名稱欄位，而不是報告 `third-party`。
* **[Claude Code Analytics API](https://platform.claude.com/docs/en/api/admin/analytics/plugins/list)**：Claude Code 按名稱報告官方和社群層級的 plugin，並將所有其他 plugin 報告為 `third-party`。

## 後續步驟

* [為您的組織管理 plugin](https://code.claude.com/docs/zh-TW/plugins/org.md)：限制使用者可以安裝的 marketplace 並要求您信任的 plugin
* [安裝和管理 plugin](https://code.claude.com/docs/zh-TW/plugins/install.md)：在選擇範圍之前檢查 plugin 的詳細資訊窗格
* [Anthropic 的 marketplace](https://code.claude.com/docs/zh-TW/plugins/anthropic-marketplaces.md)：哪些 marketplace 名稱是 Anthropic 的
* [安全性](https://code.claude.com/docs/zh-TW/security.md)：Claude Code 自己的安全模型

<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/plugins/anthropic-marketplaces | lastmod: 2026-10-28 | section: Plugins / Use plugins -->
> 來源：https://code.claude.com/docs/zh-TW/plugins/anthropic-marketplaces（官方 zh-TW，lastmod 2026-10-28）｜分類：Plugins › Use plugins｜EN 摘要：Anthropic's official and community plugin marketplaces for Claude Code: their names, repositories, how you add each, and where to browse their plugins.

# Anthropic 的市集

> Anthropic 為 Claude Code 提供的官方與社群外掛市集：它們的名稱、儲存庫、如何新增每個市集，以及在哪裡瀏覽其中的外掛。

Anthropic 為 Claude Code 發佈兩個通用外掛市集：[官方](https://github.com/anthropics/claude-plugins-official)和[社群](https://github.com/anthropics/claude-plugins-community)。每個市集都是位於其自身 GitHub 儲存庫中的外掛目錄。當您在 Claude Code 工作階段中從其中一個市集安裝外掛時，需在 `@` 後輸入市集的名稱，如 `/plugin install commit-commands@claude-plugins-official`。

使用此頁面來區分這兩個市集，並找到可檢查官方市集是否包含特定外掛的位置。

> [!NOTE]
>
> 這些情況在其他頁面上涵蓋：
>
> * **如何安裝 plugin**：請參閱[安裝 plugin](https://code.claude.com/docs/zh-TW/plugins/install.md)
> * **安裝失敗**：請參閱[plugin 疑難排解](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md)

前往您需要的頁面部分：

* 若要按儲存庫、市集名稱和取得方式區分這兩個市集，請參閱 [Anthropic 的市集](#anthropic’s-marketplaces)。
* 若要在官方 marketplace 中尋找 plugin，請參閱[在官方 marketplace 中尋找 plugin](#find-plugins-in-the-official-marketplace)。

## Anthropic 的 marketplace

市集是儲存庫在其 `.claude-plugin/marketplace.json` 檔案中定義的外掛目錄。官方和社群市集各自來自其自身的 GitHub 儲存庫。Anthropic 也發佈主題特定的市集，例如 `anthropics/skills` 和 `anthropics/knowledge-work-plugins`，您可以在 Claude Code 工作階段中使用 `/plugin marketplace add <owner>/<repo>` 新增。

此表格提供每個 marketplace 的儲存庫和 marketplace 名稱，這是您從該 marketplace 安裝 plugin 時在 `@` 後輸入的內容。社群 marketplace 的名稱是 `claude-community`，而不是其儲存庫名稱。

| | 官方 | 社群 |
| :- | :- | :- |
| 儲存庫 | [`anthropics/claude-plugins-official`](https://github.com/anthropics/claude-plugins-official) | [`anthropics/claude-plugins-community`](https://github.com/anthropics/claude-plugins-community) |
| 市集名稱 | `claude-plugins-official` | `claude-community` |
| 其中包含的內容 | Anthropic 維護的外掛，加上來自合作夥伴和其他作者的外掛 | 第三方外掛，由其作者提交給 Anthropic |
| 取得方式 | Claude Code 在您第一次啟動互動式終端機工作階段時新增它，除非[受管原則](https://code.claude.com/docs/zh-TW/plugins/org.md#allow-the-official-marketplace-and-your-own)或 `CLAUDE_CODE_DISABLE_OFFICIAL_MARKETPLACE_AUTOINSTALL` 阻止它。如果遺失，請參閱 [Marketplace `claude-plugins-official` not found](https://code.claude.com/docs/zh-TW/plugins/troubleshooting#marketplace-claude-plugins-official-not-found) | 您在 Claude Code 工作階段中使用 `/plugin marketplace add anthropics/claude-plugins-community` 新增它 |

如果您編寫了 plugin 並希望其他人安裝它，請參閱[發佈 plugin](https://code.claude.com/docs/zh-TW/plugins/publish.md)，其涵蓋您自己的 marketplace 和提交到 Anthropic 的目錄。

### 已棄用的 `claude-code-plugins` 市集

> [!WARNING]
>
> `anthropics/claude-code` 中的 `claude-code-plugins` 市集已棄用。若要新增外掛，請在您的 shell 中執行 `claude plugin install <plugin>@claude-plugins-official`，並略過任何執行 `/plugin marketplace add anthropics/claude-code` 的教學步驟。

除非您安裝了下列兩個外掛之一，否則您可以保留 `claude-code-plugins` 外掛和該市集原狀。它們會從 `claude-plugins-official` 儲存庫更新。

* **`ralph-wiggum`**：此外掛現在是 `ralph-loop`，其命令以 `/ralph-loop:` 開頭。如果這些命令無法使用，請在您的 shell 中執行 `claude plugin install ralph-loop@claude-plugins-official`。
* **`claude-opus-4-5-migration`**：此外掛已停用，因此請在您的 shell 中執行 `claude plugin uninstall claude-opus-4-5-migration@claude-code-plugins` 將其移除。

如果有任何其他外掛停止運作，請參閱[外掛已安裝但無法運作](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#plugin-installed-but-not-working)。

## 在官方 marketplace 中尋找 plugin

官方 marketplace `claude-plugins-official` 是 Claude Code 為您新增的。它列出的大部分內容來自合作夥伴和其他作者，而不是來自 Anthropic：工具供應商發佈將 Claude Code 連接到其服務的 plugin，Anthropic 維護一個較小的自有集合，例如 `commit-commands`、`code-review`、`feature-dev` 和[語言伺服器 plugin](https://code.claude.com/docs/zh-TW/plugins/code-intelligence.md)。目錄經常變化，所以此頁面不列出它。

若要查看其中的內容，請在 Claude Code 工作階段中使用 `/plugin` 的 **Discover** 標籤（您可以搜尋），或在網路上瀏覽 [Claude Marketplace](https://claude.com/marketplace/plugins)。

## 從 Anthropic 的 marketplace 瀏覽和安裝

您可以在 Claude Code、網路或 GitHub 上搜尋 Anthropic 的 marketplace 中的 plugin：

* **在 Claude Code 中，透過瀏覽**：在互動式工作階段中執行 `/plugin`。其 **Discover** 標籤列出您的 marketplace 中的 plugin。
* **在 Claude Code 中，按名稱**：在工作階段中執行 `/plugin install <name>`，它會在您的 marketplace 中查詢名稱。如果 plugin 在其中之一，其詳細資訊會在 `/plugin` 面板中開啟，在您選擇[安裝範圍](https://code.claude.com/docs/zh-TW/plugins/install.md#install-a-plugin)並確認之前，不會安裝任何內容。如果不在，您會看到 `Plugin "<name>" not found in any marketplace`。
* **在網路上**：在 [Claude Marketplace](https://claude.com/marketplace/plugins) 上搜尋完整目錄，其顯示安裝計數並標記某些 plugin 為 **Anthropic verified**。
* **在 GitHub 上**：在 marketplace 的儲存庫中開啟 `.claude-plugin/marketplace.json`，例如 [`anthropics/claude-plugins-official`](https://github.com/anthropics/claude-plugins-official)。該檔案就是目錄本身。

Anthropic 的目錄與這些 marketplace 分開。目錄是 claude.ai 上的目錄。您從 claude.ai 上的目錄新增的 plugin 透過[帳戶同步](https://code.claude.com/docs/zh-TW/plugins/loading.md#synced-plugins)到達 Claude Code。若要在那裡列出您自己的 plugin，請參閱[提交至 Anthropic 的目錄](https://code.claude.com/docs/zh-TW/plugins/publish.md#submit-to-anthropics-directory)。

若要從桌面應用程式或指令碼安裝，或查看雲端工作階段載入的內容，請參閱[安裝 plugin](https://code.claude.com/docs/zh-TW/plugins/install.md)。

### 新增社群市集

社群市集在您新增之前不會註冊。在 Claude Code 工作階段中，執行 `/plugin marketplace add anthropics/claude-plugins-community`，然後使用 `@claude-community` 尾碼安裝。

如果 `claude-plugins-official` 不在 `/plugin` 的 **Marketplaces** 標籤上，使用 `/plugin marketplace add anthropics/claude-plugins-official` 以相同方式新增它。

如需 `not found` 錯誤和無法新增的 marketplace，請參閱[plugin 疑難排解](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#install-a-plugin)。

## 第三方 marketplace

許多熱門 plugin 不在任何 Anthropic marketplace 中。它們在其作者自己的 marketplace 中，通常是在其根目錄中具有 `.claude-plugin/marketplace.json` 的 GitHub 儲存庫。

Anthropic 不審查第三方 marketplace，所以在新增一個之前，請閱讀 [Plugin 安全性和信任](https://code.claude.com/docs/zh-TW/plugins/security.md)。

若要使用第三方 marketplace，在 Claude Code 工作階段中使用 `/plugin marketplace add <owner>/<repo>` 新增其儲存庫，然後使用 `/plugin install <plugin>@<marketplace-name>` 安裝。marketplace 名稱是該 `marketplace.json` 的 `name` 欄位，Claude Code 在新增 marketplace 後會列印它。

如需新增 marketplace 的其他方式，請參閱[新增 marketplace](https://code.claude.com/docs/zh-TW/plugins/install.md#add-a-marketplace)。

## 後續步驟

* [安裝和管理 plugin](https://code.claude.com/docs/zh-TW/plugins/install.md)：從其中一個 marketplace 安裝 plugin 並選擇範圍
* [Plugin 安全性和信任](https://code.claude.com/docs/zh-TW/plugins/security.md)：plugin 可以在您的機器上執行的操作，以及在安裝前如何檢查一個
* [程式碼智慧 plugin](https://code.claude.com/docs/zh-TW/plugins/code-intelligence.md)：安裝官方 marketplace 的語言伺服器 plugin 之一
* [建立 marketplace](https://code.claude.com/docs/zh-TW/plugins/create-marketplace.md)：在 Anthropic 的旁邊執行您自己的 marketplace

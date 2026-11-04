<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/plugins/code-intelligence | lastmod: 2026-10-02 | section: Plugins / Use plugins -->
> 來源：https://code.claude.com/docs/zh-TW/plugins/code-intelligence（官方 zh-TW，lastmod 2026-10-02）｜分類：Plugins › Use plugins｜EN 摘要：Install a language server plugin so Claude sees type errors after edits and navigates code by symbol, and answer the LSP plugin recommendation dialog.

# Code intelligence plugins

> 安裝語言伺服器外掛程式，讓 Claude 在編輯後看到型別錯誤並按符號導覽程式碼，並回應 LSP 外掛程式建議對話框。

Code intelligence 外掛程式為 Claude 提供編輯器所具有的即時診斷和前往定義功能，因此 Claude 可以在執行建置之前捕捉其自身編輯引入的型別錯誤和遺漏的匯入，並按符號而非文字搜尋來尋找定義和參考。

每個外掛程式都透過語言伺服器協定 (LSP) 將 Claude Code 連接到一種語言的語言伺服器。您從 Anthropic 的官方市集安裝外掛程式，並在您的機器上安裝語言伺服器二進位檔。

> [!NOTE]
>
> Code intelligence 外掛程式在終端機工作階段中運作。在[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)中，Claude Code 不會啟動外掛程式語言伺服器，因此 Claude 在那裡無法取得診斷或程式碼導覽。若要撰寫您自己的語言伺服器外掛程式，或連接沒有外掛程式的語言伺服器，請參閱[外掛程式元件中的 LSP 伺服器](https://code.claude.com/docs/zh-TW/plugins/components.md#lsp-servers)。

若要開始使用，請在[安裝 code intelligence 外掛程式](#install-a-code-intelligence-plugin)下的表格中找到您的語言。該表格中的外掛程式來自 Anthropic 的[官方外掛程式市集](https://code.claude.com/docs/zh-TW/plugins/anthropic-marketplaces.md)。

如果您已經看到 **LSP 外掛程式建議**對話框，請參閱[接受或關閉建議對話框](#accept-or-dismiss-the-recommendation-dialog)以了解每個選擇的作用。

## 安裝 code intelligence 外掛程式

Code intelligence 外掛程式告訴 Claude Code 哪個命令啟動語言伺服器以及它處理哪些檔案副檔名。它不包含語言伺服器。先安裝語言伺服器二進位檔，然後安裝外掛程式，最後確認伺服器啟動。

**1. 安裝語言伺服器二進位檔**

在下表中找到您的語言，並安裝其列中的二進位檔。如果您的語言未列出，請參閱[新增沒有官方外掛程式的語言](#add-a-language-without-an-official-plugin)。

| 語言 | 外掛程式 | 二進位檔 |
| :- | :- | :- |
| C/C++ | [`clangd-lsp`](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/clangd-lsp) | `clangd` |
| C# | [`csharp-lsp`](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/csharp-lsp) | `csharp-ls` |
| Go | [`gopls-lsp`](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/gopls-lsp) | `gopls` |
| Java | [`jdtls-lsp`](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/jdtls-lsp) | `jdtls` |
| Kotlin | [`kotlin-lsp`](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/kotlin-lsp) | `kotlin-lsp` |
| Liquid | [`liquid-lsp`](https://github.com/Shopify/liquid-skills/tree/main/plugins/liquid-lsp) | `shopify`，來自 Shopify CLI |
| Lua | [`lua-lsp`](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/lua-lsp) | `lua-language-server` |
| PHP | [`php-lsp`](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/php-lsp) | `intelephense` |
| Python | [`pyright-lsp`](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/pyright-lsp) | `pyright-langserver` |
| Ruby | [`ruby-lsp`](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/ruby-lsp) | `ruby-lsp` |
| Rust | [`rust-analyzer-lsp`](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/rust-analyzer-lsp) | `rust-analyzer` |
| Swift | [`swift-lsp`](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/swift-lsp) | `sourcekit-lsp` |
| TypeScript 和 JavaScript | [`typescript-lsp`](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/typescript-lsp) | `typescript-language-server` |

Anthropic 維護表格中的每個外掛程式，除了 `liquid-lsp` 外，該外掛程式由 Shopify 維護，官方市集也列出了它。

若要找到安裝二進位檔的命令，請按照表格中的外掛程式連結前往其 README。對於 TypeScript，該命令是 `npm install -g typescript-language-server typescript`。

安裝二進位檔後，確認它在您啟動 `claude` 的 shell 的 `PATH` 上，例如使用 `which typescript-language-server`，或在 PowerShell 中使用 `Get-Command typescript-language-server`。

**2. 安裝外掛程式**

在 VS Code 擴充功能或桌面應用程式中，請改為按照[安裝外掛程式](https://code.claude.com/docs/zh-TW/plugins/install.md#install-a-plugin)操作，而非執行此步驟。在終端機中，執行 `claude` 啟動 Claude Code，然後在其提示字元中輸入以下內容，將 `typescript-lsp` 替換為步驟 1 表格中為您的語言列出的外掛程式：

```
/plugin install typescript-lsp@claude-plugins-official
```

確認訊息會說明外掛程式現在是否處於作用中或需要 `/reload-plugins`。如果安裝失敗並顯示 `Marketplace "claude-plugins-official" not found`，請參閱[該錯誤的疑難排解項目](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#marketplace-claude-plugins-official-not-found)。若要控制外掛程式的安裝位置，或從 shell 而不是在 Claude Code 內執行安裝，請參閱[安裝外掛程式](https://code.claude.com/docs/zh-TW/plugins/install.md)。

**3. 確認伺服器啟動**

語言伺服器在 Claude 首次編輯具有外掛程式副檔名之一的檔案時啟動。若要看到它運作，請要求 Claude 在該語言的檔案中引入型別錯誤，然後修復它。然後檢查對話框中的診斷行：

* **出現診斷行**：在引入錯誤的編輯下方出現 `Found N new diagnostic issues in M files (ctrl+o to expand)` 表示伺服器已啟動。
* **未出現診斷行**：執行 `/plugin` 並開啟 **Errors** 標籤。讀取 `Executable not found in $PATH: "<binary>"` 的列會命名要安裝的二進位檔。如果標籤中沒有這樣的列，請參閱[疑難排解 code intelligence](#troubleshoot-code-intelligence)。

安裝遺漏的二進位檔後，Claude Code 會在 Claude 下次編輯相符檔案時重試。如果您將二進位檔安裝到不在您啟動 `claude` 的 shell 的 `PATH` 上的目錄中，請從它所在的 shell 啟動新工作階段。

## 查看 Claude 獲得的內容

執行語言伺服器後，Claude 獲得診斷和程式碼導覽：

* **編輯後的診斷**：每次 Claude 編輯或寫入伺服器處理的檔案時，Claude 都會獲得伺服器報告的錯誤和警告。它會看到它引入的型別錯誤、遺漏的匯入或語法錯誤，而無需執行編譯器。
* **程式碼導覽**：Claude 獲得一個 `LSP` 工具，該工具透過伺服器查詢符號，而不是搜尋文字。該工具是唯讀的。有關 Claude 可以使用該工具查詢的內容以及權限如何應用於它，請參閱 [LSP 工具行為](https://code.claude.com/docs/zh-TW/tools-reference.md#lsp-tool-behavior)。

### 自己閱讀診斷

Claude 編輯伺服器處理的檔案後，對話框只顯示 `Found N new diagnostic issues` 摘要。若要閱讀問題本身，請按 **Ctrl+O**。

## 接受或關閉建議對話框

如果語言伺服器二進位檔已在您的 `PATH` 上，但使用它的外掛程式未安裝，Claude Code 會在標題為 **LSP 外掛程式建議**的對話框中提供為您安裝外掛程式。

### 建議對話框何時出現

**LSP 外掛程式建議**對話框可在 Claude 編輯檔案後出現。這些條件決定它是否出現以及它提供哪個外掛程式：

* **外掛程式符合檔案**：您已新增的其中一個市集或 Claude Code 為您註冊的官方市集列出了該檔案副檔名的 code intelligence 外掛程式，且外掛程式的二進位檔已安裝。
* **官方優先**：當多個市集為副檔名提供外掛程式時，對話框會提供官方市集的外掛程式。
* **每個工作階段一次**：對話框在一個工作階段中最多出現一次，針對 Claude 編輯的第一個相符檔案。
* **不適用於雲端工作階段**：當您的終端機連接到雲端工作階段（例如您使用 [`claude --cloud`](https://code.claude.com/docs/zh-TW/claude-code-on-the-web#from-terminal-to-cloud) 啟動的工作階段）時，對話框永遠不會出現。

### 回應建議對話框

**LSP 外掛程式建議**對話框會命名外掛程式並提供這些選擇：

* **Yes, install**：Claude Code 為您的使用者帳戶安裝外掛程式並列印 `<plugin> installed · restart to apply`。啟動新工作階段以載入伺服器。
* **No, not now**：對話框關閉，稍後的工作階段可以再次提供外掛程式。按 **Esc** 也會執行相同操作。
* **Never for this plugin**：對話框停止為該外掛程式出現，但仍會為其他外掛程式出現。
* **Disable all LSP recommendations**：對話框停止為每種語言出現。

如果您未選擇選項，Claude Code 會在 30 秒後關閉它，並將其計為已忽略。計數會跨工作階段保留。在忽略五個對話框後，Claude Code 停止推薦外掛程式，與您選擇 **Disable all LSP recommendations** 相同。

### 重新開啟建議

**LSP 外掛程式建議**對話框在您選擇 **Disable all LSP recommendations** 或忽略它五次後停止出現。

* **已停用或忽略五次**：若要在任一情況下重新開啟它，請從 `~/.claude.json`（Claude Code 自己的設定檔）中移除 `lspRecommendationDisabled` 和 `lspRecommendationIgnoredCount` 鍵。
* **永不為此外掛程式**：如果您選擇了 **Never for this plugin** 並希望再次提供該外掛程式，請從同一檔案中的 `lspRecommendationNeverPlugins` 列表中移除其 `name@marketplace` ID。

## 疑難排解 code intelligence

外掛程式疑難排解頁面涵蓋 code intelligence 外掛程式特定的症狀，位於[語言伺服器不啟動、使用過多記憶體或報告錯誤診斷](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#language-server-doesnt-start)下：

* **語言伺服器不啟動**：您在 `/plugin` 的 **Errors** 標籤中看到 `Executable not found in $PATH`，或 Claude 永遠不會報告該語言的診斷。
* **高記憶體使用量**：當伺服器索引專案時，記憶體使用量會增加。
* **monorepo 中的誤判診斷**：診斷報告匯入為未解決，但實際上已解決。

## 新增沒有官方外掛程式的語言

如果您的語言不在[官方外掛程式表格](#install-a-code-intelligence-plugin)中，您仍然可以連接語言伺服器。

1. 使用 `.lsp.json` 檔案撰寫外掛程式，該檔案命名伺服器命令和它處理的檔案副檔名。
2. 然後使用 [`--plugin-dir`](https://code.claude.com/docs/zh-TW/plugins/cli-reference#flags-that-load-a-plugin-for-one-session) 載入外掛程式或將其發佈到市集。

有關檔案的欄位和實際範例，請參閱[外掛程式元件中的 LSP 伺服器](https://code.claude.com/docs/zh-TW/plugins/components.md#lsp-servers)。

## 後續步驟

* [外掛程式元件中的 LSP 伺服器](https://code.claude.com/docs/zh-TW/plugins/components.md#lsp-servers)：為沒有官方外掛程式的語言伺服器撰寫 `.lsp.json`
* [安裝和管理外掛程式](https://code.claude.com/docs/zh-TW/plugins/install.md)：範圍、更新和解除安裝
* [疑難排解外掛程式](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md)：超出本頁語言伺服器的載入錯誤
* [在官方市集中尋找外掛程式](https://code.claude.com/docs/zh-TW/plugins/anthropic-marketplaces.md#find-plugins-in-the-official-marketplace)：瀏覽官方市集其餘部分的位置

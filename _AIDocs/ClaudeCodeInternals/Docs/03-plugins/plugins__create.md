<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/plugins/create | lastmod: 2026-10-28 | section: Plugins / Create plugins -->
> 來源：https://code.claude.com/docs/zh-TW/plugins/create（官方 zh-TW，lastmod 2026-10-28）｜分類：Plugins › Create plugins｜EN 摘要：Build your first Claude Code plugin from an empty directory, test it without a marketplace, and convert an existing .claude/ setup.

# 建立 Claude Code 外掛程式

> 從空目錄建立您的第一個 Claude Code 外掛程式，在沒有市集的情況下測試它，並轉換現有的 .claude/ 設定。

外掛程式是一個包含技能、代理、hooks 和 MCP 伺服器的目錄，加上一個稱為清單的 `plugin.json` 檔案，用來命名外掛程式。Claude Code 將該目錄作為一個單位載入，因此您可以與隊友分享、在多個專案中安裝，或將其發佈到市集。

本頁面適用於編寫自己外掛程式的人員。

> [!NOTE]
>
> 其他頁面涵蓋了這些情況：
>
> * **安裝他人的外掛程式**：請參閱[安裝外掛程式](https://code.claude.com/docs/zh-TW/plugins/install.md)
> * **不確定您是否需要外掛程式**：請參閱概述中的[決定是否需要外掛程式](https://code.claude.com/docs/zh-TW/plugins/overview.md#decide-whether-you-need-a-plugin)
> * **您的外掛程式使用者在 claude.ai 或 Cowork 上**：同一個資料夾會以不同的元件子集安裝在那裡。請參閱[外掛程式結構和測試](https://claude.com/docs/plugins/build)和[元件支援表](https://claude.com/docs/plugins/platform-support#compare-component-support-by-app)

從與您已有的內容相符的部分開始：

* **還沒有任何東西**：遵循[建立您的第一個外掛程式](#create-your-first-plugin)，然後[在沒有市集的情況下開發](#develop-without-a-marketplace)和[測試和偵錯](#test-and-debug)。
* **已在 `.claude/` 下有檔案**：執行一次第一個外掛程式的逐步解說以了解佈局，然後遵循[轉換現有的 `.claude/` 設定](#convert-an-existing-claude-setup)。

## 決定何時使用外掛程式

技能、代理、hooks 和 MCP 伺服器都可以在您的專案或主目錄中獨立運作。當它只為一個專案或只為您服務時，保持該獨立設定。當您想與隊友分享設定、在多個專案中安裝，或發佈版本化版本時，請建立外掛程式。

當您將獨立技能、代理、hooks 和 MCP 設定移到外掛程式中時，它們的位置和名稱會改變：

* **檔案的位置**：在外掛程式自己的目錄（稱為外掛程式根目錄）下，作為 `skills/`、`agents/`、`hooks/hooks.json` 和 `.mcp.json`。
* **它們的命名方式**：外掛程式技能和代理會取得外掛程式名稱作為前綴，例如 `/my-plugin:hello`，因此兩個外掛程式可以各自提供一個 `hello` 技能而不會衝突。

若要將現有設定移到外掛程式中，請參閱[轉換現有的 `.claude/` 設定](#convert-an-existing-claude-setup)。

## 建立您的第一個外掛程式

在此逐步解說中，您建立一個外掛程式，其唯一元件是一個技能（問候），並使用 `--plugin-dir` 執行它，該選項會為一個工作階段載入外掛程式而不安裝它。外掛程式可以包含任何[元件](https://code.claude.com/docs/zh-TW/plugins/components.md)的組合，例如技能、代理、hooks 和 MCP 伺服器，且不需要任何一個；一個技能是展示佈局的最小範例。

您需要 Claude Code [已安裝並登入](https://code.claude.com/docs/zh-TW/quickstart.md#step-1-install-claude-code)。

在您想保留外掛程式的目錄（例如 `~/projects`）中開啟終端機，並從該目錄執行這些步驟中的命令。您可以將外掛程式保留在任何地方，因為當您啟動工作階段時，您會將其路徑傳遞給 Claude Code。

**1. 建立外掛程式目錄**

建立外掛程式目錄，其中包含一個 `.claude-plugin/` 資料夾來保存清單：

```bash theme={null}
mkdir -p my-first-plugin/.claude-plugin
```

**2. 編寫清單**

[清單](https://code.claude.com/docs/zh-TW/plugins/manifest-reference.md)是一個名為 `plugin.json` 的 JSON 檔案，它告訴 Claude Code 外掛程式的名稱並描述它。將此檔案儲存為 `my-first-plugin/.claude-plugin/plugin.json`：

```json my-first-plugin/.claude-plugin/plugin.json theme={null}
{
  "name": "my-first-plugin",
  "description": "A greeting plugin to learn the basics",
  "version": "1.0.0",
  "author": {
    "name": "Your Name"
  }
}
```

這四個欄位的作用如下：

* **`name`**：必需。它識別外掛程式並成為外掛程式提供的每個技能和代理的前綴。不要在其中放置空格。
* **`description`**：使用者在 `/plugin` 中看到的外掛程式文字。
* **`version`**：選用。設定它會讓使用者保持在該版本，直到您更改它；[發佈新版本](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md#release-a-new-version)說明何時設定或省略它。
* **`author`**：要歸功於誰。其中的 `name` 是必需的；`email` 和 `url` 是選用的。

每個其他欄位都在[清單參考](https://code.claude.com/docs/zh-TW/plugins/manifest-reference.md#fields)上。

只有 `plugin.json` 放在 `.claude-plugin/` 內。您接下來添加的技能直接放在 `my-first-plugin/` 下，在該資料夾旁邊。

**3. 添加技能**

此外掛程式的一個元件是一個技能。每個技能是 `skills/` 下的一個目錄，包含一個 `SKILL.md` 檔案。建立技能的目錄：

```bash theme={null}
mkdir -p my-first-plugin/skills/hello
```

然後使用此內容建立 `my-first-plugin/skills/hello/SKILL.md`：

```markdown my-first-plugin/skills/hello/SKILL.md theme={null}
---
name: hello
description: Greet the user with a friendly message
disable-model-invocation: true
---

Greet the user warmly and ask how you can help them today.
```

`disable-model-invocation: true` 行表示 Claude 不會自行執行該 skill。從您希望 Claude 自行執行的 skill 中移除該行。skill 的命令結合外掛程式名稱和 skill 的名稱，因此您將此 skill 執行為 `/my-first-plugin:hello`。對於其他 frontmatter 欄位，請參閱[skill frontmatter 參考](https://code.claude.com/docs/zh-TW/skills.md#frontmatter-reference)。

**4. 驗證外掛程式**

在執行任何操作之前檢查清單和 skill 的 frontmatter：

```bash theme={null}
claude plugin validate ./my-first-plugin
```

該命令列印它檢查的清單路徑和 `✔ Validation passed`。如果它改為列印 `✘ Validation failed`，則該結果行上方的每一行都命名要修復的欄位。在[`claude plugin validate` 報告錯誤](https://code.claude.com/docs/zh-TW/plugins/troubleshooting#claude-plugin-validate-reports-errors)下查找每條訊息。

**5. 使用外掛程式執行 Claude Code**

啟動已載入外掛程式的工作階段：

```bash theme={null}
claude --plugin-dir ./my-first-plugin
```

Claude Code 啟動後，執行技能：

```text theme={null}
/my-first-plugin:hello
```

Claude 會回覆一個問候。

外掛程式只在您使用 `--plugin-dir` 啟動的工作階段中載入。若要在沒有該旗標的情況下繼續處理它，或測試 `.zip` 組建，請參閱[在沒有市集的情況下開發](#develop-without-a-marketplace)。

若要讓 Claude 為您建立並檢查更大的外掛程式，請從 `claude-plugins-official` 市集[安裝](https://code.claude.com/docs/zh-TW/plugins/install.md#install-a-plugin) Anthropic 的 `plugin-dev` 外掛程式，該外掛程式會新增用於編寫技能、hooks 和 MCP 伺服器等元件的技能和代理，以及用於驗證完成的外掛程式的技能和代理。安裝後，執行 `/plugin-dev:create-plugin` 後跟您想要的外掛程式的描述，Claude 會引導您完成設計、建立和驗證它。

### 分享您的外掛程式

使用[建立您的第一個外掛程式](#create-your-first-plugin)建立的外掛程式只存在於您的機器上。當它準備好供其他人使用時，有三種方式可以將其提供給他們：

* **直接將其發送給少數人**：給他們外掛程式的目錄或其 `.zip`，無需發佈任何內容。請參閱[在沒有市集的情況下分享外掛程式](https://code.claude.com/docs/zh-TW/plugins/publish.md#share-a-plugin-without-a-marketplace)。
* **在您自己的市集中列出它**：隊友添加您的市集一次並按名稱安裝外掛程式，他們會收到您的更新。請參閱[透過您自己的市集發佈](https://code.claude.com/docs/zh-TW/plugins/publish.md#publish-through-your-own-marketplace)。
* **將其提交到 Anthropic 的社群市集**：列出後，任何添加該市集的人都可以安裝它。請參閱[提交到社群市集](https://code.claude.com/docs/zh-TW/plugins/publish.md#submit-to-anthropics-directory)。

### 外掛程式佈局

每種[元件](https://code.claude.com/docs/zh-TW/plugins/components.md)（例如技能、代理、hooks 和 MCP 伺服器）都放在外掛程式根目錄下的固定目錄中，外掛程式根目錄是您傳遞給 `--plugin-dir` 的目錄。只添加您使用的目錄。若要點擊完整的外掛程式目錄並閱讀每個檔案的作用，請開啟[外掛程式瀏覽器](https://code.claude.com/docs/zh-TW/plugins/components.md#explore-the-plugin-directory)。

該表列出了大多數外掛程式開始使用的目錄，[完整佈局](https://code.claude.com/docs/zh-TW/plugins/manifest-reference.md#standard-layout)列出了其餘的。

| 位置 | 內容 |
| :- | :- |
| `.claude-plugin/plugin.json` | 清單。當您使用 `--plugin-dir` 載入外掛程式且它沒有清單時，Claude Code 會以其目錄命名外掛程式 |
| `skills/` | 每個技能一個 `<name>/SKILL.md` 目錄 |
| `commands/` | 平面 Markdown 檔案，技能的較舊形式。對於新外掛程式，請使用 `skills/` |
| `agents/` | 每個子代理一個 Markdown 檔案 |
| `hooks/hooks.json` | Hook 設定：一個頂級 `"hooks"` 鍵，其值的形狀與設定檔案中的 `hooks` 相同 |
| `.mcp.json` | MCP 伺服器定義 |

> [!WARNING]
>
> 只有 `plugin.json` 放在 `.claude-plugin/` 內。保存在那裡的元件不會載入。
>
> 外掛程式根目錄是外掛程式自己的目錄，不是 `~/.claude/` 本身。保存在 `~/.claude/.mcp.json` 的 `.mcp.json` 不會載入。

## 在沒有市集的情況下開發

您不需要[市集](https://code.claude.com/docs/zh-TW/plugins/overview.md#get-plugins-from-a-marketplace)來執行您正在編寫的外掛程式。改為直接從磁碟或 URL 載入它：

* [`--plugin-dir`](#load-a-directory-or-archive-for-one-session)：為一個工作階段載入目錄或 `.zip` 存檔。
* [`--plugin-url`](#fetch-an-archive-from-a-url-for-one-session)：為一個工作階段從 URL 擷取 `.zip` 存檔。
* [`claude plugin init`](#scaffold-a-plugin-that-loads-every-session)：在 `~/.claude/skills/` 下搭建一個可跨工作階段載入的外掛程式。

如果以不同方式載入的兩個外掛程式共享一個名稱，請參閱[名稱衝突](https://code.claude.com/docs/zh-TW/plugins/loading.md#name-conflicts)以了解 Claude Code 保留哪一個。

### 為一個工作階段載入外掛程式

您可以通過三種方式為單個工作階段載入外掛程式：使用 `--plugin-dir` 從磁碟上的目錄或 `.zip` 存檔，使用 `--plugin-url` 從 URL，或從環境變數（當您無法添加旗標時）。每個外掛程式只為該工作階段載入，沒有任何內容寫入您的設定。當您在工作階段期間編輯外掛程式的檔案時，執行 `/reload-plugins` 以載入變更。

#### 從目錄或 `.zip` 載入外掛程式

當您從 shell 啟動 `claude` 時，使用外掛程式的根目錄或其 `.zip` 存檔傳遞 `--plugin-dir`。重複該旗標以載入多個外掛程式：

```bash theme={null}
claude --plugin-dir ./my-first-plugin --plugin-dir ./other-plugin.zip
```

#### 載入外掛程式資料夾

若要從一個地方載入多個外掛程式，請傳遞一個保存它們的資料夾，例如 `--plugin-dir ./plugins`。載入外掛程式資料夾需要 Claude Code v2.1.265 或更新版本。

如果資料夾沒有 `.claude-plugin/` 目錄且其頂級沒有外掛程式元件，Claude Code 會將其視為外掛程式資料夾。然後，每個具有 `.claude-plugin/plugin.json` 清單的直接子資料夾都會作為單獨的外掛程式載入。資料夾中的所有其他內容都會被跳過而不出現錯誤，包括沒有清單的子資料夾。如果資料夾中的外掛程式無法載入，請檢查其子資料夾是否具有 `.claude-plugin/plugin.json`。

您也可以傳遞一個資料夾，該資料夾在其外掛程式資料夾旁邊保存 `.claude-plugin/marketplace.json`。只要該 `.claude-plugin/` 目錄不包含 `plugin.json`，外掛程式資料夾仍會載入。市集檔案中沒有任何內容被安裝或啟用，因為 Claude Code 不會讀取它。從這樣的資料夾載入外掛程式需要 Claude Code v2.1.281 或更新版本。

在互動式工作階段中，您也可以在啟動後在資料夾中添加和移除外掛程式：

* 您添加的子資料夾在其清單存在後會作為新外掛程式載入。
* 當您移除子資料夾時，其外掛程式會卸載。

對於這些變更中的每一個，工作階段中都會出現一條訊息。如果在對話中途載入或卸載外掛程式會[使提示快取失效](https://code.claude.com/docs/zh-TW/prompt-caching.md#enabling-or-disabling-a-plugin)，則該變更會被保留，訊息會告訴您執行 `/reload-plugins` 以應用它。

#### 從 URL 載入外掛程式

當您從 shell 啟動 `claude` 時，使用 `.zip` 存檔的位址傳遞 `--plugin-url`，例如您的 CI 發佈的組建成品：

```bash theme={null}
claude --plugin-url https://example.com/my-first-plugin.zip
```

Claude Code 在啟動時下載存檔。若要載入多個，請重複該旗標或在一個引用的引數中傳遞以空格分隔的 URL。

只在您控制或信任的存檔上指向該旗標。

如果 Claude Code 無法擷取存檔或存檔無效，它會在沒有外掛程式的情況下啟動，並記錄一個外掛程式載入錯誤，您可以在 `/plugin` 管理器的**錯誤**標籤中查看。

#### 從環境變數載入外掛程式

若要在無法添加 `--plugin-dir` 旗標的工作階段中載入外掛程式，請改為在 [`CLAUDE_CODE_PLUGIN_DIRS`](https://code.claude.com/docs/zh-TW/env-vars#variables) 環境變數中列出它們的絕對路徑。Claude Code 會像載入 `--plugin-dir` 路徑一樣載入每個路徑。這些外掛程式會添加到您使用 `--plugin-dir` 傳遞的任何外掛程式中。[專案和本機設定無法設定此變數](https://code.claude.com/docs/zh-TW/settings-reference.md#variables-claude-code-ignores-in-env)。`CLAUDE_CODE_PLUGIN_DIRS` 需要 Claude Code v2.1.280 或更新版本。

受管設定可以關閉 `--plugin-dir` 和 `CLAUDE_CODE_PLUGIN_DIRS`。請參閱[為一個工作階段載入外掛程式的旗標](https://code.claude.com/docs/zh-TW/plugins/cli-reference.md#flags-that-load-a-plugin-for-one-session)。若要一起測試外掛程式及其依賴的外掛程式，請參閱[在本機測試外掛程式及其依賴](https://code.claude.com/docs/zh-TW/plugins/dependencies.md#test-a-plugin-and-its-dependency-locally)。

### 讓外掛程式在每個工作階段中載入

您的個人 skills 目錄是 `~/.claude/skills/`，而其中包含 `.claude-plugin/plugin.json` 的資料夾就是一個 skills 目錄外掛程式。除非您的管理員已[封鎖 skills 目錄外掛程式](https://code.claude.com/docs/zh-TW/plugins/loading.md#skills-directory-plugins-blocked-by-managed-settings)，否則 Claude Code 會在工作階段啟動時載入每一個這類外掛程式，無需旗標，也無需安裝步驟。`claude plugin init` 可為您搭建一個。

#### 使用 `claude plugin init` 搭建外掛程式

`claude plugin init` 在 `~/.claude/skills/` 下寫入一個啟動外掛程式。從您的 shell 搭建一個：

```bash theme={null}
claude plugin init my-tool
```

該命令在 `~/.claude/skills/my-tool/` 下建立一個 `.claude-plugin/plugin.json` 和一個根 `SKILL.md`。它列印 `✔ Created plugin "my-tool" at ~/.claude/skills/my-tool` 後跟 `It will auto-load next session as my-tool@skills-dir. Run /reload-plugins to load it now.`

傳遞 `--with skills` 以讓 `claude plugin init` 為您在 `skills/` 下搭建一個技能。其他 `--with` 值在[外掛程式命令參考](https://code.claude.com/docs/zh-TW/plugins/cli-reference.md#plugin-init)上。

#### 在搭建的外掛程式中命名技能

`~/.claude/skills/my-tool/SKILL.md` 的根技能也是個人技能，因此您將其作為 `/my-tool` 而不是 `/my-tool:my-tool` 呼叫。您在外掛程式內的 `skills/` 下添加的技能會取得外掛程式名稱前綴，例如 `/my-tool:example`。

#### 停止載入外掛程式

若要停止載入搭建的外掛程式，請刪除其目錄，或在 shell 中使用 `claude plugin init` 列印的 `my-tool@skills-dir` 名稱執行 `claude plugin disable my-tool@skills-dir`。在 ID `my-tool@skills-dir` 中，`skills-dir` 代替市集名稱，因為外掛程式從您的技能目錄而不是市集載入。

#### 透過存放庫分享外掛程式

`claude plugin init` 將外掛程式寫入您的個人 skills 目錄 `~/.claude/skills/`，此目錄由您在這台機器上的所有專案共用。若要讓外掛程式為一個儲存庫中的每個人載入，請在 `<project>/.claude/skills/<name>/` 自己建立相同的佈局，包括其 `.claude-plugin/plugin.json`。請參閱[透過儲存庫分享的外掛程式](https://code.claude.com/docs/zh-TW/plugins/loading.md#plugins-shared-through-a-repository)以了解 Claude Code 在什麼條件下載入它。

## 測試和偵錯

當對外掛程式的變更沒有顯示時，按順序執行這些檢查。每一個都告訴您 Claude Code 對外掛程式做了什麼：

1. 在您的 shell 中，執行 `claude plugin validate <path>`。它檢查清單和每個技能、代理和命令檔案的 frontmatter，並在 `Validation passed` 時退出 `0`。添加 `--strict` 以在警告時也失敗。退出代碼和目錄處理在[外掛程式命令參考](https://code.claude.com/docs/zh-TW/plugins/cli-reference.md#plugin-validate)上。
2. 在執行中的工作階段中，執行 `/reload-plugins` 以應用您在磁碟上所做的編輯。它列印一個 `Reloaded:` 行，其中包含計數。然後通過輸入其 `/plugin-name:skill` 命令或在 `/plugin` **已安裝**標籤中找到外掛程式來確認技能已載入。
3. 在同一工作階段中，執行 `/plugin`。**已安裝**標籤列出您的外掛程式，在外掛程式的詳細資訊中，Claude Code 找到的元件。**錯誤**標籤列出無法載入的內容及其原因，例如清單中不存在的路徑。
4. 回到您的 shell，執行 `claude plugin list`。它在各自的部分中列印僅工作階段和技能目錄外掛程式，帶有 `Status: ✔ loaded` 或載入錯誤。若要包括您正在開發的外掛程式，請在 `plugin list` 之前使用其路徑傳遞 `--plugin-dir`。
5. 如果您的外掛程式位於 skills 目錄中，而 `claude plugin list` 沒有列印它，且該處或 `/plugin` 中都沒有錯誤，請參閱[被受管設定封鎖的 skills 目錄外掛程式](https://code.claude.com/docs/zh-TW/plugins/loading.md#skills-directory-plugins-blocked-by-managed-settings)。

若要檢查 MCP 伺服器，請在工作階段中執行 `/mcp` 以查看伺服器的狀態。當伺服器健康時，`/mcp` 會將其列為已連接。如果不是，請參閱[不啟動的 MCP 伺服器](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#invalid-mcp-server-config-for-and-mcp-servers-that-dont-start)。

若要檢查 hook，請觸發它匹配的事件。例如，要求 Claude 編輯檔案以觸發 `PostToolUse` hook。然後閱讀[偵錯日誌](https://code.claude.com/docs/zh-TW/hooks.md#debug-hooks)，它顯示哪些 hooks 匹配、它們的退出代碼和它們的輸出。

下一部分涵蓋您在開發時最可能遇到的失敗，[疑難排解頁面](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#build-a-plugin)對每一個都有完整的條目。

### 找不到元件路徑

`/plugin` 的**錯誤**標籤顯示 `<component> path not found: <path>`，例如 `commands path not found`。清單中的元件路徑（例如 `commands`、`skills`、`agents` 或 `hooks`）指向不存在的內容。修復路徑或建立目錄，然後在工作階段中執行 `/reload-plugins`。請參閱[`commands path not found`](https://code.claude.com/docs/zh-TW/plugins/troubleshooting#commands-path-not-found)。

### `--plugin-dir` 在市集根目錄不載入 `plugins/` 下的外掛程式

`--plugin-dir` 採用外掛程式的根目錄，即包含 `.claude-plugin/plugin.json` 和元件目錄（例如 `skills/`）的目錄。如果您改為指向市集根目錄，Claude Code 不會讀取 `marketplace.json`，因此 `plugins/` 下的外掛程式不會載入，您看不到錯誤。將旗標指向一個外掛程式的資料夾，或添加市集。請參閱[疑難排解條目](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#plugin-dir-loads-a-plugin-with-no-components)。

### 外掛程式載入但其技能遺失

`skills/` 目錄在 `.claude-plugin/` 內，或清單中的 `skills` 條目指向一個檔案。將 `skills/` 移到外掛程式根目錄，將每個 `skills` 條目指向包含 `SKILL.md` 的目錄，並在工作階段中執行 `/reload-plugins`。請參閱[外掛程式載入但其技能遺失](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#plugin-loads-but-its-skills-are-missing)。

### `userConfig` 對話框從不出現

您外掛程式的 [`userConfig`](https://code.claude.com/docs/zh-TW/plugins/components#user-configuration) 選項的對話框是在工作階段中透過 `/plugin` 安裝的一部分。使用 `--plugin-dir` 載入不會顯示它，`claude plugin install` 在 shell 中也不會。載入外掛程式後，在工作階段中執行 `/plugin configure <plugin-name>` 以開啟它。請參閱[`userConfig` 對話框從不出現](https://code.claude.com/docs/zh-TW/plugins/troubleshooting#the-userconfig-dialog-never-appears)。

### 檢查外掛程式是否改變 Claude 的行為

無錯誤載入的外掛程式仍然可能無法按您的意圖引導 Claude。`claude plugin eval`（您在 shell 中執行）使用和不使用外掛程式執行您的測試案例並評分差異。請參閱[使用 evals 測試外掛程式](https://code.claude.com/docs/zh-TW/plugin-evals.md)，從[建立您的第一個 eval 套件](https://code.claude.com/docs/zh-TW/plugin-evals.md#create-your-first-eval-suite)開始。

## 轉換現有的 `.claude/` 設定

如果您已在專案的 `.claude/` 目錄下有技能、代理或 hooks，您可以將它們移到外掛程式中而無需重寫它們。

從專案根目錄（包含 `.claude/` 的目錄）執行這些步驟中的命令，因為 `cp` 路徑相對於它。

**1. 建立外掛程式結構**

在 `.claude/` 旁邊建立外掛程式目錄及其 `.claude-plugin/` 資料夾。您之後可以將外掛程式移到任何地方。

```bash theme={null}
mkdir -p my-plugin/.claude-plugin
```

建立 `my-plugin/.claude-plugin/plugin.json`：

```json my-plugin/.claude-plugin/plugin.json theme={null}
{
  "name": "my-plugin",
  "description": "Migrated from standalone configuration",
  "version": "1.0.0"
}
```

**2. 複製您現有的檔案**

將您擁有的每個設定目錄複製到外掛程式根目錄，並跳過您沒有的任何目錄的命令。

```bash theme={null}
cp -r .claude/commands my-plugin/
```

```bash theme={null}
cp -r .claude/agents my-plugin/
```

```bash theme={null}
cp -r .claude/skills my-plugin/
```

執行 `ls -a my-plugin` 以確認您複製的每個目錄都出現在 `.claude-plugin` 旁邊。

**3. 移動您的 hooks**

如果您在 `.claude/settings.json` 或 `.claude/settings.local.json` 中有 hooks，請建立一個 hooks 目錄：

```bash theme={null}
mkdir -p my-plugin/hooks
```

建立 `my-plugin/hooks/hooks.json` 並將 `hooks` 物件從您的設定檔案複製到其中。格式相同。

此範例顯示帶有一個 hook 的形狀，該 hook 在 Claude 寫入或編輯每個檔案時執行 linter。用您自己的 `hooks` 物件替換範例。

```json my-plugin/hooks/hooks.json theme={null}
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [{ "type": "command", "command": "jq -r '.tool_input.file_path' | xargs npm run lint:fix" }]
      }
    ]
  }
}
```

**4. 測試遷移的外掛程式**

為一個工作階段載入外掛程式：

```bash theme={null}
claude --plugin-dir ./my-plugin
```

在其新名稱下檢查每個元件：

* **技能**：為曾經是 `/deploy` 的技能執行 `/my-plugin:deploy`。
* **子代理**：要求 Claude 為曾經是 `reviewer` 的代理使用 `my-plugin:reviewer` 代理。
* **Hooks**：觸發每個 hook 匹配的事件。

如果遺失了什麼，請執行[測試和偵錯](#test-and-debug)。

當原始檔案仍在 `.claude/` 下時，它們會與外掛程式的副本一起保持載入：

* **技能和代理**：這兩組不會衝突，因為外掛程式的技能和代理帶有 `my-plugin:` 前綴。`/deploy` 和 `/my-plugin:deploy` 都有效，Claude 將 `reviewer` 和 `my-plugin:reviewer` 視為兩個子代理。
* **Hooks**：hooks 沒有前綴，因此同時在您的設定檔案和 `hooks/hooks.json` 中的 hook 會在其事件每次觸發時執行兩次。

在您確認外掛程式有效後，從 `.claude/` 刪除原始檔案並從您的設定檔案中移除 `hooks` 物件。

## 後續步驟

* [外掛程式元件](https://code.claude.com/docs/zh-TW/plugins/components.md)：將代理、hooks、MCP 伺服器、LSP 伺服器和使用者設定添加到您的外掛程式
* [使用 evals 測試外掛程式](https://code.claude.com/docs/zh-TW/plugin-evals.md)：編寫 eval 案例並使用 `claude plugin eval` 執行它們以檢查外掛程式引導 Claude 行為的可靠性
* [發佈外掛程式](https://code.claude.com/docs/zh-TW/plugins/publish.md)：版本化它、將其放在市集中，並將其提交以供審查
* [外掛程式結構和測試](https://claude.com/docs/plugins/build)：同一個外掛程式資料夾安裝在 claude.ai 和 Cowork 上。某些元件僅限 Claude Code，而[元件支援表](https://claude.com/docs/plugins/platform-support#compare-component-support-by-app)列出了在每個平台上加載的元件
* [外掛程式清單參考](https://code.claude.com/docs/zh-TW/plugins/manifest-reference.md)：每個 `plugin.json` 欄位、路徑規則和目錄
* [技能](https://code.claude.com/docs/zh-TW/skills.md)：編寫您的外掛程式提供的技能
* [Anthropic 在 claude-plugins-official 儲存庫中的外掛程式](https://github.com/anthropics/claude-plugins-official/tree/main/plugins)：本頁面佈局的完整實作範例，例如 `feature-dev` 和 `code-review`

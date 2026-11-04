<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/plugins/create-marketplace | lastmod: 2026-10-28 | section: Plugins / Run a marketplace -->
> 來源：https://code.claude.com/docs/zh-TW/plugins/create-marketplace（官方 zh-TW，lastmod 2026-10-28）｜分類：Plugins › Run a marketplace｜EN 摘要：Build a plugin marketplace from a marketplace.json file and test it locally before you host it.

# 建立 marketplace

> 從 marketplace.json 檔案建立 plugin marketplace，並在託管前在本機測試。

plugin marketplace 是一個目錄或儲存庫，包含 `.claude-plugin/marketplace.json` 檔案，該檔案列出您的 plugins 以及從何處取得每個 plugin。您將目錄推送到 git 主機，任何有存取權限的人都可以使用一個命令在 Claude Code 中註冊它，並從中安裝您的 plugins。

當您想要讓您選擇的群組（例如您的團隊或組織）安裝您的 plugins 並持續從您控制的目錄接收更新時，請建立您自己的 marketplace。該儲存庫可以是私有的，可以列出任意數量的 plugins，管理員可以[在每台機器上要求它](https://code.claude.com/docs/zh-TW/plugins/org.md)。

> [!NOTE]
>
> 其他頁面涵蓋了這些情況：
>
> * **與少數人分享一個 plugin**：將 plugin 的目錄或其 `.zip` 檔案發送給他們。請參閱[不使用 marketplace 分享 plugin](https://code.claude.com/docs/zh-TW/plugins/publish.md#share-a-plugin-without-a-marketplace)。
> * **向所有人提供 plugin**：將其提交到 Anthropic 的社群 marketplace。請參閱[提交到社群 marketplace](https://code.claude.com/docs/zh-TW/plugins/publish.md#submit-to-anthropics-directory)。
> * **自己使用 plugin**：使用 `--plugin-dir` 載入它或將其保存在您的 skills 目錄中。請參閱[不使用 marketplace 開發](https://code.claude.com/docs/zh-TW/plugins/create.md#develop-without-a-marketplace)。

從[建立 marketplace](#create-a-marketplace) 開始，在您自己的機器上建立一個並從中安裝 plugin，然後[新增更多 plugin 項目](#add-plugin-entries)。

## 建立 marketplace

以下步驟在您的機器上建立 marketplace，將 plugin 新增到其中，在 Claude Code 中註冊它，並從中安裝 plugin。這是整個流程，也是您的使用者在您將 marketplace 託管在他們可以存取的地方後所經歷的相同流程。從您想要建立 `my-marketplace/` 的目錄在您的 shell 中執行每個命令。

您需要一個 plugin 來列出。該範例使用來自[建立您的第一個 plugin](https://code.claude.com/docs/zh-TW/plugins/create.md#create-your-first-plugin) 的 `my-first-plugin`，這是一個具有一個 skill 的 plugin，您可以將其作為 `/my-first-plugin:hello` 執行；如果您還沒有 plugin，請先建立它。若要改用您自己的 plugin，請在步驟說 `my-first-plugin` 的任何地方替換其目錄和其 `name`。有關 plugin 目錄可以包含的內容，請參閱 [plugin 目錄探索器](https://code.claude.com/docs/zh-TW/plugins/components.md#explore-the-plugin-directory)。

**1. 設定 marketplace 目錄**

marketplace 是一個包含 `.claude-plugin/marketplace.json` 檔案的目錄，加上它列出的 plugins。建立 marketplace 目錄及其 `.claude-plugin/` 資料夾，然後將您的 plugin 複製到 `plugins/` 下：

```bash theme={null}
mkdir -p my-marketplace/.claude-plugin my-marketplace/plugins
cp -r my-first-plugin my-marketplace/plugins/
```

檢查 plugin 在其現在所在位置是否有效，以便任何後續錯誤都是關於 marketplace 而不是 plugin：

```bash theme={null}
claude plugin validate ./my-marketplace/plugins/my-first-plugin
```

輸出的最後一行讀作 `✔ Validation passed`。

**2. 建立 marketplace 檔案**

將 `marketplace.json` 儲存在 `my-marketplace/.claude-plugin/marketplace.json`。該檔案需要 `name`、`owner` 和 `plugins` 陣列。

`plugins` 中的每個物件都是一個 plugin 項目，需要 `name` 和 `source`。將項目的 `source` 寫成從 marketplace 根目錄的路徑。根目錄是 `my-marketplace/`，即包含 `.claude-plugin/` 的目錄。

```json my-marketplace/.claude-plugin/marketplace.json theme={null}
{
  "name": "my-marketplace",
  "description": "Plugins for my team",
  "owner": {
    "name": "Your Name"
  },
  "plugins": [
    {
      "name": "my-first-plugin",
      "source": "./plugins/my-first-plugin",
      "description": "A greeting plugin to learn the basics"
    }
  ]
}
```

**3. 驗證 marketplace**

在 marketplace 目錄上執行 `claude plugin validate` 以檢查 JSON 語法、必需欄位以及其 `.claude-plugin/marketplace.json` 中的每個 plugin 項目。

```bash theme={null}
claude plugin validate ./my-marketplace
```

對於在步驟 2 中編寫的檔案，輸出的最後一行讀作 `✔ Validation passed`。

**4. 新增 marketplace 並安裝 plugin**

將目錄註冊為 marketplace。

```bash theme={null}
claude plugin marketplace add ./my-marketplace
```

該命令列印 `✔ Successfully added marketplace: my-marketplace (declared in user settings)`，這意味著 marketplace 已記錄在您的使用者設定檔中。

安裝 plugin。安裝 id 是項目的 `name`、`@` 和 marketplace `name`。

```bash theme={null}
claude plugin install my-first-plugin@my-marketplace
```

該命令列印 `✔ Successfully installed plugin: my-first-plugin@my-marketplace (scope: user)`。

在工作階段內，`/plugin marketplace add ./my-marketplace` 以相同方式註冊 marketplace。`/plugin install my-first-plugin@my-marketplace` 在 `/plugin` 面板中開啟 plugin 的詳細資訊，您可以在其中安裝它。有關該流程，請參閱[安裝和管理 plugins](https://code.claude.com/docs/zh-TW/plugins/install.md)。

**5. 確認 plugin 已載入**

列出已安裝的 plugins。

```bash theme={null}
claude plugin list
```

輸出列出 `my-first-plugin@my-marketplace`，其中 `Status: ✔ enabled`。

若要查看 plugin 載入的內容，請顯示其詳細資訊。

```bash theme={null}
claude plugin details my-first-plugin
```

`Component inventory` 部分讀作 `Skills (1)  hello`。

若要執行 skill，請啟動工作階段並輸入 `/my-first-plugin:hello`。Claude 會向您問候。該命令以 plugin 的名稱作為前綴，就像每個 plugin skill 的名稱一樣。

## 新增 plugin 項目

您分發的每個 plugin 都是 `marketplace.json` 的 `plugins` 陣列中的一個物件。若要新增第二個 plugin，請新增第二個物件。這些欄位涵蓋大多數項目：

* `name`：人們在安裝時在 `@` 之前輸入的識別碼。[Plugin 項目](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#plugin-entries)說明名稱可以使用的字元。
* `source`：Claude Code 從何處取得 plugin。對於 marketplace 目錄內的 plugin，請寫入相對路徑字串，如[逐步解說](#create-a-marketplace)中所示，或對於目錄外的 plugin，請寫入來源物件。請參閱[選擇 plugin 來源](#choose-a-plugin-source)。
* `description`：人們在 `/plugin` 中瀏覽您的 marketplace 時在 plugin 旁邊看到的行。

有關完整欄位清單，請參閱 [Plugin 項目](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#plugin-entries)，其中也說明了項目可以設定的 [`plugin.json`](https://code.claude.com/docs/zh-TW/plugins/manifest-reference) 欄位及其適用時機。

## Plugin 項目規則

來自新 marketplace 的大多數失敗安裝來自於從錯誤目錄編寫的相對路徑，或來自與 plugin 的 `plugin.json` 中的 `name` 不同的項目名稱。

### 從 marketplace 根目錄編寫相對路徑

marketplace 根目錄是包含 `.claude-plugin/` 的目錄。在[逐步解說](#create-a-marketplace)中，那是 `my-marketplace/`，所以項目的 `source` 是 `"./plugins/my-first-plugin"`。該路徑不是從 `.claude-plugin/` 內部開始的，所以不要使用 `..` 來離開它。

包含 `..` 的路徑和指向不存在目錄的路徑在不同命令中失敗：

* **包含 `..` 的路徑**：`claude plugin validate` 將項目報告為無效。該訊息以 `Path contains "..": ./../plugins/my-first-plugin` 開頭。
* **指向不存在目錄的路徑**：`claude plugin validate` 通過。`claude plugin install` 失敗，並顯示 `Source path does not exist: <path>`，其中 `<path>` 是 Claude Code 檢查的絕對位置。

### 保持項目名稱和清單名稱相同

marketplace plugin 在 `marketplace.json` 中有一個項目 `name` 和在其自己的 `plugin.json` 中有一個 `name`，稱為清單名稱。每個名稱出現在不同的地方：

* **項目名稱**：安裝 id，`<entry-name>@<marketplace>`。這是人們輸入以安裝的內容，`claude plugin list` 顯示的內容，以及 Claude Code 在其設定檔中的 [`enabledPlugins`](https://code.claude.com/docs/zh-TW/settings-reference#enabledplugins) 下編寫的鍵。
* **清單名稱**：plugin skills 上的前綴，以及 `claude plugin details` 接受的名稱。

當兩個名稱不同且有人按清單名稱安裝時，Claude Code 報告 `Plugin "<manifest-name>" not found in marketplace "<marketplace>"`。保持兩個名稱相同。有關 Claude Code 如何使用這兩個名稱的更多資訊，請參閱 [Plugin 載入參考](https://code.claude.com/docs/zh-TW/plugins/loading.md#find-where-a-plugin-came-from)。

### 將未使用的子模組排除在複製之外

當有人新增您的 marketplace 時，Claude Code 會複製儲存庫，並且只擷取包含 plugin 檔案的 git 子模組。需要 Claude Code v2.1.295 或更新版本。

您可以透過放置每個 plugin 的位置，來決定 Claude Code 要擷取哪些子模組：

* **位於子目錄中的 plugin**：Claude Code 會擷取 plugin 目錄內的子模組，以及包含該 plugin 的子模組。請將 plugin 需要的子模組放在 plugin 的目錄內，並將不需要的子模組放在目錄外
* **位於 marketplace 根目錄的 plugin**：只要 plugin 的任一檔案參照了任何子模組內的路徑，Claude Code 就會擷取儲存庫中的所有子模組。如果您的儲存庫有一個只供建置使用的大型子模組，請將 plugin 移至子目錄中

如果位於根目錄的 plugin 會執行子模組中的檔案，請在 plugin 的 hook 或伺服器設定中明確寫出該檔案的路徑，例如 `${CLAUDE_PLUGIN_ROOT}/vendor/tool/run.sh`。Claude Code 會讀取這些路徑，以判斷 plugin 是否需要這些子模組。它無法看到腳本在執行時才組合出的路徑。

如需完整規則，請參閱 [marketplace 儲存庫中的 Git 子模組](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#git-submodules-in-the-marketplace-repository)。

## 選擇 plugin 來源

`marketplace.json` 中的每個 plugin 項目都有一個 `source`，告訴 Claude Code 從何處取得該 plugin。根據 plugin 檔案的儲存位置選擇來源。該表列出了大多數 marketplace 擁有者使用的來源。

| 來源 | 何時使用 | 最小 `source` 值 |
| :- | :- | :- |
| 相對路徑 | plugin 的檔案在 marketplace 目錄本身內 | `"./plugins/my-first-plugin"` |
| `github` | plugin 是其自己的 GitHub 儲存庫 | `{ "source": "github", "repo": "your-org/my-first-plugin" }` |
| `git-subdir` | plugin 是某個其他儲存庫的子目錄，例如 monorepo | `{ "source": "git-subdir", "url": "your-org/monorepo", "path": "tools/my-first-plugin" }` |

在 `git-subdir` 來源中，`url` 接受 git URL 或 `owner/repo` GitHub 簡寫。

plugin 也可以來自以下來源類型之一：

* `url`：任何主機上的 git 儲存庫（按 URL）
* `archive`：通過 HTTPS 下載的 zip 檔案
* `npm`：npm 套件
* `command`：通過在安裝 plugin 的機器上執行命令產生的目錄

有關每種來源類型的欄位，以及將基於 git 的來源固定到 `ref` 或 `sha`，請參閱 [Plugin 來源](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#plugin-sources)。

## 驗證和測試

當您新增 plugins 時，在每次編輯後在您的 shell 中執行 `claude plugin validate ./my-marketplace`，並在分享前從您自己機器上的 marketplace 安裝。驗證和安裝會捕捉不同的問題。

### 驗證報告的問題

`claude plugin validate` 只讀取 marketplace 目錄內的檔案。它報告：

* JSON 語法錯誤，如 `json: Invalid JSON syntax: <reason>`
* 遺漏的必需欄位，例如 `owner: Invalid input`
* 違反[marketplace 參考](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#top-level-fields)中命名規則的 marketplace 或 plugin 名稱
* 包含 `..` 的相對 `source`
* 頂層或 plugin 項目中的未知欄位，作為警告
* 每個相對路徑 plugin 的 `plugin.json` 中的問題，如 `plugins[N] plugin.json → <field>: <message>`

有關 `validate` 可以列印的每條訊息，請參閱[驗證訊息](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#validation-messages)。有關其旗標和結束代碼，請參閱 [`plugin validate`](https://code.claude.com/docs/zh-TW/plugins/cli-reference#plugin-validate)。

### 新增或安裝時出現的問題

`claude plugin validate` 不報告的問題在您新增 marketplace 或從中安裝時出現：

* **當您新增 marketplace 時**：確切的[官方 marketplace 名稱](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#reserved-names)，例如 `claude-plugins-official`，通過驗證。當您新增具有其中一個名稱的 marketplace 時，Claude Code 拒絕它，並顯示以 `The name '<name>' is reserved for official Anthropic marketplaces` 開頭的訊息。
* **當您安裝 plugin 時**：
  * Claude Code 在您安裝 plugin 時首先取得 `github`、`git-subdir` 或其他遠端來源，因此錯誤的 `repo` 或 `path` 會在那時出現。
  * 相對 `source` 的目錄不存在也會在安裝時失敗，並顯示 `Source path does not exist: <path>`。

### 測試對 plugin 的編輯

在[逐步解說](#create-a-marketplace)中，您從具有相對路徑 `source` 的本機目錄新增了 `my-marketplace`。使用該設定，Claude Code 直接從 `my-marketplace/plugins/` 讀取 plugin 的檔案。您的編輯在下一個工作階段開始時或當您在工作階段中執行 `/reload-plugins` 時生效，無需更改 plugin 的 `version`。

從您託管的 marketplace 安裝的人會在 plugin 快取中獲得副本。有關他們如何接收新版本，請參閱[保持使用者最新](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md#keep-users-up-to-date)。

### 移除 marketplace 以重新開始

若要移除所有內容並重新開始，請在您的 shell 中執行 `claude plugin marketplace remove my-marketplace`。該命令移除 marketplace 並卸載其 plugins。

## 託管您的 marketplace

一旦您可以從市集在您自己的機器上安裝外掛，如[建立市集](#create-a-marketplace) 中所示，請將市集目錄推送到 git 主機。推送之前，請為市集設定一個其他作者不太可能選用的頂層 `name`，因為使用者[無法擁有兩個同名的市集](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#marketplace-file)。

您的隊友然後在他們的 shell 中為 GitHub 儲存庫執行 `claude plugin marketplace add <owner>/<repo>`，或使用儲存庫 URL 執行相同命令。然後他們按名稱安裝 plugin，如[逐步解說](#create-a-marketplace)中所示。

有關私有儲存庫存取、更新、版本控制以及重新命名或移除項目，請參閱[託管和維護 marketplace](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md)。

## 後續步驟

* [託管和維護 marketplace](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md)：選擇主機、保持使用者最新，並安全地重新命名或移除 plugins
* [Marketplace 參考](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md)：`marketplace.json` 欄位和來源類型
* [為您的組織管理 plugins](https://code.claude.com/docs/zh-TW/plugins/org.md)：在每台機器上要求您的 marketplace 及其 plugins
* [按相關性建議 plugins](https://code.claude.com/docs/zh-TW/plugins/relevance.md)：當工作階段匹配時，讓 Claude Code 建議來自您的 marketplace 的 plugin

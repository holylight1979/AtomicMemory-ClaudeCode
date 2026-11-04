<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/plugins/marketplace-reference | lastmod: 2026-10-25 | section: Plugins / Reference -->
> 來源：https://code.claude.com/docs/zh-TW/plugins/marketplace-reference（官方 zh-TW，lastmod 2026-10-25）｜分類：Plugins › Reference｜EN 摘要：Complete reference for marketplace.json fields, plugin entries, and the plugin and marketplace source objects, with where each is valid.

# Marketplace 參考

> marketplace.json 欄位、外掛程式項目和外掛程式與 marketplace 來源物件的完整參考，包括每個欄位的有效位置。

`marketplace.json` 是定義外掛程式 marketplace 的檔案。它包含 marketplace 的名稱、其擁有者，以及每個外掛程式的一個項目。每個項目的外掛程式來源說明 Claude Code 從何處擷取該外掛程式。

marketplace 來源是一個單獨的物件，說明 Claude Code 從何處擷取 marketplace 檔案本身。您在設定中寫入一個，或當您執行 `claude plugin marketplace add` 時 Claude Code 會建立一個。

此參考適用於需要確切欄位名稱或值的 marketplace 維護者，以及需要知道哪些 `source` 值在 [`extraKnownMarketplaces`](https://code.claude.com/docs/zh-TW/settings-reference#extraknownmarketplaces)、[`strictKnownMarketplaces`](https://code.claude.com/docs/zh-TW/settings-reference#strictknownmarketplaces) 和 [`blockedMarketplaces`](https://code.claude.com/docs/zh-TW/plugins/org#restrict-what-users-can-install) 中有效的管理員。

> [!NOTE]
>
> 這些情況在其他頁面上涵蓋：
>
> * **建立或託管 marketplace**：請參閱 [Create a marketplace](https://code.claude.com/docs/zh-TW/plugins/create-marketplace.md) 和 [Host and maintain a marketplace](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md)
> * **允許清單和封鎖清單配方**：請參閱 [Manage plugins for your organization](https://code.claude.com/docs/zh-TW/plugins/org.md)

尋找您正在寫入或讀取的部分：

* **marketplace 檔案**：[頂層欄位](#top-level-fields) 和 [外掛程式項目](#plugin-entries)
* **項目的 `source`**：[Plugin sources](#plugin-sources)
* **設定中的 `source` 物件**：[Marketplace sources](#marketplace-sources)
* **來自 [`claude plugin validate <path>`](https://code.claude.com/docs/zh-TW/plugins/cli-reference) 的輸出**：[Validation messages](#validation-messages)，將每個訊息對應到它命名的欄位

## Marketplace 檔案

在您的 marketplace 目錄中的 `.claude-plugin/marketplace.json` 處儲存 marketplace 檔案。如果您將檔案保存在存放庫中的其他位置，使用者必須在 [`extraKnownMarketplaces`](https://code.claude.com/docs/zh-TW/settings-reference#extraknownmarketplaces) 中宣告 marketplace，並在其來源上設定 `path`，因為 `claude plugin marketplace add` 沒有此選項。

包含 `.claude-plugin/` 的目錄稱為 marketplace 根目錄，每個相對外掛程式來源都從它解析，而不是從 `.claude-plugin/`。

每個使用者每個 `name` 註冊一個 marketplace，因此使用者一次不能有兩個同名的已註冊 marketplace。

Claude Code 會忽略未知的頂層鍵或外掛程式項目鍵，而不是拒絕它，因此拼寫錯誤會無聲地載入。`claude plugin validate` 將每個未知鍵報告為警告。

### 保留名稱

您不能為您的 marketplace 指定以下任何名稱：

* **官方 marketplace 名稱**：`claude-code-marketplace`、`claude-code-plugins`、`claude-plugins-official`、`anthropic-marketplace`、`anthropic-plugins`、`agent-skills`、`anthropic-agent-skills`、`life-sciences`、`knowledge-work-plugins`、`claude-for-legal`、`claude-for-financial-services`、`financial-services-plugins`、`first-party-plugins` 和 `claude-tag-plugins`。除非 marketplace 來自 `github.com/anthropics/` 下的 `github` 或 `git` [marketplace 來源](#marketplace-sources)，否則保留。
* **社群 marketplace 名稱**：`claude-community`、`claude-plugins-community` 和 `healthcare`。在與官方名稱相同的規則下保留。
* **外掛程式目錄名稱**：`anthropic-plugin-directory` 和 `claude-plugin-directory`。在與官方名稱相同的規則下保留。
* **冒充官方 marketplace 的名稱**：名稱如 `official-claude-plugins` 或 `claude-plugins-v2`，以及任何包含非 ASCII 字元的名稱。錯誤是 `Marketplace name impersonates an official Anthropic/Claude marketplace`。名稱中的控制或雙向格式化字元也會報告 `Marketplace name cannot contain control or bidirectional-formatting characters`。已在此類名稱下註冊的 marketplace 停止載入，連同其外掛程式。
* **保留名稱的另一種拼寫**：與保留名稱的拼寫不同，只是尾部有點，或用下劃線以外的符號代替連字號，因此 `claude.code.plugins` 計為 `claude-code-plugins`。新增 marketplace 失敗，錯誤為 [`is another spelling of "<reserved>", a reserved marketplace name`](https://code.claude.com/docs/zh-TW/errors#marketplace-name-is-another-spelling-of-a-reserved-name)，而已使用此類名稱註冊的 marketplace 會停止載入。此檢查需要 Claude Code v2.1.280 或更新版本。
* **Claude Code 用於不來自 marketplace 的外掛程式的名稱**：`inline` 用於使用 [`--plugin-dir`](https://code.claude.com/docs/zh-TW/cli-reference) 載入的外掛程式，`builtin` 用於內建外掛程式，`skills-dir` 用於從 [`.claude/skills/`](https://code.claude.com/docs/zh-TW/skills) 自動載入的外掛程式，`synced` 用於從您的 claude.ai 帳戶同步的外掛程式。`claude-plugin-test` 也被保留。`skills-dir` 也在 `strictKnownMarketplaces` 和 `blockedMarketplaces` 中顯示為 `{"source": "skills-dir"}`，在 [Source values valid only in policy lists](#source-values-valid-only-in-policy-lists) 下描述。
* **`npm`、`pip`、`uv`、`cargo`、`github` 和 `gh`**：以任何大小寫保留。此檢查需要 Claude Code v2.1.275 或更新版本。
* **每個 JavaScript 物件都具有的成員名稱**：`constructor`、`hasOwnProperty`、`isPrototypeOf`、`propertyIsEnumerable`、`toLocaleString`、`toString` 和 `valueOf`。`claude plugin marketplace add` 會拒絕使用其中之一的 marketplace，錯誤為 [`Claude Code reserves this name and cannot register a marketplace under it`](https://code.claude.com/docs/zh-TW/plugins/troubleshooting#claude-code-reserves-this-name)。此檢查需要 Claude Code v2.1.296 或更新版本。
* **以 `claudeai-` 開頭的名稱**：為託管在 claude.ai 上的 marketplace 保留。`claude plugin marketplace add` 拒絕任何其他使用一個的 marketplace，錯誤為 `Cannot add marketplace "<name>": names starting with "claudeai-" are reserved for marketplaces hosted on claude.ai`。
* **已註冊 GitHub marketplace 的下載資料夾 `<owner>-<repo>`**：對於從 `github` 來源（例如 `acme/x-tools`）新增的 marketplace，無論該 marketplace 本身的 `name` 為何，Claude Code 都會透過名為 `acme-x-tools` 的資料夾下載它。當該 marketplace 以 `acme-x-tools` 以外的名稱註冊時，`claude plugin marketplace add` 會在下載另一個名為 `acme-x-tools` 的 marketplace 後拒絕它，並報告 `Can't use the marketplace name "acme-x-tools"`。此檢查需要 Claude Code v2.1.290 或更新版本。

當已註冊的 marketplace 因其名稱模仿官方名稱而停止載入時，`claude plugin list` 和 `/plugin` 報告 `Claude Code refuses the marketplace name "<name>"`。該訊息告訴您移除 marketplace。移除它也會解除安裝其外掛程式，並刪除其資料、選項和密鑰。此具名拒絕訊息需要 Claude Code v2.1.282 或更新版本。

如果設定檔以內嵌方式宣告該 marketplace，該訊息會告訴您先重新命名其項目，再移除舊名稱。如需相關步驟，請參閱 [Claude Code refuses the marketplace name](https://code.claude.com/docs/zh-TW/errors.md#claude-code-refuses-the-marketplace-name)。此訊息在 Claude Code v2.1.292 或更新版本中會列出這些步驟。

## 頂層欄位

該表列出 Claude Code 從 `marketplace.json` 讀取的每個鍵。`name`、`owner` 和 `plugins` 是必需的。

| 欄位 | 類型 | 描述 |
| :- | :- | :- |
| `name` | 字串 | Marketplace 識別碼：字母、數字、`.`、`_` 和 `-`，以字母或數字開頭，且不得包含 `..`。`claude plugin validate` 會讓任何其他名稱驗證失敗，因為 Claude Code [無法從使用此類名稱的市集安裝外掛](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#cannot-install-plugins-from-a-marketplace-with-this-name)。使用者安裝外掛時，會在 [外掛 ID](https://code.claude.com/docs/zh-TW/plugins/loading.md#find-where-a-plugin-came-from)（例如 `my-plugin@my-marketplace`）中的 `@` 後面輸入此名稱。請參閱 [保留名稱](#reserved-names) |
| `owner` | 物件 | 維護者資訊。`name` 是必需的；`email` 和 `url` 是可選的 |
| `plugins` | 陣列 | [外掛程式項目](#plugin-entries)。每個項目都單獨驗證，因此一個無效項目不會導致 marketplace 失敗 |
| `$schema` | 字串 | JSON Schema URL 用於編輯器自動完成。在載入時忽略 |
| `description` | 字串 | 向使用者顯示的 Marketplace 描述。`claude plugin validate` 在缺少時發出警告 |
| `version` | 字串 | Marketplace 資訊清單版本 |
| `metadata.description`、`metadata.version` | 字串 | `description` 和 `version` 的替代位置 |
| `metadata.pluginRoot` | 字串 | 裸外掛程式來源名稱解析的目錄。請參閱 [Relative path plugin source](#relative-path-plugin-source)。需要 Claude Code v2.1.239 或更新版本 |
| `forceRemoveDeletedPlugins` | 布林值 | 當 `true` 時，您從 `plugins` 中移除的外掛程式會在使用者的機器上解除安裝。請參閱 [Host and maintain a marketplace](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md) |
| `allowCrossMarketplaceDependenciesOn` | 字串陣列 | 其外掛程式可能被安裝為此 marketplace 外掛程式依賴項的 Marketplace 名稱。當您安裝外掛程式時，只有該外掛程式自己的 marketplace 中的清單適用於其整個依賴鏈。請參閱 [Plugin dependencies](https://code.claude.com/docs/zh-TW/plugins/dependencies.md) |
| `renames` | 物件 | 從前一個外掛程式 `name` 到其目前名稱的對應，或對於您移除的外掛程式為 `null`。請參閱 [Host and maintain a marketplace](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md) |

## 外掛程式項目

`marketplace.json` 的頂層 `plugins` 陣列中的每個物件命名一個外掛程式並說明從何處擷取它。`name` 和 `source` 是必需的。

除了[目錄列表欄位](https://code.claude.com/docs/zh-TW/plugins/manifest-reference.md#directory-listing-fields)之外，項目也接受每個 [`plugin.json` 欄位](https://code.claude.com/docs/zh-TW/plugins/manifest-reference)，例如 `description`、`version`、`author`、`commands` 和 `hooks`。有關這些欄位何時適用，請參閱 [How an entry combines with plugin.json](#entry-and-plugin-json)。

該表列出項目自己的欄位和資訊清單欄位，其含義在項目中改變。

| 欄位 | 類型 | 描述 |
| :- | :- | :- |
| `name` | 字串 | 外掛程式識別碼：字母、數字、`.`、`_` 和 `-`，以字母或數字開頭。`claude plugin validate` 會拒絕其他名稱，Claude Code 無法安裝。使用者在安裝時在 `@` 前輸入它，即使外掛程式自己的 `plugin.json` 設定了不同的 `name` |
| `source` | 字串或物件 | 從何處擷取外掛程式。請參閱 [Plugin sources](#plugin-sources) |
| `description` | 字串 | 在 [`/plugin`](https://code.claude.com/docs/zh-TW/plugins/install) 清單和詳細資訊中顯示 |
| `version` | 字串 | 外掛程式的版本字串。當 `plugin.json` 也設定 `version` 時，`plugin.json` 優先，`claude plugin validate` 發出警告。請參閱 [Plugin loading reference](https://code.claude.com/docs/zh-TW/plugins/loading.md) |
| `category` | 字串 | 用於組織目錄的自由格式類別 |
| `tags` | 字串陣列 | 用於搜尋的自由格式標籤 |
| `strict` | 布林值 | 預設 `true`。`plugin.json` 是否是外掛程式元件的決定性來源。請參閱 [Strict mode](#strict-mode) |
| `relevance` | 物件 | 告訴 Claude Code 何時建議外掛程式的訊號。請參閱 [Recommend plugins for your org](https://code.claude.com/docs/zh-TW/plugins/relevance.md) |
| `dependencies` | 陣列 | 必須為此外掛程式啟用的外掛程式。每個項目是 `"name"`、`"name@marketplace"` 或物件。請參閱 [Plugin dependencies](https://code.claude.com/docs/zh-TW/plugins/dependencies.md) |
| `defaultEnabled` | 布林值 | 預設 `true`。當使用者未在 [`enabledPlugins`](https://code.claude.com/docs/zh-TW/settings-reference#enabledplugins) 中設定時，外掛程式一開始是否為啟用狀態。項目值優先於 `plugin.json` |
| `displayName` | 字串 | 在 UI 中顯示的人類可讀名稱。當項目和外掛程式的 `plugin.json` 都未設定時，使用者看到外掛程式的 `name` |
| `metadata` | 物件 | 用於您自己欄位的自由格式物件。Claude Code 不讀取它。需要 Claude Code v2.1.222 或更新版本 |
| `headers` | 物件 | Claude Code 在下載此項目的 [archive](#archive-plugin-source) 時發送的 HTTP 標頭。此處設定的標頭替換來自 marketplace 來源的 [`headers`](#fields-by-type) 的同名標頭。需要 Claude Code v2.1.238 或更新版本 |
| `headersHelper` | 字串 | 列印此項目的存檔下載標頭的命令，作為一個 JSON 物件，用於會過期的憑證。項目也必須設定 [`"strict": false`](#strict-mode)。需要 Claude Code v2.1.238 或更新版本。請參閱 [Authenticate archive downloads](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md#authenticate-archive-downloads) |

### 項目如何與 plugin.json 結合

項目的欄位以不同方式應用於已擷取的外掛程式，該外掛程式有自己的 `.claude-plugin/plugin.json` 和沒有的外掛程式：

* **沒有 `plugin.json`**：無論 `strict` 如何，項目都是資訊清單。項目中的每個資訊清單欄位都適用，包括 [`mcpServers`、`lspServers`、`userConfig` 和 `channels`](https://code.claude.com/docs/zh-TW/plugins/manifest-reference)。
* **`plugin.json` 存在**：`plugin.json` 是資訊清單。[Strict mode](#strict-mode) 決定項目的六個元件欄位 `commands`、`agents`、`skills`、`hooks`、`outputStyles` 和 `themes` 是與其結合還是作為衝突被拒絕。項目 `mcpServers`、`lspServers`、`userConfig` 和 `channels` 不適用。在 `plugin.json` 中宣告它們。

#### 項目中的 hook

將項目 `hooks` 寫為內聯物件，將 hook 事件名稱對應到 matcher 陣列。如果您寫入檔案路徑或陣列，`claude plugin validate` 會通過它。這些 hook 永遠不會執行，Claude Code 為外掛程式報告 `not yet supported in a marketplace entry` 錯誤。將基於檔案的 hook 放在外掛程式自己的 [`hooks/hooks.json`](https://code.claude.com/docs/zh-TW/plugins/components) 或 `plugin.json` 中。

#### 顯示欄位

項目和外掛程式自己的 `plugin.json` 都可以設定顯示欄位 `displayName`、`description`、`author`、`homepage`、`repository`、`license` 和 `keywords`。使用者在外掛程式清單和詳細資訊中看到這些值，在安裝前後：

* 對於您在項目上設定的欄位，使用者看到項目的值，即使 `plugin.json` 設定了不同的值。
* 對於項目未設定的欄位，使用者看到 `plugin.json` 值。

在安裝前，Claude Code 只能為具有 [relative-path source](#relative-path-plugin-source) 的項目讀取 `plugin.json`，其外掛程式檔案在 marketplace 內。對於具有任何其他來源類型的項目，使用者在安裝外掛程式之前只看到項目自己的欄位。

### Strict mode

`strict` 決定當已擷取的外掛程式有自己的 `plugin.json` 且項目也宣告任何 [component fields](#entry-and-plugin-json) 時會發生什麼：`commands`、`agents`、`skills`、`hooks`、`outputStyles` 或 `themes`。使用 `strict: true`（預設值），Claude Code 將項目的元件欄位附加到 `plugin.json`，除了 `hooks`，其 matcher 會按事件替換資訊清單的 matcher。使用 `strict: false`，宣告任何元件欄位的項目是衝突，外掛程式無法載入。該表顯示 `strict`、`plugin.json` 和項目的元件欄位的每個組合。

| `strict` | `plugin.json` | 項目元件欄位 | 結果 |
| :- | :- | :- | :- |
| 任何 | 不存在 | 任何 | 項目是資訊清單 |
| `true`（預設值） | 存在 | 任何 | `plugin.json` 是權威。Claude Code 將項目的元件欄位附加到它，除了 `hooks`，其 matcher [replace the manifest's per event](https://code.claude.com/docs/zh-TW/plugins/manifest-reference.md#how-entry-fields-combine-with-plugin-json) |
| `false` | 存在 | 無 | `plugin.json` 是資訊清單，與 `true` 相同 |
| `false` | 存在 | 一個或多個 | 衝突。外掛程式無法載入，錯誤為 `Plugin <name> has conflicting manifests: both plugin.json and marketplace entry specify components` |

## Plugin 來源

Plugin 項目的 `source` 說明 Claude Code 從何處取得該 plugin。它可以是相對路徑字串，或是一個物件，其 `source` 鍵名指定類型，因此項目看起來像 `"source": { "source": "github", "repo": "your-org/formatter" }`。

下表列出每個 plugin 來源類型及其欄位。

| 類型 | 欄位 | 備註 |
| :- | :- | :- |
| 相對路徑 | 字串本身 | marketplace 內的目錄，從 marketplace 根目錄解析。必須以 `./` 開頭，除非您在 [`metadata.pluginRoot` 下寫入裸名](#relative-path-plugin-source)。`"."` 本身表示根目錄 |
| `github` | `repo`、`ref`、`sha` | GitHub 儲存庫，格式為 `owner/repo` |
| `url` | `url`、`ref`、`sha` | 任何 git 儲存庫的 URL |
| `git-subdir` | `url`、`path`、`ref`、`sha` | git 儲存庫的一個子目錄，使用稀疏檢出（sparse checkout）取得 |
| `npm` | `package`、`version`、`registry` | npm 登錄套件或 tarball 連結，使用您的 npm 用戶端取得並解包，不執行安裝指令碼 |
| `archive` | `url`、`sha256` | HTTPS 上的 Zip 檔案。需要 Claude Code v2.1.224 或更新版本 |
| `command` | `command`、`timeout`、`mode` | 由 Claude Code 在使用者機器上執行的命令列印的目錄。需要 Claude Code v2.1.229 或更新版本 |

名稱 `url` 和 `github` 也是 [marketplace 來源](#marketplace-sources) 類型，其中 `url` 表示直接連結到 `marketplace.json` 檔案，而非 git 儲存庫。`git` 僅作為 marketplace 來源存在，`npm` 同時作為兩者存在。`git-subdir`、`archive` 和 `command` 僅作為 plugin 來源存在。

對於 marketplace 儲存庫本身子目錄中的 plugin，使用相對路徑。對於其他儲存庫的子目錄，使用 `git-subdir`。

`github`、`url` 和 `git-subdir` 來源共享 `ref` 和 `sha` 欄位：

* **`ref`**：分支或標籤。預設為儲存庫的預設分支。
* **`sha`**：完整的 40 字元小寫提交 SHA。當您同時設定 `ref` 和 `sha` 時，Claude Code 會檢出 `sha`。在大多數 git 主機上，包括 GitHub、GitLab 和 Bitbucket，這表示即使上游的分支或標籤已被刪除，只要提交仍可從儲存庫到達，安裝就會成功。某些伺服器（例如 AWS CodeCommit）不支援按 SHA 取得提交。在這些伺服器上，`ref` 仍必須存在，且固定的提交必須可從其到達。

有關每種類型如何取得、快取和版本化的資訊，請參閱 [Plugin 載入參考](https://code.claude.com/docs/zh-TW/plugins/loading.md)。

### 相對路徑 plugin 來源

路徑從 marketplace 根目錄解析。`./plugins/formatter` 是 `<root>/plugins/formatter`，即使 marketplace 檔案在 `<root>/.claude-plugin/` 中。

包含 `..` 的路徑會驗證失敗。在 macOS 和 Linux 上，Claude Code 拒絕在前導 `./` 之後任何位置包含反斜線的項目路徑，因此請使用正斜線寫入路徑。

```json theme={null}
{ "name": "formatter", "source": "./plugins/formatter" }
```

相對路徑僅在 Claude Code 擁有 marketplace 檔案時才會解析，因此請檢查 [marketplace 來源](#marketplace-sources) 類型：

* **`github`、`git`、`file` 和 `directory`**：Claude Code 擁有 marketplace 檔案。
* **`url`**：Claude Code 僅取得 `marketplace.json`，因此相對路徑無法解析。為每個 plugin 提供物件來源，例如 `github` 或 `git-subdir`。
* **`settings`**：相對路徑被直接拒絕。

#### marketplace 儲存庫中的 Git 子模組

當 Claude Code 複製 marketplace 儲存庫時，只會取得存放 plugin 檔案的 git 子模組。需要 Claude Code v2.1.295 或更新版本。

較早的版本會取得所有子模組，包括巢狀子模組。如果儲存庫有大型子模組，Claude Code 在取得時可能會超過[複製逾時](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#git-clone-timed-out-after-120s)。

對於子目錄中的 plugin，例如 `./plugins/formatter`，Claude Code 會在以下情況取得子模組：

* **plugin 位於子模組內**：子模組是 plugin 的目錄或其上層目錄
* **子模組位於 plugin 內**：子模組位於 plugin 目錄下的任何位置
* **符號連結指向子模組內**：提交至儲存庫的連結，其目標位於子模組中

位於 marketplace 根目錄的 plugin（使用 `"source": "./"`）會取得儲存庫中的所有子模組，或完全不取得。當以下任一項指向任何子模組內時，Claude Code 會取得所有子模組：

* **元件目錄**：根目錄下存放 plugin 元件的目錄，例如 `skills/`、`hooks/` 或 `bin/`
* **plugin 設定中的路徑**：plugin 的 marketplace 項目、其 `plugin.json`，或 `.mcp.json`、`hooks/hooks.json` 等設定檔中的路徑
* **符號連結**：提交至儲存庫的連結
* **plugin 檔案中的文字**：寫在設定檔或元件目錄下檔案中的子模組路徑，例如 `vendor/tool`

當以上皆不符合時，Claude Code 不會為該 plugin 取得任何子模組。同時是專案又是 plugin 的儲存庫，通常有僅供專案建置使用的子模組，此規則會將其排除。

在無法判斷哪些子模組存放 plugin 檔案的情況下，Claude Code 也會取得所有子模組，例如：

* **根目錄下的 `SKILL.md`**：此時整個儲存庫就是一個 skill 的目錄
* **Claude Code 無法讀取的檔案**：marketplace 檔案、plugin 的某個設定檔，或 `.gitmodules`

如果您使用 `--sparse` 新增 marketplace，或其來源設定了 `sparsePaths`，Claude Code 只會檢出其中指定的目錄，且不取得任何子模組。較早的版本也是如此。

若要讓 plugin 未使用的子模組不納入複製，請參閱[將未使用的子模組排除在複製之外](https://code.claude.com/docs/zh-TW/plugins/create-marketplace.md#keep-unused-submodules-out-of-the-clone)。

#### pluginRoot 下的裸名

裸名是單個目錄名稱，不含 `/`，例如 `"formatter"`。若要寫入裸名而非 `./` 路徑，請將 [`metadata.pluginRoot`](#top-level-fields) 設定為它們解析的目錄。使用 `"pluginRoot": "./plugins"`，`"source": "formatter"` 解析為 `./plugins/formatter`。需要 Claude Code v2.1.239 或更新版本。

`metadata.pluginRoot` 有以下限制：

* 它本身必須是 marketplace 內的相對路徑。
* 它對已以 `./` 開頭的來源無效。
* 包含 `/` 的來源（例如 `team-a/formatter`）不是裸名，即使設定了 `metadata.pluginRoot` 也仍需要 `./` 前綴。

### github plugin 來源

`repo` 採用 `owner/repo` 格式。`ref` 和 `sha` 是選用的。

```json theme={null}
{
  "name": "formatter",
  "source": {
    "source": "github",
    "repo": "your-org/formatter",
    "ref": "v2.0.0",
    "sha": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"
  }
}
```

### url plugin 來源

`url` 是完整的 git URL：`https://`、`http://`、`file://` 或 `git@`。不需要 `.git` 後綴，因此 Azure DevOps 和 AWS CodeCommit URL 可以按原樣使用。此類型不採用 `owner/repo` 簡寫。

```json theme={null}
{
  "name": "formatter",
  "source": {
    "source": "url",
    "url": "https://gitlab.example.com/your-group/formatter.git",
    "ref": "main"
  }
}
```

### git-subdir plugin 來源

`url` 接受完整的 git URL 或 GitHub `owner/repo` 簡寫。`path` 是保存 plugin 的子目錄，Claude Code 僅檢出該子目錄。透過 `https` 或 SSH URL 時，Claude Code 會向伺服器要求部分複製（partial clone），因此從支援部分複製的主機安裝時，大型 monorepo 中的 plugin 無需下載儲存庫的其餘部分即可安裝。

```json theme={null}
{
  "name": "formatter",
  "source": {
    "source": "git-subdir",
    "url": "https://github.com/your-org/monorepo.git",
    "path": "tools/formatter"
  }
}
```

### npm plugin 來源

`npm` 來源採用以下欄位：

* `package`：登錄套件名稱，例如 `@your-org/formatter`；附加版本的名稱，例如 `@your-org/formatter@2.0.0`；或指向套件 tarball 檔案的 `https` 連結
* `version`：版本、semver 範圍或 dist-tag，當 `package` 是未附加版本的套件名稱時使用。省略則取得 `latest`
* `registry`：不在預設登錄中的套件的登錄 URL

Claude Code 使用您的 npm 用戶端取得套件。套件的安裝指令碼（例如 `preinstall` 或 `postinstall`）永遠不會執行，其相依性在取得期間不會安裝。如果套件在其 `package.json` 旁有支援的鎖定檔案，Claude Code 會在單獨的步驟中安裝這些 [Node.js 套件相依性](https://code.claude.com/docs/zh-TW/plugins/loading.md#node-js-package-dependencies)，同樣禁用指令碼。

Claude Code 在取得任何內容之前會先檢查 `package` 值。被拒絕的值會使安裝失敗，並顯示指出該值及原因的訊息。被拒絕的值包括：

* **git 位址、資料夾或 `file:` 路徑，或 `npm:` 別名**：對於 git 儲存庫，請使用 [`github`、`url` 或 `git-subdir` 來源](#plugin-sources)；對於 marketplace 中的資料夾，請使用相對路徑；對於別名，請使用套件本身的名稱
* **github.com、gist.github.com、gitlab.com、bitbucket.org 或 git.sr.ht 上的 tarball 連結**：即使連結是 GitHub 發行版下載也會被拒絕，除非它是 `gitlab.com/api/v4/` 下的 GitLab npm 登錄連結
* **透過 `http` 的 tarball 連結**：會被拒絕，除非它指向進行安裝之使用者自己的預設 npm 登錄

`registry` URL 必須使用 `https`，除非它是進行安裝之使用者自己的預設 npm 登錄。若使用任何其他 `http` 登錄，安裝會在 npm 與其連線之前失敗。

```json theme={null}
{
  "name": "formatter",
  "source": {
    "source": "npm",
    "package": "@your-org/formatter",
    "version": "^2.0.0",
    "registry": "https://npm.example.com"
  }
}
```

### archive plugin 來源

`url` 必須使用 `https://`，且不能指向環回、連結本地或雲端中繼資料主機。有關下載的大小、逾時、重新導向和提取限制，請參閱[保持在託管檔案的下載限制內](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md#stay-within-the-download-limits-for-hosted-files)。

plugin 根目錄可能在 zip 的頂部或下一個目錄。

`sha256` 是檔案的摘要，為 64 個十六進位字元，大寫或小寫。當您設定它時，Claude Code 拒絕不符合的下載。

```json theme={null}
{
  "name": "formatter",
  "source": {
    "source": "archive",
    "url": "https://artifacts.example.com/formatter-2.0.0.zip",
    "sha256": "6bfa50e3d2e00c052b46abe51fff89346ac803e45771f76dcf6df1ab74cca5e1"
  }
}
```

### command plugin 來源

當安裝在使用者機器上的工具產生 plugin 目錄時，使用 `command` 來源，例如為使用者選擇的工具鏈呈現其 plugin 的 IDE。Claude Code 在使用者安裝或更新 plugin 時執行命令，並[每個工作階段執行一次](https://code.claude.com/docs/zh-TW/plugins/loading.md#when-a-command-source-re-runs)，因此使用者無需重新安裝即可獲得工具的變更輸出。

`command` 來源採用以下欄位：

* `command`：shell 命令，列印 plugin 目錄的絕對路徑作為一行並退出 0。Claude Code 在執行前向使用者顯示整個字串以供審查。將其寫為可列印的 ASCII，最多 500 個字元，不含四個或更多空格的連續。
* `timeout`：1 到 600 秒的整數。預設為 60。
* `mode`：`copy`（預設）或 `link`。請參閱[複製模式和連結模式](#copy-mode-and-link-mode)。

```json theme={null}
{
  "name": "formatter",
  "source": {
    "source": "command",
    "command": "my-tool claude-plugin-path",
    "timeout": 120
  }
}
```

有關使用者如何接受命令的資訊，請參閱[從您的 shell 安裝](https://code.claude.com/docs/zh-TW/plugins/install.md#install-from-your-shell)。有關您變更命令後使用者看到的內容，請參閱[變更 command 來源的命令](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md#change-the-command-of-a-command-source)。管理員使用 [`disableCommandPluginSources`](https://code.claude.com/docs/zh-TW/settings-reference#disablecommandpluginsources) 關閉 command 來源。

#### 命令必須執行的操作

編寫命令以符合以下要求：

* **Shell 和工作目錄**：Claude Code 通過 `sh` 或在 Windows 上通過 `cmd.exe` 從使用者的主目錄執行命令。提供絕對路徑或 `PATH` 上的命令。
* **輸出**：在 stdout 上列印恰好一行，即 plugin 目錄的絕對路徑，並在 `timeout` 秒內退出 0。
* **目錄內容**：目錄在命令退出時保存完整的 plugin。路徑可能因執行而異。

#### 導致安裝或更新失敗的輸出

當命令退出非零、執行時間超過 `timeout` 或列印除一個絕對路徑以外的任何內容時，安裝或更新失敗。當列印的目錄是以下之一時，它也會失敗：

* **無 plugin 內容**：列印的目錄在其頂層沒有 plugin 內容，例如 `.claude-plugin/` 目錄或 `skills/`、`commands/`、`agents/` 或 `hooks/` 目錄。
* **工作階段自己的目錄**：列印的目錄是 Claude Code 啟動的目錄或其父目錄之一。
* **網路路徑**：在 Windows 上，列印的路徑是 UNC 路徑。
* **太大而無法複製**：在複製模式中，目錄大於 256 MiB 或有超過 20,000 個項目。

#### 複製模式和連結模式

`mode` 決定 Claude Code 是複製列印的目錄還是就地使用它：

* **`copy`**：Claude Code 將目錄複製到 plugin 快取中，並從複製檔案的雜湊衍生 [plugin 版本](https://code.claude.com/docs/zh-TW/plugins/loading.md#how-claude-code-computes-the-version)。您的工具可以在命令退出後刪除或重寫目錄。產生相同檔案的重新執行計為最新。
* **`link`**：Claude Code 使用列印目錄的每個頂層項目的連結填充 plugin 的快取項目，並就地載入檔案。不複製任何內容，不雜湊檔案內容，大小限制不適用。將其用於太大而無法複製的目錄，例如呈現的 SDK 匯出。

連結模式 plugin 有以下要求：

* **保持目錄就位**：Claude Code 在每次啟動時通過連結載入 plugin，因此列印的目錄必須保持在原位，只要 plugin 保持安裝狀態。
* **列印不同的路徑以表示新內容**：版本來自列印目錄的真實路徑及其頂層項目，而非其內部的檔案。
* **保持頂層符號連結在目錄內**：如果頂層項目是指向列印目錄外的符號連結，安裝失敗。
* **包含 `node_modules`**：Claude Code 跳過連結模式 plugin 的 [Node.js 套件相依性安裝](https://code.claude.com/docs/zh-TW/plugins/loading.md#node-js-package-dependencies)，因此列印已包含 plugin 需要的套件的目錄。
* **在目錄內啟動的工作階段**：在列印目錄或其下方任何位置啟動的工作階段不載入 plugin。
* **不在 Windows 上**：Claude Code 拒絕在 Windows 上安裝連結模式 plugin。在那裡宣告 `"mode": "copy"`。

## Marketplace 來源

marketplace 來源說明 Claude Code 從何處擷取 `marketplace.json`。CLI 在您新增 marketplace 時為您建立一個，您自己在設定中寫入一個：

* **[`claude plugin marketplace add`](https://code.claude.com/docs/zh-TW/plugins/cli-reference)**：Claude Code 從您傳遞的字串建立來源。
* **[`extraKnownMarketplaces`](https://code.claude.com/docs/zh-TW/settings-reference#extraknownmarketplaces)**：您自己將來源寫為 `source` 物件。
* **[`strictKnownMarketplaces`](https://code.claude.com/docs/zh-TW/settings-reference#strictknownmarketplaces) 和 [`blockedMarketplaces`](https://code.claude.com/docs/zh-TW/plugins/org#restrict-what-users-can-install)**：管理員在這兩個政策清單中寫入來源。`strictKnownMarketplaces` 是允許清單，`blockedMarketplaces` 是封鎖清單。

類型名稱 `url`、`git` 和 `github` 在 marketplace 來源中的含義與在 [plugin source](#plugin-sources) 中不同：

| 類型名稱 | 作為 marketplace 來源 | 作為外掛程式來源 |
| :- | :- | :- |
| `url` | 直接連結到 `marketplace.json` 檔案，具有欄位 `url`、`headers` 和 `headersHelper` | 要複製的 git 存放庫，具有欄位 `url`、`ref` 和 `sha` |
| `git` | 要複製的 git 存放庫，具有欄位 `url`、`ref`、`path` 和 `sparsePaths` | 不存在 |
| `github` | GitHub 存放庫，具有欄位 `repo`、`ref`、`path` 和 `sparsePaths` | GitHub 存放庫，具有欄位 `repo`、`ref` 和 `sha`，沒有 `path` |

該表列出每個 marketplace 來源類型及其欄位、產生它的 `claude plugin marketplace add` 輸入，以及它在三個設定鍵中的作用。

| 類型 | 欄位 | `marketplace add` 輸入 | `extraKnownMarketplaces` | `strictKnownMarketplaces` | `blockedMarketplaces` |
| :- | :- | :- | :- | :- | :- |
| `url` | `url`、`headers`、`headersHelper` | 不匹配 git 形式的 `http://` 或 `https://` URL | 載入 | 允許相同的 URL | 封鎖相同的 URL |
| `github` | `repo`、`ref`、`path`、`sparsePaths` | `owner/repo`、`owner/repo@ref` 或 `owner/repo#ref` | 載入 | 允許相同的 `repo`、`ref` 和 `path`。`repo` 可能是 `owner/*` | 封鎖相同的，以及到相同存放庫的 `git` URL |
| `git` | `url`、`ref`、`path`、`sparsePaths` | `user@host:path` URL，或以 `.git` 結尾、包含 `/_git/` 或命名 github.com 或 gitlab.com 存放庫的 `http://` 或 `https://` URL。`#ref` 固定 ref | 載入 | 允許相同的 URL、`ref` 和 `path` | 封鎖相同的，以及相同 github.com 存放庫的其他拼寫 |
| `npm` | `package` | 未產生 | 無法載入：`NPM marketplace sources not yet implemented` | 解析但不匹配任何內容，因為沒有任何內容註冊 `npm` marketplace | 解析但不匹配任何內容 |
| `file` | `path` | `.json` 檔案的路徑 | 載入 | 允許相同的路徑 | 封鎖相同的路徑 |
| `directory` | `path` | 目錄的路徑 | 載入 | 允許相同的路徑 | 封鎖相同的路徑 |
| `settings` | `name`、`plugins`、`owner` | 未產生 | 載入 | 允許具有相同 `name` 和相同 `plugins` 的項目 | 封鎖相同的 `name` |
| `skills-dir` | 無 | 未產生 | 無法載入：`Unsupported marketplace source type` | 允許 [skills-directory plugins](https://code.claude.com/docs/zh-TW/plugins/org.md#keep-skills-directory-plugins-loading)。請參閱 [Source values valid only in policy lists](#source-values-valid-only-in-policy-lists) | 停止 skills-directory 外掛程式載入 |
| `hostPattern` | `hostPattern` | 未產生 | 無法載入：`Unsupported marketplace source type` | 允許主機匹配的 `github`、`git` 和 `url` 來源 | 封鎖這些來源 |
| `pathPattern` | `pathPattern` | 未產生 | 無法載入：`Unsupported marketplace source type` | 允許 `path` 匹配的 `file` 和 `directory` 來源 | 封鎖這些來源 |

### 按類型的欄位

該表列出每個 marketplace 來源欄位，該欄位具有預設值、約束或特定於其類型的含義。

| 欄位 | 類型 | 描述 |
| :- | :- | :- |
| `url` | `url` | 連結到 `marketplace.json` 檔案。Claude Code 僅下載該檔案，因此 marketplace 的外掛程式無法使用 [relative-path sources](#relative-path-plugin-source)。請參閱 [Stay within the download limits for hosted files](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md#stay-within-the-download-limits-for-hosted-files) 以了解大小、逾時和重新導向限制 |
| `url` | `git` | 要複製的 git 存放庫 |
| `headers` | `url` | Claude Code 使用擷取發送的 HTTP 標頭對應，用於已驗證的主機 |
| `headersHelper` | `url` | 列印標頭的命令，其值太短暫而無法在 `headers` 中列出。需要 Claude Code v2.1.238 或更新版本。請參閱 [Authenticate archive downloads](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md#authenticate-archive-downloads) |
| `repo` | `github` | 在 `marketplace add` 和 `extraKnownMarketplaces` 中，`repo` 必須命名一個存放庫。`marketplace add` 拒絕 `owner/*` 作為無效的 `owner/repo` 簡寫；在 `extraKnownMarketplaces` 中 Claude Code 按字面意思取用，複製失敗 |
| `ref` | `github`、`git` | 分支或標籤。預設為存放庫的預設分支 |
| `path` | `github`、`git` | marketplace 檔案在存放庫內的路徑。預設為 `.claude-plugin/marketplace.json` |
| `path` | `file` | marketplace 檔案本身。Claude Code 就地讀取它，並將上面兩個級別的目錄作為 marketplace 根目錄，因此將檔案保存在 `<root>/.claude-plugin/marketplace.json` |
| `path` | `directory` | marketplace 根目錄，包含 `.claude-plugin/marketplace.json` 的目錄 |
| `sparsePaths` | `github`、`git` | 用於稀疏簽出的目錄陣列，例如 `[".claude-plugin", "plugins"]`。`claude plugin marketplace add --sparse` 設定它 |
| `skipLfs` | `github`、`git` | 接受且無效果。請參閱 [Keep plugin files out of Git LFS](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md#keep-plugin-files-out-of-git-lfs) |
| `name` | `settings` | 必須等於 `extraKnownMarketplaces` 鍵，不能是 [保留名稱](#reserved-names) |
| `plugins` | `settings` | 內聯目錄，沒有託管檔案。每個項目採用 `name`、`source`、`description`、`version`、`strict`、`headers` 和 `headersHelper`。將每個項目的 `source` 寫為物件類型，因為相對路徑沒有要解析的存放庫 |

### 僅在政策清單中有效的來源值

`hostPattern`、`pathPattern`、`skills-dir` 和 `repo` 的 `owner/*` 形式僅在兩個政策清單中有效，`strictKnownMarketplaces` 和 `blockedMarketplaces`：

* **`hostPattern` 和 `pathPattern`**：Claude Code 在擷取前針對來源測試的正規表達式。
* **`skills-dir`**：不是來源。如果您設定了 `strictKnownMarketplaces` 但沒有 `{"source": "skills-dir"}` 項目，[skills-directory plugins](https://code.claude.com/docs/zh-TW/plugins/org.md#keep-skills-directory-plugins-loading) 會停止載入。如果您使用 [`strictPluginOnlyCustomization`](https://code.claude.com/docs/zh-TW/settings-reference#strictpluginonlycustomization) 鎖定任何自訂類型，無論該項目是否存在，它們都會停止載入。
* **`owner/*`**：作為 `github` `repo` 值，匹配恰好該 GitHub 擁有者下的每個存放庫。需要 Claude Code v2.1.223 或更新版本。

有關匹配順序、確切 `ref` 語義和配方，請參閱 [Manage plugins for your organization](https://code.claude.com/docs/zh-TW/plugins/org.md)。

### 設定中的來源物件

`extraKnownMarketplaces` 值是從 marketplace 名稱到具有 `source` 的物件的對應。此項目從其 `main` 分支的 git 存放庫註冊 marketplace：

```json theme={null}
{
  "extraKnownMarketplaces": {
    "your-marketplace": {
      "source": {
        "source": "git",
        "url": "https://git.example.com/your-org/your-marketplace.git",
        "ref": "main"
      }
    }
  }
}
```

`strictKnownMarketplaces` 和 `blockedMarketplaces` 是來源物件的陣列。此允許清單允許一個 GitHub 擁有者和一個內部主機：

```json theme={null}
{
  "strictKnownMarketplaces": [
    { "source": "github", "repo": "your-org/*" },
    { "source": "hostPattern", "hostPattern": "^git\\.example\\.com$" }
  ]
}
```

## 驗證訊息

`claude plugin validate <path>` 接受 marketplace 根目錄或 marketplace 檔案本身。它會列印錯誤和警告。如需結束代碼和 `--strict`，請參閱 [plugin validate](https://code.claude.com/docs/zh-TW/plugins/cli-reference.md#plugin-validate)。

訊息會以索引命名外掛程式項目，寫作 `plugins.1.source` 或 `plugins[1].source`。

以項目索引和 `plugin.json →` 為前綴的訊息，例如 `plugins[2] plugin.json →`，是關於該外掛程式自身的檔案。[`claude plugin validate` 報告錯誤](https://code.claude.com/docs/zh-TW/plugins/troubleshooting#claude-plugin-validate-reports-errors)列出這些訊息及其修正方式。

提及 Claude Desktop 旗標名稱的警告，這些名稱 Claude Desktop 拒絕。

下表將 marketplace 層級的訊息對應到各自相關的欄位。

| 訊息 | 層級 | 欄位 |
| :- | :- | :- |
| `Marketplace must have a name` | 錯誤 | `name` 為空 |
| `Marketplace name cannot contain spaces. Use kebab-case (e.g., "my-marketplace")` | 錯誤 | `name` |
| `Marketplace name cannot contain path separators (/ or \), ".." sequences, or be "."` | 錯誤 | `name` |
| `Marketplace name impersonates an official Anthropic/Claude marketplace` | 錯誤 | `name`。請參閱[保留名稱](#reserved-names) |
| `Marketplace name cannot contain control or bidirectional-formatting characters` | 錯誤 | `name` 包含控制字元（例如逸出或換行符）或 Unicode 雙向格式化字元 |
| `Marketplace name "inline" is reserved for --plugin-dir session plugins`, and the `builtin`, `skills-dir`, `synced`, `claude-plugin-test`, `npm`, `pip`, `uv`, `cargo`, `github`, and `gh` variants | 錯誤 | `name` |
| `Author name cannot be empty` | 錯誤 | `owner.name` |
| `Plugin name cannot contain spaces. Use kebab-case (e.g., "my-plugin")` | 錯誤 | `plugins[i].name` |
| `Plugin name cannot contain control or bidirectional-formatting characters` | 錯誤 | `plugins[i].name` |
| `Plugin name "x" is reserved: it passes as one of Anthropic's own` | 錯誤 | `plugins[i].name`。請參閱 manifest 的 [`name`](https://code.claude.com/docs/zh-TW/plugins/manifest-reference#name) 以了解保留名稱 |
| `Plugin name "x" reads as one of Anthropic's own` | 警告 | `plugins[i].name` |
| `Claude Code cannot install plugins from marketplace "x". Each part of a plugin id (plugin@marketplace) may use only the letters a-z and A-Z, digits, ".", "_" and "-", and must start with a letter or digit. Change the marketplace's "name".` | 錯誤 | `name` |
| `Claude Code cannot install plugin "x". Each part of a plugin id (plugin@marketplace) may use only the letters a-z and A-Z, digits, ".", "_" and "-", and must start with a letter or digit. Change this entry's "name".` | 錯誤 | `plugins[i].name` |
| `Duplicate plugin name "x" found in marketplace` | 錯誤 | 兩個項目共享一個 `name` |
| `plugins.i.source: Invalid input` | 錯誤 | 該項目的 `source` 不符合任何類型。請參閱[來源上的無效輸入](#invalid-input-on-a-source) |
| `plugins.i.source: Invalid string: must start with "./"` | 錯誤 | 缺少開頭 `./` 的相對路徑 `source`。在 v2.1.285 之前，此錯誤會改為列印 `Invalid input` |
| `plugins[i].source: Path contains "..": <path>` | 錯誤 | 逃逸 marketplace 根目錄的相對 `source` |
| `source.source: 'unsupported' is a parse-time placeholder and cannot be authored` | 錯誤 | `plugins[i].source` |
| `Plugin "x" sets headersHelper but is not "strict": false` | 錯誤 | `plugins[i].headersHelper`，在 `archive` 項目上 |
| `chain does not resolve (<reason>) — target must be a name in plugins[], a key in renames, or null` | 錯誤 | `renames.<old>` |
| `target "x" is not a valid plugin name (PluginIdSchema)` | 錯誤 | `renames.<old>` |
| `Unknown field 'x'. Claude Code ignores it at load time.` | 警告 | 頂層、`metadata` 下、項目中或項目 `relevance` 下的命名鍵 |
| `Marketplace has no plugins defined` | 警告 | `plugins` 為空 |
| `Plugin "x" sets headers/headersHelper, which only apply to "archive" sources; they have no effect on this entry.` | 警告 | `plugins[i].headers` 或 `plugins[i].headersHelper`，在 `source` 不是 `archive` 的項目上 |
| `Plugin "x" fetches its archive with a headersHelper but sets no sha256 pin` | 警告 | `plugins[i].source.sha256` |
| `Header "x" is a request-routing/identity header that catalog entries may not set; Claude Code drops it at download time.` | 警告 | `plugins[i].headers.<name>` |
| `Local source "x" is or traverses a symlink, so <path> was not read` | 警告 | `plugins[i].source` |
| `No marketplace description provided. Adding a description helps users understand what this marketplace offers` | 警告 | `description` |
| `Entry declares version "x" but <path>/plugin.json says "y". At install time, plugin.json wins` | 警告 | `plugins[i].version`，在相對路徑項目上 |
| `'relevance' must be an object containing topic and signals; got <type>. It will be ignored at load time.` | 警告 | `plugins[i].relevance` |
| `'metadata' must be a free-form object; got <type>. It will be ignored at load time.` | 警告 | `plugins[i].metadata` |
| `'experimental' must be an object containing component declarations; got <type>. It will be ignored at load time.` | 警告 | `plugins[i].experimental` |
| `Marketplace name "x" is reserved in Claude Desktop` | 警告 | `name` 是 `org`、`org-provisioned` 或 `unknown`。Claude Desktop 拒絕 marketplace |
| `Marketplace name "x" is not accepted by Claude Desktop (letters, digits, ".", "_", "-"; must start alphanumeric; max 128 chars)` | 警告 | `name`。Claude Desktop 拒絕 marketplace |
| `Plugin name "x" is not accepted by Claude Desktop (letters, digits, ".", "_", "-"; must start alphanumeric; max 128 chars)` | 警告 | `plugins[i].name`。Claude Desktop 捨棄該項目 |

### 來源上的無效輸入

`source` 上的 `Invalid input` 表示該物件不符合任何來源類型。檢查這些原因：

* 包含 `..` 的 `npm` `package`
* 不是[外掛程式來源](#plugin-sources)之一的 `source` 類型
* 已知類型但缺少必需欄位或類型錯誤，例如沒有 `repo` 的 `github`

不以 `./` 開頭的相對路徑（`"."` 或 [`metadata.pluginRoot` 下的 bare name](#relative-path-plugin-source) 除外）會以 `Invalid string: must start with "./"` 失敗。在 v2.1.285 之前，它會像上述原因一樣列印 `Invalid input`。

### 驗證未捕捉的失敗

`claude plugin validate` 不會報告每個失敗。寫成檔案路徑或陣列的項目 `hooks` 通過驗證，錯誤僅在外掛程式載入時出現，如[項目中的 Hooks](#hooks-in-an-entry) 所述。擷取 `source` 的錯誤也僅在安裝後出現，不在驗證中。

[`claude plugin list`](https://code.claude.com/docs/zh-TW/plugins/cli-reference) 顯示載入失敗的外掛程式及其錯誤，[疑難排解外掛程式](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md)涵蓋載入時間字串。

## 後續步驟

* [Create a marketplace](https://code.claude.com/docs/zh-TW/plugins/create-marketplace.md)：從這些欄位建立 marketplace 並在本地安裝
* [Host and maintain a marketplace](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md)：將檔案放在何處以及使用者如何接收更改
* [Plugin manifest reference](https://code.claude.com/docs/zh-TW/plugins/manifest-reference.md)：項目可以覆蓋的 `plugin.json` 欄位
* [Manage plugins for your organization](https://code.claude.com/docs/zh-TW/plugins/org.md)：使用這些來源值的允許清單和封鎖清單配方

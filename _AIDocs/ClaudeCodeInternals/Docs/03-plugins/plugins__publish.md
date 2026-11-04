<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/plugins/publish | lastmod: 2026-10-30 | section: Plugins / Create plugins -->
> 來源：https://code.claude.com/docs/zh-TW/plugins/publish（官方 zh-TW，lastmod 2026-10-30）｜分類：Plugins › Create plugins｜EN 摘要：Publish a Claude Code plugin through your own marketplace or Anthropic's directory, with a pre-release checklist and how users get updates.

# 發佈和分發外掛程式

> 透過您自己的市集或 Anthropic 的社群市集發佈 Claude Code 外掛程式，包括發行前檢查清單以及使用者如何取得更新。

發佈 Claude Code 外掛程式意味著在市集中列出它，市集是一個 JSON 目錄，列出外掛程式及其取得位置，以便其他人可以按名稱安裝它並接收您的更新。您可以執行自己的市集或將您的外掛程式提交到 Anthropic 的社群市集。若要在不發佈的情況下共享外掛程式，請將外掛程式的目錄或其 `.zip` 檔案發送給人們以供他們自行載入。

本頁面適用於已準備好共享工作外掛程式的作者。

> [!NOTE]
>
> 這些情況涵蓋在其他頁面上：
>
> * **您的外掛程式尚未完成**：從 [建立外掛程式](https://code.claude.com/docs/zh-TW/plugins/create.md) 開始
> * **您維護的 CLI 或 SDK 在官方市集中有外掛程式**：請參閱 [從您的 CLI 推薦您的外掛程式](https://code.claude.com/docs/zh-TW/plugins/cli-hints.md)

從 [選擇分發方式](#choose-how-to-distribute) 開始，比較分發選項。如果您已經知道您的路線，請前往 [準備您的外掛程式以供發行](#prepare-your-plugin-for-release)，然後按照您的路線部分，了解要告訴使用者什麼以及他們如何接收您的更新。

## 選擇分發方式

根據誰需要安裝外掛程式來選擇分發選項：

| 路線 | 誰可以安裝 | 您需要什麼 | 使用者是否自動取得您的更新？ |
| :- | :- | :- | :- |
| [無市集](#share-a-plugin-without-a-marketplace) | 您發送外掛程式資料夾或其 `.zip` 的人 | 外掛程式的資料夾 | 無。他們載入您發送的副本 |
| [您自己的市集](#publish-through-your-own-marketplace) | 任何可以存取存放庫的人，可以是您的團隊可以複製的私人存放庫 | 包含列出您的外掛程式的 `.claude-plugin/marketplace.json` 的 git 存放庫或其他主機 | 關閉 |
| [Anthropic 的目錄](#submit-to-anthropics-directory) | 在 claude.ai 或 Cowork 中新增的人。它也會透過[帳戶同步](https://code.claude.com/docs/zh-TW/plugins/loading.md#synced-plugins)在他們的 Claude Code 工作階段中載入 | 保存外掛程式的 GitHub 存放庫和付費 claude.ai 方案以供提交 | 是，在您推送的版本發佈後 |

自動更新是使用者端的每個市集設定，在背景中取得新版本。

## 準備您的外掛程式以供發行

名稱、版本、驗證和從市集安裝決定了發行是否對安裝它的人有效。在第一次發行前檢查它們，然後在之後的每次發行前再次檢查。

**1. 選擇永久名稱**

使用者透過 `name@marketplace` 安裝、啟用和設定您的外掛程式，因此重新命名的外掛程式對每個現有安裝都是不同的外掛程式。選擇 kebab-case 名稱，例如 `deploy-helper`，因為 `claude plugin validate` 會對其他形式發出警告，並將其視為永久名稱。在 `plugin.json` 中設定 `displayName` 以取得使用者看到的標籤。

**2. 決定您將如何版本化**

如果您在 `plugin.json` 中設定 `version` 並稍後推送提交而不更改它，`claude plugin update` 會列印 `<name> is already at the latest version (1.0.0).`，使用者會保留舊副本。要麼在每次發行時遞增 `version`，要麼在 git 託管的市集中省略它，以便 Claude Code 改用提交 SHA。請參閱 [版本和更新](https://code.claude.com/docs/zh-TW/plugins/loading.md#versions-and-updates)。

**3. 驗證**

在您的 shell 中，執行 `claude plugin validate --strict ./your-plugin`。乾淨的執行會列印 `✔ Validation passed`。

* **在 CI 中**：保留 `--strict`，它也會因為警告（例如未知的資訊清單欄位或缺少 `version`）而以結束代碼 1 失敗執行。如果您在上一步中選擇省略 `version`，請刪除 `--strict`。
* **路徑**：驗證報告不以 `./` 開頭的元件路徑。在 hook 命令和 MCP 伺服器設定中，將檔案稱為 `${CLAUDE_PLUGIN_ROOT}/...`。請參閱 [路徑規則](https://code.claude.com/docs/zh-TW/plugins/manifest-reference.md#path-rules)。

**4. 從本機市集安裝它**

在您的 shell 中，使用 `claude plugin marketplace add ./path-to-marketplace` 新增列出外掛程式的本機市集，從中安裝外掛程式，並啟動工作階段以確認它載入。

* 對於最小的有效市集，請參閱 [建立市集](https://code.claude.com/docs/zh-TW/plugins/create-marketplace.md)。
* 若要了解安裝是載入您的來源目錄還是快取副本，請參閱 [就地和複製的外掛程式](https://code.claude.com/docs/zh-TW/plugins/loading.md#in-place-and-copied-plugins)。

**5. 填入使用者看到的中繼資料**

在 `plugin.json` 中設定 `description`、`author`、`homepage` 和 `repository`，並在外掛程式根目錄新增 `README.md`。`homepage` 必須解析為 URL。[資訊清單參考](https://code.claude.com/docs/zh-TW/plugins/manifest-reference.md#fields) 列出每個欄位。

**6. 執行您的評估套件**

如果您有評估套件，請在 shell 中執行 `claude plugin eval`。它執行外掛程式的測試案例並評分結果，這在您變更外掛程式時會捕捉迴歸。請參閱 [使用評估測試外掛程式](https://code.claude.com/docs/zh-TW/plugin-evals.md)。

## 不使用市集共享外掛程式

如果外掛程式在 git 存放庫中，人們可以複製它並載入簽出，或從他們的 shell 使用指向您附加到發行的 `.zip` 的 `--plugin-url` 啟動 Claude Code。若要取得您的下一個版本，他們會拉取或再次下載。如果它不在存放庫中，請將目錄或其 `.zip` 發送給他們。他們可以透過以下兩種方式之一載入它：

* **對於一個工作階段**：他們從他們的 shell 使用 `claude --plugin-dir ./deploy-helper` 啟動 Claude Code，其中路徑是複製、解壓縮的資料夾或 `.zip` 本身。請參閱 [為一個工作階段載入外掛程式的旗標](https://code.claude.com/docs/zh-TW/plugins/cli-reference.md#flags-that-load-a-plugin-for-one-session)。
* **對於每個工作階段**：他們將外掛程式目錄（包含其 `.claude-plugin/plugin.json`）移到 `~/.claude/skills/` 下。從那時起，Claude Code 會在啟動時載入它，除非其管理員已[封鎖 skills 目錄外掛程式](https://code.claude.com/docs/zh-TW/plugins/loading.md#skills-directory-plugins-blocked-by-managed-settings)。

將 `.claude-plugin/marketplace.json` 新增到同一存放庫是讓人們按名稱安裝並使用命令更新的方式；請參閱 [透過您自己的市集發佈](#publish-through-your-own-marketplace)。

### 使用您自己的工具發送外掛程式

如果您維護 CLI 或 SDK，請在市集中發佈外掛程式，並讓您的安裝程式或安裝後訊息執行或列印使用者需要的兩個命令：`claude plugin marketplace add <source>`，然後 `claude plugin install <name>@<marketplace>`。對於當某人使用您的工具時的工作階段內發現，請參閱 [從您的 CLI 推薦您的外掛程式](https://code.claude.com/docs/zh-TW/plugins/cli-hints.md)。

## 透過您自己的市集發佈

您自己的市集是一個 `.claude-plugin/marketplace.json` 檔案，列出您的外掛程式，新增到 git 存放庫。一旦檔案在存放庫中，外掛程式就會發佈，沒有提交表單。您可以將檔案保留在外掛程式自己的存放庫中或在單獨的存放庫中。

### 將市集檔案新增到您的存放庫

若要從外掛程式自己的存放庫發佈，請在 `.claude-plugin/` 中的 `plugin.json` 旁邊儲存市集檔案，其中一個項目的 `source` 是 `"./"`，存放庫根目錄。給予項目與 `plugin.json` 相同的 `name`，根據 [保持項目名稱和資訊清單名稱相同](https://code.claude.com/docs/zh-TW/plugins/create-marketplace.md#keep-the-entry-name-and-the-manifest-name-the-same)：

```json .claude-plugin/marketplace.json theme={null}
{
  "name": "your-marketplace",
  "owner": { "name": "Your Name" },
  "plugins": [
    { "name": "deploy-helper", "source": "./" }
  ]
}
```

請將 `your-marketplace` 替換為其他作者不太可能選用的名稱，因為使用者[無法擁有兩個同名的市集](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#marketplace-file)。在推送之前，請在您的 shell 中於儲存庫內執行 `claude plugin validate .`。關於此執行會檢查的內容，請參閱 [驗證目錄](https://code.claude.com/docs/zh-TW/plugins/cli-reference.md#validate-a-directory)。

[建立市集](https://code.claude.com/docs/zh-TW/plugins/create-marketplace.md) 涵蓋一個存放庫中有多個外掛程式的佈局。

### 控制誰可以安裝

任何可以複製存放庫的人都可以從中安裝，因此如果存放庫是私人的，市集也是私人的。對於 git 存放庫以外的主機，請參閱 [託管市集](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md)。若要到達整個公司的每個人，包括不使用 git 的人，請參閱 [推出到整個公司](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md#roll-out-to-a-whole-company)。

### 告訴使用者如何安裝

告訴您的使用者新增市集，然後從他們的 shell 安裝外掛程式，用您的替換來源和名稱：

* 新增市集一次：`claude plugin marketplace add your-org/your-marketplace`，其中引數是 GitHub `owner/repo` 速記、URL 或路徑
* 安裝外掛程式：`claude plugin install deploy-helper@your-marketplace`
* 或從工作階段內執行兩者：`/plugin install deploy-helper --marketplace your-org/your-marketplace`。需要 Claude Code v2.1.275 或更新版本。請參閱 [在一個命令中新增市集和安裝](https://code.claude.com/docs/zh-TW/plugins/install.md#add-a-marketplace-and-install-in-one-command)
* 或從 shell 以一個命令執行兩者：`claude plugin install deploy-helper --marketplace your-org/your-marketplace`。需要 Claude Code v2.1.292 或更新版本

### 向使用者發送更新

使用者在要求時或為您的市集啟用自動更新時接收發行：

* **應要求**：使用者 shell 中的 `claude plugin update deploy-helper@your-marketplace` 會重新整理市集，並在您的外掛程式版本已變更時安裝新副本
* **自動更新**：預設為您的市集關閉。請參閱 [啟用自動更新](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md#turn-on-auto-update)。啟用後，它會在工作階段開始後延遲執行與 `claude plugin update` 相同的操作

[安裝外掛程式](https://code.claude.com/docs/zh-TW/plugins/install.md) 涵蓋使用者端命令，[自動更新何時執行](https://code.claude.com/docs/zh-TW/plugins/loading.md#when-auto-update-runs) 涵蓋時序。

## 提交到 Anthropic 的目錄

[Anthropic 的目錄](https://claude.ai/directory)是人們在 claude.ai 和 Cowork 中瀏覽以新增外掛程式和連接器的目錄。在那裡的一個列表可以觸及 claude.ai、Cowork 和 Claude Code 上的人。您可以從開發者入口網站 [claude.ai/directory/manage](https://claude.ai/directory/manage) 提交，claude.com 上的[提交外掛程式](https://claude.com/docs/plugins/submit#submit-a-plugin)會逐步說明入口網站的操作。

Anthropic 的官方市集 `claude-plugins-official` 不透過目錄入口網站接受提交。如果您與 Anthropic 合作夥伴聯絡合作，請詢問他們有關官方市集列表。

若要提交外掛程式：

**1. 確認您可以提交**

提交需要付費的 claude.ai 方案。在 Pro、Max 和 Ultra 上，您可以從自己的帳戶提交。在 Team 和 Enterprise 上，擁有者可以提交，在 Enterprise 上，擁有者也可以透過 **組織設定 > 角色** 下的自訂角色將 **目錄** 權限授予其他成員。請參閱 [確認您可以提交到目錄](https://claude.com/docs/directory/publish#confirm-you-can-submit-to-the-directory)。

**2. 在本機驗證外掛程式**

在您的 shell 中執行 `claude plugin validate ./your-plugin --strict`。用您的外掛程式目錄的路徑替換 `./your-plugin`。該命令在本機捕捉清單錯誤；[plugin validate](https://code.claude.com/docs/zh-TW/plugins/cli-reference.md#plugin-validate) 列出每次執行讀取的檔案。入口網站應用 CLI 不檢查的其他目錄規則，因此乾淨的本機執行不保證乾淨的入口網站驗證。

claude.com 上的[外掛程式提交前檢查清單](https://claude.com/docs/plugins/pre-submission-checklist#run-the-checks-before-you-submit)列出提交前要執行和修復的檢查。

**3. 檢查在哪裡載入**

某些外掛程式元件僅限 Claude Code，不在 claude.ai 或 Cowork 中載入。[元件支援表](https://claude.com/docs/plugins/platform-support#compare-component-support-by-app) 按應用程式列出每個元件，因此您知道 Claude Code 外的使用者會得到什麼。

**4. 在開發者入口網站中提交**

開啟開發者入口網站 [claude.ai/directory/manage](https://claude.ai/directory/manage)，並依照 claude.com 上的[提交外掛程式](https://claude.com/docs/plugins/submit#submit-a-plugin)操作。

流程的其餘部分記錄在 claude.com 上：

* [準備審查](https://claude.com/docs/directory/publish#prepare-for-review)：每個版本在發佈前會發生什麼
* [更新已發佈的外掛程式](https://claude.com/docs/plugins/submit#update-a-published-plugin)：新版本如何送達已安裝您外掛程式的人
* [提交您的外掛程式，以及將您的 MCP 伺服器作為連接器提交](https://claude.com/docs/directory/publish#submit-your-plugin-and-your-mcp-server-as-a-connector)：您可以提交什麼
* [將較早的提交移至開發者入口網站](https://claude.com/docs/directory/publish#move-an-earlier-submission-to-the-developer-portal)：如果您透過較早的提交表單之一提交了外掛程式（在入口網站存在之前），該怎麼辦

### 列出的外掛程式如何觸及 Claude Code 使用者

在 claude.ai 上從目錄安裝您的外掛程式的人在其帳戶上擁有它，Claude Code 將其載入為 `<name>@synced`。[從 claude.ai 同步的外掛程式](https://code.claude.com/docs/zh-TW/plugins/loading.md#synced-plugins) 涵蓋他們看到的內容以及他們如何關閉它。

## 發送更新、重新命名和移除

### 發行新版本

如果您透過您自己的市集發佈，並且您的 `plugin.json` 設定 `version`，請遞增它並推送。執行 `claude plugin update` 或啟用自動更新的使用者會接收新版本，如 [向使用者發送更新](#ship-updates-to-users) 下所述。如需目錄清單，請參閱 [更新已發佈的外掛程式](https://claude.com/docs/plugins/submit#update-a-published-plugin)。

### 標記發行

當其他外掛程式在您的上宣告版本範圍時，在 git 中標記發行，因為這些範圍針對標籤進行解析。否則您不需要標籤。

若要標記，請從外掛程式目錄在 shell 中執行 `claude plugin tag`。它建立一個 `{name}--v{version}` 標籤。新增 `--push` 以將標籤發送到 `origin`。[`plugin tag` 參考](https://code.claude.com/docs/zh-TW/plugins/cli-reference#plugin-tag) 列出其旗標。

### 重新命名或移除外掛程式

永遠不要變更已發佈外掛程式的 `name`。重新命名後，已安裝它的使用者會失去外掛程式，因為他們的安裝是在舊名稱下記錄的。您的市集檔案中的 `renames` 項目會改為遷移它們。當您想要不同的標籤時，變更 `displayName`。

如果重新命名是不可避免的，請使用市集檔案的 `renames` 對應，以便現有安裝遷移而不是因 [`Plugin "<name>" not found in marketplace`](https://code.claude.com/docs/zh-TW/plugins/troubleshooting#plugin-not-found-in-marketplace) 而失敗。若要從市集移除外掛程式，或取得完整的 `renames` 詳細資訊，請參閱託管頁面上的 [重新命名或移除外掛程式](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md#rename-or-remove-a-plugin)。[市集參考](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#top-level-fields) 有該欄位。

## 宣告依賴項

如果您的外掛程式需要來自同一市集的另一個外掛程式被啟用，請在 `plugin.json` 的 `dependencies` 陣列中列出它。每個項目是一個裸名稱或具有 semver `version` 範圍的物件。當使用者安裝您的外掛程式時，Claude Code 也會安裝並啟用依賴項。

[外掛程式依賴項](https://code.claude.com/docs/zh-TW/plugins/dependencies.md) 涵蓋範圍語法、跨市集依賴項以及使用者如何修剪他們不再需要的依賴項。

## 後續步驟

* [託管和維護市集](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md)：發行新版本並讓使用者保持最新狀態
* [外掛程式依賴項](https://code.claude.com/docs/zh-TW/plugins/dependencies.md)：宣告和版本化您的外掛程式所依賴的外掛程式
* [從您的 CLI 推薦您的外掛程式](https://code.claude.com/docs/zh-TW/plugins/cli-hints.md)：提示您的 CLI 的 Claude Code 使用者安裝外掛程式
* [測量外掛程式成本和使用情況](https://code.claude.com/docs/zh-TW/plugins/measure.md)：查看您的外掛程式在上下文中的成本以及人們是否使用它

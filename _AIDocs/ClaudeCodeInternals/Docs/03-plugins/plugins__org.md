<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/plugins/org | lastmod: 2026-11-02 | section: Plugins / Manage plugins for your organization -->
> 來源：https://code.claude.com/docs/zh-TW/plugins/org（官方 zh-TW，lastmod 2026-11-02）｜分類：Plugins › Manage plugins for your organization｜EN 摘要：Control which plugins Claude Code installs and allows across your organization through managed settings.

# 為您的組織管理 Claude Code 外掛程式

> 透過受管設定控制 Claude Code 在組織中每台機器上安裝和允許的外掛程式。

受管設定讓您決定 Claude Code 在組織中每台機器上安裝和允許的外掛程式。使用者無法覆蓋它們。您可以從 claude.ai 管理員主控台以[伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)的形式提供它們，或透過 MDM 或 `managed-settings.json` 檔案以端點受管設定的形式提供。此頁面上的大多數控制項僅在受管設定中生效。

此頁面適用於管理員，此處的設定管理 Claude Code。

> [!NOTE]
>
> 這些情況涵蓋在其他頁面上：
>
> * **為自己安裝外掛程式**：從[安裝外掛程式](https://code.claude.com/docs/zh-TW/plugins/install.md)開始
> * **控制成員在 claude.ai 和 Cowork 中可以使用哪些外掛程式**：請參閱[為您的組織管理外掛程式](https://claude.com/docs/plugins/admin)（位於 claude.com）
> * **同時將一個外掛程式推出到 claude.ai、Cowork 和 Claude Code**：請參閱[選擇推出路線](https://claude.com/docs/plugins/org-rollout#choose-a-rollout-route)（位於 claude.com）
> * **claude.ai 管理設定中的外掛程式頁面**：[**組織設定 > 外掛程式與技能**](https://claude.ai/admin-settings/skills?tab=inventory)為成員的 claude.ai 帳戶開啟外掛程式，這些外掛程式作為[同步外掛程式](https://code.claude.com/docs/zh-TW/plugins/loading.md#synced-plugins)到達 Claude Code。它不設定此頁面上的任何金鑰

這些部分遵循大多數推出所採取的順序：[為所有人或每個儲存庫要求外掛程式](#pre-install-and-require-plugins)、[為容器和 CI 設定種子](#seed-containers-and-ci)、[限制](#restrict-what-users-can-install)使用者可以自行新增的內容、[設定更新政策](#set-update-policy)，然後[稽核](#audit-and-review)已安裝的內容。若要在一個位置檢視每個政策金鑰，請參閱[控制矩陣](#control-matrix)。

## 預先安裝和要求外掛程式

市場是外掛程式的目錄，Claude Code 從 git 儲存庫、URL 或本機路徑中擷取。在機器上註冊市場後，Claude Code 可以從中安裝外掛程式。

若要為整個車隊安裝外掛程式，請在[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)、政策檔案或組織中每台機器讀取的伺服器提供的政策中同時設定兩個金鑰：`extraKnownMarketplaces` 在每台機器上註冊市場，`enabledPlugins` 命名要從中安裝和啟用的外掛程式。[選擇傳遞機制](#choose-a-delivery-mechanism)涵蓋受管設定如何到達每台機器。

### 選擇傳遞機制

受管設定透過以下三種傳遞機制之一到達機器：

* **伺服器受管設定**：在[**組織設定 > Claude Code > 受管設定**](https://claude.ai/admin-settings/claude-code)將外掛程式金鑰設定為 JSON。需要在您的 Claude 組織中具有[擁有者角色](https://code.claude.com/docs/zh-TW/server-managed-settings.md#access-control)。雲端工作階段在安裝外掛程式之前會擷取這些設定。
* **MDM 政策**：在 macOS 上，提供一個 plist，其頂級金鑰是設定金鑰。在 Windows 上，將整個 JSON 文件儲存為登錄值中的字串。plist 網域和登錄金鑰位於[每個機制儲存政策的位置](https://code.claude.com/docs/zh-TW/managed-settings.md#where-each-mechanism-stores-the-policy)。
* **受管設定檔案**：在平台的系統路徑放置 `managed-settings.json`。您也可以將檔案新增到其旁邊的 `managed-settings.d/` 放入目錄。每個平台的檔案路徑位於[每個機制儲存政策的位置](https://code.claude.com/docs/zh-TW/managed-settings.md#where-each-mechanism-stores-the-policy)，放入合併規則位於[將基於檔案的政策分割到各個團隊](https://code.claude.com/docs/zh-TW/managed-settings.md#split-a-file-based-policy-across-teams)。

如果您在 claude.ai 上有 Claude for Teams 或 Enterprise 組織，且您的裝置並非全部在 MDM 下，請使用伺服器受管設定。否則使用 MDM 政策或受管設定檔案。如需權衡，請參閱[在伺服器受管和端點受管設定之間選擇](https://code.claude.com/docs/zh-TW/server-managed-settings.md#choose-between-server-managed-and-endpoint-managed-settings)。

#### 哪個受管來源在機器上適用

預設情況下，這三個來源中只有一個在機器上適用。Claude Code 使用第一個提供政策金鑰的來源，首先檢查伺服器受管設定，然後檢查 MDM 政策，然後檢查受管設定檔案。如果伺服器受管設定提供甚至一個不相關的政策金鑰，Claude Code 會忽略該機器上 MDM 政策或受管設定檔案中的外掛程式金鑰，除了[它從每個來源讀取的金鑰](https://code.claude.com/docs/zh-TW/managed-settings.md#keys-read-from-every-admin-source)。

若要改為應用每個來源，請將[`managedSourcesBehavior`](https://code.claude.com/docs/zh-TW/managed-settings#compose-every-managed-source)設定為 `"merge"`。

[Claude Code 如何組合受管來源](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)也在兩種模式中列出 Claude Code 從每個來源讀取的金鑰。

### 要求市場及其外掛程式

在 `extraKnownMarketplaces` 下新增市場，使用市場自己的 `marketplace.json` 中的 `name` 作為金鑰。然後在 `enabledPlugins` 下將每個外掛程式新增為 `plugin-name@marketplace-name`。每個市場項目都帶有一個 `source` 物件，其中 `source` 欄位命名類型，例如 `github`。此受管設定範例註冊一個組織市場並強制啟用其中的兩個外掛程式：

```json theme={null}
{
  "extraKnownMarketplaces": {
    "your-marketplace": {
      "source": { "source": "github", "repo": "your-org/your-marketplace" },
      "autoUpdate": true
    }
  },
  "enabledPlugins": {
    "code-formatter@your-marketplace": true,
    "deploy-helper@your-marketplace": true
  }
}
```

設定到達機器後，Claude Code 註冊市場並在使用者下一個工作階段開始時安裝兩個外掛程式。使用者在 `/plugin` 中看到它們，在自己的範圍禁用其中一個不會阻止它載入，因為受管設定優先於每個其他範圍。

若要在每個範圍阻止外掛程式並將其從市場清單中隱藏，請改為在受管 `enabledPlugins` 中將其設定為 `false`。

調整市場的 `autoUpdate` 和 `source` 欄位：

* **`autoUpdate`**：`true` 保持市場及其外掛程式在背景中重新整理，`false` 關閉它。請參閱[設定更新政策](#set-update-policy)。
* **`source`**：`github` 是幾種來源類型之一。`git` 來源採用 GitLab 或內部主機的 `url`，`url` 來源採用託管 `marketplace.json` 的位址。每個來源形狀都在[市場參考](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md)中。

如果市場是私人 git 儲存庫，每個使用者都需要對其具有讀取存取權限。git 型市場的複製在使用者的機器上使用 git 執行，使用儲存的認證且無提示。對於沒有 git 主機帳戶的使用者，請改用[種子](#seed-containers-and-ci)。

受管項目也會覆蓋來自另一個來源的同名市場項目或 `--plugin-dir` 複本：

* **市場**：受管市場項目替換具有相同名稱的較低優先順序項目，兩個項目的欄位不合併。
* **`--plugin-dir` 複本**：`--plugin-dir` 為一個工作階段從本機目錄載入外掛程式。如果該複本的名稱與您的受管 `enabledPlugins` 命名的外掛程式相符，請參閱[名稱衝突](https://code.claude.com/docs/zh-TW/plugins/loading.md#name-conflicts)。

Anthropic 的官方市場 `claude-plugins-official` 當 `enabledPlugins` 將其中一個外掛程式設定為 `true` 時不需要 `extraKnownMarketplaces` 項目。該 `name@claude-plugins-official` 項目在這些金鑰適用的任何地方自行聲明市場。如果您未啟用其任何外掛程式但仍想在每台機器上註冊它，請給它一個明確項目，如[允許官方市場和您自己的](#allow-the-official-marketplace-and-your-own)所做的。

### 按儲存庫要求外掛程式

若要涵蓋一個儲存庫的貢獻者而不是整個車隊，請在該儲存庫的 `.claude/settings.json` 中設定 `extraKnownMarketplaces` 和 `enabledPlugins`。`extraKnownMarketplaces` 項目僅適用於貢獻者已信任的資料夾，在不受信任的資料夾中 Claude Code 會無訊息地忽略它們：

* **互動式工作階段**：Claude Code 僅在貢獻者接受該資料夾的[工作區信任對話](https://code.claude.com/docs/zh-TW/permissions.md#what-runs-before-you-trust-a-folder)後才註冊市場。
* **[非互動式 `-p` 執行](https://code.claude.com/docs/zh-TW/headless)**：項目僅適用於使用者已互動式接受信任的資料夾，或您在 `~/.claude.json` 中設定 `hasTrustDialogAccepted` 旗標的資料夾。

市場按相對路徑列出的外掛程式在儲存庫的 `extraKnownMarketplaces` 項目適用後從市場複本載入。市場項目指向外部來源（例如外掛程式自己的 GitHub 儲存庫）的外掛程式不會單獨從儲存庫的設定安裝。每個貢獻者看到 `Plugin "<name>" is enabled in project settings but isn't installed`，直到他們執行 `claude plugin install <name>@<marketplace> --scope project`，如[安裝外掛程式](https://code.claude.com/docs/zh-TW/plugins/install.md)所述。

如果您使用具有相對路徑的本機 `directory` 或 `file` 來源，路徑會針對您的儲存庫的主要簽出進行解析。當您從 git worktree 執行 Claude Code 時，路徑仍指向主要簽出，因此所有 worktree 共享相同的市場位置。

若要推出具有依賴項的外掛程式組合，請將組合外掛程式放在 `enabledPlugins` 中，如[外掛程式依賴項](https://code.claude.com/docs/zh-TW/plugins/dependencies.md)所述。

### 每個表面何時應用外掛程式金鑰

該表顯示每種 Claude Code 工作階段何時應用 `extraKnownMarketplaces` 和 `enabledPlugins`，來自受管設定和來自儲存庫的 `.claude/settings.json`。對於 Desktop 應用程式和 IDE 擴充功能，請參閱[安裝外掛程式](https://code.claude.com/docs/zh-TW/plugins/install.md#install-a-plugin)。

| 表面 | 受管 `extraKnownMarketplaces` 和 `enabledPlugins` | 儲存庫 `.claude/settings.json` |
| :- | :- | :- |
| 終端機、互動式 | 在接收設定的每台機器上的工作階段開始時應用 | `extraKnownMarketplaces` 在信任後應用；`enabledPlugins` 在工作階段開始時應用 |
| `-p` 和 CI | 在工作階段開始時應用，安裝在背景中執行 | 僅在受信任的資料夾中的 `extraKnownMarketplaces`；`enabledPlugins` 已應用 |
| 雲端工作階段 | 在 Anthropic 託管的環境中，僅伺服器受管設定到達工作階段，它在安裝外掛程式之前等待它們。MDM 政策和受管設定檔案保留在使用者的機器上。對於自託管環境，請參閱[政策適用的位置和時間](https://code.claude.com/docs/zh-TW/managed-settings.md#where-and-when-a-policy-applies) | 請參閱[安裝外掛程式](https://code.claude.com/docs/zh-TW/plugins/install.md#install-a-plugin)下的**雲端工作階段**標籤 |

在 `-p` 或 CI 執行中，市場和外掛程式在背景中安裝，因此外掛程式可能在第一個轉向中遺失。設定 `CLAUDE_CODE_SYNC_PLUGIN_INSTALL=1` 使執行在其第一個查詢之前等待安裝。

### 確認推出

檢查市場和外掛程式是否到達機器或 CI 執行：

* **在一台機器上**：啟動 Claude Code 並執行 `/plugin`。市場和外掛程式已列出。
* **在 CI 中**：使用 `--output-format stream-json --verbose` 執行 `claude -p`。`init` 事件在 `plugins` 下列出已載入的外掛程式。

## 為容器和 CI 設定種子

對於無法在執行時複製的容器映像和 CI 執行器，在建置時預先填充外掛程式目錄並將 `CLAUDE_CODE_PLUGIN_SEED_DIR` 指向它。Claude Code 在啟動時註冊種子的市場並從種子就地載入外掛程式快取，無需複製。

種子也為沒有 git 主機帳戶的使用者提供服務。

> [!NOTE]
>
> 在 CI/CD 環境中，在從私人儲存庫安裝外掛程式之前配置 git 認證幫助程式。在 GitHub Actions 上，匯出具有市場儲存庫讀取存取權限的令牌作為 `GH_TOKEN`，然後執行 `gh auth setup-git`。預設工作流程令牌只能存取工作流程自己的儲存庫，因此另一個儲存庫中的私人市場需要個人存取令牌或應用程式令牌。

**1. 在建置時安裝到種子中**

將 `CLAUDE_CODE_PLUGIN_CACHE_DIR` 設定為種子路徑，以便市場和外掛程式安裝在那裡而不是 `~/.claude/plugins`：

```bash theme={null}
CLAUDE_CODE_PLUGIN_CACHE_DIR=/opt/claude-seed claude plugin marketplace add your-org/your-marketplace
CLAUDE_CODE_PLUGIN_CACHE_DIR=/opt/claude-seed claude plugin install code-formatter@your-marketplace
```

種子的佈局與 `~/.claude/plugins` 相同：`known_marketplaces.json`、`marketplaces/<name>/` 和 `cache/<marketplace>/<plugin>/<version>/`。您可以在與建置位置不同的路徑掛載種子。

**2. 將執行時指向種子**

在容器的環境中設定 `CLAUDE_CODE_PLUGIN_SEED_DIR=/opt/claude-seed`。若要使用多個種子，請在 Unix 上用 `:` 或在 Windows 上用 `;` 分隔它們的路徑。Claude Code 使用包含給定市場或外掛程式快取的第一個種子。

**3. 啟用外掛程式**

種子中的外掛程式預設不啟用。在受管設定或儲存庫的 `.claude/settings.json` 中為每個要載入的種子外掛程式設定 `enabledPlugins`。

若要驗證種子，請在映像中使用 `--output-format stream-json --verbose` 執行 `claude -p`。在 `init` 事件的 `plugins` 清單中，每個已載入外掛程式的 `path` 位於種子下，例如 `/opt/claude-seed/cache/your-marketplace/code-formatter/1.0.0`。

種子市場遵循這些規則：

* **唯讀**：Claude Code 永遠不會寫入種子，並強制為種子市場關閉 `autoUpdate`。
* **種子項目優先**：在每次啟動時，種子中聲明的市場會覆蓋使用者的同名項目。使用者使用 `claude plugin disable` 而不是移除市場來選擇退出種子外掛程式。
* **更新和移除失敗**：`claude plugin marketplace update <name>` 和在種子市場上不帶 `--scope` 的 `remove` 失敗，並顯示命名種子目錄的訊息。
* **政策仍適用**：[允許清單和封鎖清單](#restrict-what-users-can-install)也檢查種子市場的記錄來源。允許您建置種子的來源。

對於沒有出站 git 存取的車隊，將種子與共享掛載上的 `directory` 或 `file` 市場來源結合。同時設定 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`，這也會關閉[外掛程式自動更新](https://code.claude.com/docs/zh-TW/plugins/loading.md#when-auto-update-runs)。如果有代理可用，請參閱[代理配置](https://code.claude.com/docs/zh-TW/network-config.md#proxy-configuration)以了解要設定的變數。

## 限制使用者可以安裝的內容

受管 `strictKnownMarketplaces` 允許清單和 `blockedMarketplaces` 封鎖清單決定外掛程式可能來自哪些市場來源。市場的來源是 Claude Code 從中擷取的 git 儲存庫、URL 或本機路徑。兩個清單都匹配外掛程式來自的市場的來源，而不是該市場內的外掛程式自己的項目。

如需常見的鎖定，允許官方市場和您自己的，請參閱[允許官方市場和您自己的](#allow-the-official-marketplace-and-your-own)。將其與[`disableSideloadFlags`](#control-matrix)配對，以便使用者無法從本機目錄或 URL 載入外掛程式。

兩個清單在任何東西下載之前和在工作階段開始時應用：

* **下載前**：當使用者新增市場以及在每次安裝、更新、重新整理和自動更新時應用清單。
* **在工作階段開始時**：清單再次應用於已安裝的外掛程式，因此已安裝的外掛程式其市場來源不再符合不會載入。`/plugin` 使用 `Marketplace "<name>" is not in the allowed marketplace list` 或 `Marketplace "<name>" is blocked by enterprise policy` 列出它。

兩個清單的執行位置取決於您在何處設定它們：

* **claude.ai 管理員主控台**：Claude Code 在[讀取伺服器受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md#where-and-when-a-policy-applies)的工作階段中執行兩個清單。claude.ai 也在您組織中的任何人從 git 儲存庫在 claude.ai 上新增新市場，或從 Claude Desktop 應用程式中 Code 標籤之外的**自訂**新增時檢查它們。這涵蓋成員為自己的帳戶新增的市場和在[**組織設定 > 外掛程式**](https://claude.ai/admin-settings/plugins)下為整個組織新增的市場。claude.ai 拒絕允許清單不允許或封鎖清單命名的儲存庫。它不重新檢查在您設定清單之前在任一位置新增的市場，也不檢查上傳的外掛程式。
* **受管設定檔案、OS 級政策或其他受管來源**：Claude Code 在讀取該來源的位置執行兩個清單。claude.ai 不讀取它。

當設定任何允許清單時，或封鎖清單命名除[`skills-dir`](#blocklist-with-blockedmarketplaces)之外的任何來源時，Claude Code 找不到其市場的外掛程式不會載入。`/plugin` 為其顯示政策錯誤而不是找不到錯誤。常見情況是市場沒有人註冊的過時 `enabledPlugins` 項目。

### 控制矩陣

該表列出每個外掛程式政策金鑰、它執行的內容以及它無法執行的內容。

| 金鑰 | 它執行的內容 | 它無法執行的內容 |
| :- | :- | :- |
| `strictKnownMarketplaces` | 市場來源的允許清單。`[]` 阻止每個來源，包括官方市場。別名：`allowedMarketplaces` | 不註冊市場、限制允許市場內的項目或阻止 `--plugin-dir` |
| `blockedMarketplaces` | 市場來源的封鎖清單，在允許清單之前檢查 | 不阻止已從不符合的來源註冊的市場 |
| `syncClaudeAiPlugins` | 設定 `false` 以停止 Claude Code 下載和載入為每個使用者帳戶[從 claude.ai 同步](https://code.claude.com/docs/zh-TW/plugins/loading.md#synced-plugins)的外掛程式。需要 Claude Code v2.1.273 或更新版本 | 不關閉一個同步外掛程式。為此，在[`enabledPlugins`](https://code.claude.com/docs/zh-TW/settings-reference#enabledplugins)中設定 `"<name>@synced": false` |
| `enabledPlugins` | `true` 強制啟用，`false` 在每個範圍阻止並隱藏外掛程式 | 不安裝其市場未註冊或不允許的外掛程式 |
| `disableSideloadFlags` | 在啟動時拒絕 `--plugin-dir`、`--plugin-url`、`--agents`、Agent SDK `plugins` 選項以及[`CLAUDE_CODE_PLUGIN_DIRS`](https://code.claude.com/docs/zh-TW/env-vars#variables)變數中命名的資料夾，也會拒絕 `--mcp-config`，除非其中的每個伺服器都是處理程序內的 `type: "sdk"` 項目。拒絕 Agent SDK 應用程式在工作階段中途透過[`addPlugins`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#load-more-plugin-folders-with-addplugins)新增的外掛程式資料夾 | 不限制 `.mcp.json`、`claude mcp add` 或 SDK 提供的伺服器。將其與[`allowedMcpServers`](https://code.claude.com/docs/zh-TW/managed-mcp)配對 |
| `disableCommandPluginSources` | 阻止具有 `command` 來源的外掛程式安裝、更新或載入。`command` 來源是其外掛程式目錄由在機器上執行命令產生的來源。未設定時，它採用 `allowManagedHooksOnly` 的值 | 不影響其他來源類型 |
| `allowManagedHooksOnly` | 限制哪些 hooks 執行。請參閱[`allowManagedHooksOnly`](https://code.claude.com/docs/zh-TW/settings-reference#allowmanagedhooksonly) | 不信任使用者自己啟用的外掛程式中的 hooks |
| `strictPluginOnlyCustomization` | 封鎖不來自外掛程式、受管設定或 Claude Code 內建功能的 skill、agent、hook 和 MCP 伺服器。它也會阻止[skill 目錄外掛程式](#keep-skills-directory-plugins-loading)載入。設定 `true` 以涵蓋全部四種類型，或設定由 `skills`、`agents`、`hooks` 和 `mcp` 值組成的陣列（例如 `["skills", "hooks"]`）以涵蓋其中部分類型 | 不會限制使用者安裝哪些外掛程式。將其與 `strictKnownMarketplaces` 搭配使用 |
| `pluginSuggestionMarketplaces` | 其外掛程式可能作為安裝建議出現在終端機中的市集。請參閱[推薦外掛程式](#recommend-plugins) | 不影響內建提示 |
| `pluginTrustMessage` | 將您的文字附加到 `/plugin` 在外掛程式安裝前顯示的信任警告 | 不改變警告自己的文字 |
| `allowedChannelPlugins` | 替換允許推送頻道訊息的預設外掛程式清單。需要 `channelsEnabled: true` | 請參閱[限制哪些頻道外掛程式可以執行](https://code.claude.com/docs/zh-TW/channels.md#restrict-which-channel-plugins-can-run) |
| [`CLAUDE_CODE_DISABLE_OFFICIAL_MARKETPLACE_AUTOINSTALL=1`](https://code.claude.com/docs/zh-TW/env-vars) | 停止互動式終端機工作階段自動註冊官方市場 | 不移除已註冊的市場。允許清單和封鎖清單在沒有它的情況下控制相同的自動註冊。在設定它的情況下啟動一次的機器在您取消設定後不會恢復自動註冊 |
| [`allowManagedModsOnly`](https://code.claude.com/docs/zh-TW/plugins/mods/admin#stop-user-installed-mods-from-loading) | 阻止每個不[屬於您組織](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md#install-your-organizations-mods)的已安裝 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md) 執行其 hook | 不會阻止包含 mod 的外掛安裝。若要這麼做，請使用此表中的市集鍵 |

表中的每個金鑰都是受管設定，除了 `enabledPlugins`、`syncClaudeAiPlugins`、`CLAUDE_CODE_DISABLE_OFFICIAL_MARKETPLACE_AUTOINSTALL` 和 `allowManagedModsOnly`：

* **`enabledPlugins`**：您可以在任何範圍設定它，受管設定會鎖定它。
* **`syncClaudeAiPlugins`**：每個使用者也可以在自己的使用者或本機設定中設定它。請參閱其[設定參考中的範圍](https://code.claude.com/docs/zh-TW/settings-reference.md#syncclaudeaiplugins)。
* **`CLAUDE_CODE_DISABLE_OFFICIAL_MARKETPLACE_AUTOINSTALL`**：這是一個環境變數，您透過[關閉整個車隊的更新](#turn-updates-off-for-the-whole-fleet)下顯示的受管 `env` 區塊提供。
* **`allowManagedModsOnly`**：這是內建外掛程式上的選項，您在受管設定中的 `pluginConfigs` 下設定。請參閱[停止使用者安裝的 mod 載入](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md#stop-user-installed-mods-from-loading)。

此處的每個設定金鑰在[設定參考](https://code.claude.com/docs/zh-TW/settings-reference.md)中都有一個項目。

#### 市場金鑰的別名

`strictKnownMarketplaces` 也可以拼寫為 `allowedMarketplaces`，`extraKnownMarketplaces` 也可以拼寫為 `additionalMarketplaces`。

* **版本**：別名需要 Claude Code v2.1.232 或更新版本，較舊的用戶端會忽略它們。在混合車隊讀取的檔案中，保持規範名稱。
* **兩個拼寫都設定**：當檔案設定兩個拼寫時，規範金鑰的值適用。

### 使用 `strictKnownMarketplaces` 的允許清單

將允許清單設定為這些來源物件的清單。大多數項目完全匹配，`hostPattern` 和 `pathPattern` 項目作為正規表達式匹配，`github` 擁有者萬用字元按擁有者匹配：

* **`github`**：`{ "source": "github", "repo": "your-org/approved-plugins" }`，帶有可選的 `ref` 和 `path`。
* **`github` 擁有者萬用字元**：`{ "source": "github", "repo": "your-org/*" }` 匹配該擁有者下的每個儲存庫。`*` 必須代表整個儲存庫名稱。Claude Code 忽略 `*/plugins` 和 `your-org/tools-*` 等項目作為無效，因此它們不匹配任何內容。需要 Claude Code v2.1.223 或更新版本。
* **`git`**：`{ "source": "git", "url": "https://gitlab.example.com/tools/plugins.git" }`，帶有可選的 `ref` 和 `path`。
* **`url`**：`{ "source": "url", "url": "https://plugins.example.com/marketplace.json" }`，帶有可選的 `headers`。
* **`file` 和 `directory`**：`{ "source": "file", "path": "/opt/marketplace/marketplace.json" }` 或 `{ "source": "directory", "path": "/opt/marketplace/plugins" }`，帶有絕對路徑。
* **`hostPattern`**：`{ "source": "hostPattern", "hostPattern": "^github\\.example\\.com$" }`，針對 `github`、`git` 和 `url` 來源的主機進行匹配。該模式在主機名中的任何地方匹配，因此使用 `^` 和 `$` 進行錨定如所示以匹配整個主機。`github` 來源始終計為 `github.com`。對於開發人員建立自己的市場的 GitHub Enterprise Server 或 GitLab 主機，使用 `hostPattern` 項目。[GHES 頁面](https://code.claude.com/docs/zh-TW/github-enterprise-server.md#allowlist-ghes-marketplaces-in-managed-settings)有工作範例。
* **`pathPattern`**：`{ "source": "pathPattern", "pathPattern": "^/opt/approved/" }`，針對 `file` 和 `directory` 來源的 `path` 進行匹配。該模式在路徑中的任何地方匹配，因此以 `^` 開頭以固定目錄前綴。`".*"` 允許每個本機路徑。
* **`skills-dir`**：`{ "source": "skills-dir" }` 不比對任何市集。關於其作用，請參閱[保持 skill 目錄外掛程式載入](#keep-skills-directory-plugins-loading)。

#### 項目如何匹配

`url` 項目在其 `url` 值上匹配；`headers` 不進行比較。對於 `github` 和 `git` 項目，`repo` 或 `url`、`ref` 和 `path` 必須全部匹配，或在兩側都不存在：

* 沒有 `ref` 的項目不涵蓋具有 `ref: "main"` 的來源。
* `your-org/your-marketplace` 的項目不涵蓋複製相同儲存庫的 `git` URL。
* 尾部斜線、`.git` 後綴或 `ssh://` 代替 `https://` 是不同的值。當市場可以由多個 URL 複製時，更喜歡 `hostPattern` 項目。

擁有者萬用字元項目遵循 `ref` 的確切規則，並匹配儲存庫內的任何 `path`，除非項目固定一個。萬用字元匹配在允許清單上區分大小寫。

#### 保持技能目錄外掛程式載入

skill 目錄外掛程式是使用者放在 `~/.claude/skills/` 或專案的 `.claude/skills/` 下、位於含有 `.claude-plugin/plugin.json` 之資料夾中的外掛程式。如果您設定了任何不含 `{ "source": "skills-dir" }` 項目的允許清單，它們會停止載入。如果您使用 [`strictPluginOnlyCustomization`](https://code.claude.com/docs/zh-TW/settings-reference#strictpluginonlycustomization) 鎖定任何自訂類型，無論該項目是否存在，它們都會停止載入。允許清單不適用於一般的 [skill](https://code.claude.com/docs/zh-TW/skills.md)，也就是沒有該資訊清單的 `SKILL.md`。

#### 託管在 claude.ai 上的市場

允許清單和封鎖清單按其主機匹配[託管在 claude.ai 上的市場](https://code.claude.com/docs/zh-TW/plugins/install.md#add-from-claude-ai)。若要允許或阻止一個，請新增與 `claude.ai` 匹配的 `hostPattern` 項目到 `strictKnownMarketplaces` 或 `blockedMarketplaces`。在允許清單上，此類項目允許您組織的 claude.ai 市場和 claude.ai 預設市場，但不允許由成員自己的 claude.ai 上傳組成的市場或其範圍 claude.ai 未聲明的市場。需要 Claude Code v2.1.273 或更新版本。

#### 鎖定每個來源

空允許清單 `[]` 鎖定每個市場來源，包括官方市場。

此鎖定不涵蓋[從 claude.ai 同步](https://code.claude.com/docs/zh-TW/plugins/loading.md#synced-plugins)的外掛程式，Claude Code 從每個使用者的帳戶而不是市場下載。若要同時停止這些，請在受管設定中將[`syncClaudeAiPlugins`](https://code.claude.com/docs/zh-TW/settings-reference#syncclaudeaiplugins)設定為 `false`，或在 claude.ai 上為您的組織關閉技能。

### 使用 `blockedMarketplaces` 的封鎖清單

`blockedMarketplaces` 採用與[`strictKnownMarketplaces`](#allowlist-with-strictknownmarketplaces)相同的來源物件，並首先檢查，因此兩個清單上的來源被阻止。封鎖清單匹配比允許清單匹配更寬：

* Git URL 被規範化，因此一個 `github.com` 儲存庫的 `git@` 和 `https://` 形式、`.git` 後綴和尾部斜線都匹配相同的項目。
* `github` 項目也阻止等效的 `git` URL，反之亦然。
* 對於 `owner/*` 項目，擁有者比較不區分大小寫。
* 沒有 `ref` 或 `path` 的項目阻止它匹配的儲存庫的每個 ref 和 path。

此項目阻止一個 GitHub 擁有者下的每個儲存庫：

```json theme={null}
{
  "blockedMarketplaces": [
    { "source": "github", "repo": "untrusted-org/*" }
  ]
}
```

`blockedMarketplaces` 中的 `url` 項目也在使用者新增 Claude Code [複製而不是擷取](https://code.claude.com/docs/zh-TW/plugins/cli-reference.md#plugin-marketplace-add)的 `https://` 儲存庫 URL 時應用，例如裸 `github.com` 或 `gitlab.com` 儲存庫 URL。如果項目命名該 URL，使用者無法新增它。匹配忽略 `.git` 後綴和使用者在 `#` 後附加的任何 ref。需要 Claude Code v2.1.232 或更新版本。

此處的 `{ "source": "skills-dir" }` 項目停止[技能目錄外掛程式](#keep-skills-directory-plugins-loading)從 `~/.claude/skills/` 和專案的 `.claude/skills/` 載入。

僅命名該項目的封鎖清單不計為活躍限制，因此它不[停止 Claude Code 找不到其市場的外掛程式](#restrict-what-users-can-install)載入。

### 允許官方市場和您自己的

大多數組織允許官方市場和他們自己的，並註冊兩者以便每台機器都有它們。此受管設定政策允許兩個市場，註冊兩者，強制啟用兩個外掛程式，並拒絕 `--plugin-dir`：

```json theme={null}
{
  "strictKnownMarketplaces": [
    { "source": "github", "repo": "anthropics/claude-plugins-official" },
    { "source": "github", "repo": "your-org/*" },
    { "source": "skills-dir" }
  ],
  "extraKnownMarketplaces": {
    "claude-plugins-official": {
      "source": { "source": "github", "repo": "anthropics/claude-plugins-official" }
    },
    "your-marketplace": {
      "source": { "source": "github", "repo": "your-org/your-marketplace" }
    }
  },
  "enabledPlugins": {
    "code-formatter@your-marketplace": true,
    "deploy-helper@your-marketplace": true
  },
  "disableSideloadFlags": true
}
```

在具有此政策的機器上，新增清單外的任何來源，例如 `/plugin marketplace add https://example.com/other-marketplace.git`，失敗並顯示包含 `is blocked by enterprise policy` 的訊息，後跟允許的來源。`claude --plugin-dir ./x` 退出並顯示命名 `disableSideloadFlags` 的訊息。

如果您從此允許清單中移除 `{ "source": "skills-dir" }` 項目，[skill 目錄外掛程式](#keep-skills-directory-plugins-loading)會停止載入。

使用明確的 `extraKnownMarketplaces` 項目註冊兩個市場，如此政策所做的，而不是依賴允許清單或官方市場自行註冊：

* **允許清單不註冊任何內容**：`extraKnownMarketplaces` 項目執行，它本身必須通過允許清單。Claude Code 拒絕註冊受管市場，其來源允許清單不匹配。
* **官方市場僅在互動式終端機工作階段中自行註冊**：即使在那裡，它也僅在允許清單允許時註冊。`-p` 執行或附加到雲端工作階段的終端機永遠不會註冊它。
* **被阻止的嘗試被記住**：如果機器曾在阻止官方市場的政策下執行，Claude Code 會記錄被阻止的嘗試，並在政策更改後不重試。`[]` 鎖定是一個此類政策。該機器僅透過此政策中的 `extraKnownMarketplaces` 項目、其中一個外掛程式的 `enabledPlugins` 項目或手動 `/plugin marketplace add` 再次註冊它。

## 設定更新政策

您可以按市場、整個車隊或透過發佈頻道按使用者群組設定更新政策。

### 按市場開啟或關閉自動更新

外掛程式自動更新在啟動後在背景中為開啟它的市場執行。如需預設開啟它的市場，請參閱[自動更新何時執行](https://code.claude.com/docs/zh-TW/plugins/loading.md#when-auto-update-runs)。若要為車隊決定，請在受管 `extraKnownMarketplaces` 項目上設定 `"autoUpdate": true` 或 `false`：

* 如果受管項目設定欄位，Claude Code 拒絕使用者的 `/plugin` 切換並顯示以 `Auto-update for '<name>' is set by` 開頭的錯誤。
* 如果受管項目保留欄位未設定，使用者的切換保持。

### 關閉整個車隊的更新

若要為每個市場關閉外掛程式自動更新，請在受管 `env` 區塊中設定 `DISABLE_AUTOUPDATER`，如此範例所做的。相同變數也停止 Claude Code 自己的更新：

```json theme={null}
{
  "env": {
    "DISABLE_AUTOUPDATER": "1"
  }
}
```

若要停止 Claude Code 自己的更新但保持外掛程式自動更新，請將 `"FORCE_AUTOUPDATE_PLUGINS": "1"` 新增到相同區塊。其他[停止外掛程式自動更新的環境變數](https://code.claude.com/docs/zh-TW/plugins/loading.md#when-auto-update-runs)以相同方式工作。

`DISABLE_AUTOUPDATER` 不涵蓋具有[`command` 來源](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference#command-plugin-source)的外掛程式。Claude Code 每個工作階段重新執行每個啟用的命令，並在其更改時安裝輸出。如需停止這些執行的內容，請參閱[命令來源何時重新執行](https://code.claude.com/docs/zh-TW/plugins/loading.md#when-a-command-source-re-runs)。

### 將發佈頻道指派給使用者群組

若要執行穩定和早期存取頻道，請託管兩個指向相同外掛程式的不同 ref 的市場。然後透過單獨的端點受管設定或閘道政策為每個使用者群組提供自己的市場。來自管理員主控台的伺服器受管設定[適用於組織中的每個使用者](https://code.claude.com/docs/zh-TW/server-managed-settings.md#current-limitations)，因此它們無法為不同的群組指派不同的設定。

* 將單獨的[端點受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)（例如受管設定檔案或 MDM 設定檔）部署到每個群組的裝置。若要檢查每個群組檔案或設定檔是否適用於也有組織範圍來源的裝置，請參閱[Claude Code 如何組合受管來源](https://code.claude.com/docs/zh-TW/managed-settings.md#precedence-within-the-managed-tier)。
* 為每個群組定義一個 [Claude 應用程式閘道政策](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#managed)。預設情況下，閘道會套用第一個其匹配規則符合使用者的政策，因此請排序政策，讓每個使用者都能到達其群組的政策。該政策的 `extraKnownMarketplaces` 對應不會與任何其他政策的對應合併，因此請在其中列出群組需要的每個市集，而不僅僅是其通道市集。

使用任一機制，穩定群組接收此配置：

```json theme={null}
{
  "extraKnownMarketplaces": {
    "stable-tools": {
      "source": { "source": "github", "repo": "your-org/stable-tools" }
    }
  }
}
```

早期存取群組改為接收 `latest-tools`。若要設定兩個市場，請參閱[執行發佈頻道](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md#run-release-channels)。

## 推薦外掛程式

市場擁有者可以將 `relevance` 訊號附加到項目，以便 Claude Code 在專案符合時建議外掛程式。

來自市場的建議僅在其在使用者的機器上註冊、您在受管設定中的 `pluginSuggestionMarketplaces` 中列出其名稱，並且您在相同政策中聲明其來源時出現。聲明來源作為市場的 `extraKnownMarketplaces` 項目或允許清單項目。官方市場僅需要名稱。請參閱[在受管設定中啟用建議](https://code.claude.com/docs/zh-TW/plugins/relevance.md#enable-suggestions-in-managed-settings)。

> [!NOTE]
>
> 在雲端工作階段的對話中，無論您是否設定 `pluginSuggestionMarketplaces`，Claude 都可以建議外掛程式。若要關閉這些建議，請參閱[關閉外掛程式建議](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#turn-off-plugin-suggestions)。

## 稽核和檢視

OpenTelemetry 事件和 Analytics API 告訴您您的車隊安裝和執行的內容。

如需外掛程式可以在機器上執行的內容以及每個信任層允許的內容，在批准市場之前請閱讀[外掛程式安全性](https://code.claude.com/docs/zh-TW/plugins/security.md)。

### OpenTelemetry 事件

`claude_code.plugin_installed` 記錄每次安裝，`claude_code.plugin_loaded` 記錄每個啟用的外掛程式在工作階段開始時。除非您設定 `OTEL_LOG_TOOL_DETAILS=1`，否則兩個事件都會編輯或省略第三方外掛程式和市場名稱，如[您後端中的編輯外掛程式名稱](https://code.claude.com/docs/zh-TW/plugins/measure.md#redacted-plugin-names-in-your-backend)所示。欄位清單位於[外掛程式已安裝事件](https://code.claude.com/docs/zh-TW/monitoring-usage.md#plugin-installed-event)和[外掛程式已載入事件](https://code.claude.com/docs/zh-TW/monitoring-usage.md#plugin-loaded-event)。

### Analytics API

在 Enterprise 計畫上，`GET /v1/organizations/analytics/plugins` 返回跨 Claude Code 和 Cowork 的每個外掛程式、每天的安裝和調用計數。您可以按使用者或 RBAC 群組對計數進行分組。到達 Anthropic 而沒有外掛程式名稱的外掛程式活動出現在一個聚合 `third-party` 列中。請參閱[端點參考](https://platform.claude.com/docs/en/api/admin/analytics/plugins/list)和[以程式設計方式存取資料](https://code.claude.com/docs/zh-TW/analytics.md#access-data-programmatically)以了解它需要的金鑰。

## 規劃受管設定無法執行的內容

這些來自安全檢視的請求在目前設定架構中沒有專用金鑰。最接近的現有控制項是：

* **按使用者或按群組目標**：每個外掛程式金鑰適用於接收設定的每個使用者。伺服器受管設定為每個組織提供一個配置。對於按群組政策，使用單獨的端點受管設定或閘道政策，如[將發佈頻道指派給使用者群組](#assign-release-channels-to-user-groups)下所述。
* **限制允許市場內的項目**：允許清單匹配市場來源。若要從允許的市場阻止一個外掛程式，請在受管 `enabledPlugins` 中將其設定為 `false`。
* **隱藏 `/plugin`**：沒有金鑰禁用命令。最接近的等效項結合僅命名您的市場的允許清單、您提供的外掛程式的受管 `enabledPlugins` 項目和 `disableSideloadFlags`。
* **透過允許清單控制 `--plugin-dir`**：允許清單不涵蓋 `--plugin-dir`。`disableSideloadFlags` 執行。
* **透過這些金鑰執行 claude.ai 外掛程式切換**：[**組織設定 > 外掛程式與技能**](https://claude.ai/admin-settings/skills?tab=inventory)不設定此頁面上的金鑰。成員和您的組織在那裡開啟的內容作為[同步外掛程式](https://code.claude.com/docs/zh-TW/plugins/loading.md#synced-plugins)到達 CLI，它們有自己的控制項。

## 疑難排解政策

如果外掛程式政策在機器上的行為不符合預期，請首先檢查這些症狀：

* **受管檔案未解析**：當 `managed-settings.json` 不是有效 JSON 時，Claude Code 拒絕啟動並列印[命名檔案的錯誤](https://code.claude.com/docs/zh-TW/errors.md#managed-settings-document-could-not-be-parsed)。解析但有一個無效項目的檔案保持其政策的其餘部分。請參閱[受管設定中的無效項目](https://code.claude.com/docs/zh-TW/managed-settings.md#invalid-entries-in-managed-settings)。
* **受管來源未載入**：執行 `/status` 並在 `Setting sources` 行中尋找 `Enterprise managed settings`。如果遺失，來源未載入。
* **使用者報告 `blocked by enterprise policy`**：訊息命名市場或其來源。對於允許清單，它也列出允許的來源。使用者面向的項目位於[疑難排解外掛程式](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md)。
* **使用者在 `~/.claude/settings.json` 中禁用的外掛程式仍然載入**：另一個設定來源重新啟用它，例如強制啟用它的受管 `enabledPlugins` 項目。`/plugin` 和 `claude plugin list` 顯示 `Disabled in ~/.claude/settings.json but still loads` 與該設定來源。

## 後續步驟

* [市場參考](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#marketplace-sources)：`extraKnownMarketplaces`、`strictKnownMarketplaces` 和 `blockedMarketplaces` 接受的 `source` 值
* [託管和維護市場](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md)：執行您的政策指向的市場
* [外掛程式安全性和信任](https://code.claude.com/docs/zh-TW/plugins/security.md)：外掛程式可以在機器上執行的內容以及在安裝前如何檢視一個
* [管理您組織的 mods](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md)：關閉或限制 mods，在 Claude Code 內執行 JavaScript 的外掛程式
* [伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)：從 claude.ai 管理員主控台提供這些金鑰
* [疑難排解外掛程式](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#blocked-by-your-organization)：政策阻止使用者時看到的訊息

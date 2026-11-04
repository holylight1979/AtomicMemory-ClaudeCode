<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/plugins/loading | lastmod: 2026-10-25 | section: Plugins / Troubleshooting -->
> 來源：https://code.claude.com/docs/zh-TW/plugins/loading（官方 zh-TW，lastmod 2026-10-25）｜分類：Plugins › Troubleshooting｜EN 摘要：Trace where Claude Code loads each plugin from, which settings file decides whether it loads, and why an update changed nothing.

# Plugin 載入參考

> 追蹤 Claude Code 從何處載入每個 plugin，哪個設定檔決定是否載入，以及為什麼更新沒有改變任何內容。

當 plugin 未載入、載入了與預期不同的副本，或未取得更新，且您想查看哪個來源、設定範圍或磁碟上的檔案決定了這一點時，請使用此頁面。它提供了 Claude Code 在工作階段啟動時和每次執行 `/reload-plugins` 時應用的規則。您也可以要求 Claude 閱讀此頁面並診斷您的設定。

> [!NOTE]
>
> 這些情況涵蓋在其他頁面上：
>
> * **安裝、啟用、停用和更新步驟**：請參閱 [安裝和管理 plugins](https://code.claude.com/docs/zh-TW/plugins/install.md)
> * **您有特定的錯誤訊息**：請參閱 [Plugin 疑難排解](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md)

從 [檢查 plugin 達到哪個階段](#check-which-stage-a-plugin-reached) 開始，了解已安裝 plugin 通過的三個階段，或前往與您看到的內容相符的部分：

* 您關閉的 plugin 仍然載入：[找出 plugin 在何處啟用](#find-where-a-plugin-is-enabled)
* 更新沒有改變任何內容：[版本和更新](#versions-and-updates)
* 您正在查看 `~/.claude/plugins/` 下的檔案：[在磁碟上找出 plugins](#find-plugins-on-disk)
* `--plugin-dir` plugin 未載入，或載入了同名 plugin：[名稱衝突](#name-conflicts)
* `~/.claude/skills/` 或 `.claude/skills/` 下的 plugin 未載入，且沒有任何錯誤說明原因：[被受管設定封鎖的 skills 目錄 plugins](#skills-directory-plugins-blocked-by-managed-settings)

## 檢查 plugin 達到哪個階段

`enabledPlugins` 項目通過多個階段成為您可以使用的 plugin：您的設定宣告它、Claude Code 將其提取到磁碟，以及執行中的工作階段載入它。當 plugin 的行為與設定檔建議的不符時，檢查它達到了哪個階段：

* **已宣告，在設定中**：`enabledPlugins` 說明哪些 plugins 應該開啟，`extraKnownMarketplaces` 說明哪些市場應該存在。當您執行 `claude plugin marketplace add` 時，Claude Code 會將市場寫入您的使用者設定中的 `extraKnownMarketplaces` 以及磁碟
* **已提取，在 `~/.claude/plugins/` 下的磁碟上**：Claude Code 已提取的記錄和提取的檔案本身：
  * `known_marketplaces.json` 記錄每個 Claude Code 已提取的市場，包括其 `source`、`installLocation`、`lastUpdated` 和 `autoUpdate`。每個使用者有一個 `known_marketplaces.json`，因此您在一個專案中新增的市場在每個專案中都可用
  * `installed_plugins.json` 記錄每個安裝及其 `scope`、`installPath` 和 `version`
  * `cache/` 保存 plugin 檔案
* **已載入，在執行中的工作階段中**：Claude Code 在啟動時或最後一次 `/reload-plugins` 時載入的 plugin 集合。對設定或磁碟的更改不會到達此層，直到您執行 `/reload-plugins` 或啟動新工作階段。這就是為什麼 `claude plugin update` 以 `Restart to apply changes.` 結尾，背景更新會提示您 `Run /reload-plugins to apply`

### 在工作階段啟動時不在磁碟上的 Plugins 和市場

Plugins 在工作階段啟動時從 `installed_plugins.json` 和快取載入，無需使用網路。工作階段啟動後，Claude Code 在背景檢查宣告的市場：

* **設定宣告但 `known_marketplaces.json` 缺少的市場**：Claude Code 複製它，然後重新載入 plugins 並下載尚未快取的已啟用 plugins
* **宣告的市場其來源在設定中已變更**：Claude Code 從新來源重新提取它並顯示 `Plugins changed. Run /reload-plugins to activate.`

未被任何路徑提取且沒有可用快取目錄的已啟用 plugin 會在 `/plugin` **Errors** 標籤中顯示 `Plugin "<name>" not cached at <path>`。如需修復，請參閱 [`Plugin "<name>" not cached at <path>`](https://code.claude.com/docs/zh-TW/plugins/troubleshooting#plugin-not-cached-at)。

## 找出 plugin 來自何處

每個 plugin 都有形式為 `<name>@<origin>` 的 id，這是您在設定檔和 `claude plugin list --json` 中看到的。`@` 之後的部分告訴您 Claude Code 在何處找到 plugin：

| ID 結尾 | Plugin 如何到達 | 如何開啟或關閉 |
| :- | :- | :- |
| `@<marketplace>` | 您從您新增的市場安裝了它 | 在設定檔中的 `enabledPlugins` 下設定 `"<name>@<marketplace>": true` 或 `false` |
| `@inline` | 您使用 `--plugin-dir` 或 `--plugin-url` 啟動 Claude Code，設定了 [`CLAUDE_CODE_PLUGIN_DIRS`](https://code.claude.com/docs/zh-TW/env-vars#variables)，或 Agent SDK 應用程式傳遞了 `plugins` 選項。它僅針對該工作階段載入 | 除非清單設定 `defaultEnabled: false` 或設定檔設定 `"<name>@inline": false`，否則工作階段開啟 |
| `@skills-dir` | 您在 `~/.claude/skills/` 或專案的 `.claude/skills/` 下儲存了具有 `.claude-plugin/plugin.json` 的 plugin 目錄 | 清單的 `defaultEnabled`，除非設定檔將 `"<name>@skills-dir"` 設定為 `true` 或 `false` |
| `@synced` | 您或您的組織為您的 claude.ai 帳戶開啟了它，Claude Code [下載了它](#synced-plugins) | 除非清單設定 `defaultEnabled: false` 或設定檔設定 `"<name>@synced": false`，否則開啟。您的組織標記為必需的 plugin 無論如何都會載入 |

對於市場 plugin，`<name>` 是 `marketplace.json` 中的項目名稱；對於 `@inline` 和 `@skills-dir`，它是 plugin 清單中的 `name`。

此表中的來源名稱是保留的，因此沒有市場可以命名為 `inline`、`skills-dir` 或 `synced`。

### 項目名稱和清單名稱

市場 plugin 有兩個名稱，它們可能不同：

* **`marketplace.json` 中的項目名稱**：安裝和啟用金鑰。它是您在 `enabledPlugins` 中寫入的內容、快取目錄的命名依據，以及 `claude plugin list` 顯示的內容
* **清單中的 `name`**：plugin 的元件命名空間所在的位置，以及 [名稱衝突](#name-conflicts) 比較的內容

### 透過儲存庫共享的 Plugins

若要透過儲存庫共享 plugin，請在 `.claude/settings.json` 中的 `enabledPlugins` 下列出它，或將其放在 `.claude/skills/` 下。Claude Code 不掃描專案的 `.claude/plugins/` 目錄。

雲端工作階段不會新增儲存庫在 [`extraKnownMarketplaces`](https://code.claude.com/docs/zh-TW/settings-reference#extraknownmarketplaces) 下列出的市場，因為這需要工作區信任對話框，雲端工作階段永遠不會顯示。

#### 儲存庫 plugin 的信任檢查與元件限制

專案範圍的 plugin 被簽入儲存庫，並到達複製它的每個協作者。因為該內容來自儲存庫而不是來自您，它僅在應用於 `.claude/settings.json` 中專案允許規則的相同信任檢查後載入。信任父資料夾或使用 `-p` 執行是不夠的。執行程式碼的元件受到進一步限制：

* 它宣告的 MCP 伺服器通過 [相同的每個伺服器核准](https://code.claude.com/docs/zh-TW/mcp.md) 作為專案 `.mcp.json`
* 它宣告為 [MCP 套件](https://code.claude.com/docs/zh-TW/plugins/manifest-reference.md#mcpservers) 的 MCP 伺服器、`.mcpb` 或 `.dxt` 檔案，或來自 plugin 目錄外的檔案被跳過。在 plugin 目錄內內聯或在 `.mcp.json` 中宣告它們
* [背景監視器](https://code.claude.com/docs/zh-TW/plugins/components.md#monitors) 不載入

信任檢查和這些元件限制都不適用於您自己的 `~/.claude/skills/` 下的 plugin。

如需如何編寫 `--plugin-dir` 和技能目錄 plugins，請參閱 [建立 plugins](https://code.claude.com/docs/zh-TW/plugins/create.md)。

#### 檢查儲存庫 plugin 為何沒有載入

如果儲存庫 `.claude/skills/` 中的 plugin 沒有載入，請檢查以下原因：

* **在子目錄中**：儲存庫根目錄的 plugin 不會載入。Claude Code 讀取工作階段 [主要工作目錄](https://code.claude.com/docs/zh-TW/permissions.md#working-directories) 的 `.claude/skills/`，且不同於一般 skill 和命令，不會為 plugin [搜尋父目錄](https://code.claude.com/docs/zh-TW/skills.md#discovery-from-parent-and-nested-directories)。請改為從儲存庫根目錄啟動，或在 v2.1.246 或更新版本上 [使用 `/cd` 將工作階段移到那裡](https://code.claude.com/docs/zh-TW/permissions#move-the-session-to-another-directory)
* **從桌面應用程式，在 worktree 中**：plugin 從主要 checkout 的 `.claude/skills/` 載入，而不是從 worktree 的載入。請參閱 [worktree 與主要 checkout 共享的內容](https://code.claude.com/docs/zh-TW/worktrees.md#what-worktrees-share-with-the-main-checkout)
* **在您尚未信任的資料夾中**：plugin 僅在您接受該資料夾的 [工作區信任對話框](https://code.claude.com/docs/zh-TW/permissions.md#what-runs-before-you-trust-a-folder) 後才會載入
* **在管理 Claude Code 的組織中**：請參閱 [受管設定封鎖的 skills 目錄 plugin](#skills-directory-plugins-blocked-by-managed-settings)

### 受管設定封鎖的 skills 目錄 plugin

如果 `~/.claude/skills/` 或專案 `.claude/skills/` 中的 plugin 資料夾沒有載入，且您沒有看到任何錯誤，您的管理員可能已透過 [受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md) 封鎖了它。這些資料夾來自您或您的儲存庫，而非來自市集，因此當您的管理員設定以下任一限制時，Claude Code 會跳過它們：

* **自訂項目鎖定為僅限 plugin**：[`strictPluginOnlyCustomization`](https://code.claude.com/docs/zh-TW/settings-reference#strictpluginonlycustomization) 設定為 `true`，或設定為列出一或多種要鎖定之自訂類型的陣列。只要有任何一種類型被鎖定（例如 `mcp`），無論 plugin 包含哪些元件，整個 plugin 都會被跳過。
* **市集來源受限**：[`strictKnownMarketplaces`](https://code.claude.com/docs/zh-TW/settings-reference#strictknownmarketplaces) 允許清單中沒有 `{ "source": "skills-dir" }` 項目，或 [`blockedMarketplaces`](https://code.claude.com/docs/zh-TW/settings-reference#blockedmarketplaces) 清單中包含該項目。

對於被跳過的資料夾，`/plugin` 和 `claude plugin list` 不會顯示任何 plugin，也不會顯示任何錯誤。其 `/<name>:<skill>` 命令和 agent 都不存在，其 hook 和 MCP 伺服器也是如此。

除非 skill 屬於被鎖定的類型，否則資料夾根目錄的 `SKILL.md` 仍會作為一般 skill 載入。在這種情況下，`/<name>` 仍可運作，且 `/plugin` **Installed** 標籤會在 **Skills** 下列出該 skill。

* **確認原因**：在 Claude Code 工作階段中執行 `/status`。如果 `Setting sources` 行列出 `Enterprise managed settings`，請詢問您的管理員這些設定中是否有任何一項適用於您。如果沒有，請參閱 [檢查儲存庫 plugin 為何沒有載入](#check-why-a-repository-plugin-didnt-load) 以了解其他原因。
* **載入整個 plugin**：將其新增到您的組織允許的 [市集](https://code.claude.com/docs/zh-TW/plugins/create-marketplace.md#create-a-marketplace)，並從該處安裝。若只想在單一工作階段中載入，請從您的 shell 使用 [`--plugin-dir`](https://code.claude.com/docs/zh-TW/plugins/cli-reference#flags-that-load-a-plugin-for-one-session) 和該資料夾的路徑啟動 `claude`，除非您的管理員也關閉了該旗標，否則此方法都能運作。

### 從 claude.ai 同步的 Plugins

您為 claude.ai 帳戶開啟的 plugin 也會在 Claude Code 中載入，與您從市場安裝的 plugins 並排。這包括您的組織為其成員開啟的 plugins。這些 plugins 中的每一個都以 `<name>@synced` 載入，沒有市場，也沒有 [安裝記錄](#check-which-stage-a-plugin-reached)。

在終端工作階段中，同步 plugin 的技能、代理、hooks、MCP 伺服器和 LSP 伺服器都會載入，具有與您安裝的市場 plugin 相同的信任。

如需 Cowork 載入的元件，請參閱 claude.com 上的 [元件支援表](https://claude.com/docs/plugins/platform-support#compare-component-support-by-app)。

同步 plugins 在 Cowork 工作階段和您使用 claude.ai 帳戶登入的終端工作階段中載入：

* **[Cowork](https://claude.com/product/cowork)**：Claude Code 在工作階段啟動時將它們下載到工作階段自己的環境中
* **終端工作階段**：每次您啟動 Claude Code 時，它在背景同步一次，下載新的和更新的 plugins，並移除您或您的組織關閉的 plugins。終端工作階段中的同步需要 Claude Code v2.1.273 或更新版本

#### 雲端 Cowork 工作階段中的同步時機

如果您在雲端執行的 Cowork 工作階段期間為您的 claude.ai 帳戶開啟或關閉 plugin，請繼續在該工作階段中工作。如果幾則訊息之後仍沒有任何變化，請啟動新的工作階段。

#### 終端工作階段中的同步時機

因為終端同步在背景執行，它可能在您的工作階段啟動後完成。當它在互動式工作階段中新增、更新或移除同步 plugin 時，您會看到 `Plugins changed. Run /reload-plugins to activate.` 執行 `/reload-plugins` 以在該工作階段中載入變更，或將其留待下次啟動 Claude Code 時。

如果您在終端機工作階段期間為您的 claude.ai 帳戶開啟或關閉 plugin，Claude Code 會在您下次啟動 Claude Code 時下載或移除它。

#### 終端同步的登入要求

在您的終端中，plugins 僅在您使用 claude.ai 帳戶登入的工作階段中同步。

Claude Code 在這些終端工作階段中既不下載也不載入同步 plugins，即使您使用 `/login` 登入後：

* 一個工作階段，其中 `ANTHROPIC_AUTH_TOKEN`、`CLAUDE_CODE_OAUTH_TOKEN` 或 `apiKeyHelper` 指令碼提供認證以代替該登入
* 一個不 [從 Anthropic 擷取功能旗標](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching) 的工作階段，例如您設定 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` 的工作階段
* 一個在 [裸機模式](https://code.claude.com/docs/zh-TW/headless.md#start-faster-with-bare-mode) 中的工作階段或您使用 `--safe-mode` 啟動的工作階段
* 一個您使用 [`--setting-sources`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 列表啟動的工作階段，該列表遺漏了 `user`

如果您在較早版本的 Claude Code 上登入，該登入不涵蓋 plugins，直到 Claude Code 在背景更新它。若要更快獲得存取權，請再次執行 `/login`。Plugin 同步然後在您下次啟動 Claude Code 時開始。

#### 控制哪些同步 plugins 載入

您可以一次關閉一個同步 plugin，除了您的組織要求的 plugin，或關閉機器上的每個同步 plugin：

* **一個 plugin**：在您的殼層中執行 `claude plugin disable <name>@synced`，工作階段中的 `/plugin` **Installed** 標籤都在您的使用者級別 [`enabledPlugins`](https://code.claude.com/docs/zh-TW/settings-reference#enabledplugins) 中儲存 `"<name>@synced": false`。若要在每個環境中將 plugin 保留在專案之外，在專案的已提交 `.claude/settings.json` 中設定相同的金鑰
* **機器上的每個同步 plugin**：在您的使用者設定中設定 [`syncClaudeAiPlugins`](https://code.claude.com/docs/zh-TW/settings-reference#syncclaudeaiplugins) 為 `false`，或您的組織在 [受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md) 中設定它。Claude Code 停止下載，下次啟動時，它將已同步的 plugins 移到 `~/.claude/plugins/.trash/`，不再載入它們。如果您的組織在 claude.ai 上關閉技能，plugins 也會停止同步
* **您的組織要求的 plugin**：您的組織在 claude.ai 上標記為必需的 plugin 即使您之前停用它也會載入。`claude plugin disable` 拒絕它，顯示 `Plugin "<name>@synced" is required by your organization and can't be disabled here. Contact your admin to change it.`，`claude plugin list` 將其標記為 `required by your org`

如需在 claude.ai 上移除 plugin，請參閱 [管理已安裝的 plugins](https://code.claude.com/docs/zh-TW/plugins/install.md#manage-installed-plugins)。

## 找出 plugin 在何處啟用

您可以在六個來源中的任何一個設定 `enabledPlugins` 項目。該表從最低優先順序到最高列出它們，以及每個適用於誰。如需設定檔本身，請參閱 [設定檔和它們影響的人](https://code.claude.com/docs/zh-TW/settings.md#where-settings-live)。

| 來源 | 您在何處設定它 | 到達 |
| :- | :- | :- |
| `--add-dir` | 您使用 `--add-dir` 傳遞的目錄中的 `.claude/settings.json` 或 `.claude/settings.local.json` | 僅此工作階段。只有 `true` 值有效果，每個其他來源都會覆蓋它 |
| `user` | `~/.claude/settings.json` | 您，在每個專案中 |
| `project` | `.claude/settings.json` | 複製儲存庫的每個人 |
| `local` | `.claude/settings.local.json` | 您，僅在此儲存庫中 |
| `flag` | 您在啟動時傳遞的 `--settings` 值 | 僅此工作階段 |
| `managed` | [受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md) | 政策涵蓋的每個使用者。`true` 強制啟用，`false` 阻止，沒有其他來源覆蓋它們 |

這些來源逐個金鑰合併。對於每個 plugin id，適用的值是來自提及該 id 的最高優先順序來源的值。不提及該 id 的來源會保留來自較低優先順序來源的值。

### 在使用者設定中停用但仍然載入

如果您在 `~/.claude/settings.json` 中將 plugin 設定為 `false`，但它仍然載入，較高優先順序來源中的 `true` 會覆蓋它。plugin 在 `claude plugin list` 和 `/plugin` 中的行顯示 `Disabled in ~/.claude/settings.json but still loads — project settings enable it, which overrides your user setting`。該訊息命名覆蓋您的來源：`project`、`project, gitignored`（針對 `.claude/settings.local.json`）、`cli flag` 或 `managed`。

若要選擇退出您機器上的專案啟用 plugin，在 `.claude/settings.local.json` 中將 id 設定為 `false`，其優先順序高於專案檔案。

### 在專案設定中啟用但未安裝

當 plugin 的唯一 `true` 在專案的 `.claude/settings.json` 中時，Claude Code 不會在未安裝它的機器上提取它，除非其市場項目具有 [相對路徑來源](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#plugin-sources) 或 [種子目錄](https://code.claude.com/docs/zh-TW/plugins/org.md#seed-containers-and-ci) 已經保存它。相反，`/plugin` **Errors** 標籤顯示 `Plugin "<name>" is enabled in project settings but isn't installed here`。

相對路徑 plugin 不需要安裝記錄，因為它從市場本身載入。

Claude Code 僅當以下來源之一將其設定為 `true` 時才提取具有外部來源的 plugin：

* 您的使用者設定
* git 不追蹤的 `.claude/settings.local.json`
* `--settings` 旗標
* 受管設定

## 在磁碟上找出 plugins

Claude Code 在一個 plugins 根目錄下保存 plugin 檔案和狀態記錄，該目錄是 `~/.claude/plugins`，除非您設定 [`CLAUDE_CODE_PLUGIN_CACHE_DIR`](https://code.claude.com/docs/zh-TW/env-vars)。表中的每個路徑都相對於該根目錄。

| 路徑 | 它保存什麼 |
| :- | :- |
| `cache/<marketplace>/<plugin>/<version>/` | 市場 plugin 的每個已安裝版本一個目錄。`<plugin>` 是市場項目名稱，`<version>` 是 [已解決的版本](#versions-and-updates)。`${CLAUDE_PLUGIN_ROOT}` 指向此目錄 |
| `data/<plugin-id>/` | plugin 的持久目錄，公開為 `${CLAUDE_PLUGIN_DATA}`。如需如何形成 `<plugin-id>`，請參閱 [路徑變數和持久資料](https://code.claude.com/docs/zh-TW/plugins/components.md#path-variables-and-persistent-data)。Claude Code 在 plugin 元件首次使用它時建立它，並在更新中保留它。當您從其最後一個範圍卸載 plugin 時，Claude Code 會刪除它，除非您傳遞 `--keep-data`。如需 `--keep-data` 和其他它保留的情況，請參閱 [plugin 卸載](https://code.claude.com/docs/zh-TW/plugins/cli-reference.md#plugin-uninstall) |
| `marketplaces/<name>/` | 從 GitHub、另一個 Git 主機或 URL 新增的市場的複製或下載。從本地 `file` 或 `directory` 來源新增的市場在此處沒有副本，其 `known_marketplaces.json` 中的 `installLocation` 是您提供的路徑 |
| `synced/` | Claude Code [從您的 claude.ai 帳戶同步的 plugins](#synced-plugins) |
| `.trash/` | claude.ai 同步移除的 plugins，例如在您在 claude.ai 上關閉一個或停止同步後 |
| `installed_plugins.json` 和 `known_marketplaces.json` | Claude Code 已安裝的記錄和已提取的市場，在 [檢查 plugin 達到哪個階段](#check-which-stage-a-plugin-reached) 下描述。[在 claude.ai 上託管的市場](https://code.claude.com/docs/zh-TW/plugins/install.md#add-from-claude-ai) 改為記錄在 `known_marketplaces_claudeai.json` 中 |
| `flagged-plugins.json` | Claude Code 卸載的 plugins，因為其市場將其除名。它們出現在 `/plugin` 的 **Flagged** 部分；請參閱 [託管市場](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md) |
| `installed_plugins.set-aside.<date>.<hash>.json` 和 `installed_plugins.unreadable.<date>.<hash>.kept` | 日期副本 Claude Code 在捨棄無法使用的安裝記錄或重建無法讀取的 `installed_plugins.json` 之前保留。請參閱 [復原說明](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#installed-plugins-json-could-not-be-read-and-was-rebuilt)。它們按照 [`cleanupPeriodDays`](https://code.claude.com/docs/zh-TW/settings-reference#cleanupperioddays) 排程老化 |

因為 `${CLAUDE_PLUGIN_ROOT}` 指向版本目錄，plugin 的根路徑隨著每個版本而變化。改為在 `${CLAUDE_PLUGIN_DATA}` 中保存 plugin 的持久檔案。

### 就地和複製的 plugins

Claude Code 根據 plugins 的來源，從您保存它們的位置就地載入某些 plugins，並將其餘的複製到快取中：

* **`--plugin-dir` 和技能目錄 plugins**：目錄就地載入，永遠不會被複製。`--plugin-url` 存檔或 `--plugin-dir` `.zip` 首先被提取到工作階段臨時目錄中
* **您從本機路徑新增的市集中的相對路徑外掛**：外掛從其在市集資料夾內的路徑就地載入。您對來源目錄的編輯會在下次工作階段啟動或 `/reload-plugins` 時生效，您無需增加版本。外掛的 hook 程序以及 MCP 和 LSP 伺服器會接收指向來源目錄的 `CLAUDE_PLUGIN_ROOT`。如需其 Node.js 相依套件，請參閱[相依套件安裝何時執行](#when-the-dependency-install-runs)
* **[連結模式](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#command-plugin-source) 中的 `command` 來源 plugins**：命令列印的目錄通過快取項目中的連結就地載入
* **每個其他市場 plugin**：Claude Code 在安裝時將 plugin 複製到 `cache/<marketplace>/<plugin>/<version>/` 中並從該副本載入。plugin 目錄外的檔案不被複製，因此當 plugin 內的指令碼讀取 plugin 根目錄上方的路徑（例如 `../shared`）時，它找不到它們

### 逃逸 plugin 目錄的路徑

無論 plugin 就地載入還是從快取副本載入，Claude Code 都不允許它宣告其自己目錄外的元件。它拒絕解決為 plugin 根目錄外的元件路徑，無論路徑是在 `plugin.json` 還是市場項目中宣告的：

* **指向 plugin 外部的路徑，如寫入的那樣**，例如 `../shared-utils`
* **導致 plugin 外部的符號連結**，除了 [一個市場內 plugins 之間的連結](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md#share-files-within-a-marketplace-with-symlinks)
* **在 macOS 和 Linux 上，路徑中任何地方包含反斜杠的路徑**，即使路徑保留在 plugin 內。因此使用反斜杠路徑宣告的元件僅在 Windows 上載入，因此使用正斜杠編寫元件路徑，例如 `./commands/deploy.md`

被拒絕的路徑顯示為 [`path escapes plugin directory`](https://code.claude.com/docs/zh-TW/errors#path-escapes-plugin-directory) 錯誤，plugin 載入時不包含該元件。

### 舊版本的清理

當您更新或卸載 plugin 時，Claude Code 將 `.orphaned_at` 標記寫入舊版本目錄。它在 14 天後的背景清理中移除該目錄，因此已載入舊版本的工作階段繼續執行。

掃描僅在 `installed_plugins.json` 記錄至少一個安裝時執行。卸載最後一個 plugin 後，孤立目錄保留，直到您安裝另一個。

### Node.js 套件依賴項

當 Claude Code 將 plugin 複製到快取時，它也會在那裡安裝 plugin 的 Node.js 套件依賴項，以便 plugin 的 hooks 和 MCP 伺服器可以載入它們。

本部分涵蓋 plugin 在其自己的 `package.json` 中宣告的 npm 和 Bun 套件。對於依賴其他 plugins 的 plugins，請參閱 [plugin 依賴項版本](https://code.claude.com/docs/zh-TW/plugins/dependencies.md)。

#### 依賴項安裝何時執行

Claude Code 每次建立複製的版本目錄時，都會將相依套件安裝到其中：

* 當您安裝 plugin 時
* 當 Claude Code 將 plugin 更新到新版本時
* 在工作階段啟動時，當已啟用 plugin 尚未快取時，例如在新機器上

對於從您以本機路徑新增的市集[就地載入](#in-place-and-copied-plugins)的相對路徑外掛，Claude Code 不會將相依套件安裝到來源目錄中。請自行在那裡安裝，或從 hook 安裝到 [`${CLAUDE_PLUGIN_DATA}`](https://code.claude.com/docs/zh-TW/plugins/components#path-variables-and-persistent-data)。

安裝僅在外掛的根目錄同時包含 `package.json` 和支援的鎖定檔案時執行。

鎖定檔案決定 Claude Code 執行哪個套件管理器：

| 鎖定檔案 | 套件管理器 |
| :- | :- |
| `bun.lock` | Bun |
| `npm-shrinkwrap.json` 或 `package-lock.json` | npm |

如果外掛包含多個這些鎖定檔案，Claude Code 會使用第一個符合項，依序檢查：`bun.lock`、`npm-shrinkwrap.json`、`package-lock.json`。

Claude Code 在以下鎖定檔案情況下會跳過安裝：

* **`bun.lockb`**：Bun 的二進位鎖定檔案無法檢查。請改為提供文字格式的 `bun.lock` 或 npm 鎖定檔案
* **`yarn.lock` 或 `pnpm-lock.yaml`**：請將其替換為 npm 鎖定檔案
* **Claude Code 無法讀取格式的鎖定檔案**：npm 鎖定檔案需要 `lockfileVersion` 為 `2` 或 `3`（由 npm 7 或更新版本寫入），而 `bun.lock` 需要 `lockfileVersion` 不高於 `2`

包含 npm 鎖定檔案以到達最多使用者。Claude Code 從使用者的 PATH 執行匹配的鎖定檔案的套件管理器，如果缺少該套件管理器，不會嘗試其他鎖定檔案。

對於透過 npm 來源分發的 plugin，使用 `npm-shrinkwrap.json`，因為 npm 從已發佈的套件中排除 `package-lock.json`。

#### 依賴項安裝的限制

Claude Code 限制此依賴項安裝，以便 plugin 或其套件中的任何程式碼在安裝期間不執行，並限制其執行時間：

* **僅限登錄檔套件**：每個相依套件都必須是在鎖定檔案中固定到確切版本的登錄檔套件。具有 git、GitHub、資料夾、工作區或連結相依套件的外掛不會進行安裝。
* **`https` 下載**：鎖定檔案中的下載連結必須使用 `https`，除非它指向執行安裝之使用者自己的預設 npm 登錄檔。
* **獨立的安裝資料夾**：套件管理器在其自身的資料夾中執行，該資料夾僅包含已檢查之相依套件清單的副本，因此 npm 和 Bun 不會讀取外掛的 `.npmrc`、`.env` 或 `bunfig.toml`。安裝成功時，Claude Code 會將產生的 `node_modules` 移入外掛。
* **凍結解析**：安裝完全使用鎖定檔案固定的版本，當 `package.json` 和鎖定檔案列出的相依套件不一致時，Claude Code 會跳過安裝
* **無生命週期指令碼**：`--ignore-scripts` 防止 `preinstall`、`install` 和 `postinstall` 指令碼執行，因此在這些指令碼中建立原生模組的依賴項在此安裝期間下載但不編譯
* **無覆寫或修補**：`package.json` 設定了 npm `overrides` 的外掛不會從 npm 鎖定檔案進行安裝，而設定了 Bun `patchedDependencies` 的外掛不會從 `bun.lock` 進行安裝
* **60 秒超時**：Claude Code 停止執行超過 60 秒的安裝並將其視為失敗

Claude Code 在此依賴項安裝之前提取 npm 來源 plugin，套件自己的安裝指令碼在提取期間不執行。請參閱 [npm plugin 來源](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#npm-plugin-source)。

您無法關閉自動安裝。沒有設定或環境變數停用它。

在受限網路中，請參閱 [網路存取要求](https://code.claude.com/docs/zh-TW/network-config.md#network-access-requirements) 以允許的主機。

#### 依賴項安裝失敗或被跳過時

如果安裝失敗或被跳過，外掛仍會載入，但需要缺少之套件的部分可能無法運作。

對於已啟用的外掛，若其快取副本具有鎖定檔案以及列出執行階段相依套件的 `package.json`，但沒有 `node_modules` 目錄，`/plugin` 和 `claude plugin list` 會顯示一則說明。該說明會指出安裝是未完成，還是無法針對此外掛執行。如需了解各種情況的處理方式，請參閱[疑難排解項目](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#the-packages-it-lists-are-not-installed)。

當自動安裝無法提供相依套件時，請從 hook 將其安裝到 [持久資料目錄](https://code.claude.com/docs/zh-TW/plugins/components.md#path-variables-and-persistent-data)。這包括需要其生命週期指令碼來建置的套件、Python 相依套件、使用 Yarn 或 pnpm 鎖定的外掛，以及非登錄檔套件的相依套件，例如 git 相依套件。

## 版本和更新

如果 plugin 的作者推送了新提交，`claude plugin update` 列印 `<name> is already at the latest version (<version>).`，Claude Code 為 plugin 計算的版本未變更，因此磁碟上的 plugin 檔案不會變更。

Claude Code 為它安裝的每個 plugin 計算版本，這就是它如何檢測更新的方式。`claude plugin update` 和背景自動更新再次計算版本，當它與 `installed_plugins.json` 記錄的內容相符時，不會取代快取副本。您啟動的更新仍可在該副本中[重試未完成的相依套件安裝](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#the-packages-it-lists-are-not-installed)。

版本也命名 plugin 的快取目錄。

固定 `"version"` 的清單是計算的版本在提交中保持相同的一種方式。請參閱 [Claude Code 如何計算版本](#how-claude-code-computes-the-version) 以了解解決順序。

從您透過本機路徑新增的市集 [就地載入](#in-place-and-copied-plugins) 的 plugin 在每次工作階段啟動時載入其當前來源檔案，無論其版本字串說什麼。對於從 [在 claude.ai 上託管的市集](https://code.claude.com/docs/zh-TW/plugins/install.md#add-from-claude-ai) 的 plugin，claude.ai 為 plugin 記錄的版本是其版本，清單的 `version` 不被讀取。

### Claude Code 如何計算版本

對於您按來源新增的市場，Claude Code 按 plugin 市場項目的 `source` 類型選擇規則。[市場參考](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#plugin-sources) 列出來源類型。對於該列表中除 `command` 外的每個來源類型：

1. plugin 清單中的 `version` 欄位首先出現
2. 然後 plugin 市場項目中的 `version` 欄位
3. 當都未設定時，版本來自來源類型：

| 來源類型 | 未設定 `version` 欄位時的版本 |
| :- | :- |
| `github`、`url` 或 `git-subdir` | 來源的提交 SHA，縮短為 12 個字元。`git-subdir` 版本也帶有子目錄路徑的雜湊 |
| `archive` | SHA-256 摘要，縮短為 12 個字元：市場項目中的 `sha256` 固定，或沒有固定時下載檔案的摘要 |
| Git 託管市場內的相對路徑 | 已安裝目錄的提交 SHA |
| 本地目錄，當 plugin 目錄和其市場都不是 git 儲存庫時 | `unknown` |
| `npm` | `unknown` |

Claude Code 不從包含安裝路徑的儲存庫（例如 git 管理的 `~/.claude`）取得版本。

對於 `command` 來源，Claude Code 始終從命令產生的內容衍生版本：其自己的 12 字元雜湊，或當清單設定一個時 `<manifest version>-<hash>`。市場項目的 `version` 對於命令來源被忽略。如需雜湊涵蓋的內容，請參閱 [複製模式和連結模式](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#copy-mode-and-link-mode)。

因為清單首先出現，固定 `"version": "1.0.0"` 的清單將每個使用者保留在快取副本上，直到其作者更改字串，無論他們推送多少提交。若要讓使用者改為追蹤提交，請從清單和項目中都省略 `version`。[託管市場](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md) 涵蓋哪個選擇適合哪個發佈設定。

### Claude Code 何時在安裝前重新整理市場

當您安裝 plugin 時，Claude Code 在其市場目錄的本地副本中查找它。您可以在工作階段中執行 `/plugin install` 或在殼層中執行 `claude plugin install`，並使用或不使用其市場命名 plugin。該表顯示這些組合中哪些重新整理本地副本。

| Plugin 名稱 | 命令 | Claude Code 重新整理什麼 |
| :- | :- | :- |
| `name@marketplace` | `/plugin install` 或 `claude plugin install` | 查找前的命名市場 |
| 僅 `name` | `/plugin install` | 僅具有自動更新的市場，且僅在查找失敗後 |
| 僅 `name` | `claude plugin install` | 無。它讀取快取的目錄而不重新整理 |

`name@marketplace` 安裝前的重新整理不取決於市場的自動更新設定或 `DISABLE_AUTOUPDATER`。

當重新整理失敗時，安裝從快取目錄進行，`claude plugin install` 報告 `marketplace not refreshed`。

Claude Code 在以下情況下跳過 `name@marketplace` 安裝前的重新整理：

* 市場從本地 `file` 或 `directory` 來源新增，或在設定中內聯定義，具有 [`settings` 來源](https://code.claude.com/docs/zh-TW/settings-reference#extraknownmarketplaces)
* [種子目錄](https://code.claude.com/docs/zh-TW/env-vars.md) 提供市場
* Claude Code 在過去 30 秒內重新整理了市場
* 您設定 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`
* [受管設定](https://code.claude.com/docs/zh-TW/plugins/org.md#restrict-what-users-can-install) 阻止市場，在這種情況下 Claude Code 也拒絕安裝

### 自動更新何時執行

在互動式工作階段中，在您傳送第一條訊息後，Claude Code 等待最多十分鐘的隨機延遲。然後它重新整理每個啟用自動更新的市場，並更新從它們在磁碟上安裝的 plugins。

執行中的工作階段保留它載入的版本，您會看到 `Plugin updated: <name> · Run /reload-plugins to apply`。無論您是否重新載入，新版本在您下次啟動時載入。

#### 哪些市場和 plugins 自動更新

市場是否自動更新遵循首先設定的：

1. **其 `extraKnownMarketplaces` 項目中的 `autoUpdate`** 在設定檔中
2. **其 `known_marketplaces.json` 項目中的 `autoUpdate`**，`/plugin` **Marketplaces** 下的 **Enable auto-update** 切換寫入。當設定檔也在 `extraKnownMarketplaces` 下宣告市場時，切換也將 `autoUpdate` 寫入該設定項目
3. **預設**：對於 Anthropic 的官方市場（例如 `claude-plugins-official`）開啟，對於 `knowledge-work-plugins` 和 `first-party-plugins` 關閉，對於 [從 claude.ai 新增的市場](https://code.claude.com/docs/zh-TW/plugins/install.md#add-from-claude-ai) 開啟，對於每個其他市場關閉

如果您設定 `DISABLE_UPDATES=1`、`DISABLE_AUTOUPDATER=1` 或 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`，整個傳遞關閉，**Enable auto-update** 切換隱藏，除非您也設定 `FORCE_AUTOUPDATE_PLUGINS=1`。[環境變數參考](https://code.claude.com/docs/zh-TW/env-vars.md) 涵蓋每個變數的更廣泛效果。

自動更新也跳過其市場項目宣告 `headersHelper` 的 plugin。[拒絕命令而不是詢問的安裝和更新](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md#installs-and-updates-that-refuse-the-command-instead-of-asking) 解釋何時此類 plugin 出現在 `/plugin` **Errors** 標籤中以及如何從那裡更新它。

當複製的 plugin 在工作階段中期更新時，hook 命令、監視器、MCP 伺服器和 LSP 伺服器繼續使用舊版本的路徑。執行 `/reload-plugins` 以將 hooks、MCP 伺服器和 LSP 伺服器切換到新路徑。監視器需要工作階段重新啟動。

### 何時命令來源重新執行

具有 `command` 來源的 Plugins 不等待 [自動更新傳遞](#when-auto-update-runs)。列印的目錄反映工具在命令執行時的狀態，因此 Claude Code 在以下時間再次執行 [您接受的命令](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md#change-the-command-of-a-command-source)：

* 每次您安裝或更新 plugin 時
* 每個已啟用命令來源 plugin 每個工作階段一次，在工作階段啟動後不久在背景中。此執行不取決於市場的自動更新設定或 `DISABLE_AUTOUPDATER`
* 在啟動或 `/reload-plugins` 時，當已啟用 plugin 的已安裝版本在 plugin 快取中遺失時

當您設定 [`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`](https://code.claude.com/docs/zh-TW/env-vars) 時，Claude Code 跳過兩個背景執行。明確安裝和更新仍然使用該變數集執行命令。

當命令的雜湊輸出已變更時，Claude Code 將結果安裝為新版本，並在執行中的互動式工作階段中重新載入它，切換 [`/reload-plugins` 切換的相同元件](https://code.claude.com/docs/zh-TW/plugins/cli-reference#reload-plugins)。您會看到 plugin 已重新載入的通知。

如果就地重新載入會使工作階段的提示快取失效，Claude Code 改為提示您執行 `/reload-plugins`，它 [警告快取成本並在使用 `--force` 重新執行時應用](https://code.claude.com/docs/zh-TW/prompt-caching#enabling-or-disabling-a-plugin)。

## 名稱衝突

當來自不同來源的已啟用 plugins 共享清單名稱時，此順序決定哪一個載入，從最高優先順序到最低：

1. 其 id 出現在受管設定 `enabledPlugins` 中的 plugin，如 `true` 或 `false`。其清單名稱與 id 的名稱部分匹配的 `--plugin-dir` 副本不被載入，您會看到 `--plugin-dir copy of "<name>" ignored: plugin is locked by managed settings`
2. 已啟用的 `--plugin-dir`、`--plugin-url` 或 `CLAUDE_CODE_PLUGIN_DIRS` plugin。它替換同名的已安裝市場 plugin 或技能目錄 plugin：
   * **已安裝的市場 plugin**：無聲替換。`claude plugin list` 仍然顯示市場行為已啟用，因為該行反映您的設定。只有當您使用 `--debug` 啟動時 Claude Code 在 `~/.claude/debug/` 下寫入的日誌記錄 `Plugin "<name>" from --plugin-dir overrides installed version`
   * **技能目錄 plugin**：替換為 `/plugin` **Errors** 標籤行，讀取 `Not loaded — the name "<name>" is already taken by a session-only plugin (--plugin-dir / --plugin-url), which takes precedence`
3. 已安裝的市場 plugin。同名的技能目錄 plugin 獲得相同的 `Not loaded` 行，命名已安裝的 plugin
4. 技能目錄 plugin。在這兩者之間，`~/.claude/skills/` 下的副本載入，專案的 `.claude/skills/` 副本被丟棄，帶有一行說明哪個路徑遮蔽了它
5. 從 claude.ai [同步的 plugin](#synced-plugins)。當來自任何其他來源的已啟用 plugin 與其名稱匹配時，Claude Code 載入該 plugin 並報告同步副本未載入。若要改為使用 claude.ai 副本，停用您自己的副本

因為順序比較清單名稱，名為 `hello-plugin` 的 `--plugin-dir` plugin 在該 plugin 的清單也說 `"name": "hello-plugin"` 時替換 `hello@example-marketplace`。

### 兩個已啟用外掛共用名稱時的 hook

當您從不同市集安裝並啟用兩個清單名稱相同的外掛時，兩者在 `/plugin` 中都會顯示為已啟用，但其中一個的 hook 會被排除。每個名稱只有一個外掛會註冊其 `hooks/hooks.json` 中的 hook，也只有一個外掛會載入 [hook 模組](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md)。當您組織的受管設定啟用了其中一個副本時，由該副本持有此名稱。否則由 Claude Code 先載入的副本持有。

若要查看哪個副本持有此名稱，請在工作階段中執行 `/plugin` 並開啟 **Errors** 分頁。該處會針對 hook 被排除的副本顯示一則說明，指出持有此名稱的副本，被排除副本的詳細資訊中也會顯示相同說明。對於 `hooks/hooks.json` hook，該說明以 `Its hooks.json hooks do not run` 開頭；對於 hook 模組，則以 `Its hooks module does not load` 開頭。此說明需要 Claude Code v2.1.296 或更新版本。

若要改為執行被排除副本的 hook，請停用或解除安裝持有此名稱的副本，然後在工作階段中執行 `/reload-plugins`。重新載入會註冊剩餘副本的 hook 並清除該說明。當持有此名稱的副本是由受管設定啟用時，您無法停用它，且只要兩者都已安裝，另一個副本的 hook 就會保持關閉。

### 防止工作階段專用 plugin 載入

若要防止 `--plugin-dir` plugin 遮蔽任何內容，或在父程序為您傳遞旗標時關閉一個，在任何設定檔中將其 id 設定為 `false`。對於清單名稱為 `hello-plugin` 的 plugin，項目是 `"enabledPlugins": {"hello-plugin@inline": false}`。停用的工作階段專用 plugin 不遮蔽，因此市場或技能目錄副本改為載入。

## 後續步驟

* [安裝和管理 plugins](https://code.claude.com/docs/zh-TW/plugins/install.md)：安裝、啟用、停用和更新步驟本身
* [Plugin 疑難排解](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md)：按產生它們的階段的錯誤訊息
* [Plugin 命令參考](https://code.claude.com/docs/zh-TW/plugins/cli-reference.md)：此頁面上命名的旗標和命令
* [為您的組織管理 plugins](https://code.claude.com/docs/zh-TW/plugins/org.md)：強制啟用或阻止 plugins 的受管設定

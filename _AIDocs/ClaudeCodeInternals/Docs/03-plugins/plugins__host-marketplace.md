<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/plugins/host-marketplace | lastmod: 2026-10-26 | section: Plugins / Run a marketplace -->
> 來源：https://code.claude.com/docs/zh-TW/plugins/host-marketplace（官方 zh-TW，lastmod 2026-10-26）｜分類：Plugins › Run a marketplace｜EN 摘要：Publish a plugin marketplace where users can reach it, grant access to a private one, and release updates and renames without breaking installs.

# 託管和維護市集

> 發佈一個外掛程式市集，讓使用者可以透過 /plugin marketplace add 新增它、安裝其外掛程式，並在您推送變更後持續接收更新。

託管市集意味著將您的 `marketplace.json` 目錄放在其他人可以使用 `/plugin marketplace add` 新增它的位置，安裝其外掛程式，並在您推送後持續接收您的變更。

本頁面適用於操作市集的人員。

> [!NOTE]
>
> 這些情況涵蓋在其他頁面上：
>
> * **您還沒有編寫目錄檔案**：從 [建立市集](https://code.claude.com/docs/zh-TW/plugins/create-marketplace.md) 開始
> * **您是管理員，需要在組織的機器上要求、限制或預先安裝市集**：閱讀 [為您的組織管理外掛程式](https://code.claude.com/docs/zh-TW/plugins/org.md)

從 [託管您的市集](#host-your-marketplace) 開始以選擇主機和您的使用者執行的命令。在您的第一次發佈之前，閱讀 [讓使用者保持最新狀態](#keep-users-up-to-date)。在您變更外掛程式的 `name` 之前，閱讀 [重新命名或移除外掛程式](#rename-or-remove-a-plugin)。

## Host your marketplace

您可以在 GitHub、另一個 git 主機、託管的 `marketplace.json` URL 或共享檔案系統上的目錄中託管 marketplace。將您主機的新增命令和使用者機器上需要的內容發送給您的使用者：

| 主機 | 使用者在 Claude Code 工作階段中執行 | 使用者需要什麼 |
| :- | :- | :- |
| GitHub | `/plugin marketplace add your-org/your-marketplace` | `git`，以及對於私有儲存庫，[Grant access to a private marketplace](#grant-access-to-a-private-marketplace) 下描述的存取權 |
| GitLab、Bitbucket、GitHub Enterprise Server 或另一個 git 主機 | `/plugin marketplace add https://gitlab.example.com/team/plugins.git` | `git` 和從其機器存取主機的權限。發送完整 URL，因為 `owner/repo` 簡寫總是指 github.com |
| 託管的 `marketplace.json` URL | `/plugin marketplace add https://plugins.example.com/marketplace.json` | 對 URL 的 HTTPS 存取。使用者不需要 `git` 來存取目錄本身 |
| 共享檔案系統上的目錄 | `/plugin marketplace add /Volumes/shared/claude-plugins` | 對路徑的讀取存取 |

若要固定 GitHub 或 git-URL marketplace 的分支或標籤，告訴使用者附加 `#<ref>`，如 `your-org/your-marketplace#stable`。[plugin commands reference](https://code.claude.com/docs/zh-TW/plugins/cli-reference.md#plugin-marketplace-add) 列出命令接受的每種形式。

成功新增會列印 `Successfully added marketplace: your-marketplace`。Claude Code 從您 `marketplace.json` 中的 `name` 欄位取得該名稱，而不是從儲存庫名稱。

使用者隨後透過其項目的 `name` 和 marketplace 的 `name` 安裝 plugin，如 `/plugin install code-formatter@your-marketplace`。

### Register the marketplace for everyone in a repository

若要與在一個儲存庫中工作的每個人共享 marketplace，請從您的 shell 在那裡執行一次 `claude plugin marketplace add your-org/your-marketplace --scope project`，並提交它寫入的 `.claude/settings.json`。Claude Code 隨後為每個 [trusts the folder](https://code.claude.com/docs/zh-TW/plugins/org.md#require-plugins-per-repository) 的隊友註冊 marketplace。

### Avoid relative-path entries in a URL-hosted marketplace

當使用者將您的 marketplace 新增為裸 `marketplace.json` URL 時，Claude Code 只下載該檔案。您 `plugins` 陣列中其 `source` 是相對路徑（如 `./plugins/formatter`）的項目隨後在安裝時失敗，並顯示 [`its marketplace entry path does not stay inside the marketplace directory`](https://code.claude.com/docs/zh-TW/plugins/troubleshooting#plugins-with-relative-paths-fail-in-url-based-marketplaces)。為每個項目提供可以自行取得的 source，如 `github` 儲存庫或 `archive` URL，或在 git 儲存庫中託管 marketplace，以便 Claude Code 複製整個樹。

### 保持在託管檔案的下載限制內

當使用者將您的 marketplace 新增為 `marketplace.json` URL，或安裝具有 [`archive`](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference#archive-plugin-source) source 的項目時，Claude Code 從您的伺服器下載檔案。下載超過此表中的限制時會失敗，因此請調整您的檔案大小並設定您的伺服器以保持在限制內。

| 檔案 | 最大下載 | 您的伺服器回應的時間 | 重新導向 |
| :- | :- | :- | :- |
| 來自 `url` marketplace source 的 `marketplace.json` | 5 MiB | 10 秒 | 重新導向到不同來源必須使用 `https://` 且不能指向迴圈、連結本地或雲端中繼資料主機，因此從 `https://` 到 `http://` 的重新導向會失敗 |
| 來自 `archive` plugin source 的 Zip | 256 MiB | 120 秒 | 最多五個。每個重新導向目標必須使用 `https://` 且不能指向迴圈、連結本地或雲端中繼資料主機 |

重新導向傳送到不同來源的請求不會攜帶您在 marketplace source 或 plugin 項目上設定的任何標頭。

檔案下載後，當 zip 超過任何這些提取限制時，安裝會失敗：

* **項目**：100,000 個檔案和目錄
* **檔案大小**：任何一個檔案未壓縮時 512 MiB
* **總大小**：未壓縮時 1 GiB
* **壓縮比**：未壓縮內容是 zip 大小的 50 倍

### Edit plugins in place on a shared directory

當使用者從共享目錄新增您的 marketplace 時，Claude Code 直接從該目錄讀取具有相對路徑 sources 的 plugins，而不是複製它們。使用者在下次啟動工作階段或執行 `/reload-plugins` 時看到您的編輯，無需更新步驟或版本提升。

### Keep plugin files out of Git LFS

將您的 plugins 需要的檔案保留在 [Git LFS](https://git-lfs.com) 之外。當使用者從 git 儲存庫中託管的 marketplace 新增 marketplace 或安裝其列出的基於 git 的 plugin 時，Claude Code 將該 marketplace 或 plugin 儲存庫複製到其機器上。複製永遠不會下載 LFS 內容，因此 LFS 追蹤的檔案會作為指標檔案到達。

### Share files within a marketplace with symlinks

若要在您的 plugin 和同一 marketplace 的其他部分之間共享檔案，請在您的 plugin 目錄內建立符號連結。當 Claude Code 將 plugin 複製到其快取時，它透過目標解析的位置處理每個符號連結：

* **在 plugin 自己的目錄內**：符號連結在快取中保留為相對符號連結，因此它在執行時繼續解析到複製的目標。
* **在同一 marketplace 內的其他地方**：符號連結被取消引用。目標的內容被複製到快取中以取代它。這讓 meta-plugin 的 `skills/` 目錄可以連結到 marketplace 中其他 plugins 定義的 skills。
* **在 marketplace 外**：符號連結因安全原因被跳過。

對於從本地路徑安裝的 plugins，或從 [`command` source](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference#command-plugin-source)（其 `mode` 是預設 `copy`）安裝的 plugins，Claude Code 只保留在 plugin 自己目錄內解析的符號連結，並跳過所有其他。

以下命令建立從 marketplace plugin 內部到由同級 plugin 定義的共享 skill 的連結。在 Windows 上，從提升的命令提示字元使用 `mklink /D` 或啟用開發人員模式：

```bash theme={null}
ln -s ../../shared-plugin/skills/foo ./skills/foo
```

## Distribute through organization settings

在 Team 或 Enterprise 方案上，您也可以透過 claude.ai 上的 [**Organization settings > Plugins & skills**](https://claude.ai/admin-settings/skills?tab=inventory) 分發 marketplace，而不是在使用者新增它的地方託管它。Organization sync 透過您組織在 claude.ai 上的 GitHub 或 GitLab 連線讀取儲存庫，因此您使用者的 git 認證不涉及。

Organization sync 對儲存庫的要求比 `/plugin marketplace add` 更嚴格：

* **Marketplace 儲存庫**：在 github.com 和 gitlab.com 上，它必須是私有或內部的
* **Plugin sources**：organization sync 只接受某些 [source types](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#plugin-sources)
* **頂級 `bin/` 目錄**：claude.ai 拒絕具有一個的 plugin 並同步 marketplace 的其餘部分。錯誤訊息以 `Plugin contains a top-level bin/ directory` 開頭。將可執行檔保留在另一個目錄中，如 `scripts/`，並從您的 hooks 或 MCP 伺服器設定中將它們參考為 `${CLAUDE_PLUGIN_ROOT}/scripts/<name>`

[Sync your organization's plugins from a repository](https://claude.com/docs/plugins/org-sync) 在 claude.com 上列出接受的 sources、GitLab 設定和 `bin/` 錯誤，而 [Manage plugins for your organization](https://claude.com/docs/plugins/admin) 涵蓋管理員工作流程。

## Grant access to a private marketplace

當使用者新增、從或更新您的 marketplace 時，Claude Code 在其機器上執行 `git`，並關閉互動式提示，並依賴該機器已經持有的任何認證。Claude Code 沒有自己的 git token，`marketplace.json` 也沒有欄位用於它。

您透過發送給使用者的新增命令的形式選擇複製是透過 SSH 還是 HTTPS 執行：

* **GitHub `owner/repo`**：Claude Code 探測 `ssh -T git@github.com`，當探測成功時透過 SSH 複製。如果探測失敗，或 SSH 複製本身失敗，它透過 HTTPS 複製。沒有 GitHub SSH 金鑰的機器上的使用者可以設定 `CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1` 以跳過探測並透過 HTTPS 複製。
* **`git@host:path.git`**：SSH。
* **`https://example.com/repo.git`**：HTTPS。

告訴使用者每個協定在其機器上需要什麼：

* **SSH**：金鑰必須在沒有密碼提示的情況下工作，例如因為它已載入 `ssh-agent`。主機必須已在 `known_hosts` 中。
* **HTTPS**：Claude Code 會保留使用者的 git 憑證輔助程式，但禁止其提示，且不會執行 askpass 程式，例如透過 `GIT_ASKPASS` 設定的程式。輔助程式已儲存的憑證可以使用；需要向使用者詢問的憑證則會失敗。在 GitHub 上，執行 `gh auth login` 後再執行 `gh auth setup-git` 即可儲存憑證。

對於 GitHub Enterprise Server 主機，使用者需要從其機器存取該主機的 git 存取。請參閱 [Plugin marketplaces on GHES](https://code.claude.com/docs/zh-TW/github-enterprise-server.md#plugin-marketplaces-on-ghes) 以了解每個 Claude Code 表面需要什麼來到達 GHES 託管的 marketplace。

如果您改為透過 claude.ai 上的 **Organization settings > Plugins & skills** 分發，您使用者的 git 認證不涉及。請參閱 [透過組織設定分發](#distribute-through-organization-settings)。

### Serve users who have no git-host account

沒有 git-host 帳戶的使用者可以將您提供的 marketplace 新增為 `marketplace.json` URL 或從共享目錄，但他們只能安裝其項目 sources 他們也可以到達的 plugins。指向私有 `github` 儲存庫的項目在安裝時仍然對他們失敗，因為 Claude Code 使用與 git 託管 marketplace 相同的非互動式 `git` 取得它。

這些項目 sources 不需要 git 帳戶：

* **`archive`**：透過 HTTPS 下載的 zip。使用者既不需要 `git` 也不需要帳戶，只需要對 URL 的網路存取。需要 Claude Code v2.1.224 或更新版本。使用 `sha256` 固定每個存檔，以便 Claude Code 拒絕變更的下載。若要使用下載傳送認證，請參閱 [Authenticate archive downloads](#authenticate-archive-downloads)。
* **公開 git 儲存庫**：當項目提供 `https://` URL 時，Claude Code 會透過 HTTPS 複製公開的 `url` 或 `git-subdir` 來源，無需憑證。對於 `github` 來源，或寫成 `owner/repo` 的 `git-subdir` 來源，請告知沒有 GitHub SSH 金鑰的使用者設定 `CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1`。

即使在沒有 SSH 金鑰的機器上，不設定 `CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1` 也能從 shell 成功執行 `claude plugin install`，仍請在您的說明中保留這項設定。對於 `github` 來源，該命令可能會自行退回使用 HTTPS，並印出 `SSH not configured, cloning via HTTPS`。從工作階段內的 `/plugin` 進行的安裝以及外掛更新不會退回，因此若未設定此變數，沒有 GitHub SSH 金鑰的使用者將會失敗。

對於一個網路上的團隊，共享檔案系統上的 `directory` marketplace 也可以在沒有 git 帳戶的情況下工作。使用者只需要對路徑的讀取存取。

### What background auto-update does with credentials

背景自動更新是 Claude Code 在工作階段啟動後對 marketplaces 和已安裝 plugins 的無人值守重新整理。對於您的 marketplace，它預設關閉，直到使用者或管理員開啟它，如 [Keep users up to date](#keep-users-up-to-date) 下所涵蓋。

當它對私有 marketplace 開啟時，新提交的背景檢查使用使用者配置的 git 認證助手，永遠不會提示。每種遠端和助手給出不同的結果：

* **SSH remotes**：載入 `ssh-agent` 中的金鑰驗證檢查。
* **具有儲存認證的 HTTPS remotes**：可以在沒有提示的情況下提供儲存認證的助手驗證檢查。Git Credential Manager、macOS Keychain 助手和 `git-credential-store` 一旦持有主機的認證就以這種方式工作。
* **具有需要提示的助手的 HTTPS remotes**：助手無法在背景中回答。更新失敗無聲，現有簽出保留在原位，因此使用者的 plugins 從最後同步狀態繼續工作。

檢查後，Claude Code 執行以下其中一項：

* **簽出是最新的**：Claude Code 按原樣保留它。
* **檢查找到新提交，或因為無法到達或驗證遠端而失敗**：Claude Code 再次複製 marketplace 並用新複製替換現有簽出。如果該複製失敗，現有簽出保留在原位。重新複製可以 [time out on large repositories](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#git-clone-timed-out-after-120s)。

若要保持私有 marketplace 最新，使用者可以執行以下任一操作：

* **儲存認證**：首先登入認證助手，以便它持有主機的認證。對於 GitHub，執行 `gh auth login`，然後 `gh auth setup-git`。
* **在失敗時保持簽出**：如果使用者設定 `CLAUDE_CODE_PLUGIN_KEEP_MARKETPLACE_ON_FAILURE=1`，當背景檢查無法到達或驗證遠端時，Claude Code 保持現有簽出而不嘗試重新複製。Plugins 從最後同步狀態繼續工作。

如果使用者在環境中設定 `GITHUB_TOKEN` 或另一個提供者 token，單獨這不會驗證背景檢查。Token 透過認證助手（如 `gh` CLI 的助手，讀取 `GH_TOKEN` 和 `GITHUB_TOKEN`）生效。

## Roll out to a whole company

將 plugin 推出到整個公司涉及您作為 marketplace 所有者、控制受管設定的管理員以及使用 Claude Code 的每個人。您可以在沒有管理員的情況下執行推出，在這種情況下每個人自己新增 marketplace 並安裝 plugin。

| 誰 | 他們做什麼 | 它在哪裡涵蓋 |
| :- | :- | :- |
| 您，marketplace 所有者 | 將目錄保留在只有公司可以讀取的儲存庫中，發送您主機的新增命令，並說明每個人在其機器上需要什麼 | [Host your marketplace](#host-your-marketplace) 和 [Grant access to a private marketplace](#grant-access-to-a-private-marketplace) |
| 管理員 | 使用受管設定中的 `extraKnownMarketplaces` 和 `enabledPlugins` 為每個人註冊 marketplace 並開啟其 plugins，並在那裡設定 `autoUpdate` | [Require a marketplace and its plugins](https://code.claude.com/docs/zh-TW/plugins/org.md#require-a-marketplace-and-its-plugins) 和 [Set update policy](https://code.claude.com/docs/zh-TW/plugins/org.md#set-update-policy) |
| 每個人 | 需要對私有 git 儲存庫的讀取存取，其認證已儲存在其機器上。沒有管理員，他們也執行新增和安裝命令 | [Add a private marketplace](https://code.claude.com/docs/zh-TW/plugins/install.md#add-a-private-marketplace) |

對於沒有 git-host 帳戶的人，這些部分各涵蓋一種到達他們的方式：

* **不需要 git 帳戶的項目 sources**：[Serve users who have no git-host account](#serve-users-who-have-no-git-host-account)
* **預先填充的 plugins 目錄**：[Seed containers and CI](https://code.claude.com/docs/zh-TW/plugins/org.md#seed-containers-and-ci)，也為沒有 git-host 帳戶的使用者服務
* **claude.ai organization settings**：[Distribute through organization settings](#distribute-through-organization-settings)，其中您使用者的 git 認證不涉及

## Keep users up to date

您的變更透過背景自動更新到達使用者，一旦它對您的 marketplace 開啟，或當使用者自己更新 plugin 時。在兩種情況下，使用者只有在其計算版本變更時才獲得 plugin 的新副本，如 [Release a new version](#release-a-new-version) 下所述。

### Turn on auto-update

背景自動更新預設對您的 marketplace 關閉，`marketplace.json` 沒有欄位來開啟它。使用者或管理員開啟它：

* **告訴使用者開啟它**：每個使用者進入 `/plugin` 中的 **Marketplaces**，選擇您的 marketplace，並選擇 **Enable auto-update**。
* **要求管理員設定它**：如果管理員在受管設定中的您 marketplace 的 `extraKnownMarketplaces` 項目上設定 `"autoUpdate": true`，它對接收這些設定的每個人都開啟。請參閱 [Set update policy](https://code.claude.com/docs/zh-TW/plugins/org.md#set-update-policy)。

沒有自動更新，使用者在工作階段中執行 `/plugin marketplace update <name>` 或在 shell 中執行 `claude plugin update <plugin>@<name>` 時接收您的變更。

有關使用者在更新到達時看到的內容，請參閱 [When auto-update runs](https://code.claude.com/docs/zh-TW/plugins/loading.md#when-auto-update-runs)。

### Release a new version

若要向使用者發佈新版本，變更 plugin 的 `version`。使用者只有在 plugin 的計算版本與他們擁有的版本不同時才獲得新副本。該版本首先來自 `plugin.json`，然後來自 marketplace 項目，根據 [Versions and updates](https://code.claude.com/docs/zh-TW/plugins/loading.md#versions-and-updates)。

使用者從透過本機路徑新增的市集[就地載入](https://code.claude.com/docs/zh-TW/plugins/loading.md#find-plugins-on-disk)的外掛不受 `version` 控制。它在每個工作階段啟動時載入您的目前檔案，無論其版本字串說什麼。

對於除了就地載入或來自 `command` source 的安裝之外的每次安裝，要麼在每次發佈時增加 `version`，要麼省略它：

* **在每次發佈時提升 `version`**：使用者保留在其快取副本上，直到字串變更。如果您設定 `"version": "1.0.0"` 並推送新提交而不變更它，使用者不會接收它們。
* **省略 `version`**：使用者改為追蹤您的提交。將 `version` 保留在 `plugin.json` 和 marketplace 項目之外。

不要在 `plugin.json` 和 marketplace 項目中都設定 `version`。如果您這樣做，Claude Code 使用 `plugin.json` 值而不警告，`claude plugin validate` 報告不匹配為 `Entry declares version "<a>" but <path>/plugin.json says "<b>"`。

### Hold users on one version

一個 marketplace 一次為每個 plugin 提供一個版本，因此您透過選擇每個項目指向的內容來保持使用者在一個版本上：

* **plugin 項目上的 `ref` 和 `sha`**：`ref` 命名分支或標籤，`sha` 命名 `github`、`url` 或 `git-subdir` source 的提交。請參閱 [Plugin sources](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#plugin-sources)。
* **新增命令上的 `#<ref>`**：新增 `your-org/your-marketplace#stable` 的使用者獲得該目錄的分支或標籤。對於一次兩個發佈線，請參閱 [Run release channels](#run-release-channels)。
* **`<plugin>--v<version>` 標籤**：依賴的版本範圍針對這些標籤解析。請參閱 [Release a plugin that others depend on](https://code.claude.com/docs/zh-TW/plugins/dependencies.md#tag-plugin-releases-for-version-resolution)。

[Release a new version](#release-a-new-version) 說明變更的項目何時到達使用者。

### Change the command of a command source

如果您變更 [`command` source](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference#command-plugin-source) 的 `command`，或切換其 `mode`，每個使用者必須在 Claude Code 執行它之前接受新命令。Claude Code 只執行使用者在安裝或最後更新 plugin 時接受的確切命令。

在使用者的 marketplace 副本取得變更後，該使用者看到以下內容：

* **沒有更多背景執行**：該使用者的命令的 [once-per-session run](https://code.claude.com/docs/zh-TW/plugins/loading.md#when-a-command-source-re-runs) 停止，因此工具的新輸出不會到達他們。
* **`/plugin` Errors 標籤中的項目**：項目顯示新命令和要執行的 `claude plugin update` 命令。

告訴使用者執行該項目顯示的 `claude plugin update` 命令，在終端中。Claude Code 向他們顯示新命令並要求他們接受它。

## Run release channels

若要提供穩定和早期存取軌道，託管兩個 marketplaces，其項目指向同一 plugin 的不同 refs，並讓每個使用者新增他們想要的。Claude Code 沒有發佈頻道概念，一個 marketplace 一次為每個 plugin 提供一個版本。

給兩個 `marketplace.json` 檔案不同的 `name` 值。Claude Code 透過其 `name` 識別 marketplace，因此使用者一次不能有兩個具有相同名稱的 marketplaces 已註冊。

使用這兩個目錄，新增 `stable-tools` 的使用者從 `stable` 分支安裝 `code-formatter`，新增 `latest-tools` 的使用者從 `latest` 安裝它：

```json theme={null}
{
  "name": "stable-tools",
  "owner": { "name": "Your Org" },
  "plugins": [
    { "name": "code-formatter", "source": { "source": "github", "repo": "your-org/code-formatter", "ref": "stable" } }
  ]
}
```

```json theme={null}
{
  "name": "latest-tools",
  "owner": { "name": "Your Org" },
  "plugins": [
    { "name": "code-formatter", "source": { "source": "github", "repo": "your-org/code-formatter", "ref": "latest" } }
  ]
}
```

給兩個 refs 不同的 `plugin.json` 版本，或省略 `version` 以便提交 SHA 區分它們。更新透過比較版本檢測，因此在沒有版本變更的情況下移動的 ref 使使用者保留在快取副本上。

若要將頻道指派給使用者群組而不是讓使用者選擇，管理員給每個群組匹配的 `extraKnownMarketplaces` 項目，如 [Set update policy](https://code.claude.com/docs/zh-TW/plugins/org.md#set-update-policy) 下所述。

## Rename or remove a plugin

Plugin 的 `name` 是其識別碼。使用者在 `enabledPlugins` 和 `pluginConfigs` 設定鍵以及 `/plugin install` 中參考它，因此變更它會破壞每次現有安裝。

若要變更使用者在 `/plugin` 中看到的標籤而不破壞任何東西，在 `plugin.json` 中設定 `displayName` 並保持 `name` 不變。

### Migrate users with a renames map

當您必須變更 `name` 時，將頂級 `renames` 對應新增到 `marketplace.json`，以便 Claude Code 遷移現有使用者，而不是報告 [`Plugin "<name>" not found in marketplace`](https://code.claude.com/docs/zh-TW/plugins/troubleshooting#plugin-not-found-in-marketplace)。當您從 `plugins` 移除項目時也執行相同操作。

將每個前名稱對應到其目前名稱，或在 plugin 消失時對應到 `null`。此 marketplace 將 `formatter` 重新命名為 `code-formatter` 並記錄 `legacy-linter` 已移除：

```json theme={null}
{
  "name": "your-marketplace",
  "owner": { "name": "Your Org" },
  "plugins": [
    { "name": "code-formatter", "source": "./plugins/code-formatter" }
  ],
  "renames": {
    "formatter": "code-formatter",
    "legacy-linter": null
  }
}
```

在您推送後，仍然啟用舊名稱的使用者看到以下結果之一：

* **重新命名的項目**：plugin 在其新名稱下載入。`claude plugin list` 和 `/plugin` 下 plugin 的詳細資訊一次顯示 `Renamed to "code-formatter" in the "your-marketplace" marketplace`，Claude Code 在使用者、專案和本地設定範圍中將舊鍵重寫為新鍵在 `enabledPlugins` 和 `pluginConfigs` 中。
* **`null` 項目**：舊鍵從這些範圍中刪除，使用者看到 `Removed from the "your-marketplace" marketplace`。
* **在受管設定中啟用**：plugin 仍然在其新名稱下載入，但 Claude Code 無法重寫受管設定，因此通知重複出現，直到管理員在那裡更新 `enabledPlugins`。

對於使用者從 git 儲存庫或 URL 新增的 marketplace，重新命名的 plugin 報告 [`Plugin "<name>" not cached at <path>`](https://code.claude.com/docs/zh-TW/plugins/troubleshooting#plugin-not-cached-at)，直到使用者在工作階段中執行 `/plugin install code-formatter@your-marketplace` 一次。

將 `renames` 視為僅附加歷史記錄。在每個人遷移後保持舊項目。當您再次重新命名時，添加第二個項目而不是編輯第一個，因為 Claude Code 遵循從最舊名稱的鏈。

在您的 shell 中，編輯對應後執行 `claude plugin validate .`。它拒絕循環或在 `null` 或 `plugins` 中的名稱以外的任何地方結束的鏈，並顯示 `renames.<name>: chain does not resolve`。

### Uninstall removed plugins from users' machines

若要從使用者的機器卸載已移除的 plugin 而不是留下副本，在 `marketplace.json` 的頂級設定 `"forceRemoveDeletedPlugins": true`。沒有欄位，已移除的 plugin 保留已安裝，並在工作階段載入它時報告 `Plugin "<name>" not found in marketplace`。使用它，Claude Code 在每個工作階段啟動時執行以下操作：

1. 比較使用者從您的 marketplace 安裝的內容與項目和 `renames` 對應，並將既未列出也未重新命名的任何 plugin 視為已移除。
2. 從使用者、專案和本地範圍卸載每個已移除的 plugin。只有受管設定安裝的 Plugins 保留在原位。
3. 在 `/plugin` 中的 **Flagged** 標題下列出每個已移除的 plugin，狀態為 `Removed from marketplace`。

## Authenticate archive downloads

若要驗證 [`archive`](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference#archive-plugin-source) 下載（如從私有登錄的下載），設定 Claude Code 使用它發送的 HTTP 標頭。您可以在以下任一位置設定 `headers`：

* **Marketplace 的 `url` source**：您註冊 marketplace 的 `url` source，如 [`extraKnownMarketplaces`](https://code.claude.com/docs/zh-TW/settings-reference#extraknownmarketplaces) 項目。
* **Plugin 的項目**：在 Claude Code v2.1.238 或更新版本上，您可以改為在 plugin 的 `marketplace.json` 項目上設定它，在 `source` 旁邊。

在任一位置，當值是短期的（如您的登錄按需生成的 token）時，設定 `headersHelper` 命令而不是 `headers`。Claude Code 執行命令並將其列印的 JSON 物件作為該位置的標頭發送。需要 Claude Code v2.1.238 或更新版本。

[marketplace reference](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#plugin-entries) 列出 `headers` 和 `headersHelper` 項目欄位。

您選擇的位置決定哪些下載獲得標頭以及 Claude Code 何時執行命令：

| 位置 | 獲得標頭的下載 | Claude Code 何時執行在那裡設定的 `headersHelper` |
| :- | :- | :- |
| Marketplace `url` source | 在 marketplace URL 的來源上的存檔下載，意味著相同的方案、主機和連接埠 | 在每次 marketplace 的 `marketplace.json` 的取得之前以及在該來源上的每次存檔下載之前。Claude Code 重複使用一次執行的輸出長達 60 秒 |
| Plugin 項目 | 該項目的下載只 | 只有當使用者自己安裝或更新該一個 plugin 並 [accepts the command](#how-users-accept-a-headershelper-command) 時 |

其中兩個位置都設定相同名稱的標頭，Claude Code 發送項目的值。在一個位置內，命令列印的標頭覆蓋 `headers` 中列出的相同名稱的標頭。

### Add a headersHelper to a plugin entry

此項目在 `source` 旁邊設定 `headersHelper`。它也設定 [`"strict": false`](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference#strict-mode)，Claude Code 要求設定 `headersHelper` 的 `marketplace.json` 項目：

```json theme={null}
{
  "name": "my-plugin",
  "description": "Formatting commands for internal services",
  "strict": false,
  "source": {
    "source": "archive",
    "url": "https://registry.example.com/plugins/my-plugin-2.1.0.zip"
  },
  "headersHelper": "/opt/bin/mint-registry-token.sh"
}
```

若要檢查項目，在您的 shell 中執行 `claude plugin install my-plugin@your-marketplace`。Claude Code 向您顯示命令和存檔 URL，並在您接受後下載 zip。

### Write the headersHelper command

無論您在 marketplace 的 `url` source 還是在 plugin 項目上設定 `headersHelper`，編寫命令以滿足這些要求：

* **命令文字**：最多 500 個可列印 ASCII 字元，沒有四個或更多空格的執行。
* **輸出**：在 stdout 上列印一個標頭名稱和字串值的 JSON 物件，然後在 10 秒內退出 0。
* **Shell 和工作目錄**：Claude Code 透過 `sh` 執行命令，或在 Windows 上透過 `cmd.exe`。工作目錄是設定目錄，即 `~/.claude` 或 [`CLAUDE_CONFIG_DIR`](https://code.claude.com/docs/zh-TW/env-vars#variables)。給出絕對路徑或 `PATH` 上的命令，因為相對路徑針對該目錄解析，而不是使用者的專案。
* **Claude Code 移除的變數**：當命令在 `marketplace.json` 項目中設定，或在專案的 `.claude/settings.json` 或 `.claude/settings.local.json` 中設定時，Claude Code 從環境中移除每個名稱看起來像認證的變數，透過 [same rule it applies to an MCP `headersHelper`](https://code.claude.com/docs/zh-TW/mcp#which-variables-a-helper-can-read)。`ANTHROPIC_API_KEY` 和 `MY_REGISTRY_TOKEN` 都被移除，因此讓命令從檔案或認證存儲讀取其認證。此移除不適用於在使用者設定、`--settings` 檔案或受管設定中設定的命令。
* **Claude Code 設定的變數**：`CLAUDE_CODE_MARKETPLACE_URL` 和 `CLAUDE_CODE_MARKETPLACE_NAME` 用於 `url` source 的命令，以及 `CLAUDE_CODE_PLUGIN_NAME` 和 `CLAUDE_CODE_PLUGIN_ARCHIVE_URL` 用於項目的命令。`CLAUDE_CODE_MARKETPLACE_NAME` 在使用者透過 URL 新增 marketplace 後的第一次取得時未設定，因為該取得是提供名稱的內容。

鑄造持有者 token 的命令列印像這樣的物件：

```json theme={null}
{"Authorization": "Bearer eyJhbGciOiJSUzI1NiJ9"}
```

### When Claude Code skips a headersHelper command or drops its output

`headersHelper` 命令不執行，或來自 `headers` 或命令輸出的標頭被刪除，當以下任一情況適用時：

* **命令失敗**：如果命令退出非零、執行超過 10 秒或列印除了字串值的 JSON 物件以外的任何內容，命令執行的取得或下載不會發生。
* **Marketplace URL 不以 `https://` 開頭**：該 `url` source 的命令不執行，請求只攜帶其 `headers` 欄位中列出的標頭。
* **重新導向離開來源**：當下載被重新導向離開存檔 URL 的來源時，重新導向的請求不攜帶來自 marketplace `url` source 或 plugin 項目的 `headers` 值或命令輸出。
* **項目設定路由或身份標頭**：Claude Code 從項目的 `headers` 和命令輸出中刪除請求路由和用戶端身份名稱（如 `Host`、`Cookie` 和 `X-Forwarded-*`），並保持驗證名稱（如 `Authorization`）。每個 `marketplace.json` 項目都以這種方式過濾。對於設定中的內聯 plugin 項目，請參閱 [`extraKnownMarketplaces`](https://code.claude.com/docs/zh-TW/settings-reference#extraknownmarketplaces)。
* **命令在 `--add-dir` 目錄的設定中設定**：命令被忽略，在 `url` source 和 [inline plugin entry](https://code.claude.com/docs/zh-TW/settings-reference.md#extraknownmarketplaces) 上，只有該檔案的 `headers` 被發送。
* **受管設定阻止命令**：將 [`disableCommandPluginSources`](https://code.claude.com/docs/zh-TW/settings-reference#disablecommandpluginsources) 設定為 `true` 阻止 `headersHelper` 命令，[`allowManagedHooksOnly`](https://code.claude.com/docs/zh-TW/settings-reference#allowmanagedhooksonly) 也阻止它們，除非 `disableCommandPluginSources` 明確為 `false`。在任一阻止下，Claude Code 仍然為受管設定本身聲明的 marketplace 執行命令。

### How users accept a headersHelper command

使用者在每次自己單獨安裝或更新該一個 plugin 時接受 plugin 項目的命令。Claude Code 顯示命令和存檔 URL，並只在使用者接受後執行命令。

使用者可以在終端機中的 Claude Code 工作階段內、在未執行任何工作階段的 shell 中，或在 VS Code 擴充功能中安裝或更新 plugin：

* **終端機工作階段**：從 `/plugin` 中的 plugin 自己的檢視。
* **Shell**：使用 `claude plugin install` 或 `claude plugin update`。
* **VS Code 擴充功能**：從 [**Manage plugins** 對話框](https://code.claude.com/docs/zh-TW/vs-code.md#manage-plugins)，需使用擴充功能 2.1.290 或更新版本。

在非互動式 shell 中，傳遞 [`--yes`](https://code.claude.com/docs/zh-TW/plugins/cli-reference#plugin-install) 以接受命令。若要接受只有先前 `--json` 執行顯示的命令，傳遞 [`--accept-command`](https://code.claude.com/docs/zh-TW/plugins/cli-reference#plugin-install) 與執行報告的 `sha256`。

Claude Code 只執行它顯示的命令，用於它顯示的存檔 URL。如果項目的命令或存檔 URL 在這之間變更，Claude Code 拒絕安裝或更新。僅查詢字串中的變更不計，但在 VS Code 擴充功能中或使用 `--accept-command` 時除外。

### Installs and updates that refuse a command instead of asking

在除了單一 plugin 安裝或更新之外的任何操作上，Claude Code 既不執行項目的命令也不下載其存檔。Plugin 保留在其已安裝版本或保留未安裝，使用者看到以下結果之一：

* **一次安裝多個 plugins、來自 plugin 建議或作為另一個 plugin 的依賴**：Claude Code 拒絕具有命令的 plugin 並將使用者導向該 plugin 在 `/plugin` 中的自己檢視。批量安裝中的其他 plugins 仍然安裝。依賴被拒絕 plugin 的 plugin 失敗安裝，直到使用者自己安裝被拒絕 plugin。
* **背景自動更新，或工作階段啟動用於其存檔從未下載的 plugin**：Claude Code 在 `/plugin` Errors 標籤中列出 plugin，以便使用者知道自己安裝或更新它。

### When a marketplace `url` source's command runs

您在設定檔案中聲明 marketplace `url` source 的 `headersHelper`，如 [`extraKnownMarketplaces`](https://code.claude.com/docs/zh-TW/settings-reference#extraknownmarketplaces) 項目，而不是在 marketplace 發佈的目錄中。Claude Code 因此不要求使用者在每次安裝或更新時接受它。相反，聲明它的設定檔案決定 Claude Code 何時執行它：

| 設定檔案 | Claude Code 何時執行命令 |
| :- | :- |
| 使用者設定、`--settings` 檔案或機器上的受管設定檔案 | 無需詢問，包括在背景 marketplace 重新整理期間 |
| 專案的 `.claude/settings.json` 或 `.claude/settings.local.json` | 只有在使用者接受該資料夾本身的 [workspace trust dialog](https://code.claude.com/docs/zh-TW/permissions.md#what-runs-before-you-trust-a-folder) 後。`-p` 或 SDK 工作階段不計為接受它，也不計為授予對父資料夾的信任 |
| 伺服器受管設定 | 在互動式工作階段中，只有在使用者在 [security approval dialog](https://code.claude.com/docs/zh-TW/server-managed-settings.md#security-approval-dialogs) 中批准交付的設定後 |

對於這些檔案中的 [inline plugin entry](https://code.claude.com/docs/zh-TW/settings-reference.md#extraknownmarketplaces)，Claude Code 要求與該檔案中 marketplace 級別命令相同的資料夾信任或設定批准，使用者也在每次安裝或更新時接受項目的命令。

## Depend on and recommend other plugins

項目可以聲明對其他 plugins 的依賴。

* **版本範圍**：依賴可以攜帶 semver 範圍。
* **跨 marketplace 依賴**：來自另一個 marketplace 的依賴只有在您的 marketplace 在 `allowCrossMarketplaceDependenciesOn` 中列出該 marketplace 時才安裝。

對於版本範圍、它們解析的 `<plugin>--v<version>` git-tag 約定以及跨 marketplace 信任，請參閱 [Plugin dependencies](https://code.claude.com/docs/zh-TW/plugins/dependencies.md)。

若要在專案匹配它時讓 Claude Code 建議 plugin，將 `relevance` 區塊新增到項目，其中包含識別專案的信號。使用者只有在管理員在 `pluginSuggestionMarketplaces` 中列出您的 marketplace 時才會看到這些建議。對於信號和啟用步驟，請參閱 [Plugin relevance](https://code.claude.com/docs/zh-TW/plugins/relevance.md)。

## 解決市集無法做到的事

某些擁有者要求的功能在 `marketplace.json` 中沒有對應的欄位。以下是每項功能最接近的選項：

* **限制使用者安裝其他項目**：市集允許清單是受管理的設定，`strictKnownMarketplaces`。請參閱[限制使用者可以安裝的項目](https://code.claude.com/docs/zh-TW/plugins/org.md#restrict-what-users-can-install)。
* **在使用者未要求的情況下安裝或啟用外掛程式**：沒有入口欄位可以安裝外掛程式。受管理的 `enabledPlugins` 可以為整個機隊執行此操作；請參閱[預先安裝並要求外掛程式](https://code.claude.com/docs/zh-TW/plugins/org.md#pre-install-and-require-plugins)。
* **向不同的使用者顯示不同的項目**：項目沒有對象欄位，每個新增市集的使用者都會看到整個目錄。為不同的對象託管不同的市集。
* **將外掛程式標記為已棄用**：沒有棄用狀態。選項是移除項目，在 `renames` 中將其名稱對應到 `null`，並選擇性地設定 `forceRemoveDeletedPlugins`。
* **為使用者開啟自動更新**：每個使用者在 `/plugin` 中的**市集**下開啟它，或管理員在受管理的設定中設定 `autoUpdate`。請參閱[開啟自動更新](#turn-on-auto-update)。
* **攜帶 git 認證**：沒有市集欄位可以保存 git 權杖。對 git 託管的市集或外掛程式的存取遵循使用者的 git 設定，詳見[授予對私人市集的存取權](#grant-access-to-a-private-marketplace)。對於 `archive` 來源，項目可以改為設定 [`headers` 或 `headersHelper`](#authenticate-archive-downloads)。

## Next steps

* [Marketplace reference](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md)：`marketplace.json` 欄位、source 類型和驗證訊息
* [Manage plugins for your organization](https://code.claude.com/docs/zh-TW/plugins/org.md)：在整個組織的機器上要求、限制或播種您的 marketplace
* [Plugin dependencies](https://code.claude.com/docs/zh-TW/plugins/dependencies.md)：標籤發佈，以便依賴您的 plugins 的 plugins 可以解析版本
* [Troubleshoot plugins](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md)：您的使用者在新增或從您的 marketplace 更新時看到的錯誤

<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/plugins/troubleshooting | lastmod: 2026-10-25 | section: Plugins / Troubleshooting -->
> 來源：https://code.claude.com/docs/zh-TW/plugins/troubleshooting（官方 zh-TW，lastmod 2026-10-25）｜分類：Plugins › Troubleshooting｜EN 摘要：Fix plugin errors in Claude Code. Find the exact message you saw, grouped by stage from where /plugin runs through install and org policy.

# 排除外掛程式故障

> 修復 Claude Code 中的外掛程式錯誤。找到您看到的確切訊息，按照 /plugin 執行、安裝和組織政策的階段分組。

此頁面列出 Claude Code 外掛程式和市集的錯誤訊息和症狀，市集是 Claude Code 安裝外掛程式的目錄。每個項目都提供原因、一個修復方法，以及修復後您會看到的內容。

如果訊息命名了外掛程式或市集，該項目會顯示一個佔位符，例如 `<name>`。

無論您是安裝外掛程式、建置外掛程式、託管市集，還是為組織管理外掛程式，都可以使用此頁面。

> [!NOTE]
>
> 這些情況涵蓋在其他頁面上：
>
> * **為什麼範圍、快取和優先順序的行為方式如此**：閱讀 [外掛程式載入參考](https://code.claude.com/docs/zh-TW/plugins/loading.md)
> * **查找旗標、欄位或命令**：使用 [外掛程式命令參考](https://code.claude.com/docs/zh-TW/plugins/cli-reference.md)、[清單參考](https://code.claude.com/docs/zh-TW/plugins/manifest-reference.md) 或 [市集參考](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md)
> * **出現 `hooks module not loaded` 或 `hooks module did not load` 訊息**：該外掛程式是一個 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md)，因此請閱讀 [mod 無法載入](https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot.md#the-mod-doesn’t-load)

搜尋您看到的確切訊息。每個訊息都列在產生它的階段下，這不一定是您執行的命令。例如，安裝可能因為市集遺失而失敗，所以該訊息在 [新增市集](#add-a-marketplace) 下。

## 找到 `/plugin` 執行的位置

`/plugin` 是您在執行中的 Claude Code 終端機工作階段內輸入的命令，它會開啟互動式面板。本節中的條目涵蓋您可以輸入它但它無法執行的位置，以及不存在的命令拼寫。

### `/plugin isn't available in this environment`

您在 Claude Code 終端機工作階段以外的地方輸入了 `/plugin`，Claude 回覆了這一行，而不是開啟任何東西。

您會在沒有終端機來繪製 `/plugin` 面板的工作階段中收到此回覆：[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)，使用 `claude -p`、Agent SDK、Claude 桌面應用程式的 Code 標籤、VS Code 擴充功能面板，以及 claude.ai/code 上的瀏覽器。

在 VS Code 擴充功能面板中，只有 `/plugin` 行後面跟著某些內容（例如 `/plugin install <plugin>@<marketplace>`）會收到此回覆。單獨輸入 `/plugin` 或 `/plugins` 會開啟 **管理外掛程式** 對話框。

改為從您所在的表面安裝外掛程式：

* **Claude 桌面應用程式、本機或 SSH 工作階段**：使用 [安裝外掛程式](https://code.claude.com/docs/zh-TW/plugins/install.md#install-a-plugin) 下的 **桌面應用程式** 標籤
* **VS Code 擴充功能**：使用 [安裝外掛程式](https://code.claude.com/docs/zh-TW/plugins/install.md#install-a-plugin) 下的 **VS Code** 標籤
* **網路上的 Claude Code，或桌面雲端工作階段**：雲端工作階段沒有外掛程式瀏覽器。請參閱 [安裝外掛程式](https://code.claude.com/docs/zh-TW/plugins/install.md#install-a-plugin) 下的 **雲端工作階段** 標籤，了解雲端工作階段載入的內容
* **您有權存取的終端機**：執行 `claude` 並在那裡輸入 `/plugin`，或在您的 shell 中執行 `claude plugin install <plugin>@<marketplace>`，而不啟動工作階段

當終端機安裝成功時，`/plugin` 會列印以 `✓ Installed <plugin>.` 開頭的安裝摘要，而 `claude plugin install` 會列印 `Successfully installed plugin: <plugin>@<marketplace>`。

### `zsh: no such file or directory: /plugin`

您在 shell 提示符處輸入了 `/plugin ...`，shell 報告不存在名為 `/plugin` 的檔案。Bash 報告 `bash: /plugin: No such file or directory`。

`/plugin` 是您在 Claude Code 工作階段內輸入的命令，而不是在 shell 提示符處。啟動工作階段並在那裡輸入相同的命令：

```shell theme={null}
claude
```

然後，在 Claude Code 提示符處：

```text theme={null}
/plugin install <plugin>@<marketplace>
```

成功的安裝會列印以 `✓ Installed <plugin>.` 開頭的摘要。如果安裝本身隨後失敗，其訊息在 [新增市集](#add-a-marketplace) 或 [安裝外掛程式](#install-a-plugin) 下。

若要從 shell 安裝而不啟動工作階段，請改為執行 `claude plugin install <plugin>@<marketplace>`。

### `The term '/plugin' is not recognized as the name of a cmdlet`

您在 PowerShell 提示符處輸入了 `/plugin ...`，而 `/plugin` 是 Claude Code 命令，不是程式。Bash 和 Zsh 報告 [它們自己的這個錯誤形式](#zsh-no-such-file-or-directory-plugin)。

改為使用以下任一方式：

* 執行 `claude`，然後在 Claude Code 提示符處輸入 `/plugin`
* 在 PowerShell 中執行 `claude plugin install <plugin>@<marketplace>`，而不啟動工作階段

### `claude: command not found` after `claude plugin ...`

您在 shell 中執行了 `claude plugin install ...`，shell 根本找不到 `claude`。在 Windows 上，訊息是 `'claude' is not recognized as the name of a cmdlet` 或 `'claude' is not recognized as an internal or external command`。

原因不是外掛程式命令。請遵循 [驗證您的 PATH](https://code.claude.com/docs/zh-TW/troubleshoot-install.md#verify-your-path)，然後重試外掛程式命令。

### `Unknown command` and command spellings that don't exist

您輸入了您在某處看到的外掛程式命令，並在工作階段中收到 `Unknown command: /<name>`，或從 shell 中的 `claude` 二進位檔案收到 `error: unknown command '<name>'` 或 `error: unknown option '<flag>'`。

有幾個命令拼寫在使用中，Claude Code 沒有。下表將每個對應到真實命令。[外掛程式命令參考](https://code.claude.com/docs/zh-TW/plugins/cli-reference.md) 列出子命令及其旗標。

| 您輸入 | Claude Code 說什麼 | 改為使用 |
| :- | :- | :- |
| `claude plugin add <source>` | `error: unknown command 'add'` | `claude plugin marketplace add <source>` 以新增市集，或 `claude plugin install <plugin>@<marketplace>` 以安裝外掛程式 |
| `claude plugin install <plugin> --project` | `error: unknown option '--project'` | `claude plugin install <plugin>@<marketplace> --scope project` |
| `/install <plugin>` | `Unknown command: /install` | `/plugin install <plugin>@<marketplace>` |
| `/plugin add <source>` | `/plugin` 面板在 **Discover** 標籤上開啟 | `/plugin marketplace add <source>` |
| `marketplace.anthropic.com` 作為來源 | `Invalid marketplace source format. Try: owner/repo, https://..., or ./path` | `anthropics/claude-plugins-official` 用於官方市集 |

這些拼寫看起來不對但有效：

* `claude plugins` 是 `claude plugin` 的別名
* `claude plugin remove` 是 `claude plugin uninstall` 的別名
* `/plugins` 和 `/marketplace` 在工作階段中開啟與 `/plugin` 相同的面板

## 新增市集

市集是您從 git 儲存庫、URL 或本機路徑新增到 Claude Code 的目錄。這些條目涵蓋當新增失敗或稍後重新整理失敗時您收到的訊息。

### `Marketplace "claude-plugins-official" not found`

您在工作階段中執行了 `/plugin install <plugin>@claude-plugins-official`，Claude Code 報告它沒有該名稱的市集。

官方市集尚未在此機器上註冊。Claude Code 通常在您第一次啟動互動式終端機工作階段時自行註冊它。如果您只透過 VS Code 擴充功能使用 Claude Code，它還沒有執行，並且它會跳過或延遲該步驟：

* 當政策阻止來源時
* 當設定 `CLAUDE_CODE_DISABLE_OFFICIAL_MARKETPLACE_AUTOINSTALL` 時
* 在失敗的嘗試之後，等待重試

`claude plugin` shell 命令永遠不會為您註冊它。

新增它，然後重試安裝：

```text theme={null}
/plugin marketplace add anthropics/claude-plugins-official
```

Claude Code 列印 `Successfully added marketplace: claude-plugins-official`，而 `/plugin marketplace list` 顯示市集及其來源。

對於此訊息中的任何其他市集名稱，請參閱 [`Marketplace "<name>" not found`](#marketplace-not-found)。

相同的字串也出現在 `/plugin` **Errors** 標籤中，面板的載入失敗清單，當您的設定中列出的外掛程式命名您尚未新增的市集時。

### `Marketplace "<name>" not found`

您在工作階段中執行了 `/plugin install`，Claude Code 報告它沒有該名稱的市集。有兩種形式的命令會到達此訊息：

* **`/plugin install <plugin>@<name>`**：安裝行，通常來自某人傳送給您的，命名您尚未新增的市集。本條目的其餘部分涵蓋尋找和新增它。
* **`/plugin install <source>` 搭配路徑、URL 或 `owner/repo`**：此形式報告訊息而不是安裝，即使對於您已經新增的來源。若要在一個命令中從來源安裝，請參閱 [新增市集並在一個命令中安裝](https://code.claude.com/docs/zh-TW/plugins/install.md#add-a-marketplace-and-install-in-one-command)。

如果名稱以 `claudeai-` 開頭，市集託管在 claude.ai 上，您可以使用 `claude plugin marketplace add --claudeai <name>` 從 shell 按名稱新增它。請參閱 [從 claude.ai 新增市集](https://code.claude.com/docs/zh-TW/plugins/install.md#add-from-claude-ai)。

對於任何其他名稱，安裝行命名市集但不說明市集託管在何處，Claude Code 沒有索引來查詢市集名稱。詢問傳送該行的人市集的來源，這是 GitHub `owner/repo`、git URL 或路徑。然後 [新增市集](https://code.claude.com/docs/zh-TW/plugins/install.md#add-a-marketplace) 並再次執行安裝行。

某人傳送給您的市集是第三方的，所以 [在安裝前檢查外掛程式](https://code.claude.com/docs/zh-TW/plugins/security.md#review-a-plugin-before-you-install)。

如果您已經新增了市集，請根據 `/plugin marketplace list` 檢查拼寫。

### `Invalid marketplace source format`

您執行了 `/plugin marketplace add <source>`、`claude plugin marketplace add <source>` 或 `claude plugin install <plugin> --marketplace <source>`，Claude Code 回覆 `Invalid marketplace source format. Try: owner/repo, https://..., or ./path`。

Claude Code 接受以下形式之一的來源：

* GitHub `owner/repo` 速記
* `https://` 或 `http://` URL
* `user@host:path` SSH URL
* 以 `./`、`../`、`/` 或 `~` 開頭的本機路徑

裸名稱（例如 `claude-plugins-official`）不符合任何一個。裸主機名稱（例如 `marketplace.anthropic.com`）也不符合。

以接受的形式之一重新輸入來源：

```text theme={null}
/plugin marketplace add anthropics/claude-plugins-official
```

當新增成功時，Claude Code 列印 `Successfully added marketplace: <name>`。

### `'<source>' is not a valid GitHub owner/repo shorthand`

您傳遞了一個包含斜線但不是 `owner/repo` 的來源，例如 `github.com/owner/repo` 或 `gitlab.example.com/group/project` 路徑。Claude Code 拒絕了它，並提供了接受的形式清單。

`owner/repo` 速記僅限 GitHub，必須遵循 GitHub 的命名規則，因此主機名稱或額外的路徑段會失敗。以符合市集託管位置的形式傳遞來源：

* **任何主機上的儲存庫**：完整的複製 URL
* **託管的 `marketplace.json`**：其 `https://` URL
* **本機簽出**：`./path` 或絕對路徑

例如，若要透過其複製 URL 新增官方市集，請在工作階段中：

```text theme={null}
/plugin marketplace add https://github.com/anthropics/claude-plugins-official.git
```

成功的新增會列印 `Successfully added marketplace: <name>`。

### `Invalid git URL`

您新增了市集、安裝了外掛程式，或從 git 位址執行了更新，命令失敗，訊息中顯示 `Invalid git URL`。

Claude Code 在執行 git 之前檢查每個 git 位址。它拒絕其協議不支援的位址。它也拒絕 git 可能讀取為命名不同伺服器或資料夾的位址，而不是位址顯示的位址。

位址後面的文字命名要變更的內容。按照訊息所說重寫位址並再次執行命令。

改為說 `is blocked by enterprise policy` 的拒絕來自您組織的設定。請參閱 [市集來源被企業政策阻止](#marketplace-source-is-blocked-by-enterprise-policy)。

### `Path does not exist: <path>`

您傳遞了本機路徑給 `marketplace add`，該路徑處沒有任何內容。相對路徑相對於您的目前目錄解析。

檢查訊息中的已解析路徑。然後從相對路徑開始的目錄執行命令，或傳遞市集目錄的絕對路徑。成功的新增會列印 `Successfully added marketplace: <name>`。

Claude Code 接受包含 `.claude-plugin/marketplace.json` 的目錄，或指向 `.json` 檔案的路徑。指向任何其他檔案的路徑會失敗，並顯示 `File path must point to a .json file (marketplace.json)`。

### `Marketplace file not found at <path>/.claude-plugin/marketplace.json`

Claude Code 複製或下載了市集，但在其內部的預期路徑中找不到 `marketplace.json`。新增命令將其報告為 `Failed to add marketplace: Marketplace file not found at ...`。

預設位置是儲存庫根目錄中的 `.claude-plugin/marketplace.json`，[市集參考](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md) 列出接受的位置。

修復因所有者和其他人而異：

* **您擁有市集**：將檔案放在該位置並重新新增市集
* **其他人託管它**：詢問所有者確切的來源他們發佈

### `Cannot add marketplace "<name>": Claude Code cannot install plugins from a marketplace with this name`

您新增了市集，而其 `marketplace.json` 中的 [`name`](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference#top-level-fields) 無法作為 [外掛 ID](https://code.claude.com/docs/zh-TW/plugins/loading.md#find-where-a-plugin-came-from)（例如 `my-plugin@my-marketplace`）中 `@` 之後的部分。Claude Code 會拒絕此新增，且不會註冊任何內容。

訊息的其餘部分說明名稱的規則。在此範例中，`_internal` 因以 `_` 開頭而違反規則：

```text theme={null}
Cannot add marketplace "_internal": Claude Code cannot install plugins from a marketplace with this name. Each part of a plugin id (plugin@marketplace) may use only the letters a-z and A-Z, digits, ".", "_" and "-", and must start with a letter or digit. The name is set by "name" in the marketplace's marketplace.json; ask its maintainer to change it.
```

為市集取一個符合該規則的名稱，然後再次新增：

* **您擁有市集**：變更 `marketplace.json` 中的 `name`，例如改為 `internal-tools`
* **其他人託管它**：請所有者變更名稱

在 v2.1.295 之前，Claude Code 會將此範例中的新增回報為成功。

### `Cannot add marketplace "<name>": Claude Code reserves this name and cannot register a marketplace under it`

您新增了市集，而其 `marketplace.json` 中的 [`name`](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference#top-level-fields) 是每個 JavaScript 物件都具有的成員名稱之一，例如 `constructor`、`toString` 或 `valueOf`。Claude Code 保留這些名稱，因此會拒絕此新增，且不會註冊任何內容。[保留名稱](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#reserved-names) 列出了這些名稱。

在此範例中，市集名為 `constructor`：

```text theme={null}
Cannot add marketplace "constructor": Claude Code reserves this name and cannot register a marketplace under it. The name is set by "name" in the marketplace's marketplace.json; ask its maintainer to change it.
```

如果設定檔在 [`extraKnownMarketplaces`](https://code.claude.com/docs/zh-TW/settings-reference#extraknownmarketplaces) 下宣告該市集，Claude Code 在啟動時嘗試新增它也會以相同方式失敗，且此訊息會出現在 `/plugin` 中的 **Errors** 標籤上。

為市集取另一個名稱，然後再次新增：

* **您擁有市集**：變更 `marketplace.json` 中的 `name`
* **其他人託管它**：請所有者變更名稱

在 v2.1.296 之前，新增此類市集會因內部錯誤而失敗，而不是顯示此訊息。

### `SSH authentication failed` or `HTTPS authentication failed`

您從 git 儲存庫新增或更新了市集，複製失敗，並顯示 `Failed to clone marketplace repository:` 後跟以下其中一行。

首先檢查儲存庫本身：拼寫錯誤的 `owner/repo`、不存在的儲存庫或您看不到的私人儲存庫也會以此訊息結尾。在瀏覽器中開啟儲存庫 URL，或在終端機中執行 `git ls-remote <url>`，以確認它存在且您有權存取。

如果儲存庫是正確的，原因是憑證。Claude Code 會關閉 git 的提示和 askpass 程式（包括在 `GIT_ASKPASS` 中設定的程式），並以批次模式執行 SSH。當 git 需要提示時，複製的錯誤會包含 `fatal: Cannot prompt because user interactivity has been disabled`、`terminal prompts disabled` 或 `fatal: unable to get password from user`。只有 git 無需提示或 askpass 程式即可取得的憑證才會成功：

* **SSH**：`ssh -T git@<host>` 必須成功而不提示密碼，並且主機必須已在 `known_hosts` 中
* **HTTPS**：您的憑證輔助程式必須保存該主機的 token。對於 GitHub，執行 `gh auth login` 和 `gh auth setup-git`。對於其他主機，在您的 git 憑證輔助程式中儲存個人存取 token。若要測試，請在終端機中取消設定 `GIT_ASKPASS` 並執行 `git -c core.askPass= ls-remote <url>`。

一旦您所用協定的檢查成功執行而不提示，請再次執行新增或更新。成功的新增會列印 `Successfully added marketplace: <name>`。成功的更新會從您的 shell 列印 `Successfully updated marketplace: <name>`，或在工作階段中列印 `✔ Updated 1 marketplace`。

若要讓 Claude Code 跳過 GitHub `owner/repo` 來源的 SSH，請設定 `CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1`。沒有它，當 `github.com` 的 SSH 金鑰看起來已配置時，Claude Code 會透過 SSH 複製這些來源，並在 SSH 複製失敗時回退到 HTTPS。

有關背景自動更新可以和不能對您的認證做什麼，請參閱 [背景自動更新對認證的作用](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md#what-background-auto-update-does-with-credentials)。

### `SSH host key is not in your known_hosts file`

您從您從未連接過的主機透過 SSH 新增了市集，複製失敗，並顯示此行和 `ssh -T git@<host>` 提示。對於金鑰已更改的主機，訊息是 `SSH host key has changed`，並改為提供 `ssh-keygen -R <host>` 提示。

Claude Code 使用 `StrictHostKeyChecking=yes` 複製，因此它拒絕您尚未接受其金鑰的主機，而不是自動接受金鑰。從您的終端機連接一次以接受指紋，然後重試：

```shell theme={null}
ssh -T git@github.com
```

對於公開儲存庫，改為使用其 `https://` URL 新增市集，以完全避免 SSH。

### `Command 'git' not found or is in an unsafe location`

在 Windows 上，您新增了市集，Claude Code 報告 `Failed to clone marketplace repository: Command 'git' not found or is in an unsafe location (current directory)`。

Claude Code 在您的 `PATH` 上查找 `git`，並拒絕執行僅在目前目錄中找到的。若要修復它，請安裝 Git 並重試：

**1. 安裝 Git for Windows**

安裝 Git for Windows，使 `git` 在您的 `PATH` 上。

**2. 開啟新終端機**

開啟新終端機，使更新的 `PATH` 適用。

**3. 確認 git 執行**

確認 `git --version` 列印版本。

**4. 重試新增**

再次執行 `marketplace add` 命令。

### `Git clone timed out after 120s`

您新增或更新了市集，它失敗，並顯示 `Git clone timed out after 120s`，後跟設定 `CLAUDE_CODE_PLUGIN_GIT_TIMEOUT_MS` 的提示。

複製市集和重新複製一個以更新它，預設情況下獲得 120 秒。對於大型儲存庫或緩慢連接，提高限制。該值以毫秒為單位：

> [tab] Bash or Zsh
>
> ```bash theme={null}
> export CLAUDE_CODE_PLUGIN_GIT_TIMEOUT_MS=300000
> ```

> [tab] PowerShell
>
> ```powershell theme={null}
> $env:CLAUDE_CODE_PLUGIN_GIT_TIMEOUT_MS = "300000"
> ```

然後在同一 shell 中重試。

如果儲存庫是 monorepo，使用 `claude plugin marketplace add <source> --sparse <paths>` 限制簽出到您命名的目錄。

如果儲存庫有大型 git 子模組，請更新 Claude Code。在 v2.1.295 及更新版本中，Claude Code 僅擷取[包含外掛檔案的子模組](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#git-submodules-in-the-marketplace-repository)。較早的版本會擷取每個子模組，光是這樣就可能用盡這 120 秒。

### Marketplace updates keep failing offline

您在市集的 git 主機無法到達的環境中工作，每個工作階段都在背景中重複失敗的重新整理。您現有的市集簽出保持原位，啟動不會延遲。

每個工作階段，對於 [開啟自動更新](https://code.claude.com/docs/zh-TW/plugins/loading.md#which-marketplaces-and-plugins-auto-update) 的市集，Claude Code 在背景中檢查市集的 git 主機是否有新提交。當該檢查無法到達主機時，它會嘗試再次複製市集，離線時該複製也會失敗。

設定此變數以跳過重新複製嘗試，並在檢查無法到達主機時繼續使用現有簽出：

> [tab] Bash or Zsh
>
> ```bash theme={null}
> export CLAUDE_CODE_PLUGIN_KEEP_MARKETPLACE_ON_FAILURE=1
> ```

> [tab] PowerShell
>
> ```powershell theme={null}
> $env:CLAUDE_CODE_PLUGIN_KEEP_MARKETPLACE_ON_FAILURE = "1"
> ```

設定變數後，Claude Code 僅對已包含 `.claude-plugin/marketplace.json` 的簽出跳過重新複製。從未複製或其複製中途停止的市集仍會獲得複製嘗試，因此在線上新增一次。

對於完全離線部署，改為在映像建置時使用 `CLAUDE_CODE_PLUGIN_SEED_DIR` 預先填充外掛程式目錄，遵循 [種子容器和 CI](https://code.claude.com/docs/zh-TW/plugins/org.md#seed-containers-and-ci)。

### Marketplace add fails on a GitHub Enterprise Server host

您從 GitHub Enterprise Server (GHES) URL 新增了市集，並收到政策錯誤，或您從 claude.ai 新增了它，並收到 GitHub 存取錯誤。

兩種情況都在 GHES 頁面上：

* [政策錯誤](https://code.claude.com/docs/zh-TW/github-enterprise-server.md#marketplace-add-fails-with-a-policy-error) 表示您的組織限制了市集來源，管理員需要為主機新增 `hostPattern`
* [claude.ai 上的 GitHub 存取錯誤](https://code.claude.com/docs/zh-TW/github-enterprise-server.md#marketplace-add-on-claude-ai-fails-with-a-github-access-error) 表示您自己的 GitHub Enterprise 帳戶尚未連接

## 安裝外掛程式

您新增了市集並執行了安裝，安裝停止並顯示訊息，而不是安裝任何內容。這些條目涵蓋這些訊息。它們也涵蓋稍後出現在 `/plugin` **Errors** 標籤中的相關訊息，或當外掛程式或其市集無法找到、讀取或信任時的空白 **Discover** 標籤。

### `Plugin "<name>" not found in marketplace "<marketplace>"`

您執行了 `/plugin install <name>@<marketplace>` 或 `claude plugin install <name>@<marketplace>`，外掛程式名稱不在您機器上該市集目錄的副本中。

當您根本沒有新增市集時，`claude plugin install` 在您的 shell 中列印相同的訊息。如果 `claude plugin marketplace update <marketplace>` 然後回答 `Marketplace '<marketplace>' not found`，[首先新增市集](#add-a-marketplace)。

#### `not found in marketplace` with a refresh hint

提示讀取 `Your local copy may be out of date — try claude plugin marketplace update <marketplace>` 或 `The marketplace couldn't be refreshed (...)`。Claude Code 在查詢前沒有重新整理市集，例如當您離線時，所以您的目錄副本可能已過時。使用市集的名稱重新整理，然後再次安裝：

```text theme={null}
/plugin marketplace update <marketplace>
```

`claude plugin marketplace update` 列印 `Successfully updated marketplace: <name>`，而 `/plugin marketplace update` 顯示 `✔ Updated 1 marketplace`。如果重試的安裝列印相同的訊息，請按照 [`not found in marketplace` with no hint](#the-message-has-no-hint) 描述檢查名稱。[Claude Code 何時在安裝前重新整理市集](https://code.claude.com/docs/zh-TW/plugins/loading.md#when-claude-code-refreshes-a-marketplace-before-an-install) 列出重新整理不執行的其他情況。

#### `not found in marketplace` with no hint

名稱是最可能的問題。開啟 `/plugin`，前往 **Discover**，並從清單中複製名稱。

在 v2.1.232 之前，Claude Code 僅在查詢未命中後重新整理命名的市集，並且僅當為其開啟自動更新時。

### `Plugin "<name>" not found in any marketplace`

您執行了 `/plugin install <name>`，沒有 `@marketplace`，沒有註冊的市集有該外掛程式。`claude plugin install <name>` 報告 `Plugin "<name>" not found in any configured marketplace`。

沒有市集名稱，`claude plugin install` 搜尋它已有的目錄，不會首先重新整理它們，而 `/plugin install` 僅重新整理開啟自動更新的市集。命名市集，Claude Code 在查詢外掛程式前重新整理它：

```text theme={null}
/plugin install <name>@<marketplace>
```

當安裝成功時，您在工作階段中看到 `✓ Installed <plugin>.`，或從 `claude plugin install` 看到 `Successfully installed plugin: <plugin>@<marketplace>`。

如果您不知道哪個市集列出外掛程式，請執行 `/plugin marketplace list` 以取得您擁有的市集，並在 `/plugin` 中瀏覽 **Discover** 以查找外掛程式名稱。

### `Plugin '<name>@<marketplace>' is already installed globally`

您為已在使用者範圍或由受管設定安裝的外掛程式執行了 `/plugin install`，Claude Code 拒絕了 `Use '/plugin' to manage existing plugins.`。如果您輸入了沒有 `@<marketplace>` 的外掛程式名稱，訊息會省略 `globally`。

外掛程式已在每個專案中可用，因此沒有任何內容要新增。若要變更其 [範圍](https://code.claude.com/docs/zh-TW/plugins/install.md)、啟用或停用它，或設定它，請開啟 `/plugin` 並前往 **Installed**。

僅在專案或本機範圍安裝的外掛程式不會觸發此訊息。Claude Code 允許您也在使用者範圍安裝它，因此它在其他專案中可用。

`claude plugin install` 在您的 shell 中列印不同的訊息。對於已在目標範圍安裝的外掛程式，它列印 `Plugin "<name>@<marketplace>" is already installed (scope: user)` 並以退出代碼 0 退出。如果其快取目錄遺失，相同的命令會重新下載它。

### `"<plugin>" was not installed: it would share its folder with "<other>"`

您透過 `claude plugin install`、`/plugin` 或工作階段中的安裝建議安裝了外掛程式，Claude Code 拒絕了它，並顯示此行或 `would share its saved data with`。

被拒絕的外掛程式的 id 和已安裝的外掛程式的 id 對應到磁碟上的相同資料夾：一旦 `.` 和 `@` 被寫成 `-`，它們就是相同的。在 macOS 和 Windows 上，僅在大寫字母中不同的 id 也對應到相同的資料夾。安裝兩者會將一個外掛程式的檔案放在另一個的資料夾中，因此 Claude Code 拒絕，已安裝的外掛程式保留其檔案。

訊息命名了解決方案：

* **其他外掛程式已安裝**：訊息說 `Only one of the two can be installed.` 並命名 `claude plugin uninstall` 命令或 `/plugin` 中的卸載步驟，以移除其他外掛程式。執行它，然後再次安裝。對於卸載移除的內容，請參閱 [卸載刪除和保留的內容](https://code.claude.com/docs/zh-TW/plugins/cli-reference.md#what-an-uninstall-deletes-and-keeps)。
* **兩個 id 在一次安裝中到達**，例如外掛程式及其需要的相依套件：沒有安裝順序可以幫助。只有列出這兩個外掛程式的市集的維護者可以修復它，方法是重新命名其中一個。當兩者來自不同的市集時，任一個的維護者都可以。

### `This plugin uses a source type your Claude Code version does not support`

您安裝了一個外掛程式，其市集條目使用此版本 Claude Code 無法擷取的來源類型，Claude Code 停止並顯示此訊息和 `Update Claude Code and try again.`

更新 Claude Code，然後重試安裝。來源類型在 [市集參考](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md) 上。

### `Plugin archive integrity check failed`

您安裝了一個作為 zip 存檔分發的外掛程式，Claude Code 拒絕了它，並顯示此行和 `The archive was not installed.`。外掛程式的市集條目使用帶有 `sha256` 釘選的 [`archive` 來源](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference)，下載的檔案的摘要與釘選不符。

完整訊息如下所示：

```text theme={null}
Plugin archive integrity check failed for https://artifacts.example.com/claude-plugins/my-plugin.zip: expected sha256 6bfa50e3d2e00c052b46abe51fff89346ac803e45771f76dcf6df1ab74cca5e1, got ac52220c0914ef8ca6a602e4a7362f88d30fb021110f72a6d15b68c3fe7df2b7. The archive was not installed. Verify the sha256 in the marketplace entry, or that the URL serves the intended file.
```

修復因發佈者和安裝程式而異：

* **您發佈外掛程式**：重新計算 URL 提供的確切檔案的摘要，並更新市集條目中的 `sha256`。使用 `shasum -a 256 my-plugin.zip` 或 PowerShell 中的 `Get-FileHash -Algorithm SHA256 my-plugin.zip`
* **您安裝外掛程式**：在工作階段中執行 `/plugin marketplace update <name>` 以重新整理目錄，以防條目已更正，然後重試安裝。如果重新整理後摘要仍然不同，請詢問市集所有者在安裝前他們釘選了哪個檔案

### `An npm plugin source must name a registry package`

市集條目使用 [`npm` 來源](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference#npm-plugin-source) 的外掛程式無法安裝、更新或載入，且訊息包含此句。Claude Code 在擷取任何內容之前檢查了條目的 `package` 值並拒絕了它。訊息會指出該值與原因：

```text theme={null}
"github:acme/formatter" was not installed: it is not an http or https link. An npm plugin source must name a registry package (name or name@version) or link to a tarball file. For a plugin in a git repository, use a "github", "url" or "git-subdir" source.
```

市集的所有者必須變更該條目：

* **如果那是您**：將 `package` 變更為 [npm 外掛程式來源參考](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#npm-plugin-source) 接受的值，或將條目切換為 `github`、`url` 或 `git-subdir` 來源
* **如果不是您**：向市集所有者報告訊息

### `Marketplace "<name>" is registered from an untrusted source`

您之前新增的市集停止載入，其外掛程式也停止載入。此行出現在 `/plugin` **Errors** 標籤或下一次重新整理時。

市集以 [為官方 Anthropic 市集保留](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md) 的名稱註冊，但其註冊來源不是 `anthropics` GitHub 儲存庫。每次市集載入或重新整理時都會重新檢查保留的名稱，因此市集和從它安裝的外掛程式停止載入。

完整訊息命名保留的名稱和修復：

```text theme={null}
Marketplace "claude-community" is registered from an untrusted source: The name 'claude-community' is reserved for official Anthropic marketplaces. Only repositories from 'github.com/anthropics/' can use this name. To fix it, remove the marketplace and re-add it from the official source.
```

修復因使用者和發佈者而異：

* **您使用市集**：在您的 shell 中，執行 `claude plugin marketplace remove <name>`，然後從官方 `github.com/anthropics` 儲存庫再次新增市集
* **您發佈了在其名稱變為保留前使用該名稱的第三方市集**：重新命名它，並要求使用者從您的來源重新新增它

在 v2.1.205 之前，Claude Code 僅在您新增市集時檢查名稱，因此在其名稱變為保留前註冊的條目保持載入。

### `Marketplace "<name>" is added but ignored`

市集在 `~/.claude/plugins/known_marketplaces.json` 中有條目，但該條目未通過 Claude Code 每次讀取該檔案時執行的檢查，因此市集和從它安裝的外掛程式停止載入。在您的 shell 中，`claude plugin list` 會為每個受影響的外掛程式報告一行，指出原因和修復方式：

```text theme={null}
Marketplace team-tools is added but ignored. Its location is on a network drive, has "." or ".." in its path, or couldn't be checked. Re-add the marketplace (one added from a folder or file must be re-added from a copy on this computer), or, to trust a folder on a network drive, declare it under extraKnownMarketplaces in user or managed settings.
```

在工作階段中，`/plugin` **Errors** 標籤會將市集名稱放在引號中，在原因之後結束該行，並在其下一行顯示修復方式。

`is added but ignored` 之後的句子指出條目未通過的檢查：

* `Its location is on a network drive, has "." or ".." in its path, or couldn't be checked`，或關於 `The folder or file it was added from` 的相同句子：市集的目錄或其新增來源的本機路徑位於網路位置、路徑中有 `.` 或 `..` 區段，或無法檢查
* `Its git URL can't be used: <reason>` 或 `Its URL can't be read as an https:// or http:// address`：條目記錄的來源 URL 是 Claude Code 拒絕從中複製或擷取的 URL
* `Its source doesn't match its extraKnownMarketplaces entry in user or managed settings`：條目與同名的 [`extraKnownMarketplaces`](https://code.claude.com/docs/zh-TW/settings-reference#extraknownmarketplaces) 宣告不符

當 `(see the debug log)` 取代原因出現在 `is added but ignored` 之後時，表示 Claude Code 拒絕了市集的名稱，例如 [保留名稱的另一種拼寫](https://code.claude.com/docs/zh-TW/errors.md#marketplace-name-is-another-spelling-of-a-reserved-name)。[偵錯日誌](https://code.claude.com/docs/zh-TW/debug-your-config.md) 會指出該條目。

**該怎麼做：**

* 依照訊息中的修復方式。在您的 shell 中，執行 `claude plugin marketplace remove <name>`，然後從支援的來源或本機路徑再次新增市集，並重新安裝其外掛程式（remove 命令會卸載這些外掛程式）。remove 命令對被忽略的條目有效
* 若要保留位於網路位置的市集，請在您的使用者或受管設定中於 [`extraKnownMarketplaces`](https://code.claude.com/docs/zh-TW/settings-reference#extraknownmarketplaces) 下宣告它；儲存庫的 `.claude/settings.json` 或 `.claude/settings.local.json` 中的宣告不算數
* 對於與其設定宣告不同的來源，請從宣告的來源重新新增市集，或變更宣告。`claude plugin marketplace add` 會拒絕相同的不符情況；請參閱 [對應的 `Cannot add marketplace` 條目](#cannot-add-marketplace-source-doesnt-match)
* 對於被拒絕的名稱，請移除市集，若該行提供了 `Remove it:` 之後的命令，請使用該命令；以相同名稱再次新增會再次被拒絕

在 v2.1.286 之前，無論原因為何，`claude plugin list` 都會將此類市集報告為 `Marketplace <name> not found`，而 `/plugin` **Errors** 標籤會將其報告為 `Marketplace "<name>" is registered but was refused (see the debug log)`。原因僅出現在偵錯日誌中。在 v2.1.286 中，原因和修復句子使用不同的措辭，例如 `Its recorded location is network-shaped or unclassifiable (never probed)`。

### `Plugin <name> has a corrupt manifest file` or `has an invalid manifest file`

Claude Code 擷取了外掛程式，然後無法讀取其 `.claude-plugin/plugin.json`。在 shell 中，此行中的 `<name>` 可以是臨時目錄名稱；`Failed to install plugin "<name>@<marketplace>"` 前綴帶有外掛程式的真實名稱。措辭說明哪個檢查失敗：

* **`corrupt manifest file`，後跟 `JSON parse error:`**：檔案不是有效的 JSON
* **`invalid manifest file`，後跟 `Validation errors:`**：檔案可解析但未通過 schema 驗證，例如 `name: Invalid input` 用於遺失的必需欄位

`claude plugin install` 報告為 `Failed to install plugin "<name>@<marketplace>":` 並以代碼 1 退出。

外掛程式的作者必須修復檔案，在那之前無法安裝外掛程式：

* **如果那是您**：在您的 shell 中執行 `claude plugin validate <plugin-directory>` 以查看相同的錯誤及其違規路徑，然後修復檔案
* **如果不是您**：向市集所有者報告訊息

### `Plugin directory not found at path: <path>`

`/plugin` 中的 **Errors** 標籤顯示這個用於啟用的外掛程式，其市集按相對路徑列出，例如 `./plugins/my-plugin`，當市集內該路徑處沒有目錄時。如果您維護市集，請更正條目的 `source` 路徑或還原資料夾。否則，向市集所有者報告訊息。

`Marketplace directory not found at path: <path>` 表示市集自己的目錄遺失。對於您從本機路徑新增的市集，該目錄已移動或已刪除。還原它，或移除市集並從其新位置再次新增它。

### `No plugins available` or `No marketplaces configured`

您開啟了 `/plugin`，**Discover** 標籤為空，或 `claude plugin marketplace list` 列印 `No marketplaces configured`。

沒有市集註冊，因此沒有目錄可顯示。在工作階段中，新增官方市集 `anthropics/claude-plugins-official`：

```text theme={null}
/plugin marketplace add anthropics/claude-plugins-official
```

Claude Code 列印 `Successfully added marketplace: claude-plugins-official`，而 **Discover** 列出其外掛程式。[Anthropic 市集](https://code.claude.com/docs/zh-TW/plugins/anthropic-marketplaces.md) 頁面列出您可以新增的其他市集。

### `Marketplace "<name>" is already added from a different source`

您在工作階段中或從 shell 使用 [安裝命令上的 `--marketplace <source>`](https://code.claude.com/docs/zh-TW/plugins/install#add-a-marketplace-and-install-in-one-command) 指定了新的市集來源。Claude Code 從該來源擷取的目錄與您已從不同來源新增的市集具有相同的名稱。Claude Code 保留現有市集而不是替換它，外掛程式未安裝。

完整訊息如下所示：

```text theme={null}
Marketplace "acme-tools" is already added from a different source (github:acme/plugins). To use this source instead, remove that marketplace first with /plugin marketplace remove acme-tools.
```

選擇您想要的來源：

* **您已新增的市集**：使用 `/plugin install <plugin>@<name>` 按名稱從它安裝
* **新來源**：執行 `/plugin marketplace remove <name>`，然後重試安裝

### `Cannot add marketplace "<name>": its source doesn't match its extraKnownMarketplaces entry in user or managed settings`

您新增了一個市集，而其 `marketplace.json` 中的 `name` 在您的使用者設定或受管設定中已有 [`extraKnownMarketplaces`](https://code.claude.com/docs/zh-TW/settings-reference#extraknownmarketplaces) 條目。您提供的來源與該條目列出的來源不同，因此 Claude Code 拒絕新增且不註冊任何內容。

兩個來源只有在類型相同且每個欄位的值都相同時才相符。設定了您未傳遞之 `ref` 的條目會被視為不同。當您以 `https://github.com/` URL 提供儲存庫時，`github` 條目也會被視為不同，因為 Claude Code 會將該 URL 記錄為 [`git` 來源](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference#marketplace-sources)。請執行以下其中一項：

* **使用宣告的來源**：Claude Code 會自行[註冊在設定中宣告的市集](https://code.claude.com/docs/zh-TW/settings-reference.md#extraknownmarketplaces)，因此請先在工作階段中執行 `/plugin marketplace list`。如果清單顯示該名稱，表示市集已註冊，無需新增任何內容。

  如果清單未顯示該名稱，請依照條目的寫法輸入來源來新增它。對於 `source` 物件為 `{ "source": "github", "repo": "acme-corp/claude-plugins", "ref": "v1.2.0" }` 的條目，請執行：

  ```text theme={null}
  /plugin marketplace add acme-corp/claude-plugins#v1.2.0
  ```

* **使用新來源**：編輯或移除 `extraKnownMarketplaces` 條目，然後再次新增市集。如果受管設定宣告它，請詢問您的管理員

在 v2.1.287 之前，訊息為 `Cannot add marketplace "<name>": its network source differs from the one declared for it in settings (kind, target, or a fetch-shaping field such as headers / ref / path / sparsePaths)`。

### `Failed to install: <plugin> (<reason>)`

您在 `/plugin` 功能表中選擇了要安裝的外掛程式，沒有任何一個安裝，功能表關閉並顯示失敗的摘要。

某些原因（例如失敗複製後的 git 輸出）僅顯示其第一行。當這樣的原因被縮短時，摘要以 `Installing a plugin from its details (Enter) in /plugin shows its full error.` 結尾

該做什麼取決於摘要是否縮短了原因：

* 修復括號中原因命名的內容
* 當原因被縮短時，執行 `/plugin`，在 **Discover** 標籤上選擇外掛程式，然後按 **Enter** 從其詳細資訊安裝它。如果安裝在那裡失敗，詳細資訊檢視會顯示整個錯誤

### `Could not move the new copy of this plugin version into <path>`

當您安裝外掛程式時，Claude Code 下載其檔案的新副本，並將其移動到 [外掛程式快取](https://code.claude.com/docs/zh-TW/plugins/loading.md#find-plugins-on-disk) 中該版本的資料夾。此訊息表示移動失敗，通常是因為另一個程式在安裝執行時使用了該資料夾。檔案系統代碼出現在括號中：

```text theme={null}
Could not move the new copy of this plugin version into /home/user/.claude/plugins/cache/acme-tools/formatter/1.2.0: the new copy or the version folder stayed busy while the install ran (ENOTEMPTY) — usually a scanner still reading the freshly downloaded files, another program using that folder, or another process re-creating it. The previously installed copy was moved back. Run the install again once other Claude Code sessions or programs using that folder have finished.
```

訊息說明了安裝前的副本發生了什麼，這告訴您外掛程式是否仍然有效：

* `The previously installed copy was moved back`：您擁有的版本仍然安裝
* `had to be removed first`、`was not moved back` 或 `could not be moved back`：該外掛程式版本在安裝成功前未安裝
* 沒有這樣的句子：沒有較早的副本，因此版本未安裝

在 Windows 上，當另一個程式持有已安裝的副本本身時，訊息改為說該副本 `could not be replaced`，並且 `It was not replaced and the new copy was discarded`，因此您擁有的版本仍然安裝。

`Left on disk` 清單命名快取內的預留資料夾。稍後安裝該版本或外掛程式快取清理會移除它們，因此您不需要刪除它們。

若要修復安裝：

* 關閉使用外掛程式資料夾（在 `~/.claude/plugins/cache` 下）的其他 Claude Code 工作階段、編輯器和終端機，然後再次執行安裝
* 當訊息說檢查外掛程式快取資料夾的權限時，還原您對其命名的資料夾的寫入權限並釋放磁碟空間，然後再次執行安裝

### Dependency errors

宣告相依套件的外掛程式在無法滿足相依套件時可能無法安裝或安裝並保持停用。訊息在安裝時或載入時到達您：

* **在安裝期間**：拒絕作為安裝的錯誤訊息返回
* **當外掛程式載入時**：問題出現在 `claude plugin list` 和 `/plugin` **Errors** 標籤中，Claude Code 保持受影響的外掛程式停用，直到您解決它

下表列出每個訊息及其修復。若要作為作者宣告相依套件，請參閱 [外掛程式相依套件](https://code.claude.com/docs/zh-TW/plugins/dependencies.md)。

| 訊息 | 含義 | 如何解決 |
| :- | :- | :- |
| `Dependency "<dep>" is not installed` | 宣告的相依套件未安裝。 | 使用 `claude plugin install <dep>@<marketplace>` 在您的 shell 中安裝它，或卸載外掛程式。如果相依套件的市集尚未註冊，請新增它並在您的工作階段中執行 `/reload-plugins`，這會安裝它可以解決的遺失相依套件。 |
| `"<name>@synced" is loaded from your claude.ai account but meets a marketplace dependency only for other claude.ai plugins`，出現在 `is not installed` 訊息中 | 相依套件指定了市集，而同名的外掛程式是從您的 claude.ai 帳戶載入的。宣告該相依套件的外掛程式並非從 claude.ai 載入，因此 claude.ai 外掛程式無法滿足它。 | 在您的 shell 中執行 `claude plugin install <dep>@<marketplace>`，從其市集安裝相依套件。之後會改為載入市集副本，而非 claude.ai 的副本。 |
| `Dependency "<dep>" is disabled` | 相依套件已安裝但已關閉。 | 啟用相依套件，或卸載需要它的外掛程式。 |
| `Requires "<dep>" <range>, installed <version>` | 已安裝的相依套件版本超出外掛程式的宣告範圍。 | 將相依套件更新到範圍內的版本，或卸載外掛程式。 |
| `<Plugin or Dependency> "<name>" has conflicting version requirements` | 沒有版本滿足每個釘選它的範圍。訊息列出範圍。 | 卸載或更新其中一個衝突的外掛程式，或要求上游作者擴大其約束。 |
| `... has version requirements too complex to intersect` 或 `has an invalid version requirement` | 範圍不是有效的 semver，或無法相交組合的範圍。 | 修復無效範圍或簡化長 `\|\|` 鏈。 |
| `... has no git tag satisfying <range>` | 相依套件的儲存庫在範圍內沒有 `<name>--v*` 標籤。 | 檢查上游是否使用該約定標記版本，或放寬範圍。 |
| `Dependency "<dep>" (required by <plugin>) is in marketplace "<marketplace>", which is not in the allowlist` | 相依套件在不同的市集中，預設情況下跨市集解析已關閉。 | 在相同範圍自行安裝相依套件，在您的 shell 中使用 `claude plugin install <dep>@<marketplace>` 加上您安裝外掛程式的 `--scope`，然後重試。 |

若要以程式設計方式查看這些，請在您的 shell 中執行 `claude plugin list --json`。有問題的外掛程式帶有 `errors` 欄位及其訊息和 `errorDetails` 欄位，每個都有 `type`：前三列是 `dependency-unsatisfied`，第四列是 `dependency-version-unsatisfied`。

## 外掛程式已安裝但無法運作

安裝成功，但外掛程式的技能、hooks 或伺服器沒有執行任何操作。從 [外掛程式不出現或其技能不顯示](#plugin-doesnt-appear-or-its-skills-dont-show-up) 開始，它告訴您 Claude Code 報告它載入的位置，然後符合訊息。

### Plugin doesn't appear or its skills don't show up

您安裝了外掛程式並輸入 `/` 期望其技能，或要求 Claude 使用它，但沒有任何反應。

在變更任何內容前檢查外掛程式的狀態：

**1. 確認外掛程式已安裝並啟用**

執行 `/plugin` 並開啟 **Installed**。確認外掛程式已列出並啟用。`claude plugin list` 在您的 shell 中列印相同的清單，每個外掛程式的版本、範圍和 `Status: ✔ enabled`。

**2. 讀取 Errors 標籤**

在同一面板中開啟 **Errors** 標籤。每個條目將訊息與指導行配對。本節其餘部分的大多數訊息來自該標籤。

**3. 如果您在此工作階段期間安裝，請重新載入**

如果外掛程式已安裝且無錯誤，但您在此工作階段期間安裝了它，請執行 `/reload-plugins`。它列印 `Reloaded:` 及外掛程式、技能、代理、hooks 和伺服器的計數。當某些失敗時，它新增 `N errors during load. Run /plugin for details.`

如果外掛程式載入無錯誤且其技能仍未出現，下一步因您自己的外掛程式和其他人的而異：

* **您正在建置的外掛程式**：請參閱 [外掛程式載入但其技能遺失](#plugin-loads-but-its-skills-are-missing)
* **某人發佈的外掛程式**：在 `/plugin` 中開啟 **Installed**，並開啟外掛程式的詳細資訊窗格，其中列出外掛程式包含的內容。在那裡列出無技能的外掛程式在您輸入 `/` 時沒有任何內容可提供

### `Run /reload-plugins to apply.`

`/plugin` 中的安裝摘要以 `Run /reload-plugins to apply.` 結尾，而不是 `Plugin is now active.`。同時，提示詞上方可能會出現 `Plugins changed. Run /reload-plugins to activate.` 通知。

Claude Code 在安裝期間沒有啟用外掛程式，要麼是因為啟用它會 [使提示快取失效](https://code.claude.com/docs/zh-TW/prompt-caching.md#enabling-or-disabling-a-plugin)，要麼是因為啟用嘗試失敗。

您不需要輸入命令。面板關閉，Claude Code 為您執行 `/reload-plugins`，或將其排隊直到正在串流的回應完成。

讀取該重新載入列印的內容：

* **`Reloaded:` 及外掛程式、技能、代理、hooks 和伺服器的計數**：外掛程式現在處於活動狀態。當某些無法載入時，該行新增 `N errors during load. Run /plugin for details.`
* **`This reload changes MCP tools (...) — your next message will re-read the whole conversation instead of using the cache. Run /reload-plugins --force to apply.`**：重新載入會新增或移除外掛程式 MCP 伺服器，或 `LSP` 工具，並使您的提示快取失效。對於 LSP 情況，該行以 `This reload adds the LSP tool` 或 `This reload removes the LSP tool` 開頭。執行它時使用 `--force` 以啟用外掛程式，或啟動新工作階段

在 v2.1.268 之前，在安裝期間未啟用的安裝保持待處理，直到您自己執行 `/reload-plugins`。

在 v2.1.246 之前，該摘要中的技能計數僅包括外掛程式的 `commands/` 條目，因此重新載入可以載入外掛程式的 `SKILL.md` 技能，仍然報告 `0 skills`。

### `The packages it lists are not installed` 或 `were not installed, because ...`

對於相依套件安裝後沒有留下 `node_modules` 目錄的外掛程式，`/plugin` 和 `claude plugin list` 會顯示下列其中一則註記。外掛程式會載入，但需要遺失套件的部分可能無法運作。

* **`are not installed`**：此外掛程式可以執行安裝，但安裝未完成，例如因為失敗或逾時。若要重試安裝，請在 shell 中執行註記提供的 `claude plugin update` 命令，或從 `/plugin` 更新外掛程式

  ```shell theme={null}
  claude plugin update formatter@my-marketplace
  ```

  如果重試失敗，輸出會說明原因。當設定了 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` 時，`claude plugin update` 和 `/plugin` 會略過重試，並報告外掛程式已是最新版本。

* **`were not installed, because ...`**：此外掛程式無法執行安裝，註記會指出原因，例如 Yarn、pnpm 或 `bun.lockb` 鎖定檔，或其套件管理器未安裝在此電腦上的鎖定檔。只要該原因仍存在，更新外掛程式就不會安裝這些套件。如果原因是鎖定檔，則必須由外掛程式的作者替換它。如果是缺少套件管理器，請安裝它，然後更新外掛程式

### `Plugin "<name>" not cached at <path>`

**Errors** 標籤顯示此行及指導 `Run /plugin to refresh the plugin cache`。Claude Code 有外掛程式的安裝記錄，但記錄指向的目錄遺失，例如在您清除快取後。

從您的 shell 重新安裝外掛程式。`claude plugin install <name>@<marketplace>` 重新下載外掛程式，其安裝目錄遺失，即使其記錄存在：

```shell theme={null}
claude plugin install <name>@<marketplace>
```

然後在您的工作階段中執行 `/reload-plugins`。**Errors** 標籤條目消失，外掛程式回到 **Installed** 下。

### `installed_plugins.json holds a record under "<id>" that this version of Claude Code cannot read`

訊息以這些形式出現：

* **`claude plugin list`**：將其列印為 `Note:`
* **`claude plugin install`、`uninstall` 和 `update`**：拒絕並顯示 `Plugin "<name>" was not installed:`、`Plugin "<name>" was not uninstalled:` 或 `Plugin "<name>" was not updated:`，後跟相同的文字
* **任何這三個命令上的 `--json`**：結果行帶有相同的 `message` 和 `failureCode: "install_records_unreadable"`
* **多個這樣的記錄**：訊息讀作 `holds records under`
* **整個檔案宣告此版本不知道的格式**：訊息讀作 `installed_plugins.json is in a format (version <N>) that this version of Claude Code does not know` 代替

`installed_plugins.json` 中的命名記錄在有效的外掛程式 id 下是有效的 JSON，但其欄位不會為此版本解析。最有可能另一個版本的 Claude Code 寫入了它，也許是更新的版本。

當記錄存在時，此版本不會重寫檔案，因此記錄不會遺失。

按順序採取訊息的選項：

1. 使用 `claude update` 更新 Claude Code。
2. 如果您無法更新，請使用寫入記錄的 Claude Code 版本卸載命名的外掛程式。
3. 如果都沒有幫助，請手動從 `installed_plugins.json` 刪除記錄，然後重新啟動 Claude Code 或執行 `/reload-plugins`。

### `installed_plugins.json could not be read and was rebuilt`

`claude plugin list` 列印此注意事項，其路徑為保留的檔案，名為 `installed_plugins.unreadable.<date>.<hash>.kept`，只要該檔案位於 `installed_plugins.json` 旁邊。

不是有效 JSON 的 `installed_plugins.json`，或不是外掛程式清單的，無法說出您安裝的內容。

開啟 `.kept` 檔案以查看舊檔案記錄的內容，並重新安裝您遺失的外掛程式。Claude Code 永遠不會讀取檔案，該檔案在 [`cleanupPeriodDays`](https://code.claude.com/docs/zh-TW/settings-reference#cleanupperioddays) 排程上老化。

### `install records under names that no version of Claude Code can use were removed from installed_plugins.json`

`claude plugin list` 列印此注意事項，其路徑為副本，名為 `installed_plugins.set-aside.<date>.<hash>.json`，只要該副本位於 `installed_plugins.json` 旁邊。注意事項以 `Nothing needs doing about these copies.` 結尾。

`installed_plugins.json` 中的記錄位於不是有效外掛程式 id 的金鑰下，因此沒有版本的 Claude Code 可以使用它。檔案的其餘部分正常載入。

Claude Code 將無法使用的記錄複製到 `.set-aside` 檔案中，並將其從清單中刪除。Claude Code 永遠不會讀取副本，副本在 [`cleanupPeriodDays`](https://code.claude.com/docs/zh-TW/settings-reference#cleanupperioddays) 排程上老化。

### `does not load (...), so Claude Code ignores the whole file`

命令已成功執行。警告所指的設定檔有錯誤，因此在您修正它之前，Claude Code 會忽略整個檔案，包括命令寫入其中的任何內容。

修正警告所指出的錯誤。對於 Claude Code 不接受的值，[修正損壞的設定檔](https://code.claude.com/docs/zh-TW/settings.md#fix-a-broken-settings-file) 說明了修正方法。然後，如果命令的變更已不在檔案中，請再次執行該命令。

警告會出現在您 shell 中 `claude plugin install`、`enable`、`disable` 或 `claude plugin marketplace add` 的成功行之後：

```text theme={null}
⚠ /home/user/.claude/settings.json does not load (its "permissions" is not valid), so Claude Code ignores the whole file, including anything this command wrote there. Fix the file, then run this command again if its change is missing. If a newer Claude Code wrote the file, update Claude Code instead.
```

括號中的文字指出錯誤：

* **`its "<key>" is not valid`**：加上引號的設定項目持有 Claude Code 不接受的值。請在 [設定參考](https://code.claude.com/docs/zh-TW/settings-reference.md) 中查閱該設定項目可接受的值。當有多個值無效時，文字會指出第一個設定項目並計算其他項目的數量，例如 `its "permissions" and 1 other value are not valid`。
* **`it is not a JSON object`**：檔案的頂層不是 JSON 物件，例如頂層是陣列的檔案。

### `Disabled in ~/.claude/settings.json but still loads`

您在 `~/.claude/settings.json` 中將外掛程式設定為 `false`，其在 `claude plugin list` 或 `/plugin` 中的行顯示此訊息，後跟啟用它的來源，例如 `— project settings enable it, which overrides your user setting`。該更高優先順序來源中的 `true` 正在覆蓋您的使用者設定。

若要在您的機器上選擇退出專案啟用的外掛程式，請在 `.claude/settings.local.json` 中將 id 設定為 `false`，其優先順序高於專案檔案。對於訊息可以命名的其他來源，請參閱 [在使用者設定中停用但仍然載入](https://code.claude.com/docs/zh-TW/plugins/loading.md#disabled-in-user-settings-but-still-loads)。

如果 `claude plugin list` 改為將外掛程式標記為 `required by your org`，沒有設定檔涉及：您的組織在 claude.ai 上將該同步外掛程式標記為必需，即使您之前停用了它，它也會載入。請參閱 [從 claude.ai 同步的外掛程式](https://code.claude.com/docs/zh-TW/plugins/loading.md#synced-plugins)。

### `Plugin "<name>" is enabled in project settings but isn't installed here`

**Errors** 標籤顯示此行用於您的專案的 `.claude/settings.json` 啟用的外掛程式，指導 `Run claude plugin install <name>@<marketplace> --scope project to install it for this project`。

儲存庫的設定可以為打開它的每個人啟用外掛程式，但它們不會安裝它。當外掛程式來自外部來源（例如 GitHub 儲存庫或 npm 套件）時，Claude Code 在您自己安裝它之前不會下載它。從指導行在您的 shell 中執行命令，然後重新載入：

```shell theme={null}
claude plugin install <name>@<marketplace> --scope project
```

在您的工作階段中執行 `/reload-plugins` 後，**Errors** 標籤條目消失，外掛程式列在 **Installed** 下。

如果您的組織為您預先安裝外掛程式，它會透過受管設定執行此操作。請參閱 [預先安裝和要求外掛程式](https://code.claude.com/docs/zh-TW/plugins/org.md#pre-install-and-require-plugins)。

### 在 Windows 上執行 `plugin uninstall` 後外掛程式仍保持安裝

在 Windows 上，您在專案或本機範圍執行 `claude plugin uninstall`，它回報成功，但 `claude plugin list` 或 `/plugin` 仍列出該外掛程式。

`installed_plugins.json` 中針對該專案資料夾保存了該外掛程式的兩筆安裝記錄，每筆對資料夾路徑的寫法不同，而一次解除安裝只會移除其中一筆。若要檢查，請在 shell 中執行 `claude plugin list --json`。該外掛程式剩餘的列會有一個 `projectPath`，其資料夾寫法與您執行解除安裝的位置不同，例如 `C:\work\app` 寫成 `c:\work\app`。

從同一個資料夾，以相同的 `--scope` 再次執行相同的解除安裝命令。第二次執行在其自身的路徑寫法下找不到記錄，因此會移除另一種寫法下的記錄。對於專案範圍的安裝：

```shell theme={null}
claude plugin uninstall <name>@<marketplace> --scope project
```

然後再次執行 `claude plugin list --json`，確認該列已消失。

在 v2.1.295 之前，第二次執行會失敗並顯示 `Plugin "<name>" is not installed in project scope`。請執行 `claude update`，然後再次執行解除安裝。

### 從 git 儲存庫安裝的外掛程式顯示版本 `unknown`

`claude plugin list` 中的 `Version: unknown` 可能表示 Claude Code 無法讀取它作為 git 來源外掛程式版本所使用的提交。該外掛程式可能有自己的儲存庫，或位於以 git 託管的市集內。

在您的 shell 中執行以下命令，將 `formatter@my-marketplace` 替換為 `claude plugin list` 中該外掛程式的 `name@marketplace` 行：

**1. 更新 Claude Code**

[更新 Claude Code](https://code.claude.com/docs/zh-TW/setup.md#update-claude-code) 至 v2.1.302 或更新版本，該版本會以可讀取提交的格式進行複製：

```shell theme={null}
claude update
```

**2. 更新市集**

更新 Claude Code 的市集副本，其中保存了位於市集儲存庫內之外掛程式的提交：

```shell theme={null}
claude plugin marketplace update my-marketplace
```

**3. 更新外掛程式**

更新外掛程式以重寫其記錄的版本：

```shell theme={null}
claude plugin update formatter@my-marketplace
```

**4. 檢查版本**

檢查 `Version:` 行是否顯示如 [12 個字元的提交 ID](https://code.claude.com/docs/zh-TW/plugins/loading.md#how-claude-code-computes-the-version) 之類的值：

```shell theme={null}
claude plugin list
```

`claude plugin update` [每次執行只變更一個範圍的區塊](https://code.claude.com/docs/zh-TW/plugins/cli-reference.md#which-scope-the-command-updates)。對於仍顯示 `unknown` 的區塊，請使用該區塊的 `Scope:` 值重新執行：

```shell theme={null}
claude plugin update formatter@my-marketplace --scope project
```

如果重新執行後該區塊仍顯示 `unknown`，請參閱 [取得更多協助](https://code.claude.com/docs/zh-TW/troubleshooting.md#get-more-help)。

### `Failed to load hooks from <path>` and hooks that don't fire

外掛程式的 hooks 不執行，或一個阻止了一個動作。要麼 **Errors** 標籤顯示它們的載入失敗，hooks 載入且您在文字記錄中看到 `<Event> hook error` 通知或阻止錯誤，要麼 hook 載入無錯誤且永遠不會觸發。

#### Hooks fail to load

**Errors** 標籤顯示以下其中一個訊息：

* **`Failed to load hooks from <path>: <reason>`**：`hooks/hooks.json` 不是有效的 JSON 或失敗 hooks 架構。原因命名解析或驗證錯誤。修復檔案。若要在發佈外掛程式前在 `hooks/hooks.json` 中捕捉 JSON 語法問題，請在您的 shell 中執行 `claude plugin validate <plugin-directory>`
* **`hooks path not found: <path>`**：清單的 `hooks` 欄位命名在相對於外掛程式根目錄的該路徑處不存在的檔案。修復路徑或新增檔案
* **`hooks path escapes plugin directory: <path>`**：請參閱 [Path escapes plugin directory](https://code.claude.com/docs/zh-TW/errors.md#path-escapes-plugin-directory)

#### `hook error` notices in the transcript

形式為 `... hook error: Failed with non-blocking status code: <stderr>` 的通知表示 hook 執行且其命令失敗。例如，`Stop hook error: Failed with non-blocking status code: /bin/sh: node: command not found` 表示 Claude Code 產生的 shell 找不到 `node`。安裝它，或確保它在您啟動 `claude` 的終端機的 `PATH` 上。

如果 stderr 顯示外掛程式的路徑在空格處被截斷，hook 的 shell 形式命令在引號外使用 `${CLAUDE_PLUGIN_ROOT}`，且安裝路徑包含空格。將變數用雙引號括起來或使用 [exec 形式](https://code.claude.com/docs/zh-TW/hooks.md#exec-form-and-shell-form)。若要找到未引用的變數，請在外掛程式目錄上執行 `claude plugin validate`，並查找其 [引用警告](https://code.claude.com/docs/zh-TW/plugins/manifest-reference.md#quoting-and-path-separators)。

如果通知讀作 `Failed to run: Plugin directory does not exist: <path>`，請參閱 [`Plugin directory does not exist`](#plugin-directory-does-not-exist)。

對於任何其他錯誤，從外掛程式目錄自行執行 hook 的命令以查看完整輸出，或使用 [偵錯記錄](https://code.claude.com/docs/zh-TW/hooks.md#debug-hooks) 捕捉完整 stderr。

#### A plugin hook blocks a tool call or prompt

退出代碼為 2 的 hook [阻止它執行的動作](https://code.claude.com/docs/zh-TW/hooks.md#exit-code-2)。當外掛程式的 hook 以這種方式阻止且其 stderr 是阻止訊息時，錯誤以 `This hook comes from the <plugin> plugin.` 結尾，以便您知道要停用或修復哪個外掛程式。在 v2.1.281 之前，錯誤沒有命名外掛程式。

如果該訊息顯示外掛程式的路徑在空格處被截斷，應用 [未引用的 `${CLAUDE_PLUGIN_ROOT}` 修復](#hook-error-notices-in-the-transcript)。

#### Hook loads but never fires

如果 hook 載入無錯誤但從未觸發，請先在您的工作階段中執行 `/plugin` 並開啟該外掛程式的詳細資訊。若其中有一則以 `Its hooks.json hooks do not run` 開頭的註記，表示另一個同名的已啟用外掛程式改為註冊了它的 hook，而 [當兩個已啟用的外掛程式同名時的 hook](https://code.claude.com/docs/zh-TW/plugins/loading.md#hooks-when-two-enabled-plugins-share-a-name) 說明了是哪一個副本以及如何切換。否則，請檢查 hook 的定義，然後觀察它的執行：

**1. 檢查事件名稱**

事件名稱區分大小寫，因此確認您的名稱完全符合，例如 `PostToolUse`。

**2. 檢查匹配器**

確認 hook 的 `matcher` 符合工具名稱。

**3. 故意觸發事件**

對於 `PostToolUse` hook，要求 Claude 編輯檔案。

**4. 讀取偵錯日誌**

開啟 [偵錯日誌](https://code.claude.com/docs/zh-TW/hooks.md#debug-hooks)，其記錄哪些 hooks 符合。執行的 hook 會出現在那裡及其退出代碼。

### `Plugin directory does not exist: <path>`

即使訊息要求重新安裝，也請先在 Claude Code 提示字元執行 `/reload-plugins`。當您的工作階段載入外掛程式 hook 的目錄已從磁碟上消失時，外掛程式的 hook 會失敗並顯示 `Failed to run: Plugin directory does not exist: <path> (<plugin> — run /plugin to reinstall)`，且該 hook 不會執行。[`Plugin directory not found at path: <path>`](#plugin-directory-not-found-at-path) 是另一則訊息，與市集條目有關。

重新載入會從外掛程式目前的目錄載入其 hook。此失敗在每個工作階段中針對每個 hook 事件和命令只會顯示一次，因此 hook 不再報錯並不代表已修正。請改為讀取重新載入的輸出：

* **`Reloaded:` 且沒有錯誤行**：外掛程式的 hook 不再指向遺失的目錄
* **`N errors during load. Run /plugin for details.`**：在 `/plugin` 中開啟 **Errors** 標籤，並依照本頁中對應其顯示訊息的條目處理
* **以 `Run /reload-plugins --force to apply.` 結尾的行**：沒有任何內容被重新載入，hook 會持續失敗。請在 Claude Code 提示字元執行 `/reload-plugins --force`

### `Invalid MCP server config for "<server>"` and MCP servers that don't start

外掛程式捆綁了 MCP 伺服器，**Errors** 標籤顯示 `Invalid MCP server config for "<server>": <error>`，或伺服器已列出但 `/mcp` 永遠不會顯示它已連接。

#### `Invalid MCP server config for "<server>": <error>`

伺服器的配置通過架構檢查，但 Claude Code 無法為此工作階段解決它。冒號後的文字命名原因並決定修復：

* **`Missing environment variables: <names>`**：在啟動 Claude Code 的 shell 中設定這些變數，然後啟動新工作階段
* **`URL is unset or invalid`**：URL 使用的 `${user_config.*}` 選項未設定。執行 `/plugin configure <plugin>` 以設定它
* **`has an invalid MCP url`** 或 **`headersHelper for MCP server '<server>' references ${user_config.*}`**：外掛程式自己的配置有問題。修復您外掛程式的 MCP 配置中的 `url` 或 `headersHelper`，或如果外掛程式不是您的，向外掛程式的作者報告。`headersHelper` 情況在 [外掛程式命令參考了 user\_config](https://code.claude.com/docs/zh-TW/errors.md#plugin-command-references-user-config) 下有自己的條目

#### `Bundled MCP server "<name>" was not started: it needs configuration`

外掛程式包括伺服器作為 [MCPB 套件](https://code.claude.com/docs/zh-TW/plugins/components.md#include-a-packaged-mcpb-server)，宣告 `user_config`，且必需的設定沒有已保存的值或已保存的值無法通過套件自己的驗證，因此 Claude Code 跳過啟動伺服器。外掛程式的其餘部分有效。

在 `/plugin` 的 **Installed** 標籤上選擇外掛程式，並選擇 **Configure** 以提供值。保存後，`/plugin` 顯示 `Configuration saved.` 並關閉，Claude Code 重新載入外掛程式，如 [管理已安裝的外掛程式](https://code.claude.com/docs/zh-TW/plugins/install.md#manage-installed-plugins) 下所述。伺服器在該重新載入應用後啟動。在 v2.1.285 之前，Claude Code 跳過伺服器而不顯示此行。

#### Server is configured but never connects

執行 `/mcp` 以查看伺服器的狀態。當伺服器健康時，`/mcp` 將其列為已連接。

若要讀取伺服器在啟動時列印的錯誤，請執行 `claude --debug` 並在 `~/.claude/debug/<session-id>.txt` 開啟日誌。`--debug` 旗標不會列印到終端機。

> [!NOTE]
>
> 當與 [外掛程式 stdio 伺服器](https://code.claude.com/docs/zh-TW/mcp.md#plugin-provided-mcp-servers) 的連線在您執行 `claude --debug` 前不到 15 分鐘內失敗時，Claude Code [不會啟動該伺服器](https://code.claude.com/docs/zh-TW/errors.md#skipping-connection-recent-failure-cached)。在新的工作階段中，從 `/mcp` 中該伺服器的選單選擇 **Reconnect** 以啟動它，然後開啟日誌。

`.mcp.json` 中失敗架構的伺服器條目不會出現在 **Errors** 標籤中。Claude Code 丟棄該伺服器，並僅在該偵錯日誌中記錄 `Invalid MCP server config for <server> in <path>`。若要在不載入外掛程式的情況下找到條目，請在外掛程式目錄上在您的 shell 中執行 `claude plugin validate`，它將其報告為錯誤。

在 v2.1.281 之前，`claude plugin validate` 沒有檢查 `.mcp.json`。

#### Server works with `--plugin-dir` but fails after install

您是外掛程式的作者，伺服器在您使用 `--plugin-dir` 從其來源目錄載入外掛程式時啟動，但在安裝後失敗。

Claude Code 將已安裝的外掛程式複製到其快取中，因此僅從來源目錄工作的路徑會中斷。使用 `${CLAUDE_PLUGIN_ROOT}` 在外掛程式內寫入路徑。

對於到達外掛程式目錄外的路徑，請參閱 [外掛程式參考的外掛程式目錄外的檔案未找到](#files-the-plugin-references-outside-its-directory-arent-found)。

### Language server doesn't start, uses too much memory, or reports wrong diagnostics

您安裝了 [程式碼智慧外掛程式](https://code.claude.com/docs/zh-TW/plugins/code-intelligence.md)，Claude 沒有看到診斷，或語言伺服器使用太多記憶體或報告不是真實的錯誤。

#### Language server doesn't start

外掛程式連接到您單獨安裝的語言伺服器二進位檔案，Claude Code 從您的 `PATH` 按命令名稱產生它。

`/plugin` **Errors** 標籤顯示失敗及其原因，例如 `Executable not found in $PATH: "<binary>"`，而 `claude --debug` 將其記錄為 `LSP server <name> failed to start: <reason>`。

安裝二進位檔案並確認它在您啟動 `claude` 的終端機的 `PATH` 上，例如使用 `which typescript-language-server`。然後啟動新工作階段。

#### Language server uses too much memory

語言伺服器（例如 `rust-analyzer` 和 `pyright`）索引整個專案。使用 `/plugin disable <plugin>` 在工作階段中停用外掛程式，並改為依賴 Claude 的內建搜尋工具。

#### False positive diagnostics in a monorepo

未為工作區配置的語言伺服器可以報告內部套件的未解決匯入。Claude Code 端沒有任何內容要修復，診斷不會阻止 Claude 編輯程式碼。

## 建立外掛程式

您正在開發外掛程式，並使用 `--plugin-dir` 載入它或從本機市集安裝它。這些項目涵蓋您在開發外掛程式時遇到的失敗。若要在每次變更後執行檢查，請參閱[測試和偵錯](https://code.claude.com/docs/zh-TW/plugins/create.md#test-and-debug)。

兩個也會影響外掛程式使用者的失敗在[外掛程式已安裝但無法運作](#plugin-installed-but-not-working)下有其項目：

* **未觸發的 hook**：請參閱[未觸發的 hook](#failed-to-load-hooks-from-and-hooks-that-dont-fire)
* **未啟動的 MCP 伺服器**：請參閱[未啟動的 MCP 伺服器](#invalid-mcp-server-config-for-and-mcp-servers-that-dont-start)

### `commands path not found: <path>`

**Errors** 標籤顯示 `commands path not found: <absolute path>`，並提供指導 `Check that the path in your manifest or marketplace config is correct`。`skills`、`agents` 和 `hooks` 也會出現相同訊息。

Claude Code 從您的 `plugin.json` 或市集項目解析了一個路徑，相對於外掛程式根目錄，但在該處找不到任何內容。訊息中的路徑是它檢查的絕對路徑，因此請將其與磁碟上的內容進行比較。修正路徑或建立目錄，然後執行 `/reload-plugins`。

> [!NOTE]
>
> 在 v2.1.299 之前，此訊息可能會在啟動時出現在標示為 `synced[0]` 等標籤的列上。該列代表[從 claude.ai 同步](https://code.claude.com/docs/zh-TW/plugins/loading.md#synced-plugins)的外掛程式。當您電腦上的另一個 Claude Code 工作階段在片刻前更新了該外掛程式並移動了其檔案時，就會出現此訊息。若要載入該外掛程式，請重新啟動 Claude Code。若要避免此訊息因這個原因出現，請更新至 v2.1.299 或更新版本。

資訊清單中的路徑相對於外掛程式根目錄，並以 `./` 開頭。解析到外掛程式根目錄外的路徑會改為報告為 `<component> path escapes plugin directory`，並被捨棄。

### `--plugin-dir` 在市集根目錄不會載入 `plugins/` 下的外掛程式

您啟動了 `claude --plugin-dir <path>`，沒有看到錯誤，但外掛程式的 skills、agents 和 hook 不存在。

`--plugin-dir` 採用外掛程式的根目錄，即包含 `.claude-plugin/plugin.json` 和元件目錄（例如 `skills/`）的目錄。如果您改為指向市集根目錄，Claude Code 不會讀取 `marketplace.json`，因此 `plugins/` 下的外掛程式不會載入，您也看不到錯誤。在 v2.1.281 之前，Claude Code 將市集根目錄載入為一個以該目錄命名的空外掛程式。將旗標指向外掛程式目錄本身：

```shell theme={null}
claude --plugin-dir ./my-marketplace/plugins/my-plugin
```

然後在 `/plugin` 中開啟 **Installed**，外掛程式的詳細資訊窗格會列出其元件。

### 外掛程式參考其目錄外的檔案找不到

外掛程式使用 `--plugin-dir` 從其來源目錄運作，但安裝後失敗，出現關於路徑（例如 `../shared-utils`）的錯誤。

Claude Code 將已安裝的外掛程式複製到其快取中，並從該處載入它，因此到達外掛程式自身目錄外的路徑在快取中指向空無。將共用檔案移到外掛程式目錄內，或透過其內的符號連結參考它們。如需快取位置和路徑解析方式，請參閱[在磁碟上尋找外掛程式](https://code.claude.com/docs/zh-TW/plugins/loading.md#find-plugins-on-disk)。

### `${CLAUDE_PLUGIN_ROOT}` 在 Windows 上顯示正斜線

在 Windows 上，透過 Git Bash 執行的外掛程式 hook 接收 `${CLAUDE_PLUGIN_ROOT}` 為 `C:/Users/you/...` 而不是 `C:\Users\you\...`，預期反斜線的指令碼會中斷。

安裝 Git Bash 後，[shell 形式的 hook](https://code.claude.com/docs/zh-TW/hooks.md#exec-form-and-shell-form) 預設會透過 Git Bash 執行。對於透過 Git Bash 執行的 hook，Claude Code 會以正斜線傳遞路徑，使 Bash 不會將反斜線讀取為跳脫字元。Bash 內建命令、MSYS 工具和原生 Windows 二進位檔都接受該形式。

如果您的指令碼需要反斜線，請將 hook 切換為保留原生路徑的其中一種形式，如[執行形式和 shell 形式](https://code.claude.com/docs/zh-TW/hooks.md#exec-form-and-shell-form)下所述：

* 執行形式的 hook，它使用 `args` 陣列直接產生程序
* 具有 `"shell": "powershell"` 的 hook

### 外掛程式載入但其 skills 遺失

您的外掛程式列在 **Installed** 下，沒有錯誤，但當您輸入 `/` 時，不會提供其 skills。

Skills 從外掛程式根目錄的 `skills/` 載入，命令從外掛程式根目錄的 `commands/` 載入。只有 `plugin.json` 屬於 `.claude-plugin/` 內，`.claude-plugin/` 內的 `skills/` 目錄不會被掃描。將目錄移到外掛程式根目錄，並執行 `/reload-plugins`。之後，外掛程式的詳細資訊窗格在 `/plugin` 中列出 skills，輸入 `/` 會提供它們。

每個 skill 是包含 `SKILL.md` 的目錄。資訊清單中指向 `SKILL.md` 檔案而不是其目錄的 `skills` 項目會報告為 `path is a file; skills entries must be directories containing SKILL.md`。

### Skill 載入但 Claude 從不叫用該 skill

您外掛程式的 skill 在您輸入其 `/<plugin>:<skill>` 命令時執行，但 Claude 從不在回應純文字請求時叫用它。

按順序檢查這些原因：

* **Skill 設定 `disable-model-invocation: true`**：[建立您的第一個外掛程式](https://code.claude.com/docs/zh-TW/plugins/create.md#create-your-first-plugin)中的範本 skill 會設定它。從您想要 Claude 自行叫用的 skill 中移除該行。[控制誰叫用 skill](https://code.claude.com/docs/zh-TW/skills.md#control-who-invokes-a-skill) 涵蓋該欄位
* **描述不符合人們的提問方式**：完成[Skill 未觸發](https://code.claude.com/docs/zh-TW/skills.md#skill-not-triggering)中的檢查
* **描述被截斷**：安裝許多 skills 時，Claude Code 會縮短描述以符合列表的字元預算，這可能會去除 Claude 需要匹配請求的關鍵字。請參閱[Skill 描述被截短](https://code.claude.com/docs/zh-TW/skills.md#skill-descriptions-are-cut-short)

若要測量 skill 在現實提示詞中觸發的頻率，而不是逐一檢查，請使用 [`tool_used: Skill` 評分器](https://code.claude.com/docs/zh-TW/plugin-evals#create-your-first-eval-suite)撰寫評估案例，並在每次描述變更後使用 `claude plugin eval` 執行它。

### `<directory> is not a plugin or skill folder` 來自 `claude plugin eval init`

您從不是外掛程式根目錄的目錄（例如您的家目錄或保留外掛程式在子目錄中的儲存庫根目錄）執行了 `claude plugin eval init`。`init` 在工作目錄下寫入套件，因此它會停止，而不是建立外掛程式永遠看不到的 `evals/` 目錄。

變更到外掛程式的根目錄，即保存 `.claude-plugin/plugin.json` 或 skill 的 `SKILL.md` 的目錄，然後再次執行命令。若要刻意在其他地方搭建套件，請傳遞 `--eval-dir`。請參閱[使用評估測試外掛程式](https://code.claude.com/docs/zh-TW/plugin-evals.md)。

### `userConfig` 對話框從不出現

您的外掛程式宣告 `userConfig` 選項，但安裝時不會出現設定對話框。

安裝是否要求這些值取決於您在何處執行它：

* **在工作階段中的 `/plugin install`，或 `/plugin` 中的 Discover 標籤**：對話框是此互動式安裝的一部分
* **VS Code 擴充功能的管理外掛程式對話框**：在安裝後以表單形式要求未設定的選項。在 v2.1.285 之前，在該處安裝不會顯示選項表單，因此請使用 `/plugin configure <plugin>@<marketplace>` 從終端機工作階段設定值
* **在您的 shell 中的 `claude plugin install`**：永遠不會提示 `userConfig` 值。它會儲存您傳遞的任何 `--config KEY=VALUE` 值，當選項保持未設定時，它會列印 `N userConfig options not yet set — run /plugin configure <plugin>@<marketplace> in Claude Code, or pass --config KEY=VALUE.` 當任何未設定的選項是必需的時，`(M required)` 跟隨 `not yet set`。

如果您從 shell 安裝，請使用 `--config` 傳遞值，每個選項一個旗標：

```shell theme={null}
claude plugin install my-plugin@my-marketplace --config api_url=https://example.com
```

當每個選項都設定時，安裝輸出不會包含 `not yet set` 行。

若要之後改為開啟對話框，請在工作階段中執行 `/plugin configure my-plugin@my-marketplace`。從 shell，[`claude plugin configure`](https://code.claude.com/docs/zh-TW/plugins/cli-reference#plugin-configure) 顯示哪些選項仍未設定，並儲存在 stdin 上管道傳入的值。它需要 Claude Code v2.1.285 或更新版本。

如果您傳遞資訊清單未宣告的 `--config` 鍵，外掛程式仍會安裝，命令會列印 `⚠ Installed, but --config not applied: --config key "<key>" isn't declared in this plugin's userConfig.` 後面跟著外掛程式確實宣告的鍵。

對於運送[MCPB 套件檔案](https://code.claude.com/docs/zh-TW/plugins/components.md#include-a-packaged-mcpb-server)的外掛程式，該檔案宣告其自身的 `user_config`，訊息改為讀取 `isn't declared in this plugin's userConfig or by its bundled MCP servers.`，已知的鍵包括該伺服器的鍵，寫成 `<server>.<key>`。資訊清單按 URL 參考的套件在安裝時不會被讀取，因此其鍵不會被列出，訊息會說在 `/plugin` 中設定它。設定 `<server>.<key>` 鍵需要 Claude Code v2.1.285 或更新版本。

### `claude plugin validate` 報告錯誤

您執行了 `claude plugin validate <path>`，或在工作階段中執行了 `/plugin validate <path>`，它列印了 `Found N errors` 和 `Validation failed`，然後以代碼 1 結束。

驗證器讀取您提供的路徑處的資訊清單：外掛程式目錄的 `.claude-plugin/plugin.json`、市集目錄的 `.claude-plugin/marketplace.json`，或者對於同時包含兩者的目錄則讀取兩者。對於市集，它在項目自身資訊清單中的問題前加上項目索引，如 `plugins[1] plugin.json → json: ...`。在 v2.1.289 之前，Claude Code 會將同時包含兩者的目錄僅作為市集進行驗證。

該表涵蓋停止驗證的訊息和兩個警告 `No frontmatter block found` 和 `Unknown field '<key>'`，只有在您傳遞 `--strict` 時才會停止。其他警告，例如遺失描述，未列出。

| 訊息 | 原因 | 修正 |
| :- | :- | :- |
| `File not found: <path>` | 路徑沒有資訊清單，或不存在。 | 針對外掛程式或市集根目錄（包含 `.claude-plugin/` 的目錄）執行命令。 |
| `No manifest found in directory. Expected .claude-plugin/marketplace.json or .claude-plugin/plugin.json` | 目錄沒有 `.claude-plugin/` 資訊清單。 | 建立資訊清單，或指向正確的目錄。 |
| `Invalid JSON syntax: <parse error>` | 資訊清單或 `hooks/hooks.json` 不是有效的 JSON。 | 修正 JSON。在您修正 `hooks/hooks.json` 之前，工作階段會載入外掛程式而不包含該檔案中的 hook。 |
| `Path not found: <path>. The runtime loader will report this as a load failure.` | 資訊清單中的元件路徑不存在。 | 修正路徑或建立目錄。 |
| `Path contains ".." which could be a path traversal attempt: <path>` | 元件路徑逃逸外掛程式目錄。 | 使用外掛程式根目錄內的路徑。 |
| `Path is a file; skills entries must be directories containing SKILL.md` | `skills` 項目指向 `SKILL.md` 而不是其目錄。 | 指向父目錄，或 `.` 表示根層級 `SKILL.md`。 |
| `No frontmatter block found` 或 `YAML frontmatter failed to parse: <error>` | Skill、agent 或命令檔案有遺失或無效的 YAML frontmatter。 | 在 `---` 分隔符之間新增或修正 frontmatter。驗證外掛程式目錄時報告。 |
| `Plugin name "<name>" is reserved: it passes as one of Anthropic's own` | 外掛程式的 `name` 是其中一個[保留名稱](https://code.claude.com/docs/zh-TW/plugins/manifest-reference.md#name)。 | 根據其功能重新命名外掛程式。 |
| `Unknown field '<key>'` | 資訊清單有 schema 未定義的欄位。 | 移除它，或使用訊息建議的名稱。Claude Code 在載入時忽略未知欄位。如需 `plugin.json` 中的 `privacyPolicyUrl` 和其他目錄列表欄位，請參閱[目錄列表欄位](https://code.claude.com/docs/zh-TW/plugins/manifest-reference.md#directory-listing-fields)。 |

在每次修正後再次執行命令，直到它不列印任何錯誤。

`plugin.json` 欄位在[資訊清單參考](https://code.claude.com/docs/zh-TW/plugins/manifest-reference.md)上，市集層級訊息在[市集驗證錯誤](#marketplace-validation-errors)下。

### `Plugin <name> has conflicting manifests`

外掛程式無法載入，出現 `Plugin <name> has conflicting manifests: both plugin.json and marketplace entry specify components.`

外掛程式有其自身的 `plugin.json`，其市集項目設定 `strict: false` 同時也宣告 `commands`、`agents`、`skills`、`hooks`、`outputStyles` 或 `themes` 中的任何一個。從項目中移除這些欄位，或在項目中設定 `strict: true`，以便 Claude Code 將它們附加到 `plugin.json`。請參閱[嚴格模式](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#strict-mode)。

### `Warning: No commands found in plugin <name> custom directory`

當外掛程式載入時，`claude --debug` 日誌在 `~/.claude/debug/<session-id>.txt` 記錄 `Warning: No commands found in plugin <name> custom directory: <path>. Expected .md files or SKILL.md in subdirectories.` 工作階段或 **Errors** 標籤中不會出現任何內容。

資訊清單中的 `commands` 路徑存在，但不包含 `.md` 檔案，也不包含子目錄中的 `SKILL.md`。新增命令檔案，或從資訊清單中移除路徑。

## 託管市集

您發佈市集，使用者報告錯誤，或您自己的驗證失敗。這些條目適用於市集所有者。

### Plugins with relative paths fail in URL-based marketplaces

使用者使用 `https://example.com/marketplace.json` URL 新增了您的市集。其 `source` 是相對路徑（例如 `./plugins/my-plugin`）的外掛程式安裝失敗，並顯示 `its marketplace entry path does not stay inside the marketplace directory`。已安裝的外掛程式無法載入，並顯示 `Plugin source path refused`。兩個訊息都有 [錯誤參考條目](https://code.claude.com/docs/zh-TW/errors.md#marketplace-entry-path-does-not-stay-inside-the-marketplace-directory)。

當使用者使用 URL 新增市集時，Claude Code 僅下載 `marketplace.json` 檔案本身。它不會從該伺服器按相對路徑擷取外掛程式檔案，因此相對路徑中的條目指向從未擷取的目錄。為每個條目提供 Claude Code 可以自行擷取的來源，例如 GitHub 儲存庫：

```json theme={null}
{ "name": "my-plugin", "source": { "source": "github", "repo": "owner/repo" } }
```

或者，在 git 儲存庫中託管市集，並告訴使用者使用儲存庫 URL 新增它。對於 git 來源，Claude Code 複製整個儲存庫，因此相對路徑解析。來源類型在 [市集參考](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md) 上。

### 根外掛程式來自 git 子模組的檔案在安裝後遺失

您的外掛程式位於市集根目錄，並執行或讀取儲存庫中某個 git 子模組的檔案。安裝後，該子模組的目錄是空的。在 v2.1.295 之前，Claude Code 會擷取每個子模組，因此該目錄會有內容。

當 Claude Code 複製您的市集時，它只會擷取[包含外掛程式檔案的子模組](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#git-submodules-in-the-marketplace-repository)。對於位於根目錄的外掛程式，它會藉由讀取外掛程式設定中的路徑以及外掛程式檔案的文字來判斷。它無法看到指令碼在執行時才建構的路徑。

請將指向子模組的路徑完整寫在 Claude Code 能讀取的位置，例如 hook 命令中的 `${CLAUDE_PLUGIN_ROOT}/vendor/tool/run.sh`。Claude Code 接著會為該外掛程式擷取儲存庫中的每個子模組。

### Marketplace validation errors

您從市集目錄執行了 `claude plugin validate .`，它報告了市集檔案本身的錯誤或警告。

`claude plugin validate` 也驗證其 `source` 是本機路徑的每個條目，並在條目的 `version` 與外掛程式自己的清單不同時警告。

下表列出市集級別訊息。條目級別訊息是 [`claude plugin validate` reports errors](#claude-plugin-validate-reports-errors) 下的外掛程式訊息，前綴為 `plugins[N] plugin.json →`。

| 訊息 | 種類 | 修復 |
| :- | :- | :- |
| `Duplicate plugin name "<name>" found in marketplace` | 錯誤 | 為每個外掛程式提供唯一的 `name`。 |
| `Path contains "..": <path>` 在 `plugins[N].source` 下 | 錯誤 | 使用相對於市集根目錄的路徑，沒有 `..` 段。 |
| `Marketplace name cannot contain control or bidirectional-formatting characters` | 錯誤 | 從名稱中移除字元，例如逃逸或換行符。 |
| `Plugin name cannot contain control or bidirectional-formatting characters` | 錯誤 | 從外掛程式 `name` 中移除字元。 |
| `Claude Code cannot install plugins from marketplace "<name>". Each part of a plugin id (plugin@marketplace) may use only the letters a-z and A-Z, digits, ".", "_" and "-", and must start with a letter or digit. Change the marketplace's "name".` | 錯誤 | 將市集重新命名以符合訊息所述的規則。 |
| `Claude Code cannot install plugin "<name>". Each part of a plugin id (plugin@marketplace) may use only the letters a-z and A-Z, digits, ".", "_" and "-", and must start with a letter or digit. Change this entry's "name".` | 錯誤 | 將條目重新命名以符合訊息所述的規則。 |
| `Marketplace has no plugins defined` | 警告 | 至少新增一個條目到 `plugins`。 |
| `No marketplace description provided` | 警告 | 新增頂級 `description`。 |
| `Plugin name "<name>" is not kebab-case` 在 `plugins[N] plugin.json → name` 下 | 警告 | 重新命名為小寫字母、數字和連字號；claude.ai 市集同步需要該形式。 |
| `Entry declares version "<a>" but <path>/plugin.json says "<b>"` | 警告 | 更新條目以符合 `plugin.json`，在安裝時是權威的。 |
| `Marketplace name "<name>" is reserved in Claude Desktop` | 警告 | 重新命名市集。Claude Desktop 的受管市集同步拒絕任何大小寫的 `org`、`org-provisioned` 和 `unknown`。 |
| `Marketplace name "<name>" is not accepted by Claude Desktop` 或 `Plugin name "<name>" is not accepted by Claude Desktop` | 警告 | 重新命名為最多 128 個字元的字母、數字、`.`、`_` 和 `-`，以字母或數字開頭。 |

在 v2.1.247 之前，包含控制或雙向格式化字元的市集名稱報告為 `Marketplace name impersonates an official Anthropic/Claude marketplace`。

## 被您的組織阻止

您的組織部署受管設定，限制外掛程式，命令被拒絕，並顯示政策訊息。這些條目命名每個拒絕背後的設定，因此您知道要求管理員什麼。對於管理員端，請參閱 [為您的組織管理外掛程式](https://code.claude.com/docs/zh-TW/plugins/org.md)。

### `Marketplace source '<source>' is blocked by enterprise policy`

您執行了 `/plugin marketplace add`、`update` 或安裝，Claude Code 拒絕了此行。

您的管理員在受管設定中設定了 `blockedMarketplaces` 或 `strictKnownMarketplaces`，此來源不被允許。要求您的管理員允許來源，或新增訊息列出的允許來源之一。

將訊息的其餘部分與看到的內容相符，以查看什麼類型的政策阻止了來源：

* **`Allowed sources: <list>`**：阻止來自 `strictKnownMarketplaces` 允許清單而不是 `blockedMarketplaces` 阻止清單
* **`No external marketplaces are allowed.`**：`strictKnownMarketplaces` 允許清單為空
* **提示速記假設 github.com 的 `Tip:`**：允許清單允許 git 主機按主機名稱，您傳遞的 `owner/repo` 速記指向 github.com。如果儲存庫位於您的內部主機上，使用其完整 URL 再次新增它，例如 `git@your-git-host.com:owner/repo.git`

您在政策變得更具限制性之前新增的市集停止重新整理，因為政策在每次重新整理時適用。

### `Marketplace "<name>" is not in the allowed marketplace list`

**Errors** 標籤顯示此行，或 `Marketplace "<name>" is blocked by enterprise policy`，用於您已註冊的市集。

相同的受管設定，阻止 [市集來源](#marketplace-source-is-blocked-by-enterprise-policy)，在載入時適用。`strictKnownMarketplaces` 不包括此市集，或 `blockedMarketplaces` 命名它，因此 Claude Code 停止載入它及其外掛程式。對於允許清單變體，指導行顯示允許的來源，或 `Contact your administrator to configure allowed marketplace sources`。對於阻止清單變體，它讀取 `This marketplace source is explicitly blocked by your administrator`。

### `Plugin "<name>" is blocked by your organization's policy and cannot be installed`

安裝被拒絕，並顯示此行，啟用時顯示相同的行，以 `cannot be enabled` 結尾，或安裝或更新時顯示命名原因的行：`Plugin "<name>" is from marketplace "<marketplace>", which is blocked by your organization's policy`，或 `Plugin "<name>" depends on "<dep>", which is blocked by your organization's policy`。

受管設定阻止此外掛程式、其市集或它需要的依賴項。詢問您的管理員哪個條目適用。被阻止的依賴項表示外掛程式在依賴項的市集被允許前無法安裝。

### `--plugin-dir is disabled by your organization's managed settings (disableSideloadFlags)`

您使用 `--plugin-dir`、`--plugin-url`、`--agents` 或 `--mcp-config` 啟動了 `claude`。Claude Code 以此訊息退出，並顯示 `Plugins, custom agents, and MCP servers can only be loaded from sources your administrator has approved.`

您的管理員在受管設定中設定了 `disableSideloadFlags`，這會關閉從任意路徑載入外掛程式、代理和伺服器的旗標。改為從核准的市集載入外掛程式，或要求您的管理員移除設定。

`/plugin` **Errors** 標籤中的相關訊息是 `--plugin-dir copy of "<name>" ignored: plugin is locked by managed settings`。受管設定按名稱啟用或停用該外掛程式，Claude Code 忽略您的 `--plugin-dir` 副本，因此旗標無法覆蓋政策。

### `Plugins from ~/.claude/skills/ are blocked by your organization's managed settings`

您執行了 `claude plugin init` 或 `claude plugin enable`，它停止並顯示此行。訊息命名 `strictKnownMarketplaces or blockedMarketplaces`，並要求您的管理員將 `{"source":"skills-dir"}` 新增到 `strictKnownMarketplaces` 或從 `blockedMarketplaces` 中移除它。

`skills-dir` 來源代表 Claude Code 從您的 `~/.claude/skills/` 目錄載入的外掛程式。要求您的管理員進行訊息命名的變更。

### `Command-sourced plugins are disabled by your organization's managed settings`

您安裝或更新了具有 `command` 來源的外掛程式，它停止並顯示此行和 `The plugin was not installed or updated and its command was not run.`

您的管理員設定了 `disableCommandPluginSources`，因此 Claude Code 拒絕執行市集宣告的產生外掛程式的命令。單獨設定 `allowManagedHooksOnly` 在 `disableCommandPluginSources` 未設定時具有相同的效果。詢問您的管理員外掛程式是否可以從政策允許的來源類型發佈。

### `Marketplace '<name>' is seed-managed`

您執行了 `claude plugin marketplace update <name>`，它失敗，並顯示 `Marketplace '<name>' is seed-managed (<dir>)` 和要求您詢問管理員的提示。

操作員透過 `CLAUDE_CODE_PLUGIN_SEED_DIR` 預先填充此市集，Claude Code 將種子管理的市集視為唯讀。批量 `marketplace update` 跳過它並更新其他的。

若要變更市集的內容，請詢問維護種子映像的人員更新它。有關程序，請參閱 [種子容器和 CI](https://code.claude.com/docs/zh-TW/plugins/org.md#seed-containers-and-ci)。

## 後續步驟

* [外掛程式載入參考](https://code.claude.com/docs/zh-TW/plugins/loading.md)：為什麼範圍、快取和優先順序的行為方式如此
* [外掛程式命令參考](https://code.claude.com/docs/zh-TW/plugins/cli-reference.md)：`claude plugin` 命令的旗標、預設值、輸出和退出代碼
* [安裝和管理外掛程式](https://code.claude.com/docs/zh-TW/plugins/install.md)：從開始的安裝步驟
* [為您的組織管理外掛程式](https://code.claude.com/docs/zh-TW/plugins/org.md#troubleshoot-policy)：管理員的政策端故障排除

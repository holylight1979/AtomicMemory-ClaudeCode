<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/plugins/install | lastmod: 2026-10-28 | section: Plugins / Use plugins -->
> 來源：https://code.claude.com/docs/zh-TW/plugins/install（官方 zh-TW，lastmod 2026-10-28）｜分類：Plugins › Use plugins｜EN 摘要：Install Claude Code plugins from a marketplace on any surface you use, choose an install scope, and update or remove them later.

# 安裝和管理外掛程式

> 從任何使用介面上的市集安裝 Claude Code 外掛程式，選擇安裝範圍，並在稍後更新或移除它們。

安裝外掛程式會將其技能、代理、hooks 和 MCP 伺服器新增到您機器上的 Claude Code。

本頁面適用於在自己的機器或帳戶上使用外掛程式的任何人，無論是在終端機、桌面應用程式、IDE 或雲端工作階段中：它涵蓋安裝、選擇範圍、新增市集和保持外掛程式更新。

> [!NOTE]
>
> 這些情況在其他頁面上涵蓋：
>
> * **您使用 claude.ai 聊天或 Cowork，而不是 Claude Code**：請參閱 [claude.ai 和 Cowork 中的外掛程式](https://claude.com/docs/plugins/overview)
> * **Claude Code 列印了錯誤**：在 [外掛程式疑難排解](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md) 中找到它

從 [安裝外掛程式](#install-a-plugin) 開始。如果有人傳送給您的安裝命令其 `@` 名稱不是 `claude-plugins-official`，請先 [新增該市集](#add-a-marketplace)。

## 安裝外掛程式

作為範例，本節安裝來自 [Anthropic 官方市集](https://code.claude.com/docs/zh-TW/plugins/anthropic-marketplaces.md) 的 [`commit-commands`](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/commit-commands)，它新增了用於提交、推送和開啟拉取請求的命令。

相同的步驟安裝任何其他外掛程式：在 `commit-commands` 和 `claude-plugins-official` 出現的地方替換其名稱和其市集的名稱。如果該外掛程式來自不同的市集，請先 [新增市集](#add-a-marketplace)。

選擇您執行 Claude Code 的位置的標籤。

> [tab] Terminal
>
> 在您的專案中使用 `claude` 啟動 Claude Code，然後：
>
> **1. 使用安裝命令開啟外掛程式的詳細資訊**
>
> 使用外掛程式的名稱和市集執行 `/plugin install`。在工作階段中，此命令不會立即安裝：它在該外掛程式的詳細資訊上開啟 `/plugin` 面板，以便您可以檢閱它並先選擇範圍。
>
> ```text theme={null}
> /plugin install commit-commands@claude-plugins-official
> ```
>
> 若要瀏覽，請執行不帶外掛程式名稱的 `/plugin`：面板在 **Discover** 標籤上開啟，該標籤列出您新增的每個市集中的外掛程式，您可以輸入以搜尋，然後在外掛程式上按 **Enter** 以開啟其詳細資訊。
>
> **2. 檢閱外掛程式新增的內容**
>
> 詳細資訊窗格顯示外掛程式的描述。它也可以顯示：
>
> * **Will install**：外掛程式新增的命令、代理、技能、hooks 和 MCP 及 LSP 伺服器。
> * **Last updated**：針對 Anthropic 官方市集中的外掛程式顯示。
> * **Context cost**：對於 Anthropic 官方市集中的外掛程式，有兩個令牌估計。**Every turn** 是外掛程式新增到您傳送的每條訊息的內容，**When invoked** 是其技能和代理在 Claude 載入它們後新增的內容。當您透過命名其市集開啟外掛程式時（如步驟 1 命令所做的那樣）或從 **Marketplaces** 標籤時，估計會出現。您從 **Discover** 清單到達的詳細資訊窗格不會顯示它們。
>
> 來自本機或自訂市集的外掛程式可以改為顯示 `Components will be discovered at installation`。
>
> 外掛程式可以執行 hooks 和 MCP 伺服器，因此在安裝前請閱讀窗格。請參閱 [外掛程式安全性和信任](https://code.claude.com/docs/zh-TW/plugins/security.md)。
>
> **3. 選擇範圍**
>
> 選擇三個安裝選項之一：
>
> * **Install for you (user scope)**：您在此機器上的每個專案中都獲得外掛程式
> * **Install for all collaborators on this repository (project scope)**：它對在此儲存庫中工作的每個人都啟用
> * **Install for you, in this repo only (local scope)**：您只在此儲存庫中獲得它
>
> [選擇安裝範圍](#choose-an-install-scope) 說明每個範圍寫入哪個設定檔，以及當相同外掛程式在多個位置設定時哪個適用。
>
> 選擇範圍後，Claude Code 安裝外掛程式及其宣告的任何依賴項，然後列印安裝摘要。
>
> **4. 閱讀安裝摘要**
>
> 摘要的最後一句告訴您外掛程式在此工作階段中是否可用：
>
> * **Active now**：`Plugin is now active.` 不需要重新載入。
> * **Active, but a server needs setup**：`Plugin is now active.` 後面跟著 `Its bundled MCP server needs configuration before it can start`。外掛程式的 [bundled MCP server](https://code.claude.com/docs/zh-TW/plugins/components.md#include-a-packaged-mcpb-server) 在您設定其選項之前無法啟動。在 `/plugin` 的 **Installed** 標籤上選擇外掛程式，然後選擇 **Configure** 以設定伺服器的選項。
> * **Reload needed**：`Run /reload-plugins to apply.` 面板關閉，Claude Code 為您執行該重新載入。如果重新載入會 [使提示快取失效](https://code.claude.com/docs/zh-TW/prompt-caching.md#enabling-or-disabling-a-plugin)，它會警告並改為保留外掛程式待處理。執行 `/reload-plugins --force` 以無論如何啟動它，這會花費一個未快取的請求。
> * **Load failed**：`The plugin couldn't be loaded`。在 `/plugin` 中開啟 **Errors** 標籤以了解原因，然後請參閱 [安裝後：外掛程式無法運作](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#plugin-installed-but-not-working)。
>
> **5. 確認外掛程式有效**
>
> 輸入 `/` 並在其名稱下尋找外掛程式的 skill，形式為 `/<plugin>:<skill>`。對於 `commit-commands`，`/commit-commands:commit` 出現。另外兩個地方也列出外掛程式：
>
> * 在 `/plugin` 中開啟 **Installed** 標籤，該標籤列出具有其範圍的外掛程式。
> * 在您的 shell 中，執行 `claude plugin list`，它列印相同的清單，包含 `Version`、`Scope` 和 `Status` 行。
>
> 如果 `/commit-commands:commit` 沒有出現，請參閱 [安裝後：外掛程式無法運作](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#plugin-installed-but-not-working)。
>
> 從任何其他市集安裝需要先執行一個額外步驟：[新增市集](#add-a-marketplace)。Claude Code 在您第一次啟動互動式終端機工作階段時為您新增 Anthropic 的官方市集，這就是為什麼範例跳過該步驟。如果您在 [claude.com/marketplace](https://claude.com/marketplace) 上找到外掛程式，其 **Claude Code** 按鈕會複製其 [shell 形式](#install-from-your-shell) 中的安裝命令，`claude plugin install <name>@claude-plugins-official`。

> [tab] Desktop app
>
> 在桌面應用程式的 **Code** 標籤中的本機或 SSH 工作階段中：
>
> **1. 開啟外掛程式瀏覽器**
>
> 按一下提示詞輸入框旁的 **+** 按鈕，然後選擇 **Add plugins**。如果 **+** 選單顯示的是 **Plugins** 而非 **Add plugins**，請選擇 **Plugins**，然後選擇 **Browse plugins**。外掛程式瀏覽器開啟，顯示來自您市集的外掛程式。
>
> **2. 選擇外掛程式**
>
> 找到 `commit-commands` 並選擇它。
>
> **3. 選擇範圍**
>
> 選擇 [範圍](#choose-an-install-scope)：您的使用者帳戶、此專案或僅限本機。
>
> 若要稍後啟用、停用或解除安裝外掛程式，請參閱 [在桌面應用程式中安裝外掛程式](https://code.claude.com/docs/zh-TW/desktop.md#install-plugins)。

> [tab] VS Code
>
> 在 VS Code 中的 Claude Code 面板中：
>
> **1. 開啟 Manage plugins**
>
> 在提示框中輸入 `/plugins` 以開啟 **Manage plugins**。
>
> **2. 安裝外掛程式**
>
> 在 **Plugins** 標籤上，搜尋 `commit-commands` 並按一下 **Install**。如果標籤未列出任何外掛程式，請先在 **Marketplaces** 標籤上新增 `anthropics/claude-plugins-official`。
>
> **3. 選擇範圍**
>
> 選擇 [範圍](#choose-an-install-scope)：**Install for you**、**Install for this project** 或 **Install locally**。
>
> 您的變更會套用到開啟的工作階段，無需重新啟動。請參閱 [在 VS Code 中管理外掛程式](https://code.claude.com/docs/zh-TW/vs-code.md#manage-plugins)。

> [tab] Cloud session
>
> [雲端工作階段](https://code.claude.com/docs/zh-TW/cloud-environments.md)（包括 [claude.ai/code 上的瀏覽器](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)）沒有外掛程式瀏覽器，不會載入您在自己的機器上安裝的外掛程式或您儲存庫的 `.claude/settings.json` 開啟的外掛程式。對於您的組織透過受管設定分發的外掛程式，請參閱 [為您的組織管理外掛程式](https://code.claude.com/docs/zh-TW/plugins/org.md)。
>
> 請參閱 [您的設定中哪些部分也可在雲端工作階段中使用](https://code.claude.com/docs/zh-TW/cloud-environments.md#what-carries-over-from-your-setup) 以了解您設定的其餘部分。

### 選擇安裝範圍

外掛程式的安裝範圍決定誰獲得外掛程式以及哪個設定檔將其記錄為啟用：

* **User scope**：外掛程式在此機器上的每個專案中為您啟用。該項目進入 `~/.claude/settings.json` 中的 `enabledPlugins`。
* **Project scope**：外掛程式在此儲存庫中為每個人啟用。該項目進入 `.claude/settings.json`，您提交它。提交該項目會為您的協作者開啟外掛程式，但不會將其下載到他們的機器上，因此每個協作者也需執行一次 `claude plugin install <name>@<marketplace> --scope project`；請參閱 [在專案設定中啟用但未安裝](https://code.claude.com/docs/zh-TW/plugins/loading.md#enabled-in-project-settings-but-not-installed)。
* **Local scope**：外掛程式在此儲存庫中僅為您啟用。該項目進入 `.claude/settings.local.json`。

某些外掛程式由其作者設定為預設關閉，透過 [`defaultEnabled`](https://code.claude.com/docs/zh-TW/plugins/manifest-reference#defaultenabled) 欄位。這樣的外掛程式已安裝但保持關閉，直到您在 shell 中使用 `claude plugin enable <name>` 或從工作階段中 `/plugin` 的 **Installed** 標籤開啟它。

當相同的外掛程式在多個範圍設定時，本機設定覆蓋專案設定，專案設定覆蓋使用者設定。請參閱 [尋找外掛程式啟用的位置](https://code.claude.com/docs/zh-TW/plugins/loading.md#find-where-a-plugin-is-enabled) 以了解完整規則。

終端機、桌面應用程式的本機工作階段和一台電腦上的 VS Code 擴充功能讀取相同的設定檔，因此您在其中任何一個以使用者範圍安裝的外掛程式在其他兩個中可用。

### JetBrains、非互動式執行和 Agent SDK

您執行 Claude Code 的某些地方沒有自己的外掛程式瀏覽器：

* **JetBrains IDEs**：JetBrains 外掛程式在 IDE 的終端機中執行 Claude Code，因此在那裡使用 **Terminal** 標籤的步驟。
* **`claude -p` 和其他非互動式執行**：`/plugin` 不執行，Claude 回覆 `/plugin isn't available in this environment.` 您已安裝的外掛程式確實會載入。使用 [`claude plugin` 命令](#install-from-your-shell) 從 shell 安裝和管理它們。
* **Agent SDK**：透過 SDK 的外掛程式選項載入外掛程式。請參閱 [在 Agent SDK 中載入外掛程式](https://code.claude.com/docs/zh-TW/agent-sdk/plugins.md)。

如果 Claude Code 報告儲存庫的 `.claude/settings.json` 中啟用的外掛程式未安裝，請參閱 [在專案設定中啟用但未安裝](https://code.claude.com/docs/zh-TW/plugins/loading.md#enabled-in-project-settings-but-not-installed)。

> [!TIP]
>
> 如果您是外掛程式作者測試磁碟上的外掛程式副本，請從 shell 使用 `--plugin-dir` 啟動 Claude Code，以便為一個工作階段載入它，而不是安裝它。請參閱 [為一個工作階段載入外掛程式的旗標](https://code.claude.com/docs/zh-TW/plugins/cli-reference.md#flags-that-load-a-plugin-for-one-session)。

### 來自您 claude.ai 帳戶的外掛程式

您的 claude.ai 帳戶是外掛程式的單獨來源，與您安裝的市集並列：

* **What arrives**：您為 claude.ai 帳戶開啟的每個外掛程式，以及您的組織為其成員開啟的每個外掛程式。在終端機工作階段中，每次您在使用該帳戶登入時啟動 Claude Code 時，它們會在背景同步；在 Cowork 工作階段中，它們在工作階段啟動時下載。
* **Where you see them**：在 `/plugin` 和 `claude plugin list` 中，ID 為 `<name>@synced`。您可以在自己的範圍關閉一個，除非您的組織要求它。
* **What doesn't go the other way**：您使用 `/plugin` 或 `claude plugin install` 安裝的外掛程式保留在此機器上，不會新增到您的 claude.ai 帳戶。

有關同步時間、登入要求和關閉同步，請參閱 [從 claude.ai 同步的外掛程式](https://code.claude.com/docs/zh-TW/plugins/loading.md#synced-plugins)。

### 從您的 shell 安裝

在 shell 中執行 `claude plugin install` 以安裝外掛程式，而無需啟動 Claude Code 工作階段，例如從設定指令碼。

* **Scope**：預設為使用者範圍。傳遞 `--scope project` 或 `--scope local` 以變更它。
* **When the plugins load**：它安裝的外掛程式在您下次啟動 Claude Code 時載入，或當您在已開啟的工作階段中執行 `/reload-plugins` 時載入。
* **The marketplace on a new machine**：在尚未有人開啟互動式 Claude Code 工作階段的機器上，官方市集未註冊，因此從它安裝的指令碼在安裝前執行 `claude plugin marketplace add anthropics/claude-plugins-official`。請參閱 [從您的 shell 新增和安裝](#add-and-install-from-your-shell)。

```bash theme={null}
claude plugin install formatter@your-org --scope project
```

命令完成時列印 `Successfully installed plugin: formatter@your-org (scope: project)`。

某些外掛程式透過執行其市集命名的命令進行安裝，稱為 [`command` source](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference#command-plugin-source)。Claude Code 向您顯示該命令並要求您在執行前接受它。指令碼沒有人回答該提示，因此在那裡傳遞 `--yes` 以接受它。

有關其他 `claude plugin install` 旗標，請參閱 [plugin install](https://code.claude.com/docs/zh-TW/plugins/cli-reference.md#plugin-install)。

## 新增市集

當您想要的外掛程式不在 Anthropic 的官方市集中時，您只需要本節，例如同事發佈的外掛程式或來自 Anthropic 社群市集的外掛程式。

市集是外掛程式的目錄，Claude Code 必須知道市集才能從中安裝。您新增一次市集。之後，其外掛程式出現在 **Discover** 標籤上，並使用 `/plugin install <plugin>@<marketplace>` 在工作階段中或 `claude plugin install <plugin>@<marketplace>` 在 shell 中安裝，其中 `<marketplace>` 是市集註冊的名稱。若要在一個步驟中同時執行兩者，請參閱 [新增市集並在一個命令中安裝](#add-a-marketplace-and-install-in-one-command)。

在 Claude Code 工作階段中，執行 `/plugin marketplace add` 後跟市集的來源：GitHub 儲存庫、任何主機上的 git 儲存庫、本機目錄或檔案，或託管的 `marketplace.json`。

| Source | What you type | Example |
| :- | :- | :- |
| GitHub repository | `owner/repo`。新增 `#ref` 以固定分支或標籤。 | `/plugin marketplace add anthropics/claude-plugins-official`，或 `/plugin marketplace add your-org/plugins#v1.2.0` 以固定 `v1.2.0` 標籤 |
| Git repository on any host | 完整的複製 URL。新增 `#ref` 以固定分支或標籤。 | `/plugin marketplace add https://gitlab.example.com/your-group/your-marketplace.git#v1.0.0` |
| Local directory or file | 保存 `.claude-plugin/marketplace.json` 的目錄的相對或絕對路徑，或 JSON 檔案本身的路徑。以 `./` 或 `../` 開始相對路徑，因為 Claude Code 將裸 `name/name` 讀取為 GitHub 儲存庫。 | `/plugin marketplace add ./my-marketplace` |
| Hosted `marketplace.json` | 其 `https://` URL | `/plugin marketplace add https://example.com/marketplace.json` |

從 shell，`claude plugin marketplace add` 採用相同的來源。

> [!TIP]
>
> `/plugin market` 也可作為 `/plugin marketplace` 的較短形式。

在每個 URL 上包含 `https://` 前綴，或對 SSH 使用 `git@host:path` 形式。如果您輸入裸 `gitlab.example.com/your-group/your-marketplace.git`，Claude Code 將其讀取為 GitHub `owner/repo` 速記並拒絕它。

命令成功時，它列印 `Successfully added marketplace: <name>`，市集的外掛程式在您下次開啟 `/plugin` 時出現在 **Discover** 標籤上，無需重新載入。如果失敗，請在 [外掛程式疑難排解](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#add-a-marketplace) 中匹配錯誤訊息。

### 新增市集並在一個命令中安裝

若要從您尚未新增的市集安裝外掛程式，請在安裝命令上使用 `--marketplace` 命名市集來源，可在工作階段中或從 shell 執行。來源採用 [與 `/plugin marketplace add` 相同的形式](#add-a-marketplace)，例如 GitHub `owner/repo`、git URL 或本機路徑。單獨給出外掛程式名稱，不帶 `@marketplace` 後綴。

#### 在工作階段中新增並安裝

在 Claude Code 工作階段中執行 `/plugin install`，並提供外掛程式和來源。需要 Claude Code v2.1.275 或更新版本。在工作階段中，來源不能包含空格。

```text theme={null}
/plugin install deploy-helper --marketplace your-org/plugins
```

如果您尚未新增該市集，Claude Code 會顯示它解析的來源並要求您在新增前確認。市集新增後，外掛程式的詳細資訊開啟，您選擇 [安裝範圍](#install-a-plugin)。如果來源與您已新增的市集相符，Claude Code 會跳過確認並在該市集中開啟外掛程式的詳細資訊。

#### 從 shell 新增並安裝

在 shell 中，無需啟動工作階段，執行 `claude plugin install` 並提供外掛程式和來源。需要 Claude Code v2.1.292 或更新版本。

```bash theme={null}
claude plugin install deploy-helper --marketplace your-org/plugins
```

shell 命令會新增市集而不經過確認步驟。您已從該來源新增的市集會被重複使用。新的市集會在與 `claude plugin marketplace add` 相同的 [組織政策檢查](https://code.claude.com/docs/zh-TW/plugins/org.md#restrict-what-users-can-install) 下新增，並且即使您傳遞 `--scope project`，也會宣告在您的使用者設定中。

如果您尚未新增該市集，命令會列印 `Successfully added marketplace: <name> (declared in user settings)`，然後 [安裝外掛程式](#install-from-your-shell)。

### 新增私人市集

私人市集是您需要認證才能複製的儲存庫中的市集，在 GitHub 或任何其他 git 主機上。您使用與公開市集相同的 `/plugin marketplace add` 或 `claude plugin marketplace add` 命令新增它。Claude Code 使用機器上已有的 git 認證複製它，永遠不會提示，因此每種連接方式都有要求：

* **HTTPS**：您的 git 憑證助手適用，因此您使用 `gh auth login`、macOS Keychain 或 `git-credential-store` 設定的存取有效。Git 的提示和 askpass 程式均已停用，包括在 `GIT_ASKPASS` 中設定的程式，因此當 git 必須要求憑證時，複製會失敗而不是提示。
* **SSH**：主機必須已在您的 `known_hosts` 檔案中，金鑰必須在沒有密碼提示的情況下工作。如果您的 git 設定在 `GIT_SSH_COMMAND`、`GIT_SSH` 或您的 git 設定的 `core.sshCommand` 中命名 SSH 程式，Claude Code 會執行該程式。
* **GitHub `owner/repo` shorthand**：Claude Code 檢查您的 SSH 金鑰是否驗證到 `github.com`，如果驗證則透過 SSH 複製，如果不驗證則透過 HTTPS 複製。設定 [`CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1`](https://code.claude.com/docs/zh-TW/env-vars#variables) 以跳過該檢查並始終透過 HTTPS 複製。

當您執行 `/plugin install`、`/plugin marketplace update` 和 `claude plugin update` 時，相同的認證適用。

在 GitHub Enterprise Server 主機上，請參閱 [GHES 上的外掛程式市集](https://code.claude.com/docs/zh-TW/github-enterprise-server.md#plugin-marketplaces-on-ghes) 以了解每個操作需要的認證。

如果您的組織透過受管設定為您註冊市集，您不需要自己新增它。請參閱 [預先安裝和要求外掛程式](https://code.claude.com/docs/zh-TW/plugins/org.md#pre-install-and-require-plugins)。

### 從 claude.ai 新增市集

在 [從您的 claude.ai 帳戶同步外掛程式](https://code.claude.com/docs/zh-TW/plugins/loading.md#synced-plugins) 的終端機工作階段中，claude.ai 也可以為您列出外掛程式市集，例如您的組織的外掛程式庫和您自己的 claude.ai 上傳。您透過其名稱而不是來源新增其中之一。從 claude.ai 新增市集需要 Claude Code v2.1.273 或更新版本。

從 `/plugin` 面板或 shell 新增 claude.ai 市集：

* **Inside a session**：執行 `/plugin` 並前往 **Marketplaces** 標籤，該標籤列出來自 claude.ai 的市集。在那裡選擇一個以新增它。
* **From your shell**：執行 `claude plugin marketplace list`，它在 `From claude.ai:` 部分列印它們。然後執行 `claude plugin marketplace add` 並使用 `--claudeai` 旗標和清單中顯示的名稱。

例如，此命令新增名為 `claudeai-organization-library` 的市集：

```bash theme={null}
claude plugin marketplace add --claudeai claudeai-organization-library
```

Claude Code 在本機名稱下註冊市集，該名稱以 `claudeai-` 開頭，源自 claude.ai 列出的名稱。例如，列為「Organization library」的市集變成 `claudeai-organization-library`。透過該名稱安裝其外掛程式，例如使用 `claude plugin install <plugin>@claudeai-organization-library`。

如果您登出或登入不同的 claude.ai 組織，市集保持配置但不顯示外掛程式，您已從中安裝的外掛程式繼續載入。

`From claude.ai:` 部分也可以列出透過 claude.ai 共享的基於 git 的市集，並為每個市集列印來源。透過該來源新增它們，如 [新增市集](#add-a-marketplace) 中所示，而不是使用 `--claudeai`。

## 管理已安裝的外掛程式

`/plugin` 中的 **Installed** 標籤列出您的外掛程式，並提供啟用、停用、更新或卸載每個外掛程式的操作。在 Claude Code 工作階段中，執行 `/plugin` 並按 **Tab** 到達它，或執行 `/plugin enable`、`/plugin disable` 或 `/plugin uninstall` 以開啟面板並在那裡進行該變更。停用的外掛程式在清單底部的摺疊標題下分組。在清單上使用這些鍵：

* 輸入以按名稱或描述篩選。
* 按 **Space** 啟用或停用選定的外掛程式，按 **f** 將其加入最愛。
* 按 **Enter** 開啟外掛程式的詳細資訊。

外掛程式的詳細資訊功能表提供 **Disable plugin** 或 **Enable plugin**、**Update now** 和 **Uninstall**。採用設定的外掛程式會出現兩個額外項目，外掛程式可以同時顯示兩者：

* **Configure options**：當外掛程式的資訊清單宣告 [`userConfig` 選項](https://code.claude.com/docs/zh-TW/plugins/manifest-reference#user-configuration) 時顯示。開啟這些選項的對話框
* **Configure**：當外掛程式包含 [封裝的 MCP 伺服器](https://code.claude.com/docs/zh-TW/plugins/components.md#include-a-packaged-mcpb-server) 時顯示。設定該伺服器自己的 `user_config` 設定

標籤也可以在 **Managed** 範圍顯示外掛程式。您的組織透過 [受管設定](https://code.claude.com/docs/zh-TW/settings.md#settings-files) 安裝了這些，您無法在此啟用、停用或卸載它們。

對於您的組織在 claude.ai 上要求的同步外掛程式，請參閱 [管理從 claude.ai 同步的外掛程式](#manage-plugins-synced-from-claude-ai)。

當您關閉 `/plugin` 面板並在其中進行待處理變更時，Claude Code 為您執行 `/reload-plugins` 以套用它們。如果重新載入會 [使提示快取失效](https://code.claude.com/docs/zh-TW/prompt-caching.md#enabling-or-disabling-a-plugin)，它會警告並改為保留變更待處理。執行 `/reload-plugins --force` 以無論如何套用它們。

### 管理從 claude.ai 同步的外掛程式

`/plugin` 中的 **Installed** 標籤也列出 [從您的 claude.ai 帳戶同步的外掛程式](https://code.claude.com/docs/zh-TW/plugins/loading.md#synced-plugins)，其來源為 `synced`。同步外掛程式在 Claude Code v2.1.273 或更新版本的終端機工作階段中出現。

* **Enable or disable**：使用 **Installed** 標籤，除非您的組織將外掛程式標記為必需。
* **Remove**：在 claude.ai 上關閉外掛程式。

當 Claude Code 將新增、更新或移除的外掛程式同步到互動式工作階段時，您會看到 `Plugins changed. Run /reload-plugins to activate.` 執行 `/reload-plugins` 以在該工作階段中載入變更，或將其保留到下次啟動 Claude Code。

### 卸載專案啟用的外掛程式

當您為此儲存庫的 `.claude/settings.json` 啟用的外掛程式選擇 **Uninstall** 時，無論是從 **Installed** 標籤還是使用 `/plugin uninstall`，Claude Code 會詢問是否為您停用它或為每個人卸載它：

* **Disable for me**：按 **y**。Claude Code 在您的 `.claude/settings.local.json` 中為外掛程式寫入 `false` 並將其保留為專案安裝。
* **Uninstall for everyone**：按 **u**。Claude Code 從共享 `.claude/settings.json` 移除外掛程式。

### 查看已安裝的外掛程式新增到您工作階段的內容

在 shell 中，執行 `claude plugin details <name>` 以了解已安裝的外掛程式。`Always-on` 行是外掛程式在啟用它的每個工作階段中新增的令牌數，每個元件行顯示哪個技能或代理貢獻最多。有關完整輸出和每個數字的含義，請參閱 [測量外掛程式的成本](https://code.claude.com/docs/zh-TW/plugins/measure.md#measure-what-a-plugin-costs)。

### 尋找您不再使用的外掛程式

在 `/plugin` 的 **Installed** 標籤上，您自己安裝且最近未使用的外掛程式出現在 **Not used recently** 標題下，每個外掛程式的詳細資訊顯示 **Last used** 行。使用該標題和該行尋找仍新增啟動和內容成本的外掛程式，然後停用或卸載它們。

### 具有依賴項的外掛程式

外掛程式可以宣告它依賴的其他外掛程式。當您從市集安裝、停用或卸載這樣的外掛程式時，Claude Code 也會對這些依賴項進行操作：

* **Install**：Claude Code 也在相同範圍安裝並啟用外掛程式的宣告依賴項。成功訊息列出它們。
* **Enable**：Claude Code 也啟用已安裝但停用的外掛程式的依賴項。如果宣告的依賴項未安裝，啟用失敗，訊息告訴您先安裝它。
* **Disable**：當另一個啟用的外掛程式仍需要您命名的外掛程式時，Claude Code 拒絕並列印以正確順序停用兩者的鏈式命令。
* **Uninstall**：自動安裝的依賴項保留到您在 shell 中執行 `claude plugin prune` 為止；請參閱 [plugin prune](https://code.claude.com/docs/zh-TW/plugins/cli-reference.md#plugin-prune)。

如果您改為使用 `--plugin-dir` 載入外掛程式，請參閱 [在本機測試外掛程式及其依賴項](https://code.claude.com/docs/zh-TW/plugins/dependencies.md#test-a-plugin-and-its-dependency-locally)。

### 從 shell 管理外掛程式

您也可以在不啟動 Claude Code 工作階段的情況下管理外掛程式。在 shell 中，執行 `claude plugin install`、`enable`、`disable` 或 `uninstall` 作為普通終端機命令；它們變更 `/plugin` 面板所做的相同設定。每個都採用 `--scope` 以針對一個範圍，當您省略它時使用預設範圍：

* `enable` 和 `disable` 作用於其設定已列出外掛程式的最具體範圍。
* `install` 和 `uninstall` 作用於使用者範圍。

例如，這些命令停用並重新啟用外掛程式，然後在專案範圍卸載它：

```bash theme={null}
claude plugin disable formatter@your-org
claude plugin enable formatter@your-org
claude plugin uninstall formatter@your-org --scope project
```

## 保持外掛程式更新

當外掛程式來自的市集啟用了自動更新時，外掛程式會自動更新。工作階段啟動後，Claude Code 重新整理這些市集並更新您從中安裝的外掛程式的磁碟副本。

執行中的工作階段保持它已載入的版本。更新後，您會看到 `Plugin updated: <name> · Run /reload-plugins to apply`，下一個工作階段會自動載入新版本。

這些是每種市集類型的自動更新預設值：

* **On by default**：`claude-plugins-official` 和其他 [官方市集名稱](https://code.claude.com/docs/zh-TW/plugins/security.md#official-marketplace-names)（除了 `knowledge-work-plugins` 和 `first-party-plugins`）以及 [從 claude.ai 新增的市集](#add-from-claude-ai)。
* **Off by default**：所有其他市集，包括社群市集、第三方市集和本機開發市集。

有關自動更新何時執行、它跳過哪些外掛程式以及關閉它的環境變數，請參閱 [自動更新何時執行](https://code.claude.com/docs/zh-TW/plugins/loading.md#when-auto-update-runs)。

### 為市集開啟或關閉自動更新

在 Claude Code 工作階段中，執行 `/plugin` 並前往 **Marketplaces** 標籤。選擇市集，然後選擇 **Enable auto-update** 或 **Disable auto-update**。

### 立即更新外掛程式

若要更新單一外掛程式，請在工作階段中，在 `/plugin` 的 **Installed** 標籤上開啟該外掛程式並選擇 **Update now**，或在 shell 中執行 `claude plugin update <plugin>@<marketplace>`。

沒有可一次更新所有外掛程式的命令。若要一次更新您從某個市集安裝的外掛程式，請前往 `/plugin` 中的 **Marketplaces** 標籤，選擇該市集，然後選擇 **Update marketplace**。這會重新整理該市集的清單、更新您從中安裝的外掛程式，並回報任何留待您自行更新的外掛程式。具有 [`command` 來源](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference#command-plugin-source) 的外掛程式，或其市集項目設定了 `headersHelper` 命令的外掛程式，不會以此方式更新，因此您需要從 **Installed** 標籤上的外掛程式檢視中更新，或使用 `claude plugin update <plugin>@<marketplace>` 更新。

如果您在 shell 中執行 `claude plugin marketplace update` 而不指定名稱，它會重新整理每個市集的清單，但會讓您已安裝的外掛程式維持在目前版本。

### 從私人市集自動更新

對於私人市集，請參閱 [背景自動更新對憑證的處理](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md#what-background-auto-update-does-with-credentials) 以了解背景自動更新如何透過 SSH 和 HTTPS 驗證，以及 [外掛程式疑難排解](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#add-a-marketplace) 以了解失敗時看到的訊息。

## 管理市集

`/plugin` 中的 **Marketplaces** 標籤列出您註冊的每個市集及其來源。選擇一個以瀏覽其外掛程式、更新其清單、開啟或關閉自動更新，或移除它。

您也可以使用命令從 shell 或工作階段內列出、更新和移除市集：

| Action | In your shell | Inside a session |
| :- | :- | :- |
| List marketplaces | `claude plugin marketplace list` | `/plugin marketplace list` |
| Update a marketplace's listing | `claude plugin marketplace update <name>` | `/plugin marketplace update <name>` |
| Remove a marketplace | `claude plugin marketplace remove <name>` | `/plugin marketplace remove <name>` |

當您移除市集時，Claude Code 卸載您從中安裝的每個外掛程式，並從設定檔中移除其 `enabledPlugins` 項目。**Marketplaces** 標籤在要求您確認前命名這些外掛程式。

## 後續步驟

* [Anthropic 的市集](https://code.claude.com/docs/zh-TW/plugins/anthropic-marketplaces.md)：官方和社群市集的差異以及在哪裡瀏覽每個市集
* [外掛程式載入參考](https://code.claude.com/docs/zh-TW/plugins/loading.md)：為什麼外掛程式載入、未載入或在更新後未變更
* [外掛程式安全性和信任](https://code.claude.com/docs/zh-TW/plugins/security.md)：在從您不認識的市集安裝外掛程式前要檢閱的內容
* [外掛程式疑難排解](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md)：安裝和市集錯誤訊息及其修復
* [建立外掛程式](https://code.claude.com/docs/zh-TW/plugins/create.md)：建立您自己的外掛程式

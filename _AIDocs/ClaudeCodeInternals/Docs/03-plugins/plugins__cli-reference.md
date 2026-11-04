<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/plugins/cli-reference | lastmod: 2026-10-28 | section: Plugins / Reference -->
> 來源：https://code.claude.com/docs/zh-TW/plugins/cli-reference（官方 zh-TW，lastmod 2026-10-28）｜分類：Plugins › Reference｜EN 摘要：Reference for the claude plugin shell commands, /plugin and /reload-plugins in a session, and the flags that load a plugin for one session.

# Plugin 命令參考

> claude plugin shell 命令的參考，包括在工作階段中的 /plugin 和 /reload-plugins，以及在單一工作階段中載入 plugin 的旗標。

您可以從 shell 或指令碼執行 plugin 命令，方式為 `claude plugin`，或在 Claude Code 工作階段內執行 `/plugin` 和 `/reload-plugins`。本參考提供每個命令的旗標、預設值、輸出和結束代碼，以及在單一工作階段中載入 plugin 的兩個旗標。

下列表格列出每個子命令的常用選項，而非所有選項。在 shell 中執行 `claude plugin --help` 以查看您的版本有哪些子命令，並執行 `claude plugin <subcommand> --help` 以查看子命令的完整選項清單。

> [!NOTE]
>
> 這些情況涵蓋在其他頁面上：
>
> * **安裝和管理步驟，以及 `/plugin` 執行的位置**：請參閱 [安裝和管理 plugins](https://code.claude.com/docs/zh-TW/plugins/install.md)
> * **命令在磁碟上變更的內容以及哪個範圍優先**：請參閱 [Plugin 載入參考](https://code.claude.com/docs/zh-TW/plugins/loading.md)
> * **錯誤訊息的含義**：請參閱 [Troubleshoot plugins](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md)

## claude plugin 命令

從 shell 或指令碼執行 `claude plugin <subcommand>`，在 Claude Code 工作階段外。這些子命令安裝和管理 plugins，而不開啟 [`/plugin`](#plugin-in-a-session) 面板。

`claude plugins` 是 `claude plugin` 的別名。

每個子命令共享這些結束代碼、plugin 引數和範圍值：

* **結束代碼**：成功時為 `0`，失敗時為 `1`。`validate` 為非預期錯誤新增結束 `2`，`eval` 新增 [其部分](#plugin-eval) 中列出的代碼。
* **Plugin 引數**：`<plugin>` 引數是 plugin `name` 或 `name@marketplace`。當兩個市集提供相同名稱時，使用限定形式。`configure` 僅接受限定形式。
* **範圍**：`--scope` 接受 `user`、`project` 或 `local`，並命名命令寫入的設定檔。`update` 也接受 `managed`。

### plugin init

在 `~/.claude/skills/<name>/` 建立新 plugin 的架構。除非您的管理員已 [封鎖 skills-directory plugins](https://code.claude.com/docs/zh-TW/plugins/loading.md#skills-directory-plugins-blocked-by-managed-settings)，否則它會在您的下一個工作階段中以 `<name>@skills-dir` 的形式載入，無需安裝步驟。

`new` 是 `init` 的別名。

對於以此命令開始的建立、測試和編輯工作流程，請參閱 [建立 plugin](https://code.claude.com/docs/zh-TW/plugins/create.md)。

```bash theme={null}
claude plugin init <name> [options]
```

`<name>` 成為 `~/.claude/skills/` 下的目錄名稱和 plugin 的 manifest 中的 `name`。

該命令沒有另一個位置的旗標。若要改為在專案內建立架構，請參閱 [建立 plugin](https://code.claude.com/docs/zh-TW/plugins/create.md)。

| 旗標 | 說明 |
| :- | :- |
| `--description <text>` | Manifest 說明 |
| `--author <name>` | 作者名稱。預設為 `git config user.name` |
| `--author-email <email>` | 作者電子郵件。預設為 `git config user.email` |
| `--with <components...>` | 也為 `skills`、`agents`、`hooks`、`mcp`、`lsp`、`output-style` 或 `channel` 建立起始檔案的架構 |
| `-f, --force` | 覆寫目標處的現有 `.claude-plugin/` |

使用起始 skill 和 hook 檔案建立 plugin 的架構：

```bash theme={null}
claude plugin init my-helper --with skills hooks
```

Claude Code 驗證其寫入的內容，並列印 `Created plugin "my-helper" at ~/.claude/skills/my-helper`，後面跟著它載入的 id 和關閉它的 `claude plugin disable` 命令。

當 Claude Code 無法安全地建立架構時，它會結束 `1` 而不寫入，訊息會命名原因。這些是常見原因：

* 未知的 `--with` 值
* 目標處現有的架構，沒有 `--force`
* 受管的市集允許清單未包含 `skills-dir` 來源，或封鎖清單列出了它。訊息為 [`Plugins from ~/.claude/skills/ are blocked by your organization's managed settings`](https://code.claude.com/docs/zh-TW/plugins/troubleshooting#plugins-from-claude-skills-are-blocked-by-your-organizations-managed-s)。

### plugin install

從您已新增的市集安裝 plugin。`i` 是 `install` 的別名。

```bash theme={null}
claude plugin install <plugin> [options]
```

大多數 plugins 無需提示即可安裝。對於其市集項目 [執行命令以安裝它](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md) 或 [為其下載設定 `headersHelper`](https://code.claude.com/docs/zh-TW/plugins/host-marketplace#how-users-accept-a-headershelper-command) 的 plugin，Claude Code 首先列印命令並詢問 `Run this command now? [y/N]`。

| 旗標 | 說明 |
| :- | :- |
| `-s, --scope <scope>` | 安裝範圍：`user`、`project` 或 `local`。預設為 `user` |
| `--config <key=value>` | 設定 plugin 的 manifest 宣告的 [`userConfig`](https://code.claude.com/docs/zh-TW/plugins/manifest-reference) 選項。為每個選項重複旗標。寫成 `<server>.<key>` 的金鑰改為設定 [內附的 MCP 伺服器](https://code.claude.com/docs/zh-TW/plugins/components.md#include-a-packaged-mcpb-server) 在其自己的 `user_config` 中宣告的設定，用於 plugin 內附帶的 bundle 檔案。`<server>.<key>` 形式需要 Claude Code v2.1.285 或更新版本 |
| `-y, --yes` | 接受顯示的安裝命令，無需 `Run this command now?` 提示。當命令在 Claude Code 工作階段內執行時（例如從 Bash 工具或 hook）被忽略。需要 Claude Code v2.1.229 或更新版本 |
| `--accept-command <sha256>` | 接受顯示的安裝命令，其 `sha256` 先前的 [`--json` 執行](#plugin-json-result) 在 `shownCommand` 中報告，代替 `-y`。無法與 `-y` 結合。請參閱 [接受顯示的安裝命令](#accept-a-displayed-install-command)。需要 Claude Code v2.1.271 或更新版本 |
| `--json` | 將結果列印為 stdout 最後一行的一個 JSON 物件，而不是人類可讀的訊息，供指令碼使用。請參閱 [JSON 結果格式](#plugin-json-result)。需要 Claude Code v2.1.268 或更新版本 |
| `--marketplace <source>` | 從位於 `<source>` 的市集安裝以裸名稱給出的 `<plugin>`，如果您尚未新增該市集，會先新增它。請參閱 [在一個命令中新增市集並安裝](https://code.claude.com/docs/zh-TW/plugins/install.md#add-a-marketplace-and-install-in-one-command)。需要 Claude Code v2.1.292 或更新版本 |

在您的 shell 中執行 `claude plugin install --help`，查看您的版本支援的每個選項。

從您自己的終端機傳遞 `-y` 以接受顯示的命令，無需提示。以下是沒有 TTY 和 Claude 執行命令時發生的情況：

* **stdin 或 stdout 不是 TTY，且您既不傳遞 `-y` 也不傳遞 `--accept-command`**：安裝被拒絕。輸出說命令只是顯示，結束代碼為 `1`
* **Claude 透過其 Bash 工具執行命令**：`-y` 被忽略。改為從您自己的終端機執行命令

為複製專案的每個人安裝 plugin：

```bash theme={null}
claude plugin install formatter@my-marketplace --scope project
```

Claude Code 列印 `Successfully installed plugin: formatter@my-marketplace (scope: project)`。當沒有新安裝時，輸出說明原因：

* **已在該範圍安裝**：輸出為 `Plugin "formatter@my-marketplace" is already installed (scope: project)`，結束代碼為 `0`
* **您拒絕命令來源提示**：輸出為 `Aborted.`，結束代碼為 `1`
* **您拒絕 `headersHelper` 提示，或無法在沒有 TTY 的情況下確認**：輸出為 `Aborted — the command was not run.`，結束代碼為 `1`

#### JSON 結果格式

當您將 `--json` 傳遞給 `plugin install` 時，stdout 的最後一行是一個 JSON 物件。只解析該行，因為 Claude Code 在其前面列印市集宣告的任何命令。

三個欄位始終存在：

* `command`：執行的子命令，例如 `install`
* `outcome`：`ok` 或 `failed`
* `message`：結果的人類可讀說明

其他欄位（例如 `pluginId`、`scope` 和 `failureCode`）僅在適用時出現。

`plugin uninstall`、`plugin update`、`plugin enable` 和 `plugin disable` 上的 `--json` 選項會列印相同的物件，並帶有該子命令自己的欄位。

使用錯誤（例如無效的 `--scope`）不列印結果行，結束 `1`，stderr 上有原因。

#### 市集命令的 JSON 結果

在 `plugin marketplace add`、`plugin marketplace remove` 和 `plugin marketplace update` 上，`--json` 會在 stdout 的最後一行列印一個 JSON 物件，其中包含 `command`、`outcome` 和 `message` 欄位。以下是 `claude plugin marketplace remove your-marketplace --json` 的結果：

```json theme={null}
{"command":"marketplace-remove","outcome":"ok","marketplace":"your-marketplace","message":"Successfully removed marketplace: your-marketplace"}
```

`command` 值為 `marketplace-add`、`marketplace-remove` 或 `marketplace-update`。以下欄位僅在適用時出現：

* `marketplace`：命令所作用的市集名稱
* `failureCode`：說明命令失敗原因的代碼，例如 `invalid_source`

當引數為 [保留名稱](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#reserved-names) `anthropic-plugin-directory` 時，`plugin marketplace add` 和 `plugin marketplace remove` 可能不列印結果行，因此對於該名稱，請檢查結束代碼。

#### 接受顯示的安裝命令

當 `--json` 執行顯示市集宣告的命令且不執行它時，`failed` 結果也會帶有 `shownCommand` 物件。其欄位包括顯示的命令、它所屬的 plugin 和命令的 `sha256`。

若要接受完全相同的命令，從您自己的終端機使用該 `sha256` 作為 `--accept-command` 重新執行，因為旗標在 Claude Code 工作階段內無效。需要 Claude Code v2.1.271 或更新版本。

`sha256` 計為完全相同的命令、plugin 和市集目錄的接受。如果自命令顯示以來其中任何一個已變更，Claude Code 不接受 `sha256` 並再次顯示命令。執行自己的市集重新整理擷取的變更也計為此類變更。

如果 `shownCommand.acceptCommandMatched` 為 `false`，您傳遞的 `sha256` 與現在顯示的命令不符。在使用其 `sha256` 重新執行之前，檢查該命令。

### plugin uninstall

從一個範圍移除已安裝的 plugin。`remove` 和 `rm` 是 `uninstall` 的別名。

```bash theme={null}
claude plugin uninstall <plugin> [options]
```

| 旗標 | 說明 |
| :- | :- |
| `-s, --scope <scope>` | 從範圍卸載：`user`、`project` 或 `local`。預設為 `user` |
| `--keep-data` | 保留 plugin 的持久資料目錄 `~/.claude/plugins/data/<id>/` |
| `--prune` | 也移除沒有剩餘 plugin 需要的自動安裝 [相依套件](https://code.claude.com/docs/zh-TW/plugins/dependencies.md) |
| `-y, --yes` | 跳過 `--prune` 確認提示。當 stdin 或 stdout 不是 TTY 時，需要與 `--prune` 一起使用 |
| `--json` | 將結果列印為 stdout 最後一行的一個 JSON 物件，格式與 [`plugin install --json`](#plugin-json-result) 相同。無法與 `--prune` 結合。需要 Claude Code v2.1.268 或更新版本 |

從專案範圍卸載 plugin：

```bash theme={null}
claude plugin uninstall formatter@my-marketplace --scope project
```

Claude Code 列印 `Successfully uninstalled plugin: formatter (scope: project)`。當 plugin 未在該範圍安裝時，命令列印以 `Failed to uninstall plugin "formatter@my-marketplace":` 開頭的行，並結束 `1`。

如果失敗行繼續顯示 `"formatter" was not uninstalled:` 並命名設定檔，Claude Code 無法確認該範圍的設定不再開啟 plugin，因此 plugin 保持安裝並保留其保存的所有內容。使用 `--json`，結果帶有 `failureCode: "settings_still_on"`。此設定檢查需要 Claude Code v2.1.282 或更新版本。

#### 卸載刪除和保留的內容

當您從最後一個安裝 plugin 的範圍卸載 plugin 時，Claude Code 也會刪除 plugin 的儲存 [選項和機密](https://code.claude.com/docs/zh-TW/plugins/manifest-reference.md#user-configuration) 及其資料目錄 `~/.claude/plugins/data/<id>/`。有三個例外：

* 使用 `--keep-data`，資料目錄保持
* 當另一個已安裝的 plugin 使用相同資料夾時，例如其 ID 僅在字母大小寫上與此不同的 plugin，資料目錄保持
* 當 Claude Code 無法在從該範圍移除 plugin 後讀回已安裝 plugins 的列表時，選項、機密和資料目錄全部保持，因為 plugin 可能仍在另一個範圍安裝。卸載仍然成功。訊息列出保留的內容及其刪除方式，使用 `--json` 結果帶有 `savedKept: "install_records_unreadable"`

使用 `--json`，`keptData` 報告目錄是否保持，`/plugin` 在保持時顯示 `· data preserved`。對於在沒有 `--keep-data` 的情況下保持的目錄，此報告需要 Claude Code v2.1.281 或更新版本。`savedKept` 欄位需要 Claude Code v2.1.282 或更新版本。

### plugin enable

啟用已停用的 plugin。對於 [從 claude.ai 同步的 plugin](https://code.claude.com/docs/zh-TW/plugins/loading.md#synced-plugins)，將 `<name>@synced` 作為 plugin 傳遞。

```bash theme={null}
claude plugin enable <plugin> [options]
```

| 旗標 | 說明 |
| :- | :- |
| `-s, --scope <scope>` | 啟用的範圍：`user`、`project` 或 `local`。省略時自動偵測 |
| `--json` | 將結果列印為 stdout 最後一行的一個 JSON 物件，格式與 [`plugin install --json`](#plugin-json-result) 相同。需要 Claude Code v2.1.268 或更新版本 |

不使用 `--scope`，命令按本地、專案、使用者的順序檢查您的設定檔，並使用第一個提及 plugin 的範圍。

如果您傳遞 plugin 未宣告的 `--scope`，命令要麼寫入覆寫，要麼失敗：

* **[優先於](https://code.claude.com/docs/zh-TW/plugins/loading.md) 宣告範圍的範圍**：Claude Code 在您傳遞的範圍寫入覆寫。例如，`claude plugin disable formatter --scope local` 為您單獨關閉專案啟用的 plugin
* **任何其他範圍**：命令失敗，訊息為 `Plugin "formatter" is installed at project scope, not user. Use --scope project or omit --scope to auto-detect.`

如果 plugin 已在解析的範圍啟用，命令列印 `Plugin "formatter" is already enabled` 並結束 `1`。使用 `--json`，結果有 `"failureCode": "already_in_goal_state"` 和 `"alreadyInGoalState": true`，因此指令碼可以將該情況視為成功。

當 plugin 宣告 [相依套件](https://code.claude.com/docs/zh-TW/plugins/dependencies.md) 時，Claude Code 也啟用它們。命令在這些情況下失敗：

* **相依套件未安裝**：啟用失敗並列印每個遺漏相依套件的 `claude plugin install` 命令
* **相依套件被您組織的 plugin 原則阻止**：啟用失敗並命名被阻止的相依套件
* **相依套件在優先於目標範圍的範圍設定為 `false`**：啟用失敗。在該範圍啟用相依套件，或傳遞 `--scope` 以在那裡寫入

在宣告它的任何地方重新啟用 plugin：

```bash theme={null}
claude plugin enable formatter
```

Claude Code 列印 `Successfully enabled plugin: formatter (scope: project)`，命名它偵測到的範圍。

### plugin disable

停用 plugin 而不卸載它。對於 [從 claude.ai 同步的 plugin](https://code.claude.com/docs/zh-TW/plugins/loading.md#synced-plugins)，將 `<name>@synced` 作為 plugin 傳遞。

```bash theme={null}
claude plugin disable [plugin] [options]
```

| 旗標 | 說明 |
| :- | :- |
| `-a, --all` | 停用每個啟用的 plugin。無法與 plugin 名稱或 `--scope` 結合 |
| `-s, --scope <scope>` | 停用的範圍：`user`、`project` 或 `local`。省略時自動偵測 |
| `--json` | 將結果列印為 stdout 最後一行的一個 JSON 物件，格式與 [`plugin install --json`](#plugin-json-result) 相同。需要 Claude Code v2.1.268 或更新版本 |

不使用 `--scope`，範圍以與 [`plugin enable`](#plugin-enable) 相同的本地、專案、使用者順序自動偵測。

如果您既不傳遞 plugin 名稱也不傳遞 `--all`，Claude Code 列印 `Please specify a plugin name or use --all to disable all plugins` 並結束 `1`。停用已停用的 plugin 列印 `Plugin "formatter" is already disabled` 並結束 `1`，如 [`plugin enable`](#plugin-enable) 對已啟用 plugin 所做的那樣。

命令對仍然需要的 plugin 失敗：

* **另一個啟用的 plugin [相依於](https://code.claude.com/docs/zh-TW/plugins/dependencies.md) 它**：命令失敗並命名要先停用的相依項
* **您的組織要求它作為同步 plugin**：命令失敗且不保存任何內容

停用一個 plugin：

```bash theme={null}
claude plugin disable formatter
```

Claude Code 列印 `Successfully disabled plugin: formatter (scope: project)`。

### plugin update

將 plugin 更新到其市集提供的最新版本。新版本在您的下一個工作階段中載入，或在執行中的工作階段中執行 `/reload-plugins` 後載入。

```bash theme={null}
claude plugin update <plugin> [options]
```

| 旗標 | 說明 |
| :- | :- |
| `-s, --scope <scope>` | 更新的範圍：`user`、`project`、`local` 或 `managed`。省略時自動偵測 |
| `-y, --yes` | 接受來自 [command-source](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md) plugin 的已變更安裝命令，無需提示。當 stdin 或 stdout 不是 TTY 時需要，除非您傳遞 `--accept-command`。需要 Claude Code v2.1.229 或更新版本 |
| `--accept-command <sha256>` | 接受市集宣告的命令，其 `sha256` 先前的 [`--json` 執行](#plugin-json-result) 在 `shownCommand` 中報告，代替 `-y`。無法與 `-y` 結合。需要 Claude Code v2.1.271 或更新版本 |
| `--json` | 將結果列印為 stdout 最後一行的一個 JSON 物件，格式與 [`plugin install --json`](#plugin-json-result) 相同。需要 Claude Code v2.1.268 或更新版本 |

更新 plugin：

```bash theme={null}
claude plugin update formatter@my-marketplace
```

Claude Code 列印 `Checking for updates for plugin "formatter@my-marketplace"…`，然後是結果。當沒有更新時，它列印 `formatter is already at the latest version (1.0.0).` 並結束 `0`，除非它 [重試 plugin 的相依套件安裝](#retry-an-unfinished-dependency-install) 且該安裝失敗。

#### 命令更新哪個範圍

如果您省略 `--scope`，命令會在您目前專案安裝 plugin 的最具體範圍更新它，檢查本地、專案、使用者，然後受管。

在 v2.1.281 之前，命令在您省略 `--scope` 時使用 `user`，因此更新僅在專案或本地範圍安裝的 plugin 失敗，訊息為 `Plugin "<name>" is not installed at scope user`。在這些版本上，傳遞 `--scope`。

`managed` 是您可以更新但不能安裝的唯一範圍。對於管理員安裝的 plugins，請參閱 [為您的組織管理 plugins](https://code.claude.com/docs/zh-TW/plugins/org.md)。

#### 依裸名稱更新

您可以傳遞裸 plugin 名稱，命令會根據您安裝的 plugins 進行比對。當來自不同市集的已安裝 plugins 共享名稱時，命令拒絕更新並列出要執行的限定 `plugin-name@marketplace-name` 命令。按裸名稱更新需要 Claude Code v2.1.246 或更新版本。

#### 重試未完成的相依套件安裝

當 plugin 已是其最新版本時，命令也可以在其快取副本中重試未完成的相依套件安裝。關於該重試會執行或被略過的情況，請參閱 [它列出的套件未安裝](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#the-packages-it-lists-are-not-installed)。如果重試失敗，輸出為 `Failed to update plugin "formatter@my-marketplace"` 加上原因，結束代碼為 `1`。在 v2.1.287 之前，命令會回報 plugin 已是最新版本，而不重試安裝。

### plugin list

列出已安裝的 plugins，包括其版本、範圍和狀態。

```bash theme={null}
claude plugin list [options]
```

| 旗標 | 說明 |
| :- | :- |
| `--json` | 將列表列印為 JSON |
| `--available` | 也列出您的市集提供但您未安裝的 plugins。沒有 `--json` 時無效 |
| `--data-size [plugin]` | 測量每個已安裝 plugin 的 [保存的資料目錄](#what-an-uninstall-deletes-and-keeps)，或僅測量命名 plugin 的，以 `name@marketplace` 形式給出。沒有 `--json` 時無效。如果名稱沒有安裝記錄，命令列印 `--data-size names a plugin that is not installed` 並結束 `1`，而不是列印列表。需要 Claude Code v2.1.285 或更新版本 |

Claude Code 按每個 plugin 的載入方式對人類可讀的輸出進行分組：

* **`Installed plugins:`**：您從市集安裝的 plugins
* **`Session-only plugins (--plugin-dir / --plugin-url):`**：由同一命令中的這些旗標載入的 plugins，如 `claude --plugin-dir ./my-plugin plugin list`
* **`Skills-directory plugins (.claude/skills/*):`**：Claude Code 在 skills 目錄中找到的 plugins
* **`Synced from claude.ai`**：[從您的 claude.ai 帳戶同步的 plugins](https://code.claude.com/docs/zh-TW/plugins/loading.md#synced-plugins)

當任何群組中都沒有任何內容時，Claude Code 列印 ``No plugins installed. Use `claude plugin install` to install a plugin.``

#### JSON 輸出

使用 `--json`，Claude Code 列印一個陣列，每個安裝一個物件。每個物件帶有下面的欄位。`id`、`version`、`scope`、`enabled` 和 `installPath` 始終存在，其他欄位僅在適用時出現。

| 欄位 | 類型 | 說明 |
| :- | :- | :- |
| `id` | string | 安裝為 `name@marketplace`，工作階段專用 plugins 為 `name@inline`，skills-directory plugins 為 `name@skills-dir`，從 claude.ai 同步的 plugins 為 `name@synced` |
| `version` | string | 對於市集安裝，[Claude Code 在安裝時計算的](https://code.claude.com/docs/zh-TW/plugins/loading.md#versions-and-updates) 版本。對於工作階段專用、skills-directory 或同步 plugin，manifest 的 `version`，或未宣告時為 `unknown` |
| `scope` | string | 安裝為 `user`、`project`、`local` 或 `managed`；skills-directory plugins 為 `user` 或 `project`；工作階段專用 plugins 為 `session`；從 claude.ai 同步的 plugins 為 `synced` |
| `enabled` | boolean | plugin 在您的合併設定中是否啟用 |
| `installPath` | string | plugin 載入的目錄，但工作階段從其市集資料夾 [就地載入](https://code.claude.com/docs/zh-TW/plugins/loading.md#in-place-and-copied-plugins) 的 plugin 除外 |
| `readFromFolder` | string | 對於工作階段從其市集資料夾 [就地載入](https://code.claude.com/docs/zh-TW/plugins/loading.md#in-place-and-copied-plugins) 的 plugin，該資料夾內 plugin 的來源目錄。需要 Claude Code v2.1.289 或更新版本 |
| `folderVersion` | string | 搭配 `readFromFolder`，Claude Code 從該資料夾載入時 plugin 的 `version`，可能與上方的 `version` 欄位不同。當 plugin 未載入或未宣告版本時不存在。需要 Claude Code v2.1.289 或更新版本 |
| `installedAt` | string | 安裝的 ISO 時間戳。僅市集安裝 |
| `lastUpdated` | string | 上次更新的 ISO 時間戳。僅市集安裝 |
| `projectPath` | string | 安裝所屬的專案。僅 `project` 和 `local` 範圍 |
| `mcpServers` | object | plugin 的 MCP 伺服器定義，當市集安裝的 plugin 有任何時 |
| `errors` | array of strings | 載入錯誤，當 plugin 無法載入時 |
| `notes` | array of strings | 不屬於載入錯誤的警告，例如編寫問題或 [未安裝的套件](https://code.claude.com/docs/zh-TW/plugins/loading.md#when-the-dependency-install-fails-or-is-skipped) |
| `errorDetails` | array of objects | 每個 `errors` 項目一個物件，給出其診斷 `type` 和它引用的名稱，例如 plugin、市集、伺服器或檔案。需要 Claude Code v2.1.268 或更新版本 |
| `noteDetails` | array of objects | 每個 `notes` 項目的相同詳細物件。需要 Claude Code v2.1.268 或更新版本 |
| `hasUserConfig` | boolean | 當 plugin 已載入且其 manifest 宣告 [`userConfig` 選項](https://code.claude.com/docs/zh-TW/plugins/manifest-reference#user-configuration) 時存在且為 `true`。對於無法載入的 plugin 不存在，無論其 manifest 宣告什麼。保存的值永遠不包括。需要 Claude Code v2.1.285 或更新版本 |
| `projectEnabled` | boolean | 專案的共享 `.claude/settings.json` 是否開啟 plugin。僅市集安裝。需要 Claude Code v2.1.285 或更新版本 |
| `dataDirSize` | object | 使用 `--data-size`，plugin 的 [保存的資料目錄](#what-an-uninstall-deletes-and-keeps) 的大小為 `bytes` 和 `human`；當目錄遺漏或空白時不存在。僅市集安裝。需要 Claude Code v2.1.285 或更新版本 |
| `dataDirUnreadable` | boolean | 使用 `--data-size`，當保存的資料目錄存在但無法測量時為 `true`。僅市集安裝。需要 Claude Code v2.1.285 或更新版本 |

使用 `--json --available`，Claude Code 列印一個物件而不是陣列。其 `installed` 欄位保存已安裝 plugin 物件的陣列，其 `available` 欄位保存每個未安裝市集 plugin 的一個物件，欄位如下。

| 欄位 | 類型 | 說明 |
| :- | :- | :- |
| `pluginId` | string | `name@marketplace` |
| `name` | string | plugin 在市集中的名稱 |
| `marketplaceName` | string | 提供它的市集 |
| `source` | string or object | 市集項目的 [source](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md)：相對路徑為字串，否則為物件 |
| `description` | string | 項目的說明，當它有時 |
| `version` | string | 項目的版本，當它宣告時 |
| `installCount` | number | 安裝計數，當 Claude Code 有 plugin 的計數時 |

### plugin details

顯示 plugin 的元件清單及其預計的 token 成本。

plugin 必須已載入：已安裝、在 skills 目錄中找到，或在同一命令中使用 `--plugin-dir` 或 `--plugin-url` 傳遞。`<name>` 是 plugin `name` 或 `name@marketplace`。

```bash theme={null}
claude plugin details <name>
```

命令除了 `--help` 外不接受任何旗標。

顯示已安裝 plugin 的貢獻：

```bash theme={null}
claude plugin details formatter
```

Claude Code 列印 plugin 的名稱、版本、說明和來源，然後是這些部分：

* **`Component inventory`**：plugin 的 skills、agents、hooks、MCP 伺服器和 LSP 伺服器
* **`Projected token cost`**：plugin 添加到每個工作階段的始終開啟 tokens
* **`Per-component (rounded)`**：每個 skill、agent 和命令的始終開啟和按調用估計。當 plugin 沒有時省略

對於兩個成本數字的含義，請參閱 [測量 plugin 成本和使用](https://code.claude.com/docs/zh-TW/plugins/measure.md)。

對於未載入的 plugin，Claude Code 列印此訊息並結束 `1`：

```text theme={null}
Plugin "formatter" not found. Run `claude plugin list` to see installed plugins, or pass --plugin-dir <path> to load one from disk.
```

以 `@builtin` 結尾的 ID 指的是 [Claude Code 內建的 plugins](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md#mods-built-into-claude-code) 之一。如果您傳遞此類 ID 而 Claude Code 找不到該 plugin，訊息會改為：

```text theme={null}
Plugin "<name>@builtin" not found. Built-in plugins don't appear in `claude plugin list`. To see the ones available in a session, run /plugin in Claude Code and open the Installed tab.
```

### plugin configure

顯示已安裝 plugin 的 [`userConfig`](https://code.claude.com/docs/zh-TW/plugins/manifest-reference#user-configuration) 選項及其設定的選項，或儲存在 stdin 上傳入的值。需要 Claude Code v2.1.285 或更新版本。

```bash theme={null}
claude plugin configure <plugin>
```

| 旗標 | 說明 |
| :- | :- |
| `--values-stdin` | 從 stdin 讀取選項值作為單行字串的 JSON 物件並儲存它們。您遺漏的選項保留其儲存的值 |
| `--json` | 將結果列印為 stdout 上的一個 JSON 物件。不使用 `--values-stdin`，物件帶有選項的 `schema` 和 `choices`、其起始 `inputs` 以及 `configured` 和 `unconfigured` 選項名稱。使用 `--values-stdin`，它帶有 `saved` 選項名稱，以及當它們可以被讀回時，`unconfigured` 選項名稱 |

不使用旗標，命令列出每個選項，最多三個標籤：`required` 或 `optional`，然後 `sensitive` 用於 manifest 宣告為敏感的選項，然後 `set` 或 `not set`。它不列印任何儲存的值。使用 `--json`，輸出包括不敏感選項的儲存值，永遠不包括敏感選項的文字。

若要儲存值，將它們寫入檔案作為將選項金鑰對應到字串值的 JSON 物件，然後在 stdin 上傳遞檔案。將 `formatter@my-marketplace` 替換為您自己的 plugin 的 id，如 `claude plugin list` 所示。此範例從包含 `{"api_url": "https://example.com"}` 的檔案 `values.json` 設定一個名為 `api_url` 的選項：

```bash theme={null}
claude plugin configure formatter@my-marketplace --values-stdin < values.json
```

Claude Code 根據選項的宣告類型驗證每個值，並列印 `Configuration saved. Restart Claude Code to apply it.` 如果您傳遞 manifest 未宣告的金鑰，或驗證失敗的值，命令不儲存任何內容，列印 `Failed to save configuration:` 加上原因，並結束 `1`。使用 `--json`，被拒絕的值也列印 stdout 上的物件，其 `refused` 欄位帶有 `message`，以及當一個選項有問題時，其 `option` 金鑰。

傳遞 plugin 的完整 `name@marketplace` id，如 `claude plugin list` 所示。`configure` 不接受裸 `name`。當沒有已載入的 plugin 有該 id 時，命令列印 `No installed plugin has the id "<plugin>".` 並結束 `1`。

對於內附的 MCP 伺服器的設定，請參閱 [`plugin install --config`](#plugin-install) 或 `/plugin` 中的 **Configure** 項目。

### plugin prune

移除沒有已安裝的 plugin 再需要的自動安裝 [相依套件](https://code.claude.com/docs/zh-TW/plugins/dependencies.md)。命令永遠不會移除您自己安裝的 plugin。`autoremove` 是 `prune` 的別名。

```bash theme={null}
claude plugin prune [options]
```

| 旗標 | 說明 |
| :- | :- |
| `-s, --scope <scope>` | 修剪的範圍：`user`、`project` 或 `local`。預設為 `user` |
| `--dry-run` | 列出將移除的內容而不移除它 |
| `-y, --yes` | 跳過確認提示。當 stdin 或 stdout 不是 TTY 時需要 |

預覽修剪將移除的內容：

```bash theme={null}
claude plugin prune --dry-run
```

Claude Code 列出孤立的相依套件並以 `(dry run — nothing removed)` 結尾。沒有要移除的內容時，它列印以 `Nothing to prune` 開頭的行。

不使用 `--dry-run`，命令僅在您在提示處確認或傳遞 `-y` 後移除孤立的相依套件。

無論您在提示處的答案如何，結束代碼都是 `0`。

`prune` 的作用取決於是否附加了終端機以及您是否傳遞了 `-y`：

| 終端機和旗標 | 發生的情況 |
| :- | :- |
| 互動式終端機，無 `-y` | 列出孤立的相依套件並詢問 `Remove? [y/N]` |
| 任何終端機，`-y` | 移除它們並列印 `Removed N auto-installed plugins: <names>` |
| 非 TTY stdin 或 stdout，無 `-y` | 列印列表並 ``Not a TTY — run `claude plugin prune -y` to remove.``，不移除任何內容 |

### plugin eval

執行 plugin 的 [eval cases](https://code.claude.com/docs/zh-TW/plugin-evals.md) 並報告評分結果。需要 Claude Code v2.1.269 或更新版本。

每個案例是一個提示詞加上評分者。Claude Code 在隔離的工作階段中執行它多次，僅載入目標 plugin，預設情況下也不載入 plugin 執行，以便報告顯示差異。

請參閱 [使用 evals 測試 plugins](https://code.claude.com/docs/zh-TW/plugin-evals.md) 以了解案例格式、評分者、結果和 CI 使用。

```bash theme={null}
claude plugin eval [target] [options]
```

可選的 `target` 預設為目前目錄，並採用以下任何形式：

* plugin 目錄
* 單個 `prompt.md` 或 `case.yaml` 檔案
* 已安裝的 plugin，如 `name` 或 `name@marketplace`
* `name@skills-dir`

將目標放在 `--tag`、`--allow-tools` 和 `--json` 之前。這些選項中的每一個都將其後面的單詞作為其值，因此在其中一個之後寫入的目標被讀作標籤、工具名稱或 JSON 輸出路徑，而不是目標。

此表列出大多數執行使用的選項。執行 `claude plugin eval --help` 以獲得完整集合，包括 `--case`、`--tag`、`--output-dir`、`--report`、`--allow-real-servers`、`--keep-temp` 和 `--verbose`。

| 選項 | 說明 | 預設 |
| :- | :- | :- |
| `--runs <n>` | 每個 [arm](https://code.claude.com/docs/zh-TW/plugin-evals.md#compare-against-a-no-plugin-baseline) 中每個案例的執行 | 每個案例的 `runs`，否則 3 |
| `-j, --concurrency <n>` | 同時執行的 agent 工作階段，1 到 8。它們共享您的速率限制 | `1` |
| `--model <model>` | 測試中的 agent 的模型 | 每個案例的 `model`，否則 `ANTHROPIC_MODEL`（如果設定），否則 Claude Code 的預設值 |
| `--judge-model <model>` | `llm` 和 `baseline` 評分者的模型 | [背景任務](https://code.claude.com/docs/zh-TW/plugin-evals.md#grade-the-result) 使用的模型 |
| `--ablation <mode>` | `none` 或 `with-without`。請參閱 [與無 plugin 基線比較評分](https://code.claude.com/docs/zh-TW/plugin-evals.md#compare-against-a-no-plugin-baseline) | 依案例決定，如該節所述 |
| `--threshold <0..1>` | 如果任何案例評分低於此，結束 1 | `1.0` |
| `--max-cost-usd <usd>` | 一旦支出達到此值，停止下一次執行，結束 2，並報告部分結果 | 無限制 |
| `--allow-tools <tools...>` | 授予超出唯讀集合的工具，例如 `Bash`、`Write`、`Edit` 或 `"mcp__plugin_<plugin>_<server>__*"`。請參閱 [授予工具](https://code.claude.com/docs/zh-TW/plugin-evals.md#grant-tools) | |
| `--scaffold` | 執行每個案例的 [`scaffold_script`](https://code.claude.com/docs/zh-TW/plugin-evals#add-setup-or-history-with-case-yaml) | 關閉 |
| `--trust-plugin` | 跳過首次執行信任提示，用於 CI。請參閱 [執行可以存取的內容](https://code.claude.com/docs/zh-TW/plugin-evals.md#security) | 關閉 |
| `--mocks <mode>` | `record` 或 `off`。請參閱 [模擬 MCP 伺服器](https://code.claude.com/docs/zh-TW/plugin-evals.md#mock-mcp-servers) | `record` |
| `--eval-dir <dir>` | plugin 下方保存案例的目錄 | manifest 的 `experimental.evals`，否則 `evals` |
| `--json [path]` | 將 [結果文件](https://code.claude.com/docs/zh-TW/plugin-evals.md#json-result) 列印到 stdout，或寫入 `.json` 路徑 | |
| `--no-publish` | 保持 HTML 報告本地 | |

結束代碼報告執行如何結束。若要在管道中對其進行操作，請參閱 [在 CI 中執行 evals](https://code.claude.com/docs/zh-TW/plugin-evals.md#run-evals-in-ci)。

| 結束代碼 | 含義 |
| :- | :- |
| `0` | 套件通過：每個案例都符合閾值，且沒有其他原因導致執行失敗 |
| `1` | 失敗的案例、載入錯誤、不受信任的 plugin 目錄、[因 API 錯誤而結束](https://code.claude.com/docs/zh-TW/plugin-evals.md#runs-ended-on-an-api-error) 的執行，或 [在 CI 中執行 evals](https://code.claude.com/docs/zh-TW/plugin-evals.md#run-evals-in-ci) 下列出的其他原因 |
| `2` | 部分執行 |
| `130` | 已中斷 |
| `143` | 已終止 |

### plugin eval init

為目前目錄中的 plugin 建立 eval 套件。需要 Claude Code v2.1.269 或更新版本。請參閱 [建立您的第一個 eval 套件](https://code.claude.com/docs/zh-TW/plugin-evals.md#create-your-first-eval-suite)。

```bash theme={null}
claude plugin eval init [name] [options]
```

從 plugin 的根資料夾執行命令，也就是保存 `.claude-plugin/plugin.json` 或 skill 的 `SKILL.md` 的目錄。若要有意在另一個目錄中建立套件架構，傳遞 `--eval-dir`。

在終端機中，命令開啟互動式 Claude Code 工作階段以進行編寫訪談。在訪談中，Claude 執行以下操作：

1. 讀取 plugin
2. 詢問您它應該做好什麼
3. 提議案例和評分者
4. 寫入案例檔案
5. 執行案例並與您檢查評分，以確認評分者按您的方式評分

使用 `--bare` 或沒有終端機，命令改為寫入空白單案例範本。當 Claude 從 Claude Code 工作階段內執行命令時，命令列印該工作階段要遵循的訪談說明，而不是寫入範本。

可選的 `name` 是案例名稱。它在 `--bare` 或沒有終端機時需要，因為命令為該案例寫入空白範本。案例名稱以字母或數字開頭，僅包含字母、數字、`.`、`_` 和 `-`。在每個平台上，命令也拒絕 Windows 無法儲存的名稱，例如 `con` 或以 `.` 結尾的名稱。

命令接受這些選項：

| 選項 | 說明 | 預設 |
| :- | :- | :- |
| `--bare` | 為 `<name>` 寫入空白 `prompt.md` 和 `graders/criteria.md`，而不是執行訪談 | |
| `-i, --interactive` | 需要訪談。沒有終端機時失敗，而不是寫入範本 | |
| `--eval-dir <dir>` | 目前目錄下方寫入案例的目錄 | manifest 的 `experimental.evals`，否則 `evals` |

### plugin tag

為 plugin 發佈建立名為 `<name>--v<version>` 的帶註解 git 標籤。標籤前，命令檢查 plugin 的 `plugin.json` 和任何列出它的市集項目是否同意版本。

有關何時標籤發佈，請參閱 [發佈 plugin](https://code.claude.com/docs/zh-TW/plugins/publish.md)。

```bash theme={null}
claude plugin tag [path] [options]
```

`[path]` 是 plugin 目錄，預設為目前目錄。命令透過從該目錄向上走到列出 plugin 的 `.claude-plugin/marketplace.json` 來找到市集項目。

| 旗標 | 說明 |
| :- | :- |
| `--push` | 建立後將標籤推送到 `--remote` |
| `--dry-run` | 列印將標籤化的內容而不建立標籤 |
| `-f, --force` | 跳過髒工作樹和標籤已存在檢查 |
| `-m, --message <msg>` | 標籤註解訊息。`%s` 代表版本。預設為 `<name> <version>` |
| `--remote <name>` | 使用 `--push` 推送到的遠端。預設為 `origin` |

預覽市集簽出中 plugin 的標籤：

```bash theme={null}
claude plugin tag plugins/formatter --dry-run
```

Claude Code 列印計畫：

* plugin 名稱
* 版本及其來自的檔案
* 匹配的市集項目，當有時
* 標籤名稱
* 它將執行的 `git tag` 和 `git push` 命令

不使用 `--dry-run`，Claude Code 列印 `Created tag formatter--v1.0.0` 並列印 `Pushed to origin` 或您自己執行的推送命令。如果推送失敗，標籤仍在本地建立，命令以錯誤結束。

當命令無法安全地標籤時，它結束 `1` 並列印原因。常見原因是：

* `plugin.json` 或市集項目中沒有 `version`
* 標籤已存在
* 工作樹是髒的

### plugin test

為 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md)（一種其程式碼會註冊事件處理常式的 plugin）執行測試。此命令不需要工作階段、登入或網路。如需如何撰寫測試，請參閱 [測試 mod](https://code.claude.com/docs/zh-TW/plugins/mods/test.md)。

```bash theme={null}
claude plugin test [directory]
```

`[directory]` 是 mod 的目錄，預設為目前目錄。命令會執行其下名稱以 `.test.ts` 或 `.test.tsx` 結尾的每個檔案，並在測試失敗時以狀態 1 結束。

為 `./first-mod` 中的 mod 執行測試：

```bash theme={null}
claude plugin test ./first-mod
```

### plugin validate

驗證 plugin manifest、市集 manifest 或目錄中的 skills、agents 和命令，並以 CI 工作可以對其進行操作的代碼結束。對於建立、測試和編輯工作流程，請參閱 [建立 plugin](https://code.claude.com/docs/zh-TW/plugins/create.md)。對於驗證器在每個 manifest 中檢查的內容，請參閱 [plugin manifest 參考](https://code.claude.com/docs/zh-TW/plugins/manifest-reference.md) 和 [市集參考](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md)。

```bash theme={null}
claude plugin validate <path> [options]
```

| 旗標 | 說明 |
| :- | :- |
| `--strict` | 將警告視為錯誤，因此執行時容許的未識別欄位和遺漏中繼資料會使執行失敗 |
| `--json` | 將驗證報告輸出為具有相同結束代碼的一個 JSON 物件。需要 Claude Code v2.1.259 或更新版本 |

在提交前驗證 plugin：

```bash theme={null}
claude plugin validate ./my-plugin --strict
```

#### 驗證目錄

`<path>` 是 manifest 檔案或目錄。給定目錄，Claude Code 透過在其中找到的內容選擇要驗證的內容：

* `.claude-plugin/marketplace.json`，當它存在時
* 否則 `.claude-plugin/plugin.json`
* 否則元件檔案，由目錄的名稱選擇。驗證沒有 manifest 的元件檔案需要 Claude Code v2.1.233 或更新版本：
  * 名為 `skills`、`agents` 或 `commands` 的目錄：其中的檔案
  * 名為 `.claude` 的目錄：其中的 `skills`、`agents` 和 `commands` 目錄
  * 任何其他目錄：其 `.claude` 下的這三個目錄

當目錄同時包含 `.claude-plugin/marketplace.json` 和 `.claude-plugin/plugin.json` 時，Claude Code 會驗證市集，也會驗證 plugin 的 manifest 和元件檔案。這需要 Claude Code v2.1.289 或更新版本。

Claude Code 不遵循您命名的目錄內的符號連結。它的作用取決於連結的位置：

* **plugin 或 `.claude` 根下的連結 `skills`、`agents` 或 `commands` 目錄**：Claude Code 警告其中的任何內容都未被讀取。
* **`skills`、`agents` 或 `commands` 目錄內的連結項目**：Claude Code 跳過它，並按目錄警告它跳過了多少個工作階段會載入的項目。
* **您命名的 `skills`、`agents` 或 `commands` 目錄本身是符號連結，或其父 `.claude` 目錄是**：Claude Code 報告錯誤，且不檢查其中的任何內容。改為命名真實目錄。

驗證執行不讀取幾個檔案：

* **plugin 根處的 `SKILL.md`**：當您針對 plugin 目錄執行 `claude plugin validate` 時，Claude Code 不檢查 plugin 根處的 `SKILL.md`
* **plugin 根處的 `CLAUDE.md`**：在 plugin 執行中，Claude Code 也警告 plugin 根處的 `CLAUDE.md`
* **市集執行中的 Plugin 檔案**：從市集目錄，Claude Code 不開啟市集列於其他目錄中之 plugins 的 skill、agent、command 或 hook 檔案，或它們捆綁的 MCP 伺服器檔案。若要在這些檔案中找到錯誤，驗證每個 plugin 目錄

#### 輸出和結束代碼

Claude Code 列印它驗證的檔案、任何帶有其路徑的錯誤和警告，以及判決行。結束代碼遵循判決：

| 結束代碼 | 判決行 | 含義 |
| :- | :- | :- |
| `0` | `Validation passed` 或 `Validation passed with warnings` | manifest 載入。使用 `--strict`，也沒有警告 |
| `1` | `Validation failed` 或 `Validation failed (--strict treats warnings as errors)` | 錯誤，或 `--strict` 下的警告。[建議](#advice-on-the-readme) 不計入，無論是否使用 `--strict` |
| `2` | `Unexpected error during validation: <reason>` | 驗證器本身失敗，例如在不可讀的路徑上 |

使用 `--json`，Claude Code 將報告寫入 stdout 作為具有這些頂級欄位的一個 JSON 物件：

* `success`：結束代碼給出的相同判決
* `strict`：執行是否將警告視為錯誤
* `target`：Claude Code 驗證的解析路徑
* `manifest`：manifest 自己的結果，或沒有 manifest 的執行為 `null`
* `contents`：每個檔案的結果，命名其 `file` 並帶有 `errors`、`warnings` 和 `notes` 陣列。沒有錯誤、警告或註記的檔案不會有項目，因此沒有可報告的內容時 `contents` 為空。對於 [同時含有 `marketplace.json` 和 `plugin.json` 的目錄](#validate-a-directory)，`manifest` 是 `marketplace.json` 的結果，`plugin.json` 的結果則放在 `contents` 中
  * `gatingHooks`：每個可以拒絕動作的 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md) hook（例如 `tool.call` hook）是否具有 [`.catch` 處理常式](https://code.claude.com/docs/zh-TW/plugins/mods/events#handle-a-hook-that-fails)。每個項目提供 `module`、`pattern`、`hook` 和 `hasCatch`。需要 Claude Code v2.1.290 或更新版本
* `advice`：該次執行的 [建議](#advice-on-the-readme)，每個項目以 `file` 指名 README，並帶有 `message` 和要貼上的 `installLine`。沒有建議時為空。需要 Claude Code v2.1.295 或更新版本

在結束 `2` 時，命令不向 stdout 寫入任何內容。錯誤訊息進入 stderr。

#### README 的建議

`claude plugin validate` 輸出中的 `Advice` 區塊表示 plugin 的 README 沒有從市集安裝該 plugin 的行，並提供一行供您新增。建議不是錯誤也不是警告。無論是否使用 `--strict`，它都不會變更判決行或結束代碼。需要 Claude Code v2.1.295 或更新版本。

例如，驗證 `acme-tools` 市集的目錄時，會為其 `deploy-helper` plugin 列印此建議：

```text theme={null}
Validating marketplace manifest: /path/to/acme-tools/.claude-plugin/marketplace.json

ℹ Advice (does not change the verdict):

  ❯ /path/to/acme-tools/plugins/deploy-helper/README.md: This README has no line that installs "deploy-helper" from a marketplace. Add the install line, which works in one step on Claude Code 2.1.275 or later.
      /plugin install deploy-helper --marketplace acme/tools

✔ Validation passed
```

若要清除建議，請將建議的行貼到它指名的 README 中，然後在您的 shell 中再次執行 `claude plugin validate`。`Advice` 區塊就會消失。

如果建議的行包含預留位置 `<owner>/<repo>`，原封不動地貼上並不會清除建議。請先取得真正的來源：

* **您驗證的是 plugin 本身的目錄**：當市集從其自身內部的目錄列出該 plugin 時，請改為驗證該目錄。當市集從其他地方（例如 GitHub 儲存庫）列出該 plugin 時，請自行填入 `<owner>/<repo>`
* **您驗證的是市集的目錄**：Claude Code 會從該目錄頂層 `.git` 目錄的 `origin` 遠端填入來源。當它無法使用該遠端時（例如沒有遠端），請自行將 `<owner>/<repo>` 替換為您市集的來源

當 `plugin install` 或其簡寫 `plugin i` 在同一行後面接著下列任一項時，您已撰寫的安裝行就會計入。`/plugin` 和 `claude plugin` 兩種寫法都算：

* `<plugin>@<marketplace>`，例如 `/plugin install deploy-helper@acme-tools`
* plugin 的名稱和 `--marketplace <source>`，例如 `/plugin install deploy-helper --marketplace acme/tools`

## claude plugin marketplace 命令

從 shell 執行 `claude plugin marketplace <subcommand>` 以新增、列出、重新整理和移除您安裝外掛所用的市集。

* **結束代碼**：這些子命令遵循外掛命令的[結束代碼慣例](#claude-plugin-commands)
* **範圍**：它們的 `--scope` 旗標沒有 `-s` 短形式

有關市集是什麼以及 Claude Code 如何快取它，請參閱[外掛載入參考](https://code.claude.com/docs/zh-TW/plugins/loading.md)。

### plugin marketplace add

從 GitHub 儲存庫、git URL、託管的 `marketplace.json` 或本地路徑新增市集，並在設定檔中宣告它。

新增後，Claude Code 會安裝您已安裝的外掛所缺少的任何[相依套件](https://code.claude.com/docs/zh-TW/plugins/dependencies.md)。

```bash theme={null}
claude plugin marketplace add <source> [options]
```

| 旗標 | 說明 |
| :- | :- |
| `--scope <scope>` | 在其中宣告市集的設定檔：`user`、`project` 或 `local`。預設為 `user` |
| `--sparse <paths...>` | 將 git 簽出限制為這些目錄，用於 monorepos。僅 `github` 和 `git` 來源 |
| `--claudeai` | 將引數讀作 [claude.ai 上託管的市集](https://code.claude.com/docs/zh-TW/plugins/install.md#add-from-claude-ai) 的名稱，而不是來源。需要 Claude Code v2.1.273 或更新版本 |
| `--json` | 將命令是否成功及其訊息，以一個 JSON 物件的形式列印在 stdout 的最後一行，採用 [JSON 結果格式](#plugin-json-result)。搭配 `--claudeai` 時無效。需要 Claude Code v2.1.287 或更新版本 |

`<source>` 採用下表中的任何形式，其形式決定來源類型以及 Claude Code 如何擷取市集。對於結果來源物件，請參閱[市集參考](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md)。

| 您輸入 | 來源類型 | Claude Code 如何擷取它 |
| :- | :- | :- |
| `owner/repo`、`owner/repo#ref` 或 `owner/repo@ref` | `github` | 複製 GitHub 儲存庫，給定時固定到 `ref`。所有者和儲存庫必須遵循 GitHub 命名規則 |
| `user@host:path[.git][#ref]` | `git` | 透過 SSH 複製 |
| 以 `.git[#ref]` 結尾或包含 `/_git/` 的 `http://` 或 `https://` URL，例如 `https://example.com/repo.git` | `git` | 複製 URL，包括 Azure DevOps URL |
| `https://github.com/owner/repo` 或 `https://gitlab.com/namespace/project`，或相同的 `http://` 版本 | `git` | 在附加 `.git` 後複製 URL |
| 任何其他 `http://` 或 `https://` URL，包括沒有 `.git` 的自託管 git 主機 | `url` | 將 URL 作為 `marketplace.json` 擷取。若要改為複製儲存庫，請附加 `.git` |
| `./path`、`../path`、`/path` 或 `~/path` 到目錄 | `directory` | 就地讀取目錄。在 Windows 上，`.\`、`..\` 和 `C:\` 形式也有效 |
| 相同的路徑形式，到 `.json` 檔案 | `file` | 就地讀取檔案 |

對於其複製 URL 不帶 `.git` 尾碼的主機（例如 AWS CodeCommit），改為在 [`extraKnownMarketplaces`](https://code.claude.com/docs/zh-TW/settings-reference#extraknownmarketplaces) 中將市集新增為 git 項目。Claude Code 複製 git 項目，無論其 URL 是否以 `.git` 結尾。

Claude Code 也複製具有嵌套子群組的 `gitlab.com` URL，例如 `https://gitlab.com/group/subgroup/project`。

新增市集並與專案共享：

```bash theme={null}
claude plugin marketplace add your-org/your-marketplace --scope project
```

Claude Code 列印 `Successfully added marketplace: your-marketplace (declared in project settings)`，使用市集自己的 manifest 中的 `name`。重複新增或無效來源則會列印以下結果之一：

* **市集已在磁碟上**：輸出為 `Marketplace 'your-marketplace' already on disk — declared in project settings`，結束代碼為 `0`
* **無法識別的來源**：輸出為 `Invalid marketplace source format. Try: owner/repo, https://..., or ./path`，結束代碼為 `1`
* **裸主機，例如 `gitlab.example.com/team/plugins`**：新增失敗，因為是無效的 `owner/repo` 速記，訊息告訴您新增 `https://` 或使用本地路徑

按 `claude plugin marketplace list` 的 `From claude.ai:` 部分中列印的名稱新增 [claude.ai 上託管的市集](https://code.claude.com/docs/zh-TW/plugins/install.md#add-from-claude-ai)：

```bash theme={null}
claude plugin marketplace add --claudeai claudeai-organization-library
```

使用 `--claudeai` 時，命令拒絕 `--scope` 和 `--sparse`。市集為您的帳戶託管，未在設定檔中宣告，因此您無法透過專案的 `.claude/settings.json` 共享它。

### plugin marketplace list

列出您新增的每個市集及其來源。

```bash theme={null}
claude plugin marketplace list [options]
```

| 旗標 | 說明 |
| :- | :- |
| `--json` | 將列表列印為 JSON |

Claude Code 列印 `Configured marketplaces:` 和每個市集一個 `Source:` 行，或 `No marketplaces configured`。

使用 `--json` 時，Claude Code 列印一個陣列，每個市集一個物件，帶有下面的欄位。每個欄位都是字串。

| 欄位 | 說明 |
| :- | :- |
| `name` | 市集的名稱 |
| `source` | `github`、`git`、`url`、`directory`、`file` 或 `claudeai` |
| `repo` | `owner/repo`。僅 `github` 來源 |
| `url` | 複製或擷取 URL。僅 `git` 和 `url` 來源 |
| `path` | 本地路徑。僅 `directory` 和 `file` 來源 |
| `ref` | 固定的分支或標籤。`github` 和 `git` 來源，僅當固定時 |
| `installLocation` | Claude Code 快取市集的位置 |

已新增的 [claude.ai 市集](https://code.claude.com/docs/zh-TW/plugins/install.md#add-from-claude-ai) 沒有本地複製，因此其項目帶有其 claude.ai 識別碼 `marketplaceId` 和 `organizationUuid`，代替 `installLocation`。它也帶有 `scope`（當有記錄時）和 `status`。

如果您的終端機工作階段[從您的 claude.ai 帳戶同步外掛](https://code.claude.com/docs/zh-TW/plugins/loading.md#synced-plugins)，文字列表以 `From claude.ai:` 部分結尾。該部分列出 claude.ai 為您的帳戶列出但您尚未新增的市集，包括基於 git 的和託管的。它需要 Claude Code v2.1.273 或更新版本。

若要從該部分新增市集，請參閱[從 claude.ai 新增市集](https://code.claude.com/docs/zh-TW/plugins/install.md#add-from-claude-ai)。

`--json` 輸出僅涵蓋已設定的市集，並省略該部分。

### plugin marketplace remove

從您的設定中移除市集的宣告。`rm` 是 `remove` 的別名。

> [!WARNING]
>
> 當您從最後一個宣告它的範圍移除市集時，Claude Code 也會刪除其快取並解除安裝您從它安裝的每個外掛。它也會盡可能刪除它們已儲存的[選項和密鑰](https://code.claude.com/docs/zh-TW/plugins/manifest-reference.md#user-configuration)和[資料](https://code.claude.com/docs/zh-TW/plugins/components.md#path-variables-and-persistent-data)。
>
> 若要重新整理市集而不失去其外掛，請改為執行 `plugin marketplace update`。

```bash theme={null}
claude plugin marketplace remove <name> [options]
```

`<name>` 是 `plugin marketplace list` 顯示的市集名稱，而不是您傳遞給 `add` 的來源。

| 旗標 | 說明 |
| :- | :- |
| `--scope <scope>` | 從一個設定範圍移除宣告：`user`、`project` 或 `local`。不使用它時，Claude Code 從每個範圍移除宣告 |
| `--json` | 將命令是否成功及其訊息，以一個 JSON 物件的形式列印在 stdout 的最後一行，採用 [JSON 結果格式](#plugin-json-result)。需要 Claude Code v2.1.287 或更新版本 |

從每個範圍移除市集：

```bash theme={null}
claude plugin marketplace remove your-marketplace
```

Claude Code 列印 `Successfully removed marketplace: your-marketplace`。當命令解除安裝外掛時，輸出會在例如 `Also uninstalled 2 plugins from this marketplace:` 的行下列出它們。若要再次使用其中一個，請重新新增市集並重新安裝該外掛。

如果您將範圍限定到未宣告該市集的設定檔，命令會失敗，訊息為 `Marketplace 'your-marketplace' is not declared in project settings. Omit --scope to remove it from all scopes.`

### plugin marketplace update

重新整理一個市集或每個市集，從其來源擷取新外掛和版本。使用分支或標籤 `ref` 新增的市集會更新到該 ref 的最新提交，而不是儲存庫的預設分支。

```bash theme={null}
claude plugin marketplace update [name] [options]
```

| 旗標 | 說明 |
| :- | :- |
| `--json` | 將命令是否成功及其訊息，以一個 JSON 物件的形式列印在 stdout 的最後一行，採用 [JSON 結果格式](#plugin-json-result)。未指定名稱時，命令會拒絕 `--json` 並以 `1` 結束。需要 Claude Code v2.1.287 或更新版本 |

重新整理一個市集：

```bash theme={null}
claude plugin marketplace update your-marketplace
```

Claude Code 列印 `Successfully updated marketplace: your-marketplace`。當您省略名稱時，它列印計數，例如 `Successfully updated 2 marketplaces`。

## /plugin 在工作階段中

在互動式工作階段內，`/plugin` 開啟 plugin 面板。每個子命令在標籤上開啟面板、在那裡執行操作或內聯列印結果。`/plugins` 和 `/marketplace` 是 `/plugin` 的別名。

您只能在互動式終端工作階段中執行這些命令。在非互動式執行（例如 `claude -p`）中，Claude Code 回覆 `/plugin` 在此環境中不可用。

有關哪些表面有 `/plugin`、如何在沒有它的情況下安裝以及每個面板標籤顯示的內容，請參閱 [安裝和管理 plugins](https://code.claude.com/docs/zh-TW/plugins/install.md)。

`<plugin>` 是 plugin `name` 或 `name@marketplace`。

下表列出每個工作階段形式。shell 子命令 `init`、`update`、`details`、`prune`、`eval`、`eval init` 和 `test` 沒有工作階段形式。

| 命令 | 別名 | 它的作用 |
| :- | :- | :- |
| `/plugin` | | 在 **Discover** 標籤上開啟面板。`/plugin` 後的任何無法識別的第一個單詞執行相同操作 |
| `/plugin help` | `/plugin --help`、`/plugin -h` | 顯示 `/plugin` 子命令的使用列表 |
| `/plugin list [--enabled\|--disabled]` | `ls` | 內聯列印您從市集安裝的外掛，包括版本、範圍和狀態。篩選旗標僅顯示該狀態。啟用狀態尚未套用的外掛標記為 `— run /reload-plugins to apply` |
| `/plugin install` | `i` | 開啟 **Discover** 標籤 |
| `/plugin install <plugin>` | `i` | 在 **Discover** 標籤中開啟 plugin 的詳細資訊。使用 `name@marketplace`，在該市場的列表中開啟它們 |
| `/plugin install <source>` | `i` | 當目標是路徑、URL 或 `owner/repo` 時報告 [marketplace not found](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#marketplace-not-found) 錯誤並不安裝任何內容，即使是您已經新增的來源。若要從來源安裝，請參閱 [在一個命令中新增市場和安裝](https://code.claude.com/docs/zh-TW/plugins/install.md#add-a-marketplace-and-install-in-one-command) |
| `/plugin install <plugin> --marketplace <source>` | `i` | 當您尚未新增市場時在 `<source>` 新增市場，要求您先確認，然後開啟 plugin 的詳細資訊。請參閱 [在一個命令中新增市場和安裝](https://code.claude.com/docs/zh-TW/plugins/install.md#add-a-marketplace-and-install-in-one-command)。需要 Claude Code v2.1.275 或更新版本 |
| `/plugin manage` | | 開啟 **Installed** 標籤 |
| `/plugin stats` | | 在 [`/skill-doctor`](https://code.claude.com/docs/zh-TW/skills#find-unused-skills) 可用的工作階段中開啟 **Stats** 標籤。在其他任何地方，它在 **Discover** 標籤上開啟面板 |
| `/plugin enable <plugin>` | | 在 plugin 處開啟 **Installed** 標籤並啟用它 |
| `/plugin disable <plugin>` | | 在 plugin 處開啟 **Installed** 標籤並停用它 |
| `/plugin uninstall <plugin>` | | 在 plugin 處開啟 **Installed** 標籤並卸載它 |
| `/plugin configure <plugin>` | `config` | 開啟外掛的 [`userConfig`](https://code.claude.com/docs/zh-TW/plugins/manifest-reference) 對話框，或報告外掛未宣告任何 |
| `/plugin validate <path>` | | 列印與 `claude plugin validate` 相同的報告，內聯 |
| `/plugin tag [path] [--push] [--dry-run] [--force]` | | 建立發佈標籤，如 `claude plugin tag` 所做的那樣。接受 `--push`、`--dry-run` 和 `--force` 或 `-f`；使用任何其他旗標或額外引數，Claude Code 改為列印使用 |
| `/plugin marketplace` | `market` | 不執行任何可見操作。傳遞 `add`、`list`、`update` 或 `remove` |
| `/plugin marketplace add [source]` | `market add` | 使用來源，新增它並報告結果。沒有來源，開啟 **Add marketplace** 輸入 |
| `/plugin marketplace list` | `market list` | 內聯列印您的市場名稱 |
| `/plugin marketplace update [name]` | `market update` | 開啟 **Marketplaces** 標籤。使用名稱，在那裡重新整理該市場 |
| `/plugin marketplace remove [name]` | `market remove`、`market rm`、`marketplace rm` | 開啟 **Marketplaces** 標籤。使用名稱，在那裡移除該市場 |

如果您在 `/plugin enable`、`disable`、`uninstall` 或 `configure` 中命名目前專案中未安裝的 plugin，Claude Code 列印 `Plugin "<plugin>" is not installed in this project` 而不是執行操作。

## /reload-plugins

在不重新啟動工作階段的情況下，將待處理的外掛程式變更套用到執行中的工作階段。待處理的變更是指自工作階段啟動以來，您在磁碟上安裝、更新、啟用、停用或編輯的外掛程式。

當您關閉 `/plugin` 面板且在其中進行了待處理的變更時，Claude Code 會為您執行 `/reload-plugins`。在外掛程式面板外發生的變更（例如您在另一個終端機中執行的 `claude plugin` 命令）之後，請自行執行此命令。

```text theme={null}
/reload-plugins [--force]
```

| 旗標 | 說明 |
| :- | :- |
| `--force` | 即使重新載入會使提示快取失效，也要套用重新載入。不加破折號的 `force` 也可以 |

### 重新載入摘要

Claude Code 重新載入每個作用中的外掛程式，並列印一行摘要 `Reloaded: N plugins · N skills · N agents · N hooks · N plugin MCP servers · N plugin LSP servers`，在沒有互動式終端機的工作階段中省略外掛程式 MCP 伺服器計數。當任何外掛程式失敗時，摘要會新增 `N errors during load. Run /plugin for details.`

技能計數涵蓋外掛程式提供的每項技能，包括其 `commands/` 項目和其 SKILL.md 技能。代理計數是在工作階段中載入的代理數量，包括不來自外掛程式的代理。

當重新載入的外掛程式的[相依性](https://code.claude.com/docs/zh-TW/plugins/dependencies.md)遺失時，Claude Code 會安裝它們、重新載入，並在摘要中附加 `(+ N dependencies: <names>) resolved`。

### 變更 MCP 工具的重新載入

當重新載入會新增或移除外掛程式 MCP 伺服器或 `LSP` 工具，且該變更會使[提示快取](https://code.claude.com/docs/zh-TW/prompt-caching.md#enabling-or-disabling-a-plugin)失效時，Claude Code 不會套用重新載入。它會列印類似 `This reload changes MCP tools (<server>) — your next message will re-read the whole conversation instead of using the cache. Run /reload-plugins --force to apply.` 的一行。傳遞 `--force` 以無論如何套用它。

### 沒有互動式終端機的工作階段

`/reload-plugins` 也在沒有互動式終端機的工作階段中執行，例如桌面應用程式、Agent SDK 和[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)搭配 `-p`。需要 Claude Code v2.1.260 或更新版本。

在這些工作階段中，命令只在您自行將其輸入到工作階段時執行，例如在 `-p` 提示或桌面應用程式的提示方塊中。當它以其他方式到達時，例如透過[遠端控制](https://code.claude.com/docs/zh-TW/remote-control.md)或從 Slack 轉送的訊息，命令會回覆 `/reload-plugins isn't available over a remote connection in this session.` 並且不重新載入任何內容。

這些工作階段中的重新載入不會連接或斷開外掛程式 MCP 伺服器。這些變更會在您的下一個工作階段中生效。

## 為單一工作階段載入 plugin 的旗標

兩個 `claude` 旗標為單一工作階段載入 plugin，無需安裝它。兩者都可重複。

Plugin 作者使用它們在發佈前測試 plugin。對於載入-編輯-重新載入工作流程，請參閱 [開發而不使用市場](https://code.claude.com/docs/zh-TW/plugins/create.md#develop-without-a-marketplace)。

| 旗標 | 說明 | 範例 |
| :- | :- | :- |
| `--plugin-dir <path>` | 從目錄或其 `.zip` 存檔載入 plugin。plugins 資料夾載入每個保存 `.claude-plugin/plugin.json` 的子資料夾。每個旗標採用一個路徑 | `claude --plugin-dir ./my-plugin --plugin-dir ./other.zip` |
| `--plugin-url <url>` | 從 URL 擷取 plugin `.zip` 存檔。重複旗標，或在一個引用值中傳遞多個 URL 空格分隔 | `claude --plugin-url "https://example.com/a.zip https://example.com/b.zip"` |

任一旗標載入的 plugin 是工作階段專用 plugin。[`claude plugin list`](#plugin-list) 將其顯示為 `<name>@inline`，範圍為 `session`，但僅當相同旗標在子命令前時。例如，執行 `claude --plugin-dir ./my-plugin plugin list`。該 plugin 在以 `Session-only plugins` 開頭的標題下顯示為 `<name>@inline`，而 `--json` 將其 `scope` 報告為 `session`。

當工作階段專用 plugin 與已安裝的 plugin 共享名稱時，Claude Code 為該工作階段載入工作階段專用複製並跳過已安裝的複製。如果您使用 `claude plugin disable <name>@inline` 停用工作階段專用複製，或受管設定鎖定該 plugin 名稱，已安裝的複製改為載入。對於優先順序，請參閱 [Plugin 載入參考](https://code.claude.com/docs/zh-TW/plugins/loading.md)。

管理員可以拒絕兩個旗標和 [`CLAUDE_CODE_PLUGIN_DIRS`](https://code.claude.com/docs/zh-TW/env-vars#variables) 變數中命名的資料夾，使用受管 [`disableSideloadFlags`](https://code.claude.com/docs/zh-TW/settings-reference#disablesideloadflags) 設定。Claude Code 然後列印旗標被您組織的受管設定停用，並結束 `1` 而不啟動。

從 Agent SDK，[`plugins`](https://code.claude.com/docs/zh-TW/agent-sdk/plugins) 選項等同於 `--plugin-dir`。

## 後續步驟

* [安裝和管理 plugins](https://code.claude.com/docs/zh-TW/plugins/install.md)：與步驟相同的操作，以及您在每一個看到的內容
* [Plugin 載入參考](https://code.claude.com/docs/zh-TW/plugins/loading.md)：每個命令在磁碟上變更的內容以及哪個範圍生效
* [Troubleshoot plugins](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md)：安裝、市場、載入和驗證錯誤訊息及其修復
* [Plugin manifest 參考](https://code.claude.com/docs/zh-TW/plugins/manifest-reference.md)：`claude plugin validate` 檢查的欄位

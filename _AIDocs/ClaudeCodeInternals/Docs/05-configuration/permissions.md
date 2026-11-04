<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/permissions | lastmod: 2026-11-02 | section: Configuration / Permissions and sandboxing -->
> 來源：https://code.claude.com/docs/zh-TW/permissions（官方 zh-TW，lastmod 2026-11-02）｜分類：Configuration › Permissions and sandboxing｜EN 摘要：Control what Claude Code can access and do with fine-grained permission rules, modes, and managed policies.

# 設定權限

> 使用細粒度權限規則、模式和受管理原則來控制 Claude Code 可以存取和執行的操作。

Claude Code 支援細粒度權限，讓您可以精確指定代理允許執行和不允許執行的操作。權限設定可以簽入版本控制並分發給組織中的所有開發人員，也可以由個別開發人員自訂。

## 權限系統

Claude Code 使用分層權限系統來平衡功能和安全性。下表顯示每種工具類型，在手動模式中是否在操作執行前要求核准。其他[權限模式](#permission-modes)會改變哪些操作會詢問您；在自動模式中，分類器會檢查操作而不是您，[分類器如何評估操作](https://code.claude.com/docs/zh-TW/permission-modes.md#how-the-classifier-evaluates-actions)列出它看到的操作。

| 工具類型 | 範例 | 需要核准 | "是，不要再問"行為 |
| :- | :- | :- | :- |
| 唯讀 | 檔案讀取、Grep | 否，在[工作目錄和其他目錄](#working-directories)內 | 不適用 |
| Bash 命令 | Shell 執行 | 是，除了內建的[唯讀命令](#read-only-commands)集合 | 每個儲存庫和命令永久有效 |
| 檔案修改 | Edit/Write 檔案 | 是 | 直到工作階段結束 |
| Web 擷取 | WebFetch | 是，除了內建的[預先核准的文件網域](https://code.claude.com/docs/zh-TW/tools-reference.md#webfetch-tool-behavior)集合 | 每個儲存庫和網域永久有效 |
| Web 搜尋 | WebSearch | 是 | 每個儲存庫永久有效 |

權限提示會顯示 Claude 即將執行的操作，接著列出您的選項。此範例是手動模式工作階段中 Bash 命令的權限提示：

![標題為 Bash command 的 Claude Code 權限提示。在一則關於自動模式的提醒下方，顯示說明 'Run the test suite'、命令 npm test，以及 'This command requires approval' 這一行，接著詢問 'Do you want to proceed?' 並提供四個選項：Yes；Yes, and don't ask again for: npm test \*；Yes, and switch to auto mode；以及 No。頁尾列出兩個按鍵：Esc 取消，Tab 修改。](https://mintcdn.com/claude-code/oa7CKjMeIChox26S/images/permission-prompt-bash-light.png?fit=max\&auto=format\&n=oa7CKjMeIChox26S\&q=85\&s=87585d008a29304873466399f7b476f6)

第三個選項 **Yes, and switch to auto mode** [並非每個權限提示都會出現](https://code.claude.com/docs/zh-TW/permission-modes.md#switch-permission-modes)。

當您選擇"是，不要再問"且核准永久保存時（例如 Bash 命令或 WebFetch 網域），Claude Code 會將規則保存到 git 儲存庫根目錄的 `.claude/settings.local.json`，透過 [worktrees](https://code.claude.com/docs/zh-TW/worktrees.md) 解析到主簽出。該規則適用於該儲存庫中任何位置的未來工作階段，包括在子目錄和 worktrees 中啟動的工作階段。檔案修改核准不會保存到檔案：如表所示，它持續到工作階段結束。在某些情況下，例如在 git 儲存庫外或在 Windows 上，Claude Code 不使用儲存庫根目錄；[Claude Code 查找每個檔案的位置](https://code.claude.com/docs/zh-TW/settings.md#where-claude-code-looks-for-each-file)列出這些情況以及它改為保存規則的位置。

有時權限提示只提供一次性核准，沒有"不要再問"選項，也沒有允許操作用於工作階段其餘部分的選項。Claude Code 只在權限提示可以向您顯示它們允許的所有內容時才提供這些選項，因此您從權限提示保存的規則只涵蓋其選項命名的內容。當權限提示只提供一次性核准時，請核准操作一次，或在 [`/permissions`](#manage-permissions) 中自行新增規則。若要停止以 `watch` 等 exec 包裝器開頭的命令，或帶有 `-delete` 等動作的 `find` 命令的權限提示，請參閱 [Exec 包裝器和 `find` 動作](#exec-wrappers-and-find-actions)。

### 在回答權限提示時新增評論

您可以在核准或拒絕單個操作時向 Claude 附加備註。在大多數權限提示上，包括 Bash、PowerShell、檔案和 MCP 工具權限提示，移至**是**或**否**並按 `Tab` 以在該選項上開啟評論欄位。WebFetch 和瀏覽器權限提示不提供該欄位。允許操作用於工作階段其餘部分或保存規則的選項也不接受評論。

開啟欄位後，輸入評論，然後按以下其中一個鍵：

* `Enter`：提交您的答案並附加評論。如果您將欄位留空，Claude Code 會提交答案而不附加評論。
* `Tab`：關閉欄位而不回答。Claude Code 保留您輸入的文字，如果您使用該選項回答，仍會傳送它。
* `Shift+Tab`：在檔案權限提示上，例如 Edit 或 Write 權限提示，與 `Tab` 相同，會關閉欄位。在 v2.1.235 之前，在欄位內按 `Shift+Tab` 會改為選擇允許操作用於工作階段其餘部分的選項，因此 Claude Code 會核准該操作用於工作階段其餘部分並捨棄評論。

Claude Code 根據您的回答方式以不同方式傳遞評論：

* **是**：Claude Code 執行操作，然後在結果之後將您的評論傳送給 Claude。
* **否**：Claude Code 將您的評論作為拒絕原因傳送給 Claude，Claude 繼續工作。如果您在主對話的權限提示上選擇**否**而沒有評論，Claude Code 會停止該回合。

## 管理權限

您可以使用 `/permissions` 檢視和管理 Claude Code 的工具權限。此對話框列出所有權限規則及其來源的 `settings.json` 檔案。您可以在 Claude 工作時開啟此對話框：當您新增或移除規則時，Claude Code 會從 Claude 在同一輪中的下一個工具呼叫開始套用變更。在 v2.1.234 之前，Claude Code 會將命令排隊直到輪次完成。

* **Allow** 規則讓 Claude Code 使用指定的工具，無需手動批准。
* **Ask** 規則在 Claude Code 嘗試使用指定工具時提示確認。
* **Deny** 規則防止 Claude Code 使用指定的工具。

規則按順序評估：deny、ask，然後 allow。該順序中的第一個符合項決定結果，規則特異性不會改變順序。

一個廣泛的 deny 規則（例如 `Bash(aws *)`）會阻止每個符合的呼叫，包括也符合較窄 allow 規則（例如 `Bash(aws s3 ls)`）的呼叫，因此 deny 規則無法攜帶允許清單例外。ask 和 allow 之間也適用相同的優先順序：符合的 ask 規則即使有更具體的 allow 規則也符合相同的呼叫時，也會提示。

Deny 規則的行為取決於它們是否命名工具或在工具內限定模式。像 `Bash` 這樣的裸工具名稱會將工具從 Claude 的上下文中完全移除，因此 Claude 永遠看不到它。如果您在工作階段中途新增此類規則，Claude 無法從其下一個工具呼叫開始呼叫該工具；[拒絕整個工具](https://code.claude.com/docs/zh-TW/prompt-caching.md#denying-an-entire-tool)涵蓋 Claude 已經看過的定義會發生什麼。像 `Bash(rm *)` 這樣的限定規則會保留工具可用性，並在 Claude 嘗試時阻止符合的呼叫。

裸名稱移除適用於除了 [`EndConversation`](https://code.claude.com/docs/zh-TW/tools-reference#endconversation-tool-behavior) 之外的每個工具：deny 規則在任何其他工具仍然存在時無法移除它，ask 規則永遠不會為它提示。

> [!NOTE]
>
> 權限規則由 Claude Code 強制執行，而不是由模型強制執行。您的提示或 `CLAUDE.md` 中的指令會影響 Claude 嘗試執行的操作，但不會改變 Claude Code 允許的操作。若要授予或撤銷存取權限，請使用 `/permissions`、此處描述的規則、[permission mode](https://code.claude.com/docs/zh-TW/permission-modes.md) 或 [PreToolUse hook](#extend-permissions-with-hooks)。

當 [auto mode](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode) 可用於您的工作階段時，此對話框也包括 [auto mode 分類器規則](https://code.claude.com/docs/zh-TW/auto-mode-config.md#edit-rules-from-permissions)。選擇 **Auto mode** 標籤以檢視它們。

## 權限模式

Claude Code 支援多種權限模式來控制工具呼叫的批准方式。請參閱 [Permission modes](https://code.claude.com/docs/zh-TW/permission-modes.md) 以了解何時使用每一種。若要變更工作階段啟動時的模式，請在您的 [settings files](https://code.claude.com/docs/zh-TW/settings.md#where-settings-live) 中設定 `defaultMode`。[Which mode a session starts in](https://code.claude.com/docs/zh-TW/permission-modes.md#which-mode-a-session-starts-in) 涵蓋每個計畫的內建預設值以及 VS Code 擴充功能讀取的內容。

| 模式 | 描述 |
| :- | :- |
| `default` | 在首次使用每個工具時提示權限。在 CLI、VS Code 和 JetBrains 擴充功能以及桌面應用程式中標示為 Manual，Claude Code 接受 `manual` 作為別名 |
| `acceptEdits` | 自動接受工作目錄或 `additionalDirectories` 中路徑的檔案編輯和常見檔案系統命令，例如 `mkdir`、`touch`、`mv` 和 `cp` |
| `plan` | Claude 讀取檔案並執行唯讀 shell 命令以探索，但不編輯您的原始檔案；在 [auto mode](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode) 可用的情況下，分類器批准的命令也會執行。在 CLI 和 VS Code 擴充功能中標示為 Plan |
| `auto` | 在沒有例行提示的情況下執行；在 shell 命令和網路要求等操作執行之前，背景 [classifier](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode) 會檢查它們是否符合您的要求 |
| `dontAsk` | 自動拒絕每個原本會提示的呼叫，但您安裝的 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md) 仍可核准其中部分呼叫。工作目錄中的檔案讀取和其他不需要核准的操作仍會執行，透過 `/permissions` 或 `permissions.allow` 規則預先核准的工具也會執行。`AskUserQuestion`、標示為 [`requiresUserInteraction`](https://code.claude.com/docs/zh-TW/mcp#require-approval-for-a-specific-tool) 的 MCP 工具、[來自網路路徑的讀取](#network-paths)，以及在該設定到達 Claude Code 的工作階段中[您的組織設定為 `ask`](https://code.claude.com/docs/zh-TW/mcp#organization-controls-on-connector-tools) 的連接器工具，即使您已允許它們也會被拒絕 |
| `bypassPermissions` | 跳過權限提示，但[任何模式都不會自動核准的動作](https://code.claude.com/docs/zh-TW/permission-modes.md#actions-no-mode-auto-approves)除外 |

> [!WARNING]
>
> 在 `bypassPermissions` 模式中，Claude Code 跳過權限提示，包括對 [protected paths](https://code.claude.com/docs/zh-TW/permission-modes.md#protected-paths)（例如 `.git` 和 `.claude`）的寫入。[cross-session messaging safeguards](https://code.claude.com/docs/zh-TW/permission-modes.md#skip-all-checks-with-bypasspermissions-mode) 仍然適用。僅在隔離環境（例如容器或虛擬機）中使用此模式，其中 Claude Code 無法造成損害。

若要防止 `bypassPermissions` 或 `auto` 模式被使用，請在任何 [settings file](https://code.claude.com/docs/zh-TW/settings.md#where-settings-live) 中將 `permissions.disableBypassPermissionsMode` 或 `permissions.disableAutoMode` 設定為 `"disable"`。這些在 [managed settings](#managed-settings) 中最有用，因為它們無法被覆蓋。

## 權限規則語法

權限規則遵循格式 `Tool` 或 `Tool(specifier)`。指定符內的括號是字面的，因此包含括號的命令或路徑不需要逃逸。

### 符合工具的所有使用

若要符合工具的所有使用，請使用不帶括號的工具名稱：

| 規則 | 效果 |
| :- | :- |
| `Bash` | 符合所有 Bash 命令 |
| `WebFetch` | 符合所有網頁擷取請求 |
| `Read` | 符合所有檔案讀取 |

`Bash(*)` 等同於 `Bash` 並符合所有 Bash 命令。作為拒絕規則，兩種形式都會從 Claude 的上下文中移除該工具。

工具在逐字稿和權限對話框中顯示的標籤可能與其規範名稱不同。例如，逐字稿中標記為 `Stop Task` 的工具具有規範名稱 `TaskStop`。權限規則和 [hook matcher](https://code.claude.com/docs/zh-TW/hooks.md) 不會比對標籤，因此寫成 `Stop Task` 的規則不符合。對於拒絕和詢問規則，[啟動警告](https://code.claude.com/docs/zh-TW/errors.md#matches-no-tool)會指出這一點。請使用[工具參考](https://code.claude.com/docs/zh-TW/tools-reference.md)中列出的規範名稱。

### 使用指定符進行細粒度控制

在括號中新增指定符以符合特定工具使用：

| 規則 | 效果 |
| :- | :- |
| `Bash(npm run build)` | 符合確切命令 `npm run build` |
| `Read(./.env)` | 符合讀取目前目錄中的 `.env` 檔案 |
| `WebFetch(domain:example.com)` | 符合對 example.com 的擷取請求 |

### 按輸入參數進行符合

拒絕和詢問規則可以使用 `Tool(param:value)` 符合任何內建工具上的頂層輸入參數。

若要符合 MCP 工具上的參數，請使用 [`--disallowedTools`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 傳遞拒絕規則。當 Claude Code 載入設定檔時，它會跳過任何具有括號的 `mcp__` 規則。Claude Code 在互動式工作階段開始時在無效設定對話框中列出跳過的規則，以及在 [`claude doctor`](https://code.claude.com/docs/zh-TW/debug-your-config#check-resolved-settings) 輸出中列出。

當 Claude 呼叫該工具且該參數設定為該確切值時，參數規則會符合。允許規則對於一個參數值不會確立該呼叫整體是安全的，因此允許規則繼續使用每個工具自己的指定符語法。這適用於工具接受的任何純量參數：

| 規則 | 符合 |
| :- | :- |
| `Agent(model:opus)` | 要求 Opus 模型層級的 Agent 呼叫 |
| `Agent(isolation:worktree)` | 要求 git worktree 的 Agent 呼叫 |
| `Bash(run_in_background:true)` | 在背景執行的 Bash 呼叫 |

參數符合遵循這些規則：

* 參數名稱必須是工具輸入的直接欄位，例如 Agent 工具上的 `model`。巢狀在物件或陣列內的欄位不可符合
* 每個規則命名一個參數。若要在 `model` 和 `isolation` 上設定閘道，請寫入兩個規則 `Agent(model:opus)` 和 `Agent(isolation:worktree)`，而不是在一個規則中組合它們
* 值支援 `*` 作為符合任何字元序列的萬用字元，因此 `Agent(isolation:*)` 符合任何明確的隔離值。沒有 `*` 時，符合是確切的
* 模型省略的參數永遠不會被符合，因此 `Agent(model:*)` 不符合留下 `model` 未設定的呼叫
* 值與 Claude 傳送的字面輸入進行比較，在任何正規化之前。`Agent(model:opus)` 符合別名 `opus` 但不符合完整模型 ID
* `Skill(skill:<name>)` 拒絕規則改為[符合該技能在其任何名稱下](https://code.claude.com/docs/zh-TW/skills.md#restrict-claude%E2%80%99s-skill-access)，例如其別名或顯示名稱
* 使用 [`--verbose`](https://code.claude.com/docs/zh-TW/cli-reference) 執行以查看每個工具呼叫中的確切參數名稱和值
* 冒號周圍的空格被忽略

您無法以這種方式符合工具的主要內容欄位：Bash 和 PowerShell 的 `command`、Read、Edit 和 Write 的 `file_path`、Grep 和 Glob 的 `path`、NotebookEdit 的 `notebook_path`，以及 WebFetch 的 `url`。像 `Bash(command:rm *)` 這樣的規則可能會被複合命令繞過，因此 Claude Code 會忽略它並在啟動時發出警告。改用 `Bash(rm *)`、`Read(./path)` 或 `WebFetch(domain:host)`。

### 萬用字元模式

Bash 規則中的 `*` 符合任何文字（包括空格），因此一個規則涵蓋一系列命令。沒有 `*` 的規則符合一個確切命令。

> [!WARNING]
>
> 將 `*` 放在子命令之後。在 `git log --oneline main` 中，`git` 是程式，`log` 是子命令，是決定程式執行什麼的詞。Claude Code 將第一個 `*` 之前的所有內容按原樣符合，因此這些詞是限制規則的內容：`Bash(git log *)` 僅允許 `git log` 命令，而 `Bash(git *)` 允許每個 git 命令。Claude Code [在啟動時警告](https://code.claude.com/docs/zh-TW/errors.md#has-a-wildcard-before-the-rest-of-the-command)關於在子命令之前有 `*` 的允許規則，例如 `Bash(git * main)`。

寫下您希望 Claude 執行而不詢問的命令，並將變化的部分替換為 `*`。使用此設定，Claude Code 執行 npm 指令碼和 git 提交而不詢問，並拒絕以 `git push` 開頭的命令。以另一種方式寫入的推送，例如 `git -C . push`，不符合；請參閱 [Bash 規則不符合的內容](#bash-rule-limits)。

```json theme={null}
{
  "permissions": {
    "allow": [
      "Bash(npm run *)",
      "Bash(git commit *)"
    ],
    "deny": [
      "Bash(git push *)"
    ]
  }
}
```

`*` 可以出現在規則中的任何位置：開始、中間或結尾。每一行顯示一個規則、它符合的命令，以及附近它不符合的命令：

| 您寫入 | 符合 | 不符合 |
| :- | :- | :- |
| `Bash(npm run build)` | `npm run build` | `npm run build --watch` |
| `Bash(npm run *)` | `npm run build`、`npm run test --watch`、`npm run` | `npm install` |
| `Bash(git log * main)` | `git log --oneline main`、`git log -5 main`、`git log --output=<file> main` | `git log main`、`git push origin main` |
| `Bash(git * main)` | `git merge main`、`git push origin main`、`git -c core.fsmonitor=<script> diff main` | `git log` |
| `Bash(* --version)` | `node --version`、`bash -c 'echo hi' --version` | `node -v` |
| `Bash(ls *)` | `ls -la`、`ls` | `lsof` |
| `Bash(ls*)` | `ls -la`、`lsof` | |
| `Bash(* --help *)` | `npm --help x` | `npm --help` |

三個符合規則產生這些行：

* **`*` 代表其位置中的任何文字。** 在 `Bash(git * main)` 中，它代表子命令，因此 Claude Code 符合每個 git 子命令和它之前的每個選項。這包括 `-c`，它使 git 執行您命名的程式。在 `Bash(* --version)` 中，`*` 代表程式，因此任何程式都符合。
* **末尾的 `*`（前面有空格）也符合裸命令。** `Bash(ls *)` 符合 `ls`，而 `Bash(git log *)` 符合 `git log`。這僅在尾部 `*` 是規則的唯一萬用字元時成立：`Bash(* --help *)` 符合 `npm --help x` 但不符合 `npm --help`。
* **尾部 `*` 前的空格是規則的一部分。** `Bash(ls *)` 在 `ls` 後需要空格，因此 `lsof` 不符合。`Bash(ls*)` 沒有空格，因此它也符合 `lsof`。

`:*` 後綴是寫入尾部萬用字元的等效方式，因此 `Bash(ls:*)` 符合與 `Bash(ls *)` 相同的命令。

權限對話框在您為命令前綴選擇「是，不要再問」時寫入空格分隔的形式。`:*` 形式僅在模式末尾被識別。在像 `Bash(git:* push)` 這樣的模式中，冒號被視為字面字元，不會符合 git 命令。

### 工具名稱萬用字元

拒絕和詢問規則也接受工具名稱位置中的 glob 模式。該模式必須符合完整工具名稱：`"*"` 符合每個工具，而 `"mcp__*"` 符合所有伺服器上的每個 MCP 工具。由裸名稱 glob 拒絕規則符合的工具會從 Claude 的上下文中移除，與裸工具名稱相同，包括 [`EndConversation`](https://code.claude.com/docs/zh-TW/tools-reference#endconversation-tool-behavior) 例外：glob 拒絕無法在任何其他工具保留時移除它，而 glob 詢問永遠不會提示它。此設定拒絕每個 MCP 工具：

```json theme={null}
{
  "permissions": {
    "deny": [
      "mcp__*"
    ]
  }
}
```

允許規則僅在字面 `mcp__<server>__` 前綴之後接受工具名稱 glob。伺服器區段必須無 glob，以便規則命名您設定的特定伺服器。`mcp__puppeteer__*` 符合來自 `puppeteer` 伺服器的每個工具，而 `mcp__github__get_*` 符合其 `get_` 工具。未錨定的允許 glob（例如 `"*"`、`"B*"` 或 `"mcp__*"`）會被跳過，不會自動核准任何內容。

拒絕或詢問規則，其工具名稱不符合任何已知工具，會產生[啟動警告](https://code.claude.com/docs/zh-TW/errors.md#matches-no-tool)以捕捉拼寫錯誤。包含 `_` 或 `*` 的工具名稱不受檢查限制，Claude Code 已移除的工具名稱（例如 `TaskOutput`）也是如此。

## 特定工具的權限規則

### Bash

Bash 規則會比對整個命令文字，其中 `*` 代表任意文字。[萬用字元模式](#wildcard-patterns)說明了每種規則形式會比對哪些命令，以及 `*` 應放在哪裡。本節其餘部分涵蓋 Claude Code 如何比對複合命令與包裝器、前綴規則無法核准哪些包裝器與 `find` 動作、規則不會比對的內容、唯讀命令，以及重新導向。

#### 複合命令

> [!TIP]
>
> Claude Code 能辨識 shell 運算子，因此像 `Bash(safe-cmd *)` 這樣的規則不會授予它執行 `safe-cmd && other-cmd` 命令的權限。可辨識的命令分隔符號為 `&&`、`||`、`;`、`|`、`|&`、`&` 以及換行。每個子命令都必須獲得允許，複合命令才能不經提示即執行，例如因為該子命令符合某條允許規則，或是[唯讀命令](#read-only-commands)。

只要有任何子命令符合，拒絕規則與詢問規則就會套用，包括巢狀於子 shell、命令替換或控制流程主體（例如 `for` 迴圈）內的命令。像 `Bash(git clean *)` 這樣的詢問規則，對於 `cd /tmp && git clean -f` 或 `echo "$(git clean -f)"` 仍會提示您，即使在[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)下也是如此。

當 `&&` 或 `||` 後面沒有任何內容時，例如 `npm test &&`，Claude Code 會將該命令視為無法解析，且不會為了比對允許規則而將其拆分為子命令，因此像 `Bash(npm *)` 這樣的規則不會核准它。

當您以「Yes, and don't ask again」核准複合命令時，Claude Code 會為每個需要核准的子命令分別儲存一條規則，而不是為完整的複合字串儲存單一規則。例如，核准 `git status && npm test` 會為 `npm test` 儲存一條規則，因此日後不論 `&&` 前面是什麼，`npm test` 的呼叫都會被辨識。像 `cd` 進入工作目錄外部目錄這類子命令，會為該路徑產生自己的 Read 規則。單一複合命令最多可儲存 5 條規則。

#### 包裝器

在比對 Bash 規則之前，Claude Code 會剝除一組固定的包裝器，因此像 `Bash(npm test *)` 這樣的規則也會比對 `timeout 30 npm test`。會被剝除的包裝器為 `timeout`、`time`、`nice`、`nohup` 與 `stdbuf`，以及 shell 內建命令 `command` 與 `builtin`，還有 zsh 的 `noglob`。它們都會將其引數作為實際命令執行。有兩種相關形式不會被剝除：查詢形式 `command -v`（它查詢命令而非執行命令），以及 zsh 的 `nocorrect`。

Claude Code 也會剝除開頭對某些已知安全環境變數的指派，因此 `Bash(npm test *)` 會比對 `NODE_ENV=test npm test`。允許規則不會越過對任何其他變數的指派進行比對。拒絕或詢問規則則會越過任何開頭的指派進行比對，因此拒絕清單中的 `Bash(rm *)` 仍會比對 `FOO=bar rm -rf tmp/`。

不帶參數的 `xargs` 也會被剝除，因此 `Bash(grep *)` 會比對 `xargs grep pattern`。只有在 `xargs` 沒有旗標時才會剝除：像 `xargs -n1 grep pattern` 這樣的呼叫會被當作 `xargs` 命令比對，因此為內部命令撰寫的規則不會涵蓋它。

此包裝器清單為內建，無法設定。`direnv exec`、`devbox run`、`mise exec`、`npx` 與 `docker exec` 等開發環境執行器不在清單中。由於這些工具會將其引數作為命令執行，像 `Bash(devbox run *)` 這樣的規則會比對 `run` 之後的任何內容，包括 `devbox run rm -rf .`。若要核准在環境執行器內的工作，請撰寫同時包含執行器與內部命令的特定規則，例如 `Bash(devbox run npm test)`。為每個您想允許的內部命令各新增一條規則。

#### Exec 包裝器與 `find` 動作

像 `Bash(watch *)` 或 `Bash(find *)` 這樣的前綴規則無法自動核准下列命令，因此在 Manual 模式下它們會提示：

* **Exec 包裝器**：例如 `watch`、`setsid`、`ionice` 與 `flock`
* **`find`**：帶有會執行命令、刪除檔案或寫入檔案的動作，例如 `-exec`、`-delete`、`-rm` 或 `-fprint`，或帶有 `-files0-from`（它會從檔案讀取要搜尋的路徑）

若要核准其中不含 `*` 的特定呼叫，請為完整的命令字串撰寫完全比對規則，例如 `Bash(find build -type f -delete)`。

當命令含有 `*` 時，例如 `find . -name '*.tmp' -delete`，Claude Code 會將規則解讀為[萬用字元模式](#wildcard-patterns)而非完全比對，因此該命令仍會提示。請在每次提示時核准，或使用針對它回傳 `"allow"` 的 [PreToolUse hook](https://code.claude.com/docs/zh-TW/hooks.md#pretooluse-decision-control)。

#### Bash 規則不會比對的內容

Bash 規則會在 Claude Code 拆分[複合命令](#compound-commands)並剝除[包裝器](#process-wrappers)之後，比對 Claude 撰寫的命令文字。它不會比對以不同形式呼叫的同一程式，因此拒絕或詢問規則涵蓋的是 Claude 通常產生的呼叫方式，並不是圍繞該程式的安全邊界。下列規則放在 `deny` 或 `ask` 中時，會阻止第一種形式，但不會阻止其他形式：

| 規則 | 會阻止 | 不會阻止 |
| :- | :- | :- |
| `Bash(curl *)` | `curl https://example.com` | `/usr/bin/curl https://example.com`、`sh -c 'curl https://example.com'` |
| `Bash(rm *)` | `rm -rf build/` | `/bin/rm -rf build/`、`bash -c 'rm -rf build/'` |
| `Bash(git push *)` | `git push origin main` | `git -C . push origin main`、`git -c push.default=current push origin main`、`git 'push' origin main` |

最後一欄中的命令由您的其他規則與權限模式決定。

若需要不依賴命令文字的檔案系統與網路強制執行，請使用[沙箱機制](https://code.claude.com/docs/zh-TW/sandboxing.md)。若要在命令執行前以您自己的邏輯檢查完整的命令文字，請使用 [PreToolUse hook](#extend-permissions-with-hooks)。

#### 唯讀命令

Claude Code 會將一組內建的 Bash 命令辨識為唯讀，並在每種模式下不經權限提示即執行它們，除非 [`permissions.blockReadsOutsideWorkingDirectories`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-blockreadsoutsideworkingdirectories) 針對工作目錄外部的路徑改變此行為。此組合包括 `ls`、`cat`、`echo`、`pwd`、`head`、`tail`、`grep`、`find`、`wc`、`which`、`diff`、`stat`、`du`、`cd`，以及 `git` 的唯讀形式。此組合無法設定；若要讓其中某個命令需要提示，請為它新增 `ask` 或 `deny` 規則。在自動模式下，這些命令也可能等待分類器的審查；請參閱[分類器如何評估動作](https://code.claude.com/docs/zh-TW/permission-modes.md#how-the-classifier-evaluates-actions)。

像 `ls > out.txt` 這樣的重新導向會對目標加上檢查。請參閱[重新導向](#redirections)。

對於所有旗標皆為唯讀的命令，允許使用未加引號的 glob 模式，因此 `ls *.ts` 與 `wc -l src/*.py` 會不經提示即執行。

在 Manual 模式下，此組合中的命令在下列情況仍會提示：

* **具有可寫入旗標之命令的未加引號 glob**：具有可寫入或可執行旗標的命令，例如 `find`、`sort`、`sed` 與 `git`，在出現未加引號的 glob 時會提示，因為 glob 可能展開成像 `-delete` 這樣的旗標。
* **指向其他 daemon 的 `docker`**：當命令帶有選擇不同 daemon 的旗標時，例如 `-H`、`--context`，或 Podman 的 `--url` 與 `--connection`，`docker` 的唯讀形式會提示。
* **帶有開啟路徑旗標的 `file`**：當 `file` 傳入 `-m`/`--magic-file` 或 `-f`/`--files-from` 時會提示，因為這些旗標會讓 `file` 開啟旗標值中所指定的路徑。
* **可能印出環境變數的 `ps`**：當 `ps` 的某個引數可能作為 `e` 選項時會提示，例如 `ps auxe` 或 `ps aux -e`，因為該選項會印出程序的環境變數。`ps aux` 與 `ps -ef` 會不經提示即執行。對 `ps aux -e` 等帶連字號形式的檢查需要 Claude Code v2.1.290 或更新版本。
* **Windows 上的網路路徑**：引數包含網路（UNC）路徑（例如 `\\server\share\file`）的命令會提示，因為存取網路路徑可能會將您的 Windows 憑證傳送給其所指定的主機。相同的檢查也適用於 [PowerShell 工具](https://code.claude.com/docs/zh-TW/tools-reference.md#powershell-tool)命令。
* **寫入特殊 shell 變數**：設定、取消設定或迴圈遍歷某些特殊 shell 變數（例如 `PATH` 或 `IFS`）的命令，即使命令的其餘部分為唯讀也會提示。
* **分析無法解析的命令**：當 Claude Code 無法完整解析某個命令時，它會要求核准，而不是將該命令視為唯讀。超過 10,000 個字元的命令一律會提示，因為它們超出分析所能解析的範圍。

`cd` 進入工作目錄或[額外目錄](#working-directories)內的路徑也屬於唯讀，而像 `cd packages/api && ls` 這樣的複合命令，當每個部分各自符合條件時，會不經提示即執行。下列組合即使每個部分都是唯讀也會提示：

* **`cd` 搭配 `git`**：當 `cd` 切換到不同目錄時會提示，因為在新目錄中執行 `git` 可能會執行該目錄的 hook。目標解析為目前工作目錄的 `cd` 不會產生任何作用，也不會觸發提示。
* **`cd` 搭配重新導向**：當 Claude Code 無法判斷 `cd` 執行後重新導向目標會相對於哪個目錄解析時會提示。唯一重新導向目標為 `/dev/null` 的命令，例如 `cd app; grep -r pattern . 2>/dev/null`，不會提示，因為 `/dev/null` 不依賴工作目錄。

> [!WARNING]
>
> 試圖限制命令引數的 Bash 權限模式相當脆弱。例如，`Bash(curl http://github.com/ *)` 的用意是將 curl 限制為 GitHub URL，但不會比對下列變化形式：
>
> * URL 前面的選項：`curl -X GET http://github.com/...`
> * 不同的協定：`curl https://github.com/...`
> * 重新導向：`curl -L http://short.example.com/xyz`，它會重新導向至 GitHub
> * 變數：`URL=http://github.com && curl $URL`
>
> 若要更可靠地篩選 URL，請考慮：
>
> * **限制 Bash 網路工具**：使用拒絕規則阻止 `curl`、`wget` 及類似命令，然後針對允許的網域使用帶有 `WebFetch(domain:github.com)` 權限的 WebFetch 工具。拒絕規則不會比對以路徑呼叫或在 `sh -c` 內呼叫的同一程式，因此當限制必須確實生效時，請搭配[沙箱網路允許清單](https://code.claude.com/docs/zh-TW/sandboxing.md#network-isolation)使用；請參閱 [Bash 規則不會比對的內容](#bash-rule-limits)
> * **使用 PreToolUse hook**：實作一個 hook，驗證 Bash 命令中的 URL 並封鎖不允許的網域
> * **新增 CLAUDE.md 指引**：在 `CLAUDE.md` 中描述您允許的 curl 模式。這會影響 Claude 的嘗試方向，但不會強制執行邊界，因此請搭配上述其中一個選項使用
>
> 請注意，單獨使用 WebFetch 並不會阻止網路存取。如果允許 Bash，Claude 仍可使用 `curl`、`wget` 或其他工具存取任何 URL。

#### 重新導向

當命令重新導向輸出或輸入時，Claude Code 會依據您的檔案規則檢查重新導向目標，就如同 Claude 直接寫入或讀取該檔案一樣：

* **輸出重新導向**：對於 `> file`、`>> file` 或 `2> file`，檢查涵蓋您的 `Edit` 允許與拒絕規則、[受保護路徑](https://code.claude.com/docs/zh-TW/permission-modes.md#protected-paths)以及[工作目錄](#working-directories)。像 `Bash(git commit *)` 這樣的規則允許的是命令，而非目標。以 `~` 開頭或包含 glob 字元的目標需要您的核准。
* **輸入重新導向**：對於 `< file`，檢查涵蓋您的 `Read` 允許與拒絕規則以及工作目錄。工作目錄外部的目標需要您的核准，除非有允許規則涵蓋它。包含 glob 模式的目標，或在同一命令中位於 `cd` 之後的相對路徑，即使有允許規則涵蓋也需要您的核准。Claude Code 在 v2.1.257 及更新版本中會檢查輸入目標。

背後沒有檔案的目標不會被檢查：`/dev/null`、`2>&1` 與 `<&3` 等檔案描述符形式，以及 here-doc 與 here-string。

Claude Code 也會檢查 `tee` 命令寫入的檔案，包括在像 `make | tee build.log` 這樣的管線中。檢查涵蓋您的 `Edit` 允許與拒絕規則、[受保護路徑](https://code.claude.com/docs/zh-TW/permission-modes.md#protected-paths)以及[工作目錄](#working-directories)。像 `Bash(tee *)` 這樣的允許規則不會涵蓋工作目錄外部的目的地。Claude Code 在 v2.1.269 及更新版本中會檢查 `tee` 目標。

### PowerShell

PowerShell 權限規則使用與 [Bash 規則](#wildcard-patterns)相同的形式，而不帶參數的 `PowerShell` 或 `PowerShell(*)` 會比對每個命令。下列設定允許 `Get-ChildItem` 與 `git commit` 命令，同時封鎖 `Remove-Item`：

```json theme={null}
{
  "permissions": {
    "allow": [
      "PowerShell(Get-ChildItem *)",
      "PowerShell(git commit *)"
    ],
    "deny": [
      "PowerShell(Remove-Item *)"
    ]
  }
}
```

常見的別名會在比對前先正規化。針對 cmdlet 名稱撰寫的規則也會比對到這些別名，因此 `PowerShell(Get-ChildItem *)` 也會比對到 `gci`、`ls` 和 `dir`。比對不區分大小寫。

Claude Code 會解析 PowerShell AST，並獨立檢查複合命令中的每個命令。管線運算子 `|`、陳述式分隔符號 `;`，以及在 PowerShell 7+ 上的鏈結運算子 `&&` 與 `||`，會將複合命令拆分為子命令。每個子命令都必須獲得允許，複合命令才能不經提示即執行，例如符合某條允許規則。

### Read 和 Edit

若要封鎖 Claude 的檔案工具讀取某個檔案或目錄，請為其路徑新增 `Read` 拒絕規則，例如 `Read(./.env)` 或 `Read(./secrets/**)`；[排除敏感檔案](https://code.claude.com/docs/zh-TW/settings-reference.md#exclude-sensitive-files)中有可直接貼上的範例。如果您的專案有 `.claudeignore` 檔案，它不會有任何作用，因此請將其項目移至 `Read` 拒絕規則中。

#### `Read` 與 `Edit` 規則涵蓋的範圍

`Edit` 規則適用於所有編輯檔案的內建工具。Claude 會盡力將 `Read` 規則套用至所有讀取檔案的內建工具（例如 Grep 與 Glob）、提示詞中的 `@file` 提及，以及已連線的 [IDE](https://code.claude.com/docs/zh-TW/vs-code.md#the-built-in-ide-mcp-server) 與 Claude 共用的選取內容與開啟檔案脈絡。

`Read(path)` 拒絕規則也適用於您貼到提示詞中的圖片路徑，以及您 @ 提及的目錄：

* **圖片路徑**：當您在終端機中將圖片路徑貼上或將圖片檔案拖曳到提示詞中，且規則比對到該路徑時，Claude Code 不會附加該圖片。如果貼上的內容中沒有其他圖片，該路徑會以文字形式保留在您的提示詞中。
* **目錄**：[Claude 收到的清單](https://code.claude.com/docs/zh-TW/common-workflows.md#reference-files-and-directories)會省略規則比對到的檔案與目錄名稱。

Claude Code 在 v2.1.290 及更新版本中會檢查貼上的圖片路徑與目錄清單。

`Read` 拒絕規則也會封鎖同一路徑上的 [Edit 與 Write 工具](https://code.claude.com/docs/zh-TW/errors.md#file-is-covered-by-a-read-deny-rule)，包括在該處建立新檔案。NotebookEdit 不在涵蓋範圍內，因此請為任何工具都不得變更的路徑新增 `Edit` 拒絕規則。對於 Write 工具，此檢查需要 Claude Code v2.1.228 或更新版本。

> [!WARNING]
>
> Read 與 Edit 拒絕規則適用於 Claude 的內建檔案工具、Claude Code 在 Bash 中辨識的檔案命令（例如 `cat`、`head`、`tail`、`sed` 與 `tee`），以及 Bash [重新導向](#redirections)的目標（例如 `> file` 與 `< file`）。它們不適用於未指名檔案即讀取檔案的命令，例如從包含該檔案的目錄執行的 `grep -r pattern .`，也不適用於間接讀取或寫入檔案的任意子程序，例如自行開啟檔案的 Python 或 Node 腳本。若需要在作業系統層級強制執行、封鎖所有程序存取某個路徑，請[啟用沙箱](https://code.claude.com/docs/zh-TW/sandboxing.md)。

#### `Write(path)`、`NotebookEdit(path)` 與 `Glob(path)` 規則永遠不會比對

Claude Code 只會依據 `Edit(path)` 與 `Read(path)` 規則檢查檔案權限。如果您為 `Write`、`NotebookEdit`、`Glob` 或舊版 `MultiEdit` 撰寫路徑規則，Claude Code 會接受該規則，但永遠不會以它比對任何讀取或編輯。

請使用 `Edit(docs/**)` 取代 `Write(docs/**)`、`NotebookEdit(docs/**)` 或 `MultiEdit(docs/**)`，並使用 `Read(docs/**)` 取代 `Glob(docs/**)`。若要比對 Write、NotebookEdit 或 Glob 工具的每次使用（不論路徑為何），請只撰寫工具名稱。

#### 路徑模式如何比對

Read 與 Edit 規則皆使用 [gitignore](https://git-scm.com/docs/gitignore) 模式語法，具有四種不同的模式類型：

| 模式 | 意義 | 範例 | 比對 |
| - | - | - | - |
| `//path` | 從檔案系統根目錄起算的絕對路徑 | `Read(//Users/alice/secrets/**)` | `/Users/alice/secrets/**` |
| `~/path` | 從家目錄起算的路徑 | `Read(~/Documents/*.pdf)` | `/Users/alice/Documents/*.pdf` |
| `/path` | 相對於設定來源的路徑 | `Edit(/src/**/*.ts)` | 在專案設定中為 `<primary working directory>/src/**/*.ts` |
| `path` 或 `./path` | 相對於目前目錄的路徑 | `Read(*.env)` | `<cwd>/*.env` |

> [!WARNING]
>
> 像 `/Users/alice/file` 這樣的模式並不是絕對路徑。單一開頭斜線會錨定在設定來源，而非檔案系統根目錄。請使用 `//Users/alice/file` 表示絕對路徑。

##### 模式錨定的位置

`/path` 模式會錨定在與定義它的設定來源相關聯的目錄，因此同一條規則會依您放置的位置而比對不同的位置：

| 規則定義於 | `/path` 解析為 |
| :- | :- |
| 位於 `.claude/settings.json` 的專案設定 | `<primary working directory>/path` |
| 位於 `.claude/settings.local.json` 的本機設定 | `<primary working directory>/path` |
| 位於 `~/.claude/settings.json` 的使用者設定 | `~/.claude/path` |
| 以 `--settings <file>` 傳入的檔案 | `<directory of file>/path` |
| CLI 旗標或工作階段規則 | `<primary working directory>/path` |

透過 `/permissions` 新增的規則，會依照您將它儲存至的設定檔所對應的那一列。

本機設定規則會錨定在工作階段的[主要工作目錄](#working-directories)，而不是 Claude Code [儲存該檔案](#permission-system)的儲存庫根目錄。在從儲存庫根目錄啟動的工作階段中，這兩個目錄相同；在 [worktree](https://code.claude.com/docs/zh-TW/worktrees.md) 工作階段中，像 `Edit(/src/**)` 這樣的共用規則會比對該 worktree 自己的 `src/` 目錄。

使用者設定中像 `Read(/secrets/**)` 這樣的拒絕規則，封鎖的是 `~/.claude/secrets/**`，而不是您專案中的 `secrets` 目錄。若要在使用者設定中撰寫適用於每個專案內部的規則，請改用 `//` 絕對路徑或 `~/` 相對於家目錄的路徑。

在 Windows 上，路徑會在比對前正規化為 POSIX 形式。`C:\Users\alice` 會變成 `/c/Users/alice`，因此請使用 `//c/**/.env` 來比對該磁碟機上任何位置的 `.env` 檔案。若要跨所有磁碟機比對，請使用 `//**/.env`。

範例：

* `Edit(/docs/**)`：編輯 `<primary working directory>/docs/` 中的內容，而不是 `/docs/` 或 `<primary working directory>/.claude/docs/`
* `Read(~/.zshrc)`：讀取您家目錄的 `.zshrc`
* `Edit(//tmp/scratch.txt)`：編輯絕對路徑 `/tmp/scratch.txt`
* `Read(src/**)`：作為允許規則時，只讀取 `<current-directory>/src/`；作為拒絕或詢問規則時，會比對目前目錄下任何深度的 `src` 目錄

##### 模式比對的深度

規則只會比對其錨點下的檔案；在此範圍內，比對深度取決於模式形式，以及（對於單一區段目錄模式而言）規則類型，如下所述。單純的檔名遵循 gitignore 語意並在任何深度比對，因此 `Read(.env)` 與 `Read(**/.env)` 是等價的：

| 拒絕規則 | 會封鎖 | 不會封鎖 |
| - | - | - |
| `Read(.env)` 或 `Read(**/.env)` | 目前目錄或其下的任何 `.env` | 父目錄或其他專案中的 `.env` |
| `Read(//**/.env)` | 檔案系統上任何位置的任何 `.env` | 無；此規則錨定在檔案系統根目錄 |

具有單一目錄區段的相對模式（例如 `src/**`）會依規則類型在不同深度比對：

* **允許規則**：`Edit(src/**)` 只比對 `<cwd>/src` 及其下的檔案。若要允許任何深度的目錄名稱，請撰寫 `Edit(**/src/**)`。
* **拒絕與詢問規則**：`Read(secrets/**)` 會比對目前目錄下任何深度名為 `secrets` 的目錄，因此該規則也適用於巢狀的副本。

其他所有模式形式在每種規則類型中都以相同深度比對：`Edit(/src/**)` 與 `Edit(src/components/**)` 只在其錨定位置比對，而 `Edit(**/src/**)` 會在任何深度比對。

下列範例以一個具有頂層 `src/` 目錄以及位於 `vendor/` 下之巢狀副本的專案，展示各種模式形式：

```text theme={null}
<current-directory>/
├── src/
│   └── app.ts
└── vendor/
    └── pkg/
        └── src/
            └── lib.js
```

| 規則 | 比對 `src/app.ts` | 比對 `vendor/pkg/src/lib.js` |
| :- | :- | :- |
| `Edit(src/**)` 作為允許規則 | 是 | 否 |
| `Edit(src/**)` 作為拒絕或詢問規則 | 是 | 是 |
| `Edit(/src/**)` 於任何規則類型 | 是 | 否 |
| `Edit(**/src/**)` 於任何規則類型 | 是 | 是 |

> [!NOTE]
>
> 在 gitignore 模式中，`*` 會在單一路徑區段內比對，且可出現在模式中的任何位置，而 `**` 會跨目錄比對。

#### 特殊字元與 `!` 否定

當您以「Yes, and don't ask again」核准檔案路徑時，Claude Code 會跳脫該路徑中的 gitignore 模式字元，例如 `[`、`]` 與 `*`，因此產生的規則只會比對您所核准的字面路徑。您自行撰寫的規則不會被跳脫。

您不需要跳脫路徑中的括號，因此 `Edit(./Finance (2024)/**)` 會比對拼寫如此的 `Finance (2024)` 資料夾。

路徑無法作為 gitignore 模式使用的拒絕或詢問規則，仍會保護該確切路徑。模式無法使用的允許規則不會核准任何內容。

以 `!` 開頭的拒絕或詢問模式是 gitignore 否定。它會從列在它之前的 `path` 或 `./path` 規則中排除它所比對的路徑。在單一設定檔的 `deny` 清單中，`Read(*.env)` 後接 `Read(!sample.env)` 會封鎖任何深度中名稱以 `.env` 結尾的每個檔案，但名為 `sample.env` 的檔案除外。列在最前面的 `!` 規則不會排除任何內容。

排除只會影響來自同一來源的規則。專案設定或 `--disallowedTools` 中的 `Read(!.env)` 不會取消來自受管設定或任何其他設定檔的 `Read(./.env)` 拒絕規則。

有兩項限制會縮小 `!` 模式所能排除的範圍：

* 即使 `!` 後面接著 `/`、`~/` 或 `//`，Claude Code 仍會相對於目前目錄解讀 `!` 模式，因此該模式無法影響以這些前綴錨定的規則。`Read(!~/notes/public/**)` 不會從 `Read(~/notes/**)` 中排除任何內容。
* 排除無法重新開放被規則整體封鎖之目錄內的檔案。在 `Read(secrets/**)` 與 `Read(!secrets/public/**)` 的情況下，Claude Code 仍會封鎖 `secrets/public` 以及 `secrets` 的其餘部分。

#### 符號連結

當 Claude 請求的檔案路徑經過符號連結時，權限檢查會涵蓋兩個路徑：Claude 請求的路徑，以及它解析後的檔案。這適用於 macOS、Linux 與 Windows 上的符號連結，以及 Windows 上的目錄連接點（junction）。

##### 規則如何比對經符號連結的路徑

允許規則與拒絕規則對請求的路徑與其解析後的檔案有不同的處理方式：

* **允許規則**：只有在請求的路徑與其解析後的檔案都符合時才會套用。透過允許目錄內、指向該目錄外部的符號連結所進行的讀取，不符合該規則。
* **拒絕規則**：只要請求的路徑或其解析後的檔案任一符合就會套用。指向被拒絕檔案的符號連結本身也會被拒絕。例如，在允許 `Read(./project/**)` 且拒絕 `Read(~/.ssh/**)` 的情況下，位於 `./project/key` 且指向 `~/.ssh/id_rsa` 的符號連結會被封鎖：目標不符合允許規則，且符合拒絕規則。

在 macOS 與 Linux 上，透過符號連結目錄以 `//`、`~/` 或 `/` 模式撰寫的拒絕或詢問規則，也會套用於該目錄的實際位置。例如，在 `/etc` 解析為 `/private/etc` 的 macOS 上，`Read(//etc/**)` 也會封鎖 `/private/etc/hosts`。在 v2.1.268 之前，透過符號連結目錄撰寫的拒絕或詢問規則，不會套用於以其實際位置指定的路徑。

Grep 與 Glob 會搜尋 `path` 引數所解析到的目錄。Claude Code 會對該目錄套用 `Read` 拒絕規則。

##### 經由符號連結的附件

`Read` 拒絕規則也涵蓋下列附件，對每個附件依其指名的路徑或解析後的檔案進行比對。當規則比對到附件時，Claude Code 會將該附件排除在對話之外：

* **`@` 提及**：您在提示詞中提及的檔案或目錄。被拒絕的檔案不會在對話中留下任何內容，而[目錄的清單](#read-and-edit)會省略規則所涵蓋的名稱。
* **貼上的圖片**：您在終端機中將其路徑貼上或拖曳到提示詞中的圖片
* **已變更的檔案**：Claude Code 在磁碟上的檔案變更後重新讀取的檔案
* **IDE 脈絡**：已連線 IDE 共用的選取內容與開啟檔案脈絡

當啟用 [`permissions.blockReadsOutsideWorkingDirectories`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-blockreadsoutsideworkingdirectories)，或在 [`--restricted`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 工作階段中，若這些附件來自該設定或旗標會拒絕 Claude 檔案讀取的路徑，也會被排除。

在您 `@` 提及的檔案位置出現下列這行文字，表示 Claude Code 無法判斷該路徑指向何處，例如因為其符號連結形成迴圈：

```text theme={null}
Referenced <path> (not read: could not be examined)
```

Claude 會被告知改用其檔案工具讀取該路徑，若 Claude Code 只是沒有足夠時間檢查該路徑，這樣做便可能成功。

當路徑的符號連結無法解析時，該讀取也會被[拒絕](https://code.claude.com/docs/zh-TW/errors.md#refusing-after-a-symlink-changed)，因此請修正磁碟上的連結，或以可解析的路徑 `@` 提及該檔案。

##### 經由符號連結的寫入

如果 Claude 要求編輯或寫入的路徑本身是符號連結，Edit 與 Write 工具會[拒絕寫入並引導 Claude 前往連結的目標](https://code.claude.com/docs/zh-TW/errors.md#refusing-after-a-symlink-changed)。

當通往檔案途中的某個目錄是符號連結，或由 Bash 或 PowerShell 命令執行寫入時，寫入仍可能經由符號連結進行。對於這些寫入，結果取決於寫入所解析到的檔案相對於您的[工作目錄](#working-directories)與[受保護路徑](https://code.claude.com/docs/zh-TW/permission-modes.md#protected-paths)的位置：

* **解析至工作目錄外部**：當請求的路徑位於您的工作目錄內，而其解析後的檔案不在其中時，該寫入在 [`acceptEdits` 模式](https://code.claude.com/docs/zh-TW/permission-modes#auto-approve-file-edits-with-acceptedits-mode)下不會被自動核准。在[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)下，除非有允許規則核准該寫入，否則會提示您，而不是由分類器決定。提示會指明寫入所解析到的路徑。
* **解析至請求路徑未指名的受保護路徑**：[受保護路徑表格](https://code.claude.com/docs/zh-TW/permission-modes.md#protected-paths)列出了每種權限模式下的結果，但在表格將寫入交由分類器處理之處，此類寫入會改為提示您。

##### 無法解析或會變更的路徑

當 Claude Code 無法判斷某個路徑在磁碟上指向何處時，例如因為其上的符號連結形成迴圈，Read、Edit 與 Write 工具會[拒絕該操作](https://code.claude.com/docs/zh-TW/errors.md#refusing-after-a-symlink-changed)。

當工具接著開啟已核准的檔案時，它會[確認該路徑仍解析至權限檢查所核准的位置](https://code.claude.com/docs/zh-TW/errors.md#refusing-after-a-symlink-changed)。

#### 網路路徑

當 Claude 的檔案讀取工具（例如 Read、Grep 與 Glob）從網路路徑讀取時，該讀取會經過獨立的權限檢查。網路路徑是可以連到另一部電腦的路徑：在 Windows 上是 UNC 路徑，例如 `\\server\share\file`；在 macOS 與 Linux 上是 `/net` 自動掛載路徑，例如 `/net/fileserver/notes.txt`。查詢這類路徑可能會連絡其所指定的主機，而在 Windows 上，該連絡可能會將您的憑證傳送給該主機。shell 命令有其各自的檢查：在 Manual 模式下，引數包含 UNC 路徑的唯讀 Bash 或 PowerShell 命令[在 Windows 上仍會提示](#read-only-commands)。

在 Claude Code v2.1.292 及更新版本中，下列每一項都會保留提示：

* **允許規則**：規則不會預先核准該讀取，包括針對整個工具的規則，例如 `Read`
* **PreToolUse hook**：回傳 `"allow"` 的 [hook](#extend-permissions-with-hooks) 不會略過提示
* **自動模式**：提示會交給您，而[分類器](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)不會決定該讀取

在 `dontAsk` 模式下，Claude Code 會拒絕該讀取而非提示。在 `bypassPermissions` 模式下，以及在可使用[略過權限](https://code.claude.com/docs/zh-TW/permission-modes.md#skip-all-checks-with-bypasspermissions-mode)的 plan mode 互動式終端機工作階段中，該讀取會在沒有此提示的情況下執行。

若要在沒有此提示的情況下讀取網路共用上的檔案，請先為該共用提供本機路徑：

* **Windows**：將共用對應至磁碟機代號，並在啟動 Claude Code 時以 `--add-dir` 傳入該磁碟機，如[工作目錄](#working-directories)所述。對於對應至 `Z:` 的共用，請在 PowerShell 中執行 `claude --add-dir Z:\`。
* **macOS 與 Linux**：將共用掛載至本機路徑，例如 `/mnt` 或 `/Volumes` 下的目錄，並從該處讀取檔案，如[工作目錄是網路路徑](https://code.claude.com/docs/zh-TW/errors.md#working-directory-is-a-network-path)所述

### WebFetch

WebFetch 規則使用 `domain:` 前綴，並比對所請求 URL 的主機名稱。比對不區分大小寫、支援 `*` 萬用字元，並會從規則與主機名稱兩者中剝除結尾的 `.`，因此 `example.com.` 與 `example.com` 會被視為相同。

* `WebFetch(domain:example.com)` 只比對對 `example.com` 的請求。若也要涵蓋 `api.example.com` 等子網域，請新增 `WebFetch(domain:*.example.com)` 規則
* `WebFetch(domain:*.example.com)` 會比對任何深度的子網域，例如 `api.example.com` 或 `a.b.example.com`，但不包括 `example.com` 本身
* `WebFetch(domain:*)` 會比對每個網域。它與不帶參數的 `WebFetch` 規則不同；請參閱[允許或拒絕每次擷取](#allow-or-deny-every-fetch)

在開頭的 `*.` 或單獨的 `*` 以外的任何位置，萬用字元只會比對兩個點之間的文字。`WebFetch(domain:example.*)` 會比對 `example.org`（其中 `*` 成為 `org`），但不會比對 `example.evil.com`（其中 `*` 必須成為 `evil.com` 並跨越一個點）。這可防止結尾萬用字元比對到攻擊者可能註冊的網域。

`WebFetch` 規則中的萬用字元需要 Claude Code v2.1.172 或更新版本才能比對擷取。

#### 允許或拒絕每次擷取

不帶參數的 `WebFetch` 規則是沒有 `domain:` 部分的工具名稱，例如 `"deny": ["WebFetch"]`。它與 `WebFetch(domain:*)` 都涵蓋每個 URL，但 Claude Code 套用它們的方式不同，而且只有 `domain:` 形式會同時將其網域加入沙箱的[允許或拒絕網域清單](https://code.claude.com/docs/zh-TW/sandboxing.md#network-isolation)。該章節列出沙箱所接受的萬用字元形式，以及新增單獨 `*` 的版本。

每一列顯示規則在 `allow` 清單與 `deny` 清單中的作用：

| 規則 | 在 `allow` 中 | 在 `deny` 中 |
| :- | :- | :- |
| `WebFetch` | Claude 擷取時不會提示您。不會改變沙箱化命令可連線的主機。 | Claude Code 會移除 `WebFetch` 工具，因此 Claude 完全無法擷取。不會改變沙箱化命令可連線的主機。 |
| `WebFetch(domain:*)` | Claude 擷取時不會提示您，且沙箱化命令可連線至任何主機。 | Claude Code 保留該工具並拒絕每次擷取，且沙箱化命令無法連線至任何主機。 |

這兩種形式在讀取 [artifact](https://code.claude.com/docs/zh-TW/artifacts.md)（Artifact 工具在 claude.ai 上發佈的頁面）時也有所不同。不帶參數的 `WebFetch` 拒絕或詢問規則不適用於這些讀取。涵蓋 `claude.ai` 或 `*.claudeusercontent.com` 內容主機的 `domain:` 規則，例如 `WebFetch(domain:claude.ai)` 或 `WebFetch(domain:*)`，會拒絕每次讀取或在讀取前提示。[`Artifact` 規則](https://code.claude.com/docs/zh-TW/artifacts#disable-artifacts)也有相同作用。

當規則封鎖讀取時，拒絕訊息會指明該規則。在 v2.1.268 之前，不帶參數的 `WebFetch` 拒絕規則會封鎖每次 artifact 讀取，而不帶參數的詢問規則會在每次讀取前提示。

若要讓 Claude 自由擷取，同時保持沙箱允許清單不變，請使用不帶參數的形式。下列 `settings.json` 即是如此：

```json theme={null}
{
  "permissions": {
    "allow": ["WebFetch"]
  }
}
```

當您要求 Claude 擷取頁面時，它會不經提示即擷取。當您要求它針對沙箱允許清單以外的主機執行[沙箱化](https://code.claude.com/docs/zh-TW/sandboxing.md)的 `curl` 時，Claude Code 仍會針對該主機提示您，因為不帶參數的規則並未將該主機加入允許清單。

在[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)下，Claude 則會在命令的[個別命令允許網域](https://code.claude.com/docs/zh-TW/sandboxing.md#per-command-allowed-domains-in-auto-mode)中指明該主機，交由分類器審查。

### MCP

若要比對來自某個 MCP 伺服器的每個工具，請撰寫 `mcp__<server>__*`。若要比對單一工具，請撰寫其完整名稱 `mcp__<server>__<tool>`。

* `mcp__puppeteer` 會比對 `puppeteer` 伺服器提供的任何工具
* `mcp__puppeteer__*` 使用萬用字元語法，同樣會比對 `puppeteer` 伺服器的所有工具
* `mcp__puppeteer__puppeteer_navigate` 會比對 `puppeteer` 伺服器提供的 `puppeteer_navigate` 工具

對於 `<server>`，請依該伺服器工具名稱中出現的方式撰寫伺服器名稱。下列範例展示針對包含特殊字元的名稱、來自外掛的伺服器，以及包含 `__` 或以 `_` 結尾的名稱所應撰寫的規則：

* **包含 `.` 或空格等字元的名稱**：這些字元會變成 `_`，因此對於您設定為 `my.server` 的伺服器，請撰寫 `mcp__my_server__*`
* **由外掛提供的伺服器**：`<server>` 採用[外掛範圍形式](https://code.claude.com/docs/zh-TW/mcp.md#plugin-provided-mcp-servers)，因此對於名為 `my-plugin` 之外掛中的 `database-tools` 伺服器，請撰寫 `mcp__plugin_my-plugin_database-tools__*`
* **包含 `__` 或以 `_` 結尾的 `<server>`**：請以完整名稱撰寫萬用字元形式 `mcp__<server>__*`。對於名為 `reports__v2` 的伺服器，請撰寫 `mcp__reports__v2__*`。不帶參數的 `mcp__reports__v2` 與較短的 `mcp__reports` 作為允許規則時不會比對其工具，因為 Claude Code 會將兩者都解讀為名為 `reports` 之伺服器的規則。

  不過，作為拒絕或詢問規則時，這兩個名稱也都會涵蓋 `reports__v2` 伺服器的每個工具。若只要涵蓋名為 `reports` 的伺服器，請以 `mcp__reports__<tool>` 形式為每個工具各撰寫一條規則，或重新命名其中一個伺服器。

如果您的組織已將某個 [claude.ai 連接器](https://code.claude.com/docs/zh-TW/mcp.md#organization-controls-on-connector-tools)工具設為 `ask`，且該設定在您的工作階段中傳達到 Claude Code，則針對該工具的允許規則不會生效：Claude Code 會在每次呼叫時提示，即使在 `auto` 與 `bypassPermissions` 模式下也是如此。在永不提示的 `dontAsk` 模式下，Claude Code 會改為拒絕該呼叫。Claude Code 自行擷取之連接器的工具會以 `mcp__claude_ai_<server>__<tool>` 形式出現。

在 Claude Desktop 應用程式的 [Cowork](https://claude.com/docs/cowork/overview) 工作階段中，Claude 會透過 Cowork 的 `mcp__workspace__bash` 工具而非內建的 `Bash` 工具執行 shell 命令，而 Cowork 同樣提供 `mcp__workspace__web_fetch` 用於網頁擷取。Claude Code 也會將指名整個 `Bash` 或 `WebFetch` 工具的拒絕規則套用至這些 Cowork 工具，因此受管的 `Bash` 拒絕規則會阻止 Claude 在 Cowork 中執行 shell 命令。當 Claude Code 封鎖這類呼叫時，訊息會指明該 Cowork 工具：`Permission to use mcp__workspace__bash has been denied.` 允許規則不會延續：Claude Code 永遠不會將 `Bash` 允許規則套用至 `mcp__workspace__bash`。

### Agent (subagents)

使用 `Agent(AgentName)` 規則來控制 Claude 可以使用哪些 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md)：

* `Agent(Explore)` 會比對 Explore subagent
* `Agent(Plan)` 會比對 Plan subagent
* `Agent(my-custom-agent)` 會比對名為 `my-custom-agent` 的自訂 subagent

將這些規則新增至設定中的 `deny` 陣列，或使用 `--disallowedTools` CLI 旗標來停用特定 agent。若要停用 Explore agent：

```json theme={null}
{
  "permissions": {
    "deny": ["Agent(Explore)"]
  }
}
```

### Cd

`Cd` 規則控制 [`/cd` 命令](https://code.claude.com/docs/zh-TW/commands)可以將工作階段移動到哪些目錄。`Cd` 不是模型可呼叫的工具：Claude 無法呼叫它，這些規則只在您自行執行 `/cd` 時套用。

不帶參數的 `Cd` 拒絕規則會完全停用 `/cd`。`Cd(<path-pattern>)` 拒絕規則會封鎖符合的目標。拒絕規則會檢查目標的每種寫法，包括其解析過程中經過的每個符號連結節點，因此為某個路徑撰寫的規則也會封鎖解析至該路徑的目標。

新增任何 `Cd` 允許規則都會將 `/cd` 切換為允許清單模式：解析後的目標目錄必須符合您的其中一條允許規則，否則 `/cd` 會拒絕。若未設定任何 `Cd` 規則，`/cd` 會維持其預設行為，並提示您信任不熟悉的目錄。

路徑模式與 [Read 和 Edit 規則](#read-and-edit)共用 `//`、`~/` 與 `/` 錨點，但比對是錨定於整個目錄路徑，而非 gitignore 風格。`*` 恰好比對一個路徑區段，而 `**` 會跨區段比對。結尾的 `/**` 也會比對其所指名的根目錄。

| 規則 | 比對 | 不比對 |
| - | - | - |
| `Cd(~/code/*)` | `~/code/app` | `~/code/app/src`、`~/code` |
| `Cd(~/code/**)` | `~/code` 及其下的任何目錄 | `~/code` 以外的目錄 |
| `Cd(**/node_modules)` | 目前目錄下任何深度的任何 `node_modules` 目錄 | `node_modules/pkg` |

## 使用 hooks 擴展權限

[Claude Code hooks](https://code.claude.com/docs/zh-TW/hooks-guide.md) 讓您可以註冊自訂 shell 命令，以在執行時評估權限。當 Claude Code 進行工具呼叫時，PreToolUse hooks 在權限提示之前執行，適用於除了 [`EndConversation`](https://code.claude.com/docs/zh-TW/tools-reference#endconversation-tool-behavior) 以外的每個工具。hook 輸出可以拒絕工具呼叫、強制提示或跳過提示以讓呼叫繼續進行。

### 規則、hook 與 mod 之間的優先順序

PreToolUse hook 決定不會繞過權限規則。Claude Code 會評估 deny 和 ask 規則，無論 PreToolUse hook 返回什麼：符合的 deny 規則會阻止呼叫，符合的 ask 規則即使在 hook 返回 `"allow"` 或 `"ask"` 時仍會提示。這保留了 [Manage permissions](#manage-permissions) 中描述的 deny 優先順序，包括在受管理設定中設定的 deny 規則。

該優先順序涵蓋設定檔中的 hook 和外掛 `hooks/hooks.json` 中的 hook。您安裝的處理 [`tool.check`](https://code.claude.com/docs/zh-TW/plugins/mods/events#approve-or-refuse-a-tool-call-before-the-user-is-asked) 事件的 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md) 會在 `PreToolUse` hook 執行之後才給出答案。當機器上有[受管理設定](https://code.claude.com/docs/zh-TW/settings.md#check-what-your-organization-enforces)，或工作階段的憑證為 Team 或 Enterprise 的 [`/login`](https://code.claude.com/docs/zh-TW/authentication#authentication-precedence) 時，在 mod 核准呼叫的情況下，以下結果預設維持不變：

* deny 規則拒絕的呼叫仍會被拒絕，您的組織可以改變這一點。
* ask 規則會提示的呼叫仍會提示您。
* `PreToolUse` hook 或 [`permissions.blockReadsOutsideWorkingDirectories`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-blockreadsoutsideworkingdirectories) 會提示的呼叫仍會提示您。
* `PreToolUse` hook 阻止的呼叫仍會被阻止，無論該 hook 來自哪個設定檔。
* 您的 [`--permission-prompt-tool`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 或 Agent SDK [`canUseTool` 回呼](https://code.claude.com/docs/zh-TW/agent-sdk/user-input#handle-tool-approval-requests)會被詢問的呼叫，仍會交由該工具或回呼處理。

若既沒有受管理設定，工作階段的憑證也不是 Team 或 Enterprise 的 `/login`，mod 可以核准 deny 規則拒絕或 `PreToolUse` hook 阻止的呼叫。改用 API 金鑰或長期有效的 [`CLAUDE_CODE_OAUTH_TOKEN`](https://code.claude.com/docs/zh-TW/authentication#generate-a-long-lived-token) 執行的工作階段並未使用該登入，即使該登入已被儲存。

在這種設定下，當 mod 核准 ask 規則、`PreToolUse` hook 或 `permissions.blockReadsOutsideWorkingDirectories` 會提示的呼叫時，您不會收到提示。您的 `--permission-prompt-tool` 或 `canUseTool` 回呼也不會被詢問 mod 核准的呼叫。在每種設定下，自動模式、plan mode 和 `dontAsk` 模式各自會增加一項專屬的結果：

* **[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)**：mod 核准的呼叫會在沒有分類器檢查的情況下執行，除非 mod 無法繞過您的權限提示工具或 Agent SDK 權限回呼。在那種情況下，分類器會先檢查該呼叫。
* **[Plan mode](#hook-approvals-in-plan-mode)**：mod 無法核准非唯讀的呼叫，例如檔案編輯或會寫入的 shell 命令。
* **[`dontAsk` 模式](https://code.claude.com/docs/zh-TW/permission-modes#allow-only-pre-approved-tools-with-dontask-mode)**：mod 可以核准除了該模式本身之外沒有其他機制會拒絕的呼叫。

請參閱 [Decide whether to trust a mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md#decide-whether-to-trust-a-mod)，或如果您部署受管理設定，請參閱 [Manage mods for your organization](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md#know-what-happens-by-default)。

對於[需要使用者互動的工具](https://code.claude.com/docs/zh-TW/permission-modes.md#actions-no-mode-auto-approves)，例如 `AskUserQuestion` 或標記為 `requiresUserInteraction` 的 MCP 工具，mod 的 `tool.check` 核准不會跳過提示。需要 Claude Code v2.1.292 或更新版本。標記為 [`requiresUserInteraction`](https://code.claude.com/docs/zh-TW/mcp#require-approval-for-a-specific-tool) 的 MCP 工具在 hook 返回 `"allow"` 時也仍會提示，從[網路路徑](#network-paths)進行的讀取，以及在該設定到達 Claude Code 的工作階段中[您的組織設定為 `ask`](https://code.claude.com/docs/zh-TW/mcp#organization-controls-on-connector-tools) 的連接器工具也是如此。

阻止 hook 也優先於 allow 規則。以代碼 2 退出的 hook 會在評估權限規則之前停止工具呼叫，因此即使 allow 規則會允許呼叫，該阻止也會適用。若要執行所有 Bash 命令而無需提示，除了您想要阻止的少數幾個，請將 `"Bash"` 新增到您的 allow 清單，並註冊一個 PreToolUse hook 來拒絕那些特定命令。請參閱 [Block edits to protected files](https://code.claude.com/docs/zh-TW/hooks-guide.md#block-edits-to-protected-files) 以取得您可以調整的 hook 指令碼。

### plan mode 中的 hook 核准

在 [plan mode](https://code.claude.com/docs/zh-TW/permission-modes.md#analyze-before-you-edit-with-plan-mode) 中，除了 `ExitPlanMode` 之外，您的 `PreToolUse` hook 的 `"allow"` 對檔案編輯或其他非唯讀呼叫沒有作用。您會得到與沒有 hook 時該呼叫相同的提示、阻止或核准，而 Claude Code 仍會套用 hook 返回的任何 `updatedInput`。如果 hook 以 `"allow"` 和 `updatedInput` 回應 [`ExitPlanMode`](https://code.claude.com/docs/zh-TW/hooks#allow-with-updatedinput)，該工具仍會在沒有提示的情況下執行。

在 plan mode 中，處理 `tool.check` 的 mod 也無法核准檔案編輯或其他非唯讀呼叫，但仍可以阻止此類呼叫。若要解除對 hook 和 mod 核准的此限制，請[核准計劃](https://code.claude.com/docs/zh-TW/permission-modes.md#review-and-approve-a-plan)或切換到其他權限模式。

## 工作目錄

根據預設，Claude 可以存取啟動它的目錄中的檔案。該目錄是工作階段的主要工作目錄，直到您[使用 `/cd` 移動工作階段](#move-the-session-to-another-directory)。您可以擴展此存取：

* **在啟動期間**：使用 `--add-dir <path>` CLI 引數
* **在工作階段期間**：使用 `/add-dir` 命令
* **持久設定**：新增到 [settings files](https://code.claude.com/docs/zh-TW/settings.md#where-settings-live) 中的 `additionalDirectories`

其他目錄中的檔案遵循與原始工作目錄相同的權限規則：除了[網路路徑](#network-paths)檢查之外，它們變成可讀的而無需提示，檔案編輯權限遵循目前的權限模式。

您無法新增大多數[網路路徑](https://code.claude.com/docs/zh-TW/errors.md#working-directory-is-a-network-path)，例如 UNC 共用 `\\server\share`，作為工作目錄，因為查詢它可能會聯絡它所命名的主機。在 Windows 上，請改為將共用對應到磁碟機代號，並在啟動時使用 `--add-dir` 傳遞磁碟機。

在 macOS 的背景工作階段中，當 Claude 需要讀取或寫入檔案時，工作階段主機會分別從您的終端機要求存取受保護的資料夾，例如 `~/Desktop`、`~/Documents` 和 `~/Downloads`；如果讀取失敗並出現 `Operation not permitted`，請參閱[如何授予背景工作階段對資料夾的存取權](https://code.claude.com/docs/zh-TW/agent-view.md#background-sessions-can%E2%80%99t-read-desktop-documents-or-downloads-on-macos)。

### 封鎖工作目錄外的檔案工具讀取和寫入

若要讓 Claude 的檔案工具在每個權限模式（包括 `bypassPermissions`）中拒絕工作目錄外的路徑，請將下列其中一個或兩個設定鍵設為 `true`：

* **[`permissions.blockReadsOutsideWorkingDirectories`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-blockreadsoutsideworkingdirectories)**：檔案工具會拒絕讀取該處的檔案，但 Claude Code 本身需要的檔案除外。在自動模式中，Claude Code 會在 Claude 首次[讀取工作目錄外的檔案](https://code.claude.com/docs/zh-TW/permission-modes.md#first-read-outside-the-working-directories)時提供開啟它的選項。
* **[`permissions.blockWritesOutsideWorkingDirectories`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-blockwritesoutsideworkingdirectories)**：`Write`、`Edit` 和 `NotebookEdit` 工具會拒絕寫入該處，但 Claude Code 自己的某些檔案（例如計畫檔案）除外。此設定鍵不會限制 shell 命令、MCP 工具或 hook 執行的程式，因此請使用[沙箱機制](https://code.claude.com/docs/zh-TW/sandboxing.md)來限制 shell 命令的寫入位置。需要 Claude Code v2.1.314 或更新版本。

若要在任一設定鍵為 `true` 時仍可存取某個外部目錄，請[將其新增為工作目錄](https://code.claude.com/docs/zh-TW/settings-reference.md#let-one-directory-through-the-read-or-write-block)。

### 將工作階段移動到另一個目錄

若要將工作階段移動到不同的主要工作目錄，而不是[在目前目錄旁新增目錄](#working-directories)，請執行 `/cd <path>`。Claude Code 會保留對話、載入新目錄的 `CLAUDE.md`，並在您之前未在其中工作時提示您[信任工作區](#project-allow-rules-and-workspace-trust)。之後，當您從新目錄執行 `--resume` 時，Claude Code 會[找到移動的工作階段](https://code.claude.com/docs/zh-TW/sessions.md#where-the-session-picker-looks)。

移動後，Claude Code 會立即套用新目錄的專案設定：

* 其專案設定，包括其權限規則和 [hooks](https://code.claude.com/docs/zh-TW/hooks.md)
* 其 [`.mcp.json` 伺服器](https://code.claude.com/docs/zh-TW/mcp#project-scope)，受限於與啟動時相同的[伺服器核准](https://code.claude.com/docs/zh-TW/mcp.md#project-server-approvals-and-workspace-trust)，以及您在其中註冊的[本機範圍](https://code.claude.com/docs/zh-TW/mcp.md#local-scope) MCP 伺服器
* 其設定啟用的 [plugins](https://code.claude.com/docs/zh-TW/plugins/overview.md)、其 [skills](https://code.claude.com/docs/zh-TW/skills.md#discovery-from-parent-and-nested-directories) 和其 [subagents](https://code.claude.com/docs/zh-TW/sub-agents.md)
* 其 [`env`](https://code.claude.com/docs/zh-TW/settings-reference#env) 值，套用在前一個目錄設定的環境變數之上，這些變數保持有效

Claude Code 也會斷開前一個目錄的專案和[本機範圍](https://code.claude.com/docs/zh-TW/mcp.md#local-scope) MCP 伺服器，以及移動後不再啟用的 [plugins](https://code.claude.com/docs/zh-TW/mcp.md#plugin-provided-mcp-servers) 的伺服器。它從新目錄的設定而不是前一個目錄的設定中取得[其他目錄](#working-directories)，並保留您使用 `--add-dir` 或 `/add-dir` 新增的目錄。移動啟用的 Hooks 仍會收到 [`${CLAUDE_PROJECT_DIR}`](https://code.claude.com/docs/zh-TW/hooks#reference-scripts-by-path) 設定為工作階段啟動的專案根目錄。

當新目錄尚未受信任時，Claude Code 會在信任提示中列出目錄設定會啟用的允許規則、其他目錄、hooks 和輔助命令，以便您可以在接受前檢查它們。如果您拒絕，工作階段會保持在原位。在 v2.1.246 之前，`/cd` 不會套用新目錄的設定、hooks、MCP 伺服器或 skills，直到您恢復工作階段，其信任提示也不會列出目錄設定會啟用的內容。

使用 [`Cd` 權限規則](#cd)限制或停用 `/cd` 目標。

### 其他目錄授予檔案存取權，而非設定

新增目錄會擴展 Claude 可以讀取和編輯檔案的位置。它不會使該目錄成為完整的設定根目錄：大多數 `.claude/` 設定不會從其他目錄發現，儘管有幾種類型作為例外被載入。

這些例外僅適用於使用 `--add-dir` 旗標或 `/add-dir` 命令新增的目錄，包括 Agent SDK 透過旗標新增的目錄。在設定檔中的 `permissions.additionalDirectories` 中列出的目錄僅授予檔案存取權，不會載入以下任何設定。

Agent SDK 在 TypeScript 中的 [`additionalDirectories`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#options) 選項和在 Python 中的 [`add_dirs`](https://code.claude.com/docs/zh-TW/agent-sdk/python#claudeagentoptions) 選項也會收到例外，儘管 TypeScript 選項與設定金鑰共享其名稱。SDK 會將每個項目作為 `--add-dir` 傳遞給 Claude Code，因此這些目錄的行為類似於旗標新增的目錄。來自任何旗標新增目錄的 Skills、命令和 subagents 會透過 `project` [setting source](https://code.claude.com/docs/zh-TW/agent-sdk/claude-code-features.md#control-filesystem-settings-with-settingsources) 載入，因此當您在 CLI 上使用 [`--setting-sources`](https://code.claude.com/docs/zh-TW/cli-reference) 或在 SDK 中使用 `settingSources` 排除該來源時，它們不會載入，而[裸模式](https://code.claude.com/docs/zh-TW/headless.md#start-faster-with-bare-mode)會跳過其中的命令和 subagents。

以下設定類型從 `--add-dir` 目錄載入：

| 設定 | 從 `--add-dir` 載入 |
| :- | :- |
| `.claude/skills/` 中的 [Skills](https://code.claude.com/docs/zh-TW/skills.md) | 是，具有即時重新載入 |
| `.claude/commands/` 中的 [Command files](https://code.claude.com/docs/zh-TW/skills.md#where-skills-live) | 是，無即時重新載入。當新增的目錄和您的專案都定義同名命令時，Claude Code 會執行您的專案命令 |
| `.claude/agents/` 中的 [Subagents](https://code.claude.com/docs/zh-TW/sub-agents.md) | 是，無即時重新載入 |
| `.claude/settings.json` 和 `.claude/settings.local.json` 中的 [Settings](https://code.claude.com/docs/zh-TW/settings.md) | 僅 `enabledPlugins` 和 [`extraKnownMarketplaces`](https://code.claude.com/docs/zh-TW/settings-reference#extraknownmarketplaces) 金鑰 |
| [CLAUDE.md](https://code.claude.com/docs/zh-TW/memory.md) 檔案、`.claude/rules/` 和 `CLAUDE.local.md` | 僅當設定 `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1` 時。`CLAUDE.local.md` 另外需要 `local` 設定來源，預設啟用 |

若要在工作階段中期從您[主要工作目錄](#working-directories)的子目錄載入 skills、命令和 subagents，請執行 `/add-dir` 並使用該子目錄的路徑。Claude Code 會為工作階段的其餘部分載入它們，而無需提示您或新增工作目錄，因為子目錄已經可讀。這需要 Claude Code v2.1.257 或更新版本。

#### 輸出風格、hooks 和本機設定的載入位置

Claude Code 從目前工作目錄及其父目錄、您在 `~/.claude/` 的使用者目錄和受管理設定發現輸出風格。Hooks 和其他 `.claude/settings.json` 金鑰從目前工作目錄的 `.claude/` 資料夾載入，沒有父目錄備援，同時也從您的使用者 `~/.claude/settings.json` 和受管理設定載入。

`.claude/settings.local.json` 則從 git 儲存庫根目錄載入，即使您在子目錄中啟動 Claude Code，除了 Claude Code [不使用儲存庫根目錄](https://code.claude.com/docs/zh-TW/settings.md#where-claude-code-looks-for-each-file)的情況，例如在 Windows 上。

若要在專案間共享該設定，請使用以下方法之一：

* **使用者級別設定**：將檔案放在 `~/.claude/agents/`、`~/.claude/output-styles/` 或 `~/.claude/settings.json` 中，使其在每個專案中可用
* **Plugins**：將設定打包並分發為 [plugin](https://code.claude.com/docs/zh-TW/plugins/overview.md)，供團隊安裝
* **從設定目錄啟動**：從包含您想要的 `.claude/` 設定的目錄執行 Claude Code

## 權限如何與沙箱互動

權限和 [sandboxing](https://code.claude.com/docs/zh-TW/sandboxing.md) 是互補的安全層：

* **權限**控制 Claude Code 可以使用哪些工具以及它可以存取哪些檔案或網域。它們適用於 Bash、Read、Edit、WebFetch、MCP 和其他所有工具，除了 deny 或 ask 規則無法阻止 [`EndConversation`](https://code.claude.com/docs/zh-TW/tools-reference#endconversation-tool-behavior)，而任何其他工具仍然存在。
* **沙箱**提供作業系統級別的強制執行，限制 shell 命令的檔案系統和網路存取。它適用於 Bash、PowerShell 和 [Monitor](https://code.claude.com/docs/zh-TW/tools-reference.md#monitor-tool) 工具命令及其子程序。

使用兩者進行深度防禦，因為即使提示注入繞過 Claude 的決策制定，沙箱限制仍然適用。來自沙箱設定和權限規則的路徑和網域會 [合併到最終沙箱設定](https://code.claude.com/docs/zh-TW/sandboxing.md#permission-rules)。

當您啟用沙箱並將 `autoAllowBashIfSandboxed` 保留在其預設值 `true` 時，沙箱化 Bash 命令無需提示即可執行，即使您的權限包括 bare `Bash` ask 規則，或 [等效的 `Bash(*)` 形式](#match-all-uses-of-a-tool)：沙箱邊界替代整個工具提示。

在 [plan mode](https://code.claude.com/docs/zh-TW/permission-modes.md#analyze-before-you-edit-with-plan-mode) 中，Claude Code 會跳過此替代。沒有 ask 規則時，[內建唯讀命令](#read-only-commands)仍然無需提示即可執行，任何其他 shell 命令在您仍在規劃時會通過常規權限流程；請參閱 [plan mode](https://code.claude.com/docs/zh-TW/permission-modes.md#analyze-before-you-edit-with-plan-mode) 以了解 Claude Code 如何在那裡控制命令。使用 bare `Bash` ask 規則時，每個 Bash 命令都會提示，包括沙箱化唯讀命令，與沙箱外相同。

這些檢查仍然適用：

* 內容範圍的 ask 規則（如 `Bash(git push *)`）仍然強制提示
* 其他沙箱化命令也可能通過常規權限流程，如 [Auto-allow mode](https://code.claude.com/docs/zh-TW/sandboxing.md#auto-allow-mode) 所述

不會在沙箱中執行的命令（例如排除的命令）會遵守 bare `Bash` ask 規則。請參閱 [沙箱模式](https://code.claude.com/docs/zh-TW/sandboxing.md#sandbox-modes) 以變更此行為。

## 受管理設定

對於需要集中控制的組織，管理員部署受管理設定，使用者和專案設定無法覆蓋，除了少數[安全敏感的金鑰](https://code.claude.com/docs/zh-TW/settings.md#exceptions-to-managed-settings-precedence)。[部署受管理設定](https://code.claude.com/docs/zh-TW/managed-settings.md)涵蓋傳遞機制、受管理層級內的優先順序，以及[僅受管理設定可以設定的金鑰](https://code.claude.com/docs/zh-TW/managed-settings.md#managed-only-settings)。

其中一個金鑰[`allowManagedPermissionRulesOnly`](https://code.claude.com/docs/zh-TW/settings-reference#allowmanagedpermissionrulesonly)使受管理設定成為權限規則的唯一設定來源。其項目列出 Claude Code 隨後忽略的每個來源。

`disableBypassPermissionsMode`通常放在受管理設定中以強制執行組織原則，但它可以從任何範圍工作。使用者可以在自己的設定中設定它，讓自己無法使用繞過模式。

## 設定優先順序

權限規則遵循與所有其他 Claude Code 設定相同的 [settings precedence](https://code.claude.com/docs/zh-TW/settings.md#settings-precedence)，受管理設定最高：沒有其他級別（包括命令列引數）可以覆蓋受管理權限規則。

如果工具在任何級別被拒絕，沒有其他級別可以允許它。例如，受管理設定 deny 無法被 `--allowedTools` 覆蓋，`--disallowedTools` 可以新增超出受管理設定定義的限制。

相同的規則也適用於設定範圍：如果使用者設定允許某項權限而專案設定拒絕它，deny 規則會阻止它。反之亦然：使用者級別的 deny 會阻止專案級別的 allow，因為來自任何範圍的 deny 規則會在 allow 規則之前進行評估。

這個優先順序是在設定檔和命令列引數之間。關於 deny 規則是否對您安裝的 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md) 成立，請參閱 [使用 hooks 擴展權限](#extend-permissions-with-hooks)。

嵌入主機可以透過 SDK `managedSettings` 選項提供額外的受管理原則，包括權限 allow 規則，除非管理員設定 `allowManaged*Only` 鎖定；[將原則傳遞給 Claude Desktop 工作階段](https://code.claude.com/docs/zh-TW/claude-apps-gateway#deliver-policy-to-claude-desktop-sessions) 涵蓋嵌入器原則在哪些情況下才會套用。

## 專案允許規則和工作區信任

`permissions.allow` 規則和專案 `.claude/settings.json` 中的 `permissions.additionalDirectories` 項目會授予功能，因此 Claude Code 只有在您接受該資料夾的[工作區信任對話框](https://code.claude.com/docs/zh-TW/security.md#additional-safeguards)後才會套用這些規則。對話框會列出資料夾將授予的規則和目錄，以便您先進行檢查。`deny` 和 `ask` 規則不受影響，因為它們只會限制。

Claude Code 以您啟動它的位置為鍵來儲存您接受的信任：

* 在儲存庫中，Claude Code 會以 git 儲存庫根目錄作為信任的鍵，因此信任涵蓋整個儲存庫，除了任何巢狀在其中的 git 儲存庫（例如子模組）。在 [worktree](https://code.claude.com/docs/zh-TW/worktrees.md) 中，它使用主簽出的根目錄，就像它對[已儲存規則](#permission-system)所做的一樣。
* 在儲存庫外，Claude Code 會以您啟動它的目錄作為信任的鍵，信任涵蓋該目錄的任何子目錄，除了巢狀在其中的 git 儲存庫（例如複製）。每個涵蓋的子目錄隨後都會計為一個您信任其父目錄的資料夾。
* 當您在家目錄中啟動時，Claude Code 只在目前工作階段內保持信任，不會將其寫入磁碟；請參閱[額外保護措施](https://code.claude.com/docs/zh-TW/security.md#additional-safeguards)說明。

Claude Code 只在互動工作階段中顯示信任對話框。`claude -p` 執行或 SDK 工作階段永遠不會顯示它，信任父資料夾不會計入這些規則，因此[您信任資料夾前執行的內容](#what-runs-before-you-trust-a-folder)說明了在這兩種情況下 Claude Code 仍然使用的儲存庫內容。

在啟動或重新啟動[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)之前，Claude Code 也會檢查工作階段執行所在目錄的工作區信任。如果您從未信任的目錄中的終端機執行 `claude --bg`，信任對話框會先出現，一旦您接受它，工作階段就會啟動。在無法出現對話框的地方（例如在指令碼中），命令會改為以[`Workspace not trusted`](https://code.claude.com/docs/zh-TW/errors#workspace-not-trusted-when-dispatching-a-background-session)錯誤結束。

### 當您的本機設定檔案需要信任時

`.claude/settings.local.json` 通常是您自己的檔案，因此 Claude Code 會套用其允許規則和其他目錄，無需信任步驟。當檔案在 git 中被追蹤，或 `.claude` 是符號連結時，Claude Code 會改為將其視為儲存庫提供的檔案，並暫不套用其規則，直到您信任資料夾為止。

Claude Code 執行 git 來區分兩者，並且只有在您信任資料夾後才執行 git：您接受了它的信任對話框或其父目錄的信任對話框，其信任延伸到它，或您在 `-p` 或 SDK 工作階段中，這被視為已接受。在此之前，您啟動 Claude Code 的位置決定了該檔案規則會發生什麼：

* **在您的設定主目錄中：** Claude Code 會立即套用該資料夾的 `.claude/settings.local.json`，無需執行 git。您的設定主目錄是您的家目錄，或是其 `.claude` 子目錄已被您設定為 [`CLAUDE_CONFIG_DIR`](https://code.claude.com/docs/zh-TW/env-vars#variables) 的目錄。如果該 `CLAUDE_CONFIG_DIR` 目錄位於 git 儲存庫內，且 Claude Code 改為[將您的本機設定保留在儲存庫根目錄](https://code.claude.com/docs/zh-TW/settings.md#where-claude-code-looks-for-each-file)，它會像在其他地方一樣暫不套用這些規則。
* **其他任何地方：** Claude Code 會像對待專案設定一樣暫不套用該檔案的規則。檢查執行後，Claude Code 會套用未追蹤檔案的規則，或位於任何 git 儲存庫外的目錄中的檔案的規則，即使您尚未信任該確切資料夾。

> [!NOTE]
>
> 設定主目錄例外只會跳過信任步驟。`~/.claude/settings.local.json` 仍然是[本機範圍](https://code.claude.com/docs/zh-TW/settings.md#compare-the-scope-of-each-settings-file)，因此 Claude Code 只在您在家目錄本身啟動的工作階段中讀取它，而不是在每個專案中。若要在所有專案中套用權限規則，請改為將它們新增到您的使用者設定：`~/.claude/settings.json` 或設定 `CLAUDE_CONFIG_DIR` 時的 `$CLAUDE_CONFIG_DIR/settings.json`。

### 您信任資料夾前執行的內容

每一列是儲存庫可以提供的一種內容。各欄是您尚未信任資料夾本身的兩種情況：您只信任了父資料夾，或您在那裡執行了 `claude -p` 或 SDK，這永遠不會顯示信任對話框。父資料夾欄不適用於[巢狀儲存庫](#project-allow-rules-and-workspace-trust)內：在互動工作階段中 Claude Code 會為其顯示信任對話框，在那裡執行的 `claude -p` 或 SDK 會遵循 `claude -p` 欄。

| 儲存庫提供的內容 | 您只信任了父資料夾 | `claude -p` 或 SDK，資料夾從未被信任 |
| :- | :- | :- |
| 設定檔案中的 [hook](https://code.claude.com/docs/zh-TW/hooks.md)、[`env`](https://code.claude.com/docs/zh-TW/settings-reference#env) 區塊和輔助命令（例如 [`apiKeyHelper`](https://code.claude.com/docs/zh-TW/settings-reference#apikeyhelper)），以及專案 skill 的 [hook](https://code.claude.com/docs/zh-TW/hooks.md#hooks-in-skills-and-agents) 和 [`allowed-tools`](https://code.claude.com/docs/zh-TW/skills#pre-approve-tools-for-a-skill) | 已使用 | 已使用。工作區信任在任何工作階段中都不會限制 skill 的 `allowed-tools` |
| `.claude/settings.json` 中的 `permissions.allow` 規則和 `additionalDirectories` | 在您接受信任對話框之前不使用，對話框會再次出現列出它們 | 不使用。Claude Code 會列印 [`this workspace has not been trusted`](https://code.claude.com/docs/zh-TW/errors#workspace-has-not-been-trusted) 警告到 stderr |
| 專案 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#hooks-in-subagent-frontmatter) 中的 frontmatter hook、專案 [`@skills-dir` 外掛](https://code.claude.com/docs/zh-TW/plugins/loading#plugins-shared-through-a-repository)，以及來自儲存庫或 `--add-dir` 目錄的 [`extraKnownMarketplaces`](https://code.claude.com/docs/zh-TW/settings-reference#extraknownmarketplaces) 項目 | 不使用，不提供對話框 | 不使用 |
| 來自儲存庫或 `--add-dir` 目錄的 subagent 的 frontmatter 中的內聯 [`mcpServers`](https://code.claude.com/docs/zh-TW/sub-agents#scope-mcp-servers-to-a-subagent) | 不使用，不提供對話框 | 不使用 |
| `.mcp.json` 中的伺服器，包括儲存庫[在其自己的設定中核准的伺服器](https://code.claude.com/docs/zh-TW/mcp.md#project-server-approvals-and-workspace-trust) | Claude Code 在連接它們之前會詢問您。儲存庫自己的核准不計算 | 連接而不詢問，無論是否核准。SDK 只在 `settingSources` 包含專案設定時才載入它們。同一資料夾中的 `claude mcp list` 仍然將此類伺服器報告為待處理 |
| `.mcp.json` 中伺服器上的 [`headersHelper`](https://code.claude.com/docs/zh-TW/mcp#trust-a-folder-before-its-headershelper-runs) | 在您接受信任對話框之前不執行，對話框會再次出現命名輔助程式的宣告位置。Claude Code 在此之前僅使用其靜態 `headers` 連接伺服器 | 不執行。Claude Code 僅使用其靜態 `headers` 連接伺服器，並為每個伺服器列印 [`headersHelper not run`](https://code.claude.com/docs/zh-TW/errors#headershelper-not-run) 行到 stderr |

對於需要此確切資料夾被信任的列，請手動信任它：在 `~/.claude.json` 中設定 `projects["<path>"].hasTrustDialogAccepted` 為 `true`，其中 `<path>` 是儲存庫根目錄，或儲存庫外的資料夾本身。Claude Code 在跳過的 subagent hook 或內聯 MCP 伺服器的偵錯日誌行中列印確切的鍵，在跳過的允許規則的 stderr 警告中列印，以及在跳過的輔助程式的 `headersHelper not run` 行中列印。

在您在未編寫的儲存庫中執行 `claude -p` 之前，請決定它可以在您的機器上執行什麼：

* 傳遞 `--setting-sources user`，或設定 SDK 的 `settingSources` 而不包含專案設定，以便 Claude Code 既不讀取專案的設定檔案也不讀取其 `.mcp.json`
* 使用 [`--bare`](https://code.claude.com/docs/zh-TW/headless#start-faster-with-bare-mode) 啟動，以便 Claude Code 不從專案讀取任何 hook、skill、自訂命令、subagent、外掛或 `.mcp.json` 伺服器。專案的 `env` 區塊和輔助程式（例如其設定檔案中的 `awsAuthRefresh`）仍然適用，Claude Code 只從 `--settings` 讀取 `apiKeyHelper`
* 傳遞 `--settings '{"disableAllHooks": true}'` 以[關閉該執行的 hook](https://code.claude.com/docs/zh-TW/hooks.md#disable-or-remove-hooks)。僅在您的使用者設定中設定它是不夠的，因為儲存庫的專案設定優先於您的設定，並且可以將其設定回 `false`
* 新增 [`disabledMcpjsonServers`](https://code.claude.com/docs/zh-TW/settings-reference#disabledmcpjsonservers) 項目以在每個工作階段類型中按名稱拒絕 `.mcp.json` 伺服器

## 範例設定

此 [repository](https://github.com/anthropics/claude-code/tree/main/examples/settings) 包含常見部署情境的入門設定。使用這些作為起點並根據您的需求進行調整。

## 另請參閱

* [所有設定](https://code.claude.com/docs/zh-TW/settings-reference.md#permission-settings)：每個設定鍵，包括權限鍵
* [設定自動模式](https://code.claude.com/docs/zh-TW/auto-mode-config.md)：告訴自動模式分類器您的組織信任哪些基礎設施
* [沙箱隔離](https://code.claude.com/docs/zh-TW/sandboxing.md)：Bash 命令的作業系統級別檔案系統和網路隔離
* [驗證](https://code.claude.com/docs/zh-TW/authentication.md)：設定使用者對 Claude Code 的存取
* [安全性](https://code.claude.com/docs/zh-TW/security.md)：安全防護措施和最佳實踐
* [Hooks](https://code.claude.com/docs/zh-TW/hooks-guide.md)：自動化工作流程並擴展權限評估

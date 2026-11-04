<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/hooks | lastmod: 2026-11-03 | section: Reference / Reference -->
> 來源：https://code.claude.com/docs/zh-TW/hooks（官方 zh-TW，lastmod 2026-11-03）｜分類：Reference › Reference｜EN 摘要：Reference for Claude Code hook events, configuration schema, JSON input/output formats, exit codes, async hooks, HTTP hooks, prompt hooks, and MCP tool hooks.

# Hooks 參考

> Claude Code hook 事件、配置架構、JSON 輸入/輸出格式、退出代碼、非同步 hooks、HTTP hooks、提示 hooks 和 MCP 工具 hooks 的參考。

> [!TIP]
>
> 如需快速入門指南和範例，請參閱 [使用 hooks 自動化工作流程](https://code.claude.com/docs/zh-TW/hooks-guide.md)。

Hooks 是使用者定義的 shell 命令、HTTP 端點、MCP 工具呼叫、LLM 提示或子代理，在 Claude Code 生命週期的特定時間點自動執行。Claude Code 在任何地方執行時都會觸發相同的 hook 事件：終端機中的工作階段、IDE 擴充功能、[桌面應用程式](https://code.claude.com/docs/zh-TW/desktop-quickstart.md) 和 [雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)。使用此參考來查詢事件架構、配置選項、JSON 輸入/輸出格式，以及非同步 hooks、HTTP hooks 和 MCP 工具 hooks 等進階功能。

外掛程式也可以將 hooks 註冊為 JavaScript 函式，Claude Code 會在其自己的程序中呼叫這些函式，這些函式既可以在介面中繪製，也可以對事件進行操作。執行此操作的外掛程式是 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md)，這些函式 hooks 在 [對事件做出反應](https://code.claude.com/docs/zh-TW/plugins/mods/events.md) 中涵蓋，而不是在此處。此頁面上的 hooks 會繼續與 mods 一起運作。

## Hook 生命週期

Claude Code 在工作階段期間的特定時間點執行 hooks。當事件觸發且匹配器符合時，Claude Code 會將有關該事件的 JSON 上下文傳遞給您的 hook 處理程式。對於命令 hooks，輸入會到達 stdin。對於 HTTP hooks，它會作為 POST 請求正文到達。您的處理程式可以檢查輸入、採取行動，並可選擇性地返回決定。

事件分為三種節奏：

* 每個工作階段一次：`SessionStart` 和 `SessionEnd`
* 每個轉向一次：`UserPromptSubmit`、`Stop` 和 `StopFailure`
* 在代理迴圈內每個工具呼叫上：`PreToolUse` 和 `PostToolUse`，除了 [`EndConversation`](https://code.claude.com/docs/zh-TW/tools-reference#endconversation-tool-behavior) 呼叫外，兩者都會跳過

![Hook 生命週期圖表，顯示可選的 Setup 進入 SessionStart，然後是每個轉向的迴圈，包含 UserPromptSubmit、用於 slash commands 的 UserPromptExpansion、嵌套的代理迴圈（PreToolUse、PermissionRequest、PostToolUse、PostToolUseFailure、PostToolBatch、SubagentStart/Stop、TaskCreated、TaskCompleted）和 Stop 或 StopFailure，接著是 TeammateIdle、PreCompact、PostCompact 和 SessionEnd，Elicitation 和 ElicitationResult 嵌套在 MCP 工具執行內，PermissionDenied 作為 PermissionRequest 的側分支用於自動模式拒絕，WorktreeCreate、WorktreeRemove、Notification、ConfigChange、InstructionsLoaded、CwdChanged、FileChanged 和 DirectoryAdded 作為獨立非同步事件，PreModelSwitch 作為獨立順序事件，在請求的模型切換之前執行，PostModelSwitch 作為獨立非同步事件，在工作階段的模型變更後執行，以及 MessageDisplay 作為顯示專用事件，在助手訊息文字串流時執行](https://mintcdn.com/claude-code/x7pO8l4XcvAXCoVc/images/hooks-lifecycle.svg?fit=max\&auto=format\&n=x7pO8l4XcvAXCoVc\&q=85\&s=81b9256c1bbe8832553485f5d9e9c746)

下表總結了每個事件何時觸發。[Hook 事件](#hook-events)部分記錄了每個事件的完整輸入架構和決定控制選項。

| 事件 | 何時觸發 |
| :- | :- |
| `SessionStart` | 當工作階段開始或繼續時 |
| `Setup` | 當您使用 `--init-only` 啟動 Claude Code，或在 `-p` 模式中使用 `--init` 或 `--maintenance` 時。用於 CI 或指令碼中的一次性準備 |
| `UserPromptSubmit` | 當提示詞被提交時，在 Claude 處理之前。也會在 [Claude Code 自行開始的回合](https://code.claude.com/docs/zh-TW/hooks.md#userpromptsubmit)上觸發 |
| `UserPromptExpansion` | 當使用者輸入的命令擴展為提示詞時，在到達 Claude 之前。可以阻止擴展 |
| `PreToolUse` | 在工具呼叫執行之前。可以阻止它 |
| `PermissionRequest` | 當工具呼叫需要權限決定時 |
| `PermissionDenied` | 當自動模式拒絕工具呼叫時，包括沒有分類器判決的拒絕。使用 JSON `hookSpecificOutput.retry: true` 告訴模型它可能重試被拒絕的工具呼叫。Claude Code 在分類器未產生判決時忽略 `retry` |
| `PostToolUse` | 在工具呼叫成功後 |
| `PostToolUseFailure` | 在工具呼叫失敗後 |
| `PostToolBatch` | 在完整的平行工具呼叫批次解決後，在下一個模型呼叫之前 |
| `Notification` | 當 Claude Code 傳送通知時 |
| `MessageDisplay` | 在助手訊息文字顯示時 |
| `SubagentStart` | 當子代理被生成時 |
| `SubagentStop` | 當子代理完成時 |
| `TaskCreated` | 當透過 `TaskCreate` 建立任務時 |
| `TaskCompleted` | 當任務被標記為已完成時 |
| `Stop` | 當 Claude 完成回應時 |
| `StopFailure` | 當回合因 API 錯誤而結束時 |
| `TeammateIdle` | 當[代理團隊](https://code.claude.com/docs/zh-TW/agent-teams.md)隊友即將閒置時 |
| `InstructionsLoaded` | 當 CLAUDE.md 或 `.claude/rules/*.md` 檔案被載入到上下文時。在工作階段開始時以及在工作階段期間延遲載入檔案時觸發 |
| `ConfigChange` | 當設定檔在工作階段期間變更時 |
| `CwdChanged` | 當工作目錄變更時，例如當 Claude 執行 `cd` 命令時。適用於使用 direnv 等工具進行反應式環境管理 |
| `DirectoryAdded` | 當工作目錄在工作階段中期透過 `/add-dir` 或 SDK `register_repo_root` 控制請求新增時 |
| `FileChanged` | 當監視的檔案在磁碟上變更時。`matcher` 欄位指定要監視的檔案名稱 |
| `WorktreeCreate` | 當透過 `--worktree`、`isolation: "worktree"` 建立 worktree 時，或用於背景工作階段時。取代預設的 git 行為 |
| `WorktreeRemove` | 當由 `WorktreeCreate` hook 建立的 worktree 正在被移除時 |
| `PreCompact` | 在上下文壓縮之前 |
| `PostCompact` | 在上下文壓縮完成後 |
| `PreModelSwitch` | 在 Claude Code 應用您或用戶端要求的模型切換之前。可以阻止切換 |
| `PostModelSwitch` | 在工作階段的模型變更後，包括 Claude Code 自行進行的變更，例如當您繼續工作階段時恢復模型 |
| `Elicitation` | 當 MCP 伺服器在工具呼叫期間要求使用者輸入時 |
| `ElicitationResult` | 在使用者回應 MCP 引出後，在回應傳送回伺服器之前 |
| `SessionEnd` | 當工作階段終止時 |

### Hook 如何解析

為了了解事件、匹配器和處理程式如何組合在一起，請考慮此 `PreToolUse` hook，它會阻止破壞性 shell 命令。

> [tab] macOS/Linux
>
> `matcher` 縮小到 Bash 工具呼叫，`if` 條件進一步縮小到符合 `rm *` 的 Bash 子命令，因此 `block-rm.sh` 僅在兩個篩選器都符合時才生成：
>
> ```json theme={null}
> {
>   "hooks": {
>     "PreToolUse": [
>       {
>         "matcher": "Bash",
>         "hooks": [
>           {
>             "type": "command",
>             "if": "Bash(rm *)",
>             "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/block-rm.sh",
>             "args": []
>           }
>         ]
>       }
>     ]
>   }
> }
> ```
>
> 該指令碼從 stdin 讀取 JSON 輸入，提取命令，如果包含 `rm -rf`，則返回 `permissionDecision` 為 `"deny"`。將其儲存到您的專案中的 `.claude/hooks/block-rm.sh`，並使用 `chmod +x .claude/hooks/block-rm.sh` 使其可執行，以便 Claude Code 可以執行它：
>
> ```bash theme={null}
> #!/bin/bash
> # .claude/hooks/block-rm.sh
> COMMAND=$(jq -r '.tool_input.command')
>
> if echo "$COMMAND" | grep -q 'rm -rf'; then
>   jq -n '{
>     hookSpecificOutput: {
>       hookEventName: "PreToolUse",
>       permissionDecision: "deny",
>       permissionDecisionReason: "Destructive command blocked by hook"
>     }
>   }'
> else
>   exit 0  # no decision; normal permission flow applies
> fi
> ```
>
> 此指令碼，如同本頁面上解析 JSON 輸入的其他 Bash 範例，使用 `jq`，因此在嘗試之前請安裝 `jq` 並確保它在您的 `PATH` 上。

> [tab] Windows (PowerShell)
>
> 匹配器 `Bash|PowerShell` 涵蓋 [PowerShell 工具](#powershell)以及 Bash。單一 `if` 規則只符合一個工具的呼叫，因此每個工具都有自己的處理程式：第一個縮小到符合 `rm *` 的 Bash 子命令，第二個縮小到符合 `Remove-Item *` 的 PowerShell 命令。兩者都透過 `powershell.exe` 執行相同的指令碼：
>
> ```json theme={null}
> {
>   "hooks": {
>     "PreToolUse": [
>       {
>         "matcher": "Bash|PowerShell",
>         "hooks": [
>           {
>             "type": "command",
>             "if": "Bash(rm *)",
>             "command": "powershell.exe",
>             "args": [
>               "-NoProfile",
>               "-ExecutionPolicy",
>               "Bypass",
>               "-File",
>               "${CLAUDE_PROJECT_DIR}/.claude/hooks/block-rm.ps1"
>             ]
>           },
>           {
>             "type": "command",
>             "if": "PowerShell(Remove-Item *)",
>             "command": "powershell.exe",
>             "args": [
>               "-NoProfile",
>               "-ExecutionPolicy",
>               "Bypass",
>               "-File",
>               "${CLAUDE_PROJECT_DIR}/.claude/hooks/block-rm.ps1"
>             ]
>           }
>         ]
>       }
>     ]
>   }
> }
> ```
>
> `-NoProfile` 旗標會跳過載入您的 PowerShell 設定檔，以便 hook 快速啟動，而 `-ExecutionPolicy Bypass` 讓 PowerShell 執行本機指令碼檔案。
>
> 該指令碼從 stdin 讀取 JSON 輸入，提取命令，如果包含 `rm -rf` 或 `Remove-Item` 後跟 `-Recurse`，則返回 `permissionDecision` 為 `"deny"`。將其儲存到您的專案中的 `.claude/hooks/block-rm.ps1`：
>
> ```powershell theme={null}
> # .claude/hooks/block-rm.ps1
> $callInput = [Console]::In.ReadToEnd() | ConvertFrom-Json
> $command = $callInput.tool_input.command
>
> if ($command -match 'rm -rf|Remove-Item.*-Recurse') {
>   @{
>     hookSpecificOutput = @{
>       hookEventName = "PreToolUse"
>       permissionDecision = "deny"
>       permissionDecisionReason = "Destructive command blocked by hook"
>     }
>   } | ConvertTo-Json
> } else {
>   exit 0  # no decision; normal permission flow applies
> }
> ```

現在假設 Claude Code 決定針對 macOS/Linux 設定執行 `Bash "rm -rf /tmp/build"`。以下是發生的情況：

![Hook 解析圖表：PreToolUse 觸發，匹配器檢查 Bash 符合，然後 if 條件檢查 Bash(rm \*) 符合。如果兩者都符合，hook 命令執行並返回 permissionDecision deny，因此工具呼叫被阻止，Claude Code 繼續。如果任一檢查未能符合，hook 被跳過，工具呼叫允許繼續進行。](https://mintcdn.com/claude-code/ikqp3_70mqIahteV/images/hook-resolution.svg?fit=max\&auto=format\&n=ikqp3_70mqIahteV\&q=85\&s=be0bf3053550c26de5f54cd64674c197)

**1. 事件觸發**

`PreToolUse` 事件觸發。Claude Code 將工具輸入作為 JSON 在 stdin 上發送到 hook：

```json theme={null}
{ "tool_name": "Bash", "tool_input": { "command": "rm -rf /tmp/build" }, ... }
```

**2. 匹配器檢查**

匹配器 `"Bash"` 符合工具名稱，因此此 hook 群組啟動。如果您省略匹配器或使用 `"*"`，群組在事件的每次出現時啟動。

**3. If 條件檢查**

`if` 條件 `"Bash(rm *)"` 符合，因為 `rm -rf /tmp/build` 是符合 `rm *` 的子命令，因此此處理程式生成。如果命令是 `npm test`，`if` 檢查會失敗，`block-rm.sh` 永遠不會執行，避免程序生成開銷。`if` 欄位是可選的；沒有它，符合群組中的每個處理程式都執行。

**4. Hook 處理程式執行**

該指令碼檢查完整命令並找到 `rm -rf`，因此它將決定列印到 stdout：

```json theme={null}
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Destructive command blocked by hook"
  }
}
```

如果命令是更安全的 `rm` 變體，如 `rm file.txt`，指令碼會改為執行 `exit 0`。Exit code 0 且沒有輸出表示 hook 沒有決定要報告，因此工具呼叫會繼續通過正常的[權限流程](https://code.claude.com/docs/zh-TW/permissions.md)。Hook 可以拒絕呼叫，但保持沉默不會批准它。

**5. Claude Code 根據結果採取行動**

Claude Code 讀取 JSON 決定，阻止工具呼叫，並向 Claude 顯示原因。

下面的[設定](#configuration)部分記錄了完整架構，每個 [hook 事件](#hook-events)部分記錄了您的命令接收的輸入以及它可以返回的輸出。

## 設定

Hook 定義在 JSON 設定檔中。設定有三層巢狀結構：

1. 選擇要回應的 [hook 事件](#hook-events)，例如 `PreToolUse` 或 `Stop`
2. 新增 [matcher 群組](#matcher-patterns)來篩選觸發時機，例如「僅限 Bash 工具」
3. 定義一個或多個在符合時執行的 [hook 處理常式](#hook-handler-fields)

請參閱上方的 [Hook 如何解析](#how-a-hook-resolves)，其中有附註解範例的完整逐步說明。

> [!NOTE]
>
> 本頁針對每個層級使用特定術語：**hook 事件**指生命週期中的時間點，**matcher 群組**指篩選條件，**hook 處理常式**指實際執行的 shell 命令、HTTP 端點、MCP 工具、提示詞或 agent。單獨使用「hook」時指的是整體功能。

### Hook 位置

定義 hook 的位置決定其範圍：

| 位置 | 範圍 | 可共用 |
| :- | :- | :- |
| `~/.claude/settings.json` | 您的所有專案 | 否，僅限您的電腦本機 |
| `.claude/settings.json` | 單一專案 | 是，可提交至儲存庫 |
| `.claude/settings.local.json` | 單一專案 | 否，Claude Code 將設定儲存至此檔時會將其加入 gitignore |
| 受管政策設定 | 整個組織 | 是，由管理員控管 |
| [外掛](https://code.claude.com/docs/zh-TW/plugins/overview.md) `hooks/hooks.json` | 外掛啟用時 | 是，與外掛綁定 |
| [Skill](https://code.claude.com/docs/zh-TW/skills.md) frontmatter | 叫用 skill 後的工作階段剩餘期間。請參閱 [skill 與 agent 中的 hook](#hooks-in-skills-and-agents) | 是，定義於 skill 檔案中 |
| [Subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) frontmatter | 該 subagent 執行期間 | 是，定義於 subagent 檔案中 |

[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)不會讀取您本機的 `~/.claude/settings.json`。在[自行託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#permissions-and-tool-approval)中，Claude Code 也會執行操作者從 runner 主機的 `~/.claude/` 預先植入的 hook；當 runner 映像檔的受管設定檔屬於 [Claude Code 套用的受管來源](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)之一時，Claude Code 也會執行該檔案中的 hook，而依預設，這僅在伺服器受管設定與透過 MDM 傳遞的 Claude Code 政策都未提供受管層級時才會發生。請參閱[從您的設定中沿用的項目](https://code.claude.com/docs/zh-TW/cloud-environments.md#what-carries-over-from-your-setup)，了解哪些設定檔與外掛（以及因此哪些 hook）會進入雲端工作階段。

如需設定檔解析的詳細資訊，請參閱[設定](https://code.claude.com/docs/zh-TW/settings.md)。

來自設定檔、受管政策設定與外掛的 hook 也會在 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 內執行。當 subagent 呼叫工具時，`PreToolUse` 與 `PostToolUse` 等工具事件會觸發與主對話中相同的已設定 hook，且輸入會帶有用於識別 subagent 的 `agent_id` 與 `agent_type` [通用輸入欄位](#common-input-fields)。

管理員可以在[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)中使用 [`allowManagedHooksOnly`](https://code.claude.com/docs/zh-TW/settings-reference#allowmanagedhooksonly) 來限制可執行的 hook：

* 您的使用者、專案、本機及外掛 hook 會被封鎖。在受管設定 `enabledPlugins` 中強制啟用的外掛所提供的 hook 不受此限
* Claude Code 也會將您的 [`statusLine`](https://code.claude.com/docs/zh-TW/statusline)、[`fileSuggestion`](https://code.claude.com/docs/zh-TW/settings-reference#filesuggestion) 與 [`subagentStatusLine`](https://code.claude.com/docs/zh-TW/statusline#subagent-status-lines) 設定限縮為僅採用受管設定
* 除非 [`disableCommandPluginSources`](https://code.claude.com/docs/zh-TW/settings-reference#disablecommandpluginsources) 明確設為 `false`，否則 Claude Code 也會停用具有 [`command` 來源](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference#command-plugin-source)的外掛，包括在受管設定 `enabledPlugins` 中強制啟用的外掛。`command` 來源需要 Claude Code v2.1.229 或更新版本
* 除非 [`disableCommandPluginSources`](https://code.claude.com/docs/zh-TW/settings-reference#disablecommandpluginsources) 明確設為 `false`，否則 Claude Code 也會封鎖市集的 [`headersHelper` 命令](https://code.claude.com/docs/zh-TW/plugins/host-marketplace#authenticate-archive-downloads)，但受管設定本身宣告的市集除外

請參閱[在 `allowManagedHooksOnly` 下會執行的項目](https://code.claude.com/docs/zh-TW/settings-reference#what-runs-under-allowmanagedhooksonly)。

Hook 項目會在各設定層級之間合併，而不是互相取代：使用者、專案與本機設定會加入各自的 hook，而不會移除受管 hook；且在受管設定以外設定的 [`disableAllHooks`](#disable-or-remove-hooks) 無法停用受管 hook。

[HTTP hook 允許清單](https://code.claude.com/docs/zh-TW/settings-reference.md#hook-and-skill-settings)適用於所有來源的 hook，包括受管政策設定：

* `allowedHttpHookUrls`：只要在任一設定層級中定義，Claude Code 僅會在 HTTP hook 處理常式的 URL 符合合併後的允許清單時執行它
* `httpHookAllowedEnvVars`：定義後，Claude Code 只會將清單上的環境變數插入 hook 標頭中

### Matcher 模式

`matcher` 欄位用於篩選 hook 的觸發時機。Matcher 的評估方式取決於其包含的字元：

| Matcher 值 | 評估方式 | 範例 |
| :- | :- | :- |
| `"*"`、`""` 或省略 | 全部符合 | 每次發生該事件時都會觸發 |
| 僅包含字母、數字、`_`、`-`、空格、`,` 與 `\|` | 精確字串，或以 `\|` 或 `,` 分隔的精確字串清單，前後可有空白 | `Bash` 僅符合 Bash 工具；`Edit\|Write` 與 `Edit, Write` 皆精確符合這兩個工具中的任一個；`code-reviewer` 僅符合該 agent 類型 |
| 包含任何其他字元 | JavaScript 正規表示式，未錨定 | `^Notebook` 符合名稱以 `Notebook` 開頭的任何工具；`mcp__memory__.*` 符合來自 `memory` 伺服器的所有工具 |

走正規表示式路徑的 matcher 會以 JavaScript 的 `RegExp.prototype.test` 進行測試，只要值中任何位置有符合即成功。`Edit.*` 同時符合 `Edit` 與 `NotebookEdit`；需要完整字串比對時，請以 `^` 與 `$` 包住模式，例如 `^Edit$`。

`FileChanged` 與 `StopFailure` 使用較窄的精確比對字元集，僅限字母、數字、`_` 與 `|`。這兩個事件的 matcher 中若含有連字號、空格或逗號，就會走正規表示式路徑，且只有 `|` 能分隔替代項目。下表中其他支援 matcher 的事件皆接受 `|` 或 `,`。

`FileChanged` 事件在建立監看清單時不遵循這些規則。請參閱 [FileChanged](#filechanged)。

每種事件類型比對的欄位不同：

| 事件 | Matcher 篩選的對象 | Matcher 值範例 |
| :- | :- | :- |
| `PreToolUse`、`PostToolUse`、`PostToolUseFailure`、`PermissionRequest`、`PermissionDenied` | 工具名稱 | `Bash`、`Edit\|Write`、`mcp__.*` |
| `SessionStart` | 工作階段的啟動方式 | `startup`、`resume`、`clear`、`compact`、`fork` |
| `Setup` | 觸發 setup 的 CLI 旗標 | `init`、`maintenance` |
| `SessionEnd` | 工作階段結束的原因 | `clear`、`resume`、`logout`、`prompt_input_exit`、`other` |
| `Notification` | 通知類型 | `permission_prompt`、`idle_prompt`、`auth_success`、`elicitation_dialog`、`elicitation_url_dialog`、`elicitation_complete`、`elicitation_response`、`agent_needs_input`、`agent_completed`、`quota_auto_resume_fired`、`quota_auto_resume_stale`、`quota_auto_resume_disabled`、`plugin_notification` |
| `SubagentStart` | agent 類型 | `general-purpose`、`Explore`、`Plan`、自訂 agent 名稱，或外掛範圍的名稱，例如 `^my-plugin:reviewer$` |
| `PreCompact`、`PostCompact` | 觸發壓縮的原因 | `manual`、`auto` |
| `PreModelSwitch`、`PostModelSwitch` | 工作階段要切換到的模型之標準名稱，如 [PreModelSwitch](#premodelswitch) 中所述 | `claude-opus-5`、`claude-opus-4-6\|claude-opus-5`、`.*opus.*` |
| `SubagentStop` | agent 類型 | 與 `SubagentStart` 相同的值 |
| `ConfigChange` | 設定來源 | `user_settings`、`project_settings`、`local_settings`、`policy_settings`、`skills` |
| `CwdChanged` | 不支援 matcher | 每次發生時一律觸發 |
| `DirectoryAdded` | 目錄的加入方式 | `slash_command`、`register_repo_root` |
| `FileChanged` | 要監看的字面檔名（請參閱 [FileChanged](#filechanged)） | `.envrc\|.env` |
| `StopFailure` | 錯誤類型 | `rate_limit`、`overloaded`、`authentication_failed`、`oauth_org_not_allowed`、`account_on_hold`、`billing_error`、`invalid_request`、`model_not_found`、`server_error`、`max_output_tokens`、`cloud_credential_error`、`unknown` |
| `InstructionsLoaded` | 載入原因 | `session_start`、`nested_traversal`、`path_glob_match`、`include`、`compact` |
| `UserPromptExpansion` | 命令名稱 | 您的 skill 或命令名稱 |
| `Elicitation` | MCP 伺服器名稱 | 您已設定的 MCP 伺服器名稱 |
| `ElicitationResult` | MCP 伺服器名稱 | 與 `Elicitation` 相同的值 |
| `UserPromptSubmit`、`PostToolBatch`、`Stop`、`TeammateIdle`、`TaskCreated`、`TaskCompleted`、`WorktreeCreate`、`WorktreeRemove`、`MessageDisplay` | 不支援 matcher | 每次發生時一律觸發 |

以 `cloud_credential_error` 比對 `StopFailure` 需要 Claude Code v2.1.267 或更新版本，這是第一個以該值回報憑證載入失敗，而非以 `server_error` 或 `unknown` 回報的版本。

對於大多數事件，Claude Code 會以它透過 stdin 傳送給您的 hook 的 [JSON 輸入](#hook-input-and-output)中的某個欄位來評估 matcher。對於工具事件，該欄位為 `tool_name`。對於 `PreModelSwitch` 與 `PostModelSwitch`，Claude Code 會以從 `to_model` 推導出的標準名稱來評估 matcher，如 [PreModelSwitch](#premodelswitch) 中所述。每個 [hook 事件](#hook-events)章節都列出了該事件完整的 matcher 值與輸入 schema。

此範例僅在 Claude 寫入或編輯檔案時執行 lint 指令碼：

```json theme={null}
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/lint-check.sh"
          }
        ]
      }
    ]
  }
}
```

若您為不支援 matcher 的事件加入 `matcher` 欄位，該欄位會被靜默忽略。

對於工具事件，您可以在個別 hook 處理常式上設定 [`if` 欄位](#common-fields)以進一步縮小篩選範圍。`if` 使用[權限規則語法](https://code.claude.com/docs/zh-TW/permissions.md)同時比對工具名稱與引數，因此 `"Bash(git *)"` 會在 Bash 輸入的任何子命令符合 `git *` 時執行，而 `"Edit(*.ts)"` 僅對 TypeScript 檔案執行。

#### 比對 MCP 工具

[MCP](https://code.claude.com/docs/zh-TW/mcp.md) 伺服器的工具在工具事件（`PreToolUse`、`PostToolUse`、`PostToolUseFailure`、`PermissionRequest`、`PermissionDenied`）中會以一般工具的形式出現，因此您可以用比對其他工具名稱的相同方式來比對它們。

MCP 工具遵循 `mcp__<server>__<tool>` 命名模式，例如：

* `mcp__memory__create_entities`：Memory 伺服器的建立實體工具
* `mcp__filesystem__read_file`：Filesystem 伺服器的讀取檔案工具
* `mcp__github__search_repositories`：GitHub 伺服器的搜尋工具

若要比對某個伺服器的所有工具，請在伺服器前綴後加上 `.*`。`.*` 是必要的：像 `mcp__memory` 或 `mcp__brave-search` 這樣的 matcher 只包含精確比對字元，因此會被當作精確字串比較，不會符合任何工具。

* `mcp__memory__.*` 符合 `memory` 伺服器的所有工具
* `mcp__brave-search__.*` 符合名稱含有連字號的伺服器的所有工具
* `mcp__.*__write.*` 符合任何伺服器中名稱以 `write` 開頭的任何工具

來自[外掛綁定 MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md#plugin-provided-mcp-servers)的工具使用包含外掛名稱的範圍化伺服器區段：`mcp__plugin_<plugin-name>_<server-name>__<tool>`。針對單純伺服器鍵撰寫的 matcher 永遠不會對這些工具觸發。例如名為 `my-plugin` 的外掛以鍵 `db` 綁定了一個伺服器，則 `query` 工具會顯示為 `mcp__plugin_my-plugin_db__query`，因此比對該伺服器所有工具的 matcher 為 `mcp__plugin_my-plugin_db__.*`。在處理常式的 [`if` 欄位](#common-fields)中也請使用相同的範圍化工具名稱。請參閱[外掛提供的 MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md#plugin-provided-mcp-servers)，了解範圍化名稱的組成方式。

此範例會記錄所有 memory 伺服器的操作，並驗證來自任何 MCP 伺服器的寫入操作：

```json theme={null}
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "mcp__memory__.*",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Memory operation initiated' >> ~/mcp-operations.log"
          }
        ]
      },
      {
        "matcher": "mcp__.*__write.*",
        "hooks": [
          {
            "type": "command",
            "command": "/home/user/scripts/validate-mcp-write.py"
          }
        ]
      }
    ]
  }
}
```

### Hook 處理常式欄位

內層 `hooks` 陣列中的每個物件都是一個 hook 處理常式：即 matcher 符合時執行的 shell 命令、HTTP 端點、MCP 工具、LLM 提示詞或 agent。共有五種類型：

* **[命令 hook](#command-hook-fields)**（`type: "command"`）：執行 shell 命令。您的指令碼會透過 stdin 接收事件的 [JSON 輸入](#hook-input-and-output)，並透過退出碼與 stdout 回傳結果。
* **[HTTP hook](#http-hook-fields)**（`type: "http"`）：將事件的 JSON 輸入以 HTTP POST 請求傳送至某個 URL。端點會透過回應主體，以與命令 hook 相同的 [JSON 輸出格式](#json-output)回傳結果。
* **[MCP 工具 hook](#mcp-tool-hook-fields)**（`type: "mcp_tool"`）：呼叫已設定的 [MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md)上的工具。工具的文字輸出會比照命令 hook 的 stdout 處理。
* **[提示詞 hook](#prompt-and-agent-hook-fields)**（`type: "prompt"`）：將提示詞傳送給 Claude 模型進行單回合評估。模型會以 JSON 回傳其決定。請參閱[以提示詞為基礎的 hook](#prompt-based-hooks)。
* **[Agent hook](#prompt-and-agent-hook-fields)**（`type: "agent"`）：產生一個 subagent，可使用 Read、Grep 與 Glob 等工具驗證條件後再回傳決定。Agent hook 屬實驗性功能，可能會變更。請參閱[以 agent 為基礎的 hook](#agent-based-hooks)。

事件觸發時，其所有符合的 hook 會平行執行。若其中超過 12 個是提示詞或 agent hook，會同時執行其中 12 個，其餘的則在執行中的 hook 完成時陸續開始。每個等待中 hook 的 [`timeout`](#common-fields) 會在該 hook 開始執行時才開始計算。

若您在多個設定檔中定義相同的處理常式，它只會執行一次。外掛或 skill 中的相同處理常式副本則會分開執行。

處理常式會在目前目錄中以 Claude Code 的環境執行。若目前目錄已不存在，例如在工作階段中途被另一個 shell 刪除的 worktree 或暫存目錄，Claude Code 會從下列目錄中第一個仍存在者執行命令 hook：工作階段啟動時的目錄、專案根目錄、您的家目錄，或系統暫存目錄。Claude Code 會在[偵錯日誌](#debug-hooks)中記錄一則指出備援目錄的警告。若是您從桌面應用程式啟動的 worktree 工作階段，請參閱 [worktree 與主要 checkout 共用的項目](https://code.claude.com/docs/zh-TW/worktrees.md#what-worktrees-share-with-the-main-checkout)。

`$CLAUDE_CODE_REMOTE` 環境變數在遠端 Web 環境中為 `"true"`，在本機 CLI 中則未設定。Claude Code v2.1.199 及更新版本會在本機工作階段具有作用中的 Remote Control 連線時，將 [`$CLAUDE_CODE_BRIDGE_SESSION_ID`](https://code.claude.com/docs/zh-TW/env-vars) 設為 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 工作階段 ID。

#### 通用欄位

這些欄位適用於所有 hook 類型：

| 欄位 | 必要 | 說明 |
| :- | :- | :- |
| `type` | 是 | `"command"`、`"http"`、`"mcp_tool"`、`"prompt"` 或 `"agent"` |
| `if` | 否 | 用於篩選此 hook 執行時機的[權限規則語法](https://code.claude.com/docs/zh-TW/permissions.md#permission-rule-syntax)，例如 `"Bash(git *)"` 或 `"Edit(*.ts)"`。只有在工具呼叫符合該模式時，hook 命令才會執行。請參閱 [Bash 比對表](#bash-if-matching)，了解 Bash 模式如何針對子命令、`$()` 與反引號進行評估。僅在工具事件上評估：`PreToolUse`、`PostToolUse`、`PostToolUseFailure`、`PermissionRequest` 與 `PermissionDenied`。在其他事件上，設定了 `if` 的 hook 永遠不會執行 |
| `timeout` | 否 | 取消前的秒數。對於以 [`async: true`](#run-hooks-in-the-background) 執行的命令 hook，Claude Code 不會強制執行此值。預設值：`command`、`http` 與 `mcp_tool` 為 600；`prompt` 為 30；`agent` 為 60。在 [`UserPromptSubmit`](#userpromptsubmit)、[`PreModelSwitch`](#premodelswitch) 與 [`PostModelSwitch`](#postmodelswitch) 上，Claude Code 會將 `command`、`http` 與 `mcp_tool` 的預設值降為 30，在 [`MessageDisplay`](#messagedisplay) 上則降為 10。[`SessionEnd`](#sessionend) hook 共用 1.5 秒的時間預算；若您的設定為個別 hook 設定了更長的 `timeout`，Claude Code 會將預算提高以配合，最多 60 秒 |
| `statusMessage` | 否 | hook 執行期間顯示的自訂轉圈訊息 |
| `once` | 否 | 若為 `true`，Claude Code 會在 hook 第一次成功執行後將其移除。執行失敗、以退出碼 2 封鎖或逾時的情況下，hook 會保留，因此在下一個符合的事件上會再次執行。僅對在 [skill frontmatter](#hooks-in-skills-and-agents) 中宣告的 hook 生效；在設定檔與 agent frontmatter 中會被忽略 |

`if` 欄位只能容納一條權限規則。沒有 `&&`、`||` 或清單語法可用來組合規則；若要套用多個條件，請為每個條件分別定義 hook 處理常式。

在檔案工具的 `if` 條件中，像 `"Edit(src/**)"` 這樣的單一區段目錄模式只會符合工作目錄中的 `src` 目錄及其下的檔案。若要符合任意深度中名為 `src` 的目錄，請寫成 `"Edit(**/src/**)"`。

#### `if` 模式如何比對 Bash 命令

對於 [`if` 欄位](#common-fields)中的 Bash 模式，您的 hook 命令是否執行取決於模式的形式以及 Claude 所叫用的 Bash 命令。比對前會先移除開頭的 `VAR=value` 指派。

| `if` 模式 | Bash 命令 | Hook 是否執行？ | 原因 |
| :- | :- | :- | :- |
| `Bash(git *)` | `FOO=bar git push` | 是 | 開頭的指派會被移除；`git push` 符合 |
| `Bash(git *)` | `npm test && git push` | 是 | 每個子命令都會檢查；`git push` 符合 |
| `Bash(rm *)` | `echo $(rm -rf /)` | 是 | `$()` 與反引號內的命令會被檢查；`rm -rf /` 符合 |
| `Bash(rm *)` | `echo $(date)` | 否 | 沒有子命令符合 `rm *` |
| `Bash(git push *)` | `echo $(date)` | 是 | 指定超過命令名稱的模式，在遇到 `$()`、反引號或 `$VAR` 時仍會執行 hook |

當 Claude Code 無法判斷 Bash 輸入會執行哪些命令時，無論模式為何都會執行您的 hook。由於 `if` 篩選僅為盡力而為，若要強制實施嚴格的允許或拒絕，請使用[權限系統](https://code.claude.com/docs/zh-TW/permissions.md)而非 hook。

#### 命令 hook 欄位

除了[通用欄位](#common-fields)之外，命令 hook 還接受下列欄位：

| 欄位 | 必要 | 說明 |
| :- | :- | :- |
| `command` | 是 | 要執行的 shell 命令。搭配 `args` 時，則為要直接產生的可執行檔。請參閱 [Exec 形式與 shell 形式](#exec-form-and-shell-form) |
| `args` | 否 | 引數清單。若有此欄位，`command` 會被解析為可執行檔，並以 `args` 作為引數向量直接產生，不經過 shell。請參閱 [Exec 形式與 shell 形式](#exec-form-and-shell-form) |
| `async` | 否 | 若為 `true`，會在背景執行而不封鎖。請參閱[在背景執行 hook](#run-hooks-in-the-background) |
| `asyncRewake` | 否 | 若為 `true`，會在背景執行，並在退出碼為 2 時喚醒 Claude。Hook 的 stderr（若 stderr 為空則為 stdout）會以[系統提醒](https://code.claude.com/docs/zh-TW/glossary.md#system-reminder)的形式顯示給 Claude，讓它能對長時間執行的背景失敗做出反應 |
| `shell` | 否 | 此 hook 使用的 shell。接受 `"bash"` 或 `"powershell"`。預設為 `"bash"`，在未安裝 Git Bash 的 Windows 上則為 `"powershell"`。設為 `"powershell"` 會在 Windows 上透過 PowerShell 執行命令。由於 hook 會直接產生 PowerShell，因此不需要 `CLAUDE_CODE_USE_POWERSHELL_TOOL`。設定了 `args` 時會被忽略 |
| `onFailure` | 否 | hook 失敗時，觸發該 hook 的動作是否繼續進行：`"continue"` 或 `"block"`。關於 `"block"` 以及未設定此欄位時的行為，請參閱[在 hook 失敗時封鎖動作](#block-the-action-when-a-hook-fails)。需要 Claude Code v2.1.295 或更新版本 |

##### Exec 形式與 shell 形式

設定了 `args` 時，命令 hook 會以 exec 形式執行；省略 `args` 時則以 shell 形式執行。只要 hook 參照了[路徑預留位置](#reference-scripts-by-path)，就請設定 `args`，因為每個元素都會作為單一引數傳遞，無需加引號。當您需要管線或 `&&` 等 shell 功能，或上述兩種情況都不適用時，請省略 `args`。

**Exec 形式**在有 `args` 時執行。Claude Code 會將 `command` 解析為 `PATH` 上的可執行檔，並以 `args` 作為引數向量直接產生它。由於沒有 shell，每個 `args` 元素都會完全依照所寫的內容成為一個引數，而 `${CLAUDE_PLUGIN_ROOT}` 等路徑預留位置會以純字串形式代入 `command` 與每個 `args` 元素。撇號、`$` 與反引號等特殊字元會原封不動地傳遞，因為沒有 shell 會解譯它們。在任何平台上都不會進行 shell 斷詞。

**Shell 形式**在沒有 `args` 時執行。`command` 字串會傳給 shell：macOS 與 Linux 上為 `sh -c`，Windows 上為 Git Bash，未安裝 Git Bash 時則為 PowerShell。設定 `shell` 欄位可明確選擇。Shell 會對字串進行斷詞、展開變數，並解譯管線、`&&`、重新導向與萬用字元。

> [!NOTE]
>
> 在 Windows 上，exec 形式要求 `command` 解析為真正的可執行檔，例如 `.exe`。npm、npx、eslint 與其他工具安裝在 `node_modules/.bin` 中的 `.cmd` 與 `.bat` shim 並非可執行檔，無法在沒有 shell 的情況下產生。若要以 exec 形式執行它們，請直接以 `node` 叫用底層指令碼，例如 `"command": "node", "args": ["${CLAUDE_PLUGIN_ROOT}/node_modules/eslint/bin/eslint.js"]`。`node` 加上指令碼路徑的模式在所有平台上都可運作，因為 `node.exe` 是真正的二進位檔。若要依名稱執行 `.cmd` 或 `.bat` shim，請使用 shell 形式。

此範例執行與外掛綁定的 Node 指令碼。Exec 形式會將解析後的指令碼路徑作為單一引數傳遞，無需加引號：

```json theme={null}
{
  "type": "command",
  "command": "node",
  "args": ["${CLAUDE_PLUGIN_ROOT}/scripts/format.js", "--fix"]
}
```

等效的 shell 形式需要加引號，以處理含有空格或特殊字元的路徑：

```json theme={null}
{
  "type": "command",
  "command": "node \"${CLAUDE_PLUGIN_ROOT}\"/scripts/format.js --fix"
}
```

兩種形式都支援相同的[路徑預留位置](#reference-scripts-by-path)，並且都會在產生的程序上將它們匯出為環境變數 `CLAUDE_PROJECT_DIR`、`CLAUDE_PLUGIN_ROOT` 與 `CLAUDE_PLUGIN_DATA`，因此無論指令碼是如何啟動的，都能讀取 `process.env.CLAUDE_PLUGIN_ROOT`。

外掛 hook 另外還會代入 [`${user_config.*}`](https://code.claude.com/docs/zh-TW/plugins/manifest-reference#user-configuration) 值，但僅限 exec 形式：該值會以純字串形式代入 `command` 與每個 `args` 元素，因此不會被 shell 重新剖析。

`command` 參照 `${user_config.*}` 的 shell 形式外掛 hook 會以[錯誤](https://code.claude.com/docs/zh-TW/errors.md#plugin-command-references-user-config)失敗，而不會執行。若要在 shell 形式的 hook 中使用選項值，請讀取 `$CLAUDE_PLUGIN_OPTION_<KEY>` 環境變數，例如 `webhook_url` 選項對應的 `$CLAUDE_PLUGIN_OPTION_WEBHOOK_URL`，或設定 `args` 將 hook 切換為 exec 形式。在 v2.1.207 之前，shell 形式的外掛 hook 命令也會代入 `${user_config.*}`。

> [!NOTE]
>
> 在 exec 形式中，`command` 只能是可執行檔名稱或路徑。若 `command` 是不含路徑分隔符號的單純名稱，且在有 `args` 的情況下包含空白，Claude Code 會記錄警告，因為產生程序將會失敗：不存在名為 `node script.js` 的可執行檔。請將多餘的 token 移至 `args`。含有空格的絕對路徑，例如 `C:\Program Files\nodejs\node.exe`，是單一有效的可執行檔，不會觸發警告。

#### HTTP hook 欄位

除了[通用欄位](#common-fields)之外，HTTP hook 還接受下列欄位：

| 欄位 | 必要 | 說明 |
| :- | :- | :- |
| `url` | 是 | POST 請求要傳送到的 URL |
| `headers` | 否 | 以鍵值對表示的額外 HTTP 標頭。值支援使用 `$VAR_NAME` 或 `${VAR_NAME}` 語法插入環境變數。只有列在 `allowedEnvVars` 中的變數會被解析 |
| `allowedEnvVars` | 否 | 可插入標頭值中的環境變數名稱清單。對未列出之變數的參照會被替換為空字串。任何環境變數插入都必須設定此欄位才能運作 |
| `onFailure` | 否 | hook 失敗時該動作的處理方式：`"continue"`（預設）或 `"block"`。請參閱[在 hook 失敗時封鎖動作](#block-the-action-when-a-hook-fails)。需要 Claude Code v2.1.295 或更新版本 |

Claude Code 會將 hook 的 [JSON 輸入](#hook-input-and-output)作為 POST 請求主體傳送，並帶有 `Content-Type: application/json`。回應主體使用與命令 hook 相同的 [JSON 輸出格式](#json-output)。

錯誤處理方式與命令 hook 不同；請參閱 [HTTP 回應處理](#http-response-handling)。

此範例將 `PreToolUse` 事件傳送至本機驗證服務，並使用 `MY_TOKEN` 環境變數中的 token 進行驗證：

```json theme={null}
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "http",
            "url": "http://localhost:8080/hooks/pre-tool-use",
            "timeout": 30,
            "headers": {
              "Authorization": "Bearer $MY_TOKEN"
            },
            "allowedEnvVars": ["MY_TOKEN"]
          }
        ]
      }
    ]
  }
}
```

#### MCP 工具 hook 欄位

除了[通用欄位](#common-fields)之外，MCP 工具 hook 還接受下列欄位：

| 欄位 | 必要 | 說明 |
| :- | :- | :- |
| `server` | 是 | 已設定的 MCP 伺服器名稱。對於[外掛綁定的伺服器](https://code.claude.com/docs/zh-TW/mcp.md#plugin-provided-mcp-servers)，這是範圍化名稱 `plugin:<plugin-name>:<server-name>`，例如 `plugin:my-plugin:db`，而非單純的伺服器鍵 |
| `tool` | 是 | 要在該伺服器上呼叫的工具名稱 |
| `input` | 否 | 傳遞給工具的引數。字串值支援從 hook 的 [JSON 輸入](#hook-input-and-output)進行 `${path}` 代入，例如 `"${tool_input.file_path}"` |

此範例會在每次 `Write` 或 `Edit` 後，呼叫 `my_server` MCP 伺服器上的 `security_scan` 工具，並傳入被編輯檔案的路徑：

```json theme={null}
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "mcp_tool",
            "server": "my_server",
            "tool": "security_scan",
            "input": { "file_path": "${tool_input.file_path}" }
          }
        ]
      }
    ]
  }
}
```

##### 如何讀取工具的結果

Claude Code 讀取工具文字內容的方式與讀取命令 hook stdout 相同，遵循[退出碼 0 下的剖析規則](#exit-code-0)。若工具回傳 `isError: true`，hook 會產生非封鎖性錯誤，並繼續執行。

##### 當伺服器仍在連線中

在 hook 可以封鎖或變更結果的事件上，例如 `PreToolUse` 或 `Stop`，Claude Code 會在呼叫工具前等待正在連線的伺服器，最多等待 [`MCP_TIMEOUT`](https://code.claude.com/docs/zh-TW/env-vars)，且不超過 hook 本身的 [`timeout`](#common-fields)。在觀察性事件上，例如 `Notification` 或 `SessionEnd`，則不會等待。

顯示 [`cached` 狀態](https://code.claude.com/docs/zh-TW/mcp#server-status-detail)的伺服器會在 hook 呼叫其工具時進行連線。若此時伺服器未連線，hook 會產生非封鎖性錯誤，並繼續執行。Hook 永遠不會啟動 OAuth 流程，因此請先[從 `/mcp` 驗證伺服器](https://code.claude.com/docs/zh-TW/mcp#authenticate-with-remote-mcp-servers)。

##### 在 MCP 伺服器可用前觸發的事件

啟動時的 `SessionStart`（包括使用 `--continue` 或 `--resume` 時）以及每個 `Setup` 事件，都會在工作階段的 MCP 伺服器可供 hook 使用之前觸發。Claude Code 會略過這些事件的 `mcp_tool` hook 而不呼叫工具，且[偵錯日誌](#debug-hooks)會記錄 `mcp_tool hooks are not available for the 'SessionStart' hook event (no MCP client context)`，或指名 `Setup` 的相同訊息。當 `SessionStart` 在工作階段稍後（`/clear` 或壓縮之後）再次觸發時，其 `mcp_tool` hook 會執行。對於工作階段啟動時所需的任何內容，請改在 `SessionStart` 上使用 `type: "command"` hook。

#### 提示詞與 agent hook 欄位

除了[通用欄位](#common-fields)之外，提示詞與 agent hook 還接受下列欄位：

| 欄位 | 必要 | 說明 |
| :- | :- | :- |
| `prompt` | 是 | 要傳送給模型的提示詞文字。使用 `$ARGUMENTS` 作為 hook 輸入 JSON 的預留位置。若要包含字面文字，請以反斜線跳脫：`\$1.00` 會呈現為 `$1.00` |
| `model` | 否 | 用於評估的模型。預設為 Claude Code 用於[背景功能](https://code.claude.com/docs/zh-TW/model-config.md#environment-variables)的模型 |

### 以路徑參照指令碼

使用這些預留位置，以相對於專案或外掛根目錄的方式參照 hook 指令碼，不受 hook 執行時的工作目錄影響：

* `${CLAUDE_PROJECT_DIR}`：工作階段啟動時的專案根目錄。Claude Code 也會在 [stdio MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md#option-3-add-a-local-stdio-server)與外掛 LSP 伺服器的環境中設定此變數。
* `${CLAUDE_PLUGIN_ROOT}`：外掛的安裝目錄，用於與[外掛](https://code.claude.com/docs/zh-TW/plugins/overview.md)綁定的指令碼。請參閱[外掛環境變數](https://code.claude.com/docs/zh-TW/plugins/manifest-reference.md#environment-variables)，了解此路徑在更新時的行為。
* `${CLAUDE_PLUGIN_DATA}`：外掛的[持久資料目錄](https://code.claude.com/docs/zh-TW/plugins/components.md#path-variables-and-persistent-data)，用於應在外掛更新後保留的相依性與狀態。

> [!NOTE]
>
> **Worktree 的情況不同。** 若 Claude 在工作階段期間進入 [worktree](https://code.claude.com/docs/zh-TW/worktrees.md)，Claude Code 會讓 `${CLAUDE_PROJECT_DIR}` 維持原樣，並以另一種方式將 worktree 路徑傳給您的 hook：
>
> * **`${CLAUDE_PROJECT_DIR}` 保持不變**：它仍指向工作階段啟動時的專案根目錄，因此像 `${CLAUDE_PROJECT_DIR}/.claude/hooks/check-style.sh` 這樣的命令仍會在主要 checkout 中執行指令碼。
> * **`cwd` 跟隨 Claude**：Claude 進入 worktree 後，hook [輸入 JSON](#common-input-fields) 中的 `cwd` 欄位為 worktree 根目錄；Claude 執行 `cd` 後則為新的目錄。當 hook 需要知道 Claude 正在哪個目錄中工作時，請讀取此欄位。
>
> 若是您從桌面應用程式啟動的 worktree 工作階段，請參閱 [worktree 與主要 checkout 共用的項目](https://code.claude.com/docs/zh-TW/worktrees.md#what-worktrees-share-with-the-main-checkout)，了解 `${CLAUDE_PROJECT_DIR}` 指向何處。

任何參照路徑預留位置的 hook，建議使用 [exec 形式](#exec-form-and-shell-form)。在 shell 形式中，請以雙引號包住每個預留位置。

> [tab] 專案指令碼
>
> 此範例使用 `${CLAUDE_PROJECT_DIR}`，在任何 `Write` 或 `Edit` 工具呼叫後，從專案的 `.claude/hooks/` 目錄執行樣式檢查器：
>
> ```json theme={null}
> {
>   "hooks": {
>     "PostToolUse": [
>       {
>         "matcher": "Write|Edit",
>         "hooks": [
>           {
>             "type": "command",
>             "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/check-style.sh",
>             "args": []
>           }
>         ]
>       }
>     ]
>   }
> }
> ```

> [tab] 外掛指令碼
>
> 在 `hooks/hooks.json` 中定義外掛 hook，可選擇加入頂層的 `description` 欄位。外掛啟用時，其 hook 會與您的使用者及專案 hook 合併。
>
> 此範例執行與外掛綁定的格式化指令碼：
>
> ```json theme={null}
> {
>   "description": "Automatic code formatting",
>   "hooks": {
>     "PostToolUse": [
>       {
>         "matcher": "Write|Edit",
>         "hooks": [
>           {
>             "type": "command",
>             "command": "${CLAUDE_PLUGIN_ROOT}/scripts/format.sh",
>             "args": [],
>             "timeout": 30
>           }
>         ]
>       }
>     ]
>   }
> }
> ```
>
> 如需建立外掛 hook 的詳細資訊，請參閱[外掛元件參考](https://code.claude.com/docs/zh-TW/plugins/components.md#hooks)。

### Skill 與 agent 中的 hook

除了設定檔與外掛之外，hook 也可以使用 frontmatter 直接定義在 [skill](https://code.claude.com/docs/zh-TW/skills.md) 與 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 中，其設定格式與以設定為基礎的 hook 相同。Claude Code 保留其註冊的時間長短取決於元件：

* **Subagent hook**：Claude Code 只會在該 subagent 執行期間執行它們，並在其完成時移除。Claude Code 會將此處的 `Stop` hook 轉換為 `SubagentStop`，也就是 subagent 完成時觸發的事件。
* **Skill hook**：Claude Code 會在您或 Claude 叫用 skill 時註冊它們，並在工作階段剩餘期間持續執行，包括 skill 本身所在回合之後的回合。若要讓 Claude Code 改為在 hook 第一次成功執行後將其移除，請在其上設定 [`once: true`](#common-fields)。

此 skill 定義了一個 `PreToolUse` hook，會在每個 `Bash` 命令之前執行安全驗證指令碼：

```yaml theme={null}
---
name: secure-operations
description: Perform operations with security checks
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/security-check.sh"
---
```

Subagent 在其 YAML frontmatter 中使用相同的格式。

專案 skill 中的 frontmatter hook 遵循與[設定檔中的 hook 相同的工作區信任規則](#workspace-trust)。Claude Code 會在您或 Claude 叫用 skill 時註冊它們，包括在您尚未信任的資料夾中執行 `-p` 時。

專案 subagent 中的 frontmatter hook，只有在您為 agent 檔案所在的資料夾接受[工作區信任對話方塊](https://code.claude.com/docs/zh-TW/permissions.md#project-allow-rules-and-workspace-trust)後才會執行。`-p` 工作階段不算作接受。[信任資料夾前會執行的項目](https://code.claude.com/docs/zh-TW/permissions.md#what-runs-before-you-trust-a-folder)將此與設定檔規則進行比較，而 subagent 頁面列出了[哪些範圍不受此限](https://code.claude.com/docs/zh-TW/sub-agents.md#hooks-in-subagent-frontmatter)。

#### Skill hook 的限制

若您或 Claude 叫用 skill 後，該 skill 的 frontmatter hook 未觸發，請在該工作階段中執行 [`/hooks`](#the-%2Fhooks-menu)。若清單中列出了它們，請參閱 [Hook 未觸發](https://code.claude.com/docs/zh-TW/hooks-guide.md#hook-not-firing)。若清單中一個都未列出，該 skill 可能受到僅限外掛的鎖定，或已超過 hook 上限，因而在沒有任何 frontmatter hook 的情況下執行。請逐一檢查各種情況：

* **僅限外掛的鎖定**：您組織的管理員可以透過 [`strictPluginOnlyCustomization`](https://code.claude.com/docs/zh-TW/settings-reference#strictpluginonlycustomization-hooks) 受管設定，將 hook 鎖定為僅限外掛與受管設定。在此鎖定下，只有外掛 skill、[隨附 skill](https://code.claude.com/docs/zh-TW/skills.md#bundled-skills)，或位於[受管設定目錄](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)中的 skill 才會保留其 frontmatter hook。您自己設定檔中的 hook 也不會執行。
  * **檢查**：在 Claude Code 工作階段中輸入 `/status`。若 [`Setting sources` 行](https://code.claude.com/docs/zh-TW/settings#check-what-your-organization-enforces)包含 `Enterprise managed settings`，請詢問您的管理員 `strictPluginOnlyCustomization` 是否鎖定了 hook。
  * **修正**：將該 skill 移入[外掛](https://code.claude.com/docs/zh-TW/plugins/create.md#convert-an-existing-claude-setup)，因為外掛 skill 會保留其 frontmatter hook。將該外掛列入[市集](https://code.claude.com/docs/zh-TW/plugins/create-marketplace.md#create-a-marketplace)，再從該處安裝。若 Claude Code 以 [`is blocked by enterprise policy`](https://code.claude.com/docs/zh-TW/plugins/troubleshooting#marketplace-source-is-blocked-by-enterprise-policy) 拒絕該市集，請要求您的管理員允許該市集。
* **Hook 上限**：在 Claude Code v2.1.304 或更新版本中，每個 skill 來源在每個工作階段中都有各自的上限。您的專案、您的個人 skill 資料夾，以及每個外掛都算作不同的來源。來自同一來源的 skill 最多可註冊 1,024 個 hook。這些 hook 的 matcher 總計最多 16,384 個字元。底下有多個 hook 的 matcher，會針對每個 hook 各計算一次。
  * **檢查**：在開啟偵錯日誌的情況下，重現 hook 未觸發的工作階段：
    1. 從您的 shell 以 `claude --debug` 啟動新的工作階段。若您不是從 shell 啟動工作階段，請改為在新工作階段中先輸入 [`/debug`](https://code.claude.com/docs/zh-TW/commands#all-commands)。
    2. 以相同順序叫用相同的 skill，包括由 Claude 叫用的那些，因為兩項總計都是逐個 skill 累加的。對於無法以命令形式輸入的 skill，請要求 Claude 叫用。
    3. 在[偵錯日誌](#debug-hooks)中搜尋 `registers none of its hooks`。包含該文字的行會指出超過上限的 skill。
  * **修正**：在該 skill 或同一來源的其他 skill 中宣告較少的 hook 或較短的 matcher，然後啟動新的工作階段。若這些 skill 並非您可編輯的，請要求其作者做出該變更。在那之前，請啟動新的工作階段，並在叫用同一來源的任何其他 skill 之前，先叫用您需要的 skill。

若兩種情況都不符合，請檢查是否有[未能剖析的 frontmatter](https://code.claude.com/docs/zh-TW/skills.md#skill-not-triggering)。

### `/hooks` 選單

在 Claude Code 中輸入 `/hooks`，即可開啟已設定 hook 的唯讀瀏覽器。清單會標示每個 hook 的來源，例如使用者設定、專案設定、本機設定、外掛或目前的工作階段。

選取某個 hook 即可查看其執行內容的完整文字以及定義位置，例如其設定檔的路徑或其外掛的名稱。

若要瀏覽所有 hook 事件，包括未設定任何 hook 的事件，請在清單末端選取 `All events`。

### 停用或移除 hook

若要移除定義在設定檔中的 hook，請從該檔案中刪除其項目。

若要暫時停用所有 hook 而不移除它們，請在您的設定檔中設定 `"disableAllHooks": true`。Claude Code 會讀取套用[設定優先順序](https://code.claude.com/docs/zh-TW/settings.md#settings-precedence)後剩下的值，因此專案 `.claude/settings.json` 中的 `"disableAllHooks": false` 會覆寫您使用者設定中的 `true`。若要不論專案設定為何都在單次執行中關閉 hook，請傳入 `--settings '{"disableAllHooks": true}'`，它會優先於專案與本機設定。無法在保留於設定中的同時停用個別 hook。

`disableAllHooks` 設定會遵循受管設定的階層。若管理員已透過受管政策設定來設定 hook，則在使用者、專案或本機設定中設定的 `disableAllHooks` 無法停用這些受管 hook。只有在受管設定層級設定的 `disableAllHooks` 才能停用受管 hook。如需各層級的完整作用範圍，請參閱 [`disableAllHooks`](https://code.claude.com/docs/zh-TW/settings-reference#disableallhooks)。

直接編輯設定檔中的 hook，通常會由檔案監看程式自動偵測並套用。

## Hook 輸入和輸出

命令 hook 透過 stdin 接收 JSON 資料，並透過退出碼、stdout 和 stderr 傳回結果。HTTP hook 接收相同的 JSON 作為 POST 請求正文，並透過 HTTP 回應正文傳回結果。本部分涵蓋所有事件通用的欄位和行為。每個事件在 [Hook 事件](#hook-events) 下的部分包括其特定的輸入 schema 和決定控制選項。

在 macOS 和 Linux 上，命令 hook 在沒有控制終端機的自己的工作階段中執行。Hook 程序和任何子程序無法開啟 `/dev/tty` 或直接向 Claude Code 介面發送逃逸序列。Windows 沒有 `/dev/tty`。

要在任何平台上向使用者顯示訊息，請在 JSON 輸出中返回 [`systemMessage`](#json-output)。某些事件會捨棄它或將其傳遞到其他地方，每個 [事件的部分](#hook-events) 都會說明。要觸發桌面通知、設定視窗標題或響鈴，請改為返回 [`terminalSequence`](#emit-terminal-notifications)。

### 通用輸入欄位

Hook 事件接收這些欄位作為 JSON，除了每個 [hook 事件](#hook-events) 部分中記錄的事件特定欄位。對於命令 hook，此 JSON 透過 stdin 到達。對於 HTTP hook，它作為 POST 請求正文到達。

| 欄位 | 描述 |
| :- | :- |
| `session_id` | 目前工作階段識別碼 |
| `prompt_id` | 識別目前正在處理的使用者提示詞的 UUID。與 [OpenTelemetry 事件上的 `prompt.id` 屬性](https://code.claude.com/docs/zh-TW/monitoring-usage#event-correlation-attributes) 相符，因此您可以將 hook 輸出與單一提示詞的遙測相關聯。在第一個使用者輸入之前不存在 |
| `transcript_path` | 對話 JSON 的路徑。逐字稿檔案以非同步方式寫入，可能滯後於記憶體中的對話，因此當 hook 觸發時，它可能尚未包含目前回合的最新訊息。需要目前回合最後助手文字的 hook 應在 [Stop](#stop) 和 [SubagentStop](#subagentstop) 上使用 `last_assistant_message`，而不是讀取逐字稿 |
| `cwd` | 叫用 hook 時的目前工作目錄 |
| `scratchpad_dir` | 工作階段的 [暫存目錄](https://code.claude.com/docs/zh-TW/claude-directory.md#session-scratchpad-directory) 的路徑，Claude 在其中保存臨時工作檔案。當工作階段沒有暫存或臨時目錄不可用時不存在。需要 Claude Code v2.1.257 或更新版本 |
| `permission_mode` | 目前 [權限模式](https://code.claude.com/docs/zh-TW/permissions.md#permission-modes)：`"default"`、`"plan"`、`"acceptEdits"`、`"auto"`、`"dontAsk"` 或 `"bypassPermissions"`。標記為**手動**的模式以 `"default"` 到達，永遠不會以 `"manual"` 到達，因此匹配 `"default"` 的指令碼繼續工作。並非所有事件都接收此欄位。檢查每個 [hook 事件](#hook-events) 部分中的 JSON 範例 |
| `effort` | 物件，其 `level` 為執行 hook 時的 [effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level) 設定，包括 skill、subagent 或 `ultrathink` 的等級：`"low"`、`"medium"`、`"high"`、`"xhigh"` 或 `"max"`。在支援 effort 的模型上，存在於 `PreToolUse`、`PostToolUse`、`Stop`、`SubagentStop` 以及其他具有工具使用上下文的事件中。如果模型不支援您的等級，`level` 為實際執行的等級。您變更的等級可能會在它[開始生效](https://code.claude.com/docs/zh-TW/model-config.md#when-a-new-effort-level-starts)之前就顯示在此處。`$CLAUDE_EFFORT` 保存相同的等級。 |
| `hook_event_name` | 觸發的事件名稱 |

`agent_id` 和 `agent_type` 會告訴您的指令碼 hook 是在哪個 agent 中觸發的，例如 subagent、[同一程序內的隊友](https://code.claude.com/docs/zh-TW/agent-teams.md#choose-a-display-mode)，或您透過 `--agent` 選擇的 agent：

| 欄位 | 描述 |
| :- | :- |
| `agent_id` | hook 觸發所在的 subagent 或同一程序內隊友的唯一識別碼。 |
| `agent_type` | Agent 名稱（例如 `"Explore"` 或 `"security-reviewer"`）。當工作階段使用 `--agent` 或 hook 在 subagent 內觸發時出現。對於 subagent，subagent 的類型優先於工作階段的 `--agent` 值。請參閱 [SubagentStart](#subagentstart) 以了解自訂和外掛 subagent 報告的值，以及如何針對外掛範圍名稱編寫 matcher。 |

只有 [`SessionStart`](#sessionstart) hook 可以接收 `model` 欄位，且 Claude Code 不一定包含它。[`PreModelSwitch`](#premodelswitch) 和 [`PostModelSwitch`](#postmodelswitch) hook 改為接收 `from_model` 和 `to_model`，因此使用 PostModelSwitch hook 來追蹤模型在工作階段期間的變化。

沒有 `$CLAUDE_MODEL` 環境變數。如果您在 shell 中設定了 `$ANTHROPIC_MODEL`，hook 可以讀取它，但當您在工作階段期間使用 `/model` 切換模型時，該值不會改變。

Hook 程序繼承父環境，但不包括 Claude Code [從它產生的每個子程序中移除](https://code.claude.com/docs/zh-TW/monitoring-usage.md#administrator-configuration) 的 `OTEL_*` 匯出器變數，以及當 [`CLAUDE_CODE_SUBPROCESS_ENV_SCRUB`](https://code.claude.com/docs/zh-TW/env-vars#variables) 設定為 `1` 時它剝離的變數。在[套用 HIPAA 設定](https://code.claude.com/docs/zh-TW/hipaa-setup.md#check-how-developers-sign-in-and-connect)的工作階段中，Claude Code 也會從 hook 的環境中[移除 Anthropic 憑證](https://code.claude.com/docs/zh-TW/hipaa-setup.md#anthropic-credentials-in-commands-hooks-and-mcp-servers)。

例如，Bash 命令的 `PreToolUse` hook 在 stdin 上接收此內容：

```json theme={null}
{
  "session_id": "abc123",
  "prompt_id": "550e8400-e29b-41d4-a716-446655440000",
  "transcript_path": "/home/user/.claude/projects/.../transcript.jsonl",
  "cwd": "/home/user/my-project",
  "scratchpad_dir": "/tmp/claude-1000/-home-user-my-project/abc123/scratchpad",
  "permission_mode": "default",
  "hook_event_name": "PreToolUse",
  "tool_name": "Bash",
  "tool_input": {
    "command": "npm test",
    "description": "Run test suite",
    "timeout": 120000,
    "run_in_background": false
  },
  "tool_use_id": "toolu_01ABC123..."
}
```

`tool_name`、`tool_input` 和 `tool_use_id` 欄位是事件特定的。每個 [hook 事件](#hook-events) 部分記錄了該事件的額外欄位。

### 退出碼輸出

當您的 hook 執行完成時，Claude Code 會根據其退出碼決定是否繼續執行觸發該 hook 的操作，例如工具呼叫或提示詞：

* **成功**：您的 hook 以 0 退出。Claude Code 套用您的 hook 列印的任何 [JSON 輸出](#json-output) 欄位，除非這些欄位阻止或拒絕該操作，否則操作會繼續進行。[啟動背景程序的 hook](#hooks-that-start-a-background-process) 說明了例外情況。
* **阻止性錯誤**：您的 hook 以 2 退出。在 [可以阻止的事件](#exit-code-2-behavior-per-event) 上，Claude Code 會停止該操作。
* **非阻止性錯誤**：您的 hook 以任何其他代碼退出，或以其他方式失敗，例如無法啟動或列印無效的 JSON。操作會繼續進行，但 [失敗時會阻止操作的 hook](#block-the-action-when-a-hook-fails) 除外，例如將 `onFailure` 設定為 `"block"` 的 hook。在 `PreToolUse` 等事件上，您會在逐字稿中看到 `<hook name> hook error` 通知。

您的 hook 列印到 stdout 的內容可能會改變結果。例如，當 `PreToolUse` hook 以 1 退出，但列印了通過驗證的 JSON 時，該 JSON 仍可決定接下來發生的情況。要找出您的 hook 在 `PreToolUse` 等事件上的結果，請將第一欄中它列印到 stdout 的內容與頂端的退出碼對應：

| Stdout | 退出 0 | 退出 2 | 任何其他退出碼 |
| :- | :- | :- | :- |
| 通過 [schema 驗證](#json-output) 的 JSON 物件 | 成功。欄位生效 | 阻止性錯誤。Claude Code 仍會讀取欄位，但它們無法覆寫阻止 | 成功。Claude Code 忽略退出碼，僅由欄位決定。對於 [失敗時會阻止操作的 hook](#block-the-action-when-a-hook-fails)，該次執行改為計為失敗 |
| [無法解析](#exit-code-0) 或未通過 schema 驗證的 JSON | 非阻止性錯誤。通知帶有解析或驗證訊息 | 阻止性錯誤。您的 stderr 即為原因 | 非阻止性錯誤。通知帶有解析或驗證訊息 |
| [純文字](#exit-code-0) 或無內容 | 成功 | 阻止性錯誤。您的 stderr 即為原因 | 非阻止性錯誤。通知帶有您的 stderr 的第一行 |

某些事件有自己的規則：

* **`WorktreeCreate`**：任何非零退出碼都會使 worktree 建立失敗，無論您的 JSON 說什麼。
* **`WorktreeRemove`**：任何非零退出碼會在目錄之後仍然存在時使 worktree 移除失敗。
* **`Stop`、`SubagentStop`、`TaskCompleted` 和外掛的 `UserPromptSubmit` hook**：當您的 hook 以 2 退出、stdout 沒有任何內容，且其 stderr 表示找不到檔案（例如 `No such file or directory`）時，Claude Code 將該次執行視為非阻止性錯誤。
* **`Elicitation` 和 `ElicitationResult`**：當您的 hook 以 0 退出時，Claude Code 套用您的 `hookSpecificOutput`，在任何其他退出碼上則忽略它。
* **捨棄 hook 輸出的事件，例如 `StopFailure`**：Claude Code 在任何退出碼上都會忽略您的 JSON，但 `terminalSequence` 等副作用欄位仍會觸發。

要查看退出碼 2 在您的事件上的作用，請參閱 [每個事件的退出碼 2 行為](#exit-code-2-behavior-per-event)。要查看它接受哪些決定欄位，請參閱 [決定控制](#decision-control)。

#### 退出碼 0

退出 0 表示成功，是當您列印 JSON 進行結構化控制時的預期退出碼。當您的 hook 以 0 退出，但列印了無法解析或未通過 [schema 驗證](#json-output) 的 JSON 時，操作會繼續進行，除非該 hook 是 [失敗時會阻止操作的 hook](#block-the-action-when-a-hook-fails)。該次執行不會是套用您欄位的成功，而是 [非阻止性錯誤](#exit-code-output)。

要修正您的輸出，請使用 `<hook name> hook error` 通知所帶有的解析或驗證訊息。對於非 [async](#how-async-hooks-execute) 的 hook，只有當您列印單一 JSON 物件（位於一行或多行），且周圍只有空白時，您的 stdout 才會被視為 [JSON 輸出](#json-output)。Claude Code 會將其他任何 stdout 讀取為純文字或解析失敗：

* **不以 `{` 開頭的輸出，或以 `{` 開頭但不以 `}` 結尾的輸出**：純文字。依此規則，JSON 陣列和帶引號的 JSON 字串都是純文字。
* **兩行或更多行，每行本身都可解析為 JSON，且第一行以 `{` 開頭、最後一行以 `}` 結尾**：若沒有任何一行是設定欄位的 JSON 輸出物件，則為純文字。若有一行是，則輸出為解析失敗，因此請列印該物件，且 stdout 上不要有其他任何內容。
* **其他任何以 `{` 開頭並以 `}` 結尾但不是有效 JSON 的內容**：解析失敗。

對於大多數事件，Claude Code 將 stdout 寫入偵錯日誌，不在逐字稿中顯示。例外是 `UserPromptSubmit`、`UserPromptExpansion`、`SessionStart` 和 `PostModelSwitch`，其中 Claude Code 將純文字 stdout 新增為 Claude 可以看到並據以行動的上下文。在這些事件上，Claude Code 不會新增其無法解析的 stdout。

Claude 永遠看不到以 0 退出的 hook 的 stderr。要在 `PreToolUse` 等事件上自行讀取它，請啟用 [偵錯日誌](#debug-hooks)。要從 `PostToolUse` 或 `PostToolUseFailure` hook 向 Claude 顯示警告，請改為退出 2，以便 [Claude 看到 stderr](#exit-code-2-behavior-per-event)，儘管工具已執行。

#### 退出碼 2

以代碼 2 退出以阻止操作。在 [可以阻止的事件](#exit-code-2-behavior-per-event) 上，Claude Code 會停止該操作：例如，`PreToolUse` hook 會阻止工具呼叫，`UserPromptSubmit` hook 會拒絕提示詞。

隨阻止一起傳回的訊息是您的 hook 的 stderr。如果您的 hook 也列印了做出阻止決定的 JSON，Claude Code 會改用該決定的原因。

即使您的 hook 列印 JSON，退出 2 仍會阻止：

* **通過 schema 驗證的 JSON**：Claude Code 仍會讀取 [JSON 輸出](#json-output) 欄位，但它們無法覆寫阻止。即使 `permissionDecision` 為 `"allow"` 也無法讓操作通過。在 `Elicitation` 和 `ElicitationResult` 上，exit-2 hook 的 `hookSpecificOutput` 會被忽略。
* **未通過 schema 驗證的 JSON**：hook 仍會阻止。Claude Code 使用您的 stderr 作為阻止原因，並在偵錯日誌中記錄驗證失敗。

此指令碼透過退出 2 阻止 `rm` 命令，並將每個其他命令留給正常權限流程：

```bash theme={null}
#!/bin/bash
# 從 stdin 讀取 JSON 輸入，檢查命令
input=$(cat)
command=$(jq -r '.tool_input.command' <<<"$input")

if [[ "$command" == rm* ]]; then
  echo "Blocked: rm commands are not allowed" >&2
  exit 2  # 阻止性錯誤：工具呼叫被阻止
fi

exit 0  # 無決定：正常權限流程適用
```

將此指令碼註冊為 `Bash` 上的 `PreToolUse` hook 後，以 `rm` 開頭的命令會被阻止，Claude 會收到 hook 的 stderr 作為工具的錯誤，前綴為事件名稱、工具名稱和 hook 的命令：

```text theme={null}
PreToolUse:Bash hook error: [${CLAUDE_PROJECT_DIR}/.claude/hooks/no-rm.sh]: Blocked: rm commands are not allowed
```

#### 其他退出碼

帶有 `Failed with non-blocking status code:` 的 `<hook name> hook error` 通知表示您的 hook 的退出碼不是 0 或 2，且其 stdout 為純文字或空白。除非該 hook 是 [失敗時會阻止操作的 hook](#block-the-action-when-a-hook-fails)，否則這是 [非阻止性錯誤](#exit-code-output)，因此您的 hook 並未停止該操作。要擷取您的 hook 的完整 stderr，而不僅是通知顯示的第一行，請啟用 [偵錯日誌](#debug-hooks)。

例如，當 `Bash` 上的 `PreToolUse` hook 將 `something broke` 列印到 stderr 並以 1 退出時，`PreToolUse:Bash hook error` 通知帶有這一行：

```text theme={null}
Failed with non-blocking status code: something broke
```

如果通知帶有 shell 的 `No such file or directory` 訊息（如下列這一行），表示該 hook 從未執行，例如因為其指令碼路徑不存在：

```text theme={null}
Failed with non-blocking status code: /bin/sh: /path/to/hook.sh: No such file or directory
```

如果路徑錯誤，請在設定該 hook 的位置修正它。在 shell 形式中，當指令碼路徑不存在或不可執行時，shell 以代碼（如 127）退出，通知帶有解譯器的訊息。除非該 hook 是 [失敗時會阻止操作的 hook](#block-the-action-when-a-hook-fails)，否則無法啟動的 hook 也是非阻止性錯誤。

當您設定原則 hook 時，請在其第一次執行時留意此通知，因為 `settings.json` 中拼寫錯誤的路徑代表該 hook 永遠不會執行。要在 hook 無法啟動時阻止操作，請設定 [`onFailure: "block"`](#block-the-action-when-a-hook-fails)。

> [!WARNING]
>
> 沒有有效 JSON 輸出的退出碼 1 是非阻止性錯誤，除非該 hook 是 [失敗時會阻止操作的 hook](#block-the-action-when-a-hook-fails)，儘管 1 是傳統的 Unix 失敗代碼。如果您的 hook 旨在強制執行原則，請使用 `exit 2`。

#### 逾時

除了您使用 [`async: true`](#run-hooks-in-the-background) 執行的命令 hook，Claude Code 會取消達到其 [`timeout`](#common-fields) 的 `command`、`http` 或 `mcp_tool` hook，並捨棄 hook 的輸出，因此在大多數事件上，逾時的 hook 不會做出決定。在 [`PreModelSwitch`](#premodelswitch) 上，在其逾時時被取消的 hook 會阻止模型切換。

在 `PreToolUse` 上，逾時的 `command`、`http` 或 `mcp_tool` hook 不阻止工具呼叫，但 [失敗時會阻止操作的 hook](#block-the-action-when-a-hook-fails) 除外。呼叫透過正常 [權限流程](https://code.claude.com/docs/zh-TW/permissions.md) 繼續，因此不要指望停滯的 hook 充當閘門。要在 `command` 或 `http` hook 逾時時阻止呼叫，請設定 [`onFailure: "block"`](#block-the-action-when-a-hook-fails)。超過其逾時的 [Agent SDK 回呼 hook](https://code.claude.com/docs/zh-TW/agent-sdk/hooks.md) [會阻止工具呼叫](#pretooluse)。

#### 啟動背景程序的 hook

如果您的命令 hook 在背景程序中做出決定後就退出，該程序在 Claude Code 停止讀取之後才列印的拒絕不會阻止工具呼叫。對於非 [async](#run-hooks-in-the-background) 的 hook，Claude Code 會在 hook 本身的程序退出後不久完成讀取 hook 的輸出。

請在啟動背景程序之前列印決定，並重新導向該程序的 stdout 和 stderr。如果您的指令碼列印允許決定，然後啟動背景程序而未重新導向該程序的 stdout 和 stderr，Claude Code 會阻止工具呼叫。hook 錯誤包含 `refusing to honor the suspect capture`。

此 `PreToolUse` hook 指令碼使用 `policy-check.sh` 列印決定，然後在背景上傳指標：

```bash theme={null}
#!/bin/bash
"$CLAUDE_PROJECT_DIR"/.claude/hooks/policy-check.sh || exit $?
"$CLAUDE_PROJECT_DIR"/.claude/hooks/upload-metrics.sh >/dev/null 2>&1 &
```

指令碼的其餘部分執行以下操作：

* **`|| exit $?`**：讓檢查的退出碼成為 hook 本身的退出碼，因此以 2 退出以拒絕的檢查仍會阻止。否則 hook 會以最後一行的代碼退出，也就是 0。
* **`>/dev/null 2>&1 &`**：在背景執行 `upload-metrics.sh` 並重新導向其輸出，使其不會讓 hook 的輸出保持開啟。

要測試此指令碼，請讓 `policy-check.sh` 以 2 退出，然後觸發該 hook 所匹配的工具呼叫。工具呼叫會被阻止。

#### 在 hook 失敗時阻止操作

在大多數事件上，當 hook 失敗或逾時時，Claude Code 仍會執行該操作。如此一來，路徑錯誤或指令碼當機的原則 hook 會讓所有操作通過。若要改為阻止操作，請在 `command` 或 `http` hook 上設定 `"onFailure": "block"`。需要 Claude Code v2.1.295 或更新版本。關於 Agent SDK 回呼 hook，請參閱[在回呼失敗時阻止操作](https://code.claude.com/docs/zh-TW/agent-sdk/hooks.md#block-the-action-when-a-callback-fails)。

> [!NOTE]
>
> 在沒有 Git Bash 的 Windows 上，未設定 `onFailure` 的 shell 形式 `PreToolUse` 或 `PermissionRequest` 命令 hook 失敗時，可能改為[阻止工具呼叫](#failed-hooks-on-windows-without-git-bash)。

`.claude/settings.json` 中的這個 `PreToolUse` hook 會在每個 Bash 命令之前執行專案指令碼，並在指令碼失敗時阻止該命令：

```json theme={null}
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "node",
            "args": ["${CLAUDE_PROJECT_DIR}/.claude/hooks/check-command.js"],
            "onFailure": "block"
          }
        ]
      }
    ]
  }
}
```

要測試它，請讓 `check-command.js` 保持不存在，並要求 Claude 執行 `ls` 之類的 Bash 命令。Claude Code 會阻止該呼叫，錯誤包含 `failed; blocking because onFailure is "block"`，後接 node 本身的錯誤輸出（此處截短為一行）：

```text theme={null}
PreToolUse:Bash hook error: [node ${CLAUDE_PROJECT_DIR}/.claude/hooks/check-command.js]: failed; blocking because onFailure is "block"
Error: Cannot find module '/path/to/project/.claude/hooks/check-command.js'
```

逾時後，訊息會顯示 `timed out` 而不是 `failed`。未設定 `onFailure` 時，同樣缺少的指令碼是非阻止性錯誤，`ls` 會執行。

以下各項都計為失敗：

* **無法啟動**：命令 hook 無法啟動，例如因為指令碼或可執行檔不存在
* **0 或 2 以外的退出碼**：對命令 hook 而言，即使它列印了允許操作的 JSON（例如 `permissionDecision: "allow"`）也會計入。要傳回 JSON 決定，請以 0 退出
* **HTTP 錯誤**：HTTP hook 的連線失敗，或回應狀態不是 2xx
* **逾時**：hook 達到其 [`timeout`](#common-fields)
* **無效輸出**：JSON 輸出 [無法解析](#exit-code-0) 或未通過 [schema 驗證](#json-output)。對於 HTTP hook，既非空白也非 JSON 物件的 2xx 正文也會計入。命令 hook 的純文字 stdout 不算失敗

設定 `"block"` 後，失敗會執行 [退出碼 2 在該事件上的作用](#exit-code-2-behavior-per-event)，但 `PermissionRequest` 除外，在該事件上它會拒絕請求。例如，`PreToolUse` 失敗會阻止工具呼叫，`UserPromptSubmit` 失敗會阻止提示詞。

該欄位對以下 hook 沒有作用：

* **`Stop`、`SubagentStop`、`TaskCompleted` 和 `TeammateIdle` hook**：在這些事件上，退出碼 2 會讓 Claude 回去繼續工作，而 Claude 無法修復無法執行的 hook
* **背景命令 hook**：設定 [`async` 或 `asyncRewake`](#run-hooks-in-the-background) 的命令 hook

#### Windows 上沒有 Git Bash 時失敗的 hook

如果被阻止的工具呼叫的錯誤包含以下文字，表示某個 `PreToolUse` 或 `PermissionRequest` 命令 hook 失敗或逾時，並阻止了該呼叫：

```text theme={null}
blocking because Git Bash wasn't found, so only exit code 0 or 2 counts as this hook's verdict.
```

如果錯誤還顯示 `PowerShell started no program`，請從 [針對僅由帶引號字串組成之 `command` 的修正方式](#powershell-started-no-program) 著手，PowerShell 會將這類命令列印出來，而不是執行它。

在沒有 Git Bash 的情況下，該 hook 傳回 0 或 2 以外的任何退出碼都計為 [失敗](#block-the-action-when-a-hook-fails)，即使它列印了不拒絕呼叫的 JSON。要找出 hook 失敗的原因，請查看 [偵錯日誌](#debug-hooks)。然後選擇符合您 hook 的修正方式：

* **hook 失敗時操作應繼續進行**：在 hook 中新增 [`"onFailure": "continue"`](#block-the-action-when-a-hook-fails)
* **hook 以 1 退出來發出警告，但在當機時必須阻止**：使用 `"onFailure": "continue"` 時，呼叫會在退出碼 1 時繼續進行，無論是警告還是當機皆然。請改為新增 `"onFailure": "block"`，並在指令碼發出警告之處以退出碼 0 結束，讓這些呼叫繼續進行。若仍要在 `PreToolUse` 上顯示警告，請將其列印到 stdout，放在單一 JSON 物件的 [`systemMessage`](#json-output) 欄位中。
* **hook 是為 Bash 撰寫的**：在沒有 Git Bash 的情況下，未設定 `shell` 的 [shell 形式](#exec-form-and-shell-form) hook 會在 PowerShell 中執行，並可能在那裡失敗。安裝 [Git for Windows](https://git-scm.com/downloads/win)，或者如果 Git Bash 安裝在 Claude Code 找不到的位置，請設定 [`CLAUDE_CODE_GIT_BASH_PATH`](https://code.claude.com/docs/zh-TW/env-vars)。然後啟動新的工作階段。
* **hook 執行單一 `.exe`，而非 `.cmd` 或 `.bat` 檔案**：將程式放在 `command` 中、將其引數放在 `args` 中以使用 exec 形式，並新增 `"onFailure": "block"`。Claude Code 接著會在沒有 shell 的情況下啟動該程式。若沒有 `"onFailure": "block"`，當程式失敗、不存在或逾時時，呼叫可能會繼續進行
* **必須在失敗時阻止的 PowerShell 防護 hook**：在未設定 `onFailure` 的情況下，一旦安裝了 Git for Windows 且 Claude Code 找到 Git Bash，它就不會再阻止。新增 `"onFailure": "block"`，讓失敗或逾時在有無 Git Bash 的情況下都會阻止呼叫。同時設定 `"shell": "powershell"`，讓 hook 從此之後繼續在 PowerShell 中執行，而不是在 Git Bash 中執行

在 v2.1.309 之前，訊息為 `blocking because Git Bash wasn't found and this hook doesn't set "shell" to "powershell", so only exit code 0 or 2 counts as its verdict.`

#### PowerShell started no program

出現此錯誤的 hook 是在 PowerShell 中執行的，而對於僅由帶引號字串組成的 `command`（例如 `"command": "\"C:\\Tools\\guard.exe\""`），PowerShell 會將其列印出來，而不是執行它。

* **要列印文字（例如 JSON）**：設定 `"shell": "powershell"`，hook 便會以 0 退出
* **要執行 `.ps1`、`.cmd` 或 `.bat` 檔案，或路徑含有變數的 `.exe`**：設定 `"shell": "powershell"`，並在帶引號的路徑前加上 `&`。保留 `$HOME` 原樣，並依照 [`check.ps1` 範例](#reference-scripts-by-path-in-powershell-hooks) 拼寫 `$env:CLAUDE_PROJECT_DIR` 的方式來拼寫環境變數
* **要執行路徑中不含 `$` 的單一 `.exe`**：從 `command` 中移除內層引號，然後套用 [執行單一 `.exe` 之 hook 的修正方式](#failed-hooks-on-windows-without-git-bash)，若程式不接受引數，請寫入 `"args": []`
* **要執行為 Bash 撰寫的指令碼**：套用 [為 Bash 撰寫之 hook 的修正方式](#failed-hooks-on-windows-without-git-bash)

#### 每個事件的退出碼 2 行為

退出碼 2 是 hook 發出「停止，不要這樣做」的方式。效果取決於事件，因為某些事件代表可以被阻止的操作（例如尚未發生的工具呼叫），而其他事件代表已經發生或無法防止的事情。

| Hook 事件 | 可以阻止？ | 退出 2 時發生的情況 |
| :- | :- | :- |
| `PreToolUse` | 是 | 阻止工具呼叫 |
| `PermissionRequest` | 否 | 此事件不接受退出碼 2，權限流程保持不變。改為透過 [`decision` 物件](#permissionrequest-decision-control) 拒絕 |
| `UserPromptSubmit` | 是 | 阻止提示詞，所以它永遠不會到達 Claude。請參閱 [被阻止的提示詞留下什麼](#what-a-blocked-prompt-leaves-behind) |
| `UserPromptExpansion` | 是 | 阻止擴展 |
| `Stop` | 是 | 防止 Claude 停止，繼續對話 |
| `SubagentStop` | 是 | 防止 subagent 停止 |
| `TeammateIdle` | 是 | 防止隊友閒置，所以它繼續工作 |
| `TaskCreated` | 是 | 回滾任務建立 |
| `TaskCompleted` | 是 | 防止任務被標記為已完成 |
| `ConfigChange` | 是 | 阻止設定變更生效（除了 `policy_settings`） |
| `StopFailure` | 否 | 輸出和退出碼被忽略，除了 `terminalSequence` |
| `PostToolUse` | 否 | 向 Claude 顯示 stderr；工具已執行 |
| `PostToolUseFailure` | 否 | 向 Claude 顯示 stderr；工具已失敗 |
| `PostToolBatch` | 是 | 在下一個模型呼叫之前停止代理式迴圈 |
| `PermissionDenied` | 否 | 退出碼和 stderr 被忽略，因為拒絕已發生。使用 JSON `hookSpecificOutput.retry: true` 告訴模型它可以重試；Claude Code 對於 [no-verdict denials](#permissiondenied-decision-control) 會忽略 `retry: true` |
| `Notification` | 否 | 退出碼和 stderr 被忽略 |
| `SubagentStart` | 否 | 僅向使用者顯示 stderr |
| `SessionStart` | 否 | 僅向使用者顯示 stderr |
| `Setup` | 否 | 退出碼和 stderr 被忽略 |
| `SessionEnd` | 否 | 僅向使用者顯示 stderr |
| `CwdChanged` | 否 | 僅向使用者顯示 stderr |
| `DirectoryAdded` | 否 | Stderr 進入偵錯日誌；目錄已新增 |
| `FileChanged` | 否 | 僅向使用者顯示 stderr |
| `PreCompact` | 是 | 阻止壓縮 |
| `PostCompact` | 否 | 僅向使用者顯示 stderr |
| `PreModelSwitch` | 是 | 阻止模型切換並向使用者顯示 stderr |
| `PostModelSwitch` | 否 | 僅向使用者顯示 stderr；模型已切換 |
| `Elicitation` | 是 | 拒絕請求，且不會出現對話框 |
| `ElicitationResult` | 是 | 阻止回應（操作變為拒絕） |
| `WorktreeCreate` | 是 | 任何非零退出碼都會導致 worktree 建立失敗 |
| `WorktreeRemove` | 是 | 任何非零退出碼會在目錄之後仍然存在時使 worktree 移除失敗。請參閱 [WorktreeRemove](#worktreeremove) 以了解目錄發生的情況 |
| `InstructionsLoaded` | 否 | 退出碼被忽略 |
| `MessageDisplay` | 否 | 原始文字被顯示 |

對於 `SessionStart`、`SubagentStart` 和 `PostModelSwitch`，Claude Code 在逐字稿中將退出碼 2 的 stderr 呈現為 `<hook name> hook error` 通知，與 [非阻止性錯誤](#exit-code-output) 相同的方式。Claude 看不到它，工作階段或 subagent 繼續進行。對於 `SubagentStart`，通知出現在 subagent 自己的逐字稿中，而不是在父對話中。

### HTTP 回應處理

HTTP hook 使用 HTTP 狀態碼和回應正文，而不是退出碼和 stdout。要在請求失敗或返回非 2xx 狀態時阻止操作，請設定 [`onFailure: "block"`](#block-the-action-when-a-hook-fails)。要阻止工具呼叫或拒絕權限，請返回 2xx 回應，其 JSON 正文包含適當的 [決定欄位](#decision-control)。

發生 [非阻止性錯誤](#exit-code-output) 後，操作會繼續進行，除非該 hook 是 [失敗時會阻止操作的 hook](#block-the-action-when-a-hook-fails)。除了在 [每個事件表](#exit-code-2-behavior-per-event) 中有自己的失敗約定的事件（如 `WorktreeCreate`）之外，每種回應或失敗會得到以下結果：

* **2xx 且正文為空**：成功，等同於退出碼 0 且無輸出
* **2xx 且 JSON 物件正文**：使用與命令 hook 相同的 [JSON 輸出](#json-output) schema 進行解析。未通過 schema 驗證的正文是非阻止性錯誤
* **2xx 且任何其他正文，如純文字**：非阻止性錯誤，處理方式與非 2xx 狀態相同。Claude Code 不將文字新增到 Claude 的上下文
* **非 2xx 狀態**：非阻止性錯誤
* **連線失敗**：非阻止性錯誤
* **逾時**：hook 被取消，如 [逾時](#timeouts) 下所述

### JSON 輸出

退出碼只讓您阻止或保持沉默，但 JSON 輸出提供更細緻的控制。與其以代碼 2 退出來阻止，不如退出 0 並將 JSON 物件列印到 stdout。Claude Code 從該 JSON 讀取特定欄位以控制行為，包括用於阻止、允許或升級給使用者的 [決定控制](#decision-control)。

> [!NOTE]
>
> 為每個 hook 選擇一種方法：要麼單獨使用退出碼進行信號傳遞，要麼退出 0 並列印 JSON 進行結構化控制。如果您混合它們，退出 2 保持其 [阻止效果](#exit-code-2-behavior-per-event)，Claude Code 仍然讀取 JSON 欄位，但 [Exit code 2](#exit-code-2) 下記錄的一個 elicitation 例外除外。

僅將 JSON 物件列印到 stdout。對於非 [async](#how-async-hooks-execute) 的 hook，stdout 中的其他文字（例如您的 shell 設定檔在啟動時 echo 的一行）會使 Claude Code 無法將該物件讀取為 JSON，[Hook JSON 無效](https://code.claude.com/docs/zh-TW/hooks-guide.md#hook-json-has-no-effect) 說明如何找出並消除該文字。

Hook 的 `additionalContext`、`systemMessage` 和 `initialUserMessage` 字串，以及其純 stdout，上限為 10,000 個字元：

* **範圍**：Claude Code 分別測量每個字串，即使多個 hook 為同一事件執行。對於 JSON 輸出，每個欄位分別測量；純 stdout 整體測量。
* **超過限制**：Claude Code 將輸出儲存到工作階段目錄中的檔案，並將其替換為檔案路徑和最多前 2,000 個字元的預覽。大型有效 Bash 結果的處理方式相同，如 [輸出限制](https://code.claude.com/docs/zh-TW/tools-reference.md#output-limits) 下所述。與該 Bash 上限不同，此上限沒有可提高它的設定或環境變數。
* **讀取檔案**：Claude Code 不要求 Claude 讀取檔案，因此將 Claude 必須始終看到的任何內容保持在上限內。

JSON 物件支援三種欄位：

* **通用欄位**，如 `continue`，列在下表中。每個事件都接受它們，但某些事件捨棄它們或將 `systemMessage` 傳遞到逐字稿以外的地方。每個事件的部分都會說明。`terminalSequence` 在這些事件上也有效，但 [發出終端機通知](#emit-terminal-notifications) 下列出的例外除外。
* **頂層 `decision` 和 `reason`** 由某些事件用來阻止或提供回饋。
* **`hookSpecificOutput`** 是一個巢狀物件，用於需要更豐富控制的事件。它需要一個設定為事件名稱的 `hookEventName` 欄位。

| 欄位 | 預設 | 描述 |
| :- | :- | :- |
| `continue` | `true` | 如果為 `false`，Claude 在 hook 執行後完全停止處理。優先於任何事件特定的決定欄位 |
| `stopReason` | 無 | 當 `continue` 為 `false` 時向使用者顯示的訊息。它停留在對話中，因此如果對話繼續，Claude 會看到它 |
| `suppressOutput` | `false` | 無效果：Claude Code 接受該欄位但不據以行動。成功的 hook 的 stdout 永遠不在逐字稿中顯示，並記錄在偵錯日誌中 |
| `systemMessage` | 無 | 向使用者顯示的警告訊息。在 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 和 [`--output-format stream-json`](https://code.claude.com/docs/zh-TW/headless) 輸出中，它可以作為 [`SDKInformationalMessage`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#sdkinformationalmessage) 到達 |
| `terminalSequence` | 無 | Claude Code 代表您發出的終端機逃逸序列，例如桌面通知、視窗標題或響鈴。限制為 OSC `0`/`1`/`2`/`9`/`99`/`777` 和 BEL。如果值包含允許清單外的任何內容，該欄位將被忽略。使用此項而不是寫入 `/dev/tty`，後者對 hook 不可用 |

要完全停止 Claude：

```json theme={null}
{ "continue": false, "stopReason": "Build failed, fix errors before continuing" }
```

對於 `PreToolUse` 和 `PostToolUse` hook，即使工具呼叫在 Claude 仍在串流回應時失敗或完成，停止仍然適用。

#### 發出終端機通知

Hook 在沒有控制終端機的情況下執行，因此直接將逃逸序列寫入 `/dev/tty` 會失敗。相反，在 `terminalSequence` 欄位中返回逃逸序列，Claude Code 會透過其自己的終端機寫入路徑為您發出它。這不會產生競爭狀況，在 tmux 和 GNU screen 內有效，並在沒有 `/dev/tty` 的 Windows 上有效。

該欄位接受由一個或多個允許清單中逃逸序列組成的字串：

* OSC `0`、`1`、`2`：視窗和圖示標題
* OSC `9`：iTerm2、ConEmu、Windows Terminal 和 WezTerm 通知，包括 `9;4` 工作列進度
* OSC `99`：Kitty 通知
* OSC `777`：urxvt、Ghostty 和 Warp 通知
* 單獨的 BEL

序列可以用 BEL 或 ST 終止。允許清單外的任何內容，包括 CSI 游標和顏色序列、OSC 調色盤序列、OSC 8 超連結、OSC 52 剪貼簿寫入和 OSC 1337，都會被拒絕，該欄位將被忽略。

Claude Code 在處理您的 hook 輸出時自行寫入序列，因此該欄位在捨棄 `systemMessage` 和 `continue` 的事件上也有效，例如 `Notification` 和 `StopFailure`。它有兩個限制：

* Claude Code 僅在互動式工作階段中寫入序列，且僅在其介面顯示於螢幕上時。在使用 `-p` 旗標的非互動模式和 Agent SDK 中，它忽略該欄位。
* `WorktreeCreate` 命令 hook 無法返回 JSON，因為 Claude Code 將其 stdout 讀取為 worktree 路徑。HTTP `WorktreeCreate` hook 返回 JSON 並可以包含該欄位。

下面的範例從 `Notification` hook 觸發桌面通知。逃逸序列使用 `printf` 八進位逃逸建立，因此控制位元組永遠不會出現在 shell 命令列上，並以 `jq -n --arg` 建立 JSON 輸出，因此通知訊息中的引號、反斜線和換行符號會被正確逃逸：

```bash theme={null}
#!/bin/bash
# Notification hook：當 Claude Code 需要注意時 ping 桌面。
input=$(cat)
title="Claude Code"
body=$(jq -r '.message // "Needs your attention"' <<<"$input")
seq=$(printf '\033]777;notify;%s;%s\007' "$title" "$body")
jq -nc --arg seq "$seq" '{terminalSequence: $seq}'
```

`{ "terminalSequence": "..." }` 形式在任何 shell 或語言中都相同。

#### 為 Claude 新增上下文

`additionalContext` 欄位將字串從您的 hook 傳遞到 Claude 的上下文視窗。Claude Code 將字串包裝在 [系統提醒](https://code.claude.com/docs/zh-TW/glossary.md#system-reminder) 中，並將其插入到 hook 觸發時的對話位置。Claude 在下一個模型請求時讀取提醒，但它不會在介面中顯示為聊天訊息。

在 `hookSpecificOutput` 中將 `additionalContext` 與事件名稱一起返回：

```json theme={null}
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "This file is generated. Edit src/schema.ts and run `bun generate` instead."
  }
}
```

提醒出現的位置取決於事件：

* [SessionStart](#sessionstart) 和 [SubagentStart](#subagentstart)：在對話開始時，在第一個提示詞之前
* [UserPromptSubmit](#userpromptsubmit) 和 [UserPromptExpansion](#userpromptexpansion)：與提交的提示詞一起
* [PreToolUse](#pretooluse)、[PostToolUse](#posttooluse)、[PostToolUseFailure](#posttoolusefailure) 和 [PostToolBatch](#posttoolbatch)：在工具結果旁邊
* [Stop](#stop) 和 [SubagentStop](#subagentstop)：在回合結束時。對話繼續，以便 Claude 可以對回饋採取行動。請參閱 [Stop 決定控制](#stop-decision-control)
* [PostModelSwitch](#postmodelswitch)：與切換後的下一個請求一起。請參閱 [PostModelSwitch 決定控制](#postmodelswitch-decision-control) 以了解時機

當多個 hook 為同一事件返回 `additionalContext` 時，Claude 接收所有值。

如果您的字串包含 `<system-reminder>` 或 `</system-reminder>` 標籤，Claude 收到的字串中該標籤的 `<` 會被替換為 `&lt;`。

如果值超過 10,000 個字元，Claude Code 會將文字寫入工作階段目錄中的檔案，並改為將檔案路徑與最多前 2,000 個字元的預覽傳遞給 Claude。Claude 可以讀取檔案，但 Claude Code 不要求它這樣做。

使用 `additionalContext` 來提供 Claude 應該知道的有關您環境目前狀態或剛剛執行的操作的資訊：

* **環境狀態**：目前分支、部署目標或啟用中的功能旗標
* **條件式專案規則**：哪個測試命令適用於剛編輯的檔案，此 worktree 中哪些目錄是唯讀的
* **外部資料**：指派給您的未解決問題、最近的 CI 結果、從內部服務擷取的內容

對於永遠不會改變的指示，優先使用 [CLAUDE.md](https://code.claude.com/docs/zh-TW/memory.md)。它無需執行指令碼即可載入，是靜態專案慣例的標準位置。

將文字寫成事實陳述，而不是命令式系統指示。「部署目標是 production」或「此儲存庫使用 `bun test`」之類的措辭讀起來像專案資訊。以帶外系統命令形式呈現的文字可能會觸發 Claude 的提示詞注入防禦，這會導致 Claude 將文字呈現給您，而不是將其視為上下文。

Claude Code 在工作階段逐字稿中儲存注入的文字。對於 `PostToolUse` 或 `UserPromptSubmit` 等工作階段中途的事件，當您使用 `--continue` 或 `--resume` 繼續時，Claude Code 會重播儲存的文字，而不是為過去的回合重新執行 hook，因此時間戳記或提交 SHA 等值會變得過時。`SessionStart` hook 會在繼續時再次執行，其 `source` 設定為 `"resume"`，或在您新增了 `--fork-session` 時設定為 `"fork"`，因此它們可以重新整理其上下文。

#### 決定控制

並非每個事件都支援透過 JSON 阻止或控制行為。支援的事件各自使用不同的欄位集來表達該決定。在編寫 hook 之前，使用此表作為快速參考：

| 事件 | 決定模式 | 關鍵欄位 |
| :- | :- | :- |
| UserPromptSubmit、UserPromptExpansion、PostToolUse、PostToolUseFailure、PostToolBatch、Stop、SubagentStop、ConfigChange、PreCompact | 頂層 `decision` | `decision: "block"`、`reason`。Stop 和 SubagentStop 也接受 `hookSpecificOutput.additionalContext` 用於 [繼續對話的非錯誤回饋](#stop-decision-control) |
| TeammateIdle、TaskCompleted | 退出碼或 `continue: false` | 退出碼 2 以 stderr 回饋阻止操作。JSON `{"continue": false, "stopReason": "..."}` 也會完全停止隊友，與 `Stop` hook 行為一致；[TaskCompleted 在 `TaskUpdate` 工具觸發事件時忽略它](#taskcompleted-decision-control) |
| TaskCreated | 退出碼或頂層 `decision` | 退出碼 2 或 `decision: "block"` [取消任務](#taskcreated-decision-control) 並將訊息返回給 Claude。`continue: false` 被忽略 |
| PreToolUse | `hookSpecificOutput` | `permissionDecision`（allow/deny/ask/defer）、`permissionDecisionReason` |
| PreModelSwitch | `hookSpecificOutput` 或頂層 `decision` | `permissionDecision`（allow/deny/ask）、`permissionDecisionReason`。`decision: "block"` 也會 [取消切換](#premodelswitch-decision-control) |
| PermissionRequest | `hookSpecificOutput` | `decision.behavior`（allow/deny） |
| PermissionDenied | `hookSpecificOutput` | `retry: true` 告訴模型它可以重試被拒絕的工具呼叫；Claude Code 對於 [no-verdict denials](#permissiondenied-decision-control) 會忽略它 |
| WorktreeCreate | 路徑返回 | 命令 hook 在 stdout 上列印路徑；HTTP hook 返回 `hookSpecificOutput.worktreePath`。Hook 失敗或缺少路徑會導致建立失敗 |
| WorktreeRemove | 退出碼 | 任何非零退出碼會在目錄之後仍然存在時使移除失敗。JSON 輸出被捨棄 |
| Elicitation、ElicitationResult | `hookSpecificOutput` 或頂層 `decision` | `action`（accept/decline/cancel）、`content`（表單欄位值）。`decision: "block"` 也會 [拒絕](#other-ways-to-decline-an-elicitation) |
| MessageDisplay | `hookSpecificOutput` | `displayContent` 替換螢幕上顯示的文字。僅影響顯示：逐字稿和 Claude 看到的內容保持原樣 |
| SessionStart、SubagentStart、PostModelSwitch | 僅上下文 | `hookSpecificOutput.additionalContext` 為 Claude 新增上下文。SessionStart 也接受 [`initialUserMessage`、`watchPaths`、`sessionTitle` 和 `reloadSkills`](#sessionstart-decision-control)。無阻止或決定控制 |
| Setup、Notification、SessionEnd、PostCompact、InstructionsLoaded、StopFailure、CwdChanged、DirectoryAdded、FileChanged | 無 | 無決定控制。用於副作用，如日誌記錄或清理 |

一些事件也可以重寫內容，而不僅僅是允許或阻止它：

* `PreToolUse`：直接位於 `hookSpecificOutput` 下的 `updatedInput` 會在工具執行前替換其引數。請參閱 [PreToolUse 決定控制](#pretooluse-decision-control)
* `PermissionRequest`：`decision` 物件內的 `updatedInput`。請參閱 [PermissionRequest 決定控制](#permissionrequest-decision-control)
* `PostToolUse`：`updatedToolOutput` 替換工具的結果。請參閱 [PostToolUse 決定控制](#posttooluse-decision-control)
* `UserPromptSubmit`：無法替換提示詞；僅在其旁邊注入 `additionalContext`

對於遮蔽或轉換使用案例，在 `PreToolUse` 攔截外送的工具輸入，在 `PostToolUse` 攔截傳入的工具結果。

以下是每種模式的實際範例：

> [tab] 頂層決定
>
> `decision` 的唯一值是 `"block"`。要允許操作進行，請從 JSON 中省略 `decision`，或以 0 退出而不帶任何 JSON：
>
> ```json theme={null}
> {
>   "decision": "block",
>   "reason": "Test suite must pass before proceeding"
> }
> ```

> [tab] PreToolUse
>
> 使用 `hookSpecificOutput` 進行更豐富的控制：允許、拒絕或升級給使用者。您還可以在執行前修改工具輸入或為 Claude 注入額外上下文。有關完整的選項集，請參閱 [PreToolUse 決定控制](#pretooluse-decision-control)。
>
> ```json theme={null}
> {
>   "hookSpecificOutput": {
>     "hookEventName": "PreToolUse",
>     "permissionDecision": "deny",
>     "permissionDecisionReason": "Database writes are not allowed"
>   }
> }
> ```

> [tab] PermissionRequest
>
> 使用 `hookSpecificOutput` 代表使用者允許或拒絕權限請求。允許時，您還可以修改工具的輸入或套用權限規則，以便使用者不會再次收到權限提示。有關完整的選項集，請參閱 [PermissionRequest 決定控制](#permissionrequest-decision-control)。
>
> ```json theme={null}
> {
>   "hookSpecificOutput": {
>     "hookEventName": "PermissionRequest",
>     "decision": {
>       "behavior": "allow",
>       "updatedInput": {
>         "command": "npm run lint"
>       }
>     }
>   }
> }
> ```

有關延伸範例，包括 Bash 命令驗證、提示詞篩選和自動核准指令碼，請參閱指南中的 [您可以自動化的內容](https://code.claude.com/docs/zh-TW/hooks-guide.md#what-you-can-automate) 和 [Bash 命令驗證器參考實作](https://github.com/anthropics/claude-code/blob/main/examples/hooks/bash_command_validator_example.py)。

## Hook 事件

每個事件都對應 Claude Code 生命週期中可執行 hook 的一個時間點。以下各節依照生命週期的順序排列：從工作階段設定、經過代理式迴圈，到工作階段結束。每一節說明事件何時觸發、支援哪些 matcher、接收的 JSON 輸入，以及如何透過輸出控制行為。

### SessionStart

在 Claude Code 開始新工作階段或恢復現有工作階段時執行。適合用來載入開發情境，例如現有的 issue 或程式碼庫的近期變更，或是設定環境變數。若是不需要指令碼的靜態情境，請改用 [CLAUDE.md](https://code.claude.com/docs/zh-TW/memory.md)。

SessionStart 會在每個工作階段執行，因此請讓這些 hook 保持快速。僅支援 `type: "command"` 和 `type: "mcp_tool"` hook。關於 `mcp_tool` hook 何時執行，請參閱 [MCP tool hook 欄位](#mcp-tool-hook-fields)。

matcher 值對應工作階段的啟動方式：

| Matcher | 觸發時機 |
| :- | :- |
| `startup` | 新工作階段 |
| `resume` | `--resume`、`--continue` 或 `/resume` |
| `clear` | `/clear` |
| `compact` | 自動或手動壓縮 |
| `fork` | 從現有工作階段分岔出的新工作階段：搭配 `--resume` 或 `--continue` 的 `--fork-session`、`/fork` 背景副本、`/branch`，或您[移至背景](https://code.claude.com/docs/zh-TW/agent-view.md#from-inside-a-session)的對話 |

當您啟動互動式工作階段、在啟動時以 `--continue` 或 `--resume` 恢復對話，或執行 `/clear` 時，SessionStart hook 會在背景執行。您可以立即開始輸入，恢復的對話也會直接顯示，無需等待 hook。Claude 的第一個回應仍會等待 hook 完成，以便其情境能傳達給 Claude。

當您在工作階段內以 `/resume` 切換對話時，切換會改為等待 hook 完成。若您在背景 hook 仍在執行時執行 `/clear` 或切換到另一個對話，它們回傳的任何內容都不會套用到工作階段。

啟動時也有相同的等待，包括恢復的工作階段：在 SessionStart hook 仍在執行時送出的提示詞，要等到 hook 完成後才會傳達給 Claude。

在任一種等待期間，按下 `Esc` 可將提示詞取回輸入框而不送出。hook 會繼續執行。

#### SessionStart 輸入

除了[通用輸入欄位](#common-input-fields)之外，SessionStart hook 還會接收 `source`，以及選擇性的 `model`、`agent_type` 和 `session_title`：

| 欄位 | 說明 |
| :- | :- |
| `source` | 工作階段的啟動方式：新工作階段為 `"startup"`、恢復的工作階段為 `"resume"`、`/clear` 之後為 `"clear"`、壓縮之後為 `"compact"`，從現有工作階段分岔出的新工作階段則為 `"fork"` |
| `model` | 目前使用的模型識別碼。此欄位可能被省略，例如在 `/clear` 之後，或工作階段透過對話復原還原時，因此讀取前請先檢查欄位是否存在 |
| `agent_type` | agent 名稱，當您以 `claude --agent <name>` 啟動 Claude Code 時才會出現 |
| `session_title` | 工作階段的自訂標題，在已設定時出現，例如透過 `--name`、`/rename`、hook 的 `sessionTitle` 輸出，或 Agent SDK 的 `renameSession()`。輸出 `sessionTitle` 的 hook 可以先檢查此欄位，以避免覆寫既有的自訂標題 |

您尚未命名的工作階段仍可能有[自動產生的標題](https://code.claude.com/docs/zh-TW/sessions.md#name-your-sessions)。該標題不是自訂標題，也不會出現在 `session_title` 中。

當 `source` 為 `"resume"` 或 `"fork"`，且逐字稿中至少包含一則 Claude 的回應時，SessionStart hook 還會接收下列四個欄位。您的 hook 可以用它們在第一個請求之前回報恢復一段閒置已久的對話所需的成本，例如透過 [`systemMessage`](#json-output)。這些欄位需要 Claude Code v2.1.251 或更新版本。

| 欄位 | 說明 |
| :- | :- |
| `seconds_since_last_response` | 自恢復的逐字稿中最後一則回應以來經過的實際秒數 |
| `context_tokens` | 恢復的工作階段的第一個請求作為提示詞重新傳送的 token 數 |
| `prompt_cache_likely_expired` | 當最後一則回應早於工作階段的[提示快取存留期](https://code.claude.com/docs/zh-TW/prompt-caching.md#cache-lifetime)，或之後的壓縮取代了已快取的對話時為 `true` |
| `estimated_cache_write_usd` | 以工作階段的模型將 `context_tokens` 寫入提示快取的估計成本（美元），不含回應 |

此範例顯示一個在最後一則回應 90 分鐘後恢復的工作階段的輸入：

```json theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "hook_event_name": "SessionStart",
  "source": "resume",
  "model": "claude-opus-5",
  "seconds_since_last_response": 5400,
  "context_tokens": 182340,
  "prompt_cache_likely_expired": true,
  "estimated_cache_write_usd": 1.1396
}
```

#### SessionStart 決策控制

SessionStart hook 可以為 Claude 新增情境、提供第一則使用者訊息、設定工作階段標題、監看檔案，以及重新載入 skill。除了所有 hook 都可使用的 [JSON 輸出欄位](#json-output)之外，請為每一項回傳對應的欄位：

| 欄位 | 說明 |
| :- | :- |
| `additionalContext` | 在對話開始時、第一個提示詞之前加入 Claude 情境的字串。關於文字如何傳遞以及應放入什麼內容，請參閱[為 Claude 新增情境](#add-context-for-claude) |
| `initialUserMessage` | 在使用 `-p` 旗標的[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)中，作為工作階段第一則使用者訊息的字串。即使您未傳入提示詞，它也會成為第一個回合。您傳入的提示詞會作為下一個回合 |
| `sessionTitle` | 設定工作階段標題，效果與 `/rename` 相同。在 `source` 為 `"startup"`、`"resume"` 或 `"fork"` 時套用 |
| `watchPaths` | 在此工作階段期間要監看 [FileChanged](#filechanged) 事件的絕對路徑陣列 |
| `reloadSkills` | 布林值。為 `true` 時，Claude Code 會在 SessionStart hook 完成後重新掃描 [skill](https://code.claude.com/docs/zh-TW/skills.md) 和命令目錄。請參閱[重新載入 hook 安裝的 skill](#reload-skills-that-a-hook-installs) |

此輸出會新增情境並為工作階段命名：

```json theme={null}
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "Current branch: feat/auth-refactor\nUncommitted changes: src/auth.ts, src/login.tsx\nActive issue: #4211 Migrate to OAuth2",
    "sessionTitle": "auth-refactor"
  }
}
```

只新增情境的 hook 可以直接印出內容而不必建構 JSON，因為 Claude Code 會將 SessionStart hook 的[純文字 stdout](#exit-code-0) 加入 Claude 的情境。

若您外掛的 SessionStart hook 提供 `initialUserMessage` 或 `sessionTitle`，請在工作階段開始前安裝該外掛。對於在 SessionStart hook 執行完畢後才完成安裝的外掛，Claude Code 會忽略這兩個欄位。

#### 重新載入 hook 安裝的 skill

若要讓 SessionStart hook 安裝的 skill 在同一個工作階段中可用，請回傳 `reloadSkills`。skill 探索通常在 SessionStart hook 完成之前就會執行，因此若沒有此欄位，hook 寫入 `~/.claude/skills/` 或 `.claude/skills/` 的檔案可能在第一個提示詞執行時尚未被載入。

此範例會同步共用的 skill 儲存庫並要求重新掃描：

```bash theme={null}
#!/bin/bash

git -C ~/.claude/skills/team-skills pull --quiet 2>/dev/null || \
  git clone --quiet https://git.example.com/your-org/team-skills.git ~/.claude/skills/team-skills

echo '{"hookSpecificOutput": {"hookEventName": "SessionStart", "reloadSkills": true}}'
```

儲存庫 URL 僅為預留位置。請將其替換為您自己的 skill 儲存庫。

#### 保存環境變數

SessionStart hook 可以存取 `CLAUDE_ENV_FILE` 環境變數，它提供一個檔案路徑，讓您可以為 Claude 在工作階段稍後執行的 shell 命令保存環境變數。

若要設定個別的環境變數，請將 `export` 陳述式寫入 `CLAUDE_ENV_FILE`。請使用附加（`>>`）以保留其他 hook 設定的變數：

```bash theme={null}
#!/bin/bash

if [ -n "$CLAUDE_ENV_FILE" ]; then
  echo 'export NODE_ENV=production' >> "$CLAUDE_ENV_FILE"
  echo 'export DEBUG_LOG=true' >> "$CLAUDE_ENV_FILE"
  echo 'export PATH="$PATH:./node_modules/.bin"' >> "$CLAUDE_ENV_FILE"
fi

exit 0
```

若要擷取設定命令所造成的所有環境變更，請比較前後匯出的變數：

```bash theme={null}
#!/bin/bash

ENV_BEFORE=$(export -p | sort)

# Run your setup commands that modify the environment
source ~/.nvm/nvm.sh
nvm use 20

if [ -n "$CLAUDE_ENV_FILE" ]; then
  ENV_AFTER=$(export -p | sort)
  comm -13 <(echo "$ENV_BEFORE") <(echo "$ENV_AFTER") >> "$CLAUDE_ENV_FILE"
fi

exit 0
```

每個 Bash 命令都會在命令本身之前將該檔案的內容作為 shell 程式碼執行，因此其中的一行可以使用 Bash 能求值的任何內容，例如 `export PATH="$PATH:./node_modules/.bin"` 中的 `$PATH` 參照。

##### PowerShell 命令中保存的變數

在 Claude Code v2.1.296 或更新版本中，[PowerShell](https://code.claude.com/docs/zh-TW/tools-reference.md#powershell-tool) 命令也會接收 `CLAUDE_ENV_FILE` 中的變數，但 PowerShell 從不執行該檔案。Claude Code 會從中讀出賦值，並改為複製到 PowerShell 命令的環境中。只有當本工作階段中每個 hook 所寫入的內容，以及您在啟動前[將 `CLAUDE_ENV_FILE` 設為](https://code.claude.com/docs/zh-TW/env-vars)的任何指令碼中，每一行都屬於下列其中一種時，才會這麼做：

* 空白行或 `#` 註解
* 位於行首的單一賦值，寫法為 `export NAME=value`、`declare -x NAME=value` 或 `NAME=value`，且其值是 Bash 會按原樣使用的值，可由下列部分任意組合而成：僅使用字母、數字及字元 `_ @ % + = : , . / -` 的未加引號文字、單引號內的文字，以及其中任何 `$`、反引號或 `"` 都已用反斜線跳脫的雙引號內文字

若有任何一行屬於其他類型，例如帶有未跳脫 `$PATH` 的 `export PATH="$PATH:./node_modules/.bin"`、`source` 命令，或 `direnv export bash` 輸出的 `$'...'` 字串，PowerShell 命令將不會接收任何變數，且 `claude --debug` 會記錄 `Session environment is not all plain assignments`。Bash 命令仍會接收所有變數。在 Windows 上，PowerShell 命令也不會接收值中包含 `/` 或 `\` 的變數，因為 Git Bash 和 Windows 的路徑寫法不同。[沙箱化](https://code.claude.com/docs/zh-TW/sandboxing.md)的 PowerShell 命令不會接收任何變數。

> [!NOTE]
>
> `CLAUDE_ENV_FILE` 可供 SessionStart、[Setup](#setup)、[CwdChanged](#cwdchanged) 和 [FileChanged](#filechanged) hook 使用。其他 hook 事件無法存取此變數，在 PowerShell 中執行的 hook 也無法存取，無論是透過 [`"shell": "powershell"`](#command-hook-fields)，還是在沒有 Git Bash 的 Windows 上預設執行。

### Setup

僅在您以 `--init-only` 啟動 Claude Code，或在使用 `-p` 旗標的[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)中搭配 `--init` 或 `--maintenance` 啟動時觸發。一般啟動時不會觸發。適合用於您從 CI 或指令碼明確觸發的一次性相依套件安裝或排程清理，與一般的工作階段啟動分開。若要進行每個工作階段的初始化，請改用 [SessionStart](#sessionstart)。

matcher 值對應觸發 hook 的 CLI 旗標：

| Matcher | 觸發時機 |
| :- | :- |
| `init` | `claude --init-only` 或 `claude -p --init` |
| `maintenance` | `claude -p --maintenance` |

當您執行 `claude --init-only` 時，Claude Code 會執行 Setup hook 以及帶有 `startup` matcher 的 `SessionStart` hook，然後在不開始對話的情況下結束。

當您以 `-p` 開始或繼續對話時，也需要提供提示詞，可作為引數或透過 stdin 管道傳入。當 `SessionStart` hook 提供 [`initialUserMessage`](#sessionstart-decision-control)，或您恢復含有[延遲工具呼叫](#defer-a-tool-call-for-later)的工作階段時，可以省略提示詞。

成功時，`--init-only` 不會在終端機印出任何內容。若要確認 hook 已執行，請以 `claude --debug-file <path> --init-only` 啟動，將 `<path>` 替換為日誌檔案位置，然後檢查日誌中的 Setup 和 SessionStart hook 項目。

由於 Setup 不會在每次啟動時觸發，需要安裝相依套件的外掛不能只依賴 Setup。實務上的做法是在首次使用時檢查相依套件，缺少時再安裝，例如使用一個 hook 或 skill 檢查 `${CLAUDE_PLUGIN_DATA}/node_modules`，若不存在則執行 `npm install`。關於已安裝相依套件的存放位置，請參閱[持久資料目錄](https://code.claude.com/docs/zh-TW/plugins/components.md#path-variables-and-persistent-data)。若您透過市集發布外掛，可能不需要此做法：Claude Code 在快取外掛時會[自動安裝符合條件的 Node.js 套件相依套件](https://code.claude.com/docs/zh-TW/plugins/loading.md#node-js-package-dependencies)。

#### Setup 輸入

除了[通用輸入欄位](#common-input-fields)之外，Setup hook 還會接收 `trigger` 欄位，其值為 `"init"` 或 `"maintenance"`：

```json theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "hook_event_name": "Setup",
  "trigger": "init"
}
```

#### Setup 決策控制

Setup hook 無法阻擋；無論退出碼為何，執行都會繼續。無論退出碼為何，Claude Code 都會捨棄 Setup hook 的 [JSON 輸出欄位](#json-output)，例如 `systemMessage`、`continue` 和 `hookSpecificOutput.additionalContext`。使用 `-p` 時，只有在您以 `--output-format stream-json --verbose` 啟動的情況下，Setup hook 的 stdout、stderr 和退出碼才會以 [`hook_response` 事件](https://code.claude.com/docs/zh-TW/headless#read-session-metadata)的形式出現在執行輸出中。

Setup hook 可以存取 `CLAUDE_ENV_FILE`。如果您的 hook 將變數寫入該檔案，這些變數會保存到該工作階段後續的 Bash 命令中，與 [SessionStart hook](#persist-environment-variables) 相同。`Setup` 上只會執行 `type: "command"` hook。`Setup` 上的 `type: "mcp_tool"` hook 一律會被略過，如 [MCP 工具 hook 欄位](#mcp-tool-hook-fields)中所述。

### InstructionsLoaded

當 `CLAUDE.md` 或 `.claude/rules/*.md` 檔案被載入情境時觸發。此事件會在工作階段開始時針對預先載入的檔案觸發，並在稍後檔案延遲載入時再次觸發，例如當 Claude 存取包含巢狀 `CLAUDE.md` 的子目錄，或帶有 `paths:` frontmatter 的條件式規則相符時。此 hook 不支援阻擋或決策控制。它以非同步方式執行，用於可觀察性目的。

當 Claude 透過 **Project instructions** 設定[直接讀取 `AGENTS.md`](https://code.claude.com/docs/zh-TW/memory#agents-md) 時，此事件不會觸發。當 `CLAUDE.md` 匯入您的 `AGENTS.md` 時會觸發，此時 `load_reason` 與其他任何匯入的檔案一樣設為 `include`；當 `CLAUDE.md` 是指向它的符號連結時也會觸發，視為一般的 `CLAUDE.md` 載入。

matcher 會比對 `load_reason`。例如，使用 `"matcher": "session_start"` 僅針對工作階段開始時載入的檔案觸發，或使用 `"matcher": "path_glob_match|nested_traversal"` 僅針對延遲載入觸發。

#### InstructionsLoaded 輸入

除了[通用輸入欄位](#common-input-fields)之外，InstructionsLoaded hook 還會接收下列欄位：

| 欄位 | 說明 |
| :- | :- |
| `file_path` | 已載入的指令檔案的絕對路徑 |
| `memory_type` | 檔案的範圍：`"User"`、`"Project"`、`"Local"` 或 `"Managed"` |
| `load_reason` | 載入檔案的原因：`"session_start"`、`"nested_traversal"`、`"path_glob_match"`、`"include"` 或 `"compact"`。`"compact"` 值會在壓縮事件後重新載入指令檔案時觸發 |
| `globs` | 檔案 `paths:` frontmatter 中的路徑 glob 模式（若有）。僅在 `path_glob_match` 載入時出現 |
| `trigger_file_path` | 對於延遲載入，觸發此次載入的被存取檔案的路徑 |
| `parent_file_path` | 對於 `include` 載入，包含此檔案的上層指令檔案的路徑 |

```json theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../transcript.jsonl",
  "cwd": "/Users/my-project",
  "hook_event_name": "InstructionsLoaded",
  "file_path": "/Users/my-project/CLAUDE.md",
  "memory_type": "Project",
  "load_reason": "session_start"
}
```

#### InstructionsLoaded 決策控制

InstructionsLoaded hook 沒有決策控制。它們無法阻擋或修改指令載入。Claude Code 會捨棄它們的 [JSON 輸出欄位](#json-output)，例如 `systemMessage` 和 `continue`。請將此事件用於稽核日誌、合規追蹤或可觀察性。

### UserPromptSubmit

在提示詞送出時、Claude 處理之前執行。這可讓您
根據提示詞或對話新增額外情境、驗證提示詞，或
阻擋特定類型的提示詞。

`UserPromptSubmit` hook 不僅會針對您輸入的提示詞觸發。Claude Code 也會在下列情況執行它們：

* [工作階段範圍的排程任務](https://code.claude.com/docs/zh-TW/scheduled-tasks.md)觸發時，包括 `/loop` 的每次迭代
* [背景 subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#run-subagents-in-foreground-or-background) 向啟動它的工作階段回報時
* [另一個工作階段傳送訊息](https://code.claude.com/docs/zh-TW/cross-session-messaging.md)到您的主要對話時

`UserPromptSubmit` hook 對於 `command`、`http` 和 `mcp_tool` 類型的預設逾時為 30 秒，短於這些類型在大多數其他事件上的 600 秒預設值。由於此 hook 在每個提示詞之前執行，並會阻擋模型處理直到完成，卡住的 hook 會使工作階段停滯。若您的 hook 需要更多時間，請在 hook 項目中設定 `timeout` 欄位。

除了以 [`async: true`](#run-hooks-in-the-background) 執行的 command hook 之外，達到逾時的 `UserPromptSubmit` command、HTTP 或 MCP tool hook 會被取消，其輸出（包括任何 `additionalContext`）會被捨棄。提示詞仍會在沒有該情境的情況下傳達給 Claude。若要改為阻擋提示詞，請在 command 或 HTTP hook 上設定 [`onFailure: "block"`](#block-the-action-when-a-hook-fails)。逐字稿會顯示一則通知，指出該 hook、觸發的逾時，以及輸出已被捨棄。

`UserPromptSubmit` 上的 [Agent SDK 回呼 hook](https://code.claude.com/docs/zh-TW/agent-sdk/hooks.md) 達到逾時時，會以指出該 hook 與逾時的訊息封鎖提示詞，因為那裡的回呼可能扮演不得在失敗時放行的政策關卡。工作階段會繼續。

#### 提示詞檢查期間按下 `Esc`

如果您在 hook 仍在檢查提示詞時按下 `Esc` 或中斷工作階段，檢查會停止，提示詞也不會傳達給 Claude。您在終端機輸入的文字會回到提示詞輸入框，並在您重新送出時再次由 hook 檢查。

hook 可能在您中斷的同一時刻阻擋提示詞。此時提示詞會維持被阻擋的狀態：您會看到該 hook 的[阻擋訊息](#what-a-blocked-prompt-leaves-behind)，文字也不會回到輸入框。

#### UserPromptSubmit 輸入

除了[通用輸入欄位](#common-input-fields)之外，UserPromptSubmit hook 還會接收包含所送出文字的 `prompt` 欄位。被收合為 `[Pasted text #N]` 預留位置的貼上內容會在原處展開後送達。在 Claude Code [為 Claude 標記貼上文字](https://code.claude.com/docs/zh-TW/terminal-config.md#how-claude-treats-pasted-text)的工作階段中，該展開內容位於 `<pasted_content id="…">` 行和 `</pasted_content id="…">` 行之間，因此若您的 hook 會解析提示詞，請將這些行納入考量。

當工作階段有自訂標題時，UserPromptSubmit hook 也會接收 `session_title`，其意義與 [SessionStart `session_title` 欄位](#sessionstart-input)相同。

```json theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "UserPromptSubmit",
  "prompt": "Write a function to calculate the factorial of a number"
}
```

當提示詞是您輸入的 [skill](https://code.claude.com/docs/zh-TW/skills.md) 或自訂命令（例如 `/deploy staging`）時，hook 接收的是您輸入的那一行原文，而非展開後的 skill 內容。如果 hook 阻擋了該提示詞，命令就不會執行，因此 skill [以 `` !`<command>` `` 注入](https://code.claude.com/docs/zh-TW/skills#inject-dynamic-context)的 shell 命令也不會執行。若要改為比對命令的名稱或引數，請使用 [UserPromptExpansion](#userpromptexpansion)。

#### UserPromptSubmit 決策控制

`UserPromptSubmit` hook 可以控制是否處理所送出的提示詞，並新增情境。所有 [JSON 輸出欄位](#json-output)皆可使用。

在退出碼為 0 時，有兩種方式可以將情境加入對話：

* **純文字 stdout**：Claude Code 會將其[視為純文字](#exit-code-0)的 stdout 加入 Claude 的情境
* **帶有 `additionalContext` 的 JSON**：使用下方的 JSON 格式以獲得更多控制。`additionalContext` 欄位會作為情境加入

兩種管道都不會產生可見的逐字稿項目。純 stdout 和 `additionalContext` 值各自以 hook 名稱開頭的系統提醒形式注入；Claude 會讀取兩者。若要確認已傳遞，請查看[除錯日誌](#debug-hooks)。

若要阻擋提示詞，請回傳 `decision` 設為 `"block"` 的 JSON 物件：

| 欄位 | 說明 |
| :- | :- |
| `decision` | `"block"` 會在提示詞傳達給 Claude 之前將其停止。省略則允許提示詞繼續 |
| `reason` | 當 `decision` 為 `"block"` 時向使用者顯示。不會加入情境 |
| `additionalContext` | 與所送出的提示詞一同加入 Claude 情境的字串。請參閱[為 Claude 新增情境](#add-context-for-claude) |
| `sessionTitle` | 設定工作階段標題。可用於根據提示詞內容自動為工作階段命名 |
| `suppressOriginalPrompt` | 若 hook 阻擋提示詞時此值為 `true`，阻擋訊息中將不包含提示詞文字。請參閱[被阻擋的提示詞會留下什麼](#what-a-blocked-prompt-leaves-behind) |

以退出碼 2 阻擋的 hook，其處理方式與 `reason` 相同：阻擋訊息會向使用者顯示 stderr 文字，且不會加入情境。

```json theme={null}
{
  "decision": "block",
  "reason": "Explanation for decision",
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "My additional context here",
    "sessionTitle": "My session title",
    "suppressOriginalPrompt": true
  }
}
```

#### 被阻擋的提示詞會留下什麼

被阻擋的提示詞永遠不會傳達給 Claude，但其文字並不會從所有地方移除。預設情況下，向使用者顯示的阻擋訊息結尾為 `Original prompt:`，後接所送出的文字，而 Claude Code 會將該訊息寫入磁碟上的工作階段逐字稿檔案。若要在訊息中省略該文字，請在 `hookSpecificOutput` 內印出帶有 `"suppressOriginalPrompt": true` 的 JSON。無論 hook 是以 `decision: "block"` 還是以退出碼 2 阻擋，此設定皆有效。

`suppressOriginalPrompt` 只會變更阻擋訊息。所送出的文字仍可能出現在本機檔案中，例如工作階段逐字稿和您的提示詞歷程記錄，因此阻擋 hook 並不是讓機密不落入磁碟的方法。若要限制或移除這些檔案，請參閱[純文字儲存](https://code.claude.com/docs/zh-TW/claude-directory.md#plaintext-storage)和[清除本機資料](https://code.claude.com/docs/zh-TW/claude-directory.md#clear-local-data)。

### UserPromptExpansion

在使用者輸入的命令展開為提示詞、傳達給 Claude 之前執行。可用於阻擋特定命令被直接呼叫、為特定 skill 注入情境，或記錄使用者呼叫了哪些命令。例如，比對 `deploy` 的 hook 可以在沒有核准檔案時阻擋 `/deploy`，或比對某個審查 skill 的 hook 可以將團隊的審查檢查清單作為 `additionalContext` 附加。

此事件涵蓋了 `PreToolUse` 未涵蓋的路徑：比對 `Skill` 工具的 `PreToolUse` hook 只會在 Claude 呼叫該工具時觸發，但直接輸入 `/skillname` 會繞過 `PreToolUse`。`UserPromptExpansion` 會在該直接路徑上觸發。

比對 `command_name`。將 matcher 留空可針對每個提示詞類型的命令觸發。

#### UserPromptExpansion 輸入

除了[通用輸入欄位](#common-input-fields)之外，UserPromptExpansion hook 還會接收 `expansion_type`、`command_name`、`command_args`、`command_source`，以及原始的 `prompt` 字串。`expansion_type` 欄位對於 skill 和自訂命令為 `slash_command`，對於 MCP 伺服器提示詞則為 `mcp_prompt`。

```json theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../00893aaf.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "UserPromptExpansion",
  "expansion_type": "slash_command",
  "command_name": "example-skill",
  "command_args": "arg1 arg2",
  "command_source": "plugin",
  "prompt": "/example-skill arg1 arg2"
}
```

#### UserPromptExpansion 決策控制

`UserPromptExpansion` hook 可以阻擋展開或新增情境。所有 [JSON 輸出欄位](#json-output)皆可使用。

| 欄位 | 說明 |
| :- | :- |
| `decision` | `"block"` 會阻止命令展開。省略則允許其繼續 |
| `reason` | 當 `decision` 為 `"block"` 時向使用者顯示 |
| `additionalContext` | 與展開後的提示詞一同加入 Claude 情境的字串。請參閱[為 Claude 新增情境](#add-context-for-claude) |

以退出碼 2 阻擋的 hook，其處理方式與 `reason` 相同：阻擋訊息會向使用者顯示 stderr 文字。

```json theme={null}
{
  "decision": "block",
  "reason": "This slash command is not available",
  "hookSpecificOutput": {
    "hookEventName": "UserPromptExpansion",
    "additionalContext": "Additional context for this expansion"
  }
}
```

### MessageDisplay

在助理訊息串流顯示到螢幕上時執行。Claude Code 會分段顯示訊息：每當有一批新完成的行準備好呈現時，hook 會以這些行執行一次，Claude Code 則在其位置呈現 hook 的替換文字。長訊息會產生多次呼叫；短訊息可能只產生一次。

使用 MessageDisplay 來：

* 移除 markdown 以呈現精簡的顯示
* 轉換 Agent SDK 應用程式向其使用者顯示的文字
* 從 Claude 的回應中遮蔽 API 金鑰或內部主機名稱

Claude Code 會保留每一批內容直到您的 hook 回傳，因此請讓 hook 保持快速。若 hook 失敗或逾時，Claude Code 會顯示原始文字。此事件的預設逾時為 10 秒；若您的 hook 需要更多時間，請在 hook 項目中設定 `timeout` 欄位。

MessageDisplay 僅影響顯示：替換文字只會變更螢幕上呈現的內容。逐字稿和 Claude 所見的內容會保留原始文字，因此 Claude 永遠看不到替換內容，詳細模式也會顯示原始文字。hook 只接收助理訊息的文字，因此工具結果和您輸入的文字會原封不動地呈現。

MessageDisplay 不支援 matcher，並會針對每則串流文字的助理訊息觸發；沒有文字的訊息（例如僅包含工具呼叫的回應）不會觸發它。

在非互動式執行中，包括 Agent SDK 查詢和 `claude -p`，MessageDisplay 會對每則助理訊息執行一次，而不是每批行執行一次。這單次呼叫會在訊息完成後到達，並攜帶完整的訊息文字：`index` 為 `0`、`final` 為 `true`，`delta` 則包含整則訊息。收集每則訊息 `delta` 文字的 hook，在兩種模式下接收到的總文字相同。

#### MessageDisplay 輸入

除了[通用輸入欄位](#common-input-fields)之外，MessageDisplay hook 還會接收回合和訊息的識別碼、此次呼叫在訊息中的位置，以及 `delta` 中的新文字。批次邊界取決於文字的串流方式，因此請使用 `index` 和 `final` 追蹤訊息的進度，而不要預期行會以特定方式分組。

| 欄位 | 說明 |
| :- | :- |
| `turn_id` | 目前回合的 UUID |
| `message_id` | 正在顯示的助理訊息的 UUID。在同一則訊息的每一批中都相同。這不是 API 的 `msg_…` id，因此無法與逐字稿的訊息 id 對應 |
| `index` | 此批次在訊息中從零開始的索引 |
| `final` | 在訊息的最後一批為 `true`。每則訊息恰有一個最終批次 |
| `delta` | 自上一批以來新完成的行，包含結尾換行字元。一律為完整的行，但最終批次可能在行中間結束。在互動式執行中，當訊息以換行結尾時，最終批次的 delta 為空，因此請將 `final`（而非非空的 delta）視為訊息結束的訊號。在 Agent SDK 和 `claude -p` 執行中，單次呼叫會攜帶整則訊息 |

```json theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../transcript.jsonl",
  "cwd": "/Users/my-project",
  "hook_event_name": "MessageDisplay",
  "turn_id": "0c9e6a2f-7d41-4f4e-9a15-3f4f7c2b8d10",
  "message_id": "5b2a9c8e-1f63-4d8a-b7c4-9e0d2a6f1c3b",
  "index": 0,
  "final": false,
  "delta": "Here is the plan:\n"
}
```

#### MessageDisplay 輸出

除了所有 hook 都可使用的 [JSON 輸出欄位](#json-output)之外，MessageDisplay hook 還可以回傳 `displayContent`，以在螢幕上取代 delta：

| 欄位 | 說明 |
| :- | :- |
| `displayContent` | 取代 delta 顯示的文字。省略則顯示原始內容 |

MessageDisplay hook 沒有決策控制。它們無法阻擋訊息，也無法變更儲存在逐字稿中或傳送給 Claude 的內容。Claude Code 會依據其 JSON 輸出中的 `displayContent` 採取動作，並捨棄 `systemMessage` 和 `continue`。

此範例會從 Claude 的回應中移除 markdown 格式，以純文字方式顯示。指令碼會從 stdin 讀取每一批，從 `delta` 中移除粗體標記和行內程式碼反引號，並將結果作為 `displayContent` 回傳。

> [tab] macOS/Linux
>
> 在您的設定檔中為此事件註冊一個 command hook：
>
> ```json theme={null}
> {
>   "hooks": {
>     "MessageDisplay": [
>       {
>         "hooks": [
>           {
>             "type": "command",
>             "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/plain-display.sh",
>             "args": []
>           }
>         ]
>       }
>     ]
>   }
> }
> ```
>
> 將此指令碼儲存至專案中的 `.claude/hooks/plain-display.sh`，並以 `chmod +x` 使其可執行：
>
> ```bash theme={null}
> #!/bin/bash
> jq '{hookSpecificOutput: {hookEventName: "MessageDisplay", displayContent: (.delta | gsub("\\*\\*"; "") | gsub("`"; ""))}}'
> ```

> [tab] Windows (PowerShell)
>
> 註冊一個透過 PowerShell 執行指令碼的 command hook：
>
> ```json theme={null}
> {
>   "hooks": {
>     "MessageDisplay": [
>       {
>         "hooks": [
>           {
>             "type": "command",
>             "command": "powershell.exe",
>             "args": [
>               "-NoProfile",
>               "-ExecutionPolicy",
>               "Bypass",
>               "-File",
>               "${CLAUDE_PROJECT_DIR}/.claude/hooks/plain-display.ps1"
>             ]
>           }
>         ]
>       }
>     ]
>   }
> }
> ```
>
> `-NoProfile` 旗標會略過載入您的 PowerShell 設定檔，讓 hook 快速啟動，而 `-ExecutionPolicy Bypass` 則讓 PowerShell 能執行本機指令碼檔案。
>
> 將此指令碼儲存至專案中的 `.claude/hooks/plain-display.ps1`：
>
> ```powershell theme={null}
> $batch = [Console]::In.ReadToEnd() | ConvertFrom-Json
> $text = $batch.delta -replace '\*\*', '' -replace '`', ''
> @{
>   hookSpecificOutput = @{
>     hookEventName = "MessageDisplay"
>     displayContent = $text
>   }
> } | ConvertTo-Json
> ```

不含 markdown 的批次會原封不動地通過。若指令碼失敗，例如因為缺少 `jq`，Claude Code 會顯示原始文字，並只在[除錯輸出](#debug-hooks)中記錄該失敗，而不會在工作階段中顯示。

### PreToolUse

在 Claude 建立工具參數之後、處理工具呼叫之前執行。比對 `EndConversation` 以外的任何工具名稱：內建工具如 `Bash`、`PowerShell`、`Edit`、`Write`、`Read`、`Glob`、`Grep`、`Agent`、`Workflow`、`WebFetch`、`WebSearch`、`AskUserQuestion` 和 `ExitPlanMode`，以及任何 [MCP 工具名稱](#match-mcp-tools)。

若要在特定檔案於磁碟上變更時執行 hook（無論是誰寫入的），請使用 [FileChanged](#filechanged)，而不要依名稱比對檔案編輯工具。與 PreToolUse 不同，Claude Code 會在變更之後執行 FileChanged hook，且它們沒有決策控制，因此無法阻擋寫入。

> [!WARNING]
>
> PreToolUse 只在 Claude 呼叫工具時執行。預設情況下，您[在提示詞中以 `@` 參照](https://code.claude.com/docs/zh-TW/common-workflows#reference-files-and-directories)的檔案會在沒有任何工具呼叫的情況下加入。Claude Code 會在建構提示詞時插入其內容，因此不會為它們觸發任何 PreToolUse hook，包括比對 `Read` 的 hook。PreToolUse 也不會針對 [`EndConversation`](https://code.claude.com/docs/zh-TW/tools-reference#endconversation-tool-behavior) 觸發。
>
> 您可以阻擋特定路徑被 `@` 參照，或關閉插入功能：
>
> * **阻擋特定路徑**：為它們新增 [`Read` 拒絕規則](https://code.claude.com/docs/zh-TW/permissions#read-and-edit)
> * **關閉插入功能**：在您的 shell、使用者設定或受管設定中設定 [`CLAUDE_CODE_DISABLE_FILE_MENTIONS=1`](https://code.claude.com/docs/zh-TW/env-vars#variables)。Claude 接著會取得被提及的路徑，並附上一則說明，要求以其檔案工具讀取。若 Claude 這麼做，您相符的 PreToolUse hook 就會執行。此變數需要 Claude Code v2.1.299 或更新版本，且 Claude Code 會在專案設定和本機設定中忽略它。

使用 [PreToolUse 決策控制](#pretooluse-decision-control)來允許、拒絕、詢問或延遲工具呼叫。

`PreToolUse` 上超過逾時的 [Agent SDK 回呼 hook](https://code.claude.com/docs/zh-TW/agent-sdk/hooks.md#hook-timeout) 會阻擋該工具呼叫。

#### PreToolUse 輸入

除了[通用輸入欄位](#common-input-fields)之外，PreToolUse hook 還會接收 `tool_name`、`tool_input` 和 `tool_use_id`。

對於 [MCP 工具](#match-mcp-tools)，輸入還會攜帶 `mcp_server`，這是一個包含伺服器 `name` 以及說明伺服器定義來源之 `source` 的物件。`source` 的值包括 `plugin`、`sdk`，以及 `user` 和 `project` 等設定範圍。Agent SDK 參考文件中的 [`McpServerProvenance`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#mcpserverprovenance) 列出了所有值，並說明如何處理您無法辨識的值。請根據 `source` 而非 `name` 或 `mcp__<server>__` 工具名稱前綴來做信任決策。`mcp_server` 欄位需要 Claude Code v2.1.274 或更新版本。

對於檔案工具 `Write`、`Edit` 和 `Read`，`tool_input.file_path` 一律為絕對路徑：

* Claude Code 會在 hook 執行前展開 `~` 和相對路徑，因此比對路徑的 hook 無法透過 `~` 或同一路徑的相對寫法被繞過
* 在 Windows 上，路徑會以反斜線分隔符號送達，即使您的 hook 在 Git Bash 下執行、`$PWD` 看起來像 `/c/project` 也是如此
* 以正斜線撰寫的比較（例如 `/src/` 檢查）永遠不會比對到反斜線路徑，工具呼叫會如同 hook 沒有要阻擋的內容般繼續進行
* 比較前請先正規化分隔符號：在 Bash 中使用 `FILE_PATH="${FILE_PATH//\\//}"`，或在 Python 中使用 `file_path.replace("\\", "/")`，然後比對 `/src/` 之類的路徑片段，而不要以 `^` 錨定，因為路徑是絕對路徑

Windows 上的 `Write` 呼叫會傳遞：

```json theme={null}
{
  "hook_event_name": "PreToolUse",
  "tool_name": "Write",
  "tool_input": {
    "file_path": "C:\\project\\src\\index.ts",
    "content": "..."
  },
  ...
}
```

`tool_input` 欄位取決於工具：

##### Bash

執行 shell 命令。

| 欄位 | 類型 | 範例 | 說明 |
| :- | :- | :- | :- |
| `command` | string | `"npm test"` | 要執行的 shell 命令 |
| `description` | string | `"Run test suite"` | 選用，說明命令用途 |
| `timeout` | number | `120000` | 選用，以毫秒為單位的逾時。超過[上限](https://code.claude.com/docs/zh-TW/tools-reference.md#bash-tool-behavior)的值會被降至上限，而不會被拒絕 |
| `run_in_background` | boolean | `false` | 是否在背景執行命令 |

當 Bash 命令變更 Git 儲存庫中的檔案時，Claude Code 可以記錄變更內容。當 [`bashEditDiffEnabled`](https://code.claude.com/docs/zh-TW/settings-reference#basheditdiffenabled) 設定開啟記錄時，它會在每種權限模式下記錄變更；該設定的項目說明了哪些檔案可以設定它。否則，它只會在自動模式和 `bypassPermissions` 模式下記錄，且僅在 Claude Code 指示 Claude 透過 Bash 編輯檔案時才記錄。將 `bashEditDiffEnabled` 設為 `false` 可關閉記錄。背景命令和唯讀命令不會附帶差異。

接著，您的 [PostToolUse hook](#posttooluse) 會在 `tool_response.bashEditDiff` 中接收變更的檔案。此清單涵蓋命令執行期間儲存庫中發生的變更。Git 忽略的檔案和子模組中的檔案不會列出。需要 Claude Code v2.1.269 或更新版本。

> [!NOTE]
>
> 此清單為盡力而為，且處於公開測試版。Claude Code 可能遺漏某項變更、納入另一個程序同時變更的檔案，或在達到大小限制時停止。欄位結構可能會變更。請使用此清單來找出需要審查的內容，而不要用來強制執行政策。

`changedFiles` 和 `files` 列出命令變更的內容；其餘欄位說明該清單的完整程度和可靠程度。

| 欄位 | 類型 | 範例 | 說明 |
| :- | :- | :- | :- |
| `changedFiles` | array | `["/path/to/src/app.ts"]` | 命令變更的檔案絕對路徑，最多 200 個。只要 `files` 包含差異或 `moreFiles` 大於零時就會出現 |
| `files` | array | `[{"filePath": "/path/to/src/app.ts", "hunks": [...]}]` | 最多 5 個變更檔案的差異，供顯示用。對於命令新增或移除的檔案，`created` 或 `deleted` 為 `true` |
| `moreFiles` | number | `2` | 在 `files` 中沒有差異的變更檔案數量 |
| `unavailable` | boolean | `true` | 當差異不完整或無法取得時設定 |
| `skipped` | boolean | `true` | 針對會移動工作樹的 Git 命令設定，例如 `git checkout` 或 `git stash`，因此 Claude Code 不會取得差異 |
| `shared` | boolean | `true` | 當另一個 Bash 工具呼叫（例如 subagent 的呼叫）同時在相同儲存庫中執行時設定，因此部分列出的變更可能來自該命令 |

##### PowerShell

執行 PowerShell 命令。關於各平台的可用性，請參閱 [PowerShell 工具](https://code.claude.com/docs/zh-TW/tools-reference.md#powershell-tool)。

欄位與 Bash 工具相同，命令字串位於 `command`：

| 欄位 | 類型 | 範例 | 說明 |
| :- | :- | :- | :- |
| `command` | string | `"Get-ChildItem -Recurse"` | 要執行的 PowerShell 命令 |
| `description` | string | `"List files recursively"` | 選用，說明命令用途 |
| `timeout` | number | `120000` | 選用，以毫秒為單位的逾時 |
| `run_in_background` | boolean | `false` | 是否在背景執行命令 |

在檢查 shell 命令的 hook 中比對 `Bash|PowerShell`，以涵蓋兩種工具：

* 在 Windows 上，只要啟用了 PowerShell 工具，Claude 就會將 PowerShell 視為主要 shell，並透過它傳送 shell 命令。
* 在沒有 Git Bash 的 Windows 上，該工具會自動啟用，且 Claude Code 完全不會註冊 Bash 工具。
* 只比對 `Bash` 的 hook 在那裡永遠不會觸發。

##### Write

建立或覆寫檔案。

| 欄位 | 類型 | 範例 | 說明 |
| :- | :- | :- | :- |
| `file_path` | string | `"/path/to/file.txt"` | 要寫入的檔案的絕對路徑 |
| `content` | string | `"file content"` | 要寫入檔案的內容 |

##### Edit

取代現有檔案中的字串。

| 欄位 | 類型 | 範例 | 說明 |
| :- | :- | :- | :- |
| `file_path` | string | `"/path/to/file.txt"` | 要編輯的檔案的絕對路徑 |
| `old_string` | string | `"original text"` | 要尋找並取代的文字 |
| `new_string` | string | `"replacement text"` | 替換文字 |
| `replace_all` | boolean | `false` | 是否取代所有出現處 |

##### Read

讀取檔案內容。

| 欄位 | 類型 | 範例 | 說明 |
| :- | :- | :- | :- |
| `file_path` | string | `"/path/to/file.txt"` | 要讀取的檔案的絕對路徑 |
| `offset` | number | `10` | 選用，開始讀取的行號 |
| `limit` | number | `50` | 選用，要讀取的行數 |

##### Glob

尋找符合 glob 模式的檔案。

| 欄位 | 類型 | 範例 | 說明 |
| :- | :- | :- | :- |
| `pattern` | string | `"**/*.ts"` | 用來比對檔案的 glob 模式 |
| `path` | string | `"/path/to/dir"` | 選用，要搜尋的目錄。預設為目前的工作目錄 |

##### Grep

使用正規表示式搜尋檔案內容。

| 欄位 | 類型 | 範例 | 說明 |
| :- | :- | :- | :- |
| `pattern` | string | `"TODO.*fix"` | 要搜尋的正規表示式模式 |
| `path` | string | `"/path/to/dir"` | 選用，要搜尋的檔案或目錄 |
| `glob` | string | `"*.ts"` | 選用，用於篩選檔案的 glob 模式 |
| `output_mode` | string | `"content"` | `"content"`、`"files_with_matches"` 或 `"count"`。預設為 `"files_with_matches"` |
| `-i` | boolean | `true` | 不區分大小寫的搜尋 |
| `multiline` | boolean | `false` | 啟用多行比對 |

##### WebFetch

擷取並處理網頁內容。

| 欄位 | 類型 | 範例 | 說明 |
| :- | :- | :- | :- |
| `url` | string | `"https://example.com/api"` | 要擷取內容的 URL |
| `prompt` | string | `"Extract the API endpoints"` | 對擷取內容執行的提示詞 |
| `offset` | number | `100000` | 選用，從頁面開頭略過的字元數。Claude 會設定此值以繼續閱讀長頁面。需要 Claude Code v2.1.290 或更新版本 |

##### WebSearch

搜尋網路。

| 欄位 | 類型 | 範例 | 說明 |
| :- | :- | :- | :- |
| `query` | string | `"react hooks best practices"` | 搜尋查詢 |
| `allowed_domains` | array | `["docs.example.com"]` | 選用：只包含來自這些網域的結果 |
| `blocked_domains` | array | `["spam.example.com"]` | 選用：排除來自這些網域的結果 |
| `mode` | string | `"extended"` | 選用：搜尋類型。`"standard"` 會要求較輕量的搜尋，`"extended"` 則要求完整搜尋。有些工作階段不會傳送 `mode`，而未帶此欄位的呼叫會執行完整搜尋。需要 Claude Code v2.1.282 或更新版本 |

##### Agent

產生一個 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md)。

| 欄位 | 類型 | 範例 | 說明 |
| :- | :- | :- | :- |
| `prompt` | string | `"Find all API endpoints"` | agent 要執行的任務 |
| `description` | string | `"Find API endpoints"` | 任務的簡短說明 |
| `subagent_type` | string | `"Explore"` | 要使用的專門 agent 類型 |
| `model` | string | `"sonnet"` | 選用，用來覆寫預設值的模型別名 |

當前景 Agent 呼叫完成時，您的 [PostToolUse hook](#posttooluse) 會在 `tool_response` 中接收 subagent 的結果和執行遙測。讀取這些欄位以檢視執行情況；若要彙總各 subagent 的 token 和成本，請使用以 `query_source` `"subagent"` 篩選的 [token 和成本計數器](https://code.claude.com/docs/zh-TW/monitoring-usage.md#token-counter)，因為 `totalTokens` 和 `usage` 只涵蓋最後一個請求：

| 欄位 | 類型 | 範例 | 說明 |
| :- | :- | :- | :- |
| `status` | string | `"completed"` | 前景 subagent 為 `"completed"`，背景 subagent 為 `"async_launched"`。關於哪些 subagent 以何種方式執行，請參閱[在前景或背景執行 subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#run-subagents-in-foreground-or-background) |
| `agentId` | string | `"a4d2c8f1e0b3a297"` | subagent 執行的識別碼 |
| `content` | array | `[{"type": "text", "text": "Found 12 endpoints..."}]` | subagent 的最終文字區塊；對於透過 `SubagentHandback` 提交報告的 subagent，則以一則關於該交回的簡短說明代替 |
| `resolvedModel` | string | `"claude-sonnet-4-5"` | subagent 起始使用的模型，可能與所要求的模型不同 |
| `modelsUsed` | array | `["claude-sonnet-4-5", "claude-haiku-4-5"]` | 依序使用的模型，連續重複者會合併；僅在執行途中切換模型時設定 |
| `totalTokens` | number | `12450` | subagent 最後一個 API 請求的 token 數：輸入、輸出和快取 token 的總和。這不是整個執行的總計 |
| `totalDurationMs` | number | `48211` | subagent 執行的實際經過時間 |
| `totalToolUseCount` | number | `7` | subagent 進行的工具呼叫次數 |
| `usage` | object | `{"input_tokens": 8320, ...}` | 最後一個 API 請求的各類型 token 明細：`input_tokens`、`output_tokens`、`cache_creation_input_tokens`、`cache_read_input_tokens` |

在 Claude Code v2.1.271 或更新版本中，以 [`SubagentHandback`](https://code.claude.com/docs/zh-TW/tools-reference) 工具執行的 subagent（Claude Code 在[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)中提供此工具）會透過該工具提交報告，而不是以文字回傳。此時其 `completed` 結果的 `content` 欄位會攜帶一則關於該交回的簡短說明，而非報告本身。若要讀取報告，請讓 `PreToolUse` 或 `PostToolUse` hook 比對 `SubagentHandback`，並讀取 `tool_input.message`。

對於背景 subagent，工具會在任務移至背景時回傳，因此 `tool_response` 不攜帶任何用量欄位：背景啟動會立即回傳，而被 Claude Code 在執行中途移至背景的前景任務則會在該轉換時回傳。它包含 `status: "async_launched"`、`agentId`、`description`、`prompt`、`outputFile` 和 `resolvedModel`。

在 `completed` 回應中，`resolvedModel` 指出 subagent 開始時使用的模型，這可能與 `tool_input` 中的 `model` 值不同，例如在 `availableModels` 或其他覆寫生效時。在 `async_launched` 回應中，`resolvedModel` 指出 agent 移至背景時正在使用的模型，因此在移至背景之前發生的切換會反映在其中。

##### AskUserQuestion

向使用者詢問一到四個多選題。

| 欄位 | 類型 | 範例 | 說明 |
| :- | :- | :- | :- |
| `questions` | array | `[{"question": "Which framework?", "header": "Framework", "options": [{"label": "React", "description": "Component library"}, {"label": "Vue", "description": "Progressive framework"}], "multiSelect": false}]` | 要呈現的問題，每個問題包含 `question` 字串、簡短的 `header`、`options` 陣列，以及選用的 `multiSelect` 旗標 |
| `answers` | object | `{"Which framework?": "React"}` | 選用。將問題文字對應到所選選項的標籤。多選答案會以逗號連接標籤。Claude 不會設定此欄位；若要以程式方式回答，請透過 `updatedInput` 提供 |

##### ExitPlanMode

呈現計畫，並在 Claude 離開 [plan mode](https://code.claude.com/docs/zh-TW/permission-modes.md#analyze-before-you-edit-with-plan-mode) 之前請使用者核准。Claude 會在呼叫工具之前將計畫寫入磁碟上的檔案，因此模型傳來的原始 `tool_input` 通常是空的。Claude Code 會在將輸入傳給 hook 之前注入計畫內容和檔案路徑。

| 欄位 | 類型 | 範例 | 說明 |
| :- | :- | :- | :- |
| `plan` | string | `"## Refactor auth\n1. Extract..."` | Markdown 格式的計畫內容。從磁碟上的計畫檔案注入 |
| `planFilePath` | string | `"/Users/.../plans/refactor-auth.md"` | 計畫檔案的路徑。注入 |
| `allowedPrompts` | array | `[{"tool": "Bash", "prompt": "run tests"}]` | 已棄用。Claude Code 會接受此欄位但予以忽略。在 v2.1.205 之前，它攜帶 Claude 為實作計畫所要求的以提示詞為基礎的權限 |

在 `PostToolUse` 中，`tool_response` 是一個物件，其中的 `plan` 和 `filePath` 欄位包含已核准的計畫，另外還有內部狀態旗標。請讀取 `tool_response.plan` 取得計畫內容，而不要從磁碟重新讀取檔案。

#### PreToolUse 決策控制

`PreToolUse` hook 可以控制工具呼叫是否繼續。與其他使用頂層 `decision` 欄位的 hook 不同，PreToolUse 會在 `hookSpecificOutput` 物件內回傳其決策。這讓它擁有更豐富的控制：四種結果（允許、拒絕、詢問或延遲），以及在執行前修改工具輸入的能力。

| 欄位 | 說明 |
| :- | :- |
| `permissionDecision` | `"allow"` 會略過權限提示，但[沒有任何模式會自動核准的動作](https://code.claude.com/docs/zh-TW/permission-modes.md#actions-no-mode-auto-approves)和[從網路路徑讀取](https://code.claude.com/docs/zh-TW/permissions.md#network-paths)除外。對於[Agent SDK 應用程式標記為 `always_ask` 的工具](https://code.claude.com/docs/zh-TW/agent-sdk/custom-tools#require-approval-for-specific-tools)的呼叫，它也不會略過核准，除非[權限模式核准了該呼叫](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md#permission-modes-that-can-approve-an-always_ask-call)。`AskUserQuestion` 和 `ExitPlanMode` 需要[與 `"allow"` 搭配的 `updatedInput`](#allow-with-updatedinput)。關於 plan mode，請參閱[plan mode 中的 hook 核准](https://code.claude.com/docs/zh-TW/permissions.md#hook-approvals-in-plan-mode)。`"deny"` 會阻止工具呼叫。`"ask"` 會提示使用者確認。`"defer"` 會結束回合，讓工具稍後可以恢復，且需要使用 `-p` 旗標的[非互動模式](#defer-a-tool-call-for-later)。無論 hook 回傳什麼，[拒絕與詢問規則](https://code.claude.com/docs/zh-TW/permissions.md#manage-permissions)仍會被評估 |
| `permissionDecisionReason` | 對於 `"ask"`，會在權限提示中向使用者顯示。當 Claude Code 在沒有人能回應該提示的 `-p` 執行中[拒絕呼叫](https://code.claude.com/docs/zh-TW/headless.md#turn-off-permission-prompts-in-unattended-runs)時，Claude 會改為在工具結果中讀到原因。對於 `"deny"`，會向 Claude 顯示。對於 `"allow"` 和 `"defer"`，只會寫入[除錯日誌](#debug-hooks) |
| `updatedInput` | 在執行前修改工具的輸入參數。會取代整個輸入物件，因此請將未變更的欄位與修改過的欄位一起納入。Claude Code 會針對您的 hook 回傳的輸入（而非 Claude 傳送的輸入）評估權限規則和 Bash 命令的[自動移至背景資格](https://code.claude.com/docs/zh-TW/tools-reference.md#foreground-commands-that-move-to-the-background)。搭配 `"allow"` 可自動核准，搭配 `"ask"` 可向使用者顯示修改後的輸入。對於 `"defer"` 會被忽略。若沒有 `permissionDecision`，[自動模式可能會拒絕變更後的呼叫](#pretooluse-updatedinput-in-auto-mode) |
| `additionalContext` | 與工具結果一同加入 Claude 情境的字串。當 `permissionDecision` 為 `"defer"` 時會被忽略。請參閱[為 Claude 新增情境](#add-context-for-claude) |

當多個 PreToolUse hook 回傳不同的決策時，優先順序為 `deny` > `defer` > `ask` > `allow`。

以退出碼 2 阻擋的 hook，其處理方式與 `"deny"` 相同：Claude 會將 stderr 訊息視為拒絕原因。

當 hook 回傳 `"ask"` 時，向使用者顯示的權限提示會包含一個標籤，指出該 hook 的來源：來自任何設定檔或 agent frontmatter 的 hook 為 `[settings]`，外掛的 hook 為 `[plugin:<name>]`，來自 skill frontmatter 的 hook 則為 `[skill]`。這有助於使用者了解是哪個設定來源在要求確認。

```json theme={null}
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "permissionDecisionReason": "My reason here",
    "updatedInput": {
      "field_to_modify": "new value"
    },
    "additionalContext": "Current environment: production. Proceed with caution."
  }
}
```

> [!NOTE]
>
> PreToolUse 先前使用頂層的 `decision` 和 `reason` 欄位，但這些欄位在此事件中已棄用。請改用 `hookSpecificOutput.permissionDecision` 和 `hookSpecificOutput.permissionDecisionReason`。已棄用的值 `"approve"` 和 `"block"` 分別對應到 `"allow"` 和 `"deny"`。PostToolUse 和 Stop 等其他事件則繼續以頂層 `decision` 和 `reason` 作為其目前的格式。

#### 自動模式中的 PreToolUse `updatedInput`

當您的 hook 在[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)中回傳 `updatedInput` 但沒有 `permissionDecision` 時，Claude Code 可能會拒絕變更後的呼叫。[伺服器審查的](https://code.claude.com/docs/zh-TW/permission-modes.md#server-side-classifier-review)是 Claude 撰寫的輸入，而不是您的 hook 回傳的輸入。在直接連線到 Anthropic API 的互動式終端機工作階段和 VS Code 工作階段中，拒絕訊息會包含下列文字：

```text theme={null}
a hook changed this call's input after auto mode reviewed it
```

在出現此文字的拒絕之後，Claude 可以再次發出變更後的呼叫，讓伺服器審查它。若 Claude 在下一個回應中完全重複變更後的輸入，您的 hook 仍會執行：

* 它可以拒絕該呼叫，或將其送到權限提示
* 它回傳的任何 `updatedInput` 都會被捨棄，因此實際執行的就是伺服器審查過的內容

除非 [Claude 在回覆中告訴您自動模式無法檢查該呼叫](https://code.claude.com/docs/zh-TW/errors.md#hook-changed-input-after-review)，否則您不需要為了此拒絕而變更 hook。

在會顯示此文字的工作階段中，設定中或外掛 hook 檔案中的 [`command` hook](#command-hook-fields) 可以變更 Bash、PowerShell、Monitor、Edit、Write 和 NotebookEdit 呼叫而不會觸發此拒絕。拒絕仍可能出現，例如當任何 hook 變更了同一個 Claude 回應中較早的呼叫，或 Bash 命令要求在沙箱外執行時。

#### 自動模式中的 PreToolUse `ask` 決策

在[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)中，PreToolUse hook 的 `"ask"` 通常會將工具呼叫送往權限提示，而[分類器](https://code.claude.com/docs/zh-TW/permission-modes.md#how-the-classifier-evaluates-actions)不會對其做出決定。有些呼叫則會走不同的路徑：

* **同樣被 Claude Code 自身檢查標記的呼叫**：這些包括寫入[受保護路徑](https://code.claude.com/docs/zh-TW/permission-modes.md#protected-paths)，以及要求[在沙箱外執行](https://code.claude.com/docs/zh-TW/sandboxing.md#the-unsandboxed-retry-escape-hatch)的命令。分類器可能會在任何提示出現之前拒絕這類呼叫。如果分類器核准，該呼叫通常仍會送往提示。
* **`SubagentHandback` 呼叫**：此工具用於傳遞 subagent 的報告。它不會顯示任何提示，且即使分類器反對，呼叫仍會執行。

若要停止 `SubagentHandback` 呼叫，請回傳 `"deny"`。Claude Code 接著會告知 subagent（最多三次）其報告未傳遞，並請它再次呼叫該工具。如果您的 hook 持續拒絕，subagent 會在未透過此工具傳遞報告的情況下結束，而等待它的對話會收到一則說明此情況的通知。

#### 需要使用者互動的工具

`AskUserQuestion` 和 `ExitPlanMode` 需要使用者互動。在使用 `-p` 旗標的[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)中，只有當執行具有可接收提示的[權限主機](https://code.claude.com/docs/zh-TW/headless.md#turn-off-permission-prompts-in-unattended-runs)（例如 Agent SDK 的 `canUseTool` 回呼）時，Claude Code 才會提供這些工具。

`PreToolUse` hook 在執行下列動作時即可滿足該需求：

1. 從 stdin 讀取工具的輸入
2. 透過您自己的 UI 收集答案
3. 回傳 `permissionDecision: "allow"`，並搭配包含答案的 `updatedInput`，讓工具在不提示的情況下執行

對於這些工具，僅回傳 `"allow"` 是不夠的。

對於 `AskUserQuestion`，請回傳原始的 `questions` 陣列，並新增一個 [`answers`](#askuserquestion) 物件，將每個問題的文字對應到所選答案。此輸出以 `React` 回答一個問題：

```json theme={null}
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "updatedInput": {
      "questions": [
        {
          "question": "Which framework?",
          "header": "Framework",
          "options": [{"label": "React", "description": "Component library"}, {"label": "Vue", "description": "Progressive framework"}],
          "multiSelect": false
        }
      ],
      "answers": {"Which framework?": "React"}
    }
  }
}
```

伺服器以 [`_meta["anthropic/requiresUserInteraction"]`](https://code.claude.com/docs/zh-TW/mcp#require-approval-for-a-specific-tool) 標記的 MCP 工具則更為嚴格：hook 無法以 `"allow"` 略過其核准提示，無論是否搭配 `updatedInput`，因為 Claude Code 無法確認 hook 已收集到該工具所需的互動。

#### 將工具呼叫延遲到稍後

`"defer"` 適用於以子程序方式執行 `claude -p` 並讀取其 JSON 輸出的整合，例如 Agent SDK 應用程式或建構在 Claude Code 之上的自訂 UI。它讓呼叫端程序可以在工具呼叫處暫停 Claude、透過自己的介面收集輸入，然後從中斷處恢復。Claude Code 只在使用 `-p` 旗標的[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)中遵守此值。在互動式工作階段中，它會記錄警告並忽略 hook 結果。

`AskUserQuestion` 工具是典型的情況：Claude 想詢問使用者某件事，但沒有終端機可供回答。`-p` 執行只有在具有[權限主機](https://code.claude.com/docs/zh-TW/headless.md#turn-off-permission-prompts-in-unattended-runs)時才會提供 `AskUserQuestion`，例如您以 `--permission-prompt-tool` 傳入的 MCP 工具，因此請以此方式啟動執行。來回流程如下：

1. Claude 呼叫 `AskUserQuestion`。`PreToolUse` hook 觸發。
2. hook 傳回 `permissionDecision: "defer"`。工具不會執行。回合以一個帶有 `stop_reason: "tool_deferred"` 的結果結束，而待處理的工具呼叫會保留在逐字稿中。
3. 呼叫端程序從 SDK 結果讀取 `deferred_tool_use`，在自己的 UI 中呈現問題，並等待答案。
4. 呼叫端程序以相同的權限主機執行 `claude -p --resume <session-id>`。同一個工具呼叫再次觸發 `PreToolUse`。
5. hook 回傳 `permissionDecision: "allow"`，並在 `updatedInput` 中附上答案。工具執行，Claude 繼續。

`deferred_tool_use` 欄位攜帶工具的 `id`、`name` 和 `input`。`input` 是 Claude 為該工具呼叫產生的參數，在執行前擷取：

```json theme={null}
{
  "type": "result",
  "subtype": "success",
  "stop_reason": "tool_deferred",
  "session_id": "abc123",
  "deferred_tool_use": {
    "id": "toolu_01abc",
    "name": "AskUserQuestion",
    "input": { "questions": [{ "question": "Which framework?", "header": "Framework", "options": [{"label": "React", "description": "Component library"}, {"label": "Vue", "description": "Progressive framework"}], "multiSelect": false }] }
  }
}
```

沒有逾時或重試次數限制。工作階段會保留在磁碟上直到您繼續它，但受 [`cleanupPeriodDays`](https://code.claude.com/docs/zh-TW/settings-reference#cleanupperioddays) 保留期清理的約束，該清理預設會在 30 天後刪除工作階段檔案，並遵循[保留期清理規則](https://code.claude.com/docs/zh-TW/claude-directory.md#cleaned-up-automatically)。

如果在您繼續時延後的工具已不再可用，繼續後的第一個結果會帶有 `stop_reason: "tool_deferred_unavailable"` 和 `is_error: true`，且 hook 不會觸發。當提供該工具的 MCP 伺服器在繼續的工作階段中未連線時，就會發生這種情況。`deferred_tool_use` payload 仍會包含在內，讓您可以識別遺失的是哪個工具。

* **如果您在繼續時或之後未傳送提示詞**，該呼叫仍處於待處理狀態。在工具可用時再次繼續，它會最先執行。
* **如果您在繼續時或之後傳送了提示詞**，Claude Code 會在沒有工具結果的情況下回答它，並捨棄延後的呼叫。如果您仍需要呼叫該工具，請在工具可用後傳送新的提示詞。

如果在您不帶提示詞繼續時，所等待的答案尚未就緒，hook 可以再次傳回 `"defer"`。如果您傳送了提示詞而 hook 再次延後，Claude Code 會以相同方式處理該提示詞：在沒有工具結果的情況下回答，並捨棄該呼叫。請在不帶提示詞的情況下繼續，直到 hook 傳回 `"allow"` 或 `"deny"`，這就是呼叫端程序跳出迴圈的方式。

`"defer"` 只在 Claude 於該回合中進行單一工具呼叫時有效。若 Claude 同時進行多個工具呼叫，`"defer"` 會被忽略並顯示警告，工具則會經由一般的權限流程繼續。此限制的原因在於恢復時只能重新執行一個工具：無法在不讓其他呼叫懸而未決的情況下，延遲一批呼叫中的其中一個。

> [!NOTE]
>
> 若要在 plan mode 中恢復延遲的工作階段，請將 [`--permission-prompt-tool`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 與 `--resume` 一起傳入，讓 Claude Code 能呈現計畫以供核准。其他條件請參閱[以 `-p` 在 plan mode 中恢復](https://code.claude.com/docs/zh-TW/sessions#resume-in-plan-mode-with-p)。需要 Claude Code v2.1.246 或更新版本。
>
> 當您以 `-p` 恢復時，Claude Code 不會還原任何其他已儲存的權限模式。它會以新的 `claude -p` 執行所使用的權限模式啟動，因此若延遲的工作階段使用了 `--permission-mode` 或 `--dangerously-skip-permissions`，請再次傳入。當您不使用 `-p`、以 `claude --resume <session-id>` 恢復時，Claude Code 會還原已儲存的權限模式，例外情況列於[恢復時的權限模式](https://code.claude.com/docs/zh-TW/sessions.md#permission-mode-on-resume)。

### PermissionRequest

在 Claude Code 即將向您要求使用工具的權限時執行。在無法顯示提示的工作階段中，例如[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)中的背景 subagent，Claude Code 仍會執行這些 hook，若沒有 hook 回傳決策，它會拒絕該工具呼叫。對於傳達到 `--permission-prompt-tool` 或 Agent SDK 的 [`canUseTool` 回呼](https://code.claude.com/docs/zh-TW/agent-sdk/permissions)的呼叫，hook 會與您的主機並行執行，並以先做出決定者為準。
使用 [PermissionRequest 決策控制](#permissionrequest-decision-control)代表使用者允許或拒絕。

當您需要在 Claude 要求使用工具權限的當下取得訊號時，請使用此事件。Claude Code 只會在提示已等待約六秒後，才執行 `permission_prompt` 類型的 [Notification](#notification) hook。

Claude Code 不會針對沙箱化命令的[網路請求](https://code.claude.com/docs/zh-TW/sandboxing.md#network-isolation)執行 PermissionRequest hook。若要取得該提示的訊號，請使用 `permission_prompt` 通知類型。

比對工具名稱，值與 PreToolUse 相同。

#### PermissionRequest 輸入

PermissionRequest hook 會接收 `tool_name` 與 `tool_input` 欄位，與 PreToolUse hook 相同，但不含 `tool_use_id`。對於 MCP 工具，它們也會接收 [`mcp_server`](#pretooluse-input) 物件。選用的 `permission_suggestions` 陣列包含 Claude Code 針對此請求建議的[權限更新](#permission-update-entries)，例如新增允許規則或變更權限模式。

`permission_suggestions` 陣列並非您所看到選項的精確清單，因為每個權限對話框會自行建構其選項。有些對話框（例如用於檔案編輯的對話框）完全不讀取此陣列，而是從請求本身推導出選項。會讀取此陣列的對話框，仍可能隱藏某個建議仍保留在陣列中的選項，例如當 [`allowManagedPermissionRulesOnly`](https://code.claude.com/docs/zh-TW/settings-reference#allowmanagedpermissionrulesonly) 隱藏儲存規則的選項時。它也可能提供沒有對應建議項目的選項，例如 [**Yes, and switch to auto mode**](https://code.claude.com/docs/zh-TW/permission-modes.md#switch-permission-modes)，此選項會直接變更權限模式，而非透過權限更新。

PreToolUse hook 會在每次工具呼叫之前執行，無論是否需要權限。PermissionRequest hook 只會在 Claude Code 即將向您請求權限時執行，或在它原本會自動拒絕某個無法提示的呼叫時執行。這兩個事件都不會針對 [`EndConversation`](https://code.claude.com/docs/zh-TW/tools-reference#endconversation-tool-behavior) 觸發。

```json theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "PermissionRequest",
  "tool_name": "Bash",
  "tool_input": {
    "command": "rm -rf node_modules",
    "description": "Remove node_modules directory"
  },
  "permission_suggestions": [
    {
      "type": "addRules",
      "rules": [{ "toolName": "Bash", "ruleContent": "rm -rf node_modules" }],
      "behavior": "allow",
      "destination": "localSettings"
    }
  ]
}
```

#### PermissionRequest 決策控制

`PermissionRequest` hook 可以允許或拒絕權限請求。除了所有 hook 都可使用的 [JSON 輸出欄位](#json-output)之外，您的 hook 指令碼還可以回傳包含以下事件專屬欄位的 `decision` 物件：

| 欄位 | 說明 |
| :- | :- |
| `behavior` | `"allow"` 授予權限，`"deny"` 拒絕權限。[拒絕與詢問規則](https://code.claude.com/docs/zh-TW/permissions.md#manage-permissions)仍會被評估，因此回傳 `"allow"` 的 hook 不會覆寫相符的拒絕規則 |
| `updatedInput` | 僅適用於 `"allow"`：在執行前修改工具的輸入參數。會取代整個輸入物件，因此請將未變更的欄位與修改過的欄位一併包含。修改後的輸入會再次依據拒絕與詢問規則進行評估 |
| `updatedPermissions` | 僅適用於 `"allow"`：要套用的[權限更新項目](#permission-update-entries)陣列，例如新增允許規則或變更工作階段的權限模式 |
| `message` | 僅適用於 `"deny"`：告訴 Claude 權限被拒絕的原因 |
| `interrupt` | 僅適用於 `"deny"`：若為 `true`，則停止 Claude |

以退出碼 2 結束但未提供 `decision` 物件的 hook 不會改變權限流程，且其 stderr 會被捨棄。若要授予或拒絕請求，請回傳 `decision` 物件。

```json theme={null}
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "allow",
      "updatedInput": {
        "command": "npm run lint"
      }
    }
  }
}
```

#### 權限更新項目

`updatedPermissions` 輸出欄位與 [`permission_suggestions` 輸入欄位](#permissionrequest-input)都使用相同的項目物件陣列。每個項目都有一個決定其他欄位的 `type`，以及一個控制變更寫入位置的 `destination`。

| `type` | 欄位 | 效果 |
| :- | :- | :- |
| `addRules` | `rules`、`behavior`、`destination` | 新增權限規則。`rules` 是 `{toolName, ruleContent?}` 物件的陣列。省略 `ruleContent` 即可比對整個工具。`behavior` 為 `"allow"`、`"deny"` 或 `"ask"` |
| `replaceRules` | `rules`、`behavior`、`destination` | 以提供的 `rules` 取代 `destination` 中指定 `behavior` 的所有規則 |
| `removeRules` | `rules`、`behavior`、`destination` | 移除指定 `behavior` 的相符規則 |
| `setMode` | `mode`、`destination` | 變更權限模式。有效的模式為 `default`、`auto`、`acceptEdits`、`dontAsk`、`bypassPermissions`、`plan`，以及作為 `default` 別名的 `manual` |
| `addDirectories` | `directories`、`destination` | 新增工作目錄。`directories` 是路徑字串的陣列 |
| `removeDirectories` | `directories`、`destination` | 移除工作目錄 |

> [!NOTE]
>
> 帶有 `bypassPermissions` 的 `setMode` 只有在您啟動工作階段時已可使用略過模式的情況下才會生效：`--dangerously-skip-permissions`、`--permission-mode bypassPermissions`、`--allow-dangerously-skip-permissions`，或在[使用者、`--settings` 或受管設定](https://code.claude.com/docs/zh-TW/settings-reference#permissions-defaultmode)中設定 `permissions.defaultMode: "bypassPermissions"`。否則此更新不會產生任何作用。當 [`permissions.disableBypassPermissionsMode`](https://code.claude.com/docs/zh-TW/permissions#managed-settings) 停用此模式，或工作階段以[受限模式](https://code.claude.com/docs/zh-TW/cli-reference.md#cli-flags)啟動時，此更新同樣不會產生任何作用。
>
> 無論 `destination` 為何，`bypassPermissions` 都不會被保存為 `defaultMode`。

每個項目上的 `destination` 欄位決定變更是僅保留在記憶體中，還是保存到設定檔。

| `destination` | 寫入位置 |
| :- | :- |
| `session` | 僅在記憶體中，工作階段結束時捨棄 |
| `localSettings` | `.claude/settings.local.json` |
| `projectSettings` | `.claude/settings.json` |
| `userSettings` | `~/.claude/settings.json` |

hook 可以將其接收到的其中一個 `permission_suggestions` 作為自己的 `updatedPermissions` 輸出回傳。

### PostToolUse

在工具成功完成後立即執行。

依工具名稱比對，值與 PreToolUse 相同。

當工具名稱不是合適的篩選條件時，可使用更廣泛的比對方式：

* 若要在任何工具成功完成後執行 hook，請省略 `matcher` 或將其設為 `"*"`。接著您的 hook 可以自行找出變更內容，例如執行 `git status --porcelain`，它也會列出 `git diff` 遺漏的未追蹤檔案。對於失敗的工具呼叫，請在 [PostToolUseFailure](#posttoolusefailure) 下加入相同的 hook。
* 若要在特定檔案於磁碟上變更時執行 hook（不論是由誰寫入），請使用 [FileChanged](#filechanged)。當 `Bash` 命令或 Claude Code 以外的程序重寫同一個檔案時，Claude Code 不會執行比對 `Edit|Write` 的 `PostToolUse` hook。

#### PostToolUse 輸入

`PostToolUse` hook 會在工具已成功執行後觸發。輸入同時包含 `tool_input`（傳送給工具的引數）與 `tool_response`（工具回傳的結果）。兩者的確切 schema 取決於工具。檔案工具的 `tool_input` 路徑格式與 [PreToolUse](#pretooluse-input) 相同：一律為絕對路徑，並使用平台原生的分隔符號，因此在 Windows 上為反斜線。對於 MCP 工具，輸入也會攜帶 [`mcp_server`](#pretooluse-input) 物件。

```json theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "PostToolUse",
  "tool_name": "Write",
  "tool_input": {
    "file_path": "/path/to/file.txt",
    "content": "file content"
  },
  "tool_response": {
    "filePath": "/path/to/file.txt",
    "type": "create"
  },
  "tool_use_id": "toolu_01ABC123...",
  "duration_ms": 12
}
```

| 欄位 | 說明 |
| :- | :- |
| `duration_ms` | 選用。工具執行時間（毫秒）。不包含花在權限提示與 PreToolUse hook 上的時間 |

#### PostToolUse 決策控制

`PostToolUse` hook 可以在工具執行後向 Claude 提供回饋。除了所有 hook 都可使用的 [JSON 輸出欄位](#json-output)之外，您的 hook 指令碼還可以回傳以下事件專屬欄位：

| 欄位 | 說明 |
| :- | :- |
| `decision` | `"block"` 會在工具結果旁加入 `reason`。Claude 仍會看到原始輸出；若要取代輸出，請使用 `updatedToolOutput` |
| `reason` | 當 `decision` 為 `"block"` 時向 Claude 顯示的說明 |
| `additionalContext` | 與工具結果一併加入 Claude 上下文的字串。請參閱[為 Claude 新增上下文](#add-context-for-claude) |
| `classifierContext` | 關於此呼叫結果的簡短註記，提供給[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)分類器而非 Claude。請參閱[為自動模式分類器註記結果](#annotate-a-result-for-the-auto-mode-classifier)。需要 Claude Code v2.1.236 或更新版本 |
| `updatedToolOutput` | 在將工具輸出傳送給 Claude 之前，以提供的值取代。該值必須符合工具的輸出結構 |
| `updatedMCPToolOutput` | 僅取代 [MCP 工具](#match-mcp-tools)的輸出。建議改用適用於所有工具的 `updatedToolOutput` |

以下範例取代了 `Bash` 呼叫的輸出。取代值符合 `Bash` 工具的輸出結構：

```json theme={null}
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "Additional information for Claude",
    "updatedToolOutput": {
      "stdout": "[redacted]",
      "stderr": "",
      "interrupted": false,
      "isImage": false
    }
  }
}
```

> [!WARNING]
>
> `updatedToolOutput` 只會改變 Claude 看到的內容。在 hook 觸發時工具早已執行，因此任何寫入的檔案、執行的命令或傳送的網路請求都已生效。OpenTelemetry 工具 span 與分析事件等遙測資料也會在 hook 執行前擷取原始輸出。若要在工具呼叫執行前加以阻止或修改，請改用 [PreToolUse](#pretooluse) hook。
>
> 取代值必須符合工具的輸出結構。內建工具回傳的是結構化物件而非純字串。例如，`Bash` 回傳的物件包含 `stdout`、`stderr`、`interrupted` 與 `isImage` 欄位。對於內建工具，不符合工具輸出 schema 的值會被忽略，並改用原始輸出。MCP 工具的輸出會直接傳遞，不進行 schema 驗證。移除 Claude 所需的錯誤細節，可能導致它基於錯誤的假設繼續進行。

#### 為自動模式分類器註記結果

回傳 `classifierContext`，即可將關於工具呼叫結果的簡短註記傳送給[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)分類器，而非傳送給 Claude。分類器[永遠不會接收工具結果本身](https://code.claude.com/docs/zh-TW/permission-modes.md#how-the-classifier-evaluates-actions)，因此此欄位是在分類器審查後續動作之前，告知它呼叫回傳內容的受支援方式。此欄位需要 Claude Code v2.1.236 或更新版本。

以下範例告訴分類器查詢輸出的來源：

```json theme={null}
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "classifierContext": "This query ran against the staging database, not production."
  }
}
```

分類器對該註記的重視程度，取決於您在何處設定 hook：

* **在 Claude Code 中設定的 hook**：對於來自設定檔、外掛、skill 與 agent frontmatter 的 hook，分類器會將註記視為未經驗證、由應用程式提供的上下文。註記永遠無法確立使用者意圖；若註記聲稱您核准或要求了某件事，分類器會將該聲明與您在對話中的訊息進行比對
* **程序內的 Agent SDK 回呼**：當嵌入 Claude Code 的應用程式將 hook 註冊為 [TypeScript SDK 回呼](https://code.claude.com/docs/zh-TW/agent-sdk/hooks.md)，並在即時工作階段期間回傳註記時，分類器可能會將註記中轉述的使用者陳述視為使用者意圖。此類陳述可以滿足分類器原本會接受您所傳送訊息作為依據的同意要求，但永遠無法解除您自己的訊息也無法解除的封鎖。工作階段恢復後，Claude Code 會將還原的註記視為未經驗證的上下文。當兩類 hook 都對同一個呼叫進行註記時，分類器會將合併後的註記視為未經驗證

Claude Code 在傳遞註記時會套用以下限制：

* **長度**：Claude Code 將單一工具呼叫的註記上限設為 2,000 個字元，並截斷其餘部分。此上限由回應該呼叫的所有 hook 共用
* **僅限同步回應**：Claude Code 會忽略[在背景執行](#run-hooks-in-the-background)之 hook 回應中的此欄位，因為該回應會在 Claude Code 記錄工具結果之後才抵達
* **分類器不記錄的呼叫**：分類器的逐字稿會省略唯讀查詢，例如檔案讀取與搜尋。附加在這些呼叫上的註記會被 Claude Code 捨棄
* **與重寫的互動**：當註記描述的是您以 `updatedToolOutput` 取代的輸出時，請在同一個 hook 回應中同時回傳這兩個欄位。若該重寫遭拒或被其他 hook 的重寫取代，Claude Code 會捨棄該註記。若您回傳註記時未進行重寫，即使有其他 hook 重寫了輸出，Claude Code 仍會傳遞該註記

> [!WARNING]
>
> 分類器會將您放入 `classifierContext` 的內容視為來自承載工作階段之應用程式的資訊，因此請勿將不受信任的工具輸出或第三方文字複製到其中。請將註記限縮為關於此單一呼叫的簡短陳述，例如其來源的事實或使用者對其的陳述；請勿使用此欄位傳遞不相關的訊息或一連串事件。

### PostToolUseFailure

在已開始執行的工具失敗時執行：工具擲出錯誤，或 MCP 工具回傳錯誤結果。可用於記錄失敗、傳送警示，或向 Claude 提供修正回饋。

依工具名稱比對，值與 PreToolUse 相同。

> [!NOTE]
>
> 此事件不會針對執行前就被拒絕的工具呼叫觸發：未知的工具名稱、未通過 schema 或工具專屬驗證的輸入，或權限拒絕。驗證拒絕會以 `tool_use_error` 結果回傳，且發生在 hook 執行之前，因此既不會觸發 `PreToolUse`，也不會觸發 `PostToolUseFailure`。權限拒絕會觸發 `PreToolUse`，但不會觸發此事件；請參閱 [PermissionDenied](#permissiondenied)。

#### PostToolUseFailure 輸入

PostToolUseFailure hook 會接收與 PostToolUse 相同的 `tool_name` 與 `tool_input` 欄位，並以頂層欄位提供錯誤資訊。對於 MCP 工具，它們也會接收 [`mcp_server`](#pretooluse-input) 物件。例如，失敗的 `npm test` 命令可能會傳遞：

```json theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "PostToolUseFailure",
  "tool_name": "Bash",
  "tool_input": {
    "command": "npm test",
    "description": "Run test suite"
  },
  "tool_use_id": "toolu_01ABC123...",
  "error": "Exit code 1\nError: Cannot find module 'express'",
  "is_interrupt": false,
  "duration_ms": 4187
}
```

| 欄位 | 說明 |
| :- | :- |
| `error` | 描述發生何種錯誤的字串。格式取決於失敗的工具 |
| `is_interrupt` | 選用的布林值。當失敗是以中止形式抵達 Claude Code，而非工具所回報的錯誤時為 true。取消正在執行的工具不會觸發此 hook；工具結果會改為攜帶中斷訊息 |
| `duration_ms` | 選用。工具執行時間（毫秒）。不包含花在權限提示與 PreToolUse hook 上的時間 |

`error` 字串通常與 Claude 收到的失敗工具結果文字相同。其格式因工具與失敗情況而異。請讓您的 hook 以 `tool_name`、`is_interrupt` 以及 `Exit code N` 第一行為判斷依據；將字串的其餘部分視為顯示文字，而非穩定的格式。

* 對於 Bash 與 PowerShell，已執行並結束的命令會產生第一行 `Exit code N`，接著是命令所產生的任何輸出，以單一區塊呈現，stdout 與 stderr 交錯
* 當 Claude Code 無法啟動 shell 程序本身時，payload 也可能只攜帶沒有退出碼行的單純失敗訊息
* Claude Code 會以 `... [N characters truncated] ...` 標記為中心截斷長字串的中間部分，也可能插入自己的行，例如 `Command timed out after 2m 0s`

#### PostToolUseFailure 決策控制

`PostToolUseFailure` hook 可以在工具失敗後向 Claude 提供上下文。除了所有 hook 都可使用的 [JSON 輸出欄位](#json-output)之外，您的 hook 指令碼還可以回傳以下事件專屬欄位：

| 欄位 | 說明 |
| :- | :- |
| `additionalContext` | 與錯誤一併加入 Claude 上下文的字串。請參閱[為 Claude 新增上下文](#add-context-for-claude) |

```json theme={null}
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUseFailure",
    "additionalContext": "Additional information about the failure for Claude"
  }
}
```

### PostToolBatch

在批次中的每個工具呼叫都已完成後執行一次，於 Claude Code 向模型傳送下一個請求之前。`PostToolUse` 會針對每個工具各觸發一次，這表示當 Claude 進行平行工具呼叫時，它會同時觸發。`PostToolBatch` 則會以完整批次精確觸發一次，因此適合用來注入取決於所執行工具集合、而非任何單一工具的上下文。此事件沒有 matcher。

#### PostToolBatch 輸入

除了[通用輸入欄位](#common-input-fields)之外，PostToolBatch hook 還會接收 `tool_calls`，這是一個描述批次中每個工具呼叫的陣列：

```json theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "PostToolBatch",
  "tool_calls": [
    {
      "tool_name": "Read",
      "tool_input": {"file_path": "/.../ledger/accounts.py"},
      "tool_use_id": "toolu_01...",
      "tool_response": "1\tfrom __future__ import annotations\n2\t..."
    },
    {
      "tool_name": "Read",
      "tool_input": {"file_path": "/.../ledger/transactions.py"},
      "tool_use_id": "toolu_02...",
      "tool_response": "1\tfrom __future__ import annotations\n2\t..."
    }
  ]
}
```

`tool_response` 包含模型在對應 `tool_result` 區塊中收到的相同內容。該值是序列化後的字串或內容區塊陣列，與工具輸出的內容完全一致。對於 `Read`，這表示是帶有行號前綴的文字，而非原始檔案內容。回應可能很大，因此請只解析您需要的欄位。

> [!NOTE]
>
> `tool_response` 的結構與 `PostToolUse` 不同。`PostToolUse` 傳遞的是工具的結構化 `Output` 物件，例如 `Write` 的 `{filePath: "...", type: "create"}`；`PostToolBatch` 傳遞的則是模型所看到的序列化 `tool_result` 內容。

#### PostToolBatch 決策控制

`PostToolBatch` hook 可以為 Claude 注入上下文。除了所有 hook 都可使用的 [JSON 輸出欄位](#json-output)之外，您的 hook 指令碼還可以回傳以下事件專屬欄位：

| 欄位 | 說明 |
| :- | :- |
| `additionalContext` | 在下一次模型呼叫前注入一次的上下文字串。關於傳遞細節、應放入的內容，以及恢復的工作階段如何處理過去的值，請參閱[為 Claude 新增上下文](#add-context-for-claude) |

```json theme={null}
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolBatch",
    "additionalContext": "These files are part of the ledger module. Run pytest before marking the task complete."
  }
}
```

回傳 `decision: "block"` 或 `continue: false` 會在下一次模型呼叫前停止代理式迴圈。封鎖訊息來自 JSON 的 `reason` 或 `stopReason`，或在退出碼 2 時來自 stderr。您會在逐字稿中看到它以警告形式呈現，且它會保留在對話中，因此 Claude 會在對話繼續時看到它。

### PermissionDenied

在[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)拒絕工具呼叫時執行，包括在沒有分類器判定的情況下拒絕，原因是[獨立於自動模式之外的安全檢查拒絕了分類器本身的請求](https://code.claude.com/docs/zh-TW/errors.md#auto-mode-cannot-determine-the-safety-of-an-action)，或其回應無法解析。此 hook 只會在自動模式下觸發：當您手動拒絕權限對話框、`PreToolUse` hook 封鎖呼叫，或 `deny` 規則相符時，都不會執行。可用於記錄拒絕、調整設定，或告知模型它可以重試該工具呼叫。

依工具名稱比對，值與 PreToolUse 相同。

#### PermissionDenied 輸入

除了[通用輸入欄位](#common-input-fields)之外，PermissionDenied hook 還會接收 `tool_name`、`tool_input`、`tool_use_id` 與 `reason`。對於 MCP 工具，它們也會接收 [`mcp_server`](#pretooluse-input) 物件。

```json theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "auto",
  "hook_event_name": "PermissionDenied",
  "tool_name": "Bash",
  "tool_input": {
    "command": "rm -rf /tmp/build",
    "description": "Clean build directory"
  },
  "tool_use_id": "toolu_01ABC123...",
  "reason": "[Irreversible Local Destruction]"
}
```

| 欄位 | 說明 |
| :- | :- |
| `reason` | 拒絕原因。對於分類器判定，在大多數工作階段中，它會以方括號標示相符的規則，例如 `[Data Exfiltration]`；其他形式請參閱[審查拒絕](https://code.claude.com/docs/zh-TW/auto-mode-config.md#review-denials)。對於[無判定的拒絕](#permissiondenied-decision-control)，它以 `Auto mode could not evaluate this action and is blocking it for safety` 開頭。對於因分類器模型無法使用而產生的拒絕，它是固定文字 `Classifier unavailable` |

#### PermissionDenied 決策控制

PermissionDenied hook 可以告知模型它可以重試被拒絕的工具呼叫。回傳一個 `hookSpecificOutput.retry` 設為 `true` 的 JSON 物件：

```json theme={null}
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionDenied",
    "retry": true
  }
}
```

當 `retry` 為 `true` 時，Claude Code 會在對話中加入一則訊息，告知模型它可以重試該工具呼叫。Claude Code 本身不會撤銷拒絕。若您的 hook 未回傳 JSON，或回傳 `retry: false`，拒絕維持有效，模型會收到原始的拒絕訊息。

當分類器[未對該動作產生判定](https://code.claude.com/docs/zh-TW/errors.md#auto-mode-cannot-determine-the-safety-of-an-action)時，Claude Code 會忽略 `retry: true`：其回應無法解析，或獨立於自動模式之外的安全檢查拒絕了分類器本身的請求。對於這些拒絕，Claude Code 已在拒絕訊息中告知模型應稍後重試或繼續其他工作。

### Notification

在 Claude Code 傳送通知時執行。依通知類型比對。省略 matcher 即可針對所有通知類型執行 hook。

即使關閉了桌面通知，您仍會收到這些 hook 事件：`preferredNotifChannel` 設定（包括 `notifications_disabled`）只會改變您接收提醒的方式，而不會影響您的 hook 是否執行。

| Matcher | 觸發時機 |
| :- | :- |
| `permission_prompt` | Claude 需要您核准工具使用或沙箱化命令的[網路請求](https://code.claude.com/docs/zh-TW/sandboxing.md#network-isolation)，且提示已等待約六秒 |
| `idle_prompt` | Claude 約在 60 秒前完成回應，且您之後未曾輸入 |
| `auth_success` | 身分驗證完成 |
| `elicitation_dialog` | MCP 伺服器開啟 elicitation 表單，且您約六秒未輸入 |
| `elicitation_url_dialog` | MCP 伺服器要求您開啟瀏覽器 URL，且您約六秒未輸入 |
| `elicitation_complete` | MCP 伺服器回報 [URL 模式 elicitation](#elicitation-input) 已完成 |
| `elicitation_response` | MCP elicitation 回應被傳回伺服器 |
| `agent_needs_input` | 在終端機中開啟 [agent 檢視](https://code.claude.com/docs/zh-TW/agent-view.md)時，某個背景工作階段開始等待您的輸入。當終端機工作階段向您顯示 [agent team 隊員的終端機設定問題](https://code.claude.com/docs/zh-TW/agent-teams.md#choose-a-display-mode)，或自動模式關於[分類器請求費用](https://code.claude.com/docs/zh-TW/auto-mode-classifier-billing.md)的通知，且您約六秒未輸入時，也會觸發 |
| `agent_completed` | 背景工作階段完成或失敗。僅在終端機中開啟 [agent 檢視](https://code.claude.com/docs/zh-TW/agent-view.md)時觸發 |
| `quota_auto_resume_fired` | Claude Code 在 claude.ai 用量上限暫停您的任務後繼續執行：在重設時，或在等待期間您於 Claude Code 中所做的某些動作（例如新增用量點數、升級方案或切換模型）使用量再次可用時提前繼續，但有[模型設定例外](https://code.claude.com/docs/zh-TW/interactive-mode.md#wait-for-a-usage-limit-to-reset) |
| `quota_auto_resume_stale` | claude.ai 用量上限在您的電腦休眠超過約 30 分鐘期間重設。Claude Code 會等待您按下 `Enter`，而非繼續執行。若休眠時間較短，它會繼續執行並改為觸發 `quota_auto_resume_fired` |
| `quota_auto_resume_disabled` | Claude Code 結束對 claude.ai 用量上限的等待，且未繼續您的任務：[`autoContinueAtUsageLimit`](https://code.claude.com/docs/zh-TW/settings-reference#autocontinueatusagelimit) 已關閉，或在 Claude Code 自行開始的等待期間重設時間延後超過 24 小時、繼續的任務持續觸及上限，或繼續執行在抵達模型之前遭到封鎖。當您按下 `Esc` 或 `Ctrl+C`，或選擇 **Don't continue automatically** 時不會觸發 |
| `plugin_notification` | [mod](https://code.claude.com/docs/zh-TW/plugins/mods/api.md#show-something-without-starting-a-turn) 以 `$.ui.notify` 發出通知。除非 mod 另行設定，否則 hook 的 `title` 為該 mod 的名稱 |

`quota_auto_resume_fired`、`quota_auto_resume_stale` 與 `quota_auto_resume_disabled` 類型需要 Claude Code v2.1.234 或更新版本。

在終端機工作階段中，針對沙箱化命令網路請求的 `permission_prompt` 需要 Claude Code v2.1.246 或更新版本。

針對隊員終端機設定問題的 `agent_needs_input` 需要 Claude Code v2.1.248 或更新版本。

> [!NOTE]
>
> `permission_prompt`、`idle_prompt`、`elicitation_dialog` 與 `elicitation_url_dialog` 類型與桌面通知共用相同的時機，因此在終端機工作階段中，只有當您看起來不在終端機前時才會看到它們：
>
> * 當您約六秒未輸入時，預期會出現 `permission_prompt`。計時器從權限提示出現時開始，每次按鍵都會使其延後。若要在 Claude 請求使用工具的權限時立即執行 hook，請改用 [PermissionRequest](#permissionrequest)。
> * 在 Claude 完成回應約 60 秒後，預期會出現 `idle_prompt`，但前提是您之後未曾輸入，且沒有背景 agent（例如背景 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md)）仍在執行。Claude Code 在等待 claude.ai 用量上限重設期間不會傳送 `idle_prompt`。當等待自行結束時，會改為觸發其中一個 `quota_auto_resume_*` 類型。
> * 當您約六秒未輸入時，預期會針對 elicitation 表單出現 `elicitation_dialog`，或針對瀏覽器 URL 請求出現 `elicitation_url_dialog`。兩者與 `permission_prompt` 共用相同的六秒門檻：計時器從對話框出現時開始，每次按鍵都會使其延後。
>
> 在另一個對話框顯示於畫面上時抵達的權限請求或 elicitation，仍適用相同的六秒門檻，從請求抵達時開始計時。其通知可能會在請求仍於開啟的對話框後方等待時送達您。

在 Claude Code 將權限請求傳送至 Agent SDK 的 [`canUseTool` 回呼](https://code.claude.com/docs/zh-TW/agent-sdk/user-input)的工作階段中（也就是 Claude Desktop 與 VS Code 擴充功能承載 Claude Code 的方式），Claude Code 對 `permission_prompt` 的計時方式不同：

* 預期會在 Claude 請求權限約六秒後出現 `permission_prompt`。Claude Code 不會因為您輸入而延後它。
* 若您或 [PermissionRequest](#permissionrequest) hook 較早回應，Claude Code 不會執行 `permission_prompt`。
* 將 [`CLAUDE_CODE_DISABLE_PERMISSION_PROMPT_NOTIFY_HOOKS`](https://code.claude.com/docs/zh-TW/env-vars) 設為 `1`，即可在這些工作階段中關閉 `permission_prompt`。

在 v2.1.233 之前，`permission_prompt` 不會在這些工作階段中觸發。

使用不同的 matcher，即可依通知類型執行不同的處理常式。以下設定會在 Claude 需要權限核准時觸發權限專屬的警示指令碼，並在 Claude 閒置時觸發另一個通知：

```json theme={null}
{
  "hooks": {
    "Notification": [
      {
        "matcher": "permission_prompt",
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/permission-alert.sh"
          }
        ]
      },
      {
        "matcher": "idle_prompt",
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/idle-notification.sh"
          }
        ]
      }
    ]
  }
}
```

#### Notification 輸入

除了[通用輸入欄位](#common-input-fields)之外，Notification hook 還會接收包含通知文字的 `message`、選用的 `title`，以及指出觸發類型的 `notification_type`。

```json theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "hook_event_name": "Notification",
  "message": "Claude needs your permission",
  "title": "Permission needed",
  "notification_type": "permission_prompt"
}
```

Notification hook 無法封鎖或修改通知。Claude Code 會捨棄其 `systemMessage` 與 `continue` 欄位，但仍會輸出 [`terminalSequence`](#emit-terminal-notifications)，桌面通知範例正是仰賴此欄位。Notification hook 的用途是產生副作用，例如將通知轉送至外部服務。

### SubagentStart

在 Claude 使用 Agent 工具產生 subagent 時、在 Claude [恢復 subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#resume-subagents) 時，以及每次程序內 [agent team](https://code.claude.com/docs/zh-TW/agent-teams.md) 隊員處理新訊息時執行。支援使用 matcher 依 agent 類型名稱篩選。對於內建 agent，這是 agent 名稱，例如 `general-purpose`、`Explore` 或 `Plan`。對於[自訂 subagent](https://code.claude.com/docs/zh-TW/sub-agents.md)，這是 agent frontmatter 中的 `name` 欄位，而非檔案名稱。

對於由[外掛](https://code.claude.com/docs/zh-TW/plugins/overview.md)提供的 subagent，agent 類型是外掛範圍的識別碼，例如 `my-plugin:reviewer`，而非單純的 frontmatter 名稱。冒號會使外掛範圍的名稱走正規表示式路徑，因此請以 `^` 與 `$` 錨定 matcher 以進行精確比對：`^my-plugin:reviewer$`。

#### SubagentStart 輸入

除了[通用輸入欄位](#common-input-fields)之外，SubagentStart hook 還會接收包含 subagent 唯一識別碼的 `agent_id`，以及包含 matcher 篩選依據之 agent 名稱的 `agent_type`。

```json theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "hook_event_name": "SubagentStart",
  "agent_id": "agent-abc123",
  "agent_type": "Explore"
}
```

SubagentStart hook 無法封鎖 subagent 的建立，但可以將上下文注入 subagent。除了所有 hook 都可使用的 [JSON 輸出欄位](#json-output)之外，您還可以回傳：

| 欄位 | 說明 |
| :- | :- |
| `additionalContext` | 在 subagent 對話開始時、其第一個提示詞之前，加入 subagent 上下文的字串。請參閱[為 Claude 新增上下文](#add-context-for-claude) |

```json theme={null}
{
  "hookSpecificOutput": {
    "hookEventName": "SubagentStart",
    "additionalContext": "Follow security guidelines for this task"
  }
}
```

當 hook 針對同一個 subagent 再次執行時，只有在 subagent 的上下文尚未保有先前執行所注入的副本時，Claude Code 才會注入回傳的上下文。啟動時注入的副本會保留在原處，使 subagent 的[提示快取](https://code.claude.com/docs/zh-TW/prompt-caching.md#subagents-and-the-cache)保持完整。在[自動壓縮](https://code.claude.com/docs/zh-TW/sub-agents.md#auto-compaction)捨棄該副本後，Claude Code 會再次注入下一次執行的上下文。

### SubagentStop

在 Claude Code subagent 完成回應時執行。依 agent 類型比對，值與 SubagentStart 相同。

#### SubagentStop 輸入

除了[通用輸入欄位](#common-input-fields)之外，SubagentStop hook 還會接收 `stop_hook_active`、`agent_id`、`agent_type`、`agent_transcript_path` 與 `last_assistant_message`。`agent_type` 欄位是用於 matcher 篩選的值。`transcript_path` 是主工作階段的逐字稿，而 `agent_transcript_path` 則是儲存在巢狀 `subagents/` 資料夾中的 subagent 自身逐字稿。`last_assistant_message` 欄位包含 subagent 最終回應的文字內容，因此 hook 無需解析逐字稿檔案即可存取。

並非每個 SubagentStop 事件都來自 Claude 所產生的 subagent。Claude Code 也會為其自身的某些功能執行內部 agent，例如[提示詞建議](https://code.claude.com/docs/zh-TW/interactive-mode.md#prompt-suggestions)與 [`/btw` 旁支問題](https://code.claude.com/docs/zh-TW/interactive-mode#side-questions-with-%2Fbtw)，當其中之一完成時，SubagentStop 也會觸發。對於這些事件，`agent_type` 是工作階段本身執行時所使用的 agent 名稱，例如以 [`--agent`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 或 [`agent` 設定](https://code.claude.com/docs/zh-TW/settings-reference#agent)所設定者；若工作階段未使用任何 agent 執行，則為空字串。

指定 agent 類型的 `matcher` 不會比對空的 `agent_type`。matcher 被省略、為 `""` 或 `"*"`，或是可比對空字串之正規表示式的 hook，也會針對 `agent_type` 為空的事件執行。

在 Claude Code v2.1.271 或更新版本中，使用 [`SubagentHandback`](https://code.claude.com/docs/zh-TW/tools-reference) 工具執行的 subagent 會在停止之前透過該工具傳遞其報告。此時 `last_assistant_message` 欄位保存的是 subagent 的結尾文字（若有），而非所傳遞的報告。報告是該呼叫的 `message` 輸入，比對 `SubagentHandback` 的 `PreToolUse` 或 `PostToolUse` hook 會以 `tool_input.message` 接收它。

SubagentStop hook 也會接收 [Stop 輸入](#stop-input)中所述的 `background_tasks` 與 `session_crons` 陣列。這兩個陣列的範圍都是父工作階段，而非 subagent。

```json theme={null}
{
  "session_id": "abc123",
  "transcript_path": "~/.claude/projects/.../abc123.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "SubagentStop",
  "stop_hook_active": false,
  "agent_id": "def456",
  "agent_type": "Explore",
  "agent_transcript_path": "~/.claude/projects/.../abc123/subagents/agent-def456.jsonl",
  "last_assistant_message": "Analysis complete. Found 3 potential issues...",
  "background_tasks": [],
  "session_crons": []
}
```

SubagentStop hook 使用與 [Stop hook](#stop-decision-control) 相同的決策控制格式，包括將 `hookEventName` 設為 `"SubagentStop"` 的 `hookSpecificOutput.additionalContext`，用於提供讓 subagent 繼續執行的非錯誤回饋。回傳帶有 `reason` 的 `decision: "block"` 會讓 subagent 繼續執行，並將 `reason` 作為下一個指令傳遞給 subagent。以退出碼 2 封鎖的 hook 也會以相同方式傳遞其 stderr 訊息。若要在 subagent 回傳後將上下文注入父工作階段，請改為在 `Agent` 工具上使用 [`PostToolUse`](#posttooluse) hook。

### TaskCreated

在透過 `TaskCreate` 工具建立任務時執行。可用於強制執行命名慣例、要求任務說明，或防止建立特定任務。在[沒有 Task 工具的工作階段](https://code.claude.com/docs/zh-TW/tools-reference.md#task-tool-availability)中，此事件不會觸發。

TaskCreated hook 不支援 matcher，每次發生時都會觸發。

#### TaskCreated 輸入

除了[通用輸入欄位](#common-input-fields)之外，TaskCreated hook 還會接收 `task_id`、`task_subject`，以及選用的 `task_description`、`teammate_name` 與 `team_name`。

```json theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "hook_event_name": "TaskCreated",
  "task_id": "task-001",
  "task_subject": "Implement user authentication",
  "task_description": "Add login and signup endpoints",
  "teammate_name": "implementer",
  "team_name": "session-a1b2c3d4"
}
```

| 欄位 | 說明 |
| :- | :- |
| `task_id` | 正在建立之任務的識別碼 |
| `task_subject` | 任務標題 |
| `task_description` | 任務的詳細說明。可能不存在 |
| `teammate_name` | 建立任務之隊員的名稱。可能不存在 |
| `team_name` | 已棄用。衍生自工作階段的團隊名稱；將在未來版本中移除 |
| `agent_id` | 在此事件中，此[通用輸入欄位](#common-input-fields)識別建立任務的 subagent 或[程序內隊員](https://code.claude.com/docs/zh-TW/agent-teams.md#choose-a-display-mode)。可能不存在。需要 Claude Code v2.1.290 或更新版本 |

#### TaskCreated 決策控制

TaskCreated hook 可以使用退出碼 2 或 JSON 決策封鎖建立。無論哪種方式，Claude Code 都會刪除該任務，並將您的訊息作為工具錯誤回傳給 Claude。Claude Code 會忽略此事件的 `continue: false`，Claude 會繼續工作。

* **退出碼 2**：Claude Code 會將 stderr 文字作為訊息回傳。
* **JSON `{"decision": "block", "reason": "..."}`**：Claude Code 會將 `reason` 作為訊息回傳。

以下範例會封鎖主旨不符合必要格式的任務：

```bash theme={null}
#!/bin/bash
INPUT=$(cat)
TASK_SUBJECT=$(echo "$INPUT" | jq -r '.task_subject')

if [[ ! "$TASK_SUBJECT" =~ ^\[TICKET-[0-9]+\] ]]; then
  echo "Task subject must start with a ticket number, e.g. '[TICKET-123] Add feature'" >&2
  exit 2
fi

exit 0
```

### TaskCompleted

在任務被標記為已完成時執行。此事件會在兩種情況下觸發：任何 agent 透過 TaskUpdate 工具明確將任務標記為已完成時，或 [agent team](https://code.claude.com/docs/zh-TW/agent-teams.md) 隊員在仍有進行中任務的情況下結束其回合時。可用於在任務關閉前強制執行完成條件，例如通過測試或 lint 檢查。

TaskCompleted hook 不支援 matcher，每次發生時都會觸發。

#### TaskCompleted 輸入

除了[通用輸入欄位](#common-input-fields)之外，TaskCompleted hook 還會接收 `task_id`、`task_subject`，以及選用的 `task_description`、`teammate_name` 與 `team_name`。

```json theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "TaskCompleted",
  "task_id": "task-001",
  "task_subject": "Implement user authentication",
  "task_description": "Add login and signup endpoints",
  "teammate_name": "implementer",
  "team_name": "session-a1b2c3d4"
}
```

| 欄位 | 說明 |
| :- | :- |
| `task_id` | 正在完成之任務的識別碼 |
| `task_subject` | 任務標題 |
| `task_description` | 任務的詳細說明。可能不存在 |
| `teammate_name` | 完成任務之隊員的名稱。可能不存在 |
| `team_name` | 已棄用。衍生自工作階段的團隊名稱；將在未來版本中移除 |
| `agent_id` | 在此事件中，此[通用輸入欄位](#common-input-fields)識別完成任務的 subagent 或[程序內隊員](https://code.claude.com/docs/zh-TW/agent-teams.md#choose-a-display-mode)。可能不存在。需要 Claude Code v2.1.290 或更新版本 |

#### TaskCompleted 決策控制

TaskCompleted hook 支援兩種控制任務完成的方式：

* **退出碼 2**：任務不會被標記為已完成，且 stderr 訊息會作為回饋傳回給模型。
* **JSON `{"continue": false, "stopReason": "..."}`**：當事件是由隊員結束其回合所觸發時，會完全停止該隊員，與 `Stop` hook 的行為一致。`stopReason` 會顯示給使用者。當事件是由 `TaskUpdate` 工具觸發時，Claude Code 會忽略 `continue: false`；退出碼 2 仍會封鎖完成。

以下範例會執行測試，並在測試失敗時封鎖任務完成：

```bash theme={null}
#!/bin/bash
INPUT=$(cat)
TASK_SUBJECT=$(echo "$INPUT" | jq -r '.task_subject')

# Run the test suite
if ! npm test 2>&1; then
  echo "Tests not passing. Fix failing tests before completing: $TASK_SUBJECT" >&2
  exit 2
fi

exit 0
```

### Stop

在主要 Claude Code agent 完成回應時執行。若停止是由使用者中斷所造成，則不會執行。API 錯誤會改為觸發
[StopFailure](#stopfailure)。

> [!TIP]
>
> [`/goal`](https://code.claude.com/docs/zh-TW/goal) 命令是工作階段範圍、以提示詞為基礎之 Stop hook 的內建捷徑。當您希望 Claude 持續朝某個條件努力，又不想撰寫 hook 設定時，請使用它。

#### Stop 輸入

除了[通用輸入欄位](#common-input-fields)之外，Stop hook 還會接收 `stop_hook_active`、`last_assistant_message`、`background_tasks` 與 `session_crons`。當 Claude Code 已因 stop hook 而繼續執行時，`stop_hook_active` 欄位為 `true`。請檢查此值或處理逐字稿，以避免因永遠無法解決的條件而持續封鎖。

Claude Code 套用 8 次連續繼續的上限：在 stop hook 連續讓回合繼續八次之後，Claude Code 會覆寫下一次封鎖並結束回合。每當 Claude 呼叫工具時，連續繼續的次數就會重設。若要提高上限，請設定 [`CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`](https://code.claude.com/docs/zh-TW/env-vars)。

`last_assistant_message` 欄位包含 Claude 最終回應的文字內容，因此 hook 無需解析逐字稿檔案即可存取。對於針對剛完成之回合採取動作的 hook（例如朗讀或通知 hook），請使用此欄位，而非讀取 `transcript_path`：在所有版本中，逐字稿檔案並不保證在 Stop 時已包含最終訊息。

`background_tasks` 與 `session_crons` 陣列讓 hook 能夠區分「工作階段已完成」與「工作階段已暫停，等待背景工作將其喚醒」。當任務登錄可存取時，這兩個陣列都會存在；當沒有任何進行中或已排程的項目時，它們為空。

`background_tasks` 中的每個項目描述一個進行中的任務，並使用以下欄位：

| 欄位 | 說明 |
| :- | :- |
| `id` | 任務識別碼 |
| `type` | 易於理解的任務類型標籤，例如 `shell`、`subagent`、`monitor`、`workflow`、`teammate`、`cloud session` 或 `MCP task`。每個標籤識別建立該任務的 Claude Code 功能。對於無法辨識的類型，會退回使用原始的區別值 |
| `status` | 目前的任務狀態 |
| `description` | 自由文字說明，上限為 1000 個字元，截斷時會在字串內加上 `… [+N chars]` 標記 |
| `command` | shell 命令列，上限為 1000 個字元。僅存在於 `shell` 任務 |
| `agent_type` | subagent 類型名稱。僅存在於 `subagent` 任務 |
| `server` | MCP 伺服器名稱。僅存在於 `monitor` 與 `MCP task` 任務 |
| `tool` | MCP 工具名稱。僅存在於 `monitor` 與 `MCP task` 任務 |
| `name` | 工作流程名稱。僅存在於 `workflow` 任務 |

`session_crons` 中的每個項目描述一個工作階段範圍的排程喚醒，來源為 `CronCreate`、`ScheduleWakeup` 與 `/loop`：

| 欄位 | 說明 |
| :- | :- |
| `id` | Cron 任務識別碼 |
| `schedule` | Cron 運算式，例如 `0 9 * * 1-5` |
| `recurring` | 對於排程僅編碼單一觸發時間的一次性喚醒為 `false`，對於每次相符時都會重新觸發的任務為 `true` |
| `prompt` | cron 觸發時提交的提示詞，上限為 1000 個字元，並使用相同的 `… [+N chars]` 標記 |

以下範例顯示一個包含一個進行中 shell 任務與一個週期性 cron 的 Stop 輸入：

```json theme={null}
{
  "session_id": "abc123",
  "transcript_path": "~/.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "Stop",
  "stop_hook_active": true,
  "last_assistant_message": "I've completed the refactoring. Here's a summary...",
  "background_tasks": [
    {
      "id": "task-001",
      "type": "shell",
      "status": "running",
      "description": "tail logs",
      "command": "tail -f /var/log/syslog"
    }
  ],
  "session_crons": [
    {
      "id": "cron-001",
      "schedule": "0 9 * * 1-5",
      "recurring": true,
      "prompt": "check the build"
    }
  ]
}
```

#### Stop 決策控制

`Stop` 與 `SubagentStop` hook 可以控制 Claude 是否繼續。除了所有 hook 都可使用的 [JSON 輸出欄位](#json-output)之外，您的 hook 指令碼還可以回傳以下事件專屬欄位：

| 欄位 | 說明 |
| :- | :- |
| `decision` | `"block"` 會阻止 Claude 停止。省略則允許 Claude 停止 |
| `reason` | 當 `decision` 為 `"block"` 時為必要欄位。告訴 Claude 為何應該繼續 |
| `hookSpecificOutput.additionalContext` | 給 Claude 的非錯誤回饋。對話會繼續，讓 Claude 可據以行動，但與 `decision: "block"` 不同，它在逐字稿中會顯示為 hook 回饋，而非 hook 錯誤 |

以退出碼 2 封鎖的 hook 與 `reason` 的路由方式相同：Claude 會將 stderr 訊息作為其應繼續的原因說明。

```json theme={null}
{
  "decision": "block",
  "reason": "Must be provided when Claude is blocked from stopping"
}
```

當 hook 依設計運作並為 Claude 提供指引時（例如「完成前請執行測試套件」），請使用 `additionalContext`。它會透過與 `decision: "block"` 相同的迴圈保護機制讓對話繼續，也就是 `stop_hook_active` 輸入與 8 次連續繼續的上限，但逐字稿會將其標記為 `Stop hook feedback`，且不會顯示 hook 錯誤通知：

```json theme={null}
{
  "hookSpecificOutput": {
    "hookEventName": "Stop",
    "additionalContext": "Please run the test suite before finishing"
  }
}
```

### StopFailure

當回合因 API 錯誤而結束時，取代 [Stop](#stop) 執行。除了 [`terminalSequence`](#emit-terminal-notifications) 之外，Claude Code 會忽略此 hook 的輸出與退出碼。當 Claude 因速率限制、身分驗證問題或其他 API 錯誤而無法完成回應時，可用於記錄失敗、傳送警示或採取復原動作。

#### StopFailure 輸入

除了[通用輸入欄位](#common-input-fields)之外，StopFailure hook 還會接收 `error`、選用的 `error_details`，以及選用的 `last_assistant_message`。`error` 欄位識別錯誤類型，並用於 matcher 篩選。

| 欄位 | 說明 |
| :- | :- |
| `error` | 錯誤類型：`rate_limit`、`overloaded`、`authentication_failed`、`oauth_org_not_allowed`、`account_on_hold`、`billing_error`、`invalid_request`、`model_not_found`、`server_error`、`max_output_tokens`、`cloud_credential_error` 或 `unknown` |
| `error_details` | 關於錯誤的其他細節（若有） |
| `last_assistant_message` | 對話中顯示的已呈現錯誤文字。與 `Stop` 和 `SubagentStop` 中此欄位保存 Claude 的對話輸出不同，對於 `StopFailure`，它包含 API 錯誤字串本身，例如 `"API Error: Rate limit reached"` |

```json theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "hook_event_name": "StopFailure",
  "error": "rate_limit",
  "error_details": "429 Too Many Requests",
  "last_assistant_message": "API Error: Rate limit reached"
}
```

StopFailure hook 沒有決策控制。它們僅用於通知與記錄目的。

### TeammateIdle

在 [agent team](https://code.claude.com/docs/zh-TW/agent-teams.md) 隊員結束其回合、即將進入閒置時執行。可用於在隊員停止工作前強制執行品質關卡，例如要求通過 lint 檢查或確認輸出檔案存在。

TeammateIdle hook 不支援 matcher，每次發生時都會觸發。

#### TeammateIdle 輸入

除了[通用輸入欄位](#common-input-fields)之外，TeammateIdle hook 還會接收 `teammate_name` 與 `team_name`。

```json theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "TeammateIdle",
  "teammate_name": "researcher",
  "team_name": "session-a1b2c3d4"
}
```

| 欄位 | 說明 |
| :- | :- |
| `teammate_name` | 即將進入閒置之隊員的名稱 |
| `team_name` | 已棄用。衍生自工作階段的團隊名稱；將在未來版本中移除 |
| `agent_id` | 在此事件中，此[通用輸入欄位](#common-input-fields)識別即將進入閒置的[程序內隊員](https://code.claude.com/docs/zh-TW/agent-teams.md#choose-a-display-mode)。可能不存在。需要 Claude Code v2.1.290 或更新版本 |

#### TeammateIdle 決策控制

TeammateIdle hook 支援兩種控制隊員行為的方式：

* **退出碼 2**：隊員會接收 stderr 訊息作為回饋，並繼續工作而非進入閒置。
* **JSON `{"continue": false, "stopReason": "..."}`**：完全停止該隊員，與 `Stop` hook 的行為一致。`stopReason` 會顯示給使用者。

以下範例會在允許隊員進入閒置之前，檢查建置產物是否存在：

```bash theme={null}
#!/bin/bash

if [ ! -f "./dist/output.js" ]; then
  echo "Build artifact missing. Run the build before stopping." >&2
  exit 2
fi

exit 0
```

### ConfigChange

在工作階段期間設定檔變更時執行。可用於稽核設定變更、強制執行安全政策，或封鎖對設定檔的未經授權修改。

當設定檔、受管政策檔案或 skill 檔案變更時，Claude Code 會執行 ConfigChange hook。對於受管政策，只有在 `managed-settings.json` 或 `managed-settings.d/` 中的檔案變更時才會執行。它會套用[伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)以及 macOS 受管偏好設定或 Windows 登錄政策的變更，但不會執行這些 hook。在啟用 [`wslInheritsWindowsSettings`](https://code.claude.com/docs/zh-TW/settings-reference#wslinheritswindowssettings) 的 WSL 上，它也會在政策輪詢時套用已變更的 Windows 端受管設定檔，而不執行這些 hook。

matcher 依設定來源進行篩選：

| Matcher | 觸發時機 |
| :- | :- |
| `user_settings` | `~/.claude/settings.json` 變更 |
| `project_settings` | `.claude/settings.json` 變更 |
| `local_settings` | `.claude/settings.local.json` 變更 |
| `policy_settings` | `managed-settings.json` 或 `managed-settings.d/` 中的檔案變更 |
| `skills` | `.claude/skills/` 中的 skill 檔案變更 |

以下範例會記錄所有設定變更以進行安全稽核：

```json theme={null}
{
  "hooks": {
    "ConfigChange": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/audit-config-change.sh",
            "args": []
          }
        ]
      }
    ]
  }
}
```

#### ConfigChange 輸入

除了[通用輸入欄位](#common-input-fields)之外，ConfigChange hook 還會接收 `source` 以及選用的 `file_path`。`source` 欄位指出變更的設定類型，而 `file_path` 提供被修改之特定檔案的路徑。

```json theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "hook_event_name": "ConfigChange",
  "source": "project_settings",
  "file_path": "/Users/.../my-project/.claude/settings.json"
}
```

#### ConfigChange 決策控制

ConfigChange hook 可以封鎖設定變更使其不生效。使用退出碼 2 或 JSON `decision` 即可阻止變更。遭封鎖時，新設定不會套用至正在執行的工作階段。

| 欄位 | 說明 |
| :- | :- |
| `decision` | `"block"` 會阻止套用設定變更。省略則允許變更 |
| `reason` | 會被接受，但永遠不會顯示 |

```json theme={null}
{
  "decision": "block",
  "reason": "Configuration changes to project settings require admin approval"
}
```

`policy_settings` 變更無法被封鎖。當機器上的受管設定檔變更時，hook 仍會針對 `policy_settings` 來源觸發，因此您可以用它們記錄這些編輯，但任何封鎖決策都會被忽略。這可確保企業受管設定一律生效。當[伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)抵達或重新整理時，Claude Code 不會執行 `ConfigChange` hook。

Claude Code 會依據 ConfigChange hook JSON 輸出中的封鎖決策採取行動，並捨棄 `systemMessage` 與 `continue`。無論您是以 `reason` 封鎖，還是以退出碼 2 搭配 stderr 封鎖，被封鎖的變更都不會向您或 Claude 顯示任何訊息。Claude Code 只會在除錯日誌中寫入一行。

### CwdChanged

當主對話中的 shell 命令變更工作目錄時執行，例如 Claude 執行 `cd` 命令時。可用於對目錄變更做出反應：重新載入環境變數、啟用專案專屬的工具鏈，或自動執行設定指令碼。可與 [FileChanged](#filechanged) 搭配，用於 [direnv](https://direnv.net/) 等管理各目錄環境的工具。

CwdChanged hook 可以存取 [`CLAUDE_ENV_FILE`](#persist-environment-variables)。若您的 hook 將變數寫入該檔案，這些變數會保留至後續的 Bash 命令中，直到下一個 CwdChanged 事件時由 Claude Code 清除。

CwdChanged 不支援 matcher，每次發生時都會觸發。

#### CwdChanged 輸入

除了[通用輸入欄位](#common-input-fields)之外，CwdChanged hook 還會接收 `old_cwd` 與 `new_cwd`。

```json theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../transcript.jsonl",
  "cwd": "/Users/my-project/src",
  "hook_event_name": "CwdChanged",
  "old_cwd": "/Users/my-project",
  "new_cwd": "/Users/my-project/src"
}
```

#### CwdChanged 輸出

除了所有 hook 都可使用的 [JSON 輸出欄位](#json-output)之外，CwdChanged hook 還可以回傳 `watchPaths`，以動態設定 [FileChanged](#filechanged) 要監看的檔案路徑：

| 欄位 | 說明 |
| :- | :- |
| `watchPaths` | 絕對路徑的陣列。取代目前的動態監看清單。來自您 `matcher` 設定的路徑一律會被監看。回傳空陣列會清除動態清單，這在進入新目錄時很常見 |

CwdChanged hook 沒有決策控制。它們無法封鎖目錄變更。

Claude Code 會從其 JSON 輸出中讀取 `watchPaths` 與 `systemMessage`，並捨棄 `continue`。在互動式工作階段中，它會將 `systemMessage` 顯示為簡短的終端機通知。該訊息不會進入 SDK 訊息串流。

### DirectoryAdded

在您於工作階段中途使用 `/add-dir` 命令新增工作目錄後，或在 SDK 用戶端以 `register_repo_root` 控制請求新增工作目錄後執行。可用於準備新加入的儲存庫，例如安裝其相依套件。

在以下情況下，Claude Code 不會觸發此事件：

* 您透過 `--add-dir` 啟動旗標傳入目錄；[SessionStart](#sessionstart) 涵蓋這些目錄
* 您在 `/permissions` 的 Workspace 分頁上新增目錄
* 您新增的目錄已經是工作目錄或位於工作目錄之內

Claude Code 會在重新整理沙箱與權限狀態之後觸發 DirectoryAdded，因此當您的 hook 執行時，沙箱化的工具已能看到新目錄。hook 命令本身則在沙箱外執行。

Claude Code 不會等待 hook：新增動作會立即完成，而 hook 會在背景以預設的 600 秒逾時執行。

matcher 依目錄的新增方式進行篩選：

| Matcher | 觸發時機 |
| :- | :- |
| `slash_command` | 您使用 `/add-dir` 新增目錄 |
| `register_repo_root` | SDK 用戶端以 `register_repo_root` 控制請求新增目錄 |

#### DirectoryAdded 輸入

除了[通用輸入欄位](#common-input-fields)之外，DirectoryAdded hook 還會接收 `directory` 與 `source`。

| 欄位 | 說明 |
| :- | :- |
| `directory` | 所新增目錄的絕對路徑 |
| `source` | 目錄的新增方式，`/add-dir` 為 `"slash_command"`，SDK 控制請求為 `"register_repo_root"` |

```json theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../transcript.jsonl",
  "cwd": "/Users/my-project",
  "hook_event_name": "DirectoryAdded",
  "directory": "/Users/my-other-repo",
  "source": "slash_command"
}
```

DirectoryAdded hook 沒有決策控制。它們無法封鎖新增動作，因為在 hook 執行時新增已經完成。Claude Code 會捨棄其 JSON 輸出中的 `continue` 欄位，並依來源以不同方式呈現其餘部分：

* `slash_command`：Claude Code 會在下一個對話回合將 hook 的 `systemMessage` 作為上下文傳遞給 Claude，而不是顯示給您。失敗 hook 的數量會顯示在逐字稿中。完整的失敗輸出會寫入除錯日誌
* `register_repo_root`：Claude Code 只會將 `systemMessage` 輸出與失敗輸出寫入除錯日誌

### FileChanged

在受監看的檔案於磁碟上發生變更時執行。Claude Code 透過檔案系統監看器偵測變更，而非檢查工具呼叫，因此無論是什麼變更了該檔案，它都會執行 hook：`Edit` 或 `Write` 工具呼叫、Claude 以 `Bash` 執行的指令碼，或完全在 Claude Code 之外的程序。常見的用途是在專案設定檔變更時重新載入環境變數。

此事件的 `matcher` 具有兩種作用：

* **建立監看清單**：該值會以 `|` 分割，每個片段都會被註冊為工作目錄中的字面檔名，因此 `".envrc|.env"` 會精確監看這兩個檔案。正規表示式在此沒有用處：像 `^\.env` 這樣的值會監看一個字面名稱為 `^\.env` 的檔案。
* **篩選要執行的 hook**：當受監看的檔案變更時，同一個值會依據標準的 [matcher 規則](#matcher-patterns)，針對變更檔案的基本名稱篩選要執行哪些 hook 群組。

此範例會在任何變更之後（包括 `Bash` 命令或外部指令碼改寫該檔案）正規化 `data.csv` 中的行尾字元：

```json theme={null}
{
  "hooks": {
    "FileChanged": [
      {
        "matcher": "data.csv",
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/normalize-line-endings.sh"
          }
        ]
      }
    ]
  }
}
```

此 hook 會從 stdin 上 [JSON 輸入](#filechanged-input)的 `file_path` 欄位讀取變更檔案的絕對路徑。它的 `grep` 防護條件所檢查的，正是 `perl` 所移除的內容，也就是行尾的 CR，因此正規化之後的那次執行會直接結束而不觸碰該檔案。較寬鬆的防護條件會造成無限迴圈，因為即使 `perl -i` 沒有取代任何內容也會改寫檔案，而 Claude Code 會在每次改寫後再次執行此 hook。請將此指令碼儲存於 `/path/to/normalize-line-endings.sh` 並設為可執行：

```bash theme={null}
#!/bin/bash
FILE=$(jq -r .file_path)
if grep -q $'\r$' "$FILE"; then
  perl -pi -e 's/\r$//' "$FILE"
fi
```

若要確認 hook 是否正常運作，請要求 Claude 以 `Bash` 命令在 `data.csv` 附加一行 CRLF。Claude Code 會執行此 hook，檔案最終會使用 LF 行尾。

若要監看無法事先指名的檔案，請從 hook 傳回 [`watchPaths`](#filechanged-output) 以動態更新監看清單。Claude Code 只有在有東西指名要監看的檔案時才會啟動監看器，因此請以一個 matcher 至少指名一個檔案的 FileChanged 群組，或以傳回 `watchPaths` 的 [SessionStart](#sessionstart-decision-control) 或 [CwdChanged](#cwdchanged) hook 來初始化清單。當受監看的檔案變更時，matcher 仍會篩選要執行哪些 hook 群組，因此請讓處理動態路徑的群組省略 matcher，這樣它會符合每個受監看的檔案，且不會在監看清單中新增任何項目。`"*"` matcher 同樣會符合每個檔案，但 Claude Code 會像處理其他值一樣將其註冊到監看清單中，成為一個字面名稱為 `*` 的檔案。

FileChanged hook 可以存取 [`CLAUDE_ENV_FILE`](#persist-environment-variables)。寫入該檔案的變數會持續套用到後續的 Bash 命令，直到下一次 [CwdChanged](#cwdchanged) 事件發生時由 Claude Code 清除為止。

#### FileChanged 輸入

除了[通用輸入欄位](#common-input-fields)之外，FileChanged hook 還會收到 `file_path` 與 `event`。

| 欄位 | 說明 |
| :- | :- |
| `file_path` | 變更檔案的絕對路徑 |
| `event` | 發生的情況：`"change"` 表示檔案已修改，`"add"` 表示檔案已建立，`"unlink"` 表示檔案已刪除 |

```json theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../transcript.jsonl",
  "cwd": "/Users/my-project",
  "hook_event_name": "FileChanged",
  "file_path": "/Users/my-project/.envrc",
  "event": "change"
}
```

#### FileChanged 輸出

除了所有 hook 皆可使用的 [JSON 輸出欄位](#json-output)之外，FileChanged hook 還可以傳回 `watchPaths`，以動態更新要監看的檔案路徑：

| 欄位 | 說明 |
| :- | :- |
| `watchPaths` | 絕對路徑的陣列。會取代目前的動態監看清單。來自您 `matcher` 設定的路徑一律會被監看。當您的 hook 指令碼根據變更的檔案發現其他需要監看的檔案時，請使用此欄位 |

FileChanged hook 沒有決策控制。它們無法阻止檔案變更發生。

Claude Code 會從其 JSON 輸出讀取 `watchPaths` 與 `systemMessage`，並捨棄 `continue`。在互動式工作階段中，它會將 `systemMessage` 顯示為簡短的終端機通知。該訊息不會傳送到 SDK 訊息串流。

### WorktreeCreate

在 Claude Code 建立 worktree 時執行，例如以下情況：

* 您以 `claude --worktree` 啟動工作階段
* Claude 在工作階段期間建立 worktree，並以 [`EnterWorktree`](https://code.claude.com/docs/zh-TW/tools-reference) 工具切換進入
* [subagent 使用 `isolation: "worktree"`](https://code.claude.com/docs/zh-TW/sub-agents#choose-the-subagent-scope)
* [工作流程](https://code.claude.com/docs/zh-TW/workflows.md#migrate-many-files-in-parallel)在自己的 worktree 中執行 agent
* Claude Code 將[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md#how-file-edits-are-isolated)隔離在其自己的 worktree 中
* `worktree` 模式下的 [`claude remote-control`](https://code.claude.com/docs/zh-TW/remote-control#start-a-remote-control-session) 在自己的 worktree 中啟動工作階段

WorktreeCreate hook 不會針對 Claude 透過 Bash 新增的 worktree 執行，而外掛的 hook 也不會針對您以 `--worktree` 與 [`--tmux`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 啟動時所建立的 worktree 執行：

* **透過 Bash 執行 `git worktree add`**：若要檢查或封鎖該命令，請新增一個使用 `Bash` matcher 的 [`PreToolUse`](#pretooluse) hook。
* **`--worktree` 搭配 `--tmux`**：Claude Code 會在載入外掛之前建立 worktree，因此來自外掛的 WorktreeCreate hook 不會執行。若要讓您的 hook 在同時使用兩個旗標時執行，請改為在[設定檔](#configuration)中定義它。在 v2.1.300 之前，外掛的 WorktreeCreate hook 在僅使用 `--worktree` 時也不會執行。

根據預設，Claude Code 會使用 `git worktree` 建立隔離的工作副本。設定 WorktreeCreate hook 會取代該預設的 git 行為，讓您可以使用其他版本控制系統，例如 SVN、Perforce 或 Mercurial。

由於此 hook 會完全取代預設行為，因此不會處理 [`.worktreeinclude`](https://code.claude.com/docs/zh-TW/worktrees#copy-gitignored-files-into-worktrees)。如果您需要將 `.env` 等本機設定檔複製到新的 worktree，請在 hook 指令碼中完成。

此 hook 必須傳回所建立之 worktree 目錄的路徑。Claude Code 會將此路徑用作隔離工作階段的工作目錄。關於各 hook 類型如何傳回路徑，請參閱 [WorktreeCreate 輸出](#worktreecreate-output)。

Claude Code 會依據 hook 是否成功以及傳回的路徑採取動作，並捨棄 `systemMessage` 與 `continue`。

此範例會建立 SVN 工作副本，並印出路徑供 Claude Code 使用。請將儲存庫 URL 替換為您自己的：

```json theme={null}
{
  "hooks": {
    "WorktreeCreate": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash -c 'NAME=$(jq -r .name); DIR=\"$HOME/.claude/worktrees/$NAME\"; svn checkout https://svn.example.com/repo/trunk \"$DIR\" >&2 && echo \"$DIR\"'"
          }
        ]
      }
    ]
  }
}
```

此 hook 會從 stdin 上的 JSON 輸入讀取 worktree 的 `name`，將全新副本簽出到新目錄，並印出該目錄路徑。最後一行的 `echo` 就是 Claude Code 讀取為 worktree 路徑的內容。請將其他任何輸出重新導向至 stderr，以免干擾該路徑。

#### WorktreeCreate 輸入

除了[通用輸入欄位](#common-input-fields)之外，WorktreeCreate hook 還會收到 `name` 欄位。這是新 worktree 的 slug 識別碼，可能由使用者指定或自動產生，例如 `bold-oak-a3f2`。

```json theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "hook_event_name": "WorktreeCreate",
  "name": "feature-auth"
}
```

#### WorktreeCreate 輸出

WorktreeCreate hook 不使用標準的允許/封鎖決策模型。取而代之的是，由 hook 的成功或失敗決定結果。此 hook 必須傳回所建立之 worktree 目錄的路徑：

* **命令 hook**（`type: "command"`）：將路徑印為 stdout 的最後一個非空白行。Claude Code 會在讀取該行之前移除 ANSI 跳脫碼，因此在您的 `echo` 之前印出的 shell 啟動橫幅會被忽略。請將其他任何 hook 輸出重新導向至 stderr。
* **HTTP hook**（`type: "http"`）：在回應主體中傳回 `{ "hookSpecificOutput": { "hookEventName": "WorktreeCreate", "worktreePath": "/absolute/path" } }`。

如果 hook 失敗或未產生路徑，worktree 建立會失敗並出現錯誤。Claude Code 會以 hook 執行時所在的目錄為基準解析相對路徑，並收合其中的 `.` 或 `..` 區段。如果產生的路徑不是 Claude Code 可以進入的目錄，工作階段會印出指名該路徑的錯誤，並以代碼 1 結束。

Claude Code 會拒絕包含 `.` 或 `..` 區段的絕對路徑，以及任何在儲存庫根目錄之下經過符號連結的路徑。錯誤會指名被拒絕的元件。提交至儲存庫的符號連結可能會將 worktree 重新導向到儲存庫之外。請回傳不經過儲存庫內符號連結的正規化路徑。

### WorktreeRemove

在 Claude Code 清理由您的 [`WorktreeCreate`](#worktreecreate) hook 所建立的 worktree 時執行。此事件會在以下情況觸發：

* 您結束互動式 [worktree 工作階段](https://code.claude.com/docs/zh-TW/worktrees.md#start-claude-in-a-worktree)，並在 Claude Code 提示時選擇移除 worktree
* 您結束一個尚未[命名](https://code.claude.com/docs/zh-TW/sessions.md#name-your-sessions)的互動式 worktree 工作階段，Claude Code 沒有找到已變更或未追蹤的檔案，並在不提示您的情況下移除 worktree
* 您刪除在該 worktree 中執行的[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md#what-deleting-a-session-removes)
* 您在工作階段期間要求 Claude 結束並移除 worktree，而 Claude 以 [`ExitWorktree`](https://code.claude.com/docs/zh-TW/tools-reference) 工具將其移除
* 由 [`claude remote-control`](https://code.claude.com/docs/zh-TW/remote-control#start-a-remote-control-session) 以 `worktree` 模式啟動的工作階段在未當機的情況下結束，且 Claude Code 在其 worktree 中沒有找到已變更或未追蹤的檔案，也沒有新的提交
* 您在 `claude remote-control` 以 `worktree` 模式啟動的工作階段仍在執行時停止它，且 Claude Code 在這些工作階段的 worktree 中沒有找到已變更或未追蹤的檔案，也沒有新的提交

當 subagent 或工作流程 agent 完成時，Claude Code 會保留您的 WorktreeCreate hook 為其建立的 worktree，且不會執行您的 WorktreeRemove hook。請在工作完成後自行移除這些 worktree。

對於 `ExitWorktree` 呼叫或 `claude remote-control` 清理，Claude Code 在您的 hook 執行前不會提示您。除非呼叫傳入 [`discard_changes: true`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#exitworktree)，否則 `ExitWorktree` 會拒絕移除由 hook 建立的 worktree，這使得您的 hook 成為該途徑上的最後一道檢查。

Claude Code 使用 git 尋找已變更或未追蹤的檔案，因此在不是 git 簽出（或不位於 git 簽出內）的 worktree 中，即使目錄中含有未提交的工作，它也找不到任何檔案。請在您的 WorktreeRemove hook 刪除任何內容之前檢查這類工作。

對於以 git 為基礎的 worktree，Claude Code 會以 `git worktree remove` 自動處理清理。如果您設定了 WorktreeCreate hook，請搭配 WorktreeRemove hook 來控制清理：

* **沒有 WorktreeRemove hook**：對於結束時或透過 `ExitWorktree` 進行的移除，Claude Code 會改用 git；而在 `claude remote-control` 進行清理時則會保留 worktree：
  * **您結束 worktree 工作階段，或 Claude 呼叫 `ExitWorktree`**：Claude Code 會以如同 `git worktree remove --force` 的方式移除您的 WorktreeCreate hook 所傳回的路徑，因此 git 能識別的 worktree 會被移除。git 無法識別的 worktree（例如您的 hook 以非 git 版本控制系統建立的 worktree）則會保留在磁碟上。
  * **`claude remote-control` 清理工作階段的 worktree**：worktree 會保留在磁碟上，且執行 `claude remote-control` 的終端機會顯示 `worktree removal failed, kept: <path>`。
  * **您刪除背景工作階段**：請參閱[刪除工作階段會移除哪些內容](https://code.claude.com/docs/zh-TW/agent-view.md#what-deleting-a-session-removes)。
* **Hook 以 0 結束**：worktree 會被視為已移除。Claude Code 不會從 hook 讀取其他任何內容，因此請確保您的 hook 已刪除該目錄。
* **Hook 以非零值結束**：如果 `worktree_path` 處的目錄之後仍然存在，移除即告失敗，worktree 會保留在磁碟上，且不會改用 git。在以非零值結束前已刪除目錄的 hook 會被視為已移除。關於失敗如何回報，請參閱 [WorktreeRemove 輸入](#worktreeremove-input)。

Claude Code 絕不會刪除屬於 hook 建立之 worktree 的分支，因為它只知道您的 WorktreeCreate hook 所回傳的路徑。如果您的 WorktreeCreate hook 建立了分支，請在您的 WorktreeRemove hook 中將其刪除。Claude Code 會捨棄 WorktreeRemove hook 的 [JSON 輸出欄位](#json-output)，例如 `systemMessage` 和 `continue`。

對於背景工作階段的刪除，Claude Code 會在執行 hook 之前驗證所儲存的 worktree 路徑，拒絕本身是符號連結或在儲存庫根目錄之下經過符號連結的路徑。在該路徑上，只有在您於 [agent view](https://code.claude.com/docs/zh-TW/agent-view.md#what-deleting-a-session-removes) 中確認刪除時，hook 才會針對仍含有檔案的 worktree 執行。對於這類 worktree，[`claude rm`](https://code.claude.com/docs/zh-TW/agent-view#manage-sessions-from-the-shell) 則會保留工作階段和 worktree。

Claude Code 會將 WorktreeCreate 傳回的路徑作為 hook 輸入中的 `worktree_path` 傳入。此範例會讀取該路徑並移除目錄：

```json theme={null}
{
  "hooks": {
    "WorktreeRemove": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash -c 'jq -r .worktree_path | xargs rm -rf'"
          }
        ]
      }
    ]
  }
}
```

#### WorktreeRemove 輸入

除了[通用輸入欄位](#common-input-fields)之外，WorktreeRemove hook 還會收到 `worktree_path` 欄位，也就是要移除之 worktree 的絕對路徑。

```json theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "hook_event_name": "WorktreeRemove",
  "worktree_path": "/Users/.../my-project/.claude/worktrees/feature-auth"
}
```

WorktreeRemove hook 的退出碼決定結果。當 hook 以非零值結束，且 `worktree_path` 處的目錄之後仍然存在時，移除即告失敗：

* worktree 會保留在磁碟上，hook 的命令與 stderr 會寫入[偵錯日誌](#debug-hooks)。
* 如果您當時正在刪除背景工作階段，該工作階段也會保留。[agent view](https://code.claude.com/docs/zh-TW/agent-view.md#what-deleting-a-session-removes) 中的拒絕訊息會回報 hook 的結束方式（例如 `exited 1`）、引用其 stderr 的開頭，並說明再次刪除工作階段是否仍會移除該目錄。
* 如果 `claude remote-control` 當時正在清理工作階段的 worktree，執行它的終端機會顯示 `worktree removal failed, kept: <path>`。

### PreCompact

在 Claude Code 即將執行壓縮作業之前執行。

matcher 值表示壓縮是手動或自動觸發的：

| Matcher | 觸發時機 |
| :- | :- |
| `manual` | `/compact` |
| `auto` | 對話達到[自動壓縮視窗](https://code.claude.com/docs/zh-TW/model-config.md#set-the-auto-compact-window)時的自動壓縮，以及[閒置壓縮](https://code.claude.com/docs/zh-TW/settings-reference.md#idlecompaction) |

以代碼 2 結束可封鎖壓縮。對於手動的 `/compact`，stderr 訊息會顯示給使用者。您也可以傳回包含 `"decision": "block"` 的 JSON 來封鎖。

封鎖自動壓縮會依觸發時機而產生不同效果。如果壓縮是在達到上下文上限之前主動觸發的，Claude Code 會略過它，對話會在未壓縮的情況下繼續。如果壓縮是為了從 API 已傳回的上下文上限錯誤中復原而觸發的，底層錯誤會浮現，且目前的請求會失敗。

Claude Code 會捨棄 PreCompact hook 的 `systemMessage` 與 `continue` 欄位。

#### PreCompact 輸入

除了[通用輸入欄位](#common-input-fields)之外，PreCompact hook 還會收到 `trigger` 與 `custom_instructions`。對於 `manual`，`custom_instructions` 包含使用者傳入 `/compact` 的內容，未傳入任何內容時則為 `null`。對於 `auto`，`custom_instructions` 為 `null`。

```json theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "hook_event_name": "PreCompact",
  "trigger": "manual",
  "custom_instructions": null
}
```

### PostCompact

在 Claude Code 完成壓縮作業後執行。使用此事件對新的壓縮後狀態做出反應，例如記錄產生的摘要或更新外部狀態。Claude Code 會捨棄 PostCompact hook 的 `systemMessage` 與 `continue` 欄位。

適用與 `PreCompact` 相同的 matcher 值：

| Matcher | 觸發時機 |
| :- | :- |
| `manual` | `/compact` 之後 |
| `auto` | 對話達到[自動壓縮視窗](https://code.claude.com/docs/zh-TW/model-config.md#set-the-auto-compact-window)時的自動壓縮之後，以及[閒置壓縮](https://code.claude.com/docs/zh-TW/settings-reference.md#idlecompaction)之後 |

#### PostCompact 輸入

除了[通用輸入欄位](#common-input-fields)之外，PostCompact hook 還會收到 `trigger` 與 `compact_summary`。`compact_summary` 欄位包含壓縮作業所產生的對話摘要。

```json theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "hook_event_name": "PostCompact",
  "trigger": "manual",
  "compact_summary": "Summary of the compacted conversation..."
}
```

PostCompact hook 沒有決策控制。它們無法影響壓縮結果，但可以執行後續工作。

### PreModelSwitch

在 Claude Code 套用您或用戶端所請求的模型切換之前執行。可用來封鎖切換、要求確認，或在切換發生前顯示切換的成本。

PreModelSwitch 需要 Claude Code v2.1.251 或更新版本。Claude Code 會針對以下請求執行它：

* `/model <name>` 與 `/model` 選擇器
* `Option+P` 或 `Alt+P` 模型選擇器
* `/config` 中的 Model 設定
* 開啟[快速模式](https://code.claude.com/docs/zh-TW/fast-mode.md)且因此變更工作階段的模型時
* 來自 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md#query-object) 主機或 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 的 `set_model` 請求，或 `apply_flag_settings` 請求中的模型變更

對於 Claude Code 自行進行的切換，例如[自動模型備援](https://code.claude.com/docs/zh-TW/model-config.md#automatic-model-fallback)或在您繼續工作階段時還原模型，Claude Code 不會執行 PreModelSwitch hook。這些變更只會觸發 [PostModelSwitch](#postmodelswitch)。

Claude Code 會將 matcher 與工作階段要切換到的模型之標準名稱進行比對，並忽略任何 `[1m]` 後綴。像 `opus` 這樣的別名、帶日期的模型 ID，以及供應商特定的 ID（例如 Amazon Bedrock 模型 ID）都會符合它們所解析到的同一個標準名稱，因此 `claude-opus-5` 涵蓋了 Opus 5 的所有寫法。

當 Claude Code 無法判斷目標的標準名稱時（例如只有您的 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)知道的自訂模型 ID），它會不論 matcher 為何而執行每個 PreModelSwitch hook。因此，進行封鎖的 hook 應檢查其輸入中的 `to_model`，而非僅依賴 matcher。

請將 matcher 寫成精確名稱、以 `|` 分隔的清單（例如 `claude-opus-4-6|claude-opus-5`），或正規表示式（例如 `.*opus.*`）。此範例使用精確名稱 matcher，並同時檢查 hook 輸入中的 `to_model`，因此會以代碼 2 結束來拒絕切換到 Opus 4.6，並放行其他任何目標：

> [tab] macOS/Linux
>
> 此命令以 `jq` 檢查 `to_model`：
>
> ```json theme={null}
> {
>   "hooks": {
>     "PreModelSwitch": [
>       {
>         "matcher": "claude-opus-4-6",
>         "hooks": [
>           {
>             "type": "command",
>             "command": "jq -e '.to_model | test(\"opus-4-6\")' > /dev/null && { echo 'Opus 4.6 is retired for this project. Use a newer model.' >&2; exit 2; }; exit 0"
>           }
>         ]
>       }
>     ]
>   }
> }
> ```

> [tab] Windows (PowerShell)
>
> 註冊一個透過 PowerShell 執行指令碼的命令 hook：
>
> ```json theme={null}
> {
>   "hooks": {
>     "PreModelSwitch": [
>       {
>         "matcher": "claude-opus-4-6",
>         "hooks": [
>           {
>             "type": "command",
>             "command": "powershell.exe",
>             "args": [
>               "-NoProfile",
>               "-ExecutionPolicy",
>               "Bypass",
>               "-File",
>               "${CLAUDE_PROJECT_DIR}/.claude/hooks/block-opus-46.ps1"
>             ]
>           }
>         ]
>       }
>     ]
>   }
> }
> ```
>
> 將此指令碼儲存至專案中的 `.claude/hooks/block-opus-46.ps1`：
>
> ```powershell theme={null}
> $hookInput = [Console]::In.ReadToEnd() | ConvertFrom-Json
> if ($hookInput.to_model -match 'opus-4-6') {
>   [Console]::Error.WriteLine('Opus 4.6 is retired for this project. Use a newer model.')
>   exit 2
> }
> exit 0
> ```

若要確認 hook 是否正常運作，請在執行其他模型的工作階段中執行 `/model claude-opus-4-6`。Claude Code 會保留目前的模型，並回報 PreModelSwitch hook 封鎖了切換，並以您的訊息作為原因。

#### PreModelSwitch 輸入

除了[通用輸入欄位](#common-input-fields)之外，PreModelSwitch hook 還會收到此表中的欄位。最後五個欄位描述將對話重新傳送給新模型的成本，讓 hook 可以在切換發生前顯示該數字。

| 欄位 | 類型 | 說明 |
| :- | :- | :- |
| `from_model` | string | 切換前的模型 ID |
| `to_model` | string | 切換後的模型 ID。matcher 會與此模型的標準名稱進行比對 |
| `requested_model` | string 或 `null` | 請求所指名的模型：像 `opus` 這樣的別名、完整的模型 ID，或在請求預設模型時為 `null` |
| `source` | string | 請求的來源：`"command"` 表示 `/model <name>`、`/config` 中的 Model 設定，或開啟快速模式；`"picker"` 表示模型選擇器；`"sdk"` 表示來自 Agent SDK 主機或 Remote Control 的 `set_model` 請求，或 `apply_flag_settings` 請求中的模型變更 |
| `context_tokens` | number | 下一個請求作為提示詞重新傳送的 token 數：主要對話中最後一個回應的輸入、快取讀取、快取建立與輸出 token 的總和。在第一個回應之前為 `0` |
| `prompt_cache_warm` | boolean | 目前模型的提示快取是否可能仍處於溫熱狀態，也就是切換會使其失效 |
| `cache_ttl` | string | 此次切換時主要對話的[提示快取存留期](https://code.claude.com/docs/zh-TW/prompt-caching.md#cache-lifetime)：`"5m"` 或 `"1h"` |
| `estimated_cache_write_usd` | number | 以 `cache_ttl` 費率在 `to_model` 上將 `context_tokens` 寫入提示快取的估計成本（美元），不包含下一個回應。伺服器可能不需要重新快取整個上下文，因此請將其視為估計值 |
| `pricing` | string | Claude Code 為 `estimated_cache_write_usd` 計價的方式：`"configured"` 表示您的組織已設定自己的費率並依此計價，`"catalog"` 表示依牌價計價，`"default"` 表示 `to_model` 沒有已知價格，Claude Code 假設了預設費率 |

此範例顯示在執行 Sonnet 5 的工作階段中執行 `/model opus` 時的輸入：

```json theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "hook_event_name": "PreModelSwitch",
  "from_model": "claude-sonnet-5",
  "to_model": "claude-opus-5",
  "requested_model": "opus",
  "source": "command",
  "context_tokens": 182340,
  "prompt_cache_warm": true,
  "cache_ttl": "5m",
  "estimated_cache_write_usd": 1.1396,
  "pricing": "catalog"
}
```

#### PreModelSwitch 決策控制

`PreModelSwitch` hook 可以取消切換、要求使用者確認，或讓切換繼續進行。退出碼 2 或頂層的 `decision: "block"` 會取消切換。

若要進行更精細的控制，請在 `hookSpecificOutput` 物件中傳回 `permissionDecision` 與 `permissionDecisionReason`，如同 [PreToolUse](#pretooluse-decision-control)。`PreModelSwitch` 接受 `"allow"`、`"deny"` 與 `"ask"`。它不接受 `"defer"`、`updatedInput` 或 `additionalContext`。下表說明這兩個欄位：

| 欄位 | 說明 |
| :- | :- |
| `permissionDecision` | `"allow"` 會繼續進行，並略過[提示快取溫熱時 Claude Code 顯示的確認](https://code.claude.com/docs/zh-TW/prompt-caching.md#switching-models)。`"deny"` 會取消切換。`"ask"` 會提示使用者確認 |
| `permissionDecisionReason` | 對於 `"deny"`，會作為切換遭封鎖的原因顯示給使用者，或作為 `set_model` 請求的錯誤傳回。對於 `"ask"`，會顯示在確認提示中。對於 `"allow"` 則會被忽略 |

只有互動式工作階段中的 `/model` 能顯示 `"ask"` 提示。在其他所有使用介面上，包括使用 `-p` 旗標的非互動模式、`/config` 以及 `set_model` 請求，Claude Code 都會將 `"ask"` 視為拒絕。

此範例會要求使用者確認，並引用 `context_tokens` 中的 token 數：

```json theme={null}
{
  "hookSpecificOutput": {
    "hookEventName": "PreModelSwitch",
    "permissionDecision": "ask",
    "permissionDecisionReason": "Switching now re-sends about 180k tokens to the new model. Continue?"
  }
}
```

當多個 PreModelSwitch hook 傳回不同的決策時，優先順序為 `deny` > `ask` > `allow`。

無論決策為何，Claude Code 都會向使用者顯示您的 hook 所傳回的任何 `systemMessage`，因此回報成本的 hook 可以傳回 `{"systemMessage": "..."}` 並以 0 結束。

#### PreModelSwitch 逾時及其他退出碼

在逾時之前未回應的 PreModelSwitch hook 會阻擋切換。此事件的預設逾時為 30 秒。

沒有有效 JSON 輸出且退出碼不是 0 或 2 的情況屬於[非封鎖錯誤](#other-exit-codes)，因此切換會繼續進行，但[其失敗會封鎖動作](#block-the-action-when-a-hook-fails)的 hook 除外。

### PostModelSwitch

在工作階段的模型變更後執行。可用來為 Claude 提供特定模型的指引，而無需編輯每個 CLAUDE.md，例如適用於特定模型的組織層級指令。

PostModelSwitch 需要 Claude Code v2.1.251 或更新版本。由於模型已經變更，它無法進行封鎖。Claude Code 會在以下任何變更後執行 PostModelSwitch hook：

* 您或用戶端所請求的切換
* [自動模型備援](https://code.claude.com/docs/zh-TW/model-config.md#automatic-model-fallback)，它會變更工作階段的模型
* 像 [`opusplan`](https://code.claude.com/docs/zh-TW/model-config#opusplan-model-setting) 這樣的設定進入或離開 plan mode
* Claude Code 在您繼續工作階段時還原模型

當[備援模型鏈](https://code.claude.com/docs/zh-TW/model-config.md#fallback-model-chains)中的模型負責某個回合時，Claude Code 不會執行 PostModelSwitch hook，因為該替代只持續一個回合，且不會變更工作階段的模型。

matcher 遵循與 [PreModelSwitch](#premodelswitch) 相同的規則：Claude Code 會將其與工作階段切換到的模型之標準名稱進行比對。

此範例會在工作階段的模型變更為任何 Opus 模型時加入指引：

```json theme={null}
{
  "hooks": {
    "PostModelSwitch": [
      {
        "matcher": ".*opus.*",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'On Opus, delegate implementation work to subagents and keep this conversation for planning and review.'"
          }
        ]
      }
    ]
  }
}
```

若要確認 hook 是否正常運作，請從執行其他模型的工作階段切換到 Opus 模型，例如在 Sonnet 工作階段中執行 `/model opus`，然後詢問 Claude 它對目前模型有什麼指引。

#### PostModelSwitch 輸入

PostModelSwitch hook 會收到與 [PreModelSwitch](#premodelswitch-input) 相同的欄位，其中 `hook_event_name` 設為 `"PostModelSwitch"`，並多了兩個 `source` 值：`"auto"` 表示自動備援或 Claude Code 自行進行的其他變更，`"resume"` 表示您繼續工作階段時所還原的模型。

當 `source` 為 `"auto"` 時，`requested_model` 為 `null`。當 `source` 為 `"resume"` 時，它是 Claude Code 所還原的已儲存模型設定。

#### PostModelSwitch 決策控制

Claude Code 會在以 0 結束時取得您 hook 的[純文字 stdout](#exit-code-0)，或取得 JSON 輸出中的 `additionalContext`，並在切換後隨下一個請求傳遞給 Claude。除了所有 hook 皆可使用的 [JSON 輸出欄位](#json-output)之外，您還可以傳回：

| 欄位 | 說明 |
| :- | :- |
| `additionalContext` | 隨下一個請求加入 Claude 上下文的字串。請參閱[為 Claude 新增上下文](#add-context-for-claude) |

如果在您傳送下一個提示詞後五秒內 hook 尚未完成，Claude Code 會在不含該輸出的情況下傳送該請求，並改為將其附加到再下一個請求。如果模型在下一個請求之前變更了數次，Claude Code 只會傳遞最後一次切換之目標模型的輸出。

### SessionEnd

在 Claude Code 工作階段結束時執行。適用於清理工作、記錄工作階段
統計資料或儲存工作階段狀態。支援以 matcher 依結束原因進行篩選。

hook 輸入中的 `reason` 欄位表示工作階段結束的原因：

| 原因 | 說明 |
| :- | :- |
| `clear` | 以 `/clear` 命令清除工作階段 |
| `resume` | 透過互動式 `/resume` 切換工作階段 |
| `logout` | 使用者已登出 |
| `prompt_input_exit` | 使用者在提示詞輸入可見時結束 |
| `other` | 其他結束原因 |
| `bypass_permissions_disabled` | 已於 v2.1.234 移除；Claude Code 不會傳送此值。請將其從您的 `SessionEnd` matcher 中移除 |

#### SessionEnd 輸入

除了[通用輸入欄位](#common-input-fields)之外，SessionEnd hook 還會收到表示工作階段結束原因的 `reason` 欄位。所有值請參閱上方的[原因表](#sessionend)。

```json theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "hook_event_name": "SessionEnd",
  "reason": "other"
}
```

SessionEnd hook 沒有決策控制。它們無法阻止工作階段終止，但可以執行清理工作。Claude Code 會捨棄其 [JSON 輸出欄位](#json-output)，例如 `systemMessage`。

SessionEnd hook 的預設逾時為 1.5 秒。它適用於您結束、執行 `/clear`，或以互動式 `/resume` 切換工作階段時。您可以透過兩種方式給予 hook 更多時間：

* **個別 hook 的 `timeout`**：在該 hook 的設定中設定 `timeout`。整體預算會自動提高，以符合您設定檔中最高的個別 hook `timeout`，最多 60 秒。如果您以此方式提高預算，沒有自己 `timeout` 的 hook 仍會保留預設值。在外掛程式提供的 hook 上設定的逾時不會提高預算。
* **`CLAUDE_CODE_SESSIONEND_HOOKS_TIMEOUT_MS`**：以毫秒為單位設定此環境變數，以明確覆寫預算。您設定的值也會成為每個沒有自己 `timeout` 之 hook 的逾時。

此範例將預算設為 5 秒：

```bash theme={null}
CLAUDE_CODE_SESSIONEND_HOOKS_TIMEOUT_MS=5000 claude
```

在 v2.1.268 之前，`CLAUDE_CODE_SESSIONEND_HOOKS_TIMEOUT_MS` 只會提高整體預算，沒有自己 `timeout` 的 hook 仍會在 1.5 秒後被取消。

### Elicitation

在 MCP 伺服器於工作進行中請求使用者輸入時執行。根據預設，Claude Code 會顯示互動式對話方塊讓使用者回應。hook 可以攔截此請求並以程式方式回應，完全略過對話方塊。

關於包含設定項目與指令碼的完整 hook，請參閱[從指令碼回答表單請求](#answer-a-form-request-from-a-script)。

matcher 欄位會與 MCP 伺服器名稱進行比對。

#### Elicitation 輸入

除了[通用輸入欄位](#common-input-fields)之外，Elicitation hook 還會收到 `mcp_server_name`、`message`，以及選用的 `mode`、`url`、`elicitation_id` 與 `requested_schema` 欄位。

表單模式的 elicitation，也就是最常見的情況：

```json theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "hook_event_name": "Elicitation",
  "mcp_server_name": "my-mcp-server",
  "message": "Please provide your credentials",
  "mode": "form",
  "requested_schema": {
    "type": "object",
    "properties": {
      "username": { "type": "string", "title": "Username" }
    }
  }
}
```

URL 模式的 elicitation，用於以瀏覽器為基礎的身分驗證：

```json theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "hook_event_name": "Elicitation",
  "mcp_server_name": "my-mcp-server",
  "message": "Please authenticate",
  "mode": "url",
  "url": "https://auth.example.com/login"
}
```

#### Elicitation 輸出

Elicitation hook 可以代替使用者回答請求、拒絕或取消請求，或將其留給對話方塊處理。若要回答、拒絕或取消，請以 0 結束並印出含有 `action` 的 `hookSpecificOutput` 物件。伺服器會收到您的答覆，且不會出現對話方塊。此表的每一列都顯示針對某個結果應傳回的內容，以及 MCP 伺服器會收到的內容：

| 目的 | 傳回 | 伺服器收到 |
| :- | :- | :- |
| 代替使用者回答 | `"action": "accept"`，並在 `content` 中提供表單欄位值 | `accept` 以及您的 `content` |
| 拒絕請求 | `"action": "decline"` | `decline` |
| 取消請求 | `"action": "cancel"` | `cancel` |
| 將請求留給使用者 | 無輸出，退出碼為 0 | 使用者在[對話方塊](https://code.claude.com/docs/zh-TW/mcp.md#respond-to-mcp-elicitation-requests)中的答覆 |

此輸出會回答 [Elicitation 輸入](#elicitation-input)中所示的表單模式請求。`content` 中的鍵是該請求之 `requested_schema` 中的屬性名稱：

```json theme={null}
{
  "hookSpecificOutput": {
    "hookEventName": "Elicitation",
    "action": "accept",
    "content": {
      "username": "alice"
    }
  }
}
```

此輸出會拒絕請求：

```json theme={null}
{
  "hookSpecificOutput": {
    "hookEventName": "Elicitation",
    "action": "decline"
  }
}
```

在對話方塊中，選取 **Decline** 會傳送 `decline`，按下 `Esc` 則會傳送 `cancel`，因此請傳回您希望伺服器看到的那一個。

對於 URL 模式的請求，傳回 `accept` 的 hook 會略過對話方塊，因此 URL 永遠不會開啟。

無論您傳回哪個 `action`，Claude Code 都會捨棄 Elicitation hook JSON 輸出中的 `reason`、`systemMessage` 與 `continue`。

#### 拒絕 elicitation 的其他方式

您的 hook 也可以透過以下方式拒絕。伺服器會收到與 `"action": "decline"` 相同的 `decline`：

* **以代碼 2 結束**：Claude Code 會忽略同一個 hook 所印出的 `hookSpecificOutput`
* **印出頂層的 `"decision": "block"`**：封鎖會覆寫同一輸出中的 `action`

當多個 hook 符合同一個請求時，其中一個的拒絕會覆寫另一個的 `accept` 或 `cancel`。

此指令碼會拒絕 URL 模式的請求，並將表單請求留給對話方塊處理：

```bash theme={null}
#!/bin/bash
if [ "$(jq -r '.mode')" = "url" ]; then
  exit 2
fi
```

使用者和伺服器都看不到您的 hook 拒絕的原因，因為 Claude Code 不會顯示您的 stderr 或您的 `reason`。

從 v2.1.105 起直到 v2.1.284 修正為止，Claude Code 會忽略 `Elicitation` 與 `ElicitationResult` hook 的頂層 `decision`。

#### 從指令碼回答表單請求

此範例會代替使用者回答一個反覆出現的問題。名為 `issue-tracker` 的 MCP 伺服器會在表單中要求專案鍵，而 hook 會填入 `DOCS`。當 `project_key` 是表單唯一的欄位時，指令碼會接受。對於其他任何請求，它不會印出任何內容，因此會出現對話方塊。

> [tab] macOS/Linux
>
> 在您的設定檔中為此事件註冊命令 hook，並以伺服器名稱作為 matcher：
>
> ```json theme={null}
> {
>   "hooks": {
>     "Elicitation": [
>       {
>         "matcher": "issue-tracker",
>         "hooks": [
>           {
>             "type": "command",
>             "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/answer-project-key.sh",
>             "args": []
>           }
>         ]
>       }
>     ]
>   }
> }
> ```
>
> 將此指令碼儲存至專案中的 `.claude/hooks/answer-project-key.sh`，並以 `chmod +x` 設為可執行：
>
> ```bash theme={null}
> #!/bin/bash
> input=$(cat)
> fields=$(jq -c '.requested_schema.properties // {} | keys' <<<"$input")
>
> if [ "$fields" = '["project_key"]' ]; then
>   jq -n '{hookSpecificOutput: {hookEventName: "Elicitation", action: "accept", content: {project_key: "DOCS"}}}'
> fi
> ```

> [tab] Windows (PowerShell)
>
> 註冊一個透過 PowerShell 執行指令碼的命令 hook，並以伺服器名稱作為 matcher：
>
> ```json theme={null}
> {
>   "hooks": {
>     "Elicitation": [
>       {
>         "matcher": "issue-tracker",
>         "hooks": [
>           {
>             "type": "command",
>             "command": "powershell.exe",
>             "args": [
>               "-NoProfile",
>               "-ExecutionPolicy",
>               "Bypass",
>               "-File",
>               "${CLAUDE_PROJECT_DIR}/.claude/hooks/answer-project-key.ps1"
>             ]
>           }
>         ]
>       }
>     ]
>   }
> }
> ```
>
> 將此指令碼儲存至專案中的 `.claude/hooks/answer-project-key.ps1`：
>
> ```powershell theme={null}
> $request = [Console]::In.ReadToEnd() | ConvertFrom-Json
> $fields = @($request.requested_schema.properties.PSObject.Properties.Name)
>
> if ($fields.Count -eq 1 -and $fields[0] -eq 'project_key') {
>   @{
>     hookSpecificOutput = @{
>       hookEventName = "Elicitation"
>       action = "accept"
>       content = @{ project_key = "DOCS" }
>     }
>   } | ConvertTo-Json -Depth 3
> }
> ```

若要確認 hook 是否正常運作，請以 `claude --debug` 啟動 Claude Code，並給 Claude 一項會讓伺服器要求專案鍵的工作。不會出現對話方塊，且[偵錯日誌](#debug-hooks)中會有一行以 `Elicitation resolved by hook: {"action":"accept","content":{"project_key":"DOCS"}}` 結尾。

### ElicitationResult

在使用者回應 MCP elicitation 後執行。hook 可以在回應傳回 MCP 伺服器之前觀察、修改或封鎖該回應。

當 [Elicitation](#elicitation) hook 回答了請求時，Claude Code 會將該答覆傳送給伺服器，而不執行 ElicitationResult hook。

matcher 欄位會與 MCP 伺服器名稱進行比對。

#### ElicitationResult 輸入

除了[通用輸入欄位](#common-input-fields)之外，ElicitationResult hook 還會收到 `mcp_server_name`、`action`，以及選用的 `mode`、`elicitation_id` 與 `content` 欄位。

```json theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "hook_event_name": "ElicitationResult",
  "mcp_server_name": "my-mcp-server",
  "action": "accept",
  "content": { "username": "alice" },
  "mode": "form"
}
```

#### ElicitationResult 輸出

ElicitationResult hook 可以讓使用者的回應通過、變更其值，或封鎖它。若要變更或封鎖回應，請以 0 結束並印出含有 `action` 的 `hookSpecificOutput` 物件。此表的每一列都顯示針對某個結果應傳回的內容，以及 MCP 伺服器會收到的內容：

| 目的 | 傳回 | 伺服器收到 |
| :- | :- | :- |
| 讓回應通過 | 無輸出，退出碼為 0 | 使用者的回應，未經變更 |
| 變更提交的值 | `"action": "accept"`，並在 `content` 中提供新值 | `accept` 以及您的 `content`，取代使用者的值 |
| 封鎖回應 | `"action": "decline"` | `decline`，不含使用者的值 |
| 取消請求 | `"action": "cancel"` | `cancel`，以及使用者提交的值。若要保留不送出這些值，請傳回 `"decline"` |

此輸出會變更 [ElicitationResult 輸入](#elicitationresult-input)中所示的回應，使伺服器在使用者提交 `alice` 之處收到 `alice@example.com`：

```json theme={null}
{
  "hookSpecificOutput": {
    "hookEventName": "ElicitationResult",
    "action": "accept",
    "content": {
      "username": "alice@example.com"
    }
  }
}
```

您的 `content` 會取代使用者的整個 `content` 物件，因此請包含您未變更的欄位。請一併傳回 `action`，因為 Claude Code 會忽略沒有 `action` 的 `hookSpecificOutput`。

ElicitationResult hook 在使用者拒絕或取消時也會執行，且您的 `action` 會取代使用者的。請在傳回 `accept` 之前，先確認輸入的 `action` 是 `accept`，否則您的 hook 會將被拒絕的請求變成已接受的請求。此指令碼會在使用者接受時進行相同的變更、保留其他欄位，否則不列印任何內容：

```bash theme={null}
#!/bin/bash
input=$(cat)

if [ "$(jq -r '.action' <<<"$input")" = "accept" ]; then
  jq '{hookSpecificOutput: {hookEventName: "ElicitationResult", action: "accept", content: (.content + {username: (.content.username + "@example.com")})}}' <<<"$input"
fi
```

此輸出會封鎖回應：

```json theme={null}
{
  "hookSpecificOutput": {
    "hookEventName": "ElicitationResult",
    "action": "decline"
  }
}
```

退出碼 2 與頂層的 `"decision": "block"` 也會封鎖回應。[拒絕 elicitation 的其他方式](#other-ways-to-decline-an-elicitation)說明了當 hook 同時使用多種方式時哪一種會生效、使用者會看到什麼，以及哪些版本會忽略 `decision`。

無論您傳回哪個 `action`，Claude Code 都會捨棄 ElicitationResult hook JSON 輸出中的 `reason`、`systemMessage` 與 `continue`。

## 基於提示的 hooks

除了命令、HTTP 和 MCP tool hooks 外，Claude Code 還支援基於提示的 hooks（`type: "prompt"`），使用 LLM 評估是否允許或阻止操作，以及代理 hooks（`type: "agent"`），生成具有工具存取權限的代理驗證器。並非所有事件都支援每種 hook 類型。

支援所有五種 hook 類型（`command`、`http`、`mcp_tool`、`prompt` 和 `agent`）的事件：

* `PermissionDenied`
* `PostToolBatch`
* `PostToolUse`
* `PostToolUseFailure`
* `PreToolUse`
* `Stop`
* `SubagentStop`
* `TaskCompleted`
* `TaskCreated`
* `TeammateIdle`
* `UserPromptExpansion`
* `UserPromptSubmit`

`PermissionRequest` 支援 `command`、`http`、`mcp_tool` 和 `prompt` hooks，但不支援 `agent` hooks。如果您在此事件上配置代理 hook，Claude Code 會跳過它，權限流程保持不變。要從 hook 允許或拒絕，請從命令或 HTTP hook 返回[決定物件](#permissionrequest-decision-control)。

支援 `command`、`http` 和 `mcp_tool` hooks 但不支援 `prompt` 或 `agent` 的事件：

* `ConfigChange`
* `CwdChanged`
* `DirectoryAdded`
* `Elicitation`
* `ElicitationResult`
* `FileChanged`
* `InstructionsLoaded`
* `MessageDisplay`
* `Notification`
* `PostCompact`
* `PostModelSwitch`
* `PreCompact`
* `PreModelSwitch`
* `SessionEnd`
* `StopFailure`
* `SubagentStart`
* `WorktreeCreate`
* `WorktreeRemove`

`SessionStart` 和 `Setup` 支援 `command` 和 `mcp_tool` hooks，而 [MCP tool hook 欄位](#mcp-tool-hook-fields)描述了它們的 `mcp_tool` hooks 何時執行。它們不支援 `http`、`prompt` 或 `agent` hooks。

### 基於提示的 hooks 如何工作

基於提示的 hooks 不執行 Bash 命令，而是：

1. 將 hook 輸入和您的提示詞發送到 Claude 模型，預設為 Claude Code 用於[背景功能](https://code.claude.com/docs/zh-TW/model-config.md#environment-variables)的模型
2. LLM 以包含決定的結構化 JSON 回應
3. Claude Code 自動處理決定

### 提示 hook 配置

將 `type` 設定為 `"prompt"` 並提供 `prompt` 字串而不是 `command`。使用 `$ARGUMENTS` 佔位符將 hook 的 JSON 輸入資料注入到您的提示文字中。

在提示詞 hook 或 [agent hook](#agent-based-hooks) 中，您可以將 `prompt` 寫成關於要阻止或允許什麼的規則，例如「Block any Bash command that reads `.env` files」，或寫成必須成立的條件，例如「All unit tests pass」。

此 `Stop` hook 詢問 LLM 在允許 Claude 完成之前是否應該評估所有任務是否完成：

```json theme={null}
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "prompt",
            "prompt": "Evaluate if Claude should stop: $ARGUMENTS. Check if all tasks are complete."
          }
        ]
      }
    ]
  }
}
```

| 欄位 | 必需 | 描述 |
| :- | :- | :- |
| `type` | 是 | 必須為 `"prompt"` |
| `prompt` | 是 | 要發送到 LLM 的提示文字。使用 `$ARGUMENTS` 作為 hook 輸入 JSON 的佔位符。如果 `$ARGUMENTS` 不存在，輸入 JSON 會附加到提示 |
| `model` | 否 | 用於評估的模型。預設為 Claude Code 用於[背景功能](https://code.claude.com/docs/zh-TW/model-config.md#environment-variables)的模型 |
| `timeout` | 否 | 逾時（秒）。預設值：30 |
| `continueOnBlock` | 否 | 在適用的事件上，`true` 將 `ok: false` 原因反饋給 Claude 並繼續而不是結束轉換。預設值：`false`。請參閱[回應架構](#response-schema)以了解每個事件的行為 |

### 回應架構

LLM 必須以包含以下內容的 JSON 回應：

```json theme={null}
{
  "ok": true | false,
  "reason": "Explanation for the decision",
  "impossible": true | false
}
```

| 欄位 | 描述 |
| :- | :- |
| `ok` | `true` 允許操作。`false` 時，請參閱下面的每個事件行為 |
| `reason` | 當 `ok` 為 `false` 時必需 |
| `impossible` | 選用。當模型判斷條件永遠無法滿足時，模型會以 `ok: false` 返回它。在 `Stop` 和 `SubagentStop` 上，Claude Code 會讓轉換結束而不是反饋原因。代理 hooks 和其他事件會忽略它 |

`ok: false` 時發生的情況取決於事件：

* `Stop` 和 `SubagentStop`：原因被反饋給 Claude 作為其下一個指令，轉換繼續，除非回應也設定 `impossible: true`，在這種情況下 Claude Code 允許停止，轉換結束
* `PreToolUse`：工具呼叫被拒絕；預設情況下回合結束，拒絕原因在聊天中顯示為警告行。設定 `continueOnBlock: true` 以改為將原因作為工具錯誤返回給 Claude，使其可以調整並繼續，相當於命令 hook 的 `permissionDecision: "deny"`
* `PostToolUse`：預設情況下轉換結束，原因在聊天中顯示為警告行。設定 `continueOnBlock: true` 以將原因反饋給 Claude 並繼續轉換
* `PostToolBatch`、`UserPromptSubmit` 和 `UserPromptExpansion`：轉換結束，原因顯示為警告行。這些事件在 `decision: "block"` 上結束轉換，無論 `continue` 如何
* `PostToolUseFailure` 和 `TaskCreated`：原因作為工具錯誤返回給 Claude，轉換繼續，無論 `continueOnBlock` 如何
* `TaskCompleted`：當它因為任務在轉換期間被標記為完成而觸發時，原因作為工具錯誤返回給 Claude，轉換繼續，無論 `continueOnBlock` 如何。當它因為隊友停止而觸發時，它的行為類似 `TeammateIdle` 並預設停止隊友
* `TeammateIdle`：預設情況下隊友停止，原因顯示為警告行。設定 `continueOnBlock: true` 以將原因反饋給隊友並保持其工作狀態
* `PermissionRequest`：`ok: false` 沒有效果。要從 hook 拒絕批准，請使用[命令 hook](#command-hook-fields)返回 `hookSpecificOutput.decision.behavior: "deny"`
* `PermissionDenied`：`ok: false` 沒有效果，因為拒絕已經發生。此事件讀取的唯一輸出是 `hookSpecificOutput.retry`，提示和代理 hooks 無法設定。它們在此事件上執行，但其輸出被丟棄。使用[命令 hook](#command-hook-fields)返回 `retry`

如果您需要對任何事件進行更精細的控制，請使用[命令 hook](#command-hook-fields)，其中包含[決定控制](#decision-control)中描述的每個事件欄位。

### 在停止前檢查多個條件

此 `Stop` hook 使用詳細提示在允許 Claude 停止之前檢查三個條件。`SubagentStop` hooks 使用相同的格式來評估 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 是否應該停止。如果模型因為條件尚未滿足而返回 `"ok": false`，Claude 繼續工作，提供的原因作為其下一個指令：

```json theme={null}
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "prompt",
            "prompt": "You are evaluating whether Claude should stop working. Context: $ARGUMENTS\n\nAnalyze the conversation and determine if:\n1. All user-requested tasks are complete\n2. Any errors need to be addressed\n3. Follow-up work is needed\n\nRespond with JSON: {\"ok\": true} to allow stopping, or {\"ok\": false, \"reason\": \"your explanation\"} to continue working.",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

## 基於代理的 hooks

> [!WARNING]
>
> 代理 hooks 是實驗性的。行為和配置可能在未來版本中變更。對於生產工作流程，建議使用[命令 hooks](#command-hook-fields)。

基於代理的 hooks（`type: "agent"`）類似於基於提示的 hooks，但具有多輪工具存取。代理 hook 不是單一 LLM 呼叫，而是生成一個可以讀取檔案、搜尋程式碼和檢查程式碼庫以驗證條件的 subagent。代理 hooks 支援與[基於提示的 hooks](#prompt-based-hooks) 相同的事件，除了 `PermissionRequest`。

### 代理 hooks 如何工作

當代理 hook 觸發時：

1. Claude Code 生成一個 subagent，使用您的提示和 hook 的 JSON 輸入
2. Subagent 可以使用 Read、Grep 和 Glob 等工具進行調查
3. 在最多 50 輪後，subagent 返回結構化的 `{ "ok": true/false }` 決定
4. Claude Code 允許該動作（如果 `ok` 是 `true`）。如果 `ok` 是 `false`，Claude Code 會以與提示 hook 相同的方式處理阻止，該提示 hook 在該事件上具有 `continueOnBlock: true`，如[回應架構](#response-schema)下所列

代理 hooks 在驗證需要檢查實際檔案或測試輸出時很有用，而不僅僅是評估 hook 輸入資料。

### 代理 hook 配置

將 `type` 設定為 `"agent"` 並提供 `prompt` 字串，使用 `$ARGUMENTS` 作為 hook 輸入 JSON 的佔位符。配置欄位與[提示 hooks](#prompt-hook-configuration) 相同，除了代理 hooks 具有更長的預設逾時 60 秒，且沒有 `continueOnBlock` 欄位。

回應架構是 `{ "ok": true }` 允許或 `{ "ok": false, "reason": "..." }` 阻止。在 `ok: false` 時，Claude Code 會以處理[提示 hook 且具有 `continueOnBlock: true`](#response-schema) 的相同方式處理代理 hook；代理 hooks 沒有 `continueOnBlock` 欄位，且不支援提示 hook 的 `impossible` 欄位。

此 `Stop` hook 驗證所有單元測試通過，然後允許 Claude 完成：

```json theme={null}
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "agent",
            "prompt": "Verify that all unit tests pass. Run the test suite and check the results. $ARGUMENTS",
            "timeout": 120
          }
        ]
      }
    ]
  }
}
```

## 在背景執行 hooks

預設情況下，hooks 會阻止 Claude 的執行，直到它們完成。對於長時間執行的任務，如部署、測試套件或外部 API 呼叫，設定 `"async": true` 以在背景執行 hook，同時 Claude 繼續工作。非同步 hooks 無法阻止或控制 Claude 的行為：回應欄位，如 `decision`、`permissionDecision` 和 `continue` 沒有效果，因為它們會控制的操作已經完成。

### 配置非同步 hook

將 `"async": true` 新增到命令 hook 的配置以在背景執行它而不阻止 Claude。此欄位僅在 `type: "command"` hooks 上可用。

此 hook 在每個 `Write` 工具呼叫後執行測試指令碼。Claude 立即繼續工作，同時 `run-tests.sh` 執行。當指令碼完成時，其輸出在下一個對話輪次上傳遞：

```json theme={null}
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/run-tests.sh",
            "async": true
          }
        ]
      }
    ]
  }
}
```

一旦非同步 hook 在背景執行，Claude Code 不會對其強制執行 `timeout`。Claude Code 仍然會對使用 `asyncRewake` 執行的 hook 強制執行 `timeout`。

Claude Code 只在工作階段執行時傳遞非同步 hook 的結果：

* 在[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)中使用 `-p` 旗標，Claude Code 會在清理時終止任何仍在執行的非同步 hook，並以 `cancelled` 結果完成它
* 如果你的 hook 工作必須超越 `claude -p` 工作階段，請從它啟動一個完全分離的程序

### 非同步 hooks 如何執行

當非同步 hook 觸發時，Claude Code 啟動 hook 程序並立即繼續，而不等待它完成。Hook 在 stdin 上接收與同步 hook 相同的 JSON 輸入。

背景程序退出後，Claude Code 會在下一個對話回合將 hook 的 JSON 回應中的 `additionalContext` 和 `systemMessage` 欄位傳遞給 Claude，但[重複的 `SessionStart` 輸出](#limitations)除外。與同步 hook 的 `systemMessage` 不同，這兩個欄位都不會顯示給您。

將 JSON 回應單獨輸出至 stdout，或單獨列印在其自己的一行上：

* **單獨輸出至 stdout**：當回應是 stdout 上唯一的文字時，它可以跨越多行，例如經過美化排版的 `jq` 輸出。跨越多行需要 Claude Code v2.1.295 或更新版本。
* **單獨佔一行**：當回應本身可容納於一行時，非同步 hook 可以將其他文字列印到 stdout，例如使用 `jq -c`。

Claude Code 驗證該 JSON 回應是否符合與同步 hook 相同的[輸出 schema](#json-output)，並捨棄任何值類型錯誤的欄位，例如不是字串的 `systemMessage`，而不是傳遞它。使用 `--debug` 執行以查看命名每個捨棄欄位的警告。

非同步 hook 完成通知預設被抑制。要查看它們，請使用 `Ctrl+O` 啟用詳細模式或使用 `--verbose` 啟動 Claude Code。

### 檔案變更後執行測試

此 hook 在 Claude 寫入檔案時在背景啟動測試套件，然後在測試完成時將結果報告回 Claude。將此指令碼儲存到專案中的 `.claude/hooks/run-tests-async.sh` 並使用 `chmod +x` 使其可執行：

```bash theme={null}
#!/bin/bash
# run-tests-async.sh

# 從 stdin 讀取 hook 輸入
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# 僅針對原始檔案執行測試
if [[ "$FILE_PATH" != *.ts && "$FILE_PATH" != *.js ]]; then
  exit 0
fi

# 執行測試並通過 additionalContext 報告結果給 Claude
RESULT=$(npm test 2>&1)
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
  MSG="Tests passed after editing $FILE_PATH"
else
  MSG="Tests failed after editing $FILE_PATH: $RESULT"
fi
jq -nc --arg msg "$MSG" '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $msg}}'
```

然後將此配置新增到專案根目錄中的 `.claude/settings.json`。`async: true` 旗標讓 Claude 在測試執行時繼續工作：

```json theme={null}
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/run-tests-async.sh",
            "args": [],
            "async": true
          }
        ]
      }
    ]
  }
}
```

### 限制

非同步 hooks 與同步 hooks 相比有額外的限制：

* Hook 輸出在下一個對話輪次上傳遞。如果工作階段閒置，回應會等待直到下一個使用者互動。例外：退出代碼為 2 的 `asyncRewake` hook 即使在工作階段閒置時也會立即喚醒 Claude。
* 每次執行都會建立一個單獨的背景程序。
* 非同步 `SessionStart` hook 在每次事件觸發時都會執行。當 `additionalContext` 和 `systemMessage` 文字與 Claude 上次從該 hook 收到的內容相同時，Claude Code 會略過該 hook 的輸出，除非此後有同步 `SessionStart` hook 新增了其他文字。當文字變更時，Claude Code 會傳遞該文字，並在壓縮或 `/clear` 之後該 hook 下次執行時再次傳遞。在 v2.1.295 之前，Claude Code 會在每次恢復時將相同的文字再次新增到對話中。

## 安全考慮

### 免責聲明

> [!WARNING]
>
> 命令 hooks 以您的完整使用者權限執行 shell 命令。它們可以修改、刪除或存取您的使用者帳戶可以存取的任何檔案。在將任何 hook 命令新增到您的設定之前，請審查並測試它們。

### 工作區信任

Claude Code 在執行任何來自設定檔的 hook 之前會檢查工作區信任。什麼算作受信任取決於工作階段類型：

* **互動式工作階段**：Claude Code 會保留來自每個設定檔的 hooks，包括您自己的 `~/.claude/settings.json`，直到您接受該資料夾的[工作區信任對話框](https://code.claude.com/docs/zh-TW/permissions.md#project-allow-rules-and-workspace-trust)，或接受其信任延伸到該資料夾的父目錄
* **`-p` 或 SDK 工作階段**：Claude Code 不會顯示對話框，並將該資料夾視為受信任，因此儲存庫 `.claude/settings.json` 中提交的 hooks 會在您從未信任過的資料夾中執行

在您對儲存庫執行 `claude -p` 之前，如果您沒有編寫該儲存庫，請審查其 `.claude/` 設定檔，使用 [`--bare`](https://code.claude.com/docs/zh-TW/headless#start-faster-with-bare-mode) 開始，或[為該執行關閉 hooks](#disable-or-remove-hooks)，使用 `--settings '{"disableAllHooks": true}'`。專案子代理中的 Frontmatter hooks 遵循比設定檔 hooks 更嚴格的規則。[在您信任資料夾之前執行的內容](https://code.claude.com/docs/zh-TW/permissions.md#what-runs-before-you-trust-a-folder)按工作階段類型列出每種儲存庫內容。

### 安全最佳實踐

編寫 hooks 時，請記住這些實踐：

* **驗證和清理輸入**：永遠不要盲目信任輸入資料
* **始終引用 shell 變數**：使用 `"$VAR"` 而不是 `$VAR`
* **阻止路徑遍歷**：檢查檔案路徑中的 `..`
* **使用絕對路徑**：為指令碼指定完整路徑。在 exec 形式中，使用 `${CLAUDE_PROJECT_DIR}` 且路徑不需要引用。在 shell 形式中，將其包裝在雙引號中
* **跳過敏感檔案**：避免 `.env`、`.git/`、金鑰等

## Windows PowerShell 工具

在 Windows 上，您可以通過在命令 hook 上設定 `"shell": "powershell"` 在 PowerShell 中執行個別 hooks。Claude Code 自動偵測 `pwsh.exe`（PowerShell 7 及更新版本的可執行檔），並回退到 `powershell.exe`（Windows PowerShell 5.1）。

```json theme={null}
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "shell": "powershell",
            "command": "Write-Host 'File written'"
          }
        ]
      }
    ]
  }
}
```

### 在 PowerShell hook 中依路徑參考指令碼

若要從 PowerShell shell 形式命令參考專案根目錄，請寫入 `${CLAUDE_PROJECT_DIR}` 或 `$env:CLAUDE_PROJECT_DIR`。Claude Code 會在 PowerShell shell 形式命令中將 `${CLAUDE_PROJECT_DIR}`、`${CLAUDE_PLUGIN_ROOT}` 和 `${CLAUDE_PLUGIN_DATA}` 佔位符重寫為 PowerShell 的 `${env:NAME}` 形式，無論 hook 是在 `settings.json`、外掛或 skill 中定義。PowerShell 會在解析後從匯出的環境中解析該值，因此佔位符在雙引號字串內有效，但在單引號字串內無效，因為 PowerShell 永遠不會在單引號字串中展開變數。

不要在 PowerShell hook 中寫入裸露的 `$CLAUDE_PROJECT_DIR` 拼寫。PowerShell 會將其解析為未定義的本機變數，並將其解析為 `$null`，這會導致指令碼路徑沒有其專案根目錄前綴。Claude Code 不會重寫該形式；它會在 [debug log](#debug-hooks) 中記錄警告。

下面的範例顯示了一個 `settings.json` hook，它使用 `$env:` 形式執行專案指令碼：

```json theme={null}
{
  "type": "command",
  "shell": "powershell",
  "command": "& \"$env:CLAUDE_PROJECT_DIR\\.claude\\hooks\\check.ps1\""
}
```

## 偵錯 hooks

Hook 執行詳細資訊被寫入偵錯日誌檔案。使用 `claude --debug-file <path>` 啟動 Claude Code 以將日誌寫入已知位置，或執行 `claude --debug` 並在 `~/.claude/debug/<session-id>.txt` 讀取日誌。`--debug` 標誌不列印到終端。

例如，在 `Write` 上的 `PostToolUse` hook，其命令列印 `hook-ran` 會產生如下項目：

```text theme={null}
2026-07-19T02:03:24.382Z [DEBUG] Hook output does not start with {, treating as plain text
2026-07-19T02:03:24.382Z [DEBUG] "Hook PostToolUse:Write (PostToolUse) success:\nhook-ran"
```

若要找出執行緩慢的 hook，請在日誌中搜尋以持續時間結尾的 `Hooks:` 行。在 Claude Code v2.1.296 或更新版本中，工具事件、`UserPromptSubmit`、`SessionStart`、`Stop` 及其他數個事件上的每個命令 hook 在完成時都會留下這樣一行，無論其輸出了什麼。該行會列出事件名稱，並以冒號連接 hook 所匹配的工具名稱或其他值，接著是以方括號括住的 hook 命令、其來源外掛（如有）、執行的結束方式以及所花費的時間，例如 `Hooks: PostToolUse:Write [.claude/hooks/log-write.sh] finished with status 0 (31ms)`。執行也可能以 `timed out after <N>ms`、`cancelled`、`moved to the background` 或 `failed to start` 結束。在某些事件上，例如 `Notification`、`SessionEnd` 和 `PreCompact`，命令 hook 會改為留下不含持續時間的 `completed with status` 行。

有關更細粒度的 hook 匹配詳細資訊，設定 `CLAUDE_CODE_DEBUG_LOG_LEVEL=verbose` 以查看額外的日誌行，例如 hook 匹配器計數和查詢匹配。

有關故障排除常見問題，如 hooks 不觸發、Stop hooks 持續阻擋或配置錯誤，請參閱指南中的 [限制和故障排除](https://code.claude.com/docs/zh-TW/hooks-guide.md#limitations-and-troubleshooting)。有關涵蓋 `/context`、`/doctor` 和設定優先順序的更廣泛診斷逐步解說，請參閱 [偵錯您的設定](https://code.claude.com/docs/zh-TW/debug-your-config.md)。

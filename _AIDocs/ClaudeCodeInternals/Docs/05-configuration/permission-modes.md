<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/permission-modes | lastmod: 2026-11-03 | section: Configuration / Permissions and sandboxing -->
> 來源：https://code.claude.com/docs/zh-TW/permission-modes（官方 zh-TW，lastmod 2026-11-03）｜分類：Configuration › Permissions and sandboxing｜EN 摘要：Control whether Claude asks before acting. Switch permission modes with Shift+Tab in the CLI, the mode indicator in VS Code, or the mode selector in Desktop.

# 選擇權限模式

> 控制 Claude 在採取動作前是否詢問。在 CLI 中使用 Shift+Tab、在 VS Code 中使用模式指示器，或在 Desktop 中使用模式選擇器來切換權限模式。

權限模式設定 Claude 在工作階段中可以執行哪些操作而無需先詢問您。在 Manual 模式中，Claude Code 會在大多數編輯檔案、執行 shell 命令或存取網路的操作前停止並詢問您。在[自動模式](#eliminate-prompts-with-auto-mode)中，第二個模型（分類器）會審查操作而不是您；[分類器如何評估操作](#how-the-classifier-evaluates-actions)列出它審查的操作以及跳過的操作。

在 Claude Code v2.1.283 或更新版本中，自動模式是互動式終端機和 VS Code 工作階段的內建起始權限模式。在較早版本中，它只在 Pro、Max、Ultra 和 Team 方案上是內建的起始權限模式。[工作階段在哪個模式中啟動](#which-mode-a-session-starts-in)涵蓋改變起始權限模式的使用介面和設定。您也可以隨時改變執行中工作階段的權限模式。

## 可用模式

每種模式在便利性與監督之間做出不同的取捨。下表顯示在各模式中，Claude 無需權限提示即可執行的操作。Manual 模式以其設定值 `default` 列出。

| 模式 | 無需詢問即可執行的操作 | 最適合 |
| :- | :- | :- |
| `default` | 僅讀取 | 親自審查每項操作、敏感工作 |
| [`acceptEdits`](#auto-approve-file-edits-with-acceptedits-mode) | 讀取、檔案編輯，以及常見的檔案系統命令（`mkdir`、`touch`、`mv`、`cp` 等） | 反覆修改您正在審查的程式碼 |
| [`plan`](#analyze-before-you-edit-with-plan-mode) | 讀取，以及在[自動模式](#eliminate-prompts-with-auto-mode)可用時經分類器核准的命令 | 在變更程式碼庫之前先進行探索 |
| [`auto`](#eliminate-prompts-with-auto-mode) | 所有操作，並在背景進行安全檢查 | 長時間任務、減少提示疲勞 |
| [`dontAsk`](#allow-only-pre-approved-tools-with-dontask-mode) | 工作目錄內的檔案讀取及預先核准的工具；任何原本會提示的操作都會被拒絕，不過您安裝的 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md) 仍可核准其中部分呼叫 | 受嚴格限制的 CI 與指令碼 |
| [`bypassPermissions`](#skip-all-checks-with-bypasspermissions-mode) | 所有操作 | 僅限隔離的容器與虛擬機器 |

審查每項操作的模式在 CLI、`claude --help`、VS Code 與 JetBrains 擴充功能，以及桌面應用程式中稱為 **Manual**。其設定值為 `default`，這是 hook 與 SDK 整合所使用的值。在任何需要輸入該值的地方，CLI 都接受 `manual` 作為別名，例如 `claude --permission-mode manual` 或 `"defaultMode": "manual"`。

對[受保護路徑](#protected-paths)的寫入永遠不會被自動核准，唯一的例外是 `bypassPermissions` 模式，以及可使用略過權限的 plan mode 工作階段；後者指的是以[將 `bypassPermissions` 加入模式循環](#switch-permission-modes)的方式啟動的互動式終端機工作階段。

模式設定的是基準。您可以在其上疊加[權限規則](https://code.claude.com/docs/zh-TW/permissions.md#manage-permissions)，以預先核准或封鎖特定工具。拒絕規則在每種模式中都會生效，包括 `bypassPermissions`。只要 Claude 仍至少有一個其他可呼叫的工具，拒絕規則與詢問規則就不適用於 [`EndConversation`](https://code.claude.com/docs/zh-TW/tools-reference#endconversation-tool-behavior)。允許規則在 `bypassPermissions` 中沒有作用。

### 任何模式都不會自動核准的操作

Claude Code 在任何模式中（包括 `bypassPermissions`）都不會自動核准下列操作，不過您可以在 `bypassPermissions` 模式中[關閉危險 `rm` 命令的提示](#turn-off-the-critical-path-removal-prompt-in-bypasspermissions-mode)。每個項目都連結至說明各模式中實際會發生什麼情況的章節：

* 符合明確[詢問規則](https://code.claude.com/docs/zh-TW/permissions.md#manage-permissions)的工具
* 您的組織[設定為 `ask`](https://code.claude.com/docs/zh-TW/mcp#organization-controls-on-connector-tools) 的連接器工具，適用於該設定會傳達至 Claude Code 的工作階段
* 需要使用者互動的工具：內建的 `AskUserQuestion` 工具，以及標記為 [`requiresUserInteraction`](https://code.claude.com/docs/zh-TW/mcp#require-approval-for-a-specific-tool) 的 MCP 工具
* 經識別的 `rm` 與 `rmdir` [關鍵路徑刪除](#critical-paths)（任何允許規則或 `PreToolUse` hook 的 `"allow"` 都無法核准），以及被標記為 [`Dangerous rm operation not ruled out`](#dangerous-rm-operation-not-ruled-out) 的 Bash 命令
* [跨工作階段訊息傳遞保護措施](#skip-all-checks-with-bypasspermissions-mode)
* 在 [`permissions.blockReadsOutsideWorkingDirectories`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-blockreadsoutsideworkingdirectories) 開啟時，對工作目錄以外位置的讀取：經識別的檔案讀取 Bash 命令即使在自動模式與 `bypassPermissions` 模式中也會提示，任何需要核准才能在沙箱外執行的[非沙箱重試](https://code.claude.com/docs/zh-TW/sandboxing.md#the-unsandboxed-retry-escape-hatch)也是如此。需要 Claude Code v2.1.257 或更新版本。

  shell 剖析器無法追蹤的命令，例如多次變更目錄或執行子 shell 的命令，即使未指定任何外部路徑，也會以相同方式提示。當命令在[沙箱](https://code.claude.com/docs/zh-TW/sandboxing.md)中執行且由沙箱強制執行該封鎖時，此提示不適用。
* 在 [`permissions.blockWritesOutsideWorkingDirectories`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-blockwritesoutsideworkingdirectories) 開啟時，對工作目錄以外位置的寫入：Claude Code 會拒絕在該處的 `Write`、`Edit` 與 `NotebookEdit` 呼叫，但[其自身的部分檔案](https://code.claude.com/docs/zh-TW/settings-reference.md#what-the-write-block-refuses-and-what-stays-writable)除外。此設定鍵不會限制 shell 命令、MCP 工具或 hook 執行的程式，因此請使用[沙箱機制](https://code.claude.com/docs/zh-TW/sandboxing.md)來限制 shell 命令的寫入位置。需要 Claude Code v2.1.314 或更新版本。

## 常見設定

權限模式決定 Claude 是否在操作前詢問，而 [Bash 沙箱](https://code.claude.com/docs/zh-TW/sandboxing.md)和外部[隔離邊界](https://code.claude.com/docs/zh-TW/sandbox-environments.md)決定操作執行後可以到達什麼。下表中的每一行將目標與讓您到達該目標的旗標或設定以及所需的隔離配對，作為起點。[可用的模式](#available-modes)列出在每種模式中無需提示即可執行的操作。

| 您想要 | 開始使用 | 所需的隔離 | 注意 |
| :- | :- | :- | :- |
| 自己審查每個操作 | Manual 模式：`claude --permission-mode default` | 無 | 敏感工作、不熟悉的程式碼 |
| 在本地迭代，提示更少，無需分類器 | Manual 模式加上 Bash 沙箱在[自動允許模式](https://code.claude.com/docs/zh-TW/sandboxing.md#sandbox-modes)中：`claude --permission-mode default`，然後執行 `/sandbox` 並選擇自動允許 | 內建 Bash 沙箱，在 macOS、Linux 和 WSL2 上 | 拒絕規則仍然適用，詢問規則命名命令（例如 `Bash(git push *)`）仍然提示。[自動允許模式](https://code.claude.com/docs/zh-TW/sandboxing.md#auto-allow-mode)涵蓋其他可能提示的命令。若要改為從設定檔開啟沙箱，請將 [`sandbox.enabled`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-enabled) 設定為 `true` |
| 在變更任何內容前探索 | `claude --permission-mode plan` | 無 | Claude Code 會阻止編輯，直到您[批准計畫](#review-and-approve-a-plan) |
| 在自動模式中無人值守工作 | `claude --permission-mode auto`、[內建起始權限模式](#which-mode-a-session-starts-in)（v2.1.283 或更新版本） | 無；沙箱或容器增加深度防禦 | 需要[支援的模型](#eliminate-prompts-with-auto-mode)，您的組織可以[關閉自動模式](#eliminate-prompts-with-auto-mode) |
| 在 CI 中使用精確允許清單執行 | `claude -p "run the test suite" --permission-mode dontAsk --allowedTools "Bash(npm test)" "Read"` | 無，超出您的 CI 執行器提供的 | [雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)忽略設定檔中的 `dontAsk` |
| 在容器內完全無人值守執行 | `claude -p "<prompt>" --dangerously-skip-permissions` | 必需：容器、虛擬機或[沙箱執行時](https://code.claude.com/docs/zh-TW/sandbox-environments.md#sandbox-runtime)；在 Linux 和 macOS 上，以[非 root 使用者](#skip-all-checks-with-bypasspermissions-mode)執行 | 雲端工作階段忽略設定檔中的此模式。在此 `-p` 執行中，[仍會提示的少數呼叫](#skip-all-checks-with-bypasspermissions-mode)會被拒絕 |

Bash 沙箱和自動模式獨立工作並結合，除了[沙箱模式](https://code.claude.com/docs/zh-TW/sandboxing.md#sandbox-modes)下列出的例外。如需完整互動，請參閱[沙箱化如何與權限和權限模式相關](https://code.claude.com/docs/zh-TW/sandboxing.md#how-sandboxing-relates-to-permissions-and-permission-modes)和[隔離如何與權限模式相關](https://code.claude.com/docs/zh-TW/sandbox-environments.md#how-isolation-relates-to-permission-modes)。

## 工作階段在哪個模式中啟動

當您在終端機中啟動新工作階段時，Claude Code 會從適用的第一個中取得權限模式：

1. `--permission-mode` 旗標或 `--dangerously-skip-permissions`

2. [設定檔](https://code.claude.com/docs/zh-TW/settings.md#where-settings-live)中的 `permissions.defaultMode`

   如果您在 `.claude/settings.json` 或 `.claude/settings.local.json` 中設定 `"auto"`，該值不會生效，Claude Code 會改為使用內建預設值而不是來自 `~/.claude/settings.json` 的 `defaultMode`。如果您在這兩個檔案中設定 `"bypassPermissions"`，它也不會生效，工作階段會以 Manual 模式啟動。其他值適用於任何設定檔。

3. 內建預設值

VS Code 擴充功能啟動的對話遵循[切換權限模式](#switch-permission-modes)中的擴充功能自身清單。如需 Claude Code 在恢復工作階段時啟動的權限模式，請參閱[恢復時的權限模式](https://code.claude.com/docs/zh-TW/sessions.md#permission-mode-on-resume)。

內建 `auto` 預設在 macOS、Linux 和 WSL 上需要 Claude Code v2.1.228 或更新版本，在原生 Windows 上需要 v2.1.233 或更新版本。在較早的版本上，內建預設是 Manual。

內建預設取決於您如何執行 Claude Code。符合的第一行適用。該表涵蓋您在終端機或透過 VS Code 擴充功能啟動的工作階段；對於桌面應用程式和 claude.ai，請參閱[切換權限模式](#switch-permission-modes)中的 Desktop 和 Web 標籤。

| 您如何執行 Claude Code | 內建起始權限模式 |
| :- | :- |
| 任何設定檔將 `disableAutoMode` 設定為 `"disable"` | `default` |
| `claude -p` 或 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#permission-modes) | `default` |
| 您的組織已套用 [HIPAA 設定](#hipaa-configuration)，且工作階段[符合其適用條件](https://code.claude.com/docs/zh-TW/hipaa-setup.md#check-how-developers-sign-in-and-connect) | Claude Code v2.1.285 或更新版本上為 `default`；仍可切換到自動模式 |
| 在終端機或透過 [VS Code 擴充功能](https://code.claude.com/docs/zh-TW/vs-code.md) | Claude Code v2.1.283 或更新版本上的 `auto`；在較早的版本上，Pro、Max、Ultra 或 Team 方案上的 `auto`（在[擷取功能旗標](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)的工作階段中），否則為 `default` |

當旗標、設定檔或內建預設選擇 `auto` 但自動模式對工作階段不可用時，Claude Code 會改為以 Manual 啟動工作階段。當工作階段不符合[可用性要求](#eliminate-prompts-with-auto-mode)時，自動模式不可用，例如設定檔關閉它或不支援它的模型，或當 Anthropic 已在伺服器端暫時關閉它時。

內建預設第一次在自動模式中啟動您的工作階段時，Claude Code 會顯示連結到此頁面的通知：

* 在終端機中，一次，在工作階段頂部
* 在 VS Code 擴充功能中，作為新對話螢幕上的卡片，直到您關閉它

如果您的 `~/.claude/settings.json` 將 `defaultMode` 設定為 `auto` 以外的值，且沒有其他設定檔設定它，您的工作階段會繼續以該模式啟動。

在 Pro、Max、Ultra 和 Team 方案上，以及在[不擷取功能旗標](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)的工作階段中，Claude Code 會詢問一次是否將設定變更為自動模式。此問題會顯示在終端機或 VS Code 擴充功能中，如果您拒絕，您的設定會保持原樣。

### 在 `claude -p` 和 Agent SDK 執行中被拒絕的工具呼叫

在 Claude Code v2.1.302 或更新版本中，[未設定權限模式](#which-mode-a-session-starts-in)的 `claude -p` 和 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#permission-modes) 執行會以 Manual 模式啟動。此模式在 SDK 選項和設定中顯示為 `default`。需要核准的呼叫會被拒絕，除非您透過允許規則、hook、`canUseTool` 回呼或 `--permission-prompt-tool` 核准它們。

若要讓這些呼叫獲得核准，請新增允許規則或以自動模式啟動：

* **[新增允許規則](https://code.claude.com/docs/zh-TW/permissions.md#manage-permissions)**：Claude 會執行您列出的呼叫。將 [`--allowedTools "Bash(npm test)"`](https://code.claude.com/docs/zh-TW/headless#auto-approve-tools) 傳遞給 `claude -p`，或設定您 SDK 的[允許工具選項](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#allow-and-deny-rules)。
* **以[自動模式](#eliminate-prompts-with-auto-mode)啟動**：分類器模型會審查呼叫，因此您無需事先列出任何內容。將 `--permission-mode auto` 傳遞給 `claude -p`，或設定您 SDK 的[權限模式選項](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#set-permission-mode)。

以下範例顯示 CLI 和各 SDK 的自動模式寫法：

> [tab] CLI
>
> ```bash theme={null}
> claude -p "Run the test suite and fix any failures" --permission-mode auto
> ```

> [tab] TypeScript
>
> ```typescript theme={null}
> const options = {
>   permissionMode: "auto"
> };
> ```

> [tab] Python
>
> ```python theme={null}
> from claude_agent_sdk import ClaudeAgentOptions
>
> options = ClaudeAgentOptions(permission_mode="auto")
> ```

在 v2.1.302 之前，如果這些執行不[擷取功能旗標](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)，例如在[第三方提供者](https://code.claude.com/docs/zh-TW/third-party-integrations.md)上或使用 `DISABLE_TELEMETRY` 時，可能會以自動模式啟動。

### 以不同的權限模式啟動

您可以為一個工作階段、或作為機器、專案或組織中每個工作階段的預設值設定起始權限模式。當多個設定檔設定 `permissions.defaultMode` 時，[設定優先順序](https://code.claude.com/docs/zh-TW/settings.md#settings-precedence)決定，因此專案或受管值優先於 `~/.claude/settings.json`。若要變更已執行工作階段的權限模式，請參閱[切換權限模式](#switch-permission-modes)。

| 若要為以下設定起始權限模式 | 執行此操作 |
| :- | :- |
| 您即將啟動的一個工作階段 | 將權限模式作為旗標傳遞，例如 `claude --permission-mode default` |
| 您在此機器上啟動的每個終端機工作階段 | 在 `~/.claude/settings.json` 中設定 `permissions.defaultMode`。如需 VS Code 擴充功能讀取的內容，請參閱[切換權限模式](#switch-permission-modes) |
| 您在一個專案中啟動的每個終端機工作階段 | 在專案的 `.claude/settings.json` 中設定 `permissions.defaultMode`。您在終端機中啟動的工作階段遵守除 `auto` 和 `bypassPermissions` 外的每個值；VS Code 擴充功能啟動的工作階段不讀取專案設定以取得起始權限模式 |
| 您組織中的每個終端機工作階段 | 在[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)中設定 `permissions.defaultMode`。終端機工作階段以該模式啟動，人們仍然可以切換到自動模式；如需 VS Code 擴充功能讀取的內容，請參閱[切換權限模式](#switch-permission-modes)。若要移除自動模式以便沒有人可以選擇它，請改為將 `permissions.disableAutoMode` 設定為 `"disable"` |

此範例使您機器上的每個終端機工作階段以 Manual 模式啟動，其設定值為 `default`。將其儲存在 `~/.claude/settings.json` 中：

```json theme={null}
{
  "permissions": {
    "defaultMode": "default"
  }
}
```

您啟動的下一個工作階段會在狀態列中顯示 `⏸ manual mode on`。

### HIPAA 設定下的權限模式

在已套用 [HIPAA 設定](https://code.claude.com/docs/zh-TW/hipaa-setup.md)的組織中，內建 `auto` 預設不適用。當沒有其他項目選擇起始權限模式時，終端機或 VS Code 工作階段會以 Manual 模式啟動。終端機工作階段還會顯示 `Auto mode isn't the default for your organization · Shift+Tab to switch`，而 VS Code 擴充功能不會顯示通知。[檢查開發人員如何登入和連線](https://code.claude.com/docs/zh-TW/hipaa-setup.md#check-how-developers-sign-in-and-connect)列出了適用此情況的工作階段。

自動模式和 `bypassPermissions` 仍然可用：

* **切換到自動模式**：按 `Shift+Tab`，或使用[您介面的控制項](#switch-permission-modes)
* **以自動模式啟動**：傳遞 `--permission-mode auto`，或在您的使用者設定中將 `permissions.defaultMode` 設定為 `auto`，或在受管設定中為整個組織設定。請參閱[以不同的權限模式啟動](#start-in-a-different-mode)
* **移除自動模式**：在受管設定中將 [`permissions.disableAutoMode`](https://code.claude.com/docs/zh-TW/settings-reference#disableautomode) 設定為 `"disable"`
* **封鎖 `bypassPermissions`**：在受管設定中將 [`permissions.disableBypassPermissionsMode`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-disablebypasspermissionsmode) 設定為 `"disable"`

需要 Claude Code v2.1.285 或更新版本，即 [HIPAA 設定的最低版本](https://code.claude.com/docs/zh-TW/hipaa-setup.md#update-claude-code-and-claude-desktop)。

## 切換權限模式

每個介面都有自己的控制項用於在工作階段期間切換權限模式，以及自己的方式來選擇新工作階段啟動的權限模式。選擇您的介面以查看其控制項。

> [tab] CLI
>
> **在工作階段期間**：按 `Shift+Tab` 循環切換權限模式。從 `auto`，第一次按下切換到 `default`，循環然後執行 `default` → `acceptEdits` → `plan`。可選模式在 `plan` 之後插入。狀態列將活動模式顯示為 `default` 的灰色 `⏸ manual mode on`，或作為 `⏵⏵ accept edits on`、`⏸ plan mode on`、`⏵⏵ auto mode on`、`⏵⏵ don't ask on` 或 `⏵⏵ bypass permissions on`。
>
> 請觀察此片段中以自動模式啟動的工作階段的狀態列。每次按下 `Shift+Tab`，它會從 `auto mode on` 變更為 `manual mode on`、`accept edits on`、`plan mode on`，然後回到 `auto mode on`。
>
> <video autoPlay muted loop playsInline src="https://mintcdn.com/claude-code/tA-x-5L2YsYSVdee/images/permission-modes-cycle-light.mp4?fit=max&auto=format&n=tA-x-5L2YsYSVdee&q=85&s=3927dd62d59b01efd81b3578f2a6f971" aria-label="Claude Code 提示詞下方的狀態列隨著每次按下 Shift+Tab 而變更：auto mode on、manual mode on、accept edits on、plan mode on，然後再次回到 auto mode on。" />
>
> 並非每個模式都在預設循環中：
>
> * `auto`：當[自動模式可用](#eliminate-prompts-with-auto-mode)時出現；循環切換到它會在不需要確認提示的情況下切換模式
> * `bypassPermissions`：在您使用 `--permission-mode bypassPermissions`、`--dangerously-skip-permissions`、`--allow-dangerously-skip-permissions` 或[使用者、`--settings` 或受管設定](https://code.claude.com/docs/zh-TW/settings-reference#permissions-defaultmode)中的 `permissions.defaultMode: "bypassPermissions"` 啟動後出現。`--allow-` 變體將權限模式新增到循環中而不啟動它
> * `dontAsk`：永遠不會在循環中出現；使用 `--permission-mode dontAsk` 設定它
>
> 啟用的可選模式在 `plan` 之後插入，`bypassPermissions` 優先，`auto` 最後。如果您同時啟用了兩者，您將在循環到 `auto` 的途中循環通過 `bypassPermissions`。
>
> **從 Bash 權限提示**：在 Manual 和 `acceptEdits` 權限模式中，當[自動模式](#eliminate-prompts-with-auto-mode)可用時，Claude Code 會將**是的，並切換到自動模式**新增到 Bash 命令的權限提示。選擇它以批准命令並將工作階段切換到自動模式。[PowerShell 工具](https://code.claude.com/docs/zh-TW/tools-reference.md#powershell-tool)提示不提供該選項。需要 Claude Code v2.1.247 或更新版本。
>
> Claude Code 不會將該選項新增到由您的[`ask` 規則](https://code.claude.com/docs/zh-TW/permissions#manage-permissions)之一或[hook](https://code.claude.com/docs/zh-TW/hooks.md#pretooluse-decision-control)強制的提示，因為自動模式仍會向您顯示這些提示，因此切換不會移除它們。
>
> **在啟動時**：將權限模式作為旗標傳遞。
>
> ```bash theme={null}
> claude --permission-mode plan
> ```
>
> **作為預設值**：在您想要的範圍設定 `permissions.defaultMode`，如[以不同的權限模式啟動](#start-in-a-different-mode)中所述。
>
> 相同的 `--permission-mode` 旗標適用於 `-p` 用於[非互動式執行](https://code.claude.com/docs/zh-TW/headless.md)。

> [tab] VS Code
>
> **在工作階段期間**：點擊提示框底部的模式指示器。它對此頁面上的模式使用這些標籤：
>
> | UI 標籤 | 模式 |
> | :- | :- |
> | Manual | `default` |
> | Edit automatically | `acceptEdits` |
> | Plan | `plan` |
> | Auto | `auto` |
> | Bypass permissions | `bypassPermissions` |
>
> **作為預設值**：若要固定對話啟動的權限模式，請在 VS Code 使用者設定中將 `claudeCode.initialPermissionMode` 設定為 `default`、`manual`、`acceptEdits`、`plan` 或 `bypassPermissions`。該設定不接受 `auto`；若要以 Auto 啟動，請將其保留未設定，並從模式指示器中選擇**Auto**一次，如下面第 2 項所述。擴充功能在適用的第一個中啟動每個新對話：
>
> 1. `claudeCode.initialPermissionMode`
> 2. 您上次從模式指示器選擇的模式，如果它是 Manual、Edit automatically 或 Auto。選擇 Plan 或 Bypass permissions 僅適用於該對話
> 3. 來自[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)或 `~/.claude/settings.json` 的 `permissions.defaultMode`
> 4. 您的方案、提供者和組織設定的[內建預設](#which-mode-a-session-starts-in)
>
> 擴充功能永遠不會從專案的 `.claude/settings.json` 或 `.claude/settings.local.json` 讀取起始權限模式。當設定 `claudeCode.claudeProcessWrapper` 時，第 3 和 4 項也不適用：這些對話以 Manual 啟動，除非第 1 或 2 項設定權限模式。
>
> 在 v2.1.283 之前，第 3 項僅在 Pro、Max、Ultra 和 Team 方案上適用於[擷取功能旗標](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)的工作階段。
>
> 當[自動模式可用](#eliminate-prompts-with-auto-mode)時，Auto 會在模式指示器中出現。
>
> Bypass permissions 需要擴充功能設定中的 **Allow dangerously skip permissions** 切換。沒有它，權限模式不會在指示器中出現，來自第 1 或 3 項的 `bypassPermissions` 值會改為以 Manual 啟動對話。當自動模式不可用時，來自任何項的 Auto 同樣會以 Manual 啟動對話。
>
> 請參閱 [VS Code 指南](https://code.claude.com/docs/zh-TW/vs-code.md)以取得擴充功能特定的詳細資訊。

> [tab] JetBrains
>
> JetBrains 外掛程式在 IDE 終端機中執行 Claude Code，因此切換權限模式的方式與 CLI 中相同：按 `Shift+Tab` 循環切換，或在啟動時傳遞 `--permission-mode`。

> [tab] Desktop
>
> **在工作階段期間**：在 Code 標籤中，使用提示詞輸入框下方那一列中的模式選擇器。並非每個模式都會在選擇器中出現：
>
> * **Auto**：當[自動模式可用](#eliminate-prompts-with-auto-mode)時出現
> * **Bypass permissions**：在 Pro、Max 和 Ultra 方案上需要 Desktop 設定中的 **Allow bypass permissions mode** 切換；在 Team 和 Enterprise 方案上，組織政策改為控制它
>
> Cowork 不使用這些模式。它有自己的權限模式，需另外啟用，而且在為您的帳戶啟用超出其預設值的模式之前，完全不會顯示模式選擇器。請參閱 [Cowork 文件](https://claude.com/docs/cowork/overview)。
>
> 如需桌面特定的詳細資訊，請參閱 Desktop 指南中的[選擇權限模式](https://code.claude.com/docs/zh-TW/desktop.md#choose-a-permission-mode)。
>
> **作為預設值**：在[設定](https://code.claude.com/docs/zh-TW/settings.md#where-settings-live)中設定 `defaultMode`。桌面應用程式讀取與 CLI 相同的設定檔，並將權限模式套用到新的本機工作階段。
>
> 您在模式選擇器中選擇的模式會按資料夾記住，並優先於該資料夾的 `defaultMode`。Plan 是例外：選擇它僅適用於目前工作階段。
>
> 如需 `defaultMode` 在設定檔中的位置，請參閱[以不同的權限模式啟動](#start-in-a-different-mode)下的範例。

> [tab] Web and mobile
>
> 在 [claude.ai/code](https://claude.ai/code) 上，使用提示詞輸入框下方那一列中的模式下拉式選單。在行動應用程式中，點選提示詞輸入框中的 **+** 按鈕，然後點選 **Permission**。雲端工作階段和 Remote Control 工作階段提供不同的權限模式：
>
> * **[Cloud sessions](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)**：接受編輯、Plan 和 Auto。接受編輯對應於 `default` 模式：雲端工作階段預先核准檔案編輯，無論模式為何，因此下拉式選單會顯示接受編輯而不是 Manual。雲端工作階段仍然遵守設定中的 `defaultMode: "acceptEdits"`。Auto 模式僅在您的組織允許且選定的模型支援時出現。Bypass permissions 不可用。
> * **[Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) sessions** 在您的本機機器上：Manual、接受編輯、Plan 和 Auto（適用於您自己啟動的工作階段），您無法從應用程式選擇 Bypass permissions。若要使用 Auto，工作階段必須符合自動模式的[可用性要求](#eliminate-prompts-with-auto-mode)。如需在您的電腦上執行的專案執行緒，請參閱[在您自己的電腦上執行執行緒](https://code.claude.com/docs/zh-TW/claude-projects.md#run-a-thread-on-your-own-computer)。
>   * 除了 Bypass permissions，下拉式選單顯示本機工作階段所在的權限模式，包括從終端機設定的模式。它在應用程式或終端機中權限模式變更時更新。
>   * 由[桌面應用程式](https://code.claude.com/docs/zh-TW/desktop.md)或 [VS Code 擴充功能](https://code.claude.com/docs/zh-TW/vs-code.md)託管的工作階段在權限模式變更時向 claude.ai 報告，與在終端機中託管的工作階段相同。
>
> 對於 Remote Control，執行工作階段的本機機器必須使用您的 claude.ai 帳戶登入；不支援 API 金鑰。您也可以在啟動該本機工作階段時設定起始權限模式：
>
> ```bash theme={null}
> claude remote-control --permission-mode acceptEdits
> ```

## 使用 acceptEdits 模式自動批准檔案編輯

`acceptEdits` 模式讓 Claude 在您的工作目錄中建立和編輯檔案，無需提示。當此模式處於活動狀態時，狀態列會顯示 `⏵⏵ accept edits on`。

除了檔案編輯外，`acceptEdits` 模式還會自動批准常見的檔案系統 Bash 命令：`mkdir`、`touch`、`rm`、`rmdir`、`mv`、`cp` 和 `sed`。除了 `touch` 之外，當這些命令以安全環境變數（例如 `LANG=C` 或 `NO_COLOR=1`）或程序包裝器（例如 `timeout`、`nice` 或 `nohup`）作為前綴時，也會自動批准。與檔案編輯一樣，自動批准僅適用於工作目錄或 `additionalDirectories` 內的路徑。

以下情況仍會提示：

* 超出該範圍的路徑
* 寫入[受保護路徑](#protected-paths)
* 可辨識的 `rm` 和 `rmdir` [關鍵路徑移除](#critical-paths)
* `touch` 搭配純檔案路徑以外的任何內容，例如選項、glob，或 `timeout 5`、`LANG=C` 等前綴
* 所有其他 Bash 命令（除了[內建唯讀集合](https://code.claude.com/docs/zh-TW/permissions.md#read-only-commands)）

每個路徑也會經過[符號連結檢查](https://code.claude.com/docs/zh-TW/permissions.md#symlinks)，因此解析到該範圍外的寫入也不會自動批准。

當[PowerShell 工具](https://code.claude.com/docs/zh-TW/tools-reference.md#powershell-tool)啟用時，`acceptEdits` 模式也會自動批准 `Set-Content`、`Add-Content`、`Clear-Content` 和 `Remove-Item` 在範圍內的路徑上，以及它們的常見別名。相同的範圍和受保護路徑規則適用，`Remove-Item` 有[自己的檢查](#remove-item-in-powershell)。包含引號字元的位置引數（例如 `Set-Content .\notes.txt "It's done"` 中的撇號）仍會在範圍內路徑上提示，因為 Claude Code 無法靜態驗證其引用和未引用讀數不同的引數。透過命名參數（例如 `-Value`）傳遞內容以避免提示。

當您想在編輯器中或透過 `git diff` 事後檢查變更，而不是逐個批准每個編輯時，請使用 `acceptEdits`。

從 Manual 模式按一次 `Shift+Tab` 進入它，或直接啟動它：

```bash theme={null}
claude --permission-mode acceptEdits
```

## 使用 plan mode 在編輯前進行分析

Plan mode 會讓 Claude 研究並提出變更，但不實際執行這些變更。Claude 會讀取檔案、執行 shell 命令進行探索並撰寫計畫，但不會編輯您的原始碼。除了在[可使用略過權限](#skip-all-checks-with-bypasspermissions-mode)的互動式終端機工作階段中之外，編輯會一直被封鎖，直到您核准計畫為止。

規劃期間 shell 命令的處理方式取決於工作階段，以下情況中第一個符合者適用：

* **可使用略過權限的互動式終端機工作階段**：分類器和權限提示都不適用於規劃命令。[使用 bypassPermissions 模式略過所有檢查](#skip-all-checks-with-bypasspermissions-mode)說明了在該模式下仍會提示的少數情況。
* **可使用[自動模式](https://code.claude.com/docs/zh-TW/auto-mode-config.md)且 `useAutoModeDuringPlan` 設定已開啟**（預設為開啟）：分類器會審查[關鍵路徑移除](#critical-paths)以外的 shell 命令，而不是提示您。核准的命令會執行，遭拒絕的命令則會被封鎖。
* **無法使用自動模式，或 `useAutoModeDuringPlan` 已關閉**：[內建唯讀命令集](https://code.claude.com/docs/zh-TW/permissions.md#read-only-commands)以外的命令會提示要求核准，即使已啟用沙箱的[自動允許模式](https://code.claude.com/docs/zh-TW/sandboxing.md#sandbox-modes)也是如此。

按下 `Shift+Tab` 或在單一提示詞前加上 `/plan` 即可進入 plan mode。您也可以從 CLI 以 plan mode 啟動：

```bash theme={null}
claude --permission-mode plan
```

再次按下 `Shift+Tab` 即可在不核准計畫的情況下離開 plan mode。

### 審查並核准計畫

計畫準備就緒後，Claude 會呈現計畫並詢問如何進行。在該提示中，您可以選擇：

* **Yes, and use auto mode**：核准並以[自動模式](#eliminate-prompts-with-auto-mode)開始。如果[您的工作階段無法使用](#eliminate-prompts-with-auto-mode)自動模式（例如因為您的組織已將其關閉），此選項會顯示為 **Yes, auto-accept edits**。如果您在啟動工作階段時已啟用略過權限，此選項則會顯示為 **Yes, and switch to BYPASS PERMISSIONS (no further prompts) for this session**。
* **Yes, manually approve edits**：核准並逐一審查每項編輯。
* **No, keep planning**：留在 plan mode 並告訴 Claude 要變更的內容。

核准計畫會結束 plan mode，並將工作階段切換為各核准選項所描述的權限模式，讓 Claude 開始編輯。若要再次規劃，請使用 `Shift+Tab` 循環切換回 plan mode，或在下一個提示詞前加上 `/plan`。

按下 `Ctrl+G` 可在您的預設文字編輯器中開啟提議的計畫，並在 Claude 繼續之前直接編輯。啟用 [`showClearContextOnPlanAccept`](https://code.claude.com/docs/zh-TW/settings-reference#showclearcontextonplanaccept) 時，清單會新增第一個選項，用於核准計畫並清除規劃內容。

接受計畫也會根據該計畫為工作階段產生[標題](https://code.claude.com/docs/zh-TW/sessions.md#name-your-sessions)，除非您已為工作階段命名。

### 將 plan mode 設為預設

若要將 plan mode 設為專案終端機工作階段的預設模式，請在 `.claude/settings.json` 中將 `defaultMode` 設為 `plan`，放置方式如[以不同的權限模式啟動](#start-in-a-different-mode)下的範例所示。由 [VS Code 擴充功能](https://code.claude.com/docs/zh-TW/vs-code.md)啟動的對話不會從專案設定讀取起始權限模式。在該情況下，請改為在您的 VS Code 使用者設定中將 `claudeCode.initialPermissionMode` 設為 `plan`。

## 使用自動模式消除權限提示

自動模式讓 Claude 無需例行權限提示即可執行。一個獨立的分類器模型在操作執行前進行審查，阻止任何超出您請求範圍、針對無法識別的基礎設施或似乎由 Claude 讀取的惡意內容驅動的操作。明確的[詢問規則](https://code.claude.com/docs/zh-TW/permissions.md#manage-permissions)仍會強制提示。

使用 Claude Code v2.1.283 或更新版本，自動模式是所有計畫和提供商上互動式終端機和 VS Code 工作階段的[內建起始權限模式](#which-mode-a-session-starts-in)。在較早版本上，它僅在 Pro、Max、Ultra 和 Team 計畫上是內建起始權限模式。

分類器也會在 Claude Code 傳遞 Claude 使用 [`SendMessage`](https://code.claude.com/docs/zh-TW/tools-reference) 向另一個 agent 傳送的每條訊息之前進行審查，無論是純文字還是結構化的 [agent team](https://code.claude.com/docs/zh-TW/agent-teams.md) 訊息，在自動模式和[分類器審查命令時的 plan mode](#analyze-before-you-edit-with-plan-mode) 中都會進行審查；傳送審查需要 Claude Code v2.1.222 或更新版本。

預設情況下，分類器不審查可識別的針對關鍵路徑的 `rm` 和 `rmdir` 移除，例如 `rm -rf /` 或 `rm -rf ~`。[關鍵路徑](#critical-paths)涵蓋在每個權限模式中對它們的處理。

自動模式也會促使 Claude 繼續工作而不停下來提出澄清問題，儘管當您的提示詞或 skill 明確依賴它時 Claude 仍會詢問。為了在仍會提示您的模式中獲得更強的自主行為，請改為設定[主動輸出風格](https://code.claude.com/docs/zh-TW/output-styles.md)。

> [!WARNING]
>
> 自動模式減少了權限提示，但不保證安全。將其用於您信任大致方向的任務，而不是作為敏感操作審查的替代品。

自動模式僅在您的帳戶滿足所有這些要求時才可用：

* **計畫**：所有計畫。
* **組織**：在 Team 和 Enterprise 上，自動模式預設可用。管理員可以透過在[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)中將 `permissions.disableAutoMode` 設定為 `"disable"` 來為組織關閉它。
* **模型**：在 Anthropic API 和 [AWS 上的 Claude Platform](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md) 上，Claude Opus 4.6 或更新版本、Sonnet 4.6 或更新版本、Haiku 5.5，或 [Fable 模型](https://code.claude.com/docs/zh-TW/model-config.md#work-with-fable)。在 Amazon Bedrock、Google Cloud 的 Agent Platform、Microsoft Foundry 和已登入的 [Claude 應用程式閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)工作階段上，僅限 Claude Sonnet 5 或更新版本、Opus 4.7 或更新版本、Haiku 5.5 和 Fable 模型。較舊的模型，包括 Sonnet 4.5、Opus 4.5、Haiku 4.5 和 claude-3 模型，在任何提供商上都不受支援。
* **提供商**：在 Anthropic API、AWS 上的 Claude Platform、Amazon Bedrock、Google Cloud 的 Agent Platform、Microsoft Foundry 和已登入的 Claude 應用程式閘道工作階段上預設可用。

如果 Claude Code 報告自動模式不可用，首先檢查這些要求以及任何設定檔是否設定了 [`disableAutoMode`](https://code.claude.com/docs/zh-TW/settings-reference#disableautomode)。Anthropic 也可能已在伺服器端關閉自動模式，或伺服器可能已為您的帳戶拒絕自動模式。收到任一答案的工作階段會保持自動模式關閉直到工作階段結束，因此請稍後啟動新工作階段。

另一則指明某個模型並表示自動模式「無法確定」某個操作安全性的訊息，意味著分類器請求失敗。該失敗通常是暫時的，但在 Amazon Bedrock 上，它可能會重複發生，直到您的帳戶可以呼叫所指明的模型。請參閱[錯誤參考](https://code.claude.com/docs/zh-TW/errors.md#auto-mode-cannot-determine-the-safety-of-an-action)以了解原因和應對方法。

如果您在[設定](https://code.claude.com/docs/zh-TW/settings-reference.md#all-settings)中設定 `defaultMode: "auto"`，而終端機工作階段在沒有錯誤的情況下以手動模式啟動，該設定可能位於 `.claude/settings.json` 或 `.claude/settings.local.json` 中。`auto` 不會從這些檔案生效。請將其移至 `~/.claude/settings.json`。對於 VS Code 擴充功能啟動的對話，請改為檢查[切換權限模式](#switch-permission-modes)中該擴充功能自己的清單。

### Bedrock、Agent Platform 或 Foundry 上的自動模式

在 [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md)、[Google Cloud 的 Agent Platform](https://code.claude.com/docs/zh-TW/google-vertex-ai.md)、[Microsoft Foundry](https://code.claude.com/docs/zh-TW/microsoft-foundry.md) 和已登入的 [Claude 應用程式閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)工作階段上，自動模式預設可用。如果您未在這些環境中設定權限模式，互動式工作階段會以自動模式啟動，而 `claude -p` 或 Agent SDK 執行會以手動模式啟動，其設定值為 `default`：

* **互動式終端機和 VS Code 工作階段**：若要以自動模式以外的權限模式啟動這些工作階段，請按照[以不同權限模式啟動](#start-in-a-different-mode)的說明設定 `permissions.defaultMode`，或從 VS Code 擴充功能的[模式指示器](#switch-permission-modes)中選擇一個。[工作階段以哪種模式啟動](#which-mode-a-session-starts-in)列出了以自動模式啟動這些工作階段的 Claude Code 版本。
* **`claude -p` 和 Agent SDK 執行**：若要以自動模式啟動，請將 `--permission-mode auto` 傳遞給 `claude -p`，或在 TypeScript 中傳遞 `permissionMode: "auto"`、在 Python 中傳遞 `permission_mode="auto"`。如果您未傳遞權限模式，請參閱[`claude -p` 和 Agent SDK 執行中被拒絕的工具呼叫](#which-mode-a-non-interactive-run-starts-in)，其中也涵蓋較早的 Claude Code 版本。

這些提供商上僅支援 Claude Sonnet 5 或更新版本、Opus 4.7 或更新版本、Haiku 5.5 和 Fable 模型。在任何其他模型上，工作階段改為以手動模式啟動。在這些提供商上搭配 Haiku 5.5 使用自動模式需要 Claude Code v2.1.293 或更新版本。

要防止開發人員使用自動模式，請在[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)中將 `disableAutoMode` 設定為 `"disable"`。這會從 `Shift+Tab` 循環中移除 `auto`，並且以 `--permission-mode auto` 啟動的工作階段改為以手動模式啟動。已在自動模式中執行的工作階段，在該設定從[管理員部署的來源](https://code.claude.com/docs/zh-TW/managed-settings.md#which-managed-source-claude-code-uses)送達該工作階段時會離開自動模式，並顯示 `auto mode disabled by settings`。在 v2.1.251 之前，執行中的工作階段會保持自動模式直到它結束。

### 伺服器端分類器審查

在自動模式中，Claude Code 可以要求伺服器檢查[決策順序](#how-the-classifier-evaluates-actions)送交審查的操作，作為工作階段模型請求的一部分，而不是發送自己的分類器請求。以下工作階段會提出此要求：

* **直接連接到 Anthropic API**：在互動式終端機工作階段，以及 `-p`、Agent SDK、[VS Code 擴充功能](https://code.claude.com/docs/zh-TW/vs-code.md)和[桌面應用程式](https://code.claude.com/docs/zh-TW/desktop.md)工作階段中，無論您的計畫或帳戶類型為何，隨 Anthropic 逐步推出。請對照以下最低 Claude Code 版本檢查您的工作階段類型：
  * 在互動式終端機工作階段中，在 Pro、Max、Ultra 和 Team 計畫上詢問伺服器需要 Claude Code v2.1.271 或更新版本。在 Enterprise 計畫和 Claude API 帳戶上，這些工作階段需要 v2.1.278 或更新版本。
  * 在 `-p`、Agent SDK、VS Code 擴充功能和桌面應用程式工作階段中，詢問伺服器需要 Claude Code v2.1.281 或更新版本
  * 從 v2.1.282 開始，[不擷取功能旗標](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)的工作階段（例如因為您關閉了遙測），在任何類型的工作階段中都會預設詢問伺服器
* **雲端提供商，或 LLM 閘道或代理伺服器**：在 [AWS 上的 Claude Platform](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md)、Amazon Bedrock、Google Cloud 的 Agent Platform 和 Microsoft Foundry 上，以及每當您將 `ANTHROPIC_BASE_URL` 指向 [LLM 閘道或代理伺服器](https://code.claude.com/docs/zh-TW/llm-gateway)時，無論您的計畫為何。預設詢問需要 Claude Code v2.1.278 或更新版本。
* **已登入的 [Claude 應用程式閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)工作階段**：需要 Claude Code v2.1.280 或更新版本
* **在 Anthropic 託管環境中的[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)**：無論您的計畫為何，當您從網頁、行動應用程式，或在選取 **Cloud** 的情況下從桌面應用程式啟動時。由[雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md)啟動的工作階段會隨 Anthropic 逐步推出而詢問伺服器。

在伺服器審查操作的情況下，由其判決決定這些操作。還有兩種其他可能的結果：

* **伺服器不審查工作階段**：回應完成時沒有審查結果，或伺服器回答它不審查此工作階段。最常見的原因是 LLM 閘道或代理伺服器丟棄了審查請求或結果，以及平台、區域或憑證尚未提供伺服器端檢查。Claude Code 會改用自己的分類器請求。一旦該備援在工作階段的其餘部分持續生效，它會在這些請求會被計費的帳戶上顯示[關於分類器請求費用的通知](https://code.claude.com/docs/zh-TW/auto-mode-classifier-billing.md)。
* **伺服器對操作沒有給出判決**：Claude Code 會拒絕該操作，而不是在未經審查的情況下執行它。在任何連線上，當回應在審查結果到達前結束，或結果以 Claude Code 無法讀取的形式到達時，就會發生這種情況。截斷回應或重寫結果的 LLM 閘道或代理伺服器可能導致任一情況。在直接連接到 Anthropic API 時，當伺服器對該操作的檢查失敗（例如逾時）時也會發生。[伺服器未返回安全判決](https://code.claude.com/docs/zh-TW/errors.md#the-server-returned-no-safety-verdict)涵蓋拒絕訊息、拒絕重複發生時的情況以及應對方法。

  如果 [hook](https://code.claude.com/docs/zh-TW/hooks.md#pretooluse-updatedinput-in-auto-mode) 或 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md) 在伺服器審查後變更了操作的輸入，Claude Code 可能會在沒有判決的情況下拒絕該操作。在直接連接到 Anthropic API 的互動式終端機和 VS Code 工作階段中，拒絕文字會包含 `a hook changed this call's input after auto mode reviewed it`。[其錯誤項目](https://code.claude.com/docs/zh-TW/errors.md#hook-changed-input-after-review)涵蓋應對方法。

要跳過詢問伺服器並始終使用 Claude Code 自己的分類器請求，請設定 [`CLAUDE_CODE_AUTO_MODE_SERVER=0`](https://code.claude.com/docs/zh-TW/env-vars)。在直接連接到 Anthropic API 時，該變數需要 Claude Code v2.1.281 或更新版本。在該情況下將其設定為 `1`，會在尚未啟用伺服器審查的工作階段中開啟伺服器審查，除非您也設定了 `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1`。如果您設定 `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1` 並保持 `CLAUDE_CODE_AUTO_MODE_SERVER` 未設定，Claude Code 也會停止詢問伺服器，但[停用預發行功能](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md#disable-pre-release-capabilities)所述的情況除外。

### 預設分類器模型

預設情況下，分類器請求會送往 Claude Sonnet 5。如果 `/status` 顯示 `Auto mode server` 為 `Enabled`，則僅會針對[伺服器審查](#server-side-classifier-review)範圍以外的呼叫傳送這些請求。

在此表格中找出第一個符合您工作階段的列。您會取得該列的模型，而不是 Sonnet 5。

| 您的工作階段 | 分類器模型 |
| - | - |
| 具有 Anthropic 設定的分類器模型 | 所設定的模型。[檢查除錯日誌](#classifier-model-check)以查看是哪一個 |
| 在 Claude Sonnet 4.6 上執行 | Sonnet 4.6 |
| 已設定 [`ANTHROPIC_DEFAULT_SONNET_MODEL`](https://code.claude.com/docs/zh-TW/model-config#environment-variables) | 其值；若其值為 Claude Sonnet 5.5 或 Claude Opus 5.5，則為 Sonnet 5 |

如果您的提供商無法提供 Sonnet 5 或 `ANTHROPIC_DEFAULT_SONNET_MODEL` 中的模型，或您組織的[模型政策](https://code.claude.com/docs/zh-TW/model-config.md#restrict-model-selection)排除了該模型，Claude Code 會使用備援模型。備援模型是您工作階段的模型，若為 [Fable 工作階段](https://code.claude.com/docs/zh-TW/model-config.md#work-with-fable)則是 Opus 模型。

### 選擇分類器模型

使用 Claude Code v2.1.302 或更新版本時，將 [`CLAUDE_CODE_AUTO_MODE_MODEL`](https://code.claude.com/docs/zh-TW/env-vars) 設定為完整的模型 ID，即可在[預設](#default-classifier-model)以外的模型上執行分類器。您雲端提供商自己的完整模型 ID 也可以使用。此 `~/.claude/settings.json` 範例設定了 Claude Sonnet 4.6：

```json theme={null}
{
  "env": {
    "CLAUDE_CODE_AUTO_MODE_MODEL": "claude-sonnet-4-6"
  }
}
```

#### 當審查者不是您的模型時

| 情況 | 會發生什麼 | 該怎麼做 |
| - | - | - |
| [除錯日誌](#classifier-model-check)回報了 Anthropic 設定的分類器模型 | 由該模型審查 | 無需處理 |
| 您設定了 Claude Opus 5、Sonnet 5.5、Opus 5.5，或您組織的[模型政策](https://code.claude.com/docs/zh-TW/model-config.md#restrict-model-selection)所排除的模型 | 由[預設分類器模型](#default-classifier-model)審查 | 設定其他模型 |
| 您的提供商無法提供該模型 | 分類器檢查失敗，因此 Claude Code [拒絕每個受檢查的操作](https://code.claude.com/docs/zh-TW/errors.md#auto-mode-cannot-determine-the-safety-of-an-action) | 設定提供商可提供的模型，或移除該變數 |
| 在工作階段中，`/status` 顯示 [`Auto mode server`](#server-side-classifier-review) 為 `Enabled` | 由伺服器審查，不使用您的模型 | 無需處理 |

若同時符合多種情況，請以最先列出的為準。

#### 檢查分類器使用的模型

從您的 shell 使用 [`--debug-file`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 啟動自動模式工作階段：

```bash theme={null}
claude --permission-mode auto --debug-file classifier-debug.log
```

讓 Claude 執行一個非唯讀的 shell 命令，然後在日誌中搜尋 `classifier_request_started`：

* **`model=` 後面是您的模型**：該變數已生效
* **`model=` 後面是不同的模型**：在日誌中搜尋 `ignoring CLAUDE_CODE_AUTO_MODE_MODEL`，其中會說明原因以及任何需要採取的步驟
* **沒有這樣的行**：在 Claude Code 提示字元中讀取 `/status` 裡的 `Auto mode server`：
  * **`Enabled`**：[伺服器](#server-side-classifier-review)已設定為審查此工作階段的呼叫。
  * **`Disabled`**：確認[權限模式](#switch-permission-modes)為 auto，然後讓 Claude 執行另一個非唯讀命令。

### 分類器預設阻止的內容

分類器信任您的工作目錄，以及工作階段啟動時為其設定的遠端。在工作階段期間使用 `git remote add` 或 `git remote set-url` 新增或重新指向的遠端不受信任，其他所有內容都被視為外部，直到您[設定受信任的基礎設施](https://code.claude.com/docs/zh-TW/auto-mode-config.md)。

**預設阻止**：

* 下載並執行程式碼，例如 `curl | bash`
* 將敏感資料傳送到外部端點
* 生產部署和遷移
* 雲端儲存上的大量刪除
* 授予 IAM 或儲存庫權限
* 修改共享基礎設施
* 不可逆地銷毀工作階段前已存在的檔案
* 強制推送
* 提交或推送在執行時會將秘密或敏感資料傳送到儲存庫外部，或擴大部署所公開內容的變更。這涵蓋將秘密傳遞到原本未接收該秘密之目的地的 CI 工作流程或部署設定、讀取秘密儲存區並將資料送出的指令碼或設定步驟，以及擴大部署發佈內容的設定變更，例如 registry、可見性、建置產物或 sourcemap 設定。此檢查適用於任何分支，即使儲存庫是公開的也適用，並在提交或推送該變更時觸發，無論該提交或推送是否觸發管線；要解除它，需要指明執行時的效果，而不僅僅是提交或推送
* `git reset --hard`、`git checkout -- .`、`git restore .`、`git clean -fd`、`git stash drop` 或 `git stash clear`，分類器推定這些會丟棄未提交的變更
* 當 HEAD 的提交不是在此工作階段中建立時的 `git commit --amend`
* 從 v2.1.198 開始，當 HEAD 的提交已經被推送時的 `git commit --amend`。僅修改訊息的改寫不會被阻止：在 Claude 於此工作階段期間建立的提交上，沒有新暫存內容的 `--amend -m`
* `terraform destroy`、`pulumi destroy`、`cdk destroy` 或 `terragrunt destroy`，以及套用會銷毀資源的計畫
* 寫入秘密管理器，或變更 DNS 記錄或 TLS 憑證
* 合併未經任何人核准的 pull request、核准 Claude 自己的 pull request，或停用 CI 檢查
* 發佈本身就是對自動化發出命令的留言，例如 `atlantis apply` 或機器人的 `/deploy` 或 `/merge`
* 切換、逐步調整或刪除生產環境的功能旗標
* 將基礎設施變更套用到受保護的 IaC 範圍，或排空並移除叢集節點
* 對共享運算叢集的寫入超出您所指明的資源，例如會涵蓋到其他使用者工作的標籤選擇器或 `--all`
* 建立在每個節點上執行或攔截叢集流量的 Kubernetes 資源，例如 DaemonSets 和 admission webhooks
* 對敏感遠端目標開啟互動式 shell 或連接埠轉發
* 開啟使本機服務可從公開網際網路存取的通道或反向 shell
* 將有效的憑證或 token 印出到逐字稿或檔案中
* 存取在您的[環境](https://code.claude.com/docs/zh-TW/auto-mode-config.md#define-trusted-infrastructure)中列為敏感資料位置的位置、從中複製資料出去，或將資料從該位置傳送給該項目所排除的對象
* 繞過您的內部套件 registry，將套件安裝導向公開 registry。當您的環境中列出了內部 registry 或鏡像，或您在對話中告訴 Claude 存在內部 registry 或鏡像時，即適用此規則
* 執行帶有解除安全防護旗標的命令，例如 `--insecure`
* 啟動在沒有人工核准或沙箱的情況下執行的自主 agent 迴圈，例如使用 `--dangerously-skip-permissions` 或 `--no-sandbox` 啟動的迴圈。這包括在停用隔離和逐項操作核准的情況下執行第三方 agent 或評估工具，例如使用 `--yes-always` 啟動的執行器
* 可能將頁面內容、Cookie 或憑證傳送到其他來源的 [Claude in Chrome](https://code.claude.com/docs/zh-TW/chrome.md) 瀏覽器操作
* 透過萬用字元、glob 或存留時間篩選，而非特定指名的路徑，刪除 `/tmp`、`$TMPDIR` 或其他共享暫存或快取目錄中的檔案
* 在傳送、上傳、發佈或寫給其他人或共享系統的內容中包含敏感細節，而您自己的訊息並未授權將這些細節提供給該收件者。當儲存庫位於信任邊界之外或為公開時（包括您組織自己的公開儲存庫），PR 和 issue 內文、提交訊息和留言都視為此類對外內容；內部檔案路徑、代號、即時 API 回應資料（例如電子郵件或帳戶識別碼）以及基礎設施識別碼都視為敏感細節。PR 或 issue 內文中來自 API 回應的即時個人資料，例如電子郵件地址、帳戶或組織識別碼或使用量指標，無論儲存庫的可見性或信任邊界為何，都需要您指明這些細節和收件者
* 向 Claude Code 自己的 tmux 窗格傳送按鍵以操控其自身介面，分類器將此視為 Claude 變更自己的權限或監督
* 註解掉、刪除或強制通過保護安全行為的測試或斷言，例如驗證、存取控制、輸入驗證或沙箱機制
* 刪除或拆除 Claude 未在工作階段中建立的有狀態資源，當沒有更具體的刪除規則適用且您未指明該資源時
* 將 API 基礎 URL、代理伺服器端點、webhook 接收器或 registry 鏡像重新指向不符合任務的第三方主機，包括在 `.env.example` 等範例檔案中
* 使用 `git remote set-url` 或 `git remote add` 變更推送目的地，除非您指明了新的遠端
* 將秘密或個人或受託資料推送到已知為公開的儲存庫，或將不屬於該儲存庫本身工作的機密資料推送到那裡。對個人或受託資料而言，dotfiles 儲存庫本身的主題內容是唯一的例外，而來自私人儲存庫的內容流向任何公開使用介面也會以相同方式被阻止。當儲存庫的可見性未確定時，分類器不會僅憑此點而阻止；它會改為依據其他規則判斷內容
* 對不同的儲存庫或組織開啟 pull request、使用 `gh repo fork` 進行分叉，或推送到第三方儲存庫，除非您指明了該外部目標
* 來自敏感本機儲存區，或來自名稱、路徑或類型標示其為敏感之檔案的內容，進入提交、推送、PR 或 issue 文字、gist 或貼文，或套件發佈，除非您同時指明了來源和目的地。工作階段逐字稿和對話日誌、憑證和設定點資料夾（例如 SSH 金鑰、雲端憑證、瀏覽器設定檔和 shell 歷史記錄）以及使用者資料匯出都包含在內，且儲存庫為私人並不會解除此限制
* 寫入 Claude Code 工作階段逐字稿，即 `~/.claude/projects/` 或您所設定之設定目錄下的 `.jsonl` 歷史檔案，無論是直接寫入還是透過 shell 命令。此規則也涵蓋 Claude Code 為其自身檢查附加到每個逐字稿項目的中繼資料行。讀取逐字稿不會被阻止
* 遞迴強制刪除，例如 `rm -rf "$VAR"` 或 `Remove-Item -Recurse -Force $dir`，其目標是在分類器看到的對話中任何地方都未被指派的 shell 變數，或以此類變數為根的 glob。該值僅來自較早的命令輸出，而分類器永遠不會收到這些輸出，因此分類器無法依據其他刪除規則驗證刪除目標。當您指明正在刪除的確切路徑，或 Claude 將解析後的字面路徑寫入命令中重新執行刪除時，此阻止即會解除。分類器可以解析其目標的刪除不受影響。

  直接位於變數下的 glob，如 `rm -rf "$VAR"/*`，則屬於[關鍵路徑](#critical-paths)。目標為單獨的 `*` 或以 `/*` 或 `\*` 結尾的 `Remove-Item` 永遠不會送到分類器：Claude Code 會[直接拒絕它們](#remove-item-in-powershell)。

其中幾個類別取決於[環境](https://code.claude.com/docs/zh-TW/auto-mode-config.md#define-trusted-infrastructure)項目，例如敏感遠端目標和受保護的 IaC 範圍，您可以將其縮小到具體名稱。

Claude Code v2.1.257 及更新版本也預設阻止這些：

* 從雲端執行個體中繼資料端點（例如 `169.254.169.254`）請求憑證，或明確使用機器自身的服務帳戶或節點身分來驗證雲端、叢集或 registry 呼叫
* 透過直接請求以外的路徑連線到公開主機，例如通道、反向 shell，或被改寫為指向外部的解析器或代理伺服器設定
* 讀取屬於主機而非屬於您任務的憑證，例如節點憑證或節點的容器 registry 驗證資訊
* 連線到或掃描 Claude 未啟動的同層容器、Pod 或 VM，或容器底下的節點

如果 Claude Code 在本應允許其中某項操作的環境中執行，請在 `autoMode.environment` 的[主機隔離項目](https://code.claude.com/docs/zh-TW/auto-mode-config.md#define-trusted-infrastructure)中描述該設定。

Claude Code v2.1.261 及更新版本也預設阻止這些：

* 在訊息、PR 或 issue 文字、文件，或任何連結會被開啟或擷取的其他地方，發佈或寫入指向公開貼文、圖表或資料分享服務的連結，而該 URL 本身即攜帶所分享的內容，除非您指明了該服務

**預設允許**：

* 您工作目錄中的本機檔案操作
* 安裝在您的鎖定檔案或清單檔中宣告的相依套件
* 讀取 `.env` 並將憑證傳送到其對應的 API
* 唯讀 HTTP 請求
* 推送到您正在處理的儲存庫的任何分支，包括預設分支。名稱將其標示為部署或發佈目標的非預設分支，例如 `production` 或 `gh-pages`，不在此列：分類器會依其本身的情況判斷推送到那裡的操作。

  推送的內容仍會依據分類器的其他規則進行檢查，[`permissions.deny` 規則](https://code.claude.com/docs/zh-TW/permissions#manage-permissions)仍可在每個模式中[依撰寫方式](https://code.claude.com/docs/zh-TW/permissions.md#bash-rule-limits)阻止推送命令。遠端自身的分支保護也仍然適用。
* 刪除 Claude 在同一工作階段中稍早建立的特定工作
* 作為您任務的一部分讀取、審查或撰寫與安全相關的程式碼、設定和威脅模型
* 在同一多 agent 工作階段中協同工作的 agent 之間的訊息
* 將資料傳送到您在 [`environment`](https://code.claude.com/docs/zh-TW/auto-mode-config#define-trusted-infrastructure) 中列出的受信任網域、儲存桶和服務。這僅涵蓋資料流，不涵蓋在同一基礎設施上的破壞性操作或憑證操作
* [Claude in Chrome](https://code.claude.com/docs/zh-TW/chrome.md) 導覽至受信任的內部網域、localhost 或您指明的 URL

沙箱化命令預設不會取得網路存取權。Claude 會在命令本身上指明該命令需要的主機，分類器會連同命令一起審查這些主機，核准的清單僅為該單一命令開放這些主機。[每個命令允許的網域](https://code.claude.com/docs/zh-TW/sandboxing.md#per-command-allowed-domains-in-auto-mode)涵蓋清單可以和不能開放的內容，以及命令嘗試連線到未列出主機時的情況。

執行 `claude auto-mode defaults` 以將完整規則清單以 JSON 格式印出。如果例行操作被阻止，管理員可以透過 `autoMode.environment` 設定新增受信任的儲存庫、儲存桶和服務：請參閱[設定自動模式](https://code.claude.com/docs/zh-TW/auto-mode-config.md)。

推送到您正在處理的儲存庫的任何分支，以及建立符合您請求的 pull request，都無需提示即可執行，除非該推送或 pull request 屬於[阻止清單](#what-the-classifier-blocks-by-default)，例如秘密或敏感資料離開儲存庫，或以不同儲存庫或組織為目標的 pull request。要在保持自動模式的同時，於這些命令執行前要求人工檢查點，請新增 `permissions.ask` 規則，這些規則會[依撰寫方式](https://code.claude.com/docs/zh-TW/permissions.md#bash-rule-limits)比對命令：請參閱[常見邊界](https://code.claude.com/docs/zh-TW/auto-mode-config.md#common-boundaries)。

### 工作目錄外的第一次讀取

當 [`permissions.blockReadsOutsideWorkingDirectories`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-blockreadsoutsideworkingdirectories) 關閉時，除了[從網路路徑讀取](https://code.claude.com/docs/zh-TW/permissions.md#network-paths)以外的檔案讀取在自動模式中無需提示即可執行，包括在[工作目錄](https://code.claude.com/docs/zh-TW/permissions.md#working-directories)外的讀取。Claude 第一次對工作目錄外的路徑使用 Read、Grep 或 Glob 工具時，Claude Code 會詢問是否允許該讀取。

該提示不會出現在非互動式 `-p` 執行或背景工作階段中；那裡的讀取照常執行。

無論您如何回答，Claude 都會繼續工作：

* **是，並繼續允許工作目錄外的任何讀取**：讀取會執行，之後在工作目錄外的讀取照常執行，Claude Code 會記錄您的答案，讓提示不再出現
* **否，並從現在開始阻止工作目錄外的讀取**：讀取被拒絕，Claude Code 會在您的使用者設定中將 [`permissions.blockReadsOutsideWorkingDirectories`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-blockreadsoutsideworkingdirectories) 設定為 `true`，這會使檔案工具在此工作階段及之後的每個工作階段、每個權限模式中拒絕此類讀取。若要解除此阻止，請從每個設定了該項目的[設定檔](https://code.claude.com/docs/zh-TW/settings.md#settings-files-and-who-they-affect)中移除該設定，然後重新啟動每個執行中的工作階段。若只需在此工作階段中開放單一目錄，請使用 `/add-dir`。
* **否，下次再詢問**：讀取被拒絕，下一次在工作目錄外的讀取會再次提示
* **是，但下次再詢問**：讀取會執行，不會儲存任何內容，下一次在工作目錄外的讀取會再次提示

### 您在對話中陳述的邊界

分類器將您在對話中陳述的邊界視為阻止訊號。如果您告訴 Claude「不要推送」或「等我審查後再部署」，即使預設規則會允許，分類器也會阻止相符的操作。邊界會持續有效，直到您在之後的訊息中解除它。Claude 自行判斷條件已滿足並不會解除它。

邊界不會以規則的形式儲存。分類器在每次檢查時都會從逐字稿重新讀取它們，因此如果[上下文壓縮](https://code.claude.com/docs/zh-TW/costs.md#reduce-token-usage)移除了陳述該邊界的訊息，邊界可能會遺失。若需要硬性保證，請改為新增[拒絕規則](https://code.claude.com/docs/zh-TW/permissions.md#permission-rule-syntax)。

### 您在對話中陳述的核准

如果您告訴 Claude 某個被阻止的操作是允許的，分類器會將其視為您的核准，並可以解除該阻止。您的措辭決定了操作是否執行，以及核准的涵蓋範圍：

* **指明操作及其細節**：您的訊息必須指明該操作，以及使其危險的具體事項，例如強制推送的分支。僅指明動詞不會解除任何阻止，因此「您可以強制推送」會使阻止保持有效。
* **預期它只涵蓋一個操作**：核准涵蓋您所指明的破壞性操作，因此之後的操作會再次被阻止，除非您將核准授予為持續有效。若要停止逐一核准某個例行模式，請將其新增到 [`autoMode.allow`](https://code.claude.com/docs/zh-TW/auto-mode-config#override-the-block-and-allow-rules)。
* **某些阻止會保持有效**：[分類器的優先順序](https://code.claude.com/docs/zh-TW/auto-mode-config.md#override-the-block-and-allow-rules)說明了您的核准可以解除哪些阻止。要執行無法解除的步驟，請[離開自動模式](#switch-permission-modes)並回答權限提示。

### 當自動模式改用備援時

當自動模式無法核准您工作階段的操作時，發生的情況取決於具體情形：

* **被阻止的操作**：Claude Code 會顯示通知，並在 `/permissions` 的 **Recently blocked** 分頁中列出該操作，您可以在此[核准該操作，讓 Claude 可以重試](https://code.claude.com/docs/zh-TW/auto-mode-config.md#review-denials)。
* **重複阻止**：如果分類器連續 3 次或總共 20 次阻止操作，自動模式會暫停，Claude Code 會恢復提示。核准被提示的操作即可恢復自動模式。請參閱[重複阻止閾值](#repeated-block-thresholds)以了解阻止如何計數。
* **分類器沒有判決**：當自動模式以外的安全檢查拒絕分類器自身的請求，或分類器的回應無法解析時，Claude Code 會阻止該操作，且不顯示通知，也不建立 **Recently blocked** 項目。請參閱[自動模式無法確定操作的安全性](https://code.claude.com/docs/zh-TW/errors.md#auto-mode-cannot-determine-the-safety-of-an-action)以了解每種情況顯示的訊息和應對方法。
* **伺服器未提供判定結果**：在[伺服器端分類器審查](#server-side-classifier-review)下，若伺服器未對某個動作提供判定結果，Claude Code 會拒絕該動作，且在連續十個回應都沒有判定結果後，可能會停止該回合。請參閱[伺服器未傳回安全判定結果](https://code.claude.com/docs/zh-TW/errors.md#the-server-returned-no-safety-verdict)。
* **檢查期間切換模式**：如果您在分類器檢查尚未完成時切換權限模式，Claude Code 會捨棄新模式不會請求的判決。您會改為被提示核准，或者該操作在 [`dontAsk` 模式](#allow-only-pre-approved-tools-with-dontask-mode)中被自動拒絕。

#### 重複阻止閾值

連續 3 次阻止和總共 20 次阻止的閾值無法設定。總計數器會在整個工作階段中持續累計，僅在其自身的上限觸發備援時才會重設。當自動模式以外的安全檢查拒絕分類器自身的請求時，Claude Code 不會將該拒絕計入任一閾值。

沒有 [`--permission-prompt-tool`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 的[非互動式](https://code.claude.com/docs/zh-TW/headless.md) `-p` 執行沒有可改用的提示。當重複阻止達到閾值時，該操作不會執行，Claude 會繼續工作。Claude Code 不會停止執行。

重複阻止通常意味著分類器缺少關於您基礎設施的上下文。請使用 `/feedback` 回報誤判，或請管理員[設定受信任的基礎設施](https://code.claude.com/docs/zh-TW/auto-mode-config.md)。

### 自動模式如何評估操作

以下章節涵蓋 Claude Code 評估操作的順序、分類器如何審查 subagent 的工作，以及分類器呼叫在成本和延遲上增加的負擔。

> [accordion] 分類器如何評估操作
>
> 每個操作都會經過固定的決策順序。第一個相符的步驟優先：
>
> 1. 符合您的[允許、詢問或拒絕規則](https://code.claude.com/docs/zh-TW/permissions.md#manage-permissions)的操作會立即決定，但有以下例外：
>    * 寫入[受保護路徑](#protected-paths)的操作即使符合允許規則，也會送交分類器。當受保護路徑是符號連結的設定檔所指向的檔案時，該寫入可能會改為提示您，如[受保護路徑](#protected-paths)清單所述
>    * 沒有任何允許規則能核准可識別的針對[關鍵路徑](#critical-paths)的 `rm` 和 `rmdir` 移除操作
>    * 標記為 [`requiresUserInteraction`](https://code.claude.com/docs/zh-TW/mcp#require-approval-for-a-specific-tool) 的 MCP 工具即使符合允許規則也會直接提示您，而在[您的組織設定為 `ask`](https://code.claude.com/docs/zh-TW/mcp#organization-controls-on-connector-tools) 的連接器工具上，若該設定已送達 Claude Code 的工作階段，也是如此
>    * 攜帶[每個命令允許的網域](https://code.claude.com/docs/zh-TW/sandboxing.md#per-command-allowed-domains-in-auto-mode)的 shell 命令即使符合允許規則，也會送交分類器，因為規則核准的是命令，而不是其主機
>    * 依命令內容比對的詢問規則，例如 `Bash(git push *)`，會改用權限提示
>    * 經[符號連結檢查](https://code.claude.com/docs/zh-TW/permissions.md#symlinks)解析為受保護路徑的寫入操作，在 Claude 所請求的路徑本身不受保護時會提示您
>    * 從[網路路徑](https://code.claude.com/docs/zh-TW/permissions.md#network-paths)讀取即使符合允許規則也會提示您
> 2. 唯讀操作和您工作目錄中的檔案編輯會自動核准，但寫入[受保護路徑](#protected-paths)和[工作目錄外的第一次讀取](#first-read-outside-the-working-directories)除外，後者會提示您
>    * 在具有[伺服器端分類器審查](#server-side-classifier-review)的工作階段中，唯讀和[沙箱化](https://code.claude.com/docs/zh-TW/sandboxing.md#sandbox-modes)的 shell 命令會等待該審查，若審查將其標記則會被阻止
>    * 在您工作目錄內、經[符號連結檢查](https://code.claude.com/docs/zh-TW/permissions.md#symlinks)解析為工作目錄外位置的寫入操作會提示您
>    * 當 Claude 讀取[其他人製作的 artifact](https://code.claude.com/docs/zh-TW/artifacts.md#read-an-artifact-shared-with-you) 時，適用該章節所列的核准情況
>    * 從[網路路徑](https://code.claude.com/docs/zh-TW/permissions.md#network-paths)讀取會提示您
> 3. 其他所有操作都會送交分類器，但採用預設處理方式的[關鍵路徑移除](#critical-paths)除外。在步驟 1 中直接提示您的連接器工具和 `requiresUserInteraction` MCP 工具也永遠不會送到分類器，因此組織要求的核准和同意步驟都不會被自動核准
> 4. 如果分類器阻止操作，Claude 會收到原因。在大多數工作階段中，原因會指明分類器比對到的規則，例如 `[Data Exfiltration]`，而不是提供書面說明；請參閱[檢視拒絕](https://code.claude.com/docs/zh-TW/auto-mode-config.md#review-denials)
>
> 您安裝的處理 `tool.check` 的 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md) 也可以核准操作。關於其核准無法越過您的規則和 hook 的情況，請參閱[使用 hook 擴充權限](https://code.claude.com/docs/zh-TW/permissions.md#precedence-among-rules-hooks-and-mods)。
>
> 關於 [Claude in Chrome](https://code.claude.com/docs/zh-TW/chrome.md) 瀏覽器操作在 VS Code 擴充功能中如何獲得核准，請參閱[VS Code 工作階段中的權限提示](https://code.claude.com/docs/zh-TW/chrome.md#permission-prompts-in-vs-code-sessions)。
>
> 進入自動模式時，授予任意程式碼執行能力的廣泛允許規則會被移除：
>
> * 無條件的 `Bash(*)` 或 `PowerShell(*)`
> * 使用萬用字元的直譯器，例如 `Bash(python*)`
> * 套件管理器的執行命令
> * `Agent` 允許規則
> * [`Monitor`](https://code.claude.com/docs/zh-TW/tools-reference#monitor-tool) 允許規則，因為 Claude Code 透過 shell 執行 Monitor 命令
>
> 像 `Bash(npm test)` 這樣的窄規則仍然有效。當您離開自動模式時，Claude Code 會恢復被移除的規則。在 v2.1.236 之前，Claude Code 在自動模式中保留 `Monitor` 允許規則，因此比對整個工具的規則會在沒有分類器審查的情況下核准 Monitor 命令。
>
> Claude Code 也會在可能丟棄未提交工作的命令（例如 `git reset --hard` 或 `rm -rf`）之前自行執行 `git status`，並向分類器顯示是否存在已暫存、已修改或未追蹤的工作。即使儲存庫的 git 設定指定了 `status.showUntrackedFiles=no`，Claude Code 仍會在該檢查中回報未追蹤的檔案。
>
> 在 Claude Code 本身發送的分類器請求中，分類器會看到使用者訊息、除唯讀查詢（例如檔案讀取和搜尋）之外的工具呼叫，以及您的 CLAUDE.md 內容。工具結果會從這些請求中移除，因此檔案或網頁中的惡意內容無法直接操縱分類器。
>
> 您可以使用 [PostToolUse hook 的 `classifierContext` 欄位](https://code.claude.com/docs/zh-TW/hooks#annotate-a-result-for-the-auto-mode-classifier)註解呼叫的結果，分類器會將其視為應用程式提供的上下文。該欄位需要 Claude Code v2.1.236 或更新版本。
>
> 另一個獨立的伺服器端探測器會掃描傳入的工具結果，並在 Claude 讀取之前標記可疑內容。有關這些防護層如何協同運作的更多資訊，請參閱[自動模式公告](https://claude.com/blog/auto-mode)和[工程深入探討](https://www.anthropic.com/engineering/claude-code-auto-mode)。

> [accordion] 自動模式如何處理 subagent
>
> 分類器會在三個時間點檢查 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 的工作：
>
> 1. 在 subagent 啟動之前，會評估委派的任務描述，因此看起來危險的任務會在產生時就被阻止。
> 2. 在 subagent 執行期間，其每個操作都會經過與父工作階段相同的[決策順序](#how-the-classifier-evaluates-actions)，並套用相同的阻止和允許規則。subagent frontmatter 中的任何 `permissionMode` 都會被忽略。
> 3. 當 subagent 完成時，分類器會在父工作階段讀取報告之前審查其工作和最終報告。當分類器標記了 subagent 的工作或報告，或另一個獨立的 API 安全檢查拒絕了該審查時，報告仍會送達，但前面會加上安全警告。當分類器無法進行審查時，報告送達時會附帶一則說明，提醒您在據此採取行動前先驗證 subagent 的工作。

> [accordion] 成本和延遲
>
> Claude Code 的分類器請求可能在您 `/model` 選擇以外的模型上執行。請參閱[它們在哪個模型上執行](#default-classifier-model)。
>
> 在 Enterprise 計畫，以及使用 Claude API、[AWS 上的 Claude Platform](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md)、Amazon Bedrock、Google Cloud 的 Agent Platform 或 Microsoft Foundry 的帳戶上，分類器呼叫會計入您的 token 使用量。每次檢查都會傳送部分逐字稿以及待處理的操作，在執行前增加一次往返。讀取和受保護路徑以外的工作目錄編輯會略過分類器，因此額外負擔主要來自 shell 命令和網路操作。若伺服器將審查操作作為工作階段模型請求的一部分，就沒有獨立的分類器呼叫需要計入；請參閱[伺服器端分類器審查](#server-side-classifier-review)。
>
> 沙箱化的網路存取不會針對每個連線增加分類器請求。分類器會在一次審查中，將[命令所指明的主機](https://code.claude.com/docs/zh-TW/sandboxing.md#per-command-allowed-domains-in-auto-mode)與命令一併判斷，而 Claude Code 會依據核准的清單檢查每個連線，不會再次呼叫分類器。

## 使用 dontAsk 模式僅允許預先批准的工具

如果您設定 `dontAsk` 模式，Claude Code 會自動拒絕所有原本會提示您的工具呼叫，不過您安裝的 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md) 仍可核准其中部分呼叫。若要查看 mod 可以核准哪些呼叫，請參閱[使用 hook 擴充權限](https://code.claude.com/docs/zh-TW/permissions.md#precedence-among-rules-hooks-and-mods)。

Claude 仍會執行在 Manual 模式中不需要核准的操作，例如您工作目錄內的檔案讀取和[唯讀 Bash 命令](https://code.claude.com/docs/zh-TW/permissions.md#read-only-commands)。符合您 `permissions.allow` 規則的操作以及由 [PreToolUse hook](https://code.claude.com/docs/zh-TW/permissions.md#extend-permissions-with-hooks) 核准的呼叫也會執行。在您預先定義 Claude 可以執行哪些操作的 CI 管道或受限環境中使用此模式；工作階段永遠不會等待輸入。此模式啟用時，狀態列會顯示 `⏵⏵ don't ask on`。

Claude Code 會拒絕符合您明確 [`ask` 規則](https://code.claude.com/docs/zh-TW/permissions#manage-permissions)的呼叫，而不是提示。它也會拒絕內建的 `AskUserQuestion` 工具，即使您的允許規則符合它，以及您的組織[設定為 `ask`](https://code.claude.com/docs/zh-TW/mcp#organization-controls-on-connector-tools)的連接器工具在該設定到達 Claude Code 的工作階段中。它以相同方式拒絕標記為 [`_meta["anthropic/requiresUserInteraction"]`](https://code.claude.com/docs/zh-TW/mcp#require-approval-for-a-specific-tool) 的 MCP 工具，因為它們的核准卡需要此模式永遠不會收集的答案。

允許規則或 `PreToolUse` hook 無法核准以下項目：

* 可辨識的 `rm` 和 `rmdir` [關鍵路徑移除](#critical-paths)，例如 `rm -rf /` 和 `rm -rf ~`
* 從[網路路徑](https://code.claude.com/docs/zh-TW/permissions.md#network-paths)讀取

[Claude Code on the web](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md) 上的雲端工作階段會忽略 `defaultMode: "dontAsk"`；詳見 [bypassPermissions](#skip-all-checks-with-bypasspermissions-mode) 以了解詳情。

在啟動時使用旗標設定：

```bash theme={null}
claude --permission-mode dontAsk
```

## 使用 bypassPermissions 模式略過所有檢查

`bypassPermissions` 模式會停用權限提示與安全檢查，讓工具呼叫立即執行，包括寫入[受保護路徑](#protected-paths)。

即使在 `bypassPermissions` 模式下，每一項[任何模式都不會自動核准的動作](#actions-no-mode-auto-approves)都會出現提示或遭到拒絕，不過您可以[關閉危險 `rm` 命令的提示](#turn-off-the-critical-path-removal-prompt-in-bypasspermissions-mode)。讀取[其他組織的公開 artifact](https://code.claude.com/docs/zh-TW/artifacts.md#read-an-artifact-shared-with-you) 需要您的核准，而此模式不會請求核准，因此 Claude 無法讀取這類 artifact。[PowerShell 中的 Remove-Item](#remove-item-in-powershell) 拒絕規則在此模式下同樣適用。

有兩項[跨工作階段訊息](https://code.claude.com/docs/zh-TW/cross-session-messaging.md)保護措施在此模式下仍然適用，在可使用略過權限的互動式終端機 plan mode 工作階段中也同樣適用：

* 針對傳送至本機以外之您的工作階段的訊息，[`isolatePeerMachines`](https://code.claude.com/docs/zh-TW/settings-reference#isolatepeermachines) 核准提示仍會出現。
* 當沒有適用的 [`crossSessionInbound`](https://code.claude.com/docs/zh-TW/cross-session-messaging#control-inbound-messages) 值時，Claude Code 會保留來自您其他工作階段的傳入訊息以待您核准，只有在傳送端工作階段表明自己也正在略過權限提示時，才會不經詢問直接傳遞。如果您在訊息被保留期間離開此權限模式，Claude Code 會重新套用傳入規則，並傳遞這些規則現在接受的任何保留訊息。

在可使用略過權限的互動式終端機工作階段中，Claude Code 也不會強制執行 [plan mode](#analyze-before-you-edit-with-plan-mode) 的封鎖。Claude 仍會被指示在不編輯的情況下進行規劃，但它在規劃期間嘗試的檔案編輯或 shell 命令會在不提示的情況下執行。明確的 [ask 規則](https://code.claude.com/docs/zh-TW/permissions.md#manage-permissions)，以及可識別的 `rm` 和 `rmdir` [關鍵路徑移除操作](#critical-paths)，仍會提示。

在 Claude Code 於沒有互動式終端機的環境中執行時，plan mode 都會保留其封鎖，包括使用 `-p` 的[非互動式執行](https://code.claude.com/docs/zh-TW/headless.md)、[Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#plan-mode-plan) 工作階段，以及 [VS Code 擴充功能](https://code.claude.com/docs/zh-TW/vs-code.md)聊天面板中的對話。在這些環境中，`--allow-dangerously-skip-permissions` 可讓 `bypassPermissions` 稍後成為可選擇的模式。

> [!WARNING]
>
> 僅在隔離環境中使用此模式，例如沒有網際網路存取的容器、虛擬機器或 dev container，讓 Claude Code 無法損害您的主機系統。

您無法從啟動時未啟用此模式的工作階段進入 `bypassPermissions`。請在啟動時透過 [`permissions.defaultMode: "bypassPermissions"`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-defaultmode) 或啟用旗標來啟用它：

```bash theme={null}
claude --permission-mode bypassPermissions
```

`--dangerously-skip-permissions` 旗標與此等效。

在您以 [`--restricted`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 啟動的工作階段中，Claude Code 會拒絕 `bypassPermissions`。`--restricted` 需要 Claude Code v2.1.248 或更新版本。

當您第一次在啟用此模式的情況下啟動互動式工作階段時，Claude Code 會顯示警告對話框，要求您為未經權限檢查所採取的動作承擔責任：

* **如果您接受**：Claude Code 會在 `~/.claude/settings.json` 中將 `skipDangerousModePermissionPrompt` 設為 `true`，之後的工作階段便會略過此對話框。若要再次看到對話框，請從該檔案中移除此設定鍵或將其設為 `false`。[`skipDangerousModePermissionPrompt` 參考](https://code.claude.com/docs/zh-TW/settings-reference#skipdangerousmodepermissionprompt)列出了您或您的組織可以設定它的其他設定檔。
* **如果您拒絕**：Claude Code 會結束。

在[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)中不會顯示對話框。

當您的接受記錄在使用者設定或受管設定中時，[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)會予以採用：

* 如果沒有記錄接受，`claude --bg --permission-mode bypassPermissions` 會被拒絕。請先在互動式工作階段中接受對話框。
* 如果 `skipDangerousModePermissionPrompt` 僅設定在 `.claude/settings.local.json` 中，背景工作階段會在[略過請求被忽略](#bypass-permissions-ignored-in-a-background-session)的狀態下啟動：

  * 當 `--allow-dangerously-skip-permissions` 被忽略時，`bypassPermissions` 不會出現在其 `Shift+Tab` 循環中。
  * 當 `--permission-mode bypassPermissions` 或 `--dangerously-skip-permissions` 被忽略時，工作階段會改以手動模式啟動。

  請將 `"skipDangerousModePermissionPrompt": true` 加入 `~/.claude/settings.json`，然後啟動新的背景工作階段。

在 Linux 和 macOS 上，當以 root 身分或在 `sudo` 下執行時，Claude Code 會拒絕以 `bypassPermissions` 模式啟動：

```text theme={null}
--dangerously-skip-permissions cannot be used with root/sudo privileges for security reasons
```

在可識別的沙箱內會自動略過此檢查。若要在容器中自主執行，請使用 [dev container](https://code.claude.com/docs/zh-TW/devcontainer.md) 設定，它會以非 root 使用者身分執行 Claude Code。

[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)不會採用您設定檔中的 `defaultMode: "bypassPermissions"` 或 `"dontAsk"`，因此儲存庫中簽入的設定無法以略過權限模式啟動雲端工作階段。此設定會被靜默忽略，工作階段會改以模式下拉選單中顯示的權限模式啟動。請參閱[切換權限模式](#switch-permission-modes)，了解雲端工作階段提供哪些模式。

> [!WARNING]
>
> `bypassPermissions` 無法防範提示詞注入或非預期的動作。若要在權限提示大幅減少的情況下進行背景安全檢查，請改用[自動模式](#eliminate-prompts-with-auto-mode)。管理員可以在[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)中將 `permissions.disableBypassPermissionsMode` 設為 `"disable"` 來封鎖此模式。

### 背景工作階段中的略過權限請求被忽略

此通知表示[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)未在使用者設定或受管設定中找到您對[略過權限警告](#bypass-permissions-acceptance)的接受，因此忽略了啟動時提出的略過請求：

```text theme={null}
Bypass permissions was requested at launch and ignored · if that was you, ~/.claude/settings.json needs "skipDangerousModePermissionPrompt": true
```

請將 `"skipDangerousModePermissionPrompt": true` 加入 `~/.claude/settings.json`，然後啟動新的背景工作階段。

### `claude agents` 顯示互動式工作階段會略過的略過權限警告

如果 [`claude agents`](https://code.claude.com/docs/zh-TW/agent-view#dispatch-defaults) 顯示了[略過權限警告](#bypass-permissions-acceptance)，但您的互動式工作階段會略過它，請檢查 `skipDangerousModePermissionPrompt` 是否設定在 `.claude/settings.local.json` 或 `--settings` 檔案中。互動式工作階段會將該處的設定鍵視為您對警告的接受，而 `claude agents` 不會。無論您是否在該處找到它，請接受警告，將此設定鍵加入 `~/.claude/settings.json`，也就是 `claude agents` 尋找它的位置。

## 受保護的路徑

對於一小組路徑的寫入操作永遠不會自動批准，唯一的例外是 `bypassPermissions` 模式，以及可使用[略過權限](#skip-all-checks-with-bypasspermissions-mode)的計畫模式互動式終端工作階段。這可以防止意外損壞儲存庫狀態和 Claude 自身的設定。

| 模式 | 受保護路徑寫入 |
| :- | :- |
| `default`、`acceptEdits` | 提示 |
| `plan` | 在[略過權限](#skip-all-checks-with-bypasspermissions-mode)可用的互動式終端工作階段中允許。否則，當[自動模式](#eliminate-prompts-with-auto-mode)在規劃期間可用時路由到分類器，當它不可用時提示 |
| `auto` | 路由至分類器 |
| `dontAsk` | 拒絕 |
| `bypassPermissions` | 允許 |

在使用 [`--restricted`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 啟動的工作階段中，需要 Claude Code v2.1.248 或更新版本，分類器無法批准受保護路徑寫入。

當 [`permissions.blockWritesOutsideWorkingDirectories`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-blockwritesoutsideworkingdirectories) 開啟時，Claude Code 在每種權限模式下都會拒絕對設定檔的 `Write`、`Edit` 和 `NotebookEdit` 寫入。

在將受保護路徑寫入路由到分類器的模式中，當 Claude 要求的路徑本身不受保護時，[符號連結檢查](https://code.claude.com/docs/zh-TW/permissions.md#symlinks)解析為受保護路徑的寫入會改為提示您。

設定檔案中的 [`permissions.allow`](https://code.claude.com/docs/zh-TW/permissions#manage-permissions) 規則不會預先批准受保護路徑的寫入。安全檢查在 Claude Code 評估設定中的允許規則之前執行，因此在 `~/.claude/settings.json` 或 `.claude/settings.json` 中的 `Edit(.claude/**)` 之類的項目不會改變上表中的每個模式結果。在提示的模式中，對專案的 `.claude/` 資料夾或 `~/.claude/` 的寫入提示可以提供以下其中一個工作階段範圍的選項：

* 對於專案的 `.claude/` 資料夾：**是的，並允許 Claude 在此工作階段編輯此專案的 .claude 資料夾中的檔案**
* 對於 `~/.claude/`：**是的，並允許 Claude 在此工作階段編輯其 \~/.claude 資料夾中的檔案**

受保護的目錄：

* `.git`
* `.config/git`
* `.vscode`
* `.idea`
* `.husky`
* `.cargo`
* `.devcontainer`
* `.yarn`
* `.mvn`
* `.claude`，但有少數例外，例如：
  * Claude 自身位於 `.claude/worktrees/` 下的 git worktrees
  * 目前工作階段自身位於 `~/.claude/plans/` 或您所設定的 [`plansDirectory`](https://code.claude.com/docs/zh-TW/settings-reference#plansdirectory) 中的計畫檔案
  * [背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md#where-state-is-stored)自身位於 `~/.claude/jobs/<id>/tmp/` 的暫存目錄
  * 在未使用 `--restricted` 啟動的工作階段中，專案[自動記憶](https://code.claude.com/docs/zh-TW/memory.md#storage-location)目錄（例如 `~/.claude/projects/<project>/memory/`）中的 markdown 檔案
  * 在未使用 `--restricted` 啟動的工作階段中，[subagent 記憶](https://code.claude.com/docs/zh-TW/sub-agents.md#enable-persistent-memory)目錄（例如 `.claude/agent-memory/`）中的 markdown 檔案
* 您使用 [`--plugin-dir`](https://code.claude.com/docs/zh-TW/plugins/mods/create#change-a-mod-with-claude) 載入的目錄，因為當檔案變更時 Claude Code 會從中重新載入並執行 mod 的程式碼
* `~/.claude/dev-mods/`，或 [`CLAUDE_CONFIG_DIR`](https://code.claude.com/docs/zh-TW/env-vars) 所指向目錄中的 `dev-mods/`，Claude 會在此儲存[它為您撰寫的 mod](https://code.claude.com/docs/zh-TW/plugins/mods/create.md#ask-claude-for-a-mod)

受保護的檔案：

* `.gitconfig`、`.gitmodules`
* `.bashrc`、`.bash_profile`、`.bash_login`、`.bash_aliases`、`.bash_logout`、`.zshrc`、`.zprofile`、`.zshenv`、`.zlogin`、`.zlogout`、`.profile`、`.envrc`
* `.npmrc`、`.yarnrc`、`.yarnrc.yml`、`.pnp.cjs`、`.pnp.loader.mjs`、`.pnpmfile.cjs`、`bunfig.toml`、`.bunfig.toml`
* `.bazelrc`、`.bazelversion`、`.bazeliskrc`
* `.pre-commit-config.yaml`、`lefthook.yml`、`lefthook.yaml`、`.lefthook.yml`、`.lefthook.yaml`
* `gradle-wrapper.properties`、`maven-wrapper.properties`
* `.devcontainer.json`
* `.ripgreprc`、`pyrightconfig.json`
* `.mcp.json`、`.claude.json`
* `remote-settings.json`（即您組織的[伺服器管理設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)的儲存副本），以及 Claude Code 與其一同保存的簽章、同步和同意檔案，位於 `~/.claude` 或 [`CLAUDE_CONFIG_DIR`](https://code.claude.com/docs/zh-TW/env-vars) 所指向的目錄中
* 您在啟動工作階段時傳遞給 [`--settings`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags)、`--mcp-config` 或 `--agents` 的檔案
* 當您的使用者、專案或本機[設定檔](https://code.claude.com/docs/zh-TW/settings.md#settings-files-and-who-they-affect)本身是符號連結時（例如連結到 dotfiles 儲存庫），該設定檔所指向的檔案。在將受保護路徑寫入路由到分類器的模式中，對此檔案的寫入會改為提示您，即使有允許規則相符也是如此。如果該檔案本身的路徑也是某個設定檔的路徑，例如另一個資料夾中的 `.claude/settings.json`，則該寫入會如同其他受保護路徑寫入一樣交由分類器處理

## 關鍵路徑

關鍵路徑是 Claude Code 保護的目錄，防止 `rm` 和 `rmdir` 命令刪除，例如檔案系統根目錄、您的家目錄和您的工作目錄。Claude Code 會在這些命令執行前進行檢查，任何[允許規則](https://code.claude.com/docs/zh-TW/permissions.md#manage-permissions)都無法核准其目標被識別為關鍵路徑的命令。此檢查可能遺漏某些命令，因此無法取代[沙箱機制](https://code.claude.com/docs/zh-TW/sandboxing.md)等作業系統層級的控制。

關鍵路徑移除是指 Claude Code 識別其目標為關鍵路徑的 `rm` 或 `rmdir` 命令。返回 `"allow"` 的 [`PreToolUse` hook](https://code.claude.com/docs/zh-TW/permissions#extend-permissions-with-hooks) 同樣無法核准此類命令。即使在會跳過其他提示的權限模式中，允許規則或 `PreToolUse` hook 也無法核准此類命令。

> [!WARNING]
>
> 檢查遺漏的命令不會受到特殊處理，因此工作階段中任何會核准 Bash 命令的機制都可以在不提示的情況下核准它。這包括允許規則、`bypassPermissions` 模式，以及沙箱的[自動允許模式](https://code.claude.com/docs/zh-TW/sandboxing.md#auto-allow-mode)。此檢查僅適用於 `rm` 和 `rmdir`，因此其他經核准的命令同樣可能刪除關鍵路徑。

無論檢查是否識別出命令，以下控制都會生效：

* **拒絕規則**：與命令匹配的[拒絕規則](https://code.claude.com/docs/zh-TW/permissions.md#manage-permissions)會阻止該命令，不過您安裝的 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md) 仍可核准[其中部分呼叫](https://code.claude.com/docs/zh-TW/permissions.md#precedence-among-rules-hooks-and-mods)
* **沙箱機制**：[沙箱機制](https://code.claude.com/docs/zh-TW/sandboxing.md)讓作業系統限制 Bash 命令可以寫入的路徑。在沙箱中執行的命令仍可刪除您的工作目錄
* **嚴格沙箱模式**：預設情況下，沙箱中的命令可以[在沙箱外重試](https://code.claude.com/docs/zh-TW/sandboxing.md#the-unsandboxed-retry-escape-hatch)，而允許規則或 `bypassPermissions` 模式可以在不提示的情況下核准該重試。[嚴格沙箱模式](https://code.claude.com/docs/zh-TW/sandboxing.md#turn-off-the-retry-with-strict-sandbox-mode)會關閉此重試

Claude Code 識別出的移除會發生什麼，[取決於您的權限模式](#critical-path-removals-in-each-permission-mode)。`Remove-Item` 和 `cmd` 移除內建命令有自己的檢查，詳見 [PowerShell 中的 Remove-Item](#remove-item-in-powershell)。

### 哪些路徑是關鍵路徑

Claude Code 將 `rm` 或 `rmdir` 目標視為關鍵路徑，當它是以下任何一項時：

* 檔案系統根目錄
* 頂級目錄，即根目錄的任何直接子目錄，例如 `/usr`、`/etc` 或 `/data`
* 您的家目錄。在 Windows 上，其 8.3 短名稱也算在內，例如 `C:\Users\LONGNA~1`
* Windows 磁碟機根目錄及其頂級目錄，例如 `C:\` 和 `C:\Windows`。`\\?\C:\` 和 `\\localhost\C$` 等寫法視同 `C:\`
* 您的工作目錄及其父目錄
* 您的其他工作目錄及其父目錄，但僅當移除是其中一個目錄下的 glob 時，例如 `rm -rf <dir>/*`。對目錄本身執行 `rm -rf <dir>` 不會觸發此檢查

關於 `/mnt/c` 或 `/Volumes/USB` 等已掛載磁碟機路徑，請參閱[已掛載磁碟機提示](#the-mounted-drive-prompt)。

對家目錄 8.3 短名稱以及 `\\?\C:\` 和 `\\localhost\C$` 寫法的檢查需要 Claude Code v2.1.292 或更新版本。

### 計為關鍵路徑的其他目標

Claude Code 也將以下 `rm` 和 `rmdir` 目標視為關鍵路徑。最後一列說明每個目標計為關鍵路徑的原因。

| 目標 | 範例 | 計為關鍵路徑的原因 |
| :- | :- | :- |
| shell 變數下的 glob 或尾部斜線 | `rm -rf "$DIR"/*` | 當變數為空時，命令變成從檔案系統根目錄的移除 |
| 位置參數（例如 `$1` 或 `$@`）下的相同形式，當命令中沒有任何內容給它賦值時 | `rm -rf "$1"/*` | 命令展開為從根目錄的移除 |
| shell 變數後跟一個常見的頂級目錄名稱，例如 `mnt`、`tmp`、`usr` 或 `Users` | `rm -rf "$TMPDIR/mnt"` | 當變數展開為空時，命令移除 `/mnt` |
| 同一命令從目錄列印替換（例如 `$(pwd)` 或 `$(git rev-parse --show-toplevel)`）分配的變數 | `D=$(pwd); rm -rf "$D"` | 該值可以命名您的工作目錄或儲存庫根目錄 |
| 僅是命令替換輸出的目標，當 `rm` 是遞迴時 | `rm -rf "$(pwd)"` | Claude Code 無法在命令執行前檢查目標 |
| 關鍵路徑後的尾部命令替換 | `rm -rf ~/$(cmd)` | Claude Code 檢查如果替換展開為空時會保留的路徑，這裡是您的主目錄 |
| 僅是反斜線的目標 | `rm -rf "\\"` | Windows 上的 Git Bash 將單個反斜線讀取為目前磁碟機的根目錄，因此檢查適用於每個平台 |
| 以 GUID 而非磁碟機代號指定磁碟區的 Windows 路徑 | `rm -rf '\\?\Volume{GUID}\work\build'` | 該路徑未指明位於哪個磁碟機，因此可能是關鍵路徑。需要 Claude Code v2.1.292 或更新版本 |
| 某些以 `/*` 或 `/*/` 結尾的目標 | `rm -rf logs/*/*`、`rm -rf logs/*/`、`cd logs && rm -rf a/*` | Claude Code 無法在命令執行前判斷它們會觸及哪些目錄 |

要關閉對僅是命令替換輸出的目標的檢查，請在啟動 Claude Code 的環境中設定 [`CLAUDE_CODE_DISABLE_SUBSTITUTION_RM_PROMPT=1`](https://code.claude.com/docs/zh-TW/env-vars#variables)。

### 巢狀命令和內聯指令碼中的移除

Claude Code 也會查看這些構造：

* **巢狀命令**：帶有 `(...)` 的子殼層、帶有 `{ ...; }` 的大括號群組、帶有 `$(...)` 或反引號的命令替換，或帶有 `<(...)` 的程序替換。Claude Code 會找到關鍵路徑移除，無論它位於巢狀形式內（如 `(rm -rf ~)` 或 `echo "$(rm -rf ~)"`），還是位於同一命令中的其他位置。
* **內聯指令碼**：以 `-c` 傳遞給 `sh`、`bash`、`zsh` 或類似 POSIX shell 的指令碼，如 `bash -c 'rm -rf ~'`。
  * 當指令碼是雙引號時，呼叫端 shell 會在內部 shell 接收指令碼之前展開其變數。在 `find . -name '*.tmp' -exec sh -c "rm -rf \"$1\"/*" _ {} \;` 中，命令會針對每個匹配項展開為從檔案系統根目錄的移除，Claude Code 將其視為關鍵路徑移除。
  * 將 `$1` 綁定到實際值的單引號指令碼（如 `sh -c 'rm -rf "$1"/*' _ {}` 所做的）不會被標記。

要關閉對直接輸入在 `-c` 指令碼中的關鍵路徑（例如 `~`）的檢查，請在啟動 Claude Code 的環境中設定 [`CLAUDE_CODE_DISABLE_INLINE_SHELL_RM_PROMPT=1`](https://code.claude.com/docs/zh-TW/env-vars#variables)。

### 重寫被標記的命令

如何重寫命令以通過檢查取決於它使用的[其他目標](#other-targets-that-count-as-critical-paths)：

* **glob 或尾部斜線在變數（例如 `$DIR`）下**：保護每個展開，使殼層在變數未設定或為空時停止並出現錯誤，如 `rm -rf "${DIR:?}"/*`，或使用字面路徑。其展開都以這種方式保護的移除通過此檢查，因此在 `bypassPermissions` 模式中，除非另一個[關鍵路徑](#critical-paths)檢查標記它，否則它會在沒有提示的情況下執行。
* **glob 或尾部斜線在通常設定的變數（例如 `$HOME`）下**：使用字面路徑。
* **從目錄列印替換分配的變數**：使用字面路徑。`"${D:?}"` 保護不會清除此檢查，因為變數不為空。
* **僅是命令替換輸出的目標**：首先單獨執行替換，然後移除它列印的字面路徑。提示會告訴 Claude 執行相同操作。

對於變數下的 glob 或尾部斜線，提示會命名被標記的 `rm` 並說明如何重寫它以通過檢查。

### `Dangerous rm operation not ruled out` 提示

完整原因如下：

```text theme={null}
Dangerous rm operation not ruled out — the shell may read this command differently than it was parsed
```

此原因表示 shell 解讀該命令的方式可能與 Claude Code 不同，因此即使命令中沒有 `rm`，移除操作也可能位於未經檢查的部分。在 `auto` 或 `bypassPermissions` 模式中，帶有以下句子的拒絕來自同一項檢查：

```text theme={null}
This command could not be checked for dangerous rm operations: the shell may read it differently than it was parsed.
```

您會收到關鍵路徑移除[在您的權限模式中](#critical-path-removals-in-each-permission-mode)會收到的提示或拒絕，`bypassPermissions` 也不例外，不過您可以在 `bypassPermissions` 模式中[關閉該提示](#turn-off-the-critical-path-removal-prompt-in-bypasspermissions-mode)。您無法透過 `Bash` 或 `Bash(*)` 允許規則、沙箱[自動允許模式](https://code.claude.com/docs/zh-TW/sandboxing.md#auto-allow-mode)或返回 `"allow"` 的 `PreToolUse` hook 核准此命令。請閱讀命令，然後核准提示，或在遭拒絕後於您的 shell 中執行它。

### 已掛載磁碟機提示

當遞迴 `rm` 的目標是列出的[已掛載磁碟機路徑](#paths-that-get-the-mounted-drive-prompt)（例如 `/mnt/c` 或 `/Volumes/USB/build`）時，已掛載磁碟機提示會出現在 macOS、Linux 和 WSL 上。其原因顯示為 `Dangerous rm operation on mounted drive path: <path>`。`/*` 目標即使沒有遞迴旗標也會出現此提示，因為 Claude Code 將 `rm /Volumes/USB/build/*` 視為對 `/Volumes/USB/build` 的移除。

即使有針對 `rm` 的允許規則，Claude Code 仍會將該命令作為[關鍵路徑移除](#critical-paths)處理：根據[您的權限模式](#critical-path-removals-in-each-permission-mode)顯示提示或拒絕。核准提示即可讓 `rm` 執行，或[關閉此提示](#turn-off-the-mounted-drive-prompt)。

#### 會出現已掛載磁碟機提示的路徑

將您的遞迴 `rm` 或 `/*` 移除的目標與以下路徑形式比對，其中每個預留位置（例如 `<drive>` 或 `<name>`）恰好代表一個路徑區段：

| 位於 | 會出現提示的路徑形式 | 範例 |
| :- | :- | :- |
| `/Volumes` | `/Volumes/<drive>`、`/Volumes/<drive>/<name>` | `/Volumes/USB`、`/Volumes/USB/build` |
| `/System/Volumes` | `/System/Volumes`、`/System/Volumes/<volume>`、`/System/Volumes/<volume>/<name>` | `/System/Volumes/Data` |
| `/media` | `/media/<user>`、`/media/<user>/<drive>`、`/media/<user>/<drive>/<name>` | `/media/alex` |
| `/run/media` | `/run/media`、`/run/media/<user>`、`/run/media/<user>/<drive>`、`/run/media/<user>/<drive>/<name>` | `/run/media/alex/USB/build` |
| `/mnt` | `/mnt/<name>`，以及單一字母掛載點（例如 WSL 的 `/mnt/c`）下的 `/mnt/<letter>/<name>` | `/mnt/data`、`/mnt/c/Users` |

對於 `/Volumes`、`/media` 或 `/mnt` 本身的遞迴或非遞迴 `rm`，您會改為看到[關鍵路徑](#which-paths-are-critical)原因 `Dangerous rm operation on critical path: <path>`。

相對目標會從您的工作目錄起算，因此當您在 `/Volumes/USB` 中工作時，`rm -rf build` 的目標是 `/Volumes/USB/build`，並會出現此提示。

#### 關閉已掛載磁碟機提示

若要停止出現已掛載磁碟機提示，同時保留[其他原因引起的提示](#removals-that-still-prompt-with-the-mounted-drive-prompt-off)，請在環境中設定 [`CLAUDE_CODE_DISABLE_MOUNTED_DRIVE_RM_PROMPT=1`](https://code.claude.com/docs/zh-TW/env-vars#variables) 來啟動 Claude Code。例如，在[您的 shell](https://code.claude.com/docs/zh-TW/env-vars.md#set-variables-in-your-shell) 中設定該變數，並從該 shell 啟動 `claude`：

```bash theme={null}
export CLAUDE_CODE_DISABLE_MOUNTED_DRIVE_RM_PROMPT=1
claude
```

在以此方式啟動的工作階段中，對於 `/Volumes/USB` 等整個磁碟機以及其他[列出的路徑](#paths-that-get-the-mounted-drive-prompt)，已掛載磁碟機提示都會停止出現。如果您允許 `Bash(rm *)`、使用 Manual 模式，並在 `/Volumes/USB` 中工作，那麼 `rm -rf build` 會在沒有提示的情況下執行。

如果提示仍顯示 `Dangerous rm operation on mounted drive path`，表示該變數未傳遞到工作階段：

* **變數位於設定檔中**：無論是哪種設定檔，Claude Code 都會[忽略設定檔 `env` 區塊中的此變數](https://code.claude.com/docs/zh-TW/settings-reference#variables-claude-code-ignores-in-env)，因此請改在您啟動 `claude` 的地方設定該變數
* **工作階段啟動時未設定變數**：請從已設定該變數的環境重新啟動 `claude`，因為執行中的工作階段不會取得該變數

#### 關閉已掛載磁碟機提示後仍會提示的移除

在 Manual 模式中且有針對 `rm` 的允許規則時，對已掛載磁碟機路徑的 `rm` 仍可能出現提示，但不帶 `Dangerous rm operation on mounted drive path` 原因：

* **目標位於您的工作目錄之外**：當您在 `/Volumes/USB/project` 中工作時，`rm -rf /Volumes/USB/other` 會出現提示。若要停止該提示，請將[包含該目標的目錄新增](https://code.claude.com/docs/zh-TW/permissions.md#working-directories)至工作階段
* **目標含有 `*`**：`rm -rf build/*` 會出現提示。核准該提示即可執行命令，或要求 Claude 不使用 `*` 而逐一指名每個目標
* **目標是關鍵路徑**：`/mnt` 本身和您的工作目錄本身仍是[關鍵路徑](#which-paths-are-critical)，因此對其中任一者執行 `rm -rf` 會出現提示。核准該提示即可讓 `rm` 執行

### 每個權限模式中的關鍵路徑移除

Claude Code 對關鍵路徑移除的處理取決於您的權限模式：

| 模式 | 結果 |
| :- | :- |
| `default`、`acceptEdits` | 要求您批准 |
| `plan` | 要求您批准。當[分類器在規劃期間檢查命令](#analyze-before-you-edit-with-plan-mode)且沒有可用的繞過權限時，按 `auto` 模式處理 |
| `auto` | 在終端中要求您批准，有[時間限制](#time-limits-and-denials-in-auto-and-bypasspermissions-modes)。在其他地方，拒絕它 |
| `dontAsk` | 拒絕它 |
| `bypassPermissions` | 在終端機中，要求您在時間限制用完前核准。在其他地方，請參閱[各處的處理方式](#time-limits-and-denials-in-auto-and-bypasspermissions-modes) |

如果明確的[詢問規則](https://code.claude.com/docs/zh-TW/permissions.md#manage-permissions)與命令匹配，Claude Code 會改為詢問您，即使在 `auto` 模式中也沒有時間限制。在詢問的模式中，[`PermissionRequest` hook](https://code.claude.com/docs/zh-TW/hooks#permissionrequest) 可以回答提示。

若要在 `bypassPermissions` 模式中不經提示即執行這些移除，請參閱[關閉關鍵路徑移除提示](#turn-off-the-critical-path-removal-prompt-in-bypasspermissions-mode)。

### auto 和 bypassPermissions 模式中的時間限制和拒絕

在 `auto` 和 `bypassPermissions` 模式中，關鍵路徑移除的終端提示顯示兩分鐘倒計時：

* 如果倒計時在您回答前用完，Claude Code 會拒絕該命令並告訴 Claude 改為執行什麼，因此無人值守的工作階段會繼續工作。
* 在提示打開時按任何鍵以停止倒計時並保持提示等待您的回答。
* 在一個工作階段中，這些提示中的三個在無人回答的情況下用完後，Claude Code 會停止顯示它們並立即拒絕進一步的關鍵路徑移除。發送新訊息會重新開始計數。

時間限制適用於 Claude Code v2.1.281 及更新版本，`auto` 模式在終端機以外的拒絕也是如此。

不在終端機時，您不會收到該提示：

| 位置 | `auto` | `bypassPermissions` |
| :- | :- | :- |
| [VS Code 擴充功能](https://code.claude.com/docs/zh-TW/vs-code.md)的聊天面板 | 拒絕它 | 除非 [`PermissionRequest` hook](https://code.claude.com/docs/zh-TW/hooks#permissionrequest) 允許，否則拒絕它 |
| [桌面應用程式](https://code.claude.com/docs/zh-TW/desktop.md) | 拒絕它 | 除非 `PermissionRequest` hook 允許，否則拒絕它 |
| [`-p` 執行](https://code.claude.com/docs/zh-TW/headless)或 [Agent SDK 工作階段](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md) | 拒絕它 | 由您的 [`--permission-prompt-tool`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 或 [`canUseTool` 回呼](https://code.claude.com/docs/zh-TW/agent-sdk/user-input#handle-tool-approval-requests)決定。若兩者皆無，或在 [`--permission-prompts none`](https://code.claude.com/docs/zh-TW/headless#turn-off-permission-prompts-in-unattended-runs) 下，除非 `PermissionRequest` hook 允許，否則拒絕它。若要改為不經提示即執行這些移除，請參閱[關閉關鍵路徑移除提示](#turn-off-the-critical-path-removal-prompt-in-bypasspermissions-mode) |

無論移除在何處遭拒絕，您都可以閱讀完整命令並在您的 shell 中執行它。

若要變更每種模式下的處理方式，請將 [`CLAUDE_CODE_DISABLE_DANGEROUS_RM_TIMEOUT`](https://code.claude.com/docs/zh-TW/env-vars#variables) 設為 `1`：

* **`bypassPermissions`**：終端機提示沒有時間限制，且 VS Code 聊天面板會詢問您
* **`auto`**：由[分類器](#eliminate-prompts-with-auto-mode)決定，適用於終端機、VS Code 聊天面板、`-p` 執行和 Agent SDK 工作階段

請在啟動 Claude Code 的環境中設定它，例如您的 shell 或 SDK 的 `env` 選項，而不是在 Claude Code 設定檔中。若要用於聊天面板，請將它加入 VS Code 本身的使用者 `settings.json` 中的 [`claudeCode.environmentVariables`](https://code.claude.com/docs/zh-TW/vs-code#extension-settings)，然後開始新的對話：

```json theme={null}
{
  "claudeCode.environmentVariables": [
    { "name": "CLAUDE_CODE_DISABLE_DANGEROUS_RM_TIMEOUT", "value": "1" }
  ]
}
```

### 在 bypassPermissions 模式中關閉關鍵路徑移除提示

若要在 `bypassPermissions` 模式中不經提示即執行以[關鍵路徑](#critical-paths)為目標的 Bash `rm` 和 `rmdir` 命令，請在環境中設定 [`CLAUDE_CODE_EVEN_MORE_DANGEROUSLY_SKIP_PERMISSIONS=1`](https://code.claude.com/docs/zh-TW/env-vars#variables) 來啟動 Claude Code。這需要 Claude Code v2.1.311 或更新版本。Claude Code 僅從啟動環境讀取此變數，並會[忽略設定檔 `env` 區塊中的此變數](https://code.claude.com/docs/zh-TW/settings-reference#variables-claude-code-ignores-in-env)。例如，在[您的 shell](https://code.claude.com/docs/zh-TW/env-vars.md#set-variables-in-your-shell) 中設定它，並從該處啟動 `claude`：

> [tab] macOS, Linux, WSL
>
> ```bash theme={null}
> export CLAUDE_CODE_EVEN_MORE_DANGEROUSLY_SKIP_PERMISSIONS=1
> claude --permission-mode bypassPermissions
> ```

> [tab] Windows PowerShell
>
> ```powershell theme={null}
> $env:CLAUDE_CODE_EVEN_MORE_DANGEROUSLY_SKIP_PERMISSIONS = "1"
> claude --permission-mode bypassPermissions
> ```

> [tab] Windows CMD
>
> ```batch theme={null}
> set CLAUDE_CODE_EVEN_MORE_DANGEROUSLY_SKIP_PERMISSIONS=1
> claude --permission-mode bypassPermissions
> ```

> [!WARNING]
>
> 設定此變數後，您會失去針對破壞性刪除的安全提示：`rm -rf ~` 之類的命令可能在不詢問您的情況下執行。請僅在內容遺失也無妨的[隔離環境](#skip-all-checks-with-bypasspermissions-mode)中設定它。

移除僅在 `bypassPermissions` 模式本身中不經提示執行，在 plan mode 中則不會，且僅限於 Bash 和 [Monitor](https://code.claude.com/docs/zh-TW/tools-reference.md#monitor-tool) 工具中被關鍵路徑檢查標記的項目。這包括 Claude Code 無法完整解析的命令，這些命令同樣會不經提示執行。

#### 關於關鍵路徑移除提示的啟動通知

若要確認 `CLAUDE_CODE_EVEN_MORE_DANGEROUSLY_SKIP_PERMISSIONS` 是否生效，請閱讀 Claude Code 在啟動時印出的那一行。在 `-p` 執行中，它位於 stderr。在 Agent SDK 應用程式中，請傳入 [`stderr` 選項](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#options)以讀取它。該行會顯示以下其中一項：

* **`is set, so dangerous rm commands can run without a prompt`**：在受管設定和外掛 hook 載入後，移除即可不經提示執行。如果移除仍持續出現提示或遭拒絕，請參閱[為何關鍵路徑移除提示仍保持開啟](#why-the-critical-path-removal-prompt-stays-on)
* **`has no effect in this session`**：移除在整個工作階段中維持其一般的提示或拒絕。若要變更此情況，請在[為何關鍵路徑移除提示仍保持開啟](#why-the-critical-path-removal-prompt-stays-on)中找出您的情況
* **`has no effect while the Windows registry cannot be read for managed settings`**：移除維持其一般的提示或拒絕，若之後讀取登錄檔成功，此變數會在不需重新啟動的情況下生效。如果移除仍持續出現提示或遭拒絕，請參閱[為何關鍵路徑移除提示仍保持開啟](#why-the-critical-path-removal-prompt-stays-on)

沒有該行並不代表提示已開啟：未設定 `stderr` 選項的 Agent SDK 應用程式看不到該行，而移除仍可不經提示執行。否則，請確認您已在啟動環境中設定該變數、工作階段[可以進入 `bypassPermissions` 模式](#skip-all-checks-with-bypasspermissions-mode)，且 `claude` 並非在另一個工作階段內執行。某些工作階段[啟動時不帶有該變數](#why-the-critical-path-removal-prompt-stays-on)。

如果您看到其中一行但並未設定該變數，請找出設定它的位置（例如您的 shell 設定檔），並將其移除。

#### 為何關鍵路徑移除提示仍保持開啟

如果 `CLAUDE_CODE_EVEN_MORE_DANGEROUSLY_SKIP_PERMISSIONS` 沒有效果，且移除維持其[一般的提示或拒絕](#critical-path-removals-in-each-permission-mode)，請檢查是否有以下原因：

* **其他機制處理權限提示**：未搭配 [`--permission-prompts none`](https://code.claude.com/docs/zh-TW/headless#turn-off-permission-prompts-in-unattended-runs) 的 [`--permission-prompt-tool`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 或 Agent SDK [`canUseTool` 回呼](https://code.claude.com/docs/zh-TW/agent-sdk/user-input)、具有任何 matcher 的 [`PermissionRequest` hook](https://code.claude.com/docs/zh-TW/hooks#permissionrequest)，或處理該事件的 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/events.md#hook-the-settings-hook-events)。移除該 hook、mod、工具或回呼，然後重新啟動 `claude`
* **由 [VS Code 擴充功能](https://code.claude.com/docs/zh-TW/vs-code.md)的聊天面板或[桌面應用程式](https://code.claude.com/docs/zh-TW/desktop.md)執行工作階段**：請改在終端機中啟動 `claude`，例如 IDE 的整合式終端機
* **有規則涵蓋 Bash、Edit 或 Read**：以這些工具之一為目標的[拒絕或詢問規則](https://code.claude.com/docs/zh-TW/permissions.md#manage-permissions)，無論是在啟動時存在，或在工作階段期間被 Claude Code 讀取，即使您之後將其移除也一樣。移除該規則並重新啟動 `claude`。若要排除某個工具，請使用 [`--tools`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 而非拒絕規則
* **[`permissions.blockReadsOutsideWorkingDirectories`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-blockreadsoutsideworkingdirectories) 已開啟**：從每個將其設為 `true` 的設定檔中移除此設定，然後重新啟動 `claude`
* **`claude` 在另一個工作階段內執行**：從工作階段的 Bash 工具或 hook 啟動的 `claude`，即使其命令列上帶有該變數也一樣。請從您自己的 shell 啟動 `claude`。請勿將此巢狀工作階段限制視為安全邊界
* **`PreToolUse` hook 對移除回應 `ask`**：變更該 hook 的回傳值
* **由 Claude Code 為您啟動工作階段**：[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)、分割窗格中的 [agent team](https://code.claude.com/docs/zh-TW/agent-teams.md) 隊員，以及 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 伺服器建立的工作階段，啟動時都不帶有該變數。請從您自己的 shell 啟動 `claude`
* **無法讀取受管設定**：Claude Code 尚未成功讀取您的[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)來源。如果伺服器受管設定持續無法載入，請參閱 [Remote managed settings failed to load](https://code.claude.com/docs/zh-TW/errors.md#remote-managed-settings-failed-to-load)。對於任何不是登錄檔查詢的其他失敗，請要求管理該來源的人員修正
* **無法查詢 Windows 登錄檔**：在 Windows 和 WSL 中，此變數需要登錄檔的回應，即使 [WSL 不將其用於設定](https://code.claude.com/docs/zh-TW/settings-reference.md#wslinheritswindowssettings)也是如此。在非英文版 Windows、關閉 interop 的 WSL，或 WSL2 核心上的容器中，查詢可能在整個工作階段中都失敗。如果 interop 已關閉，請將其開啟。否則，請自行執行這些移除

### PowerShell 中的 Remove-Item

當您啟用 [PowerShell 工具](https://code.claude.com/docs/zh-TW/tools-reference.md#powershell-tool)時，Claude Code 為 `Remove-Item` 和 `cmd` 內建命令 `rd`、`rmdir`、`del` 和 `erase` 提供自己的檢查，與 `rm` 關鍵路徑清單分開。對於 `Remove-Item`，結果取決於目標，第一個匹配的情況適用：

* **系統路徑**：檔案系統根目錄及其頂級目錄、磁碟機根目錄及其頂級目錄，以及您的主目錄。Claude Code 在每種模式中都拒絕該命令，不詢問您。
* **萬用字元**：裸 `*`，或任何以 `/*` 或 `\*` 結尾的目標，包括 shell 變數下的 glob，例如 `$dir/*`。Claude Code 在每種模式中都拒絕該命令，不詢問您，在[分類器](#eliminate-prompts-with-auto-mode)看到它之前。
* **您的工作目錄或其父目錄之一，帶有 `-Recurse`**：Claude Code 將命令視為任何其他需要在您的權限模式中批准的命令，因此它在詢問的模式中詢問您，在 `auto` 模式中將其發送給分類器，在 `dontAsk` 模式中拒絕它。`bypassPermissions` 模式跳過此檢查。

系統路徑情況也適用於 `rd`、`rmdir`、`del` 和 `erase`，當 Claude 通過 `cmd` 執行它們時，如 `cmd /c rd /s /q C:\Users`。預設情況下，Claude Code 在每種模式中都拒絕此類命令，不詢問您。此 `cmd` 檢查需要 Claude Code v2.1.283 或更新版本。

在判斷 `cmd` 目標時，Claude Code 將跟在字面文字後的 PowerShell 變數視為空。這使得 `cmd /c rd /s /q "C:\$name"` 成為 `C:\` 的移除，因此它也被拒絕。尾部萬用字元計為它清空的資料夾，因此 `cmd /c del /q C:\*` 被拒絕，而 `cmd /c del /q dist\*` 在您的專案中則不被拒絕。

要關閉 `cmd` 檢查，請在啟動 Claude Code 的環境中設定 [`CLAUDE_CODE_DISABLE_POWERSHELL_CMD_RM_DENY=1`](https://code.claude.com/docs/zh-TW/env-vars#variables)。Claude Code 在設定檔的 `env` 區塊中忽略此變數。系統路徑上的 `Remove-Item` 無論如何都保持被拒絕。

## 另請參閱

* [Permissions](https://code.claude.com/docs/zh-TW/permissions.md)：allow、ask 和 deny 規則；受管理的原則
* [Configure auto mode](https://code.claude.com/docs/zh-TW/auto-mode-config.md)：告訴分類器您的組織信任哪些基礎設施
* [Hooks](https://code.claude.com/docs/zh-TW/hooks.md)：透過 `PreToolUse` 和 `PermissionRequest` hooks 的自訂權限邏輯
* [Security](https://code.claude.com/docs/zh-TW/security.md)：保護措施和最佳實踐
* [Sandboxing](https://code.claude.com/docs/zh-TW/sandboxing.md)：Bash 命令的檔案系統和網路隔離
* [Non-interactive mode](https://code.claude.com/docs/zh-TW/headless.md)：使用 `-p` 旗標執行 Claude Code

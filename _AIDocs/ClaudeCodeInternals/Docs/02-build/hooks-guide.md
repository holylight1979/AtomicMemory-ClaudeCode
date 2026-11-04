<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/hooks-guide | lastmod: 2026-11-02 | section: Build with Claude Code / Automation -->
> 來源：https://code.claude.com/docs/zh-TW/hooks-guide（官方 zh-TW，lastmod 2026-11-02）｜分類：Build with Claude Code › Automation｜EN 摘要：Run shell commands automatically when Claude Code edits files, finishes tasks, or needs input. Format code, send notifications, validate commands, and enforce project rules.

# 使用 hooks 自動化工作流程

> 當 Claude Code 編輯檔案、完成任務或需要輸入時，自動執行 shell 命令。格式化程式碼、發送通知、驗證命令並強制執行專案規則。

Hooks 是使用者定義的 shell 命令。Claude Code 在其生命週期的特定時間點執行它們，這給予您確定性的控制：某些操作總是會發生，而不是依賴 LLM 選擇執行它們。使用 hooks 來強制執行專案規則、自動化重複性任務，並將 Claude Code 與您現有的工具整合。

對於需要判斷而不是確定性規則的決策，您也可以使用[基於提示的 hooks](#prompt-based-hooks) 或[基於代理的 hooks](#agent-based-hooks)，它們使用 Claude 模型來評估條件。

有關擴展 Claude Code 的其他方式，請參閱[skills](https://code.claude.com/docs/zh-TW/skills.md)以提供 Claude 額外的指令和可執行命令、[subagents](https://code.claude.com/docs/zh-TW/sub-agents.md)以在隔離的上下文中執行任務，以及[plugins](https://code.claude.com/docs/zh-TW/plugins/overview.md)以打包要在專案間共享的擴展。

> [!TIP]
>
> 本指南涵蓋常見用例和入門方式。有關完整的事件架構、JSON 輸入/輸出格式和非同步 hooks 和 MCP 工具 hooks 等進階功能，請參閱 [Hooks 參考](https://code.claude.com/docs/zh-TW/hooks.md)。

## 設定您的第一個 hook

若要建立 hook，請將 `hooks` 區塊新增到[設定檔](#configure-hook-location)。本逐步解說建立一個桌面通知 hook，因此每當 Claude 等待您的輸入而不是監視終端時，您都會收到警報。

**1. 將 hook 新增到您的設定**

開啟 `~/.claude/settings.json` 並新增 `Notification` hook。如果檔案不存在，請建立它。下面的範例使用 `osascript` 進行 macOS；有關 Linux 和 Windows 命令，請參閱[當 Claude 需要輸入時收到通知](#get-notified-when-claude-needs-input)。

```json theme={null}
{
  "hooks": {
    "Notification": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "osascript -e 'display notification \"Claude Code needs your attention\" with title \"Claude Code\"'"
          }
        ]
      }
    ]
  }
}
```

如果您的設定檔已經有 `hooks` 鍵，請將 `Notification` 作為現有事件鍵的同級項目新增，而不是替換整個物件。每個事件名稱是單個 `hooks` 物件內的鍵：

```json theme={null}
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [{ "type": "command", "command": "jq -r '.tool_input.file_path' | xargs npx prettier --write" }]
      }
    ],
    "Notification": [
      {
        "matcher": "",
        "hooks": [{ "type": "command", "command": "osascript -e 'display notification \"Claude Code needs your attention\" with title \"Claude Code\"'" }]
      }
    ]
  }
}
```

您也可以透過在 CLI 中描述您想要的內容，要求 Claude 為您編寫 hook。

**2. 驗證設定**

在 Claude Code 提示字元輸入 `/hooks` 以開啟 hooks 瀏覽器。您的新 hook 會出現在 `Notification` 下的列表中。

**3. 測試 hook**

按 `Esc` 返回 CLI。按 `Shift+Tab` 直到狀態列顯示 `⏸ manual mode on`，要求 Claude 執行需要權限的操作，然後切換離開終端機。您應該會收到桌面通知。

## 您可以自動化的項目

hook 讓您在 Claude Code 生命週期的關鍵時間點執行程式碼：在編輯後格式化檔案、在命令執行前加以封鎖、在 Claude 需要輸入時傳送通知、在工作階段開始時注入上下文等等。如需 hook 事件的完整清單，請參閱 [Hooks 參考](https://code.claude.com/docs/zh-TW/hooks.md#hook-lifecycle)。

每個範例都包含一個可直接使用的設定區塊，您可以將其新增至[設定檔](#configure-hook-location)。

如需在實際環境中使用 hook 執行獨立模型審查並將發現結果回饋至工作階段的範例，請參閱 [`security-guidance` 外掛如何與 Claude Code 整合](https://code.claude.com/docs/zh-TW/security-guidance#how-the-plugin-integrates-with-claude-code)。

### 在 Claude 需要輸入時收到通知

每當 Claude 完成工作並需要您的輸入時，即可收到桌面通知，讓您可以切換至其他工作，而無需反覆查看終端機。

此 hook 使用 `Notification` 事件，Claude Code 會在 Claude 等待輸入或權限時觸發此事件。確切時機請參閱[各通知類型的觸發時機](https://code.claude.com/docs/zh-TW/hooks.md#notification)。

以下每個分頁都使用該平台原生的通知命令。將此內容新增至 `~/.claude/settings.json`：

> [tab] macOS
>
> ```json theme={null}
> {
>   "hooks": {
>     "Notification": [
>       {
>         "matcher": "",
>         "hooks": [
>           {
>             "type": "command",
>             "command": "osascript -e 'display notification \"Claude Code needs your attention\" with title \"Claude Code\"'"
>           }
>         ]
>       }
>     ]
>   }
> }
> ```
>
> > [accordion] 如果沒有出現通知
> >
> > `osascript` 會透過內建的 Script Editor 應用程式傳送通知。如果 Script Editor 沒有通知權限，該命令會靜默失敗，且 macOS 不會提示您授予權限。
> >
> > 在 Terminal 中執行此命令一次，讓 Script Editor 出現在您的通知設定中：
> >
> > ```bash theme={null}
> > osascript -e 'display notification "test"'
> > ```
> >
> > 此時還不會出現任何通知。開啟 **System Settings > Notifications**，在清單中找到 **Script Editor**，然後開啟 **Allow Notifications**。再次執行該命令，確認測試通知有出現。

> [tab] Linux
>
> ```json theme={null}
> {
>   "hooks": {
>     "Notification": [
>       {
>         "matcher": "",
>         "hooks": [
>           {
>             "type": "command",
>             "command": "notify-send 'Claude Code' 'Claude Code needs your attention'"
>           }
>         ]
>       }
>     ]
>   }
> }
> ```
>
> > [accordion] 如果沒有出現通知
> >
> > `notify-send` 需要桌面通知常駐程式，而無頭伺服器、SSH 工作階段和大多數容器都沒有此程式。請先直接測試該命令：
> >
> > ```bash theme={null}
> > notify-send 'Claude Code' 'test'
> > ```
> >
> > 如果找不到該命令，請在 Debian 和 Ubuntu 上安裝 `libnotify-bin` 套件，或安裝您的發行版中的對應套件。

> [tab] Windows (PowerShell)
>
> ```json theme={null}
> {
>   "hooks": {
>     "Notification": [
>       {
>         "matcher": "",
>         "hooks": [
>           {
>             "type": "command",
>             "command": "powershell.exe -Command \"[System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms'); [System.Windows.Forms.MessageBox]::Show('Claude Code needs your attention', 'Claude Code')\""
>           }
>         ]
>       }
>     ]
>   }
> }
> ```
>
> > [accordion] 如果沒有出現對話方塊
> >
> > 此命令會開啟對話方塊，而非在螢幕角落顯示通知，因此對話方塊可能會在您的終端機視窗後方開啟。請先直接在 PowerShell 中測試該命令。
> >
> > 如果您在 WSL 中執行 Claude Code，`powershell.exe` 必須透過 Windows interop 在您的 `PATH` 上可用。

空的 `matcher` 會在所有通知類型上觸發。若只要在特定事件上觸發，請將其設為下列其中一個值：

| Matcher | 觸發時機 |
| :- | :- |
| `permission_prompt` | Claude 需要您核准工具使用或沙箱化命令的[網路請求](https://code.claude.com/docs/zh-TW/sandboxing.md#network-isolation)，且提示已等待約六秒 |
| `idle_prompt` | Claude 約 60 秒前完成回應，且您此後未曾輸入 |
| `auth_success` | 身分驗證完成 |
| `elicitation_dialog` | MCP 伺服器開啟 elicitation 表單，且您約六秒未輸入 |
| `elicitation_url_dialog` | MCP 伺服器要求您開啟瀏覽器 URL，且您約六秒未輸入 |
| `elicitation_complete` | MCP 伺服器回報 [URL 模式 elicitation](https://code.claude.com/docs/zh-TW/hooks.md#elicitation-input) 已完成 |
| `elicitation_response` | MCP elicitation 回應已傳回伺服器 |
| `agent_needs_input` | 在 [agent view](https://code.claude.com/docs/zh-TW/agent-view.md) 開啟期間，背景工作階段開始等待您的輸入。當終端機工作階段向您顯示 [agent team 隊員的終端機設定問題](https://code.claude.com/docs/zh-TW/agent-teams.md#choose-a-display-mode)或自動模式關於[分類器請求費用](https://code.claude.com/docs/zh-TW/auto-mode-classifier-billing.md)的通知，且您約六秒未輸入時，也會觸發 |
| `agent_completed` | 背景工作階段完成或失敗。僅在 [agent view](https://code.claude.com/docs/zh-TW/agent-view.md) 開啟期間觸發 |
| `quota_auto_resume_fired` | 在 claude.ai 用量上限暫停您的工作後，Claude Code 繼續執行該工作：在重設時，或者當您在等待期間於 Claude Code 中執行的某些操作（例如新增用量點數、升級方案或切換模型）使用量再次可用時提早繼續，但有[模型設定的例外情況](https://code.claude.com/docs/zh-TW/interactive-mode.md#wait-for-a-usage-limit-to-reset) |
| `quota_auto_resume_stale` | claude.ai 用量上限在您的電腦睡眠超過約 30 分鐘期間重設。Claude Code 會等待您按下 `Enter`，而不是繼續執行。若睡眠時間較短，則會繼續執行並改為觸發 `quota_auto_resume_fired` |
| `quota_auto_resume_disabled` | Claude Code 結束對 claude.ai 用量上限的等待，且未繼續執行您的工作：在 Claude Code 自行開始的等待期間 [`autoContinueAtUsageLimit`](https://code.claude.com/docs/zh-TW/settings-reference#autocontinueatusagelimit) 被關閉或重設時間延至 24 小時以後；繼續執行的工作持續觸及上限；或繼續執行在到達模型之前遭到封鎖。當您按下 `Esc` 或 `Ctrl+C`，或選擇 **Don't continue automatically** 時不會觸發 |
| `plugin_notification` | [mod](https://code.claude.com/docs/zh-TW/plugins/mods/api.md#show-something-without-starting-a-turn) 透過 `$.ui.notify` 發出通知。除非 mod 自行設定，否則 hook 的 `title` 為該 mod 的名稱 |

Claude Code 在終端機中，以及在 Claude Desktop、VS Code 擴充功能和其他透過 Agent SDK 回應權限請求的主機中，對 `permission_prompt` 的計時方式不同。兩種計時方式請參閱[各通知類型的觸發時機](https://code.claude.com/docs/zh-TW/hooks.md#notification)。

`quota_auto_resume_fired`、`quota_auto_resume_stale` 和 `quota_auto_resume_disabled` matcher 需要 Claude Code v2.1.234 或更新版本。

在終端機工作階段中，針對沙箱化命令網路請求的 `permission_prompt` 需要 Claude Code v2.1.246 或更新版本。

針對隊員終端機設定問題的 `agent_needs_input` 需要 Claude Code v2.1.248 或更新版本。

在 Claude Code 提示字元中輸入 `/hooks`，並確認該 hook 出現在 `Notification` 下方。

### 在編輯後自動格式化程式碼

在 Claude 編輯的每個檔案上自動執行 [Prettier](https://prettier.io/)，讓格式保持一致，無需手動介入。

此 hook 使用帶有 `Edit|Write` matcher 的 `PostToolUse` 事件，因此只會在檔案編輯工具之後執行。該命令使用 [`jq`](https://jqlang.org/) 擷取已編輯的檔案路徑，並將其傳遞給 Prettier。將此內容新增至專案根目錄中的 `.claude/settings.json`：

```json theme={null}
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "jq -r '.tool_input.file_path' | xargs npx prettier --write"
          }
        ]
      }
    ]
  }
}
```

若要測試此 hook，請要求 Claude 在 JavaScript 檔案中新增一行包含單引號字串的程式碼，然後開啟該檔案：在 Prettier 的預設設定下，hook 會將其改寫為雙引號。

hook 成功時，Claude Code 不會在對話中顯示任何內容。若要確認 hook 已執行，請檢查已編輯的檔案是否已重新格式化，或參閱[檢查 hook 執行了什麼](#check-what-a-hook-did)。

若要在特定檔案發生任何變更時（包括 `Bash` 命令改寫它時）重新格式化該檔案，請改用 [FileChanged](https://code.claude.com/docs/zh-TW/hooks.md#filechanged) hook。

> [!NOTE]
>
> 本頁的 Bash 範例使用 `jq` 進行 JSON 解析。在 macOS 上使用 `brew install jq` 安裝，在 Debian 和 Ubuntu 上使用 `apt-get install jq` 安裝，或參閱 [`jq` 下載](https://jqlang.org/download/)。

### 封鎖對受保護檔案的編輯

防止 Claude 修改敏感檔案，例如 `.env`、`package-lock.json` 或 `.git/` 中的任何內容。Claude 會收到說明編輯遭封鎖原因的回饋，以便調整其做法。

此範例使用由 hook 呼叫的獨立指令碼檔案。該指令碼會將目標檔案路徑與受保護模式清單進行比對，並以退出碼 2 結束來封鎖編輯。

**1. 建立 hook 指令碼**

將此內容儲存至 `.claude/hooks/protect-files.sh`：

```bash theme={null}
#!/bin/bash
# protect-files.sh

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Normalize Windows backslash separators so the patterns below match
FILE_PATH="${FILE_PATH//\\//}"

PROTECTED_PATTERNS=(".env" "package-lock.json" ".git/")

for pattern in "${PROTECTED_PATTERNS[@]}"; do
  if [[ "$FILE_PATH" == *"$pattern"* ]]; then
    echo "Blocked: $FILE_PATH matches protected pattern '$pattern'" >&2
    exit 2
  fi
done

exit 0
```

**2. 在 macOS 和 Linux 上將指令碼設為可執行**

hook 指令碼必須是可執行的，Claude Code 才能執行它們：

```bash theme={null}
chmod +x .claude/hooks/protect-files.sh
```

**3. 註冊 hook**

在 `.claude/settings.json` 中新增一個 `PreToolUse` hook，在任何 `Edit` 或 `Write` 工具呼叫之前執行該指令碼：

```json theme={null}
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/protect-files.sh"
          }
        ]
      }
    ]
  }
}
```

**4. 測試 hook**

要求 Claude 在您的 `.env` 檔案中新增註解。Claude Code 會在編輯執行前將其封鎖，並將指令碼的 `Blocked:` 訊息作為回饋傳遞給 Claude。

### 在壓縮後重新注入上下文

當 Claude 的上下文視窗填滿時，壓縮會摘要對話以釋放空間。這可能會遺失重要細節。使用帶有 `compact` matcher 的 `SessionStart` hook，在每次壓縮後重新注入關鍵上下文。

Claude Code 會將您的命令寫入 stdout 的純文字新增至 Claude 的上下文中。此範例會提醒 Claude 專案慣例和近期工作。將此內容新增至專案根目錄中的 `.claude/settings.json`：

```json theme={null}
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "compact",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Reminder: use Bun, not npm. Run bun test before committing. Current sprint: auth refactor.'"
          }
        ]
      }
    ]
  }
}
```

您可以將 `echo` 替換為任何產生動態輸出的命令，例如使用 `git log --oneline -5` 顯示近期提交。若要在每次工作階段開始時注入上下文，請考慮改用 [CLAUDE.md](https://code.claude.com/docs/zh-TW/memory.md)。關於環境變數，請參閱參考中的 [`CLAUDE_ENV_FILE`](https://code.claude.com/docs/zh-TW/hooks#persist-environment-variables)。

### 稽核設定變更

追蹤工作階段期間設定檔或 skill 檔案的變更時間。`ConfigChange` 事件會在外部程序或編輯器修改設定檔時觸發，因此您可以記錄變更以符合法規要求，或封鎖未經授權的修改。

此範例會將每次變更附加至稽核日誌。將此內容新增至 `~/.claude/settings.json`：

```json theme={null}
{
  "hooks": {
    "ConfigChange": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "jq -c '{timestamp: now | todate, source: .source, file: .file_path}' >> ~/claude-config-audit.log"
          }
        ]
      }
    ]
  }
}
```

matcher 依設定類型進行篩選：`user_settings`、`project_settings`、`local_settings`、`policy_settings` 或 `skills`。若要封鎖變更生效，請以退出碼 2 結束或傳回 `{"decision": "block"}`。完整的輸入 schema 請參閱 [ConfigChange 參考](https://code.claude.com/docs/zh-TW/hooks.md#configchange)。

若要確認 hook 有記錄變更，請在工作階段執行期間於另一個編輯器中編輯設定檔，然後開啟 `~/claude-config-audit.log`：hook 會針對每次變更附加一行包含時間戳記、來源和檔案路徑的 JSON。

### 在目錄或檔案變更時重新載入環境

有些專案會根據您所在的目錄設定不同的環境變數。像 [direnv](https://direnv.net/) 這類工具會在您的 shell 中自動完成此操作，但 Claude 的 Bash 工具不會自行取得這些變更。

將 `SessionStart` hook 與 `CwdChanged` hook 搭配使用即可解決此問題。`SessionStart` 會載入您啟動時所在目錄的變數，而 `CwdChanged` 會在 Claude 每次變更目錄時重新載入它們。兩者都會寫入 `CLAUDE_ENV_FILE`，Claude Code 會在每個 Bash 命令之前將其作為指令碼前置內容執行。將此內容新增至 `~/.claude/settings.json`：

```json theme={null}
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "direnv export bash > \"$CLAUDE_ENV_FILE\""
          }
        ]
      }
    ],
    "CwdChanged": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "direnv export bash > \"$CLAUDE_ENV_FILE\""
          }
        ]
      }
    ]
  }
}
```

在每個含有 `.envrc` 的目錄中執行一次 `direnv allow`，讓 direnv 獲准載入它。如果您使用 devbox 或 nix 而非 direnv，同樣的模式也適用，只需以 `devbox shellenv` 或 `devbox global shellenv` 取代 `direnv export bash`。

若要針對特定檔案而非每次目錄變更做出反應，請使用 `FileChanged` 並搭配列出要監看檔名的 `matcher`，各檔名以 `|` 分隔。建立監看清單時，Claude Code 會將此值拆分為字面檔名，而不是將其作為正規表示式求值。關於同一個值如何在檔案變更時篩選要執行的 hook 群組，請參閱 [FileChanged](https://code.claude.com/docs/zh-TW/hooks.md#filechanged)。此範例會監看工作目錄中的 `.envrc` 和 `.env`：

```json theme={null}
{
  "hooks": {
    "FileChanged": [
      {
        "matcher": ".envrc|.env",
        "hooks": [
          {
            "type": "command",
            "command": "direnv export bash > \"$CLAUDE_ENV_FILE\""
          }
        ]
      }
    ]
  }
}
```

關於輸入 schema、`watchPaths` 輸出和 `CLAUDE_ENV_FILE` 詳細資訊，請參閱 [CwdChanged](https://code.claude.com/docs/zh-TW/hooks.md#cwdchanged) 和 [FileChanged](https://code.claude.com/docs/zh-TW/hooks.md#filechanged) 參考條目。

### 自動核准特定權限提示

針對您一律允許的工具呼叫略過核准對話方塊。此範例會自動核准 `ExitPlanMode`，這是 Claude 完成呈現計畫並請求繼續時所呼叫的工具，因此您不會在每次計畫就緒時都收到提示。

與上述使用退出碼的範例不同，自動核准需要您的 hook 將 JSON 決策寫入 stdout。Claude Code 會在即將向您請求權限時執行 `PermissionRequest` hook，如果您的 hook 傳回 `"behavior": "allow"`，Claude Code 便會代您回應該請求。

matcher 將 hook 的範圍限定為僅 `ExitPlanMode`，因此不會影響其他提示。將此內容新增至 `~/.claude/settings.json`：

```json theme={null}
{
  "hooks": {
    "PermissionRequest": [
      {
        "matcher": "ExitPlanMode",
        "hooks": [
          {
            "type": "command",
            "command": "echo '{\"hookSpecificOutput\": {\"hookEventName\": \"PermissionRequest\", \"decision\": {\"behavior\": \"allow\"}}}'"
          }
        ]
      }
    ]
  }
}
```

當 hook 核准時，Claude Code 會退出 plan mode，並還原您進入 plan mode 之前啟用的權限模式。逐字稿會在原本應出現對話方塊的位置顯示「Allowed by PermissionRequest hook」。hook 路徑一律保留目前的對話：它無法像對話方塊那樣清除上下文並開始新的實作工作階段。

若要改為設定特定的權限模式，您的 hook 輸出可以包含帶有 `setMode` 項目的 `updatedPermissions` 陣列。`mode` 值可以是任何權限模式，例如 `default`、`acceptEdits` 或 `bypassPermissions`，而 `destination: "session"` 只會將其套用於目前的工作階段。

> [!NOTE]
>
> `bypassPermissions` 只有在您啟動工作階段時已可使用略過模式的情況下才會套用：`--dangerously-skip-permissions`、`--permission-mode bypassPermissions`、`--allow-dangerously-skip-permissions`，或在[使用者、`--settings` 或受管設定](https://code.claude.com/docs/zh-TW/settings-reference#permissions-defaultmode)中設定 `permissions.defaultMode: "bypassPermissions"`。如果略過模式已被 [`permissions.disableBypassPermissionsMode`](https://code.claude.com/docs/zh-TW/permissions#managed-settings) 停用，或您是在[受限模式](https://code.claude.com/docs/zh-TW/cli-reference.md#cli-flags)下啟動工作階段，則不會套用。
>
> Claude Code 永遠不會將其儲存為 `defaultMode`。

若要將工作階段切換為 `acceptEdits`，您的 hook 會將此 JSON 寫入 stdout：

```json theme={null}
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "allow",
      "updatedPermissions": [
        { "type": "setMode", "mode": "acceptEdits", "destination": "session" }
      ]
    }
  }
}
```

請盡可能縮小 matcher 的範圍。比對 `.*` 或將 matcher 留空，會自動核准每個工具權限提示，包括檔案寫入和 shell 命令。完整的決策欄位請參閱 [PermissionRequest 參考](https://code.claude.com/docs/zh-TW/hooks.md#permissionrequest-decision-control)。

## hooks 如何運作

Claude Code 在其生命週期的特定時間點觸發 hook 事件。當事件觸發時，Claude Code 會並行執行所有相符的 hook；請參閱 [Hook 處理程式欄位](https://code.claude.com/docs/zh-TW/hooks.md#hook-handler-fields) 以了解重複處理程式的處理方式。下表顯示每個事件及其觸發時機：

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

每個 hook 都有一個 `type` 決定其執行方式。大多數 hooks 使用 `"type": "command"`，它執行 shell 命令。還有四種其他類型可用：

* `"type": "http"`：將事件資料 POST 到 URL。請參閱 [HTTP hooks](#http-hooks)。
* `"type": "mcp_tool"`：在已設定的 MCP 伺服器上呼叫工具。請參閱 [MCP tool hooks](https://code.claude.com/docs/zh-TW/hooks.md#mcp-tool-hook-fields)。
* `"type": "prompt"`：單輪 LLM 評估。請參閱 [Prompt-based hooks](#prompt-based-hooks)。
* `"type": "agent"`：具有工具存取的多輪驗證。Agent hooks 是實驗性的，可能會變更。請參閱 [Agent-based hooks](#agent-based-hooks)。

### 合併來自多個 hooks 的結果

當多個 hooks 相符同一事件時，每個 hook 的命令都會執行到完成，然後 Claude Code 才會合併結果。一個 hook 傳回 `deny` 不會阻止同層 hooks 執行。不要依賴一個 hook 的 `deny` 來抑制另一個 hook 中的副作用。

所有相符的 hooks 完成後，Claude Code 會合併其輸出。對於 `PreToolUse` 權限決定，最嚴格的答案適用，順序為 `deny`、`defer`、`ask`、`allow`。來自 `additionalContext` 的文字會從每個 hook 保留並一起傳遞給 Claude。

下面的範例在 `Bash` 上註冊兩個 `PreToolUse` hooks。第一個將每個命令附加到日誌檔案並以 0 結束。第二個執行一個指令碼，當命令包含 `rm -rf` 時以 2 結束以拒絕：

```json theme={null}
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "jq -r .tool_input.command >> ~/.claude/bash.log"
          },
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/block-rm-rf.sh"
          }
        ]
      }
    ]
  }
}
```

當 Claude 嘗試執行 `rm -rf /tmp/build` 時，兩個 hooks 並行執行。日誌 hook 將命令寫入 `~/.claude/bash.log` 並以 0 結束，這表示沒有決定。護欄 hook 以 2 結束，這拒絕了工具呼叫。拒絕優先，所以 Claude Code 阻止命令並向 Claude 顯示護欄的 stderr。日誌項目仍然被寫入，因為日誌 hook 已經執行。

### 讀取輸入並傳回輸出

Hooks 通過 stdin、stdout、stderr 和結束代碼與 Claude Code 通訊。當事件觸發時，Claude Code 將事件特定資料作為 JSON 傳遞到您的指令碼的 stdin。您的指令碼讀取該資料，執行其工作，並通過結束代碼告訴 Claude Code 接下來要做什麼。

#### Hook 輸入

每個事件都包含常見欄位，如 `session_id`（會話的唯一 ID）和 `cwd`（事件觸發時的工作目錄），但每個事件類型都會新增不同的資料。當 Claude 執行 Bash 命令時，`PreToolUse` hook 在 stdin 上接收這些欄位：

* `hook_event_name`：觸發 hook 的事件
* `tool_name`：Claude 即將使用的工具
* `tool_input`：Claude 傳遞給工具的引數。對於 Bash，其 `command` 欄位保存 shell 命令。

例如，`npm test` 命令的 hook 輸入如下所示：

```json theme={null}
{
  "session_id": "abc123",
  "cwd": "/Users/sarah/myproject",
  "hook_event_name": "PreToolUse",
  "tool_name": "Bash",
  "tool_input": {
    "command": "npm test"
  }
}
```

您的指令碼可以解析該 JSON 並對任何這些欄位採取行動。`UserPromptSubmit` hooks 改為取得 `prompt` 文字，`SessionStart` hooks 取得 `startup`、`resume`、`clear`、`compact` 或 `fork` 的 `source`，以此類推。請參閱參考中的 [常見輸入欄位](https://code.claude.com/docs/zh-TW/hooks.md#common-input-fields) 以了解共享欄位，以及每個事件的部分以了解事件特定的結構描述。

#### Hook 輸出

您的指令碼通過寫入 stdout 或 stderr 並以特定代碼結束來告訴 Claude Code 接下來要做什麼。以下 `PreToolUse` hook 阻止命令：

```bash theme={null}
#!/bin/bash
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command')

if echo "$COMMAND" | grep -q "drop table"; then
  echo "Blocked: dropping tables is not allowed" >&2  # stderr becomes Claude's feedback
  exit 2 # exit 2 = block the action
fi

exit 0  # exit 0 = no decision; the normal permission flow applies
```

若結束代碼不是 0 或 2，且沒有有效的 JSON 輸出，則在大多數事件上動作會繼續進行，除非該 hook 屬於 [其失敗會阻止動作](https://code.claude.com/docs/zh-TW/hooks.md#block-the-action-when-a-hook-fails) 的類型。`onFailure` 設定為 `"block"` 的 hook 就是一個例子。以結束代碼 0 結束表示無異議，或以結束代碼 2 結束以阻止該動作：

* **結束代碼 0**：如果您從 `PreToolUse` hook 以結束代碼 0 結束，工具呼叫仍會經過正常的 [權限流程](https://code.claude.com/docs/zh-TW/permissions.md)，因為結束代碼 0 並不會核准它。對於 `UserPromptSubmit`、`UserPromptExpansion`、`SessionStart` 和 `PostModelSwitch` hooks，Claude Code 會將其 [視為純文字](https://code.claude.com/docs/zh-TW/hooks.md#exit-code-0) 的 stdout 新增到 Claude 的上下文。
* **結束代碼 2**：將原因寫入 stderr。視事件而定，Claude 會將其作為回饋接收以便調整、使用者會看到它，或者不顯示任何訊息（如 `ConfigChange` 和 `Elicitation`）。某些事件無法被阻止：對於 `SessionStart` 和其他事件，結束代碼 2 向使用者顯示 stderr 並繼續執行。請參閱 [每個事件的結束代碼 2 行為](https://code.claude.com/docs/zh-TW/hooks.md#exit-code-2-behavior-per-event) 以取得完整清單。
* **任何其他結束代碼**：關於每個事件的例外情況（例如 `WorktreeCreate` 在任何非零結束代碼上失敗），請參閱 [結束代碼輸出](https://code.claude.com/docs/zh-TW/hooks.md#exit-code-output)。在其他事件上，除非該 hook 屬於其失敗會阻止動作的類型，請依據您的 hook 印出到 stdout 的內容找出您的情況：
  * 通過 schema 驗證的已解析物件：Claude Code 忽略結束代碼，JSON 單獨決定結果，hook 不會報告為錯誤。
  * 未通過 schema 驗證的已解析物件，或 Claude Code [嘗試解析為 JSON](https://code.claude.com/docs/zh-TW/hooks.md#exit-code-0) 但不是有效 JSON 的 stdout：動作以非阻止性錯誤繼續進行。請查看 `<hook name> hook error` 通知中的驗證或解析訊息。
  * Claude Code [視為純文字](https://code.claude.com/docs/zh-TW/hooks.md#exit-code-0) 的 stdout，或空 stdout：動作以非阻止性錯誤繼續進行。逐字稿顯示 `<hook name> hook error` 通知，然後是 stderr 的第一行，前綴為 `Failed with non-blocking status code:`。要擷取完整的 stderr，請使用 `claude --debug` 或在工作階段中執行 `/debug` 來啟用 [偵錯日誌](https://code.claude.com/docs/zh-TW/hooks.md#debug-hooks)。

#### 結構化 JSON 輸出

結束代碼只允許您阻止或保持沉默。為了獲得更多控制，結束代碼 0 並改為列印 JSON 物件到 stdout。

> [!NOTE]
>
> 使用結束代碼 2 以 stderr 訊息阻止，或使用結束代碼 0 和 JSON 進行結構化控制。每個 hook 選擇一種方法。有關混合它們時會發生什麼，請參閱 [結束代碼輸出](https://code.claude.com/docs/zh-TW/hooks.md#exit-code-output)。

例如，`PreToolUse` hook 可以拒絕工具呼叫並告訴 Claude 原因，或將其升級給使用者以供核准：

```json theme={null}
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Use rg instead of grep for better performance"
  }
}
```

使用 `"deny"`，Claude Code 取消工具呼叫並將 `permissionDecisionReason` 回饋給 Claude。

在 `PreToolUse` 上，您也可以傳回 `"ask"` 以向使用者顯示正常的權限提示，或傳回 `"allow"` 以跳過互動式權限提示。使用 `"allow"` 時，拒絕和詢問規則（包括企業管理的拒絕清單）仍然適用，以下情況的提示也同樣適用：

* 從 [網路路徑](https://code.claude.com/docs/zh-TW/permissions.md#network-paths) 讀取
* 標記為 [`requiresUserInteraction`](https://code.claude.com/docs/zh-TW/mcp#require-approval-for-a-specific-tool) 的 MCP 工具
* 呼叫 [Agent SDK 應用程式標記為 `always_ask` 的工具](https://code.claude.com/docs/zh-TW/agent-sdk/custom-tools#require-approval-for-specific-tools)，除非 [權限模式核准該呼叫](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md#permission-modes-that-can-approve-an-always_ask-call)
* 在該設定會傳達到 Claude Code 的工作階段中，[您的組織設定為 `ask`](https://code.claude.com/docs/zh-TW/mcp#organization-controls-on-connector-tools) 的連接器工具

  關於 `"allow"` 在 plan mode 中的作用，請參閱 [plan mode 中的 hook 核准](https://code.claude.com/docs/zh-TW/permissions.md#hook-approvals-in-plan-mode)。

第四個值 `"defer"` 在 [非互動模式](https://code.claude.com/docs/zh-TW/headless.md) 中使用 `-p` 旗標時可用。傳回此值會結束該回合並保留工具呼叫，以便 Agent SDK 包裝器可以收集輸入並繼續。請參閱參考中的 [延遲工具呼叫以供稍後使用](https://code.claude.com/docs/zh-TW/hooks.md#defer-a-tool-call-for-later)。

`PreModelSwitch` hook 傳回相同的 `permissionDecision` 欄位：`"allow"` 允許模型切換進行，`"deny"` 取消它。`"ask"` 在您在互動式會話中執行 `/model` 時要求您確認切換；在其他地方，Claude Code 將 `"ask"` 視為拒絕。請參閱 [PreModelSwitch 決定控制](https://code.claude.com/docs/zh-TW/hooks.md#premodelswitch-decision-control)。

其他事件使用不同的決定模式。例如，`PostToolUse` 和 `Stop` hooks 使用頂層 `decision: "block"` 欄位，而 `PermissionRequest` 使用 `hookSpecificOutput.decision.behavior`。請參閱參考中的 [摘要表](https://code.claude.com/docs/zh-TW/hooks.md#decision-control) 以取得按事件的完整細目。

對於 `UserPromptSubmit` hooks，改為使用 `hookSpecificOutput.additionalContext` 將文字注入 Claude 的上下文。將 `additionalContext` 嵌套在 `hookSpecificOutput` 內；如果您將其放在 JSON 的頂層，Claude Code 會以無聲方式忽略它。例如，此輸出將目前分支狀態新增到每個提示：

```json theme={null}
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "Current branch: release-42. Deploy freeze until Friday."
  }
}
```

請參閱 [UserPromptSubmit 決定控制](https://code.claude.com/docs/zh-TW/hooks.md#userpromptsubmit-decision-control) 以取得完整的輸出形狀，包括阻止提示和設定會話標題。

具有 `type: "prompt"` 的 Hooks 以不同方式處理輸出：請參閱 [Prompt-based hooks](#prompt-based-hooks)。

### 使用匹配器篩選 hooks

沒有匹配器，hook 會在其事件的每次出現時觸發。匹配器可讓您縮小範圍。例如，如果您只想在檔案編輯後執行格式化程式，而不是在每次工具呼叫後，請將匹配器新增到您的 `PostToolUse` hook：

```json theme={null}
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          { "type": "command", "command": "prettier --write ..." }
        ]
      }
    ]
  }
}
```

`"Edit|Write"` 匹配器只在 Claude 使用 `Edit` 或 `Write` 工具時觸發，不在使用 `Bash`、`Read` 或任何其他工具時觸發。逗號以相同方式分隔替代項，所以 `"Edit, Write"` 是等效的。請參閱 [匹配器模式](https://code.claude.com/docs/zh-TW/hooks.md#matcher-patterns) 以了解純名稱和正規表達式的評估方式。

> [!NOTE]
>
> Claude 也可以通過執行 shell 命令來建立或修改檔案。如果您的 hook 必須看到每個檔案變更，例如用於合規性掃描或稽核日誌，請新增一個 [`Stop`](https://code.claude.com/docs/zh-TW/hooks#stop) hook，每輪掃描一次工作樹。對於每次呼叫的覆蓋範圍，也請匹配 `Bash|PowerShell` 並讓您的指令碼使用 `git status --porcelain` 列出修改和未追蹤的檔案。[PowerShell hook 輸入部分](https://code.claude.com/docs/zh-TW/hooks.md#powershell) 說明了為什麼僅匹配 `Bash` 是不夠的。要在特定檔案在磁碟上變更時執行 hook，無論是什麼寫入它，請使用 [FileChanged](https://code.claude.com/docs/zh-TW/hooks.md#filechanged) hook。

每個事件類型都在特定欄位上進行匹配：

| 事件 | 匹配器篩選的內容 | 範例匹配器值 |
| :- | :- | :- |
| `PreToolUse`、`PostToolUse`、`PostToolUseFailure`、`PermissionRequest`、`PermissionDenied` | 工具名稱 | `Bash`、`Edit\|Write`、`mcp__.*` |
| `SessionStart` | 會話如何開始 | `startup`、`resume`、`clear`、`compact`、`fork` |
| `Setup` | 哪個 CLI 旗標觸發設定 | `init`、`maintenance` |
| `SessionEnd` | 會話為什麼結束 | `clear`、`resume`、`logout`、`prompt_input_exit`、`other` |
| `Notification` | 通知類型 | `permission_prompt`、`idle_prompt`、`auth_success`、`elicitation_dialog`、`elicitation_url_dialog`、`elicitation_complete`、`elicitation_response`、`agent_needs_input`、`agent_completed`、`quota_auto_resume_fired`、`quota_auto_resume_stale`、`quota_auto_resume_disabled`、`plugin_notification` |
| `SubagentStart` | 代理類型 | `general-purpose`、`Explore`、`Plan` 或自訂代理名稱 |
| `PreCompact`、`PostCompact` | 什麼觸發了壓縮 | `manual`、`auto` |
| `PreModelSwitch`、`PostModelSwitch` | 會話切換到的模型的規範名稱，如 [PreModelSwitch](https://code.claude.com/docs/zh-TW/hooks.md#premodelswitch) 下所述 | `claude-opus-5`、`claude-opus-4-6\|claude-opus-5`、`.*opus.*` |
| `SubagentStop` | 代理類型 | 與 `SubagentStart` 相同的值 |
| `ConfigChange` | 設定來源 | `user_settings`、`project_settings`、`local_settings`、`policy_settings`、`skills` |
| `DirectoryAdded` | 目錄如何被新增 | `slash_command`、`register_repo_root` |
| `StopFailure` | 錯誤類型 | `rate_limit`、`overloaded`、`authentication_failed`、`oauth_org_not_allowed`、`account_on_hold`、`billing_error`、`invalid_request`、`model_not_found`、`server_error`、`max_output_tokens`、`cloud_credential_error`、`unknown` |
| `InstructionsLoaded` | 載入原因 | `session_start`、`nested_traversal`、`path_glob_match`、`include`、`compact` |
| `Elicitation` | MCP 伺服器名稱 | 您已設定的 MCP 伺服器名稱 |
| `ElicitationResult` | MCP 伺服器名稱 | 與 `Elicitation` 相同的值 |
| `FileChanged` | 要監視的字面檔案名稱（請參閱 [FileChanged](https://code.claude.com/docs/zh-TW/hooks.md#filechanged)） | `.envrc\|.env` |
| `UserPromptExpansion` | 命令名稱 | 您的技能或命令名稱 |
| `UserPromptSubmit`、`PostToolBatch`、`Stop`、`TeammateIdle`、`TaskCreated`、`TaskCompleted`、`WorktreeCreate`、`WorktreeRemove`、`CwdChanged`、`MessageDisplay` | 不支援匹配器 | 始終在每次出現時觸發 |

下面的標籤顯示不同事件類型上的一些其他匹配器。

> [tab] 記錄每個 Bash 命令
>
> 僅匹配 `Bash` 工具呼叫並將每個命令記錄到檔案。`PostToolUse` 事件在命令完成後觸發，所以 `tool_input.command` 包含執行的內容。hook 在 stdin 上接收事件資料作為 JSON，`jq -r '.tool_input.command'` 僅提取命令字串，`>>` 將其附加到日誌檔案：
>
> ```json theme={null}
> {
>   "hooks": {
>     "PostToolUse": [
>       {
>         "matcher": "Bash",
>         "hooks": [
>           {
>             "type": "command",
>             "command": "jq -r '.tool_input.command' >> ~/.claude/command-log.txt"
>           }
>         ]
>       }
>     ]
>   }
> }
> ```

> [tab] 匹配 MCP 工具
>
> MCP 工具使用與內建工具不同的命名慣例：`mcp__<server>__<tool>`，其中 `<server>` 是 MCP 伺服器名稱，`<tool>` 是它提供的工具。例如，`mcp__github__search_repositories` 或 `mcp__filesystem__read_file`。來自 [plugin-bundled 伺服器](https://code.claude.com/docs/zh-TW/mcp.md#plugin-provided-mcp-servers) 的工具改為使用範圍伺服器區段，例如 `mcp__plugin_my-plugin_db__query`。使用正規表達式匹配器來針對來自特定伺服器的所有工具，或使用 `mcp__.*__write.*` 之類的模式跨伺服器進行匹配。請參閱參考中的 [匹配 MCP 工具](https://code.claude.com/docs/zh-TW/hooks.md#match-mcp-tools) 以取得完整的範例清單。
>
> 下面的命令使用 `jq` 從 hook 的 JSON 輸入中提取工具名稱，並將其寫入 stderr。寫入 stderr 可保持 stdout 清潔以用於 JSON 輸出，並將訊息傳送到 [偵錯日誌](https://code.claude.com/docs/zh-TW/hooks.md#debug-hooks)：
>
> ```json theme={null}
> {
>   "hooks": {
>     "PreToolUse": [
>       {
>         "matcher": "mcp__github__.*",
>         "hooks": [
>           {
>             "type": "command",
>             "command": "echo \"GitHub tool called: $(jq -r '.tool_name')\" >&2"
>           }
>         ]
>       }
>     ]
>   }
> }
> ```

> [tab] 在會話結束時清理
>
> `SessionEnd` 事件支援會話結束原因的匹配器。此 hook 只在 `clear` 原因上觸發，在您執行 `/clear` 時設定，而不是在正常結束時：
>
> ```json theme={null}
> {
>   "hooks": {
>     "SessionEnd": [
>       {
>         "matcher": "clear",
>         "hooks": [
>           {
>             "type": "command",
>             "command": "rm -f /tmp/claude-scratch-*.txt"
>           }
>         ]
>       }
>     ]
>   }
> }
> ```

#### 使用 `if` 欄位按工具名稱和引數篩選

`if` 欄位使用 [權限規則語法](https://code.claude.com/docs/zh-TW/permissions.md) 按工具名稱和引數一起篩選 hooks，因此 hook 程序只在工具呼叫相符時生成。這超越了 `matcher`，它只在工具名稱級別按工具名稱篩選。

例如，此設定只在 Claude 使用 `git` 命令而不是所有 Bash 命令時執行 hook：

```json theme={null}
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "if": "Bash(git *)",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/check-git-policy.sh"
          }
        ]
      }
    ]
  }
}
```

您的 hook 命令是否執行取決於您的 `if` 模式的形狀和 Claude 正在呼叫的 Bash 命令：

| `if` 模式 | Bash 命令 | Hook 執行？ | 原因 |
| :- | :- | :- | :- |
| `Bash(git *)` | `git push` | 是 | 命令名稱相符 |
| `Bash(git *)` | `npm test && git push` | 是 | 每個子命令都被檢查；`git push` 相符 |
| `Bash(git *)` | `echo $(git log)` | 是 | `$()` 和反引號內的命令被檢查；`git log` 相符 |
| `Bash(git *)` | `echo $(date)` | 否 | 沒有子命令相符 `git *` |
| `Bash(git push *)` | `echo $(date)` | 是 | 指定超過命令名稱的模式在 `$()`、反引號或 `$VAR` 上執行 hook |

當 Claude Code 無法確定 Bash 輸入執行哪些命令時，無論模式如何，它都會執行您的 hook。[Bash 匹配表](https://code.claude.com/docs/zh-TW/hooks.md#bash-if-matching) 涵蓋 Claude Code 可以和不能按子命令縮小的命令形狀。因為篩選是盡力而為，請使用 [權限系統](https://code.claude.com/docs/zh-TW/permissions.md) 而不是 hook 來強制執行硬允許或拒絕。

`if` 欄位接受與權限規則相同的模式：`"Bash(git *)"`、`"Edit(*.ts)"` 等。要匹配多個工具名稱，請使用各自具有自己 `if` 值的單獨處理程式，或在支援管道替代的 `matcher` 級別進行匹配。

`if` 只適用於工具事件：`PreToolUse`、`PostToolUse`、`PostToolUseFailure`、`PermissionRequest` 和 `PermissionDenied`。將其新增到任何其他事件會防止 hook 執行。

### 設定 hook 位置

您新增 hook 的位置決定其範圍：

| 位置 | 範圍 | 可共享 |
| :- | :- | :- |
| `~/.claude/settings.json` | 您的所有專案 | 否，本機到您的機器 |
| `.claude/settings.json` | 單一專案 | 是，可以提交到儲存庫 |
| `.claude/settings.local.json` | 單一專案 | 否，當 Claude Code 將設定儲存到它時被 gitignored |
| 受管理的原則設定 | 組織範圍 | 是，由管理員控制 |
| [Plugin](https://code.claude.com/docs/zh-TW/plugins/overview.md) `hooks/hooks.json` | 啟用 plugin 時 | 是，與 plugin 一起打包 |
| [Skill](https://code.claude.com/docs/zh-TW/skills.md) frontmatter | 叫用技能後的會話其餘部分。請參閱 [Hooks in skills and agents](https://code.claude.com/docs/zh-TW/hooks.md#hooks-in-skills-and-agents) | 是，在技能檔案中定義 |
| [Subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) frontmatter | 該 subagent 執行時 | 是，在 subagent 檔案中定義 |

在 Claude Code 中執行 [`/hooks`](https://code.claude.com/docs/zh-TW/hooks#the-%2Fhooks-menu) 以瀏覽按事件分組的所有已設定 hooks。

要停用 hooks，請在您的設定檔案中設定 `"disableAllHooks": true`。Claude Code 讀取 [設定優先順序](https://code.claude.com/docs/zh-TW/hooks.md#disable-or-remove-hooks) 適用後剩下的值，因此專案的設定檔案可以覆蓋您的。在受管理的設定中設定的 Hooks 仍然執行，除非 `disableAllHooks` 也在那裡設定。對於每個級別的完整範圍，請參閱 [`disableAllHooks`](https://code.claude.com/docs/zh-TW/settings-reference#disableallhooks)。

如果您在 Claude Code 執行時直接編輯設定檔案，檔案監視程式通常會自動選取 hook 變更。

## 基於提示的 hooks

對於需要判斷而不是確定性規則的決策，使用 `type: "prompt"` hooks。Claude Code 不執行 shell 命令，而是將您的提示和 hook 的輸入資料傳送到 Claude 模型以做出決策。如果您需要更多功能，可以使用 `model` 欄位指定不同的模型。

模型的唯一工作是傳回其決策作為 JSON：

* `"ok": true`：操作繼續
* `"ok": false`：發生的情況取決於事件：
  * `Stop` 和 `SubagentStop`：`reason` 被回饋給 Claude，以便它繼續工作，除非回應也設定 `"impossible": true` 以標記該條件為永遠無法滿足的條件，在這種情況下 Claude Code 允許停止並結束回合
  * `PreToolUse`：工具呼叫被拒絕；預設情況下回合結束，拒絕 `reason` 在聊天中顯示為警告行。在 hook 上設定 `continueOnBlock: true` 以改為將 `reason` 傳回給 Claude 作為工具錯誤，以便它可以調整並繼續
  * `PostToolUse`：預設情況下回合結束，`reason` 在聊天中顯示為警告行。設定 `continueOnBlock: true` 以將 `reason` 回饋給 Claude 並改為繼續回合
  * `PostToolBatch`、`UserPromptSubmit` 和 `UserPromptExpansion`：回合結束，`reason` 在聊天中顯示為警告行

此範例使用 `Stop` hook 詢問模型是否所有請求的任務都已完成。如果模型傳回 `"ok": false` 因為條件尚未滿足，Claude 會繼續工作並使用 `reason` 作為其下一個指令：

```json theme={null}
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "prompt",
            "prompt": "Check if all tasks are complete. If not, respond with {\"ok\": false, \"reason\": \"what remains to be done\"}."
          }
        ]
      }
    ]
  }
}
```

有關完整的配置選項，請參閱參考中的[基於提示的 hooks](https://code.claude.com/docs/zh-TW/hooks.md#prompt-based-hooks)。

## 基於代理的 hooks

> [!WARNING]
>
> Agent hooks 是實驗性的。行為和配置可能在未來版本中改變。對於生產工作流程，優先使用[命令 hooks](https://code.claude.com/docs/zh-TW/hooks.md#command-hook-fields)。

當驗證需要檢查檔案或執行命令時，使用 `type: "agent"` hooks。與只進行單個 LLM 呼叫的提示 hooks 不同，代理 hooks 生成一個 subagent，可以讀取檔案、搜尋程式碼和使用其他工具在傳回決策之前驗證條件。

代理 hooks 使用 `"ok"` / `"reason"` 回應格式，預設超時時間更長（60 秒），最多 50 個工具使用輪次。它們不支援提示 hook 的 `impossible` 欄位。當 `ok: false` 時，Claude Code 處理代理 hook 的方式與處理在同一事件上設定 `continueOnBlock: true` 的提示 hook 相同，因此在 `PreToolUse` 和 `PostToolUse` 上輪次會繼續；代理 hooks 沒有 `continueOnBlock` 欄位。請參閱[代理 hook 配置](https://code.claude.com/docs/zh-TW/hooks.md#agent-hook-configuration)以了解欄位，包括 Claude Code 用 hook 的 JSON 輸入替換的 `$ARGUMENTS` 預留位置。

此範例驗證在允許 Claude 停止之前測試通過：

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

當 hook 輸入資料本身足以做出決策時，使用提示 hooks。當您需要根據程式碼庫的實際狀態驗證某些內容時，使用代理 hooks。

有關完整的配置選項，請參閱參考中的[基於代理的 hooks](https://code.claude.com/docs/zh-TW/hooks.md#agent-based-hooks)。

## HTTP hooks

使用 `type: "http"` hooks 將事件資料 POST 到 HTTP 端點，而不是執行 shell 命令。端點接收命令 hook 在 stdin 上接收的相同 JSON，並使用相同的 JSON 格式透過 HTTP 回應主體傳回結果。

HTTP hooks 在您希望 Web 伺服器、雲端函數或外部服務處理 hook 邏輯時很有用：例如，一個共享的審計服務，在整個團隊中記錄工具使用事件。

此範例將每個工具使用 POST 到本機記錄服務：

```json theme={null}
{
  "hooks": {
    "PostToolUse": [
      {
        "hooks": [
          {
            "type": "http",
            "url": "http://localhost:8080/hooks/tool-use",
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

您的端點會以與命令 hooks 相同的[輸出格式](https://code.claude.com/docs/zh-TW/hooks.md#json-output)傳回 JSON 回應主體，而 Claude Code 也會檢查回應狀態：

* **2xx 狀態**：若要阻止工具呼叫，請在主體中傳回適當的 `hookSpecificOutput` 欄位。
* **任何其他狀態，或請求失敗**：Claude Code 會回報[非阻斷性錯誤](https://code.claude.com/docs/zh-TW/hooks.md#exit-code-output)並讓該動作繼續進行。若要讓失敗的端點阻止該動作，請在 hook 上設定 [`onFailure: "block"`](https://code.claude.com/docs/zh-TW/hooks#block-the-action-when-a-hook-fails)。

標頭值支援使用 `$VAR_NAME` 或 `${VAR_NAME}` 語法的環境變數插值。只有在 `allowedEnvVars` 陣列中列出的變數才會被解析；所有其他 `$VAR` 參考保持為空。

有關完整的配置選項和回應處理，請參閱參考中的 [HTTP hooks](https://code.claude.com/docs/zh-TW/hooks.md#http-hook-fields)。

## 限制和故障排除

### 限制

設計 hooks 時請記住這些限制：

* 命令 hooks 只透過 stdout、stderr 和退出代碼通訊。它們無法觸發 `/` 命令或工具呼叫。透過 `additionalContext` 傳回的文字會作為[系統提醒](https://code.claude.com/docs/zh-TW/glossary.md#system-reminder)注入，Claude 將其讀取為純文字。HTTP hooks 改為透過回應主體通訊。
* Hook 超時因類型而異。透過 `timeout` 欄位（以秒為單位）按 hook 覆寫。
  * `command`、`http`、`mcp_tool`：10 分鐘。Claude Code 將 `UserPromptSubmit`、`PreModelSwitch` 和 `PostModelSwitch` hooks 的預設值降低至 30 秒，將 `MessageDisplay` 的預設值降低至 10 秒。
  * `prompt`：30 秒。
  * `agent`：60 秒。
  * [`SessionEnd`](https://code.claude.com/docs/zh-TW/hooks#sessionend) hooks 的任何類型共享 1.5 秒的預算。如果您的設定為 hook 設定了更長的 `timeout`，Claude Code 會將預算提高以匹配，最多 60 秒。
* `PostToolUse` hooks 無法撤銷操作，因為工具已經執行。
* [`PermissionRequest`](https://code.claude.com/docs/zh-TW/hooks#permissionrequest) hook 在 Claude Code 即將要求您授予權限時觸發，或在它原本會自動拒絕無法顯示提示的呼叫時觸發。在使用 `-p` 旗標的[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)中，它們在 [`dontAsk` 模式](https://code.claude.com/docs/zh-TW/permission-modes#allow-only-pre-approved-tools-with-dontask-mode)以外仍會執行，而沒有任何 hook 做出決策、也沒有其他機制能回應的呼叫會被拒絕。
* `Stop` hooks 在 Claude 完成回應時觸發，而不僅在任務完成時。它們在使用者中斷時不觸發。API 錯誤觸發 [StopFailure](https://code.claude.com/docs/zh-TW/hooks.md#stopfailure) 代替。
* 當多個 `PreToolUse` hook 傳回 [`updatedInput`](https://code.claude.com/docs/zh-TW/hooks#pretooluse) 以重寫工具的輸入時，Claude Code 不會合併這些重寫，也不保證工具會以哪一個重寫執行。避免有多個 hook 重寫同一工具的輸入。

### Hooks 和權限模式

透過設定檔或外掛 `hooks/hooks.json` 中的 hook，您無法將限制放寬到超過權限規則允許的範圍，而 hook 的 `"deny"` 在每個權限模式中都有效：

* **仍優先於 `"allow"` 的項目**：傳回 `"allow"` 的 hook 不會繞過來自設定的拒絕規則，也無法抑制以下情況的提示：
  * 從[網路路徑](https://code.claude.com/docs/zh-TW/permissions.md#network-paths)讀取
  * 標記為 [`requiresUserInteraction`](https://code.claude.com/docs/zh-TW/mcp#require-approval-for-a-specific-tool) 的 MCP 工具
  * 對 [Agent SDK 應用程式標記為 `always_ask` 之工具](https://code.claude.com/docs/zh-TW/agent-sdk/custom-tools#require-approval-for-specific-tools)的呼叫，除非[權限模式核准該呼叫](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md#permission-modes-that-can-approve-an-always_ask-call)
  * 在該設定會傳達到 Claude Code 的工作階段中，[您的組織設定為 `ask`](https://code.claude.com/docs/zh-TW/mcp#organization-controls-on-connector-tools) 的連接器工具

在 [plan mode](https://code.claude.com/docs/zh-TW/permissions.md#hook-approvals-in-plan-mode) 中，如果您的 `PreToolUse` hook 對檔案編輯傳回 `"allow"`，您會得到與沒有 hook 時該編輯相同的提示、阻止或核准。若要解除 hook 核准的這項限制，請[核准計畫](https://code.claude.com/docs/zh-TW/permission-modes.md#review-and-approve-a-plan)或切換到其他權限模式。

* **`"deny"` 在每個權限模式中都有效**：傳回 `permissionDecision: "deny"` 的 hook 會阻止工具，即使在 `bypassPermissions` 模式或使用 `--dangerously-skip-permissions` 時也是如此。`PreToolUse` hook 在任何權限模式檢查之前觸發，在每個[權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md)中皆然，包括 `dontAsk`。這讓您能強制執行使用者無法透過變更其權限模式來繞過的原則。

> [!NOTE]
>
> 如果您的機器沒有[受管設定](https://code.claude.com/docs/zh-TW/settings.md#check-what-your-organization-enforces)，且您的工作階段未使用 Team 或 Enterprise 方案的 [`/login` 憑證](https://code.claude.com/docs/zh-TW/authentication#authentication-precedence)，[mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md) 可以核准您的 `PreToolUse` hook 已阻止的呼叫。改以 API 金鑰或長期有效的 [`CLAUDE_CODE_OAUTH_TOKEN`](https://code.claude.com/docs/zh-TW/authentication#generate-a-long-lived-token) 執行的工作階段並未使用該登入，即使該登入已儲存也是如此。
>
> 在 plan mode 中，mod 只有在此類被阻止的呼叫為唯讀時才能核准它，因此不包括檔案編輯。關於 mod 的核准無法越過您的規則和 hook 的情況，請參閱[使用 hook 擴充權限](https://code.claude.com/docs/zh-TW/permissions.md#precedence-among-rules-hooks-and-mods)。

### Hook 未觸發

Hook 已配置但從不執行。

* 執行 `/hooks` 並確認 hook 出現在正確的事件下
* 對於 skill frontmatter 中的 hook，請叫用該 skill 或請 Claude 叫用，然後再次執行 `/hooks`。`/hooks` 不會列出工作階段中尚未叫用之 skill 的 hook。如果 `/hooks` 仍未列出該 hook，請檢查其他原因，例如[未能解析的 frontmatter](https://code.claude.com/docs/zh-TW/skills.md#skill-not-triggering) 或其中一項 [skill hook 的限制](https://code.claude.com/docs/zh-TW/hooks.md#limits-on-skill-hooks)
* 檢查匹配器模式是否與工具名稱完全相符。匹配器區分大小寫
* 驗證您觸發的是正確的事件類型：`PreToolUse` 在工具執行前觸發，`PostToolUse` 在之後觸發。`PermissionRequest` hook 在 Claude Code 即將要求您的權限時觸發；請參閱[限制](#limitations)以了解非互動模式的情況

### Hook 輸出中的錯誤

您在文字記錄中看到類似「PreToolUse hook error: ...」的訊息。

* 您的指令意外以非零代碼退出。透過管道傳輸範例 JSON 來手動測試它：
  ```bash theme={null}
  echo '{"tool_name":"Bash","tool_input":{"command":"ls"}}' | ./my-hook.sh
  echo $?  # Check the exit code
  ```
* 如果您看到「command not found」，使用絕對路徑或 `${CLAUDE_PROJECT_DIR}` 來參考指令。為了完全避免 shell 引用，添加 `"args": []` 以切換到 [exec 形式](https://code.claude.com/docs/zh-TW/hooks.md#exec-form-and-shell-form)，它直接生成指令而不使用 shell
* 如果您看到「jq: command not found」，安裝 `jq` 或使用 Python/Node.js 進行 JSON 解析
* 如果訊息包含 `blocking because Git Bash wasn't found`，表示您在 Windows 上、Claude Code 找不到 Git Bash，且失敗或逾時的 hook 阻止了工具呼叫。請參閱[在沒有 Git Bash 的 Windows 上失敗的 hook](https://code.claude.com/docs/zh-TW/hooks.md#failed-hooks-on-windows-without-git-bash) 以了解修正方法
* 如果通知顯示 JSON 驗證訊息，您的 hook 的 stdout 解析為 JSON 但未通過架構驗證。如果顯示 JSON 解析訊息，stdout 看起來像 JSON 物件但不是有效的 JSON。即使在退出 0 時也會發生這兩種情況。

  要修復解析失敗，使用 JSON 編碼器（例如 `jq`）而不是字串連接來建立有效負載，以便值內的引號和反斜線被轉義。參考的[退出代碼輸出](https://code.claude.com/docs/zh-TW/hooks.md#exit-code-output)部分涵蓋了退出代碼和 JSON 組合
* 如果指令根本沒有執行，使其可執行：`chmod +x ./my-hook.sh`

### `/hooks` 顯示未配置任何 hooks

您編輯了設定檔但 hooks 未出現在選單中。

* 檔案編輯通常會自動選取。如果在幾秒鐘後仍未出現，檔案監視程式可能已錯過變更：重新啟動您的工作階段以強制重新載入。
* 驗證您的 JSON 有效：不允許尾隨逗號和註解
* 確認設定檔在正確的位置：`.claude/settings.json` 用於專案 hooks，`~/.claude/settings.json` 用於全域 hooks
* 如果選單顯示 `Only hooks from managed settings run here`，表示您的組織已設定 [`allowManagedHooksOnly`](https://code.claude.com/docs/zh-TW/settings-reference#allowmanagedhooksonly)。您的使用者、專案和本機設定檔中的 hook 不會執行，也不會列出

### Stop hook 觸發區塊上限

Claude 繼續工作而不是停止，然後以警告結束回合，表示 Stop hook 連續阻止了太多次。

當 Stop hook 連續阻止八次、且期間 Claude 沒有任何工具呼叫時，Claude Code 會覆寫它。您的 hook 指令碼需要檢查它是否已經觸發了延續。從 JSON 輸入解析 `stop_hook_active` 欄位，如果為 `true` 則提前退出：

```bash theme={null}
#!/bin/bash
INPUT=$(cat)
if [ "$(echo "$INPUT" | jq -r '.stop_hook_active')" = "true" ]; then
  exit 0  # Allow Claude to stop
fi
# ... rest of your hook logic
```

如果您的 hook 合理地需要超過八次迭代才能收斂，使用 [`CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`](https://code.claude.com/docs/zh-TW/env-vars) 提高上限。

### Hook JSON 沒有效果

您的 hook 列印有效的 JSON，但決策沒有生效，文字記錄中也沒有出現錯誤。檢查哪個原因適用：

* **JSON 前的額外輸出**：其他東西首先寫入 stdout，通常是您 shell 設定檔中的無條件 `echo`，所以輸出不再以 `{` 開頭。請參閱[JSON 前的 shell 設定檔輸出](#shell-profile-output-before-the-json)。
* **欄位位置錯誤**：將每個欄位的位置與 [JSON 輸出](https://code.claude.com/docs/zh-TW/hooks.md#json-output)格式進行比較。例如，`permissionDecision` 應該在 `hookSpecificOutput` 內，而不是在頂層。請參閱[位於錯誤層級的欄位](#fields-at-the-wrong-level)。

#### JSON 前的 shell 設定檔輸出

Hook 在非互動式 shell 中執行，但 Git Bash 和某些設定（例如 `BASH_ENV` 指向 `~/.bashrc`）仍然會載入您的設定檔，而設定檔列印的任何內容都會在您 hook 的 JSON 之前到達 stdout：

```text theme={null}
Shell ready on arm64
{"decision": "block", "reason": "Not allowed"}
```

除非該 hook 是[非同步](https://code.claude.com/docs/zh-TW/hooks.md#how-async-hooks-execute)的，否則 Claude Code 會將不以 `{` 開頭的輸出讀取為純文字，因此您的 JSON 會被忽略。由於 hook 以 0 退出，逐字稿中也不會顯示任何錯誤。要檢查是否為此原因，請使用 `claude --debug` 啟動 Claude Code，觸發 hook，然後在[除錯日誌](https://code.claude.com/docs/zh-TW/hooks.md#debug-hooks)中搜尋 `Hook output does not start with {`。要修復此問題，請在您的設定檔中包裝 `echo` 陳述式，使其只在互動式 shell 中執行：

```bash theme={null}
# 在 ~/.zshrc 或 ~/.bashrc 中
if [[ $- == *i* ]]; then
  echo "Shell ready"
fi
```

`$-` 變數包含 shell 旗標，`i` 表示互動式。Hooks 在非互動式 shell 中執行，因此 echo 被跳過。

#### 位於錯誤層級的欄位

當您的 hook 在頂層而不是在 `hookSpecificOutput` 內傳回 `permissionDecision` 或 `additionalContext` 時，JSON 仍然會解析，Claude Code 會忽略放置錯誤的欄位而不報告錯誤。要查看它忽略了哪些欄位，使用 `claude --debug` 啟動 Claude Code 並在[除錯日誌](https://code.claude.com/docs/zh-TW/hooks.md#debug-hooks)中搜尋 `Hook JSON output had unrecognized keys`。

### 檢查 hook 做了什麼

按 `Ctrl+O` 開啟逐字稿檢視，並尋找 hook 的結果：

* **成功**：您看不到任何內容，除非 hook 的 JSON 顯示某些內容，例如 `systemMessage` 或 Stop hook 回饋。
  * 要確認 hook 已執行，請檢查其效果，例如重新格式化的檔案
* **阻止錯誤**：在大多數事件上，您會看到隨阻止一起傳回的訊息，例如 `Blocked: rm commands are not allowed`。在少數事件上，例如 `ConfigChange` 和 `Elicitation`，您不會看到任何訊息。[退出碼 2](https://code.claude.com/docs/zh-TW/hooks.md#exit-code-2) 說明訊息的來源。
* **非阻止錯誤**：您會看到 `<hook name> hook error` 通知，其中包含簡短說明，例如 `Failed with non-blocking status code:` 之後的 stderr 第一行，或 JSON 驗證或解析訊息。操作仍會繼續進行。

若要查詢特定退出碼和 stdout 所對應的結果，包括每個事件的例外，請參閱參考文件中的[退出碼輸出](https://code.claude.com/docs/zh-TW/hooks.md#exit-code-output)。

如需完整的執行詳細資訊，包括 hook 退出碼、stdout 和 stderr，請閱讀[除錯日誌](https://code.claude.com/docs/zh-TW/hooks.md#debug-hooks)。使用 `claude --debug-file /tmp/claude.log` 啟動 Claude Code 以寫入已知路徑，然後在另一個終端機中執行 `tail -f /tmp/claude.log`。如果您啟動時沒有該旗標，請在工作階段中執行 `/debug` 以啟用日誌並找到日誌路徑。

## 深入瞭解

* [Hooks 參考](https://code.claude.com/docs/zh-TW/hooks.md)：完整的事件架構、JSON 輸出格式、非同步 hooks 和 MCP 工具 hooks
* [安全考量](https://code.claude.com/docs/zh-TW/hooks.md#security-considerations)：在共享或生產環境中部署 hooks 之前進行檢查
* [Bash 命令驗證器範例](https://github.com/anthropics/claude-code/blob/main/examples/hooks/bash_command_validator_example.py)：完整的參考實現

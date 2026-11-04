<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/keybindings | lastmod: 2026-10-24 | section: Configuration / Interface -->
> 來源：https://code.claude.com/docs/zh-TW/keybindings（官方 zh-TW，lastmod 2026-10-24）｜分類：Configuration › Interface｜EN 摘要：Customize keyboard shortcuts in Claude Code with a keybindings configuration file.

# 自訂鍵盤快捷鍵

> 使用快捷鍵配置檔案在 Claude Code 中自訂鍵盤快捷鍵。

Claude Code 支援可自訂的鍵盤快捷鍵。執行 `/keybindings` 以在 `~/.claude/keybindings.json` 建立或開啟您的配置檔案。

## 配置檔案

快捷鍵配置檔案是一個包含 `bindings` 陣列的物件。每個區塊指定一個上下文和一個按鍵組合到動作的對應。

> [!NOTE]
>
> 快捷鍵檔案的變更會自動偵測並套用，無需重新啟動 Claude Code。

| 欄位 | 說明 |
| :- | :- |
| `$schema` | 選用的 JSON Schema URL，用於編輯器自動完成 |
| `$docs` | 選用的文件 URL |
| `bindings` | 按上下文分組的繫結區塊陣列 |

此範例在聊天上下文中將 `Ctrl+E` 繫結到開啟外部編輯器，並取消繫結 `Ctrl+S`：

```json theme={null}
{
  "$schema": "https://www.schemastore.org/claude-code-keybindings.json",
  "$docs": "https://code.claude.com/docs/zh-TW/keybindings",
  "bindings": [
    {
      "context": "Chat",
      "bindings": {
        "ctrl+e": "chat:externalEditor",
        "ctrl+s": null
      }
    }
  ]
}
```

## 上下文

每個繫結區塊都指定一個**上下文**，其中繫結適用：

| 上下文 | 描述 |
| :- | :- |
| `Global` | 在應用程式的任何地方適用 |
| `Chat` | 主聊天輸入區域 |
| `Autocomplete` | 自動完成選單已開啟 |
| `Settings` | 設定選單 |
| `Confirmation` | 權限和確認對話框 |
| `Tabs` | 標籤導覽元件 |
| `Help` | 說明選單可見 |
| `Transcript` | 文字記錄檢視器 |
| `HistorySearch` | 歷史記錄搜尋模式 (Ctrl+R) |
| `Task` | 工作在前景執行中 |
| `ThemePicker` | 佈景主題選擇器對話框 |
| `Attachments` | 選取對話框中的影像附件導覽 |
| `Footer` | 頁尾指示器導覽 (工作、團隊、差異、成品) |
| `MessageSelector` | 倒帶和摘要對話框訊息選取 |
| `DiffDialog` | [差異檢視器](#diff-actions)導覽 |
| `DiffPanel` | [差異面板](https://code.claude.com/docs/zh-TW/interactive-mode.md#diff-panel)已開啟 |
| `ModelPicker` | 模型選擇器努力程度 |
| `EffortSlider` | 由 `/effort` 開啟的努力滑桿 |
| `Select` | 通用選取/清單元件 |
| `Plugin` | Plugin 對話框 (瀏覽、探索、管理) |
| `AbovePrompt` | [提示詞上方的區域](#above-prompt-actions)或其中的按鈕擁有鍵盤焦點 |
| `AbovePromptInput` | 提示詞上方區域或 mod 窗格中的輸入欄位擁有鍵盤焦點 |
| `AbovePromptSelect` | 提示詞上方區域或 mod 窗格中的選取元件擁有鍵盤焦點 |
| `Pane` | 由 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md#know-which-keys-your-mod-can-receive) 繪製的窗格擁有鍵盤焦點 |
| `PaneField` | mod 窗格中的輸入欄位或選取元件擁有鍵盤焦點 |
| `Agents` | [Agent 檢視](https://code.claude.com/docs/zh-TW/agent-view.md) (`claude agents`) |
| `Scroll` | 對話捲動和全螢幕模式中的文字選取 |

在 v2.1.205 之前，`/doctor` 診斷畫面存在 `Doctor` 上下文和 `doctor:fix` 動作。

## 可用動作

動作採用 `namespace:action` 格式，例如 `chat:submit` 用於傳送訊息，`app:toggleTodos` 用於顯示任務清單。每個情境都有其特定的可用動作。

### 應用程式動作

在 `Global` 情境中可用的動作：

| 動作 | 預設 | 說明 |
| :- | :- | :- |
| `app:interrupt` | Ctrl+C | 取消目前的操作 |
| `app:exit` | Ctrl+D | 結束 Claude Code。在 800ms 內按兩次以確認 |
| `app:redraw` | （未繫結） | 強制重繪終端機 |
| `app:toggleTodos` | Ctrl+T | 切換 Claude 待辦檢查清單的顯示。這不是 [`/tasks`](https://code.claude.com/docs/zh-TW/commands) 背景任務檢視 |
| `app:toggleTranscript` | Ctrl+O | 切換詳細逐字稿 |

### 歷史記錄動作

用於瀏覽命令歷史記錄的動作：

| 動作 | 預設 | 說明 |
| :- | :- | :- |
| `history:search` | Ctrl+R | 開啟歷史記錄搜尋 |
| `history:previous` | Up | 上一個歷史記錄項目 |
| `history:next` | Down | 下一個歷史記錄項目 |

### 聊天動作

在 `Chat` 情境中可用的動作：

| 動作 | 預設 | 說明 |
| :- | :- | :- |
| `chat:cancel` | Escape | 取消目前的輸入 |
| `chat:clearInput` | Ctrl+L | 強制完整重繪畫面，保留輸入與對話 |
| `chat:clearScreen` | Cmd+K | 與 `chat:clearInput` 相同。關於 Cmd+K 在 iTerm2 和 Terminal.app 上的行為，請參閱[清除對話](https://code.claude.com/docs/zh-TW/fullscreen.md#clear-the-conversation) |
| `chat:killAgents` | Ctrl+X Ctrl+K | 停止此工作階段中所有正在執行的[背景 subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#run-subagents-in-foreground-or-background)，並在此工作階段的剩餘時間內關閉 [artifact 自動回覆](https://code.claude.com/docs/zh-TW/artifacts.md#let-claude-reply-to-comments-on-its-own)。在 3 秒內按兩次快捷鍵以確認。即使背景 subagent 的權限提示正在開啟，也可以按下此快捷鍵 |
| `chat:cycleMode` | Shift+Tab\* | 循環切換權限模式 |
| `chat:modelPicker` | Meta+P | 開啟模型選擇器 |
| `chat:fastMode` | Meta+O | 切換快速模式 |
| `chat:thinkingToggle` | Meta+T | 切換延伸思考 |
| `chat:submit` | Enter | 送出訊息 |
| `chat:queueSubmit` | Ctrl+X Enter | 送出訊息並標記為等待輪到它：當 Claude 正在工作時，Claude Code 會[將其排入佇列](https://code.claude.com/docs/zh-TW/interactive-mode.md#queue-messages-while-claude-works)，且絕不中斷目前的回合。與 `chat:submit` 不同，即使自動完成建議正處於醒目提示狀態，它也會送出草稿。需要 v2.1.247 或更新版本 |
| `chat:sendNow` | Ctrl+Enter, Ctrl+X Ctrl+S | 立即傳送您[排入佇列的訊息](https://code.claude.com/docs/zh-TW/interactive-mode.md#queue-messages-while-claude-works)，連同您的草稿一起傳送。[Claude Code 何時傳送您排入佇列的內容](https://code.claude.com/docs/zh-TW/interactive-mode.md#when-claude-code-sends-what-you-queued)說明了 Claude 正在處理的回合會如何處理。當沒有任何項目在執行時，此按鍵會送出草稿，而在 [shell 模式](https://code.claude.com/docs/zh-TW/interactive-mode.md#shell-mode-with-prefix)中則只會將命令排入佇列。不回報延伸按鍵的終端機會將 `Ctrl+Enter` 當作一般的 `Enter` 傳送，因此 `Ctrl+X Ctrl+S` 是在任何終端機中都能運作的繫結。需要 v2.1.275 或更新版本 |
| `chat:newline` | Ctrl+J | 插入換行而不送出 |
| `chat:undo` | Ctrl+\_, Ctrl+Shift+- | 復原上一個動作 |
| `chat:externalEditor` | Ctrl+G, Ctrl+X Ctrl+E | 在外部編輯器中開啟。[agent 檢視的 dispatch 輸入](https://code.claude.com/docs/zh-TW/agent-view.md#keyboard-shortcuts)也會遵循此動作的單一按鍵繫結 |
| `chat:stash` | Ctrl+S | 暫存目前的提示詞 |
| `chat:imagePaste` | Ctrl+V（在 Windows 和 WSL 上為 Alt+V） | 從剪貼簿貼上圖片。在 WSL 上，兩個快捷鍵預設都已繫結 |
| `command:<name>` | （未繫結） | 執行[命令](https://code.claude.com/docs/zh-TW/commands.md) `/<name>`。例如，在 `Chat` 區塊中設定 `"meta+g": "command:compact"` 會讓 `Meta+G` 執行 `/compact` |

\*在未啟用 VT 模式的 Windows 上（Node \<24.2.0/\<22.17.0、Bun \<1.2.23），預設為 Meta+M。

### 自動完成動作

在 `Autocomplete` 情境中可用的動作：

| 動作 | 預設 | 說明 |
| :- | :- | :- |
| `autocomplete:accept` | Tab | 接受建議 |
| `autocomplete:dismiss` | Escape | 關閉選單 |
| `autocomplete:previous` | Up | 上一個建議 |
| `autocomplete:next` | Down | 下一個建議 |

### 確認動作

在 `Confirmation` 情境中可用的動作：

| 動作 | 預設 | 說明 |
| :- | :- | :- |
| `confirm:yes` | Enter | 確認動作 |
| `confirm:no` | Escape | 拒絕動作 |
| `confirm:previous` | Up | 上一個選項 |
| `confirm:next` | Down | 下一個選項 |
| `confirm:nextField` | Tab | 在 `/fast` 對話框中，開啟或關閉快速模式 |
| `confirm:previousField` | （未繫結） | Claude Code 不會回應此動作，而指定此動作的 `keybindings.json` 仍然有效 |
| `confirm:toggle` | Space | 切換選取 |
| `confirm:cycleMode` | Shift+Tab\* | 在檔案權限提示上，關閉已開啟的[註解欄位](https://code.claude.com/docs/zh-TW/permissions.md#add-a-comment-when-you-answer-a-permission-prompt)；若沒有開啟的欄位，且提示提供該選項時，則選取允許此動作在工作階段剩餘時間內執行的選項 |

\*在未啟用 VT 模式的 Windows 上（Node \<24.2.0/\<22.17.0、Bun \<1.2.23），預設為 Meta+M。

在 v2.1.257 之前，有一個預設繫結至 `Ctrl+E` 的 `confirm:toggleExplanation` 動作，會在 Bash 和 PowerShell 權限提示上顯示由模型產生的命令說明。

對話框使用 `confirm:yes` 和 `confirm:no` 來接受與取消，即使對話框並未提出是非問題也是如此。如果您在此情境中繫結單一字母（例如 `y` 或 `n`），該字母也會作用於從未將其顯示為按鍵的對話框。將 `y` 和 `n` 顯示為按鍵的對話框會自行讀取這些字母，不需要繫結。

在大多數對話框中，按兩次 `Ctrl+C` 或 `Ctrl+D` 會關閉對話框，而不是結束 Claude Code。第一次按下後的提示會說明第二次按下是關閉對話框還是結束。這兩個按鍵都是[保留的](#reserved-shortcuts)，無法重新繫結。

此範例將 `y` 繫結至 `confirm:yes`，將 `n` 繫結至 `confirm:no`：

```json theme={null}
{
  "bindings": [
    {
      "context": "Confirmation",
      "bindings": {
        "y": "confirm:yes",
        "n": "confirm:no"
      }
    }
  ]
}
```

使用這些繫結時，當[文字欄位](#text-fields)取得焦點時，`y` 和 `n` 仍會以字母形式輸入。

在 v2.1.280 之前，`y` 預設也繫結至 `confirm:yes`，`n` 則繫結至 `confirm:no`。如果您在 v2.1.280 之前使用 `/keybindings` 建立了 `keybindings.json`，該檔案會列出這兩個繫結，且在您刪除這兩行之前它們會持續生效。

### 權限動作

在 `Confirmation` 情境中可用於權限對話框的動作：

| 動作 | 預設 | 說明 |
| :- | :- | :- |
| `permission:toggleDebug` | （未繫結） | Claude Code 不會回應此動作，而指定此動作的 `keybindings.json` 仍然有效 |

### 逐字稿動作

在 `Transcript` 情境中可用的動作：

| 動作 | 預設 | 說明 |
| :- | :- | :- |
| `transcript:toggleShowAll` | Ctrl+E | 切換顯示所有內容 |
| `transcript:exit` | q, Ctrl+C, Escape | 結束逐字稿檢視 |

`transcript:toggleShowAll` 僅適用於傳統渲染器；在[全螢幕渲染](https://code.claude.com/docs/zh-TW/fullscreen.md)中，逐字稿檢視器不提供顯示全部的切換功能。

### 歷史記錄搜尋動作

在 `HistorySearch` 情境中可用的動作：

| 動作 | 預設 | 說明 |
| :- | :- | :- |
| `historySearch:next` | Ctrl+R | 下一個符合項目 |
| `historySearch:accept` | Escape, Tab | 接受選取 |
| `historySearch:cancel` | Ctrl+C | 取消搜尋 |
| `historySearch:execute` | Enter | 執行選取的命令 |
| `historySearch:cycleScope` | Ctrl+S | 循環切換範圍：工作階段、專案、所有位置 |

`historySearch:next`、`historySearch:accept`、`historySearch:cancel` 和 `historySearch:execute` 的預設值適用於傳統渲染器中的行內歷史記錄搜尋，該搜尋一律會搜尋所有專案的提示詞。`historySearch:cycleScope` 僅在[全螢幕渲染](https://code.claude.com/docs/zh-TW/fullscreen.md)中生效，在此模式下 `Ctrl+R` 會改為開啟搜尋對話框，而 `Ctrl+S` 會循環切換其範圍。該對話框的其他按鍵是固定的，無法重新繫結：`Enter` 或 `Tab` 會將醒目提示的符合項目放入提示詞輸入中，`Esc` 則會取消。

### 任務動作

在 `Task` 情境中可用的動作：

| 動作 | 預設 | 說明 |
| :- | :- | :- |
| `task:background` | Ctrl+B, Ctrl+X Ctrl+B | 將目前的任務移至背景 |

### 主題動作

在 `ThemePicker` 情境中可用的動作：

| 動作 | 預設 | 說明 |
| :- | :- | :- |
| `theme:toggleSyntaxHighlighting` | Ctrl+T | 切換語法醒目提示 |

### 說明動作

在 `Help` 情境中可用的動作：

| 動作 | 預設 | 說明 |
| :- | :- | :- |
| `help:dismiss` | Escape | 關閉說明選單 |

### 分頁動作

在 `Tabs` 情境中可用的動作：

| 動作 | 預設 | 說明 |
| :- | :- | :- |
| `tabs:next` | Tab, Right | 下一個分頁 |
| `tabs:previous` | Shift+Tab, Left | 上一個分頁 |

在含有分頁的對話框中，當分頁列取得焦點時，`tabs:next` 和 `tabs:previous` 會切換分頁。在某些對話框中（例如 `/help` 和 `/sandbox`），分頁切換按鍵在分頁內容中也能運作。

`Up` 和 `Down` 會在分頁列與分頁內容之間移動焦點，而內容中的清單只有在取得焦點時才會回應按鍵。

### 附件動作

在 `Attachments` 情境中可用的動作：

| 動作 | 預設 | 說明 |
| :- | :- | :- |
| `attachments:next` | Right | 下一個附件 |
| `attachments:previous` | Left | 上一個附件 |
| `attachments:remove` | Backspace, Delete | 移除選取的附件 |
| `attachments:exit` | Down, Escape | 結束附件瀏覽 |

### 頁尾動作

在 `Footer` 情境中可用的動作：

| 動作 | 預設 | 說明 |
| :- | :- | :- |
| `footer:next` | Right | 下一個頁尾項目 |
| `footer:previous` | Left | 上一個頁尾項目 |
| `footer:up` | Up, Ctrl+P | 在頁尾中向上瀏覽（在頂端時取消選取） |
| `footer:down` | Down, Ctrl+N | 在頁尾中向下瀏覽 |
| `footer:openSelected` | Enter | 開啟選取的頁尾項目 |
| `footer:clearSelection` | Escape | 清除頁尾選取 |
| `footer:close` | x | 停止選取的 [agent](https://code.claude.com/docs/zh-TW/sub-agents.md#observe-and-steer-running-forks) 或[工作流程](https://code.claude.com/docs/zh-TW/workflows.md#manage-runs)，若其已不再執行，則關閉其所在列 |
| `footer:dismiss` | （未繫結） | 將按鍵繫結至此動作不會有任何效果，而指定此動作的 `keybindings.json` 仍然有效。在 v2.1.281 之前，Backspace 和 Delete 繫結至此動作，用於從頁尾關閉選取的 artifact 連結。 |

當選取了頁尾項目（例如提示詞下方 agent 面板中的某一列）時，即使您在 `Chat` 情境中將 `Enter` 重新繫結至 `chat:queueSubmit` 或 `chat:newline`，`Enter` 仍會開啟該項目。

`Footer` 情境未繫結之按鍵上的 `Chat` 繫結（例如用於 `chat:cycleMode` 的 `Shift+Tab`），在選取項目時仍會繼續運作。

### 訊息選擇器動作

在[倒轉選單](https://code.claude.com/docs/zh-TW/checkpointing.md)的訊息清單中，您可以使用 [Select 動作](#select-actions)及其預設按鍵來瀏覽訊息並挑選其中一則。您為這些動作設定的 `Select` 繫結也適用於此處。`MessageSelector` 情境本身沒有任何動作或預設繫結。您可以使用它來僅針對此清單變更按鍵，方法是在 `MessageSelector` 區塊中繫結 Select 動作，例如 `select:accept`。

此範例將 `o` 繫結為在倒轉選單中挑選醒目提示的訊息，而不變更任何其他清單：

```json theme={null}
{
  "bindings": [
    {
      "context": "MessageSelector",
      "bindings": {
        "o": "select:accept"
      }
    }
  ]
}
```

在 v2.1.283 之前，此清單會忽略 `Select` 繫結，並擁有自己的動作：`messageSelector:up`、`messageSelector:down`、`messageSelector:top`、`messageSelector:bottom` 和 `messageSelector:select`。如果您的 `keybindings.json` 繫結了其中一個名稱，該繫結會在此清單中繼續運作，作為執行相同功能的 Select 動作。`Home` 和 `End` 會跳至清單的任一端；在 v2.1.283 之前，預設是由 `Shift+K` 和 `Shift+J` 等按鍵執行此功能。

### 差異動作

這些動作僅作用於 Claude Code 較早期的差異檢視器，也就是在您於 `/plugin` 中停用 [`cc-plugin-diff` mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview#mods-built-into-claude-code) 後，`/diff` 在[全螢幕渲染](https://code.claude.com/docs/zh-TW/fullscreen.md)以外開啟的檢視器。當該 mod 啟用時，`/diff` 會改為開啟[差異對話框](https://code.claude.com/docs/zh-TW/interactive-mode.md#diff-dialog)。無論哪種情況，指定這些動作的 `keybindings.json` 都能正常載入而不會出錯。

在 `DiffDialog` 情境中可用的動作：

| 動作 | 預設 | 說明 |
| :- | :- | :- |
| `diff:dismiss` | Escape | 關閉差異檢視器；若在詳細檢視中，則改為返回檔案清單，而不關閉檢視器 |
| `diff:previousSource` | Left | 上一個差異來源 |
| `diff:nextSource` | Right | 下一個差異來源 |
| `diff:previousFile` | Up, K | 檔案清單中的上一個檔案；在詳細檢視中向上捲動一行 |
| `diff:nextFile` | Down, J | 檔案清單中的下一個檔案；在詳細檢視中向下捲動一行 |
| `diff:back` | （未繫結） | 在差異檢視器中返回。Escape 會透過 `diff:dismiss` 執行返回動作。先前在詳細檢視中預設的 Left 已於 v2.1.203 移除 |

檔案清單也會透過 [Select 動作](#select-actions)的預設按鍵和您的 `Select` 繫結來回應這些動作。`select:previous` 和 `select:next` 會移至上一個和下一個檔案，而 `Enter` 會透過 `select:accept` 開啟所選檔案的差異。若要僅針對檔案清單變更其中一個按鍵，請在 `DiffDialog` 區塊中繫結該 Select 動作。

在 v2.1.283 之前，檔案清單會忽略 `Select` 繫結，而 `Enter` 是透過獨立的 `diff:viewDetails` 動作開啟所選檔案的差異。如果您的 `keybindings.json` 繫結了 `diff:viewDetails`，該繫結會在檔案清單中繼續作為 `select:accept` 運作。

差異詳細檢視也將分頁器風格的按鍵繫結至標準的[捲動動作](#scroll-actions)。這些繫結屬於 `DiffDialog` 情境，且僅適用於詳細檢視；[捲動動作](#scroll-actions)下列出的 `Scroll` 情境預設值保持不變。

| 動作 | 預設 | 說明 |
| :- | :- | :- |
| `scroll:pageUp` | PageUp | 向上捲動半個檢視區 |
| `scroll:pageDown` | PageDown | 向下捲動半個檢視區 |
| `scroll:fullPageUp` | Shift+Space, B | 向上捲動一整個檢視區 |
| `scroll:fullPageDown` | Space | 向下捲動一整個檢視區 |
| `scroll:top` | G, Home | 跳至頂端 |
| `scroll:bottom` | Shift+G, End | 跳至底端 |

### 差異面板動作

用於在全螢幕渲染中由 `/diff` 開啟之[差異面板](https://code.claude.com/docs/zh-TW/interactive-mode.md#diff-panel)的動作。`app:cycleDiffBase` 屬於 `DiffPanel` 情境，該情境在面板開啟時啟用；其他動作則屬於 `Global`。

內建的 [`cc-plugin-diff` mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview#mods-built-into-claude-code) 會繪製此面板，並處理 `app:cycleDiffBase`、`app:diffFileListUp` 和 `app:diffFileListDown`。`app:toggleReplTab`、`app:toggleDiffNoiseFilter` 和 `app:toggleDiffPreSession` 僅作用於 Claude Code 較早期的面板，也就是在您於 `/plugin` 中停用 `cc-plugin-diff` 後由 `/diff` 開啟的面板。

| 動作 | 預設 | 說明 |
| :- | :- | :- |
| `app:toggleReplTab` | （未繫結） | 開啟或關閉差異面板 |
| `app:cycleDiffBase` | Ctrl+X B | 循環切換面板的比較基準：此工作階段、未提交，接著是分支 |
| `app:diffFileListUp` | Ctrl+Up, Meta+Up | 當面板的檔案清單超出範圍時向上捲動 |
| `app:diffFileListDown` | Ctrl+Down, Meta+Down | 當面板的檔案清單超出範圍時向下捲動 |
| `app:toggleDiffNoiseFilter` | （未繫結） | 在面板中顯示或隱藏測試檔案與產生的檔案 |
| `app:toggleDiffPreSession` | （未繫結） | 展開或摺疊此工作階段之前的變更 |

### 模型選擇器動作

在 `ModelPicker` 情境中可用的動作：

| 動作 | 預設 | 說明 |
| :- | :- | :- |
| `modelPicker:decreaseEffort` | Left | 降低 effort 等級 |
| `modelPicker:increaseEffort` | Right | 提高 effort 等級 |
| `modelPicker:thisSessionOnly` | s | 僅將醒目提示的模型套用至此工作階段 |

### Effort 滑桿動作

在 `EffortSlider` 情境中可用的動作，該情境即為您在不帶引數執行 `/effort` 時開啟的滑桿。滑桿的 Enter 和 Escape 按鍵無法重新繫結。

| 動作 | 預設 | 說明 |
| :- | :- | :- |
| `effortSlider:decreaseEffort` | Left | 將滑桿移至下一個較低的 effort 等級。需要 v2.1.284 或更新版本 |
| `effortSlider:increaseEffort` | Right | 將滑桿移至下一個較高的 effort 等級。需要 v2.1.284 或更新版本 |
| `effortSlider:toggleUltracode` | Tab | 當滑桿[提供此選項](https://code.claude.com/docs/zh-TW/model-config.md#when-ultracode-is-available)時，為此工作階段開啟或關閉 [ultracode](https://code.claude.com/docs/zh-TW/workflows.md#let-claude-decide-with-ultracode)。需要 v2.1.284 或更新版本 |
| `effortSlider:thisSessionOnly` | s | 僅將取得焦點的 [effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)套用至此工作階段。需要 v2.1.257 或更新版本 |

### Select 動作

在 `Select` 情境中可用的動作：

| 動作 | 預設 | 說明 |
| :- | :- | :- |
| `select:next` | Down, J, Ctrl+N | 下一個選項 |
| `select:previous` | Up, K, Ctrl+P | 上一個選項 |
| `select:pageUp` | PageUp | 向上移動一頁選項 |
| `select:pageDown` | PageDown | 向下移動一頁選項 |
| `select:first` | Home | 第一個選項 |
| `select:last` | End | 最後一個選項 |
| `select:accept` | Enter | 接受選取 |
| `select:cancel` | Escape | 取消選取 |

在 `/skills`、`/mcp` 和 `/tasks` 等清單面板中，Claude Code 會套用您的 `select:pageUp`、`select:pageDown`、`select:first` 和 `select:last` 繫結。在大多數其他清單中（例如 `/model` 選擇器），會套用您的 `select:first` 和 `select:last` 繫結。無論您的繫結為何，PageUp 和 PageDown 都會在這些清單中翻頁瀏覽選項。

在 v2.1.280 之前，這些其他清單會忽略 Home、End 以及您的 `select:first` 和 `select:last` 繫結。

在 v2.1.283 之前，無論您的繫結為何，`/mcp` 工具清單都使用固定的 PageUp 和 PageDown 按鍵翻頁。

### 外掛動作

在 `Plugin` 情境中可用的動作：

| 動作 | 預設 | 說明 |
| :- | :- | :- |
| `plugin:toggle` | Space | 切換外掛選取 |
| `plugin:install` | I | 安裝選取的外掛 |
| `plugin:favorite` | F | 將選取的外掛加入最愛，使其排序在 Installed 分頁的頂端附近 |

### 提示詞上方動作

用於提示詞上方區帶的動作，該區帶是 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md#pick-where-to-draw) 繪製按鈕、輸入欄位和選擇框的共用區域。`abovePrompt:toggle` 和 `abovePrompt:focus` 適用於 `Chat` 情境。其他動作則適用於區帶或窗格中目前取得鍵盤焦點之項目的[情境](#contexts)。

| 動作 | 預設 | 說明 |
| :- | :- | :- |
| `abovePrompt:toggle` | Ctrl+X Ctrl+A | 將區帶摺疊為單列提示，或再次展開 |
| `abovePrompt:focus` | Ctrl+X Tab | 將鍵盤焦點移至區帶，接著移至每個開啟的[窗格](#pane-actions)，並從最後一個窗格返回提示詞 |
| `abovePrompt:next` | Tab | 將焦點移至下一個控制項 |
| `abovePrompt:previous` | Shift+Tab | 將焦點移至上一個控制項 |
| `abovePrompt:press` | Enter | 按下取得焦點的按鈕、送出取得焦點的輸入欄位，或在選擇框中挑選醒目提示的選項 |
| `abovePrompt:leave` | Escape | 將鍵盤焦點返回至提示詞 |
| `abovePrompt:highlightNext` | Down | 在取得焦點的選擇框中醒目提示下一個選項 |
| `abovePrompt:highlightPrevious` | Up | 在取得焦點的選擇框中醒目提示上一個選項 |

在 [`AbovePrompt` 情境](#contexts)中，Right 和 Left 預設也會執行 `abovePrompt:next` 和 `abovePrompt:previous`，而 Space 也會執行 `abovePrompt:press`。

`AbovePrompt` 情境也將 Up、Down、PageUp、PageDown、Home 和 End 繫結至[窗格捲動動作](#pane-actions) `pane:scrollUp` 至 `pane:bottom`，因此若要為區帶變更其中一個按鍵，請在 `AbovePrompt` 區塊中繫結該捲動動作。

### 窗格動作

用於由 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md#know-which-keys-your-mod-can-receive) 繪製之窗格的動作。捲動、調整大小和關閉動作適用於 `Pane` [情境](#contexts)。`pane:close` 也適用於 `PaneField` 情境，因此在窗格的某個欄位取得焦點時也能運作。`pane:next` 和 `pane:previous` 在開啟多個窗格時適用於 `Global` 情境。

| 動作 | 預設 | 說明 |
| :- | :- | :- |
| `pane:scrollUp` | Up | 當窗格的列數多於可顯示的數量時，向上捲動窗格 |
| `pane:scrollDown` | Down | 當窗格的列數多於可顯示的數量時，向下捲動窗格 |
| `pane:pageUp` | PageUp | 將窗格向上捲動一頁 |
| `pane:pageDown` | PageDown | 將窗格向下捲動一頁 |
| `pane:top` | Home | 跳至窗格頂端 |
| `pane:bottom` | End | 跳至窗格底端 |
| `pane:grow` | Ctrl+X Left, Ctrl+X Up | 給予窗格更多空間：位於逐字稿旁時增加寬度，位於提示詞上方時增加高度 |
| `pane:shrink` | Ctrl+X Right, Ctrl+X Down | 給予窗格較少空間：位於逐字稿旁時減少寬度，位於提示詞上方時減少高度 |
| `pane:close` | Ctrl+X X | 關閉窗格 |
| `pane:next` | （未繫結） | 顯示下一個開啟的窗格 |
| `pane:previous` | （未繫結） | 顯示上一個開啟的窗格 |

`Pane` 情境也將 Tab、Shift+Tab、Enter 和 Escape 繫結至與區帶相同的[提示詞上方動作](#above-prompt-actions)，而窗格的輸入欄位和選擇框則使用 `AbovePromptInput` 和 `AbovePromptSelect` 情境。[鍵盤焦點與快速鍵](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md#know-which-keys-your-mod-can-receive)列出了每個按鍵在窗格中的作用。

### 設定動作

在 `Settings` 情境中可用的動作。`select:accept` 和 `confirm:no` 動作沿用自 [Select](#select-actions) 和 [Confirmation](#confirmation-actions) 情境，但具有 Settings 特有的行為：每個設定在您變更後會立即套用，因此 Escape 會在儲存您的變更後關閉面板，而非拒絕變更。

| 動作 | 預設 | 說明 |
| :- | :- | :- |
| `settings:search` | / | 進入搜尋模式 |
| `settings:retry` | R | 發生錯誤時重試載入使用量資料 |
| `settings:fixUsage` | F | 當 `/usage` 頁尾提供修正時，將 Claude Code 可套用的 [`/usage` 建議](https://code.claude.com/docs/zh-TW/costs#apply-recommendations-with-the-fix-shortcut)傳送至您的工作階段。需要 v2.1.305 或更新版本 |
| `select:accept` | Enter, Space | 變更選取的設定或開啟其子選單 |
| `confirm:no` | Escape | 關閉面板。變更已儲存 |

### Agents 動作

在 `Agents` 情境中可用的動作，該情境適用於以 `claude agents` 開啟的 [agent 檢視](https://code.claude.com/docs/zh-TW/agent-view.md)。需要 v2.1.257 或更新版本。

| 動作 | 預設 | 說明 |
| :- | :- | :- |
| `agents:switchView` | Ctrl+S | 在狀態與目錄之間切換[工作階段分組](https://code.claude.com/docs/zh-TW/agent-view.md#organize-the-list) |
| `agents:togglePin` | Ctrl+T | [釘選或取消釘選](https://code.claude.com/docs/zh-TW/agent-view.md#organize-the-list)選取的工作階段 |
| `agents:find` | Ctrl+F | 使用 [`n:` 篩選器](https://code.claude.com/docs/zh-TW/agent-view#filter-sessions)依名稱尋找工作階段。需要 v2.1.288 或更新版本 |
| `agents:rename` | Ctrl+R | [重新命名](https://code.claude.com/docs/zh-TW/agent-view.md#organize-the-list)選取的工作階段。需要 v2.1.288 或更新版本 |
| `agents:previousGroup` | Ctrl+Up, Meta+Up | 跳至上一個[群組標題](https://code.claude.com/docs/zh-TW/agent-view.md#organize-the-list)。需要 v2.1.288 或更新版本 |
| `agents:nextGroup` | Ctrl+Down, Meta+Down | 跳至下一個群組標題。需要 v2.1.288 或更新版本 |

當 agent 檢視開啟時，對於 `Agents` 情境所繫結的任何按鍵，Claude Code 都會使用 `Agents` 繫結，並忽略同一按鍵上的 `Chat` 或 `Global` 繫結。例如，在 agent 檢視中按下 Ctrl+S 會切換工作階段分組，而不是觸發預設的 `chat:stash`。

dispatch 輸入的外部編輯器快捷鍵不是 `Agents` 動作。agent 檢視會遵循 `Chat` 情境的 `chat:externalEditor` 繫結，預設為 Ctrl+G。

在 agent 檢視中，繫結會在單一按鍵時觸發，因此繫結至 `chat:externalEditor` 的 Ctrl+X Ctrl+E 組合鍵不會在該處開啟編輯器。

### 語音動作

啟用[語音聽寫](https://code.claude.com/docs/zh-TW/voice-dictation.md)時，在 `Chat` 情境中可用的動作：

| 動作 | 預設 | 說明 |
| :- | :- | :- |
| `voice:pushToTalk` | Space | 聽寫提示詞。依 `/voice` 模式按住或輕按 |

### 捲動動作

啟用[全螢幕渲染](https://code.claude.com/docs/zh-TW/fullscreen.md)時，在 `Scroll` 情境中可用的動作：

| 動作 | 預設 | 說明 |
| :- | :- | :- |
| `scroll:lineUp` | `wheelup` | 向上捲動一行。滑鼠滾輪捲動會觸發此動作 |
| `scroll:lineDown` | `wheeldown` | 向下捲動一行。滑鼠滾輪捲動會觸發此動作 |
| `scroll:pageUp` | PageUp | 向上捲動半個檢視區高度 |
| `scroll:pageDown` | PageDown | 向下捲動半個檢視區高度 |
| `scroll:top` | Ctrl+Home | 跳至對話的開頭 |
| `scroll:bottom` | Ctrl+End | 跳至最新訊息並重新啟用自動跟隨 |
| `scroll:halfPageUp` | （未繫結） | 向上捲動半個檢視區高度。行為與 `scroll:pageUp` 相同，提供給 vi 風格的重新繫結使用 |
| `scroll:halfPageDown` | （未繫結） | 向下捲動半個檢視區高度。行為與 `scroll:pageDown` 相同，提供給 vi 風格的重新繫結使用 |
| `scroll:fullPageUp` | （未繫結） | 向上捲動一整個檢視區高度 |
| `scroll:fullPageDown` | （未繫結） | 向下捲動一整個檢視區高度 |
| `selection:copy` | Ctrl+Shift+C / Cmd+C | 將選取的文字複製到剪貼簿 |
| `selection:clear` | （未繫結） | 清除目前的文字選取。需要 v2.1.234 或更新版本 |
| `selection:extendLeft` | Shift+Left | 將目前的選取範圍向左延伸一欄 |
| `selection:extendRight` | Shift+Right | 將目前的選取範圍向右延伸一欄 |
| `selection:extendUp` | Shift+Up | 將目前的選取範圍向上延伸一列。當選取範圍到達頂端邊緣時會捲動檢視區 |
| `selection:extendDown` | Shift+Down | 將目前的選取範圍向下延伸一列。當選取範圍到達底端邊緣時會捲動檢視區 |
| `selection:extendLineStart` | Shift+Home | 將目前的選取範圍延伸至行首 |
| `selection:extendLineEnd` | Shift+End | 將目前的選取範圍延伸至行尾 |

## 按鍵組合語法

### 修飾鍵

使用 `+` 分隔符搭配修飾鍵：

* `ctrl` 或 `control` - Control 鍵
* `shift` - Shift 鍵
* `alt`、`opt`、`option` 或 `meta` - Windows 和 Linux 上的 Alt 鍵，macOS 上的 Option 鍵
* `cmd`、`command`、`super` 或 `win` - macOS 上的 Command 鍵，Windows 上的 Windows 鍵，Linux 上的 Super 鍵

`cmd` 群組只在報告 Super 修飾鍵的終端機中被偵測，例如支援 Kitty 鍵盤協議或 xterm 的 `modifyOtherKeys` 模式的終端機。大多數終端機不會發送它，因此對於您想在任何地方都能運作的繫結，請使用 `ctrl` 或 `meta`。

例如：

```text theme={null}
ctrl+k          Ctrl + K
shift+tab       Shift + Tab
meta+p          macOS 上的 Option + P，其他地方為 Alt + P
ctrl+shift+c    多個修飾鍵
```

### 大寫字母

Claude Code 不區分大小寫地解析按鍵名稱，因此 `K` 與 `k` 的繫結相同，`ctrl+K` 與 `ctrl+k` 相同。若要繫結 Shift 和一個字母，請寫 `shift+k`。

### 非美式鍵盤配置

即使您的作用中鍵盤配置輸入其他字元，也請將 Ctrl 快捷鍵的按鍵名稱寫成拉丁字元。

Claude Code 如何將您按下的按鍵與繫結相符取決於配置的類型：

* 在西里爾字母等非拉丁配置下，當終端機使用 Kitty 鍵盤協議並報告該位置時，Claude Code 會根據按鍵的美式配置位置來符合 Ctrl 快捷鍵。在這樣的終端機中，使用俄文配置時，按下 Ctrl 和實體 W 鍵會觸發 `ctrl+w`。在不報告位置的終端機中，Claude Code 會符合終端機為按鍵發送的任何內容：ASCII 控制碼會觸發拉丁快捷鍵，而作為西里爾字元到達的按鍵不符合任何繫結
* 在重新排列拉丁字母的配置下，例如 AZERTY，Claude Code 會符合按鍵輸入的字母，因此按下 Ctrl 和標記為 A 的按鍵會觸發 `ctrl+a`

### 和弦

和弦是由空格分隔的按鍵組合序列：

```text theme={null}
ctrl+k ctrl+s   按 Ctrl+K，放開，然後按 Ctrl+S
```

在每個按鍵組合的 3 秒內按下下一個。如果您等待更長時間，Claude Code 會取消和弦並顯示簡短通知。

### 特殊鍵

* `escape` 或 `esc` - Escape 鍵
* `enter` 或 `return` - Enter 鍵
* `tab` - Tab 鍵
* `space` - 空格鍵
* `up`、`down`、`left`、`right` - 方向鍵
* `pageup`、`pagedown` - Page Up 和 Page Down 鍵
* `home`、`end` - Home 和 End 鍵
* `backspace`、`delete` - 刪除鍵
* `wheelup`、`wheeldown` - 滑鼠滾輪捲動事件

## 取消繫結預設快捷鍵

將動作設定為 `null` 以取消繫結預設快捷鍵：

```json theme={null}
{
  "bindings": [
    {
      "context": "Chat",
      "bindings": {
        "ctrl+s": null
      }
    }
  ]
}
```

這也適用於和弦繫結。取消繫結共享前綴的每個和弦會釋放該前綴以用作單一鍵繫結。任何作用中的內容中的和弦會保留其前綴的保留狀態，因此您必須在定義該和弦的內容中取消繫結每個和弦。

Claude Code 在 `ctrl+x` 前綴上繫結這些預設和弦，依內容分列如下：

* `Chat`：`ctrl+x ctrl+k`、`ctrl+x ctrl+e`、`ctrl+x enter`、`ctrl+x ctrl+a`、`ctrl+x ctrl+s` 和 `ctrl+x tab`
* `Task`：`ctrl+x ctrl+b`
* `DiffPanel`：`ctrl+x b`
* `Pane`：`ctrl+x left`、`ctrl+x right`、`ctrl+x up`、`ctrl+x down` 和 `ctrl+x x`
* `PaneField`：`ctrl+x x`

`ctrl+x enter` 和弦需要 v2.1.247 或更新版本，`ctrl+x b`、`ctrl+x ctrl+a` 和 `ctrl+x tab` 需要 v2.1.260 或更新版本，而 `ctrl+x ctrl+s` 需要 v2.1.275 或更新版本。

若要將 `ctrl+x` 本身回收為單一鍵繫結，請取消繫結所有這些：

```json theme={null}
{
  "bindings": [
    {
      "context": "Task",
      "bindings": {
        "ctrl+x ctrl+b": null
      }
    },
    {
      "context": "DiffPanel",
      "bindings": {
        "ctrl+x b": null
      }
    },
    {
      "context": "Pane",
      "bindings": {
        "ctrl+x left": null,
        "ctrl+x right": null,
        "ctrl+x up": null,
        "ctrl+x down": null,
        "ctrl+x x": null
      }
    },
    {
      "context": "PaneField",
      "bindings": {
        "ctrl+x x": null
      }
    },
    {
      "context": "Chat",
      "bindings": {
        "ctrl+x ctrl+k": null,
        "ctrl+x ctrl+e": null,
        "ctrl+x enter": null,
        "ctrl+x ctrl+a": null,
        "ctrl+x ctrl+s": null,
        "ctrl+x tab": null,
        "ctrl+x": "chat:newline"
      }
    }
  ]
}
```

如果您取消繫結前綴上的某些但不是全部和弦，按下前綴仍會進入和弦等待模式以進行剩餘的繫結。

## 保留的快捷鍵

這些快捷鍵無法重新繫結：

| 快捷鍵 | 原因 |
| :- | :- |
| Ctrl+C | 硬編碼的中斷/取消 |
| Ctrl+D | 硬編碼的結束 |
| Ctrl+M | Claude Code 始終將其接收為 Enter |
| Ctrl+\[ | Claude Code 始終將其接收為 Escape。在使用 Kitty 鍵盤協議的終端機中，這需要 v2.1.242 或更新版本 |
| Ctrl+I | Claude Code 始終將其接收為 Tab |
| Ctrl+H | 傳送 ASCII 退格位元組。[Claude Code 在 Windows 上如何讀取它](https://code.claude.com/docs/zh-TW/terminal-config.md#fix-backspace-deleting-a-whole-word-on-windows)取決於您的終端機和 [`CLAUDE_CODE_BS_AS_CTRL_BACKSPACE`](https://code.claude.com/docs/zh-TW/env-vars) 環境變數 |
| Caps Lock | 未傳遞至終端機應用程式 |

## 終端機衝突

某些快捷鍵可能與終端機多工器衝突：

| 快捷鍵 | 衝突 |
| :- | :- |
| Ctrl+B | tmux 前綴（按兩次以傳送） |
| Ctrl+A | GNU screen 前綴 |
| Ctrl+Z | Unix 程序暫停 (SIGTSTP) |

## 文字欄位

如果你綁定一個裸露的字母、數字或空格鍵，你仍然可以在對話框或面板內的文字欄位中輸入該字元。其中一個欄位是 Claude 提出問題時的 `Other` 答案。當欄位獲得焦點時，你按下的可列印鍵（不含 Ctrl、Alt 或 Cmd）會進入該欄位，Claude Code 不會根據你的綁定來匹配它。

這些鍵在欄位獲得焦點時仍會執行其綁定：

* 不輸入字元的鍵，例如 Enter、Escape、Tab 和方向鍵
* 任何使用 Ctrl、Alt 或 Cmd 按下的鍵
* 已在進行中的[和弦](#chords)的第二個按鍵

在主提示符處，Claude Code 根據作用中的內容（例如 `Chat`）來匹配每個鍵，只有在沒有綁定取用該鍵時才會輸入該鍵。

## Vim 模式互動

當您透過 `/config` 中的編輯器模式設定啟用 vim 模式時，快捷鍵和 vim 模式會獨立運作：

* **Vim 模式**在文字輸入層級處理輸入：游標移動、模式和動作
* **快捷鍵**在元件層級處理動作，例如切換待辦事項或提交訊息
* 在 vim 模式中，Escape 鍵會將 INSERT 模式切換為 NORMAL 模式；它不會觸發 `chat:cancel`
* 大多數 Ctrl+鍵快捷鍵通過 vim 模式傳遞到快捷鍵系統
* Vim 鍵無法透過快捷鍵檔案重新對應。若要對應兩鍵 INSERT 模式序列（例如 `jj`）至 Escape，請使用 [`vimInsertModeRemaps`](https://code.claude.com/docs/zh-TW/interactive-mode#remap-insert-mode-key-sequences) 設定
* 在 vim NORMAL 模式中，`?` 顯示說明選單（vim 行為）
* 在 vim NORMAL 模式中，`/` 開啟歷史搜尋，與標準模式中的 Ctrl+R 相同

在 Claude 提出的問題的 `Other` 列中，vim 模式下的 Escape 不會立即取消該問題。除了在[螢幕閱讀器模式](https://code.claude.com/docs/zh-TW/accessibility.md)中以外，每次您將焦點移至該列時，該列都會從 INSERT 模式開始。當您在 `Other` 列中按下 Escape 時，該列會切換到 NORMAL 模式或捨棄輸入到一半的 vim 命令，而問題仍會保持開啟。在 NORMAL 模式中再按一次 Escape 即可取消該問題。

### 按一個鍵取消問題

若要在 vim 模式中按一個鍵即取消問題，請在 `Select` 情境中將另一個鍵綁定至 `select:cancel`。您可以在只能選擇一個選項的問題的 `Other` 列中以此方式取消。在[螢幕閱讀器模式](https://code.claude.com/docs/zh-TW/accessibility.md)中，或在可選擇多個選項的問題中，綁定的鍵不會取消問題，因此請改用 Escape 取消。

請選擇搭配 Ctrl 或 Alt 按下的鍵。單獨的字母或數字會改為[輸入至 `Other` 列](#text-fields)，而不會觸發您的綁定。例如，若要綁定 `Ctrl+Q`，請將以下內容新增至 `~/.claude/keybindings.json`：

```json theme={null}
{
  "bindings": [
    {
      "context": "Select",
      "bindings": {
        "ctrl+q": "select:cancel"
      }
    }
  ]
}
```

儲存檔案後，在只能選擇一個選項的問題的 `Other` 列中按下 `Ctrl+Q`。無論該列處於 INSERT 或 NORMAL 模式，問題都會關閉。

## 驗證

Claude Code 驗證您的快捷鍵並為以下項目寫入警告到偵錯日誌：

* 解析錯誤（無效的 JSON 或結構）
* 拼寫錯誤的修飾鍵，例如 `ctl+k`。Claude Code 會捨棄它無法識別的部分，並將繫結應用於剩餘的按鍵，在此範例中為 `k`。
* 按鍵字串中 `+` 旁邊有空格，例如 `ctrl+ k`。Claude Code 會將該字串解讀為由 `ctrl+` 後接 `k` 組成的[組合鍵](#chords)。沒有任何按鍵會單獨符合 `ctrl+`，因此該繫結永遠不會觸發。請移除該空格。
* 無效的上下文名稱
* 無效的動作值，例如不是字串或 `null` 的動作
* 未知的動作名稱，例如已註冊動作的拼寫錯誤。Claude Code 會跳過該繫結並保持該按鍵的任何預設繫結有效。
* 保留快捷鍵衝突
* 同一上下文中的重複繫結

使用 [`--debug`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 啟動 Claude Code 以查看詳細資訊。

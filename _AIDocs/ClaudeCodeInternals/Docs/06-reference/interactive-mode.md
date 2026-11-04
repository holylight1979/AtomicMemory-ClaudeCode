<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/interactive-mode | lastmod: 2026-11-03 | section: Reference / Reference -->
> 來源：https://code.claude.com/docs/zh-TW/interactive-mode（官方 zh-TW，lastmod 2026-11-03）｜分類：Reference › Reference｜EN 摘要：Complete reference for keyboard shortcuts, input modes, and interactive features in Claude Code sessions.

# 互動模式

> Claude Code 工作階段中鍵盤快捷鍵、輸入模式和互動功能的完整參考。

## 快捷鍵

> [!NOTE]
>
> 快捷鍵可能因平台和終端而異。在[全螢幕渲染](https://code.claude.com/docs/zh-TW/fullscreen.md)中，在文字記錄檢視器中按 `?` 以查看可用的快捷鍵。
>
> **macOS 使用者**：Option/Alt 鍵快捷鍵（`Alt+B`、`Alt+F`、`Alt+D`、`Alt+Y`、`Alt+P`）需要在您的終端中將 Option 設定為 Meta。請參閱[在 macOS 上啟用 Option 鍵快捷鍵](https://code.claude.com/docs/zh-TW/terminal-config.md#enable-option-key-shortcuts-on-macos)以了解每個終端中的設定。

### 一般控制

| 快捷鍵 | 說明 | 內容 |
| :- | :- | :- |
| `Ctrl+C` | 中斷或清除輸入 | 中斷執行中的操作。如果沒有任何操作執行中，第一次按下會清除提示詞輸入，第二次按下會退出 Claude Code。若要取回已清除的草稿，請參閱[取回已清除的草稿](#bring-back-a-cleared-draft) |
| `Ctrl+X Ctrl+K` | 停止此工作階段中所有執行中的[背景 subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#run-subagents-in-foreground-or-background)，並在此工作階段剩餘期間關閉 [artifact 自動回覆](https://code.claude.com/docs/zh-TW/artifacts.md#let-claude-reply-to-comments-on-its-own)。在 3 秒內按兩次以確認。即使背景 subagent 的權限提示正開啟，您也可以按下此鍵 | Subagent 控制 |
| `Ctrl+D` | 退出 Claude Code 工作階段 | 第一次按下會顯示確認提示，第二次在 800ms 內按下會退出。當提示有文字時，`Ctrl+D` 會刪除游標後的字元 |
| `Ctrl+G` 或 `Ctrl+X Ctrl+E` | 在預設文字編輯器中開啟 | 在您的預設文字編輯器中編輯您的提示或自訂回應。`Ctrl+X Ctrl+E` 是 readline 原生繫結。在 `/config` 中開啟**在外部編輯器中顯示最後回應**以在您的提示上方將 Claude 的先前回覆作為 `#` 註解內容前置；Claude Code 會在您儲存時移除註解區塊 |
| `Ctrl+L` | 重繪螢幕 | 強制完整終端重繪，保留輸入和對話歷史記錄。如果顯示變得混亂或部分空白，請使用此選項來復原。請參閱[清除對話](https://code.claude.com/docs/zh-TW/fullscreen.md#clear-the-conversation)以了解全螢幕渲染 |
| `Ctrl+O` | 切換文字記錄檢視器 | 顯示詳細的工具使用情況和執行情況，每個助手訊息上都有時間戳記和使用的模型。也會展開預設摺疊的行，例如 MCP 呼叫，顯示為單一 `Called slack 3 times` 行，以及[來自您其他工作階段的訊息](https://code.claude.com/docs/zh-TW/cross-session-messaging.md#what-a-message-looks-like)，顯示為單行 `Message from @<sender>` 預覽 |
| `Ctrl+R` | 反向搜尋命令歷史記錄 | 以互動方式搜尋先前的命令 |
| `Ctrl+V` 或 `Cmd+V`（iTerm2）或 `Alt+V`（Windows 和 WSL） | 從剪貼簿貼上影像 | 在游標處插入 `[Image #N]` 晶片，以便您可以在提示中按位置參考它。在 WSL 上，`Ctrl+V` 和 `Alt+V` 都已繫結；如果您的終端攔截 `Ctrl+V`，請使用 `Alt+V` |
| `Ctrl+B` | 背景執行工作 | 將 Bash 命令和代理放在背景中。Tmux 使用者按兩次 |
| `Ctrl+T` | 切換 Claude 的工作清單 | 在狀態區域中顯示或隱藏 [Claude 的待辦事項清單](#task-list)。這不是背景工作檢視；使用 [`/tasks`](https://code.claude.com/docs/zh-TW/commands) 以查看執行中的 shell 和子代理 |
| `Ctrl+S` | 隱藏或復原提示 | 輸入中有文字時，隱藏它並清除提示。在空提示上再次按下時，復原隱藏的文字、游標位置、貼上的內容和輸入模式，所以隱藏的 `!` [shell 命令](#shell-mode-with-prefix)會以 shell 模式回來 |
| `Ctrl+Z` | 暫停 Claude Code | 僅限 Unix。將程序暫停到您的 shell；執行 `fg` 以繼續 |
| `Left/Right arrows` | 在對話框標籤之間循環 | 在權限對話框和功能表中的標籤之間導覽。在標籤式對話框中，當標籤列具有焦點時，這些鍵會切換標籤。請參閱[標籤動作](https://code.claude.com/docs/zh-TW/keybindings.md#tabs-actions)以了解焦點如何移動 |
| `Tab` | 接受自動完成建議，或在權限答案中新增註解 | 當自動完成建議在提示輸入中顯示時，接受選定的建議。在大多數權限提示上，當**是**或**否**獲得焦點時，會在該選項上開啟註解欄位，再次按下會關閉欄位。請參閱[在您回答權限提示時新增註解](https://code.claude.com/docs/zh-TW/permissions.md#add-a-comment-when-you-answer-a-permission-prompt) |
| `Up/Down arrows` 或 `Ctrl+P`/`Ctrl+N` | 移動游標或導覽命令歷史記錄 | 當輸入跨越多個視覺行時（無論是換行還是多行），首先在提示內移動游標。一旦游標在第一行或最後一行視覺行上，再次按下會導覽命令歷史記錄。當您有訊息排隊時，從第一行按 `Up` 會改為[取回您排隊的內容](#take-back-what-you-queued) |
| `Esc` | 中斷 Claude 或關閉對話框 | 停止目前的回應或工具呼叫中途，以便您可以重新導向。Claude 會保留迄今為止完成的工作。如果您有[訊息排隊](#queue-messages-while-claude-works)，Claude Code 會在下一步傳送它們。當對話框開啟時，`Esc` 會關閉對話框。當頁尾項目被選中時（例如提示下方的[子代理面板](https://code.claude.com/docs/zh-TW/sub-agents.md#run-subagents-in-foreground-or-background)中的一列），`Esc` 會[取消選中它](https://code.claude.com/docs/zh-TW/keybindings.md#footer-actions)而不是中斷。在權限提示上，`Esc` 會拒絕該操作，與[**否**（不含註解）](https://code.claude.com/docs/zh-TW/permissions.md#add-a-comment-when-you-answer-a-permission-prompt)相同 |
| `Esc` + `Esc` | 清除輸入草稿或回溯 | 當提示輸入包含文字時，雙 `Esc` 會清除它並將草稿儲存到歷史記錄，以便 `Up` 可以回憶它。當輸入為空時，雙 `Esc` 會開啟[回溯功能表](https://code.claude.com/docs/zh-TW/checkpointing.md)以從先前的時間點復原或摘要程式碼和對話 |
| `Ctrl+Enter` 或 `Ctrl+X Ctrl+S` | 立即傳送排隊的訊息 | 傳送您的[排隊訊息](#queue-messages-while-claude-works)和您的草稿與它們一起立即發出。[Claude Code 何時傳送您排隊的內容](#when-claude-code-sends-what-you-queued)涵蓋了 Claude 正在處理的回合會發生什麼。在[shell 模式](#shell-mode-with-prefix)中，該鍵只會將您的命令排隊。在不報告延伸鍵的終端中，`Ctrl+Enter` 會以純 `Enter` 的形式到達；`Ctrl+X Ctrl+S` 在任何終端中都有效。需要 Claude Code v2.1.275 或更新版本 |
| `Shift+Tab` 或 `Alt+M`（當 Node 或 Bun 執行時間未啟用 VT 輸入模式時在 Windows 上） | 循環權限模式 | 循環通過 `default`（在模式指示器中標記為 Manual）、`acceptEdits`、`plan` 和（如果可用）`bypassPermissions`，然後是 `auto`。從 `auto`，第一次按下會切換到 `default`。請參閱[權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md)。在檔案權限提示上，相同的鍵會關閉開啟的[註解欄位](https://code.claude.com/docs/zh-TW/permissions.md#add-a-comment-when-you-answer-a-permission-prompt)。沒有開啟欄位時，它會選擇允許該操作以供工作階段其餘部分的選項（當提示提供該選項時） |
| `Option+P`（macOS）或 `Alt+P`（Windows/Linux） | 切換模型 | 切換模型而不清除您的提示 |
| `Option+T`（macOS）或 `Alt+T`（Windows/Linux） | 切換延伸思考 | 啟用或停用延伸思考模式。對 Opus 5.5、Sonnet 5.5、Haiku 5.5 或 Fable 模型沒有影響，它們始終使用延伸思考。在 macOS 上無需設定 Option 為 Meta 即可運作 |
| `Option+O`（macOS）或 `Alt+O`（Windows/Linux） | 切換快速模式 | 啟用或停用[快速模式](https://code.claude.com/docs/zh-TW/fast-mode.md) |

### 文字編輯

| 快捷鍵 | 說明 | 內容 |
| :- | :- | :- |
| `Ctrl+A` | 將游標移至目前行的開始 | 在多行輸入中，移至目前邏輯行的開始 |
| `Ctrl+E` | 將游標移至目前行的結尾 | 在多行輸入中，移至目前邏輯行的結尾 |
| `Ctrl+K` | 刪除到行尾 | 儲存已刪除的文字以供貼上 |
| `Ctrl+U` | 從游標刪除到行開始 | 儲存已刪除的文字以供貼上。重複以清除多行輸入中的行。在 macOS 上，包括 iTerm2 和 Terminal.app 的終端模擬器會將 `Cmd+Backspace` 對應到此快捷鍵 |
| `Ctrl+W` | 刪除回到先前的空白 | 儲存已刪除的文字以供貼上。一次按下會移除整個路徑或 `--flag=value`。若要僅刪除先前的單字，請在 macOS 上按 `Option+Delete` 或在 Windows 上按 `Ctrl+Backspace` |
| `Ctrl+Y` | 貼上已刪除的文字 | 貼上您最後使用單字或行刪除快捷鍵（例如 `Ctrl+K`、`Ctrl+U` 或 `Ctrl+W`）刪除的文字 |
| `Alt+Y`（在 `Ctrl+Y` 之後） | 循環貼上歷史記錄 | 貼上後，循環通過先前刪除的文字。在 macOS 上需要[Option 為 Meta](#keyboard-shortcuts) |
| `Alt+B` | 將游標向後移動一個單字 | 單字導覽。在 macOS 上需要[Option 為 Meta](#keyboard-shortcuts) |
| `Alt+F` | 將游標向前移動一個單字 | 移至目前單字的結尾，或當游標在單字之間時移至下一個單字的結尾。在 macOS 上需要[Option 為 Meta](#keyboard-shortcuts) |
| `Alt+D` | 刪除到單字結尾 | 刪除到目前單字的結尾，或當游標在單字之間時刪除到下一個單字的結尾。儲存已刪除的文字以供貼上。在 macOS 上需要[Option 為 Meta](#keyboard-shortcuts) |
| `Ctrl+_` 或 `Ctrl+Shift+-` | 復原最後的輸入編輯 | 復原先前的輸入文字和游標位置 |

### 編輯快捷鍵中的單字邊界

單字快捷鍵 `Alt+B`、`Alt+F`、`Alt+D`、`Option+Delete` 和 `Ctrl+Backspace` 將單字視為字母和數字的執行，因此標點符號（例如 `_`、`.` 和 `/`）會分隔單字。在提示中有 `src/utils/foo.ts` 時，重複按 `Alt+B` 會在 `ts`、`foo`、`utils` 和 `src` 的開始處停止。

`Ctrl+W` 不同：它忽略標點符號並刪除回到先前的空白，因此一次按下會移除所有 `src/utils/foo.ts`。

在沒有空格的文字中（例如中文或日文），單字快捷鍵仍然一次移動或刪除一個單字。

這些 readline 慣例適用於 Claude Code v2.1.261 及更新版本。在較早版本中開啟它們的 [`keybindingFlavor`](https://code.claude.com/docs/zh-TW/settings-reference#keybindingflavor) 設定已被棄用，沒有任何影響。

您無法在[快捷鍵設定檔](https://code.claude.com/docs/zh-TW/keybindings.md)中重新對應這些快捷鍵，該檔案沒有這些快捷鍵的操作。

### 主題和顯示

| 快捷鍵 | 說明 | 內容 |
| :- | :- | :- |
| `Ctrl+T` | 切換程式碼區塊的語法醒目提示 | 僅在 `/theme` 選擇器功能表內運作。控制 Claude 回應中的程式碼是否使用語法著色 |

### 多行輸入

| 方法 | 快捷鍵 | 內容 |
| :- | :- | :- |
| 快速逃脫 | `\` + `Enter` | 在所有終端中運作 |
| Option 鍵 | `Option+Enter` | 在 macOS 上啟用[Option 為 Meta](https://code.claude.com/docs/zh-TW/terminal-config.md#enable-option-key-shortcuts-on-macos)後 |
| Shift+Enter | `Shift+Enter` | 在 iTerm2、WezTerm、Ghostty、Kitty、Warp、Apple Terminal、Windows Terminal 中原生。對於其他終端，請參閱[輸入多行提示](https://code.claude.com/docs/zh-TW/terminal-config.md#enter-multiline-prompts) |
| 控制序列 | `Ctrl+J` | 在任何終端中無需設定即可運作 |
| 貼上模式 | 直接貼上 | 對於程式碼區塊、日誌 |

### 快速命令

| 快捷鍵 | 說明 | 備註 |
| :- | :- | :- |
| `/` 在開始 | 命令或技能 | 請參閱[命令](#commands)和[技能](https://code.claude.com/docs/zh-TW/skills.md) |
| `!` 在開始 | Shell 模式 | 直接執行命令，將其輸出新增到工作階段，並讓 Claude 回應它 |
| `@` | 檔案路徑提及 | 觸發檔案路徑自動完成。在具有[跨工作階段訊息](https://code.claude.com/docs/zh-TW/cross-session-messaging.md#message-another-session)的工作階段中，當您在 `@` 後輸入至少一個字母時，Claude Code 也會建議您在此機器上的其他即時工作階段，以便您可以告訴 Claude 訊息您選擇的工作階段。需要 Claude Code v2.1.232 或更新版本 |
| `:` | 表情符號速記代碼 | 輸入完整的 `:name:` 以插入表情符號，或輸入兩個或更多字元以取得建議。請參閱[表情符號速記代碼](#emoji-shortcodes) |
| `?` 在空輸入上 | 切換快捷鍵說明面板 | 當輸入已包含文字時輸入 `?` 會插入字元 |

### 文字記錄檢視器

當文字記錄檢視器開啟時（使用 `Ctrl+O` 切換），這些快捷鍵可用。執行不帶引數的 `/tui` 以檢查哪個渲染器處於作用中。`Ctrl+E` 可以通過 [`transcript:toggleShowAll`](https://code.claude.com/docs/zh-TW/keybindings) 重新繫結。

| 快捷鍵 | 說明 |
| :- | :- |
| `?` | 切換鍵盤快捷鍵說明面板。需要[全螢幕渲染](https://code.claude.com/docs/zh-TW/fullscreen.md) |
| `{` / `}` | 跳到先前或下一個使用者提示，如 vim 段落動作。需要[全螢幕渲染](https://code.claude.com/docs/zh-TW/fullscreen.md) |
| `Ctrl+E` | 切換顯示所有內容。僅在傳統渲染器中可用，不在[全螢幕渲染](https://code.claude.com/docs/zh-TW/fullscreen.md)中 |
| `[` | 將完整對話寫入您終端的原生捲動回溯，以便 `Cmd+F`、tmux 複製模式和其他原生工具可以搜尋它。需要[全螢幕渲染](https://code.claude.com/docs/zh-TW/fullscreen.md#search-and-review-the-conversation) |
| `v` | 將對話寫入臨時檔案並在 `$VISUAL` 或 `$EDITOR` 中開啟它。需要[全螢幕渲染](https://code.claude.com/docs/zh-TW/fullscreen.md) |
| `q`、`Ctrl+C`、`Esc` | 退出文字記錄檢視。所有三個都可以通過 [`transcript:exit`](https://code.claude.com/docs/zh-TW/keybindings) 重新繫結 |

### 語音輸入

| 快捷鍵 | 說明 | 備註 |
| :- | :- | :- |
| 按住或點選 `Space` | 語音聽寫 | 需要啟用[語音聽寫](https://code.claude.com/docs/zh-TW/voice-dictation.md)。按住以錄製，或執行 `/voice tap` 以進行點選切換。[可重新繫結](https://code.claude.com/docs/zh-TW/voice-dictation.md#rebind-the-dictation-key) |

## 指令

在 Claude Code 中輸入 `/` 以查看可用的指令，或輸入 `/` 後跟任何字母來篩選。`/` 選單列出內建指令、捆綁和使用者撰寫的 [skills](https://code.claude.com/docs/zh-TW/skills.md)，以及由 [plugins](https://code.claude.com/docs/zh-TW/plugins/overview.md) 和 [MCP servers](https://code.claude.com/docs/zh-TW/mcp.md#use-mcp-prompts-as-commands) 貢獻的指令。並非所有內建指令對每個使用者都可見，因為某些指令取決於您的平台或方案，而且 [某些可用指令在設計上隱藏在選單之外](https://code.claude.com/docs/zh-TW/commands.md#how-the-command-menu-matches-what-you-type)，當您輸入其完整名稱時會執行。

在 [全螢幕呈現](https://code.claude.com/docs/zh-TW/fullscreen.md#use-the-mouse) 中，`/` 指令和 `@` 檔案建議清單也會回應滑鼠：懸停會反白一列，點擊會接受它。

請參閱 [指令參考](https://code.claude.com/docs/zh-TW/commands.md) 以取得 Claude Code 中包含的完整指令清單。

### 在提示中途完成指令

指令完成也適用於提示的中途：在空格後輸入 `/`，然後輸入名稱的前幾個字母，如 `run the tests, then /com`。只有名稱以這些字母開頭的指令才會符合，因此檔案路徑（例如 `/tmp/notes.md`）不會保持清單開啟。Claude Code 只有在指令 [開始您的訊息](https://code.claude.com/docs/zh-TW/commands.md) 時才會自行執行指令。

* **在 [全螢幕呈現](https://code.claude.com/docs/zh-TW/fullscreen.md) 中**：當您輸入時，符合項會以清單形式開啟，沒有反白的列，因此 `Enter` 仍會按輸入的方式傳送您的提示。按 `Tab` 以插入最上面的符合項，或使用方向鍵和 `Enter` 選擇一列。
* **在全螢幕外**：最上面符合項的其餘部分會在您的游標處顯示為幽靈文字，當有更多指令符合時會顯示計數（例如 `+2`）。按 `Tab` 以插入唯一的符合項，或在有多個符合項時開啟清單，然後使用方向鍵和 `Enter` 選擇一列。

在兩個呈現器中，在裸露的中途 `/` 上按 `Tab` 以列出每個指令。

外掛 skill 也會在其裸露名稱上符合，因此 `/deploy` 會找到名為 `myplugin:deploy-app` 的 skill。當您插入符合項時，Claude Code 會寫入完整的 `/myplugin:deploy-app`。

## Vim 編輯器模式

透過 `/config` → Editor mode 啟用 vim 風格的編輯。

Claude Code 會在您使用 `Ctrl+O` 切換[文字記錄檢視器](#transcript-viewer)或開啟和關閉面板（例如 `/config`）時保留您的 vim 模式和游標位置。如果您在 NORMAL 模式下離開提示，當您返回時它仍然處於 NORMAL 模式，游標位置與您離開時相同。

### 模式切換

| 命令 | 動作 | 來自模式 |
| :- | :- | :- |
| `Esc` 或 `Ctrl+[` | 進入 NORMAL 模式。在使用 Kitty 鍵盤協議的終端中，`Ctrl+[` 需要 v2.1.242 或更新版本 | INSERT、VISUAL |
| `i` | 在游標前插入 | NORMAL |
| `I` | 在行首插入 | NORMAL |
| `a` | 在游標後插入 | NORMAL |
| `A` | 在行尾插入 | NORMAL |
| `o` | 在下方開啟新行 | NORMAL |
| `O` | 在上方開啟新行 | NORMAL |
| `v` | 開始字元式視覺選擇 | NORMAL |
| `V` | 開始行式視覺選擇 | NORMAL |

### 重新對應 INSERT 模式快捷鍵序列

[`vimInsertModeRemaps`](https://code.claude.com/docs/zh-TW/settings-reference#viminsertmoderemaps) 設定會將兩個按鍵的 INSERT 模式序列對應到 Escape，因此像 `jj` 這樣的對應會讓您返回 NORMAL 模式。

以下 `~/.claude/settings.json` 範例會開啟 vim 模式並將 `jj` 對應到 Escape：

```json theme={null}
{
  "editorMode": "vim",
  "vimInsertModeRemaps": { "jj": "<Esc>" }
}
```

每個鍵恰好是按順序輸入的兩個可列印字元，而 `"<Esc>"` 是唯一支援的目標。具有不同長度或目標的項目會被忽略。

輸入序列的第一個字元會正常插入。在一秒內按下第二個字元會移除該待處理字元並切換到 NORMAL 模式，在您的輸入中不留下任何字元。在一秒的時間窗口之後，或如果按下不同的按鍵，兩個字元都會保留為字面文字，因此您仍然可以透過在兩個按鍵之間暫停來輸入包含該序列的單字。

Claude Code 只會從您的使用者設定檔、`--settings` 旗標和[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)讀取此設定。專案的 `.claude/settings.json` 或 `.claude/settings.local.json` 中的項目會被忽略，因此簽出的儲存庫無法重新對應您的快捷鍵。

### 導覽（NORMAL 模式）

| 命令 | 動作 |
| :- | :- |
| `h`/`j`/`k`/`l` | 向左/向下/向上/向右移動 |
| `Space` | 向右移動 |
| `w` | 下一個單字 |
| `e` | 單字結尾 |
| `b` | 上一個單字 |
| `0` | 行首 |
| `$` | 行尾 |
| `^` | 第一個非空白字元 |
| `gg` | 輸入開始 |
| `G` | 最後一行的開頭 |
| `f{char}` | 跳到目前行上下一個字元出現位置 |
| `F{char}` | 跳到目前行上上一個字元出現位置 |
| `t{char}` | 跳到目前行上下一個字元出現位置之前 |
| `T{char}` | 跳到目前行上上一個字元出現位置之後 |
| `;` | 重複上一個 f/F/t/T 動作 |
| `,` | 反向重複上一個 f/F/t/T 動作 |
| `%` | 跳到對應的 `()`、`[]` 或 `{}` 括號；當游標不在括號上時，會從目前行上的下一個括號開始。需要 Claude Code v2.1.301 或更新版本 |
| `/` | 開啟反向歷史搜尋，與 `Ctrl+R` 相同。空搜尋提示會顯示提示：按 `Esc` 然後 `i` 然後 `/` 以改為開啟命令選單 |

> [!NOTE]
>
> 在 vim NORMAL 模式中，如果游標位於輸入的開始或結尾且無法進一步移動，`j`/`k` 和 `↑`/`↓` 會改為導覽命令歷史。在空提示上按 `←` 會從 NORMAL 模式以及 INSERT 模式開啟 [agent 檢視](https://code.claude.com/docs/zh-TW/agent-view.md)。

### 編輯（NORMAL 模式）

| 命令 | 動作 |
| :- | :- |
| `x` | 刪除字元 |
| `r{char}` | 將游標下的字元取代為 `{char}` |
| `dd` | 刪除行 |
| `D` | 刪除到行尾 |
| `dw`/`de`/`db` | 刪除單字/到結尾/向後 |
| `df{char}`/`dt{char}` | 刪除到並包括，或刪除到目前行上下一個字元出現位置之前 |
| `dj`/`dk` | 刪除目前行和下方或上方的行 |
| `dgg`/`dG` | 從目前行刪除到第一行或最後一行 |
| `d0`/`c0`/`y0` | 從游標刪除、變更或複製回到行首。需要 Claude Code v2.1.281 或更新版本 |
| `d%`/`c%`/`y%` | 從游標刪除、變更或複製到 `%` 所跳至的括號（包括該括號）。需要 Claude Code v2.1.301 或更新版本 |
| `cc` | 變更行 |
| `C` | 變更到行尾 |
| `cw`/`ce`/`cb` | 變更單字/到結尾/向後 |
| `s` | 替換字元：刪除游標下的字元並進入 INSERT 模式 |
| `S` | 替換行：清除行並進入 INSERT 模式 |
| `yy`/`Y` | 複製行 |
| `yw`/`ye`/`yb` | 複製單字/到結尾/向後 |
| `p` | 在游標後貼上 |
| `P` | 在游標前貼上 |
| `>>` | 縮排行 |
| `<<` | 取消縮排行 |
| `J` | 合併行 |
| `u` | 復原 |
| `.` | 重複上一個變更 |

### 文字物件（NORMAL 模式）

文字物件可與運算子（例如 `d`、`c` 和 `y`）搭配使用：

| 命令 | 動作 |
| :- | :- |
| `iw`/`aw` | 內部/周圍單字 |
| `iW`/`aW` | 內部/周圍 WORD（空白分隔） |
| `i"`/`a"` | 內部/周圍雙引號 |
| `i'`/`a'` | 內部/周圍單引號 |
| `i(`/`a(` | 內部/周圍括號 |
| `i[`/`a[` | 內部/周圍方括號 |
| `i{`/`a{` | 內部/周圍大括號 |

### 視覺模式

按 `v` 進行字元式選擇或按 `V` 進行行式選擇。動作會延伸選擇，運算子會直接作用於它。

| 命令 | 動作 |
| :- | :- |
| `d`/`x` | 刪除選擇 |
| `y` | 複製選擇 |
| `c`/`s` | 變更選擇 |
| `p` | 用暫存器內容取代選擇 |
| `r{char}` | 將每個選定的字元取代為 `{char}` |
| `~`/`u`/`U` | 切換、小寫或大寫選擇 |
| `>`/`<` | 縮排或取消縮排選定的行 |
| `J` | 合併選定的行 |
| `o` | 交換游標和錨點 |
| `iw`/`aw`/`i"`/… | 選擇文字物件 |
| `v`/`V` | 在字元式和行式之間切換，或退出 |

不支援使用 `Ctrl+V` 的區塊式視覺模式。

### 在 vim 模式中取消問題

當您在 [Claude 提出的問題](https://code.claude.com/docs/zh-TW/tools-reference.md#askuserquestion-tool-behavior)的 `Other` 列中輸入自己的答案時，按兩次 `Esc` 即可取消該問題。

若要改為只按一個鍵就取消，請[綁定另一個鍵來取消問題](https://code.claude.com/docs/zh-TW/keybindings.md#cancel-a-question-with-one-key-press)。

## 命令歷史

Claude Code 會保留您輸入的提示詞歷史，並且向上箭頭可以回憶同一專案過去工作階段的提示詞：

* 輸入歷史按工作目錄儲存
* 執行 `/clear` 會開始新的工作階段：回憶時會先列出新工作階段的提示詞，然後是較早工作階段的提示詞。前一個工作階段的對話會被保留，可以繼續進行。
* 連續提交相同的提示詞兩次只會記錄一個歷史項目，因此按向上箭頭會跳到前一個不同的提示詞
* 當您回憶包含貼上文字的提示詞時，Claude Code 會在您重新提交時再次傳送完整的貼上內容。如果內容已被[自動清理](https://code.claude.com/docs/zh-TW/claude-directory.md#cleaned-up-automatically)，Claude Code 不會傳送字面上的 `[Pasted text #N]` 字串；請參閱[貼上大型內容](https://code.claude.com/docs/zh-TW/terminal-config.md#paste-large-content)以了解提示詞會發生什麼情況
* 使用 `!` 的歷史展開預設為停用

### 找回已清除的草稿

若要找回您以 `Ctrl+C` 清除的草稿，請按 `Up`，可以在清除後立即按，也可以在傳送訊息或命令之後按：

* **清除草稿後立即找回**：在提示詞仍為空白時按一次 `Up`。需要 Claude Code v2.1.288 或更新版本。
* **傳送訊息或命令之後找回**：按 `Up` 回到該草稿。Claude Code 會為目前的工作階段保留最近十個已清除的草稿，包含其貼上的文字和圖片，並在您結束時捨棄它們。需要 Claude Code v2.1.292 或更新版本。

### 使用 Ctrl+R 進行反向搜尋

按 `Ctrl+R` 以互動方式搜尋您的命令歷史。在[全螢幕渲染](https://code.claude.com/docs/zh-TW/fullscreen.md)中，`Ctrl+R` 會改為開啟搜尋對話框。在對話框中輸入以篩選，並按 `Up` 和 `Down` 在符合項目清單中移動，預覽窗格會顯示反白符合項目的開頭部分。

在對話框中，按 `Ctrl+S` 可在此工作階段、此專案和所有專案之間循環切換範圍。按 `Enter` 或 `Tab` 將符合項目放在提示詞輸入中，或按 `Esc` 取消。下面的步驟說明傳統渲染器的內嵌搜尋：

1. **開始搜尋**：按 `Ctrl+R` 啟動反向歷史搜尋
2. **輸入查詢**：輸入要在先前命令中搜尋的文字。目前的符合項目會出現在提示詞輸入中。
3. **導覽符合項目**：再次按 `Ctrl+R` 循環瀏覽較舊的符合項目
4. **搜尋範圍**：內嵌搜尋始終搜尋來自所有專案的提示詞
5. **接受符合項目**：
   * 按 `Tab` 或 `Esc` 接受目前的符合項目並繼續編輯
   * 按 `Enter` 接受並立即執行命令
6. **取消搜尋**：
   * 按 `Ctrl+C` 取消並還原您的原始輸入
   * 在空搜尋上按 `Backspace` 取消

接受符合項目或取消搜尋會立即生效，即使 Claude Code 仍在載入歷史。

## 背景 Bash 命令

Claude Code 支援在背景執行 Bash 命令，讓您可以在長時間執行的程序進行時繼續工作。

### 背景執行的運作方式

當 Claude Code 在背景執行命令時，它會非同步執行該命令並立即傳回背景工作 ID。Claude Code 可以在命令繼續在背景執行時回應新的提示。

若要在背景執行命令，您可以：

* 提示 Claude Code 在背景執行命令
* 按 `Ctrl+B` 將一般 Bash 工具叫用移至背景。Tmux 使用者必須按 `Ctrl+B` 兩次，因為 tmux 的前置鍵。

當命令在完成前達到逾時時，Claude Code 會自動[將其移至背景](https://code.claude.com/docs/zh-TW/tools-reference.md#foreground-commands-that-move-to-the-background)，而不是停止它，除非命令以 `sleep` 開頭。如果您已使用 [`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS`](https://code.claude.com/docs/zh-TW/env-vars#variables) 關閉背景命令，或透過以 [bare 模式](https://code.claude.com/docs/zh-TW/headless.md#start-faster-with-bare-mode)啟動，命令會在逾時時停止。若要變更逾時，請設定 [Bash 逾時環境變數](https://code.claude.com/docs/zh-TW/tools-reference.md#timeout-and-output-limits)。

**主要功能：**

* 輸出會寫入檔案，Claude 可以使用 Read 工具擷取它
* 背景工作具有唯一的 ID，用於追蹤和輸出擷取
* 當 Claude Code 結束時，背景工作會自動清理。在 macOS 和 Linux 上，當您從 [`/tasks`](https://code.claude.com/docs/zh-TW/commands) 停止背景工作或 Claude Code 在結束時停止它時，從工作的 shell 分離的程序（例如在 `setsid` 或 `timeout` 下啟動的程序）也會停止
* 如果您將工作階段放在背景而不是結束它，您的背景工作會繼續在背景工作階段中執行。請參閱[將執行中的工作階段放在背景](https://code.claude.com/docs/zh-TW/agent-view.md#from-inside-a-session)
* 背景工作如果輸出超過 5GB，會自動終止，stderr 中會有說明原因的備註
* 在 macOS 和 Linux 上，當作業系統回報嚴重記憶體壓力時，Claude Code 會停止您執行中的背景任務，前提是工作階段已閒置至少 30 分鐘，且沒有任何回合或 subagent 正在執行
  * [偵錯日誌](https://code.claude.com/docs/zh-TW/debug-your-config.md)會說明為什麼任務被停止，或為什麼壓力事件讓它們繼續執行
  * 將 [`CLAUDE_CODE_DISABLE_BG_SHELL_PRESSURE_REAP`](https://code.claude.com/docs/zh-TW/env-vars) 設定為 `1` 以關閉記憶體壓力停止
* 在您從終端機、桌面應用程式或 VS Code 擴充功能操作的本機工作階段中，背景命令沒有時間限制。在無人看管執行的工作階段中（例如 `-p` 執行或雲端工作階段），Claude Code 會在背景命令達到其[時間限制](https://code.claude.com/docs/zh-TW/tools-reference.md#time-limit-for-background-commands)時停止它
* 由前景[子代理](https://code.claude.com/docs/zh-TW/sub-agents.md#run-subagents-in-foreground-or-background)啟動的背景命令在該子代理的執行結束時結束，無論是完成、失敗或被中斷；請參閱工具參考中的[背景命令停止時](https://code.claude.com/docs/zh-TW/tools-reference.md#when-a-background-command-stops)

若要關閉背景命令，請將 [`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS`](https://code.claude.com/docs/zh-TW/env-vars#variables) 環境變數設定為 `1`。設定後，您也會失去 `Ctrl+B` 快捷鍵以及[其他背景功能](https://code.claude.com/docs/zh-TW/env-vars.md#variables)，例如[在背景執行 skill](https://code.claude.com/docs/zh-TW/skills.md#run-skills-in-a-subagent)。以 [bare 模式](https://code.claude.com/docs/zh-TW/headless.md#start-faster-with-bare-mode)啟動也有相同的效果。

**常見的背景命令：**

* 建置工具（webpack、vite、make）
* 套件管理員（npm、yarn、pnpm）
* 測試執行器（jest、pytest）
* 開發伺服器
* 長時間執行的程序（docker、terraform）

### 使用 `!` 前置詞的 Shell 模式

透過在輸入前加上 `!` 直接執行 shell 命令，無需透過 Claude：

```bash theme={null}
! npm test
! git status
! ls -la
```

Shell 模式：

* 將命令及其輸出新增至對話內容
* 顯示即時進度和輸出
* 支援相同的 `Ctrl+B` 背景執行，用於長時間執行的命令
* 不需要 Claude 解釋或核准命令
* 支援歷史記錄型自動完成：輸入部分命令並按 `Tab` 以從目前專案中的先前 `!` 命令完成
* 支援即時檔案路徑自動完成：輸入包含正斜線的 token（例如 `./src/` 或 `~/`）以查看相符檔案和目錄的下拉式清單，然後按 `Tab` 以接受。在 Windows 上也使用正斜線；下拉式清單由 `/` 觸發，而不是 `\`
* 在空提示上按 `Escape`、`Backspace` 或 `Ctrl+U` 結束
* 將以 `!` 開頭的文字貼到空提示中會自動進入 shell 模式，符合輸入的 `!` 行為

除非您的工作階段是[嚴格沙箱模式](https://code.claude.com/docs/zh-TW/sandboxing.md#turn-off-the-retry-with-strict-sandbox-mode)下列出的其中一個，否則您在 shell 模式中輸入的命令會在[沙箱](https://code.claude.com/docs/zh-TW/sandboxing.md)外執行，即使您已啟用沙箱機制，因為沙箱適用於 Claude 執行的命令。

一旦命令輸出進入逐字稿，Claude 會自動回應，因此您可以執行 `! npm test` 並取得失敗的說明，無需第二個提示詞。回應成本與傳送一般提示詞相同。若要改為將輸出新增至內容而不回應，請在 `settings.json` 中將 [`respondToBashCommands`](https://code.claude.com/docs/zh-TW/settings-reference#respondtobashcommands) 設定為 `false`。

## 在 Claude 工作時排隊傳送訊息

在 Claude 工作時輸入訊息並按 `Enter`。Claude Code 會將訊息排隊而不是中斷該回合，並在對話中列出排隊的項目，直到傳送為止。您可以用相同的方式排隊 `!` [shell 命令](#shell-mode-with-prefix)和大多數 [命令](https://code.claude.com/docs/zh-TW/commands.md)，除了 `/status` 等 Claude Code 會在您傳送時立即執行的命令。

已傳送和排隊的訊息會以灰色顯示，直到 Claude 開始回應它們為止，因此您可以看出 Claude 還沒有開始處理哪些訊息。

如果您從 [已連線的 IDE](https://code.claude.com/docs/zh-TW/vs-code.md#the-built-in-ide-mcp-server) 排隊帶有選取項目的訊息，它會保留您按下 `Enter` 時的選取項目，無論您之後選取什麼。

### Claude Code 何時傳送您排隊的內容

排隊項目何時到達 Claude 取決於您排隊的內容。

* 訊息：如果您在 Claude 執行工具呼叫時排隊訊息，Claude Code 會在這些工具呼叫完成後立即將其傳遞給 Claude，在同一回合內。當回合結束時仍有訊息排隊，它們會在沒有另一次按鍵的情況下按照您輸入的順序傳出
* 命令和 shell 命令：Claude Code 會保留它們直到回合結束，然後逐個執行，保持您排隊的順序

若要在不等待的情況下傳送您排隊的內容，請按 `Ctrl+Enter`。您排隊的訊息會立即傳出，如果您已輸入草稿，您的草稿會排隊在後面。需要 Claude Code v2.1.275 或更新版本。

如果您在訊息前面排隊了 `!` shell 命令，該快捷鍵會中斷回合。否則，回合發生的情況取決於您按下快捷鍵時 Claude 正在執行的操作：

* 執行 shell 命令、subagent 或其他可以移至 [背景](#background-bash-commands)的工作：該工作會移至背景並繼續執行，Claude 會在同一回合中讀取您的訊息
* 僅撰寫回應，或執行無法移至背景的操作：Claude Code 會中斷回合並在下一步傳送您的訊息。在 v2.1.281 之前，該快捷鍵在兩種情況下都會中斷回合

在 [shell 模式](#shell-mode-with-prefix)中，該快捷鍵只會排隊您的命令。在不回報擴充按鍵的終端機中，`Ctrl+Enter` 會以純 `Enter` 的形式到達並排隊草稿；`Ctrl+X Ctrl+S` 在任何終端機中都有效。兩個快捷鍵都是 [`chat:sendNow` 動作](https://code.claude.com/docs/zh-TW/keybindings#chat-actions)的繫結。

按 `Esc` 以中斷回合而不提交您的草稿。Claude Code 會保留您排隊的內容並立即傳送。

Claude Code 會在您傳送某些命令時立即執行它們，而不是排隊，其中包括 `/model`、`/effort` 和 `/fast`。這三個命令各自改變一個設定：模型、effort 等級或快速模式。Claude Code 是否將新設定應用於 Claude 已在進行的回合，或僅從您的下一回合開始，因命令而異：

* [`/model`](https://code.claude.com/docs/zh-TW/model-config#setting-your-model)：一旦您確認 [快取警告](https://code.claude.com/docs/zh-TW/prompt-caching.md#switching-models)（如果 Claude Code 顯示的話），Claude Code 會從該回合中它進行的下一個請求開始使用新模型
* `/effort`：您傳送的下一則訊息會以新等級執行。若要 [在 Claude 已在進行的回合中開始套用](https://code.claude.com/docs/zh-TW/model-config.md#when-a-new-effort-level-starts)，請在 Claude 執行工具呼叫時排隊一則訊息
* [`/fast`](https://code.claude.com/docs/zh-TW/fast-mode#toggle-fast-mode)：Claude Code 保留回合開始時啟用的快速模式設定，因此您的速度變更從您的下一回合開始應用。如果您目前的模型不支援快速模式，開啟它也會 [切換您的模型](https://code.claude.com/docs/zh-TW/prompt-caching.md#turning-on-fast-mode)，Claude Code 會從該回合中的下一個請求開始使用新模型

### 在有排隊訊息時將工作階段移至背景

當您 [按下 `←`](https://code.claude.com/docs/zh-TW/agent-view#switch-sessions-without-leaving-the-terminal) 後工作階段移至背景時，您已排隊的訊息會隨之移動。Claude 會在背景中按照您傳送的順序讀取它們。

命令和 `!` shell 命令無法移動，某些訊息也無法移動，例如附加了 [IDE 選取項目](https://code.claude.com/docs/zh-TW/vs-code.md#the-built-in-ide-mcp-server)的訊息。如果您在其中任何一個仍在排隊時按下 `←`，工作階段會留在前景，並出現以 `Cannot open agents` 開頭的通知。若要將工作階段移至背景，請先將該項目移出佇列，然後再次按下 `←`：

* **命令和 `!` shell 命令**：等待它們在回合結束時執行，或 [取回它們](#take-back-what-you-queued)並清除輸入框。當有其他任何項目在排隊時，您無法取回 `!` shell 命令，因此請等待它們執行。
* **無法移動的訊息**：等待 Claude 讀取它們

### 取回您排隊的內容

從輸入框的第一行按 `Up` 以取回排隊的訊息和命令。Claude Code 會將它們從佇列中移除並放入輸入框，每行一個，位於您已輸入的任何文字之前。編輯文字並按 `Enter` 以將其作為一個項目再次排隊，或清除輸入框以捨棄它。

Claude Code 只有在輸入框為空且您沒有其他排隊項目時才會取回排隊的 shell 命令，並在執行時將輸入框切換到 shell 模式。否則它會將它們保留在佇列中，以其 `!` 前綴列出，並在回合結束後執行它們。

如果您在 `←` [等待將工作階段移至背景](https://code.claude.com/docs/zh-TW/agent-view.md#switch-sessions-without-leaving-the-terminal)時取回排隊的文字，該文字會保留在輸入框中，且 Claude Code 會取消切換。如果您在工作階段移動的那一刻取回文字，該文字會隨前景畫面一起消失：它並未被傳送。您取回的每則訊息都會在 [命令歷史記錄](#command-history)中儲存為獨立的項目。若要復原其中一則，請重新開啟該工作階段，並在沒有任何排隊項目的空白提示詞上按 `Up`。

## 提示建議

當您首次開啟工作階段時，Claude Code 會在提示輸入中顯示一個灰色的範例命令，以幫助您開始。它從您專案的 git 歷史記錄中選擇此範例，因此該範例反映了您最近正在處理的檔案。

Claude 回應後，Claude Code 可以根據您的對話歷史記錄建議您的下一個提示，例如多部分請求的後續步驟或工作流程的自然延續。

* 按 `Tab` 或 `Right arrow` 將建議放入提示輸入中，然後按 `Enter` 提交
* 開始輸入以關閉它

Claude Code 使用背景請求產生每個這些下一個提示建議，該請求會計入您方案的使用限制或您的 API 成本。因為它會重複使用對話的提示快取，所以主要是快取讀取加上少數輸出權杖，因此額外成本最少。

### 當 Claude Code 跳過建議時

在互動模式中，Claude Code 預設會關閉提示建議，並在 `/config` 中隱藏 **Prompt suggestions** 切換，該切換位於[不會擷取功能旗標的工作階段](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)中，例如第三方提供者上的工作階段或透過 Claude 應用程式閘道的工作階段，以及在[安裝或升級後的第一個工作階段](https://code.claude.com/docs/zh-TW/env-vars.md#first-session-after-an-install-or-upgrade)中，其旗標尚未到達。

Claude Code 也會在多種情況下跳過個別建議，包括：

* 提示快取為冷狀態，以避免不必要的成本
* 在對話的第一輪之後，在某些工作階段中
* 前一個回應以錯誤結束
* 當您處於 Plan Mode 時
* 您的帳戶接近或已達到用量上限。若要讓此跳過行為在您達到上限之前不生效，請將 [`CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION`](https://code.claude.com/docs/zh-TW/env-vars) 設定為 `true`。在 v2.1.238 之前，即使將變數設定為 `true`，Claude Code 也會在接近上限時跳過建議
* 在[代理團隊](https://code.claude.com/docs/zh-TW/agent-teams.md)中，預設情況下在隊友的工作階段中。主導者的工作階段會顯示建議

通知 `Showing fewer prompt suggestions · use one to bring them back` 表示 Claude Code 顯示建議的頻率降低了，因為您連續多次未使用建議。若要恢復為一般頻率，請使用一個建議，或將 [`CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION`](https://code.claude.com/docs/zh-TW/env-vars) 設定為 `true`。

在列印模式中，Claude Code 預設不會產生建議。使用 [`--prompt-suggestions`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 搭配 `-p "<prompt>" --output-format stream-json --verbose` 讓 Claude Code 在每個產生建議的輪次後發出 `prompt_suggestion` 訊息。產生器在此也會跳過非常短的對話和冷提示快取，因此單一短 `-p` 查詢可能不會發出任何建議。

### 關閉提示建議

若要完全停用提示建議，請使用以下任一方法：

* 在 `/config` 中關閉 **Prompt suggestions**
* 在您的設定檔中將 [`promptSuggestionEnabled`](https://code.claude.com/docs/zh-TW/settings-reference#promptsuggestionenabled) 設定為 `false`
* 將 [`CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION`](https://code.claude.com/docs/zh-TW/env-vars) 環境變數設定為 `false`，其優先於設定：
  ```bash theme={null}
  export CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION=false
  ```

若要在整個組織中關閉提示建議，請在[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)中將 `promptSuggestionEnabled` 設定為 `false`。同時在受管 [`env`](https://code.claude.com/docs/zh-TW/settings-reference#env) 金鑰下將 `CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION` 設定為 `false`，以便使用者無法使用自己的環境變數重新啟用它們。

## You should know 建議

「You should know」會找出一件您應該知道但可能遺漏的事情，例如 Claude 在未說明的情況下所做的取捨，或是可能有誤的結果。找到時，它會在提示詞輸入框上方顯示一則簡短的提醒：

```text theme={null}
✦ Heads up · There was a change to how folder sharing starts in June, which may have bumped usage metrics artificially.
  1: Learn more   2: Knew this already   0: Dismiss
```

這是 Claude Code 的[內建 mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md#mods-built-into-claude-code) 之一，也就是內建於 Claude Code 中、預設為關閉的外掛。需要 Claude Code v2.1.287 或更新版本。

啟用期間，當 Claude 處理較長的任務時，一個側邊 agent 會不時重新閱讀對話。側邊 agent 是發送至同一模型的獨立請求，且沒有任何工具，因此無法讀取檔案、執行命令，也無法改變 Claude 的行為。

如果您的組織可使用此 mod，當您以 claude.ai 帳戶或 Console API 金鑰直接連線至 Claude API 時，`/plugin` 會列出它。若您透過 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)或 [Claude apps 閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)連線，或從 [`apiKeyHelper`](https://code.claude.com/docs/zh-TW/settings-reference#apikeyhelper) 取得金鑰，則不會列出。即使是直接連線，以下工作階段也不會列出它：

* [不擷取此 mod 所依賴之功能旗標](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)的工作階段，例如設定了 `DISABLE_TELEMETRY` 的工作階段
* 旗標尚未送達的[安裝或升級後的第一個工作階段](https://code.claude.com/docs/zh-TW/env-vars.md#first-session-after-an-install-or-upgrade)

若要啟用，請在 Claude Code 提示詞中執行：

```text theme={null}
/plugin enable cc-plugin-you-should-know@builtin
```

在 `/plugin` 未列出此 mod 的情況下，啟用命令會回應 `Plugin "cc-plugin-you-should-know@builtin" is not installed in this project`。

### 檢查的費用

此 mod 啟用期間，檢查是發送至您工作階段所使用之同一模型的背景請求，並會計入您方案的用量上限或 API 費用。每次檢查都會傳送 Claude 上下文中已有的內容，也就是截至目前為止的對話及其工具結果，接著是此 mod 本身的指令以及您近期提醒的文字。對話部分會以與 Claude 自身下一個請求相同的條件，從工作階段的[提示快取](https://code.claude.com/docs/zh-TW/prompt-caching.md)中讀取。指令（長達數千個 token）以及側邊 agent 的回覆，則在每次檢查時全額計費。

若要觀察檢查的進行，請在啟動 Claude Code 之前，於您的 shell 中設定 [`CLAUDE_CODE_YOU_SHOULD_KNOW_DEBUG=1`](https://code.claude.com/docs/zh-TW/env-vars)。

### 回應提醒

在空白的提示詞輸入框中單獨輸入選項的數字。提醒提供以下選項：

* **Learn more**：在提醒下方開啟一段簡短說明，並附有其自身的選項：
  * **Understood**：關閉說明並將該主題標記為已知
  * **Chat in main session**：將提醒引用到您的提示詞輸入框中，以便您加上問題並傳送給 Claude
  * **Dismiss**：關閉說明，但不將該主題標記為已知
* **Knew this already**：關閉提醒並將該主題標記為已知。
* **Dismiss**：關閉提醒。

除非您使用 **Chat in main session** 傳送提醒，否則主 agent 不會看到它。

Claude Code 會將您近期的提醒以及您標記為已知的主題，保存在 `~/.claude/plugins/store/` 下一個名稱以 `cc-plugin-you-should-know` 開頭的檔案中。每次檢查（無論在此工作階段或之後的工作階段）都會將這些內容列給側邊 agent，作為不應重複的項目。當該檔案經過 [`cleanupPeriodDays`](https://code.claude.com/docs/zh-TW/settings-reference#cleanupperioddays) 都沒有任何工作階段讀取或寫入時，Claude Code 會將其刪除。若要更早清除，請在沒有工作階段執行時刪除該檔案。

### 關閉 You should know

若要關閉 You should know，請使用以下任一方式：

* 在 Claude Code 提示詞中執行 `/plugin disable cc-plugin-you-should-know@builtin`，或從 `/plugin` 的 **Installed** 分頁將其關閉
* 在未先開啟 **Learn more** 的情況下對提醒選擇 **Dismiss** 後，在 `Dismissed.` 那一行選擇 **Turn off suggestions**，該行會在 20 秒後消失

## Emoji 快捷代碼

在提示詞輸入中輸入 `:` 後跟 emoji 快捷代碼以插入 emoji。

* 輸入完整的快捷代碼，例如 `:heart:`，Claude Code 會在您輸入結尾的 `:` 時立即將其替換為 ❤️
* 輸入 `:` 加上至少兩個字元的名稱，例如 `:hea`，以開啟建議彈出視窗，然後按 `Tab` 或 `Enter` 以插入突出顯示的 emoji

快捷代碼必須在輸入的開始或空格後開始，因此單字或 URL 內的 `:` 不會開啟建議。

若要關閉此功能，請在 `settings.json` 中將 [`emojiCompletionEnabled`](https://code.claude.com/docs/zh-TW/settings-reference#emojicompletionenabled) 設定為 `false`。這會停用建議彈出視窗和內嵌替換。

## 在輸入時檢查拼寫

Claude Code 可以在您輸入時在提示輸入框中為拼寫錯誤的單詞加上底線。它只檢查輸入框中的文字，從不檢查 Claude 的回覆或您的檔案。它也不會在輸入框處於[殼層模式](#shell-mode-with-prefix)、`Ctrl+R` 歷史記錄搜尋或[語音聽寫](https://code.claude.com/docs/zh-TW/voice-dictation.md)時檢查任何內容。

拼寫檢查預設為關閉，Claude Code 在[螢幕閱讀器模式](https://code.claude.com/docs/zh-TW/accessibility.md)中不檢查任何內容。需要 Claude Code v2.1.235 或更新版本。

### 先決條件

* 安裝 [aspell](https://github.com/GNUAspell/aspell)、[hunspell](https://github.com/hunspell/hunspell) 或 [ispell](https://en.wikipedia.org/wiki/Ispell)，並確保它在您的 `PATH` 上。Claude Code 在每個平台上執行它找到的前三個中的第一個，包括套件管理員在 Windows 上安裝的 `.cmd` shim。
* 若要檢查程式是否在您的 `PATH` 上，請在您的終端機中執行 `aspell --version`、`hunspell --version` 或 `ispell -v`。「command not found」錯誤表示它還不在您的 `PATH` 上。

### 開啟或關閉拼寫檢查

Claude Code 從三個地方讀取 [`spellcheck`](https://code.claude.com/docs/zh-TW/settings-reference#spellcheck) 設定，並在專案的 `.claude/settings.json` 和 `.claude/settings.local.json` 中忽略它。從您使用的任何一個地方開啟它：

> [tab] 使用者設定
>
> 將 `spellcheck` 新增到 `~/.claude/settings.json`。它適用於您開啟的每個專案，就像您的其他[使用者設定](https://code.claude.com/docs/zh-TW/settings.md#where-settings-live)一樣：
>
> ```json theme={null}
> {
>   "spellcheck": { "enabled": true }
> }
> ```

> [tab] 命令列
>
> 將 `spellcheck` 儲存在 JSON 檔案中，例如 `spellcheck.json`：
>
> ```json theme={null}
> {
>   "spellcheck": { "enabled": true }
> }
> ```
>
> 然後將檔案傳遞給 `--settings`。它僅適用於該工作階段：
>
> ```bash theme={null}
> claude --settings spellcheck.json
> ```

> [tab] 受管設定
>
> 將 `spellcheck` 新增到您組織的[受管設定來源](https://code.claude.com/docs/zh-TW/permissions.md#managed-settings)之一。它適用於接收這些設定的每個使用者，他們無法將其關閉：
>
> ```json theme={null}
> {
>   "spellcheck": { "enabled": true }
> }
> ```

若要檢查拼寫檢查是否開啟，請輸入一個拼寫錯誤的單詞和一個空格。Claude Code 會為該單詞加上底線。如果沒有，請參閱[當 Claude Code 不加任何底線時](#when-claude-code-underlines-nothing)。若要再次關閉拼寫檢查，請在同一位置將 `enabled` 設定為 `false`，或移除 `spellcheck`。

若要選擇 Claude Code 執行的三個程式中的哪一個、它使用的字典或底線顏色，請在同一位置在 `enabled` 旁邊新增以下任何欄位：

* `checker`：`aspell`、`hunspell` 或 `ispell`。Claude Code 不會從您命名的檢查器回退，並將任何其他值視為 `auto`。
* `language`：您的檢查器形式中的字典名稱，例如 `en_GB`。Claude Code 忽略任何不是純字典名稱的值，例如路徑或包含空格的名稱，檢查器使用其預設字典。
* `color`：顏色名稱，例如 `yellow`，或 `#rrggbb`、`#rgb`、`rgb(r,g,b)`、`ansi256(n)` 或 `ansi:<name>` 值。Claude Code 預設使用您主題的錯誤顏色，對於任何它無法識別的值也是如此。

例如，此 `spellcheck` 設定使用其 `en_GB` 字典執行 hunspell，並以黃色為單詞加上底線。它在 `~/.claude/settings.json`、您傳遞給 `--settings` 的檔案和受管設定中的工作方式相同：

```json theme={null}
{
  "spellcheck": {
    "enabled": true,
    "checker": "hunspell",
    "language": "en_GB",
    "color": "yellow"
  }
}
```

如果三個地方中有多個具有 `spellcheck` 設定，Claude Code 只使用其中一個：受管設定優先，然後是 `--settings`，然後是使用者設定。它不會合併來自兩個地方的欄位。例如，當 `--settings` 設定 `spellcheck` 時，您使用者設定中的 `language` 無效。

### Claude Code 加底線的內容

在您暫停輸入後不久，Claude Code 會為字典不知道的單詞加上底線。它在您仍在輸入時不理會該單詞，直到您超過它，並且它永遠不會改變您的文字。它也會跳過看起來像程式碼的文字：

* 命令，例如 `/help`、`@` 提及、URL、檔案路徑和旗標，例如 `--verbose`
* 包含數字、底線或第一個字母後大寫字母的單詞，以及反引號中的文字

Claude Code 也會跳過中文、日文、韓文、泰文、寮文、高棉文和緬甸文文字。

Claude Code 沒有自己的單詞列表：當您的檢查器說某個單詞拼寫錯誤時，它就是拼寫錯誤。若要停止 Claude Code 為某個單詞加底線，請按照檢查器自己的文件將該單詞新增到您的檢查器的個人字典。Claude Code 在您重新啟動它後會選取新單詞。

### 當 Claude Code 不加任何底線時

當 Claude Code 無法保持檢查器執行時，它不加任何底線：

* 未安裝檢查器，或您在 `checker` 中命名的檢查器遺失
* 檢查器在啟動時或工作階段稍後連續失敗兩次。Claude Code 在第一次失敗後重新啟動它，在第二次失敗後停止檢查，直到您重新啟動 Claude Code
* 檢查器花費超過 15 秒來回答三次。每次，Claude Code 都會將它等待的單詞保留為未標記；在第三次之後，它停止檢查，直到您重新啟動 Claude Code

若要找出發生了哪一種情況，請使用 `claude --debug` 啟動拼寫檢查並輸入一個單詞。然後在 `~/.claude/debug/<session-id>.txt` 的偵錯日誌中查找 `[spellcheck]` 行。一行命名 Claude Code 啟動的程式，或列出它查找但未找到的程式。稍後的行說明它停止的原因。那裡的缺少字典錯誤表示檢查器沒有您的 `language` 值的字典，或當 `language` 未設定時沒有預設字典。安裝一個，或將 `language` 設定為您擁有的字典。

## 提示詞中的隱形字元

貼上的文字可能包含 Unicode 字元，終端機不會顯示這些字元，例如標籤字元、雙向控制字元和零寬度空格，因此提示詞可能包含您看不到的文字。為了防止複製的文字攜帶終端機不會顯示的指令，Claude Code 會在您按下 Enter 時移除這些字元，然後再傳送任何內容。它會清理提示詞和提示詞所包含的任何摺疊 [貼上文字參考](https://code.claude.com/docs/zh-TW/terminal-config.md#paste-large-content) 的內容。Claude Code 會保留波斯語和印度系文字所使用的連接符，以及表情符號序列內的選擇器。

如果 Claude Code 移除了任何內容，該 Enter 不會傳送任何內容。清理後的提示詞會回到輸入框中，並顯示通知，例如 `Removed 3 invisible characters · review and press Enter to send`，再次按下 Enter 會傳送顯示的文字。

當您在命令列上傳遞提示詞時，例如 `claude "fix the login bug"`，Claude Code 不會等待第二次 Enter。它會移除字元、顯示通知並傳送清理後的提示詞。如果清理後的提示詞會以 `/` 開頭，Claude Code 會改為將其放在輸入框中供您檢閱並傳送。

## 使用 /diff 檢視變更

執行 `/diff` 以在不離開 Claude Code 的情況下查看工作樹中的變更。您可以看到 Claude 迄今為止所做的編輯，以及任何您尚未提交的其他內容。`/diff` 開啟的內容取決於目前使用的渲染器：

* **[全螢幕渲染](https://code.claude.com/docs/zh-TW/fullscreen.md)**：[差異面板](#diff-panel)會在對話旁邊開啟。該面板會保持開啟並在您繼續工作時更新。
* **經典渲染器**：[差異對話框](#diff-dialog)會在提示詞上方開啟，您在閱讀完後將其關閉。

面板和對話框皆來自 `cc-plugin-diff`，這是[Claude Code 內建的 mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md#mods-built-into-claude-code) 之一。如果您在 `/plugin` 中停用該 mod，`/diff` 會改為開啟 Claude Code 先前的面板和[差異檢視器](https://code.claude.com/docs/zh-TW/keybindings.md#diff-actions)。

在 `/diff` 從 git 讀取的變更中，子模組會顯示為單一項目，且僅當其指向的提交發生變更時才會出現；對子模組內檔案的編輯不會在此處顯示。一旦 Claude 編輯了檔案，面板和對話框也會提供每個回合編輯內容的檢視。這些回合檢視來自 Claude 的檔案編輯而非 git，因此 Claude 透過 shell 命令進行的變更僅出現在工作樹檢視 `Current` 下。

### 差異面板

差異面板列出已變更的檔案及其新增和移除的行數，並在列表下方顯示每個檔案的差異。Claude Code 會在 Claude 編輯檔案或執行 shell 命令時重新整理它。若要關閉面板，請再次執行 `/diff` 或按一下其標題中的 `✕`。

若要使用該面板，您需要：

* [全螢幕渲染](https://code.claude.com/docs/zh-TW/fullscreen.md)
* 一個 git 儲存庫
* 寬度至少為 110 欄的終端機
* Claude Code v2.1.287 或更新版本

一旦 Claude 開始編輯檔案，如果您的終端機寬度至少為 144 欄，該面板也會自動開啟。在您自己使用 `/diff` 開啟它後，後續工作階段會在 Claude 在任何足夠寬的終端機中編輯檔案時立即開啟它。關閉面板後，它會保持關閉狀態，在此工作階段和後續工作階段中，直到您再次執行 `/diff`。

當面板開啟時，您可以：

* **跳至檔案**：按一下列表中的其列。使用滑鼠滾輪捲動面板。當檔案列表本身太長而無法容納時，使用 `Alt+Up` 和 `Alt+Down` 或 `Ctrl+Up` 和 `Ctrl+Down` 捲動它。
* **詢問 Claude 有關某個檔案的變更**：按一下檔案差異上方、檔案名稱右側的 `ask`。Claude Code 會將該檔案的差異附加到您的下一個提示詞，且在您傳送該提示詞之前，按鈕會顯示 `asked ✓`。對第二個檔案提問會取代第一個。
* **顯示單一回合的編輯**：按一下面板標題中的 `source` 選擇器，然後使用 `Up` 和 `Down` 選擇回合並按 `Enter`。回合標示為 `T1`、`T2` 等。選擇器會在 Claude 編輯檔案後出現，而 `Current` 會讓您返回工作樹。
* **顯示面板遺漏的檔案**：列表會跳過測試檔案和產生的檔案，並將此工作階段之前的變更摺疊為底部的一行。按一下任一計數行以展開它。
* **變更面板比較的對象**：按 `Ctrl+X B` 以在此工作階段的變更、您的未提交變更作為一個列表，以及自您的分支從預設分支分割以來的所有內容之間循環。Claude Code 會記住每個儲存庫的選擇。

若要重新繫結捲動檔案列表或變更比較對象的快捷鍵，請參閱[差異面板動作](https://code.claude.com/docs/zh-TW/keybindings.md#diff-panel-actions)。

在未完成的合併、rebase、cherry-pick 或 revert 期間，面板會持續顯示它上次從 git 讀取的變更，因此不會被該操作的傳入變更填滿。它會在操作結束後的第一次重新整理時更新，例如當 Claude 下一次編輯檔案時。

### 差異對話框

差異對話框會以帶邊框的區塊形式在提示詞上方開啟，並列出已變更的檔案及其新增和移除的行數。它會將這些檔案與 `HEAD` 進行比較，或與您上次針對此儲存庫[在差異面板中選擇](#diff-panel)的對象進行比較。

一旦 Claude 編輯了檔案，列表上方會出現 `source` 選擇器。對於每個促使 Claude 編輯檔案的提示詞，它都會提供一個回合檢視，標示為 `T1`、`T2` 等。回合檢視僅顯示該回合的編輯，而 `Current` 會讓您返回工作樹。

在對話框中使用這些按鍵：

* **上和下**：選取檔案。
* **Enter**：開啟所選檔案的差異。使用上和下或 PageUp 和 PageDown 捲動它。
* **Esc**：從檔案的差異返回到列表，或從列表關閉對話框。
* **Tab**：移至 `source` 選擇器，然後使用上和下選擇 `Current` 或回合檢視並按 Enter。在檔案的差異中，Tab 會移至 `ask` 按鈕。按 Enter 將該檔案的差異附加到您的下一個提示詞。

## 使用 /btw 提出附帶問題

使用 `/btw` 提出關於您目前工作的問題，而不將其新增至對話歷史記錄。

```
/btw what was the name of that config file again?
```

Claude 會根據對話中已有的內容來回答附帶問題：您的訊息、它的回覆，以及它蒐集的工具結果。您可以詢問 Claude 已經讀過的程式碼、它之前做出的決定，或工作階段中的任何其他內容。較晚的附帶問題也會看到您之前的附帶問題：Claude Code 會在每次提問時重新播放最新的 20 次交換，直到您清除它們為止。問題和答案永遠不會進入對話歷史記錄。在終端機中，它們會出現在可關閉的覆蓋層中。終端機會將執行緒保留在記憶體中：按 `x` 清除較早的交換，當您退出 Claude Code 時，它就會消失。

在 [VS Code 擴充功能](https://code.claude.com/docs/zh-TW/vs-code.md#use-the-prompt-box)的聊天面板中，`/btw` 會開啟一個面板，而不是本節所述的覆蓋層，您可以直接在面板中提出後續問題。該面板的執行緒在視窗重新載入後仍會保留，遵循該頁面所述的保留排程。您需要 v2.1.227 或更新版本的擴充功能。較早的擴充功能版本不提供 `/btw`。

* **Claude 工作時可用**：即使 Claude 正在處理回應時，您也可以執行 `/btw`。附帶問題會獨立執行，不會中斷主要回合。它會看到目前為止對話中的所有內容，除了 Claude 仍在撰寫的回覆。
* **無工具存取**：附帶問題只能根據已在內容中的內容來回答。Claude 在回答附帶問題時無法讀取檔案、執行命令或搜尋。如果 Claude 無論如何都將工具呼叫寫成文字，答案會以一個說明沒有任何內容被執行的備註結尾。
* **單一回應**：覆蓋層中沒有後續回合。若要繼續執行緒，請提出另一個 `/btw` 問題。若要在本機工作階段中繼續使用完整工具存取，請按 `f` 將此問題和答案分支到[背景子代理](https://code.claude.com/docs/zh-TW/sub-agents.md#fork-the-current-conversation)。
* **低成本**：當對話的[提示快取](https://code.claude.com/docs/zh-TW/prompt-caching.md)處於熱狀態時，附帶問題的成本只是答案本身之外的少量成本。

您最新的五個較早附帶問題會以暗淡的清單形式出現在目前答案上方，並顯示任何較舊問題的計數。它們會保持在對話歷史記錄之外。

若要在關閉覆蓋層後返回，請執行不帶問題的 `/btw`。覆蓋層會在您最近的交換上重新開啟。

答案出現後，覆蓋層會接受這些按鍵。

| 按鍵 | 動作 |
| :- | :- |
| `Space`、`Enter`、`Escape` | 關閉答案並返回提示 |
| `Up` / `Down` | 捲動答案 |
| `Shift+Left` / `Shift+Right` | 在此答案和您較早的 `/btw` 答案之間步進。`Shift+Left` 移至較舊的答案，`Shift+Right` 返回目前的答案。`[` 和 `]` 執行相同操作，適用於不報告 `Shift` 與箭頭鍵的終端機。`Tab` / `Shift+Tab` 在相同答案之間循環。需要 Claude Code v2.1.257 或更新版本。在 v2.1.187 和 v2.1.256 之間，按鍵是純 `Left` / `Right` |
| `c` | 將答案複製到您的剪貼簿作為原始 Markdown。使用此方法而不是滑鼠選取，後者會擷取硬換行的終端機呈現，而不是原始文字 |
| `f` | 啟動[分支子代理](https://code.claude.com/docs/zh-TW/sub-agents.md#fork-the-current-conversation)，它繼承父對話加上此問題和答案，以便它可以繼續使用完整工具存取。您保持在目前工作階段中，並在[提示下方的面板](https://code.claude.com/docs/zh-TW/sub-agents.md#observe-and-steer-running-forks)中找到分支。僅在本機工作階段中可用 |
| `x` | 清除目前答案上方顯示的較早 `/btw` 交換清單 |

在附加的[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md#attach-to-a-session)中，`Left` 會分離並將您返回代理檢視，即使答案仍在送達中。附帶問題會在您離開時繼續執行。下次您附加到工作階段時，覆蓋層會使用附帶問題或其答案重新開啟。在 v2.1.257 之前，`Left` 在那裡不會分離。

`/btw` 會看到您的完整對話，或[您開啟的 subagent 逐字稿](#ask-btw-about-a-subagent)，但沒有工具。[Subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 有工具，並從它接收的提示詞開始。[分支](https://code.claude.com/docs/zh-TW/sub-agents.md#fork-the-current-conversation)則從此對話的副本開始。使用 `/btw` 詢問 Claude 已從此工作階段了解的內容；使用 subagent 來發現新的內容。

### 針對 subagent 使用 /btw 提問

在[開啟 subagent 逐字稿](https://code.claude.com/docs/zh-TW/sub-agents.md#observe-and-steer-running-forks)時，Claude 會根據該逐字稿而非主要對話來回答 `/btw`，因此您可以詢問該 subagent 做了什麼。之後從該逐字稿提出的 `/btw` 只會看到您從該逐字稿提出的附帶問題。需要 Claude Code v2.1.314 或更新版本。

從 [agent team](https://code.claude.com/docs/zh-TW/agent-teams.md) 隊員的逐字稿提問時，Claude 會根據主要對話來回答。

## 工作清單

工作清單是 Claude 的待辦事項檢查清單：Claude 建立的項目，用於規劃多步驟工作，並顯示待處理、進行中或已完成的指示器。它與背景工作檢視分開。若要查看執行中的 shell 和子代理，請改用 [`/tasks`](https://code.claude.com/docs/zh-TW/commands)。

此清單僅在具有工作追蹤工具的工作階段中填充，Claude Code 預設在 [Opus 4.7、Sonnet 4.6、Haiku 4.5 及更早的模型](https://code.claude.com/docs/zh-TW/tools-reference.md#task-tool-availability) 上提供這些工具。在任何其他模型上，包括 Claude Code 無法識別的模型 ID，除非您使用 `CLAUDE_CODE_ENABLE_TODO_TOOLS=1` 或 [工作工具可用性](https://code.claude.com/docs/zh-TW/tools-reference.md#task-tool-availability) 下的其他方式選擇加入，否則清單保持空白。當工作階段具有這些工具時，工作清單的運作方式如下：

* 按 `Ctrl+T` 切換工作清單檢視。顯示一次最多五個工作。當 Claude 尚未建立任何檢查清單項目時，切換沒有可見效果，因為沒有任何內容可顯示
* 如果您保持清單展開，Claude Code 會在下次啟動仍有工作的工作階段時（例如使用 `--resume` 或 `--continue`）還原展開檢視。當工作清單為空時，Claude Code 會以摺疊狀態啟動它
* 若要查看所有工作或清除它們，直接詢問 Claude：「show me all tasks」或「clear all tasks」
* 工作在內容壓縮過程中保持不變，幫助 Claude 在較大的專案上保持組織
* 若要在工作階段之間共享工作清單，請設定 `CLAUDE_CODE_TASK_LIST_ID` 以使用 `~/.claude/tasks/` 中的具名目錄：`CLAUDE_CODE_TASK_LIST_ID=my-project claude`

## 工作階段摘要

當您離開終端機後返回時，Claude Code 會顯示工作階段迄今為止發生情況的單行摘要。摘要會在背景中生成，一旦自上次完成的回合已經過至少三分鐘且終端機未獲得焦點，摘要就會準備好供您切換回來時使用。摘要只會在工作階段至少有三個回合後出現，且永遠不會連續出現兩次。

執行 `/recap` 以按需生成摘要。此指令只有在您親自要求時才會執行。當它出現在從 Slack、Teams 或專案討論串轉發的訊息中時，您會收到一則[通知](https://code.claude.com/docs/zh-TW/errors.md#recap-only-runs-when-you-ask-for-it-yourself)，而不是摘要。當 `/recap` 出現在雲端排程任務傳送的提示詞中時，您也會收到該通知。

工作階段摘要在所有方案和提供者上預設為開啟。若要關閉自動摘要，請開啟 `/config` 並關閉**工作階段摘要**。自動摘要永遠不會出現在非互動模式中。Claude Code 將自動摘要和 `/recap` 輸出都限制在 400 個字元。

## 等待使用量限制重設

當 claude.ai [使用量限制](https://code.claude.com/docs/zh-TW/errors.md#youve-hit-your-session-limit) 在任務中途停止 Claude 時，Claude Code 會在開啟的工作階段中等待，並在限制重設後自動繼續該任務。在使用 claude.ai 訂閱登入的互動式工作階段中，自動繼續預設為開啟。需要 Claude Code v2.1.234 或更新版本。

Claude Code 等待時，工作階段底部的幾行會顯示您的上限何時重設，以及 Claude 何時會繼續：

```text theme={null}
Usage limit reached · limit resets 3:45pm
Continuing automatically at 3:45pm · Esc to cancel
```

任一行在這些文字之後都可能帶有更多內容，例如第一行的說明連結，或第二行的 `/usage-credits to continue now`。當等待自行開始時，對話中也會以一行 `Usage limit reached · continuing automatically at 3:45pm · esc to cancel` 記錄下來。

保持工作階段開啟。接下來發生的情況取決於等待如何結束：

* **在重設時**：第二行會變為 `Continuing shortly · Esc to cancel`。接著對話中會出現 `Usage limit reset · Continuing automatically`，Claude Code 會提示 Claude 從停止的地方接續任務。它不會重新傳送您的最後一條訊息。
* **在您的電腦睡眠後**：如果睡眠超過約 30 分鐘，且上限在睡眠期間重設，第一行會顯示 `Your usage limit has reset`，第二行會顯示 `Press enter to continue`。按 `Enter` 繼續。若睡眠時間較短，或睡眠在重設前就已結束，Claude Code 會自動繼續。
* **提前**：當您使用 `/usage-credits` 完成新增 [使用額度](https://code.claude.com/docs/zh-TW/costs.md#add-usage-credits-to-your-subscription)、在 `/upgrade` 後重新登入，或在等待期間使用 `/model` 切換模型時，Claude Code 會檢查使用量是否再次可用，如果可用則立即繼續。它不會在您在瀏覽器中自行進行的升級或購買後檢查。在 [`opusplan`](https://code.claude.com/docs/zh-TW/model-config#opusplan-model-setting) 和其他在不同模型上執行計畫模式的模型設定下，Claude Code 會改為等待重設。

在繼續的任務中，Claude Code 仍會照常要求 [權限](https://code.claude.com/docs/zh-TW/permissions.md)，因此任務可能會在您不在時停在權限提示處。如果任務再次達到上限，等待會再次開始。

自動繼續三次後，自動繼續會停止，並出現 `Automatic continue stopped after repeated usage-limit hits` 通知。執行 `/rate-limit-options` 以選擇接下來要做什麼。當您傳送另一個提示詞，或從該選單中選擇等待時，計數會重新開始。對於跨越多個重設視窗執行的 [`/goal`](https://code.claude.com/docs/zh-TW/goal) 或 [工作階段範圍的排程任務](https://code.claude.com/docs/zh-TW/scheduled-tasks.md)，自動繼續同樣會在繼續三次後停止。

### 取消等待

在這些行顯示期間，於提示詞為空時按 `Esc`，或按 `Ctrl+C`，或執行 [`/rate-limit-options`](https://code.claude.com/docs/zh-TW/commands#all-commands) 並選擇 **Don't continue automatically**。Claude Code 會以一行以 `Automatic continue cancelled` 開頭的訊息確認。

取消後，在您傳送提示或再次從 `/rate-limit-options` 選擇以 **Wait here, then continue automatically** 開頭的列之前，不會有任何內容繼續。Claude Code 不會在該重設視窗中自行再次啟動等待；下一個重設視窗會重新開始。

等待也會在以下情況下結束而不繼續任務：

* **您傳送提示詞**：Claude Code 會傳送您的提示詞而不是等待。如果您的提示詞也達到上限，它會保留在對話中，且 Claude Code 會再次開始等待。
* **您退出 Claude Code**：當您繼續工作階段時，等待不會重新啟動。
* **對話轉手**：您使用 `/login` 切換帳戶、清除或倒帶對話、`/resume` 另一個工作階段、使用 `/teleport` 拉取一個、使用 `/tui` 或 [`/restart`](https://code.claude.com/docs/zh-TW/commands#all-commands) 重新啟動，或將工作階段交給 Claude Desktop、背景工作階段或雲端。
* **設定關閉，或重設超過 24 小時**：這只會結束 Claude Code 自行啟動的等待。您從 `/rate-limit-options` 選擇的等待會繼續倒數。
* **繼續被阻止**：一個 [`UserPromptSubmit` hook](https://code.claude.com/docs/zh-TW/hooks#userpromptsubmit) 阻止繼續提示，或在到達模型之前失敗，會結束等待。Claude Code 會告訴您繼續未執行。傳送提示以繼續。

### 自行啟動等待

Claude Code 在以下情況下不會自行啟動等待：

* **遠端控制和代理團隊隊友工作階段**：該終端上的人仍然可以啟動一個。
* **重設超過 24 小時**：每週限制可能在數天後重設。
* **您執行該系列外的模型時的 Opus 或 Sonnet 限制**：您的下一回合可能不會達到該限制。[`opusplan`](https://code.claude.com/docs/zh-TW/model-config#opusplan-model-setting) 和其他在受限系列上執行計畫模式的模型設定不會獲得此例外。

在這些情況下，以及每當自動繼續關閉時，當您在自己的終端達到限制時，Claude Code 會在每個重設視窗中開啟一次使用量限制選項菜單。選擇以 **Wait here, then continue automatically** 開頭的列以啟動等待。在 [遠端控制](https://code.claude.com/docs/zh-TW/remote-control.md) 或 [代理團隊](https://code.claude.com/docs/zh-TW/agent-teams.md) 隊友工作階段中，自行執行 `/rate-limit-options` 以開啟菜單。

Claude Code 在以下情況下根本不提供等待：

* **背景工作階段和 `-p` 執行**：菜單列不可用。
* **API 金鑰、雲端提供者和按使用量計費**：那裡的使用量按請求計量，因此沒有重設可等待。
* **沒有已儲存 claude.ai 登入的 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway#subscriptions-and-gateways)**：Claude Code 只在已儲存的 claude.ai 登入是作用中認證時提供等待。

### 關閉自動繼續

在 `/config` 中，關閉 **Continue automatically at usage limit**，或在您的使用者設定中將 [`autoContinueAtUsageLimit`](https://code.claude.com/docs/zh-TW/settings-reference#autocontinueatusagelimit) 設定為 `false`。`/config autoContinueAtUsageLimit=false` 也有效，包括使用 `-p`，但 `key=value` 形式無法將其重新開啟，因為該設定授予無人值守執行。Claude Code 為此金鑰讀取的設定檔在 [設定參考](https://code.claude.com/docs/zh-TW/settings-reference.md#autocontinueatusagelimit) 中。

## PR 審查狀態

在具有開放拉取請求的分支上工作時，Claude Code 會在頁腳中顯示可點擊的 PR 連結，例如「PR #446」。該連結具有彩色底線，指示審查狀態：

* 綠色：已批准
* 黃色：待審查
* 紅色：要求變更
* 灰色：草稿

拉取請求合併或關閉後，徽章會消失。

`Cmd+click`（macOS）或 `Ctrl+click`（Windows/Linux）該連結以在瀏覽器中開啟拉取請求。

狀態會在 `git push` 或更改拉取請求的 `gh pr` 命令（例如 `gh pr create` 或 `gh pr merge`）在工作階段中成功後立即重新整理。

Claude Code 會將徽章呈現為超連結，即使它無法在您的終端中偵測到超連結支援，這在 SSH 或 tmux 中很常見。設定 [`FORCE_HYPERLINK=0`](https://code.claude.com/docs/zh-TW/env-vars) 以將徽章呈現為純文字。

當您設定 [`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`](https://code.claude.com/docs/zh-TW/env-vars) 時，Claude Code 不會檢查拉取請求或合併請求狀態。

> [!NOTE]
>
> GitHub 儲存庫的 PR 狀態需要 GitHub 權杖。Claude Code 根據遠端的主機尋找一個：
>
> * **github.com**：`GH_TOKEN` 或 `GITHUB_TOKEN`，或由 `gh auth login` 儲存的權杖。沒有權杖時，當未安裝 `gh` CLI 時，頁腳會顯示 `install gh for PR status`，或當已安裝時顯示 `gh auth login for PR status`
> * **設定為 `GH_HOST` 的 GitHub Enterprise 主機**：`GH_ENTERPRISE_TOKEN` 或 `GITHUB_ENTERPRISE_TOKEN`，或由 `gh auth login --hostname <host>` 儲存的權杖。沒有權杖時，頁腳會顯示相同的提示
> * **任何其他 GitHub 主機**：由 `gh auth login --hostname <host>` 儲存的權杖。沒有權杖時，Claude Code 不會顯示徽章和提示

### GitLab 合併請求

當您在具有開放 GitLab 合併請求的分支上工作時，Claude Code 會在頁腳位置顯示可點擊的 `MR !N` 徽章，該位置通常保留給 GitHub PR 連結。`!N` 是 GitLab 自己的合併請求編號 N 的參考語法。彩色底線顯示合併請求的狀態：

* 綠色：GitLab 報告合併請求可合併
* 黃色：任何其他開放狀態
* 灰色：草稿

合併請求合併或關閉後，徽章會消失。

它會在 `git push` 或更改合併請求的 `glab mr` 命令（例如 `glab mr create` 或 `glab mr merge`）在工作階段中成功後立即重新整理。

若要取得徽章，您需要：

* Claude Code v2.1.234 或更新版本
* 指向您的 GitLab 主機的儲存庫遠端，可以是 gitlab.com 或自管理執行個體
* 您 `PATH` 上的 [`glab` CLI](https://gitlab.com/gitlab-org/cli)，已使用 `glab auth login` 進行驗證

Claude Code 在檢查狀態時會忽略 `glab` 的權杖環境變數（例如 `GITLAB_TOKEN`），因此您無法從單獨匯出的權杖取得徽章。Claude Code 也會在每個工作階段中尋找 `glab` 及其登入一次，因此在安裝 `glab` 或執行 `glab auth login` 後請重新啟動 Claude Code。

## 問題參考連結

當 Claude 提及問題時使用 `owner/repo#123` 的格式，只要您的終端機支援超連結，您就可以點擊該參考來開啟它。如果 Claude Code 未偵測到您的終端機支援超連結，請將 [`FORCE_HYPERLINK`](https://code.claude.com/docs/zh-TW/env-vars) 設定為 `1` 以開啟連結，或設定為 `0` 以保持參考為純文字。

您只能取得兩部分 `owner/repo#123` 格式的連結。以下這些會保持為純文字：

* 單獨的 `#123`
* 巢狀的 GitLab 路徑，例如 `group/subgroup/project#123`
* 程式碼跨度或程式碼區塊內的任何參考
* 長度超過約 1,000 行或 100,000 個字元的回覆中的任何參考

Claude Code 會根據從您的 git remote 識別出的儲存庫主機來建立連結，而不是根據參考所命名的儲存庫：

| 您的儲存庫主機 | `owner/repo#123` 連結到 |
| :- | :- |
| github.com、GitHub Enterprise 主機或下方未列出的任何主機 | `https://<host>/owner/repo/issues/123` |
| gitlab.com | `https://gitlab.com/owner/repo/-/issues/123` |
| bitbucket.org、codeberg.org 或 gitea.com | 無連結；參考保持為純文字 |

## 另請參閱

* [Skills](https://code.claude.com/docs/zh-TW/skills.md) - 自訂提示和工作流程
* [Checkpointing](https://code.claude.com/docs/zh-TW/checkpointing.md) - 回溯 Claude 的編輯並恢復先前的狀態
* [CLI 參考](https://code.claude.com/docs/zh-TW/cli-reference.md) - 命令列旗標和選項
* [設定](https://code.claude.com/docs/zh-TW/settings.md) - 配置選項
* [記憶體管理](https://code.claude.com/docs/zh-TW/memory.md) - 管理 CLAUDE.md 檔案

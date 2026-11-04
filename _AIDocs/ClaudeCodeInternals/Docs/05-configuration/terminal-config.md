<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/terminal-config | lastmod: 2026-10-29 | section: Configuration / Interface -->
> 來源：https://code.claude.com/docs/zh-TW/terminal-config（官方 zh-TW，lastmod 2026-10-29）｜分類：Configuration › Interface｜EN 摘要：Fix Shift+Enter for newlines, get a terminal bell when Claude finishes, configure tmux, match the color theme, and enable Vim mode in the Claude Code CLI.

# 為 Claude Code 設定您的終端機

> 修正 Shift+Enter 以插入新行、在 Claude 完成時取得終端機鈴聲、設定 tmux、符合色彩主題，以及在 Claude Code CLI 中啟用 Vim 模式。

Claude Code 可在任何終端機中無需設定即可運作。此頁面適用於當某些特定功能的行為不符合您的預期時。在下方找到您的症狀。如果一切已經感覺正確，您不需要此頁面。

* [Shift+Enter 提交而非插入新行](#enter-multiline-prompts)
* [macOS 上的 Option 鍵快捷鍵無法運作](#enable-option-key-shortcuts-on-macos)
* [Claude 完成時沒有聲音或警示](#get-a-terminal-bell-or-notification)
* [您在 tmux 內執行 Claude Code](#configure-tmux)
* [Windows 上的 Backspace 刪除整個單字](#fix-backspace-deleting-a-whole-word-on-windows)
* [顯示閃爍或回捲跳躍](#switch-to-fullscreen-rendering)
* [您想在提示中使用 Vim 快捷鍵](#edit-prompts-with-vim-keybindings)

此頁面是關於讓您的終端機向 Claude Code 傳送正確的訊號。若要變更 Claude Code 本身回應的快捷鍵，請改為參閱 [快捷鍵](https://code.claude.com/docs/zh-TW/keybindings.md)。

## 輸入多行提示

按 Enter 鍵提交您的訊息。若要在不提交的情況下新增換行符，請按 Ctrl+J，或輸入 `\` 然後按 Enter。兩種方法在每個終端機上都可以使用，無需設定。

在大多數終端機中，您也可以按 Shift+Enter，但支援情況因終端機模擬器而異：

| 終端機 | Shift+Enter 用於換行 |
| :- | :- |
| Ghostty、Kitty、iTerm2、WezTerm、Warp、Apple Terminal、Windows Terminal | 無需設定即可使用 |
| 支援 kitty 鍵盤協議的其他終端機，例如 foot 和 Alacritty 0.16 或更新版本 | 無需設定即可使用。需要 Claude Code v2.1.269 或更新版本 |
| VS Code、Cursor、Devin Desktop、Alacritty 0.16 之前的版本、Zed | 執行一次 `/terminal-setup` |
| gnome-terminal、JetBrains IDE（例如 PyCharm 和 Android Studio） | 不可用；使用 Ctrl+J 或 `\` 然後 Enter |

對於 VS Code、Cursor、Devin Desktop、Alacritty 0.16 之前的版本和 Zed，`/terminal-setup` 會將 Shift+Enter 快捷鍵寫入終端機的設定檔。在首次執行時，您會看到確認訊息，例如 `Installed VSCode terminal Shift+Enter key binding`。現有的快捷鍵設定會保留；如果您看到類似 `VSCode terminal Shift+Enter key binding already configured` 的訊息，表示未進行任何變更。請直接在主機終端機中執行 `/terminal-setup`，而不是在 tmux 或 screen 內執行，因為它需要寫入主機終端機的設定。

在 VS Code、Cursor 和 Devin Desktop 中，`/terminal-setup` 也會更新兩個編輯器設定：它將 `terminal.integrated.gpuAcceleration` 設定為 `"off"` 以防止整合終端機中的文字亂碼，並設定 `terminal.integrated.mouseWheelScrollSensitivity` 以在[全螢幕模式](https://code.claude.com/docs/zh-TW/fullscreen.md)中實現更平順的捲動。若要復原 GPU 加速變更，請將其設回 `"auto"` 並重新載入編輯器視窗。

在 Zed 中，`/terminal-setup` 會就地更新您的 `keymap.json`：

* 如果 keymap 已有快捷鍵設定，且其中沒有 Terminal `shift-enter`，Claude Code 會先將其備份到同一目錄中的副本（例如 `keymap.json.1a2b3c4d.bak`），然後將 Shift+Enter 快捷鍵合併到您的 keymap 中，保留您的其他快捷鍵和註解
* 如果 Claude Code 無法讀取或解析 keymap、無法備份，或無法驗證合併結果，它會[保持檔案不變並列印快捷鍵區塊供您自行新增](https://code.claude.com/docs/zh-TW/errors.md#terminal-setup-left-your-zed-keymap-unchanged)

如果您在 tmux 內執行，即使外部終端機支援，Shift+Enter 也需要下方的 [tmux 設定](#configure-tmux)。

若要將換行符綁定到不同的按鍵，或交換行為使 Enter 插入換行符而 Shift+Enter 提交，請在您的[快捷鍵檔案](https://code.claude.com/docs/zh-TW/keybindings.md)中對應 `chat:newline` 和 `chat:submit` 動作。

## 在 macOS 上啟用 Option 鍵快捷鍵

某些 Claude Code 快捷鍵使用 Option 鍵，例如 Option+Enter 用於換行或 Option+P 用於切換模型。在 macOS 上，大多數終端機預設不會將 Option 作為修飾鍵發送，因此這些快捷鍵在啟用之前不會執行任何操作。終端機的此設定通常標記為「使用 Option 作為 Meta 鍵」；Meta 是現在標記為 Option 或 Alt 的鍵的歷史 Unix 名稱。

> [tab] Apple Terminal
>
> 開啟「設定」→「描述檔」→「鍵盤」，並勾選「使用 Option 作為 Meta 鍵」。
>
> 如果您接受了 Claude Code 的首次執行終端機設定提示，這已經完成。該提示會為您執行 `/terminal-setup`，它會啟用 Option 作為 Meta 並在您的 Apple Terminal 描述檔中關閉可聽見的鈴聲。
>
> 在[螢幕閱讀器模式](https://code.claude.com/docs/zh-TW/accessibility.md)中，`/terminal-setup` 保持鈴聲設定不變，以便終端機鈴聲保持可聽見。如果較早的執行關閉了鈴聲，請在「設定」→「描述檔」→「進階」→「可聽見的鈴聲」下重新開啟。

> [tab] iTerm2
>
> 開啟「設定」→「描述檔」→「按鍵」→「一般」，並將「左 Option 鍵」和「右 Option 鍵」設定為「Esc+」。
>
> 在 iTerm2 中執行 `/terminal-setup` 會在「設定」→「一般」→「選取」下啟用「終端機中的應用程式可以存取剪貼簿」，以便 `/copy` 命令可以寫入您的系統剪貼簿。該命令即使在 tmux 內執行時也能偵測 iTerm2。重新啟動 iTerm2 以使變更生效。

> [tab] VS Code
>
> 將 `"terminal.integrated.macOptionIsMeta": true` 新增至您的 VS Code 設定。

對於 Ghostty、Kitty 和其他終端機，請在終端機的設定檔中尋找 Option-as-Alt 或 Option-as-Meta 設定。

## 取得終端機鈴聲或通知

當 Claude 完成任務或暫停以等待權限提示，且您似乎不在終端機前時，它會觸發通知事件。請參閱[各通知類型何時觸發](https://code.claude.com/docs/zh-TW/hooks.md#notification)以了解確切的時機。將此顯示為終端機鈴聲或桌面通知可讓您在長時間任務執行時切換到其他工作。

根據預設，Claude Code 在某些終端機中會傳送桌面通知，在其他終端機中則會傳送鈴聲字元或不傳送任何內容：

* **Ghostty、Kitty 和 iTerm2**：桌面通知，其中 iTerm2 僅在您開啟其警示設定後才會顯示。
* **Apple Terminal**：沒有聲音；當 Claude Code 發現最前方 Terminal 視窗的描述檔中「Audible bell」為關閉時，會傳送靜音鈴聲字元，否則不傳送任何內容。如果該描述檔的「Visual bell」或 Dock 彈跳選項為開啟，該鈴聲字元會顯示為視窗閃爍，或在 Terminal 位於背景時顯示為 Dock 彈跳。
* **其他終端機**：不傳送任何內容。

若要讓 Claude Code 無論終端機或描述檔為何都傳送鈴聲字元，請將 [`preferredNotifChannel`](https://code.claude.com/docs/zh-TW/settings-reference#preferrednotifchannel) 設定為 `"terminal_bell"`。在 Apple Terminal 中，還需在 **Settings > Profiles > Advanced** 下開啟 **Audible bell** 才能聽到它。下列設定項目會設定此頻道：

```json ~/.claude/settings.json theme={null}
{
  "preferredNotifChannel": "terminal_bell"
}
```

桌面通知透過 SSH 到達您的本機，因此遠端工作階段仍可提醒您。Ghostty 和 Kitty 會將其轉發到您的作業系統通知中心，無需進一步設定。iTerm2 需要您啟用轉發：

**1. 開啟 iTerm2 通知設定**

前往 Settings → Profiles → Terminal。

**2. 啟用警示**

勾選「Notification Center Alerts」，然後按一下「Filter Alerts」並啟用「Send escape sequence-generated alerts」。

如果通知仍未出現，請確認您的終端機應用程式在作業系統設定中具有通知權限，且如果您在 tmux 內執行，請[啟用傳遞](#configure-tmux)。

### 使用通知 hook 播放音效

在任何終端機中，您可以設定[通知 hook](https://code.claude.com/docs/zh-TW/hooks-guide.md#get-notified-when-claude-needs-input) 以在 Claude 需要您注意時播放音效或執行自訂命令。Hook 與內建通知一起執行，而不是取代它，因此不會收到桌面通知的終端機（例如 Warp 或 VS Code 整合終端機）可以使用 hook 或改為將 `preferredNotifChannel` 設定為 `"terminal_bell"`。

下列範例在 macOS 上播放系統音效。連結的指南包含 macOS、Linux 和 Windows 的桌面通知命令。

```json ~/.claude/settings.json theme={null}
{
  "hooks": {
    "Notification": [
      {
        "hooks": [{ "type": "command", "command": "afplay /System/Library/Sounds/Glass.aiff" }]
      }
    ]
  }
}
```

## 在終端機中查看工作階段狀態

如果您的終端機實作了 OSC 7501 Program Status Protocol，它就能顯示每個互動式 Claude Code 工作階段是正在運作、正在等待您，還是已完成，這在您執行長時間任務或同時執行多個工作階段時很有幫助。Claude Code 中沒有需要開啟的設定。若要了解您的終端機是否實作了此協定，以及它在何處顯示狀態，請查閱其文件。

如果終端機已實作此協定，但您沒有看到某個工作階段的狀態，請逐一檢查以下原因：

* **Claude Code 版本**：狀態回報需要 Claude Code v2.1.295 或更新版本。在您的 shell 中執行 `claude --version` 以進行檢查。
* **tmux**：在 tmux 內，Claude Code 會檢查 tmux 是否支援，而非檢查您的終端機，且 [`allow-passthrough`](#configure-tmux) 對此沒有作用。請在 tmux 之外啟動工作階段。
* **背景工作階段**：[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)不會向您的終端機回報其狀態，即使您已附加至該工作階段也是如此。其狀態會改為顯示在 agent 檢視中。
* **[`CLAUDE_CODE_DISABLE_TERMINAL_TITLE`](https://code.claude.com/docs/zh-TW/env-vars#variables)**：如果您將此變數設為 `1`，Claude Code 就不會檢查是否支援，也不會回報狀態。請取消設定此變數。

在回報支援此協定的終端機中，分頁標題開頭不會出現狀態符號。由於終端機本身會顯示工作階段的狀態，Claude Code 便會省略在其他終端機中加在標題前方的符號。

## 設定 tmux

當 Claude Code 在 tmux 內執行時，預設會發生兩個問題：Shift+Enter 會提交而不是插入新行，且桌面通知和[進度列](https://code.claude.com/docs/zh-TW/settings-reference.md#terminalprogressbarenabled)永遠無法到達外層終端。將這些行新增到 `~/.tmux.conf`，然後執行 `tmux source-file ~/.tmux.conf` 以將其套用到執行中的伺服器：

```bash ~/.tmux.conf theme={null}
set -g allow-passthrough on
set -g focus-events on
set -s extended-keys on
set -as terminal-features 'xterm*:extkeys'
```

`allow-passthrough` 行讓通知和進度更新到達外層終端，而不是被 tmux 吞沒。`extended-keys` 行讓 tmux 區分 Shift+Enter 和純 Enter，以便換行快捷鍵能夠運作。

[mod 的 `Image`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#elements) 需要 `allow-passthrough` 和 `focus-events` 這兩行，以及其他[在 tmux 內繪製的需求](https://code.claude.com/docs/zh-TW/plugins/mods/gallery.md#draw-an-image-inside-tmux)。新增這些行之後，還需要從 tmux 分離、重新連接，並重新啟動 Claude Code。

## 修復 Windows 上 Backspace 刪除整個單詞的問題

在 Windows 上，Claude Code 將到達的 Backspace 讀取為 `^H` 時會將其解釋為 Ctrl+Backspace，這會[刪除前一個單詞](https://code.claude.com/docs/zh-TW/interactive-mode.md#text-editing)，除非 `TERM_PROGRAM` 是 `mintty` 或 `TERM` 是 `cygwin`。在 macOS 和 Linux 上，Claude Code 將其讀取為純 Backspace。

如果每次按下 Backspace 都會刪除整個單詞，表示您的終端機為純 Backspace 發送 `^H`。設定 [`CLAUDE_CODE_BS_AS_CTRL_BACKSPACE=0`](https://code.claude.com/docs/zh-TW/env-vars)。Backspace 和 Ctrl+H 隨後將各刪除一個字元。如果在 macOS 或 Linux 上 Ctrl+Backspace 只刪除一個字元，因為您的終端機為其發送 `^H`，請改為將變數設定為 `1`。

## 配合色彩主題

使用 `/theme` 命令，或 `/config` 中的主題選擇器，選擇與終端機相符的 Claude Code 主題。選取 auto 選項會偵測終端機的淺色或深色背景，因此每當終端機跟隨作業系統外觀變更時，主題也會隨之變更。Claude Code 不會控制終端機本身的配色方案，該方案由終端機應用程式設定。

若要自訂介面底部顯示的內容，請設定[自訂狀態列](https://code.claude.com/docs/zh-TW/statusline.md)，以顯示目前的模型、工作目錄、git 分支或其他脈絡資訊。

### 建立自訂主題

除了內建的預設主題之外，`/theme` 還會列出您已定義的任何自訂主題，以及已安裝的[外掛](https://code.claude.com/docs/zh-TW/plugins/components.md#themes-and-output-styles)所提供的任何主題。選取清單最後的 **New custom theme…** 即可以互動方式建立主題：先為主題命名，再挑選要覆寫的個別色彩 token。在自訂主題反白顯示時按下 `Ctrl+E` 即可編輯該主題。

每個自訂主題都是 `~/.claude/themes/` 中的一個 JSON 檔案。不含 `.json` 副檔名的檔名即為主題的 slug，選取該主題時會將 `custom:<slug>` 儲存為您的主題偏好設定。該檔案有三個選用欄位：

| 欄位 | 類型 | 說明 |
| :- | :- | :- |
| `name` | string | 在 `/theme` 中顯示的標籤。預設為檔名 slug |
| `base` | string | 主題所依據的內建預設主題：`dark`、`light`、`dark-daltonized`、`light-daltonized`、`dark-ansi` 或 `light-ansi`。預設為 `dark` |
| `overrides` | object | 色彩 token 名稱與色彩值的對應表。未列於此處的 token 會沿用基礎預設主題 |

色彩值接受 `#rrggbb`、`#rgb`、`rgb(r,g,b)`、`ansi256(n)` 或 `ansi:<name>`，其中 `<name>` 為 16 種標準 ANSI 色彩名稱之一，例如 `red` 或 `cyanBright`。未知的 token 與無效的色彩值會被忽略，因此拼寫錯誤不會破壞畫面呈現。

以下範例定義了一個主題，保留 dark 預設主題，但重新設定提示詞強調色、錯誤文字與成功文字的顏色：

```json ~/.claude/themes/dracula.json theme={null}
{
  "name": "Dracula",
  "base": "dark",
  "overrides": {
    "claude": "#bd93f9",
    "error": "#ff5555",
    "success": "#50fa7b"
  }
}
```

Claude Code 會監看 `~/.claude/themes/`，並在新增或變更檔案時重新載入，因此在編輯器中所做的修改會套用至執行中的工作階段，無需重新啟動。如果 Claude Code 啟動時 `~/.claude/themes/` 資料夾本身尚不存在，請在建立第一個主題檔案後重新啟動一次。此後，變更無需重新啟動即可套用。

以下參考資料涵蓋可在 `overrides` 中設定的 token。`/theme` 中的互動式編輯器會以即時預覽顯示相同的 token，另外還包含一些此處省略的單一用途強調色，例如新手引導畫面的色彩。

> [accordion] 色彩 token 參考
>
> 以下範例結合了下列數個群組中的 token：品牌強調色、plan mode 邊框、差異背景，以及訊息背景。
>
> ```json ~/.claude/themes/midnight.json theme={null}
> {
>   "name": "Midnight",
>   "base": "dark",
>   "overrides": {
>     "claude": "#a78bfa",
>     "planMode": "#38bdf8",
>     "diffAdded": "#14532d",
>     "diffRemoved": "#7f1d1d",
>     "userMessageBackground": "#1e1b4b"
>   }
> }
> ```
>
> #### 文字與強調色
>
> 控制整個介面中使用的主要品牌強調色與前景文字色調。
>
> | Token | 控制項目 |
> | :- | :- |
> | `claude` | 主要品牌強調色，用於載入指示器與助理標籤 |
> | `text` | 預設前景文字 |
> | `inverseText` | 繪製於彩色背景上的文字，例如狀態徽章 |
> | `inactive` | 次要文字，例如提示、時間戳記與停用的項目 |
> | `subtle` | 淡色邊框與弱化的次要文字 |
> | `suggestion` | 自動完成建議與選擇器中的選取反白 |
> | `permission` | 對話框邊框，包括權限提示與選擇器 |
> | `remember` | 記憶與 `CLAUDE.md` 指示器 |
>
> #### 狀態色彩
>
> 在訊息與指示器中表示成功、失敗與警告狀態。
>
> | Token | 控制項目 |
> | :- | :- |
> | `success` | 成功訊息與通過的檢查 |
> | `error` | 錯誤訊息與失敗 |
> | `warning` | 警告、注意訊息，以及自動模式指示器 |
> | `merged` | 已合併的 pull request 狀態 |
>
> #### 輸入框與模式指示器
>
> 設定輸入框邊框色彩，以及權限模式或指示器啟用時顯示的強調色。
>
> | Token | 控制項目 |
> | :- | :- |
> | `promptBorder` | 輸入框邊框 |
> | `planMode` | Plan mode 強調色、plan 訊息，以及 plan mode 對話框 |
> | `autoAccept` | 接受編輯模式強調色 |
> | `bashBorder` | 輸入 `!` shell 命令時的輸入框邊框 |
> | `ide` | IDE 連線指示器 |
> | `fastMode` | 快速模式指示器 |
> | `effortUltra` | [ultracode](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level) 開啟時輸入框邊框上的 `ultracode` 標籤。您對此色彩的覆寫在 Claude Code v2.1.239 或更新版本中生效 |
>
> #### 差異呈現
>
> 為檔案編輯與審查中新增和移除的程式碼上色。
>
> | Token | 控制項目 |
> | :- | :- |
> | `diffAdded` | 新增行的背景 |
> | `diffRemoved` | 移除行的背景 |
> | `diffAddedDimmed` | 拒絕編輯後顯示的淡化差異中新增行的背景 |
> | `diffRemovedDimmed` | 拒絕編輯後顯示的淡化差異中移除行的背景 |
> | `diffAddedWord` | 新增行內的字詞層級反白 |
> | `diffRemovedWord` | 移除行內的字詞層級反白 |
>
> #### 全螢幕模式
>
> Claude Code 僅在[全螢幕呈現模式](https://code.claude.com/docs/zh-TW/fullscreen.md)中使用 `userMessageBackgroundHover`、`selectionBg` 與 `composerSidebarBackground`。它在預設與全螢幕呈現器中都會繪製 `userMessageBackground`、`bashMessageBackgroundColor` 與 `memoryBackgroundColor`。
>
> | Token | 控制項目 |
> | :- | :- |
> | `userMessageBackground` | 逐字稿中您的訊息後方的背景 |
> | `userMessageBackgroundHover` | 訊息在滑鼠停留或展開時後方的背景 |
> | `bashMessageBackgroundColor` | 逐字稿中 `!` shell 命令項目後方的背景 |
> | `memoryBackgroundColor` | 逐字稿中 `#` 記憶項目後方的背景 |
> | `selectionBg` | 以滑鼠選取的文字背景 |
> | `composerSidebarBackground` | 對話旁面板的背景，例如[差異面板](https://code.claude.com/docs/zh-TW/fullscreen.md#watch-your-changes-in-the-diff-panel)或 [mod 的窗格](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md) |
>
> #### 用量計量表與發言者標籤
>
> 調整 `/usage` 檢視中顯示的長條，以及區分您的訊息與 Claude 訊息的標籤。
>
> | Token | 控制項目 |
> | :- | :- |
> | `rate_limit_fill` | 用量計量表的已填滿部分 |
> | `rate_limit_empty` | 用量計量表的未填滿部分 |
> | `briefLabelYou` | 您的訊息上 `You` 標籤的色彩 |
> | `briefLabelClaude` | 助理訊息上 `Claude` 標籤的色彩 |
>
> #### 微光變體與 subagent 色彩
>
> 數個 token 有配對的微光變體，提供載入指示器動畫漸層中使用的較淺色彩。如果動畫看起來不協調，請連同其基礎 token 一起覆寫微光變體。
>
> * `claude` 與 `claudeShimmer`
> * `warning` 與 `warningShimmer`
> * `permission` 與 `permissionShimmer`
> * `promptBorder` 與 `promptBorderShimmer`
> * `inactive` 與 `inactiveShimmer`
> * `fastMode` 與 `fastModeShimmer`
>
> 每個 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 與平行任務會以八種具名色彩之一顯示，讓您能在逐字稿中區分它們。Token 名稱遵循 `<color>_FOR_SUBAGENTS_ONLY` 模式，其中 `<color>` 為 `red`、`blue`、`green`、`yellow`、`purple`、`orange`、`pink` 或 `cyan`。覆寫這些 token 即可變更各具名色彩的外觀。例如，定義中含有 `color: blue` 的 subagent 會使用 `blue_FOR_SUBAGENTS_ONLY` 的值繪製。
>
> 當 [`ultrathink`](https://code.claude.com/docs/zh-TW/model-config#use-ultrathink-for-one-off-deep-reasoning) 可以提高某個回合的投入程度時，Claude Code 會以七色彩虹漸層呈現提示詞輸入中的該字詞。Token 名稱遵循 `rainbow_<color>` 與 `rainbow_<color>_shimmer` 模式，其中 `<color>` 為 `red`、`orange`、`yellow`、`green`、`blue`、`indigo` 或 `violet`。

## 切換至全螢幕渲染

在[螢幕閱讀器模式](https://code.claude.com/docs/zh-TW/accessibility.md)中，本節不適用。Claude Code 始終呈現為純文字滾動，除非在附加的[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)中，如果您在任何其他工作階段中執行 `/tui fullscreen`，Claude Code 會列印說明而不是切換。

如果顯示閃爍或在 Claude 工作時捲動位置跳動，請切換至[全螢幕渲染模式](https://code.claude.com/docs/zh-TW/fullscreen.md)。在此模式中，您可以使用滑鼠或 PageUp 在 Claude Code 內捲動，而不是使用終端機的原生捲回；請參閱[全螢幕頁面](https://code.claude.com/docs/zh-TW/fullscreen.md#search-and-review-the-conversation)以了解如何搜尋和複製。

如果閃爍是唯一的問題，且您的終端機支援同步輸出但未被自動偵測，例如 Emacs `eat`，請設定 [`CLAUDE_CODE_FORCE_SYNC_OUTPUT=1`](https://code.claude.com/docs/zh-TW/env-vars) 以停止閃爍而不改變渲染器。

執行 `/tui fullscreen` 以切換並儲存偏好設定。您的對話會完整重新啟動，未來的工作階段將以全螢幕啟動，除非[全螢幕啟動失敗](https://code.claude.com/docs/zh-TW/fullscreen.md#fullscreen-renderer-didnt-finish-starting)。您也可以在啟動 Claude Code 之前設定 `CLAUDE_CODE_NO_FLICKER` 環境變數：

```bash Bash and Zsh theme={null}
CLAUDE_CODE_NO_FLICKER=1 claude
```

```powershell PowerShell theme={null}
$env:CLAUDE_CODE_NO_FLICKER = "1"; claude
```

```json ~/.claude/settings.json theme={null}
{
  "env": {
    "CLAUDE_CODE_NO_FLICKER": "1"
  }
}
```

## 在寬終端機中限制回應寬度

在寬終端機中，Claude 回應中的每一行文字會佔據視窗的完整寬度。若要改為在設定的欄數處換行，請在您的設定中設定 [`maxProseWidth`](https://code.claude.com/docs/zh-TW/settings-reference#maxprosewidth)。

## 貼上大型內容

當您貼上超過 800 個字元或超過三行的內容到提示時，Claude Code 會將輸入摺疊為預留位置，例如 `[Pasted text #1 +120 lines]`，以保持輸入框可用，並在您提交時仍會傳送完整內容。對於非常大的輸入（例如整個檔案或長日誌），請將內容寫入檔案並要求 Claude 讀取它，而不是貼上。對話記錄保持可讀，Claude 可以在稍後的回合中按路徑參考該檔案。VS Code 整合終端也可能在非常大的貼上到達 Claude Code 之前從中丟棄字元，因此在那裡使用檔案。

如果貼上的內容包含[隱形 Unicode 字元](https://code.claude.com/docs/zh-TW/interactive-mode.md#invisible-characters-in-prompts)，Claude Code 會在您按下 Enter 時移除它們，並將清理後的提示放回輸入框供您以另一個 Enter 傳送。

### Claude 如何處理貼上的文字

當您提交時，Claude 會看到每個 `[Pasted text #N]` 預留位置後面的內容，標記為您從其他地方貼上而非輸入的文字。Claude 被告知貼上可能包含您未撰寫的指示，並且只在您輸入的訊息要求時才遵循其中的指示。在不[擷取功能旗標](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)的工作階段中，貼上不會被標記。

### 刪除並復原摺疊的貼上

當您使用字詞或行快捷鍵（例如 `Ctrl+W` 或 `Ctrl+K`）刪除，或透過 `f`/`t` 動作（例如 `df]`）使用 vim 刪除，且刪除範圍到達 `[Pasted text #N]` 預留位置內部時，Claude Code 會完全移除預留位置。若要復原它，請在字詞或行快捷鍵後使用 [`Ctrl+Y`](https://code.claude.com/docs/zh-TW/interactive-mode#text-editing) 貼上刪除的內容，或在 vim 刪除後使用 [`p` 在 NORMAL 模式中](https://code.claude.com/docs/zh-TW/interactive-mode#editing-normal-mode)。

### 回想包含貼上文字的提示

Claude Code 將每個 `[Pasted text #N]` 預留位置後面的內容保留在 `~/.claude/paste-cache/` 下，因此當您從[命令歷史](https://code.claude.com/docs/zh-TW/interactive-mode.md#command-history)回想提示並重新提交時，完整的貼上內容會再次傳送，包括在稍後的工作階段中。

早於 [`cleanupPeriodDays`](https://code.claude.com/docs/zh-TW/settings-reference#cleanupperioddays) 的快取檔案會根據[保留掃描規則](https://code.claude.com/docs/zh-TW/claude-directory.md#cleaned-up-automatically)被刪除，因此回想的提示可能參考不再存在的貼上文字。當您提交這樣的提示時，Claude Code 永遠不會傳送字面上的 `[Pasted text #N]` 字串，並顯示通知命名遺失的貼上：

* 在有剩餘文字的純提示中，Claude Code 移除預留位置並傳送剩餘文字。
* 在[殼層模式](https://code.claude.com/docs/zh-TW/interactive-mode.md#shell-mode-with-prefix)命令或 `/` 命令中，移除會改變執行的內容，以及在任何提示中移除留下空白時，Claude Code 取消提交並在輸入中保留原始文字，預留位置仍在其中。刪除預留位置或編輯命令，然後重新提交。

## 使用 Vim 快捷鍵編輯提示詞

Claude Code 包含用於提示詞輸入的 Vim 風格編輯模式。透過 `/config` → Editor mode 啟用它，或在 `~/.claude/settings.json` 中將 [`editorMode`](https://code.claude.com/docs/zh-TW/settings-reference#editormode) 設定為 `"vim"`。將 Editor mode 設回 `normal` 以關閉它。

Vim 模式支援 NORMAL 和 VISUAL 模式動作和運算子的子集，例如 `hjkl` 導航、`v`/`V` 選擇，以及 `d`/`c`/`y` 搭配文字物件。請參閱 [Vim 編輯器模式參考](https://code.claude.com/docs/zh-TW/interactive-mode.md#vim-editor-mode) 以取得完整的快捷鍵表。

Vim 動作無法透過快捷鍵檔案重新對應。若要將兩個按鍵的 INSERT 模式序列（例如 `jj`）對應到 Escape，請在使用者設定中設定 [`vimInsertModeRemaps`](https://code.claude.com/docs/zh-TW/interactive-mode#remap-insert-mode-key-sequences)。

在 INSERT 模式中按 Enter 仍會提交您的提示詞，不同於標準 Vim。在 NORMAL 模式中使用 `o` 或 `O`，或按 Ctrl+J，以插入新行。

## 相關資源

* [互動模式](https://code.claude.com/docs/zh-TW/interactive-mode.md)：完整鍵盤快捷鍵參考和 Vim 快捷鍵表
* [快捷鍵](https://code.claude.com/docs/zh-TW/keybindings.md)：重新對應任何 Claude Code 快捷鍵，包括 Enter 和 Shift+Enter
* [全螢幕渲染](https://code.claude.com/docs/zh-TW/fullscreen.md)：全螢幕模式中捲動、搜尋和複製的詳細資訊
* [Hooks 指南](https://code.claude.com/docs/zh-TW/hooks-guide.md)：Linux 和 Windows 的更多通知 hook 範例
* [疑難排解](https://code.claude.com/docs/zh-TW/troubleshooting.md)：終端機配置外部問題的修復

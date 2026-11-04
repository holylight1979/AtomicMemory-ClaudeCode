<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/accessibility | lastmod: 2026-10-27 | section: Configuration / Interface -->
> 來源：https://code.claude.com/docs/zh-TW/accessibility（官方 zh-TW，lastmod 2026-10-27）｜分類：Configuration › Interface｜EN 摘要：Set up Claude Code for screen readers such as VoiceOver and NVDA, plus settings for screen magnifiers, reduced motion, and colorblind-friendly themes.

# 使用 Claude Code 搭配螢幕閱讀器

> 為 VoiceOver 和 NVDA 等螢幕閱讀器設定 Claude Code，以及螢幕放大鏡、減少動畫和色盲友善主題的設定。

Claude Code 具有螢幕閱讀器模式，可將其視覺終端介面替換為純文字、線性文字。該模式不使用方框、進度動畫和就地重繪，而是列印標記的行，螢幕閱讀器（例如 VoiceOver 或 NVDA）會依序讀取這些行，讓您可以進行完整對話、批准工具權限並從頭到尾檢查輸出。

螢幕閱讀器模式是選擇性加入的。如果您使用螢幕放大鏡、減少動畫或色盲友善主題而不是螢幕閱讀器，請從[無障礙設定](#accessibility-settings)表格設定 `CLAUDE_CODE_ACCESSIBILITY`、`prefersReducedMotion` 或 `theme`。螢幕閱讀器模式只會調整終端介面，因此您不需要在 VS Code 擴充功能的聊天面板中使用它。在 Claude Code v2.1.236 或更新版本上，擴充功能會[向您的螢幕閱讀器宣告聊天活動](https://code.claude.com/docs/zh-TW/vs-code.md#use-a-screen-reader)，無需任何設定。

## 開啟螢幕閱讀器模式

選擇與您使用螢幕閱讀器頻率相符的方法：

* 針對一個工作階段：執行 `claude --ax-screen-reader`。
* 針對從一個 shell 啟動的工作階段：設定 `CLAUDE_AX_SCREEN_READER` 環境變數為 `1`。在 Bash 或 Zsh 中，執行 `export CLAUDE_AX_SCREEN_READER=1`。在 PowerShell 中，執行 `$env:CLAUDE_AX_SCREEN_READER = "1"`。將該行新增至您的 shell 設定檔以保留供未來的 shell 使用。
* 針對機器上的每個工作階段：將 `"axScreenReader": true` 新增至您的使用者[設定檔](https://code.claude.com/docs/zh-TW/settings.md)。此設定適用於任何終端機，包括 VS Code 整合終端機。

如果您結合多種方法，Claude Code 會優先套用 [`--ax-screen-reader`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 旗標而非 [`CLAUDE_AX_SCREEN_READER`](https://code.claude.com/docs/zh-TW/env-vars#variables) 環境變數，並優先套用環境變數而非 [`axScreenReader`](https://code.claude.com/docs/zh-TW/settings-reference#axscreenreader) 設定。

如果您透過 SSH 使用 Claude Code，請在執行 Claude Code 的遠端機器上設定環境變數或設定。

Claude Code 列印的第一行確認模式：`[Screen Reader Mode: on via flag]`、`[Screen Reader Mode: on via env]` 或 `[Screen Reader Mode: on via settings]`。

### 專案設定無法開啟螢幕閱讀器模式

啟動行 `Screen reader mode is off: project settings can't turn it on` 表示專案要求開啟螢幕閱讀器模式，但沒有其他方式將其開啟。無論值為何，Claude Code 都會忽略專案的 `.claude/settings.json` 和 `.claude/settings.local.json` 中的 `axScreenReader` 鍵，以及 `env` 底下的 `CLAUDE_AX_SCREEN_READER` 值。

* **若要開啟此模式**：使用 `--ax-screen-reader` 啟動 Claude Code、在您的 shell 中將 `CLAUDE_AX_SCREEN_READER` 設定為 `1`，或將 `"axScreenReader": true` 新增至您的使用者[設定檔](https://code.claude.com/docs/zh-TW/settings.md)並重新啟動 Claude Code。您不需要變更專案的檔案。開啟此模式後，啟動時會改為顯示[確認行](#turn-on-screen-reader-mode)。
* **如果您不使用螢幕閱讀器**：您不需要執行任何操作。若要停止顯示此行，請將 `"axScreenReader": false` 新增至您的使用者設定檔，或從專案的設定檔中移除 `axScreenReader` 鍵和 `CLAUDE_AX_SCREEN_READER` 變數。

## 關閉螢幕閱讀器模式

反轉開啟模式的任何方法：不使用旗標啟動、取消設定環境變數，或在您的使用者設定檔中將 `axScreenReader` 設定為 `false`。如果您將 `CLAUDE_AX_SCREEN_READER` 設定為 `0`，Claude Code 即使設定為 `true` 也會保持模式關閉。

## 無障礙設定

下表列出每個無障礙選項、您是否將其設定為旗標、環境變數或設定，以及它會變更的內容。

| 選項 | 類型 | 變更的內容 |
| :- | :- | :- |
| [`--ax-screen-reader`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) | 旗標 | 單一工作階段的螢幕閱讀器模式。 |
| [`CLAUDE_AX_SCREEN_READER`](https://code.claude.com/docs/zh-TW/env-vars#variables) | 環境變數 | 從您設定它的殼層啟動的工作階段的螢幕閱讀器模式。 |
| [`axScreenReader`](https://code.claude.com/docs/zh-TW/settings-reference#axscreenreader) | 設定 | 當設為 `true` 時，每個工作階段的螢幕閱讀器模式。 |
| [`CLAUDE_AX_STARTUP_QUIET_MS`](https://code.claude.com/docs/zh-TW/env-vars#variables) | 環境變數 | Claude Code 在確認行之後等待多長時間，然後在螢幕閱讀器模式中繪製第一個提示。需要 Claude Code v2.1.217 或更新版本。 |
| [`CLAUDE_AX_PREPARK_MS`](https://code.claude.com/docs/zh-TW/env-vars#variables) | 環境變數 | 設定後，Claude Code 在螢幕閱讀器模式中寫入新的或變更的行之前，將終端機游標停留在目前行開頭的毫秒數。需要 Claude Code v2.1.233 或更新版本。 |
| [`CLAUDE_CODE_ACCESSIBILITY`](https://code.claude.com/docs/zh-TW/env-vars#variables) | 環境變數 | 當您將其設定為 `1` 時，終端游標對於螢幕放大鏡（例如 macOS Zoom）保持可見。游標跟隨輸入插入符號，在 Claude Code v2.1.218 或更新版本上，跟隨功能表和面板（例如 `/config` 和 `/plugin`）中的反白列。 |
| [`prefersReducedMotion`](https://code.claude.com/docs/zh-TW/settings-reference#prefersreducedmotion) | 設定 | 當設為 `true` 時，減少或沒有微調器、閃爍和其他動畫。 |
| [`theme`](https://code.claude.com/docs/zh-TW/settings-reference#theme) | 設定 | 介面顏色，包括色盲友善的 `dark-daltonized` 和 `light-daltonized` 主題。您也可以使用 [`/theme`](https://code.claude.com/docs/zh-TW/commands#all-commands) 選擇一個。 |
| [`preferredNotifChannel`](https://code.claude.com/docs/zh-TW/settings-reference#preferrednotifchannel) | 設定 | 當值為 `"terminal_bell"` 時，在螢幕閱讀器模式外的終端鈴聲，當 Claude 在等待您時。 |

## 您的螢幕閱讀器聽到的內容

在螢幕閱讀器模式中，Claude Code 寫入平面文字：

* 介面框架沒有方框繪製字元
* 沒有僅限顏色的提示
* 沒有未變更內容的重繪。進度微調器呈現為靜態文字
* Claude 回覆中的表格讀作 `Header: value` 句子，而不是方框字元網格
* 差異以純文字讀出，逐行以 `+` 和 `-` 標記新增和移除的行，因此您可以在回答檔案編輯核准提示之前，先聽到提議的變更

Claude Code 將其列印到終端機捲軸的所有內容都保留下來，因此您可以使用螢幕閱讀器的檢視命令或終端機的搜尋功能重新閱讀較早的回合。Claude Code 在螢幕閱讀器模式中忽略 [`tui` 設定](https://code.claude.com/docs/zh-TW/settings-reference#tui)。除了在[已知限制](#known-limitations)下列出的附加背景工作階段外，它列印捲動文字而不是[全螢幕呈現](https://code.claude.com/docs/zh-TW/fullscreen.md)。

Claude Code 在啟動時列印[確認行](#turn-on-screen-reader-mode)後，會等待 3 秒再繪製提示，以便您的螢幕閱讀器可以完成該行。按任何鍵結束等待。若要變更等待的長度，請設定 [`CLAUDE_AX_STARTUP_QUIET_MS`](https://code.claude.com/docs/zh-TW/env-vars#variables)。

逐字稿中的每條訊息都以您的螢幕閱讀器宣佈的標籤開頭，命名其內容：您的訊息、Claude 的回覆和思考、工具活動、錯誤和警告以及提示。這些標籤也可搜尋，因此您可以透過搜尋終端機的捲軸在逐字稿的各個部分之間跳轉：

| 標籤 | 意義 |
| :- | :- |
| `you:` | 您的訊息 |
| `claude:` | Claude 的回覆 |
| `thinking:` | Claude 的思考 |
| `tool:` | 工具活動，例如檔案編輯或命令執行 |
| `tool error:` | 失敗的工具 |
| `error:` | 對話中的錯誤，例如失敗的 API 請求 |
| `warning:` | Claude Code 的警告，例如切換到備援模型 |
| `Permission Required:` | 等待您回答的權限提示 |
| `Cost:` | Claude Code 結束時的工作階段成本摘要（如果您的帳戶[顯示成本](https://code.claude.com/docs/zh-TW/costs.md)） |

Claude Code 將終端機游標保持在輸入插入點上，因此您的螢幕閱讀器的讀取目前行命令會讀取您正在編輯的提示詞。當您在輸入行末尾輸入時，或在該處按 `Backspace`，Claude Code 只寫入變更的字元。您的螢幕閱讀器只會回應這些字元。

當您使用其中一個[文字編輯快捷鍵](https://code.claude.com/docs/zh-TW/interactive-mode.md#text-editing)刪除單字或行時，Claude Code 會宣佈已刪除的文字：

* 使用 `Ctrl+W` 或 `Alt+D` 刪除單字，或在 macOS 上使用 `Option+Delete` 或在 Windows 上使用 `Ctrl+Backspace`
* 使用 `Ctrl+U` 或 `Cmd+Backspace` 刪除到行的開始
* 使用 `Ctrl+K` 刪除到行的結尾

當您使用 `Shift+Tab` 循環[權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md)時，Claude Code 會宣佈您切換到的權限模式，例如 `[plan mode on]` 或 `[accept edits on]`。Claude Code 列印公告一次，不會在稍後的重繪上重複。

### 閱讀較早的輸出而不失去目前位置

如果您在閱讀較早的輸出時，螢幕閱讀器跳回提示，這是因為它正在跟隨終端機游標。Claude Code 每次寫入新文字時，都會將終端機游標移回提示。

若要在閱讀時保持目前位置，請停止讓螢幕閱讀器跟隨終端機游標。在 NVDA 中，按 `NVDA+6` 可停止檢視游標跟隨終端機游標。再按一次 `NVDA+6` 即可重新開啟跟隨。

### 在回合之間跳轉

Claude Code 在回合邊界處發出 OSC 133 shell 整合標記，因此您終端機的跳轉到上一個提示鍵在回合之間移動，而無需讀取整個逐字稿：

* iTerm2：Cmd+Shift+Up
* VS Code 終端機：Windows 上的 Ctrl+Up，macOS 上的 Cmd+Up
* Windows Terminal：預設沒有鍵；在其設定中繫結 `scrollToMark` 動作
* Kitty 和 Ghostty：檢查終端機的文件以了解其跳轉到提示鍵

macOS Terminal 不對標記進行操作，Claude Code 在 WezTerm 中不發出標記。在這些終端機中，改為搜尋捲軸中的 `you:` 標籤。

## 回答選單和提示

在螢幕閱讀器模式中，您通常使用方向鍵導覽的選單（包括權限提示）會變成編號清單。Claude Code 會將每個選項宣布為編號行，然後是 `Select with numbers` 提示，該提示會說明有效範圍。輸入您想要的選項編號，然後按 Enter。

* 按 Escape 鍵取消提示以 `or Escape to cancel` 結尾的選單。
* 如果您輸入的編號不在清單上，Claude Code 會宣布有效範圍，讓您重新嘗試。

[`/effort`](https://code.claude.com/docs/zh-TW/model-config#adjust-effort-level) 選擇器在螢幕閱讀器模式外是滑塊，在螢幕閱讀器模式中會變成相同類型的編號清單。

是或否提示要求輸入答案，而不是兩選項選單。回答 `y` 或 `n`，然後按 Enter。`yes` 和 `no` 也可以。

## 聽取 Claude Code 需要您時的提示

在螢幕閱讀器模式中，當 Claude Code 需要您的注意時，它會發出終端鈴聲，因此您不必持續檢查文字記錄。鈴聲會在以下情況響起：

* Claude 完成回覆
* 提示或對話框需要您的回答，例如權限提示
* 執行時間超過 5 秒的工具完成

鈴聲是您終端的標準警報。若要將其靜音，請變更您終端應用程式中的鈴聲設定。在螢幕閱讀器模式以外，將 [`preferredNotifChannel`](https://code.claude.com/docs/zh-TW/settings-reference#preferrednotifchannel) 設定為 `"terminal_bell"` 以在 Claude 等待您時取得[類似的鈴聲](https://code.claude.com/docs/zh-TW/terminal-config.md#get-a-terminal-bell-or-notification)。

## 已知限制

某些行為未針對螢幕閱讀器模式進行調整：

* 當螢幕閱讀器執行時，螢幕閱讀器模式不會自動開啟。
* Claude Code 不會宣佈您透過命令進行的權限模式變更，例如使用 `/plan` 進入 [plan mode](https://code.claude.com/docs/zh-TW/permission-modes.md#analyze-before-you-edit-with-plan-mode)。
* 使用 `claude attach` 或從代理檢視附加到[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)會進入終端的替代螢幕，該螢幕沒有原生回滾。這與[其他附加工作階段的行為相同](https://code.claude.com/docs/zh-TW/fullscreen.md)。若要返回，請在空提示上按左箭頭，或如果對話框有焦點，請按 Ctrl+Z。
* Claude Code 在其在結束時列印的摘要中宣佈成本，而不是按回合。
* 螢幕閱讀器模式不會使用 `-p` 旗標變更[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)。非互動模式已寫入純文字，並保持為指令碼的替代方案。

## 報告問題

如果螢幕閱讀器、放大鏡或終端出現問題，請在 [Claude Code 問題追蹤器](https://github.com/anthropics/claude-code/issues)上開啟問題，並在標題中提及您的輔助技術。在報告中包含您的作業系統、終端應用程式以及輔助技術名稱和版本。

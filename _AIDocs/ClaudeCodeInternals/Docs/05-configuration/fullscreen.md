<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/fullscreen | lastmod: 2026-10-21 | section: Configuration / Interface -->
> 來源：https://code.claude.com/docs/zh-TW/fullscreen（官方 zh-TW，lastmod 2026-10-21）｜分類：Configuration › Interface｜EN 摘要：Enable a smoother, flicker-free rendering mode with mouse support and stable memory usage in long conversations.

# 全螢幕渲染

> 啟用更平順、無閃爍的渲染模式，具有滑鼠支援和穩定的記憶體使用，適用於長對話。

> [!NOTE]
>
> 全螢幕渲染是一個[研究預覽](#research-preview)。無論您是[預設在全螢幕或在經典渲染器中啟動](#fullscreen-by-default)取決於您的設定。在您目前的對話中執行 `/tui fullscreen` 或 `/tui default` 以切換。行為可能會根據回饋而改變。

全螢幕渲染是 Claude Code CLI 的替代渲染路徑，可消除閃爍、在長對話中保持記憶體使用平穩，並新增滑鼠支援。它在終端的替代螢幕緩衝區上繪製介面，就像 `vim` 或 `htop` 一樣，並且只渲染目前可見的訊息。這減少了每次更新時傳送到終端的資料量。

在渲染吞吐量是瓶頸的終端模擬器中，差異最為明顯，例如 VS Code 整合終端、tmux 和 iTerm2。如果您的終端捲動位置在 Claude 工作時跳到頂部，或者工具輸出串流進來時螢幕閃爍，此模式可以解決這些問題。

> [!NOTE]
>
> 全螢幕一詞描述的是 Claude Code 如何接管終端的繪製表面，就像 `vim` 一樣。它與最大化終端視窗無關，並且在任何視窗大小下都能運作。

## 啟用全螢幕渲染

在任何 Claude Code 對話中執行 `/tui fullscreen`。CLI 會儲存 [`tui` 設定](https://code.claude.com/docs/zh-TW/settings-reference#tui)並重新啟動進入全螢幕模式，您的對話保持完整，因此您可以在工作階段中途切換而不會失去上下文。執行 `/tui default` 以切換回經典渲染器，或執行 `/tui` 不帶任何引數以列印哪個渲染器處於活動狀態。

在[螢幕閱讀器模式](https://code.claude.com/docs/zh-TW/accessibility.md)中，Claude Code 一律使用經典渲染器，除了附加的[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)仍會以全螢幕渲染。如果您在任何其他工作階段中執行 `/tui fullscreen`，Claude Code 會列印說明而不是切換，並且不會變更已儲存的 `tui` 設定。

Claude Code 會將這些內容帶入重新啟動的工作階段：

* 對話在螢幕上顯示的樣子。在執行 [`/rewind`](https://code.claude.com/docs/zh-TW/checkpointing#rewind-and-summarize) 之後，這表示：
  * 如果您在工作階段中較早倒帶，Claude Code 會從倒帶點而不是儲存在磁碟上的較長文字記錄重新啟動。例如，如果您倒帶超過最後三則訊息，重新啟動的工作階段會在沒有這些訊息的情況下開啟
  * 如果您倒帶到第一則訊息之前，Claude Code 會以空白對話重新啟動
* 您的[權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md)和[努力等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)
* 您上次使用 [`/model`](https://code.claude.com/docs/zh-TW/model-config#setting-your-model) 選擇的模型
* 您使用 [`--allowed-tools` 或 `--disallowed-tools`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 傳遞的規則，以及您的 `--agent`、`--agents`、`--append-system-prompt` 和 `--system-prompt-snapshot` 旗標
* 您啟動時使用的 `--chrome` 或 `--no-chrome` 旗標，讓 [Chrome 整合](https://code.claude.com/docs/zh-TW/chrome.md)依照您為此工作階段所做的選擇保持開啟或關閉

Claude Code 會拒絕重新啟動，如果工作階段有它無法傳遞給重新啟動程序的限制。它無法傳遞的限制包括：

* 啟動旗標，例如 [`--system-prompt`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 替換、[`--tools`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 允許清單或 [`--setting-sources`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags)
* [hook 或 SDK 權限更新](https://code.claude.com/docs/zh-TW/hooks.md#permission-update-entries)為此工作階段新增的拒絕或詢問規則

在這種情況下，Claude Code 會列印 [`Cannot switch renderers in this session`](https://code.claude.com/docs/zh-TW/errors#cannot-switch-renderers-in-this-session) 及其原因。它不會切換或儲存任何內容。

您也可以在啟動 Claude Code 之前設定 `CLAUDE_CODE_NO_FLICKER` 環境變數：

```bash theme={null}
CLAUDE_CODE_NO_FLICKER=1 claude
```

如需了解 [`tui`](https://code.claude.com/docs/zh-TW/settings-reference#tui) 設定和變數在兩者都設定時如何結合，請參閱該設定的項目。在[全螢幕啟動失敗](#fullscreen-renderer-didnt-finish-starting)後，Claude Code 仍會遵守變數但不會遵守設定。`/tui` 命令會從重新啟動的程序中清除 `CLAUDE_CODE_NO_FLICKER`，以便它寫入的設定生效。

### 預設全螢幕

附加的[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)會以全螢幕渲染，[螢幕閱讀器模式](https://code.claude.com/docs/zh-TW/accessibility.md)中的其他工作階段會使用經典渲染器。否則，Claude Code 會在符合您設定的此表格第一列的渲染器中啟動您：

| 您的情況 | 您啟動的渲染器 |
| :- | :- |
| 您設定了 [`CLAUDE_CODE_DISABLE_ALTERNATE_SCREEN=1`](https://code.claude.com/docs/zh-TW/env-vars) 或 `CLAUDE_CODE_NO_FLICKER=0` | 經典 |
| 您設定了 `CLAUDE_CODE_NO_FLICKER=1` | 全螢幕 |
| Claude Code [在此機器上全螢幕啟動失敗後關閉了全螢幕](#fullscreen-renderer-didnt-finish-starting) | 經典 |
| 您在 iTerm2 的 [`tmux -CC` 整合模式](#use-with-tmux)中，或您透過 SSH 連線到在 Windows 上執行的 Claude Code | 經典 |
| 您儲存了 [`tui` 設定](https://code.claude.com/docs/zh-TW/settings-reference#tui) | 設定命名的渲染器 |
| 您的工作階段不會[從 Anthropic 擷取功能旗標](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)，且 Claude Code 已停止在此機器上提供啟動對話 | 經典 |
| 您的工作階段不會從 Anthropic 擷取功能旗標，且此機器的第一次 Claude Code 啟動執行了 v2.1.239 或更新版本 | 全螢幕 |
| 您的工作階段會從 Anthropic 擷取功能旗標，且您在 2026 年 5 月 6 日或之後首次使用 Claude Code | 全螢幕 |
| 其他任何情況 | 經典 |

不會擷取功能旗標的工作階段包括透過 [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md)、[Google Cloud 的 Agent Platform](https://code.claude.com/docs/zh-TW/google-vertex-ai.md) 或 [Microsoft Foundry](https://code.claude.com/docs/zh-TW/microsoft-foundry.md) 的工作階段，以及關閉遙測的工作階段。

如果您在經典渲染器中啟動且尚未儲存 `tui` 設定，Claude Code 可能會在啟動時開啟對話框提供切換：

* 如果您接受，Claude Code 會以與 `/tui fullscreen` 相同的方式重新啟動，帶著相同的工作階段狀態，並在重新啟動的工作階段[成功啟動](#fullscreen-renderer-didnt-finish-starting)後儲存設定。
* 如果您選擇**稍後**，Claude Code 不會在此機器上再次提供。
* Claude Code 在顯示對話框三次啟動後停止提供，無論是否回答。

## 變更內容

全螢幕渲染改變了 CLI 如何繪製到您的終端。輸入框保持固定在螢幕底部，而不是在輸出串流進來時移動。如果輸入在 Claude 工作時保持不動，則全螢幕渲染處於活動狀態。只有可見的訊息保留在渲染樹中，因此無論對話長度如何，記憶體都保持恆定。

因為對話存在於替代螢幕緩衝區而不是終端的捲動回溯，所以有幾件事的運作方式不同：

| 之前 | 現在 | 詳細資訊 |
| :- | :- | :- |
| `Cmd+f` 或 tmux 搜尋來尋找文字 | `Ctrl+o` 進入文字記錄模式，然後 `/` 搜尋或 `[` 寫入捲動回溯 | [搜尋和檢閱對話](#search-and-review-the-conversation) |
| 終端的原生點擊並拖曳來選擇和複製 | 應用程式內選擇，在滑鼠釋放時自動複製 | [使用滑鼠](#use-the-mouse) |
| `Cmd` 點擊來開啟 URL | macOS 上的 `Cmd` 點擊，其他地方的 `Ctrl` 點擊 | [使用滑鼠](#use-the-mouse) |

如果滑鼠捕捉干擾您的工作流程，您可以[關閉它](#keep-native-text-selection)，同時保持無閃爍渲染。

## 使用滑鼠

全螢幕渲染會擷取滑鼠事件，並在 Claude Code 內部處理它們：

* **在提示輸入欄中點擊**，以在您輸入的文字中的任何位置放置游標。
* **點擊 `/` 命令或 `@` 檔案清單中的建議**，以接受它。懸停會突顯游標下的列。
* **點擊選擇功能表中的選項**，以選擇它。這涵蓋權限提示、`/model`、`/config` 和其他顯示選項清單的對話框。
* **點擊多選功能表中的選項**，以切換它，然後點擊提交按鈕以確認您的選擇。點擊自由文字列（例如多選題中的 `Other` 列）會聚焦其輸入欄位，以便您可以輸入答案。
* **點擊 `/config` 面板中的設定值**，以變更它，並使用滑鼠滾輪捲動設定清單。需要 Claude Code v2.1.271 或更新版本。
* **使用滑鼠滾輪捲動選擇或多選功能表**，當它有超過一次顯示的選項時，例如短終端機視窗中的 `/model` 清單。當指標在其選項上方時，滾輪會捲動清單。需要 Claude Code v2.1.280 或更新版本。
* **使用捲軸捲動溢出的清單。** 在清單面板（例如 `/skills`、`/mcp` 和 `/plugin` 的已安裝清單）中，當指標位於列數超過可容納範圍的清單上方時，捲軸會出現在該清單旁邊。點擊軌道以跳至該點，或拖曳滑塊。需要 Claude Code v2.1.281 或更新版本。
  * 當捲軸兩端有 `↑` 和 `↓` 箭頭時，點擊箭頭以捲動單一列，或按住箭頭以持續捲動。箭頭需要 Claude Code v2.1.286 或更新版本。
* **點擊清單邊緣的 `↑ N more` 或 `↓ N more` 列**，以跳至清單的該端，而不選擇任何選項。需要 Claude Code v2.1.286 或更新版本。
* **點擊已摺疊的工具結果**，以展開它並查看完整輸出。再次點擊以摺疊。工具呼叫及其結果會一起展開。只有有更多內容要顯示的訊息才可點擊。
  * 點擊也會展開 `!` shell 命令的輸出，無論是較舊的截斷結果或命令執行時的即時進度列。需要 Claude Code v2.1.257 或更新版本。
  * 點擊也會展開當寄件者是[隊友](https://code.claude.com/docs/zh-TW/agent-teams.md)或在您的工作階段中執行的另一個 agent 時的暗淡 `Message from @<sender>` 列。
* **在 macOS 上按住 `Cmd`，或在 Linux 和 Windows 上按住 `Ctrl`，然後點擊 URL 或檔案路徑**，以開啟它。純 `http://` 和 `https://` URL 會在您的瀏覽器中開啟。當 Claude Code 處理點擊時，工具輸出中的檔案路徑（例如在 Edit 或 Write 後列印的路徑）會在您的檔案管理員中開啟，並選取該檔案。不使用修飾鍵的純點擊不會開啟連結，符合原生終端機行為。
  * 在 Linux 和 WSL 上，點擊檔案路徑需要提供 `org.freedesktop.FileManager1` D-Bus 介面的檔案管理員。若沒有，則不會開啟任何項目。
  * Claude Code 會將網路 (UNC) 路徑（例如 `\\server\share\file.ts`）呈現為純文字，沒有連結，因為開啟網路路徑可能會將您的 Windows 憑證傳送到它命名的主機。
  * 某些 macOS 終端機會將 `Cmd`+點擊轉發給執行中的應用程式，而不是自己開啟連結，而終端機滑鼠協定無法編碼 `Cmd` 鍵，因此 Claude Code 會收到純點擊。在 Ghostty 以及 macOS 上的 Warp 中，Claude Code 會偵測到這一點，並讓純點擊連結開啟它，而按住 `Cmd` 仍然有效。
  * 在 VS Code 整合終端機和類似的 xterm.js 型終端機中，Claude Code 會遵循終端機自己的連結處理程式，該處理程式使用相同的手勢。
* **點擊並拖曳**，以在對話中的任何位置選擇文字。雙擊會選擇一個單字，符合 iTerm2 的單字邊界，因此檔案路徑會選擇為一個單位。雙擊 URL 會選擇整個 URL，包括配置。三擊會選擇該列。
* **使用滑鼠滾輪滾動**，以在對話中移動。

選定的文字會在滑鼠釋放時自動複製到您的剪貼簿。若要關閉此功能，請在 `/config` 中切換「選擇時複製」。

關閉「選擇時複製」後，按 `Ctrl+Shift+c` 以手動複製。在支援 kitty 鍵盤協定的終端機上（例如 kitty、WezTerm、Ghostty 和 iTerm2），`Cmd+c` 也有效。如果您有作用中的選擇，`Ctrl+c` 會複製而不是取消。

有作用中的選擇時，按住 `Shift` 並按箭頭鍵，以從鍵盤擴展它。`Shift+↑` 和 `Shift+↓` 會在選擇到達頂部或底部邊緣時滾動檢視區。`Shift+Home` 和 `Shift+End` 會擴展到目前列的開始或結束。

在正常提示檢視中，作用中選擇發生的情況取決於您按下的鍵：

* **`Esc`**：Claude Code 執行該鍵的常用動作，例如中斷執行中的回應或關閉開啟的對話框，而選擇保持突顯。
* **`PgUp`、`PgDn`、`Ctrl+Home`、`Ctrl+End` 或 `Shift`、`Alt` 或 `Option` 或 `Cmd`、`Win` 或 `Super` 搭配箭頭、`Home` 或 `End` 鍵**：選擇保持。
* **任何其他鍵，包括純箭頭鍵、`Enter` 和輸入的字元**：Claude Code 會清除選擇。
* **繫結至 [`selection:clear`](https://code.claude.com/docs/zh-TW/keybindings#scroll-actions) 的鍵**：Claude Code 會清除選擇，即使該鍵是 `Esc` 或其他通常保持選擇的鍵。該動作沒有預設繫結。

在[逐字稿模式](#search-and-review-the-conversation)中，列在該處的導覽鍵也會保持選擇。

## 捲動對話

全螢幕渲染會處理應用程式內的捲動。使用這些快捷鍵進行導航：

| 快捷鍵 | 動作 |
| :- | :- |
| `PgUp` / `PgDn` | 向上或向下捲動半個螢幕 |
| `Ctrl+Home` | 跳至對話的開始 |
| `Ctrl+End` | 跳至最新訊息並重新啟用自動跟隨 |
| 滑鼠滾輪 | 一次捲動幾行 |

如果您關閉已[壓縮](https://code.claude.com/docs/zh-TW/context-window.md#what-survives-compaction)的工作階段並[繼續](https://code.claude.com/docs/zh-TW/sessions.md#what-a-resumed-session-restores)該工作階段，向上捲動會停在 `Conversation compacted` 列，而您較早的訊息會保留在磁碟上的[逐字稿檔案](https://code.claude.com/docs/zh-TW/sessions.md#where-transcripts-are-stored)中。若要取得這些訊息中的細節，請要求 Claude 在該檔案中查詢。

在沒有專用 `PgUp`、`PgDn`、`Home` 或 `End` 鍵的鍵盤上（例如 MacBook 鍵盤），請按住 `Fn` 並使用方向鍵：`Fn+↑` 傳送 `PgUp`、`Fn+↓` 傳送 `PgDn`、`Fn+←` 傳送 `Home`、`Fn+→` 傳送 `End`。`Ctrl+Fn+→` 在 macOS 上無法到達 Claude Code，因此 MacBook 鍵盤預設沒有可用的跳至底部快捷鍵組合。請改用以下其中一個選項：

* 點擊[跳至底部按鈕](#auto-follow)。
* 使用滑鼠滾輪捲動到底部以繼續跟隨。
* 將 `scroll:bottom` 重新繫結到您的鍵盤可以傳送的快捷鍵組合。

這些動作可重新繫結。請參閱[捲動動作](https://code.claude.com/docs/zh-TW/keybindings.md#scroll-actions)以取得完整的動作名稱清單，包括沒有預設繫結的半頁和全頁變體。

當您向上捲動時，對話頂部會出現一個暗淡的標題列，顯示已捲動到檢視上方的最新提示。點擊該列以跳至該提示。

### 自動跟隨

向上捲動會暫停自動跟隨，以便新輸出不會將您拉回底部。當您向上捲動時，`Jump to bottom` 按鈕會浮動在逐字稿的底部邊緣，當新輸出到達時會顯示計數，例如 `3 new messages`。點擊它、按 `Ctrl+End` 或捲動到底部以繼續跟隨。

當自動跟隨暫停時，當回應完成串流時，檢視也會保持在您捲動的位置。

按鈕的鍵盤提示反映您的鍵盤可以傳送的內容。在 macOS 上，它建議點擊或 `Fn+↓` 捲動，因為 `Ctrl+End` 無法從 Mac 鍵盤到達 Claude Code。重新繫結 [`scroll:bottom`](https://code.claude.com/docs/zh-TW/keybindings#scroll-actions)，按鈕會在每個平台上顯示您的快捷鍵組合。

在終端機太窄而無法容納完整標籤的情況下，按鈕會縮短提示，而不是換行到文字記錄行下方。

若要完全關閉自動跟隨，使檢視保持在您留下的位置，請開啟 `/config` 並將自動捲動設定為關閉。停用自動捲動後，檢視永遠不會自動跳至底部。需要回應的權限提示和其他對話框仍會捲動到檢視中，無論此設定如何。

### 滑鼠滾輪捲動

滑鼠滾輪捲動需要您的終端機將滑鼠事件轉發給 Claude Code。大多數終端機在應用程式要求時都會執行此操作。iTerm2 將其設定為每個設定檔的設定：如果滾輪沒有反應但 `PgUp` 和 `PgDn` 有效，請開啟 \[設定] → \[設定檔] → \[終端機] 並開啟 \[啟用滑鼠報告]。點擊展開和文字選取也需要相同的設定。

如果滑鼠滾輪捲動感覺很慢，您的終端機可能會以沒有乘數的方式每個物理刻度傳送一個捲動事件。某些終端機（例如 Ghostty 和啟用更快捲動的 iTerm2）已經放大滾輪事件。其他終端機（包括 VS Code 整合終端機）每個刻度傳送一個事件。Claude Code 無法偵測哪個。

設定 `CLAUDE_CODE_SCROLL_SPEED` 以乘以基本捲動距離：

```bash theme={null}
export CLAUDE_CODE_SCROLL_SPEED=3
```

值 `3` 符合 `vim` 和類似應用程式中的預設值。此設定接受任何正值，最高為 20，包括低於 1 的小數值，例如 `0.25`，以減緩已經放大滾輪事件的終端機中的加速觸控板和滾輪捲動。

若要以互動方式調整捲動速度，請執行 `/scroll-speed`。在對話框開啟時捲動，即可立即感受變化。按 `←` 和 `→` 調整速度，按 `r` 重設為自動偵測的預設值，按 `Enter` 儲存。對話框以整數步進到 10，在支援更精細控制的終端機上，它也提供四分之一步進到 0.25。

該命令寫入與 `CLAUDE_CODE_SCROLL_SPEED` 環境變數設定相同的值，持久化到 `~/.claude/settings.json`。對話框的最大值為 10：如果您透過環境變數設定更高的值，對話框會顯示 10，從對話框儲存會持久化 10。此命令在 JetBrains IDE 終端機中不可用。

與基本速度分開，當您快速旋轉滾輪時，Claude Code 會加速捲動速率，因此快速旋轉覆蓋的距離比相同數量的慢刻度更遠。若要關閉加速並保持每個刻度的恆定速率，請在 [`settings.json`](https://code.claude.com/docs/zh-TW/settings-reference#all-settings) 中將 `wheelScrollAccelerationEnabled` 設定為 `false`。此設定需要 Claude Code v2.1.174 或更新版本。

### 在 JetBrains IDE 終端機中捲動

在 JetBrains IDE 終端機中，Claude Code 應用其自己的捲動處理並忽略 `CLAUDE_CODE_SCROLL_SPEED`。終端機以比其他模擬器高得多的速率傳送捲動事件，因此在其他地方調整的乘數會在此處超出。

在 2025.2 中，終端機也有捲動滾輪錯誤，會產生虛假的方向鍵和錯誤方向事件。Claude Code 在執行時偵測這些並自動減輕它們，因此觸控板和滑鼠滾輪捲動無需設定即可工作。為了獲得最佳捲動體驗，請升級到 2025.3 或更新版本。如果 Claude Code 偵測到該錯誤，它會在您第一次捲動時顯示提示。

## 搜尋和檢視對話

`Ctrl+o` 在一般提示和文字記錄模式之間切換。

如需更簡潔的檢視，只顯示您最後的提示、工具呼叫的單行摘要及編輯 diffstats，以及最終回應，請執行 `/focus`。此設定會在工作階段之間保留。再次執行 `/focus` 可將其關閉。

文字記錄模式獲得 `less` 風格的導覽和搜尋：

| 快捷鍵 | 動作 |
| :- | :- |
| `/` | 開啟搜尋。輸入以尋找符合項目，按 `Enter` 接受，按 `Esc` 取消並還原您的捲動位置 |
| `n` / `N` | 跳至下一個或上一個符合項目。在您關閉搜尋列後有效 |
| `j` / `k` 或 `↑` / `↓` | 捲動一行 |
| `g` / `G` 或 `Home` / `End` | 跳至頂部或底部 |
| `{` / `}` | 跳至上一個或下一個提示 |
| `Ctrl+u` / `Ctrl+d` | 捲動半頁 |
| `Ctrl+b` / `Ctrl+f` 或 `Space` / `b` | 捲動整頁 |
| `Ctrl+o`、`Esc` 或 `q` | 結束文字記錄模式並返回提示 |

您終端機的 `Cmd+f` 和 tmux 搜尋看不到對話，因為它位於替代螢幕緩衝區中，而不是原生捲動回溯。若要將內容交回您的終端機，請先按 `Ctrl+o` 進入文字記錄模式，然後：

* **`[`**：將完整對話寫入您終端機的原生捲動回溯緩衝區，所有工具輸出已展開。對話現在是您終端機中的普通文字，因此 `Cmd+f`、tmux 複製模式和任何其他原生工具都可以搜尋或選取它。長工作階段在進行此操作時可能會暫停片刻。這會持續到您使用 `Esc` 或 `q` 結束文字記錄模式為止，這會讓您返回全螢幕呈現。下一個 `Ctrl+o` 會重新開始。
* **`v`**：將對話寫入暫存檔案並在 `$VISUAL` 或 `$EDITOR` 中開啟它。

## 在差異面板中觀看您的變更

在全螢幕渲染中，[`/diff`](https://code.claude.com/docs/zh-TW/interactive-mode#review-changes-with-%2Fdiff) 會在對話旁邊開啟一個面板，因此您可以在 Claude 工作時觀看變更累積。[差異面板](https://code.claude.com/docs/zh-TW/interactive-mode.md#diff-panel)涵蓋了它顯示的內容、它何時會自行開啟、如何保持它關閉，以及如何變更它比較的對象。

## 清除對話

執行 `/clear` 以開始新的對話。

若顯示看起來亂碼或部分空白，請按 `Ctrl+L` 重新繪製螢幕。重新繪製會保留對話和您的輸入。

當您的終端機將 `Cmd+K` 傳遞給 Claude Code 時，它的作用與 `Ctrl+L` 相同。iTerm2 和 Terminal.app 會自行處理 `Cmd+K` 並清除自己的螢幕，Claude Code 會偵測到已清除的螢幕並重新繪製對話。在 v2.1.280 之前，從 v2.1.260 開始，按 `Ctrl+L` 或 `Cmd+K`（到達 Claude Code 時）會在全螢幕渲染中清除螢幕。在 v2.1.238 之前，在兩秒內按兩次 `Ctrl+L` 會執行 `/clear`。

## 與 tmux 搭配使用

全螢幕渲染在 tmux 內可以運作，但有三項注意事項。

滑鼠滾輪捲動需要 tmux 的滑鼠模式。如果您的 `~/.tmux.conf` 尚未啟用此功能，請新增以下這一行並重新載入您的設定：

```bash theme={null}
set -g mouse on
```

沒有滑鼠模式的情況下，滾輪事件會傳送到 tmux 而不是 Claude Code。使用 `PgUp` 和 `PgDn` 進行鍵盤捲動在任一情況下都可以運作。如果 Claude Code 偵測到 tmux 但滑鼠模式已關閉，它會在啟動時列印一次性提示。

全螢幕渲染與 iTerm2 的 tmux 整合模式不相容，該模式是您使用 `tmux -CC` 進入的模式。在整合模式中，iTerm2 會將每個 tmux 窗格渲染為原生分割，而不是讓 tmux 繪製到終端機。替代螢幕緩衝區和滑鼠追蹤在該處無法正確運作：滑鼠滾輪沒有作用，雙擊可能會損毀終端機狀態。請勿在 `tmux -CC` 工作階段中啟用全螢幕渲染。在 iTerm2 內的常規 tmux（不含 `-CC`）可以正常運作。

tmux 3.6 系列及更早版本不實作同步輸出，因此在這些版本下，您在重繪期間可能會看到比直接在終端機中執行 Claude Code 時更多的閃爍。Claude Code 在啟動時會探測終端機以尋求同步輸出支援，並在終端機報告支援時使用它。如果您在 tmux 下看到閃爍，請升級到最新的 tmux 或在 tmux 外的自己的終端機標籤中執行 Claude Code。

## 保持原生文字選取

滑鼠捕捉是最常見的摩擦點，特別是在 SSH 或 tmux 內部。當 Claude Code 捕捉滑鼠事件時，您終端機的原生選取複製功能會停止運作。您使用點擊並拖曳進行的選取存在於 Claude Code 內部，而不是在您終端機的選取緩衝區中，因此 tmux 複製模式、Kitty 提示和類似工具看不到它。

Claude Code 會將選取內容寫入您的系統剪貼簿，它使用的路徑取決於您的設定。在本機工作階段中，它會執行原生剪貼簿工具：

* **macOS**: `pbcopy`
* **Linux**: Wayland 上的 `wl-copy`，或 X11 上已安裝的 `xclip` 或 `xsel`。Claude Code 會同時寫入剪貼簿和 PRIMARY 選取，因此中鍵貼上可以運作。
* **Windows 和 WSL**: PowerShell `Set-Clipboard`

在 tmux 內部，它也會寫入 tmux 貼上緩衝區。透過 SSH，它會回退到 OSC 52 逃脫序列。在 GNU screen 內部，Claude Code 也會將長選取複製到剪貼簿。在 v2.1.219 之前，如果您複製的選取長度超過大約 570 個字元，GNU screen 會將 base64 文字列印到視窗中。Claude Code 會在每次複製後列印一個提示，告訴您它使用了哪個路徑。

某些終端機預設會阻止 OSC 52。iTerm2 會阻止它，直到您開啟 Settings → General → Selection → Applications in terminal may access clipboard；在 iTerm2 中執行 [`/terminal-setup`](https://code.claude.com/docs/zh-TW/terminal-config) 會為您啟用此功能。

若要進行一次性原生選取，要使用的按鍵取決於您的終端機：

* **Terminal.app**: `Fn`
* **iTerm2**: `Option`
* **VS Code、Cursor 和 Devin Desktop**: `Shift`，或在啟用 `terminal.integrated.macOptionClickForcesSelection` 設定的 macOS 上使用 `Option`
* **大多數其他終端機**: `Shift`

按住該按鍵同時點擊並拖曳。您的終端機會自行處理選取，而不是將其傳遞給 Claude Code，因此複製快捷鍵如 `Cmd+C` 可以在您選取的內容上運作。Claude Code 也會在其螢幕上提示中顯示正確的按鍵。

透過 SSH 或在 tmux 內部，Claude Code 無法總是偵測您連接的終端機，因此提示會列出候選按鍵。

如果您一直依賴原生選取，請設定 `CLAUDE_CODE_DISABLE_MOUSE=1` 以選擇退出滑鼠捕捉，同時保持無閃爍渲染和平面記憶體：

```bash theme={null}
CLAUDE_CODE_NO_FLICKER=1 CLAUDE_CODE_DISABLE_MOUSE=1 claude
```

停用滑鼠捕捉後，使用 `PgUp`、`PgDn`、`Ctrl+Home` 和 `Ctrl+End` 的鍵盤捲動仍然有效，您的終端機會原生處理選取。您會失去點擊定位游標、點擊展開工具輸出、URL 點擊和 Claude Code 內部的滾輪捲動。

若要保持滾輪捲動但關閉點擊、拖曳和懸停處理，請改為設定 `CLAUDE_CODE_DISABLE_MOUSE_CLICKS=1`。當兩個變數都設定時，`CLAUDE_CODE_DISABLE_MOUSE` 優先。

停用點擊後，Claude Code 仍然會捕捉滑鼠，因此滾輪和觸控板會捲動對話，但左鍵在 Claude Code 內部不執行任何操作。您仍然需要按住終端機的按鍵進行原生點擊並拖曳選取。右鍵和中鍵貼上在支援它們的終端機上繼續運作。

## 疑難排解

### 螢幕上出現過時或位置錯誤的文字

全螢幕渲染只會傳送在幀之間變更的儲存格。某些終端機（最常見的是 Windows Terminal 和其他 ConPTY 支援的主機）會不正確地合併這些定位寫入，並在您調整視窗大小之前，在螢幕上留下較早輸出的片段。

設定 [`CLAUDE_CODE_ALT_SCREEN_FULL_REPAINT=1`](https://code.claude.com/docs/zh-TW/env-vars) 以在每一幀上重新繪製每個儲存格，而不是傳送增量更新。

在 Windows PowerShell 上：

```powershell theme={null}
$env:CLAUDE_CODE_ALT_SCREEN_FULL_REPAINT = "1"
claude
```

在 macOS 或 Linux 上：

```bash theme={null}
CLAUDE_CODE_ALT_SCREEN_FULL_REPAINT=1 claude
```

在 Windows 上，Claude Code 已經為背景工作階段和 [agent view](https://code.claude.com/docs/zh-TW/agent-view.md) 自動啟用完整重繪，因此您只需要為直接啟動的互動式全螢幕工作階段設定此變數。

### 啟動時出現「Claude Code 的全螢幕渲染器上次未完成啟動」

如果此機器上的全螢幕工作階段在成功啟動之前當機，Claude Code 會在經典渲染器中啟動您的下一個工作階段，並列印以下兩行之一。工作階段在繪製其第一幀後，要麼保持運行 10 秒鐘，要麼您使用 `/exit`、Ctrl+C 或 Ctrl+D 結束它，工作階段就已成功啟動。您看到的行告訴您 Claude Code 在此工作階段後會執行什麼操作：

* 在一次失敗的啟動後，您會看到「Claude Code 的全螢幕渲染器上次在此機器上未完成啟動」。Claude Code 會在您啟動的下一個工作階段中再次嘗試全螢幕渲染
* 在兩次失敗的啟動後，您會看到「Claude Code 的全螢幕渲染器在此機器上反覆啟動失敗」。Claude Code 會繼續使用經典渲染器，直到您更新 Claude Code 或執行 `/tui fullscreen`，並在之後的那些工作階段中不列印任何內容

若要確認失敗的啟動是您在經典渲染器中的原因，請執行不帶引數的 `/tui`。當失敗的啟動是原因時，`Current renderer` 行會說明這一點。

若要保持經典渲染器，請執行 `/tui default`，這會儲存 `tui` 設定而不重新啟動。若要再次嘗試全螢幕渲染，請執行 `/tui fullscreen`。如果該工作階段也未完成啟動，請[回報問題](#research-preview)。

在 v2.1.236 之前，Claude Code 在失敗的啟動後持續在全螢幕渲染中啟動工作階段。

#### Claude Code 如何計算失敗的啟動

* 計算的工作階段：只有因為您的 `tui` 設定而在全螢幕渲染中啟動的工作階段、因為您接受了[啟動對話框](#fullscreen-by-default)而啟動的工作階段，或因為 Claude Code 預設在全螢幕中啟動您的工作階段
* `CLAUDE_CODE_NO_FLICKER=1`：如果您設定了它，Claude Code 會在失敗的啟動後以全螢幕方式渲染該工作階段，並且不計算它
* 計數重設：Claude Code 按 Claude Code 版本計算失敗的啟動，成功的全螢幕啟動會重設計數
* 啟動對話框：如果您接受了對話框，重新啟動的工作階段當機，Claude Code 不會列印任何行，也不會在此 Claude Code 版本上再次顯示對話框

## 研究預覽

全螢幕渲染是一項研究預覽功能。它已在常見的終端模擬器上進行測試，但您可能會在較不常見的終端或不尋常的設定上遇到渲染問題。

如果您遇到問題，請在 Claude Code 內執行 `/feedback` 來報告，或在 [claude-code GitHub 儲存庫](https://github.com/anthropics/claude-code/issues)上開啟議題。請包含您的終端模擬器名稱和版本。

若要關閉全螢幕渲染，請執行 `/tui default`，或如果您以該方式啟用了 `CLAUDE_CODE_NO_FLICKER`，請取消設定。當您使用 `/tui default` 切換回去時，Claude Code 可能會先顯示一個選擇性的回饋提示，詢問您切換的原因。輸入原因並按 `Enter` 鍵傳送，或按 `Esc` 鍵跳過。無論哪種方式，CLI 都會重新啟動到經典渲染器。若要強制使用經典渲染器而不管已儲存的 `tui` 設定，請設定 `CLAUDE_CODE_DISABLE_ALTERNATE_SCREEN=1`。經典渲染器將對話保留在您終端的原生捲軸中，因此 `Cmd+f` 和 tmux 複製模式可以照常運作。

從[代理檢視](https://code.claude.com/docs/zh-TW/agent-view.md)或 `claude attach` 開啟的背景工作階段始終使用全螢幕渲染。附加終端進入替代螢幕緩衝區以顯示工作階段，經典渲染器在那裡沒有捲軸或滑鼠處理，因此 `tui` 設定和 `CLAUDE_CODE_DISABLE_ALTERNATE_SCREEN` 不適用於它們。

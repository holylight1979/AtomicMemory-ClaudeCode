<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/voice-dictation | lastmod: 2026-10-22 | section: Configuration / Interface -->
> 來源：https://code.claude.com/docs/zh-TW/voice-dictation（官方 zh-TW，lastmod 2026-10-22）｜分類：Configuration › Interface｜EN 摘要：Speak your prompts in the Claude Code CLI with hold-to-record or tap-to-record voice dictation.

# 語音聽寫

> 在 Claude Code CLI 中使用按住錄音或點擊錄音的語音聽寫功能來說出您的提示。

在 Claude Code CLI 中說出您的提示，而不是輸入它們。您的語音會即時轉錄到提示輸入中，因此您可以在同一條訊息中混合語音和輸入。使用 `/voice` 啟用聽寫，然後在說話時按住一個鍵或點擊一次開始，再點擊一次發送。

在[按住模式](#hold-to-record)下，聽寫也適用於 [agent 檢視](https://code.claude.com/docs/zh-TW/agent-view.md#peek-and-reply)。在 dispatch 輸入或窺視面板回覆聚焦時，按住您的按鍵通話鍵，即可聽寫到背景工作階段。

## 要求

語音聽寫會將您錄製的音頻串流傳輸到 Anthropic 的伺服器進行轉錄。音頻不在本地處理。它需要以下所有條件：

* **Claude.ai 帳戶**：語音轉文字服務僅在您使用 Claude.ai 帳戶進行身份驗證時可用，當 Claude Code 配置為直接使用 Anthropic API 金鑰、Amazon Bedrock、Google Cloud 的 Agent Platform 或 Microsoft Foundry 時不可用。
* **本地麥克風**：語音聽寫在[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)或 SSH 工作階段中不起作用。
* **如果您在 WSL 中執行 Claude Code，則需要 WSLg**：WSLg 在從 Microsoft Store 在 Windows 10 或 11 上安裝 WSL2 時包含。如果 WSLg 不可用，例如在 WSL1 上，改為在原生 Windows 中執行 Claude Code。

轉錄不會消耗 Claude 訊息或代幣，也不會計入 `/usage` 中顯示的限制。請參閱[資料使用](https://code.claude.com/docs/zh-TW/data-usage.md)了解 Anthropic 如何處理您的資料。

音頻錄製在 macOS、Linux 和 Windows 上使用內建的原生模組。在 Linux 上，如果原生模組無法載入，Claude Code 會回退到 ALSA utils 中的 `arecord` 或 SoX 中的 `rec`。如果兩者都不可用，`/voice` 會列印您的套件管理員的安裝命令。

Claude Code [VS Code 擴充功能](https://code.claude.com/docs/zh-TW/vs-code.md)也支援語音聽寫，具有相同的 Claude.ai 帳戶要求。它在 VS Code Remote 工作階段中不可用，包括 SSH、Dev Containers 和 Codespaces，因為麥克風在您的本地機器上，而擴充功能在遠端主機上執行。

## 啟用語音聽寫

執行 `/voice` 以啟用聽寫。啟用時，Claude Code 會執行麥克風檢查。在 macOS 上，如果您的終端機從未被授予權限，這會觸發系統麥克風權限提示。

```
/voice
Voice mode enabled (hold). Hold space to record. Dictation language: en (/config to change).
```

`/voice` 接受一個可選的模式引數：

| 命令 | 效果 |
| :- | :- |
| `/voice` | 切換開啟或關閉，保持目前模式 |
| `/voice hold` | 在[按住模式](#hold-to-record)中啟用 |
| `/voice tap` | 在[點擊模式](#tap-to-record-and-send)中啟用 |
| `/voice off` | 停用 |

語音聽寫在工作階段之間保持。直接在您的[使用者設定檔案](https://code.claude.com/docs/zh-TW/settings.md)中設定它，而不是執行 `/voice`：

```json theme={null}
{
  "voice": {
    "enabled": true,
    "mode": "tap"
  }
}
```

啟用語音聽寫的前三個工作階段中，當提示為空時，輸入頁尾會顯示 `hold space to speak` 提示。提示文字反映您目前的 `voice:pushToTalk` 快捷鍵繫結，如果您[重新繫結聽寫鍵](#rebind-the-dictation-key)，則會更新。提示文字在兩種模式中都相同，如果您配置了[自訂狀態行](https://code.claude.com/docs/zh-TW/statusline.md)，則不會出現。

轉錄在兩種模式中都針對編碼詞彙進行了調整。常見的開發術語如 `regex`、`OAuth`、`JSON` 和 `localhost` 都能正確識別，您目前的專案名稱和 git 分支名稱會自動新增為識別提示。

## 按住錄音

按住模式是推送通話：錄製在您按住鍵時執行，在您鬆開時停止。這是預設模式。

按住 `Space` 開始錄製。Claude Code 通過監視來自您終端機的快速按鍵重複事件來偵測按住的鍵，因此在錄製開始前有一個簡短的預熱期。頁尾在預熱期間顯示 `keep holding…`，然後在錄製啟動後顯示 `listening…`。錄製時，提示游標會變成一個隨著您麥克風音量上下波動的橫條，除非您已開啟 [`prefersReducedMotion`](https://code.claude.com/docs/zh-TW/settings-reference#prefersreducedmotion)。

前幾個按鍵重複字元在預熱期間輸入到輸入中，並在錄製啟動時自動移除。單個 `Space` 點擊仍會輸入一個空格，因為按住偵測只在快速重複時觸發。

按住或點擊 `Space` 只在按鍵會輸入到提示的地方開始聽寫。在[轉錄檢視器](https://code.claude.com/docs/zh-TW/interactive-mode.md#transcript-viewer)中，`Space` 會翻頁瀏覽對話，而在[vim 模式](https://code.claude.com/docs/zh-TW/interactive-mode.md#vim-editor-mode)中 INSERT 以外的狀態下，它是一個命令。[重新繫結的修飾符組合](#rebind-the-dictation-key)（例如 `meta+k`）永遠不會輸入文字，因此它也會從這些地方開始聽寫。

> [!TIP]
>
> 若要跳過預熱，使用 `/voice tap` 切換到[點擊模式](#tap-to-record-and-send)，或[重新繫結到修飾符組合](#rebind-the-dictation-key)，例如 `meta+k`。修飾符組合在第一次按鍵時開始錄製。

您的語音在您說話時出現在提示中，在轉錄最終確定之前會變暗。鬆開 `Space` 停止錄製並最終確定文字。轉錄會插入到您的游標位置，游標保持在插入文字的末尾，因此您可以按任何順序混合輸入和聽寫。再次按住 `Space` 以附加另一個錄製，或先移動游標以在提示中的其他位置插入語音：

```
> refactor the auth middleware to ▮
  # hold space, speak "use the new token validation helper"
> refactor the auth middleware to use the new token validation helper▮
```

預設情況下，鬆開鍵會插入轉錄並等待您按 `Enter`。在 `voice` 設定物件中設定 `"autoSubmit": true` 以在您鬆開鍵時自動發送提示，只要轉錄至少有三個單詞。

## 點擊錄音並發送

點擊模式使用單個按鍵切換錄製：點擊一次開始，說話，然後再點擊一次發送提示。沒有預熱，您不需要保持鍵被按住。

使用 `/voice tap` 啟用點擊模式。當提示輸入為空時，點擊 `Space` 開始錄製。頁尾在錄製時顯示 `● REC · tap to send`。再次點擊 `Space` 停止。

Claude Code 插入轉錄，當轉錄至少有三個單詞時自動提交提示。較短的轉錄會被插入但不會被提交，因此意外點擊不會發送一個隨意的單詞。

三個單詞的閾值計算不使用空格書寫的語言中的單詞。日文、中文和泰文轉錄計算個別單詞，因此它們在點擊模式和使用 `autoSubmit` 的保持模式中自動提交。

第一次點擊只在提示輸入為空時開始錄製，因此您在撰寫訊息時仍然可以正常輸入空格。第二次點擊無論輸入內容如何都會停止錄製。錄製也會在 15 秒無聲或 2 分鐘總時間後自動停止。

## 取消錄音

按 `Esc` 或 `Ctrl+C` 來取消聽寫，而不是完成它。Claude Code 會停止麥克風、捨棄文字記錄，並將提示恢復到錄音開始前的狀態。

兩個按鍵也會在完成的錄音文字記錄仍在處理時取消。您在處理期間編輯或提交的提示會保持您留下的狀態。

這兩個按鍵在取消的按下中不會執行任何其他操作：`Esc` 不會中斷 Claude 的回應，`Ctrl+C` 不會清除提示或計為[退出 Claude Code 的兩次按下](https://code.claude.com/docs/zh-TW/interactive-mode.md#general-controls)中的第一次。

## 變更聽寫語言

語音聽寫使用與控制 Claude 回應語言相同的 [`language` 設定](https://code.claude.com/docs/zh-TW/settings-reference#language)。如果該設定為空，聽寫預設為英文。在 VS Code 擴充功能中，如果 `language` 為空，聽寫會在預設為英文之前使用 VS Code 的 `accessibility.voice.speechLanguage` 設定。

> [accordion] 支援的聽寫語言
>
> | 語言 | 代碼 |
> | :- | :- |
> | 捷克文 | `cs` |
> | 丹麥文 | `da` |
> | 荷蘭文 | `nl` |
> | 英文 | `en` |
> | 法文 | `fr` |
> | 德文 | `de` |
> | 希臘文 | `el` |
> | 印地文 | `hi` |
> | 印尼文 | `id` |
> | 義大利文 | `it` |
> | 日文 | `ja` |
> | 韓文 | `ko` |
> | 挪威文 | `no` |
> | 波蘭文 | `pl` |
> | 葡萄牙文 | `pt` |
> | 俄文 | `ru` |
> | 西班牙文 | `es` |
> | 瑞典文 | `sv` |
> | 土耳其文 | `tr` |
> | 烏克蘭文 | `uk` |

在 `/config` 中或直接在設定中設定語言。您可以使用 [BCP 47 語言代碼](https://en.wikipedia.org/wiki/IETF_language_tag)或語言名稱：

```json theme={null}
{
  "language": "japanese"
}
```

如果您的 `language` 設定不在支援的清單中，`/voice` 會在啟用時警告您，並為聽寫回退到英文。Claude 的文字回應不受此回退的影響。

## 重新繫結聽寫鍵

聽寫鍵在 `Chat` 上下文中繫結到 `voice:pushToTalk`，預設為 `Space`。相同的繫結控制按住和點擊模式。在 [`~/.claude/keybindings.json`](https://code.claude.com/docs/zh-TW/keybindings) 中重新繫結它：

```json theme={null}
{
  "bindings": [
    {
      "context": "Chat",
      "bindings": {
        "meta+k": "voice:pushToTalk",
        "space": null
      }
    }
  ]
}
```

`voice:pushToTalk` 動作一次使用一個鍵。當您繫結自訂鍵時，它會取代預設的 `Space` 繫結，而不是新增第二個觸發器，因此此範例中的 `"space": null` 行是為了清晰起見，可以省略而不改變行為。

在按住模式中，避免繫結裸字母鍵，例如 `v`，因為按住偵測依賴於按鍵重複，字母在預熱期間輸入到提示中。使用 `Space`，或使用修飾符組合，例如 `meta+k` 以在第一次按鍵時開始錄製，無需預熱。點擊模式沒有預熱，因此大多數鍵都可以。

某些鍵不會傳遞到終端應用程式，根本無法繫結。例如，如果您嘗試繫結 `Caps Lock`，它會顯示錯誤。請參閱[自訂鍵盤快捷鍵](https://code.claude.com/docs/zh-TW/keybindings.md)了解完整的快捷鍵語法和保留快捷鍵的清單。

## 疑難排解

語音聽寫未啟動或錄製時的常見問題：

* **`Unknown command: /voice`**：`/voice` 僅在 claude.ai 帳戶為您目前使用中的登入身分時可用。如果您尚未使用此類帳戶登入，請執行 `/login`。如果正在使用 `ANTHROPIC_API_KEY`、`ANTHROPIC_AUTH_TOKEN`、`apiKeyHelper` 設定或[第三方提供者](#requirements)，它會優先於 claude.ai 登入，因此請將其移除並重新啟動 Claude Code。
* **`Voice mode requires a Claude.ai account`**：您執行 `/voice` 或開始錄製時，Claude Code 找不到可用的 claude.ai 登入。執行 `/login` 以重新登入。
* **`Voice mode is disabled by your organization's policy`**：您的組織的管理員政策停用了語音聽寫。請聯絡您的組織管理員以確認您的組織是否可使用語音聽寫。
* **`Microphone access is denied`**：在系統設定中授予您的終端機麥克風權限。在 macOS 上，前往系統設定 → 隱私與安全 → 麥克風並啟用您的終端機應用程式，然後再次執行 `/voice`。在 Windows 上，前往設定 → 隱私與安全 → 麥克風並開啟桌面應用程式的麥克風存取，然後再次執行 `/voice`。如果您的終端機未列在 macOS 設定中，請參閱[終端機未列在 macOS 麥克風設定中](#terminal-not-listed-in-macos-microphone-settings)。
* **`Voice mode requires SoX for audio recording` on Linux**：原生音頻模組無法載入，且未安裝回退。使用錯誤訊息中顯示的命令安裝 SoX，例如 `sudo apt-get install sox`。
* **`Voice mode requires a microphone, but SoX could not open an audio capture device`**：SoX 已安裝，但主機沒有音頻擷取裝置，例如無頭伺服器或容器。在具有麥克風的機器上執行 Claude Code。自 v2.1.195 起，Linux 上的 Claude Code 在該情況下報告此訊息；較早的版本即使已安裝 SoX 也會要求您安裝它。
* **`Voice mode could not find a working audio recorder in WSL`**：WSLg 透過 PulseAudio 而非 ALSA 裝置路由音頻，因此 SoX 需要明確安裝其 PulseAudio 後端。執行 `sudo apt install sox libsox-fmt-pulse`。單獨安裝 `sox` 會拉入 ALSA 後端，這在 WSL 上無法錄製，因為沒有 `/dev/snd` 裝置。
* **`Voice input is failing repeatedly and has been paused`**：語音聽寫在 10 秒內連續遇到三個擷取失敗。Claude Code 暫停聽寫，直到自這些失敗中的第一個以來已經過了 10 秒。這通常表示此主機上的麥克風或音頻堆疊無法捕獲音頻，例如無頭伺服器、沒有音頻傳遞的遠端 shell 或被拒絕的麥克風權限。確認工作輸入裝置，修復上述項目中的根本原因，然後再次觸發語音。在 v2.1.202 之前，只有啟動失敗計入暫停。
* **在按住模式中按住 `Space` 時沒有任何反應**：在按住時監視提示輸入。如果空格不斷累積，語音聽寫可能已關閉；執行 `/voice hold` 啟用它。如果只出現一個或兩個空格然後沒有任何反應，語音聽寫已開啟但按住偵測未觸發。按住偵測需要您的終端機發送按鍵重複事件，因此如果在作業系統層級停用了按鍵重複，它無法偵測按住的鍵。使用 `/voice tap` 切換到點擊模式以避免按鍵重複要求。
* **在點擊模式中點擊 `Space` 輸入空格而不是錄製**：第一次點擊只在提示輸入為空時開始錄製。先清除輸入，或通過執行 `/voice tap` 檢查您是否處於點擊模式。
* **`No audio detected from microphone`**：錄製已開始但捕獲了無聲。確認正確的輸入裝置設定為系統預設值，其輸入級別未靜音或接近零。在 Windows 上，開啟設定 → 系統 → 聲音 → 輸入並選擇您的麥克風。在 macOS 上，開啟系統設定 → 聲音 → 輸入。
* **`Voice connection failed`**：您的錄製因為連線失敗而從未到達轉錄服務。檢查您的網路並重試。捕獲無音頻的錄製會報告 `No audio detected from microphone` 而不是此訊息。在 v2.1.200 之前，無聲麥克風可能會報告連線失敗，這暗示網路問題，而實際問題是輸入裝置。
* **`Dictation error: WebSocket error:` 後接憑證錯誤，例如 `unable to get local issuer certificate`**：請參閱 VS Code 頁面上的[聽寫或 Web 分頁在進行 TLS 檢查的代理伺服器後方失敗](https://code.claude.com/docs/zh-TW/vs-code.md#dictation-or-the-web-tab-fails-behind-a-tls-inspecting-proxy)。
* **`Voice stream error: WebSocket upgrade rejected with HTTP <status>`**：伺服器以顯示的 HTTP 狀態拒絕了您的連線，因此這不是網路中斷。400 範圍內的狀態通常表示過期的登入、代理或機器人保護服務代替轉錄服務回應。執行 `/login` 以重新整理您的登入，如果狀態持續，請檢查您的網路路徑上是否有 VPN 或代理。如果拒絕到達時您仍在錄製，Claude Code 會在顯示此訊息之前重試 400 範圍外的狀態一次；它不會重試 400 範圍內的狀態。在 v2.1.229 至 v2.1.231 中，原生組建未顯示此訊息：Claude Code 繼續錄製，按住模式頁尾仍顯示 `listening…`，並在您停止錄製後報告 `Voice connection failed`。
* **`No speech detected`**：音頻到達轉錄服務但未識別任何單詞。靠近麥克風說話，減少背景噪音，並確認您的[聽寫語言](#change-the-dictation-language)與您說話的語言相符。
* **`Dictation stopped: no speech recognized for 15 seconds` 或 `Dictation stopped at its 2-minute limit`**：在 VS Code 擴充功能中，錄製會在 15 秒內未識別任何單詞時結束，或在開始後兩分鐘結束。如果您在這 15 秒內有說話，請嘗試 `No speech detected` 的修正方法。已識別的單詞會保留在提示輸入框中，且不會被送出。若要新增更多內容，請再次點擊麥克風按鈕。
* **轉錄是亂碼或使用了錯誤的語言**：聽寫預設為英文。如果您用另一種語言聽寫，請先在 `/config` 中設定它。請參閱[變更聽寫語言](#change-the-dictation-language)。

### 終端機未列在 macOS 麥克風設定中

如果您的終端機應用程式未出現在系統設定 → 隱私與安全 → 麥克風下，則沒有您可以啟用的切換。重設您的終端機的權限狀態，以便下一次 `/voice` 執行觸發新的 macOS 權限提示。

**1. 重設您的終端機的麥克風權限**

執行 `tccutil reset Microphone <bundle-id>`，將 `<bundle-id>` 替換為您的終端機的識別碼：內建終端機為 `com.apple.Terminal`，或 iTerm2 為 `com.googlecode.iterm2`。對於其他終端機，使用 `osascript -e 'id of app "AppName"'` 查詢識別碼。

> [!WARNING]
>
> 您可以執行 `tccutil reset Microphone` 而不需要套件 ID，但它會撤銷 Mac 上每個應用程式的麥克風存取權限，包括 Zoom 或 Slack 等應用程式。每個應用程式在下次使用時都需要重新請求存取權限，因此不要在活躍通話期間執行它。

**2. 退出並重新啟動您的終端機**

macOS 不會重新提示已在執行的程序。使用 Cmd+Q 退出終端機應用程式，而不只是關閉其視窗，然後再次開啟它。

**3. 觸發新的提示**

啟動 Claude Code 並執行 `/voice`。macOS 會提示麥克風存取；允許它。

## 另請參閱

* [自訂鍵盤快捷鍵](https://code.claude.com/docs/zh-TW/keybindings.md)：重新繫結 `voice:pushToTalk` 和其他 CLI 鍵盤動作
* [所有設定](https://code.claude.com/docs/zh-TW/settings-reference.md#voice)：`voice`、`language` 和其他設定鍵
* [互動模式](https://code.claude.com/docs/zh-TW/interactive-mode.md)：鍵盤快捷鍵、輸入模式和工作階段控制
* [命令](https://code.claude.com/docs/zh-TW/commands.md)：`/voice`、`/config` 和所有其他命令的參考

<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/mobile | lastmod: 2026-10-30 | section: Getting started / Platforms and integrations -->
> 來源：https://code.claude.com/docs/zh-TW/mobile（官方 zh-TW，lastmod 2026-10-30）｜分類：Getting started › Platforms and integrations｜EN 摘要：Start, monitor, and steer Claude Code tasks from your phone with the Claude app for iOS and Android.

# Claude Code 行動版

> 從您的手機使用 Claude iOS 和 Android 應用程式來啟動、監控和引導 Claude Code 工作。

Claude [iOS](https://apps.apple.com/us/app/claude-by-anthropic/id6473753684) 和 [Android](https://play.google.com/store/apps/details?id=com.anthropic.claude) 應用程式是 Claude Code 工作階段的用戶端，而不是程式碼執行的地點。從您的手機，您可以存取雲端上的[雲端工作階段](#start-and-monitor-cloud-sessions)和[專案](https://code.claude.com/docs/zh-TW/claude-projects.md)、透過[遠端控制](#continue-a-local-session-with-remote-control)在您自己的機器上執行的工作階段，或透過 [Dispatch](https://code.claude.com/docs/zh-TW/desktop.md#sessions-from-dispatch) 的桌面應用程式。

> [!NOTE]
>
> Claude Code 沒有單獨的行動應用程式：雲端工作階段和遠端控制都位於 Claude 應用程式中的 **Code** 標籤，而 Dispatch 是您在應用程式中向其傳送訊息的工作。

## 取得應用程式

**1. 下載 Claude 應用程式**

安裝 [iOS](https://apps.apple.com/us/app/claude-by-anthropic/id6473753684) 或 [Android](https://play.google.com/store/apps/details?id=com.anthropic.claude) 的 Claude 應用程式。在 iPad 上，安裝相同的 iOS 應用程式。

> [!TIP]
>
> 在 Claude Code 工作階段中執行 `/mobile` 以顯示 [claude.ai/mobile](https://claude.ai/mobile) 的 QR 碼，該碼會開啟您手機的正確應用程式商店。`/ios` 和 `/android` 執行相同的操作。

**2. 登入**

使用您用於 Claude Code 的相同 claude.ai 帳戶和組織登入。雲端工作階段和遠端控制需要 claude.ai 帳戶，因此無法透過 Anthropic Console API 金鑰或來自 Amazon Bedrock 等第三方提供者的帳戶存取。

**3. 開啟 Code 標籤**

在應用程式的導覽中點選 **Code** 以存取您的工作階段，或在您的手機上開啟 [claude.ai/code/new](https://claude.ai/code/new) 以在應用程式中啟動新的 Code 工作階段。如果您看不到 Code 標籤，您的方案或組織可能不包含這些功能；請參閱[按訂閱方案的可用性](https://code.claude.com/docs/zh-TW/feature-availability.md#availability-by-subscription-plan)。

## 從您的手機工作

從應用程式，您可以啟動雲端工作階段、開啟專案、驅動在您的電腦上執行的 Claude Code 工作階段，或向 Dispatch 傳送工作訊息。應用程式對所有項目都相同；它們在工作發生的位置上有所不同。

| 功能 | 您連接到的內容 | 何時使用 |
| :- | :- | :- |
| [雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md) | 雲端基礎設施上的工作階段，預設由 Anthropic 管理 | 您的儲存庫在 GitHub 上，工作應在您放下手機後繼續執行。請參閱[雲端快速入門](https://code.claude.com/docs/zh-TW/web-quickstart.md)進行設定。 |
| [專案](https://code.claude.com/docs/zh-TW/claude-projects.md) | Claude 協調平行工作執行緒並回報的對話 | 您有一系列相關的工作而不是一個工作，並想查看哪些執行緒已完成或需要您。 |
| [遠端控制](https://code.claude.com/docs/zh-TW/remote-control.md) | 在您的電腦上執行的 Claude Code 工作階段 | 工作需要您的本機檔案系統、工具或 MCP 伺服器。 |
| [Dispatch](https://code.claude.com/docs/zh-TW/desktop.md#sessions-from-dispatch) | 您電腦上的桌面應用程式 | 您想傳送工作訊息並讓 Dispatch 決定如何執行它。需要 Pro、Max 或 Ultra 方案。 |

如果您的電腦將關閉，請使用雲端工作階段或專案，它們在雲端中執行並在您的筆記型電腦關閉後繼續執行。遠端控制和 Dispatch 驅動您自己的機器，因此它需要保持開啟並執行 Claude Code 或桌面應用程式。如果您的機器在遠端控制工作階段期間進入睡眠狀態，Claude Code 會在機器恢復上線時重新連接。

如需更完整的比較，請參閱[當您遠離終端機時工作](https://code.claude.com/docs/zh-TW/platforms.md#work-when-you-are-away-from-your-terminal)。

雲端工作階段和遠端控制從 **Code** 標籤執行。對於您在應用程式中作為工作傳送訊息的 Dispatch，請參閱[來自 Dispatch 的工作階段](https://code.claude.com/docs/zh-TW/desktop.md#sessions-from-dispatch)。

### 啟動和監控雲端工作階段

雲端工作階段在雲端基礎設施上執行工作，預設由 Anthropic 管理，因此工作階段在您放下手機後繼續執行。從 Code 標籤，選擇儲存庫和分支、描述工作，然後提交。工作階段在裝置間持續存在：您在筆記型電腦上啟動的工作已準備好從您的手機進行審查，您從手機啟動的工作在您回到辦公桌時正在等待。

在應用程式中開啟工作階段以檢查進度、回答 Claude 的問題或將其引導到新的方向。您也可以告訴 Claude [監看拉取請求](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#auto-fix-pull-requests)並在 CI 失敗或審查意見到達時修復它們。若要連接 GitHub 並設定您的環境，請遵循[雲端快速入門](https://code.claude.com/docs/zh-TW/web-quickstart.md)，並查看[在雲端中使用 Claude Code](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md) 以了解雲端工作階段可以執行的所有操作。

### 使用遠端控制繼續本機工作階段

遠端控制將 Claude 應用程式連接到在您的機器上執行的 Claude Code 工作階段，因此程式碼執行和檔案系統存取保持本機，而您從手機驅動工作階段。在您的電腦上使用 `claude remote-control` 啟動工作階段，或在已開啟的工作階段中執行 `/remote-control`。然後掃描終端機可以顯示的 QR 碼，或開啟 Claude 應用程式、點選 **Code**，然後從清單中選擇工作階段。請參閱[從另一個裝置連接](https://code.claude.com/docs/zh-TW/remote-control.md#connect-from-another-device)以了解每個選項。

當您在 Claude 應用程式中新增附件時，它也會到達本機工作階段：

* **照片**：Claude 直接將附加的照片視為您訊息的一部分。Claude Code 也會將每張照片儲存在 `~/.claude/uploads/` 下，並告訴 Claude 儲存的檔案路徑，因此 Claude 可以將影像複製到它建立的檔案中。
* **其他檔案**：Claude Code 將它們下載到您的機器，並將它們作為 `@` 檔案參考傳遞給 Claude。

如需需求、調用模式和疑難排解，請參閱[遠端控制概述](https://code.claude.com/docs/zh-TW/remote-control.md)。

### 取得推播通知

當遠端控制處於作用中時，Claude 可以向您的手機傳送推播通知，通常在長時間執行的工作完成或需要您做出決定時。您也可以在提示中要求一個，例如 `notify me when the tests finish`。請參閱[行動推播通知](https://code.claude.com/docs/zh-TW/remote-control.md#mobile-push-notifications)以了解兩個 `/config` 切換和傳遞疑難排解。

Dispatch 在它產生的 Code 工作階段完成或需要您的批准時傳送自己的通知，如[來自 Dispatch 的工作階段](https://code.claude.com/docs/zh-TW/desktop.md#sessions-from-dispatch)中所述。

## 限制

行動用戶端涵蓋工作階段所需的大部分內容，但有一些限制：

* **僅限本機命令**：僅在終端機介面中執行的命令，例如 `/plugin` 和 `/resume`，無法從應用程式中工作。[遠端控制限制](https://code.claude.com/docs/zh-TW/remote-control.md#limitations)列出了從行動裝置工作的命令以及它們的行為如何不同。
* **權限模式**：雲端工作階段提供接受編輯、Plan 和 Auto，Remote Control 工作階段提供 Manual、接受編輯、Plan 和 Auto。在任何情況下，您都無法從應用程式中選擇 Bypass permissions。請參閱[切換權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md#switch-permission-modes)，了解 Auto 何時可用。
* **Dispatch 方案**：Dispatch 需要 Pro、Max 或 Ultra 方案，在 Team 或 Enterprise 上不可用。

## 相關資源

* [平台和整合](https://code.claude.com/docs/zh-TW/platforms.md)：比較 Claude Code 執行的每個表面
* [Claude Code 網頁版](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)：雲端工作階段如何執行以及如何在您的終端機之間移動工作
* [設定雲端環境](https://code.claude.com/docs/zh-TW/cloud-environments.md)：雲端工作階段的網路存取層級、環境變數和設定指令碼
* [遠端控制](https://code.claude.com/docs/zh-TW/remote-control.md)：從任何裝置繼續本機工作階段
* [來自 Dispatch 的工作階段](https://code.claude.com/docs/zh-TW/desktop.md#sessions-from-dispatch)：Dispatch 工作如何在桌面應用程式中成為 Code 工作階段
* [Channels](https://code.claude.com/docs/zh-TW/channels.md)：在工作在您的機器上執行時，透過 Telegram、Discord 或 iMessage 從您的手機詢問 Claude 一些事情
* [Claude Code 在 Slack 中](https://code.claude.com/docs/zh-TW/slack.md)：透過提及 `@Claude` 從您的 Slack 工作區委派編碼工作

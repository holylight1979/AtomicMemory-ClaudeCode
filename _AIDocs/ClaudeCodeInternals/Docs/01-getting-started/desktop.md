<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/desktop | lastmod: 2026-11-04 | section: Getting started / Platforms and integrations -->
> 來源：https://code.claude.com/docs/zh-TW/desktop（官方 zh-TW，lastmod 2026-11-04）｜分類：Getting started › Platforms and integrations｜EN 摘要：Get more out of Claude Code Desktop: parallel sessions with Git isolation, drag-and-drop pane layout, integrated terminal and file editor, side chats, computer use, Dispatch sessions from your phone, visual diff review, app previews, PR monitoring, connectors, and enterprise configuration.

# Desktop 應用程式

> 充分利用 Claude Code Desktop：具有 Git 隔離的並行會話、拖放窗格佈局、整合終端機和檔案編輯器、側邊聊天、電腦使用、從您的手機 Dispatch 會話、視覺化差異檢查、應用程式預覽、PR 監控、連接器和企業配置。

在 Claude Desktop 應用程式中，Claude Code 就是 **Code** 標籤。此應用程式也提供聊天和 [Cowork](https://claude.com/product/cowork)，後者負責處理 Dispatch 和更長的代理工作。本頁面是 Code 標籤的參考。

> [card] [下載 macOS 版本](https://claude.ai/api/desktop/darwin/universal/dmg/latest/redirect?utm_source=claude_code\&utm_medium=docs)
>
> 適用於 Intel 和 Apple Silicon 的通用版本

> [card] [下載 Windows 版本](https://claude.ai/api/desktop/win32/x64/setup/latest/redirect?utm_source=claude_code\&utm_medium=docs)
>
> 適用於 x64 處理器

> [card] [取得 Claude for Linux (測試版)](https://code.claude.com/docs/zh-TW/desktop-linux.md)
>
> 適用於 Ubuntu 和 Debian 的 apt 或 .deb

若要使用 Windows ARM64，請下載 [ARM64 安裝程式](https://claude.ai/api/desktop/win32/arm64/setup/latest/redirect?utm_source=claude_code\&utm_medium=docs)。在 Linux 上，使用 apt 安裝；請參閱 [Claude Desktop on Linux](https://code.claude.com/docs/zh-TW/desktop-linux.md)。

安裝後，啟動 Claude，登入，然後點擊 **Code** 標籤。如需您第一個會話的逐步說明，請參閱[快速入門指南](https://code.claude.com/docs/zh-TW/desktop-quickstart.md)。

在 Code 標籤中，每個對話都是一個**會話**：它有自己的聊天歷史記錄和專案資料夾，獨立於任何其他會話。側邊欄列出您的會話，並讓您並行執行多個會話。在會話中，您可以：

* [使用差異檢查檢查和評論變更](#review-changes-with-diff-view)，然後[透過 CI 監控產生的 PR](#monitor-pull-request-status)
* [在瀏覽器窗格中預覽您執行的應用程式](#preview-your-app)，同時 Claude 驗證其自己的變更，並[在其旁邊開啟外部網站](#browse-external-sites)
* [在 iOS Simulator 窗格中觀看 Claude 執行和測試您的 iOS 應用程式](https://code.claude.com/docs/zh-TW/desktop-ios-simulator.md)
* [排列窗格](#arrange-your-workspace)，將聊天、差異、瀏覽器、終端機和檔案編輯器並排放置
* 提出[側邊問題](#ask-a-side-question-without-derailing-the-session)，使用會話的內容而不會偏離主題
* 讓 Claude [檢查、訊息或封存您的其他會話](#work-across-sessions)
* [連接外部工具](#connect-external-tools)，例如 GitHub、Slack 和 Linear
* 讓 Claude [開啟應用程式並控制您的螢幕](#let-claude-use-your-computer)
* 在您的機器上、[雲端](#run-long-running-tasks-in-the-cloud)或 [SSH](#ssh-sessions) 上執行

如需[排程定期工作](https://code.claude.com/docs/zh-TW/desktop-scheduled-tasks.md)、[快捷鍵](#keyboard-shortcuts)或[從您的手機傳送任務](#sessions-from-dispatch)，請參閱連結的頁面和章節。如果您已經使用基於終端機的 CLI，請參閱 [CLI 比較](#coming-from-the-cli)以了解哪些內容可以轉移。

## 開始會話

在傳送第一則訊息之前，請在提示詞方塊下方的列中選擇環境、專案資料夾、權限模式和模型：

* **環境**：使用環境選擇器（該列中的第一個控制項）選擇 Claude 執行的位置。請參閱[環境設定](#environment-configuration)。
  * 如果新工作階段的提示詞方塊下方沒有顯示環境，請依照[舊版版面配置的步驟](#check-which-layout-you-have)操作。
* **專案資料夾**：點擊環境選擇器旁的專案資料夾控制項，選擇 Claude 工作的資料夾。
  * **雲端工作階段**：選擇[儲存庫](#run-long-running-tasks-in-the-cloud)而非資料夾
  * **[已儲存的本機或 SSH 環境](#create-a-saved-environment)**：該環境已包含其資料夾，因此該列不會顯示專案資料夾控制項。若要變更資料夾，請[編輯環境](#use-edit-or-remove-a-saved-environment)。
* **權限模式**：使用[模式選擇器](#choose-a-permission-mode)選擇 Claude 擁有多少自主權。您可以在工作階段期間變更權限模式。
* **模型**：從該列靠右側的模型選擇器中選擇[模型](https://code.claude.com/docs/zh-TW/model-config.md#available-models)。您可以在工作階段期間變更模型。

輸入您的任務並按 **Enter** 開始。每個會話都會追蹤自己的上下文並獨立進行變更。

## 使用程式碼

提供 Claude 正確的背景資訊、控制它自主執行的程度，並檢查它所做的變更。

### 使用提示詞輸入框

輸入您想讓 Claude 執行的操作，然後按 **Enter** 鍵傳送。Claude 會讀取您的專案檔案、進行變更，並根據您的[權限模式](#choose-a-permission-mode)執行命令。您可以隨時重新導向 Claude：點擊停止按鈕立即中斷，或輸入更正並按 **Enter** 鍵傳送，無需停止執行中的操作。Claude 會在目前操作完成後立即讀取更正，並在下一步之前進行調整。

提示詞輸入框旁的 **+** 按鈕可讓您存取檔案附件、[skills](#use-skills)、[connectors](#connect-external-tools) 和 [plugins](#install-plugins)。

### 接受建議的提示詞

Claude 回覆後，Code 標籤可能會在空白的提示詞輸入框中以灰色文字顯示建議的下一個提示詞。Claude Code 會透過一個簡短的背景請求，根據您的對話[產生每個建議](https://code.claude.com/docs/zh-TW/interactive-mode.md#prompt-suggestions)，此請求會計入您方案的用量上限或您的 API 費用。

* **使用建議**：按 **Tab** 或**向右鍵**將其放入提示詞輸入框，視需要進行編輯，然後按 **Enter** 傳送。在接受建議之前按 **Enter** 不會傳送該建議。
* **撰寫您自己的提示詞**：直接開始輸入。建議只會在提示詞輸入框為空且沒有附加檔案時顯示。

在**設定 > Code** 或**設定 > Claude Code** 中關閉**提示詞建議**，即可停止顯示建議。每個工作階段會從下次啟動或繼續時起不再顯示建議。

### 將檔案和背景資訊新增至提示詞

若要將檔案提供給 Claude，請在提示詞輸入框中 @mention 該檔案或將其附加：

* **@mention 檔案**：輸入 `@` 後跟檔案名稱，將檔案新增至對話背景資訊。
  * **在雲端工作階段中**：`@` 只有在您傳送第一則訊息後才能列出檔案。如果 `@` 沒有列出任何檔案，請先在不附帶該檔案的情況下傳送第一則訊息，然後在下一則訊息中 @mention 該檔案。
* **附加檔案**：使用提示詞輸入框旁的 **+** 按鈕將影像、PDF 和其他檔案附加到您的提示詞，或直接將檔案拖放到提示詞中。這對於分享錯誤的螢幕截圖、設計模型或參考文件很有用。
  * **在 [WSL 工作階段](https://code.claude.com/docs/zh-TW/desktop-wsl.md)中**：如果 **+** 選單顯示的是**新增影像**而不是**新增檔案或相片**，則您只能附加影像。若要將工作階段資料夾中的任何其他檔案提供給 Claude，請 @mention 該檔案。

### 選擇權限模式

權限模式控制 Claude 在工作階段期間的自主程度：它是否在編輯檔案、執行命令或兩者之前詢問。您可以隨時使用提示詞輸入框下方那一列中的模式選擇器切換權限模式。若要自行核准每項變更，請切換至「手動」。

若要為新的本機工作階段設定預設模式，請將 `permissions.defaultMode` 新增至您的[設定檔](https://code.claude.com/docs/zh-TW/settings.md#where-settings-live)。桌面應用程式讀取與 CLI 相同的設定檔。您在選擇器中選擇的模式會記住每個資料夾，並優先於該資料夾的 `defaultMode`，但 Plan 除外，它僅適用於目前工作階段。

| 模式 | 設定鍵 | 行為 |
| - | - | - |
| **手動** | `default` | Claude 在編輯檔案或執行命令之前詢問。您會看到差異，並可以接受或拒絕每項變更。 |
| **接受編輯** | `acceptEdits` | Claude 自動接受檔案編輯和常見的檔案系統命令，例如 `mkdir`、`touch` 和 `mv`，但在執行其他終端機命令之前仍會詢問。當您信任檔案變更並想要更快速的迭代時，請使用此選項。 |
| **Plan** | `plan` | Claude 讀取檔案並執行命令以進行探索，然後提出計畫而不編輯您的原始程式碼。適合複雜的工作，您想先檢查方法。 |
| **自動** | `auto` | Claude 執行時不會出現例行提示；在 shell 命令和網路請求等操作執行之前，背景分類器會檢查它們是否與您的請求一致。當[自動模式可用](#auto-mode-availability)時出現；沒有單獨的設定切換。 |
| **略過權限** | `bypassPermissions` | Claude 執行時不會出現權限提示，除了[任何模式都不會自動核准的操作](https://code.claude.com/docs/zh-TW/permission-modes.md#actions-no-mode-auto-approves)、當 Claude [在外部網站上執行操作](#browse-external-sites)時的安全分類器，或桌面操作，例如刪除工作階段（但不包括[封存工作階段](#work-across-sessions)）。相當於 CLI 中的 `--dangerously-skip-permissions`。在 Pro、Max 和 Ultra 方案上，請在**設定 > Code** 或**設定 > Claude Code** 中啟用「允許略過權限模式」。在 Team 和 Enterprise 方案上沒有設定切換，而是由組織政策控制它。僅在沙箱容器或虛擬機中使用此選項。 |

Code 標籤的早期版本將這些模式標記為「詢問權限」、「自動接受編輯」和「Plan 模式」。

`dontAsk` 權限模式僅在 [CLI](https://code.claude.com/docs/zh-TW/permission-modes.md#allow-only-pre-approved-tools-with-dontask-mode) 中可用。

> [!TIP]
>
> 在 Plan 中開始複雜的工作，讓 Claude 在進行變更之前規劃方法。一旦您核准計畫，切換至「接受編輯」或「手動」以執行它。請參閱 [plan mode](https://code.claude.com/docs/zh-TW/permission-modes.md#analyze-before-you-edit-with-plan-mode) 以了解更多有關此工作流程的資訊。

雲端工作階段支援「接受編輯」、「Plan」和「自動」。「接受編輯」對應於 `default` 模式：雲端工作階段預先核准檔案編輯，因此選擇器顯示「接受編輯」而不是「手動」。「略過權限」在雲端工作階段中不可用，包括[自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)中的工作階段。

Enterprise 管理員可以限制哪些權限模式可用。請參閱[企業設定](#enterprise-configuration)以了解詳細資訊。

#### 自動模式可用性

自動模式適用於 Anthropic API 上的所有使用者，需要 Claude Opus 4.6 或更新版本、Sonnet 4.6 或更新版本、Haiku 5.5，或 [Fable 模型](https://code.claude.com/docs/zh-TW/model-config.md#work-with-fable)。組織管理員可以使用[受管設定](#managed-settings)中的 `disableAutoMode` 鍵關閉自動模式。

在將 Desktop 路由到 Google Cloud 的 Agent Platform 的 Enterprise 部署中，自動模式也預設可用；請參閱 [Bedrock、Agent Platform 或 Foundry 上的自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#enable-auto-mode-on-bedrock-agent-platform-or-foundry)以了解支援的模型。

### 預覽您的應用程式

Claude 可以啟動開發伺服器並在「瀏覽器」窗格中開啟它以驗證其變更。這適用於前端網路應用程式以及後端伺服器：Claude 可以測試 API 端點、檢視伺服器日誌，並對它發現的問題進行迭代。在大多數情況下，Claude 在編輯專案檔案後會自動啟動伺服器。您也可以隨時要求 Claude 進行預覽。預設情況下，Claude [自動驗證](#auto-verify-changes)每次編輯後的變更。

在本機工作階段中，點擊聊天中的 HTML、PDF 或影片路徑，即可在「瀏覽器」窗格中開啟它。

> [!NOTE]
>
> 在 [SSH 工作階段](#ssh-sessions)中，Claude 沒有「瀏覽器」窗格的工具，因此無法在該窗格中開啟您的應用程式，也無法[自動驗證](#auto-verify-changes)其變更。該窗格的**開發伺服器**選單和您[已設定的預覽伺服器](#configure-preview-servers)也無法使用。若要自行查看應用程式，請在遠端機器上啟動其伺服器，然後[將其連接埠轉送到您的電腦](#reach-a-port-on-the-remote-machine)。

如果 Claude 在本機工作階段中啟動伺服器後「瀏覽器」窗格沒有開啟，請點擊聊天中該伺服器卡片上的**開啟**。

從「瀏覽器」窗格，您可以：

* 直接在「瀏覽器」窗格中與執行中的應用程式互動
* 觀看 Claude 自動驗證其自身的變更：它會擷取螢幕截圖、檢查 DOM、點擊元素、填寫表單，並修復它發現的問題
* 從「瀏覽器」窗格標題列中的**開發伺服器**選單啟動或停止伺服器，或一次停止所有伺服器
* 透過「瀏覽器」窗格 **⋮** 選單中的**保留 Cookie**，選擇「瀏覽器」是否在您結束應用程式後保留 Cookie，因此您在開發期間不必重新登入

在 SSH 工作階段中，當您結束 Desktop 時，該窗格的 Cookie 會遺失。您無法透過**保留 Cookie** 變更此行為。

Claude 根據您的專案建立初始伺服器設定。如果您的應用程式使用自訂開發命令，請編輯 `.claude/launch.json` 以符合您的設定。請參閱[設定預覽伺服器](#configure-preview-servers)以了解完整參考。

若要清除「瀏覽器」已儲存的資料，請在「瀏覽器」窗格的 **⋮** 選單中選擇**清除瀏覽資料**。若要完全關閉「瀏覽器」，請在**設定 > Code** 或**設定 > Claude Code** 中關閉**瀏覽器工具**。

### 瀏覽外部網站

「瀏覽器」窗格是一個標籤式瀏覽器，因此您可以在執行中的應用程式旁邊開啟文件、問題追蹤器或任何其他網站。若要開啟「瀏覽器」，請在 macOS 上按 **Cmd+Shift+B**，或在 Windows 上按 **Ctrl+Shift+B**，或點擊工作階段標題列中的**瀏覽器**。您可以登入窗格中的網站，包括彈出式登入流程，例如 Google OAuth。

您第一次點擊聊天中的外部連結時，會出現一個對話方塊，詢問連結要在「瀏覽器」窗格中開啟，還是在您的預設瀏覽器中開啟。若要稍後變更您的選擇，請使用「瀏覽器」窗格 **⋮** 選單中的**在內建瀏覽器中開啟連結**。在 macOS 上按 **Cmd** 點擊或在 Windows 上按 **Ctrl** 點擊，會直接在您的預設瀏覽器中開啟連結。

Claude 可以使用與[驗證您的應用程式](#preview-your-app)相同的工具讀取和互動外部頁面，並進行兩項額外的安全檢查：

* 安全分類器在每個權限模式中檢查 Claude 在外部頁面上的寫入操作，例如點擊和輸入。這些是[自動模式](#choose-a-permission-mode)使用的相同分類器，當它們標記操作時，您會獲得權限提示，無論模式如何。
* 在「自動」和「略過權限」以外的權限模式中，在 Claude 導航到新網站之前也會應用網域允許清單檢查。

#### 核准 Claude 在網站上的操作

Claude 首次在外部網站上執行操作時，會出現權限卡，Claude 會等待您的選擇：**允許一次**、**始終允許**或**拒絕**。**允許一次**核准操作而不儲存任何內容。**始終允許**在您的裝置上儲存該網站的核准，您可以在「設定」中撤銷它。每個網站都需要自己的核准，包括子網域。您的本機開發伺服器和專案檔案不需要核准，因此[自動驗證](#auto-verify-changes)可以繼續進行而不會出現提示。

即使在已核准的網站上，Claude 也不會在沒有您的輸入的情況下購買商品、建立帳戶或繞過 CAPTCHA。在「瀏覽器」窗格中瀏覽使用與 [Chrome 中的 Claude 擴充功能](https://code.claude.com/docs/zh-TW/chrome.md)相同的安全模型。請參閱[安全地使用 Chrome 中的 Claude](https://support.claude.com/en/articles/12902428-using-claude-in-chrome-safely)以了解 Claude 如何處理敏感網站和危險操作。

#### 在「瀏覽器」和 Chrome 擴充功能之間選擇

「瀏覽器」窗格使用乾淨的瀏覽器設定檔，與您的個人瀏覽器分開，沒有您儲存的登入或歷史記錄。使用它來建立和測試您的應用程式，以及不需要您的身份的網站。當您想讓 Claude 在您的已登入工作階段中充當您時，請改用 [Chrome 中的 Claude 擴充功能](https://code.claude.com/docs/zh-TW/chrome.md)，它會共享您的瀏覽器的登入狀態。

#### 限制您的組織的外部瀏覽

「瀏覽器」遵循與 Claude in Chrome 擴充功能相同的[網站允許清單和封鎖清單控制](https://support.claude.com/en/articles/13065128-claude-in-chrome-admin-controls)。如果您的組織已為擴充功能設定了這些清單，「瀏覽器」會自動尊重它們。管理員也可以使用 [`browserExternalPageTools` 受管設定](#managed-settings)關閉 Claude 在外部頁面上的工具。停用工具後，使用者仍然可以導航到外部網站；Claude 的工具無法讀取或對其進行操作。

若要完全關閉外部瀏覽，請將 [`disableBrowserExternalNavigation` 受管設定](#managed-settings)設定為 `true`。這會阻止「瀏覽器」中的所有外部導航，包括您的組織允許清單上的網站；localhost 開發伺服器和檔案預覽保持運作。使用 `browserExternalPageTools` 讓使用者繼續瀏覽外部網站而不使用 Claude 的工具，並使用 `disableBrowserExternalNavigation` 為使用者和 Claude 阻止外部網站。

### 使用差異檢視檢查變更

Claude 對您的程式碼進行變更後，差異檢視可讓您在建立 pull request 之前逐個檔案檢查修改。若要開啟差異檢視，請點擊[工作階段詳細資料面板](#see-session-details)中**變更**卡片上的行數，例如 `+12 -1`。您也可以點擊工作階段標題列中的**變更**。雲端工作階段相對於基礎分支的差異可能會[遺漏尚未推送的變更](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#troubleshoot-a-missing-file-in-the-diff-view)。

若要對特定行進行評論，請將游標停留在某一行上，然後點擊其行號旁出現的 **+** 以開啟評論框。輸入您的意見反應並按 **Enter** 鍵以新增評論。在多行新增評論後，一次提交所有評論：

* **macOS**：按 **Cmd+Enter**
* **Windows**：按 **Ctrl+Enter**

Claude 會讀取您的評論並進行要求的變更，這些變更會顯示為您可以檢查的新差異。

### 檢查您的程式碼

若要讓 Claude 在您提交之前審查您的變更，請在[提示詞輸入框](#use-the-prompt-box)中輸入 `/code-review`。審查完成後，結果會出現在對話中。

在本機、[SSH](#ssh-sessions) 和 [WSL](https://code.claude.com/docs/zh-TW/desktop-wsl.md) 工作階段中，結果會以**程式碼審查**卡片呈現，並依檔案分組。使用該卡片來處理這些結果：

* 點擊**在差異中逐一檢視**以開啟差異檢視，並逐一檢視各項結果。位於目前差異中的結果會顯示在其對應的行，您可以在那裡點擊**修正此項**或將其關閉。
* 點擊**套用修正**以要求 Claude 修正仍未處理的結果。

在任何工作階段中，您也可以在提示詞輸入框中要求 Claude 修正審查發現的問題。若要了解 `/code-review` 檢查的內容及其接受的引數，請參閱[使用 `/code-review` 在本機審查](https://code.claude.com/docs/zh-TW/code-review-local)。

### 監控 pull request 狀態

若要讓 Claude 修復失敗的檢查，或讓 GitHub 合併 pull request，請開啟**自動修復**或**就緒時合併**。開啟 pull request 後，它會連同其 CI 檢查的狀態出現在[工作階段詳細資料面板](#see-session-details)的**變更**卡片中。開啟其標題旁的 **⋮** 選單：

* **自動修復**：在本機工作階段中，Claude 也會處理由您以外的人留下的新審查評論。評論的作者必須是儲存庫擁有者、組織成員、協作者或 GitHub App。
* **就緒時合併**：為該 PR 開啟 GitHub 的自動合併。在本機工作階段中，Desktop 會請求壓縮合併，除非基礎分支使用合併佇列。
  * **在 SSH 和 WSL 工作階段中**：**就緒時合併**已停用，因此請在 GitHub 上為該 pull request 開啟自動合併
  * **如果儲存庫不允許自動合併**：**就緒時合併**無法開啟，因此請先在您的 [GitHub 儲存庫設定](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-auto-merge-for-pull-requests-in-your-repository)中啟用自動合併
* **[較早的版面配置](#check-which-layout-you-have)**：工作階段有 pull request 後，點擊其狀態列上的 **CI**。

若要在 PR 合併或關閉後自動封存工作階段，請在**設定 > Code** 或**設定 > Claude Code** 中開啟[自動封存](#archive-a-session)。

> [!NOTE]
>
> PR 監控需要在您的機器上安裝並驗證 [GitHub CLI (`gh`)](https://cli.github.com/)。如果未安裝 `gh`，Desktop 會在您首次嘗試建立 PR 時提示您安裝它。
>
> 在 [SSH 工作階段](#ssh-sessions)中，請在點擊**建立 PR** 之前於遠端機器上設定 `git` 和 `gh`，因為 Claude 會在那裡推送分支並執行 `gh pr create`。請自行在那裡安裝 `gh`，因為 Desktop 在 SSH 工作階段中不會提示您安裝。接著在那裡確認 `git push` 可以正常運作，且 `gh auth status` 顯示您已登入。

## 安排您的工作區

Code 標籤是圍繞您可以以任何佈局排列的窗格構建的：聊天、差異、瀏覽器、終端機、檔案、plan、tasks 和 subagent，以及 macOS 上的 [iOS Simulator](https://code.claude.com/docs/zh-TW/desktop-ios-simulator.md)。透過其標題拖動窗格以重新定位它，或拖動窗格邊緣以調整其大小。在 macOS 上按 **Cmd+\\** 或在 Windows 上按 **Ctrl+\\** 以關閉焦點窗格。

若要開啟其他窗格，請點擊工作階段標題列中對應的圖示按鈕。將游標懸停在按鈕上即可查看各按鈕的名稱，例如 **Terminal**、用於差異檢視的 **Changes**、**Browser** 和 **Files**。如果您想要的窗格在標題列中沒有按鈕，請從按鈕旁的 **⋮** 選單中選擇：

* **視窗較窄時**：放不下的按鈕會移入選單
* **沒有按鈕的窗格**：**Background tasks** 和 **Plan** 等窗格會在工作階段有內容可在這些窗格中顯示時列出

若要跨螢幕工作，將窗格（例如差異或終端機）彈出到其自己的視窗中，完成後將其停靠回來。Claude 會在主視窗中繼續工作。

> [!NOTE]
>
> 本節中的窗格佈局、終端機、檔案編輯器和檢視模式需要 Claude Desktop v1.2581.0 或更新版本。在 macOS 上開啟 **Claude > Check for Updates…** 或在 Windows 上開啟 **Help > Check for Updates…** 以更新。

### 查看工作階段詳細資訊

工作階段詳細資訊面板是聊天旁的一組卡片，顯示工作階段在何處執行、變更了什麼、正在執行什麼，以及其上下文使用情況。此面板會在您啟動工作階段後出現，前提是聊天區域的寬度足以容納它。

#### 隱藏或顯示工作階段詳細資訊面板

若要隱藏或顯示面板，請點擊工作階段標題列中的 **Hide session rail** 或 **Show session rail**，或在標題列的 **⋮** 選單中點擊。如果您仍然看不到面板，請[檢查您使用的是哪種 Code 標籤佈局](#check-which-layout-you-have)。

### 在終端機中執行命令

整合終端機讓您在工作階段旁執行命令，而無需切換到另一個應用程式。點擊工作階段標題列中的 **Terminal**，或在 macOS 或 Windows 上按 **Ctrl+\`**。終端機在您工作階段的工作目錄中開啟，並與 Claude 共用相同的環境，因此 `npm test` 或 `git status` 等命令會看到 Claude 正在編輯的相同檔案。若要開啟第二個終端機標籤，請點擊終端機窗格標題中的 **+** 或右鍵點擊聊天中的資料夾以選擇 **Open in terminal**。

如果 WSL 工作階段沒有終端機，請參閱[如果終端機或連接器無法使用](https://code.claude.com/docs/zh-TW/desktop-wsl.md#check-for-the-terminal-and-connectors)。終端機可在本機和 [SSH](#ssh-sessions) 工作階段中使用，但在 [Windows 遠端機器](#windows-remote-machines)上有所限制。

### 開啟和編輯檔案

若要開啟 Claude 提及的檔案，請點擊聊天中的檔案路徑。

若要自行編輯檔案，請使用[檔案窗格](#arrange-your-workspace)：

* **本機工作階段**：您可以編輯工作階段工作目錄內的檔案，但某些僅供檢視的檔案除外，例如 `.mcp.json` 和 `.claude/settings.json`。若要變更這類檔案，請[在其他應用程式中開啟它](#open-files-in-other-apps)。
* **雲端、SSH 和 WSL 工作階段**：檔案窗格僅供檢視，因此請要求 Claude 進行編輯。

#### 在檔案窗格中儲存編輯

預設情況下，您在檔案窗格中的編輯會自動儲存，因此窗格不會顯示 **Save** 按鈕。若要自行儲存編輯，請在窗格的 **⋮** 選單中取消勾選 **Auto save**。關閉 **Auto save** 後，變更檔案後點擊 **Save** 以寫入您的編輯，或點擊 **Cancel** 以還原編輯。

如果窗格警告檔案已在磁碟上變更，請點擊 **Override** 以用您的編輯覆寫磁碟上的版本，或點擊 **Discard** 以捨棄您的編輯。

### 在其他應用程式中開啟檔案

右鍵點擊聊天、差異檢視器或檔案窗格中的任何檔案路徑以開啟上下文選單：

* **Attach as context**：將檔案新增到您的下一個提示詞
* **Open in**：在已安裝的編輯器（如 VS Code、Cursor 或 Zed）中開啟檔案
* **Show in Finder**（在 macOS 上），**Show in Explorer**（在 Windows 上）：開啟包含資料夾
* **Copy**：子選單，可複製檔案的 **Absolute path**、**Relative path** 或 **Filename**

### 切換檢視模式

檢視模式控制聊天逐字稿中顯示多少詳細資訊。若要切換檢視模式，請從工作階段標題旁的插入符號開啟工作階段選單並選擇 **Transcript view**，或在 macOS 或 Windows 上按 **Ctrl+O** 以循環瀏覽它們。Thinking 模式僅在 Claude 在您正在檢視的工作階段中產生思考後才會出現在選單中。

| 模式 | 它顯示什麼 |
| - | - |
| **Normal** | 工具呼叫摺疊成摘要，具有完整文字回應 |
| **Thinking** | 工具呼叫摺疊成摘要，加上 Claude 的思考 |
| **Verbose** | Claude 採取的每個工具呼叫、檔案讀取和中間步驟，加上 Claude 的思考 |

使用 Thinking 來追蹤 Claude 的推理，工具呼叫仍然摺疊。在除錯 Claude 為什麼採取特定操作時使用 Verbose。Claude Desktop 1.46388.1 之前的版本也列出 Summary 模式，而仍設定為 Summary 的工作階段在您更新後會以 Normal 開啟。

### 鍵盤快捷鍵

在 macOS 上按 **Cmd+/** 或在 Windows 上按 **Ctrl+/** 以查看 Code 標籤中可用的所有快捷鍵。本節中的表格顯示 macOS 按鍵。在 Windows 和 Linux 上，請替換以下按鍵：

* **Cmd+Option**：按 **Alt**
* **Cmd+Ctrl**：按 **Ctrl+Alt**
* **Cmd**：按 **Ctrl**

以 `Ctrl` 開頭的快捷鍵在每個平台上都相同。

| 快捷鍵 | 操作 |
| - | - |
| `Cmd` `/` | 顯示鍵盤快捷鍵 |
| `Cmd` `N` | 新工作階段 |
| `Cmd` `Option` `1`–`9` | 在[目前佈局](#check-which-layout-you-have)的新工作階段畫面中，選擇環境 |
| `Cmd` `Option` `0` | 在目前佈局的新工作階段畫面中，開啟 [**New environment** 對話框](#create-a-saved-environment) |
| `Cmd` `W` | 關閉工作階段 |
| `Ctrl` `Tab` / `Ctrl` `Shift` `Tab` | 在工作階段之間切換 |
| `Cmd` `Shift` `]` / `Cmd` `Shift` `[` | 下一個或上一個工作階段 |
| `Esc` | 停止 Claude 的回應 |
| `Tab` / `Right arrow` | 在空白的提示詞輸入框中[接受建議的提示詞](#accept-a-suggested-prompt) |
| `Cmd` `Shift` `D` | 切換差異窗格 |
| `Cmd` `Shift` `B` | 切換瀏覽器窗格 |
| `Cmd` `Shift` `S` | 在瀏覽器中選擇元素 |
| `Ctrl` `` ` `` | 切換終端機窗格 |
| `Cmd` `\` | 關閉焦點窗格 |
| `Cmd` `Ctrl` `W` | 將焦點工作階段移出[分割檢視](#work-in-parallel-with-sessions) |
| `Cmd` `;` | 開啟側邊聊天 |
| `Ctrl` `O` | 循環檢視模式 |
| `Cmd` `Shift` `M` | 開啟權限模式選單 |
| `Cmd` `Shift` `I` | 開啟模型選單 |
| `Cmd` `Shift` `E` | 開啟工作量選單 |
| `1`–`9` | 在開啟的選單中選擇項目 |

這些快捷鍵適用於 Code 標籤。在 Desktop 中，`Shift+Tab` 不會像在終端機的 [interactive mode](https://code.claude.com/docs/zh-TW/interactive-mode.md#keyboard-shortcuts) 中那樣循環切換權限模式。

### 檢查使用情況

若要查看此工作階段的上下文視窗已使用多少，請先確認您的 Code 標籤佈局：

* **目前佈局**：[工作階段詳細資訊面板](#see-session-details)中 **Context** 卡片的標題會以百分比顯示。開啟該卡片即可依類別查看占用視窗的內容。
* **[較早的佈局](#check-which-layout-you-have)**：點擊模型選擇器旁的使用情況環。其彈出視窗會顯示您的上下文視窗使用情況。

無論使用哪種佈局，在提示詞輸入框中輸入 `/context`，即可在聊天中列出此工作階段上下文視窗的分類明細。

在兩種佈局中，使用情況環都位於提示詞輸入框下方的那一列。點擊它即可查看您的方案使用情況，該使用情況在您所有的 Claude Code 使用介面中共用。

## 讓 Claude 使用您的電腦

電腦使用讓 Claude 開啟您的應用程式、控制您的螢幕，並以您的方式直接在您的機器上工作。要求 Claude 與沒有 CLI 的桌面工具互動，或自動化只能透過 GUI 運作的內容。對於執行和測試 iOS 應用程式，Desktop 會開啟專用的 [iOS Simulator 窗格](https://code.claude.com/docs/zh-TW/desktop-ios-simulator.md)，而不是控制您的螢幕；該窗格無需啟用電腦使用即可運作。

> [!NOTE]
>
> 電腦使用是 macOS 和 Windows 上的研究預覽，需要 Pro、Max 或 Ultra 計畫。它在 Team 或 Enterprise 計畫上不可用。Claude Desktop 應用程式必須執行。在 macOS 上，電腦使用需要 macOS 14 或更新版本。

電腦使用預設為關閉。[在設定中啟用它](#enable-computer-use)，然後 Claude 才能控制您的螢幕。在 macOS 上，您還需要授予協助工具和螢幕錄製權限。

在 macOS 上，電腦使用也可以在背景執行：Claude 在您批准的應用程式中工作，同時您繼續工作。

> [!WARNING]
>
> 與[沙箱化 Bash 工具](https://code.claude.com/docs/zh-TW/sandboxing.md)不同，電腦使用在您的實際桌面上執行，可以存取您批准的任何內容。Claude 會檢查每個操作並標記螢幕上內容的潛在提示注入，但信任邊界不同。有關最佳實踐，請參閱[電腦使用安全指南](https://support.claude.com/en/articles/14128542)。

### 何時應用電腦使用

Claude 有多種方式與應用程式或服務互動，電腦使用是最廣泛和最慢的。它首先嘗試最精確的工具：

* 如果您有服務的[連接器](#connect-external-tools)，Claude 會使用連接器。
* 如果任務是 shell 命令，Claude 會使用 Bash。
* 如果任務是瀏覽器工作且您已設定[Chrome 中的 Claude](https://code.claude.com/docs/zh-TW/chrome.md)，Claude 會使用它。
* 如果任務是執行或測試 iOS 應用程式，Claude 會使用 [iOS Simulator 窗格](https://code.claude.com/docs/zh-TW/desktop-ios-simulator.md)，它不使用螢幕控制。
* 如果以上都不適用，Claude 會使用電腦使用。

[每個應用程式的存取層級](#app-permissions)強化了這一點：瀏覽器限制為僅檢視，終端機和 IDE 限制為僅點擊，引導 Claude 使用專用工具，即使電腦使用處於活動狀態。螢幕控制保留給其他工具無法到達的內容，例如原生應用程式、硬體控制面板或沒有 API 的專有工具。

### 啟用電腦使用

電腦使用預設為關閉。如果您要求 Claude 執行需要它的操作而它處於關閉狀態，Claude 會告訴您如果在設定中啟用電腦使用，它可以執行該任務。

**1. 更新桌面應用程式**

確保您有最新版本的 Claude Desktop。在 macOS 和 Windows 上，在 [claude.com/download](https://claude.com/download) 下載或更新；在 Linux 上，透過您的套件管理員更新（[說明](https://code.claude.com/docs/zh-TW/desktop-linux.md)）。然後重新啟動應用程式。

**2. 開啟切換**

在桌面應用程式中，開啟 **Settings**，然後：

* **如果 Settings 選單列出 This computer**：前往 **This computer > System**
* **否則**：前往 **Capabilities**

在 **Computer use** 下，開啟 **Enable computer use**：

* **Windows**：切換立即生效，設定完成
* **macOS**：繼續下一步

如果您看不到切換，請確認您在 macOS 或 Windows 上使用 Pro、Max 或 Ultra 計畫，然後更新並重新啟動應用程式。

**3. 授予 macOS 權限**

在 macOS 上，在切換生效之前授予兩個系統權限：

* **Accessibility**：讓 Claude 點擊、輸入和滾動
* **Screen Recording**：讓 Claude 看到您螢幕上的內容

「設定」頁面顯示每個權限的目前狀態。如果任一被拒絕，點擊徽章以開啟相關的「系統設定」窗格。

### 應用程式權限

Claude 第一次需要使用應用程式時，會在您的會話中出現提示。點擊 **Allow for this session** 或 **Deny**。批准在目前會話中持續，或在 [Dispatch 產生的會話](#sessions-from-dispatch)中持續 30 分鐘。

提示也顯示 Claude 對該應用程式獲得的控制級別。這些層級由應用程式類別固定，無法變更：

| 層級 | Claude 可以執行的操作 | 適用於 |
| :- | :- | :- |
| 僅檢視 | 在螢幕截圖中查看應用程式 | 瀏覽器、交易平台 |
| 僅點擊 | 點擊和滾動，但不能輸入或使用快捷鍵 | 終端機、IDE |
| 完全控制 | 點擊、輸入、拖動和使用快捷鍵 | 其他所有內容 |

具有廣泛影響力的應用程式（如終端機、Finder 或檔案總管，以及「系統設定」或「設定」）在提示中顯示額外警告，以便您知道批准它們會授予什麼。

在 Settings 中，您[開啟電腦使用](#enable-computer-use)所在的 **Computer use** 區段包含以下選項：

* **Denied apps**：在此處新增應用程式以拒絕它們而不提示。Claude 可能仍會透過允許應用程式中的操作間接影響被拒絕的應用程式，但它無法直接與被拒絕的應用程式互動。
* **Unhide apps when Claude finishes**：當電腦使用未在背景執行時，Claude 工作時會隱藏您的其他視窗，以便它僅與批准的應用程式互動。當 Claude 完成時，隱藏的視窗會被恢復，除非您關閉此設定。

## 管理工作階段

每個工作階段都是一個獨立的對話，具有自己的上下文和變更。您可以並行執行多個工作階段、分支出側邊聊天、讓 Claude 檢查並傳送訊息到您的其他工作階段、將工作傳送到雲端，或讓 Dispatch 從您的手機為您啟動工作階段。

### 使用工作階段並行工作

點擊側邊欄中的 **+ New**，或在 macOS 上按 **Cmd+N** 或在 Windows 上按 **Ctrl+N**，以並行處理多個任務。按 **Ctrl+Tab** 和 **Ctrl+Shift+Tab** 以在工作階段之間切換。

您也可以在目前工作階段旁邊或在其專屬的視窗中開啟第二個工作階段：

* **並排**：在 macOS 上按住 **Option** 或在 Windows 上按住 **Alt**，然後點擊側邊欄中的工作階段，或在該工作階段上按一下滑鼠右鍵並選擇 **Open in**，然後選擇 **Split view**
* **在其專屬的視窗中**：在 macOS 上按住 **Cmd** 或在 Windows 上按住 **Ctrl**，然後點擊工作階段，或在該工作階段上按一下滑鼠右鍵並選擇 **Open in**，然後選擇 **New window**

在分割檢視中，您最後開啟或點擊的窗格具有焦點，另一個窗格則會變暗。若要變更窗格所顯示的工作階段，請點擊該窗格使其取得焦點，然後點擊側邊欄中的工作階段。若要將具有焦點的工作階段移出分割檢視，請在 macOS 上按 **Cmd+Ctrl+W** 或在 Windows 上按 **Ctrl+Alt+W**。

#### 在專屬的 worktree 中執行工作階段

在屬於 Git 儲存庫的專案中，請在開始工作階段之前開啟 **Worktree**，讓工作階段在其專屬的 [Git worktree](https://code.claude.com/docs/zh-TW/worktrees.md)（專案的隔離副本）中執行。**Worktree** 預設為關閉，Claude 會直接在專案資料夾中工作。在[目前的版面配置](#check-which-layout-you-have)中，請在[提示詞輸入框下方的列](#start-a-session)中開啟 **Worktree**。

* **使用[第三方供應商](https://code.claude.com/docs/zh-TW/third-party-integrations.md)時**：如果提示詞輸入框下方的列顯示了專案資料夾控制項，但沒有顯示 **Worktree**，請點選專案資料夾控制項並開啟 **Worktree**
* **作為[已儲存的本機或 SSH 環境](#create-a-saved-environment)的預設值**：在建立或編輯環境時設定 **Worktree**
* **[較早的版面配置](#check-which-layout-you-have)**：選取提示詞輸入框上方、分支名稱旁邊的 **worktree** 核取方塊

Worktrees 預設儲存在 `<project-root>/.claude/worktrees/` 中。若要改為將其儲存在自訂目錄中：

* **本機工作階段**：在 **Settings > Code** 或 **Settings > Claude Code** 中設定 **Worktree location**
* **SSH 工作階段**：在 [SSH 連線](#choose-where-ssh-session-worktrees-go)上設定 **Worktree folder**

您也可以在 **Settings > Code** 或 **Settings > Claude Code** 中設定 **Branch prefix**。Desktop 會將其加在每個 worktree 分支名稱前面，這對於保持 Claude 建立的分支井然有序很有用。

若要在新 worktrees 中包含 gitignored 檔案（如 `.env`），請在您的專案根目錄中建立 [`.worktreeinclude` 檔案](https://code.claude.com/docs/zh-TW/worktrees#copy-gitignored-files-into-worktrees)。請參閱 [worktree 與主要簽出共用的內容](https://code.claude.com/docs/zh-TW/worktrees.md#what-worktrees-share-with-the-main-checkout)，了解 worktree 工作階段從何處讀取專案設定、hook 和 skill。

> [!NOTE]
>
> 工作階段隔離需要 [Git](https://git-scm.com/downloads)。大多數 Mac 預設包含 Git。在終端機中執行 `git --version` 進行檢查；如果它列印版本號，表示已安裝 Git。如果您遇到 Git 錯誤，請在 [Cowork](https://claude.com/product/cowork) 中詢問 Claude 以幫助排除您的設定問題。

### 將資料夾新增到工作階段

在工作階段啟動之前或執行期間新增資料夾：

* **在本機工作階段啟動之前**：在[建立已儲存的環境](#create-a-saved-environment)或編輯環境時，於 **Folders** 下新增資料夾，然後[從該已儲存的環境啟動工作階段](#use-edit-or-remove-a-saved-environment)。
* **在本機或 [SSH](#ssh-sessions) 工作階段執行期間**：點擊提示詞輸入框旁的 **+**，然後選擇 **Add folder**。Claude 會直接在該資料夾中工作，不使用 [worktree](#run-a-session-in-its-own-worktree)。

### 存檔工作階段

在存檔 worktree 中有未提交變更的工作階段之前，請參閱[在工作階段存檔時保留未提交的變更](#keep-uncommitted-changes-when-a-session-is-archived)。若要存檔工作階段，請將滑鼠懸停在側邊欄中的該工作階段上，開啟其選單，然後選擇 **Archive**。該工作階段會移至您的[已存檔工作階段](#organize-and-find-sessions)。

若要讓工作階段在其 pull request 合併或關閉時自動存檔，請在 **Settings > Code** 或 **Settings > Claude Code** 中開啟 **Auto-archive after PR merge or close**。雲端工作階段和仍在執行中的工作階段不會自動存檔。

#### 在工作階段存檔時保留未提交的變更

工作階段存檔時，您可能會遺失該工作階段 worktree 中未提交的變更，因此請先提交您想保留的內容：

* **如果 Desktop 詢問這些變更**：選擇 **Archive anyway** 以捨棄變更，或取消並提交變更
* **如果變更僅有未追蹤的檔案**：請在 Claude 於該工作階段中開啟的 pull request 合併之前，提交您想保留的檔案，因為屆時 Desktop 可能會在不詢問的情況下將其刪除
* **其他任何情況**：worktree 及其變更會保留在磁碟上。對於本機工作階段，Desktop 會在工作階段存檔後或您最後一次開啟它後約 30 天（以較晚者為準）將兩者移除。若要保留變更，請從 [**Archived** 標籤](#organize-and-find-sessions)開啟該工作階段，然後選擇 **Unarchive**

### 整理和尋找工作階段

您可以從側邊欄工作階段清單中的圖示來分組、排序和尋找工作階段：

* **目前的版面配置**：將滑鼠懸停在工作階段清單中的標題上以顯示 **Group and sort** 圖示，然後點擊它。若要尋找已存檔的工作階段，請選擇選單最後一列的 **View all**，然後開啟 **Archived** 標籤。
* **[較早的版面配置](#check-which-layout-you-have)**：**Filter** 圖示無須懸停即會顯示。點擊它以使用 **Group by** 或 **Sort by** 排列清單。若要顯示已存檔的工作階段，請選擇 **Status**，然後選擇 **Archived**。

若要重新命名工作階段，請開啟該工作階段，然後點擊標題列中的工作階段標題。

### 檢查並釋放上下文

若要檢查上下文使用情況，請參閱[檢查使用情況](#check-usage)。當上下文填滿時，Claude 會自動總結對話並繼續工作。您也可以輸入 `/compact` 來更早觸發總結並釋放上下文空間。有關壓縮如何運作的詳細資訊，請參閱[上下文視窗](https://code.claude.com/docs/zh-TW/how-claude-code-works.md#the-context-window)。

### 在工作階段完成時收到通知

桌面應用程式會在 Code 工作階段完成任務且您目前未檢視該工作階段時傳送作業系統通知。對於屬於[專案](https://code.claude.com/docs/zh-TW/claude-projects.md#see-what-needs-you-in-overview)的工作階段，您會改為收到專案的通知。

### 在不偏離工作階段的情況下詢問側邊問題

側邊聊天讓您詢問 Claude 一個使用您工作階段上下文的問題，但不會將任何內容新增回主對話。當您想要理解一段程式碼、檢查假設或探索想法而不引導工作階段偏離時，請使用它。

在 macOS 上按 **Cmd+;** 或在 Windows 上按 **Ctrl+;** 以開啟側邊聊天，或在提示詞輸入框中輸入 `/btw`。側邊聊天可以讀取主執行緒中到該點為止的所有內容。完成後，關閉側邊聊天並在您離開的地方繼續主工作階段。

側邊聊天在本機、SSH 和 WSL 工作階段中可用。桌面應用程式不會將側邊聊天儲存到磁碟，因此您在關閉應用程式後無法返回到一個。

### 觀看背景任務

任務窗格顯示在目前工作階段內執行的背景工作：subagents、背景 shell 命令和[動態工作流程](https://code.claude.com/docs/zh-TW/workflows.md)。當工作階段有背景工作時，請從標題列的 **⋮** 選單中選擇 **Background tasks** 以開啟此窗格。

點擊任何項目以在 subagent 窗格中查看其輸出或停止它。若要查看其他工作階段正在執行的操作，請使用[側邊欄](#work-in-parallel-with-sessions)，或詢問 Claude [為您檢查它們](#work-across-sessions)。

### 跨工作階段工作

Claude 可以列出您的其他 Code 標籤工作階段、讀取每個工作階段一直在執行的操作，以及在它們之間傳送訊息。以日常用語詢問：「哪個工作階段涉及了身份驗證重構？」、「API 工作階段得出了什麼結論？」或「告訴付款工作階段 schema 已變更」。

您也可以詢問 Claude 重新命名或存檔工作階段。例如，請它存檔 PR 已合併的工作階段。

透過此使用介面，Claude 只能看到桌面應用程式本身執行的工作階段：Code 標籤中的本機、[SSH](#ssh-sessions) 和 [WSL](https://code.claude.com/docs/zh-TW/desktop-wsl.md) 工作階段。Claude 看不到雲端工作階段，或您從終端機 CLI 或 VS Code 擴充功能啟動的工作階段，即使在同一專案的 worktrees 中也是如此，因此有九個終端機 worktrees 開啟和兩個桌面工作階段時，Claude 在其中一個回答會報告另一個桌面工作階段。Claude 永遠不會列出您詢問的工作階段。預設情況下，它會看到 20 個最近活躍的工作階段，並跳過已存檔的工作階段，除非您要求它們。[跨工作階段傳訊](https://code.claude.com/docs/zh-TW/cross-session-messaging.md)另外讓 Claude 傳送訊息到[您的其他 Claude Code 工作階段](https://code.claude.com/docs/zh-TW/cross-session-messaging.md#see-which-sessions-claude-can-reach)，包括終端機工作階段。

當 Claude 透過此使用介面傳送訊息到另一個工作階段時，Claude Code 會在那裡將其顯示為一張卡片，標籤為傳送工作階段的標題和返回連結，因此您總是可以看到訊息來自何處。如果接收工作階段正在執行任務中，Claude Code 會保留訊息，Claude 會在目前工作完成後讀取它。接收端的 Claude 可以回覆，Claude Code 會透過此使用介面傳遞回覆。Claude 無法傳遞到已存檔的工作階段，並會在訊息未送達時告訴您。

Claude Code 在工作階段間應用三個安全行為：

* 在 Claude 存檔工作階段之前，您會收到核准卡片，但自動模式和略過權限模式除外，在這兩種模式下，Claude 可以在沒有核准卡片的情況下存檔工作階段。若要被詢問，請切換到 Manual。
* Claude Code 會根據接收工作階段的[入站控制](https://code.claude.com/docs/zh-TW/cross-session-messaging.md#control-inbound-messages)檢查來自此使用介面的每條訊息，即使接收工作階段本身沒有[跨工作階段傳訊](https://code.claude.com/docs/zh-TW/cross-session-messaging.md#availability)。如果您在接收工作階段中將 [`crossSessionInbound`](https://code.claude.com/docs/zh-TW/settings-reference#crosssessioninbound) 設定為 `refuse`，Claude Code 會丟棄來自此使用介面的訊息。Claude Code 會向 Claude 桌面應用程式報告拒絕。在 v2.1.234 之前，Claude Code 會丟棄來自此使用介面到沒有跨工作階段傳訊的接收工作階段的每條訊息。
* Claude Code 引用每條傳入訊息並將其歸因於傳送它的工作階段，Claude 在對其進行操作時仍然遵循接收工作階段自己的權限設定。

### 啟動 Claude 建議的任務

當 Claude 注意到目前任務範圍以外值得修復的內容時，會將該工作建議為一項任務。在[目前的版面配置](#check-which-layout-you-have)上的本機和 SSH 工作階段中，建議會以聊天中的卡片呈現，其按鈕可啟動該任務或將其保留在此工作階段中：

* **Start**：在另一個工作階段中啟動該任務。預設情況下，任務會在目前工作階段的環境中執行。卡片隨後會顯示已啟動工作階段的狀態，而[側邊欄](#work-in-parallel-with-sessions)會在目前工作階段下方列出已啟動的工作階段。
* **Do it here**：將該任務作為訊息傳送到目前工作階段
* **Options**：在點擊 **Start** 之前，檢閱或變更環境、模型、[worktree](#run-a-session-in-its-own-worktree) 和權限等設定
* **Start all**：當卡片列出多項任務時，在各自的工作階段中啟動每項任務，無須等待一項任務完成後再啟動下一項

在雲端工作階段中，以及較早版面配置上的本機和 SSH 工作階段中，建議會以 **Suggested task** 卡片呈現。若要以卡片主要按鈕所示的方式啟動任務（例如 **Send to cloud** 或 **Start with worktree**），請點擊該按鈕。點擊主要按鈕旁的插入符號可查看啟動任務的其他方式，包括 **Do it here**。

### 在雲端執行長時間執行的任務

對於大型重構、測試套件、遷移或其他長時間執行的任務，在開始工作階段時，於[環境選擇器](#start-a-session)中選擇 **Cloud** 下的環境。雲端工作階段預設在 Anthropic 管理的基礎設施上執行，即使您關閉應用程式或關閉電腦，也會繼續執行。隨時檢查以查看進度或引導 Claude 朝不同方向發展。您也可以從 [claude.ai/code](https://claude.ai/code) 或 [Claude 行動應用程式](https://code.claude.com/docs/zh-TW/mobile.md)監控雲端工作階段。

雲端工作階段也支援多個儲存庫。選擇儲存庫的位置：

* **目前的版面配置**：選擇雲端環境後，在提示詞輸入框下方的那一列中選擇。
* **[較早的版面配置](#check-which-layout-you-have)**：在提示詞輸入框上方選擇。若要新增另一個儲存庫，請點擊所選儲存庫旁邊的 **+**。

有關雲端工作階段如何運作的更多資訊，請參閱[在雲端使用 Claude Code](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)。當一項工作需要許多雲端工作階段時，請使用[專案](https://code.claude.com/docs/zh-TW/claude-projects.md)：Claude 會從一個對話中為您啟動並追蹤工作階段。相關步驟請參閱[建立專案](https://code.claude.com/docs/zh-TW/claude-projects.md#create-a-project)。

> [!NOTE]
>
> [SSH 工作階段](#ssh-sessions)中的任務也可以[在 Desktop 中斷連線時繼續執行](#keep-a-task-running-while-desktop-is-disconnected)，但若使用 Claude 帳戶，任務可能會在其登入過期時停止。

### 在另一個使用介面中繼續

若要在其他地方繼續工作階段，請從工作階段標題旁的插入符號或側邊欄中該工作階段的列開啟工作階段選單，然後選擇 **Open in**：

* 選擇 **Cloud** 以將工作階段作為[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)繼續，您的對話會以摘要形式帶過去。在您確認之前，對話框會說明您的檔案是否也會一併移動，以及雲端工作階段準備就緒後是否會存檔此工作階段。透過 [SSH](#ssh-sessions) 或在 [WSL](https://code.claude.com/docs/zh-TW/desktop-wsl.md) 中執行的工作階段無法以此方式移動。
* 選擇已安裝的編輯器或您的檔案管理器，以在其中開啟該工作階段在磁碟上的資料夾。

### 控制哪些工作階段會出現在您的其他裝置上

本機工作階段在 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 將其連線後，就會出現在您的其他裝置上。已連線的工作階段會出現在 [claude.ai/code](https://claude.ai/code) 的工作階段清單中，以及已登入您 claude.ai 帳戶之裝置上的 Claude 應用程式中。

本機工作階段會在您為其開啟 Remote Control 時連線，或在啟動時自動連線：

* **您為該工作階段開啟**：使用該工作階段的 **Remote Control** 開關，或在其提示詞輸入框中輸入 `/remote-control`。
* **在啟動時連線**：當 **Settings > Code** 或 **Settings > Claude Code** 中的 **Connect new sessions to Remote Control** 開啟時，新工作階段會自動連線。如果您從未變更該設定，Desktop 會遵循您使用者設定或受管設定中的 [`remoteControlAtStartup`](https://code.claude.com/docs/zh-TW/settings-reference#remotecontrolatstartup)，其次是您組織的預設值。

若要查看工作階段是否已連線，請查看其[工作階段詳細資料面板](#see-session-details)中 **Environment** 卡片上的 **Remote Control** 開關。

若要讓工作階段不出現在您的其他裝置上，請在您需要的層級關閉 Remote Control：

* **單一工作階段**：關閉其 **Remote Control** 開關。在啟動時即已連線的工作階段中，輸入 `/remote-control` 會讓 Remote Control 保持開啟，並顯示 `Remote Control is already on. This session connected automatically when it started.`。點擊該行上的 **Turn off** 以中斷連線。
* **此電腦上的新 Desktop 工作階段**：在 **Settings > Code** 或 **Settings > Claude Code** 中關閉 **Connect new sessions to Remote Control**。如果它已顯示為關閉，請先將其開啟再關閉，讓 Desktop 儲存您的選擇。儲存後，它會優先於 `remoteControlAtStartup` 和預設值。
* **此電腦上的任何工作階段，包括 CLI**：在 `~/.claude/settings.json` 中將 [`disableRemoteControl`](https://code.claude.com/docs/zh-TW/settings-reference#disableremotecontrol) 設定為 `true`，以阻止工作階段連線。在您儲存該檔案時已連線的工作階段會保持連線，直到您為其關閉 Remote Control。

若要隱藏已出現在您其他裝置上的工作階段，請在 Desktop 中將其存檔。Desktop 也會存檔該工作階段的 Remote Control 副本，使其離開那些裝置上的預設工作階段清單。若要在那裡檢視或刪除它，請參閱[存檔工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#archive-sessions)。

### 來自 Dispatch 的工作階段

[Dispatch](https://support.claude.com/en/articles/13947068) 是與 Claude 的持久對話，存在於 [Cowork](https://claude.com/product/cowork) 中。您向 Dispatch 傳送任務，它決定如何處理它。

任務可以透過兩種方式成為 Code 工作階段：您直接要求一個，例如「開啟 Claude Code 工作階段並修復登入錯誤」，或 Dispatch 決定任務是開發工作並自行產生一個。通常路由到 Code 的任務包括修復錯誤、更新相依性、執行測試或開啟 pull request。研究、文件編輯和試算表工作保留在 Cowork 中。

#### 追蹤 Dispatch 啟動的工作階段

Dispatch 啟動的工作階段會與您的其他工作階段一起出現在 Code 標籤的側邊欄中。使用側邊欄的[預設分組和排序](#organize-and-find-sessions)時，請在其執行所在資料夾的群組中尋找最新的工作階段。當它完成或需要您的核准時，您會在手機上收到推送通知。

如果您已[啟用電腦使用](#let-claude-use-your-computer)，Dispatch 產生的 Code 工作階段也可以使用它。這些工作階段中的應用程式核准在 30 分鐘後過期並重新提示，而不是像常規 Code 工作階段那樣持續整個工作階段。

#### 設定 Dispatch

* **計畫**：Dispatch 需要 Pro、Max 或 Ultra 計畫，在 Team 或 Enterprise 計畫上不可用
* **設定、配對和 Dispatch 設定**：請參閱 [Dispatch 幫助文章](https://support.claude.com/en/articles/13947068)

Dispatch 是當您遠離終端機時與 Claude 合作的多種方式之一。如需與其他選項的比較，請參閱[平台和整合](https://code.claude.com/docs/zh-TW/platforms.md#work-when-you-are-away-from-your-terminal)。

## 擴展 Claude Code

連接外部服務、新增可重複使用的工作流程、自訂 Claude 的行為，並設定預覽伺服器。若要在一個地方管理連接器、skills 和外掛，請點擊側邊欄中的 **Customize**。[Cowork](https://claude.com/product/cowork) 在桌面應用程式中從此 Customize 設定取得其 skills、外掛和連接器，該設定透過您的 claude.ai 帳戶同步，而不是從 CLI 的 `~/.claude` 目錄。

Claude Code 也會在您使用相同帳戶登入的終端機會話中載入為您的 claude.ai 帳戶啟用的 skills 和 plugins。請參閱 [Skills synced from claude.ai](https://code.claude.com/docs/zh-TW/skills.md#how-synced-skills-behave) 和 [Plugins synced from claude.ai](https://code.claude.com/docs/zh-TW/plugins/loading.md#synced-plugins)。

### 連接外部工具

連接器是具有圖形化設定流程的 [MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md)。

在使用 Claude 帳戶的本機或 [SSH](#ssh-sessions) 工作階段中，於工作階段開始前或進行期間，點擊提示詞輸入框旁的 **+** 以新增連接器。選擇 **Add connectors** 以開啟連接器目錄。如果選單改為顯示 **Connectors**，請選擇它，然後選擇 **Browse connectors**。

> [!NOTE]
>
> 以下情況在其他頁面中說明：
>
> * **Connectors 在 WSL 工作階段中呈現灰色**：請參閱[如果終端機或連接器無法使用](https://code.claude.com/docs/zh-TW/desktop-wsl.md#check-for-the-terminal-and-connectors)
> * **雲端工作階段**：請參閱[連接器如何連至 Claude Code](https://code.claude.com/docs/zh-TW/mcp.md#how-connectors-reach-claude-code)

連接後，Claude 可以讀取您的日曆、傳送訊息、建立問題，並直接與您的工具互動。您可以詢問 Claude 在您的工作階段中設定了哪些連接器。若要管理或中斷連接器，請點擊側邊欄中的 **Customize** 並開啟 **Connectors**。

對於 Connectors 中未列出的整合，請透過[設定檔](https://code.claude.com/docs/zh-TW/mcp.md#installing-mcp-servers)手動新增 MCP 伺服器。您也可以[建立自訂連接器](https://support.claude.com/en/articles/11175166-getting-started-with-custom-connectors-using-remote-mcp)。

### 使用 skills

[Skills](https://code.claude.com/docs/zh-TW/skills.md) 擴展 Claude 可以執行的操作。Claude 在相關時自動載入它們，或者您可以直接呼叫一個：在提示框中輸入 `/` 或點擊 **+** 按鈕並選擇 **Slash commands** 以瀏覽可用的內容。這包括 [built-in commands](https://code.claude.com/docs/zh-TW/commands.md)、您的 [custom skills](https://code.claude.com/docs/zh-TW/skills.md#create-your-first-skill)、來自您程式碼庫的專案 skills，以及來自任何 [installed plugins](https://code.claude.com/docs/zh-TW/plugins/install.md) 的 skills。選擇一個，它會在輸入欄位中突出顯示。在其後輸入您的任務並照常傳送。

您可以在 Claude 正在工作時傳送命令，就像傳送任何其他訊息一樣，工作階段會在回合完成後回到閒置狀態。

本機會話從 `~/.claude/skills/` 載入您的個人 skills。[SSH](#ssh-sessions) 會話從遠端主機的主目錄讀取 `~/.claude/skills/`，而不是從您的機器。

本機和雲端會話也會載入為您的 claude.ai 帳戶啟用的 skills，除了本機會話（當您的組織設定 [`disableSideloadFlags`](https://code.claude.com/docs/zh-TW/settings-reference#disablesideloadflags) 時）。雲端會話改為載入它們，而不是 `~/.claude/skills/`，如 [Skills in Cowork and cloud sessions](https://code.claude.com/docs/zh-TW/skills.md#skills-in-cowork-and-cloud-sessions) 所述。

### 安裝 plugins

[Plugins](https://code.claude.com/docs/zh-TW/plugins/overview.md) 是可重複使用的套件，可將 skills、agents、hooks、MCP servers 和 LSP 配置新增到 Claude Code。您可以從桌面應用程式安裝 plugins，而無需使用終端機。

在本機工作階段或 [SSH 工作階段](#ssh-sessions)中，點擊提示詞輸入框旁的 **+** 並選擇 **Add plugins** 以開啟外掛瀏覽器。如果選單改為顯示 **Plugins**，請選擇它，然後選擇 **Browse plugins**，或選擇 **Manage plugins** 以啟用、停用或解除安裝外掛。

您可以將 plugins 限定於您的使用者帳戶、特定專案或僅本機。如果您的組織集中管理 plugins，這些 plugins 在桌面會話中的可用方式與在 CLI 中相同，除了桌面應用程式在 [`disableSideloadFlags`](https://code.claude.com/docs/zh-TW/settings-reference#disablesideloadflags) 下扣留的那些。

plugin 瀏覽器在雲端會話中不可用，而且您從桌面應用程式安裝的 plugins 不適用於雲端會話。雲端會話也不會安裝儲存庫的 `.claude/settings.json` 宣告的 plugins，如 [What carries over from your setup](https://code.claude.com/docs/zh-TW/cloud-environments.md#what-carries-over-from-your-setup) 所述。Plugins 在 WSL 會話中不可用。有關完整的 plugin 參考（包括建立您自己的 plugins），請參閱 [plugins](https://code.claude.com/docs/zh-TW/plugins/overview.md)。

### 配置預覽伺服器

Claude 會自動偵測您的開發伺服器設定，並將配置儲存在您開始會話時選擇的資料夾根目錄中的 `.claude/launch.json`。Preview 使用此資料夾作為其工作目錄，因此如果您選擇了父資料夾，具有自己開發伺服器的子資料夾將不會自動偵測。若要使用子資料夾的伺服器，請直接在該資料夾中開始會話，或手動新增配置。

若要自訂伺服器的啟動方式，例如使用 `yarn dev` 而不是 `npm run dev` 或變更連接埠，請編輯 `.claude/launch.json`。該檔案支援帶註解的 JSON。

```json theme={null}
{
  "version": "0.0.1",
  "configurations": [
    {
      "name": "my-app",
      "runtimeExecutable": "npm",
      "runtimeArgs": ["run", "dev"],
      "port": 3000
    }
  ]
}
```

您可以定義多個配置以從同一專案執行不同的伺服器，例如前端和 API。請參閱下面的 [examples](#examples)。

#### 自動驗證變更

啟用 `autoVerify` 時，Claude 會在編輯檔案後自動驗證程式碼變更。它會擷取螢幕截圖、檢查錯誤，並在完成回應之前確認變更有效。

自動驗證預設為開啟。若要按專案停用，請將 `"autoVerify": false` 新增到 `.claude/launch.json`，或在 Browser 窗格的 **⋮** 選單中關閉 **Auto-verify changes**。

```json theme={null}
{
  "version": "0.0.1",
  "autoVerify": false,
  "configurations": [
    {
      "name": "my-app",
      "runtimeExecutable": "npm",
      "runtimeArgs": ["run", "dev"],
      "port": 3000
    }
  ]
}
```

停用後，預覽工具仍然可用，您可以隨時要求 Claude 進行驗證。自動驗證使其在每次編輯後自動進行。

#### 配置欄位

`configurations` 陣列中的每個項目接受以下欄位：

| 欄位 | 類型 | 描述 |
| - | - | - |
| `name` | string | 此伺服器的唯一識別碼 |
| `runtimeExecutable` | string | 要執行的命令，例如 `npm`、`yarn` 或 `node` |
| `runtimeArgs` | string\[] | 傳遞給 `runtimeExecutable` 的引數，例如 `["run", "dev"]` |
| `port` | number | 您的伺服器監聽的連接埠。預設為 3000 |
| `cwd` | string | 相對於您的專案根目錄的工作目錄。預設為專案根目錄。使用 `${workspaceFolder}` 明確參考專案根目錄 |
| `env` | object | 以鍵值對表示的其他環境變數，例如 `{ "NODE_ENV": "development" }`。請勿在此處放置機密，因為此檔案會提交到您的儲存庫。關於機密，請參閱[為開發伺服器設定環境變數](#set-environment-variables-for-dev-servers)。 |
| `autoPort` | boolean | 如何處理連接埠衝突。請參閱 [Port conflicts](#port-conflicts) |
| `program` | string | 使用 `node` 執行的指令碼。請參閱 [when to use `program` vs `runtimeExecutable`](#when-to-use-program-vs-runtimeexecutable) |
| `args` | string\[] | 傳遞給 `program` 的引數。僅在設定 `program` 時使用 |
| `url` | string | preview 開啟的位址，而不是 `http://localhost:<port>`。請參閱 [open the preview at a specific URL](#open-the-preview-at-a-specific-url) |

##### 何時使用 `program` 與 `runtimeExecutable`

使用 `runtimeExecutable` 搭配 `runtimeArgs` 透過套件管理器啟動開發伺服器。例如，`"runtimeExecutable": "npm"` 搭配 `"runtimeArgs": ["run", "dev"]` 執行 `npm run dev`。

當您有想要直接使用 `node` 執行的獨立指令碼時，使用 `program`。例如，`"program": "server.js"` 執行 `node server.js`。使用 `args` 傳遞其他標誌。

##### 在特定 URL 開啟 preview

根據預設，preview 開啟 `http://localhost:<port>`。當您的伺服器需要不同的位址時，設定 `url`。常見情況是需要本機 HTTPS 的伺服器、使用 `*.localhost` 子網域的應用程式，以及透過重新導向登入您的應用程式。

```json theme={null}
{
  "version": "0.0.1",
  "configurations": [
    {
      "name": "my-app",
      "runtimeExecutable": "npm",
      "runtimeArgs": ["run", "dev"],
      "port": 8443,
      "url": "https://localhost:8443"
    }
  ]
}
```

Localhost 位址直接開啟，完全像預設連接埠位址一樣。這包括 `localhost`、任何 `*.localhost` 子網域、`127.0.0.1` 和 `::1`。基於安全考量，localhost `url` 必須只是您伺服器的來源 — 沒有路徑或查詢，且連接埠必須符合項目的連接埠。若要顯示特定頁面，請在 preview 開啟後要求 Claude 導覽到該處。具有路徑、查詢或不符合連接埠的 localhost `url` 會報告為配置錯誤，該錯誤會命名 url 並顯示修正。

對於任何其他位址，Desktop 會在 preview 首次開啟它時要求您的許可，就像您在 preview 中瀏覽到新網站時一樣。外部位址可能包括路徑。選擇 **Always allow** 以在未來跳過該網站的提示。限制 preview 中外部網站的組織原則仍然適用。

若要預覽您已經自己執行的伺服器，請設定 `url` 而不設定命令。Claude 會將 preview 附加到您執行中的伺服器，而不是啟動一個：

```json theme={null}
{
  "version": "0.0.1",
  "configurations": [
    {
      "name": "my-app",
      "url": "https://app.localhost:3000"
    }
  ]
}
```

`url` 必須是 `http` 或 `https`，且不得包含使用者名稱或密碼。

#### 連接埠衝突

`autoPort` 欄位控制當您偏好的連接埠已在使用時會發生什麼：

* **`true`**：Claude 自動尋找並使用空閒連接埠。適合大多數開發伺服器。
* **`false`**：Claude 失敗並出現錯誤。當您的伺服器必須使用特定連接埠時使用此選項，例如 OAuth 回呼或 CORS 允許清單。
* **未設定（預設）**：您的伺服器會取得下一個空閒連接埠，與 `true` 相同，但下述一種情況除外。在 Claude Desktop v2.37337.0 之前，Claude 會改為詢問伺服器是否需要該確切連接埠，然後將您的答案儲存在 `launch.json` 中。

如果您偏好的連接埠已在使用且未設定 `autoPort`，當下列所有條件都成立時，您的伺服器會保持停止狀態：

* 您透過 `npm`、`yarn`、`pnpm` 或 `bun` 指令碼啟動伺服器。
* 您偏好的連接埠寫死在該指令碼中，或 Claude 無法檢查該指令碼。
* 您未在 `runtimeArgs` 中傳遞連接埠。

在這種情況下，請釋放該連接埠、移除寫死的值，或變更 `port` 以符合指令碼。改為設定 `"autoPort": true` 僅適用於會讀取 `PORT` 的指令碼。

讓您的伺服器從 `PORT` 環境變數讀取其連接埠，該變數帶有指派的連接埠。當 Claude 將您的伺服器移至不同的連接埠時，也會改寫 `runtimeArgs` 中的 `--port` 或 `-p` 值以使其相符。

#### 範例

這些配置顯示不同專案類型的常見設定：

> [tab] Next.js
>
> 此配置使用 Yarn 在連接埠 3000 上執行 Next.js 應用程式：
>
> ```json theme={null}
> {
>   "version": "0.0.1",
>   "configurations": [
>     {
>       "name": "web",
>       "runtimeExecutable": "yarn",
>       "runtimeArgs": ["dev"],
>       "port": 3000
>     }
>   ]
> }
> ```

> [tab] Multiple servers
>
> 對於具有前端和 API 伺服器的 monorepo，定義多個配置。前端使用 `autoPort: true`，因此如果 3000 被佔用，它會選擇空閒連接埠，而 API 伺服器需要確切的連接埠 8080：
>
> ```json theme={null}
> {
>   "version": "0.0.1",
>   "configurations": [
>     {
>       "name": "frontend",
>       "runtimeExecutable": "npm",
>       "runtimeArgs": ["run", "dev"],
>       "cwd": "apps/web",
>       "port": 3000,
>       "autoPort": true
>     },
>     {
>       "name": "api",
>       "runtimeExecutable": "npm",
>       "runtimeArgs": ["run", "start"],
>       "cwd": "server",
>       "port": 8080,
>       "env": { "NODE_ENV": "development" },
>       "autoPort": false
>     }
>   ]
> }
> ```

> [tab] Node.js script
>
> 若要直接執行 Node.js 指令碼而不是使用套件管理器命令，請使用 `program` 欄位：
>
> ```json theme={null}
> {
>   "version": "0.0.1",
>   "configurations": [
>     {
>       "name": "server",
>       "program": "server.js",
>       "args": ["--verbose"],
>       "port": 4000
>     }
>   ]
> }
> ```

## 環境設定

您在[啟動工作階段](#start-a-session)時選擇的環境，決定了 Claude 在何處執行以及您如何連線：

* **Local**：在您的機器上執行，可直接存取您的檔案
* **Cloud**：預設在 Anthropic 管理的基礎架構上執行。即使您關閉應用程式，工作階段仍會繼續。
* **SSH**：在您透過 SSH 連線的遠端機器上執行，例如您自己的伺服器、雲端 VM 或開發容器。正在執行的任務可以[在 Desktop 中斷連線時繼續進行](#keep-a-task-running-while-desktop-is-disconnected)，但使用 Claude 帳戶時，任務可能會在其登入過期時停止。
* **WSL**（Windows）：在您機器上的 [WSL 2 發行版](https://code.claude.com/docs/zh-TW/desktop-wsl.md)內執行，使用其 Linux 工具鏈和原生路徑

### 建立已儲存的環境

已儲存的環境是[環境選擇器](#start-a-session)中的一個項目，記錄 Claude 的執行位置，讓您之後可以在該處開始工作階段。本機或 SSH 環境也會保存 Claude 工作所在的資料夾。已儲存的本機與 SSH 環境屬於[目前版面配置](#check-which-layout-you-have)的一部分，因此若您看不到它們，請確認您使用的是哪種版面配置，以及如何取得目前的版面配置。

**1. 開啟 New environment 對話方塊**

開啟提示詞輸入框下方的環境選擇器，然後選取其選單底部的 **New environment**。

**2. 選擇 Claude 的執行位置**

選取 **Local**、**SSH** 或 [**Cloud**](#cloud-sessions) 分頁，並填寫該分頁上的表單。在 **SSH** 分頁上，選擇一個[連線](#ssh-sessions)以及遠端機器上的資料夾。

**3. 儲存環境**

選取 **Create environment**，或在 **Cloud** 分頁上選取 **Add environment**。

#### Desktop 為您建立的環境

如果環境選擇器列出了您未建立的本機或 SSH 環境，表示是 Desktop 為您建立的。當您第一次在[目前版面配置](#check-which-layout-you-have)中開啟 Code 分頁時，Desktop 最多會建立八個環境。這些環境來自您上個月最常使用的本機和 SSH 資料夾。您可以[編輯或刪除它們](#use-edit-or-remove-a-saved-environment)。

#### 使用、編輯或移除已儲存的環境

在[環境選擇器](#start-a-session)中找到該環境的項目：

* **啟動工作階段**：選取該項目。
* **編輯或刪除**：將滑鼠游標停留在該項目上，然後點選齒輪圖示。若要刪除本機或 SSH 環境，請在 **Edit environment** 中點選 **Delete environment**。
* **封存雲端環境**：請參閱[封存環境](https://code.claude.com/docs/zh-TW/cloud-environments.md#archive-an-environment)。

### 本機工作階段中的環境變數

若要為本機工作階段設定環境變數，請[將其新增至已儲存的本機環境](#set-environment-variables-for-local-sessions)，然後從該環境開始新的工作階段。

`PATH` 和 `CLAUDE_CONFIG_DIR` 等變數有其專屬的說明：

| 變數 | 改為執行的操作 |
| :- | :- |
| `PATH`，即系統搜尋 `npm` 等程式的資料夾 | 請參閱[工作階段找不到已安裝的工具](#session-not-finding-installed-tools)。在 Windows 上，Desktop 不會讀取 PowerShell 設定檔，因此請在您的使用者或系統環境變數中設定 `PATH`，然後結束並重新開啟 Desktop。 |
| 來自 [`claude_desktop_config.json`](#mcp-servers-from-the-claude-desktop-chat-app) 的 MCP 伺服器所用的變數 | 結束 Desktop，在該伺服器的 `env` 區塊中設定，然後重新開啟 Desktop |
| [`CLAUDE_CONFIG_DIR`](https://code.claude.com/docs/zh-TW/env-vars#variables) 或 [`CLAUDE_CODE_TMPDIR`](https://code.claude.com/docs/zh-TW/env-vars#variables) | 在[您為開發伺服器設定變數的其中一個位置](#set-environment-variables-for-dev-servers)設定，然後結束並重新開啟 Desktop |
| `API_TIMEOUT_MS`、`ANTHROPIC_BASE_URL` 或 Desktop 自行設定的其他變數 | 請參閱[Desktop 自行設定的環境變數](#environment-variables-desktop-sets-itself) |

在 macOS 或 Linux 上，如果您以 `export` 設定的變數在 Claude 執行的命令中遺失或不正確，請參閱[Claude 執行的命令中匯出的變數遺失或不正確](#exported-variable-missing-or-wrong-in-commands-claude-runs)。

#### 為本機工作階段設定環境變數

將變數新增至已儲存的本機環境，並從該環境啟動您的工作階段。Desktop [會自行設定某些變數](#environment-variables-desktop-sets-itself)，例如 `API_TIMEOUT_MS`，您的工作階段會取得 Desktop 的值，而不是您的值。

> [!NOTE]
>
> 如果新的工作階段在提示詞輸入框下方沒有顯示任何環境，表示您使用的是[較早的版面配置](#check-which-layout-you-have)，其中沒有已儲存的本機環境。請改用[本機環境編輯器](#use-the-local-environment-editor)。

**1. 開啟本機環境的表單**

* **建立已儲存的本機環境**：選取環境選擇器選單底部的 [**New environment**](#create-a-saved-environment)，然後選取 **Local** 分頁
* **變更您已有的環境**：在環境選擇器中，將游標停留在 **Local** 下的已儲存環境上，然後按一下齒輪圖示以開啟 [**Edit environment**](#use-edit-or-remove-a-saved-environment)

**2. 輸入變數**

選取 **Environment variables**，每行輸入一個 `KEY=value`，然後選取 **Done**。

**3. 儲存環境**

選取 **Create environment** 或 **Save**。

只有從該環境啟動的工作階段才會取得這些變數。

若要為每個本機工作階段設定變數，請將其新增至 `~/.claude/settings.json` 檔案中的 [`env` 鍵](https://code.claude.com/docs/zh-TW/env-vars#set-variables-in-settings-files)。如果該變數已存在於 Desktop 啟動工作階段時使用的環境中，Claude Code 會[忽略該值](https://code.claude.com/docs/zh-TW/settings-reference.md#how-env-values-interact-with-your-shell)。如需支援變數的完整清單，請參閱[環境變數](https://code.claude.com/docs/zh-TW/env-vars.md)。

#### 為開發伺服器設定環境變數

若要在不提交至 [`launch.json`](#configure-preview-servers) 的情況下為開發伺服器提供機密資訊，請在下列其中一處設定，然後重新啟動 Desktop：

* **macOS 和 Linux**：在您的 shell 設定檔中匯出
* **Windows**：將其新增至您的使用者或系統環境變數
* **任何平台**：如果您能開啟[本機環境編輯器](#use-the-local-environment-editor)，請將其儲存在該編輯器中

開發伺服器不會取得您新增至[已儲存的環境](#create-a-saved-environment)或 `~/.claude/settings.json` 的變數。

#### 使用本機環境編輯器

若要開啟本機環境編輯器，請點選您自己電腦項目上的齒輪圖示，而不是已儲存環境上的齒輪圖示：

* **位於提示詞輸入框下方的選擇器**：將滑鼠游標停留在您電腦的項目上，即 **Local** 下的第一個項目。如果出現齒輪圖示，請點選它。如果沒有出現，表示無法使用該編輯器，請以其他方式為[本機工作階段](#set-environment-variables-for-local-sessions)或[開發伺服器](#set-environment-variables-for-dev-servers)設定變數。
* **位於提示詞輸入框上方的選擇器**：將滑鼠游標停留在 **Local** 上，然後點選齒輪圖示

每行輸入一個 `KEY=value`，然後選取 **Save changes**。您在此處儲存的變數會以加密方式儲存在您的電腦上。本機工作階段會取得這些變數，但 [Desktop 自行設定的](#environment-variables-desktop-sets-itself)任何變數（例如 `API_TIMEOUT_MS`）除外。重新啟動 Desktop 即可將您的變數提供給開發伺服器。

#### Claude 執行的命令中缺少匯出的變數或其值錯誤

如果 Claude 在 macOS 或 Linux 上執行的命令沒有取得您在 `~/.zshrc` 或 `~/.bashrc` 中以 `export` 設定的變數，或取得錯誤的值，請依序嘗試下列步驟：

**1. 啟動新的工作階段**

請 Claude 再次執行該命令。

**2. 結束並重新開啟 Desktop**

然後啟動新的工作階段。

**3. 檢查您已儲存的變數**

如果命令取得了錯誤的值，請檢查您是否也在[已儲存的環境](#use-edit-or-remove-a-saved-environment)或[本機環境編輯器](#use-the-local-environment-editor)中設定了該變數。若是如此，請在該處變更值並啟動新的工作階段。

**4. 使用已儲存的環境**

將變數新增至[已儲存的本機環境](#set-environment-variables-for-local-sessions)，然後從該環境啟動新的工作階段。對於 `PATH`、`CLAUDE_CONFIG_DIR` 或 `API_TIMEOUT_MS` 等變數，請改為遵循[其各自的說明](#environment-variables-in-local-sessions)。

在 v2.1.304 之前，Claude Code 不會將匯出的變數傳遞給命令，因此請[檢查工作階段執行的版本](#claude-code-version-in-the-code-tab)。

#### Desktop 自行設定的環境變數

如果您設定了 `API_TIMEOUT_MS` 或 `ANTHROPIC_BASE_URL`，但本機工作階段中沒有任何變化，這是因為 Desktop 會自行設定這些[變數](https://code.claude.com/docs/zh-TW/env-vars.md#variables)以及其他變數。無論您是在 shell 設定檔、Windows 使用者或系統變數、本機環境編輯器，還是已儲存的環境中設定，本機工作階段都會取得 Desktop 的值。將您的值移至設定檔也沒有幫助，因為 Claude Code 在本機工作階段中會[忽略該值](https://code.claude.com/docs/zh-TW/settings-reference.md#how-env-values-interact-with-your-shell)。

* `API_TIMEOUT_MS`：本機工作階段會取得 `900000`，即 15 分鐘。若需要更長的逾時時間，請[安裝 Claude Code CLI](https://code.claude.com/docs/zh-TW/quickstart.md) 並改用它取代 Desktop。[在您的 shell 中設定該變數](https://code.claude.com/docs/zh-TW/env-vars.md#set-variables-in-your-shell)，然後在終端機中執行 `claude`。
* `ANTHROPIC_BASE_URL`：當您以 Claude 帳戶登入時，本機工作階段會取得 Anthropic 的 API 主機。若要使用閘道，請改為設定 Desktop 的[第三方推論設定](https://code.claude.com/docs/zh-TW/llm-gateway-connect.md#desktop-app)。

#### 關閉延伸思考

[延伸思考](https://code.claude.com/docs/zh-TW/model-config.md#extended-thinking)預設為啟用，可提升複雜推理任務的效能，但會使用額外的 token。若要關閉它，請在[已儲存的本機環境](#set-environment-variables-for-local-sessions)或[本機環境編輯器](#use-the-local-environment-editor)中將 `MAX_THINKING_TOKENS` 設定為 `0`。思考隨後會在 Anthropic API 上關閉，但 Opus 5.5、Sonnet 5.5、Haiku 5.5 和 Fable 模型除外，這些模型一律使用延伸思考。

在 Opus 5 上，還必須在啟動工作階段之前選擇 `high` 或更低的 effort。在[目前版面配置](#check-which-layout-you-have)中，開啟模型選擇器並在 **Effort** 下選取一個等級。如果您以較高的等級啟動了工作階段，請以 `high` 或更低的等級啟動新的工作階段。

#### 固定思考預算

在具有[自適應推理](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)的模型上，Claude Code 會忽略正值 `MAX_THINKING_TOKENS` 中的數字本身，因為改由自適應推理控制思考深度。在 Opus 4.6 和 Sonnet 4.6 上，將 `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING` 設為 `1` 即可使用固定的思考預算；Fable 模型、Sonnet 5 及更新版本、Haiku 5.5，以及 Opus 4.7 及更新版本一律使用自適應推理，沒有固定預算模式。

### 受管裝置上的本機工作階段

如果您電腦的項目在環境選擇器中呈灰色，並顯示工具提示 **Disabled by your organization**，表示您的管理員已[關閉本機工作階段](#managed-settings)。在 Windows 上，[WSL](https://code.claude.com/docs/zh-TW/desktop-wsl.md) 項目（其在受管裝置上的可用性是[另外管理的](https://code.claude.com/docs/zh-TW/admin-setup.md#wsl-sessions-in-claude-code-desktop)）也會以相同方式呈灰色。

如果已設定 SSH 連線，新的工作階段預設會使用第一個 SSH 連線。如果您嘗試繼續現有的本機工作階段，Desktop 會顯示訊息，告知此裝置無法使用本機工作階段。當您選取[已儲存的本機環境](#create-a-saved-environment)時，會顯示此錯誤：`Couldn’t switch environments: the Local environment isn’t available anymore.` 請改為選擇 [SSH](#ssh-sessions) 或[雲端](#cloud-sessions)環境，或聯絡您的 IT 團隊。

### 雲端工作階段

即使您關閉應用程式，雲端工作階段仍會在背景繼續執行。使用量會計入您的[訂閱方案限制](https://code.claude.com/docs/zh-TW/costs.md)，不另外收取運算費用。

若要新增、編輯或[封存](https://code.claude.com/docs/zh-TW/cloud-environments.md#archive-an-environment)雲端環境，請開啟[環境選擇器](#start-a-session)：

* **新增環境**：選取選擇器選單底部的 **New environment**，然後選取 [**New environment** 對話方塊](#create-a-saved-environment)的 **Cloud** 分頁
* **編輯或封存您自己的其中一個環境**：將滑鼠游標停在該環境上，然後按一下齒輪圖示

如需設定網路存取和環境變數的詳細資訊，請參閱[設定雲端環境](https://code.claude.com/docs/zh-TW/cloud-environments.md)。

### SSH 工作階段

SSH 工作階段可讓您在遠端機器上執行 Claude Code，同時使用桌面應用程式作為介面。這對於處理位於雲端 VM、開發容器，或具有特定硬體或相依性的伺服器上的程式碼庫很有用。

> [!NOTE]
>
> 如果您搭配[第三方供應商](https://code.claude.com/docs/zh-TW/third-party-integrations.md)使用 Desktop，SSH 工作階段需要另外設定。請參閱 [SSH remote sessions in Claude Desktop on 3P](https://claude.com/docs/third-party/claude-desktop/ssh-remote-sessions)。

在 [**New environment** 對話方塊](#create-a-saved-environment)中新增 SSH 連線，然後在該連線上開始工作階段。如果新的工作階段在提示詞輸入框下方沒有顯示任何環境，表示您使用的是較早的版面配置。請參閱[檢查您使用的版面配置](#check-which-layout-you-have)。

**1. 開啟 New environment 對話方塊**

在啟動工作階段之前，開啟提示詞輸入框下方的環境選擇器，然後選取其選單底部的 **New environment**。

**2. 新增連線**

在 **New environment** 對話方塊的 **SSH** 分頁上，開啟 **Host** 清單，選取 **Add SSH connection…**，然後填寫連線詳細資訊：

* **Name**：此連線的易記標籤。
* **SSH host**：`user@hostname` 或在 `~/.ssh/config` 中定義的主機。
* **SSH port**：若留空則預設為 22，或使用您 SSH 設定中的連接埠。
* **SSH key (optional)**：您私密金鑰的路徑，例如 `~/.ssh/id_ed25519`。留空即可使用您的 SSH 設定或 SSH agent。
* **Worktree folder**：遠端機器上的資料夾，例如 `~/worktrees`，新的工作階段會在其中建立 worktree。留空即可使用[遠端機器的預設值](#choose-where-ssh-session-worktrees-go)。

然後選取 **Add SSH connection**。

**3. 在該連線上啟動工作階段**

選取遠端機器上的資料夾，然後點選 **Create environment**。您會將該機器和資料夾一起保存為[已儲存的環境](#create-a-saved-environment)，以供之後的工作階段使用。Desktop 會為新的工作階段選取它，因此請輸入您的任務並按下 **Enter**。

遠端機器可以執行 Linux、macOS 或 [Windows](#windows-remote-machines)。Desktop 會在您第一次連線時自動在遠端機器上安裝 Claude Code。連線後，SSH 工作階段支援權限模式、連接器、外掛和 MCP 伺服器。

#### SSH 工作階段的遠端機器需求

Linux 或 macOS 遠端機器需要支援的處理器、具有 SFTP 的 SSH 伺服器、未以 `noexec` 掛載的安裝資料夾、可運作的 shell，以及網路存取。請在連線之前，或在登入後連線失敗時，檢查每一項需求：

* **系統**：x86\_64 或 arm64 處理器。該機器也必須符合 Claude Code 的[系統需求](https://code.claude.com/docs/zh-TW/setup.md#system-requirements)。在 Linux 上，Claude Code 需要 glibc 2.17 或更新版本，或 musl。若要查看機器使用哪一種，請在該機器上執行 `ldd --version`。在 Alpine Linux 等以 musl 為基礎的發行版上，也請安裝 [Claude Code 所需的套件](https://code.claude.com/docs/zh-TW/setup.md#alpine-linux-and-musl-based-distributions)。
* **SFTP**：SSH 伺服器必須提供 SFTP 子系統，其 `sshd_config` 中的 `Subsystem sftp` 行會開啟此子系統。若要檢查，請在您電腦上的終端機中以 `sftp` 連線到相同的主機和連接埠。可正常運作的伺服器會顯示 `sftp>` 提示字元。
* **伺服器上的 `MaxSessions 1`**：若要連線到 `sshd_config` 設定了 `MaxSessions 1` 的伺服器，請執行以下其中一項：
  * **您的電腦執行 macOS 或 Linux**：更新至 Claude Desktop v3.1623.0 或更新版本
  * **您的電腦執行 Windows**：確保 Desktop [透過 OpenSSH 用戶端連線](#use-your-ssh-configuration)，因為 Desktop 的內建 SSH 用戶端無法連線到該伺服器
  * **您可以變更伺服器**：提高 `MaxSessions`，例如提高到 OpenSSH 的預設值 10
* **使用 `MaxSessions 1` 時的登入**：使用不需提示即可運作的登入方式，例如由您的 SSH agent 保存的金鑰。Desktop 每次連線或重新連線時至少會登入兩次。每個[終端機](#run-commands-in-the-terminal)分頁，以及每個您在其中執行以 `!` 開頭之命令的 Desktop 工作階段，預期至少會再多一次登入。Claude 執行的命令則不會有額外登入。
* **使用 `MaxSessions 1` 時的一次性代碼**：如果每次登入都會提示您，例如使用一次性代碼時，`!` 命令會失敗。請改在終端機分頁中執行這些命令，終端機分頁會在自己的窗格中提示。
* **安裝資料夾**：Desktop 會在您家目錄的 `~/.claude/remote/` 下安裝輔助程式和 Claude Code。它會從該處執行這些程式，因此該資料夾不能位於以 `noexec` 掛載的檔案系統上。請在每位連線使用者的家目錄中預留約 1 GB 的磁碟空間。如需該資料夾包含的內容，請參閱[遠端機器上的檔案和程序](#files-and-processes-on-the-remote-machine)。
* **Shell**：遠端機器上為您帳戶設定的 shell 必須能執行透過 SSH 傳送的命令，如同 Bash、Zsh 和 `sh`
* **網路**：Claude Code 在遠端機器上執行，並從該處發出網路請求，因此該機器需要 [Claude Code 所需的網路存取](https://code.claude.com/docs/zh-TW/network-config.md#network-access-requirements)。如果機器無法下載 Claude Code，Desktop 會在您的電腦上下載並上傳。Claude Code 的其他請求仍從遠端機器發出。如果 Linux 遠端機器需要代理伺服器或 CA 憑證，請[為 SSH 工作階段設定](#set-a-proxy-or-a-ca-certificate-for-ssh-sessions)。

#### 檢查遠端機器的主機金鑰

主機金鑰是遠端機器出示以證明其身分的金鑰，而指紋是該金鑰的簡短形式。當您信任某個金鑰時，您的電腦會儲存它，並在不再詢問的情況下連線至任何出示該金鑰的對象。請在信任金鑰之前先檢查它，因為可能有東西正在攔截連線。

首先，根據您看到指紋的位置，找出該金鑰屬於哪台機器：

* **Desktop 詢問 `Connect to <host> for the first time?`，或您選取了 Review new key**：Desktop 所指名的機器，即 `<host>`
* **Desktop 詢問 `Connect through <jump host> for the first time?`**：跳板主機，也就是您的連線所經過的機器，而不是您要連線的目標機器
* **`ssh` 在終端機中詢問或警告**：其訊息所指名的機器，這可能不是您輸入的那台

從機器本身取得該機器自己的指紋，而不是透過您正在檢查的連線取得：

* **由其他人管理該機器**：請向他們索取其主機金鑰指紋
* **由您管理，且它執行 Linux 或 macOS**：在該機器的主控台上，或透過您已信任的連線，在其上執行 `ssh-keygen -lf /etc/ssh/ssh_host_<type>_key.pub`。對於 `<type>`，請使用 Desktop 或 `ssh` 在指紋旁顯示的金鑰類型，並以小寫表示：`ED25519` 或 `ssh-ed25519` 請使用 `ed25519`。

然後將機器本身的指紋與您所看到的指紋進行比對：

* **兩者相符**：信任該金鑰。在 Desktop 中選取 **Trust and connect** 或 **Trust new key**，或在終端機中回答 `yes`。
* **兩者不同，或您無法檢查**：請勿連線。在 Desktop 中選取 **Cancel**，或在終端機中回答 `no`。如果由其他人管理該機器，請告訴他們您看到的指紋。

如果是疑難排解步驟將您引導至此，無論結果為何，請回到該步驟。

#### 為 SSH 工作階段設定代理伺服器或 CA 憑證

如果 Linux 遠端機器透過代理伺服器連上網際網路或需要 CA 憑證，請在該機器的 `~/.claude/settings.json` 中的 `env` 下加入[代理伺服器和 CA 變數](https://code.claude.com/docs/zh-TW/network-config.md)。即使您已在該機器的 `~/.profile`、`~/.bash_profile`、`~/.zprofile` 或 `~/.zshrc` 中匯出這些變數，也請加入。

在 SSH 工作階段中，即使該機器終端機中的 `claude` 能從這些檔案取得變數，Claude Code 也不會取得。工作階段可能因此停止回應，或顯示 **The connection from … to the API failed**、**Authentication failed** 或 **Claude Code on … couldn’t verify the API connection’s certificate**。重新登入也沒有幫助。

**1. 加入變數**

對於 CA 檔案，請使用 [`NODE_EXTRA_CA_CERTS`](https://code.claude.com/docs/zh-TW/network-config#custom-ca-certificates)，因為 Claude Code 不會信任 `~/.claude/settings.json` 中來自 `SSL_CERT_FILE` 的 CA。此範例設定了代理伺服器和 CA 檔案：

```json ~/.claude/settings.json theme={null}
{
  "env": {
    "HTTPS_PROXY": "http://proxy.example.com:8080",
    "NODE_EXTRA_CA_CERTS": "/etc/ssl/certs/example-ca.pem"
  }
}
```

**2. 再次傳送您的訊息**

請再次傳送您的訊息，因為您在該檔案中新增或變更的變數會在幾秒內生效。如果仍然失敗，請啟動新的工作階段。

##### 找出在遠端機器其他位置設定的代理伺服器或 CA 變數

請檢查 Linux 遠端機器是否在其他位置設定了代理伺服器或 CA 變數，因為工作階段會使用該值，並[忽略任何設定檔中的值](https://code.claude.com/docs/zh-TW/settings-reference.md#how-env-values-interact-with-your-shell)：

**1. 列出遠端機器設定的變數**

在您電腦上的終端機中執行 `ssh devbox env`，並將主機換成您自己的。

**2. 在設定變數的位置變更該變數**

如果清單中有該變數，請在設定它的檔案中變更，例如遠端機器上的 `~/.zshenv`、`/etc/environment` 或 `~/.bashrc`。

**3. 讓工作階段取得新值**

重新啟動遠端機器，或結束 Desktop 並終止輔助程式的程序，如[移除輔助程式](#files-and-processes-on-the-remote-machine)的前兩個步驟所示。請在沒有任務執行時進行，因為任一種方式都會中斷 Claude 的工作。

#### 使用您的 SSH 設定

當 Desktop 透過您電腦上的 OpenSSH 用戶端連線時，您可以在 macOS、Linux 和 Windows 上使用您的 SSH 設定：

* **macOS 和 Linux**：Desktop 透過在您電腦上執行 OpenSSH 用戶端來連線，因此會使用您的 `~/.ssh/config`。透過 OpenSSH 用戶端連線需要 Claude Desktop v1.37937.0 或更新版本。
* **Windows**：當 Desktop 透過 OpenSSH 用戶端連線時，會使用您的 `%USERPROFILE%\.ssh\config`。如果您使用的是 Claude 帳戶而非第三方供應商，透過 OpenSSH 用戶端連線需要滿足以下所有條件：

  * Claude Desktop v2.2553.0 或更新版本。若要查看您的版本，請參閱[檢查您的版本](#check-your-version)。
  * Microsoft 的 OpenSSH 9.4 或更新版本
  * 使用本頁頂端的下載按鈕安裝 Desktop，因為來自 Microsoft Store 的 Desktop 不會透過 OpenSSH 用戶端連線

  如果您無法滿足這些需求，或使用第三方供應商，請參閱[在 Windows 上不透過 OpenSSH 用戶端連線](#connect-on-windows-without-the-openssh-client)。

使用 OpenSSH 用戶端時，請在 **SSH host** 欄位中輸入設定檔中的 `Host` 名稱。Desktop 接著會使用該 `Host` 項目中的設定，例如 `HostName`、`User`、`IdentityFile`、`CertificateFile`、`ProxyJump` 和 `ProxyCommand`。

新增連線之前，請在您電腦上的終端機中檢查用戶端和項目：

* **macOS 和 Linux 上的用戶端版本**：執行 `ssh -V`。用戶端必須是 OpenSSH 7.6 或更新版本。
* **Windows 上的用戶端版本**：Desktop 會先嘗試您 `PATH` 上的 `ssh`，因此請執行 `ssh -V`。如果輸出顯示 `OpenSSH_for_Windows_` 以及 9.4 或更新版本，則用戶端通過檢查。如果未通過，請檢查 Desktop 接下來會嘗試的兩個資料夾：在 `C:\Windows\System32\OpenSSH` 中執行 `.\ssh.exe -V`，然後在 `C:\Program Files\OpenSSH` 中執行。
* **Windows 上沒有用戶端通過**：在 Windows 中新增 **OpenSSH Client** 選用功能並安裝擱置中的 Windows 更新，或安裝 [Microsoft 的較新版本](https://learn.microsoft.com/en-us/troubleshoot/windows-server/system-management-components/upgrade-in-box-openssh-to-latest-openssh-release)。然後結束並重新開啟 Desktop。若要查看 Desktop 是否找到可用的 OpenSSH 用戶端，請在 [`ssh.log`](#get-desktops-logs-for-an-ssh-problem) 中尋找 `Windows OpenSSH client:` 和版本，或尋找 `no usable Windows OpenSSH client`。
* **項目**：在 Windows 上，請使用通過版本檢查的用戶端。以 `Host` 名稱執行 `ssh`，例如 `ssh devbox`。如果失敗，請先修正項目。

您可以將 **SSH port** 和 **SSH key (optional)** 欄位留空。如果您填寫其中之一，Desktop 會將其與項目一併使用：

* **SSH port**：此處的值會覆寫項目的 `Port`
* **SSH key (optional)**：使用 OpenSSH 用戶端時，除了項目的 `IdentityFile` 和 SSH agent 中的金鑰外，Desktop 還會提供您選取的金鑰檔案。在 Windows 上，請選取 OpenSSH 格式的金鑰，因為 `ssh` 不會讀取 PuTTY `.ppk` 檔案。

##### 在 Windows 上不透過 OpenSSH 用戶端連線

在 Windows 上，如果您的電腦不符合 [OpenSSH 用戶端的需求](#use-your-ssh-configuration)，您會透過 Desktop 的內建 SSH 用戶端連線。使用第三方供應商時，您透過哪個用戶端連線也取決於您的 Desktop 版本與管理員的設定。請參閱 [SSH remote sessions in Claude Desktop on 3P](https://claude.com/docs/third-party/claude-desktop/ssh-remote-sessions)。

使用內建用戶端時，如果您的 `PATH` 有 `ssh` 命令，您仍可以在 **SSH host** 欄位中輸入 SSH 設定中的 `Host` 名稱，但有以下限制：

* **來自項目的設定**：Desktop 會採用 `HostName`、`User`、`Port`、`IdentityFile` 與 `ConnectTimeout`。如果您的 `PATH` 上有 `sh` shell，也會採用 `ProxyCommand`。
* **SSH key (optional)**：將此欄位留空以保留項目的 `IdentityFile`，因為您在此選取的金鑰檔案會取代 `IdentityFile`
* **`CertificateFile` 和 `ProxyJump`**：Desktop 會忽略 `CertificateFile`，且如果項目設定了 `ProxyJump`，連線會失敗。若要使用其中任一設定，請[透過 OpenSSH 用戶端連線](#use-your-ssh-configuration)。

##### 透過跳板主機連線到機器

若要連線到位於跳板主機（也稱為 bastion）後方的機器，請在項目中設定 `ProxyJump` 或 `ProxyCommand`。下列項目會透過 `bastion.example.com` 連線到 `devbox.internal.example.com`：

```text ~/.ssh/config theme={null}
Host devbox
  HostName devbox.internal.example.com
  User alice
  ProxyJump bastion.example.com
```

在 **SSH host** 欄位中輸入 `devbox`。

如果您的管理員[限制了 SSH 主機](#allow-jump-hosts)，跳板主機也必須在清單中。在您電腦的終端機中執行 `ssh -G bastion.example.com`，並請管理員允許其輸出的 `hostname`。

##### 連線到遠端機器上的容器

若要在未公開 SSH 連接埠的容器內執行工作階段，請使用 `ProxyCommand` 連線到它，因為 Desktop 不會執行您所連線項目的 `RemoteCommand`。如果您的項目使用 `RemoteCommand` 進入容器，工作階段會在該項目所登入的機器上執行，而不是在容器中執行。

**1. 加入項目**

將下列項目新增至 `~/.ssh/config` 的結尾，若您有第一個 `Host *` 項目，則直接新增在其上方。請將 Docker 容器 `devbox`、其使用者 `dev` 與機器 `build.example.com` 替換為您自己的值。此項目的命令會為每個連線在容器內啟動一個 SSH 伺服器：

```text ~/.ssh/config theme={null}
Host devbox-container
  User dev
  ProxyCommand ssh build.example.com docker exec -i devbox /usr/sbin/sshd -i
```

**2. 準備容器**

* 安裝 OpenSSH 伺服器，並使用在您重新建置映像或重新建立容器時保持不變的主機金鑰
* 為 `User` 中指定的帳戶提供登入方式，例如 `authorized_keys` 檔案
* 確認容器符合[遠端機器需求](#remote-machine-requirements-for-ssh-sessions)

**3. 檢查允許清單**

如果您的管理員[限制 SSH 主機](#restrict-which-ssh-hosts-users-can-connect-to)，請在您電腦上的終端機中執行 `ssh -G devbox-container`。請管理員在 `sshHostAllowlist` 中允許它輸出的 `hostname`，此處為 `devbox-container`。當管理員允許該名稱時，就等於允許您項目的 `ProxyCommand` 所連線的任何目標。

**4. 測試項目，然後連線**

在您電腦上的終端機中執行 `ssh devbox-container`。修正它回報的問題，並重複執行，直到它在不詢問您任何內容的情況下於容器中開啟 shell：

* **如果 `ssh` 要求輸入密碼、複雜密碼或驗證碼**：改用無需提示即可運作的登入方式，例如您 SSH agent 持有的金鑰
* **如果 `ssh` 回報 `Cannot execute command-line and remote command.` 或 `Bad packet length`**：從您 `build.example.com` 的項目中移除 `RemoteCommand` 和 `RequestTTY`。之後，在您電腦上的終端機中執行 `ssh build.example.com` 會在該機器上開啟 shell，而不是在容器中。
* **如果 `ssh` 回報 `Connection closed by UNKNOWN port 65535`**：在同一個終端機中執行 `ssh build.example.com docker exec devbox /usr/sbin/sshd -t`。
  * 如果輸出 `Missing privilege separation directory: /run/sshd`，請在容器中建立該資料夾。
  * 如果輸出 `no hostkeys available` 且容器有主機金鑰，請在此命令和項目中的 `exec` 之後加入 `-u root`。

然後在 **SSH host** 欄位中輸入 `devbox-container`。

##### 在 `ProxyCommand` 中使用來自您 shell 的變數

在 macOS 和 Linux 上，若要在 `ProxyCommand` 或 `Match exec` 命令中使用您自己的環境變數，請在 shell 啟動檔案（例如 `~/.zshrc`）中 export。然後結束並重新開啟 Desktop。Desktop 啟動時會讀取您的登入 shell 所 export 的內容，並保留這些值直到您結束 Desktop。

這需要 Claude Desktop v2.37337.0 或更新版本，以及接受 `-0` 的 `env` 命令，您可以在電腦上的終端機中執行 `env -0` 來檢查。

> [!NOTE]
>
> 如果您的 shell 設定了臨時 AWS 憑證，請[為 AWS CLI 提供設定檔](#use-aws-credentials-in-a-proxycommand)，而不是匯出 `AWS_*` 變數。

##### 在 macOS 和 Linux 上的 `ProxyCommand` 中使用 AWS 憑證

如果您在 shell 啟動檔案中設定了臨時 AWS 憑證，執行 AWS CLI 的 `ProxyCommand` 可能在終端機中能夠連線，但在 Desktop 中失敗。當您的 shell 匯出 `AWS_SESSION_TOKEN`、`AWS_SECURITY_TOKEN` 或 `AWS_CREDENTIAL_EXPIRATION` 時，Desktop 中的 `ssh` 和您的 `ProxyCommand` 不會取得 shell 的 AWS 憑證、`AWS_REGION` 或 `AWS_PROFILE`。

如果 AWS CLI 沒有其他區域或憑證來源，它會失敗並顯示 `You must specify a region` 或 `Unable to locate credentials`。若要從 Desktop 連線，請為 AWS CLI 提供一個它從 `~/.aws/config` 讀取的設定檔：

**1. 新增具有區域和憑證來源的設定檔**

此範例新增名為 `corp` 的設定檔，該設定檔從輔助程式取得憑證：

```ini ~/.aws/config theme={null}
[profile corp]
region = us-east-1
credential_process = /full/path/to/your-credential-helper
```

* **`region`**：提供您所連線機器的 AWS 區域
* **`credential_process`**：提供以 [AWS 文件所述的 JSON 格式](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sourcing-external.html)輸出憑證之程式的完整路徑。請選擇不需要您輸入任何內容的程式，因為 AWS CLI 會在每次連線時執行它，包括您不在時的重新連線。
* **IAM Identity Center**：加入設定檔的 [IAM Identity Center 設定](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html)來取代 `credential_process`。請在連線之前於終端機中執行 `aws sso login --profile corp`，並在該登入失效時再次執行。

**2. 在 ProxyCommand 中指定設定檔**

此範例將 `--profile` 加入 [AWS 文件中針對 Session Manager 的命令](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-getting-started-enable-ssh-connections.html)：

```text ~/.ssh/config theme={null}
Host i-*
  ProxyCommand sh -c "aws ssm start-session --profile corp --target %h --document-name AWS-StartSSHSession --parameters 'portNumber=%p'"
```

**3. 再次連線**

在終端機中以該主機執行 `ssh`，確認項目在該處仍可連線，然後從 Desktop 連線。

##### 提高 SSH 連線逾時

如果您的工作階段在透過跳板主機或 `ProxyCommand` 連線時逾時，請在 `~/.ssh/config` 中遠端機器的項目裡提高 `ConnectTimeout`。請使用超過 90 秒的值。再加上跳板主機或 `ProxyCommand` 等待您的任何時間，例如在登入提示時或等待手機推播時：

```text ~/.ssh/config theme={null}
Host devbox
  HostName devbox.internal.example.com
  User alice
  ProxyJump bastion.example.com
  ConnectTimeout 120
```

`ssh` 會使用它為主機找到的第一個值，因此請將項目保持在任何設定 `ConnectTimeout` 的 `Host *` 項目之上。若要確認，請在您電腦上的終端機中執行 `ssh -G devbox`。其輸出會包含 `connecttimeout 120`。變更值之後，請結束並重新開啟 Desktop。

如果您的 SSH 設定未為該主機設定 `ConnectTimeout`，Desktop 會給 `ssh` 30 秒的連線時間。透過跳板主機或 `ProxyCommand` 時，該時間包含路由連線所需的時間。

| `ConnectTimeout` | 連線 | 您擁有的時間 |
| - | - | - |
| 未設定 | 您在 macOS 或 Linux 上使用 Claude Desktop v4.4212.0 或更新版本，透過跳板主機或 `ProxyCommand` 啟動工作階段 | 30 秒，然後以 90 秒進行第二次嘗試。如果 Desktop 在第一次嘗試期間向您顯示了提示，則不會有第二次嘗試。在 Desktop 為 `ProxyJump` 主機顯示的登入提示上所花的時間不計入。路由上的其他等待則會計入。 |
| 未設定 | Windows 上的 Desktop 或較早版本、設定了 `MaxSessions 1` 的遠端機器，或 Desktop 自行啟動的重新連線 | 30 秒。路由上的每次等待都會計入。 |
| 已設定 | 每次連線與重新連線 | 您設定的值。路由上的每次等待都會計入。 |

如果遠端機器本身在等待您手機上的核准，無論您設定的 `ConnectTimeout` 為何，請在 45 秒內核准。您無法提高此限制，因為 Desktop 會自行設定 `ServerAliveInterval` 與 `ServerAliveCountMax`，而 `ssh` 接著會關閉遠端機器在這段時間內未傳送任何內容的登入。

##### 修正只有 Desktop 會套用的 `Match host` 區塊

如果 Desktop 使用了終端機中 `ssh devbox` 不會使用的設定，請在項目的 `HostName` 行上方尋找 `Match host` 區塊。在終端機中，`ssh` 會在 `HostName` 行之前讀取該處的區塊，因此它會將區塊與 `devbox` 比較。Desktop 會在命令列上將 `HostName` 值提供給 `ssh`，因此 `ssh` 會將區塊與該值比較。

若要檢查，請在您電腦上的終端機中執行 `ssh -G`，並如同 Desktop 一樣在命令列上加入項目的 `HostName` 和 `User` 值：

```bash theme={null}
ssh -G -o HostName=devbox.internal.example.com -l alice devbox
```

將輸出與 `ssh -G devbox` 的輸出比較。如果區塊的設定（例如 `proxycommand`）只出現在第一個輸出中，該區塊就只會在 Desktop 中生效。若要讓 Desktop 也略過它，請在其 `Match` 行中加入 `!originalhost devbox`：

```text ~/.ssh/config theme={null}
Match host *.internal.example.com !originalhost devbox
```

若要確認，請再次執行第一個命令。區塊的設定不再出現在其輸出中。

##### Desktop 會關閉的轉送設定

在與遠端機器的連線上，Desktop 會關閉 `ForwardAgent`、`ForwardX11`、`LocalForward`、`RemoteForward`、`DynamicForward` 和 `Tunnel`，即使您的 SSH 設定開啟了它們。在[終端機](#run-commands-in-the-terminal)或 `!` 命令中，您的轉送設定可能[只有有時會套用](#limits-while-desktop-is-disconnected)，因為 Desktop 可能會在該處啟動遵循這些設定的另一個 `ssh`。

* **若要連線到遠端機器上的連接埠**：[自行轉送](#reach-a-port-on-the-remote-machine)
* **若要從遠端機器使用您自己的金鑰**：在遠端機器本身設定憑證，例如用於 `git push`

若要防止 Desktop 轉送您的 SSH agent 或連接埠，請在您電腦上的終端機中執行 `ssh -G devbox`。然後以 Desktop 可能的執行方式再執行一次，加上它輸出的 `hostname` 和 `user` 值，如 `ssh -G -o HostName=devbox.internal.example.com -l alice devbox`。第二個輸出可能會顯示第一個輸出略過的 `Match` 區塊中的設定。

在兩個輸出中尋找值不是 `no` 的 `forwardagent` 行，以及以 `localforward`、`remoteforward` 或 `dynamicforward` 開頭的行。如果找到，請從您的 SSH 設定中移除該設定。對您的 `ProxyCommand` 以 `ssh` 連線的主機也做同樣的處理。

#### 連線到遠端機器上的連接埠

若要開啟在遠端機器上執行的伺服器（例如連接埠 3000 上的開發伺服器），請自行轉送該連接埠。在您電腦上的終端機中，以 `-L` 和您連線的主機（例如 `devbox`）執行 `ssh`：

```bash theme={null}
ssh -N -L 3000:localhost:3000 devbox
```

如果您在連線上填寫了 **SSH port** 或 **SSH key (optional)**，請以相同的值加入 `-p` 或 `-i`。讓該命令保持執行，並在您電腦上的瀏覽器中開啟 `http://localhost:3000`，即可連線到遠端機器的連接埠 3000。如果 `ssh` 輸出 `open failed: administratively prohibited`，請要求該機器的管理員允許 TCP 轉送，這由 SSH 伺服器 `sshd_config` 中的 `AllowTcpForwarding` 控制。

#### Windows 遠端機器

Windows 遠端機器需要 Claude Desktop v2.31226.0 或更新版本。

請使用 Microsoft 的 OpenSSH Server。機器可以是 x64 或 ARM64。SSH 伺服器啟動的 shell 可以是 `cmd.exe`、Windows PowerShell 5.1 或 Git Bash。

Windows 遠端機器的測試比 Linux 遠端機器少。在依賴它之前，請先在該處試用您自己的工作。

在 Windows 遠端機器上，預期會有下列限制（但不限於此）：

* **終端機**：在資料夾為 Windows 路徑（例如 `C:/projects/app`）的工作階段中，[終端機](#run-commands-in-the-terminal)不會開啟
* **沙箱**：Claude Code 在該處以原生 Windows 執行，並在沙箱外執行命令。請參閱[沙箱的執行位置](https://code.claude.com/docs/zh-TW/sandboxing.md)。
* **外掛**：Desktop 不會複製包含 Windows 無法儲存之檔案或資料夾名稱（例如含有 `:` 的名稱）的外掛。工作階段會列出 Desktop 略過的外掛。
* **MCP 伺服器**：在某些 Windows 遠端機器上，Claude 對 `claude_desktop_config.json` 中 MCP 伺服器的呼叫會經過 Desktop，因此 Claude [在 Desktop 中斷連線時](#limits-while-desktop-is-disconnected)無法呼叫它們的工具。在 Claude Desktop v2.37337.0 之前，這適用於所有 Windows 遠端機器。
* **Worktree**：worktree 會放在 `<project-root>/.claude/worktrees/`。如果您[選擇其他資料夾](#choose-where-ssh-session-worktrees-go)，Desktop 會忽略它。
* **先前的訊息**：如果 SSH 伺服器的 shell 是 `cmd.exe` 或 Windows PowerShell，您可能必須先連線才能看到工作階段先前的訊息
* **分支**：如果 SSH 伺服器的 shell 是 `cmd.exe` 或 Windows PowerShell，您只能在工作階段的第一則訊息處分支該工作階段
* **中斷連線時執行**：只有在 SSH 伺服器允許程式在啟動它的連線結束後繼續存在時，任務才會[在 Desktop 中斷連線時繼續執行](#keep-a-task-running-while-desktop-is-disconnected)。若要確認，請[測試遠端機器](#prepare-a-long-task)。
* **殘留的程序**：工作階段結束後，請檢查機器上是否有 Claude Code 啟動的程式，因為它們可能會繼續執行。Desktop 安裝的[背景輔助程式](#keep-a-task-running-while-desktop-is-disconnected)在該處不會自行停止。

#### 在 Desktop 中斷連線時讓任務繼續執行

如果您的電腦進入睡眠、失去網路或您結束 Desktop，任務會繼續進行，直到完成、需要您處理，或達到其中一項[限制](#limits-while-desktop-is-disconnected)。闔上筆電蓋子視為睡眠。Desktop 或電腦重新啟動（包括因更新而重新啟動）視為結束。

Claude Code 在遠端機器上以程序執行，並在 Desktop 安裝於該處的背景輔助程式之下運作，因此不需要您的 SSH 連線即可繼續執行。本節所述的行為需要 Claude Desktop v2.31226.0 或更新版本。

> [!WARNING]
>
> 如果您使用 Claude 帳戶登入 Desktop，請勿指望任務能整夜執行。Desktop 只有在執行中且已連線時才會為任務更新該登入，因此在您中斷連線後，任務的登入可能會過期，任務隨之停止。您中斷連線時剩餘的時間不一，可能只有幾分鐘。
>
> 目前完成的工作會保留在遠端機器上，您回來時可以傳送訊息繼續。
>
> 如果任務必須整夜執行：
>
> * [讓您的電腦保持喚醒](https://code.claude.com/docs/zh-TW/desktop-scheduled-tasks.md#how-scheduled-tasks-run)並連上網路，筆電蓋子保持開啟且 Desktop 保持執行
> * 對遠端機器及途中的任何跳板主機，使用無需提示即可運作的登入方式，例如您 SSH agent 持有的金鑰。這樣 Desktop 就能在連線中斷後自行重新連線。
>
> 對於必須在電腦睡眠或關機時執行的任務，請改為啟動[雲端工作階段](#run-long-running-tasks-in-the-cloud)。

* **睡眠或網路中斷之後**：如果程序[仍在執行](#limits-while-desktop-is-disconnected)且 Desktop 能在無提示的情況下登入，您就能取回執行中的任務。如果無法，請[傳送訊息](#reconnect-after-sleep-or-a-network-loss)。
* **結束後**：任務會繼續執行，但除非 Desktop 能重新加入其程序，否則在工作階段再次開啟時您會失去該任務。結束前，請查看 [Desktop 何時能重新加入](#reopen-a-session-after-you-quit-desktop)。如果您失去了任務，請傳送訊息以繼續。

當您回來且任務尚未完成時，請檢查是否有 Desktop 無法重新連線的訊息、身分驗證錯誤或等待中的請求：

* **Desktop 無法重新連線**：工作階段會說明原因，通知也可能會說明。Desktop 可能[需要您登入](#reconnect-after-sleep-or-a-network-loss)。
* **身分驗證錯誤**：[登入 token 或憑證](#limits-while-desktop-is-disconnected)可能已過期。使用 Claude 帳戶時，請傳送訊息以繼續。使用第三方供應商時，請參閱 [SSH remote sessions in Claude Desktop on 3P](https://claude.com/docs/third-party/claude-desktop/ssh-remote-sessions)。
* **等待中的請求**：[回應它](#handle-requests-that-arrive-while-you-are-away)
* **以上皆非**：傳送訊息以繼續

##### 準備長時間任務

* **先更新**：在開始長時間任務之前更新 Desktop。在 macOS 和 Windows 上，Desktop 可能會自行重新啟動以安裝已下載的更新。當 Claude 正在處理 SSH 任務時，該重新啟動會等待。根據預設，一旦更新已等待 72 小時，如果 Desktop 能[在之後重新加入任務](#reopen-a-session-after-you-quit-desktop)，重新啟動就可能在任務期間進行。
* **結束前確認**：結束或重新啟動後，您不一定能取回執行中的任務，例如在某些 Desktop 更新之後。相關情況請參閱[結束 Desktop 後重新開啟工作階段](#reopen-a-session-after-you-quit-desktop)。
* **使用較舊版本時，讓 Desktop 保持開啟**：在 Windows 上使用 v3.1623.0 之前的 Claude Desktop 時，Desktop 結束或重新啟動後您無法取回執行中的任務。在 macOS 或 Linux 上搭配第三方供應商使用 v2.42304.0 之前的版本時也是如此。在這兩種情況下，請在任務期間讓 Desktop 保持開啟。若要查看您的版本，請參閱[檢查您的版本](#check-your-version)。
* **減少請求**：選擇能[讓任務較少等待您](#handle-requests-that-arrive-while-you-are-away)的權限模式、規則或 hook
* **檢查跳板主機**：如果您的跳板主機要求登入（例如推送到手機），請改用無需提示即可運作的登入方式。否則 Desktop 每次嘗試重新連線時都可能再傳送一次推送。
* **測試遠端機器**：啟動一個短任務，在任務仍在執行時結束 Desktop，並在任務應已完成很久之後再次開啟工作階段。如果任務尚未完成且工作階段未顯示身分驗證錯誤，請檢查遠端機器上[可能終止任務的因素](#limits-while-desktop-is-disconnected)。
* **不要在 Desktop 的終端機中執行命令**：如果遠端機器會[登出閒置的終端機](#limits-while-desktop-is-disconnected)，請從 Desktop 以外的 SSH 登入執行您自己的命令

##### Desktop 中斷連線時的限制

您讓其保持執行的任務，可能會在其登入過期時、遠端機器終止它時，或輔助程式停止或被取代時結束：

* **登入 token 或憑證**：使用 Claude 帳戶時，token 過期後任務會因身分驗證錯誤而停止。使用第三方供應商時，會過期的憑證（例如來自單一登入或憑證輔助程式的憑證）也是如此。請參閱 [SSH remote sessions in Claude Desktop on 3P](https://claude.com/docs/third-party/claude-desktop/ssh-remote-sessions)。使用 Claude 帳戶時，請[讓 Desktop 保持執行且已連線](#keep-a-task-running-while-desktop-is-disconnected)，以便它更新登入。
* **遠端機器**：如果遠端機器重新啟動，或在您的 SSH 連線關閉時終止您的程序，執行中的任務就會結束。Desktop 中斷連線期間，沒有任何機制會重新啟動它。systemd-logind 的 `KillUserProcesses` 為 `yes` 且適用於您使用者的 Linux 機器，會以這種方式終止您的程序。若要讓任務在該處持續執行，請要求管理員將您的使用者排除，例如使用 `KillExcludeUsers`。
* **閒置的終端機**：某些 Linux 遠端機器會登出在設定時間內無人輸入的終端機（systemd-logind 的 `StopIdleSessionSec`）。Desktop 在 macOS 或 Linux 上時，工作階段的[終端機](#run-commands-in-the-terminal)和 `!` 命令預設會共用 Desktop 的 SSH 連線。該登出會在 Desktop 連線時結束連線，執行中的任務也可能隨之結束。關閉終端機窗格無法避免此情況，因此請[不要在該終端機中執行命令](#prepare-a-long-task)。
* **Desktop 更新**：如果更新帶來新的輔助程式，Desktop 會在之後的連線中取代遠端機器上的輔助程式，這可能會終止仍在執行的任務
* **長時間未連線**：在 Linux 或 macOS 遠端機器上，如果 Desktop 30 天內未連線，輔助程式會停止，並終止在其下執行的每個 Claude Code 程序。請在此之前連線。

Desktop 中斷連線時，檔案編輯和某些工具可能會失敗。如果任務需要它們，請讓 Desktop 保持連線：

* **Worktree**：在使用 [worktree](#run-a-session-in-its-own-worktree) 的工作階段中，Desktop 會在 Claude 進行每次檔案編輯之前進行檢查。在 Desktop 中斷連線期間，每次編輯會等待約 30 秒然後失敗。Shell 命令仍會執行。在 Linux 或 macOS 遠端機器上，[編輯可以繼續運作](#worktree-edits-while-disconnected)。如果您不確定，請在不使用 worktree 的情況下啟動工作階段。
* **資料夾限制**：如果您的組織限制工作階段可使用的資料夾，無論是否使用 worktree，Desktop 都會檢查每次檔案讀取、搜尋和編輯。Desktop 中斷連線時，每項操作會等待最多 10 分鐘後失敗。
* **連接器**：[連接器](#connect-external-tools)和 Desktop 提供的其他工具會透過 Desktop 執行，因此在 Desktop 中斷連線時，每次呼叫會在約 30 秒後失敗
* **工作流程**：Desktop 會在每個新的[工作流程](https://code.claude.com/docs/zh-TW/workflows.md)啟動前進行檢查，因此在 Desktop 中斷連線時，新的工作流程會等待最多 10 分鐘後失敗
* **MCP 伺服器**：Claude Code 在遠端機器上啟動的 MCP 伺服器不會透過 Desktop 執行，因此 Claude 仍可呼叫它們的工具。只有在 Desktop 未使用其[內建 SSH 用戶端](#worktree-edits-while-disconnected)時，來自 `claude_desktop_config.json` 的伺服器才屬於此類。否則，以及在[某些 Windows 遠端機器](#windows-remote-machines)上，Claude 在 Desktop 中斷連線時無法呼叫它們的工具。

> [accordion] worktree 中的編輯何時會繼續運作
>
> 在 Linux 或 macOS 遠端機器上，該檢查不會經過 Desktop，因此在 Desktop 中斷連線時，worktree 內的編輯會繼續運作。在 Claude Desktop v2.37337.0 之前，這僅適用於 Linux 遠端機器。
>
> 在某些情況下編輯仍會失敗，包括下列情況：
>
> * **內建 SSH 用戶端**：Desktop 使用內建 SSH 用戶端，例如在從 Microsoft Store 安裝的版本中，或在沒有 Microsoft OpenSSH 9.4 或更新版本的 Windows 電腦上
> * **儲存庫位置**：儲存庫是您的家目錄、家目錄上層的資料夾，或 `~/.claude`
> * **macOS 路徑**：在 macOS 遠端機器上，儲存庫位於 `/Volumes` 之下，或儲存庫或 worktree 路徑中的資料夾名稱含有 `~` 或非 ASCII 字元
> * **資料夾限制**：您的組織限制工作階段可使用的資料夾
> * **企業啟動器**：在 Claude Desktop v2.37337.0 之前，您使用 Claude 帳戶登入，且您的組織透過[企業啟動器](https://code.claude.com/docs/zh-TW/corporate-launcher.md)在遠端機器上啟動 Claude Code
>
> 沒有 worktree 的工作階段不會有此類檢查，除非您的組織限制工作階段可使用的資料夾。

##### 處理您不在時收到的請求

如果 Claude 在 Desktop 中斷連線時需要您的核准或向您提問，Claude 會在遠端機器上等待。此等待本身沒有時間限制。當 Desktop 重新加入該程序時，會向您顯示該請求。如果 Desktop 改為啟動新的程序，您就會失去該請求。

如果等待您的請求在您回來時已消失，其中一個原因是 Desktop 自行重新啟動，例如為了安裝更新。只有在 Desktop 能重新加入程序時，您才能在重新啟動後保留請求，因此在讓任務持續執行前，請查看 [Desktop 何時能重新加入](#reopen-a-session-after-you-quit-desktop)。

如果您失去請求，請傳送訊息以繼續。

若要減少任務停下來等待您的頻率，並在您不在時收到任務的消息，請在離開前設定下列任一項：

* **自動模式**：如果[您可使用自動模式](#auto-mode-availability)，請選擇[自動模式](#choose-a-permission-mode)。在多次遭到封鎖後，系統會[再次詢問您](https://code.claude.com/docs/zh-TW/permission-modes.md#when-auto-mode-falls-back)。
* **允許規則**：在遠端機器上的使用者設定檔 `~/.claude/settings.json` 中，為任務所需的命令加入[允許規則](https://code.claude.com/docs/zh-TW/permissions.md#manage-permissions)。如果您的組織[只接受來自受管設定的權限規則](https://code.claude.com/docs/zh-TW/settings-reference.md#allowmanagedpermissionrulesonly)，請要求管理員將規則加入會傳送到遠端機器的[受管設定](#managed-settings)。如需專案 `.claude/settings.json` 中的允許規則，請參閱[專案允許規則與工作區信任](https://code.claude.com/docs/zh-TW/permissions.md#project-allow-rules-and-workspace-trust)。
* **會代為回應的 hook**：在遠端機器上的 `~/.claude/settings.json` 中設定 [`PermissionRequest` hook](https://code.claude.com/docs/zh-TW/hooks#permissionrequest)，代替您允許或拒絕請求
* **會提醒您的 hook**：在同一個檔案中設定帶有 `permission_prompt` matcher 的 [`Notification` hook](https://code.claude.com/docs/zh-TW/hooks#notification)，在有請求等待時傳送訊息給自己
* **在 Claude 完成時通知您的 hook**：在同一個檔案中設定 [`Stop` hook](https://code.claude.com/docs/zh-TW/hooks#stop)，在 Claude 完成回應時傳送訊息給自己。當 API 錯誤結束該回合時，它不會執行。對於該情況，請設定 [`StopFailure` hook](https://code.claude.com/docs/zh-TW/hooks#stopfailure)。

如果您的組織[只執行受管 hook](https://code.claude.com/docs/zh-TW/settings-reference.md#allowmanagedhooksonly)，請要求管理員將 hook 加入會傳送到遠端機器的[受管設定](#managed-settings)。

Claude Code 在任何權限模式下（包括 Bypass permissions）都不會自動核准[少數動作](https://code.claude.com/docs/zh-TW/permission-modes.md#actions-no-mode-auto-approves)。視權限模式而定，Claude Code 會拒絕此類動作或詢問您，任務接著會等待您的回答。

##### 睡眠或網路中斷後重新連線

如果您回來時 Desktop 尚未重新連線，請在工作階段中傳送訊息。只有在能夠無提示登入的情況下（例如使用您 SSH agent 持有的金鑰），Desktop 才會自行重新連線。

* **記住的密碼**：您讓 Desktop 記住的密碼同樣能在無提示的情況下運作，但若長時間離開，建議使用您 SSH agent 持有的金鑰。如果使用該密碼的登入中斷或停滯，Desktop 可能會停止重新連線並等待您。
* **其他任何提示**：如果遠端機器提示輸入其他內容（例如一次性驗證碼），您可能會在電腦上收到通知。按一下通知，或在工作階段中傳送訊息，Desktop 就會顯示該提示。

> [accordion] 如果跳板主機要求登入、中斷時間很長、訊息未傳送、輸出遺失，或程序已消失
>
> * **跳板主機，您不在時推送停止**：當沒有人回應跳板主機的登入（例如推送到手機）時，macOS 或 Linux 上的 Desktop 可能會發生此情況。Desktop 接著會在沒有人使用您電腦時停止重新連線。當您解鎖或使用電腦時，您可能會再收到一次推送，因為 Desktop 可能會再試一次。在三次嘗試未獲回應後，它會等待直到您重試或傳送訊息。
> * **跳板主機，推送持續傳來**：在 Desktop 無法判斷沒有人回應的情況下（例如 Windows 上的 Desktop），只要有可重新加入的程序，無論該程序是否仍在執行，它都會持續嘗試。您每次嘗試都可能再收到一次推送。若要結束嘗試，請結束 Desktop，這[可能會讓您失去執行中的任務](#reopen-a-session-after-you-quit-desktop)。
> * **長時間中斷**：Desktop 會減緩至大約每五分鐘嘗試一次。若要更快重新連線，請在工作階段中重試或傳送訊息。Desktop 會在連線後嘗試傳遞該訊息。
> * **訊息未傳送**：您的訊息下方出現 `Your organization's settings haven't loaded, so your message to <host> wasn't sent. Retry to send it.` 這一列，表示 Desktop 已重新連線，但因為您組織的設定尚未載入而暫緩傳送您的訊息。選取 **Retry** 以立即傳送訊息。如果您不做任何事，Desktop 會在設定載入後再次嘗試。
> * **輸出遺失**：Desktop 中斷連線時，輔助程式會將每個工作階段最近的 Claude Code 輸出保留在 16 MiB 的緩衝區中，並捨棄較舊的輸出。Desktop 重新連線後，工作階段可能會顯示 `Loading recent output from <host>…`。如果 Desktop 無法載入所有輸出，您會看到 `Some output produced while you were disconnected may be missing here.` 這一列。此列並不代表任務已停止。
> * **程序已消失**：程序在 Desktop 中斷連線期間結束，例如遠端電腦重新啟動時。Desktop 接著可能會從對話已儲存的歷史記錄啟動新程序，並指示 Claude 繼續任務。如果任務仍處於停止狀態，請傳送訊息。若使用第三方供應商，請更新至 Claude Desktop v2.42304.0 或更新版本，因為較早的版本永遠不會自行繼續任務。

##### 結束 Desktop 後重新開啟工作階段

結束 Desktop 後，任務會在遠端電腦上繼續執行，但除非 Desktop 能重新加入其程序，否則工作階段再次開啟時任務會停止。Desktop 關閉期間，任務會執行直到完成、需要您處理，或達到某個[限制](#limits-while-desktop-is-disconnected)。

* **Windows 上的 Desktop，任務在 v3.1623.0 之前的版本中啟動**：即使 Desktop 之後已更新，您也無法取回該任務。請只在您預期任務已完成時才再次啟動 Desktop，因為工作階段可能會在 Desktop 啟動時開啟，而工作階段開啟時任務就會停止。如果您不知道任務是在哪個版本中啟動的，也請等到您預期任務已完成。
* **macOS 或 Linux 上的第三方供應商，任務在 v2.42304.0 之前的版本中啟動**：您無法取回該任務。請只在您預期任務已完成時才再次啟動 Desktop。
* **任何其他任務**：啟動 Desktop 並開啟工作階段，如果 Desktop 重新加入，任務就會繼續進行。它不一定能重新加入，例如在某些 Desktop 更新之後，因此請[在長時間任務之前更新](#prepare-a-long-task)。

任務停止時，工作階段可能會在 Desktop 啟動新程序時顯示 `Restarting Claude Code on <host>…`。您也會失去任何正在等待您的核准或問題。如果 Claude 沒有自行繼續，請傳送訊息，Claude 就會從對話的已儲存歷程記錄繼續。

如需第三方部署的相關資訊，請參閱 [SSH remote sessions in Claude Desktop on 3P](https://claude.com/docs/third-party/claude-desktop/ssh-remote-sessions)。

> [!WARNING]
>
> 當對話的 Claude Code 程序仍在執行時，請勿在遠端機器上為該對話執行 [`claude --resume`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags)。Claude Code 不會阻止您，兩個程序接著會寫入同一個對話。如果您不確定，請加入 `--fork-session`，它會在對話的副本中繼續，但兩個程序仍會處理相同的檔案。

#### 選擇 SSH 工作階段 worktree 的位置

除非您的組織限制工作階段可使用的資料夾，否則新的 SSH 工作階段會在下列位置中第一個已設定的位置建立其 [worktree](#run-a-session-in-its-own-worktree)：

1. SSH 連線上的 **Worktree folder**
2. 遠端機器上 `~/.claude/settings.json` 中的 [`worktree.location`](https://code.claude.com/docs/zh-TW/settings-reference#worktree-location)
3. `<project-root>/.claude/worktrees/`，即預設值

每個專案會在您設定的資料夾中取得自己的子資料夾，因此使用 `~/worktrees` 時，worktree 的路徑為 `~/worktrees/<project>-<id>/<worktree-name>`。如果您設定的資料夾位於專案內，Desktop 會對該專案忽略它並使用預設值。在 [Windows 遠端機器](#windows-remote-machines)上，Desktop 一律使用預設值。

##### 在現有連線上設定 worktree 資料夾

在您之前新增的連線或您組織管理的連線設定中，設定 **Worktree folder**。此欄位需要 Claude Desktop v1.44121.0 或更新版本。如果您的組織限制工作階段可使用的資料夾，Desktop 會隱藏此欄位，並將 worktree 保留在專案內。

**1. 找到連線**

開啟[環境選擇器](#start-a-session)，並在 **SSH** 下找到該連線。

**2. 開啟連線的設定**

將滑鼠游標停留在該連線上，然後點選齒輪圖示。如果開啟的對話方塊在 **Host** 旁顯示 **Edit connection…**，請選取 **Edit connection…**。

**3. 設定資料夾**

在 **Worktree folder** 中，輸入遠端機器上的資料夾，例如 `~/worktrees`，然後選取 **Save changes**。

#### 遠端機器上的檔案和程序

Desktop 會在每位連線到 Linux 或 macOS 遠端機器的使用者家目錄中，於 `~/.claude/remote/` 下安裝輔助程式和 Claude Code。輔助程式不會監聽任何網路連接埠，但 Claude Code 及其啟動的程式（例如 MCP 伺服器和開發伺服器）可能會。

| 資料夾 | 內容 |
| - | - |
| `~/.claude/remote/srv/` | 輔助程式，每個版本一個資料夾 |
| `~/.claude/remote/ccd-cli/` | Claude Code，每個版本一個檔案 |
| `~/.claude/remote/run/` | 輔助程式的執行階段檔案，例如其 socket 和日誌，每台連線的電腦一個資料夾 |
| `~/.claude/remote/plugins/` | Desktop 從使用者電腦複製的外掛 |
| [`~/.claude/uploads/`](https://code.claude.com/docs/zh-TW/claude-directory#clear-local-data) | 使用者附加到訊息的檔案，每個工作階段一個資料夾 |

若要列出某位使用者的程序，請以該使用者身分在遠端機器上執行 `pgrep -fl "$HOME/.claude/remote/"`，或以該使用者的家目錄取代 `$HOME`：

* **輔助程式**：每台連線的電腦會有一個或多個 `server` 程序
* **Claude Code**：輔助程式為使用者工作階段啟動的程序，每個程序都來自以其版本命名的檔案，例如 `2.1.295-…`

Desktop 透過使用者的 SSH 連線，經由輔助程式在 `~/.claude/remote/run/` 下資料夾中的 Unix socket `rpc.sock` 連線到輔助程式。除了 root 之外，機器上的其他使用者無法連線到該 socket，因為它的模式為 600，且其資料夾的模式為 700。

如需輔助程式何時會自行停止，請參閱 [Desktop 中斷連線時的限制](#limits-while-desktop-is-disconnected)。

若要為某位使用者移除輔助程式和 Claude Code：

**1. 結束 Desktop**

在該使用者連線來源的每台電腦上結束 Desktop。Desktop 會在下次連線時再次安裝這兩個程式，而且它可能會自行重新連線。

**2. 終止程序**

以該使用者身分登入遠端機器，對 [`pgrep`](#files-and-processes-on-the-remote-machine) 列出的每個 Claude Code 程序 ID 執行 `kill`。當這些程序從清單中消失後，再對每個 `server` 程序的 ID 執行 `kill`。如果您先終止 `server` 程序，Claude Code 正在執行的命令可能會繼續執行。

然後列出該使用者剩餘的程序，例如使用 `ps -u "$(id -un)" -f`，並終止您認得是由 Claude Code 啟動的任何程序。它留在背景的程式可能在其結束後繼續執行，且不會出現在 `pgrep` 清單中。

**3. 刪除資料夾**

刪除 `~/.claude/remote/`。若要移除 Claude Code 本身在 `~/.claude/` 和 `~/.claude.json` 中的檔案，請參閱[移除設定檔](https://code.claude.com/docs/zh-TW/setup.md#remove-configuration-files)。

##### 終止單一工作階段的程序

若要終止單一工作階段的 Claude Code 程序，請在 Desktop 連線至遠端機器時，於 Desktop 中[封存該工作階段](#archive-a-session)。該程序在其任務完成後以及您結束 Desktop 後仍會繼續執行。

在封存 worktree 中有未提交變更的工作階段之前，請參閱[在封存工作階段時保留未提交的變更](#keep-uncommitted-changes-when-a-session-is-archived)。

##### 查看程序以哪位使用者身分執行

輔助程式和 Claude Code 會以 Desktop 透過 SSH 登入的使用者身分執行。安裝和啟動它們不需要 `sudo`。若要檢查使用者，請在遠端機器上以 [`pgrep`](#files-and-processes-on-the-remote-machine) 列出的程序 ID 執行 `ps -o user= -p`。

Claude Code 啟動的程式（例如 shell 命令和 MCP 伺服器）也會以該使用者身分啟動。請審查該使用者在遠端機器上的權限（包括其 `sudo` 規則），就像審查在該處執行命令的人員一樣。

##### 查看誰連線到遠端機器

若要了解誰連線到遠端機器，請讀取該機器上 SSH 伺服器的日誌，其中來自 Desktop 的登入看起來與來自終端機的登入相同。Desktop 在 macOS 或 Linux 上時，預期每次 Desktop 連線會有一筆記錄，而不是每個工作階段一筆。

如果伺服器設定了 `MaxSessions 1`，每次 Desktop 連線或重新連線時至少會有兩筆項目。每個終端機分頁，以及每個您在其中執行以 `!` 開頭之命令的 Desktop 工作階段，至少還會再多一筆。

您在 Claude Code 的[指標與事件](https://code.claude.com/docs/zh-TW/monitoring-usage.md#available-metrics-and-events)中找不到 Desktop 的 SSH 連線。若要從中得知 SSH 工作階段在哪台遠端機器上執行，請參閱[將遙測歸因於 Desktop SSH 工作階段](https://code.claude.com/docs/zh-TW/monitoring-usage.md#attribute-telemetry-to-desktop-ssh-sessions)。關於 Desktop 自身的連線記錄，請參閱[取得 SSH 問題的 Desktop 日誌](#get-desktops-logs-for-an-ssh-problem)。

#### 登入前即關閉的連線

若 SSH 伺服器的日誌顯示在任何登入之前即關閉的連線，這些可能是 Desktop 對 SSH 連接埠的測試。Desktop 會測試機器是否有回應，例如在連線至該機器失敗之後。它會開啟至該連接埠的連線並立即關閉，不傳送任何內容。預期會有一次或連續數次測試，例如約兩分鐘內八次。

若沒有任何機制因此類連線而封鎖或拒絕位址，您不需要對 Desktop 的測試採取任何行動。若 Desktop 連線所用的位址遭到拒絕或封鎖，請檢查 [SSH 伺服器本身是否拒絕該位址](#check-whether-the-ssh-server-itself-refuses-the-address)，以及 [fail2ban 是否計入 Desktop 的測試](#check-whether-fail2ban-counts-desktops-tests)。

##### 在 SSH 伺服器的日誌中辨識測試

請將您日誌中的行，與 Linux 上的 OpenSSH 伺服器在預設 `LogLevel` 下為測試寫入的行進行比較，並對照您伺服器版本所在的列。若伺服器的問候訊息在 Desktop 關閉連線之前送達，您可能會看到最後一欄中的行：

| OpenSSH 版本 | 測試的行 | 問候訊息先送達時的行 |
| - | - | - |
| 6.6 至 7.9 | 含有 `Did not receive identification string from 203.0.113.7` 的行 | 相同的行 |
| 8.0 至 8.2 | `error: kex_exchange_identification: Connection closed by remote host` | `error: kex_exchange_identification: read: Connection reset by peer` |
| 8.3 至 9.4 | `error: kex_exchange_identification: Connection closed by remote host`，接著是 `Connection closed by 203.0.113.7 port 51234` | `error: kex_exchange_identification: read: Connection reset by peer`，接著是 `Connection reset by 203.0.113.7 port 51234` |
| 9.5 至 10.2 | `Connection closed by 203.0.113.7 port 51234` | `error: kex_exchange_identification: read: Connection reset by peer`，接著是 `Connection reset by 203.0.113.7 port 51234` |
| 10.3 至 10.5 | `Connection closed by 203.0.113.7 port 51234 [preauth]` | `error: kex_exchange_identification: read: Connection reset by peer [preauth]`，接著是 `Connection reset by 203.0.113.7 port 51234 [preauth]` |

其他開啟並關閉該連接埠的程式也可能留下相同的行。若行中有位址，請確認它是執行 Desktop 的電腦所連線的位址。

8.0 至 8.2 的行沒有位址。若要取得位址，請在 `sshd_config` 中設定 `LogLevel VERBOSE`，並以 root 身分執行 `sshd -T | grep -i loglevel`。若輸出 `loglevel VERBOSE`，請重新載入 SSH 伺服器。然後在測試的行之前尋找含有 `Connection from 203.0.113.7 port 51234` 的行。

##### 檢查 SSH 伺服器本身是否拒絕該位址

若來自許多執行 Desktop 的電腦共用之位址的連線遭到拒絕，請在 SSH 伺服器的日誌中尋找結尾類似下列內容的行：

```text theme={null}
drop connection #0 from [203.0.113.7]:51234 on [192.0.2.10]:22 penalty: connections without attempting authentication
```

在預設 `LogLevel` 下，OpenSSH 9.8 及更新版本在因連線未嘗試登入即關閉（如 Desktop 的測試）而拒絕某個位址時，可能會寫入這樣的行。在預設設定下，僅憑幾次測試不會出現這樣的行。

若要防止拒絕，請在 `sshd_config` 中將 `PerSourcePenaltyExemptList` 設為使用者連線所用的位址，例如 `PerSourcePenaltyExemptList 203.0.113.7`。伺服器接著不會對這些位址套用任何懲罰，包括針對登入失敗的懲罰。若要檢查該檔案，請以 root 身分執行 `sshd -T | grep -i persourcepenalt`。若輸出您的清單，請重新載入 SSH 伺服器。

##### 檢查 fail2ban 是否計入 Desktop 的測試

若 fail2ban 0.10.5 或更新版本封鎖了 Desktop 連線所用的位址，請在 `jail.conf`、`jail.local` 或 `jail.d/` 下找出您 jail 的模式：

* **在括號中指定模式的 `filter` 行**，例如 `filter = sshd[mode=aggressive]`：使用該模式。
* **只有原始的 `filter` 行**，含有 `[mode=%(mode)s]`：使用 `mode` 行，若沒有則為 `normal`。

若模式為 `normal`，fail2ban 不會計入 Desktop 測試的行，因此請尋找封鎖的其他原因。

若為其他模式，請將您自己日誌中的行複製到遠端機器上的檔案。複製每一行的完整內容，從日期到結尾；若測試留下兩行，則兩行都複製。在該處以該檔案與您 jail 的模式（例如 `aggressive`）執行 `fail2ban-regex`：

```bash theme={null}
fail2ban-regex -o ip lines.log "sshd[mode=aggressive]"
```

對於 fail2ban 計入的每次失敗，該命令會在單獨一行輸出位址，例如 `203.0.113.7`。在此情況下，請[防止封鎖](#prevent-a-ban-by-fail2ban)。若沒有輸出任何內容，表示 fail2ban 在該模式下不會計入這些行，因此請尋找封鎖的其他原因。

##### 防止 fail2ban 封鎖

若要防止 fail2ban 因 Desktop 的測試而封鎖某個位址，請變更 jail 的兩項設定之一，兩者各有代價：

* **`mode`**：在您 jail 設定它的任何位置將其設為 `normal`，無論是在 `mode` 行中，或在 `filter = sshd[mode=aggressive]` 這類行的括號中。您會放棄只有其他模式才會進行的所有計數，例如對未嘗試登入即連線並離開之用戶端的計數。
* **`ignoreip`**：將其設為使用者連線所用的位址，例如 `ignoreip = 203.0.113.7`。fail2ban 接著不會計入來自這些位址的任何內容，包括登入失敗。

#### 使用在遠端機器上設定的 MCP 伺服器

若要在 SSH 工作階段中使用來自 `~/.claude.json` 或專案 `.mcp.json` 的 [MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md)，請在遠端機器上的這些檔案中設定它。Claude Code 會在該處啟動它們的 stdio 伺服器，因此請在遠端機器上安裝這些伺服器所執行的命令。如需來自 `claude_desktop_config.json` 的伺服器，請參閱 [Desktop 中斷連線時的限制](#limits-while-desktop-is-disconnected)。

#### 從連結開啟 SSH 工作階段

`claude://code/new` 連結會開啟 Desktop 的新工作階段頁面，且可以指定 SSH 連線。將此類連結放在執行手冊、儀表板或 wiki 頁面中，即可開啟已針對正確機器和資料夾設定好的 Desktop。對於會移除此類連結的平台，請參閱[連結顯示為純文字而非可點選的連結](https://code.claude.com/docs/zh-TW/deep-links.md#the-link-renders-as-plain-text-instead-of-being-clickable)。

SSH 連結需要 Claude Desktop v2.110.0 或更新版本。

下列連結指定了 `build.example.com` 上的使用者 `dev`、連接埠 2222 和資料夾 `/srv/payments`，並填入提示詞：

```text theme={null}
claude://code/new?ssh_host=dev%40build.example.com&ssh_port=2222&ssh_folder=/srv/payments&q=Investigate%20the%20failed%20deploy
```

SSH 連結接受下列參數，其中只有 `ssh_host` 為必要參數：

| 參數 | 值 |
| :- | :- |
| `ssh_host` | `host` 或 `user@host`，寫法與 **SSH host** 欄位相同。值不能以 `-` 開頭，且主機部分只接受字母、數字、`.`、`_`、`:` 和 `-` |
| `ssh_port` | 1 到 65535 之間的連接埠號碼 |
| `ssh_folder` | 遠端機器上的資料夾。以 `/` 或 `~/` 開頭，或使用 `~` |
| `q` | 要填入提示詞方塊的 URL 編碼文字 |

來自 `~/.ssh/config` 的別名只有對擁有該項目的人才能作為 `ssh_host` 使用。若要符合人們已有的連線，請為連結提供與該連線相同的使用者、主機和連接埠。

當您開啟連結時，Desktop 會在選取連線之前要求您確認：

* **您已有的連線**：如果主機、使用者和連接埠與您的其中一個連線相符，Desktop 會詢問是否使用該連線，並顯示連線的名稱和主機，以及連結指定的資料夾（若有）。
* **新連線**：否則 Desktop 會開啟新增 SSH 連線的對話方塊。當您新增連線時，Desktop 會在儲存任何內容之前詢問是否連線，並顯示連結中的主機，以及連結指定的連接埠和資料夾（若有）。

在您確認之前，Desktop 不會儲存連結中的主機、連接埠或資料夾，也不會以它們選取或開啟連線。如果已選取某個 SSH 連線，新工作階段頁面仍可能自行連線到該連線，就像沒有連結時一樣，即使連結指定的是相同的主機。連結無法攜帶金鑰檔案、密碼或命令。

任何人都可以撰寫連結，因此請檢查它填入了什麼：

* **確認之前**：檢查主機和資料夾。
* **傳送之前**：檢查提示詞和所選的環境。

Desktop 會在連結開啟時填入提示詞，取代您尚未傳送的任何文字，且絕不會代您傳送。它會將提示詞視為純文字，因此開頭的 `/` 或 `!` 以及 `@` 檔案提及不會作為命令或提及。如果您取消，提示詞會保留在方塊中，且您原先選取的環境不會變更。

連結不會繞過 [`sshHostAllowlist`](#restrict-which-ssh-hosts-users-can-connect-to)。Desktop 會在連線時檢查允許清單。

如果連結開啟 Desktop 時沒有出現有關連線的對話方塊，請查看是否為下列原因之一：

* **您已登出**：請登入，然後再次開啟連結。
* **另一個對話方塊已開啟**：請關閉它，然後再次開啟連結。
* **連結無效**：Desktop 會顯示說明需修正內容的訊息，且不會填入提示詞。
* **Desktop 版本早於 v2.110.0**：較早的版本會忽略 SSH 參數，並只以提示詞開啟新工作階段頁面。
* **SSH 工作階段已關閉**：如果您的管理員將允許清單設為空陣列，Desktop 會拒絕 SSH 連結。

#### 透過命令建立 SSH 連線

若有命令列工具會依需求建立您的遠端機器，請將其命令新增至 [`~/.claude/settings.json`](https://code.claude.com/docs/zh-TW/settings#settings-files) 中的 `sshHostCommands`。環境選取器接著會列出以您的項目命名的選項，例如 **Create Dev box**。選取後，Desktop 會在您的電腦上執行該命令，將命令輸出的主機儲存為 SSH 連線，然後進行連線。

> [!NOTE]
>
> 從命令建立的連線需要在 macOS 或 Linux 上使用 Claude Desktop v3.6556.0 或更新版本，或在 Windows 上使用 v4.16336.0 或更新版本，並以 Claude 帳戶登入。在 Windows 上，Desktop 還必須[透過 OpenSSH 用戶端連線](#use-your-ssh-configuration)。管理員可以[將命令分發給團隊](#distribute-commands-to-your-team)。

Desktop 只有在您建立連線或[建立另一台機器](#create-another-machine)時才會執行該命令，而不是每次連線時都執行。每個項目都是一個連線，指向 Desktop 最後一次從該項目的命令所儲存的主機。

> [!WARNING]
>
> Desktop 不會停止或刪除機器。下列每一項都會持續運作，也可能持續產生費用，直到您用自己的工具將其刪除為止：
>
> * 在您[建立另一台](#create-another-machine)之前，某個項目所指向的機器
> * 您從檔案中移除的項目，或您變更了其 `id` 的項目所擁有的機器
> * 您的命令建立了、但 Desktop 未儲存其主機的機器，例如在下列情況中：
>   * 命令失敗或逾時
>   * Desktop 無法使用印出的主機、另一個連線已使用該主機，或您的組織不允許該主機
>   * 命令執行期間，您取消了它、移除了其項目、變更了其 `command` 或 `id`，或結束了 Desktop

以下範例新增一個名為 Dev box 的連線。若檔案不存在，請建立它。若檔案中已有設定，請將此設定鍵加在旁邊。命令 `acme-dev create` 代表您自己的工具，而 `~/project` 是 Desktop 在您的命令所建立的每台機器上選取的資料夾：

```json ~/.claude/settings.json theme={null}
{
  "sshHostCommands": [
    {
      "id": "devbox",
      "name": "Dev box",
      "command": "acme-dev create",
      "startDirectory": "~/project"
    }
  ]
}
```

在 Windows 上，像 `acme-dev` 這樣的單純名稱無法運作，因此請[以程式的完整路徑作為命令的開頭](#write-the-command-on-windows)。

每個項目接受以下欄位，其中 `id`、`name` 和 `command` 為必填：

| 欄位 | 值 |
| :- | :- |
| `id` | 最多 64 個 ASCII 字母、數字、`.`、`_` 和 `-`，且以字母或數字開頭。請使用 `sshHostCommands` 或 [`sshConfigs`](#pre-configure-ssh-connections-for-your-team) 中沒有其他項目使用的 `id`。Desktop 會以它保存連線的主機，因此若您變更它，該連線會從沒有主機的狀態重新開始，其機器會持續執行，且 Desktop [仍可連線到它們](#remove-an-entry)。 |
| `name` | 連線在環境選取器中的名稱，單行最多 200 個字元 |
| `command` | 程式及其引數，如[撰寫命令](#write-the-command)所述 |
| `sshIdentityFile` | 您私密金鑰的路徑，例如 `~/.ssh/id_ed25519`。省略此欄位即使用您的 SSH 設定或 SSH agent。 |
| `startDirectory` | 遠端機器上的預設資料夾。以 `/` 或 `~/` 開頭，或使用 `~`。 |

若要變更或移除連線，請編輯檔案中的對應項目，因為應用程式的 SSH 連線對話框不會為其開啟。編輯檔案後不需要重新啟動 Desktop。若項目沒有出現或無法選取，請參閱[若命令遺失或呈灰色](#if-a-command-is-missing-or-gray)。

##### 撰寫命令

在 Windows 上，請從[在 Windows 上撰寫命令](#write-the-command-on-windows)開始，其中說明了以下哪些規則適用於該平台。

在 macOS 和 Linux 上，Desktop 會直接啟動程式，不經過 shell，也沒有終端機：

* **程式**：寫出其名稱，或從 `/` 開始的完整路徑。Desktop 會在您的登入 shell 所匯出的 `PATH` 中尋找單純名稱。相對路徑（例如 `./acme-dev`）、以 `~` 開頭的路徑，以及 shell 別名和函式都無法運作。
* **路徑中的空格**：將程式的完整路徑放在單引號中，例如 `'/Users/you/My Tools/make-devbox' create`。引號（單引號或雙引號）需要 Claude Desktop v4.16336.0 或更新版本，且只能用於程式路徑的前後。
* **引數**：以空格分隔引數。在引號外，命令只能包含空格、ASCII 字母、數字以及字元 `+,-./:=@_~`，且任何單字都不能以 `~` 開頭。加上引號的路徑還可以包含一些其他字元，例如 `(`、`)` 和 `&`。
* **腳本**：如果命令需要其他任何內容，例如加上引號的引數、管線、變數，或包含 `?` 或 `&` 的 URL，請將其放入腳本中。讓腳本可執行，以 `#!` 行開頭，並將 `command` 設定為其完整路徑，例如 `/Users/you/bin/make-devbox`。在 macOS 上，請勿將腳本放在 Documents、Desktop 和 Downloads 資料夾中，macOS 可能會在這些位置封鎖它。
* **輸入**：程式不會取得任何輸入，也沒有終端機，因此無法在其中向您提示。若您的工具透過瀏覽器或提示讓您登入，請先從終端機登入，並在每次登入失效時再次登入。
* **環境**：程式會在您的家目錄中執行，並使用您的登入 shell 匯出的變數。Desktop 會在啟動時讀取這些變數，如同處理[`ProxyCommand`](#use-variables-from-your-shell-in-a-proxycommand) 一樣，因此變更變數後請結束並重新開啟 Desktop。
* **時間限制**：Desktop 會停止執行超過 10 分鐘仍未結束的程式。Desktop 的進度訊息不會顯示程式的輸出。若要更早停止程式，請選取該訊息旁的 **Cancel**。

程式必須以代碼 0 結束，並且只在標準輸出上輸出主機，格式為下列兩種之一：

* **一行**：`host` 或 `user@host`，寫法與 [SSH 連結](#open-an-ssh-session-from-a-link)中的 `ssh_host` 相同。若要指定連接埠，請使用 JSON 格式。
* **一個 JSON 物件**：`sshHost`，以及選填的數值 `sshPort` 和取代項目本身設定的 `startDirectory`，例如 `{"sshHost": "dev@devbox-1234.example.com", "sshPort": 2222}`

若要查看 Desktop 讀取的輸出，請在終端機中以無輸入、且標準輸出導向檔案的方式執行命令：

```bash theme={null}
acme-dev create < /dev/null > host.txt
```

檔案中必須只包含主機。執行此測試時，您的工具也會建立一台機器，因此事後請用您的工具將其刪除。

若您的工具在主機之前輸出其他行，例如進度訊息，請將其包裝在只輸出主機的指令碼中。以下指令碼會輸出工具輸出的最後一行。若工具失敗，指令碼會以相同代碼結束，讓 Desktop 回報失敗：

```bash theme={null}
#!/bin/bash
out=$(mktemp) || exit
trap 'rm -f "$out"' EXIT
acme-dev create > "$out" || exit
tail -n 1 "$out"
```

若命令失敗，Desktop 訊息中的 **View details** 會顯示命令寫入標準錯誤的最後一行（如果有的話）。

##### 在 Windows 上撰寫命令

在 Windows 上，`command` 必須以 `.exe`、`.cmd` 或 `.bat` 檔案從磁碟機代號開始的完整路徑開頭。Desktop 不會在您的 `PATH` 中尋找單純名稱，因此 `command` 為 `acme-dev create` 的項目會[呈灰色](#if-a-command-is-missing-or-gray)。

`%USERPROFILE%\.claude\settings.json` 中的以下項目會以引數 `create` 執行 `C:\Program Files\Acme\acme-dev.exe`。在 JSON 中，每個反斜線要寫兩次，或改寫為 `/`。因為路徑中有空格，所以使用單引號：

```json settings.json theme={null}
{
  "sshHostCommands": [
    {
      "id": "devbox",
      "name": "Dev box",
      "command": "'C:\\Program Files\\Acme\\acme-dev.exe' create"
    }
  ]
}
```

關於路徑中的空格、輸入、時間限制以及程式輸出的內容，請遵循[撰寫命令](#write-the-command)中的規則。其他規則則改為遵循以下規則：

* **程式**：請勿使用網路路徑（例如 `\\server\share`）、變數（例如 `%USERPROFILE%`）或 ASCII 以外的字母。路徑中只要有其中任何一項，項目就會呈灰色。如果您的使用者資料夾名稱中有此類字母，請將程式放在該資料夾之外。
* **引數**：遵循撰寫命令中的引數規則。命令還可以包含 `\`，但任何單字都不能以它結尾。
* **腳本**：使用 `.cmd` 或 `.bat` 檔案，Desktop 會透過 `cmd.exe` 執行它。即使加上引號，檔案路徑也不能包含 `&`、`^` 或 `;`。在您撰寫的檔案中，請使用 `%*` 讀取引數，因為 `%1` 到 `%9` 會在 `,` 和 `=` 處分割引數。
* **環境**：程式會取得 Desktop 應用程式的環境變數，而非 shell 設定檔中的變數。變更變數後，請結束並重新開啟 Desktop。
* **測試**：若要查看 Desktop 讀取的輸出，請在命令提示字元中執行命令。將包含空格的路徑放在雙引號中，並使用 `NUL` 表示無輸入，例如 `"C:\Program Files\Acme\acme-dev.exe" create < NUL > host.txt`。檔案中必須只包含主機。此測試也會建立一台機器，因此之後請用您的工具將其刪除。

##### 包裝會輸出其他行的 Windows 工具

如果您的工具在主機之前會輸出其他行，例如進度訊息，請將其包裝在只輸出主機的批次檔中。以下檔案會輸出您工具輸出的最後一行，並在您的工具失敗時以其代碼結束：

```batch make-devbox.cmd theme={null}
@echo off
setlocal
set "host="
set "out=%TEMP%\acme-dev-%RANDOM%.txt"
call "C:\Program Files\Acme\acme-dev.exe" create > "%out%"
set "code=%ERRORLEVEL%"
for /f "usebackq delims=" %%L in ("%out%") do set "host=%%L"
del "%out%"
if not "%code%"=="0" exit /b %code%
setlocal EnableDelayedExpansion
echo(!host!
```

將 `command` 設定為該檔案的完整路徑，在 JSON 中例如 `C:\\tools\\make-devbox.cmd`。請保持最後兩行不變，因為它們會輸出主機而不會將其當作命令執行。

##### 連線至新主機

第一次連線至每個新主機時，需回答兩個問題：

* **主機金鑰**：在 OpenSSH 預設的主機金鑰檢查下，請檢查金鑰的指紋，然後選擇是否連線。若要略過此問題，請讓您的命令在輸出主機之前，將金鑰新增到 `~/.ssh/known_hosts`（在 Windows 上為 `%USERPROFILE%\.ssh\known_hosts`）：
  * 使用您的工具在建立機器時得知的金鑰
  * 若連接埠不是 22，請以 `[host]:port` 作為該行的開頭
  * 如果您的工具會重複使用主機名稱，也請移除舊金鑰所在的行
* **資料夾**：選擇您是否信任在該處開啟的資料夾

請對這些主機保持主機金鑰檢查開啟，並為它們保留 `known_hosts` 檔案。若 `StrictHostKeyChecking` 為 `no` 或 `accept-new`，且 `UserKnownHostsFile` 也是 `/dev/null` 或 `none`，就沒有任何東西會記錄金鑰。之後當您的工具重複使用某個名稱時，您可能會在沒有警告的情況下連線至另一台機器。

即使電腦前沒有人，重複使用的名稱也很重要，因為 Desktop 會自行連線到這些主機。例如，它會在主機回應後，傳遞您在主機無法連線時所傳送的訊息。即使主機金鑰檢查已開啟，在下列情況中，訊息仍可能送達該名稱的新機器，因此請在機器被刪除之前[停止使用該機器](#stop-using-a-machine)：

* 您、您的命令或其他程式將新金鑰加入了 `known_hosts`，或移除了舊金鑰的那一行，就像您的命令在會新增主機金鑰時所做的那樣
* 您工具的機器共用同一個主機金鑰
* 您工具的機器共用一個受 `known_hosts` 信任的憑證授權單位
* 您或您的管理員設定了 `KnownHostsCommand` 或 `VerifyHostKeyDNS yes`，使 SSH 接受來自 `known_hosts` 以外的金鑰

##### 建立另一台機器

在您選取 **Create another Dev box** 之後，您在先前機器上的工作階段仍可繼續運作，而新的工作階段會使用新機器。在環境選擇器中選取該項目，即可建立全新的機器，或取代已不存在的機器。在新工作階段頁面上，表示 Desktop 無法連線到主機的訊息也會提供此選項。

* **先前機器上的工作階段**：請從側邊欄繼續這些工作階段，因為選擇器只列出 Dev box 目前的機器，而不列出先前的機器。Desktop 可能會自行連線到它們的機器，例如在 Desktop 啟動時，因此使用完畢後請[停止使用該機器](#stop-using-a-machine)。
* **在 Claude Desktop v4.4212.0 之前被取代的主機**：這些版本會顯示 **Replace Dev box's host**，並停止連線到被取代的主機。若要在該主機上繼續工作階段，請開啟該工作階段，選取 **Add SSH connection**，並儲存 Desktop 所填入的連線。在取代另一台主機之前，請先更新 Desktop。
* **在兩台機器上建立新工作階段**：在 [`sshHostCommands`](#create-an-ssh-connection-from-a-command) 中新增第二個項目
* **尚未回應的新主機**：讓新工作階段頁面保持開啟最多 10 分鐘，期間它會持續嘗試連線。若主機仍未回應，請在頁面的訊息中選取 **Create another Dev box**。
* **不久後再建立另一台機器**：在一小時內執行命令數次之後，每次再執行都需要在 Desktop 開啟的對話方塊中確認，該對話方塊會顯示命令

##### 停止使用機器

若要讓 Desktop 停止自行連線到由命令建立的機器，請封存該機器上的每個工作階段：

1. 在側邊欄中找到該機器的工作階段。工作階段的[詳細資料面板](#see-session-details)會顯示其執行所在的主機。
2. [封存每個工作階段](#archive-a-session)，並保持其封存狀態。
3. 若您在建立此機器之後，尚未從同一個 `sshHostCommands` 項目建立另一台機器，請[建立一台](#create-another-machine)，或[移除該項目](#remove-an-entry)。在那之前，該機器是該項目已儲存的連線，當您在選取該連線的情況下開啟新工作階段頁面時，Desktop 可能會連線到它。
4. 在應用程式中刪除連到該機器的任何其他 SSH 連線，或移除其 [`sshConfigs`](#pre-configure-ssh-connections-for-your-team) 項目。
5. 結束並重新開啟 Desktop，這會關閉其與該機器的連線，並結束其連線嘗試。
6. 使用您的工具刪除該機器。

##### 移除項目

在您從設定檔中移除項目或變更其 `id` 之後，其機器上的工作階段仍會保留，因此 Desktop 仍可連線到這些機器。它可能在電腦前沒有人時這麼做，例如為了重新加入工作階段正在執行的程序，或傳遞一則等待傳送的訊息。若要阻止此情況，請依[停止使用機器](#stop-using-a-machine)所述封存這些工作階段。

若您是管理員且移除了受管項目，您使用者的工作階段也會保留，且每位使用者都必須自行封存。若要自行封鎖該項目的機器，請設定一個 [`sshHostAllowlist`](#restrict-which-ssh-hosts-users-can-connect-to)，使其符合您使用者仍需要的主機，而不符合這些機器的主機名稱。只有在模式能區分兩者的情況下才能這麼做。

##### 將命令分發給團隊

若要為團隊提供連線，請在每台電腦上的 Claude Code [受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)檔案或 MDM 政策中設定 `sshHostCommands`，而不是在桌面應用程式自身的[裝置管理政策](#device-management-policies)中設定。使用者會在自己的項目旁看到您的項目，且應用程式不提供編輯或移除項目的方式，無論是他們的還是您的。

以下受管設定檔為使用者提供一個名為 Dev box 的連線，並關閉使用者自己的項目，以及來自使用者、專案和本機設定的 Claude Code hook：

```json managed-settings.json theme={null}
{
  "sshHostCommands": [
    {
      "id": "acme-devbox",
      "name": "Dev box",
      "command": "/usr/local/bin/acme-dev create"
    }
  ],
  "strictPluginOnlyCustomization": ["hooks"]
}
```

部署設定鍵之前，請確定以下各項：

* **設定鍵的放置位置**：若您針對 Claude Code 的 MDM 政策已設定某個[政策設定鍵](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)，請將其放在該處。否則，請將其放在受管設定檔中。預設情況下，這類政策的優先順序高於檔案，此時 Desktop 會忽略檔案中的項目。即使在適用[伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)的情況下，也請在電腦上設定：Desktop 會忽略伺服器受管設定中的此設定鍵，專案和本機設定中的也一樣。
* **`id`**：若使用者的 `sshHostCommands` 項目使用了您的 `id`，只有您的項目有效。若任何其他 SSH 連線使用了它，例如使用者 `sshConfigs` 中的連線，您的項目會呈灰色。請選擇使用者不太可能選用的 `id`。
* **程式**：提供其完整路徑，因為在 macOS 和 Linux 上，Desktop 會在每位使用者的 `PATH` 中查找單純名稱，而在 Windows 上，使用單純名稱的項目會呈灰色。程式會以使用者身分執行，並使用[該使用者的變數](#write-the-command)。
* **每個平台**：為 Windows 電腦部署一個項目，為 macOS 和 Linux 電腦部署另一個項目。使用 [Windows 路徑](#write-the-command-on-windows)的項目在 macOS 和 Linux 上會呈灰色，而使用 macOS 或 Linux 路徑的項目在 Windows 上會呈灰色。
* **使用者自己的項目**：Desktop 將使用者的項目視同 [hook](https://code.claude.com/docs/zh-TW/hooks.md)，因為兩者都會在電腦上執行程式。若只允許您的項目，請將 [`strictPluginOnlyCustomization`](https://code.claude.com/docs/zh-TW/settings-reference#strictpluginonlycustomization) 設為 `["hooks"]`，或將 `"hooks"` 加入其清單。這也會停用來自使用者、專案和本機設定的 Claude Code hook，且無法保留它們。若改為將該設定鍵或 [`allowManagedHooksOnly`](https://code.claude.com/docs/zh-TW/settings-reference#allowmanagedhooksonly) 設為 `true`，則會封鎖更多內容，詳見各設定鍵的說明。
* **所有項目**：若也要關閉您的項目，請在受管設定中設定 [`disableAllHooks`](https://code.claude.com/docs/zh-TW/settings-reference#disableallhooks)。若您設定了 [`disableDesktopLocalSessions`](https://code.claude.com/docs/zh-TW/settings-reference#disabledesktoplocalsessions)，或設定了不允許任何主機的 `sshHostAllowlist`，選擇器將不會列出任何 **Create** 或 **Create another** 項目。
* **鎖定設定的生效位置**：對於這些項目，Desktop 會從伺服器受管設定以及電腦自身的檔案或政策讀取 `allowManagedHooksOnly`、`strictPluginOnlyCustomization` 和 `disableAllHooks`，並套用較嚴格的結果。在 Desktop 向 claude.ai 檢查伺服器受管設定之前，所有項目都會呈灰色，即使您的組織沒有任何伺服器受管設定也是如此。
* **允許的主機**：若您設定了 [`sshHostAllowlist`](#restrict-which-ssh-hosts-users-can-connect-to)，請確保有模式符合您的工具輸出的每個主機名稱，並在模式中省略 `user@`。Desktop 只會在命令執行後檢查輸出的名稱，因此被清單拒絕的機器已經存在，使用者必須用您的工具將其刪除。每次連線時，解析後的 `HostName` 也必須符合。

部署設定鍵後，請在測試電腦上重新啟動 Desktop。在 Code 分頁的環境選取器中，查看 **SSH** 底下，或單一的 **SSH** 列。您的項目會顯示為 **Create** 選項，或顯示為灰色選項，將游標移至其上時會顯示原因。若項目不見了，請檢查您放置設定鍵的位置，再檢查[若命令遺失或呈灰色](#if-a-command-is-missing-or-gray)中的情況。

##### 若命令遺失或呈灰色

在下列情況中，環境選擇器不會列出任何 **Create** 或 **Create another** 項目：

* **檔案**：`~/.claude/settings.json` 含有[無效的 JSON 或被 schema 拒絕的值](https://code.claude.com/docs/zh-TW/settings.md#fix-a-broken-settings-file)、您拼錯了設定鍵，或您將其放在專案的設定中。請修正檔案。
* **帳戶**：您使用的是[第三方提供者](https://code.claude.com/docs/zh-TW/third-party-integrations.md)而非 Claude 帳戶。請自行將每個主機新增為 [SSH 連線](#ssh-sessions)。
* **Windows**：Desktop 版本早於 v4.16336.0，或未透過 OpenSSH 用戶端連線。請更新 Desktop 並符合 [OpenSSH 用戶端的需求](#use-your-ssh-configuration)，然後結束並重新開啟 Desktop。
* **您組織的設定**：您的管理員關閉了本機工作階段，或關閉了 SSH 工作階段。請詢問他們您是否可以使用命令。
* **沒有 `ssh` 程式**：Desktop 無法在您的電腦上啟動 OpenSSH 用戶端。請安裝它，或請您的管理員允許它，然後重新啟動 Desktop。

無法選取的項目會呈灰色。將游標移至其上即可查看原因：

* **項目中有錯誤**：修正訊息中指出的欄位或命令。如果 `id` 已被使用，請為該項目指定另一個。在 Windows 上，命令必須[以程式的完整路徑開頭](#write-the-command-on-windows)。
* **設定檔損壞**：當您自己的設定檔損壞時，您管理員的項目可能會呈灰色，並顯示指出該檔案的訊息。[修正檔案](https://code.claude.com/docs/zh-TW/settings.md#fix-a-broken-settings-file)。
* **新主機**：在 Desktop 儲存主機後的一分鐘內，[**Create another**](#create-another-machine) 會呈灰色。請在這一分鐘過後再選取它。在 Claude Desktop v4.4212.0 之前，**Replace Dev box's host** 會呈灰色 10 分鐘。
* **hook 已關閉或受限**：您自己的項目只在您自己的 hook 可以執行的地方有效。請從您的設定中移除 `disableAllHooks`，或詢問您的管理員。
* **設定仍在載入**：在 Desktop 載入您組織的[伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)之前，所有項目都會呈灰色，通常是在啟動後幾秒鐘內。若項目持續呈灰色，請檢查您與 claude.ai 的連線。

#### 為您的團隊預先設定 SSH 連線

管理員可以在[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)中設定 `sshConfigs`，將 SSH 連線分發給團隊成員。

* **使用者看到的內容**：以此方式定義的連線會自動出現在每位使用者的環境選擇器中。
* **使用者可以變更的內容**：使用者可以選取受管連線，並為其[設定自己的 **Worktree folder**](#set-the-worktree-folder-on-an-existing-connection)。他們無法在應用程式中編輯其他欄位或刪除該連線。

下列範例預先設定了單一連線：

```json theme={null}
{
  "sshConfigs": [
    {
      "id": "shared-dev-vm",
      "name": "Shared Dev VM",
      "sshHost": "user@dev.example.com",
      "sshPort": 22,
      "sshIdentityFile": "~/.ssh/id_ed25519"
    }
  ]
}
```

每個項目都需要 `id`、`name` 和 `sshHost`。`sshPort` 和 `sshIdentityFile` 欄位為選用。使用者也可以將 `sshConfigs` 加入自己的 `~/.claude/settings.json`。

如果您在 `sshHost` 中省略 `user@`，Desktop 會以每位開發人員的 `~/.ssh/config` 為該主機設定的 `User` 連線，否則以他們在自己電腦上的使用者名稱連線。

#### 限制使用者可連線的 SSH 主機

管理員可以在[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)中設定 `sshHostAllowlist`，將 Desktop 的 SSH 工作階段限制在一組核准的主機。設定後，使用者只能連線到解析後主機名稱符合其中一個模式的主機。將其設為空陣列即可停用 SSH 工作階段。[`sshHostAllowlist` 參考項目](https://code.claude.com/docs/zh-TW/settings-reference#sshhostallowlist)說明空陣列如何與其他受管來源中的清單合併。

下列範例允許連線到 `devboxes.example.com` 下的任何主機，以及單一指定的堡壘主機：

```json theme={null}
{
  "sshHostAllowlist": ["*.devboxes.example.com", "bastion.example.com"]
}
```

> [!WARNING]
>
> 如果您的組織提供[伺服器管理的設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)，請在該處設定 `sshHostAllowlist`。預設情況下，Desktop 只會從[提供政策鍵的最高排名受管來源](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)讀取此鍵。如果該來源未設定此鍵，Desktop 會忽略較低排名的 MDM 政策或受管設定檔中的清單，並將此鍵視為[未設定](https://code.claude.com/docs/zh-TW/settings-reference.md#sshhostallowlist)。Desktop 不會顯示任何警告。
>
> 也請在每位使用者機器上的最高排名 MDM 政策或受管設定檔中保留相同的清單。Desktop 會在啟動時擷取伺服器管理的設定，且不會保留快取副本，因此在擷取成功之前，套用的是機器上的清單。

模式不區分大小寫。`*` 符合任何主機，`*.example.com` 符合 `example.com` 及其任何子網域。其他任何寫法皆為完全比對。檢查會針對經由 `ssh -G` 進行 `~/.ssh/config` 解析後的主機名稱執行，因此只要 `Host` 別名解析後的 `HostName` 相符，該別名即可獲准。工作階段的[跳板主機](#allow-jump-hosts)也必須相符。

`sshHostAllowlist` 只會從受管設定讀取；使用者或專案設定中的值會被忽略。只有 Claude Desktop 應用程式會遵循此設定；Claude Code CLI 和 IDE 擴充功能不會讀取它，且它不會限制透過 Bash 工具執行的 `ssh` 命令。它管理的是 Desktop 應用程式會連線到哪些主機，而不是網路出口流量，因此如果您需要硬性邊界，請將它與您組織的網路或零信任控制措施搭配使用。

##### 允許跳板主機

將 Desktop 會檢查的每個跳板主機，以其本身解析後的 `HostName` 加入 `sshHostAllowlist`。請在使用者更新至 Claude Desktop v3.1623.0 或更新版本之前加入跳板主機，否則使用者將無法透過這些主機連線。

> [!WARNING]
>
> 清單只有一種項目，因此使用者也可以在您列出的任何主機上啟動工作階段。請只列出您也願意讓使用者在其上執行工作階段的跳板主機。

Desktop 會檢查使用者的 `~/.ssh/config` 為工作階段主機設定的 `ProxyJump` 中的跳板主機，或寫成 `ssh -W %h:%p <host>` 的 `ProxyCommand` 中的跳板主機。如果 Desktop 在連線或重新連線工作階段時，所檢查的某個跳板主機不在清單上，連線就會失敗。當使用者啟動工作階段或傳送訊息時，錯誤詳細資料會提供該跳板主機的 `HostName`，也就是需要加入的名稱：

```text theme={null}
SSH host "bastion.example.com" is not allowed by your organization's managed settings. It is a jump host on the way to "devbox".
```

如果訊息中提到 `managed settings on this computer`，請將該名稱加入使用者電腦上的清單。如果缺少多個跳板主機，錯誤一次只會指出一個。若要在使用者更新之前找出所有名稱，請在使用者電腦上使用終端機：

**1. 找出路徑**

以使用者連線的主機執行 `ssh -G`，例如 `ssh -G devbox`。尋找 `proxyjump` 行，或寫成 `ssh -W %h:%p <host>` 的 `proxycommand` 行。即使命令帶有 `-l`、`-p`、`-J`、`-q`、`-v`、`-N`、`-T`、`-x` 或 `-a` 中的任何一個，仍會計入，且 `-J` 之後的主機也是跳板主機。如果 `proxycommand` 行執行的是 `ssh` 以外的程式，則無須為其加入任何項目。

**2. 查詢每個跳板主機**

對該行中的每個跳板主機執行 `ssh -G`，不要帶任何 `:port`，並記下其輸出的 `hostname`。如果該行第一個跳板主機的輸出中有上述任一種行，請以該行重複此步驟。忽略後續跳板主機輸出中的此類行。

**3. 加入名稱**

將每個主機名稱，或涵蓋該名稱的萬用字元，加入您設定清單的每個受管來源中的 `sshHostAllowlist`。然後請使用者結束並重新開啟 Desktop，因為 Desktop 會在啟動時擷取伺服器受管設定。

#### 關閉本機工作階段並分發 SSH 連線

若要關閉本機工作階段並將 SSH 工作階段限制在您選擇的主機，請同時部署 [`disableDesktopLocalSessions`](https://code.claude.com/docs/zh-TW/settings-reference#disabledesktoplocalsessions)、[`sshConfigs`](#pre-configure-ssh-connections-for-your-team) 和 [`sshHostAllowlist`](#restrict-which-ssh-hosts-users-can-connect-to)。

> [!NOTE]
>
> 此設定適用於使用 Claude 帳戶登入的使用者。使用[第三方供應商](https://code.claude.com/docs/zh-TW/third-party-integrations.md)時，SSH 工作階段預設為關閉，而設定 `sshHostAllowlist` 可以開啟它們。部署這些鍵之前，請閱讀 [SSH remote sessions in Claude Desktop on 3P](https://claude.com/docs/third-party/claude-desktop/ssh-remote-sessions)。

下列範例關閉本機工作階段、新增一個連線，並將 SSH 工作階段限制在該連線的主機：

```json managed-settings.json theme={null}
{
  "disableDesktopLocalSessions": true,
  "sshConfigs": [
    {
      "id": "shared-dev-vm",
      "name": "Shared Dev VM",
      "sshHost": "dev.example.com"
    }
  ],
  "sshHostAllowlist": ["dev.example.com"]
}
```

這些鍵適用於桌面應用程式。它們不會影響執行 Claude Code 的其他方式，例如 CLI、Cowork 和雲端工作階段：

* **CLI**：這些鍵都無法阻止開發人員在自己的電腦上執行 Claude Code CLI
* **Cowork**：這些鍵都不適用於 [Cowork](https://claude.com/docs/cowork/overview) 工作階段或 Cowork 排程任務
* **雲端工作階段**：這些鍵都不會改變[雲端工作階段](#cloud-sessions)是否可用。若要關閉它們，請使用 [Admin console 控制項](#admin-console-controls)下的 **Cloud sessions** 設定。

調整範例時，請檢查主機名稱、Desktop 版本和檔案權限：

* **主機名稱**：確認 `sshHostAllowlist` 中有模式符合每個 `sshConfigs` 項目的主機名稱（不含 `user@`），否則開發人員將無法連線至該主機。此外，也請加入符合 Desktop 在前往該主機途中所檢查的每個[跳板主機](#allow-jump-hosts)的模式。關於 Desktop 如何比對主機名稱，請參閱[限制使用者可以連線的 SSH 主機](#restrict-which-ssh-hosts-users-can-connect-to)。
* **版本**：`disableDesktopLocalSessions` 需要 Claude Desktop v1.37937.0 或更新版本
* **檔案權限**：確保電腦上每位開發人員的帳戶都能讀取受管設定檔。Desktop 不會套用帳戶無法讀取之檔案中的鍵，而 Claude Code 也會[在沒有這些鍵的情況下啟動](https://code.claude.com/docs/zh-TW/managed-settings.md#find-entries-claude-code-dropped)。

將這三個鍵放在同一個[受管來源](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)中，也就是您提供的最高排名來源。如果您提供[伺服器管理的設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)，也請在每台電腦上的最高排名 MDM 政策或受管設定檔中保留這三個鍵的副本。Desktop 會在啟動時擷取伺服器管理的設定，而在擷取成功之前，會套用電腦上的副本。

若要確認設定已套用，請檢查開發人員的電腦：

**1. 檢查環境選擇器**

結束並重新開啟 Desktop，然後開啟[環境選擇器](#start-a-session)。如果其中顯示以下內容，表示設定已生效：

* 該電腦的項目，以灰色顯示
* **SSH** 下的 **Shared Dev VM**。如果該處未列出，請點擊單一的 **SSH** 列，或群組末端的 **More**。

如果該電腦的項目仍可使用，請檢查是否為下列原因：

* **Desktop 版本**：如果 Desktop 早於 v1.37937.0，請更新 Desktop。
* **受管設定檔**：請確保該檔案為有效的 JSON。
* **受管來源**：請確保該電腦會讀取存放這些鍵的[受管來源](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)。

**2. 新增不在允許清單上的主機**

使用不在允許清單上的主機名稱（例如 `other.example.com`）[新增 SSH 連線](#ssh-sessions)。Desktop 會儲存該連線但拒絕連線，並表示您組織的設定不允許此連線。

## 企業設定

Team 或 Enterprise 計畫上的組織可以透過管理員主控台控制、受管設定檔案和裝置管理原則來管理桌面應用程式行為。

### 管理員主控台控制

這些設定透過[管理員設定主控台](https://claude.ai/admin-settings/claude-code)進行設定：

* **Desktop**：控制您組織中的使用者是否可以在桌面應用程式中存取 Claude Code
* **雲端工作階段**：為您的組織啟用或停用[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)
* **Remote Control**：為您的組織啟用或停用 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md)

在已啟用 HIPAA 的 Enterprise 組織中，**Desktop** 切換開關預設為關閉，[Owner](https://code.claude.com/docs/zh-TW/server-managed-settings.md#access-control) 可以將其開啟。套用 [HIPAA 設定](https://code.claude.com/docs/zh-TW/hipaa-setup.md)會將其關閉，即使先前已開啟也一樣，因此 Owner 之後必須再將其開啟。**雲端工作階段**和 **Remote Control** 預設也為關閉，且一旦組織套用了 HIPAA 設定，Owner 便無法將其開啟。

> [!NOTE]
>
> 管理員主控台[資料和隱私設定](https://claude.ai/admin-settings/data-privacy-controls)中**監控**下的 Cowork OpenTelemetry 表單僅適用於 Cowork 工作階段。在此機器上的 Cowork 工作階段中，桌面應用程式會將該收集器作為 `OTEL_*` 環境變數傳遞給 Claude Code，因此即使該工作階段中的 Claude Code [永遠不會擷取管理員主控台設定](#managed-settings)，表單仍會生效。
>
> 若要從 Code 分頁工作階段匯出遙測，請在 Claude Code 受管設定的 `env` 區塊中設定 `CLAUDE_CODE_ENABLE_TELEMETRY` 和 `OTEL_*` 變數，如[監控的管理員設定](https://code.claude.com/docs/zh-TW/monitoring-usage.md#administrator-configuration)所示。本機、雲端和 SSH 工作階段各自[從不同來源讀取受管設定](#managed-settings)。有關雲端工作階段可以連線的主機，請參閱[網路存取](https://code.claude.com/docs/zh-TW/cloud-environments.md#network-access)。有關 Code 分頁工作階段回報的 `service.name`，請參閱[服務資訊](https://code.claude.com/docs/zh-TW/monitoring-usage.md#service-information)。
>
> 若要了解 SSH 工作階段是在哪台遠端機器上執行，請參閱[將遙測歸屬於 Desktop SSH 工作階段](https://code.claude.com/docs/zh-TW/monitoring-usage.md#attribute-telemetry-to-desktop-ssh-sessions)。

### 受管設定

受管設定會覆寫專案和使用者設定，並套用於 Desktop 中的 Claude Code 工作階段。除非某個鍵的列另有說明，否則您可以在您組織的[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)檔案中設定這些鍵，或透過管理員主控台遠端推送它們。

| 鍵 | 描述 |
| - | - |
| `permissions.disableBypassPermissionsMode` | 設定為 `"disable"` 以防止使用者啟用略過權限模式。 |
| `disableAutoMode` | 設定為 `"disable"` 以從模式選擇器中移除 [Auto](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode) 模式。也可放在 `permissions` 下。 |
| `autoMode` | 自訂自動模式分類器在您的組織中信任和封鎖的內容。請參閱[設定自動模式](https://code.claude.com/docs/zh-TW/auto-mode-config.md)。 |
| `browserExternalPageTools` | 設定為 `"disabled"` 以防止 Claude 使用工具來讀取或操作[瀏覽器窗格](#browse-external-sites)中的外部頁面。使用者仍然可以自行瀏覽外部網站，本機開發伺服器預覽不受影響。 |
| `disableMobileSimulatorTools` | 設定為 `true` 以封鎖 Claude 在 [iOS Simulator 窗格](https://code.claude.com/docs/zh-TW/desktop-ios-simulator.md#turn-off-simulator-access)中控制和擷取裝置的工具。該窗格仍可供使用者自行點擊使用；只有 Claude 的存取被移除。該值必須是 JSON 布林值 `true`；字串 `"true"` 會被忽略。 |
| `disableBrowserExternalNavigation` | 設定為 `true` 以完全關閉[瀏覽器窗格](#browse-external-sites)中的外部瀏覽。使用者和 Claude 都無法瀏覽外部網站，localhost 開發伺服器預覽不受影響。該值必須是 JSON 布林值 `true`；字串 `"true"` 會被忽略。 |
| `sshConfigs` | 預先設定顯示在環境下拉式選單中的 [SSH 連線](#pre-configure-ssh-connections-for-your-team)。使用者無法刪除受管連線，除了自己的 **Worktree folder** 之外也無法編輯任何內容。 |
| `sshHostCommands` | 為使用者提供[主機來自命令的 SSH 連線](#distribute-commands-to-your-team)，與使用者自己的連線並存。Desktop 從電腦上的受管設定檔案或 MDM 原則讀取此鍵，並在[伺服器管理的設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)中忽略它。需要在 macOS 或 Linux 上使用 Claude Desktop v3.6556.0 或更新版本，或在 Windows 上使用 v4.16336.0 或更新版本，並以 Claude 帳戶登入。在 Windows 上，Desktop 還必須[透過 OpenSSH 用戶端連線](#use-your-ssh-configuration)。 |
| `sshHostAllowlist` | 將 [SSH 工作階段](#restrict-which-ssh-hosts-users-can-connect-to)限制在已解析主機名稱符合這些模式之一的主機。僅從受管設定讀取。 |
| `disableDesktopLocalSessions` | 設定為 `true` 以關閉[在裝置上執行的 Code 工作階段](#local-sessions-on-managed-devices)，僅保留連線到其他主機的 SSH 工作階段和雲端工作階段。該值必須是 JSON 布林值 `true`。僅從受管設定讀取。需要 Claude Desktop v1.37937.0 或更新版本。 |
| `disableSshSavedPasswords` | 設定為 `true` 以停止 Desktop 提供記住 SSH 密碼的選項，並停止使用或顯示先前已儲存的密碼。開啟此設定不會刪除這些密碼。僅從受管設定讀取。需要 Claude Desktop v1.49585.0 或更新版本。 |
| `managedMcpServers` | 將 MCP 伺服器設定推送給所有使用者。僅在第三方 (3P) Desktop 部署中可用。在每個項目中，設定 `"http"`、`"sse"` 或 `"stdio"` 的傳輸方式、連線詳細資訊，以及可選的 `toolPolicy` 對應，以限制使用者可以叫用該伺服器的哪些工具。請透過受管設定檔案、MDM 或 Claude apps gateway 原則的 [`desktop` 區塊](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#claude-desktop-overlay)傳遞，因為第三方部署不會收到管理員主控台設定。若要透過閘道傳遞，您需要在閘道伺服器上使用 Claude Code v2.1.232 或更新版本。這是桌面應用程式自己的鍵；Claude Code 會讀取自己的[同名受管設定](https://code.claude.com/docs/zh-TW/managed-mcp.md#provide-servers-through-managed-settings)，其項目結構不同。 |

哪些受管設定會套用到 Desktop 工作階段，取決於該工作階段執行的位置。模型限制（例如 [`availableModels`](https://code.claude.com/docs/zh-TW/model-config#restrict-model-selection)）在 Desktop 的 Claude Code 工作階段中的強制方式與終端機 CLI 相同；請參閱[使用介面涵蓋範圍](https://code.claude.com/docs/zh-TW/model-config.md#surface-coverage)。

* **此機器上的本機工作階段**：部署到磁碟的受管設定檔案會套用。當工作階段使用[符合條件的登入](https://code.claude.com/docs/zh-TW/server-managed-settings.md#platform-availability)向 Anthropic 的 API 進行身分驗證時，透過管理員主控台遠端推送的受管設定也會套用到這些工作階段，並遵循與終端機 CLI 相同的[設定優先順序](https://code.claude.com/docs/zh-TW/settings.md#settings-precedence)。
* **[雲端工作階段](#cloud-sessions)**：接收[伺服器管理的設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)；裝置部署的檔案不會套用到它們，因為它們在 Anthropic 管理的 VM 上執行。路由到[自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)的工作階段也會讀取執行器映像中的受管設定檔案。[Claude Code 如何結合受管來源](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)說明該檔案何時適用。
* **[SSH 工作階段](#ssh-sessions)**：工作階段從遠端主機讀取受管設定檔案。Desktop 本身會在本機上讀取 `sshConfigs`、`sshHostAllowlist`、`disableSshSavedPasswords` 和 `disableDesktopLocalSessions`。如果您傳遞多個受管來源，它[預設只從其中一個讀取](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)。
* **[Cowork](https://claude.com/docs/cowork/overview) 工作階段**：在此機器上的 Cowork 工作階段中，即使使用者以 Team 或 Enterprise 帳戶登入，Claude Code 也永遠不會擷取管理員主控台設定，並且會讀取部署到機器的原則，除非您的 Claude Desktop 設定設有 `requireCoworkFullVmSandbox`。遠端 Cowork 工作階段兩者皆不會接收。請參閱[原則適用的位置和時間](https://code.claude.com/docs/zh-TW/managed-settings.md#where-and-when-a-policy-applies)以了解哪些裝置檔案會套用到 Cowork，以及 [MCP 權限規則](https://code.claude.com/docs/zh-TW/permissions.md#mcp)以了解 `Bash` 和 `WebFetch` 規則如何套用於 Cowork 的工具。

在本機和 SSH 工作階段中，桌面應用程式會直接將每個使用者已連線的 claude.ai 連接器傳遞給 Claude Code。無論您使用哪個設定來源或檔案位置，任何 MCP 設定或 `managed-mcp.json` 都不會影響這些連接器。若要在這些工作階段中封鎖連接器的工具，請使用您組織的[連接器工具控制](https://code.claude.com/docs/zh-TW/mcp.md#organization-controls-on-connector-tools)。[連接器如何到達 Claude Code](https://code.claude.com/docs/zh-TW/mcp.md#how-connectors-reach-claude-code) 說明在每種工作階段中由哪些設定管理連接器。

`permissions.disableBypassPermissionsMode` 和 `disableAutoMode` 也可在使用者和專案設定中運作，但將它們放在受管設定中可防止使用者覆寫它們。

有關只有受管來源可以設定的權限、外掛和傳遞鍵，請參閱[只有受管設定可以設定的鍵](https://code.claude.com/docs/zh-TW/managed-settings.md#managed-only-settings)。

#### 在 Code 分頁中行為不同的 Claude Code 設定

在本機工作階段中，下列鍵（以及其他鍵）會產生不同的效果或沒有可見的效果，因為 Code 分頁取代了終端機介面。它們在終端機中仍然適用，因此您可以保留這些設定。

| 鍵 | 在本機工作階段中 |
| - | - |
| `askUserQuestionTimeout` | 逾時不適用，因此 Claude 提出的問題會保持開啟，等待使用者回答 |
| `awaySummaryEnabled` | 此鍵沒有效果 |
| `bashEditDiffEnabled` | Code 分頁不會顯示 Bash 命令所變更的檔案清單 |
| `companyAnnouncements` | Code 分頁不會顯示公告 |
| `defaultShell` | 使用者在 `!` 之後輸入的命令會在應用程式選擇的 shell 中執行：macOS 和 Linux 上為其登入 shell，Windows 上為 PowerShell |
| `fileSuggestion` | `@` 檔案選擇器會建立自己的檔案清單，不會執行您設定的命令 |
| `modelPicker` | 模型選擇器會列出每位使用者帳戶可用的模型。若要限制這些模型，請設定 [`availableModels`](https://code.claude.com/docs/zh-TW/model-config#restrict-model-selection)。 |
| `pluginTrustMessage` | 使用者安裝外掛時看到的警告不會包含您設定的訊息 |
| `prUrlTemplate` | pull request 連結使用 pull request 本身的 URL，而非範本 |
| `respectGitignore` | `@` 檔案選擇器會建立自己的檔案清單，不會讀取此鍵 |
| `respondToBashCommands` | 無論值為何，Claude 都會回應使用者以 `!` 執行的命令輸出 |
| `showClearContextOnPlanAccept` | 使用者核准計畫時不會有清除上下文的選項 |
| `skipDangerousModePermissionPrompt` | Code 分頁對[略過權限模式](#choose-a-permission-mode)有自己的確認步驟，此鍵不會略過該確認 |
| `verbose`、`viewMode` | 每位使用者在[工作階段選單中的**逐字稿檢視**](#switch-view-modes)下選擇檢視方式 |
| `worktree.baseRef`、`worktree.sparsePaths`、`worktree.symlinkDirectories` | 不會用於 Code 分頁為工作階段建立的 worktree |

### 裝置管理原則

IT 團隊可以透過 macOS 上的 MDM、Windows 上的群組原則或 Linux 上的原則檔案來管理桌面應用程式。可用的原則包括啟用或停用 Claude Code 功能、控制 macOS 和 Windows 上的自動更新，以及設定自訂部署 URL。

* **macOS**：使用 Jamf 或 Kandji 等工具透過 `com.anthropic.claudefordesktop` 偏好設定網域進行設定
* **Windows**：透過位於 `SOFTWARE\Policies\Claude` 的登錄進行設定
* **Linux**：透過位於 `/etc/claude-desktop/managed-settings.json`、由 root 擁有的檔案進行設定，該檔案以 JSON 物件保存原則鍵。如果 root 以外的任何人可以寫入該檔案或其資料夾，Desktop 會拒絕使用該檔案。它與 Claude Code 的[受管設定檔案](https://code.claude.com/docs/zh-TW/managed-settings.md)是不同的檔案。

#### 將登入限制為您的組織

若要限制哪些 claude.ai 組織可以登入 Claude Desktop，請在 Claude Desktop 原則中設定 `forceLoginOrgUUID`。

此鍵需要 Claude Desktop v1.2581.0 或更新版本。

在 Linux 上，僅設定此鍵的原則檔案內容如下：

```json /etc/claude-desktop/managed-settings.json theme={null}
{
  "forceLoginOrgUUID": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

請將預留位置替換為您的 claude.ai 組織 ID，該 ID 顯示在 [claude.ai 管理設定](https://claude.ai/admin-settings/organization)中。它與 Claude Code 的 [`forceLoginOrgUUID`](https://code.claude.com/docs/zh-TW/settings-reference#forceloginorguuid) 設定所使用的 ID 相同。有關設定此鍵的 macOS 和 Windows 範例，請參閱適用於 HIPAA-ready 組織的 Cowork 指南中的[部署 Claude Desktop 原則](https://claude.com/docs/cowork/hipaa-setup#deploy-the-claude-desktop-policy)。

> [!WARNING]
>
> 部署之前，請先檢查 `forceLoginOrgUUID` 的值。如果該 ID 不是您組織的 ID，您組織中的成員將無法使用 Claude Desktop，除非他們也屬於具有該 ID 的組織。若要復原，請部署正確的 ID，並請他們重新啟動 Claude Desktop。

如果您在 Claude Code 的[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)中設定 `forceLoginMethod` 和 `forceLoginOrgUUID`，並不會改變 Claude Desktop 的登入畫面。

### 網路存取需求

Desktop 從 Anthropic CDN 主機載入其應用程式程式碼和使用者內容。

```text theme={null}
anthropic.com
*.anthropic.com
claude.ai
*.claude.ai
claude.com
*.claude.com
claude.app
*.claude.app
*.claudeusercontent.com
*.claudemcpcontent.com
```

除非您為 [OTLP](https://code.claude.com/docs/zh-TW/monitoring-usage.md)、LLM 閘道或 MCP 伺服器設定自訂連接埠，否則流量皆為連接埠 443 上的 HTTPS。

有關代理伺服器、自訂憑證授權單位、mTLS 和獨立 CLI 所需的網域，請參閱[網路設定](https://code.claude.com/docs/zh-TW/network-config.md)。

若要減少防火牆萬用字元的數量，請改為允許這些 Anthropic 主機。某些子網域是動態產生的，必須保持為萬用字元。

```text theme={null}
anthropic.com
api.anthropic.com
a-api.anthropic.com
a-cdn.anthropic.com
s-cdn.anthropic.com
assets-proxy.anthropic.com
claude.ai
a.claude.ai
assets.claude.ai
downloads.claude.ai
*.livepreview.claude.ai
claude.com
platform.claude.com
sso.claude.com
*.livepreview.claude.app
*.claudeusercontent.com
*.claudemcpcontent.com
```

如果您的組織已為 Claude 啟用 [IP 允許清單](https://support.claude.com/en/articles/13200993-restrict-access-to-claude-with-ip-allowlisting)，請將 `bridge.claudeusercontent.com` 透過與 `claude.ai` 和 `api.anthropic.com` 相同的代理伺服器出口路由。如果您無法以這種方式路由，請將您的代理伺服器用於該主機的出口位址新增到您組織的 IP 允許清單，但僅限該位址專屬於您的組織時：共用的代理伺服器出口範圍也會放行該代理伺服器廠商的其他客戶。

Anthropic 會依據連線來源的位址，檢查與該主機的連線是否符合您組織的 IP 允許清單。如果您的代理伺服器透過不在該允許清單上的位址傳送該主機的流量，Claude in Chrome 和其他透過橋接連線的功能會停止運作，而應用程式的其餘部分則會繼續運作。

從 [Google Fonts](https://code.claude.com/docs/zh-TW/artifacts.md#improve-the-visual-design) 載入字體的 [artifact](https://code.claude.com/docs/zh-TW/artifacts.md) 也會請求 `fonts.googleapis.com` 和 `fonts.gstatic.com`。這兩個主機都是選用的。如果您封鎖它們，artifact 會以備援字體呈現。請以快速拒絕而非無聲丟棄的方式封鎖，讓字體請求立即失敗，而不會延遲頁面的首次呈現。

Artifact 也可以從 `cdnjs.cloudflare.com`、`cdn.jsdelivr.net`、`cdn.tailwindcss.com`、`code.jquery.com` 和 `unpkg.com` 載入 JavaScript 程式庫（例如 React 或圖表套件），且不會從其他任何外部主機載入。如果您封鎖這些主機，artifact 中依賴程式庫的部分將無法運作，而且與被封鎖的字體不同，被封鎖的程式庫沒有備援。此處同樣請以快速拒絕的方式封鎖，讓被封鎖的程式庫請求立即失敗，而不是懸置直到逾時。

### 身分驗證和 SSO

Team 和 Enterprise 組織可以要求所有使用者使用 SSO。有關計畫層級的詳細資訊，請參閱[身分驗證](https://code.claude.com/docs/zh-TW/authentication.md)；有關 SAML 設定，請參閱[設定 SSO](https://support.claude.com/en/articles/13132885-setting-up-single-sign-on-sso)；OIDC 設定則涵蓋在 [Claude Enterprise Administrator Guide](https://claude.com/resources/tutorials/claude-enterprise-administrator-guide) 中。

### 資料處理

Claude Code 在本機工作階段中於本機處理您的程式碼，或在雲端工作階段中於 Anthropic 管理的基礎設施上處理，除非您的組織將它們路由到[自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)。雲端工作階段（包括在自託管環境中）會將對話和程式碼上下文傳送到 Anthropic 的 API 進行處理；本機和 SSH 工作階段則會將它們傳送到您的部署所設定的[模型提供者](#feature-comparison)，預設為 Anthropic 的 API。有關資料保留、隱私和合規性的詳細資訊，請參閱[資料處理](https://code.claude.com/docs/zh-TW/data-usage.md)。

### 部署

Desktop 可以透過企業部署工具分發：

* **macOS**：透過 MDM（例如 Jamf 或 Kandji）使用 `.dmg` 安裝程式分發
* **Windows**：透過 MSIX 套件部署。有關企業部署選項（包括無聲安裝），請參閱[為 Windows 部署 Claude Desktop](https://support.claude.com/en/articles/12622703-deploy-claude-desktop-for-windows)

有關需在防火牆中加入允許清單的網域，請參閱上方的[網路存取需求](#network-access-requirements)。有關代理伺服器設定、自訂憑證授權單位和 LLM 閘道，請參閱[網路設定](https://code.claude.com/docs/zh-TW/network-config.md)。

有關完整的企業設定參考，請參閱[企業設定指南](https://support.claude.com/en/articles/12622667-enterprise-configuration)。

## 來自 CLI？

如果您已經使用 Claude Code CLI，Desktop 執行相同的基礎引擎，具有圖形介面。您可以在同一機器上同時執行兩者，甚至在同一專案上執行。每個都維護單獨的工作階段清單，您可以將 CLI 工作階段帶入 Desktop。它們透過 CLAUDE.md 檔案共用設定和專案記憶。

若要將 CLI 工作階段移至 Desktop，請在終端機中執行 `/desktop`。Claude 儲存您的工作階段並在桌面應用程式中開啟它，然後退出 CLI。此命令在 macOS 和 x64 Windows 上可用，當您使用 Claude 訂閱登入時。它不適用於 API 金鑰身分驗證或 Amazon Bedrock、Google Cloud 的 Agent Platform 或 Microsoft Foundry。

從您的 shell，[`claude --desktop`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 直接開啟 Desktop，無需啟動終端機工作階段。它需要 Claude Code v2.1.285 或更新版本，並具有與 `/desktop` 相同的平台和登入要求。沒有其他引數時，它會在目前目錄中開啟 Desktop。若要在 Desktop 中開啟現有的 CLI 工作階段，請為此目錄中最近的對話新增 `--continue`，或使用 `/status` 顯示的工作階段 ID 新增 `--resume`：

```bash theme={null}
claude --desktop --resume <session-id>
```

Claude Code 列印 `Opening session <session-id> in Claude Desktop`，工作階段在應用程式中開啟，命令退出。工作階段名稱不能代替 ID。Claude Code 不會移動在另一個終端機中開啟或仍在背景執行的工作階段。如果未安裝 Claude Desktop，命令會列印下載連結並退出。

您也可以從 Desktop 內部使用 `/resume` 取得 CLI 工作階段。此命令在本機工作階段中可用，不在 SSH、WSL 或雲端工作階段中可用。

若要在 Desktop 中繼續終端機工作階段：

1. 在終端機中關閉工作階段。
2. 在 Desktop 提示詞方塊中，輸入 `/resume`。Desktop 列出您從此電腦上的 CLI 啟動的工作階段。按標題、資料夾或分支搜尋，並預覽每個工作階段停止的位置。
3. 選擇工作階段。它在應用程式中繼續進行，具有完整的對話和內容。

Desktop 繼續相同的工作階段而不是副本，因此之後在終端機中執行 `claude --resume` 仍然會找到它。

> [!TIP]
>
> 何時使用 Desktop 與 CLI：當您想要在一個視窗中管理並行工作階段、並排排列窗格或視覺化檢查變更時，使用 Desktop。當您需要指令碼、自動化或偏好終端機工作流程時，使用 CLI。

### CLI 旗標等效項

此表顯示常見 CLI 旗標的桌面應用程式等效項。未列出的旗標沒有桌面等效項，因為它們是為指令碼或自動化設計的。

| CLI | Desktop 等效項 |
| - | - |
| `--model sonnet` | 提示詞方塊下方列中的模型選擇器 |
| `--resume`, `--continue` | 點擊側邊欄中的工作階段，或在提示詞方塊中輸入 `/resume` 以取得您從 CLI 啟動的工作階段 |
| `--permission-mode` | 提示詞方塊下方列中的模式選擇器 |
| `--dangerously-skip-permissions` | 略過權限模式。在 Pro、Max 和 Ultra 方案上，在 **設定 > Code** 或 **設定 > Claude Code** 中啟用「允許略過權限模式」；在 Team 和 Enterprise 方案上，組織政策控制它 |
| `--add-dir` | 在本機和 SSH 工作階段中[將資料夾新增至工作階段](#add-folders-to-a-session)，或在雲端工作階段中選擇[多個儲存庫](#run-long-running-tasks-in-the-cloud) |
| `--allowedTools`, `--disallowedTools` | 沒有各別工作階段等效項。[設定檔](https://code.claude.com/docs/zh-TW/settings.md)中的權限規則仍然適用。 |
| `--verbose` | [Verbose 檢視模式](#switch-view-modes) |
| `--print`, `--output-format` | 不可用。Desktop 僅限互動。 |
| `ANTHROPIC_MODEL` 環境變數 | 提示詞方塊下方列中的模型選擇器 |
| `MAX_THINKING_TOKENS` 環境變數 | 請參閱[關閉延伸思考](#turn-off-extended-thinking) |

### 共用設定

Desktop 和 CLI 讀取相同的設定檔，因此您的設定會轉移：

* **[CLAUDE.md](https://code.claude.com/docs/zh-TW/memory.md)** 和 `CLAUDE.local.md` 檔案在您的專案中由兩者使用
* 在 `~/.claude.json` 或 `.mcp.json` 中設定的 **[MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md)** 在兩者中都有效
* 在設定中定義的 **[Hooks](https://code.claude.com/docs/zh-TW/hooks.md)** 和 **[skills](https://code.claude.com/docs/zh-TW/skills.md)** 適用於兩者
* `~/.claude.json` 和 `~/.claude/settings.json` 中的 **[設定](https://code.claude.com/docs/zh-TW/settings.md)** 是共用的。`settings.json` 中的權限規則、允許的工具和其他設定適用於 Desktop 工作階段。部分設定鍵[在 Code 標籤中的行為不同](#claude-code-settings-that-behave-differently-in-the-code-tab)。
* **模型**：相同的[模型](https://code.claude.com/docs/zh-TW/model-config.md#available-models)在兩者中都可用。在 Desktop 中，從提示詞方塊下方列中的模型選擇器選擇模型。您可以在工作階段期間從相同的選擇器變更模型。

#### Claude Desktop 聊天應用程式中的 MCP 伺服器

Desktop 應用程式從 `claude_desktop_config.json` 將 MCP 伺服器載入到本機 Code 標籤工作階段中，以及來自 `~/.claude.json` 和 `.mcp.json` 的伺服器。在 `claude_desktop_config.json` 中定義的伺服器在 Desktop 聊天使用介面和本機 Code 標籤工作階段中都可用。

如果您在 `claude_desktop_config.json` 和 `~/.claude.json` 或 `.mcp.json` 中定義相同的伺服器名稱，本機工作階段中的 Code 標籤連接一次並使用 `claude_desktop_config.json` 定義。

應用程式也會將 `~/.claude.json` 中的 stdio 伺服器重新傳遞到本機工作階段中的嵌入式 CLI。當 `~/.claude.json`（使用者範圍）和 `.mcp.json` 的頂層定義相同的 stdio 伺服器名稱時，Code 標籤使用 `~/.claude.json` 定義，偏離 CLI [範圍階層](https://code.claude.com/docs/zh-TW/mcp.md#scope-hierarchy-and-precedence)。

> [!NOTE]
>
> 獨立 CLI 不讀取 `claude_desktop_config.json`。在 macOS 和 WSL 上，執行 `claude mcp add-from-claude-desktop` 將這些伺服器複製到 `~/.claude.json`。請參閱[從 Claude Desktop 匯入 MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md#import-mcp-servers-from-claude-desktop)以了解匯入流程和範圍選項。

### 功能比較

此表比較 CLI 和 Desktop 之間的核心功能。有關 CLI 旗標的完整清單，請參閱 [CLI 參考](https://code.claude.com/docs/zh-TW/cli-reference.md)。

| 功能 | CLI | Desktop |
| - | - | - |
| 權限模式 | 所有模式，包括 `dontAsk` | Manual、Accept edits、Plan 和 Auto。Bypass permissions 在模式選擇器中出現，一旦啟用：在 Pro、Max 和 Ultra 方案上透過「設定」切換，或在 Team 和 Enterprise 方案上透過組織政策 |
| [第三方提供者](https://code.claude.com/docs/zh-TW/third-party-integrations.md) | Amazon Bedrock、Google Cloud 的 Agent Platform、Microsoft Foundry | Anthropic 的 API 預設。若要進行閘道路由，請參閱[將桌面應用程式連接到閘道](https://code.claude.com/docs/zh-TW/llm-gateway-connect.md#desktop-app)。若要在 Amazon Bedrock、Google Cloud 的 Agent Platform、Microsoft Foundry 或自託管 LLM 閘道上執行 Code 標籤，請參閱 [Claude Desktop on 3P](https://claude.com/docs/third-party/claude-desktop/overview)。 |
| [MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md) | 在設定檔中設定 | 本機和 SSH 工作階段的連接器 UI，或設定檔 |
| [外掛](https://code.claude.com/docs/zh-TW/plugins/overview.md) | `/plugin` 命令 | 外掛管理器 UI |
| @mention 檔案 | 文字型 | 具有自動完成，但雲端工作階段的第一則訊息除外 |
| 檔案附件 | 不可用 | 影像、PDF |
| 工作階段隔離 | [`--worktree`](https://code.claude.com/docs/zh-TW/cli-reference) 旗標 | [在專屬 worktree 中執行工作階段](#run-a-session-in-its-own-worktree) |
| 多個工作階段 | 單獨的終端機 | 側邊欄標籤 |
| 定期任務 | Cron 工作、CI 管道 | [排程任務](https://code.claude.com/docs/zh-TW/desktop-scheduled-tasks.md) |
| 電腦使用 | [透過 `/mcp` 在 macOS 上啟用](https://code.claude.com/docs/zh-TW/computer-use) | [應用程式和螢幕控制](#let-claude-use-your-computer)在 macOS 和 Windows 上 |
| iOS 模擬器 | 透過[電腦使用](https://code.claude.com/docs/zh-TW/computer-use.md#test-a-simulator-flow)驅動模擬器 | [iOS Simulator 窗格](https://code.claude.com/docs/zh-TW/desktop-ios-simulator.md)自動開啟 |
| Dispatch 整合 | 不可用 | [Dispatch 工作階段](#sessions-from-dispatch)在側邊欄中 |
| 指令碼和自動化 | [`--print`](https://code.claude.com/docs/zh-TW/cli-reference)、[Agent SDK](https://code.claude.com/docs/zh-TW/headless.md) | 不可用 |

### Desktop 中不可用的內容

以下功能在 Desktop 中不可用，除非另有說明：

* **第三方提供者**：Desktop 預設連接到 Anthropic 的 API。若要透過閘道路由 Desktop，或在 Amazon Bedrock、Google Cloud 的 Agent Platform、Microsoft Foundry 或自託管 LLM 閘道上執行 Code 標籤，請遵循[第三方提供者列](#feature-comparison)中的連結。
* **Linux (beta)**：Linux 桌面應用程式中尚未提供電腦使用。請參閱 [Claude Desktop on Linux](https://code.claude.com/docs/zh-TW/desktop-linux.md)。
* **內嵌程式碼建議**：Desktop 不提供自動完成樣式的程式碼補全。它透過對話式提示詞和明確的程式碼變更進行工作，並可在 Claude 回覆後[建議您的下一個提示詞](#accept-a-suggested-prompt)。
* **Agent teams**：協調的團隊，其中 Claude 作為團隊組長從共用任務清單中指派任務給隊員，在 [CLI](https://code.claude.com/docs/zh-TW/agent-teams.md) 中可用，不在 Desktop 中。若要在一個工作階段內進行多 agent 工作，請使用 [dynamic workflows](https://code.claude.com/docs/zh-TW/workflows.md)，它們在 Desktop 中執行；Claude 也可以[直接傳遞訊息和管理您的其他工作階段](#work-across-sessions)。
* **Terminal-dialog 命令**：在終端機中開啟互動式面板的內建命令，在 Code 標籤中的行為不同。直接編輯[設定檔](https://code.claude.com/docs/zh-TW/settings.md)以管理權限規則和設定，或從獨立 CLI 執行命令。
  * 沒有引數形式的命令，例如 `/permissions`，回覆 `isn't available in this environment`。
  * `/config` 開啟 **設定 > Code** 或 **設定 > Claude Code**。

## 疑難排解

下面的部分涵蓋桌面應用程式特定的問題。對於出現在聊天中的執行時 API 錯誤，例如 `API Error: 500`、`529 Overloaded`、`429` 或 `Prompt is too long`，請參閱[錯誤參考](https://code.claude.com/docs/zh-TW/errors.md)。

### 檢查您的版本

若要查看您執行的桌面應用程式版本：

* **macOS**：點擊選單列中的 **Claude**，然後點擊 **About Claude**
* **Windows**：點擊 **Help**，然後點擊 **About Claude**

點擊版本號以將其複製到您的剪貼簿。

#### Code 標籤中的 Claude Code 版本

若要查看工作階段執行的 Claude Code 版本，請在 **Code** 標籤的本機工作階段中輸入 `/status`，並查看 **Claude Code** 列，其中會顯示如 `2.1.286` 的版本。

若要為本機工作階段取得較新的版本，請在 macOS 上開啟 **Claude > Check for Updates…**，或在 Windows 上開啟 **Help > Check for Updates…**，然後啟動新的工作階段。

在本機工作階段中，**Code** 標籤會執行其自己的 Claude Code 副本，該副本有自己的版本號。桌面應用程式會下載並更新該副本，因此它可能與您終端機中的 `claude` 命令不同，且更新其中一個不會更新另一個。

### 檢查您使用的版面配置

如果新工作階段在提示詞方塊上方而非下方顯示[環境](#start-a-session)，表示您使用的是較早的版面配置：

* **[早於 v2.37337.0 的 Desktop](#check-your-version)**：請更新以取得目前的版面配置。在 macOS 上選擇 **Claude > Check for Updates…**，或在 Windows 上選擇 **Help > Check for Updates…**。
* **[第三方提供者](https://code.claude.com/docs/zh-TW/third-party-integrations.md)且工作階段在您的電腦上執行**：目前的版面配置需要 Claude Desktop v3.1623.0 或更新版本，因此請[檢查您的版本](#check-your-version)。若要更新，請在 macOS 上選擇 **Claude > Check for Updates…**，或在 Windows 上選擇 **Help > Check for Updates…**。如果您的組織[關閉了自動更新](#device-management-policies)，**Check for Updates…** 會被隱藏，因此請向您的管理員索取 v3.1623.0 或更新版本。
* **第三方提供者且工作階段在您組織的基礎架構上執行**：目前的版面配置需要 Claude Desktop v4.29.0 或更新版本，因此請[檢查您的版本](#check-your-version)。如果您使用的是較舊的版本，請向您的管理員索取 v4.29.0 或更新版本。如果您不知道您的工作階段在何處執行，請詢問您的管理員。

在較早的版面配置中，請在提示詞方塊上方選擇環境以及任何專案資料夾或儲存庫，並在其下方的列中選擇權限模式和模型。較早的版面配置沒有[工作階段詳細資訊面板](#see-session-details)和[已儲存的本機與 SSH 環境](#create-a-saved-environment)。

### Code 標籤中的 403 或驗證錯誤

如果在使用 Code 標籤時看到 `Error 403: Forbidden` 或其他驗證失敗：

1. 從應用程式選單登出並重新登入。這是最常見的修復。
2. 驗證您有有效的付費訂閱：Pro、Max、Ultra、Team 或 Enterprise。
3. 如果 CLI 有效但 Desktop 無效，完全退出桌面應用程式（不只是關閉視窗），然後重新開啟並登入。
4. 檢查您的網際網路連線和代理設定。

### 啟動時螢幕空白或卡住

如果應用程式開啟但顯示空白或無反應的螢幕：

1. 重新啟動應用程式。
2. 檢查待處理的更新。在 macOS 和 Windows 上，應用程式在啟動時自動更新；在 Linux 上，透過 apt 更新，如 [Claude Desktop on Linux](https://code.claude.com/docs/zh-TW/desktop-linux.md) 中所述。
3. 在受管理的網路上，確認您的防火牆允許[網路存取要求](#network-access-requirements)中的 CDN 主機。
4. 在 Windows 上，檢查「事件檢視器」中的 **Windows 日誌 → 應用程式** 下的當機日誌。

### 「無法載入會話」

如果您看到 `Failed to load session`，選定的資料夾可能不再存在、Git 儲存庫可能需要未安裝的 Git LFS，或檔案權限可能阻止存取。嘗試選擇不同的資料夾或重新啟動應用程式。

### 會話找不到已安裝的工具

如果 Claude 找不到 `npm`、`node` 或其他 CLI 命令等工具，請驗證工具在您的常規終端機中有效、檢查您的 shell 設定檔是否正確設定 PATH，並重新啟動桌面應用程式以重新載入環境變數。

### Git 和 Git LFS 錯誤

在其自己的 worktree 中執行的會話需要 Git。如果您看到「Git is required」，請安裝 [Git](https://git-scm.com/downloads)，或在 Windows 上安裝 [Git for Windows](https://git-scm.com/downloads/win)，然後重新嘗試。在 Windows 上，1.49585.0 之前的 Claude Desktop 版本在啟動任何本機會話之前要求 Git；如果您看到該提示且未使用 worktrees，請更新應用程式。

如果您看到「Git LFS is required by this repository but is not installed」，請從 [git-lfs.com](https://git-lfs.com/) 安裝 Git LFS，執行 `git lfs install`，然後重新啟動應用程式。

### Windows 上的 MCP servers 無法運作

如果 MCP server 切換沒有回應或伺服器在 Windows 上無法連接，請檢查伺服器是否在您的設定中正確配置、重新啟動應用程式、驗證伺服器程序在工作管理員中執行，並檢查伺服器日誌以查看連線錯誤。

### SSH host key verification failed

以下每則訊息都表示 Desktop 拒絕了某個[主機金鑰](#check-a-remote-machines-host-key)：

* `Couldn't connect to <host>` 卡片上 **View details** 下的 `SSH host key verification failed` 或 `Host denied (verification failed)`
* 提示詞方塊旁或 **Test connection** 之後的 `Connection failed: Host key changed or not trusted`
* 已中斷連線的工作階段上的 `<host>'s host key is not trusted` 或 `<host>'s host key has changed`

Desktop 通常會拒絕金鑰，是因為它與您電腦上儲存的金鑰不同，或是因為該機器沒有儲存任何金鑰。重建或重新安裝過的機器通常會提供新的金鑰，攔截連線的東西也會如此。請在再次連線之前檢查金鑰，並從 Desktop 隨訊息顯示的內容開始：

* **您使用 Windows，且 Desktop 顯示 `Connection failed: Host key changed or not trusted`**：請先排除[缺少 OpenSSH 用戶端](#ssh-host-key-refused-on-windows-without-an-openssh-client)的可能
* **Desktop 要求您設定 `UserKnownHostsFile`**：在 `~/.ssh/config` 中將其設為 `~/.ssh/known_hosts`，然後[從終端機檢查金鑰](#check-the-host-key-from-a-terminal)
* **您看到 Review new key 按鈕**：選擇它，並將 Desktop 顯示的指紋與該機器本身的指紋[比對](#check-a-remote-machines-host-key)。如果相符，請選擇 **Trust new key** 以取代已儲存的金鑰。否則請選擇 **Cancel**。
* **您沒有看到 Review new key 按鈕、Desktop 顯示 `Couldn't show the new key`，或 Desktop 在 Trust new key 之後再次拒絕金鑰**：[從終端機檢查金鑰](#check-the-host-key-from-a-terminal)

#### 從終端機檢查主機金鑰

在您的電腦上執行 `ssh <SSH host>`，其中使用 Desktop 中您的 [SSH 連線](#ssh-sessions)的 **SSH host** 值。如果該連線有 **SSH port** 值，請加上 `-p <SSH port>`。在 Windows 上請使用 PowerShell，因為 Desktop 不會使用 Git Bash 或 WSL 中的 `ssh` 進行連線。如果 PowerShell 找不到 `ssh`，請[安裝 Microsoft 的 OpenSSH 用戶端](#ssh-host-key-refused-on-windows-without-an-openssh-client)。

留意 `ssh` 在其訊息中指出的是哪台機器，那可能是跳板主機而非 `<SSH host>`，然後依照符合的情況處理：

* **`ssh` 詢問是否繼續連線**：將其顯示的指紋與該機器本身的指紋[比對](#check-a-remote-machines-host-key)。只有在相符時才回答 `yes`。
* **`ssh` 警告主機金鑰已變更**：將警告中的指紋與該機器本身的指紋[比對](#check-a-remote-machines-host-key)。只有在相符時，才刪除 `Offending <type> key in <file>:<line>` 指出的那一行，然後重新執行 `ssh`。如果 `ssh` 再次針對另一行發出警告，請如前所述比對、刪除並重新執行。
* **`ssh` 未經詢問就拒絕它不認識的金鑰**：向該機器的管理者取得其 `known_hosts` 行，而不要透過您正在檢查的連線取得。將該行加入您的 `known_hosts` 檔案，以 `ssh` 訊息中的名稱作為其主機名稱，然後重新執行 `ssh`。
* **`ssh` 未詢問您主機金鑰就繼續登入**：先不要輸入密碼。[檢查 `ssh` 已信任的金鑰](#check-the-keys-that-ssh-already-trusts)。

一旦 `ssh` 接受了您已檢查或加入的金鑰，請在 Desktop 中重試。如果 Desktop 再次拒絕金鑰，請參閱[取得 SSH 問題的 Desktop 日誌](#get-desktops-logs-for-an-ssh-problem)。

##### 檢查 `ssh` 已信任的金鑰

重新執行相同的 `ssh` 命令，並加上 `-v -S none`。在其輸出中，`Server host key:` 行會顯示指紋，而接下來的 `Host '<name>' is known` 行會指出該指紋所屬的機器。將您找到的每個指紋與該機器本身的指紋[比對](#check-a-remote-machines-host-key)。

* **跳板主機沒有 `Server host key:` 行**：也執行 `ssh -v -S none <jump host>`，並以相同方式比對該指紋。
* **指紋不相符，或您無法檢查**：不要再次連線。移除已儲存的金鑰：在 `Host '<name>' is known` 下，`Found key in <file>:<line>` 行會指出存放該金鑰的檔案。執行 `ssh-keygen -R "<name>" -f <file>`。如果您將主機金鑰存放在多個檔案中，請從每個檔案中移除該金鑰。如果您無法變更檔案，請告知您電腦的管理者。
* **每個指紋都相符**：請在 Desktop 中重試。如果 Desktop 再次拒絕金鑰，請參閱[取得 SSH 問題的 Desktop 日誌](#get-desktops-logs-for-an-ssh-problem)。

### 在沒有 OpenSSH 用戶端的 Windows 上 SSH 主機金鑰遭拒

在沒有 OpenSSH 用戶端的 Windows 上，Desktop 即使是正確的主機金鑰也會拒絕，並顯示 `Connection failed: Host key changed or not trusted`。它需要該用戶端來查詢已儲存的金鑰。若要查看您是否已安裝，請在 PowerShell 中執行 `ssh`。如果 PowerShell 無法辨識 `ssh`，請安裝 [Microsoft 的 OpenSSH 用戶端](https://learn.microsoft.com/windows-server/administration/openssh/openssh_install_firstuse)並重新啟動 Desktop。

然後再次連線。如果 Desktop 詢問是否首次連線，請在信任之前[檢查該機器的主機金鑰](#check-a-remote-machines-host-key)。如果 Desktop 仍拒絕金鑰，請依照 [SSH host key verification failed](#ssh-host-key-verification-failed) 下的其他情況處理。

### 登入後 SSH 連線失敗

在此表格中找到卡片的標題，或錯誤訊息結尾的代碼，然後依照最後一欄的說明操作。若要查看訊息，請在失敗卡片上選擇 **View details**。

| 卡片上的標題 | 代碼 | 處理方式 |
| - | - | - |
| `<host>'s SSH server has SFTP turned off` | `[SFTP_UNAVAILABLE]` | 在伺服器的 `sshd_config` 中開啟 SFTP，如[遠端機器要求](#remote-machine-requirements-for-ssh-sessions)中所述 |
| `SFTP doesn't start on <host>` | `[SFTP_NOT_STARTED]` | 在您電腦的終端機中使用 `sftp` 連線至同一主機，以查看是什麼阻止了它，然後檢查 Desktop 訊息中指出的設定和檔案 |
| `<host> allows too few SSH sessions per connection` | `[SESSION_LIMIT]` | 更新至 Claude Desktop v3.1623.0 或更新版本，或提高伺服器 `sshd_config` 中的 `MaxSessions`，例如提高至 OpenSSH 的預設值 10 |
| `<host> is out of disk space` | `[ENOSPC]` 或 `[EDQUOT]` | 釋放遠端機器上您家目錄或 `/tmp` 中的空間或配額 |
| `Free up disk space on this computer` | `[ENOSPC]` 或 `[EDQUOT]`，出現在以 `Couldn't prepare the deploy locally` 開頭的訊息中 | 釋放您電腦上的空間 |
| `Claude Code won't start on <host>` | `[CLI_UNRESPONSIVE]` | 等待一分鐘，然後重試。如果持續失敗，請在遠端機器上執行訊息中指出的命令，以查看 Claude Code 是否在該處有回應。 |
| `Ask <host>'s administrator to let Claude's server run` | `[SERVER_NOT_RUNNABLE]` 或 `[SETUP_DIR_NOEXEC]` | 請遠端機器的管理員允許程式從該機器上的 `~/.claude/remote/` 執行，如[要求](#remote-machine-requirements-for-ssh-sessions)中所述 |
| `Try again in a few minutes` | `[DOWNLOAD_BUSY]` | 等待幾分鐘，然後重試。Anthropic 的下載伺服器或您電腦所在網路上的代理伺服器回報其忙碌中。如果此卡片持續出現，請詢問該網路的管理員是否有代理伺服器限制下載。 |

對於任何其他訊息，請檢查[遠端機器要求](#remote-machine-requirements-for-ssh-sessions)。

### 取得 SSH 問題的 Desktop 日誌

`ssh.log` 是 Desktop 對其 SSH 連線的記錄，包含在您從 **Help** 選單儲存的 Desktop 日誌 zip 檔案中。若要儲存，請開啟 **Help > Troubleshooting**，並選擇適用於您系統的項目：

* **macOS**：**Show Logs in Finder**
* **Windows**：**Show Logs in File Explorer**
* **Linux**：**Show Logs in File Manager**

傳送前請先檢查這些檔案，因為其中可能包含您環境中的名稱和其他詳細資訊。`<host>` 和 `<user>` 代表 Desktop 已取代的名稱。Desktop 不會取代所有名稱，SSH 主機或使用者名稱仍可能以原樣出現。如果您將 zip 檔案傳送給他人，請告知是哪個主機在何時失敗，因為日誌中可能未指出該主機。

zip 檔案不包含 Desktop 安裝在遠端機器上的輔助程式的日誌。若也要取得該日誌，請從連線使用者家目錄中 [`~/.claude/remote/run/`](#files-and-processes-on-the-remote-machine) 下的輔助程式資料夾複製這些檔案：

* **`remote-server.log`**：輔助程式最近一次執行的日誌。
* **`remote-server.log.old`**（如果存在）：再前一次執行的日誌。請儘快複製，因為下次 Desktop 連線並必須再次啟動輔助程式時，您就會失去它。

傳送前也請檢查這些檔案。

### 應用程式無法退出

* **macOS**：按 Cmd+Q。如果應用程式沒有回應，使用 Cmd+Option+Esc 強制退出，選擇 Claude，然後點擊「強制退出」。
* **Windows**：使用 Ctrl+Shift+Esc 的工作管理員來結束 Claude 程序。

### Windows 特定問題

* **安裝後 PATH 未更新**：開啟新的終端機視窗。PATH 更新僅適用於新的終端機會話。
* **並行安裝錯誤**：如果您看到有關另一個安裝進行中的錯誤，但實際上沒有，請嘗試以管理員身份執行安裝程式。

### 在 CLI 中開啟時「分支尚不存在」

雲端工作階段可以建立在您的本機機器上不存在的分支。點擊工作階段中的分支名稱並選擇 **Copy branch name**，然後在本機提取它：

```bash theme={null}
git fetch origin <branch-name>
git checkout <branch-name>
```

### 仍然卡住？

* 在桌面應用程式中開啟「Help → Get Support」，或直接造訪 [Claude 支援中心](https://support.claude.com/)
* 對於在獨立 `claude` CLI 中也會重現的問題，請在 [GitHub Issues](https://github.com/anthropics/claude-code/issues) 上搜尋或提交錯誤

提交問題時，請包括您的桌面應用程式版本、您的作業系統、確切的錯誤訊息和相關日誌。在 macOS 上，檢查 Console.app。在 Windows 上，檢查「事件檢視器 → Windows 日誌 → 應用程式」。檢查日誌摘錄後再將其發佈到公開問題；它們可能包括來自您環境的檔案路徑和其他詳細資訊。

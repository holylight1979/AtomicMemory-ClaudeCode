<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/chrome | lastmod: 2026-10-30 | section: Getting started / Platforms and integrations -->
> 來源：https://code.claude.com/docs/zh-TW/chrome（官方 zh-TW，lastmod 2026-10-30）｜分類：Getting started › Platforms and integrations｜EN 摘要：Connect Claude Code to your Chrome browser to test web apps, debug with console logs, automate form filling, and extract data from web pages.

# 在 Chrome 中使用 Claude Code

> 將 Claude Code 連接到您的 Chrome 瀏覽器，以測試網頁應用程式、使用控制台日誌進行除錯、自動填充表單，以及從網頁中提取資料。

Claude Code 與 [Claude in Chrome 瀏覽器擴充功能](https://chromewebstore.google.com/detail/claude/fcoeoabgfenejglbffodgkkbkcdhcgfn)整合，為您提供從 CLI 或 [VS Code 擴充功能](https://code.claude.com/docs/zh-TW/vs-code.md#automate-browser-tasks-with-chrome) 進行瀏覽器自動化的功能。建立您的程式碼，然後在瀏覽器中測試和除錯，無需切換上下文。

Claude 為瀏覽器任務開啟新標籤頁，並共享您瀏覽器的登入狀態，因此它可以存取您已登入的任何網站。瀏覽器操作在可見的 Chrome 視窗中即時執行。當 Claude 遇到登入頁面或 CAPTCHA 時，它會暫停並要求您手動處理。

擴充功能會將 Claude 開啟的標籤頁收集到與您的工作階段綁定的 Chrome 標籤頁群組中。在本機工作階段中，工作階段結束時 Claude Code 是否會關閉該群組，取決於工作階段的結束方式：

* 當您輸入 `/clear` 時，Claude Code 會關閉該群組（包括已開啟的頁面），除非在清除後仍會保留的工作仍在執行中
* 當您使用 `/resume` 等命令切換工作階段、結束 Claude Code，或在清除後仍會保留的工作仍在執行時執行 `/clear`，Claude Code 只會在群組中僅包含空白新標籤頁時才關閉該群組，讓您可能仍在閱讀的頁面保持開啟

> [!NOTE]
>
> Chrome 整合適用於 Google Chrome 和 Microsoft Edge。Claude Code 也會在其他基於 Chromium 的瀏覽器（包括 Brave、Arc、Vivaldi 和 Opera）中偵測擴充功能並設定連線。Windows Subsystem for Linux (WSL) 不支援 Chrome 整合。

## 功能

連接 Chrome 後，您可以在單一工作流程中鏈接瀏覽器操作與編碼任務：

* **即時除錯**：直接讀取控制台錯誤和 DOM 狀態，然後修復導致它們的程式碼
* **設計驗證**：從 Figma 模型建立 UI，然後在瀏覽器中開啟以驗證它是否相符
* **網頁應用程式測試**：測試表單驗證、檢查視覺回歸或驗證使用者流程
* **已驗證的網頁應用程式**：與 Google Docs、Gmail、Notion 或您已登入的任何應用程式互動，無需 API 連接器
* **資料提取**：從網頁中提取結構化資訊並將其儲存在本地
* **任務自動化**：自動化重複的瀏覽器任務，如資料輸入、表單填充或多網站工作流程
* **檔案上傳**：將您電腦上的檔案附加到網頁上的上傳欄位
* **工作階段錄製**：將瀏覽器互動錄製為 GIF，以記錄或分享發生的情況

## 先決條件

在使用 Claude Code 與 Chrome 之前，您需要：

* [Google Chrome](https://www.google.com/chrome/)、[Microsoft Edge](https://www.microsoft.com/edge) 或其他基於 Chromium 的瀏覽器，例如 Brave、Arc、Vivaldi 或 Opera
* [Claude in Chrome 擴充功能](https://chromewebstore.google.com/detail/claude/fcoeoabgfenejglbffodgkkbkcdhcgfn) 版本 1.0.36 或更高版本，可在 Chrome Web Store 中取得
* [Claude Code](https://code.claude.com/docs/zh-TW/quickstart.md#step-1-install-claude-code)
* 直接 Anthropic 計畫（Pro、Max、Ultra、Team 或 Enterprise）

在已啟用 HIPAA 的 Enterprise 組織中，Claude in Chrome 預設為關閉，[Owner](https://code.claude.com/docs/zh-TW/server-managed-settings.md#access-control) 可以在 [**Organization settings > Claude in Chrome**](https://claude.ai/admin-settings/browser-extension) 中將其開啟。您與 Anthropic 簽訂的商業夥伴協議（BAA）不涵蓋透過 Claude in Chrome 傳送至第三方網站的資料。如需 Eligible Services 清單，請參閱 [Implementation Guide](https://trust.anthropic.com/resources?s=l1wrssd9hsbi4gak0tp5a6\&name=%5Banthropic%5D-hipaa-ready-offering-implementation-guide)。

Chrome 整合還需要使用 `/login` 登入。如果您使用 API 金鑰或來自 [`claude setup-token`](https://code.claude.com/docs/zh-TW/authentication#generate-a-long-lived-token) 的長期 token 進行身分驗證，即使您傳入 `--chrome`，Claude Code 也會保持 Chrome 整合關閉。瀏覽器擴充功能無法使用這些憑證進行身分驗證。

> [!NOTE]
>
> Chrome 整合不適用於 Amazon Bedrock、Google Cloud 的 Agent Platform 或 Microsoft Foundry 等第三方提供商。如果您只透過第三方提供商存取 Claude，則需要單獨的 claude.ai 帳戶才能使用此功能。

## 在 CLI 中開始使用

**1. 使用 Chrome 啟動 Claude Code**

使用 `--chrome` 旗標啟動 Claude Code：

```bash theme={null}
claude --chrome
```

首次搭配 Chrome 啟動時，Claude Code 會顯示一次性的對話方塊，介紹此整合功能並說明網站權限的運作方式。按 Enter 繼續。

若要在未來的工作階段中不使用旗標即可啟用 Chrome，請參閱[預設啟用 Chrome](#enable-chrome-by-default)。

**2. 請 Claude 使用瀏覽器**

此範例會導覽至某個頁面、與其互動，並回報找到的內容，全部都在您的終端機或編輯器中完成：

```text wrap theme={null}
Go to code.claude.com/docs, click on the search box,
type "hooks", and tell me what results appear
```

如果 Claude Code 在執行瀏覽器動作前要求權限，請予以核准。該對話方塊以 `Claude in Chrome wants to` 開頭，並提供在此工作階段中允許該網站所有動作的選項。Claude 會開啟新分頁並開始執行任務。

隨時執行 `/chrome` 即可檢查連線狀態、管理權限、重新連接擴充功能，或選擇要使用哪個已連接的瀏覽器。當狀態面板顯示「狀態：已啟用」以及「擴充功能：已安裝」時，即表示整合功能正常運作。

如果連接了多個瀏覽器，您可以選擇 Claude 要使用哪一個。若在您做出選擇之前就開始執行瀏覽器動作，Claude 會提示您選擇一個。若之後要切換瀏覽器，請執行 `/chrome` 並選取 **Select browser…**。即使有其他瀏覽器連接，Claude 也會持續使用您所選擇的瀏覽器。

若為 VS Code，請參閱 [VS Code 中的瀏覽器自動化](https://code.claude.com/docs/zh-TW/vs-code.md#automate-browser-tasks-with-chrome)。

### 在 Claude 要求時安裝擴充功能

當 Claude 在互動式工作階段中需要使用您的瀏覽器，而 Claude Code 未偵測到擴充功能時，Claude Code 會顯示標題為「Claude wants to use your browser」的安裝提示。Claude Code 每個工作階段最多詢問一次。

該提示提供三個選項：

* **Install extension**：在您的瀏覽器中開啟擴充功能安裝頁面，並開始引導式設定。Claude Code 會等待安裝完成、連接擴充功能，並在同一個工作階段中啟用瀏覽器工具。連線就緒後，選取「Continue with browser tools」，Claude 便會在您的瀏覽器中繼續執行任務。您可以選取「Continue without browser tools」離開設定，稍後再使用 `/chrome` 完成。
* **Not now**：在不使用瀏覽器工具的情況下繼續執行任務。Claude Code 可能會在之後的工作階段中再次詢問。
* **Don't ask again**：在未來的工作階段中不再顯示此提示。您仍可隨時使用 `/chrome` 設定此整合功能。

有兩項受管 MCP 政策會關閉此提示：

* 如果您的組織使用 [`deniedMcpServers` 受管設定](https://code.claude.com/docs/zh-TW/managed-mcp#policy-based-control-with-allowlists-and-denylists)封鎖 `claude-in-chrome` MCP 伺服器，Claude Code 不會顯示安裝提示。
* 如果您的組織部署了 [`managed-mcp.json`](https://code.claude.com/docs/zh-TW/managed-mcp#exclusive-control-with-managed-mcp-json) 檔案，但未[允許 Claude in Chrome 與受管集合並存](https://code.claude.com/docs/zh-TW/managed-mcp.md#allow-claude-in-chrome-alongside-the-managed-set)，Claude Code 不會顯示安裝提示。

### 預設啟用 Chrome

若要連接 Chrome 而不必每次都傳入 `--chrome`，請在 CLI 工作階段中執行 `/chrome` 並選取**預設啟用**。在 [VS Code 擴充功能](https://code.claude.com/docs/zh-TW/vs-code.md#automate-browser-tasks-with-chrome)中，於提示詞輸入框中輸入 `/chrome` 並開啟**預設啟用**開關。兩者共用同一個設定，因此在任一處開啟，都會同時對 CLI 與 VS Code 生效。

在開啟此設定且使用 Claude Code v2.1.287 或更新版本時，每個 VS Code 工作階段都會在啟動時連接到您的瀏覽器，因此 Claude 在您輸入 `@browser` 之前就能使用它。在較早的版本中，或在此設定關閉時，VS Code 工作階段會在您輸入 `@browser` 時才連接。

當 Chrome 未執行時，Claude Code 會正常啟動。

> [!NOTE]
>
> 預設啟用 Chrome 會增加上下文使用量，因為瀏覽器工具及其指示會一直處於載入狀態。如果您發現上下文消耗增加，請關閉此設定，僅在需要時連接：在 CLI 中使用 `--chrome`，或在 VS Code 提示詞輸入框中輸入 [`@browser`](https://code.claude.com/docs/zh-TW/vs-code#automate-browser-tasks-with-chrome)。

### 回應啟動對話方塊

如果啟動 `claude` 時出現「Claude in Chrome extension detected」對話方塊，您的回答會變更[**預設啟用**設定](#enable-chrome-by-default)：

* **Yes, use my browser**：開啟此設定並連接此工作階段
* **No, keep browser tools off**，或按 Esc：關閉此設定，且 Claude Code 將不再提議設定 Chrome

若要為之後的工作階段變更您的回答，請執行 `/chrome`。

### 管理網站權限

網站層級的權限繼承自 Chrome 擴充功能。請在 Chrome 擴充功能設定中管理權限，以控制 Claude 可以在哪些網站上瀏覽、點擊和輸入。在[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)中，當自動模式分類器本身核准了對某個網站的瀏覽器呼叫時，擴充功能會針對該次呼叫略過其自身的逐網站檢查，除非您的權限規則拒絕 Claude in Chrome 存取任何網站。

### VS Code 工作階段中的權限提示

在 VS Code 工作階段中，當 Claude Code 在執行瀏覽器動作前進行詢問時，權限提示會以卡片形式顯示在聊天面板中。當動作的目標是您尚未允許的網站時，該卡片也會提供允許該網站的選項。

在因為開啟了[預設啟用](#enable-chrome-by-default)而於啟動時連接到您瀏覽器的工作階段中，在手動、自動編輯、自動以及略過權限模式下，Claude Code 都會在對您尚未允許的網站執行瀏覽器動作前詢問您。在自動與略過權限模式下，此行為會持續到您在該工作階段中輸入 `@browser` 為止。

### plan mode 中的瀏覽器工具

在 [plan mode](https://code.claude.com/docs/zh-TW/permission-modes.md#analyze-before-you-edit-with-plan-mode) 中，Claude 錄製 GIF、開啟新分頁或執行捷徑之前，會出現權限提示。在互動式 CLI 工作階段中，如果[略過權限模式可用](https://code.claude.com/docs/zh-TW/permission-modes.md#skip-all-checks-with-bypasspermissions-mode)且[功能旗標擷取](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)已關閉，這些呼叫會在沒有提示的情況下執行。

設定了 `createIfEmpty` 的 `tabs_context_mcp` 呼叫也會出現提示，包含上述任一動作的 `browser_batch` 呼叫亦同。

## 範例工作流程

這些範例展示了將瀏覽器操作與編碼任務結合的常見方式。執行 `/mcp`，選擇 `claude-in-chrome`，然後選擇 **View tools** 以查看可用瀏覽器工具的完整清單。

### 測試本地網頁應用程式

開發網頁應用程式時，要求 Claude 驗證您的變更是否正確運作：

```text wrap theme={null}
I just updated the login form validation. Can you open localhost:3000,
try submitting the form with invalid data, and check if the error
messages appear correctly?
```

Claude 導航到您的本地伺服器、與表單互動並報告其觀察結果。

### 使用控制台日誌進行除錯

Claude 可以讀取控制台輸出以幫助診斷問題。告訴 Claude 要尋找的模式，而不是要求所有控制台輸出，因為日誌可能很冗長：

```text wrap theme={null}
Open the dashboard page and check the console for any errors when
the page loads.
```

Claude 讀取控制台訊息，可以篩選特定模式或錯誤類型。

### 自動填充表單

加快重複資料輸入任務的速度：

```text wrap theme={null}
I have a spreadsheet of customer contacts in contacts.csv. For each row,
go to the CRM at crm.example.com, click "Add Contact", and fill in the
name, email, and phone fields.
```

Claude 讀取您的本地檔案、導航網頁介面並為每筆記錄輸入資料。

### 上傳檔案到網頁

Claude 可以將您電腦上的檔案附加到頁面上的上傳欄位。Claude Code 會讀取檔案並將其內容傳送到瀏覽器，因此上傳在本地和遠端工作階段中皆可運作。

此範例將日誌檔案附加到表單：

```text wrap theme={null}
Open the bug tracker at bugs.example.com, create a new issue,
and attach logs/session.log to it
```

如果 Claude 拒絕附加檔案或上傳失敗，請檢查以下原因：

* **權限**：只有在工作階段被允許讀取檔案時，Claude 才能上傳該檔案，因此拒絕對檔案進行 `Read` 存取的[權限規則](https://code.claude.com/docs/zh-TW/settings-reference.md#permission-settings)也會阻止上傳該檔案。
* **大小**：單次上傳的檔案總計最多可達 10 MB。
* **硬連結**：Claude 會拒絕具有多個硬連結的檔案，這在 `node_modules` 等套件管理器儲存區中很常見。請複製該檔案並上傳副本。
* **憑證名稱**：如果檔案的名稱或所在資料夾屬於通常存放憑證的位置，例如 `.env`、`.pem` 或 `.key` 檔案，或 `.ssh` 下的任何內容，Claude 會拒絕該檔案。需要 Claude Code v2.1.293 或更新版本。

### 在 Google Docs 中起草內容

使用 Claude 直接在您的文件中寫入，無需 API 設定：

```text wrap theme={null}
Draft a project update based on the recent commits and add it to my
Google Doc at docs.google.com/document/d/abc123
```

Claude 開啟文件、點擊編輯器並輸入內容。這適用於您已登入的任何網頁應用程式：Gmail、Notion、Sheets 等。

### 從網頁中提取資料

從網站中提取結構化資訊：

```text wrap theme={null}
Go to the product listings page and extract the name, price, and
availability for each item. Save the results as a CSV file.
```

Claude 導航到頁面、讀取內容並將資料編譯成結構化格式。

### 執行多網站工作流程

協調多個網站之間的任務：

```text wrap theme={null}
Check my calendar for meetings tomorrow, then for each meeting with
an external attendee, look up their company website and add a note
about what they do.
```

Claude 跨標籤頁工作以收集資訊並完成工作流程。

### 錄製演示 GIF

建立瀏覽器互動的可共享錄製：

```text wrap theme={null}
Record a GIF showing how to complete the checkout flow, from adding
an item to the cart through to the confirmation page.
```

Claude 錄製互動序列並將其儲存為 GIF 檔案。錄製內容會擷取瀏覽器中所有可見的內容，包括已登入頁面上的帳戶詳細資料，因此在與團隊以外的人分享之前，請先檢查錄製內容。

### 將螢幕截圖儲存到磁碟

要求 Claude 將螢幕截圖保留為檔案：

```text wrap theme={null}
Take a screenshot of the checkout page and save it to disk
```

Claude 會將圖片儲存到磁碟並回報檔案路徑。

## 疑難排解

### 未偵測到擴充功能

如果 Claude Code 無法偵測到 Chrome 擴充功能：

1. 驗證 Chrome 擴充功能已安裝並在 `chrome://extensions` 中啟用
2. 透過執行 `claude --version` 驗證 Claude Code 是否為最新版本
3. 檢查 Chrome 是否正在執行
4. 執行 `/chrome` 並選擇「重新連接擴充功能」以重新建立連接
5. 如果問題仍然存在，請重新啟動 Claude Code 和 Chrome

第一次啟用 Chrome 整合時，Claude Code 會安裝原生訊息主機設定檔。Chrome 在啟動時讀取此檔案，因此如果擴充功能在您的第一次嘗試中未被偵測到，請重新啟動 Chrome 以取得新設定。

Claude Code 只會在第一次安裝時開啟瀏覽器標籤頁，提示您連接擴充功能。當稍後的工作階段重寫設定檔時（例如在切換建置或設定目錄後），Claude Code 不會重新開啟它。

如果連接仍然失敗，請驗證主機設定檔是否存在於：

對於 Chrome：

* **macOS**：`~/Library/Application Support/Google/Chrome/NativeMessagingHosts/com.anthropic.claude_code_browser_extension.json`
* **Linux**：`~/.config/google-chrome/NativeMessagingHosts/com.anthropic.claude_code_browser_extension.json`
* **Windows**：在 Windows 登錄中檢查 `HKCU\Software\Google\Chrome\NativeMessagingHosts\`

對於 Edge：

* **macOS**：`~/Library/Application Support/Microsoft Edge/NativeMessagingHosts/com.anthropic.claude_code_browser_extension.json`
* **Linux**：`~/.config/microsoft-edge/NativeMessagingHosts/com.anthropic.claude_code_browser_extension.json`
* **Windows**：在 Windows 登錄中檢查 `HKCU\Software\Microsoft\Edge\NativeMessagingHosts\`

其他基於 Chromium 的瀏覽器會從各自以瀏覽器命名的設定目錄中讀取相同的檔案。例如，macOS 上的 Brave 使用 `~/Library/Application Support/BraveSoftware/Brave-Browser/NativeMessagingHosts/`，而在 Windows 上，每個瀏覽器都有自己的登錄機碼，例如 `HKCU\Software\BraveSoftware\Brave-Browser\NativeMessagingHosts\`。

### 專案設定無法開啟 Chrome

終端機中出現此警告，表示您正在使用的專案嘗試開啟 Chrome 整合，而 Claude Code 不允許：

```text wrap theme={null}
Claude Code ignored CLAUDE_CODE_ENABLE_CFC in this project's settings: a project can't turn on Claude in Chrome. To turn it on yourself, run /chrome or start with --chrome.
```

該專案的 `.claude/settings.json` 或 `.claude/settings.local.json` 在其 `env` 區塊中將 [`CLAUDE_CODE_ENABLE_CFC`](https://code.claude.com/docs/zh-TW/env-vars#variables) 設為 `1`，以開啟 Chrome 整合。Claude Code 並未套用該設定，因此此工作階段中的 Chrome 整合處於關閉狀態，Claude 沒有瀏覽器工具。

Claude Code 會略過此設定，因為這些檔案儲存在專案目錄中，而您簽出的儲存庫不應能夠將 Claude 連接到您的瀏覽器。

您可以照常繼續工作。如果您想要使用瀏覽器工具，或希望警告消失，請執行下列其中一項：

* **立即取得瀏覽器工具**：結束後在 shell 中以 `claude --chrome` 重新啟動。
* **在之後的工作階段中取得瀏覽器工具**：在 Claude Code 提示字元中執行 `/chrome`，並選擇[**預設啟用**](#enable-chrome-by-default)。這會套用於之後啟動的工作階段，而不是目前正在執行的工作階段。
* **停止警告且不使用瀏覽器工具**：從專案的設定檔中移除 `CLAUDE_CODE_ENABLE_CFC` 這一行。

### 瀏覽器無回應

如果 Claude 的瀏覽器命令停止工作：

1. 檢查是否有模態對話框（警告、確認、提示）阻止頁面。JavaScript 對話框會阻止瀏覽器事件並防止 Claude 接收命令。手動關閉對話框，然後告訴 Claude 繼續。
2. 要求 Claude 建立新標籤頁並重試
3. 透過在 `chrome://extensions` 中停用並重新啟用 Chrome 擴充功能來重新啟動它

### 長工作階段期間連接中斷

Chrome 擴充功能的服務工作者可能在延長的工作階段期間進入閒置狀態，這會中斷連接。如果瀏覽器工具在一段時間不活動後停止工作，請執行 `/chrome` 並選擇「重新連接擴充功能」。

執行 `/chrome` 時，請查看其 `Status` 行。如果顯示「Not connected」，表示目前執行中的工作階段本身與 Chrome 的連接已失敗。選擇「重新連接擴充功能」以重新啟動該連接。連接成功後，擴充功能的重新連接頁面會在 Chrome 中開啟。在 v2.1.290 之前，「重新連接擴充功能」只會開啟該頁面，而不會重新啟動失敗的連接，因此如果在較早版本上瀏覽器工具沒有恢復，請更新 Claude Code。

### 擴充功能登入了不同的組織

如果您隸屬於多個 claude.ai 組織，擴充功能必須登入與 Claude Code 相同的組織。如果兩者不同，即使兩者使用相同的 claude.ai 帳戶，Claude 的瀏覽器工具也會回傳「Browser extension is not connected」。

若要查看 Claude Code 登入的是哪個組織，請在 Claude Code 提示字元中執行 [`/status`](https://code.claude.com/docs/zh-TW/commands)，並查看 `Organization` 列。

> [!WARNING]
>
> 如果您登出擴充功能，將會失去儲存在其中的捷徑和排程任務。請先嘗試[常見錯誤訊息](#common-error-messages)下的其他修復方法。

若要變更擴充功能的組織，請在擴充功能的設定中登出，然後登入並選擇 `/status` 所顯示的組織。

### Windows 特定問題

在 Windows 上，您可能會遇到：

* **命名管道衝突 (EADDRINUSE)**：如果另一個程序正在使用相同的命名管道，請重新啟動 Claude Code。關閉任何可能使用 Chrome 的其他 Claude Code 工作階段。
* **原生訊息主機錯誤**：如果原生訊息主機在啟動時崩潰，請嘗試重新安裝 Claude Code 以重新產生主機設定。
* **設定頁面無法開啟**：請更新 Claude Code。在 v2.1.211 之前，提示您連接擴充功能的瀏覽器標籤頁在 Windows 上可能無法開啟。

### 常見錯誤訊息

以下是最常遇到的錯誤及其解決方法：

| 錯誤 | 原因 | 修復 |
| - | - | - |
| 「Browser extension is not connected」 | 擴充功能未在 Chrome 中安裝並執行、擴充功能登入的 claude.ai 帳戶或組織與 Claude Code 不同，或您組織的 IP 允許清單拒絕了與 `bridge.claudeusercontent.com` 的連接 | 檢查擴充功能是否已登入與 Claude Code 相同的 claude.ai 帳戶和[組織](#extension-signed-in-to-a-different-organization)，重新啟動 Chrome 和 Claude Code，然後執行 `/chrome` 以重新連接。如果您的組織使用 IP 允許清單且錯誤仍然存在，請參閱[組織 IP 允許清單與代理伺服器出口流量](https://code.claude.com/docs/zh-TW/network-config.md#organization-ip-allowlists-and-proxy-egress) |
| 擴充功能在 `/chrome` 中顯示「未偵測到」 | Chrome 擴充功能未安裝或已停用 | 在 `chrome://extensions` 中安裝或啟用擴充功能 |
| 「沒有可用的標籤頁」 | Claude 在標籤頁準備好之前嘗試操作 | 要求 Claude 建立新標籤頁並重試 |
| 「接收端不存在」 | 擴充功能服務工作者進入閒置狀態 | 執行 `/chrome` 並選擇「重新連接擴充功能」 |
| 「No browsers are connected」 | Chrome 未開啟，或擴充功能登入的 claude.ai 帳戶和組織與 Claude Code 不同，或 Claude Code 無法連線至 `bridge.claudeusercontent.com` | 確認 Chrome 已開啟，且擴充功能已登入與 Claude Code 相同的 claude.ai 帳戶和[組織](#extension-signed-in-to-a-different-organization)。若是如此，請檢查您的網路是否允許 Claude Code 連線至 `bridge.claudeusercontent.com`，該位址列於[網路存取需求](https://code.claude.com/docs/zh-TW/network-config.md#network-access-requirements)中 |

## 另請參閱

* [電腦使用](https://code.claude.com/docs/zh-TW/computer-use.md)：當任務無法在瀏覽器中完成時控制原生 macOS 應用程式
* [在 VS Code 中使用 Claude Code](https://code.claude.com/docs/zh-TW/vs-code.md#automate-browser-tasks-with-chrome)：VS Code 擴充功能中的瀏覽器自動化
* [CLI 參考](https://code.claude.com/docs/zh-TW/cli-reference.md)：命令列標誌，包括 `--chrome`
* [常見工作流程](https://code.claude.com/docs/zh-TW/common-workflows.md)：更多使用 Claude Code 的方式
* [資料和隱私](https://code.claude.com/docs/zh-TW/data-usage.md)：Claude Code 如何處理您的資料
* [Claude in Chrome 入門](https://support.claude.com/en/articles/12012173-getting-started-with-claude-in-chrome)：Chrome 擴充功能的完整文件，包括快捷鍵、排程和權限

<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/computer-use | lastmod: 2026-10-30 | section: Getting started / Platforms and integrations -->
> 來源：https://code.claude.com/docs/zh-TW/computer-use（官方 zh-TW，lastmod 2026-10-30）｜分類：Getting started › Platforms and integrations｜EN 摘要：Enable computer use in the Claude Code CLI so Claude can open apps, click, type, and see your screen on macOS. Test native apps, debug visual issues, and automate GUI-only tools without leaving your terminal.

# 讓 Claude 從 CLI 使用您的電腦

> 在 Claude Code CLI 中啟用 computer use，讓 Claude 可以在 macOS 上開啟應用程式、點擊、輸入和查看您的螢幕。測試原生應用程式、除錯視覺問題，以及自動化僅限 GUI 的工具，無需離開您的終端機。

> [!NOTE]
>
> Computer use 是 macOS 上的研究預覽版本，需要 Pro、Max 或 Ultra 方案。Team 或 Enterprise 方案不提供此功能。它需要互動式工作階段，因此在使用 `-p` 旗標的非互動模式中不可用。

Computer use 讓 Claude 可以開啟應用程式、控制您的螢幕，並以您的方式在您的機器上工作。從 CLI，Claude 可以編譯 Swift 應用程式、啟動它、點擊每個按鈕，並擷取結果的螢幕截圖，所有這些都在編寫程式碼的同一個對話中進行。

本頁涵蓋 computer use 在 CLI 中的運作方式。如需 Desktop 應用程式，請參閱 [Desktop 中的 computer use](https://code.claude.com/docs/zh-TW/desktop.md#let-claude-use-your-computer)。

## 您可以使用 computer use 做什麼

Computer use 處理需要 GUI 的任務：任何您通常必須離開終端機並手動執行的操作。

* **建置和驗證原生應用程式**：要求 Claude 建置 macOS 選單列應用程式。Claude 編寫 Swift、編譯它、啟動它，並點擊每個控制項以驗證它在您開啟之前是否有效。
* **端對端 UI 測試**：將 Claude 指向本機 Electron 應用程式並說「測試上線流程」。Claude 開啟應用程式、點擊註冊，並擷取每個步驟的螢幕截圖。無需 Playwright 設定、無需測試工具。
* **除錯視覺和版面配置問題**：告訴 Claude「模態視窗在小視窗上被裁剪」。Claude 調整視窗大小、重現錯誤、擷取螢幕截圖、修補 CSS，並驗證修復。Claude 看到您看到的內容。
* **驅動僅限 GUI 的工具**：與設計工具、硬體控制面板、iOS 模擬器或沒有 CLI 或 API 的專有應用程式互動。

## Computer use 何時適用

Claude 有多種方式與應用程式或服務互動。Computer use 是最廣泛和最慢的，因此 Claude 首先嘗試最精確的工具：

* 如果您有該服務的 [MCP server](https://code.claude.com/docs/zh-TW/mcp.md)，Claude 會使用它。
* 如果任務是 shell 命令，Claude 會使用 Bash。
* 如果任務是瀏覽器工作且您已設定 [Claude in Chrome](https://code.claude.com/docs/zh-TW/chrome.md)，Claude 會使用它。
* 如果以上都不適用，Claude 會使用 computer use。

螢幕控制保留用於其他工具無法到達的事物：原生應用程式、模擬器（例如 iOS Simulator）和沒有 API 的工具。

## 啟用 computer use

Computer use 可作為稱為 `computer-use` 的內建 MCP server 使用。預設情況下它是關閉的，直到您啟用它。

**1. 開啟 MCP 選單**

在互動式 Claude Code 工作階段中，執行：

```text theme={null}
/mcp
```

在伺服器清單中找到 `computer-use`。它顯示為已停用。

**2. 啟用伺服器**

選擇 `computer-use` 並選擇**啟用**。該設定按專案保留，因此您只需為每個想要 computer use 的專案執行一次。

**3. 授予 macOS 權限**

Claude 第一次嘗試使用您的電腦時，您會看到授予兩個 macOS 權限的提示：

* **Accessibility**：讓 Claude 點擊、輸入和捲動
* **Screen Recording**：讓 Claude 看到您螢幕上的內容

提示包含開啟相關系統設定窗格的連結。授予兩者，然後在提示中選擇**重試**。授予螢幕錄製權限後，macOS 可能需要您重新啟動 Claude Code。

設定後，要求 Claude 執行需要 GUI 的操作：

```text theme={null}
建置應用程式目標、啟動它，並點擊每個標籤以確保
沒有任何內容崩潰。擷取您找到的任何錯誤狀態的螢幕截圖。
```

## 依工作階段核准應用程式

啟用 `computer-use` 伺服器並不會讓 Claude 存取您電腦上的每個應用程式。在工作階段中，Claude 第一次需要使用特定應用程式時，您的終端機會顯示權限提示，內容包括：

* Claude 想要控制哪些應用程式
* 所請求的任何額外權限，例如剪貼簿存取
* Claude 工作期間將隱藏多少其他應用程式

選擇 **Allow for this session** 或 **Deny**。核准在目前的工作階段內有效。當 Claude 同時請求多個應用程式時，您可以一次核准它們。

影響範圍廣泛的應用程式會在權限提示中顯示額外警告，讓您了解核准它們會授予哪些權限：

| 警告 | 適用對象 |
| :- | :- |
| 等同於 shell 存取 | Terminal、iTerm、VS Code、Warp 及其他終端機和 IDE |
| 可讀取或寫入任何檔案 | Finder |
| 可變更系統設定 | System Settings |

這些應用程式並未遭到封鎖。此警告讓您自行判斷該任務是否值得授予這種層級的存取權限。

核准 Finder 即可讓 Claude 點按桌面、Dock 或 Finder 視窗。

Claude 的控制層級也會因應用程式類別而異：瀏覽器和交易平台僅供檢視，終端機和 IDE 僅限點按，其他所有應用程式則享有完整控制權。如需完整的層級說明，請參閱 [Desktop 中的應用程式權限](https://code.claude.com/docs/zh-TW/desktop.md#app-permissions)。

## Claude 如何在您的螢幕上工作

了解流程有助於您預期 Claude 將執行的操作以及如何進行干預。

### 一次一個工作階段

一次只有一個工作階段可以使用您的電腦。工作階段在其第一個電腦使用操作時持有鎖定，並在工作階段退出時釋放它，而不是在任務完成時。第二個工作階段的電腦使用會失敗，並出現一個錯誤，指出持有鎖定的工作階段。先退出該工作階段。

### Claude 工作時應用程式被隱藏

當 Claude 開始控制您的螢幕時，其他可見的應用程式會被隱藏，以便 Claude 只與已核准的應用程式互動。您的終端機視窗保持可見並從螢幕截圖中排除，因此您可以觀看工作階段，Claude 永遠看不到自己的輸出。

當 Claude 完成該輪次時，隱藏的應用程式會自動恢復。

### 螢幕截圖會自動縮小

Claude Code 在將每個螢幕截圖傳送到模型之前會自動縮小它。您不需要降低顯示解析度或在 Retina 或其他高解析度顯示器上調整視窗大小。16 吋 MacBook Pro 以原生 Retina 解析度擷取 3456×2234，並縮小到大約 1372×887，保持寬高比。

沒有設定可以變更目標大小。如果螢幕上的文字或控制項在縮小後對 Claude 來說太小而無法讀取，請增加應用程式中的大小，而不是變更您的顯示解析度。

### 隨時停止

Claude 在每個輪次中首次使用您的電腦時，會出現 macOS 通知：「Claude 正在使用您的電腦 · 按 Esc 停止」。在任何地方按 `Esc` 立即中止目前操作，或在終端機中按 `Ctrl+C`。無論哪種方式，Claude 都會停止、取消隱藏您的應用程式，並將控制權返回給您。工作階段會保持 [computer use 鎖定](#one-session-at-a-time)，直到它退出。

Claude 完成時會出現第二個通知。

## 安全性和信任邊界

> [!WARNING]
>
> 與 [沙箱化 Bash 工具](https://code.claude.com/docs/zh-TW/sandboxing.md)不同，computer use 在您的實際桌面上執行，可以存取您核准的應用程式。Claude 檢查每個操作並標記來自螢幕上內容的潛在提示注入，但信任邊界是不同的。請參閱 [computer use 安全指南](https://support.claude.com/en/articles/14128542)以了解最佳實踐。

內建護欄在不需要設定的情況下降低風險：

* **按應用程式核准**：Claude 只能控制您在目前工作階段中已核准的應用程式。
* **哨兵警告**：授予 shell、檔案系統或系統設定存取的應用程式在您核准之前會被標記。
* **終端機從螢幕截圖中排除**：Claude 永遠看不到您的終端機視窗，因此您工作階段中的螢幕上提示無法反饋到模型中。
* **全域逃脫**：`Esc` 鍵可以從任何地方中止 computer use，並且按鍵被消耗，因此提示注入無法使用它來關閉對話框。
* **鎖定檔案**：一次只有一個工作階段可以控制您的機器。

## 範例工作流程

這些範例顯示將 computer use 與編碼任務結合的常見方式。

### 驗證原生建置

對 macOS 或 iOS 應用程式進行變更後，讓 Claude 在一次通過中編譯和驗證：

```text theme={null}
建置 MenuBarStats 目標、啟動它、開啟偏好設定視窗，
並驗證間隔滑塊更新標籤。完成後擷取偏好設定視窗的螢幕截圖。
```

Claude 執行 `xcodebuild`、啟動應用程式、與 UI 互動，並報告它發現的內容。

### 重現版面配置錯誤

當視覺錯誤僅在特定視窗大小出現時，讓 Claude 找到它：

```text theme={null}
設定模態視窗在狹窄視窗上裁剪其頁尾。調整應用程式
視窗大小直到您可以重現它、擷取裁剪狀態的螢幕截圖，
然後檢查模態容器的 CSS。
```

Claude 調整視窗大小、擷取損壞的狀態，並讀取相關的樣式表。

### 測試模擬器流程

無需編寫 XCTest 即可驅動 iOS 模擬器：

```text theme={null}
開啟 iOS 模擬器、啟動應用程式、點擊上線螢幕，
並告訴我是否有任何螢幕花費超過一秒鐘的時間來載入。
```

Claude 以您使用滑鼠的方式控制模擬器。此流程適用於 CLI；在 Desktop 應用程式中，相同的請求會開啟 [iOS Simulator 窗格](https://code.claude.com/docs/zh-TW/desktop-ios-simulator.md)，而不是螢幕控制。

## 與 Desktop 應用程式的差異

CLI 和 Desktop 表面共享相同的 computer use 引擎，有一些差異：

| 功能 | Desktop | CLI |
| :- | :- | :- |
| 平台 | macOS 和 Windows | 僅 macOS |
| 啟用 | 在[設定](https://code.claude.com/docs/zh-TW/desktop.md#enable-computer-use)中切換 | 在 `/mcp` 中啟用 `computer-use` |
| 拒絕的應用程式清單 | 可在設定中設定 | 尚不可用 |
| 自動取消隱藏切換 | 可選 | 始終開啟 |
| Dispatch 整合 | Dispatch 生成的工作階段可以使用 computer use | 不適用 |

## 疑難排解

### "Computer use is in use by another Claude session"

另一個 Claude Code 工作階段持有鎖定，它會一直保持到該工作階段退出為止。退出該工作階段。如果另一個工作階段崩潰，當 Claude 偵測到該程序不再執行時，鎖定會自動釋放。

### macOS 權限提示不斷重新出現

授予螢幕錄製權限後，macOS 有時需要重新啟動請求程序。完全退出 Claude Code 並啟動新工作階段。如果提示仍然存在，開啟**系統設定 > 隱私與安全 > 螢幕錄製**並確認您的終端機應用程式已列出並啟用。

### `computer-use` 未出現在 `/mcp` 中

伺服器僅在符合條件的設定上出現。檢查：

* 您在 macOS 上。Computer use 在 CLI 中不適用於 Linux 或 Windows。在 Windows 上，請改用 [Desktop 中的 computer use](https://code.claude.com/docs/zh-TW/desktop.md#let-claude-use-your-computer)。
* 您使用的是 Pro、Max 或 Ultra 方案。執行 `/status` 以確認您的訂閱。
* 您透過 claude.ai 進行身份驗證。Computer use 不適用於 Amazon Bedrock、Google Cloud 的 Agent Platform 或 Microsoft Foundry 等第三方提供者。如果您完全透過第三方提供者存取 Claude，您需要單獨的 claude.ai 帳戶才能使用此功能。
* 您在互動式工作階段中。Computer use 在使用 `-p` 旗標的非互動模式中不可用。

## 另請參閱

* [Desktop 中的 Computer use](https://code.claude.com/docs/zh-TW/desktop.md#let-claude-use-your-computer)：具有圖形設定頁面的相同功能
* [Claude in Chrome](https://code.claude.com/docs/zh-TW/chrome.md)：用於基於網路的任務的瀏覽器自動化
* [MCP](https://code.claude.com/docs/zh-TW/mcp.md)：將 Claude 連接到結構化工具和 API
* [Sandboxing](https://code.claude.com/docs/zh-TW/sandboxing.md)：Claude 的 Bash 工具如何隔離檔案系統和網路存取
* [Computer use 安全指南](https://support.claude.com/en/articles/14128542)：安全 computer use 的最佳實踐

<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/desktop-ios-simulator | lastmod: 2026-10-30 | section: Getting started / Platforms and integrations -->
> 來源：https://code.claude.com/docs/zh-TW/desktop-ios-simulator（官方 zh-TW，lastmod 2026-10-30）｜分類：Getting started › Platforms and integrations｜EN 摘要：Claude Code Desktop opens your app in the iOS Simulator pane when Claude builds, runs, or checks it, with a separate simulator for each session.

# 在模擬器中測試 iOS 應用程式

> Claude Code Desktop 在 Claude 建置、執行或檢查應用程式時，會在 iOS Simulator 窗格中開啟您的應用程式，每個工作階段都有一個獨立的模擬器。

> [!NOTE]
>
> iOS Simulator 窗格在 macOS 上的 Claude Code Desktop 中處於公開測試版。它在 Pro、Max、Ultra、Team 和 Enterprise 方案上可用，但在啟用 HIPAA 設定的 Enterprise 組織中除外。

iOS Simulator 窗格在 Claude Code Desktop 中的對話旁邊顯示您的應用程式在 Apple 的 iOS Simulator 中執行。當 Claude 在模擬器中建置、安裝、啟動或檢查您的應用程式時，窗格會自動開啟並即時串流裝置螢幕。使用它來觀看 Claude 執行和測試您的應用程式，或在 Claude 繼續工作時自己點選應用程式。

模擬器窗格直接驅動模擬器，因此不需要[電腦使用](https://code.claude.com/docs/zh-TW/desktop.md#let-claude-use-your-computer)，也不會接管您的螢幕或隱藏其他視窗。從 CLI，Claude 透過[電腦使用](https://code.claude.com/docs/zh-TW/computer-use.md#test-a-simulator-flow)到達 iOS Simulator，它以滑鼠的方式控制螢幕上的模擬器。

## 需求

模擬器窗格使用 Apple 的模擬器工具，桌面應用程式不包含這些工具。在開始工作階段之前，請確保您有：

* Claude Desktop v1.24012.0 或更新版本
* Mac，因為 Apple 的 iOS Simulator 只在 macOS 上執行
* [Xcode](https://developer.apple.com/xcode/)，已安裝 iOS 平台，提供模擬器裝置。如果 Xcode 尚未列出任何模擬器，請參閱[模擬器窗格顯示找不到模擬器](#the-simulator-pane-says-no-simulators-were-found)
  * 建議使用 Xcode 26.x 或 Xcode 27，窗格可與兩者搭配使用。如果您安裝了多個 Xcode，請參閱[選擇模擬器窗格使用的 Xcode](#choose-which-xcode-the-simulator-pane-uses)

> [!NOTE]
>
> 在本頁面上，「裝置」是指模擬的 iPhone 或 iPad，是您在 Xcode 中的 **Window → Devices and Simulators** 下管理的相同模擬器裝置之一，不是實體硬體。

模擬器窗格僅在本機工作階段中可用。在[雲端](https://code.claude.com/docs/zh-TW/desktop.md#run-long-running-tasks-in-the-cloud)和 [SSH](https://code.claude.com/docs/zh-TW/desktop.md#ssh-sessions) 工作階段中，Claude 在無法到達您 Mac 上模擬器的機器上執行。

### 選擇模擬器窗格使用的 Xcode

如果您安裝了多個 Xcode，例如 Xcode 26.x 與 Xcode 27 並行，窗格會使用 `xcode-select` 指向的任何一個。若要使用不同的安裝，請按其路徑選擇它。

例如，如果您想要的 Xcode 安裝為 `/Applications/Xcode-26.4.app`，請在終端機中執行此命令：

```bash theme={null}
sudo xcode-select -s /Applications/Xcode-26.4.app
```

然後結束並重新開啟 Claude Desktop，使窗格使用新選擇的 Xcode。

若要檢查選擇了哪個安裝，請執行 `xcode-select -p`。它會列印選擇的安裝的 Developer 資料夾，例如 `/Applications/Xcode-26.4.app/Contents/Developer`。

## 在模擬器中執行您的應用程式

您不需要命令或設定來開啟模擬器窗格。當 Claude 在模擬器中執行您的應用程式時，它會開啟窗格。

**1. 開啟您的 iOS 專案**

在 Claude Code Desktop 中，開啟 **Code** 標籤，並以您應用程式的專案作為[專案資料夾](https://code.claude.com/docs/zh-TW/desktop.md#start-a-session)開始工作階段。任何為 iOS Simulator 建置應用程式的專案都可以使用。

**2. 要求 Claude 執行或測試應用程式**

圍繞執行或驗證應用程式的任務進行表述。例如：

```text theme={null}
Build the app and run it in the simulator to check the onboarding flow.
```

**3. 在模擬器窗格中觀看應用程式**

當應用程式在模擬器中啟動時，iOS Simulator 窗格會在對話旁邊開啟。Claude 第一次使用裝置時，桌面應用程式會要求您允許；請參閱[授予 Claude 對裝置的存取權](#grant-claude-access-to-a-device)。Claude 安裝應用程式、點選應用程式，並讀取螢幕以驗證自己的變更，同時您觀看。

模擬器窗格在 Claude 在工作階段中的任何時間在模擬器中啟動應用程式時開啟。當您的要求是關於查看應用程式時，例如「新螢幕看起來對嗎？」，Claude 在開始工作之前啟動模擬器。Claude 修復錯誤或變更螢幕後，要求它驗證變更：重新啟動應用程式會在窗格未開啟時重新開啟窗格。

模擬器窗格顯示應用程式實際啟動的任何裝置。要在特定裝置上測試，在您的要求中命名它，例如「在 iPhone SE 模擬器上執行它」，Claude 在建置和啟動時會針對該裝置。

Claude 啟動的裝置也會出現在 Apple 的 Simulator 應用程式中，或在 Xcode 27 的 Device Hub 中。Claude 可以在您已經啟動的裝置上安裝應用程式。

您也可以自己開啟模擬器窗格。一旦工作階段已附加模擬器，或 Claude Code 偵測到 iOS 應用程式相關工作，工作階段的標題列中就會出現 **iOS Simulator** 按鈕。如果窗格尚未顯示裝置，請按一下 **Attach simulator**，或從旁邊的裝置功能表中選擇特定裝置；選擇已關閉的裝置會啟動它。如果 Xcode 或其模擬器遺失，窗格會改為顯示設定步驟，並在您完成每個步驟時將其勾選。

## 自己控制模擬器

模擬器窗格是互動式的，不僅是檢視器。在 Claude 工作時或在任務之間，您可以：

* 透過在裝置螢幕上按一下和拖曳來點選和滑動
* 使用與 Apple 的 Simulator 應用程式相同的快捷鍵按下硬體按鈕：**Cmd+Shift+H** 表示主畫面、**Cmd+L** 表示鎖定、**Cmd+Up Arrow** 和 **Cmd+Down Arrow** 表示音量
* 使用旋轉按鈕或 **Cmd+Right Arrow** 將裝置順時針旋轉四分之一圈
* 從裝置功能表切換窗格顯示的裝置，該功能表列出每個模擬器的作業系統版本以及是否已啟動
* 使用 **Cmd+S** 儲存螢幕擷圖或使用 **Cmd+R** 儲存螢幕錄製，使用窗格的擷取按鈕或快捷鍵；檔案會儲存到您的桌面
* 透過按一下 **Detach simulator** 停止串流裝置而不關閉它，這會將窗格返回其 **Attach simulator** 狀態

如果窗格顯示 **Display** 功能表，請使用它來調整來自模擬器的影片串流。如果窗格對您的 Mac 造成負擔，請降低 **Frame rate** 或 **Resolution**。這兩項設定會變更窗格顯示裝置的方式，而不是應用程式的執行方式。

您和 Claude 驅動相同的裝置，因此您的點選會變更 Claude 看到的應用程式狀態。要讓 Claude 檢查特定螢幕，請透過點選導航到它，然後要求。當 Claude 驅動裝置時，窗格會在螢幕上方顯示 **Claude is using this device** 徽章；在徽章清除之前暫停點選，以便結果反映應用程式而不是您的輸入。

## 工作階段如何管理裝置

每個裝置都屬於啟動它的工作階段，因此[平行工作階段](https://code.claude.com/docs/zh-TW/desktop.md#work-in-parallel-with-sessions)不共享裝置：您在一個工作階段的窗格中看到的內容反映該工作階段的工作，而不是另一個的。在側邊欄中切換工作階段會切換模擬器檢視以及對話，切換回去會在相同裝置上恢復它停止的位置。如果 Claude 使用多個裝置，每個都會開啟自己的窗格，每個工作階段最多 4 個。

Claude Code Desktop 在模擬器不再使用時關閉它啟動的模擬器：當您退出應用程式時、當您封存工作階段時，或在您從其窗格分離裝置後 10 分鐘。您在 Claude Code Desktop 之外啟動的裝置，例如在 Apple 的 Simulator 應用程式或 Device Hub 中啟動的裝置，永遠不會自動關閉。要立即關閉附加的裝置，請使用窗格中的關閉按鈕。

## 授予 Claude 對裝置的存取權

Claude 在控制裝置之前要求您的同意，而建置應用程式或在其上開啟 URL 遵循您工作階段的權限模式。您或您的組織也可以完全關閉 Claude 的存取。

### 第一次允許裝置

Claude 第一次使用模擬器時，桌面應用程式會要求您允許。同意涵蓋控制該裝置和擷取其螢幕擷圖，您每個裝置給予一次，而不是每個工作階段一次。Claude 對裝置的螢幕擷圖會傳送到 Anthropic，並根據您的正常對話保留設定保留，因此不要在 Claude 使用的裝置上登入真實帳戶。

您允許裝置後，Claude 對其的操作，例如點選、輸入、啟動應用程式和擷取螢幕擷圖，無需進一步提示即可執行。它們具有與您在窗格中按一下相同的信任，並且它們只觸及模擬的裝置，因此窗格不需要電腦使用所需的 macOS 無障礙和螢幕錄製權限。

如果您拒絕，裝置仍會啟動，窗格仍可用於您自己的點選；只有 Claude 的存取保持關閉。要稍後改變主意，請按一下窗格中的 **Let Claude use it**。

### 遵循您的權限模式的操作

兩個操作遵循您工作階段的[權限模式](https://code.claude.com/docs/zh-TW/permissions.md#permission-modes)，而不是一次性同意：

* 在裝置上開啟 URL，例如測試深層連結或在裝置的 Safari 中載入頁面，因為 URL 可以攜帶資料離開裝置。
* 建置應用程式，因為 `xcodebuild` 在您的 Mac 上執行您專案的建置指令碼。檢查已在進行中的建置不會提示。

### 關閉模擬器存取

您可以在桌面應用程式的設定中關閉 Claude 的模擬器存取。組織有兩種方式為所有人關閉它：

* `disableMobileSimulatorTools` [受管設定](https://code.claude.com/docs/zh-TW/desktop.md#managed-settings)阻止 Claude 的模擬器工具。模擬器窗格仍可用於您自己的點選，該設定無法從應用程式內覆寫。
* `requireCoworkFullVmSandbox` 原則金鑰，它在隔離的虛擬機器內而不是在您的 Mac 上執行 Claude 的工具，完全停用模擬器窗格和 Claude 的模擬器工具，因此在設定時窗格無法附加裝置。

Claude 會告訴您何時適用任一項。

## 限制

Claude 只驅動模擬的裝置，無法控制實體 iPhone 或 iPad。要在其上測試，請自己從 Xcode 在其上執行應用程式，然後描述您看到的內容或將螢幕擷圖附加到對話中，以便 Claude 從中工作。

## 疑難排解

### 當 Claude 執行應用程式時，模擬器窗格不開啟

Claude 可能沒有識別出您想要執行或測試應用程式，或模擬器工具可能遺失。檢查以下內容：

* 明確說明目標，例如「在 iOS Simulator 中執行應用程式並點選註冊流程」。
* 確認 Xcode 和 iOS 模擬器已安裝，且您的 Xcode 版本符合[需求](#requirements)。
* 如果您的組織管理 Claude Code，[模擬器工具可能被原則停用](#turn-off-simulator-access)。
* 如果您在啟用 HIPAA 設定的 Enterprise 組織中，模擬器窗格對您不可用。
* 模擬器窗格需要 Claude Desktop v1.24012.0 或更新版本。開啟 **Claude > Check for Updates…**，然後重新啟動應用程式。

### 模擬器窗格顯示找不到模擬器

Xcode 已安裝但沒有 iOS 模擬器可列出。模擬器窗格顯示要遵循的設定步驟，並在每個步驟完成時檢查它們。要手動安裝遺失的部分，請從 Xcode 的設定下載 iOS 模擬器執行時間，或執行 `xcodebuild -downloadPlatform iOS`。

## 另請參閱

* [Desktop 中的電腦使用](https://code.claude.com/docs/zh-TW/desktop.md#let-claude-use-your-computer)：沒有專用窗格的應用程式的螢幕控制
* [CLI 中的電腦使用](https://code.claude.com/docs/zh-TW/computer-use.md)：CLI 如何到達 iOS Simulator
* [在專屬 worktree 中執行工作階段](https://code.claude.com/docs/zh-TW/desktop.md#run-a-session-in-its-own-worktree)：工作階段如何隔離變更
* [開始使用 Claude Code Desktop](https://code.claude.com/docs/zh-TW/desktop-quickstart.md)

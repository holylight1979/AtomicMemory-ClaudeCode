<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/desktop-wsl | lastmod: 2026-10-19 | section: Getting started / Platforms and integrations -->
> 來源：https://code.claude.com/docs/zh-TW/desktop-wsl（官方 zh-TW，lastmod 2026-10-19）｜分類：Getting started › Platforms and integrations｜EN 摘要：Run Code sessions inside a WSL 2 distribution on Windows

# Claude Code Desktop in WSL

> 在 Windows 上的 WSL 2 發行版內執行 Code 工作階段

在 Windows 上，Code 標籤可以在 WSL 2 發行版內執行工作階段，而不是在 Windows 本身上執行。工作階段的 Claude Code 程序、其工具和 git 都在發行版內執行，使用其 Linux 工具鏈和原生 Linux 路徑，與您的專案所針對的環境相同。

當您的儲存庫位於發行版的檔案系統內時，請使用 WSL 工作階段。從 Windows 處理這些檔案會通過網路檔案系統，這很慢且會破壞檔案監視；在發行版內執行工作階段可以避免兩者。

## 需求

* Windows 10 或 11，搭配 [WSL 2](https://learn.microsoft.com/windows/wsl/install)。不支援 WSL 1。
* 至少一個已安裝的發行版（例如 Ubuntu）。
* 在發行版內安裝的 `git`。

## 啟動 WSL 工作階段

**1. 選擇發行版**

在 Code 標籤中啟動新工作階段，並開啟提示詞輸入框下方的[環境選擇器](https://code.claude.com/docs/zh-TW/desktop.md#start-a-session)；在[較早的版面配置](https://code.claude.com/docs/zh-TW/desktop.md#check-which-layout-you-have)中，它則位於輸入框上方。您已安裝的 WSL 2 發行版會出現在 **WSL** 區段中。選擇一個。

**2. 選擇資料夾**

工作階段在發行版的家目錄中啟動。使用資料夾選擇器選擇專案資料夾。瀏覽在發行版內進行，使用 Linux 路徑，例如 `/home/you/project`。

**3. 信任資料夾**

資料夾中的第一個工作階段會顯示工作區信任對話框。信任是按發行版和資料夾授予的。在一個發行版中信任的資料夾，在另一個發行版中或在 Windows 上的相同路徑中不會被信任。

發行版中的第一個工作階段需要花費一些時間，而 Claude 在其中進行設定。您也可以從一般資料夾選擇器開啟 `\\wsl.localhost\...` 資料夾，它會在該發行版內重新開啟。

## WSL 工作階段中的運作方式

平行工作階段、側邊聊天、視覺差異檢閱、分支和 pull request 狀態，以及 worktrees 都可以運作，由發行版內的 git 和工具鏈支援。「在編輯器中開啟」會開啟透過 [Remote - WSL](https://code.visualstudio.com/docs/remote/wsl) 連接到發行版的 VS Code。

如果某項 Desktop 功能在 WSL 工作階段中無法使用或受到限制，請檢查它是否屬於下列其中之一：

* **終端機和連接器**：您的工作階段可能缺少[整合終端機](https://code.claude.com/docs/zh-TW/desktop.md#run-commands-in-the-terminal)、[連接器](https://code.claude.com/docs/zh-TW/desktop.md#connect-external-tools)，或兩者皆缺少。請參閱[如果終端機或連接器無法使用](#check-for-the-terminal-and-connectors)。
* **[外掛](https://code.claude.com/docs/zh-TW/desktop.md#install-plugins)**：在 WSL 工作階段中無法使用
* **檔案編輯**：您可以在[檔案窗格](https://code.claude.com/docs/zh-TW/desktop.md#open-and-edit-files)中檢視檔案，但無法在其中編輯，因此請要求 Claude 進行變更
* **附件**：如果 **+** 選單顯示的是 **Add image** 而非 **Add files or photos**，則您只能附加圖片。請參閱[將檔案和內容新增至提示詞](https://code.claude.com/docs/zh-TW/desktop.md#add-files-and-context-to-prompts)。

### 如果終端機或連接器無法使用

您無法自行為 WSL 工作階段開啟整合終端機或連接器：

* **Claude 帳戶**：這兩項功能正在分別推出。請選取 **Help > Check for Updates…**，如果更新後某項功能仍然缺少，則無需採取任何動作。
* **[第三方供應商](https://code.claude.com/docs/zh-TW/third-party-integrations.md)**：WSL 工作階段不會提供終端機或連接器，更新 Desktop 也不會改變這一點

## 受管理的裝置

在由組織管理的裝置上，WSL 工作階段可能無法使用。如果工作階段啟動失敗，並顯示裝置受管理的訊息，這由您的管理員控制。管理員：請參閱部署指南中的[設定如何到達裝置](https://code.claude.com/docs/zh-TW/admin-setup.md#decide-how-settings-reach-devices)。

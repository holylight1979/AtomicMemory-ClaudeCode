<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/desktop-quickstart | lastmod: 2026-10-30 | section: Getting started / Platforms and integrations -->
> 來源：https://code.claude.com/docs/zh-TW/desktop-quickstart（官方 zh-TW，lastmod 2026-10-30）｜分類：Getting started › Platforms and integrations｜EN 摘要：Install the Claude desktop app, open the Code tab, and start your first Claude Code session on a project folder on your computer.

# 開始使用桌面應用程式

> 安裝 Claude 桌面應用程式、開啟 Code 標籤，並在您電腦上的專案資料夾開始您的第一個 Claude Code 會話。

桌面應用程式透過圖形介面為您提供 Claude Code。您可以請 Claude 處理電腦上某個資料夾中的程式碼，然後自行檢閱變更，完全不需要使用終端機。

Claude Code 位於應用程式側邊欄頂端的 **Code** 標籤中。本頁面將引導您安裝應用程式，並在該處開始您的第一個工作階段。Claude Code 需要 [Pro、Max、Ultra、Team 或 Enterprise 訂閱](https://claude.com/pricing?utm_source=claude_code\&utm_medium=docs\&utm_content=desktop_quickstart_pricing)。

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

> [!NOTE]
>
> 這些情況涵蓋在其他頁面上：
>
> * **已設定完成**：請參閱 [使用 Claude Code Desktop](https://code.claude.com/docs/zh-TW/desktop.md) 以了解 Code 標籤可以執行的所有操作
> * **想在終端機中使用 `claude`**：[分別安裝 CLI](https://code.claude.com/docs/zh-TW/quickstart.md)
> * **使用 Chat 或 Cowork**：請參閱 [Claude 說明中心](https://support.claude.com/)
> * **需要更多關於安裝或部署桌面應用程式的資訊**：請參閱 [Claude Desktop 支援文章](https://support.claude.com/en/collections/16163169-claude-desktop)

## 安裝

**1. 安裝並登入**

在 macOS 和 Windows 上，從上方連結下載安裝程式並執行它。在 Linux 上，請按照 [Claude Desktop on Linux](https://code.claude.com/docs/zh-TW/desktop-linux.md) 中的安裝步驟進行。從 macOS 上的應用程式資料夾、Windows 上的開始功能表或 Linux 上的應用程式啟動器啟動 Claude，然後使用您的 Anthropic 帳戶登入。

**2. 開啟 Code 標籤**

點擊側邊欄頂部的 **Code** 標籤。如果標籤只顯示圖示，請將滑鼠游標停留在圖示上以查看其名稱。如果點擊 **Code** 後出現提示或錯誤，請依照對應的解決方式處理：

* **提示升級**：您需要先[訂閱付費方案](https://claude.com/pricing?utm_source=claude_code\&utm_medium=docs\&utm_content=desktop_quickstart_upgrade)
* **提示線上登入**：請完成登入並重新啟動應用程式
* **403 錯誤**：請參閱[身分驗證疑難排解](https://code.claude.com/docs/zh-TW/desktop.md#403-or-authentication-errors-in-the-code-tab)

桌面應用程式包含 Claude Code，因此您無需安裝 Node.js 或 CLI 即可使用 Code 標籤。

## 開始您的第一個工作階段

開啟 Code 標籤後，選擇一個專案並告訴 Claude 要做什麼。

**1. 選擇環境和資料夾**

在[提示詞輸入框下方的那一列](https://code.claude.com/docs/zh-TW/desktop.md#start-a-session)中，點擊第一個控制項，也就是環境選擇器，並選擇 **Local** 群組中最上方的項目。接著點擊環境選擇器旁的專案資料夾控制項，選擇 **Open folder…**，然後選擇您的專案目錄。

如果新的工作階段在提示詞輸入框下方沒有顯示環境，表示您使用的是較早的版面配置。請參閱[確認您使用的版面配置](https://code.claude.com/docs/zh-TW/desktop.md#check-which-layout-you-have)。

> [!TIP]
>
> 從一個您熟悉的小型專案開始。這是最快看到 Claude Code 能做什麼的方式。

您也可以選擇：

* **Cloud**：在雲端執行工作階段，即使您關閉應用程式也會繼續進行。請參閱 [Use Claude Code in the cloud](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md) 以了解雲端工作階段的運作方式。
* **SSH**：透過 SSH 連接到遠端機器，例如您自己的伺服器、雲端虛擬機或開發容器。請先[新增連線](https://code.claude.com/docs/zh-TW/desktop.md#ssh-sessions)。Desktop 在您第一次連接時會自動在遠端機器上安裝 Claude Code。正在執行的工作可以[在 Desktop 中斷連線時繼續進行](https://code.claude.com/docs/zh-TW/desktop.md#keep-a-task-running-while-desktop-is-disconnected)，但若使用 Claude 帳戶，當其登入過期時可能會停止。
* **WSL**（Windows）：在 [WSL 2 distribution](https://code.claude.com/docs/zh-TW/desktop-wsl.md) 內執行工作階段；Claude Code、工具和 git 在 Linux 端執行，使用原生路徑。

**2. 選擇模型**

從提示詞輸入框下方那一列靠右端的模型選擇器中選擇模型。請參閱 [models](https://code.claude.com/docs/zh-TW/model-config.md#available-models) 以比較可用的模型。您稍後可以從模型選擇器變更模型。

**3. 告訴 Claude 要做什麼**

輸入您想要 Claude 做的事：

* `Find a TODO comment and fix it`
* `Add tests for the main function`
* `Create a CLAUDE.md with instructions for this codebase`

[工作階段](https://code.claude.com/docs/zh-TW/desktop.md#work-in-parallel-with-sessions)是與 Claude 關於您的程式碼的對話。每個工作階段追蹤其自己的內容和變更。

**4. 檢視並接受變更**

查看提示詞輸入框下方那一列中的[權限模式](https://code.claude.com/docs/zh-TW/desktop.md#choose-a-permission-mode)，以了解 Claude 是否會等待您的核准：

* **Auto or Accept edits**：Claude 套用其檔案變更，並出現指示器（例如 `+12 -1`），以便您可以在[差異檢視](https://code.claude.com/docs/zh-TW/desktop.md#review-changes-with-diff-view)中檢視它們
* **Manual**：Claude 提議每項變更並等待您的核准後才套用

在 Manual 模式中，您會看到：

1. 確切顯示將變更內容的差異
2. 用於核准或拒絕每項變更的按鈕
3. Claude 處理您的請求時的即時更新

## 接下來呢？

您已經完成了第一次編輯。如需了解 Desktop 的完整功能參考，請參閱[使用 Claude Code Desktop](https://code.claude.com/docs/zh-TW/desktop.md)。以下是一些可以嘗試的事項。

**中斷並調整方向。** 您可以隨時重新導向 Claude。點擊停止按鈕立即中斷，或輸入更正並按 **Enter** 鍵發送，無需停止執行中的操作。無論哪種方式，您都不必等待它完成或重新開始。

**為 Claude 提供更多背景資訊。** 在提示詞輸入框中輸入 `@filename` 以將特定檔案引入對話。Claude 擁有的背景資訊越多，結果就越好。請參閱[新增檔案和背景資訊](https://code.claude.com/docs/zh-TW/desktop.md#add-files-and-context-to-prompts)。

**使用 skills 執行可重複的工作。** 輸入 `/` 或點擊 **+** → **Slash commands** 以瀏覽[內建命令](https://code.claude.com/docs/zh-TW/commands.md)、[自訂 skills](https://code.claude.com/docs/zh-TW/skills.md) 和外掛 skills。Skills 是可重複使用的提示，您可以在需要時隨時叫用，例如程式碼審查檢查清單或部署步驟。

**在提交前檢查變更。** Claude 編輯檔案後，會出現 `+12 -1` 指示器。點擊它以開啟[差異檢視](https://code.claude.com/docs/zh-TW/desktop.md#review-changes-with-diff-view)，逐個檔案檢查修改，並在特定行上留下評論。Claude 會讀取您的評論並進行修訂。若要讓 Claude 自行審查變更，請在提示詞輸入框中輸入 [`/code-review`](https://code.claude.com/docs/zh-TW/desktop#review-your-code)。

**調整您擁有的控制程度。** 您的[權限模式](https://code.claude.com/docs/zh-TW/desktop.md#choose-a-permission-mode)設定了 Claude 在不請求批准的情況下可以執行的操作：

* **自動**：分類器在背景中檢查操作，並阻止有風險的操作，而不是詢問您。
* **手動**：Claude 在編輯檔案或執行命令前會詢問。
* **接受編輯**：Claude 自動接受檔案編輯以加快迭代速度。
* **Plan**：Claude 提出方法而不編輯任何檔案，這在大型重構前很有用。

**新增外掛以獲得更多功能。** 安裝可新增 skills、agents、MCP 伺服器等功能的[外掛](https://code.claude.com/docs/zh-TW/desktop.md#install-plugins)。

**整理您的工作區。** 將聊天、差異、終端機、檔案和瀏覽器窗格拖放到您想要的任何版面配置中。使用 **Ctrl+\`** 開啟終端機以在您的工作階段旁執行命令，或點擊檔案路徑以開啟它。請參閱[整理您的工作區](https://code.claude.com/docs/zh-TW/desktop.md#arrange-your-workspace)。

**預覽您的應用程式。** 當您在 desktop 中執行開發伺服器時，您的應用程式會在瀏覽器窗格中開啟，該窗格也可以[開啟外部網站](https://code.claude.com/docs/zh-TW/desktop.md#browse-external-sites)。Claude 可以檢視執行中的應用程式、測試端點、檢查日誌，並根據所看到的內容進行迭代。請參閱[預覽您的應用程式](https://code.claude.com/docs/zh-TW/desktop.md#preview-your-app)。

**追蹤您的 pull request。** 開啟 PR 後，Claude Code 會監控 CI 檢查結果，並可自動修復失敗。請參閱[監控 pull request 狀態](https://code.claude.com/docs/zh-TW/desktop.md#monitor-pull-request-status)。

**將 Claude 排程執行。** 設定[排程工作](https://code.claude.com/docs/zh-TW/desktop-scheduled-tasks.md)以定期自動執行 Claude：每天早上進行程式碼審查、每週進行相依性稽核，或從您連接的工具提取資訊的簡報。

**準備好時進行擴展。** 從側邊欄開啟[平行工作階段](https://code.claude.com/docs/zh-TW/desktop.md#work-in-parallel-with-sessions)以同時處理多個任務，可選擇每個任務都在自己的 Git worktree 中，並開啟[任務窗格](https://code.claude.com/docs/zh-TW/desktop.md#watch-background-tasks)以監控工作階段正在執行的 subagents 和背景命令。開啟[側邊聊天](https://code.claude.com/docs/zh-TW/desktop.md#ask-a-side-question-without-derailing-the-session)以提出問題而不會偏離主線。將[長期執行的工作發送到雲端](https://code.claude.com/docs/zh-TW/desktop.md#run-long-running-tasks-in-the-cloud)以便即使您關閉應用程式也能繼續執行，或在任務耗時超過預期時，[將已開始的工作階段移至雲端](https://code.claude.com/docs/zh-TW/desktop.md#continue-in-another-surface)。[連接外部工具](https://code.claude.com/docs/zh-TW/desktop.md#extend-claude-code)（例如 GitHub、Slack 和 Linear）以整合您的工作流程。

## 接下來

* [使用 Claude Code Desktop](https://code.claude.com/docs/zh-TW/desktop.md)：權限模式、平行工作階段、差異檢視、連接器和企業設定
* [從 CLI 遷移過來？](https://code.claude.com/docs/zh-TW/desktop.md#coming-from-the-cli)：在同一個專案上執行 Desktop 和 CLI，並比較功能、旗標等效項，以及 Desktop 中不可用的功能
* [疑難排解](https://code.claude.com/docs/zh-TW/desktop.md#troubleshooting)：常見錯誤和設定問題的解決方案
* [最佳實踐](https://code.claude.com/docs/zh-TW/best-practices.md)：撰寫有效提示詞和充分利用 Claude Code 的提示
* [常見工作流程](https://code.claude.com/docs/zh-TW/common-workflows.md)：除錯、重構、測試等的教學

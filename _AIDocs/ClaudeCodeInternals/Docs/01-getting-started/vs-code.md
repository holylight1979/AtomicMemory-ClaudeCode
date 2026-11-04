<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/vs-code | lastmod: 2026-11-04 | section: Getting started / Platforms and integrations -->
> 來源：https://code.claude.com/docs/zh-TW/vs-code（官方 zh-TW，lastmod 2026-11-04）｜分類：Getting started › Platforms and integrations｜EN 摘要：Install and configure the Claude Code extension for VS Code. Get AI coding assistance with inline diffs, @-mentions, plan review, and keyboard shortcuts.

# 在 VS Code 中使用 Claude Code

> 安裝並設定 VS Code 的 Claude Code 擴充功能。透過內聯差異、@-提及、計畫審查和鍵盤快捷鍵獲得 AI 編碼協助。

![VS Code 編輯器，右側開啟 Claude Code 擴充功能面板，顯示與 Claude 的對話](https://mintcdn.com/claude-code/-YhHHmtSxwr7W8gy/images/vs-code-extension-interface.jpg?fit=max\&auto=format\&n=-YhHHmtSxwr7W8gy\&q=85\&s=300652d5678c63905e6b0ea9e50835f8)

VS Code 擴充功能為 Claude Code 提供了原生圖形介面，直接整合到您的 IDE 中。這是在 VS Code 中使用 Claude Code 的推薦方式。

使用此擴充功能，您可以：

* 在接受 Claude 的計畫之前進行審查和編輯
* 在進行編輯時自動接受
* 從您的選擇中 @-提及具有特定行範圍的檔案
* 存取對話歷史記錄
* 在單獨的標籤或視窗中開啟多個對話

## 先決條件

安裝前，請確保您擁有：

* VS Code 1.94.0 或更高版本
* Anthropic 帳戶：任何付費 Claude 訂閱（Pro、Max、Ultra、Team 或 Enterprise）或 Claude Console 帳戶都可以使用，不需要 API 金鑰。首次開啟擴充功能時，您將[使用此帳戶登入](https://code.claude.com/docs/zh-TW/authentication.md#log-in-to-claude-code)。如果您透過第三方提供者（如 Amazon Bedrock 或 Google Cloud 的 Agent Platform）存取 Claude，請參閱[使用第三方提供者](#use-third-party-providers)以取得設定說明。

> [!TIP]
>
> 此擴充功能包含其自有的 CLI（命令列介面）副本供聊天面板使用。若要在 VS Code 的整合終端機中執行 `claude`，您還需要[獨立 CLI 安裝](https://code.claude.com/docs/zh-TW/setup.md)。詳細資訊請參閱 [VS Code 擴充功能與 Claude Code CLI](#vs-code-extension-vs-claude-code-cli)。

## 安裝擴充功能

點擊您所使用 IDE 的連結即可直接安裝：

* [為 VS Code 安裝](vscode:extension/anthropic.claude-code)
* [為 Cursor 安裝](cursor:extension/anthropic.claude-code)

或者在 VS Code 中，按下 `Cmd+Shift+X`（Mac）或 `Ctrl+Shift+X`（Windows/Linux）開啟「擴充功能」檢視，搜尋「Claude Code」，然後點擊 **Install**。

> [!NOTE]
>
> 擴充功能市集屬於第三方軟體，Anthropic 並未為其背書、維護或稽核。Anthropic 會將擴充功能提交至 Visual Studio Marketplace 和 Open VSX Registry 進行發布。

擴充功能的版本號碼即為其所內建的 Claude Code 版本。例如，需要 Claude Code v2.1.286 或更新版本的功能，就需要 2.1.286 或更新版本的擴充功能，版本號碼可在「擴充功能」檢視中查看。

Claude Code 也可以在其他編輯器和容器中執行：

* **其他 VS Code 分支版本**：此擴充功能也可安裝在 Devin Desktop 或 Kiro 等分支版本中。請在編輯器的「擴充功能」檢視中搜尋「Claude Code」，或從 [Open VSX Registry](https://open-vsx.org/extension/Anthropic/claude-code) 安裝。
* **無法安裝擴充功能的編輯器**：請改為[安裝 CLI](https://code.claude.com/docs/zh-TW/quickstart.md)，並在編輯器的整合式終端機中執行 `claude`。CLI 可在任何終端機中運作。
* **開發容器**：若要在開發容器中執行 Claude Code，請參閱[開發容器](https://code.claude.com/docs/zh-TW/devcontainer.md)。

> [!NOTE]
>
> 如果安裝後擴充功能沒有出現，請重新啟動 VS Code，或從命令選擇區執行「Developer: Reload Window」。

## 開始使用

安裝完成後，您可以透過 VS Code 介面開始使用 Claude Code：

**1. 開啟 Claude Code 面板**

在整個 VS Code 中，Spark 圖示代表 Claude Code：![Spark 圖示](https://mintcdn.com/claude-code/c5r9_6tjPMzFdDDT/images/vs-code-spark-icon.svg?fit=max\&auto=format\&n=c5r9_6tjPMzFdDDT\&q=85\&s=3ca45e00deadec8c8f4b4f807da94505)

開啟 Claude 最快的方式是點選 **Editor Toolbar**（編輯器右上角）中的 Spark 圖示。此圖示僅在開啟檔案時才會顯示。

![VS Code 編輯器在 Editor Toolbar 中顯示 Spark 圖示](https://mintcdn.com/claude-code/mfM-EyoZGnQv8JTc/images/vs-code-editor-icon.png?fit=max\&auto=format\&n=mfM-EyoZGnQv8JTc\&q=85\&s=eb4540325d94664c51776dbbfec4cf02)

開啟 Claude Code 的其他方式：

* **Activity Bar**：點選左側邊欄中的 Spark 圖示以開啟工作階段清單。點選任一工作階段即可在您[偏好的位置](#extension-settings)開啟，或開始新的工作階段。此圖示在 Activity Bar 中始終可見。
* **Command Palette**：按下 `Cmd+Shift+P`（Mac）或 `Ctrl+Shift+P`（Windows/Linux），輸入「Claude Code」，然後選擇「Open in New Tab」等選項
* **Status Bar**：點選視窗右下角的 **✻ Claude Code**。即使未開啟任何檔案，此方式也能使用。

您可以拖曳 Claude 面板，將其重新放置於 VS Code 中的任何位置。詳細資訊請參閱[自訂您的工作流程](#customize-your-workflow)。

**2. 登入**

第一次開啟面板時，會出現登入畫面。點選 **Sign in** 並在瀏覽器中完成授權。

如果之後看到 **Not logged in · Please run /login**，擴充功能會自動重新開啟登入畫面。如果登入畫面沒有出現，請從 Command Palette 使用 **Developer: Reload Window** 重新載入視窗。

如果您已在 shell 中設定 `ANTHROPIC_API_KEY`，但仍看到登入提示，可能是 VS Code 沒有繼承您的 shell 環境。請從終端機使用 `code .` 啟動 VS Code，使其繼承您的環境變數，或改用您的 Claude 帳戶登入。

登入後，會出現 **Learn Claude Code** 檢查清單。點選 **Show me** 逐一完成各個項目，或點選 X 將其關閉。若之後要重新開啟，請在 VS Code 設定的 **Extensions > Claude Code** 下取消勾選 **Hide Onboarding**。

**3. 傳送提示詞**

請 Claude 協助處理您的程式碼或檔案，無論是說明某項功能的運作方式、除錯問題，還是進行變更。

> [!TIP]
>
> Claude 會自動看到您選取的文字。按下 `Option+K`（Mac）/ `Alt+K`（Windows/Linux）還可以在提示詞中插入 @-mention 參照（例如 `@file.ts#5-10`）。

以下是針對檔案中特定行提問的範例：

![VS Code 編輯器在 Python 檔案中選取了第 2-3 行，Claude Code 面板顯示一個針對這些行、帶有 @-mention 參照的問題](https://mintcdn.com/claude-code/FVYz38sRY-VuoGHA/images/vs-code-send-prompt.png?fit=max\&auto=format\&n=FVYz38sRY-VuoGHA\&q=85\&s=ede3ed8d8d5f940e01c5de636d009cfd)

**4. 檢閱變更**

請查看提示詞輸入框底部顯示的[權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md#which-mode-a-session-starts-in)：

* 在 Auto 或 Edit automatically 模式下，Claude 會直接編輯您工作區中的[大多數檔案](https://code.claude.com/docs/zh-TW/permission-modes.md#protected-paths)，而不會詢問。
* 在 Manual 模式下，當 Claude 想要編輯檔案時，會並排顯示原始內容與建議的變更，然後請求權限。您可以接受、拒絕，或告訴 Claude 改做什麼。如果您在接受之前直接於差異檢視中編輯建議的內容，Claude 會得知您已修改過，因此不會假設檔案與其原始建議一致。

  ![VS Code 顯示 Claude 建議變更的差異，以及詢問是否進行編輯的權限提示](https://mintcdn.com/claude-code/FVYz38sRY-VuoGHA/images/vs-code-edits.png?fit=max\&auto=format\&n=FVYz38sRY-VuoGHA\&q=85\&s=e005f9b41c541c5c7c59c082f7c4841c)

若要一次檢閱一項建議的編輯變更，請使用差異中每項變更下方的 **Accept this change** 和 **Reject this change** 按鈕。拒絕某項變更會在建議的內容中還原該變更；接受則會將其標記為已檢閱。逐項變更檢閱需要 Claude Code v2.1.275 或更新版本。

接受或拒絕整個檔案仍會完成檢閱。包含超過 100 項變更的差異開啟時不會顯示逐項變更按鈕，因此請以整個檔案為單位進行檢閱。

相同的操作也可以在游標位置透過編輯器的右鍵選單，以及在 Command Palette 中以 **Claude Code: Accept Change at Cursor** 和 **Claude Code: Reject Change at Cursor** 執行。

如需更多關於 Claude Code 用途的構想，請參閱[常見工作流程](https://code.claude.com/docs/zh-TW/common-workflows.md)。

> [!TIP]
>
> 從 Command Palette 執行「Claude Code: Open Walkthrough」，即可獲得基本功能的導覽。

## 使用提示詞輸入框

提示詞輸入框支援多項功能：

* **權限模式**：點擊提示詞輸入框底部的模式指示器即可切換權限模式。在 Claude Code v2.1.283 或更新版本中，Auto 是內建的起始權限模式；在較早版本中，僅 Pro、Max、Ultra 和 Team 方案如此。請參閱[擴充功能如何選擇起始權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md#switch-permission-modes)，了解哪些因素會改變此設定，以及指示器提供的每種權限模式。
  * **Auto**：由分類器審查大多數動作，而不是詢問您。請參閱[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)，了解它會審查和封鎖哪些內容。
  * **Manual**：Claude 在編輯檔案和執行大多數 shell 命令前會請求權限。
  * **Plan**：Claude 會描述它將執行的動作，並在進行變更前等待核准。VS Code 會自動將計畫開啟為完整的 Markdown 文件，您可以在其中加入行內註解，在 Claude 開始之前提供意見回饋。

    您也可以在提示詞輸入框中輸入 `/plan`。需要 Claude Code v2.1.280 或更新版本。

    * `/plan`：切換到 plan mode。如果您已處於 plan mode，則改為顯示目前的計畫。
    * 帶有任務的 `/plan`，例如 `/plan fix the auth bug`：切換到 plan mode 並開始規劃該任務。
    * `/plan open`：當您已處於 plan mode 時，在編輯器中開啟計畫檔案。
  * **Edit automatically**：Claude 會直接進行編輯而不詢問。
* **模型**：從命令選單中選取 **Switch model…**，即可在工作階段中途變更模型。您也可以點擊提示詞輸入框底部的模型名稱來開啟相同的選擇器。在 Claude Code v2.1.284 或更新版本中，在提示詞輸入框中單獨輸入 `/model` 也會開啟選擇器。

  當目前的模型支援 [effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)時，選擇器也會顯示 **Effort** 列，且模型名稱按鈕會顯示所選的等級。當您選擇 `max` 以外的等級時，Claude Code 會將其儲存為目前模型的預設值，存放於使用者設定中的 [`modelSettings`](https://code.claude.com/docs/zh-TW/settings-reference#modelsettings) 之下；`max` 僅套用於目前的工作階段。模型名稱按鈕和 **Effort** 列需要 Claude Code v2.1.257 或更新版本。

  當[動態工作流程](https://code.claude.com/docs/zh-TW/workflows.md)已啟用且目前的模型支援時，**Effort** 列下方會出現 **Ultracode** 開關。開啟後，Claude 會在此工作階段中，以所選的 effort 等級為每個實質任務規劃一個[工作流程](https://code.claude.com/docs/zh-TW/workflows.md#let-claude-decide-with-ultracode)。開啟期間，模型名稱按鈕會在等級後方顯示 `· Ultracode`。此開關需要 Claude Code v2.1.284 或更新版本。
* **命令選單**：點擊 `/` 或輸入 `/` 以開啟命令選單。選項包括附加檔案和切換模型。

  Customize 區段包含 MCP 伺服器、命令、輸出風格、hook、記憶、指令、權限和外掛等項目。帶有終端機圖示的項目會在整合式終端機中開啟。

  * 若要瀏覽 `/usage` 或 [`/remote-control`](https://code.claude.com/docs/zh-TW/remote-control) 等命令，請在 Customize 區段中選取 **Slash commands**。對話方塊會列出這些命令並提供篩選框。選取其中一個即可執行。在提示詞輸入框中輸入 `/` 仍會以內嵌方式建議命令。需要 Claude Code v2.1.257 或更新版本。

    輸入 `/skills` 也會開啟此對話方塊。每個 [skill](https://code.claude.com/docs/zh-TW/skills.md) 列都會顯示其[可見性](https://code.claude.com/docs/zh-TW/skills.md#override-skill-visibility-from-settings)，例如 **On** 或 **Name only**。點擊可見性即可變更，但標記為 **locked** 的列（例如外掛 skill）除外。`/skills` 捷徑和可見性控制項需要 Claude Code v2.1.280 或更新版本。
  * 在 Customize 區段中選取 **Output styles**，即可選擇[輸出風格](https://code.claude.com/docs/zh-TW/output-styles.md)，包括您的自訂風格。需要 Claude Code v2.1.257 或更新版本。

    若要改為建立自訂風格，請從 **Output styles** 選單中選取 **Build a custom style**。Claude Code 會在專案層級或使用者層級為您撰寫[風格檔案](https://code.claude.com/docs/zh-TW/output-styles.md#create-a-custom-output-style)。需要 Claude Code v2.1.261 或更新版本。
  * 在 Customize 區段中選取 **Hooks**，即可檢視工作階段中載入的 [hook](https://code.claude.com/docs/zh-TW/hooks.md)，並依事件分組。您可以新增、編輯或移除儲存在使用者、專案和本機設定檔中的 hook。來自其他來源的 hook（例如受管設定或外掛）為唯讀。需要 Claude Code v2.1.269 或更新版本。
  * 在 Customize 區段中選取 **Permissions**，即可檢視工作階段的[權限規則](https://code.claude.com/docs/zh-TW/permissions.md)，並分為 Allow、Ask 和 Deny 三組。您可以將規則新增至使用者、專案或本機設定，也可以移除儲存在其中的規則。來自其他來源的規則（例如受管設定或僅適用於此工作階段的核准）為唯讀。需要 Claude Code v2.1.269 或更新版本。
  * 在 Customize 區段中選取 **Memory**，即可開啟或關閉[自動記憶](https://code.claude.com/docs/zh-TW/memory.md#auto-memory)。開啟期間，您也可以瀏覽 Claude 已儲存的記憶，並在檔案管理員中顯示存放這些記憶的資料夾。需要 Claude Code v2.1.274 或更新版本。

    點擊已儲存的記憶即可在對話方塊中閱讀，您可以在其中編輯文字、刪除記憶，或在編輯器中開啟其檔案。在對話方塊中檢視、編輯和刪除記憶需要 Claude Code v2.1.275 或更新版本。
  * 在 Customize 區段中選取 **Instructions**，即可編輯 Claude 讀取的 [CLAUDE.md 檔案](https://code.claude.com/docs/zh-TW/memory.md#claude-md-files)。選取檔案即可在編輯器中開啟。如果檔案尚不存在，Claude Code 會先建立它。需要 Claude Code v2.1.274 或更新版本。
  * 在 Customize 區段中選取 **Status**，或輸入 `/status`，即可查看工作階段的 Claude Code 版本、帳戶、模型和 MCP 伺服器詳細資訊。需要 Claude Code v2.1.280 或更新版本。
  * 在 Customize 區段中選取 **Sandbox**，或輸入 `/sandbox`，即可查看 Claude 的 Bash 命令是否在[沙箱](https://code.claude.com/docs/zh-TW/sandboxing.md)中執行。您可以在其中切換沙箱模式並新增[排除的命令](https://code.claude.com/docs/zh-TW/settings-reference.md#sandbox-excludedcommands)。需要 Claude Code v2.1.280 或更新版本。
  * 在 Customize 區段中選取 **Claude in Chrome**，或輸入 `/chrome`，即可檢查和管理 [Claude in Chrome](https://code.claude.com/docs/zh-TW/chrome.md) 連線。兩者都需要使用 claude.ai 帳戶登入。需要 Claude Code v2.1.280 或更新版本。
  * 在 Context 區段中選取 **Export conversation**，或輸入 `/export`，即可將對話複製為純文字或儲存至檔案。加上檔案名稱（例如 `/export notes.txt`）即可略過對話方塊，並選擇檔案的儲存位置。需要 Claude Code v2.1.280 或更新版本。
  * Settings 區段包含 **Enable Remote Control for all sessions**，它會設定 [`remoteControlAtStartup`](https://code.claude.com/docs/zh-TW/settings-reference#remotecontrolatstartup)，以控制[新的互動式工作階段是否自動連線至 Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md#enable-remote-control-for-all-sessions)。需要 Claude Code v2.1.203 或更新版本。

    當您在 VS Code 視窗中開啟或關閉此切換時，變更不僅限於之後啟動的工作階段，也會套用至該 VS Code 視窗中已開啟的工作階段。如果您將其關閉，已開啟的工作階段會中斷連線。在 Claude Code v2.1.261 或更新版本中，變更也會套用至您其他 VS Code 視窗中開啟的工作階段。
  * Settings 區段也包含 **Focus view**，它會將工具呼叫、工具結果和思考內容隱藏在可展開的列中，只留下您的提示詞和 Claude 的回應。您可以在該處切換，或使用 `Ctrl+Option+F`（Mac）/ `Ctrl+Alt+F`（Windows/Linux），或從命令選擇區使用 **Claude Code: Toggle Focus view**。此變更會套用至每個開啟的工作階段，並在工作階段之間保留。需要 Claude Code v2.1.221 或更新版本。

    Claude 最新的待辦事項清單會保持可見，Claude 待回覆問題所詢問的文字也會保持可見；這需要 Claude Code v2.1.225 或更新版本。當 Claude 執行 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 時，顯示其最新活動的即時進度列會出現在啟動它們的工具呼叫群組下方。這需要 Claude Code v2.1.269 或更新版本。
  * 若要登出您的 Anthropic 帳戶，請在 Settings 區段中選取 **Sign out**，或輸入 `/logout`。在[第三方供應商](#use-third-party-providers)上，選單不會提供任何一種方式。需要 Claude Code v2.1.277 或更新版本。
  * 若要回報錯誤，請點擊選單底部的 **Report a problem**，或輸入 `/bug` 或 `/feedback`，並可選擇性附上描述以預先填入回報內容。當您提交回報且已透過第一方連線登入 Anthropic 時，Claude Code 會將其傳送給 Anthropic。需要 Claude Code v2.1.229 或更新版本。

    在第三方供應商上，或沒有 Anthropic 憑證時，不會傳送任何內容。對話方塊會在您撰寫之前說明這一點。提交後會將回報儲存為[位於 `~/.claude/feedback-bundles/` 下的本機封存檔](https://code.claude.com/docs/zh-TW/data-usage#telemetry-services)，並遮蔽已知的 API 金鑰和 token 模式。將回報儲存在您的電腦上需要 Claude Code v2.1.284 或更新版本。

    回報儲存後，確認訊息會列出檔案名稱，並包含 **Show folder** 按鈕。請將該檔案傳送給您的 Anthropic 客戶代表，或附加至支援請求中。

    如果您組織的政策關閉了產品意見回饋，**Report a problem** 不會出現在選單中，而 `/bug` 和 `/feedback` 會顯示 `Feedback is turned off by your organization's policy or this environment's settings.` 通知，而不是開啟回報。在 Claude Code v2.1.284 或更新版本中，如果您設定了 `DISABLE_FEEDBACK_COMMAND` 或 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` 環境變數，意見回饋也會被關閉，開啟回報時會改為顯示該通知。
* **旁支問題**：輸入 `/btw` 後接問題，即可詢問有關工作階段的問題，[而不會加入對話中](https://code.claude.com/docs/zh-TW/interactive-mode.md#side-questions-with-%2Fbtw)。答案會在聊天旁的面板中開啟，您可以在其中提出後續問題。需要 Claude Code v2.1.227 或更新版本。

  此討論串在視窗重新載入後仍會保留。Claude Code 會保留最新的 20 次交流，並依照 [`cleanupPeriodDays`](https://code.claude.com/docs/zh-TW/settings-reference#cleanupperioddays) 排程讓已儲存的討論串過期，前提是 Claude Code 能夠[安全地判斷保留期限](https://code.claude.com/docs/zh-TW/claude-directory.md#cleaned-up-automatically)。若要清除討論串，請點擊面板中的垃圾桶圖示。
* **複製回應**：將滑鼠懸停在回應上並點擊 **Copy response** 即可將其複製到剪貼簿，或輸入 `/copy` 以複製最新的回應。`/copy 2` 會複製倒數第二個回應。需要 Claude Code v2.1.277 或更新版本。
* **書籤**：將滑鼠懸停在回應上並點擊 **Bookmark response** 即可儲存，或在已儲存的回應上點擊 **Remove bookmark** 以移除。

  若要檢閱已儲存的回應，請開啟 Bookmarks 面板。您可以點擊 Claude Code 面板頂部的書籤圖示、在命令選單的 Context 區段中選取 **Bookmarks**，或輸入 `/bookmarks`。需要 Claude Code v2.1.286 或更新版本。
* **Claude 傳送給您的檔案**：當工作階段連線至 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md#start-a-remote-control-session)，且 Claude 使用 [`SendUserFile` 工具](https://code.claude.com/docs/zh-TW/tools-reference)傳送檔案給您時，對話中會顯示一列，例如 **Sent report.md, chart.png**。點擊檔案名稱即可在編輯器中開啟。此列在 Focus view 中仍會保持可見。需要 Claude Code v2.1.295 或更新版本。

  當檔案路徑指向網路主機時，該檔案會顯示為您無法點擊的完整路徑，例如 `\\server\share\report.md`。Claude Code 不會為該檔案建立連結，因為開啟它會連線至該主機，且在 Windows 上[可能會將您的 Windows 憑證傳送至該主機](https://code.claude.com/docs/zh-TW/permissions.md#read-only-commands)。
* **上下文指示器**：提示詞輸入框會顯示您已使用了多少 Claude 的上下文視窗。Claude 會在需要時自動壓縮，您也可以手動執行 `/compact`。
* **提示快取時鐘**：上下文指示器旁的時鐘圖示會估算對話的[提示快取](https://code.claude.com/docs/zh-TW/prompt-caching.md)在過期前還剩多少時間。它會從快取的五分鐘或一小時[存留期](https://code.claude.com/docs/zh-TW/prompt-caching.md#cache-lifetime)開始倒數，而每個使用快取的回應都會重新開始倒數。除了壓縮之外，[使快取失效的動作](https://code.claude.com/docs/zh-TW/prompt-caching.md#actions-that-invalidate-the-cache)不會重設時鐘，因此在您切換模型後，它仍可能顯示剩餘的分鐘數。
  * 在倒數結束之前，圖示會顯示剩餘的分鐘數，例如 **12m**。
  * 倒數結束時，分鐘數會消失，圖示會變成紅色（或您佈景主題的錯誤色彩），直到下一個回應為止。快取很可能已過期，因此在快取重建期間，您下一則訊息的回應可能會較慢且成本較高。如果五分鐘的存留期在您的訊息之間不斷用盡，請參閱[自行選擇 TTL](https://code.claude.com/docs/zh-TW/prompt-caching.md#choose-the-ttl-yourself)。
  * 在對話剛[壓縮](https://code.claude.com/docs/zh-TW/prompt-caching.md#compacting-the-conversation)後，圖示也會變成紅色且不顯示分鐘數，直到下一個回應為止，因為快取尚未涵蓋壓縮後的對話。
* **Agent 地圖**：當對話包含 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 時，提示詞輸入框底部會出現 agent 計數，例如 **2 agents**。其圓點會顯示是否有任何 subagent 正在工作或正在等待您的權限。

  點擊 agent 計數即可開啟 agent 地圖，它會將對話的 subagent 繪製成位於主 agent 下方的樹狀結構，每個都附有其狀態、經過時間和 token 數。點擊 subagent 即可查看其提示詞和工具呼叫、開啟其唯讀逐字稿，或在其執行時將其停止。需要 Claude Code v2.1.269 或更新版本。

  地圖也會在 agent 下方列出工作階段的其他[背景任務](https://code.claude.com/docs/zh-TW/tools-reference.md#background-commands)，例如背景 shell 命令和[監視器](https://code.claude.com/docs/zh-TW/tools-reference.md#monitor-tool)。點擊某一列即可開啟該任務的卡片並在其中將其停止。

  若要在未顯示 agent 計數時開啟地圖（例如 Claude 已啟動背景 shell 但沒有 subagent 時），請在提示詞輸入框中輸入 `/tasks`。地圖中的背景任務和輸入的 `/tasks` 需要 Claude Code v2.1.277 或更新版本。

  在 Claude Code v2.1.286 或更新版本中，當您點擊 **Stop** 或按下 `Esc` 時，目前的回合會結束。背景 agent 會持續執行，直到完成或您從地圖中將其停止為止。
* **延伸思考**：讓 Claude 花更多時間推理複雜的問題。若要將其關閉或重新開啟，請使用命令選單（`/`）Model 區段中的 **Thinking** 開關。在[無法關閉思考](https://code.claude.com/docs/zh-TW/model-config.md#extended-thinking)的模型上，選單中沒有 **Thinking** 開關，且思考會保持開啟。

  僅顯示標籤（例如 `Thought for 12s`）的思考區塊不含文字，點擊時也不會展開。若要查看思考摘要，請在 `~/.claude/settings.json` 中將 [`showThinkingSummaries`](https://code.claude.com/docs/zh-TW/settings-reference#showthinkingsummaries) 設為 `true`，然後從命令選擇區執行 **Developer: Reload Window**。

  您既有的思考區塊會保持空白。在重新載入後的回應中，點擊區塊或按下 `Ctrl+O` 即可將其全部展開。
* **多行輸入**：按下 `Shift+Enter` 即可新增一行而不傳送。這在問題對話方塊的「Other」自由文字輸入中也適用。

### 參照檔案和資料夾

使用 @ 提及為 Claude 提供特定檔案或資料夾的上下文。當您輸入 `@` 後接檔案或資料夾名稱時，Claude 會讀取該內容，並可以回答相關問題或對其進行變更。Claude Code 支援模糊比對，因此您可以輸入部分名稱來找到所需內容：

```text wrap theme={null}
Explain the logic in @auth (fuzzy matches auth.js, AuthService.ts, etc.)
What's in @src/components/ (include a trailing slash for folders)
```

### 讀取 PDF 的特定頁面

對於大型 PDF，您可以要求 Claude 讀取特定頁面，而不是整個檔案。您可以要求單一頁面、範圍（例如第 1-10 頁），或開放式範圍（例如第 3 頁之後）。讀取特定頁面需要在執行 Claude Code 的機器上安裝 [poppler-utils](https://code.claude.com/docs/zh-TW/tools-reference.md#read-tool-behavior)。

### 在提示詞中包含終端機輸出

使用 `@terminal:name` 在提示詞中參照終端機輸出，其中 `name` 是終端機的標題。這可讓 Claude 看到命令輸出、錯誤訊息或日誌，而不需要複製貼上。

### 附加圖片和檔案

* 若要附加圖片，請從剪貼簿將其貼到提示詞輸入框中。
* 若要附加檔案，請在將檔案拖曳至提示詞輸入框時按住 `Shift`。
* 若要從上下文中移除附件，請點擊其上的 X。

### 貼上文字

您貼上的文字會在提示詞輸入框中保持可見，而不會像[在終端機中](https://code.claude.com/docs/zh-TW/terminal-config.md#paste-large-content)那樣摺疊成預留位置。在 Claude Code [會標記貼上文字](https://code.claude.com/docs/zh-TW/terminal-config.md#how-claude-treats-pasted-text)的工作階段中，Claude 仍會將大量貼上的內容視為您貼上的文字，而非您輸入的文字。

Claude Code 也會從您貼到提示詞輸入框的文字以及您傳送的任何其他內容中，移除[不可見的 Unicode 字元](https://code.claude.com/docs/zh-TW/interactive-mode.md#invisible-characters-in-prompts)：

* 如果在您貼上時出現 `Removed 3 invisible characters from the pasted text` 之類的通知，表示文字已在移除這些字元後輸入。
* 如果在您傳送時出現有關已移除字元的通知，表示沒有傳送任何內容。清理後的文字會回到提示詞輸入框中。再次傳送即可依所顯示的內容傳送文字。

### 來自您的選取內容和開啟檔案的自動上下文

當您在編輯器中選取文字時，Claude 可以自動看到您反白的程式碼。提示詞輸入框的頁尾會顯示已選取的行數。即使沒有選取任何內容，Claude 也會看到您在編輯器中開啟的檔案，且提示詞輸入框會顯示其名稱。

按下 `Option+K`（Mac）/ `Alt+K`（Windows/Linux）即可插入包含檔案路徑和行號的 @ 提及，例如 `@app.ts#5-10`。

#### 避免將您的選取內容和開啟的檔案加入訊息

若要避免所選取的文字或您開啟的檔案進入您的訊息，請在 VS Code 的設定中關閉對應的設定：

* **所選取的文字**：關閉 [Attach Selection 設定](vscode://settings/claudeCode.attachSelection)。需要 Claude Code v2.1.300 或更新版本。若要捨棄單一選取內容，請點擊行數旁的 **X**。當您選取其他文字時，行數會重新出現。
* **開啟的檔案**：關閉 [Attach Open File 設定](vscode://settings/claudeCode.attachOpenFile)。需要 Claude Code v2.1.271 或更新版本。除非您的訊息包含您在該檔案中選取的文字，否則不會加入該檔案。

若要在 Attach Selection 關閉時將文字加入為 @ 提及，請選取文字，然後在 Mac 上按下 `Option+K`，或在 Windows 和 Linux 上按下 `Alt+K`。

當您在 VS Code 的整合式終端機中執行 `claude` 時，這兩項設定同樣適用。

#### 來自已排除或已忽略檔案的選取文字

在聊天面板中，擴充功能會對某些檔案隱瞞所選取的文字：

* 當檔案位於您的工作區內，且符合您的 `files.exclude` 或 `search.exclude` 設定時，Claude 最多只會收到檔案的路徑，而不會收到您選取的文字。
* 這同樣適用於被 git 忽略的檔案，前提是 VS Code 的 `search.useIgnoreFiles` 設定和擴充功能的 [`respectGitIgnore` 設定](#extension-settings)都已開啟（此為預設值）。

此篩選僅涵蓋聊天面板。當 Claude Code 在整合式終端機中執行時，Claude 可能會收到您在這些檔案中選取的文字。若要在該處避免 Claude 取得檔案內容，請新增 [`Read` 拒絕規則](https://code.claude.com/docs/zh-TW/permissions#read-and-edit)。

### 回應中的 LaTeX 數學式

聊天面板會將 Claude 回應中的 LaTeX 數學式顯示為排版後的公式。數學式呈現需要 Claude Code v2.1.301 或更新版本。在[終端機模式](#switch-to-terminal-mode)中，數學式不會排版。面板會同時排版獨立顯示數學式和行內數學式：

* **獨立顯示數學式**：單獨佔一行或多行的 `$$ … $$` 或 `\[ … \]` 區塊，以及語言為 `math` 的圍欄程式碼區塊
* **行內數學式**：在同一行中開始和結束的 `$…$` 或 `\(…\)`，例如 `$E = mc^2$` 或 `\(a^2 + b^2 = c^2\)`

面板會嘗試將數學式與相同字元的其他用途區分開來，因此 `$HOME`、像 `$5` 這樣的價格，或 `sed 's/\(foo\)/\1/'` 等文字不會被排版。程式碼片段內的文字，或除了圍欄 `math` 區塊以外的任何程式碼區塊內的文字也不會被排版。如果您預期會排版的公式以原始寫法顯示，請參閱[公式顯示為原始 LaTeX](#a-formula-shows-as-raw-latex)。

當您選取並複製包含已排版公式的文字時，您會取得以 `$…$` 或 `$$…$$` 分隔符號包住的公式 TeX 原始碼，而不是繪製出的符號。[**Copy response**](#use-the-prompt-box) 和 `/copy` 會提供 Claude 所撰寫的原始回應，包括 TeX 原始碼。

### 繼續過去的對話

點擊 Claude Code 面板頂部的 **Session history** 按鈕即可存取您的對話記錄。您可以依關鍵字搜尋或依時間瀏覽。

點擊任何對話即可繼續該對話。如果該對話已在目前視窗的另一個分頁中開啟，點擊它會切換到該分頁。當通知指出該對話仍在其他地方開啟時，請參閱[如何在此視窗中繼續該對話](#the-conversation-is-still-open-somewhere-else)。如果對話開啟時未顯示任何訊息，請參閱[繼續的對話為何一開始是空白的](#a-resumed-conversation-is-blank-at-first)。如需有關繼續工作階段的更多資訊，請參閱[管理工作階段](https://code.claude.com/docs/zh-TW/sessions.md)。

* **工作階段標題**：新的工作階段會根據您的第一則訊息獲得 AI 產生的標題。
* **重新命名和封存**：將滑鼠懸停在工作階段上即可顯示這些動作。重新命名可為其提供具描述性的標題，封存則會將其移至清單底部的 **Archived sessions** 群組。
* **設定 [`claudeProcessWrapper`](#extension-settings) 時遺漏的對話**：請將擴充功能更新至 2.1.304 或更新版本。清單隨後會包含先前遺漏的對話，以及由 `claude -p` 或 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 在此工作區中啟動的工作階段。

預設情況下，14 天沒有活動的工作階段會自動移至 **Archived sessions**，除非它處於開啟狀態、未讀，或位於[群組](#organize-sessions-into-groups)中。自動封存需要 Claude Code v2.1.265 或更新版本。若要變更期限或將其關閉，請開啟 [Archive Inactive Sessions 設定](vscode://settings/claudeCode.archiveInactiveSessions)，並選取天數或 **Never**。

若要還原已封存的工作階段：

* **單一工作階段**：展開 **Archived sessions** 並點擊 **Unarchive session**。
* **一次還原所有已封存的工作階段**：將滑鼠懸停在活動列中工作階段清單的 **Archived sessions** 標題上，然後點擊其取消封存圖示。需要 Claude Code v2.1.277 或更新版本。

在 v2.1.257 之前，此動作為 **Delete session**，它會隱藏工作階段且無法還原。升級後，您當時刪除的工作階段會出現在 **Archived sessions** 之下。

當您繼續的對話是在 plan mode 中結束時，Claude Code 會還原 plan mode。需要 Claude Code v2.1.246 或更新版本。在以下情況中，Claude Code 不會還原 plan mode：

* 擴充功能從 `claudeCode.initialPermissionMode` 或沿用自先前對話的選擇來[選擇起始權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md#switch-permission-modes)
* 您已設定 `claudeCode.claudeProcessWrapper`
* [拒絕規則](https://code.claude.com/docs/zh-TW/permissions.md#manage-permissions)移除了 [`ExitPlanMode`](https://code.claude.com/docs/zh-TW/tools-reference) 工具

#### 對話仍在其他地方開啟

當通知指出對話仍在其他地方開啟時，若要在此視窗中繼續，請先完成適用於您情況的步驟，再點擊 **Open here anyway**：

* **您沒有在其他地方開啟任何內容**：擴充功能重新啟動前的 Claude 程序可能仍開啟著該對話。該程序通常會在約 10 分鐘內自行結束，因此請等待這段時間後再點擊。如果您在它結束前點擊，該對話會在兩處同時開啟，直到該程序結束為止。
* **您在其他地方開啟了該對話**：請先在該處將其關閉，例如在終端機中結束 `claude`，或在另一個 VS Code 視窗中關閉其分頁

當對話仍在另一個 Claude Code 程序中開啟時，此通知會取代提示詞輸入框出現：

```text theme={null}
This conversation is still open somewhere else. Using it in two places at once can mix up its messages. If the extension restarted recently, a Claude process from before the restart may still be finishing. It usually ends on its own within about 10 minutes. This notice stays until you choose Open here anyway.
```

設定了 [`claudeProcessWrapper`](#extension-settings) 時，擴充功能會略過此檢查並直接開啟對話。

### 從 claude.ai 繼續雲端工作階段

如果您執行[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)，可以直接在 VS Code 中繼續這些工作階段。這需要使用 **Claude.ai Subscription** 登入，而非 Anthropic Console。

**1. 開啟工作階段記錄**

點擊 Claude Code 面板頂部的 **Session history** 按鈕。

**2. 選取 Web 分頁**

對話方塊會顯示兩個分頁：Local 和 Web。點擊 **Web** 即可查看來自 claude.ai 的工作階段。

**3. 選取要繼續的工作階段**

瀏覽或搜尋工作階段。點擊其中一個即可在本機繼續對話。

> [!NOTE]
>
> 當您開啟的資料夾是 GitHub 儲存庫時，Web 分頁只會顯示來自該儲存庫的工作階段。
>
> 當您繼續雲端工作階段時，擴充功能會下載對話記錄的副本；變更不會同步回 claude.ai。

Web 分頁也會列出您的 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 工作階段。如果您點擊在您目前開啟的資料夾中執行的工作階段，擴充功能會開啟該本機對話，而不是下載副本。如果已有分頁顯示該對話，擴充功能會聚焦該分頁。如果擴充功能無法排除另一個 Claude 程序已開啟該對話的可能性，您會改為取得下載的副本。

如果對話的任何部分下載失敗，會出現錯誤且不會儲存任何副本。再次選取該工作階段即可重試。如果您選取的工作階段尚無可下載的對話，錯誤訊息會告訴您應改在何處繼續。

### 查看帳戶和使用量

執行 `/usage` 以開啟 Account & usage 對話方塊，其中會顯示您登入的帳戶和您的使用量。使用量數字會依您的登入方式而定：

* **claude.ai 方案**：顯示您方案限制的使用量長條，例如目前工作階段和本週。

  對話方塊也會細分哪些因素正在消耗您的方案限制：

  * **建議**：建議的變更，每列一項，例如 `Trim ~/code/api/CLAUDE.md · 49k tokens per request`
  * **修正按鈕**：若要讓 Claude Code 套用其可套用的建議，請點擊建議下方的按鈕，例如 **Fix both**。若要了解該按鈕會作用於哪些列，以及之後您的工作階段中會發生什麼事，請參閱[使用修正捷徑套用建議](https://code.claude.com/docs/zh-TW/costs.md#apply-recommendations-with-the-fix-shortcut)。需要 Claude Code v2.1.305 或更新版本。

    [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 連線期間不會顯示此按鈕。如果在 Remote Control 連線後出現 `The usage fix wasn’t fully sent. Open usage and try again.` 警告，請先[中斷 Remote Control 連線](https://code.claude.com/docs/zh-TW/remote-control.md#check-connection-status)再重試。
  * **歸因**：顯示每個 skill、subagent、外掛和 MCP 伺服器所產生使用量的表格

  使用 Day 和 Week 切換，即可在過去 24 小時和過去 7 天之間切換。這些數字為近似值，是根據此機器上的本機工作階段計算而得，因此不包括來自其他裝置或 claude.ai 的使用量。
* **其他登入方式**：當方案限制不適用於您的登入方式時（例如在[第三方供應商](#use-third-party-providers)上或使用 API 金鑰時），Usage 區段會改為顯示工作階段本身的成本和 token 使用量。CLI 的 `/usage` 會在其 [Session 區塊](https://code.claude.com/docs/zh-TW/costs.md#track-your-costs)中顯示相同的總計。活動列中的工作階段清單也會在其 **Account & usage** 標題下顯示使用中工作階段的總計。需要 Claude Code v2.1.277 或更新版本。

如需有關追蹤和減少使用量的更多資訊，請參閱[追蹤您的成本](https://code.claude.com/docs/zh-TW/costs.md#track-your-costs)。

### 使用檢查點倒轉

VS Code 擴充功能支援檢查點，它會追蹤 Claude 的檔案編輯，並讓您倒轉至先前的狀態。將滑鼠懸停在任何訊息上即可顯示倒轉按鈕，然後從三個選項中選擇：

* **Fork conversation from here**：從此訊息開始新的對話分支，同時保留所有程式碼變更
* **Rewind code to here**：將檔案變更還原至對話中的此時間點，同時保留完整的對話記錄
* **Fork conversation and rewind code**：開始新的對話分支，並將檔案變更還原至此時間點

如需有關檢查點運作方式及其限制的完整詳細資訊，請參閱[檢查點功能](https://code.claude.com/docs/zh-TW/checkpointing.md)。

## 自訂您的工作流程

您可以重新放置 Claude 面板、執行多個對話、將工作階段清單分組或篩選，或切換至終端機模式。

### 選擇 Claude 的位置

您可以拖曳 Claude 面板，將其重新放置在 VS Code 中的任何位置。抓住面板的分頁或標題列，並將其拖曳至：

* **次要側邊欄**：視窗的右側。在撰寫程式碼時讓 Claude 保持可見。
* **主要側邊欄**：帶有檔案總管、搜尋等圖示的左側邊欄。
* **編輯器區域**：將 Claude 以分頁形式開啟在您的檔案旁。適用於附帶任務。

當 Claude 在新的編輯器群組中開啟分頁時，擴充功能會鎖定該群組。之後在 Claude 分頁處於焦點時開啟的檔案，會改為開啟在另一個群組中，而不是在其旁邊。

若要讓擴充功能停止鎖定群組，請關閉 [Lock Editor Groups 設定](vscode://settings/claudeCode.lockEditorGroups)。已鎖定的群組會保持鎖定，直到您將其解除鎖定。此設定需要 Claude Code v2.1.274 或更新版本。

> [!TIP]
>
> 使用側邊欄進行主要的 Claude 工作階段，並為附帶任務開啟額外的分頁。Claude 會記住您偏好的位置。活動列中的工作階段清單圖示與 Claude 面板是分開的。工作階段清單在活動列中始終可見，而 Claude 面板圖示只有在面板停靠於左側邊欄時才會出現在那裡。

### 重新載入後繼續對話

在您執行 **Developer: Reload Window** 或重新啟動 VS Code 後，請確認對話原本開啟的位置：

* **編輯器分頁**：對話會隨其分頁一起恢復。
* **側邊欄**：如果您在過去 10 分鐘內於其中傳送過訊息或 Claude 曾在其中回應，對話就會恢復。如果沒有恢復，請從[工作階段歷史記錄](#resume-past-conversations)恢復對話。

如果提示詞輸入框的位置出現通知，表示該對話仍在其他地方開啟，請參閱[如何在此處繼續對話](#the-conversation-is-still-open-somewhere-else)。如果訊息一開始保持空白，請參閱[為何空白以及何時會出現](#a-resumed-conversation-is-blank-at-first)。

#### 重新載入後中斷的步驟

如果重新載入使 Claude 在步驟進行中被中斷，Claude 會在對話恢復時繼續該步驟，並在聊天中以通知標示此接續。需要 Claude Code v2.1.274 或更新版本。如果該步驟是在一小時以前被中斷，或工作階段在其他地方開啟，對話則會以閒置狀態恢復。

#### 關閉重新載入後的接續

若要讓 Claude 在重新載入後不再繼續中斷的步驟，請開啟 [Continue After Reload 設定](vscode://settings/claudeCode.continueAfterReload)並取消勾選。

如果您在 VS Code 的環境中或在 [`environmentVariables` 設定](#extension-settings)中設定了 [`CLAUDE_CODE_RESUME_INTERRUPTED_TURN`](https://code.claude.com/docs/zh-TW/env-vars#variables) 或任何其他 `CLAUDE_CODE_RESUME_` 變數，它在面板中不會有任何作用。這是因為擴充功能在啟動面板的工作階段之前會移除這些變數。

#### 對話未重新開啟

重新載入後，如果出現一個新的聊天，且其提示詞輸入框上方有類似以下的通知，表示面板讓您的對話保持關閉，因為該對話的最近兩次開啟都未完成：

```text theme={null}
“Fix the login bug” was not reopened. It did not finish opening the last 2 times, and opening it again may stop Claude Code from responding here.
```

當面板在載入對話時當機或停止回應，或者您在對話開啟後約三秒內重新載入或關閉視窗時，開啟就不會完成。對話本身不會改變，並保留在[工作階段歷史記錄](#resume-past-conversations)中。

* **仍要開啟**：點擊 **Open it anyway** 或從工作階段歷史記錄中選取該對話。對話完成開啟後，之後重新載入時它會[照常恢復](#continue-conversations-after-a-reload)。
* **如果面板在載入對話時停止回應**：重新載入視窗。系統會開啟一個新的聊天。
* **保持關閉**：繼續在新的聊天中工作。一旦您傳送提示詞，通知就會消失。

### 執行多個對話

從命令選擇區使用 **Open in New Tab** 或 **Open in New Window** 來開始額外的對話。每個對話都會維護自己的歷史記錄和上下文，讓您可以平行處理不同的任務。

使用分頁時，spark 圖示上的小彩色圓點會指示狀態：藍色表示有待處理的權限請求，橘色表示 Claude 在分頁隱藏期間已完成。

### 將工作階段整理成群組

在活動列的工作階段清單中，您可以將相關的工作階段收集到具名稱、可摺疊的群組中。需要 Claude Code v2.1.229 或更新版本。

* **將工作階段分組或取消分組**：在工作階段上按一下滑鼠右鍵，即可以其建立群組、將其移至現有群組，或將其從所屬群組中移除。每個工作階段一次只屬於一個群組，因此將其移至另一個群組時，會將其從原群組中移除。
* **一次移動多個工作階段**：`Cmd`-點擊（Mac）/ `Ctrl`-點擊（Windows/Linux）每個工作階段，或 `Shift`-點擊以選取一個範圍，然後在選取範圍上按一下滑鼠右鍵。
* **從分頁將工作階段分組**：從命令選擇區執行 **Claude Code: Add Session Tab to Group**，然後選取或建立群組。需要 Claude Code v2.1.257 或更新版本。
* **重新命名或刪除群組**：在群組標題上按一下滑鼠右鍵。刪除群組只會移除群組本身，其工作階段會回到未分組的清單中。

擴充功能會依工作區資料夾儲存群組，因此群組在視窗重新載入後仍會保留，並出現在您開啟相同資料夾的每個視窗中。當您搜尋清單時，擴充功能會將所有群組中的符合項目顯示在單一平面清單中。

### 篩選工作階段清單

若要縮小活動列中冗長的工作階段清單，請使用清單頂端的兩個篩選控制項。需要 Claude Code v2.1.271 或更新版本。只要任一篩選器開啟，已封存的工作階段就不會顯示。

* **Active**：開啟此切換開關，僅顯示需要您輸入、正在處理或未讀的工作階段，以及您最後聚焦的 Claude 分頁中的工作階段。
* **依狀態篩選**：點擊漏斗圖示，然後勾選 **Needs input**、**Working** 或 **Completed**，以顯示處於其中任一狀態的工作階段。勾選 **Open** 或 **Closed**，可依工作階段是否開啟來縮小範圍。當工作階段在此視窗中有分頁，或正在此電腦上的另一個 Claude Code 程序中執行（例如在終端機中）時，即視為開啟。

當 **Active** 開啟且您勾選了某個狀態、**Open** 或 **Closed** 時，清單也會顯示所有符合您勾選項目的工作階段。您設定的篩選器在視窗重新載入後仍會保留。

### 切換至終端機模式

根據預設，擴充功能會開啟圖形化聊天面板。如果您偏好 CLI 風格的介面，請開啟 [Use Terminal 設定](vscode://settings/claudeCode.useTerminal)並勾選該核取方塊。

您也可以在 Mac 上按 `Cmd+,`，或在 Windows/Linux 上按 `Ctrl+,` 開啟 VS Code 設定，前往 **Extensions > Claude Code**，然後勾選 **Use Terminal**。

## 管理外掛

VS Code 擴充功能包含一個圖形化介面，可用於安裝和管理[外掛](https://code.claude.com/docs/zh-TW/plugins/overview.md)。在提示詞輸入框中輸入 `/plugins` 即可開啟 **Manage plugins** 介面。

### 安裝外掛

外掛對話框顯示兩個分頁：**Plugins** 和 **Marketplaces**。

在 Plugins 分頁中：

* **已安裝的外掛**顯示在頂部，並附有切換開關可啟用或停用。
  * 如果您關閉專案共用的 `.claude/settings.json` 所啟用的外掛，擴充功能會先詢問：**Disable for me** 僅為您關閉該外掛，而 **Disable for everyone** 則會變更共用檔案。
  * 載入失敗的外掛會在其列上顯示簡短原因。點擊該原因可查看您能採取的處理方式，包括複製完整的錯誤訊息，以便在[外掛疑難排解](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md)中查詢。
* 來自您已設定之市集的**可用外掛**顯示在下方
* 可依名稱或描述搜尋以篩選外掛
* 在任何可用外掛上點擊 **Install**

安裝外掛時，請選擇安裝範圍：

* **Install for you**：可在您的所有專案中使用（使用者範圍）
* **Install for this project**：與專案協作者共用（專案範圍）
* **Install locally**：僅限您本人，且僅限此儲存庫（本機範圍）

安裝完成後，會出現一個表單，詢問該外掛尚未設定的任何[設定選項](https://code.claude.com/docs/zh-TW/plugins/components.md#user-configuration)。若要稍後檢視或變更這些選項，請點擊外掛列上的齒輪圖示。

敏感的文字欄位會被遮蔽，先前儲存的密鑰會顯示 **(unchanged)**。將欄位留空即可保留已儲存的值。儲存變更後，已開啟的工作階段會重新載入其外掛，且對話框會顯示 **Restart Claude to apply plugin changes**。

### 解除安裝外掛

每個已安裝的列都會標示其安裝所在的[範圍](https://code.claude.com/docs/zh-TW/plugins/install.md#choose-an-install-scope)。若要解除安裝該項安裝，請點擊該列的垃圾桶圖示。變暗的垃圾桶圖示表示該列無法從此工作區解除安裝，例如由您的組織管理的外掛，或是為其他專案安裝的外掛。

擴充功能在以下兩種情況會先詢問：

* **專案共用的 `.claude/settings.json` 所啟用的外掛**：選擇 **Disable for me**，可為您的協作者保留已安裝的外掛；或選擇 **Uninstall for everyone**，以 [`--keep-data`](https://code.claude.com/docs/zh-TW/plugins/cli-reference#what-an-uninstall-deletes-and-keeps) 移除專案的安裝，因此外掛已儲存的資料目錄會保留下來。如果您已為自己關閉該外掛，垃圾桶圖示會直接移除您自己的安裝，不會再詢問。
* **其他情況下，具有已儲存資料之外掛的最後一項安裝**：選擇保留或刪除資料；**Keep** 為預設值

### 分享外掛安裝連結

若要讓某人直接前往安裝特定外掛，請提供擴充功能的 `install-plugin` URL。開啟此 URL 會啟動或聚焦 VS Code、開啟 Claude Code 面板，並開啟 **Manage plugins** 對話框，停在該外掛的範圍選擇畫面。在對方選擇範圍之前，不會安裝任何東西。如果該外掛的市集尚未在對方的 Claude Code 中設定，對話框會先要求對方新增它。

```text theme={null}
vscode://anthropic.claude-code/install-plugin?plugin=code-review&marketplace=anthropics/claude-plugins-official
```

此 URL 接受兩個查詢參數：

| 參數 | 說明 |
| - | - |
| `plugin` | 外掛在其市集中列出的名稱。必填。 |
| `marketplace` | 市集的[來源](https://code.claude.com/docs/zh-TW/plugins/install.md#add-a-marketplace)：GitHub `owner/repo`、`https://` URL，或 git SSH 位址，例如 `git@github.com:owner/repo.git`。省略時預設為 `anthropics/claude-plugins-official`。 |

擴充功能在開啟任何內容之前會檢查這兩個值：

* **外掛名稱**：最多 100 個字元，以 ASCII 字母或數字開頭，其餘僅能使用 ASCII 字母、數字、`.`、`_` 和 `-`。
* **市集來源**：僅限 `marketplace` 參數所列的格式，因此不能是本機路徑、`http://` 位址或市集的名稱（例如 `claude-plugins-official`）。`https://` URL 不能包含使用者名稱、密碼或查詢字串。
* **Git ref**：若要將市集固定至某個分支或標籤，請在來源後方於 `%23`（`#` 的編碼形式）之後附加該 ref，例如 `marketplace=owner/repo%23v1.0`。含有未編碼 `#` 的連結會失敗。`anthropics` GitHub 組織中的市集無法在連結中固定。

開啟違反這些規則之連結的人會看到以 `Invalid plugin installation URL` 開頭的錯誤。Claude Code 面板和對話框都不會開啟，也不會安裝任何東西。如果您的外掛名稱或市集無法放入連結中，請告知使用者先在 **Marketplaces** 分頁中新增市集，再從 **Plugins** 分頁安裝外掛。

以下情況會在對話框中顯示訊息，而非進入範圍選擇：

* **市集中沒有列出該名稱的外掛**：對話框會回報找不到該外掛。請將 `plugin` 值與市集的清單進行比對。
* **該外掛已安裝**：對話框會如此告知，且不會有任何變更。
* **已新增另一個同名的不同市集**：對話框會表示連結中的市集未被新增，且不會安裝任何東西。

GitHub README、issue 以及其他一些 Markdown 託管平台會移除 scheme 不是 `http` 或 `https` 的連結，因此 `vscode://` 連結在那些地方會顯示為純文字。在這些平台上，請將 URL 放入程式碼區塊中，如同[連結顯示為純文字而非可點擊](https://code.claude.com/docs/zh-TW/deep-links.md#the-link-renders-as-plain-text-instead-of-being-clickable)針對 `claude-cli://` 連結所說明的方式。

### 管理市集

切換至 **Marketplaces** 分頁以新增或移除外掛來源：

* 輸入 GitHub 儲存庫、URL 或本機路徑以新增市集
* 點擊重新整理圖示以更新市集的外掛清單
* 點擊垃圾桶圖示以移除市集。移除市集會[解除安裝您從該市集安裝的所有外掛](https://code.claude.com/docs/zh-TW/plugins/install.md#manage-marketplaces)，因此會先顯示確認訊息並列出這些外掛

您在對話框中所做的外掛變更，會立即套用至該 VS Code 視窗中已開啟的 Claude Code 工作階段。

如果您開啟對話框所在的工作階段無法重新載入其外掛，對話框會提供重試或在該工作階段中重新啟動 Claude 的選項。

> [!NOTE]
>
> 擴充功能透過執行與 CLI 相同的命令來管理外掛。您在擴充功能中設定的外掛和市集也可在 CLI 中使用，反之亦然。

如需進一步了解外掛系統，請參閱[外掛](https://code.claude.com/docs/zh-TW/plugins/overview.md)和[外掛市集](https://code.claude.com/docs/zh-TW/plugins/overview.md)。

### 在面板中繪製內容的外掛

包含 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md) 的外掛可以在聊天面板中繪製內容。繪製功能需要擴充功能版本 2.1.299 或更新版本。[不會擷取功能旗標](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)的工作階段（例如在 Amazon Bedrock 上的工作階段）需要 2.1.304 或更新版本。從這類外掛中，您可以看到：

* 位於對話旁或提示詞輸入框上方的窗格
* 位於提示詞輸入框上方的快顯通知或狀態列
* 以外掛自己的方式繪製的訊息或工具呼叫

當您安裝的外掛在面板中新增或變更某些內容時，會有標籤標示該外掛，措辭如下：

* **From the token-chart plugin**：此內容由外掛繪製或輸出，或此卡片是外掛在向您詢問事項
* **Edited by the token-chart plugin**：外掛變更了 Claude Code 所繪製的內容，例如工具呼叫
* **Prompt from the token-chart plugin**：外掛代表您傳送了此訊息

若要阻止外掛繪製內容，請在[外掛對話框](#install-plugins)中關閉該外掛。

## 使用 Chrome 自動化瀏覽器任務

將 Claude 連接到您的 Chrome 瀏覽器，即可在不離開 VS Code 的情況下測試網頁應用程式、透過主控台日誌進行除錯，以及自動化瀏覽器工作流程。此功能需要 [Claude in Chrome 擴充功能](https://chromewebstore.google.com/detail/claude/fcoeoabgfenejglbffodgkkbkcdhcgfn) 1.0.36 或更新版本。

在提示詞輸入框中輸入 `@browser`，接著輸入您希望 Claude 執行的操作：

```text wrap theme={null}
@browser go to localhost:3000 and check the console for errors
```

您也可以開啟附件選單，選取特定的瀏覽器工具，例如開啟新分頁或讀取頁面內容。

Claude 會為瀏覽器任務開啟新分頁，並共用您瀏覽器的登入狀態，因此可以存取任何您已登入的網站。

如需進一步了解瀏覽器的使用方式，請參閱：

* [預設啟用 Chrome](https://code.claude.com/docs/zh-TW/chrome.md#enable-chrome-by-default)：讓每個工作階段在啟動時自動連接到您的瀏覽器，無需輸入 `@browser`
* [VS Code 工作階段中的權限提示](https://code.claude.com/docs/zh-TW/chrome.md#permission-prompts-in-vs-code-sessions)：Claude Code 何時會在執行瀏覽器操作前詢問您
* [搭配 Chrome 使用 Claude Code](https://code.claude.com/docs/zh-TW/chrome.md)：設定說明、完整功能清單及疑難排解

## 使用 git

Claude Code 與 git 整合，協助您直接在 VS Code 中進行版本控制工作流程。要求 Claude 提交變更、建立提取請求或跨分支工作。若要在具有自己的檔案和分支的隔離 worktree 中啟動 Claude，請參閱 [使用 worktrees 執行平行工作階段](https://code.claude.com/docs/zh-TW/worktrees.md)。

### 建立提交和提取請求

Claude 可以暫存變更、撰寫提交訊息，以及根據您的工作建立提取請求：

```text wrap theme={null}
commit my changes with a descriptive message
create a pr for this feature
summarize the changes I've made to the auth module
```

建立提取請求時，Claude 會根據實際的程式碼變更產生描述，並可以新增有關測試或實作決策的內容。

### 重新開啟已移至 worktree 的對話

在重新開啟的對話中，**This session is in worktree** 橫幅表示該對話的工作目錄是橫幅所指名的 [worktree](https://code.claude.com/docs/zh-TW/worktrees.md)，而非此視窗所開啟的資料夾。若要在新的 VS Code 視窗中開啟該 worktree，請按一下橫幅上的 **Open worktree**。

例如，當您[要求 Claude 在某個 worktree 中工作](https://code.claude.com/docs/zh-TW/worktrees.md#ask-claude-to-create-a-worktree)時，對話就會移至該 worktree。當您重新開啟對話，或面板[在視窗重新載入後重新開啟對話](#continue-conversations-after-a-reload)時，如果該 worktree 是由 Claude Code 在 `.claude/worktrees/` 下建立且仍然存在，對話就會在該 worktree 中繼續。在 Claude Code v2.1.300 之前，會改為開啟一個空白對話。若使用這些版本，請更新擴充功能。

## 在背景執行工作

將長時間執行的命令或 subagent 移至背景，然後從提示詞輸入框查看其狀態。

### 將執行中的命令或 subagent 移至背景

當某個命令或 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 讓 Claude 等待的時間超出您的預期時，請點擊對話中其工具呼叫下方的 **Run in background**。需要 Claude Code v2.1.287 或更新版本。

* **時機**：命令執行約兩秒後，或 Claude 一開始等待其從主對話產生的 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#run-subagents-in-foreground-or-background)，此操作就會出現。
* **點擊之後**：Claude 會停止等待並繼續該回合。命令或 subagent 會以[背景任務](https://code.claude.com/docs/zh-TW/tools-reference.md#background-commands)的形式持續執行，並在完成時通知 Claude。

若要在此期間查看任務狀態或停止任務，請在提示詞輸入框中輸入 `/tasks` 以開啟 [agent 地圖](#use-the-prompt-box)。subagent 會在其中的 agent 樹狀結構中保有其位置，而命令則列於 agent 下方，並在[其卡片上顯示最新輸出](#monitor-background-processes)。

#### subagent 下方沒有 Run in background 操作

在 VS Code 中，subagent 預設不會顯示此操作。若要了解某個 subagent 的原因，請在 [agent 地圖](#use-the-prompt-box)中開啟其卡片，並查看 `Spawned by` 這一行：

* **`Spawned by the main agent`**：該 subagent 是在背景啟動的，因此 Claude 並未等待它，您無需進行任何操作。若要讓 Claude 改為等待 subagent，請參閱[讓 Claude 等待 subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#let-claude-wait-for-a-subagent)。
* **`Spawned by` 列出的是另一個 subagent**：此操作只會出現在由主 agent 產生的 subagent 上，而不會出現在另一個 subagent 正在等待的[巢狀 subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#let-subagents-spawn-their-own-subagents) 上。若要提前結束巢狀 subagent，請點擊其卡片上的 **Stop agent**。正在等待的 subagent 隨後會在沒有該結果的情況下繼續執行。

### 監控背景程序

在提示詞輸入框中輸入 `/tasks` 以開啟 [agent 地圖](#use-the-prompt-box)，其中會列出工作階段的背景任務，例如 Claude 以背景 shell 命令形式持續執行的開發伺服器。點擊任務即可開啟其卡片，並可在卡片中停止該任務。需要 Claude Code v2.1.277 或更新版本。

對於背景 shell 命令，或執行命令的 [monitor](https://code.claude.com/docs/zh-TW/tools-reference.md#monitor-tool)，卡片也會顯示該命令的最新輸出，並在命令執行期間持續更新。

#### 查看背景 subagent 的工具呼叫

當某個 subagent 僅顯示為一行狀態列而沒有任何工具呼叫時，請在提示詞輸入框中輸入 `/tasks` 以開啟 [agent 地圖](#use-the-prompt-box)，並在其中點擊該 subagent。該 subagent 正[在背景執行](#the-run-in-background-action-is-missing-under-a-subagent)，其卡片會顯示其工具呼叫，以及一個可開啟其逐字稿的按鈕。

## VS Code 命令與快捷鍵

若要開啟命令選擇區，請在 Mac 上按 `Cmd+Shift+P`，或在 Windows/Linux 上按 `Ctrl+Shift+P`。在其中輸入「Claude Code」，即可查看 Claude Code 擴充功能所有可用的 VS Code 命令。

部分快捷鍵取決於目前「聚焦」的面板（接收鍵盤輸入的面板）。當游標位於程式碼檔案中時，編輯器處於聚焦狀態。當游標位於 Claude 的提示詞輸入框中時，Claude 處於聚焦狀態。使用 `Cmd+Esc` / `Ctrl+Esc` 在兩者之間切換。

> [!NOTE]
>
> 這些是用於控制擴充功能的 VS Code 命令。並非所有 Claude Code 內建命令都可在擴充功能中使用。詳情請參閱 [VS Code 擴充功能與 Claude Code CLI 的比較](#vs-code-extension-vs-claude-code-cli)。

| 命令 | 快捷鍵 | 說明 |
| - | - | - |
| Focus Input | `Cmd+Esc` (Mac) / `Ctrl+Esc` (Windows/Linux) | 在編輯器與 Claude 之間切換焦點 |
| Focus last message | - | 將鍵盤焦點移至對話中最新的訊息或等待中的權限提示，以便從該處使用鍵盤或螢幕閱讀器閱讀。無法在[終端機模式](#switch-to-terminal-mode)中使用。需要 Claude Code v2.1.268 或更新版本 |
| Open in Side Bar | - | 在側邊欄中開啟 Claude |
| Open in Terminal | - | 以終端機模式開啟 Claude |
| Open in New Tab | `Cmd+Shift+Esc` (Mac) / `Ctrl+Shift+Esc` (Windows/Linux) | 以編輯器分頁開啟新對話 |
| Open in New Window | - | 在獨立視窗中開啟新對話 |
| New Conversation | `Cmd+N` (Mac) / `Ctrl+N` (Windows/Linux) | 開始新對話。需要 Claude 處於聚焦狀態，且 `enableNewConversationShortcut` 設為 `true` |
| Reopen Closed Session | `Cmd+Shift+T` (Mac) / `Ctrl+Shift+T` (Windows/Linux) | 重新開啟最近關閉的 Claude 工作階段分頁。若最後關閉的分頁不是 Claude 工作階段，則改為執行 VS Code 一般的重新開啟已關閉編輯器功能。可透過 `enableReopenClosedSessionShortcut` 停用 |
| Insert @-Mention Reference | `Option+K` (Mac) / `Alt+K` (Windows/Linux) | 插入目前檔案與選取範圍的參照（需要編輯器處於聚焦狀態） |
| Accept Change at Cursor | - | 在逐一[檢閱提議的編輯](#get-started)時，接受游標所在處的變更。需要 Claude Code v2.1.275 或更新版本 |
| Reject Change at Cursor | - | 在逐一檢閱提議的編輯時，還原游標所在處的變更。需要 Claude Code v2.1.275 或更新版本 |
| Toggle Focus view | `Ctrl+Option+F` (Mac) / `Ctrl+Alt+F` (Windows/Linux) | 隱藏或顯示對話中的工具活動。在 Claude 面板或側邊欄可見時有效。在 Windows/Linux 上，當焦點位於偵錯主控台或可搜尋的清單（例如檔案總管）時，`Ctrl+Alt+F` 會改為開啟 VS Code 的尋找功能。請將焦點移至編輯器或 Claude 面板後再按一次。需要 Claude Code v2.1.221 或更新版本 |
| Rename Session Tab | - | 重新命名目前 Claude 分頁中的工作階段。需要 Claude Code v2.1.257 或更新版本 |
| Add Session Tab to Group | - | 將目前 Claude 分頁中的工作階段加入您選取或建立的[工作階段群組](#organize-sessions-into-groups)。需要 Claude Code v2.1.257 或更新版本 |
| Mark Session as Unread | - | 在工作階段清單中將目前 Claude 分頁中的工作階段標示為未讀。需要 Claude Code v2.1.257 或更新版本 |
| Show Logs | - | 檢視擴充功能偵錯日誌 |
| Logout | - | 登出您的 Anthropic 帳戶 |

### 從其他工具啟動 VS Code 分頁

擴充功能會在 `vscode://anthropic.claude-code/open` 註冊一個 URI 處理常式。您可以使用它從自己的工具開啟新的 Claude Code 分頁：shell 別名、瀏覽器書籤小程式，或任何可開啟 URL 的指令碼。若 VS Code 尚未執行，開啟此 URL 會先啟動 VS Code。若 VS Code 已在執行中，URL 會在目前聚焦的視窗中開啟。

使用作業系統的 URL 開啟工具來呼叫此處理常式。

> [tab] macOS
>
> ```bash theme={null}
> open "vscode://anthropic.claude-code/open"
> ```

> [tab] Linux
>
> ```bash theme={null}
> xdg-open "vscode://anthropic.claude-code/open"
> ```
>
> `xdg-open` 命令來自 `xdg-utils` 套件。若 shell 回報找不到此命令，請參閱[在 Linux 上找不到 xdg-open](https://code.claude.com/docs/zh-TW/deep-links.md#xdg-open-is-not-found-on-linux)。

> [tab] Windows
>
> 在 PowerShell 中：
>
> ```powershell theme={null}
> Start-Process "vscode://anthropic.claude-code/open"
> ```
>
> 在 `cmd.exe` 中，`start` 會將第一個加上引號的引數視為視窗標題，因此請在 URL 之前傳入空白標題：
>
> ```cmd theme={null}
> start "" "vscode://anthropic.claude-code/open"
> ```

此處理常式接受兩個選用的查詢參數：

| 參數 | 說明 |
| - | - |
| `prompt` | 要預先填入提示詞輸入框的文字。必須經過 URL 編碼。提示詞會預先填入，但不會自動送出。 |
| `session` | 要繼續的工作階段 ID，來自目前在 VS Code 中開啟的資料夾。使用 Claude Code v2.1.300 或更新版本時，來自該資料夾儲存庫的主要 checkout 或 [worktree](https://code.claude.com/docs/zh-TW/worktrees.md) 的工作階段也能繼續。若找不到該工作階段，則會改為開始新的對話。若該工作階段已在某個分頁中開啟，則會聚焦該分頁。若要以程式方式取得工作階段 ID，請參閱[繼續對話](https://code.claude.com/docs/zh-TW/headless.md#continue-conversations)。 |

例如，若要開啟預先填入「review my changes」的分頁：

```text theme={null}
vscode://anthropic.claude-code/open?prompt=review%20my%20changes
```

擴充功能也會處理 `vscode://anthropic.claude-code/install-plugin`，它會[針對單一外掛開啟外掛對話方塊](#share-a-plugin-install-link)。若要啟動終端機工作階段而非 VS Code 分頁，請使用 CLI 的 `claude-cli://` 處理常式。請參閱[從連結啟動工作階段](https://code.claude.com/docs/zh-TW/deep-links.md)。

## 設定

您可以在兩個地方設定此擴充功能：VS Code 的擴充功能設定，以及 Claude Code 設定檔：

* VS Code 中的**擴充功能設定**：控制擴充功能在 VS Code 中的行為。使用 `Cmd+,`（Mac）或 `Ctrl+,`（Windows/Linux）開啟，然後前往 **Extensions > Claude Code**。您也可以輸入 `/` 並選取 **General config…** 來開啟設定。
* `~/.claude/settings.json` 中的 **Claude Code 設定**：由擴充功能與 CLI 共用。用於允許的命令、環境變數、hook 和 MCP 伺服器。在 Claude Code v2.1.283 或更新版本中，它也是決定對話起始權限模式的依據之一；在較早的版本中，僅適用於 Pro、Max、Ultra 和 Team 方案。[切換權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md#switch-permission-modes)列出了其優先順序。詳情請參閱[設定](https://code.claude.com/docs/zh-TW/settings.md)。

> [!TIP]
>
> 將 `"$schema": "https://json.schemastore.org/claude-code-settings.json"` 新增至您的 `settings.json`，即可直接在 VS Code 中取得所有可用設定的自動完成與行內驗證。

### 擴充功能設定

VS Code 會從您的使用者設定讀取 `initialPermissionMode`，並忽略工作區的值。在 v2.1.225 之前，VS Code 會將此設定預設為 `default`，並套用工作區的值。

| 設定 | 預設值 | 說明 |
| - | - | - |
| `useTerminal` | `false` | 以終端機模式而非圖形面板啟動 Claude |
| `initialPermissionMode` | - | 控制新對話的核准提示：`default`、`plan`、`acceptEdits` 或 `bypassPermissions`。`manual` 是 `default` 的別名，會選取模式指示器中標示為 **Manual** 的模式。若未設定，擴充功能會依照[切換權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md#switch-permission-modes)中的說明選擇起始權限模式。 |
| `preferredLocation` | `panel` | Claude 開啟的位置：`sidebar`（右側）或 `panel`（新分頁） |
| `lockEditorGroups` | `true` | [鎖定 Claude 為其分頁啟動的編輯器群組](#choose-where-claude-lives)，讓您在 Claude 分頁處於焦點時開啟的檔案會移至其他群組。關閉時，擴充功能永遠不會鎖定編輯器群組。需要 Claude Code v2.1.274 或更新版本 |
| `autosave` | `true` | 在 Claude 讀取或寫入檔案前自動儲存檔案 |
| `attachOpenFile` | `true` | 將編輯器中開啟的檔案新增至您的訊息，並顯示在提示詞輸入框中。關閉時，只有在連同您選取的文字一起時才會新增該檔案。需要 Claude Code v2.1.271 或更新版本 |
| `attachSelection` | `true` | 將您在編輯器中選取的文字新增至您的訊息，並顯示在提示詞輸入框中。關閉時，您仍可[將選取內容以 @-mention 形式新增](#automatic-context-from-your-selection-and-open-file)。需要 Claude Code v2.1.300 或更新版本 |
| `useCtrlEnterToSend` | `false` | 使用 Ctrl/Cmd+Enter 而非 Enter 傳送提示詞 |
| `scrollToBottomOnSend` | `true` | 傳送訊息時將對話捲動至底部。關閉時，對話會停留在您離開時的位置。需要 Claude Code v2.1.275 或更新版本 |
| `showMessageTimestamps` | `true` | 顯示每則訊息的傳送時間。日期行會標示日期變更之處。需要 Claude Code v2.1.284 或更新版本。在 v2.1.290 之前，預設值為 `false` |
| `spinnerVerbs` | `{"mode": "append", "verbs": []}` | 設定回合執行期間對話旋轉指示器輪流顯示的動詞，使用與 CLI 的 [`spinnerVerbs`](https://code.claude.com/docs/zh-TW/settings-reference#spinnerverbs) 相同的 `mode` 和 `verbs` 欄位。 |
| `enableNewConversationShortcut` | `false` | 啟用 Cmd/Ctrl+N 以開始新對話 |
| `enableReopenClosedSessionShortcut` | `true` | 使用 Cmd/Ctrl+Shift+T 重新開啟最近關閉的 Claude 工作階段分頁。當最後關閉的分頁不是 Claude 工作階段時，此快速鍵會改為執行 VS Code 一般的重新開啟已關閉編輯器命令。 |
| `archiveInactiveSessions` | `14` | 在沒有活動達此天數後[自動封存工作階段](#resume-past-conversations)：`1`、`2`、`7` 或 `14`。設定為 `0` 即可關閉。需要 Claude Code v2.1.265 或更新版本 |
| `continueAfterReload` | `true` | 視窗重新載入後，Claude 會在還原的工作階段中[繼續被中斷的步驟](#continue-conversations-after-a-reload)。需要 Claude Code v2.1.274 或更新版本 |
| `hideOnboarding` | `false` | 隱藏入門檢查清單（學士帽圖示） |
| `focusView` | `false` | 將工具呼叫、工具結果和思考隱藏在可展開的列中，只留下您的提示詞和 Claude 的回應。Claude 最新的待辦事項清單會保持可見；這需要 Claude Code v2.1.225 或更新版本。您也可以從命令選單切換 Focus view。需要 Claude Code v2.1.221 或更新版本 |
| `respectGitIgnore` | `true` | 從檔案搜尋和[選取內容脈絡](#selected-text-from-excluded-or-ignored-files)中排除 .gitignore 模式 |
| `usePythonEnvironment` | `true` | 執行 Claude 時啟用工作區的 Python 環境。需要 Python 擴充功能。 |
| `environmentVariables` | `[]` | 為 Claude 程序設定環境變數。若要共用設定，請改用 Claude Code 設定。[`CLAUDE_CONFIG_DIR`](https://code.claude.com/docs/zh-TW/env-vars) 項目僅在其值為絕對路徑時才會套用；擴充功能不會展開 `~`，並會忽略相對路徑值。 |
| `disableLoginPrompt` | `false` | 略過身分驗證提示（適用於第三方供應商設定） |
| `allowDangerouslySkipPermissions` | `false` | 將 Bypass permissions 新增至模式選擇器。僅在沒有網際網路存取的沙箱中使用。 |
| `claudeProcessWrapper` | - | 用於啟動 Claude 程序的可執行檔。若存在隨附的二進位檔，其路徑會作為引數傳入。如果擴充功能的建置未包含適用於您平台的二進位檔，請將此設定為另外安裝的 `claude` 二進位檔。 |

## 使用第三方供應商

預設情況下，Claude Code 會直接連線至 Anthropic 的 API。如果您的組織使用 Amazon Bedrock、Google Cloud 的 Agent Platform 或 Microsoft Foundry 來存取 Claude，請將擴充功能設定為改用您的供應商：

**1. 停用登入提示**

開啟 [Disable Login Prompt 設定](vscode://settings/claudeCode.disableLoginPrompt)並勾選該核取方塊。

您也可以在 Mac 上按 `Cmd+,`，或在 Windows/Linux 上按 `Ctrl+,` 開啟 VS Code 設定，搜尋「Claude Code login」，然後勾選 **Disable Login Prompt**。

**2. 設定您的供應商**

請依照您供應商的設定指南操作：

* [在 Amazon Bedrock 上使用 Claude Code](https://code.claude.com/docs/zh-TW/amazon-bedrock.md)
* [在 Google Cloud 的 Agent Platform 上使用 Claude Code](https://code.claude.com/docs/zh-TW/google-vertex-ai.md)
* [在 Microsoft Foundry 上使用 Claude Code](https://code.claude.com/docs/zh-TW/microsoft-foundry.md)

這些指南說明如何在 `~/.claude/settings.json` 中設定您的供應商，以確保您的設定在 VS Code 擴充功能與 CLI 之間共用。

使用第三方供應商時，擴充功能不提供需要 claude.ai 帳戶的功能，例如方案用量列、[語音聽寫](https://code.claude.com/docs/zh-TW/voice-dictation.md)，以及用於[雲端工作階段](#resume-cloud-sessions-from-claude-ai)的 Web 分頁。關於 Account & usage 對話方塊在這些登入方式下顯示的內容，請參閱[檢查帳戶與用量](#check-account-and-usage)。

先前透過 `/login` 留下的 claude.ai 登入資訊會維持未使用狀態：擴充功能不會在任何請求中傳送它。

## 使用螢幕閱讀器

擴充功能的聊天面板可搭配螢幕閱讀器使用。您不需要開啟任何設定：擴充功能會為每位使用者朗讀對話活動，且不會有任何視覺上的變化。這與 CLI 需自行啟用的[螢幕閱讀器模式](https://code.claude.com/docs/zh-TW/accessibility.md)不同，後者會調整終端機介面。

聊天面板的螢幕閱讀器支援需要 Claude Code v2.1.236 或更新版本。

在對話期間，擴充功能會朗讀：

* **Claude 的回覆**：擴充功能會在每則回覆完成時朗讀一次，文字串流輸出期間則保持靜默。螢幕閱讀器會將程式碼區塊朗讀為行數摘要，以標籤朗讀連結，並逐一儲存格朗讀表格；完整回覆仍可在逐字稿中閱讀。
* **權限請求與問題**：當權限提示出現時，擴充功能會朗讀該請求，並說出 Claude 想要使用的工具名稱。當 Claude 向您提出問題，以及 Claude 完成計畫並等待您審閱時，擴充功能也會以相同方式朗讀。
* **狀態變更**：擴充功能會在 Claude 開始工作、Claude 準備好接收您的輸入，以及 Claude Code 開始壓縮對話時進行朗讀。如果您在工作階段的 [SessionStart](https://code.claude.com/docs/zh-TW/hooks.md#sessionstart) hook 仍在執行時傳送提示詞，螢幕閱讀器也會朗讀「Running start-up hooks.」。
* **已排入佇列的訊息**：當您在 Claude 工作時傳送訊息，擴充功能會針對該訊息朗讀「Message queued.」。
* **錯誤與模型提示**：擴充功能會朗讀對話中的錯誤，並在[用量點數同意提示](https://code.claude.com/docs/zh-TW/model-config.md#fable-and-usage-credits)或[已標記請求提示](https://code.claude.com/docs/zh-TW/model-config.md#ask-before-switching)出現時進行朗讀。

Claude 工作期間，螢幕閱讀器會朗讀文字標籤，以取代進度旋轉圖示的動畫。

當您重新開啟工作階段或切換至其他工作階段時，擴充功能不會朗讀任何內容：還原的歷史記錄、待處理的權限提示，以及進行中的狀態都會保持靜默，直到有新的事件發生。

### 使用鍵盤操作聊天面板

逐字稿中的每個回合都以一個視覺上隱藏的標題開頭，該標題以開啟該回合的提示詞作為標籤。使用螢幕閱讀器的標題導覽功能即可在各回合之間跳轉。

在一個回合中移動時，螢幕閱讀器會朗讀您目前所在的是誰的訊息：

* **您的訊息**：「You」
* **Claude 的訊息**：「Claude」
* **工具步驟**：「Claude」加上工具名稱，例如「Claude, Bash」
* **思考區塊**：「Claude, thinking」

由於擴充功能將逐字稿公開為具標籤的區域，您也可以使用 `Tab` 將焦點移至逐字稿本身，並依自己的步調閱讀。若要改為將焦點移至最新訊息或等待中的權限提示，請從[命令選擇區](#vs-code-commands-and-shortcuts)執行 **Claude Code: Focus last message**。

當權限提示選項會儲存權限規則或目錄存取權時，其標籤結尾會說明核准的儲存位置，例如「all projects」或「this session」。若要變更儲存位置：

* 在該選項取得焦點時，按下 `Left` 或 `Right` 方向鍵。當您移至每個儲存位置時，擴充功能都會朗讀該位置。方向鍵功能需要 Claude Code v2.1.268 或更新版本。
* 點擊標籤中的儲存位置。

## VS Code 擴充功能與 Claude Code CLI 的比較

Claude Code 同時提供 VS Code 擴充功能（圖形化面板）與 CLI（終端機中的命令列介面）兩種形式。部分功能僅在 CLI 中提供。若需要使用僅限 CLI 的功能，請在 VS Code 的整合式終端機中執行 `claude`。這需要先進行 [獨立 CLI 安裝](https://code.claude.com/docs/zh-TW/setup.md)：擴充功能不會將 `claude` 加入您的 PATH。請參閱[在 VS Code 中執行 CLI](#run-cli-in-vs-code)。

| 功能 | CLI | VS Code 擴充功能 |
| - | - | - |
| 命令與 skill | [全部](https://code.claude.com/docs/zh-TW/commands.md) | 部分（輸入 `/` 以查看可用項目） |
| MCP 伺服器設定 | 是 | 是：在聊天面板中使用 `/mcp` [新增與管理伺服器](#connect-to-external-tools-with-mcp) |
| 檢查點 | 是 | 是 |
| `!` Bash 快捷方式 | 是 | 否 |
| Tab 自動完成 | 是 | 否 |

### 在 VS Code 中執行 CLI

若要在不離開 VS Code 的情況下使用 CLI，請在 Windows/Linux 上按 `` Ctrl+` ``，或在 Mac 上按 `` Cmd+` `` 開啟整合式終端機，然後執行 `claude`。啟動 `claude` 並不會安裝擴充功能。若未安裝擴充功能，在整合式終端機中執行 `/ide` 會回報「No available IDEs detected」，而 `/status` 會將 IDE 顯示為「Not connected」。

若要取得差異檢視與診斷資訊共享等功能，請從整合式終端機或外部終端機將 CLI 連線至擴充功能：

* **整合式終端機**：[安裝擴充功能](#install-the-extension)，然後啟動 `claude`。CLI 會自動連線。
* **外部終端機**：在 Claude Code 中執行 `/ide` 以連線至 VS Code。若 VS Code 正在執行但未安裝擴充功能，`/ide` 會自動安裝它，除非您已關閉 [`autoInstallIdeExtension`](https://code.claude.com/docs/zh-TW/settings-reference#autoinstallideextension)。

安裝擴充功能並不會將 `claude` 加入您的 shell PATH。擴充功能內含一份供其聊天面板使用的私有 CLI 副本，但若要在終端機中輸入 `claude`，則需要進行[獨立 CLI 安裝](https://code.claude.com/docs/zh-TW/setup.md)。只需執行一次安裝，本頁面中的命令（包括 `claude mcp add` 與 `claude --resume`）即可在任何終端機中運作。若安裝後仍找不到 `claude`，請[驗證您的 PATH](https://code.claude.com/docs/zh-TW/troubleshoot-install.md#verify-your-path)。

### 在擴充功能與 CLI 之間切換

擴充功能與 CLI 共用相同的對話記錄。若要在 CLI 中繼續擴充功能中的對話，請在終端機中執行 `claude --resume`。這會開啟一個互動式選擇器，供您搜尋並選取對話。

## 使用 MCP 連接外部工具

MCP (Model Context Protocol) 伺服器讓 Claude 能夠存取外部工具、資料庫和 API。

若要在不離開 VS Code 的情況下管理 MCP 伺服器，請在聊天面板中輸入 `/mcp`。在開啟的對話框中，您可以：

* 新增伺服器
* 移除儲存在 local、user 或 project [範圍](https://code.claude.com/docs/zh-TW/mcp.md#mcp-installation-scopes)的伺服器
* 啟用或停用伺服器
* 重新連線至伺服器
* 管理 OAuth 身分驗證

在對話框中新增和移除伺服器需要 Claude Code v2.1.261 或更新版本。

您也可以在 VS Code 的整合式終端機（`` Ctrl+` `` 或 `` Cmd+` ``）中執行 `claude mcp add`。對話框與終端機命令會儲存至相同的 MCP 設定，且透過任一方式所做的變更，都會在您之後開始的對話中生效。以下範例新增 GitHub 的遠端 MCP 伺服器，該伺服器使用以標頭傳遞的[個人存取 token](https://github.com/settings/personal-access-tokens) 進行身分驗證：

```bash theme={null}
claude mcp add --transport http github https://api.githubcopilot.com/mcp/ \
  --header "Authorization: Bearer YOUR_GITHUB_PAT"
```

請將 `YOUR_GITHUB_PAT` 替換為您的個人存取 token。`claude mcp add` 命令會儲存設定而不驗證憑證，因此此處會接受預留位置值，但伺服器稍後會無法連線。若要驗證連線，請開始新的對話，輸入 `/mcp`，並確認伺服器顯示 **Connected**。憑證錯誤的伺服器會顯示 **Failed**。

設定完成後，即可要求 Claude 使用這些工具（例如「Review PR #456」）。

> [!NOTE]
>
> 若要尋找可連接的伺服器，請參閱[尋找和建置 MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md#find-and-build-mcp-servers)。

## 內建的 IDE MCP 伺服器

擴充功能啟用時，會執行一個本機 MCP 伺服器，CLI 會自動連線到該伺服器。透過此伺服器，CLI 會：

* 在 VS Code 的原生差異檢視器中開啟差異
* 讀取您目前的選取範圍以供 `@` 提及使用
* 在您使用 Jupyter notebook 時，要求 VS Code 執行儲存格

此伺服器名為 `ide`，且不會顯示在 `/mcp` 中，因為沒有任何需要設定的項目。不過，如果您的組織使用 `PreToolUse` hook 將 MCP 工具加入允許清單，您就需要知道它的存在。

**選取範圍與開啟檔案的上下文。** 連線期間，CLI 會在您送出的每個提示詞中，將您目前的編輯器選取範圍以及作用中檔案的路徑作為上下文一併附上。發生這種情況時，逐字稿會顯示一行 `⧉ Selected N lines from <file>`。以下情況會改變該上下文：

* **關閉 [Attach Selection 設定](#keep-your-selection-and-open-file-out-of-your-messages)**：CLI 不會將您的選取範圍作為上下文附上。
* **關閉 Attach Open File 設定**：CLI 只有在同時附上選取範圍時，才會附上作用中檔案的路徑。
* **佇列中的訊息**：如果您[在 Claude 工作時將訊息加入佇列](https://code.claude.com/docs/zh-TW/interactive-mode.md#queue-messages-while-claude-works)，該訊息會保留您按下 `Enter` 時的選取範圍，無論您之後選取了什麼。
* **敏感檔案**：若要排除 `.env` 等敏感檔案，請為其路徑新增 [`Read` 拒絕規則](https://code.claude.com/docs/zh-TW/permissions#read-and-edit)。相符的拒絕規則會阻止該檔案的選取文字和開啟檔案通知傳送給 Claude。

**傳輸與身分驗證。** 伺服器會繫結到 `127.0.0.1` 上 10000–65535 範圍內的隨機連接埠，且該連接埠無法設定。傳輸方式與驗證 token 的運作方式如下：

* **傳輸**：未加密的 `ws://`。由於通訊端僅限迴路介面，任何能夠擷取流量的程序也都能從鎖定檔讀取 token，因此 TLS 並不會增加保護。
* **驗證 token**：每次擴充功能啟用時，都會產生一個新的隨機驗證 token，並將其寫入位於 `~/.claude/ide/<port>.lock` 的鎖定檔。CLI 必須以 `X-Claude-Code-Ide-Authorization` 標頭提供該 token 才能連線。
* **鎖定檔權限**：鎖定檔在 `0700` 目錄中具有 `0600` 權限，因此只有執行 VS Code 的使用者能夠讀取。如果設定了 `CLAUDE_CONFIG_DIR`，鎖定檔則會改為寫入 `$CLAUDE_CONFIG_DIR/ide/`。

**向模型公開的工具。** 此伺服器提供十幾個工具，但只有兩個對模型可見。其餘皆為 CLI 用於自身 UI 的內部 RPC，例如開啟差異、讀取選取範圍以及儲存檔案。這些工具會在工具清單傳送給 Claude 之前被過濾掉。

| 工具名稱（hook 所見） | 功能 | 唯讀 |
| - | - | - |
| `mcp__ide__getDiagnostics` | 傳回語言伺服器診斷資訊：即 VS Code 問題面板中的錯誤與警告。可選擇限定於單一檔案。 | 是 |
| `mcp__ide__executeCode` | 在作用中 Jupyter notebook 的核心中執行 Python 程式碼。請參閱下方的確認流程。 | 否 |

**聊天面板中的診斷。** 在聊天面板中，使用 Claude Code v2.1.285 或更新版本時，Claude 會透過另一個名為 `claude-vscode` 的內建伺服器讀取 VS Code 的問題面板。Claude 可以向它詢問單一檔案中，或 VS Code 擁有診斷資訊的所有檔案中目前的錯誤與警告。

hook 與權限規則會將聊天面板的診斷工具視為 `mcp__claude-vscode__getDiagnostics`。若要同時涵蓋 CLI 與聊天面板中的診斷，請在您的 hook 或規則中同時指定 `mcp__ide__getDiagnostics` 和 `mcp__claude-vscode__getDiagnostics`。

以下 `settings.json` 範例會拒絕這兩個工具：

```json theme={null}
{
  "permissions": {
    "deny": [
      "mcp__ide__getDiagnostics",
      "mcp__claude-vscode__getDiagnostics"
    ]
  }
}
```

`Read` 拒絕規則不涵蓋這兩個工具中的任何一個，因此請如範例所示，使用[拒絕規則](https://code.claude.com/docs/zh-TW/permissions.md#mcp)依名稱封鎖它們。

**Jupyter 執行一律會先詢問。** `mcp__ide__executeCode` 無法在無聲無息的情況下執行任何內容。每次呼叫都會經過以下步驟：

1. 程式碼會以新儲存格的形式插入到作用中 notebook 的末尾。
2. VS Code 會捲動畫面以顯示該儲存格。
3. 原生的 Quick Pick 會詢問您要 **Execute** 還是 **Cancel**。

取消，或以 `Esc` 關閉選擇器，會向 Claude 傳回錯誤，且不會執行任何內容。當沒有作用中的 notebook、未安裝 Jupyter 擴充功能（`ms-toolsai.jupyter`），或核心不是 Python 時，此工具也會直接拒絕執行。

> [!NOTE]
>
> Quick Pick 確認與 `PreToolUse` hook 是分開的。`mcp__ide__executeCode` 的允許清單項目讓 Claude 能夠*提議*執行儲存格；而 VS Code 內的 Quick Pick 才是讓它*實際*執行的關鍵。

## 修正常見問題

登入、網路和啟動錯誤在安裝疑難排解和錯誤參考頁面中各有專門的條目。請在表格中找到您看到的內容，然後點擊連結。

| 您看到的內容 | 前往位置 |
| - | - |
| 登入後出現 `API Error: 403 Request not allowed` | [登入後出現 403 Forbidden](https://code.claude.com/docs/zh-TW/troubleshoot-install.md#403-forbidden-after-login) |
| 已登入後仍被要求再次登入 | [未登入或 token 已過期](https://code.claude.com/docs/zh-TW/troubleshoot-install.md#not-logged-in-or-token-expired) |
| 雲端供應商憑證在終端機中可用，但在擴充功能中無法使用 | [Bedrock、Agent Platform 或 Foundry 憑證未載入](https://code.claude.com/docs/zh-TW/troubleshoot-install.md#bedrock-agent-platform-or-foundry-credentials-not-loading) |
| `SSL certificate verification failed` 或 `Self-signed certificate detected` | [SSL 憑證錯誤](https://code.claude.com/docs/zh-TW/errors.md#ssl-certificate-errors) |
| `Dictation error: WebSocket error:` 後面接著憑證錯誤（例如 `unable to get local issuer certificate`），或 Web 分頁上出現 `Remote server is not connected` | [聽寫或 Web 分頁在 TLS 檢查代理伺服器後方失敗](#dictation-or-the-web-tab-fails-behind-a-tls-inspecting-proxy) |
| `Claude Code process exited with code 1` 或其他代碼 | [Claude Code process exited with code N](https://code.claude.com/docs/zh-TW/errors.md#claude-code-process-exited-with-code-n) |
| `Could not locate the Claude CLI on PATH` | [Could not locate the Claude CLI on PATH](https://code.claude.com/docs/zh-TW/errors.md#could-not-locate-the-claude-cli-on-path) |
| `The connection to Claude Code ended before this message completed` | [The connection to Claude Code ended before this message completed](https://code.claude.com/docs/zh-TW/errors.md#the-connection-to-claude-code-ended-before-this-message-completed) |
| `The Claude Code program for this computer, the <build> build, could not be found` | [The Claude Code program for this computer could not be found](https://code.claude.com/docs/zh-TW/errors.md#the-claude-code-program-for-this-computer-could-not-be-found) |
| 在 VS Code 的整合式終端機中找不到 `claude` | [在 VS Code 中執行 CLI](#run-cli-in-vs-code) |

### 擴充功能無法安裝

* 確保您使用相容的 VS Code 版本（1.94.0 或更新版本）
* 檢查 VS Code 是否具有安裝擴充功能的權限
* 嘗試直接從 [Visual Studio Marketplace](https://marketplace.visualstudio.com/items?itemName=anthropic.claude-code) 安裝

### 看不到 Spark 圖示

當您開啟檔案時，Spark 圖示會出現在**編輯器工具列**（編輯器右上角）中。如果您沒有看到它：

1. **開啟檔案**：此圖示需要開啟檔案。僅開啟資料夾是不夠的。
2. **檢查 VS Code 版本**：需要 1.94.0 或更新版本。請在 **Help > About** 中查看
3. **重新啟動 VS Code**：從命令選擇區執行「Developer: Reload Window」
4. **停用衝突的擴充功能**：暫時停用其他 AI 擴充功能（Cline、Continue 等）
5. **檢查工作區信任**：擴充功能在受限模式下無法運作

或者，點擊視窗右下角**狀態列**中的 **✻ Claude Code**。即使沒有開啟檔案，此方法也能運作。您也可以使用**命令選擇區**（`Cmd+Shift+P` / `Ctrl+Shift+P`）並輸入「Claude Code」。

### 在 macOS 上按 Cmd+Esc 沒有反應

在 macOS Tahoe 及更新版本中，系統的遊戲覆疊鍵盤快捷鍵預設綁定為 `Cmd+Esc`，會在按鍵傳送到 VS Code 之前將其攔截。若要釋放此鍵盤快捷鍵：

1. 開啟系統設定
2. 前往鍵盤，然後是鍵盤快捷鍵，再到遊戲控制器
3. 取消勾選遊戲覆疊核取方塊

或者，將擴充功能重新綁定到其他按鍵：開啟 VS Code 的[鍵盤快捷鍵編輯器](https://code.visualstudio.com/docs/configure/keybindings)（`Cmd+K Cmd+S`），搜尋 `Claude Code: Focus input`，並指定新的快捷鍵。

### Ctrl+J 在提示詞輸入框中新增一行

若要讓 `Ctrl+J` 不再於提示詞輸入框中新增一行，請在 Claude Code 的 `keybindings.json` 檔案中[解除該按鍵的綁定](https://code.claude.com/docs/zh-TW/keybindings.md#unbind-default-shortcuts)。擴充功能在 2.1.309 或更新版本中才會讀取此檔案，因此若擴充功能版本較舊，請先在擴充功能檢視中更新。

此範例為完整的檔案內容，其中只有一個解除該按鍵綁定的項目，即 `Chat` 區塊中的 `"ctrl+j": null`：

```json theme={null}
{
  "bindings": [
    {
      "context": "Chat",
      "bindings": {
        "ctrl+j": null
      }
    }
  ]
}
```

此檔案位於您的 Claude Code 設定目錄中，除非您已使用 `CLAUDE_CONFIG_DIR` 將其移至他處，否則該目錄為 `~/.claude`。請查看該目錄，並依照您發現的情況採取對應的步驟：

* **尚無 `keybindings.json`**：建立此檔案，內容與範例完全相同
* **有 `keybindings.json` 但沒有 `Chat` 區塊**：將範例中的 `Chat` 區塊加入頂層的 `bindings` 陣列，位置不限
* **有 `Chat` 區塊但沒有 `"ctrl+j"` 這一行**：將 `"ctrl+j": null` 加入該區塊的 `bindings`
* **`Chat` 區塊中已有 `"ctrl+j"` 這一行**：將該行的值改為 `null`

儲存檔案後，在提示詞輸入框中按下 `Ctrl+J` 就不會再新增一行。

如果 `Ctrl+J` 仍會在提示詞輸入框中新增一行，請依序從命令選擇區執行以下兩個命令：

1. **Developer: Reload Window**，然後再次在提示詞輸入框中按下 `Ctrl+J`
2. **Claude Code: Show Logs**，然後尋找包含 `Ctrl+J in the chat input still inserts a newline` 的警告。在警告指出的檔案中修正其回報的問題，儲存檔案後再次按下 `Ctrl+J`。

如果日誌中沒有此類警告，請確認該檔案位於您的 Claude Code 設定目錄中，且其 `Chat` 區塊將 `"ctrl+j"` 設為 `null`。如果 `Ctrl+J` 仍會新增一行，請[回報此問題](https://github.com/anthropics/claude-code/issues)。

### Claude Code 面板空白或無法載入

如果 Claude Code 面板已開啟，但完全沒有顯示任何內容（連提示詞輸入框都沒有），請在擴充功能檢視中將擴充功能更新至 v2.1.309 或更新版本。然後從命令選擇區執行 **Developer: Reload Window**。如果接著看到 `Claude Code couldn’t load` 通知，請依序執行其列出的步驟。

如果面板仍無法載入，請開啟擴充功能的日誌，並附上日誌副本[回報此問題](https://github.com/anthropics/claude-code/issues)：

* **在 v2.1.309 或更新版本上仍為空白**：從命令選擇區執行 **Claude Code: Show Logs** 以開啟日誌
* **通知中的步驟沒有幫助**：點擊通知中的 **Show logs** 以開啟日誌

### 繼續的對話一開始是空白的

當您[繼續過去的對話](#resume-past-conversations)，或對話[在重新載入後恢復](#continue-conversations-after-a-reload)時，在該對話的 Claude Code 程序啟動期間，其訊息可能會保持空白。大約一秒後，空白處會出現 `Waiting for your plugins…`。

您不需要進行任何操作。當程序啟動並確認沒有外掛需要先檢查這些訊息後，訊息就會出現；如果啟動時間較長，則會在 20 秒後出現。

### 每次重新載入重新開啟對話時，面板都會停止回應

如果每次重新載入並恢復對話時，整個面板都會當機、凍結或只顯示 `Something went wrong`，請將擴充功能更新至 v2.1.301 或更新版本。然後再次重新載入視窗或重新啟動 VS Code。當對話連續兩次未能完成開啟後，您會在其位置得到一個新的聊天，並附有[對話未重新開啟](#a-conversation-was-not-reopened)的通知。

### 公式顯示為原始 LaTeX

如果 Claude 回應中的數學式都沒有被排版，請在擴充功能檢視中檢查擴充功能的版本，因為[數學式呈現](#latex-math-in-responses)需要 2.1.301 或更新版本。如果您使用[終端機模式](#switch-to-terminal-mode)（無論版本為何都不會排版數學式），請取消勾選 [Use Terminal 設定](vscode://settings/claudeCode.useTerminal)，讓 Claude Code 改為在聊天面板中開啟。

如果某個公式按原文顯示，而其附近的其他公式已被排版，請檢查是否為以下原因：

* **公式為行內公式，且面板未將其視為數學式**：請要求 Claude 以獨立成行的 `$$` 區塊再次傳送該公式。當 `$…$` 分隔符號之間的文字符合以下情況時，面板會將行內公式按原文顯示：
  * 不只是簡單的算術，卻沒有 `=`、`+` 或 `^` 等字元將其標示為數學式，例如 `$O(n log n)$`
  * 以數字開頭且沒有此類字元，例如 `$30$` 和 `$1/N$`
  * 美元符號內有空格，例如 `$ x^2 $`
  * 超過 60 個字元
  * 被拆分到兩行。被拆分到兩行的 `\(…\)` 公式同樣不會被排版。
* **公式有 TeX 語法錯誤**：請要求 Claude 修正錯誤後重寫公式。
* **公式定義了巨集**：含有巨集定義（例如 `\newcommand` 或 `\def`）的公式會按原文顯示。請要求 Claude 不使用巨集重寫公式。
* **公式含有未跳脫的 `%`**：請要求 Claude 使用 `\%` 表示百分比符號後重寫公式。
* **公式過大**：超過 8,192 個字元的公式，或排版後的輸出會遠大於其 TeX 原始碼的公式，會按原文顯示。請要求 Claude 將其拆分為較小的公式，或以更精簡的方式撰寫。
* **公式位於大量數學式之後**：在回應中的同一個文字區塊內，面板會依序排版公式，直到達到上限為止。超過上限的後續公式會按原文顯示。請要求 Claude 單獨再次傳送您需要的公式。

### 聽寫或 Web 分頁在 TLS 檢查代理伺服器後方失敗

當聽寫或 Web 分頁因憑證錯誤（例如 `unable to get local issuer certificate`）而失敗時，請在 `~/.claude/settings.json` 的 `env` 區塊中設定 [`NODE_EXTRA_CA_CERTS`](https://code.claude.com/docs/zh-TW/network-config#custom-ca-certificates)。將其設為包含您代理伺服器根 CA 憑證的 PEM 檔案路徑，您的 IT 團隊可以提供此檔案。失敗情況會顯示在麥克風按鈕或 Web 分頁上，或顯示在日誌中：

* **聽寫**：麥克風按鈕會在 `Dictation error: WebSocket error:` 之後顯示錯誤文字。
* **Web 分頁**：列出[雲端工作階段](#resume-cloud-sessions-from-claude-ai)的分頁會顯示 `Remote server is not connected`，但不含錯誤文字。若要在日誌中讀取錯誤文字：
  1. 從[命令選擇區](#vs-code-commands-and-shortcuts)執行 **Claude Code: Show Logs**，以開啟 `Claude VSCode` 輸出頻道。
  2. 點擊分頁上的 **Reconnect**，並等待其不再顯示 `Connecting…`。
  3. 在頻道中搜尋 `Error fetching remote sessions:` 或 `Failed to fetch organization UUID:`，然後閱讀最新符合的那一行中該前綴之後的錯誤文字。
* **日誌警告**：提及 `an authority that Claude Code does not trust` 的警告表示發生憑證錯誤。位於 TLS 檢查代理伺服器後方時，請在 `~/.claude/settings.json` 的 `env` 中設定 `NODE_EXTRA_CA_CERTS`。v2.1.309 之前的版本不會記錄此警告。

此修正需要擴充功能版本 2.1.307 或更新版本，因此請先更新擴充功能。然後將 `NODE_EXTRA_CA_CERTS` 設為憑證檔案的完整路徑，且不要使用 `~`。若為 Windows 路徑，請在 `settings.json` 中將每個反斜線寫兩次，例如 `C:\\certs\\example-ca.pem`。

> [!NOTE]
>
> 在連線至 WSL、SSH 主機、開發容器或其他系統的視窗中，請在該系統上儲存憑證檔案並編輯 `~/.claude/settings.json`，而不是在您的本機電腦上。

此範例指定位於 Linux 或 macOS 路徑 `/etc/ssl/certs/example-ca.pem` 的憑證檔案：

```json ~/.claude/settings.json theme={null}
{
  "env": {
    "NODE_EXTRA_CA_CERTS": "/etc/ssl/certs/example-ca.pem"
  }
}
```

儲存 `settings.json`，然後開始錄音或再次點擊 **Reconnect**。如果錯誤再次出現，請使用 **Claude Code: Show Logs** 開啟輸出頻道，並搜尋 `use the CA certificates file`。此類警告會說明擴充功能無法使用您的檔案的原因，以及它從何處讀取該路徑。接著在下表中找出您設定 `NODE_EXTRA_CA_CERTS` 的每個位置，並依照該列的說明操作：

| 設定位置 | 處理方式 |
| - | - |
| 啟動 VS Code 時所使用的環境 | 在此設定的值優先於 `~/.claude/settings.json` 中的值，即使其指定的檔案無法使用也是如此。請修正或移除該值，然後重新啟動 VS Code |
| `~/.claude/settings.json` 中的 `env` | 修正該值或其指定的檔案，然後開始錄音或再次點擊 **Reconnect** |
| VS Code 的 [`claudeCode.environmentVariables`](#extension-settings) 設定、`~/.claude.json`、專案的 `.claude/settings.json` 或 `.claude/settings.local.json`，或受管設定 | 在此設定的值不會套用至聽寫或 Web 分頁。請同時在 `~/.claude/settings.json` 的 `env` 中設定此變數 |

### Claude Code 一直沒有回應

如果 Claude Code 沒有回應您的提示詞：

1. **檢查您的網際網路連線**：確保您有穩定的網際網路連線
2. **開始新對話**：嘗試開始一個新的對話，看看問題是否仍然存在
3. **嘗試使用 CLI**：從終端機執行 `claude`，看看是否能獲得更詳細的錯誤訊息

如果問題仍然存在，請[在 GitHub 上提交 issue](https://github.com/anthropics/claude-code/issues)，並附上錯誤的詳細資訊。

## 解除安裝擴充功能

若要解除安裝 Claude Code 擴充功能：

1. 在 Mac 上按 `Cmd+Shift+X`，或在 Windows/Linux 上按 `Ctrl+Shift+X`，以開啟擴充功能檢視
2. 搜尋「Claude Code」
3. 按一下 **Uninstall**

當您啟動 `claude` 時，擴充功能會保持解除安裝狀態。如果您在 VS Code 執行期間從外部終端機執行 `/ide`，Claude Code 會重新安裝擴充功能。若要避免這種情況，請在 `~/.claude.json` 中將 [`autoInstallIdeExtension`](https://code.claude.com/docs/zh-TW/settings-reference#autoinstallideextension) 設定為 `false`，或從整合式終端機在 `/config` 中關閉 **Auto-install IDE extension**。您也可以將 [`CLAUDE_CODE_IDE_SKIP_AUTO_INSTALL`](https://code.claude.com/docs/zh-TW/env-vars) 環境變數設定為 `1`。

若要一併移除擴充功能資料並重設所有設定，請刪除您平台上擴充功能的儲存目錄。

在 macOS 上：

```bash theme={null}
rm -rf ~/Library/"Application Support"/Code/User/globalStorage/anthropic.claude-code
```

在 Linux 上：

```bash theme={null}
rm -rf ~/.config/Code/User/globalStorage/anthropic.claude-code
```

在 Windows 上，於 PowerShell 中：

```powershell theme={null}
Remove-Item -Recurse -Force "$env:APPDATA\Code\User\globalStorage\anthropic.claude-code"
```

如需更多協助，請參閱[疑難排解指南](https://code.claude.com/docs/zh-TW/troubleshooting.md)。

## 後續步驟

現在您已在 VS Code 中設定好 Claude Code：

* [探索常見工作流程](https://code.claude.com/docs/zh-TW/common-workflows.md)，充分發揮 Claude Code 的效益
* [設定 MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md)，透過外部工具擴充 Claude 的功能。可在聊天面板中使用 `/mcp` 新增及管理這些伺服器。
* [設定 Claude Code 設定](https://code.claude.com/docs/zh-TW/settings.md)，自訂允許的命令、hook 等。這些設定在擴充功能與 CLI 之間共用。
* 查看 Claude Code 的[安全防護措施](https://code.claude.com/docs/zh-TW/security.md)與[資料使用](https://code.claude.com/docs/zh-TW/data-usage.md)

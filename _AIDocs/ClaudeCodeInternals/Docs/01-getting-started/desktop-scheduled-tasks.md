<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/desktop-scheduled-tasks | lastmod: 2026-10-27 | section: Getting started / Platforms and integrations -->
> 來源：https://code.claude.com/docs/zh-TW/desktop-scheduled-tasks（官方 zh-TW，lastmod 2026-10-27）｜分類：Getting started › Platforms and integrations｜EN 摘要：Set up scheduled tasks in Claude Code Desktop to run Claude automatically on a recurring basis for daily code reviews, dependency audits, or morning briefings.

# 在 Claude Code Desktop 中排程定期任務

> 在 Claude Code Desktop 中設定排程任務，以定期自動執行 Claude 進行每日程式碼審查、相依性稽核或早晨簡報。

排程任務會在您選擇的時間和頻率自動啟動新的工作階段。使用它們進行定期工作，例如每日程式碼審查、相依性更新檢查，或從您的日曆和收件匣提取資訊的早晨簡報。

Desktop 應用程式的 **Scheduled tasks** 頁面會同時列出本機排程任務和[雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md)（前身為 routines）：

* **本機任務**：在您的機器上執行，可直接存取您的檔案和工具，但只有在應用程式開啟且您的電腦處於喚醒狀態時才會觸發
* **雲端任務**：即使您的電腦關閉也能執行，並且也可以透過 API 呼叫或 GitHub 事件啟動

本頁涵蓋本機排程任務；如需雲端排程任務及其觸發選項，請參閱[使用排程任務自動化工作](https://code.claude.com/docs/zh-TW/routines.md)。

> [!NOTE]
>
> 如果您的應用程式以[先前的名稱](https://code.claude.com/docs/zh-TW/routines.md#where-the-name-routines-still-appears)顯示此功能，請在本頁提到 **Scheduled** 的地方點選 **Routines**，並在提到 **New task** 的地方點選 **New routine**。

## 比較排程選項

Claude Code 提供三種方式來排程定期或一次性的工作：

| | [Cloud](https://code.claude.com/docs/zh-TW/routines.md) | [Desktop](https://code.claude.com/docs/zh-TW/desktop-scheduled-tasks.md) | [`/loop`](https://code.claude.com/docs/zh-TW/scheduled-tasks) |
| :- | :- | :- | :- |
| 執行位置 | Cloud，預設由 Anthropic 管理 | 您的機器 | 您的機器 |
| 需要機器開啟 | 否 | 是 | 是 |
| 需要開啟的工作階段 | 否 | 否 | 是 |
| 跨重新啟動持續存在 | 是 | 是 | 在 `--resume` 上復原，有[例外](https://code.claude.com/docs/zh-TW/scheduled-tasks.md#limitations) |
| 存取本機檔案 | 否（全新複製） | 是 | 是 |
| MCP 伺服器 | 每個工作配置的連接器 | [設定檔](https://code.claude.com/docs/zh-TW/mcp.md)和連接器 | 繼承自工作階段 |
| 權限提示 | 預設為[自動模式](https://code.claude.com/docs/zh-TW/routines.md#permission-prompts-during-a-run) | 每個工作可設定 | 繼承自工作階段 |
| 可自訂排程 | 是 | 是 | 是 |
| 最小間隔 | 1 小時 | 由 Claude 設定時為 1 分鐘，[在表單中為 1 小時](https://code.claude.com/docs/zh-TW/desktop-scheduled-tasks.md#schedule-options) | 1 分鐘 |

> [!TIP]
>
> 使用**雲端工作**來執行應該在沒有您的機器的情況下可靠執行的工作。當您需要存取本機檔案和工具時，使用**Desktop 工作**。使用 **`/loop`** 進行工作階段期間的快速輪詢。

> [!NOTE]
>
> 根據預設，本機排程任務會針對您的工作目錄的任何狀態執行，包括未提交的變更。若要改為讓每次執行使用其自己的[隔離 Git worktree](https://code.claude.com/docs/zh-TW/desktop.md#run-a-session-in-its-own-worktree)，請在建立任務後，於任務的[**Edit** 表單](#manage-scheduled-tasks)中選取 **Worktree**。當任務的資料夾是 Git 儲存庫時，即可使用此核取方塊。

## 建立排程任務

本機排程任務需要 Claude Desktop 1.1.5368 或更新版本。

**1. 開啟 Scheduled tasks 頁面**

在 [**Code** 標籤](https://code.claude.com/docs/zh-TW/desktop.md)中，按一下側邊欄中或側邊欄 **More** 選單中的 **Scheduled**。如果側邊欄顯示的是 **Routines** 而非 **Scheduled**，請按一下 **Routines**，再按一下 **New routine**，然後繼續參閱[全頁表單](#full-page-form)。

**2. 開始新任務**

按一下 **New task** 以開啟 **New scheduled task** 對話框。繼續之前，請留意是否出現以下畫面：

* 如果開啟的選單中有 **Create with Claude** 和 **Set up manually**，請選擇 **Set up manually** 以開啟對話框。
* 如果 **Only on this computer** 位於對話框頂端，請在輸入任何內容之前，先前往[對話框頂端有 Only on this computer 時](#dialog-with-only-on-this-computer-at-the-top)。
* 如果開啟的是含有 **Local** 和 **Cloud** 的選單，或開啟的是整個頁面而非對話框，請前往[全頁表單](#full-page-form)。

**3. 為任務命名**

在 **Name** 欄位中輸入名稱。Desktop 會將其轉換為小寫 kebab-case，並用作任務在磁碟上的資料夾名稱，因此該名稱在您的所有任務中必須是唯一的。

**4. 撰寫指示**

在名稱下方的方塊中，輸入 Claude 在任務執行時應執行的操作。

**5. 開啟 Only on this computer**

先跳過 **Trigger** 卡片，展開其下方的 **Advanced settings**。在 **General** 標籤上，開啟 **Only on this computer**。開啟後，任務會在您的電腦上的本機資料夾中執行。

如果該開關無法使用，請清除儲存庫或 GitHub 事件或 API 觸發條件，因為這些會使任務成為[雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md)。

**6. 選擇本機資料夾**

在 **Local folder** 列中選擇一個資料夾。在您選擇資料夾之前，**Create** 會保持無法使用。

**7. 設定排程**

回到 **Trigger** 卡片，選擇一個[排程預設選項](#schedule-options)。

**8. 選擇權限模式和模型**

在指示方塊的工具列中，選擇[權限模式](#permissions-for-scheduled-tasks)和模型。如果保持不變，執行時會使用您的 Claude Code 設定和預設模型。

**9. 建立任務**

按一下 **Create**。如果您尚未信任該資料夾，Desktop 會在此時要求您信任它。任務的詳細資料頁面隨即開啟。

在詳細資料頁面上，按一下鉛筆圖示以開啟 [**Edit** 表單](#manage-scheduled-tasks)。您可以在其中變更 Desktop 根據您的指示填入的 **Description**、選擇 **Worktree**，或將排程切換為 **Manual** 或 **Custom**。

您也可以透過在任何工作階段中描述您想要的內容來建立任務。例如，「設定每天早上 9 點執行的每日程式碼審查」會建立定期任務。像「提醒我明天下午 3 點檢查部署」這樣的請求會建立一次性任務，在觸發後會自動停用。

### 對話框頂端有 Only on this computer 時

如果 **New scheduled task** 對話框開啟時 **Only on this computer** 位於頂端，請在輸入任何內容之前先將其開啟。開啟後，一個用於本機任務的獨立空白表單會取代原本的表單。

接著填寫本機表單的欄位：

* **Name**：輸入名稱，方式與[建立排程任務的步驟](#create-a-scheduled-task)相同。
* **Description**：輸入說明。在您輸入之前，**Create** 會保持無法使用。
* **指示方塊**：輸入 Claude 在任務執行時應執行的操作。從方塊中的選單選擇權限模式和模型。
* **Working folder**：選擇任務執行所在的資料夾。在您選擇資料夾之前，**Create** 會保持無法使用。
* **Trigger**：選擇排程。關於預設選項，請參閱[排程選項](#schedule-options)。

按一下 **Create**。任務的詳細資料頁面隨即開啟。

### 全頁表單

如果開啟的是含有 **Local** 和 **Cloud** 的選單，請選擇 **Local**。標題為 **New local routine** 或 **New local scheduled task** 的頁面隨即開啟。填寫其欄位：

* **Name**：輸入在您的所有任務中唯一的名稱。
* **Description**：輸入說明。
* **Instructions**：輸入 Claude 在任務執行時應執行的操作。在同一個方塊中，選擇權限模式、模型，以及任務執行所在的資料夾。
* **Schedule**：選擇其中一個[排程選項](#schedule-options)。

如果 **Create** 無法使用，請將游標停留在其上方，以查看表單還缺少哪些內容。按一下 **Create**，任務的詳細資料頁面隨即開啟。

## 排程選項

當您在 **Advanced settings** 下開啟 **Only on this computer** 時，**Trigger** 卡片會提供 Hourly、Daily、Weekdays 和 Weekly。若要為此類任務使用 **Manual** 或 **Custom**，請在建立任務後開啟其 [**Edit** 表單](#manage-scheduled-tasks)。該表單、[頂部有 **Only on this computer** 的對話框](#dialog-with-only-on-this-computer-at-the-top)以及[完整頁面表單](#full-page-form)提供以下六個選項：

* **Hourly**：每小時執行一次
* **Daily**：每天在您選擇的本機時間執行
* **Weekdays**：與 Daily 相同，但跳過星期六和星期日
* **Weekly**：顯示時間選擇器和日期選擇器
* **Manual**：無排程，只有在您按一下 **Run now** 時才執行。適用於儲存您按需觸發的提示詞
* **Custom**：依照您輸入的 cron 運算式執行，並以您的本機時間進行計算，例如 `0 9 * * *` 代表每天上午 9:00。星期幾和月份請以數字表示，因為不接受其名稱。星期日為 `0`，而非 `7`。表單會拒絕執行頻率高於每小時一次的運算式。

您也可以在任何 Desktop 工作階段中請 Claude 設定排程。Claude 不受每小時一次的限制，並且可以設定在未來特定時間的單次執行。例如，請它「每 30 分鐘執行一次測試套件」或「下週一上午 9 點，摘要自週五以來合併的 pull request」。

## 排程任務如何執行

本機排程任務在您的機器上執行。Desktop 在應用程式開啟時每分鐘檢查一次排程，並在任務到期時啟動新的工作階段，獨立於您開啟的任何手動工作階段。每個任務在排程時間後會有幾分鐘的小延遲，以錯開 API 流量。延遲是確定性的：同一任務始終在相同的偏移量處啟動。

任務只有在 desktop 應用程式執行且您的電腦處於喚醒狀態時才會執行。如果您的電腦在排程時間內進入睡眠狀態，該執行會被跳過。若要防止閒置睡眠，請在 **Settings > Desktop app** 或 **Settings > This computer > System** 中啟用 **Keep computer awake**。關閉筆記型電腦蓋仍會使其進入睡眠狀態。

> [!NOTE]
>
> 對於需要在電腦關閉時執行，或應該透過 API 呼叫或 GitHub 事件觸發的任務，請改為建立[雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md)。

### 尋找某次執行的工作階段

若要開啟某次執行所啟動的工作階段，請前往該任務的[詳細資訊頁面](#manage-scheduled-tasks)，並在 **History** 清單中點選該次執行的列。

側邊欄的工作階段清單也可以顯示 **Scheduled** 群組，每個任務佔一列。若要開啟某任務最近一次執行的工作階段，請在該群組中點選該任務的列。若要顯示此群組，請先[確認您使用的版面配置](https://code.claude.com/docs/zh-TW/desktop.md#check-which-layout-you-have)：

* **目前的版面配置**：開啟 [**Group and sort** 選單](https://code.claude.com/docs/zh-TW/desktop.md#organize-and-find-sessions)，選取 **Show**，然後選取 **Scheduled**。此群組預設為收合狀態，請點選其標題以展開。當您至少有一個任務為 **Active**（即任務詳細資訊頁面所顯示的 **Status**）時，**Show** 才會列出 **Scheduled**。如果未列出，請使用 **History** 清單，無論群組是否顯示皆可使用。
* **較早的版面配置**：此群組已位於工作階段清單中，無需額外開啟

無論透過哪種方式進入某次執行的工作階段，您都可以查看 Claude 執行的操作、審查變更，以及回應權限提示。Claude 可以編輯檔案、執行命令、建立提交和開啟 pull request，與您自己啟動的工作階段相同。

## 錯過的執行

當應用程式啟動或您的電腦喚醒時，Desktop 會檢查每個任務是否在過去七天內錯過了任何執行。如果有，Desktop 會為最近錯過的時間啟動恰好一次的追趕執行，並丟棄任何較舊的執行。錯過六天的每日任務在喚醒時執行一次。Desktop 會在追趕執行啟動時顯示通知。

在撰寫提示詞時請記住這一點。排程在上午 9 點的任務可能在晚上 11 點執行，如果您的電腦整天都在睡眠狀態。如果時間很重要，請在提示詞本身中新增護欄，例如：「只審查今天的提交。如果已經過下午 5 點，請跳過審查，只發佈錯過內容的摘要。」

## 排程任務的權限

每個任務都有其自己的權限模式，您在建立或編輯任務時設定。來自 `~/.claude/settings.json` 的允許規則也適用於排程任務工作階段。如果任務在 [Manual 模式](https://code.claude.com/docs/zh-TW/desktop.md#choose-a-permission-mode)下執行，並且需要執行它沒有權限的工具，執行會停滯，直到您核准它。若要核准，請[找到該次執行的工作階段](#find-a-runs-session)，並在其中回答權限提示。

為了避免停滯，在建立任務後按一下 **Run now**，監視權限提示，並為每個提示選擇「always allow」。該任務的未來執行會自動批准相同的工具，無需提示。您可以從任務的詳細資料頁面審查和撤銷這些批准。

標記為 [`requiresUserInteraction`](https://code.claude.com/docs/zh-TW/mcp#require-approval-for-a-specific-tool) 的 MCP 工具會在每次呼叫時提示，並且不提供 always-allow 選項。呼叫這些工具的執行每次都會停滯。

## 管理排程任務

在 **Code** 標籤中，按一下側邊欄中的 **Scheduled**，然後按一下清單中的任務以開啟其詳細資料頁面。從這裡您可以：

* **Run now**：立即啟動任務，無需等待下一個排程時間
* **Status**：在 Active 和 Paused 之間切換，以暫停或繼續排程執行，無需刪除任務
* **Edit**：變更 instructions、排程、資料夾或其他設定
* **Review history**：查看每次過去的執行，包括跳過的執行。將滑鼠懸停在跳過的項目上以查看原因：您的電腦在睡眠狀態、前一次執行仍在進行中，或其他排程任務已在執行。按一下 **Show more** 以載入較舊的項目。
* **Review allowed permissions**：從 **Always allowed** 面板查看和撤銷此任務的已儲存工具批准
* **Delete**：移除任務。任務建立的工作階段會被[封存](https://code.claude.com/docs/zh-TW/desktop.md#organize-and-find-sessions)，而非刪除。存放任務 `SKILL.md` 檔案的資料夾會保留在磁碟上的 `~/.claude/scheduled-tasks/<task-name>/`，或者如果您設定了 [`CLAUDE_CONFIG_DIR`](https://code.claude.com/docs/zh-TW/env-vars) 變數，則位於其下的 `scheduled-tasks/<task-name>/`。若要移除該資料夾，請自行刪除。

您也可以透過在任何 Desktop 工作階段中詢問 Claude 來列出、建立、編輯和暫停任務。例如，「暫停我的 dependency-audit 任務」或「顯示我的排程任務」。若要刪除任務，請使用其詳細資料頁面上的 **Delete** 按鈕。

排程任務也可以使用 `update_scheduled_task` MCP 工具在執行中的工作階段內修改其自己的排程或提示。這可讓任務根據其發現重新排程自己，例如，當它偵測到已建立發行分支時，重新排程程式碼審查以更早執行。

若要在磁碟上編輯任務的提示，請開啟 `~/.claude/scheduled-tasks/<task-name>/SKILL.md`（如果設定了 [`CLAUDE_CONFIG_DIR`](https://code.claude.com/docs/zh-TW/env-vars)，則在其下）。該檔案使用 YAML frontmatter 作為 `name` 和 `description`，提示作為主體。變更在下一次執行時生效。Schedule、資料夾、模型和啟用狀態不在此檔案中：透過 Edit 表單變更它們或詢問 Claude。

## 相關資源

* [雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md)：在雲端按排程、透過 API 呼叫或回應 GitHub 事件執行任務，即使您的電腦關閉也能執行
* [在排程上執行提示](https://code.claude.com/docs/zh-TW/scheduled-tasks.md)：在 CLI 中使用 `/loop` 的工作階段範圍排程
* [Claude Code GitHub Actions](https://code.claude.com/docs/zh-TW/github-actions.md)：在 CI 中按排程執行 Claude，而不是在您的機器上執行
* [使用 Claude Code Desktop](https://code.claude.com/docs/zh-TW/desktop.md)：完整的 Desktop 應用程式指南

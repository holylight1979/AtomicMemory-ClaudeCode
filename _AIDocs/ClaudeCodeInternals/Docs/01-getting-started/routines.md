<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/routines | lastmod: 2026-11-03 | section: Getting started / Platforms and integrations -->
> 來源：https://code.claude.com/docs/zh-TW/routines（官方 zh-TW，lastmod 2026-11-03）｜分類：Getting started › Platforms and integrations｜EN 摘要：Put Claude Code on autopilot. Create scheduled tasks, formerly routines, that run in the cloud on a schedule, on API calls, or on GitHub events.

# 使用排程任務自動化工作

> 讓 Claude Code 自動運作。建立排程任務（前身為 routines），在雲端依排程、於 API 呼叫時或因應 GitHub 事件而執行。

> [!NOTE]
>
> 排程任務目前處於研究預覽階段。行為、限制和 API 介面可能會變更。

雲端排程任務（前身為 routine）是一組已儲存的 Claude Code 設定：一個提示詞、一個或多個儲存庫，以及一組[連接器](https://code.claude.com/docs/zh-TW/mcp.md)，只需打包一次即可自動執行。排程任務在 Anthropic 管理的雲端基礎設施上執行，或在路由至您組織的[自行託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)時於該處執行，因此即使您的筆記型電腦關閉，它們仍會持續運作。

每個排程任務可以附加一個或多個觸發條件：

* **排程**：依照每小時、每晚或每週等定期節奏執行，或在特定的未來時間執行一次
* **API**：透過向任務專屬端點傳送帶有 bearer token 的 HTTP POST，隨需觸發
* **GitHub**：自動回應儲存庫事件（例如 pull request 或發行版本）而執行

單一排程任務可以組合多種觸發條件。例如，PR 審查任務可以每晚執行、由部署指令碼觸發，同時也對每個新的 PR 做出回應。

排程任務不一定需要排程：

* 只有 API 觸發條件的任務會在您呼叫其端點時執行。
* 只有 GitHub 觸發條件的任務會在發生符合的儲存庫事件時執行。

排程任務適用於 Pro、Max、Ultra、Team 和 Enterprise 方案。您可以在 [claude.ai/code/routines](https://claude.ai/code/routines) 建立和管理它們，或從 CLI 使用 `/schedule`。先前的名稱 routines [仍會出現](#where-the-name-routines-still-appears)。

> [!NOTE]
>
> 另外兩項功能會在您的機器上而非雲端排程工作：[Desktop 排程任務](https://code.claude.com/docs/zh-TW/desktop-scheduled-tasks.md)和 [`/loop`](https://code.claude.com/docs/zh-TW/scheduled-tasks)。若要在這三者之間做選擇，請參閱[比較排程選項](https://code.claude.com/docs/zh-TW/scheduled-tasks.md#compare-scheduling-options)。

Team 和 Enterprise 的擁有者可以在 [**Organization settings > Capabilities > Remote sessions**](https://claude.ai/admin-settings/capabilities) 透過 **Scheduled tasks (Was Routines)** 或 **Routines** 切換開關，為所有成員關閉排程任務。關閉此開關後，現有的排程任務會停止執行，成員也無法建立新的排程任務。

如果您的 Enterprise 組織透過[自訂角色](https://support.claude.com/en/articles/13930452)管理您的存取權，您還需要具備包含排程任務權限的角色。擁有者可以在 [**Organization settings > Roles**](https://claude.ai/admin-settings/roles) 中，於角色的 **Remote sessions** 區段新增此權限。

## 使用案例範例

每個範例都將一種觸發條件類型與適合排程任務的工作類型配對：無人值守、可重複執行，且有明確的結果。

* **待辦事項維護**：排程觸發條件每個工作日晚上在您的儲存庫中執行，並將您的問題追蹤器新增為連接器。排程任務讀取自上次執行以來開啟的問題、套用標籤，並依據所引用的程式碼區域指派負責人。接著將摘要發布到 Slack，讓團隊每天一開始就有整理好的佇列。
* **警報分類**：當錯誤閾值被超過時，您的監控工具會呼叫排程任務的 API 端點，並將警報內文作為 `text` 傳遞。任務的提示詞指示 Claude 調查觸發 payload 中的警報，因此它會擷取堆疊追蹤，並將其與儲存庫中最近的提交相互關聯。接著它會開啟一個草稿 pull request，內含建議的修正以及返回警報的連結。值班人員只需審查 PR，而不必從空白的終端機開始。
* **客製化程式碼審查**：GitHub 觸發條件在 `pull_request.opened` 時執行。排程任務套用您團隊自己的審查檢查清單，針對安全性、效能和風格問題留下行內註解。它也會新增一則摘要註解，讓人工審查者可以專注於設計，而不是機械式的檢查。
* **部署驗證**：您的 CD 管線在每次正式環境部署後呼叫排程任務的 API 端點。任務針對新的建置執行冒煙檢查、掃描錯誤日誌以找出回歸問題，並在部署時段結束前向發布頻道發布可否部署的結論。
* **文件偏移**：排程觸發條件每週執行。排程任務掃描自上次執行以來合併的 PR、標記引用了已變更 API 的文件，並針對文件儲存庫開啟更新 PR，供編輯者審查。
* **函式庫移植**：GitHub 觸發條件在 `pull_request.closed` 時執行，並篩選為某個 SDK 儲存庫中已合併的 PR。排程任務將變更移植到另一種語言的平行 SDK，並開啟對應的 PR，讓兩個函式庫保持同步，而無需人工重新實作每項變更。

## 建立排程任務

您可以從 [claude.ai/code/routines](https://claude.ai/code/routines) 網頁、Desktop 應用程式或 CLI 建立排程任務。這三個使用介面都會寫入同一個雲端帳戶，因此您在其中一個介面建立的排程任務會立即出現在其他介面中。在 Desktop 應用程式的 **Code** 標籤中，按一下側邊欄或側邊欄 **More** 選單中的 **Scheduled**，然後按 **New task**，再依照[從網頁建立](#create-from-the-web)繼續操作。

排程任務以完整的 Claude Code 雲端工作階段自主執行。工作階段會執行 shell 命令、使用 [skills](https://code.claude.com/docs/zh-TW/skills.md)，並呼叫您包含的任何連接器。在[專案](https://code.claude.com/docs/zh-TW/claude-projects.md#what-threads-pick-up-from-your-repositories)的討論串之外，這些 skills 也包括已提交至所複製儲存庫中的 skills。建立任務時您無需選擇權限模式：若要了解執行何時會停下來等待您，請參閱[執行期間的權限提示](#permission-prompts-during-a-run)。

排程任務可以存取的內容取決於：

* 您選擇的儲存庫
* [環境](https://code.claude.com/docs/zh-TW/cloud-environments.md)的網路存取和變數
* 您包含的連接器

請將上述每一項的範圍限制在任務實際需要的內容。

排程任務屬於您個人的 claude.ai 帳戶。它們不會與隊友共享，且其執行會計入您帳戶的[用量與限制](#usage-and-limits)。排程任務透過您連接的 GitHub 身分或連接器所執行的任何動作，都會顯示為由您執行。提交和 pull request 會帶有您的 GitHub 使用者，而 Slack 訊息、Linear 票證或其他連接器動作則會使用您為這些服務連結的帳戶。

### 從網頁建立

**1. 開啟建立對話方塊**

前往 [claude.ai/code/routines](https://claude.ai/code/routines) 並按一下 **New task**，以開啟 **New scheduled task** 對話方塊。繼續之前，請檢查是否出現以下畫面：

* 如果按鈕顯示的是 **New routine** 而非 **New task**，請按一下 **New routine**，並依照[完整頁面表單](#full-page-form)繼續操作。
* 在 Desktop 應用程式中，如果開啟了包含 **Local** 和 **Cloud** 的選單，請前往[完整頁面表單](#full-page-form)。
* 如果開啟了包含 **Create with Claude** 和 **Set up manually** 的選單，請選擇 **Set up manually** 以開啟對話方塊。**Create with Claude** 則可讓您在對話中描述任務，改由 Claude 替您建立。
* 如果開啟的是完整頁面而非對話方塊，請前往[完整頁面表單](#full-page-form)。

如果對話方塊開啟時已經顯示 **Repositories** 和 **Environment**，請參閱[該對話方塊的差異](#dialog-with-repositories-and-environment-in-the-main-view)。否則，此對話方塊也會為 claude.ai 聊天建立排程任務。若要讓您的任務成為對話方塊中所稱的 Claude Code 任務，請在接下來的步驟中選擇儲存庫，或新增 GitHub 事件或 API 觸發條件。這類任務會在雲端工作階段中執行 Claude Code。

**2. 為任務命名並撰寫提示詞**

為排程任務提供描述性名稱，並撰寫 Claude 每次執行的提示詞。提示詞是最重要的部分：任務會自主執行，因此提示詞必須自成一體，並明確說明要做什麼以及怎樣才算成功。

觸發條件觸發時，工作階段會將已儲存的提示詞視為其被指派的工作並加以執行，而不是將其視為在對話途中傳入的不受信任內容。觸發條件僅證明該提示詞是事先由您帳戶上的授權工作階段所儲存。因此，觸發的提示詞並非即時的使用者輸入，無法作為執行期間動作的核准或同意。工作階段在執行期間擷取的內容仍維持其一般處理方式。

**3. 選擇觸發條件**

在 **Trigger** 列中，選擇任務的啟動方式。若要組合多個觸發條件，請按一下該列末端的 **+**。

> [tab] Schedule
>
> 為定期執行選擇預設頻率。請參閱[新增排程觸發條件](#add-a-schedule-trigger)，以了解時區處理、延遲啟動、自訂 cron 間隔和一次性執行。

> [tab] GitHub event
>
> 選擇儲存庫、要回應的事件以及選用的篩選條件。請參閱[新增 GitHub 觸發條件](#add-a-github-trigger)，以取得支援的事件和篩選欄位的完整清單。

> [tab] API
>
> 在此選擇 **API**。當您按一下 **Create** 時，**API token** 對話方塊只會顯示 token 一次，因此請在關閉對話方塊前複製它。請參閱[新增 API 觸發條件](#add-an-api-trigger)以複製 URL 或產生新的 token。

**4. 選擇儲存庫**

展開 **Advanced settings**。在 **General** 標籤的 **Repository** 下，選擇一個或多個 GitHub 儲存庫供 Claude 在其中工作。

每個儲存庫都會在執行開始時被複製。Claude 會為其變更建立以 `claude/` 為前綴的分支。

**5. 選擇環境**

選擇儲存庫後，下方會出現 **Cloud environment**。為任務選擇一個[雲端環境](https://code.claude.com/docs/zh-TW/cloud-environments.md)。如果已經選擇了某個環境，您可以保留它或選擇其他環境。環境控制雲端工作階段可以存取的內容：

* **Network access**：設定每次執行期間可用的網際網路存取層級
* **Environment variables**：提供 Claude 在每次執行期間可以使用的值。這些值[對使用該環境的任何人都可見](https://code.claude.com/docs/zh-TW/cloud-environments.md#what-carries-over-from-your-setup)，因此在 Anthropic 託管的環境中，請改將 Claude 在執行期間所呼叫 API 的金鑰儲存為[網路機密](https://code.claude.com/docs/zh-TW/cloud-environments.md#add-network-secrets)。該章節也列出了永遠不會取得機密的請求
* **Setup script**：安裝任務所需的相依套件和工具。結果會被[快取](https://code.claude.com/docs/zh-TW/cloud-environments.md#environment-caching)，因此指令碼不會在每個工作階段重新執行

系統提供具有 **Trusted** 網路存取的 **Default** 環境，它只允許[預設允許清單](https://code.claude.com/docs/zh-TW/cloud-environments.md#default-allowed-domains)中的套件登錄、雲端供應商 API、容器登錄和常見開發網域透過工作階段的網路存取。您新增到任務的連接器會透過 Anthropic 的伺服器存取其服務，因此不需要變更允許清單。

如果您的任務需要直接存取您自己的服務，或該清單以外的網域，請在執行前編輯環境的[網路存取](https://code.claude.com/docs/zh-TW/cloud-environments.md#network-access)。若要使用另一個環境，請先[建立一個](https://code.claude.com/docs/zh-TW/cloud-environments.md#configure-your-environment)。

**6. 選擇模型和 effort 等級**

在提示詞輸入框的模型選擇器中選擇模型，供 Claude 在每次執行時使用。對於 Claude Code 任務，如果該模型提供 [effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)，同一個選擇器中的 **Effort** 會顯示目前的等級。若要變更，請選擇其他等級。選擇器的 **Default** 選項不提供任何等級。

**7. 檢查連接器**

切換到 **Advanced settings** 的 **Connectors** 標籤。預設會包含您所有已連接的 [MCP 連接器](https://code.claude.com/docs/zh-TW/mcp.md)。請移除任務不需要的連接器：Claude 在執行期間可以使用所包含的連接器，包括寫入。若要了解執行何時會先停下來詢問您，請參閱[執行期間的權限提示](#permission-prompts-during-a-run)。

**8. 建立任務**

按一下 **Create**。對話方塊會關閉，並開啟新任務的詳細資料頁面。任務會在下次其中一個觸發條件符合時執行。若要立即開始執行，請按一下詳細資料頁面上的 **Run now**。

若要查看某次執行做了什麼，請在詳細資料頁面的 **History** 清單中按一下該次執行。該次執行會[以完整工作階段開啟](#view-and-interact-with-runs)（每次執行都是一個新的工作階段），您可以在其中查看 Claude 做了什麼、檢閱變更並建立 pull request。

#### 主檢視中包含 Repositories 和 Environment 的對話方塊

請依照[從網頁建立的步驟](#create-from-the-web)操作，並在對話方塊的主檢視中填寫各個欄位，而不是在 **Advanced settings** 下填寫。此對話方塊只會建立 Claude Code 任務。

請在新增 GitHub 事件觸發條件之前先選擇儲存庫，因為在選擇儲存庫之前無法使用該觸發條件。

#### 完整頁面表單

在 Desktop 應用程式中，如果開啟了包含 **Local** 和 **Cloud** 的選單，請選擇 **Cloud**。標題為 **New routine** 或 **New scheduled task** 的頁面隨即開啟。請填寫其中的欄位：

* **Name**：輸入名稱。
* **Instructions**：輸入提示詞。在同一個方塊中，選擇模型、effort 等級（如果模型有提供）、儲存庫和環境。若要了解各項所控制的內容，請參閱[從網頁建立](#create-from-the-web)下的步驟。
* **Select a trigger**：選擇 **Schedule**、**GitHub event** 或 **API**。若為排程，請參閱[新增排程觸發條件](#add-a-schedule-trigger)。若為 [GitHub 事件](#add-a-github-trigger)，請選擇儲存庫。若為 [API 觸發條件](#add-an-api-trigger)，請從按一下 **Create** 後開啟的 **API token** 對話方塊中複製 token，因為它只會顯示一次。若要組合多個觸發條件，請按一下 **Add another trigger**。
* **Connectors**：預設會包含您所有已連接的連接器，因此請移除任務不需要的連接器。

如果 **Create** 無法使用，請將游標停留在其上方，以查看表單還需要哪些內容。按一下 **Create**，任務的詳細資料頁面隨即開啟。

### 從 CLI 建立

在任何工作階段中執行 `/schedule`，即可透過對話方式建立排程任務。您也可以直接傳入描述，例如定期任務 `/schedule daily PR review at 9am`，或一次性任務 `/schedule clean up feature flag in one week`。Claude 會逐步收集與網頁對話方塊相同的資訊，然後將任務儲存到您的帳戶。此命令也可使用別名 `/routines`。

成功啟動時看起來會像一段對話：Claude 會在儲存前詢問有關排程、儲存庫和提示詞的後續問題。如果 Claude 反而回覆您需要進行身分驗證，或無法連接到您的遠端 claude.ai 帳戶，則表示並未建立排程任務；請參閱[疑難排解](#troubleshooting)。

使用 `/schedule` 建立的任務具有排程觸發條件。您也可以新增其他類型的觸發條件：

* **API 觸發條件**：在 [claude.ai/code/routines](https://claude.ai/code/routines) 網頁上編輯任務
* **[GitHub 觸發條件](#add-a-github-trigger)**：在網頁上編輯任務，或在 CLI 中請 Claude 處理。從 CLI 新增需要 Claude Code v2.1.225 或更新版本

沒有排程觸發條件的排程任務（例如僅由 API 呼叫或 GitHub 事件啟動的任務）沒有下次執行時間。當 Claude 儲存或更新此類任務時，CLI 不會顯示任何時間。

## 設定觸發條件

排程任務會在其中一個觸發條件符合時啟動。您可以隨時在任務[編輯對話方塊](#edit-and-control-scheduled-tasks)的 **Trigger** 列中新增或移除任務的觸發條件。

當任務有兩個或更多觸發條件時，每個觸發條件在該對話方塊中都會有一個垃圾桶圖示。若要移除排程或 GitHub 事件觸發條件，請按一下其垃圾桶圖示，然後按 **Save changes**。若要移除 API 觸發條件，請改為[刪除其 token](#add-an-api-trigger)。

### 新增排程觸發條件

排程觸發條件會依照定期節奏執行任務，或在特定的未來時間執行一次。在網頁上任務的建立或編輯對話方塊中，選擇預設頻率，例如每小時、每天或每週：

* **整點執行**：如果您將執行排程在剛好整點（例如 9:00），它可能會晚幾分鐘才開始。若要在接近排程時間時開始，請選擇整點後幾分鐘，例如 9:07。
* **自訂間隔**：若需要預設選項未提供的節奏，請建立任務並在其[編輯對話方塊](#edit-and-control-scheduled-tasks)中選擇 **Custom**。接著輸入 cron 運算式，例如 `0 */2 * * *` 代表每兩小時執行一次。若要從 CLI 設定，請執行 [`/schedule update`](#manage-scheduled-tasks-from-the-cli)。執行頻率高於每小時一次的運算式會被拒絕。
* **時區**：選擇預設頻率時，請以您的本地時區輸入時間。
* **Cron 運算式時區**：當運算式只有五個欄位時，請以 UTC 撰寫小時，因此 `0 9 * * 1-5` 會在平日 UTC 上午 9:00 執行。如果該欄位以 `CRON_TZ=` 前綴開頭，請保留它並以該時區撰寫小時，或將其刪除並以 UTC 撰寫小時。

#### 排程一次性執行

一次性排程會在特定時間戳記執行任務一次。例如，您可以用它來：

* 在本週稍後提醒自己
* 在推出完成後開啟清理 PR
* 在上游變更發布後開始後續工作

任務執行後會自動關閉，網頁 UI 會將其標記為 **Completed**。若要再次執行，請在網頁上開啟任務的[編輯對話方塊](#edit-and-control-scheduled-tasks)，並選擇 **One-time** 或 **Once**（依您的對話方塊所顯示的標籤而定）。接著以您的本地時區設定新的日期和時間並儲存。

從 CLI 以自然語言描述時間即可建立一次性執行。Claude 會根據目前時間解析該描述，並在儲存前確認絕對時間戳記。

```text theme={null}
/schedule tomorrow at 9am, summarize yesterday's merged PRs
```

```text theme={null}
/schedule in 2 weeks, open a cleanup PR that removes the feature flag
```

一次性執行會計入與其他排程執行相同的每小時限制。詳情請參閱[用量與限制](#usage-and-limits)。

### 新增 API 觸發條件

API 觸發條件會為排程任務提供專屬的 HTTP 端點。使用任務的 bearer token 向該端點傳送 POST，即可啟動新的工作階段並傳回工作階段 URL。您可以用它將 Claude Code 整合到警報系統、部署管線、內部工具，或任何可以發出經身分驗證之 HTTP 請求的地方。

請在網頁上新增 API 觸發條件，可以在[建立任務](#create-from-the-web)時新增，或稍後依照以下步驟新增。您無法從 CLI 新增 API 觸發條件或管理其 token。

**1. 開啟任務進行編輯**

前往 [claude.ai/code/routines](https://claude.ai/code/routines)，按一下您想透過 API 觸發的排程任務，然後開啟其名稱旁的選單並選擇 **Edit**。**Edit scheduled task** 對話方塊隨即開啟。

**2. 新增 API 觸發條件**

在 **Trigger** 列中，按一下 **+**，然後從開啟的選單中選擇 **API**。隨即會出現包含此任務之 **Fire URL** 和 **Token** 的面板。

**3. 複製 URL 並產生 token**

複製 **Fire URL**。按一下 **Generate token**，然後立即從 **Token generated** 對話方塊複製 token。token 只會顯示一次，之後無法再取得，因此請將其存放在安全的地方，例如您警報工具的機密存放區。

API 觸發條件會在您產生 token 後立即生效。您不需要按一下 **Save changes**，完成後直接關閉對話方塊即可。

**4. 呼叫端點**

向 URL 傳送 POST 時，請在 `Authorization: Bearer` 標頭中傳送 token。[觸發排程任務](#trigger-a-scheduled-task)提供了完整範例。

每個排程任務都有自己的 token，其範圍僅限於觸發該任務。若要關閉 API 存取或輪換 token，請再次[開啟任務的 **Edit scheduled task** 對話方塊](#edit-and-control-scheduled-tasks)。這兩項控制項都位於 API 觸發條件面板中的 token 旁，且會立即生效：

* **關閉 API 存取**：按一下 **Delete token**，即 **Regenerate** 旁的垃圾桶圖示。這會移除 API 觸發條件
* **輪換 token**：按一下 **Regenerate**。先前的 token 會停止運作，**Token generated** 對話方塊會顯示新的 token 一次

#### 觸發排程任務

向 `/fire` 端點傳送 POST 請求，並在 `Authorization` 標頭中包含 bearer token。請求內文接受選用的 `text` 欄位，用於提供特定於該次執行的背景資訊，例如警報內文或失敗的日誌，並與任務已儲存的提示詞一起傳遞給任務。該值是自由格式文字，不會被解析：如果您傳送 JSON 或其他結構化 payload，任務會將其當作字面字串接收。

`text` 值不會以單純訊息的形式傳達給 routine。它會被包裝在 `<routine-fire-payload>` 區塊中傳達，該區塊將其標記為不受信任的資料，並告訴 Claude 除非 routine 本身的提示詞如此指示，否則不要遵循其中的指示。在網頁 UI 中透過 **Run now** 提供的文字也會套用相同的包裝。

這表示 routine 已儲存的提示詞必須明確選擇對觸發文字採取行動：撰寫提示詞時要明確引用 payload，例如「Investigate the alert described in the routine-fire-payload block」，否則 routine 會將該文字視為不具作用的背景資訊。任何持有 bearer token 的人都可以傳送 `text`，因此這層包裝可確保來自外洩 token 的觸發文字會被標記為不受信任的資料，而不是作為對您 routine 的直接指示。

以下範例從 shell 觸發排程任務。顯示的任務 ID 和 token 為預留位置：請將其替換為您在[新增 API 觸發條件](#add-an-api-trigger)時複製的 URL 和 token，否則請求會因 `401` 身分驗證錯誤而失敗：

```bash theme={null}
curl -X POST https://api.anthropic.com/v1/claude_code/routines/trig_01ABCDEFGHJKLMNOPQRSTUVW/fire \
  -H "Authorization: Bearer sk-ant-oat01-xxxxx" \
  -H "anthropic-beta: experimental-cc-routine-2026-04-01" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{"text": "Sentry alert SEN-4521 fired in prod. Stack trace attached."}'
```

成功的請求會傳回包含新工作階段 ID 和 URL 的 JSON 內文：

```json theme={null}
{
  "type": "routine_fire",
  "claude_code_session_id": "session_01HJKLMNOPQRSTUVWXYZ",
  "claude_code_session_url": "https://claude.ai/code/session_01HJKLMNOPQRSTUVWXYZ"
}
```

在瀏覽器中開啟工作階段 URL，即可即時觀看執行、檢閱變更或手動繼續對話。

> [!WARNING]
>
> `/fire` 端點在 `experimental-cc-routine-2026-04-01` beta 標頭下提供。在此功能處於研究預覽期間，請求和回應的結構、速率限制以及 token 語意都可能會變更。破壞性變更會在新的帶日期 beta 標頭版本下發布，而最近的兩個先前標頭版本會繼續運作，讓呼叫端有時間進行遷移。

#### API 參考

如需完整的 API 參考，包括所有錯誤回應、驗證規則和欄位限制，請參閱 Claude Platform 文件中的 [Trigger a routine through the API](https://platform.claude.com/docs/en/api/claude-code/routines-fire)。

`/fire` 端點僅供 claude.ai 使用者使用，並不屬於 Claude Platform API 介面的一部分。

### 新增 GitHub 觸發條件

GitHub 觸發條件會在已連接的儲存庫上發生符合的事件時，自動啟動新的工作階段。Claude Code 不會在不同事件之間重複使用工作階段，因此兩次 PR 更新會產生兩個獨立的工作階段。

> [!NOTE]
>
> GitHub webhook 事件受到每個任務和每個帳戶的每小時上限限制。超過限制的事件會被捨棄，直到時間視窗重設為止。

無論您從哪個使用介面設定觸發條件，Claude GitHub App 都必須安裝在您想訂閱的儲存庫上。

* 從網頁 UI 設定 GitHub 觸發條件，若尚未安裝該應用程式，網頁 UI 會提示您安裝。請依照以下步驟在網頁上設定。
* 從 CLI 設定時，請先從 [GitHub App 頁面](https://github.com/apps/claude)安裝應用程式，然後請 Claude 將 GitHub 觸發條件附加到現有的排程任務，例如 `/schedule add a GitHub trigger to my nightly review for pull requests opened in acme/webapp`。CLI 方式需要 Claude Code v2.1.225 或更新版本。Claude 新增觸發條件後，會回覆該觸發條件所觸發之任務的連結。

**1. 開啟任務進行編輯**

前往 [claude.ai/code/routines](https://claude.ai/code/routines)，按一下排程任務，然後開啟其名稱旁的選單並選擇 **Edit**。**Edit scheduled task** 對話方塊隨即開啟。

**2. 新增 GitHub 事件觸發條件**

在 **Trigger** 列中，按一下 **+**，然後從開啟的選單中選擇 **GitHub event**。

> [!NOTE]
>
> 在 CLI 中執行 `/web-setup` 會授予用於複製的儲存庫存取權限，但不會安裝 Claude GitHub App，也不會啟用 webhook 傳遞。

**3. 設定觸發條件**

視需要變更儲存庫，從[支援的事件](#supported-events)清單中選擇一個事件，並可選擇性地新增篩選條件。接著按一下對話方塊底部的 **Save changes** 以套用觸發條件。

#### 支援的事件

請從以下任一類別中選擇事件。在每個類別中，您可以選擇特定的動作（例如 `pull_request.opened`），或對該類別中的所有動作做出回應。

| Event | Triggers when |
| :- | :- |
| Pull request | 當 PR 被開啟、關閉、指派、加上標籤、同步或以其他方式更新時 |
| Release | 當發行版本被建立、發布、編輯或刪除時 |
| Issue | 當 issue 被開啟、編輯、關閉、重新開啟、加上標籤、指派或以其他方式更新時 |

#### 篩選 pull request

使用篩選條件來縮小哪些 pull request 會啟動新的工作階段。所有篩選條件都必須符合，排程任務才會觸發。可用的篩選欄位如下：

| Filter | Matches |
| :- | :- |
| Author | PR 作者的 GitHub 使用者名稱 |
| Title | PR 標題文字 |
| Body | PR 描述文字 |
| Base branch | PR 的目標分支 |
| Head branch | PR 的來源分支 |
| Labels | 套用到 PR 的標籤 |
| Is draft | PR 是否處於草稿狀態 |
| Is merged | PR 是否已合併 |

每個篩選條件都將一個欄位與一個運算子配對：等於、包含、開頭為、是其中之一、不是其中之一，或符合 regex。

`matches regex` 運算子會測試整個欄位值，而不是其中的子字串。若要符合任何包含 `hotfix` 的標題，請寫成 `.*hotfix.*`。如果沒有前後的 `.*`，篩選條件只會符合完全是 `hotfix`、前後沒有任何內容的標題。若要進行不使用 regex 語法的字面子字串比對，請改用 `contains` 運算子。

以下是一些篩選條件組合範例：

* **Auth module review**：base branch 為 `main`，head branch 包含 `auth-provider`。將任何涉及身分驗證的 PR 傳送給專門的審查者。
* **Ready-for-review only**：is draft 為 `false`。略過草稿，讓任務只在 PR 準備好接受審查時執行。
* **Label-gated backport**：labels 包含 `needs-backport`。僅在維護者為 PR 加上標籤時，才觸發移植到另一個分支的任務。

## 管理排程任務

按一下清單中的排程任務即可開啟其詳細資料頁面。詳細資料頁面會顯示任務的儲存庫、連接器、提示詞、排程、API token、GitHub 觸發條件，以及過去的執行清單。

### 檢視執行並與之互動

按一下任何執行，即可將其作為完整的工作階段開啟。在那裡，您可以查看 Claude 做了什麼、檢閱變更、建立 pull request 或繼續對話。每個執行工作階段的運作方式都與其他工作階段相同：使用工作階段標題旁的下拉選單來重新命名、封存或刪除它。

在任務詳細資料頁面的 **History** 下，每個已結束執行的資料列末端，若執行失敗會顯示 **Error**，若已取消會顯示 **Cancelled**，若成功則兩者皆不顯示。**Status** 篩選器將這三種結果分別稱為 **Failed**、**Cancelled** 和 **Succeeded**。這些結果說明的是工作階段如何結束，而非 Claude 是否完成了您提示詞所描述的工作，因此請開啟該次執行並閱讀其逐字稿，以了解實際發生了什麼事。

* **Succeeded**：工作階段結束時，Claude Code 未回報失敗。被封鎖的網路請求、缺少的連接器工具，以及 Claude 無法完成的工作，都會顯示在逐字稿中，而不是在資料列上
* **Failed**：工作階段未正常結束。例如，它意外停止、以錯誤結束，或在執行開始前就已被封存
* **Cancelled**：執行並未失敗，且其工作階段已被封存。如果您封存了一次成功執行的工作階段，該執行會變為 **Cancelled**。任務本身無需任何變更

如果 **History** 下出現警告，請參閱[「The last run」警告](#the-last-run-didnt-start)。

### 編輯與控制排程任務

您可以在詳細資料頁面上：

* 按一下 **Run now** 立即開始執行，無需等待下一個排程時間。
* 使用頁面頂端的開關來暫停或恢復排程。已暫停的任務會保留其設定，但在您重新開啟之前不會執行。
* 開啟任務名稱旁的選單並選擇 **Edit**，以變更名稱、提示詞、儲存庫、環境、連接器或任務的任何觸發條件。**Edit scheduled task** 對話方塊會以與[建立對話方塊](#create-from-the-web)相同的版面配置開啟。若要新增觸發條件，請按一下 **Trigger** 列中的 **+**。按一下 **Save changes** 以套用您的編輯。API token 相關動作會立即生效，無需按 **Save changes**。
* 開啟同一個選單並選擇 **Delete** 以刪除任務。

### 從 CLI 管理排程任務

執行 `/schedule list` 以查看您的排程任務，執行 `/schedule update` 以變更其中一個，或執行 `/schedule run` 以立即啟動其中一個。

您也可以詢問排程任務的執行記錄，例如 `/schedule why did my nightly review do nothing this morning?`。Claude 會列出任務最近的執行及其狀態，以及[在網頁上開啟每次執行](#view-and-interact-with-runs)的連結。它也會讀取執行的日誌來說明發生了什麼事，包括工具錯誤、權限遭拒以及最終結果。需要 Claude Code v2.1.227 或更新版本。

### 儲存庫與分支權限

排程任務需要 GitHub 存取權限才能複製儲存庫。當您從 CLI 使用 `/schedule` 建立排程任務時，Claude 會檢查您的帳戶是否具有執行該命令所在儲存庫的 GitHub 存取權限。若沒有，Claude 會新增一則設定說明，指出如何授予權限。

> [!NOTE]
>
> 請參閱 [GitHub 身分驗證選項](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#github-authentication-options)，以了解授予存取權限的兩種方式。在 Team 和 Enterprise 方案中，必須由您 Claude 組織的[擁有者](https://code.claude.com/docs/zh-TW/server-managed-settings.md#access-control)先開啟各個方式，您才能使用；請參閱[連接 GitHub](https://code.claude.com/docs/zh-TW/web-quickstart.md#connect-github)。

如果在執行時間到來時您的 GitHub 連線遺失或已過期，排程任務會跳過執行，直到您重新連接為止，最長 72 小時。只要在該時間範圍內重新連接 GitHub，任務就會自動恢復。如果 72 小時後仍未連接，任務就會關閉，您需要在重新連接 GitHub 後將其重新開啟。

您新增的每個儲存庫在每次執行時都會被複製。除非您的提示詞另有指定，否則 Claude 會從儲存庫的預設分支開始。如果執行是由 [GitHub pull request 事件](#add-a-github-trigger)觸發，且該 pull request 的儲存庫是任務的第一個儲存庫，則該儲存庫會改為從 pull request 的 head 提交開始。

除非您的提示詞指示 Claude 推送到其他分支，否則 Claude 會將其工作推送到以 `claude/` 為前綴的分支。若要控制執行可以推送到哪些分支，請在 GitHub 上使用分支保護規則或規則集。對於在 Anthropic 管理的基礎設施上進行的執行，以及透過 [Anthropic 的 git 代理伺服器](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#use-the-anthropic-git-proxy)推送的自行託管執行，GitHub 會將這些規則套用於您所連接的 GitHub 存取權限，因此該存取權限可以略過的規則不會阻擋執行的推送。使用您的部署所提供之 git 憑證進行推送的自行託管執行，則會依照那些憑證進行檢查。請參閱[設定 git](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#configure-git)。

### 連接器

排程任務可以使用您已連接的 MCP 連接器，在每次執行期間讀取和寫入外部服務。例如，負責分類支援請求的任務可能會從 Slack 頻道讀取資料，並在 Linear 中建立問題。

連接器是您帳戶上的 [claude.ai 整合](https://code.claude.com/docs/zh-TW/mcp.md#use-mcp-servers-from-claude-ai)。您在 CLI 中使用 `claude mcp add` 於本機新增的 MCP 伺服器儲存在您的機器上，而非您的 claude.ai 帳戶中，因此不會出現在連接器清單中。若要在排程任務中使用其中一個伺服器：

* **作為連接器**：在 [claude.ai/customize/connectors](https://claude.ai/customize/connectors) 將其新增為連接器
* **在儲存庫中**：對於只有一個儲存庫的排程任務，您也可以改為在已提交的 [`.mcp.json`](https://code.claude.com/docs/zh-TW/mcp#project-scope) 中宣告該伺服器，除非該任務是以[專案](https://code.claude.com/docs/zh-TW/claude-projects.md#what-threads-pick-up-from-your-repositories)中的討論串形式執行。若是如此，請將該伺服器新增為連接器。

建立排程任務時，預設會包含您目前所有已連接的連接器。請移除不需要的連接器，以限制 Claude 在執行期間可以存取的工具。您也可以直接從任務的建立或編輯對話方塊新增連接器。

若要在該對話方塊以外管理或新增連接器，請造訪 [claude.ai/customize/connectors](https://claude.ai/customize/connectors)，或在 CLI 中使用 `/schedule update`。

### 執行期間的權限提示

> [!NOTE]
>
> 對於在您組織的自行託管環境中執行的任務，請參閱[權限與工具核准](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#permissions-and-tool-approval)。

當執行在 Anthropic 的雲端上啟動新的工作階段時，除非自動模式無法使用，否則該工作階段會以[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)開始。在自動模式中，分類器模型會允許或封鎖原本需要等待您核准的動作。

在以下這類情況中，執行仍會停止並等待回應：

* **即使在自動模式中也會提示的動作**：例如，符合[詢問規則](https://code.claude.com/docs/zh-TW/permissions.md#manage-permissions)的動作。請參閱[自動模式如何評估動作](https://code.claude.com/docs/zh-TW/permission-modes.md#how-auto-mode-evaluates-actions)
* **重複封鎖**：單次封鎖不會結束執行。一旦封鎖達到自動模式的[重複封鎖門檻](https://code.claude.com/docs/zh-TW/permission-modes.md#repeated-block-thresholds)，執行的工作階段中就會出現權限提示，並持續等待直到有人回應

如果自動模式無法使用，例如您的組織已將其關閉，或任務的模型不支援自動模式，執行會保留其啟動時的權限模式。若要回應等待中的提示，請從任務的[詳細資料頁面](#view-and-interact-with-runs)開啟該執行。

在[專案](https://code.claude.com/docs/zh-TW/claude-projects.md)中，執行可以延續某個討論串，而不是啟動新的工作階段。該執行會保留該討論串當時所處的權限模式。該討論串建立時，除非自動模式無法使用，否則會以自動模式開始。若要回應在該討論串中等待的提示，請參閱[解除等待核准的討論串](https://code.claude.com/docs/zh-TW/claude-projects.md#unblock-a-thread-waiting-on-approval)。

### 執行在未詢問的情況下發布 artifact 時

在以[自動模式](#permission-prompts-during-a-run)進行的執行期間，一旦分類器允許發布，Claude 就會在未詢問您的情況下發布 [artifact](https://code.claude.com/docs/zh-TW/artifacts.md)。在某些情況下仍會先詢問您，例如發布符合[詢問規則](https://code.claude.com/docs/zh-TW/permissions.md#manage-permissions)時。在您[分享它](https://code.claude.com/docs/zh-TW/artifacts.md#share-an-artifact)之前，新的 artifact 僅對您可見。下方的 [Accept edits 規則](#artifacts-in-accept-edits-mode)不適用於自動模式。

當排程任務的工作是讓某個頁面保持最新時，請提供一個您已發布的 artifact 給它。

#### Accept edits 模式中的 artifact

當排程任務的排程或 **Run now** 啟動一次執行時，Claude 可以在未詢問的情況下發布新的 [artifact](https://code.claude.com/docs/zh-TW/artifacts.md)。在您[分享它](https://code.claude.com/docs/zh-TW/artifacts.md#share-an-artifact)之前，新的 artifact 僅對您可見。如果發布內容為頁面宣告了執行階段功能，例如[連接器呼叫](https://code.claude.com/docs/zh-TW/artifacts.md#pull-live-data-with-mcp-connectors)或[檔案下載](https://code.claude.com/docs/zh-TW/artifacts.md#offer-a-file-download)，Claude 會先詢問。

在這類執行中，只有在以下所有條件皆成立時，Claude 才會在未詢問的情況下重新發布現有的 artifact：

* 您可以編輯該 artifact，且它屬於您自己的組織
* 如果發布內容不只包含頁面（例如輔助檔案），則您是該 artifact 的擁有者
* 該 artifact 未公開分享
* 如果該 artifact 已與特定人員或您的組織分享，其檢視者不會自動看到每個新版本
* 發布不會強制覆蓋較新的版本
* 發布未為頁面宣告執行階段功能
* 現有頁面未持有超出該頁面範圍的授權，例如[連接器呼叫](https://code.claude.com/docs/zh-TW/artifacts.md#pull-live-data-with-mcp-connectors)

在所有其他情況下，包括由 API 或 GitHub 觸發條件啟動的執行，Claude 都會先詢問。

### 環境與網路存取

每個排程任務都使用一個[雲端環境](https://code.claude.com/docs/zh-TW/cloud-environments.md)，用來控制網路存取、環境變數和設定指令碼。任務在每次執行時都會繼承環境的網路政策。

**Default** 環境使用 **Trusted** 網路存取，只允許[預設允許清單](https://code.claude.com/docs/zh-TW/cloud-environments.md#default-allowed-domains)透過工作階段的網路存取。在該路徑上對允許清單以外主機的請求會失敗，並傳回 `403` 和 `x-deny-reason: host_not_allowed`。MCP 連接器的流量會經由 Anthropic 的伺服器路由，而不是走該路徑，因此您新增到任務的連接器無需將其主機加入 **Allowed domains** 即可運作。請在[連接器](#connectors)下移除您不需要的連接器。

若要在您自己的某個環境上允許其他網域，請依照以下步驟操作。[組織共用環境](https://code.claude.com/docs/zh-TW/cloud-environments.md#organization-shared-environments)在此處會以唯讀方式開啟，因此改由擁有者從[管理設定](https://claude.ai/admin-settings)中的 **Cloud environments** 頁面變更其網路存取。

**1. 開啟任務進行編輯**

前往 [claude.ai/code/routines](https://claude.ai/code/routines)，按一下排程任務，然後開啟其名稱旁的選單並選擇 **Edit**。**Edit scheduled task** 對話方塊隨即開啟。

**2. 開啟環境選擇器**

前往 **Advanced settings > General > Cloud environment**，如果 **Advanced settings** 處於收合狀態，請先將其展開。按一下顯示您環境名稱（例如 **Default**）的雲端圖示。

**3. 開啟環境設定**

將滑鼠游標停留在清單中的環境上，然後按一下右側出現的設定圖示。

**4. 變更網路存取層級**

在 **Edit cloud environment** 對話方塊中，將 **Network access** 變更為 **Custom**，並在 **Allowed domains** 中輸入您的網域。勾選 **Also include default list of common package managers**，即可在自訂網域之外保留[預設允許清單](https://code.claude.com/docs/zh-TW/cloud-environments.md#default-allowed-domains)。若需要不受限制的存取，請改為選擇 **Full**。

**5. 儲存**

在 **Edit cloud environment** 對話方塊中按一下 **Save changes**，然後關閉其後方的 **Edit scheduled task** 對話方塊。新政策會從下一次執行開始套用。

請參閱[網路存取](https://code.claude.com/docs/zh-TW/cloud-environments.md#network-access)，以了解存取層級和預設允許清單的詳細資訊。

## 用量與限制

排程任務消耗訂閱用量的方式與互動式工作階段相同。您可以在 [claude.ai/settings/usage](https://claude.ai/settings/usage) 查看目前的消耗量。

除了訂閱用量之外，每種啟動執行的方式都有每小時限制：

| 動作 | 限制 | 計算對象 | 超過限制時 |
| :- | :- | :- | :- |
| 排程執行，包括一次性執行 | 每小時 100 次 | 您的帳戶 | 執行會等待到限制重設為止 |
| **Run now**、API 觸發，以及將一次性任務設定為再次執行 | 每小時 30 次 | 每個排程任務，三者共用一個計數 | 動作會失敗，直到限制重設為止 |
| **Run now** 以及將一次性任務設定為再次執行 | 每小時 100 次 | 您的帳戶 | 同上 |
| API 觸發 | 每小時 100 次 | 您的帳戶，與 **Run now** 分開計算 | 同上 |
| GitHub 事件 | 請參閱[新增 GitHub 觸發條件](#add-a-github-trigger) | | |

這些每小時限制都沒有超額使用。

當排程任務達到您的訂閱用量上限時，已開啟用量點數的組織可以透過計量超額使用繼續執行排程任務。若沒有用量點數，額外的執行會被拒絕，直到您的用量時間視窗重設為止。請在 [claude.ai/settings/usage](https://claude.ai/settings/usage) 開啟用量點數。在 Team 和 Enterprise 方案中，由管理員在 [claude.ai/admin-settings/usage](https://claude.ai/admin-settings/usage) 為組織開啟用量點數。

當您的訂閱暫停時，您的排程任務會被擱置且不會執行。訂閱恢復啟用後，請將它們重新開啟。

## 仍使用 routines 名稱的地方

排程任務先前稱為 routines，以下這些地方仍保留先前的名稱。它們所指的都是同一項功能：

* **應用程式**：在部分帳戶中，側邊欄項目和頁面標題顯示為 **Routines**，按鈕顯示為 **New routine**，其他標籤也使用 routine 一詞。若要在該處建立任務，請參閱[完整頁面表單](#full-page-form)。
* **網址**：`claude.ai/code/routines`
* **CLI**：`/schedule` 的別名 `/routines`、該命令的說明，以及 Claude 在設定任務時的回覆
* **API**：`/fire` 端點路徑、其 beta 標頭、其回應 `type`、`<routine-fire-payload>` 標籤，以及 [Trigger a routine through the API](https://platform.claude.com/docs/en/api/claude-code/routines-fire) 參考頁面
* **組織設定**：**Scheduled tasks (Was Routines)** 或 **Routines** 切換開關

## 疑難排解

### `/schedule` 傳回 "Unknown command"

當其中一項需求未滿足時，CLI 會隱藏 `/schedule`：您輸入時，命令選單會顯示 `No commands match "/schedule"`。送出該命令會傳回 `Unknown command: /schedule`，但下方註明會有不同回應的情況除外。

原因通常是以下其中之一：

* 您使用 Console API 金鑰、[Anthropic 設定檔或聯合憑證](https://code.claude.com/docs/zh-TW/authentication.md#anthropic-profiles-and-federation-credentials)，或雲端供應商（例如 Amazon Bedrock、Google Cloud 的 Agent Platform 或 Microsoft Foundry）進行身分驗證。`/schedule` 需要以 claude.ai 訂閱登入。使用 Console API 金鑰或設定檔且已啟用功能旗標擷取時，送出 `/schedule` 會改為顯示 `/schedule is available with Claude for Enterprise — ask your admin about migrating from API-key access`。使用雲端供應商登入時，您仍會看到 `Unknown command: /schedule`。如果您的 shell 中設定了 `ANTHROPIC_API_KEY` 或 `ANTHROPIC_AUTH_TOKEN`，或在 `settings.json` 中設定了 `apiKeyHelper`，請先將其移除，因為這些設定優先於 claude.ai 登入。設定檔或聯合憑證也同樣優先，因此也請將其關閉
* 您已完全登出，沒有 API 金鑰或其他憑證。在已啟用功能旗標擷取時，送出 `/schedule` 會顯示 `/schedule requires a claude.ai subscription. Run /login to sign in with your claude.ai account.` 在 v2.1.268 之前，已登出的工作階段會顯示與 Console API 金鑰相同的 Claude for Enterprise 訊息
* 您位於雲端工作階段中，在此情況下送出 `/schedule` 會回覆該命令在該環境中無法使用。請改從[網頁 UI](https://claude.ai/code/routines) 管理排程任務
* 您組織的政策停用了排程任務所需的[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)。在此情況下，送出 `/schedule` 會改為回覆 [`Cloud sessions are disabled by your organization's policy`](https://code.claude.com/docs/zh-TW/errors#cloud-sessions-are-disabled-by-your-organizations-policy)。在 v2.1.268 之前，它會傳回 `Unknown command: /schedule`
* 擁有者為您的 Team 或 Enterprise 組織[關閉了排程任務](#routines-are-disabled-by-your-organizations-policy)。在 v2.1.227 之前，此情況下命令仍會出現，而 claude.ai 會在 Claude 嘗試建立或執行任務時拒絕它
* 您的 Enterprise 組織以[自訂角色](https://support.claude.com/en/articles/13930452)管理您的存取權，而您的角色中沒有任何一個包含 **Remote sessions** 下的排程任務權限。請聯絡擁有者將其新增至您的其中一個角色

如果原因在於您的 CLI 登入方式或您位於雲端工作階段中，您仍可在 [claude.ai/code/routines](https://claude.ai/code/routines) 建立和管理排程任務。您在該處需要 Pro、Max、Ultra、Team 或 Enterprise 帳戶。如果您的組織關閉了排程任務或雲端工作階段，或您的角色中缺少這些權限，您也無法在網頁上建立排程任務。

### 您的組織已關閉排程任務

您的組織已關閉雲端排程任務，且您無法從本機設定變更此狀態。請詢問您的 Team 或 Enterprise 擁有者，是否能在 [**Organization settings > Capabilities > Remote sessions**](https://claude.ai/admin-settings/capabilities) 開啟 **Scheduled tasks (Was Routines)** 或 **Routines** 切換開關。

### "The last run" 警告

當 **History** 下的警告以 "The last run" 開頭時，請在第一欄中找到該警告，並依照該列的說明操作。之後的某次執行開始後，警告就會清除。

| 警告 | 處理方式 |
| :- | :- |
| "The last run didn't start because your organization had reached its limit on cloud sessions running at once." | 任務無需變更。請稍後點選 **Run now**，或等待下一次執行 |
| "The last run didn't start because its cloud environment couldn't be found or used." | 在任務的詳細資料頁面上，開啟其名稱旁的選單，選取 **Edit**，然後找到[雲端環境選擇器](#environments-and-network-access)。如果其顯示 **Unavailable environment**，表示該環境已封存或您的帳戶已無法使用，請在該處選擇其他環境並儲存變更。否則，請在詳細資料頁面上以 **Run now** 重試，或在選擇器中挑選其他環境並儲存變更 |
| "The last run was blocked because it couldn't access something it needs, or your organization's policy doesn't allow it." | 請確認您的 [GitHub 存取權](#repositories-and-branch-permissions)涵蓋任務的儲存庫。如果已涵蓋，請詢問您 Claude 組織的[擁有者](https://code.claude.com/docs/zh-TW/server-managed-settings.md#access-control)是否有政策封鎖了該任務 |
| "The last run didn't start because of a problem that's usually temporary." | 點選 **Run now** 再試一次，或等待下一次執行 |
| "The last run didn't start because its repository or branch wasn't available." | 請在 GitHub 上確認任務中的每個儲存庫都有[執行起始所用的分支](#repositories-and-branch-permissions)。也請確認您的 [GitHub 存取權](#repositories-and-branch-permissions)涵蓋每個儲存庫，如果您的連線已過期，請重新連接 GitHub |
| "The last run didn't start because some of its settings weren't accepted." | 在任務的詳細資料頁面上，開啟其名稱旁的選單並選取 **Edit**。對話方塊不會標示哪項設定未被接受，因此請在該處逐一檢查每項設定，包括任務的名稱、提示詞、模型、儲存庫、環境、連接器和觸發條件 |
| "The last run stopped because a usage limit was reached." | 關於達到用量上限後任務的執行何時可以再次開始，請參閱[用量與上限](#usage-and-limits) |
| "The last run failed." | 點選 **Run now** 再試一次，或等待下一次執行。失敗的執行沒有可開啟的工作階段 |

## 相關資源

* [`/loop` 與工作階段內排程](https://code.claude.com/docs/zh-TW/scheduled-tasks)：在開啟的 CLI 工作階段中排程本機任務
* [Desktop 排程任務](https://code.claude.com/docs/zh-TW/desktop-scheduled-tasks.md)：在您的機器上執行、可存取本機檔案的本機排程任務
* [雲端環境](https://code.claude.com/docs/zh-TW/cloud-environments.md)：為雲端工作階段設定網路存取、環境變數和設定指令碼
* [Projects](https://code.claude.com/docs/zh-TW/claude-projects.md)：由 Claude 在平行雲端工作階段之間協調的持續性工作；從專案建立的排程任務會出現在其 **Scheduled tasks** 標籤上
* [MCP 連接器](https://code.claude.com/docs/zh-TW/mcp.md)：連接 Slack、Linear 和 Google Drive 等外部服務
* [GitHub Actions](https://code.claude.com/docs/zh-TW/github-actions.md)：在儲存庫事件發生時，於您的 CI 管線中執行 Claude

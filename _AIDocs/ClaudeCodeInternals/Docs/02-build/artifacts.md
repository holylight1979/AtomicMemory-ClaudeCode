<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/artifacts | lastmod: 2026-10-30 | section: Build with Claude Code / Artifacts -->
> 來源：https://code.claude.com/docs/zh-TW/artifacts（官方 zh-TW，lastmod 2026-10-30）｜分類：Build with Claude Code › Artifacts｜EN 摘要：Artifacts turn Claude Code's work into live, interactive pages on claude.ai that you can keep private, share with your organization, or publish to a public link.

# 將工作階段輸出分享為成品

> 成品將 Claude Code 的工作轉化為 claude.ai 上的即時互動頁面，您可以保持私密、與您的組織分享，或發佈到公開連結。

> [!NOTE]
>
> Artifact 適用於 Pro、Max、Ultra、Team 和 Enterprise 方案，並需要使用 [`/login`](https://code.claude.com/docs/zh-TW/setup#authenticate) 登入的工作階段。請參閱[可用性](#availability)以了解完整的需求集合。

[成品](https://claude.com/features/artifacts)是一個即時互動的網頁，Claude Code 從您的工作階段發佈到 claude.ai 上的私密 URL。您在瀏覽器中開啟它，當工作階段繼續進行時，它會就地更新。當您想讓其他人也看到它時，可以從頁面標題中分享它。

![在 claude.ai/code/artifact 中開啟的成品。檢視器標題顯示成品標題 acme-funnel-fix、一個「分享」按鈕和作者頭像。「分享」選單已開啟，顯示「始終分享最新版本」切換、讀取「分享版本 2」的版本選擇器、「Acme 的所有人」對象選擇器和「複製連結」按鈕。在標題下方，成品頁面顯示兩個並排的行動裝置模型、一個漏斗圖表和一列指標卡片。](https://mintcdn.com/claude-code/kaHIYYMIYMYPxQg9/images/artifacts-viewer.png?fit=max\&auto=format\&n=kaHIYYMIYMYPxQg9\&q=85\&s=dbfd671cdb0d15f49f808b9e89778fe1)

## 何時使用 artifact

當終端文字不是 Claude 產生的內容的合適媒介時，請使用 artifact：輸出內容比逐行閱讀更容易查看和互動。Claude 從您的工作階段可以存取的任何內容建立頁面，包括您的程式碼庫和透過您的[連接工具](https://code.claude.com/docs/zh-TW/mcp.md)提取的資料，因此頁面可以顯示需要段落才能描述的內容。例如，要求 Claude：

* 透過附註的差異引導審查者查看提取請求
* 從工作階段已提取的資料呈現儀表板
* 並排配置多個設計或實作選項
* 保持在長任務執行時填入的調查時間軸
* 傳送連結給隊友，而不是將輸出貼到 Slack
* 發佈狀態板，每次有人開啟時[透過 MCP 連接器提取新鮮資料](#pull-live-data-with-mcp-connectors)

請參閱[您可以建立的內容](#what-you-can-build)以取得符合這些的提示，以及[使用 MCP 連接器提取即時資料](#pull-live-data-with-mcp-connectors)以取得連接器支援的板的提示。

### artifact 不是什麼

artifact 是工作的擷取：一個自包含的頁面，沒有後端，因此無法提供多個路由。對於具有後端的託管內部工具，請改為在您自己的基礎設施上部署它。請參閱[頁面限制](#page-constraints)以取得完整的限制集合。

## 建立成品

Claude 可能會在輸出適合頁面時自動發佈成品，或者你可以直接要求建立一個。若要要求，請用純文字命名功能或描述你想要的視覺輸出。任何比以文字閱讀更容易看到的東西都是很好的候選，例如帶有內聯註解的差異、圖表或一組選項進行比較。下面的提示是兩個例子；請參閱[你可以建立的內容](#what-you-can-build)以了解更多模式。

```text wrap theme={null}
Make an artifact that walks through this PR with the diff annotated inline.
```

```text wrap theme={null}
Build a dashboard artifact of last week's deploy failures by service and keep it updated as you investigate.
```

除非您指定位置，否則 Claude 會將頁面寫入專案外暫存目錄中的 HTML 或 Markdown 檔案，然後將其發佈。在您[分享](#share-an-artifact)之前，artifact 僅供您本人檢視。

首次發佈後，Claude 會輸出 URL，您的瀏覽器會開啟新頁面。

* **重新開啟頁面**：隨時按 `Ctrl+]` 即可重新開啟此工作階段最近的 artifact
* **查看此工作階段的 artifact**：提示詞下方的 `⧉` 標籤會顯示 artifact 的名稱，若工作階段有多個 artifact，則顯示數量。在[全螢幕渲染](https://code.claude.com/docs/zh-TW/fullscreen.md)中，按一下即可開啟 [`/artifacts`](#find-an-artifact-again) 清單
* **避免開啟瀏覽器**：在您的環境中設定 `CLAUDE_CODE_ARTIFACT_AUTO_OPEN=0`
* **Remote Control**：如果您是從 claude.ai、Claude Desktop 或 Claude 行動應用程式透過 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 傳送提示詞，執行工作階段的機器上不會開啟任何分頁。下次 Claude 根據您在終端機輸入的提示詞發佈 artifact 時，瀏覽器就會在該機器上開啟

Claude 會為 artifact 選擇標題，以及與頁面內容相符的瀏覽器分頁圖示，例如圖表或日曆。標題會出現在您於 claude.ai 上的 [artifact 庫](#share-an-artifact)以及分享連結中。如果您想要特定的標題或分頁圖示，請向 Claude 提出要求。

如果 Claude 回應無法發佈，或只寫入本機 HTML 檔案而未提供連結，表示您的工作階段未啟用 artifact。請檢查[可用性](#availability)需求。如果終端機顯示 `Artifacts need a claude.ai login`，請參閱[該錯誤的說明](https://code.claude.com/docs/zh-TW/errors.md#artifacts-need-a-claude-ai-login)以了解如何登入。

### Claude Code 何時會在發佈前詢問

Claude 根據您輸入的提示詞所發佈的新 artifact，會直接通過，不會出現權限提示或經過分類器審查。在下列情況中，Claude Code 會先詢問您，或在[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)中交由分類器審查該發佈：

| 時機 | Claude Code 的行為 |
| :- | :- |
| 工作階段處於 [plan mode](https://code.claude.com/docs/zh-TW/permission-modes.md#analyze-before-you-edit-with-plan-mode) | 在每個 artifact 首次發佈前詢問 |
| 該發佈為頁面宣告了執行階段功能，例如[連接器呼叫](#pull-live-data-with-mcp-connectors)或[檔案下載](#offer-a-file-download) | 在該次發佈前詢問 |
| 您已公開分享該 artifact | 在每次對話中變更前詢問一次 |
| Claude 在由[工作階段範圍的排程任務](https://code.claude.com/docs/zh-TW/scheduled-tasks.md)於您的工作階段中觸發所啟動的回合中發佈，而非由您輸入的提示詞啟動 | 在每個 artifact 首次發佈前詢問 |
| Claude 在未經您核准的情況下無法讀取該檔案 | 在發佈前詢問。`Artifact` 工具的允許規則不會略過此提示 |
| 在 [Manual](https://code.claude.com/docs/zh-TW/permission-modes.md) 或 `acceptEdits` 模式中，Claude 對某個 artifact 的檔案進行小幅變更，而該檔案未經您核准便無法編輯，例如 Manual 模式中的專案檔案 | 在發佈該變更前詢問。即使允許規則涵蓋 `Artifact` 工具，仍會詢問您，因為對該檔案的編輯需要您的核准 |

若要讓 Claude 在未經您核准的情況下讀取[工作目錄](https://code.claude.com/docs/zh-TW/permissions.md#working-directories)以外的檔案，請在啟動時使用 [`--add-dir`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags)，或在工作階段中使用 `/add-dir`，將其資料夾新增為工作目錄。Claude 本來就會直接讀取這些目錄中的檔案，以及其寫入頁面的暫存目錄中的檔案，而不會詢問。

如果發佈提示中包含 `Also makes 1 edit to that file on disk.` 之類的句子，表示 Claude 正在一個步驟中變更 artifact 的檔案並將其發佈。當您核准該提示後，Claude Code 會先發佈頁面，然後將變更寫入您的檔案。

## 更新成品

要求 Claude 修訂頁面，或讓長時間執行的任務在進行時重新發佈。Claude 編輯基礎檔案並重新發佈到相同的 URL。

```text wrap theme={null}
在摘要圖表下方新增按地區的細項分析，並重新發佈。
```

任何開啟該頁面的人都會看到就地更新。每次發佈都會成為一個版本，您可以從頁面標題中的**分享**控制項選擇檢視者看到的版本。

若要從不同的工作階段更新成品，請提供 Claude 其 URL，或使用 [`/artifacts`](#find-an-artifact-again) 附加它。如果兩者都沒有，新的工作階段會建立新的成品，而不是更新現有的。

```text wrap theme={null}
使用今天的數字更新 https://claude.ai/code/artifact/5fbea6f3-...。
```

## 再次尋找成品

在 Claude Code 中執行 `/artifacts`，以列出您擁有的 artifact 以及與您共享的 artifact。目前工作階段的 artifact 會排在最前面，位於 **This session** 之下。

選擇一個 artifact，然後按下以下其中一個按鍵：

* **`Enter`**：若該 artifact 已附加到目前的工作階段，則在瀏覽器中開啟它；若尚未附加，則將其附加到目前的工作階段
* **`o`**：在瀏覽器中開啟它
* **`c`**：複製其連結
* **`d`**：在[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)以外，經您確認後永久刪除您擁有的 artifact。其連結將對所有人失效，包括您自己

Claude Code 從您的 claude.ai 帳戶讀取清單，因此當 artifact 的連結已從終端機捲出時，`/artifacts` 在新工作階段中以及執行 `/clear` 之後仍可運作。

## 分享成品

新的成品只有你能看到。若要分享，請在瀏覽器中開啟成品，並使用頁面標題中的**分享**控制項。標題也會連結到你的圖庫 [claude.ai/code/artifacts](https://claude.ai/code/artifacts)，其中列出你建立的每個成品。

您組織中的檢視者可以看到誰發佈了該頁面：在組織內分享的 artifact 上，您的名稱會在標題選單中；在公開 artifact 上，已登入的組織成員檢視者會在頁面標題中看到您的名稱。未登入或來自組織外部的檢視者開啟公開連結時，會看到標籤 `Content is user-generated and unverified.` 而不是您的名稱。

你可以分享給誰取決於你的方案：

* **在組織內**：在 Team 和 Enterprise 方案上，授予組織中特定人員或所有人的存取權。檢視者以組織成員身分登入 claude.ai 以查看該頁面。
* **公開**：分享一個連結，網際網路上的任何人都可以開啟，無需 claude.ai 登入。在 Team 和 Enterprise 方案上，公開分享處於關閉狀態，直到擁有者[為組織啟用它](#control-public-sharing)。

### 連結到特定檢視

如果頁面有多個檢視，例如分頁或區段，您可以直接連結到其中一個。請向 Claude 索取連結：

```text wrap theme={null}
Give me a link to each tab of the deploy failures dashboard.
```

每個連結都是 artifact 的連結，並在結尾加上錨點，例如 `#overview`。

### 讓某人與你一起編輯

與你分享的人預設為檢視者：他們可以看到你發佈的每個版本，但無法變更頁面。在 Team 和 Enterprise 方案上，你也可以讓某人成為編輯者。在分享對話中，新增一個人並將其角色從**檢視者**切換為**編輯者**。

編輯者發佈新版本的方式與你[從另一個工作階段更新成品](#update-an-artifact)相同：他們提供成品的 URL 給 Claude，或從 [`/artifacts`](#find-an-artifact-again) 附加它，Claude 會提取目前內容並使用他們的變更重新發佈。所有開啟該頁面的人都會即時看到每個更新。

如果編輯者在 Claude 持有該頁面較舊副本時發佈，Claude Code 會拒絕以該副本為基礎的發佈。接著 Claude 會將其變更合併到較新的版本上，然後再次發佈。

## 閱讀與您共享的成品

當有人與您共享成品時，您可以讓 Claude 閱讀它：提供 Claude 其 URL，或從 [`/artifacts`](#find-an-artifact-again) 附加它。

Claude 閱讀他人撰寫的頁面的方式與它使用 [WebFetch](https://code.claude.com/docs/zh-TW/tools-reference.md#webfetch-tool-behavior) 閱讀網頁的方式相同：它取得所詢問內容的摘要，而不是原始頁面，摘要報告寫入頁面的指示，而不是轉達它們。Claude Code 也會將頁面的完整原始碼儲存到本機檔案，Claude 可以在需要確切內容時開啟該檔案，例如重新發佈成品作為 [編輯器](#let-someone-edit-with-you)。

在以下情況下，Claude Code 會在 Claude 閱讀 artifact 之前要求您核准，此外還有您的權限模式或規則所要求的任何提示：

* **沒有網路存取權的雲端工作階段**：對於 [雲端環境](https://code.claude.com/docs/zh-TW/cloud-environments.md#access-levels)，即 **None** 等級。在 [自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode) 中，分類器可以代為核准；在 [Cowork](https://claude.com/product/cowork) 工作階段中，核准只能由您進行。
* **其他組織的公開 artifact**：即使在自動模式下，Claude Code 也會先詢問您。在 Claude Code 無法詢問您的情況下，例如在 `bypassPermissions` 模式中，Claude 無法閱讀該 artifact。只有在 [功能旗標擷取](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching) 開啟時，Claude 才能閱讀這些 artifact。
* **無法確認擁有者或網路設定**：當 Claude Code 無法確認 artifact 的建立者，或無法確認雲端工作階段的網路設定時，它會詢問您，而您的核准僅適用於該次請求。
* **plan mode**：在 [plan mode](https://code.claude.com/docs/zh-TW/permission-modes.md#analyze-before-you-edit-with-plan-mode) 中，Claude Code 會在 Artifact 工具閱讀您組織中其他人建立的 artifact 之前詢問您。

當 Claude 使用 WebFetch 閱讀 artifact 時，WebFetch 本身的 [提示規則](https://code.claude.com/docs/zh-TW/tools-reference.md#webfetch-tool-behavior) 仍然適用。

## 收集成品上的評論

當您在組織內分享成品時，與您分享的人可以在頁面上留下評論，您可以讓 Claude 讀取這些評論並回覆。您需要 Claude Code v2.1.221 或更新版本。Claude 在兩種情況下會讀取評論：

* **您要求 Claude 讀取評論**：提供 Claude 成品的 URL 並要求查看評論。Claude 會列出每個執行緒，並標記可以編輯成品的人發送給它的評論。
* **可以編輯成品的人向 Claude 發送評論**：在頁面上的執行緒中，他們使用**傳送給 Claude** 發送評論，或在其中提及 `@claude`。無論哪種方式，他們都會啟動該執行緒。

Claude 只能回覆或解決已啟動的執行緒。其他執行緒保持開啟狀態，直到某人在頁面上解決它們。檢視者會看到每個回覆都歸屬於 Claude，透過您。

如果您公開分享成品，只有公開連結存取的人看不到其評論，也無法新增任何評論。現有評論執行緒會保留在成品上，您和其編輯者仍然可以讀取並回覆它們。

若要自行要求評論，請提供 Claude URL：

```text wrap theme={null}
Read the comments on https://claude.ai/code/artifact/5fbea6f3-... and make the changes the commenters ask for.
```

如果 Claude 告訴您它無法讀取評論，請確認您的版本、您的工作階段和您的功能旗標設定：

* 您執行的是 Claude Code v2.1.221 或更新版本。
* 您不在安裝 Claude Code 或從 v2.1.221 之前的版本升級後的第一個工作階段中。在[安裝或升級後的第一個工作階段](https://code.claude.com/docs/zh-TW/env-vars.md#first-session-after-an-install-or-upgrade)中，Claude 可能還無法讀取評論；開始新的工作階段並再次詢問。
* 您未關閉功能旗標擷取。

### 讓 Claude 自動回覆評論

在您的工作階段發佈 artifact 後，Claude Code 會監視該 artifact 的評論。當可以編輯 artifact 的人向 Claude 發送評論時，它會立即到達您的工作階段，Claude 可以讀取執行緒並回覆，而無需您詢問。

您需要 Claude Code v2.1.228 或更新版本。如果您關閉了[功能旗標擷取](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)，Claude Code 不會監視評論。

您的[權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md)決定了當發送的評論到達時 Claude 的行為：

* **Claude 自動回覆**：如果您處於允許 Claude 在不詢問您的情況下發佈回覆的權限模式，Claude 會讀取執行緒並回覆。您會看到 `Auto-replied to comment thread on Artifact: <name>`。
* **Claude 等待您**：在計畫模式外，當發佈回覆需要您的批准時，您會看到 `Comments are waiting on Artifact: <name>`。Claude 隨後會要求您批准讀取執行緒，然後再次批准發佈回覆。
* **Claude 在計畫模式中暫停**：您會看到 `Comments are waiting on Artifact: <name>`，Claude 不會回覆，直到您離開計畫模式並要求它讀取並回覆。

Claude 在處理該成品上的 60 個已發送評論或執行緒啟動後，也會停止自動回覆該成品。您會看到 `Comments are waiting on Artifact: <name>` 一次，當該小時的評論過期時，Claude 會重新開始。

執行 `/tasks` 以查看您的工作階段正在監視的 artifact。`/tasks` 會將 Claude Code 自行啟動的監視歸類在 **System tasks** 列下。在該列上按 `Enter` 即可列出它們。您要求 Claude 啟動的監視會顯示在 **Monitors** 下。

您可以透過以下任何方式停止 Claude 自動回覆：

* **在閒置提示字元處按一次 Ctrl+C**：Claude 暫停回覆您的工作階段正在監視的每個成品。在您發送下一條訊息後，回覆會重新開始。
* **在 `/tasks` 中停止任務**：Claude 停止回覆該成品，直到您要求它在那裡恢復回覆。重新發佈成品不會再次開始回覆，當您稍後恢復工作階段時，停止仍然適用。
* **在 3 秒內按兩次 `Ctrl+X Ctrl+K`**：[停止每個執行中背景子代理](https://code.claude.com/docs/zh-TW/interactive-mode.md#general-controls)的和弦也會停止 Claude 在工作階段的其餘時間內回覆每個成品。要求 Claude 恢復回覆不會撤銷此停止。

由 Claude Code 自行啟動的監視，可能會在 artifact 數小時沒有活動後結束。若要重新啟動監視，請再次發佈 artifact 或要求 Claude 監視它。

如果傳遞評論的服務變得不可用或停止回應，Claude Code 會嘗試重新連接一段時間，然後停止監視您的工作階段正在監視的每個成品。

## 使用 MCP 連接器拉取即時資料

每當有人檢視 artifact 時，artifact 可以呼叫 [MCP 連接器](https://code.claude.com/docs/zh-TW/mcp.md#use-mcp-servers-from-claude-ai)，因此頁面會顯示目前資料，而不是建立該頁面的工作階段所收集的快照。來自 artifact 的連接器呼叫適用於 Pro、Max、Ultra、Team 和 Enterprise 方案，並需要 Claude Code v2.1.209 或更新版本。在較早的版本上，Claude 會發佈該頁面，其中包含工作階段在建立時收集的任何資料。

若要建立連接器支援的頁面，請在提示中命名連接器和您想要的資料：

```text wrap theme={null}
建立一個顯示我們開放中 pull request 的儀表板 artifact，該 artifact 在頁面載入時透過我的 GitHub 連接器拉取即時清單。
```

Claude 會在發佈時宣告該頁面可能呼叫的連接器，且該頁面無法呼叫該宣告之外的連接器。只有來自您 claude.ai 帳戶的連接器符合資格：Claude 在宣告中命名它們，當有人檢視該頁面時，每個呼叫都會 [透過檢視帳戶自己的連接](#how-connector-calls-work-for-viewers) 執行到該連接器。您在 Claude Code 中設定的本機 MCP 伺服器（例如來自 `.mcp.json` 的伺服器）可以在 Claude 建立頁面時提供資料，但已發佈的頁面無法呼叫它們。

該頁面在載入時會擷取資料，並可以按間隔重新整理或當檢視者在頁面上使用重新整理控制項時重新整理。回應會快取在檢視者的瀏覽器中，因此重新開啟的頁面會立即從快取的回應呈現，然後使用新鮮結果進行更新。

### 連接器呼叫如何為檢視者運作

當已發佈的頁面呼叫連接器時，該呼叫會使用檢視該頁面的人的帳戶，而不是發佈該頁面的人的帳戶：

* **每個檢視者使用自己的連接器**：呼叫會透過檢視帳戶的已連接工具進行，因此兩個人開啟相同的儀表板可能會看到不同的資料，取決於他們的帳戶可以存取的內容。該頁面永遠不會看到任何人的認證；claude.ai 代表該頁面進行呼叫。
* **檢視者先核准存取**：claude.ai 在該頁面的第一個連接器呼叫之前會要求每個檢視者的許可。拒絕的檢視者或尚未連接該頁面使用的連接器的檢視者仍然可以看到該頁面，但沒有其即時區段。
* **動作也使用檢視者的帳戶**：頁面可以提供控制項，這些控制項會叫用具有副作用的連接器工具，例如發佈訊息或更新問題。該動作會透過選擇該控制項的任何人的帳戶進行。

當您計畫共享連接器支援的頁面時，請要求 Claude 在每個即時區段中包含一個後備訊息，該訊息命名它需要的連接器。缺少連接的檢視者會看到要連接的內容，而不是空白區段。

您可以 [在您的組織內或公開共享連接器支援的頁面](#share-an-artifact)，如您的方案和組織設定所允許。連接器呼叫不會針對未登入 claude.ai 或來自您組織外部的公開連結的檢視者執行。該檢視者會看到沒有其即時區段的頁面。

### 頁面對檢視者不顯示即時資料

當連接器支援的頁面呈現但其即時區段對您組織中的檢視者保持空白時，請檢查這些原因：

* **檢視者尚未連接連接器**：連接器是按帳戶的，因此每個檢視者都需要自己的連接到該頁面呼叫的每個連接器。他們可以在 claude.ai 上的 [**Customize > Connectors**](https://claude.ai/customize/connectors) 下新增一個，然後重新載入頁面。
* **檢視者拒絕了許可要求**：拒絕會持續到該頁面載入的其餘部分。重新載入頁面會帶回許可要求。
* **連接器呼叫已針對組織關閉**：擁有者控制管理設定中的 [**Enable artifact connectors** 切換](#control-connector-calls-from-artifacts)。
* **頁面呼叫連接器未公開的工具名稱**：受影響的區段對所有人（包括您）保持空白。當頁面命名閘道式連接器後面的個別工具，而該連接器只公開其自己的少數工具時，就會發生這種情況。要求 Claude 修正頁面呼叫的工具名稱並再次發佈。

  當 Claude 發佈頁面且該連接器的工具在您的工作階段中可用時，Claude Code 會檢查頁面宣告的工具名稱與它們的對比，警告 Claude 不符合的名稱，並在沒有任何名稱符合時拒絕發佈。在 v2.1.265 之前，它會在不檢查它們的情況下發佈頁面。

## 提供檔案下載

成品可以向檢視者提供頁面生成的檔案，例如表格的 CSV 匯出或圖表的 PNG。檢視者透過頁面上的下載控制項（例如按鈕）來儲存檔案。檔案下載是 claude.ai 按帳戶啟用的執行時功能，因此 Claude 在建立控制項之前會檢查您的帳戶是否具有此功能。

檢視者無法從普通下載連結或頁面上的指令碼儲存檔案，因為 claude.ai 上的成品檢視器會阻止頁面本身啟動的任何下載，包括指向 `data:` 或 `blob:` URL 的連結。如果頁面具有以這種方式建立的下載按鈕，請要求 Claude 使用下載功能重新建立它們。

若要提供檔案，請在您的提示中要求控制項和檔案格式：

```text wrap theme={null}
Add a button that downloads this table as a CSV file.
```

Claude 將下載功能宣告為發佈的一部分，其方式與[使用 MCP 連接器提取即時資料](#pull-live-data-with-mcp-connectors)相同。

## 您可以建立的內容

成品是單個 HTML 頁面，因此您可以用 HTML、CSS 和內聯 JavaScript 表達的任何內容都在範圍內。下面的模式最常出現。

### 逐步查看變更

要求一個頁面，在相關行旁邊呈現差異或設計變更並帶有註解，以便審查者可以在程式碼旁邊閱讀您的推理，而不是從描述中重建它。

```text wrap theme={null}
Make an artifact that walks through this PR. Render the diff with margin annotations and color-code findings by severity.
```

### 比較替代方案

要求在一個頁面上有多個變體，以便您可以相互評估它們。這適用於佈局、複製、API 形狀或實現計劃。

```text wrap theme={null}
Make an artifact with four distinctly different layouts for the settings panel. Vary density and grouping, and lay them out as a grid with a one-line tradeoff under each.
```

### 使用互動控制項進行調整

要求滑塊、切換或輸入欄位綁定到您正在調整的任何內容，以便您可以直接探索值，而不是描述它們。

```text wrap theme={null}
Build an artifact with sliders for the easing curve, duration, and delay so I can try values on this transition. Show the animation live as I move them.
```

### 將結果帶回您的工作階段

成品可以充當輕量級編輯器，用於您隨後交給 Claude 的決定。要求匯出控制項，產生您可以貼到終端的文字，以便與頁面互動的結果流回工作階段，而不是停留在頁面上。

```text wrap theme={null}
Make a triage board artifact with each open issue as a draggable card across Now, Next, Later, and Cut columns. Add a "Copy as prompt" button that gives me the final ordering to paste back here.
```

### 追蹤進行中的工作

要求 Claude 在長任務執行時保持成品最新，以便任何有連結的人都可以跟進，而無需閱讀終端。

```text wrap theme={null}
Turn this migration plan into a checklist artifact. Check items off as you complete them and add a note for anything you skip.
```

## 改進視覺設計

Claude 在建立成品時會應用內建的設計技能，因此頁面會獲得經過深思熟慮的調色盤、排版和版面配置，無需額外提示。該技能也會在選擇自己的設計之前，先查看您專案中是否存在現有的設計系統。設計權杖是您設計系統重複使用的具名顏色、排版和間距值。為了保持成品與您產品品牌的一致性，請將它們記錄在 Claude 可以找到的地方，例如專案的 [CLAUDE.md](https://code.claude.com/docs/zh-TW/memory.md) 或您儲存庫中的主題檔案：

```markdown theme={null}
## Design system

- Colors: primary #1a4d8f, accent #f59e0b, surface #f8fafc
- Typography: Inter for body, JetBrains Mono for code
- Spacing: 8px scale, 6px border radius
```

Claude 將您的設計系統視為比自己的選擇更高的優先順序，並將您的提示視為比兩者都更高的優先順序。上面的標題和格式是一個範例；任何清晰的顏色、字型和間距清單都可以使用。

對於排版，Claude 可以從 Google Fonts 載入字型，這是成品頁面可以載入的唯一外部字型來源。Claude 會將任何其他字型內嵌為 `@font-face` 資料 URI，並為每個字型提供備用堆疊，因此即使字型無法載入，頁面仍會呈現。若要使用特定字型，請在您的提示或設計系統中命名它。

## 從投影片、設計或文件範本開始

與其從頭開始建立頁面，Claude 可以從您 claude.ai 帳戶上的其中一個範本開始建立成品：[Claude Slides](https://support.claude.com/en/articles/17153992-what-are-artifacts-and-how-do-i-use-them#h_11d5a9a5fa) 用於簡報、[Claude Design](https://support.claude.com/en/articles/14604416-get-started-with-claude-design) 用於視覺設計，或 [Claude Docs](https://support.claude.com/en/articles/16923645-get-started-with-claude-docs) 用於其他人將閱讀和編輯的文件。每個都在 claude.ai 上的自己編輯器中開啟，您和您的隊友可以直接變更它或要求 Claude 變更，並將其匯出為 PowerPoint、PDF 或 Word 等格式。

若要從範本開始，請描述您想要的內容，例如「將遷移說明轉換為週四審查的投影片組」或「將此計畫寫成團隊的文件」。Claude 會選擇相符的範本，從您的要求和工作階段已有的內容填入，並提供您連結。對於投影片組或設計，您也可以使用簡介執行 `/slides` 或 `/design`。

> [!NOTE]
>
> 範本處於測試版。它們在 Pro、Max、Ultra 和 Team 方案上預設為開啟。在 Enterprise 方案上，擁有者會在 **Organization settings > Artifacts** 下[開啟每個範本](https://support.claude.com/en/articles/16994751-artifacts-admin-guide-for-team-and-enterprise-plans)。如果您的組織已關閉 Slides 範本，`/slides` 不會出現；如果它已關閉 Design 範本，`/design` 不會草擬設計。兩個命令都需要 Claude Code v2.1.265 或更新版本，以及 [artifact 可用](#availability)的工作階段。

### 製作投影片組

使用簡介執行 `/slides`，說明投影片組涵蓋的內容及其對象：

```text wrap theme={null}
/slides a quarterly review of the platform team's reliability work, for the engineering all-hands
```

Claude 會建立 Claude Slides 成品並提供您連結。在桌面瀏覽器中開啟它以編輯或呈現投影片組。如果您執行 `/slides` 時沒有簡介，Claude 會在建立任何內容之前詢問投影片組應該涵蓋的內容。

### 草擬設計畫布

若要模擬 UI、螢幕流程、登陸頁面或海報，而不是建立頁面，請使用簡介執行 `/design`。Claude 會在一個畫布上將設計草擬為美工板，並將畫布發佈為 Claude Design 成品。簡介會命名您想要繪製的內容：

```text wrap theme={null}
/design a settings screen for a mobile banking app
```

在桌面瀏覽器中開啟已發佈的成品以檢閱美工板。在美工板上選取元素並變更它，您的編輯會自動儲存。您可以將每個美工板匯出為 PNG 或 PDF。

### 使用 Claude Docs 撰寫文件

Claude Docs 作為 claude.ai [連接器](https://code.claude.com/docs/zh-TW/mcp.md#use-mcp-servers-from-claude-ai)而不是命令到達 Claude Code。連接後，`/mcp` 會將其列為 `claude.ai Claude Docs`。針對供其他人使用的文件的要求會進入 Claude Docs 而不是成品頁面：規格、提案或您在工作階段中進行的計畫寫法。Claude 會在草擬文件時提供文件的連結。

屬於程式碼庫的文件（例如 README）會保持為檔案。若要取得 Claude 否則會放在 Claude Docs 中的內容的檔案，請命名格式，例如 `.docx` 或儲存庫中的 Markdown 檔案。若只要關閉 `claude.ai Claude Docs` 連接器，請參閱[停用 claude.ai 連接器](https://code.claude.com/docs/zh-TW/mcp.md#disable-claude-ai-connectors)。

## 頁面限制

每個成品是一個獨立的頁面。Claude Code 會將您發佈的檔案包裝在 HTML 文件殼層中，並在嚴格的內容安全政策 (CSP) 下提供服務，這會限制頁面可以執行的操作。

| 限制 | 效果 |
| :- | :- |
| 外部請求 | 頁面可以從 Google Fonts 載入字型，以及從[五個公開 CDN 主機](#allowlist-the-viewer-domain)載入指令碼：cdnjs、unpkg、Tailwind 和 jQuery CDN，以及 jsDelivr 上的選定路徑，例如 `/npm/`。CSP 會阻止所有外部影像和所有其他外部指令碼、樣式表和字型，並讓 `fetch`、XHR 和 WebSocket 呼叫只能到達頁面自身的來源和 Google Fonts 主機。因此，Claude 會從這些 CDN 之一載入頁面需要的任何程式庫，內嵌所有其他 CSS 和 JavaScript，並將影像嵌入為資料 URI。[Connector 呼叫](#pull-live-data-with-mcp-connectors)會通過 claude.ai 進行，它會自行進行網路呼叫。 |
| 無後端 | 成品是靜態頁面。它無法自行驗證檢視者。 |
| 下載 | 頁面無法自行啟動下載。為了讓檢視者儲存頁面產生的檔案，Claude 會宣告下載功能。請參閱[提供檔案下載](#offer-a-file-download)。 |
| 單一頁面 | 相對連結無法解析，因為頁面旁邊沒有部署任何內容。對於多區段內容，Claude 使用頁面內錨點而不是個別檔案。 |
| 來源檔案類型 | 發佈的檔案必須是 `.html`、`.htm` 或 `.md`，且必須解碼為 UTF-8，或根據其位元組順序標記解碼為小端 UTF-16。Markdown 檔案會呈現為樣式化的文件頁面，並具有語法醒目提示的程式碼。無法解碼或包含替換字元 `U+FFFD` 的檔案會[被拒絕並顯示要修正的行和列](https://code.claude.com/docs/zh-TW/errors.md#the-source-file-is-not-valid-utf-8-text)。 |
| 來源位置 | 路徑指向網路主機的檔案會在未被讀取的情況下遭到拒絕。請參閱[未發佈：該檔案位於網路共用上](https://code.claude.com/docs/zh-TW/errors.md#not-published-that-file-is-on-a-network-share)，了解哪些路徑會遭到拒絕，以及 Windows 上對應磁碟機的例外情況。 |
| 呈現大小 | 呈現的頁面必須為 16 MiB 或更小。大型嵌入影像通常是發佈因大小而失敗的原因。 |

產生成品會像任何其他回應一樣使用輸出權杖，而樣式化頁面比相同內容作為終端文字更耗費權杖。內嵌 CSS、用於互動控制的 JavaScript，尤其是嵌入為資料 URI 的影像，是主要貢獻者。若要減少成品的權杖成本：

* 對於圖表，優先使用 SVG 或 HTML 和 CSS，而不是嵌入的光柵影像
* 省略您不需要的互動性
* 讓頁面摘要大型資料集，而不是完整內嵌它們

## 可用性

成品需要下面的每個條件。當不滿足其中一個時，Claude 寫入本地 HTML 檔案或說它無法發佈。

| 要求 | 可用時間 |
| :- | :- |
| 方案 | Pro、Max、Ultra、Team 或 Enterprise。在 Pro、Max 和 Ultra 方案上，artifact 在您分享之前僅供您私人使用，且不適用管理員管理。在 Team 和 Enterprise 方案上，artifact 預設開啟，Owner 可以在 claude.ai 管理設定中[為組織關閉它們](#manage-artifacts-for-your-organization)。 |
| 身分驗證 | 工作階段由 claude.ai 帳戶支援：在 CLI 或桌面應用程式中使用 `/login` 登入。Claude Tag 工作階段不需要登入步驟。使用 API 金鑰、[閘道 token](https://code.claude.com/docs/zh-TW/llm-gateway) 或雲端提供者憑證的工作階段無法發佈。 |
| 模型提供者 | Anthropic API。在 [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md)、[Google Cloud 的 Agent Platform](https://code.claude.com/docs/zh-TW/google-vertex-ai.md) 或 [Microsoft Foundry](https://code.claude.com/docs/zh-TW/microsoft-foundry.md) 上不可用。 |
| 組織政策 | 客戶管理的加密金鑰 (CMEK)、HIPAA 和[零資料保留](https://code.claude.com/docs/zh-TW/zero-data-retention.md)未為組織啟用。 |
| 使用介面 | Claude Code CLI，或 Claude 桌面應用程式版本 1.13576.0 或更新版本。[Claude Tag](https://claude.com/docs/claude-tag/overview) 工作階段在 Claude Tag 和 artifact 都為組織啟用時也可以發佈 artifact。由 [`claude remote-control`](https://code.claude.com/docs/zh-TW/remote-control) 提供服務的工作階段，在由您自己啟動該工作階段時可以發佈 artifact。需要 Claude Code v2.1.281 或更新版本。在 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md)、GitHub Action 和 MCP 伺服器情境中預設關閉，當您從自己的終端機或指令碼以 [`-p`](https://code.claude.com/docs/zh-TW/headless) 執行 Claude Code 時，以及設定 [`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`](https://code.claude.com/docs/zh-TW/env-vars) 時亦同。 |

您的組織是否允許成品來自您組織的政策，Claude Code 從 `api.anthropic.com` 載入。當 Claude Code 無法載入政策時，成品不可用。當您要求一個時，Claude 會說明原因。

如果涉及代理、VPN 或網路篩選，請要求您的 IT 管理員允許 `api.anthropic.com` 通過。Claude Code 會在背景中持續重試，一旦政策載入並允許，成品就會變成可用。

## 停用 artifacts

若要關閉您自己工作階段中的 artifacts，無論您的組織設定為何，請使用以下任一方式：

| 位置 | 操作 |
| :- | :- |
| [`/config`](https://code.claude.com/docs/zh-TW/commands) | 關閉 **Artifacts** 列，這會將 [`"enableArtifact": false`](https://code.claude.com/docs/zh-TW/settings-reference#enableartifact) 寫入您的使用者設定 |
| [設定檔](https://code.claude.com/docs/zh-TW/settings.md) | 設定 `"enableArtifact": false`。已棄用的 `"disableArtifact": true` 也會關閉 artifacts |
| [環境變數](https://code.claude.com/docs/zh-TW/env-vars.md) | 設定 `CLAUDE_CODE_DISABLE_ARTIFACT=1` |
| [權限規則](https://code.claude.com/docs/zh-TW/permissions.md) | 將 `Artifact` 新增至 `permissions.deny` |

一旦您在 [`--settings`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 檔案中或使用 `CLAUDE_CODE_DISABLE_ARTIFACT` 關閉 artifacts，或您的管理員在[受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)中關閉它們，就沒有設定檔能將其重新開啟。

您也可以在專案的 `.claude/settings.json` 或 `.claude/settings.local.json` 中設定 `"enableArtifact": false`，以關閉該專案中工作階段的 artifacts。任一檔案中的 `"enableArtifact": true` 都不會將其重新開啟。在專案和本機設定中接受此金鑰需要 Claude Code v2.1.242 或更新版本。

如果您新增 `WebFetch` deny 或 ask 規則但不含 `domain:` 部分，它不會關閉 artifacts 或阻止 artifact 讀取。[`permissions` 中 `deny` 或 `ask` 內的 `WebFetch(domain:claude.ai)` 規則確實適用於 artifact 讀取](https://code.claude.com/docs/zh-TW/permissions#allow-or-deny-every-fetch)。

## 為您的組織管理成品

Team 和 Enterprise 方案上的擁有者從 [claude.ai 管理設定](https://claude.ai/admin-settings/artifacts)控制成品。成品內容儲存在 Anthropic 營運的基礎設施上，僅對發佈組織的已驗證成員可見，以及他們與之分享的人員，除非成品是[公開分享](#control-public-sharing)。

### 啟用或停用成品

要為整個組織啟用或停用成品，請前往 [**組織設定 > 成品**](https://claude.ai/admin-settings/artifacts)並使用**成品**切換。在具有角色型存取控制的 Enterprise 方案上，您還可以將成品範圍限制為特定角色：前往 [**組織設定 > 角色**](https://claude.ai/admin-settings/roles)、編輯角色，並設定**成品**許可。

### 控制來自成品的連接器呼叫

[來自成品的連接器呼叫](#pull-live-data-with-mcp-connectors)有自己的切換，與開啟或關閉成品的**成品**切換分開。前往 [**組織設定 > 功能**](https://claude.ai/admin-settings/capabilities)並使用**啟用成品連接器**切換。同一個切換控制在 claude.ai 對話中建立的成品的連接器呼叫。

### 控制公開分享

在 Team 和 Enterprise 方案上，公開分享預設為關閉。要讓成員將成品發佈到任何人都可以檢視而無需登入的公開連結，請前往 [**組織設定 > 成品**](https://claude.ai/admin-settings/artifacts)並在**成品**切換下開啟**外部分享**。將其關閉會阻止透過現有公開連結的存取，而不會變更每個成品的對象；如果您重新啟用它，存取將恢復。

### 設定保留政策

要設定在自動刪除之前保留成品的時間，請前往 [**組織設定 > 資料和隱私**](https://claude.ai/admin-settings/data-privacy-controls)。您可以為仍然是其作者私人的成品和已共享的成品設定單獨的保留期。

### 檢查稽核日誌

發佈、分享和刪除成品各自出現在您組織的稽核日誌中，位於 `claude_artifact_*` 事件類型下，與在 claude.ai 對話中建立的成品使用的相同系列。

### 允許列表檢視器網域

claude.ai 上的檢視器從沙箱化的 `*.claudeusercontent.com` 來源載入每個成品。如果您的組織限制出站網路存取，請將該網域新增到您的允許列表中，以及 `claude.ai`。請參閱[網路存取要求](https://code.claude.com/docs/zh-TW/network-config.md#network-access-requirements)以了解完整清單。

從 [Google Fonts](#improve-the-visual-design) 載入字型的成品也會要求 `fonts.googleapis.com` 和 `fonts.gstatic.com`。兩個主機都是選用的。如果您封鎖它們，成品會以備用字型呈現。使用快速拒絕而不是無聲丟棄來封鎖，以便字型要求立即失敗，而不是延遲頁面的首次呈現。

成品也可以從 `cdnjs.cloudflare.com`、`cdn.jsdelivr.net`、`cdn.tailwindcss.com`、`code.jquery.com` 和 `unpkg.com` 載入 JavaScript 程式庫（例如 React 或圖表套件），而不能從任何其他外部主機載入。如果您封鎖這些主機，成品中依賴程式庫的部分將無法運作，與被封鎖的字型不同，被封鎖的程式庫沒有備用方案。在這裡也使用快速拒絕，以便被封鎖的程式庫要求立即失敗，而不是掛起直到逾時。

### 使用 Compliance API 列出和刪除成品

[Compliance API](https://docs.claude.com/en/api/compliance) 提供端點來列出組織的成品、檢索特定版本的內容和刪除成品：

| 方法 | 端點 |
| :- | :- |
| `GET` | `/v1/compliance/apps/code/artifacts` |
| `GET` | `/v1/compliance/apps/code/artifacts/{artifact_id}/versions/{version_id}` |
| `DELETE` | `/v1/compliance/apps/code/artifacts/{artifact_id}` |

有關請求和回應 schema，請參閱 [Compliance API 參考](https://platform.claude.com/docs/en/api/compliance/apps/code/artifacts)。

## 相關資源

* 瀏覽與成品配對的[提示模式和工作流程](https://code.claude.com/docs/zh-TW/prompt-library.md)
* 將您重複使用的成品提示轉變為[技能](https://code.claude.com/docs/zh-TW/skills.md)，以便您可以將其作為命令呼叫
* [連接 MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md)，以便 Claude 可以將資料提取到成品中，同時建置頁面

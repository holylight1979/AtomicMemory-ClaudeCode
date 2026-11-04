<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/analytics | lastmod: 2026-11-02 | section: Administration / Usage and costs -->
> 來源：https://code.claude.com/docs/zh-TW/analytics（官方 zh-TW，lastmod 2026-11-02）｜分類：Administration › Usage and costs｜EN 摘要：View Claude Code usage metrics, track adoption, and measure engineering velocity in the analytics dashboard.

# 使用分析追蹤團隊使用情況

> 在分析儀表板中檢視 Claude Code 使用指標、追蹤採用情況，並衡量 Claude Code 對工程速度的影響。

Claude Code 提供分析儀表板，幫助組織瞭解開發人員使用模式、追蹤貢獻指標，並衡量 Claude Code 對工程速度的影響。存取您方案的儀表板：

| 方案 | 儀表板 URL | 包含內容 | 深入瞭解 |
| - | - | - | - |
| Claude for Teams / Enterprise | [claude.ai/analytics/claude-code](https://claude.ai/analytics/claude-code) | 使用指標、與 GitHub 整合的貢獻指標、排行榜、資料匯出 | [詳細資訊](#access-analytics-for-team-and-enterprise) |
| API (Claude Console) | [platform.claude.com/claude-code](https://platform.claude.com/claude-code) | 使用指標、支出追蹤、團隊見解 | [詳細資訊](#access-analytics-for-api-customers) |

Code Review 有其專屬的儀表板。如需審查活動與支出，請參閱[檢視使用情況](https://code.claude.com/docs/zh-TW/code-review-costs.md#view-usage)。

## 存取 Team 和 Enterprise 的分析資料

導覽至 [claude.ai/analytics/claude-code](https://claude.ai/analytics/claude-code)。管理員和擁有者可以檢視儀表板。

Team 和 Enterprise 儀表板包括：

* **使用情況指標**：已接受的程式碼行數、建議接受率、每日活躍使用者和工作階段
* **貢獻指標**：使用 Claude Code 協助的 PR 和已發佈的程式碼行數，搭配 [GitHub 整合](#enable-contribution-metrics)
* **排行榜**：按 Claude Code 使用情況排名的頂級貢獻者
* **資料匯出**：下載貢獻資料為 CSV 格式以進行自訂報告

如需每位使用者的權杖計數和成本估計，請設定 [OpenTelemetry 匯出](https://code.claude.com/docs/zh-TW/monitoring-usage.md)，或從您組織的分析設定匯出 [支出報告](https://support.claude.com/en/articles/12883420-view-usage-analytics-for-team-and-enterprise-plans)，其中列出每位使用者和每個模型的權杖使用情況和估計使用額度支出。

### 啟用貢獻指標

> [!NOTE]
>
> 貢獻指標處於公開測試版，可在 Claude for Teams 和 Claude for Enterprise 方案上使用。這些指標僅涵蓋您 claude.ai 組織內的使用者。透過 Claude Console API 或第三方整合的使用情況不包括在內。

使用情況和採用資料適用於所有 Claude for Teams 和 Claude for Enterprise 帳戶。貢獻指標需要額外設定以連接您的 GitHub 組織。

您需要擁有者角色才能設定分析設定。GitHub 管理員必須安裝 GitHub 應用程式。

> [!WARNING]
>
> 貢獻指標不適用於啟用 [Zero Data Retention](https://code.claude.com/docs/zh-TW/zero-data-retention.md) 的組織。分析儀表板將僅顯示使用情況指標。

**1. 安裝 GitHub 應用程式**

GitHub 管理員在您組織的 GitHub 帳戶上安裝 Claude GitHub 應用程式，位址為 [github.com/apps/claude](https://github.com/apps/claude)。

**2. 啟用 Claude Code 分析**

Claude 擁有者導覽至 [claude.ai/admin-settings/claude-code](https://claude.ai/admin-settings/claude-code) 並啟用 Claude Code 分析功能。

**3. 啟用 GitHub 分析**

在同一頁面上，啟用「GitHub 分析」切換。

**4. 使用 GitHub 進行驗證**

完成 GitHub 驗證流程並選擇要包括在分析中的 GitHub 組織。

資料通常在啟用後的 24 小時內出現，並進行每日更新。如果沒有資料出現，您可能會看到以下其中一則訊息：

* **「需要 GitHub 應用程式」**：安裝 GitHub 應用程式以檢視貢獻指標
* **「資料處理進行中」**：幾天後再檢查，如果資料未出現，請確認 GitHub 應用程式已安裝

貢獻指標涵蓋託管於 github.com 上的儲存庫。對於 [GitHub Enterprise Server](https://code.claude.com/docs/zh-TW/github-enterprise-server.md) 上的儲存庫，分析儀表板僅顯示使用情況指標。

### 檢視摘要指標

> [!NOTE]
>
> 這些指標刻意保守，代表對 Claude Code 實際影響的低估。只有在高度確信 Claude Code 參與的情況下，才會計算程式碼行和 PR。

儀表板在頂部顯示這些摘要指標：

* **包含 CC 的 PR**：包含至少一行使用 Claude Code 撰寫的程式碼的已合併提取要求的總計數
* **包含 CC 的程式碼行**：所有已合併 PR 中使用 Claude Code 協助撰寫的程式碼總行數。只計算「有效行」：正規化後超過 3 個字元的行，不包括空行和僅包含括號或瑣碎標點符號的行。
* **包含 Claude Code 的 PR (%)**：包含 Claude Code 協助程式碼的所有已合併 PR 的百分比
* **建議接受率**：使用者接受 Claude Code 程式碼編輯建議的次數百分比，包括 Edit、Write 和 NotebookEdit 工具使用情況
* **已接受的程式碼行**：Claude Code 的 Edit 和 Write 工具在已接受的編輯中新增或移除的程式碼總行數。這不包括被拒絕的建議，且之後刪除的行不會減少總數。

### 探索圖表

儀表板包括多個圖表以視覺化一段時間內的趨勢。

#### 追蹤採用

採用圖表顯示每日使用趨勢：

* **使用者**：每日活躍使用者
* **工作階段**：每天的活躍 Claude Code 工作階段數

#### 測量每位使用者的 PR

此圖表顯示一段時間內的個別開發人員活動：

* **每位使用者的 PR**：每天合併的 PR 總數除以每日活躍使用者
* **使用者**：每日活躍使用者

使用此功能可了解隨著 Claude Code 採用增加，個別生產力如何變化。

#### 檢視提取要求細目

提取要求圖表顯示已合併 PR 的每日細目：

* **包含 CC 的 PR**：包含 Claude Code 協助程式碼的提取要求
* **不包含 CC 的 PR**：不包含 Claude Code 協助程式碼的提取要求

切換至**程式碼行**檢視以按程式碼行而非 PR 計數查看相同的細目。

#### 尋找頂級貢獻者

排行榜顯示按貢獻量排名的前 10 位使用者。在以下項目之間切換：

* **提取要求**：顯示每位使用者的 Claude Code 與所有 PR
* **程式碼行**：顯示每位使用者的 Claude Code 與所有行

按一下**匯出所有使用者**以下載所有使用者的完整貢獻資料為 CSV 檔案。匯出包括所有使用者，而不僅是顯示的前 10 位。

### PR 歸因

啟用貢獻指標後，Claude Code 會分析已合併的提取要求，以確定哪些程式碼是使用 Claude Code 協助撰寫的。這是透過將 Claude Code 工作階段活動與每個 PR 中的程式碼進行比對來完成的。

#### 歸因程序

合併提取要求時：

1. 從 PR 差異中提取新增的行
2. 識別在時間視窗內編輯相符檔案的 Claude Code 工作階段
3. 使用多種策略將 PR 行與 Claude Code 輸出進行比對
4. 計算 AI 協助行和總行的指標

在比較之前，行會進行正規化：空白字元會被修剪、多個空格會被摺疊、引號會被標準化，文字會轉換為小寫。

包含 Claude Code 協助行的已合併提取要求在 GitHub 中會標籤為 `claude-code-assisted`。

#### 時間視窗

PR 合併日期前 21 天至後 2 天的工作階段會被考慮用於歸因比對。

#### 排除的檔案

某些檔案會自動從分析中排除，因為它們是自動產生的：

* 鎖定檔案：package-lock.json、yarn.lock、Cargo.lock 及類似檔案
* 產生的程式碼：Protobuf 輸出、建置成品、縮小的檔案
* 建置目錄：dist/、build/、node\_modules/、target/
* 測試夾具：快照、錄製、模擬資料
* 超過 1,000 個字元的行，可能是縮小或產生的

#### 歸因附註

在解釋歸因資料時，請記住這些額外詳細資訊：

* 由開發人員大幅重寫的程式碼（差異超過 20%）不會歸因於 Claude Code
* 不考慮 21 天視窗外的工作階段
* 演算法在執行歸因時不考慮 PR 來源或目的地分支

### 充分利用分析

使用貢獻指標來展示投資報酬率、識別採用模式，並找到可以幫助他人開始使用的團隊成員。

#### 監控採用

追蹤採用圖表和使用者計數以識別：

* 可以分享最佳實踐的活躍使用者
* 整個組織的整體採用趨勢
* 可能表示摩擦或問題的使用情況下降

#### 測量投資報酬率

貢獻指標有助於使用您自己程式碼庫中的資料回答「此工具值得投資嗎？」：

* 隨著採用增加，追蹤一段時間內每位使用者的 PR 變化
* 比較使用和不使用 Claude Code 發佈的 PR 和程式碼行
* 與 [DORA 指標](https://dora.dev/)、衝刺速度或其他工程 KPI 一起使用，以了解採用 Claude Code 帶來的變化

#### 識別超級使用者

排行榜可幫助您找到具有高 Claude Code 採用率的團隊成員，他們可以：

* 與團隊分享提示技巧和工作流程
* 提供有關運作良好的反饋
* 幫助新使用者上手

#### 以程式設計方式存取資料

在 Enterprise 方案上，[Claude Enterprise Analytics API](https://platform.claude.com/docs/en/api/admin/analytics) 會為您的組織返回每位使用者的參與度、使用情況和成本報告，涵蓋所有 Claude 表面，包括 Claude Code。主要擁有者在 [claude.ai/analytics/api-keys](https://claude.ai/analytics/api-keys) 建立具有 `read:analytics` 範圍的金鑰。API 在 Teams 方案上不可用。

若要改為透過 GitHub 查詢貢獻資料，請搜尋標籤為 `claude-code-assisted` 的 PR。

## 訪問 API 客戶的分析

使用 Claude Console 的 API 客戶可以在 [platform.claude.com/claude-code](https://platform.claude.com/claude-code) 訪問分析。您需要 UsageView 權限才能訪問儀表板。開發人員、計費、管理員、所有者和主要所有者角色具有此權限。若要以程式設計方式提取每日每位使用者的指標，請使用 [Claude Code Analytics API](https://platform.claude.com/docs/zh-TW/build-with-claude/claude-code-analytics-api) 搭配管理員 API 金鑰。

> [!NOTE]
>
> GitHub 整合的貢獻指標目前不適用於 API 客戶。Console 儀表板僅顯示使用和支出指標。

Console 儀表板顯示：

* **已接受的程式碼行數**：Claude Code 的 Edit 和 Write 工具在已接受的編輯中新增或移除的程式碼行總數。這不包括被拒絕的建議，之後刪除的行也不會減少總數。
* **建議接受率**：用戶接受代碼編輯工具使用的次數百分比，包括 Edit、Write 和 NotebookEdit 工具。
* **活躍使用者**和**工作階段**：活躍使用者與 Claude Code 工作階段的每日計數。
* **支出**：每日 API 成本（以美元計）。

### 查看團隊洞察

團隊洞察表會針對您在儀表板頂端選取的日期範圍（預設為過去 30 天）顯示以下每位使用者的欄位：

* **成員**：在該範圍內有回報 Claude Code 使用量的使用者和 API 金鑰。API 金鑰使用者按金鑰名稱顯示，OAuth 使用者按電子郵件地址顯示。
* **支出**：每位使用者的 API 成本總計。
* **已接受行數**：每位使用者由 Edit 和 Write 工具在已接受的編輯中新增或移除的行數總計。

> [!NOTE]
>
> Console 儀表板中的支出數字是用於分析目的的估計值。有關實際成本，請參閱[成本頁面](https://platform.claude.com/cost)。

## 相關資源

* [使用 OpenTelemetry 進行監控](https://code.claude.com/docs/zh-TW/monitoring-usage.md)：將實時指標和事件匯出到您的可觀測性堆棧
* [有效管理成本](https://code.claude.com/docs/zh-TW/costs.md)：設置支出限制並優化令牌使用
* [權限](https://code.claude.com/docs/zh-TW/permissions.md)：配置角色和權限

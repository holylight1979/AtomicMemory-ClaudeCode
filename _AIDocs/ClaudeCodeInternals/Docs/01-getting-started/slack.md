<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/slack | lastmod: 2026-11-02 | section: Getting started / Platforms and integrations -->
> 來源：https://code.claude.com/docs/zh-TW/slack（官方 zh-TW，lastmod 2026-11-02）｜分類：Getting started › Platforms and integrations｜EN 摘要：Delegate coding tasks from Slack. This earlier version answers mentions only from Pro, Max, and Ultra accounts in workspaces not connected to Claude Tag.

# Slack 中的 Claude Code

> 從 Slack 委派編碼任務。此較早版本僅在未連接 Claude Tag 的工作區中，回應來自 Pro、Max 和 Ultra 帳戶的提及。

> [!WARNING]
>
> 此較早的 Slack 中的 Claude Code 僅回應來自 Pro、Max 和 Ultra 帳戶的頻道 @提及，且僅限於沒有任何組織將其連接到 [Claude Tag](https://claude.com/product/tag) 的 Slack 工作區。每個工作階段都以個別使用者的帳戶運行。Claude Tag 以 @Claude 身份作為您組織的共享身份運行，具有管理員設定的存取權限。
>
> * **Pro、Max 和 Ultra 方案：** Claude Tag 在個人方案上不可用，因此請在未連接 Claude Tag 的工作區中[設定此版本](#setting-up-claude-code-in-slack)。
> * **Team 和 Enterprise 方案：** 您現有的 Slack 應用程式和 @Claude 控制代碼保持不變。[設定 Claude Tag](https://claude.com/docs/claude-tag/overview) 以建立新工作區；若要移動已使用此版本的工作區，請參閱[從較早的 Slack 中的 Claude 遷移](https://claude.com/docs/claude-tag/admins/migrate-from-earlier)。
> * **收到通知而非回答：** 請查閱 @Claude 回覆的[設定通知](#this-workspace-isnt-set-up-for-claude-tag-yet)或[停用通知](#the-legacy-claude-in-slack-bot-is-retired)。

Slack 中的 Claude Code 將 Claude Code 的強大功能直接帶入您的 Slack 工作區。當您提及 `@Claude` 並附帶編碼任務時，Claude 會自動檢測意圖並在雲端建立 Claude Code 工作階段，讓您無需離開團隊對話即可委派開發工作。

此整合建立在現有的 Claude for Slack 應用程式基礎上，但為編碼相關請求添加了智能路由到雲端的 Claude Code。每個工作階段在您自己的 Claude 帳戶下運行，使用您連接的儲存庫和您的方案限制。

## 使用案例

* **錯誤調查和修復**：要求 Claude 在 Slack 頻道中報告錯誤時立即調查和修復。
* **快速代碼審查和修改**：讓 Claude 根據團隊反饋實現小功能或重構代碼。
* **協作調試**：當團隊討論提供關鍵背景資訊（例如錯誤重現或使用者報告）時，Claude 可以使用該資訊來指導其調試方法。
* **並行任務執行**：在 Slack 中啟動編碼任務，同時繼續其他工作，完成時接收通知。

## 先決條件

在使用 Slack 中的 Claude Code 之前，請確保您具有以下條件：

| 要求 | 詳情 |
| :- | :- |
| Claude 計畫 | Pro、Max 或 Ultra |
| Slack 工作區 | 未被任何組織連接到 [Claude Tag](https://claude.com/docs/claude-tag/overview)。如果 @Claude 回覆[停用通知](#the-legacy-claude-in-slack-bot-is-retired)，表示該工作區已連接 |
| 雲端工作階段 | [雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)已為您的帳戶啟用 |
| GitHub 帳戶 | 在 [claude.ai/code](https://claude.ai/code) 連接，至少有一個存儲庫已驗證 |
| Slack 驗證 | 您的 Slack 帳戶通過 Claude 應用程式連接到您的 Claude 帳戶 |

## 在 Slack 中設定 Claude Code

**1. 在 Slack 中安裝 Claude 應用程式**

工作區管理員必須從 Slack 應用程式市場安裝 Claude 應用程式。訪問 [Slack 應用程式市場](https://slack.com/marketplace/A08SF47R6P4) 並點擊「Add to Slack」以開始安裝程序。

**2. 連接您的 Claude 帳戶**

應用程式安裝後，驗證您的個人 Claude 帳戶：

1. 通過點擊您的應用程式部分中的「Claude」在 Slack 中開啟 Claude 應用程式
2. 開啟應用程式首頁標籤
3. 點擊 **Connect Claude account** 以將您的 Slack 帳戶與您的 Claude 帳戶連接
4. 在您的瀏覽器中完成驗證流程

**3. 設定雲端工作階段**

確保雲端工作階段已為您的帳戶正確設定：

* 訪問 [claude.ai/code](https://claude.ai/code) 並使用您連接到 Slack 的同一帳戶登入
* 如果尚未連接，請連接您的 GitHub 帳戶
* 驗證至少一個您希望 Claude 使用的存儲庫

**4. 選擇您的路由模式**

連接帳戶後，設定 Claude 如何在 Slack 中處理您的訊息。開啟 Slack 中的 Claude 應用程式首頁以找到**路由模式**設定。

| 模式 | 行為 |
| :- | :- |
| **僅代碼** | Claude 將所有 @mentions 路由到 Claude Code 工作階段。最適合使用 Claude in Slack 專門用於開發任務的團隊。 |
| **代碼 + 聊天** | Claude 分析每條訊息並智能地在 Claude Code（用於編碼任務）和 Claude Chat（用於寫作、分析和一般問題）之間路由。最適合希望為所有類型工作提供單一 @Claude 入口點的團隊。 |

> [!NOTE]
>
> 在代碼 + 聊天模式中，如果 Claude 在 Chat 中回答但您想要的是編碼工作階段，請在該回覆上點擊 **Switch to code repo...** 並選擇一個儲存庫。Claude 隨後會改以您的訊息啟動 Claude Code 工作階段。

**5. 將 Claude 新增到頻道**

Claude 在安裝後不會自動新增到任何頻道。要在頻道中使用 Claude，請通過在該頻道中輸入 `/invite @Claude` 來邀請它。Claude 只能在已新增它的頻道中回應 @mentions。

## 工作原理

### 自動檢測

在 Code + Chat 路由模式中，當您在 Slack 頻道或執行緒中提及 @Claude 時，Claude 會自動偵測您的訊息是否為編碼任務。編碼任務會被路由到 Claude Code 雲端工作階段。其他任何內容都會收到常規聊天回覆。在 Code 專用模式中，每個 @mention 都會進入 Claude Code。

您也可以明確告訴 Claude 將請求作為編碼任務處理，即使它沒有自動檢測到。

> [!NOTE]
>
> Slack 中的 Claude Code 僅在頻道（公開或私人）中工作。它在直接訊息 (DM) 中不起作用。

### 背景資訊收集

**來自執行緒**：當您在執行緒中 @mention Claude 時，它會從該執行緒中的所有訊息收集背景資訊以理解完整對話。

**來自頻道**：當直接在頻道中提及時，Claude 會查看最近的頻道訊息以獲取相關背景資訊。

此背景資訊幫助 Claude 理解問題、選擇適當的存儲庫並指導其任務方法。

> [!WARNING]
>
> 當在 Slack 中調用 @Claude 時，Claude 會獲得對對話背景資訊的存取權限以更好地理解您的請求。Claude 可能會遵循背景資訊中其他訊息的指示，因此使用者應確保僅在受信任的 Slack 對話中使用 Claude。

### 工作階段流程

1. **啟動**：您 @mention Claude 並提出編碼請求
2. **檢測**：Claude 分析您的訊息並檢測編碼意圖
3. **工作階段建立**：在 claude.ai/code 上建立新的 Claude Code 工作階段
4. **進度更新**：Claude 在工作進行時向您的 Slack 執行緒發佈狀態更新
5. **完成**：完成後，Claude 會更新其在執行緒中的訊息，附上最終回應和操作按鈕，並向您傳送一則連結至該訊息的直接訊息
6. **審查**：點擊 **View session** 以查看完整逐字稿，或點擊 **Create PR** 以開啟 pull request

## 用戶介面元素

### 訊息操作

* **View session**：在您的瀏覽器中打開完整的 Claude Code 工作階段，您可以在其中查看所有執行的工作、繼續工作階段或提出其他請求。
* **Create PR**：開啟該工作階段分支的 GitHub 比較頁面，您可以在該頁面建立 pull request。此按鈕會在工作階段完成後，出現在 Claude 於工作階段開始時發布的狀態訊息上。
* **Switch to code repo...**：如果 Claude 在 Chat 中回應，但您想要的是編碼工作階段，請點擊此按鈕並選擇一個儲存庫，Claude 便會以您的原始請求啟動 Claude Code 工作階段。

### 存儲庫選擇

Claude 根據您的 Slack 對話中的背景資訊自動選擇儲存庫。如果 Claude 無法判斷您指的是哪個儲存庫，它會請您選擇：點擊 **Select repository** 並從清單中選擇一個。

## 存取和權限

### 用戶級別存取

| 存取類型 | 要求 |
| :- | :- |
| Claude Code 工作階段 | 每個用戶在其自己的 Claude 帳戶下運行工作階段 |
| 使用情況和速率限制 | 工作階段計入個人用戶的計畫限制 |
| 存儲庫存取 | 用戶只能存取他們個人連接的存儲庫 |
| 工作階段歷史記錄 | 工作階段出現在您的 Claude Code 歷史記錄中，位於 claude.ai/code |

### 工作區級別存取

Slack 工作區管理員控制 Claude 應用程式是否可在其工作區中使用：

| 控制 | 描述 |
| :- | :- |
| 應用程式安裝 | 工作區管理員決定是否從 Slack 應用程式市場安裝 Claude 應用程式 |
| Enterprise Grid 分發 | 對於 Enterprise Grid 組織，組織管理員可以控制哪些工作區有權存取 Claude 應用程式 |
| 應用程式移除 | 從工作區移除應用程式會立即撤銷該工作區中所有用戶的存取權限 |

### 基於頻道的存取控制

安裝應用程式不會將 Claude 添加到任何頻道。Claude 只在已添加它的頻道中回應 @mentions；使用 `/invite @Claude` 邀請它。它在公開和私人頻道中都可以工作。管理員可以通過管理 Claude 被邀請到哪些頻道以及誰有權存取這些頻道來控制誰使用 Claude Code。這在工作區級別權限之外增加了一層存取控制。

## 在何處可以存取什麼

**在 Slack 中**：您將看到狀態更新、完成摘要和操作按鈕。完整記錄被保留並始終可存取。

**在 claude.ai/code**：完整的 Claude Code 工作階段，包含完整對話歷史記錄、所有代碼更改和檔案操作。工作階段保存在您的 Claude Code 歷史記錄中，位於 [claude.ai/code](https://claude.ai/code)，您可以在其中繼續過去的工作階段、參考它們或建立拉取請求。

對於 Enterprise 和 Team 帳戶，從 Slack 中的 Claude 建立的工作階段會自動對組織可見。有關更多詳情，請參閱 [雲端工作階段共享](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#share-sessions)。

## 最佳實踐

### 撰寫有效的請求

* **具體明確**：在相關時提供檔案名稱、函式名稱或錯誤訊息。
* **提供背景資訊**：如果從對話中不清楚，請提及儲存庫或專案。
* **定義成功**：解釋「完成」的樣子。Claude 應該撰寫測試嗎？更新文件？建立 PR？
* **使用執行緒**：在討論錯誤或功能時在執行緒中回覆，以便 Claude 可以收集完整的背景資訊。

### 何時使用 Slack 與網頁

**使用 Slack 的時機**：背景資訊已存在於 Slack 討論中、您想非同步啟動任務，或您正在與需要可見性的隊友協作。

**直接使用網頁的時機**：您需要上傳檔案、想要在開發期間進行即時互動，或正在處理更長、更複雜的任務。

## 故障排除

### "This workspace isn't set up for Claude Tag yet"

當以下兩項條件皆成立時，@Claude 會在討論串中回覆此通知，而非提供答案：

* 沒有任何組織已將您的 Slack 工作區連接到 [Claude Tag](https://claude.com/docs/claude-tag/overview)。
* 您在 Slack 中連結的 Claude 帳戶不是 Pro、Max 或 Ultra 方案。

Claude Tag 適用於 Team 和 Enterprise 方案。若要連接工作區，請從通知中提到的 `@Claude connect` 命令開始，然後依照[設定 Claude Tag](https://claude.com/docs/claude-tag/overview) 進行。

### "The legacy Claude in Slack bot is retired"

此通知的開頭為 `The legacy Claude in Slack bot is retired effective October 5, 2026 and no longer responds in channels.`。您的 Slack 工作區已連接到某個 Claude 組織，但在該組織的 Claude Tag 設定中，頻道、工作區或組織預設值仍選擇了舊版本。此通知與您自己的方案無關，因此 Pro、Max 和 Ultra 帳戶也會收到。

如果您是該組織的擁有者，請開啟 [Claude 管理設定](https://claude.ai/admin-settings/claude-tag)，並為該頻道開啟 Claude Tag。若要修正所有繼承此設定的頻道，請改為在工作區或組織預設值上變更設定。如需完整的遷移說明，請參閱[從舊版 Claude in Slack 遷移](https://claude.com/docs/claude-tag/admins/migrate-from-earlier)。如果您不是擁有者，請將此項目傳送給擁有者。

### "Claude Code 未為您的帳戶啟用"

此錯誤表示您的 Claude 帳戶尚未有雲端環境。使用您連接到 Slack 的同一帳戶登入 [claude.ai/code](https://claude.ai/code) 一次，並完成[網路快速入門](https://code.claude.com/docs/zh-TW/web-quickstart.md#connect-github)，這會建立您的預設雲端環境或要求您建立它。錯誤會在您下次提及時清除。每位使用者必須個別執行此操作。

### 工作階段未啟動

1. 驗證您的 Claude 帳戶已在 Claude 應用程式首頁中連接
2. 檢查您的帳戶是否已啟用雲端工作階段
3. 確保您至少有一個 GitHub 存儲庫連接到 Claude Code

### 來自 Claude Tag 頻道的工作階段無法啟動

此項目適用於使用 [Claude Tag](https://claude.com/docs/claude-tag/overview) 的工作區。如果您在 [claude.ai/code](https://claude.ai/code) 建立了頻道的雲端環境，它屬於您的個人帳戶，Claude 無法在個人環境中啟動頻道工作階段。Claude Code 會立即使工作階段失敗，重試也無法幫助。

如果您是擁有者且環境是您自己的，請從環境選擇器[與組織共享](https://code.claude.com/docs/zh-TW/cloud-environments.md#organization-shared-environments)。否則，擁有者應從[管理設定](https://claude.ai/admin-settings)中的**雲端環境**頁面將其重新建立為組織共享環境。

您可以透過兩種方式應用它：

* 在 [claude.ai/admin-settings/claude-code](https://claude.ai/admin-settings/claude-code) 將其設定為組織預設值。
* [在 Claude Tag 管理設定中的頻道上設定它](https://claude.com/docs/claude-tag/admins/troubleshooting#channel-sessions-use-the-wrong-environment-or-can%E2%80%99t-find-one)。

如果您不是擁有者，請將此項目傳送給擁有者。

### 存儲庫未顯示

1. 在 [claude.ai/code](https://claude.ai/code) 連接存儲庫
2. 驗證您對該存儲庫的 GitHub 權限
3. 嘗試斷開並重新連接您的 GitHub 帳戶

### 選擇了錯誤的存儲庫

在您的請求中包括儲存庫名稱以獲得更準確的選擇。

### 驗證錯誤

1. 在應用程式首頁中斷開並重新連接您的 Claude 帳戶
2. 確保您在瀏覽器中登入正確的 Claude 帳戶

## 目前限制

* **僅 GitHub**：存儲庫必須在 GitHub 上。
* **一次一個拉取請求**：每個工作階段可以建立一個拉取請求。
* **需要雲端工作階段存取**：使用者需要存取[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)。

## 相關資源

> [card] [雲端上的 Claude Code](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)
>
> 深入瞭解雲端工作階段

> [card] [Claude for Slack](https://claude.com/claude-and-slack)
>
> Claude for Slack 的一般文件

> [card] [Claude Tag](https://claude.com/docs/claude-tag/overview)
>
> 在 Slack 中由組織管理的 @Claude，具有管理員設定的存取權限

> [card] [Slack App Marketplace](https://slack.com/marketplace/A08SF47R6P4)
>
> 從 Slack Marketplace 安裝 Claude 應用程式

> [card] [Claude 說明中心](https://support.claude.com)
>
> 取得額外支援

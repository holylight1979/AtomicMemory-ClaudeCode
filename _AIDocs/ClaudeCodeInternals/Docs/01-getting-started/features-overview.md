<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/features-overview | lastmod: 2026-10-26 | section: Getting started / Core concepts -->
> 來源：https://code.claude.com/docs/zh-TW/features-overview（官方 zh-TW，lastmod 2026-10-26）｜分類：Getting started › Core concepts｜EN 摘要：Understand when to use CLAUDE.md, Skills, subagents, hooks, MCP, and plugins.

# 擴展 Claude Code

> 了解何時使用 CLAUDE.md、Skills、subagents、hooks、MCP 和 plugins。

Claude Code 結合了一個能夠推理您程式碼的模型與[內建工具](https://code.claude.com/docs/zh-TW/how-claude-code-works.md#tools)，用於檔案操作、搜尋、執行和網路存取。內建工具涵蓋了大多數編碼任務。本指南涵蓋擴展層：您添加的功能，用於自訂 Claude 的知識、將其連接到外部服務，以及自動化工作流程。

> [!NOTE]
>
> 有關核心代理迴圈如何運作的資訊，請參閱[Claude Code 如何運作](https://code.claude.com/docs/zh-TW/how-claude-code-works.md)。

**初次使用 Claude Code？** 從[CLAUDE.md](https://code.claude.com/docs/zh-TW/memory.md)開始了解專案約定，然後根據特定觸發器添加其他擴展[如下所示](#build-your-setup-over-time)。

## 概述

擴展插入代理迴圈的不同部分：

* **[CLAUDE.md](https://code.claude.com/docs/zh-TW/memory.md)** 添加 Claude 在每個會話中看到的持久上下文
* **[Output styles](https://code.claude.com/docs/zh-TW/output-styles.md)** 為會話中的每個回應設定 Claude 的角色、語調和回應格式
* **[Skills](https://code.claude.com/docs/zh-TW/skills.md)** 添加可重複使用的知識和可調用的工作流程
* **[Code intelligence](https://code.claude.com/docs/zh-TW/tools-reference.md#lsp-tool-behavior)** 將 Claude 連接到語言伺服器以進行符號級導航和即時類型錯誤
* **[MCP](https://code.claude.com/docs/zh-TW/mcp.md)** 將 Claude 連接到外部服務和工具
* **[Subagents](https://code.claude.com/docs/zh-TW/sub-agents.md)** 在隔離的上下文中運行自己的迴圈，返回摘要
* **[Dynamic workflows](https://code.claude.com/docs/zh-TW/workflows.md)** 從 Claude 編寫的指令碼運行許多 subagents，返回一個結果
* **[Cross-session messaging](https://code.claude.com/docs/zh-TW/cross-session-messaging.md)** 讓 Claude 將訊息從您的一個會話傳遞到另一個會話
* **[Hooks](https://code.claude.com/docs/zh-TW/hooks-guide.md)** 在 Claude Code 達到生命週期事件時運行您的指令碼、HTTP 請求、MCP 工具呼叫、提示或 subagent
* **[Plugins](https://code.claude.com/docs/zh-TW/plugins/overview.md)** 和 **[marketplaces](https://code.claude.com/docs/zh-TW/plugins/overview.md)** 打包和分發這些功能

[Skills](https://code.claude.com/docs/zh-TW/skills.md) 是最靈活的擴展。Skill 是一個包含知識、工作流程或指令的 markdown 檔案。您可以使用像 `/deploy` 這樣的命令調用 skills，或者 Claude 可以在相關時自動載入它們。Skills 可以在您目前的對話中運行，或通過 subagents 在隔離的上下文中運行。

## 依目標選擇功能

各項功能涵蓋範圍廣泛，從 Claude 每個工作階段都會看到的常駐上下文，到您或 Claude 可以叫用的隨選功能，再到在特定事件發生時執行的背景自動化。下表列出可用的功能以及各自適用的時機。

| 功能 | 用途 | 使用時機 | 範例 |
| - | - | - | - |
| **CLAUDE.md** | 每次對話都會載入的持久上下文 | 專案慣例、「一律執行 X」的規則 | 「使用 pnpm，不要用 npm。提交前先執行測試。」 |
| **[輸出風格](https://code.claude.com/docs/zh-TW/output-styles.md)** | 為整個工作階段設定 Claude 角色、語氣與回應格式的指令 | 希望每個回應都採用的語氣、長度或格式，或讓 Claude 以軟體工程師以外的身分工作 | 內建的 Concise 風格可讓回應更簡短；自訂風格可讓每個問題都先以圖表回答 |
| **Skill** | Claude 可使用的指令、知識與工作流程 | 可重複使用的內容、參考文件、可重複執行的任務 | `/deploy` 會執行您的部署檢查清單；包含端點模式的 API 文件 skill |
| **Subagent** | 回傳摘要結果的隔離執行上下文 | 上下文隔離、平行任務、專門化的工作者 | 讀取大量檔案但只回傳關鍵發現的研究任務 |
| **[動態工作流程](https://code.claude.com/docs/zh-TW/workflows.md)** | 由 Claude 撰寫、在背景執行多個 subagent 的指令碼 | 超出少數幾個 subagent 能處理的工作，或希望交叉驗證的發現 | 稽核整個程式碼庫，並由第二組 agent 驗證每項發現 |
| **[跨工作階段傳訊](https://code.claude.com/docs/zh-TW/cross-session-messaging.md)** | Claude 將訊息從您的一個工作階段傳遞到另一個工作階段 | 您自行執行、在任務進行中需要彼此發現的工作階段 | 一個工作階段警告另一個工作階段，它所做的變更會破壞對方正在建構的內容 |
| **[程式碼智慧](https://code.claude.com/docs/zh-TW/tools-reference.md#lsp-tool-behavior)** | 語言伺服器導覽與診斷 | 型別語言、grep 速度慢或不精確的大型程式碼庫 | 直接跳到符號的定義，而不是讀取整個檔案 |
| **MCP** | 連接外部服務 | 外部資料或動作 | 查詢您的資料庫、發布訊息到 Slack、控制瀏覽器 |
| **Hook** | 由事件觸發的指令碼、HTTP 請求、MCP 工具呼叫、提示詞或 subagent | 必須在每個相符事件上執行的自動化 | 每次編輯檔案後執行 ESLint |
| **[Artifact](https://code.claude.com/docs/zh-TW/artifacts.md)** | 將工作階段輸出發布為私人的互動式網頁 | 希望以視覺方式檢視或分享、而非以終端機文字呈現的輸出 | 隨著 Claude 調查而更新的事件時間軸 |

\*\*[外掛](https://code.claude.com/docs/zh-TW/plugins/overview.md)\*\*是封裝層。外掛會將 skill、hook、subagent 與 MCP 伺服器組合成單一可安裝的單元。外掛 skill 具有命名空間（例如 `/my-plugin:review`），因此多個外掛可以並存。當您想在多個儲存庫中重複使用相同的設定，或透過 **[市集](https://code.claude.com/docs/zh-TW/plugins/overview.md)** 散布給其他人時，請使用外掛。

### 逐步建立您的設定

您不需要一開始就設定好所有內容。每項功能都有可辨識的觸發時機，大多數團隊大致依照以下順序加入：

| 觸發時機 | 加入 |
| :- | :- |
| Claude 兩次弄錯某個慣例或命令 | 將其加入 [CLAUDE.md](https://code.claude.com/docs/zh-TW/memory.md) |
| 您一再要求 Claude 更簡短、多加解釋，或以相同格式回答 | 設定[輸出風格](https://code.claude.com/docs/zh-TW/output-styles.md) |
| 您一再輸入相同的提示詞來開始某項任務 | 將其儲存為使用者可叫用的 [skill](https://code.claude.com/docs/zh-TW/skills.md) |
| 您第三次將相同的操作手冊或多步驟程序貼到聊天中 | 將其整理為 [skill](https://code.claude.com/docs/zh-TW/skills.md) |
| 您一直從 Claude 看不到的瀏覽器分頁複製資料 | 將該系統連接為 [MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md) |
| Claude 讀取大量檔案來找出符號的定義或使用位置 | 為您的語言安裝[程式碼智慧外掛](https://code.claude.com/docs/zh-TW/plugins/code-intelligence.md) |
| 某個附帶任務以您之後不會再參考的輸出塞滿對話 | 透過 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 處理 |
| 您希望某件事每次都自動發生而不需要要求 | 撰寫 [hook](https://code.claude.com/docs/zh-TW/hooks-guide.md) |
| 第二個儲存庫需要相同的設定 | 將其封裝為[外掛](https://code.claude.com/docs/zh-TW/plugins/overview.md) |

同樣的觸發時機也能告訴您何時該更新現有的設定。反覆出現的錯誤或一再出現的審查意見，應該編輯 CLAUDE.md，而不是在聊天中進行一次性的修正。您一直手動調整的工作流程，代表這個 skill 需要再修訂一次。

### 比較相似的功能

有些功能看起來可能很相似。如需更深入了解如何在它們之間做選擇，請參閱部落格上的 [Steering Claude Code: when to use CLAUDE.md, skills, hooks, and subagents](https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more)。以下說明如何區分它們。

> [tab] Skill 與 Subagent
>
> Skill 與 subagent 解決的是不同的問題：
>
> * **Skill** 是可以載入到任何上下文中的可重複使用內容
> * **Subagent** 是與主要對話分開執行的隔離工作者
>
> | 面向 | Skill | Subagent |
> | - | - | - |
> | **是什麼** | 可重複使用的指令、知識或工作流程 | 擁有自己上下文的隔離工作者 |
> | **主要優點** | 在不同上下文之間共用內容 | 上下文隔離。工作分開進行，只回傳摘要 |
> | **[上下文視窗](https://code.claude.com/docs/zh-TW/context-window.md)影響** | 增加到您的主要視窗 | 使用獨立的視窗，擁有自己的輸入與輸出 token |
> | **最適合** | 參考資料、可叫用的工作流程 | 需要讀取大量檔案的任務、平行工作、專門化的工作者 |
>
> **Skill 可以是參考型或動作型。** 參考型 skill 提供 Claude 在整個工作階段中使用的知識（例如您的 API 風格指南）。動作型 skill 則告訴 Claude 執行特定的事情（例如執行部署工作流程的 `/deploy`）。
>
> **使用 subagent** 的時機是需要上下文隔離，或上下文視窗即將填滿時。Subagent 可能會讀取數十個檔案或執行大量搜尋，但主要對話只會收到摘要。由於 subagent 的工作不會消耗主要上下文，當您不需要讓中間過程保持可見時，這也很有用。自訂 subagent 可以擁有自己的指令，並可預先載入 skill。
>
> **兩者可以結合。** Subagent 可以預先載入特定的 skill（`skills:` 欄位）。Skill 可以使用 `context: fork` 在隔離的上下文中執行。詳情請參閱 [Skill](https://code.claude.com/docs/zh-TW/skills.md)。

> [tab] CLAUDE.md 與 Skill
>
> 兩者都儲存指令，但載入方式不同，用途也不同。
>
> | 面向 | CLAUDE.md | Skill |
> | - | - | - |
> | **載入** | 每個工作階段自動載入 | 隨選載入 |
> | **可包含檔案** | 可以，使用 `@path` 匯入 | 可以，使用 `@path` 匯入 |
> | **可觸發工作流程** | 否 | 可以，使用 `/<name>` |
> | **最適合** | 「一律執行 X」的規則 | 參考資料、可叫用的工作流程 |
>
> **放在 CLAUDE.md**：如果 Claude 應該隨時知道這些內容，例如程式碼慣例、建置命令、專案結構、「絕不執行 X」的規則。
>
> **放在 skill**：如果是 Claude 有時才需要的參考資料（API 文件、風格指南），或是您透過 `/<name>` 觸發的工作流程（部署、審查、發布）。
>
> **經驗法則：** 讓 CLAUDE.md 保持在 200 行以內。如果內容持續增加，請將參考內容移至 skill，或拆分為 [`.claude/rules/`](https://code.claude.com/docs/zh-TW/memory#organize-rules-with-claude/rules/) 檔案。

> [tab] CLAUDE.md 與輸出風格
>
> 兩者都為 Claude 提供常駐指令。CLAUDE.md 承載 Claude 應該知道的內容，而輸出風格則設定 Claude 的回應方式。
>
> | 面向 | CLAUDE.md | 輸出風格 |
> | - | - | - |
> | **內容** | 關於專案的事實與規則 | 角色、語氣與回應格式 |
> | **切換** | 一律載入 | 一次只有一個生效；可隨時[切換風格](https://code.claude.com/docs/zh-TW/output-styles.md#change-your-output-style) |
> | **最適合** | 建置命令、慣例、「絕不執行 X」的規則 | 較簡短的回應、搭配程式碼的說明、非工程類角色 |
>
> **放在 CLAUDE.md**：如果無論使用哪種風格，這些內容對專案都成立，例如程式碼慣例、建置命令、專案結構。
>
> **使用輸出風格**：如果內容與回應本身有關，且您之後可能想將其關閉，例如長度、格式、Claude 解釋的詳細程度，或是寫作助理等不同的角色。Claude Code 包含[內建風格](https://code.claude.com/docs/zh-TW/output-styles.md#built-in-output-styles)，您也可以撰寫自己的風格。
>
> **兩者可以結合。** 無論您選擇哪種風格，CLAUDE.md 都會保持載入。Claude 會將兩者都視為指令來遵循，因此兩者都不具強制性。對於每次都必須發生的事情，請使用 [hook](https://code.claude.com/docs/zh-TW/hooks-guide.md)。

> [tab] CLAUDE.md、規則與 Skill
>
> 三者都儲存指令，但載入方式不同：
>
> | 面向 | CLAUDE.md | `.claude/rules/` | Skill |
> | - | - | - | - |
> | **載入** | 每個工作階段 | 每個工作階段，或開啟相符檔案時 | 隨選，在叫用或相關時載入 |
> | **範圍** | 整個專案 | 可限定於特定檔案路徑 | 特定任務 |
> | **最適合** | 核心慣例與建置命令 | 特定語言或特定目錄的準則 | 參考資料、可重複執行的工作流程 |
>
> **使用 CLAUDE.md** 存放每個工作階段都需要的指令：建置命令、測試慣例、專案架構。
>
> **使用規則** 讓 CLAUDE.md 保持聚焦。具有 [`paths` frontmatter](https://code.claude.com/docs/zh-TW/memory#path-specific-rules) 的規則只會在 Claude 處理相符檔案時載入，藉此節省上下文。
>
> **使用 skill** 存放 Claude 有時才需要的內容，例如 API 文件或您透過 `/<name>` 觸發的部署檢查清單。

> [tab] Subagent 與動態工作流程
>
> 兩者都在主要對話之外執行工作。使用 subagent 時，由 Claude 逐回合決定接下來要執行什麼。在工作流程中，則由指令碼決定：
>
> * **Subagent** 是 Claude 產生的工作者，每個都會將摘要回傳給產生它的對話
> * **[動態工作流程](https://code.claude.com/docs/zh-TW/workflows.md)** 是由 Claude 撰寫的指令碼，會在背景執行多個 subagent 並回傳單一結果
>
> **使用 subagent** 的時機是需要快速、專注的工作者時：研究某個問題、驗證某項主張、審查某個檔案。Subagent 完成工作後回傳摘要，讓您的主要對話保持整潔。Claude 在產生時為其[命名](https://code.claude.com/docs/zh-TW/sub-agents.md#subagent-names)的 subagent 也可以[彼此傳訊](https://code.claude.com/docs/zh-TW/sub-agents.md#what-loads-at-startup)。
>
> **使用動態工作流程** 的時機是某項工作[超出少數幾個 subagent 能處理的範圍](https://code.claude.com/docs/zh-TW/workflows.md#when-to-use-a-workflow)，或您希望在看到發現之前先交叉驗證時，例如整個程式碼庫的稽核、大型遷移，或從多個角度起草的計畫。若要啟動工作流程，請[在提示詞中要求使用工作流程](https://code.claude.com/docs/zh-TW/workflows.md#ask-for-a-workflow-in-your-prompt)。
>
> **若要將某個工作階段的發現傳遞給另一個工作階段**，請要求第一個工作階段的 Claude 傳送。Claude 會透過[跨工作階段傳訊](https://code.claude.com/docs/zh-TW/cross-session-messaging.md)傳遞。[平行執行 agent](https://code.claude.com/docs/zh-TW/agents.md) 比較了同時執行多個 Claude 的其他方式，包括您交付出去、之後再回來查看的工作階段。

> [tab] MCP 與 Skill
>
> MCP 將 Claude 連接到外部服務。Skill 則擴充 Claude 所知道的內容，包括如何有效使用這些服務。
>
> | 面向 | MCP | Skill |
> | - | - | - |
> | **是什麼** | 用於連接外部服務的協定 | 知識、工作流程與參考資料 |
> | **提供** | 工具與資料存取 | 知識、工作流程、參考資料 |
> | **範例** | Slack 整合、資料庫查詢、瀏覽器控制 | 程式碼審查檢查清單、部署工作流程、API 風格指南 |
>
> 兩者解決不同的問題，且能良好地搭配運作：
>
> **MCP** 為 Claude 提供針對外部系統專門打造的工具，連線與身分驗證則由伺服器處理。
>
> **Skill** 為 Claude 提供如何有效使用這些工具的知識，以及您可以透過 `/<name>` 觸發的工作流程。Skill 可能包含您團隊的資料庫 schema 與查詢模式，或是包含團隊訊息格式規則的 `/post-to-slack` 工作流程。

> [tab] Hook 與 Skill
>
> Claude Code 會在生命週期事件發生時執行 hook；而 skill 則是載入到上下文中供 Claude 套用。
>
> | 面向 | Hook | Skill |
> | - | - | - |
> | **執行內容** | shell 命令、HTTP 請求、MCP 工具呼叫、LLM 提示詞或 subagent | Claude 閱讀並遵循的指令 |
> | **觸發方式** | [生命週期事件](https://code.claude.com/docs/zh-TW/hooks.md#hook-events)，例如 `PostToolUse` 或 `SessionStart` | 您輸入 `/<name>`，或 Claude 判斷描述與您的任務相符 |
> | **確定性** | 在其事件發生時觸發，無需 Claude 決定 | Claude 解讀指令；結果可能有所不同 |
> | **上下文成本** | 除非 hook 回傳輸出，否則為零 | 描述在每個工作階段載入；使用時載入完整內容 |
> | **最適合** | 編輯後執行 lint、封鎖不安全的命令、記錄、通知 | 需要推理的工作流程、參考資料、多步驟任務 |
>
> **使用 hook** 的時機是動作每次都必須以相同方式發生，且不需要 Claude 思考時。例如：儲存時格式化、拒絕 `rm -rf /`、在工作階段結束時發布 Slack 訊息。
>
> **使用 skill** 的時機是應由 Claude 決定如何套用步驟，或內容是知識而非指令碼時。例如：`/release` 檢查清單、您的 API 風格指南、除錯操作手冊。
>
> **將防護措施放在 hook 中。** 在 CLAUDE.md 或 skill 中寫下「絕不編輯 `.env`」這類指令只是請求，而非保證。封鎖該編輯的 `PreToolUse` hook 才是強制執行。如果某條規則每次都必須成立，請將其設為 hook，而不是提示詞指令。
>
> **Hook 輸出會進入上下文。** 執行 linter 的 `PostToolUse` hook 會將結果以文字形式回饋給 Claude 閱讀；`/fix-lint` skill 則告訴 Claude 如何解決這些問題。

### 了解功能如何分層

功能可以在多個層級定義：整個使用者、個別專案、透過外掛，或透過受管理的政策。您也可以在子目錄中巢狀放置 CLAUDE.md 檔案，或將 skill 放在 monorepo 的特定套件中。當同一功能存在於多個層級時，分層方式如下：

* **CLAUDE.md 檔案**是累加的：所有層級會同時將內容提供給 Claude 的上下文。來自工作目錄及其上層目錄的檔案會在啟動時載入；子目錄的檔案則在您於其中工作時載入。當指令互相衝突時，Claude 會自行判斷如何調和。請參閱 [CLAUDE.md 檔案的載入方式](https://code.claude.com/docs/zh-TW/memory.md#how-claude-md-files-load)。
* **Skill 與 subagent** 依名稱覆寫：當同一名稱存在於多個層級時，會依優先順序由其中一個定義勝出（skill 為 managed > user > project；subagent 為 managed > CLI 旗標 > project > user > plugin）。外掛 skill 具有[命名空間](https://code.claude.com/docs/zh-TW/plugins/components.md#skills)以避免衝突。請參閱 [skill 探索](https://code.claude.com/docs/zh-TW/skills.md#resolve-skills-that-share-a-name)與 [subagent 範圍](https://code.claude.com/docs/zh-TW/sub-agents.md#choose-the-subagent-scope)。
* **MCP 伺服器**依名稱覆寫：local > project > user。請參閱 [MCP 範圍](https://code.claude.com/docs/zh-TW/mcp.md#scope-hierarchy-and-precedence)。
* **Hook** 會合併：所有已註冊的 hook 都會在其相符事件發生時觸發，無論來源為何。請參閱 [hook](https://code.claude.com/docs/zh-TW/hooks.md)。

### 結合功能

每種擴充功能解決不同的問題：CLAUDE.md 處理常駐上下文，skill 處理隨選的知識與工作流程，MCP 處理外部連線，subagent 處理隔離，hook 則處理自動化。實際的設定會依您的工作流程將它們結合使用。

例如，您可以使用 CLAUDE.md 存放專案慣例、使用 skill 處理部署工作流程、使用 MCP 連接資料庫，並使用 hook 在每次編輯後執行 lint。每項功能都處理自己最擅長的部分。

| 模式 | 運作方式 | 範例 |
| - | - | - |
| **Skill + MCP** | MCP 提供連線；skill 教導 Claude 如何善加運用 | MCP 連接到您的資料庫，skill 記錄您的 schema 與查詢模式 |
| **Skill + Subagent** | Skill 產生 subagent 進行平行工作 | `/audit` skill 啟動安全性、效能與風格 subagent，各自在隔離的上下文中工作 |
| **CLAUDE.md + Skill** | CLAUDE.md 存放常駐規則；skill 存放隨選載入的參考資料 | CLAUDE.md 寫著「遵循我們的 API 慣例」，skill 則包含完整的 API 風格指南 |
| **Hook + MCP** | Hook 透過 MCP 觸發外部動作 | 編輯後 hook 在 Claude 修改關鍵檔案時傳送 Slack 通知 |

## 了解上下文成本

您添加的每個功能都消耗 Claude 的一些上下文。太多可能會填滿您的上下文視窗，但它也可能添加噪聲，使 Claude 效率降低；skills 可能無法正確觸發，或 Claude 可能會失去對您的約定的追蹤。了解這些權衡有助於您構建有效的設置。有關這些功能如何在運行會話中結合的互動式視圖，請參閱[探索上下文視窗](https://code.claude.com/docs/zh-TW/context-window.md)。

### 按功能的上下文成本

每個功能都有不同的載入策略和上下文成本：

| 功能 | 何時載入 | 什麼載入 | 上下文成本 |
| - | - | - | - |
| **CLAUDE.md** | 工作階段開始 | 在工作階段開始時載入的每個檔案的完整內容 | 每個請求 |
| **Output styles** | 會話開始，以及當您切換風格時 | 活躍風格的完整指令；預設風格無任何內容 | 每個請求 |
| **Skills** | 會話開始 + 使用時 | 啟動時的描述，使用時的完整內容 | 低（每個請求的描述）\* |
| **MCP 伺服器** | 會話開始 | 工具名稱；完整架構按需 | 低，直到使用工具 |
| **Code intelligence** | 檔案編輯後和按需 | 編輯後的診斷；查詢時的符號位置 | 低；減少其他地方的檔案讀取 |
| **Subagents** | 生成時 | 具有指定 skills 的新鮮上下文，或用於[分支](https://code.claude.com/docs/zh-TW/sub-agents.md#fork-the-current-conversation)的父對話 | 與主會話隔離 |
| **Hooks** | 觸發時 | 無（外部運行） | 零，除非 hook 返回額外上下文 |

\*在 skill 的 frontmatter 中設定 [`disable-model-invocation: true`](https://code.claude.com/docs/zh-TW/skills#control-who-invokes-a-skill)，以將其描述排除在 Claude 的上下文之外。對於您未編寫的 skill，在設定中設定 [`skillOverrides`](https://code.claude.com/docs/zh-TW/skills#override-skill-visibility-from-settings) 以執行相同操作，而無需編輯其檔案。

### 了解功能如何載入

每個功能在您的會話中的不同點載入。下面的選項卡說明每個功能何時載入以及什麼進入上下文。

![上下文載入：CLAUDE.md 在會話開始時載入並保留在每個請求中。MCP 工具名稱在啟動時載入，完整架構延遲到使用。Skills 在啟動時載入描述，在調用時載入完整內容。Subagents 獲得隔離的上下文。Hooks 外部運行。](https://mintcdn.com/claude-code/ikqp3_70mqIahteV/images/context-loading.svg?fit=max\&auto=format\&n=ikqp3_70mqIahteV\&q=85\&s=aab139e750494a237ae2e0c8f9139b0a)

> [tab] CLAUDE.md
>
> **何時：** 會話開始
>
> **什麼載入：** 在工作階段開始時載入的每個 CLAUDE.md 檔案的完整內容（受管理、使用者和專案級別）。
>
> **繼承：** Claude 從您的工作目錄讀取 CLAUDE.md 檔案直到根目錄，並在存取子目錄中的檔案時發現其中嵌套的 CLAUDE.md。有關詳細資訊，請參閱 [CLAUDE.md 檔案如何載入](https://code.claude.com/docs/zh-TW/memory.md#how-claude-md-files-load)。如果嵌套的 CLAUDE.md 超過其[單一檔案大小限制](https://code.claude.com/docs/zh-TW/memory.md#claude-ignores-the-end-of-my-subdirectory-claude-md)，Claude 只會收到該檔案的開頭部分。
>
> > [!TIP]
> >
> > 保持 CLAUDE.md 在 200 行以下。將參考資料移動到 skills，它們按需載入。若要取得[已簽入 CLAUDE.md 的修剪建議](https://code.claude.com/docs/zh-TW/memory.md#my-claude-md-is-too-large)，請執行 `/doctor`。

> [tab] Skills
>
> Skills 是 Claude 工具包中的額外功能。它們可以是參考資料（如 API 風格指南）或可調用的工作流程，您可以使用 `/<name>` 觸發（如 `/deploy`）。Claude Code 附帶[捆綁的 skills](https://code.claude.com/docs/zh-TW/commands.md)，如 `/code-review`、`/batch` 和 `/debug`，開箱即用。您也可以創建自己的。
>
> **何時：** 取決於 skill 的配置。預設情況下，描述在會話開始時載入，完整內容在使用時載入。對於僅使用者 skills（`disable-model-invocation: true`），在您調用它們之前不會載入任何內容。
>
> **什麼載入：** 對於模型可調用的 skills，Claude 在每個請求中看到名稱和描述。當您使用 `/<name>` 調用 skill 或 Claude 自動載入它時，完整內容載入到您的對話中。
>
> **Claude 如何選擇 skills：** Claude 將您的任務與 skill 描述相匹配，以決定哪些相關。如果描述模糊或重疊，Claude 可能載入錯誤的 skill 或錯過會有幫助的。要告訴 Claude 使用特定 skill，請使用 `/<name>` 調用它。
>
> **上下文成本：** 低，直到使用。僅使用者 skills 在調用前成本為零。
>
> **在 subagents 中：** subagent 的 `skills` 欄位中列出的 skills，其完整內容會[在啟動時載入其上下文](https://code.claude.com/docs/zh-TW/sub-agents.md#preload-skills-into-subagents)，而非按需載入。Subagents 仍然可以透過 Skill 工具發現和調用未列出的專案、使用者和外掛 skills。
>
> > [!TIP]
> >
> > 對具有副作用的 skills 使用 `disable-model-invocation: true`。這節省上下文並確保它們只在您指名時執行。

> [tab] MCP 伺服器
>
> **何時：** 工作階段開始。
>
> **什麼載入：** 來自連接伺服器的工具名稱和伺服器指令。完整 JSON 架構保持延遲，直到 Claude 需要特定工具。
>
> **上下文成本：** [工具搜尋](https://code.claude.com/docs/zh-TW/mcp.md#scale-with-mcp-tool-search)預設啟用，因此閒置 MCP 工具消耗最少上下文。
>
> > [!TIP]
> >
> > 執行 `/mcp` 以查看每個伺服器的連接狀態。執行 `/context all` 以查看每個已載入 MCP 工具使用多少令牌。Claude Code [自動重新連接到遠程伺服器](https://code.claude.com/docs/zh-TW/mcp.md#automatic-reconnection)（如果它們斷開連接），您可以斷開您未主動使用的伺服器。

> [tab] Code intelligence
>
> **何時：** 檔案編輯後，以及當 Claude 導航程式碼時按需。
>
> **什麼載入：** 每次檔案編輯後的類型錯誤和警告。當 Claude 查詢符號時的定義、參考和類型資訊。
>
> **上下文成本：** 低。符號查詢通常會取代廣泛的檔案讀取，因此淨上下文使用可能會下降。
>
> > [!TIP]
> >
> > LSP 工具在您為您的語言安裝[程式碼智能 plugin](https://code.claude.com/docs/zh-TW/plugins/code-intelligence.md)之前處於非活動狀態。

> [tab] Subagents
>
> **何時：** 按需，當您或 Claude 為任務生成一個時。
>
> **什麼載入：** 新鮮、隔離的上下文，包含：
>
> * agent 自身的系統提示詞，而不是 Claude Code 系統提示詞
> * agent `skills:` 欄位中列出的 skills 的完整內容
> * CLAUDE.md 和 git 狀態。內建的 Explore 和 Plan agent [兩者皆不載入](https://code.claude.com/docs/zh-TW/sub-agents.md#what-loads-at-startup)，而定義中設定了 [`omitClaudeMd`](https://code.claude.com/docs/zh-TW/sub-agents#supported-frontmatter-fields) 的 agent 啟動時不包含使用者、專案和本地 CLAUDE.md 檔案。
> * 主 agent 在提示詞中傳遞的任何上下文
>
> 對於[分支](https://code.claude.com/docs/zh-TW/sub-agents.md#fork-the-current-conversation)，Claude Code 改為載入父對話到目前為止的內容、系統提示和工具。
>
> **上下文成本：** 與主會話隔離。
>
> > [!TIP]
> >
> > 對不需要您完整對話上下文的工作使用 subagents。它們的隔離防止膨脹您的主會話。

> [tab] Hooks
>
> **何時：** 觸發時。Claude Code 在特定生命週期事件（如工具執行、會話邊界、提示提交、權限請求和壓縮）時執行 hooks。有關完整清單，請參閱 [Hooks](https://code.claude.com/docs/zh-TW/hooks.md)。
>
> **什麼載入：** 預設情況下無。Hooks 在主對話外執行。
>
> **上下文成本：** 零，除非 hook 返回添加為訊息到您的對話的輸出。
>
> > [!TIP]
> >
> > Hooks 非常適合不需要影響 Claude 上下文的副作用（linting、logging）。

## 了解更多

每個功能都有自己的指南，包含設置指令、範例和配置選項。

> [card] [CLAUDE.md](https://code.claude.com/docs/zh-TW/memory.md)
>
> 存儲專案上下文、約定和指令

> [card] [Skills](https://code.claude.com/docs/zh-TW/skills.md)
>
> 給予 Claude 領域專業知識和可重複使用的工作流程

> [card] [Subagents](https://code.claude.com/docs/zh-TW/sub-agents.md)
>
> 將工作卸載到隔離的上下文

> [card] [Dynamic workflows](https://code.claude.com/docs/zh-TW/workflows.md)
>
> 從一個指令碼執行許多 subagents

> [card] [Cross-session messaging](https://code.claude.com/docs/zh-TW/cross-session-messaging.md)
>
> 讓 Claude 向您的其他工作階段傳送訊息

> [card] [MCP](https://code.claude.com/docs/zh-TW/mcp.md)
>
> 將 Claude 連接到外部服務

> [card] [Hooks](https://code.claude.com/docs/zh-TW/hooks-guide.md)
>
> 使用 hooks 自動化動作

> [card] [Plugins](https://code.claude.com/docs/zh-TW/plugins/overview.md)
>
> 捆綁和共享功能集

> [card] [Marketplaces](https://code.claude.com/docs/zh-TW/plugins/create-marketplace.md)
>
> 託管和分發 plugin 集合

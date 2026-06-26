# 知識攝取與跨專案分析 — 主動彙整 GitLab、找出無效率

> 所屬：[JARVIS 企業 AI 平台發想](README.md) · 對應願景 #8 #16

---

## 1. 對應願景需求

| # | 願景需求原文 | 動詞拆解 | 現況覆蓋 |
|---|---|---|---|
| **#8** | 「主動彙整公司 GitLab 上開放專案，彙整分類各專案的可共享知識」 | **爬取** → **分類** → **入庫** → **可被他人檢索** | 🔴 **10%**：read-project skill 能系統性讀懂一個專案、產 doc-index atom，但是**手動、單次、單專案** |
| **#16** | 「定期根據 AI 對全公司專案的技術架構/設定架構/工作流程認知，對各專案提設計核心與理念修補，彙整各專案無效率來源，分門別類最簡單率直報告」 | **定期** + **跨專案認知** + **產診斷報告**（設計修補 + 無效率彙整） | 🔴 **5%**：記憶**刻意 per-project 隔離**，沒有「中央能讀全部專案」的角色 |

兩條需求是同一條管線的兩端：#8 是**攝取**（把分散在 GitLab 的專案知識吸進來、分類、可共享），#16 是**分析輸出**（在吸進來的全公司知識上做橫向比對，產出「哪裡重複造輪、哪裡架構不一致、哪裡是技術債」的定期報告）。沒有 #8 的攝取面，#16 的跨專案分析就是無米之炊。

> 定位提醒：本檔是 [README](README.md) P2「感官與觸手」的第一個器官。它依賴 P0 地基——攝取進來的知識要落到一個**有權限、中心化、可被多客戶端讀**的知識服務（見 [記憶作為共享皮層](01-memory-as-shared-cortex.md)），而 #16 的「定期跨專案分析」本質是一個長時程 agent 任務，要靠 [編排核心](02-orchestration-core.md) 來排程與分工。

---

## 2. 現有方案比對表

> 數字會過時，皆附來源 URL。查證時點：2026-06-26。

| 系統 | 攝取 / 索引機制 | 權限同步 | 跨專案彙整 | 可仿效 | 來源 |
|---|---|---|---|---|---|
| **Sourcegraph** | **SCIP**（Source Code Intelligence Protocol）：語言無關索引格式，protobuf schema（`scip.proto`），記錄**定義 + 引用**，跨 repo 邊界做 go-to-definition / find-references；indexer 覆蓋 **10 語言家族**（C#/C++/Go/Java·Scala·Kotlin/PHP/Python/Ruby/Rust/TS·JS/Dart）。SCIP 是 LSIF 的後繼，2026 起轉為獨立開源治理（Steering Committee 含 Uber/Meta/Sourcegraph 工程師） | 走各 VCS host 既有權限（整合層） | 跨 repo 程式碼搜尋 + 導航（hover/PR 跨 repo 引用） | **索引格式直接借**：SCIP 當「程式碼語意層」的標準，不自己重造解析器；跨 repo 引用解析正是 #16「重複造輪偵測」的底層能力 | [scip-code.org](https://scip-code.org/) · [github.com/sourcegraph/scip](https://github.com/sourcegraph/scip/) · [docs.sourcegraph.com](https://docs.sourcegraph.com/code_intelligence/explanations/precise_code_intelligence) |
| **Glean** | 100+ turnkey connector（含 GitHub/GitLab/Slack/Confluence/Jira/Drive…）+ **permissions-aware knowledge graph** | ★ **權限烘進索引本身**：搜尋時無權文件「根本不出現」，自動同步來源系統 ACL | 跨來源統一檢索（代碼+文件+對話+工單），2026 推 Agentic Engine 2 / Enterprise Agent Development Lifecycle | **權限模型 = 黃金標準**：retrieval 時就過濾（呼應 [01](01-memory-as-shared-cortex.md) 的「scope 要從注入過濾升級成存取控制」） | [glean.com/connectors/gitlab](https://www.glean.com/connectors/gitlab) · [docs.glean.com/connectors](https://docs.glean.com/connectors/connectors-power-glean) |
| **GitLab Orbit（Knowledge Graph）** | 單一 Rust binary，把 SDLC + 程式碼建成 **property graph**；**Remote**（ClickHouse 後端）索引 groups/projects/users/notes/MR/pipelines/jobs/work items/milestones/labels/vulnerabilities/findings + **11+ 語言**程式碼；**Local**（DuckDB 後端，純程式碼、可離線）索引 dir/file/function·class 定義 + 跨檔 import；YAML ontology 驅動 | Local 走檔案系統權限；Remote **每次查詢由 GitLab 強制授權** | 統一 SDLC context API；DSL 編譯成 ClickHouse SQL，支援 aggregation/traversal/neighbors/pathfinding；REST + MCP + CLI 多介面 | **原生 GitLab + 知識圖 + MCP 介面 = 幾乎照抄的攝取後端**；Local/Remote 二分對應我們 client 離線快取 / 中央服務的分層 | [github.com/gitlabhq/orbit-knowledge-graph](https://github.com/gitlabhq/orbit-knowledge-graph) · [docs.gitlab.com/.../knowledge_graph](https://docs.gitlab.com/user/project/repository/knowledge_graph/) |
| **GitLab Duo Agent Platform**（Code Review Flow / Agentic SAST） | 站在 Orbit 圖上：跨檔依賴理解的 code review、18.9 起 Agentic SAST 自動分析 finding → 生成 context-aware fix → 開 MR | 走 GitLab 原生權限 | 在單專案內做 cross-file 推理（非跨專案彙整） | **「分析 agent 產 actionable 報告」的範式**：#16 的「設計修補建議」就是這類 agent 的跨專案版 | [about.gitlab.com/gitlab-duo-agent-platform](https://about.gitlab.com/gitlab-duo-agent-platform/) · [docs.gitlab.com/.../code_review](https://docs.gitlab.com/user/duo_agent_platform/flows/foundational_flows/code_review/) |

> **三家分工洞察**：Sourcegraph 給**程式碼語意層**（SCIP 索引）、Glean 給**權限感知檢索層**、GitLab Orbit 給**SDLC 知識圖 + 原生 GitLab 攝取**。我們不需要三者全造——攝取後端最接近現成的是 Orbit（開源、Rust、原生 GitLab、出 MCP），權限模型學 Glean，程式碼語意索引借 SCIP。差異化護城河在第三節的「無效率分析報告」與我們既有的**記憶品質治理**（信任分級/衝突偵測/反退避）。

---

## 3. 推薦設計取捨

### 3.1 攝取管線分層選型（不重造輪子）

給內部開發平台的優選骨架：

```
GitLab webhook（push/MR/issue 事件）
        ↓ 觸發
ingestion worker：pull commits/MR/issue + SCIP/LSP 程式碼索引 + 解析 commit/PR → intent
        ↓ 寫入
知識圖（Nodes: File/Function/Class/Issue/PR/Developer；Edges: calls/references/depends_on/resolves/authored_by）
        ↓ 加掛
permission filter（VCS access_token 驗證，只取/只回有權 repo）
        ↓ 雙路檢索
向量（語意）+ 圖（結構） → LLM context
        ↓ 轉化
萃取管線（quick/deep/SessionEnd）→ atom（可共享知識，走衝突偵測去重）
```

| 層 | 職責 | 優選 | 理由 |
|---|---|---|---|
| **觸發** | 何時攝取 | **GitLab webhook**（增量）+ 排程器（全量校正） | 增量即時、全量補漏；不要純輪詢爬（噪音大、延遲高） |
| **程式碼語意索引** | 解析定義/引用/依賴 | **SCIP**（或退而求其次 LSP） | 語言無關、10+ 語言現成、跨 repo 引用是「重複造輪偵測」的底層 |
| **知識圖** | 結構化專案知識 | **property graph**（file/function/PR/decision/owner 為節點） | Orbit 已驗證；圖天生擅長「跨專案 depends_on / 同構結構」比對 |
| **權限** | 誰能看到什麼 | **Glean-style：烘進索引、retrieval 時過濾** | 跨專案攝取最大紅線就是權限洩漏（見 §5） |
| **入庫** | 攝取內容 → 長期記憶 | 復用**萃取管線 → atom**（衝突偵測去重） | 我們已有的最成熟零件，直接接 |
| **分析** | 跨專案診斷 | **跨專案分析 agent**（長時程，編排層排程） | #16 的核心，見 §3.2 |

### 3.2 #16「無效率來源」怎麼定義指標 + 怎麼「分門別類最簡單率直報告」

「無效率」必須先**可量測**才不會淪為空泛抱怨。建議五類指標（每類給 AI 一個可計算的偵測信號）：

| 無效率類別 | 偵測信號（AI 怎麼算出來） | 資料來源 | 報告動作 |
|---|---|---|---|
| **重複造輪** | 跨專案函式/模組**語意相似度** ≥ 閾值（向量 + SCIP 引用圖比對），多處實作同一意圖 | 程式碼語意索引 | 「A 專案的 X 與 B 專案的 Y 高度相似 → 建議抽共用庫」 |
| **架構不一致** | 同類專案的分層/命名/設定結構**偏離**團隊基線 pattern | 知識圖結構 + 設定檔解析 | 「3 個服務各用不同 config 載入法 → 建議統一」 |
| **Dead code / 孤兒** | 函式無任何 `references` 邊、模組無 import、檔案長期無 commit | SCIP 引用圖 + git history | 「N 個無引用函式 → 清理候選」 |
| **技術債** | TODO/FIXME 密度、過期依賴版本、測試覆蓋缺口、循環依賴 | 程式碼掃描 + 依賴圖 | 按嚴重度排序的債務清單 |
| **流程瓶頸** | MR 平均 review 時長、pipeline 失敗率、issue 滯留時間 | SDLC 知識圖（Orbit 式） | 「X 專案 MR 平均卡 5 天 → 流程瓶頸」 |

**「最簡單率直報告」的格式原則**（呼應使用者直球偏好）：

| 原則 | 做法 |
|---|---|
| 分門別類 | 按上表五類分節，每類一張表 |
| 率直 | 每條 = 「**問題一句話** + **證據（檔/數字/連結）** + **建議動作**」，不鋪陳 |
| 可行動 | 每條附「修補成本估計」與「優先序」，讓 PM/lead 能直接排 backlog |
| 不淹沒 | 只報**超過閾值**的（見 §5「報告淪為噪音」風險）；附信賴度，低信賴度的標「(待人工確認)」 |

### 3.3 關鍵取捨（分析表）

| 取捨點 | 選項 A | 選項 B | 建議 | 理由 |
|---|---|---|---|---|
| 攝取觸發 | 純排程爬取 | webhook 增量 + 排程校正 | **混合** | 增量即時省算力，排程補漏防 webhook 丟事件 |
| 知識圖 vs 純向量 | 只做向量檢索 | 圖 + 向量雙路 | **雙路** | 「重複造輪 / 架構不一致」是**結構**問題，純向量答不準；向量補語意模糊查詢 |
| 程式碼索引 | 自寫 parser | SCIP/LSP 現成 | **SCIP** | 多語言自寫 parser 是無底洞 |
| 分析報告 | 一次全量重算 | 增量 + 定期全量 | **定期全量 + 事件增量** | #16 明寫「定期」；增量讓嚴重項即時冒出來 |
| 攝取內容入庫 | 新建獨立 store | 復用 atom 萃取管線 | **復用** | 衝突偵測 / 去重 / 信任分級已現成，換攝取來源即可 |

---

## 4. ★落地切入點

**核心洞察：我們已經有「讀懂專案 → 萃取知識 → 去重入庫」的零件，缺的是把它從「人手動跑一個專案」變成「排程器自動跑全公司專案 + 一個能跨專案橫向看的中央分析角色」。**

| 現有零件 | 現狀 | → 願景要長成 |
|---|---|---|
| **read-project skill** | 系統性閱讀一個專案 → doc-index atom，**手動單次** | **自動化**：webhook/排程觸發，批量跑全公司開放專案；read-project 的「讀懂→截錄重點」邏輯就是 ingestion worker 的核心 |
| **harvest skill**（Playwright + cookie） | 網頁收割（Google Docs/Sheets） | 攝取**非 Git 來源**（wiki/需求文件）的現成爬取骨架 |
| **docdrift**（src Edit → 偵測對應 _AIDocs 需更新） | 偵測「碼改了、文件沒跟」 | **攝取後維護**：攝取進來的專案知識，當來源 repo 變動時偵測「中央知識過期」並重攝取 |
| **PostToolUse 增量索引** | 本機編輯即時更新索引 | 攝取事件驅動的增量入庫範式（換成 webhook 事件源） |
| **萃取管線**（quick/deep/SessionEnd）+ 衝突偵測 | 對話內容 → atom，去重 | **攝取內容 → atom**：把「對話來源」換成「GitLab 來源」，去重/信任分級直接沿用 |
| **scope 四層**（global/shared/project 自治層） | 記憶**刻意 per-project 隔離**，無中央跨專案角色 | ★ **新增「跨專案中央分析角色」**：需打破 per-project 隔離（讓一個角色能讀全部專案），**但必須保權限**——只能讀有權的 repo，分析結果按 owner 權限分發 |
| **專案層 Vector（@3849，可上百 atom）** | 單專案向量檢索 | 跨專案向量庫的雛形，規模化後接公司級向量 DB（見 [01](01-memory-as-shared-cortex.md)） |
| **conflict-review / pending review** | 管理職裁決敏感 atom | 跨專案分析報告若涉敏感判斷（如「某團隊架構爛」），走裁決流再發布 |

### 能用 vs 必新建（誠實標注）

| 能力 | 狀態 | 說明 |
|---|---|---|
| 讀懂專案 → 截錄重點 | ✅ **能用（須自動化）** | read-project 邏輯完整，只是觸發方式是手動 |
| 攝取內容 → atom 去重入庫 | ✅ **能用（須換來源）** | 萃取管線 + 衝突偵測現成，來源從對話換成 GitLab |
| 攝取後維護（來源變→重攝取） | 🟡 **半成品** | docdrift 有「碼變→文件過期」概念，但偵測對象是本機，須改成 webhook 驅動的跨專案 |
| 非 Git 來源爬取 | 🟡 **半成品** | harvest 有 Playwright 骨架，但無排程、無分類入庫 |
| **GitLab connector** | 🔴 **必新建** | 現無任何 VCS 整合；建議直接評估接 Orbit（開源、出 MCP）而非自寫 |
| **排程爬取器** | 🔴 **必新建** | #16 的「定期」靠它；現無排程中樞 |
| **自動分類入庫**（攝取量級的分類） | 🔴 **必新建** | realm 分類器是「core/local 三問」的小規模分類，攝取量級需擴充 |
| **權限標記 / 權限感知檢索** | 🔴 **必新建** | 跨專案最大紅線；現況 scope 是注入過濾非存取控制（見 [01](01-memory-as-shared-cortex.md)） |
| **跨專案分析 agent** | 🔴 **必新建** | #16 核心；長時程任務，依賴 [編排核心](02-orchestration-core.md) |
| **定期報告產生器** | 🔴 **必新建** | journal skill 是單人事後聚合，跨專案診斷報告須新建 |

> 最小可行起步（推測）：先**不接 GitLab API**，用一支排程器在本機定時對「已 clone 的 N 個專案目錄」跑 read-project 邏輯 → 萃取進一個**跨專案 atom 命名空間**（暫時繞過權限，僅自己機器、僅自己有權的專案），跑通「批量攝取 → 跨專案向量比對 → 產一份重複造輪 + dead code 的 markdown 報告」閉環。**先驗證「跨專案分析能產出有用結論」這個最不確定的假設**，再補 GitLab connector、排程化、權限層。演進全圖見 [從現有系統如何長出來](09-evolution-from-current-system.md)。

---

## 5. 已知風險 / 紅線 / 待驗證假設

| 類別 | 項目 | 說明 / 緩解 |
|---|---|---|
| 🔴 紅線 | **權限洩漏** | 跨專案攝取一旦把「某人無權的 repo 知識」回給他，等於繞過 GitLab 權限。**必須**走 Glean-style「權限烘進索引、retrieval 時過濾」；攝取時就標 owner/可見範圍，分析報告也要按權限分發（無權者看不到涉及該 repo 的結論） |
| 🔴 紅線 | **「主動彙整」變「全公司監控」** | #16 的「對各團隊提無效率報告」極易被當成績效監控，引發信任崩壊。緩解：報告**對事不對人**（談架構/代碼/流程，不點名個人）、敏感判斷走 [conflict-review](#) 管理職裁決再發布、團隊可選擇加入 |
| 🔴 紅線 | **攝取了不該攝取的東西** | 開放專案裡可能混入 secrets/憑證/PII。攝取前須 secret 掃描 + PII 過濾，否則中央知識庫變成洩密放大器 |
| 🟡 風險 | **跨專案彙整誤判** | 「語意相似 ≠ 真重複」「結構不同 ≠ 架構爛」。誤判的「重複造輪/該統一」建議會誤導決策。緩解：相似度只當**候選信號**、附證據、低信賴度標「(待人工確認)」，不直接下結論 |
| 🟡 風險 | **LLM 提取幻覺傳播** | 攝取階段 LLM 對 commit/PR intent 的錯誤解讀會被當「事實」入庫，再被跨專案分析引用，幻覺逐層放大。緩解：攝取內容標來源行號/commit hash 可回溯，走萃取管線的信任分級（[臨]→[觀]→[固]），未經確認不晉升為高信任 |
| 🟡 風險 | **報告淪為噪音** | 全公司掃出幾千條「technical debt」沒人看。緩解：只報超過閾值項、按嚴重度+修補成本排序、每期限量 top-N、附「上期已修 / 仍未處理」對比讓報告有閉環 |
| 🟡 風險 | **攝取規模壓垮現有檢索** | 全域 BM25 in-memory（現約數十 atom）扛不住公司級數萬攝取 atom。緩解：攝取 atom 走專案層 Vector（@3849 已驗證可上百）→ 規模化接向量 DB 叢集（見 [01](01-memory-as-shared-cortex.md)） |
| ❓ 待驗證 | **跨專案分析真能產出有用結論** | 這是整條管線**最不確定**的假設。「AI 比對全公司專案後給的修補建議」實際採用率未知，可能多是顯而易見或不切實際的建議。→ MVP 階段就要先驗（見 §4 最小起步） |
| ❓ 待驗證 | **直接接 Orbit vs 自建攝取後端** | 假設「Orbit 開源 + 原生 GitLab + 出 MCP，直接接最省事」。但 Orbit 綁 GitLab.com Remote / ClickHouse，自架 GitLab 或要客製分析指標時，耦合代價未知，可能仍要自建（推測） |
| ❓ 待驗證 | **打破 per-project 隔離不破壊現有治理** | 假設「新增跨專案中央角色，能在保權限前提下與現有 scope 四層共存」。中央角色「能讀全部」與 scope「刻意隔離」是設計張力，平衡點待驗 |

---

> 互引：知識落到哪 [記憶共享皮層](01-memory-as-shared-cortex.md)｜誰來排程分析 [編排核心](02-orchestration-core.md)｜攝取工具怎麼上架 [工具認證註冊](04-tool-registry-and-protocols.md)｜權限地基 [安全治理](08-security-governance-compliance.md)｜演進路徑 [從現有系統如何長出來](09-evolution-from-current-system.md)｜回 [README](README.md)

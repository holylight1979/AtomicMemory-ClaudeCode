# 編排核心 — 大腦的前額葉：多 Agent 跨角色協作

> 所屬：[JARVIS 企業 AI 平台發想](README.md) · 對應願景 #2 #4 #16

---

## 0. 一句話定調

[README](README.md) 把現有原子記憶系統比喻成「很完整的海馬迴」。本檔講的是**前額葉**：負責「拆解任務 → 分派給對的角色/模型 → 收回交付 → 驗收把關 → 失敗重派」的那個**長時程狀態機**。

現有系統有不少「編排雛形」零件（sub-agent 並行 dispatch、Auto-Handoff、Fix Escalation、Codex Companion），但它們都是**單發、無狀態、限定情境**的——沒有一個會記得「這個專案這次要做的三件事、第二件卡住了、第三件等第一件交付」。**真正的核心（會分工、會記進度、會驗收的引擎）目前完全缺。** 這是整張願景圖裡最大的空洞。

---

## 1. 對應願景需求

| # | 願景需求原文（節錄） | 編排面要解的問題 |
|---|---|---|
| **#2** | 跨各家大模型主動分工 | 「主動」＝有個東西看著任務進度與各 agent/模型能力，**動態決定下一步派誰**。這是 manager/router 職責，不是固定 if-else。模型挑選細節分流到 [模型路由](03-model-routing.md)，本檔只管「分工的決策骨架」。 |
| **#4** | 跨企劃/程式/美術/MIS/SE/PM/QA，以**專案為核心**整合 | 多個專業角色協作同一個專案 → 需要「角色定義 + 任務交接協定 + 共享專案上下文」。這是 role-based 多 agent 協作引擎。 |
| **#16** | 定期跨專案分析、設計修補、無效率報告 | 這種任務本身就是**長時程、多步、跨資料源**的：掃多專案 → 分析 → 產報告 → 可能再開修補任務。沒有任務 DAG + 持久化狀態，跑到一半斷了就全廢。攝取面見 [知識攝取](05-knowledge-ingestion.md)，本檔管「怎麼把它編成一個可恢復的工作流」。 |

> 三條需求共同指向同一個缺件：**一個有狀態、可恢復、能分派、能驗收的編排引擎**。#2 要它的「分派決策」，#4 要它的「角色協作」，#16 要它的「長時程任務狀態」。

---

## 2. 現有方案比對表

> 數字與特性以 2026-06 各來源 URL 為準（會過時）。編排模型分四類：**graph**（有向圖節點/邊）、**conversation**（對話歷史驅動）、**role-based**（角色定義 + process）、**planner-executor**（先生計畫再執行）。

| 系統 | 編排模型 | 狀態管理與持久化 | HITL 機制 | 可仿效什麼 | 來源 URL |
|---|---|---|---|---|---|
| **LangGraph** (1.2, 2026-05-11) | graph + conditional edges（節點=agent，邊=轉移） | **每次轉移自動 checkpoint**，pluggable saver（Memory/SQLite/Postgres）；pause/resume、**time-travel 重播任意歷史狀態**、多實例水平擴展為一等公民 | 一等公民：runtime 暫停存狀態等人輸入（秒~小時），人回覆後從暫停點精確 resume；需設 persistent checkpointer | **狀態骨架本身**：耐久、可重播、可恢復。production 多 agent 業界 2026 收斂選擇 | [langchain.com/.../ai-agent-frameworks](https://www.langchain.com/resources/ai-agent-frameworks) · [christianmendieta.ca/.../time-travel](https://christianmendieta.ca/human-in-the-loop-ai-time-travel-workflows-with-langgraph/) · [tech-insider.org/.../13-steps](https://tech-insider.org/langgraph-tutorial-python-stateful-agent-13-steps-2026/) |
| **CrewAI** (0.105+, 2026-03) | role-based crew + process types（sequential/hierarchical） | session 狀態；OSS 版**可觀測性弱**（crew 失敗要當偵探查哪個 agent 壞）；0.105 加企業版 observability/scheduling | 有（guardrails / 迭代上限 / bounded delegation），但靠工程紀律補 | **角色心智模型**：role/goal/backstory 映射 PM/程式/美術/QA 最直覺；零到可動 crew <1 小時 | [vibecoding.app/.../crewai-review](https://vibecoding.app/blog/crewai-review) · [agilesoftlabs.com/.../crewai-in-production-2026](https://www.agilesoftlabs.com/blog/2026/06/crewai-in-production-2026-real-lessons) |
| **AutoGen / AG2** | conversation（GroupChat 多 agent 對話） | 對話歷史，預設 **in-memory**（重啟即失） | 對話中插人類 agent | 對話式協作的簡單抽象（已被 MS Agent Framework 吸收） | [learn.microsoft.com/.../magentic](https://learn.microsoft.com/en-us/semantic-kernel/frameworks/agent/agent-orchestration/magentic) |
| **Microsoft Agent Framework 1.0** (GA 2026-04-03) | 混合：graph workflows + 5 種 orchestration（sequential/concurrent/handoff/group-chat/**Magentic**） | AutoGen 簡單抽象 + Semantic Kernel 企業特性（**session 狀態 / type safety / middleware / telemetry / Azure**）；**全模式支援 streaming + checkpointing + HITL approvals + pause/resume** | 全模式內建 HITL approvals + pause/resume（長任務） | **★Magentic manager**：一個 manager 依「任務進度 + agent 能力」動態挑下一個該行動的 agent，維護 shared context + 追進度——**正是願景 #2「哪家在哪方面強就派誰」現成範式** | [devblogs.microsoft.com/.../version-1-0](https://devblogs.microsoft.com/agent-framework/microsoft-agent-framework-version-1-0/) · [learn.microsoft.com/.../magentic](https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/magentic) · [devblogs.microsoft.com/.../semantic-kernel-multi-agent-orchestration](https://devblogs.microsoft.com/agent-framework/semantic-kernel-multi-agent-orchestration/) |
| **Google ADK** | batteries-included（內含 agent-as-service） | 內建 session 管理；ADK Web 瀏覽器 debug UI、code execution、CLI | 透過 debug UI 介入 | **開發者體驗 / 可觀測 UI**：瀏覽器內看 agent 步驟、debug、agent 部署為 service | [langchain.com/.../ai-agent-frameworks](https://www.langchain.com/resources/ai-agent-frameworks) |
| **OpenHands** (舊 OpenDevin) | autonomous software-engineer agent（單 agent 自主多步） | 自管執行 sandbox 狀態 | 可中途介入 | **自主軟體工程 agent 的開源範本**：跑任何 LLM、可自架、2026 對標 Devin benchmark、~66k 使用者 | [agentstant.com/tools/opendevin](https://agentstant.com/tools/opendevin/) |
| **Devin 2.0 / 2.2** (Cognition, 2025-04 起) | planner-executor（virtual teammate） | 平台託管的 session + 程式碼庫狀態（Devin Search 索引 codebase） | **★Interactive Planning**：先生成多步技術藍圖→給人確認/改→才動工，task 成功率 +83% | **驗收前置範式**：把「計畫」做成一個顯式、可審、可改的 artifact，而非黑箱直接動手 | [pristren.com/.../devin-vs-claude-code](https://pristren.com/blog/devin-vs-claude-code-vs-github-copilot-workspace/) · [cognition.com/blog/devin-2](https://cognition.com/blog/devin-2) |

### 一頁速讀（這張表的結論）

- **要耐久狀態 → 抄 LangGraph**（checkpoint/replay/HITL 是一等公民，不是補丁）。
- **要動態分工 → 抄 Magentic manager**（依進度+能力挑下一個 agent）。
- **要角色直覺 → 抄 CrewAI 的 role/goal/backstory 定義法**（但別用它的 OSS 觀測性）。
- **要驗收/計畫可審 → 抄 Devin 的 Interactive Planning**（計畫先成 artifact 給人確認）。
- **要 debug UI → 看 ADK 的 Web UI 思路**。

---

## 3. 推薦設計取捨

場景：**PM / 企劃 / 程式 / 美術 / MIS / SE / QA 跨角色，協作同一個專案。**

### 3-1. 三套骨架怎麼疊（不是三選一，是分層各取所長）

```
┌─────────────────────────────────────────────────────────┐
│  L3 角色定義層 — 借 CrewAI 心智模型                          │
│     role / goal / backstory / 可用工具 / 可讀記憶 scope     │
│     (programmer / art / planner / qa / se / mis / pm …)    │
├─────────────────────────────────────────────────────────┤
│  L2 分派決策層 — 借 Magentic manager                        │
│     看「任務進度 + 各 agent/模型能力」→ 動態挑下一步派誰        │
│     (能力→模型的映射委派給 03-model-routing)                │
├─────────────────────────────────────────────────────────┤
│  L1 狀態骨架層 — 借 LangGraph                               │
│     任務 DAG / 每步 checkpoint / pause-resume / 失敗重播     │
│     持久化到 DB（非 in-memory）→ 斷線/重啟/跨 session 可恢復  │
└─────────────────────────────────────────────────────────┘
```

| 分層 | 選型 | 為什麼是它（理由） | 不選 X 的理由 |
|---|---|---|---|
| L1 狀態骨架 | **LangGraph 式 graph + DB checkpointing** | 願景 #16 的長時程任務「跑到一半斷掉不能全廢」是硬需求；checkpoint/replay/HITL 在它是一等公民 | 不用 AutoGen：對話歷史預設 in-memory，長任務不耐久 |
| L2 分派決策 | **Magentic-style manager** | 願景 #2「主動分工」＝動態決策，不是寫死 if-else；manager 維護 shared context + 追進度 | 不用 CrewAI hierarchical 當決策核心：OSS 觀測性弱、失敗難 debug |
| L3 角色定義 | **CrewAI-style role/goal/backstory** | 願景 #4 的角色（PM/程式/美術/QA）天然映射 role 抽象，宣告式、易讀（合 USER.md「高可讀性」偏好） | — |
| 計畫/驗收 | **Devin-style Interactive Planning** | 把「計畫」做成顯式 artifact，先給人確認再動工（HITL gate），#16 報告類任務尤其需要 | 不黑箱直衝：成本與錯誤都不可控 |

> **(推測)** 實作上不必真的引入這三個重量級框架當依賴。更可能是「**抄它們的設計、用現有原子記憶系統的零件自建一個輕量編排器**」——理由見 USER.md 偏好「薄框架、開發者要能理解底層」與 [演進路徑](09-evolution-from-current-system.md)。框架當設計參考，不當運行時黑盒。

### 3-2. 任務生命週期：分解 → 指派 → 交付 → 驗收閘

```
[需求]
   │ ① 分解 (decompose)        ← PM/planner agent + Devin 式 Interactive Planning
   ▼   產出：任務 DAG（節點=子任務，邊=依賴），人類確認 gate
[任務 DAG]
   │ ② 指派 (assign)           ← Magentic manager：看能力+進度挑 role+model
   ▼   產出：每節點 → (role, model, 工具集, 記憶 scope)
[各 agent 並行/串行執行]      ← 現有 sub-agent dispatch 可長大成這層
   │ ③ 交付 (deliver)          ← agent 回傳 artifact + 自評 + 證據
   ▼
[驗收閘 acceptance gate]      ← ★最缺、最難、最關鍵的一環
   │   通過 → 寫回專案記憶（atom）+ 標 DAG 節點 done
   │   不通過 → 退回重派（retry++），達閾值升級
   ▼
[全 DAG done → 結案報告]
```

### 3-3. 驗收閘怎麼設計（核心難點，分析表）

「驗收」是這套引擎和「一堆 agent 亂跑」的唯一分界線。設計選項：

| 驗收方式 | 適用任務 | 客觀性 | 成本 | 落地建議 |
|---|---|---|---|---|
| **程式化硬閘**（測試通過/lint/build/schema 校驗） | 程式、結構化產物 | 高（可重現） | 低 | **優先**。現成可借：Stop gate 的 test-fail 偵測、evasion guard | 
| **對抗審計**（第二個 agent/模型挑錯） | 設計、報告、文案、跨專案分析 | 中（仍主觀但去單點偏誤） | 中 | 借 **Codex Companion**（GPT 第二意見）+ Fix Escalation 6-agent 會議思路 |
| **HITL 人類驗收**（角色負責人 approve） | 高風險 / 對外交付 / 美術主觀 | 取決於人 | 高（要人時間） | 借 LangGraph HITL pause-resume；只在高風險節點插，避免到處攔人 |
| **規則 + 信任分級**（產出寫記憶前過品質閘） | 知識/記憶寫入 | 中 | 低 | 直接復用現有 **write-gate 品質閘門 + 信任分級 [臨]/[觀]/[固]** |

> **取捨建議**：驗收**分級**——可程式驗證的（程式產物）走硬閘；主觀產物（設計/報告）走「對抗審計 + 必要時 HITL」；記憶寫入走現有 write-gate。**不要追求單一萬能驗收標準**（見 §5 紅線）。

---

## 4. ★在現有原子記憶系統上的落地切入點

這是本檔最有實作價值的一節：把「編排引擎」釘回現在的程式碼，**誠實標「能用 vs 必新建」**。

### 4-1. 能長大的「編排雛形」零件（已有，可演進）

| 現有零件 | 現況本質 | 對應編排職責 | 能長成什麼 | 缺口 |
|---|---|---|---|---|
| **sub-agent 並行 dispatch**（同 message 多 Agent，Explore/Plan/general-purpose） | 單發、無狀態、parent 收完即丟 | §3-2 的「執行層」 | 任務 DAG 節點的執行單元 | 缺 DAG 調度器在上面管依賴/進度 |
| **Auto-Handoff 四層**（跨 session 無損交接 stub） | 只是「交接 **prompt**」，非任務編排 | 長時程狀態的**雛形** | 升級成「任務狀態快照」而非純文字 prompt | 缺結構化任務狀態（現在是給人/下一 session 讀的文字，非機器可恢復的 state） |
| **Fix Escalation**（retry≥2 → 6-agent 精確修正會議） | 限定「修不好」情境觸發 | §3-2 的「失敗重派 + 升級」 | 通用「驗收不通過 → 升級」協議 | 現在綁死「修 bug」場景，需抽象成通用 retry/escalate |
| **Codex Companion**（GPT 第二意見對抗審計，subprocess） | 限定審計當前動作 | §3-3 的「對抗審計驗收」 | 驗收閘的對抗審計引擎 | 現在是「審當前對話」，需變成「審任意 agent 交付物」 |
| **Wisdom Engine**（情境分類 + 反思） | 記憶層自省 | manager 的「進度/情境判讀」輔助 | 餵 manager 做分派決策的情境訊號 | 現在不參與任務分派 |
| **role:{name} scope 四層**（programmer/art/planner…） | 記憶**注入過濾**（誰能看哪些 atom） | §3-1 的 L3「角色定義」 | 角色的記憶/工具 scope 邊界 | 只是「能看什麼記憶」，不是「能做什麼任務、用什麼工具」的完整 role |
| **Stop gate**（sync/evasion/test-fail/post-mortem） | 單 session 收尾把關 | §3-3 的「程式化硬閘驗收」 | 驗收閘的硬閘部件（test-fail/evasion 復用） | 現在管「一個 session 完成」，非「一個任務節點交付」 |
| **write-gate 品質閘 + 信任分級** | 記憶寫入品質控制 | §3-3 的「記憶寫入驗收」 | 交付物寫回專案記憶的閘 | 直接可復用 |

### 4-2. 必須新建（現有零件補不出來）

| 必新建 | 為什麼補不出來 | 第一性需求 |
|---|---|---|
| **長時程任務狀態機 + 持久化** | 現有狀態全是 `workflow/state-{session-id}.json` 的 **session ephemeral**；Auto-Handoff 是文字 prompt 不是機器 state | 跨 session/跨 agent 可恢復的任務 state（DB-backed，借 LangGraph checkpoint 思路） |
| **任務 DAG / 分解-依賴圖** | 完全沒有「子任務 + 依賴」的資料結構；現在是線性 session | 一個 DAG 模型 + 調度器（哪些可並行、哪些等依賴） |
| **分派決策器（manager）** | sub-agent dispatch 是 parent 自己當下決定，無「看全局進度+能力動態挑」的常駐邏輯 | Magentic-style manager（能力映射委派 [模型路由](03-model-routing.md)） |
| **通用驗收閘**（非綁修 bug） | Fix Escalation/Stop gate 都綁死特定情境 | 抽象的 acceptance gate：硬閘/對抗/HITL 分級（§3-3） |
| **跨 agent 記憶共享 / shared task context** | 現在記憶 scope 是「**注入過濾**」非「**多 agent 即時共享同一份任務黑板**」；且記憶 per-project 隔離（#16 痛點） | 任務級 shared context（blackboard）+ 跨專案讀取權（接 [記憶共享皮層](01-memory-as-shared-cortex.md) 的服務化 + 權限） |

> **依賴警告**：§4-2 的「跨 agent 記憶共享」與「持久化狀態」**強依賴** [01 記憶服務化 + 真權限](01-memory-as-shared-cortex.md) 這個 P0 地基。沒有中心化、有權限、多客戶端可即時讀寫的記憶服務，編排器存的任務 state 還是散在各人單機 → 退回 N 個孤島。**編排是 P1，但它的記憶共享部分得等 P0 完成**（見 [README 演進路徑](README.md) 與 [09](09-evolution-from-current-system.md)）。

### 4-3. 最小可行起點（MVP，(推測) 排序）

1. **抽象 Fix Escalation → 通用 retry/escalate 協議**（最小改動、復用最多現成邏輯）。
2. **把 Auto-Handoff 的「文字交接」加一份「結構化任務 state」副本**（往持久化狀態機踏第一步）。
3. **單專案、3-5 節點的線性任務 DAG + 程式化硬閘驗收**（先不碰動態分派，manager 用固定順序）。
4. 驗證 OK 後，才上 Magentic-style 動態分派 + 跨 agent shared context（依賴 P0）。

---

## 5. 已知風險 / 紅線 / 待驗證假設

| 類型 | 項目 | 說明 | 緩解 / 待驗證 |
|---|---|---|---|
| 🔴 紅線 | **多 agent 成本爆炸** | CrewAI 已實證「多 agent 通訊 high token consumption」；6-agent 會議 × 長 DAG = token 與 $ 失控 | 設迭代上限 + bounded delegation（CrewAI 教訓）；分派器把便宜任務派便宜模型（[模型路由](03-model-routing.md)）；**(待驗證)** 每節點成本上限與全局預算閘 |
| 🔴 紅線 | **驗收的客觀標準難定** | 程式可測，但「設計好不好/報告有沒有價值」沒有可重現的客觀函數 | §3-3 分級驗收（不追單一萬能標準）；主觀項用對抗審計去單點偏誤 + 必要時 HITL；**(待驗證)** 對抗審計的假陽/假陰率 |
| 🟠 風險 | **編排複雜度反噬** | 編排層自己變成最難 debug 的黑盒（CrewAI OSS 觀測性弱已是前車之鑑） | 借 ADK 式可視化 debug UI + LangGraph time-travel 重播；每步 checkpoint 留審計軌跡 |
| 🟠 風險 | **與「薄框架」偏好衝突** | LangGraph/MS Agent Framework 都是重依賴，違 USER.md「薄框架、懂底層」 | 框架當設計參考、自建輕量編排器（§3-1 推測）；**(待驗證)** 自建 vs 直接用框架的維護成本 |
| 🟠 風險 | **錯誤級聯 / 失控迴圈** | DAG 上游 agent 產出垃圾 → 下游全建在錯誤上；retry 迴圈打不住 | 驗收閘攔在每個節點交付處（不是只攔最後）；retry 達閾值強制升級/停（借 Fix Escalation + Guardian「最多阻 2 次、第 3 次放行」精神，但編排場景要的是「停下問人」而非放行） |
| 🟡 假設 | **(推測) sub-agent dispatch 能無痛長成 DAG 執行層** | 現在 parent dispatch 是同步收束模型，DAG 要非同步 + 部分失敗容錯 | **(待驗證)** 現有 dispatch 機制能否支援「節點失敗不拖垮整圖」 |
| 🟡 假設 | **(推測) 角色 scope 能直接當 agent role 邊界** | scope 管「看什麼記憶」≠ role 管「做什麼任務/用什麼工具」 | **(待驗證)** 需擴 role 定義（加 goal/工具集/驗收責任），不只是記憶過濾 |

---

## 6. 收束（對發想者）

- **記住分界線**：編排引擎 vs「一堆 agent 亂跑」，差別只在**驗收閘**和**持久化任務狀態**這兩樣——而這兩樣恰恰是現有系統**最缺**的。其餘（角色、分派、執行）都有雛形可長大。
- **設計可抄、運行自建**：LangGraph（狀態）+ Magentic（分派）+ CrewAI（角色）+ Devin（計畫/驗收）四套各取一層，但落地用現有零件自建輕量編排器，守住「薄框架」偏好。
- **它卡在 P0 地基上**：編排本體是 P1，但「跨 agent 記憶共享」這條腿站在 [01 記憶服務化 + 真權限](01-memory-as-shared-cortex.md) 上。地基沒好，編排器存的狀態還是單機孤島。
- **下一步該釐清的**：(a) 驗收閘的分級規則與成本上限怎麼定；(b) 現有 sub-agent dispatch 能否非同步化當 DAG 執行層（待驗證）；(c) 角色 scope 要擴成完整 role 定義的工作量。

> 鄰檔：分派「派誰」的模型挑選見 [模型路由](03-model-routing.md)；角色能用的工具從哪來見 [工具註冊](04-tool-registry-and-protocols.md)；#16 跨專案分析的資料攝取見 [知識攝取](05-knowledge-ingestion.md)；落地總路徑見 [從現有系統長出來](09-evolution-from-current-system.md)。

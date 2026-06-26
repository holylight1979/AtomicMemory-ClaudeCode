# 記憶作為共享皮層 — 從單機海馬迴到多租戶中央知識層
> 所屬：[JARVIS 企業 AI 平台發想](README.md) · 對應願景 #1 #3 #10

> **本檔立場**：屬 `_AIDocs/Vision/` 發想層，以「說不定某天會真的拿出來做」的可執行設計參考書寫，非空想。技術數字均附來源 URL（會過時，以原始出處為準）；前瞻判斷標 (推測)。

---

## 1. 對應願景需求（為何屬此檔）

| # | 願景需求原文 | 與記憶層的關係 |
|---|------------|--------------|
| **#1** | 客戶端 AI + 內部 AI 伺服器、自主分類 scope、內部開發人員專用（源自 JARVIS） | 「自主分類 scope」＝記憶寫入時的作用域判定；「客戶端 + 伺服器」＝記憶必須從單機檔案升級為中央服務。**這是記憶層的地基題。** |
| **#3** | 分層記憶（專案 / 個人 / 核心），跨專案不重複勞動 | 現有 scope 四層 + realm 分區已覆蓋約 70%（README 評），缺的是「中心化共享 + 即時同步」，不是分層概念本身。 |
| **#10** | 開發經驗知識最大保留 | atom + episodic + 萃取管線已是個人單機天花板；缺「多人匯流、規模化存取」。 |

一句話定位：**現有原子記憶系統是一顆做到單機天花板的「海馬迴」；本檔談的是把它升級成多人共用、權限感知的「共享皮層」。** 這顆皮層是 JARVIS 大腦最關鍵的器官之一，但不是大腦本身（編排引擎才是核心，見 [編排核心](02-orchestration-core.md)）。

> 為什麼是「皮層」不只是「資料庫」：差異化護城河在**記憶品質治理**——信任分級、效用閉環、衝突偵測、選擇性遺忘、反退避。多數企業知識層只有「存 + 檢索」，沒有「治理 + 自我精煉」。這層已經啃下來了，是升級時不能丟的本錢。

---

## 2. 現有方案比對表

> 取材自各系統官方文件與論文。Zep 數字以原始論文（arxiv 2501.13956）為主，並標注與二手評測來源的差異。

| 系統 | 核心設計 | 可仿效點 | 侷限 / 紅線 | 來源 URL |
|------|---------|---------|------------|----------|
| **Mem0** | 四維作用域 `user_id` / `agent_id` / `run_id`(session) / `app_id`(org)，寫入時打標、檢索時組合並自動 merge & rank（user > session > raw history）；single-pass ADD + entity linking + 多信號檢索（semantic + BM25 + entity） | **四維作用域＝多租戶標杆**：billing agent 永不見支票、support agent 只見支持事實，靠 scope 組合天然隔離；entity linking 可跨作用域連結但需顯式開 | 作用域需**早期定**（事後改 schema 痛）；跨作用域查詢複雜；**無原生 document-level ACL**（隔離靠 query 標對 id，非資料庫強制，標錯就洩漏） | [multi-agent memory](https://mem0.ai/blog/multi-agent-memory-systems) · [GitHub](https://github.com/mem0ai/mem0) · [entity-scoped](https://docs.mem0.ai/platform/features/entity-scoped-memory) |
| **Letta / MemGPT** | OS 虛擬記憶式三層：Core（RAM 常駐，agent 人格 + 當前任務）/ Recall（磁碟 + 向量，可召回歷史）/ Archival（冷存）；agent 用工具自編輯記憶（self-editing） | 「agent 自己管理記憶層級」的範式；Core block 概念可映射到我們的 [固] 常駐高信任 atom | 運行時綁定深（記憶與 agent runtime 耦合）；**多租戶弱**（為單 agent 設計，非企業多人共享） | [agent memory](https://www.letta.com/blog/agent-memory/) |
| **Zep**（Graphiti 引擎） | 時序知識圖：事實帶 `valid_at` / `invalid_at` 版本戳、可標記過時、支援「當時 vs 現在」推理；融合對話 + 結構化業務資料 | **時序版本化**正是我們缺的——atom 現在改寫即覆蓋，無「這事實何時為真」維度；實體解析內建 | 圖維護成本高；企業級需自架或付費；數字需驗（見下） | [論文 arxiv 2501.13956](https://arxiv.org/abs/2501.13956) · [二手評測 2026](https://baeseokjae.github.io/posts/zep-ai-agent-memory-review-2026/) |
| **Cognee** | 文檔→知識圖 ECL 管道：Extract → **Cognify**（chunk + 抽實體/typed edge + OWL/RDF ontology 驗證，每節點打 `ontology_valid` 旗標分辨 grounded vs 幻覺）→ Load（同時寫向量 + 圖 + 關聯庫）；**Memify** 後處理：rated response 回饋 → 調 edge 權重，越用越準 | **`ontology_valid` 旗標**＝抗幻覺寫入的好設計，可映射我們的 Write Gate；**Memify edge-weight 回饋**＝與我們 atom_access α-β 效用閉環同源思路，可互相印證 | 重度依賴 LLM 抽取品質；ontology 需供給或自動生成（自動生成的本體未必對） | [grounding AI memory](https://www.cognee.ai/blog/deep-dives/grounding-ai-memory) · [Cognify docs](https://docs.cognee.ai/core-concepts/main-operations/cognify) · [Memify](https://medium.com/@cognee/cognee-knowledge-graph-optimization-memify-post-processing-pipeline-ce049417d9c3) |
| **多租戶 RAG 三模型** | (a) store-per-tenant（每租戶獨立庫）(b) multitenant + RLS（共庫，列級安全過濾）(c) hybrid（shared + multitenant + per-tenant 混用，Azure 推薦） | hybrid 對應我們未來的 global（shared）/ role（multitenant）/ personal（近 per-tenant）三態 | store-per-tenant 隔離最強但成本高、難跨租戶查；RLS 必須在 **retrieval 階段就過濾**，漏一處即洩漏 | [Azure secure multitenant RAG](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/secure-multitenant-rag) |
| **權限感知檢索三模式** | (1) Orchestrator / API 層過濾（中央治理 + 稽核）(2) **PostgreSQL RLS**（資料庫層強制，應用無法繞過）(3) 向量 DB 內建過濾：Qdrant JWT payload filter（v1.9.0+）/ Pinecone namespace（1 RU/查 vs metadata 過濾 100 RU） | RLS「應用繞不過」是真 AuthZ 的關鍵；Qdrant payload index on `tenant_id`、Pinecone namespace 物理分區可直接拿來分租戶 | 純 API 層過濾＝信任應用程式不出錯（我們現況的等價弱點）；向量 DB 過濾須建索引否則慢 | [Azure 同上](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/secure-multitenant-rag) · [Qdrant multitenancy](https://qdrant.tech/documentation/manage-data/multitenancy/) |

### Zep 數字的誠實標注（待驗證點）

- **論文（arxiv 2501.13956）原始口徑**：在 DMR benchmark 達 **94.8%**（勝 MemGPT 93.4%）；在 LongMemEval 上**準確率最高提升 18.5%、回應延遲降低約 90%**，最大增益在 temporal-reasoning / multi-session / single-session-preference 類題。來源：[論文頁](https://huggingface.co/papers/2501.13956)、[arxiv abs](https://arxiv.org/abs/2501.13956)。
- **二手評測（2026 review）口徑**：另引「38.4%（時間推理）/ 184%（偏好合成）」與「<200ms p99、SOC 2」。這些**未在原論文核到對應數字**，疑為不同 benchmark 切片或產品頁宣稱。**(推測)** 採用時應回原始出處復核，勿直接引二手百分比。

> 教訓（與本系統 rules/core.md「斷言前先實證」同源）：**第三方評測的漂亮百分比要回原始論文核口徑**，本檔已分開列示。

---

## 3. 推薦設計取捨

### 優選組合：四維作用域（Mem0 式） + 雙層權限強制（RLS + 向量過濾） + 時序版本（Zep 式） + 既有品質治理保留

```
寫入：atom_io funnel（保留）→ 打 scope 四維標 → ontology/Write-Gate 驗證 → 寫中央 store
存取：身分(SSO/RBAC) → RLS 列級過濾（DB 強制） → 向量 payload 過濾（檢索層） → ACT-R 排序 → token budget
治理：信任分級 + 效用 α-β 閉環 + 時序版本戳 + 衝突偵測 + 選擇性遺忘（全部保留並服務化）
```

| 取捨點 | 選項 | 建議 | 理由 |
|--------|------|------|------|
| 作用域模型 | Mem0 四維 vs 現有 scope 四層 | **沿用現有四層語意，補上「檢索期強制過濾」** | 現有 global/shared/role/personal 已是好的四維雛形，缺的是「過濾」不是「分層」；不必砍掉重練 |
| 權限強制點 | 純 API 層 vs RLS vs 向量過濾 | **RLS（DB 強制）為主 + 向量 payload 過濾為輔** | 純 API 層＝信任應用不出錯（＝我們現況弱點）；RLS「應用繞不過」才是真 AuthZ |
| 向量庫 | LanceDB（現用）vs Qdrant vs Pinecone | **規模化後遷 Qdrant**（JWT payload filter + tenant 分片） | LanceDB 單機嵌入夠用；公司級多租戶要 Qdrant 的內建 multitenancy + payload index |
| 時序 | 覆蓋改寫（現況）vs Zep 版本戳 | **加 `valid_at`/`invalid_at`，先軟上線** | 「決策何時生效、何時被推翻」對開發知識極有價值；但圖維護成本高，先在高價值 atom 試點 |
| 自我精煉 | 自建 α-β vs Cognee Memify | **保留自建 α-β，借鏡 Memify 的 edge-weight 思路** | 兩者同源（用信號回饋調權重），自建的已驗證且懂底層；Memify 印證方向正確，不必換框架 |
| 多租戶隔離模型 | per-tenant / RLS / hybrid | **hybrid**（global=shared 庫、role=multitenant、personal=近 per-tenant） | 對齊 Azure 推薦，且天然映射現有三層 scope |

> 薄框架原則（USER.md 偏好）：**不引整套 Mem0/Zep/Cognee 取代現有系統**，而是抽取它們各自的「一個對的設計點」（四維作用域 / 時序戳 / ontology 旗標 / RLS 強制）接進現有管線。開發者要能理解底層運作，故權限與檢索盡量落在能自審的 PostgreSQL RLS + 自建 funnel，而非黑箱 SaaS。

---

## 4. ★ 在現有原子記憶系統上的落地切入點（本檔最重要的一節）

> 原則：**誠實標「能用 vs 必新建」**，不把現況講得比實際強。現況最致命的三個前提：
> 1. **現有 scope 是「注入過濾」，不是「存取控制」** — 它決定「要不要把 atom 塞進 prompt」，不是「你有沒有權限讀」。任何能讀檔案系統的人都能 `cat` 到別人的 personal atom。
> 2. **管理職認證是 honor-system（君子協定）** — personal `role.md` 自宣告 + shared `_roles.md` 白名單，無真 AuthN，改檔即提權。
> 3. **單機檔案、無中央服務** — atom 散在各人 `~/.claude`，靠 git/svn commit/pull 做最終一致同步，無並發控制、無 server push。

### 4.1 零件盤點：能用 vs 必新建

| 現有零件 | 現況能力 | 在共享皮層裡 | 判定 |
|---------|---------|-------------|------|
| **scope 四層** global/shared/role:{name}/personal:{user} | 注入時過濾哪些 atom 進 prompt | 作用域**語意**直接複用（已是好的四維雛形） | ✅ **能用**（語意層）／ ❌ 必新建強制過濾 |
| **realm 維度**（core/local，path 前綴推導） | 控制「只在 cwd∈~/.claude 注入」 | 可演化為「租戶 / 專案邊界」標籤 | ✅ **能用**（概念可遷移） |
| **atom_access α-β 效用閉環**（Beta-Bernoulli, Wilson 下界, λ=0.97 慢衰減） | 注入→使用→結果閉環，晉升/降級候選 | **直接服務化**：與 Cognee Memify edge-weight 同源，是護城河 | ✅ **能用**（保留並服務化） |
| **信任分級** [臨]→[觀]→[固] + Confirmations 門檻 | 跨 session 萃取命中升級 | 共享皮層的「知識成熟度」標籤，多人匯流時更有意義 | ✅ **能用** |
| **檢索管線** trigger→BM25 in-mem→Vector fallback→ACT-R→Related-edge→Section-level→budget | 個人單機快、效果好 | BM25 只 in-memory ~56 atoms，**不可規模化到公司級數萬 atom** | ⚠️ **部分能用**：ACT-R 排序 / Related-edge / Section-level 邏輯可留；**BM25 in-mem 必換**向量 DB 叢集 + 權限感知過濾 |
| **寫入 funnel** atom_io.py 唯一入口 + PreToolUse gate 強制 | 單機唯一寫入點、強制驗證 | **funnel 模式直接複用**，但後端從檔案改中央 store API | ✅ **能用**（介面留，後端改） |
| **衝突偵測**（write/pull/startup 三時段 + 敏感類 auto-pending review） | 單人視角的衝突偵測 | 多人同改需升級成 CRDT/OT 或樂觀鎖 | ⚠️ **部分能用**：偵測時機/敏感分類邏輯留；**多人並發合併必新建** |
| **Memory Governance**（分心懲罰 / relevance gate / selective forgetting / 隔離 `_distant/`） | 個人記憶衛生 | 共享皮層更需要（多人污染風險更高） | ✅ **能用**（價值更高） |

### 4.2 必須新建的硬骨頭（現況完全沒有）

| 必新建項 | 為什麼現況做不到 | 對應現有方案參考 |
|---------|----------------|----------------|
| **中央 atom store（有 API 的服務）** | 現在是單機檔案 + git/svn 最終一致；無並發寫入、無 server push 即時同步 | Mem0 server / 自架 PostgreSQL + pgvector |
| **真 AuthN**（SSO / LDAP / OIDC） | 現在是 honor-system，改 `role.md` / `_roles.md` 即提權 | 企業 IdP 整合 |
| **真 AuthZ（檢索期強制過濾）** | 現在 scope 只是「注入過濾」，能讀檔即能讀全部 | **PostgreSQL RLS**（應用繞不過）+ Qdrant JWT payload filter |
| **規模化檢索** | BM25 in-mem ~56 atoms，公司級數萬 atom 撐不住 | Qdrant 叢集 + tenant 分片 + payload index on `tenant_id` |
| **多人並發合併** | 三時段衝突偵測是單人視角 | CRDT / OT / 樂觀鎖 |
| **不可篡改稽核** | JSONL audit 在本機可被改 | append-only / 簽章 / WORM 儲存 |
| **at-rest 加密 + retention 政策** | 明文 `.md` 散落各人硬碟 | DB 層加密 + 分租戶 retention |

### 4.3 演進切入順序（不平行鋪開，有地基依賴）

1. **抽 funnel 後端**：`atom_io.py` 介面不動，後端從「寫檔案」改「呼叫中央 store API」（先單實例，client 仍可離線快取）。— 風險最低、改動面最小的第一刀。
2. **真身分接入**：SSO/OIDC + RBAC，把 honor-system 的 `_roles.md` 換成 IdP group。
3. **檢索期強制過濾**：PostgreSQL RLS default-deny + 向量 payload 過濾；**scope 從「注入過濾」正式升級為「存取控制」**。
4. **規模化向量層**：LanceDB → Qdrant 叢集，保留 ACT-R / Related-edge / Section-level 排序邏輯，只換底層索引與過濾。
5. **時序版本 + 多人合併**：加 `valid_at`/`invalid_at`，衝突偵測升級為並發合併。

> 與 [從現有系統如何長出來](09-evolution-from-current-system.md) 的 P0 地基對齊：步驟 1–3 即 README 所述「記憶服務化 + 真權限」，是它配當核心的入場券。

---

## 5. 已知風險 / 紅線 / 待驗證假設

### 紅線（不可踩）

- **「注入過濾」≠「存取控制」這條線一定要跨過**：若服務化後仍用 scope 當權限，等於把 honor-system 搬上伺服器，反而給人「有權限」的錯覺。AuthZ 必須落在資料庫層（RLS）或檢索層強制，不能只靠應用自律。
- **品質治理零件不可在服務化過程被丟掉**：信任分級 / α-β 效用閉環 / 遺忘 / 反退避是護城河，遷移時要當一等公民帶走，不是「之後再補」。
- **多租戶隔離標錯 id 即洩漏**：Mem0 式四維作用域的天然隔離前提是「query 標對 id」；企業場景必須有 RLS 兜底，不能只靠應用標對。

### 待驗證假設 (推測)

| 假設 | 風險 | 驗證方式 |
|------|------|---------|
| (推測) 現有 ACT-R / Related-edge 排序邏輯能無痛搬到 Qdrant 之上 | 排序依賴 in-memory 結構，向量 DB 重排介面未必對等 | 小規模 PoC：同一批 atom 在 LanceDB vs Qdrant 跑相同 query 比對排序 |
| (推測) PostgreSQL RLS 在公司級數萬 atom + 多租戶仍維持可接受延遲 | RLS policy 複雜時查詢計畫退化 | 壓測 default-deny + tenant policy 在目標規模的 p95/p99 |
| (推測) 時序版本戳能在不重寫 atom 格式下軟上線 | atom `.md` schema 加欄位可能波及 funnel / 索引 | 先在 `_atom_index.json` JSON SoT 加 optional 欄位試點，不動 `.md` 本體 |
| (推測) BM25→向量 DB 切換後，~56 atom 規模的「小而精」檢索品質不退化 | 向量在小語料上未必勝 BM25 | A/B：保留 BM25 為 fallback，比對命中品質 |

### 開放問題

- 離線客戶端快取與中央 store 的一致性模型？（最終一致 vs 強一致 — 影響多人協作體感，待 [編排核心](02-orchestration-core.md) 的任務狀態機定義後再決）
- Zep 式時序圖的維護成本，對「個人開發知識」這種寫多讀少的場景是否划算？(推測 多數 atom 不需要時序，只對「決策/架構」類值得)
- 二手評測數字（Zep 38.4%/184%、<200ms p99）的原始口徑未核到，採信前必須回原始 benchmark 復核（見 §2 誠實標注）。

---

> **下一步導讀**：本檔談的是「皮層本身怎麼升級」；皮層升級完，誰來指揮它讀寫、跨 agent 分工，見 [編排核心](02-orchestration-core.md)；整體演進路徑與地基依賴見 [從現有系統如何長出來](09-evolution-from-current-system.md)；回 [README](README.md)。

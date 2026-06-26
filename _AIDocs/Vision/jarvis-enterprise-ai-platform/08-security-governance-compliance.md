# 安全、權限、治理、合規 — 私有平台的免疫系統
> 所屬：[JARVIS 企業 AI 平台發想](README.md) · 對應願景 #6 #13

> **本檔立場**：屬 `_AIDocs/Vision/` 發想層，以「說不定某天會真的拿出來做」的可執行設計參考書寫，非空想。技術數字均附來源 URL（會過時，以原始出處為準）；前瞻判斷標 (推測)。查證時點：2026-06-26。

---

## 1. 對應願景需求

| # | 願景需求原文 | 與本檔的關係 |
|---|------------|------------|
| **#6** | 客戶端可以是公司內部私有的溝通平台、**由 AI 自己維護**，且可因**涵蓋系統部**、達到**權限控管**等安全性防護 | 三件事：① 私有平台的「免疫系統」（AuthN/AuthZ/加密/稽核）② 權限要能「涵蓋系統部」＝按部門/職務/專案分層 ③「AI 自己維護」＝治理動作本身也能託管給 AI（呼應 [#11 自我維護](09-evolution-from-current-system.md)）。**這是整個願景最關鍵、現況覆蓋最低（約 10%）的地基。** |
| **#13** | 請假、填單等資料也都能交給他，**會議召開**也可以 | 平台從「讀知識、答問題」跨到「動真實業務系統」（HR/日曆/表單）。這是大腦的**運動神經**——有副作用、要授權、要人工確認、要稽核。 |

一句話定位：**前面幾個器官（記憶、編排、工具、攝取）讓平台「會想」；本檔讓它「能被信任地動手」，並讓「被它碰過的每一件事」都留下不可賴帳的證據。** 沒有這層，前面所有能力在企業裡都不敢上線。

> 為什麼叫「免疫系統」：免疫系統的工作不是讓身體更強，而是**辨識「自我 vs 非我」並阻止傷害**。權限治理同理——它不增加 AI 能力，而是定義「誰能讓 AI 做什麼、做了要留證」。能力越強，這層越不能省。

---

## 2. 現有方案比對表

> 數字會過時，皆附來源 URL。

### 2.1 多租戶隔離 / 檢索期存取控制 / RBAC+SSO / 稽核

| 機制 | 做法 | 強制層級 | 合規對應 | 可仿效 | 來源 URL |
|---|---|---|---|---|---|
| **多租戶 RAG：store-per-tenant** | 每租戶一個獨立向量庫 | 物理隔離（最強） | 資料邊界天然清楚 | 對應我們的 `personal:{user}`（近 per-tenant） | [Azure secure multitenant RAG](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/secure-multitenant-rag) |
| **多租戶 RAG：multitenant + RLS** | 共庫，列級安全 default-deny 過濾 | 資料庫層（應用繞不過） | 成本優；**必須在 retrieval 階段過濾** | 對應 `role`（同職務共享、列級隔離） | 同上 |
| **多租戶 RAG：hybrid** | shared + multitenant + per-tenant 混用（Azure 推薦） | 混合 | 按敏感度分配隔離強度 | **直接對應 scope 四層**（global=shared／role=multitenant／personal=近 per-tenant） | 同上 |
| **檢索 ACL：Orchestrator/API 層** | 中央服務取得身份後套 filter 再查向量 | 應用層 | 稽核集中、治理統一 | 對應現有 atom 注入管線「先判 scope 再注入」的位置 | [AI gateway control plane](https://medium.com/@mausumi345/ai-gateway-the-control-plane-powering-enterprise-ai-platforms-5b78dea7d509) |
| **檢索 ACL：PostgreSQL RLS** | 資料庫列級安全策略，default-deny，**應用無法繞過** | 資料庫層（最可靠） | 「應用即使有 bug 也洩不出去」 | 真 AuthZ 的兜底層；honor-system 的解藥 | [Azure 同上](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/secure-multitenant-rag) |
| **檢索 ACL：向量 DB 內建** | Qdrant JWT access-claim payload filter／Pinecone namespace 物理分區 | 向量庫層 | 過濾在搜索內完成、不讓 LLM 見無權文檔 | LanceDB→Qdrant 後可用；ABAC/RBAC scoped 到 collection/namespace | [Securing vector DBs 2026](https://www.blockchain-council.org/ai/securing-and-governing-vector-databases-privacy-prompt-injection-multi-tenant-access-control/) |
| **Enterprise RBAC + SSO** | IdP（Okta/Azure AD）登入 → 發 JWT/SAML（claims: user_id/org_id/roles）→ Orchestrator 驗簽取 claims → Data Access Layer 套 filter → 向量搜索帶 filter → 稽核 | 身份在 IdP、決策在 Orchestrator | 權限決策**不在 prompt**、可獨立稽核 | 把現有 honor-system 的 `_roles.md` 換成 IdP group claim | [AI gateway 同上](https://medium.com/@mausumi345/ai-gateway-the-control-plane-powering-enterprise-ai-platforms-5b78dea7d509) |
| **不可竄改稽核** | 每個動作以外部金鑰簽章、簽章串鏈、收據存於 agent 信任邊界外（append-only/WORM） | 密碼學 + 儲存層 | EU AI Act 證據力前提 | JSONL audit 的升級目標 | [EU AI Act logging](https://www.helpnetsecurity.com/2026/04/16/eu-ai-act-logging-requirements/) · [PredictionGuard 工具](https://predictionguard.com/blog/best-eu-ai-act-compliance-tools-for-enterprise-ai-programs-in-2026) |

> ⚠️ **關鍵共識（多份來源一致）**：AI Gateway 本身**不**強制 vector DB 內的 document-level 權限——「document-level ACL/RBAC remains inside the vector store or search engine」（[Securing vector DBs 2026](https://www.blockchain-council.org/ai/securing-and-governing-vector-databases-privacy-prompt-injection-multi-tenant-access-control/)）。亦即：**閘道擋外圍、但租戶/文檔級隔離一定要落在資料層（RLS / payload filter）**。這正是 [記憶共享皮層](01-memory-as-shared-cortex.md) §4 反覆強調的「注入過濾≠存取控制」。

### 2.2 AI Gateway 架構（控制平面）

業界 2026 已收斂出「AI Gateway = 控制平面」範式，把治理從各應用拉到統一入口（Gartner 2025-10 發首份 AI Gateway Market Guide，預估 2028 年 70% 多模型團隊會用 Gateway — [TrueFoundry](https://www.truefoundry.com/blog/best-ai-gateway)）：

```
Control Plane（SSO/JWT + RBAC + rate limit/quota + PII 偵測遮罩
              + prompt injection 防禦 + model routing + 成本追蹤）
   → Orchestration（任務分解，見 02）
   → Knowledge（Qdrant + RBAC/ABAC + tenant_id + 不可竄改 audit）
   → LLM（+ inference logging）
   → 後處理（PII 遮罩 + citation + confidence + audit 簽章 + retention）
```

統一稽核日誌應涵蓋六類事件並各自帶簽章與 retention：**identity（誰）/ inference（用了哪個模型）/ retrieval（讀了哪些文檔）/ compliance（觸發哪條政策）/ output（回了什麼、遮了什麼）/ audit（簽章鏈）**。對應願景的「派誰」見 [模型路由](03-model-routing.md)、「治理知識」見 [記憶共享皮層](01-memory-as-shared-cortex.md)。

### 2.3 業務流程自動化 connector（#13）

| 能力 | 業界做法 | 成熟度（2026） | 可仿效 | 來源 URL |
|---|---|---|---|---|
| 請假 / PTO / 填單 | connector 接 Workday/ERP/ITSM，agent 規劃步驟→填單→路由審批 | **成熟**：PTO、onboarding、expense routing 已是 agentic 平台標配 | connector + 工作流引擎 + 審批路由 | [Sana enterprise agents 2026](https://sanalabs.com/agents-blog/ai-agents-for-automating-work-enterprise-guide-2026) · [HR automation 2026](https://www.elementum.ai/blog/hr-process-automation-tools) |
| 人工介入審批 | **HITL（human-in-the-loop）**：AI 執行、人在關鍵決策點 review/approve | 業界共識「scalable + trustworthy 的平衡點」 | 高權限/有副作用的動作**強制**人工確認（複用現有 pending review 範式） | [Sana 同上](https://sanalabs.com/agents-blog/ai-agents-for-automating-work-enterprise-guide-2026) |
| 會議召開 | 接日曆（Google/Outlook）connector，自動找空檔→建會議→發邀請 | 成熟 | connector + 日曆 API + 衝突偵測 | [AI workflow trends 2026](https://www.cflowapps.com/ai-workflow-automation-trends/) |
| 治理效益 | 「含 audit trail + HITL 的部署，合規事件減少 up to 73%」 | 廠商宣稱數字 **(推測：須回原始口徑復核，[記憶皮層](01-memory-as-shared-cortex.md) §2 同款警告)** | 證明 audit + HITL 是 connector 的必要配套，不是選配 | [Sana 同上](https://sanalabs.com/agents-blog/ai-agents-for-automating-work-enterprise-guide-2026) |

### 2.4 EU AI Act（高風險 AI，2026-08-02 生效）

| 條文 | 要求 | 對平台的設計含意 | 來源 URL |
|---|---|---|---|
| **Article 12** 記錄保存 | 系統須**自動記錄**全生命週期事件（風險情境/上市後監控/運作監控三類） | 平台所有 AI 動作（檢索、推論、connector 操作）都要自動落 log | [Article 12 原文](https://artificialintelligenceact.eu/article/12/) · [Help Net 解讀](https://www.helpnetsecurity.com/2026/04/16/eu-ai-act-logging-requirements/) |
| **Article 13** 文件 | deployer 須得到「如何收集/解讀 log」的指引 | 稽核 log 要有 schema 文件、可被獨立解讀 | [Help Net 同上](https://www.helpnetsecurity.com/2026/04/16/eu-ai-act-logging-requirements/) |
| **Articles 19 & 26** 保留 | log **至少保留 6 個月**（生物辨識/執法類 24 月；金融可併入既有監管文件） | retention 政策按租戶/類別設定 | [Help Net 同上](https://www.helpnetsecurity.com/2026/04/16/eu-ai-act-logging-requirements/) |
| **Article 14** 人工監督 | 高風險 AI 須可被人工介入/否決 | = HITL；對應 #13 的審批確認 | [PredictionGuard](https://predictionguard.com/blog/best-eu-ai-act-compliance-tools-for-enterprise-ai-programs-in-2026) |
| **Article 21** 配合稽核 | 須提供主管機關 log 與符合性文件 | log 要可匯出、機關可讀格式 | [Help Net 同上](https://www.helpnetsecurity.com/2026/04/16/eu-ai-act-logging-requirements/) |

> **稽核「有證據力」的三條件**（[Help Net Security](https://www.helpnetsecurity.com/2026/04/16/eu-ai-act-logging-requirements/) 強調）：① **不可竄改**——條文沒明寫「tamper-proof」，但「可被靜默修改的 log 對監管者零證據力」；做法是每動作用**外部金鑰簽章 + 簽章串鏈 + 收據存於 agent 信任邊界外**。② **獨立**——簽章金鑰必須在 agent 信任邊界**之外**，杜絕自我竄改。③ **保留**——6 月以上、機關可讀格式。罰則上看 €15M 或全球營業額 3%。
> 註：Annex III 義務 2026-08-02 生效，惟可能因 EU Digital Omnibus 延至 2027-12 **(推測：以官方最終公告為準)**。

---

## 3. 推薦設計取捨

### 3.1 優選骨架

```
登入：員工 → 企業 AD/Okta（SSO）→ IdP 發 JWT（claims: user_id / dept / role / project）
授權：query + JWT → Orchestrator 驗簽取 claims → Data Access Layer 組 filter
存取：PostgreSQL RLS（default-deny，DB 強制） + Qdrant JWT payload filter（檢索層）
動作：connector 操作（請假/填單/會議）→ 高權限走 HITL 人工確認 → 執行
留證：每動作 append-only + 外部金鑰簽章 + 串鏈 → 6 月+ retention（可機關匯出）
```

> 薄框架原則（USER.md 偏好）：權限決策落在**能自審的 PostgreSQL RLS + 自建 Orchestrator filter**，而非黑箱 SaaS Gateway；先讓開發者看得懂底層，再談買現成 Gateway 省事。

### 3.2 關鍵取捨（分析表）

| 取捨點 | 選項 A | 選項 B | 建議 | 理由 |
|---|---|---|---|---|
| 真權限強制點 | 純 Orchestrator/API 層過濾 | PostgreSQL RLS 兜底 | **RLS 為主 + API 為輔** | 純 API＝信任應用不出 bug（＝現況弱點）；RLS「應用繞不過」才是真 AuthZ |
| 租戶隔離模型 | 全 store-per-tenant | 全 RLS 共庫 | **hybrid（對齊 Azure 與現有 scope 四層）** | 按敏感度分配隔離強度：高敏感 per-tenant、一般 role 共庫 RLS、公共 global |
| 稽核不可竄改 | append-only 檔案 | 外部簽章 + 串鏈 | **外部簽章串鏈（金鑰在信任邊界外）** | EU AI Act 證據力前提；現有 JSONL 本機可改＝無證據力 |
| connector 動作授權 | 全自動執行 | 高權限走 HITL | **混合：唯讀/低風險自動、寫入/有副作用走 HITL** | 直接照搬現有「敏感類→管理職裁決」成功範式 |
| 信任根（簽章/IdP） | 自簽 CA | 企業 IdP + HSM/KMS 管私鑰 | **企業 IdP 起步，私鑰進 HSM/KMS** | 內網單一信任域；私鑰外洩=信任體系崩，須硬體保護 + 輪替 |

### 3.3「涵蓋系統部達權限控管」的分層設計（#6 核心）

願景要「涵蓋系統部」＝權限要能沿**組織結構**切。建議三軸交叉，全部落在 JWT claims + RLS policy，不靠應用自律：

| 軸 | 對應 claim | 範例 RLS 效果 | 對應現有 scope |
|---|---|---|---|
| **部門（dept）** | `dept=系統部 / 美術部 / PM` | 系統部 atom 只系統部可檢索 | 接近 `role`（但按部門非職務） |
| **職務（role）** | `role=programmer / management / QA` | 管理職可裁決 pending、QA 看測試知識 | 直接對應現有 `role:{name}` |
| **專案（project）** | `project=A / B` | 專案 A 成員看不到專案 B 機密 | 對應 realm 的「租戶/專案邊界」演化（見 [01](01-memory-as-shared-cortex.md) §4.1） |

> 一句話：**現有 scope 四層提供了「分層的語意」，但要「涵蓋系統部」必須把這些軸變成 IdP claim + DB RLS policy 的笛卡兒組合，並且 default-deny**——沒明確授予就看不到，而非「沒禁止就看得到」。

---

## 4. ★落地切入點

**核心洞察：治理的「形」現有系統已意外齊備（scope/裁決/守衛/稽核/自癒五件套），但每一件的「實」都差一截——差在「honor-system→真強制」「可改→不可竄改」「注入過濾→存取控制」。本檔的工作不是從零造治理，而是把這五件「形似」升級成「實至」。**

### 4.1 治理「形」已具：現有五件套盤點

| 現有零件 | 治理的「形」 | 缺的「實」 | 判定 |
|---|---|---|---|
| **scope 四層** global/shared/role/personal | 分層作用域語意 | 只是「注入過濾」、能讀檔即能讀全部 | 🟡 形似：語意可留，**強制過濾必新建** |
| **管理職雙向認證** personal `role.md` 自宣告 + shared `_roles.md` 白名單 | 「角色要雙向登記」的概念 | **honor-system**：無加密、無真 AuthN，**能改白名單就能提權** | 🟡 形似：概念對，**真 AuthN 必新建** |
| **敏感類 auto-pending review**（architecture/decision → 管理職 `/conflict-review` 裁決） | 「高敏感動作要人工裁決」的工作流 | 對象是 atom（知識），未涵蓋 connector 動作 | ✅ **能用（須平移）**：HITL 範式直接套到 #13 高權限操作 |
| **cross-realm write guard**（外部專案禁寫核心層 / 禁汙染全域 MCP 配置） | 「跨邊界寫入要擋」的權限分層雛形 | 只擋寫入路徑，非檢索/讀取存取控制 | 🟡 形似：邊界意識在，**讀取側 ACL 必新建** |
| **JSONL audit trail** | 留下動作紀錄 | **本機可被改**＝零證據力 | 🟡 形似：欄位可留，**外部簽章串鏈必新建** |
| **Evasion Guard（反退避）+ Codex Companion（GPT 第二意見審計）** | 「AI 行為要被獨立監督」的概念 | 監督的是 AI 自身行為品質，非企業權限 | ✅ **能用（概念可遷移）**：第二意見審計＝合規 review 的雛形 |
| **atom-heal（L1 機械補連結／L2 LLM 提案修／L3 喚醒）+ Wisdom Engine 反思 + docdrift** | **「AI 自己維護」的雛形**（#6 後半） | 限記憶層自癒，未到服務層自維運/權限自維護 | ✅ **能用（可長大）**：是 #6「AI 自維護」最具體的種子，詳見 [演進](09-evolution-from-current-system.md) |

### 4.2 能用 vs 必新建（誠實標注）

| 能力 | 狀態 | 說明 |
|---|---|---|
| HITL 裁決工作流 | ✅ **能用（須平移）** | pending review→管理職裁決，從治理 atom 平移到治理 connector 動作 |
| 「AI 自維護」雛形 | ✅ **能用（可長大）** | atom-heal / Wisdom / docdrift 是 #6 自維護的種子 |
| 第二意見審計範式 | ✅ **能用（概念遷移）** | Codex Companion 的「獨立審計」可長成合規 review gate |
| 分層作用域語意 | 🟡 **半成品** | scope/realm 有語意，無 DB 強制 |
| **真 AuthN（SSO/LDAP/OIDC/JWT）** | 🔴 **必新建** | 現況 honor-system，改檔即提權 |
| **真 AuthZ（檢索期強制過濾）** | 🔴 **必新建** | scope=注入過濾，須 RLS + payload filter |
| **at-rest 加密** | 🔴 **必新建** | 明文 `.md` 散落硬碟 |
| **不可竄改稽核（外部簽章串鏈）** | 🔴 **必新建** | JSONL 本機可改 |
| **業務流程 connector（HR/日曆/表單）** | 🔴 **必新建** | 現況 0%，無任何公司系統 connector |

> 與 [記憶共享皮層](01-memory-as-shared-cortex.md) §4 的硬骨頭清單高度重疊——**因為 #6 的權限地基，本質上就是把記憶層的 AuthN/AuthZ/加密/稽核做對**。本檔多出來的獨立工作是 §2.3 的 connector 與 §3.3 的組織分層。最小可行起步 (推測)：先接一個唯讀 connector（如查日曆空檔）跑通「JWT→Orchestrator filter→connector→簽章 audit」全鏈，**先不接寫入操作**，驗證治理鏈順了，再加請假/填單這類有副作用、需 HITL 的動作。演進全圖見 [從現有系統如何長出來](09-evolution-from-current-system.md)。

---

## 5. 已知風險 / 紅線 / 待驗證假設

| 類別 | 項目 | 說明 / 緩解 |
|---|---|---|
| 🔴 紅線 | **權限洩漏＝災難** | 私有溝通平台一旦無權者讀到他人/他部門機密，傷害不可逆。**default-deny + RLS 兜底**，絕不只靠應用標對 id（Mem0 式四維隔離標錯即洩漏，見 [01](01-memory-as-shared-cortex.md) §5） |
| 🔴 紅線 | **稽核被竄改＝零證據力** | 「可靜默修改的 log」對監管者無價值。必須外部金鑰簽章 + 串鏈 + 收據存於 agent 信任邊界外；私鑰進 HSM/KMS + 輪替 |
| 🔴 紅線 | **connector 有副作用＝可造成真實後果** | AI 誤發請假/誤召會議/誤填表單是真實業務事故。**寫入類動作一律 HITL 人工確認**，且每步可審計、可回溯、可撤銷（推測：需設計 compensating action） |
| 🔴 紅線 | **prompt injection** | 員工或文檔內藏惡意指令誘導 AI 越權操作 connector 或洩密。Gateway 層 injection 偵測 + 權限決策**不在 prompt**（在 Orchestrator/RLS，prompt 改不動授權） |
| 🟡 風險 | **PII / 個資** | 請假/填單含個資；檢索/輸出須 PII 偵測遮罩（Gateway 標配能力）；retention 政策按法規分租戶設定 |
| 🟡 風險 | **honor-system 的過渡期假象** | 服務化後若仍用 scope 當權限，等於把君子協定搬上伺服器、給人「有權限」的錯覺（見 [01](01-memory-as-shared-cortex.md) §5）。AuthZ 沒落 DB/檢索層前，不可宣稱「已權限控管」 |
| 🟡 風險 | **「AI 自維護」的權限邊界** | #6 要「AI 自己維護」，但 AI 自維護治理規則 = AI 能改自己的權限？**自維護必須限縮在 default-deny 內、且改權限類動作強制 HITL + 簽章**，否則自維護變自我提權後門 |
| 🟡 風險 | **員工監控的合規界線** | #13 記錄員工請假/會議＝個人行為資料。須區分「業務必要」vs「監控」，落 retention/最小化/知情同意；EU AI Act 對「員工管理」類 AI 另有高風險認定 (推測：須法務確認適用範圍) |
| ❓ 待驗證 | HITL 範式從 atom 平移到 connector 的程度 | 假設「pending review 程式骨架能套 connector 動作」。connector 有外部副作用、時效性（會議時間）、不可逆性，比 atom 純資料複雜，平移時可能需實質擴充而非換對象 |
| ❓ 待驗證 | RLS 在組織三軸交叉 policy 的延遲 | dept×role×project 笛卡兒組合的 RLS policy 可能讓查詢計畫退化；須在目標規模壓測 p95/p99（與 [01](01-memory-as-shared-cortex.md) §5 同款待驗證） |
| ❓ 待驗證 | EU AI Act 生效日與適用範圍 | Annex III 2026-08-02 生效，可能延至 2027-12；本平台是否落入「高風險」分類取決於用途。以官方最終公告 + 法務判定為準 (推測) |

---

> 互引：身份權限的記憶層做法 [記憶共享皮層](01-memory-as-shared-cortex.md)｜誰來指揮這些受治理的動作 [編排核心](02-orchestration-core.md)｜「派哪個模型」的成本/路由 [模型路由](03-model-routing.md)｜connector 與工具的上架治理 [工具註冊](04-tool-registry-and-protocols.md)｜「AI 自維護」如何從現有自癒長大 [從現有系統如何長出來](09-evolution-from-current-system.md)｜回 [README](README.md)

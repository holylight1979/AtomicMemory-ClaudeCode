# 工具認證註冊與互通協定 — 開發完→簽章註冊→他人共享

> 所屬：[JARVIS 企業 AI 平台發想](README.md) · 對應願景 #5

---

## 1. 對應願景需求

**#5**：「主動擴充支援功能、可共享知識 & 工具：根據需求提供 UnityMCP / Unreal / Excel 編輯 / 文檔產出 等工具；只要工具在**客戶端開發完成**、**自主交給伺服器分類認證且註冊**後，**他人就能使用**。」

關聯 **#11**（自我維護與擴展）——工具上架是「平台自我擴展」最具體的入口：今天某個程式設計師寫了一個 Unreal 場景批改工具，明天美術、PM、QA 都能直接呼叫，平台的能力面就被使用者自己撐大了。

一句話拆解這條需求成三段生命週期：

```
[客戶端開發] → [伺服器：分類 → 認證 → 註冊 → 相容/權限] → [中央分發] → [他人發現並使用]
   個人寫工具          ←—— 這一整段是現在完全缺的「工具治理層」——→        共享
```

現況覆蓋約 **5%**：所有 MCP server 各自在 `settings.json` / `.claude.json` 手動配置，**沒有中央註冊、沒有認證、沒有分發**。願景的「自主交給伺服器」是這條的核心動詞，而它正是缺口所在。

> 定位提醒：本檔是 [README](README.md) 「三層棧」中**第二層（agent↔工具）**的治理。第一層（agent↔agent）見 [編排核心](02-orchestration-core.md)；第三層（治理知識）就是原子記憶系統本身，見 [記憶作為共享皮層](01-memory-as-shared-cortex.md)。模型側的「派誰」見 [模型路由](03-model-routing.md)。

---

## 2. 現有方案比對表

> 數字會過時，皆附來源 URL。查證時點：2026-06-26。

| 協定 / 註冊中心 | 解決什麼 | 認證 / 簽章 / 分發機制 | 成熟度與採納 | 可仿效 | 來源 |
|---|---|---|---|---|---|
| **MCP（Model Context Protocol, Anthropic）** | agent↔工具的傳輸/介面標準（tool / resource / prompt） | 協定本身不管認證；交給傳輸層（stdio 本機信任、HTTP+OAuth） | 事實標準；excel / playwright / workflow-guardian 都是 MCP server | 工具**介面層**直接沿用，不重造 | [modelcontextprotocol.io](https://modelcontextprotocol.io/registry/about) |
| **官方 MCP Registry**（Anthropic+GitHub+Microsoft+PulseMCP） | 公開 MCP server 的中央**目錄 + 發現 API**（像 app store） | **reverse-DNS namespace 認證**：`io.github.user/srv`、`com.example/srv` 綁定已驗證的 GitHub 帳號或網域，只有 namespace 擁有者能發布 | 2025-09 預覽上線，REST API（`/v0/servers`）；preview 期可能有破壞性變更 | 「namespace=信任根」直接對應企業內部 LDAP/SSO 身份綁定；REST 發現 API 可內網私有化 | [registry.modelcontextprotocol.io](https://registry.modelcontextprotocol.io/docs) · [blog 2025-09-08](https://blog.modelcontextprotocol.io/posts/2025-09-08-mcp-registry-preview/) |
| **MCP Gateway & Registry**（agentic-community / Cisco 系） | 把分散 MCP server 變成 governed/auditable 的統一入口 | **OAuth 2.0/OIDC**（Keycloak/Entra/Okta/Auth0/Cognito）+ M2M client credentials + **Dynamic Client Registration**（Claude Code/Cursor 可自註冊）；上架走 **draft→approved→active/deprecated** 生命週期；註冊時**自動安全掃描**（Cisco AI Defense）；ANS/**PKI 信任徽章**；audit log 自動遮罩憑證 | 開源、活躍；含語意搜尋（向量+關鍵字 RRF）、access-scoped 結果 | **這就是 #5 的近乎成品藍圖**：OAuth 上架認證 + 動態發現 + 審計 + draft→approved 裁決流，幾乎一一對應我們的 atom funnel 範式 | [github.com/agentic-community/mcp-gateway-registry](https://github.com/agentic-community/mcp-gateway-registry) |
| **Google Cloud Agent Registry** | 雲端託管的 agent / MCP server 註冊與治理 | 走 GCP IAM；可註冊並託管 MCP servers | 商業雲服務 | 「託管式 registry」的對照組；自建 vs 買的決策參考 | [docs.cloud.google.com/agent-registry](https://docs.cloud.google.com/agent-registry/overview) · [register-mcp-servers](https://docs.cloud.google.com/agent-registry/register-mcp-servers) |
| **A2A（Agent2Agent, Linux Foundation）** | agent↔agent **跨組織**協調協定（不是工具層） | Agent Card 宣告能力；跨組織信任靠各家 IdP；不含工具簽章 | **150+ 組織**（AWS/Cisco/Google/IBM/MS/Salesforce/SAP/ServiceNow）；22k+ GitHub stars；5 種語言 SDK；供應鏈/金融/保險/IT ops production | 「能力廣播」格式可借：工具上架後以 Agent-Card-style capability 對 agent 群播 | [linuxfoundation.org 公告](https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year) |
| **AGNTCY Agent Directory Service（Cisco→Linux Foundation）** | content-addressed、**OCI-aligned** 去中心化目錄 | **SHA-256 content addressing**（digest 即不可竄改 ID）+ **Sigstore 簽章** + OCI artifact 封裝 + **DHT（Kademlia）** rendezvous 做 provider 發現 | 研究/草案階段（IETF draft-mp-agntcy-ads）；參考 IPFS/OCI 既有基礎 | **這是「簽章認證+不可竄改註冊+發現」的現成設計**：digest 當版本指紋、Sigstore 當信任根 | [arxiv 2509.18787](https://arxiv.org/pdf/2509.18787) · [docs.agntcy.org/dir](https://docs.agntcy.org/dir/overview/) |
| **AI Agent Registry 治理綜述** | registry 生命週期的學術歸納 | 歸納 centralized / enterprise / distributed 三種路線的權衡 | arxiv 綜述 | 幫我們**選路**：企業內部 = enterprise（中心化+權限）路線，而非公開 distributed | [arxiv 2508.03095](https://arxiv.org/html/2508.03095v3) |

> **2026 收斂洞察**：業界已收斂成三層棧 = **A2A（agent 協調）+ MCP（agent-工具）+ shared context layer（治理業務知識）**。我們的原子記憶系統定位 = 第三層治理知識層；本檔處理的工具註冊 = 第二層的「上架治理」。A2A 與 MCP 官方都已明確表態二者互補而非競爭（[Linux Foundation 公告](https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year)）。

---

## 3. 推薦設計取捨

### 3.1 分層選型（不重造輪子）

| 層 | 職責 | 優選 | 理由 |
|---|---|---|---|
| 工具**介面** | 工具怎麼被呼叫 | **MCP** 原樣沿用 | 已是事實標準，現有 excel/playwright/workflow-guardian 都已是 MCP，零遷移成本 |
| 工具**上架認證** | 誰能發布、發布要過什麼門 | **Gateway/Registry 範式**（OAuth + draft→approved + 安全掃描） | agentic-community 已驗證；對應我們現成的 atom funnel 裁決流（見 §4） |
| 工具**簽章版本** | 內容不可竄改、版本可追溯 | **AGNTCY-style**：SHA-256 content-addressed digest + Sigstore 簽章 | digest 即版本指紋，杜絕「同名工具被偷換內容」的供應鏈攻擊 |
| 工具**能力廣播** | 工具上架後 agent 怎麼知道有它 | **A2A-style** capability card + registry 推送 | 讓 [編排核心](02-orchestration-core.md) 的 manager 動態看到新工具 |
| 工具**發現** | 使用者/agent 怎麼找到工具 | 中心化 **REST + 語意搜尋**（企業 enterprise 路線，非 DHT） | 內網場景中心化即可，DHT 是跨組織去中心化才需要的複雜度（推測：公司內不值得） |

### 3.2 工具上架生命週期設計

```
①開發            ②提交              ③分類             ④認證              ⑤註冊            ⑥分發           ⑦使用
client 端    →   push manifest  →  自動歸類      →  簽章+掃描       →  digest 入庫   →  能力廣播    →  他人呼叫
（MCP server）   （含元資料）       （工具域/角色）   （信任根驗身份）    （不可竄改版本）   （A2A card）    （權限過濾後可見）
                       ↓ 敏感類（高權限/寫檔/外連）
                  pending review → 管理職裁決（approve/reject）
```

| 階段 | 必做檢查 | 對照現有零件 |
|---|---|---|
| ②提交 | manifest schema 驗證（name/version/scopes/inputs） | atom_write 的 schema 驗證 |
| ③分類 | 自動判工具域（World/Tools/3D…）+ 適用角色 | realm 分類引擎（core/local 三問） |
| ④認證 | 發布者身份（SSO/namespace）+ 安全掃描 + 簽章 | check-bypass 靜態掃描 + 管理職認證 |
| ⑤註冊 | content digest 去重 + 版本鏈 + 衝突偵測 | atom 去重 + 衝突偵測 |
| ⑥分發 | 推送到 client 可發現的中央索引 | （新建：現在 git pull 同步不夠即時） |
| ⑦使用 | **retrieval 時權限過濾**（無權者根本看不到） | ⚠️ 現在 scope 只是「注入過濾」非「存取控制」，須補（見 [01](01-memory-as-shared-cortex.md)） |

### 3.3 關鍵取捨（分析表）

| 取捨點 | 選項 A | 選項 B | 建議 | 理由 |
|---|---|---|---|---|
| registry 形態 | 中心化（enterprise） | 去中心化（DHT/AGNTCY） | **中心化** | 公司內網單一信任域，DHT 的去中心化是跨組織才划算（推測） |
| 信任根 | 自簽 CA / namespace | 外部 Sigstore | **內部 namespace+SSO** 起步，digest 借 AGNTCY 概念 | 內網不需公開透明日誌；但 digest 不可竄改要學起來 |
| 上架門檻 | 全自動掃描放行 | 敏感類人工裁決 | **混合**：低風險自動、高權限/寫檔/外連走 pending review | 完全照搬現有 atom 敏感類→管理職裁決的成功範式 |
| 工具發現 | 靜態清單 | 語意搜尋 | **語意搜尋** | Gateway 已證可行；與向量記憶庫同一套 embedding 基礎設施 |

---

## 4. ★落地切入點

**核心洞察：我們已經有一套「工具上架認證」的範式，只是它現在治理的對象是 atom（知識），把它平移到治理 tool（工具）即可。** atom funnel 與 tool registry 的同構關係：

| atom 知識治理（已存在、運轉中） | → | tool 工具治理（願景 #5、待建） |
|---|---|---|
| `lib/atom_io.py` 唯一寫入入口 | → | 工具上架唯一入口（單一 publish API） |
| PreToolUse gate 強制走 funnel | → | gate 強制：未經註冊的工具不可被 agent 載入 |
| JSONL audit trail | → | 上架/呼叫審計（Gateway 已示範憑證遮罩） |
| 衝突偵測（同名/矛盾 atom） | → | 工具版本衝突 / 同名覆蓋偵測 |
| pending review（敏感類→管理職裁決） | → | 高權限工具上架→管理職 approve/reject |
| `check-bypass.py`（掃白名單外寫入點） | → | 掃「繞過 registry 直接配 MCP」的旁路 |
| realm 分類器（core/local 三問、預設安全） | → | 工具自動分類（工具域/適用角色，預設最小權限） |
| cross-realm guard（外部專案禁汙染全域 MCP 配置） | → | 已有的「禁汙染全域 MCP 配置」就是工具治理的雛形權限分層 |

### 能用 vs 必新建（誠實標注）

| 能力 | 狀態 | 說明 |
|---|---|---|
| 工具介面標準 | ✅ **能用** | MCP 已是現況，excel/playwright/workflow-guardian 三個現成被治理對象 |
| 單一入口 + gate + 審計 + 裁決範式 | ✅ **能用（須平移）** | atom funnel 的程式模式完整可借，換治理對象即可 |
| 權限分層意識 | 🟡 **半成品** | cross-realm guard 已有「禁汙染全域配置」概念，但只是注入層、非存取控制 |
| **中央 registry（DB + 發現 API）** | 🔴 **必新建** | 現在 MCP 全靠手動配 settings.json，無中央目錄 |
| **簽章 / content digest / 版本鏈** | 🔴 **必新建** | 現在無任何工具完整性驗證 |
| **即時分發**（client 自動發現新工具） | 🔴 **必新建** | 現況 git pull 同步太慢、非工具場景設計 |
| **發布者身份（SSO/namespace 認證）** | 🔴 **必新建** | 管理職認證目前是「君子協定」，見 [安全治理](08-security-governance-compliance.md) |

> 最小可行起步（推測）：先把現有三個 MCP server 灌進一個本機 SQLite registry + 一支 publish CLI（複用 atom_io 的 funnel 程式骨架），跑通「分類→pending review→註冊→list」閉環，**先不做簽章與即時分發**——驗證治理流程順了，再補密碼學與分發。演進全圖見 [從現有系統如何長出來](09-evolution-from-current-system.md)。

---

## 5. 已知風險 / 紅線 / 待驗證假設

| 類別 | 項目 | 說明 / 緩解 |
|---|---|---|
| 🔴 紅線 | **惡意工具供應鏈** | 上架工具能讀檔/外連/執行碼，一個惡意工具 = 全公司 RCE。**必須**安全掃描（Cisco AI Defense 範式）+ 簽章 + 最小權限 default-deny，不可只靠人工 review |
| 🔴 紅線 | **簽章信任根** | 內部自簽 CA 一旦私鑰外洩，整個信任體系崩。須 HSM/KMS 管私鑰 + 金鑰輪替；digest 不可竄改是第二道防線 |
| 🔴 紅線 | **權限是存取控制、不是注入過濾** | 沿用現況「scope=注入過濾」的錯誤會讓無權者仍能列出/呼叫工具。retrieval/list 時就要過濾，見 [01](01-memory-as-shared-cortex.md) §權限 |
| 🟡 風險 | **協定仍在收斂** | MCP Registry 仍 preview、可能破壞性變更；AGNTCY/ADS 仍 IETF draft。押注太早可能要重寫 → 介面層抽象包一層，別讓上層直接耦合特定協定版本（推測） |
| 🟡 風險 | **版本相容地獄** | 工具 v1→v2 改了 input schema，舊 agent 呼叫炸。須語意化版本 + 相容性宣告 + registry 擋不相容呼叫 |
| 🟡 風險 | **中心化 registry 單點** | 中央目錄掛 = 全公司工具不可用。須高可用 + client 端快取（離線仍能用已快取工具，呼應 [README](README.md) P0「client 仍可離線快取」） |
| ❓ 待驗證 | 中心化 vs DHT 的選擇 | 假設「公司內網中心化足矣、不需 DHT」。若未來跨子公司/跨組織共享，假設失效，可能要回頭看 AGNTCY 去中心化路線（推測） |
| ❓ 待驗證 | atom funnel 範式可平移程度 | 假設「治理 atom 的程式骨架能直接套治理 tool」。tool 的執行語意比 atom 的純資料複雜（有副作用、有權限上下文），平移時可能需要實質擴充而非單純換對象 |

---

> 互引：上層協調 [編排核心](02-orchestration-core.md)｜下層知識治理 [記憶作為共享皮層](01-memory-as-shared-cortex.md)｜身份權限地基 [安全治理](08-security-governance-compliance.md)｜演進路徑 [從現有系統如何長出來](09-evolution-from-current-system.md)｜回 [README](README.md)

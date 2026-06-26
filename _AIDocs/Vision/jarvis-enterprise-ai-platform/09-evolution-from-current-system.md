# 從現有原子記憶系統長成平台 — 落地切入點與演進路線圖
> 所屬：[JARVIS 企業 AI 平台發想](README.md) · 對應願景 #11 #14 + 綜合

> **本檔立場**：屬 `_AIDocs/Vision/` 發想層，以「說不定某天會真的拿出來做」的可執行設計參考書寫，非空想。本檔是 [README 演進路徑](README.md) 的詳細展開，也是 [01](01-memory-as-shared-cortex.md)–[08](08-security-governance-compliance.md) 各檔「落地切入點」一節的**總整合**——把所有遠大目標釘回「現在的程式碼裡，從哪個檔／哪個機制開始改」。前瞻判斷標 (推測)；架構模式附來源 URL（會過時，以原始出處為準）。查證時點：2026-06-26。

---

## 1. 對應願景需求（為何本檔是總整合）

| # | 願景需求原文 | 與本檔的關係 |
|---|------------|------------|
| **#11** | 架構具備**自我維護與擴展能力** | 現有 `atom-heal`／`Wisdom Engine`／`docdrift` 已是**記憶層自維護**的種子，但只到記憶層；要長成平台得擴到**服務層自維運**（部署／健康監控／自動擴容／跨客戶端版本升級協調）。§4 專論。 |
| **#14** | 可串接**手機 APP**，但**核心作業還是必須放在電腦** | 這是一條 client-server 切分線：手機 thin client 只做 I/O／通知／輕查詢，重運算與記憶留桌面／伺服器。§5 專論。 |
| **綜合** | #1–#16 全部 | 前八檔各自談「某一個器官」怎麼長；本檔談「**這些器官按什麼順序、用哪些現有零件、踩哪些不可逆點長出來**」。它不引入新主題，只把落地結論排成一張可執行的路線圖。 |

一句話定位：**前八檔回答「要長成什麼」，本檔回答「從現在這套程式碼怎麼開始長、哪些先哪些後、哪些一旦做了回不去」。** 這是整份發想最有實作價值的一檔——因為它拒絕空想，只認「現在的 `atom_io.py` / `server.js` / `config.json` 裡，第一刀切哪」。

> 為何強調「演進」而非「重寫」：現有系統在**個人單機**這個範疇已做到天花板（信任分級、效用閉環、衝突偵測、遺忘、反退避）。這些是護城河（§6），重寫必然丟失。正確姿勢是**絞殺者模式（Strangler Fig）**——在舊系統外圍包一層門面，逐塊把功能挪到新服務，舊零件「被慢慢勒住」而非「被一次砍掉」（[Martin Fowler, StranglerFigApplication](https://martinfowler.com/bliki/StranglerFigApplication.html)；[Azure Strangler Fig Pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/strangler-fig)）。

---

## 2. 現有系統「能用 vs 必新建」總盤點表

> 把 [01](01-memory-as-shared-cortex.md)–[08](08-security-governance-compliance.md) 各檔的落地結論整合成一張大表。判定沿用各檔口徑：✅ 能用（可長大／須平移）｜🟡 形似（語意可留、強制必新建）｜🔴 必新建（現況沒有）。**現有零件引真實檔名／機制**，不誇大。

| 能力面向 | 現有零件（可長大） | 必新建 | 判定 | 對應子檔 |
|---|---|---|---|---|
| **作用域語意** | `scope` 四層 global/shared/role/personal + `realm`（core/local，path 前綴推導） | 檢索期**強制過濾**（注入過濾→存取控制） | 🟡 語意能用、強制必新建 | [01](01-memory-as-shared-cortex.md) [08](08-security-governance-compliance.md) |
| **寫入閘** | `atom_io.py` funnel 唯一入口 + PreToolUse gate + Write Gate 品質閘 | 後端從「寫檔案」改「呼叫中央 store API」 | ✅ 介面留、後端改 | [01](01-memory-as-shared-cortex.md) |
| **效用閉環** | `<atom>.access.json` 遙測 + Beta-Bernoulli α/β + Wilson 下界 + λ=0.97 慢衰減 | 服務化（多人匯流時更有意義）；**可複用到「模型×任務成功率」評分** | ✅ 保留並服務化 | [01](01-memory-as-shared-cortex.md) [03](03-model-routing.md) |
| **信任分級** | [臨]→[觀]→[固] + Confirmations 門檻（≥4/≥10） | — | ✅ 直接複用 | [01](01-memory-as-shared-cortex.md) |
| **檢索排序** | trigger→BM25 in-mem(~56 atoms)→Vector fallback→ACT-R→Related-edge→Section-level→budget | BM25 in-mem **不可規模化** → 向量 DB 叢集 + 權限感知過濾 | ⚠️ 排序邏輯留、BM25 必換 | [01](01-memory-as-shared-cortex.md) |
| **真身份** | 管理職雙向認證（`role.md` 自宣告 + `_roles.md` 白名單，honor-system） | SSO/LDAP/OIDC + JWT claims | 🔴 必新建 | [08](08-security-governance-compliance.md) |
| **真權限** | scope（注入過濾）+ cross-realm write guard（擋寫入路徑） | PostgreSQL RLS（default-deny，DB 強制）+ Qdrant payload filter（讀取側 ACL） | 🔴 必新建 | [01](01-memory-as-shared-cortex.md) [08](08-security-governance-compliance.md) |
| **稽核** | JSONL audit trail（本機可改） | 外部金鑰簽章 + 串鏈 + 收據存於信任邊界外（append-only/WORM） | 🟡 欄位留、簽章必新建 | [08](08-security-governance-compliance.md) |
| **編排：執行單元** | sub-agent 並行 dispatch（同 message 多 Agent） | 任務 DAG 調度器（管依賴/進度） | ✅ 雛形可長大 | [02](02-orchestration-core.md) |
| **編排：長時程狀態** | Auto-Handoff 四層（跨 session 交接**文字** stub） | 機器可恢復的**任務狀態快照**（DB-backed，借 LangGraph checkpoint） | ✅ 雛形可長大 | [02](02-orchestration-core.md) |
| **編排：失敗重派** | Fix Escalation（retry≥2 → 6-agent 精確修正） | 抽象成通用 retry/escalate（非綁修 bug） | ✅ 須抽象 | [02](02-orchestration-core.md) |
| **編排：對抗驗收** | Codex Companion（GPT 第二意見審計）+ Stop gate（test-fail/evasion 硬閘） | 通用 acceptance gate（硬閘/對抗/HITL 分級）；審「任意交付物」 | ✅ 須平移 | [02](02-orchestration-core.md) |
| **跨 agent 記憶** | scope（注入過濾，非共享黑板）；記憶 per-project 隔離 | 任務級 shared context（blackboard）+ 跨專案讀取權 | 🔴 必新建（**強依賴 P0**） | [02](02-orchestration-core.md) |
| **模型路由** | 雙 LLM 二分 + Dual-Backend 三階段退避（=熔斷器雛形）+ 向量 fallback 鏈（=層級降級）+ 依任務挑萃取模型（=task-based 雛形） | Model Registry + Capability Scoring + `route()` 決策層 + 成本/品質旋鈕 | ✅ 雛形多、registry/scoring 必新建 | [03](03-model-routing.md) |
| **工具上架** | atom funnel「單一入口+gate+審計+pending review」範式 + MCP（excel/playwright/workflow-guardian 現成被治理對象） | 中央 registry（DB+發現 API）+ 簽章/content digest/版本鏈 + 即時分發 + 發布者身份 | ✅ 範式可平移、registry 必新建 | [04](04-tool-registry-and-protocols.md) |
| **攝取** | `read-project`（手動）+ `docdrift` + 萃取管線（quick/deep/SessionEnd）+ 衝突偵測 | GitLab connector（評估接 Orbit 開源出 MCP）+ 排程爬取 + 攝取量級分類 + 權限標記 + 跨專案分析 agent + 定期報告產生器 | ✅ 邏輯能用、來源/排程/權限必新建 | [05](05-knowledge-ingestion.md) |
| **多模態** | 本地 3090（可掛 WhisperX）+ playwright/excel 截圖 + `browse-sprites` + 萃取管線（會議摘要落 atom） | audio 擷取+STT 全棧 + 即時翻譯 pipeline + 術語庫(可落 atom) + 出圖 connector(ComfyUI) | ✅ 通道現成、全棧必新建 | [06](06-multimodal-io.md) |
| **作業紀錄** | `journal` skill（事後聚合）+ episodic atom + SessionEnd 萃取 + PostToolUse file tracking（=事件源） | OS 焦點層即時採集器 + 隱私三色分級器 + 同意儀表板 + 自動刪除政策 | ✅ 聚合層能用、採集層必新建 | [07](07-work-journal-and-activity.md) |
| **業務 connector** | 敏感類 auto-pending review（=HITL 範式） | HR/日曆/表單 connector + 流程自動化 + 生產級排程中樞 | ✅ HITL 範式平移、connector 必新建 | [08](08-security-governance-compliance.md) |
| **自維護** | `atom-heal`（L1 機械/L2 LLM 提案/L3 喚醒）+ Wisdom Engine 反思 + docdrift + 自我迭代晉升 | 服務層自維運（部署/健康監控/自動擴容/版本升級協調） | ✅ 記憶層種子可長大 | [08](08-security-governance-compliance.md) §4 · §4 本檔 |
| **跨裝置** | 純桌面（0%） | 手機 thin client + client-server 協定 + 通知通道 | 🔴 必新建 | §5 本檔 |

> **盤點的兩個結論**：① **「能用」遠多於想像**——編排、路由、工具、攝取、多模態、紀錄、自維護全有雛形零件，多數是「重組/平移」而非「從零造」。② **「必新建」高度收斂到同一個地基**——真身份、真權限、中央服務、稽核簽章，這四項在 [01](01-memory-as-shared-cortex.md) §4 與 [08](08-security-governance-compliance.md) §4 反覆出現，因為它們**本質是同一件事**：把記憶從「單機 honor-system」升級成「有權限的中央服務」。**這就是 P0。**

---

## 3. 演進路線圖 P0 → P2

> 鐵律：**不平行鋪開，有嚴格地基依賴。** 每階段標：目標 / 用哪些現有零件 / 新建什麼 / 可逆性 / 風險 / 驗收標準。各階段內部再用絞殺者模式逐刀切，舊路徑保留為 fail-open 回退（[AWS Strangler Fig](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/strangler-fig.html)）。

### P0 — 地基：記憶服務化 + 真權限

沒有它，後面全是 N 個互不相通的單機孤島（[README §A](README.md)；[02](02-orchestration-core.md) §4-2 依賴警告）。

| 項目 | 內容 |
|---|---|
| **目標** | 把 atom store 從「單機檔案 + git/svn 最終一致」抽成「**有 API 的中央服務 + 真權限**」，且保留離線快取。 |
| **用現有零件** | `atom_io.py` funnel（介面不動，後端改 API call）；scope/realm 語意；信任分級 + α/β 效用閉環（保留並服務化）；ACT-R/Related-edge/Section-level 排序邏輯；衝突偵測時機/敏感分類；管理職 `_roles.md`（換成 IdP group claim）。 |
| **新建** | 中央 atom store（PostgreSQL + pgvector 或 Mem0 server）；AuthN（SSO/OIDC + JWT）；AuthZ（PostgreSQL RLS default-deny + Qdrant JWT payload filter）；at-rest 加密；外部簽章串鏈稽核。 |
| **可逆性** | **前半可逆**：抽 funnel 後端是「加一層 API」，舊檔案路徑可留為快取/回退（fail-open）。**後半難回頭**：見 §7——一旦上多租戶真權限並做資料遷移，scope→RLS 的資料模型改動難回退。 |
| **風險** | 「注入過濾≠存取控制」這條線若沒跨過，等於把 honor-system 搬上伺服器、給人「有權限」的錯覺（[01](01-memory-as-shared-cortex.md) §5 紅線）；BM25→向量切換在 ~56 atom 小語料上品質可能不升反降（保留 BM25 fallback A/B）。 |
| **驗收標準** | (a) `atom_io.py` 走中央 API 寫入，斷網時 client 仍能讀寫本地快取、復網自動同步；(b) 無權使用者在**檢索層**就讀不到他人 personal atom（不是「沒注入」而是「查不到」），用 RLS default-deny 壓測驗證；(c) 每筆寫入有外部簽章、本機改檔被偵測；(d) 護城河零件（信任分級/α-β/遺忘/反退避）在服務化後行為不變（回歸測試）。 |

### P1 — 核心編排：編排引擎 + 模型路由器 + 工具註冊中心

| 項目 | 內容 |
|---|---|
| **目標** | 長出「前額葉」——多 agent 任務分解→指派→交付→驗收的長時程能力；動態選模；工具中央上架共享。 |
| **用現有零件** | 編排：sub-agent dispatch（執行單元）/ Auto-Handoff（狀態雛形）/ Fix Escalation（重派）/ Codex+Stop gate（驗收）/ role scope（角色邊界）。路由：雙 LLM 二分 + 三階段退避(熔斷器) + 向量 fallback 鏈 + 依任務挑模型。工具：atom funnel 範式 + 三個現成 MCP。 |
| **新建** | 編排：長時程任務狀態機（DB-backed checkpoint）+ 任務 DAG + 分派決策器（Magentic-style manager）+ 通用驗收閘 + **跨 agent shared context**（強依賴 P0）。路由：Model Registry（`config.json` 加 `models[]`）+ Capability Scoring（**複用 Wilson α/β**）+ `route()` + 成本/品質旋鈕。工具：中央 registry + 簽章/digest + 即時分發 + 發布者身份。 |
| **可逆性** | **大致可逆**：編排器、router、registry 都是「在現有零件外面包協調層」，可加 feature flag 灰度，出問題退回現況的「parent 自己 dispatch + 寫死路由 + 手動配 MCP」。Capability Scoring 種子資料是新研究問題（[03](03-model-routing.md) §4 誠實標記），失敗只是退回固定二分。 |
| **風險** | 多 agent 成本爆炸（6-agent 會議 × 長 DAG，[02](02-orchestration-core.md) §5）；編排層自己變最難 debug 的黑盒；合規路由不可被成本旋鈕覆蓋（機敏資料強制本地，硬性前置，[03](03-model-routing.md) §5 紅線）。 |
| **驗收標準** | (a) 單專案 3–5 節點線性 DAG 能跑通「分解→指派→程式化硬閘驗收→交付」，且跨 session 可從 checkpoint 恢復；(b) `route()` 對「翻譯/萃取/決策」三類任務正確選模，機敏標籤無條件走本地；(c) 一個 MCP 工具能走「分類→pending review→註冊→他 client list 到」閉環。 |

> P1 內部順序（[02](02-orchestration-core.md) §4-3 / [03](03-model-routing.md) §4 / [04](04-tool-registry-and-protocols.md) §4）：先抽象 Fix Escalation 成通用 retry/escalate（最小改動）→ Auto-Handoff 加結構化 state 副本 → 線性 DAG + 硬閘 → 才上動態分派 + shared context（此步等 P0）。路由與工具註冊可與編排並行（不互相阻塞）。

### P2 — 感官與觸手：攝取 + 多模態 + 業務 connector + 跨裝置

| 項目 | 內容 |
|---|---|
| **目標** | 讓平台「能看會聽能動手」並延伸到手機：主動彙整 GitLab、會議 STT/翻譯、出圖、業務流程自動化、手機 thin client。 |
| **用現有零件** | 攝取：read-project 邏輯 + 萃取管線 + 衝突偵測（來源從對話換 GitLab）。多模態：本地 3090 + playwright/excel 截圖 + browse-sprites + 萃取管線（摘要落 atom）。connector：pending review = HITL 範式。 |
| **新建** | GitLab connector（評估 Orbit）+ 排程爬取 + 跨專案分析 agent + 定期報告產生器；audio+STT 全棧（WhisperX/pyannote）+ 即時翻譯 pipeline + 術語庫(落 atom) + 出圖(ComfyUI)；HR/日曆/表單 connector + 排程中樞；手機 thin client + 通知通道（§5）。 |
| **可逆性** | **高度可逆**：每個感官/觸手都是獨立 connector，加減不影響核心；唯一例外是 #13 寫入類 connector（請假/填單有真實副作用，[08](08-security-governance-compliance.md) §5 紅線），必須 HITL + 可撤銷(compensating action)。 |
| **風險** | 單 3090 搶卡——即時翻譯與其他本地推理爭用同一張卡是序列硬約束（[06](06-multimodal-io.md) §4，「會議當下只轉錄、翻譯/摘要排會後」的降級方案，即時翻譯列加卡後 P2+）；跨專案分析「真能產出有用結論」是整條管線最不確定的假設（[05](05-knowledge-ingestion.md) §5，MVP 先驗）；員工監控合規界線（[07](07-work-journal-and-activity.md) §3：護欄先於擴採集，EDPB 僱傭同意常無效→定位「員工自用可關 + 管理職僅見聚合」）。 |
| **驗收標準** | (a) 對 N 個已 clone 專案跑批量攝取，產一份「重複造輪 + dead code」報告且採用率可量測；(b) 會後 WhisperX→萃取→atom 閉環跑通（非即時）；(c) 唯讀 connector（查日曆空檔）走通「JWT→Orchestrator filter→connector→簽章 audit」全鏈，寫入類才加 HITL；(d) 手機端能查 atom + 收通知，重任務確實落在桌面/伺服器執行（§5）。 |

> **跨階段地基依賴一圖**（文字版）：`P0 記憶服務化+真權限` →（解鎖）→ `P1 編排的跨 agent shared context` + `P2 攝取的權限標記` + `P2 connector 的授權稽核`。**P1/P2 凡涉及「多人共享同一份知識/狀態」的部分，全部站在 P0 上**；不涉共享的純工程件（router registry、會後 STT、出圖）可提早做。

---

## 4. #11 自我維護與擴展：從記憶層自癒長到服務層自維運

現況的 #11 覆蓋約 35%（[README](README.md)），且全在**記憶層**。要當平台核心，得把「自維護」從記憶資料擴到**運行的服務**。

| 自維護層級 | 現有零件（記憶層，已有） | 平台層要長成什麼 | 可逆性 |
|---|---|---|---|
| **L1 機械修復** | atom-heal L1（自動補反向連結/索引）；docdrift（偵測文件漂移） | 服務健康自癒：壞掉的 worker 自動重啟、索引自動重建（vector skill `rebuild` 雛形可長大） | 可逆（純運維腳本） |
| **L2 LLM 提案** | atom-heal L2（LLM 提修復方案）；Wisdom Engine 反思 | 服務異常根因分析 + 修復提案（log 異常→診斷卡→提案）；複用 Fix Escalation 的「修不好就升級」 | 可逆 |
| **L3 喚醒人工** | atom-heal L3（修不好→`_heal_review/` 管理職裁決）；conflict pending review | 自維運的 HITL：自動擴容/版本升級這類高風險動作**強制人工確認 + 簽章**（[08](08-security-governance-compliance.md) §5：自維護不可變自我提權後門） | — |
| **擴展（scale-out）** | 自我迭代晉升（atom 自動晉升/降級候選） | 自動擴容（負載→加 worker）+ 跨客戶端版本升級協調（滾動升級、相容性檢查） | 🔴 上多客戶端後難回頭 |

> 設計紅線（[08](08-security-governance-compliance.md) §5 同源）：**「AI 自己維護」≠「AI 能改自己的權限」。** 自維護動作必須限縮在 default-deny 內，凡改權限/部署/擴容類一律 HITL + 外部簽章，否則自維護退化成自我提權後門。atom-heal「最多自動修 N 次，修不好喚醒人工」的既有節制（呼應 Guardian「最多阻 2 次、第 3 次放行」精神）正是服務層自維運該繼承的安全閥。

> (推測) 最務實的第一刀：把 `vector` skill 的 `rebuild`、worker 重啟這類**現有運維動作**包進一個「健康監控 + 自癒」daemon，沿用 atom-heal 的 L1→L2→L3 升級階梯，**先自癒、不自擴**——自動擴容/版本協調等多客戶端成熟後再上（不可逆，見 §7）。

---

## 5. #14 跨裝置架構：手機 thin client + 核心留電腦

願景白紙黑字：**「可串接手機 APP，但核心作業還是必須放在電腦」**——這直接定義了 client-server 切分線，不是「手機也跑一套」。

| 層 | 放哪 | 做什麼 | 不做什麼 |
|---|---|---|---|
| **手機 thin client** | 手機 | I/O（語音/文字輸入、結果呈現）、推播通知（任務完成/待 HITL 審批）、輕查詢（查 atom、看日誌摘要）、HITL 審批按鈕 | **不**跑 LLM 推理、**不**存權威記憶、**不**跑編排/攝取/STT |
| **核心** | 桌面/內部伺服器 | 重運算（Claude/Ollama 推理、向量檢索、編排 DAG、攝取、STT）、權威 atom store、所有有副作用的 connector 動作 | — |
| **連線** | P0 中央服務的 API | 手機經 SSO 取 JWT → 走 P0 的 AuthZ → 查/收結果；離線時看本地快取的摘要 | 手機不直連模型/向量庫，一律過 Orchestrator filter |

> 為何「核心留電腦」是對的設計（不只是願景指定）：① 單 3090 與本地 Ollama 在桌面，手機沒有等價算力；② 權威記憶 + RLS 權限必須中心化（P0 已是 server），手機只是又一個 client；③ 重副作用 connector（請假/開會）要 HITL + 稽核，手機只當「審批終端」而非「執行端」最安全。

> 落地姿勢（推測）：手機 client 本質是 **P0 中央服務的第 N 個 client**——和桌面 Claude Code client 共用同一套 AuthN/AuthZ/API。設計上採**離線優先（local-first）**：手機本地存可離線查的快取摘要，復網經 CRDT/最終一致同步（[Ink & Switch, Local-first software](https://www.inkandswitch.com/local-first/)）；但**權威寫入與重運算永遠回桌面/伺服器**——這正是願景「核心留電腦」與 local-first「離線可用」的調和點：手機可離線**讀**，但**寫與算**回核心。跨裝置同步的衝突合併與 P1 編排的任務狀態一致性模型同源（[01](01-memory-as-shared-cortex.md) §5 開放問題），宜待狀態機定義後一併決。

---

## 6. 差異化護城河：演進時絕不可丟的既有資產

把現有系統長成平台時，最大的誘惑是「打掉重練、買現成知識層」。但現有系統最值錢的，恰恰是商業方案**普遍沒有**的那層。

| 護城河資產 | 現有真實機制 | 多數商業方案（如 Glean）有嗎 | 演進時的命令 |
|---|---|---|---|
| **信任分級** | [臨]→[觀]→[固] + Confirmations 門檻 | 多半只有「存/不存」，無成熟度維度 | 服務化時當一等公民帶走 |
| **效用閉環** | α/β Beta-Bernoulli + Wilson 下界 + λ 慢衰減（與 Cognee Memify edge-weight 同源） | 罕見；多數靠人工策展或純向量相似度 | 保留並服務化；還可複用到模型評分（[03](03-model-routing.md)） |
| **衝突偵測** | 三時段（write/pull/startup）+ 敏感類 auto-pending review | 罕見做到「寫入前主動偵測語意衝突」 | 升級為多人並發合併（CRDT/OT），但偵測邏輯留 |
| **選擇性遺忘** | Memory Governance（分心懲罰/relevance gate/`_distant/` 隔離） | 幾乎沒有；多數只增不刪 | 共享皮層更需要（多人污染風險更高） |
| **反退避治理** | Evasion Guard + Codex Companion + context-memory-governance 憲法 | 沒有同類概念 | 可長成合規 review gate（[08](08-security-governance-compliance.md) §4） |

> 一句話（[README §收束](README.md)）：**最難、最少人做對的「記憶品質治理」已經啃下來了。** Glean 驗證了「權限感知知識層 + 多模型 + 企業治理」商業走得通（$300M ARR），但它和我們的差異化護城河正在這層品質治理。演進時這些是地基資產，不是「之後再補」——一旦在服務化過程被當成包袱丟掉，就把唯一的差異化也丟了。

---

## 7. 遷移風險與不可逆點

> 核心策略：**絞殺者模式 + fail-open 回退**——能加 API 層包住舊機制的都可逆；一旦做「資料模型遷移 + 多租戶上線」就難回頭。把不可逆點識別出來，在它之前留足回退路徑。

| 改動 | 可逆性 | 為什麼 | 緩解 |
|---|---|---|---|
| 抽 `atom_io.py` funnel 後端為 API | ✅ **可逆** | 介面不動，舊檔案路徑可保留為快取/回退 | feature flag 雙寫（同時寫檔案 + API），灰度切換 |
| 加 Model Registry / `route()` / 工具 registry | ✅ **可逆** | 都是在現有零件外包協調層 | flag 控制，出問題退回寫死二分/手動配 MCP |
| 編排器 / DAG / 驗收閘 | ✅ **大致可逆** | 加在 sub-agent dispatch 之上 | 退回 parent 當下 dispatch |
| 各感官/觸手 connector | ✅ **可逆** | 獨立 connector，加減不影響核心 | 唯讀先行；寫入類 HITL + compensating action |
| **scope → 真 RLS 權限的資料遷移** | 🔴 **難回頭** | 一旦把 atom 從「明文 .md + 注入過濾」遷成「DB 列 + RLS 標籤 + 加密」，多租戶資料模型定型，要退回單機檔案需反向 ETL，且加密/簽章後資料難原樣還原 | 遷移前先在 `_atom_index.json` JSON SoT 加 optional 欄位試點（不動 .md 本體，[01](01-memory-as-shared-cortex.md) §5）；保留一份明文匯出快照當逃生艙 |
| **多租戶正式上線（多人寫同一中央庫）** | 🔴 **難回頭** | 多人資料一旦混入同一中央庫並建立跨租戶引用/共享，無法乾淨拆回各人單機 | 先單租戶（自己）service 化跑穩，再開多租戶；多租戶前先定清資料邊界與 retention |
| **自動擴容 / 跨客戶端版本協調上線** | 🔴 **難回頭** | 一旦多客戶端依賴中央版本協調，回退單機會破壞已分發 client 的相容性 | §4：先自癒不自擴；擴容前先有版本相容性檢查與滾動回退機制 |

> 鐵律總結：**P0 的「服務化前半（抽 API）」與 P1/P2 的協調層都可逆**——可大膽用絞殺者模式漸進、保留 fail-open。**P0 的「真權限資料遷移」與「多租戶上線」是不可逆點**——做之前必須：① 明文快照逃生艙；② 單租戶先跑穩；③ 資料邊界與 retention 定清。一旦跨過，就是「從個人海馬迴正式變成公司共享皮層」的那道門——值得跨，但要帶好回退繩再跨。

---

## 8. 收束（對發想者）

- **第一刀切哪**：P0 的「抽 `atom_io.py` funnel 後端為中央 API（雙寫灰度）」——最小改動、最低風險、完全可逆，卻是把「個人海馬迴」推向「共享皮層」的第一步。
- **最關鍵的依賴**：P1 編排的「跨 agent 記憶共享」與 P2 攝取的「權限標記」全站在 P0 真權限上；P0 沒到位，後面再炫的能力也只是 N 個單機孤島（[02](02-orchestration-core.md) §4-2）。
- **最容易犯的錯**：服務化時把護城河（信任分級/效用閉環/遺忘/反退避，§6）當包袱丟掉，或在跨過「真權限資料遷移」這個不可逆點（§7）前沒留逃生艙。
- **#11 與 #14 的本質**：#11 是「把 atom-heal 的 L1→L2→L3 自癒階梯從記憶層擴到服務層，但改權限/擴容類強制 HITL」；#14 是「手機只是 P0 中央服務的又一個 thin client，離線可讀、寫與算回核心」。兩者都不是新造輪子，是把既有零件按安全邊界延伸。

> 互引導讀：記憶皮層升級細節 [01](01-memory-as-shared-cortex.md)｜編排引擎 [02](02-orchestration-core.md)｜模型路由 [03](03-model-routing.md)｜工具註冊 [04](04-tool-registry-and-protocols.md)｜知識攝取 [05](05-knowledge-ingestion.md)｜多模態 [06](06-multimodal-io.md)｜作業紀錄 [07](07-work-journal-and-activity.md)｜安全治理 [08](08-security-governance-compliance.md)｜回 [README](README.md)

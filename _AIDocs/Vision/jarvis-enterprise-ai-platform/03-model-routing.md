# 多模型主動分工 — 哪家在哪方面強就派誰
> 所屬：[JARVIS 企業 AI 平台發想](README.md) · 對應願景 #2

> **立場**：發想層、可執行的設計參考（「說不定某天會做成成品」）。技術現況以來源 URL 為準，會過時；推測處標「(推測)」。

---

## 1. 對應願景需求

| 願景 | 內容 | 本檔關係 |
|------|------|---------|
| **#2（主檔）** | 跨各家大模型，哪家在哪方面表現出色就負責什麼的**主動分工** | 本檔核心：model registry + capability scoring + 動態選模 + fallback |
| #7（附帶） | 翻譯 | 「翻譯」是一種任務類型 → router 選翻譯強的模型（如某些模型中英術語保真較佳）；pipeline/術語庫見 [多模態 I/O](06-multimodal-io.md) |
| 全平台（成本面） | 編排、攝取、日誌、衝突偵測都在燒 token | router 是**全平台的成本閥門**：把廉價任務壓到本地/小模型，貴模型只接硬任務 |

**一句話定位**：[編排核心](02-orchestration-core.md) 是「決定哪個 *agent* 該行動」，本檔的 router 是「決定那個 agent 該用哪個 *模型*」。兩者是上下層——編排在任務層分工，router 在模型層分工。

現況覆蓋 **🔴 5%**：只有 Claude(雲) + Ollama(本地) 的**固定二分**，分工寫死在程式裡，沒有 registry、沒有評分、沒有動態選模（見 §4）。

---

## 2. 現有方案比對表

> 數字均附 URL，2026-06 查得；商業數字多為廠商自報，實測會因任務分佈而異 (推測)。

| 系統 | 路由策略 | 容錯 / fallback | 成本省幅 | 可仿效點 | 來源 |
|------|---------|----------------|---------|---------|------|
| **OpenRouter** | `openrouter/auto` 分析 prompt 複雜度/任務型自動選模（NotDiamond 驅動）；`cost_quality_tradeoff` 0–10（0=最強模型、10=最便宜、預設 7） | 雙層：**模型層**（context-length/moderation/ratelimit/downtime 降級）+ **提供商層**（5xx 跨商容錯，失敗不計費）；選定後 pin 模型+商以利 prompt cache | 隨 tradeoff 旋鈕浮動；無額外路由費，按所選模型計費 | 「auto + 一個旋鈕調成本/品質」的極簡 UX；wildcard 限定（`anthropic/*`）；**失敗不計費** | [blog](https://openrouter.ai/blog/insights/model-routing/) · [docs](https://openrouter.ai/docs/guides/routing/routers/auto-router) |
| **Portkey**（AI Gateway，開源） | **最全**：條件路由（metadata）/ 負載平衡（加權）/ 層級降級（嵌套 fallback）/ 任務型路由；語義快取 | **最強**：重試指數退避（≤5）+ **熔斷器**（依錯誤率/狀態碼 trip，cooldown 後自動恢復、暫時移除不健康 target）；可指定觸發 fallback 的錯誤類型 | 廠商定位「成本/延遲雙路由」；省幅依策略 | 熔斷器（避免 retry storm）、嵌套層級降級、語義快取、50+ 守衛、成本追蹤 | [blog](https://portkey.ai/blog/task-based-llm-routing/) · [retries/CB](https://portkey.ai/blog/retries-fallbacks-and-circuit-breakers-in-llm-apps/) · [gh](https://github.com/Portkey-AI/gateway) |
| **RouteLLM**（學術/開源） | 學習式：embedding 路由 / BERT 分類器（<10ms，無需 LLM 推理）；可自訓 | 框架本身專注路由決策，容錯靠上游 | **省 85% @ 95% GPT-4 品質**（MT Bench，僅 ~14% 流量走強模型）；MMLU 省 45%、GSM8K 省 35% | 「強弱二分 + 學習式門檻」這招最值得仿；可用 Chatbot Arena 偏好資料自訓 | [arxiv](https://arxiv.org/pdf/2406.18665) · [lmsys](https://www.lmsys.org/blog/2024-07-01-routellm/) · [gh](https://github.com/lm-sys/routellm) |
| **Martian** | 商業實時動態路由 | 商業託管 | **20%–97%**（依任務複雜度），延遲 20–50ms | 「實時 + 低延遲」的商業基準線 | [awesome-routing](https://github.com/Not-Diamond/awesome-ai-model-routing) |
| **LiteLLM**（最輕代理層，開源） | 統一 API 50+ 提供商；auto routing（查詢複雜度分類）；路由規則 GitOps（版本控管） | 代理層 fallback/重試 | 取決於規則 | **規則即程式碼（GitOps）**——路由策略進 git review，最貼合本平台習慣 | [docs](https://docs.litellm.ai/docs/proxy/auto_routing) |
| **(現況) 雙 LLM 二分** | **寫死**：Claude=雲決策/分類，Ollama=本地 embedding/萃取/rerank；萃取 quick→qwen3 / deep→gemma4 | Ollama 三階段退避 + 向量 fallback 鏈（見 §4） | 本地零 API 費，但無動態選模 | —（這正是要演進的起點） | [toolchain-ollama 記憶] |

> 路由開銷對照（決定「值不值得路由」的關鍵）：rule-based **<1ms** / embedding(semantic) **~5ms+embed** / BERT 或 ML 分類器 **<10–100ms** / LLM 分類器 **500–2000ms**。典型 LLM 推理本身就 500–2000ms，所以**即使 100ms 路由開銷，只要省下 50% 推理就划算**。成本優化 5 策略（語義路由 50–200ms@85%+精度 / 成本感知 / 意圖分類 10–50ms / 串級 progressive escalation / 負載平衡）實測省 40–85%。來源：[digitalapplied 2026 guide](https://www.digitalapplied.com/blog/llm-model-routing-2026-cost-quality-optimization-engineering-guide)。

---

## 3. 推薦設計取捨（給內部開發平台）

不照搬任何單一家。給「內部、可自託管、要看得懂底層」的平台，建議三件拼起來：

1. **Portkey-style gateway 為骨架**：容錯（熔斷 + 指數退避）+ 任務型/條件路由。容錯是非功能性剛需，別自己重寫 retry storm 防護。
2. **串級 escalation 為主路由策略**：`本地 Ollama（fast）→ 雲端 Claude（powerful）`。RouteLLM 證明強弱二分能 95% 品質省 85% 成本——本平台本來就有「本地免費 / 雲端付費」這條天然斷層，幾乎是為串級量身打造。
3. **capability registry 為大腦**：登錄「哪個模型擅長什麼」（程式 / 翻譯 / 出圖判斷 / 長文 / 結構化萃取），router 查表選模，而非寫死 if-else。

### 路由策略選型（按開銷/精度排）

| 策略 | 開銷 | 精度 | 適用 | 取捨 |
|------|------|------|------|------|
| 規則 / metadata 條件 | <1ms | 看規則 | 已知任務型（萃取走 qwen3、翻譯走 X） | 最透明、最好 debug；冷啟動就能用；但靠人寫規則 |
| 意圖分類（小模型） | 10–50ms | 中 | prompt 看不出任務型時 | 廉價；需訓練/維護分類器 |
| 語義/embedding 路由 | 50–200ms | 85%+ | 細粒度相似任務匹配 | 本平台**已有 embedding 基礎建設**，邊際成本低；延遲較高 |
| 串級 escalation | 一次廉價推理 | 高（強模型兜底） | 大多數任務 | 最省；壞處是難任務被罰一次本地失敗的延遲 |
| LLM 分類器 | 500–2000ms | 高 | 高價值低頻決策 | 太貴，僅編排層偶用 (推測) |

> 建議組合：**條件規則（已知任務直接派）→ 命中不了用語義路由 → 仍不確定走串級兜底**。三層由便宜到貴，與現有 [向量 fallback 鏈](#) 的「能跑就用便宜的」哲學一致。

### 本地優先 vs 雲端品質權衡

| 維度 | 本地優先（Ollama） | 雲端優先（Claude 等） | 設計取捨 |
|------|-------------------|---------------------|---------|
| 成本 | 零 API 費（電費/折舊） | 按 token 計費 | 高頻低風險任務（萃取/rerank/分類）壓本地 |
| 品質 | 小模型，硬任務易翻車 | SOTA | 決策/長程推理/對外產出走雲端 |
| 延遲 | 受本地 GPU 限（GTX 1050 Ti 4GB 只能單模型輪替；RTX 3090 無此限） | 網路 RTT + 排隊 | 即時互動看哪邊瓶頸小 |
| 隱私/合規 | 資料不出機房 | 資料上雲（合規敏感） | 機敏資料**強制**本地，由 router 依資料標籤硬性路由（紅線，見 §5） |
| 可用性 | 本機掛了就沒了 | 廠商 SLA + 跨商容錯 | 串級天然互為 fallback |

> 結論：**預設本地、按需升雲**。把「升雲」當成一次需要理由（複雜度/品質門檻/合規允許）的明確決策，而不是預設值——這既省成本又逼出「為什麼這個任務值得用貴模型」的可解釋性。

---

## 4. ★落地切入點（現有零件 → router 雛形）

**好消息：router 的骨架已經零散地存在了，只是寫死、沒抽象。** 把現有四個機制重讀成 router 語彙：

| 現有零件（真實存在） | 對應 router 概念 | 能用 vs 必新建 |
|---------------------|-----------------|---------------|
| **雙 LLM 固定二分**：Claude(雲,決策/分類) + Ollama(本地,embedding/萃取/rerank) | 一張寫死的「2 entry registry + 2 條 routing rule」 | ✅ **能用**（語義就是 registry，只是 hard-coded）→ 抽成資料表 |
| **依任務挑萃取模型**：quick=qwen3:1.7b(5s) / deep=gemma4:e4b | 任務型條件路由（task → model） | ✅ **能用**（已是 task-based 雛形）→ 泛化成查表 |
| **Ollama Dual-Backend 三階段退避**：連續 2 失敗→Short DIE 60s→10 分內 2 次→Long DIE 等 6h 邊界 | 熔斷器（circuit breaker）+ cooldown | ✅ **能用**（這就是熔斷器！）→ 升級成 per-model 健康狀態 |
| **`ollama_client.py` 三 API（generate/chat/embed）auto primary→fallback；failover 切 model 名** | 提供商層 fallback + 模型降級 | ✅ **能用**→ 推廣到「雲↔本地」跨層 fallback |
| **向量 fallback 鏈**：Ollama → sentence-transformers → keyword | 層級降級（tiered fallback / 嵌套 fallback） | ✅ **能用**（已是三層 graceful degradation） |

**必新建（現在完全沒有）**：

| 缺件 | 內容 | 起手 |
|------|------|------|
| **Model Registry** | 結構化登錄每個模型：endpoint、成本/1k token、延遲、上下文長度、能力標籤（程式/翻譯/萃取/長文/出圖判斷）、健康狀態 | `workflow/config.json` 已有 `usefulness.*` 旋鈕的先例 → 新增 `models[]` 區塊；把 §4 表第一/二列的寫死值搬進去 |
| **Capability Scoring** | 「哪個模型在哪方面強」的可更新評分。**可複用現有 Wilson 下界效用閉環**（atom 晉升用的 Beta-Bernoulli α/β + decay λ=0.97）——把「atom 有沒有用」換成「模型在某任務型上成不成功」，同一套統計骨架 | 仿 `usefulness` 的 succ/fail 累計 + Wilson LB；初值靠人工/公開 benchmark 種子 |
| **Router 決策層** | 吃 task type + 成本/品質偏好 + 資料合規標籤 → 查 registry + scoring → 選模 | 把現在散在 extract-worker / server.js 的「選哪個模型」決策**收斂到單一 `route()`**；先實作條件規則層（最透明），再加語義層 |
| **成本/品質旋鈕** | 仿 OpenRouter `cost_quality_tradeoff` 0–10，掛到 `config.json` | 一個純量旋鈕，串級的升雲門檻隨它移動 |

> **演進路徑**：① 抽 registry（純重構，把寫死值搬進 config，行為不變）→ ② 把三階段退避升成 per-model 熔斷器 → ③ 加 capability scoring（複用 Wilson）→ ④ 上條件規則 router → ⑤ 視需要加語義/串級。每步都可獨立驗證、行為向後相容。落地依賴順序見 [從現有系統演進](09-evolution-from-current-system.md)。

> **誠實標記**：①②④⑤ 是把既有機制重組（工程量中、風險低）；③ 的 capability scoring 種子資料與評分校準是真正的新研究問題——「模型在某任務型上強不強」需要可信的 ground truth，冷啟動只能靠公開 benchmark + 少量人工標註，再靠線上回饋慢慢校正 (推測)。

---

## 5. 已知風險 / 紅線 / 待驗證假設

| 類別 | 項目 | 說明 / 緩解 |
|------|------|------------|
| 🔴 紅線 | **合規路由不可被成本旋鈕覆蓋** | 機敏資料強制本地，必須是**硬性前置過濾**，排在成本/品質決策之前。否則「為省錢把客戶資料送雲」是合規事故。資料標籤 → 強制本地，無條件。 |
| 🔴 紅線 | **路由黑盒不透明** | 學習式路由（embedding/LLM 分類器）選模理由難解釋，出事難復盤。對內部平台**優先可解釋的規則層**，黑盒策略只在低風險高頻任務用，且必記錄「為何選這個模型」進 audit。 |
| ⚠ 風險 | **品質優先偏差 → 永遠選貴模型** | 若 scoring 只看品質不看成本，router 會退化成「全走 Claude」，等於沒做。必須把成本明確進目標函數（OpenRouter 的 tradeoff、RouteLLM 的強弱比例都是在治這個）。 |
| ⚠ 風險 | **第三方 SaaS 鎖定 vs 自託管** | OpenRouter/Martian/Portkey-SaaS 省事但把「選模權」交出去、且資料過第三方。本平台立場是內部可自託管 → **取 Portkey/LiteLLM 的開源核心自架**，不接其託管。 |
| ⚠ 風險 | **路由開銷吃掉省下的成本** | 對短任務，LLM 分類器（500–2000ms）的路由開銷可能比省下的還貴。規則：路由策略的開銷必須 ≪ 被路由任務的推理成本（見 §2 開銷表）。 |
| ⚠ 風險 | **熔斷誤判長尾** | 三階段退避的 Long DIE（等 6h）對偶發抖動可能過度懲罰，把健康模型關太久。per-model 熔斷要分「短暫 ratelimit」vs「真死」用不同 cooldown。 |
| ❓ 待驗證 | capability scoring 種子可信度 | 公開 benchmark（MT Bench/MMLU）與「本平台實際任務分佈」的相關性未知；冷啟動評分可能偏差大，需線上回饋校正。(推測) |
| ❓ 待驗證 | 串級的「本地失敗罰一次延遲」可接受度 | 串級對難任務會先吃一次本地失敗再升雲，互動式場景的延遲體感是否可忍受，需實測。(推測) |
| ❓ 待驗證 | Wilson 效用閉環能否直接搬到模型評分 | atom 晉升的 α/β 統計能否原樣套到「模型×任務型成功率」，量綱與樣本量假設是否成立，需驗證（框架跨域複用先驗型別/值域，見核心規則）。(推測) |

---

> **相鄰子檔**：上游任務分工見 [編排核心](02-orchestration-core.md)；模型背後的工具上架/認證見 [工具註冊與協定](04-tool-registry-and-protocols.md)；翻譯/出圖/STT 等「任務型」的需求面見 [多模態 I/O](06-multimodal-io.md)；落地依賴與演進順序見 [從現有系統演進](09-evolution-from-current-system.md)。回 [README](README.md)。

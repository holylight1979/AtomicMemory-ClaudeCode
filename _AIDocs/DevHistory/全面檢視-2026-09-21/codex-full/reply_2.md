**結論：優先修正「評估器與線上管線不一致、失效記憶可能被 Related 帶回、拒用被誤判為使用」三項問題；目前沒有證據支持直接導入另一套記憶框架。** 圖排序與離線策略鞏固值得做小型實驗，但尚未達到正式新增機制的門檻。

本報告查證至 **2026-09-21**。已完整閱讀既有業界調查，並核對檢索、注入、效用歸因、失敗萃取與回歸評估程式。以下區分：

- **本地實測**：本輪執行的唯讀回歸與合成案例。
- **論文／作者自報**：已查原始論文或專案來源，未在本機重跑。
- **提案／推論**：針對本系統的改法與成本估計，不代表已證實提升。

真正晚於既有調查日期 **2026-08-28** 的新增研究證據，主要是 **Memory Trust Gap（9/1）、Revoked but Still Authoritative（9/8）、REALM（9/13）**。其餘是補查機制、校正數字或排除重複，不冒充新發表成果。

## 候選清單

先列直接影響決策的本地證據；表中 L1–L6 指向下列位置。

| 編號 | 已驗證事實與證據 |
|---|---|
| **L1** | 線上已有一跳 `Related` 廣度優先搜尋（BFS，沿連結逐層找鄰居），不是完全沒有傳播：[wg_atoms.py:302](C:/Users/holylight/.claude/hooks/wg_atoms.py:302)。但 Related 的篩選函式沒有接收 query，只依效用與 activation 排序、最多保留 6 顆：[ups_inject.py:102](C:/Users/holylight/.claude/hooks/handlers/ups_inject.py:102)。 |
| **L2** | `Supersedes` 僅掃描當次命中的候選，移除舊 atom 後，仍把完整 `all_atoms` 傳給後段：[ups_search.py:293](C:/Users/holylight/.claude/hooks/handlers/ups_search.py:293)。Related 隨後從該池擴散：[ups_inject.py:302](C:/Users/holylight/.claude/hooks/handlers/ups_inject.py:302)。 |
| **L3** | 回歸評估器的 `retrieve()` 是 trigger → BM25 補位 → 零命中才 vector，**沒有 RRF、ACT-R、Supersedes、Related 或最終注入裁切**：[run.py:77](C:/Users/holylight/.claude/tools/memory-eval/run.py:77)。線上 RRF 實作在 [ups_search.py:320](C:/Users/holylight/.claude/hooks/handlers/ups_search.py:320)。 |
| **L4** | 使用判定主要看 token 重疊，不辨認「採用／引用／否定」：[wg_atoms.py:1110](C:/Users/holylight/.claude/hooks/wg_atoms.py:1110)。成功訊號可來自「宣告完成且沒有失敗訊號」，再套到被判 used 的 atom：[stop.py:350](C:/Users/holylight/.claude/hooks/handlers/stop.py:350)、[stop.py:425](C:/Users/holylight/.claude/hooks/handlers/stop.py:425)。 |
| **L5** | 負面記憶已具備「觸發場景 → 錯誤行為 → 正確做法＋根因」格式，不缺一般反模式萃取：[extract-worker.py:180](C:/Users/holylight/.claude/hooks/extract-worker.py:180)。 |
| **L6** | 已有曝光、α/β 效用、工具使用證據、失念及 token 稅報表：[memory-effect-report.py:2](C:/Users/holylight/.claude/tools/memory-effect-report.py:2)。失念偵測以問題文本匹配 trigger，排除 session 中已注入者：[wg_recall_miss.py:169](C:/Users/holylight/.claude/hooks/wg_recall_miss.py:169)。 |

### 可推進或值得驗證的候選

成本是熟悉本專案者的粗估；不含長期觀察，也不是承諾。

| # | 名稱 | 來源（URL / 檔案:行） | 機制 | 類型 | 對本系統的意義（差在哪） | 第一個 session 看得到的效果 | 成本（人日／風險） | 證據等級 |
|---|---|---|---|---|---|---|---|---|
| **1** | **評估實際送入模型的記憶** | L3、L6 | 固定索引、access 統計、時間與 vector 回應，再跑實際排序及注入組裝。分開記錄「找到、排入、正文送達、只有指標、被裁掉」。既有 Recall/MRR 保留，但不再把檢索命中當成內容已送达。 | 補強 | 現有評估器無法驗證 RRF、activation 或 Related 的改善。這是所有演算法實驗的前置條件。 | 立即看見舊評估與線上結果差異、裁切造成的漏失及失效題目。 | **1–2**；注意測試不得更新 access sidecar。 | **本地程式核對＋回歸實測** |
| **2** | **所有檢索路徑共用失效排除** | [Revoked，2026-09](https://arxiv.org/html/2609.08258v1)、L2 | 將已確定被取代的 atom 排除，作為整條檢索管線的不變條件。排除不能依賴「新 atom 也剛好命中」。Related 擴散後與最终輸出前仍須保持有效性。 | 補強 | 本系統已有 Supersedes；缺口在涵蓋範圍與後段重新帶回，不需要另造衝突裁判。 | 合成案例中，舊 atom 不再從 Related 回流。 | **0.5–1**；須區分當前建議與明確的歷史查詢。 | **論文實驗＋本地函式層重現** |
| **3** | **效用歸因校準：拒用不算採用** | L4；[Memory Trust Gap，2026-09](https://arxiv.org/html/2609.01852v1) | 將「提到」與「依其採取行動」分開標記。先用少量標註樣本測現有 used 判定；遇明確否定或證據不足，保留 unknown，不增加成功計數。另用配對任務比較有／無記憶的結果，辨識負效益。 | 補強／精簡 | 不再新增一組 helpful/harmful 計數；先避免既有 α/β 被錯誤歸因污染。Wilson 公式無法補救錯誤標籤。 | 本輪已能重現「不要使用 X」卻被判 used；修正後可立即驗證。 | **1–2**；中文否定不能只靠一條 regex，可能錯殺真正使用。 | **本地合成實測；改法待驗證** |
| **4** | **Related 加查詢相關性與度數正規化** | [HippoRAG 2](https://arxiv.org/html/2502.14802v1)、[Cognee 原始碼](https://raw.githubusercontent.com/topoteretes/cognee/main/cognee/modules/retrieval/utils/brute_force_triplet_search.py)、L1 | 從直接命中的 seed 傳遞部分分數，出邊越多，每條分到越少。鄰居還要通過當前 query 的相關性檢查，再與直接候選競爭同一預算。先測一跳，不增加圖深度。 | 補強／可能精簡 | 已有傳播，但 Related 排序主要看歷史 activation，缺 query 訊號。增量是改善既有選擇，不是新增知識圖譜。 | 在既有連結的多跳題與干擾題上，立即比較補回幾題、誤帶幾顆。 | **1–2** 實驗；高連結節點、錯誤連結可能放大干擾。 | **論文／原始碼；本地增益未測** |
| **5** | **離線整併改成「有證據才更新局部」** | [ACE](https://arxiv.org/html/2510.04618v1)、[Useful Memories Become Faulty](https://arxiv.org/html/2605.12978v1)、L5 | 從同類且具結果證據的經驗形成候選；只更新局部條目，保留來源與例外。將整併前後記憶放到保留題比較，通過才採納。不能把「已寫出高階洞見」當成功指標。 | 精簡／條件式補強 | 8 月已提背景整併；本輪增量是**限制何時整併及何時拒絕整併**，不是再加睡眠服務。 | 使用既有歷史資料，第一輪即可發現資訊被壓掉或規則過度泛化。 | **2–3** 試驗；沒有足夠證據或保留題就不做。 | **論文反例；本地效果未測** |
| **6** | **REALM：檢索後只重整局部連結** | [REALM，2026-09-13](https://arxiv.org/html/2609.16053v1) | 檢索得到的局部子圖，經任務回饋後執行 add／strengthen／weaken。更新式為 \(w\leftarrow clip(w+\eta c,w_{\min},1)\)；strengthen 的 \(\eta=1-w_b\)，weaken 為 \(-(w_b-w_{\min})\)。它主要改連結，而非反覆改寫正文。 | 新增，**暫緩** | 比單顆 ACT-R 更進一步：學「哪些記憶一起有用」。但目前 α/β 歸因還不足以可靠驅動邊權重學習。 | 可用歷史資料做一次局部重整對照；不能保證冷啟動首回合有收益。 | **3–5**；自我強化錯誤連結及新增狀態成本。 | 作者消融：LoCoMo **+2.01 pp**、LongMemEval **+2.13 pp**；非本地成績。 |

### 指定研究逐項核對：可借的機制與不採用理由

以下多數不應成為新增工作項目；列出是為了明確交代研究覆蓋與排除依據。

| # | 名稱 | 來源 | 機制 | 類型 | 對本系統的意義（差在哪） | 第一個 session 看得到的效果 | 成本／風險 | 證據等級 |
|---|---|---|---|---|---|---|---|---|
| 7 | **Mem0** | [論文](https://arxiv.org/html/2504.19413v1) | 抽取候選事實，再對相似舊記憶判定 ADD／UPDATE／DELETE／NOOP。圖版本另外存實體關係。其核心是寫入時整合，不是特殊遺忘公式。 | 已有重疊，不新增 | atom_write 的品質閘、去重及衝突處理已覆蓋主要用途。 | 未查到換框架的首 session 增量。 | 不採用；遷移大於增量。 | 作者 LoCoMo judge：**66.88／圖版 68.44**；不能與其他論文的 F1 混排。 |
| 8 | **Zep／Graphiti** | [論文](https://arxiv.org/html/2501.13956v1)、[搜尋文件](https://help.getzep.com/searching-the-graph) | 事實邊記錄世界有效時間及系統記錄時間。融合全文、向量與圖搜尋，可用 RRF、MMR 等重排。舊事實失效後保留，是否排除仍依讀取路徑與過濾條件。 | 補強，僅取 #2 | 單純加時間欄位不能解決舊資料重新被使用。完整雙時間圖譜目前成本過高。 | #2 可測；全套換裝無必要。 | 局部 **0.5–1**；完整導入不估列。 | 作者同為 GPT-4o：LongMemEval **60.2→71.2**。既有調查的 **63.8→71.2** 混用了不同模型列，應校正。 |
| 9 | **Letta sleep-time compute** | [論文](https://arxiv.org/abs/2504.13171)、[官方機制說明](https://www.letta.com/blog/sleep-time-compute/) | 在問題到來前處理可重用上下文，將結果存成 learned context。Letta 將核心記憶編輯交給背景 agent，前台 agent 專注互動。提前計算能攤提成本，但取決於後續問題是否重用。 | 已評估；不再新增服務 | 本系統已有 detached worker；「背景跑 LLM」本身不是缺口。 | 未查到本地首 session 淨收益。 | 不採用全套；可作 #5 的批次執行方式。 | Stateful GSM／AIME 同準確率下，作者報告約 **5×** 減少 test-time compute；不是 Claude Code 實測。 |
| 10 | **Cognee** | [檢索原始碼](https://raw.githubusercontent.com/topoteretes/cognee/main/cognee/modules/retrieval/utils/brute_force_triplet_search.py) | 向量搜尋取得節點，再投影鄰域與三元組。程式會替擴散新節點補做向量評分，避免只因相連就得到不合理預設分數。排序亦可納入節點／邊回饋。 | 補強，僅借 #4 | 值得借的是「擴散後仍須評 query 相關性」，而非導入圖資料庫。 | 可在相同候選池比較 Related 噪音。 | 局部 **1–2**；原始碼 main 會變動。 | 原始碼；**未查到此單一機制的可靠消融數字**。 |
| 11 | **A-MEM** | [論文 v1](https://arxiv.org/html/2502.12110v1) | note 含原文、時間、關鍵詞、標籤、描述、embedding 與連結。新 note 找近鄰，LLM 決定建立連結並更新舊 note 的描述。演化發生於新資料到來時。 | 已有重疊；暫不引入自動改寫 | atom＋Related 已有相近骨架；自動改寫舊描述會增加漂移風險。 | 未證實優於現有策展。 | 不採用全套。 | v1 GPT-4o 多跳 F1：**39.41**，MemGPT **17.29**；開放域反而 **48.43＜60.16**，不是全項領先。 |
| 12 | **MemoryBank／Ebbinghaus** | [論文 §2.3](https://arxiv.org/html/2305.10250) | 保留率 \(R=e^{-t/S}\)。每次喚回令 \(S\leftarrow S+1\)、\(t\leftarrow0\)，使記憶更慢淡出。這是喚回强化，而非結果導向强化。 | 精簡：不加第二套衰減 | 本系統已有 ACT-R、效用調整 decay 與 selective forget；再疊此曲線沒有清楚增量。 | 無新增效果證據。 | **0**，保留現行。 | 公式已核；**未查到足以證明該遺忘項單獨優勢的消融數字**。 |
| 13 | **Generative Agents 反思樹** | [論文 §4.2、§6.5](https://arxiv.org/html/2304.03442) | 最近事件的重要性總和超過 **150** 才反思。取最近 100 筆形成 3 個問題，檢索後生成 5 個引用來源的洞見。洞見可再作上層洞見的材料。 | 暫緩 | 可借來源指向與批次觸發；不能把 NPC 的人格綜合效果直接當工程記憶可靠度。 | 必須有既有經驗才能回放測試。 | 試驗 **2–3**；推測逐層變成「事實」的風險高。 | 人類可信度 TrueSkill：完整 **29.89**、去反思 **26.88**；不是任務正確率。 |
| 14 | **HippoRAG 1／2** | [HippoRAG 2 論文](https://arxiv.org/html/2502.14802v1)、[官方 repo](https://github.com/OSU-NLP-Group/HippoRAG) | v1 以查詢實體當 seed，跑 personalized PageRank（PPR，從查詢起點反覆沿圖傳遞分數）。v2 加 passage 節點、query-to-triple 與 LLM triple filtering，再跑 PPR。標準形式為 \(p=(1-\alpha)s+\alpha P^\top p\)。 | 補強，僅測 #4 | 有用增量是 seed 分數傳播與鄰居辨識；全文圖抽取與 70B 過濾器不屬小改動。 | 現有 Related 多跳題可立即 A/B。 | 局部 **1–2**；完整移植不建議。 | Llama-3.3-70B reader：平均 F1 **59.8 vs NV-Embed-v2 57.0**；MuSiQue Recall@5 **74.7 vs 69.7**。 |
| 15 | **ReasoningBank** | [論文](https://arxiv.org/html/2509.25140v1) | 自評 trajectory 成敗，從兩者抽取 title／description／content 策略。用 embedding 取 top-k；其 consolidation 實際是簡單追加。MaTTS 額外比較同題不同嘗試，利用成功與失敗差異改善策略。 | 重疊多；不新增一般負面記憶 | L5 已有反模式與根因。真正可能的差異是**同題成敗配對**，但不能為產生記憶刻意增加大量 rollout。 | 有現成成敗對照時才可檢驗。 | 局部試驗 **1–2**；自評錯誤會污染策略。 | WebArena 三 backbone 相對無記憶 **+8.3／+7.2／+4.6 pp**；Gemini Flash 平均步數 **9.7→8.3**。 |
| 16 | **ACE playbook delta／grow-and-refine** | [論文](https://arxiv.org/html/2510.04618v1) | Generator 執行、Reflector 抽教訓、Curator 產生局部條目更新。每條有 ID 與 helpful／harmful 計數，程式合併，再定期去冗。避免整份 playbook 每輪重寫。 | 精簡／局部補強 | atom 本身已是局部條目，α/β 也已有；不需要再造一份 playbook 與第二套計數。 | 可直接檢查整併是否保留舊例外。 | 只納入 #5。 | AppWorld 作者綜合平均：ReAct **42.4→online ACE 59.5**；不等於每種任務提高 17.1 pp。 |
| 17 | **Dynamic Cheatsheet** | [論文](https://arxiv.org/abs/2504.07952)、[ACE 反例](https://arxiv.org/html/2510.04618v1) | 每題後把可重用策略與程式更新進小抄，後續題重用。主要收益包含保留可執行且已驗證的程式。整體重寫可能把舊細節壓掉。 | 不採用整份重寫 | 既有 atom／skill 已能分項保留，不必退回單一小抄。 | 無可靠新增效果。 | **0**；避免引入壓縮退化。 | GPT-4o Game of 24 **10%→99%**；高度可重用求解程式的特定任務。 |
| 18 | **Voyager skill library** | [論文](https://arxiv.org/abs/2305.16291) | 根據環境回饋、執行錯誤及自驗修正程式。成功技能以可執行程式存入庫，之後檢索與組合。記憶的主要內容是程序，不是自然語言摘要。 | 目前無新增必要 | 應將可驗證程序留在既有 skill／工具，atom 記條件與入口；不自動把每次成功都變 skill。 | 找到明確重複程序時才有。 | 視具體程序估算。 | Minecraft 作者結果：獨特物品 **3.3×**、里程碑最高 **15.3×** 加速；不可轉為本系統效益預估。 |
| 19 | **MemOS** | [論文](https://arxiv.org/html/2507.03724v1) | MemCube 統一正文、KV cache 與參數記憶的內容及治理 metadata。scheduler 按任務與使用情況載入或轉換記憶。KV 方案預先編碼記憶並放在 GPU。 | 對本任務多數無關 | 本地 hook 注入不控制 Claude 的 KV／模型權重；導入 OS 抽象會增加大量框架成本。 | 無可驗證的首 session 增量。 | 不採用。 | H800／Transformers 實驗，Qwen3-8B 長 context 短 query TTFT **2.04→0.12 秒**，另有 **0.93 秒建置**。 |
| 20 | **Mem-α** | [論文](https://arxiv.org/html/2509.25911v1) | 用強化學習訓練 memory insert／update／delete 策略。獎勵包含下游 QA、工具格式、語意有效性及壓縮 \(1-L_m/L_c\)。管理 core／episodic／semantic 記憶。 | 非小改動，暫緩 | 需要訓練與任務資料，不能把 reward 式子貼進 prompt 就取得論文能力。 | 首 session 無法驗證自家收益。 | 原論文 **32 張 H100、3 天**；不符合本輪成本條件。 | 驗證集平均 **0.642 vs long-context 0.588**；混合任務指標，非單一 QA 準確率。 |
| 21 | **LightMem** | [論文](https://arxiv.org/html/2510.18866v1) | 前段 token 篩選、依主題切段、摘要後入庫。離線更新候選為 \(Q(e_i)=TopK\{e_j: t_j\ge t_i\}\)，限制後來資料更新早期資料。昂貴維護與前台分離，更新佇列可批次處理。 | 已有離線重疊；僅供 #5 參考 | 主題分段可能比整段 20k chars 更聚焦；但 LLMLingua-2／attention 分段不是直接靠現有 Ollama 就具備。 | 需比較同一 transcript 的抽取完整度，不能只看省 token。 | 簡化試驗 **2–3**；否定、版本等資訊可能被壓掉。 | 作者跨配置報告 token **32–117×**、API calls **17–177×** 減少；屬整套管線，不是離線更新單項效果。 |

## 最值得做的 5 件（排序＋理由）

**前三件可進修補計畫；第四、第五只建議設有停止條件的實驗。**

### 1. 對齊評估器，先停止使用錯位指標決策

本輪實際執行：

```powershell
python -B tools/memory-eval/run.py
```

| 項目 | 本輪結果 |
|---|---:|
| atom 數 | 193 |
| 有效正例 | 175 |
| 負例 | 14 |
| 目標已不在索引、被跳過 | 34 |
| Recall@1 | 64.6% |
| Recall@3 | 91.4% |
| MRR | 0.774 |
| 負例誤命中 | 7.1%，即 1/14 |
| 評估時間 | 約 0.97 秒 |
| Vector | 關閉 |

這些是**舊檢索評估路徑**的結果，不是線上完整管線品質。另有兩處基準不同：[baseline.json:2](C:/Users/holylight/.claude/tools/memory-eval/baseline.json:2) 記錄 Recall@1 約 **67.0%**，而 [TECH.md:326](C:/Users/holylight/.claude/TECH.md:326) 寫 **53.6%**。題目集合又已有 34 條跳過，因此不能直接將數值差異解讀成演算法退步。

最小修改範圍是評估器及必要的檢索／組裝共用入口。量測分三層：

- **候選召回**：預期 atom 是否進池。
- **內容送達**：模型是否真的收到所需正文，不能以 cold／skip 標題代替。
- **任務效果**：固定任務下，帶記憶是否改善答案或工具行為。

先修復失效題目的對應關係，不要一律重新生成題庫，以免把舊難題換掉而得到假進步。

### 2. 把 Supersedes 從「當次候選過濾」改為「全路徑有效性約束」

已重現的合成案例：

> `New` 取代 `Old`，主候選已移除 `Old`；但 `New.Related` 仍指向 `Old`。呼叫現有 `spread_related()` 後，結果重新包含 `Old`。

這是**函式層重現**，不是宣稱正式 session 已發生事故。另一路風險由程式直接可見：若只有舊 atom 命中、新 atom 沒命中，當前 Supersedes 掃描不會讀到新 atom 的取代聲明。

最小設計是從**可見、有效的索引池**建立取代關係，讓直接檢索、Related 與最終輸出共用；鏈式取代、循環與跨 scope 邊需有明確處理。

9 月研究提供了新的支持：在其會暴露舊記錄的 Graphiti 與 mem0 experimental 設定中，錯誤動作為 **699/1,620（43.1%）**；store-level filter 條件為 **0/1,620**。這不證明所有部署都如此，但證明「保存失效標記」與「讀取時確實排除」是兩件事。[原論文 §4](https://arxiv.org/html/2609.08258v1)

### 3. 校準 α/β 的輸入，先不要換晉升公式

本輪對現有 `detect_atom_use()` 做合成測試：

- atom 表示使用兩個舊介面／模式。
- 回合文字明確表示「不要使用，兩者已過時」。
- 函式仍回傳 **`used=true`、containment=1.0**。

因此目前的計數較接近「文字涉及該記憶＋本輪結果」，還不能視為該 atom 的因果效益。先新增一小組**採用、引用、拒用、修正、未知**標註案例，校準這個輸入；不要再加一套 LLM 自評計數替代它。

本輪也核算了現行參數：

\[
LB(3/3,z=1.28)=0.6468
\]

三個成功樣本確實可通過 0.6；但只要成功標籤受到誤歸因，門檻再精密也沒有意義。每日 \(\lambda=0.97\) 的證據半衰期約 **22.76 天**；它降低舊證據權重，**不會自動辨識事實已失效**。

另有一個文件校正：`z=1.28` 約對應 **80% 雙側／90% 單側**，不是註解中的 80% 單側；加上衰減權重及相依樣本，也不宜把這個分數直接宣稱為嚴格校準的事實可信度。[atom_access.py:26](C:/Users/holylight/.claude/lib/atom_access.py:26)

### 4. 用既有 Related 做一跳排序實驗，作為不使用 cross-encoder 的第一選擇

目前真正值得測的不是「有圖 versus 沒图」，而是：

1. Related 關閉。
2. 現有一跳 Related＋歷史 activation 排序。
3. 一跳分數傳播＋query 相關性檢查。

可用下式作為**本地實驗提案，非論文原樣移植**：

\[
s_0=\operatorname{normalize}\!\left(RRF\cdot e^{0.25\,activation\_rank}\right)
\]

\[
s_1=(1-\rho)s_0+\rho P^\top s_0
\]

其中 \(P\) 按每個節點的出邊數正規化，只做一次傳播；\(\rho=0\) 是對照組。作用是避免「連很多張卡的 atom」憑連結數支配结果。

先保持一跳與 1200-token 上限，利用現有 trigger／BM25 訊號；有既存 embedding 的範圍再測語意 gate。**先不要新增全域 embedding 索引，也不要把 Ollama LLM 判斷塞進每次 UPS。**

HippoRAG 2 的 recognition filtering 是可借的概念，但論文使用的抽取／過濾模型是 Llama-3.3-70B，不能據此宣稱本地小模型有相同效果。[論文 §3.4–3.5、Table 2](https://arxiv.org/html/2502.14802v1)

採用門檻：多跳保留題有提升、直接題不退步、干擾注入不增加；若關閉 Related 表現相同或更好，**精簡掉擴散就是合格成果**。

### 5. 先做整併前後對照，再決定是否需要任何新鞏固流程

一般失敗模式萃取已有，睡眠批次也早已評估；不應再以這兩個名稱開新子系統。

只挑已有結果證據、同類問題的少量歷史案例，比較：

- 原 atom；
- 局部增補適用條件／例外；
- 高階策略摘要；
- 無該策略的對照。

量測新增策略是否改善未見過的同類題，及是否傷害原本答對的題。**不能用「產生幾顆 atom」作績效。**

反面證據值得重視：2026 年研究在受測環境中發現，持續文字整併可能劣於不帶記憶；streaming consolidation 相較整批 Pool 出現 **17–38 個百分點**差距。不過該研究部分條件把全部記憶放入 context、重複次數有限，不能直接套算本系統退化程度。[原論文 §3、§8](https://arxiv.org/html/2605.12978v1)

若要執行上述計畫，順序是 **#1 → #2／#3 → #4／#5 實驗**。生產排序的實驗預設關閉；回滾靠恢復既有選擇分支，候選記憶留在待審層、不覆寫來源 atom。這可讓新增複雜度與實證收益綁定。

## 社群負面經驗：哪些已有對策，哪些仍缺

| 負面經驗與來源 | 外部解法／教訓 | 本系統對照 |
|---|---|---|
| **相似搜尋硬湊 top-k**：Cognee 使用者以不相關主題查詢仍拿回 3 個技術片段，指出 nearest 不代表 relevant。[Issue #4462](https://github.com/topoteretes/cognee/issues/4462) | 需要可回空集合的相關性門檻；只有排序、或只標示低信心都不夠。此為特定版本的使用者重現，不泛稱目前所有 backend。 | BM25／vector 已有門檻；**Related gate 缺 query 輸入**，應集中驗證這一路。 |
| **舊事實仍從 MCP 搜尋回傳**：Graphiti 使用者要求 stale-fact filtering 與可配置 reranker。[Issue #1645](https://github.com/getzep/graphiti/issues/1645) | 在讀取路徑真正執行有效性條件。 | 有 Supersedes，但存在 L2 的覆蓋與順序缺口；不需另造衝突系統。 |
| **小抄越整越空**：ACE 記錄 Dynamic Cheatsheet 某一步由 **18,282 tokens→122**，該案例準確率 **66.7→57.1**。[ACE §2.2](https://arxiv.org/html/2510.04618v1) | 局部 delta 更新，避免全量重寫。 | atom 已分項管理，是現成優勢；不應為了「playbook」退回單一大摘要。 |
| **新日期讓舊記憶更可信**：Memory Trust Gap 測 Qwen3 0.6／1.7／4／8B，Benefit suite 對 stale 值的依從率 **0.92–1.00**。[論文](https://arxiv.org/html/2609.01852v1) | 小模型尤其需要在生成前解決衝突；只加 metadata 並不總有效。 | 不宜把更高 activation 或更新 timestamp 當成事實更正確。有效性應先於排序。 |
| **token 稅／注入過多** | 舊調查已涵蓋硬預算、去冗、按需載入。 | **不新增同名量測**。現有報表的「token 稅」主要抓高曝光零使用；它仍可能漏掉「確實被使用、卻令答案更差」的記憶，因此需 #3 的配對效果量測。[報表定義](C:/Users/holylight/.claude/tools/memory-effect-report.py:10) |

## 明確不建議做的（＋為什麼）

- **不再提「新增 spreading activation」**：已有一跳傳播。只驗證 query-aware 排序與關閉對照，不先加深度或圖資料庫。
- **不新增一般反模式／失敗記憶子系統**：現有格式已包含場景、錯誤、正解、根因；ReasoningBank 的一般功能高度重疊。
- **不把 ACE 的 helpful／harmful 計數另做一套**：已有 α/β；優先校準使用與結果的歸因。
- **不換成 MemoryBank 遺忘曲線、不把曝光當學會**：已有更貼近用途的效用調整與可逆隔離，未查到第二套衰減的增量證據。
- **不全面安裝 Mem0、Graphiti、Cognee、MemOS 或訓練 Mem-α**：遷移、服務及模型成本均超出已證實需求。
- **不每輪反思或整庫重寫**：既有調查已提整併，本輪反而找到應限制整併的新證據。
- **不直接用 2026 新論文的 LLM confidence 更新 Related 權重**：REALM 的方法有研究價值，但本地歸因尚未可靠；先防止錯誤反馈自我強化。
- **不將不同论文榜單數字混排**：LoCoMo judge、F1、AppWorld 複合平均、NPC 可信度及 TTFT 測的是不同事。

## 未查到／不確定的

1. **沒有本系統採用新演算法後的準確率提升數字。** 本輪只執行既有回歸與兩個合成案例；未跑跨模型 QA，也未新增 Ollama 推論。
2. **Supersedes 回流與拒用誤歸因的正式 session 發生率未查到。** 函式機制已重現，實際影響仍須回放日志。
3. **未證實本地小模型 recognition filter 的品質與延遲。** 因此不把它當成已成立的輕量 rerank 替代品。
4. **MemoryBank 遺忘項、Cognee 擴散後重評分的獨立效益數字未查到。** 不用整套框架分數替代單一機制證據。
5. **現有 14 條負例不足以證明低誤注入率。** 而且它們多是天氣、翻譯等明顯域外題；應補「詞彙相近但不適用」、舊版本、歷史查詢、否定及跨 scope 題。
6. **本輪未修改檔案或系統。** 已完成唯讀驗證與可供主持者彙整的實作順序；目前環境為唯讀，不能進行上述修補。

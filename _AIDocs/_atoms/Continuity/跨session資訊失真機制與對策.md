# 跨session資訊失真機制與對策

- Scope: global
- Author: holylight
- Confidence: [觀]
- Trigger: 失真, 失憶, context 壓縮, 長對話, 多 session, lost in the middle, context rot, goal drift, 摘要有損, 為什麼會偏掉, anchoring, context poisoning, 錯誤發展, 錯誤認知, 記憶汙染, 知識汙染, 上下文腐化, selective forgetting
- Created-at: 2026-06-18
- Related: handoff-綜觀品質與抗失真寫法, feedback-workflow-discipline, decisions-architecture, cognitive-patterns, decisions, realm-範疇分區機制-v5, 跨session協調-衝突預警機制與cc原生現況

## 知識

- [觀] **跨 session 失真的根因不是「模型變笨」、是「變不穩」**：多輪 vs 單輪平均掉 39%，主因是 unreliability +112%、aptitude 僅 -16%；且強模型一樣不穩 → **換更強的模型救不了多-session 失真**，唯一可靠的防線是 handoff/續接文件的寫法本身。（Microsoft-Salesforce, arXiv 2505.06120）
- [觀] 失真是多機制疊加，非單一現象；下表逐機制給「寫 handoff 時可直接套用」的對策：

| 機制 | 一句話原理 | 對策（寫/讀 handoff 時） |
|---|---|---|
| M1 Lost-in-Middle | 注意力呈 U 形，關鍵資訊移到中段準確率可掉 >30% | 關鍵約束/否定條件放文件**首尾**，別埋中段 |
| M2 Context Rot | 遠在視窗上限前即退化（200K 視窗常 50K 就劣化） | 文件自足精簡，**不挾帶**原始長 transcript |
| M3 Lossy Summary | 壓縮誘發「填補空缺式」幻覺 | 標「此為壓縮、可能有損」；load-bearing 數值/路徑**逐字保留** |
| M4 Recency 過載/Distraction | 過度倚賴近期歷史、傾向重複舊動作而非合成新計畫 | 主目標放高權重區並**週期重申**，別堆積歷史動作日誌 |
| M5 Anchoring | 資訊不全時過早鎖死假設、新證據進來也不修正 | 標「假設 vs 已驗證」，未驗證項勿當 anchor |
| M6 Goal Drift | 多輪漸偏主目標（goal reminder 是最有效解，judge +16%） | 首段固定主目標、續接者每隔數步回讀 |
| M7 Compounding | 早期小錯級聯滾雪球，且步錯率隨任務進度上升 | 交接前**驗證再傳**、標 ✓/✗ 斷開錯誤被下游引用 |
| M8 Context Poisoning | 幻覺寫進高權重區後被反覆引用、自我強化（最頑固） | 隔離「事實 vs 推測」；高權重區（目標/狀態）只放已確認 |
| M9 Context Clash | context 內新舊矛盾，模型任選一個且一樣自信 | 顯式裁決「以 X 為準、作廢 Y」＋時間戳，不並列 |
| M10 Omission/Confusion | 漏寫的前提被下游腦補；冗餘工具/資訊也會被誤用降品質 | 顯式列出隱含前提（環境/版本/路徑/已試過的）；只帶相關背景 |

- [觀] **可量測警訊（handoff 高失真風險信號）**：挾帶完整舊 transcript 而非精煉結論、主體是「摘要的摘要」(多代轉述)、通篇陳述句無 verified/assumption 區分、找不到顯式主目標區、新舊指示並列無時序裁決、依賴未寫出的環境/路徑前提。自動化偵測方向：對「原始意圖」的語意距離/KL 逐 turn 上升且無 restoring → drift 失控，可作記憶系統的 drift gate。
- [觀] **學門分層與記憶治理定位**：Context Engineering（塞什麼進視窗，Anthropic「最小高訊號 token 集」）／ Agent Memory Management·Memory Governance（長期記憶庫的形成·檢索·遺忘·汙染·漂移治理，本記憶系統屬此）／人類根理論 Cognitive Load Theory（extraneous load＝無關材料拖垮處理）。對策核心非省 token，而是 selective forgetting + relevance gating + 最小高訊號集——**避免汙染 > 省 token**。全貌見 `_AIDocs/context-memory-governance.md`。
- [觀] **landmark 來源**：Lost-in-the-Middle (arXiv 2307.03172)、LLMs Get Lost in Multi-Turn Conversation (2505.06120)、Context Rot (Chroma)、Anthropic 工程文 effective-context-engineering / effective-harnesses-for-long-running-agents。Drew Breunig 4 失效模式（poisoning／distraction／confusion／clash）≒ M8／M4／M10／M9 的別名子集。寫法守則落地見 [[handoff-綜觀品質與抗失真寫法]]。

## 行動

- 寫/讀 handoff 時對照 10 機制逐一套對策（首尾放約束、標 ✓/✗、顯式裁決矛盾、週期重申主目標）
- 不靠「換更強模型」解多-session 失真——靠文件寫法本身
- 大型/多 session 任務感覺偏離時自檢四問：① 這條 context 是高訊號還是 distractor？② 有無被前面的錯誤/摘要 poison？③ 有無與現有資訊 clash？④ 範圍是否在縮小（distraction）？
- 設計/改記憶系統注入·萃取 hook：注入做 relevance gate + 最小高訊號集裁切；萃取寫 atom 前先過「這是實證還是幻覺/臆測」的 poisoning gate；衰減做過期低效用主動隔離（selective forgetting）。既有 anti-pollution DNA：ReadHits 降純曝光、不參與晉升。
- (記憶系統可選) 把「主目標語意距離逐 turn 上升且無 restoring」做成自動 drift gate

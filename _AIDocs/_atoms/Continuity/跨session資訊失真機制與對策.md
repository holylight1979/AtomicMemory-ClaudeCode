# 跨session資訊失真機制與對策

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 失真, 失憶, context 壓縮, 長對話, 多 session, lost in the middle, context rot, goal drift, 摘要有損, 為什麼會偏掉, anchoring, context poisoning, 錯誤發展, 錯誤認知
- Created-at: 2026-06-18
- Related: handoff-綜觀品質與抗失真寫法, feedback-workflow-discipline, decisions-architecture

## 知識

- [臨] **跨 session 失真的根因不是「模型變笨」、是「變不穩」**：多輪 vs 單輪平均掉 39%，主因是 unreliability +112%、aptitude 僅 -16%；且強模型一樣不穩 → **換更強的模型救不了多-session 失真**，唯一可靠的防線是 handoff/續接文件的寫法本身。（Microsoft-Salesforce, arXiv 2505.06120）
- [臨] 失真是多機制疊加，非單一現象；下表逐機制給「寫 handoff 時可直接套用」的對策：

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

- [臨] **可量測警訊（handoff 高失真風險信號）**：挾帶完整舊 transcript 而非精煉結論、主體是「摘要的摘要」(多代轉述)、通篇陳述句無 verified/assumption 區分、找不到顯式主目標區、新舊指示並列無時序裁決、依賴未寫出的環境/路徑前提。自動化偵測方向：對「原始意圖」的語意距離/KL 逐 turn 上升且無 restoring → drift 失控，可作記憶系統的 drift gate。
- [臨] **landmark 來源**：Lost-in-the-Middle (arXiv 2307.03172)、LLMs Get Lost in Multi-Turn Conversation (2505.06120)、Context Rot (Chroma)、Anthropic 工程文 effective-context-engineering / effective-harnesses-for-long-running-agents。寫法守則落地見 [[handoff-綜觀品質與抗失真寫法]]。

## 行動

- 寫/讀 handoff 時對照 10 機制逐一套對策（首尾放約束、標 ✓/✗、顯式裁決矛盾、週期重申主目標）
- 不靠「換更強模型」解多-session 失真——靠文件寫法本身
- (記憶系統可選) 把「主目標語意距離逐 turn 上升且無 restoring」做成自動 drift gate

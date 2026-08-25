# grok協作實戰認知-特質與監工分工手感

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: grok 特質, 跟 grok 合作, 雙 LLM 分工, 監工 grok, grok 水位, grok 交接, 派工給 grok, grok 可信度
- Created-at: 2026-08-25
- Related: 並行llm即時通訊-inbox機制, workflow-parallel-agents, 歸因早停-找到合理嫌疑機制就停止驗證, commit-前必須核對-staged-清單而非只信自己-add-了什麼

## 知識

- [臨] **Grok 4.6 實戰特質（MudClient 戰役 70+ 封實證）**：實證紀律極穩（已驗證/推測/不猜全程沒掉）、盤點零事實錯誤、會主動修正我的假設（拒步樣式、hook 欄位名、ReindexNames 過時）、自主連跑可靠（三主幹一次跑完）、遇異常會自己停。弱點：沒被要求時們向保守到逐步等 ack；水位從 35%→一個 Phase 能吃到 75%，長戰役必須預排 session 切換（它寫自己的交接進原生記憶＋規則檔自載，新 session read-back 兩次均滿分）。
- [臨] **監工 80/20 實战手感**：全戰役我零行親手改碼，只改一行過時註解；價值在裁決與抄捕：否決寬觸發、抄到 Core 複製 arion 字面值、抄到 settings.json 持久化蓋預設、親讀逐字稿抓到真根因。**設計先行（提案→裁決→實作）對大改動極有效**；小改動直接派。
- [臨] **我自己的誤判模式（記下防再犯）**：guardian MCP 連線案兩輪歸因（wrapper std handle、hooks 風暴）均被後續證據推翻→同條件一綠一紅就是非決定性，該停追；`git add 目錄` 擈進 5.9MB 輸出——印了 135 却照 commit（既有 atom 再犯）；逐段 ack 讓一天 70+ 封信。納入 [[feedback-高速推進每步跨大-禁越執行越偏細節越耗時]] 與 [[feedback-每輪重新校準全盤現況與偏移指標-inbox來回易帶偏風向]]。

## 行動

- 派工 Grok：整 Phase 一次講完，明言「不必等 ack、異常才停」
- Grok 水位 ≥ 70% 或大仗前→要它寫交接＋新 session prompt，使用者重開面板
- 它的報告可信但仍抽驗引用碼位與 diff（它也會漏列改過的檔）

# feedback-原子記憶不內建預設會有下一個session的行為-接續單只是全AI執行升級的特例不是標竿

- Scope: global
- Author: holylight
- Source: 原設計者 2026-10-20 晚 AskUserQuestion 答覆（T2.15 否決）
- Confidence: [臨]
- Trigger: 下一個 session, 自動匯出接續單, next-phase-auto, 目標樹跨 session, 收尾自動匯出, 預設有下個 session, 不內建, 原設計者否決
- Created-at: 2026-10-20
- Quote: 「該收割的知識與經驗都好了我就關掉。」

## 知識

- [臨] 原設計者原話（否決「收尾時目標樹有補充或糾正就自動匯出接續檔、下個 session 自動接上」的提案）：「我不允許原子記憶內建這種『預設會有下一個 session 的行為』，原因我很久以前就說過了。這次升級可以這樣是因為本就全 AI 執行、判定細節、且被大量使用者使用後反饋，並不代表這操作再專案、或其他範圍，可以成為未來的標竿。」
- [臨] 判法：驗收或設計時看到「換 session 後樹沒跨過去」，那是預期行為，不是缺口；不要再提任何「收尾自動為下個 session 留東西」的機制。人要接續時自己叫 /handoff。

## 行動

- 提案任何「自動為下個 session 準備」的機制前：停，這條已被原設計者否決；跨 session 接續只走人主動的 /handoff

# context將滿時把同一批檔的多條改動交給單一子代理照序做-續派用SendMessage保留它的context-主session只做獨立複核與轉交

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: context 快滿, context 80%, 派子代理實作, general-purpose, 續派子代理, SendMessage 子代理, 子代理 commit, 獨立複核, 換手
- Created-at: 2026-10-13
- Source: session:c4685bc9 2026-10-13
- Quote: 「你是 v6.0 的工作 session track-goal（需求目標核心流程設計單，只設計不寫程式），總控台是 claude-ad。第一步用 EnterWorktree 切進 worktree C:\Users\holylight\.claude-wt\track-goal（分支 v6/track-goal，已存在，不要新建）。派工 prompt 在 C:\Users\holylight\.c…」

## 知識

- [臨] 實作量大、自己 context 已七成多時：把工作交給一個 general-purpose 子代理在同一 worktree、同一分支照序做（每條規則一 commit）。改動集中在同一批檔時只派一個，不平行派多個（同檔互相覆蓋）。prompt 要自足：目標原話、要讀的檔、每條規則的實作方向、測試與反證做法、量測指令、環境地雷、回報格式。
- [臨] 後續的裁定與追加工作（例：放寬某條判斷、跑 codex 初審並處理）用 SendMessage 續派同一個子代理——它保留完整 context，比重派省很多；主 session 只做獨立複核（git status、自己重跑 verify 與量尺、抽看關鍵入口）與最後轉交，自己的 context 不被實作細節吃掉。
- [臨] 交付信要寫明哪些 commit 是子代理做的、主 session review 時改了什麼、自己獨立複核了哪些數字；review 只抽看關鍵段時照實寫『抽看』，不寫成逐行審過。

## 行動

- 自己 context 不夠完成整件時：先派單一子代理照序實作，再用 SendMessage 續派同一個
- 交付註明子代理 commit 與主 session 的複核範圍

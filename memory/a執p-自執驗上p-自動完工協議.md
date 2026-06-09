# A執P 自執驗上P 自動完工協議

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: A執P, 自執驗上P, Auto執驗上P, 自動執驗上P, 全自動完工, 自動推進, auto-handoff, 自動交接
- Created-at: 2026-06-09
- Related: workflow-rules, feedback-workflow-discipline, preferences

## 知識

- [臨] A執P / 自執驗上P / Auto執驗上P =「自動推進需求的徹底執行」：在 執驗上P（執行→驗證→上GIT→產Prompt）之上加「自動連續推進 + 全套自檢/記錄/同步/通知」的最高完工標準。
- [臨] 七要素：① 每階段自檢 ② 以現存或模擬資料**實測**驗證無誤（非紙上推斷）③ 自我檢討 ④ 經驗文件記錄（_AIDocs/Failures 等）⑤ 人讀文件同步（Architecture/_CHANGELOG/TECH）⑥ 通知使用者 ⑦ 待命上傳（SVN 或 GIT，依環境）。
- [臨] 與 執驗上P 關係：執驗上P 是單階段收尾四步；A執P 是跨階段自動推進、每階段跑滿執驗上P、再疊加自檢/實測/記錄/同步/通知的自動化超集。
- [臨] 機制地基：Auto-Handoff 四層（PreCompact L2 自動 stub / PostToolBatch L3 補全 / Stop L1 token 預警 / SessionEnd L4 兜底，見 Architecture「Auto-Handoff 四層自動交接」段）提供跨 session 無損交接 stub。「全自動 spawn 新 session」終極形態靠 Phase 4 外部 watcher（claude -p headless），超出 hook 能力、實驗性。

## 行動

- 使用者說「A執P」「自執驗上P」「Auto執驗上P」→ 按七要素徹底執行，不可只做 執行+上傳就宣告完成
- 實測驗證必用現存或模擬資料真跑，不可紙上推斷
- 收尾走 IDENTITY (a)(b)(c)(d) 全項檢視 + 人讀文件同步
- 保育期過後按 confirmations / 效用門檻手動晉升 [臨]→[觀]

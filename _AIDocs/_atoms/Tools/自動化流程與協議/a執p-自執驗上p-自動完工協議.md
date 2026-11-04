# A執P 自執驗上P 自動完工協議

- Scope: global
- Author: holylight
- Source: commit:c86b1e9 2026-06-09（原對話已逾保留期）
- Confidence: [臨]
- Trigger: A執P, 自執驗上P, Auto執驗上P, 自動執驗上P, 全自動完工, 自動推進, auto-handoff, 自動交接, /goal, 長任務續跑
- Created-at: 2026-06-09
- Related: workflow-rules, feedback-workflow-discipline, preferences, handoff-綜觀品質與抗失真寫法

## 知識

- [臨] A執P / 自執驗上P / Auto執驗上P =「自動推進需求的徹底執行」：在 執驗上P（執行→驗證→上GIT→產Prompt）之上加「自動連續推進 + 全套自檢/記錄/同步/通知」的最高完工標準。
- [臨] 七要素：① 每階段自檢 ② 以現存或模擬資料**實測**驗證無誤（非紙上推斷）③ 自我檢討 ④ 經驗文件記錄（_AIDocs/Failures 等）⑤ 人讀文件同步（Architecture/_CHANGELOG/TECH）⑥ 通知使用者 ⑦ 待命上傳（SVN 或 GIT，依環境）。
- [臨] 與 執驗上P 關係：執驗上P 是單階段收尾四步；A執P 是跨階段自動推進、每階段跑滿執驗上P、再疊加自檢/實測/記錄/同步/通知的自動化超集。
- [臨] 機制地基：長任務自動連續推進目前用原生 `/goal <完成條件>`（另一個模型每回合後檢查條件，Claude 持續做到達成），條件寫成可檢查的結果（例：目標測試全綠＋文件同步）。自製外部 watcher（`tools/auto-continue/`）已刪：原生補上了同一能力。跨 session 交接仍靠 Auto-Handoff 四層（見 Architecture「Auto-Handoff 四層自動交接」段）。

## 行動

- 使用者說「A執P」「自執驗上P」「Auto執驗上P」→ 按七要素徹底執行，不可只做 執行+上傳就宣告完成
- 要無人值守連續推進 → 建議用 /goal，完成條件寫成可檢查的結果
- 實測驗證必用現存或模擬資料真跑，不可紙上推斷
- 收尾走 IDENTITY 收尾誠實四要素 + 人讀文件同步

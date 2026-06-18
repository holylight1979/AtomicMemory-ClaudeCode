# A執P 自執驗上P 自動完工協議

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: A執P, 自執驗上P, Auto執驗上P, 自動執驗上P, 全自動完工, 自動推進, auto-handoff, 自動交接
- Created-at: 2026-06-09
- Related: workflow-rules, feedback-workflow-discipline, preferences, handoff-綜觀品質與抗失真寫法

## 知識

- [臨] A執P / 自執驗上P / Auto執驗上P =「自動推進需求的徹底執行」：在 執驗上P（執行→驗證→上GIT→產Prompt）之上加「自動連續推進 + 全套自檢/記錄/同步/通知」的最高完工標準。
- [臨] 七要素：① 每階段自檢 ② 以現存或模擬資料**實測**驗證無誤（非紙上推斷）③ 自我檢討 ④ 經驗文件記錄（_AIDocs/Failures 等）⑤ 人讀文件同步（Architecture/_CHANGELOG/TECH）⑥ 通知使用者 ⑦ 待命上傳（SVN 或 GIT，依環境）。
- [臨] 與 執驗上P 關係：執驗上P 是單階段收尾四步；A執P 是跨階段自動推進、每階段跑滿執驗上P、再疊加自檢/實測/記錄/同步/通知的自動化超集。
- [臨] 機制地基：Auto-Handoff 四層（PreCompact L2 自動 stub / PostToolBatch L3 補全 / Stop L1 token 預警 / SessionEnd L4 兜底，見 Architecture「Auto-Handoff 四層自動交接」段）提供跨 session 無損交接 stub。「全自動 spawn 新 session」終極形態＝Phase 4 外部 watcher（`tools/auto-continue/`，超出 hook 能力、實驗性·非正式上線）。
- [臨] Phase 4 **已實證+PoC 完成**：`claude -p "/continue"` headless **確實執行 slash-command skill**（VSCode 擴充套件 binary 2.1.169 實跑：is_error:false、result 為 /continue skill 原文、非 prompt 透傳；查證法見 [[cc-能力查證反編譯實跑-binary]]）。watcher 監看 `resolve_staging_dir` next-phase*.md → spawn /continue → 寫新 stub 遞迴，四道 guard（max_consecutive_spawns / budget_usd / confirm_every_n / kill_switch）＋ single-stub 不變式。spawn 須接 stdin DEVNULL（避 3s 卡）；自主接續需 `--permission-mode bypassPermissions`，blast radius 由 guard 界定。用法/風險見 `tools/auto-continue/README.md`。

## 行動

- 使用者說「A執P」「自執驗上P」「Auto執驗上P」→ 按七要素徹底執行，不可只做 執行+上傳就宣告完成
- 實測驗證必用現存或模擬資料真跑，不可紙上推斷
- 收尾走 IDENTITY (a)(b)(c)(d) 全項檢視 + 人讀文件同步
- 保育期過後按 confirmations / 效用門檻手動晉升 [臨]→[觀]

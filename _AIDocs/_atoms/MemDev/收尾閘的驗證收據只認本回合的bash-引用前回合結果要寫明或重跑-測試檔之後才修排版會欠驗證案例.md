# 收尾閘的驗證收據只認本回合的Bash-引用前回合結果要寫明或重跑-測試檔之後才修排版會欠驗證案例

- Scope: global
- Author: holylight
- Source: session:23787466 2026-10-13 track-g12
- Confidence: [臨]
- Trigger: ReconcileGate, 收尾閘, 驗證收據, 本回合, 重跑過, 改碼欠驗證案例, 收尾放行確認, 測試檔之後改碼
- Created-at: 2026-10-13
- Related: 使用者放行的判定要防偽造-只認tool-use-id對到askuserquestion的答案-打字放行要整句嚴格比對-跨回合要承接

## 知識

- [臨] ReconcileGate (c)：收尾文字說「跑了／重跑過」，但本回合沒有任何 Bash／PowerShell 執行就擋；它只認本回合 PostToolUse 落帳的收據，不認前一回合跑過的。實例：前一回合 verify 348 passed，下一回合收尾寫「修完空白後 verify 重跑過」→ 被擋。解法：引用前回合結果時寫明「前一回合跑的」，或本回合重跑一次。
- [臨] ReconcileGate (d)：最後一次改測試檔之後又改程式檔（即使只補兩個排版空白）就算「改碼欠驗證案例」，義務跨回合追。純排版修正寫不出會紅的案例，只能被擋時走 AskUserQuestion 放行，同一件事一個 session 問了兩次。避法：所有程式修正（含複查 diff 抓到的排版）都做完，再做最後一次測試檔修改與重跑。

## 行動

- 收尾提到驗證結果：本回合沒跑就寫明是前回合的，或當場重跑
- 排版修正排在最後一次改測試檔之前做完

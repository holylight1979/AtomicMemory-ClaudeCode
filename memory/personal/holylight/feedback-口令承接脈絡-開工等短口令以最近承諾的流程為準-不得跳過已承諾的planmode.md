# feedback-口令承接脈絡-開工等短口令以最近承諾的流程為準-不得跳過已承諾的PlanMode

- Scope: personal:holylight
- Author: holylight
- Confidence: [臨]
- Trigger: 開工, 動工, 口令歧義, plan mode, 先出計畫, 誤讀指令, 承諾流程
- Created-at: 2026-09-02
- Source: unknown 2026-09-02（原對話已逾保留期）

- Related: feedback-預計畫文件先改到使用者認可才進planmode定執行細節-不是收到校正就馬上進planmode

## 知識

- [臨] 實踩：AI 前一輪承諾「我會先進 Plan Mode 出計畫再改」，使用者回「…然後就開工」。AI 讀成「跳過計畫直接實作」並改完 7+ 檔；使用者事後更正：「開工」是指「照你說的進 Plan Mode」。
- [臨] 教訓：使用者的簡短口令（開工/動工/去做/開始吧）是在**承接 AI 最近一次自己宣告的流程**，不是覆蓋它。自己剛承諾過的步驟（Plan Mode、先驗證、先備份）不因短口令而豁免；要跳過必須使用者明說。

## 行動

- 收到「開工」類短口令→先檢查自己上一輪是否承諾過流程步驟，有則照承諾走
- 架構級/core 多檔任務：宣告會進 Plan Mode 就真的進，不自行降級為直接實作

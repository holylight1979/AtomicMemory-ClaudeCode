# 總控台收尾被main既有紅測連擋時-請負責軌把那個修正單獨commit再cherry-pick進main-不自己改碼不找人放行

- Scope: global
- Author: holylight
- Source: session 7b0c2e17 2026-10-22 調度總控台（main 2df228f3 cherry-pick 自 gate-fixes-007 2dcab66f）
- Confidence: [臨]
- Trigger: TestFailGate, 測試未綠, 既有紅測, 基底就紅, 總控台收尾被擋, cherry-pick, 單獨 commit, 連擋
- Created-at: 2026-10-22
- Related: feedback-閘門反覆擋同一件事時要修判定的根因-不要一再請使用者放行

## 知識

- [臨] 現象：總控台在合併後的 live 跑到一支 main 上本來就紅的測試，收尾的「測試未綠」閘就把它算成本回合欠帳；總控台不自己改碼、原設計者也沒說跳過，照實寫「還紅」也解不開，實測連擋 6 次。
- [臨] 解法：請正在跑的負責軌先把那個修正單獨 commit（只含這件、附兩種跑法收據），總控台 cherry-pick 進 main、重跑轉綠後推；該軌之後合 main 時同一筆自動對掉。不自己改碼、不發放行題。
- [臨] 根因修法已裁（對人總控台 #61）：閘加有名規則「基底就紅且已派工的紅測不算本回合欠帳」，排閘小修 008；上線前用上面的解法。
- [臨] 順帶：多支驗證合成一條指令又用 tail 截斷，閘看不出哪支紅、會多算一項；各支分開跑。

## 行動

- 合併前先在 main 跑目標 verify，分清「基底就紅」與「合進來才紅」
- 基底就紅 → 當下請負責軌單獨 commit 修正，cherry-pick 進 main

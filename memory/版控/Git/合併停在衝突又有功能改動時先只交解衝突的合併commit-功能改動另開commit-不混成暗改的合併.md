# 合併停在衝突又有功能改動時先只交解衝突的合併commit-功能改動另開commit-不混成暗改的合併

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 合併衝突, merge commit, 暗改合併, evil merge, 解衝突, 功能改動分開 commit
- Created-at: 2026-10-27
- Related: 解合併衝突兩側都留只對純加法段成立-hunk切在函式中段會吃掉共用尾行-改用main版加分支尾段重建-解完必跑該檔verify不只py-compile
- Source: session:17c8cd5c#840617df 2026-10-27

## 知識

- [臨] 合併停在衝突、手上同時有功能改動時，不要把功能改動一起放進合併 commit：審合併的人只看衝突段，夾帶的改動沒人看到，日後也追不到是誰在哪一步改的。
- [臨] 做法：自動合好的檔已在 index，不動；衝突檔先暫寫成只含解衝突結果的版本，git add 後 commit 完成合併；再把完整內容（含功能改動）寫回，另一個 commit 交。

## 行動

- 合併 commit 只放解衝突結果
- 功能改動在合併完成後另一個 commit

# 測試要假造版控提交時間-svn用svnadmin-setrevprop改svn-date後重新checkout-git用author與committer-date-幾版設同一刻可證明比的是版號

- Scope: global
- Author: holylight
- Source: hooks/verify/verify_health_selftests.py（commit 4831257d）
- Confidence: [臨]
- Trigger: svnadmin, setrevprop, svn:date, GIT_COMMITTER_DATE, 提交時間, fixture, 假造日期, 測試 repo
- Created-at: 2026-10-29
- Related: svn測試與hook的三個實測事實-diff3相鄰改動自合-整wc-status爆預算-只信xml輸出
- Quote: 「有沒有要收割的經驗知識? 應該可以關 session 了齁?」

## 知識

- [臨] svn：`svnadmin setrevprop <repo> -r N svn:date <檔>`（檔內 UTC ISO，例 `2026-05-05T04:00:00.000000Z`），不需 pre-revprop-change hook；工作副本在 commit 時就記下日期，改完要重新 checkout 才看得到。
- [臨] 新 checkout 的檔 mtime＝現在、版控日期＝假造的舊日，正好重現「這台剛 update」。
- [臨] 把幾版的 svn:date 設成同一刻 → 時間分不出先後，只剩版號，可證明程式比的是版號。git 用 GIT_AUTHOR_DATE＋GIT_COMMITTER_DATE，commit 加 `-c commit.gpgsign=false` 免得他機設定擋住。

## 行動

- 寫依版控時間判斷的測試：用本機 svnadmin create＋file:// 建真 repo，沒裝 svn 就 skip

# feedback-svn-commit-一律先問使用者確認-計畫核准不等於上版授權

- Scope: global
- Author: holylight
- Confidence: [固]
- Trigger: svn commit, 上SVN, 上版, commit 授權, 計畫核准, ExitPlanMode, 驗證完就上, 不先問就 commit, 上傳必經明確授權, svn status, sgi_server, sgi_client, Tools/, 順手修, 同事回報, 文件修正, README, 註解, SVN 資料夾
- Created-at: 2026-08-28
- Related: workflow-svn, feedback-收尾工作樹要上乾淨-該上就上-用不到就刪-不反問, feedback-svn-上傳必經明確授權

## 知識

- [固] **硬規則（使用者 2026-08-28 明訂）**：此專案下，任何屬於 SVN 版控資料夾（`sgi_server/` `sgi_client/` `Tools/`）內的異動，**一律要等使用者驗證、確認過，且明確說「上SVN」才可以 commit**；沒經過同意一律不可以上。**不分異動大小與性質**——程式碼、README、註解、文件、一行修字都算；「已自驗正確」「只是文件」「同事等著用」「跟剛上的那版同主題順手補」都不是豁免。
- [固] 計畫核准＝授權做工，不＝授權上版；同一 session 前半段的「上GIT & 上SVN」不延伸到後半段新任務；使用者要在看到驗證結果後自己說「上SVN」。git（_AIDocs/.claude）也依使用者當場指示；沒說就一樣問。
- [固] 再犯紀錄（同日兩次，證明「我知道規則」不等於「會停手」）：① r15343——計畫第 9 步寫「SVN commit」、計畫獲核准，驗證完直接送，使用者：「SVN 不是都要經過我再次確認才可以上嗎」。② 同日 r15352——同事回報 README 漏改兩態，我改完 README＋Program.cs 註解後把 svn commit 直接串進同一個 Bash 指令送出，事後才報告；使用者再次明訂上方硬規則。共同根因：把「修正明顯正確／驗證已綠」當成上版授權，且 commit 混在多步指令裡、沒有獨立的停點。更早的 r1159（2026-06-10 DevTeamShare）同型。

## 行動

- 改到 SVN 資料夾內任何檔案後：驗證 → `svn status` 列出 M/A 清單 → 停在「以上待你確認後說『上SVN』」；**不得**把 `svn commit` 寫進與修改／驗證同一個指令串
- 使用者說「上SVN」才 commit，且只送他確認過的那份清單；commit 訊息一律 `--encoding UTF-8 -F <utf8檔>`
- 「同事在等」「跟剛上的同主題」「只是文件」→ 仍照上一條停點，不豁免

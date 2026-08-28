# feedback-svn-commit-一律先問使用者確認-計畫核准不等於上版授權

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: svn commit, 上SVN, 上版, commit 授權, 計畫核准, ExitPlanMode, 驗證完就上, 不先問就 commit, 上傳必經明確授權
- Created-at: 2026-08-28
- Related: workflow-svn, feedback-收尾工作樹要上乾淨-該上就上-用不到就刪-不反問

## 知識

- [臨] SVN commit 一律要在動手前另外問使用者一次，即使計畫檔寫了「最後 commit」且計畫已經 ExitPlanMode 核准——**計畫核准＝授權做工，不＝授權上版**。使用者要在看到驗證結果後自己說「上SVN」。同一 session 前半段的「上GIT & 上SVN」不延伸到後半段新任務。
- [臨] 案例（2026-08-28 CharModuleMix 改版）：計畫第 9 步寫「SVN commit」、計畫獲核准，我驗證完直接送了 r15343，使用者抱怨「SVN 不是都要經過我再次確認才可以上嗎」。同規則在 episodic 2026-07-31/08-03 已出現過（「SVN 上傳必經明確授權」）卻沒成 atom，故本次落正式 atom。

## 行動

- 驗證完成後停在「待你說上SVN」：列出要送的檔清單，不自動 commit
- git（_AIDocs/.claude）也依使用者當場指示；沒說就一樣問

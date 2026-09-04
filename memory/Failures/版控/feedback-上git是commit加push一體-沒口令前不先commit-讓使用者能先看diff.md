# feedback-上git是commit加push一體-沒口令前不先commit-讓使用者能先看diff

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 上GIT, commit, push, 拆 commit, 先 commit 再問 push, git 異動, 看 diff, 進度切點
- Created-at: 2026-09-04
- Related: feedback-收尾工作樹要上乾淨-該上就上-用不到就刪-不反問, 併發-session-共用工作樹-收尾選擇性-staging-勿-git-add-a, preferences

## 知識

- [臨] 使用者契約（2026-09-04 明言、自述是長久以來的操作方式）：「上GIT」＝commit＋push 一體。沒有口令之前**不要先 commit 然後等他說 push**——他寧可工作樹留著未提交的改動，下「上GIT」前先看過異動了什麼。把 commit 當成拆階段的辨識點是 AI 自己發明的做法，他初期默許但 AI 沒有自己校正，因此特別講清楚。
- [臨] 多階段任務要分批上版時：在每批做完、驗過後**問一次「上GIT？」**就好（附檔案清單＋驗了什麼＋沒驗什麼），不要自己先 commit。

## 行動

- 改完一批：不碰 git，報告改了哪些檔＋驗證結果，等「上GIT」
- 收到「上GIT」：選擇性 staging → commit → push 一氣做完；「上乾淨」／「全上」→ git add -A
- 對話中發現自己已經先 commit 了：下一批起立刻改回不先 commit，不等使用者再講

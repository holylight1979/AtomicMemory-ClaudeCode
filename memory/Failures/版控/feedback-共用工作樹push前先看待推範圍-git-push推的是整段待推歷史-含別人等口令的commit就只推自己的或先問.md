# feedback-共用工作樹push前先看待推範圍-git-push推的是整段待推歷史-含別人等口令的commit就只推自己的或先問

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: git push, push 前, 待推範圍, origin/main..HEAD, 連帶推出, 共用工作樹, 別人的 commit, 等口令
- Created-at: 2026-10-14
- Related: 併發-session-共用工作樹-收尾選擇性-staging-勿-git-add-a, git-已push-commit-勿改寫-雙-push-url-gitlab-main-force-保護致遠端分叉
- Source: session:8f368a10#99aa6d5b 2026-10-14
- Quote: 「再收割一次知識與經驗?」

## 知識

- [臨] 選擇性 staging 只管得到 commit，管不到 push：`git push` 推的是本機分支整段待推歷史。共用工作樹裡別的 session 已 commit、正在等使用者口令的 commit，會跟著自己那筆一起推出去；快轉推出後撤不回來。
- [臨] 實例：只想推自己 1 筆功能 commit，連帶推出約 50 筆（含總控台的 v6 合併與待驗 fix）。背景記憶同步早在 Logs/vcs-sync.log 寫了「待推歷史含非記憶 commit…待使用者上GIT 一起推」，它是刻意壓著不推的。對人總控台裁定不補救（快轉無 force、往前修），教訓入卡。
- [臨] 規則：push 前先看 `git log --oneline origin/main..HEAD`。待推段只有自己的 commit 與記憶收割 commit 才推；含別人的程式 commit 就只推自己的，或先問總控台／使用者。
- [臨] 再犯：對人總控台推一筆原話輯文件，把工作軌五個還沒跑全量的 commit 一起帶上 GitHub。總控台推任何東西前同樣要先看 git log origin/main..main；有別人的 commit 就交給調度推。

## 行動

- git push 前先 git log --oneline origin/main..HEAD
- 待推段含別人的程式 commit：不推，先問總控台或使用者

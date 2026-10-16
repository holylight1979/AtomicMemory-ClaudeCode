# 共用工作樹有MERGE_HEAD時不要git-commit-選擇性staging擋不住會把別人的合併以你的訊息收尾

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: MERGE_HEAD, 合併進行中, git commit, 共用工作樹, 併發 session, 意外合併提交, 雙 parent
- Created-at: 2026-10-15
- Related: 併發-session-共用工作樹-收尾選擇性-staging-勿-git-add-a, 共用工作樹讓同伴先fast-forward-自己的未提交改動存成patch還原後再3way套回-套回會留在暫存區要取消暫存
- Source: session:afddb6f8 2026-10-15
- Quote: 「這是我在專案層做token消耗檢查時CC提出的問題，請找出問題並根治 (最高優先)： ``` <pasted_content id="c0cb"> [根層] 覆轍提示跨專案洩漏，請修根因。 現象：在 TSLG 專案 session 啟動時，[Guardian:覆轍] 列出 15 個根層檔（verify_release_rules.py、wg_need_goal.py、overview_hub.p…」

## 知識

- [臨] 選擇性 staging 擋不住「別的 session 合併到一半」：共用工作樹有 `.git/MERGE_HEAD` 時，任何 `git commit` 都會把那個合併收尾，對方已暫存的整批改動以你的提交訊息落成雙 parent 的合併提交。實遇：只 `git add` 一支測試，提交後卻帶進對方 20 檔、還沒補驗的改動。
- [臨] 預防在兩端：提交方 commit 前先查 `.git/MERGE_HEAD`，在就等對方或先問；合併方不在共用的 live 樹做 `merge --no-commit`，改在自己的工作樹合併、live 只做快轉。

## 行動

- 共用工作樹上 git commit 前：`test -f .git/MERGE_HEAD` 有就停，查是哪個 session 在合併、等它提交
- 要合併分支進共用 main：在自己的 worktree 合、驗完，live 只做 fast-forward

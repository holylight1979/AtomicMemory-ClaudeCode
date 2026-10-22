# commit前閘要查這次真的會提交的內容-同一條指令裡的git-add還沒跑-檔名用-z取

- Scope: global
- Author: holylight
- Source: commit:3fa4d130 2026-10-20
- Confidence: [臨]
- Trigger: commit 前檢查, PreToolUse git commit, git add && git commit, 暫存區, diff --cached, core.quotePath, name-status -z, 隱私閘漏過, 病形閘, pre-commit 閘
- Created-at: 2026-10-20
- Related: commitorder閘只認最新一則使用者原話-中間夾系統通知或背景事件就要請使用者重下口令

## 知識

- [臨] PreToolUse 在整條 Bash 指令執行前就跑：`git add X && git commit` 檢查時 X 還沒進暫存區，只看 `git diff --cached` 會整個漏掉 X（實證：隱私閘原本就這樣漏過 `git add .env && git commit`）。要查「這次真的會提交什麼」得把同一條指令裡排在 commit 前的 git add 路徑算進去（tracked 用 `git diff HEAD -- <路徑>`、新檔用 `git ls-files -o --exclude-standard -- <路徑>`），再加 `commit -a`（工作樹已追蹤改動，工作樹刪除要蓋掉暫存區）、`commit <路徑>`（只提交那些路徑的工作樹內容）；`--pathspec-from-file`、`--git-dir`／`GIT_DIR` 預讀不到範圍，閘要擋而非退回看暫存區。
- [臨] git 預設 core.quotePath=true：`git diff --name-status`／`ls-files` 不帶 -z 時中文檔名輸出成帶引號的八進位跳脫，副檔名判斷與 blob 查詢都會錯；列舉檔名一律 `-z` 拿 NUL 分隔的真檔名。本機若全域設 false，測試要在 repo 層釘回 true 才測得到。
- [臨] 「新寫進的病 vs 舊碼原本就有」用新舊兩版比：病形範圍內有改到的行才算碰到，再拿所有提交檔舊版裡同一個（規則, 那一行去空白）一份抵一份——搬動抵得掉、原行保留又複製一份抵不掉；只看錨點行或用集合不計數都會漏（Codex 審查實證）。

## 行動

- 寫任何 commit 前閘：判斷「會提交哪些檔」用一處共用函式（本機在 tools/project-smells.py commit_entries，隱私閘與病形閘共用），不要各閘自己 diff --cached
- 測 commit 閘必備案例：`git add X && git commit` 前暫存區為空仍要查到 X

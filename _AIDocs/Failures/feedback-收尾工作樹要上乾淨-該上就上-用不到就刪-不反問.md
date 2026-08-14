# feedback-收尾工作樹要上乾淨-該上就上-用不到就刪-不反問

- Scope: global
- Author: holylight
- Confidence: [觀]
- Trigger: 上乾淨, 工作樹, 收尾, git status, 未提交, chore commit, 用不到就刪, 選擇性 staging, 殘留檔, 上版, 上GIT
- Created-at: 2026-08-12
- Related: 併發-session-共用工作樹-收尾選擇性-staging-勿-git-add-a, 自己flag的維護動作直接做完不要反問

## 知識

- [觀] 使用者原則（2026-08-12 指正）：收尾時工作樹要整體上乾淨——「該上的就要上、用不到的就刪」，不得拿「非本 session 產物/跟我無關」當理由留髒工作樹。選擇性 staging 的目的只是不踩「併發 session 進行中」的進度；確認無活躍 session（coord status 空）後，殘留的共用治理檔（.claude 記憶/索引/驗收單）就該一併收掉，不另開儀式性的「獨立 chore」還反問要不要。
- [觀] 收乾淨屬自己 flag 的維護動作→直接做完不反問（同 [[自己flag的維護動作直接做完不要反問]]）；本機自建捷徑類（*.lnk）進 .gitignore。

## 行動

- 每次收尾 commit 後跑 git status --porcelain；非空則判定：併發進度→留；共用治理檔→一併收；用不到→刪/ignore，當場執行不反問

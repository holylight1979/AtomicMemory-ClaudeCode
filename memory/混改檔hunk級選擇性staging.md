# 混改檔hunk級選擇性staging

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: hunk, 混改檔, 選擇性 staging, git apply, 併發 session, exact-stage
- Created-at: 2026-08-13
- Related: 併發-session-共用工作樹-收尾選擇性-staging-勿-git-add-a, commit-前必須核對-staged-清單而非只信自己-add-了什麼

## 知識

- [臨]（2026-08-12 Proj-JARVIS T7 實戰）同一檔被兩個 session 混改時，exact-stage 下探到 hunk 層：`git diff <file>` 存 patch → 以 `(?m)^(?=@@ )` 切 hunk、只留自己的重組 patch → `git apply --cached my.patch`（按 context 搜尋，容忍行號飄移）。對方未完成的 hunk 留在工作樹不動。
- **How to apply:** commit 前 `git diff --cached <file>` 逐檔驗證 staged 只含自己的 hunk；前提：staged tree（HEAD+自己改動）自身可編譯、不依賴對方未 commit 的新檔。[[併發-session-共用工作樹-收尾選擇性-staging-勿-git-add-a]]

## 行動

- （依知識內容判斷）

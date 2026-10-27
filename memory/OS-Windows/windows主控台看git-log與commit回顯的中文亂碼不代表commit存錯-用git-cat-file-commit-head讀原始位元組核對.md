# windows主控台看git-log與commit回顯的中文亂碼不代表commit存錯-用git-cat-file-commit-HEAD讀原始位元組核對

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: git log 亂碼, commit 訊息亂碼, 主控台亂碼, git cat-file, UTF-8, 中文 commit
- Created-at: 2026-10-27
- Related: svn-commit-中文訊息在-cp950-主控台會亂碼-必加-encoding-utf-8, git-已push-commit-勿改寫-雙-push-url-gitlab-main-force-保護致遠端分叉
- Source: session:17c8cd5c 2026-10-27

## 知識

- [臨]（本機實見）Windows 主控台裡 git log、git commit 回顯的中文訊息會變亂碼，但 commit 物件存的是正確 UTF-8；亂的是輸出到主控台時的編碼轉換，不是 commit 內容。
- [臨] 要核對訊息存得對不對，用 `git cat-file commit HEAD`（或指定 rev）讀原始物件，需要時導到檔案再以 UTF-8 讀；不要看到亂碼就 amend，已推的 commit 更不能改寫。

## 行動

- git 輸出中文亂碼時，先用 git cat-file commit <rev> 核對原始位元組，再決定要不要動 commit

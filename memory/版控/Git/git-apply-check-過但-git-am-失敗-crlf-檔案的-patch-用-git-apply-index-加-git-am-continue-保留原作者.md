# git apply --check 過但 git am 失敗-CRLF 檔案的 patch 用 git apply --index 加 git am --continue 保留原作者

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: git am, git apply, patch does not apply, format-patch, 同事 patch, 審核 patch, CRLF patch, git am --continue, 保留作者, 無 push 權
- Created-at: 2026-09-01

## 知識

- [臨] 收到別人 `git format-patch` 的 .patch 時：`git apply --check` 全過但 `git am` 對同一顆報 `patch does not apply`，差別在 `git am` 經 mailsplit 後對 **CRLF 檔**（本庫 tools/workflow-guardian-mcp/lib/*.js 是 CRLF）的行尾處理與 `git apply` 不同；LF 檔（.py）同一包 am 正常。
- [臨] 解法（保留對方作者/時間/commit message）：`git am` 停在該顆後，`git apply --index <該 .patch>` 把內容進 index，再 `git am --continue` —— am 會用 patch 裡的 From/Date/Subject 建 commit。不要改用自己 commit（作者會變成自己）。審核實測用 `git worktree add <scratch> HEAD` + `git apply` 在隱離樹跑測試，主工作樹不動；用完 `git worktree remove --force` + `prune`。

## 行動

- 審別人 patch：先 apply --check，再在暫時 worktree 套上跑測試，最後 git am 合併保留作者
- git am 對 CRLF 檔失敗 → git apply --index 該 patch + git am --continue，勿改自己 commit

# 既有非git目錄原地接上版控-reset-mixed加逐路徑備份-勿只信diff-filter-M-本機覆蓋檔用skip-worktree

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 原地接版控, git init 既有目錄, reset --mixed, skip-worktree, diff-filter, 安裝器, install.py, 接管既有目錄, untracked would be overwritten
- Created-at: 2026-10-05

## 知識

- [臨] 把 repo 套到「已有內容、不是 git」的目錄（實測 2026-10-05）：`git init` → `remote add` → `fetch` → `git reset --mixed origin/<分支>`（工作目錄零改動，只設 HEAD 與 index）→ 備份 → `git checkout -- .`。直接 `git checkout -t origin/<分支>` 會因 untracked 檔將被覆蓋而拒絕。
- [臨] 備份清單不能只取 `git diff --name-only --diff-filter=M`：使用者既有的東西與 repo 路徑同名但型別不同（檔 vs 目錄、symlink）不列在 M，`checkout -- .` 會無備份刪掉換成 repo 版。要對每個 tracked 路徑及其祖先做檔案系統檢查，型別衝突者先移進備份。
- [臨] 來源是 `--depth 1` 的本機 clone 時，從它 fetch 會印 rejected shallow roots 但 rc 仍為 0、ref 沒建；fetch 後必須驗 `refs/remotes/origin/<分支>` 存在。Windows 另需 `core.longpaths=true`，否則 checkout 中途 Filename too long 留下半套。
- [臨] 本機必須與 repo 版本不同的 tracked 檔（例如合併過使用者值的設定檔）留在「已修改」狀態，會讓「整樹乾淨才拉」的自動同步永遠不拉、本地 commit 推不出去而分叉。對該檔下 `git update-index --skip-worktree`：status 變乾淨；上游沒動它時 pull 成功且保留本機內容；上游動到它時 pull 安全中止，需先取消標記、還原、pull、重新合併、再下標記。

## 行動

- 接管既有目錄：reset --mixed 後逐 tracked 路徑檢查型別衝突並備份，再 checkout；寫階段狀態檔讓中斷可續跑
- fetch 後驗 ref 存在，不看 rc
- 本機要長期偏離 repo 的 tracked 檔用 skip-worktree，並提供升級流程處理上游改到該檔的情況

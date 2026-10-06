# 既有非git目錄原地接上版控-reset-mixed加逐路徑備份-勿只信diff-filter-M-本機覆蓋檔用skip-worktree

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 原地接版控, git init 既有目錄, reset --mixed, skip-worktree, diff-filter, 安裝器, install.py, 接管既有目錄, untracked would be overwritten
- Created-at: 2026-10-05
- Source: session:46e124e0#6449dbac 2026-10-05
- Quote: 「好。開工吧，請盡量多開agent高速完工，並且也要派Codex+你自己的agent 進行 從項目計畫開始的審查。」

## 知識

- [臨] 把 repo 套到「已有內容、不是 git」的目錄（實測 2026-10-05）：`git init` → `remote add` → `fetch` → `git reset --mixed origin/<分支>`（工作目錄零改動，只設 HEAD 與 index）→ 備份 → `git checkout -- .`。直接 `git checkout -t origin/<分支>` 會因 untracked 檔將被覆蓋而拒絕。
- [臨] 備份清單不能只取 `git diff --name-only --diff-filter=M`：使用者既有的東西與 repo 路徑同名但型別不同（檔 vs 目錄、symlink）不列在 M，`checkout -- .` 會無備份刪掉換成 repo 版。要對每個 tracked 路徑及其祖先做檔案系統檢查，型別衝突者先移進備份。
- [臨] 來源是 `--depth 1` 的本機 clone 時，從它 fetch 會印 rejected shallow roots 但 rc 仍為 0、ref 沒建；fetch 後必須驗 `refs/remotes/origin/<分支>` 存在。Windows 另需 `core.longpaths=true`，否則 checkout 中途 Filename too long 留下半套。
- [臨] 本機必須與 repo 版本不同的 tracked 檔（例如合併過使用者值的設定檔）留在「已修改」狀態，會讓「整樹乾淨才拉」的自動同步永遠不拉、本地 commit 推不出去而分叉。對該檔下 `git update-index --skip-worktree`：status 變乾淨；上游沒動它時 pull 成功且保留本機內容；上游動到它時 pull 安全中止，需先取消標記、還原、pull、重新合併、再下標記。
- [臨] 安裝器不要為「目標目錄不存在」另開「直接 clone 成目標」的路線：那樣的機器與開發機無法區分，會原樣拿到 repo 擁有者的設定檔，且安裝器自己改了 tracked 檔卻沒有 skip-worktree，之後升級必敗。單一路線＝一律 clone 到暫存再接管，目標不存在就先建空目錄。
- [臨] 使用者檔案的解析（JSON 是否合法）要放在任何改動之前；先 checkout 後解析會在壞檔時停在「已換成系統整檔」的半套狀態。升級流程同樣要寫階段狀態檔，否則被硬殺後重跑會把「已還原成系統版、標記已取消」誤認成未管理的機器。
- [臨] 判斷「設定檔裡哪些 hook 屬於本系統」不能用路徑子字串：別的專案的 `.claude/hooks/` 與使用者自己放在家目錄的腳本都會被誤刪。用「指向家目錄＋是版控追蹤檔（或檔案已不存在）」判定，並把丟掉的條目印出來。

## 行動

- 接管既有目錄：reset --mixed 後逐 tracked 路徑檢查型別衝突並備份，再 checkout；寫階段狀態檔讓中斷可續跑
- fetch 後驗 ref 存在，不看 rc
- 本機要長期偏離 repo 的 tracked 檔用 skip-worktree，並提供升級流程處理上游改到該檔的情況

# 併發 session 共用工作樹-收尾選擇性 staging 勿 git add -A

- Scope: global
- Author: holylight
- Confidence: [固]
- Trigger: 上GIT, git add, staging, 收尾, git status, 併發 session, concurrent session, commit, disjoint 批次, 多 session
- Created-at: 2026-07-01
- Related: workflow-rules, feedback-completion-gates, 原子記憶審查總結-好機制被小故障卡死非過重-拔前先實證, 跨session協調-衝突預警機制與cc原生現況, commit-前必須核對-staged-清單而非只信自己-add-了什麼, sed-i-在-crlf-repo-會整檔改換行, feedback-收尾工作樹要上乾淨-該上就上-用不到就刪-不反問, 混改檔hunk級選擇性staging, 併發session共用的不只工作樹-執行中的應用程式行程也是共用資源, feedback-能自動化實跑的驗證不准推給使用者-離線模擬不算驗證

## 知識

- [固] 使用者會同時跑多個 Claude session 共用**同一 git 工作樹**。故某 session 收尾時 `git status` 常含「其他 session 尚未提交的改動」；且本 session 起始環境的 gitStatus 快照可能**失真**（顯示 clean 但實際已有既存未提交改動，`git pull` 不會動到本地未提交檔）。
- [固] 鐵律：收尾提交務必**選擇性 staging**——`git add <本批明確檔案…>` 後 commit；**絕不** `git add -A` / `git commit -a`。否則會把他 session 的 in-progress 改動連同**錯誤的 commit message** 掃進本批，破壞 disjoint 批次邊界、污染他人語意。
- [固] 診斷意外出現的 modified 檔：diff 內容判別是 (a) runtime hook 自動寫入（如 world.html 演化）還是 (b) 他 session 的手寫批次。若主題連貫、`run_verify` 通過＝完整的他 session 批次 → **留給其 owner session 自行 commit，不代刀**（他常會用自己的正確 message 落地，如實測 P8b 隔壁 P5 session 自行提交 6 檔）。
- **Why:** 盲 `git add -A` 在併發共用工作樹下會跨批次污染——把不屬於本批、甚至你被明確交代不可編輯的檔（如 stop.py）併進 commit，事後難拆。
- **How to apply:** 收尾三步——① `git status --porcelain` 核對；② 只 `git add` 本批宣告的檔；③ commit 後再 `git status` 確認殘留檔恰為「非本批、他 session 的」，於收尾報告通報，不擅動。
- [固] 反向診斷（上面從「我掃走他人檔」角度寫，這裡是反方向）：他 session 的 `git add -A` 也會把**我未 commit 的編輯**掃進他的 commit → 我那筆改動 `git status`、`git diff HEAD` 皆空（working==HEAD）。若「我明明改了卻不顯示」，先 `git show HEAD:<檔>` 查是否已被平行 commit 吃掉，**別當編輯遺失或自己幻覺**。實例：2026-07-01 P5 批我改的 `workflow/config.json` `_doc` 被隰壁 `f12e0c8`（lang-guard P8b）掃走；同時 `run_verify` 695→710 也是平行 session 加的測試。
- [固] **`git reset --hard` 是同一家族的地雷，且更隱微**：`git add -A` 是「把他人的改動掃進來」，`reset --hard` 是「把他人的改動沖掉」——它不只回退 commit，還會**連同工作區所有 unstaged 修改一併丟揉**（包括本 session 從未碰過、使用者或他 session 留的）。實例 2026-07-28：為收欛一個 amend 後的分岔，跑 `git reset --hard origin/master`，**連帶沖掉 session 開始就存在的 `.vscode/settings.json` 未提交修改**（兩行 dotnet 設定）。錯誤心法：動手前只驗證了「兩個 commit 的 tree 相同、不會掉我的檔」，**沒盤點工作區其他人的未提交變更**。
- [固] **未 staged 的修改被 `reset --hard` 沖掉，git 側無解（沒 blob、沒 reflog）——但 VS Code Local History 能救**：`%APPDATA%/Code/User/History/<hash>/entries.json` 存 `resource` → 檔案 URI 對應，同目錄各版本快照依 timestamp 排序。救援流程：`grep -rl "<相對路徑>" $APPDATA/Code/User/History/` → 讀 entries.json 找最新 id → `cp` 回原位 → `git status` 確認回到原本的 ` M` 狀態。
- [固] **遠端 master 可能是 protected branch（GitLab）——推出去的 commit message 就嚺死了**：`git push --force-with-lease` 會被 pre-receive hook 擋（「not allowed to force push to a protected branch」），而本地已 amend → 分岔 → 此時**別反射性用 `reset --hard` 收欛**（見上條）。預防在上游：commit message 一次寫對。此次根因：在 **Bash tool 裡誤用 PowerShell here-string** `git commit -m @'\n...\n'@` → Git Bash 不認，`@` 被當成訊息內容首尾各多一行。正解：Bash tool 用 heredoc `git commit -F - <<'EOF' ... EOF`；PowerShell tool 才用 `@'...'@`。

## 行動

- （依知識內容判斷）

# 併發 session 共用工作樹-收尾選擇性 staging 勿 git add -A

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 上GIT, git add, staging, 收尾, git status, 併發 session, concurrent session, commit, disjoint 批次, 多 session
- Created-at: 2026-07-01
- Related: workflow-rules, feedback-completion-gates

## 知識

- [臨] 使用者會同時跑多個 Claude session 共用**同一 git 工作樹**。故某 session 收尾時 `git status` 常含「其他 session 尚未提交的改動」；且本 session 起始環境的 gitStatus 快照可能**失真**（顯示 clean 但實際已有既存未提交改動，`git pull` 不會動到本地未提交檔）。
- [臨] 鐵律：收尾提交務必**選擇性 staging**——`git add <本批明確檔案…>` 後 commit；**絕不** `git add -A` / `git commit -a`。否則會把他 session 的 in-progress 改動連同**錯誤的 commit message** 掃進本批，破壞 disjoint 批次邊界、污染他人語意。
- [臨] 診斷意外出現的 modified 檔：diff 內容判別是 (a) runtime hook 自動寫入（如 world.html 演化）還是 (b) 他 session 的手寫批次。若主題連貫、`run_verify` 通過＝完整的他 session 批次 → **留給其 owner session 自行 commit，不代刀**（他常會用自己的正確 message 落地，如實測 P8b 隔壁 P5 session 自行提交 6 檔）。
- **Why:** 盲 `git add -A` 在併發共用工作樹下會跨批次污染——把不屬於本批、甚至你被明確交代不可編輯的檔（如 stop.py）併進 commit，事後難拆。
- **How to apply:** 收尾三步——① `git status --porcelain` 核對；② 只 `git add` 本批宣告的檔；③ commit 後再 `git status` 確認殘留檔恰為「非本批、他 session 的」，於收尾報告通報，不擅動。

## 行動

- （依知識內容判斷）

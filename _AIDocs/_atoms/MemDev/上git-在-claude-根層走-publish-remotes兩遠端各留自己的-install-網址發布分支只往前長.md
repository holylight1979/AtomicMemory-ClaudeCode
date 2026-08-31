# 上GIT 在 claude 根層走 publish-remotes——兩遠端各留自己的 Install 網址、發布分支只往前長

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 上GIT, publish-remotes, publish/github, publish/gitlab, 雙遠端, gitlab remote, origin 只推 github, Install.md 網址, repo-url, 發布分支, git push origin main, non-fast-forward
- Created-at: 2026-08-31
- Related: git-已push-commit-勿改寫-雙-push-url-gitlab-main-force-保護致遠端分叉, feedback-收尾工作樹要上乾淨-該上就上-用不到就刪-不反問

## 知識

- [臨] ~/.claude 這個 repo 的「上GIT」不再 `git push origin main`：`origin` 只指 GitHub、另有 `gitlab` remote。main commit 後跑 `python tools/publish-remotes.py`——對每個遠端在 TEMP 開暫時 worktree checkout `publish/<name>`，merge main → 把 Install.md 的 `<!-- repo-url -->…<!-- /repo-url -->` 區塊改成只剩該遠端網址 → commit → `push <remote> publish/<name>:main`。發布分支只往前長、永不 force（GitLab main 有 pre-receive force 保護）。
- [臨] 為什麼：使用者要「兩端各留各自的網址、不集中」；同一顆 commit 推兩邊內容必相同，所以每個遠端各一條發布分支。主工作樹全程不動；SessionEnd 晉升自動 push 也改呼叫此腳本——裸 `git push` 從 main 到 origin/main 會 non-ff 被拒。
- [臨] 腳本以自身 TARGETS 表為準重寫區塊，冪等且自癒：就算 `git pull` 把某遠端的網址 commit 併回 main，下次 publish 兩邊仍各自正確。merge 衝突只允許在 Install.md（取 main 版再重套替換），其他檔衝突直接 abort 報錯。

## 行動

- ~/.claude 收尾上 GIT：commit main → `python tools/publish-remotes.py`（可 `--only github|gitlab`、`--dry-run`）；不要手打 `git push origin main`
- push 被拒 non-fast-forward → 先確認是不是從 main 直推遠端 main（該走腳本），再查有無改寫已 push 歷史
- 改 Install.md 版控庫段時保留 `<!-- repo-url -->` 標記，否則腳本拒絕替換

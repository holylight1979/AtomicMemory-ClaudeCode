# git 已push commit 勿改寫 — 雙 push-url + GitLab main force 保護致遠端分叉

- Scope: global
- Author: holylight
- Confidence: [觀]
- Trigger: git commit, git push, amend, git amend, force push, force-with-lease, rebase, dual push url, 雙push, gitlab, github, pre-receive hook declined, non-fast-forward, 遠端分叉, 分叉, commit message, heredoc, 多行 commit message, 上GIT, main 保護, force 保護, publish-remotes, Fork graph, 單一條線
- Created-at: 2026-07-06
- Related: workflow-rules, feedback-tooling-reliability, workflow-svn, feedback-收尾工作樹要上乾淨-該上就上-用不到就刪-不反問

## 知識

- [觀] 本 repo（~/.claude AtomicMemory）origin＝**雙 push URL**（GitHub + 公司 GitLab 同時推同一份歷史；另有 `gitlab` remote 只為 fetch）；GitLab main 有 pre-receive force-push 保護（**只准 fast-forward**，force / non-ff → `remote rejected … pre-receive hook declined`），GitHub 無保護。後果：`git commit --amend` / rebase / 任何改寫**已 push** 的 commit 後再 push → **GitHub 接受、GitLab 擋 → 兩遠端分叉**。GitLab 那顆 SHA 動不了，只能把 local + GitHub 一起 `reset --hard` + force 退回對齊 GitLab 的舊 SHA（連同醜 commit message 永久定住、回不去）。
- [觀] 鐵律：**已 push 的 commit 一律不改寫**（不 amend、不 rebase -i、不 force-push main）。要修 message / 內容 → 往前開**新 commit**。只有『尚未 push』的本地 commit 才可自由 amend。
- [觀] 多行 commit message 用 `git commit -F <file>`（訊息寫檔再帶入）；**別**把 `$(cat <<'EOF'…)` heredoc 塞進**單引號** `-m` —— 單引號不做命令替換，整段 `$(cat <<EOF` 會**字面**進 message（bash 工具環境實際踩過）。
- [觀] **區別「雙 push URL」與「兩個獨立 remote」－―前者才會分叉**。上面講的分叉前提是「同一個 remote 掛兩個 push URL、兩邊推**同一份歷史**」，所以一方有 force 保護就會卡住。若是**兩個獨立 remote、推兩份不同的歷史**（例：AI-gen-projs 的 `origin`→GitLab 全 repo，另一個 `github-mud`→用 `git subtree push --prefix=<子資料夾>` 推子資料夾抽出來的歷史），ref 不共用，**沒有分叉問題**。但「已 push 的 commit 不改寫」兩種都適用——改寫了會讓 subtree 重新映射出不同 SHA。
- [觀] 共用 repo 的**子資料夾**要單獨外推成一個 repo：用 `git subtree`，**不可以在子資料夾裡 `git init`**（檔案已被父 repo 追蹤，嵌套 .git 會讓父 repo 把它當成 submodule）。`git subtree push` 每次重掃全部 commit（輸出一長串 `n/N` 進度數字、跑一兩分鐘）是正常的；不要手動 `git subtree split -b <分支>`，分支已存在會失敗。
- [觀] 手邊沒裝 `gh` 也能程式化建 GitHub private repo：`git credential fill` 餵 `protocol=https` / `host=github.com` 取出 Windows 認證管理員裡的 token（`gho_` 開頭，實測帶 `repo` scope），再 POST `api.github.com/user/repos` 帶 `private:true`。
- [觀] 不要再走「每個遠端各一條發布分支」（曾用 `tools/publish-remotes.py` 讓 Install.md 兩端各留網址）：兩端內容不同 → 必為不同 commit → 不 force 就只能 merge 鏈，每發布固定兩顆 merge，Fork graph 交錯；`git pull origin` 還會把本地 main 快轉成發布分支。使用者拍板：Install.md 不列網址、腳本與 publish/* 撤除、origin 雙 push URL 同一條線；SessionEnd 晉升自動 push 也是 `git push origin main`。

## 行動

- ~/.claude 收尾上 GIT：commit main → `git push`；兩行 push 輸出都 fast-forward 才算完成
- 上 GIT：多行 commit message 一律 `git commit -F <file>`，不用 heredoc-in-quoted `-m`
- 已 push 的 commit 要修 → 開新 commit 往前修，**絕不** amend / rebase / force（此 repo GitLab main force-protected + 雙 push URL → 分叉且回不去）
- push 遇 `pre-receive hook declined` → 多半是 force / non-ff 被擋，先確認自己沒在改寫已 push 的歷史
- 不要再建 publish/* 分支或平台專屬內容檔；Install.md 版控庫段保持不列網址

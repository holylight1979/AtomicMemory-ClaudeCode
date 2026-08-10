# git 已push commit 勿改寫 — 雙 push-url + GitLab main force 保護致遠端分叉

- Scope: global
- Author: holylight
- Confidence: [觀]
- Trigger: git commit, git push, amend, git amend, force push, force-with-lease, rebase, dual push url, 雙push, gitlab, github, pre-receive hook declined, non-fast-forward, 遠端分叉, 分叉, commit message, heredoc, 多行 commit message, 上GIT, main 保護, force 保護
- Created-at: 2026-07-06
- Related: workflow-rules, feedback-tooling-reliability, workflow-svn

## 知識

- [觀] 本 repo（~/.claude AtomicMemory）origin＝**雙 push URL**（GitLab + GitHub 同時推）；GitLab main 有 pre-receive force-push 保護（**只准 fast-forward**，force / non-ff → `remote rejected … pre-receive hook declined`），GitHub 無保護。後果：`git commit --amend` / rebase / 任何改寫**已 push** 的 commit 後再 push → **GitHub 接受、GitLab 擋 → 兩遠端分叉**。GitLab 那顆 SHA 動不了，只能把 local + GitHub 一起 `reset --hard` + force 退回對齊 GitLab 的舊 SHA（連同醜 commit message 永久定住、回不去）。
- [觀] 鐵律：**已 push 的 commit 一律不改寫**（不 amend、不 rebase -i、不 force-push main）。要修 message / 內容 → 往前開**新 commit**。只有『尚未 push』的本地 commit 才可自由 amend。
- [觀] 多行 commit message 用 `git commit -F <file>`（訊息寫檔再帶入）；**別**把 `$(cat <<'EOF'…)` heredoc 塞進**單引號** `-m` —— 單引號不做命令替換，整段 `$(cat <<EOF` 會**字面**進 message（bash 工具環境實際踩過）。

## 行動

- 上 GIT：多行 commit message 一律 `git commit -F <file>`，不用 heredoc-in-quoted `-m`
- 已 push 的 commit 要修 → 開新 commit 往前修，**絕不** amend / rebase / force（此 repo GitLab main force-protected + 雙 push URL → 分叉且回不去）
- push 遇 `pre-receive hook declined` → 多半是 force / non-ff 被擋，先確認自己沒在改寫已 push 的歷史

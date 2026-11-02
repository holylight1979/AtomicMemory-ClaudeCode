# Agent工具的worktree隔離在工作目錄磁碟代號是小寫c時被拒-報core-worktree-redirect-等工作目錄回到大寫C再派並清掉殘留的鎖住工作樹

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: isolation worktree, worktree 隔離, core.worktree redirect, Refusing to use, 磁碟代號大小寫, 子代理工作樹, agent worktree, locked worktree
- Created-at: 2026-11-02
- Source: session:3f490ffe 2026-11-02

## 知識

- [臨]（Windows、VSCode 擴充實測）同一則回覆一次派 4 個 isolation=worktree 的子代理，全部回錯「Refusing to use c:\…\.claude\worktrees\agent-… as an isolation worktree: git resolves its working tree to C:/…（a core.worktree redirect…）」；當時環境的主要工作目錄是小寫 `c:\Users\…`，git 回報的是大寫 `C:/`，路徑比對不分大小寫就判成跳出工作樹。工作目錄變回大寫 `C:\…` 後重派同樣的子代理全部成功。
- [臨] 失敗的那次工作樹與分支已經建好、而且是 locked：要逐個 `git worktree unlock <路徑> && git worktree remove <路徑>` 再 `git branch -D worktree-agent-…`，否則留下一堆空工作樹。

## 行動

- 派 isolation=worktree 前看環境的主要工作目錄：磁碟代號是小寫就先讓工作目錄回到大寫 C: 再派
- 被拒後先清殘留的 locked 工作樹與分支再重派

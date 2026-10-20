# 已在worktree裡的session不能直接EnterWorktree到外部路徑-先ExitWorktree-keep回啟動目錄再進

- Scope: global
- Author: holylight
- Source: session 5e209e95 2026-10-20（track-data-file-ask 換到 data-file-ask-2）
- Confidence: [臨]
- Trigger: EnterWorktree, ExitWorktree, 換工作樹, 新 worktree, worktree 被刪, not a managed worktree
- Created-at: 2026-10-20
- Related: 工作session切進worktree後被隔離寫不到worktree外-交付改用sendmessage回全文-cwd不在worktree時收據根對不上

## 知識

- [臨] 工作 session 已經在某棵 worktree 裡時，再呼叫 EnterWorktree(path=<.claude-wt 底下另一棵>) 會被拒：「<啟動目錄>\.claude\worktrees does not exist, so <路徑> cannot be a worktree managed by Claude Code」。已在 worktree 內只能切到 .claude/worktrees/ 底下的樹，外部路徑只在從啟動目錄第一次進入時收。總控台合併後刪了舊樹、給新樹時就會遇到。
- [臨] 解法：ExitWorktree(action=keep) 回啟動目錄（不刪任何東西；舊樹已被刪也照樣成功），再 EnterWorktree(path=<新樹>)。

## 行動

- 換到總控台給的新樹：先 ExitWorktree keep，再 EnterWorktree path

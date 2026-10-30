# worktree隔離session的claude-job-dir在live資料根底下-規定寫入只用worktree時暫存放worktree內不stage或repo外-不用job-tmp

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: CLAUDE_JOB_DIR, jobs tmp, job 暫存, worktree 暫存放哪, 不碰 live, 寫入只用 worktree, worktree 隔離 session
- Created-at: 2026-10-27
- Related: 退回檢查的暫存副本要用git-archive整棵解-tar要force-local-回放樹放repo外-並行工作樹時不用stash
- Source: session:17c8cd5c#840617df 2026-10-27

## 知識

- [臨] Claude Code 給 session 的 CLAUDE_JOB_DIR（~/.claude/jobs/<id>/tmp）在 ~/.claude 底下，也就是記憶系統的 live 資料根。worktree 隔離 session 規定「寫入只用 worktree、不碰 live」時，寫進 job tmp 等於寫進 live。
- [臨] 暫存改放 worktree 內（不 stage）或 repo 外的目錄。放在 ~/.claude 底下另有一害：在那裡跑 pytest 會沿祖先目錄吃到 live 的 conftest.py。

## 行動

- worktree 隔離 session 寫暫存前先看路徑是不是在 ~/.claude 底下；是就改放 worktree 內或 repo 外

# 純函式的舊碼對照用git-show取舊版exec成模組-不動工作樹

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: git show 舊版, 載成模組, 舊碼對照, 不動工作樹
- Created-at: 2026-10-20
- Source: session:a49d53e9 2026-10-20
- Quote: 「track-gate-bypass：你是工作軌 track-gate-bypass，總控台是 claude-e3（送信前先 ListAgents 確認，名字會變）。第一步用 EnterWorktree 切進 C:\Users\holylight\.claude-wt\gate-bypass（分支 gate-bypass，已存在，不要新建；不存在就 SendMessage 總控台要，不要自己建）。…」

## 知識

- [臨] 只要證明「舊版純函式給同一輸入結果不同」時，用 `git show <commit>:<檔>` 取原始碼、exec 成一個獨立模組跟現行模組並排跑，印哨兵；工作樹完全不動，寫碼查核不會記改碼。要經 hook 入口的行為才需要實際退回檔。

## 行動

- 做舊碼對照前先判斷受測的是純函式還是 hook 入口；純函式用 git show 載模組比

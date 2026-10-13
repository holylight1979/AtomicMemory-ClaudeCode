# 退回檢查的暫存副本要用git-archive整棵解-tar要force-local-副本含部位表會被overviewhub當專案-送codex的diff不能有暫存外絕對路徑

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 退回檢查, 退回紅, 暫存副本, git archive, tar --force-local, Cannot connect to C, replay-guard, 提示詞指到暫存目錄以外的路徑, 舊版檔跑新測試
- Created-at: 2026-10-13
- Related: worktree隔離session改部位檔被overviewhub閘連擋-證據只認read事件與bash註解三行-git-c-live與python-heredoc與變數路徑一律被拒
- Source: session:6ea645d0 2026-10-13
- Quote: 「你是 v6.0 的工作 session track-g12w，總控台是 claude-9f（調度；對人總控台是 claude-91）。第一步用 EnterWorktree 切進 worktree C:\Users\holylight\.claude-wt\track-g12w（分支 v6/track-g12w，已存在，不要新建）。派工 prompt 在 C:\Users\holylight\.c…」

## 知識

- [臨] 始末：工作 session 要證「新案在舊版程式紅在斷言」，只把 hooks/、lib/ 複製到 scratchpad 再換回舊檔，pytest 收集一路缺 tools/ 的模組、.claude/overview-map.md、workflow/config.json，連撒三次。根因：hooks 的 verify 會讀 repo 根的部位表與 config、import tools/ 的模組，零碎複製必漏。正解：`git archive --format=tar -o <scratch>/head.tar HEAD`，進目標目錄 `tar --force-local -xf ../head.tar` 解整棵，再只覆蓋新測試與新模組、保留要退回的舊檔。
- [臨] GNU tar（Git Bash）把 `C:/…` 的冒號當遠端主機：報 `Cannot connect to C: resolve failed`，加 `--force-local` 或用相對路徑。
- [臨] 解出來的副本含 .claude/overview-map.md，OverviewHub 的 find_map 會把 scratchpad 副本當成專案：對副本 cp 也要先 Read 副本裡該部位一個檔、指令開頭放各部位定位三行（每個要寫入的部位各一組）。
- [臨] 第二意見工具 prepare 的 replay-guard pre 擋「提示詞指到暫存目錄以外的路徑」：diff 裡測試夾具的假路徑 `C:/p/gone.py` 就讓 job blocked。假路徑一律寫相對（pkg/gone.py）。材料取 `git diff HEAD`，沒 git add 的新檔看不到；先 commit 到分支，它會退取 main...HEAD。從 worktree 跑 `WG_CLAUDE_DIR=<worktree> python tools/second-opinion/run.py prepare|execute`，job 目錄落 worktree 的 workflow/second-opinion/（gitignored），不碰 live。

## 行動

- 退回檢查：git archive HEAD 整棵解到 scratchpad（tar --force-local），只覆蓋新測試與新模組，junitxml 看每案是 failure 不是 error
- 送 codex 前：commit 到分支、grep diff 有沒有磁碟代號絕對路徑

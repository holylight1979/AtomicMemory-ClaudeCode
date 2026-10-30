# worktree隔離session改部位檔被OverviewHub閘連擋-證據只認Read事件與Bash註解三行-git-C-live與python-heredoc與變數路徑一律被拒

- Scope: global
- Author: holylight
- Source: session:836cdfff 2026-10-13 track-b3
- Confidence: [臨]
- Trigger: worktree 隔離, python - heredoc 被擋, 變數路徑 被擋, git -C live 被擋, 反轉驗證 worktree, live 未動證明, 隔離 session 硬擋
- Created-at: 2026-10-13
- Related: 工作session切進worktree後被隔離寫不到worktree外-交付改用sendmessage回全文-cwd不在worktree時收據根對不上, 退回檢查的暫存副本要用git-archive整棵解-tar要force-local-副本含部位表會被overviewhub當專案-送codex的diff不能有暫存外絕對路徑
- Quote: 「施工agent若能多開就多開，提速吧」

## 知識

- [臨] 隔離 session 的硬擋（實證）：`git -C <live>` 任何子命令（含只讀 status）一律拒；`python -` heredoc、路徑含 `$W` 變數的指令被寫入目標解析器拒（改 Edit 工具或字面絕對路徑）；同一條指令把 `python -m pytest` 與 git 串在一起也拒（拆兩條）。live 未動證明改用 `cmp <live 檔> <git show <基準>:檔 的副本>`＋grep 新符號＋stat mtime。
- [臨] 反轉驗證在隔離 session：`git show <舊版>:檔 > scratchpad/old.py`、cp 現版到 scratchpad，用 cp 換檔跑 pytest 再 cp 回來（不走 git checkout，暫存區不會被動）；紅的型別要分類：新案要紅在 AssertionError，純函式新 API 案紅在 AttributeError 可接受但要在交付信標明。
- [臨] `git hash-object <live 路徑>` 也被 CrossRealmBashBlock 擋；`python -c "…"` 被寫入目標解析器拒，驗 JSON 用 `python -m json.tool <檔>`。live 未動證明：scratchpad Python 用 hashlib 算 git blob（sha1 of `blob <長度>\0`＋位元組）對 `git -C <worktree> rev-parse main:<路徑>`，逐檔 SAME／DIFF；DIFF 用 difflib 看差在哪、對開工快照判是不是自己改的。
- [臨] 隔離 session 的驗證帳本落在 live `workflow/verify-ledger/<sid>.jsonl`，AEC (j) 填 live 路徑。根層 worktree 的量尺（PYTEST_MEASURE）屬一般證據，接 `| tail`／`2>&1` 就不算；改完最後一個檔後在 worktree 根再跑一次不接管線的目標 verify 才收尾。
- [臨] live 未動證明查 main 有沒有某檔用 `git rev-parse --verify -q main:<路徑>`；不加時查不到會把參數印回 stdout，被當成有。

## 行動

- 隔離 session 一律字面絕對路徑、不用 python - heredoc、不碰 git -C live；live 未動證明用 cmp 與 mtime

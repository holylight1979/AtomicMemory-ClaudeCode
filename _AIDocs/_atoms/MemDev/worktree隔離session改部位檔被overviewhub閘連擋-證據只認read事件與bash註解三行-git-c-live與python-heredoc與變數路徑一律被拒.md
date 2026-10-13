# worktree隔離session改部位檔被OverviewHub閘連擋-證據只認Read事件與Bash註解三行-git-C-live與python-heredoc與變數路徑一律被拒

- Scope: global
- Author: holylight
- Source: session:836cdfff 2026-10-13 track-b3
- Confidence: [臨]
- Trigger: 定位三行被擋, Edit 被擋 證據不足, 還沒讀過這個部位的檔, fix-escalation, worktree 隔離, python - heredoc 被擋, 變數路徑 被擋, git -C live 被擋, 反轉驗證 worktree, live 未動證明
- Created-at: 2026-10-13
- Related: 工作session切進worktree後被隔離寫不到worktree外-交付改用sendmessage回全文-cwd不在worktree時收據根對不上
- Quote: 「你是 v6.0 的工作 session track-b3，總控台是 claude-2c。第一步用 EnterWorktree 切進 worktree C:\Users\holylight\.claude-wt\track-b3（分支 v6/track-b3，已存在，不要新建）。派工 prompt 在 C:\Users\holylight\.claude\workflow\v6-inbox\to-…」

## 知識

- [臨] 始末（2026-10-13 track-b3，Edit 被 OverviewHub 閘連擋 9 次觸發 fix-escalation）：切進 worktree 後改 lib／tools 部位的檔，閘回「還沒讀過這個部位的檔」與「還沒交出定位三行」。錯誤行為＝照 bypass 模式提示用 Bash 的 sed／grep 讀部位檔（不算 Read 事件，part_files_read 記不到）、三行只寫在回覆文字（worktree session 的 transcript 偶爾掉「先文字再工具」那段）。正確做法＝注入導讀卡後至少用 Read 工具讀該部位 1 個檔，三行同時放進下一個 Bash 開頭的 `#` 註解，一次把本回合會碰的所有部位各寫一組，之後 Edit 一路放行。
- [臨] 根因：閘的證據來源是 PostToolUse 的 Read 事件與 transcript 的 assistant 文字／工具參數，不是「我看過了」；bypass 提示「盡量用 Bash 讀檔」與閘的證據規則相衝，照提示做就必被擋。設計原理：閘要可稽核的讀檔紀錄與 hook 解析得到的三行，Bash 只做寫入目標判定。運作邏輯：wg_overview.on_read 只把 Read／Bash 解析出的讀路徑記進 part_files_read；on_edit 用 transcript_offset 之後的 assistant 文字找三行，工具參數也在三管道內，所以 Bash 註解最穩。
- [臨] 隔離 session 的硬擋（同場實證）：`git -C <live>` 任何子命令（含只讀 status）一律拒；`python -` heredoc、路徑含 `$W` 變數的指令被寫入目標解析器拒（改 Edit 工具或字面絕對路徑）；同一條指令把 `python -m pytest` 與 git 串在一起也拒（拆兩條）。live 未動證明改用 `cmp <live 檔> <git show <基準>:檔 的副本>`＋grep 新符號＋stat mtime。
- [臨] 反轉驗證在隔離 session：`git show <舊版>:檔 > scratchpad/old.py`、cp 現版到 scratchpad，用 cp 換檔跑 pytest 再 cp 回來（不走 git checkout，暫存區不會被動）；紅的型別要分類：新案要紅在 AssertionError，純函式新 API 案紅在 AttributeError 可接受但要在交付信標明。

## 行動

- 改部位檔前：Read 一個該部位的檔 ＋ Bash 開頭註解交三行（每個會碰的部位各一組）
- 隔離 session 一律字面絕對路徑、不用 python - heredoc、不碰 git -C live；live 未動證明用 cmp 與 mtime

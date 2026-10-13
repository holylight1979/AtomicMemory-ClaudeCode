# shell命令判定的語意陷阱-續行先接回再判-引號外token起頭的井號是註解-只有單引號是字面-外層語意先查整段原文

- Scope: global
- Author: holylight
- Source: v6/track-a4 003～008 codex 審查退件（36fcc0b、3dd5a8b、2e98849，合進 main fbbcc9e）hooks/handlers/pre_tool_use.py _scan_segments／_wrapped_commit_verdict
- Confidence: [臨]
- Trigger: 續行, line continuation, 反斜線換行, cmd ^, PowerShell 反引號, shell 註解, 撇號, 雙引號展開, 命令替換, $(), heredoc, 斷詞器, 口令閘
- Created-at: 2026-10-13
- Related: 從指令字串辨識shell包裝要斷詞看執行檔basename再找執行旗標-regex會被帶引號完整路徑與啟動選項繞過-內層要認真子命令, 從指令文字判斷某支程式真的跑過-要用尊重引號的同一套解析且只看最後執行的鏈-逐條補shell技巧不收斂就改白名單語法解析不了不算證據
- Quote: 「你是 v6.0 的工作 session track-a4，總控台是 claude-2c。第一步用 EnterWorktree 切進 worktree C:\Users\holylight\.claude-wt\track-a4（分支 v6/track-a4，已存在，不要新建）。派工 prompt 在 C:\Users\holylight\.claude\workflow\v6-inbox\to-…」

## 知識

- [臨] 續行要在切段前接回，而且判定用的文字也要是接回後的：Bash 的 `\`＋換行（引號外與雙引號裡）、cmd 的 `^`＋換行、PowerShell 的反引號＋換行（引號外）都不是兩條命令。只把續行從 token 的值拿掉、判定卻拿原字串切片重組，`git\⏎  commit` 照樣認不出。Bash 接回不補空白：`git\⏎commit`（下一行不縮排）是 `gitcommit` 一個字。
- [臨] 引號外、位在 token 起頭的 `#` 到行尾是註解（Bash 與 PowerShell），要略過內容但保留換行切段；不認註解的話，`# Run the user's command` 的撇號會被當開引號，跨行吞掉下一行命令，後面的撇號再把引號閉合，連「引號沒閉合就擋」的保守規則都救不到。引號裡與 token 中間的 `#` 是字面（`"fix #12"`、`a#b`），不能刪掉所有 `#` 後的字。
- [臨] 只有單引號裡是字面：雙引號裡的 `$(…)`、反引號會展開執行，白名單判斷不能用「把所有引號內容清空」來證明沒副作用。多一層包裝時，外層 shell 的雙引號裡單引號只是普通字元：`bash -c "git log --grep='$(…)'"` 的 `$(` 在外層就執行了，要先用外層語意查整段原文（含內層自己的外層引號），再剝一層引號往內遞迴。
- [臨] 要逐段判：找到一個查詢包裝，不代表同一條命令的其他片段安全（`bash -c "git log"; (git commit -m x)`）。每段都要跑子 shell 括號／eval／命令替換的檢查。
- [臨] heredoc 只剝內文：起始行 delimiter 後面的 `&& git commit -F msg` 是真命令要留；逐行找第一個結束行（零行內文也算），跨行 regex 會漏認空 heredoc 的結束行、一路剝到下一個同名 heredoc，把中間的命令吞掉。
- [臨] 展開訊號加目標字樣就擋（fail-closed）會誤擋少數查詢（`cd "$(git rev-parse --show-toplevel)" && git log --grep=commit`），接受為已知邊界時要把「查詢請拿掉字樣或改用單引號」寫進擋訊息，讓被擋的人有路可走。

## 行動

- 斷詞器每個 token 存「去掉續行、保留引號」的原文，判定與展開檢查都用它
- 引號外 token 起頭的 # 當註解略過到行尾，換行照切段
- 包裝段先以外層語意查整段原文再遞迴內層；每段都跑展開檢查
- 接受為已知邊界的誤擋，擋訊息要寫怎麼改寫才不擋

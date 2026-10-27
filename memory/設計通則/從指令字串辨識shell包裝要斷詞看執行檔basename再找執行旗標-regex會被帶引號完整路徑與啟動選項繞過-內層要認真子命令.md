# 從指令字串辨識shell包裝要斷詞看執行檔basename再找執行旗標-regex會被帶引號完整路徑與啟動選項繞過-內層要認真子命令

- Scope: global
- Author: holylight
- Source: commit fbbcc9e（0f10b03、36fcc0b、3dd5a8b、2e98849）hooks/handlers/pre_tool_use.py CommitOrder 口令閘
- Confidence: [臨]
- Trigger: bash -c, bash -lc, powershell -Command, cmd /c, shell 包裝, 包裝偵測, 執行旗標, basename, 口令閘, 指令字串解析, Program Files, & 呼叫運算子, 有沒有呼叫 git, .git 路徑, 快篩
- Created-at: 2026-10-13
- Related: 從指令文字判斷某支程式真的跑過-要用尊重引號的同一套解析且只看最後執行的鏈-逐條補shell技巧不收斂就改白名單語法解析不了不算證據, shell命令判定的語意陷阱-續行先接回再判-引號外token起頭的井號是註解-只有單引號是字面-外層語意先查整段原文

## 知識

- [臨] 閘要從一段 Bash／PowerShell 指令字串判斷「裡面有沒有被包起來的某個命令」時（例：`bash -lc 'git commit …'`），用 regex 比「shell 名緊接執行旗標」會漏掉一般寫法：shell 名與旗標之間夾啟動選項（`bash -l -c`、`powershell -NoProfile -ExecutionPolicy Bypass -Command`、`cmd /d /s /c`）、Windows 安裝路徑含空白要加引號（`"C:/Program Files/Git/bin/bash.exe" -lc …`）、PowerShell 用 `&` 呼叫（`& "…pwsh.exe" -Command …`）。先把引號內容清空再比 regex 的做法，會連帶把帶引號的執行檔路徑一起抹掉。
- [臨] 收斂的做法是斷詞：保留引號狀態切段、每個 token 留原文與剝一層引號的值，看執行檔 basename（去路徑、去 .exe、不分大小寫），再往後找該 shell 的執行旗標：POSIX shell 的短旗標組含 c 就算（-c、-lc、-ec），內層是旗標後那一個 token；PowerShell 認 -Command 與縮寫（-c、-com…），cmd 認 /c、/k，內層是旗標後整串。逐條補 regex 會一直被下一種寫法打穿。
- [臨] 取出內層後要認真正的子命令，不能只看「先出現 git、後出現 commit」字樣：`bash -lc 'git log --grep=commit'` 是查詢。內層的 git 子命令全是查詢白名單（log/status/diff/show）才放行；內層真有 commit、再包一層（遞迴設上限，超過上限只看字樣）、或判不明，一律照原本的檢查走（fail-closed）。
- [臨] 快篩與解析器要用同一套大小寫規則：Windows 上 `Git commit`、`GIT.EXE commit` 都能執行，若快篩用大小寫敏感的 `"git" in command` 先放掉，後面認得大小寫的解析器根本跑不到。
- [臨] 驗證這類閘要以「一般人會怎麼寫」出反例，每條反例換回修正前版本要紅在斷言；四輪外部審查的 BLOCK 全是一般寫法（啟動選項、帶引號路徑、續行、註解撇號），刻意構造的 shell 技巧（變數間接 `x=git; $x commit`）可列已知邊界。
- [臨] 判斷指令有沒有做某個動作（例如 git push）要逐段看段首的子命令：段用 &&、||、;、|、&、換行切開，子命令前面只准全域選項和環境變數指定；echo、commit 訊息裡的字樣、--dry-run／-n 都不算。
- [臨] 從 transcript 配 tool_use 和 tool_result 時，跨次掃描要保留還沒等到結果的 tool_use id，不然結果晚寫一步就漏配。
- [臨] 判「指令裡有沒有呼叫 git」的樣式要排除路徑裡的 .git（`ls repo/.git/hooks`）：不排除的話，唯讀指令會被當成「git 段比掃描器認到的多」，退回較粗的整條判法而誤擋。

## 行動

- 寫閘要從指令字串認包裝命令時，先寫斷詞器（保留引號、留原文與值），用 basename＋執行旗標判包裝，不用 regex 比整串
- 內層用真子命令判，查詢白名單外或判不明一律走原檢查
- 快篩條件與解析器的大小寫規則對齊

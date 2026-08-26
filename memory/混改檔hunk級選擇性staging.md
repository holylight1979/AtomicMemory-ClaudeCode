# 混改檔hunk級選擇性staging

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: hunk, 混改檔, 選擇性 staging, git apply, 併發 session, exact-stage
- Created-at: 2026-08-13
- Related: 併發-session-共用工作樹-收尾選擇性-staging-勿-git-add-a, commit-前必須核對-staged-清單而非只信自己-add-了什麼, 併發session共用的不只工作樹-執行中的應用程式行程也是共用資源

## 知識

- [臨]（2026-08-12 Proj-JARVIS T7 實戰）同一檔被兩個 session 混改時，exact-stage 下探到 hunk 層：`git diff <file>` 存 patch → 以 `(?m)^(?=@@ )` 切 hunk、只留自己的重組 patch → `git apply --cached my.patch`（按 context 搜尋，容忍行號飄移）。對方未完成的 hunk 留在工作樹不動。
- **How to apply:** commit 前 `git diff --cached <file>` 逐檔驗證 staged 只含自己的 hunk；前提：staged tree（HEAD+自己改動）自身可編譯、不依賴對方未 commit 的新檔。[[併發-session-共用工作樹-收尾選擇性-staging-勿-git-add-a]]
- [觀]（2026-08-25 MudClient 雙 Claude 夜班實戰，四次 commit 皆用）三個補強缺一不可：① **CRLF repo 的 patch 要走 bytes**——Python `text=True`／universal newline 會剝掉 `\r`，`git apply --cached` 回「patch does not apply」；`subprocess.run(capture_output=True)` 拿 bytes、`splitlines(keepends=True)` 切 hunk、bytes 餵回 apply。② **同一個 hunk 混了兩包**（例：三段新測試連在一起）regex 選不開時，改「直接寫 index」：工作檔去掉對方段落 → `git hash-object -w --stdin` → `git update-index --cacheinfo 100644,<hash>,<path>`。③ **commit 前用隔離匯出驗 staged tree**：`git checkout-index -a --prefix=<暫存>/` → 在暫存目錄 `dotnet build -o` ＋跑自測；兩次都抓到 `git add <檔>` 把對方半成品 hunk 掃進 index（HEAD+自己 hunk 不編譯），比 `git diff --cached` 目視可靠。
- **How to apply:** 每個混改檔先 `git reset HEAD -- <檔>` 再以自己的識別字（方法名／欄位名）regex 選 hunk（`-U1` 降低相鄰 hunk 黏連）；staged 後 `git show :<檔> | grep -cE <對方識別字>` 應為 0；隔離 build 綠才 commit。regex 漏選的小 hunk（訊息文字）會留在工作樹——下一包 commit 前 `git diff` 再掃一次自己的殘留。

## 行動

- （依知識內容判斷）

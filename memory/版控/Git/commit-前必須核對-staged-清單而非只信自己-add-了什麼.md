# commit 前必須核對 staged 清單而非只信自己 add 了什麼

- Scope: global
- Author: holylight
- Confidence: [固]
- Trigger: git diff --cached, staged 清單, commit 前核對, 誤提交, 別的 session 的檔
- Created-at: 2026-08-07
- Related: 併發-session-共用工作樹-收尾選擇性-staging-勿-git-add-a, sed-i-在-crlf-repo-會整檔改換行, vendor-二進位-中間目錄路徑會嵌進組件-暫存路徑必須固定否則雜湊不可重現, 混改檔hunk級選擇性staging, grok協作實戰認知-特質與監工分工手感, 驗收裁判對多階段戰役的等待回合會誤判為完工宣稱-規格檔只綁當前phase, svn-commit-中文訊息在-cp950-主控台會亂碼-必加-encoding-utf-8

## 知識

- [固] 自己 `git add` 了哪些檔 ≠ index 裡有哪些檔。別的 session、MCP 工具（如 `atom_write`）或 hook 都可能已先 stage 東西，`git commit` 會一併帶走。**固定做法：commit 前跑 `git diff --cached --name-only` 逐行核對，或改用 `git commit -- <明確路徑>`。** 實際踩過：add 了 2 檔、commit 場報 6 檔，多出四個是另一 session 的 atom 與記憶索引，被掛在無關的 commit message 底下；已 push 後重寫歷史只會製造更多混亂。
- [固] 清單核對不夠——**單檔內容也會混人**：共用工作樹併發下，`git add` 吸的是 add 當下的工作樹；即使幾分鐘前 diff 乾淨，他 session 在窗口間落筆就把他人 WIP 一併吸進 index（2026-08-13 R1 實踩 ClientLlmService.cs 混入 U1 不可編譯 WIP）。撞檔候選 add 後逐檔 `git show :<path> | grep <他人特徵詞>` 驗歸屬。
- [固] 混入時的修法（不動工作樹、不毀他人進行中工作）：從 HEAD blob 重建「HEAD＋僅自己改動」版 → `git hash-object -w` → `git update-index --cacheinfo 100644,<oid>,<path>` → 留 note 告知對方 rebase；禁 checkout/reset。blob 換行可能是 LF（autocrlf），字串比對前先正規化。

## 行動

- commit 前一律先 `git diff --cached --name-only`，確認每一行都是本次該交的；有多出來的就 `git restore --staged` 拿掉再 commit。

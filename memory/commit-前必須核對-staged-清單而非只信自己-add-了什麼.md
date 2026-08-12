# commit 前必須核對 staged 清單而非只信自己 add 了什麼

- Scope: global
- Author: holylight
- Confidence: [觀]
- Trigger: git diff --cached, staged 清單, commit 前核對, 誤提交, 別的 session 的檔
- Created-at: 2026-08-07
- Related: 併發-session-共用工作樹-收尾選擇性-staging-勿-git-add-a, sed-i-在-crlf-repo-會整檔改換行

## 知識

- [觀] 自己 `git add` 了哪些檔 ≠ index 裡有哪些檔。別的 session、MCP 工具（如 `atom_write`）或 hook 都可能已先 stage 東西，`git commit` 會一併帶走。**固定做法：commit 前跑 `git diff --cached --name-only` 逐行核對，或改用 `git commit -- <明確路徑>`。** 實際踩過：add 了 2 檔、commit 場報 6 檔，多出四個是另一 session 的 atom 與記憶索引，被掛在無關的 commit message 底下；已 push 後重寫歷史只會製造更多混亂。

## 行動

- commit 前一律先 `git diff --cached --name-only`，確認每一行都是本次該交的；有多出來的就 `git restore --staged` 拿掉再 commit。

# 共用工作樹只stage自己的hunk-別用unidiff-zero-換回HEAD原文再update-index

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 部分 hunk, 只 stage 自己的, unidiff-zero, git apply --cached, update-index --cacheinfo, checkout-index, 共用工作樹 commit, 別的 session 也改了同一檔
- Created-at: 2026-10-16
- Related: 併發-session-共用工作樹-收尾選擇性-staging-勿-git-add-a
- Source: session:9c06da1b 2026-10-16
- Quote: 「/continue C:\Users\holylight\.claude\memory\_staging\next-phase-hud-1b.md」

## 知識

- [臨] 同一檔只 stage 自己的 hunk：別用 `git diff -U0`＋`git apply --cached --unidiff-zero`——純插入段沒有上下文，會被放錯位置，暫存區變成壞檔（實遇：函式定義行被搬到別處）。
- [臨] 可靠做法：拿工作區版本，把別人的段落逐字換回 HEAD 原文（每段要剛好出現一次）→ `git hash-object -w` → `git update-index --cacheinfo 100644,<sha>,<路徑>`；之後確認能編譯、`git diff` 只剩別人的段落。
- [臨] 要測「實際要提交的組合」：`git ls-files | git checkout-index --stdin --prefix=<短路徑>/` 匯出暫存區到隔離目錄跑測試；不要 stash 共用工作樹（會動到別人的檔）。Windows 前綴要短（長檔名會超過 260 字元），根目錄的 conftest／pytest.ini 也要一起匯出。

## 行動

- 共用工作樹下同檔有別人的改動：換回 HEAD 原文 → hash-object → update-index，不用 unidiff-zero
- commit 前用 checkout-index 匯出暫存區到短路徑跑關鍵測試

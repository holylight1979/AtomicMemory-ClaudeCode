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
- [臨] 暫存區全機共用、存的是整檔快照：我只 staged 自己的 hunk 之後，另一個 session 對同一檔 git add，整檔蓋掉我 staged 的版本；我接著 commit 就帶走對方 staged 的整批檔、漏掉自己在那幾檔的 hunk，推上去的 HEAD 不一致（程式呼叫 HEAD 還沒有的參數）。
- [臨] commit 前「印出 git diff --cached --name-only」不算檢查：用 && 串在 commit 前只是印，清單多了別人的檔照樣 commit。要寫成會中斷的比對（staged 清單跟預期不同就 exit 1），或整個不碰共用暫存區：GIT_INDEX_FILE=<暫存檔> git read-tree HEAD → 套自己的改動 → write-tree → commit-tree → update-ref 帶舊值比對。
- [臨] 已經撞了且推上去：不改寫歷史；先叫對方把他 staged 的 commit 掉（他的快照本來就不含我的 hunk、HEAD 也沒有，不會蓋掉我的），再補自己的；先補我的的話，對方下一次 commit 會用舊快照把我的 hunk 蓋回去。
- [臨] 暫存區也是共用的：stage 完要在同一條指令裡馬上 commit。實遇兩次：另一個 session 的 commit 和背景知識收割的 commit，都把我還沒提交的 staged 檔一起帶走，提交訊息對不上；反過來，對方自己沒 stage 的 hunk 也因為暫存區放的是我的版本而漏交。發現擞車先比對 HEAD 與工作區的關鍵字，確認誰的東西進了 HEAD，再通知對方。

## 行動

- 共用工作樹下同檔有別人的改動：換回 HEAD 原文 → hash-object → update-index，不用 unidiff-zero
- commit 前用 checkout-index 匯出暫存區到短路徑跑關鍵測試

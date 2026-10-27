# 取svn工作副本的BASE版-先用status-xml挑出本地改過的檔只對它們svn-cat-r-BASE-沒改過的BASE就是工作樹內容

- Scope: global
- Author: holylight
- Source: 2026-10-23 C# 閱讀路徑 svn 支援實作
- Confidence: [臨]
- Trigger: svn cat -r BASE, svn BASE 版, svn status --xml, svn 取舊版, svn 改動前內容, svn 逐檔 cat 太慢
- Created-at: 2026-10-23
- Related: svn中文路徑實證-cp950內中文走worker安全-cp950外字元best-fit成亂碼讓add-parents建亂碼目錄-targets檔無效, git-cat-file-batch-check的missing行帶回原輸入含空白路徑-成功行只有sha-type-size不帶名字-要按輸入順序配對不能靠名字拆欄

## 知識

- [臨] 要拿 svn 工作副本裡一批檔的 BASE 版（本地改動前的內容）：先跑 `svn status --xml <路徑…>`（只讀本地、不連伺服器），只對 wc-status item 是 modified、replaced、conflicted、missing 這類「有 BASE 且內容可能不同」的檔跑 `svn cat -r BASE`；沒列出來的檔是 normal，BASE 就等於工作樹內容，直接讀磁碟。
- [臨] added、unversioned 沒有 BASE（舊版沒有這個檔）；svn cat 失敗的當新檔並註明。逐檔 svn cat 每檔約 0.2 秒，幾百檔就是幾十秒，這樣挑過只剩真改過的幾檔。

## 行動

- 要比對 svn 本地改動前後：先 status --xml 一次分類，只對改過的檔 svn cat -r BASE，不要逐檔全 cat

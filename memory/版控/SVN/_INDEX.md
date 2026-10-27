# memory/版控/SVN — 範疇索引

> 階層範疇索引（自動生成，`_` 前綴非 atom）。機制見 [[realm-範疇分區機制-v5]]。

## 本層 atom

| Atom | 說明 |
|------|------|
| pwsh-傳中文路徑給svn-exe會亂碼且big5的一字含位元組觸發peg解析-改用python-subprocess | pwsh-傳中文路徑給svn-exe會亂碼且big5的一字含@位元組觸發peg解析-改用python-subprocess |
| svn-commit-中文訊息在-cp950-主控台會亂碼-必加-encoding-utf-8 | svn commit 中文訊息在 cp950 主控台會亂碼-必加 --encoding UTF-8 |
| svn中文路徑實證-cp950內中文走worker安全-cp950外字元best-fit成亂碼讓add-parents建亂碼目錄-targets檔無效 | svn中文路徑實證-cp950內中文走worker安全-cp950外字元best-fit成亂碼讓add-parents建亂碼目錄-targets檔無效 |
| svn反向合併整檔衝突多半是後續修訂換了行尾-以現行檔為底手動拿hunk再位元組比對 | svn反向合併整檔衝突多半是後續修訂換了行尾-以現行檔為底手動拿hunk再位元組比對 |
| workflow-svn | SVN 工作流規則 |
| 取svn工作副本的base版-先用status-xml挑出本地改過的檔只對它們svn-cat-r-base-沒改過的base就是工作樹內容 | 取svn工作副本的BASE版-先用status-xml挑出本地改過的檔只對它們svn-cat-r-BASE-沒改過的BASE就是工作樹內容 |
| 大型svn工作副本整棵svn-status很慢-每檔約45微秒-hook裡查svn狀態要設時間上限-逾時改查點名的檔並記住這個根很慢 | 大型svn工作副本整棵svn-status很慢-每檔約45微秒-hook裡查svn狀態要設時間上限-逾時改查點名的檔並記住這個根很慢 |

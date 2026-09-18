# svn反向合併整檔衝突多半是後續修訂換了行尾-以現行檔為底手動拿hunk再位元組比對

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: svn merge -c, 反向合併, reverse merge, 整檔衝突, 行尾, CRLF, LF, 退版, svn revert 修訂, tree conflict, 退回舊版
- Created-at: 2026-09-14

## 知識

- [臨] svn 反向合併（svn merge -c -N .）時若某檔從第 1 行到最後一行整個衝突，先懷疑是後續別人的修訂把行尾換了（CRLF→LF），不是內容真的全變；用 python 以 bytes 數 b'\r\n' 與 b'\n' 就能確認（msys 的 grep/cat -A 會做文字模式轉換，不可信）。
- [臨] 解法：以 .working（現行內容）為底，只把目標修訂的 hunk 用 python bytes 手動拿掉，插回的舊行要先剔 \r（從舊版檔取行會帶 CRLF），再 svn resolve --accept working。驗法：只被自己修訂動過的檔 svn cat -r <退版前修訂> 與工作副本位元組相等；有別人後續修訂的檔，逐一 svn diff -c <別人修訂> 的 + 行都還在。
- [臨] 反向合併自己分支的歷史不會留 svn:mergeinfo（顯示 Recording mergeinfo 但 svn status 根目錄無 M）；要排除子樹（別人維護的目錄），在根合併後立刻 svn revert -R <子樹> 即可。後續修訂改過的新增檔退版時會 tree conflict（local edit, incoming delete），svn resolve --accept working 後 svn delete --force。
- [臨] codex exec -s read-only 在 Windows 撺 CreateProcessWithLogonW 1385 時改加 -c 'windows.sandbox="unelevated"'；另 msys bash 裡 sleep 被工具擋，等條件用 until 迴圈。

## 行動

- 整檔衝突先算 bytes 行尾，再決定手合
- 退版驗收用「與退版前修訂位元組相等」當硬標準

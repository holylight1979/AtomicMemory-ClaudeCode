# Windows路徑包含判斷兩側要統一表示-先去長路徑前綴再normpath-轉長路徑後再normpath

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 8.3 短路徑, GetLongPathNameW, normpath, 長路徑前綴, UNC, 暫存目錄判斷, gettempdir, 路徑包含, HOLYLI~1
- Created-at: 2026-10-13
- Source: session:ec069e59 2026-10-13
- Quote: 「你是 v6.0 的「待命 track-e」，總控台是 claude-ad。現在只做三件事就停：①用 ToolSearch 載入工具（query: select:SendMessage,ListAgents）②用 ListAgents 看自己的名字（列表最上面「This session is …」那行）③SendMessage 給 claude-ad 一句「待命 track-e：<你的名字>」。之…」

## 知識

- [臨] 判斷「某路徑在某目錄底下」時兩側要轉成同一種表示再比：Windows 的 `tempfile.gettempdir()` 可能回 8.3 短路徑（`C:\Users\XXXX~1\…`），同一目錄也會以長路徑出現；用 GetLongPathNameW 轉長路徑（檔案不存在就往上找存在的祖先轉、再接回尾段）。
- [臨] 順序：先拿掉 `\\?\` 前綴（磁碟機路徑去前綴，`\\?\UNC\server\share` 轉 `\\server\share`）——`os.path.normpath` 遇到 `\\?\` 開頭會整條原樣回傳，連 `..` 都不消；再 normpath → 轉長路徑 → 轉完再 normpath（API 會保留 `..`，否則 `<tmp>\..\..\專案\x.py` 會被判成在 tmp 底下）。
- [臨] UNC 路徑不呼叫 GetLongPathNameW（不為了比對去查網路）；GLOBALROOT、`\\.\` 裝置命名空間、`\\?\Volume{…}`、`C:foo` 磁碟機相對路徑不展開，判不在底下（錯的方向是多要證據，不是漏記）。轉換失敗（API 回 0 不拋例外）時，帶短檔名記號 `~數字` 的路徑要在 stderr 說一聲，不靜默。

## 行動

- 寫路徑包含判斷：兩側走同一個正規化函式（去前綴→normpath→長路徑→normpath）
- 測試要涵蓋長短交叉、前綴單側／雙側、`..` 逃出、別磁碟機與 UNC

# 當使用-mysqlx-協定33060進行資料讀取時如果-mysql-server-重啟後-x-連線狀態異常cli

- Scope: global
- Author: auto-captured
- Confidence: [臨]
- Trigger: auto-capture
- Created-at: 2026-06-18

## 知識

- [臨] 當使用 mysqlx 協定（33060）進行資料讀取時，如果 MySQL Server 重啟後 X 連線狀態異常，client 端在執行 `await conn.Select(...).Execute<T>(...)` 時，會因為等待一個永遠不會到來的回應而無限 hang。此問題與資料量或邏輯無關。

## 行動

- （依知識內容判斷）

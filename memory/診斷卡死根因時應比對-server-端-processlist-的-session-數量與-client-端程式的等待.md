# 診斷卡死根因時應比對-server-端-processlist-的-session-數量與-client-端程式的等待

- Scope: global
- Author: auto-captured
- Confidence: [臨]
- Trigger: auto-capture
- Created-at: 2026-06-18

## 知識

- [臨] 診斷卡死根因時，應比對 Server 端 Processlist 的 Session 數量與 Client 端程式的等待狀態。如果 Server 端顯示 `Mysqlx_connections_accepted` 和 `Mysqlx_connections_closed` 數值匹配（即連線已關閉），

## 行動

- （依知識內容判斷）

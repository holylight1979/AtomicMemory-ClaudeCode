# 閒置session收到跨session訊息會自動開新回合處理-不必靠工具呼叫或背景sleep叫醒-背景session收信做完是結束不是閒置

- Scope: global
- Author: holylight
- Source: 兩個 claude --bg（haiku）探針實測，2026-11-04
- Confidence: [臨]
- Trigger: 跨 session 訊息何時送進來, 等同伴回覆, 閒置收信, 自動開回合, notify_when_idle, 背景 session 結束, 被叫回來, SendMessage 等回信
- Created-at: 2026-11-04
- Related: 跨session訊息在收件端進計畫模式時會被扣住等使用者核准-逾時就作廢不送達-補充事項要寫進開工句或等對方離開計畫模式再送, feedback-要轉告別的session就自己sendmessage-名稱對不上session-id就用開始時間比對對話紀錄第一筆

## 知識

- [臨] 實測：閒置的 session 收到 SendMessage 會自動開新回合處理，0.04 秒進對話、2 秒內回信，中間沒有任何工具呼叫。等同伴回覆時直接結束回合就好，回信到了自己會被叫回來，不必空呼叫 ListAgents 或背景跑 sleep 當計時器。
- [臨] `notify_when_idle` 可用。背景 session 收信做完的狀態是「結束」不是閒置：判它做完了沒看回信或 `claude agents --json` 的 status，不要等它變閒置。收件端權限模式不同時訊息可能被扣，見 crossSessionInbound 那張卡。

## 行動

- 等同伴回信：送出後直接結束回合，不掛 sleep 計時器、不輪詢
- 判背景 session 做完沒：看回信或 claude agents --json status，不等 idle

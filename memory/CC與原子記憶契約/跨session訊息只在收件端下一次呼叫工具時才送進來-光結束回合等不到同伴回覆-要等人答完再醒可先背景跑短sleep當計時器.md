# 跨session訊息只在收件端下一次呼叫工具時才送進來-光結束回合等不到同伴回覆-要等人答完再醒可先背景跑短sleep當計時器

- Scope: global
- Author: holylight
- Source: track-data-root-2 A8 實走 006（session 616e4407）2026-10-14，調度總控台代寫
- Confidence: [臨]
- Trigger: 跨 session 訊息何時送進來, 等同伴回覆, 結束回合等不到, 背景 sleep 計時器, 被叫回來, ListAgents 收信
- Created-at: 2026-10-14

- Related: 跨session訊息在收件端進計畫模式時會被扣住等使用者核准-逾時就作廢不送達-補充事項要寫進開工句或等對方離開計畫模式再送

## 知識

- [臨] 跨 session SendMessage 的訊息只在收件端下一次呼叫工具時才送進對話；光是結束回合等，沒有工具呼叫就永遠等不到同伴回覆，至少要呼叫一次工具（例 ListAgents）讓訊息進來。要讓 Stop 先處理完放行、自己之後再醒來：先在背景跑一個短 sleep 當計時器再結束回合，計時器跑完的通知會把 session 叫回來。

## 行動

- 等同伴回覆時不要空手結束回合；用背景短 sleep 或下一次工具呼叫讓訊息進來

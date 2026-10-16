# feedback-要轉告別的session就自己SendMessage-名稱對不上session-id就用開始時間比對對話紀錄第一筆

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 轉告, SendMessage, ListAgents, 同伴 session, 跨 session 訊息, 哪個 session, session id 對不上, 請使用者轉告
- Created-at: 2026-10-16
- Related: 自己flag的維護動作直接做完不要反問
- Source: session:eefb3380#fe87d67f 2026-10-16
- Quote: 「轉告，你自己去SendMessage呀」

## 知識

- [臨] 使用者原話：「轉告，你自己去 SendMessage 呀」——我在收尾報告把「把兩件事轉告另一個 session」列成使用者的下一動，理由是對不出哪個同伴是它。能自己做的轉告不推給使用者。
- [臨] ListAgents 的同伴名稱（claude-xx [ref]）跟 session id 沒有對應關係（例：本 session eefb3380 叫 claude-af），資料根也沒有對照檔。對法：讀目標 session 的對話紀錄（projects/<專案>/<sid>.jsonl）第一筆 timestamp（UTC），跟 ListAgents 的「started N 小時前」比；只有一個對得上就是它。訊息第一句寫明「若你不是 <sid> 請忽略」，對錯也不誤導。

## 行動

- 收尾前要轉告別的 session 的事：自己 ListAgents＋比開始時間找到它，直接 SendMessage，不列成使用者的下一動
- 訊息開頭一句自足（接收端人類只看得到第一行），附「不是你就忽略」與「不需要回覆」

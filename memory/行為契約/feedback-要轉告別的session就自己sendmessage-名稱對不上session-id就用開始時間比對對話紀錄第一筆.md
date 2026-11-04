# feedback-要轉告別的session就自己SendMessage-名稱對不上session-id就用開始時間比對對話紀錄第一筆

- Scope: global
- Author: holylight
- Source: session:eefb3380#fe87d67f 2026-10-16
- Quote: 「轉告，你自己去SendMessage呀」
- Confidence: [臨]
- Trigger: 轉告, SendMessage, ListAgents, claude agents --json, 同伴 session, 跨 session 訊息, 哪個 session, session id 對不上, 請使用者轉告
- Created-at: 2026-10-16
- Related: 自己flag的維護動作直接做完不要反問

## 知識

- [臨] 使用者原話：「轉告，你自己去 SendMessage 呀」——我在收尾報告把「把兩件事轉告另一個 session」列成使用者的下一動，理由是對不出哪個同伴是它。能自己做的轉告不推給使用者。
- [臨] 找目標 session：`claude agents --json` 每列直接給 sessionId 與 name，對照就知道是誰，不必再拿 transcript 第一筆時間去比。用 `--name <軌名>` 起的 session 名字固定，就是 SendMessage 的地址；沒指定名字的分頁是系統配的 claude-xx，reload 後會換，送前先重查。訊息第一句寫明「若你不是 <軌名或 sid> 請忽略」。

## 行動

- 收尾前要轉告別的 session 的事：自己用 claude agents --json（或 ListAgents）找到它，直接 SendMessage，不列成使用者的下一動
- 訊息開頭一句自足（接收端人類只看得到第一行），附「不是你就忽略」與「不需要回覆」

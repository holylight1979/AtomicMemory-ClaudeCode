# 跨session訊息在收件端進計畫模式時會被扣住等使用者核准-逾時就作廢不送達-補充事項要寫進開工句或等對方離開計畫模式再送

- Scope: global
- Author: holylight
- Source: 調度總控台 track-workflow-cleanup 補充訊息逾時 2026-10-14
- Confidence: [臨]
- Trigger: 跨 session 訊息被扣住, Cross-session delivery notice, held by that session, not approved before expiry, 計畫模式 收不到訊息, 權限模式不同, 開工句補充
- Created-at: 2026-10-15
- Related: 跨session訊息只在收件端下一次呼叫工具時才送進來-光結束回合等不到同伴回覆-要等人答完再醒可先背景跑短sleep當計時器
- Quote: 「確認看看還有什麼沒做或者沒收割的，要關session了」

## 知識

- [臨] 實測：開工句送到工作分頁後，它照指示進計畫模式；之後給它的補充訊息因為雙方權限模式不同被扣住，要使用者在那個分頁按核准，沒人按就逾時作廢，對方完全看不到。寄件端會收到 held 與 not approved before expiry 兩則通知；重送只會再被扣。
- [臨] 反過來，計畫模式的分頁送出的交付信也可能沒送到總控台（本場清理軌的交付是原設計者手動轉來的）。

## 行動

- 會進計畫模式的工作軌：要說的事一次寫進開工句，不靠事後補充
- 收到 held 通知：告訴使用者那個分頁有訊息待核准，或請他審計畫時順便確認，不重送

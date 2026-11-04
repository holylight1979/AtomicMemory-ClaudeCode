# feedback-自動化腳本收尾精準關閉自己開的瀏覽器分頁-借用的只還原不關

- Scope: personal:holylight
- Author: holylight
- Source: C:/tmp/office/collect_month_worklog.js
- Quote: 工具要增加，如果都處理好以後，你開啟用來查詢的那些工具、網頁要精準的關閉
- Confidence: [臨]
- Trigger: 精準關閉, 收尾關閉, 自動化腳本, Playwright, CDP, Chrome Debug, 瀏覽器分頁, 查詢工具, 開啟的網頁, browser cleanup
- Created-at: 2026-10-07

## 知識

- [臨] 使用者要求：自動化腳本把資料抓完後，用來查詢而開啟的工具／網頁要「精準關閉」——自己啟動的瀏覽器整個關、自己開的分頁只關那一個、借用使用者已登入的分頁只把內容導回進來時的頁面；其他分頁一律不碰。失敗停在登入頁時例外：保留視窗讓人登入再跑。
- [臨] 實作要點：啟動時記下 launched / opened / homeUrl 三個旗標，收尾用 try-finally 依旗標分流；Playwright connectOverCDP 的 browser.close() 只斷連線不關瀏覽器，要真關用 newBrowserCDPSession().send('Browser.close')。

## 行動

- 寫會開瀏覽器／外部工具的腳本時，一開始就設計收尾分流，不是跑完再補
- 交付時列出三種情境（自己開／借用／失敗停住）各做什麼並實測

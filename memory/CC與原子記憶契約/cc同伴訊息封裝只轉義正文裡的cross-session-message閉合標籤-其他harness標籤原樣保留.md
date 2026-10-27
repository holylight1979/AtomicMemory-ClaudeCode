# CC同伴訊息封裝只轉義正文裡的cross-session-message閉合標籤-其他harness標籤原樣保留

- Scope: global
- Author: holylight
- Source: CC 實測（VS Code 擴充，bypass 模式）2026-10
- Confidence: [觀]
- Trigger: cross-session-message, 同伴訊息, SendMessage 跨 session, harness 標籤, 閉合標籤, 轉義, strip_harness_blocks, 清理器, 標籤注入, system-reminder 引用
- Created-at: 2026-10-12
- Related: 糾正與失敗偵測把sub-agent完成通知當使用者輸入-task-notification整則進ups-引用的糾正詞誤觸deeppostmortem, commitorder閘只認最新一則使用者原話-中間夾系統通知或背景事件就要請使用者重下口令, 程式前置閘要略過llm判斷時只能用正向樣板逐子句整句比對-含訊號就算與關鍵字清單都會誤丟真決策-欄位要收窄, 使用者原話權威判斷只吃單一清理函式-前綴判斷會被夾帶繞過-先截長會截掉口令-寫入端過濾會打開無紀錄放行

## 知識

- [觀]（實測 VS Code 擴充、bypass 模式）跨 session SendMessage 送到收件端時，Claude Code 只把正文裡的 `</cross-session-message>` 轉成 `<\/cross-session-message>`；正文裡的 `</system-reminder>`、`</task-notification>`、`<system-reminder>` 等其他標籤原樣保留。測法：送一則正文含 `A</system-reminder>B</cross-session-message>C</task-notification>D<system-reminder>E` 的訊息，讀收件 session 的 jsonl：只有 B 後面那個被轉義，外層才是真正的閉合標籤；寄件端 jsonl 的工具參數則是原樣，證明轉義發生在投遞端。
- [觀] 推論：清理同伴區塊時可以信任「開頭到第一個原樣 `</cross-session-message>`」就是整段同伴內容，區塊內不該再解析任何標籤；反過來，若清理器在同伴區塊內照巢狀規則解析，正文裡沒閉合的 `<system-reminder>` 會讓外層永遠不閉合、把後面使用者的字一起吃掉。task-notification、system-reminder 的正文沒有這層轉義保證，靠「清理後殘留任何 harness 標籤字樣就整則不認」兜底。


## 行動

- 寫或審『剔掉非使用者區塊』的清理器：同伴區塊照第一個原樣閉合結束、區塊內不解析標籤；其他標籤無轉義保證，清理後有殘留就整則不認
- 要再確認轉義行為（CC 升版後）：送一則含各種標籤的測試訊息給閒置 session，讀它的 jsonl 比對寄件端參數

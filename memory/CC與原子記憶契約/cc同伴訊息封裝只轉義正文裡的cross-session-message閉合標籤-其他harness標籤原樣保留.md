# CC同伴訊息封裝只轉義正文裡的cross-session-message閉合標籤-其他harness標籤原樣保留

- Scope: global
- Author: holylight
- Source: workflow/v6-inbox/to-track-a3/026-returned.md（實測段）
- Confidence: [臨]
- Trigger: cross-session-message, 同伴訊息, SendMessage 跨 session, harness 標籤, 閉合標籤, 轉義, user_typed_text, strip_harness_blocks, 清理器, 標籤注入, system-reminder 引用
- Created-at: 2026-10-12
- Related: 糾正與失敗偵測把sub-agent完成通知當使用者輸入-task-notification整則進ups-引用的糾正詞誤觸deeppostmortem, commitorder閘只認最新一則使用者原話-中間夾系統通知或背景事件就要請使用者重下口令
- Quote: 「<cross-session-message from="uds:\\.\pipe\LOCAL\cc-msg-aa1d485368fca9958b7357c8a9a7531a" from-name="claude-88" from-mode="bypass"> 收 </cross-session-message>」

## 知識

- [臨]（實測 2026-10-12，VS Code 擴充、bypass 模式）跨 session SendMessage 送到收件端時，Claude Code 只把正文裡的 `</cross-session-message>` 轉成 `<\/cross-session-message>`；正文裡的 `</system-reminder>`、`</task-notification>`、`<system-reminder>` 等其他標籤原樣保留。測法：送一則正文含 `A</system-reminder>B</cross-session-message>C</task-notification>D<system-reminder>E` 的訊息，讀收件 session 的 jsonl：只有 B 後面那個被轉義，外層才是真正的閉合標籤；寄件端 jsonl 的工具參數則是原樣，證明轉義發生在投遞端。
- [臨] 推論：清理同伴區塊時可以信任「開頭到第一個原樣 `</cross-session-message>`」就是整段同伴內容，區塊內不該再解析任何標籤；反過來，若清理器在同伴區塊內照巢狀規則解析，正文裡沒閉合的 `<system-reminder>` 會讓外層永遠不閉合、把後面使用者的字一起吃掉。task-notification、system-reminder 的正文沒有這層轉義保證，靠「清理後殘留任何 harness 標籤字樣就整則不認」兜底。

## 行動

- 寫或審『剔掉非使用者區塊』的清理器：同伴區塊照第一個原樣閉合結束、區塊內不解析標籤；其他標籤無轉義保證，清理後有殘留就整則不認
- 要再確認轉義行為（CC 升版後）：送一則含各種標籤的測試訊息給閒置 session，讀它的 jsonl 比對寄件端參數

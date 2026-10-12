# fail-closed閘裡的附加輸出要隔離例外-否則附加資訊炸掉會被當閘異常擋住放行

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: fail-closed, 閘環境異常, except Exception deny, 附加輸出, 候選填空, 閘內例外, 外部報告解析, OverflowError mktime
- Created-at: 2026-10-12
- Source: session:a1cd2ad7 2026-10-12
- Quote: 「<cross-session-message from="uds:\\.\pipe\LOCAL\cc-msg-9f5042f2e3dc154060b9c298be50f88d" from-name="claude-2d" from-mode="bypass"> 是，我是 a2 工作 session（worktree C:\Users\holylight\.claude-wt\track-a2，分…」

## 知識

- [臨] 外層 `try: … except Exception: deny`（不知道就擋，不 fail-open）的閘裡，若在判定「放行」之後還產生附加資訊（候選清單、提示、報告摘要），附加資訊的任何例外都會被外層當成閘壞掉而 deny，把本來該放行的動作擋掉；若例外發生在落盤之前，計數等狀態沒存，下次同樣路徑又炸又擋，變成永久卡死。實例：一份欄位型別不對的外部報告（`generated_at: 0000-01-01` 讓 `time.mktime` 拋 OverflowError、`part: 7` 讓字串串接拋 TypeError）讓整個專案每個檔的第二次 Edit 都被擋。
- [臨] 修法分兩層，都要做：①解析外部輸入的那層把型別收乾淨（日期換算包 try 退回備案、欄位型別不對整列丟棄並計數附一行原因），②附加輸出在閘內用自己的 try 隔離，失敗只附一行「X 產生失敗（不影響本次放行）」＋記 log，閘的放行／擋判定不受影響。②不是把擋降成提醒：判定在附加輸出之前已經做完。同理，在同一個 fail-open 包裝裡把附加輸出和主要注入放一起，附加炸掉會連主要注入一起吞掉。
- [臨] 審查時的問法：這個閘的 `except` 範圍裡，有沒有「判定之後才跑、讀外部資料」的程式？有就是這個坑。

## 行動

- 寫 fail-closed 閘時，判定之後的附加輸出用獨立 try 包住，失敗附一行說明＋log，不改變判定
- 閘裡讀外部報告／設定時，日期與欄位型別都要驗，不信外部格式

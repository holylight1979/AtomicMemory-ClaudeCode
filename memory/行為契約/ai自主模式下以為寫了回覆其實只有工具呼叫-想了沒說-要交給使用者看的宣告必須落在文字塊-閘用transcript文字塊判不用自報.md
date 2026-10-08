# AI自主模式下以為寫了回覆其實只有工具呼叫-想了沒說-要交給使用者看的宣告必須落在文字塊-閘用transcript文字塊判不用自報

- Scope: global
- Author: holylight
- Source: session e40bc31f，tri-link 某專案/047／root/064
- Confidence: [臨]
- Trigger: 想了沒說, 以為寫了, 定位三行, located=false, 文字塊, thinking 不算, 自主模式, 自報不可信, transcript 驗
- Created-at: 2026-10-07
- Quote: 「接手「AI 寫碼守門三方討論」的根層總控端。先讀 C:\Users\holylight\.claude\memory\_staging\next-phase-AI寫碼守門三方討論.md 全文，照「下一步」做：重掛 Monitor 盯 <專案路徑>\.claude\inbox\tri-link\ 的 from-projects 與 from-某專案、對帳信箱、做 R4 與 R5、每 6…」

## 知識

- [臨] 實證（某專案 session，注入閘第一批真實 log）：AI 在信裡堅稱「改檔前我在回覆裡寫了定位三行」，transcript 注入點之後 70 筆 assistant 紀錄：tool_use 45、thinking 24、text 1，沒有任何一筆含那三行。自主連續工作時「想了就以為說了」是真會發生的失敗形狀。所以：①要交給使用者看的宣告（定位、判斷、自檢）必須落在文字塊，不是 thinking、不是工具參數；②闘判「有沒有交」只能看 transcript 的 text block，不能信 AI 自報；③別人說「我明明寫了」先拿 transcript 核，不先懷疑判法。
- [臨] 更正：那場「以為寫了其實沒有」後來查明大半是 harness 吃字（同一回合先文字再工具的文字不進 transcript，三邊各自複驗），不是模型想了沒說。不變的結論：閘仍不能信自報；但判「有沒有交」要三管道都看（文字塊、工具呼叫參數、thinking），只看文字塊會把真交了的判成沒交。實證：同一人同管線，三行放 Bash 開頭註解 5/5 被認到，只放回覆文字 0/6；純文字回合結尾的文字才留得下。

## 行動

- 改檔前的定位三行／任何「我已說明」→ 確認它是在回覆文字裡輸出的，不是在思考裡
- 闘或審查要驗「AI 有沒有交 X」→ 掃 transcript text block，把自報當待驗證主張

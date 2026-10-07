# AI自主模式下以為寫了回覆其實只有工具呼叫-想了沒說-要交給使用者看的宣告必須落在文字塊-閘用transcript文字塊判不用自報

- Scope: global
- Author: holylight
- Source: session e40bc31f，tri-link tslg/047／root/064
- Confidence: [臨]
- Trigger: 想了沒說, 以為寫了, 定位三行, located=false, 文字塊, thinking 不算, 自主模式, 自報不可信, transcript 驗
- Created-at: 2026-10-07

## 知識

- [臨] 實證（TSLG session，注入閘第一批真實 log）：AI 在信裡堅稱「改檔前我在回覆裡寫了定位三行」，transcript 注入點之後 70 筆 assistant 紀錄：tool_use 45、thinking 24、text 1，沒有任何一筆含那三行。自主連續工作時「想了就以為說了」是真會發生的失敗形狀。所以：①要交給使用者看的宣告（定位、判斷、自檢）必須落在文字塊，不是 thinking、不是工具參數；②闘判「有沒有交」只能看 transcript 的 text block，不能信 AI 自報；③別人說「我明明寫了」先拿 transcript 核，不先懷疑判法。

## 行動

- 改檔前的定位三行／任何「我已說明」→ 確認它是在回覆文字裡輸出的，不是在思考裡
- 闘或審查要驗「AI 有沒有交 X」→ 掃 transcript text block，把自報當待驗證主張

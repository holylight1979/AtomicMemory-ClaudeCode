# 擋訊息教的替代管道會被當成替代做法-寫明註解只放在不寫檔的指令上-宣告完照常用edit-write-同類說法全面grep並用掃原始碼的案例守住

- Scope: global
- Author: holylight
- Source: 2026-10-23 第二意見等待修補實測
- Confidence: [臨]
- Trigger: 擋訊息措辭, 替代管道, Bash 註解宣告, 改用 Bash 寫檔, python -c 改檔, 改檔清單空, 擋 Edit Write, 擋訊息引導
- Created-at: 2026-10-22
- Related: datafileask宣告行寫在回覆文字裡同一則訊息的工具呼叫在pretooluse讀不到-先跑一個bash開頭註解行再發edit, bash寫入目標解析器會把python-c與pytest-c當成無法判定而擋-改寫成腳本檔或讓pytest自找ini-grep工具預設跳過gitignore檔

## 知識

- [臨] 擋訊息教的「替代管道」會被 AI 當成替代做法：擋 Edit／Write 的訊息寫「宣告也可以寫成 Bash 指令開頭的 # 註解」，被讀成「改用 Bash 寫檔」，之後全程 python -c 改檔。
- [臨] 後果：Bash 寫入判不出目標，改檔清單整個 session 是空的，靠它的三道閘都看不到這些改動。
- [臨] 修法：擋 Edit／Write 的閘要寫明「註解只放在不寫檔的指令上，宣告完照常用 Edit／Write」；同類說法一次全面 grep 改齊，並用掃原始碼的案例守住（擋訊息再出現這種引導就紅）。

## 行動

- 擋訊息裡提到替代管道：同句寫明它只用在哪、主路徑照舊；改完 grep 全部同類說法，加掃原始碼的案例

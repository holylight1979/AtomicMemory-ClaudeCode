# DataFileAsk宣告行寫在回覆文字裡同一則訊息的工具呼叫在PreToolUse讀不到-先跑一個Bash開頭註解行再發Edit

- Scope: global
- Author: holylight
- Source: commit:b7847dda 2026-10-22（實測）
- Confidence: [臨]
- Trigger: 動資料檔｜, DataFileAsk, 宣告行讀不到, 文字還沒落盤, 資料檔宣告
- Created-at: 2026-10-22
- Related: 擋訊息教的替代管道會被當成替代做法-寫明註解只放在不寫檔的指令上-宣告完照常用edit-write-同類說法全面grep並用掃原始碼的案例守住

## 知識

- [臨] DataFileAsk 的「動資料檔｜…」宣告行寫在回覆文字裡，同一則訊息的工具呼叫在 PreToolUse 讀不到（文字還沒落盤，跟 PAN 拆除同一個原因）。要先跑一個 Bash 開頭 `# 動資料檔｜…` 註解行，再發 Edit。擋訊息目前說「寫在回覆文字」是過時說法（追蹤中）。

## 行動

- （依知識內容判斷）

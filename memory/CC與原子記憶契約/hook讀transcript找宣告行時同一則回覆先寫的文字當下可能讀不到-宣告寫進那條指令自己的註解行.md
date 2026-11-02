# hook讀transcript找宣告行時同一則回覆先寫的文字當下可能讀不到-宣告寫進那條指令自己的註解行

- Scope: global
- Author: holylight
- Source: commit:b7847dda 2026-10-22（實測）
- Confidence: [臨]
- Trigger: 宣告行讀不到, 文字還沒落盤, 宣告寫進指令註解, 負向對照｜, NEGATIVE_CONTROL_DECLARED, 同一則訊息的工具呼叫
- Created-at: 2026-11-02
- Related: 擋訊息教的替代管道會被當成替代做法-寫明註解只放在不寫檔的指令上-宣告完照常用edit-write-同類說法全面grep並用掃原始碼的案例守住
- Supersedes: datafileask宣告行寫在回覆文字裡同一則訊息的工具呼叫在pretooluse讀不到-先跑一個bash開頭註解行再發edit

## 知識

- [臨] 讀 transcript 找 AI 宣告行的 hook：同一則回覆裡先寫的文字，在那次工具呼叫的 hook 執行當下可能還沒寫進 transcript，讀不到。要讓同一次呼叫就被認到，宣告寫進那次指令自己的 `#` 註解行（Bash 開頭一行）。
- [臨] 目前用這套的是負向對照宣告「負向對照｜<這條指令裡出現的路徑或字樣>：<理由>」（規則 NEGATIVE_CONTROL_DECLARED，hooks/wg_release_rules.py）：程式從回覆文字／工具參數／thinking（主檔與子代理檔）加這次指令的 `#` 註解一起找；比對點到的字樣時指令的 `#` 註解行先去掉，宣告寫在註解裡不會自己對上自己。

## 行動

- 要 hook 在同一次呼叫就讀到宣告：寫進那條指令開頭的 # 註解行，不只寫在回覆文字
- 寫負向對照宣告：點到的字樣要是指令真的會跑的那幾行裡的字

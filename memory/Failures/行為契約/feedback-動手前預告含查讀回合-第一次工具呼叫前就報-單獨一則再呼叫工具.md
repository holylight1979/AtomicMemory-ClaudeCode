# feedback-動手前預告含查讀回合-第一次工具呼叫前就報-單獨一則再呼叫工具

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 動手前預告, 執行目標, 預估, PreActionNotice, pre-action-notice, PAN, 查讀不用報, 落盤時差, text_blocks
- Created-at: 2026-09-18
- Related: 禁語-hook-不開引用豁免誤報噪音-vs-契約破洞不對稱, feedback-workflow-discipline

## 知識

- [臨] 使用者 2026-09-18 糾正：「動手前預告」不限修改動作，每回合**第一次呼叫工具前**（grep/sed/跑分析腳本都算）就要輸出「執行目標／預估」。舊契約寫「首次修改動作前」，我照字面在純查讀回合直接 thinking→tool calls，使用者看到的就是「沒說要做什麼、估多久」。
- [臨] 實證（9/10～9/18 閘門 log 133 回合對回 transcript）：26 回合沒預告全是純查讀被閘門攔（sed -n/awk/svn info/變數賦值/python heredoc），根因是契約定義比閘門窄，不是閘門誤判；另 33 回合預告寫了但與 tool call 同一則訊息，hook 讀 transcript 時 text block 尚未落盤（text_blocks=0），2～6 秒後同回合第二個工具呼叫才通過。
- [臨] 修法是改契約不是放寬閘門（同禁語 hook 原則：多提醒的噪音 vs 契約破洞不對稱）。IDENTITY.md 已改為「第一次呼叫工具前，預告單獨成一則可見訊息送出，下一則才呼叫工具」。

## 行動

- 每回合準備呼叫任何工具前，先單獨送出一則含「執行目標：…」「預估：…」的可見文字，再於下一則呼叫工具
- 純查讀回合也要報，一句話即可；不要以「還沒要修改」為由跳過
- 被 [Guardian:PreActionNotice] 提醒時，補預告一次即可，不要去改白名單或降低閘門靈敏度

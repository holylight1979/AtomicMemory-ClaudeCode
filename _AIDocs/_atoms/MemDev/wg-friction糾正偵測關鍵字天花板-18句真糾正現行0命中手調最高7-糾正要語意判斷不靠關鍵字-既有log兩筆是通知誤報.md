# wg-friction糾正偵測關鍵字天花板-18句真糾正現行0命中手調最高7-糾正要語意判斷不靠關鍵字-既有log兩筆是通知誤報

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: wg_friction, detect_correction, 糾正偵測, user_correction_count, guard-friction, 成效指標, 糾正次數, 關鍵字天花板
- Created-at: 2026-10-07
- Related: 糾正與失敗偵測把sub-agent完成通知當使用者輸入-task-notification整則進ups-引用的糾正詞誤觸deeppostmortem
- Source: session:3e106167#158b8da6 2026-10-07
- Quote: 「不是有該驗的要驗嗎?」

## 知識

- [臨] 實測：三個 session 共 18 句使用者真糾正（「不要老是要我拍版」「怎麼還可以推到結論」「白燒 token」等）丟進 `hooks/wg_friction.py:detect_correction`，現行關鍵字 0 命中；`Logs/guard-friction.jsonl` 全部 3 行中 2 行是 `<task-notification>` 通知文字誤報。手調兩組規則（否定詞加第二人稱、質問語氣）對 10 句非糾正 0 誤報，但最高只到 7/18；剩下是指令句與原則句，表面字詞跟一般指示分不開。
- [臨] 結論：「使用者糾正次數」現況不能當任何機制的成效基線；要用它得讓 LLM 每輪標「這句是不是糾正」，或換指標；改關鍵字是死路。

## 行動

- 拿糾正次數當成效數字前先看 log 行數與 excerpt 是不是通知文字
- 要修糾正偵測：設計語意標註路徑，不調關鍵字

# feedback-清理暫存先確認資料夾用途與是否還有別處副本-不進版控的本機資料刪了救不回-不整夾清空

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 清理, 清暫存, rm -rf, workflow/inbox, gitignored, 誤刪, 刪資料夾, scratchpad
- Created-at: 2026-11-05
- Source: session:d164c54c#73e15770 2026-11-05
- Quote: 「收割後，可以關session囉?」

## 知識

- [臨] 使用者要求確認是暫存無誤才刪，我卻只憑 gitignored 和資料夾名就把 workflow/inbox 整夾清空。它其實是派工信箱，也是研究報告引用的實測原始資料的唯一一份；逐字稿只重建回部分文字檔，12 輪激辯全文與實測 JSON 救不回。
- [臨] gitignored 代表本機唯一，不代表可丟。刪之前：查 TECH 與 grep 這條路徑的用途；查保留文件有沒有引用裡面的檔；用 ListAgents 與 state 檔排除還開著的 session；先列清單。誤刪後可從 ~/.claude/projects 的 jsonl 取 Write、Edit、Read 紀錄重建文字檔。

## 行動

- 刪 gitignored 資料夾前先查用途與引用，逐夾判斷，不用萬用字元整夾清空
- 保留的文件引用了要刪的檔時，先把被引用的原文一起封存

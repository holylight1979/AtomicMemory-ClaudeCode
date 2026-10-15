# need_goal-reconcile參數格式-每項要id與終點status-evidence是物件陣列kind只收receipt-case-file-atom-level只收measured-read-inferred

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: need_goal reconcile, reconcile 拒收, 目標樹結案, evidence 必須是物件, 完整對照
- Created-at: 2026-10-15
- Source: session:242d1f2a#7f55cf09 2026-10-15
- Quote: 「OK，那此session還有沒有什麼沒做、或者沒收割到的知識或經驗? 準備關了。」

## 知識

- [臨] need_goal(action=reconcile) 的 items 每項要 id（T<數字>）、status 只收 done|partial|none|dropped、evidence 是物件陣列；每個證據物件要 kind（只收 receipt|case|file|atom）、ref、level（只收 measured|read|inferred），可加 note。commit 雜湊不能當 kind，要引用就寫在 file 證據的 note 裡，或引用收據號 R<號>。

## 行動

- 結案前照這個格式一次交對，不要拿字串陣列試

# verify_scope宣告項目太多時PostToolUse逾時被砍-宣告靜默遺失-只列改檔必要的項

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: verify_scope, 驗證範圍宣告, 宣告沒存, 宣告沒回應, CASE_DECLARED_FOR_CHANGE, 還沒宣告由哪個案例驗, PostToolUse 逾時, need_goal 沒回應
- Created-at: 2026-10-16
- Source: session:11e2b170 2026-10-16
- Quote: 「開工 (階段什麼的進度 你安排好)。」

## 知識

- [臨] 現象：`need_goal(action=verify_scope)` 帶 20 項時，回 chip「已收到」但沒有 `[Guardian:VerifyScope] 收下` 那段回應，state 裡也沒有新的 S編號；之後 Stop 一直擋「還沒宣告由哪個案例驗」。同一份拆成 9 項立刻收下；15 項時也正常。PostToolUse hook timeout 是 5 秒（settings.json），推斷是逐項查收據超時被砍、宣告還沒寫進 state 就沒了，而且沒有任何訊號（逮時未實測計時）。
- [臨] 判斷是不是這個坑：送出 verify_scope 後沒看到「收下：S<號>」那段，就是沒存。檢查法：讀 workflow/state-<sid>.json 的 verify_scope[<sid>] 最後一筆的 id。
- [臨] 做法：只列「改過的程式檔要靠它驗（case_for）」與「真的會受影響」的項，只是拿掉替身的測試檔不必列進範圍；每次宣告是完整範圍，前幾段改的程式檔也要留 case_for，否則會被擋。

## 行動

- verify_scope 送出後確認有「收下：S<號>」回應；沒有就拆少項重送
- 宣告只列 case_for 與真的會受影響的項，別把所有碰過的測試都塞進去

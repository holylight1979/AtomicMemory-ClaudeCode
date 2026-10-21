# 補子行程壓窗旗標前先看它的輸出要去哪-刻意印到主控台的子行程用no-window-exempt註記-掃描規則不是真理

- Scope: global
- Author: holylight
- Source: 某工作軌 004 交付信 post-mortem（總控台代寫）
- Confidence: [臨]
- Trigger: CREATE_NO_WINDOW, 壓窗旗標, no-window-exempt, verify_no_window_spawn, subprocess.run 輸出不見, 子行程沒有主控台, 重跑仍紅
- Created-at: 2026-10-21
- Quote: 「除非像是先前我曾經說的"session派工之間必須等(衝突或先後必須..那些)"，否則就請你持續多開加速完工，須注意工人模型用Opus、Effort 也注意一下，除非"絕對必須用Fable"。」

## 知識

- [臨] 壓窗規則（每支子行程帶 CREATE_NO_WINDOW）是給 hook／排程在沒主控台時不閃窗用的；刻意要把輸出直接印到呼叫端主控台的子行程（例：抽樣指令的檢查工具）加了旗標就沒有主控台、繼承來的輸出會消失，別的案例因此紅。
- [臨] 掃描腳本本來就留了 `no-window-exempt` 註記給這種子行程：退掉旗標、那行加註記寫理由，掃描與輸出案例兩邊都綠。
- [臨] 判準：補旗標前先問這支子行程的輸出要去哪；紅了第一次就查機制，不靠重跑確認（某軌 post-mortem：重跑兩次才回頭查）。

## 行動

- 補任何子行程旗標前先看它的 stdout／stderr 去向
- verify_no_window_spawn 紅時先看那行是不是該豁免，不先改旗標

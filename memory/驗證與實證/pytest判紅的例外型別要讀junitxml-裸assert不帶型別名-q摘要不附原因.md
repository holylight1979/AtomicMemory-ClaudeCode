# pytest判紅的例外型別要讀junitxml-裸assert不帶型別名-q摘要不附原因

- Scope: global
- Author: holylight
- Source: session 45f9aa09 2026-10-13 退回紅與規則變異
- Confidence: [臨]
- Trigger: 紅在斷言, 退回紅, 紅的型別, junitxml, 規則變異, mutant
- Created-at: 2026-10-13
- Related: 反轉驗證換回舊版會同時改暫存區要restore-staged-新案走舊碼就有的入口才紅在斷言, 需求目標閘被審出三漏洞同根-判定只拿到路徑字串-命令語義在解析器就丟了-判定與設定取法各入口各寫一份
- Quote: 「<pasted_content id="c931"> 你是 v6.0 的工作 session track-b-hooks-2（接 track-b-hooks 未完：需求目標 4.3 第六關鍵點、queued_command 同伴訊息補掃、4.4 提問前用 PreToolUse 擋），總控台是 claude-aa（對人總控台 claude-91）。第一步用 EnterWorktree 切進 wor…」

## 知識

- [臨]（實跑，Windows、pytest -q 子行程）分類「紅在哪種例外」時 grep 終端輸出會漏算：裸 `assert x` 失敗印成 `E assert None`，不帶 AssertionError 字樣；`-q` 的 FAILED 摘要行不附原因；子行程輸出是 CRLF，正則 `$` 對不上。
- [臨] 可靠做法：pytest 加 `--junitxml <檔>`，逐個 testcase 讀 `failure`／`error` 元素的 message。`failure` 且 message 以 `assert` 或 `AssertionError` 開頭＝紅在斷言；`error` 元素＝測試本身出錯（fixture／import 等，不是斷言）。
- [臨] 規則變異清單照模組宣稱的規則逐條列，不只列任務點名的：變異沒紅通常是案例有跑到那一步但沒斷言它的回傳，補斷言就紅。

## 行動

- 退回紅／變異腳本用 --junitxml 判紅的型別，不 grep 終端輸出
- 變異沒紅 → 先找哪個案例跑到該步卻沒斷言，補斷言後重跑

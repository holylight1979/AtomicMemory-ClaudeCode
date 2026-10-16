# 驗證範圍要的收據用明列檔名的單一pytest前景指令-for迴圈加變數或printf前綴與背景跑都不算

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 驗證範圍收據, SCOPE_ITEM_RECEIPT_AFTER_EDIT, 無哨兵, 收據不算, 背景跑 pytest, for 迴圈跑測試, 改完要重跑
- Created-at: 2026-10-16
- Source: session:8d787d66#74485b00 2026-10-16
- Quote: 「好，那收割一下知識、技術，這session應該完工沒有代辦或以知未修BUG 可以關掉了?」

## 知識

- [臨] 驗證範圍閘認的收據要能從指令字面看出跑了哪些檔、從輸出認出 pytest 結尾行：`for f in ...; do pytest $f; done` 加 `printf "%s: "` 前綴的寫法落帳成「無哨兵」，範圍項目一項都不算；改成一個 `python -X utf8 -m pytest -q 檔1 檔2 …` 明列檔名就一次清掉多項。
- [臨] run_in_background 跑的 pytest 沒有收據（PostToolUse 只看到「已啟動」），只有 run_verify 與根 conftest 整組（tools/verify、lib/verify）自寫收據；要交範圍收據就前景跑（單次 10 分鐘內拆成幾批）。
- [臨] 範圍裡的檔案項目，任何一個程式檔再改都會讓它們的收據作廢（程式檔一律算相關）：長測試留到確定不再改程式之後再跑，中途只跑要確認方向的那支。

## 行動

- 交範圍收據：前景、單一 pytest 指令、明列檔名，不包 for 迴圈、不加印字前綴
- 改完最後一個程式檔才跑整份範圍

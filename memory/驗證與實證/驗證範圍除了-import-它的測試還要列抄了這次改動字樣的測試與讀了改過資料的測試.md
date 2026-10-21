# 驗證範圍除了 import 它的測試，還要列抄了這次改動字樣的測試與讀了改過資料的測試

- Scope: global
- Author: holylight
- Source: _AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/LLM切入點自評-2026-10-21.md E24
- Confidence: [臨]
- Trigger: 驗證範圍, verify_scope, 該測哪些, 哪些測試有關聯, 範圍漏判, SCOPE_LEAK_REVIEW, root_cause, 漏判率, case_for, no_case
- Created-at: 2026-10-21
- Quote: 「A」
- Entry: E24

## 知識

- [臨] 判範圍三問：①誰 import 或用子行程跑到改過的程式（列進項目，可寫 depends）②誰的斷言抄了這次改的訊息字樣、標籤、欄位名、格式（宣告前先 grep 測試目錄找舊字面值，命中的都列）③誰讀了改過的資料、設定、索引（寫進 inputs）。反例：把擋訊息標籤改名，只列 import 那支單元測試；另外幾支斷言標籤原文的整合測試事後紅，記成範圍漏判。
- [臨] 不為保險列整個資料夾：每項要說得出「它讀到／斷言了這次改的哪個東西」；說不出就是還沒查，先查再列。
- [臨] 漏判檢討：先看紅掉的斷言碰的是不是那次改動的東西。是 → missed，root_cause 寫可重用的盲點（例：只看 import、沒 grep 字面值），next_time 寫下次多做哪一步；看到紅的 session 自己在那之後改過相關檔 → 先查是不是自己造成的，是就 unrelated 並寫證據。
- [臨] case_for 只掛本 session 寫或改過、會因這次改動變紅變綠的案例；沒動過的舊測試已驗到 → no_case 理由寫「既有案例 X 已驗到 Y」。

## 行動

- 宣告前 grep 測試目錄裡這次改掉的舊字面值
- 每項 why 寫「它讀到／斷言了這次改的哪個東西」

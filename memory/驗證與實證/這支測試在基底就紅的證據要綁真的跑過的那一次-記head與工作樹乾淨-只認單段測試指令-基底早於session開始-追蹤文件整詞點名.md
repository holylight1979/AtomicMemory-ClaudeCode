# 這支測試在基底就紅的證據要綁真的跑過的那一次-記head與工作樹乾淨-只認單段測試指令-基底早於session開始-追蹤文件整詞點名

- Scope: global
- Author: holylight
- Source: 2026-10-23 跨層閘與寫入目標判定修補實測
- Confidence: [臨]
- Trigger: 基底就紅, 基底紅, 改動前就紅, 既有紅測, pre-existing failure, 紅測放行, 基底 commit, 追蹤文件
- Created-at: 2026-10-23
- Related: 放行或豁免要綁使用者看過的那幾件-鍵用規則加完整對象-之後又改了檔就失效

## 知識

- [臨] 「這支測試在基底就紅」的證據要綁在真的跑過的那一次：當下記 HEAD 與已追蹤檔乾不乾淨，只認單段測試指令（多段輸出會誤綁到第一段的 commit）。
- [臨] 基底 commit 要早於 session 開始：自己做的 merge、rebase 產生的 commit 不算「改動前」，否則拿自己的 merge 當基底就能冒充。
- [臨] 追蹤文件要整詞點名那支測試、且本 session 沒改過：子字串比對會讓 test_x_other 冒充 test_x。上面少任何一件都有繞法。

## 行動

- 認「基底就紅」前逐件對：這次執行的 HEAD＋乾淨、單段指令、基底早於 session、追蹤文件整詞點名且未改
- 每種繞法各寫一個會紅的案例（多段輸出、同前綴測試名、自己的 merge 當基底）

# 驗證範圍的收據要在前景直接跑那一項-指令尾只接tail不夾grep-背景跑與超過十分鐘的不算-改檔排在跑範圍之前

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 驗證範圍, verify_scope, 收據不算, SCOPE_ITEM_RECEIPT_AFTER_EDIT, 收尾被擋, 跑綠了還擋, 背景跑測試
- Created-at: 2026-10-15
- Source: session:bbc75a05#08f4ca4d 2026-10-15
- Quote: 「收割的經驗知識，是全域的、以後專案層也會產生效益的嗎?」

## 知識

- [臨] 改了程式就要用 need_goal verify_scope 宣告驗證範圍，收尾閘要範圍內每一項都有「最後一次改動之後跑綠」的收據。收據是從工具輸出落帳，所以：前景跑（背景跑在啟動當下就落帳、沒有結果）；一次工具呼叫 10 分鐘內，超過就分批；指令尾巴只接 `2>&1 | tail -3`，管線裡夾 grep 等讀檔印字的指令不算（分不出結果是誰印的）；只跑一部分（-k、節點篩選）不算整檔項目。
- [臨] 宣告後又改了程式（或和該項有關的檔），那一項的收據就作廢要重跑；把文件、筆記類的修改排在跑範圍之前，跑完就不要再動。
- [臨]（實遇）收據只被跟該項有關的改動作廢（規則 SCOPE_EDIT_RELATED_TO_ITEM）：pytest 檔、探針腳本這類項目，改 _staging 文件不會讓它們作廢；但部位量尺那種尾巴帶 `&& echo X DONE` 的指令項目，程式看不出它讀哪些檔，任何改檔（連 _staging 的計畫文件）都算，跑完範圍再改文件就要補跑那一條。量尺項目排在最後跑，或改完文件再補跑一次。
- [臨]（實遇）`for f in ...; do pytest $f; done` 加 `printf` 前綴的寫法落帳成「無哨兵」，一項都不算；一個 `python -X utf8 -m pytest -q 檔1 檔2 …` 明列檔名就能一次清掉多個檔案項。
- [臨] 一行跑完多項的寫法：`python -m pytest -q a.py b.py && <量尺>`——量尺放最後、前面只用 && 串跑程式的指令、量尺後面不接過濾，測試檔各項與量尺項都認（lib/self_receipt._after_programs）。`pytest … | tail -4 && 量尺` 不算：中間的 tail 讓 pytest 那一項判成「夾了不算執行程式的指令」；多段量尺（A && B）後面接 `| tail` 也不算（管線蓋掉最後一段 exit）。
- [臨] 部位表的文件層與記憶層量尺不再接 echo：sync_doc_counts.py／skill-index.py／sync-memory-index.py 的 --check 自己印 DOC_COUNTS_CHECK／SKILL_INDEX_CHECK／MEMORY_INDEX_CHECK PASS|FAIL。
- [臨] 改了獨立的測試案例檔（不是 conftest、同資料夾沒人 import 它）只作廢點名它的那一項（SCOPE_CASE_EDIT_ONLY_ITS_ITEM）；改產品程式碼或被 import 的案例檔（probe_release_rules、verify_stop_reconcile）照舊作廢範圍裡每一項。
- [臨] 指令開頭加 `timeout 300 python -m pytest …` 也不算收據：timeout 是包裝執行器、不在執行程式白名單，哨兵分不出是誰印的（閘小修 006 實遇：十幾張 PASS 全被判「對得上改檔 0 筆」）。要限時就用工具呼叫的 timeout 參數，指令本身直接 `python -X utf8 -m pytest -q <檔>`。
- [臨] 收尾前在 job 暫存目錄（~/.claude/jobs/<id>/tmp）用 Write 寫的查帳 .py 也算「改了程式」，完整對照會把之前所有收據判成「改完沒重跑」，verify_scope 的 depends 也救不了（閘小修 006 實遇）。最後一輪驗證之後只用 Read／Grep／`python -m json.tool` 查帳，不再寫任何 .py。

## 行動

- 收尾前跑範圍：前景、分批在 10 分鐘內、尾巴只接 tail；文件修改先做完再跑


## 演化日誌

| 日期 | 變更 | 來源 |
|------|------|------|
| 2026-10-29 | 退役移入 _distant/：驗證範圍閘已於 2026-10-29 拔除（c4314d97）；本卡以「改了程式要用 need_goal verify_scope 宣告」為前提，該動作現在會被拒收，留著會誤導；收據判定的現行規則在 TECH/release-rules.md 與 lib/self_receipt.py | memory-audit --delete |

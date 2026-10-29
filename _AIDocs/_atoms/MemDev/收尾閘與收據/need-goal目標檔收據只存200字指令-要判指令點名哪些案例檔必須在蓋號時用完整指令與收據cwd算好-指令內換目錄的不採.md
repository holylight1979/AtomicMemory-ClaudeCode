# need_goal目標檔收據只存200字指令-要判指令點名哪些案例檔必須在蓋號時用完整指令與收據cwd算好-指令內換目錄的不採

- Scope: global
- Author: holylight
- Source: workflow/v6-inbox/from-track-goal-evidence/（交付 001、codex 報告）；main 076e566c
- Confidence: [臨]
- Trigger: need_goal 收據, stamp_receipts, receipts cmd 截斷, 先紅後綠, red_then_green, CASE_RED_THEN_GREEN, case_files_in_cmd, 收據比對案例檔, root_uncertain, 指令點名案例
- Created-at: 2026-10-14
- Related: 只記錄不擋的功能也要送獨立唯讀審查-一般寫法的輸入照樣會記錯

## 知識

- [臨] 始末（track-goal-evidence，C-G3＋C-G10）：先紅後綠比對初版在 reconcile 時拿目標檔 receipts[].cmd 去比，codex 唯讀審查抓出 3 個一般寫法就記錯：①cmd 蓋號時只存前 200 字，長 pytest 指令尾端點名的案例比不到；②用 hook 的 cwd 解相對路徑，`cd sub && pytest verify_a.py` 會把根目錄的同名 verify_a.py 記成先紅後綠；③case_files_in_cmd 不認引號，`"my tests/test_a.py"` 被切成 tests/test_a.py。三個都先寫成紅案例重現再修。
- [臨] 正解：工作暫存 state 的收據（post_tool_use record_receipt）有完整 cmd（cmd_full=True）、cwd、root_uncertain；凡要「看指令點名了什麼」的判定，都在 wg_need_goal.stamp_receipts 蓋號當下用完整指令＋收據自己的 cwd 算出 cases（絕對正規化路徑）存進目標檔，root_uncertain／has_cd／沒記 cwd → 空清單；目標檔不存長指令（heredoc 指令可達數 KB）。升級前蓋的收據沒有 cases，不參與比對。
- [臨] case_files_in_cmd 是 GREEN_SAME_CASE_CLEARS 與 CASE_RED_THEN_GREEN 共用的取檔函式，已改成引號裡含空白的路徑整段算一個；改它要跑 verify_release_rules 與 verify_stop_reconcile（後者走 post_tool_use 的紅測清帳）。

## 行動

- 新判定要讀收據指令內容：先查目標檔存的是不是截短版，是就改在 stamp_receipts 蓋號時算好結果
- 相對路徑一律用收據自己的 cwd 解；指令內換目錄（root_uncertain）的收據不採
- 從指令取案例檔一律走 wg_release_rules.case_files_in_cmd，不另寫 regex

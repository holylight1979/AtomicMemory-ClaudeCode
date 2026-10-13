# 真hook子行程探針只設WG_CLAUDE_DIR隔離不了守門紀錄-GUARD_LOG_DIR固定家目錄-要再帶WG_TEST_LOGS_DIR與HOME-USERPROFILE

- Scope: global
- Author: holylight
- Source: session 08519976 track-b-hooks 2026-10-13（探針：need_goal_hook_probe.py）
- Confidence: [臨]
- Trigger: 探針, 真 hook 入口探針, dispatcher 探針, WG_CLAUDE_DIR, WG_TEST_LOGS_DIR, GUARD_LOG_DIR, 守門紀錄寫進 live, 探針污染 live, 隔離探針
- Created-at: 2026-10-13
- Related: 驗證探針的副作用與假失敗-heredoc反斜線-假session登記-dry-run留目錄-fallback索引源, hook-內呼叫外部工具的四個坑-home覆寫下claude-dir指錯-pythonw無stdio-5秒預算-探針要隔離global設定, 假家目錄測試要同時設home與userprofile-windows的pathhome看userprofile而bash看home

## 知識

- [臨] 始末（2026-10-13 實踩）：用子行程跑真 dispatcher（hooks/workflow-guardian.py）的情境探針，只用 WG_CLAUDE_DIR 把資料根指到暫存，以為全部寫入都關住了。結果 live 的 Logs/guard-need_goal.jsonl 還是多了探針 session 的紀錄。同天另一條軌的探針也寫進 live：四支 guard log，另加向量啟動器的 vector-observation-probe.log。
- [臨] 根因與設計原理：wg_core 的資料根（CLAUDE_DIR＝claude_data_dir()，吃 WG_CLAUDE_DIR）和守門紀錄目錄（GUARD_LOG_DIR＝Path.home()/.claude/Logs）是兩條獨立算法。logs_dir() 只認三種覆蓋：monkeypatch 改過的 GUARD_LOG_DIR、環境變數 WG_TEST_LOGS_DIR、pytest 內（PYTEST_CURRENT_TEST）。這樣設計是為了讓測試不污染遙測，但子行程探針不在 pytest 裡、也沒帶 WG_TEST_LOGS_DIR，就落回家目錄。tools/memory-vector-service/starter.py 直接用 Path.home()，同樣不跟資料根。
- [臨] 防再犯：子行程探針的環境變數四件一起帶，都指到探針暫存：WG_CLAUDE_DIR、WG_TEST_LOGS_DIR、USERPROFILE、HOME。宣告 PASS 前對 live 的 Logs／workflow／memory 跑 `find -newer <探針開始標記檔>`，有新寫入就當污染回報。在 worktree 隔離裡清不到 live，就把檔名＋行＋session_id 報給總控台。探針範本見本卡的 Source。
- [臨] 更正（track-a2c 001 合進 main f2e4b343 後）：`hooks/wg_core.py` 的 `_DEFAULT_LOGS_DIR` 已改成 `CLAUDE_DIR/"Logs"`，守門紀錄跟著資料根（WG_CLAUDE_DIR）走，不再固定家目錄。但測試與探針仍要帶 WG_TEST_LOGS_DIR：子行程若只設 WG_CLAUDE_DIR 而模組已在別的環境被先匯入、或拿掉 PYTEST_CURRENT_TEST，守門紀錄還是會落進 live Logs（track-b2 verify_need_goal 雙行程案實踩）。
- [臨] 另兩條同類漏網（track-b2 實踩）：①一次跑多個 hooks/verify 檔時，只要有一個模組沒設 WG_CLAUDE_DIR 就先 import wg_core，整個 pytest 行程的資料根就是 live，跑真 UPS／PostToolUse 入口的既有測試會把假 session 的檔寫進 live workflow/；新增會寫資料根的機制要比照 wg_core.logs_dir，在 pytest 裡資料根沒被測試導走時改寫系統暫存目錄。②測試中途呼叫 monkeypatch.undo() 會連 fixture 的資料根導向一起撤掉，之後的寫入落進真資料根；只撤部分替換用 pytest.MonkeyPatch.context()。
- [臨] UserPromptSubmit 會叫起 tools/memory-vector-service/starter.py，它用 Path.home() 寫 Logs/vector-observation-probe.log；真 hook 探針要把向量檢索關掉（資料根 workflow/config.json 的 vector_search.enabled=false）或 USERPROFILE／HOME 指到暫存目錄。驗法：跑前後用假 session_id 搜 live 的 Logs 與 workflow，筆數不變才算沒污染。

## 行動

- 寫子行程跑真 hook 的探針：同時帶 WG_CLAUDE_DIR、WG_TEST_LOGS_DIR、USERPROFILE、HOME，四個都指到暫存
- 探針宣告 PASS 前先用 find -newer 標記檔查 live 有沒有被寫

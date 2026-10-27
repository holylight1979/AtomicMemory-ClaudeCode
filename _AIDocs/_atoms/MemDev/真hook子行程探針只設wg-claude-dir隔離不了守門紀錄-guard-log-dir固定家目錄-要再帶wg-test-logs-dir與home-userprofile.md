# 真hook子行程探針只設WG_CLAUDE_DIR隔離不了守門紀錄-GUARD_LOG_DIR固定家目錄-要再帶WG_TEST_LOGS_DIR與HOME-USERPROFILE

- Scope: global
- Author: holylight
- Source: session 08519976 track-b-hooks 2026-10-13（探針：need_goal_hook_probe.py）；2026-10-22 chain-breaker 實測
- Confidence: [臨]
- Trigger: 探針, 真 hook 入口探針, dispatcher 探針, WG_CLAUDE_DIR, WG_TEST_LOGS_DIR, GUARD_LOG_DIR, 守門紀錄寫進 live, 探針污染 live, 隔離探針, 以 session 為鍵的帳, 跨呼叫累積, 同一回合第 2 次
- Created-at: 2026-10-13
- Related: 驗證探針的副作用與假失敗-heredoc反斜線-假session登記-dry-run留目錄-fallback索引源, hook-內呼叫外部工具的四個坑-home覆寫下claude-dir指錯-pythonw無stdio-5秒預算-探針要隔離global設定, 假家目錄測試要同時設home與userprofile-windows的pathhome看userprofile而bash看home

## 知識

- [臨] 始末（實踩）：用子行程跑真 dispatcher（hooks/workflow-guardian.py）的情境探針，只用 WG_CLAUDE_DIR 把資料根指到暫存，以為寫入都關住了，live 的 Logs/guard-need_goal.jsonl 仍多了探針 session 的紀錄；同天另一個探針也寫進 live 四支 guard log 與向量啟動器的 vector-observation-probe.log。當時守門紀錄目錄固定在家目錄，跟資料根是兩條獨立算法。
- [臨] wg_core 的守門紀錄目錄預設在資料根下（CLAUDE_DIR/Logs）；logs_dir() 另認三種覆蓋：monkeypatch 改過的 GUARD_LOG_DIR、環境變數 WG_TEST_LOGS_DIR、pytest 內（PYTEST_CURRENT_TEST），讓測試不污染遙測。子行程只設 WG_CLAUDE_DIR 仍不夠：模組若已在別的環境先被匯入、或拿掉 PYTEST_CURRENT_TEST，守門紀錄還是落進 live Logs（雙行程案實踩）。
- [臨] 防再犯：子行程探針四個環境變數一起帶、都指暫存：WG_CLAUDE_DIR、WG_TEST_LOGS_DIR、USERPROFILE、HOME。宣告 PASS 前對 live 的 Logs／workflow／memory 跑 `find -newer <探針開始標記檔>`，或跑前後用假 session_id 搜 live 筆數不變；有新寫入當污染回報，隔離環境裡清不到 live 就回報檔名＋行＋session_id。探針範本見本卡的 Source。
- [臨] UserPromptSubmit 會叫起 tools/memory-vector-service/starter.py，它直接用 Path.home() 寫 Logs/vector-observation-probe.log、不跟資料根；真 hook 探針要把向量檢索關掉（資料根 workflow/config.json 的 vector_search.enabled=false）或 USERPROFILE／HOME 指暫存。
- [臨] 另兩條同類漏網：①一次跑多個 hooks/verify 檔時，只要有一個模組沒設 WG_CLAUDE_DIR 就先 import wg_core，整個 pytest 行程的資料根就是 live，跑真 UPS／PostToolUse 入口的既有測試會把假 session 的檔寫進 live workflow/；②測試中途呼叫 monkeypatch.undo() 會連 fixture 的資料根導向一起撤掉，之後的寫入落進真資料根；只撤部分替換用 pytest.MonkeyPatch.context()。
- [臨] 根因通則：驗收只看測試綠、沒驗跑完 live 多了什麼；資料根、守門紀錄目錄、家目錄三個根各自決定，只導一個就漏。新增會寫檔的機制要比照 wg_core.logs_dir：在 pytest 裡資料根沒被測試導走時改寫系統暫存目錄。
- [臨] 新加「以 session 為鍵、跨呼叫累積」的帳時，同一次 pytest 的資料根是共用的、案例的 session id 又常一樣，前一案的觸發會讓後一案被判成同一回合第 2 次；要每案一份：拿 PYTEST_CURRENT_TEST 去掉結尾的階段字樣（(setup)／(call)／(teardown)）當命名空間，放進 wg_core.logs_dir() 的測試暫存目錄，不放模組載入時就算好的資料根。


## 行動

- 寫子行程跑真 hook 的探針：同時帶 WG_CLAUDE_DIR、WG_TEST_LOGS_DIR、USERPROFILE、HOME，四個都指到暫存
- 探針宣告 PASS 前先用 find -newer 標記檔查 live 有沒有被寫

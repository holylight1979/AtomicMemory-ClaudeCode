# 暫存路徑類放行規則上線要配測試開關-pytest-tmp下的假專案會被整批放行-探針run目錄不放系統暫存否則寫碼查核整段不跑

- Scope: global
- Author: holylight
- Source: workflow/v6-inbox/from-track-gate-rules/001-gate-rules-done.md §6b
- Confidence: [臨]
- Trigger: TEMP_COPY_NOT_PROJECT, TEMP_REPO_COMMIT_EXEMPT, WG_TEMP_RULES, 暫存目錄豁免, pytest tmp 假專案, 探針 run 目錄, 31 案翻紅, 暫存規則測試開關, probe-runs, _is_ephemeral_path, 無頭實跑受測專案位置, LOCALAPPDATA Temp 不記帳, modified_files 漏記, 同步提醒看不到改檔
- Created-at: 2026-10-13
- Quote: 「你是 v6.0 的「調度」總控台（新任，接 claude-aa；對人總控台見接續單「現任」行）。職責：派工、對帳、快照複跑、合併、推送、刪樹刪分支、與各工作 session 通訊；不改碼、不開子代理、不回答原設計者。第一步 ToolSearch 載入 SendMessage 與 ListAgents，ListAgents 看自己的名字，SendMessage claude-aa 與對人總控台各一…」

## 知識

- [臨] 實踩（track-gate-rules 045）：規則「暫存目錄下的副本不當專案、暫存 repo 的 commit 免口令」上線後，verify 用 pytest tmp_path 建的假專案全部落在系統暫存底下，整批被當暫存放行，31 個既有案翻紅。規則本身對，缺的是「測試環境怎麼關掉它」：補環境變數 WG_TEMP_RULES=off 只關暫存判定（不關「暫存收據不採信」），verify 檔頭 autouse fixture setenv；正式環境不設。
- [臨] 真 hook 入口探針的 run 目錄不能放系統暫存（%TEMP%／scratchpad）：hook 會把沙箱裡的專案改檔當暫存檔豁免，寫碼查核整段不跑、探針假綠。改放 `<worktree>-probe-runs/`（與受測樹同層、不在暫存），跑完刪。
- [臨] 暫存判定要判 commit 實際落的 repo 根（find_vcs_root），不是執行目錄：正式 repo 底下的 scratchpad 子目錄不得拿到豁免；_TEMP_TOKENS 只認 /pytest-of-、/temp/claude/、/.pytest_cache/，不認裸 /scratchpad/。暫存根與目標兩側都先做 8.3 長路徑展開再比（這台 TEMP 就是 HOLYLI~1）。
- [臨]（track-b-hooks 合 gate-rules 後）別軌的測試檔沒設 `WG_TEMP_RULES=off`，合進來才紅：on_read／on_edit 跳過暫存路徑、導讀卡不注入、定位不擋。合 main 後自己的讀檔／注入案紅了，先用 `WG_TEMP_RULES=off` 單跑那案確認，再在該檔 fixture 加 setenv。
- [臨] 調度端教訓：這類「看路徑／環境就改判定」的全域規則合前只跑該軌目標清單抄不到影響面（合進 main 後別軌才發現 29 案紅，分兩批清）。合前先 grep 所有會被規則掃到的同型測試（寫 overview-map、走 hook 注入、用 tmp_path 建假專案的 verify）全跑一遍；合後發現紅不 revert，歸軌往前修，其他軌的合入排在修完之後（紅 main 上分不清新舊紅）。
- [臨] 無頭實跑的受測專案也不能放系統暫存：TEMP_COPY_NOT_PROJECT 把暫存底下的專案當副本，定位閘不擋、不注入；`_shared._is_ephemeral_path` 把 %LOCALAPPDATA%\Temp 底下的寫入當暫存檔不記帳，收尾閘看不到改檔。受測專案放 C:\w4\<名>；刪時 git 物件檔是唯讀，rmtree 要先清唯讀再刪。
- [臨] `_shared._is_ephemeral_path` 是用 tempfile.gettempdir() 判的：暫存目錄底下的寫入一律不記進 modified_files，同步提醒、寫碼查核都看不到改檔；實測第一跑就因此白跑。
- [臨] 並行改檔案例的沙箱不能放在 pytest 的 tmp_path：路徑含 `/pytest-of-`，`_is_ephemeral_path` 會把改檔當暫存檔、一筆都不記，案例看起來像紀錄全掉。沙箱改用 `tempfile.mkdtemp`，子行程的 TEMP 指到沙箱外，再設 `WG_TEMP_RULES=off`。

## 行動

- 加任何「路徑在暫存就放行」的規則：同一筆加測試開關＋fixture，先跑既有 verify 看翻紅數
- 寫真 hook 探針：run 目錄放受測樹旁，不放 %TEMP%／scratchpad；宣告 PASS 前確認寫碼查核真的跑過

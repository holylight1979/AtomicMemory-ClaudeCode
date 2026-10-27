
## 2026-10-23-CCon-R1（eea8391f-f8f5-4b24-80fb-1befb780d1c1.jsonl）
- 當時版重播對 transcript：27/27 筆逐字相同（注入段＋改檔擋不擋與擋訊息本文）
- 砍前（004 帳）：第一回合 22 次呼叫、輸入 1,485,029；沒樹被擋 0 次；缺定位被擋 8 次（第一次在第 3 次呼叫、行 83）；定位閘擋過後到改成功前多 4 次呼叫（第 3～6 次）；OverviewHub a1 231,157、a2 45,006、擋訊息被重讀 b 31,281
- main 版同一批輸入：改檔擋 8 次（當時版 8 次）；第一次擋的缺件：- 還沒交出定位行（注入導讀卡後讀了 13 個檔、跨 5 個目錄）。寫在回覆文字，或一條不寫檔的 Bash／PowerShell 指令（例如
- 分支版：判定與擋訊息同 main（是）；提示 2 則：
  - 行 57（進第 2 次呼叫的輸入，約 254 tok）：[Guardian:OverviewHub] 改【銷售報表】的程式檔前交定位四行：定位｜部位、定位｜根因層（候選 A …；候選 B …；選 A 因為 …，只找到一個就寫「第二個不存在因為 …」）、定位｜前例、定位｜批判（先下「合理／不合理，因為 …」再寫更好的做法與同類在哪）；寫在比改檔早一則的回覆文字，或一條不寫檔的 Bash／PowerShell 指令（例如 `git diff`）開頭的 `#` 註解（thinking 讀不到），宣告完照常用 Edit／Write 改，不要改用 Bash／PowerShell 寫檔。
  - 行 57（進第 2 次呼叫的輸入，約 38 tok）：[Guardian:OverviewHub] 改【測試】的程式檔前交定位四行（格式同前一則提示）。
- 反事實（推論：AI 照提示做）：被擋那批前一則回覆交四行（463 tok，AI 自己後來交的那組），改檔換成行 146 起成功的那批 4 筆 → 分支版擋 0 次、main 版擋 0 次
- 量差（推論）：去掉第 3～6 次呼叫（輸入 231,157）、之後每次少讀 D=9,684；加回提示與四行被重讀 11,604；第一回合 1,485,029 → 1,120,216，省 364,813；秒（模型／含工具與 hook）44.3／49.4
  四行：定位｜部位：銷售報表——periods.py 新增 taipei_month_of、report.py 新增 product_totals、lines.py 新增 product_lines、cli.py 新增 by-product 分支；monthly 相關三個函式行為不改
定位｜根因層：候選 A 邏輯層 periods.month_of 轉 UTC 才取月份（sales/periods.py:7）；候選 B 資料讀入層 store.load／CSV 的 ts 本身錯；選 A 因為 CSV 每筆都帶 +08:00、store.load 原樣傳遞、fromisoformat 保留時區，B 的輸入是對的，不修 A 則錯誤月份會繼續流到每個用 month_of 的報表
定位｜前例：無
定位｜批判：不合理，因為 month_of 違反 README 台北時間規則（10/01 凌晨兩筆被算進 9 月），但直接改它會動到財務的 monthly 數字，更好的做法是 by-product 走新的 taipei_month_of、month_of 保持現狀並在 docstring 標明，monthly 修正交使用者與財務拍板；同類還可能在哪：report.monthly_totals（grep 確認 month_of 只有這一個呼叫點）

## 2026-10-23-CCon-R2（2eee21a0-5e96-4f4a-8801-b9313232a174.jsonl）
- 當時版重播對 transcript：28/28 筆逐字相同（注入段＋改檔擋不擋與擋訊息本文）
- 砍前（004 帳）：第一回合 24 次呼叫、輸入 1,663,606；沒樹被擋 0 次；缺定位被擋 7 次（第一次在第 4 次呼叫、行 88）；定位閘擋過後到改成功前多 4 次呼叫（第 4～7 次）；OverviewHub a1 240,841、a2 65,299、擋訊息被重讀 b 40,051
- main 版同一批輸入：改檔擋 5 次（當時版 7 次）；第一次擋的缺件：- 還沒交出定位行（注入導讀卡後讀了 14 個檔、跨 5 個目錄）。寫在回覆文字，或一條不寫檔的 Bash／PowerShell 指令（例如
- 分支版：判定與擋訊息同 main（是）；提示 2 則：
  - 行 35（進第 1 次呼叫的輸入，約 283 tok）：[Guardian:OverviewHub] 改【銷售報表】的程式檔前先用 need_goal(action=set, goal=…) 立需求目標樹，再交定位四行：定位｜部位、定位｜根因層（候選 A …；候選 B …；選 A 因為 …，只找到一個就寫「第二個不存在因為 …」）、定位｜前例、定位｜批判（先下「合理／不合理，因為 …」再寫更好的做法與同類在哪）；寫在比改檔早一則的回覆文字，或一條不寫檔的 Bash／PowerShell 指令（例如 `git diff`）開頭的 `#` 註解（thinking 讀不到），宣告完照常用 Edit／Write 改，不要改用 Bash／PowerShell 寫檔。
  - 行 48（進第 2 次呼叫的輸入，約 68 tok）：[Guardian:OverviewHub] 改【測試】的程式檔前先用 need_goal(action=set, goal=…) 立需求目標樹，再交定位四行（格式同前一則提示）。
- 反事實（推論：AI 照提示做）：被擋那批前一則回覆交四行（956 tok，AI 自己後來交的那組），改檔換成行 161 起成功的那批 6 筆 → 分支版擋 0 次、main 版擋 0 次
- 量差（推論）：去掉第 4～7 次呼叫（輸入 240,841）、之後每次少讀 D=13,950；加回提示與四行被重讀 21,901；第一回合 1,663,606 → 1,221,466，省 442,140；秒（模型／含工具與 hook）58.1／63.6
  四行：定位｜部位：銷售報表——sales/periods.py 新增 taipei_month_of、report.py 新增 product_totals、lines.py 新增 product_lines、cli.py 新增 by-product 分支；monthly 的既有函式一行不改
定位｜根因層：候選 A 邏輯層 periods.month_of 轉 UTC 才切月，台北 10/01 00:00-07:59 的單被算進 9 月，違反 README「一律台北時間」；候選 B 資料讀入層 store.load/sales.csv，實查時間都帶 +08:00、欄位齊全，讀入沒壞；選 A 因為月份是在 A 算錯，修 B 之後 A 照樣把 10/01 早上兩筆塞進 9 月。修 A 會改到財務在用的 monthly，故本次 A 不動，by-product 另走台北時間的 taipei_month_of
定位｜前例：無
定位｜批判：不合理，因為 month_of 註明是「報表的月份歸屬」卻用 UTC 切月，和權威規則相反，monthly 9 月多算、10 月少算台北時間 10/01 早上的單（各 315 元：9 月現 520 應為 205，10 月現 420 應為 735），更好的做法是 month_of 改用台北時間並收掉 taipei_month_of，但要財務先點頭；同類還可能在哪：report.monthly_totals 是 month_of 唯一呼叫點，legacy/ 已停用、沒用到它
定位｜部位：測試——tests/test_report.py 新增 product_totals 跨月邊界案例、tests/test_cli.py 新增 by-product 輸出與參數錯誤案例；既有 test_monthly_cli_output 原封不動，當 monthly 沒被改的回歸證據
定位｜根因層：候選 A 新函式切月用錯時區（沿用 UTC 的 month_of）；候選 B 測試資料沒落在 10/01 凌晨，抓不到時區錯；選 A 為主要防線因為那是會出錯的程式，B 一併防：案例放台北 10/01 02:15 與 09/30 23:30、11/01 00:00 三筆跨月邊界，整個 dict 精確比對，納入與排除都驗到，不會因「什麼都沒發生」而過
定位｜前例：無
定位｜批判：合理，因為既有 monthly 測試精確比對整段輸出，正是財務格式的回歸防線，不該隨本次改；同類還可能在哪：無，因為專案只有 test_cli 與 test_report 兩支測試
LOCATE_HINT_REPLAY DONE r1_saved=36.48 r2_saved=44.21 blocks_before=15 blocks_after=0 calls_saved=8 secs=51.2
LOCATE_HINT_REPLAY_CHECK PASS

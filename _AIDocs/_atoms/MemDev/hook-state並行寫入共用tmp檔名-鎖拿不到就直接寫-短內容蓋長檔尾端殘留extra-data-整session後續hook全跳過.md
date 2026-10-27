# hook-state並行寫入共用tmp檔名-鎖拿不到就直接寫-短內容蓋長檔尾端殘留Extra-data-整session後續hook全跳過

- Scope: global
- Author: holylight
- Source: session ccffc32e 2026-10-12；Logs/atom-debug-2026-10-12_10.log；hooks/wg_core.py（state 讀寫段）；2026-10-23 state 讀改寫握鎖修補實測
- Quote: 「<cross-session-message from="uds:\\.\pipe\LOCAL\cc-msg-0fe62aba882b7ac6d551d144aaddb651" from-name="claude-93" from-mode="bypass"> 補一筆證據給你省一趟：我這邊有一份舊全量輸出 C:\Users\HOLYLI~1\AppData\Local\Temp\claude\c…」
- Confidence: [臨]
- Trigger: state:unreadable, state 檔存在但讀不到, Extra data, write_state, state-<sid>.json 壞, hook 跳過, part_files_read 歸零, 導讀卡沒讀過, 鎖住或 JSON 壞, 並行工具呼叫 hook 競寫, LK_NBLCK, repair_state, state:lock-timeout, state:pending-written
- Created-at: 2026-10-12
- Depends: path:C:/Users/holylight/.claude/hooks/wg_core.py
- Related: 活躍session的state被fallback覆蓋-讀失敗不等於遺失且working-ttl-30分太短-多sub-agent共用session-id時必撞, 平行hook讀改寫session-state要整段握鎖-寫時重讀再合併只當拿不到鎖的退路-鎖內只有50到80ms

## 知識

- [臨] 現象（根層 session ccffc32e）：同一則訊息並行 4 個 Write＋3 個 SendMessage 後，`workflow/state-<sid>.json` 從 10:13:57 起不再更新，`Logs/atom-debug-*.log` 連續 45 筆 `[state:unreadable] state 檔存在但讀不到（鎖住或 JSON 壞），本次 hook 跳過、不建 fallback 覆蓋`；表面症狀是部位閘一直說「還沒看過導讀卡／同頂層目錄讀了 0 個檔」、verify_receipts 不再累積。`python -m json.tool` 報 `Extra data: line 6970`——合法 JSON 後面多 119 字元舊內容尾巴。
- [臨] 成因：多支 hook 行程共用同一個 tmp 檔名、鎖拿不到還照寫時，兩支同時 `open(tmp,'w')`，先寫的長內容被後寫的短內容從開頭覆蓋、尾端殘留，replace 後整檔壞。read_state_status 正確地不建 fallback，代價是該 session 之後每支 hook 都跳過。
- [臨] 自救：把 state 檔用 `json.JSONDecoder().raw_decode` 取第一個完整物件寫回、原檔備份 `.corrupt-<ts>`，hook 立刻恢復；要用時照這個做法現寫。
- [臨] 現況（規則 STATE_RMW_LOCKED）：tmp 檔名每行程唯一＋os.replace 換檔，state 檔永遠是完整 JSON；讀→改→寫整段在 session 鎖（state-<sid>.lock）裡。等鎖最多到 hook 上限的一半，等不到不無鎖寫、不整份覆蓋，改留待併帳（stderr `[state:lock-timeout]`、`[state:pending-written]`），換檔失敗也留帳，下一支拿到鎖的行程併回（`[state:pending-merged]`）；殘留 tmp 浮 `[state:tmp-left]`。並發案在 hooks/verify/verify_state_write_concurrency.py、verify_state_parallel_rmw.py。
- [臨] 讀改寫沒排隊的另一個症狀：同一 session 平行多個子代理時 hook 互相覆寫 state，old_test_added 被蓋掉，剛加的測試被改舊測試閘當舊測試擋；根因是 state 競寫，不是閘誤判。

## 行動

- 看到部位閘連續 deny「沒讀過卡／讀檔 0 個」而自己明明讀過 → 先 grep Logs/atom-debug-*.log 的 [state:unreadable]，再 json.tool 驗 state 檔
- state 壞了用 raw_decode 取前段修回，不要刪檔重建（會丟整 session 歷史）
- 改 write_state 時先寫並發案再改碼（兩個子行程同時寫同一 sid）

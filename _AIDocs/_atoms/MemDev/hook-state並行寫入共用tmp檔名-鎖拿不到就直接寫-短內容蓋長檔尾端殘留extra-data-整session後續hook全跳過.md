# hook-state並行寫入共用tmp檔名-鎖拿不到就直接寫-短內容蓋長檔尾端殘留Extra-data-整session後續hook全跳過

- Scope: global
- Author: holylight
- Source: session ccffc32e 2026-10-12；Logs/atom-debug-2026-10-12_10.log；hooks/wg_core.py:959-1004
- Quote: 「<cross-session-message from="uds:\\.\pipe\LOCAL\cc-msg-0fe62aba882b7ac6d551d144aaddb651" from-name="claude-93" from-mode="bypass"> 補一筆證據給你省一趟：我這邊有一份舊全量輸出 C:\Users\HOLYLI~1\AppData\Local\Temp\claude\c…」
- Confidence: [臨]
- Trigger: state:unreadable, state 檔存在但讀不到, Extra data, write_state, state-<sid>.json 壞, hook 跳過, part_files_read 歸零, 導讀卡沒讀過, 鎖住或 JSON 壞, 並行工具呼叫 hook 競寫, LK_NBLCK, repair_state
- Created-at: 2026-10-12
- Depends: path:C:/Users/holylight/.claude/hooks/wg_core.py
- Related: 活躍session的state被fallback覆蓋-讀失敗不等於遺失且working-ttl-30分太短-多sub-agent共用session-id時必撞

## 知識

- [臨] 現象（根層 session ccffc32e）：同一則訊息並行 4 個 Write＋3 個 SendMessage 後，`workflow/state-<sid>.json` 從 10:13:57 起不再更新，`Logs/atom-debug-*.log` 連續 45 筆 `[state:unreadable] state 檔存在但讀不到（鎖住或 JSON 壞），本次 hook 跳過、不建 fallback 覆蓋`；表面症狀是部位閘一直說「還沒看過導讀卡／同頂層目錄讀了 0 個檔」、verify_receipts 不再累積。`python -m json.tool` 報 `Extra data: line 6970`——合法 JSON 後面多 119 字元舊內容尾巴。
- [臨] 根因在 `hooks/wg_core.py:write_state`：所有 hook 行程共用同一個 `state-<sid>.tmp`；Windows 鎖用 `msvcrt.locking(LK_NBLCK)`，拿不到只 `except OSError` 把 lock_fh 設 None 然後**照樣往下寫**。兩支 hook 同時 `open(tmp,'w')`，先寫的長內容被後寫的短內容從 offset 0 覆蓋、尾端殘留，`replace` 後整檔壞。read_state_status 正確地不建 fallback，但代價是該 session 餘生每支 hook 都跳過。
- [臨] 自救：把 state 檔用 `json.JSONDecoder().raw_decode` 取第一個完整物件寫回、原檔備份 `.corrupt-<ts>`（scratchpad 範本 repair_state.py），hook 立刻恢復。修法（待派工）：tmp 檔名帶 pid（`path.with_suffix(f'.{os.getpid()}.tmp')`）；鎖拿不到短暫重試幾次再寫；verify 加兩行程併發 write_state 後檔仍是合法 JSON 的案。
- [臨] 已修（v6/track-b2，merge 268a12d）：`write_state` tmp 檔名帶 pid、鎖拿不到重試 10×20ms 才無鎖寫（stderr `[state:lock-timeout]`）、replace 失敗重試並不動原檔（`[state:replace-failed]`）、unlink 失敗浮 `[state:tmp-left]`；併發反例案 `hooks/verify/verify_state_write_concurrency.py` 在舊條件下確定性重現 Extra data。殺檔自救的一次性腳本已隨派工信箱清理刪除，要用時照上一條 raw_decode 做法重寫。

## 行動

- 看到部位閘連續 deny「沒讀過卡／讀檔 0 個」而自己明明讀過 → 先 grep Logs/atom-debug-*.log 的 [state:unreadable]，再 json.tool 驗 state 檔
- state 壞了用 raw_decode 取前段修回，不要刪檔重建（會丟整 session 歷史）
- 改 write_state 時先寫併發案再改碼（兩個子行程同時寫同一 sid）

# 平行hook讀改寫session-state要整段握鎖-寫時重讀再合併只當拿不到鎖的退路-鎖內只有50到80ms

- Scope: global
- Author: holylight
- Source: 2026-10-23 state 讀改寫握鎖修補實測；2026-10-23 MCP 與寫卡工具修補實測
- Confidence: [臨]
- Trigger: STATE_RMW_LOCKED, 整段握鎖, 平行 hook 讀改寫, state 鎖, begin_state_rmw, end_state_rmw, 鎖內時間, 寫時重讀再合併, state 互相覆蓋, probe_state_parallel_perf
- Created-at: 2026-10-22
- Related: hook-state跨行程三方合併要依欄位業務語意分型-通用合併會破壞去重鍵-事件序號-分回合版本, hook-state並行寫入共用tmp檔名-鎖拿不到就直接寫-短內容蓋長檔尾端殘留extra-data-整session後續hook全跳過, windows-每支-hook-子程序啟動約-150ms-同事件多支-standalone-hook-先量再併-過-100ms-且等價回放全過才合

## 知識

- [臨] 平行工具呼叫的多支 hook 讀改寫同一份 session state：整段握鎖（第一次讀 state 就拿這個 session 的鎖、握到 handler 結束）比「寫的時候重讀磁碟再合併」可靠；合併只當拿不到鎖時的退路。
- [臨] 握鎖的代價小：一支 hook 從讀 state 到寫回只要 50～80ms，行程啟動（約 150ms）和載入 handler（約 90ms）都在鎖外；平行 10 支整段握鎖最慢 1.15 秒，上限 5 秒。
- [臨] 合併的語意陷阱很多：審查四輪抓到的 12 個阻擋問題全在退路（待併帳、三方合併），主路徑一個都沒有。
- [臨] hook 以外的 state 寫者（萃取 worker、MCP 伺服器）一律走 `lib/state_rmw.update_state_locked`，不自己整份覆蓋。
- [臨] Node 沒有 Python msvcrt 那種位元組鎖，Node 端只能 spawn `python -m lib.state_rmw`、只送要改的鍵。
- [臨] 寫入結果分 written（寫進 state）／pending（拿不到鎖、留了待併帳）／unchanged（沒變）／missing（state 不在或讀壞）／failed（state 與待併帳都沒寫成）；failed 不能回成功。
- [臨] 已在 hook 模式（外層已握鎖）的行程呼叫時不能 end_state_rmw，否則會放掉外層握著的鎖。

## 行動

- 多個行程共寫同一份狀態檔：先讓讀→改→寫整段排隊並量鎖內時間，合併只做拿不到鎖時的退路
- 退路的交錯案例要寫得比主路徑多

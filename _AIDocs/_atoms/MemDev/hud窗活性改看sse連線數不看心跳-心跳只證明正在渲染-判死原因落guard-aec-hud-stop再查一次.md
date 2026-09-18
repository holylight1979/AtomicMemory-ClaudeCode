# hud窗活性改看sse連線數不看心跳-心跳只證明正在渲染-判死原因落guard-aec_hud-stop再查一次

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: HUD 不可達, HUD 心跳逾時, beat-status, clients, /api/aec/stream, EventSource, SSE, _hud_alive, aec_hud_fallback, guard-aec_hud, hud_stale_s, 窗活性
- Created-at: 2026-09-18
- Related: hud心跳被chromium隱藏頁節流成每分鐘一次-心跳改跑web-worker-編server.js前先顧relinquish的mtime契約, 在使用者活躍桌面彈視窗做gui實驗會被順手關掉污染數據-改headless-edge加cdp或先查前景視窗

## 知識

- [臨] Web Worker 版心跳上線後專案 session 仍每次 notable 都判「HUD 心跳逾時」。三假說實測全排除：beat-status 取樣 8–33ms 零逾時（tool handler 跑在各 session 自己的 MCP 行程，不會占住 port 持有者）；3848 只有一個 listener；config 實讀 hud_stale_s=75。真因：心跳只證明「頁面正在渲染」，視窗被遮住久了瀏覽器讓頁面休眠、心跳全停（現場 age 上百秒、窗仍開；使用者切過去看 age 就歸 2），hook 只看心跳且 except 吞掉原因。
- [臨] 現制：HUD 頁開 EventSource 到 /api/aec/stream，Node hudClients 計數（15s ping 剔死連線），beat-status 回 {age_s, clients}；Python handlers/_shared._hud_alive：clients≥1 即活（raw socket 4 分鐘、Edge 最小化 3 分鐘、CDP frozen 三種實測連線都在，視窗關了幾秒內歸 0），無連線才看 age<hud_stale_s（舊 Node 退路）；判死 info 落 Logs/guard-aec_hud.jsonl；Stop 消費 aec_hud_fallback 前再查一次。生效：hook 即時；Node 端要專案 session 重啟 MCP（或下個新 session 開機讓舊持有者退位）+ HUD 頁 F5。驗：verify_aec_hud_beat_liveness.py。

## 行動

- Stop 印「HUD 不可達（原因）」先看 guard-aec_hud.jsonl 的 clients/age/reason：無 clients 欄＝Node 舊碼未重啟
- 別再拿心跳當「窗開著」的證據；連線數才是

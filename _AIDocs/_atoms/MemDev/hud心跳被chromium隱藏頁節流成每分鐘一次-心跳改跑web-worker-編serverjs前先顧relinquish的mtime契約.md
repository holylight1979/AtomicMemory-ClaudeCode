# hud心跳被chromium隱藏頁節流成每分鐘一次-心跳改跑web-worker-編server.js前先顧relinquish的mtime契約

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: HUD 未開, HUD 心跳, beat-status, hud_stale_s, aec_hud_fallback, setInterval 節流, intensive throttling, Web Worker, relinquish, SELF_MTIME_AT_BOOT, server.js mtime, 港口持有者, 連鎖退位
- Created-at: 2026-09-10
- Related: codex裁判停用個別mcp用-c-mcp_servers名.enabled=false-mcp_servers空表是合併不是清空, 原子記憶審查總結-好機制被小故障卡死非過重-拔前先實證

## 知識

- [臨] 「HUD 視窗未開啟」誤報根因：Edge --app 視窗被 VS Code 遮住≥ 5 分鐘後，Chromium intensive wake-up throttling 把主執行緒 setInterval 對齊成每分鐘一次；實測 beat-status age_s 每 60 秒才歸零，門檻 30 秒 → 一半時間判窗死（97 個 transcript 都中過）。不是時間差、不是 port 接手。
- [臨] 修法：心跳改跑在 Blob Web Worker（Worker 計時器不受頁面隱藏節流；Chrome 88 公告只講 DOM setTimeout/setInterval），建不出 Worker 才退回主執行緒。Playwright 實測每 10s 一次。隱藏頁的真正長遡作法是 SSE/WebSocket 長連線由伺服器判存活，但需改 server.js 路由。
- [臨] ⚠ server.js 的 reclaimStaleOrphan 用「檔案當下 mtime > 持有者開機 mtime」要求退位自殺；多 session 執行中編輯 server.js（或 touch 成較新 mtime）→ 每個舊行程都會要求持有者退位，連鎖殺到剩一個，受害 session 的 MCP 工具全掉。本次誤用 touch -r 到較新檔，20 秒內殺掉 3 個 guardian。已加 guard：只有自己開機 mtime == 檔案當下 mtime 的行程才可要求退位；但舊行程沒這道 guard。
- [臨] 規則：有 guardian session 在跑時改 server.js，存檔後立刻 `touch -d '<原 mtime 到小數>'` 還原（先 stat -c %y 記下）；新碼只在持有者退場後由新 session 接手才上線。HUD 頁面也要 F5 才吃到新 JS。驗法：`netstat -ano | grep 3848` 看持有者 pid 有無變。
- [臨] Codex 審查補強（已採）：頁面被 Chromium 凍結（Page Lifecycle freeze、Edge sleeping tabs）時 Dedicated Worker 一起凍 → 沒心跳 → fallback 回 chat，這是對的（使用者真看不到）。最終設計：Worker 只管輪詢計時與 fetch reports，主執行緒收到 onmessage 才渲染並回一拍 /api/aec/beat（每 10s 至多一拍），心跳語意從「頁面還在」變成「報告已畫上去」；事件驅動的 fetch 不受計時器節流。
- [臨] server.js 程式版本改為 server.js + lib/*.js 的最新 mtime（codeMtime），改 lib（HUD 頁）也算新碼：舊行程只看 server.js mtime（已還原）故不會連鎖；下一個新 session 的 guardian 開機版本 > 舊持有者 → 要求退位接手，新 HUD 碼自動上線（頁面仍需 F5）。

## 行動

- Stop 印「HUD 心跳逾時」先 curl beat-status 取樣 70 秒：週期 60s = 舊頁面被節流，F5 HUD；周期 10s 仍逾時 = 頁面真被凍結/視窗真沒開
- 改 server.js 前 stat 記 mtime，存檔後 touch -d 還原；絕不 touch -r 到別的檔

# Guardian Dashboard 孤兒佔埠與新碼重啟

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: guardian, server.js, 3848, dashboard, 重啟, 孤兒, EADDRINUSE, 新路由 404, creature-chat, world.html
- Created-at: 2026-06-02
- Related: decisions-architecture, feedback-tooling-reliability, toolchain, reconcile-render-動畫狀態歸屬陷阱, 腦內世界-v3-自癒與-command-bus-架構, 腦內世界-環境演化-放置式架構

## 知識

- [臨] 機制：guardian server.js 的 dashboard httpServer 綁 127.0.0.1:3848，但**舊 session 的 server.js 程序不隨 session / VS Code 關閉退出**，會變孤兒持續霸佔 3848 並服務**舊碼**。新 session 的實例 bind 撞 EADDRINUSE 後只進 15s heartbeat 待命（server.js:3883-3921），佔埠者死掉才由某存活實例重綁。
- [臨] 後果：**開新 session / 重開 VS Code 都不會讓改過的 server.js 上線** —— live :3848 仍是孤兒舊碼。症狀：POST /api/<新路由> 回 404，但 server.js 檔內路由明明存在。交接常見錯誤心智模型「開新 session = guardian 重啟」就是栽在這。
- [臨] 修復步驟：(1) `Get-CimInstance Win32_Process -Filter "Name='node.exe'" | Where-Object { $_.CommandLine -like '*workflow-guardian-mcp*server.js*' } | Select ProcessId,CreationDate` 列**全部**實例（勿用 wmic|grep，配對會錯致誤殺，見 [[feedback-tooling-reliability]]）；(2) 取 server.js mtime，CreationDate 早於 mtime = 舊碼；(3) Stop-Process 殺光所有舊碼孤兒（含佔埠者），**保留**啟動晚於 mtime 的本 session 實例（用 /api/sessions 的 started_at 交叉比對 PID）；(4) 存活實例 ≤15s heartbeat 自動重綁 3848。
- [臨] 驗證：POST /api/<route> 回**非-404**（400 = route 存在僅 payload 無效，即成功）+ `(Get-NetTCPConnection -LocalPort 3848 -State Listen).OwningProcess` == 保留的新實例 PID。
- [臨] 例外：純前端改（world.html 等 dashboard 靜態檔）**不需殺程序** —— httpServer 每次 GET 重讀檔案，瀏覽器 Ctrl+F5 即生效。只有改 server.js 本身才要走上面重啟流程。

## 行動

- 改 server.js 後要讓 live :3848 生效 → 殺佔埠的舊碼孤兒，別靠重開 session / VS Code
- 判舊/新碼：CreationDate vs server.js mtime + /api/sessions started_at；列程序一律 Get-CimInstance，不用 wmic|grep
- 純改 world.html / dashboard 靜態檔 → 直接 Ctrl+F5，免動程序

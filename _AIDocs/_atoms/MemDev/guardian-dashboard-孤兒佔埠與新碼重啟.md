# Guardian Dashboard 孤兒佔埠與新碼重啟

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: guardian, server.js, 3848, dashboard, 重啟, 孤兒, EADDRINUSE, 新路由 404, creature-chat, world.html
- Created-at: 2026-06-02
- Related: decisions-architecture, feedback-tooling-reliability, toolchain, reconcile-render-動畫狀態歸屬陷阱, 腦內世界-v3-自癒與-command-bus-架構, 腦內世界-環境演化-放置式架構, dashboard-apiatoms-專案-shared-範疇被-frontmatter-scope-覆寫誤歸核心房

## 知識

- [臨] 機制：guardian server.js 的 dashboard httpServer 綁 127.0.0.1:3848，但**舊 session 的 server.js 程序不隨 session / VS Code 關閉退出**，會變孤兒持續霸佔 3848 並服務**舊碼**。新 session 的實例 bind 撞 EADDRINUSE 後只進 15s heartbeat 待命（server.js:3883-3921），佔埠者死掉才由某存活實例重綁。
- [臨] 後果：**開新 session / 重開 VS Code 都不會讓改過的 server.js 上線** —— live :3848 仍是孤兒舊碼。症狀：POST /api/<新路由> 回 404，但 server.js 檔內路由明明存在。交接常見錯誤心智模型「開新 session = guardian 重啟」就是栽在這。
- [臨] 修復步驟：(1) `Get-CimInstance Win32_Process -Filter "Name='node.exe'" | Where-Object { $_.CommandLine -like '*workflow-guardian-mcp*server.js*' } | Select ProcessId,CreationDate` 列**全部**實例（勿用 wmic|grep，配對會錯致誤殺，見 [[feedback-tooling-reliability]]）；(2) 取 server.js mtime，CreationDate 早於 mtime = 舊碼；(3) Stop-Process 殺光所有舊碼孤兒（含佔埠者），**保留**啟動晚於 mtime 的本 session 實例（用 /api/sessions 的 started_at 交叉比對 PID）；(4) 存活實例 ≤15s heartbeat 自動重綁 3848。
- [臨] 驗證：POST /api/<route> 回**非-404**（400 = route 存在僅 payload 無效，即成功）+ `(Get-NetTCPConnection -LocalPort 3848 -State Listen).OwningProcess` == 保留的新實例 PID。
- [臨] 例外：純前端改（world.html 等 dashboard 靜態檔）**不需殺程序** —— httpServer 每次 GET 重讀檔案，瀏覽器 Ctrl+F5 即生效。只有改 server.js 本身才要走上面重啟流程。
- [臨] 自癒落地（現況機制，純 Node HTTP 協作式交棒）：新碼 server.js 的 `tryBindDashboard` 探到 :3848 被佔時呼 `reclaimStaleOrphan()` → `POST /api/relinquish{requesterMtime,requesterFile}`。佔埠者（holder）收到後只在「同 server.js 檔 ∧ 對方 mtime > 自己 boot 時 mtime（＝我是舊碼）」時 ACK `relinquishing:true` 並 `process.exit(0)` **自我退出**，請求方等 socket 釋放後 rebind；peer 跑當前碼 → `relinquishing:false`、非 guardian 程序無此路由（404/連不上）→ 一律讓步（heartbeat 續等）。**「只殺自己人」由構造保證**：從不殺別進程（無 `process.kill`、無外部 shell），舊碼 holder 自己退，且只有我方碼才有 relinquish 合約 → 外部程序零影響。判「舊碼」＝ holder 的 boot-time mtime（`SELF_MTIME_AT_BOOT`，開機時 `fs.statSync(__filename).mtimeMs`）< 請求方當前檔 mtime；改碼後 mtime 變大，新實例即為「較新」。輔助：`GET /api/whoami` 回 `{pid,file,mtime}`（判定 + 驗證新碼是否上線）、`WG_DASHBOARD_PORT` env override（隔離測試多實例）、`require.main === module` 守門（bare `require()` 匯入 buildAtomContent 不綁埠/不交棒）。**踩雷教訓**：初版用 JS `execFile powershell`（Get-CimInstance 查、Stop-Process 殺）→ detached 情境 `spawn EPERM` 崩、且 node→powershell→殺進程被卡巴斯基當惡意行為封鎖 → 改純 http 協作、自我退出、跨平台、零 spawn。故上面第一條「bind 撞 EADDRINUSE 只進 heartbeat 待命」現僅是「持有者非自己人舊碼」的讓步分支。

## 行動

- 改 server.js 後要讓 live :3848 生效 → 殺佔埠的舊碼孤兒，別靠重開 session / VS Code
- 判舊/新碼：CreationDate vs server.js mtime + /api/sessions started_at；列程序一律 Get-CimInstance，不用 wmic|grep
- 純改 world.html / dashboard 靜態檔 → 直接 Ctrl+F5，免動程序

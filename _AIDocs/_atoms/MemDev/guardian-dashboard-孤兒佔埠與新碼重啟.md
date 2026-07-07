# Guardian Dashboard 孤兒佔埠與新碼重啟

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: guardian, server.js, 3848, dashboard, 重啟, 孤兒, 孤兒預防, stdin, EOF, EADDRINUSE, 新路由 404, relinquish, creature-chat, world.html
- Created-at: 2026-06-02
- Related: decisions-architecture, feedback-tooling-reliability, toolchain, reconcile-render-動畫狀態歸屬陷阱, 腦內世界-v3-自癒與-command-bus-架構, 腦內世界-環境演化-放置式架構, dashboard-apiatoms-專案-shared-範疇被-frontmatter-scope-覆寫誤歸核心房, 巨檔純機械拆分-carve腳本與驗證盲點, anti-evasion-hud-設計脊柱與強化前必讀

## 知識

- [臨] 架構：guardian server.js 一進程身兼二職——(a) 每 CC session 各 spawn 一份的 stdio MCP（atom_write/promote/edit_meta…）、(b) 綁 127.0.0.1:3848 的 HTTP dashboard（world.html/heal 等），埠只能一進程佔。故「回收佔埠者」不能無腦：佔埠的 server.js 同時可能是某活躍 session 的 MCP，貿然終止會中斷該 session 的 atom 工具。
- [臨] 孤兒預防（根治·第一道）：server.js 在 `require.main===module` 塊監聽 stdin `end`/`close`——父 CC client 退出（session/VS Code 關閉）時 OS 關 pipe 寫端 → 我方 stdin 收 EOF → 本進程 `process.exit(0)` 自行退出。故 session 一關其 server.js 隨之退出、:3848 自然釋放、孤兒根本不產生；且只作用於「自己的父」退出、不觸碰別實例（活躍 session 的 stdin 仍連活父、不會 EOF → 安全）。`_parentGone` 防重入、end+close 雙保險（Windows abrupt-kill 走 close）。守門置於 `require.main===module` → parity 測試 `require()` 匯入時不註冊、不誤觸 exit。
- [臨] 協作式交棒（兜底·第二道，供 EOF 未觸發、或「用新碼取代仍在跑的舊碼」）：新實例 `tryBindDashboard` 探到 :3848 被佔 → `reclaimStaleOrphan()` 發 `POST /api/relinquish{requesterMtime,requesterFile}`。holder 只在「同 server.js 檔 ∧ 對方 mtime > 自己 boot 時 mtime（＝我是舊碼）」時 ACK `relinquishing:true` 並 `process.exit(0)` 自行退出，請求方等 socket 釋放後 rebind；peer 跑當前碼回 `false`、非 guardian 無此路由（404/連不上）→ 一律讓步。**「只作用於自身」由構造保證**：從不對別進程 `process.kill`、無外部 shell → 外部程序零影響。判「舊碼」＝ holder 的 boot-time mtime（`SELF_MTIME_AT_BOOT`）< 請求方當前檔 mtime；改碼後 mtime 變大即為較新。輔助：`GET /api/whoami` 回 `{pid,file,mtime}`（判定 + 驗證新碼上線）、`WG_DASHBOARD_PORT` env override（隔離測試多實例）。
- [臨] 後果（僅在孤兒真的殘留時，如舊版無 EOF 預防的進程）：改過 server.js 的新路由不上線、`POST /api/<新路由>` 回 404 但檔內路由明明存在。交接常見錯誤心智模型「開新 session = guardian 重啟」就是栽在此（實案曾手動列 PID 回收 91484）。有了第一道 EOF 預防後，正常關 session 已不留孤兒。
- [臨] 上線 SOP（改 server.js 後讓 live :3848 換新碼）：改碼 mtime 變大 → 現存新實例走交棒接管；驗證＝`GET /api/whoami` 的 mtime == 新檔 mtime（或 POST 新路由回**非-404**，400=payload 無效即路由存在）+ `(Get-NetTCPConnection -LocalPort 3848 -State Listen).OwningProcess` == 新實例 PID。手動兜底（極少需要）：`Get-CimInstance Win32_Process -Filter "Name='node.exe'" | Where-Object { $_.CommandLine -like '*workflow-guardian-mcp*server.js*' } | Select ProcessId,CreationDate` 列**全部**實例（勿用 wmic|grep，配對會錯致誤傷，見 [[feedback-tooling-reliability]]），CreationDate 早於 mtime = 舊碼 → Stop-Process 回收（保留啟動晚於 mtime 的本 session 實例）。
- [臨] 例外：純前端改（world.html 等 dashboard 靜態檔）**不需動程序**——httpServer 每次 GET 重讀檔，瀏覽器 Ctrl+F5 即生效。只有改 server.js 本身才走上面重啟流程。
- [臨] 踩雷教訓：交棒初版用 JS `execFile powershell`（Get-CimInstance 查、Stop-Process 回收）→ detached 情境 `spawn EPERM` 崩、且 node→powershell→終止進程被卡巴斯基當惡意行為封鎖 → 改純 http 協作、自行退出、跨平台、零 spawn。孤兒預防（EOF 自退）同樣是純 Node、不 spawn、不碰別進程的取向延伸。

## 行動

- 改 server.js 要讓 live :3848 生效：正常靠 stdin-EOF 自退預防孤兒（關 session 即釋放埠）+ 協作式交棒接管；不靠重開 session/VS Code 硬碰
- 驗證新碼上線：`GET /api/whoami` mtime == 新檔 mtime，或 POST 新路由回非-404
- 判舊/新碼、列程序一律用 Get-CimInstance（CreationDate vs server.js mtime），不用 wmic|grep
- 純改 world.html/dashboard 靜態檔 → 直接 Ctrl+F5，免動程序

# Guardian Dashboard 孤兒佔埠與新碼重啟

- Scope: global
- Author: holylight
- Confidence: [觀]
- Trigger: guardian, server.js, 3848, dashboard, 重啟, 孤兒, stdin, EOF, EADDRINUSE, 新路由 404, relinquish, world.html, WG_DASHBOARD_PORT, 隔離埠, lib 改動
- Created-at: 2026-06-02

- Related: toolchain, feedback-tooling-reliability, anti-evasion-hud-設計脊柱與強化前必讀, dashboard-apiatoms-專案-shared-範疇被-frontmatter-scope-覆寫誤歸核心房, 巨檔純機械拆分-carve腳本與驗證盲點, 跨session協調-衝突預警機制與cc原生現況

## 知識

- [觀] 架構：server.js 一進程雙職——各 session spawn 的 stdio MCP + 綁 127.0.0.1:3848 的 HTTP dashboard，埠只一進程佔；回收佔埠者可能同時砍掉某活躍 session 的 atom 工具。
- [觀] 孤兒預防（第一道）：`require.main===module` 塊監聽 stdin end/close，父 CC client 退出→EOF→exit(0)；只對自己的父生效，活躍 session 不受影響。`_parentGone` 防重入、end+close 雙保險。
- [觀] 交棒（第二道）：新實例探到 :3848 被佔→`POST /api/relinquish{requesterMtime}`；holder 僅在「同檔 ∧ 對方 mtime > 自己 boot 時 mtime」ACK 後自退，從不 kill 別進程。`GET /api/whoami` 回 {pid,file,mtime}；`WG_DASHBOARD_PORT` 可隔離。
- [觀] `lib/*.js` 改動**不觸發交棒**（只比 server.js mtime）→ 現存實例續跑舊記憶體碼；live 生效只有新起 node 進程一途（reload window）。
- [觀] 驗證 lib 改動：起 `WG_DASHBOARD_PORT=<另一埠> node server.js` 跑完整 E2E（含 Playwright 點真前端），別 kill 他人持埠實例。bash 需 `sleep N | node …` 撐 stdin；TaskStop 只殺 shell 父層，node 須另行 Stop-Process。
- [觀] 孤兒殘留後果：新路由不上線、POST 回 404 但檔內有；「開新 session = guardian 重啟」是錯誤心智模型。
- [觀] 上線 SOP（改 server.js）：whoami mtime == 新檔 mtime（或新路由回非-404）+ 3848 listener PID == 新實例。列程序用 Get-CimInstance 篩 CommandLine 含 workflow-guardian-mcp，勿用 wmic|grep（見 [[feedback-tooling-reliability]]）；CreationDate 早於 mtime = 舊碼。
- [觀] 例外：純静態前端檔（world.html）改動不需動程序，Ctrl+F5 即生效。
- [觀] 踩雷：交棒初版走 execFile powershell → detached spawn EPERM + 卡巴斯基封鎖 → 改純 http 協作、零 spawn。
- [觀] runtime 重綁已實證：啟動 probe + 每 15s heartbeat，持埠者暴斃 ~15s 內自動重綁；「只在啟動搶埠」為錯誤假說。
- [觀] 「0 listener + 多個活 node」：playwright/excel 等 MCP 也是 node.exe；guardian 全滅時 0 listener 屬正常，開新 session 自癒。

## 行動

- 改 server.js 要 live 生效：靠 stdin-EOF 自退 + 協作式交棒，不靠重開 VS Code 硬碰
- 改 lib/*.js：交棒不會觸發——驗證走隔離埠實例，上線等 reload window 後以 whoami 的 pid 換了為準
- 判舊/新碼、列程序一律用 Get-CimInstance（CreationDate vs mtime），不用 wmic|grep
- 純改 world.html 静態檔 → Ctrl+F5，免動程序

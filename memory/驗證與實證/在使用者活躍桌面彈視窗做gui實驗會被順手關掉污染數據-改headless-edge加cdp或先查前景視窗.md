# 在使用者活躍桌面彈視窗做GUI實驗會被順手關掉污染數據-改headless-Edge加CDP或先查前景視窗

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: GUI 實驗, 彈窗, Edge --app, msedge, 實驗污染, headless, CDP, Page.setWebLifecycleState, playwright-core, EnumWindows, 前景視窗, 使用者在線
- Created-at: 2026-09-18

## 知識

- [臨] 在使用者正在用的桌面上 spawn Edge --app 視窗做長時間觀測（心跳/連線存活），三次實驗視窗都在 4 秒～4 分鐘內「消失」——不是瀏覽器凍結，是使用者順手把彈出的視窗關了（EnumWindows 事後找不到任何 HUD 視窗、VS Code 在前景）。連線與心跳同時歸零＝視窗被關，不是頁面被節流。
- [臨] 不打擾又可控的替代：`require(%APPDATA%/npm/node_modules/@playwright/mcp/node_modules/playwright-core).chromium.launch({channel:'msedge', headless:true})` 開頁，`page.context().newCDPSession(page)` 後 `Page.setWebLifecycleState({state:'frozen'|'active'})` 模擬凍結（注意 headless 下 frozen 不會停 Worker 輪詢，只能驗連線是否存活，驗不了真實休眠）。真要驗被遮住的行為，先用 EnumWindows/GetForegroundWindow 確認使用者不在線再彈窗。

## 行動

- 動桌面 GUI 前先列前景視窗；使用者在線就改 headless + CDP
- 實驗數據異常先排除「人為介入」：視窗還在嗎、連線與心跳是否同時歸零

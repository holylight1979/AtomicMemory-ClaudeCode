# v6守門出廠預設關-直接跑的js與lib-verify驗證要自己帶WG_V6等於1

- Scope: global
- Author: holylight
- Source: 2026-10-22 mcp-write-gate 減量實測
- Confidence: [臨]
- Trigger: WG_V6, v6.enabled, v6 出廠關, conftest 自動設 WG_V6, lib/verify, node 驗證腳本, v6 案例大量紅
- Created-at: 2026-10-22

## 知識

- [臨] workflow/config.json 的 v6.enabled 出廠是 false。hooks/verify、tools/verify 的 conftest 會自動設 WG_V6=1；lib/verify 沒有，node 直接跑的 MCP 驗證腳本也沒有，所以它們起的 py 子行程看到的是「關」，v6 案例大量紅，看起來像程式壞了。
- [臨] 新寫的 js 驗證或 lib/verify 案例要測 v6 行為，就在檔頭自己設 WG_V6=1。

## 行動

- v6 案例一片紅：先查受測子行程有沒有拿到 WG_V6=1，再懷疑程式

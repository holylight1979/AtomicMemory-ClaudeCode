# MCP的node端程式改了要開新session才載到-同機其他session的MCP程序仍跑舊碼-python端每次spawn立即生效

- Scope: global
- Author: holylight
- Source: session e40bc31f，tri-link projects/057／root/065
- Confidence: [臨]
- Trigger: MCP 舊碼, atom-tools.js, funnel.js, 改了沒生效, 重起 MCP, 新 session 才載, write-gate title, 去重閘沒吃到
- Created-at: 2026-10-07
- Quote: 「接手「AI 寫碼守門三方討論」的根層總控端。先讀 C:\Users\holylight\.claude\memory\_staging\next-phase-AI寫碼守門三方討論.md 全文，照「下一步」做：重掛 Monitor 盯 c:\Projects\.claude\inbox\tri-link\ 的 from-projects 與 from-tslg、對帳信箱、做 R4 與 R5、每 6…」

## 知識

- [臨] 實踩：R6 改了 `tools/workflow-guardian-mcp/lib/atom-tools.js`／`funnel.js`（去重閘多傳 title）並上版，另一個早已開著的專案 session 立刻實測仍被擋 0.869——它的 workflow-guardian MCP 是 node 常駐程序，session 開時載入 js，之後改檔不重載。同機其他 session 要吃到新碼必須開新 session（MCP 跟著重起）。對照：python 端（memory-write-gate.py、hooks）每次呼叫都是新 spawn，改完立即生效。所以 node 端和 python 端各改一半的修法，在舊 session 裡會出現「半生效」的怪結果。

## 行動

- 改到 workflow-guardian-mcp 的 js → 通知其他 session「要開新 session 才生效」，別讓他們在舊 session 實測
- 別人回報「你的修法沒生效」→ 先問他的 session 是不是你上版前開的；自己用 python 端 stdin 直打一次區分哪半沒生效

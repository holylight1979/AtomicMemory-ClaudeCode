# MCP的node端程式改了要開新session才載到-同機其他session的MCP程序仍跑舊碼-python端每次spawn立即生效

- Scope: global
- Author: holylight
- Source: session e40bc31f，tri-link 某專案/057／root/065
- Confidence: [臨]
- Trigger: MCP 舊碼, atom-tools.js, funnel.js, 改了沒生效, 重起 MCP, 新 session 才載, write-gate title, 去重閘沒吃到
- Created-at: 2026-10-07
- Quote: 「接手「AI 寫碼守門三方討論」的根層總控端。先讀 C:\Users\holylight\.claude\memory\_staging\next-phase-AI寫碼守門三方討論.md 全文，照「下一步」做：重掛 Monitor 盯 c:\Projects\.claude\inbox\tri-link\ 的 from-projects 與 from-tslg、對帳信箱、做 R4 與 R5、每 6…」

## 知識

- [臨] 實踩：R6 改了 `tools/workflow-guardian-mcp/lib/atom-tools.js`／`funnel.js`（去重閘多傳 title）並上版，另一個早已開著的專案 session 立刻實測仍被擋 0.869——它的 workflow-guardian MCP 是 node 常駐程序，session 開時載入 js，之後改檔不重載。同機其他 session 要吃到新碼必須開新 session（MCP 跟著重起）。對照：python 端（memory-write-gate.py、hooks）每次呼叫都是新 spawn，改完立即生效。所以 node 端和 python 端各改一半的修法，在舊 session 裡會出現「半生效」的怪結果。
- [臨]（need_goal 合進 main 後實踩）python 閘立刻生效、它要求呼叫的 MCP 工具得 Reload 才有 → 合併前就開著的分頁改程式被擋、又建不了樹，誠實流程死鎖。合這類「閘＋新 MCP 工具」的改動前，先讓還在改碼的分頁 Reload；擋下訊息要附「叫不到工具 → Reload Window」。被擋的分頁不繞閘、不提關閘，把要改的內容原文交給有工具的分頁。
- [臨] 夜實測修正：在 VS Code 擴充裡，workflow-guardian MCP 是整個視窗共用一個程序，開新 Claude Code 分頁不會重起它——骨架（need-goal.js）合進 main 後，新開分頁的工具清單仍沒有 need_goal。要載到 MCP 新碼只有 Reload Window（或整個關掉 VS Code 再開）；「開新 session 才載到」只對終端機 CLI 各自起程序的情況成立。
- [臨] 程序樹實證：每個 session 的 claude.exe 底下經 pythonw run-hidden.py 外殼各起一個 MCP node 程序，不是整個 VS Code 視窗共用一個（接續單舊寫法錯，已更正）。收尾閘會沿程序樹比對這個 session 的服務載入版本，已最新時叫使用者 Reload Window 會被擋一次；程式更新以外的理由要重載就加一行「重載原因：…」。
- [臨] py 閘新增一種「拒寫」結果時，合併後 py 立即生效、MCP js 要新 session 才換碼；舊 js 只認既有的拒寫動作名（skip／update），新動作名會被當放行直接落檔。新的拒寫型結果要沿用舊 js 會拒的 action，另加旗標（例 need_declaration）給新 js 辨識；實測舊 js＋新 py 照拒不落檔。

## 行動

- 改到 workflow-guardian-mcp 的 js → 通知其他 session「要開新 session 才生效」，別讓他們在舊 session 實測
- 別人回報「你的修法沒生效」→ 先問他的 session 是不是你上版前開的；自己用 python 端 stdin 直打一次區分哪半沒生效

# need_goal新增選填欄位在MCP未Reload前Python端就收得到-js只驗已知欄位-但LLM看不到新欄位說明-提問的PreToolUse不擋提醒要到使用者答完才看到

- Scope: global
- Author: holylight
- Source: commit d3e59d75 2026-10-15（判斷入口盤點階段 2）
- Confidence: [臨]
- Trigger: need_goal 新欄位, MCP Reload, same_class, inputs, 未知欄位, PreToolUse 提醒時機, AskUserQuestion 提醒, 交出前一問
- Created-at: 2026-10-15
- Related: pretooluse的additionalcontext不是寫前攔截-edit-payload已生成-提醒只影響下一次

## 知識

- [臨]（實測）need_goal 的 js 層（tools/workflow-guardian-mcp/lib/need-goal.js）只驗已知欄位的形狀，不拒未知欄位；PostToolUse 拿到的是原始 tool_input。所以在 Python 端（wg_need_goal／wg_verify_scope）新增的選填欄位（例：reconcile 的 same_class、verify_scope 的 inputs），本 session 的 MCP 沒 Reload 也照樣收、存、顯示。差別只在 LLM 看不到新欄位的 schema 說明，要靠擋訊息或回應文字告訴它。
- [臨] 反過來：要讓 LLM 自己想到用新欄位，schema 說明（mcp.js）與 js 驗證都要同步，且已開著的分頁要 Reload Window 才載到；收尾報告要寫這一句。
- [臨] 想在「提問、交計畫之前」送一題給 LLM：AskUserQuestion／ExitPlanMode 的 PreToolUse 不擋時，additionalContext 要等工具跑完（使用者答完）才進 LLM 眼前，來不及影響這次提問。真正來得及的點是：擋下時的訊息、寫計畫檔（plans／_staging 的 .md）後的 PostToolUse、完整對照收下的回應（通常緊接在交付訊息之前）。


## 行動

- Python 端加 need_goal 選填欄位時：同步 mcp.js schema 與 need-goal.js 驗證，報告提醒 Reload Window；Python 端可先用、不必等 Reload
- 要在提問或交計畫前送題：放擋訊息、寫計畫檔後的 PostToolUse 或完整對照回應，不放不擋的 PreToolUse 提醒


## 演化日誌

| 日期 | 變更 | 來源 |
|------|------|------|
| 2026-10-30 | 退役移入 _distant/：描述的機制（需求目標樹 need_goal 的 MCP 欄位與完整對照送題時機）已從寫碼守門拔除；PreToolUse 提醒時機另有 pretooluse 的 additionalContext 卡記載 | memory-audit --delete |

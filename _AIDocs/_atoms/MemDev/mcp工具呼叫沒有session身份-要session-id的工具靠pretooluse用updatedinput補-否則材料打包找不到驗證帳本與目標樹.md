# MCP工具呼叫沒有session身份-要session_id的工具靠PreToolUse用updatedInput補-否則材料打包找不到驗證帳本與目標樹

- Scope: global
- Author: holylight
- Source: G9 軌（claude-9c）2026-10-20 交付信 001 第十段，總控台代寫
- Confidence: [臨]
- Trigger: second_opinion_start, session_id 未給, updatedInput, MCP 沒有 session, 材料沒有需求目標樹, goal.md 無目標樹, PreToolUse 補參數, settings.json matcher
- Created-at: 2026-10-20

## 知識

- [臨] MCP 工具（例 second_opinion_start）被呼叫時，MCP 進程本身不知道是哪個 session 在叫，參數裡沒有 session_id，打包材料時就找不到這個 session 的驗證帳本與需求目標樹（live 實測 note：「沒有驗證帳本（session_id=未給）」，goal.md 永遠是「無目標樹」）。解法：PreToolUse hook 對這類工具名用 updatedInput 把 hook 輸入的 session_id 補進參數（與 Agent 分支同一做法）；前提是 settings.json 的 PreToolUse matcher 有掛那個工具名，沒掛就補不到。
- [臨] 通則：任何要「本 session 的狀態」（帳本、樹、改檔清單）的 MCP 工具，都要走這條補參數路，不要在 MCP 端猜 session；驗收時要真打一次看打包結果第一行是不是樹根。

## 行動

- 新增要 session 狀態的 MCP 工具：PreToolUse 補 session_id（updatedInput）＋ settings.json matcher 掛工具名＋合併後真打一次驗

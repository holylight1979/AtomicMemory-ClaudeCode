# MCP js 改動後未重啟-lazy-require 新舊模組混載-tool 回 undefined 類錯誤不是 bug-Reload Window 即復原

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: MCP 重啟, Reload Window, Received undefined, spawn failed, atom_write 壞, lazy-require, 模組混載, 改 js 後, paths.js
- Created-at: 2026-09-01

## 知識

- [臨] 改了 `tools/workflow-guardian-mcp/lib/*.js` 後、MCP server 還沒重啟時，已載入的模組（如 paths.js）是舊版快取，而 **lazy-require** 的模組（funnel.js/atom-tools.js 在第一次 tool call 才載入）會讀到新檔 → 新檔引用舊模組沒匯出的名字（例：`PYTHON_EXE`）得到 undefined。症狀：`atom_write: spawn failed: The "file" argument must be of type string. Received undefined`。這不是 patch 壞，是混載；Reload Window（或重啟 claude）即復原。重啟前如需寫 atom，走 py 單源 `lib.atom_io.write_atom(source="mcp")`（新 atom 只能 [臨] 起跳）。

## 行動

- 改 MCP js 後的 tool 錯誤先判「是否尚未重啟」，重啟後再驗證才算數
- 合併別人的 MCP js patch 後提醒對方：git pull 後 Reload Window

# claude-code的mcp工具呼叫上限約27小時但互動模式滿120秒自動轉背景-要等長工作的mcp工具每次等待短於120秒分段等

- Scope: global
- Author: holylight
- Source: 2026-10-23 第二意見等待修補實測
- Confidence: [臨]
- Trigger: MCP_TOOL_TIMEOUT, MCP_TOOL_IDLE_TIMEOUT, MCP_AUTO_BACKGROUND_MS, MCP 工具逾時, MCP 轉背景, 120 秒轉背景, Bash 轉背景, 長工作 MCP 工具, 分段等待
- Created-at: 2026-10-22
- Related: 查claude-code內建預設值-claude-exe是bun打包的原生檔-grep-a撈環境變數名前後300字找預設常數-檔約300mb要一次查準

## 知識

- [臨] Claude Code 2.1.308 執行檔實查：MCP 工具呼叫上限 MCP_TOOL_TIMEOUT 預設 1e8 毫秒（約 27.8 小時），工具送 progress 通知不會延長；stdio 閒置上限 CLAUDE_CODE_MCP_TOOL_IDLE_TIMEOUT 預設 30 分。
- [臨] 互動模式下 MCP 呼叫滿 120 秒會自動轉成背景工作（CLAUDE_CODE_MCP_AUTO_BACKGROUND_MS 預設 120000），Bash 指令同樣滿 120 秒轉背景；-p 無頭模式不轉。
- [臨] 所以要等長工作的 MCP 工具，每次等待要短於 120 秒，分段等。

## 行動

- 設計會等長工作的 MCP 工具：單次等待設在 120 秒以下，沒結果就回「還在跑」讓呼叫端再等一段
- 要確認 Claude Code 內建上限：查執行檔裡的預設常數，不憑記憶

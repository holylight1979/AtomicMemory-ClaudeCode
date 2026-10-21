# 在worktree跑mcp的js測試要設WG-CLAUDE-DIR指暫存資料根-否則server開機紀錄寫進live-要真落檔就同程序require-atom-tools先換掉sendToolResult與syncMemoryIndex

- Scope: global
- Author: holylight
- Source: track-dedupe-ai-judge 2026-10-20 verify_atom_write_dedupe.js（總控台代寫）
- Confidence: [臨]
- Trigger: smoke_mcp_stdio, WG_CLAUDE_DIR 暫存, mcp-boot 寫進 live, js 測試落檔, require atom-tools, sendToolResult, syncMemoryIndex, MCP js 測試 隔離
- Created-at: 2026-10-20
- Quote: 「"下個寫碼session" !? 他們有空就讓他們修完不是嗎..? 這也是我說 "我從未答應把這種東西另外放進修正計畫" 的狀況... 倘若是 Codex 或審查時挖出來的、但LLM判斷後 其實屬於"飄移"的，直接不做，但倘若有關且確實有問題，就應該要立即修正」

## 知識

- [臨] 在 worktree 跑 tools/workflow-guardian-mcp/verify/smoke_mcp_stdio.js 要把 WG_CLAUDE_DIR 指到暫存資料根（裡面放 memory/_meta 的 taxonomy.json、realm-lexicon.json），否則 server 的開機紀錄會寫進 live 的 workflow/mcp-boot。MCP js 測試要真落檔驗行為，可在同一程序 require lib/atom-tools，先把 mcp.sendToolResult 與 funnel.syncMemoryIndex 換成收集用的替身，再接假向量服務＋真 py 閘跑（範例 tools/workflow-guardian-mcp/verify/verify_atom_write_dedupe.js）。

## 行動

- worktree 裡跑任何會起 MCP server 的測試：先設 WG_CLAUDE_DIR 指隔離根

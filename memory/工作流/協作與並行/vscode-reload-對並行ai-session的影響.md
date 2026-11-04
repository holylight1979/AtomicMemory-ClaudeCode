# VSCode-Reload-對並行AI-session的影響

- Scope: global
- Author: holylight
- Source: commit:d823a10 2026-08-24（原對話已逾保留期）
- Confidence: [臨]
- Trigger: VSCode Reload, Reload Window, 雙 sessionstart, monitor 重掛, 並行 session, 面板 MCP, reload 後名字換了, No agent named
- Created-at: 2026-08-24
- Related: 並行llm即時通訊-inbox機制

## 知識

- [臨] VSCode Reload Window 不是冷啟動：本尊 session id 不變、對話歷史仍在（resume）。真正卸下 Claude 相容 hooks/skills 需完整關掉 VSCode 再開——inspect 在 hooks=false/skills=false 之後仍列 `~/.claude` 來源 19 條 hook + 21 條 skill（已驗證，卸載未證實）。
- [臨] Reload 殺掉 Grok persistent monitor；Reload 後聲盲直到使用者戳醒，開場自檢（`ai-inbox.md`）才重掛。常出現雙 sessionstart：短命 id 無 sessionend + 本尊 resume。
- [臨] Grok 面板 workflow-guardian MCP 非決定性（同條件 reload 紅/綠互現）；CLI/無頭穩定綠。面板寫 atom 定調可先試 MCP，紅則 `python -m lib.atom_io_cli`。
- [臨] grok-guardian PreToolUse 紅線在面板 session 也會攔截：直接 `write` `~/.claude\` 下路徑被 deny（例外 `memory\_staging\`）。終端指令繞寫不擋。
- [臨] 沒用 `--name` 起的分頁，Reload 後跨 session 的訊息名字（ListAgents 的 claude-xx）會換：同一分頁 reload 前叫 claude-21、之後叫 claude-2d，舊名 SendMessage 回「No agent named … is reachable」；分頁要等它被 resume 才出現在清單，剛 reload 時可能缺人。用 `claude --bg --name <軌名>` 起的 session 名字固定，不受影響。接手時先跑 `claude agents --json`（每列有 sessionId 與 name）對人，不憑舊名或清單順序猜。

## 行動

- Reload 後請使用者戳 Grok 一聲，再重掛 monitor、對帳信箱。
- 不要用 Grok 的 write/search_replace 直接改 `~/.claude`；atom 走 MCP 或 atom_io_cli。
- 判死不只看 sessionend；Reload 的雙 start 不是兩個對手。
- 要長期對話的工作軌用 --name 起，地址才不會因 reload 失效。

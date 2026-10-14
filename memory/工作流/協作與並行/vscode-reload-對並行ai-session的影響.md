# VSCode-Reload-對並行AI-session的影響

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: VSCode Reload, Reload Window, 雙 sessionstart, monitor 重掛, 並行 session, 面板 MCP
- Created-at: 2026-08-24
- Related: 並行llm即時通訊-inbox機制
- Source: commit:d823a10 2026-08-24（原對話已逾保留期）

## 知識

- [臨] VSCode Reload Window 不是冷啟動：本尊 session id 不變、對話歷史仍在（resume）。真正卸下 Claude 相容 hooks/skills 需完整關掉 VSCode 再開——inspect 在 hooks=false/skills=false 之後仍列 `~/.claude` 來源 19 條 hook + 21 條 skill（已驗證，卸載未證實）。
- [臨] Reload 殺掉 Grok persistent monitor；Reload 後聲盲直到使用者戳醒，開場自檢（`ai-inbox.md`）才重掛。常出現雙 sessionstart：短命 id 無 sessionend + 本尊 resume。
- [臨] Grok 面板 workflow-guardian MCP 非決定性（同條件 reload 紅/綠互現）；CLI/無頭穩定綠。面板寫 atom 定調可先試 MCP，紅則 `python -m lib.atom_io_cli`。
- [臨] grok-guardian PreToolUse 紅線在面板 session 也會攔截：直接 `write` `~/.claude\` 下路徑被 deny（例外 `memory\_staging\`）。終端指令繞寫不擋。
- [臨] Reload Window 後跨 session 的訊息名字（ListAgents 的 claude-xx）會換：同一個 a2 工作分頁 reload 前叫 claude-21、之後叫 claude-2d；舊名 SendMessage 回「No agent named … is reachable」。分頁要等它被 resume 才出現在 ListAgents（列上顯示 started N 分鐘前），所以剛 reload 時清單可能缺人、過幾分鐘又多出新名字。總控台接手時先 ListAgents，對每個不認得的名字送一句「你是哪個軌／原名是什麼？只回一句身份」，回覆後才派工，不要憑舊名或清單順序猜。
- [臨] Reload Window 把所有存活 session 的 claude-xx 通訊名全部重編，派工單與開工句裡寫死的舊名全失效，新開的工作軌送「收到開工」會失敗。回復法：對人總控台 Reload 後先 ListAgents，對每個 peer 送同一則「報你的軌名＋我的新名」，收齊後把調度新名轉給各軌、sed 改掉派工單與接續單現任行的舊名。預防：開工句與派工單寫「調度總控台（分頁標題 X，名冊名會變，送前先 ListAgents）」，不寫死 claude-xx。
- [臨] Reload 時機：等所有在執行回合的分頁停下（閒置或在等人答）再 Reload，並排在新軌開工之前，讓新軌一開始就載到新 MCP 碼、也不會被打斷。MCP 改的若只是提示字句，晚點 Reload 不影響正確性。

## 行動

- Reload 後請使用者戳 Grok 一聲，再重掛 monitor、對帳信箱。
- 不要用 Grok 的 write/search_replace 直接改 `~/.claude`；atom 走 MCP 或 atom_io_cli。
- 判死不只看 sessionend；Reload 的雙 start 不是兩個對手。

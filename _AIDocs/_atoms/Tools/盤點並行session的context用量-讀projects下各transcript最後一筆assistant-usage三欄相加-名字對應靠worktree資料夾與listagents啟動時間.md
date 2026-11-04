# 盤點並行session的context用量-讀projects下各transcript最後一筆assistant-usage三欄相加-名字對應靠worktree資料夾與ListAgents啟動時間

- Scope: global
- Author: holylight
- Source: session:72133ffb#7946e477 2026-10-13
- Quote: 「我看 某專案 的token量已經快要滿了，應該要新開session接續了吧?」
- Confidence: [臨]
- Trigger: token 量, context 用量, 盤點 session, 快滿了, 換手時機, transcript usage, cache_read_input_tokens, 多 session 盤點, claude agents --json
- Created-at: 2026-10-13

## 知識

- [臨] 要知道各並行 session 現在吃了多少 context（判要不要換手），不必逐一問它們：讀 `~/.claude/projects/<cwd-slug>/<sessionId>.jsonl`，取最後一筆 type=assistant 的 `message.usage`，`input_tokens + cache_read_input_tokens + cache_creation_input_tokens` ≈ 該 session 目前 context（1M 窗下 870K ≈ 87%）。
- [臨] 名字對應：`claude agents --json` 每列直接給 sessionId 與 name（`--name` 起的就是軌名），拿 sessionId 找檔即可。cwd-slug 是 cwd 每個非英數字元各轉一個 '-'：`--worktree <軌名>` 起的工作軌 cwd 是 `<repo>/.claude/worktrees/<軌名>/`，根層 session 在 `projects/c--users-holylight--claude/`。腳本模板：逐行 json.loads，記最後一筆 usage 與 user/assistant 筆數，五個 session 一次印出。

## 行動

- 要判工作 session 該不該換手：先讀 transcript 最後一筆 usage，不要靠它自報
- 超過 80% 的 session 不再派新工，只寫交接備忘＋ atom

# 要靠transcript宣告判的閘擋MCP工具-MCP行程沒有session與transcript-掛settings的PreToolUse-matcher由python-hook判

- Scope: global
- Author: holylight
- Source: session:7e33fec4 2026-10-22
- Confidence: [臨]
- Trigger: MCP 閘, atom_write 擋, PreToolUse matcher, MCP 沒有 session, 宣告行, mcp__workflow-guardian__, updatedInput, session_id 補參數
- Created-at: 2026-10-22
- Quote: 「施工agent若能多開就多開，提速吧」

## 知識

- [臨] MCP server 行程不知道是哪個 session、讀不到 transcript，要核對本 session 宣告行的閘放在 MCP 端判不了。做法：settings.json PreToolUse 那條 workflow-guardian matcher 加上 `mcp__workflow-guardian__<工具名>`，Python hook 拿 hook 輸入的 session_id／transcript_path 判、deny 就不會呼叫 MCP；JS 不改、不重複邏輯。
- [臨] 反過來要讓 MCP 工具本身拿到 session（例：要讀本 session 的驗證帳本、改檔清單）：PreToolUse hook 對那個工具名用 updatedInput 把 hook 輸入的 session_id 補進參數（與 Agent 分支同一做法），前提同樣是 matcher 掛了那個工具名；不要在 MCP 端猜 session。
- [臨] MCP 呼叫要算出會寫哪個檔，用 MCP 自己定位用的同一支 `lib/atom_io.locate_atom`（約 0.13 秒），不要在 hook 另寫一套路徑規則；matcher 只在 settings.json 一處，沒有安裝範本另存。

## 行動

- 新閘要擋 MCP 工具：先確認判定需不需要 session／transcript；需要就掛 PreToolUse matcher、在 Python hook 判
- 新增要本 session 狀態的 MCP 工具：PreToolUse 用 updatedInput 補 session_id＋ matcher 掛工具名，合併後真打一次看工具拿到的 session_id
- 改完補一案讀真 settings.json 斷言 matcher 有那個工具名

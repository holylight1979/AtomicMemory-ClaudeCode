# vscode-claude-code-空分頁由總控台用剪貼簿貼開工句啟動-enter只換行要點送出鈕-中文走set-clipboard不走type

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 開新 session, 空分頁, 貼 prompt, Set-Clipboard, MCPControl, 總控台派工, 多 session 啟動, VS Code Claude Code 分頁
- Created-at: 2026-10-08
- Source: session:94d9989e 2026-10-09
- Quote: 「[Cross-session idle notice] "claude-a2", which you asked to be notified about, is idle now — it finished a turn at 23:50. This is an automated notice from that session's harness — not a message from…」

## 知識

- [臨] 使用者下班前在 VS Code 預開多個空的 Claude Code 分頁（Bypass permissions），總控台要派工時自己啟動：PowerShell `Set-Clipboard -Value <開工句>`（中文走剪貼簿，MCPControl 的 type 走 IME 進不了輸入框）→ MCPControl 點分頁（截圖確認是 Untitled 空頁、模式是 Bypass）→ 點輸入框 → `ctrl+v` → 截圖核對內容 → 點右下角橘色送出鈕（Enter 只插入換行，不送出）。開工句要含：軌名、總控台名、派工 prompt 絕對路徑、worktree 絕對路徑、「cwd 在 live、所有讀寫用 worktree 絕對路徑」、回報一句的要求。新 session 的名字（claude-xx）要等它 SendMessage 回來才知道，ListAgents 看不出哪個分頁是誰。
- [臨] 已 idle 的既有 session 可直接 SendMessage 指派，不必走 GUI；GUI 只用在真正空白的分頁。

## 行動

- 派工前先 ListAgents 看有無 idle 的可指派；沒有才走剪貼簿＋GUI 開空分頁
- 貼上後截圖核對再點送出鈕，不按 Enter

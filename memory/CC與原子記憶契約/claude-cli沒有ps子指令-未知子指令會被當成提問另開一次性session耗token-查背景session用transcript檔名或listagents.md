# claude-cli沒有ps子指令-未知子指令會被當成提問另開一次性session耗token-查背景session用transcript檔名或listagents

- Scope: global
- Author: holylight
- Source: session f0055a0d 2026-10-22 誤用實踩
- Confidence: [臨]
- Trigger: claude ps, claude 子指令, 背景 session id, claude stop, 未知子指令, 一次性 session
- Created-at: 2026-10-22

## 知識

- [臨] `claude.exe ps`（CC 2.1.304）不是子指令：「ps」被當成一句提問，另開一個一次性 session 回答（會耗 token、還會跑 hook）。要查背景 session 的 id 去 `claude stop <短 id>`：讀 `~/.claude/projects/<cwd 編碼>/<session-id>.jsonl` 的檔名，或用 ListAgents；不確定有沒有某個子指令先跑 `claude --help`。

## 行動

- 對 claude CLI 下沒用過的子指令前先看 --help

# Claude 審查者 A：Claude Code 官方最新變更（2026-05 → 09）— 摘錄

（來源：claude-code-guide agent，21 次工具呼叫；版本號待 Codex #1 交叉驗證）

## Hooks
- SubagentStart / SubagentStop（v2.1.183+）：subagent context 仍隔離，自製記憶不自動注入。
- PermissionRequest / PermissionDenied（v2.1.183+）：可當「使用者拒絕操作」的記憶觸發點。
- hooks `async: true` + 自訂 `timeout`（v2.1.128+，2026-05）：hook 可背景執行、不卡 prompt。→ 可能取代 run-hidden.py detached worker 的一部分（待驗 SessionEnd 是否適用）。
- PostToolBatch / PostCompact 官方文件確認存在（v2.1.265+ 才正式列）。

## 原生記憶
- MEMORY.md 200 行 / 25KB 限制（v2.1.214+）；橋接檔需守限。
- `.claude/rules/` path-scoped（frontmatter `paths:`，v2.1.198+）；symlink 共用（v2.1.225+）。
- AGENTS.md 原生支援（v2.1.277+），CLAUDE.md 優先。
- 跨專案記憶：原生仍無。
- /compact 後根層 CLAUDE.md 重讀；嵌套與 rules 待再次讀檔才重載。

## Context
- promptCacheTtl / subagentPromptCacheTtl 設定（v2.1.242+，2026-08-25）；Pro/Max 預設 1h。
- Subagent 預設隔離，`omitClaudeMd: true` 可跳過 CLAUDE.md（v2.1.233+）。
- /context 列出載入的記憶檔、MCP、hook 狀態（v2.1.206+）。
- Dynamic Workflows（v2.1.157+，2026-05-25）：workflow 內 agent context 獨立，記憶要手動傳。

## Skills / Plugins
- frontmatter：`context: fork`、`disable-model-invocation`、`paths`、`when_to_use`、`allowed-tools`、`hooks`（v2.1.240+）。
- `/skill-doctor`（v2.1.251+，2026-09-04）：7 日 tokens/uses、未使用警告、context budget。
- `claude plugin eval`（v2.1.269+，2026-09-07）：6 grader、with/without ablation、CI threshold。
- marketplace + `claude mcp login`。

## 其他
- session `--name`、resume、Remote Control；Claude Tag（Slack，2026-06-23）與本地 auto memory 隔離。
- Agent SDK 支援 hook 註冊，不內建 auto memory。
- `--append-system-prompt` resume 不保留。
- OpenTelemetry：未查到新增。

## 該 agent 認為最值得注意的 5 件
1. prompt cache 1h TTL；2. subagent 完全隔離；3. workflow context 獨立；4. MEMORY.md 200 行硬限；5. Claude Tag 與本地 auto memory 隔離。

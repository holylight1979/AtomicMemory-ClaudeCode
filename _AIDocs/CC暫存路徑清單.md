# CC 暫存路徑清單

> Claude Code 運作期間會產生暫存檔的已知路徑，清理時逐條掃。

| 路徑模式 | 產生者 | 說明 |
|---|---|---|
| `%TEMP%/wg-iso-*/` | pytest（workflow-guardian 測試隔離） | 每次跑測試產生一個，可全刪 |
| `%TEMP%/pytest-of-<user>/` | pytest 框架 | 測試 session 暫存，可全刪 |
| `%TEMP%/claude/<project-hash>/<session-uuid>/scratchpad/` | Claude Code session | 每個 session 一個；先用 ListAgents 與 `workflow/state-*.json` 排除還開著的 session，其餘可刪 |
| `~/.claude/workflow/inbox/` | 多 session 派工信箱（`to-track-*`、`from-track-*`、`_console`），也放實測結果 | **不是暫存**：本機唯一一份、不進版控、刪了救不回；逐夾確認已結案、結果已封存才刪，不可整夾清空 |
| `~/.claude/memory/_staging/` | 研究報告、接續單 | 做完的搬 DevHistory 或刪；未完成的留著 |

## 清理順序建議

1. **_staging/**：判斷價值 → 搬 DevHistory 或刪
2. **%TEMP%/**：確認是暫存後批次刪
3. **workflow/inbox/**：逐夾確認，不整夾清空

## 更新紀錄

- 2026-11-05：初版，從 v6.0 清理作業整理出的五條路徑

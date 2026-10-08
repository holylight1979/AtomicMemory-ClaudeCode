# settings.json 權限與工具鏈

> 從 Architecture.md 移入（2026-04-17 索引化）。
> keywords: settings, permissions, allow, 權限, 工具鏈, tools

## 權限設定（`settings.json::permissions.allow`）

- **Bash**：powershell, python, ls, wc, du, git, gh, ollama, curl, echo, grep, find
- **Read**：`C:\Users\**`, `C:\OpenClawWorkspace\**`
- **Edit/Write**：`.claude/**`、某專案的 `.claude/**`
- **MCP**：workflow-guardian (workflow_signal, workflow_status)
- **PostToolUse matcher**：`Edit|Write|Bash`（2026-04-17 加 Bash 以支援 Evasion Guard Test-Fail 偵測 + _CHANGELOG auto-roll）

## 工具鏈（`tools/`）

| 工具 | 路徑 | 用途 |
|------|------|------|
| ollama_client.py | `tools/ollama_client.py` | Dual-Backend Ollama Client（三階段退避+auth+failover） |
| rag-engine.py | `tools/rag-engine.py` | CLI: search/index/status/health |
| memory-write-gate.py | `tools/memory-write-gate.py` | 寫入品質閘門 + 去重 |
| memory-audit.py | `tools/memory-audit.py` | 格式驗證、過期、晉升建議（支援 `--project-dir`） |
| memory-conflict-detector.py | `tools/memory-conflict-detector.py` | 矛盾偵測（full-scan / write-check / pull-audit 三 mode） |
| conflict-review.py | `tools/conflict-review.py` | V4 Pending Queue 後端（list/approve/reject，管理職雙向認證 guard） |
| memory-peek.py | `tools/memory-peek.py` | V4.1 列最近 24h 自動萃取 atom + pending + trigger 原因 [F7] |
| memory-undo.py | `tools/memory-undo.py` | V4.1 撤銷自動萃取（_rejected/ + reason 分類 + reflection_metrics）[F20][F23] |
| atom-health-check.py | `tools/atom-health-check.py` | Atom 健康度（Related 完整性） |
| migrate-v221.py | `tools/migrate-v221.py` | V2.21 遷移（_AIAtoms + 個人記憶 → .claude/memory/） |
| cleanup-old-files.py | `tools/cleanup-old-files.py` | 環境清理 |
| snapshot-v4-atoms.py | `tools/snapshot-v4-atoms.py` | [F13] 產 `v4_atoms_baseline.jsonl`（63+ atoms SHA256） |
| changelog-roll.py | `tools/changelog-roll.py` | _CHANGELOG.md 自動滾動（搭配 PostToolUse hook） |
| read-excel.py | `tools/read-excel.py` | Excel 讀取工具 |
| unity-yaml-tool.py | `tools/unity-yaml-tool.py` | Unity YAML 解析/生成 |
| memory-vector-service/ | `tools/memory-vector-service/` | HTTP 服務 (port 3849) |
| gdoc-harvester/ | `tools/gdoc-harvester/` | Google Docs/Sheets 收割 + dashboard |
| workflow-guardian-mcp/ | `tools/workflow-guardian-mcp/` | MCP server + Dashboard (port 3848) |

完整檔樹：`Project_File_Tree.md`。

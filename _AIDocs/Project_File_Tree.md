# Claude Code 全域設定 — 目錄角色說明
> 路徑 `~/.claude/`；2026-04-28 瘦身 218→30 行；2026-06-03 校準 V5 現況（commands→skills、補 `lib/`·`workflow/`·`plugins/`·`_AIDocs/_atoms/`）；詳細跑 `tree -L 3` 或查各子目錄 `_INDEX.md`

## 頂層目錄角色
| 路徑 | 角色 | 維護來源 |
|------|------|---------|
| `CLAUDE.md` / `IDENTITY.md` / `USER.md` / `rules/core.md` | always-loaded 入口 | 手寫 |
| `settings.json` / `.mcp.json` | Hook 鏈 + 權限 + MCP server | 手寫 |
| `memory/` | 原子記憶資料層（`_atom_index.json` SoT + `MEMORY.md` 索引 + core atom md + `_vectordb/` + `wisdom/` + `_reference/` + `_staging/` + `personal/{user}/` + `shared/` + `roles/{role}/`）。feedback-*/失敗 atom 物理居 `_AIDocs/Failures/`、local 範疇 atom 居 `_AIDocs/_atoms/`（索引仍在此單一來源） | hook auto + atom_write |
| `lib/` | atom 規則/IO 單一源（`atom_spec` / `atom_locations` / `atom_io` / `atom_access` + `verify/`） | 手寫 |
| `hooks/` | Hook 腳本（`workflow-guardian.py` + `wg_*.py` + `wisdom_engine.py` + `handlers/` + lib） | 手寫 |
| `skills/` | V5 全域 skills（2026-05-27 取代 `commands/`） | 手寫 |
| `tools/` `scripts/` | 工具腳本 / 一次性遷移（含 `workflow-guardian-mcp/` server.js + world.html） | 手寫 |
| `workflow/` | Guardian runtime 狀態 + `config.json`（多數 gitignore） | hook |
| `_AIDocs/` | 長期參考知識（`Architecture` / `SPEC_*` / `DevHistory/` 演進史 / `Failures/` 失敗 atom / `_atoms/` local 範疇 atom） | 手寫 + auto-roll |
| `plans/` | 進行中規劃；完成搬 `_AIDocs/DevHistory/` | 手寫 |
| `prompts/` `templates/` | Prompt / atom 模板（`templates/icld-sprint-template.md` 由 workflow-icld atom 引用） | 手寫 |
| `plugins/` | Claude Code plugin（MR 安裝） | 手寫 |
| `journals/` `Logs/` | 工作日誌 / 執行日誌 | hook |
| `projects/` | per-project session jsonl + 專案層記憶 | Claude Code |
| `sessions/` `session-env/` `file-history/` `cache/` `ide/` `shell-snapshots/` `backups/` | Claude Code 內部狀態 | 系統 |

## 結構性規則
- always-loaded 入口聖域：不放後設、版本沿革、hook 常數
- 記憶分層：global / shared / role / personal/{user}；範疇 core（`memory/`，全專案注入）vs local（`_AIDocs/_atoms/`，只在 ~/.claude 注入）
- 規劃 vs 知識：`plans/` 短期；完成搬 `_AIDocs/DevHistory/{topic}/`
- 子目錄詳細：`hooks/` → `Architecture.md`；`memory/`+realm → `SPEC_ATOM_V5.md`

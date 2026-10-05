---
task_slug: memory-search
session_id: d892b7c9-9c98-47fc-ae48-747e217bd73f
created_at: 2026-10-01
source: multifile
status: done
---
## 目標
任何 MCP 客戶端（Codex／Cursor）或命令列一句話查到記憶，結果是穩定 JSON（`schema_version=1`），走與 hook 注入同一條檢索管線、scope 可見性同一套收窄。SoT：`lib/memory_search.py`；契約說明 TECH §5.8。

## 必須發生
- `wg_atoms.build_candidate_pool(cwd, user, roles, *, org_root=, global_atoms=)` 純函式（不註冊專案、不建目錄、不寫檔），SessionStart 改呼叫它且既有守門字面行（`global_atoms = parse_memory_index(MEMORY_DIR)`、`project_mem_dir`／`v4_user` 變數名）保留 → `verify_memory_search.py::test_build_candidate_pool_matches_old_inline`（V4／V3／無專案／無身份四案）、`test_build_candidate_pool_is_side_effect_free`、`test_session_start_keeps_guard_literals_and_calls_pool`
- `search()` 回傳含 `schema_version`、`mode`、`warnings`、每筆 `author／audience／tags／status` 四欄 → `test_contract_fields`
- 已知 trigger 命中已知 atom、分數遞減；`fusion:"legacy"` 分支也有分數；BM25 對整池（含專案層）跑 → `test_trigger_hits_known_atom_scores_descend`、`test_legacy_fusion_has_scores`、`test_bm25_runs_over_project_layer_too`
- 他人 personal 不出現；`user="unknown"` 不出現任何 personal；`roles=None` 不讀 role 層 → `test_other_personal_never_appears`、`test_unknown_user_sees_no_personal`、`test_roles_none_sees_no_role_layer`
- `use_vector=False` 不建 `vector_rekick.marker`、`mode` 不含 vector → `test_no_vector_does_not_touch_rekick_marker`、`test_vector_mode_label_and_top_k`
- 同名跨層取 project，被遮蔽者進 `warnings`；同一實體檔從兩層看到不警告 → `test_same_name_project_wins_with_warning`、`test_same_file_through_two_layers_is_silent`
- 三入口：`atom_io_cli` action `search` 走通（`test_cli_search_action`）；MCP tools/list 為 8 個且 `memory_search` 真查回表格標頭／`schema_version`、空 query 拒收（`smoke_mcp_stdio.js`）；`tools/memory-search.py` 表格有標頭（`test_format_table_has_header`）
- `settings.json` permissions.allow 含 `mcp__workflow-guardian__memory_search`

## 禁止發生
- 不加 receipt、不寫 state（唯讀工具）
- 不進 PostToolUse matcher
- 不改既有 `verify_scope_visibility.py`、`verify_vcs_sync_worker.py` 的守門字面行

## 驗證指令
- python -m pytest lib/verify/verify_memory_search.py -q
- node tools/workflow-guardian-mcp/verify/smoke_mcp_stdio.js（需重啟 MCP 後實測 `memory_search` 出現在 Claude Code tools/list）
- python tools/memory-search.py "git commit 前要看 diff" --no-vector --json

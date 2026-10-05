---
task_slug: org-layer
session_id: d892b7c9-9c98-47fc-ae48-747e217bd73f
created_at: 2026-10-01
source: multifile
status: done
---
## 目標
公司記憶 repo 一次設定，所有專案看得到、能寫。設計核心：org＝「一個被所有專案看得到的專案記憶目錄」，走專案層既有機制，py 寫入端零改；`org` 只是 MCP／CLI 語法糖（檔內仍 `Scope: shared`）。順手修向量增量索引靜默覆寫。SoT：`wg_core.org_memory_root()`／`realm.orgMemoryRoot()`；TECH §4.4。

## 必須發生
- config `org_memory: {enabled, roots:[{id, root}]}`；程式只讀 `roots[0]`，長度 >1 → 拒絕並 stderr、停用 org（不靜默）→ `hooks/verify/verify_org_layer.py::test_org_memory_root_rejects_multiple_roots`
- 候選池：任意 cwd 池含 org 組；`project_root == org_root` 不重複；未設 org 池不變；org 下 personal 不洩漏 → `test_pool_has_org_group_and_no_duplicate_when_cwd_is_org`、`test_pool_without_org_root_is_unchanged`、`test_org_personal_not_leaked`
- 讀取消費：`ups_search.collect_matched_atoms` 吃 `atom_index["org"]`（base=`org_base`）→ `test_ups_search_consumes_org_group`；向量層 `visible_vector_layers(extra_layers=)` 原樣附加、不傳清單不變 → `test_visible_vector_layers_extra_layers`
- 寫入：js `atom_write`／`atom_retire`／harvest items scope enum 加 `org`，改寫成 `scope=shared + project_cwd=org_root`；`dedupLayersFor("org")`＝global + `shared:<org slug>`；config 未啟用明確拒絕 → `test_js_org_sugar_mirrors_python`、`smoke_mcp_stdio.js`（scope=org dry_run 落 `<org_root>/.claude/memory/shared/`／未啟用拒絕）
- 同步：`collect_sync_targets` 含 org 根（已是當前專案根則不重複）→ `test_collect_sync_targets_includes_org_root`
- `tools/org-memory.py --init <root>`：建 `MEMORY.md`（含 atom-catalog）、`_atom_index.json`、`shared/`、`shared/_taxonomy.json`（Lv1「工具」）、`project-tree.json {"standalone": true}`、種一張工具卡 `shared/工具/org-memory.md`（索引非空，`sync-memory-index --check` 才能 exit 0）、寫 config、直接寫 registry；冪等 → `test_init_tree_then_sync_check_passes`、`test_init_registers_config_and_registry`
- SessionStart `[Org] 公司層 N 顆（<root>）`；根未 checkout／索引缺 → 警告一行；config 未啟用零 context
- `indexer.py` 增量寫入：只在 table 不存在時 `create_table`，其餘例外 stderr＋raise、不整表覆寫 → `tools/verify/verify_vector_service.py::test_write_records_incremental_error_does_not_overwrite`

## 禁止發生
- `org` 不進 `VALID_SCOPES`（py 零改）
- 不迴圈多根、不帶 library_id
- 候選池只認 config，不從 registry 推導
- 不對 org 跑 `_regenerate_role_filtered_memory_index`

## 已知可接受
- Dashboard 會把 org 當一個專案列出

## 驗證指令
- python -m pytest hooks/verify/verify_org_layer.py tools/verify/verify_vector_service.py -q
- node tools/workflow-guardian-mcp/verify/smoke_mcp_stdio.js
- 初始化（需使用者給公司記憶 repo 本機路徑）：python tools/org-memory.py --init <root>；之後開新 session 看 `[Org] 公司層 N 顆`

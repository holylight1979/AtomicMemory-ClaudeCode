# V4 專案自治層 + 三層 Scope + Role-filtered JIT

> 從 Architecture.md 移入（2026-04-17 索引化）。規範真相：`SPEC_ATOM_V4.md` §3, §4, §8。
> keywords: scope, personal, shared, role, global, project-registry, role-filter, JIT, vector layer

## 專案自治層

- **Project Registry**（`memory/project-registry.json`）：SessionStart 自動 `register_project(cwd)`，跨專案發現
- **路徑切換**：`get_project_memory_dir()` 新路徑 `{project_root}/.claude/memory/` 優先，舊路徑 fallback
- **專案 Delegate**：`{project_root}/.claude/hooks/project_hooks.py`（inject/extract/on_session_start），subprocess 隔離呼叫（5s timeout）
- **遷移工具**：`tools/migrate-v221.py`（_AIAtoms + 個人 memory → .claude/memory/）

## V4 三層 Scope + Role-filtered JIT

- **三層 scope**（per project）：`shared/` / `roles/{r}/` / `personal/{user}/`，加 `global`（`~/.claude/memory/`）共四層
- **SessionStart 流程**：`get_current_user()` → `bootstrap_personal_dir()`（冪等建 `personal/{user}/role.md` + `.gitignore`）→ `load_user_role()`（多角色逗號分隔）→ `is_management()`（雙向認證：personal `role.md` 宣告 + shared `_roles.md` 白名單）→ 寫入 `state["user_identity"]`
- **atom_index 載入**：V4 layout 偵測（shared/roles/personal 任一存在）→ 直接用 `_collect_v4_role_atoms` 結果（避免 V3 MEMORY.md 自我循環）；非 V4 → V3 MEMORY.md/_ATOM_INDEX.md fallback + V4 entries union
- **動態 MEMORY.md**：`_regenerate_role_filtered_memory_index` 寫 `<!-- AUTO-GENERATED: V4 role filter -->` header；護寫保護：檔案存在且首行不是 header → 跳過（不覆寫 V3 人手版本）
- **JIT vector filter**（SPEC §8.1）：UPS 從 `state["user_identity"]` 取 user/roles，呼叫 `_semantic_search(user, roles)`；vector service 端 `_build_v4_layer_clause` 組 `(layer = 'global' OR layer LIKE 'shared:%' OR layer LIKE 'role:%:r1' OR ... OR layer LIKE 'personal:%:user')`，sanitize `[\w-]+` 防注入；管理職 → 不傳 user/roles → 全量
- **Vector layer schema**：indexer 把 project 拆 `shared:{slug}` / `role:{slug}:{r}` / `personal:{slug}:{user}` 三類；`flat-legacy` kind 處理 mem_dir 直下舊 atom（視為 shared）；chunk metadata 新增 `Scope`/`Audience`/`Author` 三欄
- **管理職額外**：`_count_pending_review` 計 `shared/_pending_review/*.md` → context line `[Pending Review] N 件`

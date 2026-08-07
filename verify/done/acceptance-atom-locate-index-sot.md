---
task_slug: atom-locate-index-sot
session_id: 31e28020-e2bc-40e7-bbae-57adb25db9f3
created_at: 2026-08-07
source: plan
status: done
---
> 自核 2026-08-07：必須發生 12/12 全過（lib/verify 145 綠：verify_atom_locate_scope 17 +
> verify_conflict_write_gate 7 + 既有 121 含更新後 edit_metadata 守門；js stdio 端到端 7 情境全過；
> conflict-review list/approve 端到端過；全域 validate_index=[] / scope_drift=0）。
> 禁止發生 4/4 未違反（扁平相容/role-personal 窄根/敏感 audience 優先於 subdir 皆有測試釘住；
> js 定位仍 spawn py locate 單一來源）。js 改動待 MCP server 重啟生效。
## 必須發生
- 已搬到 memory/projects/<X>/ 的 atom，atom_write mode=replace / append 直接命中（索引 path 優先），不再回 Atom not found
- locate 索引命中防護細化為段層級（skip 段 / _archive*），兄弟目錄不被 _is_under 誤殺；_LOCATE_SKIP_DIRS 加 roles
- write_index 不再硬編 scope="global"：明給用之、None 沿用既有條目、新條目才預設 global
- atom-move move/reconcile 預設沿用索引 scope（含 cross-root），新增 --scope 明確覆寫，scope_changed 據實回報
- atom_write 新增 subdir（僅 scope=shared；相對 memory root；僅影響 create 落點）；非法段（../、_ 前綴、personal/roles/skip 段）拒絕
- create 撞名防叉：slug 已存在於子夾時 create 拒絕並提示現址
- MCP schema（mcp.js）同步：atom_write.subdir、atom_move.scope
- 回歸驗證新增並全綠：projects 子夾 replace/append、move 前後 scope 不變（含中夾 replace 的髒污鏈）、subdir 落點與拒絕、無 subdir 扁平相容
- 文件同步：_AIDocs/_CHANGELOG.md、相關 atom 知識更新
- （症狀5）trigger >30 字元在 atom_write 當下即拒絕（py+js 入口雙檢；append 不動既有 triggers 不受影響），不再留到 atom_move validate_index 才爆
- （症狀6）atom_edit_meta 支援專案層 atom：index root 以「上溯最近 _atom_index.json」定位，不再硬編 ~/.claude
- （症狀4，第二階段）衝突偵測：contradict 需複驗一致才 block、不穩定降級 warn；比對納入專案分區；_pending_review 草稿有可用的核准/退回流程

## 禁止發生
- 既有 memory/shared/ 與 memory/global/ 扁平佈局行為改變（無 subdir 落點、global 路由、Failures/_atoms 路由不動）
- role/personal 跨使用者/跨角色保護被放寬（維持窄根）
- 敏感 audience → _pending_review 路由被 subdir 繞過
- js 端另建第二套定位邏輯（定位規則仍 py 單一來源）

## 驗證指令
- python lib/verify/verify_atom_subdir_locate.py（既有守門）
- python lib/verify/verify_atom_locate_scope.py（本次新增回歸：三情境 + 相容案例）
- python -c "from lib.atom_index_json import validate_index; from pathlib import Path; print(validate_index(Path.home()/'.claude'/'memory'))" → []
- python tools/sync-atom-index.py（scope_drift 為零）
- stdio JSON-RPC 直驅新 spawn 的 server.js 重放三情境（js 端到端，不動本 session server）

---
task_slug: identity-roles-deciders
session_id: d892b7c9-9c98-47fc-ae48-747e217bd73f
created_at: 2026-10-01
source: multifile
status: done
---
## 目標
身份與職能自動來自 AD，什麼都不用填；待審草稿人人可裁決、人人看得到；管理職概念拿掉，改一個設定鍵 `review.deciders`（空＝全員）。SoT：`hooks/wg_roles.py`；契約 TECH §13.1、SPEC §2「身份與職能解析」。

## 必須發生
- 身份 fallback 為 `unknown`（`wg_roles._DEFAULT_USER`、`handlers/_shared.py`），`entry_visible` 對 `unknown` 不開任何 personal → `hooks/verify/verify_roles_from_file.py::test_default_user_is_unknown_and_unknown_sees_no_personal`
- 職能三層 `load_user_role(cwd, user)`：
  - `role.md` 缺／單角色／多角色；專案層優先、全域 fallback；空檔落到下一層 → `test_role_md_missing_and_ad_unavailable_gives_empty`、`test_role_md_single_role`、`test_role_md_multi_role_and_global_fallback`、`test_role_md_empty_file_falls_through_to_ad`
  - AD 群組（stub `whoami` csv，不真跑）：`PJA146_TSLG_02_核心程式` → programmer 且 `roles/programmer/` atom 進池；`_美術` → art；無匹配 → roles 空、role atom 不進池；whoami 失敗 → `[]` 且 stderr 一行；`> Project-Code:` 只取該專案群組；行程內只查一次 → `test_ad_core_programmer_group_maps_and_enters_pool`、`test_ad_art_group_maps_to_art`、`test_ad_no_matching_group_gives_empty_and_no_role_atoms`、`test_ad_whoami_failure_gives_empty_and_stderr`、`test_ad_project_code_filters_to_declared_project`、`test_ad_query_cached_once_per_process`
  - `map_groups_to_roles` 先比長鍵、去重保序 → `test_map_groups_longest_key_first_and_dedupe`
  - 都沒有 → `[]`，**不預設 programmer**；`session_start.py` 的 `or ["programmer"]` 拿掉 → `test_load_user_role_when_pool_builder_consumes_it`
- 裁決：deciders 空 → True；非空不含 → False；含 → True；config 壞 → True 且 stderr；無參呼叫相容 → `test_deciders_empty_everyone_can_decide`、`test_deciders_nonempty_gates_by_user`、`test_config_broken_fails_open_with_stderr`
- `[Pending Review] N 件` 不再受 `v4_mgmt` 限制（全員顯示）
- `tools/init-roles.py --me <roles>` 寫 role.md（冪等）、`--status` 印三層各自解析到什麼＋deciders；`--promote-mgmt` 與「Management 白名單」區塊刪除；`conflict-review.py` 拒絕 hint 指向 config
- 既有 `verify_project_layer_smoke.py`（monkeypatch is_management）、`verify_scope_visibility.py` 全綠

## 禁止發生
- 不做 SSO／RBAC／簽章、不建成員表、不做 `can_review(actor,target,action)` 政策層
- 不預設 programmer（查不到職能不得擴大 role 層可見範圍）
- 同事機器 getuser 失敗不得冒名（unknown 不讀 personal）

## 驗證指令
- python -m pytest hooks/verify/verify_roles_from_file.py tools/verify/verify_project_layer_smoke.py hooks/verify/verify_scope_visibility.py -q
- python tools/init-roles.py --project-cwd <專案根> --status
- 例外覆寫：python tools/init-roles.py --project-cwd <專案根> --me art

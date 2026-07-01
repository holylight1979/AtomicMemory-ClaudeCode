# skills/_archived — 休眠 skill（保回滾，非刪）

> `_` 前綴 → 不被 `tools/skill-index.py`（`skills/*/SKILL.md` 單層掃描）計入，
> 亦不被 Claude Code 自動發現（skill 發現源＝ `skills/<name>/SKILL.md` 單層）。
> 檔案原封保留，隨時可還原。

## 為何休眠

單人單機環境（見 `USER.md`）下「多人團隊層」機制全機空轉（roster/pending queue 恆 0 佇列）。
`hooks/wg_roles.py` 已降為單人 hardcode shim（`is_management()` 恆真、roster = 單一使用者），
其周邊依賴多職務治理的 skill 失去實際場景，故降 dormant。

## 已休眠清單

| skill | 原用途 | 依賴 |
|---|---|---|
| `init-roles` | 專案多職務模式啟用引導（建 shared/roles/personal 三層 + roster + post-merge hook） | `tools/init-roles.py`、`wg_roles` |
| `conflict-review` | 管理職裁決 pending queue（approve/reject 敏感 atom） | `tools/conflict-review.py`、`wg_roles.is_management`（雙向認證） |

後端 `tools/init-roles.py` / `tools/conflict-review.py` 仍留在 `tools/`（未動），一併作為回滾基座。

> 註：`heal-review` **未**休眠——它有 world-dashboard `/api/heal` 消費者，對單人有效；
> 其 `is_management()` 閘走 `wg_roles` 誠實 shim（恆真），單人永不被擋，非假閘。

## 如何還原（回多人協作時）

1. `git mv skills/_archived/<name> skills/<name>`
2. 還原 `hooks/wg_roles.py` 的多人雙向認證：見 `_AIDocs/DevHistory/v4-archive/wg_roles.py`
3. `python tools/skill-index.py --write`（重生 `_skill_index.json` + 同步各文件 skill-count marker）

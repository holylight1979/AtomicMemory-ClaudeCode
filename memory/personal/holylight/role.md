# Role Declaration

> **單人環境休眠**：本檔屬「多職務共享記憶」三層樣板（shared / roles / personal）的 personal 層。
> 單人單機下 `hooks/wg_roles.py` 以單人 shim 恆定接管角色（`programmer` + `management` 恆真），
> **下方 Role / Management 宣告不被讀取**。它僅在 `/init-roles` 啟用多職務模式時才生效
> ——該 skill 現已休眠於 `skills/_archived/`，回多人協作時還原。保留供未來回滾，勿刪。

- User: holylight
- Role: programmer
- Management: false

> （多職務啟用後）請依實際職務修改 Role（programmer / art / planner / pm / qa / management，
> 逗號分隔多值）。Management 需另在 shared `_roles.md` 白名單登記才生效。

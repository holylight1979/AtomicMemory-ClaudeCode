## 2026-10-27 定位與立樹先提示後擋（LOCATE_HINT_ON_FIRST_READ）

- `hooks/wg_overview.py`：`on_read` 讀檔時注入導讀卡的部位，第一次讀到它的程式檔那則讀檔結果（PostToolUse）附一行（`_locate_read_hint`／`locate_read_hint`）：沒目標樹就先 need_goal set、交定位四行（根因層兩候選＋理由、批判先下判斷；need_goal 關＝三行）、寫在比改檔早一則的回覆文字或不寫檔指令的 `#` 註解、thinking 讀不到；立樹與定位併成同一行。一部位一 session 一次（部位紀錄 `locate_hint`），第二個部位起只點名「格式同前」；改檔時才補注入、已交過定位、非程式檔、子代理讀的、OverviewHub 或 v6 關著不送。`on_edit` 判定與擋訊息不動。
- `hooks/wg_need_goal.py`：`edit_gate` 的適用判式抽成 `_edit_gate_applies`（行為不變），新增 `tree_owed_for_edit` 給讀檔提示用同一支判式。
- `hooks/wg_release_rules.py` 檔尾登錄 LOCATE_HINT_ON_FIRST_READ；案例 `hooks/verify/verify_locate_hint.py`（走真的 PostToolUse／PreToolUse：提示在第一個 Edit 之前那則讀檔結果、照做不擋、沒照做照擋、非程式檔／第二次讀／已交定位／改檔先注入／子代理不送、v6 與 OverviewHub 關時不變、need_goal 關＝三行），`verify_release_rules.py` 檔尾對照。
- TECH.md §7.6 寫入閘、§7.7 改程式前、§7.8 加列。
- 量測：`_AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/v6.0的代價-定位先提示-實測/locate_hint_replay.py`（＋`locate_hint_worker.py`、`-輸出.md`）：004 R1／R2 第一回合事件帳在 f5b30c9e／f45be4ea／分支三版重播，當時版逐字對上 transcript（27/27、28/28）；分支判定與擋訊息同 main；提示都出在第一個改檔之前；AI 照提示做（推論）時被擋重做那段每跑 4 次呼叫不發生，第一回合省 36.5 萬／44.2 萬 token、擋 8／7 次 → 0。

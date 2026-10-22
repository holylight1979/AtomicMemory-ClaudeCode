## 2026-10-22 連鎖斷路器：閘擋了 AI 修、修了又被擋，就停下來交使用者決定
- **AI 寫程式時會看到的**（守門總開關 v6 開才有；出廠 `workflow/config.json` 的 `chain_breaker.enabled` 寫開，設定裡沒寫這段＝不開；v6 關時以總開關為準、整個不跑）：
  - 同一個使用者回合裡，閘擋下或記欠 → AI 動手 → 又被擋，記成一條連鎖；**深度 2**（閘→修→閘→修→第三次閘）或**同一道閘第 2 次而且兩次之間 AI 有動手**就中止。原樣重試、只改寫回覆就又撞同一道閘，不算連鎖，交回那道閘自己的擋次上限。
  - 中止之後（能互動的 session）：這一回合其餘閘只記錄不擋；讀與問以外的工具先停手（Read／Grep／Glob、唯讀指令、AskUserQuestion 照放）；收尾擋一次，送連鎖過程表（第幾步、哪道閘、擋了什麼、AI 接著改了哪些檔幾行、只改註解有標、每步耗時、總共連鎖幾次深度多少），要 AI 用 AskUserQuestion 問三選一：「還原連鎖改動（不符本批目標）」「信任後續 AI 審查，繼續」「放行這一回合」。
  - 還原：只還原連鎖那一段（改檔前那一刻存的快照寫回、連鎖中新建的檔刪掉、寫回後重讀比對），連鎖前的改動不動；被別處改過的檔不覆寫、列出來。繼續：額度重給，再超再問。放行：這一回合其餘閘只記錄，紅測、對帳這些既有閘也照它們的放行規則記成使用者放行。
  - headless／SDK 與子代理沒人能答：不問、不停手，其餘閘只記錄，AI 照常把工作做完；收尾擋一次要 AI 把經過表寫進收尾報告；不還原也不繼續。
  - 中止中被改成只記錄的閘不留「本回合擋過」標記（拐彎判斷、寫碼查核自己出錯的標記放回原值），選繼續之後照常擋。
  - 沒有連鎖時（擋一次、修一次、過）各閘的輸出一字不變，連子行程呼叫也不變。
- **改了什麼**（軌 track-chain-breaker 第二段：接線）：`hooks/handlers/stop.py`（各閘之前 `chain_store.on_stop`；17 處擋或記欠之前 `_chain_hold`，紅測與等值證法在各自函式的預算之前問；子代理收尾；「後面還會擋」預覽回報閘名；`_unmark` 放回標記；收尾出口附三選一結果；預覽裡問 git 的部分一次收尾只問一次）、`hooks/handlers/pre_tool_use.py`（開頭停手 `_chain_halt`、`_deny` 記觸發與只記錄放行、放行出口存快照）、`hooks/handlers/post_tool_use.py`（成功與失敗的工具呼叫記 AI 動作 `_chain_action`）、`hooks/handlers/session_end.py`（`chain_store.session_cleanup`：這個 session 的快照、7 天沒動的別 session 快照與連鎖帳）、`workflow/config.json` 新增 `chain_breaker` 段、`.gitignore` 加 `workflow/chain-snap/`。`hooks/wg_chain.py` 加規則 CHAIN_GATE_NAME、CHAIN_ACTION_FACTS、CHAIN_SAME_GATE_NO_ACTION，`readonly_shell`、`action_of`、`gate_name`、`same_count`；警報後只記錄的不算進次數與深度、同一道閘只記一筆；沒人能答的不停手。`lib/chain_store.py` v6 總開關擋在 `_ctx`，pytest 底下每案各用一份帳與快照。settings.json 要補 PreToolUse 的 MCP 寫入工具 matcher 與 PostToolUseFailure 註冊（另以 patch 合入）。
- **驗證**：`hooks/verify/verify_chain_breaker.py`、新檔 `hooks/verify/verify_chain_wiring.py`（走真的 Stop／PreToolUse／PostToolUse／SessionEnd 入口），pytest 與直接跑尾行哨兵；handler 與模組換回改前版本跑紅案例紅在斷言、反例綠；改到的 handler 被引用的既有案例照跑；無頭實跑一題（`claude -p`，hook 指到工作樹、資料根放暫存）。

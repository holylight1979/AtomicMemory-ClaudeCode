## 2026-10-22 連鎖斷路器：閘擋了 AI 修、修了又被擋，第二次就停下來交使用者決定
- **AI 寫程式時會看到的**（守門總開關 v6 開、出廠 `workflow/config.json` 的 `chain_breaker.enabled` 寫開；設定裡沒寫這段＝不開）：
  - 同一個使用者回合裡，閘擋下或記欠 → AI 動手 → 又被擋，記成一條連鎖；**深度 2**（閘→修→閘→修→第三次閘）或**同一道閘第 2 次**就中止。
  - 中止之後：這一回合其餘閘只記錄不擋；讀與問以外的工具先停手（Read／Grep／Glob、唯讀指令、AskUserQuestion 照放）；收尾擋一次，送連鎖過程表（第幾步、哪道閘、擋了什麼、AI 接著改了哪些檔幾行、只改註解有標、每步耗時、總共連鎖幾次深度多少），要 AI 用 AskUserQuestion 問三選一：「還原連鎖改動（不符本批目標）」「信任後續 AI 審查，繼續」「放行這一回合」。
  - 還原：只還原連鎖那一段（改檔前那一刻存的快照寫回、連鎖中新建的檔刪掉、寫回後重讀比對），連鎖前的改動不動；被別處改過的檔不覆寫、列出來。繼續：額度重給，再超再問。放行：這一回合其餘閘只記錄，紅測、對帳這些既有閘也照它們的放行規則記成使用者放行。
  - headless／SDK 與子代理沒人能答：只中止留帳、不還原也不繼續，AI 把經過表寫進收尾報告。
  - 沒有連鎖時（擋一次、修一次、過）各閘的輸出一字不變。
- **改了什麼**（軌 track-chain-breaker 第二段：接線）：`hooks/handlers/stop.py`（各閘之前 `chain_store.on_stop`；17 處擋或記欠之前 `_chain_hold`，紅測與等值證法在各自函式的預算之前問；子代理收尾；「後面還會擋」預覽帶閘名給斷路器、`_piggyback` 重用同一份；收尾出口附答案結果）、`hooks/handlers/pre_tool_use.py`（開頭停手 `_chain_halt`、`_deny` 記觸發與只記錄放行、放行出口存快照）、`hooks/handlers/post_tool_use.py`（成功與失敗的工具呼叫記 AI 動作 `_chain_action`）、`hooks/handlers/session_end.py`（清快照）、`workflow/config.json` 新增 `chain_breaker` 段、`.gitignore` 加 `workflow/chain-snap/`。`hooks/wg_chain.py` 加規則 CHAIN_GATE_NAME、CHAIN_ACTION_FACTS，`readonly_shell`、`action_of`、`gate_name`；警報後只記錄的不算進次數與深度、同一道閘只記一筆；`lib/chain_store.py` 加 `drop_snapshots`，pytest 底下每案各用一份帳。
- **設定**：`chain_breaker` 段沒寫 `enabled`＝不開；各閘自己的案例只帶部分設定，照各閘原本的擋次與放行測。中止中被改成只記錄的閘，閘函式先記下的「本回合擋過」標記（拐彎判斷、寫碼查核自己出錯）放回原值；停手時的唯讀指令白名單收緊（sed 只認 `-n` 一段印行、sort 黏著 `-o`、rg／sort 叫外部程式、git `-c`／`--ext-diff`／`-O`、PowerShell 括號一律當動手）。
- **驗證**：`hooks/verify/verify_chain_breaker.py`（105）、新檔 `hooks/verify/verify_chain_wiring.py`（12，走真的 Stop／PreToolUse／PostToolUse／SessionEnd 入口），pytest 與直接跑尾行哨兵；三支 handler 換回接線前跑 9 案紅在斷言、反例綠；標記放回的 2 案拿掉修正跑紅；改到的 handler 被引用的既有案例 36 支照跑；無頭實跑一題（`claude -p`，hook 指到工作樹、資料根放暫存）。

## 2026-10-27 導讀卡第一次碰到時只送病灶一句＋卡路徑，改那塊之前自己 Read
- **AI 寫程式時會看到的**（守門總開關 v6 開時）：
  - **第一次碰到部位不再整張塞導讀卡**（設定 `overview_hub.card_injection`，預設 `pointer`；`lib/overview_hub.build_injection_ex(pointer=True)`、`_pointer_body`）：定位要求照送，卡的部分只剩兩行——卡上「已知病灶」第一條（截 160 字）與卡路徑，寫明「改這個部位的檔之前先 Read，可跟讀部位檔同一則送」。目標改了之後的目標視角重送也照這個送法。沒有卡的部位兩種送法逐字相同。
  - **改那塊之前要 Read 過卡**（`hooks/wg_overview._unread_cards`）：指標制送卡的部位，本 session 沒讀過表上每張卡就照定位閘的方式擋，跟其他缺件列在同一則擋訊息、附卡路徑；讀卡記在讀檔帳（同讀檔證據），改檔 log 記 `card_mode`、`card_unread`。知識類部位原本只要「卡已注入」，指標制另要 Read 過卡（`deny_reason=card_unread`），一樣走擋次上限與同批短訊息（擋的出口抽成 `_locate_deny`，程式部位與知識部位共用）。
  - **接縫**：`card_injection: "full"` 回到整張注入（原程式原處不動），不要求 Read 卡；值只收 `pointer`／`full`，寫錯是設定錯誤（`lib/hub_config.validate_hub_cfg`）。v6 總開關關時一律 `full`（`wg_overview._cfg` 算出 `_card_mode`），行為跟以前一樣。升級前注入、沒有 `card_mode` 的舊紀錄照整張算，不追要讀卡。
- **省多少**（事件帳重播，`card_pointer_replay` 量法見交付）：004 那題（qb2-sales）三個部位表上都沒有卡，五跑第一回合 72 個 OverviewHub 事件重播，注入 10/10 逐字相同、改檔 62/62 擋法相同 → 這題省 0 token、0 次擋、0 秒。有卡的部位（根層 6 個 code 部位，feature 意圖）：整張注入平均 2,892 token、指標 522；碰了沒改的部位照 004 R1 的位置被重讀 20 次，每個省約 4.7 萬；改了的部位要 Read 卡（平均 2,451）約打平（每個 +0.08 萬），前提是讀卡跟別的讀檔同一則送。
- **驗證**：新案例 `hooks/verify/verify_overview_card_pointer.py` 11 支；拿 main 5ccf44d2 回放 9 紅、2 綠（綠的是「v6 關行為不變」「沒卡部位兩模式相同」兩支不變式）。既有案例裡斷言整張卡內容的改成明設 `card_injection: full`（測的是整張注入本身）。
- **已知限制**：讀卡只認本 session 讀檔帳裡的路徑（`_session_reads`）；本 session 還沒注入任何部位前讀的卡、而那張卡本身落在部位表某個部位裡時，那次讀不進讀檔帳，要再讀一次。卡路徑在根層 worktree 指 live 的 `memory/`（`card_mem_dir`，跟整張注入讀的同一份）。改了的部位省不省看 AI 有沒有把讀卡併進同一則：沒併就多一次呼叫（004 平均每次約 7 萬 token），比整張注入貴。

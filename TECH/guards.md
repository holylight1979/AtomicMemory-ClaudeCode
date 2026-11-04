# 寫碼守門：細節（乙篇附錄）

[↑ 乙篇](coding-guard.md)

[乙篇：寫碼守門](coding-guard.md) 的細節。每一節開頭有「↑」連回乙篇對應的一節（A7.1 ↔ [乙3](coding-guard.md#乙3-收尾閘序守門開時與收據)）。規則全表另在 [TECH/release-rules.md](release-rules.md)。

- 本檔寫的都是**守門開時**的行為。開關也會改到記憶系統的地方 → [跨層表](../TECH.md#守門開關會改到記憶系統的地方)。
- 不看守門開關的閘（基本守門）細節已搬到 [TECH A7](../TECH.md#a7-基本守門細節)。原位只留標題與一行指標，舊連結才有落點。
- 各 `## A7.x` 標題沿用原字，錨點不變。

## A7 守門與收尾：開頭說明

[↑ 乙1](coding-guard.md#乙1-開關與減量原則)

### 守門總開關（完整）

- 設定鍵：[`workflow/config.json`](../workflow/config.json) 的 `coding_guard.enabled`，出廠開。
- 判法 `wg_core.v6_enabled`（[`hooks/wg_core.py`](../hooks/wg_core.py)），先到先贏：
  - 環境變數 `WG_CODING_GUARD=1` 開、`=0` 關；沒設才看舊名 `WG_V6`（同義）。
  - 設定：`coding_guard.enabled` 是 JSON 的 true 就開；不是再看舊鍵 `v6.enabled`，是 JSON 的 true 也開。
  - 只認 JSON 的 true：寫成字串、段不是物件，一律當關。
- 本機要開：設環境變數，或在不進版控的 `workflow/config.local.json` 寫 `{"coding_guard": {"enabled": true}}`。舊寫法 `{"v6": {"enabled": true}}` 照樣能開。
- 關著時本檔的守門全都不跑；清單見 [乙1〈開關改了什麼〉](coding-guard.md#開關改了什麼)。
- 開關也改到記憶系統 30 處行為（例：記憶系統的收尾閘守門關時擋、守門開時只提醒）→ [跨層表](../TECH.md#守門開關會改到記憶系統的地方)。
- 開著時，每回合的守門只在寫碼回合啟動（[CODING_TURN_ONLY](release-rules.md#coding_turn_only)，`wg_core.coding_turn`）：
  - hook 計時的 run 帳
  - 記憶系統的退避偵測、退縮閘、收尾檢核（跨層表 #22）
  - `coding_guard.coding_turn_only=false` 退回每回合都跑。
- 守門的模組用到才載：handler 頂端用 `lazy_module`（[`hooks/wg_lazy_re.py`](../hooks/wg_lazy_re.py)）宣告，第一次取它的屬性才執行模組。守門關時不載。
- 下面各表寫的是開著時的行為。

### 擋或提醒（完整）

- 判定與送法只讀 [`hooks/wg_release_rules.py`](../hooks/wg_release_rules.py) 的 `RULE_MODE`，呼叫端一律經 `gate_mode(rule, v6)` 問。
- 寫碼守門開著時，守門照擋的只有兩類：
  - 病形閘（SmellGate）。
  - 紅測閘與寫碼查核的 (a) 說修好要有綠收據。
  - `RULE_CLASS` 標病形／紅測的規則名。
- 其餘寫碼守門一律**提醒**：
  - 第一次提醒一行（規則名＋現象＋做法，`remind_line`）＋留帳。
  - 不擋、不讓對話續跑。
  - 同一條規則同一個對象同一個 session 只提醒一次（`remind_due`）。
- 提醒掛在前一個動作的工具結果上（PostToolUse），不掛 PreToolUse 的 additionalContext：
  - 收尾類的要求掛最後一次改程式檔那批的工具結果。
  - Stop 只留帳、不續跑、不開放行題。
  - 規則名 REMIND_ON_PRIOR_RESULT。
- 記憶系統的收尾閘（退縮歸屬、收割、同步、深度檢討…）守門開時也照本表改提醒（跨層表 #21）。
- 不屬寫碼守門的安全與權限邊界照擋（`RULE_CLASS` 標「不在範圍」）：
  - 版控口令
  - 隱私檔
  - 驗證批次
  - 記憶目錄寫入
  - 跨層寫入
  - svn 測試路徑
  - 裁判子 session 的收尾
  - `readonly_paths`：守門開時照擋；守門關時部位表整個不跑，不擋（跨層表 #36）。
- 表上沒登的規則名當照擋。
- 寫碼守門關時 `gate_mode` 一律回 block。
- 下面各表每道閘前面標的「照擋」「提醒」就是這張表的現況；標「照擋（不在範圍）」的是安全邊界。
- 下面各節寫的「擋滿 N 次、第 N+1 次放行」「Stop 回 additionalContext 讓對話續跑一回合」是照擋時的送法（寫碼守門關，或 `RULE_MODE` 把那條規則列成照擋）：
  - 寫碼守門開著時，判成提醒的規則在 Stop 只留帳，不續跑、不吃擋次（[STOP_REMIND_LEDGER_ONLY](release-rules.md#stop_remind_ledger_only)）。
  - 例：寫碼查核 (b)。程式裡照擋那條分支留著，`RULE_MODE` 改表就換送法。
  - 不屬寫碼守門的 [lang_guard](#lang_guard) 不讀本表：照舊在 Stop 回 additionalContext、續跑一回合。

## A7.0 寫程式時一路會遇到什麼（總覽）

[↑ 乙2](coding-guard.md#乙2-一路會遇到什麼)

照 AI 寫程式的先後順序，說每個時刻系統會問什麼、送什麼卡、擋什麼。

- 「擋」＝工具呼叫被拒（deny）或收尾被打回（block），AI 補完才能繼續。
- 「提醒」＝只多送一段文字、不擋。

### ① 開場（SessionStart）

- **系統做什麼**：
  - 列公司層與週健檢狀態。
- **擋不擋**：提醒。
- **見**：[TECH §3.1](../TECH.md#31-settingsjson-十一個事件)、[TECH §8](../TECH.md#8-可觀測與自我維護)。

### ② 收到需求（UserPromptSubmit）

- **系統做什麼**：
  - 注入相關記憶卡。
- **擋不擋**：不擋。
- **見**：[TECH §5](../TECH.md#5-檢索與注入每-prompt)。

### ③ 改檔當下（PreToolUse）

- **部位表唯讀路徑**：寫入目標命中這一層 `readonly_paths` 就擋（[OVERVIEW_READONLY_PATHS](release-rules.md#overview_readonly_paths)；守門關時部位表整個不跑，不擋）。
- **寫入目標判不出的指令**（例：`python -c` 內嵌碼裡開檔寫）放行並留帳。
- **擋不擋**：擋（`readonly_paths`）。
- **見**：[乙7](coding-guard.md#乙7-部位表與-depends-召回)。

### ④ 改完之後（PostToolUse）

- **系統做什麼**：
  - 記下改了哪些檔（收尾的寫碼查核看這份帳）。
  - 讀到某張卡 `Depends` 指著的檔，附一行「改它前先讀卡」，同卡一 session 一次（[Depends 召回](#depends-召回)）。
- **擋不擋**：提醒。
- **見**：[乙7](coding-guard.md#乙7-部位表與-depends-召回)。

### ⑤ 問使用者之前（AskUserQuestion）

- **系統做什麼**：
  - 每題要附推薦選項（缺了提醒）。
  - 問改法前先讀過題目提到的部位（只提醒）。
- **擋不擋**：提醒。
- **見**：[乙6](coding-guard.md#乙6-其他寫碼守門)、[問使用者附推薦](#問使用者附推薦askuserquestion)。

### ⑥ 跑測試

- **系統做什麼**：
  - 驗證程式印的**哨兵行**（`<名>_CHECK PASS／FAIL`、`<名> DONE k=v`）連同完整指令收成「收據」。
  - 紅了記紅測。
- **收據的限制**：
  - 收據不防偽造：不看指令形狀、不查指令裡寫的哨兵字樣。
  - 指令解析不了（heredoc、`$( )`…）只當一般證據，不算部位量尺與整體驗證。
- **擋不擋**：只記帳。
- **見**：[乙7](coding-guard.md#乙7-部位表與-depends-召回)、[收據列](#收據收據列)。

### ⑦ 宣告完成（Stop）

- **查核順序**：
  - 紅測沒修好不准說完成。
  - 寫碼查核：說修好要有改動之後的綠收據 (a)。
  - refactor／perf 要等值證法、答熱路徑。
  - 不准把可做的事推給下個 session。
  - 知識收割。
  - 清掉自己建的工作樹與暫存。
  - 同步提醒。
- **擋滿的處理**：寫碼查核擋滿不自己放行，改問使用者【收尾放行確認】；各閘預算與沒人能回答時怎麼放見 [擋次預算](#擋次預算完整)。紅測閘不看擋次預算、不問放行：紅測還在又宣告完成就擋（[TestFailGate](#testfailgate)）。
- **連鎖斷路器**：閘擋→修→又擋連成一串時，由連鎖斷路器中止、交使用者三選一（[乙8](coding-guard.md#乙8-連鎖斷路器)）。
- **擋不擋**：擋只紅測與 (a)；其餘提醒。
- **見**：[乙3](coding-guard.md#乙3-收尾閘序守門開時與收據)、[乙4](coding-guard.md#乙4-擋滿之後怎麼放行)。

### ⑧ 交付

- **系統做什麼**：
  - 收尾檢核報告（`anti_evasion_report`：本 session 目標、大原則方向、AI 自己做主三類，加系統帳）送 HUD 給人看。
- **擋不擋**：提醒。
- **見**：[TECH §7.2](../TECH.md#72-反退避anti-evasion)。

### ⑨ commit 與合併

- **口令**：要使用者下過口令（上GIT 等）。
  - 寫碼守門開時口令撐到這批 push 完或使用者打字開新回合。
- **隱私檔**：不准提交。
- **病形**：這次提交的程式不能新長出病形（巢狀過深、匿名函式過長…）。
- **worktree**：在 git worktree 裡不要求 push。
- **多 session 並行**：工作軌只 commit 在自己的分支，交付信交總控台合併。
- **擋不擋**：擋。口令、隱私屬安全邊界（不在範圍）；病形屬寫碼守門照擋的兩類。
- **見**：[乙6](coding-guard.md#乙6-其他寫碼守門)、[TECH §7.3](../TECH.md#73-commit-與驗證前的閘)、[TECH §7.1](../TECH.md#71-收尾閘序守門關時) 同步閘、[TECH §13.4](../TECH.md#134-多-session-協作雙總控台與工作軌)。

### 目前關著的閘（完整）

- **寫碼查核只擋 (a)**（`reconcile_gate.block_letters`，[`workflow/config.json`](../workflow/config.json)）：(b)(c)(v)(e) 照判、只印 stderr。
  - 拿掉這個鍵＝全部字母都進送法判斷。
- 收尾檢核報告（`aec.scan_report_gate`）、卡片表態（`atom_audit.enabled`）、svn 提交測試路徑閘（`overview_hub.svn_test_block.enabled`）屬基本守門 → [TECH A7](../TECH.md#a7-基本守門細節)。
- 下面各表寫的是閘開著時的完整行為。

## A7.1 Stop 閘序

[↑ 乙3](coding-guard.md#乙3-收尾閘序守門開時與收據)

入口：[`hooks/handlers/stop.py handle_stop`](../hooks/handlers/stop.py)。

- 一開頭（任何閘之前）問一次連鎖斷路器（[乙8](coding-guard.md#乙8-連鎖斷路器)）：中止中這一回合其餘閘只記錄不擋。
- 之後依序查（前者優先），順序見 [乙3](coding-guard.md#乙3-收尾閘序守門開時與收據)。
- 記憶系統的收尾閘（退縮歸屬、收割、收尾檢核、同步、卡片表態、深度檢討）標題留在下面，細節已搬到 [TECH A7](../TECH.md#a7-基本守門細節)。

### 擋次預算（完整）

- **共用一份**：退縮歸屬、AEC-Pending、Reload 建議、卡片表態與最底下的一般同步擋共用 `stop_gate_max_blocks` 2。
  - 第 3 次放行（放行時不另印訊息）。
  - 寫碼守門開時每個使用者回合重新計次；寫碼守門關時整個 session 累計（跨層表 #26）。
  - 守門開時這幾道都照 `RULE_MODE` 判成提醒、不吃預算；哪一條改回照擋才會吃。
  - 規則 [BLOCK_BUDGET_SHARED](release-rules.md#block_budget_shared)。
- **寫碼查核**（ReconcileGate (a)(b)(c)(v)）每個使用者回合一份 `reconcile_gate.max_blocks_per_turn`；紅測閘不看擋次預算。
- **等值閘**：等值沒證齊、熱路徑答了缺東西，吃寫碼查核那份預算；熱路徑沒答，每個使用者回合擋一次（[Equivalence](#equivalence等值與熱路徑g7)）。
- **擋滿只認使用者放行**（[乙4](coding-guard.md#乙4-擋滿之後怎麼放行)）；沒人能回答（headless／SDK、子代理、裁判）擋滿就放行並留帳。
- **閘自己判定出錯**：同一個錯誤每個使用者回合擋一次，之後放行並留帳（[GATE_SELF_ERROR](release-rules.md#gate_self_error)）。

### TestFailGate

- **條件**：
  - 最後一則宣告完成，且本 session 有未轉綠的失敗測試。
  - 寫碼守門開或關同一套（[TECH §7.1](../TECH.md#71-收尾閘序守門關時)）。
  - 只認本 session 的條目；子代理內的紅測不記主 session。
- **綠怎麼清紅**：
  - 綠只清它涵蓋的紅（[GREEN_CLEARS_ONLY_CASES_IT_RAN](release-rules.md#green_clears_only_cases_it_ran)）。
  - 綠點名整檔（沒 -k／-m）＝那檔裡紅掉的案例全跑到。
    - 路徑分隔、大小寫、./ 前綴、絕對路徑寫法不同也認得。
    - 跑到的記進那筆紅的 `cleared_units`。
- **紅的範圍怎麼存**（規則 [RED_SCOPE_FROM_FULL_COMMAND](release-rules.md#red_scope_from_full_command)，`post_tool_use._test_scope`）：
  - 存解析後的目標，不存只有前 200 字的 `cmd`。
  - 內容是每段測試子命令＋點名的檔、目錄、節點、-k 這類篩選，與它前面的換目錄（cd／pushd／Set-Location）。
  - 跟指令多長無關、不截斷。
  - 判綠涵不涵蓋、新的紅取不取代舊紅、是不是重跑同一組都用它。
  - 這次的指令也解析成同樣的形狀來比。
  - 不用 `cmd` 的原因：截在 `2>&1` 中間會剩一個 `2` 被當成目錄，什麼重跑都涵蓋不到。
  - 認不出測試子命令就判不出目標：不拿片段當路徑，只認原樣重跑或列得出名字的紅被跑到。
  - 判不出目標、綠了卻沒涵蓋，都留帳 `Logs/guard-testfail_scope.jsonl`。
- **模式**：**照擋**；不問 `RULE_MODE`，守門開或關都擋。
- **擋訊息**：
  - 抬頭「測試未綠：還有 N 支沒跑綠」，算支數不算筆數。
  - 真的有綠掉幾支才附「（M 支已綠）」。
  - 每筆只列還沒跑綠的那幾支（最多 3 支＋等 N 支；已清的絕不列）。
  - 附「重跑這幾支檔就夠：<那幾支所在的檔，去重>」。
  - 出路照三條原文：(a) 修復 (b) 明確說明為何不修並標記為已知 regression (c) 降級任務定義。
- **輸出沒列出是哪一支的紅**：
  - 擋訊息附「重跑這個範圍」：解析出的每段照抄照順序，別接 tail／head。
  - 判不出目標或長過 600 字就給「原指令完整照跑或跑整套」。
  - 綠了而且涵蓋就清掉；紅了照列出的那幾支記。
- **預算與放行**：不看擋次預算、沒有放行詢問；連鎖斷路器中止中也照擋。每擋一次把共用擋次的計數 `stop_blocked_count` 加一，紅測閘自己不比上限。
- **使用者叫跳過**：使用者說「先這樣／跳過」，UserPromptSubmit 整份清掉紅測清單（`handlers/ups_gates`）。
- **判的時點**：
  - 紅只在宣告完成的收尾才判。
  - 沒宣告完成的回合不判、也不算判過，紅照留到之後哪個回合宣告完成。
- **刻意紅不進紅測清單**（記紅那一刻判，守門開或關都跑）：
  - 負向對照：指令的 `#` 註解或三管道寫「負向對照｜<這條指令裡的字樣>：<理由>」（[NEGATIVE_CONTROL_DECLARED](release-rules.md#negative_control_declared)）。
  - 跑紅時本 session 改的程式檔退回舊版（[RED_WHILE_REVERTED](release-rules.md#red_while_revertedretry_counts_rerun_cyclesgreen_same_case_clears)）。
  - 兩種都記進 deliberate_reds 留痕。
- **同一條指令跑了不只一次測試**：紅在記帳時就定案（[RED_LAST_RESULT_IN_COMMAND](release-rules.md#red_last_result_in_command)）。

### ReconcileGate

- **目前只有 (a) 擋**：
  - `reconcile_gate.block_letters`：(b)(c)(v)(e) 照判、只印 stderr。
- **(a) 說修好**：看有沒有對得上改檔的 PASS。
  - 收據要晚於每個對上的改檔、同一棵樹、指令能當一般證據。
  - 不限本回合：舊回合的只要之後本 session 沒再改任何程式檔就算。
  - 子代理改的與判不出目標的寫入都算改；改過就要新的 PASS，擋訊息點名改了哪個檔。
  - 改檔所在部位也沒有合格的自寫收據。
- **(b) 說量了**：本回合沒有能當證據的 DONE，也沒有合格的自寫收據。
- **(c) 說試過**：本回合沒有任何 Bash／PowerShell 執行。
- **(v) 搬了含程式檔的目錄**：欠搬之後的路徑掃描與抽樣兩張收據（規則 [MOVE_CODE_DIR_NEEDS_SCAN_AND_SAMPLE](release-rules.md#move_code_dir_needs_scan_and_sample)）；跨回合，不看措辭。
- **案例檔的定義**（驗證批次閘數測試檔支數時用，`wg_verify_batch`）：
  - 符合 `verify_case_globs` 的程式檔（測試目錄或 test_／_test／.test／.spec 這類檔名，相對專案根比）。
  - 檔名剛好含 test 的產品檔不算。
- **不算改碼的改檔**（剔出 (a) 要對的改檔清單，Stop 的 stderr 印規則名）：
  - 改過又原樣還原：git 追蹤、git status 對它無輸出、本 session 第一次改它之後沒 commit（[NET_UNCHANGED](release-rules.md#net_unchanged)；例：反證暫改再 `git checkout` 還原）。
  - 只差註解、內容等於已提交版本、一次性 git 啟動器（COMMENT_ONLY_CHANGE、CONTENT_EQUALS_COMMITTED、LAUNCHER_NOT_CODE）。
  - 判不出來照算改了。
- **(e) 收尾報告欄**：AEC (j) 證據路徑缺或不存在、(k) 是空字串。
- **(a)(b)(c) 看什麼**：
  - 最後一句話（優先用 hook 輸入的 last_assistant_message，不套 30 字下限）。
  - 以及擋滿時記下的原宣稱（同一個使用者回合的續跑回合裡照查）。
  - 這時 (a) 認任一回合晚於改檔的合格 PASS（規則 [CARRIED_CLAIM_ANY_TURN_RECEIPT](release-rules.md#carried_claim_any_turn_receipt)）。
- **判定出錯**：同一個錯誤每個使用者回合擋一次，之後放行並留帳（[GATE_SELF_ERROR](release-rules.md#gate_self_error)）。
- **模式**：照擋只 (a)（紅測類）；其餘字母提醒。
- **預算**：
  - 紅測與寫碼查核（(a)(b)(c)(v)）共用每個使用者回合一份 `reconcile_gate.max_blocks_per_turn`（2，不分哪一條規則，[BLOCK_BUDGET_SHARED](release-rules.md#block_budget_shared)）。
- **擋滿的放行**：
  - 不自行放行：記 pending，要用 AskUserQuestion 照【收尾放行確認】問使用者。
  - pending 只在同一個使用者回合有效，使用者打字開新回合就失效、預算重給（[PENDING_SAME_USER_TURN](release-rules.md#pending_same_user_turnrelease_covers_shown_itemsnoninteractive_release_at_budget)）。
  - 使用者要在最後一次擋之後選放行，或打字「放行」，才放這一回合，並記 user_release（健檢列 red）。
  - 之後的回合只沿用擋訊息列過的那幾件（[RELEASE_COVERS_SHOWN_ITEMS](release-rules.md#pending_same_user_turnrelease_covers_shown_itemsnoninteractive_release_at_budget)，[乙4](coding-guard.md#乙4-擋滿之後怎麼放行)）。
  - 子代理、裁判、headless／SDK、背景 session（CLAUDE_JOB_DIR）沒有人能回答：擋滿就放行並留帳（[NONINTERACTIVE_RELEASE_AT_BUDGET](release-rules.md#pending_same_user_turnrelease_covers_shown_itemsnoninteractive_release_at_budget)）。
- **(e) 的送法**：目前不在 `block_letters`，照判、只印 stderr。
  - 拿掉 `block_letters` 時，寫碼守門開是提醒，只留帳。
  - 照擋時（`RULE_MODE` 把它列成照擋）屬記憶與報告類：不走放行詢問，擋滿後第 3 次放行並寫 guard-reconcile_overflow（健檢列 red）。

### Equivalence（等值與熱路徑，G7）

- **條件**：
  - 本回合意圖是 refactor 或 perf。
    - `state.turn_intent`，只由使用者本人打的字判（`harness_text.user_typed_text`）。
    - 同伴訊息、背景通知沿用上一個意圖。
  - 本回合改過程式檔。
  - 宣告完成。
- **開關**：`overview_hub.equivalence.enabled`（hub 設定，[`lib/hub_config.py`](../lib/hub_config.py)）。
- **規則與位置**：
  - 規則 [REFACTOR_NEEDS_EQUIVALENCE](release-rules.md#refactor_needs_equivalence)／[PERF_HOT_PATH_NEEDS_MEASURE](release-rules.md#perf_hot_path_needs_measure)（[乙9](coding-guard.md#乙9-規則全表)）。
  - 事實在 [`handlers/stop.py _equivalence_gate`](../hooks/handlers/stop.py)，排在寫碼查核（ReconcileGate）之後、Deferral 之前。
- **模式**：提醒。
- **refactor 要有**：
  - 最後一次改程式檔之後要有三筆 `PRESERVE_CHECK PASS` 收據。
    - 指令是 [`skills/behavior-preservation/scripts/preserve-check.py --mutation order／side_effect／boundary`](../skills/behavior-preservation/scripts/preserve-check.py) 各一次。
    - 一筆收據只算指令裡最後一個 --mutation。
  - 或收尾一行「等值證法｜不適用｜<理由>」。
- **refactor／perf 都要答熱路徑**：
  - 「熱路徑｜是｜<哪裡>」，加量測收據 `<NAME> DONE k=v`。
    - 要帶數字；pytest 統計行轉的 PYTEST_MEASURE 不算。
    - 或「量測｜不做｜<理由>」。
  - 或「熱路徑｜否｜<為什麼>」。
- **擋的處理**：
  - 等值沒證齊、熱路徑答了缺東西 → 吃寫碼查核的預算擋，擋滿問使用者（沒人能回答的擋滿放行留帳）。
  - 熱路徑沒答每個使用者回合擋一次。
- 留帳 `Logs/guard-equivalence.jsonl`。

### Evasion 偵測／DeferralGate
→ 已搬到 [TECH A7](../TECH.md#a7-基本守門細節)

### KnowledgeHarvest
→ 已搬到 [TECH A7](../TECH.md#a7-基本守門細節)

### Harvest-Pending
→ 已搬到 [TECH A7](../TECH.md#a7-基本守門細節)

### ScanReport
→ 已搬到 [TECH A7](../TECH.md#a7-基本守門細節)

### AEC-Pending
→ 已搬到 [TECH A7](../TECH.md#a7-基本守門細節)

### HUD fallback
→ 已搬到 [TECH A7](../TECH.md#a7-基本守門細節)

### Reload 建議（規則 RELOAD_ADVICE_ALREADY_LOADED）

- **條件**：
  - 收尾叫使用者 Reload Window，但每個活著的工具服務（MCP server）都已載入磁碟上最新的程式。
  - 本 session（含子代理）沒改過路徑含 [`tools/workflow-guardian-mcp/`](../tools/workflow-guardian-mcp/) 的檔就整個不判（[RELOAD_ADVICE_MCP_EDITS_ONLY](release-rules.md#reload_advice_already_loadedreload_advice_mcp_edits_only)）。
- **模式**：提醒。
- **動作**：
  - 擋一次：拿掉那句。
  - 真有程式以外的理由（改了 MCP 啟動設定、settings.json）就保留並加一行「重載原因：<哪個設定改了>」。
  - 每個使用者回合一次、吃共用預算。

### 同步閘（SyncReminder）
→ 已搬到 [TECH A7](../TECH.md#a7-基本守門細節)

### AtomAudit（卡片表態）
→ 已搬到 [TECH A7](../TECH.md#a7-基本守門細節)

### 驗收裁判（Stop 端）

- **形式**：獨立 hook `codex_companion.py`，寫碼守門開時才跑。
- **行為**：
  - Stop 只起背景審查、立即放行。
  - 結果在下一則使用者訊息附一行。
  - fail 且 severity ≥high 才附完整說明（[乙5](coding-guard.md#乙5-驗收裁判)）。
- **模式**：獨立 hook、不經 RULE_MODE；永不 block。
- 裁判逾時 → 下一則附「uncertain」。

### Deep Post-Mortem
→ 已搬到 [TECH A7](../TECH.md#a7-基本守門細節)

### 追蹤帳本（退縮閘的「追蹤｜…」行）

- **寫入端**：退縮閘那一問的答案，回覆裡的「追蹤｜<哪一件>：<現在不做的原因>」各記一筆（`stop._record_tracking_lines`）；守門開或關都記。
  - 帳本 `workflow/tracking/<slug>.jsonl`，一行一筆；行尾可帶「｜建議：…｜該誰解：…」另存兩欄；`[部位] 結案：<原文開頭至少 8 字>` 關掉一筆。
  - 收尾檢核報告的 (k) 不寫進來；目前沒有程式把帳本讀回來（開場不列）。
- **同一件不重記**（[TRACKING_SAME_ITEM_NOT_REWRITTEN](release-rules.md#tracking_same_item_not_rewritten)）：
  - 唯一寫入口 `append_tracking`。
  - 部位相同且原文相同 → 不重記（字面相近不併，併錯會吞掉一件）。
  - 換句話說的同一件，由 AI 在行尾寫「｜同追蹤項：<那筆裡連續至少 8 字>」：對到唯一一筆就換成新說法（supersedes＋結案成對）；對不到或多筆照記並 stderr。
  - 帳本只追加不改寫，中途斷掉最多多一筆重複，清理器照結案成對處理。

### 迴歸提示

- **條件**：本 session 有驗收 fail/high 真命中。
- **動作**：piggyback 建議補測試／落 atom，每 session 一次。

### 子代理與裁判的 Stop

- SubagentStop 與裁判子 session（`CLAUDE_COMPANION_JUDGE=1`）的 Stop 只跑寫碼查核（`stop._code_gate_no_ask`）。
- 跟主 session 同一份預算，擋滿就放行並留帳（event=`*_released`），不問使用者。
- 寫入目標判不出的指令放行並留帳（UNKNOWN_TARGET_LOGGED）。

### 超時降級

- **只在守門開時有**：守門關時不計時、不降級、不代送（跨層表 #6）。非寫碼回合不寫 run 帳，降級保護照跑。主文見 [乙11](coding-guard.md#乙11-hook-計時與快逾時降級)。
- **計時**（[`hooks/wg_hook_timing.py`](../hooks/wg_hook_timing.py)）：
  - SessionStart、UserPromptSubmit、PreToolUse、PostToolUse、Stop 從行程建立起計時，段落之間打一個點。
- **降級條件**：
  - 累計超過這個事件 hook 上限的 80%。
  - 上限讀法：settings.json 裡 workflow-guardian 那支的 timeout，有 matcher 的組要對得上工具名。
  - 資料根沒有 settings.json 讀程式碼根那份。
  - 都讀不到用 `hook_timing.fallback_limit_s`。
- **降級動作**：
  - 把 state 寫回、放行，後面的段落這次不跑。
  - 寫 `Logs/guard-hook_timing.jsonl` 一筆 kind=degraded（跑到哪一段、各段耗時）＋stderr 一行。
- **不降級的後果**：Claude Code 時間到直接取消 hook。
  - 不保證採用已印的輸出（未實測）。
  - state 寫不回、什麼訊號都沒有。
- **各事件降級跳過的段落**：
  - SessionStart：
    - 追蹤提示一開場就算好排在表頭後，降級時送出已備好的提示（追蹤提示在前）並附一行說明。
    - 選配提示、開場 git 快照、清舊 state、向量服務這次不跑。
  - UserPromptSubmit：跳過脈絡、檢索與注入組裝；前置閘、記原話、寫 state 照做，附一行說明。
  - PostToolUse：
    - 只跳過提示類段落（depends 召回、跨 session 碰撞、同伴檢查）。
    - 改檔記帳、寫 state 照做。
  - PreToolUse：只打點不改判定（逾時被取消本來就放行，提早放行只會少查）。
- **單一段落跑過上限**：
  - 打點只在段落之間，單一段落一路跑過上限打不到點，所以起表時另排背景鬧鐘。
  - 到上限 95% 還沒結束就先寫一筆 kind=overrun（卡在哪一段之後、有沒有代送）＋stderr。
  - SessionStart／UserPromptSubmit 登記了代送輸出、正常輸出還沒送時，鬧鐘接著代送已備好的那份並結束行程，搶在取消前送出。
- 每次 hook 結束另寫一筆 kind=run；[`python tools/hook-timing.py`](../tools/hook-timing.py) 看各段中位數。

### 擋訊息格式與回合定義

- 寫碼查核的每一條擋訊息都是一條有名字的規則（[`hooks/wg_release_rules.py`](../hooks/wg_release_rules.py)，規則表 [乙9](coding-guard.md#乙9-規則全表)）。
- 格式：`✗ (<字母>) <規則名>：<一句現象>｜證據：<一行一證據>`。
- 擋次預算每個使用者回合共用一份、不分是哪一條規則（[BLOCK_BUDGET_SHARED](release-rules.md#block_budget_shared)），擋滿訊息列出全部命中條目。
- 「回合」＝使用者打字開的回合；同伴訊息、背景通知都不開回合（[TURN_SINCE_USER_PROMPT](release-rules.md#turn_since_user_prompt)）。

### 擋訊息的問法

- 擋訊息的字句會把 AI 帶到哪裡，跟判斷本身一樣要調。
- 下面幾處的字句都是「先分辨是哪種情況，再給那種情況的處置」。
- 字句的實測（內網 gemma4:e4b 比對兩種寫法）紀錄在 [`_AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/LLM切入點自評-實測/`](../_AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/LLM切入點自評-實測/)（[`cases_003.json`](../_AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/LLM切入點自評-實測/cases_003.json)、[`results_003.jsonl`](../_AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/LLM切入點自評-實測/results_003.jsonl)、README 判定表）。
- 字句由 [`hooks/verify/verify_entry_wording.py`](../hooks/verify/verify_entry_wording.py) 守。

#### 提問前先讀部位
- **字句在哪**：`wg_release_rules.ask_overview_verdict`
- **怎麼問**：這條不單獨擋；但被別條擋下要重組時，先讀題目提到、還沒讀的部位檔，讀完再定推薦或判斷不必問。

#### 退避舉證
- **字句在哪**：[`handlers/user_prompt_submit.evasion_ask`](../hooks/handlers/user_prompt_submit.py)
- **怎麼問**：
  - 排在那一則注入最前面。
  - 先處理這件再做新請求：寫成本、小就先做掉；真的不做或只是描述就寫不做行／不是退避行。

#### SmellGate 處置句
- **字句在哪**：[`tools/project-smells.render_commit_report`](../tools/project-smells.py)
- **怎麼問**：先分被點名的段落是不是你這次任務寫的。
  - 是 → 修或 smell-ok；壓平照設計尺（提早 return／continue、替判斷式取名、查表），不為壓層數抽只呼叫一次的小函式。
  - 不是 → 不修：別人留在暫存區的檔只提交自己的；舊碼搬動、改名、合併進來的原樣再送一次。

### 定死規則（寫碼查核相關，改法不得放寬）

- CommitOrder 豁免：commit 落在記憶系統 repo 或其 worktree 才不等口令。
  - 只認 `&&` 串的 `cd <絕對路徑>`／`git [-C <字面路徑>] add|commit|push` 句型。
- git checkout 只給一個參數：
  - 現存檔＝還原該檔。
  - 現存目錄＝目標不明。
  - 都不是＝切分支，不算寫入。

## A7.2 反退避（Anti-Evasion）

→ 已搬到 [TECH §7.2](../TECH.md#72-反退避anti-evasion) 與 [TECH A7](../TECH.md#a7-基本守門細節)

## A7.3 擋滿之後怎麼放行（`hooks/wg_release.py`）

[↑ 乙4](coding-guard.md#乙4-擋滿之後怎麼放行)

目的：寫碼類的查核閘擋滿次數後，AI 不能自己放行、也不能改寫措辭繞過，決定權交回使用者。用在寫碼查核（ReconcileGate）、等值閘。

### 擋滿訊息

- 固定格式，要 AI 用 AskUserQuestion 問使用者。
- 題目含標記【收尾放行確認】。
- 選項固定兩個：「放行這一回合」「繼續擋，先修好」。

### 放行只認兩種

- 都要出現在「最後一次擋」之後。
- AskUserQuestion 那題的回答是「放行這一回合」。
  - 只認題目含標記的那次工具回應。
  - 其他工具輸出或 AI 自己印同樣的字不算。
- 或使用者本人新打一則整句就是放行句（「放行」「好，放行這一回合」這類）。
  - 否定、疑問、引用都不算。

### 待放行只在同一個使用者回合有效（規則 PENDING_SAME_USER_TURN）

- 判法 `wg_release.pending_of`。
- 擋滿記 `pending_release`。
- 背景通知、同伴訊息開的續跑回合不算換回合，照第一次擋滿時的宣稱原話重查。
- 使用者打字開了新回合就失效，預算重給、不拿上一回合的宣稱重查。
- 放行記 `user_release`，週健檢列紅。

### 放行的是列過的那幾件（規則 RELEASE_COVERS_SHOWN_ITEMS）

- 同一回合照選項字面整個放。
- 之後的回合只沿用擋訊息列過、使用者看過的條目：
  - 對帳每條 ✗ 的規則與現象。
- 原因還在不再問、原因消失就拿掉。
- 寫碼查核放行之後又改了檔，整份不再沿用。
- 新出現的原因照擋。

### 沒人能回答的情境

- 對象：裁判子 session、子代理、headless／SDK 主 session。
- 不叫它問。
- 寫碼查核、等值證法照預算擋，擋滿就放行並留帳。
  - 主 session event=noninteractive_released。
  - 子代理與裁判 `*_released`。
- 擋訊息不說「不能放行」（規則 [NONINTERACTIVE_RELEASE_AT_BUDGET](release-rules.md#pending_same_user_turnrelease_covers_shown_itemsnoninteractive_release_at_budget)）。

### 與提問閘的關係

- 提問閘（[問使用者附推薦](#問使用者附推薦askuserquestion)）認得這種放行題。
- 真有擋滿待放行紀錄時，放行題不必附推薦。

## A7.4 驗收裁判：AI 審查 AI 產出（四段閉環）

[↑ 乙5](coding-guard.md#乙5-驗收裁判)

先給裁判**案卷**（任務專屬驗收標準）再談能力——通用直覺審必然低精度。

### 總開關與只記錄

- 整段歸守門總開關：寫碼守門關著（出廠）時，兩個觸發處（收尾宣稱完成、規格檔標 done）都不跑。
- 寫碼守門開著時：
  - 裁判只在背景審。
  - 記 `workflow/acceptance-audit.jsonl`。
  - advisory 照注，**一律不擋收尾**；沒有改成硬閘的開關（[`hooks/verify/verify_acceptance_review.py`](../hooks/verify/verify_acceptance_review.py) 的 `test_no_sync_gate_left_in_hook` 守著擋收尾的程式路徑不再長回來）。
- 為什麼不擋：擋收尾會讓「改 → 驗收 → 再改 → 再驗收」無限擴張，裁判只記錄、結果交人看。

### ① 規格工件

- **入口**：[`hooks/acceptance_spec.py`](../hooks/acceptance_spec.py)（由 guardian PostToolUse 同程序呼叫 `run()`）。
- **機制**：
  - 不提示 AI 寫規格檔：守門開或關都不送字。
  - AI 自己寫了 `<專案根>/.claude/verify/acceptance-<slug>.md`（必須發生／禁止發生／驗證指令），PostToolUse 把路徑登記進 `workflow/acceptance-spec/<sid>.json` 的 spec_paths，影子裁判憑它找這個任務的標準。
  - `acceptance_spec.enabled=false` 連登記都不做。

### ② 影子裁判

- **入口**：[`tools/codex-companion/acceptance.py`](../tools/codex-companion/acceptance.py)。
- **機制**：
  - Stop 完成宣稱觸發。
  - 任務↔規格**四分流**：bound 才審；ambiguous / other_session / none → uncertain 不發。
  - 案卷＝需求原話＋清單＋diff 頭尾採樣＋測試輸出，截斷必 in-band 標記。
  - verdict pass/fail/uncertain → `workflow/acceptance-audit.jsonl`。

### ③ 背景審

- **入口**：`codex_companion.py` Stop。
- **機制**：
  - Stop 不等：起背景審查、立即放行。
  - 結果落 assessment 檔，下一則 UserPromptSubmit 附一行。
  - fail ∧ high 附完整說明。
  - 配額分桶 acceptance 上限 8／保底 6。

### ④ 迴歸提示

- **入口**：[`stop.py _acceptance_regression_hint`](../hooks/handlers/stop.py)。
- **機制**：見 [A7.1 迴歸提示](#迴歸提示)。

### 裁判後端鏈

- 位置：[`tools/codex-companion/judge_backend.py`](../tools/codex-companion/judge_backend.py)。
- 順序：
  - codex：跨廠；一律經 [`tools/codex-call.py`](../tools/codex-call.py) 叫（叫不起來回非 0 並印原因，不報成功）。
  - → headless `claude -p --model sonnet`：同廠不同模型，獨立性較低。
  - 不論哪個後端，結果都只當 advisory。
  - → 皆無退 heuristics-only，並 SessionStart 揭露一次。
- 授權類失敗（未登入/401/429）：
  - 當輪切備援。
  - 落 `workflow/companion-backend.json` 抑制，`reprobe_hours` 24 內不重試。
- 備援子 session 帶 `CLAUDE_COMPANION_JUDGE=1`，自家 hook 見之早退（防裁判觸發裁判）。
- **殺閘寫死在程式**（`promotion_stats()`）：fail ≥10 筆且 precision <50% → 收掉。

## A7.5 其他守門

[↑ 乙6](coding-guard.md#乙6-其他寫碼守門)

本節只留寫碼守門的閘：SmellGate、問使用者附推薦，對應 [乙6](coding-guard.md#乙6-其他寫碼守門)。不看守門開關的閘細節已搬到 [TECH A7](../TECH.md#a7-基本守門細節)，標題留著當舊連結的落點。

### lang_guard
→ 已搬到 [TECH A7](../TECH.md#a7-基本守門細節)

### plan_bash_guard
→ 已搬到 [TECH A7](../TECH.md#a7-基本守門細節)

### SvnEncoding
→ 已搬到 [TECH A7](../TECH.md#a7-基本守門細節)

### SvnTestBlock
→ 已搬到 [TECH A7](../TECH.md#a7-基本守門細節)

### SmellGate
- **名稱**：SmellGate（G2），commit 前病形檢查
- **位置**：[`hooks/handlers/pre_tool_use.py check_smell_gate`](../hooks/handlers/pre_tool_use.py) → [`tools/project-smells.py`](../tools/project-smells.py)「commit 前病形檢查」段（PreToolUse Bash／PowerShell 的 git／svn commit）
- **性質**：照擋（病形）
- **查什麼內容**（這次真的會提交的）：
  - 暫存區、`commit -a`、`commit <路徑>`
  - 同一條指令前面 `git add` 要加進來的檔
  - svn 工作副本改動
- **比對方式**：
  - 每個程式檔（`wg_code_path.is_code_path`）取舊版（HEAD／BASE，改名取舊名）與新版比對
  - 檔名一律 `-z` 取，中文檔名不被跳脫
  - 「這次會提交哪些檔」由 `commit_entries` 一處判，隱私閘共用

#### 內建病形
- **匿名函式**：
  - 匿名函式本體裡再套匿名函式
  - 匿名回呼跨行套三層；測試框架的 describe／it 回呼、promise then 回呼用到外層參數的不算一層；C#「型別 名稱 =>」運算式主體成員不算 lambda
  - 匿名函式／Java 匿名類別本體超過 `anon_body_block_lines`（20）行擋、到 `anon_body_list_lines`（10）行只提醒；測試檔與測試框架回呼不量
- **Python**：
  - 只有 `__init__` 加一個方法且沒繼承的類別
  - `x = lambda`（except 區塊裡的載入替身不算；這兩條測試檔不查）
  - 巢狀三元
  - 函式控制結構巢狀 ≥`nesting_block_depth`（4）層；elif 不加層；同名函式改後沒比改前深就算舊病
- **C# Unity 腳本**（檔裡有 UnityEngine）：
  - 空的訊息方法（virtual／override／abstract 不算）
  - Update 系列本體裡直接 Find／FindObjectOfType／AddComponent／反射；先判 null 的延遲快取、`#if UNITY_EDITOR` 區段不算
- **依據與校準數字**：在派工信箱的提案信；`workflow/inbox/` 是本機資料、不進版控，別台機器看不到

#### 病灶清單與部位表
- 部位表「病灶清單」欄指的病灶文件，每條 `shape:` 也納入
- 檔對不到任何部位、而部位表裡有資料列因前綴沒用反引號包（或是沒有 / 的根目錄單檔）被整列略過 → 列「注意：部位表…整列沒被讀到」；只提醒，不改認法

#### 判定與放行
- **剝不乾淨**：大括號語言的字串、註解剝不乾淨（大括號或小括號對不上）→ 那個檔的內建病形一律只提醒不擋
- **deny 條件**：
  - 病形範圍內有這次改到的行：Python 取外層 lambda／整個類別／整個函式；刪除算碰到刪除處前後
  - 且所有提交檔舊版裡同一個（規則, 點名那行）一份抵一份抵不到
  - deny 時列病名、為什麼、怎麼改、檔與行（巢狀附幾層、匿名本體附幾行）
- **只提醒**：只提醒的另列一段；其餘列為「舊碼原本就有」只提醒；專案 `smells_report` 的列整檔算舊
- **放行**：那一行寫 `smell-ok: <理由>` → 放行並列出
- **不是這次任務寫的被點名**（不修，修它就偏離使用者這次要的事）：
  - 別人留在暫存區的檔：不動它的暫存，只提交自己的檔（`git commit -- <你的檔>`）
  - 舊碼原樣搬動或改名、合併進來的別人分支：原樣再送一次
- **同一回合同一個 repo 只擋一次**（規則 [SMELL_GATE_ONCE_PER_TURN](release-rules.md#smell_gate_once_per_turn)，`pre_tool_use._smell_once_per_turn`）：
  - 修了又長出新病、原樣重送、判不了一律擋，都不會一直擋下去
  - 第二次起放行，留帳 `Logs/guard-smell_gate.jsonl` event=released；擋訊息改當提醒送給 AI，要它把沒修就提交的病寫進收尾檢核「AI 自己做主」
  - 換使用者回合重新算；沒有 state（記不住擋過）照擋

#### 判不了一律擋
- 拆不出 commit 落點
- `--git-dir`／`--work-tree`／`GIT_DIR` 類指定
- `--pathspec-from-file`
- 程式檔超過 2000 個
- git 查詢失敗、檢查出錯
- git 別名（`git config alias.*`、別名接別名、行內 `-c alias.<名>=…`）先展開成 git 實際會跑的子命令再判；跟 git 自己指令同名的別名不認
- 下列情形就算同一條指令另有直接寫的 commit 也判不了、一律擋（隱私閘、口令閘共用同一份拆段）：
  - `!` 開頭的 shell 別名
  - commit 落點查不到別名表時不是 git 指令的子命令
  - bash -c 之類的包裝、eval
  - commit 訊息裡的 `$(…)` 裡有 commit

#### 其他
- **已知限制**：跨行的表達式箭頭函式不算套層
- **停用**：`guard.smell_gate.enabled=false`
- **手動**：[`python tools/project-smells.py --commit-check --cwd <repo>`](../tools/project-smells.py)

### 問使用者附推薦（AskUserQuestion）
- **位置**：[`hooks/wg_ask_gate.py`](../hooks/wg_ask_gate.py)
  - PreToolUse：settings.json matcher 掛 `AskUserQuestion|ExitPlanMode`
  - 沒攔到的由 PostToolBatch 事後提醒
- **性質**：提醒（照 `RULE_MODE`；事後那條路只提醒）
- **開關**：跟守門總開關；寫碼守門關時 dispatcher 不把這兩個工具送進 PreToolUse，PostToolBatch 也不跑這段
- **閘自己出錯**：判不了這題，提問照放；stderr 一行、帳記 `ask_error`，下一個工具結果附一行（[GATE_SELF_ERROR](release-rules.md#gate_self_error)）；【收尾放行確認】而且真有待放行紀錄的題目照放、不附提醒
- **原則**：人只做真正的決定，而且看懂全貌才拍板

#### 兩條規則（乙9）
- **每一題要附推薦**（[ASK_NEEDS_RECOMMENDATION](release-rules.md#ask_needs_recommendation)）：選項 label 標 `(Recommended)` 或題目含「建議：」；【收尾放行確認】固定兩選項的放行題豁免
- **問改法而題目提到的部位還沒讀過檔**（[ASK_OVERVIEW_BEFORE_DECISION](release-rules.md#ask_overview_before_decision)）：
  - 題目沒提部位表上的路徑時，看本 session 有沒有讀過任何部位檔
  - 提醒多一句「先讀過部位檔再問」（不單獨擋）

#### 提醒與放行題
- 提醒印規則名、缺哪一題、照抄可過的寫法，所有句子併成一則
- 放行題看結構：題目含【收尾放行確認】、選項正好固定兩個
  - 真有擋滿待放行紀錄時，整次全是放行題才整次豁免
  - 夾一般題或把標記塞進一般題，照查推薦

#### 留帳
- `Logs/guard-ask.jsonl`
- PostToolBatch 每次提問記一筆審計 `ask_audit`（擋過幾次）
- 訊息標記 `[Guardian:Ask]`

### version_guard
→ 已搬到 [TECH A7](../TECH.md#a7-基本守門細節)

### 跨 session 衝突預警
→ 已搬到 [TECH A7](../TECH.md#a7-基本守門細節)

### Codex Companion
- 背景審查的通則（計畫審、回合證據、交接自檢、節流）→ 已搬到 [TECH A7](../TECH.md#a7-基本守門細節)
- 驗收裁判（acceptance_review）屬寫碼守門，留在本檔：[A7.4](#a74-驗收裁判ai-審查-ai-產出四段閉環)。
- 叫 Codex 一律走 [`tools/codex-call.py`](../tools/codex-call.py)（本系統叫 Codex 的唯一入口）；後端怎麼選見 [裁判後端鏈](#裁判後端鏈)。

### Wisdom Engine
→ 已搬到 [TECH A7](../TECH.md#a7-基本守門細節)

### Fix Escalation
→ 已搬到 [TECH A7](../TECH.md#a7-基本守門細節)

### DocDrift
→ 已搬到 [TECH A7](../TECH.md#a7-基本守門細節)

### Auto-Handoff
→ 已搬到 [TECH A7](../TECH.md#a7-基本守門細節)

## A7.6 寫碼守門：部位導讀卡（OverviewHub）

[↑ 乙7](coding-guard.md#乙7-部位表與-depends-召回)

### 設定來源
- 設定在 [`workflow/config.json`](../workflow/config.json) 的 `overview_hub` 段
- 合併順序（後者蓋前者）：程式預設 < config < 公司根 [`.claude/overview-hub.json`](../.claude/overview-hub.json) < 專案根 [`.claude/overview-hub.json`](../.claude/overview-hub.json)
- 未知鍵報錯

### 部位表
- **位置**：`<專案根>/.claude/overview-map.md`；根層自己的表在 [`~/.claude/.claude/overview-map.md`](../.claude/overview-map.md)
- **解析**：[`lib/overview_hub.parse_map`](../lib/overview_hub.py)
- **一列一個部位，欄位**：
  - 路徑樣式
  - 層
  - 導讀卡名
  - 卡片狀態
  - 病灶文件
  - 量尺
  - 類別：code／knowledge，沒欄或沒標＝code
- **新專案**：用 [`tools/overview-map-scaffold.py`](../tools/overview-map-scaffold.py) 掃出骨架；預設 dry-run，`--write` 落檔、不撤回可重入

### Depends 召回
- **位置**：[`hooks/wg_depends.py`](../hooks/wg_depends.py)（PostToolUse）
- **觸發**：讀到某張卡 `- Depends: path:<檔>` 指的檔（或其目錄之下）
- **動作**：一行指標「改它前先讀卡」，同卡一 session 一次
- **相關**：
  - `authority_map` 命中文件檔一次性注入地圖
  - 索引欄由 [`sync-atom-index.py --sync-depends`](../tools/sync-atom-index.py) 以 frontmatter 為真相同步

### 收據（收據列）
- **位置**：
  - [`hooks/wg_verify_ledger.py`](../hooks/wg_verify_ledger.py)：採認、對帳
  - [`lib/self_receipt.py`](../lib/self_receipt.py)：指令解析、自寫收據
  - Stop 的 ReconcileGate（[乙3](coding-guard.md#乙3-收尾閘序守門開時與收據)）

#### 帳本
- Bash／PowerShell 輸出的哨兵連同完整指令、exit code、cwd、根，進 `workflow/verify-ledger/<sid>.jsonl` 與 state
- 哨兵格式：`<NAME>_CHECK PASS|FAIL|DONE`、`<NAME> DONE k=v`；細則見 [`rules/coding-style.md`](../rules/coding-style.md) 自檢段

#### 背景跑與自寫收據
- 適用：跑超過工具 10 分鐘上限的 run_verify，與整組 pytest 量尺（`pytest -q tools/verify`、`pytest -q lib/verify`）
- 收據位置：資料根的 `workflow/verify-ledger/_runs/`
  - run_verify 自己寫
  - 整組 pytest 由根 [`conftest.py`](../conftest.py) 寫
  - 收據的 project_root 記受測的樹
  - 收據另記紅掉的測試名 `failed_cases`
- 認的條件（都要）：
  - 改完才開始跑
  - 全綠
  - 同一棵樹
  - argv 對得上宣告的指令（或涵蓋宣告的檔案項目），或對帳 (a)(b) 認的部位量尺
- 不綁 session

#### 能當證據的收據
- 指令完整（升級前只存 200 字的舊收據不算）
- 記了啟動環境
- 在專案樹內
- 跑程式的那幾段啟動時沒有縮範圍的環境設定
  - 例：`PYTEST_ADDOPTS`、`PYTHONOPTIMIZE`
  - 從父行程繼承的也算，要在指令內清空
- 不查語法白名單、指令形狀與指令裡寫的哨兵字樣
- **收據不防偽造**（RECEIPT_NO_FORGERY_CHECK）：自己寫程式印假哨兵、手寫帳本這類刻意造假不是程式能保證的，不為它加機制

#### 部位量尺與整體驗證
- 只看跑了哪支、在哪棵樹、exit／哨兵
- **量尺怎麼比**：
  - 量尺那串指令（各指令與中間的 `&&`、`||`、`|`、`;`）連續出現在收據指令的任一處就算
  - 前後接了什麼、用什麼串、輸出導去哪都不看
  - 各指令要逐字相同（程式、直譯器選項、其他參數；`-Xutf8`＝`-X utf8`）
  - 腳本照路徑認（收據照它的 cwd、量尺照部位根），同名在別處的不算
- **整體驗證**＝下列其一：
  - 其中一段是執行根自己的 [`run_verify.py`](../run_verify.py)（不帶參數）
  - 不帶位置參數、只帶不縮範圍選項（`-q -v -s -x`、`-p no:…`、`--tb=…`）的 pytest
- **看得出量的是哪棵樹**：
  - 指令裡沒有換目錄，或只有開頭一段 `cd <絕對路徑> &&`
  - 前者執行根不變；後者執行根換成該路徑
  - 路徑在原專案根之內，樹根仍是原專案根；從 `tests/` 點名 `../hooks/verify/...` 照算
  - 其他換目錄只算一般證據
- 整體驗證與部位量尺只涵蓋執行根之下的改檔

#### 解析不了的指令
- 範圍：here-string、heredoc、`$( )`、反引號、括號、大括號、單獨的 `&`、反斜線跳脫、iex／eval／source、`bash -c`、`pwsh -Command`、if／for 這類控制結構
- 看不出跑了哪支：不算量尺、不算整體驗證，照算一般證據
- 本回合帶 PASS／DONE 的這種收據，每次收尾 stderr 一行並留帳（[RECEIPT_UNPARSED_GENERAL_ONLY](release-rules.md#receipt_unparsed_general_only)）

#### 一般證據
- 用於對帳：(a) 指令提到改檔、(b) 量了、(c) 試過
- 只比實際跑程式那幾段的參數；前置設定、cd、環境指定、echo 印的字都不算

### 過程量
- **位置**：[`tools/refix-churn.py`](../tools/refix-churn.py)（手動跑，git／svn 自動判）
- **量什麼**：同檔反覆修的熱點：版控歷史裡 fix 類提交按檔排名

### 專案覆蓋表
寫在 `<專案根>/.claude/overview-hub.json`，只寫要改的鍵。

#### `readonly_paths`
- 預設：空
- 這種專案才改：有生成碼、打包產物、第三方原始碼不准手改 → 列 glob，命中一律擋
- 守門關時不擋：部位表整個不跑（跨層表 #36）

#### `smells_report`
- 預設：空
- 這種專案才改：專案有自己的壞味道報告產生器 → 指過去
- 誰讀：病形閘（報告列的檔整檔算舊病）

#### `authority_map`
- 預設：空
- 這種專案才改：專案有權威文件（規格書、介面表）→ 檔名樣式對到地圖檔

#### 部位表「量尺」欄
- 預設：無
- 這種專案才改：部位有整組的驗證指令 → 在部位表該列量尺欄填 `量法｜指令｜門檻`
- 量尺的定位：
  - 候選材料，不是收尾必跑；對帳 (a)(b) 認「跑了部位量尺」的收據與自寫收據
  - 整包全量（[`run_verify.py`](../run_verify.py)）不能填成量尺（全量改增量待補）
- `verify_chains`（`{部位: {runtime_gate, pre, run, collect, cleanup}}`）照驗形狀，目前沒有程式讀

#### `path_bases`、`eol_policy`、`source_encodings`、`commit_encoding`
- 預設：單根／依檔頭／utf-8
- 這種專案才改：多根倉庫、CRLF 專案、非 UTF-8 原始碼（例 cp950）

#### `verify_ledger.sentinel_regex`（config）
- 預設：PASS／FAIL／DONE 兩條＋pytest 映射
- 這種專案才改：專案既有工具尾行格式不同 → 加映射，不改工具

#### `svn_test_block.enabled`
- 預設：false
- 這種專案才改：專案規定測試／練習檔不上 svn → 開，svn commit 的路徑含測試檔就擋（[TECH §7.3](../TECH.md#73-commit-與驗證前的閘) SvnTestBlock）

## A7.11 文字規格評分（G15，`tools/text-score.py`）

→ 已搬到 [TECH §7.7](../TECH.md#77-文字規格評分toolstext-scorepy) 與 [TECH A7](../TECH.md#a7-基本守門細節)

## A7.12 連鎖斷路器（`hooks/wg_chain.py` 判定、`lib/chain_store.py` 帳與快照）

[↑ 乙8](coding-guard.md#乙8-連鎖斷路器)

### 目的與開關

- 閘擋了 AI 修、修了又被擋，一路修下去會偏離原本要做的事；連成一串時停下來交使用者決定。
- 寫碼守門開著、`chain_breaker.enabled` 為 true 才跑。
  - 出廠 config 寫開。
  - 設定裡沒寫這段＝不開。
  - 寫碼守門關時以總開關為準、整個不跑。
- 每種情境一條有名字的規則，寫在 [`hooks/wg_chain.py`](../hooks/wg_chain.py) 的 `RULES`（不在 [乙9](coding-guard.md#乙9-規則全表) 那份表）。
- 斷路器自己不逼修補、不要求任何宣告，只在警報後擋：收尾擋一次、停手中擋下讀與問以外的工具呼叫。

### 記帳

- **什麼記一條邊**：
  - 同一個使用者回合、同一個對話者（主 session 或同一個子代理）裡：閘擋下或記欠 → AI 動手 → 又讓任一道閘擋下或記欠。
  - AI 動手＝改檔、重跑、寫卡、重交報告；讀檔不算（CHAIN_ACTION_FACTS）。
- **閘名**：
  - 取擋訊息第一個 `[Guardian:名稱]` 標記，認不出才用呼叫端的預設名（工具前是 `PreToolUse`）。
  - 不同的閘混成同一個名字會讓同閘次數算錯，所以每道閘的擋訊息都要帶標記。
- **不算連鎖、不接邊**：
  - 原樣重試、只改寫回覆就又撞同一道閘：交回那道閘自己的擋次上限（CHAIN_SAME_GATE_NO_ACTION）。
  - 兩次之間的動作都沒改到檔：
    - 例：重跑測試、建刪暫存工作樹這類沒寫入目標的指令、重交收尾報告。
    - 同一道閘不接邊、不算同閘次數，動作照列進經過表。
    - 改到檔＝改檔、寫卡、子代理（`wg_chain.changes_files`，[CHAIN_NO_EDIT_NO_EDGE](release-rules.md#chain_no_edit_no_edge)）。
  - 中間做了別的動作（回應別的提示）之後原封不動重送上一次被擋的同一個呼叫（CHAIN_SAME_CALL_RETRY）：
    - 判法：工具名＋參數逐字相同，帳上 gate 記 `call`。
    - 也算原樣重試，不接邊、不算同閘次數。
    - 改了內容或在指令裡補了宣告（呼叫變了）照舊算。
  - 同一個 hook 事件裡先後擋的。
  - 擋的時候就已列在「後面還會擋」預覽裡的。
- **同一則回覆算同一步**（CHAIN_SAME_BATCH）：
  - AI 在同一則 assistant 回覆裡平行送出的工具呼叫是送出前就決定好的，中間沒看到任何擋訊息。
  - 這一批之間的觸發不接成邊、不讓同閘次數加 1。
  - 呼叫之間放過的改動也不算「看過擋訊息之後的動作」；下一則回覆裡的呼叫才算。
  - 這一批的觸發接在前一批裡深度最深的那一步。
- **哪一則回覆**：
  - 帳上工具呼叫的觸發與動作記 `batch`＝這次呼叫所在那則回覆之前最後一則 assistant 的 message.id（`chain_store._batch`）。
  - CC 一則回覆串流完才整則寫進 transcript，平行一批跑 hook 時這一則還沒落盤，取「之前那則」兩種情況都一致。
  - `--no-session-persistence` 跑的 session 沒有 transcript，一律判不出。
  - 這一筆判不出（子代理、transcript 讀不到、找不到前一則或沒有 message.id，帳上記 `batch_why`）：
    - 就不跳過任何一步。
    - 前面判得出批次的步驟照用（跟那一步同一批送出的動作不算反應）。
  - 收尾不是工具呼叫、一定在所有工具呼叫那幾則之後，不帶 batch。
- **帳**：`Logs/chain-<session>.jsonl`，狀態每次從帳重算。

### 警報

- **條件**（CHAIN_ALARM_SAME_GATE）：
  - 同一道閘這一段第 `max_same_gate` 次（2；只看閘名）。
  - 兩次之間 AI 看過擋訊息後有改到檔的動作。
  - 這次擋的不是原封不動的同一個呼叫。
- **中止**：這一回合其餘閘只記錄、不擋、不記欠，同一道閘只記一筆（CHAIN_ABORT_RECORD_ONLY）。
  - 被改成只記錄的閘不留「本回合擋過」標記，選繼續之後照常擋。
- 要擋的是繞回原點的修不停，那就是同一道閘第 2 次。

#### 深度
- 深度（閘→修→閘→修→第三次閘＝2）照算、照列進經過表。
- **預設不警報**：三道各管各的閘各擋一次不是連鎖。
- `chain_breaker.depth_alarm` 設 true 才在深度到 `max_depth`（2）時也警報（CHAIN_ALARM_DEPTH）。

### 能互動的 session

- **停手**（CHAIN_HALT_UNTIL_ANSWER）：到使用者選「繼續」或「放行」之前，讀（Read／Grep／Glob、唯讀指令）與 AskUserQuestion 以外的工具呼叫先擋下。
- **收尾擋一次**，送連鎖過程表，欄位：
  - 第幾步、哪道閘
  - 擋了什麼
  - AI 接著改了哪些檔幾行（只改註解有標）
  - 每步耗時
  - 總共連鎖幾次深度多少
- **問三選一**：要 AI 用 AskUserQuestion 問，題目含【收尾放行確認】【連鎖中止】：
  - 「還原連鎖改動（不符本批目標）」
  - 「信任後續 AI 審查，繼續」
  - 「放行這一回合」
- **答案只認**：tool_use_id 對得上、題目逐字相同的那一次（CHAIN_ANSWER_BY_TOOL_USE_ID）。
- **停手那題就答了**（帳上有 answer）：
  - 同一個使用者回合的收尾不擋、不重送經過表，只附一行結果（CHAIN_STOP_NOTICE_ONCE）。
  - 答案在收尾才讀到的附結果與表。
- **被取代的擋訊息**（[CHAIN_ABORT_SHOWS_REPLACED_BLOCK](release-rules.md#chain_abort_shows_replaced_block)）：
  - 警報在哪一次響，那道閘原本的擋訊息照附在取代它的中止通知或停手訊息最後。
  - 含附註。
  - 超過 2000 字留開頭。
  - 沒人能答的收尾通知也附。

### 三選一

#### 還原（CHAIN_RESTORE_SEGMENT）
- 只還原連鎖那一段：改檔前那一刻存的快照寫回、連鎖中新建的檔刪掉、寫回後重讀比對。
- 連鎖前的改動不動。
- 被別處改過的檔不覆寫、列出來。

#### 繼續（CHAIN_CONTINUE_RESETS）
- 開新的一段，次數與深度歸零。
- 閘照常擋，再超再問。

#### 放行（CHAIN_RELEASE_TURN）
- 這一回合其餘閘照舊只記錄。
- 紅測、對帳這些既有閘也照它們的放行規則記成使用者放行。

### 沒人能答

- **範圍**：headless／SDK、子代理、裁判子 session。
- **行為**（CHAIN_HEADLESS_NO_ASK）：
  - 不問、不停手，其餘閘只記錄，AI 照常把工作做完。
  - 收尾擋一次要 AI 把經過表寫進收尾報告。
  - 不還原也不繼續。
- **例外**（[CHAIN_HEADLESS_KEEPS_DATA_GATES](release-rules.md#chain_headless_keeps_data_gates)，`wg_chain.KEEP_BLOCKING`）：
  - 會改使用者資料的閘照擋，含讓警報響的那一次。
  - 有：commit 前的口令／隱私檔／svn 測試路徑、專案 session 改根層核心或全域 MCP。
  - 經過表標「會改使用者資料照擋」。
- **判法**：`wg_release.non_interactive_reason`、警報那一刻判。
  - 入口（環境變數 `CLAUDE_CODE_ENTRYPOINT`，沒有再看 transcript 的 entrypoint 欄）是 `sdk-*` 才算 headless。
  - `claude -p` 卻把入口設成 `claude-vscode` 的跑法（有的驗收工具會這樣設）照能互動算、會停手。
- **已知限制**：這種 session 底下沒有 AskUserQuestion、沒人能答三選一，警報後讀與問以外的工具會停手到換回合（使用者下一則話）為止。

### 快照

- 連鎖段開著時，每個要被改的檔這一段第一次改之前存到 `workflow/chain-snap/<session>/`。
- 存的位置：PreToolUse 放行出口。
- 不存的情況（記原因）：
  - 超過 `snapshot_max_bytes`。
  - 這一段已存 `snapshot_max_files` 個。
- 還原時每檔最多試 `restore_retries` 次。
- SessionEnd 刪這個 session 的快照，以及 7 天沒動的別 session 快照與帳。

### 出錯

- 斷路器自己出錯一律照原本的閘行為（不中止、不只記錄、不停手），stderr 一行。
- 快照存不了照放行改動、帳上記原因。
- 沒有連鎖時（擋一次、修一次、過）各閘的輸出一字不變。

### 接線與案例

- **接線**：
  - Stop 各閘之前 `chain_store.on_stop`，每道閘擋或記欠之前問 `stop._chain_hold`。
  - PreToolUse 開頭 `_chain_halt`、擋下時記觸發、放行出口存快照。
  - 掛在 PreToolUse matcher 上的 MCP 工具（例：搬卡）也先過 `_chain_halt`（[TECH §3.1](../TECH.md#31-settingsjson-十一個事件)）。
  - PostToolUse／PostToolUseFailure 記 AI 動作。
  - SessionEnd `chain_store.session_cleanup`。
- **案例**：
  - [`hooks/verify/verify_chain_breaker.py`](../hooks/verify/verify_chain_breaker.py)（判定、帳、快照還原、同一則回覆平行 12 個呼叫的重演）。
  - [`hooks/verify/verify_chain_wiring.py`](../hooks/verify/verify_chain_wiring.py)（走真的 Stop／PreToolUse／PostToolUse／SessionEnd 入口）。
- **pytest 底下的帳隔離**：
  - `chain_store._test_root` 讓每一案每一次執行各用一份帳與快照。
  - 位置：測試用 Logs 目錄底下 `chain-tests/<這次執行>/<案例>`。
  - 「這次執行」＝環境變數裡的暫存目錄 TMPDIR／TEMP／TMP。
    - root conftest 每次 pytest 開始時換一個新的。
    - 同一個行程再跑一次 pytest.main 也換。
    - 案例開的子行程繼承同一份、誰先用到都一樣。
  - Logs 目錄跨次執行固定時（設了 `WG_TEST_LOGS_DIR`）同一案第二次跑也讀不到上一次的帳。

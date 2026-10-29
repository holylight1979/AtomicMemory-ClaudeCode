# 守門與收尾：細節（TECH §7 附錄）

[↑ 主文 §7](../TECH.md#7-守門與收尾)

TECH.md [§7](../TECH.md#7-守門與收尾) 主文的細節。每一節對應主文同編號小節（A7.1 ↔ [§7.1](../TECH.md#71-stop-閘序)），開頭有「↑ 主文」連回去。[§7.8](../TECH.md#78-放行欠帳判定規則hookswg_release_rulespy) 規則全表另在 [TECH/release-rules.md](../TECH/release-rules.md)。

## A7 守門與收尾：開頭說明

[↑ 主文 §7](../TECH.md#7-守門與收尾)

### 守門總開關（完整）

- 設定鍵：[`workflow/config.json`](../workflow/config.json) 的 `coding_guard.enabled`，出廠關；判法 `wg_core.v6_enabled`，只認 JSON 的 true。
- 本機要開：設環境變數 `WG_CODING_GUARD=1`，或在不進版控的 `workflow/config.local.json` 寫 `{"coding_guard": {"enabled": true}}`。
- `WG_CODING_GUARD=0` 強制關。
- 舊鍵 `v6` 與舊環境變數 `WG_V6` 仍可用。
- 關著時本節大部分的守門都不跑：
  - 需求目標樹
  - 寫碼查核
  - 紅測閘
  - 第二意見
  - 拐彎判斷
  - 等值閘
  - 文字評分
  - 判準卡留帳
  - 動資料檔／改舊測試／病形閘／繞閘宣告
  - 連鎖斷路器
  - 驗收裁判
  - 背景收割
- 關著時只留這套守門加進來以前就有的處理：記憶注入、導讀卡、收割、同步提醒、隱私與口令閘、語言守門…
- 開著時，每回合的守門只在寫碼回合啟動（[§11.2](../TECH.md#112-守門減量同一件事只問一次記帳交程式或免費模型) [CODING_TURN_ONLY](../TECH/release-rules.md#coding_turn_only)）：
  - 目標樹提示
  - 目標視角重看
  - 退避偵測
  - 退縮閘
  - 收尾檢核
  - 文字評分
  - 閱讀路徑
- 下面各表寫的是開著時的行為；寫「寫碼守門開時」的條目，寫碼守門關時照舊做法。

### 擋或提醒（完整）

- 判定與送法只讀 [`hooks/wg_release_rules.py`](../hooks/wg_release_rules.py) 的 `RULE_MODE`，呼叫端一律經 `gate_mode(rule, v6)` 問。
- 寫碼守門開著時，守門照擋的只有三類：
  - 病形閘（含防繞：SmellGate、GateBypass）。
  - 改使用者資料檔／改舊測試沒先宣告（DataFileAsk、OldTestDeclare）。
  - 紅測閘與寫碼查核的 (a) 說修好要有綠收據。
  - `RULE_CLASS` 標病形／宣告／紅測的規則名。
- 其餘寫碼守門一律**提醒**：
  - 第一次提醒一行（規則名＋現象＋做法，`remind_line`）＋留帳。
  - 不擋、不讓對話續跑。
  - 同一條規則同一個對象同一個 session 只提醒一次（`remind_due`）。
- 提醒掛在前一個動作的工具結果上（PostToolUse），不掛 PreToolUse 的 additionalContext：
  - 工具前的閘（定位、目標樹、導讀卡）掛第一次讀該部位程式檔或第一次改檔那則工具結果。
  - 收尾類的要求掛最後一次改程式檔那批的工具結果。
  - Stop 只留帳、不續跑、不開放行題。
  - 規則名 REMIND_ON_PRIOR_RESULT。
- 不屬寫碼守門的安全與權限邊界照擋、不讀本表：
  - 版控口令
  - 隱私檔
  - 記憶目錄寫入
  - 跨層寫入
  - `readonly_paths`
  - svn 測試路徑
  - 裁判子 session 的收尾
- 表上沒登的規則名當照擋。
- 寫碼守門關時 `gate_mode` 一律回 block，行為同這套守門加進來以前。
- 下面各表每道閘前面標的「照擋」「提醒」就是這張表的現況；標「照擋（不在範圍）」的是安全邊界。

### 代號（完整）

- `E<N>`：切入點（[§7.10](../TECH.md#710-切入點契約程式問卡教llm-判留帳回看)）。
- `G<N>`：「寫程式碼」這組需求目標的第 N 條。
  - 評分規格卡 `g<N>-評分規格*.md` 與 [`skills/console/scripts/selfscore.py`](../skills/console/scripts/selfscore.py) 用同一套號。
- `T2.<N>`：其中一條目標底下的子項。
- 程式裡的註解與設定說明也用這些號，所以表上保留，方便對照。

## A7.0 寫程式時一路會遇到什麼（總覽）

[↑ 主文 §7.0](../TECH.md#70-寫程式時一路會遇到什麼總覽)

照 AI 寫程式的先後順序，說每個時刻系統會問什麼、送什麼卡、擋什麼。

- 「擋」＝工具呼叫被拒（deny）或收尾被打回（block），AI 補完才能繼續。
- 「提醒」＝只多送一段文字、不擋。

### ① 開場（SessionStart）

- **系統做什麼**：
  - 列「之前交付時點出、還沒解的問題」。
    - 即未結追蹤項，附建議怎麼解。
    - 要 AI 第一則回覆先轉述。
  - 列公司層與週健檢狀態。
- **擋不擋**：提醒。
- **見**：[§3.1](../TECH.md#31-settingsjson-十一個事件)、[§8](../TECH.md#8-可觀測與自我維護)。

### ② 收到需求（UserPromptSubmit）

- **系統做什麼**：
  - 注入相關記憶卡。
  - 還沒有**需求目標樹**就提醒先寫。
    - 需求目標樹＝把這件事真正要達成什麼寫成樹根＋子目標。
  - 有樹就每則送回樹根一行＋當前節點一行。
  - 目標樹提示只在寫碼回合送。
- **擋不擋**：提醒。
- **見**：[§5](../TECH.md#5-檢索與注入每-prompt)、[§7.7](../TECH.md#77-需求目標樹need_goal)。

### ③ 動手前定位（改檔前的 PreToolUse）

- **沒有目標樹要先立樹**：
  - 寫「目標｜<整個需求一句>」。
  - 子目標每件一行「子目標｜…」。
  - 放在同一則先發的不寫檔指令開頭的 `#` 註解。
  - 改程式檔前 hook 照它立樹（[TREE_SET_VIA_TEXT](../TECH/release-rules.md#tree_set_via_text)，零工具回合）。
  - 缺了，寫碼守門開時提醒一行，不擋。
- **立樹路徑的細節**：
  - 訊息只教「同一則先發的不寫檔指令開頭的 `#` 註解」這一條路。
  - 早一則只有文字的回覆程式照認、不教。
  - 原因：同一則裡接著呼叫工具的文字，hook 當下讀不到（[DECL_HINT_KEEPS_EDIT_TOOLS](../TECH/release-rules.md#decl_hint_keeps_edit_tools)）。
- **改部位表上的程式檔**（部位表＝把專案切成幾個部位、每個部位一張導讀卡的對照表）要先：
  - 注入那個部位的導讀卡。
    - 預設只送病灶一句＋卡路徑，要自己 Read 過卡。
  - 讀過部位裡的檔。
  - 交「定位」五行：
    - 部位
    - 根因層（兩個候選＋為什麼選這個）
    - 前例
    - 這塊在目標樹哪個節點
    - 批判（這段寫法合不合理、同類問題還在哪）
- **沒有部位表的專案**：第一次改某個頂層目錄前交「地圖」三行（讀了／上游／下游）。
- **放行規則**：
  - 同一個使用者回合同樣的缺件擋 2 次，第 3 次放行並留帳（[GATE_DENY_CAP](../TECH/release-rules.md#gate_deny_cap)）。
  - 讀不到對話紀錄＝閘判不了，這次不要求定位行與地圖三行（[GATE_SELF_ERROR](../TECH/release-rules.md#gate_self_error)）。
- **提醒模式的唯一例外**（[LOCATE_FIRST_EDIT_BLOCKS_ONCE](../TECH/release-rules.md#locate_first_edit_blocks_once)）：
  - 每部位本 session 第一次改程式檔的那個使用者回合，定位交齊之前，同部位每個改檔都擋。
  - 同一則平行送的也擋，不計 [GATE_DENY_CAP](../TECH/release-rules.md#gate_deny_cap)。
  - 交齊才放；下一個使用者回合還缺只提醒。
- **擋不擋**：提醒。
- **見**：[§7.6](../TECH.md#76-寫碼守門部位導讀卡overviewhub)、[§7.7](../TECH.md#77-需求目標樹need_goal)。

### ④ 改檔當下

- **動資料檔**：
  - 改使用者既有的資料檔或設定檔，要先寫「動資料檔｜<路徑>：<為什麼>」。
  - 只在這個 session 改過程式檔、或這條指令同時寫程式檔時才問。
  - 純文件／設定的回合放行、留帳 skipped_non_coding。
- **改舊測試**：
  - 改既有測試（刪、改名、改斷言、加 skip）要先寫「改舊測試｜<哪支>：<理由>」。
- **兩道的放行**：
  - 同一個使用者回合同一件缺件擋 2 次後放行並留帳（[GATE_DENY_CAP](../TECH/release-rules.md#gate_deny_cap)）。
  - 閘自己出錯不擋、留帳（[GATE_SELF_ERROR](../TECH/release-rules.md#gate_self_error)）。
- **改判準卡**：
  - 改到綁了切入點的判準卡（檔頭 `- Entry:` 非空）只留帳不擋。
  - 涵蓋經 MCP `atom_write` append／replace、`atom_edit_meta`、`atom_retire` 改。
  - 寫了「改判準卡｜<卡名>：<理由>」就連理由一起記下。
- **寫入目標判不出的指令**（例：`python -c` 內嵌碼裡開檔寫）放行並留帳。
- **擋不擋**：擋（動資料檔、改舊測試）。
- **見**：[§7.5](../TECH.md#75-其他守門)、[§7.6](../TECH.md#76-寫碼守門部位導讀卡overviewhub)。

### ⑤ 改完之後（PostToolUse）

- **系統做什麼**：
  - 記下改了哪些檔、蓋到目標樹。
  - 讀到某張卡 `Depends` 指著的檔就召回那張卡。
  - 本 session 第一次碰到的部位注入導讀卡。
- **擋不擋**：提醒。
- **見**：[§7.6](../TECH.md#76-寫碼守門部位導讀卡overviewhub)、[§7.7](../TECH.md#77-需求目標樹need_goal)。

### ⑥ 問使用者之前（AskUserQuestion）

- **系統做什麼**：
  - 每題要附推薦選項（缺了提醒）。
  - 有樹時每題掛到哪個目標節點只記錄，沒掛不擋。
  - 問改法前先讀過題目提到的部位（只提醒）。
- **擋不擋**：提醒。
- **見**：[§7.7](../TECH.md#77-需求目標樹need_goal)。

### ⑦ 跑測試

- **系統做什麼**：
  - 驗證程式印的**哨兵行**（`<名>_CHECK PASS／FAIL`、`<名> DONE k=v`）連同完整指令收成「收據」。
  - 紅了記紅測。
- **收據的限制**：
  - 收據不防偽造：不看指令形狀、不查指令裡寫的哨兵字樣。
  - 指令解析不了（heredoc、`$( )`…）只當一般證據，不算部位量尺與整體驗證。
- **擋不擋**：只記帳。
- **見**：[§7.6](../TECH.md#76-寫碼守門部位導讀卡overviewhub) 收據列。

### ⑧ 宣告完成（Stop）

- **查核順序**（先把回覆丟背景評分，再依序）：
  - 紅測沒修好不准說完成。
  - 寫碼查核：說修好要有改動之後的綠收據 (a)、改了程式要有測試案例 (d)。
  - 函式拐彎過多要逐條寫判斷。
  - 大改動要跑第二意見。
  - refactor／perf 要等值證法、答熱路徑。
  - 不准把可做的事推給下個 session。
  - 知識收割。
  - 清掉自己建的工作樹與暫存。
  - 同步提醒。
- **擋滿的處理**：
  - 紅測與寫碼查核同一個使用者回合擋滿兩次，不自己放行，改問使用者【收尾放行確認】。
  - 待放行只在同一個使用者回合有效。
  - headless、子代理沒人能回答，擋滿就放行並留帳。
- **連鎖斷路器**：閘擋→修→又擋連成一串時，由連鎖斷路器中止、交使用者三選一（[§7.12](../TECH.md#712-連鎖斷路器hookswg_chainpy-判定libchain_storepy-帳與快照)）。
- **擋不擋**：擋只紅測與 (a)；其餘提醒。
- **見**：[§7.1](../TECH.md#71-stop-閘序)、[§7.3](../TECH.md#73-擋滿之後怎麼放行hookswg_releasepy)。

### ⑨ 交付

- **系統做什麼**：
  - 收尾檢核報告（`anti_evasion_report` 十欄）送 HUD 給人看。
  - 目標樹的「完整對照」（對照閘關著時由程式代填）。
  - 順手點出這次看到最該修的一件，記進追蹤帳本，下個 session 開場列出。
- **擋不擋**：提醒。
- **見**：[§7.2](../TECH.md#72-反退避anti-evasion)、[§7.7](../TECH.md#77-需求目標樹need_goal)、[§7.1](../TECH.md#71-stop-閘序) PickOne。

### ⑩ commit 與合併

- **口令**：要使用者下過口令（上GIT 等）。
  - 寫碼守門開時口令撐到這批 push 完或使用者打字開新回合。
- **隱私檔**：不准提交。
- **病形**：這次提交的程式不能新長出病形（巢狀過深、匿名函式過長…）。
- **繞閘**：被病形閘擋過後把檔移出暫存區，要寫「不是繞閘｜…」。
- **worktree**：在 git worktree 裡不要求 push。
- **多 session 並行**：工作軌只 commit 在自己的分支，交付信交總控台合併。
- **擋不擋**：擋（口令、隱私、病形、繞閘不在範圍）。
- **見**：[§7.5](../TECH.md#75-其他守門)、[§7.1](../TECH.md#71-stop-閘序) 同步閘、[§13.4](../TECH.md#134-多-session-協作雙總控台與工作軌)。

### 切入點（完整）

- 擋點與提醒點大多登記成**切入點**（程式停下來要 AI 判斷的位置，代號 E01～E41，登錄在 [`workflow/entrypoints.json`](../workflow/entrypoints.json)）。
- 問的那一刻，系統把綁在那個切入點的**判準卡**（教 AI 這種情況怎麼判的記憶卡）接在訊息後面。
- 並留帳給人事後回看判得準不準（[§7.10](../TECH.md#710-切入點契約程式問卡教llm-判留帳回看)）。

### 目前關著的閘（完整）

- 設定在 [`workflow/config.json`](../workflow/config.json)，使用者拍板；開關改回 true、`block_letters` 拿掉即恢復。
- **寫碼查核只擋 (a)(d)**（`reconcile_gate.block_letters`）：(b)(c)(e) 照判、只印 stderr。
- **目標樹對照不擋**（`reconcile_gate.goal_gate`）：
  - 目標樹照記。
  - 改程式前要有樹與提問掛節點照擋。
- **沒交收尾檢核不擋**（`aec.scan_report_gate`）：報告照收。
- **卡片表態不擋**（`atom_audit.enabled`）。
- **svn 提交測試路徑閘**（`overview_hub.svn_test_block.enabled`）：要的專案在自己的 [`.claude/overview-hub.json`](../.claude/overview-hub.json) 開。
- 下面各表寫的是閘開著時的完整行為。

## A7.1 Stop 閘序

[↑ 主文 §7.1](../TECH.md#71-stop-閘序)

入口：[`hooks/handlers/stop.py handle_stop`](../hooks/handlers/stop.py)。

- 一開頭（任何閘之前）：
  - 先把交付改程式的那則回覆丟背景文字評分（[§7.11](../TECH.md#711-文字規格評分g15toolstext-scorepy)）。
  - 把最後一句裡「順手看到最該修：…」段記進追蹤帳本（PickOne 列）。
  - 問一次連鎖斷路器（[§7.12](../TECH.md#712-連鎖斷路器hookswg_chainpy-判定libchain_storepy-帳與快照)）：中止中這一回合其餘閘只記錄不擋。
- 之後依序查（前者優先）。

### 擋次預算（完整）

- **共用一份**：退縮歸屬、AEC-Pending、Reload 建議、卡片表態與最底下的一般同步擋共用 `stop_gate_max_blocks` 2。
  - 第 3 次放行（放行時不另印訊息）。
  - 寫碼守門開時每個使用者回合重新計次；寫碼守門關時整個 session 累計。
  - 規則 [BLOCK_BUDGET_SHARED](../TECH/release-rules.md#block_budget_shared)。
- **紅測閘與寫碼查核**（ReconcileGate (a)～(d)）共用每個使用者回合一份 `reconcile_gate.max_blocks_per_turn`。
- **拐彎判斷**每個使用者回合最多擋一次。
- **第二意見、等值閘**各有自己的預算。
- **擋滿只認使用者放行**（[§7.3](../TECH.md#73-擋滿之後怎麼放行hookswg_releasepy)）；沒人能回答（headless／SDK、子代理、裁判）擋滿就放行並留帳。
- **閘自己判定出錯**：同一個錯誤每個使用者回合擋一次，之後放行並留帳（[GATE_SELF_ERROR](../TECH/release-rules.md#gate_self_error)）。

### TestFailGate

- **條件**：
  - 宣告完成，且本 session 有未轉綠的失敗測試。
  - 只認本 session 的條目；子代理內的紅測不記主 session。
- **綠怎麼清紅**：
  - 綠只清它涵蓋的紅（[GREEN_CLEARS_ONLY_CASES_IT_RAN](../TECH/release-rules.md#green_clears_only_cases_it_ran)）。
  - 綠點名整檔（沒 -k／-m）＝那檔裡紅掉的案例全跑到。
    - 路徑分隔、大小寫、./ 前綴、絕對路徑寫法不同也認得。
    - 跑到的記進那筆紅的 `cleared_units`。
- **紅的範圍怎麼存**（規則 [RED_SCOPE_FROM_FULL_COMMAND](../TECH/release-rules.md#red_scope_from_full_command)，`post_tool_use._test_scope`）：
  - 存解析後的目標，不存只有前 200 字的 `cmd`。
  - 內容是每段測試子命令＋點名的檔、目錄、節點、-k 這類篩選，與它前面的換目錄（cd／pushd／Set-Location）。
  - 跟指令多長無關、不截斷。
  - 判綠涵不涵蓋、新的紅取不取代舊紅、是不是重跑同一組都用它。
  - 這次的指令也解析成同樣的形狀來比。
  - 不用 `cmd` 的原因：截在 `2>&1` 中間會剩一個 `2` 被當成目錄，什麼重跑都涵蓋不到。
  - 認不出測試子命令就判不出目標：不拿片段當路徑，只認原樣重跑或列得出名字的紅被跑到。
  - 判不出目標、綠了卻沒涵蓋，都留帳 `Logs/guard-testfail_scope.jsonl`。
- **模式**：**照擋**（紅測）。
- **擋訊息**：
  - 抬頭「測試未綠：還有 N 支沒跑綠」，算支數不算筆數。
  - 真的有綠掉幾支才附「（M 支已綠）」。
  - 每筆只列還沒跑綠的那幾支（最多 3 支＋等 N 支；已清的絕不列）。
  - 附「重跑這幾支檔就夠：<那幾支所在的檔，去重>」。
  - 寫碼守門開關兩種訊息的失敗項同一份（`stop._red_item_lines`），關時只有出路文字照 9e476fd0。
- **block 要求**：修到綠，或寫「不做｜<哪一支>：使用者說「…」」。
  - 原句不再比對（[USER_WAIVER_NEEDS_CITATION](../TECH/release-rules.md#not_doing_declareduser_waiver_needs_citation)）。
- **基底紅**：
  - 改動前基底 commit 上就紅、追蹤文件也記了的那支。
  - 在基底的乾淨工作樹跑一次後寫「基底紅｜<那支>：<基底 commit> 也紅；追蹤 <文件>」。
  - 三件事實對得上才放（[BASE_RED_TRACKED_NOT_OWED](../TECH/release-rules.md#base_red_tracked_not_owed)）。
- **輸出沒列出是哪一支的紅**：
  - 擋訊息附「重跑這個範圍」：解析出的每段照抄照順序，別接 tail／head。
  - 判不出目標或長過 600 字就給「原指令完整照跑或跑整套」。
  - 綠了而且涵蓋就清掉；紅了照列出的那幾支記（列得出名字，「不做｜」才對得到）。
- **預算**：吃寫碼查核那份每個使用者回合的預算，擋滿照【收尾放行確認】問使用者。
- **判的時點**：
  - 紅只在宣告完成的收尾才判。
  - 沒宣告完成的回合不判、也不算判過，紅照留到之後哪個回合宣告完成。
- **判過不算的一律落帳、之後的收尾不再拿它擋**：
  - 使用者放行（user_released）。
  - 不做行（testfail_waivers）。
  - 收尾回覆寫「負向對照｜<那筆紅指令裡的字樣>：<理由>」，把那筆搬到 deliberate_reds（[NEGATIVE_CONTROL_DECLARED](../TECH/release-rules.md#negative_control_declared) 收尾入口，不必重跑）。
- **同一條指令跑了不只一次測試**：紅在記帳時就定案（[RED_LAST_RESULT_IN_COMMAND](../TECH/release-rules.md#red_last_result_in_command)）。

### ReconcileGate

- **目前只有 (a)(d) 擋**：
  - `reconcile_gate.block_letters`：(b)(c)(e) 照判、只印 stderr。
  - (f1)(f2) 因 `goal_gate=false` 不擋。
- **(a) 說修好**：看有沒有對得上改檔的 PASS。
  - 收據要晚於每個對上的改檔、同一棵樹、指令能當一般證據。
  - 不限本回合：舊回合的只要之後本 session 沒再改任何程式檔就算。
  - 子代理改的與判不出目標的寫入都算改；改過就要新的 PASS，擋訊息點名改了哪個檔。
  - 改檔所在部位也沒有合格的自寫收據。
- **(b) 說量了**：本回合沒有能當證據的 DONE，也沒有合格的自寫收據。
- **(c) 說試過**：本回合沒有任何 Bash／PowerShell 執行。
- **(d) 改了程式碼**，卻沒有本 session 新寫或改過、仍存在、同根的案例覆蓋它（規則 [CASE_COVERS_CHANGE](../TECH/release-rules.md#case_covers_change)）：
  - 覆蓋＝案例檔名 test_／verify_<模組名>、<模組名>_test。
  - 或內容提到它。
  - 或 AI 寫的「case_for｜<程式檔>：<案例…>」宣告行列了它。
  - 不比先後、不看跑綠。
  - PASS 不能代替；跨回合，不看措辭。
- **案例檔的定義**：
  - 符合 `verify_case_globs` 的程式檔（測試目錄或 test_／_test／.test／.spec 這類檔名，相對專案根比）。
  - 檔名剛好含 test 的產品檔不算。
- **知識類部位不算**：
  - 部位表類別 knowledge 的部位（文件、記憶、派工信箱）下的檔，兩邊都不算。
  - 不欠案例，也不能替寫碼部位清帳。
  - 判法看路徑屬哪一列，不看副檔名（`wg_verify_ledger.is_excluded`）。
- **改過又原樣還原的檔不算改碼**：
  - 條件：git 追蹤、git status 對它無輸出、本 session 第一次改它之後沒 commit。
  - 例：反證暫改再 `git checkout` 還原。
  - 補案例不欠；判不出來照算改了。
- **(e) 收尾報告欄**：AEC (j) 證據路徑缺或不存在、(k) 是空字串。
- **(a)(b)(c) 看什麼**：
  - 最後一句話（優先用 hook 輸入的 last_assistant_message，不套 30 字下限）。
  - 以及擋滿時記下的原宣稱（同一個使用者回合的續跑回合裡照查）。
  - 這時 (a) 認任一回合晚於改檔的合格 PASS（規則 [CARRIED_CLAIM_ANY_TURN_RECEIPT](../TECH/release-rules.md#carried_claim_any_turn_receipt)）。
- **主 session 另併需求目標的 (f2)**：交付邊界的完整對照（[§7.7](../TECH.md#77-需求目標樹need_goal)）；(f1) 改成程式記進度、不擋。
- **判定出錯**：同一個錯誤每個使用者回合擋一次，之後放行並留帳（[GATE_SELF_ERROR](../TECH/release-rules.md#gate_self_error)）。
- **模式**：照擋只 (a)（紅測類）；(d) 與其餘字母提醒。
- **預算**：
  - 紅測與寫碼查核（(a)～(d)）共用每個使用者回合一份 `reconcile_gate.max_blocks_per_turn`（2，不分哪一條規則，[BLOCK_BUDGET_SHARED](../TECH/release-rules.md#block_budget_shared)）。
- **擋滿的放行**：
  - 不自行放行：記 pending，要用 AskUserQuestion 照【收尾放行確認】問使用者。
  - pending 只在同一個使用者回合有效，使用者打字開新回合就失效、預算重給（[PENDING_SAME_USER_TURN](../TECH/release-rules.md#pending_same_user_turnrelease_covers_shown_itemsnoninteractive_release_at_budget)）。
  - 使用者要在最後一次擋之後選放行，或打字「放行」，才放這一回合，並記 user_release（健檢列 red）。
  - 之後的回合只沿用擋訊息列過的那幾件（[RELEASE_COVERS_SHOWN_ITEMS](../TECH/release-rules.md#pending_same_user_turnrelease_covers_shown_itemsnoninteractive_release_at_budget)，[§7.3](../TECH.md#73-擋滿之後怎麼放行hookswg_releasepy)）。
  - 子代理、裁判、headless／SDK 沒有人能回答：擋滿就放行並留帳（[NONINTERACTIVE_RELEASE_AT_BUDGET](../TECH/release-rules.md#pending_same_user_turnrelease_covers_shown_itemsnoninteractive_release_at_budget)）。
- **(e) 例外**：屬於記憶與報告類，照舊第 3 次放行，並寫 guard-reconcile_overflow（健檢列 red）。

### ReadingPath／TurnJudgment（閱讀路徑與拐彎判斷，G12＋G11）

#### 起跑與交付時點

- 背景 job：[`hooks/wg_reading_path.py --job`](../hooks/wg_reading_path.py)。
- 改了程式檔那批跑完就起跑：
  - PostToolBatch 看本回合改過的程式檔指紋，變了就起。
  - 量測中又改先記 pending。
  - 規則 [READING_PATH_EARLY_START](../TECH/release-rules.md#reading_path_early_startturn_judgment_pre_close)，開關 `reading_path.early_start`，關了照舊在收尾起。
- 量完的結果先存著，交收尾檢核或完整對照（need_goal reconcile）那批附上（[TURN_JUDGMENT_PRE_CLOSE](../TECH/release-rules.md#reading_path_early_startturn_judgment_pre_close)）。
  - 還有一批在量就不附。
  - 沒附到才由 Stop 送。

#### Python 量什麼

- 對本 session 改過的 Python 檔算入口拐彎數。
- 用 [`lib/turn_metrics.py`](../lib/turn_metrics.py)（純 ast）算 diff 命中的函式與類別的側面數據：
  - 巢狀深度
  - 各自巢狀的條件區塊
  - 認知複雜度加分點
  - 函式長度
  - 只轉手與連續轉手鏈
  - 繼承鏈每層新增／覆寫與空層
- **空層判準**（兩語言同一套 `turn_metrics.hollow_text`），算「這層沒加東西」的：
  - 只呼叫上層同名方法〔super()／base〕且引數照傳。
  - 補抽象宣告的空本體。
  - C# 引數照傳的空建構子。
  - 擋掉上層實作的空覆寫照列但不算空層。

#### C# 怎麼量

- `.cs` 不走整個專案的量尺與這張表，改走 [`lib/reading_path_cs.py`](../lib/reading_path_cs.py)。
- **範圍**：
  - 只量上次交工作以來變過的 .cs。
  - 照檔案指紋比，不照回合號：同一個使用者回合被擋後再改也量得到（state `measured`）。
  - 加一跳上下游。
  - 下游＝繼承、欄位／參數／區域變數型別、new、靜態呼叫指到的型別所在的檔。
    - 檔名對上的排前面，再 git grep 找全部型別的定義。
  - 上游＝git grep 提到改到的型別名的檔。
  - 上下游各最多 40 檔，截掉的註明。
- **比較方式**：
  - 範圍內的檔建 before（git cat-file 取 base 版）／after 兩張圖。
  - 用量尺同一個 Graph 與 compare。
  - 入口＝diff 命中的函式加範圍內直接呼叫它們的函式。
- **解析器**：
  - 本機有 .NET SDK 附的 Roslyn 就用 [`lib/cs_roslyn.py`](../lib/cs_roslyn.py)。
    - 第一次用時把 [`lib/cs_roslyn/`](../lib/cs_roslyn/) 小程式編進 `cache/cs-roslyn/<雜湊>/`。
    - Roslyn 只抓語法事實，分類規則照輕量解析同一批函式。
  - 沒有或跑不動用輕量解析（[`tools/reading_path_lang.py`](../tools/reading_path_lang.py)）並在 stderr 註明。
- 繼承鏈每層用 [`lib/turn_metrics_cs.py`](../lib/turn_metrics_cs.py)（查找池＝範圍，實作數標下限）。
- 範圍外的呼叫照外部算（路徑是一跳範圍裡看得到的那一段，不是整個專案的最短路）。
- C# 量不出不牽連同批 Python。
- **版控**：
  - git 根照上面的 before 比。
  - svn 工作副本（版控偵測同 `wg_verify_ledger._vcs_hit`）對 BASE 比。
    - 檔案清單與找鄰居不靠版控：有 ripgrep 用 rg、在專案根搜，沒裝就逐檔讀。
    - before 只對 `svn status --xml` 列出本地改過的檔 `svn cat -r BASE`（路徑尾端加 `@`；ANSI 字碼頁編不出的路徑不交給 svn）。
    - 查不到狀態的檔：改到的當新檔、鄰居當沒改過，並註明。
    - 沒改過的鄰居 before＝工作樹，改動行用 difflib 算。
  - svn 裡的 Python 不量（比較要 git 歷史，只報個數）。
- Python 與 C# 以外標不支援；量不出只列不問。

#### 門檻與提醒

- **模式**：提醒。
- **門檻**：`reading_path.turn_judgment`，預設拐彎 ≥2／巢狀 ≥3／條件塊 ≥2／轉手鏈 ≥2／繼承 ≥3 層或有空層。
  - 是「從第幾個彎起要人看」的事實門檻，不是判臭。
  - 到門檻的每一條都問。
- **C# 只在超線時問、才有字**：
  - 變差或新增的路拐彎 >`cs_layers`（3）。
  - 本次改到的函式只把呼叫往下傳（量尺的 passthrough；只呼叫上層同名方法的覆寫算在類別空層）。
  - 改到的型別繼承鏈 2 層以上有空層或 >`cs_layers` 層。
  - 同一入口只問最差一條，整段落在別條路裡的不另問。
  - 材料只列那幾層，一條最多 300 字（`CS_MATERIAL_MAX`）。
  - 沒超線 → 結果文字沒有 C# 的任何一行（不送模型）；量過的摘要記 `Logs/guard-reading_path.jsonl`（event=measured，lang=cs）、說明印 stderr。
- **Python 也超線才有字**：
  - 一個根沒有到門檻的條目，它的數據（尾行、可評級、最差一條、函式級數據表）不進結果文字。
  - 全文印 stderr、guard log 記 event=measured（lang=py）。
  - 量不出來的一句原因與沒量到的檔數照寫進結果。
- **只在超線時才提醒**（`reading_path.remind_only_over_threshold`，缺＝開）：
  - 收結果時扣掉已判過的，之後沒有任何一條要問 → 整段（含那些原因）不送模型、PostToolBatch 不附提醒行。
  - 只記 guard log event=under_threshold 與 stderr。
  - 至少一條要問才送條目＋那一題，PostToolBatch 的一行提醒最多列 3 條名字。
  - 關了照舊：結果文字非空就送。

#### 收尾那一行（TURN_JUDGMENT_REQUIRED）

- 收尾要有一行「拐彎判斷｜<函式、類別或入口>｜<這一層存在的理由與有沒有作用>｜<理由>｜<怎麼改直／合理，因為…>」，五欄齊。
  - 規則 [TURN_JUDGMENT_REQUIRED](../TECH/release-rules.md#turn_judgment_required)（[§7.8](../TECH.md#78-放行欠帳判定規則hookswg_release_rulespy)）；`turn_judgment_note` 核對。
- **擋點**在 Stop 的 TurnJudgment 段：
  - 寫碼查核（Reconcile）之後、SecondOpinion 之前。
  - ReadingPath 段只量不擋。
- **只問改到的**：
  - 答過的條目記名字＋內容指紋（函式比本體文字、類別比繼承結構、入口比實際路徑與數據）。
  - 之後量到同名同指紋的不再問。
  - 量完之前又改了碼，舊的那批只收答案、不擋（規則 [TURN_JUDGMENT_REQUIRED](../TECH/release-rules.md#turn_judgment_required)）。
- **缺的處理**：
  - 每個使用者回合最多擋一次（改碼也不重開）。
  - 列缺的條目與填好名字的範例行。
  - 一批最多問 `max_items`（8）條。
  - 擋下時尾段的閱讀路徑結果不再重複那一題。
  - 前面的閘擋下時 `[Guardian:AlsoOwed]` 預告「拐彎判斷：缺 N 條」（只報條數；`turn_judgment_missing` 只讀，不吃那一次）。
- **齊**：`Logs/guard-reading_path.jsonl` 記 judged。
- need_goal reconcile 沒給 turns 提醒一句；turns ≥4 要 note 寫「重找最短路：」。

### SecondOpinion（自動第二意見，G9）

#### 觸發條件

- **時點**（[SECOND_OPINION_FACT_TRIGGER](../TECH/release-rules.md#second_opinion_fact_trigger)，看事實不看措辭）：收尾。
  - 只有「還沒到收尾」不判：
    - 中途問使用者（最後一行是問句、沒宣告完成）。
    - 或寫明之後工作還在繼續（`wg_evasion` 判完成的排除詞第一類：仍在等、等待…回報、尚未開始）。
  - 而且這個使用者回合沒交收尾那批（`wg_second_opinion.not_closing`），留帳 event=deferred；欠帳留到下一次收尾。
- **規模**：本 session 改過的程式檔達大任務門檻：
  - ≥`second_opinion.auto.min_code_files` 4 檔。
  - 或對 HEAD 改動 ≥`min_changed_lines` 150 行。
  - 或改到高風險部位：部位表類別 gate 的列。
    - config 另列的 `risky_prefixes` 出廠空。
    - 記憶系統自己的高風險部位在 [`~/.claude/.claude/overview-map.md`](../.claude/overview-map.md) 標 gate。
- **出口指紋**（[SECOND_OPINION_EXIT_FINGERPRINT](../TECH/release-rules.md#second_opinion_exit_fingerprint)）：這組改動還沒交過出口。
  - 交了不需／等第二意見或跑過＋四行，就記出口時的改檔指紋（state `second_opinion_exit`），指紋沒變不再欠。
  - 出口是不需或等第二意見、之後又改了程式（改 1 支也算）再欠一次。
- **一輪了結**（SECOND_OPINION_ONCE_PER_CLAIM）：這一輪還沒了結。
  - 跑過、宣告不需或使用者放行之後，為採納意見做的修改不再要求。
  - 只有之後改到新的高風險檔、或之後新改的程式檔數再過門檻才算新一輪。
  - state `second_opinion_cover` 記已審過的高風險檔。
  - 前面回合跑完的第二意見也算基準（[SECOND_OPINION_RAN_BEFORE](../TECH/release-rules.md#second_opinion_ran_before)）：判的是跑完之後有沒有再改程式，不是有沒有換回合。
- **不觸發**：子代理、裁判、headless。
- 規則 [SECOND_OPINION_REQUIRED](../TECH/release-rules.md#second_opinion_required)／[SECOND_OPINION_DECLINED](../TECH/release-rules.md#second_opinion_declinedsecond_opinion_decline_accepted)（[§7.8](../TECH.md#78-放行欠帳判定規則hookswg_release_rulespy)）；事實 [`hooks/wg_second_opinion.py`](../hooks/wg_second_opinion.py)。

#### 要做什麼

- **模式**：提醒。
- 要本回合真的跑過 `second_opinion_start`（independent＋stage-review／evaluate）。
  - 且 `second_opinion_result` 回 done／failed／blocked。
  - session 有需求目標樹時，材料要帶到樹。
  - start 在前面回合、本回合才取回也算（[SECOND_OPINION_RESULT_ACROSS_TURNS](../TECH/release-rules.md#second_opinion_result_across_turns)）。
- 本回合任一則回覆有「第二意見與分歧裁決」段四行：Codex 結論／我方結論／分歧點／裁決與理由。
  - 被別的閘擋下後補件那則不必重抄。
- 或寫一行「不需第二意見｜<理由>」。
  - 留帳 `Logs/guard-second_opinion.jsonl`，週健檢列出。
  - 宣告行只看收尾最後一則，被收下就不擋（[SECOND_OPINION_DECLINE_ACCEPTED](../TECH/release-rules.md#second_opinion_declinedsecond_opinion_decline_accepted)）。

#### 背景模式

- 開關 `second_opinion.auto.background`（缺＝開）開時：
  - 擋訊息寫 start 後不用等結果、先把收尾其餘的事做完。
  - 收尾時還在跑，寫一行「等第二意見｜<job_id>」。
    - 那次不算宣告完成，只留帳 waiting（[SECOND_OPINION_BACKGROUND](../TECH/release-rules.md#second_opinion_backgroundsecond_opinion_done_notice)／[SECOND_OPINION_WAITING_NOT_DONE](../TECH/release-rules.md#second_opinion_waiting_not_done)）。
  - 開了的 job 跑完而 AI 還沒取回 → 下一批工具回應或收尾提醒一次（[SECOND_OPINION_DONE_NOTICE](../TECH/release-rules.md#second_opinion_backgroundsecond_opinion_done_notice)，state `second_opinion_watch`）。
  - `second_opinion_result` 跑完了馬上回、還在跑會等（每次最多 100 s，回 running 就再呼叫一次）。
  - MCP 端兩處說明同一個說法。
- 開關關：照舊，擋訊息寫 start 後直接呼叫 result、它會等到有結果。

#### 預附與預算

- 欠的那段先在收尾那批（收尾檢核或完整對照，`closing_call` 認）附上、跟 Stop 擋同一段。
  - 規則 [SECOND_OPINION_PRE_CLOSE](../TECH/release-rules.md#second_opinion_pre_close)（`wg_closing_round.so_pre_close`、`wg_second_opinion.owed_message`）。
  - 同回合指紋沒變不重附。
  - 那批沒出現或附了沒照做才由 Stop 擋。
- 每使用者回合擋 `max_blocks_per_turn`（1）次後擋滿。
  - 照 ReconcileGate 的放行規則問使用者（閘名 second_opinion，user_release 健檢列 red）。
  - 了結之後採納意見的修改不再要求。

### Equivalence（等值與熱路徑，G7）

- **條件**：
  - 本回合意圖是 refactor 或 perf。
    - `state.turn_intent`，只由使用者本人打的字判（`harness_text.user_typed_text`）。
    - 同伴訊息、背景通知沿用上一個意圖。
  - 本回合改過程式檔。
  - 宣告完成。
- **開關**：`overview_hub.equivalence.enabled`（hub 設定，[`lib/hub_config.py`](../lib/hub_config.py)）。
- **規則與位置**：
  - 規則 [REFACTOR_NEEDS_EQUIVALENCE](../TECH/release-rules.md#refactor_needs_equivalence)／[PERF_HOT_PATH_NEEDS_MEASURE](../TECH/release-rules.md#perf_hot_path_needs_measure)（[§7.8](../TECH.md#78-放行欠帳判定規則hookswg_release_rulespy)）。
  - 事實在 [`handlers/stop.py _equivalence_gate`](../hooks/handlers/stop.py)，排在 SecondOpinion 之後、Deferral 之前。
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
- **導讀卡端**：`goal_weights.refactor／perf.extra` 在視角／先問之後多送一段（等值三類、熱路徑一問、間接層一問）。

### Evasion 偵測／DeferralGate

- **條件**：
  - 退避詞命中（軟糾正）。
  - 主任務已完工：完成宣告 ∨ 本 turn 已 commit。
    - 完成宣告看整回合，別的閘擋下後補件那則不重說也算。
    - stop.py 以 `wg_second_opinion.turn_completion_text` 找本回合宣告完成的那一則。
    - 紅測、寫碼查核、收割、收尾檢核、自清、深度檢討、等值閘同一套。
  - context 用量 ≤0.75（讀 transcript 真實 usage）。
  - 收尾把帶受詞的可做之事推給「下個 session／獨立議題／非我造成」。
- **模式**：提醒。
- **擋回一問**（`wg_release_rules.CLOSING_ASK`）：「剩下沒做的，哪些改得快又有效？」
  - 快又有效的現在做掉。
  - 其餘每件寫一行「追蹤｜<哪一件>：<現在不做的原因>」，記進追蹤帳本。
  - 舊寫法「不做｜…」同一種宣告；「不做｜<哪一件>：使用者說「…」」的原句不再比對原話。
- **不標不擋的情形**（記 guard log `evasion_declared`／`deferral_declared`；規則 [NOT_DOING_DECLARED](../TECH/release-rules.md#not_doing_declareduser_waiver_needs_citation)）：
  - 退避語所在那一行對到有理由的追蹤／不做行。
  - 或說明句寫「不是退避｜<命中的詞>：因為 <理由>」。
- **[DEFERRAL_COVERS_EVASION_SENTENCE](../TECH/release-rules.md#deferral_covers_evasion_sentence)**（寫碼守門開時）：
  - 退縮閘這次擋下的那一句不再記退避旗標。
  - 下一則使用者訊息不再追問同一句。
- 使用者只說「先這樣／跳過」不再整段關掉偵測。
- 只在寫碼回合跑。

### KnowledgeHarvest

- **條件**：宣告完成 ∧ 有實質活動 ∧ 冷卻已過（[§6.3](../TECH.md#63-自動萃取在跑-vs-已停產) 階段收割；`wg_harvest.harvest_gate_reason`）。
- **模式**：提醒。
- **預設**：`harvest.background=true` 時不擋，改送背景收割（[§11.2](../TECH.md#112-守門減量同一件事只問一次記帳交程式或免費模型)）。
- **關掉或背景起不來時**：
  - 要求先 `atom_write`／`atom_retire`，再呼叫 MCP `knowledge_harvest_report`（沒東西也要 `items=[]`）。
  - **不增 `stop_blocked_count`**、每 turn 一次（`harvest_gate_turn[sid]`）。
- **放行**：近 3 則使用者本人打的字有「先這樣／跳過」→ 整批放行、留帳 `harvest_waived`（[§7.8](../TECH.md#78-放行欠帳判定規則hookswg_release_rulespy)「收割與收尾檢核的 dismiss」列）。

### Harvest-Pending

- **條件**：本 session 收割回報有 item 對不上 receipt（`knowledge_harvest[sid].pending` 非空）。
- **模式**：提醒。
- **動作**：每 turn 擋一次，要求真做完，或改 `action=skip` 附 reason 再重報。
- **放行**：使用者說先這樣／跳過整批放行（同 KnowledgeHarvest）。

### Cleanup（收尾自清）

- **條件**：宣告完成，本 session 帳上有建立紀錄、還在、沒說要留的：
  - 工作樹
  - 已合併分支（被列出的工作樹用著的也算）
  - 能刪的臨時 repo
  - 專案外檔案資料夾
- 規則 [LEFTOVER_NEEDS_CLEANUP](../TECH/release-rules.md#leftover_needs_cleanup)；事實 `aec_ledger.cleanup_facts` 現場查，只為可能成為候選的幾筆跑 git，帳再長收尾也不變慢。
- **不列**：
  - 沒合併的分支
  - 暫存區
  - 專案裡未進版控的新檔
  - gitignore 的
  - 遠端分支
  - 別的開著的 session 正在用的
  - 開場快照比對出來（來源不明）的
- 「說要留」＝HUD 按過保留或 (i) 寫過理由。
- **模式**：提醒。
- **動作**：
  - 列每一項與刪除指令（[`session-artifacts.py act --sid … --key …`](../tools/session-artifacts.py)，結果寫回帳本）。
  - 要留的在 (i) 寫理由（分支 `branch:<名> — 理由`）。
  - **不增 `stop_blocked_count`**、每 turn 一次（`cleanup_gate_turn[sid]`）。

### ScanReport

- **目前不擋**：`aec.scan_report_gate=false`；報告照收、HUD 照開。
- **開著時的條件**：宣告完成且動 core 檔或多檔。
- **模式**：提醒。
- **動作**：要求以 MCP `anti_evasion_report` 提交十欄收尾檢核 (a)(b)(d)–(k)（沒有 (c)）。

### AEC-Pending

- **條件**：
  - 本回合 emit 的報告 (d) 有「尚未寫／見下一動」。
  - 或 (h)「下一動＝寫 atom」。
  - 本 turn 已 validated 收割時 (d) 不再判。
- **模式**：提醒。
- **動作**：每 turn 擋一次，先 atom_write 再重新 emit（記憶寫入不得留給下一回合）。

### HUD fallback

- **條件**：HUD 不可達且本回合 emit 為 notable/real-evasion。
- **動作**：
  - 不 block、報告不貼回聊天（原設計者裁定）。
  - stderr 印一行：判死原因、報告檔位置、HUD 網址（可觀測性鐵律）。

### Reload 建議（規則 RELOAD_ADVICE_ALREADY_LOADED）

- **條件**：
  - 收尾叫使用者 Reload Window，但每個活著的工具服務（MCP server）都已載入磁碟上最新的程式。
  - 本 session（含子代理）沒改過路徑含 [`tools/workflow-guardian-mcp/`](../tools/workflow-guardian-mcp/) 的檔就整個不判（[RELOAD_ADVICE_MCP_EDITS_ONLY](../TECH/release-rules.md#reload_advice_already_loadedreload_advice_mcp_edits_only)）。
- **模式**：提醒。
- **動作**：
  - 擋一次：拿掉那句。
  - 真有程式以外的理由（改了 MCP 啟動設定、settings.json）就保留並加一行「重載原因：<哪個設定改了>」。
  - 每個使用者回合一次、吃共用預算。

### 同步閘（SyncReminder）

- **兩段**：
  - SyncReminder：本 session 改的檔有 1 個沒 commit、或已 commit 但 repo 領先 upstream 沒 push 就擋。
    - `sync_reminder.max_reminders` 1，每 session 一次。
  - 之後最底下的一般同步擋：才看 ≥`min_files_to_block` 2 檔，吃共用預算。
    - 先剔除已 commit 並 push 的檔再判門檻（規則 [SYNC_BLOCK_SKIPS_SYNCED](../TECH/release-rules.md#sync_block_skips_synced)）。
- **不要求 push 的情形**：
  - root 有 vcs-sync worker 活鎖（`wg_harvest.vcs_sync_lock_active`）時跳過該 root 的 unpushed 判定。
  - 改檔所在 repo 是 git worktree（git-dir ≠ git-common-dir）或分支沒有 upstream（規則 [WORKTREE_NO_PUSH](../TECH/release-rules.md#worktree_no_push)）。
- **跳過的 session**：
  - 兩段都跳過 phase 是 done／syncing 的 session。
  - 收尾或 SessionEnd 設的 done，在下一則話（UserPromptSubmit）改回 working（規則 [PROMPT_REOPENS_DONE](../TECH/release-rules.md#prompt_reopens_done)）。
  - 第一回合收得乾淨之後的回合（含續接）照樣會判。
- **模式**：提醒。
- **動作與訊息**：
  - block，訊息瘦身不列檔案清單。
  - 本回合交了收尾檢核就不擋、只印 stderr（(g) 已交代，SYNC_COVERED_BY_CLOSING_CHECK）。
  - 底部一般擋只剩待記知識或文件漂移才擋，改檔數只印 stderr（SYNC_BLOCK_NOT_REPEATED）。
  - 同一筆前面回合擋過就不再擋、有新的一筆才擋（[SYNC_BLOCK_NEW_ITEMS_ONLY](../TECH/release-rules.md#sync_block_new_items_only)）。
  - UPS 的 Sync context 只印 stderr。
  - 上GIT＝commit+push 一氣，local commit 不算同步。
  - git/svn clean 且 push 後自動標 `sync_completed`（`sync_reminder.unpushed` 可關）。

### AtomAudit（卡片表態）

- **目前不擋**：`atom_audit.enabled=false`。
- **開著時的條件**：本 session 有 trigger 命中但只以路標注入、且未 Read。
- **模式**：提醒。
- **動作**：要求讀取或表態（取用端閉環稽核）。

### 驗收裁判（Stop 端）

- **形式**：獨立 hook `codex_companion.py`，寫碼守門開時才跑。
- **行為**：
  - Stop 只起背景審查、立即放行。
  - 結果在下一則使用者訊息附一行。
  - fail 且 severity ≥high 才附完整說明（[§7.4](../TECH.md#74-驗收裁判ai-審查-ai-產出四段閉環)）。
- **模式**：獨立 hook、不經 RULE_MODE；永不 block。
- 裁判逾時 → 下一則附「uncertain」。

### Deep Post-Mortem

- **條件**：effort AND real_failure。
  - 使用者糾正 ≥2 次單獨即同時滿足兩者（見 [§7.5](../TECH.md#75-其他守門) 使用者糾正訊號）。
  - effort 的重試只數「紅了、改了、再跑仍紅」的輪數。
  - 刻意紅（退回舊碼反證）不算（規則 [RETRY_COUNTS_RERUN_CYCLES](../TECH/release-rules.md#red_while_revertedretry_counts_rerun_cyclesgreen_same_case_clears)／[RED_WHILE_REVERTED](../TECH/release-rules.md#red_while_revertedretry_counts_rerun_cyclesgreen_same_case_clears)）。
- **模式**：提醒。
- **動作**：
  - one-shot，**獨立預算**不與上列共用（防餓死）。
  - done 旗標檔案側 marker 7 天自清。
  - 不分在不在 git worktree，一律叫 atom_write 寫到資料根。

### PickOne（交付時順手點出最該修）

#### 條件

- `pick_one.enabled` 開。
- 到交付邊界：最後一句或 >30 字段落宣告完成、本回合交了收尾檢核、本回合 commit。
- 本 session 在上次問過或記過之後又改了程式檔（寫碼類判準 `wg_need_goal.is_code_path`）。

#### 何時送

- 先在交收尾檢核或完整對照那批附上（[PICK_ONE_PRE_CLOSE](../TECH/release-rules.md#pick_one_pre_closepick_one_with_turn_judgment)，開關 `pick_one.pre_close`）。
  - 附了就記問過，Stop 不再送、不再讓對話續跑一輪。
- Stop 的拐彎判斷擋下時同一則一起問（[PICK_ONE_WITH_TURN_JUDGMENT](../TECH/release-rules.md#pick_one_pre_closepick_one_with_turn_judgment)）。
- 兩處都沒走到才排在所有閘之後。

#### 動作

- **不擋**：回 `hookSpecificOutput.additionalContext`（對話續跑一回合，不是 block）。
- 送一次的內容：「這次看到的鄰近問題裡哪一件最該修、為什麼、為什麼不是數字最高的那個、建議怎麼解、該誰解」。
- **材料依部位分組**（數字都標參考、不排名）：
  - 表上「下游」
  - 導讀卡已知病灶前 2 條
  - 壞味道報告前 2 名附分數與呼叫點
  - 改到的檔行數
  - 未結追蹤項筆數

#### 呼叫點（`wg_harvest._callsites`）

- 在專案根 `git grep -l` 找含那個檔模組名的檔。
- Python 逐檔用 ast 看 import／from（看被匯入的名字不看別名，多行括號匯入照算）。
- JS／TS 逐行比 import／require 路徑（註解行不算）。
- 回「呼叫點 N（誰）」。
  - 測試檔另計「另有測試 N 支」。
  - 解析不了的另記「N 支解析不了沒算」。
  - 檔裡有 `__main__` 補「本身可直接執行」。
- 其他語言、檔名不是合法模組名、不在 git、逾時（整次材料共用 `CALLSITE_BUDGET_S` 2 秒）回「呼叫點 無法判（原因）」。
- 以模組名比對，同名模組會一起算；動態載入、路徑字串、子行程呼叫不算。

#### 只問一次

- 同一批改動只問一次，同一個使用者回合也只問一次（`pick_one[sid].asked_uturn`／`covered_uturn`）。
  - 照使用者回合比：這一問讓對話續跑一回合，續跑回合不算新的一批。
- 這次收尾是不是 Stop hook 續跑出來的（輸入帶 `stop_hook_active`）不當條件（[PICK_ONCE_PER_USER_TURN](../TECH/release-rules.md#pick_once_per_user_turn)）。
  - 第一次收尾先被別的閘（例：紅測閘）擋下、修完續跑收尾，照樣問這一次。
- 交付邊界也記整個使用者回合（`pick_one[sid].boundary_uturn`，各閘之前先記）。
  - 宣告完成那次被擋、之後沒被擋的那次回覆在答別的閘沒再說完成，照樣問。
- state 沒有 `turn_prompts_seq` 時，續跑收尾不重問已經問過的。
- 回合鍵在 state 重建時照搬、不在時錨在第一則訊息（[USER_TURN_KEY_KEPT](../TECH/release-rules.md#user_turn_key_kept)），只進同伴訊息的那段不會每則重問。
- 連鎖中止中不送。

#### 記進追蹤帳本

- 每次 Stop 開頭（任何閘之前），把最後一句裡照格式寫的「順手看到最該修：…」段記進追蹤帳本。
  - `source=pick`，另存 why／not_top／proposal／owner；同段不重記。
- **同 session 同回合同部位又點出同一件但文字略異**：
  - 判法 `same_pick_target`：去括號旁註與標點後相同、或一句是另一句開頭。
  - 只看檔名識別字或字面相似度不算，同函式的不同問題不併。
  - 換成第二次的說法：同一次追加兩列，先寫新 open 列（標 `supersedes`）、再寫結案列關掉第一筆（`superseded_by`）。
  - 帳本只追加不改寫，中途斷掉最多多一筆重複，清理器照結案成對處理。
  - 寫不進去：stderr、事件 update_failed、第一筆照留。
- 「無，因為…」不記但算答過（`covered_turn`）。
- SessionStart 先列附了建議的未結項（不分部位，最新 3 筆，要 AI 第一則回覆告訴使用者）。

#### 同一件不重記（TRACKING_SAME_ITEM_NOT_REWRITTEN）

- 唯一寫入口 `append_tracking`；k 欄、need_goal followup、PickOne 都過。
- 部位相同且原文相同 → 不重記（字面相近不併，併錯會吞掉一件）。
- 換句話說的同一件，由 AI 在行尾寫「｜同追蹤項：<那筆裡連續至少 8 字>」。
  - PickOne 段多一行「同追蹤項：」，問句列出本 session 還開著的項目。
  - 對到唯一一筆就換成新說法（supersedes＋結案成對）。
  - 對不到或多筆照記並 stderr。
- 判斷全交 AI，`wg_harvest` 只管時點與記帳。

### 迴歸提示

- **條件**：本 session 有驗收 fail/high 真命中。
- **動作**：piggyback 建議補測試／落 atom，每 session 一次。

### 子代理與裁判的 Stop

- SubagentStop 與裁判子 session（`CLAUDE_COMPANION_JUDGE=1`）的 Stop 只跑寫碼查核（`stop._code_gate_no_ask`）。
- 跟主 session 同一份預算，擋滿就放行並留帳（event=`*_released`），不問使用者。
- 寫入目標判不出的指令放行並留帳（UNKNOWN_TARGET_LOGGED）。

### 超時降級

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
  - UserPromptSubmit：跳過脈絡、導讀卡、檢索與注入組裝；前置閘、記原話、寫 state 照做，附一行說明。
  - PostToolUse：
    - 只跳過提示類段落（導讀卡、depends 召回、跨 session 碰撞、同伴檢查、MCP 切入點註記）。
    - 改檔記帳、目標樹蓋號、寫 state 照做。
  - PreToolUse：只打點不改判定（逾時被取消本來就放行，提早放行只會少查）。
- **單一段落跑過上限**：
  - 打點只在段落之間，單一段落一路跑過上限打不到點，所以起表時另排背景鬧鐘。
  - 到上限 95% 還沒結束就先寫一筆 kind=overrun（卡在哪一段之後、有沒有代送）＋stderr。
  - SessionStart／UserPromptSubmit 登記了代送輸出、正常輸出還沒送時，鬧鐘接著代送已備好的那份並結束行程，搶在取消前送出。
- 每次 hook 結束另寫一筆 kind=run；[`python tools/hook-timing.py`](../tools/hook-timing.py) 看各段中位數。

### 擋訊息格式與回合定義

- 寫碼查核的每一條擋訊息都是一條有名字的規則（[`hooks/wg_release_rules.py`](../hooks/wg_release_rules.py)，規則表 [§7.8](../TECH.md#78-放行欠帳判定規則hookswg_release_rulespy)）。
- 格式：`✗ (<字母>) <規則名>：<一句現象>｜證據：<一行一證據>`。
- 擋次預算每個使用者回合共用一份、不分是哪一條規則（[BLOCK_BUDGET_SHARED](../TECH/release-rules.md#block_budget_shared)），擋滿訊息列出全部命中條目。
- 「回合」＝使用者打字開的回合；同伴訊息、背景通知都不開回合（[TURN_SINCE_USER_PROMPT](../TECH/release-rules.md#turn_since_user_prompt)）。

### 定死規則（寫碼查核相關，改法不得放寬）

- CommitOrder 豁免：commit 落在記憶系統 repo 或其 worktree 才不等口令。
  - 只認 `&&` 串的 `cd <絕對路徑>`／`git [-C <字面路徑>] add|commit|push` 句型。
- git checkout 只給一個參數：
  - 現存檔＝還原該檔。
  - 現存目錄＝目標不明。
  - 都不是＝切分支，不算寫入。

## A7.2 反退避（Anti-Evasion）

[↑ 主文 §7.2](../TECH.md#72-反退避anti-evasion)

### 禁語清單

- **位置**：[`memory/_meta/forbidden-phrases.json`](../memory/_meta/forbidden-phrases.json)（single source；IDENTITY.md 與 `wg_evasion.py` 都讀它）。
- **六類退避語**：
  - scope-evasion
  - time-deferral
  - precedent-drift
  - capability-evasion
  - scope-impact-dismiss
  - deferral-attribution
- **三類宣稱**（對帳閘用）：fixed_claim／measured_claim／tried_claim。

### 閘與 MCP 字句不中詞表（規則 GATE_TEXT_AVOIDS_EVASION_WORDS）

- **位置**：
  - py 端：`hooks/verify/verify_evasion_guard.py::test_gate_texts_do_not_trip_evasion_detector`。
  - js 端：[`tools/workflow-guardian-mcp/verify/verify_mcp_texts_avoid_evasion_words.py`](../tools/workflow-guardian-mcp/verify/verify_mcp_texts_avoid_evasion_words.py)。
- **原因**：AI 照抄被擋的那則訊息時，偵測不開引用豁免，所以擋訊息與提示自己不用會中詞表的字句。
- **py 端怎麼測**：
  - hooks／lib 的 Python 字串字面值逐條跑 `wg_evasion.detect_evasion`。
  - f-string 插值換 X、`+` 串起來的併成一條。
  - 不算：
    - docstring
    - 正則來源（`re.<函式>` 的第一個參數、lazy_re／_compile_union 的參數、名字以 _RE／PATTERNS 結尾的常數）
    - RULES 說明表
    - 印到 sys.stderr 與留帳呼叫的參數
- **js 端怎麼測**：
  - 切出 `tools/workflow-guardian-mcp/lib/*.js` 與 [`server.js`](../tools/workflow-guardian-mcp/server.js) 每個字串字面值（樣板字串插值換 X），逐條跑 `wg_evasion.detect_evasion`（詞表就是它載入的那份）。
  - 不算：
    - 註解
    - 正則
    - require 路徑
    - 物件的鍵（介面鍵）
    - stderr／crashLog 參數
    - 給人看的儀表板與 HUD 頁模板
- 命中就改說法，不加豁免。

### 偵測

- **位置**：Stop `wg_evasion.detect_evasion`，對本輪最後一段 assistant 文字。
- **先遮蔽引用**：引號「」『』與反引號 span 先換等長空白（引用 hook 判定原文不誤觸）。
- **聲明豁免**：命中的那一行對到下列任一種，這一處不標、記 guard log `evasion_declared`：
  - 「不做｜<哪一件>：<理由>」（理由非空、不是佔位）。
  - 「不做｜<哪一件>：使用者說「<原句>」」（原句在近 3 則使用者原話裡）。
  - 各類的 `exception` 文字附在提示裡，告訴 AI 理由要寫什麼。
- **命中後**：
  - 記 `evasion_flag`（帶 category 與不做行寫法提示）。
  - 下輪 UPS 注入舉證要求 (a)/(b)/(c)。
  - PostToolUse 只讀旗標做 AEC cross-check。
- **context 豁免**（規則 [EVASION_CONTEXT_EXEMPT](../TECH/release-rules.md#evasion_context_exempt)）：四件都有證據才不標記（記 guard log `evasion_exempt`），判不出照標：
  - context 用量超過 deferral_gate.max_context_ratio。
  - 命中的是延後到下個／新 session 或之後再（詞表 context_exempt_deferral）。
  - 本回合 (k) 有內容或寫了交接檔。
  - 本回合使用者原話在且沒叫現在做。
- 詞表排除「範圍外的測試／案例」與「新 session 才會載入／生效」這類正常敘述。

### 收尾報告

- **MCP `anti_evasion_report` 一份交完**（規則 CLOSING_REPORT_ONE_CALL）：
  - `report`＝給讀者的白話全文（做了什麼／驗了什麼／沒做什麼／追蹤項），工作軌原文就是交付信。
  - 給了 `report`，e／f／g 可省（Node 端沒給 report 照擋）。
  - `harvest_items` 帶收割清單就不必另叫 knowledge_harvest_report（同一套核對）。
- **欄位**：參數名 a、b、d、e、f、g、h、i、`j_evidence_path`、`k_followups`；沒有 c。
  - a 缺失修補
  - b 逃避通報
  - d 記憶收錄帳：本回合已交核對過的收割報告可只寫「見收割報告」，沒交就記 d_pending
  - e 未告知決策＋假設
  - f 靜默狀態改變
  - g 版控收尾
  - h 收尾判定
  - i 衍生暫存清單
  - j 證據持久路徑：
    - 有驗證收據時須存在。
    - 留空或「無」由 Python PostToolUse 帶入本 session 帳本絕對路徑 `<資料根>/workflow/verify-ledger/<sid>.jsonl`。
    - 填了別的就用填的。
  - k 追蹤項：
    - 「無」或逐行；≠無 寫 `workflow/tracking/<slug>.jsonl`。
    - 行尾可寫「｜建議：<怎麼解>｜該誰解：<誰>」，帳本列另存 proposal／owner，開場先列。
- (j) 缺或不存在、(k) 是空字串，由寫碼查核的 (e) 判（規則 [AEC_EVIDENCE_PATH](../TECH/release-rules.md#aec_evidence_path)／[AEC_FOLLOWUPS_EMPTY](../TECH/release-rules.md#aec_followups_empty)）。
- severity 只看 a/b，其餘資訊性。
- MCP 回條一行（`aecChipText`，報告不進聊天）；要模型補的事只由 Python PostToolUse 回告。
- **Python one-writer cross-check**：hook 實測退避而模型自評「無」→ 升 real-evasion（HUD 顯示「疑似偷懶（待核對）」）並把證據寫進 (b)。

### HUD

- **位址**：`http://127.0.0.1:3848/aec/hud`。
- **「收尾檢核」分頁**：
  - 白話卡片：燈號＋一句話。
    - ✅ 可以關了
    - 🟡 有事要你決定
    - 🔴 疑似偷懶（待核對）→ 要你處理
  - 順序：要你處理 → 這輪做了什麼 → 記住了／之後要追。
  - 欄位字母與原始內容收進「細節」。
  - 「這個 session 留下的東西」面板（保留／刪除鈕）。
- **「全機殘留」分頁**：全部帳本還在的東西依 session 分組。
- **彈窗時機不變**：窗沒開、`aec.hud_autospawn` 開著、severity 為 notable／real-evasion 才開窗（使用者選的）。

### 產出物帳本

- **位置**：`workflow/aec-tempfiles/<sid>.jsonl`（[`handlers/aec_ledger.py`](../hooks/handlers/aec_ledger.py) 唯一寫者）。
- **PostToolUse 依工具呼叫進帳**：
  - Write 寫的檔。
  - Bash 寫入目標（mkdir、轉向、cp…）。
  - git 建的工作樹／分支／臨時 repo（init、clone）／推上遠端的分支。
  - 另收 (i) 宣告（路徑，或 `branch:<名> — 理由`）與 scratchpad 掃描。
- **開場快照比對**：
  - Stop 拿 SessionStart 記的開場快照（cwd 所在 repo 的工作樹與本地分支，`state.git_snapshot`）比對。
  - 多出來又沒建立紀錄的進帳標 `source=snapshot`（HUD 顯示來源不明）。
  - 用途：補 python 腳本裡開工作樹這類指令解析看不到的。
- **還在不在、能不能刪**現場查（檔案系統與 git）：
  - 進了版控的檔掉出清單。
  - 主分支、工作樹正在用的分支、session 工作目錄與它的上層不能刪。
  - 別的開著的 session（state 檔 30 分鐘內有更新）工作目錄在裡面或改過讀過裡面的檔 → 標正在用、刪除要再確認。
  - 路徑比對用 realpath（系統暫存區的 8.3 短檔名與長檔名同一處）。
  - 受保護路徑（memory/_AIDocs/_INDEX/_CHANGELOG/CLAUDE/…/vcs tracked）拒收。

### 保留／刪除

- **路徑**：HUD → Node `POST /api/aec/decision` → [`tools/session-artifacts.py act`](../tools/session-artifacts.py)。
- 當場執行、結果寫回帳本並顯示在該列。
- 要使用者在 HUD 再確認一次才帶 force 的：
  - 沒合併的分支
  - 有改動的工作樹
  - 遠端分支
  - 整個 repo
  - 別人在用的
- 只能指名帳上那一項。
- 列表：`GET /api/aec/tempfiles/<sid>` → [`session-artifacts.py list`](../tools/session-artifacts.py)（Node 快取 10 秒）。

### 全機殘留

- **路徑**：HUD「全機殘留」分頁 → Node `GET /api/aec/tempfiles-all` → [`session-artifacts.py list --all`](../tools/session-artifacts.py)（快取 30 秒，按任何鈕作廢）。
- 掃全部帳本只列還在的，依 session 分組並附 session 狀態（開著／多半已關／已關）。
- 同一樣東西由有建立紀錄的 session 認領。
- 每組「清掉不用再確認的」→ `act --all-safe`：
  - 要再確認的、按過保留的、來源不明的不動。
  - 其餘逐項照 act 的保護規則刪。

### 遙測

- **檔案**：`Logs/guard-evasion.jsonl`、`workflow/outcome_stats.jsonl`。
- unknown 比率連續 3 session >0.7 → advisory。
- 用途：誤攔率可量測；完成語 regex 失配不會靜默拖垮晉升軌。

## A7.3 擋滿之後怎麼放行（`hooks/wg_release.py`）

[↑ 主文 §7.3](../TECH.md#73-擋滿之後怎麼放行hookswg_releasepy)

目的：寫碼類的查核閘擋滿次數後，AI 不能自己放行、也不能改寫措辭繞過，決定權交回使用者。用在紅測閘、寫碼查核（ReconcileGate）、第二意見、等值閘。

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
  - 紅測的指令＋全部失敗節點。
- 原因還在不再問、原因消失就拿掉。
- 寫碼查核放行之後又改了檔，整份不再沿用。
- 新出現的原因照擋。

### 沒人能回答的情境

- 對象：裁判子 session、子代理、headless／SDK 主 session。
- 不叫它問。
- 寫碼查核、紅測、等值證法照預算擋，擋滿就放行並留帳。
  - 主 session event=noninteractive_released。
  - 子代理與裁判 `*_released`。
- 擋訊息不說「不能放行」（規則 [NONINTERACTIVE_RELEASE_AT_BUDGET](../TECH/release-rules.md#pending_same_user_turnrelease_covers_shown_itemsnoninteractive_release_at_budget)）。

### 與提問閘的關係

- 提問閘（[§7.7](../TECH.md#77-需求目標樹need_goal)「問使用者之前」）認得這種放行題。
- 真有擋滿待放行紀錄時，放行題不必掛目標節點。

## A7.4 驗收裁判：AI 審查 AI 產出（四段閉環）

[↑ 主文 §7.4](../TECH.md#74-驗收裁判ai-審查-ai-產出四段閉環)

先給裁判**案卷**（任務專屬驗收標準）再談能力——通用直覺審必然低精度。

### 總開關與只記錄

- 整段歸守門總開關：寫碼守門關著（出廠）時，兩個觸發處（收尾宣稱完成、規格檔標 done）都不跑。
- 規格工件的兩種提示也不送（規格檔落盤照記）。
- 寫碼守門開著時：
  - 裁判只在背景審。
  - 記 `workflow/acceptance-audit.jsonl`。
  - advisory 照注，**一律不擋收尾**；沒有改成硬閘的開關（[`hooks/verify/verify_acceptance_review.py`](../hooks/verify/verify_acceptance_review.py) 的 `test_no_sync_gate_left_in_hook` 守著擋收尾的程式路徑不再長回來）。
- 為什麼不擋：擋收尾會讓「改 → 驗收 → 再改 → 再驗收」無限擴張，裁判只記錄、結果交人看。

### ① 規格工件

- **切入點**：[`hooks/acceptance_spec.py`](../hooks/acceptance_spec.py)（由 guardian PostToolUse 同程序呼叫 `run()`）。
- **機制**：
  - ExitPlanMode → 從 plan 落 `<專案根>/.claude/verify/acceptance-<slug>.md`（必須發生／禁止發生／驗證指令）。
  - 無 plan 但改 ≥3 檔 → 一次性建議。
  - advisory-only。

### ② 影子裁判

- **切入點**：[`tools/codex-companion/acceptance.py`](../tools/codex-companion/acceptance.py)。
- **機制**：
  - Stop 完成宣稱觸發。
  - 任務↔規格**四分流**：bound 才審；ambiguous / other_session / none → uncertain 不發。
  - 案卷＝需求原話＋清單＋diff 頭尾採樣＋測試輸出，截斷必 in-band 標記。
  - verdict pass/fail/uncertain → `workflow/acceptance-audit.jsonl`。

### ③ 背景審

- **切入點**：`codex_companion.py` Stop。
- **機制**：
  - Stop 不等：起背景審查、立即放行。
  - 結果落 assessment 檔，下一則 UserPromptSubmit 附一行。
  - fail ∧ high 附完整說明。
  - 配額分桶 acceptance 上限 8／保底 6。

### ④ 迴歸提示

- **切入點**：[`stop.py _acceptance_regression_hint`](../hooks/handlers/stop.py)。
- **機制**：見 7.1（迴歸提示列）。

### 裁判後端鏈

- 位置：[`tools/codex-companion/judge_backend.py`](../tools/codex-companion/judge_backend.py)。
- 順序：
  - codex：跨廠。
  - → headless `claude -p --model sonnet`：同廠不同模型，獨立性較低。
  - 不論哪個後端，結果都只當 advisory。
  - → 皆無退 heuristics-only，並 SessionStart 揭露一次。
- 授權類失敗（未登入/401/429）：
  - 當輪切備援。
  - 落 `workflow/companion-backend.json` 抑制，`reprobe_hours` 24 內不重試。
- 備援子 session 帶 `CLAUDE_COMPANION_JUDGE=1`，自家 hook 見之早退（防裁判觸發裁判）。
- **殺閘寫死在程式**（`promotion_stats()`）：fail ≥10 筆且 precision <50% → 收掉。

## A7.5 其他守門

[↑ 主文 §7.5](../TECH.md#75-其他守門)

每道守門一個 `###` 區塊，順序與原表一致。主文 [§7.5](../TECH.md#75-其他守門) 依「什麼時候檢查」分組列出一行摘要。

### lang_guard
- **位置**：[`hooks/lang_guard.py`](../hooks/lang_guard.py)（Stop）
- **先剝掉這些再算英文佔比**：
  - code fence、inline code、URL、link 目標
  - 沒包反引號的路徑：含斜線的字要像路徑才算，條件是反斜線、冒號、兩個以上斜線、`/` `~` `.` 開頭或帶副檔名；`input/output` 這種英文斜線詞照算英文
  - 檔名與帶點名稱、底線識別字、指令旗標
- **判定**：剩下的英文佔比 ≥0.5（且 ≥40 語言字元）→ additionalContext 繁中提醒
- **續跑**：提醒後續跑一回合，`stop_hook_active` 時不再提醒
- **其他**：stateless；留帳 `Logs/guard-lang.jsonl`

### plan_bash_guard
- **位置**：[`hooks/plan_bash_guard.py`](../hooks/plan_bash_guard.py)（PreToolUse Bash）
- **何時動作**：只在 `permission_mode=plan`
- **背景**：
  - CC 原生只把 `sed -n 'N,Mp'` 當唯讀，正則位址一律當寫入
  - 路徑含 `.claude` 片段屬敏感檔 → safety check，allow 規則與 hook allow 都壓不過（debug：`Hook returned 'allow' … safety check requires full permission pipeline`）
  - `cd /c/...` 同屬 safety check
- **動作**：對 cd／sed 非列印腳本觸及 `.claude`／rm-mv-cp-touch-mkdir-chmod／未引號 `>` 回 deny，並提示改用 Read/Grep；其餘不表態
- **其他**：stateless

### SvnEncoding
- **位置**：[`hooks/handlers/pre_tool_use.py check_svn_encoding`](../hooks/handlers/pre_tool_use.py)（PreToolUse Bash／PowerShell）
- **觸發**：`svn add` 帶非 ASCII 路徑
- **動作**：`[Guardian:SvnEncoding]` 一行提醒，改交 vcs-sync 背景提交（advisory，零子行程、不 deny）
- **為什麼會壞**：
  - svn.exe 以 ANSI code page 收 argv，code page 外字元被 best-fit 成別字
  - `add --parents` 會在磁碟建出亂碼目錄（某專案 `shared/UIºt¥X`＝`UI演出`）
  - cp950 內中文走 worker 安全；`--targets` 無效
- **worker 端**：
  - `wg_vcs_sync._Svn.run` 對編不進 ACP（`GetACP`）的 argv 直接 `_Stop`、不呼叫 svn（落 last_error／.unpushed）
  - `_Svn.err` 解碼 utf-8 失敗退 ACP
- **相關**：偵測端見 [§8](../TECH.md#8-可觀測與自我維護) 亂碼名稱；守門 [`hooks/verify/verify_svn_unicode_paths.py`](../hooks/verify/verify_svn_unicode_paths.py)、[`lib/verify/verify_encoding_guard.py`](../lib/verify/verify_encoding_guard.py)

### SvnTestBlock
- **名稱**：svn 提交測試路徑閘
- **位置**：[`hooks/handlers/pre_tool_use.py check_svn_test_block`](../hooks/handlers/pre_tool_use.py)（PreToolUse Bash／PowerShell 的 svn commit）
- **性質**：照擋（不在範圍）
- **預設關**：專案 [`.claude/overview-hub.json`](../.claude/overview-hub.json) 寫 `svn_test_block.enabled=true` 才判（規則 [SVN_TEST_BLOCK_OPT_IN](../TECH/release-rules.md#svn_test_block_opt_in)）
- **擋什麼**：
  - 只看 svn commit 的路徑參數（`-m` 訊息與帶值選項的值不算）
  - 含測試目錄（test／tests／__tests__）或 `*Test.<副檔名>` 檔 → 擋
- **放行**：使用者本回合明說要把測試一起上 → 指令開頭寫 `# 測試上 svn 原句：「…」`
  - 原句要逐字在本回合原話裡
  - 那個子句沒被否定才放行
  - 放行時留帳 user_quote
- **判不了**：拆不出路徑、設定讀不到 → 不擋，stderr＋留帳 error
- **留帳**：`Logs/guard-svn_test_block.jsonl`
- **已知限制**：
  - 不帶路徑的整個工作副本 commit 看不到
  - `--targets` 清單檔裡的測試檔看不到

### SmellGate
- **名稱**：SmellGate（G2），commit 前病形檢查
- **位置**：[`hooks/handlers/pre_tool_use.py check_smell_gate`](../hooks/handlers/pre_tool_use.py) → [`tools/project-smells.py`](../tools/project-smells.py)「commit 前病形檢查」段（PreToolUse Bash／PowerShell 的 git／svn commit）
- **性質**：照擋（病形）
- **查什麼內容**（這次真的會提交的）：
  - 暫存區、`commit -a`、`commit <路徑>`
  - 同一條指令前面 `git add` 要加進來的檔
  - svn 工作副本改動
- **比對方式**：
  - 每個程式檔（`wg_need_goal.is_code_path`）取舊版（HEAD／BASE，改名取舊名）與新版比對
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
- 檔對不到任何部位、而部位表裡有資料列因前綴沒用反引號包（或是沒有 / 的根目錄單檔）被整列略過 → 列「注意：部位表…整列沒被讀到」
- OverviewHub 表外檔的擋訊息與放行警告也附同一句；只提醒，不改認法

#### 判定與放行
- **剝不乾淨**：大括號語言的字串、註解剝不乾淨（大括號或小括號對不上）→ 那個檔的內建病形一律只提醒不擋
- **deny 條件**：
  - 病形範圍內有這次改到的行：Python 取外層 lambda／整個類別／整個函式；刪除算碰到刪除處前後
  - 且所有提交檔舊版裡同一個（規則, 點名那行）一份抵一份抵不到
  - deny 時列病名、為什麼、怎麼改、檔與行（巢狀附幾層、匿名本體附幾行）
- **只提醒**：只提醒的另列一段；其餘列為「舊碼原本就有」只提醒；專案 `smells_report` 的列整檔算舊
- **放行**：那一行寫 `smell-ok: <理由>` → 放行並列出
- **別人留在暫存區的檔被點名**：
  - 照擋訊息在 commit 指令開頭加一行 `# 不是繞閘｜<檔是誰的、病要誰修>`
  - 下一行只提交自己的檔，送一次就過（[§7.5](../TECH.md#75-其他守門) GateBypass）

#### 判不了一律擋
- 拆不出 commit 落點
- `--git-dir`／`--work-tree`／`GIT_DIR` 類指定
- `--pathspec-from-file`
- 程式檔超過 2000 個
- git 查詢失敗、檢查出錯
- git 別名（`git config alias.*`、別名接別名、行內 `-c alias.<名>=…`）先展開成 git 實際會跑的子命令再判；跟 git 自己指令同名的別名不認
- 下列情形就算同一條指令另有直接寫的 commit 也判不了、一律擋（隱私閘、口令閘、需求目標 commit 閘共用同一份拆段）：
  - `!` 開頭的 shell 別名
  - commit 落點查不到別名表時不是 git 指令的子命令
  - bash -c 之類的包裝、eval
  - commit 訊息裡的 `$(…)` 裡有 commit

#### 其他
- **已知限制**：跨行的表達式箭頭函式不算套層
- **停用**：`guard.smell_gate.enabled=false`
- **手動**：[`python tools/project-smells.py --commit-check --cwd <repo>`](../tools/project-smells.py)

### DataFileAsk
- **名稱**：DataFileAsk（T2.16），改使用者既有資料檔要先宣告
- **位置**：
  - [`hooks/handlers/pre_tool_use.py`](../hooks/handlers/pre_tool_use.py) DataFileAsk 段
  - → [`hooks/wg_data_file.gate`](../hooks/wg_data_file.py)（收事實）
  - → `wg_release_rules.data_file_verdict`（規則 [USER_DATA_FILE_NEEDS_DECLARATION](../TECH/release-rules.md#user_data_file_needs_declaration)）
  - PostToolUse：`wg_data_file.note_created`／`confirm_shell_created`
- **性質**：照擋（宣告）
- **判定順序**：使用者原話點名先判；本 session 宣告過才沿用；點名記 exempt 並帶原話片段 quote

#### 管哪些目標
- Edit／Write／NotebookEdit（含 MultiEdit）要動的檔
- Bash／PowerShell 指令的每個寫入目標（`wg_core.write_paths_from_tool`；算不出的 UNKNOWN 交 OverviewHub）
- 每個目標各自判

#### 四件事實全成立才管
- **(a) 副檔名**：
  - 不是程式檔（`wg_need_goal.writes_code`），且副檔名在 `guard.data_file_ask.extensions`
  - 預設 `.json .jsonc .yaml .yml .toml .ini .cfg .conf .env .csv .tsv .xml .properties .plist .md`
  - `_AIDocs`／`memory`／`.claude` 目錄底下的 `.md` 是系統文件，不問
  - 設定給了就整份取代；清單只決定要不要問，該不該改由 AI 判
- **(b)** 呼叫前檔已存在
- **(c) 不是本 session 新建**：
  - 記在 state `created_files`，整個 session 不淘汰
  - Write 看結果 `type=create`，判不出就不記
  - Bash／PowerShell 由 PreToolUse 記呼叫前不存在的目標到 `data_file_pending_new[tool_use_id]`，PostToolUse 確認檔真的出現才轉進去；覆寫既有檔不算
- **(d) 使用者原話沒點名它**：
  - 範圍：本 session 使用者原話，即 state 近期清單＋transcript 每則使用者訊息（`user_typed_text` 清理）
  - 檔名含副檔名完整比對，前後不接檔名字元
  - 引號裡是更長的檔名、中日韓字開頭的檔名前面又接中日韓字都不算點名，寧可多問

#### 宣告怎麼找
- 宣告句：「動資料檔｜<路徑>：<為什麼>」
  - 路徑是那個檔或它的路徑尾段
  - 冒號後的理由過 `reason_present`：拿掉角括號片段後還有任一字母或數字
- 三個管道，整個 session 找：
  - 回覆文字
  - 工具呼叫參數裡 `#` 開頭的註解行
  - thinking（重用 `overview_hub.assistant_text_after`）
- Bash／PowerShell 另認這次指令自己的 `#` 註解行，因為 PreToolUse 當下這則呼叫不一定已進 transcript
- 宣告過記 state `data_file_declared`，同 session 同檔不再擋

#### 擋訊息（DENY_TEXT_SLIM）
- 預設精簡格式，只有兩行、約 320 字；`guard.deny_text_slim=false` 退回原本整段管道說明
- 第一行（`data_file_fix`；一次擋好幾個檔就每檔一個範例）：

  ```text
  [Guardian:DataFileAsk] 修法：先發一條不寫檔的 Bash／PowerShell 指令、開頭的 `#` 註解寫宣告，接著就可以改檔；照抄：# 動資料檔｜<那個檔>：<為什麼要動它、動了使用者會看到什麼>（下一行 git diff --stat）；改檔照常用 Edit／Write
  ```

- 第二行：

  ```text
  ✗ (df) USER_DATA_FILE_NEEDS_DECLARATION：要改使用者既有的資料檔 <那個檔>｜證據：(a)～(d) 四件事實各幾個字
  ```

#### 訊息裡不再重述的規矩
- 宣告放哪只教一條路：同一則先發的不寫檔指令開頭的 `#` 註解
  - 跟工具呼叫同一則送出的文字、thinking 預設不進 transcript，hook 看不到
  - 早一則只有文字的回覆與 need_goal set／update 的 `data_files` 程式照認、訊息不提（[DECL_HINT_KEEPS_EDIT_TOOLS](../TECH/release-rules.md#decl_hint_keeps_edit_tools)）
  - 原因：009 實跑三條路並列，AI 挑了最貴的，多 4 個模型回合
- 宣告完照常用 Edit／Write 改，不改用 Bash／PowerShell 寫檔
- 拿不準要不要動就用 AskUserQuestion 問使用者（附推薦）
- 每個檔各自宣告，帳留給健檢抽查
- 一條指令寫好幾個資料檔，沒對上宣告的每個都列出來

#### 讀檔提示（DATA_FILE_READ_HINT）
- 第一次讀到改了會被問的檔（Read／唯讀 Bash／PowerShell／Grep；讀了什麼跟定位閘同一支 `wg_overview.read_targets`），PostToolUse 先附一行約 100 字的宣告格式
- 內容：「[Guardian:DataFileAsk] 改 <檔> 前先宣告：動資料檔｜<路徑>：<為什麼…>（放同一則先發的不寫檔指令開頭的 `#` 註解，接著就可以改檔）」
- 由 `wg_data_file.read_hint` 產生
- 一個檔一個 session 一次，第二個檔起只點名；記 state `data_file_hinted`
- 子代理讀的不提示
- 目的是讓第一次改就帶宣告；判定不變、沒宣告照擋

#### 上限與出錯
- **擋滿放行**：同一個使用者回合同一個檔擋滿 2 次，第 3 次放行並留帳 cap_released（[GATE_DENY_CAP](../TECH/release-rules.md#gate_deny_cap)）
- **閘自己出錯**（state 讀壞、例外）＝判不了，這次不擋，stderr＋留帳 error（[GATE_SELF_ERROR](../TECH/release-rules.md#gate_self_error)）

#### 只在寫過程式的 session 管
- 判定：`wg_data_file.coding_session`，規則 [NON_CODING_TURN_NO_NUDGE](../TECH/release-rules.md#non_coding_turn_no_nudge)
- state `modified_files` 沒有任何程式檔、這條指令也沒同時寫程式檔 → 放行、不留宣告帳、只留 skipped_non_coding
- 讀檔提示同一條件（閘不會問的不提示）
- 代價：純設定回合改使用者的設定檔沒人攔（使用者裁定）

#### 留帳與開關
- `Logs/guard-data_file.jsonl` 事件：denied／declared／exempt（只記副檔名在清單內的）／cap_released／read_hint／skipped_non_coding／error
- 停用：`guard.data_file_ask.enabled=false`

### JudgeCardDeclare
- **名稱**：JudgeCardDeclare（改判準卡留帳）
- **位置**：
  - [`hooks/handlers/pre_tool_use.py`](../hooks/handlers/pre_tool_use.py) JudgeCardDeclare 段（檔案類出口）與開頭的 MCP 分流
  - → [`hooks/wg_judge_card.gate`](../hooks/wg_judge_card.py)（收事實）
  - → `wg_release_rules.judge_card_verdict`（規則 [JUDGE_CARD_CHANGE_NEEDS_DECLARATION](../TECH/release-rules.md#judge_card_change_needs_declaration)）
- **性質**：只記錄不擋
- **管什麼**：要改的檔是綁了 Entry 的判準卡＝判 AI 做得對不對的量尺。判定只用 [`lib/atom_locations.entry_bound_ids`](../lib/atom_locations.py)，三件事實全成立：
  - memory／_atoms 目錄底下的 .md（`_` 開頭除外）
  - 磁碟上已存在
  - 檔頭 `- Entry:` 非空
- **看哪些出口**：
  - Edit／MultiEdit／Write
  - Bash／PowerShell 解析得出的寫入目標（`wg_core.write_paths_from_tool`）
  - MCP `atom_write` 的 append／replace、`atom_edit_meta`、`atom_retire`
  - MCP 呼叫經 settings.json PreToolUse 的 guardian matcher 先到這裡；卡在哪個檔照 MCP 自己用的 [`lib/atom_io.locate_atom`](../lib/atom_io.py) 定位
- **管不到**：直譯器自己開檔寫卡（寫入目標解析不到）不管，不記雜湊、不事後比對（規則 [JUDGE_CARD_HASH_CATCHES_INTERPRETER](../TECH/release-rules.md#judge_card_hash_catches_interpreter)）
- **宣告行**：「改判準卡｜<卡名>：<理由>」
  - 三管道：回覆文字／工具參數裡 `#` 開頭的註解行／thinking，主檔與子代理檔都找
  - Bash／PowerShell 另認這次指令的 `#` 註解行
  - 有沒有宣告都放行
- **留帳**：
  - 每次改動每張卡留一筆 `Logs/guard-judge_card.jsonl`
  - 事件：undeclared／declared／error
  - 欄位：card、entry、path、line、via、session_id、allowed
  - 判分材料 w2_collect 照 `guard-*.jsonl` 帶上
- **出錯**：只 stderr＋留帳
- **開關與守門**：`guard.judge_card_declare.enabled=false` 停用；守門 [`hooks/verify/verify_judge_card_declare.py`](../hooks/verify/verify_judge_card_declare.py)

### OldTestDeclare
- **名稱**：OldTestDeclare（T2.17），改舊測試要先宣告
- **位置**：
  - [`hooks/handlers/pre_tool_use.py`](../hooks/handlers/pre_tool_use.py) OldTestDeclare 段
  - → [`hooks/wg_oldtest.py`](../hooks/wg_oldtest.py)（收事實；檔名不帶 `_test` 尾，免得被案例樣式 `**/*_test.*` 當成測試檔）
  - ＋ `wg_release_rules.old_test_change_verdict`
  - 時機：PreToolUse Edit／MultiEdit／Write 寫到測試檔
- **性質**：照擋（宣告）

#### 什麼算測試檔
- 重用寫碼查核的 `verify_case_globs`＋`code_exts`（`wg_verify_ledger.is_case_file`）
- 另補 `*Tests.cs`／`*Test.cs`／`*Tests.java`／`*Test.java`

#### 抓哪四種「動既有測試」
- 比對改前（磁碟現檔）與改後：Edit 套 old→new 到全檔，套不上退回只比片段；Write 比新內容；比之前去註解、空白壓成一個
- **消失**
- **改名**：舊的一支消失、新出現的一支本體行相似度 ≥0.6；只決定證據標「改名」還是「消失」
- **同名測試的斷言被刪或改**：
  - Python：assert／self.assert／pytest.raises 開頭的邏輯行，括號沒合上就併下一行
  - JS／TS、C#、Java：含 expect(／assert…(／…Assert. 的行，點開頭的續行併回
- **新加跳過標記**：skip／skipif／xfail／pytest.skip(／unittest.skip／類別或模組 pytestmark 標 skip／it.skip／xit／describe.skip／[Ignore]／Skip=／@Disabled
- **說明變了**：
  - Python 本體第一行字串被改或刪，三引號多行併成一筆；只加新說明不算
  - JS 的描述文字就是名字，改了算改名
- **不觸發**：只加新測試、改 fixture／helper、只改註解

#### 宣告與擋訊息
- 宣告行：「改舊測試｜<函式名或 檔:函式名>：<理由>」
- 找的管道：回覆文字／工具參數／thinking 三管道，主檔與子代理檔都找
- 寫法規定：
  - 多支以「、，；」分隔
  - 一行也可寫「名1：理由1、名2：理由2」各帶理由
  - 名字要點到那支既有測試；改名寫舊名；寫了檔名或類別就要對上
  - 理由要有文字內容，不是佔位
- 沒有宣告 → deny `✗ (ot) OLD_TEST_CHANGE_NEEDS_DECLARATION`
- 證據每支一行（檔、函式、哪一種），末尾印入口行範例

#### 測試範圍怎麼切
- Python 照縮排（含單行 def）
- JS／TS（it／test）、C#（[Test]／[Fact]／[TestMethod]／[Theory]）、Java（@Test）：從這支開頭到下一支開頭
- 尾端 helper 的斷言算給最後一支

#### 免擋與基線
- 宣告過的那支（連同改名後的新名）記 state `old_test_declared`
- 本 session 自己新加的測試記 state `old_test_added`
- 這兩類同 session 再動不擋
- **基線 `old_test_baseline`**：
  - 內容：本 session 第一次拍快照時那個檔有哪些測試，磁碟上的加上 git HEAD 裡的
  - 記錄時機：Edit／Write 與 Bash 類的 PreToolUse 就記；python 腳本改的檔在 PostToolUse 補記
  - HEAD 查詢失敗 → stderr＋留帳 baseline_head_error，退回只看磁碟
  - 基線沒有的那支改了也不擋（留帳 exempt `why=not_in_baseline`）
  - 基線有的（被刪又還原的舊測試）不記成新加
- **寫新測試的那次指令失敗時**：Claude Code 改送 PostToolUseFailure，一樣比、一樣記 `old_test_added`（[OLD_TEST_COMPARED_ON_FAILED_COMMAND](../TECH/release-rules.md#old_test_compared_on_failed_command)）；那一則 hook 沒跑到（逾時、被砍）時記不到，靠基線認得

#### Bash／PowerShell／NotebookEdit 寫測試檔
- **heredoc 寫法**：
  - 形式：`cat > 檔 <<TAG`／`cat >> 檔 <<TAG`（`wg_oldtest.heredoc_writes`：路徑尾段對上 `write_paths_from_tool` 的目標）
  - 寫之前就算得出改後內容，PreToolUse 與 Edit 同款判，沒宣告就擋
- **其他寫法**（Bash／PowerShell／NotebookEdit，notebook 取程式格接起來當 Python）寫之前看不到改後內容：
  - PreToolUse 把寫入目標（`wg_core.write_paths_from_tool`）裡的測試檔拍改前快照到 `workflow/old-test-snap/`
  - PostToolUse 與 PostToolUseFailure（`wg_oldtest.after_tool`，用 post_tool_use 那份 state；指令非零結束也比）比磁碟
  - 沒宣告的記 `state.old_test_undeclared`
  - 下一個 PreToolUse 掛到的工具呼叫（寫檔與執行類；matcher 外的 Read／Grep 不經過）一律擋，訊息加「這是 Bash 改的，請補宣告再繼續」
  - 補了宣告就清掉、留帳 declared_late
  - 只讀只寫那幾個欠帳檔（撤回）的呼叫不擋；撤回後的 PostToolUse 把已恢復的清掉（reverted）

#### 指令會執行 python 時改看 git
- 適用：腳本自己開檔寫、寫入目標解析不到
- **執行前記下**：HEAD、進行中的合併類操作標記、logs/HEAD 長度、repo 裡已經有改動的測試檔與內容
- **執行後新出現改動的**：
  - 取執行前的 HEAD 當改前（執行前乾淨＝磁碟與 HEAD 相同）
  - 原本就有改動的取執行前內容，所以使用者自己沒 commit 的改動不算
- **git 自己產出的內容另外算**：
  - 合併類：這條指令開始（或往下一步）的 merge／squash／cherry-pick／rebase 停在半路，判斷依據是 git 目錄的 MERGE_HEAD、SQUASH_MSG、CHERRY_PICK_HEAD、REBASE_HEAD、rebase-merge、rebase-apply 新出現或內容變了
    - → `git merge-tree --write-tree` 從 commit 重算（不讀暫存區與工作樹）
    - cherry-pick／rebase 套的是合併提交時主線不明，merge 另給的 -s／-X 看不出來 → 判不出或結果不同，照算本 session 改的，寧可多擋
  - HEAD 被 merge／pull／rebase／切分支移動：
    - 看這段期間 logs/HEAD 新增的每一筆，說明不是 commit／revert 開頭的
    - 自己 commit、amend 不算
    - revert 撤掉哪個 commit 是本 session 的決定，撤掉的測試照算改舊測試
    - → 最後一筆外來移動的終點（之後自己 commit 的照算）
  - 讀不到 reflog 又動了 HEAD → 分不出誰動的，整段照外來算併基線、不給 git 產出
- **有 git 產出時**：
  - 只算比它變了的動作（改回執行前的值＝撤掉別軌的改動，也算）
  - 同一支腳本之後再改、再 add 的照算
  - 執行前就有本 session 沒 commit 改動的檔（autostash 放回來的）：那支測試執行前就有的話，比改前也要變了才算
  - git 帶進來的測試（產出比改前多的、每筆移動前後已記基線的檔多出來的）併入基線，不當本 session 新加的放過
- **留帳**：git_op；判不出就照執行前的內容比、寧可多擋，stderr＋留帳原因；查不到 git_op_error
- **git 查不到**：只 stderr＋留帳 py_baseline_error／py_after_error，不擋 python 指令
- **抓不到的**：node 等其他直譯器自己寫檔、不在 git repo 裡

#### 上限與出錯
- **擋滿放行**：同一個使用者回合同一件缺件（檔＋測試＋動作種類；Bash 類改完欠的那筆也一樣）擋滿 2 次，第 3 次放行並留帳 cap_released（[GATE_DENY_CAP](../TECH/release-rules.md#gate_deny_cap)）
- **判不了**：既有測試檔讀不到、閘自己炸＝這次不擋，stderr＋留帳 error（[GATE_SELF_ERROR](../TECH/release-rules.md#gate_self_error)）
- **事後比對炸了**：只能 stderr＋留帳 after_error

#### 留帳與開關
- 留帳 `Logs/guard-old_test.jsonl`：denied／declared／exempt／undeclared／denied_late／declared_late／reverted／cap_released／error
- 停用：`guard.old_test_declare.enabled=false`
- 守門：[`hooks/verify/verify_old_test_declare.py`](../hooks/verify/verify_old_test_declare.py)

### GateBypass
- **名稱**：GateBypass（T2.19），病形防繞
- **位置**：[`hooks/wg_gate_bypass.py`](../hooks/wg_gate_bypass.py)
  - PreToolUse Bash／PowerShell：病形閘 deny 分支記 `smell_deny_last`
  - 病形閘之後的 GateBypass 段判
  - post_tool_use 成功 commit 清帳
- **性質**：照擋（病形防繞）

#### 什麼算嫌疑
- **前提**：病形閘擋過之後、同一個 repo 根
- **動作**（任一）：
  - git `restore --staged`／`reset`／`rm --cached`／`stash`、svn `revert`／`changelist` 動到被點名的檔
  - commit 範圍（病形閘同一份 `commit_entries`）排除它
  - commit 帶 `--no-verify` 或 `-c core.hooksPath=`
- **確認**：重掃被點名的檔（暫存區與工作樹各比 HEAD，`classify` 同一份判法），同一條病還在才算嫌疑；病修掉就清帳
- **判斷細節**：
  - 「同一個 repo」看實際版控根（根底下另開的 repo、submodule 不算）
  - magic pathspec 不模擬、一律當動到
  - `reset <非工作樹檔>` 當 revision＝整個暫存區

#### 宣告與放行
- 嫌疑要自成一行的「不是繞閘｜<理由>」
  - 指令與工具參數裡是 `#` 註解行；回覆文字／thinking 是行首；句中引用不算
  - 主檔與子代理檔都找，起點各檔各記
- 有宣告 → 放行並記 `bypass_declared`
  - 同一組被點名檔、同一份內容不再問
  - 內容變了要在上次宣告之後重新宣告
- 沒有 → `✗ (gb) GATE_BYPASS_NEEDS_DECLARATION`
- **合併被點名檔**（[GATE_BYPASS_NAMED_FILES_MERGED](../TECH/release-rules.md#gate_bypass_needs_declarationgate_bypass_named_files_merged)）：同一個 repo 還沒 commit 成功又被病形閘擋下時，這次點名的檔與先前的合併成一份；宣告要寫在該檔被點名之後才替它算數

#### 上限、出錯與其他
- **擋滿放行**：同一組被點名的檔同一個使用者回合擋滿 2 次，第 3 次放行並留帳 cap_released（[GATE_DENY_CAP](../TECH/release-rules.md#gate_deny_cap)）
- **出錯**：檢查自己出錯這次不判、留帳 error（[GATE_SELF_ERROR](../TECH/release-rules.md#gate_self_error)）
- **解析**：被點名的檔與病名從擋訊息解析（`parse_smell_deny`，字樣改了要一起改）；一條指令提交多個 repo 時記在真的有那些檔的那段
- **範圍**：state 是 session 級，跨 session 不判
- **留帳**：`Logs/guard-gate_bypass.jsonl`（suspect／declared／denied／cap_released／cleared／error）
- **開關**：`guard.gate_bypass.enabled`

### 繞閘卡片拒寫
- **名稱**：繞閘卡片拒寫（T2.19）
- **位置**：[`hooks/wg_gate_bypass.atom_refusal`](../hooks/wg_gate_bypass.py)
- **入口**：
  - [`tools/memory-write-gate.py evaluate`](../tools/memory-write-gate.py)（MCP atom_write 三種 mode）
  - [`lib/atom_io.write_atom`](../lib/atom_io.py)（程式寫手）
- **性質**：照擋（不在範圍）

#### 拒寫條件（兩者同時成立）
- ① 內容提到 Guardian 的閘：
  - `[Guardian:` 標籤
  - SmellGate／病形閘／隱私閘／PrivacyGate／CommitOrder／NeedGoal
  - `wg_release_rules.RULES` 規則名
- ② 含改暫存區／改提交範圍的做法字樣：
  - 設定鍵 `guard.gate_bypass.staging_words`
  - 預設帶動作的寫法：restore --staged、改 pathspec、拆三步、移出暫存…
  - 單獨的「pathspec」「reset」不算
- 動作：拒寫 `ATOM_BYPASS_HOWTO_REFUSED`（訊息末尾印宣告入口），留帳 atom_refused
- 只命中一個 → 照寫

#### 宣告「不是教繞法」
- 適用：AI 判斷內容不是在教繞法，例如禁止怎麼繞的指引、誤擋分析
- 寫法：知識段第一行寫「不是教繞閘｜<理由>」
  - 可帶 [臨] 前綴
  - MCP js 不用改
  - 建卡與 append 落檔前由 [`lib/atom_spec.strip_bypass_declaration`](../lib/atom_spec.py) 剝掉，卡裡不留，理由只在帳上
- 理由有內容、不是佔位 → 寫入並留帳 atom_declared

### version_guard
- **位置**：[`hooks/version_guard.py`](../hooks/version_guard.py)
- **呼叫方式**：由 guardian PostToolUse 同程序呼叫 `run()`；`__main__` 仍可獨跑
- **做什麼**：live 檔埋版本／日期／階段敘事 → warn-only

### 跨 session 衝突預警
- **位置**：[`hooks/wg_coordination.py`](../hooks/wg_coordination.py)
- **PreToolUse 同檔互寫 warn**：
  - entry 級 session_id 歸屬、mtime <30min、同檔 10min 抑制
  - 寫碼守門開時同一個檔一個 session 只警一次（`coordination.v6_once`）
- **Bash 預警**：`git add -A`／`reset --hard`／`clean -f` 同 cwd 預警；引號解包、dry-run 排除
- **PostToolUse**：60s late-collision
- **性質與限制**：
  - 純檔案、不依賴 daemon
  - first-write race 無法消除（advisory 非鎖）
- **留帳**：`Logs/session-coordination/<sid>.jsonl`
- **檢討線**：4 週零命中 → 提降級

### Codex Companion
- **位置**：[`hooks/codex_companion.py`](../hooks/codex_companion.py) ＋ [`tools/codex-companion/`](../tools/codex-companion/)
- **運作**：
  - in-process state ＋ spawn [`audit.py`](../tools/codex-companion/audit.py) 短命子程序
  - 所有審查（含收尾驗收裁判、收尾自檢）背景跑，Stop 不等、永不 block
  - 結果下一則 UserPromptSubmit 附一行
  - fail 且 severity ≥`max_inject_severity` 才附完整說明
- **節流**：Silent Advisory／Score Gate（7）／Dedup／每 session 上限 30
- **審計類**（[`assessor.py`](../tools/codex-companion/assessor.py)）：
  - plan_review：ExitPlanMode 計畫審
  - turn_audit：回合完成證據
  - architecture_review：預設關
  - handoff_review：交接文件第二意見；寫碼守門開時預設不觸發（`soft_gate.handoff_review_v6`）
  - acceptance_review：驗收裁判（[§7.4](../TECH.md#74-驗收裁判ai-審查-ai-產出四段閉環)）
- **案例**：[`hooks/verify/verify_codex_stop_async.py`](../hooks/verify/verify_codex_stop_async.py)

### Wisdom Engine
- **位置**：[`hooks/wisdom_engine.py`](../hooks/wisdom_engine.py) ＋ [`memory/wisdom/`](../memory/wisdom/)
- **情境分類**：只記 approach 給反思統計、不注入；分類看整個 session 的改檔數，不看這則訊息
- **反思**：3 指標 Bayesian 校準

### Fix Escalation
- **位置**：[`skills/fix-escalation/`](../skills/fix-escalation/) ＋ wisdom_engine
- **觸發**：同錯誤重複失敗（`track_retry` gate on `failing_tests`，error-based）
- **動作**：6 Agent 精確修正會議

### DocDrift
- **位置**：[`hooks/wg_docdrift.py`](../hooks/wg_docdrift.py)
- **做什麼**：改了程式檔沒同步改對應的 [`_AIDocs/`](../_AIDocs/) 文件就記一筆待補
- **對應表**：
  - `docdrift.path_mappings`：專案自己填，出廠空
  - `docdrift.self_path_mappings`：記憶系統自己的對應，只在改的檔落在 `~/.claude` 底下才套（改別的專案的同名檔不記）
  - 都沒對上 → 退回 `_AIDocs` 索引關鍵字比對

### Auto-Handoff
- **位置**：[`hooks/wg_handoff.py`](../hooks/wg_handoff.py)
- **時機**：
  - PreCompact 存 stub
  - Stop 的 token 預警（0.85，`token_warn_payload`）
  - SessionEnd fallback
- **輸出**：`_staging/next-phase-auto.md`

### webfetch-guard
- **位置**：[`hooks/webfetch-guard.sh`](../hooks/webfetch-guard.sh)
- **做什麼**：WebFetch 前置護欄

## A7.6 寫碼守門：部位導讀卡（OverviewHub）

[↑ 主文 §7.6](../TECH.md#76-寫碼守門部位導讀卡overviewhub)

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

### 注入
- **位置**：
  - UPS（提示提到部位檔）
  - PostToolUse（Read／唯讀 Bash／PowerShell／Grep 讀到部位檔只建紀錄）
  - PreToolUse `on_edit`（第一次改該部位的檔時送卡）
  - 程式：[`hooks/wg_overview.py`](../hooks/wg_overview.py)、[`lib/overview_hub.build_injection_ex`](../lib/overview_hub.py)
- **第一次唯讀碰到某部位**：
  - 「唯讀」＝Read、cat／sed -n／head／grep -n／git diff 這類不寫檔的指令，判法同讀檔證據 `read_targets`
  - 只建部位紀錄、標 `card_pending`
  - 讀檔結果最多多 [LOCATE_HINT_ON_FIRST_READ](../TECH/release-rules.md#locate_hint_on_first_read) 一行；寫碼守門關時連這一行都沒有
  - 卡、候選、追蹤項都不送（規則 READ_TOUCH_NO_CARD）
- **卡什麼時候送**：
  - 在第一次改這個部位的檔那則送（`_deliver_card`，log event `card`）
  - A 包把這個 deny 降成提醒後，就是「卡隨改檔結果到」
  - 或提示詞點名路徑時立刻送
  - 紀錄起點（transcript_offset、讀檔帳）不動，讀檔後交的定位行與讀過的部位檔照算

#### 卡怎麼送（`card_injection`）
- **`pointer`（預設）**：
  - 只送兩行：卡上「已知病灶」第一條（截 160 字）與卡路徑
  - 叫 AI 改這塊之前自己 Read
  - 指標行與讀卡缺件行都寫「下一則讀卡時順便讀要改的檔」（規則 [CARD_READ_WITH_EDIT_FILES](../TECH/release-rules.md#card_read_with_edit_files)）
- **`full`**：
  - 整張注入
  - 依本回合意圖（`turn_intent` 十類）用 `goal_weights` 選先送哪幾片
- **開關關態**：寫碼守門總開關開關都照這個值（關態不再退回 `full`）
- **沒有卡的部位**：兩種送法逐字相同
- **卡尾追蹤項**：只留一行「未結追蹤項 N 筆＋帳本路徑＋結案寫法」，不列內容（規則 TRACKING_COUNT_LINE_ONLY，`wg_overview._tracking_line`）
- **目標改了之後的目標視角重送**：只一行（[GOAL_VIEW_ONE_LINE](../TECH/release-rules.md#goal_view_one_line)）

### 最小地圖（G14）
- **名稱**：最小地圖，無表專案
- **時機**：PreToolUse，同寫入閘的入口
- **條件**：只在往上找不到任何部位表、改的是程式檔時查
- **要求**：本 session 第一次改某頂層目錄的程式檔前，要交「地圖｜讀了／上游／下游」三行（規則 [UNMAPPED_FIRST_EDIT_NEEDS_MIN_MAP](../TECH/release-rules.md#unmapped_first_edit_needs_min_map)，[§7.8](../TECH.md#78-放行欠帳判定規則hookswg_release_rulespy)）
- **擋訊息**：附掃表預覽與落表格式，引導先落一張部位表
- **設定**：`overview_hub.min_map`（enabled、preview_timeout_s）

### 寫入閘
- **位置**：PreToolUse（Edit／Write／NotebookEdit，以及 Bash／PowerShell 解析出的寫入目標）
- **性質**：提醒
  - 寫碼守門開時，缺件只提醒一行、留帳，不 deny
  - 寫碼守門關時照下面寫的 deny

#### 三項證據（缺一）
- 卡已注入
- 注入後讀過該部位檔 ≥`min_overview_evidence.part_files`（觸發注入的那次讀也算，[INJECT_TRIGGER_READ_COUNTED](../TECH/release-rules.md#inject_trigger_read_counted)）
- 交了定位三行：部位／根因層／前例
  - 前例填存在的卡名、「無」或「待規格：<理由>」
  - 光禿「待規格」與照抄範本不算
- 指標制送卡的程式部位另要：本 session Read 過表上每張卡
  - 讀檔帳同讀檔證據，`wg_overview._unread_cards`
  - 沒讀的跟其他缺件列在同一則擋訊息、附卡路徑
  - 改檔 log 記 `card_mode`、`card_unread`

#### 三行從哪裡認
- 回覆文字、工具參數（Bash 開頭 `#` 註解）、thinking 三處都認
- 子代理的對話在 `<sid>/subagents/agent-<agent_id>.jsonl`，主檔與子代理檔都讀（`wg_core.assistant_texts_since`）
- 起點在注入或目標改的那刻各檔各記（`transcript_offsets`）
- 之後才出現的子代理檔整份都算

#### 擋與放行的細節
- `readonly_paths` 一律擋
- transcript 讀不到＝閘判不了：這次不要求定位行與地圖三行（讀檔數照查），記守門紀錄 error（[GATE_SELF_ERROR](../TECH/release-rules.md#gate_self_error)）
- 閘自己出例外也擋（不 fail-open）
- **擋滿放行**：同回合同缺件擋 2 則回覆後放行留帳（[GATE_DENY_CAP](../TECH/release-rules.md#gate_deny_cap)）；同一則回覆平行送出的幾個改檔算一則（[DENY_CAP_PER_REPLY](../TECH/release-rules.md#deny_cap_per_reply)）
- **別的部位**：同一個使用者回合擋過某個部位之後，別的部位只缺定位行改成一行提醒、放行、留帳；缺讀檔或卡還沒注入照擋（[LOCATE_BLOCK_ONCE_PER_USER_TURN](../TECH/release-rules.md#locate_block_once_per_user_turn)）
- **訊息內容**：
  - 缺定位的擋訊息明說 thinking 預設不寫進 transcript、hook 讀不到（[LOCATE_NOT_IN_THINKING](../TECH/release-rules.md#locate_not_in_thinking)）
  - 有目標樹時完整範例每個 session 只給一次，之後換短句（[LOCATE_EXAMPLE_ONCE_PER_SESSION](../TECH/release-rules.md#locate_example_once_per_session)）
- **沒表或表外檔**：只要求同頂層目錄讀過檔；該目錄沒有可讀既有檔就不要求（[UNMAPPED_EDIT_NEEDS_READABLE_FILES](../TECH/release-rules.md#unmapped_edit_needs_readable_files)）
- **整個資料夾當目標**（rm -rf、Remove-Item -Recurse）：看它所在的上一層屬於哪個專案（[DIR_TARGET_JUDGED_BY_CONTAINER](../TECH/release-rules.md#dir_target_judged_by_container)）
- **第一次讀程式檔的提示**：讀檔時注入的部位，第一次讀到它的程式檔那則讀檔結果另附一行「改之前先立樹（沒樹時）、交定位四行、寫在哪」，讓第一次改就帶齊（[LOCATE_HINT_ON_FIRST_READ](../TECH/release-rules.md#locate_hint_on_first_read)，[§7.8](../TECH.md#78-放行欠帳判定規則hookswg_release_rulespy)；判定不動）

#### 知識類部位
- 部位表類別 knowledge 的部位（錨在專案根的最長前綴命中，[`lib/overview_hub.part_kind`](../lib/overview_hub.py)）
- 三項只要「卡已注入」
- 指標制下沒 Read 過卡，只附一行提醒、帳上記 `card_unread`，不擋
- 不要求讀部位檔與定位三行，注入文字也不叫人交三行

### 候選填空
- **位置**：`wg_overview._candidates_on_trigger`／`on_edit`
- **觸發**：提示命中 `root_cause_triggers`
  - 已注入部位各送一次「候選前 N＋根因卡＋兩問」
  - 一個都沒注入時，以 cwd 專案表送全專案一次
  - 放行的同檔第二次 Edit 也附，但與觸發詞共用 `candidates_sent`，一部位一 session 只送一次
- **候選來源順序**：`smells_report` → 導讀卡「已知病灶」段 → 明說無候選
  - 改檔路徑沒內容時只送一行，不附根因卡與兩問
  - 候選產生失敗只附一行，不改變閘判定
- **排序**：
  - smells 候選照報告原順序取、不按分數重排
  - 全專案時各部位輪流取、依部位分組列
  - 每列附「分數 X（參考）」
  - 根因那一問要求：挑的不是分數最高的就說為什麼（G5：數字只當參考）

### Depends 召回
- **位置**：[`hooks/wg_depends.py`](../hooks/wg_depends.py)（PostToolUse）
- **觸發**：讀到某張卡 `- Depends: path:<檔>` 指的檔（或其目錄之下）
- **動作**：一行指標「改它前先讀卡」，同卡一 session 一次
- **相關**：
  - `authority_map` 命中文件檔一次性注入地圖
  - 索引欄由 [`sync-atom-index.py --sync-depends`](../tools/sync-atom-index.py) 以 frontmatter 為真相同步

### 壓縮後重注
- **位置**：PreCompact／PostCompact／PostToolBatch
- **做法**：
  - 壓縮前存 OverviewHub 摘要
  - 壓縮後每部位綜觀隨 atom 一起重注（atom 先）
- **綜觀內容**：部位／層／三行已交否／主目標／卡／病灶前 N（`post_compact_chars` 截）

### 收據（收據列）
- **位置**：
  - [`hooks/wg_verify_ledger.py`](../hooks/wg_verify_ledger.py)：採認、對帳
  - [`lib/self_receipt.py`](../lib/self_receipt.py)：指令解析、自寫收據
  - Stop 的 ReconcileGate（[§7.1](../TECH.md#71-stop-閘序)）

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
- 本回合帶 PASS／DONE 的這種收據，每次收尾 stderr 一行並留帳（[RECEIPT_UNPARSED_GENERAL_ONLY](../TECH/release-rules.md#receipt_unparsed_general_only)）

#### 一般證據
- 用於對帳：(a) 指令提到改檔、(b) 量了、(c) 試過
- 只比實際跑程式那幾段的參數；前置設定、cd、環境指定、echo 印的字都不算

### 第二意見與候選池
- **位置**：
  - MCP `second_opinion_start`／`second_opinion_result`（[`tools/second-opinion/`](../tools/second-opinion/)）
  - `project_smells`（[`tools/project-smells.py`](../tools/project-smells.py)）：把專案壞味道候選排成表
- **打包給 codex 獨立審的材料**：部位卡、病灶文件、diff、帳本尾、需求目標樹（goal.md）
- **自動要求**：大任務或高風險部位收尾由 Stop 的 SecondOpinion 閘自動要求（[§7.1](../TECH.md#71-stop-閘序)）

#### diff 怎麼取
- `git diff HEAD`，空則 `main...HEAD`，或 `svn diff`
- 後面接未追蹤的新檔：`git ls-files --others --exclude-standard`／`svn status` 的 `?` 檔
  - `?` 的目錄只列名、不展開：svn 不列目錄裡的檔、忽略規則判不了
  - 寫成 new file patch 段：沒有尾換行標 `\ No newline at end of file`、空檔只留檔頭
  - 二進位與超過 `NEW_FILES_BUDGET`（200000）字的只列檔名；累計不超過它，放不下的那個起只報個數
  - 被 ignore 的不帶
  - 原因：以前新建的程式與測試審查者看不到

#### 沙箱外路徑與守門
- 材料裡指到沙箱外的絕對路徑（磁碟代號、Git Bash 的 /c/…、UNC）全部遮成「…/<最後一段>」
  - 提示詞才過得了 replay-guard pre
  - 也不把真工作副本的位置交給審查者
- **post 守門只判 codex 自己的輸出**：
  - stderr 先剝掉 `user` 段回聲的整份提示詞（prompt.md 全文當精確子字串）與回答全文（reply.raw.md，stdout 一併剝）
  - 剝完寫成 codex.stderr.own.log 交給 replay-guard post
  - codex 沒跑任何指令時（guard 只因找不到指令行而 FAIL），退路掃同一份輸出的禁區樣式與出界路徑
  - 帳本裡的 `git diff`、帶指令樣字樣的材料行、回答裡引述的禁區字樣都不算它讀出界；它自己 exec 的指令與輸出照判
  - 剝不到的照舊掃，理由與 note 寫明哪些未剝
- **有目標樹時**：question 要含樹根那句，否則 blocked

#### second_opinion_result 等待
- 等到 done／failed／blocked 才回
- job 還在跑就每 2 s 再讀 status.json，每次呼叫最多等 100 s（[`second-opinion.js`](../tools/workflow-guardian-mcp/lib/second-opinion.js) RESULT_WAIT_MS）
- 等滿仍在跑回 running 並附「再呼叫一次」
- **為什麼 100 s**（照 Claude Code 2.1.308 實查）：
  - 工具呼叫硬上限 `MCP_TOOL_TIMEOUT` 預設 1e8 ms 不是瓶頸
  - 但互動模式 MCP 呼叫滿 120 s 會被自動轉成背景工作（`CLAUDE_CODE_MCP_AUTO_BACKGROUND_MS` 預設，`-p` 無頭不轉）
  - 轉了 AI 就可能先結束回覆，所以每次等待要短於 120 s
- job 目錄在而 status.json 一時讀不到或沒寫完（run.py 寫檔不是原子替換）照等，等滿才回 failed
- 結果標頭帶 status.json 的 notes（`note:` 行）

### 過程量
- **位置**：[`hooks/wg_scorecard.py`](../hooks/wg_scorecard.py)、[`tools/scorecard-report.py`](../tools/scorecard-report.py)、[`tools/refix-churn.py`](../tools/refix-churn.py)
- **每 session 一行**：
  - 改過的部位裡注入後讀過檔的比例
  - 交三行的比例（knowledge 部位不計）
  - 同檔反覆修的熱點

### 專案覆蓋表
寫在 `<專案根>/.claude/overview-hub.json`，只寫要改的鍵。

#### `readonly_paths`
- 預設：空
- 這種專案才改：有生成碼、打包產物、第三方原始碼不准手改 → 列 glob，命中一律擋

#### `min_overview_evidence.part_files`
- 預設：1
- 這種專案才改：部位很大、讀一個檔看不出全貌 → 調高

#### `goal_weights`
- 預設：十類意圖各有片序
- 這種專案才改：導讀卡段落名跟預設不同，或某類任務該先看別的片 → 只覆蓋那個意圖

#### `locate_template`／`locate_extra`
- 預設：三句預設問法
- 這種專案才改：團隊要換問法，或某部位要加第四問（第四問只提醒、不納入三行檢查）

#### `root_cause_triggers`／`idle_triggers`
- 預設：內建詞表
- 這種專案才改：團隊口語不同（例「又出現」「接著呢」）→ 換詞

#### `smells_report`／`smells_max_age_days`
- 預設：空／7
- 這種專案才改：專案有自己的壞味道報告產生器 → 指過去，天數照報告更新頻率

#### `card_injection`
- 預設：`pointer`
- 這種專案才改：卡很短、幾乎每次碰到都會改，想省掉讀卡那一步 → `full`（整張注入，不要求 Read 卡）
- 只收 `pointer`／`full`

#### `candidate_top_n`／`post_compact_chars`／`max_card_chars`
- 預設：5／1500／6000
- 這種專案才改：病灶段很長、部位很多、壓縮後要更多綜觀 → 調整字數與條數
- `max_card_chars` 只管整張注入

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
- 這種專案才改：專案規定測試／練習檔不上 svn → 開，svn commit 的路徑含測試檔就擋（[§7.5](../TECH.md#75-其他守門) SvnTestBlock）

#### `need_goal.enabled`／`render_chars`／`scope_growth_dirs`
- 預設：true／1200／3
- 這種專案才改：對照組實驗要關掉需求目標流程；壓縮後重送的目標樹長度上限（兩倍 render_chars）（[§7.7](../TECH.md#77-需求目標樹need_goal)）

## A7.7 需求目標樹（need_goal）

[↑ 主文 §7.7](../TECH.md#77-需求目標樹need_goal)

### 分工與契約
- 程式只管：時機、留存、送回、有沒有做（有沒有寫、掛到存在的節點、引用的東西在不在、先後對不對）
- 目標內容與證據是否真的證明了什麼，由 AI 判斷
- 欄位、狀態轉換、身份、介面的契約：[`_AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/need-goal-契約.md`](../_AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/need-goal-契約.md)
- 流程開關照這次事件的 cwd 所在專案解四層設定（專案層 [`.claude/overview-hub.json`](../.claude/overview-hub.json) 的 `need_goal` 也算），每個 hook 入口同一套

### 目標檔
- **位置**：`workflow/need-goal/<sid>.json`（本機資料，不進版控）；[`hooks/wg_need_goal.py`](../hooks/wg_need_goal.py)
- **內容**：一個 session 一份
  - 多棵樹（`T1`、`T2`…）、節點（`T1.2.1`）
  - 使用者原話（權威）與同伴轉述分開記
  - 改檔與收據各蓋一個本檔自己的序號
- **每次修改整段上鎖**：取鎖 → 讀 → 改 → 寫暫存檔換名 → 放鎖；拿不到鎖不降級成無鎖寫
- 子代理用主 session 的 sid 寫同一份

### 工具
- **介面**：
  - MCP `need_goal`（[`tools/workflow-guardian-mcp/lib/need-goal.js`](../tools/workflow-guardian-mcp/lib/need-goal.js) 只驗參數回 chip）
  - ＋ PostToolUse 套用（`apply_op`）

#### 動作清單
- **set**：寫樹根、換題開新樹、改寫樹根、從續接單匯入；why 選填；開樹只回「開了新樹 T1：<樹根一句>」
- **add**：子目標，可待展開
- **update**：改節點，也是改了程式之後的一句進度；why 選填
- **reconcile**：完整對照，每個還活著的節點交終點結論＋證據
- **read**：form=handoff 取續接單區塊

#### 立樹走文字管道（TREE_SET_VIA_TEXT）
- 立寫碼樹優先走文字管道
- 寫法：同一則先發的不寫檔指令開頭的 `#` 註解
  - 「目標｜<整個需求一句>」
  - 多行「子目標｜<一件>」
- 改程式檔的 PreToolUse（`set_via_text`，`edit_gate` 之前）照它呼叫 `apply_op`（set, kind=code）
- state 效果同工具呼叫，留帳 `set_via_text`
- 早一則只有文字的回覆程式照認、工具照收，但擋訊息與提示只教 `#` 註解這一條路（[DECL_HINT_KEEPS_EDIT_TOOLS](../TECH/release-rules.md#decl_hint_keeps_edit_tools)）

#### 定位欄 `locate`（LOCATE_VIA_NEED_GOAL）
- set／update 可帶 `locate=[{part, lines}]`：改程式前的定位四行隨樹那一次呼叫一起交
- js 只驗形狀；`wg_overview.locate_from_goal` 照改檔時同一套判法
  - 通過：標 located_via=need_goal、掛節點、沒紀錄的部位先建紀錄
  - 沒過：回一行說缺什麼，改檔前照舊補交
  - 帳：`located_via_need_goal`／`locate_via_need_goal_rejected`
- **007 實測**：AI 為交四行多發一條只有 `#` 註解的指令，每部位多一個模型回合；這條路省掉那一回合
- **009 實測**：
  - 擋訊息同時教三條路，AI 挑了 need_goal update 那條（ToolSearch 載工具、update 被拒、read、再 update），多 4 個回合
  - 所以擋訊息與提示現在只教「同一則先發不寫檔指令的 `#` 註解」一條路
  - locate 欄只在這裡與 MCP 工具說明講（[DECL_HINT_KEEPS_EDIT_TOOLS](../TECH/release-rules.md#decl_hint_keeps_edit_tools)）

#### 只立一次與送回
- **目標樹只立一次**（[GOAL_TREE_SET_ONCE](../TECH/release-rules.md#goal_tree_set_once)）：
  - hook 只在改程式前沒樹時提醒 set 一次
  - reconcile 不再被任何提醒或回覆促使
  - 交付時對照由程式代填（RECONCILE_BY_PROGRAM）；AI 自己交照收
- **寫入的回覆送回樹**：
  - set 送全樹；add／update／reconcile 送精簡樹，不截節點
  - 拒收的項目附原因
- **其他 hook 提示**（[TREE_LINE_IN_HINTS](../TECH/release-rules.md#tree_line_in_hints)）：
  - 只附一行當前節點（`wg_need_goal.brief_line`）；沒有子節點就是樹根自己
  - 導讀卡與讀入範圍提示同一回合內容沒變只附一次
- **壓縮後重送**：照附樹根一行＋當前節點（`brief`）
- **退路**：`coding_guard.slim_reminders=false` 退回每則附樹根一行

#### 工具定義預算
- 工具定義（[`mcp.js`](../tools/workflow-guardian-mcp/lib/mcp.js) description＋inputSchema）估 ≤1,800 tok；每次模型呼叫都重讀
- schema 只留型別、enum 與必要欄位；拒收規則在 [`need-goal.js`](../tools/workflow-guardian-mcp/lib/need-goal.js)
- 案例：[`verify/verify_need_goal_schema_budget.js`](../tools/workflow-guardian-mcp/verify/verify_need_goal_schema_budget.js)

### 使用者說的要對得到原話
- **位置**：`wg_need_goal._check_origin` ＋ `wg_release_rules.origin_user_verdict`（規則 [ORIGIN_USER_NEEDS_QUOTE](../TECH/release-rules.md#origin_user_needs_quote)）
- **開關**：`guard.origin_user_check.enabled`（預設開）

#### 核對規則
- 時機：add／update 把子節點標 `origin=user`
- 選填 `quote`（或節點文字本身）要是樹上某則使用者原話的字面子串，至少 6 字
  - 樹上原話含匯入的前一個 session 原話
- 不到 6 字：要是某則原話的整句
  - 前後是句首、句末標點或換行；逗號不算句界
  - 去掉句末標點至少 2 個字
  - 引用自帶句末標點時要跟原話那個標點一樣，「要有測試。」對不到問句「要有測試？」
- **對上**：保持 user，節點存 `quote`、`said_seq`，history 記「引用第 N 回合」
- **對不到或只出現在同伴轉述**：
  - 強制改 inferred
  - 回傳附提醒；下一則訊息的樹提示再帶一次就清
  - `Logs/guard-need_goal.jsonl` 記 `origin_quoted`／`origin_downgraded`（節點文字與 quote 並列給人抽查語意）

#### 重核與原話來源
- 之後只改「使用者說的」子節點文字（含匯入的）也重核
  - 沒附新 quote 就拿節點存的 quote 核
  - 存的是當初節點文字對上的就不拿（`quote_by=text`）
- 核對用的原話另存在樹的 `said_all`：本 session 最多 200 則、單則 4000 字，不進續接單；不受顯示用 `user_said` 的 20 則／1000 字裁切影響
- 樹結束期間收的原話（`said_log` 還沒掛上任何樹）也算核對來源（[ORIGIN_SAID_INCLUDES_UNATTACHED](../TECH/release-rules.md#origin_said_includes_unattached)）
  - 原因：對照完樹結束後使用者再糾正，那則要等樹重開才掛回去，而重開排在同一次 update 的核對之後
- 匯入當下子節點不核；不擋工具呼叫

#### 樹根
- 樹根 origin 不動（契約：AI 對原話的解讀）；顯示一律「AI 的解讀」（續接單也是）
- set 開樹、改寫樹根、匯入時把樹根切句（。；，、——，≥6 字）
- 原話裡沒有的句子列一行「樹根這幾句原話裡沒有：…」，在當下回傳與下一則訊息各提醒一次，log 記 `root_unquoted`

### 新需求開始
- **位置**：UserPromptSubmit（`on_prompt`，排在導讀卡之前）

#### 記什麼原話
- 只認使用者本人打的字（`harness_text.user_typed_text`）
- 跨 session 訊息記成同伴轉述
- 系統通知不記，含沒有標籤包住的純文字通知：行首 `[SYSTEM NOTIFICATION - NOT USER INPUT]`、`[Cross-session idle notice]`、`[Cross-session delivery notice]` 那行起到訊息尾

#### 提醒
- **沒樹時**：第一則訊息提醒一次先寫目標
  - 寫明改程式、寫或整併文件、整理記憶或設定都算要動手
  - 寫整個需求，不只這回合先做的那段
  - 第一則提示寫明子目標每件一行「子目標｜…」，開新樹收下時不再另送題
- **有樹時**：每則只送回當前節點一行（[TREE_LINE_IN_HINTS](../TECH/release-rules.md#tree_line_in_hints)）
  - `coding_guard.slim_reminders=false` 時另附樹根一行與子目標、待展開、待對照的改動數
  - 原話對不上的提醒只在真有降級時附
- 目標樹提示只在寫碼回合送（[§11.2](../TECH.md#112-守門減量同一件事只問一次記帳交程式或免費模型) [CODING_TURN_ONLY](../TECH/release-rules.md#coding_turn_only)）；原話每則照記
- 樹對照完或結束後再提醒一次

#### 換題與糾正
- `set new_task=true` 在目前的樹還是進行中時要附 why（為什麼是另一件事、不是糾正或補充）
  - 與改寫樹根同成本
  - 收下時列舊樹沒結束的節點，叫它把被取代的標放棄
  - 已對照或結束的樹之後換題不用 why
- 糾正提醒（`on_correction`）寫明改這棵樹、不開新樹

#### 原話掛樹
- 從續接單匯入時，本 session 匯入前收到的使用者原話（常是開工句）掛進接續的那一棵
- 已對照或結束的樹重新打開（改寫樹根、增改節點、節點退回非終點、又改了檔）時，結束期間收的原話（例如對它的糾正）掛回來

### 沒樹時改了記憶知識類
- **位置**：PostToolUse 改檔蓋號（`stamp_edit`、`_knowledge_write`）
- **算不算記憶知識類**：只看查得到的事實
  - 還在的檔不是程式
  - 還在的目錄裡沒有程式檔（搬過去的目的地）
  - 已經不在的路徑有副檔名而且不是程式（刪掉或搬走的文件）
- **不算**：
  - 沒副檔名又不在的路徑（分不出）
  - 執行期資料（[RUNTIME_DATA_NO_OVERVIEW](../TECH/release-rules.md#runtime_data_no_overview)，不查 .gitignore）
- **算的**：
  - 記進目標檔 `untreed`：同一檔一筆，上限 200，超過丟最舊的並記 `untreed_dropped` 與守門紀錄
  - 這個回合第一筆只留守門紀錄 `knowledge_no_tree`，不送任何催立樹的提示（[NON_CODING_TURN_NO_NUDGE](../TECH/release-rules.md#non_coding_turn_no_nudge)：只改文件、記憶、設定的回合不跑守門）
  - 之後寫樹或從續接單匯入時，這些改檔掛進新樹（匯入時掛進接續的那一棵）
- 已對照或結束的知識類樹又改了知識類檔 → 退回進行中

### 改程式前
- **位置**：PreToolUse
  - 第一層 `edit_gate` 在 OverviewHub 之前
  - 第二層在 `wg_overview.on_edit`

#### 第一層：沒樹就擋
- **哪些檔算寫碼類**：
  - 部位類別不是知識類
  - 副檔名在 `reconcile_gate.code_exts` 聯集清單，或沒副檔名但第一行 `#!`
  - 搬移或複製（mv／cp／Move-Item／Copy-Item…）時來源含程式檔也算；來源是目錄就往下找
  - Write 新建沒副檔名而內容以 `#!` 開頭也算
- **沒有目標樹就擋**：
  - 擋之前先看 transcript 本使用者回合有沒有「目標｜」行，有就照它立樹再判（[TREE_SET_VIA_TEXT](../TECH/release-rules.md#tree_set_via_text)）
  - OverviewHub 關掉、沒專案根、表外檔都照查
  - 暫存檔不管
- **讀檔時的提示**：讀到部位的程式檔，沒樹就在定位提示那一行先講立樹（只教「目標｜」行；工具照收、不提）（[LOCATE_HINT_ON_FIRST_READ](../TECH/release-rules.md#locate_hint_on_first_read)，判式同一支 `_edit_gate_applies`）

#### 第二層：定位行
- **有樹時**，部位表上的程式檔，定位三行之後加第四行 `定位｜目標：<節點編號>（這一塊在目標裡的角色）`
  - 第四行（節點、括號內的角色）與範例佔位只記錄不擋
  - 沒寫或指錯節點就掛樹根；收尾 (f3) 從 transcript 補掛
  - 缺的記 `guard-need_goal` event=locate_soft（[LOCATE_LINES_NO_EXAMPLE_PLACEHOLDER](../TECH/release-rules.md#locate_lines_no_example_placeholder)）
- **根因層那行**：
  - 要兩個根因候選＋選擇理由，或「第二個不存在因為 …」
  - 一個使用者回合只擋一次，之後只留帳（[LOCATE_LINES_NEED_ROLE_AND_TWO_CANDIDATES](../TECH/release-rules.md#locate_lines_need_role_and_two_candidates)、TWO_CANDIDATES_ASK_ONCE，[§7.8](../TECH.md#78-放行欠帳判定規則hookswg_release_rulespy)）
- **第五行 `定位｜批判：…`**（照擋，[LOCATE_LINES_NEED_CRITIQUE](../TECH/release-rules.md#locate_lines_need_critique)）：
  - 與四行同一支判定，缺的一起列
  - 內容：這段現在的寫法合理嗎（合理＋理由，或不合理＋理由＋更好的做法）、同類還可能在哪（或「無，因為 …」）
  - 照抄範本不算
- 擋訊息附範例五行
- **定位帳**：核對通過記「部位 → 節點」，之後這個部位的改動掛到那個節點
- **隨樹交**：四行也可以在 need_goal set／update 的 `locate` 欄隨樹一起交（LOCATE_VIA_NEED_GOAL）
  - 程式照認；讀檔提示與擋訊息不提這條路、只教 `#` 註解（[DECL_HINT_KEEPS_EDIT_TOOLS](../TECH/release-rules.md#decl_hint_keeps_edit_tools)）
  - 交過的部位第一次改檔不擋、不掃 transcript（`_first_edit_once` 開頭確認 located）
- **目標改了**：開新樹、改樹根、改節點文字、匯入續接單（加子節點不算）→ 各部位的「已定位」清掉，只認之後交的那一組
- **擋滿放行**：同一個使用者回合、同一部位、同樣的缺件擋 2 次後第 3 次放行並留帳
  - 事件 `edit_deny_capped`，規則 [GATE_DENY_CAP](../TECH/release-rules.md#gate_deny_cap)，共用 `wg_core.deny_cap`
  - 沒在部位表上的改檔閘同樣，事件 `edit_unmapped_capped`
- **判不了**：讀不到 transcript＝閘判不了，這次不要求定位行（讀檔數照查）並記守門紀錄 error（[GATE_SELF_ERROR](../TECH/release-rules.md#gate_self_error)，不計次）
- **導讀卡開頭**：
  - 附當前節點一行（部位掛了節點就是那個；同一回合內容沒變只附一次）
  - 附定位第五行的格式提示
  - 三種情況同一個 session 只送一次全文（[CRITIQUE_CASES_ONCE_PER_SESSION](../TECH/release-rules.md#critique_cases_once_per_session)）

### 改了之後、交付之前
- **位置**：Stop `_verify_gates`（只有主 session）、PreToolUse commit 指令
- **目前狀態**：(f1)～(f4) 與 commit 前的目標對照都不擋
  - `reconcile_gate.goal_gate=false`（規則 [CLOSING_RITUAL_SWITCHES](../TECH/release-rules.md#closing_ritual_switches)）
  - 目標樹照記、帳照算

#### (f1) 待對照
- 改了程式檔就欠一筆「待對照」
- 收尾時程式照改到的檔與最近收據替那個節點記一筆進度（`auto_progress`，`by=program`）並清掉
  - 不擋；`goal_gate=false` 也照做
  - 背景本地模型另草擬一句（[§11.2](../TECH.md#112-守門減量同一件事只問一次記帳交程式或免費模型)）
- AI 要寫自己的判斷照樣 update（update／reconcile 依節點編號找所屬的樹，換題後舊樹欠的也交得進去）

#### (f2) 交付邊界查七條
- 開著時才查；交付邊界＝宣告完成、擋滿待查的原宣稱、本回合交了收尾檢核
- 查目前的寫碼類樹：
  - 交過完整對照
  - 目標版本沒變
  - 每個還活著的節點是終點
  - 達成／部分有證據且指標在
  - 收據晚於它支持的節點（含子孫與祖先）的最後一次改動
  - 達成不能只有推論；寫碼類的達成至少一筆沒紅的收據或讀碼級驗證案例（只有檔案、卡片、推論不算試過），且實測只配收據
  - 部分／沒有寫 followup
- 擋訊息印規則名、節點與現有每一筆證據（規則 [§7.8](../TECH.md#78-放行欠帳判定規則hookswg_release_rulespy)）
- **先紅後綠**：完整對照收下時，每筆案例證據對目標檔收據找「同一案例檔先紅、之後綠」
  - 對上記 `red_then_green` 並印在對照摘要
  - 對不上印「案例未見先紅」
  - 只記錄不擋

#### (f3) 改過程式檔的部位要掛節點
- 交付邊界另查改過程式檔的每個部位都在定位帳掛到活著的節點（改檔蓋號時記 `parts_edited`）
- 沒掛的先從 transcript 找補交的四行補掛；仍沒掛就擋，並列「<部位>：<改的檔> 沒掛目標」（規則 [EDITED_PART_NEEDS_GOAL_NODE](../TECH/release-rules.md#edited_part_needs_goal_node)）
- (f1)(f2)(f3) 三條都併進寫碼查核的擋訊息，同一個擋滿問使用者流程
- (f3) 帶規則行，擋次預算單獨計次

#### commit 前
- commit 指令執行前查 (f1)＋(f2)＋(f3)，缺了 deny
- 是不是 commit 與口令閘同一支判定：heredoc 本文裡的 commit 範例不算，heredoc 結束後真的執行的照算

#### (f4) 記憶知識類
- 記憶知識類（沒改過程式檔的樹）不進寫碼查核、commit 不擋
- 兩種情形算 (f4)：
  - 本使用者回合沒樹時改了記憶知識類的檔（不看措辭，規則 [KNOWLEDGE_EDIT_NEEDS_LIGHT_TREE](../TECH/release-rules.md#knowledge_edit_needs_light_treeknowledge_tree_reconcile_at_delivery)）
  - 交付邊界時任何一棵沒結束的知識類樹（換題後的舊樹也算）在最後一次完整對照之後還有改檔（規則 [KNOWLEDGE_TREE_RECONCILE_AT_DELIVERY](../TECH/release-rules.md#knowledge_edit_needs_light_treeknowledge_tree_reconcile_at_delivery)；樹上沒改檔的純問答樹不要求）
- 併進收尾報告欄 (e) 那一份擋，屬記憶與報告類：不問使用者
  - 這一份只數自己的次數（寫碼規則先擋過幾次不吃掉它）
  - 本回合第 3 次放行並記 `reconcile_overflow`（健檢列 red）
- 判不了不擋，寫 stderr 與守門紀錄
- 知識類的「達成」不要求案例或收據，可指到改過的檔（讀碼級）；推論最多標部分

### 問使用者之前
- **位置**：PreToolUse（settings.json matcher 掛 `AskUserQuestion|ExitPlanMode`，`wg_need_goal_points.on_ask`）；沒攔到的由 PostToolBatch 事後提醒
- **原則**：人只做真正的決定，而且看懂全貌才拍板

#### 三條規則（§7.8）
- **每一題要附推薦**：選項 label 標 `(Recommended)` 或題目含「建議：」；不分有沒有樹；【收尾放行確認】固定兩選項的放行題豁免
- **有樹時每一題各自指到節點**（[ASK_LINKED_TO_GOAL](../TECH/release-rules.md#ask_linked_to_goal) 只記錄）：
  - 比對範圍：題目＋選項 label 與描述，不含 header
  - 指到的方式：編號，或節點原文連續 8 字以上
  - 一題掛上不帶過同批其他題
  - 指到就記 checkpoint；沒指到只記 `ask_unlinked`，不擋不送
- **問改法而題目提到的部位還沒讀過檔**：
  - 題目沒提部位表上的路徑時，看本 session 有沒有讀過任何部位檔
  - 擋訊息或提示多一句「先讀過部位檔再問」（不單獨擋）

#### 擋訊息與放行題
- 擋訊息印規則名、缺哪一題、照抄可過的寫法，所有句子併成一則
- 放行題看結構：題目含【收尾放行確認】、選項正好固定兩個
  - 真有擋滿待放行紀錄時，整次全是放行題才整次豁免
  - 夾一般題或把標記塞進一般題，照查推薦
- 閘自己壞了照擋，只放整次全是放行題且真有待放行紀錄的

#### 審計
- PostToolBatch 每次提問記一筆審計 `ask_audit`
- 內容：擋過幾次、掛上哪個節點、沒掛上記「提問未掛目標（知識類／寫碼類）」

### 收尾與審查
- **位置**：PostToolUse 收尾檢核分支、HUD、`codex_companion` 驗收審查
- 收尾檢核報告自動附目前寫碼類樹（原話摘要、節點、對照結果）
- HUD 多一塊「目標對照」；收尾檢核本身不多欄
- 完整對照的部分／沒有寫進 `workflow/tracking/<slug>.jsonl`
- 驗收審查的「使用者目標」改給三段：使用者原話（權威）／同伴轉述／目標樹（AI 的解讀）；沒有同伴轉述就不印那段

### 重看
- **位置**：`wg_need_goal_points`（CRITIQUE_QUESTIONS）、`wg_need_goal`（完整對照的 same_class）
- **性質**：只送題不擋

#### 三個觸發
- 讀入範圍變大：子代理讀的檔不算進主 session 的讀入範圍，子代理也不收要它改主樹的提示
- 收到外部主張：審查結果、審查報告檔
- 目標改了重看部位：第一次 set 也算；只送一行（目標視角提問＋當前節點），不重貼導讀卡與定位範本（[GOAL_VIEW_ONE_LINE](../TECH/release-rules.md#goal_view_one_line)）

#### 送什麼
- 三個「用目標視角重看」的提示都多問兩句：這段寫法（或主張）合不合理、不合理的更好做法；同類別處還有沒有
- 再附三個具體情況題（`CRITIQUE_CASES`，定位第五行的提示也帶）：
  - 選替身時：替身和真正要判的事有沒有落差
  - 換測試環境或前提時：舊前置步驟還成立嗎
  - 寫「期望不發生」的案例時：它通過是因為規則對還是什麼都沒發生
- 回答寫進目標樹（update 的 why）

#### 每 session 送一次全文
- 三種情況每個 session 送一次全文，之後（含定位第五行的提示）換成一句指回（`CRITIQUE_CASES_POINTER`，規則 [CRITIQUE_CASES_ONCE_PER_SESSION](../TECH/release-rules.md#critique_cases_once_per_session)）
- 已送記在目標檔 `critique_sent`
  - 還沒有目標檔就照送全文、不建檔
  - 子代理用主 session 的目標檔，誰先收到全文就算送過
  - 壓縮後重送目標樹時清掉
- `coding_guard.slim_reminders=false` 退回每則全文
- 「交出前一問」已拿掉（[§11.2](../TECH.md#112-守門減量同一件事只問一次記帳交程式或免費模型)）

#### same_class
- 完整對照的達成節點可附 `same_class`（同類別處：找到的位置，或為什麼沒有）
- 沒附只提醒一句

### 續接
- **位置**：`handoff_block`／`import_handoff`／`recovery_blob`
- 續接單帶【需求目標樹】區塊：人讀段＋機讀 JSON
- 新 session 讀到 `_staging/next-phase*.md`：
  - 還沒有樹 → 自動匯入（新編號、舊證據標前一個 session、只供閱讀）
  - 已有樹 → 提示用 `import_from` 接續
  - 本 session 自己匯出的不重複匯入
- 壓縮後的目標樹獨立重送，不依附部位綜觀

### 紀錄
- **檔案**：`Logs/guard-need_goal.jsonl`
- **記什麼**：
  - 每次動作、擋改檔、擋定位（內容不夠時帶規則名）、提醒、匯入
  - (f1)(f2)(f3)(f4)
  - 沒樹改知識類（`knowledge_no_tree`）
  - commit 擋、鎖逾時、壞檔留證
  - session 結束記沒對照的樹（知識類對照後又改了檔也算）與沒樹改的知識類檔（`silent_unreconciled`）
- **收尾補掛**：記在 OverviewHub log（`relink`）

## A7.9 驗證範圍（verify_scope）

[↑ 主文 §7.9](../TECH.md#79-驗證範圍verify_scope)

這道閘已移除；原本的設計與部件見 [`_AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/驗證範圍閘封存-2026-10-29.md`](../_AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/驗證範圍閘封存-2026-10-29.md)。

## A7.10 切入點契約（程式問→卡教→LLM 判→留帳回看）

[↑ 主文 §7.10](../TECH.md#710-切入點契約程式問卡教llm-判留帳回看)

### 目的

- 程式停下來要 LLM 判斷的每個位置（切入點），判得準不準取決於那一刻注入的卡。
- 卡能加、改、退役，判斷力就能持續調。閘與案例守流程，卡守判斷。
- 本契約不加閘、不改任何閘的放行結果，只補「問的那一刻把判準卡送到」與「留帳回看」。

### 部件

#### 登錄表
- **位置**：[`workflow/entrypoints.json`](../workflow/entrypoints.json)（程式碼根，版控資料；現有 39 列、`not_entrypoints` 44 條）。
- **每個切入點一列**，欄位：
  - 代號
  - 名稱
  - 對應 RULES 規則名
  - 擋訊息裡穩定的識別字樣
  - 哪條路問（`path_values`）
  - 餵什麼、問什麼、期望判什麼
  - 回應型（`responses`）
- **代號**：
  - E01～E35 沿用 [`_AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/LLM切入點自評-2026-10-21.md`](../_AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/LLM切入點自評-2026-10-21.md) 的 E 號，之後新增的接著編。
  - 例：E38～E41 是 G6 階段 5 的糾正詞、否決記憶、衝突宣告、範疇宣告。
  - E36、E37 已撤：自檢評分不是切入點、上則評分只留帳。
- **`path_values`**：
  - 本契約接的路：stop_piggyback／pretool_deny／pretool_hint／mcp_reply／subagent_prompt／tool_cli。
  - user_prompt 只接程式自己組的問句，目前有 E38、E39。
  - session_start／post_tool_hint／local_llm 只登記不接。
- **`not_entrypoints`**：列 RULES 裡確定不是問 LLM 的規則與一句理由。
- 加切入點只改這份檔；程式不寫死任何代號，沒登錄的切入點沒有卡也沒有帳。
- **現況**：
  - E06、E30 沒登記任何路。
  - E31～E35 走不接的路。
  - 這 7 列拿不到卡。
  - subagent_prompt 路程式已接，但還沒有任何一列登記它。

#### 查表
- **位置**：[`hooks/wg_entrypoint.match_entries`](../hooks/wg_entrypoint.py)。
- 問句裡出現某列的規則名或識別字樣、而且那列登記了這條路 → 算這個切入點（可同時多列）。
- 登錄表讀不到或格式壞了 → 空表＋stderr，問句照原樣送。

#### 卡綁切入點
- **位置**：卡片 `- Entry:` 欄（[§4.1](../TECH.md#41-atom-卡片格式)）＋索引 `entry` 欄。
- **`cards_for_entry`**：
  - 先取 Entry 寫了這個代號的卡（知識段短的在前）。
  - 再拿那列的規則名＋識別字樣當查詢比卡的 trigger（與 UPS 同一支比對）當退路，命中數多的在前、同分短的在前。
  - 給裁判用的規格卡不綁 Entry（不另加白名單）。
- **候選池**：
  - 全域索引＋state 記的專案層／公司層索引。
  - scope 可見性與被取代的卡照 SessionStart 同一套。
  - 沒有 state 時沒有身份，personal／role 卡不給。

#### 預算
- **設定**：
  - `entrypoint.inject_budget_tokens`（每個切入點各一份，預設 400）。
  - `entrypoint.inject_budget_total`（同一則問句總上限，預設 1200；`wg_core.DEFAULTS`）。
- **`judgment_cards`**：只取知識段，標「判準卡（E04）：<卡名>」。
- **額度**：每個切入點實際可用＝min(各自預算, 總上限÷認出的切入點數)，切入點多時每個都分得到、整則不超過總上限。
- **送的順序**：先送每個切入點的綁定卡、再送每個切入點的退路卡。
- **共用卡**：一張卡同時是幾個切入點的判準卡只送一次（算在第一個送它的切入點）、標題列全部代號。
- **超額**：某個切入點超過它自己的額度就截斷最後一張（尾端「已截斷」）、它後面的卡不送；有卡卻沒送完的切入點帳上都記 truncated。
- 標題列不計入預算。沒卡就什麼都不接、不印「無」。

#### 健檢
- **位置**：`wg_entrypoint.health_block` → [`tools/health-weekly.py`](../tools/health-weekly.py) 2f 段（只進 info）。
- **列出**：
  - RULES 裡既沒登錄也不在 `not_entrypoints` 的規則名
  - 登錄表寫了但 RULES 沒有的規則名
  - 卡片 Entry 寫了但登錄表沒有的代號
  - 重複代號
- 只列不擋。

#### 問的那一刻注入
- **單一入口**：`wg_entrypoint.entry_note(問句, 路)`。
- **保護匯入**：[`handlers/_shared`](../hooks/handlers/_shared.py) 保護匯入（模組壞了退成不接卡＋stderr，不拖垮 handler）。
- **例外**：[`stop.py`](../hooks/handlers/stop.py) 直接匯入 `wg_text_score`、它又直接匯入 `wg_entrypoint`，這條鏈沒有保護，`wg_entrypoint` 載不起來時 Stop handler 整支載不起來。
- **各路接在哪**：
  - stop_piggyback：
    - Stop 的 `_piggyback`（只拿這道閘自己的擋訊息認切入點，卡接在後面所有預覽與提示之後）。
    - 子代理收尾 `_code_gate_no_ask` 的擋訊息（裁判子 session 走同一支但不接）。
    - PickOne 續跑提醒。
  - pretool_deny：PreToolUse 的 deny 全走 `_deny()`（裁判子 session 的 JudgeWrite 除外：裁判不注入）。
  - pretool_hint：提問前提醒與一般警告段的 additionalContext（systemMessage 給使用者看的那份不接）。
  - 上面三者共用 `_with_cards()`：
    - 只在真的要送訊息時才匯入與讀登錄表。
    - 什麼都不送的放行路徑零成本。
    - 派子代理時每次多讀一次登錄表。
  - mcp_reply：PostToolUse 對 `mcp__` 工具的單一出口，拿工具本體回覆＋同一次補的提醒認切入點，卡多接一段 additionalContext。
  - subagent_prompt：派子代理時，卡接在記憶 blob 之後、原 prompt 之前。
  - tool_cli：AI 自己跑的本系統命令列工具印給它的問題（目前沒有接卡的）。
- 原訊息逐字不變，卡一律接在最後。

#### 留帳
- **位置**：`Logs/guard-entry.jsonl`（`append_guard_log("entry")`）。
- **每個認出的切入點一筆**，欄位：
  - at、event=ask
  - session_id、turn_seq（沒有 state 記 null）
  - entry、path
  - cards（這個切入點送了哪幾張）、truncated
  - with（同一問句還認出哪些代號，調識別字樣用）
  - response（問的當下記 none）
  - 另附呼叫端給的標的鍵
- 沒認出的問句不記。

#### 回應型
- **位置**：`wg_entrypoint.resolve_responses`；登錄表每列 `responses` [{guard, event, type, match?}]；`entry_note(extra=…)` 把這次問的標的寫進問的帳。
- **判法**：照各閘自己的留帳推 AI 被問之後怎麼回。
  - 窗口＝這筆問之後到同 session 同代號下一次問（含）。
  - 窗口裡第一筆對上的閘紀錄給 declared／denied／judged／released。
  - 沒對上但同一回合又被問一次 → denied。
  - 換回合才又被問或不知道回合 → none。
- 只列「AI 回應之後」才寫的紀錄。
- E01／E02／E03／E05／E17／E19／E24（宣告收下）／E28／E29 的閘沒有可用留帳，只能靠「同回合又被問」推 denied。
- 規則寫了 match（鍵名清單）就還要問的帳與閘紀錄這些鍵相同。
- **限制**：
  - 時間戳只到秒，與問同一秒的紀錄不算（閘紀錄自己記到微秒就不受影響）。
  - 沒寫 match 的列帳上沒有標的，同 session 同代號別件事的回應會算進來。

#### 統計
- **位置**：[`tools/entry-stats.py`](../tools/entry-stats.py)（唯讀）。
- **參數**：`--days`（預設 7）、`--logs`、`--registry`、`--json`、`--asks`。
- **每個切入點**：問幾次、有卡幾次、送幾張、截斷幾次、各回應型幾筆、同一問句也認出哪些代號。
- **`--asks`**：另列每次問一筆（at、session、turn_seq、entry、path、cards、truncated、response、response_by、with）；回應型就是 `resolve_responses` 判的，不另寫判法。
- **尾行**：`ENTRY_STATS DONE entries= asks= cards= truncated=`，給了 `--asks` 再加 `asks_listed=`。
- 驗收判分讀它（文字評分週彙總不讀，見 [§7.11](../TECH.md#711-文字規格評分g15toolstext-scorepy)）。

#### 自檢評分（開發期工具，不是切入點）
- **位置**：[`skills/console/scripts/selfscore.py`](../skills/console/scripts/selfscore.py)。
- **用法**：
  - `--ask --g G8` 問。
  - `--g --score --basis（可重複）--why --rater` 答一筆。
  - `--summary [--days --json --logs]` 統計。
  - session 預設取 Claude Code 給工具子行程的 `CLAUDE_CODE_SESSION_ID`。
- **何時用**：總控台、checklist 軌、驗收判分打「這個 G 幾分」時。
- **`--ask`**：印 G 名、評分規格卡 `g<N>-評分規格*.md` 知識段三句、可用證據清單與要答的三件事（不接判準卡、不記 guard-entry）。
- **帳本**：
  - 答的一筆記 `Logs/guard-selfscore.jsonl`（event=score：g、score、basis、why、rater、unanswered）。
  - 缺欄位或分數不是 0～10 的整數照記「沒答」（原字留 score_raw），stderr 一行、不擋。
  - 帳本不是卡：不注入、不過期。
  - 分數只收 ASCII 0～10（「²」、負數、小數都記沒答）。
  - 寫帳失敗 stderr 說沒記到、尾行 recorded=0、exit 1。
- **`--summary`**：每個 G 最近一筆、最近五個分數走勢、比上次差多少。
- **尾行**：`SELFSCORE DONE asked=1`／`recorded=1 unanswered=`／`gs= records= unanswered=`。

### 刻意不做

- 不加閘、不放寬既有閘、不加例外清單；擋訊息既有格式與規則名不動。
- session_start、local_llm 這兩條路只登記不接。
- post_tool_hint 只接改程式檔那批的收尾類提醒（`post_tool_batch.closing_reminders` 把整批提醒行當一句問、卡接在後面，讀檔導讀不接）。
- user_prompt 只接程式自己組的問句（糾正問句 E38、否決問句 E39）。
- 另一支 Stop hook [`hooks/codex_companion.py`](../hooks/codex_companion.py) 自己的擋訊息沒接。
- 識別字樣是子字串比對，訊息裡當範例出現的字樣也會認到，靠帳上的 with 欄回頭調字樣。

### 問法調校：六處擋訊息字句

- 問法本身也是調校點：擋訊息字句會把 AI 帶到哪裡，跟注入的卡一樣影響判斷。
- 下面幾處的字句照切入點自評的實測改成「先分辨情況再給處置」（擋的條件不變）。
- 改前改後用內網 gemma4:e4b 實測，紀錄在 [`_AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/LLM切入點自評-實測/`](../_AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/LLM切入點自評-實測/)（[`cases_003.json`](../_AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/LLM切入點自評-實測/cases_003.json)、[`results_003.jsonl`](../_AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/LLM切入點自評-實測/results_003.jsonl)、README 判定表）。
- 字句由 [`hooks/verify/verify_entry_wording.py`](../hooks/verify/verify_entry_wording.py) 守。

#### E08 TestFailGate
- **字句在哪**：[`handlers/stop.testfail_message`](../hooks/handlers/stop.py)
- **現在怎麼問**：先看使用者有沒有叫跳過這支。
  - 有 → 測試照紅、寫引原話的不做行（程式只收這種豁免，所以同一句也認得出 E09）。
  - 沒有 → 修到綠：
    - 程式錯修程式。
    - 使用者要的新行為讓舊斷言不再對，就先宣告改舊測試再改斷言。
    - 不准加 skip／xfail、不准只為變綠改斷言。
  - 都不成 → 收尾別說完成。

#### E21 改舊測試提示
- **字句在哪**：`wg_oldtest.hint`
- **現在怎麼問**：先分是哪一種。
  - 使用者要的新行為讓舊斷言不再對 → 宣告引原話再改。
  - 使用者只說跳過 → 撤回、照紅、寫不做行。
  - 兩種都對不上才問。

#### E22 卡片版拒寫
- **字句在哪**：`wg_gate_bypass.atom_refusal`
- **現在怎麼問**：先問讀者能不能照著做讓閘擋下的內容不經修正就過關。
  - 能 → 是教繞法（即使自認誤擋）。
  - 不能 → 才宣告「不是教繞閘｜…」。

#### E05 提問前先讀部位
- **字句在哪**：`wg_release_rules.ask_overview_verdict`
- **現在怎麼問**：這條不單獨擋；但被別條擋下要重組時，先讀題目提到、還沒讀的部位檔，讀完再定推薦或判斷不必問。

#### E11 退避舉證
- **字句在哪**：[`handlers/user_prompt_submit.evasion_ask`](../hooks/handlers/user_prompt_submit.py)
- **現在怎麼問**：
  - 排在那一則注入最前面。
  - 先處理這件再做新請求：寫成本、小就先做掉；真的不做或只是描述就寫不做行／不是退避行。
  - 不點卡名。

#### SmellGate 處置句
- **字句在哪**：[`tools/project-smells.render_commit_report`](../tools/project-smells.py)
- **現在怎麼問**：先分被點名的檔是不是你這次改的。
  - 是 → 修或 smell-ok。
  - 不是 → 不修、不動它的暫存，只提交自己的檔。

## A7.11 文字規格評分（G15，`tools/text-score.py`）

[↑ 主文 §7.11](../TECH.md#711-文字規格評分g15toolstext-scorepy)

### 目的與自動評範圍

- 照一份「規格」對任何文字逐條判是非、產出評分表；裁判只用開源免費模型（Ollama），付費模型 0 token。
- 手動指令之外，收尾自動評：
  - Stop 把交付「改了哪些程式」的那則回覆丟背景評、留帳。
  - 條件：本使用者回合改了程式、這則宣告完成，一回合一則（規則 TEXT_SCORE_CODE_REPLY_ONLY）。
  - `text_score.reply_scope=all` 退回每則都評。
  - 其他回覆由使用者叫 skill `text-score`。
- 文件只在 `text_score.auto_targets` 列了 `docs` 樣式時才跟著那則一起評（出廠沒列＝不評文件）。
- 下一則使用者訊息只記一筆「上則評完了」，不注入、不叫 AI 照抄；不擋。

### 部件

#### 規格
- **位置**：`text-specs/<代號>.md`（程式碼根，版控資料；寫法 [`text-specs/README.md`](../text-specs/README.md)）。
- **格式**：
  - 開頭六鍵：規格代號＝檔名、適用、讀者、讀者目的、通過線、維護。
  - 檢核項表：代號｜問題｜判法｜必過｜沒過時｜來源。
  - 選填判例表。
  - 最多 8 條、來源必填，格式錯 exit 2。
- 程式不寫死條目。
- **判法只認四種**：
  - `模型判`（整份）
  - `程式切出標題後的第一句 → 模型判`
  - `程式切出前 N 句 → 模型判`
  - `程式先抓候選詞 → 模型判…`
- **不放 [`rules/`](../rules/)**：Claude Code 會把 rules 底下的 md 每個 session 遞迴載入。
- **說明檔**：同資料夾的 `<代號>-說明.md` 是給人看的白話說明（每條一個只寫代號的標題、連到判準卡），評分一行點進去的地方；不是規格，text-score 不讀、規格清單不列。

#### 前處理
- **函式**：`clean_text`／`sentences`／`candidates`。
- **檔頭**：
  - 去掉開頭 `---` 檔頭（`strip_frontmatter`）。
  - 判法：第一行是「鍵: 值」、冒號後接空白或行尾，`https://` 不算。
  - 框裡每一行都要是（可縮排的）鍵值或清單項；標題、縮排正文都不算，有一行正文就整段留著。
  - 交付信的 to:／seq: 不送裁判、不算句子、不算字數。
- **去掉**：code 區塊與網址（inline code 留著）。
- **句子**：
  - 標題（含引用裡的標題）、表格分隔線不算句子。
  - 去掉引用與清單符號。
  - 句號、問號、驚嘆號與換行是句界。
  - 英文句點後接空白與大寫字母才算句界。
- **候選詞**：
  - 只收像代號的字：inline code 整段、旗標、帶 `. / : _ -` 的名字、全大寫縮寫、字母夾數字。
  - 最多 12 個。

#### 裁判
- **函式**：`make_client`／`ask_judge`。
- **backend**：沿用 `ollama_client` 的 backend 設定、優先序與退避（[§9.1](../TECH.md#91-ollama-dual-backend-三階段退避toolsollama_clientpy)）。
- **每台的模型**：
  - 換成那台的裁判：`text_score.judge_model_by_backend`，沒列到的用 `judge_model`。
  - `--model` 給了全部用它。
  - `ollama_client` 不指定模型、送出前換成每台自己的。
  - 那台沒裝就算不在，不換成它原本設定的模型。
- **呼叫方式**：
  - 原生 `/api/chat`，`think:false`、`temperature:0`、明帶 `num_ctx`。
  - `format` 帶 quote → reason → verdict 的 schema。
  - 每條各問一次，題目在前、原文在後（每條開頭不同，不會接著上一條的快取算）。
- 都不在 → 剩下的條記未評、exit 0。

#### 驗收
- **函式**：`check_answer`。
- **引用驗證**：附了引用就要逐字落在送去的那段原文（不分判定；R1 只對第一句、R2 只對前三句）。
  - NFKC 統一全半形。
  - 每行去掉行首的引用／標題／清單符號。
  - 去 `*` 與反引號與空白。
  - 「…」分段依序比對。
  - 不做相似度。
- **作廢條件**：
  - 引用對不到。
  - 判否沒附引用。
  - 省略號以外不到 4 字。
  - 判定不是是／否／不適用（含 null）。
  - 回的不是 JSON。
  - `prompt_eval_count` ≥ `num_ctx`×95%（實測內網 Ollama 超過 num_ctx 時回報整段長度，不一定截到 num_ctx）。
- **欄位型別不對不會當掉**：token 數當 0、內容不是字串算不是 JSON。
- 呼叫拋出沒料到的例外記未評並 stderr。

#### 算分
- **函式**：`tally`。
- 過＝是＋不適用。
- 必過「否」或非必過「否」超過通過線容許數 → 不過。
- 必過作廢或未評 → 未定。
- 全部未評 → 未評。
- 摘要 `評分 N/M｜沒過：…｜作廢：…`。
- 裁判回答裡的分數欄一律不看。

#### 留帳
- **位置**：`Logs/guard-text_score.jsonl`。
- 寫不進去不擋（exit 0），stderr 說原因、尾行 `logged=0`。
- **一則一行**，欄位：
  - ts、session（`--session`）、kind（manual 或自動評的種類）
  - spec、spec_sha、source、text_sha、chars
  - model（排定的裁判，不重複）、judges（backend → 裁判）、models_used（實際回答的）、backends
  - secs、prompt_tokens、answer_tokens
  - pass／fail／na／void／unscored、score、total、overall、summary
  - items（每條 status、verdict、quote、reason、why、secs、token）
- 不存原文。

#### 自動評入口
- **參數**：`--auto-kind <種類>`／`path_matches`。
- **不評的情況**（印「不評：<理由>」、不問裁判、不留帳）：
  - `text_score.enabled=false`。
  - 種類不在 `auto_targets`。
  - 來源路徑不符該種類的路徑樣式。
  - 去掉檔頭與 code 與網址後的非空白字少於 `min_chars`。
- **路徑樣式**：
  - `auto_targets` 是 `{種類: 樣式清單}`。
  - 樣式從任何一層資料夾起算。
  - `*`／`?` 不跨資料夾、`**/` 零或多層、其他字元照字面、不分大小寫。
  - 空清單不比路徑。
  - stdin 沒有路徑，有樣式就不評。
  - 寫成種類清單的舊設定照舊只比種類。
- 收尾接線（下面「收尾接線」）用它。

#### 尾巴一行
- **參數**：`--tail-line`。
- stdout 只印摘要一行，不印評分表與尾行；照樣留帳。
- 摘要同留帳的 summary：
  - `評分 N/M｜沒過：…`
  - `評分 N/M｜全過`
  - 有作廢就帶 `｜作廢：…`
  - 裁判不在 `評分 未評｜裁判不在`
- 不評時 stdout 空、原因寫 stderr。
- 收尾背景評用它（輸出不讀，回覆尾巴那行取自留帳的 summary）。

#### 收尾接線
- **位置**：[`hooks/wg_text_score.py`](../hooks/wg_text_score.py)（Stop `on_stop`、UserPromptSubmit `tail_note`、背景入口 `--job`）。
- **前提**：config 要有 `text_score` 段且 `enabled` 為 true 才做事。
- **Stop**（各閘之前，被擋的回合也送）：
  - 回覆只送交付改程式那則：
    - [`stop.py`](../hooks/handlers/stop.py) 判 code_reply＝本使用者回合改了程式檔、這則宣告完成，`_reply_in_scope` 一使用者回合一則。
    - `reply_scope=all` 才每則都看。
  - 去空白後 ≥ `min_chars`（粗篩，精確字數由 `--auto-kind` 判）且跟送過的不同 → `final_reply`。
  - 本 session 本回合改過、還在的 `.md` → `docs`：
    - 只在 `auto_targets` 列了 docs 樣式時才送，出廠沒列。
    - 路徑樣式由 `--auto-kind docs` 判，不符不評。
  - 同一則、同一版文件不重送。
- **背景行程**：
  - 只寫工作檔 `workflow/text-score/<session>-<亂碼>.json`、起一個沒有視窗、脫離 hook 的背景行程就回。
  - 背景在自己的行程裡逐份呼叫 text-score 的 main：final_reply 從 stdin、docs 給路徑，`--session` 帶本 session。
  - 一份出錯只記那份，錯誤落 `workflow/text-score/worker.log`。
  - 評完刪工作檔、超過一天沒人收的清掉。
- **需求目標**：
  - 回覆與文件都要有當下的需求目標（`current_goal`：目標樹樹根，沒樹用本回合使用者原話）。
  - 都沒有這次不評。
  - 任務帶 `goal` 給 `--goal`。
- **UserPromptSubmit**：
  - 上一回合送評那則評完（留帳同 session、同 text_sha、kind=final_reply）→ `Logs/guard-text_score_tail.jsonl` 記 recorded 一次，不注入、不叫 AI 照抄。
  - 還沒評完記 pending，之後不補記。
  - docs 不記。
  - 要看分數叫 skill text-score 或查留帳、週彙總。
- **細節**：
  - 「上一則」指本回合最後一則夠長的回覆（最後是短碎句時指它前面那則）。
  - 文件評的是背景讀到時的內容。
  - 背景起成功後才失敗的那一則不重送（失敗記在 worker.log）。

#### 週彙總
- **位置**：[`tools/text-score-weekly.py`](../tools/text-score-weekly.py)（唯讀；`--weeks`、`--log`、`--json`）。
- **內容**：最近 N 個 ISO 週，每份規格：
  - 則數、裁判不在數
  - 實際回答的裁判各幾則（models_used；沒有這欄的舊紀錄記「沒記」、裁判都不在記「沒回答」）
  - 種類各幾則（final_reply／docs／manual）
  - 每條每週過率（是 ÷（是＋否））
  - 最近兩週趨勢（百分點）
  - 作廢數
- 規格雜湊不只一版時標出。
- 尾行 `TEXT_SCORE_WEEKLY DONE weeks= records= unscored= void= bad=`。

### 案例與已知限制

- **案例**：
  - [`tools/verify/verify_text_score.py`](../tools/verify/verify_text_score.py)（假 Ollama 伺服器，回應形狀錄自真回應）。
  - 收尾接線 [`hooks/verify/verify_text_score_stop.py`](../hooks/verify/verify_text_score_stop.py)。
  - 真打量尺 [`tools/verify/probe_text_score_real.py`](../tools/verify/probe_text_score_real.py)（5 份樣本印對答率與秒數，`TEXT_SCORE_REAL DONE …`，不當閘）。
- **已知限制**：
  - 裁判的判定與理由會自相矛盾，「找得到…就答否」這類反向問法最常見，所以條目一律正面問（通過＝答「是」），程式驗不出矛盾本身。
  - 裁判把引用改成簡體字、或改寫數字會被作廢。
  - Ollama 重用快取時 `prompt_eval_count` 只算新算的 token，截斷判定與 token 數會偏低。

## A7.12 連鎖斷路器（`hooks/wg_chain.py` 判定、`lib/chain_store.py` 帳與快照）

[↑ 主文 §7.12](../TECH.md#712-連鎖斷路器hookswg_chainpy-判定libchain_storepy-帳與快照)

### 目的與開關

- 閘擋了 AI 修、修了又被擋，一路修下去會偏離原本要做的事；連成一串時停下來交使用者決定。
- 寫碼守門開著、`chain_breaker.enabled` 為 true 才跑。
  - 出廠 config 寫開。
  - 設定裡沒寫這段＝不開。
  - 寫碼守門關時以總開關為準、整個不跑。
- 每種情境一條有名字的規則，寫在 [`hooks/wg_chain.py`](../hooks/wg_chain.py) 的 `RULES`（不在 [§7.8](../TECH.md#78-放行欠帳判定規則hookswg_release_rulespy) 那份表；同閘照對象計數在 [§7.8](../TECH.md#78-放行欠帳判定規則hookswg_release_rulespy) 另有一列，記各閘要報的對象）。
- 斷路器自己不逼修補、不要求任何宣告，只在警報後擋：收尾擋一次、停手中擋下讀與問以外的工具呼叫。

### 記帳

- **什麼記一條邊**：
  - 同一個使用者回合、同一個對話者（主 session 或同一個子代理）裡：閘擋下或記欠 → AI 動手 → 又讓任一道閘擋下或記欠。
  - AI 動手＝改檔、重跑、寫卡、重交報告、改目標樹；讀檔不算（CHAIN_ACTION_FACTS）。
- **閘名**：
  - 取擋訊息第一個 `[Guardian:名稱]` 標記，認不出才用呼叫端的預設名（工具前是 `PreToolUse`）。
  - 不同的閘混成同一個名字會讓同閘次數算錯，所以每道閘的擋訊息都要帶標記。
  - 改舊測試閘三條擋路第一行都是 `[Guardian:OldTestDeclare]`，✗ 條目在下一行行首（CHAIN_GATE_NAME）。
- **不算連鎖、不接邊**：
  - 原樣重試、只改寫回覆就又撞同一道閘：交回那道閘自己的擋次上限（CHAIN_SAME_GATE_NO_ACTION）。
  - 兩次之間的動作都沒改到檔：
    - 例：重跑測試、建刪暫存工作樹這類沒寫入目標的指令、重交收尾報告、改目標樹。
    - 同一道閘不接邊、不算同閘次數，動作照列進經過表。
    - 改到檔＝改檔、寫卡、子代理（`wg_chain.changes_files`，[CHAIN_NO_EDIT_NO_EDGE](../TECH/release-rules.md#chain_no_edit_no_edge)）。
  - 中間做了別的動作（回應別的提示）之後原封不動重送上一次被擋的同一個呼叫（CHAIN_SAME_CALL_RETRY）：
    - 判法：工具名＋參數逐字相同，帳上 gate 記 `call`。
    - 也算原樣重試，不接邊、不算同閘次數。
    - 改了內容或在指令裡補了宣告（呼叫變了）照舊算。
  - 同一個 hook 事件裡先後擋的。
  - 擋的時候就已列在「後面還會擋」預覽裡的。
  - 兩邊看的檔沒有交集的。
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
  - 同一道閘擋同一個對象這一段第 `max_same_gate` 次（2）。
  - 兩次之間 AI 看過擋訊息後有改到檔的動作。
  - 這次擋的不是原封不動的同一個呼叫。
- **中止**：這一回合其餘閘只記錄、不擋、不記欠，同一道閘只記一筆（CHAIN_ABORT_RECORD_ONLY）。
  - 被改成只記錄的閘不留「本回合擋過」標記，選繼續之後照常擋。
- 要擋的是繞回原點的修不停，那就是同一道閘擋同一個對象第 2 次。

#### 同閘照對象計數（CHAIN_SAME_GATE_PER_OBJECT）
- **原則**：同一道閘擋不同對象，各要各的證據，第 1 次補的沒讓第 2 次多欠什麼，各算各的第 1 次。
- **例**：
  - 定位閘先擋【訂單結帳】、AI 交定位改完，再擋【測試】：兩個部位各自的第 1 次，不響。
  - 部位 A → B → 又回到 A，A 第 2 次照響。
- **對象由誰報**：工具前閘擋下時報給斷路器（`pre_tool_use._deny` 的 `watched`／`target`，帳上記在觸發那筆）。
- **各閘怎麼報**：
  - 定位閘因為「這個部位欠證據」擋下時：
    - 報部位與擋的檔。
    - `target`＝它累積證據用的同一把鍵：專案根與部位名，表外的檔是專案根與頂層目錄。
    - 設定有錯（整層壞了，換部位也一樣擋）、唯讀路徑的擋不報。
    - 判不出部位（部位表讀不到、查表出錯）連檔也不報，免得同部位換個檔被算成別的對象。
  - 動資料檔、改舊測試：
    - 報這次要寫的檔。
    - 改舊測試另加呼叫前還欠宣告的那幾支。
    - 寧可多報、不可漏報。
    - 判不出部位或檔就不報。
- **比法**：
  - 兩次都報部位 → 比部位。
  - 都只報檔 → 有交集算同一個。
  - 有一邊沒報、或一邊報部位一邊只報檔 → 照閘名算。
- **說不出擋什麼的閘不報、照閘名**：
  - 版控口令、提交隱私、病形閘、繞閘、目標樹、svn 測試路徑這些看整批提交或整個 session 的。
  - 跨層寫入這類禁區（換個檔再撞也算繞回原點）。
  - 收尾各閘。
- 中間沒動作不算、同一則回覆算一步照舊疊在上面。
- 這些閘報了檔之後，「兩邊看的檔沒有交集不接成邊」（CHAIN_EDGE_FILES_DISJOINT）也有資料可用，只影響深度、不影響同閘次數。

#### 深度
- 深度（閘→修→閘→修→第三次閘＝2）照算、照列進經過表。
- **預設不警報**：三道各管各的閘各擋一次不是連鎖。
- `chain_breaker.depth_alarm` 設 true 才在深度到 `max_depth`（2）時也警報（CHAIN_ALARM_DEPTH）。

### 能互動的 session

- **停手**（CHAIN_HALT_UNTIL_ANSWER）：到使用者選「繼續」或「放行」之前，讀（Read／Grep／Glob、唯讀指令）與 AskUserQuestion 以外的工具呼叫先擋下。
- **收尾擋一次**，送連鎖過程表，欄位：
  - 第幾步、哪道閘
  - 擋的對象（說不出寫 —）
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
- **被取代的擋訊息**（[CHAIN_ABORT_SHOWS_REPLACED_BLOCK](../TECH/release-rules.md#chain_abort_shows_replaced_block)）：
  - 警報在哪一次響，那道閘原本的擋訊息照附在取代它的中止通知或停手訊息最後。
  - 含附註，例如紅測閘的基底紅缺哪一件。
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
- **例外**（[CHAIN_HEADLESS_KEEPS_DATA_GATES](../TECH/release-rules.md#chain_headless_keeps_data_gates)，`wg_chain.KEEP_BLOCKING`）：
  - 會改使用者資料的閘照擋，含讓警報響的那一次。
  - 有：動資料檔、改舊測試、commit 前的口令／隱私檔／svn 測試路徑、專案 session 改根層核心或全域 MCP。
  - 經過表標「會改使用者資料照擋」。
- **判法**：`wg_release.non_interactive_reason`、警報那一刻判。
  - 入口（環境變數 `CLAUDE_CODE_ENTRYPOINT`，沒有再看 transcript 的 entrypoint 欄）是 `sdk-*` 才算 headless。
  - `claude -p` 卻把入口設成 `claude-vscode` 的跑法（驗收工具為了讓第二意見照常觸發會這樣設）照能互動算、會停手。
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
  - PreToolUse 開頭 `_chain_halt`、擋下時記觸發（定位閘、動資料檔、改舊測試帶擋的對象）、放行出口存快照。
  - MCP 的寫卡、搬卡、目標樹工具也掛在 PreToolUse matcher 上（[§3.1](../TECH.md#31-settingsjson-十一個事件)）。
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

# 寫碼守門（乙篇）

[↑ TECH.md（開頭與甲篇）](../TECH.md) ・ 細節 → [TECH/guards.md](guards.md) ・ 規則全表 → [TECH/release-rules.md](release-rules.md)

寫碼守門是記憶系統上面另加的一層。AI 改程式時，它在改檔、問人、宣告完成、提交這幾個時刻多查一次。

- **出廠關**：設定鍵 `coding_guard.enabled` 出廠是 false。
- **開法**：本機設環境變數 `WG_CODING_GUARD=1`，或在不進版控的 `workflow/config.local.json` 寫 `{"coding_guard": {"enabled": true}}`（[乙1](#乙1-開關與減量原則)）。
- **開了也只在寫碼回合跑**：這個使用者回合用工具改過程式檔，才跑每回合的檢查。純問答、只改文件的回合不跑。

開關不只開關這一層。記憶系統（含基本守門）還有 36 處行為跟著變，例如記憶系統的收尾閘從「擋」變成「只提醒」。這些差異只列在一個地方：[TECH.md〈守門開關會改到記憶系統的地方〉](../TECH.md#守門開關會改到記憶系統的地方)（下文簡稱「跨層表」）。

本篇寫的都是**守門開時**的行為。守門關時，本篇各閘都不跑。

---

## 乙1 開關與減量原則

### 開關

- **設定鍵**：[`workflow/config.json`](../workflow/config.json) 的 `coding_guard.enabled`，出廠 false。
- **判法**：`wg_core.v6_enabled`（[`hooks/wg_core.py`](../hooks/wg_core.py)）。先看環境變數，沒設才看設定。設定只認 JSON 的 true，寫成字串 `"true"` 也當關。
- **本機開**：`WG_CODING_GUARD=1`，或 `workflow/config.local.json` 寫 `{"coding_guard": {"enabled": true}}`。
- **強制關**：`WG_CODING_GUARD=0`。
- **舊名照認**：設定鍵 `v6`、環境變數 `WG_V6`。
- 守門相關的其他鍵（`coding_turn_only`、各閘的 `guard.<名>.enabled`…）→ [TECH §12.1](../TECH.md#121-功能開關不想要某個功能時逐鍵關)、[TECH/config.md](config.md)。

### 開關改了什麼

| 範圍 | 守門關（出廠） | 守門開 |
|---|---|---|
| 寫碼守門這一層（乙2～乙11） | 整個不跑 | 只在寫碼回合跑 |
| 記憶系統（含基本守門） | 出廠行為 | 36 處行為改變 → [跨層表](../TECH.md#守門開關會改到記憶系統的地方) |

守門關時整個不跑、也不算跨層的項目（只在本篇）：

- 寫碼查核 ReconcileGate、拐彎判斷與閱讀路徑、等值閘、收尾自清、Reload 建議、PickOne、連鎖斷路器。
- 動資料檔 DataFileAsk、改舊測試 OldTestDeclare、病形閘 SmellGate、繞閘宣告 GateBypass、問使用者附推薦。
- 驗收規格提示與驗收裁判、開場的部位表骨架提示、部位表讀檔帳、驗證收據哨兵記帳、搬程式目錄記帳。

hook 計時與快逾時降級也只在守門開時有（[乙11](#乙11-hook-計時與快逾時降級)；跨層表 #6）。

不屬本篇、不看這個開關的：

- 手動文字評分 `/text-score` → [TECH §7.7](../TECH.md#77-文字規格評分toolstext-scorepy)。
- 基本守門（口令、隱私、驗證批次、根層保護…）→ [TECH §7](../TECH.md#7-基本守門)。
- 程式細則檔 `rules/code-thinking.md`、`rules/coding-style.md`：開頭有 `paths:` 前置欄位，AI 讀到程式檔時由 Claude Code 自動載入，不是每個 session 常駐。它們只是寫程式的思考與風格細則，不擋任何事，守門開或關都一樣載入。

### 只在寫碼回合跑

- 判法 `wg_core.coding_turn`：這個使用者回合用工具改過程式檔（`wg_code_path.is_code_path`），或跑了判不出寫入目標的指令。
- 規則 [CODING_TURN_ONLY](release-rules.md#coding_turn_only)。使用者 prompt 的關鍵字不當開關。
- 本篇只在寫碼回合跑的：閱讀路徑、hook 計時的 run 帳。
- 記憶系統的退避偵測、退縮閘、收尾檢核，守門開時也改成只在寫碼回合跑（跨層表 #22）。
- `coding_guard.coding_turn_only=false` 退回每回合都跑。

### 擋或提醒

- 送法只看 [`hooks/wg_release_rules.py`](../hooks/wg_release_rules.py) 的 `RULE_MODE`。呼叫端一律經 `gate_mode(rule, v6)` 問。
- 守門關時 `gate_mode` 一律回「擋」。所以記憶系統的收尾閘在守門關時擋、守門開時只提醒（跨層表 #21）。
- 守門開時，寫碼守門照擋的只有三類（`RULE_CLASS` 標病形／宣告／紅測），其餘提醒：

| 類別 | 守門開時 | 例子 |
|---|---|---|
| 病形（含防繞） | 擋 | SmellGate、GateBypass |
| 宣告：改資料檔、改舊測試沒先宣告 | 擋 | DataFileAsk、OldTestDeclare |
| 紅測：紅測閘、寫碼查核 (a) 說修好要有綠收據 | 擋 | TestFailGate、ReconcileGate (a) |
| 其餘寫碼守門 | 提醒 | 寫碼查核 (d)、拐彎判斷、等值閘、收尾自清、Reload 建議、PickOne、問使用者附推薦 |
| 記憶系統的收尾閘 | 提醒 | 退縮歸屬、收割、同步、深度檢討（跨層表 #21） |
| 安全與權限邊界（不在範圍） | 擋 | 版控口令、隱私檔、驗證批次、svn 測試路徑、繞閘卡片拒寫、`readonly_paths` |

- `readonly_paths` 是部位表的設定：守門開時照擋；守門關時部位表整個不跑，不擋（跨層表 #36）。
- 表上沒登的規則名當「擋」。

提醒怎麼送：

- 一行：規則名＋現象＋做法（`remind_line`），並留帳。
- 不擋、不讓對話續跑。同一條規則、同一個對象、同一個 session 只提醒一次（`remind_due`）。
- 掛在前一個動作的工具結果上（PostToolUse），不掛 PreToolUse（[REMIND_ON_PRIOR_RESULT](release-rules.md#gate_mode_tableremind_on_prior_resultrule_mode)）。
- 收尾類的提醒掛在改程式檔那批的工具結果上；Stop 只留帳（[STOP_REMIND_LEDGER_ONLY](release-rules.md#stop_remind_ledger_only)），不續跑、不吃擋次、不開放行題。所以只改文件的回合連提醒都沒有。
- 本篇寫「擋滿第 N 次放行」「續跑一回合」的地方，只在那條規則照擋時成立。

細節 → [guards.md 擋或提醒（完整）](guards.md#擋或提醒完整)

### 減量原則

寫碼守門為了不拖慢寫程式，照這幾條做：

- **只在寫碼回合啟動**：見上面〈只在寫碼回合跑〉。
- **只擋三類，其餘提醒一次**：見上面〈擋或提醒〉。
- **同一件事只問一次**：提醒與擋訊息在同一 session 或回合只送一次全文，之後併成一行。
- **記帳交程式或背景免費模型**：收據號碼、收割候選由程式或內網模型做，不叫寫碼的 AI 做。
- **要判斷的事入口還在**：動資料檔與改舊測試的宣告、拐彎判斷、等值證法、同步交代仍由 AI 宣告理由。只拿掉重複與記帳。
- **用不到就不載**：守門的模組（連鎖斷路器、動資料檔、改舊測試、繞閘、擋滿放行、閱讀路徑、背景收割…）在 handler 頂端用 `lazy_module` 宣告（[`hooks/wg_lazy_re.py`](../hooks/wg_lazy_re.py)），第一次用到才真的載入。守門關時這些模組不載；守門開時，也只在那道閘真的要判時才載。
- **語言專屬工具只是側資料**：閱讀路徑只量 Python 與 C#；commit 病形樣式只認 Python、C# Unity 腳本與匿名函式。量出來的東西是給 AI 的參考材料。沒有工具的語言不擋，由 AI 自己讀碼判斷。
  - 目前的落差：其他語言在閱讀路徑結果裡只印一行「不支援（只算 Python 與 C#）」（[`hooks/wg_reading_path.py`](../hooks/wg_reading_path.py)），這行沒叫 AI 自己讀。原則跟輸出還沒對齊。
- **能退回的做成開關**：各開關見 [TECH/config.md](config.md) 的〈功能開關〉。

---

## 乙2 一路會遇到什麼

守門開時，照 AI 寫程式的先後順序，每個時刻系統會問什麼、擋什麼。

- **擋**＝工具呼叫被拒（deny）或收尾被打回（block），AI 補完才能繼續。
- **提醒**＝多送一行字，不擋。

```text
① 開場（SessionStart）          列未結追蹤項、公司層與週健檢狀態                  提醒
   ↓
② 收到需求（UserPromptSubmit）   注入記憶卡（寫碼回合瘦身）                         不擋
   ↓
③ 改檔當下（PreToolUse）         動資料檔、改舊測試要先寫宣告行                     擋
   ↓
④ 改完之後（PostToolUse）        記改了哪些檔；讀到 Depends 指的檔就召回那張卡      提醒
   ↓
⑤ 問使用者之前（AskUserQuestion）每題附推薦；問改法前先讀過題目點名的部位          提醒
   ↓
⑥ 跑測試                         哨兵行收成「收據」；紅了記紅測                     只記帳
   ↓
⑦ 宣告完成（Stop）               依序查紅測、寫碼查核、拐彎、等值、自清…            擋只紅測與 (a)；其餘提醒
   ↓
⑧ 交付                           收尾檢核報告送 HUD；點出最該修的一件進追蹤帳本     提醒
   ↓
⑨ commit 與合併                  口令、隱私檔、病形、繞閘                           擋
```

| 時刻 | 系統做什麼 | 擋不擋 | 見哪節 |
|---|---|---|---|
| ① 開場 | 列之前沒解的問題（追蹤帳本，跨層表 #29）與待檢討項 | 提醒 | [TECH §3.1](../TECH.md#31-settingsjson-十一個事件)、[TECH §8](../TECH.md#8-可觀測與自我維護) |
| ② 收到需求 | 注入記憶卡；寫碼回合瘦身（跨層表 #7） | 不擋 | [TECH §5](../TECH.md#5-檢索與注入每-prompt) |
| ③ 改檔當下 | 動資料檔、改舊測試要先宣告 | 擋 | [乙6](#乙6-其他寫碼守門) |
| ④ 改完之後 | 記帳、召回 Depends 卡、背景量閱讀路徑 | 提醒 | [乙7](#乙7-部位表與-depends-召回)、[乙3](#乙3-收尾閘序守門開時與收據) |
| ⑤ 問使用者之前 | 每題附推薦選項 | 提醒 | [乙6](#乙6-其他寫碼守門) |
| ⑥ 跑測試 | 收據與紅測記帳 | 只記帳 | [乙3 收據](#收據) |
| ⑦ 宣告完成 | 依序查紅測、寫碼查核等 | 擋只紅測與 (a) | [乙3](#乙3-收尾閘序守門開時與收據)、[乙4](#乙4-擋滿之後怎麼放行) |
| ⑧ 交付 | 收尾檢核報告、點出最該修的一件 | 提醒 | [TECH §7.2](../TECH.md#72-反退避anti-evasion)、[乙3](#乙3-收尾閘序守門開時與收據) PickOne |
| ⑨ commit 與合併 | 口令、隱私、病形、繞閘 | 擋 | [乙6](#乙6-其他寫碼守門)、[TECH §7.3](../TECH.md#73-commit-與驗證前的閘)、[TECH §13.4](../TECH.md#134-多-session-協作雙總控台與工作軌) |

每個時刻的完整內容 → [guards.md A7.0](guards.md#a70-寫程式時一路會遇到什麼總覽)

### 目前關著的閘

- 寫碼查核的 `reconcile_gate.block_letters` 設成 `["a", "d"]`（[`workflow/config.json`](../workflow/config.json)）。
  - (b)(c)(e) 照判，只印 stderr。
  - (d) 再照送法表是提醒，所以實際只有 (a) 擋。
  - 拿掉這個鍵，(b)(c)(e) 也照送法表判（守門開時是提醒）。
- 收尾檢核報告、卡片表態、svn 測試路徑閘的開關屬基本守門 → [TECH §7](../TECH.md#7-基本守門)。

---

## 乙3 收尾閘序守門開時與收據

這節回答：守門開時，AI 宣告完成的那一刻，系統依什麼順序查、各擋什麼、擋幾次。入口是 [`hooks/handlers/stop.py`](../hooks/handlers/stop.py) 的 `handle_stop`。守門關時的閘序 → [TECH §7.1](../TECH.md#71-收尾閘序守門關時)。

- 一開頭（任何閘之前）：
  - 把最後一句「順手看到最該修：…」段記進追蹤帳本（PickOne）。
  - 問一次連鎖斷路器（[乙8](#乙8-連鎖斷路器)）：中止中，這一回合其餘閘只記錄、不擋。
- 之後依序查，前者優先：

```text
斷路器
  → 紅測（TestFailGate，新版）
  → 寫碼查核（ReconcileGate）
  → 拐彎判斷（ReadingPath／TurnJudgment）
  → 等值與熱路徑（Equivalence）
  → 退縮歸屬                              ［記憶系統］
  → 收割、收割對帳                        ［記憶系統］
  → 收尾自清（Cleanup）
  → 收尾檢核（ScanReport／AEC-Pending）    ［記憶系統］
  → Reload 建議
  → 同步閘（SyncReminder）                ［記憶系統］
  → 卡片表態（AtomAudit）                 ［記憶系統］
  → 深度檢討（Deep Post-Mortem）          ［記憶系統］
  → PickOne
  → 底部同步擋                            ［記憶系統］
```

| 閘 | 擋什麼 | 守門開時 |
|---|---|---|
| TestFailGate（新版） | 本 session 有沒轉綠的失敗測試又宣告完成 | 擋 |
| ReconcileGate | 說修好沒有綠收據 (a)、改了程式沒有案例 (d)… | 只 (a) 擋；(d) 提醒；(b)(c)(e) 只印 stderr |
| ReadingPath／TurnJudgment | 函式拐彎超線，收尾沒寫判斷 | 提醒 |
| Equivalence | refactor／perf 缺等值證法或熱路徑答覆 | 提醒 |
| Cleanup | 自己建的工作樹與暫存沒清 | 提醒 |
| Reload 建議 | 叫人 Reload，但工具服務已載入最新 | 提醒 |
| PickOne | 交付時點出最該修的一件 | 提醒（收尾那批附問句，Stop 只留帳） |
| 驗收裁判 | 背景審查，下一則附結果 | 永不擋（[乙5](#乙5-驗收裁判)） |
| 迴歸提示 | 驗收 fail／high 真命中 | 每 session 一次 |
| 標［記憶系統］的閘 | 退縮、收割、同步、深度檢討… | 提醒；收尾檢核與卡片表態設定關著，不擋也不提醒 → [TECH §7.1](../TECH.md#71-收尾閘序守門關時)、跨層表 #21 |

### 擋次預算

下面的預算只在那條規則照擋時用得到。守門開時判成提醒的規則不吃預算。

- **紅測閘與寫碼查核**共用每個使用者回合一份 `reconcile_gate.max_blocks_per_turn`（2）。等值閘缺件也吃這份。
- **拐彎判斷**每個使用者回合最多擋一次。
- **共用預算** `stop_gate_max_blocks`（2）：守門開時每個使用者回合重算（跨層表 #26）。守門開時用到它的閘都是提醒，`RULE_MODE` 把哪一條改回擋才會吃。
- **擋滿只認使用者放行**（[乙4](#乙4-擋滿之後怎麼放行)）。沒人能回答（headless／SDK、子代理、裁判）擋滿就放行並留帳。
- **閘自己判定出錯**：同一個錯誤每個使用者回合擋一次，之後放行並留帳（[GATE_SELF_ERROR](release-rules.md#gate_self_error)）。
- **子代理與裁判子 session** 的 Stop 只跑寫碼查核（`stop._code_gate_no_ask`），不問使用者。

### 其他具名項目

- **ReadingPath**：改了程式檔那批跑完，背景量改到的碼的拐彎數與側面數據（Python、C#），收尾前附上。只在超線時提醒。
- **PickOne**：交付時點出這次最該修的一件，記進追蹤帳本，下個 session 開場列出。
- **擋訊息格式**：寫碼查核每條是 `✗ (<字母>) <規則名>：<一句現象>｜證據：<一行一證據>`（規則表 [乙9](#乙9-規則全表)）。
- **舊版紅測閘**：守門關時跑的那一版 → [TECH §7.1](../TECH.md#71-收尾閘序守門關時)。

### 收據

紅測閘與寫碼查核認的證據是「收據」，不是 AI 自己說跑過。

```text
跑測試（Bash／PowerShell）
   │  哨兵行（<名>_CHECK PASS／FAIL、<名> DONE k=v）＋完整指令＋exit code
   ▼
收據進 workflow/verify-ledger/<sid>.jsonl；紅了記紅測
   │  超過 10 分鐘的驗證背景跑，印完哨兵後自寫收據
   ▼
Stop 的紅測閘與寫碼查核拿收據對帳
   ├─ (a) 說修好：對得上改檔的 PASS，或改檔部位的量尺／合格自寫收據
   └─ (d) 補案例：本 session 改過的案例要覆蓋改過的程式檔
```

- (a) 是規則 [CLAIM_FIXED_NEEDS_PASS](release-rules.md#claim_fixed_needs_passclaim_measured_needs_doneclaim_tried_needs_exec)；(d) 是規則 [CASE_COVERS_CHANGE](release-rules.md#case_covers_change)，「case_for｜<程式檔>：<案例…>」宣告行也算。
- 部位量尺來自部位表（[乙7](#乙7-部位表與-depends-召回)）；哪些收據算數 → [guards.md 收據列](guards.md#收據收據列)。
- 收據不防偽造：不看指令形狀、不查指令裡寫的哨兵字樣。指令解析不了（heredoc、`$( )`…）只當一般證據。

**為什麼要收據**：「跑過了、綠的」是宣稱；收據是哨兵與指令的紀錄，對帳時兩邊對得上才算。

細節 → [guards.md A7.1](guards.md#a71-stop-閘序)

---

## 乙4 擋滿之後怎麼放行

這節回答：寫碼類查核閘擋滿次數後，AI 不能自己放行、也不能改寫措辭繞過，決定權交回使用者。用在紅測閘、寫碼查核、等值閘。程式在 [`hooks/wg_release.py`](../hooks/wg_release.py)。

```text
擋滿 → 記 pending_release → 擋訊息要 AI 用 AskUserQuestion 問【收尾放行確認】
  ├─ 使用者選「放行這一回合」或打字「放行」（在最後一次擋之後）→ 記 user_release（週健檢列紅）→ 放行
  ├─ 使用者選「繼續擋，先修好」→ 繼續擋
  └─ 使用者打字開新回合 → pending 失效、預算重給
沒人能回答（子代理、裁判、headless／SDK）→ 擋滿就放行並留帳
```

- **擋滿訊息**：固定格式，題目含【收尾放行確認】，選項固定兩個：「放行這一回合」「繼續擋，先修好」。
- **放行只認兩種**，都要在最後一次擋之後。
- **待放行只在同一個使用者回合有效**（[PENDING_SAME_USER_TURN](release-rules.md#pending_same_user_turnrelease_covers_shown_itemsnoninteractive_release_at_budget)）。
- **放行的是列過的那幾件**（[RELEASE_COVERS_SHOWN_ITEMS](release-rules.md#pending_same_user_turnrelease_covers_shown_itemsnoninteractive_release_at_budget)）。
- **沒人能回答**的情境照預算擋，擋滿放行並留帳（[NONINTERACTIVE_RELEASE_AT_BUDGET](release-rules.md#pending_same_user_turnrelease_covers_shown_itemsnoninteractive_release_at_budget)）。
- 問使用者附推薦（[乙6](#乙6-其他寫碼守門)）認得放行題：真有待放行紀錄時，放行題整題不查。

細節 → [guards.md A7.3](guards.md#a73-擋滿之後怎麼放行hookswg_releasepy)

---

## 乙5 驗收裁判

這節回答：另一個 AI 照任務專屬的驗收標準審查產出，而不是靠通用直覺（通用直覺審必然低精度）。

```text
① 規格工件 ──→ ② 影子裁判 ──→ ③ 背景審 ──→ ④ 迴歸提示
 plan 落驗收規格   完成宣稱觸發   Stop 不等、        fail/high 命中後
 acceptance-*.md   案卷＋verdict  下一則附一行        建議補測試／落 atom
```

- **整段歸守門開關**：守門關時，兩個觸發處（收尾宣稱完成、規格檔標 done）都不跑。
- **守門開時只記錄**：裁判在背景審，記 `workflow/acceptance-audit.jsonl`，結果下一則附一行。**一律不擋收尾**，也沒有改成硬閘的開關。
  - 為什麼不擋：擋收尾會讓「改 → 驗收 → 再改 → 再驗收」無限擴張。所以裁判只記錄，結果交人看。
- **後端鏈**（[`tools/codex-companion/judge_backend.py`](../tools/codex-companion/judge_backend.py) 決定用哪個）：
  - Codex（跨廠）：一律經 [`tools/codex-call.py`](../tools/codex-call.py) 叫 `codex exec`。這支是本系統叫 Codex 的唯一入口。叫不起來、逾時、沒回答都回失敗原因，不當成功。
  - → headless `claude -p --model sonnet`（同廠不同模型）。
  - → 都沒有就退 heuristics-only，開場揭露一次。
  - 不論哪個後端，結果都只當參考。
- **殺閘寫死在程式**（`promotion_stats()`）：fail ≥10 筆且精準度 <50% → 收掉。

**為什麼要案卷**：先給裁判任務專屬的驗收標準，再談能力。

細節 → [guards.md A7.4](guards.md#a74-驗收裁判ai-審查-ai-產出四段閉環)

---

## 乙6 其他寫碼守門

這節回答：[乙3](#乙3-收尾閘序守門開時與收據) 的收尾閘序以外，寫碼守門還掛在哪些時機。每道一行：名稱｜擋什麼｜擋還是提醒。其餘不看守門開關的閘 → [TECH §7.3～7.6](../TECH.md#7-基本守門)。

**改檔前**

- `DataFileAsk`｜改使用者既有的資料檔（json／yaml／md…）前要先寫一句宣告｜擋（宣告後放行）
- `OldTestDeclare`｜刪、改名、改斷言、加跳過標記等動到既有測試前要先宣告｜擋（宣告後放行）

**問使用者前**（AskUserQuestion／ExitPlanMode，[`hooks/wg_ask_gate.py`](../hooks/wg_ask_gate.py)，留帳 `Logs/guard-ask.jsonl`）

- [`ASK_NEEDS_RECOMMENDATION`](release-rules.md#ask_needs_recommendation)｜每一題要附推薦選項；【收尾放行確認】題在真有待放行紀錄時整題不查｜提醒
- [`ASK_OVERVIEW_BEFORE_DECISION`](release-rules.md#ask_overview_before_decision)｜問改法前還沒讀過題目點名的部位裡的檔｜提醒（併在同一則）

**commit 前**

- `SmellGate`｜這次要提交的程式碼新長出「病形」（匿名函式多層巢狀、函式巢狀 ≥4 層…）｜擋（`smell-ok:` 可放行）
- `GateBypass`｜病形閘擋過後，用 `restore --staged`／`reset`／`--no-verify` 等把被點名的檔排除｜擋（要宣告「不是繞閘｜理由」）

**為什麼這樣分**：能判斷的事交程式擋；需要判斷的事（該不該動資料檔、舊測試能不能改）改成「先宣告、事後被對帳」，宣告句本身就是留給健檢抽查的帳。

**宣告型守門的共同模式**：

- 宣告寫在同一則先發的不寫檔指令開頭的 `#` 註解。
- 同一使用者回合同一缺件擋滿 2 次，第 3 次放行並留帳（[GATE_DENY_CAP](release-rules.md#gate_deny_cap)）。
- 閘自己出錯＝這次不擋，stderr＋留帳（[GATE_SELF_ERROR](release-rules.md#gate_self_error)）。
- 各閘有 `guard.<名>.enabled` 開關與 `Logs/guard-*.jsonl` 留帳。

細節 → [guards.md A7.5](guards.md#a75-其他守門)

---

## 乙7 部位表與 Depends 召回

這節回答：其他守門要知道「這個檔屬於哪個部位、這個部位用什麼驗」；讀到某張卡指著的檔時，把那張卡召回來。部位表的讀檔帳、唯讀路徑檢查與讀它設定的閘都綁守門開關：守門關時不記、不擋（[OVERVIEW_HUB_UNDER_V6](release-rules.md#overview_hub_under_v6)；跨層表 #36）。

**核心概念**：

- **部位表**：`<專案根>/.claude/overview-map.md`，一列一個部位。欄位是路徑樣式、層、導讀卡、病灶文件、量尺、類別（code／knowledge）。新專案用 [`tools/overview-map-scaffold.py`](../tools/overview-map-scaffold.py) 掃出骨架。
- **導讀卡**欄：指向該部位的那張記憶卡（卡片格式見 [TECH §4.1](../TECH.md#41-atom-卡片格式)）。系統不主動送它，AI 要看就自己讀。
- **專案覆蓋**：`<專案根>/.claude/overview-hub.json` 只寫要改的鍵。合併順序：程式預設 < config < 公司根 < 專案根；未知鍵報錯。

**誰用部位表**：

- 收據的部位量尺：部位表「量尺」欄填的驗證指令，收據裡跑了這串就算這個部位驗過（[乙3 收據](#收據)）。
- 問改法前要讀過題目點名的部位（[乙6](#乙6-其他寫碼守門) ASK_OVERVIEW_BEFORE_DECISION）。
- 病形閘的病灶清單（[乙6](#乙6-其他寫碼守門) SmellGate）。
- `readonly_paths`：列了的路徑改檔前一律擋（[乙1](#擋或提醒)）。

**Depends 召回**：讀到某張卡 `Depends` 指著的檔，PostToolUse 附一行 `[Guardian:Depends]`，叫 AI 改它前先讀卡。同一張卡一個 session 只提一次（[`hooks/wg_depends.py`](../hooks/wg_depends.py)）。守門關時沒有這一行（跨層表 #35）。

細節 → [guards.md A7.6](guards.md#a76-寫碼守門部位導讀卡overviewhub)

---

## 乙8 連鎖斷路器

這節回答：閘擋了 AI 修、修了又被擋，一路修下去會偏離原本要做的事；連成一串時停下來交使用者決定。判定在 [`hooks/wg_chain.py`](../hooks/wg_chain.py)，帳與快照在 [`lib/chain_store.py`](../lib/chain_store.py)。

```text
閘擋下／記欠
  → AI 看過擋訊息後動手（改檔、重跑、寫卡、重交報告）
  → 又被任一道閘擋下／記欠 → 記一條邊（帳 Logs/chain-<session>.jsonl）
        ↓
  同一道閘擋同一個對象，這一段第 2 次（max_same_gate），且兩次之間有改到檔、不是原封不動的同一個呼叫
        否 → 不警報，照常擋（深度只記、預設不警報）
        是 → 警報 CHAIN_ALARM_SAME_GATE
        ↓
  中止：這一回合其餘閘只記錄、不擋、不記欠
        ↓
  能互動的 session：停手（只放行讀與 AskUserQuestion）→ 收尾送連鎖過程表 → 問三選一
      ├─ 還原連鎖改動 → 把這一段第一次改之前存的快照寫回，連鎖中新建的檔刪掉
      ├─ 信任後續 AI 審查，繼續 → 開新的一段，次數與深度歸零
      └─ 放行這一回合 → 其餘閘照舊只記錄
  沒人能答（headless／SDK、子代理、裁判）：不問不停手，收尾要 AI 把經過表寫進報告；會改使用者資料的閘照擋
```

- **開關**：守門開、`chain_breaker.enabled` 為 true 才跑；設定裡沒寫這段＝不開。
- **判什麼算連鎖**：原樣重試、只改寫回覆就又撞同一道閘、沒改到檔的動作，都不算。
- **同一則回覆算同一步**（CHAIN_SAME_BATCH）：平行送出的工具呼叫沒看到擋訊息，不接成邊。
- **同閘照對象計數**（[CHAIN_SAME_GATE_PER_OBJECT](release-rules.md#chain_same_gate_per_object)）：擋不同對象各算各的第 1 次，不響。
- **斷路器不逼修補**：不要求任何宣告，只在警報後擋（收尾擋一次、停手中擋讀與問以外的工具呼叫）。
- **出錯照原閘行為**：斷路器自己出錯不中止、不只記錄、不停手，stderr 一行。沒有連鎖時各閘輸出一字不變。

**為什麼警報看同閘第 2 次**：要擋的是繞回原點的修不停。三道各管各的閘各擋一次不是連鎖，所以深度預設不警報。

細節 → [guards.md A7.12](guards.md#a712-連鎖斷路器hookswg_chainpy-判定libchain_storepy-帳與快照)

---

## 乙9 規則全表

這節回答：守門每次要決定「擋、提醒、放行、還欠」時，判斷理由散在各閘程式裡就無法稽核。所以每一種情境收成一條有名字的規則，寫在 [`hooks/wg_release_rules.py`](../hooks/wg_release_rules.py)。寫碼守門與基本守門共用同一份表。

- **一條規則一個名字**：名字會出現在擋訊息、留帳與程式註解裡。
- **一條規則一個會紅的案例**：放在 [`hooks/verify/verify_release_rules.py`](../hooks/verify/verify_release_rules.py)。端到端案例在各閘的 verify 檔；真 hook 入口探針是 [`hooks/verify/probe_release_rules.py`](../hooks/verify/probe_release_rules.py)。
- **呼叫端只蒐集事實**：state、transcript、git、檔案內容交給模組判，呼叫端不自己加例外。
- **不准用「整輪不擋」或「放寬」當解法**：要例外就新增一條有名字的規則。
- **送法**：同一條規則，守門開時照 `RULE_MODE` 擋或提醒，守門關時一律擋（[乙1](#擋或提醒)）。
- 測試或探針把假專案建在系統暫存目錄時，用環境變數 `WG_TEMP_RULES=off` 關掉兩條暫存規則。

```text
呼叫端蒐集事實（state、transcript、git、檔案內容）
  → wg_release_rules 的純函式規則判定（同樣輸入必得同樣結果）
  → Verdict(rule, owed, why, evidence)
      ├─ owed=是 → 擋訊息（帶規則名與缺哪件）／提醒（掛前一個工具結果）／留帳（Logs 的 guard-*.jsonl）
      └─ owed=否 → 放行（必要時仍留帳，說明是哪條規則放的）
```

規則分這幾大類（第一次讀只要知道有哪類，細節在全表）：

- **回合與檔案同一性**：「本回合」從哪裡算起、兩種寫法是不是同一個檔、寫碼檢查這回合要不要跑。
- **宣稱與提示詞**：宣稱詞、糾正詞、否決詞只是提示，語意交 AI 用一行宣告回答。
- **退避例外與紅測**：「追蹤」「不做」宣告怎麼放行；紅測的失敗項怎麼取、哪次綠能清哪次紅。
- **寫碼查核**：改了程式要有案例、說修好要有改完之後的收據，哪些改檔作廢哪些收據。
- **改檔事實判定**：檔被刪、搬走、改回原樣、只改註解時算不算改過。
- **擋次預算與放行**：每回合擋幾次、擋滿後怎麼問使用者、閘自己出錯時怎麼辦。
- **指令怎麼讀**：Bash／PowerShell 指令的寫入目標、刪除、唯讀、讀檔證據怎麼認。
- **提問**：問使用者要附推薦、問改法前先讀過題目點名的部位。
- **收尾加檢**：等值證法、拐彎判斷、收尾自清、收尾檢核報告的各段。
- **宣告類閘**：動使用者資料檔、改既有測試、繞閘要先宣告。
- **同步與暫存目錄**：什麼時候要求 push、暫存目錄與一次性腳本怎麼算。
- **注入與擋訊息版面**：記憶卡送多少、擋訊息怎麼排版。

**為什麼這樣設計**：判斷要可稽核、可被案例檢驗。固定規則只是判斷完之後的產物；需要判斷的事交 AI 宣告理由、事後對帳。

完整規則表 → [TECH/release-rules.md](release-rules.md)

---

## 乙10 代價

- 寫碼守門只在守門開、而且是寫碼回合時付代價。純問答、只改文件的回合，這一層幾乎不做事。
- 大頭不是 hook 程式本身，是 AI 收到提醒後多想、多寫的輸出。
- 守門關時也不是全免：settings.json 照掛守門專屬的事件與工具，hook 行程照起，讀完設定就退（跨層表 #1、#2）。
- 量過的是「hook 全關」對「全開（守門開）」，守門開對守門關沒有獨立量過。量測紀錄 → [`_AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/TECH-重整搬出-2026-10-30.md`](../_AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/TECH-重整搬出-2026-10-30.md)；完整報告在同目錄 `v6.0的代價-*.md`。
- 記憶系統本體的代價 → [TECH §11](../TECH.md#11-記憶系統的代價與怎麼量)。

---

## 乙11 hook 計時與快逾時降級

這節回答：hook 快跑到 Claude Code 給的時間上限時，系統怎麼自保。目前只在守門開時有：守門關時不計時、不降級、不代送，hook 逾時就被 Claude Code 直接取消（跨層表 #6）。

- **計時**（[`hooks/wg_hook_timing.py`](../hooks/wg_hook_timing.py)）：SessionStart、UserPromptSubmit、PreToolUse、PostToolUse、Stop 從行程建立起計時，段落之間打一個點。
- **上限**：settings.json 裡這個事件那支 hook 的 timeout；讀不到用 `hook_timing.fallback_limit_s`。
- **降級**：累計超過上限的 80%，就寫回 state、放行，後面的段落這次不跑。並寫 `Logs/guard-hook_timing.jsonl` 一筆 `kind=degraded`＋stderr 一行。
- **鬧鐘**：單一段落一路跑過上限時打不到點，所以起表時另排背景鬧鐘。到上限 95% 還沒結束，先寫一筆 `kind=overrun`；SessionStart、UserPromptSubmit 已備好的輸出由鬧鐘搶先代送。
- **只在寫碼回合記 run 帳**：非寫碼回合不寫 `kind=run`，但降級保護照跑。
- **看數字**：[`python tools/hook-timing.py`](../tools/hook-timing.py) 印各事件跑幾次、降級幾次、各段中位數與最長。

**為什麼要降級**：不降級的話，Claude Code 時間一到直接取消 hook，state 寫不回，什麼訊號都沒有。

**本機實測**（`Logs/guard-hook_timing.jsonl`）：16,874 筆計時紀錄裡，降級 32 次。PostToolUse 21、SessionStart 6、PreToolUse 4、UserPromptSubmit 1。數降級次數要數 `kind=degraded`；每次降級另有一筆帶 `degraded_at` 的 run，數 `degraded_at` 會算成兩倍。

細節 → [guards.md 超時降級](guards.md#超時降級)

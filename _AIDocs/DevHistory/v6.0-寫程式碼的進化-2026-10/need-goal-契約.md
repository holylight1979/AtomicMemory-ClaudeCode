# need_goal 契約（需求目標核心流程的骨架介面）

> **這份是什麼**：設計單《v6-B-需求目標核心流程-設計單》第九節要求「先凍結契約再並行」的那份契約。寫死目標檔格式、上鎖方式、樹與節點的狀態轉換、身份分法、序號與證據先後、`need_goal` 工具參數、續接單區塊格式、`hooks/wg_need_goal.py` 的函式介面，以及每個函式由誰實作、由哪支 hook 呼叫。
> **讀者**：track-b2（實作骨架與 4.1、4.2、4.5）、track-bkp（實作 4.3、4.4、軌五）、總控台、Codex。
> **依據**：設計單第二～五節、第九節、附錄 A～C；原設計者對第十節的定案（①A：reconcile 由 need_goal 交、回合結束查核併進寫碼查核閘、收尾檢核不加欄；②A：骨架與 4.1／4.2／4.5 全做）。
> **凍結規則**：本檔列出的檔名、欄位名、列舉值、函式簽名不再改；要改先告訴總控台，並同時通知另一軌。實作細節（訊息措辭、內部輔助函式）不在凍結範圍。

## 0. 分工

| 誰 | 擁有的檔 | 實作什麼 |
|---|---|---|
| track-b2 | `hooks/wg_need_goal.py`、`hooks/verify/verify_need_goal.py`、`tools/workflow-guardian-mcp/lib/need-goal.js`、`mcp.js`、`lib/_MAP.md`、`verify/smoke_mcp_stdio.js`、`lib/hub_config.py`（need_goal 段）、`lib/overview_hub.py`（第四行解析）、`hooks/wg_overview.py`（第四行核對、導讀卡附樹、目標改變清定位）、`hooks/wg_verify_ledger.py`（`reconcile_cfg` 的 code_exts 聯集、`is_code_file` 認 `#!`）、`hooks/handlers/post_tool_use.py`（need_goal 分支、蓋改檔與收據、讀到續接單匯入、收尾檢核附樹）、`hooks/handlers/user_prompt_submit.py`（4.1 呼叫點）、`hooks/handlers/pre_tool_use.py`（4.2 第一層、commit 前）、`hooks/handlers/stop.py`（4.5 併進寫碼查核閘）、`hooks/codex_companion.py`（驗收審查拿原話與樹）、`tools/workflow-guardian-mcp/lib/aec-hud-html.js`（HUD「目標對照」一塊）、`settings.json`（PostToolUse matcher 加 need_goal）、`.gitignore` | 第八節標「b2」的函式全部 |
| track-bkp | 新檔 `hooks/wg_need_goal_points.py`、`hooks/handlers/session_start.py`、`post_compact.py`、`post_tool_batch.py`、`session_end.py`、`hooks/wg_handoff.py`、`skills/handoff/SKILL.md`、`skills/continue/SKILL.md`；`pre_tool_use.py` 的提問分支（4.4）；`user_prompt_submit.py` 的糾正呼叫點（4.3）；`wg_overview.on_read` 的讀入範圍呼叫點（4.3）；`settings.json` PreToolUse matcher 加 `AskUserQuestion|ExitPlanMode`（依附錄 D(1) 實測結果） | 第八節標「bkp」的函式，全部放在 `hooks/wg_need_goal_points.py`，只透過第八節的公開函式讀寫目標檔 |

- 為什麼 bkp 的函式不放進 `wg_need_goal.py`：兩軌同時改同一檔會在檔尾互撞；設計單第九節要求擁有的檔互不重疊。函式名照附錄 B，只是模組換成 `wg_need_goal_points`。
- 兩軌都要改 `pre_tool_use.py`、`user_prompt_submit.py`、`wg_overview.py`：b2 只動第九節列的呼叫點，bkp 只動它自己的呼叫點；交付前各自 merge main 解衝突。

## 1. 目標檔：位置、上鎖、損毀

- 位置：`<資料根>/workflow/need-goal/<session_id>.json`（資料根＝`wg_core.WORKFLOW_DIR` 的上一層，吃 `WG_CLAUDE_DIR`）。`.gitignore` 收 `workflow/need-goal/`。pytest 裡（`PYTEST_CURRENT_TEST`）而測試沒把 `WORKFLOW_DIR` 導走時，改寫到系統暫存目錄 `wg-test-need-goal/`（同 `wg_core.logs_dir` 的作法），跑真 hook 入口的既有測試不會把假 session 的目標檔寫進資料根。
- 鎖：同目錄 `<session_id>.lock`。Windows 用 `msvcrt.locking(LK_NBLCK, 1)`，其他平台用 `fcntl.flock(LOCK_EX)`。
- **每一次修改都是一整段**：取鎖 → 讀 → 改 → 寫暫存檔 `<session_id>.<pid>.<8 碼亂數>.tmp` → `os.replace` 換檔 → 放鎖。只能透過 `update_locked(sid, fn)` 改；任何人不准自己開檔寫。
- 鎖等待上限 5 秒；拿不到 → 丟 `NeedGoalLockTimeout`，**不降級成無鎖寫**（無鎖寫會掉節點）。呼叫端照第九節處理：會擋的閘一律擋，記錄類 stderr＋守門紀錄。
- 讀：`load(sid)` 不取鎖（換檔是原子的，讀到的一定是某一次完整寫入）；Windows 換檔瞬間的 `PermissionError` 重試 10 次、每次 20 ms。檔不存在 → 回空骨架（第二節的頂層欄位，`trees` 為空），不建檔。
- 損毀（JSON 解析失敗）：`load` 丟 `NeedGoalCorrupt`；`update_locked` 把壞檔改名成 `<session_id>.corrupt-<時間>.json` 留證、stderr 一行、守門紀錄一筆，從空骨架重來，並在 doc 帶 `corrupt_backup` 讓呼叫端告訴 AI「目標檔損毀已備份，樹要重寫」。
- 新建目標檔時順手刪同目錄超過 30 天沒改的 `*.json` 與殘留 `*.tmp`（不刪 `.corrupt-*`）。**鎖檔一律不刪**：使用中的鎖檔不會更新時間，刪掉後別的行程重建新檔，兩邊各鎖各的（非 Windows 的檔案鎖綁在檔案實體上），整段上鎖就失效。

## 2. 目標檔格式

列舉值一律存英文，顯示時換中文（6.3 對照表）。

### 2.1 頂層

| 欄位 | 型別 | 說明 |
|---|---|---|
| `version` | int | 固定 1 |
| `session_id` | str | 主 session 的 sid |
| `seq` | int | 這個檔自己的序號，所有事件在鎖內從這裡拿號（第五節） |
| `next_tree` | int | 下一棵樹的號碼，從 1 起 |
| `active` | str／null | 目前的樹編號（`T3`）；還沒寫過樹是 null |
| `cwd` | str | 最近一次 `apply_op` 帶進來的 cwd（相對路徑證據用它解析） |
| `user_msgs` | int | 這個 session 收過幾則使用者本人打的訊息 |
| `said_log` | list | 最近 5 則使用者原話 `{seq, turn, text, attached}`；`attached=false` 是還沒歸進任何樹的（開新樹時搬進去） |
| `hint_sent` | dict | 4.1 提醒送過的紀錄 `{"first": bool, "after": [樹編號…]}` |
| `trees` | dict | 樹編號 → 樹（2.2） |
| `receipts` | list | 收據蓋號 `{seq, receipt_seq, key, turn, at, cmd, verdicts, exit}`，最多 300 筆，`seq` 就是 AI 引用的 `R<seq>` |
| `imports` | list | 匯入過的續接單 `{path, sha, at, trees}`（同一份同內容不重複匯入） |
| `receipts_seen` | list | 因上限被丟掉的收據識別 `<key>|<receipt_seq>|<at>`，最多 1000 筆：工作暫存裡還留著的同一筆不會被重新蓋成新號 |

### 2.2 樹

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | str | `T<n>` |
| `status` | enum | `doing`（進行中）／`reconciled`（已對照）／`closed`（結束） |
| `kind` | enum | `knowledge`（記憶知識類，預設）／`code`（寫碼類）；改過程式檔就升 `code`，不降回 |
| `goal_rev` | int | 目標版本，從 1 起 |
| `created_turn`、`created_seq` | int | 開樹的回合與序號 |
| `user_said` | list | `{seq, turn, text, prior?}`；首則上限 4000 字，其餘每則 1000 字，最多 20 則（保留第一則＋最新 19 則）；`prior=true` 是從續接單匯入的 |
| `peer_said` | list | `{seq, turn, from, text}`；每則 1000 字，最多 20 則；不當權威 |
| `links` | dict | `{"parts": {"<root>|<部位>": {"node": "T2.1", "seq": n}}}`；鍵就是 `state["overview_hub"]` 的鍵 |
| `edits` | list | `{seq, turn, path, node, agent_id, code, owed, cleared_seq?}`；同一檔同一節點還欠著對照時併成一筆（序號更新）；超過 300 筆只丟最舊的已清紀錄，owed 的一筆都不丟 |
| `node_last_edit` | dict | 節點編號 → `{seq, path}`：掛在這個節點的最後一次程式改動；證據先後只讀這裡（不受 edits 截短影響） |
| `last_reconcile` | dict／null | `{seq, turn, goal_rev, turns?}`：最近一次被收下的完整對照 |
| `goal_changed` | dict／null | `{seq, turn}`：最近一次目標改變（開樹、改樹根、增減節點、改節點文字或清楚度、匯入） |
| `imported_from` | dict／null | `{session, tree, path, map: {舊編號: 新編號}}` |
| `checkpoints` | list | `{seq, turn, point, node}`，最多 200 筆；`point` 見下 |
| `nodes` | dict | 節點編號 → 節點（2.3） |

`checkpoints.point` 的值：b2 用 `set`、`add`、`update`、`reconcile`、`locate`、`gate_f1`、`gate_f2`、`commit`；bkp 用 `scope`、`correction`、`ask`。bkp 需要自己的欄位時只能新增鍵（不改上面任何鍵的意義），並寫進本檔第十二節。

### 2.3 節點

| 欄位 | 型別 | 說明 |
|---|---|---|
| `parent` | str／null | 樹根是 null |
| `text` | str | 目標文字（LLM 寫） |
| `origin` | enum | `user`（使用者說的）／`inferred`（推出來的）／`grown`（工作中長出的）；樹根固定 `user` |
| `clarity` | enum | `clear`（明確）／`open`（待展開） |
| `status` | enum | `todo`（未開始）／`doing`（進行中）／`done`（達成）／`partial`（部分）／`none`（沒有）／`dropped`（放棄）；樹根開樹時是 `doing`，其餘新節點 `todo` |
| `history` | list | `{seq, turn, what, why}`；`what` ∈ `create`、`text`、`status`、`clarity`、`reconcile`、`import` |
| `evidence` | list | `{kind, ref, level, covers, seq, prior?}`（第五節） |
| `followup` | str | 部分／沒有時接下來要追什麼 |
| `note` | str | 完整對照時的附註（放棄的理由寫這裡） |

節點編號：子節點是父編號加 `.k`，`k` 取現有子節點最大號加一；節點永不刪除（放棄只是狀態），所以號碼不會重用。

## 3. 狀態轉換

| 事件 | 樹 | 節點 | 誰觸發 |
|---|---|---|---|
| `set`（沒有目前的樹，或 `new_task=true`） | 新樹 `doing`，成為 `active`；舊樹不動 | 樹根 `doing` | LLM |
| `set`（有目前的樹、不是換題）＝改寫樹根 | `doing`；`goal_rev+1` | 樹根文字換掉，history 記 why | LLM |
| `add` | `doing`；`goal_rev+1` | 新節點 `todo` | LLM |
| `update` 改 text 或 clarity | `doing`；`goal_rev+1` | 照改 | LLM |
| `update` 只改 status | 樹根改成 `dropped` → `closed`；樹是 `reconciled`／`closed` 而節點改成非終點 → `doing`；其他不動 | 照改 | LLM |
| `update`（任何一項被收下） | — | 清掉待對照（5.3） | LLM |
| （規則）`add` 帶 parent、`update`、`reconcile` 依節點編號找它所屬的樹 | 不限目前的樹、不切換 `active`；換題後舊樹欠的對照照樣交得進去；一次 `reconcile` 只對一棵樹 | — | — |
| `reconcile` 被收下 | 全部節點是 `done`／`dropped` → `closed`，否則 `reconciled`；記 `last_reconcile` | 照交的終點狀態；證據、followup、note 寫進節點；整棵樹的待對照全清 | LLM |
| 改了程式檔（`stamp_edit`，`code=true`） | `kind=code`；`reconciled`／`closed` → `doing` | 那筆改動 `owed=true` | 程式 |
| 改了非程式檔 | 不動 | 記進 edits，`owed=false` | 程式 |
| 從續接單匯入 | 新樹號，狀態沿用，`goal_rev=1`，`last_reconcile=null` | 狀態沿用；證據標 `prior=true` | 程式（自動）或 LLM（`set import_from`） |

「目標改變」＝開新樹、改寫樹根、`add`、`update` 改 text／clarity、匯入；發生時記 `goal_changed`，`apply_op` 回 `goal_changed=true`，post_tool_use 呼叫 `wg_overview.on_goal_changed` 清掉各部位的「已定位」（第九節）。

## 4. 身份

- 目標樹一律用**主 session 的 sid** 找。子代理的工具呼叫，hook 收到的 `session_id` 就是主 session 的（附錄 D(2) 實測成立），另帶 `agent_id`。任何函式收到 `<sid>#agent:<id>` 這種收據鍵，先切掉 `#agent:` 以後再找檔。
- 收據鍵沿用 `wg_verify_ledger`：主 session `<sid>`，子代理 `agent_receipt_key(sid, agent_id)`＝`<sid>#agent:<agent_id>`；蓋號時原樣記在 `receipts[].key`。
- 改檔的 `agent_id` 只標明是誰改的；子代理改的檔照樣進主 session 的樹、照樣欠對照，由主 session 對照。
- 子代理（SubagentStop）與裁判子 session（`CLAUDE_COMPANION_JUDGE=1`）**不跑**目標對照：`stop._code_gate_to_the_end` 不呼叫 `goal_gate_reason`；裁判的 PostToolUse 不呼叫任何 need_goal 函式。
- 使用者原話：只收 `harness_text.user_typed_text(prompt)` 非空的那一則（背景通知、子代理完成通知、跨 session 訊息清理後是空的）。跨 session 訊息另外解析 `<cross-session-message … from-name="…">` 的發送者與正文，記進 `peer_said`，不當權威。

## 5. 序號、待對照、證據先後

### 5.1 序號
- 一律用目標檔自己的 `seq`：每次 `update_locked` 裡發生的事件（開樹、增改節點、對照、蓋改檔、蓋收據、記原話）都 `seq += 1` 拿一個號。工作暫存裡的 `event_seq` 跟別的 hook 共用、沒有整段上鎖，不拿來比。
- 收據的 `receipt_seq` 是工作暫存那筆收據的 `seq`，只用來對到帳本與判斷「蓋過了沒」，不拿來比先後。

### 5.2 改檔掛哪個節點
- 部位表上的檔：`links.parts[<部位鍵>]` 指到的節點（定位第四行核對通過時寫入）。
- 沒有部位表、表上沒列、或那個部位還沒交第四行：樹根。

### 5.3 待對照（對照義務，4.5 第一層）
- 程式檔改動 `owed=true`。
- `update` 的某一項 id 是 X → 清掉 `node == X` 或 X 在 `node` 底下（X 以 `node + "."` 開頭）的 owed 改動，記 `cleared_seq`。
- `reconcile` 被收下 → 整棵樹的 owed 全清。
- 回合結束時**所有樹**還有 owed → (f1)；不看措辭、每次 Stop 都查（換題不卡開新樹，但舊樹欠的對照照樣要交一句）。

### 5.4 證據
- `kind`：`receipt`（收據）／`case`（驗證案例檔）／`file`（檔:行）／`atom`（卡名）。
- `level`：`measured`（實測）／`read`（讀碼）／`inferred`（推論）。
- `ref`：receipt 寫 `R<seq>`（或純數字），查 `receipts[].seq`；case／file 寫路徑，可帶 `:行` 或 `:行-行`，相對路徑以 `cwd` 解析，查磁碟存在；atom 寫卡名，查全域層（`wg_atoms.resolve_atom_path`）與 `cwd` 所在專案的 `.claude/memory/**/<名>.md`。
- `covers`：這筆證據支持哪幾個節點，省略＝只支持它所在的那個節點；每個都要是這棵樹的節點。
- 組合規則（程式只核對組合，不判內容）：`measured` ⇔ `receipt`（實測只能配收據，收據只能標實測）；case／file／atom 只能 `read` 或 `inferred`。
- 先後：一筆 receipt 證據的收據 `seq` 必須大於它 `covers` 每個節點掛的程式改動裡最大的 `seq`（讀 `node_last_edit`）；「節點掛的改動」＝掛在它本身、它的子孫，以及它的祖先（沒歸屬到更細節點的改動，例如沒有部位表的檔都掛樹根）。不因改了旁支的另一塊而整樹重驗。
- 收據超過 300 筆時只丟最舊、沒被任何節點證據引用的；丟掉的識別記進 `receipts_seen`。
- 匯入的證據 `prior=true`：只供閱讀，不計入 5.5 第 4～6 條。

### 5.5 完整對照的七條（4.5 第二層；`reconcile` 收件時與交付邊界時用同一支判定）
1. 這棵樹有 `last_reconcile`。
2. `last_reconcile.goal_rev == goal_rev`。
3. 每個狀態不是 `dropped` 的節點都在對照裡，而且現在的狀態是終點（`done`／`partial`／`none`／`dropped`）。
4. `done`、`partial` 至少一筆非 prior 證據；每筆指標都存在。
5. 先後：5.4 的規則。
6. `done` 不能只有 `inferred`（推論最多標部分）；`measured` ⇔ `receipt`。
7. `partial`、`none` 的 `followup` 非空；`dropped` 的 `note` 非空。

收件時 3～7 不過 → 整批拒收、一項都不套用，回每一條拒收理由。交付邊界時 1～7 對**現在的**樹重新判一次（指標可能已經不在、之後可能又改了檔或改了節點狀態）。

## 6. `need_goal` 工具

### 6.1 MCP 定義（`tools/workflow-guardian-mcp/lib/need-goal.js` 驗參、`mcp.js` 登記；不讀寫任何檔、不配編號）

| 參數 | 型別 | 用於 | 說明 |
|---|---|---|---|
| `action` | enum `set｜add｜update｜reconcile｜read` | 全部 | 必填 |
| `goal` | str | set | 一句、使用者的語言、只寫目標不寫手段；`import_from` 沒給時必填 |
| `new_task` | bool | set | 換題開新樹 |
| `why` | str | set | 改寫樹根時必填（js 只驗型別，Python 驗必填） |
| `import_from` | str | set | 續接單路徑 |
| `parent` | str | add | 掛在哪個節點，省略＝樹根 |
| `items` | array | add／update／reconcile | add：`{text 必填, clarity?, origin?}`；update：`{id 必填, text?, status?, clarity?, why 必填}`，text／status／clarity 至少一項；reconcile：`{id 必填, status 必填（done｜partial｜none｜dropped）, evidence?: [{kind, ref, level, covers?}], followup?, note?}` |
| `turns` | int ≥ 0 | reconcile | 拐了幾個彎（C-G11 預留） |
| `form` | enum `full｜compact｜handoff` | read | 預設 full；handoff 回續接單區塊（給 /handoff 手寫續接單貼上） |

js 拒收（`isError`）的呼叫，Python 不套用（post_tool_use 看到 error 回應就跳過）。js 收下回一行 `[NeedGoal] <action> 已收到`。

### 6.2 Python 端（post_tool_use 的 need_goal 分支 → `apply_op`）
- 再驗一次 js 那些規則（MIRROR：同一組列舉值），再驗只有 Python 判得了的：節點存在、目前有沒有樹、why 必填、5.5 的 3～7。
- 收下 → 套用、配編號、記 history 與 checkpoints、寫守門紀錄；`reconcile` 收下時把 `partial`／`none` 的 followup 寫進追蹤帳本 `workflow/tracking/<slug>.jsonl`（`wg_harvest.tracking_entries`＋`append_tracking`，一行一項「需求目標 T2.3（部分）：…」）。
- 回給 AI 的提示（PostToolUse additionalContext）：更新後的整棵樹（`render(tree, "full")`）＋被拒收的每一項與原因。

### 6.3 顯示用中文

| 英文 | 中文 |
|---|---|
| doing／reconciled／closed（樹） | 進行中／已對照／結束 |
| todo／doing／done／partial／none／dropped | 未開始／進行中／達成／部分／沒有／放棄 |
| clear／open | 明確／待展開 |
| user／inferred／grown | 使用者說的／推出來的／工作中長出的 |
| code／knowledge | 寫碼類／記憶知識類 |
| measured／read／inferred | 實測／讀碼／推論 |

## 7. 續接單區塊

`handoff_block(sid)` 產生、`import_handoff` 讀回。只帶狀態不是 `closed` 的樹。格式：

````
## 【需求目標樹】

（need_goal 產生；下個 session 讀到這份續接單會自動匯入。使用者原話是權威，樹是上一個 session 的解讀。）

### T2：<樹根>（進行中｜寫碼類｜待對照的改動 2）
- 使用者原話（權威）：
  - 第 5 回合：「…」
- 同伴轉述（不是使用者說的）：
  - claude-9f：「…」
- 節點：
  - T2 [進行中｜明確｜使用者說的] …；最近一次為什麼：…
    - T2.1 [達成｜明確｜推出來的] …；證據：實測 R12 `pytest …`
    - T2.2 [未開始｜待展開｜工作中長出的] 方向：…（未解問題）
- 未完事項：T2.3（部分）→ …

<!-- need-goal:begin v1 -->
```json
{"version": 1, "session_id": "<舊 sid>", "exported_at": "<ISO>", "active": "T2", "trees": [<樹，欄位同第二節，edits／links／checkpoints 不帶>]}
```
<!-- need-goal:end -->
````

- 人讀段照交接品質卡的寫法：每個節點帶最近一次「為什麼」、證據級直接標出、待展開的節點就是未解問題。
- 匯入只讀 `need-goal:begin`／`need-goal:end` 之間的 JSON（有多塊取最後一塊）；人讀段不解析。
- 匯入：每棵樹配新樹號，節點號整段換前綴（`T2.1` → `T5.1`），對照表寫進 `imported_from.map`；`user_said` 與證據標 `prior=true`；`edits`、`links`、`last_reconcile` 清空；`goal_rev=1`；history 留每個節點最後一筆並記一筆 `import`。匯出時的 `active` 對應的新樹成為 `active`。
- 同一路徑、同內容雜湊（`imports[].sha`）已匯入過 → 不再匯入，回「已匯入過（T5）」。
- 區塊的 `session_id` 等於目前的主 sid（本 session 自己匯出的，例如壓縮前寫的自動續接單）→ 不匯入（回 `own=True`）；post_tool_use 讀到這種續接單也不送任何提示。

## 8. `wg_need_goal` 函式介面（凍結）

`hooks/wg_need_goal.py`（b2 實作）：

| 函式 | 回傳 | 誰呼叫 | 做什麼 |
|---|---|---|---|
| `goal_path(sid)` | Path | 全部 | 目標檔路徑（先切掉 `#agent:`） |
| `load(sid)` | dict | 全部 | 不取鎖讀；不存在回空骨架；壞了丟 `NeedGoalCorrupt` |
| `update_locked(sid, fn)` | fn 的回傳 | 全部 | 整段上鎖套用 `fn(doc)`；`fn` 就地改 doc；鎖拿不到丟 `NeedGoalLockTimeout` |
| `next_seq(doc)` | int | 全部（只能在 `fn` 裡用） | 拿號 |
| `add_checkpoint(doc, tree, turn, point, node)` | None | 全部（只能在 `fn` 裡用） | 記一筆關鍵點紀錄，滿 200 丟最舊 |
| `handoff_session_of(text)` | str／None | b2：post_tool_use | 續接單最後一塊 need-goal 區塊是哪個 session 匯出的 |
| `active_tree(doc)` | dict／None | 全部 | 目前的樹 |
| `tree_of(doc, node_id)` | dict／None | 全部 | 節點編號所屬的樹（不限目前的樹） |
| `cfg_of(config, root=None)` | dict | 全部 | 合併後的 `need_goal` 設定（第十節） |
| `cfg_for_cwd(config, cwd)` | dict | 全部 | cwd 所在專案的設定（專案層覆蓋檔也算）；(f1)(f2)、commit 前用目標檔記的 cwd |
| `apply_op(sid, turn, tool_input, cwd="")` | dict `{ok, action, tree, rejected:[str], text, goal_changed}` | b2：post_tool_use | 套用五個動作 |
| `render(tree, form, chars=None, doc=None)` | str | 全部 | `header`（一行）／`compact`（一行一節點，chars 上限，預設設定的 `render_chars`）／`full`（含原話、轉述、證據、待對照、最近收據，要列收據時傳 doc） |
| `node_ref(tree, text)` | str／None | b2：wg_overview；bkp：on_ask | 文字裡第一個 `T\d+(\.\d+)*` 且是這棵樹、狀態不是放棄的節點 |
| `is_code_path(path, config)` | bool | 全部 | 部位類別是 knowledge → False；否則 `is_code_file(path, reconcile_cfg(config)["code_exts"])`（沒副檔名看第一行 `#!`）。部位類別真源是 `overview_hub.path_kind`（track-know） |
| `edit_gate(sid, path, config)` | str／None | b2：pre_tool_use | 4.2 第一層：回擋的理由或 None |
| `goal_for_edit(sid, path, config)` | dict／None | b2：wg_overview.on_edit | 這次改檔要不要第四行：啟用、是程式檔、有目前的樹 → 回那棵樹 |
| `link_part(sid, hub_key, node_id, turn)` | None | b2：wg_overview.on_edit | 記「部位 → 節點」與一筆 `locate` checkpoint |
| `stamp_edit(sid, path, agent_id, turn, config)` | None | b2：post_tool_use | 蓋改檔號；程式檔記待對照、樹升寫碼類、已對照或結束的樹退回進行中；沒有樹不記 |
| `stamp_receipts(sid, state, turn)` | int（蓋了幾筆） | b2：post_tool_use | 把工作暫存裡還沒蓋號的收據（主 session 與子代理）蓋進目標檔 |
| `on_prompt(sid, prompt, turn, config)` | str／None | b2：user_prompt_submit | 4.1：分使用者原話／同伴轉述／系統通知，記進樹，回要送的那一行 |
| `goal_gate_reason(sid, triggered, config)` | str／None | b2：stop._verify_gates | (f1) 每次都判；(f2) 只在 `triggered`（這則宣告完成、或擋滿待查的原宣稱、或本回合交了收尾檢核）時判 |
| `commit_gate(sid, config)` | str／None | b2：pre_tool_use（commit 指令） | commit 前：(f1)＋目前的寫碼類樹的 (f2)。(f2) 的對象＝目前的樹 `kind=code`（含從續接單匯入、這個 session 還沒改過程式的寫碼類樹：前一個 session 的證據不算數） |
| `snapshot_for_report(sid, kinds=("code",))` | dict／None | b2：post_tool_use（收尾檢核）、codex_companion | 原話摘要＋目標樹＋對照結果；目前的樹類別不在 kinds 回 None |
| `review_material(sid)` | str | b2：codex_companion | 「使用者原話（權威）／同伴轉述／目標樹（AI 的解讀）」三段分開標示的純文字；沒有樹回空字串 |
| `handoff_block(sid)` | str | bkp：wg_handoff；b2：read form=handoff | 第七節格式；沒有未結束的樹回空字串 |
| `import_handoff(sid, text, path, turn)` | dict `{imported:[新樹號], map, text, skipped}` | b2：post_tool_use、apply_op（set import_from） | 第七節 |
| `recovery_blob(sid, limit)` | str | bkp：post_compact、post_tool_batch | 壓縮後獨立重送：【需求目標樹】＋目前的樹 compact＋其他未結束樹的 header＋原話首則與最新一則，總長 ≤ limit；沒有樹回空字串 |

`hooks/wg_need_goal_points.py`（bkp 實作）：

| 函式 | 誰呼叫 | 做什麼 |
|---|---|---|
| `on_correction(sid, hits)` | user_prompt_submit（糾正偵測命中處） | 4.3 糾正提示 |
| `scope_growth_line(sid, part_label, cfg)` | wg_overview.on_read | 4.3 讀入範圍提示（自己管「每棵樹每部位一次」） |
| `on_ask(sid, tool_name, tool_input, state)` | pre_tool_use（AskUserQuestion／ExitPlanMode） | 4.4；回（擋的理由或 None、提示或 None） |
| `silent_unreconciled(sid)` | session_end | 知識類有樹沒對照、寫碼類一直沒交付 → 守門紀錄 |

例外類別 `NeedGoalLockTimeout`、`NeedGoalCorrupt` 定義在 `wg_need_goal`。

## 9. 接點

| hook | 位置 | 呼叫 | 失敗時 |
|---|---|---|---|
| UserPromptSubmit | `handle_user_prompt_submit`：`classify_intent` 之後、OverviewHub `on_prompt` 之前；`turn`＝`state["turn_seq"]+1`（這則收尾才 +1） | `on_prompt` | stderr＋除錯紀錄，不送 |
| PreToolUse | `handle_pre_tool_use` 的 OverviewHub 迴圈裡、逐寫入目標呼叫 `on_edit` 之前 | `edit_gate`（`UNKNOWN:` 目標交給 OverviewHub） | 判不了（鎖、損毀）→ 擋 |
| PreToolUse | commit 指令（`_git_commit_segments`／`_svn_segments` 命中 commit／ci） | `commit_gate` → deny | 判不了 → 擋 |
| PreToolUse → `wg_overview.on_edit` | 找到定位三行之後、`_layer_mismatch` 旁 | `goal_for_edit`、`node_ref`、`link_part` | 判不了 → 擋（OverviewHub 原本的環境異常路徑） |
| PostToolUse | need_goal 分支（`tool_name` 結尾 `need_goal`，非 error 回應） | `apply_op`；`goal_changed` → `wg_overview.on_goal_changed(state, transcript_path, turn)` | 鎖拿不到 → 回 AI「沒寫進去，請重呼叫」 |
| PostToolUse | Edit／Write／NotebookEdit／MultiEdit 的 file_path；Bash／PowerShell 的寫入目標（非 UNKNOWN、非暫存檔） | `stamp_edit` | stderr＋守門紀錄 |
| PostToolUse | 每次（有新收據才動） | `stamp_receipts` | stderr＋守門紀錄 |
| PostToolUse | Read 的檔是 `_staging/next-phase*.md` 且含 `need-goal:begin` | 還沒有樹 → `import_handoff` 並送回樹；已有樹 → 一行「要接續請 need_goal(action=set, import_from=…)」 | stderr |
| PostToolUse | anti_evasion_report 分支、`_write_aec_report_file` 之前 | `report["need_goal"] = snapshot_for_report(sid)` | 不附 |
| Stop | `_verify_gates`（只有 `handle_stop` 傳 `goal=True`；子代理、裁判不傳） | `goal_gate_reason`，結果併進寫碼查核的 `reason`，`kind` 仍是 reconcile（同預算、同擋滿問使用者、同 pending） | 判定錯誤 → 一律擋（同寫碼查核） |
| codex_companion | 驗收審查組 ctx 的 `user_goal` | `review_material`（空 → 沿用原本第一則訊息） | 沿用原本 |

`wg_overview.on_goal_changed(state, transcript_path, turn)`（b2）：每個有 `located` 欄的部位紀錄 → `located=False`、拿掉 `goal_node`／`goal_tree`、`transcript_offset` 移到當下、記 `goal_reset_turn=turn`。之後只認這之後交的那一組四行。bkp 的「目標改變後導讀卡改用目標視角重送」可以看 `goal_reset_turn`。

定位第四行：`定位｜目標：<節點編號>（這一塊在目標裡的角色）`，寫在前例那行之後（同一組）。`lib/overview_hub.LOCATE_RE` 認 `目標` 這個鍵；`locate_values` 仍只要求三行，第四行由 `on_edit` 在 `goal_for_edit` 回樹時另外要求。照抄 `<節點編號>` 不算交。

## 10. 設定

`lib/hub_config.HUB_DEFAULTS["need_goal"]`，走 OverviewHub 同一套四層合併（根層預設 < `workflow/config.json` 的 `overview_hub.need_goal` < 公司層 < 專案層 `.claude/overview-hub.json`）：

| 鍵 | 預設 | 用途 |
|---|---|---|
| `enabled` | true | 整個流程的開關（B5 對照組用）；false 時所有 hook 端呼叫都直接返回 |
| `scope_growth_dirs` | 3 | 4.3 讀入範圍的頂層目錄門檻（bkp 用） |
| `render_chars` | 1200 | compact 的字數上限 |

寫碼類判準的副檔名清單：`workflow/config.json` 的 `reconcile_gate.code_exts` 改成與預設 40 種**聯集**（只能加不能減）；`exclude_globs` 不跟著改（track-e8 的鍵，使用者要能減）。

## 11. 守門紀錄

`Logs/guard-need_goal.jsonl`（`wg_core.append_guard_log("need_goal", …)`），每筆帶 `event`、`session_id`、`turn_seq`：
`op`（action、tree、rejected 數）、`edit_blocked`、`locate_blocked`、`prompt_hint`、`import`、`gate_f1`、`gate_f2`、`commit_blocked`、`lock_timeout`、`corrupt`、`stamp_error`。bkp 用 `scope`、`correction`、`ask_blocked`、`ask_hint`、`silent_unreconciled`。

## 12. 不在本契約

- 4.3、4.4、軌五的行為細節（bkp 依設計單做，只要守第二～九節）。bkp 新增的欄位寫在這一節。
- 第六節 C 項（C-G1／G4／G9／G11／G15）：接點已留：`last_reconcile.turns`（G11）、`goal_changed`（G1）、`snapshot_for_report`（G9 材料）、reconcile 收下的時點（G4 掃視點）。
- 第七節 B5 驗法。

### 12.1 track-b-hooks 新增（只加鍵，不改第二～九節任何鍵的意義）
- 樹 `points`（dict，只有 wg_need_goal_points 寫）：`scope_parts` [部位鍵]、`scope_dirs` {mark, dirs, sent}（mark＝節點 history 最大 seq，樹一更新就重算）、`scope_pending` [{kind: part｜dirs, label, prev}]、`scope_sent_turn` int｜null（一回合最多送一則）、`multi_hinted` [路徑]。匯出時會跟著出去，匯入時不帶。
- 讀入範圍由 `post_tool_use` 對 Read／Bash／PowerShell 呼叫 `wg_need_goal_points.scope_on_read` 計算，不看 OverviewHub 開關：跨頂層目錄照算，部位鍵只在 OverviewHub 開著、表上有列時才有；這個 session 還沒有目標檔就直接返回。
- `wg_overview.read_scope_keys(path, config) → (root, part_key, dir_key)`：專案根、部位鍵 `<根>|<部位>`、頂層目錄鍵 `<根>|<頂層目錄>`；不在任何專案裡全回 None。`wg_overview.on_read` 不再算讀入範圍。
- 目標檔頂層 `peer_offset`（int）：PostToolBatch 掃 transcript 找工作中途送到的同伴訊息（attachment `queued_command`）已掃到的位元組位置；第一次只記位置不回溯，只吃到最後一個完整行。只有 `peer_claim_lines` 寫。
- 目標檔頂層 `peer_scan_truncated` {at, turn, skipped}（一批新增段超過 `PEER_SCAN_CAP` 256KB，只讀最後一段，skipped＝跳過的位元組數）、`peer_scan_error` {at, turn, error}（讀不到 transcript 或同伴訊息行 JSON 解析失敗；不擋，另寫 stderr）。
- state 鍵：
  - `need_goal_batch`（bool）：scope_on_read 排了讀入範圍提示，由 PostToolBatch 送。
  - `need_goal_ask_blocks`（int）：PreToolUse 擋提問的累計次數（`note_ask_blocked` 加一），PostToolBatch 的提問審計遇到掛上節點的提問就歸零。
  - `need_goal_multi_checked` {路徑: 次數}。
  - `need_goal_asks` [tool_use_id 或 h:<輸入雜湊>]，最多 20 筆：PreToolUse 處理過的提問。
  - `need_goal_recovery_sent`（epoch 秒）：SessionStart(compact) 當場送過目標樹，300 秒內的 PostCompact 不再存。
  - `pending_reinjection_goal`（str）：PostCompact 存、PostToolBatch 送，排在 atom 內文後、部位綜觀前；綜觀的「主目標」改成指向它。
- `state["overview_hub"][部位].goal_view_turn`：目標視角重送過的那一次 goal_reset_turn。
- 守門紀錄另加事件：`multi_edit`、`ask_error`（PreToolUse 提問分支自己炸了：擋＋stderr，只放過含【收尾放行確認】而且本 session 真有擋滿待放行紀錄的題目）、`points_error`。
- 守門紀錄事件 `ask_audit` {tool, tool_use_id, tree, blocked, linked}：PostToolBatch 對這批每一次提問記一筆，blocked＝送出前被擋過幾次，linked＝最後掛上的節點（沒掛為 null）。
- 守門紀錄事件 `external_claim` {kind, source, tree}：收到外部主張（同伴訊息、審查結果、讀交付信或審查報告檔）時送「用目標視角重看」三問並記一筆。
- checkpoint 的 point 不新增值：外部主張沿用 `scope`（有樹才記）。
- 函式：on_correction(sid, hits, turn=None)、silent_unreconciled(sid, turn=None) 多一個可省略的 turn。另有只在 bkp 模組與它的呼叫點用的：scope_on_read、scope_dir_line、batch_due、batch_lines、asks_after、mark_asked、ask_key、note_ask_blocked、peer_claim_lines、peer_of_prompt、on_external_claim、goal_view_text、recovery_text、handoff_note、handoff_section、has_open_tree。
- 4.4 擋與事後兩種模式：settings.json 的 PreToolUse matcher 有掛 AskUserQuestion|ExitPlanMode＝擋；沒掛（或 PreToolUse 不觸發）＝PostToolBatch 從 tool_calls 找沒處理過的提問，事後記錄並提醒。附錄 D(1) 實測 PreToolUse 對這兩個工具都會觸發、tool_input 完整，預設用擋（matcher 已掛）；擋的理由附照做就能過的修法（建議節點、題目裡怎麼寫、不屬於任何節點先 need_goal add）。
- 回合號慣例：只有 UserPromptSubmit 當下用 `state["turn_seq"]+1`（turn_seq 在 UPS 最後才加一）；PreToolUse／PostToolUse／PostToolBatch／Stop 用 `state["turn_seq"]` 本身。

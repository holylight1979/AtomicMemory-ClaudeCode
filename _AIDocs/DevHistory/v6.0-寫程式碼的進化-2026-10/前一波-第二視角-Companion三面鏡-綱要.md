# 第二視角：Codex Companion 三面鏡（綱要，待拍板）

> 題目：讓 CC 在寫碼／讀碼時有「第三人稱看自己」的能力——綜觀視角、批判過度技術、抓瞎掰與飄移。
> 狀態：綱要；使用者尚未拍板起手。**未拍板前只可查證、禁止修改或實作；下一步是請使用者回答文末「待使用者拍板」六題。**專案層對應綱要：`c:\Projects\.claude\memory\_staging\next-phase-AI寫碼守門.md`（零件 E 上收到這裡）。

## 路徑錨點

- 本文所有相對路徑（`hooks/…`、`tools/codex-companion/…`、`workflow/config.json`、`rules/…`、`memory/…`）一律相對根層 repo `C:\Users\holylight\.claude\`。
- 專案層一律寫絕對路徑：SGI＝`c:\Projects\`，TSLG＝`C:\TSLG\`。
- 「C# 前濾 sidecar」尚未定義路徑與格式，只是 v2 想法，禁止據此實作。

## 主張

第三人稱的載體已存在：Codex Companion（另一個模型、獨立 context、看得到 tool trace）。缺的不是新機制，是它被問的問題：`TURN_AUDIT` 只問「有沒有做、有沒有證據」，不問「飄離目標沒、多做了什麼、陳述有沒有證據」。同模型自我批判與文字規則不夠：根層 [固] 的 feedback atom 本身就是「規則在、仍重犯」的紀錄。

## 盤點（已驗證）

| 視角 | 現有 | 缺口 |
|---|---|---|
| 綜觀 | IDENTITY「動手前預告」、plan_review（只在 ExitPlanMode 觸發） | 中途不校準；turn_audit 有 user_goal 但沒被要求判飄移 |
| 過度技術 | `rules/coding-style.md`、karpathy skill（被動）、ARCHITECTURE_REVIEW prompt 已寫但 `soft_gate.architecture_review=false`；`_ARCH_FILE_RE` 只匹配 bridge/provider… + .py/.ts/.js/.rs；SessionEnd over-engineering 指標只寫 stderr | 沒人看 diff；turn_audit 只拿 modified_files 清單，只有 acceptance_review 有 diff_digest |
| 瞎掰／飄移 | turn_audit 查「宣稱 vs trace」；wg_evasion 禁語；wg_friction 糾正計數 | 不查「陳述句有沒有證據」 |

盤點的「已驗證」範圍：本 session 實讀 `hooks/codex_companion.py`、`tools/codex-companion/{prompts,heuristics,audit,acceptance}.py`、`workflow/config.json` codex_companion 段、`hooks/handlers/pre_tool_use.py:784`、`session_end.py:233-243`。未驗證：Companion 開 architecture_review 後的實際誤報率（需跑才知道）。

## 做法（候選，由便宜到貴；全部未拍板）

| # | 做法 | 狀態 | 為什麼 |
|---|---|---|---|
| 1 | `workflow/config.json` 開 `soft_gate.architecture_review`；`_ARCH_FILE_RE` **不擴**到 .cs（SGI 有 125 個 Manager、577 個 Handler，檔名猜會吃光 audit 配額）；C# 的前濾改用專案計數結果，傳遞方式（sidecar 檔）v2 | 候選 | prompt 已寫好，開關一行；先量誤報率再決定留不留 |
| 2 | `tools/codex-companion/prompts.py` TURN_AUDIT 加三面鏡 category `goal_drift`／`overengineering`／`unsupported_claim`；餵 diff 摘要（重用 `acceptance.collect_diff_digest`）；corrective_prompt 固定第三人稱句型「審核者看到：…；回答前先確認：…」；每行必帶鍵（規則條號或 diff 單元名），無鍵的行不計數（TSLG svn_review 的既有做法，讓逐項比對可數而不改 schema） | 候選 | TURN_AUDIT 每輪 Stop 都跑，是唯一不靠 plan mode、不靠檔名 regex 的審查點；專案層繞路三問放這裡 |
| 3 | 哨兵比對：acceptance 已列 trace 內驗證指令（`acceptance.py:411-432`），補比對 `^<NAME>_CHECK (PASS|FAIL)$`；驗收單驗證指令行以 `[人眼]` 開頭者跳過不計（TSLG 的 Unity 驗證多為人眼，否則整份會被判「驗證未跑」） | 候選 | 專案層 D3 契約的根層接點；沒它，「驗證指令跑過」≠「驗證通過」 |
| 4 | 同模型端節流校準：PostToolBatch 在本回合 Edit/Write 累計達 N 或修改檔數 ≥3 時注入一行（≤40 token）「使用者真正目標／現在做的屬哪部分／有沒有更少的做法」 | 候選 | Companion 非同步，這是唯一的即時層；節流守零 token 稅 |
| 5 | 量效果：wg_friction `user_correction_count` 與 wisdom reflection_metrics 前後對比 | 候選 | 沒數字就沒法判 1～4 有沒有用 |

不做（已決定，理由）：
- 新 hook 家族：現有 Stop／PostToolUse／PostToolBatch 已覆蓋三個視角需要的時點，再開家族是重複。
- 新的行為規則 atom：規則已夠，重犯紀錄證明缺的是執行面不是文字。

## 待使用者拍板（未拍板前只查證、不實作）

六題互不重疊，逐題獨立回答；個別答案優先於建議套裝。第 1 題答「否」則其餘五題作廢。

| # | 問題 | 建議 | 答「是」動到的檔 |
|---|---|---|---|
| 1 | 本階段要不要啟動？「啟動」＝批准第 2～6 題中答「是」的項目在**一個實作 session** 內改完；之後 **5 個觀測 session** 由根層 SessionEnd 自動記錄 Companion inject 與使用者採納／糾正，第 5 個 session 結束時我出一張表，再決定留或關 | 是 | 無（總開關，實際檔案見各題） |
| 2 | 做法 1：開 `soft_gate.architecture_review`（regex 不擴）？ | 開；跑 5 個 session 後看誤報率，誤報＝Companion 標 inject 但使用者未採納或明說不對，超過一半就關回 | `workflow/config.json` |
| 3 | 做法 2：TURN_AUDIT 加三面鏡、餵 diff、每行帶鍵？ | 是 | `tools/codex-companion/prompts.py`（提問文字）、`assessor.py`（組 turn_audit 的 context：`assessor.py:548-611` 只傳 modified_files，`:579-584` 的 diff_digest 現在只給 acceptance 用，要改成 turn_audit 也拿到）、`audit.py:118-123`（diff 只在 acceptance 分支蒐集，要擴到 turn_audit）。三處皆本 session 以 grep 定位，確切行待實作時再核 |
| 4 | 做法 3：哨兵比對（跳過 `[人眼]` 行）？ | 是 | `tools/codex-companion/acceptance.py` |
| 5 | 做法 4：PostToolBatch 校準行；N 取多少？ | 本階段先不做，等第 2～4 題的數字；若做，N=5 | `hooks/handlers/post_tool_batch.py` |
| 6 | SessionEnd over-engineering 指標浮出成一行？ | 是，半小時內 | `hooks/handlers/session_end.py:233-243` |

不另設題：Codex 回傳 schema 本階段不改（已決定改用每行帶鍵，見做法 2）；專案層若兩週後證明敷衍率高再開新題。

## 未解問題與阻擋關係（跨專案，非上面六題；都不阻擋根層做法 1～6）

| 問題 | 誰答 | 現況 | 阻擋誰 |
|---|---|---|---|
| SGI 零件 A 是否借 TSLG 的 Roslyn 檢查器當引擎 | 狀態＝**SGI 已決定借，仍待使用者批准**；未批准前 SGI 不起手（它自述 Session 1 等拍板）。使用者要答的具體問句只有一句：「批准 SGI 借 TSLG 引擎嗎？」 | TSLG 實測：單檔 ≤0.6 秒、`--json` 有 `line_number`、加規則＝三檔加條文一段；但分區是引擎核心的四個路徑前綴常數（`Core\RuleContext.cs:19-22`），接第三專案要改核心或抽成參數。**SGI 已定論：借**（from-projects/005），regex 版作廢；唯一核心改動＝四個分區前綴與 selftest 虛擬路徑抽成命令列或 json，預設值等於現在常數、對 TSLG 零影響；誰改、改在哪份隨「引擎的家」一起拍板。 | 只阻擋 SGI 零件 A，不阻擋根層 |
| 共用檢查器放哪 | 使用者 | 候選：公司層 `C:\CompanyAtomsMem` 工具卡，或獨立 repo 兩邊各自 checkout。三方皆同意不放根層。 | 只阻擋 SGI 零件 A 的起手位置 |
| TSLG 各 checker 是否加哨兵尾行 | TSLG 向使用者提 | 技術成本不到 10 行，TSLG 無反對理由；屬改該專案工具碼，等使用者。 | 不阻擋；未加前根層比對對 TSLG 只是不計分 |

答案衝突時優先序：使用者拍板 > SGI 定論 > 本文記錄。

TSLG 順帶揭露的它自家問題（不歸三方處理）：其 selftest 目前 FAIL，因 `_AIDocs/Rules/Coding_Style_Checklist.md` 在 HEAD 不存在，連帶本機排程審查跑不了。教訓供借引擎者：selftest 與文件雙向對齊會把工具健康綁在文件健康上，借用時對齊對象要改成自己的條文檔。

已鎖定、不必重問：哨兵格式 `^<NAME>_CHECK (PASS|FAIL)$`（根層與 SGI 逐字同意，to-root 003）。外部待回覆：TSLG 是否收斂到同格式，SGI 已在 tri-link from-projects/002 第 5 問向它問。

## 第二輪（使用者加問四題）後的修正，來源 tri-link root/004、root/006、root/007（含 Codex gpt-6-astra 反面）

- **原則**：確定規則由程式裁定；語意問題由 LLM 帶證據審；需求取捨與正式例外由人裁。code 前濾只負責整理證據與去重，不得用「靜態沒命中」排除語意審查。做法 2 依此改寫。
- **機器規則必須錨到專案的優先清單**（如 SGI 的 H 系列），指不到的預設關；規則命中多但使用者糾正沒降＝在數噪音，關掉。沒有優先清單的專案第一步是列清單，不是裝檢查器。
- **不裝解析器的專案最低配置**：優先清單文件＋CLAUDE.md 一行指標；Companion 三面鏡拿 diff 對清單審；零解析器的 code 訊號（檔案行數增量、同檔重改、實動 vs 預估檔數）。沒有當下的語法級攔截，誠實標明。
- **記憶系統的兩個接點**：規則本體住專案正本與檢查器；atom 保留來源、例外、失效條件並連到正本（不是只放指標句）。結果回流：命中頻率只觸發複查，複查先分五類（真重犯／舊問題重複掃到／規則誤報／合理例外／前提失效），只有真重犯寫教訓，草稿進 `_pending_review/` 不直寫。此為根層新候選做法 6，待拍板。
- **哨兵契約修正**：生產端機器行固定 `<NAME>_CHECK PASS|FAIL`，名稱必以 `_CHECK` 結尾；WARN 不是驗收狀態；工具 exit 2 不印哨兵＝未跑。原範例 `SMELL_GATE PASS` 等不符，已要求兩專案改名。
- **錨要是現在還痛的**（SGI 補）：已結案或已裁定不做的項目只能當語料，不能當開規則的理由。
- **根層自己的噪音規則**（SGI 實證，本 session 也觀察到）：Codex handoff 自檢對同一份文件連判 12 輪 high、`[情境:規劃] 架構級變更先 EnterPlanMode` 每則訊息注入、整場 0 採納。候選做法 7：改這兩條的觸發條件（handoff 自檢同文件同結論不重複；情境分類不在純討論回合觸發），待拍板。
- **Q5（使用者）：守門方案不等於自動重構。** 「結果一樣」只有特徵測試能證明；「簡單幾百倍」不會發生、二到五倍會。已向兩專案提一個雙盲重構實驗設計（tri-link root/008），執行需使用者點頭。
- **規則卡三要素**（SGI 採 Codex）：每條機器規則要寫「命中代表什麼風險、怎麼確認、確認後做什麼」，缺一不開。規則分兩類驗收：**風格契約**（使用者明定，使用者說關才關）與**品質假說**（抽樣判讀命中與糾正，無效就關）。錨分**防回歸**（已結案項目的證據可開，不占整改優先權）與**當前優先**（還在痛的）。
- **goal_drift 的 code 前濾改比檔名集合不比數量**（SGI 採 Codex）：IDENTITY 動手前預告已列預估，根層 parse 檔名集合與實動集合取差。回流去重用 `hit_id`（檔＋規則＋成員簽名雜湊）跨 session 只算一次持續存在；feedback atom 草稿的有效期與成效驗證仍未解，列根層待拍板。
- **Q5 在 SGI 的事實**：sgi_server 零測試專案；行為等值既有證法是資料層 byte 差分加使用者環境 live（H-3 五防線 SOP），不是單元特徵測試；所以「自動找到並改對並自證」三段中第二段現況做不到。無提點選目標不能由已讀過 H 清單的 session 跑，要乾淨 session，且 CLAUDE.md 自動載入控制塔算不算提點由使用者裁。Codex 本機沙箱（1385）讀不到檔，只能吃內嵌材料，內嵌即提點；要它自己找目標或改碼需 `danger-full-access`，要使用者點頭。
- **數量不是臭味，切分有沒有責任軸才是**（使用者裁示，以 partial 為例：對外 API／內部核心／遊戲邏輯三個 partial 是好設計）。數量型指標只當線索列報表；「每個 partial 能否對到一個職責」這類問題進 Companion 語意審提問，不進計數規則。
- **Codex 指出的事實錯誤**：CS-28 已是 TSLG 機器規則；「每型別 partial 數」不是單檔可數。

## 專案層對根層的需求（來源 `_AIDocs\DevHistory\v6.0-寫程式碼的進化-2026-10\inbox\root-link\to-root\003-accept-and-root-needs.md`）

1. TURN_AUDIT 加三面鏡並餵 diff 摘要（＝本文做法 2）→ 待拍板第 3 題。
2. Codex 回傳 schema 加條目陣列 → **已定案：本階段不改**，改用每行帶鍵（SGI 於 from-projects/004 同意此替代）；兩週後敷衍率高再開新題。
3. acceptance.py 補哨兵比對（＝本文做法 3）→ 待拍板第 4 題。
4. SessionEnd over-engineering 指標浮出成一行（原專案層 E2，移歸根層）→ 待拍板第 6 題。

做法 2 列的 `assessor.py` 接點：本 session 只 grep 到它組 turn_audit 的 context（`assessor.py:548-611`，modified_files 與 diff_digest 在此組裝），確切改動行待實作時再定。

分工定案（雙方已同意）：專案層管「數字與同步閘」，根層管「語意與每輪之間的第二視角」。

## 代號與外部依賴（讓只拿到本文的人能解碼）

- **專案層綱要／零件 A～E**：`c:\Projects\.claude\memory\_staging\next-phase-AI寫碼守門.md`。A＝C# diff 異味計數器、B＝範本檔與禁用表、C＝專案 `.claude/settings.json` 原生 hooks（C1 已刪、C2 commit 前閘、C3 編輯後計數）、D＝驗證工具契約四條、E＝繞路三問（上收根層，落本文做法 2）。
- **繞路三問**：目標一句話是什麼；從現狀到目標最短路徑是什麼；本計畫比最短路徑多出來的每一項各在解什麼問題。
- **D3 哨兵契約**：每支驗證腳本的結果收斂成整行 `<NAME>_CHECK PASS` 或 `<NAME>_CHECK FAIL`；生產端＝專案腳本，消費端＝根層 `tools/codex-companion/acceptance.py`（本文做法 3）。雙方已逐字同意此格式。
- **「規則在、仍重犯」的 feedback atom**：例 `memory/Failures/驗證與實證/feedback-未實證先別斷言-從根源驗證-先證再修-反退避反冗長.md`（[固]）。
- **root-link 往返信**：`_AIDocs\DevHistory\v6.0-寫程式碼的進化-2026-10\inbox\root-link\`，to-root 001～003 為專案層來信，to-project 001～007 為根層回信；三方討論在 `_AIDocs\DevHistory\v6.0-寫程式碼的進化-2026-10\inbox\tri-link\`。

未取得拍板前，本綱要只是候選方案，禁止直接實作。

## 限制

- Companion 非同步，結果在下一個 UserPromptSubmit 注入：是「每輪之間」的第三人稱，不是「每一步」。即時層是兩件：根層校準行（文字）加專案層計數（數字）。
- Codex 輸出 schema 是單一 JSON（無條目陣列），要「逐項比對」得改 schema。

## 第三方（TSLG）加入後的新事實（來源 `_AIDocs\DevHistory\v6.0-寫程式碼的進化-2026-10\inbox\tri-link\from-tslg\001-ack-tslg-inventory.md`）

- TSLG 已有 Roslyn 語法樹規則檢查器 `C:\TSLG\Tools\CodeReview\rule_check\`（14 條、每條附 bad/good 自驗），跑在 commit 之後的排程審查；寫碼當下與 commit 前 0 道機器閘。與專案層零件 A 功能重疊。（歷史資訊：此句寫於討論中；已被「未解問題與阻擋關係」表第一列取代——技術方向已定為借用 Roslyn、regex 版作廢，尚未取得使用者執行授權。）
- 兩個 C# 專案共用的 Roslyn 檢查器，家不在根層 `~/.claude`（不放語言專屬工具）；歸公司層工具卡（`C:\CompanyAtomsMem`）或獨立 repo，SGI 與 TSLG 皆同意，位置待使用者拍板。
- TSLG 驗證腳本有五種 PASS/FAIL 格式，無統一哨兵。角色：TSLG 腳本是哨兵的**生產端**之一（消費端只有根層 acceptance.py）；它是否收斂到已定案的格式，待它答 SGI 的問題，未答前根層只認同一個 regex。

未拍板前只可查證、禁止修改或實作；下一步先請使用者回答「待使用者拍板」六題。

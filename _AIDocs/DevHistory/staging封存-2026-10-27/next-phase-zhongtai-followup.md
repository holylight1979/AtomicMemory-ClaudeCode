# next-phase：中台記憶地基後續（已知問題兩項 → 其他 AI 輕量安裝 → 願景快項）

> 本檔絕對路徑：`C:\Users\holylight\.claude\memory\_staging\next-phase-zhongtai-followup.md`
> 專案根：`C:\Users\holylight\.claude`（原子記憶系統根層 repo，branch `main`）
> 人稱約定：[使用者]＝holylight；[AI]＝接手本檔的 Claude Code session；[同事]＝TSLG／SGI 專案成員。

## ⚠ 關鍵約束（先讀）

- 根層程式碼／文件的 commit 一律等 [使用者] 單獨送一則「上GIT」才做，commit＋push 一氣完成；選擇性 staging 列明路徑，**禁 `git add -A`**（公司 repo 也一樣——上次整包加入誤提交了 25 個 `*.access.json`）。
- 已 push 的 commit 不改寫（origin 是 GitHub＋公司 GitLab 雙 push URL，GitLab main 擋 force）。
- 全量 `python run_verify.py --json` 已從流程拔掉，不跑（全量改增量待補）；收尾只跑宣告的驗證範圍（git 類測試偶發紅見「未解問題 Q3」）。
- 改 `tools/workflow-guardian-mcp/lib/*.js` 後要重啟 Claude Code 才生效；本 session 內只能用 `node tools/workflow-guardian-mcp/verify/smoke_mcp_stdio.js` 驗。
- Bash heredoc 內含反斜線或大段含引號程式碼時，改用 Write 寫成腳本檔再跑（已三度踩到 `\n` 被展開、shell 解析失敗）。

## 1.【前置脈絡】

- 為什麼做：公司主管定的「公司共用後台核心（中台）」三要件＝共用後台＋中台主機、新專案直接接、各職能工具與知識丟上去 AI 自動分類註冊全公司共用。記憶地基已落地並推上版控；現在要（a）清掉會影響 [同事] 上手第一印象的已知問題，（b）讓企劃／美術等「不用 Claude Code」的職能也能接上公司記憶，（c）挑願景裡最快見效的一兩項。
- 判斷標準（[使用者] 定）：精準、從輕而確實、元件化、刀刀砍在關鍵處；完工後使用體驗直覺、用講的就能操作、不必記指令；能自動驗證的不推給 [使用者]。

## 2.【已完成】（皆已 push，工作樹乾淨）

- 根層 `~/.claude`：`d80b86f`（memory_search 讀取端、公司層 org、AD 身份／職能／`review.deciders`、Source／Depends 欄、編碼硬化、工具卡掃描器）、`5a7947f`（`/org` skill、`org-memory.py --join／--status`、工具卡觸發詞收斂）、`18318ee`（`--init` 佈 `.gitignore`）。
- 公司記憶 repo `https://gitlab.uj.com.tw/open-data-prog/companyatomsmem.git`，本機 `C:\CompanyAtomsMem`：`02ba39a` 骨架、`3fceb9d` 工具卡、`6545bc8` access sidecar 移出版控。現有 26 張卡（`shared/工具/`：21＋1 張 `skill-*`、3 張 `mcp-*`、種子 `org-memory`）。
- 驗證：全量 2195 案 2193 passed／1 skipped／1 偶發紅（見 Q3）；`smoke_mcp_stdio.js` SMOKE OK；從 `C:\Projects`（SGI）視角 `memory-search` 查得到公司層 atom（`scope: "org"`）。
- 只有 [使用者] 這台機器接上公司層；[同事] 尚未更新。

## 3.【權威來源】（先讀這些）

- 計畫與審查裁決全文：`C:\Users\holylight\.claude\plans\prancy-marinating-kay.md`（「辯論會議裁決」表＝哪些被砍、為什麼）。
- 現況規格：`TECH.md` §4.4（scope 與 org）、§5.8（memory_search 契約）、§12（設定鍵）、§13.1（身份／職能／裁決）；`Install-forAI.md` Step 4b（其他 AI 客戶端現況寫法，L235-245）。
- 程式接點：`hooks/wg_core.py:163 load_config`、`:181 org_memory_root`；`tools/workflow-guardian-mcp/lib/realm.js:18 orgMemoryRoot`；`hooks/handlers/session_start.py:594 _org_advisory`；`tools/org-memory.py`（`register_in_config`、`cmd_join`、`cmd_status`）；`hooks/handlers/pre_tool_use.py:340-372`（CommitOrder 閘）、`hooks/handlers/ups_gates.py:31 track_turn_prompts`、`hooks/handlers/stop.py:717`；`hooks/ensure-mcp.py`＋`mcp-servers.template.json`（MCP 註冊）；`lib/memory_search.py`、`tools/memory-search.py`。
- 既有守門：`hooks/verify/verify_git_commit_order_gate.py`、`hooks/verify/verify_org_layer.py`、`tools/verify/verify_tool_cards.py`、`lib/verify/verify_memory_search.py`。
- 相關 atom：[[commitorder閘只認最新一則使用者原話-中間夾系統通知或背景事件就要請使用者重下口令]]、[[程式批量產生的atom觸發詞不得含日常字與種類單字-一句話就把整批拉進注入吃光預算-只放專名與名稱加種類片語]]、[[身份與職能自動來自ad-帳號即get-current-user-職能由whoami群組對映-查不到就空不預設programmer-裁決名單review-deciders]]、[[併發-session-共用工作樹-收尾選擇性-staging-勿-git-add-a]]。

## 4.【產出位置】

- Step 1a：改 `hooks/wg_core.py`、`tools/workflow-guardian-mcp/lib/realm.js`、`tools/org-memory.py`、`workflow/config.json`、`.gitignore`（若新增本機檔）；verify 加在 `hooks/verify/verify_org_layer.py`。
- Step 1b：改 `hooks/handlers/` 內閘或收集端；verify 加在 `hooks/verify/verify_git_commit_order_gate.py`。
- Step 2：新 `tools/`（或 `skills/org/`）下一支輕量安裝腳本＋`Install-forAI.md` Step 4b 改寫＋`README.md` 一句；verify 新檔放 `tools/verify/`。
- 每步完成：`_AIDocs/_CHANGELOG.md` 一條、`TECH.md`／`Install-forAI.md` 對應段落同步（清單見 atom [[feedback-memory-system-doc-sync]]）。

## 5.【做法】（依序；每步做完、驗完，列「改了哪些檔＋驗了什麼」問一次「上GIT？」）

### Step 1a：共用設定檔帶著本機公司層路徑（約 1 小時）
- 現象：`workflow/config.json` 進版控且現值為 `org_memory: {"repo_url": "https://gitlab.uj.com.tw/open-data-prog/companyatomsmem.git", "enabled": true, "roots": [{"id":"org","root":"C:\\CompanyAtomsMem"}]}`。[同事] 更新後、接上前，每次啟動都看到 `[Org] 公司層記憶尚未接上（…）→ 對我說「接上公司記憶」或 /org join`；且 `--init`／`--join` 會改寫這個進版控的檔（每台機器路徑不同 → 互相覆蓋／衝突）。
- 目標：「公司 repo 網址」留在共用設定；「這台機器接上沒、根在哪」改存本機不進版控的地方。未接上的機器啟動**只提示一次**（本機記一個已提示標記，之後不再出現；已裁決，直接實作）——零提示會讓 [同事] 不知道有公司層，每次提示則是擾民。已接上的人行為不變。
- 做法方向（已定）：機器專屬狀態移到不進版控的本機檔（例：`workflow/org-memory.local.json`，加進 `.gitignore`）；`org_memory_root()`（py）與 `orgMemoryRoot()`（js）同規則先讀本機檔、共用 config 只留 `repo_url` 與預設；`register_in_config` 改寫本機檔；[使用者] 這台要無痛遷移（現值搬過去，共用 config 還原成 `enabled:false, roots:[]`＋`repo_url`）。py／js 兩端必須同規則，守門看 `verify_org_layer.py` 既有 config 案的寫法。

### Step 1b：口令閘漏收回合中途的 [使用者] 訊息（約 1 小時，先重現再修）
- 現象：[使用者] 在 [AI] 回合進行中送「我先給授權：…就直接 上GIT」，同回合稍後 `git commit` 仍被 `[Guardian:CommitOrder] 本回合使用者原話沒有版控口令` 擋下；共發生三次。
- 已知：`pre_tool_use.py:358-360` 註解寫明「整回合原話（含 mid-turn 排隊訊息）都算」，資料來自 `state["turn_prompts"]`（`ups_gates.track_turn_prompts` 在 UserPromptSubmit 收）。
- **未驗證的兩個候選根因（待確認，勿據此鎖死）**：(A) 回合中途的訊息由 harness 夾在工具結果裡送達、不觸發 UserPromptSubmit，所以進不了 `turn_prompts`；(B) 該 session 多次出現 `[Guardian] state 已重建（原 state 遺失/被 TTL 清除）`，`turn_prompts` 隨 state 一起丟失後退回只看最後一句。
- 做法：先寫能分辨 A／B 的最小重現（看 hook 輸入與 state 檔），再修；修法不得讓「[AI] 自己輸出含口令字樣」或「背景通知內文」被當成 [使用者] 口令（既有守門案必須仍綠）。

### Step 2：其他 AI 客戶端輕量安裝（約半天）
- 目標：企劃／美術等不用 Claude Code 的人，在他們的 AI 客戶端裡能查公司記憶（`memory_search`）、能把知識寫到公司層（`atom_write scope=org`），**不裝 hooks**。
- 已有：workflow-guardian MCP server（`tools/workflow-guardian-mcp/server.js`，8 個 tool）任何支援 MCP 的客戶端都能註冊；`Install-forAI.md` Step 4b 已有 Codex 範例。缺的是「一支腳本＋一頁說明」：檢查 Node／Python、clone 或更新 `~/.claude`、`org-memory.py --join`、印出該客戶端的 MCP 註冊片段。
- **開工前必問 [使用者]（一題）**：企劃與美術實際用哪個 AI 工具？支援 MCP 的桌面客戶端（Claude 桌面版、Cursor 等）→ 照上述半天可成；只能用網頁版、接不了本機工具 → 改做查詢網頁（dashboard 的 `GET /api/memory/search`，計畫列的選配），工時一到兩天，且要先處理「dashboard 行程由 Claude Code 生出、EOF 即退」的限制（`server.js:411-439`）。
- 注意：沒有 hooks 就沒有「每句話自動帶入記憶」，使用者要主動說「查記憶」；身份走 OS 帳號＝AD 帳號，`unknown` 不讀 personal（已實作）。公司層目前只有「工具」一個範疇，非程式職能要寫入時需開新範疇（`allow_new_category`）——順手在說明裡交代，或與 [使用者] 確認要不要預先開幾個。

### Step 3（Step 1、2 上版控後再問 [使用者] 要哪個）
- 作業紀錄月誌：半天到一天，既有 `journal` skill 事後彙整＋版控紀錄 → 月報；只做事後彙整，不做即時監看。
- 會議會後轉錄 → 摘要 → 入庫：一到兩天，本機顯卡跑語音辨識；即時翻譯不做。

## 6.【決策依據】

- 順序理由：[使用者] 正要請 [同事] 更新，Step 1a 是每個人第一眼會看到的東西；Step 2 是功能類每小時效益最高、直接補三要件「跨職能共用」。
- 已定案、不翻案：不做 SSO／RBAC／簽章／成員表（身份＝AD 帳號）；管理職概念已拿掉（`review.deciders` 空＝全員可裁決）；`org` 不進 `VALID_SCOPES`（MCP／CLI 語法糖＝指定根的 shared）；公司層只認單一根；工具卡只 create-if-absent、觸發詞只放卡名與「名稱＋種類」片語；HTTP 查詢路由不是「非 CC 人員的門」。各項理由在計畫檔「辯論會議裁決」表。
- 被否決的做法：把本機路徑留在共用 config 靠每人手改（會髒工作樹、互相覆蓋）；用 python subprocess 包 `git commit` 繞過口令閘（等於洗白，禁止；只有記憶庫的 vcs-sync worker 是 [使用者] 裁決過的自動提交例外）。

## 未解問題（每條可被回答）

- Q1：企劃與美術用的 AI 客戶端是哪一個、支不支援 MCP？（決定 Step 2 走腳本還是查詢網頁）
- Q3：三支 git／svn e2e 測試（`verify_vcs_sync_worker::test_pull_diverged_index_json_conflict_auto_resolved`、`verify_merge_driver_gate::test_session_start_svn_index_conflict_advisory`、`verify_merge_atom_index::test_resolve_after_merge_conflict_then_commit`）在全量或有其他 git 活動並行時各偶發過一次、單跑皆穩定。**未驗證的線索**：測試期間 hook／背景 worker 動到 global git config 的 merge driver 設定。不在本階段必修範圍；若 Step 1 的全量又撞到，單檔重跑確認後照實回報即可。
- Q2：口令閘漏收的根因是 A、B 還是兩者皆是？

## 留給 [使用者] 的手動事項（[AI] 不代做）

- （已完成）[使用者] 已重啟 Claude Code；`memory_search` 工具與 `/org` skill 已載入。
- 清 TSLG 本機亂碼空資料夾：`svn revert "C:\TSLG\.claude\memory\shared\UIºt¥X"`。
- 通知 [同事]：更新 `~/.claude`、重啟、說「接上公司記憶」（建議等 Step 1a 上版控後再通知）。

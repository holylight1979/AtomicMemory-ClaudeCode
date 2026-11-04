# 02 面向：多 session／多 agent 協作、自動化與排程、接續與收尾

> 讀者：要決定原子記憶系統下一步改什麼的人（使用者）與接手實作的 AI。
> 範圍：現況對帳表第 6 節候選 #8–13、#21，加上子代理在「多 agent 協作」角度的影響（注入機制本身留給 01 面向）。
> 材料：官方收割原文（`Docs/<夾>/<slug>.md`）、[現況對帳](../../../ClaudeCodeInternals/Docs/_現況對帳-原子記憶系統用到的CC機制.md)、[多 session 通則](../../../MultiSessionCollaboration.md)、程式碼（`hooks/`、`skills/console/`、`tools/`）。
> 版本基線：本機 VS Code 擴充內建 `claude.exe` 實測 **v2.1.317**，下文所有版本門檻（最高 v2.1.309）都已滿足。
> 本檔只分析、不改任何既有檔。標「未實測」的是官方頁有寫、本機還沒跑過的推論。
> 歸檔說明：本檔是 v6.1 動工前（2026-11-04）的計畫，文中「現況」指動工前；實際做了什麼、驗到哪見 [升級全紀錄](../升級全紀錄.md)。指向 v6.1 已刪檔的連結改成純文字並標「v6.1 已刪」。

## 一句話結論

原生在這半年補齊了「session 互相找得到、叫得醒、有固定名字、自己開 worktree」這四件事，我們 `/console` 與檔案信箱裡有一半的儀式是在繞這四個缺口，可以直接拆；但「跨人跨帳號的需求信箱」「同一工作樹的撞檔預警」「跨機器可讀的交接單」原生仍做不到，要留。另有兩個官方行為變化正在踩我們：子代理預設改背景跑之後，收尾閘會在「只是在等背景工作」的回合誤擋；`claude -p` 未來預設 `--bare` 會讓無頭裁判與無頭驗收靜默失效。

## 候選對照（現況對帳表 §6 → 本檔提案）

| 候選 | 自製功能 | 本檔處置 |
|---|---|---|
| #8 | `/console` 雙總控台＋派工信箱＋console-spawn | P1、P2、P3、P5、P7 修剪；agent teams 取代 → 不建議 |
| #9 | 手動 `git worktree add`＋補 `~/.claude.json` 信任 | P7 |
| #10 | 檔案信箱（root-link／tri-link／to-opus／mailbox） | P8（Claude 對 Claude 換原生）；mailbox、to-grok 保留 |
| #11 | 跨 session 同檔預警 `wg_coordination` | 保留，P10 補強 |
| #12 | handoff／continue／auto-continue watcher | P11 拆 watcher；P12、P13；handoff 保留 |
| #13 | 收尾閘「宣告完成」檢核、need-goal | P4；need-goal 已不在現行程式（見文末附註） |
| #21 | Windows 工作排程器跑健檢、用量監控 | 保留（不建議搬家，理由見文末） |

---

## 提案（依建議優先序）

### P1. 設 `crossSessionInbound: "accept"`，讓跨 session 訊息不再被默默扣住作廢
- 官方機制：跨 session 訊息的入站控制 `crossSessionInbound`（accept／hold／refuse）與核准期限 `dialogExpiry`（頁：[cross-session-messaging](../../../ClaudeCodeInternals/Docs/02-build/cross-session-messaging.md)「控制傳入訊息」、[settings-reference](../../../ClaudeCodeInternals/Docs/05-configuration/settings-reference.md) `crossSessionInbound`；首次出現 v2.1.224，原生 Windows 傳訊需 v2.1.234）
- 現況：`settings.json` 沒設這個鍵（現況對帳 §2.1 未列）。卡片 `跨session訊息在收件端進計畫模式時會被扣住…逾時就作廢不送達` 記下實測：工作分頁進計畫模式後，補充訊息被扣、沒人按就作廢；反向交付信也可能沒送到。對策目前是派工規矩「要說的事一次寫進開工句」（[MultiSession §5](../../../MultiSessionCollaboration.md) 第二條）。
- 落差／機會：這不是 bug，是官方的預設規則——沒設值時，「略過權限」與「會問權限」兩類 session 互傳就扣住；VS Code 分頁顯示不了核准框，扣住的訊息等滿 `dialogExpiry`（預設 5 分鐘）就丟。我們全部 session 都是 `bypassPermissions`，唯一會換類別的就是進計畫模式那一刻（官方說計畫模式只在「互動式終端機」裡算略過類，VS Code 分頁不是），正好對上卡片的現象（推論吻合，未實測）。一個設定鍵就能讓它不再發生。
- 做法：接上新能力。`settings.json` 加 `"crossSessionInbound": "accept"`（使用者層，隨 git 同步到每台機器）；之後把 MultiSession §5 第二條與該卡改成「已由設定排除，計畫模式也收得到」。
- 代價與風險：任何一個自己的本機 session 都能把訊息送進另一個——但現在全是 bypass，扣住本來就保護不了什麼；訊息仍「不算使用者同意、不能改設定、指令不執行」（官方保證）。日後若接 Remote Control，其他機器的 session 也會被直接收下，那時加 `isolatePeerMachines: true`。專案層設 `refuse`／`hold` 仍會蓋過（官方優先序：較嚴的專案值仍生效）。
- 驗法：開兩個背景 session，一個 `--permission-mode plan`、一個 bypass，互送一則訊息；改設定前收件端出現 held 通知、改後直接進對話（讀雙方 transcript 可自動判）。`/config` 的「Messages from your other sessions」列應顯示 accept。
- 分級：C

### P2. 工作軌一律用 `--name <軌名>` 起、總控台用 `/rename`，拆掉「名字會變、先 ListAgents、Reload 後點名」整套儀式
- 官方機制：session 命名 `--name`／`/rename`，名字就是 SendMessage 的地址，可 `@軌名` 指名；背景 session 的名字跨 supervisor 重啟保留（頁：[sessions](../../../ClaudeCodeInternals/Docs/01-getting-started/sessions.md)「命名您的 sessions」、[cross-session-messaging](../../../ClaudeCodeInternals/Docs/02-build/cross-session-messaging.md)「查看 Claude 可以到達的工作階段」、[agent-view](../../../ClaudeCodeInternals/Docs/02-build/agent-view.md)「從您的 shell 分派 agent」；`-n/--name` v2.1.76，背景 session 改名保留 v2.1.202，`@` 指名 v2.1.232）
- 現況：[`skills/console/SKILL.md`](../../../../skills/console/SKILL.md) 硬規則 1「送信前先 ListAgents，不寫死 claude-xx；名字 Reload 後會全變」、用法一 Step 4「Reload 後對陌生名字送『你是哪一軌？』」、規則 2「跟人說話用軌名，不用 claude-xx」；[`console-spawn.py`](../../../../skills/console/scripts/console-spawn.py) `build_cmd` 沒帶 `--name`，靠輪詢 `claude agents --json` 加讀 transcript 才知道新軌叫什麼。MultiSession §5 還寫「ListAgents 名字跟 session id 對不上，要拿 transcript 第一筆時間去比」。
- 落差／機會：`claude-xx` 是官方的「預設顯示名稱」＝工作目錄名（`.claude`）加兩碼尾碼——本機實測 `claude agents --json` 列出 `claude-ba`、`claude-71`，每次重開程序就換一個。設了名字就固定、人看得懂、session 之間直接用它定址。另外 `claude agents --json` 已經同時給 `sessionId` 與 `name`（本機實測有這兩欄），「拿時間去比」那招已經不需要。
- 做法：直接換用原生。① `console-spawn.py` 的 `build_cmd` 在 `--bg` 後加 `--name <軌名>`，報到判定直接用這個名字；② kickoff 範本 §1、§2 加「開分頁後先打 `/rename 對人總控台`（或 `調度總控台`）」——`/rename` 只能由人在那個分頁的鍵盤打，模型代打不了；③ SKILL 硬規則 1、用法一 Step 4、kickoff §5「Reload 後點名」、MultiSession §5「拿時間去比」改寫或刪除。
- 代價與風險：名字要在同機活著的 session 中唯一，撞名時 Claude 會問或改用短 id（官方行為），軌名本來就望文生義、不重複。VS Code Reload 後 `/rename` 過的分頁名字是否保留，官方頁只寫背景 session 與 `--resume <name>`，VS Code 分頁要實測。
- 驗法：`claude --bg --name t-probe "<一句話任務>"` → `claude agents --json` 的 `name` 應為 `t-probe`；另一個 session 對 `t-probe` SendMessage 成功；`claude respawn <id>` 後名字不變；VS Code 分頁 `/rename` 後 Reload，再看 `claude agents --json`。
- 分級：A

### P3. 等回信改靠「閒置收件自動開回合」與 `notify_when_idle`，撤掉「空手不能結束回合」與「背景 sleep 當鬧鐘」（先跑探針）
- 官方機制：收件 session 閒置時，到達的訊息會直接開新回合；`SendMessage` 的 `notify_when_idle` 可訂閱「對方下次閒置或結束時通知我」，訂閱本身不花 token、12 小時沒來就自動作廢；session 範圍排程 `/loop`、`CronCreate`（頁：[cross-session-messaging](../../../ClaudeCodeInternals/Docs/02-build/cross-session-messaging.md)「訊息傳遞」「在另一個工作階段閒置時獲取通知」、[scheduled-tasks](../../../ClaudeCodeInternals/Docs/02-build/scheduled-tasks.md)；傳訊 v2.1.224，`notify_when_idle` v2.1.236，v2.1.317「送給執行中背景 agent 更早送達」，`/loop` v2.1.71）
- 現況：卡片 `跨session訊息只在收件端下一次呼叫工具時才送進來-光結束回合等不到同伴回覆-要等人答完再醒可先背景跑短sleep當計時器`（2026-10-14 實測）；`/console` 硬規則 5「等同伴回信不能空手結束回合」；MultiSession §5 第一條；§2「主持端每 60 分鐘對帳」靠總控台自己記得；現況對帳 §4.1「Bash run_in_background 短 sleep 當鬧鐘」。
- 落差／機會：官方頁寫的跟我們卡片相反：閒置的 session 收到訊息就會被叫起來。卡片當時的現象，有可能是 P1 的扣留（訊息根本沒進來），也可能是當時版本的行為（約 v2.1.30x，之後 v2.1.317 又改過送達時機）。若官方說法成立：等回信就不用鬧鐘；等「工作軌做完」可以用 `notify_when_idle` 訂閱，取代輪詢 `claude agents --json`；「每 60 分鐘對帳」可以交給調度 session 裡的 `/loop 60m`。
- 做法：改寫法避衝突。先跑探針（見驗法）；證實後：刪 SKILL 硬規則 5、MultiSession §5 第一條與鬧鐘做法，該卡用 `atom_write` 改寫或 `atom_retire` 退役；kickoff §3 派工後加「總控台對該軌設 `notify_when_idle`」；§2 對帳節奏寫成「調度 session 開 `/loop 60m 對帳`」。
- 代價與風險：每則進來的訊息都是一個新回合，`UserPromptSubmit` 也會為同伴訊息觸發（[hooks](../../../ClaudeCodeInternals/Docs/06-reference/hooks.md) UserPromptSubmit 段明列），所以每則信都會跑一次記憶檢索注入，token 照算；`notify_when_idle` 只限主對話、只限同一台機器；`/loop` 重複任務 7 天過期。P1 沒做之前，扣留問題會讓這條探針結果失真，P1 要先做。
- 驗法：兩個 `--bg` session（同為 bypass）：A 送信給已閒置的 B，讀 B 的 transcript，看是否在數秒內出現新回合且沒有任何先行工具呼叫；A 對 B 設 `notify_when_idle`，給 B 一件短任務，看 A 的 transcript 收到通知行。整段可寫成腳本自動判（console-spawn 已有讀 transcript 的函式可沿用）。
- 分級：C

### P4. 收尾閘讀 Stop 輸入的 `background_tasks`：回合只是在等背景工作時，不跑「完工類」的閘
- 官方機制：Stop／SubagentStop hook 輸入帶 `background_tasks`（類型：shell、subagent、monitor、workflow、teammate…）與 `session_crons`，官方明說是讓 hook 分辨「已完成」與「暫停等背景工作叫醒」；`/goal` 自己就是背景工作還在跑時跳過評估（頁：[hooks](../../../ClaudeCodeInternals/Docs/06-reference/hooks.md)「Stop 輸入」、[goal](../../../ClaudeCodeInternals/Docs/02-build/goal.md)「背景工作延遲評估」、[sub-agents](../../../ClaudeCodeInternals/Docs/02-build/sub-agents.md)「哪些 subagents 在背景中執行」；欄位 v2.1.145；VS Code／Desktop 主對話子代理一律背景、fork 預設開 v2.1.302）
- 現況：[`hooks/handlers/stop.py`](../../../../hooks/handlers/stop.py) `handle_stop` 沒讀這兩個欄位（`hooks/` 全目錄 grep `background_tasks` 零筆）。不看「宣告完成」就會擋的閘至少有兩道：同步閘（本 session 改的檔沒 commit）、底部同步擋（改 2 檔以上有待記知識）——見 [TECH §7.1](../../../../TECH.md) 閘表。
- 落差／機會：v2.1.302 起子代理預設背景跑，主回合常在子代理還在改檔時就結束；總控台開 Monitor 等信、背景 sleep 等鬧鐘也一樣。這時收尾閘照樣跑，會逼模型把做一半的東西 commit 或寫解釋（推論，未實測）。原生已經把「是不是在等背景工作」直接放進輸入。
- 做法：接上新能力。`handle_stop` 開頭讀 `input_data.get("background_tasks")`；非空時只留紅測閘與寫碼查核（它們看的是「說了完成」），同步閘、底部同步擋、退縮歸屬、收割延到背景工作回報那一回合；在 [`hooks/wg_release_rules.py`](../../../../hooks/wg_release_rules.py) 加一條有名規則（例：`STOP_DEFERS_WHILE_BACKGROUND_RUNNING`）並寫進 TECH §7.1 與 `TECH/release-rules.md`；`handle_subagent_stop` 同理。
- 代價與風險：session 若掛著一個永遠不結束的 Monitor 或 `/loop`（`session_crons` 的重複項），收尾閘就永遠不跑——要設上限（例：同一背景任務 id 連跳 N 次就照擋）並記帳；跳過的每一次寫 guard log、不靜默。欄位在「任務登錄可存取時」才存在，沒有就照舊。
- 驗法：hooks/verify 加一支案例：Stop 輸入帶一筆 `{"type":"subagent","status":"running"}`、state 有未 commit 改檔 → 改前同步閘擋（紅）、改後放行且 guard log 有一筆 skip（綠）；再實跑一次：開背景子代理後結束回合，看 `Logs/guard-*.jsonl`。
- 分級：C

### P5. 背景工作軌算「沒人能回答」：擋滿後改放行留帳，不再發 AskUserQuestion 卡死
- 官方機制：每個背景 session 都設了 `CLAUDE_JOB_DIR` 環境變數；`/status` 的 Session kind 分 `background job · attached／unattended`；`claude agents --json` 在等人時給 `waitingFor: "input needed"`（頁：[agent-view](../../../ClaudeCodeInternals/Docs/02-build/agent-view.md)「狀態存儲位置」「從指令碼讀取工作階段狀態」「背景工作階段如何被託管」；agent view v2.1.139，TIMELINE 未單列 `CLAUDE_JOB_DIR`）
- 現況：[`hooks/wg_release.py`](../../../../hooks/wg_release.py) `non_interactive_reason` 只認三種沒人能答的情境：裁判子 session、子代理、`sdk-*` 入口；`claude --bg` 起的工作軌不在內 → 寫碼查核擋滿就叫模型發 AskUserQuestion → 沒人答、永遠卡住。現在靠派工單手寫「背景軌收尾不發 AskUserQuestion」（MultiSession §3）與卡片 `claude-bg起的工作軌收尾會卡在askuserquestion沒人答…` 的事後救法（總控台讀 transcript、自己對帳合併再 stop）。
- 落差／機會：原生給了一個可靠的「我是背景 session」訊號，規矩可以從派工單文字變成程式判定。
- 做法：接上新能力。`non_interactive_reason` 加第 ④ 訊號：環境變數 `CLAUDE_JOB_DIR` 存在 → 回「背景 session」；`NONINTERACTIVE_RELEASE_AT_BUDGET` 的說明（`wg_release_rules.py`、`TECH/release-rules.md`）補上這一類；派工單那條手寫規矩改成指向規則名。
- 代價與風險：人 attach 進背景 session 時本來可以答，現在也會直接放行（留帳在 `guard-reconcile.jsonl`，總控台收件時看得到）；使用者自己用 `←`／`/bg` 丟到背景的 session 也算背景，同樣不再問。hook 子程序是否繼承 `CLAUDE_JOB_DIR` 官方只寫「shell 命令可用」，要實測。
- 驗法：單元案例：`non_interactive_reason({}, None, env={"CLAUDE_JOB_DIR": "x"})` 回非空；實測：起一個 `--bg` session，在 hook 裡加一次性 debug log 記下有沒有這個環境變數。
- 分級：B

### P6. 為「`claude -p` 將預設 `--bare`」先做準備：無頭裁判、`--method print`、無頭實跑驗收寫明依賴
- 官方機制：`--bare` 跳過 hook、skill、子代理、外掛、MCP、自動記憶、CLAUDE.md，不讀 OAuth 登入（要 `ANTHROPIC_API_KEY`），不綁跨 session 收件匣，不開背景任務；官方頁寫「`--bare` 是指令碼與 SDK 呼叫的建議模式，並將在未來版本中成為 `-p` 的預設值」；另有 `--output-format json --json-schema` 取結構化輸出（頁：[headless](../../../ClaudeCodeInternals/Docs/02-build/headless.md)「使用 bare 模式更快啟動」「取得結構化輸出」、[cli-reference](../../../ClaudeCodeInternals/Docs/06-reference/cli-reference.md) `--bare`；`--bare` v2.1.81，限制完整生效 v2.1.286，翻成預設的版本未定）
- 現況：[`tools/codex-companion/judge_backend.py`](../../../../tools/codex-companion/judge_backend.py) `run_claude_judge` 跑 `claude -p … --output-format text`，靠訂閱登入、靠環境變數 `CLAUDE_COMPANION_JUDGE=1` 讓 dispatcher 整組早退；console-spawn `--method print`；MultiSession §7「合併前每軌先用無頭 `claude -p` 跑一個真實小任務」看的就是 hook 在真實交付裡有沒有動；auto-continue 的 `claude -p "/continue"` 靠 skill 載入（P11）。
- 落差／機會：預設一翻：裁判認證失敗（fail-open 退回只用啟發式，不容易被發現）、無頭驗收不再跑 hook 卻照樣綠、`/continue` 找不到。這是官方明說會變的行為，現在改成本最低。
- 做法：改寫法避衝突。① 每個 `-p` 呼叫點各自決定、寫在檔頭：要 hook 的（無頭驗收）在結果裡斷言「本 session 的 guard log 有記錄」，沒記錄就判紅；② 裁判本來就不需要 hook、CLAUDE.md、MCP，但 bare 要 API key，維持非 bare，另加 `--strict-mcp-config`（不給 `--mcp-config` 就不起任何 MCP server）省掉每次起 workflow-guardian／playwright 等的成本；③ 裁判輸出改 `--output-format json --json-schema <判決 schema>`，讀 `structured_output`，取代解析純文字；④ 每週看 TIMELINE，出現「關掉 bare」的旗標就在各呼叫點明帶。
- 代價與風險：`--strict-mcp-config` 不給清單時是否等於零個 server 未實測；schema 要隨判決格式維護；裁判現有的「寫碼查核」路由（`JUDGE_HANDLERS`）不動。
- 驗法：設 `CLAUDE_CODE_SIMPLE=1`（官方：等同 bare 的精簡模式）跑一次無頭驗收探針，應判紅（證明斷言有效）；裁判加 `--strict-mcp-config` 前後各跑 3 次量啟動到出結果的秒數；`--json-schema` 版用一份已知判決的材料比對欄位。
- 分級：C

### P7. 工作軌改用 `claude --bg --worktree <軌名>`＋`worktree.baseRef: "head"`，拆掉手動 `git worktree add` 與改寫 `~/.claude.json` 信任
- 官方機制：`--worktree` 建 `.claude/worktrees/<名>/`、分支 `worktree-<名>`；`-p` 跳過信任檢查、互動與 `--bg` 檢查的是你啟動的目錄；進 worktree 後自動強制隔離（擋寫主檢出、擋 git 重定向）；執行中自動 `git worktree lock`；`claude rm` 與定期掃描依規則清理；resume 自動回到 worktree；`worktree.baseRef` 決定從 `origin/<預設分支>`（fresh，預設）或本機 HEAD 分出（頁：[worktrees](../../../ClaudeCodeInternals/Docs/02-build/worktrees.md)、[agent-view](../../../ClaudeCodeInternals/Docs/02-build/agent-view.md)「檔案編輯如何隔離」「刪除工作階段會移除什麼」、[settings-reference](../../../ClaudeCodeInternals/Docs/05-configuration/settings-reference.md) `worktree.*`；`--worktree` v2.1.49，`baseRef` v2.1.133，`bgIsolation` v2.1.143，`--bg` 先查信任 v2.1.281）
- 現況：[`references/dispatch.md`](../../../../skills/console/references/dispatch.md) 與 kickoff §3 由調度先跑 `git worktree add <路徑> -b <分支> main` 到 `~/.claude-wt/<名>`；`console-spawn.py` 的 `ensure_trust` 拿 CC 存設定的同一把鎖（proper-lockfile）去改 `~/.claude.json`，鍵格式靠實測（2.1.304）；工作軌第一步自己 `EnterWorktree` 才進入隔離。
- 落差／機會：建立、信任、隔離、上鎖、清理、resume 回位，原生全包；我們自己改 CC 的設定檔，是最脆的一段（格式或鎖換了就壞）。另外 session 起在手動 worktree 裡時，原生會「略過」自動隔離，所以我們才需要第一步 `EnterWorktree`。
- 做法：直接換用原生（其他專案）。`console-spawn.py` 改成在主檢出目錄跑 `claude --bg --worktree <軌名> --name <軌名> …`，刪 `ensure_trust`；使用者層 `settings.json` 設 `"worktree": {"baseRef": "head"}`——**這條是關鍵**：其他專案的 main 常有等「上GIT」口令的未推 commit，用預設 fresh 會從 origin 分出、少掉這些；需要 gitignore 內容（如 `memory/_staging/` 的讀取材料）就放 `.worktreeinclude`。`~/.claude` 這個 repo 本身另議：原生位置會落在 `~/.claude/.claude/worktrees/`，也就是 live 樹裡面——先確認有沒有從 repo 根往下遞迴掃描的工具會掃到分身；會掃到就維持 `~/.claude-wt/`（或寫 `WorktreeCreate` hook 只對這個 repo 改位置），不會就一起換。
- 代價與風險：分支名變成 `worktree-<軌名>`；hook 仍寫死跑 live 的 `~/.claude/hooks`（跟現在一樣，MultiSession §6 已記）；Agent view 刪 session 會連未 commit 改動一起刪，`claude rm` 才會保留；`WorktreeCreate` hook 建的 worktree 不吃 `.worktreeinclude`、transcript 留在啟動目錄、掃描不清。Windows 上停程序後目錄要等鎖放掉才刪得掉（卡片已記）不變。信任只查啟動目錄這點，官方頁寫法偏向如此，要實測。
- 驗法：在一個拋棄式 repo（main 先做一個不推的 commit）：`claude --bg --worktree t1 --name t1 "<一句話任務>"` → `git worktree list` 有 `.claude/worktrees/t1`、`git merge-base --is-ancestor <未推 commit> worktree-t1` 成立、全程無信任提示；在該 session 叫它 Edit 主檢出的檔應被拒；`claude rm <id>` 後乾淨 worktree 被移除。
- 分級：A

### P8. Claude 對 Claude 的檔案信箱（root-link、tri-link、`to-opus`／`to-fable`）改走原生 SendMessage；檔案只留給要存案卷或跨人、跨模型的地方
- 官方機制：同機 session 互傳走每個 session 的具名管道（Windows），不經 Anthropic 伺服器；純文字、單則約一百萬字元上限、自動防迴圈；收件人用名字定址（頁：[cross-session-messaging](../../../ClaudeCodeInternals/Docs/02-build/cross-session-messaging.md)「訊息傳送至其他機器上的工作階段」「限制」；v2.1.224，原生 Windows v2.1.234）
- 現況：卡片 `並行llm即時通訊-inbox機制`（`~/.grok/.ai-inbox/to-opus`、`to-fable` 一信一檔、Monitor 2 秒喚醒）、`根層與專案session對齊認知用root-link雙槽與tri-link三槽信箱-落專案inbox`（2026-10-07；落專案目錄是為了避開根層寫入保護閘）；MultiSession §5「信箱協議」；現況對帳 §4.2。
- 落差／機會：「發現對方、送達、叫醒、回覆地址」原生都有，而且不寫任何檔，連「誰能寫進誰的目錄」的保護閘問題都消失。檔案信箱真正剩下的價值只有兩個：留下一份可翻的案卷、跟不是 Claude Code 的對象（Grok、別的人）溝通。
- 做法：改寫法。MultiSession §5 信箱協議段改成「Claude 對 Claude 用 SendMessage（對方用 P2 的固定名字）；要留案卷時由收件方把全文存檔」；root-link 卡 append 這個結論；`to-opus`／`to-fable` 槽在 `PROTOCOL.md` 標退場。保留：`to-grok`／`to-claude`（Grok 不是 Claude Code）、`mailbox` skill（跨人跨帳號，見「原生仍做不到」）。
- 代價與風險：訊息只存在 transcript，30 天後隨清理消失（見 P12）；每則信開一個回合、跑一次記憶注入；P1 要先做，否則計畫模式的一方會掉信。
- 驗法：下一次根層與專案對齊改用 SendMessage 進行：結束後專案 `.claude/inbox/` 沒有新檔、雙方 transcript 各有往返紀錄；或用兩個 `--bg` session 腳本化跑三輪問答。
- 分級：A

### P9. CC 新增的執行期資料夾落在 `~/.claude` repo 裡：補 `.gitignore`、掃描工具排除
- 官方機制：agent teams 寫 `~/.claude/teams/{team}/`（config、inboxes）；Desktop 本機排程寫 `~/.claude/scheduled-tasks/<名>/SKILL.md`；背景 session 暫存 `~/.claude/jobs/<id>/tmp/`；原生 worktree 在 `<repo>/.claude/worktrees/`；使用者層保存的 workflow 在 `~/.claude/workflows/`（頁：[agent-teams](../../../ClaudeCodeInternals/Docs/02-build/agent-teams.md)「架構」、[desktop-scheduled-tasks](../../../ClaudeCodeInternals/Docs/01-getting-started/desktop-scheduled-tasks.md)「管理排程任務」、[agent-view](../../../ClaudeCodeInternals/Docs/02-build/agent-view.md)「狀態存儲位置」、[workflows](../../../ClaudeCodeInternals/Docs/02-build/workflows.md)「保存工作流程以供重複使用」）
- 現況：`.gitignore` 已有 `tasks/`、`jobs/`、`daemon/`、`daemon.log`、`.claude/*`；**沒有** `teams/`、`scheduled-tasks/`（`git check-ignore` 實測）。另在 `jobs/0871da8d/tmp/headtree/` 實際看到一份背景 session 留下的整棵 hooks 程式副本，對 repo 根 `grep -r` 會掃到它。vcs-sync 的 `git add -A -f` 帶路徑清單（[`hooks/wg_vcs_sync.py`](../../../../hooks/wg_vcs_sync.py)），不會把這些自動上傳，問題只在「上GIT」選擇性 staging 時多出雜訊。
- 落差／機會：`~/.claude` 同時是 CC 設定目錄與我們的 repo，CC 每加一種執行期資料夾就會長在 repo 裡。
- 做法：相容修正。`.gitignore` 加 `teams/`、`scheduled-tasks/`；`workflows/` 先不加（將來保存的 workflow 是該跨機同步的資產）；檢查從 repo 根遞迴的工具（例 `tools/atom-health-check.py` 的檔名掃描、`tools/check-bypass.py`）有沒有排除 `jobs/`、`.claude/worktrees/`。
- 代價與風險：幾乎沒有；`scheduled-tasks/` 若之後想跨機共用提示詞，要改成進版控（排程與啟用狀態本來就不在檔裡）。
- 驗法：`git check-ignore -v teams/x scheduled-tasks/x/SKILL.md` 都有命中；建空資料夾後 `git status --porcelain` 乾淨。
- 分級：C

### P10. 跨 session 同檔預警保留，但警告附上對方的 session 名稱，讓 Claude 能直接傳訊協調
- 官方機制：`claude agents --json` 給每個活 session 的 `sessionId`、`name`、`cwd`；跨 session 訊息讓 Claude 在「我的改動會弄壞別人」時主動警告對方——但是否警告由 Claude 自己判斷，原生沒有撞檔偵測（頁：[agent-view](../../../ClaudeCodeInternals/Docs/02-build/agent-view.md)「將工作階段列為 JSON」、[cross-session-messaging](../../../ClaudeCodeInternals/Docs/02-build/cross-session-messaging.md)「何時使用」；`agents --json` v2.1.145）
- 現況：[`hooks/wg_coordination.py`](../../../../hooks/wg_coordination.py) 在動到別的活 session 改過的檔、或下 `git add -A` 這類收尾指令時 warn-only，訊息只帶短 session id；模型看不出那是哪個分頁。
- 落差／機會：原生只隔離「各在各 worktree」的 session，同一工作樹的撞檔仍只有我們偵測得到；但原生現在有通訊錄，可以讓這個警告「接下來能做事」。
- 做法：接上新能力。警告觸發時（只在觸發時，不是每次 Write）跑一次 `claude agents --json`，用 `sessionId` 對出對方名字，訊息改成「`<名字>` 也改過這個檔，可 SendMessage 告知」；失敗就退回現在的短 id（fail-open＋stderr）。MultiSession §5 的「拿時間去比」同時刪掉。
- 代價與風險：本機實測 `claude agents --json` 一次約 0.55–0.6 秒，PreToolUse 預算 5 秒內可接受，但只能放在觸發分支裡；名字要靠 P2 才有意義。
- 驗法：兩個 session 改同一檔，第二個收到的警告含第一個的名字；計時帳 `guard-hook_timing.jsonl` 該段不超過 1 秒。
- 分級：B

### P11. 拆掉實驗性 auto-continue watcher，「長任務自動續跑」交給 `/goal`
- 官方機制：`/goal <完成條件>` 是 session 範圍、以提示詞判定的 Stop hook：每回合後由小模型判斷條件達成沒，沒達成就自動開下一回合；有背景工作時延後評估並定期簽到；`--resume` 會還原進行中的 goal；`claude -p "/goal …"` 也能跑完整迴圈（頁：[goal](../../../ClaudeCodeInternals/Docs/02-build/goal.md)；v2.1.139，resume 還原 v2.1.239，閒置簽到上限 v2.1.246）
- 現況：`tools/auto-continue/auto_continue.py`（v6.1 已刪） 自標「實驗性、非正式上線」：監看 `next-phase*.md`、一棒接一棒起 `claude -p "/continue"`，四道護欄（連續數、成本、人工確認點、kill switch）；TECH 與 `settings.json` 都沒引用它（grep 零筆）。
- 落差／機會：「朝可驗證條件持續工作、不用人每步催」原生已經有，而且在同一個 session 內靠自動壓縮續命；watcher 靠 `-p` 載入 skill，P6 的 bare 預設一翻就失效。
- 做法：直接換用原生。`tools/auto-continue/` 移到封存（連同 verify），CHANGELOG 記一筆；`handoff`／`continue` skill 保留（理由見「原生仍做不到」）。
- 代價與風險：失去「context 滿了自動換新 session」——由自動壓縮取代；`/goal` 要人打（模型不會自己設），而且 `disableAllHooks` 為 true 時不可用（我們沒設）。
- 驗法：grep 確認無呼叫者；在拋棄式 repo 跑 `claude -p "/goal test/ 下的測試全過" --output-format stream-json --verbose`，看迴圈以「已達成」結束。
- 分級：A

### P12. 把 transcript 保留期從預設 30 天拉長，讓卡片來源回看、日誌與 episodic 有原文可查
- 官方機制：`cleanupPeriodDays` 決定 transcript、子代理 transcript、任務清單、背景／子代理 worktree 的保留天數，預設 30（頁：[settings-reference](../../../ClaudeCodeInternals/Docs/05-configuration/settings-reference.md) `cleanupPeriodDays`、[sessions](../../../ClaudeCodeInternals/Docs/01-getting-started/sessions.md)「逐字稿儲存位置」；TIMELINE 記 `cleanupPeriodDays: 0` 改為驗證失敗、清掃涵蓋 tasks 等）
- 現況：`settings.json` 沒設（現況對帳 §2.1「沒用到的鍵」）。`memory/` 底下有 109 個 md 檔寫著「原對話已逾保留期」；[`atom-source`](../../../../skills/atom-source/SKILL.md) skill 遇到就只能回 unrecoverable。`projects/` 目前約 2.0 GB、近 30 天 878 個 jsonl（本機實測）。
- 落差／機會：系統核心目標是「該想起的要完整送到」，卡片的 Source 指回對話，卻在 30 天後失效；一個鍵就能延長。
- 做法：接上新能力。`settings.json` 加 `"cleanupPeriodDays": 90`（建議值；照目前速度約多 4 GB）。
- 代價與風險：磁碟；子代理與背景 session 的 worktree 掃描也跟著變慢清（留得更久）；多台機器各自保留，不同步。
- 驗法：設定後 90 天內任一張新卡跑 `/atom-source` 能撈到原句；`du -sh projects` 每週記一次確認成長在預期內。
- 分級：B

### P13. `/rewind` 與「Summarize from／up to here」會讓對話倒退，但我們的 state 不退（先跑探針）
- 官方機制：倒轉選單可只還原對話、只還原程式碼或兩者，也能把某點前或後的對話壓成摘要；PreCompact／PostCompact 的 matcher 只列 `manual`（`/compact`）與 `auto`，倒轉與部分摘要有沒有觸發任何 hook 官方頁沒寫（頁：[checkpointing](../../../ClaudeCodeInternals/Docs/06-reference/checkpointing.md)「倒轉與摘要」、[hooks](../../../ClaudeCodeInternals/Docs/06-reference/hooks.md) PreCompact；「Summarize up to here」v2.1.141）
- 現況：`workflow/state-<sid>.json` 記「已注入卡名單」做去重、記改檔帳給同步閘用；壓縮後的補送只掛在 PreCompact→PostCompact→PostToolBatch（現況對帳 §5）；卡片 `claude-code的resume接續後前面回合hook注入的內容仍在context-只有壓縮才丟…` 只涵蓋 resume 與壓縮。
- 落差／機會：倒轉或部分摘要會把當時注入的卡從 context 拿掉，state 卻還記得「送過了」，同一主題再問時不會再送（未實測）；還原程式碼後改檔帳也還記著已被還原的檔，同步閘可能催 commit 一個其實沒變的檔。注入細節屬 01 面向，這裡記的是「接續」這一側的落差。
- 做法：改寫法避衝突。先實測；證實後在 UPS 的前置閘偵測「本回合 prompt 接的不是上一回合最後一則」（倒轉的特徵），視同壓縮清掉 `injected_atoms`，並用 `git status` 重新校對改檔帳。
- 代價與風險：偵測規則可能把正常分支誤判成倒轉（多送一次卡，代價小）；倒轉是互動操作，自動化測試只能做重播。
- 驗法：手動探針約 2 分鐘：觸發一張卡 → `/rewind` 選「Restore conversation」退到觸發前 → 再問同一句，看 `Logs/injection-turns.jsonl` 該卡有沒有再送；同樣測一次「Summarize from here」。
- 分級：C

### P14. 全庫型稽核寫成保存的 dynamic workflow（`~/.claude/workflows/`）
- 官方機制：Claude 寫的 JS 協調腳本，中間結果留在腳本變數不進 context，最多 16 個 agent 並行、同 session 內可續跑、可做對抗式交叉檢查；保存到 `~/.claude/workflows/` 後每個專案可用（頁：[workflows](../../../ClaudeCodeInternals/Docs/02-build/workflows.md)；v2.1.154，並行上限可調 v2.1.269）
- 現況：大量判斷型工作靠主對話派子代理或 `wg_research` 的 fan-out 建議；MultiSession §7「驗收判分開乾淨 context 的 agent 與第二意見各判一次」是人工流程。
- 落差／機會：「幾百張卡逐張判斷再交叉比對」這種工作，workflow 比主對話逐輪派子代理省 context；保存的腳本在我們 repo 裡，可跨機同步。
- 做法：接上新能力，但現在不做。條件：① 01 面向確認 workflow 起的 agent 收不收得到 `[WG:SubagentMemory]`（它們不是經 Agent 工具起的，PreToolUse 可能攔不到，官方頁未寫）；② 出現一個真的需要二十個以上 agent 的稽核需求。
- 代價與風險：token 倍增（官方警告）；workflow 中途不能問人。
- 驗法：條件成立後，拿一個小範疇（例：一個 Lv1 範疇的卡）試跑，比較與現行做法的 token 與結論差異。
- 分級：D

### P15. 跨機器 session 互傳（Remote Control）讓多台機器的 session 互通
- 官方機制：連上 Remote Control 的 session 可以 ListAgents 到你另一台機器上的 session 並傳訊，經 Anthropic 伺服器，`isolatePeerMachines` 可要求逐則核准（頁：[cross-session-messaging](../../../ClaudeCodeInternals/Docs/02-build/cross-session-messaging.md)「訊息傳送至其他機器上的工作階段」、[remote-control](../../../ClaudeCodeInternals/Docs/01-getting-started/remote-control.md)；跨機開對話 v2.1.225）
- 現況：多機共享靠 git 同步 atom 原文與索引（USER.md「多機共享」、vcs-sync worker）。
- 落差／機會：可以讓 A 機在推完新卡後通知 B 機的活 session「去拉」；但 vcs-sync 已在 SessionStart 拉取，價值小。
- 做法：不做。真要做時只當「通知」，不取代 git。
- 代價與風險：每台都要 claude.ai 登入並連 Remote Control；訊息不留檔。
- 驗法：—
- 分級：D

---

## 原生仍做不到、該保留的自製

| 自製 | 為什麼原生替不了（依據） |
|---|---|
| `mailbox` skill（網路共用資料夾，跨人、企劃寄需求單給程式） | 原生傳訊只到「你自己的」session：同機要同一 OS 使用者（Windows 具名管道要本人金鑰），跨機要同一 claude.ai 帳號連 Remote Control（[cross-session-messaging](../../../ClaudeCodeInternals/Docs/02-build/cross-session-messaging.md)「工作階段的收件匣套接字」「可用性」） |
| `~/.grok/.ai-inbox/to-grok`、`to-claude` | 對象不是 Claude Code，沒有收件匣 |
| `wg_coordination` 同工作樹撞檔預警 | 原生只隔離 worktree 裡的 session；同一工作樹誰改了什麼沒有偵測（[worktrees](../../../ClaudeCodeInternals/Docs/02-build/worktrees.md)、[agents](../../../ClaudeCodeInternals/Docs/02-build/agents.md)「任務是否涉及相同的檔案」）。保留並做 P10 |
| `handoff`／`continue` 交接單 | 原生 `--resume` 只在同一台機器、transcript 30 天後清掉；交接單是人讀得懂、跨機器可讀、經過整理的版本 |
| `/console` 的派工單、對帳、合併、推送規矩 | agent view 只給狀態，不管「哪些檔能動、怎麼對帳、怎麼合」；agent teams 不隔離 worktree（[agents](../../../ClaudeCodeInternals/Docs/02-build/agents.md)）。保留，但做 P1、P2、P3、P5、P7 減掉繞道儀式 |
| 收尾閘的擋次預算 | 見下「不建議做的」第 3 條 |

## 不建議做的

1. **用 agent teams 取代 `/console` 多軌**：實驗性、要環境變數開；隊友不隔離 worktree（我們多軌的主要價值）、`-p` 生不出隊友、`/resume` 不還原 in-process 隊友、一個 session 一隊；而且一開，Claude 自己命名的子代理會靜默變成隊友（[agent-teams](../../../ClaudeCodeInternals/Docs/02-build/agent-teams.md)「限制」「Claude 生成隊友而非子代理」）。`TeammateIdle`／`TaskCreated`／`TaskCompleted` 這三個 hook 也因此不必接。
2. **把 Windows 工作排程器的週健檢、用量監控、週截圖搬到 Desktop 排程、routines 或 `/loop`**：這些是固定流程的 Python 腳本，換成排程 Claude session 每次都要花 token；Desktop 本機排程要 app 開著、電腦醒著，睡著就跳過、補跑只補一次；routines 在雲端碰不到本機檔；`/loop` 要 session 開著且 7 天過期（[desktop-scheduled-tasks](../../../ClaudeCodeInternals/Docs/01-getting-started/desktop-scheduled-tasks.md)「比較排程選項」「錯過的執行」、[scheduled-tasks](../../../ClaudeCodeInternals/Docs/02-build/scheduled-tasks.md)「七天過期」）。
3. **用原生「連續 8 次續跑上限」取代自管擋次預算**：原生計數在 Claude 每次呼叫工具時歸零（[hooks](../../../ClaudeCodeInternals/Docs/06-reference/hooks.md)「Stop 輸入」），擋不住「修一下、又說完成」的循環；我們「每個使用者回合、每道閘各自計次，擋滿問人或留帳」才是要的語意。保留 `lang_guard` 對 `stop_hook_active` 的用法即可。
4. **用 channels 把共用信箱或檔案信箱推進 session**：研究預覽、每個 session 都要用 `--channels` 啟動、自製 channel 還要 `--dangerously-load-development-channels` 與 Bun（[channels](../../../ClaudeCodeInternals/Docs/02-build/channels.md)）；mailbox 是跨人的非即時溝通，Monitor 已有 2 秒級喚醒。
5. **用 Agent SDK 的 `sessionStore` 解決 transcript 保留或跨機共享**：它只鏡像「SDK 跑的」session，互動 session 照樣寫 `~/.claude/projects/` 照樣 30 天清（[agent-sdk__session-storage](../../../ClaudeCodeInternals/Docs/07-agent-sdk/agent-sdk__session-storage.md)）；保留期用 P12 一個鍵就好。

## 附註：現況對帳表與文件需要更正的地方

- 對帳表 §6 #13 寫「need-goal」：現行 `hooks/` 已無 `wg_need_goal` 模組，只剩 `_shared.py` 的執行期資料清理項與 `wg_release_rules.py` 的目錄名（`jobs/*/tmp/headtree/` 裡的是舊副本），可視為已退役。
- [MultiSession §5](../../../MultiSessionCollaboration.md)「ListAgents 名字跟 session id 對不上，拿 transcript 第一筆時間去比」已過時：`claude agents --json` 直接給 `sessionId`＋`name`（本機實測），`console-spawn.py` 也已經這樣用。
- MultiSession §2「子代理收不到跨 session 的 SendMessage」仍成立，但同 session 內具名子代理之間可以互傳、完成後可用 SendMessage 續用（[sub-agents](../../../ClaudeCodeInternals/Docs/02-build/sub-agents.md)「恢復 subagents」），寫派工時別把「子代理不能通訊」講得太滿。

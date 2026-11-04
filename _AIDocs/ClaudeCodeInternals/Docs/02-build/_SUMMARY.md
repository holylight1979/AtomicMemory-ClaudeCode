# 02-build 導讀（Build with Claude Code，22 頁）

> 依官方 subsection 分組；原文在同資料夾，本檔為高速導讀。

## Agents and parallel work

### 建立自訂 subagents（`sub-agents`）
- 檔案：[sub-agents.md](sub-agents.md)｜https://code.claude.com/docs/zh-TW/sub-agents｜lastmod 2026-11-03｜111KB
- 一句話：定義並使用自訂 subagent：獨立 context、專屬工具與權限的委派工作者。
- 何時讀：想把搜尋／審查等側任務移出主對話，或要寫 .claude/agents/*.md 時。
- 關鍵內容：
  - 內建 Explore（唯讀、quick/medium/very thorough）、Plan、General-purpose
  - 範圍優先序：受管設定 > --agents > .claude/agents > ~/.claude/agents > plugin
  - frontmatter：name、description、tools、disallowedTools、model、permissionMode、maxTurns
  - 另有 skills、mcpServers、hooks、memory、background、isolation: worktree、omitClaudeMd、effort
  - description 合計超過 15,000 tokens 會被警告；並行預設上限 20 個
  - /subtask 或 fork 模式：子代理繼承整段對話而非從零開始
  - SubagentStart／SubagentStop 為 settings.json 層級 hook 事件，可依 agent 名稱 matcher
  - Claude 讀 subagent 報告前會做輸出掃描（反斜線插入／標記疑似注入文字）
- 新名詞：`subagent` ＝ 在主工作階段內、自有 context 執行並回報摘要的委派工作者；`fork（/subtask）` ＝ 繼承目前整段對話的子代理，放棄輸入隔離換取上下文；`memory 欄位（user/project/local）` ＝ 給子代理的持久目錄，跨對話累積知識；`omitClaudeMd` ＝ 啟動時不載入 CLAUDE.md 的子代理選項
- 記憶系統接點：非 fork 子代理會載入 CLAUDE.md 與 git 快照，但不載入主對話的自動記憶與輸出風格（Explore/Plan 連 CLAUDE.md 都跳過）；frontmatter memory 目錄為 ~/.claude/agent-memory/<name>/ 等，屬自動記憶一部分；子代理可用 frontmatter hooks，專案層需先信任資料夾；SubagentStart/Stop 可掛 settings hook。

### 平行執行代理（`agents`）
- 檔案：[agents.md](agents.md)｜https://code.claude.com/docs/zh-TW/agents｜lastmod 2026-10-30｜9KB
- 一句話：比較五種平行執行方式：子代理、agent view、agent teams、動態工作流程、專案。
- 何時讀：不確定該用哪種平行／委派機制，或想找查看執行中工作的指令時。
- 關鍵內容：
  - 五法：subagents／agent view（claude agents）／agent teams（實驗）／workflows／projects
  - 三個輔助工具：worktrees（隔離檔案）、跨 session 訊息、/batch（5～30 個 worktree 子代理）
  - 選法三問：誰協調？工作者要互談嗎？會改同檔嗎？
  - 查看指令：claude agents、/tasks、/workflows；/agents 只指向 subagent 檔位置
  - 同時多 session 或 subagent 會倍增 token 用量
- 新名詞：`/batch` ＝ 把大變更拆成 5～30 個 worktree 隔離子代理的內建 skill；`分叉子代理` ＝ 繼承完整對話的子代理，用 /subtask 啟動
- 記憶系統接點：總覽頁；指出 agent teams 隊友彼此直接傳訊、agent view 工作階段只向使用者回報，跨 session 傳遞靠 cross-session messaging；agent teams 不隔離 worktree，需自行切分檔案。

### 協調 Claude Code 工作階段團隊（`agent-teams`）
- 檔案：[agent-teams.md](agent-teams.md)｜https://code.claude.com/docs/zh-TW/agent-teams｜lastmod 2026-11-03｜41KB
- 一句話：實驗功能：一個 lead 協調多個隊友 Claude session，共用任務清單與信箱。
- 何時讀：需要多個長時間 session 互相討論、認領任務（研究、審查、跨層開發）時。
- 關鍵內容：
  - 啟用：env CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1（預設關）
  - 顯示模式 teammateMode：in-process／auto／tmux／iterm2，旗標 --teammate-mode
  - 存放：~/.claude/teams/{team}/config.json、inboxes/{agent}.json、~/.claude/tasks/{team}/
  - 任務三態 pending/in progress/completed，認領用檔案鎖防競爭
  - hooks：TeammateIdle、TaskCreated、TaskCompleted，exit 2 阻擋並回饋
  - 限制：每 session 一個 team、無巢狀、lead 固定、/resume 不恢復 in-process 隊友
  - 隊友模型順序：提示指定 > subagent 定義 model > CLAUDE_CODE_SUBAGENT_MODEL > lead
  - 隊友繼承 lead 權限模式，生成時不能個別設定
- 新名詞：`agent team` ＝ 由 lead 與多個隊友 session 組成、共享任務清單的團隊（實驗）；`lead／teammate` ＝ 主管 session／被生成的獨立 Claude Code 實例；`信箱（inbox）` ＝ 每個 agent 一個 JSON 檔，寫入成功才算訊息送出；`team-lead` ＝ config.json 內 lead 的 agent 類型
- 記憶系統接點：團隊狀態全落地在 ~/.claude/teams 與 ~/.claude/tasks（可被外部程式讀）；TeammateIdle／TaskCreated／TaskCompleted 三個 hook 可用 exit 2 把關；隊友是完整 session，會載入專案／使用者設定（含 CLAUDE.md、hooks）；以 subagent 定義生成隊友時 skills 與 mcpServers 部分欄位不套用。

### 使用 Agent view 管理多個代理（`agent-view`）
- 檔案：[agent-view.md](agent-view.md)｜https://code.claude.com/docs/zh-TW/agent-view｜lastmod 2026-11-03｜145KB
- 一句話：claude agents：一個畫面分派、監看、回覆多個背景 Claude session。
- 何時讀：想同時交辦多個獨立任務、只在需要你時介入，或要從 shell 管背景 session。
- 關鍵內容：
  - 開啟：claude agents；分派：輸入框每個 prompt 開一個新 session
  - shell 分派：claude --bg "…"（不可與 -p 合用）、/bg、空提示按 ←
  - 狀態：Working／Needs input／Idle／Completed／Failed／Stopped
  - 管理：claude attach|logs|stop|respawn|rm <id>、claude daemon status|logs|stop
  - claude agents --json：state 為 working／blocked／done／failed／stopped
  - supervisor 背景服務託管 session；狀態在 ~/.claude/jobs/、日誌 ~/.claude/daemon.log
  - 編輯前自動移入 .claude/worktrees/；worktree.bgIsolation: "none" 可關閉
  - 未連接且閒置約一小時，supervisor 會停止該程序以釋放資源（對話保留）
- 新名詞：`agent view` ＝ claude agents 開啟的背景 session 總覽畫面（研究預覽）；`背景工作階段` ＝ 由 supervisor 託管、關閉終端機仍繼續跑的 session；`supervisor` ＝ 託管背景 session 的獨立背景服務；`CLAUDE_JOB_DIR` ＝ 背景 session 自己可寫報告檔的目錄環境變數
- 記憶系統接點：每個背景 session 都是獨立 Claude Code 程序，用同一份憑證；外部（狀態列、排程器、另一個 Claude）應用 claude agents --json 讀狀態，~/.claude/jobs/ 檔案不是穩定介面；背景 session 預設進 worktree，非 git 目錄且無 WorktreeCreate hook 則不隔離。

### 使用動態工作流程大規模協調子代理（`workflows`）
- 檔案：[workflows.md](workflows.md)｜https://code.claude.com/docs/zh-TW/workflows｜lastmod 2026-10-27｜43KB
- 一句話：動態工作流程：Claude 寫 JavaScript 腳本，由腳本大規模協調許多子代理並交叉驗證。
- 何時讀：任務大到一個對話協調不了（全庫審計、500 檔遷移、交叉檢查研究）時。
- 關鍵內容：
  - 內建 /deep-research <問題>；/workflows 開進度檢視（鍵：p 暫停、x 停止、r 重啟、s 儲存、f 篩選）
  - 觸發：提示含關鍵字 ultracode，或 /effort ultracode（同時設 xhigh）
  - 儲存為命令：.claude/workflows/（專案共享）或 ~/.claude/workflows/（個人）
  - plugin 根目錄 workflows/ 內腳本以 /<plugin>:<name> 執行；腳本讀全域 args
  - 並行上限 16 個 agent，可由 CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS 調整
  - 排程超過 25 個 agent 或預估超過 150 萬 token 顯示 Large workflow 警告
  - 權限：規則 Workflow 或 Workflow(<name>)；auto 模式僅首次詢問；-p 不詢問
  - 關閉：CLAUDE_CODE_DISABLE_WORKFLOWS=1；可暫停後在同 session 恢復
- 新名詞：`dynamic workflow` ＝ 由腳本而非 Claude 逐輪決定下一步的多代理協調；`ultracode` ＝ 啟用自動工作流程協調的 effort 設定／提示關鍵字；`/deep-research` ＝ 內建工作流程：多角度搜尋並投票驗證後出引用報告；`args` ＝ 保存的工作流程接收呼叫輸入的全域變數
- 記憶系統接點：中間結果存在腳本變數而非 Claude 的 context window；PreToolUse hook 回傳 allow 可核准 Workflow 呼叫；工作流程產生的子代理走同一套 permission 規則；專案層 .claude/workflows/ 隨版控共享，與 plugin 名稱空間分發；排程任務、webhook 內容不會觸發 ultracode 關鍵字。

### 訊息傳送至您的其他 Claude Code 工作階段（`cross-session-messaging`）
- 檔案：[cross-session-messaging.md](cross-session-messaging.md)｜https://code.claude.com/docs/zh-TW/cross-session-messaging｜lastmod 2026-10-27｜35KB
- 一句話：Claude 能列出並傳訊給你其他 Claude Code session（本機、他機、雲端）。
- 何時讀：多個 session 同時工作需互通發現／狀態，或想控制／關閉入站訊息時。
- 關鍵內容：
  - 工具：ListAgents 與 SendMessage；命令 /list-agents（別名 /peers）；@名稱 提及目標
  - SendMessage 的 notify_when_idle：目標閒置或退出時回報，12 小時未到即丟棄
  - 入站設定 crossSessionInbound：accept／hold／refuse；hold 最多保留 100 則
  - 出站控制：permissions.deny 加 SendMessage、ListAgents；isolatePeerMachines 跨機前要批准
  - 本機走 Unix socket／Windows 具名管道，不經 Anthropic；跨機經 Remote Control／雲端
  - env CLAUDE_CODE_MESSAGING_SOCKET、CLAUDE_CODE_MESSAGING_TOKEN 匯出給 hooks 與 Bash（含 SessionStart）
  - 訊息不能核准權限、不能改設定、內含命令不執行；單則約上限一百萬字元
  - 版本：macOS／Linux v2.1.224+，原生 Windows v2.1.234+；dialogExpiry 控制保留訊息逾時
- 新名詞：`cross-session messaging` ＝ Claude 之間以文字訊息互傳的功能，不傳對話歷史；`收件匣 socket` ＝ 每個 session 綁定、供其他 session 投遞訊息的通訊端；`notify_when_idle` ＝ 訂閱目標 session 下次閒置時通知的 SendMessage 輸入；`hold` ＝ 入站訊息擱置待使用者核准
- 記憶系統接點：腳本或 hook 可用 CLAUDE_CODE_MESSAGING_SOCKET 與 TOKEN 直接向自己的 session 投遞訊息（自有子程序可被驗證而免核准）；SessionStart 之前環境變數已匯出；訊息被標示為來自其他 session 而非使用者；管理員可用受管設定整體關閉。

### 使用 worktrees 執行平行會話（`worktrees`）
- 檔案：[worktrees.md](worktrees.md)｜https://code.claude.com/docs/zh-TW/worktrees｜lastmod 2026-11-02｜43KB
- 一句話：用 git worktree 為每個平行 session 提供獨立檔案與分支，避免互撞。
- 何時讀：要同時跑多個 session 改同一 repo，或設定子代理／背景 session 的 worktree 隔離。
- 關鍵內容：
  - claude --worktree <名>（-w）建於 .claude/worktrees/<名>；省略名稱會自動產生
  - 清理：乾淨的未命名 worktree 退出時自動刪；有變更則詢問保留或移除；-p 不清理
  - 子代理 frontmatter isolation: worktree；EnterWorktree／ExitWorktree 工具
  - .worktreeinclude（gitignore 語法）把 .env 等 gitignored 檔複製進新 worktree
  - 強制隔離四檢查：檔案編輯、命令工作目錄、git 重定向、命令形狀
  - WorktreeCreate／WorktreeRemove hook 可取代 git 邏輯（支援非 git VCS）
  - 共享：.git 目錄、專案層 plugin、權限核准（存主檢出 settings.local.json）
  - 恢復 session 會回到原 worktree；已刪除則在啟動目錄恢復並告知
- 新名詞：`git worktree` ＝ 同 repo 另一個獨立工作目錄＋分支；`worktree 隔離` ＝ 阻止隔離 session 寫入主檢出的工具檢查；`.worktreeinclude` ＝ 指定要複製進新 worktree 的 gitignored 檔案清單
- 記憶系統接點：進入 worktree 後 hook 的 ${CLAUDE_PROJECT_DIR} 不變、輸入 JSON 的 cwd 跟著走；「是，不再詢問」的權限規則寫到主檢出 .claude/settings.local.json；worktree 缺 .claude/skills|agents|commands 時從主檢出讀；WorktreeCreate hook 可完全接管建立。

## Artifacts

### 將工作階段輸出分享為成品（`artifacts`）
- 檔案：[artifacts.md](artifacts.md)｜https://code.claude.com/docs/zh-TW/artifacts｜lastmod 2026-10-30｜41KB
- 一句話：把 session 產出發佈成 claude.ai 上的互動網頁（artifact），可私人、組織內或公開分享。
- 何時讀：輸出用圖表／差異導覽／儀表板比純文字更好讀，或要傳連結給同事時。
- 關鍵內容：
  - Claude 自動或依要求發佈到 claude.ai 私人 URL；再次發佈更新同一 URL（版本化）
  - /artifacts 列出／附加／開啟／複製／刪除（Enter／o／c／d）
  - 來源檔限 .html／.htm／.md（UTF-8），渲染後 ≤16 MiB；單頁無後端；CSP 嚴格
  - 可用 MCP 連接器在檢視時取即時資料，並可宣告檔案下載
  - 組織內可留評論並讓 Claude 讀取／回覆（傳送給 Claude）
  - plan mode、宣告執行階段功能、已公開、排程回合發佈時，發佈前會先詢問
  - 關閉：enableArtifact: false、CLAUDE_CODE_DISABLE_ARTIFACT=1、permissions.deny 加 Artifact
  - 管理員可管：啟停、連接器、公開分享、保留政策、稽核日誌、Compliance API
- 新名詞：`artifact（成品）` ＝ 從 session 發佈的自包含互動網頁；`連接器呼叫` ＝ 頁面透過 MCP 連接器在檢視者開啟時取資料；`enableArtifact` ＝ 關閉／開啟 artifact 功能的設定鍵
- 記憶系統接點：需 /login 的 claude.ai 帳號登入；排程任務觸發的 session 回合發佈 artifact 會被詢問；artifact 由工作階段檔案重新發佈，可從別的 session 以 URL 或 /artifacts 接手更新。

## Automation

### 讓 Claude 朝著目標持續工作（`goal`）
- 檔案：[goal.md](goal.md)｜https://code.claude.com/docs/zh-TW/goal｜lastmod 2026-10-29｜15KB
- 一句話：/goal 設完成條件，Claude 每回合後由小模型檢查，沒達成就自動續跑。
- 何時讀：有可驗證終點的長任務（遷移到測試全綠、清空佇列），想免逐步提示時。
- 關鍵內容：
  - 用法：/goal <條件>（≤4,000 字元）、/goal 看狀態、/goal clear（別名 stop/off/reset/none/cancel）
  - 實作：session 範圍的 prompt-based Stop hook；評估模型讀對話，不自己跑指令
  - 三判決：尚未達成（續跑）／已達成／不可能（皆自動清除）
  - 連續多回合沒用工具視為空轉，停止迴圈並把控制權還給你
  - 清除目標的錯誤：驗證失敗、額度耗盡、壓縮無法解的 context 溢位、模型不可用
  - 背景工作未結束則跳過評估；30 分鐘簽到，CLAUDE_CODE_GOAL_CHECKIN_MINUTES=0 關閉簽到與自動重試
  - --continue／--resume 會復原未完成的目標，但計數歸零；claude -p "/goal …" 可無人值守
  - disableAllHooks 為 true 時 /goal 不可用；評估模型取 ANTHROPIC_DEFAULT_HAIKU_MODEL
- 新名詞：`/goal` ＝ 設定完成條件並自動續跑直到達成的命令；`評估器（evaluator）` ＝ 每回合後判定條件是否滿足的小型快速模型；`簽到（check-in）` ＝ 背景工作拖過 30 分鐘時要 Claude 檢查任務狀態的機制
- 記憶系統接點：/goal 就是 session 範圍的 Stop hook，與 settings 內的 Stop hook 同在每回合後觸發；Stop hook 連續阻擋 8 次會被覆寫（hooks-guide）；goal 隨 session resume 還原；受 disableAllHooks 與工作區信任同一套規則限制。

### 使用 channels 將事件推送到執行中的工作階段（`channels`）
- 檔案：[channels.md](channels.md)｜https://code.claude.com/docs/zh-TW/channels｜lastmod 2026-10-30｜23KB
- 一句話：Channel 是把外部事件（聊天、CI、webhook）推進執行中 session 的 MCP 伺服器。
- 何時讀：想讓 Claude 在你離開終端時回應 Telegram／Discord／iMessage 訊息或 webhook。
- 關鍵內容：
  - 啟用：claude --channels plugin:<name>@<marketplace>；.mcp.json 本身不夠
  - 內建預覽外掛：telegram、discord、imessage、fakechat（需 Bun；/plugin install …@claude-plugins-official）
  - 寄件者允許清單：配對碼 /telegram:access pair，再 policy allowlist；非名單者靜默丟棄
  - 事件進模型時為 <channel source=…> 標籤；回覆出現在原聊天而非終端
  - 管理員設定：channelsEnabled、allowedChannelPlugins（Team/Enterprise 預設封鎖）
  - 開發測試旗標 --dangerously-load-development-channels；兩旗標都不在 --help 列出
  - 需 claude.ai 或 Console API key 認證；Bedrock／Vertex／Foundry 不支援；研究預覽
  - 權限提示會卡住 session，除非 channel 宣告 permission relay
- 新名詞：`channel` ＝ 可雙向的 MCP 伺服器，把外部事件推到執行中的 session；`配對（pairing）` ＝ 用機器人回覆的代碼把你的帳號 ID 加入允許清單；`permission relay` ＝ channel 把權限提示轉發到聊天上批准的能力
- 記憶系統接點：事件以 <channel> 標籤直接進 session 對話，而非由 hook 注入或輪詢；與 scheduled-tasks 的輪詢互補；-p 模式下需終端輸入的工具（多選題、plan 核准）被停用；設定落在 ~/.claude/channels/<name>/.env。

### 按排程執行提示（`scheduled-tasks`）
- 檔案：[scheduled-tasks.md](scheduled-tasks.md)｜https://code.claude.com/docs/zh-TW/scheduled-tasks｜lastmod 2026-10-22｜20KB
- 一句話：用 /loop 與 cron 工具在開啟的 session 內排程重複或一次性提示。
- 何時讀：要輪詢部署／PR／建置，或設一次性提醒，而 session 保持開著時。
- 關鍵內容：
  - 三種排程：Cloud routines（最小 1 小時）／Desktop／/loop（最小 1 分鐘，需開 session）
  - /loop 5m <提示> 固定間隔；省略間隔由 Claude 動態選（1 分鐘～1 小時）；單獨 /loop 跑維護提示
  - 自訂預設提示：.claude/loop.md（專案優先）或 ~/.claude/loop.md
  - 底層工具 CronCreate／CronList／CronDelete，5 欄位 cron，每 session 最多 50 個任務
  - 重複任務 7 天後過期；--resume／--continue 會復原未過期任務
  - 抖動：每次延後最多間隔一半（上限 30 分鐘）；*/5 不延後
  - 動態模式可用 ScheduleWakeup（stop: true 結束）；固定間隔迴圈要請 Claude 取消，Esc 無效
  - 排程提示只能叫 Claude 可自行呼叫的 skill，不含內建命令與 disable-model-invocation skill
- 新名詞：`/loop` ＝ 隨附 skill，重複執行提示的命令；`session 範圍排程` ＝ 任務綁在 session，不是系統級排程；`loop.md` ＝ 取代內建維護提示的自訂預設迴圈提示檔；`ScheduleWakeup` ＝ 動態節奏迴圈用來預約下次喚醒／停止的工具
- 記憶系統接點：排程回合在使用者回合之間以低優先級插入；任務隨 session resume 還原；排程觸發的回合視同自動提示（artifacts 發佈會詢問、ultracode 關鍵字不生效）；loop.md 與 CLAUDE.md 一樣有專案／使用者兩層。

### 以程式方式執行 Claude Code（`headless`）
- 檔案：[headless.md](headless.md)｜https://code.claude.com/docs/zh-TW/headless｜lastmod 2026-10-27｜37KB
- 一句話：用 claude -p（Agent SDK CLI）非互動執行 Claude Code，適合腳本與 CI。
- 何時讀：要把 Claude 放進腳本／CI、取得 JSON 輸出，或決定要不要加 --bare。
- 關鍵內容：
  - claude -p "…" --allowedTools "Read,Edit,Bash"；成功退出碼 0
  - --bare 跳過 hook、skill、plugin、MCP、自動記憶、CLAUDE.md 自動探索與系統提醒；將成為 -p 預設
  - 沒有 --bare，-p 會像互動 session 載入專案 settings 的 hook 與 .mcp.json
  - 輸出：--output-format text|json|stream-json（配 --verbose）
  - 權限：--allowedTools、--permission-mode（auto/dontAsk/acceptEdits）、--permission-prompts none
  - 系統提示：--append-system-prompt、--system-prompt；接續：--continue、--resume <id>
  - SIGTERM 退出碼 143，並執行 SessionEnd hook；--max-budget-usd 限制費用
  - 結束時背景工作最多閒置等 10 分鐘；-p 不等待 MCP 背景工作
- 新名詞：`--bare` ＝ 最小啟動模式：不載入 hook／skill／MCP／記憶／CLAUDE.md；`--permission-prompts none` ＝ 無人值守時把會彈提示的動作一律拒絕；`stream-json` ＝ 邊跑邊輸出每則訊息的格式
- 記憶系統接點：-p 預設會載入 ~/.claude 與專案的 hooks（含 SessionStart 注入）及自動記憶；--bare 則全部不載入並省略系統提醒，需靠 --settings／--mcp-config／--append-system-prompt-file 手動帶入；SIGTERM 時 SessionEnd hook 仍會跑。

### 使用 hooks 自動化工作流程（`hooks-guide`）
- 檔案：[hooks-guide.md](hooks-guide.md)｜https://code.claude.com/docs/zh-TW/hooks-guide｜lastmod 2026-11-02｜65KB
- 一句話：hooks 入門與實例：在生命週期事件自動執行命令、HTTP、MCP 工具或模型檢查。
- 何時讀：要自動格式化、擋危險命令、壓縮後重注入 context、改權限流程，或除錯 hook 沒觸發時。
- 關鍵內容：
  - 事件約 30 種：SessionStart、UserPromptSubmit、PreToolUse、PostToolUse、Stop、PreCompact、PostCompact、SessionEnd 等
  - 類型：command、http、mcp_tool、prompt（預設 30 秒）、agent（預設 60 秒、最多 50 輪，實驗）
  - exit 2 = 阻擋並把 stderr 回饋；JSON 的 additionalContext 必須包在 hookSpecificOutput 內，放頂層會被無聲忽略
  - 多 hook 並行；PreToolUse 取最嚴格：deny > defer > ask > allow
  - SessionStart 用 matcher compact 可在壓縮後重注入提醒（stdout 進 context）
  - 位置：~/.claude/settings.json、.claude/settings.json、settings.local.json、受管設定、plugin hooks.json、skill／subagent frontmatter
  - 逾時：command／http／mcp_tool 10 分鐘、SessionEnd 共享 1.5 秒；Stop hook 連阻 8 次會被覆寫
  - 除錯：/hooks、claude --debug、disableAllHooks；allow 無法繞過 deny 規則
- 新名詞：`hook` ＝ 在生命週期節點確定性執行的使用者定義處理；`matcher` ＝ 以 | 或 , 分隔工具名稱過濾 hook 觸發；`stop_hook_active` ＝ Stop hook 輸入欄位，用來避免無限阻擋；`agent hook` ＝ 啟動多輪子代理驗證的 hook（實驗）
- 記憶系統接點：hooks 是注入 context 的官方管道：SessionStart／UserPromptSubmit 的 stdout 或 hookSpecificOutput.additionalContext 會以 system-reminder 進 Claude；hook 不能觸發 / 命令或工具呼叫；PostCompact／PreCompact、InstructionsLoaded、FileChanged、ConfigChange 事件可掛接；同一事件多 hook 的 additionalContext 全部保留；SessionEnd 預算僅 1.5 秒。

### 從連結啟動工作階段（`deep-links`）
- 檔案：[deep-links.md](deep-links.md)｜https://code.claude.com/docs/zh-TW/deep-links｜lastmod 2026-10-29｜14KB
- 一句話：claude-cli:// 連結：點一下在指定目錄開終端機 Claude session 並預填提示。
- 何時讀：想在 runbook、警報、README 中嵌入「一鍵開 Claude」連結時。
- 關鍵內容：
  - 格式 claude-cli://open?q=<URL編碼提示>&cwd=<絕對路徑>&repo=<owner/name>
  - 提示只預填，須按 Enter 才送出；畫面顯示 Prompt from an external link 警告
  - cwd 與 repo 同時給則 cwd 優先；cwd 拒絕網路／UNC 路徑與含 .. 的路徑
  - 由互動 session 首次傳訊或 agent view 時向 OS 註冊處理程式（macOS .app／Linux .desktop／Windows HKCU）
  - disableDeepLinkRegistration 設定可完全阻止註冊
  - VS Code 另有 vscode://anthropic.claude-code/open 開編輯器分頁
- 新名詞：`deep link` ＝ 自訂 URL scheme，點擊後在本機啟動 Claude Code；`disableDeepLinkRegistration` ＝ 阻止註冊 URL 處理程式的設定
- 記憶系統接點：外部連結帶入的提示視為不受信任文字，介面強制顯示警告且不自動送出；連結只選目錄與預填，不執行任何動作。

## Guides

### 在 monorepo 或大型程式碼庫中設定 Claude Code（`large-codebases`）
- 檔案：[large-codebases.md](large-codebases.md)｜https://code.claude.com/docs/zh-TW/large-codebases｜lastmod 2026-11-04｜34KB
- 一句話：在 monorepo／大型程式碼庫縮小 Claude 範圍：分層 CLAUDE.md、排除、worktree、skills。
- 何時讀：repo 很大、Claude 讀太多或載入太多不相關指示時。
- 關鍵內容：
  - 從 repo 根啟動讀全部、僅根 CLAUDE.md 啟動載入；從子目錄啟動只能存取該子樹
  - 分層 CLAUDE.md（目錄所有者維護）vs .claude/rules/ 的 paths: glob 規則
  - claudeMdExcludes：glob 排除無關目錄的 CLAUDE.md／rules（各設定範圍皆可）
  - permissions.deny 的 Read 規則擋 vendor／生成程式碼；內容搜尋預設尊重 .gitignore
  - worktree.sparsePaths 讓新 worktree 只簽出需要的目錄
  - 約定過多時移到 skills／plugin／MCP 按需載入
  - 可寫 SessionStart hook 依啟動目錄（hook 輸入）推薦對應 plugin
- 新名詞：`claudeMdExcludes` ＝ 排除特定 CLAUDE.md／規則檔的 glob 設定；`worktree.sparsePaths` ＝ 建立 worktree 時只簽出列出目錄的設定；`路徑範圍規則` ＝ rules 檔的 paths: glob，處理符合檔案時才載入
- 記憶系統接點：CLAUDE.md 載入範圍隨啟動目錄而變、子目錄檔按需載入；claudeMdExcludes 與 paths: 規則是官方的按需載入手段；SessionStart hook 讀啟動目錄可動態推薦 plugin；專案 .claude/settings.json 不像 CLAUDE.md 向上繼承。

## MCP

### 透過 MCP 將 Claude Code 連接到工具（`mcp`）
- 檔案：[mcp.md](mcp.md)｜https://code.claude.com/docs/zh-TW/mcp｜lastmod 2026-11-02｜152KB
- 一句話：MCP 完整參考：安裝各類伺服器、範圍、OAuth、輸出限制、工具搜尋與受管設定。
- 何時讀：接外部工具／資料源、調 MCP 逾時與 token 限制、處理認證或組織管控時。
- 關鍵內容：
  - 傳輸：HTTP、SSE、stdio、WebSocket；claude mcp add --transport … -s local|project|user
  - 範圍：Local 與 User 存 ~/.claude.json、Project 存 .mcp.json；優先序 Local > Project > User > plugin > claude.ai
  - 輸出：超過 10,000 token 警告，預設上限 25,000，MAX_MCP_OUTPUT_TOKENS 可調
  - 逾時：MCP_TIMEOUT（啟動）、MCP_TOOL_TIMEOUT、個別 timeout、CLAUDE_CODE_MCP_TOOL_IDLE_TIMEOUT
  - 呼叫超過 2 分鐘自動轉背景任務；CLAUDE_CODE_MCP_AUTO_BACKGROUND_MS 調整
  - 工具搜尋預設延遲載入工具定義；ENABLE_TOOL_SEARCH = true／auto／auto:N／false
  - OAuth：/mcp 認證、固定回呼埠、預設憑證、headersHelper 動態標頭
  - 伺服器可標 anthropic/requiresUserInteraction、idempotentHint、readOnlyHint；Elicitation hook 可自動回應徵詢
- 新名詞：`MCP` ＝ Model Context Protocol，連接外部工具的開放標準；`工具搜尋（tool search）` ＝ 工具定義延後到需要才載入以省 context；`徵詢（elicitation）` ＝ 伺服器中途向使用者要結構化輸入；`MCP 任務` ＝ 伺服器端長時間工作，用 MCP tasks 擴充追蹤
- 記憶系統接點：MCP 工具定義預設延遲載入，只有名稱與伺服器指令進 context；伺服器可以用 channel 主動推訊息進 session；Elicitation／ElicitationResult 是 hook 事件；hook 可用 type: mcp_tool 直接呼叫 MCP 工具；子代理 frontmatter 可限定專屬 mcpServers；專案 .mcp.json 伺服器需一次性核准。

### 連接到 MCP 伺服器（`mcp-quickstart`）
- 檔案：[mcp-quickstart.md](mcp-quickstart.md)｜https://code.claude.com/docs/zh-TW/mcp-quickstart｜lastmod 2026-10-28｜25KB
- 一句話：第一次連 MCP 伺服器的逐步教學：新增、驗證、找到設定檔。
- 何時讀：第一次用 claude mcp add，或 /mcp 顯示沒伺服器、連線失敗時。
- 關鍵內容：
  - 範例：claude mcp add --transport http claude-code-docs https://code.claude.com/docs/mcp
  - 預設 local 範圍；--scope project 寫 .mcp.json 給團隊、--scope user 全專案可用
  - 設定位置：~/.claude.json（local／user）與專案根 .mcp.json；Windows 為 %USERPROFILE%\.claude.json
  - 檢查：claude mcp list／claude mcp get <名>／工作階段內 /mcp
  - 需登入的伺服器在 /mcp 內走瀏覽器 OAuth
  - 疑難：No MCP servers configured、Failed to connect、格式錯誤的 .mcp.json 項目只會被跳過
- 新名詞：`local 範圍` ＝ 預設；僅你、僅此專案，存 ~/.claude.json；`project 範圍` ＝ .mcp.json，隨版控共享
- 記憶系統接點：與 mcp 頁共用範圍／儲存位置規則；CLAUDE_CONFIG_DIR 設定時 ~/.claude.json 位置改變。

## Skills

### 使用 skills 擴展 Claude（`skills`）
- 檔案：[skills.md](skills.md)｜https://code.claude.com/docs/zh-TW/skills｜lastmod 2026-10-30｜114KB
- 一句話：建立與管理 skill（SKILL.md）：載入位置、frontmatter、調用控制、進階模式。
- 何時讀：要寫／改／除錯 skill，或搞不懂 skill 為何沒觸發或描述被截斷時。
- 關鍵內容：
  - 位置：企業（受管）、~/.claude/skills、專案 .claude/skills、巢狀子目錄、--add-dir、plugin、claude.ai
  - 自訂命令已併入 skill；.claude/commands/ 舊格式仍可用
  - frontmatter：name、description、when_to_use（合計 1,536 字元上限）、allowed-tools、model、effort
  - 另有 disable-model-invocation、user-invocable、context: fork、agent、hooks、paths、shell、arguments
  - 只有描述常駐 context，調用才載入全文；disable-model-invocation 則描述也不載入
  - 動態注入：!`command` 區塊；$ARGUMENTS／命名參數替換
  - skill 內容調用後留在對話，壓縮時依 token 預算保留；skillListingBudgetFraction 調清單預算
  - 排錯：/doctor 看清單成本、/skill-doctor 找未用 skill、claude plugin validate 驗 frontmatter
- 新名詞：`SKILL.md` ＝ skill 的指示檔，含 YAML frontmatter；`context: fork` ＝ 讓 skill 在隔離子代理中執行；`paths（skill）` ＝ 限制只在處理符合 glob 的檔案時自動載入；`skillOverrides` ＝ 從設定覆寫 skill 可見性的鍵
- 記憶系統接點：skill 清單（名稱＋描述）常駐 context、全文按需載入，與記憶卡「觸發才注入」同型；skill frontmatter 可定義 hooks，在調用後整個 session 生效；需每次成立的規則官方建議移進 hook；skill 資料夾支援 symlink；對話壓縮後需重新調用 skill 才能還原全文。

## Troubleshooting

### 偵錯您的設定（`debug-your-config`）
- 檔案：[debug-your-config.md](debug-your-config.md)｜https://code.claude.com/docs/zh-TW/debug-your-config｜lastmod 2026-11-04｜18KB
- 一句話：診斷 CLAUDE.md、settings、hooks、MCP、skills 為何沒生效的指令與流程。
- 何時讀：設定看似沒套用、hook 不觸發、MCP 沒載入時。
- 關鍵內容：
  - /context 看 context 佔用分項（/context all 展開）
  - /memory、/skills、/hooks、/mcp、/permissions、/status、/doctor、/debug 各查一類
  - claude doctor（shell 唯讀診斷）與 /status 顯示作用中設定來源與受管設定
  - claude --safe-mode 停用 CLAUDE.md、skills、plugin、hook、MCP 等自訂項目
  - hook 常見錯：定義在獨立檔、matcher 寫成陣列、工具名拼錯；claude --debug 看評估
  - 專案 .mcp.json 伺服器需一次性核准；啟動失敗常因相對路徑
  - settings.json 編輯短暫延遲後於執行中 session 生效
- 新名詞：`--safe-mode` ＝ 停用所有自訂項目但保留認證／模型／內建工具的啟動模式；`/context` ＝ 顯示 context 視窗佔用明細的命令
- 記憶系統接點：提供查驗「記憶／hook 是否真被載入」的官方介面：/context、/memory、/hooks、InstructionsLoaded 事件；safe-mode 仍套用組織受管 hook 與設定。

### 故障排除（`troubleshooting`）
- 檔案：[troubleshooting.md](troubleshooting.md)｜https://code.claude.com/docs/zh-TW/troubleshooting｜lastmod 2026-10-23｜16KB
- 一句話：Claude Code 執行後的效能、穩定性與搜尋問題，並提供各類症狀的導引表。
- 何時讀：CPU／記憶體高、卡住、auto-compact thrashing、@file 搜不到檔案時。
- 關鍵內容：
  - 症狀路由表：安裝→troubleshoot-install、設定→debug-your-config、API 錯誤→errors
  - Autocompact is thrashing：改分段讀大檔、/compact 指定保留、移交 subagent、/clear
  - thrashing 後用 /context 判斷是 Messages 太大還是啟動載入內容太多
  - 搜尋找不到檔案時安裝系統 ripgrep（brew／apt）；WSL 搜尋慢另有節
  - 終端相關：大表被截斷、剪貼簿、SSH 複製、全螢幕滾輪
  - 不確定時先跑 /doctor
- 新名詞：`autocompact thrashing` ＝ 自動壓縮成功卻立刻被檔案／工具輸出再填滿的循環
- 記憶系統接點：thrashing 的處置涉及 context 管理：精簡啟動載入內容（CLAUDE.md、記憶注入）與把大檔工作交給 subagent。

### 排除安裝和登入問題（`troubleshoot-install`）
- 檔案：[troubleshoot-install.md](troubleshoot-install.md)｜https://code.claude.com/docs/zh-TW/troubleshoot-install｜lastmod 2026-10-30｜78KB
- 一句話：安裝與登入故障排除：command not found、PATH、權限、網路、TLS、OAuth。
- 何時讀：安裝失敗、claude 指令找不到、更新失敗或登入迴圈時。
- 關鍵內容：
  - 安裝來源 downloads.claude.ai；先用 curl -sI 驗證連線
  - 常見：command not found、PATH、permission denied、TLS／SSL、Homebrew cask、Release verification failed
  - Windows：需 Git for Windows（bash）或 PowerShell；不支援 32 位元；claude.exe 更新後遺失
  - Linux：musl／glibc 不符、Illegal instruction、低記憶體安裝被終止、WSL1 Exec format error
  - 登入：/logout 重設；OAuth 無效代碼、403、組織已停用、WSL2／SSH／容器 OAuth 失敗
  - Bedrock／Agent Platform／Foundry 憑證未載入有專節；claude doctor 做自動診斷
- 新名詞：`claude doctor` ＝ shell 內執行的安裝與設定唯讀診斷命令
- 記憶系統接點：無

### 錯誤參考（`errors`）
- 檔案：[errors.md](errors.md)｜https://code.claude.com/docs/zh-TW/errors｜lastmod 2026-11-04｜586KB
- 一句話：執行時錯誤訊息對照表：每種錯誤的意思與復原方式，並含自動重試規則。
- 何時讀：看到 API Error、用量上限、登入、連線、Prompt too long 等訊息要查原因時。
- 關鍵內容：
  - 自動重試：暫時性故障以指數退避最多 10 次才顯示錯誤
  - 類別：伺服器錯誤、用量上限、身分驗證、網路連線、請求錯誤（Prompt is too long）
  - 類別續：命令列錯誤（--bg 與 --print 衝突）、Plugin、工具、背景工作階段
  - 類別續：包裝程式／IDE、Rewind、工作階段儲存警告、設定警告、回應品質
  - 設定警告含：Instruction file not loaded、Hook needs quotes around a path with a space
  - 另有 Agent descriptions over the 15.0k-token limit、crossSessionInbound must be one of accept/hold/refuse
  - 儲存警告含 CLAUDE_CODE_SKIP_PROMPT_HISTORY、CLAUDE_CODE_CHILD_SESSION 導致文字記錄儲存關閉
  - 頁首「找到您的錯誤」表以訊息字串對應章節；超大檔（約 600KB）請用 grep 定位
- 新名詞：`自動重試` ＝ Claude Code 對暫時性 API 失敗的指數退避重試（最多 10 次）；`Instruction file not loaded` ＝ 記憶檔因 Read 拒絕規則等原因未載入的通知
- 記憶系統接點：設定警告章節解釋記憶／規則檔未載入的原因（Read deny、工作目錄外讀取被封、循環連結）與 hook 路徑含空格需加引號；CLAUDE_CODE_SKIP_PROMPT_HISTORY 與 CLAUDE_CODE_CHILD_SESSION 會關閉文字記錄儲存。

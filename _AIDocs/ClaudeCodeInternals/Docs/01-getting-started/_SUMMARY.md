# 01-getting-started 導讀（Getting started／Core concepts／Use Claude Code）

> 共 12 頁；排除 changelog 與 Platforms and integrations、Code review and pull requests 子區。原文均在本資料夾，來源為官方 zh-TW 文件。


## Getting started


### 概述（`overview`）

- 檔案：[overview.md](overview.md)｜https://code.claude.com/docs/zh-TW/overview｜lastmod 2026-10-21｜17.0 KB
- 一句話：Claude Code 是能讀程式碼、改檔、跑指令的代理式編碼工具，各平台都能用。
- 何時讀：第一次認識 Claude Code、要選安裝方式或平台時。
- 關鍵內容：
  - 原生安裝：macOS/Linux/WSL 用 `curl -fsSL https://claude.ai/install.sh | bash`；PowerShell 用 `irm https://claude.ai/install.ps1 | iex`
  - 其他安裝：Homebrew `brew install --cask claude-code`（stable 約晚一週，`claude-code@latest` 追最新）、WinGet `winget install Anthropic.ClaudeCode`
  - 原生安裝背景自動更新；Homebrew/WinGet 不會，需手動 upgrade
  - 原生 Windows 建議裝 Git for Windows，否則 Bash 工具改用 PowerShell
  - 可用介面：終端機、VS Code/JetBrains、桌面 App、網頁 claude.ai/code、Slack、Chrome
  - 功能面：CLAUDE.md、MCP、skills、hooks、subagents、`claude -p` 管線
  - 需 Claude 訂閱（Pro/Max/Ultra/Team/Enterprise）或 Console/雲端供應商帳號
- 新名詞：無
- 記憶系統接點：無（導覽頁；僅提到 CLAUDE.md、hooks、MCP、skills 為功能入口）

### 快速入門（`quickstart`）

- 檔案：[quickstart.md](quickstart.md)｜https://code.claude.com/docs/zh-TW/quickstart｜lastmod 2026-10-30｜12.6 KB
- 一句話：七步帶你在終端機安裝、登入、問問題、改程式、用 git。
- 何時讀：剛裝好要跑第一個 session，或查基本指令表時。
- 關鍵內容：
  - 七步：安裝→`claude` 啟動並登入→問問題→改碼→git→修錯/加功能→其他工作流程
  - Shell 指令：`claude`、`claude "task"`、`claude -p "query"`（一次性）、`claude -c`（續最近）、`claude -r`（挑選恢復）
  - Session 內指令：`/clear`、`/help`、`/exit`（或 Ctrl+D 兩次）
  - 輸入 `/` 看所有命令與 skills；Tab 補全；↑ 歷史；`Shift+Tab` 循環權限模式
  - 提示技巧：具體描述、逐步說明、先讓 Claude 探索再改
  - 求助：`/help`、Claude Academy「Claude Code 101」、Discord
- 新名詞：無
- 記憶系統接點：無

## Core concepts


### Claude Code 如何運作（`how-claude-code-works`）

- 檔案：[how-claude-code-works.md](how-claude-code-works.md)｜https://code.claude.com/docs/zh-TW/how-claude-code-works｜lastmod 2026-10-30｜19.0 KB
- 一句話：說明代理迴圈、內建工具、context 視窗、session、檢查點與權限的整體架構。
- 何時讀：想理解 Claude Code 內部運作、context 何時滿、session 怎麼存時。
- 關鍵內容：
  - 代理迴圈三階段：收集上下文→採取行動→驗證結果，可隨時中斷（`Esc`）
  - 內建工具五類：檔案操作、搜尋、執行、網路、程式碼智能（需 code intelligence 外掛）
  - 啟動即載入：CLAUDE.md、自動記憶（MEMORY.md 前 200 行或 25KB）、MCP、skills 描述
  - Session 以純文字 JSONL 存於 `~/.claude/projects/`；每個新 session 是全新 context，不帶前一個的歷史
  - `--continue`/`--resume` 同 session ID 附加；`--fork-session` 或 `/branch` 複製成新 ID
  - 快滿時自動 compact；持久規則放 CLAUDE.md，可加「Compact Instructions」段或 `/compact focus on …`
  - MCP 工具定義預設延遲載入（tool search），只有名稱與 server 指示佔 context
  - Claude Code 會夾帶 system-reminder（CLAUDE.md、output style、檔案變動備註、commit 歸屬行）；`attribution`、`includeGitInstructions` 可調
  - 權限模式：Auto、Manual、Accept edits、Plan，`Shift+Tab` 循環；檔案編輯前自動快照，`Esc` 兩次回溯
- 新名詞：`agentic loop` ＝ 代理迴圈：Claude 反覆「看→做→驗」直到任務完成；`agent harness` ＝ 代理工具層：包在模型外、提供工具並管理 context 的那一層；`checkpoint` ＝ 檢查點：編輯前的檔案快照，可回溯但不含 Bash 改的檔
- 記憶系統接點：context 管理：CLAUDE.md 與自動記憶每個 session 開頭載入、compact 後從磁碟重注入；system-reminder 是 Claude Code 自己夾帶指令的機制；session 逐字稿路徑 `~/.claude/projects/` 可供外部工具讀

### 擴展 Claude Code（`features-overview`）

- 檔案：[features-overview.md](features-overview.md)｜https://code.claude.com/docs/zh-TW/features-overview｜lastmod 2026-10-26｜29.3 KB
- 一句話：比較 CLAUDE.md、skills、subagent、hooks、MCP、plugins 等擴充功能何時用哪個、context 成本多少。
- 何時讀：決定某需求該做成 CLAUDE.md、rule、skill、hook 還是 MCP 時。
- 關鍵內容：
  - 十類擴充：CLAUDE.md、Output styles、Skills、Code intelligence、MCP、Subagents、Dynamic workflows、Cross-session messaging、Hooks、Plugins/marketplaces
  - context 成本：CLAUDE.md 每請求全載；Skills 啟動載描述、用時載全文；MCP 啟動只載工具名；Hooks 零成本除非回傳輸出；Subagent 隔離
  - `disable-model-invocation: true` 可把 skill 描述移出 context（僅手動 `/name` 叫用）
  - 分層：CLAUDE.md 累加；skill 依名稱覆寫（managed>user>project）；subagent managed>CLI>project>user>plugin；MCP local>project>user；hooks 全部合併觸發
  - CLAUDE.md vs rules vs skill：每 session 載入 / 每 session 或開啟符合檔案時 / 隨選載入；CLAUDE.md 目標 200 行內
  - 「必須每次發生」的規則用 hook（PreToolUse 可封鎖），CLAUDE.md/skill 只是請求不是保證
  - Skill + Subagent：skill 可 `context: fork`，subagent 可用 `skills:` 欄位預載
  - 外掛 skill 有命名空間，如 `/my-plugin:review`
- 新名詞：`plugin` ＝ 外掛：把 skill、hook、subagent、MCP 打包成可安裝單元；`dynamic workflow` ＝ 動態工作流程：Claude 寫腳本在背景跑多個 subagent 回傳單一結果；`cross-session messaging` ＝ 跨工作階段傳訊：一個 session 的 Claude 傳訊息給另一個 session；`output style` ＝ 輸出風格：設定回應角色、語氣、格式的常駐指令，一次只有一個生效
- 記憶系統接點：設定分層與 context 載入時機的權威對照表：CLAUDE.md 全載、skill 描述常駐、MCP 只載名稱、hooks 零成本；hooks 全部合併觸發（不覆寫），可與其他來源的 hook 並存；hook 輸出會進 context

### 探索 .claude 目錄（`claude-directory`）

- 檔案：[claude-directory.md](claude-directory.md)｜https://code.claude.com/docs/zh-TW/claude-directory｜lastmod 2026-10-29｜30.7 KB
- 一句話：列出專案 `.claude/` 與 `~/.claude` 每個檔案的用途、載入時機、保留與清理規則。
- 何時讀：想知道某設定該放哪個檔、`~/.claude` 下有哪些資料、何時被清掉時。
- 關鍵內容：
  - 專案層：`CLAUDE.md`、`rules/*.md`、`settings.json`、`settings.local.json`、`.mcp.json`、`.worktreeinclude`、`skills/<name>/SKILL.md`、`commands/*.md`、`output-styles/*.md`、`agents/*.md`、`workflows/*.js`、`agent-memory/<name>/`
  - 僅全域：`~/.claude.json`、`projects/<project>/memory/`（自動記憶）、`keybindings.json`、`themes/*.json`
  - frontmatter 欄位：rules 只有 `paths`；skills 約 20 欄（name/description/allowed-tools/context/hooks/paths…）；agents 含 tools/model/memory/isolation/omitClaudeMd 等
  - `CLAUDE_CONFIG_DIR` 可改 `~/.claude` 位置；Windows 為 `%USERPROFILE%\.claude`
  - `cleanupPeriodDays`（預設 30、最小 1、0 無效）清理 `projects/<project>/<session>.jsonl`、subagents、tool-results、file-history（留 100 檢查點）、plans、debug 等
  - 不被年齡掃描刪：自動記憶 `projects/<project>/memory/`、`history.jsonl`、`stats-cache.json`、`.credentials.json`、`agent-memory/`
  - 逐字稿明文儲存（含 CLAUDE.md、工具輸出、.env 內容）；`CLAUDE_CODE_SKIP_PROMPT_HISTORY` 可關寫入
  - scratchpad 在 `%TEMP%\claude\<project>\<session-id>\scratchpad\`，不在 `~/.claude`，隨逐字稿清理
- 新名詞：`scratchpad` ＝ 暫存簿：每個 session 的臨時檔目錄，位於系統暫存區；`managed-settings.json` ＝ 企業強制設定，使用者設定與 `--settings` 都不能蓋過（少數例外）
- 記憶系統接點：設定分層與檔案位置：專案 vs `~/.claude`、commit 與否；自動記憶目錄 `projects/<project>/memory/` 免於保留掃描；`rules/` 僅 `paths` frontmatter；逐字稿明文含已載入的指令檔；保留掃描只處理文件列出的路徑

### 探索上下文視窗（`context-window`）

- 檔案：[context-window.md](context-window.md)｜https://code.claude.com/docs/zh-TW/context-window｜lastmod 2026-10-28｜9.0 KB
- 一句話：互動時間軸展示 context 從啟動到 compact 的填充過程與各機制的載入/壓縮後去留。
- 何時讀：要知道什麼在啟動載入、compact 後什麼會留、如何控制 context 時。
- 關鍵內容：
  - 啟動前即載入：CLAUDE.md、自動記憶、MCP 工具名、skill 描述（AGENTS.md 可取代 CLAUDE.md）
  - 工作中載入：檔案讀取、路徑範圍規則（讀到符合檔案時）、巢狀 CLAUDE.md、PostToolUse hook 輸出
  - compact 後從磁碟重注入：根目錄 CLAUDE.md、未限定範圍的規則、自動記憶、plan mode 計畫、skill 描述（v2.1.304+）
  - compact 後不保證保留：有 `paths:` 的規則與巢狀 CLAUDE.md（被摘要，需再讀才重載）；要永久就拿掉 `paths:` 或移到根 CLAUDE.md
  - compact 後重讀最多 5 個檔案（最近修改優先，>5,000 token 只留路徑）；已叫用 skill 每個上限 5,000 token、總計 25,000，最舊先丟
  - `compact` 來源的 SessionStart hook 會在 compact 後執行並把輸出加入 context；hook 先前加的 context 隨對話被摘要
  - 控制：`/compact <重點>`、`/rewind`→Summarize from here、`/autocompact 500k`、`/clear`、委派 subagent、`/context`（含 `/context all`）、`/memory`
  - 1M token 視窗：Fable、Sonnet 5+、Haiku 5.5、Opus 4.6+、Sonnet 4.6；用 `[1m]` 模型變體
- 新名詞：`compaction` ＝ 壓縮：把舊對話換成結構化摘要以騰出空間；`Referenced file` ＝ 壓縮後以路徑引用、不含內容的大檔顯示
- 記憶系統接點：SessionStart hook 可用 matcher `compact` 在壓縮後重注入內容（記憶注入可借用）；CLAUDE.md/自動記憶/無 paths 規則 compact 後從磁碟重注入，hook 先前注入的 context 則被摘要而非保留；PostToolUse hook 輸出進 context；`/context all` 可驗證載入清單

### Claude Code 如何使用 prompt caching（`prompt-caching`）

- 檔案：[prompt-caching.md](prompt-caching.md)｜https://code.claude.com/docs/zh-TW/prompt-caching｜lastmod 2026-10-29｜42.1 KB
- 一句話：Claude Code 如何用 prompt caching：請求分層、哪些動作會讓快取失效、TTL 與檢查方式。
- 何時讀：回應突然變慢/變貴、要決定切模型/改 CLAUDE.md/裝 MCP 時機，或調 TTL 時。
- 關鍵內容：
  - 請求分層（變動少的在前）：系統提示詞（核心指示＋工具定義）→ 專案上下文（CLAUDE.md、自動記憶、無範圍規則）→ 對話；前綴精確比對，前面變動讓後面全失效
  - 專案上下文只在 session 開始、`/clear`、`/compact` 後更新；session 中編輯 CLAUDE.md 不使快取失效但也不套用（需 `/clear`/`/compact`/重啟）
  - 會讓快取失效：切模型（每模型各自快取）、改 effort（多數模型）、開 fast mode、MCP 工具定義集合變動（無 tool search 時）、啟停外掛、deny 整個工具、`/compact`、累積大量圖片、升級 Claude Code
  - 保留快取：編輯 repo 檔案（附 system-reminder）、切權限模式、換 output style（自下一回合起）、叫用 skill/指令、`/recap`、`/rewind`、spawn subagent（子代理自有前綴）
  - TTL：訂閱方案內主對話 1 小時，API key/雲端/用量點數 5 分鐘；設定 `promptCacheTtl`/`CLAUDE_CODE_PROMPT_CACHE_TTL`、`subagentPromptCacheTtl`/`CLAUDE_CODE_SUBAGENT_PROMPT_CACHE_TTL`（5m|1h，v2.1.242+）；`FORCE_PROMPT_CACHING_5M=1` 最優先
  - 快取範圍實務上限於一台機器＋一個目錄：系統提示含自動記憶路徑、cwd、平台、shell、OS 版本；同目錄並行 session 可互讀
  - 檢查：狀態列 `current_usage.cache_creation_input_tokens`／`cache_read_input_tokens`；`/usage` 的 `Prompt cache (main)` 行（含 likely cause，v2.1.260+）
  - `PreModelSwitch` hook 可要求或略過切模型確認；停用快取見「停用 prompt caching」節
- 新名詞：`prompt prefix` ＝ 前綴：每次請求開頭與快取比對的那段內容；`cache TTL` ＝ 快取存活時間，5 分鐘或 1 小時；`opusplan` ＝ plan mode 用 Opus、執行用 Sonnet 的模型設定，每次切換都是一次模型切換
- 記憶系統接點：關鍵：session 中途改 CLAUDE.md／自動記憶不會即時生效，重注入時機只有 session 開始與 `/clear`、`/compact`；系統層（工具定義）變動比對話層貴，MCP 工具增減會影響快取；系統提示內嵌自動記憶路徑

## Use Claude Code


### Claude 如何記住您的專案（`memory`）

- 檔案：[memory.md](memory.md)｜https://code.claude.com/docs/zh-TW/memory｜lastmod 2026-11-04｜53.3 KB
- 一句話：說明 CLAUDE.md、AGENTS.md、`.claude/rules/` 與自動記憶的載入層級、路徑、大小預算與疑難排解。
- 何時讀：要設計指令檔層級、調整規則範圍、查自動記憶位置/限額、或除錯「為何沒遵守」時。
- 關鍵內容：
  - 兩套記憶：CLAUDE.md（人寫、指令）與自動記憶（Claude 寫、學習）；皆當 context 而非強制設定，強制請用 hook；CLAUDE.md 是系統提示詞之後的 user message
  - CLAUDE.md 載入順序（廣→窄）：受管理原則（Win `C:\Program Files\ClaudeCode\CLAUDE.md`、Linux `/etc/claude-code/`、macOS `/Library/Application Support/ClaudeCode/`）→ `~/.claude/CLAUDE.md` → `./CLAUDE.md` 或 `./.claude/CLAUDE.md` → `./CLAUDE.local.md`
  - 從 cwd 往上每層目錄都串接載入（不覆寫，越近越後讀）；子目錄 CLAUDE.md 在讀/寫/編輯該目錄檔案時才按需載入；區塊級 HTML 註解載入前被移除
  - 目標每檔 <200 行；啟動載入單檔上限 4 MiB（超過整檔跳過）；子目錄 CLAUDE.md/按需規則有較小單檔上限，超過只給開頭並附說明
  - `@path` 匯入遞迴最深 4 層、相對於含匯入的檔案；專案層匯入到工作目錄外需首次核准對話；`CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1` 才載入 `--add-dir` 目錄的記憶檔
  - `.claude/rules/*.md` 遞迴發現；無 `paths` 的規則啟動載入，有 `paths` glob 的在 Read/Write/Edit 或算讀取的 Bash 碰到符合檔案時載入；`~/.claude/rules/` 先於專案規則；`paths` 是唯一 frontmatter 欄位；大括號展開總預算 1,000 個／4 MiB
  - 自動記憶：預設開；路徑 `~/.claude/projects/<project>/memory/`（同 git repo 的所有 worktree/子目錄共用，機器本地不跨機）；`autoMemoryDirectory` 改路徑、`autoMemoryEnabled`、`CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` 關閉
  - 自動記憶結構：`MEMORY.md` 索引（每條一行）+ 主題檔；啟動只載 MEMORY.md 前 200 行或 25KB（先到者）；主題檔按需讀；frontmatter `type` 四類 user/feedback/project/reference；寫入時自動加 `modified` 時間戳；超限寫入仍成功但回錯誤要求重寫索引
  - 主對話自動記憶不載入 subagent（fork 例外）；subagent 自有記憶為獨立目錄；`claudeMdExcludes` 可跳過檔案（陣列跨層合併，不能排除受管理檔）；`claudeMd` 鍵只在 managed settings 生效
  - `/memory` 列檔/切換自動記憶/開資料夾；`/init`、`/doctor`、`/doctor prompt-audit`（v2.1.283+）；`InstructionsLoaded` hook 記錄載入了哪些檔；`/config`「Project instructions」有四值，預設 claude-md-or-agents-md
- 新名詞：`auto memory` ＝ 自動記憶：Claude 自己寫、跨 session 累積的筆記；`CLAUDE.local.md` ＝ 個人專案偏好檔，與 CLAUDE.md 同載入，需自行 gitignore；`AGENTS.md` ＝ 其他編碼 agent 通用的指令檔，無 CLAUDE.md 時預設改讀它（v2.1.277+）；`path-scoped rule` ＝ 路徑範圍規則：frontmatter 有 `paths` 的 rule，碰到符合檔案才載入；`claudeMdExcludes` ＝ 設定鍵：以 glob 排除特定 CLAUDE.md/規則檔
- 記憶系統接點：直接對應記憶系統：(1) 原生 auto memory 目錄 `~/.claude/projects/<project>/memory/` + `MEMORY.md` 200 行／25KB 上限，與自製 atom 系統並存時路徑與預算要分開；(2) CLAUDE.md 是 user message 非 system prompt、compact 後從磁碟重注入；(3) `InstructionsLoaded` hook 可觀測載入；(4) `~/.claude/rules/` 無 paths 者啟動即載；(5) `autoMemoryDirectory` 可指向自訂目錄；(6) 寫 MEMORY.md 後 Claude Code 會量測並提醒/回錯；(7) `@import` 可把外部檔案併入 CLAUDE.md（本機已用 @IDENTITY.md 等）

### 管理 sessions（`sessions`）

- 檔案：[sessions.md](sessions.md)｜https://code.claude.com/docs/zh-TW/sessions｜lastmod 2026-10-30｜33.5 KB
- 一句話：管理 session：恢復、命名、分支、選擇器、匯出與逐字稿儲存位置。
- 何時讀：要接續/分支舊對話、找逐字稿檔、或給腳本讀 session 資料時。
- 關鍵內容：
  - 入口：`claude --continue`、`--resume [name|id|path]`、`--from-pr <n>`、`/resume`；`-n <name>` 或 `/rename` 命名
  - 恢復還原：對話、模型、agent、權限模式（部分情況）、進行中 goal、未過期排程；不還原 `--mcp-config`/`--settings`/`--plugin-dir`/`--add-dir` 需再傳
  - 分支：`/branch [name]` 或 `--continue --fork-session`；歷史複製成新 ID，原本不變；同 session 在兩個終端同時開會交錯寫入同一逐字稿
  - 選擇器：預設列目前 worktree；`Ctrl+W` 擴到全部 worktree、`Ctrl+A` 擴到整機專案；`claude -p`/Agent SDK/`/loop` 開頭的 session 不出現
  - 逐字稿：`~/.claude/projects/<project>/<session-id>.jsonl`（路徑非英數轉 `-`，超過 200 字元截斷）；格式為內部格式，版本間可能變
  - 相關設定：`CLAUDE_CONFIG_DIR`、`CLAUDE_CODE_PROJECT_DIR_NAME`（1-64 字元，需搭配 CLAUDE_CONFIG_DIR，於啟動 shell 設）、`cleanupPeriodDays`、`CLAUDE_CODE_SKIP_PROMPT_HISTORY`、`--no-session-persistence`
  - `CLAUDE_CODE_PROJECT_DIR_NAME` 會讓逐字稿與自動記憶都寫入 `<config>/projects/<name>/`，多專案可共用一個記憶目錄
  - 給腳本：`/export`、`claude -p --resume <id> --output-format json`、hook 的 `transcript_path` 欄位（SessionEnd 可讀）
  - `/clear` 存舊 session 可再 `/resume`；`/compact`、`/context` 管 context；`claude purge` 刪專案逐字稿
- 新名詞：`session` ＝ 工作階段：綁定專案目錄、存成 JSONL 的已儲存對話；`background session` ＝ 背景工作階段：脫離終端機持續執行，可 `claude attach`；`fork` ＝ 分叉：複製歷史成新 session ID 而不動原本
- 記憶系統接點：hook 輸入含 `transcript_path`，SessionEnd hook 可讀完整逐字稿（對話萃取可借用）；session 以 cwd 為鍵；多 session 同時 resume 同一 ID 會交錯寫同檔（協作衝突點）；自動記憶與逐字稿共用 `<project>` 目錄命名規則

### 常見工作流程（`common-workflows`）

- 檔案：[common-workflows.md](common-workflows.md)｜https://code.claude.com/docs/zh-TW/common-workflows｜lastmod 2026-10-22｜17.5 KB
- 一句話：日常開發食譜：探索程式碼、除錯、重構、測試、PR、文件、圖片、排程、worktree、plan mode。
- 何時讀：要找某類任務的現成提示寫法與對應指令時。
- 關鍵內容：
  - 提示食譜：了解新程式碼庫、尋找相關程式碼、修錯、重構、測試、建立 PR、文件、圖片、`@` 引用檔案/目錄
  - 排程四選項：雲端 routines、桌面排程、GitHub Actions、`/loop`（`--resume`/`--continue` 恢復未過期固定間隔迴圈）
  - 平行 session：`claude --worktree feature-auth`（需有 commit 的 repo，否則 `Failed to resolve base branch "HEAD"`）
  - 編輯前規劃：`claude --permission-mode plan` 或 `Shift+Tab` 到 `⏸ plan mode on`
  - 研究委派：`use a subagent to investigate …`，檔案讀取留在 subagent context
  - 管線：`git log --oneline -20 | claude -p "summarize these recent commits"`
  - `claude --continue` 無對話時印 `No conversation found to continue`
  - `/powerup` 互動式教學；可直接問 Claude 自己的功能（查最新官方文件）
- 新名詞：無
- 記憶系統接點：無（偏使用食譜；排程/worktree/`-p` 為多 session 協作的入口指令）

### Claude Code 最佳實踐（`best-practices`）

- 檔案：[best-practices.md](best-practices.md)｜https://code.claude.com/docs/zh-TW/best-practices｜lastmod 2026-11-04｜52.3 KB
- 一句話：最佳實踐：告訴 Claude 看不到的資訊、給可執行檢查、用 hook 強制規則、控成本、無人值守執行。
- 何時讀：調整 CLAUDE.md/hook/成本/無人值守設定，或判斷哪些舊習慣可以停做時。
- 關鍵內容：
  - 確定性 vs 非確定性：prompt/CLAUDE.md/skill 由模型決定；hook、deny 規則、managed settings 由 Claude Code 強制
  - CLAUDE.md 只寫 Claude 讀碼推不出的東西（驗證指令、陷阱、repo 外決策、已糾正兩次的事）；<200 行；個人偏好放 `CLAUDE.local.md`
  - 規則範圍化：`.claude/rules/*.md` + `paths:`；有副作用的 skill 加 `disable-model-invocation: true`
  - 完成檢查四層：prompt 內要求、`/goal <條件>`、`Stop` hook（exit code 2 阻止停止，stderr 回給 Claude，連續封鎖八次後放行）、`/code-review` 新 subagent 審
  - `PostToolUse` hook 於每次 Edit/Write 後跑格式化；hook 類型：command、http、MCP tool、prompt、agent（後兩者非確定性）
  - 省成本：任務間 `/clear`（`/clear <name>` 命名舊 session）、`/compact <重點>`、`/usage` 看 skill/subagent/plugin/MCP 分解；注意 `/loop`、goal 檢查、subagent 背景耗用
  - 快取：訂閱方案約 1 小時、API key/雲端/用量點數 5 分鐘；>約 200K token 閒置會在快取過期前被壓縮
  - 無人值守五問：完成定義、自我檢查、可觸及範圍、停止條件（`--max-turns`、`--max-budget-usd`）、結果落點；腳本用 `--bare -p --allowedTools --permission-mode dontAsk --output-format json`
  - 平行：`claude -w <name>` + `.worktreeinclude`（複製 gitignore 檔，小檔為限）；`/batch` 拆 5–30 單元；第二個 session 當獨立審查者
  - 可停做：全大寫 IMPORTANT 強調、過度管理 context、為保護 context 而 subagent（1M 視窗＋自動壓縮後多已不必要）
- 新名詞：`Stop hook` ＝ Claude 想結束回合時觸發的 hook，exit 2 可逼它繼續；`/goal` ＝ 設定完成條件，由另一模型每回合檢查；`--bare` ＝ `claude -p` 旗標：略過 hook/skill/外掛/MCP/CLAUDE.md，確保可重現
- 記憶系統接點：最直接的「規則強制」依據：「一再強調仍漏掉 → 改成 hook」；Stop hook（exit 2＋stderr）可作為收尾閘；`--bare` 會略過 hook 與 CLAUDE.md（headless 腳本不會載入記憶注入）；hook 類型含 http 與 MCP tool；Stop hook 連續封鎖八次後放行（與自製 guardian 擋次數設計相關）

### 提示詞庫（`prompt-library`）

- 檔案：[prompt-library.md](prompt-library.md)｜https://code.claude.com/docs/zh-TW/prompt-library｜lastmod 2026-10-07｜4.6 KB
- 一句話：可複製貼上的提示詞庫（依任務/角色），附成效模式說明。
- 何時讀：不知道怎麼下提示、想找現成範本時。
- 關鍵內容：
  - 六個提示模式：描述結果不是步驟、給自我檢查方式、指向參考、說明可測量目標、給工件（`@file`、日誌、截圖）、指定答案格式
  - 範例：`why is the build failing? @build.log`
  - `/verify` 檢查完成變更與執行中的應用
  - 輸出樣式可設定回應預設格式（output styles）
  - 來源為 common-workflows、best-practices 與 Anthropic 團隊使用案例部落格
- 新名詞：無
- 記憶系統接點：無

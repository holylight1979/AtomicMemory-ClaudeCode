# 08-whats-new 導讀（每週新功能）

> 來源：code.claude.com/docs/zh-TW/whats-new（官方每週摘要，2026-w13～w37；官方沒有 w31）。每週一張卡，「關鍵內容」改為「本週新功能清單」。版本對應與新名詞總表見 [TIMELINE-新功能與新名詞.md](TIMELINE-新功能與新名詞.md)。

## What's New

### 最新動態（`whats-new`）
- 檔案：[whats-new.md](whats-new.md)｜https://code.claude.com/docs/zh-TW/whats-new｜lastmod 2026-09-17｜15.1 KB
- 一句話：每週新功能摘要的總目錄，列出 w13～w37 各週重點與連結。
- 何時讀：想從週次快速定位某功能是哪一週出現。
- 本週新功能清單：（總覽頁，無單週清單；各週重點見下列各卡）
  - 共 24 週（w13–w37，缺 w31），每週附版本範圍如 `v2.1.83 → v2.1.85`
  - 每條含程式碼片段、示範、完整文件連結；細項改看 changelog
- 新名詞：無
- 記憶系統接點：無

### 第 13 週 · 2026 年 3 月 23–27 日（`whats-new/2026-w13`）
- 檔案：[whats-new__2026-w13.md](whats-new__2026-w13.md)｜https://code.claude.com/docs/zh-TW/whats-new/2026-w13｜lastmod 2026-09-10｜5.6 KB
- 一句話：自動模式、Computer use、PR 自動修復、文字稿搜尋、PowerShell 工具與條件式 hooks 登場。
- 何時讀：想知道 auto mode、hook `if` 欄位、managed-settings.d 何時出現。
- 本週新功能清單：
  - auto mode（研究預覽）：分類器代審權限，Shift+Tab 切換，`permissions.defaultMode: auto`
  - Computer use（Desktop）：控制實體桌面，預設關閉、逐步詢問
  - Web PR 自動修復：CI 面板切換，Claude 監看 CI 推修正
  - 文字稿搜尋：Ctrl+O 後按 `/`，`n`/`N` 跳轉（v2.1.83）
  - PowerShell 工具（preview）：`CLAUDE_CODE_USE_POWERSHELL_TOOL=1`（v2.1.84）
  - 條件式 hooks：hook 的 `if` 欄位用權限規則語法，如 `Bash(git commit *)`（v2.1.85）
  - 其他：plugin `userConfig`、`managed-settings.d/`、`CwdChanged`/`FileChanged` hook、agent frontmatter `initialPrompt`
- 新名詞：`auto mode` ＝ 把權限提示交給分類器自動放行安全操作、擋掉可疑操作；`hook `if` field` ＝ hook 條件欄位，只在符合權限規則語法時才啟動；`managed-settings.d/` ＝ 管理設定的分片目錄，讓多團隊各自放政策片段
- 記憶系統接點：hook `if` 可縮小記憶 hook 觸發範圍；新增 CwdChanged/FileChanged 事件；managed-settings.d 可分層佈署政策。

### 第 14 週 · 3 月 30 日 – 4 月 3 日，2026 年（`whats-new/2026-w14`）
- 檔案：[whats-new__2026-w14.md](whats-new__2026-w14.md)｜https://code.claude.com/docs/zh-TW/whats-new/2026-w14｜lastmod 2026-09-25｜5.8 KB
- 一句話：CLI 版 Computer use、/powerup 課程、無閃爍渲染、MCP 結果大小覆蓋、plugin bin/ 進 PATH。
- 何時讀：查 NO_FLICKER、PermissionDenied hook、defer 決策、plugin 可執行檔何時有。
- 本週新功能清單：
  - CLI Computer use（研究預覽，需 macOS+Pro/Max，在 `/mcp` 開 computer-use）
  - `/powerup`：終端內互動式功能課程（v2.1.90）
  - 無閃爍渲染：`CLAUDE_CODE_NO_FLICKER=1`（v2.1.89）
  - MCP 結果上限：工具 `_meta` 設 `anthropic/maxResultSizeChars`，最高 500K（v2.1.91）
  - plugin `bin/` 目錄加入 Bash 工具 PATH（v2.1.91）
  - 其他：`PermissionDenied` hook（可 `retry: true`）、PreToolUse `permissionDecision: defer`、`disableSkillShellExecution`、hook 輸出超過上限存檔、思考摘要預設關
- 新名詞：`PermissionDenied hook` ＝ auto mode 分類器拒絕時觸發，可回 retry 讓 Claude 換法；`defer` ＝ PreToolUse 決策值，-p 會話在工具呼叫處暫停待外部決定後 --resume；``/powerup`` ＝ 終端內的互動式 Claude Code 功能教學
- 記憶系統接點：PermissionDenied 與 defer 是新 hook 決策面；hook 輸出過大改存檔+預覽，影響以 hook 注入長內容的做法；plugin bin/ 可打包工具。

### 第 15 週 · 2026 年 4 月 6–10 日（`whats-new/2026-w15`）
- 檔案：[whats-new__2026-w15.md](whats-new__2026-w15.md)｜https://code.claude.com/docs/zh-TW/whats-new/2026-w15｜lastmod 2026-09-10｜5.6 KB
- 一句話：Ultraplan 雲端規劃、Monitor 工具與自我調整 /loop、/team-onboarding、/autofix-pr。
- 何時讀：查 Monitor 工具、/loop 自動間隔、/team-onboarding 或 sessionTitle hook 來源。
- 本週新功能清單：
  - Ultraplan（研究預覽）：終端起雲端規劃模式，瀏覽器審稿（後於 v2.1.222 移除）
  - Monitor 工具：背景監看程序、事件串流進對話（v2.1.98）
  - `/loop` 自我調整：省略間隔由 Claude 排程
  - `/autofix-pr`：終端啟用 Web PR 自動修復
  - `/team-onboarding`：由本機用量產生團隊入職指南（v2.1.101）
  - 其他：Focus view、Bedrock/Vertex 設定精靈、`/agents` 分頁、預設 effort 改 high、`/cost` 細分、statusline `refreshInterval`、`CLAUDE_CODE_PERFORCE_MODE`、`UserPromptSubmit` hook 可設 `sessionTitle`
- 新名詞：`Monitor tool` ＝ 開背景監看並把事件當訊息串流進對話的內建工具；`Ultraplan` ＝ 雲端起草計畫的規劃模式（已移除）；``/team-onboarding`` ＝ 把你的 Claude Code 用法打包成新人指南
- 記憶系統接點：Monitor 工具是事件驅動的非輪詢機制；UserPromptSubmit hook 輸出可含 sessionTitle。

### 第 16 週 · 2026 年 4 月 13–17 日（`whats-new/2026-w16`）
- 檔案：[whats-new__2026-w16.md](whats-new__2026-w16.md)｜https://code.claude.com/docs/zh-TW/whats-new/2026-w16｜lastmod 2026-09-09｜6.6 KB
- 一句話：Opus 4.7 與 xhigh 努力等級、Routines、/usage 細目、手機推播、原生二進位檔。
- 何時讀：查 xhigh、routines、/ultrareview 首次出現、PreCompact 可阻擋、monitors manifest。
- 本週新功能清單：
  - Claude Opus 4.7 + `xhigh` 努力等級（high 與 max 之間）
  - Routines（Web）：排程／GitHub 事件／API 觸發的範本化雲端 agent
  - `/usage` 細目：平行 session、子代理、快取遺漏、長上下文占比
  - 行動推播：Remote Control 連線後 Claude 可推通知到手機
  - 原生二進位檔：`claude` 不再呼叫 Node（v2.1.113）
  - 其他：`/ultrareview`、auto mode 開放 Max、`/recap`、`/tui`、`/focus`、plugin `monitors` manifest、`/fewer-permission-prompts`、`PreCompact` 可 block、`ENABLE_PROMPT_CACHING_1H`、`sandbox.network.deniedDomains`
- 新名詞：`xhigh` ＝ 新努力等級，介於 high 與 max；`Routines` ＝ 在雲端依排程或事件觸發的範本化 agent；``/recap`` ＝ 返回 session 時給一行離開期間摘要
- 記憶系統接點：PreCompact hook 可阻擋壓縮（exit 2 或 decision:block）；plugin 可用 monitors 鍵自動啟背景監看；1 小時 prompt cache 可選用。

### 第 17 週 · 2026 年 4 月 20–24 日（`whats-new/2026-w17`）
- 檔案：[whats-new__2026-w17.md](whats-new__2026-w17.md)｜https://code.claude.com/docs/zh-TW/whats-new/2026-w17｜lastmod 2026-09-25｜5.5 KB
- 一句話：/ultrareview 公開預覽、session 摘要、自訂主題、hooks 可直接呼叫 MCP 工具、Web 版改版。
- 何時讀：查 hook `type: mcp_tool`、/cost 併入 /usage、fork subagent 環境變數。
- 本週新功能清單：
  - `/ultrareview`：雲端 bug-hunting agent 群，結果回傳 CLI／Desktop
  - Session 摘要（返回時一行回顧）
  - 自訂色彩主題：`/theme`、`~/.claude/themes/`、plugin 可提供（v2.1.118）
  - Web 版 Claude Code 重新設計
  - 其他：vim 視覺模式、hook `type: "mcp_tool"`、`/cost`+`/stats` 併入 `/usage`、`/config` 寫入 settings.json、`CLAUDE_CODE_FORK_SUBAGENT=1`、原生版以 bfs/ugrep 取代 Glob/Grep、`claude plugin tag`
- 新名詞：`hook `type: mcp_tool`` ＝ hook 直接呼叫已連線 MCP 工具，免開子程序；`fork subagent` ＝ 繼承完整對話的分叉子代理
- 記憶系統接點：hooks 可直接叫 MCP 工具（記憶 MCP 可被 hook 直呼）；/config 變更落到 settings.json 並遵循分層優先序。

### 第 18 週 · 4 月 27 日 – 5 月 1 日，2026 年（`whats-new/2026-w18`）
- 檔案：[whats-new__2026-w18.md](whats-new__2026-w18.md)｜https://code.claude.com/docs/zh-TW/whats-new/2026-w18｜lastmod 2026-09-10｜5.1 KB
- 一句話：Windows 免 Git Bash、貼 OAuth 碼登入、claude project purge、PR URL 找回 session。
- 何時讀：查 alwaysLoad、updatedToolOutput、plugin prune、dangerously-skip-permissions 範圍。
- 本週新功能清單：
  - Windows 無需 Git Bash：無 Bash 時用 PowerShell 工具
  - `claude auth login` 可貼 OAuth 碼（WSL2／SSH／容器，v2.1.126）
  - `claude project purge`：刪除專案全部本地狀態（後更名 `claude purge`）
  - `/resume` 貼 PR URL 找建立該 PR 的 session（v2.1.122）
  - 其他：MCP `alwaysLoad: true`、`claude plugin prune`、PostToolUse `updatedToolOutput` 全工具適用、`claude ultrareview` 子命令、`--dangerously-skip-permissions` 範圍擴大、MCP 啟動失敗自動重試 3 次、大量記憶體洩漏修復
- 新名詞：``alwaysLoad`` ＝ MCP 伺服器設定，讓其全部工具不被 tool search 延遲載入；``updatedToolOutput`` ＝ PostToolUse hook 可替換任何工具的輸出
- 記憶系統接點：PostToolUse 可改寫任何工具輸出；alwaysLoad 影響 MCP 工具載入策略；project purge 清除專案狀態。

### 第 19 週 · 2026 年 5 月 4–8 日（`whats-new/2026-w19`）
- 檔案：[whats-new__2026-w19.md](whats-new__2026-w19.md)｜https://code.claude.com/docs/zh-TW/whats-new/2026-w19｜lastmod 2026-09-25｜3.7 KB
- 一句話：plugin 可從 .zip／URL 載入、Ctrl+R 搜全專案歷史、worktree.baseRef、auto mode hard_deny。
- 何時讀：查 --plugin-url、worktree.baseRef、hard_deny、hook 取得 effort 的方式。
- 本週新功能清單：
  - `--plugin-dir` 接受 .zip；`--plugin-url` 從 URL 取 plugin
  - Ctrl+R 預設搜全部專案提示（v2.1.129）
  - `worktree.baseRef`（`fresh`|`head`）決定 worktree 從遠端預設分支或本機 HEAD 分出
  - `autoMode.hard_deny`：無條件封鎖符合條件的操作
  - 其他：hook 取得 `effort.level`／`$CLAUDE_EFFORT`、`CLAUDE_CODE_SESSION_ID` 進 Bash 環境、子程序不再繼承 `OTEL_*`、`parentSettingsBehavior`、子代理進度摘要命中 prompt cache
- 新名詞：`hard_deny` ＝ auto mode 中無論允許例外都一律封鎖的規則；``worktree.baseRef`` ＝ 新 worktree 的分支基準設定
- 記憶系統接點：Bash 環境與 hooks 的 session_id 對齊（CLAUDE_CODE_SESSION_ID）；hooks 可讀 effort 等級。

### 第 20 週 · 2026 年 5 月 11–15 日（`whats-new/2026-w20`）
- 檔案：[whats-new__2026-w20.md](whats-new__2026-w20.md)｜https://code.claude.com/docs/zh-TW/whats-new/2026-w20｜lastmod 2026-10-19｜5.2 KB
- 一句話：agent view（claude agents）、/goal、Opus 4.7 上的快速模式。
- 何時讀：查 /goal、agent view、hook args/continueOnBlock/terminalSequence 何時加入。
- 本週新功能清單：
  - Agent view（研究預覽）：`claude agents` 一屏管理所有 session
  - `/goal`：設完成條件，Claude 跨回合持續工作，快速模型判定是否達成（v2.1.139）
  - `/fast` 預設改在 Opus 4.7（約 2.5 倍速，$30/$150 per MTok）
  - 其他：`claude agents` 派發旗標、hook `args: string[]` exec 形式、`continueOnBlock`（PostToolUse）、hook JSON `terminalSequence`、Rewind「在此處總結」、MCP stdio 得到 `CLAUDE_PROJECT_DIR`、`claude plugin details`、subagent_type 不分大小寫
- 新名詞：`agent view` ＝ 列出所有 Claude Code session 狀態的儀表板；``/goal`` ＝ 設定終止條件、Claude 持續回合直到成立；`hook exec form `args`` ＝ 不經 shell 直接 spawn 命令的 hook 寫法
- 記憶系統接點：hook exec form 免引號問題；continueOnBlock 把 hook 拒絕理由回饋給 Claude；terminalSequence 讓 hook 發通知；MCP stdio 與 hooks 共用 CLAUDE_PROJECT_DIR。

### 第 21 週 · 2026 年 5 月 18–22 日（`whats-new/2026-w21`）
- 檔案：[whats-new__2026-w21.md](whats-new__2026-w21.md)｜https://code.claude.com/docs/zh-TW/whats-new/2026-w21｜lastmod 2026-09-10｜3.6 KB
- 一句話：Pro 方案可用 auto mode（Sonnet 4.6）、/usage 分類歸因、/code-review。
- 何時讀：查 /code-review 起源、usage credits 更名、worktree.bgIsolation。
- 本週新功能清單：
  - Pro 方案支援 auto mode（Sonnet 4.6 與 Opus）
  - `/usage` 依 skills／subagents／plugins／MCP server 歸因耗用
  - `/code-review`（取代 /simplify 的審查用途），`--comment` 發 PR 行內評論
  - 其他："extra usage" 更名 usage credits、背景 session 出現在 `/resume`、`claude agents --json`、Windows 預設啟用 PowerShell 工具（Bedrock/Vertex/Foundry）、`worktree.bgIsolation: "none"`、`allowAllClaudeAiMcps`
- 新名詞：`usage credits` ＝ 舊稱 extra usage 的額外用量額度；``/code-review`` ＝ 在選定 effort 下報告正確性問題的審查指令
- 記憶系統接點：/usage 可看 skills、MCP 的耗用歸因；背景 session 可被 /resume。

### 第 22 週 · 5 月 25–29 日，2026 年（`whats-new/2026-w22`）
- 檔案：[whats-new__2026-w22.md](whats-new__2026-w22.md)｜https://code.claude.com/docs/zh-TW/whats-new/2026-w22｜lastmod 2026-09-10｜5.6 KB
- 一句話：Opus 4.8、動態 workflows、security-guidance plugin、Opus 4.8 快速模式降價。
- 何時讀：查 dynamic workflows、MessageDisplay hook、/reload-skills、plugin defaultEnabled。
- 本週新功能清單：
  - Claude Opus 4.8（預設 high 努力；`/effort xhigh`，需 v2.1.154+）
  - Dynamic workflows（研究預覽）：Claude 寫協調腳本、背景跨多子代理執行，`/workflows` 管理
  - security-guidance plugin：每次編輯快檢、回合結束模型檢查、提交時深度檢查
  - Opus 4.8 快速模式 $10/$50 per MTok（2x 價、約 2.5x 速）
  - 其他：`!` 背景 shell 工作、`.claude/skills` 內 plugin 自動載入、`/reload-skills`、SessionStart `reloadSkills: true`、skill `disallowed-tools`、`MessageDisplay` hook、`--fallback-model`、`defaultEnabled: false`
- 新名詞：`dynamic workflows` ＝ Claude 為任務寫的協調腳本，背景驅動大量子代理；``MessageDisplay` hook` ＝ 轉換或隱藏助手訊息顯示文字的 hook 事件；``/reload-skills`` ＝ 不重啟重新掃描 skill 目錄
- 記憶系統接點：SessionStart hook 可回 reloadSkills 使剛安裝的 skill 同 session 生效；MessageDisplay 為新 hook 事件；disallowed-tools 讓 skill 啟用時收窄工具。

### 第 23 週 · 2026 年 6 月 1–5 日（`whats-new/2026-w23`）
- 檔案：[whats-new__2026-w23.md](whats-new__2026-w23.md)｜https://code.claude.com/docs/zh-TW/whats-new/2026-w23｜lastmod 2026-09-25｜5.2 KB
- 一句話：第三方雲端也有 auto mode、acceptEdits 更安全、/plugin list、受管版本範圍。
- 何時讀：查 requiredMinimumVersion、Stop hook additionalContext、ultracode 關鍵字改名。
- 本週新功能清單：
  - Bedrock／Google Agent Platform／Foundry 上的 auto mode（`CLAUDE_CODE_ENABLE_AUTO_MODE=1`，v2.1.158）
  - acceptEdits 寫入可執行程式碼檔（shell rc、`.npmrc` 等）前先提示（v2.1.160）
  - `/plugin list`（也有 `claude plugin list`），支援 `--enabled`/`--disabled`
  - 受管設定 `requiredMinimumVersion`／`requiredMaximumVersion`（v2.1.163）
  - 其他：workflows 觸發詞改 `ultracode`、Stop/SubagentStop hook 可回 `hookSpecificOutput.additionalContext` 讓回合繼續、`claude mcp` 不再印機密、並行工具批次獨立
- 新名詞：``ultracode`` ＝ 動態 workflows 的提示觸發關鍵字（原為 workflow）；`requiredMinimumVersion` ＝ 管理員設定，版本不在範圍內的 client 啟動即退出
- 記憶系統接點：Stop/SubagentStop hook 可回 additionalContext 讓回合不結束——可作收尾提醒注入點。

### 第 24 週 · 2026 年 6 月 8–12 日（`whats-new/2026-w24`）
- 檔案：[whats-new__2026-w24.md](whats-new__2026-w24.md)｜https://code.claude.com/docs/zh-TW/whats-new/2026-w24｜lastmod 2026-09-10｜4.2 KB
- 一句話：/cd 移動 session、子代理可再生子代理、--safe-mode 疑難排解。
- 何時讀：查 safe-mode、fallbackModel 設定、nested subagent 深度、/cd。
- 本週新功能清單：
  - `/cd`：不重建 prompt cache 就換工作目錄，新目錄 CLAUDE.md 以訊息附加（v2.1.169）
  - 子代理可產生子代理，深度上限 5（v2.1.172）
  - `--safe-mode`／`CLAUDE_CODE_SAFE_MODE`：停用 CLAUDE.md、skills、plugins、hooks、MCP 等所有自訂項
  - 其他：`fallbackModel` 最多三個、session 標題依對話語言、`disableBundledSkills`、deny 規則可用 glob、`SendMessage` 轉送訊息不帶使用者授權、`enforceAvailableModels`、`footerLinksRegexes`
- 新名詞：`safe mode` ＝ 停用一切自訂項目的乾淨啟動模式；``/cd`` ＝ 把進行中的 session 移到新工作目錄
- 記憶系統接點：safe mode 會關閉 hooks 與 CLAUDE.md（排查記憶 hook 故障的隔離手段）；/cd 以附加訊息載入新 CLAUDE.md。

### 第 25 週 · 2026 年 6 月 15–19 日（`whats-new/2026-w25`）
- 檔案：[whats-new__2026-w25.md](whats-new__2026-w25.md)｜https://code.claude.com/docs/zh-TW/whats-new/2026-w25｜lastmod 2026-09-10｜4.1 KB
- 一句話：Artifacts 即時頁面、權限規則可比對工具參數、/config key=value。
- 何時讀：查 Tool(param:value) 語法、Artifacts 起源、agent teams 隱含團隊。
- 本週新功能清單：
  - Artifacts：從 session 發佈到 claude.ai 的私人即時互動頁面，持續就地更新
  - 權限規則比對輸入參數：`Agent(model:opus)`、`Agent(isolation:*)`（v2.1.178）
  - `/config key=value`：從提示直接改設定，含 `-p` 與 Remote Control（v2.1.181）
  - 其他：auto mode 擋破壞性 git 與 `terraform destroy`、`attribution.sessionUrl`、`sandbox.allowAppleEvents`、`CLAUDE_CLIENT_PRESENCE_FILE`、agent teams 隱含團隊（移除 TeamCreate/TeamDelete）、巢狀 `.claude/skills` 載入
- 新名詞：`Artifacts` ＝ Claude Code 發佈的即時可分享頁面；``Tool(param:value)`` ＝ 權限規則依工具輸入參數比對的語法
- 記憶系統接點：permission 規則可依參數比對；巢狀 .claude/skills 於處理該目錄檔案時載入。

### 第 26 週 · 2026 年 6 月 22–26 日（`whats-new/2026-w26`）
- 檔案：[whats-new__2026-w26.md](whats-new__2026-w26.md)｜https://code.claude.com/docs/zh-TW/whats-new/2026-w26｜lastmod 2026-09-09｜3.5 KB
- 一句話：claude mcp login、! 指令輸出會得到回應、/rewind 可回到 /clear 前。
- 何時讀：查 sandbox.credentials、autoMode.classifyAllShell、background subagent 權限提示。
- 本週新功能清單：
  - `claude mcp login <name>`／`logout`：shell 端執行 MCP OAuth（v2.1.186）
  - `!` 指令輸出會得到 Claude 回應（`respondToBashCommands` 可關）
  - 其他：`/rewind` 可從 `/clear` 之前恢復、`sandbox.credentials` 擋憑證檔、組織模型限制、`autoMode.classifyAllShell`、`claude_code.assistant_response` OTel 事件、背景子代理的權限提示顯示於主 session、CPU 降約 37%
- 新名詞：``sandbox.credentials`` ＝ 阻止沙箱化命令讀憑證檔與祕密環境變數；``classifyAllShell`` ＝ 讓所有 shell 命令都過 auto mode 分類器
- 記憶系統接點：OTel 新增 assistant_response 事件（會帶回應文字，隱私需留意）；/rewind 可回 /clear 前。

### 第 27 週 · 6 月 29 日 – 7 月 3 日，2026 年（`whats-new/2026-w27`）
- 檔案：[whats-new__2026-w27.md](whats-new__2026-w27.md)｜https://code.claude.com/docs/zh-TW/whats-new/2026-w27｜lastmod 2026-09-10｜5.3 KB
- 一句話：Sonnet 5 成預設、Chrome 整合正式推出、子代理預設背景、/radio。
- 何時讀：查 subagents 預設背景起點、Manual 權限模式名稱、Artifacts GA、hook matcher 精確比對。
- 本週新功能清單：
  - Claude Sonnet 5 為 Pro／Team Standard／Enterprise 預設，原生 1M 上下文
  - Claude in Chrome 正式推出（v2.1.198）
  - 子代理預設在背景執行，完成時通知（v2.1.198）
  - Claude Desktop on Linux（beta）；`/radio` Claude FM
  - 其他：Artifacts GA、組織預設模型、堆疊 skill 呼叫（最多 5 個）、`default` 權限模式更名 Manual、`/dataviz` skill、Explore 代理繼承主模型、含連字號的 hook matcher 改精確比對、串流閒置監視預設開（5 分鐘）
- 新名詞：`Manual 權限模式` ＝ 原 default 權限模式的新名稱；`background subagent` ＝ 子代理預設背景執行、不阻塞主對話
- 記憶系統接點：hook matcher 含連字號識別符改精確比對（`code-reviewer` 不再子字串比對），可能影響既有 matcher；子代理背景化改變 SubagentStop 時機。

### 第 28 週 · 2026 年 7 月 6–10 日（`whats-new/2026-w28`）
- 檔案：[whats-new__2026-w28.md](whats-new__2026-w28.md)｜https://code.claude.com/docs/zh-TW/whats-new/2026-w28｜lastmod 2026-09-09｜3.4 KB
- 一句話：Desktop 內建瀏覽器、/doctor 完整檢查並可修復、auto mode 保護 transcript。
- 何時讀：查 /doctor 新行為、/checkup、auto mode 防篡改 transcript。
- 本週新功能清單：
  - Desktop 應用內瀏覽器（沙箱化、可設定）
  - `/doctor` 變為完整設定檢查：診斷＋修復、找未用 skills／MCP／plugins 與背景成本、本機與簽入 `CLAUDE.md` 去重（v2.1.205；別名 `/checkup`）
  - 其他：auto mode 阻止篡改 session transcript 檔、`rm -rf` 未解析變數會詢問、`/cd` 路徑建議、`/commit-push-pr` 自動允許設定的 push remote、`EnterWorktree` 對專案外 worktree 要求確認、背景 agent 更新後即時升級
- 新名詞：``/doctor`` ＝ 完整設定檢查，可診斷並修復，別名 /checkup
- 記憶系統接點：/doctor 會提議精簡簽入的 CLAUDE.md 與找未用 skills/MCP；auto mode 保護 transcript 檔。

### 第 29 週 · 2026 年 7 月 13–17 日（`whats-new/2026-w29`）
- 檔案：[whats-new__2026-w29.md](whats-new__2026-w29.md)｜https://code.claude.com/docs/zh-TW/whats-new/2026-w29｜lastmod 2026-09-09｜4.5 KB
- 一句話：Artifacts 可呼叫 MCP 連接器取即時資料、螢幕閱讀器模式。
- 何時讀：查 /fork 新語義、/subtask、MCP 工具自動背景化、session 上限。
- 本週新功能清單：
  - Artifact 呼叫 MCP 連接器：每次檢視用檢視者自己的連線取即時資料
  - 螢幕閱讀器模式：純文字線性輸出（`--ax-screen-reader`／`CLAUDE_AX_SCREEN_READER`）
  - 其他：`/fork` 改為複製成新背景 session（原 session 內分叉子代理改稱 `/subtask`）、MCP 工具呼叫超過 2 分鐘自動轉背景（`CLAUDE_CODE_MCP_AUTO_BACKGROUND_MS`）、`claude auto-mode reset`、`CLAUDE_CODE_PROCESS_WRAPPER`、WebSearch／子代理生成每 session 預設各 200 次上限、「一律允許」規則存於 repo 根
- 新名詞：``/subtask`` ＝ session 內的分叉子代理（原 /fork 的舊義）；`process wrapper` ＝ 強制所有衍生程序通過企業啟動器的設定
- 記憶系統接點：「一律允許」規則存 repo 根使 worktree 共用核准；MCP 長呼叫自動背景化；子代理生成有 session 上限。

### 第 30 週 · 7 月 20–24 日，2026 年（`whats-new/2026-w30`）
- 檔案：[whats-new__2026-w30.md](whats-new__2026-w30.md)｜https://code.claude.com/docs/zh-TW/whats-new/2026-w30｜lastmod 2026-10-15｜5.7 KB
- 一句話：Opus 5 成預設 Opus、Desktop iOS Simulator 窗格、Claude Security plugin。
- 何時讀：查 /code-review 背景化、DirectoryAdded hook、子代理並行上限。
- 本週新功能清單：
  - Claude Opus 5 為預設 Opus（1M 上下文）
  - Claude Code Desktop iOS Simulator 窗格（macOS，beta）
  - Claude Security plugin：多代理漏洞掃描，輸出 `CLAUDE-SECURITY-<timestamp>/`（`/claude-security`）
  - 其他：`/code-review` 以背景子代理執行、`/verify`／`/deep-research` 僅手動叫用、emoji 短碼補全、`context: fork` skill 預設背景、子代理並行預設上限 20、`--max-budget-usd` 約束子代理、`DirectoryAdded` hook、`sandbox.filesystem.disabled`、快速模式不再支援 Opus 4.7
- 新名詞：``DirectoryAdded` hook` ＝ `/add-dir` 註冊新工作目錄後觸發的 hook；``context: fork`` ＝ skill frontmatter：在分叉子代理中執行
- 記憶系統接點：DirectoryAdded 為新 hook 事件；context: fork skill 預設背景，並行子代理上限 20。

### 第 32 週 · 2026 年 8 月 3–7 日（`whats-new/2026-w32`）
- 檔案：[whats-new__2026-w32.md](whats-new__2026-w32.md)｜https://code.claude.com/docs/zh-TW/whats-new/2026-w32｜lastmod 2026-10-15｜7.1 KB
- 一句話：session 之間可互傳訊息、自託管環境、auto mode 成預設權限模式。
- 何時讀：查 SendMessage／ListAgents、self-hosted runner、crossSessionInbound、auto mode 預設日期。
- 本週新功能清單：
  - 跨 session 傳訊：`ListAgents` 發現、`SendMessage` 傳送，`/list-agents`（v2.1.224）
  - 自託管環境：`claude self-hosted-runner` 在自家基礎設施跑雲端 session（Team／Enterprise beta）
  - auto mode 自 8 月 14 日起為 Pro／Max／Team 新 session 預設權限模式
  - 其他：VS Code Focus view、sandbox 憑證 `mode: "mask"`、marketplace `archive` 來源、`/review` 為 `/code-review` 別名、`/fork` 在獨立 worktree、專案設定不能再開 Remote Control 自動連線、移除每 session 200 子代理上限、Ultraplan 移除
- 新名詞：`cross-session messaging` ＝ 同機或跨機 Claude session 互傳訊息的機制；`self-hosted environment` ＝ 在自家機器／容器上跑 Claude Code 雲端 session 的執行器；``crossSessionInbound`` ＝ 設定是否接受他 session 訊息（accept/hold/refuse）
- 記憶系統接點：SendMessage/ListAgents 提供多 session 協作的官方通道；crossSessionInbound 控制接收；轉送訊息不帶使用者授權（防注入）。

### 第 33 週 · 2026 年 8 月 10–14 日（`whats-new/2026-w33`）
- 檔案：[whats-new__2026-w33.md](whats-new__2026-w33.md)｜https://code.claude.com/docs/zh-TW/whats-new/2026-w33｜lastmod 2026-10-15｜6.2 KB
- 一句話：Desktop 用量重置後自動續跑、fork 模式預設開、GitLab MR 與 marketplace。
- 何時讀：查 fork subagent 預設、@ 提及他 session、TodoWrite 移除、GitLab 支援。
- 本週新功能清單：
  - Desktop 達用量上限後可勾選「限制重設時自動繼續」
  - Fork 模式預設開：`fork` 子代理繼承完整對話與 prompt cache（關閉 `CLAUDE_CODE_FORK_SUBAGENT=0`，v2.1.232）
  - GitLab 合併請求：`--worktree` 接 MR URL、`claude agents` 顯示 `!N`、marketplace 支援 gitlab.com
  - 其他：提示中 `@` 提及他 session、session 名稱唯一化、marketplace `command` 來源、`CLAUDE_CODE_TOOL_MEMORY_LIMIT`、TaskCreate／TodoWrite 於新模型不再提供（`CLAUDE_CODE_ENABLE_TODO_TOOLS=1` 重啟）、新模型 Write 可免先 Read 覆寫、`/plugin install` 先刷新 marketplace
- 新名詞：`fork mode` ＝ 子代理繼承整份對話與快取的分叉模式；``@session`` ＝ 在提示用 @ 提及另一個 Claude session 名稱並用 SendMessage 傳訊
- 記憶系統接點：任務追蹤工具（TodoWrite 等）在新模型移除；fork 子代理共享 prompt cache，利於注入內容重用。

### 第 34 週 · 2026 年 8 月 17–21 日（`whats-new/2026-w34`）
- 檔案：[whats-new__2026-w34.md](whats-new__2026-w34.md)｜https://code.claude.com/docs/zh-TW/whats-new/2026-w34｜lastmod 2026-10-23｜6.8 KB
- 一句話：/design 畫板、簡潔輸出風格、手機可在你的機器開 session、Remote Control 不再預覽。
- 何時讀：查 concise output style、spellcheck 設定、keybindingFlavor、notify_when_idle。
- 本週新功能清單：
  - `/design`：以 Artifacts 為基礎發佈可編輯 UI 畫板（研究預覽）
  - 簡潔（Concise）輸出風格（v2.1.237）
  - 手機從 Claude app Code 分頁在執行 `claude remote-control` 的機器啟動 session；Remote Control 結束預覽
  - 其他：claude.ai 用量重置後自動續跑、`spellcheck` 設定、GitLab MR 頁尾徽章、`ANTHROPIC_DEFAULT_MODEL`、`SendMessage` 的 `notify_when_idle`、`keybindingFlavor: readline`、Windows 原生支援跨 session 傳訊
- 新名詞：``/design`` ＝ 從簡短描述產出可編輯 UI 畫板的技能；``notify_when_idle`` ＝ SendMessage 參數：請對方 session 閒置時回報一次
- 記憶系統接點：notify_when_idle 提供 session 間輕量同步訊號；ANTHROPIC_DEFAULT_MODEL 可設新 session 起始模型。

### 第 35 週 · 2026 年 8 月 24–28 日（`whats-new/2026-w35`）
- 檔案：[whats-new__2026-w35.md](whats-new__2026-w35.md)｜https://code.claude.com/docs/zh-TW/whats-new/2026-w35｜lastmod 2026-09-17｜6.9 KB
- 一句話：Desktop 可恢復終端 session、Claude 草擬回饋、--restricted 受限模式。
- 何時讀：查 --restricted、SendFeedback 工具、modelPicker／promptCacheTtl 設定、/cd 後設定生效。
- 本週新功能清單：
  - Desktop `/resume` 選 CLI 開的 session 續跑
  - Claude 起草回饋：`SendFeedback` 工具，`/feedback` 開草稿佇列（v2.1.247）
  - `--restricted`／`CLAUDE_CODE_RESTRICTED=1`：移除會執行命令／程式碼的內建工具與 WebFetch（v2.1.248）
  - 其他：`modelPicker` 設定、`promptCacheTtl`／`subagentPromptCacheTtl`（1h）、`/usage` 迴圈細目、`modelPricing` 受管設定、Console 帳戶登入、`/permissions` Auto mode 分頁、`/cd` 後新目錄設定／hooks／skills 立即生效、非互動模式自動續答被中斷回應、zstd 更新檔 75MB
- 新名詞：`restricted mode` ＝ 啟動時不含任何可執行命令的工具與使用者／專案設定；``SendFeedback`` ＝ Claude 自行草擬回饋報告的工具
- 記憶系統接點：/cd 後專案 hooks／.mcp.json／skills／subagents 即時生效；promptCacheTtl 可延長快取；--restricted 不載入使用者與專案設定。

### 第 36 週 · 8 月 31 日 – 9 月 4 日，2026 年（`whats-new/2026-w36`）
- 檔案：[whats-new__2026-w36.md](whats-new__2026-w36.md)｜https://code.claude.com/docs/zh-TW/whats-new/2026-w36｜lastmod 2026-09-17｜7.3 KB
- 一句話：Fable 5.1、Desktop 背景 Computer use、/diff 即時面板、/skill-doctor。
- 何時讀：查 PreModelSwitch／PostModelSwitch hook、/skill-doctor、/cost 快取行、bypassPermissions 專案設定失效。
- 本週新功能清單：
  - Claude Fable 5.1（1M 上下文；`fable` 別名）
  - Desktop 背景 Computer use（macOS，Pro/Max beta）
  - 全螢幕 `/diff` 即時面板（v2.1.260）
  - `/skill-doctor`：每個 skill 的上下文成本與使用頻率（v2.1.261）
  - 其他：`PreModelSwitch`／`PostModelSwitch` hook、`/cost` 增 Prompt cache 行、`managedMcpServers`、effort 分模型儲存、auto mode 阻擋雲端中繼資料取憑證、工作目錄外首次讀取詢問、`bashOutputMaxChars`／`taskOutputMaxChars`（至 128000）、專案設定 `defaultMode: bypassPermissions` 不再生效
- 新名詞：``PreModelSwitch` hook` ＝ 模型切換前觸發，可阻擋；``/skill-doctor`` ＝ 列出各 skill 的上下文成本與使用率
- 記憶系統接點：新增模型切換前後 hook；/skill-doctor 量化 skill 描述的 context 成本（類似 atom 注入成本檢視）；output 上限可放寬到 128K 字元。

### 第 37 週 · 2026 年 9 月 7–11 日（`whats-new/2026-w37`）
- 檔案：[whats-new__2026-w37.md](whats-new__2026-w37.md)｜https://code.claude.com/docs/zh-TW/whats-new/2026-w37｜lastmod 2026-09-25｜5.2 KB
- 一句話：claude plugin eval 測試外掛、Desktop 窗格可彈出、maxEffortLevel。
- 何時讀：查 plugin eval、maxEffortLevel、WebFetch 逾時、--plugin-dir 資料夾載入多個。
- 本週新功能清單：
  - `claude plugin eval`：對一組案例評分並與無 plugin 基準比較，`eval init` 草擬案例（v2.1.269）
  - Desktop 窗格可彈出成獨立視窗再停靠
  - 其他：`maxEffortLevel` 限制各 provider 努力等級、WebFetch 5 分鐘逾時（`CLAUDE_CODE_WEBFETCH_DEADLINE_MS`）、`--plugin-dir` 可指向含多 plugin 的資料夾、`claude plugin install/...` 加 `--json`、auto mode 拒絕原因會點名規則、`/` 命令清單、VS Code 代理地圖
- 新名詞：`plugin eval` ＝ 對 plugin 跑測試案例、評分並與無 plugin 基準比較；``maxEffortLevel`` ＝ 限制努力等級上限的設定
- 記憶系統接點：plugin eval 可量測 plugin（含 hooks）貢獻；plugin 命令加 --json 便於自動化。

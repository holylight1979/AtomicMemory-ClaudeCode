# 05-configuration 導讀（Claude Code 官方文件 zh-TW）

> 共 26 頁，依 subsection 分組；原文在本資料夾同名 .md。機器索引見 `_keywords.json`。


## Settings（設定檔與鍵）

### 設定檔案和優先順序（`settings`）
- 檔案：[settings.md](settings.md)｜https://code.claude.com/docs/zh-TW/settings｜lastmod 2026-11-03｜46KB
- 一句話：講 settings.json 有哪幾個檔、誰讀得到、同一個鍵衝突時誰贏。
- 何時讀：要決定某個設定該放哪一層、或設定沒生效要查原因時。
- 關鍵內容：
  - 四個檔：使用者 `~/.claude/settings.json`、共享專案 `.claude/settings.json`、本機 `.claude/settings.local.json`、受管 `managed-settings.json`
  - 優先序高到低：受管 > 命令列 `--settings` > 專案本機 > 共享專案 > 使用者
  - 環境變數不是一層；哪個贏依每組設定個別決定（例：`ANTHROPIC_MODEL` 勝過 `model` 鍵）
  - 清單鍵（如 `permissions.allow`）跨檔合併而非覆寫；`fallbackModel`／`modelPicker`／`availableModels`／`modelSettings` 例外
  - 設定檔被監視並熱重載，每次偵測到檔案變更會觸發 `ConfigChange` hook；MDM／伺服器受管設定改按排程到達
  - 部分鍵只在啟動時讀一次（如 `model`、`effortLevel`），中途要用 `/model`、`/effort` 切換
  - 受管優先序有例外表：`disableClaudeAiConnectors`、`permissions.blockReadsOutsideWorkingDirectories`、`maxEffortLevel` 等採「任何層的較嚴值」
  - `/status` 看載入了哪些設定來源；`claude doctor` 看被丟棄的項目；雲端工作階段不讀使用者與本機設定
- 新名詞：`managed settings` ＝ 受管設定：組織部署、你的檔案蓋不掉的最高層設定；`settings scope` ＝ 設定範圍：某個檔案影響到哪些人／專案；`ConfigChange hook` ＝ 設定檔變更時觸發的 hook 事件
- 記憶系統接點：設定分層覆寫順序的正本：受管 > `--settings` > settings.local.json > .claude/settings.json > ~/.claude/settings.json；hooks 與 permissions 清單跨檔合併；設定檔變更會觸發 `ConfigChange` hook，hook 設定可熱重載。

### 設定檔範例（`settings-example`）
- 檔案：[settings-example.md](settings-example.md)｜https://code.claude.com/docs/zh-TW/settings-example｜lastmod 2026-10-22｜15KB
- 一句話：三份可直接複製的 settings.json：個人、團隊共享、組織受管。
- 何時讀：想看設定檔長什麼樣、抄一份起手式時。
- 關鍵內容：
  - 個人檔：`model`、`modelSettings`（每模型 effort）、`editorMode: vim`、`theme`、`statusLine`、`permissions.allow`、`cleanupPeriodDays: 20`
  - 團隊共享檔（`.claude/settings.json`，提交進版控）：權限、`PreToolUse` hook（`.claude/hooks/block-rm.sh`）、`enabledPlugins`、`extraKnownMarketplaces`、`sandbox`、`plansDirectory`
  - 團隊檔注意事項：允許規則等信任資料夾後才生效；遙測類環境變數在 repo 設定中被忽略
  - 組織受管檔：`forceLoginMethod`、`availableModels`、`permissions.deny`、`allowManagedPermissionRulesOnly`、`sandbox`、`requiredMinimumVersion`
  - 受管範例把 `cleanupPeriodDays` 縮到 7 天、`companyAnnouncements` 啟動時顯示訊息
  - 每份都有「可複製」與「逐鍵註解」兩個分頁；實際設定檔不接受註解
- 新名詞：無
- 記憶系統接點：範例含 hook 區塊的放置位置，可對照現有 settings.json 結構；檔內不可有註解。

### 所有設定（`settings-reference`）
- 檔案：[settings-reference.md](settings-reference.md)｜https://code.claude.com/docs/zh-TW/settings-reference｜lastmod 2026-11-04｜450KB
- 一句話：每個 settings.json 鍵的完整字典：位置、型別、預設值、單次覆寫方式。
- 何時讀：查某個設定鍵是否存在、預設值、可放哪個檔、被哪個環境變數覆蓋時。
- 關鍵內容：
  - 開頭有「設定索引」表（Key／說明／主題／範圍）；範圍＝任何檔案／使用者／受管／全域（全域鍵存 `~/.claude.json`）
  - 17 個主題章：模型與回應、權限、沙箱、記憶與上下文、介面與終端機、Git 和歸屬、Hook 與自動化、外掛與 skill、MCP、Agent／工作階段／worktree、遠端桌面通知、身分驗證、更新、工具、隱私與遙測、企業與受管、全域設定
  - 記憶與上下文：`autoCompactEnabled`、`autoCompactWindow`（100000～1000000）、`autoMemoryEnabled`、`autoMemoryDirectory`、`claudeMd`、`claudeMdExcludes`、`env`、`fileCheckpointingEnabled`、`idleCompaction`、`plansDirectory`、`bashOutputMaxChars`（4000～128000，預設 30000）
  - Hook 與自動化：`hooks`、`disableAllHooks`、`allowManagedHooksOnly`、`allowedHttpHookUrls`、`httpHookAllowedEnvVars`；逾時是各 hook 自己的 `timeout` 欄位，無全域鍵
  - 權限：`permissions.allow/ask/deny`、`defaultMode`（default／acceptEdits／plan／auto／dontAsk／bypassPermissions）、`disableAutoMode`、`blockReads/WritesOutsideWorkingDirectories`
  - 模型：`model`、`availableModels`、`effortLevel`、`modelSettings`、`fastMode`、`promptCacheTtl`（5m／1h）、`subagentPromptCacheTtl`、`advisorModel`
  - 隱私：`cleanupPeriodDays` 預設 30 天、不可設 0；企業：`policyHelper`（`path`／`timeoutMs`／`refreshIntervalMs`）
  - 多數鍵附「每個工作階段的覆蓋」：旗標或環境變數（如 `DISABLE_AUTO_COMPACT`、`CLAUDE_CODE_DISABLE_AUTO_MEMORY`）
- 新名詞：`idleCompaction` ＝ 閒置壓縮：人離開約一小時、提示快取過期前，先把長對話壓成摘要；`modelSettings` ＝ 每個模型各自存一份 effort 等級的設定；`policyHelper` ＝ 受管設定的輔助程式，啟動時執行以取得組織政策
- 記憶系統接點：影響 hook：`disableAllHooks`、`allowManagedHooksOnly`（只留受管 hook，且停用 `/goal`）、`allowedHttpHookUrls`；hooks 跨檔合併、受管 hook 無法被其他檔移除。影響 context：`autoCompactEnabled`／`autoCompactWindow`／`idleCompaction`／`promptCacheTtl`／`claudeMd`／`claudeMdExcludes`。`env` 區塊可設環境變數，專案與本機層會忽略路徑類與遙測類變數。`cleanupPeriodDays` 決定 transcript 保留天數（預設 30）。


## Permissions and sandboxing（權限與沙箱）

### 自動模式分類器請求費用（`auto-mode-classifier-billing`）
- 檔案：[auto-mode-classifier-billing.md](auto-mode-classifier-billing.md)｜https://code.claude.com/docs/zh-TW/auto-mode-classifier-billing｜lastmod 2026-10-30｜7KB
- 一句話：說明「此工作階段不符合 auto mode 免費分類器請求」通知的意思與處理。
- 何時讀：在 auto mode 看到分類器計費通知，或透過 LLM 閘道／代理使用時。
- 關鍵內容：
  - 原因通常是 Claude Code 與 API 之間有 LLM 閘道／代理，伺服器端檢查無法通過
  - 按 Enter 繼續：分類器請求照一般 token 計費，該工作階段不再提示
  - 按 Esc／Ctrl+C 取消：動作不執行，下次檢查前通知再出現
  - 解法一：請閘道原樣轉發請求與回覆欄位（含 `safeguards`）
  - 解法二：`CLAUDE_CODE_AUTO_MODE_SERVER=0`（暫時性設定，可能移除；直連 API 需 v2.1.281+）
  - 非互動模式不等回答，直接繼續以 auto 執行
- 新名詞：`server-side classifier check` ＝ 伺服器端分類器檢查：由 Anthropic 端審查動作，目前不對分類器請求計費
- 記憶系統接點：無

### 選擇權限模式（`permission-modes`）
- 檔案：[permission-modes.md](permission-modes.md)｜https://code.claude.com/docs/zh-TW/permission-modes｜lastmod 2026-11-03｜119KB
- 一句話：六種權限模式（default／acceptEdits／plan／auto／dontAsk／bypassPermissions）各自免問的範圍。
- 何時讀：要切模式、設預設模式、或搞懂 auto mode 為何暫停或擋了某操作時。
- 關鍵內容：
  - Shift+Tab 循環切換；`permissions.defaultMode` 設啟動模式；`--permission-mode` 單次覆寫
  - v2.1.283 起 auto 是互動終端與 VS Code 的內建起始模式
  - auto 由獨立分類器模型在動作前審查；連續 3 次或累計 20 次被擋就暫停並改回詢問（閾值不可設）
  - deny 規則在所有模式都生效，連 `bypassPermissions` 也擋
  - 任何模式都不自動核准：ask 規則、`AskUserQuestion`、關鍵路徑 `rm`、跨工作階段訊息等
  - 受保護路徑（`.git`、`.vscode`、`.idea`、`.husky`、`.cargo`、`.devcontainer`、`.config/git`）寫入不自動核准，bypass 除外
  - `dontAsk`：把會提示的一律拒絕，只留預先核准的工具
  - `bypassPermissions` 只該用在隔離容器／VM；`permissions.disableBypassPermissionsMode`、`disableAutoMode` 可禁用
- 新名詞：`auto mode` ＝ 自動模式：不問例行權限，改由背景分類器模型逐一審查動作；`classifier` ＝ 分類器：審查動作是否超出你的請求範圍的獨立模型；`critical path` ＝ 關鍵路徑：如 `/`、`~` 的刪除，任何模式都不放行；`dontAsk mode` ＝ 一律拒絕未預先核准的操作，不提示；`protected paths` ＝ 受保護路徑：寫入永遠要確認的目錄清單
- 記憶系統接點：PreToolUse hook 的 allow 無法核准關鍵路徑 rm 與 ask 規則；`~/.claude/` 與專案 `.claude/` 的寫入屬受保護路徑，需確認（有專屬選項允許本工作階段編輯）；`-p` 與無人可答的場景遇到會提示的操作直接拒絕。

### 設定權限（`permissions`）
- 檔案：[permissions.md](permissions.md)｜https://code.claude.com/docs/zh-TW/permissions｜lastmod 2026-11-02｜90KB
- 一句話：細粒度權限規則：allow／ask／deny 的語法、各工具怎麼比對、與 hook 的優先序。
- 何時讀：要寫或除錯 `permissions` 規則、搞懂 deny 為何擋不掉或擋太多時。
- 關鍵內容：
  - 規則評估順序固定：deny → ask → allow，第一個符合者決定結果，不看特異性
  - 規則語法 `Tool(specifier)`，支援萬用字元；Bash、PowerShell、Read／Edit、WebFetch、MCP、Agent、Cd 各有比對細節
  - `/permissions` 看所有規則與來源檔；裸 `Bash` deny 會把工具整個從 Claude 的上下文移除
  - PreToolUse hook 的 allow 不能繞過 deny／ask 規則；hook 以 exit code 2 阻擋會先於 allow 規則
  - plan mode 下 hook 的 allow 對非唯讀呼叫無效
  - 任一層的 deny 都勝過其他層的 allow；受管 deny 連 `--allowedTools` 也蓋不掉
  - 信任資料夾前不會執行 repo 內 hook、`env`、`apiKeyHelper`；`claude -p` 不顯示信任對話框
  - 工作目錄外存取：`permissions.additionalDirectories`、`blockReadsOutsideWorkingDirectories`
- 新名詞：`permission rule` ＝ 權限規則：寫成 `Bash(git diff *)` 這種形式的允許／詢問／拒絕條目；`workspace trust` ＝ 工作區信任：首次進資料夾時問你是否信任，決定 repo 內設定能不能生效；`mod` ＝ 外掛的一種，程式碼可註冊 hook，也能參與工具核准（`tool.check`）
- 記憶系統接點：hook 與權限的優先序有明文：PreToolUse 回 allow 不蓋過 deny／ask；exit 2 的阻擋先於 allow 規則；plan mode 中 hook allow 失效；信任資料夾前專案 hook 不跑。

### 選擇沙箱環境（`sandbox-environments`）
- 檔案：[sandbox-environments.md](sandbox-environments.md)｜https://code.claude.com/docs/zh-TW/sandbox-environments｜lastmod 2026-10-25｜19KB
- 一句話：比較隔離方案：沙箱 Bash、sandbox runtime、dev container、容器、VM、雲端工作階段。
- 何時讀：要為無人值守或不信任的程式碼選隔離層級時。
- 關鍵內容：
  - 沙箱 Bash 僅限制 shell 命令，不需 Docker
  - sandbox runtime 隔離整個 Claude Code 行程（含檔案工具、MCP、hook）
  - dev container 用 `.devcontainer/`；官方範例含預設拒絕的 iptables 防火牆
  - VM 隔離最強（獨立核心）；雲端工作階段由 Anthropic 託管
  - 無特權容器內疊沙箱需 `enableWeakerNestedSandbox`
  - 隔離不改變送往模型的內容；允許出站網路仍可能外洩可讀資料
- 新名詞：`sandbox runtime` ＝ 把整個 Claude Code 行程（不只 Bash）關進沙箱的獨立執行方式
- 記憶系統接點：只有 sandbox runtime／容器／VM 這類包住整個行程的方案才能涵蓋 hook 與 MCP。

### 設定沙箱化的 Bash 工具（`sandboxing`）
- 檔案：[sandboxing.md](sandboxing.md)｜https://code.claude.com/docs/zh-TW/sandboxing｜lastmod 2026-11-04｜110KB
- 一句話：設定沙箱化 Bash：用 OS 層級限制 shell 命令能讀寫的檔案與連的網域。
- 何時讀：想讓命令在較少提示下安全執行、或除錯沙箱擋掉的命令時。
- 關鍵內容：
  - `/sandbox` 開啟，預設關閉；支援 macOS、Linux、WSL2；原生 Windows 不沙箱化
  - 只涵蓋 Bash／PowerShell／Monitor；檔案工具、MCP 伺服器、hook 在沙箱外執行
  - 預設可寫：工作目錄與暫存；可讀：機器大部分；網路：全經代理，允許網域起始為空
  - 兩種模式：auto-allow（沙箱內命令免問）與一般權限模式
  - 非沙箱重試逃生口：`dangerouslyDisableSandbox`；`allowUnsandboxedCommands: false` 關閉成嚴格模式
  - 設定鍵：`sandbox.enabled`、`filesystem.allowWrite/denyRead`、`network.allowedDomains`、`excludedCommands`、`credentials.*`
  - 受管設定強制沙箱時，repo 檔案中放寬沙箱的設定會被忽略
  - 底層是開源套件 `@anthropic-ai/sandbox-runtime`
- 新名詞：`sandboxed Bash tool` ＝ 沙箱化 Bash 工具：把 shell 命令關進 OS 層級邊界；`auto-allow mode` ＝ 沙箱內執行的命令自動核准；`unsandboxed retry` ＝ 沙箱內失敗時，經核准後在沙箱外重跑；`credential masking` ＝ 遮罩憑證：讓沙箱內命令拿不到真實密鑰
- 記憶系統接點：沙箱不涵蓋 hook 與 MCP，hook 腳本仍以完整權限執行；沙箱設定與權限規則共用分層覆寫（受管 > 使用者 > 專案）。


## Model and responses（模型與回應）

### 使用顧問工具升級困難決策（`advisor`）
- 檔案：[advisor.md](advisor.md)｜https://code.claude.com/docs/zh-TW/advisor｜lastmod 2026-10-21｜17KB
- 一句話：顧問工具：主模型在關鍵時刻諮詢更強的顧問模型（實驗性）。
- 何時讀：長任務想在規劃、卡關或宣告完成前讓更強模型把關時。
- 關鍵內容：
  - 三種啟用：`/advisor <model>`、`advisorModel` 設定、`--advisor` 旗標；`/advisor off` 關閉
  - 僅 Anthropic API；Bedrock、Claude Platform on AWS、Google Cloud Agent Platform、Foundry 不可用
  - 顧問收到完整對話記錄；顧問端不快取，每次呼叫全新處理
  - 中途開關顧問不會讓主模型提示快取失效
  - 費用：API 計費按顧問模型費率；訂閱計入用量限制
  - `CLAUDE_CODE_DISABLE_ADVISOR_TOOL=1` 完全停用；`DISABLE_TELEMETRY` 會讓功能旗標抓不到而關閉
- 新名詞：`advisor tool` ＝ 顧問工具：伺服器端第二個較強模型，在決策點被主模型諮詢
- 記憶系統接點：與子代理、opusplan、`/model` 並列為多模型協作手段；顧問呼叫不影響主對話快取。

### 使用快速模式加快回應速度（`fast-mode`）
- 檔案：[fast-mode.md](fast-mode.md)｜https://code.claude.com/docs/zh-TW/fast-mode｜lastmod 2026-11-02｜22KB
- 一句話：快速模式：同一個 Opus 以高速配置回應，最高約 2.5 倍快、每 token 更貴。
- 何時讀：要即時迭代想加速，或要了解快速模式費用與限制時。
- 關鍵內容：
  - `/fast` 切換，或使用者設定 `"fastMode": true`；提示旁出現 `↯` 圖示
  - 價格：Opus 5.5 為 $8/$40 MTok，Opus 5 與 4.8 為 $10/$50 MTok
  - 訂閱方案僅走用量點數、不計入訂閱速率限制
  - Opus 4.8 的快速模式 2026-11-30 移除；Opus 4.7 已移除
  - 開啟當下要為整段上下文付快速未快取輸入價，建議一開工就開
  - `fastModePerSessionOptIn: true` 要求每個工作階段重新選擇加入
  - 遇速率限制會自動退回標準速度並冷卻，到期後自動重開
- 新名詞：`fast mode` ＝ 快速模式：Opus 的高速付費配置，非另一個模型
- 記憶系統接點：首次開啟快速模式要重付整段上下文的未快取輸入費，性質與換模型相近。

### 模型設定（`model-config`）
- 檔案：[model-config.md](model-config.md)｜https://code.claude.com/docs/zh-TW/model-config｜lastmod 2026-11-03｜130KB
- 一句話：模型選擇、別名、effort 等級、1M 上下文、自動壓縮視窗與模型相關環境變數。
- 何時讀：要換模型、限制可選模型、調 effort、或調整 context 壓縮門檻時。
- 關鍵內容：
  - 別名：`default`、`best`、`fable`、`sonnet`、`opus`、`haiku`、`sonnet[1m]`、`opus[1m]`、`opusplan`
  - 優先序：`--model` > `ANTHROPIC_MODEL` > `model` 鍵；`/model` 中途切換（每個模型各有提示快取）
  - `availableModels`／`deniedModels`／`enforceAvailableModels` 限制可選模型；`modelOverrides` 對應閘道 ID
  - 自動壓縮視窗：`/autocompact`、`autoCompactWindow`、`--autocompact`、`CLAUDE_CODE_AUTO_COMPACT_WINDOW`，範圍 100K～1M token
  - 原生 1M 視窗模型預設約 967K token 時壓縮；`CLAUDE_CODE_DISABLE_1M_CONTEXT=1` 退回 200K
  - 未知模型 ID 假定 200K，可用 `[1m]` 後綴或 `CLAUDE_CODE_MAX_CONTEXT_TOKENS` 校正
  - `CLAUDE_CODE_SUBAGENT_MODEL` 指定子代理模型；effort 等級 low／medium／high／xhigh／max
  - 含「環境變數」章與版本歷史
- 新名詞：`effort level` ＝ 推理力度等級，越高越慢越貴越聰明；`opusplan` ＝ plan mode 用 Opus、執行時切 Sonnet 的混合模式；`extended context` ＝ 延伸上下文：1M token 視窗；`auto-compact window` ＝ 上下文填到多滿才自動壓縮
- 記憶系統接點：context 管理核心頁：`autoCompactWindow`／`DISABLE_AUTO_COMPACT`／`CLAUDE_CODE_AUTO_COMPACT_WINDOW` 決定壓縮時機；切模型會使提示快取失效；`CLAUDE_CODE_SUBAGENT_MODEL` 影響子代理成本。

### 輸出樣式（`output-styles`）
- 檔案：[output-styles.md](output-styles.md)｜https://code.claude.com/docs/zh-TW/output-styles｜lastmod 2026-10-27｜17KB
- 一句話：輸出樣式：用一組指令改變 Claude 的角色、語氣與回應格式。
- 何時讀：想讓整個工作階段固定某種回應風格，或寫自訂樣式時。
- 關鍵內容：
  - 內建：預設、Proactive、Concise、Explanatory、Learning
  - `/output-style <name>` 或 `/config` 切換，也可設 `outputStyle` 鍵
  - 自訂樣式是 Markdown + frontmatter，放 `~/.claude/output-styles`、`.claude/output-styles` 或受管目錄
  - frontmatter：`name`、`description`、`keep-coding-instructions`、`force-for-plugin`
  - 自訂樣式預設省略內建軟體工程指令，除非 `keep-coding-instructions: true`
  - 只是指令不是強制；必須每次發生的事要用 hook
- 新名詞：`output style` ＝ 輸出樣式：整場工作階段套用的回應風格指令檔；`keep-coding-instructions` ＝ 保留內建寫程式指令的 frontmatter 開關
- 記憶系統接點：輸出樣式每個請求都送出，增加輸入 token（快取可降低）；文中把「必須發生」歸 hook、「專案知識」歸 CLAUDE.md、「任務流程」歸 skill。


## Interface（介面）

### 使用 Claude Code 搭配螢幕閱讀器（`accessibility`）
- 檔案：[accessibility.md](accessibility.md)｜https://code.claude.com/docs/zh-TW/accessibility｜lastmod 2026-10-27｜14KB
- 一句話：螢幕閱讀器模式與其他無障礙設定（放大鏡、減少動畫、色盲主題）。
- 何時讀：使用 VoiceOver／NVDA，或需要減少動畫與調色時。
- 關鍵內容：
  - 開啟：`claude --ax-screen-reader`、`CLAUDE_AX_SCREEN_READER=1`、或使用者設定 `axScreenReader: true`
  - 專案設定無法開啟此模式（防止 repo 改變你的介面）
  - 模式改為純文字、線性輸出，不用方框與就地重繪
  - 其他選項：`prefersReducedMotion`、色盲友善主題、`CLAUDE_AX_STARTUP_QUIET_MS`、`CLAUDE_AX_PREPARK_MS`
  - 啟動第一行顯示 `[Screen Reader Mode: on via flag|env|settings]`
  - 含已知限制與回報管道章
- 新名詞：`screen reader mode` ＝ 螢幕閱讀器模式：把介面換成可被朗讀的純文字行
- 記憶系統接點：無

### 全螢幕渲染（`fullscreen`）
- 檔案：[fullscreen.md](fullscreen.md)｜https://code.claude.com/docs/zh-TW/fullscreen｜lastmod 2026-10-21｜32KB
- 一句話：全螢幕渲染：用終端替代螢幕緩衝區畫介面，無閃爍、記憶體平穩、支援滑鼠。
- 何時讀：長對話閃爍、捲動亂跳，或想用滑鼠選取／捲動時。
- 關鍵內容：
  - `/tui fullscreen` 啟用並重啟，對話保留；或 `CLAUDE_CODE_NO_FLICKER=1 claude`
  - `tui` 設定可設為預設全螢幕
  - 支援滑鼠點擊、滾輪捲動、自動跟隨；JetBrains 終端與 tmux 有專章
  - 搜尋與檢視對話、差異面板、清除對話的操作
  - 保留原生文字選取的做法與疑難排解（過時文字、啟動失敗計數）
  - 螢幕閱讀器模式一律用經典渲染器；為研究預覽功能
- 新名詞：`fullscreen rendering` ＝ 全螢幕渲染：像 vim 那樣接管終端繪製，不是最大化視窗；`alternate screen buffer` ＝ 終端的替代螢幕緩衝區
- 記憶系統接點：無

### 自訂鍵盤快捷鍵（`keybindings`）
- 檔案：[keybindings.md](keybindings.md)｜https://code.claude.com/docs/zh-TW/keybindings｜lastmod 2026-10-24｜41KB
- 一句話：自訂鍵盤快捷鍵：`keybindings.json` 的上下文、動作、按鍵語法與保留鍵。
- 何時讀：想改按鍵、加和弦快捷鍵、或解決與 tmux 等終端快捷鍵衝突時。
- 關鍵內容：
  - `/keybindings` 建立／開啟 `~/.claude/keybindings.json`；變更自動偵測，免重啟
  - 結構：`bindings` 陣列，每塊有 `context` 與「按鍵→動作」對應；`null` 取消綁定
  - 動作命名如 `chat:externalEditor`；有「可用動作」總表
  - 支援和弦（多鍵序列）與修飾鍵語法
  - 保留不可改：Ctrl+C、Ctrl+D、Ctrl+M、Ctrl+[、Ctrl+I、Ctrl+H、Caps Lock
  - 終端衝突：Ctrl+B（tmux）、Ctrl+A（screen）、Ctrl+Z（SIGTSTP）
  - 含 Vim 模式互動與驗證章
- 新名詞：`chord` ＝ 和弦：先按一組鍵再按下一組的多步快捷鍵；`keybinding context` ＝ 綁定的作用範圍，例如 Chat
- 記憶系統接點：無

### 自訂您的狀態列（`statusline`）
- 檔案：[statusline.md](statusline.md)｜https://code.claude.com/docs/zh-TW/statusline｜lastmod 2026-10-30｜66KB
- 一句話：自訂狀態列：寫個腳本讀 stdin 的 JSON 工作階段資料，輸出要顯示的文字。
- 何時讀：想在提示下方顯示模型、context 用量、費用、git 狀態、速率限制時。
- 關鍵內容：
  - 設定 `statusLine: {type:"command", command, padding, refreshInterval}`；本機執行，不耗 API token
  - 觸發：新助理訊息、`/compact` 完成、權限模式變更、Vim 模式切換、`refreshInterval` 計時、速率限制重設
  - 300ms 去抖動；舊腳本還在跑時新觸發會取消它
  - stdin JSON 欄位：`model`、`workspace`、`cost`、`context_window.used_percentage`、`rate_limits`、`prompt_cache`、`session_id`、`transcript_path`
  - 可輸出多行、ANSI 顏色、OSC 8 連結；讀 `COLUMNS`／`LINES` 取得寬度
  - `subagentStatusLine` 為子代理面板每列自訂內容
  - 受 `disableAllHooks`／`allowManagedHooksOnly`／不信任資料夾限制
- 新名詞：`status line` ＝ 狀態列：提示下方由你的腳本產生的資訊列；`OSC 8` ＝ 終端機可點連結的逸出序列
- 記憶系統接點：狀態列拿得到 `context_window.used_percentage`、`transcript_path`、`session_id`（資料形狀近似 hook 輸入）；與 hook 共用 `disableAllHooks` 與信任閘。

### 為 Claude Code 設定您的終端機（`terminal-config`）
- 檔案：[terminal-config.md](terminal-config.md)｜https://code.claude.com/docs/zh-TW/terminal-config｜lastmod 2026-10-29｜28KB
- 一句話：設定終端機：換行、Option 鍵、鈴聲通知、tmux、主題、貼上、Vim 編輯。
- 何時讀：Shift+Enter 沒換行、通知沒聲音、tmux 異常或要自訂主題時。
- 關鍵內容：
  - 換行：Ctrl+J 或 `\` 後 Enter；VS Code／Cursor／Zed 等跑一次 `/terminal-setup`
  - 通知：`preferredNotifChannel`（如 `terminal_bell`）；iTerm2、Ghostty、Kitty 有桌面通知
  - 可用 Notification hook 播放音效
  - tmux 設定、Windows 上 Backspace 刪整個單詞的修法
  - 自訂色彩主題（含 `light-daltonized` 色盲友善）
  - `maxProseWidth` 限制寬終端的回應寬度；大段貼上會摺疊，可刪除與回想
  - Vim 快捷鍵編輯提示詞（`editorMode: vim`）
- 新名詞：`terminal-setup` ＝ `/terminal-setup`：把 Shift+Enter 寫進終端設定檔的指令
- 記憶系統接點：提到可用 Notification hook 播放提示音，屬通知事件的 hook 應用。

### 語音聽寫（`voice-dictation`）
- 檔案：[voice-dictation.md](voice-dictation.md)｜https://code.claude.com/docs/zh-TW/voice-dictation｜lastmod 2026-10-22｜18KB
- 一句話：語音聽寫：按住或點擊錄音，把語音轉成提示文字。
- 何時讀：想用說的輸入提示，或排查麥克風與語言問題時。
- 關鍵內容：
  - `/voice` 切換；`/voice hold`、`/voice tap`、`/voice off`；預設按住空白鍵錄音
  - 音訊串流到 Anthropic 伺服器轉錄，需 Claude.ai 帳戶登入
  - 不可用於雲端工作階段與 SSH；WSL 需 WSLg
  - 轉錄不耗訊息額度，不計入 `/usage`
  - 可變更聽寫語言、可重新繫結聽寫鍵
  - VS Code 擴充功能也支援；Linux 原生模組失敗會退回 `arecord`／`rec`
- 新名詞：`hold-to-record` ＝ 按住錄音：按著鍵說話、放開即停
- 記憶系統接點：無


## Environments（環境）

### 設定雲端環境（`cloud-environments`）
- 檔案：[cloud-environments.md](cloud-environments.md)｜https://code.claude.com/docs/zh-TW/cloud-environments｜lastmod 2026-11-02｜65KB
- 一句話：設定雲端工作階段的環境：網路存取層級、環境變數、設定指令碼與快取。
- 何時讀：要讓雲端工作階段連特定網域、預裝相依套件或理解雲端與本機差異時。
- 關鍵內容：
  - 網路四層級：None、Trusted（預設，套件庫與 GitHub 等允許清單）、Custom、Full
  - 每個工作階段是全新 Ubuntu 24.04 x86_64 VM；只含 repo 內已提交的內容
  - 設定指令碼以 root 在 Claude 啟動前執行：須 exit 0、約 5 分鐘內完成才會被環境快取
  - SessionStart hook 在 Claude 啟動後每次（含恢復）執行，本機與雲端皆跑；`command` hook 預設 600 秒逾時，可設 `timeout`
  - 使用者層級 `~/.claude/settings.json` 的 hook 不會帶到雲端；多 repo 工作階段不載入 repo hook
  - 命令逾時：預設前景 2 分鐘、最多 10 分鐘，可設 `BASH_DEFAULT_TIMEOUT_MS`／`BASH_MAX_TIMEOUT_MS`
  - `CLAUDE_CODE_REMOTE=true` 可判斷是否在雲端；`/remote-env` 從 CLI 選環境
- 新名詞：`cloud environment` ＝ 雲端環境：雲端工作階段的網路、環境變數、設定指令碼組合；`environment caching` ＝ 環境快取：把設定指令碼跑完的檔案系統快照重用；`setup script` ＝ 設定指令碼：雲端 VM 啟動時先跑的 Bash
- 記憶系統接點：SessionStart hook 在雲端與本機都跑，有 600 秒預設逾時與 `timeout` 欄位；使用者層 hook 不隨雲端帶走，repo 層 `.claude/settings.json` 才會。

### 自託管環境（`self-hosted-environments`）
- 檔案：[self-hosted-environments.md](self-hosted-environments.md)｜https://code.claude.com/docs/zh-TW/self-hosted-environments｜lastmod 2026-10-30｜22KB
- 一句話：自託管環境總覽：雲端工作階段改在你自己網路內的 runner 上執行。
- 何時讀：評估是否把 Claude Code 雲端工作階段放到自家基礎設施時。
- 關鍵內容：
  - 三部件：環境（命名目的地）、執行器 runner（跑工作階段的程式）、工作階段
  - Team／Enterprise 公開測試版，預設關閉，由擁有者在管理頁開啟
  - 不適用零資料保留與 HIPAA 組織
  - 模型推理預設仍走 Anthropic，可設為送 Bedrock 或 Agent Platform
  - 使用量計入組織 Claude Code 使用量
  - 終端或 IDE 工作階段本來就在本機，與此無關；常駐機器遠端驅動用 Remote Control
- 新名詞：`self-hosted environment` ＝ 自託管環境：由你營運 runner 的雲端工作階段目的地；`runner` ＝ 執行器：認領並執行工作階段的程式，概念同 CI runner；`orchestrator` ＝ 協調器：依需求自動擴縮 runner 的程序
- 記憶系統接點：無

### 在自託管環境中自訂工作階段（`self-hosted-environments-configuration`）
- 檔案：[self-hosted-environments-configuration.md](self-hosted-environments-configuration.md)｜https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration｜lastmod 2026-11-03｜102KB
- 一句話：自訂自託管工作階段：包裝指令碼、生命週期 hook、隨需 runner、Bedrock、MCP 與權限。
- 何時讀：要在 runner 上注入憑證、換簽出方式、自動擴縮或核准工具時。
- 關鍵內容：
  - 包裝指令碼 wrapper 可為每個工作階段注入憑證與環境
  - 生命週期 hook 以 `--hooks-dir` 或 `SELF_HOSTED_RUNNER_HOOKS_DIR` 指定，在 runner 上圍繞工作階段（如 checkout）
  - checkout hook 收 `CLAUDE_RUNNER_REPO_URL`／`REPO_REF`／`CHECKOUT_PATH` 等變數，須留下含 `.git` 的工作樹
  - 隨需 runner：自動擴縮協調器
  - 可把模型請求送 Amazon Bedrock 或 Agent Platform
  - 含 MCP 伺服器與權限／工具核准章；runner 主機 `~/.claude/` 內的 hook 與受管設定會被執行
- 新名詞：`lifecycle hook` ＝ 生命週期 hook：runner 端階段腳本，不同於會話內的 Claude Code hook
- 記憶系統接點：明確區分 runner 生命週期 hook 與工作階段內 Claude Code hook；runner 主機 `~/.claude/` 植入的 hook 與 settings 在自託管工作階段生效。

### 將自託管環境部署到生產環境（`self-hosted-environments-deploy`）
- 檔案：[self-hosted-environments-deploy.md](self-hosted-environments-deploy.md)｜https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy｜lastmod 2026-11-03｜131KB
- 一句話：把自託管部署到生產：強化、網路、git 設定、映像、K8s／Compose、關閉時序、擴展。
- 何時讀：規劃自託管上線、安全強化或排錯時。
- 關鍵內容：
  - runner 會執行模型導向的任意程式碼，建議每工作階段一個臨時容器／VM（`--capacity 1`）
  - 映像中不放長期 SSH 金鑰或雲端憑證
  - 含網路要求與出站控制章；git 設定可由映像提供
  - 提供 Kubernetes 與 Docker Compose 部署範式
  - CPU／記憶體調整、關閉時序、預熱簽出重用、版本固定、擴展群
  - 已知問題與疑難排解長章
- 新名詞：無
- 記憶系統接點：無

### 在自託管環境中驗證工作階段身分（`self-hosted-environments-identity`）
- 檔案：[self-hosted-environments-identity.md](self-hosted-environments-identity.md)｜https://code.claude.com/docs/zh-TW/self-hosted-environments-identity｜lastmod 2026-10-29｜18KB
- 一句話：驗證自託管工作階段身分：驗證 `CLAUDE_CODE_SESSION_ACCESS_TOKEN` 這個 JWT。
- 何時讀：要讓內網服務信任來自 Claude 工作階段的請求時。
- 關鍵內容：
  - 工作階段令牌是 JWT，證明 Anthropic 為某環境的某工作階段簽發，不證明是哪個行程出示
  - 令牌在環境變數中，工作階段內任何程式碼都讀得到
  - 須驗證 `aud` 聲明等於環境 ID（`ccpool_...`）
  - 章節：令牌內容、驗證步驟、聲明參考、範圍衍生認證、相關環境變數
- 新名詞：`session access token` ＝ 工作階段存取令牌：JWT，用於自託管工作階段向服務自證身分
- 記憶系統接點：無

### 自託管環境快速入門（`self-hosted-environments-quickstart`）
- 檔案：[self-hosted-environments-quickstart.md](self-hosted-environments-quickstart.md)｜https://code.claude.com/docs/zh-TW/self-hosted-environments-quickstart｜lastmod 2026-10-28｜17KB
- 一句話：自託管快速入門：裝 Claude Code、建環境、啟動 runner、送第一個工作階段。
- 何時讀：第一次架自託管 runner 時照著走。
- 關鍵內容：
  - 先決條件：Team／Enterprise、擁有者權限、可連 Anthropic API 的主機
  - 步驟：安裝 Claude Code → 在管理頁建環境 → 啟動 runner → 派發工作階段
  - 可對執行中工作階段傳送後續訊息
  - 章節末附後續閱讀指引
- 新名詞：無
- 記憶系統接點：無

### 自託管環境參考（`self-hosted-environments-reference`）
- 檔案：[self-hosted-environments-reference.md](self-hosted-environments-reference.md)｜https://code.claude.com/docs/zh-TW/self-hosted-environments-reference｜lastmod 2026-11-03｜59KB
- 一句話：自託管 runner 與協調器的完整參考：CLI 旗標、環境變數、遙測、健康端點、Prometheus 指標。
- 何時讀：查 runner 旗標預設值、監控指標或健康檢查端點時。
- 關鍵內容：
  - runner 旗標多有對應環境變數，同時設定時旗標優先
  - 例：`--base-dir`（預設 `/workspace`）、`--capacity`（預設 1）、`--configure-git`、`--confine-repo-settings`（預設 `warn`）
  - 有協調器旗標、僅環境變數設定表
  - 遙測、健康端點與 Prometheus 指標長表
- 新名詞：無
- 記憶系統接點：無

### 端對端測試自託管環境（`self-hosted-environments-testing`）
- 檔案：[self-hosted-environments-testing.md](self-hosted-environments-testing.md)｜https://code.claude.com/docs/zh-TW/self-hosted-environments-testing｜lastmod 2026-10-10｜17KB
- 一句話：端對端測試自託管 runner：用 Stop hook 擷取回應，從 CI 派發工作階段驗證。
- 何時讀：要在 CI 驗證 runner 映像是否正常時。
- 關鍵內容：
  - 在測試 runner 的 `~/.claude/settings.json` 裝 Stop hook，取 stdin JSON 的最終助理訊息
  - hook 腳本存 `~/.claude/hooks/e2e-stop-hook-capture.sh`
  - 用 CLI 派發工作階段並讀回結果的測試迴圈
  - 附範例腳本、遠端測試 runner 與 CI 驗證做法、專用測試環境
- 新名詞：無
- 記憶系統接點：示範以 Stop hook 讀取最終助理訊息（stdin JSON 內含 `last_assistant_message`）作為擷取通道。

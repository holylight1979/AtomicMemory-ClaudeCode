# 03-plugins 導讀（Plugin / Marketplace / Mods / Evals）

> 本資料夾共 31 頁，依 subsection 分組；每頁一張卡。機器索引見 `_keywords.json`。

## Plugins

### Plugins 概述（`plugins/overview`）
- 檔案：[plugins__overview.md](plugins__overview.md)｜https://code.claude.com/docs/zh-TW/plugins/overview｜lastmod 2026-10-28｜14.3 KB
- 一句話：Plugin 是把 skills/agents/hooks/MCP 打包成一個單位安裝的目錄；說明何時該用它。
- 何時讀：第一次接觸 plugin、想判斷要不要用 plugin 而不是單獨 skill 時。
- 關鍵內容：
  - plugin ＝含元件的目錄，manifest 在 `.claude-plugin/plugin.json`
  - 元件：skills、agents、hooks、hook 模組(mod)、MCP servers
  - 已啟用 plugin 的 skill/agent 名稱與描述每回合都佔 context
  - `/plugin` 的 Discover 標籤安裝；`claude plugin disable` 可停用
  - 生效三層：設定(enabledPlugins)→磁碟 `~/.claude/plugins/`→工作階段
  - 安裝範圍：user / project(.claude/settings.json) / local
  - marketplace 分官方、社群、第三方三層；雲端工作階段不載入本機 plugin
- 新名詞：`plugin` ＝ 一包可安裝的擴充元件目錄；`marketplace` ＝ 列出 plugin 與取得位置的目錄檔(marketplace.json)，不是商店；`manifest` ＝ plugin.json，替 plugin 命名並放中繼資料；`mod` ＝ 帶有 hook 模組(JS 事件處理)的 plugin
- 記憶系統接點：plugin 可封裝 skills/agents/hooks/MCP/設定；啟用後名稱與描述每回合佔 context，hooks 與 MCP 隨每個工作階段啟動。

## Use plugins

### Anthropic 的市集（`plugins/anthropic-marketplaces`）
- 檔案：[plugins__anthropic-marketplaces.md](plugins__anthropic-marketplaces.md)｜https://code.claude.com/docs/zh-TW/plugins/anthropic-marketplaces｜lastmod 2026-10-28｜8.7 KB
- 一句話：列出 Anthropic 官方與社群 marketplace 的名稱、儲存庫與取得方式。
- 何時讀：想知道官方 plugin 來源、`@claude-community` 怎麼加、舊 `claude-code-plugins` 怎麼遷移時。
- 關鍵內容：
  - 官方：`anthropics/claude-plugins-official`，名稱 `claude-plugins-official`
  - 社群：`anthropics/claude-plugins-community`，名稱 `claude-community`，需手動 add
  - 首次互動啟動自動新增官方；`CLAUDE_CODE_DISABLE_OFFICIAL_MARKETPLACE_AUTOINSTALL` 可關
  - `claude-code-plugins` 已棄用；`ralph-wiggum` 改名 `ralph-loop`
  - 指令：`/plugin marketplace add anthropics/claude-plugins-community`
  - 第三方 marketplace 未經 Anthropic 審查
  - 另有 `anthropics/skills`、`anthropics/knowledge-work-plugins` 主題市集
- 新名詞：`official marketplace` ＝ Anthropic 維護並預設自動註冊的 plugin 目錄；`community marketplace` ＝ 第三方作者提交的目錄 claude-community
- 記憶系統接點：無

### Code intelligence plugins（`plugins/code-intelligence`）
- 檔案：[plugins__code-intelligence.md](plugins__code-intelligence.md)｜https://code.claude.com/docs/zh-TW/plugins/code-intelligence｜lastmod 2026-10-02｜11.5 KB
- 一句話：安裝語言伺服器(LSP) plugin，讓 Claude 編輯後看到型別錯誤並按符號導覽。
- 何時讀：想讓 Claude 看診斷訊息、遇到 LSP 外掛建議對話框、或需自行接 LSP 時。
- 關鍵內容：
  - plugin 只告訴 Claude Code 啟動命令與副檔名，不含語言伺服器二進位檔
  - 13 種語言對照表，例：C# 用 `csharp-lsp`+`csharp-ls`、Python 用 `pyright-lsp`
  - 安裝：`/plugin install typescript-lsp@claude-plugins-official`
  - 首次編輯相符副檔名檔案時才啟動；成功顯示 `Found N new diagnostic issues`
  - `/plugin` 的 Errors 標籤顯示 `Executable not found in $PATH`
  - 建議對話框每 session 一次；忽略 5 次或 30 秒逾時即停推薦
  - 重開建議：刪 `~/.claude.json` 的 `lspRecommendationDisabled` 等鍵
  - 無官方 plugin 的語言可自寫 `.lsp.json`
- 新名詞：`LSP` ＝ Language Server Protocol，語言伺服器協定，提供診斷與跳定義；`code intelligence plugin` ＝ 把 LSP 接進 Claude Code 的 plugin
- 記憶系統接點：LSP 診斷在編輯後以 `Found N new diagnostic issues` 回饋；plugin 可包含 `.lsp.json` 元件。

### 安裝和管理外掛程式（`plugins/install`）
- 檔案：[plugins__install.md](plugins__install.md)｜https://code.claude.com/docs/zh-TW/plugins/install｜lastmod 2026-10-28｜32.1 KB
- 一句話：安裝、啟用、停用、更新、卸載 plugin 與管理 marketplace 的完整操作。
- 何時讀：要安裝/移除/更新 plugin、選 scope、設自動更新、或看 claude.ai 同步 plugin 時。
- 關鍵內容：
  - `/plugin install <name>@<marketplace>` 先開詳情面板再選 scope
  - scope：user→`~/.claude/settings.json`、project→`.claude/settings.json`、local→`settings.local.json`
  - `claude plugin install formatter@x --scope project` 可在 shell 裝；`-p` 下 `/plugin` 不可用
  - claude.ai 帳戶 plugin 同步為 `<name>@synced`
  - 有依賴的 plugin：裝/啟用連帶處理，卸載後以 `claude plugin prune` 清孤兒
  - 官方市集預設自動更新，其餘預設關；`Update now`/`claude plugin update`
  - `claude plugin details <name>` 看 Always-on token 數
  - 移除 marketplace 會一併卸載其 plugin
- 新名詞：`scope` ＝ 安裝範圍：誰能啟用這個 plugin；`synced plugin` ＝ 由 claude.ai 帳戶同步下來的 plugin，ID 結尾 @synced；`defaultEnabled` ＝ manifest 欄位，false 表示裝了也預設關閉
- 記憶系統接點：enabledPlugins 依 user/project/local 設定檔分層；plugin 啟用變更要 /reload-plugins 才進現有 session。

### Plugin 安全性和信任（`plugins/security`）
- 檔案：[plugins__security.md](plugins__security.md)｜https://code.claude.com/docs/zh-TW/plugins/security｜lastmod 2026-10-28｜14.4 KB
- 一句話：說明 plugin 能在你機器上做什麼、如何安裝前檢查與移除。
- 何時讀：評估是否信任某 plugin/marketplace，或要查看官方名稱與遙測可見度時。
- 關鍵內容：
  - hooks/monitors/MCP/LSP/mod 以完整使用者權限在沙箱外執行
  - `bin/` 目錄會被加入 Bash 工具的 PATH
  - 自動更新會在背景改動磁碟上已檢查過的檔案
  - 官方名稱僅接受 `github.com/anthropics/` 來源，社群目錄 SHA 固定
  - 安裝前檢視：`claude plugin marketplace list`、`/plugin` 的 Will install、`claude plugin details`
  - 卸載後檔案留在 `~/.claude/plugins/cache/` 14 天
  - 遙測：官方層名稱原樣、其他為 third-party；`OTEL_LOG_TOOL_DETAILS=1` 可揭露
  - 受管設定 `pluginTrustMessage` 可附加信任警語
- 新名詞：`trust tier` ＝ marketplace 分官方/社群/第三方三層；`sha256 pin` ＝ archive 來源用摘要固定，下載不符即拒絕
- 記憶系統接點：plugin 的 hooks/MCP/monitors 不受權限規則與沙箱約束；hooks 以使用者權限跑；skills/agents 內容會進 context 當指令。

## Create plugins

### 使用 evals 測試 plugins（`plugin-evals`）
- 檔案：[plugin-evals.md](plugin-evals.md)｜https://code.claude.com/docs/zh-TW/plugin-evals｜lastmod 2026-10-14｜63.0 KB
- 一句話：用 `claude plugin eval` 為 plugin 寫測試案例、評分、對照無 plugin 基準並可在 CI 擋關。
- 何時讀：要量化 plugin 是否可靠改變 Claude 行為、防迴歸、或把分數接進 CI 時。
- 關鍵內容：
  - 需 Claude Code v2.1.269+；案例放 plugin 內 `evals/<case>/prompt.md` 與 `graders/*.md`
  - 每案例預設跑 3 次；`--threshold` 預設 1.0；`--runs`、`-j` 並行 1–8
  - grader 六型：regex、tool_used、tool_order、file_exists、llm(三票取二)、baseline
  - WITH / W/OUT 雙 arm，Δ ＝ plugin 貢獻；`--ablation with-without`
  - `claude plugin eval init` 互動產生案例；`--max-cost-usd` 控預算
  - 隔離執行：一次性 home，只載目標 plugin，不讀個人 hooks/CLAUDE.md/記憶
  - CI 退出碼：0 通過、1 失敗、2 部分(超預算/認證)、130 中斷；`--trust-plugin --json`
  - MCP 預設用 mock（`mocks/`），`--allow-real-servers` 才連真伺服器
- 新名詞：`eval suite` ＝ 一組針對 plugin 的測試案例；`grader` ＝ 對 Claude 產出評分的規則(regex、tool_used、llm 等)；`baseline arm` ＝ 不載 plugin 的對照組，用來算 plugin 增益Δ；`mock` ＝ 假 MCP 伺服器回應，讓測試不連真服務
- 記憶系統接點：eval 在隔離的 `claude -p` 子 session 跑，不載使用者設定/CLAUDE.md/記憶；grader 可檢查工具呼叫與檔案；可用於驗證 skill 是否被觸發。

### 從您的 CLI 推薦您的外掛程式（`plugins/cli-hints`）
- 檔案：[plugins__cli-hints.md](plugins__cli-hints.md)｜https://code.claude.com/docs/zh-TW/plugins/cli-hints｜lastmod 2026-09-25｜6.5 KB
- 一句話：CLI/SDK 作者在 stderr 輸出 claude-code-hint 標籤，提示使用者裝官方市集 plugin。
- 何時讀：維護自家 CLI 並想在 Claude Code 內推薦對應 plugin 時。
- 關鍵內容：
  - 標籤：`<claude-code-hint v="1" type="plugin" value="name@claude-plugins-official" />`
  - 只在 `CLAUDECODE` 或 `CLAUDE_CODE_CHILD_SESSION` 有設時輸出（後者需 v2.1.172+）
  - 標籤須獨佔一行並寫到 stderr，Claude Code 會在模型看到前移除
  - 僅限官方市集 plugin，不適用 claude-community
  - 每 session 每 plugin 一次，單機最多提示 100 個 plugin
  - `claude -p`、子代理、hook 輸出內標籤會被移除不提示
  - 關閉遙測(`DISABLE_TELEMETRY`等)或第三方提供者的 session 不提示
- 新名詞：`claude-code-hint` ＝ CLI 輸出的標籤，讓 Claude Code 推薦安裝 plugin
- 記憶系統接點：Bash/PowerShell 工具與 hook 命令的環境變數有 `CLAUDECODE=1`；hook 命令輸出中的 hint 標籤會被剝除。

### 新增元件至外掛程式（`plugins/components`）
- 檔案：[plugins__components.md](plugins__components.md)｜https://code.claude.com/docs/zh-TW/plugins/components｜lastmod 2026-10-25｜40.1 KB
- 一句話：逐一說明 plugin 可含的每種元件：skills、agents、hooks、MCP、LSP、monitors、主題等。
- 何時讀：要在 plugin 裡加某一類元件、查預設位置與命名規則、或用 userConfig/路徑變數時。
- 關鍵內容：
  - skill 命令名 `/<plugin>:<dir>`；根目錄 `CLAUDE.md` 不會被載入
  - agent 名 `my-plugin:security-reviewer`；frontmatter 忽略 hooks/mcpServers/permissionMode
  - hooks 於 plugin 載入時註冊，`hooks/hooks.json` 與 manifest `hooks` 合併
  - hook 環境有 `CLAUDE_PLUGIN_ROOT`、`CLAUDE_PLUGIN_DATA`、`CLAUDE_PLUGIN_OPTION_<KEY>`
  - MCP 名 `plugin:<plugin>:<server>`，工具 `mcp__plugin_<plugin>_<server>__<tool>`
  - plugin 根 `settings.json` 僅 `agent`、`subagentStatusLine` 生效，優先序最低
  - monitors 為背景 shell 命令，沙箱外執行，`-p` 不啟動
  - `userConfig` 欄位 `sensitive:true` 存安全儲存；`/plugin configure`
  - `${CLAUDE_PLUGIN_DATA}`＝`~/.claude/plugins/data/<id>/` 更新後保留
- 新名詞：`userConfig` ＝ manifest 宣告、安裝時向使用者收集的設定值；`monitor` ＝ 隨 session 常駐的背景命令，輸出以通知進 Claude；`channel` ＝ 讓外部聊天系統推訊息進 session 的 MCP 伺服器綁定；`CLAUDE_PLUGIN_DATA` ＝ 更新後仍保留的 plugin 持久資料目錄
- 記憶系統接點：plugin 內 hooks 可用 hooks.json 封裝，事件與設定檔 hooks 相同；hook 命令可取 CLAUDE_PLUGIN_ROOT/DATA 路徑；MCP 工具名帶 plugin 前綴供 matcher 比對；sensitive userConfig 存安全儲存而非 settings.json。

### 建立 Claude Code 外掛程式（`plugins/create`）
- 檔案：[plugins__create.md](plugins__create.md)｜https://code.claude.com/docs/zh-TW/plugins/create｜lastmod 2026-10-28｜26.2 KB
- 一句話：從空目錄做出第一個 plugin、不用 marketplace 就能測試，並轉換既有 .claude/ 設定。
- 何時讀：要寫新 plugin、用 --plugin-dir 載入測試、或把獨立 skills/hooks 搬進 plugin 時。
- 關鍵內容：
  - 佈局：`.claude-plugin/plugin.json`、`skills/`、`agents/`、`hooks/hooks.json`、`.mcp.json`
  - plugin 元件加前綴：`/my-plugin:hello`，避免同名衝突
  - `claude --plugin-dir ./p`（可重複，支援 .zip 與 plugins 資料夾）
  - `--plugin-url`、`CLAUDE_CODE_PLUGIN_DIRS` 為其他單 session 載入法
  - `claude plugin init my-tool` 在 `~/.claude/skills/` 搭建每 session 載入的 plugin
  - 只有 plugin.json 放 `.claude-plugin/` 內，元件放根目錄
  - `claude plugin validate` 檢查；`/reload-plugins` 重載
  - 轉換 .claude/：搬 skills/agents/hooks 並加 manifest
- 新名詞：`--plugin-dir` ＝ 單一 session 從目錄載入 plugin 的旗標；`skills-dir plugin` ＝ 放在 ~/.claude/skills/ 且帶 plugin.json 的 plugin，ID 為 @skills-dir；`plugin root` ＝ plugin 自己的目錄，非 ~/.claude
- 記憶系統接點：既有 .claude/ 的 skills/agents/hooks/.mcp.json 可原樣搬入 plugin 根目錄；plugin 根的 CLAUDE.md 不載入，須寫成 skill。

### 外掛程式相依性（`plugins/dependencies`）
- 檔案：[plugins__dependencies.md](plugins__dependencies.md)｜https://code.claude.com/docs/zh-TW/plugins/dependencies｜lastmod 2026-10-14｜16.4 KB
- 一句話：宣告 plugin 依賴與 semver 版本範圍，說明安裝、解析與修剪行為。
- 何時讀：要做 plugin 組合包、鎖依賴版本、或遇到 conflicting version requirements 時。
- 關鍵內容：
  - `plugin.json` 的 `dependencies`：字串或 `{name,version,marketplace}`
  - 版本範圍如 `~2.1.0`、`^2.0`，對 git 標籤 `<name>--v<version>` 解析
  - `claude plugin tag` 建發行標籤；無標籤符合則安裝失敗
  - 多 plugin 範圍取交集最高版；不重疊報 `has conflicting version requirements`
  - 跨 marketplace 依賴需 `allowCrossMarketplaceDependenciesOn` 允許
  - 只有 name+dependencies 的 plugin 可當團隊組合包
  - `claude plugin list` 顯示解析版本含 12 字元 commit 後綴
  - claude.ai 同步載入時依賴須同樣由 claude.ai 或市集滿足
- 新名詞：`dependency` ＝ 此 plugin 運作所需、須同時啟用的其他 plugin；`bundle plugin` ＝ 只含依賴清單、用來一次裝一組 plugin 的 plugin；`release tag` ＝ 格式 name--vX.Y.Z 的 git 標籤，供版本範圍解析
- 記憶系統接點：plugin 依賴宣告在 manifest，安裝/啟用時自動連帶安裝同 scope，停用時被需要者會拒絕；/reload-plugins 會補裝缺的依賴。

### 測量外掛程式成本和使用情況（`plugins/measure`）
- 檔案：[plugins__measure.md](plugins__measure.md)｜https://code.claude.com/docs/zh-TW/plugins/measure｜lastmod 2026-10-30｜13.2 KB
- 一句話：量測 plugin 的 token 成本與使用情況，並選對組織層遙測事件。
- 何時讀：想知道 plugin 佔多少 context、是否還有人用，或要查 OTel/Analytics 事件時。
- 關鍵內容：
  - `claude plugin details <name>` 顯示 Always-on 與 per-component token 估計
  - Always-on ＝名稱＋description＋when_to_use；hooks、MCP 不計入
  - 降成本：縮短描述、拆分 plugin
  - `/plugin` Installed 的 Not used recently：14 天且 10 個 session 未用
  - `/skill-doctor`、`/doctor`、`/usage` 皆能看未用或用量份額
  - OTel 事件：`claude_code.plugin_installed`、`plugin_loaded`、`skill_activated`、`hook_plugin_metrics`
  - 非官方 plugin 名稱預設遮蔽，`OTEL_LOG_TOOL_DETAILS=1` 取得真名
- 新名詞：`Always-on cost` ＝ plugin 每個 session 固定增加的 token 數；`Context cost` ＝ 官方市集 plugin 安裝前顯示的 token 估計
- 記憶系統接點：plugin 的名稱與描述屬 always-on context 成本；有 OTel 事件可統計 plugin 載入/skill 啟動；hooks 不吃模型 context。

### 發佈和分發外掛程式（`plugins/publish`）
- 檔案：[plugins__publish.md](plugins__publish.md)｜https://code.claude.com/docs/zh-TW/plugins/publish｜lastmod 2026-10-30｜17.0 KB
- 一句話：三種發佈路線：直接給資料夾、自建 marketplace、提交 Anthropic 目錄，附發行前檢查表。
- 何時讀：準備把 plugin 發給別人、決定名稱/版本策略、或要重新命名/移除已發佈 plugin 時。
- 關鍵內容：
  - 三路線：無市集(送資料夾/.zip)、自有 marketplace、Anthropic 目錄
  - 名稱是永久識別碼，改名會讓舊安裝失效；用 `renames` 對應遷移
  - `version` 固定則使用者留在舊版，省略則追蹤 commit
  - 發行前：`claude plugin validate --strict`、本機 marketplace 試裝、跑 `claude plugin eval`
  - 目錄提交：開發者入口 claude.ai/directory/manage，需付費方案
  - 目錄上架者在 claude.ai 安裝後於 Claude Code 為 `<name>@synced`
  - `claude plugin tag --push` 建 `{name}--v{version}` 標籤
- 新名詞：`directory` ＝ claude.ai 上供 claude.ai/Cowork 使用者瀏覽的 plugin 目錄；`renames map` ＝ marketplace.json 內舊名→新名的遷移對應
- 記憶系統接點：無

## Run a marketplace

### 建立 marketplace（`plugins/create-marketplace`）
- 檔案：[plugins__create-marketplace.md](plugins__create-marketplace.md)｜https://code.claude.com/docs/zh-TW/plugins/create-marketplace｜lastmod 2026-10-28｜15.6 KB
- 一句話：用 marketplace.json 建立自己的 plugin 市集，並在本機測試後再託管。
- 何時讀：要為團隊/組織建一個 plugin 目錄、寫 marketplace.json、本機驗證時。
- 關鍵內容：
  - `.claude-plugin/marketplace.json` 必填 `name`、`owner`、`plugins`
  - 每個 plugin 項目需 `name` 與 `source`；相對路徑 `./plugins/x` 從 marketplace 根解析
  - `claude plugin validate ./my-marketplace` 檢查 JSON、命名、`..` 路徑
  - 本機測試：`claude plugin marketplace add ./my-marketplace`
  - 項目名須與 plugin 內 manifest 名一致
  - 官方保留名稱會在 add 時被拒絕
  - 推到 git 主機後同事 `claude plugin marketplace add <owner>/<repo>`
  - `claude plugin marketplace remove` 同時卸載其 plugin
- 新名詞：`marketplace root` ＝ 含 .claude-plugin/ 的目錄，相對來源由此解析；`plugin entry` ＝ marketplace.json 中描述單一 plugin 與來源的物件
- 記憶系統接點：無

### 託管和維護市集（`plugins/host-marketplace`）
- 檔案：[plugins__host-marketplace.md](plugins__host-marketplace.md)｜https://code.claude.com/docs/zh-TW/plugins/host-marketplace｜lastmod 2026-10-26｜38.7 KB
- 一句話：託管與維護 marketplace：選主機、私有存取、更新發佈、重命名與移除。
- 何時讀：要把 marketplace 放上 GitHub/URL/共享目錄、設私有存取、發新版、做發佈頻道時。
- 關鍵內容：
  - 主機：GitHub、其他 git、`marketplace.json` URL、共享目錄
  - `marketplace add owner/repo#ref` 可固定分支/標籤；`--scope project` 提交 .claude/settings.json
  - URL 託管限制：marketplace.json 5 MiB/10 秒；archive zip 256 MiB/120 秒
  - 私有 repo 靠使用者機器現有 git 憑證，無提示；GitHub 先探測 SSH 再 HTTPS
  - 自動更新預設關，需使用者或管理員 `autoUpdate:true`
  - 發佈頻道＝兩個 marketplace 指向同 plugin 不同 `ref`
  - 改名用 `renames`，移除用 `forceRemoveDeletedPlugins`
  - archive 下載可設 `headers`/`headersHelper`
- 新名詞：`release channel` ＝ 用兩個 marketplace 指向不同 ref 實現的穩定/搶先版；`headersHelper` ＝ 印出短期憑證標頭的命令，用於受保護下載；`command source` ＝ 由執行命令產生 plugin 目錄的來源
- 記憶系統接點：marketplace 可由 `.claude/settings.json` 的 extraKnownMarketplaces 登錄給整個 repo；自動更新與憑證處理在背景以使用者機器 git 執行。

### 為您的組織推薦 plugins（`plugins/relevance`）
- 檔案：[plugins__relevance.md](plugins__relevance.md)｜https://code.claude.com/docs/zh-TW/plugins/relevance｜lastmod 2026-10-26｜12.6 KB
- 一句話：在 marketplace 項目加 relevance 訊號，讓 Claude Code 在工作符合時建議安裝 plugin。
- 何時讀：要讓組織 plugin 在適當情境被主動推薦，或管理員要啟用建議時。
- 關鍵內容：
  - 項目加 `relevance: {topic, signals}`；至少設一個 signal 才會建議
  - signals：`cwd`、`cli`、`hosts`、`filesRead`、`manifestDeps`（各最多 10 條）
  - 比對全在本機，不回報 Anthropic；永不自動安裝
  - 建議位置：spinner 提示、session 開始通知(僅 cwd)、`/plugin` Discover 置頂
  - 管理員於受管設定 `pluginSuggestionMarketplaces` 加入允許，並宣告來源
  - `spinnerTipsEnabled:false` 會關建議
  - `claude plugin validate` 驗證 relevance 區塊
- 新名詞：`relevance` ＝ marketplace 項目上的相關性規則，決定何時推薦該 plugin；`signal` ＝ 相關性比對條件，如工作目錄、讀過的檔案、執行過的命令
- 記憶系統接點：relevance 訊號會看 Claude 讀寫的檔案路徑、自動載入的 CLAUDE.md 與執行的 shell 命令名稱（本機比對）。

## Manage plugins for your organization

### 為您的組織管理 mods（`plugins/mods/admin`）
- 檔案：[plugins__mods__admin.md](plugins__mods__admin.md)｜https://code.claude.com/docs/zh-TW/plugins/mods/admin｜lastmod 2026-10-26｜41.5 KB
- 一句話：管理員用受管設定管控 mods：禁用使用者 mod、僅允許自家 mod、審查能力、以 mod 強制政策。
- 何時讀：要決定組織是否放行 mod、如何檢查 mod 能做什麼、或寫政策 mod 時。
- 關鍵內容：
  - `pluginConfigs."cc-plugin-sec-default@builtin".options.allowManagedModsOnly: true` 阻擋使用者 mod
  - 內建防護 `sec-default@builtin` 在使用者 mod 前載入，使用者無法關
  - 受管 `PreToolUse` hook 先於 mod `tool.call`；deny 規則預設優先於 mod 核准
  - `allowModsToOverrideDenyRules` 可放寬；`disableAllHooks` 連受管 hook 一併關
  - `claude plugin validate` 的 `calls:` 行可審查 `$.fs`/`$.process`/`$.http.fetch` 等
  - `prependPlugins`/`appendPlugins` 排列組織自家 mod 順序
  - 政策 mod 用 `plugin.register` 事件回 `{refuse}` 拒絕其他 mod
  - mods 不受沙箱，WebFetch 政策仍涵蓋 `$.http.fetch`
- 新名詞：`allowManagedModsOnly` ＝ 只允許組織自家 mod 的防護選項；`policy mod` ＝ 用 plugin.register 事件檢查並拒絕其他 mod 的組織 mod
- 記憶系統接點：受管 PreToolUse hook 在 mod 鏈之前執行；mod 可由組織設定控制與審計；plugin.register 事件可程式化審查他人 mod 的呼叫清單。

### 為您的組織管理 Claude Code 外掛程式（`plugins/org`）
- 檔案：[plugins__org.md](plugins__org.md)｜https://code.claude.com/docs/zh-TW/plugins/org｜lastmod 2026-11-02｜40.8 KB
- 一句話：用受管設定控管組織內 plugin：預裝、強制啟用、白/黑名單、更新政策與稽核。
- 何時讀：管理員要為整隊預裝 plugin、限制來源、種子容器/CI、或查控制矩陣時。
- 關鍵內容：
  - `extraKnownMarketplaces` + `enabledPlugins`（`name@marketplace`）預裝；`false` 可阻擋並隱藏
  - 三種受管來源：伺服器受管設定、MDM、`managed-settings.json`；預設第一個有效者生效，`managedSourcesBehavior:"merge"` 可合併
  - `strictKnownMarketplaces` 白名單、`blockedMarketplaces` 黑名單
  - `disableSideloadFlags` 關 --plugin-dir/--plugin-url；`allowManagedHooksOnly`、`strictPluginOnlyCustomization`
  - `syncClaudeAiPlugins:false` 停止 claude.ai plugin 載入
  - `CLAUDE_CODE_PLUGIN_SEED_DIR` 預填 plugin 目錄(唯讀)供容器/CI
  - `-p`/CI 背景安裝可能首輪缺 plugin，`CLAUDE_CODE_SYNC_PLUGIN_INSTALL=1`
  - 更新：`DISABLE_AUTOUPDATER`、`FORCE_AUTOUPDATE_PLUGINS`
- 新名詞：`managed settings` ＝ 管理員下發、使用者無法覆蓋的設定；`seed directory` ＝ 預先放好 marketplace 與 plugin 的唯讀目錄；`control matrix` ＝ 列出各政策金鑰能做與不能做之事的表
- 記憶系統接點：受管設定可強制 enabledPlugins、限制 hooks 只來自受管/強制 plugin；各 surface(終端/-p/雲端)套用時機不同；種子目錄供離線環境。

## Mods

### 使用 mods API（`plugins/mods/api`）
- 檔案：[plugins__mods__api.md](plugins__mods__api.md)｜https://code.claude.com/docs/zh-TW/plugins/mods/api｜lastmod 2026-11-02｜40.4 KB
- 一句話：mods API 用法：加命令/工具、呼叫模型、背景計時、跨 session 訊息、檔案/程序/網路。
- 何時讀：要在 mod 內加 /command、定時工作、傳訊給其他 session 或讀寫檔案時。
- 關鍵內容：
  - `$.command.register`、`$.tool.register` 於 `session.start` 註冊
  - `$.model.complete` 呼叫模型，可用提示快取；`maxTokens` 預設 1024
  - `$.clock.every(60_000, fn)` 背景計時；`$.ui.status` 顯示於提示下
  - `$.session.send({to:{sessionId}, text})` 跨 session 傳純文字
  - `$.fs`、`$.process.run`、`$.http.fetch`、`$.mcp.call`、`$.env`、`$.settings.read`
  - hook 模組無 Node API/`setTimeout`，一切經 `$`
  - `claude -p` 下被拒的呼叫與永不結束的處理
- 新名詞：`$.store` ＝ 機器上所有 session 共用的 JSON 鍵值儲存；`session.send` ＝ 把訊息送到另一個 session/subagent 的 API
- 記憶系統接點：$.store 為跨 session 共用的鍵值儲存(上限 4 MiB)；$.session.send/receive 可做 session 間訊息；$.settings.read、$.fs 可讀寫本機檔案。

### 建立 mod（`plugins/mods/create`）
- 檔案：[plugins__mods__create.md](plugins__mods__create.md)｜https://code.claude.com/docs/zh-TW/plugins/mods/create｜lastmod 2026-10-25｜24.4 KB
- 一句話：請 Claude 寫 mod，或自己寫、驗證、改版、測試與分享一個 mod。
- 何時讀：要做第一個 mod、用熱重載迭代、或查 TypeScript 型別定義時。
- 關鍵內容：
  - 對 Claude 描述需求，內建 skill `plugin-authoring` 會寫 mod
  - Claude 寫的 mod 放 session 的 mod 資料夾，需批准並可啟用熱重載
  - `claude --plugin-dir ./first-mod` 載入並於儲存時重載
  - `claude plugin validate ./first-mod` 列 `hooks:`/`calls:`，事件拼錯會報錯
  - Claude Code 自動寫 `claude-code/index.d.ts` 型別與 `tsconfig.json`
  - `claude -p`、`dontAsk` 下 Claude 寫的 mod 不載入（無人批准）
  - 分享：放進 marketplace，或 `--plugin-dir` 載入
- 新名詞：`hot reload` ＝ 儲存或回合結束時重新載入 mod，不必重開 session；`plugin-authoring` ＝ 教 Claude 寫 mod 的內建 skill
- 記憶系統接點：mod 的 hook 檔案用 `$.xxx.yyy` 完整寫法才能被靜態分析；內建 skill 可由 Claude 代寫。

### 使用 mod 回應事件（`plugins/mods/events`）
- 檔案：[plugins__mods__events.md](plugins__mods__events.md)｜https://code.claude.com/docs/zh-TW/plugins/mods/events｜lastmod 2026-10-27｜37.4 KB
- 一句話：從 mod 處理 Claude Code 事件：觀察、重寫、回答；包含工具、提示、回合與其他 mod 的順序。
- 何時讀：要攔截/批准工具呼叫、改寫提示、追蹤回合，或處理 hook 失敗與順序時。
- 關鍵內容：
  - hook 收 `$`、`e`、`next`；三種動作：觀察、重寫(`next({...e})`)、回答(`{deny}`/`{result}`)
  - 事件過濾器(matcher)，如 `{ tool: 'Bash' }`
  - `tool.call` 可 `{deny}`、`{result}`；`tool.check` 在 PreToolUse 之後決定放行
  - `prompt.submit` 可改 `text`/`context` 或 `{drop}`
  - 鏈順序：內建防護→使用者 mod→appendPlugins→其他內建；受管 PreToolUse 在第一個 mod 前
  - hook 失敗：`next` 前失敗則略過；用 `.catch` 與 `next.called` 可 fail-closed
  - `settings.read` hook 可改或拒絕設定讀取
- 新名詞：`middleware chain` ＝ hook 以 next 串成的處理鏈，最後到達 Claude Code 自身行為；`fail closed` ＝ hook 失敗時預設拒絕而非放行
- 記憶系統接點：mod 事件鏈與設定檔 `PreToolUse` hook 有固定交錯順序（受管 hook 最先）；`prompt.submit`/`prompt.context`/`prompt.compose` 可注入或改寫送入模型的文字；失敗可 fail-closed。

### Mod 介面圖庫（`plugins/mods/gallery`）
- 檔案：[plugins__mods__gallery.md](plugins__mods__gallery.md)｜https://code.claude.com/docs/zh-TW/plugins/mods/gallery｜lastmod 2026-10-27｜21.9 KB
- 一句話：展示 mod 能畫的介面元素與範例程式碼：文字、按鈕、欄位、Markdown、程式碼、差異、圖片。
- 何時讀：想挑選要用哪種元素、複製範例碼，或看各元素在終端的樣子時。
- 關鍵內容：
  - 分類：文字(Text/Markdown/Link)、程式碼(Code)、排版(Box)
  - 輸入：Button、Input、Select
  - 圖片：Raster、Svg、Image、Client
  - `Code` 可顯示 diff
  - `Image` 在 tmux 內有特殊繪製方式
  - 範例皆畫在 Pane，其他位置另見 interface 頁
- 新名詞：`Raster` ＝ 以彩色儲存格網格繪圖的元素；`Client` ＝ 在 mod 內嵌自訂 UI 模組的元素
- 記憶系統接點：無

### 使用 mod 在介面中繪製（`plugins/mods/interface`）
- 檔案：[plugins__mods__interface.md](plugins__mods__interface.md)｜https://code.claude.com/docs/zh-TW/plugins/mods/interface｜lastmod 2026-11-02｜52.6 KB
- 一句話：從 mod 在 Claude Code 介面繪製窗格、提示上方橫帶、按鈕、輸入欄與保存狀態。
- 何時讀：要做側邊窗格/橫帶、處理按鍵、重繪時機，或跨 /clear 保存狀態時。
- 關鍵內容：
  - 繪製位置(render site)：`Pane`、`AbovePrompt` 橫帶、Spinner、ToolUse 等
  - `$.ui.open({id})` 開窗格；`ui.render` hook 以 `{component:'Pane'}` 過濾
  - 元素：Box、Text、Button、Input、Select、Code、Markdown、Link、Image、Raster
  - 可互動元素需 `key`；`ui.press`/`ui.input` 事件
  - 重繪：`$.ui.invalidate`，節流每秒 10 次(可見處 30 次)
  - 狀態三層：模組變數(重載即失)、`$.state`(session)、`$.store`(跨 session)
  - `$.state` 需在 `types/index.d.ts` 宣告
  - 多 session 寫 `$.store` 非原子，需各自鍵或寫前重讀
- 新名詞：`render site` ＝ 介面上 mod 可介入繪製的位置；`pane` ＝ 文字記錄旁或提示上方的 mod 側邊/內嵌面板；`band` ＝ 提示上方所有 mod 共享的橫條
- 記憶系統接點：mod 可用 `$.state`(session 存活)、`$.store`(跨 session 持久)保存資料；介面僅為顯示層，不影響記憶注入。

### Mods 概覽（`plugins/mods/overview`）
- 檔案：[plugins__mods__overview.md](plugins__mods__overview.md)｜https://code.claude.com/docs/zh-TW/plugins/mods/overview｜lastmod 2026-10-20｜25.7 KB
- 一句話：Mod 是在 Claude Code 內執行 JS 事件處理的 plugin，可繪製介面、加命令、改工具呼叫。
- 何時讀：想了解 mod 能做什麼、如何安裝/信任/關閉，以及與設定 hook 的差別時。
- 關鍵內容：
  - mod ＝ plugin + `hooks/hooks.json` 的 `modules` + hook 模組(`register(on)`)
  - hook 可觀察、重寫或回答事件，鏈式 `next(e)`
  - mod 在 Claude Code 行程內跑、不受沙箱；可讀環境變數、改提示與工具呼叫
  - `claude plugin validate <dir>` 列出 `hooks:` 與 `calls:` 不需執行
  - 關閉：停用 plugin、`--safe-mode`、`"disableAllHooks": true`
  - 需 Claude Code v2.1.287+（Desktop v2.1.286+）；預設開啟
  - `/plugin` 顯示 `1 mod active · first-mod`
  - 範例 mod：token-weather、blast-radius、replay-theater
- 新名詞：`mod` ＝ 帶 hook 模組、能在 Claude Code 內改介面與行為的 plugin；`hook module` ＝ 匯出 register(on) 的 JS/TS 檔，註冊事件處理函式；`mods API` ＝ hook 收到的 `$`，提供 ui/command/tool/model/fs/process 等方法
- 記憶系統接點：mod hook 與設定檔 hooks 並行；mod 可在 prompt.submit、session.start、tool.call 等事件介入（含 prompt.context 注入），並可 $.session.send 傳訊給其他 session。

### Mods 參考資料（`plugins/mods/reference`）
- 檔案：[plugins__mods__reference.md](plugins__mods__reference.md)｜https://code.claude.com/docs/zh-TW/plugins/mods/reference｜lastmod 2026-11-04｜48.8 KB
- 一句話：Mods 完整參考：檔案、hook 函式簽章、全部事件、mods API 方法、渲染位置、元素、限制、設定。
- 何時讀：查某個事件名、API 方法、數字限制或相關設定鍵時。
- 關鍵內容：
  - 必要檔：`plugin.json`、`hooks/hooks.json`(`modules`)、hook 模組；測試 `*.test.ts`
  - 事件群：工具、提示、命令與設定、回合、session、subagent、介面、其他 mod、遙測
  - API 命名空間：`$.ui/command/tool/agent/model/prompt/session/fs/store/state/process/mcp`
  - 限制：hook 10 秒(prompt.edit 50ms)、`$.process.run` 預設 30 秒、檔案 4 MiB
  - 設定：`prependPlugins`、`appendPlugins`、`allowManagedModsOnly`、`allowModsToOverrideDenyRules`、`pluginConfigs`
  - `CLAUDE_CODE_PLUGIN_DIR_WATCH=1` 讓 `-p` 長時 session 熱重載
  - 內建防護 `sec-default@builtin`
- 新名詞：`sec-default@builtin` ＝ 內建於 Claude Code、先於使用者 mod 載入的防護 mod；`tier` ＝ mod 的來源層級(core/builtin/append/user)
- 記憶系統接點：事件含 session.start/end/compact、prompt.submit/compose/context、tool.call/check、agent.spawn、session.receive/send、session.measure；可對應記憶注入與收尾時機。

### 測試 mod（`plugins/mods/test`）
- 檔案：[plugins__mods__test.md](plugins__mods__test.md)｜https://code.claude.com/docs/zh-TW/plugins/mods/test｜lastmod 2026-10-26｜26.7 KB
- 一句話：為 mod 寫自動化測試：觸發事件、stub Claude Code 回答、模擬按鈕，無需 session 或網路。
- 何時讀：要為 mod 寫 `.test.ts`、跑 `claude plugin test` 或測計時器/繪圖時。
- 關鍵內容：
  - `claude plugin test [dir]` 執行 `*.test.ts(x)`，失敗退出碼 1
  - 從 `claude-code/testing` 匯入 `test`、`expect`
  - `on('tool.call', () => ({result:'ok'}))` stub 答案；須在首次呼叫 `$` 前註冊
  - `session.start` 不會自動跑，需 `$.session.start(...)` 觸發
  - 單一測試上限 5 秒，可設 `timeoutMs`
  - 支援測計時器、繪圖、`/clear` 後重繪、策略型 mod
- 新名詞：`stub` ＝ 測試中代替 Claude Code 回答事件的假處理函式
- 記憶系統接點：無

### 排除 mod 的故障（`plugins/mods/troubleshoot`）
- 檔案：[plugins__mods__troubleshoot.md](plugins__mods__troubleshoot.md)｜https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot｜lastmod 2026-11-03｜38.5 KB
- 一句話：診斷 mod 沒作用：依症狀/訊息找原因、拒絕訊息對照、讀偵錯日誌。
- 何時讀：mod 安裝了卻沒反應、看到 `hooks module not loaded`、`hook skipped` 等訊息時。
- 關鍵內容：
  - 先 `claude plugin validate` 看 Claude Code 讀到什麼；再用 `claude --debug` 看日誌
  - `claude plugin test` 於空目錄檢查 mod 能否載入（`hooks modules are turned off here`）
  - 拒絕原因：`disableAllHooks`、`allowManagedHooksOnly`、`--bare`、同名 plugin 先載
  - 內建防護訊息：`tried to lift a deny rule`、`mods are limited to your organization's`
  - hook 被略過：`hook skipped`、`it crashed the hooks worker`
  - `a hook changed this call's input after the model wrote it` 工具呼叫被拒
  - 繪圖問題：`needs a key`、`is drawn twice`、`plugin panel hidden`
  - 遠端 rollout switch 可關閉已安裝 mod
- 新名詞：`rollout switch` ＝ Anthropic 遠端開關，可關閉已安裝 mod；`hooks worker` ＝ 執行 mod hook 的獨立工作行程
- 記憶系統接點：mod 載入受 disableAllHooks、allowManagedHooksOnly、--bare 等設定與旗標影響；警告訊息與日誌寫入偵錯日誌或文字記錄。

## Reference

### Plugin 命令參考（`plugins/cli-reference`）
- 檔案：[plugins__cli-reference.md](plugins__cli-reference.md)｜https://code.claude.com/docs/zh-TW/plugins/cli-reference｜lastmod 2026-10-28｜64.3 KB
- 一句話：claude plugin 殼層命令、/plugin 與 /reload-plugins 的完整參考，以及單 session 載入旗標。
- 何時讀：要查某個子命令旗標、結束碼、JSON 輸出、或 /plugin 子命令對照時。
- 關鍵內容：
  - 子命令：init、install、uninstall、enable、disable、update、list、details、configure、prune、eval、tag、test、validate
  - marketplace 子命令：add/list/remove/update；`claude plugins` 為別名
  - 結束碼：成功 0、失敗 1；validate 意外錯誤 2
  - `--scope user|project|local`；`install --config KEY=VALUE`、`--json`、`-y`
  - `plugin eval` 旗標：`--runs`、`--threshold`、`--max-cost-usd`、`--allow-tools`、`--trust-plugin`
  - `/plugin` 別名 `/plugins`、`/marketplace`；非互動不可用
  - `/reload-plugins [--force]` 印 `Reloaded: N plugins · N skills · N hooks …`
  - `--plugin-dir`/`--plugin-url` 載入的 plugin ID 為 `@inline`
- 新名詞：`@inline` ＝ 用 --plugin-dir/--plugin-url 載入的 session 專用 plugin 的來源標記；`/reload-plugins` ＝ 不重啟就套用待處理 plugin 變更的命令
- 記憶系統接點：/reload-plugins 會重新載入 hooks、MCP 伺服器、skills、agents 並印計數；重載若改變 MCP/LSP 工具會使提示快取失效並先警告；非互動 session 只在輸入時執行。

### Plugin manifest 參考（`plugins/manifest-reference`）
- 檔案：[plugins__manifest-reference.md](plugins__manifest-reference.md)｜https://code.claude.com/docs/zh-TW/plugins/manifest-reference｜lastmod 2026-11-04｜41.2 KB
- 一句話：plugin.json 完整欄位參考：型別、預設、路徑形式、userConfig 與環境變數、標準佈局。
- 何時讀：查 plugin.json 某欄位、元件路徑規則、userConfig 結構或各元件預設位置時。
- 關鍵內容：
  - 只有 `name` 必填；kebab-case；以 `claude-`/`anthropic-` 開頭或保留字會被 validate 判錯
  - `version`、`defaultEnabled`、`dependencies`、`settings`(僅 agent/subagentStatusLine)、`userConfig`、`channels`
  - 元件鍵：`skills`、`commands`、`agents`、`hooks`、`mcpServers`、`lspServers`、`outputStyles`、`workflows`
  - `experimental.themes/monitors/evals`；`types` 指向 mod 型別 .d.ts
  - 路徑須 `./` 開頭、不得逃出 plugin 根目錄、必須存在
  - 取代預設：commands/agents/outputStyles；新增：skills；合併：hooks/mcpServers/lspServers
  - 變數 `${CLAUDE_PLUGIN_ROOT}`、`${CLAUDE_PLUGIN_DATA}`、`${CLAUDE_PROJECT_DIR}`
  - marketplace `strict` 決定項目與 plugin.json 誰權威
- 新名詞：`strict` ＝ marketplace 項目是否可再給已有 plugin.json 的 plugin 附加元件；`directory listing fields` ＝ icon、documentationUrl 等僅供目錄用的欄位
- 記憶系統接點：manifest 的 hooks/mcpServers 與預設檔合併載入；settings 欄位僅 agent、subagentStatusLine 生效；userConfig 敏感值存安全儲存。

### Marketplace 參考（`plugins/marketplace-reference`）
- 檔案：[plugins__marketplace-reference.md](plugins__marketplace-reference.md)｜https://code.claude.com/docs/zh-TW/plugins/marketplace-reference｜lastmod 2026-10-25｜46.7 KB
- 一句話：marketplace.json 完整參考：頂層欄位、plugin 項目、plugin 來源類型與 marketplace 來源。
- 何時讀：查 marketplace.json 欄位、各種 source 類型、保留名稱或驗證訊息時。
- 關鍵內容：
  - 必填 `name`、`owner`、`plugins`；其他頂層：`metadata.pluginRoot`、`renames`、`forceRemoveDeletedPlugins`
  - plugin 來源：相對路徑、`github`、`url`、`git-subdir`、`npm`、`archive`、`command`
  - `ref`(分支/標籤) 與 `sha`(40 字元) 固定版本
  - marketplace 來源：`url`、`github`、`git`、`file`、`directory`、`settings`、`hostPattern`
  - 保留名稱：官方/社群名、`inline`、`builtin`、`claudeai-` 開頭等
  - `strict:false` 且 plugin.json 與項目都宣告元件會衝突
  - `command` 來源有 copy/link 模式，安裝前顯示命令並要求接受
  - 未知鍵只警告不拒絕
- 新名詞：`command source` ＝ 由 Claude Code 在使用者機器執行命令產生 plugin 目錄的來源；`git-subdir` ＝ 以 sparse checkout 取 git repo 子目錄的來源；`pluginRoot` ＝ 裸名 plugin 來源解析的基底目錄
- 記憶系統接點：marketplace 來源物件同時用於 extraKnownMarketplaces、strictKnownMarketplaces、blockedMarketplaces 設定鍵。

## Troubleshooting

### Plugin 載入參考（`plugins/loading`）
- 檔案：[plugins__loading.md](plugins__loading.md)｜https://code.claude.com/docs/zh-TW/plugins/loading｜lastmod 2026-10-25｜41.5 KB
- 一句話：追蹤 plugin 從哪載入、哪個設定檔決定、檔案放哪、版本與更新規則、名稱衝突。
- 何時讀：plugin 行為與預期不符、更新沒生效、要找磁碟路徑或釐清優先序時。
- 關鍵內容：
  - 三階段：設定宣告(enabledPlugins)→磁碟(`~/.claude/plugins/`)→已載入(啟動或 /reload-plugins)
  - ID 後綴：`@<marketplace>`、`@inline`、`@skills-dir`、`@synced`
  - enabledPlugins 六來源優先序：--add-dir<user<project<local<flag<managed
  - 磁碟：`cache/`、`data/`、`marketplaces/`、`installed_plugins.json`、`known_marketplaces.json`
  - 版本：manifest version>項目 version>commit SHA 前 12 碼；固定 version 使用者不更新
  - 自動更新在首則訊息後最多隨機延遲十分鐘；舊版目錄 14 天後清理
  - npm/bun 依賴安裝：需鎖定檔、無生命週期腳本、60 秒逾時、僅 registry 套件
  - 名稱衝突順序：managed>--plugin-dir>已安裝>skills-dir>synced
- 新名詞：`installed_plugins.json` ＝ 記錄已安裝 plugin 的 scope、路徑與版本的檔案；`known_marketplaces.json` ＝ 記錄已提取 marketplace 的檔案；`in-place plugin` ＝ 不複製進快取、直接從原位置載入的 plugin
- 記憶系統接點：plugin 於 session 啟動從 installed_plugins.json 與 cache 載入（不需網路）；設定／磁碟變更不影響執行中 session，需 /reload-plugins；hooks 路徑在更新後仍指舊版直到重載；同名 plugin 的 hooks 只有一個被註冊。

### 排除外掛程式故障（`plugins/troubleshooting`）
- 檔案：[plugins__troubleshooting.md](plugins__troubleshooting.md)｜https://code.claude.com/docs/zh-TW/plugins/troubleshooting｜lastmod 2026-10-25｜94.9 KB
- 一句話：依錯誤訊息查 plugin／marketplace 問題的原因與修法，按 /plugin、新增、安裝、載入、建立、託管、組織封鎖分段。
- 何時讀：看到具體錯誤訊息（找不到市集、安裝失敗、hooks 不觸發、被政策擋）要對照修復時。
- 關鍵內容：
  - `/plugin isn't available in this environment`：非互動或雲端無面板
  - `Marketplace "claude-plugins-official" not found`：需手動 add 官方市集
  - git 驗證/逾時：SSH/HTTPS 憑證、known_hosts、`Git clone timed out after 120s`
  - 安裝：`not found in marketplace`、`archive integrity check failed`、`untrusted source`
  - 已裝無作用：`Run /reload-plugins`、`not cached at <path>`、`installed_plugins.json` 損毀自動重建
  - hooks：`Failed to load hooks`、hook error、載入但不觸發的檢查
  - MCP/LSP：`Invalid MCP server config`、伺服器不啟動、monorepo 假診斷
  - 組織封鎖：`blocked by enterprise policy`、`disableSideloadFlags`、`seed-managed`
- 新名詞：`not cached` ＝ 已啟用 plugin 在磁碟快取找不到時的錯誤狀態
- 記憶系統接點：hooks/MCP/LSP 載入失敗訊息與檢查步驟；installed_plugins.json 讀不出時會自動重建並留 .set-aside 備份。

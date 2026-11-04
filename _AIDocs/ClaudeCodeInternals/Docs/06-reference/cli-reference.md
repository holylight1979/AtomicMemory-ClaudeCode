<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/cli-reference | lastmod: 2026-11-03 | section: Reference / Reference -->
> 來源：https://code.claude.com/docs/zh-TW/cli-reference（官方 zh-TW，lastmod 2026-11-03）｜分類：Reference › Reference｜EN 摘要：Complete reference for Claude Code command-line interface, including commands and flags.

# CLI 參考

> Claude Code 命令列介面的完整參考，包括命令和旗標。

## CLI 命令

您可以使用這些命令來啟動工作階段、管道內容、繼續對話和管理更新：

| 命令 | 說明 | 範例 |
| :- | :- | :- |
| `claude` | 啟動互動式工作階段 | `claude` |
| `claude "query"` | 使用初始提示詞啟動互動式工作階段 | `claude "explain this project"` |
| `claude -p "query"` | 透過 SDK 查詢，然後退出 | `claude -p "explain this function"` |
| `cat file \| claude -p "query"` | 處理管道內容 | `cat logs.txt \| claude -p "explain"` |
| `claude -c` | 在目前目錄中繼續最近的對話 | `claude -c` |
| `claude -c -p "query"` | 透過 SDK 繼續 | `claude -c -p "Check for type errors"` |
| `claude -r "<session>" "query"` | 按 ID 或名稱繼續工作階段 | `claude -r "auth-refactor" "Finish this PR"` |
| `claude update` | 更新至最新版本 | `claude update` |
| `claude gateway` | 啟動自託管 [Claude 應用程式閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway) 伺服器，供在 Amazon Bedrock、Google Cloud 的 Agent Platform 或 Microsoft Foundry 上部署 SSO 和原則在 Claude Code 前面的管理員使用。需要 `--config` 指向 [`gateway.yaml`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config)。 | `claude gateway --config gateway.yaml` |
| `claude install [version]` | 安裝或重新安裝原生二進位檔。接受版本號如 `2.1.118`、`stable` 或 `latest`。請參閱 [安裝特定版本](https://code.claude.com/docs/zh-TW/setup.md#install-a-specific-version) | `claude install stable` |
| `claude auth login` | 登入您的 Anthropic 帳戶。使用 `--email` 預先填入您的電子郵件地址，`--sso` 強制 SSO 身分驗證，`--console` 使用 Anthropic Console 登入以進行 API 使用計費而非 Claude 訂閱 | `claude auth login --console` |
| `claude auth logout` | 登出您的 Anthropic 帳戶 | `claude auth logout` |
| `claude auth status` | 以 JSON 格式顯示身分驗證狀態。使用 `--text` 以人類可讀的格式輸出。如果已登入則以代碼 0 退出，如果未登入則以代碼 1 退出。JSON 包含一個 `configDirectory` 欄位，命名 CLI 使用的 [設定目錄](https://code.claude.com/docs/zh-TW/claude-directory.md)。該欄位需要 Claude Code v2.1.268 或更新版本。JSON 的 `authMethod` 欄位為 `none`、`claude.ai`、`oauth_token`、`api_key`、`api_key_helper` 或 `third_party` 其中之一 | `claude auth status` |
| `claude agents` | 開啟 [agent 檢視](https://code.claude.com/docs/zh-TW/agent-view.md) 以監控和分派平行背景工作階段。使用 `--cwd <path>` 僅顯示在該目錄下啟動的工作階段，或使用 `--json` 將作用中工作階段列印為 JSON 陣列以供指令碼使用（`--json --all` 也包括已完成的背景工作階段）。傳遞 `--permission-mode`、`--model`、`--effort` 或 `--agent` 以設定 [分派工作階段的預設值](https://code.claude.com/docs/zh-TW/agent-view.md#permission-mode-model-and-effort)。接受 `--settings`、`--add-dir`、`--plugin-dir` 和 `--mcp-config`，如同頂層 `claude` 命令。開啟 agent 檢視需要互動式終端機 | `claude agents --json` |
| `claude attach <id\|name>` | 在此終端機中附加到 [背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md#manage-sessions-from-the-shell)。以執行中工作階段名稱的一部分取代 ID 傳遞，需要 Claude Code v2.1.290 或更新版本 | `claude attach 7c5dcf5d` |
| `claude auto-mode defaults` | 以 JSON 格式列印內建 [自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode) 分類器規則。使用 `claude auto-mode config` 查看應用了設定的有效設定。使用 `--label <prefix>` 僅列印標籤以該前綴開頭的規則，不區分大小寫。需要 Claude Code v2.1.208 或更新版本 | `claude auto-mode defaults --label 'Git Destructive'` |
| `claude auto-mode reset` | 透過從使用者設定檔案中移除 `autoMode` 部分來還原預設 [自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode) 設定。在寫入前提示確認；傳遞 `-y`/`--yes` 以跳過提示。來自 [受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md) 或 `--settings` 旗標的規則仍然適用。需要 Claude Code v2.1.212 或更新版本。請參閱 [檢查預設值和您的有效設定](https://code.claude.com/docs/zh-TW/auto-mode-config.md#inspect-the-defaults-and-your-effective-config) | `claude auto-mode reset --yes` |
| `claude daemon logs` | 追蹤背景工作階段 [監督程序](https://code.claude.com/docs/zh-TW/agent-view.md#the-supervisor-process) 的日誌檔案 `~/.claude/daemon.log`，在新行出現時將其列印出來，直到您按下 `Ctrl+C` | `claude daemon logs` |
| `claude daemon run` | 在此終端機的前景中執行背景工作階段 [監督程序](https://code.claude.com/docs/zh-TW/agent-view.md#the-supervisor-process)，並列印其日誌 | `claude daemon run` |
| `claude daemon status` | 列印背景工作階段 [監督程序](https://code.claude.com/docs/zh-TW/agent-view.md#the-supervisor-process) 的狀態、版本、通訊端目錄和工作程序計數以進行診斷。如果監督程序未執行則退出代碼 1 | `claude daemon status` |
| `claude daemon stop --any` | 停止背景工作階段 [監督程序](https://code.claude.com/docs/zh-TW/agent-view.md#the-supervisor-process) 及其託管的工作階段。傳遞 `--keep-workers` 以保持背景工作階段執行，以便下一個監督程序重新連接到它們。`--any` 確認停止隨需監督程序，這是預設值。使用此命令從 [無回應的監督程序](https://code.claude.com/docs/zh-TW/agent-view.md#agent-view-says-the-background-service-did-not-respond) 復原 | `claude daemon stop --any --keep-workers` |
| `claude doctor` | 從終端機列印唯讀安裝和設定診斷，無需啟動工作階段，包括安裝健康狀況、設定檔案驗證錯誤和 Remote Control 資格。如需可以套用修復的工作階段內設定檢查，請執行 [`/doctor`](https://code.claude.com/docs/zh-TW/commands#all-commands) | `claude doctor` |
| `claude import [source]` | 啟動互動式工作階段，執行 [`/import`](https://code.claude.com/docs/zh-TW/commands#all-commands) 以將其他編碼 agent 的設定帶入 Claude Code。接受與命令相同的 `--dry-run` 和 `--yes` 選項。在 Amazon Bedrock、Google Cloud 的 Agent Platform、Microsoft Foundry 或 AWS 上的 Claude Platform 上不可用。當您關閉 [功能旗標擷取](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching) 時也不可用。需要 Claude Code v2.1.213 或更新版本 | `claude import codex --dry-run` |
| `claude logs <id\|name>` | 列印來自 [背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md#manage-sessions-from-the-shell) 的最近輸出。以工作階段名稱的一部分取代 ID 傳遞，需要 Claude Code v2.1.290 或更新版本 | `claude logs 7c5dcf5d` |
| `claude mcp` | 設定 Model Context Protocol (MCP) 伺服器 | 請參閱 [Claude Code MCP 文件](https://code.claude.com/docs/zh-TW/mcp.md)。 |
| `claude mcp login <name>` | 執行已設定 MCP 伺服器的 OAuth 流程，無需開啟互動式 `/mcp` 面板。適用於 HTTP、SSE 和 claude.ai 連接器伺服器。在 SSH 上新增 `--no-browser` 以列印授權 URL 而非開啟瀏覽器。對於 HTTP 或 SSE 伺服器，請將重新導向 URL 貼回提示處。對於 claude.ai 連接器，請參閱 [從您的 shell 再次授權連接器](https://code.claude.com/docs/zh-TW/remote-control.md#authorize-a-connector-again-from-your-shell)。請參閱 [從命令列進行身分驗證](https://code.claude.com/docs/zh-TW/mcp.md#authenticate-from-the-command-line) | `claude mcp login sentry` |
| `claude mcp logout <name>` | 清除 MCP 伺服器的已儲存 OAuth 憑證 | `claude mcp logout sentry` |
| `claude plugin` | 管理 Claude Code [外掛](https://code.claude.com/docs/zh-TW/plugins/overview.md)。別名：`claude plugins`。請參閱 [外掛參考](https://code.claude.com/docs/zh-TW/plugins/cli-reference.md#claude-plugin-commands) 以取得子命令 | `claude plugin install code-review@claude-plugins-official` |
| `claude purge [path]` | 刪除專案的所有本機 Claude Code 狀態：逐字稿、工作清單、偵錯日誌、檔案編輯歷史記錄、提示詞歷史記錄行和專案在 `~/.claude.json` 中的項目。省略 `[path]` 以從互動式清單中選擇。旗標：`--dry-run` 以預覽，`-y`/`--yes` 以跳過確認，`-i`/`--interactive` 以確認每個項目，`--all` 用於每個專案。請參閱 [清除本機資料](https://code.claude.com/docs/zh-TW/claude-directory.md#clear-local-data) | `claude purge ~/work/repo --dry-run` |
| `claude remote-control` | 啟動 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 伺服器以從 Claude.ai 或 Claude 應用程式控制 Claude Code。以伺服器模式執行（無本機互動式工作階段）。請參閱 [伺服器模式旗標](https://code.claude.com/docs/zh-TW/remote-control.md#start-a-remote-control-session)。停止伺服器後，您可以恢復它正在服務的工作階段。請參閱 [停止伺服器後繼續工作階段](https://code.claude.com/docs/zh-TW/remote-control.md#resume-sessions-after-stopping-the-server) | `claude remote-control --name "My Project"` |
| `claude respawn <id>` | 重新啟動 [背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md#manage-sessions-from-the-shell)（執行中或已停止），保持其對話完整。使用 `--all` 重新啟動每個執行中的工作階段，例如以取得更新的 Claude Code 二進位檔 | `claude respawn 7c5dcf5d` |
| `claude rm <id>` | 從清單中移除 [背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md#manage-sessions-from-the-shell)。當移除因工作階段的 worktree [而被拒絕](https://code.claude.com/docs/zh-TW/agent-view.md#what-deleting-a-session-removes) 且第二個 `claude rm` 可以解決時，拒絕會列印要傳遞的確切旗標和值：`--discard-unpushed <commit>@<worktree-id>` 會捨棄具有未推送提交的 worktree 以及這些提交，`--force-remove-worktree <worktree-id>` 刪除 git 或 `WorktreeRemove` hook 無法移除的 worktree 目錄。`--discard-unpushed` 需要 Claude Code v2.1.260 或更新版本，而 `--force-remove-worktree` 需要 v2.1.268 或更新版本。對話逐字稿保留在您的本機機器上，可透過 `claude --resume` 取得 | `claude rm 7c5dcf5d` |
| `claude self-hosted-runner` | 啟動執行程序，將此機器或容器註冊到 [自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments) 並在您的基礎結構上託管 Claude Code 雲端工作階段。執行 `claude self-hosted-runner setup` 以進行引導式操作員逐步解說，`claude self-hosted-runner doctor` 以 [診斷已部署的執行程序](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#troubleshooting)，以及 `claude self-hosted-runner orchestrator` 以生成 [隨需執行程序](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#on-demand-runners)。需要 Claude Code v2.1.224 或更新版本 | `claude self-hosted-runner setup` |
| `claude setup-token` | 為 CI 和指令碼產生長期 OAuth token。將 token 列印到終端機而不儲存它。需要 Claude 訂閱。請參閱 [產生長期 token](https://code.claude.com/docs/zh-TW/authentication.md#generate-a-long-lived-token) | `claude setup-token` |
| `claude stop <id>` | 停止 [背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md#manage-sessions-from-the-shell)。也接受 `claude kill` | `claude stop 7c5dcf5d` |
| `claude ultrareview [target]` | 非互動式執行 [ultrareview](https://code.claude.com/docs/zh-TW/ultrareview.md#run-ultrareview-non-interactively)。將發現列印到 stdout，成功時退出代碼 0，失敗時退出代碼 1。使用 `--json` 以取得原始 payload，使用 `--timeout <minutes>` 以覆寫 45 分鐘的預設值。在 `github.com` pull request 目標上使用 `--post` 以將完成的發現作為來自您 GitHub 帳戶的一個純文字註解發佈到 PR。`--no-post` 是預設值。`--post` 和 `--no-post` 需要 Claude Code v2.1.227 或更新版本。請參閱 [將發現發佈到 pull request](https://code.claude.com/docs/zh-TW/ultrareview.md#post-findings-to-the-pull-request) | `claude ultrareview 1234 --json` |

如果您輸入錯誤的子命令，Claude Code 會建議最接近的符合項並退出而不啟動工作階段。例如，`claude udpate` 會列印 `Did you mean claude update?`。

`claude --dangerously-skip-permissions daemon <subcommand>` 會執行 `daemon` 子命令，因此當 `claude` 的別名包含該旗標時，子命令仍可正常運作。只有前導 `--dangerously-skip-permissions` 或 `--allow-dangerously-skip-permissions` 會以這種方式路由到 `daemon`；若 `daemon` 前面有任何其他旗標，子命令就不會執行。

## CLI 旗標

使用這些命令列旗標自訂 Claude Code 的行為。`claude --help` 不會列出每個旗標，所以旗標在 `--help` 中缺失並不表示它無法使用。

| 旗標 | 說明 | 範例 |
| :- | :- | :- |
| `--add-dir` | 新增額外的工作目錄供 Claude 讀取和編輯檔案。授予檔案存取權限；Claude Code [不會探索](https://code.claude.com/docs/zh-TW/permissions.md#additional-directories-grant-file-access-not-configuration)這些目錄中的大多數 `.claude/` 設定。驗證每個路徑都存在為目錄。您無法新增大多數[網路路徑](https://code.claude.com/docs/zh-TW/errors.md#working-directory-is-a-network-path)，例如 `\\server\share`。若要在工作階段之間保留這些目錄，請在設定中設定 [`permissions.additionalDirectories`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-additionaldirectories) | `claude --add-dir ../apps ../lib` |
| `--advisor <model>` | 使用模型別名 `fable`、`opus` 或 `sonnet`，或完整模型 ID，為此工作階段啟用伺服器端[顧問工具](https://code.claude.com/docs/zh-TW/advisor.md)。優先於工作階段的 `advisorModel` 設定。`fable` 需要 [Fable 存取權](https://code.claude.com/docs/zh-TW/advisor.md#choose-an-advisor-model) | `claude --advisor opus` |
| `--agent` | 為目前工作階段指定代理程式（覆蓋 `agent` 設定） | `claude --agent my-custom-agent` |
| `--agents` | 透過 JSON 動態定義自訂子代理程式。接受 [CLI 定義的子代理程式列出的欄位](https://code.claude.com/docs/zh-TW/sub-agents.md#choose-the-subagent-scope)。使用 `--print`，值可以改為是保存物件的 JSON 檔案的路徑；檔案形式需要 Claude Code v2.1.281 或更新版本。Claude Code 在啟動時驗證值並在無效值時結束；請參閱 [`Invalid --agents configuration`](https://code.claude.com/docs/zh-TW/errors#invalid-agents-configuration) 以取得訊息以及跳過驗證的旗標和環境變數。驗證需要 Claude Code v2.1.242 或更新版本 | `claude --agents '{"reviewer":{"description":"Reviews code","prompt":"You are a code reviewer"}}'` |
| `--allow-dangerously-skip-permissions` | 將 `bypassPermissions` 新增至 `Shift+Tab` 模式循環而不以它開始。讓您以不同的模式（例如 `plan`）開始，稍後切換至 `bypassPermissions`。請參閱[權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md#skip-all-checks-with-bypasspermissions-mode) | `claude --permission-mode plan --allow-dangerously-skip-permissions` |
| `--allowedTools`, `--allowed-tools` | 無需提示權限即可執行的工具，但從[網路路徑](https://code.claude.com/docs/zh-TW/permissions.md#network-paths)讀取除外。請參閱[權限規則語法](https://code.claude.com/docs/zh-TW/settings-reference.md#permission-rule-syntax)以進行模式比對。若要限制可用的工具，請改用 `--tools`。如果您在此指定[任務追蹤工具](https://code.claude.com/docs/zh-TW/tools-reference.md#task-tool-availability)之一，Claude Code 也會讓工作階段選擇加入 | `"Bash(git log *)" "Bash(git diff *)" "Read"` |
| `--append-subagent-system-prompt` | 將自訂文字附加到每個[子代理程式](https://code.claude.com/docs/zh-TW/sub-agents.md)的系統提示末尾，包括巢狀子代理程式，除了[分叉的子代理程式](https://code.claude.com/docs/zh-TW/sub-agents.md#fork-the-current-conversation)，它會重複使用對話自己的提示。僅在非互動模式下使用 `-p` 時適用。需要 Claude Code v2.1.205 或更新版本 | `claude -p --append-subagent-system-prompt "Cite file paths in every answer" "query"` |
| `--append-subagent-system-prompt-file` | 從檔案載入文字並將其附加到[子代理程式](https://code.claude.com/docs/zh-TW/sub-agents.md)系統提示。作為 `--append-subagent-system-prompt` 的替代方案，用於命令列上過長的文字。這兩個旗標無法結合。僅在非互動模式下使用 `-p` 時適用。需要 Claude Code v2.1.261 或更新版本 | `claude -p --append-subagent-system-prompt-file ./subagent-rules.txt "query"` |
| `--append-system-prompt` | 將自訂文字附加到預設系統提示的末尾 | `claude --append-system-prompt "Always use TypeScript"` |
| `--append-system-prompt-file` | 從檔案載入額外的系統提示文字並附加到預設提示 | `claude --append-system-prompt-file ./extra-rules.txt` |
| `--autocompact <auto\|tokens>` | 為此工作階段設定 [auto-compact 視窗](https://code.claude.com/docs/zh-TW/model-config.md#set-the-auto-compact-window)而不變更已儲存的設定。接受與 `/autocompact` 相同的值；該部分涵蓋值形式以及覆蓋旗標的內容。需要 Claude Code v2.1.221 或更新版本 | `claude --autocompact 500k` |
| `--ax-screen-reader` | 呈現螢幕閱讀器友善的輸出：沒有裝飾邊框或動畫的平面文字。強制使用經典轉譯器，因此 [`tui`](https://code.claude.com/docs/zh-TW/settings-reference#tui) 設定無效；附加的[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)仍會全螢幕呈現。優先於 [`CLAUDE_AX_SCREEN_READER`](https://code.claude.com/docs/zh-TW/env-vars) 和 [`axScreenReader`](https://code.claude.com/docs/zh-TW/settings-reference#axscreenreader) 設定。需要 Claude Code v2.1.181 或更新版本 | `claude --ax-screen-reader` |
| `--bare` | 最小模式：跳過 hooks、skills、自訂命令、子代理程式、已安裝的 plugins、MCP 伺服器、自動記憶和 CLAUDE.md 的自動探索，以便指令碼呼叫啟動更快。您使用 `--add-dir` 傳遞的目錄中的 Skills 仍會載入。Claude 可以存取 Bash、檔案讀取和檔案編輯工具。設定 [`CLAUDE_CODE_SIMPLE`](https://code.claude.com/docs/zh-TW/env-vars)。請參閱[裸模式](https://code.claude.com/docs/zh-TW/headless.md#start-faster-with-bare-mode) | `claude --bare -p "query"` |
| `--betas` | 要包含在 API 請求中的 Beta 標頭（僅限 API 金鑰使用者） | `claude --betas interleaved-thinking` |
| `--bg`, `--background` | 將工作階段啟動為[背景代理程式](https://code.claude.com/docs/zh-TW/agent-view.md)並立即返回。列印工作階段 ID 和管理命令。與 `--exec` 結合以執行 shell 命令作為背景工作而不是 Claude 工作階段，或與 `--agent` 結合以執行特定的子代理程式。檢查目錄的[工作區信任](https://code.claude.com/docs/zh-TW/permissions.md#project-allow-rules-and-workspace-trust)後再啟動。無法與 `-p`/`--print` 結合；請參閱[錯誤參考](https://code.claude.com/docs/zh-TW/errors.md#command-line-errors) | `claude --bg "investigate the flaky test"` |
| `--channels` | （研究預覽）Claude 應在此工作階段中監聽其[頻道](https://code.claude.com/docs/zh-TW/channels.md)通知的 MCP 伺服器。以空格分隔的 `plugin:<name>@<marketplace>` 項目清單。需要透過 claude.ai 或 Console API 金鑰進行 Anthropic 驗證 | `claude --channels plugin:my-notifier@my-marketplace` |
| `--chrome` | 為網路自動化和測試啟用 [Chrome 瀏覽器整合](https://code.claude.com/docs/zh-TW/chrome.md) | `claude --chrome` |
| `--cloud` | 使用任務說明，建立新的[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)。使用工作階段 ID（`session_...` 或 `cse_...`）或 claude.ai/code URL，改為使用 `-p` 將訊息排入該現有工作階段。請參閱[傳送後續訊息](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#send-follow-ups-from-the-cli)。 | `claude --cloud "Fix the login bug"` |
| `--continue`, `-c` | 載入目前目錄中最近的對話，包括[已完成的背景工作階段](https://code.claude.com/docs/zh-TW/sessions.md#where-the-session-picker-looks)；開啟已完成的背景工作階段需要 Claude Code v2.1.257 或更新版本。跳過使用 `claude -p` 或 Agent SDK 建立的工作階段，以及第一個提示詞為 `/loop` 的工作階段。`claude -p --continue` 包括 `-p`、SDK 和 `/loop` 工作階段。包括使用 `/add-dir` 新增此目錄的工作階段 | `claude --continue` |
| `--dangerously-load-development-channels` | 啟用不在核准允許清單上的[頻道](https://code.claude.com/docs/zh-TW/channels-reference.md#test-during-the-research-preview)，用於本機開發。接受 `plugin:<name>@<marketplace>` 和 `server:<name>` 項目。會提示確認，因此它在互動工作階段中生效。使用 `-p` 時，Claude Code 會忽略此旗標 | `claude --dangerously-load-development-channels server:webhook` |
| `--dangerously-skip-permissions` | 跳過權限提示。等同於 `--permission-mode bypassPermissions`。請參閱[權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md#skip-all-checks-with-bypasspermissions-mode)以了解此操作跳過和不跳過的內容。對於使用 `--bg` 啟動的工作階段，當主管重新啟動工作階段時，模式[會保留](https://code.claude.com/docs/zh-TW/agent-view.md#permission-mode-model-and-effort) | `claude --dangerously-skip-permissions` |
| `--debug` | 啟用偵錯模式，可選類別篩選，例如 `--debug='mcp,startup'` 或 `--debug='!mcp'`。篩選僅在 `=` 形式中繫結；以空格分隔的篩選會啟用偵錯模式而不進行篩選 | `claude --debug='mcp,startup'` |
| `--debug-file <path>` | 將偵錯日誌寫入特定檔案路徑。隱含啟用偵錯模式。優先於 `CLAUDE_CODE_DEBUG_LOGS_DIR` | `claude --debug-file /tmp/claude-debug.log` |
| `--desktop` | 在目前目錄上開啟 [Claude Desktop 應用程式](https://code.claude.com/docs/zh-TW/desktop.md)並結束而不在終端機中啟動工作階段。新增 `--continue` 或 `--resume` 搭配工作階段 ID，以[在 Desktop 中開啟該工作階段](https://code.claude.com/docs/zh-TW/desktop.md#coming-from-the-cli)。此處的 `--resume` 僅採用工作階段 ID，不採用名稱或文字記錄路徑。不採用提示和其他旗標，除了 `--verbose` 和 `--debug` 旗標，因為應用程式會自行啟動工作階段。在 macOS 和 x64 Windows 上可用，當您使用 Claude 訂閱登入時。需要 Claude Code v2.1.285 或更新版本 | `claude --desktop` |
| `--disable-slash-commands` | 為此工作階段停用所有 skills 和命令 | `claude --disable-slash-commands` |
| `--disallowedTools`, `--disallowed-tools` | 拒絕規則。裸工具名稱會從 Claude 的內容中移除相符的工具：`"Edit"` 移除 Edit、`"*"` 移除每個工具，`"mcp__*"` 移除每個 MCP 工具。範圍規則（例如 `Bash(rm *)`）會保留工具可用，並僅拒絕[如所寫](https://code.claude.com/docs/zh-TW/permissions.md#bash-rule-limits)相符的呼叫。命名 [`EndConversation`](https://code.claude.com/docs/zh-TW/tools-reference#endconversation-tool-behavior) 的規則在任何其他工具保持時無法移除它 | `"Bash(git log *)" "Bash(git diff *)" "Edit"` |
| `--effort` | 為目前工作階段設定 [effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)。選項：`low`、`medium`、`high`、`xhigh`、`max` 或 `ultracode`。可用的等級取決於模型。`ultracode` 會請求 `xhigh` effort 並開啟 [ultracode](https://code.claude.com/docs/zh-TW/workflows.md#let-claude-decide-with-ultracode)，需要 Claude Code v2.1.203 或更新版本。在主要對話的模型上，會覆寫此工作階段的 [`modelSettings`](https://code.claude.com/docs/zh-TW/settings-reference#modelsettings) 和 [`effortLevel`](https://code.claude.com/docs/zh-TW/settings-reference#effortlevel) 設定，且不會保留 | `claude --effort high` |
| `--enable-auto-mode` | 在 v2.1.111 中移除。自動模式現在預設在 `Shift+Tab` 循環中；使用 `--permission-mode auto` 以它開始 | `claude --permission-mode auto` |
| `--environment <environment-id>` | 建立在[自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)上執行的新雲端工作階段，具有給定的 ID。環境 ID 以 `ccpool_` 開頭。請參閱 [`--environment` 分派行為](https://code.claude.com/docs/zh-TW/self-hosted-environments-testing#environment-dispatch-behavior)以了解分派行為和它拒絕的旗標組合。需要 Claude Code v2.1.224 或更新版本 | `claude -p "Fix the login bug" --environment ccpool_abc123` |
| `--exclude-dynamic-system-prompt-sections` | 將每使用者內容（例如自動記憶位置）從系統提示移出並放入第一個使用者訊息。改善在不同使用者和執行相同任務的機器上的提示快取重複使用。僅適用於預設系統提示；當設定 `--system-prompt` 或 `--system-prompt-file` 時忽略。與 `-p` 搭配使用以進行指令碼化、多使用者工作負載 | `claude -p --exclude-dynamic-system-prompt-sections "query"` |
| `--exec` | 執行 shell 命令作為 PTY 支援的背景工作而不是啟動 Claude 工作階段。與 `--bg` 搭配使用以從 shell 啟動 | `claude --bg --exec 'pytest -x'` |
| `--fallback-model` | 當主要模型過載或無法使用時（例如已淘汰的模型），啟用自動回退到指定的模型。接受按順序嘗試的逗號分隔清單。請參閱[回退模型鏈](https://code.claude.com/docs/zh-TW/model-config.md#fallback-model-chains)。若要在工作階段之間保留鏈，請使用 [`fallbackModel` 設定](https://code.claude.com/docs/zh-TW/settings-reference#fallbackmodel)，此旗標會覆蓋它 | `claude --fallback-model sonnet,haiku` |
| `--fork-session` | 恢復時，建立新的工作階段 ID 而不是重複使用原始 ID（與 `--resume` 或 `--continue` 搭配使用） | `claude --resume abc123 --fork-session` |
| `--forward-subagent-text` | 在輸出串流中將 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 的文字和思考區塊作為 `assistant` 和 `user` 訊息發出，並設定 `parent_tool_use_id`，以便您可以重建每個 subagent 的逐字稿。沒有此旗標時，Claude Code 會省略在[前景](https://code.claude.com/docs/zh-TW/sub-agents.md#run-subagents-in-foreground-or-background)中執行的 subagent 的文字和思考區塊。需要 `--print` 和 `--output-format stream-json`。關於巢狀 subagent、分叉的 skill 以及各自所需的版本，請參閱[追蹤 subagent 訊息](https://code.claude.com/docs/zh-TW/headless.md#follow-subagent-messages)。[`CLAUDE_CODE_FORWARD_SUBAGENT_TEXT`](https://code.claude.com/docs/zh-TW/env-vars) 環境變數會啟用相同的行為。需要 Claude Code v2.1.211 或更新版本 | `claude -p --output-format stream-json --verbose --forward-subagent-text "query"` |
| `--from-pr` | 開啟工作階段選擇器，篩選至連結到特定提取要求的工作階段。接受 PR 編號、GitHub 或 GitHub Enterprise PR URL、GitLab 合併要求 URL 或 Bitbucket 提取要求 URL。當 Claude 建立提取要求時，工作階段會自動連結 | `claude --from-pr 123` |
| `--ide` | 如果恰好有一個有效的 IDE 可用，在啟動時自動連線到 IDE | `claude --ide` |
| `--init` | 在工作階段之前使用 `init` 匹配器執行[設定 hooks](https://code.claude.com/docs/zh-TW/hooks.md#setup)（僅列印模式） | `claude -p --init "query"` |
| `--init-only` | 執行[設定](https://code.claude.com/docs/zh-TW/hooks.md#setup)和 `SessionStart` hooks，然後結束而不啟動對話 | `claude --init-only` |
| `--include-hook-events` | 在輸出串流中包含 hook 生命週期事件。`SessionStart` 和 `Setup` hook 事件始終包含，不需要此旗標。某些 hook 事件（例如 `Notification`、`SessionEnd`、`PreCompact` 和 `PostCompact`）永遠不會產生 `hook_started` 事件，即使使用此旗標也是如此。對於這些事件，Claude Code 仍會在執行超過一秒的命令 hook 產生輸出時發出 `hook_progress`，並僅在[在背景執行的 hook](https://code.claude.com/docs/zh-TW/hooks.md#run-hooks-in-the-background)完成時發出 `hook_response`。需要 `--output-format stream-json` | `claude -p --output-format stream-json --verbose --include-hook-events "query"` |
| `--include-partial-messages` | 在輸出中包含部分串流事件。需要 `--print` 和 `--output-format stream-json` | `claude -p --output-format stream-json --verbose --include-partial-messages "query"` |
| `--input-format` | 指定列印模式的輸入格式（選項：`text`、`stream-json`） | `claude -p --input-format stream-json --output-format stream-json --verbose` |
| `--json-schema` | 在代理程式完成其工作流程後取得符合 JSON Schema 的驗證 JSON 輸出（僅列印模式）。請參閱[結構化輸出](https://code.claude.com/docs/zh-TW/agent-sdk/structured-outputs.md)。Claude Code 在無效的 schema 上結束並接受 `format` 關鍵字作為註釋而不進行用戶端驗證 | `claude -p --json-schema '{"type":"object","properties":{...}}' "query"` |
| `--maintenance` | 在工作階段之前使用 `maintenance` 匹配器執行[設定 hooks](https://code.claude.com/docs/zh-TW/hooks.md#setup)（僅列印模式） | `claude -p --maintenance "query"` |
| `--max-budget-usd` | 一旦 API 呼叫的估計支出達到此金額即停止執行（僅列印模式）。Claude Code 會依據其[用戶端成本估算](https://code.claude.com/docs/zh-TW/agent-sdk/cost-tracking.md#estimates-not-billing)檢查上限，這可能與您的帳單不同。來自 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 的支出計入上限。支出可能會超過上限，因此請[保留餘裕](https://code.claude.com/docs/zh-TW/agent-sdk/agent-loop.md#budget-headroom)。當您使用 `--continue` 或 `--resume` 返回對話時，[從較早的執行還原](https://code.claude.com/docs/zh-TW/agent-sdk/cost-tracking.md#accumulate-costs-across-multiple-calls)的總計不計入上限。一旦支出達到上限，產生另一個 subagent 會失敗並出現 `Budget limit reached`，且 Claude Code 會停止仍在執行的背景 subagent；上限強制行為需要 Claude Code v2.1.217 或更新版本 | `claude -p --max-budget-usd 5.00 "query"` |
| `--max-turns` | 限制 agent 回合數（僅列印模式）。預設無限制。使用 `--input-format stream-json` 時，當限制結束回合時仍在佇列中的訊息會保持在佇列中，並以其自己的限制啟動新回合 | `claude -p --max-turns 3 "query"` |
| `--mcp-config` | 從 JSON 檔案或字串載入 MCP 伺服器（以空格分隔）。當您使用 `-p` 傳遞此旗標時，Claude Code 會在執行第一個回合之前等待仍在擱置的伺服器連線，直到 [`MCP_TIMEOUT`](https://code.claude.com/docs/zh-TW/env-vars) 啟動逾時（預設 30 秒）；具有[快取工具清單](https://code.claude.com/docs/zh-TW/mcp.md#managing-your-servers)的伺服器會跳過等待並在首次使用時連線。在[自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#connection-timing)中，則改為套用較短的等待時間。等待需要 Claude Code v2.1.221 或更新版本 | `claude --mcp-config ./mcp.json` |
| `--model` | 使用[模型別名](https://code.claude.com/docs/zh-TW/model-config.md#model-aliases)（例如 `sonnet`、`opus`、`haiku` 或 `fable`）或模型的完整名稱為目前工作階段設定模型。覆蓋 [`model`](https://code.claude.com/docs/zh-TW/settings-reference#model) 設定和 [`ANTHROPIC_MODEL`](https://code.claude.com/docs/zh-TW/model-config#environment-variables) | `claude --model claude-sonnet-5` |
| `--name`, `-n` | 為工作階段設定顯示名稱，顯示在 `/resume` 和終端機標題中。您可以使用 `claude --resume <name>` 恢復命名的工作階段。 [`/rename`](https://code.claude.com/docs/zh-TW/commands) 會在工作階段中途變更名稱，也會在提示列上顯示它 | `claude -n "my-feature-work"` |
| `--no-chrome` | 為此工作階段停用 [Chrome 瀏覽器整合](https://code.claude.com/docs/zh-TW/chrome.md) | `claude --no-chrome` |
| `--no-session-persistence` | 停用工作階段持續性，使工作階段不會儲存到磁碟且無法恢復。僅列印模式。[`CLAUDE_CODE_SKIP_PROMPT_HISTORY`](https://code.claude.com/docs/zh-TW/env-vars) 環境變數在任何模式中執行相同操作 | `claude -p --no-session-persistence "query"` |
| `--output-format` | 指定列印模式的輸出格式（選項：`text`、`json`、`stream-json`） | `claude -p "query" --output-format json` |
| `--permission-mode` | 以指定的[權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md)開始。接受 `default`、`acceptEdits`、`plan`、`auto`、`dontAsk`、`bypassPermissions` 或 `manual` 作為 `default` 的別名。`manual` 別名選擇 UI 標籤為 Manual 的權限模式，需要 Claude Code v2.1.200 或更新版本；`claude --help` 會列出它代替 `default`，兩個值都有效。覆蓋設定檔案中的 `defaultMode`。沒有此旗標或 `--dangerously-skip-permissions`，新工作階段會以[工作階段開始的權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md#which-mode-a-session-starts-in)中描述的權限模式開始，這也涵蓋 `-p` 執行開始的內容 | `claude --permission-mode plan` |
| `--permission-prompt-tool` | 指定 MCP 工具以在非互動模式中處理權限提示。傳遞該次執行所載入之 MCP 伺服器上某個工具的完整名稱，例如 `mcp__<server>__<tool>`。Claude Code 會在執行第一個回合之前等待該工具的 MCP 伺服器連線，直到 [`MCP_TIMEOUT`](https://code.claude.com/docs/zh-TW/env-vars) 啟動逾時（預設 30 秒）。 提示工具無法核准標記為[需要使用者互動](https://code.claude.com/docs/zh-TW/mcp.md#require-approval-for-a-specific-tool)的 MCP 工具：Claude Code 會將其 `allow` 結果轉換為拒絕。此限制需要 Claude Code v2.1.199 或更新版本 | `claude -p --mcp-config ./mcp.json --permission-prompt-tool mcp__permissions__approve "query"` |
| `--permission-prompts` | 在列印模式中設定誰回答權限提示。使用預設 `host`，Claude Code 會將它們傳送到 Agent SDK 主機或 `--permission-prompt-tool` 工具。當沒有人可以回答時傳遞 `none`，Claude Code 會改為拒絕它們。請參閱[在無人值守執行中關閉權限提示](https://code.claude.com/docs/zh-TW/headless.md#turn-off-permission-prompts-in-unattended-runs)。需要 Claude Code v2.1.259 或更新版本 | `claude -p --permission-prompts none "query"` |
| `--plugin-dir` | 從目錄或 `.zip` 封存載入 plugin，或從[plugins 資料夾](https://code.claude.com/docs/zh-TW/plugins/create.md#load-a-directory-or-archive-for-one-session)載入多個，僅供此工作階段使用。每個旗標採用一個路徑。重複旗標以取得更多路徑：`--plugin-dir A --plugin-dir B.zip`。傳遞 plugins 資料夾需要 Claude Code v2.1.265 或更新版本 | `claude --plugin-dir ./my-plugin` |
| `--plugin-url` | 從 URL 為此工作階段僅擷取 plugin `.zip` 封存。重複旗標以取得多個 plugins，或在單一引用值中傳遞以空格分隔的 URL | `claude --plugin-url https://example.com/plugin.zip` |
| `--print`, `-p` | 列印回應而不進行互動模式（請參閱 [Agent SDK 文件](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md)以取得程式設計使用詳細資訊）。關於在仍在執行的背景工作階段上使用 `--resume`，請參閱[恢復執行中的背景工作階段](https://code.claude.com/docs/zh-TW/sessions.md#resume-a-running-background-session) | `claude -p "query"` |
| `--prompt-suggestions` | 在產生提示建議的每個轉後發出 `prompt_suggestion` 訊息，其中包含預測的下一個使用者提示；非常短的對話可能不會產生任何提示。需要 `--print`、`--output-format stream-json` 和 `--verbose`。請參閱[提示建議](https://code.claude.com/docs/zh-TW/interactive-mode.md#prompt-suggestions) | `claude -p --prompt-suggestions --output-format stream-json --verbose "query"` |
| `--ref <branch>` | 使用 `--environment`，根據命名的 ref 而不是本機 `HEAD` 為新工作階段的簽出建立基礎 | `claude -p "Run the smoke test" --environment ccpool_abc123 --ref main` |
| `--remote` | `--cloud` 的已淘汰別名，包括現有工作階段形式 | `claude --remote "Fix the login bug"` |
| `--remote-control`, `--rc` | 啟動互動工作階段，並啟用[遠端控制](https://code.claude.com/docs/zh-TW/remote-control.md#start-a-remote-control-session)，以便您也可以從 claude.ai 或 Claude 應用程式控制它。可選擇傳遞工作階段的名稱 | `claude --remote-control "My Project"` |
| `--remote-control-session-name-prefix <prefix>` | 當未設定明確名稱時，[遠端控制](https://code.claude.com/docs/zh-TW/remote-control.md)自動產生工作階段名稱的前置詞。預設為您機器的主機名稱，產生名稱如 `myhost-graceful-unicorn`。設定 `CLAUDE_REMOTE_CONTROL_SESSION_NAME_PREFIX` 以取得相同效果 | `claude remote-control --remote-control-session-name-prefix dev-box` |
| `--replay-user-messages` | 從 stdin 重新發出使用者訊息回到 stdout 以進行確認。需要 `--input-format stream-json` 和 `--output-format stream-json` | `claude -p --input-format stream-json --output-format stream-json --verbose --replay-user-messages` |
| `--restricted` | 以受限模式啟動。當評估工具在共用機器上驅動 `claude` 且 Claude Code 不得執行命令或讀取該機器的使用者和專案設定時使用。Claude Code 會移除執行命令或程式碼的內建工具以及 WebFetch，除非您在 `--tools` 中個別命名它們，而不是透過 `default` 預設集。它也會將內建檔案工具限制在[工作目錄](https://code.claude.com/docs/zh-TW/permissions.md#working-directories)、僅載入[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)和 `--settings`、拒絕 [`bypassPermissions`](https://code.claude.com/docs/zh-TW/permission-modes#skip-all-checks-with-bypasspermissions-mode)，以及[拒絕從受限工作階段建立雲端工作階段](https://code.claude.com/docs/zh-TW/errors.md#cloud-sessions-cannot-be-created-from-a-restricted-session)。需要 Claude Code v2.1.248 或更新版本 | `claude --restricted -p "query"` |
| `--resume`, `-r` | 按 ID 或名稱恢復特定工作階段，或顯示互動選擇器以選擇工作階段。代替 ID，您可以傳遞工作階段 `.jsonl` [文字記錄檔](https://code.claude.com/docs/zh-TW/sessions.md#where-transcripts-are-stored)的絕對路徑。選擇器和名稱搜尋包括使用 `/add-dir` 新增此目錄的工作階段。當您傳遞工作階段 ID 時，Claude Code 會搜尋目前專案目錄及其 git worktrees，然後搜尋此機器上的所有其他專案。在 v2.1.223 之前，ID 搜尋僅涵蓋目前專案目錄及其 git worktrees。[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)在選擇器中顯示，標記為 `bg`。恢復仍在執行的工作階段[在此終端機中開啟該工作階段](https://code.claude.com/docs/zh-TW/sessions.md#resume-a-running-background-session)透過 `claude attach`，您在命令列上傳遞的提示會作為其下一個轉傳送給它。在 v2.1.285 之前，Claude Code 拒絕並列印 `claude attach` 命令以改為執行 | `claude --resume auth-refactor` |
| `--safe-mode` | 以所有自訂停用開始以疑難排解損壞的設定：CLAUDE.md、skills、plugins、hooks、MCP 伺服器、自訂命令和代理程式、輸出樣式、工作流程、自訂主題、自訂快捷鍵、狀態列和檔案建議命令、LSP 伺服器和自動記憶不會載入。驗證、模型選擇、內建工具和權限正常運作，這與 [`--bare`](https://code.claude.com/docs/zh-TW/headless#start-faster-with-bare-mode) 不同。受管設定原則仍適用，包括原則設定的 hooks、狀態列和檔案建議命令；受管 plugins、受管 skills、受管 CLAUDE.md 和原則設定的 MCP 伺服器不適用。用於檢查自訂是否觸發[自動模型回退](https://code.claude.com/docs/zh-TW/model-config.md#automatic-model-fallback)。設定 [`CLAUDE_CODE_SAFE_MODE`](https://code.claude.com/docs/zh-TW/env-vars) | `claude --safe-mode` |
| `--session-id` | 為對話使用特定工作階段 ID（必須是有效的 UUID） | `claude --session-id "550e8400-e29b-41d4-a716-446655440000"` |
| `--setting-sources` | 要載入的設定來源的逗號分隔清單（`user`、`project`、`local`）。請參閱[代理程式檢視](https://code.claude.com/docs/zh-TW/agent-view.md#what-carries-over-when-you-background)和[代理程式團隊](https://code.claude.com/docs/zh-TW/agent-teams.md#context-and-communication)以了解您從此工作階段啟動的工作階段繼承清單 | `claude --setting-sources user,project` |
| `--settings` | 設定 JSON 檔案或內嵌 JSON 字串的路徑。您在此設定的值會覆蓋此工作階段的 `settings.json` 檔案中的相同金鑰。您省略的金鑰會保留其檔案型值。檔案必須是不超過 2 MiB 的一般檔案。請參閱[設定優先順序](https://code.claude.com/docs/zh-TW/settings.md#settings-precedence) | `claude --settings ./settings.json` |
| `--strict-mcp-config` | 僅使用 `--mcp-config` 中的 MCP 伺服器，忽略所有其他 MCP 設定。請參閱[使用 managed-mcp.json 進行獨佔控制](https://code.claude.com/docs/zh-TW/managed-mcp.md#exclusive-control-with-managed-mcp-json)以了解旗標在受管 MCP 檔案下執行的操作 | `claude --strict-mcp-config --mcp-config ./mcp.json` |
| `--system-prompt` | 使用自訂文字取代整個系統提示 | `claude --system-prompt "You are a Python expert"` |
| `--system-prompt-file` | 從檔案載入系統提示，取代預設提示 | `claude --system-prompt-file ./custom-prompt.txt` |
| `--system-prompt-snapshot` | 傳遞 `off` 以在每個要求上重建系統提示，而不是重複使用[在對話的第一個要求上記錄](#system-prompt-flags-in-resumed-conversations)的提示，例如在您跨 `--continue` 執行反覆運算 `--append-system-prompt` 文字時。需要 Claude Code v2.1.257 或更新版本 | `claude --system-prompt-snapshot off` |
| `--teleport` | 在本機終端機中恢復[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md) | `claude --teleport` |
| `--teammate-mode` | 設定[代理程式團隊](https://code.claude.com/docs/zh-TW/agent-teams.md)隊友的顯示方式：`in-process`（預設）、`auto`、`tmux` 或 `iterm2`。覆蓋此工作階段的 [`teammateMode`](https://code.claude.com/docs/zh-TW/settings-reference#teammatemode) 設定。請參閱[選擇顯示模式](https://code.claude.com/docs/zh-TW/agent-teams.md#choose-a-display-mode) | `claude --teammate-mode auto` |
| `--tmux` | 為 worktree 建立 tmux 工作階段。需要 `--worktree`。在可用時使用 iTerm2 原生窗格；傳遞 `--tmux=classic` 以取得傳統 tmux | `claude -w feature-auth --tmux` |
| `--tools` | 限制 Claude 可以使用的內建工具。使用 `""` 停用全部、`"default"` 取得預設集，或工具名稱如 `"Bash,Edit,Read"`。在 macOS、Linux 和 WSL 上，預設集會排除 `Glob` 和 `Grep`，如[Glob 工具行為](https://code.claude.com/docs/zh-TW/tools-reference.md#glob-tool-behavior)下所述。如果您在此指定[任務追蹤工具](https://code.claude.com/docs/zh-TW/tools-reference.md#task-tool-availability)之一，Claude Code 也會讓工作階段選擇加入。旗標不會影響 MCP 工具；若要一併拒絕這些工具，請使用 `--disallowedTools "mcp__*"`。省略 [`EndConversation`](https://code.claude.com/docs/zh-TW/tools-reference#endconversation-tool-behavior) 的清單不會移除它；`""` 僅在沒有剩餘的 MCP 工具時移除它 | `claude --tools "Bash,Edit,Read"` |
| `--verbose` | 啟用詳細記錄，顯示完整的逐轉輸出。覆蓋此工作階段的 [`viewMode`](https://code.claude.com/docs/zh-TW/settings-reference#viewmode) 設定 | `claude --verbose` |
| `--version`, `-v` | 輸出版本號 | `claude -v` |
| `--worktree`, `-w` | 在隔離的 [git worktree](https://code.claude.com/docs/zh-TW/worktrees.md) 中啟動 Claude，位於 `<repo>/.claude/worktrees/<name>`。如果您未提供名稱，Claude Code 會產生一個。傳遞 `#<number>`、GitHub 提取要求 URL 或 GitLab 合併要求 URL 以[從 `origin` 擷取該 PR 或 MR 並從它分支 worktree](https://code.claude.com/docs/zh-TW/worktrees#branch-from-a-pull-request)。從 GitLab 合併要求分支需要 Claude Code v2.1.233 或更新版本 | `claude -w feature-auth` |

### 系統提示旗標

Claude Code 提供五個旗標用於自訂系統提示。四個設定其文字，使用 `--system-prompt-snapshot` 您可以控制對話是否保留它開始時的文字。所有五個都在互動和非互動模式中運作。

| 旗標 | 行為 | 範例 |
| :- | :- | :- |
| `--system-prompt` | 取代整個預設提示 | `claude --system-prompt "You are a Python expert"` |
| `--system-prompt-file` | 使用檔案內容取代 | `claude --system-prompt-file ./prompts/review.txt` |
| `--append-system-prompt` | 附加到預設提示 | `claude --append-system-prompt "Always use TypeScript"` |
| `--append-system-prompt-file` | 將檔案內容附加到預設提示 | `claude --append-system-prompt-file ./style-rules.txt` |
| `--system-prompt-snapshot` | 使用 `off`，在每個要求上重建提示。使用 `on`（預設），重複使用[記錄適用](#system-prompt-flags-in-resumed-conversations)的記錄提示 | `claude --append-system-prompt "Draft rules" --system-prompt-snapshot off` |

您可以組合這些旗標。若要取代預設提示詞並仍附加您自己的文字，請將 `--append-system-prompt` 或 `--append-system-prompt-file` 與 `--system-prompt` 或 `--system-prompt-file` 一起傳遞。使用 Claude Code v2.1.283 或更新版本時，您也可以將旗標與其自身的檔案形式一起傳遞，例如 `--append-system-prompt` 搭配 `--append-system-prompt-file`，Claude Code 會同時使用兩者。

例如，在 shell 中執行下列命令，以同時附加來自檔案的風格指南和一條額外指示：

```bash theme={null}
claude -p --append-system-prompt-file ./style.md --append-system-prompt "Always reply in French" "Summarize README.md"
```

Claude 會收到預設系統提示詞，後接 `style.md` 的內容、一個空白行，然後是 `Always reply in French`。即使您在 `--append-system-prompt-file` 之前傳遞 `--append-system-prompt`，檔案的內容仍會排在前面。

當取代文字結合每次執行相同的指示與每次執行變更的內容時，在指示和內容之間新增僅包含 `__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__` 的行。Claude Code 在第一個這樣的行分割提示並移除該行，因此上面的部分保持快取而下面的部分變更。需要 Claude Code v2.1.275 或更新版本。[快取自訂提示的靜態部分](https://code.claude.com/docs/zh-TW/agent-sdk/modifying-system-prompts.md#cache-the-static-part-of-a-custom-prompt)列出分割適用的設定。

根據 Claude Code 的預設身份是否仍適合您的任務進行選擇。當 Claude 應保持編碼助手並也遵循您的額外規則時使用附加旗標：每次呼叫指示、輸出格式或 `-p` 指令碼的網域內容。附加保留預設工具指導、安全指示和編碼慣例，因此您只需提供不同的部分。當表面、身份或權限模型與 Claude Code 的不同時使用取代旗標，例如管道中沒有人類監視的非編碼代理程式。取代會移除整個預設提示，包括工具指導和安全指示，因此您負責您的任務仍需要的任何內容。

對於您可以在專案之間切換和共用的持續人物，請使用[輸出樣式](https://code.claude.com/docs/zh-TW/output-styles.md)。對於專案慣例 Claude 應始終遵循，請使用 [CLAUDE.md](https://code.claude.com/docs/zh-TW/memory.md)。[Agent SDK 系統提示指南](https://code.claude.com/docs/zh-TW/agent-sdk/modifying-system-prompts.md#decide-on-a-starting-point)涵蓋更深入的相同決定。

#### 恢復對話中的系統提示旗標

預設情況下，Claude Code 在對話的第一個要求上建立系統提示一次，應用任何系統提示旗標中的文字，並在工作階段中記錄它。在對話被壓縮之前，每個稍後的要求都使用該記錄的提示，包括在您使用 `--resume` 或 `--continue` 返回對話後。如果您在該稍後的啟動上傳遞不同的系統提示旗標文字或無，它會在對話被壓縮或您啟動新對話時生效。

在[雲端工作階段](https://code.claude.com/docs/zh-TW/cloud-environments.md)之外，如果您透過傳遞 `--bare` 或設定 `CLAUDE_CODE_SIMPLE=1` 在[裸模式](https://code.claude.com/docs/zh-TW/headless.md#start-faster-with-bare-mode)中啟動 Claude Code，記錄會保持關閉，除非您傳遞 `--system-prompt-snapshot on`。在 v2.1.268 之前，不[擷取功能旗標](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)的工作階段，包括 Amazon Bedrock、Google Cloud 的 Agent Platform 和 Microsoft Foundry 上的工作階段，在每個要求上重建提示，`--system-prompt-snapshot` 無效。

若要改為在每個要求上重建提示，例如在您跨 `--continue` 執行反覆運算其措辭時，傳遞 `--system-prompt-snapshot off`。在 v2.1.265 之前，傳遞任何系統提示旗標也會關閉記錄，除非您傳遞 `--system-prompt-snapshot on`。

## 另請參閱

* [Chrome 擴充功能](https://code.claude.com/docs/zh-TW/chrome.md) - 瀏覽器自動化和網頁測試
* [互動模式](https://code.claude.com/docs/zh-TW/interactive-mode.md) - 快捷鍵、輸入模式和互動功能
* [快速入門指南](https://code.claude.com/docs/zh-TW/quickstart.md) - Claude Code 入門
* [常見工作流程](https://code.claude.com/docs/zh-TW/common-workflows.md) - 進階工作流程和模式
* [設定](https://code.claude.com/docs/zh-TW/settings.md) - 設定選項
* [Agent SDK 文件](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) - 程式化使用和整合

<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/claude-directory | lastmod: 2026-10-29 | section: Getting started / Core concepts -->
> 來源：https://code.claude.com/docs/zh-TW/claude-directory（官方 zh-TW，lastmod 2026-10-29）｜分類：Getting started › Core concepts｜EN 摘要：Where Claude Code reads CLAUDE.md, settings.json, hooks, skills, commands, subagents, workflows, rules, and auto memory. Explore the .claude directory in your project and ~/.claude in your home directory.

# 探索 .claude 目錄

> Claude Code 讀取 CLAUDE.md、settings.json、hooks、skills、commands、subagents、workflows、rules 和自動記憶的位置。探索您專案中的 .claude 目錄和主目錄中的 ~/.claude。

Claude Code 從您的專案目錄和主目錄中的 `~/.claude` 讀取指令、設定、skills、subagents 和記憶。將專案檔案提交到 git 以與您的團隊共享；`~/.claude` 中的檔案是個人設定，適用於您的所有專案。

在 Windows 上，`~/.claude` 解析為 `%USERPROFILE%\.claude`。如果您設定了 [`CLAUDE_CONFIG_DIR`](https://code.claude.com/docs/zh-TW/env-vars)，此頁面上的每個 `~/.claude` 路徑都會改為位於該目錄下。`.claude.json` 也是如此，若未設定，它位於 `~/.claude.json`。

大多數使用者只編輯 `CLAUDE.md` 和 `settings.json`。如果您的儲存庫已經有一個供其他程式設計 agent 使用的 `AGENTS.md`，Claude Code [可以讀取該檔案](https://code.claude.com/docs/zh-TW/memory.md#agents-md)來取代 `CLAUDE.md`。目錄的其餘部分是可選的：根據需要新增 skills、rules 或 subagents。

## 探索目錄

點擊樹中的檔案以查看每個檔案的功能、何時載入以及範例。

## 未顯示的內容

探索器涵蓋您編寫和編輯的檔案。一些相關檔案位於其他位置：

| 檔案 | 位置 | 用途 |
| - | - | - |
| `managed-settings.json` | 系統層級，因作業系統而異 | 企業強制執行的設定，您自己的設定檔和 `--settings` 值都無法覆寫，除了[狹隘的例外](https://code.claude.com/docs/zh-TW/settings.md#exceptions-to-managed-settings-precedence)。請參閱[檔案儲存位置](https://code.claude.com/docs/zh-TW/managed-settings.md#deploy-a-managed-settings-file)和 [Claude Code 使用的受管來源](https://code.claude.com/docs/zh-TW/managed-settings.md#precedence-within-the-managed-tier)。 |
| `CLAUDE.local.md` | 專案根目錄 | 您對此專案的私人偏好設定，與 CLAUDE.md 一起載入。手動建立它並將其新增至 `.gitignore`。 |
| `AGENTS.md` | 專案根目錄、`.claude/` 或任何目錄 | 您為 AI 編碼 agent 撰寫的專案指示。Claude Code 可以[載入它](https://code.claude.com/docs/zh-TW/memory.md#agents-md)來取代 `CLAUDE.md`。 |
| 已安裝的外掛 | `~/.claude/plugins` | 複製的市集、已安裝的外掛版本、`installed_plugins.json` 安裝記錄，以及各外掛資料，由 `claude plugin` 命令管理。從您的 claude.ai 帳戶[同步的外掛](https://code.claude.com/docs/zh-TW/plugins/loading.md#synced-plugins)會下載到 `~/.claude/plugins/synced/`。對於從市集[`command` 來源](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference#command-plugin-source)以連結模式安裝的外掛，Claude Code 會在此儲存連結而不是副本，外掛的檔案保留在命令列印的目錄中。`command` 來源需要 Claude Code v2.1.229 或更新版本。在您從本機路徑新增的市集中以相對路徑列出的外掛，也會從其來源目錄[就地載入](https://code.claude.com/docs/zh-TW/plugins/loading.md#find-plugins-on-disk)，而不是從快取副本載入。請參閱[外掛快取](https://code.claude.com/docs/zh-TW/plugins/loading.md#find-plugins-on-disk)以了解孤立版本如何被清理。 |

`~/.claude` 也保存 Claude Code 在您工作時寫入的資料：文字記錄、提示歷史記錄、檔案快照、快取和日誌。請參閱下方的[應用程式資料](#application-data)。

## 選擇正確的檔案

不同類型的自訂設定位於不同的檔案中。使用此表格找到變更應該位於何處。

| 您想要 | 編輯 | 範圍 | 參考 |
| :- | :- | :- | :- |
| 為 Claude 提供專案上下文和慣例 | `CLAUDE.md` | 專案或全域 | [Memory](https://code.claude.com/docs/zh-TW/memory.md) |
| 允許或阻止特定工具呼叫 | `settings.json` `permissions` 或 `hooks` | 專案或全域 | [Permissions](https://code.claude.com/docs/zh-TW/permissions.md)、[Hooks](https://code.claude.com/docs/zh-TW/hooks.md) |
| 在工具呼叫之前或之後執行指令碼 | `settings.json` `hooks` | 專案或全域 | [Hooks](https://code.claude.com/docs/zh-TW/hooks.md) |
| 為工作階段設定環境變數 | `settings.json` `env` | 專案或全域 | [Settings](https://code.claude.com/docs/zh-TW/settings-reference.md#all-settings) |
| 將個人覆蓋保留在 git 之外 | `settings.local.json` | 僅專案 | [Settings scopes](https://code.claude.com/docs/zh-TW/settings.md#where-settings-live) |
| 新增您使用 `/name` 叫用的提示或功能 | `skills/<name>/SKILL.md` | 專案或全域 | [Skills](https://code.claude.com/docs/zh-TW/skills.md) |
| 定義具有自己工具的專門 subagent | `agents/*.md` | 專案或全域 | [Subagents](https://code.claude.com/docs/zh-TW/sub-agents.md) |
| 透過指令碼協調許多 subagent | `workflows/*.js` | 專案或全域 | [Dynamic workflows](https://code.claude.com/docs/zh-TW/workflows.md) |
| 透過 MCP 連接外部工具 | `.mcp.json` | 僅專案 | [MCP](https://code.claude.com/docs/zh-TW/mcp.md) |
| 變更 Claude 格式化回應的方式 | `output-styles/*.md` | 專案或全域 | [Output styles](https://code.claude.com/docs/zh-TW/output-styles.md) |

## 檔案參考

此表列出探索器涵蓋的每個檔案。專案範圍的檔案位於您的儲存庫中的 `.claude/` 下（或 `CLAUDE.md`、`.mcp.json` 和 `.worktreeinclude` 的根目錄）。全域範圍的檔案位於 `~/.claude/` 中，適用於所有專案。

> [!NOTE]
>
> 有幾件事可以覆蓋您在這些檔案中放入的內容：
>
> * 您的組織部署的[受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)優先於所有設定檔和 `--settings` 值，除了[設定優先順序下的例外](https://code.claude.com/docs/zh-TW/settings.md#exceptions-to-managed-settings-precedence)
> * CLI 旗標（如 `--permission-mode` 或 `--settings`）會覆蓋該工作階段的 `settings.json`
> * 某些環境變數優先於其等效設定，但這會有所不同：檢查[環境變數參考](https://code.claude.com/docs/zh-TW/env-vars.md)以了解每個變數
>
> 請參閱[設定優先順序](https://code.claude.com/docs/zh-TW/settings.md#settings-precedence)以了解完整順序。

點擊檔案名稱以在上方的探索器中開啟該節點。

| 檔案 | 範圍 | 提交 | 功能 | 參考 |
| - | - | - | - | - |
| [`CLAUDE.md`](#ce-claude-md) | 專案和全域 | ✓ | 每個工作階段載入的指令 | [Memory](https://code.claude.com/docs/zh-TW/memory.md) |
| [`rules/*.md`](#ce-rules) | 專案和全域 | ✓ | 主題範圍的指令，可選擇路徑限制 | [Rules](https://code.claude.com/docs/zh-TW/memory.md#organize-rules-with-claude/rules/) |
| [`settings.json`](#ce-settings-json) | 專案和全域 | ✓ | 權限、hooks、環境變數、模型預設值 | [Settings](https://code.claude.com/docs/zh-TW/settings.md) |
| [`settings.local.json`](#ce-settings-local-json) | 僅專案 | | 您的個人覆蓋，當 Claude Code 將設定儲存到其中時會自動 gitignored | [Settings scopes](https://code.claude.com/docs/zh-TW/settings.md#where-settings-live) |
| [`.mcp.json`](#ce-mcp-json) | 僅專案 | ✓ | 團隊共享的 MCP 伺服器 | [MCP scopes](https://code.claude.com/docs/zh-TW/mcp.md#mcp-installation-scopes) |
| [`.worktreeinclude`](#ce-worktreeinclude) | 僅專案 | ✓ | Gitignored 檔案以複製到新的 worktrees | [Worktrees](https://code.claude.com/docs/zh-TW/worktrees.md#copy-gitignored-files-into-worktrees) |
| [`skills/<name>/SKILL.md`](#ce-skills) | 專案和全域 | ✓ | 可重複使用的提示，使用 `/name` 叫用或自動叫用 | [Skills](https://code.claude.com/docs/zh-TW/skills.md) |
| [`commands/*.md`](#ce-commands) | 專案和全域 | ✓ | 單檔案提示；與 skills 相同的機制 | [Skills](https://code.claude.com/docs/zh-TW/skills.md) |
| [`output-styles/*.md`](#ce-output-styles) | 專案和全域 | ✓ | 自訂指令集，調整 Claude 的工作方式 | [Output styles](https://code.claude.com/docs/zh-TW/output-styles.md) |
| [`agents/*.md`](#ce-agents) | 專案和全域 | ✓ | Subagent 定義及其自己的提示和工具 | [Subagents](https://code.claude.com/docs/zh-TW/sub-agents.md) |
| [`workflows/*.js`](#ce-workflows) | 專案和全域 | ✓ | Claude 撰寫並從 `/workflows` 儲存的動態工作流程指令碼；每個檔案都會變成 `/<name>` 命令 | [Dynamic workflows](https://code.claude.com/docs/zh-TW/workflows.md) |
| [`agent-memory/<name>/`](#ce-agent-memory) | 專案和全域 | ✓ | Subagents 的持久記憶 | [Persistent memory](https://code.claude.com/docs/zh-TW/sub-agents.md#enable-persistent-memory) |
| [`~/.claude.json`](#ce-claude-json) | 僅全域 | | 應用程式狀態、帳戶詳細資料、UI 切換、個人 MCP 伺服器。若此檔案不存在，Claude Code 會在您啟動工作階段或執行子命令（例如 `claude auth status`）時建立它，但執行 `--version` 或 `--help` 時不會建立。 | [Global config](https://code.claude.com/docs/zh-TW/settings-reference.md#global-config-settings) |
| [`projects/<project>/memory/`](#ce-global-projects) | 僅全域 | | 自動記憶：Claude 在工作階段間對自己的筆記 | [Auto memory](https://code.claude.com/docs/zh-TW/memory.md#auto-memory) |
| [`keybindings.json`](#ce-keybindings) | 僅全域 | | 自訂快捷鍵 | [Keybindings](https://code.claude.com/docs/zh-TW/keybindings.md) |
| [`themes/*.json`](#ce-themes) | 僅全域 | | 自訂色彩主題 | [Custom themes](https://code.claude.com/docs/zh-TW/terminal-config.md#create-a-custom-theme) |

## 按檔案分類的 Frontmatter 欄位

Skills、命令檔案、子代理、輸出樣式和規則從檔案頂部的 YAML [frontmatter](https://code.claude.com/docs/zh-TW/glossary.md#frontmatter) 讀取其設定，每個都接受自己的一組欄位。此表列出每個檔案的欄位名稱，並連結到描述它們的參考資料。

| 檔案 | Frontmatter 欄位 | 參考資料 |
| - | - | - |
| `skills/<name>/SKILL.md` | `name`, `description`, `when_to_use`, `argument-hint`, `arguments`, `disable-model-invocation`, `user-invocable`, `allowed-tools`, `disallowed-tools`, `model`, `effort`, `context`, `agent`, `background`, `hooks`, `paths`, `shell`, `metadata`, `license`, `compatibility` | [Skill frontmatter](https://code.claude.com/docs/zh-TW/skills.md#frontmatter-reference) |
| `commands/*.md` | 除了 `name` 和 `paths` 之外的 skill 欄位 | [Skill frontmatter](https://code.claude.com/docs/zh-TW/skills.md#frontmatter-reference) |
| `agents/*.md` | `name`, `description`, `tools`, `disallowedTools`, `model`, `permissionMode`, `maxTurns`, `autoCompactWindow`, `skills`, `mcpServers`, `hooks`, `memory`, `background`, `effort`, `isolation`, `color`, `initialPrompt`, `omitClaudeMd`, `experimental` | [Subagent frontmatter](https://code.claude.com/docs/zh-TW/sub-agents.md#supported-frontmatter-fields) |
| `output-styles/*.md` | `name`, `description`, `keep-coding-instructions`, `force-for-plugin` | [Output style frontmatter](https://code.claude.com/docs/zh-TW/output-styles.md#frontmatter) |
| `rules/*.md` | `paths` | [Rule frontmatter](https://code.claude.com/docs/zh-TW/memory.md#rules-frontmatter-reference) |

在 [plugin](https://code.claude.com/docs/zh-TW/plugins/components.md#agents) 中提供的代理遵守子代理欄位的子集。

## 疑難排解設定

如果設定、hook 或檔案未生效，請參閱[偵錯您的設定](https://code.claude.com/docs/zh-TW/debug-your-config.md)以取得檢查命令和症狀優先查詢表。

## 應用程式資料

除了你編寫的設定外，`~/.claude` 還保存 Claude Code 在工作階段期間寫入的資料。這些檔案是純文字格式。任何通過工具的內容都會被寫入磁碟上的文字記錄：檔案內容、命令輸出、貼上的文字。

逐字稿也可能包含 Claude Code 隨您的訊息一併傳送給模型的內容：

* 系統提示詞
* 工具定義
* 請求參數
* 它載入的指令檔案，例如 CLAUDE.md

### 自動清理

Claude Code 會刪除下列路徑中的檔案，只要它們的年齡超過 [`cleanupPeriodDays`](https://code.claude.com/docs/zh-TW/settings-reference#cleanupperioddays)，只要它能安全地確定保留期間。預設值為 30 天，最小值為 1；設定 `0` 會導致驗證錯誤。相同的年齡截止值也適用於 [孤立 worktrees](https://code.claude.com/docs/zh-TW/worktrees.md#clean-up-subagent-and-background-session-worktrees) 的自動移除。

| `~/.claude/` 下的路徑 | 內容 |
| - | - |
| `projects/<project>/<session>.jsonl` | 對話逐字稿：訊息、工具呼叫和工具結果，以及 Claude Code 傳送給模型之請求的系統提示詞、工具定義和參數 |
| `projects/<project>/<session>.orphaned-<timestamp>-<suffix>.jsonl`、`projects/<project>/<session>.jsonl.superseded-<timestamp>` | Claude Code 為該工作階段設置的先前文字記錄，而不是覆蓋或刪除它。它不會出現在工作階段選擇器中 |
| `projects/<project>/<session>/subagents/` | [Subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 逐字稿，格式與工作階段逐字稿相同，當父工作階段逐字稿過期時一併移除 |
| `projects/<project>/<session>/tool-results/` | 溢出到單獨檔案的大型工具輸出，以及 [MCP 工具返回的圖片](https://code.claude.com/docs/zh-TW/mcp.md#images-in-tool-results) 的完整大小副本 |
| `projects/<project>/<session>/mcp-tasks/` | 恢復的工作階段再次追蹤其執行中的 [MCP 任務](https://code.claude.com/docs/zh-TW/mcp.md#mcp-tasks-that-run-on-the-server)所需的資訊，以及 Claude 尚未讀取的已完成任務結果 |
| `file-history/<session>/` | Claude 更改的檔案的編輯前快照，用於 [檢查點還原](https://code.claude.com/docs/zh-TW/checkpointing.md)。保存 100 個最近檢查點的快照；沒有保留檢查點引用的快照檔案會被刪除，除了每個檔案的第一個快照 |
| `plans/` | 在 [計畫模式](https://code.claude.com/docs/zh-TW/permission-modes.md#analyze-before-you-edit-with-plan-mode) 期間寫入的計畫檔案 |
| `debug/` | 每個工作階段的偵錯日誌，在啟用偵錯日誌時寫入，例如當你使用 [`--debug`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 啟動或執行 `/debug` 時 |
| `paste-cache/` | 大型貼上內容的內容 |
| `image-cache/<session>/` | Claude Code v2.1.274 及更早版本保存的附加圖片。更新版本將貼上和附加的圖片保存在 `~/.claude` 外，在 [`CLAUDE_CODE_TMPDIR`](https://code.claude.com/docs/zh-TW/env-vars) 控制的暫存目錄下每個工作階段的 `images/` 目錄中。掃描會移除其他工作階段在此處留下的目錄，無論其年齡如何。 |
| `uploads/<session>/` | 你從網路或行動應用程式附加的檔案，以及從行動應用程式附加的照片，當訊息傳送到 [遠端控制](https://code.claude.com/docs/zh-TW/remote-control.md) 工作階段時。附加到 [雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md) 的附件會保存在該工作階段自己的雲端環境中，而不是在你的機器上。 |
| `dev-mods/<session>/` | [Claude 在工作階段期間寫入的 Mods](https://code.claude.com/docs/zh-TW/plugins/mods/create.md#ask-claude-for-a-mod) |
| `session-env/` | 每個工作階段的環境中繼資料 |
| `tasks/` | 由任務工具寫入的任務清單，每個清單一個目錄 |
| `shell-snapshots/` | 在啟動時捕獲的別名、函數和 shell 選項，由 [Bash 工具](https://code.claude.com/docs/zh-TW/tools-reference.md#bash-tool-behavior) 應用於每個命令。在正常退出時移除。掃描會清除任何在崩潰後留下的內容。 |
| `backups/` | `~/.claude.json` 的早期版本，在 Claude Code 重寫檔案時複製。Claude Code 保留五個最新版本，加上任何它無法解析的版本副本。 |
| `feedback-bundles/` | 由 `/feedback` 在第三方提供商上或當未配置 Anthropic 認證時寫入的編輯後文字記錄存檔，用於發送到你的 Anthropic 帳戶團隊 |
| `feedback/drafts/` | 排隊的 [Claude 起草的回饋](https://code.claude.com/docs/zh-TW/tools-reference.md#sendfeedback-tool-behavior) 等待你在 `/feedback` 中審查。在 `cleanupPeriodDays` 或 30 天後掃描，以較短者為準。當佇列達到其 10 份草稿限制時，Claude Code 會刪除最舊的草稿以騰出空間。 |
| `usage-data/` | 由 [`/insights`](https://code.claude.com/docs/zh-TW/costs#analyze-your-usage-patterns) 寫入的 `report.html` 和時間戳記報告副本，加上用於建立它們的快取每個工作階段分析資料 |
| `skills/.trash/`、`plugins/.trash/` | claude.ai 同步移除的 [技能](https://code.claude.com/docs/zh-TW/skills.md#how-synced-skills-behave) 和 [外掛程式](https://code.claude.com/docs/zh-TW/plugins/loading.md#synced-plugins)，例如在你在 claude.ai 上關閉一個或停止同步後。檔案保留在此處，以便你可以恢復它們，直到掃描刪除它們 |
| `plugins/installed_plugins.set-aside.<date>.<hash>.json`、`plugins/installed_plugins.unreadable.<date>.<hash>.kept` | Claude Code 在重寫 [`installed_plugins.json`](https://code.claude.com/docs/zh-TW/plugins/loading#find-plugins-on-disk) 之前製作的日期副本：安裝記錄它刪除，以及它無法讀取的檔案的內容。 |
| `todos/`、`statsig/`、`logs/` | 來自舊版本的舊版目錄。不再寫入。掃描會移除其內容，然後移除空目錄。 |

`sessions/` 中的工作階段檔案、自動記憶和 Claude Desktop 及 Cowork 文字記錄各自遵循自己的保留規則：

* **`sessions/`**：為每個執行中的工作階段保存一個小檔案，用於偵測並行工作階段和崩潰。它不是基於年齡的掃描的一部分：Claude Code 在其工作階段退出時移除每個檔案，並在下次啟動時清除崩潰遺留物。
* **自動記憶**：掃描不會刪除專案 [自動記憶](https://code.claude.com/docs/zh-TW/memory.md#auto-memory) 目錄 `projects/<project>/memory/` 中的記憶檔案。Claude Code 只有在整個保留期間該目錄一直為空時才會移除它。在 v2.1.228 之前，掃描將記憶目錄內的資料夾視為工作階段資料，可能會刪除其下的舊檔案。
* **Claude Desktop 和 Cowork 逐字稿**：對於您在 Claude Desktop 或 Cowork 中啟動或最近繼續的工作階段，Claude Code 會保留其逐字稿，無論年齡如何。若要為這些逐字稿設定年齡限制，請設定 [`desktopSessionCleanupPeriodDays`](https://code.claude.com/docs/zh-TW/settings-reference#desktopsessioncleanupperioddays)。需要 Claude Code v2.1.248 或更新版本；較早版本會在 `cleanupPeriodDays` 後刪除它們。

  在下列任一情況下，Claude Code 會改為在 `cleanupPeriodDays` 後刪除這些逐字稿：

  * [受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)設定了 `cleanupPeriodDays`
  * [HIPAA 設定套用於您的工作階段](https://code.claude.com/docs/zh-TW/hipaa-setup.md#check-how-developers-sign-in-and-connect)

Claude Code 在這些情況下跳過基於年齡的掃描：

* **裸機模式**：當你使用 [`--bare`](https://code.claude.com/docs/zh-TW/headless#start-faster-with-bare-mode) 執行 `claude -p` 時，Claude Code 不會在該工作階段中執行掃描。
* **暫停掃描**：如果 Claude Code 無法安全地確定保留期間，它會暫停保留清理掃描；[`retention_sweep` 事件](https://code.claude.com/docs/zh-TW/monitoring-usage#retention-sweep-event) 列出每個暫停它的設定。當原因是無法讀取或解析的設定檔案，或 `cleanupPeriodDays` 或 `desktopSessionCleanupPeriodDays` 明確設定的設定錯誤時，Claude Code 也會在 `/status` 中顯示警告，直到你修復設定錯誤。當 [受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md) 提供 `cleanupPeriodDays` 時，Claude Code 在任一情況下都會以受管值執行掃描。

若要確認您組織中的機器是以您設定的保留期間執行掃描，請參閱[檢查保留掃描](https://code.claude.com/docs/zh-TW/monitoring-usage.md#check-the-retention-sweep)。

### 工作階段暫存簿目錄

暫存簿是 Claude Code 為 Claude 提供的每個工作階段目錄，用於臨時檔案：中間結果、輔助指令碼和不屬於你的專案的草稿。當 Claude 說它將某些內容保存到「暫存簿」時，該檔案就在那裡。Claude 使用它而不是 `/tmp`，可以在其中建立、編輯和讀取檔案，無需權限提示。

暫存簿位於 Claude Code 的暫存目錄下，而不是 `~/.claude`。找到你的平台的目前工作階段路徑：

* **macOS**：`/private/tmp/claude-<uid>/<project>/<session-id>/scratchpad/`
* **Linux**：`/tmp/claude-<uid>/<project>/<session-id>/scratchpad/`，或當你的系統設定 `$TMPDIR` 時在其下的相同形狀
* **Windows**：`%TEMP%\claude\<project>\<session-id>\scratchpad\`

`<project>` 是你的工作目錄路徑，其中除字母和數字外的每個字元都被替換為 `-`，例如 `-Users-you-my-project`。如果你設定 [`CLAUDE_CODE_TMPDIR`](https://code.claude.com/docs/zh-TW/env-vars)，樹會改為移到該目錄下。Hooks 接收目前工作階段的路徑作為 [`scratchpad_dir`](https://code.claude.com/docs/zh-TW/hooks#common-input-fields)。

暫存簿檔案的存續時間與工作階段的逐字稿相同：[保留掃描](#cleaned-up-automatically)在刪除逐字稿時會刪除該目錄，而 [`claude purge`](#clear-local-data) 不會觸及暫存目錄。由於該目錄位於系統暫存位置下，您的作業系統也可能清除它，例如在重新啟動時。若要保留 Claude 在那裡寫入的內容，請要求 Claude 將其移到您的專案中。

工作階段只有在以下所有情況都成立時才有暫存簿：

* 你使用 claude.ai 帳戶而不是 API 金鑰登入
* 工作階段使用 Anthropic API，而不是 Amazon Bedrock、Google Cloud 的 Agent Platform 或 Microsoft Foundry
* [`enableArtifact`](https://code.claude.com/docs/zh-TW/settings-reference#enableartifact) 未設定為 `false`

### 保留直到你刪除它們

除了另有說明的列之外，保留清理掃描不會移除下列路徑，Claude Code 會保留它們直到您刪除為止。

| `~/.claude/` 下的路徑 | 內容 |
| - | - |
| `history.jsonl` | 您輸入的提示詞，附有時間戳記和專案路徑。用於向上箭頭叫回、`Ctrl+R` 歷史搜尋和 `!` shell 命令補全。當 [HIPAA 設定套用於您的工作階段](https://code.claude.com/docs/zh-TW/hipaa-setup.md#check-how-developers-sign-in-and-connect)時，每次掃描都會移除超過 `cleanupPeriodDays` 的項目。 |
| `stats-cache.json` | 由 `/usage` 顯示的彙總權杖和成本計數 |
| `remote-settings.json` | [伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md) 的快取副本，用於你的組織，或當你的組織未配置任何設定時為 `{}`。只有在工作階段 [擷取它們](https://code.claude.com/docs/zh-TW/server-managed-settings.md#platform-availability) 時才存在。Claude Code 在啟動時和工作階段期間每小時檢查更新。Claude Code 在你登出時刪除它。 |
| `cache/changelog.md` | Claude Code 變更日誌的快取副本，由 `/release-notes` 顯示。在背景中重新整理。 |
| `policy-limits.json` | 你的組織的快取功能原則設定。僅對某些帳戶類型存在。自動重新整理。`policy-limits.json.stamp.json` 側車記錄快取屬於哪個帳戶或 API 金鑰。Claude Code 在你登出時刪除兩個檔案。 |

#### 應保留的狀態檔案

視您使用的功能而定，`~/.claude/` 還會保存[應用程式資料](#application-data)下各表格未列出的檔案。其中，快取和鎖定檔案可以安全刪除。請保留以下狀態檔案：

* `.credentials.json`：你的 [登入認證](https://code.claude.com/docs/zh-TW/authentication.md#credential-management)
* `agent-memory/`：[子代理記憶](https://code.claude.com/docs/zh-TW/sub-agents.md#enable-persistent-memory)
* `jobs/` 和 `daemon/`：[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md#where-state-is-stored) 狀態

### 純文字儲存

文字記錄和歷史在靜止時未加密。OS 檔案權限是唯一的保護。如果工具讀取 `.env` 檔案或命令列印認證，該值會被寫入 `projects/<project>/<session>.jsonl`。要減少暴露：

* 降低 `cleanupPeriodDays` 以縮短 Claude Code 保留文字記錄的時間
* 設定 [`desktopSessionCleanupPeriodDays`](https://code.claude.com/docs/zh-TW/settings-reference#desktopsessioncleanupperioddays) 以給予 Claude Desktop 和 Cowork 文字記錄年齡限制
* 設定 [`CLAUDE_CODE_SKIP_PROMPT_HISTORY`](https://code.claude.com/docs/zh-TW/env-vars) 環境變數以在任何模式下跳過寫入文字記錄和提示歷史。在非互動模式下，你可以改為在 `-p` 旁邊傳遞 `--no-session-persistence`，或在 TypeScript Agent SDK 中設定 `persistSession: false`；Python SDK 沒有等效選項。
* 使用 [權限規則](https://code.claude.com/docs/zh-TW/permissions.md) 拒絕讀取認證檔案

### 清除本機資料

執行 `claude purge` 以刪除 Claude Code 為某個專案保存的狀態。它會刪除：

* `projects/` 下的文字記錄和自動記憶
* 每個工作階段的 `tasks/`、`debug/` 和 `file-history/` 項目
* `history.jsonl` 中的匹配提示行
* 專案在 `~/.claude.json` 中的項目

你在專案工作階段中貼上或附加的圖片以及每個工作階段的 [暫存簿](#session-scratchpad-directory) 儲存在 Claude Code 的暫存目錄下，而不是 `~/.claude`，所以清除不會移除它們。[保留掃描](#cleaned-up-automatically) 仍會在圖片年齡超過 `cleanupPeriodDays` 時刪除它們；清除的工作階段的暫存簿會保留，直到你刪除它或你的作業系統清除暫存目錄。

該命令列印完整的刪除計畫並在移除任何內容之前要求確認。

在 v2.1.288 之前，此命令為 `claude project purge`。

下面的範例使用 `~/work/my-repo` 作為佔位符。將其替換為你的專案的路徑。如果沒有狀態符合該路徑，該命令會列印錯誤並以狀態 1 退出。

預覽計畫而不刪除任何內容：

```bash theme={null}
claude purge ~/work/my-repo --dry-run
```

該計畫列出每個匹配項目及其包含的原因：

```text theme={null}
Purge plan for /home/user/work/my-repo:

  dir:    /home/user/.claude/projects/-home-user-work-my-repo
           project transcripts (.jsonl) and memory/
  config: projects["/home/user/work/my-repo"]
           project entry in ~/.claude.json (trust, history, MCP servers)
  filter: /home/user/.claude/history.jsonl
           12 prompt(s) typed in this project

shell-snapshots/ are not project-scoped and will not be touched
backups/ may still contain this project entry in old .claude.json snapshots (/home/user/.claude/backups); at most 5 are kept and they rotate out automatically
Dry run: 3 item(s) would be deleted.
```

使用單一確認提示刪除：

```bash theme={null}
claude purge ~/work/my-repo
```

該命令列印相同的計畫，然後詢問 `Delete 3 item(s) for /home/user/work/my-repo? This cannot be undone. [y/N]` 並且只有在你回答 `y` 時才刪除。

省略路徑以從互動清單中選擇專案。

跳過確認提示以在指令碼中使用：

```bash theme={null}
claude purge ~/work/my-repo --yes
```

其他選項：

* 傳遞 `--all` 而不是路徑，以一次清除所有專案的狀態，這會直接刪除 `history.jsonl` 而不是篩選它。
* 傳遞 `-i` 以逐項檢視刪除計畫。

該命令不會動到 `shell-snapshots/` 和 `backups/`，因為它們不屬於專案範圍，並會在計畫輸出中對其發出警告。如果有人曾在該機器上執行 [`/heapdump`](https://code.claude.com/docs/zh-TW/troubleshooting#high-cpu-or-memory-usage)，也請刪除它寫入的 `.heapsnapshot` 檔案。堆積快照包含完整對話以及該程序持有的任何憑證，而保留掃描和清除都不會觸及它。

您也可以自行刪除上述任何應用程式資料路徑，但[應保留的狀態檔案](#state-files-to-keep)除外。

| 刪除 | 你失去 |
| - | - |
| `~/.claude/projects/` | 恢復、繼續和倒帶過去工作階段，以及每個專案的自動記憶 |
| `~/.claude/history.jsonl` | 向上箭頭提示回憶、`Ctrl+R` 歷史搜尋和 `!` shell 命令完成 |
| `~/.claude/paste-cache/` | 回憶提示中的貼上文字；請參閱 [貼上大型內容](https://code.claude.com/docs/zh-TW/terminal-config.md#paste-large-content) |
| `~/.claude/uploads/` | 過去 [遠端控制](https://code.claude.com/docs/zh-TW/remote-control.md) 工作階段按路徑引用的附件 |
| `~/.claude/file-history/` | 過去工作階段的檢查點還原 |
| `~/.claude/stats-cache.json` | 由 `/usage` 顯示的歷史總計 |
| `~/.claude/usage-data/` | 過去的 [`/insights`](https://code.claude.com/docs/zh-TW/costs#analyze-your-usage-patterns) 報告和用於建立它們的快取分析資料 |
| `~/.claude/feedback-bundles/` | 你還未發送到你的 Anthropic 帳戶團隊的回饋和錯誤報告存檔 |
| `~/.claude/feedback/drafts/` | 你未發送的 [Claude 起草的回饋](https://code.claude.com/docs/zh-TW/tools-reference.md#sendfeedback-tool-behavior) |
| `~/.claude/remote-settings.json` | 無。在下次啟動時重新擷取。 |
| `~/.claude/cache/changelog.md` | 無。在背景中重新整理。 |
| `~/.claude/policy-limits.json` | 無。自動重新整理。 |
| `~/.claude/tasks/` | 您的[任務清單](https://code.claude.com/docs/zh-TW/interactive-mode.md#task-list)，包括仍在使用中的清單 |
| `~/.claude/skills/.trash/`、`~/.claude/plugins/.trash/` | 恢復 [同步技能](https://code.claude.com/docs/zh-TW/skills.md#how-synced-skills-behave) 和 [同步外掛程式](https://code.claude.com/docs/zh-TW/plugins/loading.md#synced-plugins) 的機會，Claude Code 已移除 |
| `~/.claude/plugins/installed_plugins.set-aside.<date>.<hash>.json`、`~/.claude/plugins/installed_plugins.unreadable.<date>.<hash>.kept` | Claude Code 刪除的外掛程式安裝記錄或無法讀取的副本。沒有任何東西會讀取它們回來 |
| `~/.claude/debug/`、`~/.claude/plans/`、`~/.claude/session-env/`、`~/.claude/shell-snapshots/`、`~/.claude/backups/` | 無使用者面向的內容 |
| `~/.claude/todos/`、`~/.claude/statsig/`、`~/.claude/logs/`、`~/.claude/image-cache/` | 無。舊版本的舊版目錄，不由目前版本寫入。 |

請勿刪除 `~/.claude.json`、`~/.claude/settings.json` 或 `~/.claude/plugins/`：這些檔案保存您的帳戶詳細資料、偏好設定和已安裝的外掛。

## 相關資源

* [管理 Claude 的記憶](https://code.claude.com/docs/zh-TW/memory.md)：寫入和組織 CLAUDE.md、rules 和自動記憶
* [設定設定](https://code.claude.com/docs/zh-TW/settings.md)：設定權限、hooks、環境變數和模型預設值
* [建立 skills](https://code.claude.com/docs/zh-TW/skills.md)：建立可重複使用的提示和工作流程
* [設定 subagents](https://code.claude.com/docs/zh-TW/sub-agents.md)：定義具有自己上下文的專門代理

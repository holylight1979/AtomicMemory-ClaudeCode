<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/commands | lastmod: 2026-11-03 | section: Reference / Reference -->
> 來源：https://code.claude.com/docs/zh-TW/commands（官方 zh-TW，lastmod 2026-11-03）｜分類：Reference › Reference｜EN 摘要：Complete reference for commands available in Claude Code, including built-in commands and bundled skills.

# Commands

> Claude Code 中可用命令的完整參考，包括內建命令和捆綁的 skills。

Commands 從工作階段內控制 Claude Code。它們提供了一種快速方式來切換模型、管理權限、清除上下文、執行工作流程等。

輸入 `/` 以查看可用的命令，或輸入 `/` 後跟字母以篩選。[命令菜單如何匹配您輸入的內容](#how-the-command-menu-matches-what-you-type)涵蓋了突出顯示、拼寫錯誤以及 Claude Code 隱藏的少數命令，直到您輸入其完整名稱。

命令只在您的訊息開始時被識別。命令名稱後面的文字成為其引數。在終端機提示字元中，您可以在一則訊息的開頭使用多個 [skills](https://code.claude.com/docs/zh-TW/skills.md#stack-several-skills-in-one-message)：輸入 `/skill-a /skill-b do XYZ` 會載入這兩個 skills，並將尾部文字作為引數傳遞給每個 skill。最多可以串連六個 skills。

如果您在 Claude 回應時發送命令，Claude Code 會將其排隊，並在目前回合完成後執行。Claude Code 會立即執行某些命令而不中斷回應，例如 `/status`、`/tasks` 和 `/usage`。在[全螢幕渲染](https://code.claude.com/docs/zh-TW/fullscreen.md)中，Claude Code 也會立即開啟對話命令，例如 `/theme` 和 `/help`。在 v2.1.234 之前，Claude Code 會將這些對話排隊直到回合完成。

## 典型工作流程中的指令

大多數指令在工作階段的特定時間點很有用，從設定專案到發佈變更。

**首次在儲存庫中的工作階段。** 執行 `/init` 以產生起始 `CLAUDE.md`，然後執行 `/memory` 以精化它。使用 `/mcp` 設定專案需要的任何伺服器，要求 Claude 建立任何您想要的 [subagents](https://code.claude.com/docs/zh-TW/sub-agents.md)，並執行 `/permissions` 以設定您的核准規則。

**執行工作期間。** `/plan` 在大型變更前切換到 plan mode。`/model` 和 `/effort` 調整您使用的模型以及它應用多少推理。當對話變得冗長時，`/context` 顯示什麼填滿了視窗，`/compact` 將其摘要以釋放空間。使用 `/btw` 進行不應新增至對話歷史記錄的附帶問題。

**並行執行工作。** Claude 將附帶工作委派給 [subagents](https://code.claude.com/docs/zh-TW/sub-agents.md)，`/tasks` 列出目前工作階段的背景工作，包括已完成的 subagents。`/background` 分離整個工作階段以繼續作為 [background agent](https://code.claude.com/docs/zh-TW/agent-view.md) 執行，並釋放您的終端。對於跨越程式碼庫的大型變更，`/batch` 將其分解為獨立單位，並在其自己的 [worktree](https://code.claude.com/docs/zh-TW/worktrees.md) 中執行每個單位。請參閱 [Run agents in parallel](https://code.claude.com/docs/zh-TW/agents.md) 以了解這些方法如何相關。

**在您發佈前。** `/diff` 顯示變更的內容。`/code-review` 檢查目前的 diff 是否有正確性錯誤，並可以使用 `--fix` 套用發現；傳遞 PR 編號，例如 `/code-review high 1234`，以改為檢查 pull request。`/review` 是別名。`/code-review ultra` 在雲端執行多代理檢查。`/security-review` 檢查 diff 是否有安全漏洞。

**工作階段之間。** `/clear` 在保持專案記憶的同時開始新工作。`/resume` 返回較早的對話，`/branch` 分支目前的對話以嘗試不同的方向，`/fork` 將其複製到新的 [背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)。`/teleport` 將雲端工作階段拉入此終端機，`/remote-control` 讓您從另一個裝置繼續此本機工作階段。

**當出現問題時。** `/rewind` 將程式碼和對話回復到檢查點，或摘要對話的一部分。`/doctor` 執行設定檢查，診斷安裝和設定問題，並可以修復它們，`/debug` 診斷執行時問題，`/feedback` 報告附加工作階段內容的錯誤。

## 所有命令

下表列出 Claude Code 中包含的所有命令。大多數是內建命令，其行為已編碼到 CLI 中。有兩種類型的項目被標記：

* **[Skill](https://code.claude.com/docs/zh-TW/skills.md#bundled-skills)**：一個隨附 skill。它的運作方式與您自己編寫的 skill 相同：一個交給 Claude 的提示詞。
  * `/verify` 僅在您調用時運行。
* **[Workflow](https://code.claude.com/docs/zh-TW/workflows.md#bundled-workflows)**：一個隨附的[動態工作流程](https://code.claude.com/docs/zh-TW/workflows.md)，可將工作分散到多個 subagent 並在背景運行。
  * `/deep-research` 僅在您調用時運行。

要添加您自己的命令，請參閱 [skill](https://code.claude.com/docs/zh-TW/skills.md)。

在下表中，`<arg>` 表示必需的引數，`[arg]` 表示可選的引數。

> [!NOTE]
>
> 並非每個命令都對每個使用者顯示。可用性取決於您的平台、方案和環境。例如，`/desktop` 僅在 macOS 和 x64 Windows 上使用 Claude 訂閱登入時顯示，而 `/upgrade` 在企業方案上不顯示。

| 命令 | 用途 |
| :- | :- |
| `/add-dir <path>` | 添加工作目錄以在目前工作階段期間進行檔案存取。輸入部分路徑以查看匹配的目錄建議；按 `Tab` 接受一個。大多數 `.claude/` 設定[不會從添加的目錄中發現](https://code.claude.com/docs/zh-TW/permissions.md#additional-directories-grant-file-access-not-configuration)。您無法添加大多數[網路路徑](https://code.claude.com/docs/zh-TW/errors.md#working-directory-is-a-network-path)，例如 `\\server\share`。成功添加後，您的 [`DirectoryAdded` hook](https://code.claude.com/docs/zh-TW/hooks#directoryadded) 會運行。當您在 Claude 回應時運行它時，Claude Code 會要求您立即確認目錄，一旦您確認，Claude 在同一回合中的下一個工具呼叫就可以存取它。在 v2.1.234 之前，Claude Code 會將命令排隊直到該回合完成 |
| `/advisor [model\|off]` | 啟用或停用[顧問工具](https://code.claude.com/docs/zh-TW/advisor.md)，它在任務期間的關鍵時刻諮詢第二個模型以獲得指導。接受 `fable`、`opus`、`sonnet` 或完整的模型 ID。`fable` 需要 [Fable 存取](https://code.claude.com/docs/zh-TW/advisor.md#choose-an-advisor-model)。沒有引數時，打開選擇器。在沒有互動式終端機的工作階段中，或通過 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md#limitations)，將模型或 `off` 作為引數傳遞；在那裡沒有引數時，命令會將目前顧問列印為文字。這些形式需要 Claude Code v2.1.260 或更新版本 |
| `/agents` | 列印提醒以要求 Claude 建立或管理 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md)，或直接編輯 `.claude/agents/` 或 `~/.claude/agents/`。在 v2.1.197 及更早版本上，打開用於建立和管理 subagent 設定的互動式介面 |
| `/artifact-capabilities` | **[Skill](https://code.claude.com/docs/zh-TW/skills.md#bundled-skills)。** 載入已發佈 [artifact](https://code.claude.com/docs/zh-TW/artifacts.md) 可以使用的執行時功能的參考，例如[呼叫您的連接器](https://code.claude.com/docs/zh-TW/artifacts.md#pull-live-data-with-mcp-connectors)或[提供檔案下載](https://code.claude.com/docs/zh-TW/artifacts.md#offer-a-file-download)，包括您的帳戶擁有的功能。Claude 通常在建立使用其中一個的頁面前自行載入它。在 [artifact](https://code.claude.com/docs/zh-TW/artifacts.md#availability) 可用的地方可用 |
| `/artifact-diagramming` | **[Skill](https://code.claude.com/docs/zh-TW/skills.md#bundled-skills)。** 為 Claude 在 [artifact](https://code.claude.com/docs/zh-TW/artifacts.md) 中遵循的圖表載入指導：何時圖表有幫助、要繪製什麼以及如何編寫在淺色和深色主題中保持清晰的內聯 SVG。需要 Claude Code v2.1.221 或更新版本 |
| `/artifacts` | 列出您擁有或與您共享的 [artifact](https://code.claude.com/docs/zh-TW/artifacts.md#find-an-artifact-again)，然後將其附加到工作階段、在瀏覽器中打開它或複製其連結。在 [artifact](https://code.claude.com/docs/zh-TW/artifacts.md#availability) 可用的地方可用 |
| `/auto-mode-setup` | [從您的專案和最近的工作階段草擬 `autoMode.environment` 項目](https://code.claude.com/docs/zh-TW/auto-mode-config#generate-environment-entries)，然後檢查草稿並將其保存到您的使用者設定。在 Pro、Max、Ultra 或 Team 方案上，需要 Claude Code v2.1.228 或更新版本，在原生 Windows 上則需要 v2.1.233 或更新版本。在 Enterprise 方案上或使用 Claude Console API 金鑰時，需要 v2.1.283 或更新版本。如果此命令不存在，請參閱[`/auto-mode-setup` 傳回 "Unknown command"](https://code.claude.com/docs/zh-TW/auto-mode-config#auto-mode-setup-returns-unknown-command) |
| `/autocompact [auto\|<tokens>]` | 設定自動壓縮視窗：在 Claude Code 自動壓縮之前上下文視窗有多滿。傳遞大小（例如 `500k`）或 `auto` 以返回為您的模型調整的視窗。Claude Code 將該值保存到使用者設定並將其應用於目前工作階段。有關接受的值以及覆寫它的內容，請參閱[設定自動壓縮視窗](https://code.claude.com/docs/zh-TW/model-config.md#set-the-auto-compact-window)。沒有引數時，打開顯示目前視窗的對話框。需要 Claude Code v2.1.221 或更新版本 |
| `/autofix-pr [prompt]` | 生成一個[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#auto-fix-pull-requests)，監視目前分支的 PR 並在 CI 失敗或審查者留下評論時推送修復。使用 `gh pr view` 從您簽出的分支檢測打開的 PR；要監視不同的 PR，請先簽出其分支。預設情況下，雲端工作階段被告知修復每個 CI 失敗和審查評論；傳遞提示詞以給它不同的指示，例如 `/autofix-pr only fix lint and type errors`。需要 `gh` CLI 和[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)的存取 |
| `/background [prompt]` | 分離目前工作階段以作為[背景 agent](https://code.claude.com/docs/zh-TW/agent-view.md) 運行並釋放此終端機。傳遞提示詞以在分離前發送一個進一步的指示。使用 `claude agents` 監視工作階段。要將對話複製到新的背景工作階段，同時此工作階段保持運行，請使用 `/fork`。別名：`/bg` |
| `/batch <instruction>` | **[Skill](https://code.claude.com/docs/zh-TW/skills.md#bundled-skills)。** 跨程式碼庫並行協調大規模變更。研究程式碼庫，將工作分解為 5 到 30 個獨立單位，並呈現計畫。獲得批准後，在隔離的 [worktree](https://code.claude.com/docs/zh-TW/worktrees.md) 中為每個單位生成一個[背景 subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#run-subagents-in-foreground-or-background)。每個 subagent 實現其單位、運行測試，並開啟 PR 或報告發生的情況。需要 git 儲存庫或建立 worktree 的 [`WorktreeCreate` hook](https://code.claude.com/docs/zh-TW/worktrees#non-git-version-control)。在 git 儲存庫外，`/batch` 需要 Claude Code v2.1.281 或更新版本。範例：`/batch migrate src/ from JavaScript to TypeScript` |
| `/branch [name]` | 在此點建立目前對話的分支，以便您可以嘗試不同的方向而不會丟失目前的對話。切換到分支並保留原始分支，您可以使用 `/resume` 返回。要運行副本作為單獨的[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)而不是切換到它，請使用 `/fork`；要將側面任務交給 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 以報告回此對話，請使用 `/subtask` |
| `/btw [question]` | 詢問有關目前工作階段的[側面問題](https://code.claude.com/docs/zh-TW/interactive-mode.md#side-questions-with-%2Fbtw)而不添加到對話中。如果您運行 `/btw` 而沒有問題，Claude Code 會顯示您最近的側面問題，以便您可以瀏覽較早的答案；如果您還沒有提出問題，Claude Code 會列印使用行 |
| `/bug [report]` | 報告錯誤或分享您的對話。您選擇要包含多少工作階段歷史記錄，並在發送任何內容之前在同意螢幕上確認。當您在第一方連線上登入 Anthropic 時，報告會發送給 Anthropic；在第三方提供者上，或沒有 Anthropic 憑證，Claude Code 會將報告寫入[`~/.claude/feedback-bundles/` 下的本地存檔](https://code.claude.com/docs/zh-TW/data-usage#telemetry-services)，您可以自己轉發。在 [VS Code 擴充功能](https://code.claude.com/docs/zh-TW/vs-code.md#use-the-prompt-box)中，`/bug` 改為打開擴充功能自己的回饋對話框；需要 Claude Code v2.1.229 或更新版本。當您在 Claude 回應時運行它時，Claude Code 會立即打開對話框。在 v2.1.232 之前，Claude Code 會將命令排隊直到該回合完成。別名：`/share`。在 v2.1.212 之前，`/bug` 和 `/share` 是 `/feedback` 的別名 |
| `/cd <path>` | 將此工作階段移動到新的工作目錄，保持對話。輸入部分路徑以查看匹配的目錄建議；按 `Tab` 接受一個。有關 Claude Code 從新目錄立即應用的內容以及 `/cd` 與 `/add-dir` 的區別，請參閱[將工作階段移動到另一個目錄](https://code.claude.com/docs/zh-TW/permissions.md#move-the-session-to-another-directory) |
| `/chrome` | 設定 [Claude in Chrome](https://code.claude.com/docs/zh-TW/chrome.md) 設定 |
| `/claude-api [migrate\|upgrade\|api-version\|managed-agents-onboard\|managed-agents-secure\|prompt-audit\|cost-optimize\|build-eval\|hillclimb\|preserved-thinking-migration]` | **[Skill](https://code.claude.com/docs/zh-TW/skills.md#bundled-skills)。** 為您的專案語言載入 [Claude API](https://platform.claude.com/docs/en/api/overview) 和 [Managed Agents](https://platform.claude.com/docs/en/managed-agents/overview) 參考資料。當您的程式碼匯入 `anthropic` 或 `@anthropic-ai/sdk` 時也會自動啟動。有關每個子命令的作用以及它需要的版本，請參閱[在 Claude API 專案上工作](https://code.claude.com/docs/zh-TW/skills.md#work-on-claude-api-projects) |
| `/claude-in-chrome [task]` | **[Skill](https://code.claude.com/docs/zh-TW/skills.md#bundled-skills)。** 讓 Claude 通過 [Claude in Chrome](https://code.claude.com/docs/zh-TW/chrome.md) 在您的瀏覽器中執行任務，例如測試頁面、填充表單或讀取控制台日誌。在為工作階段啟用 Chrome 整合時可用，例如使用 `claude --chrome`，或當 Claude Code 可以提供[安裝擴充功能](https://code.claude.com/docs/zh-TW/chrome.md#install-the-extension-when-claude-asks)時 |
| `/clear [name]` | 使用空上下文啟動新對話。傳遞名稱以在 `/resume` 選擇器中標記先前的對話。要在繼續相同對話的同時釋放上下文，請改用 `/compact`。使用 `/resume` 恢復先前的對話，或在同一 Claude Code 程序中，從[倒帶選單的上一個工作階段項目](https://code.claude.com/docs/zh-TW/checkpointing.md#rewind-past-a-cleared-conversation)恢復它。別名：`/reset`、`/new` |
| `/code-review [low\|medium\|high\|xhigh\|max\|ultra] [--fix] [--comment] [--max-findings n\|all\|default] [pr#\|branch\|path]` | **[Skill](https://code.claude.com/docs/zh-TW/skills.md#bundled-skills)。** 檢查目前差異或您傳遞的 PR 編號、分支或路徑，以查找正確性錯誤。根據您的模型和 effort 等級，檢查也涵蓋清理機會。傳遞 `--fix` 以應用發現，`--comment` 以在 GitHub PR 或 GitLab merge request 上發佈它們，或 `ultra` 以運行深度[雲端審查](https://code.claude.com/docs/zh-TW/ultrareview.md)。發佈到 GitLab merge request 需要 Claude Code v2.1.257 或更新版本。在 `github.com` PR 目標上使用 `ultra` 時，傳遞 `--post` 以在啟動對話框中預先選擇[將完成的發現發佈到 PR](https://code.claude.com/docs/zh-TW/ultrareview.md#post-findings-to-the-pull-request)；`--post` 需要 Claude Code v2.1.227 或更新版本。有關 effort 等級、目標設定以及它與 `/simplify` 的關係，請參閱[使用 `/code-review` 在本地檢查](https://code.claude.com/docs/zh-TW/code-review-local)。別名：`/review` |
| `/color [color\|default]` | 設定目前工作階段的提示詞欄顏色。可用顏色：`red`、`blue`、`green`、`yellow`、`purple`、`orange`、`pink`、`cyan`。使用 `default` 重置，或運行時不帶引數以選擇隨機顏色。當 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 連接時，顏色會同步到 claude.ai/code。也可在非互動模式 (`-p`) 中使用 |
| `/compact [instructions]` | 通過總結到目前為止的對話來釋放上下文。可選地傳遞焦點指示以進行摘要。請參閱[壓縮如何處理規則、skill 和記憶檔案](https://code.claude.com/docs/zh-TW/context-window.md#what-survives-compaction) |
| `/config [key=value ...]` | 打開[設定](https://code.claude.com/docs/zh-TW/settings.md)介面以調整主題、模型、[輸出風格](https://code.claude.com/docs/zh-TW/output-styles.md)和其他偏好設定。傳遞一個或多個 `key=value` 對以直接設定設定而不打開介面，例如 `/config thinking=false`、`/config theme=dark` 或 `/config model=sonnet`。`key=value` 形式也適用於非互動模式 (`-p`) 和來自 Claude 行動應用程式通過 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md)。`key=value` 形式無法打開需要您在面板中確認的設定，例如 [`autoContinueAtUsageLimit`](https://code.claude.com/docs/zh-TW/interactive-mode#turn-automatic-continue-off)，儘管它可以關閉一個。運行 `/config --help` 以列出它接受的鍵。別名：`/settings` |
| `/context [all]` | 將目前上下文使用情況視覺化為彩色網格。顯示上下文繁重工具、記憶膨脹和容量警告的最佳化建議。當對話超過上下文視窗時，輸出包括[警告](https://code.claude.com/docs/zh-TW/errors.md#context-exceeds-the-token-limit)，顯示您超過限制的距離以及哪個命令釋放空間。在[全螢幕模式](https://code.claude.com/docs/zh-TW/fullscreen.md)中，`/context` 會摺疊每項細目以保持網格可見。傳遞 `all` 以展開它 |
| `/copy [N]` | 將最後的助手回應複製到剪貼簿。傳遞數字 `N` 以複製第 N 個最新回應：`/copy 2` 複製倒數第二個。當存在程式碼區塊或引用區塊時，顯示互動式選擇器以選擇個別區塊或完整回應。在選擇器中按 `w` 以將選擇寫入檔案而不是剪貼簿，這在 SSH 上很有用 |
| `/cost` | `/usage` 的別名 |
| `/dataviz [request]` | **[Skill](https://code.claude.com/docs/zh-TW/skills.md#bundled-skills)。** 圖表、圖形和儀表板的設計指導。Claude 為資料選擇圖表形式，按角色分配顏色，使用隨附的指令碼驗證調色板以確保色盲安全和對比度，並應用標記、互動和可存取性規則。使用您用自己的調色板替換的品牌中立佔位符調色板 |
| `/debug [description]` | **[Skill](https://code.claude.com/docs/zh-TW/skills.md#bundled-skills)。** 為目前工作階段啟用偵錯日誌記錄並通過讀取工作階段偵錯日誌來排除故障。除非您使用 `claude --debug` 啟動，否則偵錯日誌記錄預設為關閉，因此在工作階段中期運行 `/debug` 會從該點開始捕獲日誌。可選地描述問題以集中分析 |
| `/deep-research <question>` | **[Workflow](https://code.claude.com/docs/zh-TW/workflows.md#bundled-workflows)。** 在問題上展開網路搜尋、擷取和交叉檢查來源，並合成引用的報告 |
| `/design [brief]` | **[Skill](https://code.claude.com/docs/zh-TW/skills.md#bundled-skills)。** 在一個畫布上草擬 UI 模型、螢幕流程、登陸頁面或海報作為畫板，發佈為 Claude Design [artifact](https://code.claude.com/docs/zh-TW/artifacts.md#draft-a-design-canvas)，例如 `/design a settings screen for a mobile banking app`。您在桌面瀏覽器中編輯畫板，您的編輯會自動保存。您可以將每個畫板匯出為 PNG 或 PDF。需要 Claude Code v2.1.265 或更新版本、[artifact 可用](https://code.claude.com/docs/zh-TW/artifacts.md#availability)的工作階段，以及[設計範本可用](https://code.claude.com/docs/zh-TW/artifacts.md#start-from-a-slides-design-or-docs-template)的帳戶；如果您的組織已關閉該範本，`/design` 不會草擬設計。在 Anthropic API 上可用。在 Amazon Bedrock、Google Cloud 的 Agent Platform、Microsoft Foundry 和 Claude Platform on AWS 上，artifact 不可用，因此命令在那裡不可用 |
| `/design consent`, `/design revoke` | 授予 Claude 對 [Claude Design](https://claude.ai/design) 的存取權，或撤回該存取權。當 Claude 的回覆要求您運行 `/design consent` 時，請自行在 Claude Code 的提示字元中輸入它 |
| `/design-login` | 使用您的 claude.ai 帳戶授權 `/design-sync` 的設計系統存取。每當 `/design-sync` 或 `/design consent` 告訴您需要登入時，請使用 `/design-login` 登入。此登入適用於位於 claude.ai/design 的獨立 Claude Design 網站，該網站將於 2026 年 12 月 14 日前關閉；請參閱[從獨立 Claude Design 遷移至 Claude](https://support.claude.com/en/articles/17440474-migrate-from-standalone-claude-design-to-claude) |
| `/design-sync [hint]` | **[Skill](https://code.claude.com/docs/zh-TW/skills.md#bundled-skills)。** 轉換您的儲存庫的 React 設計系統並將其上傳到 [Claude Design](https://claude.ai/design)，以便它生成的設計使用您的真實元件。可選地命名設計系統，例如 `/design-sync Acme DS`。首次同步會驗證每個元件，在大型儲存庫上可能需要幾個小時。在 Anthropic API 上可用。它需要 claude.ai，而 CLI 在 Amazon Bedrock、Google Cloud 的 Agent Platform、Microsoft Foundry 或 Claude Platform on AWS 上，或通過 [Claude 應用程式閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway#availability-and-limitations)時不會聯絡它。命令在那裡不可用。此命令會上傳到獨立的 claude.ai/design 網站，該網站將於 2026 年 12 月 14 日前關閉；請參閱[從獨立 Claude Design 遷移至 Claude](https://support.claude.com/en/articles/17440474-migrate-from-standalone-claude-design-to-claude) |
| `/desktop` | 在 Claude Code Desktop 應用程式中繼續目前工作階段。需要 macOS 或 x64 Windows 以及 Claude 訂閱。別名：`/app` |
| `/diff` | 檢查工作樹中的變更，包括 Claude 到目前為止所做的編輯。請參閱[使用 /diff 檢查變更](https://code.claude.com/docs/zh-TW/interactive-mode.md#review-changes-with-%2Fdiff) |
| `/doctor [prompt-audit [path]]` | **[Skill](https://code.claude.com/docs/zh-TW/skills.md#bundled-skills)。** 運行設定檢查，診斷安裝、設定、擴充功能和 `CLAUDE.md` 問題，並提出修復建議，Claude 會在您確認後應用這些修復。有關檢查涵蓋的內容，或改用 `prompt-audit` 審計您的指示，請參閱[使用 `/doctor` 檢查您的設定](https://code.claude.com/docs/zh-TW/skills#check-your-setup-with-/doctor)。`prompt-audit` 子命令需要 Claude Code v2.1.283 或更新版本。別名：`/checkup` |
| `/effort [level\|auto\|status\|ultracode [on\|off]]` | 設定 [effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)：`low` 到 `xhigh`、`max` 或 `auto`；`status` 列印它。`ultracode` 或 `ultracode on` 為工作階段打開 [ultracode](https://code.claude.com/docs/zh-TW/workflows.md#let-claude-decide-with-ultracode)，`ultracode off` 關閉它；[`ultracode`](https://code.claude.com/docs/zh-TW/settings-reference#ultracode) 鍵持續存在。`max` 僅限工作階段。`on` 和 `off` 引數需要 Claude Code v2.1.284 或更新版本。如果您在 Claude 工作時運行 `/effort`，請參閱[新等級何時開始生效](https://code.claude.com/docs/zh-TW/model-config.md#when-a-new-effort-level-starts)。在 v2.1.205 或更新版本上可在 `-p` 中運作 |
| `/exit` | 退出 CLI。在附加的[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md#attach-to-a-session)中，這會分離並且工作階段保持運行。別名：`/quit` |
| `/export [filename]` | 將目前對話匯出為純文字。使用檔案名，直接寫入該檔案。沒有，打開對話框以複製到剪貼簿或保存到檔案 |
| `/fast [on\|off]` | 切換[快速模式](https://code.claude.com/docs/zh-TW/fast-mode.md)開啟或關閉。在 Claude 回應時運行它，Claude Code 會切換快速模式而不等待該回合結束，儘管運行中的回合以其原始速度完成。在 v2.1.242 之前，Claude Code 從它從 Anthropic 擷取的功能旗標決定是在回合中途運行命令還是將其排隊直到該回合完成，並始終在不[擷取功能旗標](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)的工作階段中排隊。在使用 `-p` 的非互動模式中可用性受限；請參閱[切換快速模式](https://code.claude.com/docs/zh-TW/fast-mode.md#toggle-fast-mode) |
| `/feedback [report]` | 發送有關 Claude Code 的產品回饋。打開與 [`/bug`](#all-commands) 相同的對話框，具有相同的同意步驟、發送規則和回合中途行為。在具有 [Claude 草擬回饋](https://code.claude.com/docs/zh-TW/tools-reference.md#sendfeedback-tool-behavior)的工作階段中，不帶引數的 `/feedback` 改為打開草稿佇列，您可以在其中檢查、編輯、發送或丟棄 Claude 排隊的草稿；佇列包括在對話框中編寫新報告的選項。使用引數時，以及對於 `/bug` 始終，對話框直接打開 |
| `/fewer-permission-prompts` | **[Skill](https://code.claude.com/docs/zh-TW/skills.md#bundled-skills)。** 掃描您的逐字稿以查找常見的唯讀 Bash 和 MCP 工具呼叫，然後將優先允許清單添加到專案 `.claude/settings.json` 以減少權限提示 |
| `/focus` | 切換焦點檢視，僅顯示您的最後提示詞、帶有編輯差異統計的單行工具呼叫摘要和最終回應。工具呼叫摘要也計算在該回合中啟動的 subagent 數量並將完成的背景任務通知摺疊為單一計數。選擇在工作階段間持續存在；在設定中設定 [`viewMode`](https://code.claude.com/docs/zh-TW/settings-reference#viewmode) 以覆寫它。僅在[全螢幕渲染](https://code.claude.com/docs/zh-TW/fullscreen.md)中可用。從 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 用戶端，運行 `/focus [on\|off]` 以僅為目前工作階段打開或關閉焦點檢視，而不變更您保存的選擇；這需要 Claude Code v2.1.281 或更新版本。[VS Code 擴充功能](https://code.claude.com/docs/zh-TW/vs-code.md#use-the-prompt-box)提供其自己的焦點檢視作為命令選單切換，存儲為擴充功能設定，獨立於 `viewMode` |
| `/fork [prompt]` | [將目前對話複製](https://code.claude.com/docs/zh-TW/agent-view.md#copy-the-session-with-%2Ffork)到新的背景工作階段並繼續在此工作。傳遞提示詞，副本立即開始處理它；沒有它會在 agent view 中等待其第一個提示詞。除非副本[就地編輯](https://code.claude.com/docs/zh-TW/agent-view.md#how-file-edits-are-isolated)，Claude Code 會指示它在進行程式碼變更前建立自己的 worktree；隔離指示需要 Claude Code v2.1.221 或更新版本。要將側面任務交給 subagent，其結果返回到此對話，請使用 `/subtask`；要自己切換到副本，請使用 `/branch`。當 [agent view 關閉](https://code.claude.com/docs/zh-TW/agent-view.md#turn-off-agent-view)時，`/fork` 改為啟動[分叉 subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#fork-the-current-conversation) |
| `/goal [condition\|clear]` | 設定[目標](https://code.claude.com/docs/zh-TW/goal.md)：Claude 跨回合繼續工作直到條件滿足或目標[因另一個原因清除](https://code.claude.com/docs/zh-TW/goal.md#how-evaluation-works)。沒有引數時，顯示目前或最近達成的目標。`clear`、`stop`、`off`、`reset`、`none` 或 `cancel` 會提前移除活動目標 |
| `/heapdump` | 寫入 JavaScript 堆快照和記憶體細目到 `~/Desktop`，或在沒有 Desktop 資料夾的 Linux 上寫入您的家目錄，以診斷高記憶體使用情況。報告記憶體問題時僅附加 `-diagnostics.json` 檔案；`.heapsnapshot` 包含您的完整對話和憑證，因此不要共享它。[從命令選單隱藏](#how-the-command-menu-matches-what-you-type)；完整輸入它。請參閱[如何處理輸出](https://code.claude.com/docs/zh-TW/troubleshooting.md#high-cpu-or-memory-usage) |
| `/help` | 顯示幫助和可用命令 |
| `/hooks` | 檢視 [hook](https://code.claude.com/docs/zh-TW/hooks.md#the-%2Fhooks-menu) 設定 |
| `/ide` | 管理 IDE 整合並顯示狀態 |
| `/import [codex\|gemini\|cursor] [--dry-run] [--yes]` | 將您機器上的 OpenAI Codex、Google Gemini CLI 或 Cursor 的設定帶入 Claude Code，包括指示檔案、MCP 伺服器、命令、subagent 和 skill。在使用 `-p` 的[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)中，`/import` 列出它找到的內容並給您確認匯入的命令。添加 `--dry-run` 以預覽而不寫入任何內容，或 `--yes` 以跳過互動式選擇器。在 Amazon Bedrock、Google Cloud 的 Agent Platform、Microsoft Foundry 或 Claude Platform on AWS 上，或通過 [Claude 應用程式閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway#availability-and-limitations)時不可用。當您關閉[功能旗標擷取](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)時也不可用。從 Cursor 匯入需要 v2.1.265 或更新版本 |
| `/init` | 使用 `CLAUDE.md` 指南初始化專案。設定 `CLAUDE_CODE_NEW_INIT=1` 以獲得互動式流程，也會逐步解說 skill、hook 和個人記憶檔案。如果 `/init` 找到 OpenAI Codex 或 Google Gemini CLI 設定，它會提供使用 `/import` 進行轉移 |
| `/insights` | 生成 HTML 報告，分析您在此機器上的最近工作階段：您在哪些專案中工作、如何使用 Claude Code、事情出錯的地方以及要嘗試的功能。在[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)中不可用。有關報告位置、保留和成本，請參閱[分析您的使用模式](https://code.claude.com/docs/zh-TW/costs.md#analyze-your-usage-patterns) |
| `/install-github-app` | 為儲存庫安裝 Claude GitHub App，可選步驟設定 [GitHub Actions](https://code.claude.com/docs/zh-TW/github-actions.md) 工作流程和機密。逐步解說您選擇儲存庫和設定整合。僅適用於 github.com 儲存庫。當您的儲存庫的 git 遠端在 gitlab.com 或 bitbucket.org 上時，命令會列印通知並退出而不是啟動設定。要從 GitLab 管道運行 Claude Code，請參閱 [GitLab CI/CD](https://code.claude.com/docs/zh-TW/gitlab-ci-cd.md) |
| `/install-slack-app` | 安裝 Claude Slack 應用程式。打開瀏覽器以完成 OAuth 流程 |
| `/keybindings` | 打開您的[鍵盤快捷鍵](https://code.claude.com/docs/zh-TW/keybindings.md)檔案 |
| `/list-agents` | 列出 Claude 可以傳送訊息的 subagent、[agent team](https://code.claude.com/docs/zh-TW/agent-teams.md) 隊員和其他 Claude Code 工作階段，以及每個要使用的名稱。請參閱[跨工作階段訊息](https://code.claude.com/docs/zh-TW/cross-session-messaging.md)。也可用作 `/peers`。需要 Claude Code v2.1.224 或更新版本；較早版本報告 `Unknown command: /list-agents`。隊員行和顯示此工作階段自己名稱的第一行需要 v2.1.239 或更新版本。僅在[啟用跨工作階段訊息](https://code.claude.com/docs/zh-TW/cross-session-messaging.md#availability)的工作階段中可用 |
| `/login` | 登入您的 Anthropic 帳戶 |
| `/logout` | 登出您的 Anthropic 帳戶 |
| `/loop [interval] [prompt]` | **[Skill](https://code.claude.com/docs/zh-TW/skills.md#bundled-skills)。** 在工作階段保持打開時重複運行提示詞。省略間隔，Claude [自行調整迭代之間的步調](https://code.claude.com/docs/zh-TW/scheduled-tasks.md#let-claude-choose-the-interval)。省略提示詞，Claude 運行[內建維護提示詞](https://code.claude.com/docs/zh-TW/scheduled-tasks.md#run-the-built-in-maintenance-prompt)或您的 [`loop.md`](https://code.claude.com/docs/zh-TW/scheduled-tasks#customize-the-default-prompt-with-loop-md)。範例：`/loop 5m check if the deploy finished`。請參閱[按排程運行提示詞](https://code.claude.com/docs/zh-TW/scheduled-tasks.md)。別名：`/proactive` |
| `/mcp [reconnect (<server>\|all)\|enable\|disable [<server>\|all]]` | 管理 MCP 伺服器連線和 OAuth 身分驗證。運行時不帶引數以打開互動式清單，或傳遞 `reconnect`、`enable` 或 `disable` 與伺服器名稱或 `all`，以在不打開清單的情況下變更連線狀態。`reconnect all` 會[重試每個失敗或需要身分驗證的伺服器](https://code.claude.com/docs/zh-TW/mcp.md#retry-failed-servers-yourself)。在非互動模式 (`-p`) 中，不帶引數運行它會列印伺服器狀態的文字摘要而不是打開清單 |
| `/memory` | 編輯 `CLAUDE.md` 檔案、啟用或停用[自動記憶](https://code.claude.com/docs/zh-TW/memory.md#auto-memory)以及檢視自動記憶項目 |
| `/mobile` | 顯示 QR 碼以下載 Claude 行動應用程式。別名：`/ios`、`/android` |
| `/model [model]` | 切換 AI 模型並將其保存為新工作階段的預設值。對於支援它的模型，使用左/右箭頭以[調整 effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)。沒有引數時，打開選擇器；在行上按 `s` 以僅為目前工作階段切換。請參閱[新模型何時開始生效](https://code.claude.com/docs/zh-TW/interactive-mode.md#when-claude-code-sends-what-you-queued)。在 v2.1.242 之前，它可能會等待。使用 `-p` 時，傳遞模型引數，該引數不會保存為您的預設值；需要 v2.1.205 或更新版本 |
| `/output-style [style]` | 列出[輸出風格](https://code.claude.com/docs/zh-TW/output-styles.md)或切換到一個，例如 `/output-style concise`。請參閱[變更您的輸出風格](https://code.claude.com/docs/zh-TW/output-styles.md#change-your-output-style)。需要 Claude Code v2.1.269 或更新版本 |
| `/passes` | 與朋友分享免費一週的 Claude Code。僅在您的帳戶符合條件時可見 |
| `/permissions` | 管理工具權限的允許、詢問和拒絕規則。打開互動式對話框，您可以按範圍檢視規則、添加或移除規則、管理工作目錄以及檢查[最近的自動模式拒絕](https://code.claude.com/docs/zh-TW/auto-mode-config.md#review-denials)。您也可以從對話框的 **Auto mode** 標籤檢視和編輯[自動模式分類器規則](https://code.claude.com/docs/zh-TW/auto-mode-config.md#edit-rules-from-permissions)。別名：`/allowed-tools` |
| `/plan [description]` | 直接從提示詞進入 plan mode。傳遞可選描述以進入 plan mode 並立即開始該任務，例如 `/plan fix the auth bug` |
| `/plugin [subcommand]` | 管理 Claude Code [外掛](https://code.claude.com/docs/zh-TW/plugins/overview.md)。運行時不帶引數以打開外掛選單，或傳遞子命令（例如 `list`、`install`、`enable` 或 `disable`）以直接執行。Claude Code 可以在安裝期間啟動外掛；[安裝摘要](https://code.claude.com/docs/zh-TW/plugins/install.md#install-a-plugin)會告訴您它是否已啟動，或是否需要運行 `/reload-plugins` |
| `/plugin-authoring` | 載入 Claude 用來[編寫 mod](https://code.claude.com/docs/zh-TW/plugins/mods/create.md#ask-claude-for-a-mod) 的參考資料。當您要求 mod 時，Claude 可以自行載入它。這是來自[內建外掛](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md#mods-built-into-claude-code)的 skill，您可以在 `/plugin` 中關閉它。需要 Claude Code v2.1.287 或更新版本 |
| `/powerup` | 通過帶有動畫演示的快速互動式課程發現 Claude Code 功能 |
| `/pr-comments [PR]` | 在 v2.1.91 中移除。改為直接要求 Claude 檢視 pull request 評論。在較早版本上，擷取並顯示來自 GitHub pull request 的評論；自動檢測目前分支的 PR，或傳遞 PR URL 或編號。需要 `gh` CLI |
| `/privacy-settings` | 檢視和更新您的隱私設定。僅適用於 Pro、Max 和 Ultra 方案訂閱者 |
| `/radio` | 在瀏覽器中打開 Claude FM lo-fi 廣播。當沒有瀏覽器可用時列印串流 URL |
| `/rate-limit-options` | 顯示在 claude.ai 用量上限阻止請求時保持工作的方式：等待並[在限制重置時自動繼續](https://code.claude.com/docs/zh-TW/interactive-mode.md#wait-for-a-usage-limit-to-reset)、添加[用量點數](https://code.claude.com/docs/zh-TW/costs.md#add-usage-credits-to-your-subscription)或升級您的方案。Claude Code 也可以在您在自己的終端機達到限制時自行打開此選單。請參閱[關閉自動繼續](https://code.claude.com/docs/zh-TW/interactive-mode.md#turn-automatic-continue-off)。需要 claude.ai 訂閱。等待和繼續行需要 Claude Code v2.1.234 或更新版本 |
| `/recap` | 按需生成目前工作階段的單行摘要。請參閱[工作階段摘要](https://code.claude.com/docs/zh-TW/interactive-mode.md#session-recap)以了解您離開後出現的自動摘要 |
| `/release-notes` | 在互動式版本選擇器中檢視變更日誌。選擇特定版本以查看其發佈說明，或選擇顯示所有版本。說明在您的逐字稿中出現而不進入 Claude 看到的對話 |
| `/reload-plugins [--force]` | 重新載入所有活動[外掛](https://code.claude.com/docs/zh-TW/plugins/overview.md)以應用待處理變更而不重新啟動。報告每個重新載入元件的計數並標記任何載入錯誤。當重新載入會變更載入的 MCP 工具並使提示快取失效時，命令會警告並跳過，除非您傳遞 `--force`。也可在非互動模式 (`-p`)、Agent SDK 和桌面應用程式中使用，其中它僅在直接輸入到工作階段的輸入上運行且不應用外掛 MCP 伺服器變更；需要 Claude Code v2.1.260 或更新版本。請參閱[在不重新啟動的情況下應用外掛變更](https://code.claude.com/docs/zh-TW/plugins/cli-reference.md#reload-plugins) |
| `/reload-skills` | 重新掃描 [skill](https://code.claude.com/docs/zh-TW/skills.md) 和命令目錄，以便在工作階段期間在磁碟上添加或變更的 skill 在不重新啟動的情況下變為可用。報告有多少 skill 可用以及添加或移除了多少 |
| `/remote-control` | 使此工作階段可從 claude.ai 進行 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md)。在登出時運行它會列印 Remote Control 需要 claude.ai 訂閱並告訴您如何登入。別名：`/rc` |
| `/remote-env` | 為您從 CLI 啟動的雲端工作階段選擇預設[雲端環境](https://code.claude.com/docs/zh-TW/cloud-environments.md#select-an-environment-from-the-cli) |
| `/rename [name]` | 重新命名目前工作階段並在提示詞欄上顯示名稱。沒有名稱時，從對話歷史記錄自動生成一個。也可在非互動模式 (`-p`) 中使用。從每個重新命名的使用介面，包括 claude.ai 和桌面應用程式，Claude Code 會用空格替換新名稱中的控制和不可見字元，並將名稱上限設為 200 個字元。如果移除不可見字元後名稱為空，Claude Code 會拒絕它並顯示 `That name is empty once invisible characters are removed. Usage: /rename <name>`。字元替換和長度上限需要 Claude Code v2.1.221 或更新版本 |
| `/restart` | 重新啟動 Claude Code 並恢復此工作階段，以應用已安裝的更新。當更新安裝後頁尾提供此選項時運行它。需要 Pro、Max 或 Ultra 方案，以及在 macOS 或 Linux（非 WSL）上的原生安裝。需要 Claude Code v2.1.288 或更新版本。別名：`/update` |
| `/resume [session]` | 按 ID 或名稱恢復對話，或打開工作階段選擇器。[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)在選擇器中以 `bg` 標記出現。恢復仍在運行的工作階段時，無論是從選擇器或按 ID 或名稱，都會[打開該工作階段](https://code.claude.com/docs/zh-TW/sessions.md#resume-a-running-background-session)：您目前的對話會移到背景，此終端機會附加到運行中的工作階段。在空提示詞上按 `←` 可返回 agent view，其中也會列出您離開的對話。在 v2.1.285 之前，Claude Code 會拒絕，並告訴您使用 `claude attach` 打開該工作階段或先停止它。別名：`/continue` |
| `/review [low\|medium\|high\|xhigh\|max\|ultra] [--fix] [--comment] [--max-findings n\|all\|default] [pr#\|branch\|path]` | [`/code-review`](https://code.claude.com/docs/zh-TW/code-review-local) 的別名：檢查目前差異或您傳遞的 PR 編號、分支或路徑，例如 `/review 1234`，並採用相同的 effort 等級和旗標。沒有給定等級時，檢查重複使用您最後輸入的 `low` 到 `max` 等級；有關確切規則，請參閱[使用 `/code-review` 在本地檢查](https://code.claude.com/docs/zh-TW/code-review-local)。對於深度雲端檢查，使用 [`/code-review ultra`](https://code.claude.com/docs/zh-TW/ultrareview)。在 v2.1.223 之前，`/review` 是一個單獨的命令，按編號對 GitHub pull request 進行單次通過、唯讀檢查，在運行時不帶引數時列出打開的 PR 以選擇；從 v2.1.186 到 v2.1.201，它運行與 `/code-review medium` 相同的多 agent 引擎 |
| `/rewind` | 倒帶對話和/或程式碼到上一個點，或從選定的訊息進行摘要。請參閱[檢查點功能](https://code.claude.com/docs/zh-TW/checkpointing.md)。別名：`/checkpoint`、`/undo` |
| `/run` | **[Skill](https://code.claude.com/docs/zh-TW/skills.md#bundled-skills)。** 啟動並驅動您的專案應用程式以查看變更實際運作，而不僅僅是通過測試。請參閱[運行和驗證您的應用程式](https://code.claude.com/docs/zh-TW/skills.md#run-and-verify-your-app) |
| `/run-skill-generator` | **[Skill](https://code.claude.com/docs/zh-TW/skills.md#bundled-skills)。** 通過編寫每個專案的 [skill](https://code.claude.com/docs/zh-TW/skills.md#run-and-verify-your-app)，教 `/run` 和 `/verify` 如何從乾淨環境建置、啟動和驅動您的專案應用程式 |
| `/sandbox` | 切換[沙箱模式](https://code.claude.com/docs/zh-TW/sandboxing.md)。僅在支援的平台上可用 |
| `/schedule [description]` | 建立、更新、列出或運行[雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md)（以前稱為 routine）。Claude 以對話方式逐步解說設定。您也可以詢問[排程任務的最近運行](https://code.claude.com/docs/zh-TW/routines.md#manage-scheduled-tasks-from-the-cli)。別名：`/routines` |
| `/scroll-speed` | 以互動方式調整滑鼠滾輪[捲動速度](https://code.claude.com/docs/zh-TW/fullscreen.md#mouse-wheel-scrolling)。僅在[全螢幕渲染](https://code.claude.com/docs/zh-TW/fullscreen.md)中可用，在 JetBrains IDE 終端機中不可用 |
| `/security-review` | 分析目前分支上的變更以查找安全漏洞。檢查您的分支與 origin 預設分支之間的差異，識別注入、身分驗證問題和資料洩露等風險。需要 `origin` 遠端；如果檢查失敗並出現 `ambiguous argument` 錯誤，請參閱[錯誤參考](https://code.claude.com/docs/zh-TW/errors.md#security-review-fails-without-origin-head) |
| `/setup-bedrock` | 通過互動式精靈設定 [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md) 身分驗證、區域和模型釘選。[從命令選單隱藏](#how-the-command-menu-matches-what-you-type)直到設定 `CLAUDE_CODE_USE_BEDROCK=1`；完整輸入它。首次 Amazon Bedrock 使用者也可以從登入螢幕存取此精靈 |
| `/setup-vertex` | 通過互動式精靈設定 [Google Cloud 的 Agent Platform](https://code.claude.com/docs/zh-TW/google-vertex-ai.md) 身分驗證、專案、區域和模型釘選。[從命令選單隱藏](#how-the-command-menu-matches-what-you-type)直到設定 `CLAUDE_CODE_USE_VERTEX=1`；完整輸入它。首次 Google Cloud 的 Agent Platform 使用者也可以從登入螢幕存取此精靈 |
| `/simplify [target]` | **[Skill](https://code.claude.com/docs/zh-TW/skills.md#bundled-skills)。** 檢查變更的程式碼以查找清理機會並應用修復。四個檢查 [agent](https://code.claude.com/docs/zh-TW/sub-agents.md) 並行運行，涵蓋現有幫助程式的重複使用、簡化、效率以及變更是否處於正確的抽象層級。檢查不尋找正確性錯誤。使用 `/code-review` 查找錯誤。傳遞路徑或 PR 參考以檢查特定目標 |
| `/skill-doctor` | 顯示您的每個 [skill](https://code.claude.com/docs/zh-TW/skills.md) 在上下文中的成本以及它被使用的頻率，以便您可以[找到要關閉的 skill](https://code.claude.com/docs/zh-TW/skills.md#find-unused-skills)。需要 Claude Code v2.1.252 或更新版本和[功能旗標擷取](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching) |
| `/skills` | 列出可用的 [skill](https://code.claude.com/docs/zh-TW/skills.md)。輸入以按名稱、描述或來源篩選清單。按 `t` 按 token 計數排序，`Space` 或 `Enter` 以[循環切換 skill 對 Claude 和 `/` 選單的可見性](https://code.claude.com/docs/zh-TW/skills#override-skill-visibility-from-settings)，以及 `Esc` 以保存並關閉。您無法循環切換外掛 skill、其 frontmatter 設定 `disable-model-invocation: true` 的 skill，或在受管設定或 `--settings` 旗標中具有 `skillOverrides` 項目的 skill |
| `/slides [brief]` | **[Skill](https://code.claude.com/docs/zh-TW/skills.md#bundled-skills)。** 製作新簡報作為 Claude Slides [artifact](https://code.claude.com/docs/zh-TW/artifacts.md#make-a-slide-deck)，並根據您的簡述填充內容，例如 `/slides a quarterly review of the platform team`。需要 Claude Code v2.1.265 或更新版本、[artifact 可用](https://code.claude.com/docs/zh-TW/artifacts.md#availability)的工作階段，以及 [Slides 範本可用](https://code.claude.com/docs/zh-TW/artifacts.md#start-from-a-slides-design-or-docs-template)的帳戶；否則命令不會出現。在 Anthropic API 上可用。在 Amazon Bedrock、Google Cloud 的 Agent Platform、Microsoft Foundry 和 Claude Platform on AWS 上，artifact 不可用，因此命令在那裡不可用 |
| `/stats` | `/usage` 的別名。在 Stats 標籤上打開 |
| `/status` | 在 Status 標籤上打開設定介面，顯示版本、模型、帳戶和連線。`Session kind` 行在[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)中顯示 `background job · attached` 或 `background job · unattended`（取決於是否附加終端機），在任何其他工作階段中顯示 `interactive`。在 v2.1.221 之前，`/status` 不顯示此行。在 Claude 回應時也可運作 |
| `/statusline` | 設定 Claude Code 的[狀態列](https://code.claude.com/docs/zh-TW/statusline.md)。描述您想要的內容，或運行時不帶引數以從您的 shell 提示字元自動設定 |
| `/stickers` | 訂購 Claude Code 貼紙 |
| `/stop` | 停止您所附加的[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)，或您以[預覽回覆](https://code.claude.com/docs/zh-TW/agent-view.md#peek-and-reply)方式傳送此命令的目標工作階段；逐字稿和任何 worktree 都會保留。要分離而不停止，請使用 `/exit` 或按 `←` |
| `/subtask <task>` | 生成[分叉 subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#fork-the-current-conversation)：一個繼承完整對話並在您繼續工作時處理任務的背景 subagent。其結果在完成時返回到此對話。要將對話複製到單獨的背景工作階段，請改用 `/fork`。當 [agent view 關閉](https://code.claude.com/docs/zh-TW/agent-view.md#turn-off-agent-view)時，`/subtask` 不可用，`/fork` 改為生成分叉 subagent |
| `/tasks` | 檢視和管理目前工作階段中的背景工作，包括已完成的 subagent。也可用作 `/bashes` |
| `/team-onboarding` | 從您的 Claude Code 使用歷史記錄生成團隊入職指南。Claude 分析您過去 30 天的工作階段、命令和 MCP 伺服器使用情況，並生成隊友可以貼上作為第一條訊息以快速設定的 markdown 指南。對於 Team 和 Enterprise 方案上的 claude.ai 訂閱者，也會返回隊友可以直接在 Claude Code 中打開的共享連結 |
| `/teleport` | 將[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#from-cloud-to-terminal)拉入此終端機。打開選擇器，然後擷取分支和對話。也可用作 `/tp`。需要 claude.ai 訂閱 |
| `/terminal-setup` | [在 VS Code、Cursor、Devin Desktop、Alacritty 或 Zed 中安裝 Shift+Enter 快捷鍵以進行新行](https://code.claude.com/docs/zh-TW/terminal-config.md#enter-multiline-prompts)。在 Apple Terminal 中，[改為啟用 Option+Enter 以進行新行並關閉可聽見的鈴聲](https://code.claude.com/docs/zh-TW/terminal-config.md#enable-option-key-shortcuts-on-macos)。在 iTerm2 中，[打開剪貼簿存取以便 `/copy` 運作](https://code.claude.com/docs/zh-TW/terminal-config#enable-option-key-shortcuts-on-macos) |
| `/theme` | 變更顏色主題。包括與您的終端機淺色或深色背景相符的 `auto` 選項、淺色和深色變體、色盲無障礙 (daltonized) 主題、使用您的終端機調色板的 ANSI 主題以及來自 `~/.claude/themes/` 或外掛的任何[自訂主題](https://code.claude.com/docs/zh-TW/terminal-config.md#create-a-custom-theme)。選擇 **New custom theme…** 以建立一個 |
| `/tui [default\|fullscreen]` | 設定終端機 UI 渲染器並在保留您的對話的情況下重新啟動到它。`fullscreen` 啟用[無閃爍 alt-screen 渲染器](https://code.claude.com/docs/zh-TW/fullscreen.md)。沒有引數時，列印活動渲染器 |
| `/ultraplan <prompt>` | 已移除。改用 [plan mode](https://code.claude.com/docs/zh-TW/permission-modes.md#analyze-before-you-edit-with-plan-mode)。以前將計畫任務發送到[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)以在您的瀏覽器中檢查 |
| `/ultrareview [PR or branch]` | 在雲端沙箱中使用 [ultrareview](https://code.claude.com/docs/zh-TW/ultrareview.md) 運行深度、多 agent 程式碼審查。傳遞 PR 參考以檢查該 pull request，或傳遞基礎分支或提交以變更比較基礎。首選調用是 `/code-review ultra`，`/ultrareview` 是別名。在 Pro、Max 和 Ultra 上包括 3 次免費運行，然後需要[用量點數](https://support.claude.com/en/articles/12429409-extra-usage-for-paid-claude-plans) |
| `/update-config [request]` | **[Skill](https://code.claude.com/docs/zh-TW/skills.md#bundled-skills)。** 描述設定變更，例如允許命令、設定環境變數或添加 [hook](https://code.claude.com/docs/zh-TW/hooks.md)，Claude 編輯匹配的 [`settings.json`](https://code.claude.com/docs/zh-TW/settings) 檔案。對於主題和模型等選項，改用 `/config` |
| `/upgrade` | 在瀏覽器中打開升級頁面以切換到更高的方案層級。當瀏覽器無法打開時，命令會顯示登入提示而不列印 URL |
| `/usage` | 顯示工作階段成本、方案用量上限和活動統計。在 Pro、Max、Ultra、Team 或 Enterprise 方案上，包括[計入您的方案上限的內容細目](https://code.claude.com/docs/zh-TW/costs.md#plan-usage-breakdown)。`/cost` 和 `/stats` 是別名 |
| `/usage-credits` | 在達到上限時設定用量點數，或向您的管理員請求。在瀏覽器中打開您的[用量點數計費設定](https://code.claude.com/docs/zh-TW/costs.md#add-usage-credits-to-your-subscription)，但沒有計費存取權的 Team 和 Enterprise 成員則改為從 CLI 向其管理員發送用量點數請求，並先在對話框中確認該請求會通知其管理員。當沒有瀏覽器可以打開計費頁面時，例如通過 SSH，命令會改為列印要前往的 URL；這需要 Claude Code v2.1.205 或更新版本，較早版本在這種情況下不顯示任何內容。以前為 `/extra-usage` |
| `/verify` | **[Skill](https://code.claude.com/docs/zh-TW/skills.md#bundled-skills)。** 通過建置您的專案應用程式、運行它並觀察結果來確認程式碼變更執行其應該執行的操作，而不是依賴測試或類型檢查。請參閱[運行和驗證您的應用程式](https://code.claude.com/docs/zh-TW/skills.md#run-and-verify-your-app) |
| `/vim` | 在 v2.1.92 中移除。要在 Vim 和 Normal 編輯模式之間切換，請使用 `/config` → Editor mode |
| `/voice [hold\|tap\|off]` | 切換[語音聽寫](https://code.claude.com/docs/zh-TW/voice-dictation.md)或在特定模式下啟用它。需要 Claude.ai 帳戶 |
| `/web-setup` | 使用您的本地 `gh` CLI 憑證連接您的 GitHub 帳戶以進行[雲端工作階段](https://code.claude.com/docs/zh-TW/web-quickstart.md#connect-from-your-terminal) |
| `/workflow-authoring` | **[Skill](https://code.claude.com/docs/zh-TW/skills.md#bundled-skills)。** 載入編寫[動態工作流程](https://code.claude.com/docs/zh-TW/workflows.md)指令碼的參考：指令碼 API、恢復行為、品質模式和完整範例。Claude 通常在編寫指令碼前自行載入它；在[手動編輯已保存的指令碼](https://code.claude.com/docs/zh-TW/workflows.md#edit-a-saved-script)前自己運行它。在啟用動態工作流程時可用，需要 Claude Code v2.1.248 或更新版本 |
| `/workflows` | 打開[工作流程](https://code.claude.com/docs/zh-TW/workflows.md#watch-the-run)進度檢視以監視、暫停、恢復或保存運行中和已完成的工作流程 |

## 命令選單如何匹配您輸入的內容

Claude Code 會在您輸入時篩選 `/` 選單。下面的每個項目涵蓋您在篩選時可能注意到的一件事：

* **醒目提示**：Claude Code 只有在 `/` 後面的字母與命令的名稱或別名相符時，才會醒目提示最上面的建議，可以從名稱的開頭或名稱內的某個字開始相符，忽略 `:`、`_` 和 `-` 分隔符。輸入 `/adddir` 會醒目提示 `/add-dir`，輸入 `/new` 會透過其別名醒目提示 `/clear`。按 `Enter` 鍵執行醒目提示的建議。這些醒目提示規則需要 Claude Code v2.1.236 或更新版本。
* **打字錯誤後**：Claude Code 不會醒目提示任何內容。接近的相符項會保留在列表中，您可以使用 `Tab` 或方向鍵選擇其中一個，但 `Enter` 會按照您輸入的方式提交文字，並報告[未知命令](https://code.claude.com/docs/zh-TW/errors.md#unknown-command)。
* **您無法使用的命令**：Claude Code 會將其排除在選單之外。當沒有任何內容相符時，Claude Code 會顯示 `No commands match "/name"`。大多數無法使用的命令在您提交時會傳回[未知命令](https://code.claude.com/docs/zh-TW/errors.md#unknown-command)；少數幾個，例如[在 Console API 金鑰上的 `/schedule`](https://code.claude.com/docs/zh-TW/routines#schedule-returns-unknown-command)，會改為回答自己的可用性訊息。當您的組織政策停用某些命令時，這些命令也會回答自己的訊息。
* **隱藏命令**：Claude Code 刻意將一些可用命令（例如 `/heapdump`）保留在選單之外。部分名稱永遠不會將隱藏命令帶入選單：如果部分相符項與任何可見項目都不相符，Claude Code 會顯示相同的不相符訊息。Claude Code 只有在您輸入完整名稱後才會列出該命令，提交完整名稱會執行它。

## MCP prompts

MCP 伺服器可以公開顯示為命令的提示。詳見 [MCP prompts](https://code.claude.com/docs/zh-TW/mcp.md#use-mcp-prompts-as-commands) 以了解詳情。

## 另請參閱

* [Skills](https://code.claude.com/docs/zh-TW/skills.md)：建立您自己的命令
* [Interactive mode](https://code.claude.com/docs/zh-TW/interactive-mode.md)：鍵盤快捷鍵、Vim 模式和命令歷史記錄
* [CLI reference](https://code.claude.com/docs/zh-TW/cli-reference.md)：啟動時間旗標

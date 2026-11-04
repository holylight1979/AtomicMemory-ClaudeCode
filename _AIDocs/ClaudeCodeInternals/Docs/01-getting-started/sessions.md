<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/sessions | lastmod: 2026-10-30 | section: Getting started / Use Claude Code -->
> 來源：https://code.claude.com/docs/zh-TW/sessions（官方 zh-TW，lastmod 2026-10-30）｜分類：Getting started › Use Claude Code｜EN 摘要：Name, resume, branch, and switch between Claude Code conversations. Covers `--continue`, `--resume`, `--from-pr`, the `/resume` picker, session naming, exporting transcripts, and where transcripts are stored.

# 管理 sessions

> 命名、恢復、分支和在 Claude Code 對話之間切換。涵蓋 `--continue`、`--resume`、`--from-pr`、`/resume` 選擇器、session 命名、匯出文字記錄，以及文字記錄的儲存位置。

[工作階段](https://code.claude.com/docs/zh-TW/glossary.md#session)是與專案目錄相關聯的已儲存對話。Claude Code 在您工作時將其儲存在本地，因此您可以從中斷的地方繼續、分支以嘗試不同的方法，或在任務之間切換。

[桌面應用程式](https://code.claude.com/docs/zh-TW/desktop.md#work-in-parallel-with-sessions)、[claude.ai/code](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md) 和 [VS Code 擴充功能](https://code.claude.com/docs/zh-TW/vs-code.md#resume-past-conversations)各自維護自己的 session 歷史記錄，桌面應用程式也可以[恢復 CLI session](https://code.claude.com/docs/zh-TW/desktop.md#coming-from-the-cli)。本頁涵蓋 CLI。

## 恢復工作階段

工作階段在您工作時會持續儲存到[本機逐字稿檔案](#export-and-locate-session-data)，因此您可以在退出或執行 `/clear` 後返回其中一個工作階段。請使用這些進入點：

| 命令 | 功能 |
| :- | :- |
| `claude --continue` | 重新開啟目前目錄中最近的工作階段 |
| `claude --resume` | 開啟[工作階段選擇器](#use-the-session-picker) |
| `claude --resume <name>` | 直接恢復已命名的工作階段 |
| `claude --resume <transcript-path>` | 恢復儲存在該絕對路徑之 `.jsonl` [逐字稿檔案](#where-transcripts-are-stored)中的工作階段 |
| `claude --from-pr <number>` | 開啟工作階段選擇器，並篩選為連結到該 pull request 的工作階段 |
| `/resume` | 從進行中的工作階段內切換到不同的工作階段 |

### 恢復執行中的背景工作階段

當您使用 `claude --resume` 或 `/resume` 恢復的對話屬於仍在執行的[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)時，Claude Code 會開啟該執行中的工作階段本身。在命令列上使用 `--bg` 時，恢復則改為[背景分派](https://code.claude.com/docs/zh-TW/agent-view.md#from-your-shell)。在 v2.1.285 之前，Claude Code 會拒絕並告訴您使用 `claude attach <id>` 開啟該工作階段，或先使用 `claude stop <id>` 停止它。

* **從您的 shell**：`claude --resume <session>` 會在同一個終端機中對該工作階段執行 [`claude attach`](https://code.claude.com/docs/zh-TW/agent-view#attach-to-a-session)，而不是自行載入逐字稿。您在命令列上傳遞的提示詞，例如 `claude --resume <session> "check the tests too"`，會先作為該工作階段的下一個回合送出，Claude Code 會在附加之前列印 `Sent your prompt to the background session (<id>); opening it…`。在終端機中輸入的 `claude -p --resume <session> "prompt"` 也會執行相同操作，因此 `-p` 不會讓該次執行保持非互動式。

  當命令列具有以下任何一項時，Claude Code 不會開啟該工作階段：

  * 經由管道傳送或重新導向的輸入或輸出
  * 設定工作階段的旗標，例如 `--permission-mode`、`--model` 或 `--settings`
  * 讀取輸出的旗標，例如 `--output-format json` 或 `--json-schema`
  * 限制或倒轉執行的旗標，例如 `--max-turns` 或 `--max-budget-usd`

  具有其中任何一項，或當 [agent 檢視已關閉](https://code.claude.com/docs/zh-TW/agent-view.md#turn-off-agent-view)時，Claude Code 不會傳送任何內容，並以狀態 1 退出，列印該工作階段正在背景執行，以及用來開啟它的 `claude attach <id>` 命令；若無法判定 ID，則會告訴您在 `claude agents` 中尋找它。新增 `--fork-session` 可改為恢復該對話的副本。若要在您自己的工作階段中繼續對話本身並套用您的旗標，請執行 `claude stop <id>`，然後重複該命令。

  以 `/` 或 `!` 開頭的提示詞不會被傳送，而當工作階段正在等待您回答問題時，任何提示詞也都不會被傳送。在這兩種情況下，Claude Code 都不會開啟該工作階段，訊息會包含 `Your prompt was not sent to it` 以及原因。
* **從工作階段內**：`/resume` 會將您目前的對話移到背景，並將此終端機附加到執行中的工作階段，列印 `Opening "<title>", running in the background (<id>)`。在空白提示詞上按 `←` 即可返回 agent 檢視，其中也會列出您離開的對話。當目前的對話無法移到背景時（例如因為您已附加到背景工作階段，或工作階段持久化已關閉），`/resume` 會改為列印要執行的 `claude attach` 命令。

### 恢復的工作階段會復原什麼

當 Claude Code 從逐字稿載入對話時，恢復的工作階段會復原該對話以及其中儲存的狀態：

* 對話記錄：訊息、工具呼叫和結果。如果工作階段曾被[壓縮](https://code.claude.com/docs/zh-TW/context-window.md#what-survives-compaction)，對話會在 `Conversation compacted` 列開啟。Claude 會以最後一次壓縮的摘要、該次壓縮未摘要的訊息，以及之後的每則訊息繼續。最後一次壓縮所摘要的訊息不會再次載入。
* 中斷的工具呼叫：在前一個程序結束時（例如當機時）仍在執行的工具，在您恢復時不會再次執行。
* 模型：工作階段會繼續使用其原本使用的模型，但[設定您的模型](https://code.claude.com/docs/zh-TW/model-config.md#setting-your-model)中所述的情況除外。
* Agent：使用 [`--agent`](https://code.claude.com/docs/zh-TW/sub-agents#invoke-subagents-explicitly) 或 `agent` 設定啟動的工作階段會繼續作為該 agent 運作，並保留其工具限制和模型。恢復時傳遞 `--agent` 可選擇不同的 agent；關於任一情況下的系統提示詞，請參閱[恢復對話中的系統提示詞旗標](https://code.claude.com/docs/zh-TW/cli-reference.md#system-prompt-flags-in-resumed-conversations)。Claude Code 會在兩個地方尋找該 agent：工作階段的原始目錄（前提是您已[信任該工作區](https://code.claude.com/docs/zh-TW/permissions.md#project-allow-rules-and-workspace-trust)），然後是您進行恢復的目錄，因此當您從另一個目錄恢復時，專案範圍的 agent 仍會載入。如果 Claude Code 在這兩個地方都找不到該 agent，工作階段會以預設工具恢復，並顯示[指出該 agent 名稱的警告](https://code.claude.com/docs/zh-TW/errors.md#session-agent-no-longer-available)。
* 權限模式：如果您在終端機中使用 `claude --continue`、`claude --resume <session-id>` 或 `claude --resume <name>`（當名稱符合單一工作階段時）且不帶 `-p` 恢復，Claude Code 會復原工作階段當時的權限模式，但[恢復時的權限模式](#permission-mode-on-resume)中的情況除外，該節也涵蓋工作階段選擇器、`/resume` 以及使用 `claude -p` 恢復。傳遞 `--permission-mode` 或 `--dangerously-skip-permissions` 可覆寫復原的模式。
* 進行中的目標：工作階段結束時仍在進行中的[目標](https://code.claude.com/docs/zh-TW/goal.md#resume-with-an-active-goal)會延續；其回合計數、計時器和 token 花費基準會重設。
* 工作階段範圍的排程任務：[尚未過期的任務](https://code.claude.com/docs/zh-TW/scheduled-tasks.md#limitations)會被復原。背景 Bash 和監視任務則不會。
* 背景工作：隨著前一個程序結束的[背景 subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#run-subagents-in-foreground-or-background)、背景 Bash 命令或[工作流程](https://code.claude.com/docs/zh-TW/workflows.md)，會在恢復的逐字稿中顯示為未完成的註記。Claude Code 不會因這些註記而開始一個回合；Claude 會在您的下一個提示詞時一併讀取它們。

並非原始啟動時的每個設定旗標都會被復原。如果工作階段依賴 `--mcp-config`、`--settings`、`--plugin-dir`、`--fallback-model` 或使用 `--add-dir` 新增的目錄，請在恢復時再次傳遞它們；在工作階段中途使用 `/add-dir` 新增的目錄也不會被復原，但工作階段選擇器仍會使用它們來定位工作階段。標準設定檔（例如 `settings.json` 和 `settings.local.json`）會在啟動時重新讀取，因此存放在其中的設定不需要再次傳遞。關於 `--system-prompt` 和 `--append-system-prompt`，請參閱[恢復對話中的系統提示詞旗標](https://code.claude.com/docs/zh-TW/cli-reference.md#system-prompt-flags-in-resumed-conversations)。

#### 恢復時的權限模式

Claude Code 以哪種權限模式啟動恢復的工作階段，取決於您的恢復方式。以下情況適用於 Claude Code 從逐字稿載入對話時；當您改為[開啟仍在執行的背景工作階段](#resume-a-running-background-session)時，該工作階段會保持其目前的權限模式。

* 終端機：`claude --continue`、`claude --resume <session-id>` 或 `claude --resume <name>`（當名稱符合單一工作階段時），且不帶 `-p`。Claude Code 會復原工作階段當時的權限模式，但表格中的情況除外。傳遞 `--permission-mode` 或 `--dangerously-skip-permissions` 可覆寫復原的模式。
* 非互動式：`claude -p --resume` 或 `claude -p --continue`。Claude Code 會以新的 `claude -p` 執行會採用的權限模式啟動該次執行，但以 plan mode 結束的工作階段在[下列條件](#resume-in-plan-mode-with-p)下會以 plan mode 恢復。
* VS Code：擴充功能的對話面板。表格僅涵蓋以 plan mode 結束的對話；其餘情況請參閱[恢復過去的對話](https://code.claude.com/docs/zh-TW/vs-code.md#resume-past-conversations)。
* 啟動時的工作階段選擇器：您從[工作階段選擇器](#use-the-session-picker)選擇的工作階段，無論您是單獨使用 `claude --resume`、使用 `claude --from-pr`，還是使用符合多個工作階段的名稱來開啟選擇器。Claude Code 會以從相同命令列啟動新工作階段時的權限模式啟動該工作階段，但以 plan mode 結束的工作階段會在 plan mode 中恢復。如果您傳遞 `--permission-mode`、`--dangerously-skip-permissions` 或 `--fork-session`，Claude Code 不會復原 plan mode。不會復原其他已儲存的權限模式。
* 在工作階段內使用 `/resume`，帶或不帶引數：您切換到的對話會以您目前工作階段所在的權限模式繼續，但以 plan mode 結束的對話會在 plan mode 中恢復，即使您是以 `--permission-mode` 或 `--dangerously-skip-permissions` 啟動 Claude Code。如果該對話在本次 Claude Code 執行中稍早已開啟過，例如您一開始所在的對話，或您以 `/clear` 或 `/resume` 離開的對話，它則會改為以您目前的權限模式繼續。

如果[拒絕規則](https://code.claude.com/docs/zh-TW/permissions.md#manage-permissions)移除了 [`ExitPlanMode`](https://code.claude.com/docs/zh-TW/tools-reference) 工具，Claude 就無法呈現計畫以供核准，因此 Claude Code 不會復原 plan mode。工作階段會以從相同命令列啟動新工作階段時的權限模式啟動。使用 `/resume` 時，對話會以您目前的權限模式繼續。

在非互動式和 VS Code 路徑上復原 plan mode 需要 Claude Code v2.1.246 或更新版本。每一列列出工作階段結束時的權限模式、您透過終端機、非互動式和 VS Code 中的哪一種路徑恢復它，以及 Claude Code 啟動恢復之工作階段時採用的權限模式。

| 工作階段結束時的模式 | 恢復方式 | 恢復後的權限模式 |
| :- | :- | :- |
| `bypassPermissions` | 終端機 | 新工作階段會啟動的權限模式。若要再次[略過權限](https://code.claude.com/docs/zh-TW/permission-modes.md#skip-all-checks-with-bypasspermissions-mode)，請在啟動時使用其啟動旗標之一，或在 [user、`--settings` 或受管設定](https://code.claude.com/docs/zh-TW/settings-reference#permissions-defaultmode)中使用 `permissions.defaultMode: "bypassPermissions"` 啟用它 |
| `plan` | 終端機 | plan mode。使用 `--fork-session` 時，則為新工作階段會啟動的權限模式 |
| `plan` | 終端機，當拒絕規則移除 `ExitPlanMode` 時 | 新工作階段會啟動的權限模式 |
| `auto` | 終端機 | `auto`，僅當您的帳戶仍符合[自動模式要求](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)時 |
| Manual | 終端機 | 當新工作階段會依[內建預設值](https://code.claude.com/docs/zh-TW/permission-modes.md#which-mode-a-session-starts-in)以自動模式啟動時，為 Manual。當設定檔中的 `defaultMode` [生效](https://code.claude.com/docs/zh-TW/permission-modes.md#which-mode-a-session-starts-in)時，Claude Code 則會改以該模式啟動恢復的工作階段 |
| `plan` | 非互動式，符合[下列條件](#resume-in-plan-mode-with-p)時 | plan mode |
| 任何模式 | 非互動式，任何其他情況 | 新的 `claude -p` 執行會啟動的權限模式 |
| `plan` | VS Code | plan mode，但有 [VS Code 頁面上所述的例外](https://code.claude.com/docs/zh-TW/vs-code.md#resume-past-conversations) |

##### 使用 `-p` 以 plan mode 恢復

`claude -p --resume` 或 `claude -p --continue` 執行只有在下列所有條件都成立時，才會以 plan mode 恢復：

* 您傳遞 [`--permission-prompt-tool`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 且未傳遞 [`--permission-prompts none`](https://code.claude.com/docs/zh-TW/headless#turn-off-permission-prompts-in-unattended-runs)，以便 Claude Code 能呈現計畫以供核准
* 您未傳遞 `--permission-mode` 或 `--dangerously-skip-permissions`
* 您未傳遞 `--fork-session`
* 該次執行不是透過[頻道](https://code.claude.com/docs/zh-TW/channels.md)啟動的
* 沒有任何[拒絕規則](https://code.claude.com/docs/zh-TW/permissions.md#manage-permissions)移除 `ExitPlanMode` 工具

### 「Resume this conversation?」對話方塊

如果您在恢復工作階段時看到「Resume this conversation?」對話方塊，其估計值是僅已儲存的對話本身就會使用掉的 5 小時用量上限比例。該估計值不計入您已使用的部分。

在 Pro、Max 和 Ultra 方案中，當您[在長時間中斷後](https://code.claude.com/docs/zh-TW/prompt-caching.md#resuming-a-session)或在不同模型上恢復長對話時，可能會出現此對話方塊。估計的用量會在您選擇 **Resume** 後送出第一則訊息時產生，而不是在您選擇它時產生。請依您的下一個任務是否仍需要已儲存的對話來選擇：

* **Resume**：繼續在已儲存的對話中工作。
* **Start a new conversation**：切換到不需要已儲存對話的工作。若要稍後重新開啟它，請在提示詞輸入處執行 [`/resume`](#use-the-session-picker)。該估計值不適用於您在新對話中的第一則訊息。如果該選項表示 Claude 可以查閱此對話，您仍可在新對話中提及先前的工作。

### 工作階段選擇器的查找範圍

Claude Code 會依專案目錄儲存工作階段。根據預設，工作階段選擇器會顯示：

* 來自目前 worktree 的工作階段，包括[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)，它們在清單中會標記為 `bg`
* 在其他地方啟動並使用 `/add-dir` 新增目前目錄的工作階段

使用 `Ctrl+W` 可將範圍擴大到儲存庫的所有 worktree，或使用 `Ctrl+A` 擴大到此機器上的每個專案。

#### `/loop`、`-p`、Agent SDK 和背景工作階段

第一個提示詞是 [`/loop`](https://code.claude.com/docs/zh-TW/scheduled-tasks#run-a-prompt-repeatedly-with-%2Floop) 命令的工作階段不會出現在選擇器中，`claude --continue` 也會跳過它們。在對話稍後才執行 `/loop` 不會隱藏該工作階段。

Claude Code 會將使用 [`claude -p`](https://code.claude.com/docs/zh-TW/headless) 或 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 建立的工作階段排除在工作階段選擇器和 `claude --continue` 之外。您仍然可以將其工作階段 ID 傳遞給 `claude --resume <session-id>` 來恢復它。當您執行 [`claude -p --continue`](https://code.claude.com/docs/zh-TW/headless#continue-conversations) 時，Claude Code 會包含 `-p`、SDK 和 `/loop` 工作階段。

`claude --continue` 會開啟已完成的[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)，但不會開啟仍在執行的工作階段；開啟已完成的背景工作階段需要 Claude Code v2.1.257 或更新版本。如果您最近的對話是您[移到背景](https://code.claude.com/docs/zh-TW/agent-view.md#send-the-session-to-the-background)的對話，且它仍在背景執行，Claude Code 會顯示 `Your most recent conversation is running in the background` 和該工作階段的 ID 並退出。請從 [`claude agents`](https://code.claude.com/docs/zh-TW/agent-view#attach-to-a-session) 附加到該工作階段，或執行 `claude --resume` 以選擇另一個工作階段。

#### 其他 worktree 和專案中的工作階段

從同一儲存庫的另一個 worktree 選擇工作階段時，Claude Code 會在原處恢復它；當該工作階段自己的 worktree 已不存在時，Claude Code 會[在您目前的目錄中恢復它](https://code.claude.com/docs/zh-TW/worktrees.md#resume-a-worktree-session)。從不相關的專案選擇工作階段時，Claude Code 會改為將 `cd` 和恢復命令複製到您的剪貼簿。如果該專案的目錄已不存在，Claude Code 會在您目前的目錄中恢復該工作階段，而不是複製一個會失敗的 `cd` 命令。

使用 [`/cd`](https://code.claude.com/docs/zh-TW/commands) 移動工作階段會將其重新定位到新目錄的專案儲存空間，因此之後它會出現在該目錄的選擇器中。

#### 依工作階段 ID 或名稱恢復

您可以從任何目錄執行 `claude --resume <session-id>`，因此可以恢復在其他地方啟動或已使用 [`/cd`](https://code.claude.com/docs/zh-TW/commands) 移動的工作階段。Claude Code 會依下列順序尋找該 ID：

1. 目前的專案目錄及其 git worktree
2. 此機器上的所有其他專案

跨專案搜尋只有在恰好一個其他專案持有含該 ID 訊息的逐字稿時才會解析該 ID，因此手動複製的重複項會讓 Claude Code 回報找不到，而不是恢復任意一份副本。若沒有任何已儲存的工作階段符合該 ID，Claude Code 會回報 `No conversation found with session ID: <session-id>`。

依名稱恢復會在目前儲存庫及其 worktree 中解析。兩種形式都會尋找完全相符的項目，即使它位於不同的 worktree 中也會直接恢復：

| 命令 | 完全相符 | 名稱不明確 |
| :- | :- | :- |
| `claude --resume <name>` | 直接恢復 | 開啟工作階段選擇器，並以該名稱預先填入作為搜尋詞 |
| `/resume <name>` | 直接恢復 | 回報錯誤；執行不帶引數的 `/resume` 以開啟工作階段選擇器 |

## 命名您的 sessions

為 sessions 提供描述性名稱，以便在 session 選擇器中找到它們並按名稱恢復。當您並行處理多個任務時，這最為重要。

| 時間 | 如何設定名稱 |
| :- | :- |
| 啟動時 | `claude -n auth-refactor` |
| 在 session 期間 | `/rename auth-refactor`。名稱也會出現在提示列上 |
| 從 session 選擇器 | 反白 session 並按 `Ctrl+R` |
| 在計畫接受時 | 在 [plan mode](https://code.claude.com/docs/zh-TW/permission-modes.md#analyze-before-you-edit-with-plan-mode) 中接受計畫會根據計畫內容命名 session，除非您已經設定了一個 |
| 從 claude.ai 或 Claude 應用程式 | 重新命名 [Remote Control session](https://code.claude.com/docs/zh-TW/remote-control.md#connect-from-another-device)；Claude Code 在 CLI 中應用相同的名稱。需要 Claude Code v2.1.221 或更新版本 |
| 從桌面應用程式 | 在[桌面應用程式](https://code.claude.com/docs/zh-TW/desktop.md#organize-and-find-sessions)中重新命名工作階段 |

通過 CLI 路由或從 claude.ai 命名 session 後，使用 `claude --resume <name>` 或 `/resume <name>` 返回到它；桌面應用程式 session 在 [desktop app](https://code.claude.com/docs/zh-TW/desktop.md#work-in-parallel-with-sessions) 中恢復。請參閱[恢復 session](#resume-a-session) 以了解名稱解析在 worktrees 中的行為方式。

您未命名的 sessions 仍然會獲得 Claude Code 指派的兩個標籤。只有生成的標題可作為恢復控制代碼：

* 預設顯示名稱：您從未命名的互動式工作階段在啟動時仍會獲得預設顯示名稱。預設名稱結合了工作目錄的名稱和一個兩字元的後綴，例如 `my-app-3f`，並在執行中工作階段的列表中識別該工作階段，例如 [agent view](https://code.claude.com/docs/zh-TW/agent-view.md) 和 `claude agents --json` 輸出。預設名稱不是恢復控制代碼。如果您將其傳遞給 `claude --resume` 或 `/resume`，Claude Code 找不到該工作階段。
* 生成的標題：如果您未命名 session，Claude Code 會為其生成 session 標題。標題是您第一個提示的簡短摘要，由對小型/快速模型（通常是 Haiku 級別模型）的背景請求編寫。您直接從 shell 或指令碼啟動的 `claude -p` 執行不會獲得一個。

  接受計畫會將生成的標題替換為基於計畫的標題。您可以將任一標題傳遞給 `claude --resume` 或 `/resume`，Claude Code 會以與您設定的名稱相同的方式解析它。

## 使用 session 選擇器

在 session 內執行 `/resume`，或不帶引數執行 `claude --resume`，以開啟互動式 session 選擇器。使用這些快捷鍵來導航、搜尋和擴展清單：

| 快捷鍵 | 動作 |
| :- | :- |
| `↑` / `↓` 或 `k` / `j` | 在工作階段之間導航 |
| `→` / `←` | 展開或摺疊分組的 sessions |
| `Enter` | 恢復反白的 session |
| `1` 到 `9` | 恢復清單中該位置的工作階段 |
| `Space` | 預覽 session 內容。在不將其捕獲為貼上的終端上也可以使用 `Ctrl+V` |
| `Ctrl+R` | 重新命名反白的 session |
| `/` 或除 `Space`、`j`、`k` 或數字以外的任何可列印字元 | 進入搜尋模式並篩選工作階段。貼上 GitHub、GitHub Enterprise、GitLab 或 Bitbucket pull 或 merge request URL 以找到建立它的工作階段 |
| `Ctrl+A` | 顯示此機器上所有專案的 sessions。再次按下以返回目前儲存庫 |
| `Ctrl+W` | 顯示目前儲存庫所有 worktrees 的 sessions。再次按下以返回目前 worktree。僅在多 worktree 儲存庫中顯示 |
| `Ctrl+B` | 篩選為目前 git 分支的 sessions。再次按下以顯示所有分支 |
| `Esc` | 退出 session 選擇器或搜尋模式 |

每一列顯示工作階段名稱（如果已設定），否則顯示 AI 生成的工作階段標題、對話摘要或第一個提示詞，以及自上次活動以來的時間、git 分支和檔案大小。

使用 `/branch` 或 `--fork-session` 建立的 sessions 會取得自己的 session ID，並顯示為單獨的列。當選擇器為同一個 session 找到多個項目時，它會將它們分組在單一列下。按 `→` 展開群組。

如果 Claude Code 無法從 `claude --resume` 選擇器載入您選擇的 session，它會列印 [`Failed to resume the conversation`](https://code.claude.com/docs/zh-TW/errors#failed-to-resume-the-conversation)，並提供重試命令，然後以代碼 1 結束。從 session 內的 `/resume` 選擇器，Claude Code 會報告失敗，您目前的對話會繼續執行。

## 分支 session

分支會建立迄今為止對話的副本並將您切換到其中，保持原始對話完整。使用它來嘗試不同的方法，而不會失去您所在的路徑。

從 session 內，執行 `/branch` 並使用可選名稱：

```text theme={null}
/branch try-streaming-approach
```

如果您省略名稱，Claude Code 會根據對話中的第一個提示詞為新分支命名。

從命令列，將 `--continue` 或 `--resume` 與 `--fork-session` 結合：

```bash theme={null}
claude --continue --fork-session
```

`/branch` 確認會列印兩個 session ID：您現在所在的新分支和原始分支。原始分支在磁碟上保持不變，並在 session 選擇器中保持可用；使用 `/resume <original-name>` 或將其 ID 傳遞給 `/resume` 以返回它。

`/branch` 複製文字記錄並將執行中的 Claude Code 程序切換為寫入到它。該區別決定了分支繼承的內容：

| 狀態 | 執行 `/branch` 後 |
| :- | :- |
| 對話歷史 | 複製到分支中，直到您執行 `/branch` 的位置 |
| 「允許此 session」權限授予 | 轉移；分支在同一程序中執行，因此您現有的授予仍然適用。如果您使用 `--fork-session` 分支到單獨的程序，新程序啟動時沒有這些授予，您需要在那裡重新核准 |
| 執行中的 [背景子代理](https://code.claude.com/docs/zh-TW/sub-agents.md#run-subagents-in-foreground-or-background) 和 [背景 Bash 命令](https://code.claude.com/docs/zh-TW/interactive-mode.md#background-bash-commands) | 繼續執行。它們的輸出出現在您切換到的新分支中，而不是在原始 session 中 |
| [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 連線 | 保持連線。連線到 session 的手機或瀏覽器會跟隨您進入分支，並在那裡繼續接收新訊息 |

如果您在兩個終端中恢復同一 session 而不進行分支，來自兩者的訊息會交錯到一個文字記錄中。有關單個 session 內基於 checkpoint 的 rewind，請參閱 [Checkpointing](https://code.claude.com/docs/zh-TW/checkpointing.md)。

## 在 session 內管理上下文

這些命令控制上下文視窗中的內容，而無需離開 session：

* **`/clear`**：以空上下文重新開始。Claude Code 會儲存先前的工作階段；使用 `/resume` 恢復它，或在同一個 Claude Code 程序中，從[倒帶選單的前一個工作階段項目](https://code.claude.com/docs/zh-TW/checkpointing.md#rewind-past-a-cleared-conversation)。不帶引數時，新工作階段會保留您使用 `--name` 或 `/rename` 設定的名稱，但不會保留 AI 生成的工作階段標題。若要改為命名您要離開的工作階段，請傳遞名稱，如 `/clear release-prep`；新工作階段隨後會以未命名狀態開始
* **`/compact [instructions]`**：用摘要替換歷史記錄，可選擇性地專注於您指定的內容
* **`/context`**：顯示目前消耗上下文的內容

有關壓縮如何與 CLAUDE.md、skills 和規則互動，請參閱[上下文視窗指南](https://code.claude.com/docs/zh-TW/context-window.md)。有關何時清除與壓縮的策略，請參閱[最佳實踐](https://code.claude.com/docs/zh-TW/best-practices.md#keep-cost-and-context-down)。

## 匯出和定位工作階段資料

執行 `/export` 以開啟一個選單，讓您將目前對話複製到剪貼簿或將其儲存為純文字檔案，訊息和工具輸出呈現為可讀文字。傳遞檔案名以略過選單並直接寫入該檔案。

### 從指令碼存取對話

`/export` 產生供人閱讀的呈現逐字稿。下列介面產生供指令碼解析的結構化資料：執行的 JSON 結果、工作階段逐字稿檔案的路徑，或事件的即時串流。根據觸發指令碼的內容選擇：

* **執行 Claude 一次並擷取結果**：使用 [`--output-format json` 或 `stream-json`](https://code.claude.com/docs/zh-TW/headless#get-structured-output) 叫用 `claude -p`，以將非互動執行的結果、工作階段 ID、使用情況和成本擷取為結構化 JSON。
* **詢問現有工作階段一個問題**：將工作階段 ID 傳遞給 [`claude -p --resume`](https://code.claude.com/docs/zh-TW/headless#continue-conversations)，以傳送後續提示詞（例如摘要請求），並擷取結構化回應。
* **對工作階段事件做出反應**：讀取 [hook](https://code.claude.com/docs/zh-TW/hooks.md#common-input-fields) 和 [狀態列命令](https://code.claude.com/docs/zh-TW/statusline.md#available-data) 作為輸入接收的 `transcript_path` 欄位。`SessionEnd` hook 可在工作階段結束時封存逐字稿。
* **在 TypeScript 或 Python 應用程式中嵌入 Claude**：使用 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 以程式設計方式接收每條訊息。

下列範例使用第二個介面。它傳送後續提示詞給現有工作階段，並使用 `jq` 讀取答案：

```bash theme={null}
claude -p --resume <session-id> --output-format json "summarize what we changed" | jq -r '.result'
```

### 逐字稿儲存位置

根據預設，Claude Code 將逐字稿儲存為 JSONL，位置為 `~/.claude/projects/<project>/<session-id>.jsonl`，其中 `<project>` 是您的工作目錄路徑，非英數字元已被 `-` 取代。對於轉換後的名稱超過 200 個字元的工作目錄，Claude Code 會將名稱截斷為 200 個字元，並附加完整路徑的雜湊值，以便目錄名稱保持在檔案系統限制內。

每一行都是一個 JSON 物件：一則訊息、一次工具使用或結果、一筆 Claude Code 傳送給模型的請求紀錄，或一個中繼資料項目。項目格式是 Claude Code 的內部格式，在版本之間會變更，因此直接解析這些檔案的指令碼可能在任何版本上中斷。若要建立在工作階段資料上，請改用 `/export` 或 [指令碼介面](#access-conversations-from-scripts)。

位置、保留期和寫入行為可設定：

| 目的 | 設定 | 位置 |
| - | - | - |
| 將儲存空間移出 `~/.claude` | [`CLAUDE_CONFIG_DIR`](https://code.claude.com/docs/zh-TW/env-vars) | 環境變數 |
| [自行命名 `<project>` 目錄](#name-the-project-directory-yourself) | [`CLAUDE_CODE_PROJECT_DIR_NAME`](https://code.claude.com/docs/zh-TW/env-vars) | 環境變數 |
| 變更 30 天保留期 | [`cleanupPeriodDays`](https://code.claude.com/docs/zh-TW/settings-reference#cleanupperioddays) | `settings.json` |
| 為 [Claude Desktop 和 Cowork 逐字稿](https://code.claude.com/docs/zh-TW/claude-directory.md#cleaned-up-automatically) 設定年齡限制 | [`desktopSessionCleanupPeriodDays`](https://code.claude.com/docs/zh-TW/settings-reference#desktopsessioncleanupperioddays) | 使用者設定、受管設定或 `--settings` |
| 限制 `-p` 或 Agent SDK 工作階段的逐字稿檔案可成長的大小 | [`CLAUDE_CODE_TRANSCRIPT_LOCAL_GC`](https://code.claude.com/docs/zh-TW/env-vars) | 環境變數 |
| 在所有模式中禁止逐字稿寫入 | [`CLAUDE_CODE_SKIP_PROMPT_HISTORY`](https://code.claude.com/docs/zh-TW/env-vars) | 環境變數 |
| 禁止一次非互動執行的寫入 | [`--no-session-persistence`](https://code.claude.com/docs/zh-TW/cli-reference) | 搭配 `claude -p` 的 CLI 旗標 |

### 刪除工作階段資料

逐字稿在 [保留掃描規則](https://code.claude.com/docs/zh-TW/claude-directory.md#cleaned-up-automatically) 下會逐漸過期。若要更快刪除專案的逐字稿和相關狀態，請執行 [`claude purge`](https://code.claude.com/docs/zh-TW/claude-directory#clear-local-data)。如果您使用 [`claude rm <id>`](https://code.claude.com/docs/zh-TW/agent-view#what-deleting-a-session-removes) 刪除 [背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)，其逐字稿會保留在磁碟上，並且仍可透過 `claude --resume` 存取。

### 自行命名專案目錄

根據預設，Claude Code 從整個工作目錄路徑衍生 `<project>` 名稱。若要自行選擇名稱，請將 `CLAUDE_CODE_PROJECT_DIR_NAME` 與 `CLAUDE_CONFIG_DIR` 一起設定。Claude Code 隨後會將該工作階段的逐字稿和 [自動記憶](https://code.claude.com/docs/zh-TW/memory.md#auto-memory) 儲存在您的名稱下。這適合嵌入 Claude Code 的主機，並為每個工作階段提供自己的設定目錄。需要 Claude Code v2.1.234 或更新版本。

例如，此啟動會將租戶 A 的資料保留在 `/srv/tenant-a` 下，並將其專案目錄命名為 `work`：

```bash theme={null}
CLAUDE_CONFIG_DIR=/srv/tenant-a CLAUDE_CODE_PROJECT_DIR_NAME=work claude
```

Claude Code 將工作階段的逐字稿寫入 `/srv/tenant-a/projects/work/`，並將其自動記憶寫入 `/srv/tenant-a/projects/work/memory/`，無論工作目錄為何。

設定時適用三項規則：

* **同時設定 `CLAUDE_CONFIG_DIR`**：名稱不會隨工作目錄而變化，因此在預設 `~/.claude` 下，它會將每個專案的逐字稿和自動記憶合併到一個目錄中。當 `CLAUDE_CONFIG_DIR` 未設定時，Claude Code 會忽略 `CLAUDE_CODE_PROJECT_DIR_NAME`。
* **使用 1-64 個字母、數字、連字號或底線**：不要使用 Windows 裝置名稱，例如 `con`。Claude Code 會忽略任何其他值，並使用衍生名稱。
* **在啟動 `claude` 的 shell 環境中設定它**：Claude Code 在啟動時從該環境讀取一次，因此設定檔中的 `env` 區塊無法設定它。

命名設定目錄的專案目錄後，請繼續使用該名稱啟動。如果您使用相同的 `CLAUDE_CONFIG_DIR` 啟動 Claude Code，但不使用 `CLAUDE_CODE_PROJECT_DIR_NAME`，它會再次讀取和寫入衍生目錄。儲存在您名稱下的工作階段會保留在磁碟上：在 [工作階段選擇器](#use-the-session-picker) 中按 `Ctrl+A` 以列出該設定目錄下每個專案目錄中的工作階段（包括已釘選的），無論您如何啟動，[`claude --resume <session-id>`](#resume-a-session) 都會找到儲存在任一名稱下的工作階段。

## 另請參閱

這些頁面涵蓋相關的 session 和平行處理機制：

* [Worktrees](https://code.claude.com/docs/zh-TW/worktrees.md)：在單獨的分支上執行隔離的平行 sessions
* [Checkpointing](https://code.claude.com/docs/zh-TW/checkpointing.md)：將程式碼和對話 rewind 到較早的點
* [Context window](https://code.claude.com/docs/zh-TW/context-window.md)：什麼填充上下文以及什麼在壓縮中存活
* [Non-interactive mode](https://code.claude.com/docs/zh-TW/headless.md)：`claude -p` 下的 session 行為

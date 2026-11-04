<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/agent-view | lastmod: 2026-11-03 | section: Build with Claude Code / Agents and parallel work -->
> 來源：https://code.claude.com/docs/zh-TW/agent-view（官方 zh-TW，lastmod 2026-11-03）｜分類：Build with Claude Code › Agents and parallel work｜EN 摘要：Dispatch and manage many Claude Code sessions from one screen. Agent view shows what every session is doing and which ones need your input.

# 使用 Agent view 管理多個代理

> 從一個螢幕分派和管理許多 Claude Code 工作階段。Agent view 顯示每個工作階段正在做什麼，以及哪些需要您的輸入。

Agent view（使用 `claude agents` 開啟）是所有背景工作階段的一個螢幕：什麼正在執行、什麼需要您的輸入，以及什麼已完成。分派新工作階段，一目瞭然地查看它們的狀態，而不是滾動瀏覽記錄，並且只在需要時才介入。每個背景工作階段都是一個完整的 Claude Code 對話，在沒有終端連接的情況下持續執行，因此您可以隨時開啟、回覆和離開。

![終端中的 Agent view。頂部的一行計算等待輸入、執行中和已完成的工作階段。四個工作階段分組在「需要輸入」、「執行中」和「已完成」下。每一行顯示工作階段的名稱、其最新狀態或問題，以及一個時間。底部是用於描述新任務的輸入和一行快捷鍵提示。](https://mintcdn.com/claude-code/HDAmBwgbrZVk0pOt/images/agent-view-light.png?fit=max\&auto=format\&n=HDAmBwgbrZVk0pOt\&q=85\&s=d6905012bee31f3e6b3920b09c05dd02)

當您有多個獨立任務 Claude 可以在不需要您監看每一步的情況下執行時，請使用 agent view。分派一個錯誤修復、一個拉取請求審查和一個不穩定測試調查作為三行，在另一個視窗中繼續工作，並在某一行顯示需要您或有結果時檢查。

當您想在任何代理的工作階段中更直接地工作時，附加到該行以進入完整對話。

若要比較 agent view 與 subagents、agent teams 和 worktrees，請參閱 [平行執行代理](https://code.claude.com/docs/zh-TW/agents.md)。Agent view 在您的機器上執行工作階段，您分派每一個；若要讓 Claude 從一個對話開始並在雲端追蹤平行工作階段，請參閱 [Projects](https://code.claude.com/docs/zh-TW/claude-projects.md)。

> [!NOTE]
>
> Agent view 處於研究預覽版本。隨著功能的發展，介面和快捷鍵可能會改變。

## 快速開始

本逐步解說涵蓋核心 agent view 迴圈：分派工作、在 Claude 工作時觀看其列更新、查看以檢查並回覆，以及附加以檢視完整對話。您分派的工作階段在關閉 agent view 後會繼續執行，因此您可以離開並稍後返回。

**1. 開啟 agent view**

從您的 shell，執行：

```bash theme={null}
claude agents
```

如果您尚未接受該目錄的[工作區信任對話](https://code.claude.com/docs/zh-TW/permissions.md#project-allow-rules-and-workspace-trust)，Claude Code 會在 agent view 開啟前顯示它，與 `claude` 顯示的對話相同。接受以儲存工作區的信任並繼續。如果您拒絕，Claude Code 會退出而不開啟 agent view。

Agent view 開啟，底部有輸入框，隨著工作階段啟動，表格會填入。按 `Esc` 返回您的 shell；如果您透過以 `←` 將工作階段移至背景來開啟 agent view，`Esc` 會改為返回該對話。您的工作階段在您離開時繼續執行，下次開啟 agent view 時會重新出現。

**2. 分派工作階段**

輸入描述工作的提示詞並按 `Enter`。新的背景工作階段在該工作上啟動並顯示為一列，顯示它是否正在工作、等待您或已完成。新工作階段使用 agent view 標題中顯示的模型。[它啟動時所在的權限模式](#permission-mode-model-and-effort)取決於您如何開啟 agent view。

您在此輸入的每個提示詞都會啟動自己的新工作階段。輸入另一個提示詞並按 `Enter` 會在第一個工作階段旁邊啟動第二個工作階段，而不是向其發送後續訊息。您可以以這種方式並行執行多個工作階段。

每個工作階段獨立使用您的訂閱配額，因此在一次分派許多工作階段之前，請參閱[限制](#limitations)。

**3. 查看和回覆**

使用箭頭鍵選擇一列，然後按 `Space` 開啟查看面板。它顯示工作階段的最新輸出或它正在等待的問題，而不是完整的逐字稿。輸入回覆並按 `Enter` 發送，無需離開 agent view。

**4. 附加和分離**

在一列上按 `Enter` 或 `→` 以在需要完整對話時附加。工作階段會接管終端機，成為完整的互動式 Claude Code 工作階段。在空白提示詞上按 `←` 分離並返回表格。

**5. 帶入現有工作階段**

這個步驟需要一個執行中的工作階段。如果您遵循了之前的步驟，您在此終端機中沒有開啟的工作階段，因此請在另一個終端機中開啟一個一般 `claude` 工作階段並先向其發送訊息。

要將您已開啟的工作階段移入 agent view，在其中執行 `/bg`，或在空白提示詞上按 `←` 以在一個步驟中將工作階段移至背景並開啟 agent view。在尚無訊息的全新工作階段中，`/bg` 會要求您先發送訊息，而 `←` 可以立即運作。工作階段繼續執行並顯示為一列，與您分派的工作階段並排。

在一般 `claude` 工作階段中，於空白提示詞上按 `←` 會開啟 agent view，而頁尾中的 `←` 提示會回報您的背景工作階段狀態：

* **提示**：工作階段開啟後，頁尾會顯示 `← for agents` 十秒鐘。提示消失後，按 `←` 仍然有效
* **等待計數**：當背景工作階段正在等待您的輸入時，同一位置會計算其數量，例如 `← 2 agents`，或在超過 99 個等待時顯示 `← 99+ agents`。當終端機獲得焦點時，計數大約每十秒刷新一次，當焦點返回時立即刷新
* **完成計數**：當背景工作階段成功完成且沒有任何工作階段等待您的輸入時，頁尾會短暫顯示已完成的數量，例如兩個完成時顯示 `← 2 done`

當等待計數增加或減少時，以及當背景工作階段成功完成時，它會短暫改變顏色。如果您開啟 [`prefersReducedMotion`](https://code.claude.com/docs/zh-TW/settings-reference#prefersreducedmotion)，您將不會看到顏色變化，也不會看到 `done` 計數。在[螢幕閱讀器模式](https://code.claude.com/docs/zh-TW/accessibility.md)中，`←` 提示及其計數會被隱藏。

### 預設開啟 agent view

要讓 `claude` 在沒有引數的情況下開啟 agent view 而不是新對話，請開啟 `/config` 設定。

**1. 開啟設定**

在一般 `claude` 工作階段中，執行 `/config` 並開啟 **Open agents view by default**。若要跳過選單，直接設定 [`defaultToAgentsView`](https://code.claude.com/docs/zh-TW/settings-reference#defaulttoagentsview) 鍵：

```text theme={null}
/config defaultToAgentsView=true
```

**2. 啟動 Claude Code**

退出工作階段，然後執行沒有引數的 `claude`：

```bash theme={null}
claude
```

Agent view 會開啟以取代新對話。

當設定開啟時，若要啟動一般工作階段，請傳遞提示詞：`claude "fix the login test"`。若要關閉設定，在一般工作階段中或從 agent view 附加的工作階段中執行 `/config defaultToAgentsView=false`。

## 使用 agent 檢視監控工作階段

執行 `claude agents` 以開啟 agent 檢視。它會接管整個終端機，並按狀態分組列出每個工作階段，已釘選的工作階段和需要您處理的工作階段位於頂部。每一列顯示工作階段的名稱、目前活動和經過時間，經過時間從工作階段建立時開始計算；已完成工作階段的經過時間會固定為該次執行所花費的時間。

名稱會以該工作階段中由 [`/color`](https://code.claude.com/docs/zh-TW/commands) 設定的顏色著色，包括當您使用 `←` 或 `/background` [將工作階段移至背景](#from-inside-a-session) 時。

根據預設，清單會顯示您已啟動的每個背景工作階段，涵蓋所有專案。在一個儲存庫中工作的工作階段和在另一個 worktree 中工作的工作階段都會出現在這裡，無論您從哪個目錄開啟 agent 檢視。若要將清單縮小到單一專案，請傳遞 `--cwd`：

```bash theme={null}
claude agents --cwd ~/projects/my-app
```

這只會顯示在該目錄下啟動的工作階段。它仍然會列出已 [移入 `~/projects/my-app/.claude/worktrees/` 下的 worktree](#how-file-edits-are-isolated) 的工作階段。

您在其他終端機中開啟的互動式工作階段不會出現，直到您 [將它們移至背景](#from-inside-a-session)。工作階段產生的 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 和 [隊員](https://code.claude.com/docs/zh-TW/agent-teams.md) 不會列為單獨的列。

```text theme={null}
Pinned
  ✽ clawd walk cycle          Drawing the walk-cycle sprite frames          3m

Ready for review
  ∙ jump physics              Opened PR with collision fix                 #2048  2h

Needs input
  ✻ power-up design           double jump or wall climb?                    1m

Working
  ✽ collision detection       Adding swept-AABB checks to CollisionSystem   2m
  ✢ playtest level 3          all checkpoints cleared ×12                in 4m

Completed
  ✻ title screen              menu, options, and credits done               9m
  ∙ sound effects             14 SFX exported to assets/audio               4h
  … 6 more
```

### 讀取工作階段狀態

每一列開頭的圖示，其顏色和動畫顯示工作階段的狀態：

| 狀態 | 圖示顯示為 | 意義 |
| :- | :- | :- |
| Working | 動畫 | Claude 正在主動執行工具或產生回應 |
| Needs input | 黃色 | Claude 正在等待只有您才能提供的內容：問題的答案、權限決定，或只有您才能回答的其他提示，例如允許網路主機的 [沙箱](https://code.claude.com/docs/zh-TW/sandboxing.md) 提示，或 MCP 伺服器的 [輸入請求](https://code.claude.com/docs/zh-TW/mcp.md#respond-to-mcp-elicitation-requests)。需要附加終端機的命令，例如 `/install-github-app` 或 `/mcp` 設定清單，[也會讓無人值守的工作階段停留在此處](#attach-to-a-session) |
| Idle | 變暗 | 工作階段沒有任何工作要做，已準備好接收您的下一個提示詞 |
| Completed | 綠色 | 任務成功完成 |
| Failed | 紅色 | 任務以錯誤結束 |
| Stopped | 灰色 | 您使用 `Ctrl+X` 或 `claude stop` 停止了工作階段、[其程序從 Claude Code 外部被結束](#the-supervisor-process)，或 [它在背景服務關閉時結束](#sessions-show-as-failed-after-shutdown) |

另外，圖示的形狀有其自身的意義：

| 形狀 | 意義 |
| :- | :- |
| `✻` 或動畫 `✽` | 工作階段程序正在執行，或工作階段需要您的輸入 |
| `∙` | 程序已結束。您仍然可以查看該列，當您回覆或附加時，Claude 會從其已儲存的對話重新啟動它 |
| `✢` | 在迭代之間休眠的 [`/loop`](https://code.claude.com/docs/zh-TW/scheduled-tasks) 工作階段。該列顯示其執行次數和倒數計時 |

可能出現在列右邊緣的 `#N` 或 `!N` 標籤是指向工作階段的 [pull request 或 merge request](#pull-request-status) 的連結，不是狀態圖示的一部分。

agent 檢視開啟時，終端機分頁標題會顯示等待輸入的數量：當有工作階段需要輸入時為 `2 awaiting input · claude agents`，沒有時則為 `claude agents`。

若要從指令碼或其他程式讀取工作階段狀態，請使用 [`claude agents --json`](#read-session-state-from-a-script)，而不是 `~/.claude/jobs/` 下的檔案。

當 agent 檢視開啟時，若本機背景工作階段開始需要您的輸入、完成或失敗，Claude Code 也會透過您設定的 [終端機通知頻道](https://code.claude.com/docs/zh-TW/terminal-config.md#get-a-terminal-bell-or-notification) 發送通知。依排程執行的工作階段，例如 [`/loop`](https://code.claude.com/docs/zh-TW/scheduled-tasks) 工作階段，只在需要您的輸入時通知。通知使用與 Claude Code 其餘部分相同的 [`preferredNotifChannel` 設定](https://code.claude.com/docs/zh-TW/settings-reference#preferrednotifchannel)，並以 `agent_needs_input` 或 `agent_completed` 類型觸發 [`Notification` hook](https://code.claude.com/docs/zh-TW/hooks#notification)。

背景工作階段不需要開啟任何終端機即可繼續工作。一個獨立的 [監督程序](#the-supervisor-process) 會執行它們，因此您可以關閉 agent 檢視、關閉您的 shell，或啟動新的互動式工作階段，您分派的工作會繼續進行。

工作階段狀態會保存在磁碟上，不受自動更新和監督程序重新啟動影響。當您的機器休眠時，工作階段也會被保留。它們的程序在喚醒時繼續執行，監督程序會重新連接到它們，而不會將時間間隔視為閒置。關機仍會停止執行中的工作階段；請參閱 [工作階段在關機後顯示為失敗或停止](#sessions-show-as-failed-after-shutdown) 以了解如何復原它們。

在機器休眠時正處於回應中途的工作階段，恢復後可能沒有回應。當您開啟已停止回應的工作階段時，監督程序會重新啟動其程序，工作階段會從中斷的地方繼續被中斷的回應。

### 列摘要

每列中的單行摘要由 [Haiku 級模型](https://code.claude.com/docs/zh-TW/model-config.md) 產生，讓該列無需開啟逐字稿即可告訴您工作階段在做什麼、需要什麼或產生了什麼。當工作階段正在主動工作時，列文字最多每 15 秒根據工作階段自身的最近輸出更新一次，不會發送模型請求，並且模型會在每個回合結束時撰寫新的摘要。

工作中的列會顯示工作階段自述正在做的事，被阻擋的列則顯示它正在提出的問題。在較長的回合期間，模型也會每隔幾分鐘重寫摘要，讓忙碌的列不會持續顯示過時的摘要。摘要文字會填滿列的剩餘寬度；開啟 [查看面板](#peek-and-reply) 即可閱讀被終端機邊緣截斷的句子。

當清單 [按目錄分組](#organize-the-list) 時，摘要會以彩色文字顯示的工作階段狀態開頭，例如 `Needs input · double jump or wall climb?`。在預設的狀態分組中，群組標題已標示狀態，因此列只會顯示摘要。

回合結束摘要和每次回合中途的重寫，都是透過您的一般提供者發送的一個簡短 Haiku 級請求，並依照與工作階段本身相同的 [資料使用條款](https://code.claude.com/docs/zh-TW/data-usage.md) 計費和處理。模型重寫之間的 15 秒更新會重複使用工作階段自身的輸出，不會發送請求。在未設定 Haiku 級模型的第三方提供者或閘道上，請求會改用工作階段的主要模型；設定 [`ANTHROPIC_DEFAULT_HAIKU_MODEL`](https://code.claude.com/docs/zh-TW/model-config#environment-variables) 即可選擇一個模型。

### Pull request 狀態

當工作階段 [開啟 pull request](#how-file-edits-are-isolated) 時，Claude Code 會在列的右邊緣新增連結到該 pull request 的標籤：

* Claude Code 將 pull request 的標籤寫為 `#1234`，將 GitLab merge request 的標籤寫為 `!1234`。
* 即使 Claude Code 無法偵測到超連結支援（例如透過 SSH 或 tmux），它仍會輸出連結。設定 [`FORCE_HYPERLINK=0`](https://code.claude.com/docs/zh-TW/env-vars) 即可將標籤呈現為純文字。
* 在您向工作階段發送後續訊息後，列會回到顯示即時進度，而 Claude Code 會保留該標籤。

處理現有 pull request 的工作階段也會以相同方式連結到它。Claude Code 依 Claude 執行的命令以不同方式尋找 pull request：

* 當 Claude 使用 `gh` 編輯、留言、關閉或將 pull request 標記為就緒時，Claude Code 會連結該命令自身輸出中指明的 pull request。若 `gh` 命令擷取到的輸出未指明任何 pull request，則不會建立連結；`gh pr merge` 是常見情況，因為它只會將結果列印到互動式終端機。
* 當 Claude 使用 `gh pr checkout` 簽出 pull request 或推送到分支時，Claude Code 會使用 `gh pr view` 查詢該分支，並連結其開啟中的 pull request。
* Claude 推送時，pull request 不需要已經存在：Claude Code 會在同一目錄中之後執行的最多五個 `git`、`gh`、`glab` 或 `curl` 命令後重試分支查詢，因此在推送後建立的 pull request，包括 Claude 透過 GitHub REST API 建立的 pull request，會在重試找到它時建立連結。

當工作階段連結到多個 pull request 時，標籤會改為顯示數量，例如 `3 PRs`，並依最需要關注的開啟中 pull request 著色。開啟 [查看面板](#peek-and-reply) 即可查看全部。

Pull request 編號會依其狀態著色：

| 顏色 | Pull request 狀態 |
| :- | :- |
| 黃色 | 等待檢查或審查，或檢查失敗 |
| 綠色 | 檢查通過且沒有審查阻擋 |
| 紫色 | 已合併 |
| 灰色 | 草稿或已關閉 |

對於以 pull request 作為結果的任務，請查看此標籤取得結果：當編號變成綠色時，審查並合併該 pull request。

### 查看和回覆

在選定的列上按 `Space` 以開啟查看面板。面板開啟時會顯示該列在終端機邊緣被截斷的句子，而顯示哪個句子取決於工作階段的狀態：

* 等待您的工作階段：它提出的確切問題，位於回覆輸入上方
* 已完成的工作階段：其結果
* 工作中的工作階段：其完整狀態句子

接著會列出連結到該工作階段的所有 pull request。對於正在等待您或以安全模式執行的工作階段，其下方還會多出一行：

* 例如 `waiting 3m` 的一行：工作階段已等待您多久。列右邊緣的經過時間是另一個數字：它從工作階段啟動時開始計算
* `safe mode · customizations are off`：此工作階段在 [您的自訂項目已關閉](https://code.claude.com/docs/zh-TW/debug-your-config.md#test-against-a-clean-configuration) 的狀態下執行，因為您是從 shell 使用 `claude --bg --safe-mode` 啟動它。您可以維持原狀。若要在重新啟用自訂項目的情況下繼續對話，請執行 [`claude stop <id>`](#manage-sessions-from-the-shell)，然後執行 [`claude --resume`](https://code.claude.com/docs/zh-TW/sessions#resume-a-session)，兩者都在您的 shell 中執行

大多數時候查看面板就足夠了，您不需要開啟完整逐字稿。

在查看面板中輸入回覆，然後按 `Enter` 將其發送到該工作階段。在回覆前加上 `!` 則改為發送 Bash 命令。回覆的處理方式取決於工作階段以及您發送的內容：

* 工作中的工作階段：`/model`、`/effort`、`/rename` 和 `/usage` 會立即執行。其他回覆會加入工作階段的 [訊息佇列](https://code.claude.com/docs/zh-TW/interactive-mode.md#queue-messages-while-claude-works)，而不會中斷回應，並在 [佇列中的輸入生效時](https://code.claude.com/docs/zh-TW/interactive-mode.md#when-claude-code-sends-what-you-queued) 生效。其他 [命令](https://code.claude.com/docs/zh-TW/commands.md) 會等到回合結束才執行，即使是在工作階段自身的提示詞輸入中一輸入就會立即執行的命令也是如此
* 內容恰好為 `/stop` 的回覆：無論工作階段正在工作或正在等待您，都會立即停止工作階段，而不會傳遞給它
* [Shell 工作](#run-a-shell-command)：回覆（包括 `/stop`）會作為輸入內容送到該命令的終端機

當工作階段正在等待您時，從查看面板回答的方式取決於它在等待什麼：

* 具有預定義選項的問題：面板會以編號列出選項。在回覆輸入為空時，按下選項的編號以填入該選項，再按 `Enter` 發送，或改為輸入您自己的答案
* 沒有預定義選項的問題：輸入您的答案。當空白輸入顯示建議的回覆時，按 `Tab` 將其填入，並在發送前編輯
* 權限提示或其他對話框，例如 [沙箱](https://code.claude.com/docs/zh-TW/sandboxing.md) 提示或 MCP 伺服器的 [輸入請求](https://code.claude.com/docs/zh-TW/mcp.md#respond-to-mcp-elicitation-requests)：回覆無法回答它。您的回覆會在佇列中等待。若要回答對話框，請使用 `→` 附加

當 [`PermissionRequest`](https://code.claude.com/docs/zh-TW/hooks#permissionrequest) 或 [`PreToolUse`](https://code.claude.com/docs/zh-TW/hooks#pretooluse) hook 針對工作階段所詢問的呼叫傳回 Claude Code 無法驗證的輸出時，列會在待處理請求的文字之前顯示 hook 事件，以及 `hook output invalid:` 和驗證錯誤。對於以其他方式失敗的 hook，列會顯示該 hook 失敗。工作階段仍會等待同一個請求。

當回覆無法傳遞時，錯誤訊息會說明該回覆是否已儲存。以 `!` 或 `/` 為前綴的回覆一律不會被儲存。下次您重新啟動工作階段時，Claude Code 會將已儲存的回覆作為工作階段的下一個提示詞發送；其他回覆請再次發送。

在 [按住模式](https://code.claude.com/docs/zh-TW/voice-dictation.md#hold-to-record) 下啟用 [語音聽寫](https://code.claude.com/docs/zh-TW/voice-dictation.md) 後，在回覆輸入聚焦時按住您的按鍵通話鍵，即可以聽寫代替輸入回覆。相同的方式也適用於 agent 檢視底部的分派輸入。

使用 `↑` 和 `↓` 查看相鄰的工作階段而無需關閉面板，或使用 `→` 附加。

### 附加到工作階段

在選定的列上按 `Enter` 或 `→` 以附加。agent 檢視會被完整的互動式工作階段取代。當您附加時，Claude 會發布一則簡短回顧，說明您離開期間發生的事。

附加時，工作階段的行為與任何其他 Claude Code 工作階段相同：[命令](https://code.claude.com/docs/zh-TW/commands.md)、鍵盤快捷鍵和功能都可正常運作，但以下情況除外。

附加時，`/install-github-app` 和 [`/mcp`](https://code.claude.com/docs/zh-TW/mcp) 設定清單可正常運作，因為終端機前有人可以完成它們的對話框。當沒有人附加時，這些命令無法開啟對話框，因此工作階段會出現在 agent 檢視的 `Needs input` 下，列上顯示如 `open this session to manage MCP servers` 的內容，逐字稿中的回應也會說明相同的事。附加並再次執行該命令即可繼續；當您附加時，需要輸入的列會被清除。`/mcp reconnect <server>`、`/mcp enable` 和 `/mcp disable` 無論如何都可以在不附加的情況下運作。

無論您的 `tui` 設定為何，附加的工作階段一律以 [全螢幕模式](https://code.claude.com/docs/zh-TW/fullscreen.md) 呈現，因為背景工作階段沒有可附加內容的終端機捲動緩衝區。使用 `PgUp`、`PgDn` 或滑鼠滾輪捲動，並按 `Ctrl+O` 進入逐字稿模式。您終端機的原生捲動和 tmux 複製模式只會顯示目前的檢視區，與執行任何全螢幕應用程式時相同。

附加的工作階段不會 [向您的終端機回報其狀態](https://code.claude.com/docs/zh-TW/terminal-config.md#see-session-status-in-your-terminal)。

在空白提示詞輸入上按 `←`，或執行 `/exit`，即可分離並返回 agent 檢視，無論您是從 agent 檢視開啟工作階段，還是從 shell 使用 `claude attach <id>` 開啟。

當 [`/btw` 覆蓋層](https://code.claude.com/docs/zh-TW/interactive-mode#side-questions-with-%2Fbtw) 開啟時，`←` 也會分離。需要 Claude Code v2.1.257 或更新版本。仍在回答中的旁支問題會在您離開期間繼續執行。下次您附加時，覆蓋層會重新開啟並顯示該問題或其答案。

在 Windows 上，如果您在附加後約半秒內按 `←`，Claude Code 會顯示 `Ambiguous ←, press again to detach`，因為在這段時間內，終端機可能會重新傳遞您附加前的按鍵。再按一次 `←` 即可分離。

`Ctrl+Z` 也會分離，但會回到您開始的地方：若您是從 agent 檢視附加，則回到 agent 檢視；若您執行的是 `claude attach`，則回到您的 shell。當對話框取得焦點且不回應 `←` 時，請使用 `Ctrl+Z`。

附加時，`Ctrl+C` 保留其標準的中斷行為：它會取消執行中的回應或 `!` shell 命令，而不是分離。在空白提示詞輸入上按兩次 `Ctrl+C` 會分離。

分離永遠不會停止背景工作階段：`←`、`Ctrl+Z`、`/exit`，以及按兩次 `Ctrl+C` 或兩次 `Ctrl+D`，都會讓它繼續執行。如果您在 `/loop` 等待下一次迭代時分離，迴圈會繼續執行，且該次迭代會在您不在場的情況下依排程開始。若要在分離前停止迴圈，請參閱 [停止迴圈](https://code.claude.com/docs/zh-TW/scheduled-tasks.md#stop-a-loop)。若要從工作階段內部結束它，請執行 `/stop`。

#### 在不離開終端機的情況下切換工作階段

在前景執行的工作階段（即您在終端機中啟動、而非從 agent 檢視附加的工作階段）中，在空白提示詞輸入上按 `←` 會將其移至背景，並開啟已選定該列的 agent 檢視，讓您無需離開終端機即可切換工作階段。同樣按一次也會分離已附加的工作階段。

如果您在刪除提示詞輸入的最後一段文字或瀏覽提示詞歷史記錄後立即按 `←`，Claude Code 會要求您確認：第一次按下會顯示 `Press ← again to open agents`，在已附加的工作階段中則顯示 `Press ← again to go back to agents`，第二次按下才會切換。

當 `←` 將前景工作階段移至背景時，agent 檢視會在清單上方顯示 `Your conversation moved to the background`，並已選定該工作階段的列。接著：

* 按 `Enter` 重新開啟對話。
* 按 `Esc` 復原切換並返回對話。如果 `Esc` 顯示 `Still starting — try again in a moment`，表示背景工作階段尚未就緒，請稍後再按一次 `Esc`。
* 按兩次 `Ctrl+C` 以退出到您的 shell。

當 Claude Code 無法重新開啟對話時，它會結束並列印一個可恢復該對話的 `claude --resume` 命令。

[Claude 的任務清單](https://code.claude.com/docs/zh-TW/interactive-mode.md#task-list) 會隨對話移至背景工作階段，因此當您返回該列時，檢查清單會保持完整。

您按下 `←` 的來源列，在您使用方向鍵或滑鼠移動選擇後，名稱仍會保持粗體且不變暗，讓您能分辨自己來自哪個工作階段。

如果您按 `←` 時有工具正在執行，Claude Code 會等待它完成再移至背景，而 Claude 會在背景工作階段中繼續回應。再按一次 `←` 即可立即移至背景而不等待。當進行中的背景工作無法轉移到背景工作階段時，Claude Code 會先顯示 `Background this session?` 對話框，與 [`/background`](#from-inside-a-session) 相同。

約十秒後，Claude Code 會不再等待，直接將工作階段移至背景，但以下這類情況除外：

* **前景 subagent 仍在執行中**：Claude Code 會繼續等待，讓 Claude 啟動的[前景 subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#run-subagents-in-foreground-or-background) 的工作得以延續，並顯示 `Still backgrounding after the current tool`。再按一次 `←` 即可不等待直接轉至背景，這會讓這些 subagent 從頭重新開始。
* **權限提示或問題正在等待您的回答**：當權限提示或 Claude 提出的問題正在等待時，Claude Code 會持續等待並顯示 `Still backgrounding after the current tool — a question is waiting for your answer.` 如果您的回答讓回合得以繼續，例如在權限提示上選擇 **Yes**，Claude Code 會在目前工具完成時將工作階段移至背景。
* **您在提示詞輸入中輸入文字**：Claude Code 會取消切換，因為未發送的文字會留在您終端機的輸入框中，不會移至背景工作階段。它會顯示 `Backgrounding cancelled — you have unsent text in the input. Send it or clear it, then press ← again.` Claude 會繼續在前景工作。
* **您停止了回合**：Claude Code 會取消切換並顯示 `Backgrounding cancelled — the turn was stopped.` 例如，當您 [使用 `Esc` 中斷 Claude](https://code.claude.com/docs/zh-TW/interactive-mode#general-controls)、在主對話的權限提示上 [不附註解](https://code.claude.com/docs/zh-TW/permissions.md#add-a-comment-when-you-answer-a-permission-prompt) 選擇 **No**，或在主對話中對 Claude 提出的問題按 `Esc` 時，回合就會停止。再按一次 `←` 即可將工作階段移至背景。
* **佇列中的訊息無法移動**：您 [在 Claude 工作時加入佇列](https://code.claude.com/docs/zh-TW/interactive-mode.md#queue-messages-while-claude-works) 的訊息會隨對話移至背景工作階段。當其中某則訊息無法移動時，工作階段會留在前景，而 Claude Code 會顯示如 `Cannot open agents — 1 queued message can't move to the background. Press ← again once Claude has read it.` 的通知。

當 Claude Code 將工作階段移至背景時（無論是在約十秒後，還是在您再按一次 `←` 後），它會停止 Claude 仍在前景執行的 shell 命令。Claude Code 不會針對該命令顯示 `Background this session?` 對話框。在背景工作階段中，Claude 沒有該命令曾經啟動的記錄，因此 Claude 可能會再次執行該命令。若要在工作階段移動時讓命令繼續執行，請在 Claude Code 仍在等待時按 `Ctrl+B` [將其轉為背景命令](https://code.claude.com/docs/zh-TW/interactive-mode.md#background-bash-commands)。

即使對話尚無任何訊息，按 `←` 也會建立該工作階段的列，因此 `→` 仍可返回該工作階段。

您可以使用 `/config` 中的 [`leftArrowOpensAgents`](https://code.claude.com/docs/zh-TW/settings-reference#leftarrowopensagents) 設定，為前景工作階段關閉此快捷鍵。

##### 工作階段移至背景時發送的提示詞

如果您在工作階段移至背景的那一刻輸入提示詞或 `!` shell 命令，它會被停止或保持未發送：

* **在對話關閉時發送**：回應或命令會在對話關閉且 agent 檢視開啟時停止
* **當時仍在等待 [hook](https://code.claude.com/docs/zh-TW/hooks.md)**：提示詞不會被發送，且畫面上不會有任何說明。這包括您在 [`SessionStart` hook](https://code.claude.com/docs/zh-TW/hooks#sessionstart) 仍在執行時輸入的提示詞

在這兩種情況下，您輸入的文字都會保留在 [提示詞歷史記錄](https://code.claude.com/docs/zh-TW/interactive-mode.md#command-history) 中。若要再次發送，請開啟已移至背景的工作階段，並在其提示詞輸入上按 `↑` 以取回文字。

### 組織清單

agent 檢視會將工作階段分組，讓需要輸入的工作階段位於頂部，`Ready for review` 和 `Needs input` 位於 `Working` 和 `Completed` 上方。這些群組名稱並非與上述 [狀態](#read-session-state) 一一對應：當工作階段有需要審查或檢查失敗的開啟中 pull request 時，它會移至 `Ready for review`，而 `Completed` 會將已完成、失敗和已停止的工作階段集中在一起。

按 `Ctrl+S` 改為按目錄分組。您的選擇會在多次執行間保留。

在群組內：

* 按 `Ctrl+T` 將工作階段釘選到頂部，並 [在閒置時保持其程序執行](#the-supervisor-process)
* 按 `Shift+↑` 或 `Shift+↓` 重新排序工作階段
* 按 `Ctrl+R` 重新命名工作階段
* 在群組標題上按 `Enter` 以摺疊群組，但 [篩選](#filter-sessions) 啟用時除外，此時所有群組都會保持展開
* 按 `Ctrl+X` 停止工作階段，並在兩秒內再次按 `Ctrl+X` 將其從清單中刪除，或按 `Esc` 關閉確認而不刪除。即使停止嘗試失敗（例如因為 [背景服務沒有回應](#agent-view-says-the-background-service-did-not-respond)），第二次按下仍會刪除工作階段。在這種情況下，確認狀態會再維持兩秒，而刪除動作會自行結束工作階段的程序

在群組標題上按 `Ctrl+X` 會在確認後刪除該群組中的每個工作階段。除了 [刪除工作階段會移除什麼](#what-deleting-a-session-removes) 中說明的保留情況外，刪除會將工作階段從清單中移除。Claude 為其建立的 worktree 會被移除、保留或留在原位，取決於您的刪除方式以及 worktree 中的內容。對話逐字稿保留在您的本機上，可透過 `claude --resume` 取得。

螢幕上放不下的已完成工作階段會摺疊成 `… N more` 列。`Completed` 群組會填滿即時群組之後剩餘的垂直空間。在較矮的終端機上，標題會壓縮成單一摘要行，讓工作中或需要輸入的工作階段保持可見。

#### 找回過去的工作階段

若要找回工作階段，請在 [分派輸入](#dispatch-an-agent-from-agent-view) 中輸入 `/resume`。選擇器會開啟，依最新優先的順序列出您開啟 agent 檢視時所在儲存庫的過去工作階段，包括您已從清單中刪除的工作階段。已有列的工作階段不會列出。按 `Enter` 會將選定的工作階段恢復為背景工作階段，使其以列的形式重新加入清單。

在以下情況下，`/resume` 會失敗並顯示 `isn't available in agent view`：

* `/resume` 指定了 id 或搜尋詞
* 檢視以 `--cwd` 限定範圍
* 檢視以 [`--safe-mode`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 啟動
* 檢視以 `--permission-mode` 或 `--settings` 等旗標開啟

如果您在 `/resume` 後輸入了任何內容，請不帶該內容重新輸入。如果您使用了上述其中一個旗標，請在 shell 中不帶該旗標執行 `claude agents`，然後單獨輸入 `/resume`。

### 篩選工作階段

在分派輸入的開頭使用以下其中一個篩選條件，即可在輸入時縮小清單範圍：

| 篩選 | 顯示 |
| :- | :- |
| `a:<name>` | 執行指定 agent 的工作階段 |
| `s:<state>` | 處於指定狀態的工作階段，例如 `s:working`，或位於指定群組標題下的工作階段，例如代表 `Ready for review` 的 `s:ready`。`s:blocked` 會列出所有正在等待您的項目 |
| `n:<text>` | 名稱或第一個提示詞包含該文字的工作階段，例如 `n:login`。需要 Claude Code v2.1.287 或更新版本 |
| `o:<text>` | 結果包含該文字的工作階段，例如 `o:merged`。單獨的 `o:` 會列出所有已回報結果的工作階段 |
| Pull request 或 merge request 編號（例如 `#1234`）或其 URL | 正在處理該 pull request 或 merge request 的工作階段 |
| 任何其他 URL | 其第一個提示詞包含該 URL 的工作階段 |

若要組合篩選條件，請以 `a:`、`s:`、`n:` 或 `o:` 開頭，再加上更多條件，以空格分隔。清單會顯示符合所有條件的工作階段。例如，`s:blocked a:reviewer` 會列出正在等待您的 `reviewer` 工作階段。

篩選條件啟用時，您摺疊的群組會展開以顯示符合的項目，並選定一個符合項目，因此按 `Enter` 即可開啟它。清除輸入即可移除篩選條件，這些群組會再次摺疊。

### 鍵盤快捷鍵

在 agent 檢視中按 `?` 即可查看當下情境中的快捷鍵。下表為其摘要。

| 快捷鍵 | 動作 |
| :- | :- |
| `↑` / `↓` | 在列之間移動 |
| `PgUp` / `PgDn` | 向上或向下移動一整個畫面的列 |
| `Home` / `End` | 跳至第一列或最後一列 |
| `Enter` | 附加到選定的工作階段，或在輸入的文字不是 [篩選條件](#filter-sessions) 時提交該文字 |
| `Space` | 開啟或關閉選定工作階段的查看面板 |
| `Shift+Enter` | 在分派輸入中插入新行，[與主提示詞輸入相同](https://code.claude.com/docs/zh-TW/terminal-config.md#enter-multiline-prompts) |
| `Ctrl+Enter` | 分派並立即附加，適用於 `?` 覆蓋層列出 `ctrl+enter to start and open` 的終端機 |
| `→` | 附加到選定的工作階段 |
| `Alt+1`..`Alt+9` | 附加到聚焦工作階段所在目錄中的工作階段 1–9 |
| `Tab` | 在空白輸入上瀏覽所有 subagent。否則套用反白顯示的建議 |
| `Ctrl+S` | 在狀態和目錄之間切換分組方式 |
| `Ctrl+T` | 釘選或取消釘選選定的工作階段 |
| `Ctrl+F` | 使用 [`n:` 篩選條件](#filter-sessions) 依名稱尋找工作階段 |
| `Alt+↑` / `Alt+↓` | 跳至上一個或下一個群組標題 |
| `Ctrl+R` | 重新命名選定的工作階段 |
| `Ctrl+G` | 在您的 `$VISUAL` 或 `$EDITOR` 中開啟分派提示詞 |
| `Ctrl+J` | 在分派輸入中插入新行 |
| `Ctrl+X` | 停止工作階段；在兩秒內再次按下以刪除它 |
| `Shift+↑` / `Shift+↓` | 重新排序選定的工作階段 |
| `Esc` | 關閉查看面板、清除輸入或退出。當您是透過 `←` 將工作階段移至背景而開啟 agent 檢視時，最後一次 `Esc` 會返回該對話而不是退出。啟用 [vim 編輯器模式](https://code.claude.com/docs/zh-TW/interactive-mode.md#vim-editor-mode) 時，在輸入中按 `Esc` 會從 INSERT 切換到 NORMAL 模式並保留您的文字，與主提示詞輸入相同 |
| `Ctrl+C` | 清除輸入；按兩次以退出。當畫面上有選取的文字時，按下會改為清除選取；除非 [選取時已複製](https://code.claude.com/docs/zh-TW/settings-reference.md#copyonselect)，否則會先複製該文字 |
| `?` | 顯示快捷鍵 |

在 [`Agents` 情境](https://code.claude.com/docs/zh-TW/keybindings#agents-actions) 中具有動作的快捷鍵會遵循您的 [`keybindings.json`](https://code.claude.com/docs/zh-TW/keybindings)。`Ctrl+G` 也是如此，透過 `Chat` 情境的 `chat:externalEditor` 繫結。

## 分派新 agent

您可以從 agent view 分派新的背景工作階段、將現有的互動式工作階段傳送或複製到背景，或直接從 shell 啟動一個。

### 從 agent view 分派 agent

在 agent view 底部的輸入框中輸入提示詞，然後按 `Enter` 即可啟動新的背景工作階段。工作階段會根據提示詞自動命名；稍後可以使用 `Ctrl+R` 重新命名。

自動名稱是由 [Haiku 等級模型](https://code.claude.com/docs/zh-TW/model-config.md)撰寫的簡短標籤。工作階段之後取得的名稱也會顯示在其列上，包括當您在該工作階段中[接受計畫](https://code.claude.com/docs/zh-TW/permission-modes.md#review-and-approve-a-plan)時，工作階段取得的[產生標題](https://code.claude.com/docs/zh-TW/sessions.md#name-your-sessions)。

將圖片貼上到提示詞中，即可隨任務附上螢幕截圖或圖表。

貼上的文字超過 800 個字元或超過三行時，會摺疊為 `[Pasted text #N]` 預留位置，讓輸入保持在一行；完整文字會在您分派時送出。若要在分派前檢查或編輯摺疊的文字，請再次貼上相同的文字，預留位置就會展開回輸入框中。

為提示詞的部分內容加上前綴或提及，以控制工作階段的啟動方式：

| 輸入 | 效果 |
| :- | :- |
| `<agent-name> <prompt>` | 如果第一個單字與自訂 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 名稱相符，該 subagent 會以其 frontmatter 中的設定作為工作階段的主 agent 執行 |
| `@<agent-name>` | 在提示詞中的任何位置提及自訂 subagent，以將其作為主 agent 執行 |
| `@<repo>` | 提及儲存庫以在該處執行工作階段。關於會列出哪些儲存庫，請參閱[分派到特定目錄](#dispatch-to-a-specific-directory) |
| `/<command>` | 建議可作為提示詞分派的 [skill](https://code.claude.com/docs/zh-TW/skills.md) 和[命令](https://code.claude.com/docs/zh-TW/commands.md) |
| `! <command>` | 將 shell 命令作為背景工作執行，而不是啟動 Claude 工作階段。該工作會顯示為一列，您可以附加、觀看及分離 |
| `#<number>` 或 pull request 或 merge request URL | 如果已有工作階段正在處理該 pull request 或 merge request，Claude Code 會選取其列，而不是分派新的工作階段 |

有一小組命令會在 agent view 本身中執行，而不是分派：

* `/exit` 和 `/quit` 會關閉 agent view
* `/logout` 會將您登出
* `/model`、`/effort` 和 `/fast` 會設定[您接下來分派的工作階段的啟動方式](#set-the-model-effort-and-fast-mode)。`/effort` 和 `/fast` 需要 Claude Code v2.1.299 或更新版本。
* `/login` 會開啟登入對話框，讓您無需附加到工作階段即可重新登入
* 單獨的 `/resume` 或其別名 `/continue` 會開啟儲存庫過去工作階段的選擇器，以將其作為背景工作階段[帶回](#bring-back-a-past-session)

Skill、您自己的命令，以及會展開提示詞的內建命令（例如 `/init`）會作為第一個提示詞傳送到新的背景工作階段。提示 `isn't available in agent view` 表示您輸入的內建命令並未執行。若要執行它，請[附加到工作階段](#attach-to-a-session)並在該處輸入。您輸入的所有內容都會保留在該提示旁的輸入框中，以便您編輯。

將重複性任務打包為 [skill](https://code.claude.com/docs/zh-TW/skills.md)，可讓您從 agent view 重複啟動相同的工作流程，而無需重新輸入提示詞。

當相同的 `@name` 同時與 subagent 和同層級的儲存庫相符時，subagent 優先。不帶 `@` 的第一個單字比對也同樣適用，因此剛好以您某個 subagent 名稱開頭的提示詞會分派該 subagent，而不是將該單字視為純文字。若要明確指定，請使用 `@` 形式，或以不同的單字開頭提示詞以避免比對。

#### 分派到特定目錄

新工作階段會在您開啟 agent view 的目錄中執行。若要以不同的目錄為目標，請使用以下任一方法：

* 在該目錄中開啟 `claude agents`。
* 在父目錄中開啟 `claude agents`，並在提示詞中使用 `@<repo>` 提及子儲存庫。輸入 `@` 會列出以下目標：

  * 啟動目錄下一層的 Git 儲存庫
  * 您啟動所在的儲存庫中，位於其目錄樹內的已註冊 [git worktree](https://code.claude.com/docs/zh-TW/worktrees.md)，例如 Claude 在 `.claude/worktrees/` 下建立的 worktree，並標示其簽出的分支。在儲存庫外新增的 worktree（例如使用 `git worktree add ../feature`）不會列出
  * 清單中已有工作階段的任何目錄

  名稱包含空格的目錄不會列出。
* 從 shell 中，`cd` 進入該目錄並執行 `claude --bg "<prompt>"`。

當 agent view 依目錄分組時，分派會將提示詞傳送到所選列的目錄，因此您可以選取一個群組並分派到其中，而無需重新輸入路徑。

### 將工作階段傳送或複製到背景

有兩個命令可將工作從您所在的工作階段移到背景：`/background` 會將目前的對話傳送到背景並釋放您的終端機，而 `/fork` 會傳送一份副本，讓您在原處繼續工作。

#### 將工作階段傳送到背景

執行 `/background` 或其別名 `/bg`，可將目前的對話移到背景工作階段。傳遞提示詞（例如 `/bg run the test suite and fix any failures`）可先再給一個指令。如果您執行 `/bg` 時 Claude 正在回應，該回應會在背景工作階段中繼續。

如果您在某些類型的背景工作（例如 subagent 或工作流程）仍在執行時結束工作階段，`Background work is running` 對話框會警告這些工作將會停止。選擇 `Move to background and exit` 即可以與 `/background` 相同的方式將工作階段移到背景，並返回您的 shell。當 agent view [已關閉](#turn-off-agent-view)時，不會顯示此選項。

如果清單上已有背景工作階段使用該對話的名稱，Claude Code 會為新列的名稱加上編號，例如 `my-session (2)`，並保留現有列的名稱不變。若要重新命名新列，請在 agent view 中選取它並按 `Ctrl+R`。

#### 使用 /fork 複製工作階段

執行 `/fork` 可將目前的對話複製到新的背景工作階段，同時原始工作階段繼續執行。副本會以截至該時間點的對話中所有內容開始；關於副本在何處執行，請參閱下方的項目。它也會帶入模型、權限模式、effort 等級，以及您在工作階段期間新增的任何目錄或「不再詢問」權限授予。副本會在 agent view 中顯示為獨立的一列。

fork 之後，兩個對話彼此獨立：副本所做的任何事都不會自行進入原始對話，但在啟用[跨工作階段訊息](https://code.claude.com/docs/zh-TW/cross-session-messaging.md)的工作階段中，任一工作階段的 Claude 都可以明確地傳訊息給另一方。

當 [agent view 已關閉](#turn-off-agent-view)時，`/fork` 會啟動[分叉的 subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#fork-the-current-conversation)，而不是複製工作階段。

##### 向副本提供提示詞並開啟其工作階段

傳遞提示詞（例如 `/fork open a draft pull request with the work so far`），副本會立即開始處理。若未提供提示詞，副本會等待其第一個指令：在 `claude agents` 中選取其列並按 `Space` 傳送一個指令，或執行 `claude attach <id>`。在等待期間，所選列會顯示 `space to send it a prompt`。

`/fork` 的確認訊息為一行，顯示副本的狀態（例如 `session running`）、其 agent view 列的名稱，以及供 `claude attach` 使用的工作階段 ID。點擊名稱即可切換到副本：此工作階段會移到背景（與按 `←` 相同），並由 agent view 開啟副本的工作階段。

##### 副本的執行位置

除非副本[就地編輯](#how-file-edits-are-isolated)，否則 Claude Code 會指示它在進行程式碼變更前先建立自己的 worktree。在 git 儲存庫外，只有從 hook 建立的 worktree 移出的副本才會收到此指示；若沒有 [`WorktreeCreate` hook](https://code.claude.com/docs/zh-TW/hooks#worktreecreate)，副本會就地編輯。從您的 worktree 移出的副本也會被告知絕不可編輯、在其中執行命令或進入該 worktree，無論隔離設定為何。

副本的起始位置取決於目前工作階段的執行位置：

* 與任何分派的工作階段一樣，副本會[在編輯檔案前移到自己的 worktree](#how-file-edits-are-isolated)。在此情況下，確認訊息不會提及副本的執行位置。
* 當您的工作階段在啟動後移入其連結的 [worktree](https://code.claude.com/docs/zh-TW/worktrees.md) 時，副本會從工作階段移動前的位置開始，並且除非它[就地編輯](#how-file-edits-are-isolated)，否則會在該處以自己的 worktree 進行程式碼變更。當您的 worktree 簽出在某個分支上時，該指示也會告訴任務建立在您的工作之上的副本，以您的分支作為其新分支的基礎，因為您的分支會持續在您的 worktree 中簽出。確認訊息以 `runs in the origin tree` 結尾。
* 當您在具有主工作樹的儲存庫的連結 worktree 內啟動工作階段時，副本會在該主工作樹中開始，套用相同的「使用自己的 worktree」規則，但沒有分支指示。確認訊息在此也以 `runs in the origin tree` 結尾。
* 在 bare 儲存庫配置的 worktree 內啟動的工作階段沒有可返回的主工作樹，因此副本會留在原處，確認訊息以 `edits this checkout` 結尾。當 worktree 隔離在不位於連結 worktree 內的工作階段中[已關閉](#how-file-edits-are-isolated)時，也會顯示相同的說明，因為副本此時會編輯您開啟的檔案。

##### 無法 fork 的工作階段

使用副本不會繼承的啟動旗標所啟動的工作階段（例如取代的系統提示詞或 `--tools` 允許清單）無法 fork；Claude Code 會說明這一點，而不是建立不完整的副本。從 agent view 分派的工作階段可正常 fork：副本會使用與其來源工作階段相同的 [agent 定義](https://code.claude.com/docs/zh-TW/sub-agents.md)和附加指示啟動。

#### 移到背景時會帶入的內容

當您將工作階段移到背景時，每種進行中的背景工作會轉移到背景工作階段、僅在 Claude 於該處重新啟動它時才繼續，或停止：

* **轉移**：執行中的背景 shell 命令、已移到背景的 subagent、您使用 [`/loop`](https://code.claude.com/docs/zh-TW/scheduled-tasks) 建立的排程任務，以及 Claude [對 artifact 留言的自動回覆](https://code.claude.com/docs/zh-TW/artifacts.md#let-claude-reply-to-comments-on-its-own)，都會在背景工作階段中繼續執行。subagent 會與它啟動的所有內容一起移動，因此只有當所有這些工作都能移動時，它才會轉移。
* **僅在 Claude 重新啟動時才繼續**：執行中的[動態工作流程](https://code.claude.com/docs/zh-TW/workflows.md)。如果您查看背景工作階段時工作流程尚未繼續，請[要求 Claude 重新啟動它](#dynamic-workflows-when-you-background)。
* **停止**：無法移到背景工作階段的工作，例如執行中的 [monitor](https://code.claude.com/docs/zh-TW/tools-reference.md#monitor-tool)。當有任何此類工作在執行時，Claude Code 會顯示 `Background this session?` 對話框，讓您在它停止工作前確認。擁有 monitor 的背景 subagent 會與該 monitor 一併停止。

進入背景後，工作階段可以啟動新的 subagent、monitor 和背景命令，這些在之後分離和重新附加時都會持續執行。

原始啟動時的設定旗標會傳遞到已移到背景的工作階段，因此其 MCP 伺服器、設定和備援模型仍然有效：

* `--mcp-config` 和 `--strict-mcp-config`
* `--settings`
* `--setting-sources`
* `--add-dir`
* `--plugin-dir`
* `--fallback-model`
* `--allow-dangerously-skip-permissions`

您在工作階段期間使用 [`/add-dir`](https://code.claude.com/docs/zh-TW/permissions#additional-directories-grant-file-access-not-configuration) 新增的目錄也會一併帶入。帶入 `--allow-dangerously-skip-permissions` 會讓 `bypassPermissions` 在已移到背景的工作階段中保持可用，但不會授予任何新的權限：該模式仍需要您已有[接受略過免責聲明](https://code.claude.com/docs/zh-TW/permission-modes.md#skip-all-checks-with-bypasspermissions-mode)的記錄。

##### 移到背景時的動態工作流程

如果[動態工作流程](https://code.claude.com/docs/zh-TW/workflows.md)在您將其工作階段移到背景後尚未繼續，請要求 Claude [重新啟動該工作流程](https://code.claude.com/docs/zh-TW/workflows.md#resume-after-you-leave-the-session)。只有當 Claude 在背景工作階段中重新啟動它時，該次執行才會繼續，且 Claude Code 可能會先要求您核准該次重新啟動。工作階段的對話中會顯示一則通知，說明該工作流程 `could not be resumed`。

當 Claude 重新啟動工作流程時，您將工作階段移到背景時仍在執行的任何 subagent 都會從頭開始，並再次消耗其 token。如果您在仍有 subagent 執行時按 `←` 或執行 `/background`，`Background this session?` 對話框會說明有多少個。若要讓它們先完成，請選擇 `Stay`。

### 從您的 shell 分派 agent

傳遞 `--bg` 或其完整形式 `--background`，即可啟動直接進入背景的工作階段：

```bash theme={null}
claude --bg "investigate the flaky SettingsChangeDetector test"
```

提示詞是位置引數，而不是 `-p` 的值。Claude Code 會在建立任何工作階段之前拒絕 `--bg` 與 `-p` 或 `--print` 的組合，因為 `--print` 永遠不會啟動 `claude agents` 所附加的互動式工作階段。

如果您從終端機在尚未[信任](https://code.claude.com/docs/zh-TW/permissions.md#project-allow-rules-and-workspace-trust)的目錄中執行 `claude --bg`，會先出現工作區信任對話框，並在您接受後啟動工作階段。如果您拒絕，Claude Code 會結束而不啟動工作階段。在無法顯示對話框的情況下（例如在指令碼中），命令會改以 [`Workspace not trusted`](https://code.claude.com/docs/zh-TW/errors#workspace-not-trusted-when-dispatching-a-background-session) 錯誤結束。

若要將您已定義的特定 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md)（例如 `code-reviewer`）作為工作階段的主 agent 執行，請將 `--bg` 與 `--agent` 結合使用：

```bash theme={null}
claude --agent code-reviewer --bg "address review comments on PR 1234"
```

如果名稱與您的任何 subagent 都不相符，啟動會失敗：Claude Code 會印出 `no agent named` 警告，並仍將工作階段回報為已移到背景，但工作階段會立即以 `--agent '<name>' not found` 錯誤結束。

當已移到背景的工作階段之後繼續或重新啟動時，Claude Code 會還原該 agent 及其工具限制；關於其系統提示詞，請參閱[繼續的對話中的系統提示詞旗標](https://code.claude.com/docs/zh-TW/cli-reference.md#system-prompt-flags-in-resumed-conversations)。只要您已[信任該工作區](https://code.claude.com/docs/zh-TW/permissions.md#project-allow-rules-and-workspace-trust)，它會先在工作階段自己的目錄中搜尋該 agent，因此從其他目錄繼續工作階段時，專案範圍的 agent 仍會載入。如果該 agent 已不存在，工作階段會以預設工具繼續，且其逐字稿開頭會顯示[指出該 agent 名稱的警告](https://code.claude.com/docs/zh-TW/errors.md#session-agent-no-longer-available)。

若要在背景中繼續現有的對話，請使用 `--resume` 傳遞其完整的工作階段 ID：

```bash theme={null}
claude --resume 1f0e2c9a-6d0b-4c11-9f39-2a77c1d4e8b5 --bg "pick up where you left off and finish the migration"
```

在 Claude Code v2.1.257 或更新版本中，Claude Code 會以相同的 ID 繼續該工作階段，或以新的 ID 啟動副本，並印出一行 `note:` 說明為何無法就地繼續。當工作階段就地繼續時，`claude agents` 只會為其顯示一列。

當您將 `--bg` 與 `--continue`、單獨的 `--resume`，或帶有名稱或檔案路徑的 `--resume` 結合使用時，Claude Code 一律會啟動這樣的副本。新增 `--fork-session` 可刻意啟動副本，且不會顯示該說明。

傳遞 `--name` 可在 agent view 中設定工作階段的顯示名稱，取代自動產生的名稱：

```bash theme={null}
claude --bg --name "flaky-test-fix" "investigate the flaky SettingsChangeDetector test"
```

移到背景後，Claude 會印出工作階段的短 ID 以及管理它的命令。當承載背景工作階段的服務尚未執行時，`--bg` 可能會先在此輸出上方印出 `Starting background service…`。當您傳遞 `--name` 時，名稱會顯示在短 ID 之後：

```text theme={null}
backgrounded · 7c5dcf5d · flaky-test-fix
  claude agents             list sessions
  claude attach 7c5dcf5d    open in this terminal
  claude logs 7c5dcf5d      show recent output
  claude stop 7c5dcf5d      stop this session
```

#### 包含 `--bg` 的提示詞

提及 `--bg` 或 `--background` 的提示詞會按您輸入的原樣傳送，您傳送給背景工作階段的 `--bg` 回覆也是如此。例如，以下命令會啟動一個背景工作階段，而第二個 `--bg` 是其提示詞的一部分：

```bash theme={null}
claude --bg "find out why --bg sessions are slow to start on this machine"
```

Claude Code 只有在旗標可以出現的位置，才會將整個引數讀取為旗標：位於任何單獨的 `--` 分隔符號之前，且不在另一個旗標預期其值的位置。請將旗標放在最前面，如 `claude --bg "<prompt>"`。

當位置不明確時（例如在一連串合併的短旗標之後），Claude Code 不會啟動任何內容，而是改以 [`Couldn't tell whether --bg is a flag or text here`](https://code.claude.com/docs/zh-TW/errors#couldnt-tell-whether-bg-is-a-flag-or-text) 結束。

#### 執行 shell 命令

若要將 shell 命令作為背景工作執行，而不是 Claude 工作階段，請傳遞 `--exec`。以下範例將 `pytest -x` 作為背景工作執行：

```bash theme={null}
claude --bg --exec 'pytest -x'
```

在 agent view 中，於分派輸入的第一個字元輸入 `!` 即可分派相同類型的工作：`!` 會顯示為前綴，其後的所有內容即為命令，按 `Enter` 即可啟動工作。

該命令會以 PTY 支援的工作執行，並在 agent view 中顯示為一列，以最近一行輸出作為其狀態。shell 工作會以該命令取代 Claude 執行，因此不會呼叫任何模型，輸出也不會傳送到任何工作階段。

若要查看輸出，請附加到該列、按 `Space` 在不附加的情況下預覽，或從您的 shell 執行 `claude logs <id>`。擷取的輸出保留在記憶體中，不會寫入磁碟。該列及其輸出會在命令結束約五分鐘後自動清除，因此如果您需要結果，請在此之前讀取。

### 檔案編輯如何隔離

當您從 agent view 分派背景工作階段或使用 `claude --bg` 啟動時，工作階段會在您的工作目錄中啟動。在編輯檔案前，Claude 會將工作階段移到 `.claude/worktrees/` 下隔離的 [git worktree](https://code.claude.com/docs/zh-TW/worktrees.md)，因此平行的工作階段可以讀取相同的簽出，但各自寫入自己的 worktree。一旦工作階段進入其 worktree，Claude Code 就會為該工作階段及其產生的任何 subagent [強制執行 worktree 隔離](https://code.claude.com/docs/zh-TW/worktrees.md#how-claude-code-enforces-isolation)。

Claude 在以下情況會略過 worktree：

* 您使用 `←` 或 `/background` [將已開啟的工作階段移到背景](#from-inside-a-session)。該工作階段會繼續在原本工作的位置編輯檔案
* 工作階段已位於連結的 git worktree 內，無論是 Claude 在 `.claude/worktrees/` 下建立的，還是您使用 `git worktree add` 在其他位置建立的
* Claude 正在編輯的檔案位於連結的 git worktree 內，例如工作階段或其 subagent 使用 `git worktree add` 建立的 worktree
* 工作目錄不是 git 儲存庫，且未設定 [`WorktreeCreate` hook](https://code.claude.com/docs/zh-TW/hooks#worktreecreate)
* 寫入位置在工作目錄之外

若要為不適合使用 git worktree 的儲存庫關閉 worktree 隔離，請將 [`worktree.bgIsolation`](https://code.claude.com/docs/zh-TW/settings-reference#worktree-bgisolation) 設定為 `"none"`。背景工作階段接著會直接編輯您的工作副本，而不會先移入 worktree。將此設定新增到專案的 `.claude/settings.json`：

```json theme={null}
{
  "worktree": {
    "bgIsolation": "none"
  }
}
```

在 git 儲存庫外，工作階段會直接寫入工作目錄，彼此之間沒有隔離，因此請避免分派會編輯相同檔案的平行工作階段。如果您使用其他版本控制系統，請設定 [`WorktreeCreate` hook](https://code.claude.com/docs/zh-TW/worktrees#non-git-version-control)，Claude 就會以與 git 相同的方式隔離編輯。

當 hook 在非 git 儲存庫的目錄中失敗時，Claude 會略過該目錄的隔離，並就地編輯工作目錄。在 git 儲存庫內，Claude 會在編輯前移入 worktree 的工作階段，在該移動發生之前無法對共用簽出使用 `Edit`、`Write` 或 `NotebookEdit` 工具。

若要找到工作階段的 worktree 路徑，請附加並檢查其工作目錄。

背景工作階段產生的 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 會繼承工作階段的工作目錄。一旦工作階段位於 worktree 中，subagent 的檔案編輯就會寫入該 worktree，而不是您的工作副本。若要改為給 subagent 其自己獨立的 worktree，請在其 frontmatter 中設定 [`isolation: worktree`](https://code.claude.com/docs/zh-TW/sub-agents#supported-frontmatter-fields)，或在產生它時傳遞 `isolation: "worktree"`。

當背景工作階段在 Claude 進入的 worktree 中進行了程式碼變更時，Claude Code 會指示 Claude 在完成前保留工作，使其在您刪除工作階段及其 worktree 後仍能保存：

* **提交並推送**：Claude 會不經詢問直接提交，並在儲存庫有遠端時推送分支。
* **草稿 pull request**：當任務需要時，Claude 會開啟一個，且[`#N` 標籤](#pull-request-status)會顯示在該列上。
* **絕不**：推送到 `main` 或 `master`、強制推送及合併。
* **您的 git 指示優先**：如果任務、`CLAUDE.md` 或[記憶](https://code.claude.com/docs/zh-TW/memory.md)表示由您自行處理提交或推送，Claude 會將 git 操作留給您。

編輯並非由自己隔離的簽出的工作階段，在提交或切換分支前仍會詢問。這適用於隔離設定為 `"none"`、worktree 移動失敗，或工作階段在已存在的 worktree 內啟動的情況。

無論任務為何，Claude 都會以一份報告結束工作，說明它做了什麼以及工作位於何處：路徑、分支、pull request，或答案本身。

#### 刪除工作階段會移除什麼

在 [agent view](#organize-the-list) 中按兩次 `Ctrl+X`，或使用 [`claude rm`](#manage-sessions-from-the-shell) 刪除工作階段。除了下方保留的情況外，工作階段會從清單中移除。其逐字稿會透過 `claude --resume` 保留在您的電腦上，且移除在 supervisor 重新啟動後仍然有效。

Claude 為工作階段建立的 worktree 會如何處理：

* Agent view 會移除它，包括未提交的變更，因此請先提交您想保留的內容。
* `claude rm` 在它有未提交的變更時會保留它，連同工作階段列一起保留。
* 當另一個執行中的工作階段正在使用或已鎖定某個 worktree 時，agent view 和 `claude rm` 都不會移除它，再次刪除也不會改變這一點。Claude Code 會保留 worktree 和工作階段，並指出保留的目錄及原因；在 agent view 中，工作階段的列會顯示 `not deleted`。請關閉另一個工作階段，然後再次刪除。
* 當您刪除的工作階段，其 worktree 有 Claude Code 無法確認已保存在其他地方的提交時，Claude Code 會保留 worktree 和工作階段，且訊息會指出 worktree 的分支以及有多少提交尚未推送。訊息也會提供兩種後續做法：推送提交，或再次刪除以捨棄它們。

  遠端上的提交不會阻擋刪除。位於您 `origin` 遠端預設分支之本機副本上的提交也不會，前提是該分支已在您的主簽出中簽出，也就是儲存庫目錄本身，而不是 worktree。

  在該拒絕之後，您可以選擇：

  * 若要保留提交，請推送它們，或將它們合併到該預設分支，然後再次刪除工作階段。
  * 若要捨棄它們，請在不推送的情況下再次刪除工作階段：在 agent view 中於其列上按兩次 `Ctrl+X`，或執行拒絕訊息所印出的 `claude rm <id> --discard-unpushed` 命令。這會移除工作階段和 worktree 及其分支，捨棄未推送的提交和任何未提交的變更。

  當您再次刪除時，Claude Code 只會捨棄拒絕訊息所顯示的內容：如果 worktree 在此之後新增了提交，Claude Code 會再次保留它並顯示更新後的狀態。

  當另一個已完成工作階段的記錄也指向該 worktree 時，您再次刪除時它仍會保留；請推送提交，然後再次刪除。
* git 已無法辨識的 worktree（例如在 `git worktree prune` 之後）不會阻擋刪除。Claude Code 會刪除工作階段，並將目錄留在磁碟上。
* 當 git 或您的 [`WorktreeRemove` hook](https://code.claude.com/docs/zh-TW/hooks#worktreeremove) 無法移除 worktree 時，Claude Code 會保留 worktree 和工作階段，且訊息會指出原因。若是 hook，訊息會說明其結束方式（例如 `exited 1`），並引用其 stderr 的開頭。訊息也會告訴您接下來可以執行以下哪一項：

  * 再次刪除工作階段以強制移除目錄，方法是在 agent view 中於其列上按兩次 `Ctrl+X`，或執行 `claude rm` 拒絕訊息所印出的 `claude rm <id> --force-remove-worktree <worktree-id>` 命令。worktree 的分支會保留在儲存庫中。

    只有在 Claude Code 能確認以下所有條件時，才會提供此選項：

    * 該目錄是儲存庫在 `.claude/worktrees/` 下的連結 worktree 之一
    * worktree 及已簽出的 submodule 對追蹤檔案都沒有未提交的變更
    * 沒有其他工作階段的記錄指向它

    當 Claude Code 無法驗證 submodule 簽出的狀態時（例如已被獨立 git 儲存庫取代的 submodule），也不會提供此選項。
  * 修正造成阻礙的問題，例如提交或 stash 未提交的變更、將獨立的 git 儲存庫移出 worktree、關閉正在使用該目錄的任何程式，或修正 hook，然後再次刪除工作階段。
  * 自行移除目錄，然後再次刪除工作階段。

您自己建立並在其中啟動工作階段的 worktree，無論哪種情況都會保留在原處。

worktree 目錄不屬於任何 git 儲存庫的工作階段（因為儲存庫已被刪除，或 [`WorktreeCreate` hook](https://code.claude.com/docs/zh-TW/hooks#worktreecreate) 在其他位置建立了該目錄）仍然可以刪除。當目錄中仍有檔案時：

* Agent view 在捨棄它們之前，會要求相同的 `Ctrl+X` 連按兩次。對於 hook 建立的目錄，它會改為執行您的 [`WorktreeRemove` hook](https://code.claude.com/docs/zh-TW/hooks#worktreeremove)，若沒有該 hook，則會拒絕刪除並保留工作階段。
* `claude rm` 會保留工作階段和 worktree，並指出原因。

無論哪種方式，都會保留另一個已完成工作階段的記錄所指向的目錄。

### 設定模型、effort 與快速模式

在 agent view 中，於[分派輸入框](#dispatch-an-agent-from-agent-view)中輸入 `/model`、`/effort` 或 `/fast` 並按 `Enter`，之後您分派的工作階段就會以您設定的內容啟動。您的選擇會保留在該 agent view 視窗中，不會儲存到設定檔。`/effort` 和 `/fast` 需要 Claude Code v2.1.299 或更新版本，不接任何內容而單獨輸入的 `/model` 也是如此。

在命令後提供值，或單獨輸入命令以從清單中選擇一個：

* **模型**：`/model <name>`，例如 `/model opus`
* **[Effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)**：`/effort` 搭配 `low`、`medium`、`high`、`xhigh` 或 `max`，例如 `/effort high`。若要以 [ultracode](https://code.claude.com/docs/zh-TW/workflows.md#let-claude-decide-with-ultracode) 啟動工作階段，請改為從您的 shell 使用 [`claude agents --effort ultracode`](#dispatch-defaults) 開啟 agent view；分派輸入框不接受 `/effort ultracode`
* **快速模式**：`/fast on` 或 `/fast off`。只有在快速模式[可供您使用](https://code.claude.com/docs/zh-TW/fast-mode.md#requirements)且其模型支援快速模式時，工作階段才會以快速模式啟動。在不支援的模型上，工作階段會以關閉快速模式的狀態啟動，因此請先使用 `/model` 挑選一個[支援快速模式的模型](https://code.claude.com/docs/zh-TW/fast-mode.md)。確認新工作階段是否取得快速模式的是輸入框下方的提示，而不是標頭。

若要復原選擇，請以 `default` 作為值，例如 `/effort default`。

以下範例在 Opus 上分派一個工作階段，接著在 Sonnet 上分派下一個：

```text theme={null}
/model opus
refactor auth
/model sonnet
run the test suite
```

每個背景工作階段都可以使用不同的模型執行。若要為單一工作階段覆寫模型：

* 從 shell 中，搭配 `claude --bg` 傳遞 `--model`。
* 附加到執行中的工作階段並執行 `/model` 進行切換。從選擇器中挑選，或輸入 `/model <name>`，都會儲存為您新工作階段的預設值，除非您在選擇器中按 `s` 進行僅限此工作階段的切換。如果工作階段被重新產生，僅限此工作階段的切換仍會保留。
* 以其名稱開頭提示詞或提及 `@name`，分派其 frontmatter 設定了 `model` 的 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md)。當分派輸入框中的 `/model` 選擇生效時，不會使用該 subagent 的 `model`，因此請在該處輸入 `/model default`。如果您是以 [`claude agents --model`](#dispatch-defaults) 啟動，也不會使用該 subagent 的模型，因此請在 shell 中不帶 `--model` 執行 `claude agents`。

### 權限模式、模型與 effort

背景工作階段會依據分派的位置和方式，取得其設定、供應商、權限模式、模型和 effort。以下各小節說明每個來源，以及 supervisor 重新啟動工作階段時會保留的內容。

#### 設定與供應商

背景工作階段會從其執行所在的目錄讀取[設定](https://code.claude.com/docs/zh-TW/settings.md)，就如同您在該處以[它帶入的設定旗標](#what-carries-over-when-you-background)啟動 `claude` 一樣。這包括專案設定中的 [`env` 值](https://code.claude.com/docs/zh-TW/settings-reference#env)，因此在該處設定的 `ANTHROPIC_MODEL` 或供應商變數會套用到該目錄中的每個背景工作階段。

背景工作階段也會以您分派它的 shell 的 `PATH` 執行，因此它執行的命令會找到與您終端機相同的工具。它也會保留該 shell 的雲端供應商選擇，例如 `CLAUDE_CODE_USE_BEDROCK` 或 `CLAUDE_CODE_USE_VERTEX`，以及其 `ANTHROPIC_DEFAULT_*_MODEL` 別名和您在該處匯出的任何 [`CLAUDE_CODE_EXTRA_BODY`](https://code.claude.com/docs/zh-TW/env-vars) 覆寫。

#### LLM 閘道

如果您透過 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)路由 Claude Code，請將閘道變數放在設定檔的 `env` 區塊中，而不是在 shell 中匯出，背景工作階段就會連同其餘設定一起讀取它們。[在設定檔中設定](https://code.claude.com/docs/zh-TW/llm-gateway-connect.md#set-in-a-settings-file)會顯示該區塊，以及憑證應使用哪個設定檔。

如果您改為只在 shell 中匯出閘道的 `ANTHROPIC_BASE_URL`，它連同您一起匯出的 `ANTHROPIC_CUSTOM_HEADERS` 和憑證，只有在 [supervisor](#the-supervisor-process) 本身是從匯出相同閘道的 shell 啟動時，且僅在以下情況下，才會傳到背景工作階段：

* 您使用 `←` 或 `/background` 將自己的工作階段移到背景
* 您將工作階段分派到您所在的目錄
* 您透過附加或回覆，喚醒您所在目錄中已停止的工作階段
* 您使用 [`claude respawn`](#manage-sessions-from-the-shell) 重新啟動您所在目錄中的工作階段

Claude Code 會轉送位於雲端供應商前方的閘道。如果您分派所在的 shell 選擇了該供應商，並匯出其閘道端點及其驗證略過旗標，Claude Code 會在適用於 `ANTHROPIC_BASE_URL` 的條件下，將該端點與旗標組合連同 `ANTHROPIC_CUSTOM_HEADERS` 一起轉送到工作階段。例如，匯出 `CLAUDE_CODE_USE_VERTEX=1` 以及 `ANTHROPIC_VERTEX_BASE_URL` 和 `CLAUDE_CODE_SKIP_VERTEX_AUTH=1`，Claude Code 就會轉送該端點和旗標。

Claude Code 只會將轉送的閘道套用到該工作階段執行中的程序，絕不會將其寫入磁碟。

#### 權限模式

* **使用 `/bg` 或 `←` 移到背景**：Claude Code 會保留工作階段原本的[權限模式](https://code.claude.com/docs/zh-TW/permissions.md)，因此您切換到 `acceptEdits` 或 `auto` 的工作階段在分離後仍維持該模式
* **從在 shell 中啟動的 `claude agents` 分派，或使用 `claude --bg`**：新工作階段會以在該目錄中啟動新 `claude` 工作階段的方式開始，除非您是從以[分派預設值](#dispatch-defaults)開啟的 agent view 分派。[工作階段以哪種權限模式啟動](https://code.claude.com/docs/zh-TW/permission-modes.md#which-mode-a-session-starts-in)列出了順序

對於您從使用 `←` 開啟的 agent view 分派的工作階段，Claude Code 會從以下第一個適用的來源取得權限模式：

1. 目標目錄的 [`permissions.defaultMode`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-defaultmode)。`auto` 和 `bypassPermissions` [只有來自受管設定、`--settings` 檔案或 `~/.claude/settings.json` 時才會生效](https://code.claude.com/docs/zh-TW/settings-reference#permissions-defaultmode)。若專案的 `.claude/settings.json` 或 `.claude/settings.local.json` 中的 `defaultMode` 選擇了比您來源工作階段更寬鬆的模式，Claude Code 會拒絕它。
2. 您來源工作階段的權限模式。

   如果該工作階段處於 `bypassPermissions` 模式，新工作階段可能會改以 Manual 模式啟動，並顯示 `Bypass permissions was requested at launch and ignored` 通知。當您接受略過免責聲明的記錄只存在於 `.claude/settings.local.json` 或 `--settings` 檔案中時，就會發生這種情況。請以 Manual 模式繼續，或[將該接受記錄新增到 `~/.claude/settings.json`](https://code.claude.com/docs/zh-TW/permission-modes#bypass-permissions-ignored-in-a-background-session)。

當 Claude Code 因某個來源的模式過於寬鬆而拒絕時，由清單中的下一個來源決定。例如，如果您從 plan mode 工作階段分派到一個其簽入設定要求 `acceptEdits` 的目錄，新工作階段會以 plan mode 啟動。如果您將該 `defaultMode` 移到 `~/.claude/settings.json`，則無論您來源工作階段的權限模式為何，它都會套用。

寬鬆程度依序為 plan，接著是 Manual 和 `dontAsk`，再來是 `acceptEdits` 和 auto（兩者各自都被視為比對方更寬鬆），最後是 `bypassPermissions`。

#### 分派預設值

若要為您從 agent view 分派的每個工作階段設定預設值，請在開啟它時傳遞 `--permission-mode`、`--model`、`--effort` 或 `--agent` 中的任一個：

```bash theme={null}
claude agents --permission-mode plan --model opus --effort high
```

此處的 `--effort` 接受與[頂層 `--effort` 旗標](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags)相同的值，包括 `ultracode`。

`--agent` 會設定分派提示詞未指定 subagent 時（無論是以 `@name` 或作為第一個單字）所使用的 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md)。如果已設定 [`agent` 設定](https://code.claude.com/docs/zh-TW/settings-reference#agent)，則預設為該設定，否則為內建的通用 `claude` agent。在分派輸入中指定 subagent 會覆寫這兩者。

`claude agents` 也接受 `--dangerously-skip-permissions` 作為 `--permission-mode bypassPermissions` 的簡寫，以及 `--allow-dangerously-skip-permissions`，讓 `bypassPermissions` 出現在每個分派工作階段的 `Shift+Tab` 循環中，但不以該模式啟動。兩者都與[頂層 CLI 旗標](https://code.claude.com/docs/zh-TW/cli-reference.md)一致。

傳遞 `--restricted`，可讓您從此檢視分派的每個工作階段都以[受限模式](https://code.claude.com/docs/zh-TW/cli-reference.md#cli-flags)啟動，如同每個工作階段都是以頂層 `--restricted` 旗標啟動一樣。需要 Claude Code v2.1.248 或更新版本。

目前生效的預設值會顯示在分派輸入框下方的頁尾中。

以 `bypassPermissions` 模式啟動的背景工作階段，需要您已有[接受略過免責聲明](https://code.claude.com/docs/zh-TW/permission-modes.md#skip-all-checks-with-bypasspermissions-mode)的記錄，因為該模式會讓您未監看的工作階段無需核准即可執行動作。將 `--dangerously-skip-permissions` 或 `--permission-mode bypassPermissions` 傳遞給 `claude agents` 時，若您先前未接受過，會顯示相同的免責聲明，接受後會將 `bypassPermissions` 套用到您從此檢視啟動的工作階段。傳遞 `--allow-dangerously-skip-permissions` 也會顯示相同的免責聲明，接受後會讓 `bypassPermissions` 出現在這些工作階段的 `Shift+Tab` 循環中，但不會以該模式啟動它們。

#### 重新啟動後會保留的內容

您為背景工作階段選擇的權限模式、模型和 effort，以及[它帶入的設定旗標](#what-carries-over-when-you-background)，在 supervisor 之後[停止並重新啟動](#the-supervisor-process)其程序時都會保留。您在工作階段中途使用 `/model` 或 `/effort` 變更的模型或 effort 也會保留。

如果工作階段的 effort 是取自您的設定，而不是來自 `--effort` 或 `/effort`，Claude Code 每次為該工作階段啟動程序時都會重新讀取您的設定。在您編輯 `settings.json` 中已儲存的 effort 後，變更會套用到您使用 `←` 或 `/bg` 移到背景的工作階段，以及它們之後的重新啟動。已儲存的 effort 是指 [`effortLevel`](https://code.claude.com/docs/zh-TW/settings-reference#effortlevel) 鍵或 [`modelSettings`](https://code.claude.com/docs/zh-TW/settings-reference#modelsettings) 項目。

Claude Code 也會在該次重新啟動後保留您使用 [`/rename`](https://code.claude.com/docs/zh-TW/commands) 或 `Ctrl+R` 設定的名稱，因此您仍可執行 [`claude --resume <name>`](https://code.claude.com/docs/zh-TW/sessions#name-your-sessions) 來存取該工作階段。

您在附加期間使用 [`Ctrl+S`](https://code.claude.com/docs/zh-TW/interactive-mode#general-controls) 暫存的提示詞也會隨工作階段保留。在工作階段的程序停止或重新啟動後重新開啟它，並按 `Ctrl+S` 即可還原暫存的文字。暫存中貼上的內容在重新啟動後不會保留。

### 設定、外掛與 MCP 伺服器

Agent view 接受與 `claude` 相同的設定旗標，用於載入設定、外掛、MCP 伺服器和額外目錄。Agent view 會將 `--settings`、`--setting-sources` 和 `--plugin-dir` 套用到自身，並將每個設定旗標傳遞給您從它分派的工作階段，因此以這種方式載入的外掛或 MCP 伺服器在這些工作階段中也可使用。

| 旗標 | 效果 |
| :- | :- |
| [`--settings <file-or-json>`](https://code.claude.com/docs/zh-TW/settings) | 覆寫 agent view 和分派工作階段的設定 |
| [`--setting-sources <sources>`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) | 在 agent view 和分派工作階段中，僅載入指定的設定來源 |
| [`--add-dir <path>`](https://code.claude.com/docs/zh-TW/permissions#additional-directories-grant-file-access-not-configuration) | 授予對額外目錄的檔案存取權限 |
| [`--plugin-dir <path>`](https://code.claude.com/docs/zh-TW/plugins/create#load-a-directory-or-archive-for-one-session) | 從本機目錄載入外掛 |
| [`--mcp-config <file-or-json>`](https://code.claude.com/docs/zh-TW/mcp) | 從設定檔或 JSON 字串載入 MCP 伺服器 |
| `--strict-mcp-config` | 僅使用來自 `--mcp-config` 的 MCP 伺服器，忽略其他 MCP 設定。關於此旗標在受管 MCP 檔案下的行為，請參閱[使用 managed-mcp.json 進行獨佔控制](https://code.claude.com/docs/zh-TW/managed-mcp.md#exclusive-control-with-managed-mcp-json) |

每個值各重複一次 `--add-dir`、`--plugin-dir` 或 `--mcp-config`。`claude agents` 不支援以空格分隔的形式，例如 `--add-dir a b c`。

您可以將 `--settings`、`--setting-sources` 和 `--plugin-dir` 放在 `agents` 之前或之後。請將 `--add-dir` 和 `--mcp-config` 放在 `agents` 之後：如果您將其中任一個放在 `agents` 之前，[`claude agents --json`](#manage-sessions-from-the-shell) 會以 `unknown option` 錯誤失敗。

以下範例以設定覆寫和一個額外目錄開啟 agent view：

```bash theme={null}
claude agents --settings ./ci-settings.json --add-dir ../shared-lib
```

`--settings` 接受檔案路徑或內嵌 JSON 字串。檔案路徑必須指向現有的檔案；若檔案不存在，Claude Code 會以 `Settings file not found` 錯誤結束。

## 從 shell 管理工作階段

每個背景工作階段都有一個短 ID，您可以從 shell 使用。當您使用 `claude --bg` 啟動工作階段時會列印該 ID，每個工作階段的 ID 是其在 `~/.claude/jobs/` 下的目錄名稱。這些命令對於指令碼編寫或當您不想開啟 agent view 時很有用。

| 命令 | 目的 |
| :- | :- |
| `claude agents` | 開啟 agent view |
| `claude agents --cwd <path>` | 開啟 agent view，範圍限定於在 `<path>` 下啟動的工作階段 |
| `claude agents --json` | 將工作階段列印為 JSON 陣列並結束。請參閱 [將工作階段列為 JSON](#list-sessions-as-json) |
| `claude attach <id\|name>` | 在此終端機中附加到工作階段 |
| `claude logs <id\|name>` | 列印工作階段的最近輸出 |
| `claude stop <id>` | 停止工作階段。也接受 `claude kill` |
| `claude respawn <id>` | 重新啟動工作階段（執行中或已停止），例如用於採用更新的 Claude Code 二進位檔案。具有已儲存對話的工作階段會繼續該對話 |
| `claude respawn --all` | 重新啟動每個執行中的工作階段，例如一次將所有工作階段移至更新的 Claude Code 二進位檔案 |
| `claude rm <id>` | 從清單中移除工作階段，以及 Claude 為其建立的 worktree（當安全刪除時）；請參閱 [刪除工作階段會移除什麼](#what-deleting-a-session-removes)。對話逐字稿會保留在您的本機上，並可透過 `claude --resume` 繼續使用 |
| `claude rm <id> --discard-unpushed <commit>@<worktree-id>` | 刪除因未推送提交而拒絕刪除的工作階段，捨棄 worktree 及其分支和提交。傳遞拒絕列印的確切值；請參閱 [刪除工作階段會移除什麼](#what-deleting-a-session-removes)。需要 v2.1.260 或更新版本 |
| `claude rm <id> --force-remove-worktree <worktree-id>` | 刪除因 git 或 `WorktreeRemove` hook 無法移除其 worktree 而拒絕刪除的工作階段，無論如何刪除 worktree 目錄並在儲存庫中保留其分支。傳遞拒絕列印的確切值；請參閱 [刪除工作階段會移除什麼](#what-deleting-a-session-removes)。需要 v2.1.268 或更新版本 |
| `claude daemon status` | 列印 [supervisor](#the-supervisor-process) 的狀態、版本、socket 目錄和 worker 計數 |
| `claude daemon logs` | 追蹤 supervisor 的日誌檔案 [`~/.claude/daemon.log`](#where-state-is-stored)，在新行出現時列印出來，直到您按下 `Ctrl+C` |
| `claude daemon stop --any` | 停止 supervisor 程序及其託管的背景工作階段。傳遞 `--keep-workers` 以保持背景工作階段執行中，以便[下一個 supervisor](#the-supervisor-process) 可以重新連接到它們。下一個 `claude agents` 或 `claude --bg` 會啟動全新的 supervisor |

`claude attach` 和 `claude logs` 可以使用工作階段名稱的一部分來取代 ID，例如 `claude logs "auth refactor"`。`claude attach` 僅在工作階段的程序執行中時才能依名稱開啟工作階段，因此若要重新啟動已停止的工作階段，請改為傳遞 ID。傳遞名稱需要 Claude Code v2.1.290 或更新版本。

### 將工作階段列為 JSON

`claude agents --json` 將作用中的工作階段列印為 JSON 陣列並結束：每個即時工作階段，加上仍在執行或被阻止的背景工作階段，即使其程序已結束。新增 `--all` 以同時包含已完成的背景工作階段，並新增 `--cwd <path>` 以將清單限制為在該目錄下啟動的工作階段。

每個項目都描述一個工作階段：

| 欄位 | 出現時機 | 說明 |
| :- | :- | :- |
| `cwd`、`kind`、`startedAt` | 一律 | 工作目錄、`interactive` 或 `background`，以及 Unix 毫秒為單位的開始時間 |
| `id` | 背景工作階段 | 短 ID，可與 `claude attach`、`claude logs` 和 `claude stop` 搭配使用 |
| `state` | 背景工作階段 | `working`、`blocked`、`done`、`failed` 或 `stopped` 之一。請參閱 [從指令碼讀取工作階段狀態](#read-session-state-from-a-script)，了解每個值的含義 |
| `pid`、`status` | 程序執行時 | 程序 ID 和 `busy`、`waiting` 或 `idle` 之一 |
| `waitingFor` | 當 `status` 為 `waiting` 時 | 工作階段被阻止的原因：`permission prompt` 表示需要核准、`input needed` 表示 Claude 的問題或 MCP 伺服器的輸入請求、`sandbox request`、`worker request` 或 `dialog open` |
| `sessionId`、`name` | 設定時 | `sessionId` 是完整的工作階段 UUID，可與 [`claude --resume`](https://code.claude.com/docs/zh-TW/sessions) 搭配使用。互動工作階段的 `name` 是其 [預設顯示名稱](https://code.claude.com/docs/zh-TW/sessions.md#name-your-sessions)，直到您命名工作階段或在其中接受計畫 |

### 從指令碼讀取工作階段狀態

`claude agents --json` 是從 Claude Code 外部讀取工作階段狀態的支援方式，例如從狀態列、排程器或監督背景工作的另一個 Claude 工作階段。輪詢 `claude agents --json --all`，它會持續列出程序已結束的工作階段，並讀取每個項目的 `state`、`status` 和 `waitingFor`。

| `state` | 含義 |
| :- | :- |
| `working` | 正在執行一個回合，或工作階段在其自行驅動的工作步驟之間，例如 [`/loop`](https://code.claude.com/docs/zh-TW/scheduled-tasks) 反覆運算或等待 CI。`status` 會告訴您其程序現在是否為 `busy` |
| `blocked` | 工作階段正在等待您：它提出的問題、權限或沙箱決定、只有您才能清除的錯誤（例如過期的登入），或如果您在沒有提示詞的情況下啟動它，則為其第一個提示詞。當等待是即時程序中開啟的提示時，`waitingFor` 會命名它 |
| `done` | 最後一個回合完成了您要求的內容，工作階段已準備好接收您的下一個提示詞，無論其程序是否仍在執行 |
| `failed`、`stopped` | 工作已因錯誤而結束，或工作階段已停止 |

完成其回合並等待您下一個指令的工作階段讀取 `done`，而不是 `blocked`。`blocked` 一律表示工作階段在繼續之前需要您提供的內容。

`~/.claude/jobs/<id>/` 下的檔案不是穩定的介面。工作階段或其他程式寫入 `state`、`detail`、`tempo` 或 `needs` 的值會在下次更新時被取代。

如果您想讓工作階段用自己的話報告進度，請讓它寫入自己的檔案，例如在 `$CLAUDE_JOB_DIR/tmp` 下，而不是編輯 `state.json`。

## 背景工作階段如何被託管

Claude Code 將 agent view 中列出的每個工作階段視為背景工作階段，無論您目前是否連接到它。相比之下，直接執行 `claude` 啟動的工作階段與該終端機相關聯，並在終端機關閉時結束，除非您[將其發送到背景](#from-inside-a-session)。

要檢查您在哪種工作階段中，請執行 [`/status`](https://code.claude.com/docs/zh-TW/commands)。`Session kind` 列在背景工作階段中顯示 `background job · attached` 或 `background job · unattended`（取決於是否連接了終端機），在任何其他工作階段中顯示 `interactive`。

### 監督程序

監督程序是一個背景服務，執行您的背景工作階段，使其在您關閉 agent view 或終端機後繼續工作。Claude Code 在您第一次背景化工作階段或開啟 agent view 時啟動它，您不需要自己管理它。

每個工作階段都是監督程序下的自己的 Claude Code 程序，該程序發生的情況取決於工作階段的狀態：

* **工作中、暫停在權限提示或其他對話框上，或已連接**：程序保持執行。執行中的 subagent、工作流程或監視器計為工作中，待處理的[工作階段範圍排程任務](https://code.claude.com/docs/zh-TW/scheduled-tasks.md)（例如 `/loop` 喚醒）也是如此。
* **已完成或等待您的下一條訊息，且未連接約一小時**：監督程序停止程序以釋放資源。透過提出問題結束其回合的工作階段計為等待您的下一條訊息。對話保存在磁碟上，下次您連接或回覆時，工作階段從中斷的地方恢復。使用 `Ctrl+T` 釘選工作階段以保持其程序執行。
* **在監督程序執行時意外退出**：監督程序重新啟動程序。結束您自己使用 `←` 或 `/background` 背景化的工作階段（例如使用 `kill`）會將其標記為已停止而不是重新啟動。對於以關閉結束的工作階段，請參閱[工作階段在關閉後顯示為失敗或已停止](#sessions-show-as-failed-after-shutdown)。
* **自動更新後**：監督程序重新啟動自身到新版本，並在背景中移動閒置工作階段。正在工作、等待您或已連接的工作階段不會被中斷。
* **監督程序本身停止**，例如因為其程序從 Claude Code 外部被結束：在 macOS 和 Linux 上，除非新的監督程序在約一分鐘內連接，否則您的工作階段會停止。要啟動新的監督程序，請在 shell 中執行 `claude agents`。超過那一分鐘後，請參閱[在監督程序停止後保持工作階段執行](#keep-sessions-running-after-the-supervisor-stops)。

當工作階段的程序停止或重新啟動時，Claude 在其中啟動的背景 shell 命令和背景 subagent 會轉移到其下一個程序。動態工作流程[只有在 Claude 重新啟動它時才會繼續](#dynamic-workflows-when-you-background)。執行中的監視器和 subagent 啟動的 shell 命令會隨程序停止。如果您刪除工作階段，它轉移的所有內容都會停止。要讓所有內容隨程序停止而不是轉移，請將 [`CLAUDE_CODE_DISABLE_BG_EXIT_HANDOFF`](https://code.claude.com/docs/zh-TW/env-vars#variables) 設定為 `1`。

監督程序及其工作階段使用與您的互動工作階段相同的儲存憑證進行身分驗證。對於哪些設定和 shell 變數到達工作階段（包括 `PATH`），請參閱[設定和提供者](#settings-and-provider)。對於閘道端點，請參閱 [LLM 閘道](#llm-gateway)。

#### 在監督程序停止後保持工作階段執行

如果 agent view 在退出時顯示此通知，表示沒有[監督程序](#the-supervisor-process)正在執行：

```text theme={null}
Background sessions still running will stop in about a minute. Run 'claude agents' to keep them.
```

請在這一分鐘內於 shell 中執行 `claude agents`，以啟動新的監督程序並保持您的工作階段執行。

如果一分鐘先過去，工作階段會停止，但其保存的對話仍保留在磁碟上。要從保存的對話重新啟動工作階段，請[連接](#attach-to-a-session)或[回覆](#peek-and-reply)該工作階段，如[工作階段在關閉後顯示為失敗或已停止](#sessions-show-as-failed-after-shutdown)中所述。

### 狀態存儲位置

工作階段狀態存儲在您的 Claude Code 設定目錄下。如果您設定 [`CLAUDE_CONFIG_DIR`](https://code.claude.com/docs/zh-TW/env-vars)，監督程序改用該目錄而不是 `~/.claude`，並作為具有其自己工作階段的單獨實例執行。

| 路徑 | 內容 |
| :- | :- |
| `~/.claude/daemon.log` | 監督程序日誌 |
| `~/.claude/daemon/roster.json` | 執行中的背景工作階段列表，用於在重新啟動後重新連接 |
| `~/.claude/jobs/<id>/state.json` | 在 agent view 中顯示的每個工作階段狀態。透過 [`claude agents --json`](#read-session-state-from-a-script) 讀取它，而不是解析檔案 |
| `~/.claude/jobs/<id>/tmp/` | 每個工作階段的暫存目錄。Claude 的 `Write` 和 `Edit` 呼叫在此處不會提示權限。工作階段刪除時移除 |

每個背景工作階段都設定了 `CLAUDE_JOB_DIR` 環境變數，指向其 `~/.claude/jobs/<id>` 目錄，因此工作階段執行的 shell 命令可以將臨時檔案寫入 `$CLAUDE_JOB_DIR/tmp`，而不會與平行工作階段衝突。

要在不直接讀取檔案的情況下檢查此狀態，請執行 `claude daemon status`。它報告監督程序是否可達、其程序 ID 和版本、socket 目錄，以及有多少背景工作階段處於活動狀態。

該命令也會在執行中的監督程序版本與您叫用的 `claude` 版本不同時發出警告，這會在監督程序尚未重新啟動到新版本的更新後發生。警告會顯示兩個版本，並告訴您執行 `claude daemon stop --any` 以採用新版本。

工作階段在該版本不匹配時保持完整：較舊的 Claude Code 版本更新工作階段的 `state.json` 時會保留它不識別的欄位，並保持工作階段列出。`roster.json` 中的工作階段列表遵循相同規則，因此由較新版本啟動的工作階段保持可達，並在監督程序重新啟動後繼續接受輸入。

### 關閉 agent view

要完全關閉背景 agent 和 agent view，將 `disableAgentView` [設定](https://code.claude.com/docs/zh-TW/settings.md)設為 `true` 或設定 `CLAUDE_CODE_DISABLE_AGENT_VIEW` 環境變數。管理員可以透過[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)強制執行此操作。

## 疑難排解

### `claude agents` 列出 subagent 而不是開啟 agent view

如果 `claude agents` 列印計數後跟著您設定的 subagent，然後退出，表示 agent view 在您的環境中不可用。執行 `claude update` 以安裝最新版本。

如果更新後 agent view 仍未開啟，請檢查它是否已被設定或環境變數[關閉](#turn-off-agent-view)。

### Agent view 開啟時沒有工作階段

在您分派第一個工作階段之前，agent view 會顯示空的區段標題，每個標題下方有描述，以及輸入框上方有一行說明，代替工作階段清單。在底部的輸入框中輸入提示詞並按 `Enter` 以分派您的第一個工作階段。

### 背景化顯示 `Background this session?` 對話框

當您按 `←` 將工作階段放到背景時，若出現 `Background this session?` 對話框，表示該工作階段有進行中的背景工作，背景化會使其停止、中斷，或在無人看管的情況下繼續執行：

* **無法移動的工作**：工作階段有無法移動到背景工作階段的工作，例如執行中的 [monitor](https://code.claude.com/docs/zh-TW/tools-reference.md#monitor-tool)。對話框會列出 Claude Code 將停止的背景工作，並另外計算會轉移的任務數量。
* **具有執行中 subagent 的工作流程**：[動態工作流程](https://code.claude.com/docs/zh-TW/workflows.md)仍有 subagent 在執行。如果您仍要背景化，這些 subagent 會停止，對話框會說明有多少個。當 Claude [在背景工作階段中重新啟動該工作流程](#dynamic-workflows-when-you-background)時，它們會從頭開始。
* **自動 artifact 回覆**：Claude 正在[自行回覆 artifact 上的評論](https://code.claude.com/docs/zh-TW/artifacts.md#let-claude-reply-to-comments-on-its-own)。這些回覆會在背景工作階段中繼續，對話框也會說明這一點。

執行 `/tasks` 以查看正在執行的所有內容，然後確認仍要背景化，或選擇 `Stay` 讓工作先完成。請參閱[背景化時轉移的內容](#what-carries-over-when-you-background)以了解哪些類型的工作會轉移，哪些會被 Claude Code 停止。

### 對話顯示某個背景 agent `was carried into this session and not resumed`

此通知指出某個未在此工作階段中執行的背景 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md)。

Claude 會看到此通知並自行回覆，因此您不需要提示它。如果在閱讀 Claude 的回覆後仍需要該 subagent 的工作成果，請向 Claude 提出要求。

### 提示詞因過短而被拒絕

分派輸入框期望的是任務描述，而不是對話開場白。短於四個字元的提示詞會被拒絕並顯示 `Too short` 提示，以避免誤觸按鍵啟動工作階段。請描述您希望工作階段執行的操作，例如 `investigate the flaky checkout test`。

### 工作階段在關機後顯示為失敗或停止

關閉或重新啟動您的機器會停止執行中的背景工作階段。等待您輸入的工作階段在您回來時會保留在 `Needs input` 下。對於任何其他執行中的工作階段，agent view 顯示的內容取決於它上次取得進度的時間有多久：

* 在 48 小時內，工作階段顯示為失敗。附加或回覆它，它會從其已儲存的對話重新啟動。若要繼續被中斷的工作，請傳送回覆要求它繼續。
* 超過 48 小時，例如機器關閉數天後，工作階段顯示為停止，並顯示 `ended while the background service was off`。在該列上按 `Enter`，頁尾會顯示 `Press enter again to resume this session (it ended while the background service was off), or ctrl+x to delete it.` 在同一列上再次按 `Enter` 以恢復其已儲存的對話。回覆或 `claude attach <id>` 會在沒有該頁尾提示的情況下恢復它。

當[逐字稿清理](https://code.claude.com/docs/zh-TW/settings-reference.md#cleanupperioddays)已移除停止工作階段的已儲存對話時，Claude Code 會拒絕開啟該列：訊息會說明沒有可恢復的內容。`claude rm <id>` 會刪除該列（上述[保留的情況](#what-deleting-a-session-removes)除外），而 `claude respawn <id>` 會再次執行其原始提示詞。請參閱[此工作階段的已儲存對話已不在磁碟上](https://code.claude.com/docs/zh-TW/errors.md#this-sessions-saved-conversation-is-no-longer-on-disk)。

單純的睡眠不會停止工作階段。工作階段在睡眠期間會被保留，監督程序在喚醒時會重新連接到它們。

### 開啟工作階段時顯示對話已開啟

兩個程序無法寫入同一個逐字稿。當停止工作階段的已儲存對話已在另一個執行中的 Claude Code 程序中開啟時，Claude Code 會拒絕啟動該工作階段自己的程序。您看到的內容取決於持有該對話的是什麼：

* 您恢復對話的終端機，例如使用 `claude --resume` 或 `/resume`：該列顯示 `Open in a terminal`，並提示在那裡繼續，開啟該列會顯示 `Can't open — this session is running in another terminal`。在該終端機中繼續，或退出它並再次開啟該列。
* 另一個非互動式 Claude Code 程序，例如同一對話的背景工作階段程序尚未退出：開啟該列會顯示 `This conversation is already open in another running Claude session`。使用該程序，或等待它退出後再次開啟該列。

Claude Code 會儲存您在被拒絕的嘗試中輸入的回覆（以 `!` 或 `/` 開頭的回覆除外），並在工作階段下次啟動時傳送它。

### 開啟工作階段時顯示它沒有已儲存的逐字稿

當您開啟一個從[另一個對話背景化](#from-inside-a-session)、且在執行自己的回合之前就已停止的工作階段時，Claude Code 會恢復該對話。如果 Claude Code 找不到該對話，則會拒絕開啟該工作階段：

* `claude attach` 會列印 `This session has no saved transcript`。
* Agent view 會在清單下方顯示 `Press enter again to restart this session fresh`。

在同一列上再次按 `Enter` 以使用空對話重新啟動工作階段，或從 shell 執行 `claude respawn <id>`。

請參閱[錯誤參考](https://code.claude.com/docs/zh-TW/errors.md#this-session-has-no-saved-transcript)以取得詳細資訊。

### 終端機主機已終止或工作階段停止回應

[監督程序](#the-supervisor-process)在各自的主機程序中執行每個背景工作階段的終端機。當該程序終止或停止回應時，Claude Code 會顯示原因並提供重新啟動；在兩種情況下，對話都會被儲存，重新啟動會恢復它。[錯誤參考](https://code.claude.com/docs/zh-TW/errors.md#terminal-host-process-died)中列出了完整訊息。

無論是透過 `Enter` 或 `claude attach`，Claude Code 都永遠不會重新啟動執行 [shell 命令](#run-a-shell-command)的列，因為那樣會再次執行該命令；該列的訊息和 `claude attach` 都會說明命令不會再次執行。

### 工作階段在啟動前失敗，並出現 `possibly low memory` 註記

當背景工作階段的程序在完成啟動前退出，且主機記憶體不足時，該列的狀態會說明退出情況並附加 `possibly low memory — free some up and retry`。

該註記是一個假設，而不是已確認的原因。Claude Code 只在程序無聲退出（未寫入錯誤，也未被信號停止）且主機在該時刻回報記憶體不足時才會附加它。當程序在退出前確實寫入了錯誤時，該列會改為顯示該錯誤。

釋放機器上的記憶體，然後附加或回覆該列，監督程序會為工作階段啟動新的程序。當記憶體持續不足時，監督程序也會自行[停止閒置工作階段](#the-supervisor-process)以釋放資源，如果停止其他工作階段沒有釋放任何資源，也會停止閒置的釘選工作階段。

### Agent view 表示背景服務未回應

如果附加、查看或 `claude logs` 回報背景服務未回應，監督程序可能已停滯。停止它並讓下一個 `claude agents` 啟動新的監督程序。若要在重新啟動期間保持背景工作階段執行，請傳遞 `--keep-workers`：

```bash theme={null}
claude daemon stop --any --keep-workers
```

接著在 shell 中執行 `claude agents` 以啟動新的監督程序。在 macOS 和 Linux 上，請在舊的監督程序結束後約一分鐘內執行，否則這些工作階段會[在沒有監督程序的情況下停止](#the-supervisor-process)。如果您看到 `stopped`，但相同的錯誤再次出現，且您使用的是 macOS 或 Linux 上早於 v2.1.300 的 Claude Code，請執行 `claude update`，然後再次執行這兩個命令。

如果停止命令改為列印以下四則訊息之一，表示舊程序並未被停止。請在 shell 中執行對應列所述的動作，然後執行 `claude agents`：

| 訊息包含 | 平台 | 動作 |
| :- | :- | :- |
| `could not be verified as the daemon, so it was not signalled` | 全部 | 找出哪個程式擁有該程序 ID。如果它是您自己的監督程序，請停止它；其他程式則不要處理。然後刪除 `~/.claude/daemon.lock`。 |
| `is still running after SIGKILL` | macOS、Linux | 等待該程序退出。如果它始終未退出，請重新啟動電腦。 |
| `was not sent SIGKILL` | macOS、Linux | 再次執行停止命令。如果程序仍然存在，請使用 `ps -ww -o args= -p <pid>` 檢查：以 `daemon` 啟動的 Claude Code 是監督程序，請執行 `kill -9 <pid>`。其他程序則不要處理；如果之後 `claude agents` 無法啟動監督程序，請刪除 `~/.claude/daemon.lock`。 |
| `supervisor (pid=<pid>) is still running` | Windows | 使用 `taskkill /PID <pid>` 結束該程序 |

### 分派失敗，出現 `Could not resolve authentication method`

如果背景分派失敗並出現 `Could not resolve authentication method`，而互動式工作階段的身分驗證正常，表示接收分派的背景工作程序未取得憑證。背景工作階段從[監督程序](#the-supervisor-process)取得憑證，因此此錯誤表示監督程序本身沒有可用的已儲存憑證。確認您已執行 `/login` 或設定 API 金鑰，然後停止監督程序：

```bash theme={null}
claude daemon stop --any --keep-workers
```

在[約一分鐘](#the-supervisor-process)內，於 shell 中執行 `claude agents` 或 `claude --bg` 以啟動新的監督程序，該程序會讀取您的已儲存憑證。如果您使用環境變數（例如 `ANTHROPIC_API_KEY`）而不是 `/login` 進行身分驗證，請從已設定該變數的 shell 執行下一個命令。

請參閱[錯誤參考](https://code.claude.com/docs/zh-TW/errors.md#could-not-resolve-authentication-method)以取得完整的原因和修復清單。

### 背景工作階段顯示 `No LLM gateway`

如果背景工作階段顯示 [`No LLM gateway`](https://code.claude.com/docs/zh-TW/errors#no-llm-gateway-opened-from-another-folder)，表示它未取得您閘道的 `ANTHROPIC_BASE_URL`，因此其請求會失敗。Claude Code 未提供該設定，是因為您從訊息所指名資料夾以外的目錄分派、喚醒或重新啟動了該工作階段。

例如，當您使用 [`@<repo>`](#dispatch-to-a-specific-directory) 分派到某個儲存庫，或從其他目錄執行 `claude attach` 喚醒已停止的工作階段後，就會看到此訊息。若要讓工作階段使用您的閘道，請依閘道的設定位置選擇對應的修正方式：

* **您在終端機中匯出了閘道**：在已匯出閘道變數的終端機中，`cd` 到訊息所指名的資料夾，並執行訊息中的 [`claude respawn <id>`](#manage-sessions-from-the-shell) 命令。
  * 只有當[監督程序](#the-supervisor-process)本身是從匯出了相同閘道的 shell 啟動時，閘道才會傳遞到工作階段。如果監督程序並非如此啟動，請依照[分派失敗，出現 `Could not resolve authentication method`](#dispatch-fails-with-could-not-resolve-authentication-method) 所述，從您執行 respawn 命令的終端機重新啟動監督程序，然後再次執行該命令。
* **您在專案設定中設定了閘道的專案內使用 agent view**：將 `ANTHROPIC_BASE_URL` 及其憑證放入[設定檔的 `env` 區塊](https://code.claude.com/docs/zh-TW/llm-gateway-connect#set-in-a-settings-file)。請使用 `~/.claude/settings.json`，或工作階段所屬專案中的 `.claude/settings.local.json`，重新產生的工作階段會讀取這兩者。然後在 shell 中從任何目錄執行 [`claude respawn <id>`](#manage-sessions-from-the-shell)，以透過閘道重新啟動此工作階段。

### 背景工作階段無法在 macOS 上讀取 Desktop、Documents 或 Downloads

在 macOS 上，背景工作階段主機作為獨立的程序執行，並與您的終端機分開請求對受保護資料夾的存取權。如果背景工作階段在讀取 `~/Desktop`、`~/Documents`、`~/Downloads` 或其他受保護位置時回報 `Operation not permitted`，請在系統設定中的隱私權與安全性 > 檔案與檔案夾下授予存取權，或為該項目啟用完整磁碟取用權限。

使用原生安裝程式時，該項目會顯示為 Claude Code，授予的權限在更新後會保留。使用其他安裝方法（例如 Homebrew 或 npm）時，該項目會顯示二進位檔路徑，更新後可能需要再次授予。

### 背景工作階段無法在 macOS 上連接到本機網路主機

在 macOS 15 及更新版本上，系統會阻止程序連接到您本機網路上的裝置，直到您授予本機網路權限，因此針對 LAN 位址的命令可能會在背景工作階段中失敗並出現 `connect: no route to host`，即使相同的命令在前景終端機中可以正常運作。背景工作階段中第一個連接到本機網路位址的命令會觸發 Claude Code 的 macOS 本機網路權限提示。授予一次後，這些命令就能像在前景終端機中一樣連接到 LAN 主機。

### 工作階段在附加後回應緩慢

當已完成或正在等待您下一則訊息的工作階段在未附加的狀態下維持約一小時時，監督程序會停止其程序以釋放資源。附加會從中斷的地方啟動新的程序，並在程序重新啟動期間立即切換到該工作階段。正在工作、暫停在權限提示或其他對話框上，或已[釘選](#organize-the-list)的工作階段不會以這種方式停止，因此請使用 `Ctrl+T` 釘選工作階段以保持其回應速度。

程序啟動期間，Claude Code 會以即時工作階段的呈現方式顯示工作階段逐字稿的結尾部分，包含 markdown、醒目顯示的程式碼區塊，以及以暗淡列呈現的工具呼叫，下方為暗淡的提示區域並附有 `Session is starting` 註記。即時工作階段準備好後會立即取代它。

### `.claude/worktrees/` 正在填滿

在 agent view 中刪除工作階段會移除 Claude 為其建立的 worktree，但[某些刪除會保留 worktree 或在磁碟上留下其目錄](#what-deleting-a-session-removes)，因此剩餘目錄可能會累積。Git 不再識別的目錄不會出現在 `git worktree list` 中，因此請手動移除這些目錄。

在專案目錄中使用 `git worktree list` 列出剩餘項目，並使用 `git worktree remove <path>` 逐一移除。請參閱[清理 worktree](https://code.claude.com/docs/zh-TW/worktrees.md#clean-up-worktrees)。

## 限制

Agent view 是研究預覽版本，具有以下限制：

* **速率限制適用**：背景工作階段與互動工作階段一樣消耗您的訂閱使用量，因此並行執行十個代理的使用配額速度快十倍。
* **工作階段是本地的**：背景工作階段在您的機器上執行。它們在睡眠時保留，但如果機器關閉則停止。
* **Claude 建立的 worktrees 在 agent view 中隨工作階段刪除**：在刪除在其自己的 worktree 中編輯檔案的工作階段之前，提交變更。[某些刪除會改為保留 worktree](#what-deleting-a-session-removes)。

## 相關資源

如需了解在平行中執行 Claude 的其他方式，以及在您執行的工作階段之間傳遞發現結果，請參閱：

* [在平行中執行代理](https://code.claude.com/docs/zh-TW/agents.md)：比較 agent view 與 subagents、agent teams 和 worktrees
* [跨工作階段傳訊](https://code.claude.com/docs/zh-TW/cross-session-messaging.md)：讓您的工作階段相互傳遞發現結果
* [Agent teams](https://code.claude.com/docs/zh-TW/agent-teams.md)：協調相互傳遞訊息的多個工作階段
* [在雲端使用 Claude Code](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)：在受管雲環境中執行工作階段，而不是本地執行
* [Projects](https://code.claude.com/docs/zh-TW/claude-projects.md)：讓 Claude 從一個對話協調平行雲工作階段，並告訴您哪些需要您

## 版本歷史

Agent view 在研究預覽期間發展迅速。如果您使用較舊的 Claude Code 版本，本頁上的某些行為可能會有所不同；特別是，`claude agents` 會以 `unknown option` 錯誤拒絕它尚不支援的旗標。下表列出了每個旗標和行為何時新增。

| 版本 | 變更 |
| - | - |
| v2.1.299 | [分派輸入中的 `/effort` 和 `/fast`](#set-the-model-effort-and-fast-mode) 會為您接下來分派的工作階段設定 effort 等級和快速模式。不帶值輸入 `/model`、`/effort` 或 `/fast` 會開啟選擇器。 |
| v2.1.299 | Claude Code 僅在任何單獨的 `--` 分隔符之前、且不在另一個旗標的值中時，才[將 `--bg` 和 `--background` 讀取為旗標](#from-your-shell)，並在位置不明確時拒絕執行，而不是猜測。在此版本之前，內容為 `--bg` 或 `--background` 的提示詞或傳給背景工作階段的回覆可能會被當成旗標。這可能會反覆啟動新的背景工作階段，而不是傳遞該文字。 |
| v2.1.296 | 您在[工作階段移到背景時](#switch-sessions-without-leaving-the-terminal)輸入的提示詞或 `!` shell 命令會被停止或保持未傳送，其文字會保留在提示詞歷史中。在此版本之前，回應或命令會在您再也看不到的地方持續執行，而在 `←` 之後立即傳送的提示詞可能會在看不見的情況下再執行一次。在 `SessionStart` hook 仍在執行時輸入的提示詞會遺失：既未傳送，也不在提示詞歷史中。 |
| v2.1.295 | 在[附加的背景工作階段](#attach-to-a-session)的閒置提示詞輸入處按 `Ctrl+C`，不會影響[自訂步調的 `/loop`](https://code.claude.com/docs/zh-TW/scheduled-tasks#let-claude-choose-the-interval) 待決的喚醒，因此按兩次會分離，而迴圈會持續執行。在該輸入處按 `Esc` 會[停止自訂步調的迴圈](https://code.claude.com/docs/zh-TW/scheduled-tasks.md#stop-a-loop)並顯示 `Pending wakeup cancelled` 通知。在此版本之前，第一次 `Ctrl+C` 可能會在無提示的情況下結束自訂步調的迴圈，而 `Esc` 無法停止已隨工作階段移到背景的迴圈。 |
| v2.1.295 | 在 macOS 和 Linux 上，當 `claude agents` 在沒有[監督程序](#keep-sessions-running-after-the-supervisor-stops)執行時退出，它不會自行啟動新的監督程序。除非您再次執行 `claude agents`，否則執行中的工作階段會在約一分鐘後停止，且 agent view 在退出時可能會列印說明此情況的通知。在此版本之前，退出中的 `claude agents` 會啟動新的監督程序。 |
| v2.1.295 | 在使用原生安裝程式的 macOS 上，更新後一起重新啟動的背景工作階段，會在持有您所授予之[受保護資料夾存取權](#background-sessions-can’t-read-desktop-documents-or-downloads-on-macos)的同一個 Claude Code 項目下執行。在此版本之前，這些工作階段可能改為在二進位檔本身的路徑下執行。macOS 會將該路徑列為獨立的項目，因此資料夾存取提示可能會在更新後再次出現。 |
| v2.1.290 | [`claude attach` 和 `claude logs`](#manage-sessions-from-the-shell) 可以接受工作階段名稱的一部分來取代 ID。 |
| v2.1.290 | 作為[查看回覆](#peek-and-reply)傳送給工作中工作階段的 `/model`、`/effort`、`/rename` 和 `/usage` 會立即執行。 |
| v2.1.290 | 無法傳遞的[查看回覆](#peek-and-reply)在以 `/` 開頭時，或在工作階段的程序執行期間回答具有預定義選項的問題時，不再被儲存以供下次重新啟動時使用。 |
| v2.1.288 | `Ctrl+F` 會依名稱尋找工作階段，`Alt+↑` / `Alt+↓` 會在群組標題之間跳轉。這兩者以及 `Ctrl+R` 都可以[重新繫結](https://code.claude.com/docs/zh-TW/keybindings.md#agents-actions)。 |
| v2.1.287 | [`n:<text>` 篩選器](#filter-sessions)會依名稱或第一個提示詞尋找工作階段。當任何篩選器作用中時，您摺疊的群組會展開以顯示其符合項目，並選取第一個符合項目，因此 `Enter` 會開啟它。 |
| v2.1.287 | 作為[查看回覆](#peek-and-reply)傳送的命令會在工作階段目前的回合結束時執行，包括在工作階段自己的輸入中一輸入就會立即執行的命令。內容恰好為 `/stop` 的回覆會立即停止工作階段。 |
| v2.1.281 | [`--setting-sources`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 限制會[轉移](#what-carries-over-when-you-background)到您使用 `←` 或 `/bg` 背景化的工作階段，以及您從 agent view 分派的工作階段。在此版本之前，生成的工作階段會載入每個設定來源。 |
| v2.1.281 | `claude --bg` 和重新啟動工作階段的命令會先檢查工作階段目錄的工作區信任。從該目錄中的終端機，如果您尚未接受，[信任對話框會出現](#from-your-shell)；在無法出現對話框的地方（例如在指令碼中），命令會以 [`Workspace not trusted`](https://code.claude.com/docs/zh-TW/errors#workspace-not-trusted-when-dispatching-a-background-session) 錯誤退出。 |
| v2.1.274 | 自動更新後，您已離開約一小時的 agent view 可以將自己重新啟動到新的建置。當它這樣做時，它會保留您開啟它時的[分派預設值](#dispatch-defaults)：`--model`、`--effort`、`--permission-mode`、`--allow-dangerously-skip-permissions` 和 `--agent`。在此版本之前，重新啟動的 view 只保留 `--cwd` 和設定旗標，例如 `--settings` 和 `--mcp-config`，所以您之後分派的工作階段啟動時沒有這些預設值。 |
| v2.1.274 | 當[刪除因 git 或您的 `WorktreeRemove` hook 無法移除 worktree 而被拒絕](#what-deleting-a-session-removes)時，經 Claude Code 驗證對追蹤檔案沒有未提交變更的已簽出子模組，不會阻止再次刪除並仍移除目錄的選項。已簽出子模組內的未提交工作會計為未提交變更，訊息會指出該子模組的名稱。在此版本之前，worktree 中的任何子模組簽出都會阻止該選項，訊息說 worktree 包含巢狀儲存庫。 |
| v2.1.268 | 當[刪除因 git 或您的 `WorktreeRemove` hook 無法移除 worktree 而被拒絕](#what-deleting-a-session-removes)時，訊息會指出原因，包括 hook 如何結束及其 stderr 的開頭。對於位於儲存庫的 `.claude/worktrees/` 下的連結 worktree，若對追蹤檔案沒有未提交變更、其內沒有巢狀儲存庫，且沒有其他工作階段的記錄指向它，再次刪除工作階段會從 agent view 或使用 `claude rm <id> --force-remove-worktree <worktree-id>` 仍然移除目錄。在此版本之前，列只顯示 `worktree could not be removed (WorktreeRemove hook failed)` 或 git 的錯誤，hook 的 stderr 只進入偵錯日誌，再次刪除會以相同方式被拒絕。 |
| v2.1.268 | 在第一個 `←` 顯示 `Press ← again to open agents`，或在附加的工作階段中顯示 `Press ← again to go back to agents` 後，[至少一秒後到達的第一次按下會切換](#switch-sessions-without-leaving-the-terminal)，即使中間較快的按下被忽略。在此版本之前，每次被忽略的按下都會重新開始等待，所以以穩定的速度再次按 `←` 直到您暫停超過一秒才會切換。 |
| v2.1.260 | 當您[背景化工作階段](#from-inside-a-session)時，您其他工作階段的 [agent 清單](https://code.claude.com/docs/zh-TW/cross-session-messaging.md#see-which-sessions-claude-can-reach)會只顯示該對話一次，作為其背景工作階段，它們傳給它的訊息不再到達您移出它的終端機。在此版本之前，該終端機可能會在對話名稱下被列為第二個互動工作階段，而在移動前已傳訊息給該對話的工作階段會繼續傳遞到該終端機。 |
| v2.1.260 | 當[刪除因未推送的提交而被拒絕](#what-deleting-a-session-removes)時，訊息會指出 worktree 的分支及有多少提交未推送，再次刪除工作階段會丟棄 worktree 及其提交。在此版本之前，拒絕只說 `worktree has commits that are not pushed anywhere`，再次刪除會以相同方式被拒絕，刪除工作階段需要推送提交或手動移除 worktree。 |
| v2.1.257 | `←` [在 `/btw` 覆蓋層開啟時從附加的工作階段分離](#attach-to-a-session)，即使正在回答中途，覆蓋層會在您下次附加時重新開啟。在此版本之前，覆蓋層開啟時 `←` 不會分離。 |
| v2.1.257 | 當您執行 [`claude --resume <session-id> --bg`](#from-your-shell) 時，Claude Code 會在其自己的 ID 下繼續該工作階段，或在新 ID 下啟動副本並列印 `note:` 行說明原因。`--continue`、不帶參數的 `--resume` 和帶有名稱或路徑的 `--resume` 會啟動副本並顯示相同的備註。在此版本之前，`--resume` 與 `--bg` 總是在新 ID 下啟動副本且不說明任何內容。 |
| v2.1.257 | 當您從使用 `←` 開啟的 agent view 分派工作階段時，Claude Code 會以[目標目錄透過 `permissions.defaultMode` 設定的權限模式](#permission-mode)啟動它。當目錄未設定時，會套用您來源工作階段的權限模式。在此版本之前，分派的工作階段總是以您來源工作階段的權限模式啟動，覆寫了目錄的設定。 |
| v2.1.257 | Agent view 中的 `Ctrl+S`、`Ctrl+T` 和 `Ctrl+G` [遵循您的 `keybindings.json`](#keyboard-shortcuts)：`Ctrl+S` 和 `Ctrl+T` 透過 `Agents` 內容的 `agents:switchView` 和 `agents:togglePin` 動作，`Ctrl+G` 則透過 `Chat` 內容的 `chat:externalEditor` 繫結。在此版本之前，agent view 忽略 `keybindings.json`，這些鍵是固定的。 |
| v2.1.257 | 啟動[背景服務](#the-supervisor-process)可從兩種失敗原因中復原。在 macOS npm 安裝上，自我更新期間的啟動會[等待安裝完成](https://code.claude.com/docs/zh-TW/errors.md#eacces-when-starting-a-background-session)，而不是執行 npm 在取代二進位檔時放置的預留位置。在 Windows 上，在機器上次開機前寫入的過時 `daemon.lock`，或其記錄的程序 ID 現在屬於不同程序的，會被取代。在此版本之前，macOS 啟動在安裝期間會失敗並出現 `Error: claude native binary not installed.`，而 Windows 鎖定會使每次啟動都失敗並出現 [`exited before it became reachable`](https://code.claude.com/docs/zh-TW/errors#background-service-exited-before-it-became-reachable)，直到您刪除 `~/.claude/daemon.lock`。 |
| v2.1.257 | 當您在另一個 Claude Code 程序下載 npm 更新時開啟或分派背景工作階段，Claude Code 會在安裝執行期間[持續等待最多兩分鐘](https://code.claude.com/docs/zh-TW/errors.md#eacces-when-starting-a-background-session)，然後失敗並顯示 `Claude Code is being updated by npm on this machine`。在此版本之前，等待在十秒時停止，所以開啟會在下載仍在執行時失敗，出現 `Couldn't start the background service`。 |
| v2.1.257 | 持有[跨工作階段訊息](https://code.claude.com/docs/zh-TW/cross-session-messaging.md#control-inbound-messages)等待您核准的背景工作階段，會在其 `Needs input` 列上顯示 `approve message from`，並附上寄件者的地址和寄件者聲稱的名稱。在此版本之前，列會移到 `Needs input` 但保留其先前的文字，所以 `claude agents` 中沒有任何內容指出等待中的訊息或其寄件者。 |
| v2.1.257 | 在開啟的背景工作階段內使用 `Ctrl+S` 暫存的提示詞[會與工作階段一起保留](#what-persists-across-restarts)，所以 `Ctrl+S` 在工作階段的程序停止並再次啟動後仍能還原它。在此版本之前，暫存只存在於執行中的程序中，當工作階段閒置夠久以至於其程序停止時，或當它被停止後再重新開啟時，就會遺失。 |
| v2.1.251 | 在尚未[移入 worktree](#how-file-edits-are-isolated) 的背景工作階段中，Claude 和它生成的 subagent 可以編輯連結 git worktree 內的檔案。 |
| v2.1.251 | Claude Code 會將您分派時所在 shell 中匯出的雲端提供者閘道，例如 `ANTHROPIC_VERTEX_BASE_URL` 或 `ANTHROPIC_BEDROCK_BASE_URL` 及其身分驗證繞過旗標，以與 `ANTHROPIC_BASE_URL` 相同的條件轉發到[工作階段的工作程序](#llm-gateway)。在此版本之前，如果您從只透過這種閘道進行身分驗證的 shell 背景化或分派，工作階段發出的每個請求都會失敗，因為端點和旗標已從其環境中被丟棄。 |
| v2.1.251 | 當背景工作階段在另一個 Claude Code 程序重新整理[外掛市集](https://code.claude.com/docs/zh-TW/plugins/overview.md)時啟動，例如同級工作階段正在執行[市集自動更新](https://code.claude.com/docs/zh-TW/plugins/install.md#keep-plugins-updated)，Claude Code 會讓該市集的外掛保持可用。在此版本之前，這樣的工作階段可能在沒有該市集任何 skill、agent、hook 和 MCP 伺服器的情況下啟動，並在其整個執行期間保持如此。 |
| v2.1.248 | [分派輸入](#keyboard-shortcuts)中的 `Shift+Enter` 會插入換行，與主要提示詞輸入一致，而在 `?` 覆蓋層列出 `ctrl+enter to start and open` 的終端機中，`Ctrl+Enter` 會立即分派並附加。在此版本之前，`Shift+Enter` 會分派並附加。 |
| v2.1.248 | 當 worktree 的提交已在您 `origin` 遠端預設分支的本機副本上，且您的主要簽出已簽出該分支時，[刪除工作階段](#what-deleting-a-session-removes)會成功；在此版本之前，刪除會被拒絕並出現 `has commits that are not pushed anywhere`。 |
| v2.1.248 | 使用 `←` 或 `/background` 背景化的工作階段在執行期間會持有其 worktree 上的 [`git worktree lock`](https://code.claude.com/docs/zh-TW/worktrees#clean-up-subagent-and-background-session-worktrees)；在此版本之前，背景化會釋放鎖定，清理或 `git worktree remove` 可能在執行中的工作階段底下移除 worktree。 |
| v2.1.248 | 未在等待您輸入、且在其最後活動超過 48 小時後被發現已終止的背景工作階段，例如在機器關閉數天後，會[顯示為已停止](#sessions-show-as-failed-after-shutdown)並附上 `ended while the background service was off`，在其上按 `Enter` 會在恢復其已儲存的對話前先詢問。在此版本之前，這樣的工作階段會重新出現為新的失敗並排序到清單頂端，單次 `Enter` 就會將數週前的對話拉到前景。 |
| v2.1.248 | 開啟一個其對話[已在另一個終端機中恢復](#opening-a-session-says-the-conversation-is-already-open)的已停止列，會被拒絕並出現 `Can't open — this session is running in another terminal`，且該列會顯示 `Open in a terminal`，而不是顯示在 `Working` 下。在此版本之前，開啟該列會啟動第二個寫入相同對話的程序。 |
| v2.1.248 | 在 `PermissionRequest` 或 `PreToolUse` hook 輸出無效答案時等待權限決定的背景工作階段，會[在其列上指出 hook 事件和 schema 錯誤](#peek-and-reply)。在此版本之前，列只顯示待決的請求。 |
| v2.1.248 | 在 Windows 上，`claude agents` 在先前程式留下 win32-input-mode 的終端機分頁中啟動時，會回應鍵盤輸入。在此版本之前，Claude Code 無法解碼這類分頁傳送的按鍵記錄。 |
| v2.1.247 | 在 Linux 和 WSL 上，[其終端機主機程序已終止](#the-terminal-host-died-or-the-session-stopped-responding)的工作階段會在數秒內失敗並顯示原因。沒有產生輸出的開啟會在約十秒後結束並提供重新啟動選項，在該列上按 `Enter` 會以其對話重新啟動工作階段；`claude attach <id>` 會回報原因並退出。在此版本之前，開啟這樣的工作階段會無限期顯示 `opening… · esc to cancel`，而 `claude attach <id>` 會持續等待而不回報錯誤。 |
| v2.1.246 | 在 npm 安裝上，當[背景服務](#the-supervisor-process)在 `npm install -g @anthropic-ai/claude-code` 取代二進位檔期間無法啟動時，Claude Code 會等待最多十秒讓安裝完成並重試，然後才回報 [`EACCES: permission denied`](https://code.claude.com/docs/zh-TW/errors#eacces-when-starting-a-background-session)。 |
| v2.1.246 | 當[背景服務](#the-supervisor-process)程序在輸出錯誤後終止時，Claude Code 會回報失敗並[引用服務的第一行錯誤](https://code.claude.com/docs/zh-TW/errors.md#background-service-exited-before-it-became-reachable)。 |
| v2.1.246 | 如果您的機器在[背景服務](#the-supervisor-process)啟動期間進入睡眠，Claude Code 會重試啟動一次，而不是失敗。 |
| v2.1.246 | 對於新啟動、仍在運作但接受連線緩慢的[背景服務](#the-supervisor-process)，Claude Code 會等待約兩分鐘，而不是 45 秒。 |
| v2.1.246 | [背景服務](#the-supervisor-process)從您的家目錄啟動，所以在 macOS 和 Linux 上，已刪除或移動的啟動目錄不再阻止啟動。 |
| v2.1.246 | `/fork` 會從本身作為副本啟動、且之後尚未記錄新提示詞的工作階段[複製完整對話](#copy-the-session-with-%2Ffork)：您附加的 `/fork` 副本、在 `←` 或 `/background` 將其移到背景後重新附加的工作階段，或使用 `claude --resume <id> --fork-session` 啟動的工作階段。在此版本之前，如果您在傳送新提示詞前就在這樣的工作階段中執行 `/fork`，Claude Code 會列印正常的確認訊息，但以空對話啟動副本。使用 `←` 或 `/background` 將這樣的工作階段移到背景也會以相同方式遺失對話。 |
| v2.1.246 | 當您在剛分派的工作階段的工作程序仍在啟動時開啟它，例如在其列上按 `Enter`，Claude Code 會等待程序然後附加。在此版本之前，如果您在程序仍在啟動時按 `Enter`，Claude Code 可能會停止工作階段，出現 [`Session <id> was stopped while the respawn was in flight`](https://code.claude.com/docs/zh-TW/errors#session-was-stopped-while-the-respawn-was-in-flight)。 |
| v2.1.246 | 當您[背景化](#from-inside-a-session)已命名的工作階段時，Claude Code 只會列出它一次，而當您再次背景化相同的對話時，它會為新列的名稱編號，例如 `my-session (2)`，現有列則保留其名稱。在此版本之前，您按下 `←` 的終端機可能會在 `claude agents --json` 中以相同名稱作為第二個工作階段出現，如果您再次背景化相同的對話，Claude Code 會以完全相同的名稱新增另一列。 |
| v2.1.239 | 開啟 [vim 編輯器模式](https://code.claude.com/docs/zh-TW/interactive-mode.md#vim-editor-mode)時，在 agent view 的輸入中按 `Esc` 會從 INSERT 切換到 NORMAL 模式並保留您的文字，與主要提示詞輸入一致；在 NORMAL 模式下輸入中仍有文字時，按 `Esc` 會清除它，在空輸入上按 `Esc` 則會退出，如 [`Esc` 快捷鍵](#keyboard-shortcuts)所述。在此版本之前，`Esc` 會清除輸入。 |
| v2.1.233 | 對於連結到 GitLab merge request 的工作階段，Claude Code 會以 GitLab 的 `!1234` 參考語法寫入該列的標籤。您也可以將 merge request 的 URL 貼到[分派輸入](#filter-sessions)中以選取該工作階段。在此版本之前，標籤呈現為 `#1234`，而貼上的 merge request URL 只有在工作階段的第一個提示詞包含該 URL 時才會符合。 |
| v2.1.227 | 當另一個執行中的 Claude Code 工作階段正在該 worktree 目錄內執行時，[刪除工作階段](#what-deleting-a-session-removes)會保留工作階段及其 worktree。Agent view 會在列上顯示 `not deleted` 並在頁尾顯示原因，`claude rm` 會列印 `kept <id>` 及原因，其中會指出另一個工作階段的程序 ID。在此版本之前，刪除工作階段會在另一個工作階段仍在其中工作時移除 worktree。 |
| v2.1.225 | 在您尚未信任的目錄中執行 `claude agents`，會在 agent view 開啟前顯示與 `claude` 啟動時相同的[工作區信任對話框](https://code.claude.com/docs/zh-TW/permissions.md#project-allow-rules-and-workspace-trust)。接受會儲存該工作區的信任；拒絕則會在不開啟 agent view 的情況下退出。在此版本之前，`claude agents` 會在不詢問的情況下開啟，所以您從它分派的工作階段會在您從未被要求信任的目錄中執行。 當清單依目錄分組時，將滑鼠懸停在列上會醒目提示它，但不會改變[分派目標](#dispatch-to-a-specific-directory)；使用方向鍵或點擊選取列仍會改變目標。在此版本之前，將滑鼠移到另一個專案中的工作階段上，會在無提示的情況下改變下一個分派工作階段的啟動目錄。 |
| v2.1.221 | `/status` 會顯示 `Session kind` 列：在背景工作階段中視是否附加了終端機而顯示 `background job · attached` 或 `background job · unattended`，在任何其他工作階段中則顯示 `interactive`。在此版本之前，`/status` 不會回報工作階段種類。 `/fork`：Claude Code 會指示[副本](#from-inside-a-session)將其工作與原始工作階段的工作隔離：副本在進行程式碼變更前會建立自己的 worktree，避開原始工作階段的 worktree，且當其任務建立在該工作之上時，會以原始工作階段的分支為基礎建立新分支。請參閱連結的章節以了解確切條件。在此版本之前，副本不會收到隔離指令，可能最終編輯原始工作階段仍在使用的 worktree 或簽出。 開啟 [vim 編輯器模式](https://code.claude.com/docs/zh-TW/interactive-mode.md#vim-editor-mode)時，使用 `u` 將提示詞復原為空白後立即按 `←`，會要求與刪除文字或瀏覽提示詞歷史相同的確認，並僅在第二次按下時切換；在此版本之前，按下會立即切換。 |
| v2.1.219 | 開啟 [vim 編輯器模式](https://code.claude.com/docs/zh-TW/interactive-mode.md#vim-editor-mode)時，在空提示詞上按 `←` 在 NORMAL 模式和 INSERT 模式下都會開啟 agent view，且頁尾的 `←` 提示會在 NORMAL 模式中顯示；在此版本之前，此手勢和提示僅限 INSERT 模式，在 NORMAL 模式中空提示詞上的 `←` 不會有任何作用。在 Claude Code 等待背景化工作階段時於輸入中打字，會以 `Backgrounding cancelled — you have unsent text in the input. Send it or clear it, then press ← again.` 取消切換，讓輸入的草稿不會遺失。 |
| v2.1.218 | 在清空提示詞的刪除後兩秒內，或在瀏覽提示詞歷史後兩秒內按 `←`，會顯示 `Press ← again to open agents`，或在附加的工作階段中顯示 `Press ← again to go back to agents`，並僅在至少一秒後的第二次按下時切換；在此版本之前，按下會立即切換。出現在貼上或指令碼輸入內的 `←` 不再觸發切換。使用 `←` 背景化前景工作階段會在清單上方顯示 `Your conversation moved to the background`，在 agent view 根層級按 `Esc` 會返回該對話，而不是退出到 shell，雙按 `Ctrl+C` 仍為退出方式；如果對話無法重新開啟，Claude Code 會退出並為其列印 `claude --resume` 命令。在 Windows 上，在附加後約半秒內按下的 `←` 會顯示 `Ambiguous ←, press again to detach`，並在第二次按下時分離。 |
| v2.1.217 | 工作階段列上的 pull request 徽章即使在 Claude Code 無法偵測終端機超連結支援時（例如透過 SSH 或 tmux）也會呈現為超連結；設定 [`FORCE_HYPERLINK=0`](https://code.claude.com/docs/zh-TW/env-vars) 可將其呈現為純文字。在此版本之前，未偵測到支援時徽章會呈現為純文字。 |
| v2.1.216 | `/fork`：[確認訊息](#from-inside-a-session)為一行，顯示副本的狀態、其 agent view 列的名稱及供 `claude attach` 使用的工作階段 ID，僅當副本在主要工作樹中執行或編輯您開啟的簽出時，才會以 `runs in the origin tree` 或 `edits this checkout` 結尾。點擊名稱會背景化此工作階段，並在副本的工作階段中開啟 agent view。確認訊息不再重述副本繼承的權限模式；較早版本會列印多行確認訊息，且沒有可點擊的名稱。 需要輸入：在沒有人附加時執行的 `/install-github-app` 和 `/mcp` 設定清單，會將工作階段顯示在 `Needs input` 下，並以一列指出該命令，附加並重新執行命令即可繼續；從 v2.1.208 到 v2.1.215，它們在該狀態下會被直接拒絕。 `--agent` 還原：當工作區受信任時，恢復或重新啟動[背景化的 `--agent` 工作階段](#from-your-shell)會還原 agent 的系統提示詞和工具限制，並優先在工作階段自己的目錄中搜尋該 agent；其 agent 已不存在的工作階段會以預設工具和系統提示詞繼續，並在開啟時顯示可見的警告，而不是在無提示的情況下還原為預設 agent。 `Ctrl+X`：按兩次會刪除工作階段，即使停止嘗試失敗，而不是讓失敗的停止取消待決的刪除，且工作程序已終止的已刪除工作階段不再於下一次重新整理時重新出現。 Worktree 刪除：worktree 目錄不屬於任何 git 儲存庫的工作階段可以被刪除；在此版本之前，每次刪除這類工作階段的嘗試都會被拒絕。已不存在的目錄會立即清除。Agent view 的雙按會移除仍有檔案的目錄，對於由 hook 建立的目錄會執行您的 `WorktreeRemove` hook，除非另一個工作階段的記錄也指向它。`claude rm` 只要檔案仍存在就會保留這類目錄。 |
| v2.1.214 | 使用 `←` 或 `/background` 背景化、且閒置時沒有任何執行中項目的工作階段，會像任何其他閒置工作階段一樣停止其程序，而不是讓其程序和背景服務無限期執行。已完成的工作階段可在背景服務閒置後使用 `claude rm` 或從 agent view 移除，而從非 git 儲存庫目錄（例如多儲存庫工作區資料夾）分派後進入 worktree 的工作階段，當 worktree 本身屬於 git 儲存庫時，可以從 agent view 刪除，因為清理是從 worktree 而不是從分派工作階段的目錄解析的；這兩種移除在之前的每次嘗試都會被拒絕。重新開啟已停止的工作階段會還原其已儲存的對話，即使逐字稿儲存區中的某個資料夾無法讀取。 |
| v2.1.213 | `/install-github-app`、[`/mcp`](https://code.claude.com/docs/zh-TW/mcp) 設定清單和 MCP 身分驗證動作在附加終端機時可在背景工作階段中運作，僅在沒有人附加時被拒絕，並顯示訊息告訴您附加後再次執行命令；從 v2.1.208 到 v2.1.212，即使附加了終端機也會被拒絕。 |
| v2.1.212 | [互動工作階段中的 `/fork`](#from-inside-a-session) 會將對話複製到新的背景工作階段，而原始工作階段會持續執行；`/fork` 較早的分支 subagent 行為已移到 `/subtask`。在[關閉 agent view](#turn-off-agent-view) 時，`/fork` 保持分支 subagent 行為。 |
| v2.1.212 | [在 agent view 中輸入不帶參數的 `/resume`](#bring-back-a-past-session) 會開啟您開啟 agent view 所在儲存庫的過去工作階段選擇器。 |
| v2.1.211 | 透過附加或從其執行目錄回覆來喚醒已停止的工作階段時，會再次以與全新分派相同的條件轉發您 shell 的閘道 `ANTHROPIC_BASE_URL`，所以透過閘道 `ANTHROPIC_AUTH_TOKEN` 進行身分驗證的工作階段會在閘道上恢復，而不是回報 `Not logged in`。附加到在第一個回應完成前就從另一個對話背景化的已停止工作階段，會被拒絕並出現 `This session has no saved transcript`，而不是在無提示的情況下以相同工作階段 ID 啟動空白對話；從 agent view 開啟相同的列會在頁尾顯示拒絕訊息。從 Claude Code 外部結束 `←` 或 `/background` 工作階段的程序會將其標記為已停止，而不是讓監督程序重新啟動它；已記錄在磁碟上的停止會被遵守，除非您傳送的回覆仍在等待傳遞；當機後重新啟動的工作階段會被告知它已重新啟動；重新啟動的 `←` 或 `/background` 工作階段不會恢復超過約一小時前中斷的回應。回答或拒絕提示詞而不是為其加上標籤的工作階段命名回覆，例如對於主要是連結的提示詞，會被丟棄，該列會保留從提示詞文字取得的名稱。刪除其 worktree 已不被 git 識別的工作階段會成功，在磁碟上保留 worktree 目錄並指出其路徑，而不是每次嘗試都被拒絕。被拒絕的刪除會在工作階段列上顯示原因，包括 worktree 無法移除時的底層 git 錯誤，而不是讓該列在無提示的情況下重新出現。 |
| v2.1.210 | `claude attach` 會在背景服務啟動或重新連線時等待，而不是以 `job not found` 或 `still starting` 錯誤失敗，會將在附加期間完成的工作階段回報為已退出，並在附加完成時套用緩慢附加期間進行的終端機大小調整。提示詞頁尾的 `←` 需要輸入計數會出現在每個提供者上，包括先前顯示純 `← for agents` 形式的第三方提供者。使用 `←` 背景化工作階段會將 Claude 的任務清單帶到背景工作階段，而不是丟棄它。您按下 `←` 時所在的列在選取移動後會保留粗體、未變暗的名稱。`claude agents --effort` 會接受 `ultracode`，而不是在無提示的情況下丟棄它。 |
| v2.1.208 | 附加到程序已停止的工作階段時，會在程序啟動期間顯示其逐字稿的最後一個畫面，而不是只顯示 `Session is starting` 備註。因背景服務無法連線或傳送失敗而無法傳遞的回覆會被儲存，並在其程序再次啟動時作為工作階段的下一個提示詞傳送；在此版本之前，背景服務無法連線時遺失的回覆會被丟棄。自身二進位檔已被更新取代的程序，仍可從已安裝的 `claude` 啟動器或磁碟上的最新版本啟動監督程序，而不是在 Claude Code 重新啟動前持續失敗。執行較舊版本的監督程序永遠不會將由較新版本啟動的閒置工作階段重新啟動到其自身較舊的二進位檔上。刪除工作階段會移除其 worktree，即使工作階段已將 worktree 切換到不同的分支；而當 worktree 有未推送到任何地方的提交或另一個工作階段宣告擁有它時，會將 worktree 與工作階段列一起保留，而不是銷毀提交或讓 worktree 成為孤立狀態。`/install-github-app` 和 `/mcp` 設定清單及其身分驗證動作在背景工作階段中會被拒絕，並顯示指出替代方案的訊息；僅在 v2.1.208 中，`/model` 選擇器也以相同方式被拒絕，且輸入的 `/model <name>` 只會切換該工作階段，而不會同時儲存您的預設模型。 |
| v2.1.207 | 查看面板會以該列截斷的句子開啟，例如等待您的工作階段的確切問題，並以單行 `waiting 3m` 顯示被阻擋的工作階段已等待多久，而不是在狀態句子和問題前都加上相同的時間戳記。在分派輸入中再次貼上相同的文字會展開已摺疊的 `[Pasted text #N]` 預留位置，而不是新增第二個。透過接受計畫而命名的背景工作階段會在其列上顯示該名稱。已移入 worktree 的背景工作階段在其程序從 agent view 重新啟動時會保留其對話。 |
| v2.1.206 | 列摘要會填滿該列的剩餘寬度，並僅在終端機的右邊緣截斷，而不是在 64 欄處。監督程序重新啟動到新的 Claude Code 版本後，會在背景中將剩餘的閒置背景工作階段重新啟動到該版本，而不是每分鐘只處理幾個。使用 `Ctrl+X` 或 `claude rm` 刪除工作階段也會將其從監督程序的工作階段清單中清除，因此該列在監督程序重新啟動後不再重新出現。在分派 shell 中匯出的 `CLAUDE_CODE_EXTRA_BODY` 請求本體覆寫會傳遞到背景工作階段，而不是被忽略。 |
| v2.1.205 | 在一般 `claude` 工作階段中，提示詞頁尾的 `←` 提示會計算等待您的背景 agent 數量，例如 `← 2 agents`。列摘要會顯示工作階段自己的單行報告，在 64 欄處截斷，而不是原始工具呼叫或 `done/total` 計數；依目錄分組的列會以彩色狀態詞開頭。查看面板會以完整的狀態句子開啟，對於等待您的工作階段，其確切問題會顯示在回覆輸入上方。使用 `gh` 編輯、評論、關閉或將 pull request 標記為就緒的工作階段都會連結到該 pull request，而不只是建立或簽出 pull request 的工作階段；即使本機分支名稱不符，推送也會連結 pull request；建立命令的輸出超過內嵌限制的 pull request 也會被連結。沒有可讀文字的回合會保留工作階段的先前狀態，而不是將其切回 `Working`。`claude attach` 會為正在重新啟動的工作階段等待最多約 60 秒，並以狀態列說明原因，而不是失敗。 |
| v2.1.203 | 當監督程序共用該閘道環境時，在分派 shell 中匯出的閘道 `ANTHROPIC_BASE_URL` 會傳遞到從該 shell 分派至同一目錄的工作階段，而不是在保留一同匯出的 API 金鑰時被丟棄。分派 shell 的 `PATH` 會套用到每個工作階段的工作程序。在 subagent 執行時按 `←` 會等待它們，而不是在十秒後重新啟動它們。空清單一律會顯示各區段標題，每個標題下方附有說明。在分派輸入中輸入 `@` 也會列出啟動儲存庫中位於其目錄樹內的已註冊 git worktree。從 `effortLevel` 設定繼承的 effort 會跟隨之後對該設定的編輯，而不是在分派時固定。開啟其對話已在另一個執行中工作階段開啟的已停止工作階段，會被拒絕並顯示訊息，而不是讓該列失敗。在 agent view 中不可用的命令會將已輸入的文字保留在輸入中。在 git 儲存庫外失敗的 `WorktreeCreate` hook 不再阻止工作階段編輯檔案。 |
| v2.1.202 | 在背景工作階段上使用 `/rename` 或 `Ctrl+R` 設定的名稱，在監督程序停止並重新啟動其程序時會保留，而不是還原為工作階段分派時的名稱。 |
| v2.1.200 | 較舊的 Claude Code 版本在重寫 `roster.json` 中的工作階段清單時，會保留較新版本寫入的欄位，與現有的 `state.json` 保證一致，因此由較新版本啟動的工作階段在監督程序重新啟動後會繼續接受輸入。當您開啟已停止回應的工作階段時，監督程序會重新啟動其程序，工作階段會從中斷處繼續被中斷的回應。Agent view 會將放在 `agents` 之後的 `--plugin-dir` 旗標套用到其分派輸入中自己的 subagent 和 skill 自動完成，以及分派的工作階段。 |
| v2.1.199 | 在低記憶體主機上，其程序在完成啟動前就退出的背景工作階段，會在其列狀態中顯示 `possibly low memory — free some up and retry`，而不是只顯示單純的退出原因。使用 `←` 或 `/background` 背景化工作階段會將其 `/color` 帶到新列。 |
| v2.1.198 | 當背景工作階段需要輸入、完成或失敗時，Agent view 會透過 `preferredNotifChannel` 傳送通知，並以 `agent_needs_input` 或 `agent_completed` 類型觸發 `Notification` hook。在 `claude attach <id>` 內的 `←` 和 `/exit` 會返回 agent view，而不是退出到 shell；`Ctrl+Z` 會返回 shell。在 worktree 中隔離其工作的背景工作階段完成時，會提交、推送其自己的隔離分支（絕不是 `main` 或 `master`），並開啟草稿 pull request，而不是先詢問。`/login` 可在 agent view 中執行並開啟登入對話框。`Background work is running` 退出對話框提供 `Move to background and exit`。退出交接也涵蓋背景 subagent，它們會在下次喚醒時從其逐字稿恢復，而不是被回報為失敗。`claude --bg` 與 `-p` 或 `--print` 合併使用會被拒絕並出現錯誤。背景工作階段主機會在首次存取 LAN 時請求 macOS 本機網路權限，而不是以 `connect: no route to host` 失敗。 |
| v2.1.196 | 按一次 `←` 即可背景化前景工作階段；較早的版本需要按兩次，並附有頁尾提示和確認。傳遞給 `claude agents` 的 `--dangerously-skip-permissions` 會顯示繞過免責聲明，而不是在無提示的情況下被丟棄。您從未命名的互動工作階段在工作階段清單和 `claude agents --json` 中會帶有預設名稱，例如 `my-app-3f`。背景 shell 命令在工作階段的程序被停止、重新啟動或更新時仍會存續，包括在 Windows 上；設定 `CLAUDE_CODE_DISABLE_BG_EXIT_HANDOFF=1` 可關閉此交接。在重新啟動時被誤判為空的逐字稿會加上 `.orphaned-` 後綴重新命名，而不是被刪除。 |
| v2.1.195 | 在 Windows 上背景化工作階段時，進行中的背景工作也會轉移。`Completed` 群組會填滿剩餘的垂直空間，標題在較矮的終端機上會壓縮。較舊的 Claude Code 版本不再丟棄較新工作階段的 `state.json` 欄位，也不再從 `claude agents` 中隱藏這些工作階段。附加到已停止的工作階段會立即切換，而不是顯示空白畫面長達五秒。無法接受連線的監督程序會自行退出並釋放其鎖定。 |
| v2.1.191 | `claude --bg` 搭配不符合您任何 subagent 的 `--agent` 名稱時會啟動失敗：工作階段會立即退出並出現 `--agent '<name>' not found` 錯誤，而不是以預設 agent 執行。 |
| v2.1.174 | 背景工作階段不再從監督程序的啟動 shell 繼承閘道端點變數，例如 `ANTHROPIC_BASE_URL`；監督程序會向預熱的工作程序提供新的憑證快照，修正了虛假的 `Could not resolve authentication method` 錯誤。 |
| v2.1.172 | 分派輸入中的 `/model` 會設定工作階段範圍的分派模型覆寫。 |
| v2.1.161 | 列摘要會顯示平行工作項目的 `done/total` 計數；查看面板會指出執行最久的平行工作項目。 |
| v2.1.157 | `claude agents` 接受 `--agent`；分派的工作階段會遵循 `agent` 設定。 |
| v2.1.145 | 查看面板回覆輸入和分派輸入中支援語音聽寫。 |
| v2.1.143 | 新增 `worktree.bgIsolation` 設定；`claude agents` 接受 `--allow-dangerously-skip-permissions`。 |
| v2.1.142 | `claude agents` 接受 `--permission-mode`、`--model`、`--effort`、`--dangerously-skip-permissions`、`--settings`、`--add-dir`、`--plugin-dir`、`--mcp-config` 和 `--strict-mcp-config`。 |
| v2.1.141 | `claude agents` 接受 `--cwd` 以將清單範圍限定為單一專案。 |
| v2.1.139 | Agent view 以研究預覽形式推出。 |

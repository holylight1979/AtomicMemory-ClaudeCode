<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/agents | lastmod: 2026-10-30 | section: Build with Claude Code / Agents and parallel work -->
> 來源：https://code.claude.com/docs/zh-TW/agents（官方 zh-TW，lastmod 2026-10-30）｜分類：Build with Claude Code › Agents and parallel work｜EN 摘要：Compare the ways Claude Code can take on multiple tasks at once: subagents, agent view, agent teams, dynamic workflows, and projects.

# 平行執行代理

> 比較 Claude Code 同時執行多項任務的方式：子代理、代理檢視、代理團隊、動態工作流程和專案。

Claude Code 有五種方式可以同時處理多項任務：[子代理](https://code.claude.com/docs/zh-TW/sub-agents.md)、[代理檢視](https://code.claude.com/docs/zh-TW/agent-view.md)、[代理團隊](https://code.claude.com/docs/zh-TW/agent-teams.md)、[動態工作流程](https://code.claude.com/docs/zh-TW/workflows.md) 和 [專案](https://code.claude.com/docs/zh-TW/claude-projects.md)。它們在您的參與程度上有所不同，從自己引導每個對話到讓 Claude 協調一組工作人員，以及工作是在您的機器上執行還是在雲端執行。

| 方法 | 提供的功能 | 使用時機 |
| :- | :- | :- |
| [子代理](https://code.claude.com/docs/zh-TW/sub-agents.md) | 在一個工作階段內的委派工作人員，在自己的上下文中執行側邊任務並返回摘要 | 側邊任務會用搜尋結果、日誌或檔案內容淹沒您的主要對話，而您不會再次參考這些內容 |
| [代理檢視](https://code.claude.com/docs/zh-TW/agent-view.md) | 一個畫面可以分派和監控在背景執行的工作階段，使用 `claude agents` 開啟。研究預覽 | 您有多個獨立任務，想要交付它們，一目瞭然地檢查狀態，並且只在其中一個需要您時才介入 |
| [代理團隊](https://code.claude.com/docs/zh-TW/agent-teams.md) | 多個協調的工作階段，具有共享的任務清單和代理間訊息傳遞，由主導者管理。實驗性功能，預設停用 | 您希望 Claude 將專案分成多個部分、分配它們，並保持工作人員同步 |
| [專案](https://code.claude.com/docs/zh-TW/claude-projects.md) | 在 claude.ai/code 或桌面應用程式中進行的一個持續對話。Claude 啟動稱為執行緒的平行工作階段，在雲端執行，或在您要求時透過 Remote Control 在您的電腦上執行。它為每個工作階段提供專案的指示，並向您顯示哪些需要您。Pro、Max 和 Ultra 上的公開測試版 | 工作跨越許多任務，持續數天或數週，應在您的機器關閉時繼續執行，並且您寧願描述一次而不是分派和追蹤每個工作階段 |
| [動態工作流程](https://code.claude.com/docs/zh-TW/workflows.md) | 執行許多子代理並交叉檢查其結果的指令碼，適用於太大而無法一次協調或需要多次傳遞的工作 | 工作超出了少數子代理的範圍，或您希望針對彼此驗證發現：整個程式碼庫審計、500 個檔案遷移、交叉檢查的研究，或從多個角度起草的計畫 |

在每種方法中，工作人員都是 Claude 工作階段。若要涉及不同的工具，請將其作為 [MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md) 公開給 Claude。

還有三個工具支援此工作，但它們本身不是執行代理的方式：

* [Worktrees](https://code.claude.com/docs/zh-TW/worktrees.md) 為每個工作階段提供單獨的 git 簽出，因此平行工作階段各自編輯自己的檔案副本。將它們用於您自己執行的工作階段。從 agent 檢視分派的工作階段會 [在編輯檔案之前移動到自己的 worktree 中](https://code.claude.com/docs/zh-TW/agent-view.md#how-file-edits-are-isolated)，您生成的 subagent 也可以各自獲得一個。
* [跨工作階段訊息傳遞](https://code.claude.com/docs/zh-TW/cross-session-messaging.md) 讓 Claude 列出並訊息傳遞您在此機器上、另一台機器上或 [網路上的 Claude Code](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md) 上的其他 Claude Code 工作階段，因此您自己執行的工作階段可以在彼此之間傳遞發現和狀態。
* [`/batch`](https://code.claude.com/docs/zh-TW/commands) 是一個 [skill](https://code.claude.com/docs/zh-TW/skills.md)，讓 Claude 將一個大型變更分成 5 到 30 個 worktree 隔離的子代理。這是子代理和 worktrees 的打包使用，不是單獨的協調風格。

還有一些其他功能在您不驅動每個步驟的情況下執行 Claude，但它們解決的問題與跨代理分割工作不同：

* [背景 bash 命令](https://code.claude.com/docs/zh-TW/interactive-mode.md#background-bash-commands) 執行一個 shell 命令而不阻止對話。它不會生成代理。
* [分叉子代理](https://code.claude.com/docs/zh-TW/sub-agents.md#fork-the-current-conversation) 是一個繼承您完整對話上下文而不是從頭開始的子代理。這是生成子代理的一種方式，不是單獨的介面。使用 `/subtask` 啟動一個。Claude 也會在 [分叉模式](https://code.claude.com/docs/zh-TW/sub-agents.md#turn-fork-mode-on-or-off) 開啟時自己生成一個。若要將整個工作階段複製到與其並行執行的新 [背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md#from-inside-a-session)，請使用 `/fork`。當 [代理檢視關閉](https://code.claude.com/docs/zh-TW/agent-view.md#turn-off-agent-view) 時，分叉子代理命令是 `/fork`，而 `/subtask` 不可用。
* [雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md) 在雲端按排程執行工作階段，而不是在您的機器上平行執行。

> [!NOTE]
>
> 同時執行多個工作階段或 subagent 會倍增 token 使用量。有關使用量和速率限制詳細資訊，請參閱 [成本](https://code.claude.com/docs/zh-TW/costs.md)。

## 選擇一個方法

正確的方法取決於誰協調工作、工作人員是否需要溝通，以及他們是否編輯相同的檔案：

* **誰協調工作？**
  * Claude 在一個對話中委派並收集結果：[subagents](https://code.claude.com/docs/zh-TW/sub-agents.md)
  * 您交付獨立任務並稍後檢查：[agent view](https://code.claude.com/docs/zh-TW/agent-view.md)
  * Claude 規劃、分配並監督一組工作人員：[agent teams](https://code.claude.com/docs/zh-TW/agent-teams.md)，實驗性功能且預設停用
  * 指令碼保存計畫而不是 Claude 的逐輪判斷：[dynamic workflows](https://code.claude.com/docs/zh-TW/workflows.md)。請參閱 [workflows 與 subagents 和 skills 的比較方式](https://code.claude.com/docs/zh-TW/workflows.md#when-to-use-a-workflow)
* **工作人員需要彼此交談嗎？** Claude 可以透過 [cross-session messaging](https://code.claude.com/docs/zh-TW/cross-session-messaging.md) 在您自己執行的工作階段之間傳遞發現，包括您從 agent view 分派的工作階段。Subagents 將結果報告回生成它們的對話，agent view 工作階段只向您報告結果。agent team 中的隊友彼此直接傳訊，當他們 [擁有 Task tools](https://code.claude.com/docs/zh-TW/tools-reference.md#task-tool-availability) 時，共享任務清單。
* **任務是否涉及相同的檔案？** 使用 [worktrees](https://code.claude.com/docs/zh-TW/worktrees.md) 隔離工作。Subagents 和您自己執行的工作階段可以各自使用單獨的 worktree。Agent teams 不會在 worktrees 中隔離隊友，因此 [分割工作](https://code.claude.com/docs/zh-TW/agent-teams.md#avoid-file-conflicts)，使每個隊友擁有不同的檔案集。

## 檢查運行中的工作

檢查運行中工作的命令取決於您使用的方法：

* 對於後台會話，`claude agents` 打開 [代理視圖](https://code.claude.com/docs/zh-TW/agent-view.md)：一個屏幕顯示每個會話、其狀態以及哪些需要您的輸入。
* 對於目前工作階段中的 subagent，具名的背景 subagent 會連同其狀態出現在 @-mention 自動完成清單中。`/agents` 命令會顯示一則通知，指向 subagent 檔案的位置。若要[建立和編輯自訂 subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#configure-subagents)，請詢問 Claude 或直接編輯這些檔案。儘管名稱相似，`/agents` 與 `claude agents` 是各自獨立的功能。
* 對於當前會話後台運行的任何內容，`/tasks` 列出每個項目，並讓您檢查、附加到或停止它。該列表還包括已完成的子代理。
* 對於動態工作流程，`/workflows` 列出運行和已完成的運行、每個運行所處的階段，以及有多少代理已完成。

有關所有會話的桌面視圖，請參閱 [桌面應用中的並行會話](https://code.claude.com/docs/zh-TW/desktop.md#work-in-parallel-with-sessions)。

## 了解更多

下面的每個指南涵蓋一種方法的設置和配置：

* [創建自定義子代理](https://code.claude.com/docs/zh-TW/sub-agents.md)：定義可重用的專家並控制他們可以使用的工具。
* [使用代理視圖管理代理](https://code.claude.com/docs/zh-TW/agent-view.md)：調度會話、監視其狀態並在需要時附加。
* [協調代理團隊](https://code.claude.com/docs/zh-TW/agent-teams.md)：設置領導者和隊友、分配任務並審查他們的工作。
* [協調動態工作流](https://code.claude.com/docs/zh-TW/workflows.md)：運行捆綁的工作流或讓 Claude 編寫一個運行許多子代理並驗證其發現相互對比的工作流。
* [使用 worktrees 運行並行會話](https://code.claude.com/docs/zh-TW/worktrees.md)：在隔離的檢出中啟動 Claude、控制複製的內容並在之後進行清理。

<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/agent-teams | lastmod: 2026-11-03 | section: Build with Claude Code / Agents and parallel work -->
> 來源：https://code.claude.com/docs/zh-TW/agent-teams（官方 zh-TW，lastmod 2026-11-03）｜分類：Build with Claude Code › Agents and parallel work｜EN 摘要：Coordinate multiple Claude Code instances working together as a team, with shared tasks, inter-agent messaging, and centralized management.

# 協調 Claude Code 工作階段團隊

> 協調多個 Claude Code 實例作為團隊一起工作，具有共享任務、代理間訊息傳遞和集中管理。

> [!WARNING]
>
> Agent teams 是實驗性功能，預設為停用。透過在 [settings.json](https://code.claude.com/docs/zh-TW/settings.md) 或環境中設定 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` 來啟用。若沒有該變數，工作階段啟動時不會設定任何團隊、不會寫入團隊目錄，Claude 也不會生成或提議隊友。Agent teams 在工作階段恢復、任務協調和關閉行為方面有[已知限制](#limitations)。

Agent teams 讓您協調多個 Claude Code 實例一起工作。一個工作階段充當團隊主管，協調工作、分配任務並綜合結果。隊友獨立工作，各自在自己的 context window 中，並直接相互溝通。您也可以直接與任何隊友互動，無需透過主管。

在設定團隊之前，請檢查是否有更輕量的選項可以完成工作。[Subagents](https://code.claude.com/docs/zh-TW/sub-agents.md) 在單個工作階段內運行，透過[跨工作階段訊息傳遞](https://code.claude.com/docs/zh-TW/cross-session-messaging.md)，Claude 可以在您自己執行的工作階段之間傳遞發現。

## 何時使用 agent teams

Agent teams 最適合用於並行探索能增加真實價值的任務。請參閱[使用案例範例](#use-case-examples)以了解完整情景。最強的使用案例是：

* **研究和審查**：多個隊友可以同時調查問題的不同方面，然後分享並質疑彼此的發現
* **新模組或功能**：隊友可以各自擁有一個獨立部分，不會相互干擾
* **使用競爭假設進行除錯**：隊友並行測試不同的理論，更快地收斂到答案
* **跨層協調**：跨越前端、後端和測試的變更，各由不同的隊友負責

Agent teams 增加了協調開銷，並使用的 tokens 遠多於單個工作階段。當隊友可以獨立運作時，它們效果最佳。對於順序任務、相同檔案編輯或具有許多依賴關係的工作，單個工作階段或 [subagents](https://code.claude.com/docs/zh-TW/sub-agents.md) 更有效。

### 與 subagents 比較

Agent teams 和 [subagents](https://code.claude.com/docs/zh-TW/sub-agents.md) 都讓您並行化工作，但它們的運作方式不同。對於傳遞訊息給彼此但沒有團隊的獨立工作階段，請參閱[跨工作階段訊息傳遞](https://code.claude.com/docs/zh-TW/cross-session-messaging.md)。

![比較 subagent 和 agent team 架構的圖表。Subagents 由主代理生成、執行工作並報告結果。Agent teams 透過共享任務列表進行協調，隊友彼此直接溝通。](https://mintcdn.com/claude-code/nsvRFSDNfpSU5nT7/images/subagents-vs-agent-teams-light.png?fit=max\&auto=format\&n=nsvRFSDNfpSU5nT7\&q=85\&s=2f8db9b4f3705dd3ab931fbe2d96e42a)

Subagents 只向主代理報告結果。在 agent teams 中，隊友共享任務列表、認領工作並直接相互溝通。

| | Subagents | Agent teams |
| :- | :- | :- |
| **Context** | 自己的 context window；結果返回給呼叫者 | 自己的 context window；完全獨立 |
| **溝通** | 將結果返回給呼叫者。Claude 在生成時[命名](https://code.claude.com/docs/zh-TW/sub-agents.md#subagent-names)的 Subagents 也可以[彼此訊息傳遞](https://code.claude.com/docs/zh-TW/sub-agents.md#what-loads-at-startup) | 隊友直接相互訊息傳遞 |
| **協調** | 主代理管理所有工作 | 透過訊息進行自我協調，加上具有 [Task tools 的代理](https://code.claude.com/docs/zh-TW/tools-reference.md#task-tool-availability)的共享任務列表 |
| **最適合** | 只有結果重要的專注任務 | 需要討論和協作的複雜工作 |
| **Token 成本** | 較低：結果摘要返回到主 context | 較高：每個隊友是一個獨立的 Claude 實例 |

當您需要快速、專注的工作人員報告結果時，使用 subagents。當隊友需要分享發現、相互質疑並自行協調時，使用 agent teams。

## 啟用 agent teams

Agent teams 預設為停用。透過將 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` 環境變數設定為 `1`，在您的 shell 環境或透過 [settings.json](https://code.claude.com/docs/zh-TW/settings.md) 來啟用：

```json settings.json theme={null}
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

啟用 agent teams 也會改變普通的委派。Claude 可能會[自行命名一個 subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#subagent-names)，而當 agent teams 啟用時，Claude 命名的 subagent 會作為隊友啟動，因此即使您沒有要求，團隊也可能形成。如需更多資訊，請參閱[Claude 如何啟動 agent teams](#how-claude-starts-agent-teams)；若要關閉此行為，請參閱 [Claude 生成隊友而非 subagents](#claude-spawns-teammates-instead-of-subagents)。

生成隊友也需要互動式工作階段。在[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)中使用 `-p` 旗標，包括 Agent SDK 工作階段，Claude 不會生成隊友，即使啟用了 agent teams，Claude 命名的 subagent 也會作為普通的 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 執行。

## 啟動您的第一個 agent team

啟用 agent teams 後，用自然語言描述您想要的任務和隊友。Claude 會生成他們並根據您的提示協調工作。

此範例效果很好，因為三個角色是獨立的，可以在不相互等待的情況下探索問題：

```text wrap theme={null}
I'm designing a CLI tool that helps developers track TODO comments across
their codebase. Spawn three teammates to explore this from different angles:
one on UX, one on technical architecture, one playing devil's advocate.
```

從那裡，Claude 會建立一個[共享任務列表](https://code.claude.com/docs/zh-TW/interactive-mode.md#task-list)，在[具有 Task 工具的工作階段](https://code.claude.com/docs/zh-TW/tools-reference.md#task-tool-availability)中，為每個觀點生成隊友，讓他們探索問題，並在完成時綜合發現。

Claude 有時可能會使用[子 agent](https://code.claude.com/docs/zh-TW/sub-agents.md)而不是建立 team。子 agent 會出現在與隊友相同的 agent 面板中，因此單獨的面板不會確認 team 已形成。如果 Claude 生成了子 agent，請再次詢問並明確要求 agent team。

主管的終端在提示輸入下方的 agent 面板中列出隊友。從面板中：

* **向上和向下箭頭**：選擇隊友
* **Enter**：開啟所選隊友的記錄並直接向其傳送訊息
* **Escape**：清除選擇。當您檢視隊友的記錄時，Escape 會中斷該隊友的目前回合

當任何隊友或 subagent 仍在工作時，閒置隊友的列會保留在面板中，因此您可以選擇它來檢視其逐字稿或向其分配更多工作。一旦面板中的每個 agent 都閒置，閒置列會在 30 秒後隱藏，並在隊友的下一個回合時重新出現；隊友在隱藏時仍保持執行狀態且可定址。

當超過三個隊友同時閒置時，前三個之外的列會摺疊成單一列，計算摺疊的隊友，例如當五個閒置時顯示 `2 idle agents`。選擇它並按 Enter 以展開摺疊的列，或按 Esc 以再次摺疊它們。工作中的隊友、失敗的隊友和您正在檢視的隊友始終保持自己的列。

如果您希望每個隊友都在自己的分割窗格中，請參閱[選擇顯示模式](#choose-a-display-mode)。

## 控制您的 agent team

用自然語言告訴主管您想要什麼。它根據您的指示處理團隊協調、任務分配和委派。

### 選擇顯示模式

Agent teams 支援兩種顯示模式：

* **In-process**：所有隊友在您的主終端內運行。使用上下箭頭鍵在 agent 面板中選擇隊友，然後按 Enter 鍵查看它並輸入以直接向它傳送訊息。在任何終端中工作，無需額外設定。
* **Split panes**：每個隊友都有自己的窗格。您可以同時看到所有人的輸出並點擊窗格直接互動。需要 tmux 或 iTerm2。

> [!NOTE]
>
> `tmux` 在某些作業系統上有已知限制，傳統上在 macOS 上效果最佳。在 iTerm2 中使用 `tmux -CC` 是進入 `tmux` 的建議入口點。

預設值是 `"in-process"`。設定 `"auto"` 以在您已在 tmux 工作階段內運行或您的終端是已安裝 `it2` CLI 的 iTerm2 時啟用分割窗格，否則回退到 in-process。`"tmux"` 設定啟用分割窗格模式，並根據您的終端自動偵測是否使用 tmux 或 iTerm2。

設定 `"iterm2"` 以明確使用 iTerm2 原生分割窗格。此模式需要 [`it2` CLI](https://github.com/mkusaka/it2)，如果 `it2` 遺失，會顯示帶有安裝命令的錯誤。當您的終端是 iTerm2 且 tmux 可作為備用方案時，在 `"auto"` 或 `"tmux"` 下會出現提供安裝 `it2` 或切換到 tmux 的設定提示。

若要覆蓋預設值，請在 `~/.claude/settings.json` 中設定 [`teammateMode`](https://code.claude.com/docs/zh-TW/settings-reference#teammatemode)：

```json theme={null}
{
  "teammateMode": "auto"
}
```

若要為單個工作階段設定模式，請將其作為旗標傳遞：

```bash theme={null}
claude --teammate-mode auto
```

`--teammate-mode` 旗標是實驗性的，不會出現在 `claude --help` 中。

分割窗格模式需要 [tmux](https://github.com/tmux/tmux/wiki) 或 iTerm2 搭配 [`it2` CLI](https://github.com/mkusaka/it2)。若要手動安裝：

* **tmux**：透過您系統的套件管理器安裝。請參閱 [tmux wiki](https://github.com/tmux/tmux/wiki/Installing) 以了解平台特定的指示。
* **iTerm2**：安裝 [`it2` CLI](https://github.com/mkusaka/it2)，然後在 **iTerm2 → Settings → General → Magic → Enable Python API** 中啟用 Python API。

### 指定隊友和模型

Claude 根據您的任務決定要生成的隊友數量，或者您可以指定您想要的確切內容：

```text wrap theme={null}
Spawn 4 teammates to refactor these modules in parallel. Use Sonnet for
each teammate.
```

Claude Code 從以下第一個適用的來源為每個隊友選擇模型：

1. 您的生成提示為該隊友命名的模型。
2. 對於從[子 agent 定義](#use-subagent-definitions-for-teammates)生成的隊友，定義的 `model`，其中 `inherit` 選擇主管的模型。
3. [`CLAUDE_CODE_SUBAGENT_MODEL`](https://code.claude.com/docs/zh-TW/model-config#environment-variables)，當它設定為 `inherit` 以外的任何值時。
4. 主管的目前模型。

如果已安裝的 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md) 在其 [`agent.spawn`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#subagents) hook 中設定了模型，Claude Code 會使用該模型取代第一個來源。

如果您設定 [`CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1`](https://code.claude.com/docs/zh-TW/sub-agents#run-every-subagent-on-one-model)，前兩個來源不適用。當 `CLAUDE_CODE_SUBAGENT_MODEL` 設定為 `inherit` 以外的任何值時，Claude Code 從該環境變數為每個隊友選擇模型，否則從主管的目前模型選擇。需要 Claude Code v2.1.257 或更新版本。

在 v2.1.251 之前，`CLAUDE_CODE_SUBAGENT_MODEL` 在此順序中排在第一位。

> [!NOTE]
>
> `teammateDefaultModel` 在 v2.1.234 中被移除；Claude Code 忽略任何遺留值。改為在您的提示中命名模型。

Claude Code 根據您組織的 [`availableModels`](https://code.claude.com/docs/zh-TW/model-config#restrict-model-selection) 允許清單檢查為隊友選擇的模型。當允許清單阻止某個值時，Claude Code 會替換另一個模型：

* **家族別名，例如 `opus`**：在 Anthropic API 和 AWS 上的 Claude Platform 上，Claude Code 在允許清單允許的該家族的最新版本上運行隊友。在具有提供者特定模型 ID 的提供者上，其中[替換不運行](https://code.claude.com/docs/zh-TW/model-config.md#restrict-model-selection)，被阻止的別名會根據下一個項目符號像任何其他被阻止的值一樣回退
* **任何其他被阻止的值，包括提供者特定模型 ID 提供者上的家族別名，或其家族沒有允許版本的別名**：Claude Code 在主管的模型上運行隊友。如果您設定 `CLAUDE_CODE_SUBAGENT_MODEL`，Claude Code 會先嘗試該模型，遵循相同的規則

預設情況下，使用主管模型的隊友會繼承主管的 [effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)。在分割窗格模式中，這從 v2.1.186 開始適用；較早的版本未將主管的工作階段 effort 傳遞給分割窗格隊友。對於使用其他模型的隊友，請參閱 [subagent 和隊友的 effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#effort-level-of-subagents-and-teammates)。

### 讓隊友在實施前進行計畫

對於複雜或有風險的任務，您可以讓隊友在實施前進行計畫。當主管處於 [plan mode](https://code.claude.com/docs/zh-TW/permission-modes.md#analyze-before-you-edit-with-plan-mode) 時，Claude 生成的隊友也會在 plan mode 中工作，直到其計畫準備好。首先將主管切換到 plan mode，然後要求生成隊友：

```text wrap theme={null}
Spawn an architect teammate to refactor the authentication module.
```

當該隊友完成計畫時，它向主管發送計畫核准請求。如果您自該隊友生成以來未變更其權限模式，Claude Code 會在請求到達時立即核准計畫，無需主管審查。一旦核准，隊友退出 plan mode 並開始實施。Claude Code 會將主管目前的[權限模式](#permissions)傳遞給它；如果主管目前是 plan mode，則傳遞 Manual。

如果您在查看正在運行的 in-process 隊友的工作階段時，按下 [`Shift+Tab`](https://code.claude.com/docs/zh-TW/permission-modes#switch-permission-modes) 將其置於 plan mode，則該次運行的計畫會由主管審查，而非由 Claude Code 核准。系統不會要求您核准；主管會核准它，或將其退回修訂。

### 直接與隊友交談

每個隊友都是一個完整、獨立的 Claude Code 工作階段。您可以直接向任何隊友傳送訊息，以提供額外指示、提出後續問題或重新定向其方法。

* **In-process 模式**：使用上下箭頭鍵在 agent 面板中選擇隊友，然後按 Enter 鍵查看其工作階段並輸入以傳送訊息。在選定的隊友上按 `x` 以停止它。按 Ctrl+T 切換任務列表。
* **Split-pane 模式**：點擊隊友的窗格以直接與其工作階段互動。每個隊友都有自己終端的完整檢視。

當您正在查看 in-process 隊友時，純文字和 [skills](https://code.claude.com/docs/zh-TW/skills.md) 會傳送給該隊友，而內建命令會傳送到主管的工作階段，並具有以下保護措施：

* `/compact`、`/clear` 和 `/rewind` 作用於主管的對話，因此從此檢視執行其中任一命令前，Claude Code 會要求您確認。
* `/model` 和 `/fast` 設定的是主管的模型和快速模式，而非隊友的，因此它們不會從此檢視執行。會有通知告訴您原因。

隊友的模型和快速模式在它生成時是固定的。

### 分配和認領任務

共享任務列表協調整個團隊的工作。主管建立任務，隊友完成它們。任務有三種狀態：待處理、進行中和已完成。任務也可以依賴其他任務，並在這些任務完成之前於任務列表中顯示為已阻止。隊友不會自行認領已阻止的任務，但您或主管仍然可以分配它。

[沒有 Task 工具](https://code.claude.com/docs/zh-TW/tools-reference.md#task-tool-availability)的 Agents 改為透過訊息而非共享任務列表進行協調。

主管可以明確分配任務，或隊友可以自行認領：

* **主管分配**：告訴主管將哪個任務分配給哪個隊友
* **自行認領**：完成任務後，隊友自行選擇下一個未分配、未阻止的任務

任務認領使用檔案鎖定來防止多個隊友同時嘗試認領同一任務時的競爭條件。

### 關閉隊友

若要優雅地結束隊友的工作階段，請按名稱引用它。例如，使用名為 researcher 的隊友：

```text wrap theme={null}
Ask the researcher teammate to shut down
```

主管發送關閉請求。隊友可以批准並優雅地退出，或拒絕並提供解釋。

團隊的共享目錄在工作階段結束時會自動清理，因此沒有單獨的清理步驟。請參閱[架構](#architecture)以了解哪些目錄被移除以及哪些目錄保留在磁碟上。

### 使用 hooks 強制執行品質閘門

使用 [hooks](https://code.claude.com/docs/zh-TW/hooks.md) 在隊友完成工作或任務建立或完成時強制執行規則：

* [`TeammateIdle`](https://code.claude.com/docs/zh-TW/hooks#teammateidle)：當隊友即將閒置時運行。以代碼 2 退出以發送反饋並保持隊友工作。
* [`TaskCreated`](https://code.claude.com/docs/zh-TW/hooks#taskcreated)：當任務正在建立時運行。以代碼 2 退出以防止建立並發送反饋。
* [`TaskCompleted`](https://code.claude.com/docs/zh-TW/hooks#taskcompleted)：當任務被標記為完成時運行。以代碼 2 退出以防止完成並發送反饋。

## Agent teams 的運作方式

本節說明 agent teams 背後的架構與運作機制。如果您想開始使用，請參閱上方的[控制您的 agent team](#control-your-agent-team)。

### Claude 如何啟動 agent teams

若要啟動團隊，請要求 Claude 建立隊員。在啟用 agent teams 的情況下，當 Claude 以 [`name`](https://code.claude.com/docs/zh-TW/sub-agents#subagent-names) 呼叫 [Agent 工具](https://code.claude.com/docs/zh-TW/tools-reference.md)時，就會啟動一名隊員，除非該呼叫是 [fork](https://code.claude.com/docs/zh-TW/sub-agents.md#fork-the-current-conversation)，或在呼叫本身傳入了 `isolation`。Claude Code 不會要求您確認啟動。

Claude 也會自行為一般 subagent 命名，以便之後傳訊息給它們。這些呼叫遵循相同的規則，因此即使您沒有要求，也可能形成團隊。如果您想改用 subagent，請[關閉 agent teams](#claude-spawns-teammates-instead-of-subagents)。

### 架構

一個 agent team 由以下部分組成：

| 元件 | 角色 |
| :- | :- |
| **組長** | 產生隊員並協調工作的主要 Claude Code 工作階段 |
| **隊員** | 各自處理所指派任務的獨立 Claude Code 執行個體 |
| **任務清單** | 隊員認領並完成的共用工作項目清單 |
| **信箱** | 供 agent 之間溝通的訊息系統 |

每個 agent 的信箱是位於 `~/.claude/teams/{team-name}/inboxes/{agent-name}.json` 的 JSON 檔案。Claude Code 讀取信箱檔案時會驗證每一筆項目。不符合訊息格式的項目會被回報為錯誤並從檔案中移除；有效的訊息仍會照常傳遞。

只有在寫入收件者信箱檔案成功時，Claude Code 才會將訊息回報為已傳送，無論該訊息是純文字，還是計畫核准或關閉請求等結構化協定訊息。寫入失敗時，例如因為磁碟已滿或信箱目錄無法寫入，傳送端 agent 會收到錯誤，且不會傳送任何內容。錯誤訊息與復原步驟請參閱 [Failed to write to a teammate's inbox](https://code.claude.com/docs/zh-TW/errors.md#failed-to-write-to-a-teammate-inbox)。

Claude Code 會自動管理任務相依性：當隊員完成其他任務所相依的任務時，它會解除相依任務的封鎖，您無需採取任何動作。

團隊與任務會以衍生自工作階段的名稱儲存在本機。該名稱為 `session-` 後接工作階段 ID 的前八個字元：

* **團隊設定**：`~/.claude/teams/{team-name}/config.json`。工作階段結束時，Claude Code 會移除團隊設定目錄。
* **任務清單**：`~/.claude/tasks/{team-name}/`。此目錄在工作階段結束後仍會保留在磁碟上。若要變更 [Claude Code 保留它的時間長度](https://code.claude.com/docs/zh-TW/claude-directory.md#cleaned-up-automatically)，請設定 [`cleanupPeriodDays`](https://code.claude.com/docs/zh-TW/settings-reference#cleanupperioddays)。

Claude Code 會在工作階段啟動時自動產生這兩者，並在隊員加入、閒置或離開時更新它們。

團隊設定保存了工作階段 ID 與 tmux 窗格 ID 等執行階段狀態，因此請勿手動編輯或預先撰寫它：您的變更會在下一次狀態更新時被覆寫。

若要定義可重複使用的隊員角色，請改用 [subagent 定義](#use-subagent-definitions-for-teammates)。

團隊設定包含一個 `members` 陣列，其中列出每位成員的名稱與 agent ID。組長的項目一律帶有 agent 類型 `team-lead`。隊員的項目則帶有組長產生它時所指定的 agent 類型，無論是[內建類型](https://code.claude.com/docs/zh-TW/sub-agents.md#built-in-subagents)還是 [subagent 定義](#use-subagent-definitions-for-teammates)；若組長未指定任何類型，則省略該欄位。隊員可以讀取此檔案來得知其他團隊成員。

團隊設定沒有專案層級的對應檔案。專案目錄中類似 `.claude/teams/teams.json` 的檔案不會被視為設定；Claude 會將其當作一般檔案處理。

### 為隊員使用 subagent 定義

在任一顯示模式下產生隊員時，您都可以參照來自專案、使用者、受管理或外掛 [subagent 範圍](https://code.claude.com/docs/zh-TW/sub-agents.md#choose-the-subagent-scope)的 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 類型。這讓您可以只定義一次角色，例如 security-reviewer 或 test-runner，並同時將其重複用作委派的 subagent 與 agent team 隊員。

若要使用 subagent 定義，請在要求 Claude 產生隊員時指明其名稱：

```text wrap theme={null}
Spawn a teammate using the security-reviewer agent type to audit the auth module.
```

Claude Code 會讀取您指定的 subagent 定義，並將其中以下部分套用到隊員。若某部分取決於隊員的[顯示模式](#choose-a-display-mode)，該項目會加以說明：

* **`tools`**：Claude Code 會將隊員限制在定義的 `tools` 清單中的工具。對於 in-process 隊員，Claude Code 會在該清單中加入 `SendMessage`，而在[具備 Task 工具的工作階段](https://code.claude.com/docs/zh-TW/tools-reference.md#task-tool-availability)中，還會加入 `TaskCreate`、`TaskGet`、`TaskList` 與 `TaskUpdate`。
* **`model`**：當您的產生提示詞未指定模型時，Claude Code 在任一顯示模式下都會使用定義的 `model`。請參閱 [Claude Code 如何為隊員選擇模型](#specify-teammates-and-models)。
* **`disallowedTools`**：對於 in-process 隊員，Claude Code 會從隊員的工具集中移除定義的 `disallowedTools` 中的工具。即使清單中列出了 `SendMessage` 以及 Claude Code 加入的 Task 工具，它們仍可使用。
* **`effort`**：對於 in-process 隊員，Claude Code 會依照 [frontmatter effort 規則](https://code.claude.com/docs/zh-TW/model-config.md#set-the-effort-level)套用定義的 [`effort`](https://code.claude.com/docs/zh-TW/sub-agents#supported-frontmatter-fields)。
* **`autoCompactWindow`**：對於 in-process 隊員，Claude Code 會依照[該欄位的規則](https://code.claude.com/docs/zh-TW/sub-agents.md#subagent-auto-compact-window)套用定義的 [`autoCompactWindow`](https://code.claude.com/docs/zh-TW/sub-agents#supported-frontmatter-fields)。split-pane 隊員會忽略此欄位。需要 Claude Code v2.1.296 或更新版本。
* **本文**：對於 in-process 隊員，Claude Code 會將定義的本文附加到其預設系統提示詞之後，作為額外指示。對於 split-pane 隊員，Claude Code 會使用本文取代其預設系統提示詞。
* **`skills`**：在任一顯示模式下，Claude Code 都不會將定義的 `skills` 套用到隊員。隊員會從您的專案與使用者設定載入 skill。
* **`mcpServers`**：對於 split-pane 隊員，Claude Code 會依照[該欄位的規則](https://code.claude.com/docs/zh-TW/sub-agents.md#scope-mcp-servers-to-a-subagent)套用定義的 `mcpServers`，這些規則也涵蓋以 `--agent` 啟動的工作階段。in-process 隊員會忽略此欄位，並從您的專案與使用者設定載入 MCP 伺服器。

當 Claude 傳訊息給已不再執行的 in-process 隊員時，Claude Code 會在同一個工作階段中將其帶回，還原為其保存的任何對話，並將該訊息作為它的下一個提示詞。在您恢復工作階段之後，隊員不會以這種方式被帶回，請參閱[恢復的限制](#limitations)。

對於被帶回的隊員，只有在您已[信任 agent 檔案所在的資料夾](https://code.claude.com/docs/zh-TW/permissions.md#what-runs-before-you-trust-a-folder)時，Claude Code 才會重新套用來自專案 `.claude/agents/` 目錄或 `--add-dir` 目錄的定義。信任上層資料夾不算數。在此之前，隊員被帶回時不會具備定義中的任何工具或指示，只保留 Claude Code 為每個 in-process 隊員加入的工具。通知文字請參閱[隊員的 agent 定義未被還原](https://code.claude.com/docs/zh-TW/errors.md#teammate-agent-definition-not-restored)。

### 權限

若要切換執行中隊員的權限模式，請按 [`Shift+Tab`](https://code.claude.com/docs/zh-TW/permission-modes#switch-permission-modes)，不過 in-process 隊員可能會改以組長的模式執行。對於 split-pane 隊員，請在其窗格中按下。對於 [in-process](#choose-a-display-mode) 隊員，請在[檢視其工作階段](#talk-to-teammates-directly)時按下，隊員會在開始下一個回合時檢查其模式。

> [!NOTE]
>
> 當組長處於 [`acceptEdits`](https://code.claude.com/docs/zh-TW/permission-modes#auto-approve-file-edits-with-acceptedits-mode)、[`auto`](https://code.claude.com/docs/zh-TW/permission-modes#eliminate-prompts-with-auto-mode) 或 [`bypassPermissions`](https://code.claude.com/docs/zh-TW/permission-modes#skip-all-checks-with-bypasspermissions-mode) 模式時，未處於 [plan mode](#have-teammates-plan-before-implementing) 的 in-process 隊員會以組長的模式執行。將隊員切換為 Manual 並不會改變這一點，即使其狀態列顯示 Manual 也是如此。
>
> 若要讓它在編輯前先詢問，請在 agent 面板中的 `main` 列上按 Enter，並將組長也切換為 Manual 模式。此後組長也會詢問，任何其他處於 Manual 模式的隊員亦然。

您無法在產生隊員時為個別隊員設定權限模式。新隊員會以組長的模式啟動，包括由 `--dangerously-skip-permissions` 開啟的 `bypassPermissions` 模式。如果組長處於 [`dontAsk` 模式](https://code.claude.com/docs/zh-TW/permission-modes#allow-only-pre-approved-tools-with-dontask-mode)，隊員則會改以 [Manual 模式](https://code.claude.com/docs/zh-TW/permission-modes.md#available-modes)啟動。

[in-process](#choose-a-display-mode) 隊員會在組長即時的允許與拒絕規則下執行，因此 [`--disallowedTools`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags)、`--tools` 與 `--allowedTools` 都會套用到它。對於 split-pane 隊員，請逐一確認每個旗標：

* **`--disallowedTools` 與 `--tools`**：隊員會以組長的命令列拒絕規則與工具清單啟動。需要 Claude Code v2.1.309 或更新版本。
* **`--allowedTools`**：Claude Code 不會將此旗標傳遞給 split-pane 隊員，因此僅透過它允許的動作在該處不會被預先核准。若要事先核准這些動作，請在啟動組長時，將規則放在 [`--settings`](https://code.claude.com/docs/zh-TW/settings#change-a-setting-for-one-session) 的 `permissions.allow` 下。例如，在您的 shell 中執行 `claude --settings '{"permissions":{"allow":["Bash(npm *)"]}}'`。這些規則會套用到該工作階段的組長以及每個 split-pane 隊員。

隊員的權限提示會出現在組長工作階段中，因此請您親自在那裡核准。您不需要核准[隊員的計畫](#have-teammates-plan-before-implementing)。

#### Agent 之間的訊息

當一個 agent 透過 `SendMessage` 傳訊息給另一個 agent 時，Claude Code 會告知接收端 agent 該訊息來自另一個 Claude 工作階段，而非來自您。隊員無法代表您核准權限提示或提供同意，而被拒絕執行某動作的隊員也無法將其轉交給另一名隊員來繞過檢查。相同的規則也適用於來自[您的其他 Claude Code 工作階段之一](https://code.claude.com/docs/zh-TW/cross-session-messaging.md#how-a-session-treats-an-incoming-message)、完全位於團隊之外的訊息。

在[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)中，分類器會對 agent 之間的訊息套用兩項檢查：

* 它會將從另一個 agent 轉達的核准聲明視為不受信任的輸入，而非來自您的確認。
* 它會在 Claude Code 傳遞每則訊息之前進行審查，無論是純文字訊息，還是關閉請求或計畫核准回應等結構化協定訊息。被它封鎖的訊息永遠不會送達收件者。

### 上下文與溝通

每位隊員都有自己的上下文視窗。產生時，隊員會載入與一般工作階段相同的專案上下文：CLAUDE.md、MCP 伺服器與 skill。如果您以 [`--setting-sources`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 啟動組長，隊員會從相同的受限來源清單載入。在 v2.1.281 之前，[split-pane](#choose-a-display-mode) 隊員會載入所有設定來源。

隊員也會收到來自組長的產生提示詞。組長的對話歷程不會延續過去。

**隊員如何共享資訊：**

* **自動訊息傳遞**：當隊員傳送訊息時，訊息會自動傳遞給收件者。組長不需要輪詢更新。
* **閒置通知**：當隊員完成並停止時，會自動通知組長，並在通知中附上其最終答案。回合因 API 錯誤而結束的隊員會通知組長它已失敗，並附上錯誤文字。
* **共用任務清單**：[具備 Task 工具的 agent](https://code.claude.com/docs/zh-TW/tools-reference.md#task-tool-availability) 可以查看任務狀態並認領可用的工作。
* **隊員訊息**：依名稱傳送訊息給某一位特定隊員。若要通知所有人，請為每位收件者各傳送一則訊息。

組長在產生每位隊員時都會為其指定名稱，任何隊員都可以依該名稱傳訊息給其他任何隊員。若要取得可在之後的提示詞中參照的可預期名稱，請在產生指示中告訴組長每位隊員該如何命名。

### Token 使用量

Agent teams 使用的 token 明顯多於單一工作階段。每位隊員都有自己的上下文視窗，token 使用量會隨著作用中隊員的數量而增加。對於研究、審查與新功能開發，額外的 token 通常是值得的。對於例行任務，單一工作階段更具成本效益。使用指引請參閱 [agent team token 成本](https://code.claude.com/docs/zh-TW/costs.md#agent-team-token-costs)。

in-process 隊員的請求不屬於主要對話的[快取 TTL 分組](https://code.claude.com/docs/zh-TW/prompt-caching.md#which-ttl-each-request-gets)，因此其快取預設保留五分鐘，即使在 Claude 訂閱方案中也是如此。若要保留一小時，請將 [`subagentPromptCacheTtl`](https://code.claude.com/docs/zh-TW/settings-reference#subagentpromptcachettl) 設為 `1h`。API 會以較高的費率計費 1 小時快取寫入。

## 使用案例範例

這些範例展示了 agent teams 如何處理並行探索增加價值的任務。

### 運行並行程式碼審查

單個審查者傾向於一次專注於一種類型的問題。將審查標準分成獨立領域意味著安全性、效能和測試覆蓋都同時獲得徹底的關注。提示為每個隊友分配一個不同的視角，以便他們不重疊：

```text wrap theme={null}
Spawn three teammates to review PR #142:
- One focused on security implications
- One checking performance impact
- One validating test coverage
Have them each review and report findings.
```

每個審查者從相同的 PR 工作，但應用不同的篩選器。主管在他們完成後綜合所有三個的發現。

### 使用競爭假設進行調查

當根本原因不清楚時，單個代理傾向於找到一個看似合理的解釋並停止尋找。提示透過使隊友明確對抗來對抗這一點：每個隊友的工作不僅是調查自己的理論，還要質疑其他隊友的理論。

```text wrap theme={null}
Users report the app exits after one message instead of staying connected.
Spawn 5 agent teammates to investigate different hypotheses. Have them talk to
each other to try to disprove each other's theories, like a scientific
debate. Update the findings doc with whatever consensus emerges.
```

辯論結構是這裡的關鍵機制。順序調查受到錨定的影響：一旦探索了一個理論，後續調查就會偏向於它。

有多個獨立調查人員積極嘗試相互反駁，倖存的理論更有可能是實際的根本原因。

## 最佳實踐

### 給隊友足夠的 context

隊友自動載入專案 context，包括 CLAUDE.md、MCP servers 和 skills，但他們不繼承主管的對話歷史。請參閱[Context 和通訊](#context-and-communication)以了解詳情。在生成提示中包含任務特定的詳情：

```text wrap theme={null}
Spawn a security reviewer teammate with the prompt: "Review the authentication module
at src/auth/ for security vulnerabilities. Focus on token handling, session
management, and input validation. The app uses JWT tokens stored in
httpOnly cookies. Report any issues with severity ratings."
```

### 選擇適當的團隊規模

隊友數量沒有硬性限制，但實際限制適用：

* **Token 成本線性增加**：每個隊友都有自己的 context window 並獨立消耗 tokens。請參閱 [agent team token 成本](https://code.claude.com/docs/zh-TW/costs.md#agent-team-token-costs)以了解詳情。
* **協調開銷增加**：更多隊友意味著更多通訊、任務協調和潛在衝突
* **收益遞減**：超過一定點後，額外的隊友不會按比例加快工作

對於大多數工作流程，從 3-5 個隊友開始。這平衡了並行工作與可管理的協調。如果您有 15 個獨立任務，3 個隊友是一個很好的起點。

只有當工作真正受益於隊友同時工作時才擴展。三個專注的隊友通常優於五個分散的隊友。

### 適當調整任務大小

* **太小**：協調開銷超過收益
* **太大**：隊友工作時間過長而沒有檢查點，增加浪費努力的風險
* **恰到好處**：自包含的單位，產生清晰的可交付成果，例如函數、測試檔案或審查

> [!TIP]
>
> 主管將工作分解為任務並自動分配給隊友。如果它沒有建立足夠的任務，要求它將工作分成更小的部分。每個隊友有 5-6 個任務可以保持每個人的生產力，並讓主管在有人卡住時重新分配工作。

### 等待隊友完成

有時主管開始自己實施任務，而不是等待隊友。如果您注意到這一點：

```text wrap theme={null}
Wait for your teammates to complete their tasks before proceeding
```

### 從研究和審查開始

如果您是 agent teams 的新手，請從具有清晰邊界且不需要編寫程式碼的任務開始：審查 PR、研究庫或調查錯誤。這些任務展示了並行探索的價值，而不會帶來並行實施所帶來的協調挑戰。

### 避免檔案衝突

兩個隊友編輯同一檔案會導致覆蓋。分解工作，使每個隊友擁有不同的檔案集。

### 監控和引導

檢查隊友的進度，重新定向不起作用的方法，並在發現時綜合發現。讓團隊無人值守運行太長時間會增加浪費努力的風險。

## 故障排除

### 隊友未出現

如果在您要求 Claude 建立隊友後隊友未出現：

* 在 in-process 模式中，隊友會出現在提示輸入下方的代理面板中。使用上下箭頭鍵選擇一個，然後按 Enter 鍵查看它。
* 閒置後消失的隊友列已被隱藏，而非停止。閒置列在整個面板閒置 30 秒後隱藏，並在隊友的下一輪時重新出現。當超過三個隊友閒置時，其多餘列會摺疊成單一的 `N idle agents` 列，按 Enter 鍵可展開。按名稱向隊友發送訊息以將隱藏列恢復。
* 檢查您給 Claude 的任務是否足夠複雜以保證建立團隊。Claude 根據任務決定是否生成隊友。
* 如果您明確要求分割窗格，請確保 tmux 已安裝並在您的 PATH 中可用：
  ```bash theme={null}
  which tmux
  ```
* 對於 iTerm2，驗證 `it2` CLI 已安裝且 Python API 在 iTerm2 偏好設定中啟用。

### Claude 生成隊友而非子代理

當代理團隊啟用時，Claude 在主管工作階段中命名的子代理會作為隊友啟動。Claude [可以自行命名子代理](#how-claude-starts-agent-teams)，因此這可能在您從未將其視為團隊工作的委派期間發生。

若要讓命名的子代理再次作為子代理啟動，請將 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` 設定為 `0` 以關閉代理團隊：

```json settings.json theme={null}
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "0"
  }
}
```

您不需要啟動新工作階段：Claude Code 在您儲存時會將設定檔 `env` 值重新套用到執行中的工作階段，並在 Claude 每次生成子代理時重新讀取該變數，因此 Claude 命名的下一個子代理會作為子代理啟動。

在您的使用者 `settings.json` 中將變數設定為 `0` 會覆蓋 shell 匯出。其他設定來源仍可啟用代理團隊：

* **更高優先順序的設定檔**：專案設定、本機設定和 `--settings` 承載會在使用者設定之後套用，因此任何其中設定變數為 `1` 的 `env` 項目會獲勝。請參閱 [設定優先順序](https://code.claude.com/docs/zh-TW/settings.md#settings-precedence)。
* **受管設定**：[受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md) 會在所有其他來源之後套用。如果您的組織在該處啟用代理團隊，請要求您的管理員變更受管值。

變更後，Claude 可能仍會命名子代理，且該名稱會繼續作為 [`SendMessage` 位址](https://code.claude.com/docs/zh-TW/sub-agents#resume-subagents)運作。Claude 會在每個子代理完成時接收其結果。

### 過多權限提示

隊友權限請求冒泡到主管，這可能會造成摩擦。在生成隊友之前在 [permission settings](https://code.claude.com/docs/zh-TW/permissions.md) 中預批准常見操作以減少中斷。

### 代理提前停止

隊友可能在遇到錯誤後停止，而不是恢復。通過在 in-process 模式中選擇代理面板中的隊友並按 Enter 鍵，或在分割模式中點擊窗格來檢查其輸出，然後：

* 直接給他們額外的指示
* 生成替換隊友以繼續工作

來自主管或另一隊友的訊息會喚醒正在等待重試失敗 API 請求的 in-process 隊友，因此它會立即重試，而不是等待完整的重試延遲。

主管也可能提前停止，在所有任務實際完成之前決定團隊已完成。如果發生這種情況，告訴它繼續。

### 孤立的 tmux 工作階段

如果 tmux 工作階段在 Claude Code 工作階段結束後仍然存在，它可能未被完全清理。列出工作階段並殺死由團隊建立的工作階段：

```bash theme={null}
tmux ls
tmux kill-session -t <session-name>
```

## 限制

Agent teams 是實驗性的。要注意的目前限制：

* **沒有 in-process 隊友的工作階段恢復**：`/resume` 和 `/rewind` 不會恢復 in-process 隊友。恢復工作階段後，主管可能會嘗試向不再存在的隊友傳送訊息。如果發生這種情況，告訴主管生成新隊友。
* **任務狀態可能滯後**：隊友有時無法將任務標記為已完成，這會阻止依賴任務。如果任務似乎卡住，請檢查工作是否實際完成並手動更新任務狀態或告訴主管推動隊友。
* **關閉可能很慢**：隊友在關閉前完成其目前請求或工具呼叫，這可能需要時間。
* **每個工作階段一個團隊**：一個工作階段恰好有一個團隊，範圍限於該工作階段。您無法建立其他具名團隊或在工作階段之間共享團隊。
* **沒有嵌套團隊**：隊友無法生成自己的隊友。只有主管可以管理團隊。
* **沒有來自 in-process 隊友的背景 subagent**：in-process 隊友自己的 subagent 在前景中執行，因為隊友的背景工作無法超越主管的程序。Claude Code 在隊友生成定義設定 `background: true` 的 subagent 時會傳回錯誤。隊友的 `run_in_background: true` 請求也會失敗，可能傳回錯誤或在前景中無聲執行。從主要對話啟動的 subagent 遵循[背景預設](https://code.claude.com/docs/zh-TW/sub-agents.md#run-subagents-in-foreground-or-background)。
* **主管是固定的**：主要工作階段在其生命週期內是主管。您無法將隊友提升為主管或轉移領導權。
* **生成時無法為每個隊友設定權限模式**：隊友開始時具有 [權限](#permissions) 下所述的權限模式。
* **分割窗格需要 tmux 或 iTerm2**：預設 in-process 模式在任何終端中工作。VS Code 的整合終端、Windows Terminal 或 Ghostty 不支援分割窗格模式。

## 後續步驟

探索並行工作和委派的相關方法：

* **輕量級委派**：[subagents](https://code.claude.com/docs/zh-TW/sub-agents.md) 在您的工作階段內為研究或驗證生成幫助代理，更適合不需要代理間協調的任務
* **您自己的工作階段之間的訊息傳遞**：[cross-session messaging](https://code.claude.com/docs/zh-TW/cross-session-messaging.md) 讓 Claude 在您自己運行的工作階段之間傳遞發現結果
* **手動並行工作階段**：[Git worktrees](https://code.claude.com/docs/zh-TW/worktrees.md) 讓您自己運行多個 Claude Code 工作階段，無需自動化團隊協調

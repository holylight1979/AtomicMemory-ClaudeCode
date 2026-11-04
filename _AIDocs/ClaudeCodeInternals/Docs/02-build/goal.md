<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/goal | lastmod: 2026-10-29 | section: Build with Claude Code / Automation -->
> 來源：https://code.claude.com/docs/zh-TW/goal（官方 zh-TW，lastmod 2026-10-29）｜分類：Build with Claude Code › Automation｜EN 摘要：Set a completion condition with /goal and Claude keeps working until it's met, a model judges it impossible, or an error you have to fix clears the goal.

# 讓 Claude 朝著目標持續工作

> 使用 /goal 設定完成條件，Claude 會持續工作直到條件滿足、模型判斷不可能達成，或需要修復的錯誤清除目標。

`/goal` 命令設定完成條件，Claude 會朝著該目標持續工作，無需您在每一步進行提示。在每個回合後，一個模型會檢查條件是否滿足。如果模型判斷條件尚未滿足，Claude 會開始另一個回合，而不是將控制權返回給您。一旦條件滿足、模型判斷條件不可能滿足，或回合因[需要修復的錯誤](#errors-you-have-to-fix-clear-the-goal)而失敗時，目標會自動清除。

在具有可驗證終止狀態的實質性工作中使用目標：

* 將模組遷移到新 API，直到每個呼叫位置都編譯並通過測試
* 實現設計文件，直到所有驗收標準都滿足
* 將大型檔案分割成專注的模組，直到每個模組都在大小預算內
* 處理標記的問題待辦清單，直到佇列為空

## 比較保持工作階段執行的方式

三種方法在提示之間保持目前工作階段執行。根據應該開始下一個回合的內容進行選擇：

| 方法 | 下一個回合開始於 | 停止於 |
| :- | :- | :- |
| `/goal` | 上一個回合完成時，或在互動式工作階段中，[閒置檢查](#background-work-defers-evaluation)或[自動重試](#other-errors-retry-or-pause-the-goal)到期時 | 模型確認條件已滿足或判斷其不可能時，或回合因[你必須修復的錯誤](#errors-you-have-to-fix-clear-the-goal)而失敗時，或你執行[`/goal clear`](#clear-a-goal)時 |
| [`/loop`](https://code.claude.com/docs/zh-TW/scheduled-tasks#run-a-prompt-repeatedly-with-%2Floop) | 時間間隔經過時 | 你停止它，或 Claude 決定工作完成時 |
| [Stop hook](https://code.claude.com/docs/zh-TW/hooks-guide.md#prompt-based-hooks) | 上一個回合完成時 | 你自己的指令碼或提示決定時 |

`/goal` 和 Stop hook 都在每個回合後觸發。`/goal` 是一個工作階段範圍的快捷方式：你輸入條件，它僅在目前工作階段中有效。Stop hook 存在於你的設定檔案中，適用於其範圍內的每個工作階段，可以執行指令碼進行確定性檢查或執行提示進行模型評估的檢查。

[自動模式](https://code.claude.com/docs/zh-TW/auto-mode-config.md)本身在單個回合內批准工具呼叫，但不會開始新的回合。Claude 在判斷工作完成時停止。`/goal` 添加了一個單獨的評估器，在每個回合後檢查你的條件，因此完成由新鮮模型而不是執行工作的模型決定。這兩者是互補的：自動模式移除每個工具的提示，`/goal` 移除每個回合的提示。

> [!TIP]
>
> 上述方法保持目前工作階段執行。您也可以排程獨立於任何開啟工作階段執行的工作，例如夜間測試或早晨分類。有關雲端和桌面排程任務，請參閱[排程選項](https://code.claude.com/docs/zh-TW/scheduled-tasks.md#compare-scheduling-options)。

## 使用 `/goal`

每個工作階段可以有一個活躍的目標。相同的命令根據引數設定、檢查和清除它。

### 設定目標

執行 `/goal` 後跟你想要滿足的條件。如果已有活躍的目標，新目標會替換它。

```text theme={null}
/goal all tests in test/auth pass and the lint step is clean
```

設定目標會立即開始一個回合，條件本身作為指令。你無需發送單獨的提示。當目標活躍時，`◎ /goal active` 指示器顯示目標已執行多長時間。

目標不會改變你的權限模式。要讓目標回合無人值守地執行，請在 [auto mode](https://code.claude.com/docs/zh-TW/auto-mode-config.md) 中執行 `/goal`。在 [Manual mode](https://code.claude.com/docs/zh-TW/permission-modes.md) 中，Claude 仍會在工具呼叫前詢問，這些工具呼叫是你的設定尚未允許的，例如上面的測試命令。

當目標活躍時，文字記錄會顯示評估器返回的每個判決，你可以按 Ctrl+O 查看其背後的原因。狀態檢視也會顯示最新的原因，因此你可以看到 Claude 接下來要朝著什麼工作。

### 編寫有效條件

[評估器](#how-evaluation-works)根據 Claude 在對話中呈現的內容判斷你的條件。它不會獨立執行命令或讀取檔案，因此將條件編寫為 Claude 自己的輸出可以演示的內容。「`test/auth` 中的所有測試都通過」有效，因為 Claude 執行測試，結果出現在文字記錄中供評估器讀取。

在許多回合中保持的條件通常具有：

* **一個可測量的終止狀態**：測試結果、建置退出代碼、檔案計數、空佇列
* **一個陳述的檢查**：Claude 應該如何證明它，例如「`npm test` 退出 0」或「`git status` 是乾淨的」
* **重要的約束**：在此過程中必須不改變的任何內容，例如「沒有其他測試檔案被修改」

條件最多可以是 4,000 個字元。

要限制目標執行的時間，在條件中包含回合或時間子句，例如 `or stop after 20 turns`。Claude 每個回合都報告針對該子句的進度，評估器從對話中判斷它。

### 檢查狀態

執行不帶引數的 `/goal` 以查看目前狀態。

```text theme={null}
/goal
```

如果目標活躍，狀態顯示：

* 條件
* 它已執行多長時間
* 已評估多少個回合
* 目前令牌支出
* 評估器最新的原因

回合計數和最新的原因會在第一次評估執行後出現。

如果沒有活躍的目標，但在工作階段中較早時已達成一個目標，狀態會顯示已達成的條件及其持續時間、回合計數和令牌支出。

### 清除目標

執行 `/goal clear` 以在條件滿足前移除活躍的目標。

```text theme={null}
/goal clear
```

Claude 列印 `Goal cleared:` 後跟條件以確認，或如果沒有活躍的目標則列印 `No goal set`。

`stop`、`off`、`reset`、`none` 和 `cancel` 被接受為 `clear` 的別名。執行 `/clear` 以開始新對話也會移除任何活躍的目標。

### 使用活躍目標繼續

當你繼續一個工作階段時，Claude Code 會復原一個在工作階段結束時仍然活躍的目標。Claude Code 在每個繼續路由上復原它：`--continue`、`--resume` 搭配工作階段 ID、名稱或 [文字記錄檔案路徑](https://code.claude.com/docs/zh-TW/sessions.md#resume-a-session)，以及 [工作階段選擇器](https://code.claude.com/docs/zh-TW/sessions.md#use-the-session-picker)。在 v2.1.239 之前，Claude Code 在除了 `claude --resume` 選擇器之外的每個路由上復原目標。

Claude Code 帶著條件，但重置回合計數、計時器和令牌支出基線。它不會復原已達成或已清除的目標。

### 非互動式執行

`/goal` 在[非互動式模式](https://code.claude.com/docs/zh-TW/headless.md)、[桌面應用程式](https://code.claude.com/docs/zh-TW/desktop.md)中工作，並透過[遠端控制](https://code.claude.com/docs/zh-TW/remote-control.md)工作。使用 `-p` 設定目標會在單個呼叫中執行迴圈至完成：

```bash theme={null}
claude -p "/goal CHANGELOG.md has an entry for every PR merged this week"
```

使用預設文字輸出時，Claude 的最終回應會在迴圈結束時列印，因此執行許多回合的目標可能看起來卡住了。新增 `--output-format stream-json --verbose` 以在迴圈執行時發出每個訊息。

使用 Ctrl+C 中斷程序以在目標解決前停止非互動式目標。

## 評估如何運作

`/goal` 是工作階段範圍[基於提示詞的 Stop hook](https://code.claude.com/docs/zh-TW/hooks.md#prompt-based-hooks)的包裝器。每次 Claude 完成回合時，Claude Code 會將條件和迄今為止的對話發送到您設定的[小型快速模型](https://code.claude.com/docs/zh-TW/model-config.md)。模型返回三個判決之一，各附帶簡短原因：

* **尚未達成**：Claude 繼續工作，並將原因作為下一個回合的指導。
* **已達成**：Claude Code 清除目標並在文字記錄中記錄已達成的項目。
* **不可能**：評估器判斷該條件永遠無法滿足。Claude Code 清除目標並在文字記錄中記錄失敗項目以及原因。你不需要自己清除它。

如果 Claude 持續回答評估器而沒有取得進展（連續多個回合沒有工具使用），Claude Code 會停止迴圈、列印警告，並將控制權返回給你，目標仍然設定。評估在你的下一個提示後繼續。[hooks 指南](https://code.claude.com/docs/zh-TW/hooks-guide.md#stop-hook-hits-the-block-cap)解釋了底層機制。

### 當回合失敗時

當回合失敗時，如果錯誤是你必須修復的錯誤，Claude Code 會清除目標。在任何其他錯誤之後，目標保持設定。

#### 你必須修復的錯誤會清除目標

如果回合因無法清除的錯誤而失敗，Claude Code 會清除目標並列印警告，說明原因。警告以 `Goal cleared after an unrecoverable error` 開始，以 `Run /goal again to continue` 結束。修復原因，然後使用 `/goal <condition>` [再次設定目標](#set-a-goal)。四種失敗會清除目標：

* 驗證失敗，當 Claude Code 管理自己的認證時。當主機為你管理認證時，例如桌面應用程式或[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)，Claude Code 會保持目標活躍，因為主機會自動恢復存取權。
* 信用額度已耗盡
* [自動壓縮](https://code.claude.com/docs/zh-TW/model-config.md#set-the-auto-compact-window)無法清除的內容溢位
* 不可用的模型

#### 其他錯誤重試或暫停目標

在任何其他失敗之後，目標保持設定。在 Claude Code v2.1.269 或更新版本的互動式工作階段中，Claude Code 也會列印一行命名原因，並自動重試或等待你：

* **重試**：在傾向於自行清除的失敗之後，例如伺服器過載或連線中斷，以 `Goal still active` 開始的通知會顯示下一次嘗試前的等待時間。在三次自動重試後，目標會改為暫停。
* **暫停**：在重試只會重複的失敗之後，例如 API 速率限制、claude.ai [使用限制](https://code.claude.com/docs/zh-TW/errors.md#youve-hit-your-session-limit)或結束回合的 hook，以 `Goal paused` 開始的通知會命名原因。如果工作階段[等待在使用限制重設時自動繼續](https://code.claude.com/docs/zh-TW/interactive-mode.md#wait-for-a-usage-limit-to-reset)，Claude 會在那時繼續朝著目標努力。

隨時發送訊息以立即開始下一個回合。要關閉自動重試，請將 [`CLAUDE_CODE_GOAL_CHECKIN_MINUTES`](https://code.claude.com/docs/zh-TW/env-vars) 設定為 `0`，這也會關閉[簽到](#background-work-defers-evaluation)。

### 背景工作延遲評估

如果子代理或背景 shell 命令在回合結束時仍在執行，Claude Code 會跳過該回合的評估。它在下一個沒有背景工作執行的回合結束時進行評估。當背景工作完成時，Claude Code 會將結果作為新回合傳遞給 Claude，因此你不需要提示。

一旦背景工作讓目標等待 30 分鐘，就應該進行簽到。在簽到中，Claude Code 列出執行中的任務，並要求 Claude 讀取其輸出、如果任務正在進行則繼續等待，並修復或停止任何卡住的任務。在第一次簽到後，Claude Code 在每次後續簽到前等待時間加倍，最多為第一個間隔的四倍：使用預設值，第一次簽到後 1 小時，然後每 2 小時。Claude Code 以以下兩種方式之一傳遞應到期的簽到（包括第一次）：

* **當回合結束時**：Claude Code 在下一個工作仍在執行的回合結束時傳遞簽到。在非互動式工作階段（例如使用 `-p` 啟動的工作階段）中，這是 Claude Code 傳遞簽到的唯一方式。
* **當工作階段閒置時**：在互動式工作階段中，Claude Code 也會自動啟動回合以傳遞簽到，而不是等待你的下一個提示。如果背景工作已停止而未報告結果，Claude Code 會要求 Claude 繼續朝著目標努力。Claude Code 在你的提示之間每個目標最多啟動三次閒置簽到。在第三次閒置簽到中，Claude Code 會說閒置簽到已暫停，直到你發送另一個提示。在 v2.1.246 之前，閒置簽到是無上限的。閒置簽到需要 Claude Code v2.1.236 或更新版本。

在 v2.1.239 之前，只有閒置簽到以這種方式退避；在回合結束時傳遞的簽到在第一個間隔重複。

要更改第一個間隔，請設定 [`CLAUDE_CODE_GOAL_CHECKIN_MINUTES`](https://code.claude.com/docs/zh-TW/env-vars)。Claude Code 使用你的值代替 30 分鐘間隔，並相應地縮放後續間隔。將其設定為 `0` 以關閉簽到和[自動重試](#other-errors-retry-or-pause-the-goal)。

簽到需要 Claude Code v2.1.234 或更新版本。

### 評估模型和成本

要在不同的模型上進行評估，請設定 [`ANTHROPIC_DEFAULT_HAIKU_MODEL`](https://code.claude.com/docs/zh-TW/model-config#environment-variables)。

> [!WARNING]
>
> Claude Code 在使用小型快速模型的任何地方都會讀取 `ANTHROPIC_DEFAULT_HAIKU_MODEL`，不僅僅是用於 `/goal` 評估。當您設定它時，Claude Code 也會將 [`haiku` 別名](https://code.claude.com/docs/zh-TW/model-config#model-aliases)解析為該模型，並在其上執行工作階段標題產生和其他一些背景任務。

評估器在你的工作階段配置的任何提供者上執行。它不呼叫工具，因此只能判斷 Claude 已在對話中呈現的內容。

> [!NOTE]
>
> 評估令牌在為你的提供者配置的小型快速模型上計費，與主要回合支出相比通常可以忽略不計。

## 要求

Claude Code 在與 [工作區信任規則相同的 hooks 設定檔](https://code.claude.com/docs/zh-TW/permissions.md#what-runs-before-you-trust-a-folder) 下提供 `/goal`，因為評估器是 hooks 系統的一部分。當 [`disableAllHooks`](https://code.claude.com/docs/zh-TW/hooks#disable-or-remove-hooks) 在設定優先順序套用後為 `true` 時，或當在受管設定中設定了 [`allowManagedHooksOnly`](https://code.claude.com/docs/zh-TW/settings-reference#allowmanagedhooksonly) 時，`/goal` 也不可用。在每種情況下，命令會告訴你原因，而不是默默地什麼都不做。

## 另請參閱

* [使用 `/loop` 重複執行提示](https://code.claude.com/docs/zh-TW/scheduled-tasks#run-a-prompt-repeatedly-with-%2Floop)：按時間間隔重新執行，而不是直到條件滿足
* [基於提示的 hooks](https://code.claude.com/docs/zh-TW/hooks-guide.md#prompt-based-hooks)：當你需要自訂評估邏輯時編寫你自己的 Stop hook
* [自動模式](https://code.claude.com/docs/zh-TW/auto-mode-config.md)：自動批准工具呼叫，以便每個目標回合無人值守執行
* [排程比較](https://code.claude.com/docs/zh-TW/scheduled-tasks.md#compare-scheduling-options)：獨立於任何開啟工作階段在排程上執行工作

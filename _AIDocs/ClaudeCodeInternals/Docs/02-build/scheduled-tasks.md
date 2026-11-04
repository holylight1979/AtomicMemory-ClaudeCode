<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/scheduled-tasks | lastmod: 2026-10-22 | section: Build with Claude Code / Automation -->
> 來源：https://code.claude.com/docs/zh-TW/scheduled-tasks（官方 zh-TW，lastmod 2026-10-22）｜分類：Build with Claude Code › Automation｜EN 摘要：Use /loop and the cron scheduling tools to run prompts repeatedly, poll for status, or set one-time reminders within a Claude Code session.

# 按排程執行提示

> 使用 /loop 和 cron 排程工具在 Claude Code 工作階段內重複執行提示、輪詢狀態或設定一次性提醒。

工作階段範圍的排程任務讓 Claude 在 Claude Code 工作階段內按間隔自動重新執行提示詞。使用它們來輪詢部署、監督 PR、檢查長時間執行的建置，或在工作階段稍後提醒自己執行某些操作。

> [!NOTE]
>
> 以下情況在其他頁面中說明：
>
> * **對事件發生時做出反應而不是輪詢**：請參閱 [Channels](https://code.claude.com/docs/zh-TW/channels.md)。您的 CI 可以直接將失敗推送到工作階段中。
> * **保持工作階段逐回合執行直到符合條件，而不是按間隔執行**：請參閱 [`/goal`](https://code.claude.com/docs/zh-TW/goal)。

任務的範圍限於工作階段。當您使用 `--resume` 或 `--continue` 繼續時，Claude Code 會復原任何尚未[過期](#seven-day-expiry)的任務，除了[限制](#limitations)下列出的任務。對於獨立於任何工作階段而存在的排程，請建立[雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md)、設定 [Desktop 排程任務](https://code.claude.com/docs/zh-TW/desktop-scheduled-tasks.md)，或使用 [GitHub Actions](https://code.claude.com/docs/zh-TW/github-actions.md)。

## 比較排程選項

Claude Code 提供三種方式來排程定期或一次性的工作：

| | [Cloud](https://code.claude.com/docs/zh-TW/routines.md) | [Desktop](https://code.claude.com/docs/zh-TW/desktop-scheduled-tasks.md) | [`/loop`](https://code.claude.com/docs/zh-TW/scheduled-tasks) |
| :- | :- | :- | :- |
| 執行位置 | Cloud，預設由 Anthropic 管理 | 您的機器 | 您的機器 |
| 需要機器開啟 | 否 | 是 | 是 |
| 需要開啟的工作階段 | 否 | 否 | 是 |
| 跨重新啟動持續存在 | 是 | 是 | 在 `--resume` 上復原，有[例外](https://code.claude.com/docs/zh-TW/scheduled-tasks.md#limitations) |
| 存取本機檔案 | 否（全新複製） | 是 | 是 |
| MCP 伺服器 | 每個工作配置的連接器 | [設定檔](https://code.claude.com/docs/zh-TW/mcp.md)和連接器 | 繼承自工作階段 |
| 權限提示 | 預設為[自動模式](https://code.claude.com/docs/zh-TW/routines.md#permission-prompts-during-a-run) | 每個工作可設定 | 繼承自工作階段 |
| 可自訂排程 | 是 | 是 | 是 |
| 最小間隔 | 1 小時 | 由 Claude 設定時為 1 分鐘，[在表單中為 1 小時](https://code.claude.com/docs/zh-TW/desktop-scheduled-tasks.md#schedule-options) | 1 分鐘 |

> [!TIP]
>
> 使用**雲端工作**來執行應該在沒有您的機器的情況下可靠執行的工作。當您需要存取本機檔案和工具時，使用**Desktop 工作**。使用 **`/loop`** 進行工作階段期間的快速輪詢。

## 使用 /loop 重複執行提示詞

`/loop` [隨附 skill](https://code.claude.com/docs/zh-TW/commands.md) 是在工作階段保持開啟期間重複執行提示詞最快速的方式。間隔與提示詞皆為選填，您提供的內容決定了迴圈的行為方式。

| 您提供的內容 | 範例 | 結果 |
| :- | :- | :- |
| 間隔與提示詞 | `/loop 5m check the deploy` | 您的提示詞依[固定排程](#run-on-a-fixed-interval)執行 |
| 僅提示詞 | `/loop check the deploy` | 您的提示詞每次迭代依 [Claude 選擇的間隔](#let-claude-choose-the-interval)執行 |
| 僅間隔，或什麼都不提供 | `/loop` | 執行[內建維護提示詞](#run-the-built-in-maintenance-prompt)，若存在 `loop.md` 則執行該檔案 |

您也可以將 skill 作為提示詞傳入，例如 `/loop 20m /review-pr 1234`，以在每次迭代時重新執行該 skill。排程觸發只會執行 Claude [被允許自行叫用](https://code.claude.com/docs/zh-TW/skills.md#control-who-invokes-a-skill)的 skill。以下項目會以純文字形式傳給 Claude，而不會被執行：

* 內建命令，例如 `/permissions`、`/model` 或 `/clear`
* 標記為 [`disable-model-invocation: true`](https://code.claude.com/docs/zh-TW/skills#frontmatter-reference) 的 skill，包括隨附的 `/verify` skill
* 被 [`skillOverrides`](https://code.claude.com/docs/zh-TW/skills#override-skill-visibility-from-settings) 設定或 `Skill` [拒絕規則](https://code.claude.com/docs/zh-TW/skills.md#restrict-claude’s-skill-access)對 Claude 隱藏的 skill
* [MCP 提示詞](https://code.claude.com/docs/zh-TW/mcp.md#use-mcp-prompts-as-commands)，例如 `/mcp__github__list_prs`

### 以固定間隔執行

當您提供間隔時，Claude 會將其轉換為 cron 運算式、排程該工作，並確認執行頻率與工作 ID。

```text theme={null}
/loop 5m check if the deployment finished and tell me what happened
```

間隔可以用 `30m` 這樣的單獨 token 放在提示詞前面，或以 `every 2 hours` 這樣的子句放在提示詞後面。支援的單位為 `s`（秒）、`m`（分鐘）、`h`（小時）與 `d`（天）。

由於 cron 的最小單位為一分鐘，秒數會無條件進位至最接近的分鐘。無法對應到整齊 cron 間隔的值，例如 `7m` 或 `90m`，會被調整為最接近的可對應間隔，Claude 會告知您所選的值。

### 讓 Claude 選擇間隔

當您省略間隔時，Claude 會動態選擇間隔，而不是依固定的 cron 排程執行。每次迭代後，它會根據觀察到的情況選擇介於一分鐘到一小時之間的延遲：在建置即將完成或 PR 處於活躍狀態時等待較短時間，在沒有待處理事項時等待較長時間。所選的延遲及其原因會在每次迭代結束時顯示。

以下範例會檢查 CI 與審查留言，當 PR 趨於沉寂後，Claude 會在迭代之間等待較長時間：

```text theme={null}
/loop check whether CI passed and address any review comments
```

在 [Monitor 工具可用](https://code.claude.com/docs/zh-TW/tools-reference.md#monitor-tool)的工作階段中，當您要求動態 `/loop` 排程時，Claude 可能會直接使用該工具。Monitor 會執行背景指令碼並將每一行輸出串流回傳，完全免除輪詢，通常比以固定間隔重新執行提示詞更節省 token 且反應更即時。

動態排程的迴圈會像其他任務一樣出現在您的[排程任務清單](#manage-scheduled-tasks)中，因此您可以用相同方式列出或取消它。清單會將其待處理的喚醒顯示為一次性任務，因此排定於 `:00` 或 `:30` 的喚醒可能會[稍微提前執行](#when-a-one-shot-task-runs-early)。[七天到期](#seven-day-expiry)規則同樣適用於此迴圈。

> [!NOTE]
>
> 動態選擇的間隔與[內建維護提示詞](#run-the-built-in-maintenance-prompt)適用於所有供應商，即使關閉[功能旗標擷取](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)也能運作。在 Amazon Bedrock、Claude Platform on AWS、Google Cloud 的 Agent Platform 與 Microsoft Foundry 上，或在關閉擷取的情況下，兩者都需要 Claude Code v2.1.248 或更新版本。

### 執行內建維護提示詞

當您省略提示詞時，Claude 會使用內建的維護提示詞，而非您提供的提示詞。每次迭代時，它會依序處理以下事項：

* 繼續對話中任何未完成的工作
* 處理目前分支的 pull request：審查留言、失敗的 CI 執行、合併衝突
* 在沒有其他待處理事項時，執行清理作業，例如尋找錯誤或簡化程式碼

Claude 不會在此範圍之外啟動新的工作項目，而推送或刪除等不可逆的動作，只有在延續逐字稿中已授權的事項時才會執行。

```text theme={null}
/loop
```

單獨的 `/loop` 會以[動態選擇的間隔](#let-claude-choose-the-interval)執行此提示詞。加上間隔，例如 `/loop 15m`，即可改為依固定排程執行。若要以您自己的預設提示詞取代內建提示詞，請參閱[使用 loop.md 自訂預設提示詞](#customize-the-default-prompt-with-loop-md)。

### 使用 loop.md 自訂預設提示詞

建立 `loop.md` 檔案，即可用您自己的指令取代[內建維護提示詞](#run-the-built-in-maintenance-prompt)。它為單獨的 `/loop` 定義單一預設提示詞，而非一份獨立排程任務的清單，且只要您在命令列中提供提示詞，Claude Code 就會忽略它。若要在其之外排程其他提示詞，請使用 `/loop <prompt>` 或[直接詢問 Claude](#manage-scheduled-tasks)。

Claude 會在兩個位置尋找此檔案，並使用最先找到的那一個。

| 路徑 | 範圍 |
| :- | :- |
| `.claude/loop.md` | 專案層級。兩個檔案同時存在時優先採用。 |
| `~/.claude/loop.md` | 使用者層級。適用於任何未定義自己檔案的專案。 |

此檔案為純 Markdown，沒有必要的結構。請以直接輸入 `/loop` 提示詞的方式撰寫。以下範例用於維持發行分支的健全狀態：

```markdown title=".claude/loop.md" theme={null}
Check the `release/next` PR. If CI is red, pull the failing job log,
diagnose, and push a minimal fix. If new review comments have arrived,
address each one and resolve the thread. If everything is green and
quiet, say so in one line.
```

對 `loop.md` 的編輯會在下一次迭代時生效，因此您可以在迴圈執行期間調整指令。當兩個位置都不存在 `loop.md` 時，迴圈會改用內建維護提示詞。請保持檔案簡潔：超過 25,000 位元組的內容會被截斷。

### 停止迴圈

* **[自行調整節奏的迴圈](#let-claude-choose-the-interval)**：在迴圈等待下一次迭代時，按下 `Esc` 即可停止。您也可以在 Claude 閒置時使用 `Ctrl+C` 停止，但在[您已連接的背景工作階段](#detach-without-stopping-a-loop)中除外。`Pending wakeup cancelled` 通知會確認迴圈不會再次觸發。
* **[固定間隔迴圈](#run-on-a-fixed-interval)**：若要停止 `/loop 5m` 這類迴圈，請要求 Claude 取消它，例如 `cancel the deploy check loop`。`Esc` 與 `Ctrl+C` 無法停止它，也無法停止任何您[直接詢問 Claude 所排程](#manage-scheduled-tasks)的任務。未取消的迴圈會在[經過七天後](#seven-day-expiry)結束。

在[自行調整節奏模式](#let-claude-choose-the-interval)下，Claude 也可以在任務完成後自行結束迴圈。Claude 會以 `stop: true` 呼叫 [`ScheduleWakeup` 工具](https://code.claude.com/docs/zh-TW/tools-reference)，立即取消待處理的喚醒。若某次迭代結束時既未重新排程也未停止，Claude Code 會在約 20 分鐘後排程一次備援喚醒，若該次迭代也未重新排程，則結束迴圈。

#### 中斷連接而不停止迴圈

當您[已連接至背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md#attach-to-a-session)且 Claude 處於閒置狀態時，在空白提示字元上按兩次 `Ctrl+C` 即可中斷連接。在該處等待下一次迭代的自行調整節奏迴圈會繼續執行，且該次迭代會如期開始。若要改為停止迴圈，請在中斷連接前按下 `Esc`。使用 `Ctrl+C` 中斷連接而不停止迴圈，需要 Claude Code v2.1.295 或更新版本。

## 設定一次性提醒

對於一次性提醒，請用自然語言描述您想要的內容，而不是使用 `/loop`。Claude 會排程一個執行後自動刪除的單次執行任務。

```text theme={null}
remind me at 3pm to push the release branch
```

```text theme={null}
in 45 minutes, check whether the integration tests passed
```

Claude 會使用 cron 表達式將執行時間固定到特定的分鐘和小時，並確認何時執行。

## 管理工作階段範圍的排程任務

用自然語言要求 Claude 列出或取消任務，或直接參考基礎工具。

```text theme={null}
what scheduled tasks do I have?
```

```text theme={null}
cancel the deploy check job
```

這些是 Claude 使用的基礎工具：

| 工具 | 用途 |
| :- | :- |
| `CronCreate` | 排程新任務。接受 5 欄位 cron 表達式、要執行的提示，以及是否重複或執行一次。 |
| `CronList` | 列出排程任務及其 ID、排程、[下次執行時間](#jitter)和提示詞。 |
| `CronDelete` | 按 ID 取消任務。 |

每個排程任務都有一個 8 字元的 ID，您可以傳遞給 `CronDelete`。一個工作階段最多可以同時保存 50 個排程任務。

## 工作階段範圍的排程任務如何執行

排程器每秒檢查一次到期的任務，並以低優先級將其加入佇列。排程的提示在您的回合之間執行，而不是在 Claude 正在回應時執行。如果 Claude 在任務到期時忙碌，提示會等到目前回合結束。

所有時間都以您的本地時區解釋。cron 表達式（例如 `0 9 * * *`）表示您執行 Claude Code 的任何地方的上午 9 點，而不是 UTC。

### 抖動

排程任務的實際執行時間可能與其排程所指定的時間不同。如果每個工作階段的任務都完全按照排程執行，許多任務就會在同一時刻呼叫 API，因此 Claude Code 會偏移每個任務的執行時間。重複執行的任務會延後執行，但每五分鐘執行一次（寫成 `*/5 * * * *`）的任務除外。排程在整點或半點的一次性任務則會稍微提前執行。

若要查看任務下一次的到期時間，請閱讀終端機中 Claude 的 `CronCreate` 呼叫下方的那一列。該列會在排程之後顯示該時間，例如 `next run 10:21 AM`。若要稍後再次查看，請[要求 Claude 列出您的任務](#manage-scheduled-tasks)，並在 `CronList` 呼叫下方的各列中尋找 `next run`。這些列中的下次執行時間需要 Claude Code v2.1.299 或更新版本。

#### 重複執行的任務會延後多久

除非每五分鐘執行一次，否則重複執行的任務每次執行都會延後開始，延後時間最多為距下一次執行間隔的一半，且最多不超過 30 分鐘。您的任務屬於以下三種情況之一：

* **間隔均勻的執行**：間隔相等的任務（例如每小時、每天或每 10 分鐘）每次都會延後相同的分鐘數，即使工作階段處於閒置時也是如此。
* **間隔不均勻的執行**：間隔不相等的任務（例如排程在每小時 `:00` 和 `:15` 的任務）在每次執行時可能延後不同的分鐘數。
* **每五分鐘**：寫成 `*/5 * * * *` 的任務不會延後。在上一次執行整整五分鐘後才開始的執行，會在五分鐘的[提示快取](https://code.claude.com/docs/zh-TW/prompt-caching.md#which-ttl-each-request-gets)過期之後才開始，因此每次執行會提早 15 秒開始。

在此表格的第一欄中找到您的排程，即可查看其每次執行的開始時間。

| 排程 | 每次執行的開始時間 |
| :- | :- |
| 每 5 分鐘，寫成 `*/5 * * * *`，即 `/loop 5m` 所建立的排程 | 上一次執行後 4 分 45 秒 |
| 每 10 分鐘 | 延後 0 到 5 分鐘 |
| 每 30 分鐘 | 延後 0 到 15 分鐘 |
| 每小時，或頻率更低（例如每天） | 延後 0 到 30 分鐘 |

例如，`7,37 * * * *` 會將任務排程在 `:07` 和 `:37`，兩者相隔 30 分鐘，因此其延遲介於 0 到 15 分鐘之間。如果此任務的延遲為 14 分鐘，它會在每小時的 `:21` 和 `:51` 執行。將排程改為不同的分鐘會移動執行時間，但仍會在其上加上延遲。

#### 一次性任務何時會提前執行

排程在 `:00` 或 `:30` 的一次性任務最多會提前 90 秒執行。Claude Code 不會偏移排程在其他任何分鐘的一次性任務，因此當時間點很重要時，請避開整點和半點進行排程：使用 `3 9 * * *` 而不是 `0 9 * * *`。

### 七天過期

重複執行的任務在建立後 7 天自動過期。任務最後執行一次，然後刪除自己。這限制了被遺忘的迴圈可以執行多長時間。如果您需要重複執行的任務持續更長時間，請在過期前取消並重新建立它，或使用[雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md)或 [Desktop 排程任務](https://code.claude.com/docs/zh-TW/desktop-scheduled-tasks.md)進行持久排程。

## Cron 表達式參考

`CronCreate` 接受標準 5 欄位 cron 表達式：`minute hour day-of-month month day-of-week`。所有欄位都支援萬用字元 (`*`)、單一值 (`5`)、步驟 (`*/15`)、範圍 (`1-5`) 和逗號分隔的清單 (`1,15,30`)。

| 範例 | 含義 |
| :- | :- |
| `*/5 * * * *` | 每 5 分鐘 |
| `0 * * * *` | 每小時整點 |
| `7 * * * *` | 每小時的第 7 分鐘 |
| `0 9 * * *` | 每天上午 9 點（本地時間） |
| `0 9 * * 1-5` | 工作日上午 9 點（本地時間） |
| `30 14 15 3 *` | 3 月 15 日下午 2:30（本地時間） |

星期幾使用 `0` 或 `7` 表示星期日，`6` 表示星期六。不支援擴展語法，例如 `L`、`W`、`?` 和名稱別名，例如 `MON` 或 `JAN`。

當月份日期和星期幾都受到限制時，如果任一欄位匹配，日期就匹配。這遵循標準 vixie-cron 語義。

## 停用工作階段範圍的排程任務

在您的環境中設定 `CLAUDE_CODE_DISABLE_CRON=1` 以完全停用排程器。cron 工具和 `/loop` 變得不可用，任何已排程的任務都停止執行。請參閱 [環境變數](https://code.claude.com/docs/zh-TW/env-vars.md) 以取得完整的停用標誌清單。

## 限制

工作階段範圍的排程有固有的限制：

* 任務只在 Claude Code 執行且閒置時執行。關閉終端或讓工作階段退出會停止它們執行。[將工作階段放在背景執行](https://code.claude.com/docs/zh-TW/agent-view.md#from-inside-a-session)會將 `/loop` 任務帶到背景工作階段，該工作階段會持續執行而無需終端。
* 沒有錯過執行的追趕。如果任務的排程時間在 Claude 忙於長時間執行的請求時經過，它會在 Claude 變為閒置時執行一次，而不是每個錯過的間隔執行一次。
* 在[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md#from-inside-a-session)中，如果[自我調整的迴圈](#let-claude-choose-the-interval)的下一次喚醒到期時，工作階段的程序未在執行（例如發生當機之後），該迴圈就會停止。當程序再次啟動時，逐字稿會顯示[喚醒不會觸發的通知](https://code.claude.com/docs/zh-TW/errors.md#restarted-after-its-next-loop-wakeup-was-due)。若要繼續迴圈，請[回覆該工作階段](https://code.claude.com/docs/zh-TW/agent-view.md#peek-and-reply)並要求 Claude 讓它持續執行。
* 當您使用 `claude --resume` 或 `claude --continue` 繼續工作階段時，Claude Code 會復原使用 `CronCreate` 排程的任務，除了已[過期](#seven-day-expiry)的重複執行任務和排程時間已經過去的一次性任務。[自我調整的 `/loop`](#let-claude-choose-the-interval) 不會被復原，因此請再次執行 `/loop` 以重新啟動它。
* 已復原的重複執行任務不會針對工作階段未執行期間錯過的執行次數進行觸發。它的下一次執行是您繼續工作階段後第一個到期的執行，且該次執行會套用[抖動](#jitter)。
* 當您使用 `claude --resume` 或 `claude --continue` 繼續時，Claude Code 不會重新啟動工作階段結束時正在執行的背景 Bash 命令和監視器。如果您仍需要其中某一個，請要求 Claude 再次啟動它。
* 當[功能旗標擷取關閉](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)時，Claude Code 會將您要求跨工作階段保留的任務儲存在專案的 `.claude/scheduled_tasks.json` 檔案中。當 `.claude` 目錄或該檔案是符號連結時，Claude Code 會傳回錯誤，而不是排程任務。已儲存的任務只在您建立它的專案資料夾中執行。如果您將檔案複製到另一個資料夾（例如新的 worktree），該處的工作階段會列出複製的任務，但不會執行它們，因此請在該資料夾中再次建立任務。

對於需要無人值守執行的 cron 驅動自動化：

* [雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md)：在雲端按排程執行、透過 API 呼叫或在 GitHub 事件上執行
* [GitHub Actions](https://code.claude.com/docs/zh-TW/github-actions.md)：在 CI 中使用 `schedule` 觸發器
* [Desktop 排程任務](https://code.claude.com/docs/zh-TW/desktop-scheduled-tasks.md)：在您的機器上本地執行

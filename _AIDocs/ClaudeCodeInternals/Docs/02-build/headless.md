<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/headless | lastmod: 2026-10-27 | section: Build with Claude Code / Automation -->
> 來源：https://code.claude.com/docs/zh-TW/headless（官方 zh-TW，lastmod 2026-10-27）｜分類：Build with Claude Code › Automation｜EN 摘要：Use the Agent SDK to run Claude Code programmatically from the CLI, Python, or TypeScript.

# 以程式方式執行 Claude Code

> 使用 Agent SDK 從 CLI、Python 或 TypeScript 以程式方式執行 Claude Code。

[Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 提供與 Claude Code 相同的工具、agent 迴圈和上下文管理。它可作為 CLI 用於指令碼和 CI/CD，或作為 [Python](https://code.claude.com/docs/zh-TW/agent-sdk/python.md) 和 [TypeScript](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md) 套件供完整的程式控制。

若要以非互動模式執行 Claude Code，請傳遞 `-p` 和您的提示以及任何 [CLI 選項](https://code.claude.com/docs/zh-TW/cli-reference.md)：

```bash theme={null}
claude -p "Find and fix the bug in auth.py" --allowedTools "Read,Edit,Bash"
```

本頁涵蓋透過 CLI (`claude -p`) 使用 Agent SDK。如需具有結構化輸出、工具核准回呼和原生訊息物件的 Python 和 TypeScript SDK 套件，請參閱 [完整 Agent SDK 文件](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md)。

## 基本用法

在任何 `claude` 命令中加上 `-p`（或 `--print`）旗標以非互動方式執行。並非每個 [CLI 選項](https://code.claude.com/docs/zh-TW/cli-reference.md) 都能與 `-p` 結合。Claude Code 拒絕 `--bg`，並在有任務描述時拒絕 `--cloud`，並會出現命名衝突的錯誤；`--cloud` 與工作階段 ID 和 `-p` 一起使用時，會 [將訊息加入該雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#send-follow-ups-from-the-cli) 並退出。您經常會與 `-p` 結合的選項包括：

* `--continue` 用於 [繼續對話](#continue-conversations)
* `--allowedTools` 用於 [自動核准工具](#auto-approve-tools)
* `--output-format` 用於 [取得結構化輸出](#get-structured-output)

此範例詢問 Claude 關於您的程式碼庫的問題並列印回應：

```bash theme={null}
claude -p "What does the auth module do?"
```

Claude Code 在成功時以代碼 0 退出，在執行失敗時以非零代碼退出，因此您的指令碼可以根據退出狀態進行分支。如果您傳遞無效旗標，Claude Code 會在執行開始前向 stderr 報告錯誤。當執行內部發生失敗（例如缺少身分驗證）時，Claude Code 會將失敗列印為 stdout 上的結果。

### 使用 bare 模式更快啟動

加上 `--bare` 以跳過 hook、skill、自訂命令、[subagent](https://code.claude.com/docs/zh-TW/sub-agents.md)、已安裝的外掛、MCP 伺服器、自動記憶和 CLAUDE.md 的自動探索來減少啟動時間。沒有它，`claude -p` 會像互動工作階段一樣探索並載入這些項目，包括在工作目錄或 `~/.claude` 中設定的任何內容。

bare 模式對於 CI 和指令碼很有用，您需要在每台機器上獲得相同的結果。隊友 `~/.claude` 中的 hook 或專案 `.mcp.json` 中的 MCP 伺服器不會執行，因為 bare 模式永遠不會讀取它們。您使用 `--add-dir` 命名的目錄是部分例外：bare 模式從其 `.claude/skills/` 資料夾載入 skill，但仍然跳過其 `.claude/commands/` 和 `.claude/agents/` 資料夾。[來自其他目錄的 Skills](https://code.claude.com/docs/zh-TW/skills.md#skills-from-additional-directories) 涵蓋了哪些會載入和不會載入。

沒有 `--bare`，`-p` 工作階段會執行專案 `.claude/settings.json` 中的 hook 並連接其 `.mcp.json` 中的伺服器，即使在您從未信任的資料夾中也是如此。`-p` 工作階段不會顯示工作區信任對話框和每個伺服器的核准提示。[在您信任資料夾之前執行的內容](https://code.claude.com/docs/zh-TW/permissions.md#what-runs-before-you-trust-a-folder) 涵蓋了 `-p` 下每種類型的儲存庫內容以及如何將其排除。

此範例在 bare 模式下執行一次性摘要任務，並預先核准 Read 工具，以便呼叫完成而無需權限提示。執行前設定 `ANTHROPIC_API_KEY`，因為 bare 模式不使用您的訂閱登入：

```bash theme={null}
claude --bare -p "Summarize README.md" --allowedTools "Read"
```

在 bare 模式下，Claude Code 永遠不會讀取 OAuth 憑證或系統鑰匙圈。對於 Anthropic API，在環境中設定 `ANTHROPIC_API_KEY`，使用在 [Claude Console](https://platform.claude.com) 中建立的金鑰，或在 `--settings` JSON 中提供 `apiKeyHelper`。Amazon Bedrock、Google Cloud 的 Agent Platform 和 Microsoft Foundry 繼續照常讀取各自的提供者憑證。

在 bare 模式下，Claude 可以存取 Bash、檔案讀取和檔案編輯工具。使用旗標傳遞您需要的任何 context：

| 要載入 | 使用 |
| - | - |
| 系統提示詞新增 | `--append-system-prompt`、`--append-system-prompt-file` |
| 設定 | `--settings <file-or-json>` |
| MCP 伺服器 | `--mcp-config <file-or-json>` |
| [自訂 agent](https://code.claude.com/docs/zh-TW/sub-agents.md#choose-the-subagent-scope) | `--agents <file-or-json>` |
| 一個外掛 | `--plugin-dir <path>`、`--plugin-url <url>` |

bare 模式也會限制工作階段執行期間發生的事情：

* **MCP 伺服器**：只有在命令列上提供的伺服器會連接，例如使用 `--mcp-config`。在互動工作階段中，除非您傳遞 `--ide`，否則 Claude Code 也會跳過自動 IDE 連接。
* **系統提醒**：Claude 會收到您的提示詞和工具結果，但不會附帶 Claude Code 原本會一併加入的 [系統提醒](https://code.claude.com/docs/zh-TW/glossary.md#system-reminder)。例如，當 Claude 先前讀取的檔案在磁碟上變更時，Claude 不會收到通知，也不會取得可用 skill 的清單，包括來自 `--add-dir` 資料夾的 skill。
* **背景任務**：Claude 無法執行背景命令或背景 subagent，[`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS`](https://code.claude.com/docs/zh-TW/env-vars) 所關閉的其他功能也會一併關閉。達到 [逾時](https://code.claude.com/docs/zh-TW/tools-reference.md#timeout-and-output-limits) 的命令會停止，而不是 [移至背景](https://code.claude.com/docs/zh-TW/tools-reference.md#background-commands)。

在 v2.1.286 之前，這些限制僅部分生效：互動式 `--bare` 工作階段會連接一般工作階段會連接的 MCP 伺服器，每個 `--bare` 工作階段都會傳送系統提醒，且背景任務仍可使用。

> [!NOTE]
>
> `--bare` 是用於指令碼和 SDK 呼叫的建議模式，並將在未來版本中成為 `-p` 的預設值。

### 退出時的背景任務

在 Claude 完成其回合且 stdin 已關閉後，`claude -p` 執行可能會保持開啟，以等待 Claude 啟動的背景工作。

除非主對話啟動的背景命令仍在執行，否則預設情況下，Claude Code 會在連續閒置等待 10 分鐘後停止仍在執行的任何內容，並捨棄其部分結果。要變更 10 分鐘上限，請設定 [`CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS`](https://code.claude.com/docs/zh-TW/env-vars)，或將其設定為 `0` 以不設上限地等待。

執行會等待背景工作，例如背景命令、subagent 和工作流程、Monitor 監視，以及待處理的 `/loop` 喚醒：

* **[背景命令](https://code.claude.com/docs/zh-TW/tools-reference.md#background-commands)**：對於主對話啟動的命令，例如開發伺服器或監視建置，執行會等待直到該命令退出或達到其 [時間限制](https://code.claude.com/docs/zh-TW/tools-reference.md#time-limit-for-background-commands)。接著 Claude 會依據結果再進行一個回合。在命令執行期間，10 分鐘上限不會結束等待。
* **背景 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 和工作流程**：執行會保持開啟，直到該工作完成，因為其結果是最終輸出的一部分。
* **[Monitor](https://code.claude.com/docs/zh-TW/tools-reference.md#monitor-tool) 監視**：執行會等待直到監視逾時或 10 分鐘上限結束等待，以先發生者為準。在等待期間，Claude 會持續回應監視報告的內容。預設情況下，監視在 Claude 啟動後五分鐘逾時。
* **待處理的喚醒**：在以文字傳遞提示詞（而非使用 `--input-format stream-json`）的執行中，當 Claude 已排定 [自訂節奏的 `/loop` 喚醒](https://code.claude.com/docs/zh-TW/scheduled-tasks#let-claude-choose-the-interval) 時，執行會等待每次喚醒觸發並執行其迭代，直到 [迴圈結束](https://code.claude.com/docs/zh-TW/scheduled-tasks.md#stop-a-loop)，即使超過 10 分鐘上限也是如此。

當 stderr 是終端機且執行已等待五秒時，Claude Code 會向 stderr 列印一行以 `Waiting for background work to finish` 開頭並指出該工作的訊息。使用 [`json` 或 `stream-json` 輸出](#get-structured-output) 時，只有在 stdout 不是終端機時才會列印該行，因此您的指令碼讀取的 JSON 永遠不會包含它。

如果執行達到其 [`--max-budget-usd`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 上限，Claude Code 會停止剩餘的背景工作，而不是繼續等待。

當背景工作啟動另一個回合時，使用預設的 `text` 輸出時，執行會列印每個回合的結果；使用 `json` 輸出時，則列印最後一個回合的結果。在 v2.1.295 之前，使用 `text` 輸出時，執行也只會列印最後一個回合的結果。

#### 非互動式執行結束時的 MCP 工作

`claude -p` 執行不會等待在背景中進行的 MCP 工作：

* **[MCP 任務](https://code.claude.com/docs/zh-TW/mcp.md#mcp-tasks-that-run-on-the-server)**：在遠端伺服器上，該工作會繼續進行。若要再次追蹤它，請 [繼續該工作階段](https://code.claude.com/docs/zh-TW/mcp.md#exit-clear-or-resume-while-an-mcp-task-runs)，而不是以一次性的 `claude -p "<prompt>"` 執行。
* **由 [自動背景化](https://code.claude.com/docs/zh-TW/mcp.md#automatic-backgrounding-of-long-tool-calls) 移至背景的 MCP 呼叫**：該呼叫的結果會遺失。

### 使用 SIGTERM 停止執行

如果您使用 SIGTERM 停止 `claude -p` 執行，例如使用 `kill` 或從程序監督程式，Claude Code 會以代碼 143 退出。Claude Code 會將進行中的回合保留為未完成狀態，並且不會為其記錄任何結果。要改為結束回合，請傳送 SIGINT，或在停止程序之前呼叫 Agent SDK 的 `interrupt()`。

在 SIGTERM 上，Claude Code 會終止仍在執行的任何 Bash 命令的程序樹。Claude Code 然後執行 [`SessionEnd` hook](https://code.claude.com/docs/zh-TW/hooks#sessionend) 並退出。退出時，Claude Code 不啟動新的工具呼叫、不傳送新的模型請求，也不執行除 `SessionEnd` 以外的任何 hook。如果執行在命令中間或在信號到達時等待權限提示的答案，Claude Code 會按如下方式處理該步驟：

* **執行命令**：Claude Code 在工作階段中將命令記錄為已終止。
* **等待權限提示的答案**：如果您向程序傳送 SIGTERM，Claude Code 會將提示保留為未回答。如果您的程式透過 Agent SDK 關閉工作階段，SDK 會在傳送任何信號之前結束 Claude Code 的輸入，Claude Code 會在輸入結束後立即取消提示。

當您 [繼續工作階段](#continue-conversations) 時，Claude Code 會將中斷的回合保留為原樣，您的下一個提示詞會推動對話。要讓 Claude Code 在繼續時改為繼續中斷的回合，請設定 [`CLAUDE_CODE_RESUME_INTERRUPTED_TURN=1`](https://code.claude.com/docs/zh-TW/env-vars)。

### 如果工作目錄被刪除

如果 `claude -p` 或 Agent SDK 工作階段的工作目錄在工作階段中間被刪除，工作階段會繼續執行。當回合在目錄遺失時啟動時，Claude Code 會在 `stream-json` 輸出中發出 [警告訊息](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md#sdkinformationalmessage)，且 shell 命令會失敗，直到目錄再次存在。

## 範例

這些範例展示常見的 CLI 使用模式。當命令中提及 `auth.py` 或 `build-error.txt` 等檔案時，請替換為您自己專案中的檔案。在 CI 或其他腳本化環境中，請加上 [`--bare`](#start-faster-with-bare-mode)，讓 Claude Code 啟動時不載入主機的 hook、外掛、自動記憶或 `CLAUDE.md`。

### 透過 Claude 傳遞資料

非互動模式會讀取 stdin，因此您可以像使用任何其他命令列工具一樣，將資料透過管道傳入，並將回應重新導向輸出。

此範例將建置日誌透過管道傳入 Claude，並將說明寫入檔案：

```bash theme={null}
cat build-error.txt | claude -p 'concisely explain the root cause of this build error' > output.txt
```

使用 `--output-format json` 時，回應 payload 會包含 `total_cost_usd` 以及依模型細分的費用，因此腳本化的呼叫端無需查閱[使用量儀表板](https://code.claude.com/docs/zh-TW/costs.md)即可追蹤支出。當您使用 `--continue` 或 `--resume` 接續先前的對話時，該次執行會回報整個對話的總額，[包含先前執行的支出](https://code.claude.com/docs/zh-TW/agent-sdk/cost-tracking.md#accumulate-costs-across-multiple-calls)。這兩個數字都是[用戶端估算值](https://code.claude.com/docs/zh-TW/agent-sdk/cost-tracking.md)，可能與您的實際帳單不同。

> [!NOTE]
>
> 透過管道傳入的 stdin 上限為 10MB。若超過上限，Claude Code 會以明確的錯誤訊息及非零狀態結束。若要處理更大的輸入，請將內容寫入檔案，並在提示詞中引用該檔案路徑，而非透過管道傳入。

如果 Claude Code 無法讀取 stdin，例如啟動它的程序中斷了其一端的連線，Claude Code 會將警告輸出至 stderr，並繼續使用命令列中的提示詞。

### 將 Claude 加入建置腳本

您可以將非互動呼叫包裝在腳本中，把 Claude 當作專案專屬的 linter 或審查工具使用。

此 `package.json` 腳本會將相對於 `main` 的差異透過管道傳入 Claude，並要求它回報錯字。透過管道傳入差異意味著 Claude 不需要 Bash 權限即可讀取它，而跳脫的雙引號可讓腳本在 Windows 上保持可攜性：

```json theme={null}
{
  "scripts": {
    "lint:claude": "git diff main | claude -p \"you are a typo linter. for each typo in this diff, report filename:line on one line and the issue on the next. return nothing else.\""
  }
}
```

使用 `npm run lint:claude` 執行。

### 取得結構化輸出

使用 `--output-format` 控制回應的傳回方式：

* `text`（預設）：純文字輸出
* `json`：包含結果、工作階段 ID 及中繼資料的結構化 JSON
* `stream-json`：以換行分隔的 JSON，用於即時串流

此範例以 JSON 格式傳回專案摘要及工作階段中繼資料，文字結果位於 `result` 欄位：

```bash theme={null}
claude -p "Summarize this project" --output-format json
```

若要取得符合特定 schema 的輸出，請將 `--output-format json` 與 `--json-schema` 及 [JSON Schema](https://json-schema.org/) 定義搭配使用。回應會包含請求的中繼資料（工作階段 ID、使用量等），結構化輸出則位於 `structured_output` 欄位。

此範例會擷取函式名稱，並以字串陣列的形式傳回：

```bash theme={null}
claude -p "Extract the main function names from auth.py" \
  --output-format json \
  --json-schema '{"type":"object","properties":{"functions":{"type":"array","items":{"type":"string"}}},"required":["functions"]}'
```

如果該值不是有效的 JSON Schema，`claude` 會以 `Error: --json-schema is not a valid JSON Schema` 結束，並附上驗證器的診斷訊息。Claude Code 接受使用 `format` 關鍵字的 schema，例如 `"format": "email"`，但會將 `format` 視為註解而不強制執行。

如果某次執行結束時沒有產生有效的結構化輸出，例如因為 Claude 拒絕了該請求，回應中就不會有 `structured_output` 欄位。在您的腳本使用 `structured_output` 之前，請先確認該欄位存在。

> [!TIP]
>
> 使用 [jq](https://jqlang.org/) 等工具剖析回應並擷取特定欄位：
>
> ```bash theme={null}
> # Extract the text result
> claude -p "Summarize this project" --output-format json | jq -r '.result'
>
> # Extract structured output
> claude -p "Extract function names from auth.py" \
>   --output-format json \
>   --json-schema '{"type":"object","properties":{"functions":{"type":"array","items":{"type":"string"}}},"required":["functions"]}' \
>   | jq '.structured_output'
> ```

### 串流回應

將 `--output-format stream-json` 與 `--verbose` 及 `--include-partial-messages` 搭配使用，即可在 token 產生時即時接收。每一行都是代表一個事件的 JSON 物件：

```bash theme={null}
claude -p "Explain recursion" --output-format stream-json --verbose --include-partial-messages
```

串流的最後一行是 `result` 訊息，其中包含最終回應文字、費用及工作階段中繼資料。

如果您的消費端讀取串流的速度較慢，Claude Code 會等待佇列中的輸出消化完畢後再結束，等待時間會依仍在佇列中的量調整，上限為 30 秒。

以下範例使用 [jq](https://jqlang.org/) 篩選文字差量，僅顯示串流文字。`-r` 旗標會輸出原始字串（不含引號），`-j` 則會在不加換行的情況下串接，讓 token 持續串流：

```bash theme={null}
claude -p "Write a poem" --output-format stream-json --verbose --include-partial-messages | \
  jq -rj 'select(.type == "stream_event" and .event.delta.type? == "text_delta") | .event.delta.text'
```

如需使用回呼及訊息物件進行程式化串流，請參閱 Agent SDK 文件中的[即時串流回應](https://code.claude.com/docs/zh-TW/agent-sdk/streaming-output.md)。

#### 追蹤 subagent 訊息

來自 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 以及[在 subagent 中執行](https://code.claude.com/docs/zh-TW/skills.md#run-skills-in-a-subagent)的 skill 的訊息，會以 `assistant` 及 `user` 訊息的形式出現在串流中。其 `parent_tool_use_id` 欄位會指出每則訊息屬於哪一次執行。來自主對話的訊息在該欄位中則為 `null`。

分叉 skill 或在[前景](https://code.claude.com/docs/zh-TW/sub-agents.md#run-subagents-in-foreground-or-background)執行的 subagent 的第一則訊息，是一則 `user` 訊息，內含驅動它的提示詞或 skill 內容。在第一則訊息之後，Claude Code 會發出：

* **預設情況下**：該次執行的 `tool_use` 及 `tool_result` 區塊。
* **使用 [`--forward-subagent-text`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 或 [`CLAUDE_CODE_FORWARD_SUBAGENT_TEXT`](https://code.claude.com/docs/zh-TW/env-vars) 時**：還會包含該次執行的文字及思考區塊，因此您可以重建每次執行的逐字稿。

啟用任一選項時，Claude Code 會轉發來自[每個巢狀層級的 subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#let-subagents-spawn-their-own-subagents) 的訊息，無論每個 subagent 是透過 Agent 工具產生，還是以分叉 skill 的形式啟動。在 `parent_tool_use_id` 中，巢狀 subagent 的訊息會帶有啟動它的 Agent 或 Skill 工具呼叫 ID，因此您可以依循這些 ID 重建完整的巢狀樹狀結構。

由 Claude 透過工具呼叫啟動的執行，會帶有該工具呼叫的 ID。您透過將 `/<skill-name>` 作為提示詞傳入而啟動的分叉 skill 沒有工具呼叫，因此其訊息會改為帶有 `forked-command-` 值，並在它完成後才送達。請在第一欄中找到該次執行的啟動方式：

| 執行的啟動方式 | `parent_tool_use_id` | 其訊息送達的時機 |
| :- | :- | :- |
| Claude 從主對話呼叫 Agent 工具 | 該 Agent `tool_use` 區塊的 ID | 在 subagent 運作期間 |
| Claude 從主對話為分叉 skill 呼叫 Skill 工具 | 該 Skill `tool_use` 區塊的 ID | 在分叉 skill 運作期間 |
| 您將 `/<skill-name>` 作為提示詞傳入 | 以 `forked-command-` 開頭的值 | 在分叉 skill 完成後一併依序送達 |

對於從提示詞啟動的分叉 skill，請以 `forked-command-` 前綴比對 `parent_tool_use_id`，因為其後的名稱可能與您輸入的名稱不同。

如果您的串流中缺少其中某些訊息，請對照以下最低版本檢查您的 Claude Code 版本：

* **Claude 從主對話以 Skill 工具啟動的分叉 skill**：其 `tool_use` 及 `tool_result` 區塊需要 v2.1.86 或更新版本，其第一則 `user` 訊息以及文字及思考區塊需要 v2.1.265 或更新版本
* **由分叉 skill 產生的 subagent 的訊息，以及在 subagent 或另一個分叉 skill 內啟動的分叉 skill 的訊息**：v2.1.275 或更新版本
* **您透過將 `/<skill-name>` 作為提示詞傳入而啟動的分叉 skill 的訊息**：v2.1.287 或更新版本

#### 處理 API 重試

當 API 請求因可重試的錯誤而失敗時，Claude Code 會在重試前發出 `system/api_retry` 事件。在 v2.1.246 或更新版本中，當 `401` 或 `403` 拒絕 [`apiKeyHelper`](https://code.claude.com/docs/zh-TW/settings-reference#apikeyhelper) 憑證時，Claude Code 會靜默進行前兩次重試而不發出事件，從第三次連續重試起才照常發出事件。靜默重試仍會計入 `attempt`。您可以使用此事件在自己的介面中顯示重試進度。

| 欄位 | 類型 | 說明 |
| - | - | - |
| `type` | `"system"` | 訊息類型 |
| `subtype` | `"api_retry"` | 識別此為重試事件 |
| `attempt` | integer | 目前的嘗試次數，從 1 開始 |
| `max_retries` | integer | 此失敗原因所允許的重試總次數 |
| `retry_delay_ms` | integer | 距離下次嘗試的毫秒數 |
| `error_status` | integer 或 null | 失敗嘗試的 HTTP 狀態碼；若該次嘗試未收到來自 API 的 HTTP 回應，則為 `null` |
| `no_response` | object，選用 | 僅在失敗的嘗試[未及時收到回應標頭](https://code.claude.com/docs/zh-TW/errors.md#no-response-from-api)時出現。`waited_ms` 是該次嘗試等待的時間，`retry_wait_ms` 是重試將等待的時間。需要 Claude Code v2.1.261 或更新版本 |
| `error` | string | 錯誤類別：`authentication_failed`、`oauth_org_not_allowed`、`account_on_hold`、`billing_error`、`rate_limit`、`overloaded`、`invalid_request`、`model_not_found`、`server_error`、`max_output_tokens`、`cloud_credential_error` 或 `unknown` |
| `uuid` | string | 唯一事件識別碼 |
| `session_id` | string | 事件所屬的工作階段 |

#### 讀取工作階段中繼資料

`system/init` 事件會回報工作階段中繼資料，包括模型、工具、MCP 伺服器及已載入的外掛。除非有啟動事件排在它之前，否則它是串流中的第一個事件：

* `plugin_install` 事件，於設定 [`CLAUDE_CODE_SYNC_PLUGIN_INSTALL`](https://code.claude.com/docs/zh-TW/env-vars) 時出現。
* [`hook_started`、`hook_progress` 及 `hook_response` 事件](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#sdkhookstartedmessage)，於已設定的 [`SessionStart`](https://code.claude.com/docs/zh-TW/hooks#sessionstart) 或 [`Setup`](https://code.claude.com/docs/zh-TW/hooks#setup) hook 執行期間出現。這些事件會在 hook 產生時即時串流。

此事件還帶有一個選用的 `capabilities` 字串陣列，列出此 Claude Code 版本所實作的協定行為，例如 `interrupt_receipt_v1` 或 `interrupt_cancel_queued_v1`。請檢查此陣列來偵測功能，而非比對版本字串，並忽略您無法辨識的值。如需功能清單，請參閱 [`SDKSystemMessage`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#sdksystemmessage)。

#### 在外掛或 MCP 伺服器未載入時讓 CI 失敗

使用 `system/init` 事件中的外掛欄位來偵測未載入的外掛：

| 欄位 | 類型 | 說明 |
| - | - | - |
| `plugins` | array | 成功載入的外掛，每個都包含 `name` 及 `path` |
| `plugin_errors` | array | 外掛載入時的錯誤，每個都包含 `plugin`、`type` 及 `message`。包括未滿足的相依性版本，以及 `--plugin-dir` 載入失敗，例如路徑不存在或封存檔無效。未載入的外掛不會出現在 `plugins` 中。沒有錯誤時會省略此鍵 |

當 `--plugin-dir` 目錄或封存檔本身載入失敗時，其 `plugin_errors` 項目會以 `path` 包含解析後的絕對路徑。可用它來判斷多個 `--plugin-dir` 值中是哪一個失敗。`path` 欄位需要 Claude Code v2.1.283 或更新版本。

以相同方式使用 MCP 伺服器欄位。當您搭配 `-p` 傳入 [`--mcp-config`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 時，Claude Code 會在執行第一個回合前等待仍在擱置中的伺服器，最長等待 [`MCP_TIMEOUT`](https://code.claude.com/docs/zh-TW/env-vars) 啟動逾時時間，預設為 30 秒。具有[快取工具清單](https://code.claude.com/docs/zh-TW/agent-sdk/mcp.md#connection-timing)的遠端伺服器會略過等待，在 `system/init` 中顯示 `pending`，並在第一次工具呼叫時連線。在[自架環境](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#connection-timing)中，則會改為套用較短的等待時間。此等待需要 Claude Code v2.1.221 或更新版本。

Claude Code 會在啟動時驗證每個 `--mcp-config` 項目，並略過驗證失敗的項目，例如沒有 `type` 的 `url` 項目。執行會繼續並正常結束，因此請檢查這些欄位，以偵測從未載入的伺服器：

| 欄位 | 類型 | 說明 |
| - | - | - |
| `mcp_servers` | array | 工作階段中的 MCP 伺服器，每個都包含 `name` 及 `status` |
| `mcp_server_errors` | array | 因設定驗證而被略過的 `--mcp-config` 項目，每個都包含 `name`、`type` 及 `message`。`type` 是略過類別，例如 `unknown_type`、`url_missing_type`、`invalid_config` 或 `reserved_name`；請將無法辨識的值視為一般略過。受影響的伺服器不會出現在 `mcp_servers` 中。沒有錯誤時會省略此鍵，因此 CI 關卡可以在陣列非空時判定失敗 |

當您在終端機中手動執行命令時，Claude Code 也會將啟動警告輸出至 stderr，例如 `Warning: 1 MCP server skipped due to invalid config:`，接著列出每個被略過項目的原因。

當您重新導向 stderr，或由 CI 執行器或 SDK 主機等程式擷取 stderr 時，Claude Code 不會輸出警告，僅在 `mcp_server_errors` 欄位中回報被略過的項目。

#### 追蹤外掛安裝

設定 [`CLAUDE_CODE_SYNC_PLUGIN_INSTALL`](https://code.claude.com/docs/zh-TW/env-vars) 時，Claude Code 會在第一個回合之前安裝市集外掛的期間發出 `system/plugin_install` 事件。可使用這些事件在您自己的 UI 中呈現安裝進度。

| 欄位 | 類型 | 說明 |
| - | - | - |
| `type` | `"system"` | 訊息類型 |
| `subtype` | `"plugin_install"` | 識別此為外掛安裝事件 |
| `status` | `"started"`、`"installed"`、`"failed"` 或 `"completed"` | `started` 及 `completed` 標示整體安裝的開始與結束；`installed` 及 `failed` 回報個別市集 |
| `name` | string，選用 | 市集名稱，出現在 `installed` 及 `failed` 上 |
| `error` | string，選用 | 失敗訊息，出現在 `failed` 上 |
| `uuid` | string | 唯一事件識別碼 |
| `session_id` | string | 事件所屬的工作階段 |

### 自動核准工具

使用 `--allowedTools` 讓 Claude 無需提示即可使用特定工具。列出 `Read` 及 `Edit` 可讓 Claude 在不請求權限的情況下讀取及編輯檔案，但從[網路路徑](https://code.claude.com/docs/zh-TW/permissions.md#network-paths)讀取除外。列出 `Bash` 對 shell 命令也有相同效果，但以[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#how-auto-mode-evaluates-actions)啟動的執行除外；在此情況下，Claude Code 會將單獨的 `Bash` 項目視為過於寬泛的允許規則而捨棄，改由自動模式評估每個命令。此範例列出這三個工具，執行測試套件並修正失敗：

```bash theme={null}
claude -p "Run the test suite and fix any failures" \
  --allowedTools "Bash,Read,Edit"
```

未列出之工具的呼叫若無需核准即會執行。在[手動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#available-modes)的 `claude -p` 執行中，需要核准的呼叫會被拒絕，除非有其他機制核准它，例如 [`PermissionRequest` hook](https://code.claude.com/docs/zh-TW/hooks#permissionrequest) 或 [`--permission-prompt-tool`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags)。在 Claude Code v2.1.302 或更新版本中，當[沒有任何設定指定權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md#which-mode-a-non-interactive-run-starts-in)時，`claude -p` 執行會以手動模式啟動。

若要為整個工作階段設定基準，而非列出個別工具，請使用 `--permission-mode` 傳入[權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md)，例如 `auto`、`dontAsk` 或 `acceptEdits`：

* **`auto`**：傳入 `--permission-mode auto`，由分類器代替您審查大多數動作
* **`dontAsk`**：Claude Code 會拒絕所有原本會提示的呼叫，這對於受嚴格限制的 CI 執行很有用，不過您安裝的 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md) 仍可核准其中部分呼叫。若要查看 mod 可以核准哪些呼叫，請參閱[使用 hook 擴充權限](https://code.claude.com/docs/zh-TW/permissions.md#precedence-among-rules-hooks-and-mods)。

  在手動模式下無需核准的動作仍會執行，例如讀取工作目錄中的檔案及[唯讀命令集](https://code.claude.com/docs/zh-TW/permissions.md#read-only-commands)。您的 `--allowedTools` 項目或 `permissions.allow` 規則涵蓋的動作也同樣會執行。`AskUserQuestion`、[您的組織設為 `ask`](https://code.claude.com/docs/zh-TW/mcp#organization-controls-on-connector-tools) 的連接器工具、標記為 [`requiresUserInteraction`](https://code.claude.com/docs/zh-TW/mcp#require-approval-for-a-specific-tool) 的 MCP 工具，以及[從網路路徑讀取](https://code.claude.com/docs/zh-TW/permissions.md#network-paths)，即使有允許規則相符仍會被拒絕
* **`acceptEdits`**：Claude 無需提示即可寫入檔案，且 Claude Code 會自動核准常見的檔案系統命令，例如 `mkdir`、`touch`、`mv` 及 `cp`。[任何模式都不會自動核准的動作](https://code.claude.com/docs/zh-TW/permission-modes.md#actions-no-mode-auto-approves)仍然適用。除唯讀命令集外，其他 shell 命令及網路請求仍需要 `--allowedTools` 項目或 `permissions.allow` 規則。如需完整清單，請參閱 [`acceptEdits` 自動核准的項目](https://code.claude.com/docs/zh-TW/permission-modes#auto-approve-file-edits-with-acceptedits-mode)

此範例以 `acceptEdits` 作為基準套用 lint 修正：

```bash theme={null}
claude -p "Apply the lint fixes" --permission-mode acceptEdits
```

### 在無人值守的執行中關閉權限提示

當沒有人能回應權限提示時，例如在排程工作中，請傳入 `--permission-prompts none`。當您的執行具有權限主機時，此旗標最為重要：具有 [`canUseTool` 回呼](https://code.claude.com/docs/zh-TW/agent-sdk/user-input)的 Agent SDK 應用程式，或您透過 [`--permission-prompt-tool`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 傳入的 MCP 工具。若未使用此旗標，您的執行會等待該主機回應每個權限請求。

使用此旗標時，您的執行不會諮詢主機，也不會等待它。任何會觸發提示的動作都會被拒絕，除非有 `PermissionRequest` hook 允許；Claude 會被告知沒有人能核准該請求且不應重試，而執行會繼續進行。在沒有主機的 `-p` 執行中，這些請求無論如何都會被拒絕，而此旗標還會告知 Claude 不要重試。權限規則、[`PermissionRequest` hook](https://code.claude.com/docs/zh-TW/hooks#permissionrequest) 以及您設定的權限模式仍會優先決定每個呼叫；Claude Code 只會拒絕其他機制都無法處理的請求。

此範例以[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)執行無人值守的任務。分類器會照常審查每個動作，而 Claude Code 會拒絕任何原本會退回提示的動作：

```bash theme={null}
claude -p "Update the dependency pins and run the tests" --permission-mode auto --permission-prompts none
```

使用 `--permission-prompts none` 時，Claude Code 會移除需要由人回應的工具，例如 [`AskUserQuestion`](https://code.claude.com/docs/zh-TW/tools-reference#askuserquestion-tool-behavior)，因此 Claude 無法呼叫它們。任何沒有 [`Elicitation` hook](https://code.claude.com/docs/zh-TW/hooks#elicitation) 回應的 [MCP elicitation 請求](https://code.claude.com/docs/zh-TW/mcp.md#respond-to-mcp-elicitation-requests)都會被取消。

使用 `--output-format stream-json` 時，拒絕會以 `permission_denied` 系統訊息的形式出現，而最終結果訊息會在 `permission_denials` 中列出這些拒絕。

> [!NOTE]
>
> `--permission-prompts` 旗標需要 Claude Code v2.1.259 或更新版本。較早的版本會以未知選項錯誤拒絕它。

### 建立提交

此範例會審查已暫存的變更，並以適當的訊息建立提交：

```bash theme={null}
claude -p "Look at my staged changes and create an appropriate commit" \
  --allowedTools "Bash(git diff *),Bash(git log *),Bash(git status *),Bash(git commit *)"
```

`--allowedTools` 旗標使用[權限規則語法](https://code.claude.com/docs/zh-TW/settings-reference.md#permission-rule-syntax)。結尾的 ` *` 會啟用前綴比對，因此 `Bash(git diff *)` 允許任何以 `git diff` 開頭的命令。`*` 前的空格很重要：若沒有空格，`Bash(git diff*)` 也會比對到 `git diff-index`。

> [!NOTE]
>
> `-p` 模式下的命令支援有所不同：
>
> * 使用者呼叫的 [skill](https://code.claude.com/docs/zh-TW/skills.md) 及自訂命令可以運作。在提示詞字串中加入 `/skill-name`，Claude Code 會在執行前將其展開。
> * 僅在終端機介面中執行的內建命令（例如 `/login`）無法使用。
> * `/model`、`/effort`、`/fast`、`/color` 及 `/rename` 接受以引數形式傳入值，例如 `/model sonnet`；不帶引數的 `/mcp` 會輸出伺服器狀態的文字摘要。這些形式遵循各命令的[可用性說明](https://code.claude.com/docs/zh-TW/commands.md#all-commands)。
> * 若要變更設定，請將 `key=value` 傳給 `/config`，例如 `/config thinking=false`。
> * `/output-style <style>` 會切換[輸出風格](https://code.claude.com/docs/zh-TW/output-styles.md)，單獨使用 `/output-style` 則會列出所有風格。需要 Claude Code v2.1.269 或更新版本。

### 自訂系統提示詞

使用 `--append-system-prompt` 新增指令，同時保留 Claude Code 的預設行為。此範例將 PR 差異透過管道傳入 Claude，並指示它審查安全性弱點。將其儲存為 shell 腳本，例如 `review.sh`：

```bash theme={null}
gh pr diff "$1" | claude -p \
  --append-system-prompt "You are a security engineer. Review for vulnerabilities." \
  --output-format json
```

在此腳本中，`"$1"` 代表您在命令列上傳入的第一個引數。執行 `bash review.sh 123`，shell 會將 `"$1"` 替換為 `123`，因此腳本會擷取 PR 123 的差異。Claude Code 會以 JSON 格式輸出審查結果，文字位於 `result` 欄位。

如需更多選項，包括以 `--system-prompt` 完全取代預設提示詞，請參閱[系統提示詞旗標](https://code.claude.com/docs/zh-TW/cli-reference.md#system-prompt-flags)。若您取代預設提示詞，該次執行啟動時也不會包含 [Git 狀態快照](https://code.claude.com/docs/zh-TW/settings-reference.md#includegitinstructions)。

### 繼續對話

使用 `--continue` 繼續最近的對話，或使用 `--resume` 搭配工作階段 ID 繼續特定對話。在 Claude Code v2.1.257 或更新版本中，當您傳入 `--continue` 時，Claude Code 會開啟已經完成的[背景工作階段](https://code.claude.com/docs/zh-TW/sessions.md#where-the-session-picker-looks)，但不會開啟仍在執行中的背景工作階段。此範例會執行一次審查，然後傳送後續提示詞：

```bash theme={null}
# First request
claude -p "Review this codebase for performance issues"

# Continue the most recent conversation
claude -p "Now focus on the database queries" --continue
claude -p "Generate a summary of all issues found" --continue
```

如果您同時進行多個對話，請擷取工作階段 ID 以繼續特定的對話：

```bash theme={null}
session_id=$(claude -p "Start a review" --output-format json | jq -r '.session_id')
claude -p "Continue that review" --resume "$session_id"
```

您可以從不同的目錄執行這兩個命令：Claude Code 會在此機器上的任何專案中[依 ID 尋找工作階段](https://code.claude.com/docs/zh-TW/sessions.md#where-the-session-picker-looks)。

您也可以不傳入工作階段 ID，改為將工作階段 `.jsonl` [逐字稿檔案](https://code.claude.com/docs/zh-TW/sessions.md#where-transcripts-are-stored)的絕對路徑傳給 `--resume`，Claude Code 會繼續該檔案中儲存的對話。

## 後續步驟

* [Agent SDK 快速入門](https://code.claude.com/docs/zh-TW/agent-sdk/quickstart.md)：使用 Python 或 TypeScript 建立您的第一個 agent
* [CLI 參考](https://code.claude.com/docs/zh-TW/cli-reference.md)：所有 CLI 旗標和選項
* [GitHub Actions](https://code.claude.com/docs/zh-TW/github-actions.md)：在 GitHub 工作流程中使用 Agent SDK
* [GitLab CI/CD](https://code.claude.com/docs/zh-TW/gitlab-ci-cd.md)：在 GitLab 管道中使用 Agent SDK

<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/agent-sdk/configuration | lastmod: 2026-10-27 | section: Agent SDK / Build agents -->
> 來源：https://code.claude.com/docs/zh-TW/agent-sdk/configuration（官方 zh-TW，lastmod 2026-10-27）｜分類：Agent SDK › Build agents｜EN 摘要：Configure Agent SDK sessions: compose the options object, set the model, environment, and limits, and find each feature option's page.

# 設定您的代理

> 設定 Agent SDK 工作階段：組合選項物件、設定模型、環境和限制，並找到每個功能選項的頁面。

Agent SDK 工作階段從設定檔、環境變數和您啟動時傳遞的 `options` 物件讀取設定。本頁面說明如何組合 `options` 物件，以及哪些設定檔和環境變數控制它。

如需每個選項的類型和預設值，請參閱 [`Options`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#options)（TypeScript）和 [`ClaudeAgentOptions`](https://code.claude.com/docs/zh-TW/agent-sdk/python#claudeagentoptions)（Python）參考。

## 將選項傳遞給工作階段

每個 `query()` 呼叫都接受一個選項物件：TypeScript 中的 `Options`、Python 中的 `ClaudeAgentOptions`。每個欄位都是選擇性的，以無選項啟動的工作階段會以 SDK 的預設值執行。下面的範例設定了一個唯讀工作階段，可以總結專案的開放 TODO。配對讀作 TypeScript / Python，其中拼寫不同：

* **`model`**：選擇模型
* **`allowedTools` / `allowed_tools`**：預先核准唯讀工具清單
* **`maxTurns` / `max_turns`**：限制回合數
* **`cwd`**：設定工作目錄

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  prompt: "Summarize the open TODOs in this repo",
  options: {
    model: "claude-sonnet-5",
    allowedTools: ["Read", "Glob", "Grep"],
    maxTurns: 8,
    cwd: "/path/to/repo",
  },
})) {
  if (message.type === "result" && message.subtype === "success" && !message.is_error) {
    console.log(message.result);
  }
}
```

```python Python theme={null}
import asyncio

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

async def main():
    options = ClaudeAgentOptions(
        model="claude-sonnet-5",
        allowed_tools=["Read", "Glob", "Grep"],
        max_turns=8,
        cwd="/path/to/repo",
    )

    async for message in query(
        prompt="Summarize the open TODOs in this repo",
        options=options,
    ):
        if isinstance(message, ResultMessage) and not message.is_error:
            print(message.result)

asyncio.run(main())
```

將 `cwd` 指向您自己的其中一個專案並執行範例。該專案的開放 TODO 摘要會在結果訊息到達時列印。

`allowedTools`（TypeScript）或 `allowed_tools`（Python）預先核准列出的工具，因此對它們的呼叫會在不停止以獲得核准的情況下執行。清單外的工具保持可用。當 Claude 呼叫未列出的工具時，權限模式決定呼叫是否執行。如需詳細資訊，請參閱[允許和拒絕規則](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#allow-and-deny-rules)。

## 載入設定檔

設定檔提供超出選項物件的設定。兩個選項控制它們的載入方式：

* **`settingSources` / `setting_sources`**：控制哪些檔案系統來源載入：使用者、專案和本機。設定檔和 CLAUDE.md 檔案透過這些來源到達。
* **`settings`**：載入設定檔路徑或任一語言的內嵌 JSON 字串，TypeScript 也接受設定物件。無論您傳遞什麼形式都會覆蓋使用者、專案和本機檔案系統設定；只有受管理的原則設定排名更高。參考文件在 TypeScript 的[設定優先順序](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md#settings-precedence)和 Python 的[設定優先順序](https://code.claude.com/docs/zh-TW/agent-sdk/python.md#settings-precedence)下記錄完整的優先順序順序。

傳遞 `[]` 以停用使用者、專案和本機設定。如需詳細資訊，請參閱[在 SDK 中使用 Claude Code 功能](https://code.claude.com/docs/zh-TW/agent-sdk/claude-code-features.md)。

## 選擇模型

除非 `model` 選項、您的設定或您的環境選擇模型，否則新工作階段會在 [Claude Code 的預設模型](https://code.claude.com/docs/zh-TW/model-config.md#default-model-setting)上啟動。如需這些來源的順序，請參閱[設定您的模型](https://code.claude.com/docs/zh-TW/model-config.md#setting-your-model)。設定 `model` 以固定特定模型，或選擇較小的模型以獲得更快、更便宜的代理。該值採用模型別名或完整模型名稱；別名及其解析的版本列在[模型別名](https://code.claude.com/docs/zh-TW/model-config.md#model-aliases)下。

設定 `fallbackModel`（TypeScript）或 `fallback_model`（Python）以命名備份模型。當主要模型過載或不可用時，工作階段會切換到備份。主要模型在每個使用者回合開始時重試，因此一旦中斷通過，工作階段會返回到它。

在任一語言中，該選項接受單個模型或逗號分隔的備份清單。如需順序和鏈上限，請參閱[備份模型鏈](https://code.claude.com/docs/zh-TW/model-config.md#fallback-model-chains)。在 TypeScript 中，等於 `model` 的備份在啟動時會拋出錯誤。

下面的範例顯示 TypeScript 中的備份清單和 Python 中的單個備份：

```typescript TypeScript theme={null}
const options = {
  model: "claude-fable-5",
  fallbackModel: "claude-opus-5,claude-sonnet-5",
};
```

```python Python theme={null}
options = ClaudeAgentOptions(
    model="claude-fable-5",
    fallback_model="claude-opus-5",
)
```

> [!NOTE]
>
> [Messages API](https://platform.claude.com/docs/en/api/messages) 請求參數 `temperature`、`top_p` 和 `max_tokens` 在任一語言的選項物件上都沒有欄位。改為設定[努力級別](https://code.claude.com/docs/zh-TW/agent-sdk/agent-loop.md#effort-level)或[支出上限](#limit-turns-and-spend)，或在您需要直接使用這些參數時呼叫 Messages API。

## 設定環境變數

`env` 選項為執行您工作階段的 Claude Code 程序設定環境變數。您的值是否替換繼承的環境或合併到它上面因語言而異：

* **TypeScript**：`env` 替換子程序環境
* **Python**：SDK 將您的值合併到繼承的環境上，您的值覆蓋繼承的值

在 TypeScript 中，將 `process.env` 展開到 `env` 中以保留繼承的變數，例如 `PATH`、`HOME` 和 `ANTHROPIC_API_KEY`。當您不設定 `env` 時，子程序在兩種語言中都繼承您的環境。

該範例透過設定 `ANTHROPIC_BASE_URL` 將 API 流量路由通過閘道。

```typescript TypeScript theme={null}
const options = {
  env: { ...process.env, ANTHROPIC_BASE_URL: "https://gateway.example.com" },
};
```

```python Python theme={null}
options = ClaudeAgentOptions(
    env={"ANTHROPIC_BASE_URL": "https://gateway.example.com"},
)
```

您傳遞的變數也可以設定 Claude Code 本身。如需 Claude Code 程序讀取的變數，請參閱[環境變數](https://code.claude.com/docs/zh-TW/env-vars.md)。若要以這種方式調整 API 逾時和停滯偵測，請遵循 [TypeScript 參考](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md#handle-slow-or-stalled-api-responses)或 [Python 參考](https://code.claude.com/docs/zh-TW/agent-sdk/python.md#handle-slow-or-stalled-api-responses)中的「處理緩慢或停滯的 API 回應」部分。

## 設定工作目錄

設定 `cwd` 以在特定目錄中執行工作階段。當您不設定 `cwd` 時，工作階段會在您程序的工作目錄中執行。兩個 SDK 都沒有 `cwd` 的設定器。若要在不同目錄中執行，請使用該 `cwd` 啟動另一個工作階段。

Claude Code 讀取工作目錄以確定：

* **專案設定和 hooks**：哪個專案的[設定和 hooks 載入](https://code.claude.com/docs/zh-TW/agent-sdk/claude-code-features.md)
* **Skills**：[工作階段 skills 的發現位置](https://code.claude.com/docs/zh-TW/agent-sdk/skills.md)
* **工作階段儲存**：[儲存的工作階段屬於哪個專案](https://code.claude.com/docs/zh-TW/agent-sdk/session-storage.md)

若要讓工具到達工作目錄外的檔案，請使用 `additionalDirectories`（TypeScript）或 `add_dirs`（Python）新增路徑。如需該授予的範圍，請參閱[其他目錄授予檔案存取權，而非設定](https://code.claude.com/docs/zh-TW/permissions.md#additional-directories-grant-file-access-not-configuration)。

## 限制回合和支出

使用 `maxTurns` / `max_turns` 和 `maxBudgetUsd` / `max_budget_usd` 限制回合和支出。當未設定時，兩個上限都關閉。當工作階段達到上限時，執行以結果訊息結束，其子類型命名上限，`error_max_turns` 或 `error_max_budget_usd`。接下來發生的情況因輸入模式而異：

* **單次 `query()`**：SDK 產生上限結果，然後引發，因此將迴圈包裝在 try 區塊中以在錯誤後繼續
* **串流輸入**：工作階段在上限結果後保持活動，最大回合計數為每個排隊訊息重新開始。預算總計在訊息中累積，一旦支出達到上限，同一對話中的後續訊息以相同的預算結果結束。[`/clear`](https://code.claude.com/docs/zh-TW/agent-sdk/cost-tracking) 重新開始預算

兩個上限對 `0` 的處理方式不同：

* **`maxTurns` / `max_turns`**：`0` 執行沒有回合限制的工作階段，與不設定選項相同
* **`maxBudgetUsd` / `max_budget_usd`**：CLI 在啟動時拒絕 `0` 作為無效金額，工作階段永遠不會執行

如需有關兩個上限的詳細資訊，包括子代理支出，請參閱[回合和預算](https://code.claude.com/docs/zh-TW/agent-sdk/agent-loop.md#turns-and-budget)。

## 在工作階段中途變更設定

當您使用[串流輸入](https://code.claude.com/docs/zh-TW/agent-sdk/streaming-vs-single-mode.md)啟動工作階段時，您可以在執行時切換其模型和權限模式。您呼叫設定器的位置因語言而異：

* **TypeScript**：`query()` 傳回的物件上的方法
* **Python**：[`ClaudeSDKClient`](https://code.claude.com/docs/zh-TW/agent-sdk/python#claudesdkclient) 上的方法，因為 `query()` 傳回沒有控制方法的純迭代器

兩種語言都有相同的設定器：

* **`setModel()` / `set_model()`**：切換模型。不帶模型呼叫它以切換到 [Claude Code 的預設模型](https://code.claude.com/docs/zh-TW/model-config.md#default-model-setting)，而不是您在選項中傳遞的 `model`。如果工作階段處於自動模式，而您切換到自動模式不支援的模型，工作階段會變更為 `default` 模式。若要返回自動模式，請參閱[自動模式 (`auto`)](https://code.claude.com/docs/zh-TW/agent-sdk/permissions#auto-mode-auto)。
* **`setPermissionMode()` / `set_permission_mode()`**：切換權限模式

TypeScript 也有 `applyFlagSettings()` 和 `updateSettings()`：

* **`applyFlagSettings()`**：在執行時應用設定，如 `await session.applyFlagSettings({ effortLevel: "high" })`。該方法採用設定檔鍵而不是選項欄位，因此請檢查 [`applyFlagSettings()` 參考](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#applyflagsettings)以了解架構以及哪些鍵在工作階段中途生效。
* **`updateSettings()`**：將允許清單中的一個鍵寫入設定檔。[`updateSettings()` 參考](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#updatesettings)命名每個來源接受的鍵和版本下限。
  * 傳遞 `"localSettings"` 以寫入專案的本機設定檔，如 `await session.updateSettings("localSettings", { outputStyle: "Explanatory" })`。寫入的鍵在工作階段的下一個請求上生效，並為載入 `local` 設定的後續工作階段持續。
  * 傳遞 `"userSettings"` 以寫入 `effortLevel`，這是該來源接受的唯一鍵。Claude Code 將其儲存為工作階段目前模型的預設努力等級，執行中工作階段的努力不會改變。

下面的範例執行一個兩回合工作階段，在回合之間變更設定，並列印回答每個回合的模型。在 TypeScript 中，提示流保持第二個訊息，直到設定器執行，第二個回合在新模型上執行。

```typescript TypeScript theme={null}
import { query, type SDKUserMessage } from "@anthropic-ai/claude-agent-sdk";

function userMessage(text: string): SDKUserMessage {
  return { type: "user", message: { role: "user", content: text }, parent_tool_use_id: null };
}

// Hold the second prompt until the setters have run.
let startSecondTurn!: () => void;
const secondTurnReady = new Promise<void>((resolve) => {
  startSecondTurn = resolve;
});

async function* turnPrompts(): AsyncGenerator<SDKUserMessage, void> {
  yield userMessage("Reply with exactly: ready");
  await secondTurnReady;
  yield userMessage("Reply with exactly: done");
}

const session = query({
  prompt: turnPrompts(),
  options: {
    model: "claude-sonnet-5",
  },
});

let turnModel = "";
let completedTurns = 0;

for await (const message of session) {
  if (message.type === "assistant") {
    turnModel = message.message.model;
  } else if (message.type === "result") {
    completedTurns += 1;
    if (completedTurns === 1) {
      console.log(`First turn model: ${turnModel}`);
      await session.setModel("claude-opus-5");
      await session.setPermissionMode("acceptEdits");
      startSecondTurn();
    } else {
      console.log(`Second turn model: ${turnModel}`);
      break;
    }
  }
}
```

```python Python theme={null}
import asyncio

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient

async def main():
    options = ClaudeAgentOptions(model="claude-sonnet-5")

    async with ClaudeSDKClient(options=options) as client:
        await client.query("Reply with exactly: ready")
        first_model = ""
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                first_model = message.model

        await client.set_model("claude-opus-5")
        await client.set_permission_mode("acceptEdits")

        await client.query("Reply with exactly: done")
        second_model = ""
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                second_model = message.model

    print(f"First turn model: {first_model}")
    print(f"Second turn model: {second_model}")

asyncio.run(main())
```

在 Claude API 上，程式列印 `First turn model: claude-sonnet-5`，然後在切換後列印 `Second turn model: claude-opus-5`。

> [!NOTE]
>
> 每個模型都有自己的提示快取，因此在工作階段中途切換後，下一個請求會以新模型的費率重新計算完整對話未快取。如需詳細資訊，請參閱[切換模型](https://code.claude.com/docs/zh-TW/prompt-caching.md#switching-models)。

## 設定特定功能

下表將每個選項對應到它設定的功能。如需本頁面未涵蓋的選項，請參閱 [TypeScript](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md#options) 和 [Python](https://code.claude.com/docs/zh-TW/agent-sdk/python.md#claudeagentoptions) 參考。如果您知道您的目標但不知道哪個選項為其服務，請從[選擇正確的功能](https://code.claude.com/docs/zh-TW/agent-sdk/claude-code-features.md#choose-the-right-feature)開始。

| TypeScript | Python | 控制 | 涵蓋在 |
| - | - | - | - |
| `permissionMode` | `permission_mode` | 代理可以在沒有核准的情況下做什麼 | [設定權限](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md) |
| `allowedTools` | `allowed_tools` | 哪些工具呼叫被預先核准 | [設定權限](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md) |
| `canUseTool` | `can_use_tool` | 您對工具呼叫的核准回呼 | [處理工具核准請求](https://code.claude.com/docs/zh-TW/agent-sdk/user-input.md#handle-tool-approval-requests) |
| `systemPrompt` | `system_prompt` | 代理的指示 | [修改系統提示](https://code.claude.com/docs/zh-TW/agent-sdk/modifying-system-prompts.md) |
| `settingSources` | `setting_sources` | 哪些檔案系統設定載入 | [在 SDK 中使用 Claude Code 功能](https://code.claude.com/docs/zh-TW/agent-sdk/claude-code-features.md) |
| `mcpServers` | `mcp_servers` | 外部工具伺服器 | [使用 MCP 連接到外部工具](https://code.claude.com/docs/zh-TW/agent-sdk/mcp.md) |
| `agents` | `agents` | 子代理定義 | [子代理](https://code.claude.com/docs/zh-TW/agent-sdk/subagents.md) |
| `hooks` | `hooks` | 生命週期點的回呼 | [Hooks](https://code.claude.com/docs/zh-TW/agent-sdk/hooks.md) |
| `skills` | `skills` | 哪些 skills 載入 | [使用 skills 擴展代理](https://code.claude.com/docs/zh-TW/agent-sdk/skills.md) |
| `plugins` | `plugins` | 哪些 plugins 載入 | [Plugins](https://code.claude.com/docs/zh-TW/agent-sdk/plugins.md) |
| `outputFormat` | `output_format` | 結構化輸出架構 | [結構化輸出](https://code.claude.com/docs/zh-TW/agent-sdk/structured-outputs.md) |
| `resume` | `resume` | 繼續儲存的工作階段 | [工作階段](https://code.claude.com/docs/zh-TW/agent-sdk/sessions.md) |
| `forkSession` | `fork_session` | 分支工作階段 | [工作階段](https://code.claude.com/docs/zh-TW/agent-sdk/sessions.md) |
| `sessionStore` | `session_store` | 外部工作階段持續性 | [工作階段儲存](https://code.claude.com/docs/zh-TW/agent-sdk/session-storage.md) |
| `enableFileCheckpointing` | `enable_file_checkpointing` | 可倒帶的檔案編輯 | [檔案 checkpointing](https://code.claude.com/docs/zh-TW/agent-sdk/file-checkpointing.md) |
| `effort` | `effort` | Claude 在回應中投入多少工作 | [努力級別](https://code.claude.com/docs/zh-TW/agent-sdk/agent-loop.md#effort-level) |
| `sandbox` | `sandbox` | 工具執行的沙箱行為 | [TypeScript](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md#sandbox-configuration) 和 [Python](https://code.claude.com/docs/zh-TW/agent-sdk/python.md#sandbox-configuration) 參考，部署內容在[安全部署](https://code.claude.com/docs/zh-TW/agent-sdk/secure-deployment.md) |

## 後續步驟

若要查看組合成工作代理的設定：

* **[快速入門](https://code.claude.com/docs/zh-TW/agent-sdk/quickstart.md)**：端到端建立並執行第一個代理
* **[範例](https://code.claude.com/docs/zh-TW/agent-sdk/examples.md)**：找到完整、可執行的專案或符合您想要建立的內容的引導式 Claude Cookbook 配方
* **[多租戶隔離](https://code.claude.com/docs/zh-TW/agent-sdk/hosting.md#multi-tenant-isolation)**：使用 `settingSources` / `setting_sources`、`env` 和 `cwd` 隔離每個租戶的設定和記憶

<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/agent-sdk/hooks | lastmod: 2026-11-03 | section: Agent SDK / Control and observability -->
> 來源：https://code.claude.com/docs/zh-TW/agent-sdk/hooks（官方 zh-TW，lastmod 2026-11-03）｜分類：Agent SDK › Control and observability｜EN 摘要：Intercept and customize agent behavior at key execution points with hooks

# 使用 hooks 攔截和控制代理行為

> 在代理執行的關鍵點使用 hooks 攔截和自訂代理行為

Hooks 是回調函數，在代理事件發生時執行您的程式碼，例如工具被呼叫、會話啟動或執行停止。使用 hooks，您可以：

* **阻止危險操作**在執行前，例如破壞性的 shell 命令或未授權的檔案存取
* **記錄和稽核**工具呼叫以進行合規性、除錯或分析
* **轉換輸入和輸出**以清理資料、注入認證或重定向檔案路徑
* **要求人工批准**敏感操作，例如資料庫寫入或 API 呼叫
* **追蹤會話生命週期**以管理狀態、清理資源或傳送通知

## Hook 如何運作

**1. 事件觸發**

agent 執行期間發生某事，SDK 觸發事件：工具即將被呼叫（`PreToolUse`）、工具返回結果（`PostToolUse`）、subagent 啟動或停止、agent 閒置或執行完成。請參閱[完整事件列表](#available-hooks)。

**2. SDK 收集已註冊的 hook**

SDK 檢查為該事件類型註冊的 hook。這包括您在 `options.hooks` 中傳遞的回呼 hook，以及當相應的 [`settingSources`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#settingsource) 或 [`setting_sources`](https://code.claude.com/docs/zh-TW/agent-sdk/python#settingsource) 項目啟用時（預設 `query()` 選項即為啟用）來自設定檔的 shell 命令 hook。

**3. matcher 篩選哪些 hook 執行**

如果 hook 有 [`matcher`](#matchers) 模式（例如 `"Write|Edit"`），SDK 會針對事件的目標（例如工具名稱）測試它。沒有 matcher 的 hook 會針對該類型的每個事件執行。

**4. 回呼函式執行**

每個相符 hook 的[回呼函式](#callback-functions)會接收有關正在發生之事的輸入：工具名稱、其引數、工作階段 ID 以及其他事件特定的詳細資訊。

**5. 您的回呼返回決定**

執行任何操作（日誌、API 呼叫、驗證）後，您的回呼會返回[輸出物件](#outputs)，告訴 agent 該做什麼：允許操作、阻止它、修改輸入或將上下文注入對話。

此範例註冊一個 `PreToolUse` hook（步驟 1），帶有 `"Write|Edit"` matcher（步驟 3），因此回呼會針對 Write 和 Edit 工具觸發。觸發時，回呼接收工具的輸入（步驟 4），檢查檔案路徑是否指向 `.env` 檔案，並返回 `permissionDecision: "deny"` 以阻止操作（步驟 5）：

```python Python theme={null}
import asyncio
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeSDKClient,
    ClaudeAgentOptions,
    HookMatcher,
    ResultMessage,
)


# 定義一個接收工具呼叫詳細資訊的 hook 回呼
async def protect_env_files(input_data, tool_use_id, context):
    # 從工具的輸入引數中提取檔案路徑
    file_path = input_data["tool_input"].get("file_path", "")
    file_name = file_path.split("/")[-1]

    # 如果指向 .env 檔案，阻止操作
    if file_name.lower() == ".env":
        return {
            "hookSpecificOutput": {
                "hookEventName": input_data["hook_event_name"],
                "permissionDecision": "deny",
                "permissionDecisionReason": "Cannot modify .env files",
            }
        }

    # 返回空物件以允許操作
    return {}


async def main():
    options = ClaudeAgentOptions(
        hooks={
            # 為 PreToolUse 事件註冊 hook
            # matcher 篩選為僅 Write 和 Edit 工具呼叫
            "PreToolUse": [HookMatcher(matcher="Write|Edit", hooks=[protect_env_files])]
        }
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query("建立一個 .env 檔案，包含標準本地開發資料庫設定")
        async for message in client.receive_response():
            # 篩選助手和結果訊息
            if isinstance(message, (AssistantMessage, ResultMessage)):
                print(message)


asyncio.run(main())
```

```typescript TypeScript theme={null}
import { query, HookCallback, PreToolUseHookInput } from "@anthropic-ai/claude-agent-sdk";

// 使用 HookCallback 類型定義 hook 回呼
const protectEnvFiles: HookCallback = async (input, toolUseID, { signal }) => {
  // 將輸入轉換為特定 hook 類型以確保類型安全
  const preInput = input as PreToolUseHookInput;

  // 轉換 tool_input 以存取其屬性（在 SDK 中類型為 unknown）
  const toolInput = preInput.tool_input as Record<string, unknown>;
  const filePath = toolInput?.file_path as string;
  const fileName = filePath?.split("/").pop();

  // 如果指向 .env 檔案，阻止操作
  if (fileName?.toLowerCase() === ".env") {
    return {
      hookSpecificOutput: {
        hookEventName: preInput.hook_event_name,
        permissionDecision: "deny",
        permissionDecisionReason: "Cannot modify .env files"
      }
    };
  }

  // 返回空物件以允許操作
  return {};
};

for await (const message of query({
  prompt: "建立一個 .env 檔案，包含標準本地開發資料庫設定",
  options: {
    hooks: {
      // 為 PreToolUse 事件註冊 hook
      // matcher 篩選為僅 Write 和 Edit 工具呼叫
      PreToolUse: [{ matcher: "Write|Edit", hooks: [protectEnvFiles] }]
    }
  }
})) {
  // 篩選助手和結果訊息
  if (message.type === "assistant" || message.type === "result") {
    console.log(message);
  }
}
```

此 hook 會拒絕 `file_path` 以 `/.env` 結尾的 Write 或 Edit 呼叫，不分大小寫。在 Windows 上，`file_path` 使用反斜線，例如 `C:\project\.env`，因此此 hook 會允許對 `C:\project\.env` 的 Write 或 Edit 呼叫。

> [!WARNING]
>
> `Write|Edit` matcher 將此 hook 限制於 Write 和 Edit 工具。如果 Claude 使用 Bash 命令寫入 `.env`，此 hook 不會執行。若要在[沙箱執行](https://code.claude.com/docs/zh-TW/sandboxing.md)的情況下阻止 Bash 寫入檔案，請參閱 [Python](https://code.claude.com/docs/zh-TW/agent-sdk/python.md#sandbox-configuration) 或 [TypeScript](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md#sandbox-configuration) 的沙箱設定。

## 可用的 hooks

SDK 為代理執行的不同階段提供 hooks。某些 hooks 在兩個 SDK 中都可用，而其他則僅限 TypeScript。

| Hook 事件 | Python SDK | TypeScript SDK | 觸發條件 | 使用案例範例 |
| - | - | - | - | - |
| `PreToolUse` | 是 | 是 | 工具呼叫請求（可以阻止或修改） | 阻止危險的 shell 命令 |
| `PostToolUse` | 是 | 是 | 工具執行結果 | 將檔案變更記錄到審計追蹤 |
| `PostToolUseFailure` | 是 | 是 | 工具執行失敗 | 處理或記錄工具錯誤 |
| `PostToolBatch` | 否 | 是 | 一整批工具呼叫解決，每批一次，在下一個模型呼叫之前 | 為整個批次注入約定 |
| [`UserPromptSubmit`](https://code.claude.com/docs/zh-TW/hooks#userpromptsubmit) | 是 | 是 | 提交提示詞時，包括 Claude Code 自行開始的回合 | 將額外上下文注入提示詞 |
| [`UserPromptExpansion`](https://code.claude.com/docs/zh-TW/hooks#userpromptexpansion) | 否 | 是 | 使用者輸入的命令或 MCP 提示在到達 Claude 之前擴展為提示。當 Claude 自己呼叫技能時不會觸發 | 阻止命令直接呼叫或在輸入技能時新增上下文 |
| `MessageDisplay` | 否 | 是 | 助手訊息包含文字完成，每則訊息一次，包含完整訊息文字 | 編輯或重新格式化顯示的文字，不改變記錄 |
| `Stop` | 是 | 是 | 代理執行停止 | 在退出前保存會話狀態 |
| `StopFailure` | 否 | 是 | 回合以 API 錯誤結束，而不是正常停止 | 記錄失敗或傳送警示 |
| `SubagentStart` | 是 | 是 | 子代理初始化 | 追蹤平行任務生成 |
| `SubagentStop` | 是 | 是 | 子代理完成 | 聚合來自平行任務的結果 |
| `PreCompact` | 是 | 是 | 對話壓縮請求 | 在摘要前存檔完整記錄 |
| `PostCompact` | 否 | 是 | 對話壓縮完成 | 記錄生成的摘要 |
| [`PreModelSwitch`](https://code.claude.com/docs/zh-TW/hooks#premodelswitch) | 否 | 是 | 請求的模型切換，在發生之前（可以阻止） | 阻止切換到特定模型 |
| [`PostModelSwitch`](https://code.claude.com/docs/zh-TW/hooks#postmodelswitch) | 否 | 是 | 會話的模型變更，包括自動回退 | 為新模型提供 Claude 模型特定的指導 |
| `PermissionRequest` | 是 | 是 | 工具呼叫需要權限決定 | 自訂權限處理 |
| `PermissionDenied` | 否 | 是 | 自動模式拒絕工具呼叫，包括沒有分類器判決的拒絕 | 記錄拒絕，或告訴模型它可能重試；Claude Code 對沒有判決的拒絕忽略 `retry: true`。請參閱 [PermissionDenied](https://code.claude.com/docs/zh-TW/hooks.md#permissiondenied) |
| `SessionStart` | 否 | 是 | 會話初始化 | 初始化記錄和遙測 |
| `SessionEnd` | 否 | 是 | 會話終止 | 清理臨時資源 |
| `Notification` | 是 | 是 | 代理狀態訊息 | 將代理狀態更新傳送到 Slack 或 PagerDuty |
| `Setup` | 否 | 是 | 會話設定/維護 | 執行初始化任務 |
| `TeammateIdle` | 否 | 是 | 隊友變為空閒 | 重新分配工作或通知 |
| `TaskCreated` | 否 | 是 | 透過 `TaskCreate` 工具建立任務 | 強制執行任務命名約定 |
| [`TaskCompleted`](https://code.claude.com/docs/zh-TW/hooks#taskcompleted) | 否 | 是 | 任務標記為已完成 | 在任務關閉前要求通過測試 |
| `Elicitation` | 否 | 是 | MCP 伺服器在任務中途請求使用者輸入 | 以程式設計方式回應 MCP 輸入請求 |
| `ElicitationResult` | 否 | 是 | 使用者回應 MCP 引出 | 在回應返回伺服器之前修改或阻止回應 |
| `ConfigChange` | 否 | 是 | 設定檔案變更 | 動態重新載入設定 |
| `InstructionsLoaded` | 否 | 是 | `CLAUDE.md` 或規則檔案載入到上下文中 | 審計哪些指令檔案載入 |
| `WorktreeCreate` | 否 | 是 | Git worktree 已建立 | 追蹤隔離的工作區 |
| `WorktreeRemove` | 否 | 是 | 正在移除由 `WorktreeCreate` hook 建立的 worktree | 清理工作區資源 |
| `CwdChanged` | 否 | 是 | 會話期間工作目錄變更 | 按目錄重新載入環境變數 |
| `FileChanged` | 否 | 是 | 監視的檔案被修改、建立或刪除 | 當專案檔案變更時重新載入設定 |
| `DirectoryAdded` | 否 | 是 | 會話期間新增工作目錄 | 為中途新增的儲存庫安裝相依性 |

## 設定 hook

要設定 hook，請在 agent 選項的 `hooks` 欄位中傳遞它（Python 中的 `ClaudeAgentOptions`，TypeScript 中的 `options` 物件）。此程式碼片段假設您已經定義了 hook 回調，例如上面範例中 Python 的 `protect_env_files` 或 TypeScript 的 `protectEnvFiles`：

```python Python theme={null}
options = ClaudeAgentOptions(
    hooks={"PreToolUse": [HookMatcher(matcher="Bash", hooks=[my_callback])]}
)

async with ClaudeSDKClient(options=options) as client:
    await client.query("Your prompt")
    async for message in client.receive_response():
        print(message)
```

```typescript TypeScript theme={null}
for await (const message of query({
  prompt: "Your prompt",
  options: {
    hooks: {
      PreToolUse: [{ matcher: "Bash", hooks: [myCallback] }]
    }
  }
})) {
  console.log(message);
}
```

`hooks` 選項是一個字典（Python）或物件（TypeScript），其中：

* **鍵**：[hook 事件名稱](#available-hooks)，例如 `'PreToolUse'`、`'PostToolUse'` 和 `'Stop'`
* **值**：[matcher](#matchers) 的陣列，每個都包含可選的篩選模式和您的[回調函數](#callback-functions)

### Matcher

使用 matcher 篩選您的回調何時觸發。`matcher` 欄位根據 hook 事件類型比對不同的值。例如，工具型 hook 比對工具名稱，而 `Notification` hook 比對通知類型。

SDK matcher 遵循與[設定檔中的 matcher](https://code.claude.com/docs/zh-TW/hooks.md#matcher-patterns) 相同的規則。該部分記錄了精確字串和正規表達式評估路徑、其版本要求，以及每個事件類型的 matcher 值。

| 選項 | 類型 | 預設值 | 描述 |
| - | - | - | - |
| `matcher` | `string` | `undefined` | 針對事件的篩選欄位比對的模式，遵循[設定檔中 matcher 的規則](https://code.claude.com/docs/zh-TW/hooks.md#matcher-patterns)。對於工具 hook，該欄位是工具名稱。內建工具包括 `Bash`、`Read`、`Write`、`Edit`、`Glob`、`Grep`、`WebFetch`、`Agent` 等。請參閱[工具輸入類型](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md#tool-input-types)以取得完整列表。MCP 工具使用模式 `mcp__<server>__<action>`，其中 `<server>` 是您在 `mcpServers` 設定中使用的鍵，其拼寫方式依照[工具命名慣例](https://code.claude.com/docs/zh-TW/agent-sdk/mcp.md#tool-naming-convention)所述。 |
| `hooks` | `HookCallback[]` | - | 必需。當模式比對成功時執行的回調函數陣列 |
| `timeout` | `number` | `undefined` | 逾時時間（秒）。省略時，Claude Code 會套用[事件的預設逾時](#hook-timeout)。您的 SDK 回調遵循 `command` hook 預設值 |
| `onFailure` | `"continue" \| "block"` | `undefined` | 回調失敗時的處理方式。設定 `"block"` 以[在回調失敗時阻止該動作](#block-the-action-when-a-callback-fails)。在 Python 中，請使用 `on_failure` |

盡可能使用 `matcher` 模式來針對特定工具。帶有 `'Bash'` 的 matcher 只針對 Bash 命令執行，而省略模式會針對事件的每次出現執行您的回調。

### 回調函數

#### 輸入

每個 hook 回調接收三個引數：

* **輸入資料：** 一個包含事件詳細資訊的類型物件。每個 hook 類型都有自己的輸入形狀。例如，`PreToolUseHookInput` 包括 `tool_name` 和 `tool_input`，而 `NotificationHookInput` 包括 `message`。請參閱 [TypeScript](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md#hookinput) 和 [Python](https://code.claude.com/docs/zh-TW/agent-sdk/python.md#hookinput) SDK 參考中的完整類型定義。
  * 所有 hook 輸入共享 `session_id`、`cwd` 和 `hook_event_name`。
  * 當 hook 在 subagent 內觸發時，`agent_id` 和 `agent_type` 會被填充。在 TypeScript 中，這些在基本 hook 輸入上，可供所有 hook 類型使用。在 Python 中，它們是 `PreToolUse`、`PostToolUse`、`PostToolUseFailure` 和 `PermissionRequest` 上的可選欄位，以及 `SubagentStart` 和 `SubagentStop` 上的必需欄位。
* **工具使用 ID**（`str | None` / `string | undefined`）：關聯同一工具呼叫的 `PreToolUse` 和 `PostToolUse` 事件。
* **上下文：** 在 TypeScript 中，包含用於取消的 `signal` 屬性（`AbortSignal`）。在 Python 中，此引數保留供將來使用。

#### 輸出

您的回調返回一個具有兩類欄位的物件：

* **頂級欄位**在每個事件上被接受：`systemMessage` 向使用者顯示訊息，`continue`（Python 中的 `continue_`）決定此 hook 後 agent 是否繼續執行。某些事件會捨棄它們或將它們傳遞到其他地方。每個[事件的部分](https://code.claude.com/docs/zh-TW/hooks.md#hook-events)在 hook 頁面上說明它們的位置。
* **`hookSpecificOutput`** 控制目前操作。內部的欄位取決於 hook 事件類型：
  * 對於 `PreToolUse` hook，這是您設定 `permissionDecision`（`"allow"`、`"deny"`、`"ask"` 或 `"defer"`）、`permissionDecisionReason` 和 `updatedInput` 的地方。如果您返回 `"defer"`，該回合會以一則 `stop_reason` 為 `"tool_deferred"` 的結果訊息結束，以便您可以[稍後繼續該呼叫](https://code.claude.com/docs/zh-TW/hooks.md#defer-a-tool-call-for-later)。
  * 對於 `PostToolUse` hook，您可以設定 `additionalContext` 以將資訊附加到工具結果。要在 Claude 看到之前替換工具的輸出，請設定 `updatedToolOutput`，這適用於兩個 SDK 中的任何工具。較舊的 `updatedMCPToolOutput` 欄位僅替換 MCP 工具輸出。
  * 在 TypeScript SDK 中，`PostToolUse` 回調也可以返回 `classifierContext`，這是關於工具呼叫結果的簡短說明，用於[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)權限分類器。因為您的回調在您應用程式自己的程序中執行，分類器可能會將您在說明中轉達的使用者陳述視為使用者意圖。該欄位需要 TypeScript Agent SDK v0.3.236 或更新版本。[為自動模式分類器註解結果](https://code.claude.com/docs/zh-TW/hooks.md#annotate-a-result-for-the-auto-mode-classifier)涵蓋長度上限、僅同步規則，以及不要在說明中放入的內容。

返回 `{}` 以允許操作而不進行變更。SDK 回調 hook 使用與 [Claude Code shell 命令 hook](https://code.claude.com/docs/zh-TW/hooks.md#json-output) 相同的 JSON 輸出格式，其記錄每個欄位和事件特定選項。對於 SDK 類型定義，請參閱 [TypeScript](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md#synchookjsonoutput) 和 [Python](https://code.claude.com/docs/zh-TW/agent-sdk/python.md#synchookjsonoutput) SDK 參考。

> [!NOTE]
>
> 當多個 `PreToolUse` hook 返回不同的[決策](https://code.claude.com/docs/zh-TW/hooks.md#pretooluse-decision-control)時，`deny` 優先於 `defer`，`defer` 優先於 `ask`，`ask` 優先於 `allow`。

#### 非同步輸出

預設情況下，agent 在您的 hook 返回前等待。如果您的 hook 執行副作用，例如日誌記錄或傳送 webhook，並且不需要影響 agent 的行為，您可以改為返回非同步輸出。這告訴 agent 立即繼續，無需等待 hook 完成。在此程式碼片段中，Python 中的 `send_to_logging_service` 和 TypeScript 中的 `sendToLoggingService` 代表您定義的任何日誌記錄函數：

```python Python theme={null}
async def async_hook(input_data, tool_use_id, context):
    # 啟動背景任務，然後立即返回
    asyncio.create_task(send_to_logging_service(input_data))
    return {"async_": True, "asyncTimeout": 30000}
```

```typescript TypeScript theme={null}
const asyncHook: HookCallback = async (input, toolUseID, { signal }) => {
  // 啟動背景任務，然後立即返回
  sendToLoggingService(input).catch(console.error);
  return { async: true, asyncTimeout: 30000 };
};
```

| 欄位 | 類型 | 描述 |
| - | - | - |
| `async` | `true` | 表示非同步模式。agent 無需等待即可繼續。在 Python 中，使用 `async_` 以避免保留關鍵字。 |
| `asyncTimeout` | `number` | 背景操作的可選逾時時間（毫秒） |

> [!NOTE]
>
> 非同步輸出無法阻止、修改或將上下文注入操作，因為 agent 已經繼續。僅將它們用於副作用，例如日誌記錄、指標或通知。

### 在回調失敗時阻止該動作

在大多數事件中，如果回調拋出錯誤或返回未通過驗證的輸出，該動作會繼續進行，而您的應用程式會收到一則 `tag` 為 `hook_callback_failed` 的 [`SDKInformationalMessage`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#sdkinformationalmessage) 警告。如此一來，當機的 `PreToolUse` 防護會讓工具呼叫進入一般的權限流程。沒有返回任何內容的回調（例如沒有 `return` 的路徑）也視為失敗。在 Python 中，請從 `SystemMessage.data` 讀取 `tag`。

若要改為阻止該動作，請在 matcher 上設定 `onFailure: "block"`（TypeScript）或 `on_failure="block"`（Python）。需要 TypeScript Agent SDK v0.3.317 或更新版本，或 Python Agent SDK v0.2.177 或更新版本。此範例會在 Python 中的 `check_policy` 或 TypeScript 中的 `checkPolicy` 失敗時阻止 Bash 呼叫：

```python Python theme={null}
options = ClaudeAgentOptions(
    hooks={
        "PreToolUse": [
            HookMatcher(matcher="Bash", hooks=[check_policy], on_failure="block")
        ]
    }
)
```

```typescript TypeScript theme={null}
import type { Options } from "@anthropic-ai/claude-agent-sdk";

const options: Options = {
  hooks: {
    PreToolUse: [{ matcher: "Bash", hooks: [checkPolicy], onFailure: "block" }]
  }
};
```

若要測試，請讓回調引發錯誤，並要求 Claude 執行 Bash 命令。工具結果會包含 `failed; blocking because onFailure is "block"`，而 Claude 不會看到您的錯誤文字。

當回調沒有意見時，請返回 `{}`。設定 `"block"` 後，沒有 `return` 的路徑會阻止該動作。捕捉自身錯誤並返回 `{}` 的回調不算失敗，因此請讓錯誤從防護中向外傳遞。

#### 行為不同的事件

設定 `"block"` 時，這些事件不一定會阻止：

* **`Stop`、`SubagentStop`、`TaskCompleted` 和 `TeammateIdle`**：這些事件會忽略此選項，因此動作會繼續進行。
* **`PermissionRequest`**：只有在您的 `canUseTool` 回調回應之前到達時，阻止才會生效。
* **`PostToolUse`**：工具已經執行，因此 Claude 會將失敗作為回饋接收。

超過逾時時間的回調依照 [Hook 逾時](#hook-timeout)處理。設定 `"block"` 時，逾時也會阻止 `PreCompact`、`Elicitation` 和 `WorktreeCreate`。

#### `onFailure` 的啟動錯誤

設定 `"block"` 時，若無法遵循此選項，查詢會在啟動時失敗，且不會傳送任何提示詞：

* **Claude Code 不支援此選項**：錯誤包含 `does not honor`。請更新 Claude Code，或移除此選項。
* **工作階段已在執行中且未註冊您的 hook**：錯誤包含 `did not register your hooks`。請啟動新的工作階段。

## 範例

本節中的幾個範例僅顯示回調函數。若要執行其中一個，請在您的選項的 `hooks` 欄位中的匹配事件下註冊回調，如 [設定 hooks](#configure-hooks) 中所示。

### 修改工具輸入

此範例攔截 Write 工具呼叫並重寫 `file_path` 引數以預先加上 `/sandbox`。回調返回帶有修改路徑的 `updatedInput` 和 `permissionDecision: 'allow'` 以自動批准重寫的操作：

```python Python theme={null}
async def redirect_to_sandbox(input_data, tool_use_id, context):
    if input_data["hook_event_name"] != "PreToolUse":
        return {}

    if input_data["tool_name"] == "Write":
        original_path = input_data["tool_input"].get("file_path", "")
        return {
            "hookSpecificOutput": {
                "hookEventName": input_data["hook_event_name"],
                "permissionDecision": "allow",
                "updatedInput": {
                    **input_data["tool_input"],
                    "file_path": f"/sandbox{original_path}",
                },
            }
        }
    return {}
```

```typescript TypeScript theme={null}
const redirectToSandbox: HookCallback = async (input, toolUseID, { signal }) => {
  if (input.hook_event_name !== "PreToolUse") return {};

  const preInput = input as PreToolUseHookInput;
  const toolInput = preInput.tool_input as Record<string, unknown>;
  if (preInput.tool_name === "Write") {
    const originalPath = toolInput.file_path as string;
    return {
      hookSpecificOutput: {
        hookEventName: preInput.hook_event_name,
        permissionDecision: "allow",
        updatedInput: {
          ...toolInput,
          file_path: `/sandbox${originalPath}`
        }
      }
    };
  }
  return {};
};
```

> [!NOTE]
>
> 將 `updatedInput` 與 `permissionDecision: 'allow'` 配對以自動批准修改的輸入，或使用 `permissionDecision: 'ask'` 以將其顯示給使用者。如果您省略 `permissionDecision`，修改的輸入仍然適用並流經正常的權限評估。使用 `'defer'` 時，`updatedInput` 會被忽略。始終返回新物件，而不是改變原始 `tool_input`。

若要確認重定向，請將前綴設定為您可以寫入的路徑，例如 `./sandbox` 或 `/tmp/sandbox`（macOS 不允許建立根層級的 `/sandbox` 目錄），然後要求代理寫入檔案：Write 工具在訊息流中的結果會顯示帶有您的沙箱前綴的路徑，而不是 Claude 要求的路徑。

### 新增上下文並阻止工具

此範例拒絕 `file_path` 以 `/etc` 開頭的工具呼叫，並向模型和使用者解釋原因：

* `permissionDecision: 'deny'` 停止工具呼叫。
* `permissionDecisionReason` 告訴模型原因。
* `systemMessage` 向使用者顯示發生了什麼。

```python Python theme={null}
async def block_etc_writes(input_data, tool_use_id, context):
    file_path = input_data["tool_input"].get("file_path", "")

    if file_path.startswith("/etc"):
        return {
            # 頂級欄位：顯示給使用者的訊息
            "systemMessage": "Remember: system directories like /etc are protected.",
            # hookSpecificOutput：阻止操作
            "hookSpecificOutput": {
                "hookEventName": input_data["hook_event_name"],
                "permissionDecision": "deny",
                "permissionDecisionReason": "Writing to /etc is not allowed",
            },
        }
    return {}
```

```typescript TypeScript theme={null}
const blockEtcWrites: HookCallback = async (input, toolUseID, { signal }) => {
  const preInput = input as PreToolUseHookInput;
  const toolInput = preInput.tool_input as Record<string, unknown>;
  const filePath = toolInput?.file_path as string;

  if (filePath?.startsWith("/etc")) {
    return {
      // 頂級欄位：顯示給使用者的訊息
      systemMessage: "Remember: system directories like /etc are protected.",
      // hookSpecificOutput：阻止操作
      hookSpecificOutput: {
        hookEventName: preInput.hook_event_name,
        permissionDecision: "deny",
        permissionDecisionReason: "Writing to /etc is not allowed"
      }
    };
  }
  return {};
};
```

若要確認阻止，請在 `PreToolUse` 下使用 `Write|Edit` 匹配器註冊回調，並要求代理在 `/etc` 下建立檔案：Write 工具在訊息流中的結果包含 `Writing to /etc is not allowed`，且不會建立任何檔案。

### 自動批准特定工具

預設情況下，agent 可能在使用某些工具前提示權限。此範例透過返回 `permissionDecision: 'allow'` 自動批准唯讀檔案系統工具（Read、Glob、Grep），讓它們無需使用者確認即可執行（從[網路路徑](https://code.claude.com/docs/zh-TW/permissions.md#network-paths)讀取除外），同時讓所有其他工具受到正常權限檢查：

```python Python theme={null}
async def auto_approve_read_only(input_data, tool_use_id, context):
    if input_data["hook_event_name"] != "PreToolUse":
        return {}

    read_only_tools = ["Read", "Glob", "Grep"]
    if input_data["tool_name"] in read_only_tools:
        return {
            "hookSpecificOutput": {
                "hookEventName": input_data["hook_event_name"],
                "permissionDecision": "allow",
                "permissionDecisionReason": "Read-only tool auto-approved",
            }
        }
    return {}
```

```typescript TypeScript theme={null}
const autoApproveReadOnly: HookCallback = async (input, toolUseID, { signal }) => {
  if (input.hook_event_name !== "PreToolUse") return {};

  const preInput = input as PreToolUseHookInput;
  const readOnlyTools = ["Read", "Glob", "Grep"];
  if (readOnlyTools.includes(preInput.tool_name)) {
    return {
      hookSpecificOutput: {
        hookEventName: preInput.hook_event_name,
        permissionDecision: "allow",
        permissionDecisionReason: "Read-only tool auto-approved"
      }
    };
  }
  return {};
};
```

### 註冊多個 hooks

當事件觸發時，符合的 hook 會並行執行。對於權限決定，以最嚴格的結果為準。任一 hook 的 `deny` 都會阻止工具呼叫。由於完成順序是不確定的，請編寫每個 hook 以獨立運作，而不是依賴另一個 hook 已先執行。

下面的範例註冊三個獨立檢查，每個都[省略 matcher](https://code.claude.com/docs/zh-TW/hooks.md#matcher-patterns)。範例中的 hook 名稱，例如 Python 中的 `audit_logger` 或 TypeScript 中的 `auditLogger`，代表您定義的回調：

```python Python theme={null}
options = ClaudeAgentOptions(
    hooks={
        "PreToolUse": [
            HookMatcher(hooks=[authorization_check]),
            HookMatcher(hooks=[input_validator]),
            HookMatcher(hooks=[audit_logger]),
        ]
    }
)
```

```typescript TypeScript theme={null}
const options = {
  hooks: {
    PreToolUse: [
      { hooks: [authorizationCheck] },
      { hooks: [inputValidator] },
      { hooks: [auditLogger] }
    ]
  }
};
```

### 使用多工具匹配器篩選

使用多工具匹配器在相關工具間共享一個回調。此範例註冊三個具有不同範圍的匹配器，每個 hook 它命名代表您定義的回調：

* 管道分隔的精確列表（`Write|Edit|NotebookEdit`）針對 Write、Edit 和 NotebookEdit 工具觸發 `file_security_hook`。
* 正規表達式（`^mcp__`）針對任何名稱以 `mcp__` 開頭的 MCP 工具觸發 `mcp_audit_hook`。
* 省略的 matcher 觸發 `global_logger`，不依工具名稱篩選。

```python Python theme={null}
options = ClaudeAgentOptions(
    hooks={
        "PreToolUse": [
            # 匹配檔案修改工具
            HookMatcher(matcher="Write|Edit|NotebookEdit", hooks=[file_security_hook]),
            # 匹配所有 MCP 工具
            HookMatcher(matcher="^mcp__", hooks=[mcp_audit_hook]),
            # 匹配所有內容（無匹配器）
            HookMatcher(hooks=[global_logger]),
        ]
    }
)
```

```typescript TypeScript theme={null}
const options = {
  hooks: {
    PreToolUse: [
      // 匹配檔案修改工具
      { matcher: "Write|Edit|NotebookEdit", hooks: [fileSecurityHook] },

      // 匹配所有 MCP 工具
      { matcher: "^mcp__", hooks: [mcpAuditHook] },

      // 匹配所有內容（無匹配器）
      { hooks: [globalLogger] }
    ]
  }
};
```

### 追蹤子代理活動

使用 `SubagentStop` hooks 監控子代理何時完成其工作。請參閱 [TypeScript](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md#hookinput) 和 [Python](https://code.claude.com/docs/zh-TW/agent-sdk/python.md#hookinput) SDK 參考中的完整輸入類型。此範例在每次子代理完成時記錄摘要：

```python Python theme={null}
async def subagent_tracker(input_data, tool_use_id, context):
    # 子代理完成時記錄子代理詳細資訊
    print(f"[SUBAGENT] Completed: {input_data['agent_id']}")
    print(f"  Transcript: {input_data['agent_transcript_path']}")
    print(f"  Tool use ID: {tool_use_id}")
    print(f"  Stop hook active: {input_data.get('stop_hook_active')}")
    return {}


options = ClaudeAgentOptions(
    hooks={"SubagentStop": [HookMatcher(hooks=[subagent_tracker])]}
)
```

```typescript TypeScript theme={null}
import { HookCallback, SubagentStopHookInput } from "@anthropic-ai/claude-agent-sdk";

const subagentTracker: HookCallback = async (input, toolUseID, { signal }) => {
  // 轉換為 SubagentStopHookInput 以存取子代理特定欄位
  const subInput = input as SubagentStopHookInput;

  // 子代理完成時記錄子代理詳細資訊
  console.log(`[SUBAGENT] Completed: ${subInput.agent_id}`);
  console.log(`  Transcript: ${subInput.agent_transcript_path}`);
  console.log(`  Tool use ID: ${toolUseID}`);
  console.log(`  Stop hook active: ${subInput.stop_hook_active}`);
  return {};
};

const options = {
  hooks: {
    SubagentStop: [{ hooks: [subagentTracker] }]
  }
};
```

若要確認 hook 觸發，請註冊回調並要求代理將小任務委派給子代理，例如列出目前目錄中的檔案：當子代理完成時，回調會列印 `[SUBAGENT] Completed:` 行，其中包含子代理的 ID 和文字記錄路徑。

### 從 hooks 發出 HTTP 請求

Hooks 可以執行非同步操作，例如 HTTP 請求。在您的 hook 內捕捉錯誤，而不是讓它們傳播。

此範例在每個工具完成後傳送 webhook，記錄哪個工具執行以及何時執行。hook 捕捉來自失敗 webhook 的錯誤：

```python Python theme={null}
import asyncio
import json
import urllib.request
from datetime import datetime


def _send_webhook(tool_name):
    """同步幫助程式，將工具使用資料 POST 到外部 webhook。"""
    data = json.dumps(
        {
            "tool": tool_name,
            "timestamp": datetime.now().isoformat(),
        }
    ).encode()
    req = urllib.request.Request(
        "https://api.example.com/webhook",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    urllib.request.urlopen(req)


async def webhook_notifier(input_data, tool_use_id, context):
    # 僅在工具完成後觸發（PostToolUse），而不是之前
    if input_data["hook_event_name"] != "PostToolUse":
        return {}

    try:
        # 在執行緒中執行阻止 HTTP 呼叫以避免阻止事件迴圈
        await asyncio.to_thread(_send_webhook, input_data["tool_name"])
    except Exception as e:
        # 記錄錯誤但不引發
        print(f"Webhook request failed: {e}")

    return {}
```

```typescript TypeScript theme={null}
import { query, HookCallback, PostToolUseHookInput } from "@anthropic-ai/claude-agent-sdk";

const webhookNotifier: HookCallback = async (input, toolUseID, { signal }) => {
  // 僅在工具完成後觸發（PostToolUse），而不是之前
  if (input.hook_event_name !== "PostToolUse") return {};

  try {
    await fetch("https://api.example.com/webhook", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tool: (input as PostToolUseHookInput).tool_name,
        timestamp: new Date().toISOString()
      }),
      // 傳遞 signal 以便在 hook 超時時取消請求
      signal
    });
  } catch (error) {
    // 分別處理取消和其他錯誤
    if (error instanceof Error && error.name === "AbortError") {
      console.log("Webhook request cancelled");
    }
    // 不重新拋出
  }

  return {};
};

// 註冊為 PostToolUse hook
for await (const message of query({
  prompt: "Refactor the auth module",
  options: {
    hooks: {
      PostToolUse: [{ hooks: [webhookNotifier] }]
    }
  }
})) {
  console.log(message);
}
```

若要確認 hook 觸發，請將 webhook URL 指向您可以監視的端點並傳送使用工具的提示：hook 會在每個工具完成後傳送帶有工具名稱和時間戳記的 POST。

### 將通知轉發到 Slack

使用 `Notification` hooks 接收來自代理的系統通知並將其轉發到外部服務。在 SDK 工作階段中，Claude Code 為以下通知類型執行此 hook：

* [`permission_prompt`](https://code.claude.com/docs/zh-TW/hooks#notification) 一旦權限請求在您的 [`canUseTool` 回調](https://code.claude.com/docs/zh-TW/agent-sdk/user-input) 上等待約六秒。需要 TypeScript Agent SDK v0.3.233 或更新版本，或 Python Agent SDK v0.2.139 或更新版本
* `elicitation_complete` 和 `elicitation_response` 用於使用者提示引導流程
* `plugin_notification`：當 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/api.md#show-something-without-starting-a-turn) 呼叫 `$.ui.notify` 時

Claude Code 從 SDK 工作階段不執行的互動式 UI 發出其他類型，例如 `idle_prompt`、`auth_success` 和 `elicitation_dialog`。

每個通知都包括帶有人類可讀描述的 `message` 欄位，以及可選的 `title`。

此範例將每個通知轉發到 Slack 頻道。它需要 [Slack 傳入 webhook URL](https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/)，您可以通過將應用程式新增到 Slack 工作區並啟用傳入 webhooks 來建立：

```python Python theme={null}
import asyncio
import json
import urllib.request

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, HookMatcher


def _send_slack_notification(message):
    """同步幫助程式，透過傳入 webhook 將訊息傳送到 Slack。"""
    data = json.dumps({"text": f"Agent status: {message}"}).encode()
    req = urllib.request.Request(
        "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    urllib.request.urlopen(req)


async def notification_handler(input_data, tool_use_id, context):
    try:
        # 在執行緒中執行阻塞式 HTTP 呼叫以避免阻塞事件迴圈
        await asyncio.to_thread(_send_slack_notification, input_data.get("message", ""))
    except Exception as e:
        print(f"Failed to send notification: {e}")

    # 返回空物件。Notification hook 不修改 agent 行為
    return {}


async def main():
    options = ClaudeAgentOptions(
        hooks={
            # 為 Notification 事件註冊 hook（不需要 matcher）
            "Notification": [HookMatcher(hooks=[notification_handler])],
        },
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query("Analyze this codebase")
        async for message in client.receive_response():
            print(message)


asyncio.run(main())
```

```typescript TypeScript theme={null}
import { query, HookCallback, NotificationHookInput } from "@anthropic-ai/claude-agent-sdk";

// 定義一個將通知傳送到 Slack 的 hook 回調
const notificationHandler: HookCallback = async (input, toolUseID, { signal }) => {
  // 轉換為 NotificationHookInput 以存取訊息欄位
  const notification = input as NotificationHookInput;

  try {
    // POST 通知訊息到 Slack 傳入 webhook
    await fetch("https://hooks.slack.com/services/YOUR/WEBHOOK/URL", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: `Agent status: ${notification.message}`
      }),
      // 傳遞 signal 以便在 hook 超時時取消請求
      signal
    });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      console.log("Notification cancelled");
    } else {
      console.error("Failed to send notification:", error);
    }
  }

  // 返回空物件。通知 hooks 不修改代理行為
  return {};
};

// 為通知事件註冊 hook（不需要匹配器）
for await (const message of query({
  prompt: "Analyze this codebase",
  options: {
    hooks: {
      Notification: [{ hooks: [notificationHandler] }]
    }
  }
})) {
  console.log(message);
}
```

當 `Notification` 事件觸發時，hook 會將通知的 `message`（前綴為 `Agent status:`）發佈到您的 webhook 目標的頻道。

## 修復常見問題

### Hook 未觸發

* 驗證 hook 事件名稱正確且區分大小寫（`PreToolUse`，而不是 `preToolUse`）
* 檢查您的 matcher 模式是否與工具名稱完全匹配
* 確保 hook 在 `options.hooks` 中的正確事件類型下
* 對於支援 matcher 的非工具 hook，如 `Notification` 和 `SubagentStop`，matcher 匹配不同的欄位，而 `Stop` 完全忽略 matcher（請參閱 [matcher 模式](https://code.claude.com/docs/zh-TW/hooks.md#matcher-patterns)）
* 當 agent 達到 [`max_turns`](https://code.claude.com/docs/zh-TW/agent-sdk/python#claudeagentoptions) 限制時，hook 可能不會觸發，因為工作階段在 hook 可以執行前結束

### Matcher 未按預期篩選

Matcher 只匹配工具名稱，不匹配檔案路徑或其他引數。要按檔案路徑篩選，請在您的 hook 內檢查 `tool_input.file_path`：

```typescript theme={null}
const myHook: HookCallback = async (input, toolUseID, { signal }) => {
  const preInput = input as PreToolUseHookInput;
  const toolInput = preInput.tool_input as Record<string, unknown>;
  const filePath = toolInput?.file_path as string;
  if (!filePath?.endsWith(".md")) return {}; // 跳過非 markdown 檔案
  // 處理 markdown 檔案...
  return {};
};
```

### Hook 逾時

Claude Code 以逾時時間執行每個回調，您可以在其 `HookMatcher` 上使用 `timeout` 欄位以秒為單位設定。當您未設定時，Claude Code 使用事件的預設值：大多數事件為 600 秒，`UserPromptSubmit`、`PreModelSwitch` 和 `PostModelSwitch` 為 30 秒，`MessageDisplay` 為 10 秒。Claude Code 在關閉期間執行 `SessionEnd` 回調，使用較短的 [SessionEnd 逾時預算](https://code.claude.com/docs/zh-TW/hooks.md#sessionend-input)，預設為 1.5 秒。

當回調超過其逾時時間時，Claude Code 取消它並捨棄其輸出，工作階段繼續而不是掛起。接下來發生的情況取決於事件：

* `PreToolUse`：Claude Code 阻止工具呼叫。如果其他所有 hook 都未返回任何內容或僅返回 `allow` 決定，工具結果會告知 Claude 該 hook 未在逾時前回應，回合繼續。如果您的另一個 hook 已拒絕該呼叫，其拒絕仍會傳達給 Claude：工具結果包含該 hook 的理由，逾時文字可能接在其後。

  在 v2.1.210 之前，Claude Code 將逾時報告給 Claude 作為使用者拒絕，這使無人值守工作階段停止並等待輸入。
* `PostToolUse` 和 `PostToolUseFailure`：Claude Code 保留工具結果，回合繼續。
* `UserPromptSubmit` 和 [`UserPromptExpansion`](https://code.claude.com/docs/zh-TW/hooks#userpromptexpansion)：Claude Code 以指出 hook 名稱和逾時的訊息阻止提示詞，工作階段繼續。在 v2.1.208 之前，當這些事件上的回調逾時時，Claude Code 以 `error_during_execution` 結束查詢。
* `Stop` 和 `SubagentStop`：逾時的回調計為不返回任何決定。Agent 或 subagent 停止，如同該回調已允許它，而您其他 hook 在該事件上的決定仍然適用。在 Claude Code v2.1.273 之前，逾時的 `Stop` 或 `SubagentStop` 回調計為失敗的 hook 執行，Claude Code 捨棄您其他 hook 在該事件上的決定。
* `SessionStart`：逾時的回調計為不返回任何輸出，工作階段繼續，使用您其他 `SessionStart` hook 的輸出。
* `PreModelSwitch`：Claude Code 阻止模型切換。未回答的 hook 尚未核准切換。
* 其他事件，如 `Notification`、`PreCompact` 和 `PostModelSwitch`：Claude Code 記錄失敗並繼續。若使用 [`onFailure: "block"`](#block-the-action-when-a-callback-fails)，`PreCompact`、`Elicitation` 或 `WorktreeCreate` 上的逾時會阻止該動作。

主工作階段中 `Stop` 或 `SessionStart` 回調首次逾時時，Claude Code 也會新增 [`SDKInformationalMessage`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#sdkinformationalmessage) 到訊息流，說明驅動工作階段的應用程式未回應。稍後的逾時在您的應用程式保持無回應時不會重複該訊息。

如果您在回調待處理時中斷查詢，Claude Code 取消待處理的工具呼叫。在 v2.1.208 之前，如果您在待處理的 `PreToolUse` 回調期間中斷，工具呼叫仍可能繼續進行。

如果您的回調需要更多時間，請在其 `HookMatcher` 上設定更高的 `timeout`。在 TypeScript 中，使用第三個回調引數中的 `AbortSignal` 以在逾時觸發時優雅地處理取消。

### 工具意外被阻止

* 檢查所有 `PreToolUse` hook 是否返回 `permissionDecision: 'deny'`
* 將日誌新增到您的 hook 以查看它們返回的 `permissionDecisionReason`
* 驗證 matcher 模式不會太寬泛：空 matcher 匹配所有工具

### 修改的輸入未應用

* 確保 `updatedInput` 在 `hookSpecificOutput` 內，而不是在頂級：

  ```typescript theme={null}
  return {
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "allow",
      updatedInput: { command: "new command" }
    }
  };
  ```

* 不要將 `updatedInput` 與 `permissionDecision: 'defer'` 配對，這會捨棄修改的輸入。省略 `permissionDecision` 是可以的：修改的輸入仍通過正常權限評估應用。您也可以返回 `'allow'` 以自動核准修改的輸入或 `'ask'` 以向使用者顯示以供核准

* 在 `hookSpecificOutput` 中包括 `hookEventName` 以識別輸出適用於哪個 hook 類型

### Python 中不可用工作階段 hook

`SessionStart` 和 `SessionEnd` 可以在 TypeScript 中註冊為 SDK 回調 hook，但在 Python SDK 中不可用，因為其 `HookEvent` 類型省略它們。在 Python 中，它們僅作為[shell 命令 hook](https://code.claude.com/docs/zh-TW/hooks.md#hook-events)在設定檔中定義，例如 `.claude/settings.json`。您的 SDK 應用程式載入哪些設定檔取決於 [`setting_sources`](https://code.claude.com/docs/zh-TW/agent-sdk/python#settingsource) 或 [`settingSources`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#settingsource)。如果您設定了該選項，請包括存放 hook 的來源：

```python Python theme={null}
options = ClaudeAgentOptions(
    setting_sources=["project"],  # 載入 .claude/settings.json 包括 hooks
)
```

```typescript TypeScript theme={null}
const options = {
  settingSources: ["project"] // 載入 .claude/settings.json 包括 hooks
};
```

要改為執行初始化邏輯作為 Python SDK 回調，請使用 `client.receive_response()` 的第一條訊息作為您的觸發器。

### Subagent 權限提示倍增

生成多個 subagent 時，每個 subagent 可能會分別請求其自身工具呼叫的權限。要避免重複提示，請使用 `PreToolUse` hook 自動核准特定工具，或設定權限規則，subagent 會[從父對話繼承](https://code.claude.com/docs/zh-TW/sub-agents.md#permission-modes)這些規則。

### Subagent 的遞迴 hook 迴圈

生成 subagent 的 `UserPromptSubmit` hook 如果這些 subagent 觸發相同的 hook，可能會建立無限迴圈。要防止這種情況：

* 使用共享變數或工作階段狀態來追蹤您是否已在 subagent 內
* 將 hook 範圍限制為僅針對頂級 agent 工作階段執行

### systemMessage 未出現在輸出中

`systemMessage` 欄位向使用者顯示訊息，而不是模型。在 Claude Code v2.1.227 或更新版本上，hook 的 `systemMessage` 可以在訊息流中呈現為 [`SDKInformationalMessage`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#sdkinformationalmessage)。它是否呈現取決於事件。hooks 頁面上每個[事件的部分](https://code.claude.com/docs/zh-TW/hooks.md#hook-events)說明輸出如何呈現。要改為將上下文傳遞給模型，請返回 [`additionalContext`](https://code.claude.com/docs/zh-TW/hooks#add-context-for-claude)。

在 v2.1.227 之前，SDK 僅針對 `SessionStart` 和 `Setup` hook 在訊息流中呈現 hook 輸出。對於任何其他事件，輸出僅出現在 [`includeHookEvents`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#options)（Python 中的 `include_hook_events`）新增的生命週期事件中。該選項的條目涵蓋每個 hook 事件產生的生命週期事件。

如果您需要可靠地將 hook 決定呈現給您的應用程式，請分別記錄它們或使用專用輸出頻道。

## 相關資源

* [Claude Code hooks 參考](https://code.claude.com/docs/zh-TW/hooks.md)：完整的 JSON 輸入/輸出架構、事件文件和匹配器模式
* [Claude Code hooks 指南](https://code.claude.com/docs/zh-TW/hooks-guide.md)：shell 命令 hook 範例和逐步解說
* [TypeScript SDK 參考](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md)：hook 類型、輸入/輸出定義和配置選項
* [Python SDK 參考](https://code.claude.com/docs/zh-TW/agent-sdk/python.md)：hook 類型、輸入/輸出定義和配置選項
* [權限](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md)：控制您的代理可以做什麼
* [自訂工具](https://code.claude.com/docs/zh-TW/agent-sdk/custom-tools.md)：建立工具以擴展代理功能

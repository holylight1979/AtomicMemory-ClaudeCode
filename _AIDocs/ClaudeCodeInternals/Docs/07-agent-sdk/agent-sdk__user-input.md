<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/agent-sdk/user-input | lastmod: 2026-10-25 | section: Agent SDK / Input and output -->
> 來源：https://code.claude.com/docs/zh-TW/agent-sdk/user-input（官方 zh-TW，lastmod 2026-10-25）｜分類：Agent SDK › Input and output｜EN 摘要：Surface Claude's approval requests and clarifying questions to users, then return their decisions to the SDK.

# 處理批准和使用者輸入

> 將 Claude 的批准請求和澄清問題呈現給使用者，然後將他們的決定返回給 SDK。

在處理任務時，Claude 有時需要與使用者確認。它可能需要在刪除檔案前獲得許可，或需要詢問新專案應使用哪個資料庫。您的應用程式需要將這些請求呈現給使用者，以便 Claude 可以根據他們的輸入繼續進行。

Claude 在兩種情況下請求使用者輸入：當它需要**使用工具的許可**（例如刪除檔案或執行命令）時，以及當它有**澄清問題**（透過 `AskUserQuestion` 工具）時。兩者都會觸發您的 `canUseTool` 回呼，該回呼會暫停執行，直到您返回回應。這與普通對話輪次不同，在普通對話輪次中 Claude 完成後會等待您的下一條訊息。

對於澄清問題，Claude 會生成問題和選項。您的角色是將它們呈現給使用者並返回他們的選擇。您無法將自己的問題添加到此流程中；如果您需要自己詢問使用者某些事項，請在應用程式邏輯中單獨進行。

回呼可以無限期地保持待處理狀態。執行保持暫停狀態，直到您的回呼返回。如果使用者可能需要比您的流程合理保持運行的時間更長的時間來回應，請註冊一個 [`PreToolUse` hook](https://code.claude.com/docs/zh-TW/agent-sdk/hooks)，它返回 [`defer` 決定](https://code.claude.com/docs/zh-TW/hooks#defer-a-tool-call-for-later)而不是在回呼中等待，以便流程可以退出並稍後從持久化會話恢復。

本指南向您展示如何檢測每種類型的請求並做出適當的回應。

## 檢測 Claude 何時需要輸入

在您的查詢選項中傳遞 `canUseTool` 回呼。每當 Claude 需要使用者輸入時，回呼就會觸發，接收工具名稱和輸入作為參數：

```python Python theme={null}
from claude_agent_sdk import ClaudeAgentOptions


async def handle_tool_request(tool_name, input_data, context):
    # 提示使用者並返回允許或拒絕
    ...


options = ClaudeAgentOptions(can_use_tool=handle_tool_request)
```

```typescript TypeScript theme={null}
import type { CanUseTool } from "@anthropic-ai/claude-agent-sdk";

const handleToolRequest: CanUseTool = async (toolName, input, options) => {
  // options includes { signal: AbortSignal, suggestions?: PermissionUpdate[] }
  // 在此提示使用者，然後返回允許或拒絕
  return { behavior: "deny", message: "User declined" };
};

const options = { canUseTool: handleToolRequest };
```

回呼在兩種情況下觸發：

1. **工具需要批准**：Claude 想要使用未被[權限規則](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md)或權限模式自動批准的工具。檢查 `tool_name` 以查看工具（例如 `"Bash"`、`"Write"`）。
2. **Claude 提出問題**：Claude 呼叫 `AskUserQuestion` 工具。檢查 `tool_name == "AskUserQuestion"` 以不同方式處理它。如果您指定 `tools` 陣列，請包含 `AskUserQuestion` 以使其正常工作。有關詳細資訊，請參閱[處理澄清問題](#handle-clarifying-questions)。

> [!WARNING]
>
> **回呼永遠不會針對自動批准的工具觸發。** [權限評估流程](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#how-permissions-are-evaluated)中任何較早的批准、允許規則或 `acceptEdits` 或 `bypassPermissions` 等模式，都會在諮詢 `canUseTool` 之前解決呼叫。如果您在 `allowed_tools` 中列出工具，`canUseTool` 檢查該工具只會在[評估流程](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#how-permissions-are-evaluated)將呼叫路由回提示時執行，例如詢問規則或 `plan` 模式。對於必須應用於每個工具呼叫的邏輯，請使用 [`PreToolUse` hook](https://code.claude.com/docs/zh-TW/agent-sdk/hooks)，它在流程的其餘部分之前執行，可以允許、拒絕或修改請求。
>
> 允許規則不會預先核准[任何模式都不會自動核准的動作](https://code.claude.com/docs/zh-TW/permission-modes.md#actions-no-mode-auto-approves)；請參閱[權限如何評估](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#how-permissions-are-evaluated)以了解其中哪些到達回呼，以及在 `dontAsk` 和 `auto` 模式中會發生什麼。

您也可以使用 [`PermissionRequest` hook](https://code.claude.com/docs/zh-TW/agent-sdk/hooks#available-hooks) 在 Claude 等待批准時發送外部通知（Slack、電子郵件、推送）。

## 處理工具批准請求

一旦您在查詢選項中傳遞了 `canUseTool` 回呼，當 Claude 想要使用未經權限流程中較早步驟批准的工具時，它就會觸發。在某些設定中，例如 `dontAsk` 模式，Claude Code 不會呼叫它；[權限如何被評估](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#how-permissions-are-evaluated)的最後一步列出了它們並說明了呼叫會發生什麼。

您的回呼接收三個參數：

| 參數 | 描述 |
| - | - |
| `toolName` | Claude 想要使用的工具名稱（例如 `"Bash"`、`"Write"`、`"Edit"`） |
| `input` | Claude 傳遞給工具的參數。內容因工具而異。 |
| `options` (TS) / `context` (Python) | 其他上下文，包括可選的 `suggestions`（建議的 `PermissionUpdate` 條目以避免重新提示）和取消信號。在 TypeScript 中，`signal` 是 `AbortSignal`；在 Python 中，信號欄位保留供將來使用。有關 Python，請參閱 [`ToolPermissionContext`](https://code.claude.com/docs/zh-TW/agent-sdk/python#toolpermissioncontext)。 |

`input` 物件包含工具特定的參數。常見範例：

| 工具 | 輸入欄位 |
| - | - |
| `Bash` | `command`、`description`、`timeout` |
| `Write` | `file_path`、`content` |
| `Edit` | `file_path`、`old_string`、`new_string` |
| `Read` | `file_path`、`offset`、`limit` |

有關完整的輸入架構，請參閱 SDK 參考：[Python](https://code.claude.com/docs/zh-TW/agent-sdk/python.md#tool-input%2Foutput-types) | [TypeScript](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md#tool-input-types)。

您可以向使用者顯示此資訊，以便他們可以決定是否允許或拒絕該操作，然後返回適當的回應。

以下範例要求 Claude 建立和刪除測試檔案。當 Claude 嘗試每個操作時，回呼會將工具請求列印到終端機並提示進行 y/n 批准。

```python Python theme={null}
import asyncio

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
from claude_agent_sdk.types import (
    HookMatcher,
    PermissionResultAllow,
    PermissionResultDeny,
    ToolPermissionContext,
)


async def can_use_tool(
    tool_name: str, input_data: dict, context: ToolPermissionContext
) -> PermissionResultAllow | PermissionResultDeny:
    # 顯示工具請求
    print(f"\nTool: {tool_name}")
    if tool_name == "Bash":
        print(f"Command: {input_data.get('command')}")
        if input_data.get("description"):
            print(f"Description: {input_data.get('description')}")
    else:
        print(f"Input: {input_data}")

    # 獲取使用者批准
    response = input("Allow this action? (y/n): ")

    # 根據使用者的回應返回允許或拒絕
    if response.lower() == "y":
        # 允許：工具使用原始（或修改的）輸入執行
        return PermissionResultAllow(updated_input=input_data)
    else:
        # 拒絕：工具不執行，Claude 看到訊息
        return PermissionResultDeny(message="User denied this action")


# 必需的解決方法：虛擬 hook 保持流開放以供 can_use_tool 使用
async def dummy_hook(input_data, tool_use_id, context):
    return {"continue_": True}


async def prompt_stream():
    yield {
        "type": "user",
        "message": {
            "role": "user",
            "content": "Create a test file in /tmp and then delete it",
        },
    }


async def main():
    async for message in query(
        prompt=prompt_stream(),
        options=ClaudeAgentOptions(
            can_use_tool=can_use_tool,
            hooks={"PreToolUse": [HookMatcher(matcher=None, hooks=[dummy_hook])]},
        ),
    ):
        if isinstance(message, ResultMessage) and message.subtype == "success":
            print(message.result)


asyncio.run(main())
```

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";
import * as readline from "readline";

// 幫助程式在終端機中提示使用者輸入
function prompt(question: string): Promise<string> {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });
  return new Promise((resolve) =>
    rl.question(question, (answer) => {
      rl.close();
      resolve(answer);
    })
  );
}

for await (const message of query({
  prompt: "Create a test file in /tmp and then delete it",
  options: {
    canUseTool: async (toolName, input) => {
      // 顯示工具請求
      console.log(`\nTool: ${toolName}`);
      if (toolName === "Bash") {
        console.log(`Command: ${input.command}`);
        if (input.description) console.log(`Description: ${input.description}`);
      } else {
        console.log(`Input: ${JSON.stringify(input, null, 2)}`);
      }

      // 獲取使用者批准
      const response = await prompt("Allow this action? (y/n): ");

      // 根據使用者的回應返回允許或拒絕
      if (response.toLowerCase() === "y") {
        // 允許：工具使用原始（或修改的）輸入執行
        return { behavior: "allow", updatedInput: input };
      } else {
        // 拒絕：工具不執行，Claude 看到訊息
        return { behavior: "deny", message: "User denied this action" };
      }
    }
  }
})) {
  if ("result" in message) console.log(message.result);
}
```

此範例使用 y/n 流程，其中除 `y` 以外的任何輸入都被視為拒絕。在實踐中，您可能會構建一個更豐富的 UI，讓使用者修改請求、提供回饋或完全重定向 Claude。有關所有回應方式，請參閱[回應工具請求](#respond-to-tool-requests)。

### 回應工具請求

您的回呼返回以下兩種回應類型之一：

| 回應 | Python | TypeScript |
| - | - | - |
| **允許** | `PermissionResultAllow(updated_input=...)` | `{ behavior: "allow", updatedInput }` |
| **拒絕** | `PermissionResultDeny(message=...)` | `{ behavior: "deny", message }` |

允許時，工具會使用 Claude 要求的輸入執行，除非您返回修改的輸入，TypeScript 中為 `updatedInput` 或 Python 中為 `updated_input`。在 v2.1.207 之前，Claude Code 拒絕了省略 `updatedInput` 的允許結果，並以驗證錯誤拒絕了工具呼叫。

拒絕時，提供說明原因的訊息。Claude 會看到此訊息並可能調整其方法。

除了允許或拒絕之外，您還可以修改工具的輸入或提供幫助 Claude 調整其方法的上下文：

* **批准**：讓工具按 Claude 要求執行
* **批准並進行更改**：在執行前修改輸入（例如清理路徑、添加約束）
* **批准並記住**：回應建議的權限規則，以便匹配的呼叫在下次跳過提示
* **拒絕**：阻止工具並告訴 Claude 原因
* **建議替代方案**：阻止但引導 Claude 朝著使用者想要的方向發展
* **完全重定向**：使用[串流輸入](https://code.claude.com/docs/zh-TW/agent-sdk/streaming-vs-single-mode.md)向 Claude 發送全新指令

以下片段中的 `ask_user` 和 `askUser` 幫助程式代表您應用程式自己的提示 UI。

> [tab] 批准
>
> 使用者按原樣批准該操作。傳遞回呼中的 `input` 不變，工具完全按 Claude 要求執行。
>
> ```python Python theme={null}
> async def can_use_tool(tool_name, input_data, context):
>     print(f"Claude wants to use {tool_name}")
>     approved = await ask_user("Allow this action?")
>
>     if approved:
>         return PermissionResultAllow(updated_input=input_data)
>     return PermissionResultDeny(message="User declined")
> ```
>
> ```typescript TypeScript theme={null}
> canUseTool: async (toolName, input) => {
>   console.log(`Claude wants to use ${toolName}`);
>   const approved = await askUser("Allow this action?");
>
>   if (approved) {
>     return { behavior: "allow", updatedInput: input };
>   }
>   return { behavior: "deny", message: "User declined" };
> };
> ```

> [tab] 批准並進行更改
>
> 使用者批准但想先修改請求。您可以在工具執行前更改輸入。Claude 會看到結果，但不會被告知您更改了任何內容。適用於清理參數、添加約束或限制存取範圍。
>
> ```python Python theme={null}
> async def can_use_tool(tool_name, input_data, context):
>     if tool_name == "Bash":
>         # 使用者批准，但將所有命令限制在沙箱中
>         sandboxed_input = {**input_data}
>         sandboxed_input["command"] = input_data["command"].replace(
>             "/tmp", "/tmp/sandbox"
>         )
>         return PermissionResultAllow(updated_input=sandboxed_input)
>     return PermissionResultAllow(updated_input=input_data)
> ```
>
> ```typescript TypeScript theme={null}
> canUseTool: async (toolName, input) => {
>   if (toolName === "Bash") {
>     // 使用者批准，但將所有命令限制在沙箱中
>     const sandboxedInput = {
>       ...input,
>       command: input.command.replace("/tmp", "/tmp/sandbox")
>     };
>     return { behavior: "allow", updatedInput: sandboxedInput };
>   }
>   return { behavior: "allow", updatedInput: input };
> };
> ```

> [tab] 批准並記住
>
> 使用者批准且不想再被詢問此類呼叫。第三個回呼參數帶有 `suggestions`，這是現成的 [`PermissionUpdate`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#permissionupdate) 條目陣列。在 `updatedPermissions` 中回應其中一個以應用它。具有 `localSettings` 目的地的建議會將規則寫入 `.claude/settings.local.json`，以便未來的工作階段跳過匹配呼叫的提示。
>
> 在 TypeScript 中，針對選項帶有 [`suppressAlwaysAllowRule: true`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#canusetool) 的請求，跳過始終允許的選擇。該提示需要 Agent SDK v0.3.268 或更新版本，Python `context` 不帶有它。
>
> Python 範例需要 `claude-agent-sdk` 0.1.80 或更新版本。
>
> ```python Python theme={null}
> async def can_use_tool(tool_name, input_data, context):
>     choice = await ask_user(f"Allow {tool_name}?", ["once", "always", "no"])
>
>     if choice == "always":
>         persist = [
>             s for s in context.suggestions if s.destination == "localSettings"
>         ]
>         return PermissionResultAllow(
>             updated_input=input_data, updated_permissions=persist
>         )
>     if choice == "once":
>         return PermissionResultAllow(updated_input=input_data)
>     return PermissionResultDeny(message="User declined")
> ```
>
> ```typescript TypeScript theme={null}
> canUseTool: async (toolName, input, { suggestions = [] }) => {
>   const choice = await askUser(`Allow ${toolName}?`, ["once", "always", "no"]);
>
>   if (choice === "always") {
>     const persist = suggestions.filter(
>       (s) => s.destination === "localSettings"
>     );
>     return {
>       behavior: "allow",
>       updatedInput: input,
>       updatedPermissions: persist
>     };
>   }
>   if (choice === "once") {
>     return { behavior: "allow", updatedInput: input };
>   }
>   return { behavior: "deny", message: "User declined" };
> };
> ```

> [tab] 拒絕
>
> 使用者不希望發生此操作。阻止工具並提供說明原因的訊息。Claude 會看到此訊息並可能嘗試不同的方法。
>
> ```python Python theme={null}
> async def can_use_tool(tool_name, input_data, context):
>     approved = await ask_user(f"Allow {tool_name}?")
>
>     if not approved:
>         return PermissionResultDeny(message="User rejected this action")
>     return PermissionResultAllow(updated_input=input_data)
> ```
>
> ```typescript TypeScript theme={null}
> canUseTool: async (toolName, input) => {
>   const approved = await askUser(`Allow ${toolName}?`);
>
>   if (!approved) {
>     return {
>       behavior: "deny",
>       message: "User rejected this action"
>     };
>   }
>   return { behavior: "allow", updatedInput: input };
> };
> ```

> [tab] 建議替代方案
>
> 使用者不想要此特定操作，但有不同的想法。阻止工具並在您的訊息中包含指導。Claude 會閱讀此內容並根據您的回饋決定如何進行。
>
> ```python Python theme={null}
> async def can_use_tool(tool_name, input_data, context):
>     if tool_name == "Bash" and "rm" in input_data.get("command", ""):
>         # 使用者不想刪除，建議改為存檔
>         return PermissionResultDeny(
>             message="User doesn't want to delete files. They asked if you could compress them into an archive instead."
>         )
>     return PermissionResultAllow(updated_input=input_data)
> ```
>
> ```typescript TypeScript theme={null}
> canUseTool: async (toolName, input) => {
>   if (toolName === "Bash" && input.command.includes("rm")) {
>     // 使用者不想刪除，建議改為存檔
>     return {
>       behavior: "deny",
>       message:
>         "User doesn't want to delete files. They asked if you could compress them into an archive instead."
>     };
>   }
>   return { behavior: "allow", updatedInput: input };
> };
> ```

> [tab] 完全重定向
>
> 如需完全改變方向（不只是輕推），請使用[串流輸入](https://code.claude.com/docs/zh-TW/agent-sdk/streaming-vs-single-mode.md)向 Claude 直接發送新指令。這會繞過目前的工具請求，並為 Claude 提供全新的指令來遵循。

## 處理澄清問題

當 Claude 需要在具有多個有效方法的任務上獲得更多方向時，它會呼叫 `AskUserQuestion` 工具。這會使用 `toolName` 設定為 `AskUserQuestion` 的方式觸發您的 `canUseTool` 回呼。輸入包含 Claude 的問題作為多選選項，您將其顯示給使用者並返回他們的選擇。

> [!TIP]
>
> 澄清問題在 [`plan` 模式](https://code.claude.com/docs/zh-TW/agent-sdk/permissions#plan-mode-plan)中特別常見，Claude 在其中探索程式碼庫並在提出計畫前提出問題。這使得計畫模式非常適合互動式工作流程，您希望 Claude 在進行更改前收集需求。

以下步驟顯示如何處理澄清問題：

**1. 傳遞 canUseTool 回呼**

在您的查詢選項中傳遞 `canUseTool` 回呼。預設情況下，`AskUserQuestion` 可用。如果您指定 `tools` 陣列來限制 Claude 的功能（例如，只有 `Read`、`Glob` 和 `Grep` 的唯讀代理），請在該陣列中包含 `AskUserQuestion`。否則，Claude 將無法提出澄清問題：

```python Python theme={null}
async for message in query(
    prompt="Analyze this codebase",
    options=ClaudeAgentOptions(
        # 在您的工具清單中包含 AskUserQuestion
        tools=["Read", "Glob", "Grep", "AskUserQuestion"],
        can_use_tool=can_use_tool,
    ),
):
    print(message)
```

```typescript TypeScript theme={null}
for await (const message of query({
  prompt: "Analyze this codebase",
  options: {
    // 在您的工具清單中包含 AskUserQuestion
    tools: ["Read", "Glob", "Grep", "AskUserQuestion"],
    canUseTool: async (toolName, input) => {
      // 核准每個呼叫的預留位置。「檢測 AskUserQuestion」步驟會取代它。
      return { behavior: "allow", updatedInput: input };
    }
  }
})) {
  console.log(message);
}
```

**2. 檢測 AskUserQuestion**

在您的回呼中，檢查 `toolName` 是否等於 `AskUserQuestion` 以不同方式處理它與其他工具：

```python Python theme={null}
async def can_use_tool(tool_name: str, input_data: dict, context):
    if tool_name == "AskUserQuestion":
        # 您從使用者收集答案的實現
        return await handle_clarifying_questions(input_data)
    # 正常處理其他工具
    return await prompt_for_approval(tool_name, input_data)
```

```typescript TypeScript theme={null}
canUseTool: async (toolName, input) => {
  if (toolName === "AskUserQuestion") {
    // 您從使用者收集答案的實現
    return handleClarifyingQuestions(input);
  }
  // 正常處理其他工具
  return promptForApproval(toolName, input);
};
```

**3. 解析問題輸入**

輸入在 `questions` 陣列中包含 Claude 的問題。每個問題都有 `question`（要顯示的文字）、`options`（選擇）和 `multiSelect`（是否允許多個選擇）：

```json theme={null}
{
  "questions": [
    {
      "question": "How should I format the output?",
      "header": "Format",
      "options": [
        { "label": "Summary", "description": "Brief overview" },
        { "label": "Detailed", "description": "Full explanation" }
      ],
      "multiSelect": false
    },
    {
      "question": "Which sections should I include?",
      "header": "Sections",
      "options": [
        { "label": "Introduction", "description": "Opening context" },
        { "label": "Conclusion", "description": "Final summary" }
      ],
      "multiSelect": true
    }
  ]
}
```

有關完整欄位描述，請參閱[問題格式](#question-format)。

**4. 從使用者收集答案**

向使用者呈現問題並收集他們的選擇。您如何執行此操作取決於您的應用程式：終端機提示、網路表單、行動對話框等。

**5. 將答案返回給 Claude**

將 `answers` 物件構建為記錄，其中每個鍵是 `question` 文字，每個值是所選選項的 `label`：

| 來自問題物件 | 用作 |
| - | - |
| `question` 欄位（例如 `"How should I format the output?"`） | 鍵 |
| 所選選項的 `label` 欄位（例如 `"Summary"`） | 值 |

對於多選問題，傳遞標籤陣列或使用 `", "` 連接它們。如果您[支援自由文字輸入](#support-free-text-input)，請使用使用者的自訂文字作為值。

```python Python theme={null}
return PermissionResultAllow(
    updated_input={
        "questions": input_data.get("questions", []),
        "answers": {
            "How should I format the output?": "Summary",
            "Which sections should I include?": ["Introduction", "Conclusion"],
        },
    }
)
```

```typescript TypeScript theme={null}
return {
  behavior: "allow",
  updatedInput: {
    questions: input.questions,
    answers: {
      "How should I format the output?": "Summary",
      "Which sections should I include?": "Introduction, Conclusion"
    }
  }
};
```

### 問題格式

輸入在 `questions` 陣列中包含 Claude 生成的問題。每個問題都有這些欄位：

| 欄位 | 描述 |
| - | - |
| `question` | 要顯示的完整問題文字 |
| `header` | 問題的簡短標籤（最多 12 個字元） |
| `options` | 2-4 個選擇的陣列，每個都有 `label` 和 `description`。TypeScript：可選 `preview`。請參閱[選項預覽](#option-previews-typescript)。 |
| `multiSelect` | 如果為 `true`，使用者可以選擇多個選項 |

您的回呼接收的結構：

```json theme={null}
{
  "questions": [
    {
      "question": "How should I format the output?",
      "header": "Format",
      "options": [
        { "label": "Summary", "description": "Brief overview of key points" },
        { "label": "Detailed", "description": "Full explanation with examples" }
      ],
      "multiSelect": false
    }
  ]
}
```

#### 選項預覽 (TypeScript)

`toolConfig.askUserQuestion.previewFormat` 為每個選項添加 `preview` 欄位，以便您的應用程式可以在標籤旁邊顯示視覺模型。沒有此設定，Claude 不會生成預覽，該欄位不存在。

| `previewFormat` | `preview` 包含 |
| :- | :- |
| 未設定（預設） | 欄位不存在。Claude 不會生成預覽。 |
| `"markdown"` | ASCII 藝術和圍欄程式碼區塊 |
| `"html"` | 樣式的 `<div>` 片段（SDK 在您的回呼執行前拒絕 `<script>`、`<style>` 和 `<!DOCTYPE>`） |

該格式適用於會話中的所有問題。Claude 在視覺比較有幫助的選項上包含 `preview`（佈局選擇、配色方案），並在不會的地方省略它（是/否確認、純文字選擇）。在呈現前檢查 `undefined`。

```typescript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  prompt: "Help me choose a card layout",
  options: {
    toolConfig: {
      askUserQuestion: { previewFormat: "html" }
    },
    canUseTool: async (toolName, input) => {
      // input.questions[].options[].preview 是 HTML 字串或 undefined
      return { behavior: "allow", updatedInput: input };
    }
  }
})) {
  // ...
}
```

帶有 HTML 預覽的選項：

```json theme={null}
{
  "label": "Compact",
  "description": "Title and metric value only",
  "preview": "<div style=\"padding:12px;border:1px solid #ddd;border-radius:8px\"><div style=\"font-size:12px;color:#666\">Active users</div><div style=\"font-size:28px;font-weight:600\">1,284</div></div>"
}
```

### 回應格式

返回 `answers` 物件，將每個問題的 `question` 欄位對應到所選選項的 `label`：

| 欄位 | 描述 |
| - | - |
| `questions` | 傳遞原始問題陣列（工具處理所需） |
| `answers` | 物件，其中鍵是問題文字，值是所選標籤 |
| `response` | 可選的自由形式回覆，使用者輸入的內容，而不是回答結構化問題 |

對於多選問題，傳遞標籤陣列或使用 `", "` 連接它們。對於每個問題的自由文字，例如「其他」選項，將使用者的文字放在 `answers[question]` 中，如[支援自由文字輸入](#support-free-text-input)中所示。僅當您的 UI 讓使用者關閉問題卡並輸入不是任何特定問題答案的一般回覆時，才設定 `response`。當設定 `response` 時，Claude 會收到「使用者回應：…」而不是每個問題的答案清單。

```jsonc theme={null}
{
  "questions": [
    // ...
  ],
  "answers": {
    "How should I format the output?": "Summary",
    "Which sections should I include?": ["Introduction", "Conclusion"]
  }
}
```

#### 支援自由文字輸入

Claude 的預定義選項不會總是涵蓋使用者想要的內容。要讓使用者輸入自己的答案：

* 在 Claude 的選項後顯示額外的「其他」選擇，接受文字輸入
* 使用使用者的自訂文字作為答案值（不是「其他」一詞）

有關完整實現，請參閱下方的[完整範例](#complete-example)。

### 完整範例

當 Claude 需要使用者輸入以繼續時，它會提出澄清問題。例如，當被要求幫助決定行動應用程式的技術堆棧時，Claude 可能會詢問跨平台與原生、後端偏好或目標平台。這些問題幫助 Claude 做出與使用者偏好相符的決定，而不是猜測。

此範例在終端機應用程式中處理這些問題。以下是每個步驟發生的情況：

1. **路由請求**：`canUseTool` 回呼檢查工具名稱是否為 `"AskUserQuestion"` 並路由到專用處理程式
2. **顯示問題**：處理程式循環遍歷 `questions` 陣列並列印每個問題及編號選項
3. **收集輸入**：使用者可以輸入數字以選擇選項，或直接輸入自由文字（例如「jquery」、「i don't know」）
4. **對應答案**：程式碼檢查輸入是否為數字（使用選項的標籤）或自由文字（直接使用文字）
5. **返回給 Claude**：回應包括原始 `questions` 陣列和 `answers` 對應

將 TypeScript 版本儲存為 `ask.ts` 並使用 `npx tsx ask.ts` 執行，或將 Python 版本儲存為 `ask.py` 並使用 `python ask.py` 執行。

```python Python theme={null}
import asyncio

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
from claude_agent_sdk.types import HookMatcher, PermissionResultAllow


def parse_response(response: str, options: list) -> str:
    """將使用者輸入解析為選項編號或自由文字。"""
    try:
        indices = [int(s.strip()) - 1 for s in response.split(",")]
        labels = [options[i]["label"] for i in indices if 0 <= i < len(options)]
        return ", ".join(labels) if labels else response
    except ValueError:
        return response


async def handle_ask_user_question(input_data: dict) -> PermissionResultAllow:
    """顯示 Claude 的問題並收集使用者答案。"""
    answers = {}

    for q in input_data.get("questions", []):
        print(f"\n{q['header']}: {q['question']}")

        options = q["options"]
        for i, opt in enumerate(options):
            print(f"  {i + 1}. {opt['label']} - {opt['description']}")
        if q.get("multiSelect"):
            print("  (Enter numbers separated by commas, or type your own answer)")
        else:
            print("  (Enter a number, or type your own answer)")

        response = input("Your choice: ").strip()
        answers[q["question"]] = parse_response(response, options)

    return PermissionResultAllow(
        updated_input={
            "questions": input_data.get("questions", []),
            "answers": answers,
        }
    )


async def can_use_tool(
    tool_name: str, input_data: dict, context
) -> PermissionResultAllow:
    # 將 AskUserQuestion 路由到我們的問題處理程式
    if tool_name == "AskUserQuestion":
        return await handle_ask_user_question(input_data)
    # 為此範例自動批准其他工具
    return PermissionResultAllow(updated_input=input_data)


async def prompt_stream():
    yield {
        "type": "user",
        "message": {
            "role": "user",
            "content": "Help me decide on the tech stack for a new mobile app",
        },
    }


# 必需的解決方法：虛擬 hook 保持流開放以供 can_use_tool 使用
async def dummy_hook(input_data, tool_use_id, context):
    return {"continue_": True}


async def main():
    async for message in query(
        prompt=prompt_stream(),
        options=ClaudeAgentOptions(
            can_use_tool=can_use_tool,
            hooks={"PreToolUse": [HookMatcher(matcher=None, hooks=[dummy_hook])]},
        ),
    ):
        if isinstance(message, ResultMessage) and message.subtype == "success":
            print(message.result)


asyncio.run(main())
```

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";
import type { PermissionResult } from "@anthropic-ai/claude-agent-sdk";
import * as readline from "readline/promises";

// 幫助程式在終端機中提示使用者輸入
async function prompt(question: string): Promise<string> {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  const answer = await rl.question(question);
  rl.close();
  return answer;
}

// 將使用者輸入解析為選項編號或自由文字
function parseResponse(response: string, options: any[]): string {
  const indices = response.split(",").map((s) => parseInt(s.trim()) - 1);
  const labels = indices
    .filter((i) => !isNaN(i) && i >= 0 && i < options.length)
    .map((i) => options[i].label);
  return labels.length > 0 ? labels.join(", ") : response;
}

// 顯示 Claude 的問題並收集使用者答案
async function handleAskUserQuestion(input: any): Promise<PermissionResult> {
  const answers: Record<string, string> = {};

  for (const q of input.questions) {
    console.log(`\n${q.header}: ${q.question}`);

    const options = q.options;
    options.forEach((opt: any, i: number) => {
      console.log(`  ${i + 1}. ${opt.label} - ${opt.description}`);
    });
    if (q.multiSelect) {
      console.log("  (Enter numbers separated by commas, or type your own answer)");
    } else {
      console.log("  (Enter a number, or type your own answer)");
    }

    const response = (await prompt("Your choice: ")).trim();
    answers[q.question] = parseResponse(response, options);
  }

  // 將答案返回給 Claude（必須包括原始問題）
  return {
    behavior: "allow",
    updatedInput: { questions: input.questions, answers }
  };
}

async function main() {
  for await (const message of query({
    prompt: "Help me decide on the tech stack for a new mobile app",
    options: {
      canUseTool: async (toolName, input) => {
        // 將 AskUserQuestion 路由到我們的問題處理程式
        if (toolName === "AskUserQuestion") {
          return handleAskUserQuestion(input);
        }
        // 為此範例自動批准其他工具
        return { behavior: "allow", updatedInput: input };
      }
    }
  })) {
    if ("result" in message) console.log(message.result);
  }
}

main();
```

## 限制

* **子代理**：`AskUserQuestion` 目前在透過 Agent 工具生成的子代理中不可用
* **問題限制**：每個 `AskUserQuestion` 呼叫支援 1-4 個問題，每個 2-4 個選項

## 獲取使用者輸入的其他方式

`canUseTool` 回呼和 `AskUserQuestion` 工具涵蓋大多數批准和澄清情況，但 SDK 提供其他方式來從使用者獲取輸入：

### 串流輸入

當您需要以下情況時，使用[串流輸入](https://code.claude.com/docs/zh-TW/agent-sdk/streaming-vs-single-mode.md)：

* **在任務中途中斷代理**：在 Claude 工作時發送取消信號或改變方向
* **提供額外上下文**：添加 Claude 需要的資訊，無需等待它詢問
* **構建聊天介面**：讓使用者在長時間運行的操作期間發送後續訊息

串流輸入非常適合對話式 UI，使用者在整個執行過程中與代理互動，而不僅僅在批准檢查點。

### 自訂工具

當您需要以下情況時，使用[自訂工具](https://code.claude.com/docs/zh-TW/agent-sdk/custom-tools.md)：

* **收集結構化輸入**：構建超越 `AskUserQuestion` 多選格式的表單、精靈或多步驟工作流程
* **整合外部批准系統**：連接到現有的票務、工作流程或批准平台
* **實現特定領域的互動**：創建針對您應用程式需求的工具，例如程式碼審查介面或部署檢查清單

自訂工具讓您完全控制互動，但需要比使用內建 `canUseTool` 回呼更多的實現工作。

## 相關資源

* [配置權限](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md)：設定權限模式和規則
* [使用 hooks 控制執行](https://code.claude.com/docs/zh-TW/agent-sdk/hooks.md)：在代理生命週期的關鍵點執行自訂程式碼
* [TypeScript SDK 參考](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md#canusetool)：完整 canUseTool API 文件

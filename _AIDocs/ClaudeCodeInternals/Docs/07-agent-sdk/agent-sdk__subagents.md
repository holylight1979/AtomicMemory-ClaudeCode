<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/agent-sdk/subagents | lastmod: 2026-10-21 | section: Agent SDK / Extend with tools -->
> 來源：https://code.claude.com/docs/zh-TW/agent-sdk/subagents（官方 zh-TW，lastmod 2026-10-21）｜分類：Agent SDK › Extend with tools｜EN 摘要：Define and invoke subagents to isolate context, run tasks in parallel, and apply specialized instructions in your Claude Agent SDK applications.

# SDK 中的子代理

> 定義並調用子代理以隔離上下文、並行運行任務，以及在 Claude Agent SDK 應用程式中應用專門指令。

子代理是您的主代理可以生成的獨立代理實例，用於處理專注的子任務。
使用它們來隔離上下文、並行運行多個分析，以及應用專門指令，而無需添加到主代理的提示中。

## 概述

您可以透過三種方式建立子代理：

* **以程式設計方式**：在您的 `query()` 選項中使用 `agents` 參數。請參閱 [TypeScript](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md#agentdefinition) 和 [Python](https://code.claude.com/docs/zh-TW/agent-sdk/python.md#agentdefinition) 參考資料
* **基於檔案系統**：在 `.claude/agents/` 目錄中將代理定義為 markdown 檔案。請參閱[將子代理定義為檔案](https://code.claude.com/docs/zh-TW/sub-agents.md)
* **內建通用型**：Claude 可以隨時透過 Agent 工具叫用內建的 `general-purpose` 子代理，無需您定義任何內容

本指南著重於以程式設計方式，這是 SDK 應用程式的建議做法。

## 使用子代理的好處

因為子代理是獨立的代理實例，將工作委派給它們可以帶來四個好處：

* **上下文隔離**：每個子代理在自己的對話中執行，除非子代理是[分支](https://code.claude.com/docs/zh-TW/sub-agents.md#fork-the-current-conversation)，否則會從頭開始。無論哪種方式，中間工具呼叫和結果都保留在子代理內；只有其最終訊息返回到父代理。`research-assistant` 子代理可以探索數十個檔案，而不會有任何內容累積在主對話中。父代理會收到簡潔的摘要，而不是子代理讀取的每個檔案。請參閱[子代理繼承的內容](#what-subagents-inherit)以了解子代理上下文中的確切內容。
* **平行化**：多個子代理可以並行執行，因此獨立的子任務在最慢的時間內完成，而不是所有任務的總和。在程式碼審查期間，您可以同時執行 `style-checker`、`security-scanner` 和 `test-coverage` 子代理，而不是依序執行。
* **專門的指示和知識**：每個子代理可以有量身訂製的系統提示，具有特定的專業知識、最佳實踐和限制。`database-migration` 子代理可以具有有關 SQL 最佳實踐、回滾策略和資料完整性檢查的詳細知識，這些在主代理的指示中將是不必要的雜訊。
* **工具限制**：子代理可以限制為特定工具，降低意外操作的風險。`doc-reviewer` 子代理可能只能存取 Read 和 Grep 工具，確保它可以分析但永遠不會意外修改您的文件檔案。

## 建立子代理

### 程式化定義（推薦）

使用 `agents` 參數直接在程式碼中定義子代理。Claude 透過 `Agent` 工具叫用子代理。

本頁面上的大多數範例只會列印最終結果。若要確認 Claude 已委派給子代理而非直接回答，請參閱[偵測子代理叫用](#detect-subagent-invocation)。

此範例建立兩個子代理：一個具有唯讀存取權限的程式碼審查員，以及一個可以執行命令的測試執行器。

```python Python theme={null}
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition


async def main():
    async for message in query(
        prompt="Review the authentication module for security issues",
        options=ClaudeAgentOptions(
            # Auto-approve these tools
            allowed_tools=["Read", "Grep", "Glob", "Agent"],
            agents={
                "code-reviewer": AgentDefinition(
                    # description tells Claude when to use this subagent
                    description="Expert code review specialist. Use for quality, security, and maintainability reviews.",
                    # prompt defines the subagent's behavior and expertise
                    prompt="""You are a code review specialist with expertise in security, performance, and best practices.

When reviewing code:
- Identify security vulnerabilities
- Check for performance issues
- Verify adherence to coding standards
- Suggest specific improvements

Be thorough but concise in your feedback.""",
                    # tools restricts what the subagent can do (read-only here)
                    tools=["Read", "Grep", "Glob"],
                    # model overrides the default model for this subagent
                    model="sonnet",
                ),
                "test-runner": AgentDefinition(
                    description="Runs and analyzes test suites. Use for test execution and coverage analysis.",
                    prompt="""You are a test execution specialist. Run tests and provide clear analysis of results.

Focus on:
- Running test commands
- Analyzing test output
- Identifying failing tests
- Suggesting fixes for failures""",
                    # Bash access lets this subagent run test commands
                    tools=["Bash", "Read", "Grep"],
                ),
            },
        ),
    ):
        if hasattr(message, "result"):
            print(message.result)


asyncio.run(main())
```

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  prompt: "Review the authentication module for security issues",
  options: {
    // Auto-approve these tools
    allowedTools: ["Read", "Grep", "Glob", "Agent"],
    agents: {
      "code-reviewer": {
        // description tells Claude when to use this subagent
        description:
          "Expert code review specialist. Use for quality, security, and maintainability reviews.",
        // prompt defines the subagent's behavior and expertise
        prompt: `You are a code review specialist with expertise in security, performance, and best practices.

When reviewing code:
- Identify security vulnerabilities
- Check for performance issues
- Verify adherence to coding standards
- Suggest specific improvements

Be thorough but concise in your feedback.`,
        // tools restricts what the subagent can do (read-only here)
        tools: ["Read", "Grep", "Glob"],
        // model overrides the default model for this subagent
        model: "sonnet"
      },
      "test-runner": {
        description:
          "Runs and analyzes test suites. Use for test execution and coverage analysis.",
        prompt: `You are a test execution specialist. Run tests and provide clear analysis of results.

Focus on:
- Running test commands
- Analyzing test output
- Identifying failing tests
- Suggesting fixes for failures`,
        // Bash access lets this subagent run test commands
        tools: ["Bash", "Read", "Grep"]
      }
    }
  }
})) {
  if ("result" in message) console.log(message.result);
}
```

### AgentDefinition 設定

| 欄位 | 類型 | 必需 | 說明 |
| :- | :- | :- | :- |
| `description` | `string` | 是 | 何時使用此代理的自然語言說明 |
| `prompt` | `string` | 是 | 代理的系統提示，定義其角色和行為 |
| `tools` | `string[]` | 否 | 允許的工具名稱陣列。如果省略，會繼承[子代理可用的每個工具](https://code.claude.com/docs/zh-TW/sub-agents.md#available-tools) |
| `disallowedTools` | `string[]` | 否 | 要從代理工具集中移除的工具名稱陣列。也接受 MCP 伺服器層級的模式：`mcp__server` 或 `mcp__server__*` 會移除該伺服器的每個工具，而 `mcp__*` 會移除任何伺服器的每個 MCP 工具 |
| `model` | `string` | 否 | 此代理的模型覆寫。接受別名，例如 `'fable'`、`'opus'`、`'sonnet'`、`'haiku'`、`'inherit'`，或完整的模型 ID。`'inherit'` 使用主要模型。當您省略它時，Claude Code 會選擇[子代理模型順序](https://code.claude.com/docs/zh-TW/sub-agents.md#choose-a-model)中的模型 |
| `skills` | `string[]` | 否 | 在啟動時預先載入 agent 上下文的 skill 名稱清單。清單中最多只會預先載入[前 32 個不重複的名稱](https://code.claude.com/docs/zh-TW/sub-agents.md#preload-skills-into-subagents)。未列出的 skill 仍可透過 Skill 工具叫用 |
| `memory` | `'user' \| 'project' \| 'local'` | 否 | 此代理的記憶來源 |
| `mcpServers` | `(string \| object)[]` | 否 | 此代理可用的 MCP 伺服器，按名稱或內嵌設定 |
| `initialPrompt` | `string` | 否 | 當此代理作為主執行緒代理執行時，自動提交為第一個使用者回合。當代理作為子代理叫用時忽略 |
| `maxTurns` | `number` | 否 | 代理停止前的最大代理回合數。當代理達到限制時，Claude Code 會傳回標記為部分的輸出，您可以[繼續代理](#resume-subagents)以繼續。部分標記需要 Claude Code v2.1.246 或更新版本 |
| `autoCompactWindow` | `number` | 否 | 當此 agent 作為 subagent 執行時，將其[自動壓縮視窗](https://code.claude.com/docs/zh-TW/sub-agents.md#subagent-auto-compact-window)降低至 `100000` 到 `1000000` 之間的 token 數。需要 TypeScript Agent SDK v0.3.296 或更新版本。Python SDK 的 [`AgentDefinition`](https://code.claude.com/docs/zh-TW/agent-sdk/python#agentdefinition) 沒有此欄位 |
| `background` | `boolean` | 否 | 叫用時以非阻塞背景工作執行此代理 |
| `omitClaudeMd` | `boolean` | 否 | 將使用者、專案和本機 CLAUDE.md 檔案排除在此 agent 的初始上下文之外；受管理的原則檔案仍會載入。當 agent 作為主執行緒 agent 執行時忽略。需要 TypeScript Agent SDK v0.3.271 或更新版本。Python SDK 的 [`AgentDefinition`](https://code.claude.com/docs/zh-TW/agent-sdk/python#agentdefinition) 沒有此欄位 |
| `effort` | `'low' \| 'medium' \| 'high' \| 'xhigh' \| 'max' \| number` | 否 | 此代理的推理工作量等級 |
| `permissionMode` | `PermissionMode` | 否 | 此代理內工具執行的權限模式。[子代理繼承規則](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#available-modes)決定何時適用 |

在 Python SDK 中，多字欄位名稱（例如 `disallowedTools` 和 `mcpServers`）保持其 camelCase 拼寫以符合線路格式，而不是遵循 Python 的 snake\_case 慣例。如需詳細資訊，請參閱[`AgentDefinition` 參考](https://code.claude.com/docs/zh-TW/agent-sdk/python#agentdefinition)。

#### 選擇 Claude 是否等待 subagent

根據預設，主要 agent 產生的 subagent 會[在背景執行](https://code.claude.com/docs/zh-TW/sub-agents.md#run-subagents-in-foreground-or-background)。Agent 工具結果會帶有 `status: "async_launched"`，而報告會在稍後的回合送達。

當 Claude 的下一個動作需要該報告時，Claude 會等待：呼叫會阻塞並傳回 `status: "completed"`。若要自行做出此選擇：

* **在提示詞中**：要求 Claude 等待，例如「執行 test-runner agent 並等待它完成」
* **在定義中**：將 `background` 設定為 `true`，讓該 agent 保持在背景執行

### 檔案系統型定義（替代方案）

您也可以在 `.claude/agents/` 目錄中將子代理定義為 markdown 檔案。如需此方法的詳細資訊，請參閱 [Claude Code 子代理文件](https://code.claude.com/docs/zh-TW/sub-agents.md)。程式化定義的代理優先於具有相同名稱的檔案系統型代理。

> [!NOTE]
>
> 當 Claude 呼叫不含 `subagent_type` 的 Agent 工具時，它會取得內建的 `general-purpose` 子代理，即使您未定義任何自己的代理，Claude 也可以產生。設定 [`CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS=1`](https://code.claude.com/docs/zh-TW/env-vars) 會移除該預設值，而此類呼叫會失敗並顯示 [`subagent_type is required`](https://code.claude.com/docs/zh-TW/errors#subagent-type-is-required)。

## 子代理繼承的內容

除非子代理是[分支](https://code.claude.com/docs/zh-TW/sub-agents.md#fork-the-current-conversation)，否則其上下文視窗會重新開始，沒有父對話，但也不是空的。您從父代理傳遞到子代理的唯一內容是 Agent 工具的提示字串，因此請直接在該提示中包含子代理需要的任何檔案路徑、錯誤訊息或決策。

具有 [`SendMessage`](https://code.claude.com/docs/zh-TW/tools-reference) 工具的子代理會以工作階段中執行的其他具名代理清單開始，因此它知道可以向哪些名稱傳送訊息。Claude Code 會在子代理的第一個回合自動將清單新增到子代理。[分支](https://code.claude.com/docs/zh-TW/sub-agents.md#fork-the-current-conversation)不會取得清單，因為它繼承的是父對話。

子代理也會繼承主工作階段的擴展思考設定。

下表列出非分支子代理的上下文包含的內容以及它遺漏的內容。

| 子代理接收 | 子代理不接收 |
| :- | :- |
| 其自身的系統提示 (`AgentDefinition.prompt`) 和 Agent 工具的提示 | 父代理的對話歷史或工具結果 |
| 專案 CLAUDE.md（透過 [`settingSources`](https://code.claude.com/docs/zh-TW/agent-sdk/claude-code-features#control-filesystem-settings-with-settingsources) 載入）。設定 [`omitClaudeMd`](#agentdefinition-configuration) 的 agent 在開始時不會包含它 | 預載入的 skill 內容，除非列在 `AgentDefinition.skills` 中 |
| 工具定義（繼承自父代理或 `tools` 中的子集，[針對背景執行進行篩選](https://code.claude.com/docs/zh-TW/sub-agents.md#available-tools)） | 父代理的系統提示 |

> [!NOTE]
>
> 父層會接收 subagent 的最終報告，但可能會在其自身回應中進行摘要。若要在面向使用者的回應中逐字保留 subagent 輸出，請在您傳遞給主 `query()` 呼叫的提示詞或 `systemPrompt` 選項中包含執行此操作的指示。
>
> 在 v2.1.210 及更新版本中，Claude Code [在父代理讀取最終訊息之前掃描它以尋找指示形狀的模式](https://code.claude.com/docs/zh-TW/sub-agents.md#subagent-output-scanning)。掃描以三種不同的方式處理三種模式：
>
> * **控制標籤模仿**：Claude Code 會中立化只有工具組發出的標籤，例如 `<system-reminder>` 區塊，就地進行。它在開始角括號後插入反斜線，不刪除任何內容。
> * **權限設定提及**：Claude Code 會保留對權限設定的參考，例如 `.claude/settings.json`、`bypassPermissions` 或 `--dangerously-skip-permissions`，如同撰寫的方式。
> * **回合標記**：以 `Human:` 或 `Assistant:` 開頭的行在冒號前取得反斜線，因此訊息無法模仿對話回合邊界。
>
> 對於控制標籤或權限設定匹配，Claude Code 會在前面加上 `[harness: ...]` 標記行，命名匹配的模式；回合標記匹配不會新增標記行。這些是掃描進行的唯一修改：它永遠不會移除或改寫子代理的文字。

結束子代理早期的 API 錯誤，例如速率限制，永遠不會作為其結果傳遞。請參閱[子代理中的 API 錯誤](https://code.claude.com/docs/zh-TW/sub-agents.md#api-errors-in-subagents)以了解前景和背景行為。

## 呼叫子代理

### 自動呼叫

Claude 會根據任務和每個子代理的 `description` 自動決定何時呼叫子代理。例如，如果您定義了一個 `performance-optimizer` 子代理，其描述為「查詢調整的效能最佳化專家」，當您的提示詞提到最佳化查詢時，Claude 將呼叫它。

撰寫清晰、具體的描述，以便 Claude 能將任務與正確的子代理相匹配。

### 明確呼叫

若要保證 Claude 使用特定的子代理，請在您的提示詞中按名稱提及它：

```text theme={null}
"Use the code-reviewer agent to check the authentication module"
```

這會略過自動匹配，直接呼叫指定的子代理。

### 分叉的 subagent

[分叉（fork）](https://code.claude.com/docs/zh-TW/sub-agents.md#fork-the-current-conversation)是一種會複製目前為止對話內容、而非從頭開始的 subagent。從 Claude Code v2.1.302 起，Claude 可以在您的應用程式中啟動分叉，無需任何設定，方法是以 `subagent_type: "fork"` 呼叫 Agent 工具。

若要阻止 Claude 啟動分叉，請新增 [`Agent(fork)` 拒絕規則](https://code.claude.com/docs/zh-TW/agent-sdk/permissions#allow-and-deny-rules)：

```python Python theme={null}
options = ClaudeAgentOptions(
    # Deny only the fork subagent type; other subagents still run
    disallowed_tools=["Agent(fork)"],
)
```

```typescript TypeScript theme={null}
const options = {
  // Deny only the fork subagent type; other subagents still run
  disallowedTools: ["Agent(fork)"]
};
```

### 動態代理設定

您可以根據執行時條件動態建立代理定義。此範例建立了一個安全審查者，具有不同的嚴格程度，對於嚴格審查使用更強大的模型。

```python Python theme={null}
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition


# Factory function that returns an AgentDefinition
# This pattern lets you customize agents based on runtime conditions
def create_security_agent(security_level: str) -> AgentDefinition:
    is_strict = security_level == "strict"
    return AgentDefinition(
        description="Security code reviewer",
        # Customize the prompt based on strictness level
        prompt=f"You are a {'strict' if is_strict else 'balanced'} security reviewer...",
        tools=["Read", "Grep", "Glob"],
        # Key insight: use a more capable model for high-stakes reviews
        model="opus" if is_strict else "sonnet",
    )


async def main():
    # The agent is created at query time, so each request can use different settings
    async for message in query(
        prompt="Review this PR for security issues",
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Grep", "Glob", "Agent"],
            agents={
                # Call the factory with your desired configuration
                "security-reviewer": create_security_agent("strict")
            },
        ),
    ):
        if hasattr(message, "result"):
            print(message.result)


asyncio.run(main())
```

```typescript TypeScript theme={null}
import { query, type AgentDefinition } from "@anthropic-ai/claude-agent-sdk";

// Factory function that returns an AgentDefinition
// This pattern lets you customize agents based on runtime conditions
function createSecurityAgent(securityLevel: "basic" | "strict"): AgentDefinition {
  const isStrict = securityLevel === "strict";
  return {
    description: "Security code reviewer",
    // Customize the prompt based on strictness level
    prompt: `You are a ${isStrict ? "strict" : "balanced"} security reviewer...`,
    tools: ["Read", "Grep", "Glob"],
    // Key insight: use a more capable model for high-stakes reviews
    model: isStrict ? "opus" : "sonnet"
  };
}

// The agent is created at query time, so each request can use different settings
for await (const message of query({
  prompt: "Review this PR for security issues",
  options: {
    allowedTools: ["Read", "Grep", "Glob", "Agent"],
    agents: {
      // Call the factory with your desired configuration
      "security-reviewer": createSecurityAgent("strict")
    }
  }
})) {
  if ("result" in message) console.log(message.result);
}
```

## 偵測子代理程式叫用

Claude 透過 Agent 工具叫用 subagent。若要偵測何時叫用 subagent，請檢查 `tool_use` 區塊，其中 `name` 為 `"Agent"`。

來自 subagent 內容中的訊息包含 `parent_tool_use_id` 欄位。在 TypeScript 中，subagent 產生的每則助理訊息和使用者訊息也帶有 [`agent_id`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#sdkassistantmessage)：即該 subagent 之[任務事件](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md#sdktaskstartedmessage)的 `task_id`。當您[恢復 subagent](#resume-subagents) 時，`agent_id` 會保持不變。`agent_id` 需要 TypeScript Agent SDK v0.3.292 或更新版本。

> [!NOTE]
>
> 該工具在 `tool_use` 區塊中顯示為 `"Agent"`，但在 `system:init` 工具清單中顯示為 `"Task"`。在 Claude Code v2.1.63 之前，`tool_use` 區塊也將其命名為 `"Task"`。為了保持偵測在各個 SDK 版本中正常運作，請在 `block.name` 中同時符合兩個值。

訊息結構在 SDK 之間有所不同。在 Python 中，您可以透過 `message.content` 直接存取內容區塊。在 TypeScript 中，`SDKAssistantMessage` 包裝 Claude API 訊息，因此您透過 `message.message.content` 存取內容。

此範例會逐一查看串流訊息，在叫用 subagent 時以及後續訊息源自該 subagent 執行內容時進行記錄。TypeScript 版本也會記錄每則帶有 `agent_id` 的 subagent 訊息之 `agent_id`。

```python Python theme={null}
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition, ToolUseBlock


async def main():
    async for message in query(
        prompt="Use the code-reviewer agent to review this codebase",
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Glob", "Grep", "Agent"],
            agents={
                "code-reviewer": AgentDefinition(
                    description="Expert code reviewer.",
                    prompt="Analyze code quality and suggest improvements.",
                    tools=["Read", "Glob", "Grep"],
                )
            },
        ),
    ):
        # Check for subagent invocation. Match both names: older SDK
        # versions emitted "Task", current versions emit "Agent".
        if hasattr(message, "content") and message.content:
            for block in message.content:
                if isinstance(block, ToolUseBlock) and block.name in (
                    "Task",
                    "Agent",
                ):
                    print(f"Subagent invoked: {block.input.get('subagent_type')}")

        # Check if this message is from within a subagent's context
        if hasattr(message, "parent_tool_use_id") and message.parent_tool_use_id:
            print("  (running inside subagent)")

        if hasattr(message, "result"):
            print(message.result)


asyncio.run(main())
```

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  prompt: "Use the code-reviewer agent to review this codebase",
  options: {
    allowedTools: ["Read", "Glob", "Grep", "Agent"],
    agents: {
      "code-reviewer": {
        description: "Expert code reviewer.",
        prompt: "Analyze code quality and suggest improvements.",
        tools: ["Read", "Glob", "Grep"]
      }
    }
  }
})) {
  const msg = message as any;

  // Check for subagent invocation. Match both names: older SDK versions
  // emitted "Task", current versions emit "Agent".
  for (const block of msg.message?.content ?? []) {
    if (block.type === "tool_use" && (block.name === "Task" || block.name === "Agent")) {
      console.log(`Subagent invoked: ${block.input.subagent_type}`);
    }
  }

  // Check if this message is from within a subagent's context
  if (msg.parent_tool_use_id) {
    console.log("  (running inside subagent)");
    // On assistant and user messages, agent_id matches the task_id
    // on that subagent's task_started and other task events
    if (msg.agent_id) {
      console.log(`  agent_id: ${msg.agent_id}`);
    }
  }

  if ("result" in message) {
    console.log(message.result);
  }
}
```

## 繼續執行子代理

您可以繼續執行子代理以從中斷處繼續，而不是重新開始。繼續執行的子代理會保留其完整的對話歷史記錄，包括所有先前的工具呼叫、結果和推理。

當子代理在其 [`maxTurns`](#agentdefinition-configuration) 限制處停止時，Claude Code 會在 Agent 工具結果中將輸出標記為部分，以便 Claude 知道執行未完成。

當子代理完成時，Agent 工具結果包含一個包含 `agentId: <id>` 的文字區塊。內建的 [`Explore` 和 `Plan` 代理](https://code.claude.com/docs/zh-TW/sub-agents#built-in-subagents) 是一次性的，不會傳回 `agentId`，因此當您需要繼續執行時，請使用自訂代理或 `general-purpose`。若要以程式設計方式繼續執行子代理：

1. **擷取工作階段 ID**：從第一個查詢期間的訊息中提取 `session_id`
2. **提取代理 ID**：從 Agent 工具結果文字中解析 `agentId`
3. **繼續執行工作階段**：在第二個查詢的選項中傳遞 `resume: sessionId`，並在您的提示中包含代理 ID。每個 `query()` 呼叫預設會啟動新的工作階段，您必須繼續執行相同的工作階段以存取子代理的文字記錄。

> [!NOTE]
>
> 使用自訂代理時，在兩個查詢的 `agents` 參數中傳遞相同的代理定義。

下面的範例定義了一個自訂的 `endpoint-finder` 代理。第一個查詢執行它並從 Agent 工具結果中擷取工作階段 ID 和代理 ID，然後第二個查詢繼續執行工作階段以提出需要第一次分析內容的後續問題。

```python Python theme={null}
import asyncio
import re
from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition, ToolResultBlock

AGENTS = {
    "endpoint-finder": AgentDefinition(
        description="Locates and catalogs API endpoints in a codebase.",
        prompt="You find and document API endpoints. Report each endpoint's path, method, and handler.",
        tools=["Read", "Grep", "Glob"],
    )
}


def extract_agent_id(block: ToolResultBlock) -> str | None:
    """Extract agentId from an Agent tool result's text content."""
    parts = block.content if isinstance(block.content, list) else [{"text": block.content}]
    for part in parts:
        if match := re.search(r"agentId:\s*([\w-]+)", part.get("text") or ""):
            return match.group(1)
    return None


async def main():
    agent_id = None
    session_id = None

    # First invocation - run the endpoint-finder subagent
    try:
        async for message in query(
            prompt="Use the endpoint-finder agent to find all API endpoints in this codebase",
            options=ClaudeAgentOptions(allowed_tools=["Read", "Grep", "Glob", "Agent"], agents=AGENTS),
        ):
            # Capture session_id from ResultMessage (needed to resume this session)
            if hasattr(message, "session_id"):
                session_id = message.session_id
            # Search tool results for the agentId trailer
            for block in getattr(message, "content", None) or []:
                if isinstance(block, ToolResultBlock):
                    agent_id = extract_agent_id(block) or agent_id
            # Print the final result
            if hasattr(message, "result"):
                print(message.result)
    except Exception as error:
        # A single-shot query() raises after yielding an error result,
        # so session_id and agent_id have already been captured by the loop above.
        print(f"Session ended with an error: {error}")

    # Second invocation - resume and ask follow-up
    if agent_id and session_id:
        async for message in query(
            prompt=f"Resume agent {agent_id} and list the top 3 most complex endpoints",
            options=ClaudeAgentOptions(
                allowed_tools=["Read", "Grep", "Glob", "Agent"], agents=AGENTS, resume=session_id
            ),
        ):
            if hasattr(message, "result"):
                print(message.result)
    else:
        print("No agentId found in the first query, so there is no subagent to resume.")


asyncio.run(main())
```

```typescript TypeScript theme={null}
import { query, type SDKMessage } from "@anthropic-ai/claude-agent-sdk";

const agents = {
  "endpoint-finder": {
    description: "Locates and catalogs API endpoints in a codebase.",
    prompt: "You find and document API endpoints. Report each endpoint's path, method, and handler.",
    tools: ["Read", "Grep", "Glob"]
  }
};

// Stringify content to search for agentId without traversing nested block types
function extractAgentId(message: SDKMessage): string | undefined {
  if (message.type !== "assistant" && message.type !== "user") return undefined;
  const content = JSON.stringify(message.message.content);
  const match = content.match(/agentId:\s*([\w-]+)/);
  return match?.[1];
}

let agentId: string | undefined;
let sessionId: string | undefined;

// First invocation - run the endpoint-finder subagent
try {
  for await (const message of query({
    prompt: "Use the endpoint-finder agent to find all API endpoints in this codebase",
    options: { allowedTools: ["Read", "Grep", "Glob", "Agent"], agents }
  })) {
    // Capture session_id from ResultMessage (needed to resume this session)
    if ("session_id" in message) sessionId = message.session_id;
    // Search message content for the agentId (appears in Agent tool results)
    const extractedId = extractAgentId(message);
    if (extractedId) agentId = extractedId;
    // Print the final result
    if ("result" in message) console.log(message.result);
  }
} catch (error) {
  // A single-shot query() throws after yielding an error result,
  // so sessionId and agentId have already been captured by the loop above.
  console.error(`Session ended with an error: ${error}`);
}

// Second invocation - resume and ask follow-up
if (agentId && sessionId) {
  for await (const message of query({
    prompt: `Resume agent ${agentId} and list the top 3 most complex endpoints`,
    options: { allowedTools: ["Read", "Grep", "Glob", "Agent"], agents, resume: sessionId }
  })) {
    if ("result" in message) console.log(message.result);
  }
} else {
  console.log("No agentId found in the first query, so there is no subagent to resume.");
}
```

子代理文字記錄儲存在單獨的檔案中，並獨立於主對話之外持續存在。請參閱 [Claude Code 中的繼續執行子代理](https://code.claude.com/docs/zh-TW/sub-agents.md#resume-subagents) 以了解壓縮行為和 `cleanupPeriodDays` 清理期間。

## 工具限制

使用 `tools` 欄位來限制子代理可以執行的操作：

* **省略 `tools`**：子代理會獲得[所有可用於子代理的工具](https://code.claude.com/docs/zh-TW/sub-agents.md#available-tools)
* **列出工具**：子代理只會獲得這些工具。例如，不應編輯檔案的程式碼審查員會獲得 `["Read", "Grep", "Glob"]`

您省略的工具根本不會出現在子代理的工作階段中：Claude 會在沒有該工具的情況下工作，不會出現權限提示或錯誤。

此範例建立了一個唯讀分析代理，可以檢查程式碼但無法修改檔案或執行命令。

```python Python theme={null}
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition


async def main():
    async for message in query(
        prompt="Analyze the architecture of this codebase",
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Grep", "Glob", "Agent"],
            agents={
                "code-analyzer": AgentDefinition(
                    description="Static code analysis and architecture review",
                    prompt="""You are a code architecture analyst. Analyze code structure,
identify patterns, and suggest improvements without making changes.""",
                    # Read-only tools: no Edit, Write, or Bash access
                    tools=["Read", "Grep", "Glob"],
                )
            },
        ),
    ):
        if hasattr(message, "result"):
            print(message.result)


asyncio.run(main())
```

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  prompt: "Analyze the architecture of this codebase",
  options: {
    allowedTools: ["Read", "Grep", "Glob", "Agent"],
    agents: {
      "code-analyzer": {
        description: "Static code analysis and architecture review",
        prompt: `You are a code architecture analyst. Analyze code structure,
identify patterns, and suggest improvements without making changes.`,
        // Read-only tools: no Edit, Write, or Bash access
        tools: ["Read", "Grep", "Glob"]
      }
    }
  }
})) {
  if ("result" in message) console.log(message.result);
}
```

### 常見工具組合

| 使用案例 | 工具 | 說明 |
| :- | :- | :- |
| 唯讀分析 | `Read`、`Grep`、`Glob` | 可以檢查程式碼但無法修改或執行 |
| 測試執行 | `Bash`、`Read`、`Grep` | 可以執行命令並分析輸出 |
| 程式碼修改 | `Read`、`Edit`、`Write`、`Grep`、`Glob` | 完整的讀寫存取權限，無命令執行 |
| 完整存取 | 所有工具 | 繼承可用於子代理的工具（省略 `tools` 欄位） |

## 限制子代理的深度、並行性和支出

> [!NOTE]
>
> 本節描述 TypeScript SDK v0.3.219 和 Python SDK v0.2.127 及更新版本，這些版本包含 Claude Code v2.1.219 或更新版本。在較早的版本中，某些限制可能缺失或預設值不同，因此在依賴它們來限制執行之前，請先升級。[環境變數參考](https://code.claude.com/docs/zh-TW/env-vars.md)和[輪次和預算](https://code.claude.com/docs/zh-TW/agent-sdk/agent-loop.md#turns-and-budget)記錄了添加每個變數的 Claude Code 版本以及支出上限的子代理強制執行。

Claude 會自行決定何時生成子代理以及生成多少個子代理。每個子代理都會發出自己的 API 請求，這些請求計入查詢的 `total_cost_usd`，而子代理可以生成自己的子代理，因此一個提示可以發展成代理樹。

您可以通過三種方式限制這種增長：子代理的嵌套深度、同時運行的數量以及整個查詢的支出。通過 [`env`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#options) 選項將深度和並行性限制設定為環境變數，並將支出限制設定為查詢選項：

| 限制 | 設定方式 | 預設值 | Claude Code 在達到限制時的行為 |
| :- | :- | :- | :- |
| 深度 | [`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`](https://code.claude.com/docs/zh-TW/env-vars) | 主代理下方的 `3` 層子代理。`1` 會阻止您的子代理生成任何自己的子代理 | 使底層的子代理無法生成，因此它會自己完成委派的工作。請參閱[嵌套子代理](https://code.claude.com/docs/zh-TW/sub-agents.md#let-subagents-spawn-their-own-subagents) |
| 並行性 | [`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`](https://code.claude.com/docs/zh-TW/env-vars) | `20` 個子代理同時運行，計算 Claude 使用 Agent 工具生成的每個子代理 | 拒絕生成另一個子代理，返回 `Concurrent subagent limit reached`，直到運行計數降至限制以下。啟用[超級代碼](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)的工作階段永遠不會被拒絕。請參閱[並行子代理限制](https://code.claude.com/docs/zh-TW/sub-agents.md#concurrent-subagent-limit) |
| 支出 | TypeScript 中的 `maxBudgetUsd`，Python 中的 `max_budget_usd` | 無限制。計算呼叫自身的支出，包括子代理請求 | 通過三種方式強制執行上限：拒絕生成更多子代理，返回 `Budget limit reached`，停止仍在運行的背景子代理，並以 `error_max_budget_usd` 結果子類型結束查詢。如需了解上限在工作階段中的行為方式，請參閱[輪次和預算](https://code.claude.com/docs/zh-TW/agent-sdk/agent-loop.md#turns-and-budget) |

兩個 SDK 對 `env` 選項的處理方式不同：TypeScript SDK 用它替換子程序環境，因此將 `process.env` 展開到其中以保留 `PATH` 等變數，而 Python SDK 將其合併到繼承的環境中。此範例關閉嵌套，最多允許五個子代理同時運行，並在估計支出達到 \$5 時停止查詢：

```python Python theme={null}
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage


async def main():
    try:
        async for message in query(
            prompt="Audit every service in this repo for unhandled promise rejections",
            options=ClaudeAgentOptions(
                allowed_tools=["Read", "Grep", "Glob", "Agent"],
                # env is merged on top of the inherited environment
                env={
                    "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "1",
                    "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "5",
                },
                max_budget_usd=5.0,
            ),
        ):
            if isinstance(message, ResultMessage):
                print(f"{message.subtype}: ${message.total_cost_usd}")
    except Exception as error:
        # A single-shot query() raises after yielding an error result,
        # so the budget-capped result has already been printed above.
        print(f"Session ended with an error: {error}")


asyncio.run(main())
```

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

try {
  for await (const message of query({
    prompt: "Audit every service in this repo for unhandled promise rejections",
    options: {
      allowedTools: ["Read", "Grep", "Glob", "Agent"],
      // env replaces the subprocess environment, so spread process.env to keep PATH
      env: {
        ...process.env,
        CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH: "1",
        CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS: "5",
      },
      maxBudgetUsd: 5,
    },
  })) {
    if (message.type === "result") {
      console.log(`${message.subtype}: $${message.total_cost_usd}`);
    }
  }
} catch (error) {
  // A single-shot query() throws after yielding an error result,
  // so the budget-capped result has already been logged above.
  console.error(`Session ended with an error: ${error}`);
}
```

您看到的內容取決於查詢達到的限制（如果有的話）：

* **在支出上限以下**：您會看到 `success` 和估計成本。
* **達到支出上限**：您會看到 `error_max_budget_usd`，成本為 `5` 或以上，然後您的錯誤處理程式會運行。
* **達到並行性限制**：您會在訊息流中看到一個 `tool_result` 區塊，其中包含 `Concurrent subagent limit reached`。Claude 會收到與 Agent 工具結果相同的區塊。

### 使用子代理執行 Opus 5

Claude Opus 5 比早期模型更容易委派給子代理，因此[深度、並行性和支出限制](#cap-subagent-depth-concurrency-and-spend)在執行 Opus 5 的查詢中最為重要。[Opus 5 提示指南](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5#controlling-subagent-spawning)提供了一個委派指令，您可以將其添加到任何提示中。Claude Code 是否添加自己的指令取決於您使用的[系統提示](https://code.claude.com/docs/zh-TW/agent-sdk/modifying-system-prompts.md#how-system-prompts-work)：

* **`claude_code` 預設值**：當模型是 Opus 5 時，Claude Code 會在其系統提示中添加一行，告訴 Claude 除非被要求，否則不要呼叫 Agent 工具。Agent 工具保持可用。
* **自訂提示或無 `systemPrompt`**：Claude Code 不會建立其系統提示，因此該行不存在。將提示指南的委派指令添加到您自己的提示中。

任一指令只會引導 Claude，因此也要設定限制。Claude Code 會根據 Claude 決定的委派方式強制執行它們。

## 使用動態工作流程進行擴展

子代理適用於每轉委派幾個任務。對於協調數十到數百個代理的運行，請使用 `Workflow` 工具，它將編排移到運行時在對話上下文外執行的腳本中。請參閱[動態工作流程](https://code.claude.com/docs/zh-TW/workflows.md)以了解工作流程與逐轉子代理委派的區別。

`Workflow` 工具在 TypeScript Agent SDK v0.3.149 及更高版本中可用。在 `allowedTools` 中包含 `Workflow` 以自動批准工作流程運行。工具輸入和輸出架構列在 [TypeScript 參考](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md#workflow)中。

## 故障排除

### Claude 不委派給子代理

如果 Claude 直接完成任務而不是委派給您的子代理：

* **使用明確提示**：在您的提示詞中按名稱提及子代理，例如「使用代碼審查員代理來檢查身份驗證模組」
* **編寫清晰的描述**：準確解釋何時應使用子代理，以便 Claude 可以適當地匹配任務

### 基於檔案系統的代理未加載

Claude Code 監視 `~/.claude/agents/` 和 `.claude/agents/`，並在幾秒內拾取新的或編輯的代理檔案，無需重新啟動。如果定義從未出現，請檢查這些原因：

* **新的 `agents` 目錄**：監視程式僅涵蓋會話啟動時存在的目錄，因此新目錄中的第一個檔案需要會話重新啟動。這是最常見的原因。
* **無效的 frontmatter 或重複的 `name`**：檢查檔案的 YAML，以及現有代理是否已使用該 `name`。
* **`--disable-slash-commands`**：使用此旗標啟動的會話不監視這些目錄，並且始終需要重新啟動以加載新檔案。
* **已新增目錄下的檔案**：Claude Code 從使用 `add_dirs` (Python) 或 `additionalDirectories` (TypeScript) 選項或 CLI 的 `--add-dir` 或 `/add-dir` 新增的目錄中加載 `.claude/agents/`，但不監視它們，因此那裡的新檔案或編輯檔案需要會話重新啟動。
* **具有相同名稱的程式化代理**：傳遞給 `query()` 的 `agents` 會覆蓋具有相同名稱的檔案系統代理。

有關檔案格式，請參閱[如何編寫子代理檔案](https://code.claude.com/docs/zh-TW/sub-agents.md#write-subagent-files)。

## 相關文件

* [Claude Code subagent](https://code.claude.com/docs/zh-TW/sub-agents.md)：subagent 文件，包括基於檔案系統的定義
* [動態工作流程](https://code.claude.com/docs/zh-TW/workflows.md)：從指令碼協調許多子代理，用於超出單一對話範圍的大型工作
* [SDK 概述](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md)：開始使用 Claude Agent SDK

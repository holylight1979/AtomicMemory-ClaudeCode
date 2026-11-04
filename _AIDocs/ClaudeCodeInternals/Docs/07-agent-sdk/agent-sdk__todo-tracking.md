<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/agent-sdk/todo-tracking | lastmod: 2026-10-20 | section: Agent SDK / Control and observability -->
> 來源：https://code.claude.com/docs/zh-TW/agent-sdk/todo-tracking（官方 zh-TW，lastmod 2026-10-20）｜分類：Agent SDK › Control and observability｜EN 摘要：Track todos in Agent SDK sessions and render Claude's progress in your application from structured tool calls

# 追蹤待辦事項

> 在 Agent SDK 工作階段中追蹤待辦事項，並從結構化工具呼叫在應用程式中呈現 Claude 的進度

Claude Code 預設只在[模型可用性](#model-availability)下列出的模型上提供[任務追蹤工具](https://code.claude.com/docs/zh-TW/tools-reference.md#task-tool-availability)。較新的模型可以在沒有書面待辦事項清單的情況下追蹤多步驟工作，因此在這些模型上，您不需要本頁面上的任何內容，Claude 就能完成多步驟任務。

在具有任務追蹤工具的工作階段中，Claude 保持書面待辦事項清單，在工作時更新每個項目的狀態。您在訊息流中看到每個變更都是結構化工具呼叫。僅當您的應用程式讀取這些工具呼叫時才選擇加入工作階段，無論是記錄任務活動還是呈現自己的進度顯示。

## 模型可用性

> [!NOTE]
>
> 下列工具預設僅在 Claude Opus 4.7、Claude Sonnet 4.6、Claude Haiku 4.5 及更早的模型上可用。在所有其他模型上（包括 Claude Code 無法識別的模型 ID），除非您選擇加入，否則這些工具無法使用：
>
> * `TodoWrite`
> * `TaskCreate`
> * `TaskGet`
> * `TaskUpdate`
> * `TaskList`
>
> 只要工具可用，Claude Code 就會提供四個 Task 工具，或者當您設定 `CLAUDE_CODE_ENABLE_TASKS=0` 時改為提供 `TodoWrite`。
>
> 此預設集合適用於 Claude Code v2.1.268 及更新版本，TypeScript Agent SDK 從 v0.3.268 開始包含此版本。

在預設情況下沒有工具的模型上，除非您選擇加入工作階段，否則您在訊息流中看不到這些工具的 `tool_use` 區塊。Agent SDK 通過它捆綁的 Claude Code 二進位檔案應用這些預設值。如果您將 `pathToClaudeCodeExecutable`（TypeScript）或 `cli_path`（Python）指向您自己的 Claude Code 安裝，您將獲得該安裝提供的任何工具，在其自己的預設值下。要查看執行中工作階段中的確切集合，請[檢查哪些工具可用](https://code.claude.com/docs/zh-TW/tools-reference.md#check-which-tools-are-available)。要選擇加入工作階段，請執行以下操作之一：

* 在 [`allowedTools`](https://code.claude.com/docs/zh-TW/agent-sdk/permissions#allow-and-deny-rules)（TypeScript）或 `allowed_tools`（Python）選項中命名其中一個工具
* 在 `tools` 選項中列出工具，這會將工作階段的內置工具限制為它命名的工具。將您想要的工具與您使用的其他內置工具一起包含
* 在 `env` 選項中設定 `CLAUDE_CODE_ENABLE_TODO_TOOLS=1`，如本頁面上的範例所做的那樣。在 TypeScript 中，`env` 替換子程序環境，因此展開 `...process.env` 以保留繼承的變數。在 Python 中，`env` 合併在繼承的環境之上

## 待辦事項生命週期

Claude 將每個待辦事項移動通過可預測的生命週期：

1. **建立**：Claude 在識別任務時將待辦事項新增為 `pending`
2. **啟動**：Claude 在開始工作時將待辦事項設定為 `in_progress`
3. **完成**：Claude 在任務成功完成時將其標記為已完成
4. **移除**：Claude 通過在 `TaskUpdate` 呼叫中設定 `status: "deleted"` 來刪除不再需要的待辦事項

## Claude 何時建立待辦事項

在[具有任務追蹤工具的工作階段](#model-availability)中，Claude 為大多數多步驟工作建立待辦事項，例如：

* **複雜的多步驟任務**需要三個或更多不同的操作
* **使用者提供的任務清單**當提及多個項目時
* **較長的操作**受益於進度追蹤
* **明確的請求**當使用者要求待辦事項組織時

Claude 可能會跳過非常短或單步驟請求的待辦事項。

## 範例

在執行這些範例之前，請按照[快速入門](https://code.claude.com/docs/zh-TW/agent-sdk/quickstart.md)安裝 Claude Agent SDK。本頁面上的每個範例都共享相同的權限設定和退出行為：

* **權限模式**：範例提示要求 Claude 在專案上執行實際工作，因此每個範例都設定 `permissionMode: "acceptEdits"`（TypeScript）或 `permission_mode="acceptEdits"`（Python）以自動批准工作產生的檔案編輯。請參閱[權限模式](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#permission-modes)以了解替代方案。
* **輪次限制**：每個範例執行到代理程式完成並產生其最終結果訊息為止。如果工作階段先達到其輪次限制，該結果訊息會有 `error_max_turns` 子類型。檢查 `subtype` 以偵測該結束。
* **錯誤處理**：這些範例使用單次 `query()` 呼叫。在產生 `error_max_turns` 結果後，`query()` 會拋出包含 `Reached maximum number of turns` 的錯誤。每個範例都將其迴圈包裝在 try 區塊中，以便在發生這種情況時乾淨地退出。請參閱[處理結果](https://code.claude.com/docs/zh-TW/agent-sdk/agent-loop.md#handle-the-result)以了解結果子類型。

> [!NOTE]
>
> 任務系統訊息，[`SDKTaskNotificationMessage`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#sdktasknotificationmessage)（TypeScript）或 [`TaskNotificationMessage`](https://code.claude.com/docs/zh-TW/agent-sdk/python#tasknotificationmessage)（Python）等，報告背景任務，例如背景命令和子代理程式。在訊息流中，您看到待辦事項活動作為助手訊息中的 `tool_use` 區塊。

### 監控待辦事項變更

以下範例監視助手流中的 `TaskCreate` 和 `TaskUpdate` `tool_use` 區塊，並列印一個 `+` 行，其中包含每個新任務的主題，以及一個更新行，其中包含每個狀態變更的任務 ID 和新狀態。當您想要任務活動的日誌而不是呈現的顯示時，請使用此形狀。`+` 行不包含指派的 ID，因此此日誌無法將更新與其建立相匹配。要保持該相關性，請如[即時顯示進度](#display-progress-in-real-time)所做的那樣捕獲 ID。

串流的 `tool_use` 輸入是模型發出的原始形狀。Claude Code 在執行前修復一些接近但不正確的鍵名，將 `id` 或 `task_id` 對應到 `taskId` 和 `active_form` 對應到 `activeForm`，但該修復不會反映在流中。防禦性地讀取 `TaskUpdate` 輸入欄位，如本頁面上的兩個範例所做的那樣，而不是假設規範名稱始終存在。

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

try {
  for await (const message of query({
    prompt: "Create a static website with a home page, an about page, and a shared stylesheet, and track progress with todos",
    // Keeps the Task tools on models where Claude Code otherwise doesn't provide them.
    options: { maxTurns: 15, permissionMode: "acceptEdits", env: { ...process.env, CLAUDE_CODE_ENABLE_TODO_TOOLS: "1" } },
  })) {
    if (message.type !== "assistant") continue;
    for (const block of message.message.content) {
      if (block.type !== "tool_use") continue;
      if (block.name === "TaskCreate") {
        const input = block.input as { subject: string };
        console.log(`+ ${input.subject}`);
      } else if (block.name === "TaskUpdate") {
        const input = block.input as {
          taskId?: string;
          id?: string;
          task_id?: string;
          status?: string;
        };
        const taskId = input.taskId ?? input.id ?? input.task_id;
        if (taskId && input.status) console.log(`  ${taskId} -> ${input.status}`);
      }
    }
  }
} catch (error) {
  // A single-shot query() throws after yielding an error result.
  console.log(`Session ended with an error: ${error}`);
}
```

```python Python theme={null}
import asyncio

from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ToolUseBlock

async def main():
    try:
        async for message in query(
            prompt="Create a static website with a home page, an about page, and a shared stylesheet, and track progress with todos",
            # Keeps the Task tools on models where Claude Code otherwise doesn't provide them.
            options=ClaudeAgentOptions(max_turns=15, permission_mode="acceptEdits", env={"CLAUDE_CODE_ENABLE_TODO_TOOLS": "1"}),
        ):
            if not isinstance(message, AssistantMessage):
                continue
            for block in message.content:
                if not isinstance(block, ToolUseBlock):
                    continue
                if block.name == "TaskCreate":
                    print(f"+ {block.input.get('subject', '')}")
                elif block.name == "TaskUpdate" and block.input.get("status"):
                    task_id = (
                        block.input.get("taskId")
                        or block.input.get("id")
                        or block.input.get("task_id")
                    )
                    if task_id:
                        print(f"  {task_id} -> {block.input['status']}")
    except Exception as error:
        # A single-shot query() raises after yielding an error result.
        print(f"Session ended with an error: {error}")


asyncio.run(main())
```

### 即時顯示進度

以下範例監視助手流中的 `TaskCreate` 和 `TaskUpdate` `tool_use` 區塊，並在 `TaskTracker` 類別中保持以任務 ID 為鍵的任務映射，在每次變更時重新呈現進度摘要。摘要計算已完成和進行中的任務，並顯示每個活動項目的 `activeForm` 標籤以代替其 `subject`。當您的應用程式維護進度顯示而不是記錄每個事件時，請使用此形狀。

指派的任務 ID 不在 `TaskCreate` 輸入中。Claude Code 在攜帶其 `tool_result` 區塊的使用者訊息上傳遞每個工具的結構化輸出，在 `tool_use_result` 欄位中。對於 `TaskCreate`，該物件在 TypeScript 中記錄為[工具輸出類型](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md#tool-output-types)下的 `TaskCreateOutput`，在 Python 中該欄位是相同形狀的純字典。追蹤器通過 `tool_use_id` 將每個 `tool_result` 區塊與其 `tool_use` 呼叫配對，並從配對訊息的 `tool_use_result` 讀取 `task.id`。Claude 可以使用 `TaskList` 讀回清單，使用 `TaskGet` 讀回一個任務的完整詳細資訊。

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

type Task = { subject: string; activeForm?: string; status: string };

class TaskTracker {
  private tasks = new Map<string, Task>();
  private pendingCreates = new Map<string, { subject: string; activeForm?: string }>();

  displayProgress() {
    if (this.tasks.size === 0) {
      console.log("\nProgress: no open tasks\n");
      return;
    }

    const items = [...this.tasks.values()];
    const completed = items.filter((t) => t.status === "completed").length;
    const inProgress = items.filter((t) => t.status === "in_progress").length;

    console.log(`\nProgress: ${completed}/${this.tasks.size} completed`);
    console.log(`Currently working on: ${inProgress} task(s)\n`);

    for (const [id, task] of this.tasks) {
      const icon =
        task.status === "completed" ? "✅" : task.status === "in_progress" ? "🔧" : "❌";
      const text = task.status === "in_progress" && task.activeForm ? task.activeForm : task.subject;
      console.log(`${id}. ${icon} ${text}`);
    }
  }

  handleToolUse(block: { id: string; name: string; input: unknown }) {
    if (block.name === "TaskCreate") {
      const input = block.input as { subject: string; activeForm?: string; active_form?: string };
      this.pendingCreates.set(block.id, {
        subject: input.subject,
        activeForm: input.activeForm ?? input.active_form,
      });
    } else if (block.name === "TaskUpdate") {
      const input = block.input as {
        taskId?: string;
        id?: string;
        task_id?: string;
        status?: string;
        activeForm?: string;
        active_form?: string;
      };
      const taskId = input.taskId ?? input.id ?? input.task_id;
      if (!taskId) return;
      if (input.status === "deleted") {
        this.tasks.delete(taskId);
        this.displayProgress();
        return;
      }
      const task = this.tasks.get(taskId);
      if (!task) return;
      if (input.status) task.status = input.status;
      const active = input.activeForm ?? input.active_form;
      if (active) task.activeForm = active;
      this.displayProgress();
    }
  }

  handleToolResult(block: { tool_use_id: string; is_error?: boolean }, result: unknown) {
    const create = this.pendingCreates.get(block.tool_use_id);
    if (!create) return;
    this.pendingCreates.delete(block.tool_use_id);
    if (block.is_error) return;
    // The result's user message carries the tool's structured output as
    // tool_use_result; for TaskCreate that's TaskCreateOutput,
    // { task: { id, subject } }.
    const out = result as { task?: { id: string } };
    if (!out?.task?.id) return;
    this.tasks.set(out.task.id, { ...create, status: "pending" });
    this.displayProgress();
  }

  async trackQuery(prompt: string) {
    try {
      for await (const message of query({
        prompt,
        options: { maxTurns: 20, permissionMode: "acceptEdits", env: { ...process.env, CLAUDE_CODE_ENABLE_TODO_TOOLS: "1" } },
      })) {
        if (message.type === "assistant") {
          for (const block of message.message.content) {
            if (block.type === "tool_use") this.handleToolUse(block);
          }
        }
        if (message.type === "user" && Array.isArray(message.message.content)) {
          for (const block of message.message.content) {
            if (block.type === "tool_result") this.handleToolResult(block, message.tool_use_result);
          }
        }
      }
    } catch (error) {
      // A single-shot query() throws after yielding an error result,
      // such as when the maxTurns limit is hit.
      console.log(`Session ended with an error: ${error}`);
    }
  }
}

// Usage
const tracker = new TaskTracker();
await tracker.trackQuery("Build a complete authentication system with todos");
```

```python Python theme={null}
import asyncio

from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AssistantMessage,
    UserMessage,
    ToolUseBlock,
    ToolResultBlock,
)


class TaskTracker:
    def __init__(self):
        self.tasks: dict[str, dict] = {}
        self.pending_creates: dict[str, dict] = {}

    def display_progress(self):
        if not self.tasks:
            print("\nProgress: no open tasks\n")
            return

        completed = len([t for t in self.tasks.values() if t["status"] == "completed"])
        in_progress = len([t for t in self.tasks.values() if t["status"] == "in_progress"])

        print(f"\nProgress: {completed}/{len(self.tasks)} completed")
        print(f"Currently working on: {in_progress} task(s)\n")

        for task_id, task in self.tasks.items():
            icon = (
                "✅"
                if task["status"] == "completed"
                else "🔧"
                if task["status"] == "in_progress"
                else "❌"
            )
            text = (
                task["activeForm"]
                if task["status"] == "in_progress" and task.get("activeForm")
                else task["subject"]
            )
            print(f"{task_id}. {icon} {text}")

    def handle_tool_use(self, block: ToolUseBlock):
        if block.name == "TaskCreate":
            self.pending_creates[block.id] = {
                "subject": block.input.get("subject", ""),
                "activeForm": block.input.get("activeForm") or block.input.get("active_form"),
            }
        elif block.name == "TaskUpdate":
            task_id = (
                block.input.get("taskId")
                or block.input.get("id")
                or block.input.get("task_id")
            )
            if not task_id:
                return
            if block.input.get("status") == "deleted":
                self.tasks.pop(task_id, None)
                self.display_progress()
                return
            task = self.tasks.get(task_id)
            if not task:
                return
            if block.input.get("status"):
                task["status"] = block.input["status"]
            active = block.input.get("activeForm") or block.input.get("active_form")
            if active:
                task["activeForm"] = active
            self.display_progress()

    def handle_tool_result(self, block: ToolResultBlock, tool_use_result):
        create = self.pending_creates.pop(block.tool_use_id, None)
        if create is None or block.is_error:
            return
        # The result's user message carries the tool's structured output as
        # tool_use_result; for TaskCreate that's {"task": {"id": ..., "subject": ...}}.
        task = (tool_use_result or {}).get("task") or {}
        if not task.get("id"):
            return
        self.tasks[task["id"]] = {**create, "status": "pending"}
        self.display_progress()

    async def track_query(self, prompt: str):
        try:
            async for message in query(
                prompt=prompt,
                options=ClaudeAgentOptions(
                    max_turns=20,
                    permission_mode="acceptEdits",
                    env={"CLAUDE_CODE_ENABLE_TODO_TOOLS": "1"},
                ),
            ):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, ToolUseBlock):
                            self.handle_tool_use(block)
                if isinstance(message, UserMessage) and isinstance(message.content, list):
                    for block in message.content:
                        if isinstance(block, ToolResultBlock):
                            self.handle_tool_result(block, message.tool_use_result)
        except Exception as error:
            # A single-shot query() raises after yielding an error result,
            # such as when the max_turns limit is hit.
            print(f"Session ended with an error: {error}")


# Usage
async def main():
    tracker = TaskTracker()
    await tracker.track_query("Build a complete authentication system with todos")


asyncio.run(main())
```

## 相關文件

* [Agent SDK 參考 - TypeScript](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md)：TypeScript SDK 的選項、類型和工具架構，包括 Task 工具輸入和輸出類型
* [Agent SDK 參考 - Python](https://code.claude.com/docs/zh-TW/agent-sdk/python.md)：Python SDK 的選項、類型和工具文件
* [串流輸入](https://code.claude.com/docs/zh-TW/agent-sdk/streaming-vs-single-mode.md)：兩種輸入模式，以及何時使用串流輸入而不是這些範例使用的單次呼叫
* [為 Claude 提供自訂工具](https://code.claude.com/docs/zh-TW/agent-sdk/custom-tools.md)：使用 SDK 的進程內 MCP 伺服器定義您自己的工具

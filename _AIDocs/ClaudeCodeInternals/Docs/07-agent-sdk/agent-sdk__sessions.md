<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/agent-sdk/sessions | lastmod: 2026-10-10 | section: Agent SDK / Core concepts -->
> 來源：https://code.claude.com/docs/zh-TW/agent-sdk/sessions（官方 zh-TW，lastmod 2026-10-10）｜分類：Agent SDK › Core concepts｜EN 摘要：How sessions persist agent conversation history, and when to use continue, resume, and fork to return to a prior run.

# 使用 sessions

> Sessions 如何保持代理對話歷史，以及何時使用 continue、resume 和 fork 返回到先前的運行。

Session 是 SDK 在您的代理工作時累積的對話歷史。它包含您的提示、代理進行的每個工具呼叫、每個工具結果和每個回應。SDK 會自動將其寫入磁碟，以便您稍後可以返回它。

返回 session 意味著代理具有之前的完整上下文：它已經讀取的檔案、它已經執行的分析、它已經做出的決定。您可以提出後續問題、從中斷中恢復，或分支以嘗試不同的方法。

> [!NOTE]
>
> Sessions 保持**對話**，而不是檔案系統。要快照和還原代理所做的檔案更改，請使用[檔案檢查點](https://code.claude.com/docs/zh-TW/agent-sdk/file-checkpointing.md)。

本指南涵蓋如何為您的應用選擇正確的方法、自動追蹤 sessions 的 SDK 介面、如何捕獲 session ID 並手動使用 `resume` 和 `fork`，以及關於跨主機恢復 sessions 的注意事項。

## 選擇一個方法

您需要多少 session 處理取決於您的應用程式的形狀。當您發送應該共享上下文的多個提示時，session 管理就會發揮作用。在單個 `query()` 呼叫中，代理已經根據需要進行了盡可能多的轉換，並且權限提示和 `AskUserQuestion` 是[在迴圈中處理](https://code.claude.com/docs/zh-TW/agent-sdk/user-input.md)的（它們不會結束呼叫）。

| 您正在構建的內容 | 使用什麼 |
| :- | :- |
| 一次性任務：單個提示，無後續 | 無需額外操作。一個 `query()` 呼叫可以處理它。 |
| 在一個進程中進行多轉對話 | [`ClaudeSDKClient`（Python）或 `continue: true`（TypeScript）](#automatic-session-management)。SDK 為您追蹤 session，無需 ID 處理。 |
| 在進程重新啟動後從中斷處繼續 | `continue_conversation=True`（Python）/ `continue: true`（TypeScript）。恢復目錄中最近的 session，無需 ID。 |
| 恢復特定的過去 session（不是最近的） | 捕獲 session ID 並將其傳遞給 `resume`。 |
| 嘗試替代方法而不失去原始方法 | Fork session。 |
| 無狀態任務，不想將任何內容寫入磁碟 | 設定 [`persistSession: false`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#options)（僅限 TypeScript）。Session 僅在呼叫期間存在於記憶體中。在 Python 中，在 `env` 選項中設定 [`CLAUDE_CODE_SKIP_PROMPT_HISTORY`](https://code.claude.com/docs/zh-TW/env-vars) 以改為抑制文字記錄寫入。 |

### Continue、resume 和 fork

Continue、resume 和 fork 是您在 `query()` 上設定的選項欄位（Python 中的 [`ClaudeAgentOptions`](https://code.claude.com/docs/zh-TW/agent-sdk/python#claudeagentoptions)，TypeScript 中的 [`Options`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#options)）。

**Continue** 和 **resume** 都會拾取現有 session 並將其添加到其中。區別在於它們如何找到該 session：

* **Continue** 在當前目錄中找到最近的 session。您無需追蹤任何內容。當您的應用一次運行一個對話時效果很好。
* **Resume** 採用特定的 session ID。您追蹤 ID。當您有多個 sessions（例如，多使用者應用中每個使用者一個）或想要返回不是最近的 session 時需要。

**Fork** 不同：它創建一個新 session，從原始 session 的歷史副本開始。原始 session 保持不變。使用 fork 嘗試不同的方向，同時保持返回的選項。

## 自動工作階段管理

兩個 SDK 都提供了一個介面，可以為您跨呼叫追蹤工作階段狀態，因此您不需要手動傳遞 ID。將這些用於單一程序內的多輪對話。

### Python：`ClaudeSDKClient`

[`ClaudeSDKClient`](https://code.claude.com/docs/zh-TW/agent-sdk/python#claudesdkclient) 在內部處理工作階段 ID。每次呼叫 `client.query()` 都會自動繼續同一工作階段。呼叫 [`client.receive_response()`](https://code.claude.com/docs/zh-TW/agent-sdk/python#claudesdkclient) 以逐一查看目前查詢的訊息。將用戶端用作非同步內容管理器，以便為您處理連線設定和清除，或手動呼叫 `connect()` 和 `disconnect()`。

此範例針對同一 `client` 執行兩個查詢。第一個要求代理程式分析一個模組；第二個要求它重構該模組。因為兩個呼叫都通過同一用戶端執行個體，第二個查詢具有來自第一個查詢的完整內容，無需任何明確的 `resume` 或工作階段 ID：

```python Python theme={null}
import asyncio
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
)


def print_response(message):
    """Print only the human-readable parts of a message."""
    if isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, TextBlock):
                print(block.text)
    elif isinstance(message, ResultMessage):
        cost = (
            f"${message.total_cost_usd:.4f}"
            if message.total_cost_usd is not None
            else "N/A"
        )
        print(f"[done: {message.subtype}, cost: {cost}]")


async def main():
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Edit", "Glob", "Grep"],
    )

    async with ClaudeSDKClient(options=options) as client:
        # First query: client captures the session ID internally
        await client.query("Analyze the auth module")
        async for message in client.receive_response():
            print_response(message)

        # Second query: automatically continues the same session
        await client.query("Now refactor it to use JWT")
        async for message in client.receive_response():
            print_response(message)


asyncio.run(main())
```

每個查詢都會列印代理程式的文字回應，後面跟著結果訊息的狀態行，例如 `[done: success, cost: $0.0042]`。

如需有關何時使用 `ClaudeSDKClient` 與獨立 `query()` 函式的詳細資訊，請參閱 [Python SDK 參考](https://code.claude.com/docs/zh-TW/agent-sdk/python.md#choosing-between-query-and-claudesdkclient)。

### TypeScript：`continue: true`

TypeScript SDK 沒有像 Python 的 `ClaudeSDKClient` 這樣的工作階段保持用戶端物件。相反，在每個後續 `query()` 呼叫上傳遞 `continue: true`，SDK 會在目前目錄中選取最近的工作階段。無需 ID 追蹤。

此範例進行兩個單獨的 `query()` 呼叫。第一個建立新的工作階段；第二個設定 `continue: true`，這會告訴 SDK 在磁碟上尋找並繼續最近的工作階段。代理程式具有來自第一個呼叫的完整內容：

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

// First query: creates a new session
try {
  for await (const message of query({
    prompt: "Analyze the auth module",
    options: { allowedTools: ["Read", "Glob", "Grep"] }
  })) {
    if (message.type === "result" && message.subtype === "success") {
      console.log(message.result);
    }
  }
} catch (error) {
  // A single-shot query() throws after yielding an error result,
  // so the follow-up query below still runs.
  console.error(`Session ended with an error: ${error}`);
}

// Second query: continue: true resumes the most recent session
for await (const message of query({
  prompt: "Now refactor it to use JWT",
  options: {
    continue: true,
    allowedTools: ["Read", "Edit", "Write", "Glob", "Grep"]
  }
})) {
  if (message.type === "result" && message.subtype === "success") {
    console.log(message.result);
  }
}
```

> [!NOTE]
>
> 實驗性 [V2 工作階段 API](https://code.claude.com/docs/zh-TW/agent-sdk/typescript-v2-preview.md)（提供了具有 `send` / `stream` 模式的 `createSession()`）已在 TypeScript Agent SDK 0.3.142 中移除。改用 `query()` 函式和本頁面上描述的工作階段選項。

## 使用 session 選項與 `query()`

### 捕獲 session ID

Resume 和 fork 需要 session ID。從結果訊息上的 `session_id` 欄位讀取它（Python 中的 [`ResultMessage`](https://code.claude.com/docs/zh-TW/agent-sdk/python#resultmessage)，TypeScript 中的 [`SDKResultMessage`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#sdkresultmessage)），無論成功或錯誤，它都存在於每個結果上。在 TypeScript 中，ID 也可以作為初始化 `SystemMessage` 上的直接欄位更早獲得；在 Python 中，它嵌套在 `SystemMessage.data` 內。

```python Python theme={null}
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage


async def main():
    session_id = None

    try:
        async for message in query(
            prompt="Analyze the auth module and suggest improvements",
            options=ClaudeAgentOptions(
                allowed_tools=["Read", "Glob", "Grep"],
            ),
        ):
            if isinstance(message, ResultMessage):
                session_id = message.session_id
                if message.subtype == "success":
                    print(message.result)
    except Exception as error:
        # A single-shot query() raises after yielding an error result. If the
        # failure was an error result, the loop above already captured session_id;
        # connection or process failures yield no result message, so session_id stays None.
        print(f"Session ended with an error: {error}")

    print(f"Session ID: {session_id}")
    return session_id


session_id = asyncio.run(main())
```

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

let sessionId: string | undefined;

try {
  for await (const message of query({
    prompt: "Analyze the auth module and suggest improvements",
    options: { allowedTools: ["Read", "Glob", "Grep"] }
  })) {
    if (message.type === "result") {
      sessionId = message.session_id;
      if (message.subtype === "success") {
        console.log(message.result);
      }
    }
  }
} catch (error) {
  // A single-shot query() throws after yielding an error result. If the
  // failure was an error result, the loop above already captured sessionId;
  // connection or process failures yield no result message, so sessionId stays undefined.
  console.error(`Session ended with an error: ${error}`);
}

console.log(`Session ID: ${sessionId}`);
```

當查詢完成時，指令碼會列印代理的回應，後面跟著一行，例如 `Session ID: 5b3f2c1a-8d4e-4f6b-9a7c-2e1d0f9b8a6c`。在接下來的章節中，您將此 ID 傳遞給 `resume`。

### 按 ID 恢復

將 session ID 傳遞給 `resume` 以返回到該特定 session。代理從 session 中斷的任何地方拾取完整上下文。恢復的常見原因：

* **跟進已完成的任務。** 代理已經分析了某些內容；現在您希望它根據該分析採取行動，而無需重新讀取文件。
* **從限制中恢復。** 第一次運行以 `error_max_turns` 或 `error_max_budget_usd` 結束（請參閱[處理結果](https://code.claude.com/docs/zh-TW/agent-sdk/agent-loop.md#handle-the-result)）；以更高的限制恢復。在單次 `query()` 呼叫中，SDK 會在產生該錯誤結果後引發異常，因此在恢復前捕獲錯誤。
* **重新啟動您的進程。** 您在關閉前捕獲了 ID，並想恢復對話。

此示例使用後續提示恢復[捕獲 session ID](#capture-the-session-id) 中的 session。因為您正在恢復，代理已經在上下文中具有先前的分析：

```python Python theme={null}
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

session_id = "..."  # The ID you captured in the previous example


async def main():
    # Earlier session analyzed the code; now build on that analysis
    async for message in query(
        prompt="Now implement the refactoring you suggested",
        options=ClaudeAgentOptions(
            resume=session_id,
            allowed_tools=["Read", "Edit", "Write", "Glob", "Grep"],
        ),
    ):
        if isinstance(message, ResultMessage) and message.subtype == "success":
            print(message.result)


asyncio.run(main())
```

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

const sessionId = "..."; // The ID you captured in the previous example

// Earlier session analyzed the code; now build on that analysis
for await (const message of query({
  prompt: "Now implement the refactoring you suggested",
  options: {
    resume: sessionId,
    allowedTools: ["Read", "Edit", "Write", "Glob", "Grep"]
  }
})) {
  if (message.type === "result" && message.subtype === "success") {
    console.log(message.result);
  }
}
```

您應該會看到一個基於先前分析而構建的回應，而不是從頭開始。這確認了代理以其先前的上下文完整恢復了 session。

> [!TIP]
>
> Claude Code 將 sessions 存儲在 `~/.claude/projects/<encoded-cwd>/*.jsonl` 下。如果您設定了 `CLAUDE_CONFIG_DIR` 環境變數，請改為查看 `$CLAUDE_CONFIG_DIR/projects/` 下。
>
> 要找到您的 session 目錄，請將絕對工作目錄中的每個非英數字元替換為 `-`：`/Users/me/proj` 變成 `-Users-me-proj`。對於轉換後的名稱超過 200 個字元的工作目錄，Claude Code [會截斷名稱並附加雜湊](https://code.claude.com/docs/zh-TW/sessions.md#where-transcripts-are-stored)，因此在列出 `projects/` 時，請匹配轉換後名稱的前 200 個字元。
>
> 如果您在 `CLAUDE_CONFIG_DIR` 旁邊設定 [`CLAUDE_CODE_PROJECT_DIR_NAME`](https://code.claude.com/docs/zh-TW/sessions#name-the-project-directory-yourself)，請改為查看 `projects/` 中的該名稱。需要 TypeScript Agent SDK v0.3.234 或更新版本，或 Python Agent SDK v0.2.140 或更新版本。
>
> 您可以從任何工作目錄恢復：
>
> * **跨目錄查詢**：Claude Code 會搜尋目前專案目錄以外的位置以找到 ID；請參閱[恢復工作階段](https://code.claude.com/docs/zh-TW/sessions.md#where-the-session-picker-looks)以了解確切的查詢順序以及如何處理重複副本。
> * **僅限同一機器**：session 文件仍需要存在於目前機器上。
>
> 在 v2.1.223 之前，查詢的範圍限於目前專案目錄及其 git worktrees；捆綁較舊 CLI 的 SDK 版本仍然以這種方式運作。

要跨機器或在無伺服器環境中恢復 sessions，請使用 [`SessionStore` 適配器](https://code.claude.com/docs/zh-TW/agent-sdk/session-storage)將記錄鏡像到共享存儲。

### Fork 以探索替代方案

Forking 創建一個新 session，從原始 session 的歷史副本開始，但從該點開始分歧。fork 獲得自己的 session ID；原始的 ID 和歷史保持不變。您最終得到兩個獨立的 sessions，可以分別恢復。

> [!NOTE]
>
> Forking 分支對話歷史，而不是文件系統。如果 forked 代理編輯文件，這些更改是真實的，對在同一目錄中工作的任何 session 都可見。要分支和還原文件更改，請使用[文件檢查點](https://code.claude.com/docs/zh-TW/agent-sdk/file-checkpointing.md)。

此示例基於[捕獲 session ID](#capture-the-session-id)：您已經在 `session_id` 中分析了一個 auth 模組，並想探索 OAuth2 而不失去 JWT 焦點的線程。第一個塊 forks session 並捕獲 fork 的 ID（`forked_id`）；第二個塊恢復原始 `session_id` 以繼續沿著 JWT 路徑。您現在有兩個 session ID 指向兩個單獨的歷史：

```python Python theme={null}
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

session_id = "..."  # The ID you captured in the previous example


async def main():
    # Fork: branch from session_id into a new session
    forked_id = None
    try:
        async for message in query(
            prompt="Instead of JWT, outline how OAuth2 would work for the auth module",
            options=ClaudeAgentOptions(
                resume=session_id,
                fork_session=True,
                max_turns=5,
            ),
        ):
            if isinstance(message, ResultMessage):
                forked_id = message.session_id  # The fork's ID, distinct from session_id
                if message.subtype == "success":
                    print(message.result)
    except Exception as error:
        # A single-shot query() raises after yielding an error result. If the
        # failure was an error result, forked_id was already captured by the
        # loop above; connection or process failures yield no result message.
        print(f"Session ended with an error: {error}")

    print(f"Forked session: {forked_id}")

    # Original session is untouched; resuming it continues the JWT thread
    try:
        async for message in query(
            prompt="Continue with the JWT approach",
            options=ClaudeAgentOptions(resume=session_id),
        ):
            if isinstance(message, ResultMessage) and message.subtype == "success":
                print(message.result)
    except Exception as error:
        # A single-shot query() raises after yielding an error result.
        print(f"Session ended with an error: {error}")


asyncio.run(main())
```

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

const sessionId = "..."; // The ID you captured in the previous example

// Fork: branch from sessionId into a new session
let forkedId: string | undefined;

try {
  for await (const message of query({
    prompt: "Instead of JWT, outline how OAuth2 would work for the auth module",
    options: {
      resume: sessionId,
      forkSession: true,
      maxTurns: 5
    }
  })) {
    if (message.type === "system" && message.subtype === "init") {
      forkedId = message.session_id; // The fork's ID, distinct from sessionId
    }
    if (message.type === "result" && message.subtype === "success") {
      console.log(message.result);
    }
  }
} catch (error) {
  // A single-shot query() throws after yielding an error result. If the
  // failure was an error result, forkedId was already captured by the loop
  // above; connection or process failures yield no result message.
  console.error(`Session ended with an error: ${error}`);
}

console.log(`Forked session: ${forkedId}`);

// Original session is untouched; resuming it continues the JWT thread
try {
  for await (const message of query({
    prompt: "Continue with the JWT approach",
    options: { resume: sessionId }
  })) {
    if (message.type === "result" && message.subtype === "success") {
      console.log(message.result);
    }
  }
} catch (error) {
  // A single-shot query() throws after yielding an error result.
  console.error(`Session ended with an error: ${error}`);
}
```

您應該會看到 `forkedId` 與原始 session ID 不同。恢復原始 session 仍然會繼續 JWT 線程，這確認了 fork 沒有修改原始歷史。

## 跨主機恢復

Session 文件是創建它們的機器的本地文件。要在不同的主機上恢復 session（CI 工作者、臨時容器、無伺服器），請選擇適合的方法：

* **傳遞 session 存放區。** 附加一個 [`sessionStore` / `session_store` 配接器](https://code.claude.com/docs/zh-TW/agent-sdk/session-storage)，以便 SDK 將記錄鏡像到您自己的後端，另一個主機可以恢復它們。存放區查詢鍵衍生自工作目錄，因此請從與原始執行的 `cwd` 相符的目錄恢復。

* **移動 session 文件。** 從第一次執行中保持 `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`，並在呼叫 `resume` 之前將其還原到新主機上 `~/.claude/projects/` 下的任何目錄內。

  Claude Code 會搜尋超出目前專案目錄的範圍來尋找 ID；請參閱[恢復工作階段](https://code.claude.com/docs/zh-TW/sessions.md#where-the-session-picker-looks)以了解確切的查詢順序以及如何處理重複副本。在 v2.1.223 之前，查詢範圍限於目前專案目錄及其 git worktree；捆綁較舊 CLI 的 SDK 版本仍然以這種方式運作。

* **不依賴 session 恢復。** 捕獲您需要的結果（分析輸出、決定、文件差異）作為應用程式狀態，並將其傳遞到新 session 的提示中。這通常比運送記錄文件更穩健。

兩個 SDK 都公開用於列舉磁碟上的 sessions 和讀取其訊息的函數：TypeScript 中的 [`listSessions()`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#listsessions) 和 [`getSessionMessages()`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#getsessionmessages)，Python 中的 [`list_sessions()`](https://code.claude.com/docs/zh-TW/agent-sdk/python#list_sessions) 和 [`get_session_messages()`](https://code.claude.com/docs/zh-TW/agent-sdk/python#get_session_messages)。使用它們構建自訂 session 選擇器、清理邏輯或記錄檢視器。

兩個 SDK 也公開用於查找和變更個別 sessions 的函數：Python 中的 [`get_session_info()`](https://code.claude.com/docs/zh-TW/agent-sdk/python#get_session_info)、[`rename_session()`](https://code.claude.com/docs/zh-TW/agent-sdk/python#rename_session) 和 [`tag_session()`](https://code.claude.com/docs/zh-TW/agent-sdk/python#tag_session)，以及 TypeScript 中的 [`getSessionInfo()`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#getsessioninfo)、[`renameSession()`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#renamesession) 和 [`tagSession()`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#tagsession)。使用它們按標籤組織 sessions 或給它們人類可讀的標題。

## 相關資源

* [代理迴圈如何工作](https://code.claude.com/docs/zh-TW/agent-sdk/agent-loop.md)：了解 session 中的轉換、訊息和上下文累積
* [文件檢查點](https://code.claude.com/docs/zh-TW/agent-sdk/file-checkpointing.md)：快照和還原代理在 session 中所做的文件更改
* [Python `ClaudeAgentOptions`](https://code.claude.com/docs/zh-TW/agent-sdk/python#claudeagentoptions)：Python 的完整 session 選項參考
* [TypeScript `Options`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#options)：TypeScript 的完整 session 選項參考

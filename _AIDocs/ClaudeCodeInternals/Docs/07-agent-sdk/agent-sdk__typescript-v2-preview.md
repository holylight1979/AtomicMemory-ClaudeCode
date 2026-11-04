<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/agent-sdk/typescript-v2-preview | lastmod: 2026-09-10 | section: Agent SDK / SDK references -->
> 來源：https://code.claude.com/docs/zh-TW/agent-sdk/typescript-v2-preview（官方 zh-TW，lastmod 2026-09-10）｜分類：Agent SDK › SDK references｜EN 摘要：Reference for the removed V2 TypeScript Agent SDK session API, with session-based send/stream patterns for multi-turn conversations.

# TypeScript SDK V2 會話 API（已移除）

> 已移除的 V2 TypeScript Agent SDK 會話 API 參考，具有用於多輪對話的基於會話的 send/stream 模式。

> [!WARNING]
>
> V2 會話 API 不再受支援。TypeScript Agent SDK 0.3.142 移除了 `unstable_v2_createSession`、`unstable_v2_resumeSession`、`unstable_v2_prompt` 以及 `SDKSession` 和 `SDKSessionOptions` 類型。
>
> 若要遷移，請使用 [`query()` API](https://code.claude.com/docs/zh-TW/agent-sdk/typescript) 和它接受的[會話選項](https://code.claude.com/docs/zh-TW/agent-sdk/sessions.md)。傳遞 `AsyncIterable<SDKUserMessage>` 進行多輪對話，或使用 `options.resume` 繼續已保存的會話。如果您在 Agent SDK 0.2.x 或更早版本上維護程式碼，此頁面保留供參考。

V2 是一個實驗性會話 API，消除了對非同步生成器和 yield 協調的需求。與其在各輪之間管理生成器狀態，每一輪都是一個單獨的 `send()`/`stream()` 週期。API 表面縮減為三個概念：

* `createSession()` / `resumeSession()`：開始或繼續對話
* `session.send()`：發送訊息
* `session.stream()`：取得回應

## 安裝

Agent SDK 0.2.x 是包含 V2 介面的最後一個版本。套件版本從 0.2.x 直接跳到 0.3.142，因此上面的移除版本和下面的安裝固定版本描述的是同一個邊界。若要安裝最後一個 V2 相容版本，請固定主要和次要版本：

```bash theme={null}
npm install @anthropic-ai/claude-agent-sdk@0.2
```

> [!NOTE]
>
> SDK 為您的平台捆綁了一個原生 Claude Code 二進位檔案作為可選依賴項，因此大多數安裝無需單獨安裝 Claude Code。請參閱 [快速入門的安裝說明](https://code.claude.com/docs/zh-TW/agent-sdk/quickstart.md) 以了解需要單獨安裝的情況。

## 快速開始

### 單次提示

對於不需要維護會話的簡單單輪查詢，請使用 `unstable_v2_prompt()`。此範例發送一個數學問題並記錄答案：

```typescript theme={null}
import { unstable_v2_prompt } from "@anthropic-ai/claude-agent-sdk";

const result = await unstable_v2_prompt("What is 2 + 2?", {
  model: "claude-opus-4-7"
});
if (result.subtype === "success") {
  console.log(result.result);
}
```

<details>
  <summary>查看 V1 中的相同操作</summary>

  ```typescript theme={null}
  import { query } from "@anthropic-ai/claude-agent-sdk";

  const q = query({
    prompt: "What is 2 + 2?",
    options: { model: "claude-opus-4-7" }
  });

  for await (const msg of q) {
    if (msg.type === "result" && msg.subtype === "success") {
      console.log(msg.result);
    }
  }
  ```
</details>

### 基本會話

對於超出單個提示的互動，請建立一個會話。V2 將發送和串流分為不同的步驟：

* `send()` 分派您的訊息
* `stream()` 串流回應

這種明確的分離使得在輪次之間添加邏輯變得更容易（例如在發送後續訊息之前處理回應）。

下面的範例建立一個會話，向 Claude 發送「Hello!」，並列印文字回應。它使用 [`await using`](https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-2.html#using-declarations-and-explicit-resource-management)（TypeScript 5.2+）在區塊退出時自動關閉會話。您也可以手動呼叫 `session.close()`。

```typescript theme={null}
import { unstable_v2_createSession } from "@anthropic-ai/claude-agent-sdk";

await using session = unstable_v2_createSession({
  model: "claude-opus-4-7"
});

await session.send("Hello!");
for await (const msg of session.stream()) {
  // Filter for assistant messages to get human-readable output
  if (msg.type === "assistant") {
    const text = msg.message.content
      .filter((block) => block.type === "text")
      .map((block) => block.text)
      .join("");
    console.log(text);
  }
}
```

<details>
  <summary>查看 V1 中的相同操作</summary>

  在 V1 中，輸入和輸出都通過單個非同步生成器流動。對於基本提示，這看起來很相似，但添加多輪邏輯需要重新構造以使用輸入生成器。

  ```typescript theme={null}
  import { query } from "@anthropic-ai/claude-agent-sdk";

  const q = query({
    prompt: "Hello!",
    options: { model: "claude-opus-4-7" }
  });

  for await (const msg of q) {
    if (msg.type === "assistant") {
      const text = msg.message.content
        .filter((block) => block.type === "text")
        .map((block) => block.text)
        .join("");
      console.log(text);
    }
  }
  ```
</details>

### 多輪對話

會話在多次交換中保持上下文。要繼續對話，請在同一會話上再次呼叫 `send()`。Claude 會記住之前的輪次。

此範例詢問一個數學問題，然後詢問一個引用先前答案的後續問題：

```typescript theme={null}
import { unstable_v2_createSession } from "@anthropic-ai/claude-agent-sdk";

await using session = unstable_v2_createSession({
  model: "claude-opus-4-7"
});

// Turn 1
await session.send("What is 5 + 3?");
for await (const msg of session.stream()) {
  // Filter for assistant messages to get human-readable output
  if (msg.type === "assistant") {
    const text = msg.message.content
      .filter((block) => block.type === "text")
      .map((block) => block.text)
      .join("");
    console.log(text);
  }
}

// Turn 2
await session.send("Multiply that by 2");
for await (const msg of session.stream()) {
  if (msg.type === "assistant") {
    const text = msg.message.content
      .filter((block) => block.type === "text")
      .map((block) => block.text)
      .join("");
    console.log(text);
  }
}
```

<details>
  <summary>查看 V1 中的相同操作</summary>

  ```typescript theme={null}
  import { query } from "@anthropic-ai/claude-agent-sdk";

  // Must create an async iterable to feed messages
  async function* createInputStream() {
    yield {
      type: "user",
      session_id: "",
      message: { role: "user", content: [{ type: "text", text: "What is 5 + 3?" }] },
      parent_tool_use_id: null
    };
    // Must coordinate when to yield next message
    yield {
      type: "user",
      session_id: "",
      message: { role: "user", content: [{ type: "text", text: "Multiply by 2" }] },
      parent_tool_use_id: null
    };
  }

  const q = query({
    prompt: createInputStream(),
    options: { model: "claude-opus-4-7" }
  });

  for await (const msg of q) {
    if (msg.type === "assistant") {
      const text = msg.message.content
        .filter((block) => block.type === "text")
        .map((block) => block.text)
        .join("");
      console.log(text);
    }
  }
  ```
</details>

### 會話恢復

如果您有來自先前互動的會話 ID，您可以稍後恢復它。這對於長時間運行的工作流程或當您需要在應用程式重新啟動時保持對話時很有用。

此範例建立一個會話，儲存其 ID，關閉它，然後恢復對話：

```typescript theme={null}
import {
  unstable_v2_createSession,
  unstable_v2_resumeSession,
  type SDKMessage
} from "@anthropic-ai/claude-agent-sdk";

// Helper to extract text from assistant messages
function getAssistantText(msg: SDKMessage): string | null {
  if (msg.type !== "assistant") return null;
  return msg.message.content
    .filter((block) => block.type === "text")
    .map((block) => block.text)
    .join("");
}

// Create initial session and have a conversation
const session = unstable_v2_createSession({
  model: "claude-opus-4-7"
});

await session.send("Remember this number: 42");

// Get the session ID from any received message
let sessionId: string | undefined;
for await (const msg of session.stream()) {
  sessionId = msg.session_id;
  const text = getAssistantText(msg);
  if (text) console.log("Initial response:", text);
}

console.log("Session ID:", sessionId);
session.close();

// Later: resume the session using the stored ID
await using resumedSession = unstable_v2_resumeSession(sessionId!, {
  model: "claude-opus-4-7"
});

await resumedSession.send("What number did I ask you to remember?");
for await (const msg of resumedSession.stream()) {
  const text = getAssistantText(msg);
  if (text) console.log("Resumed response:", text);
}
```

<details>
  <summary>查看 V1 中的相同操作</summary>

  ```typescript theme={null}
  import { query } from "@anthropic-ai/claude-agent-sdk";

  // Create initial session
  const initialQuery = query({
    prompt: "Remember this number: 42",
    options: { model: "claude-opus-4-7" }
  });

  // Get session ID from any message
  let sessionId: string | undefined;
  for await (const msg of initialQuery) {
    sessionId = msg.session_id;
    if (msg.type === "assistant") {
      const text = msg.message.content
        .filter((block) => block.type === "text")
        .map((block) => block.text)
        .join("");
      console.log("Initial response:", text);
    }
  }

  console.log("Session ID:", sessionId);

  // Later: resume the session
  const resumedQuery = query({
    prompt: "What number did I ask you to remember?",
    options: {
      model: "claude-opus-4-7",
      resume: sessionId
    }
  });

  for await (const msg of resumedQuery) {
    if (msg.type === "assistant") {
      const text = msg.message.content
        .filter((block) => block.type === "text")
        .map((block) => block.text)
        .join("");
      console.log("Resumed response:", text);
    }
  }
  ```
</details>

### 清理

會話可以手動關閉或使用 [`await using`](https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-2.html#using-declarations-and-explicit-resource-management)（TypeScript 5.2+ 功能用於自動資源清理）自動關閉。如果您使用的是較舊的 TypeScript 版本或遇到相容性問題，請改用手動清理。

下面的範例僅顯示清理模式，不發送任何訊息，因此運行它們不會產生任何輸出。

**自動清理（TypeScript 5.2+）：**

```typescript theme={null}
import { unstable_v2_createSession } from "@anthropic-ai/claude-agent-sdk";

await using session = unstable_v2_createSession({
  model: "claude-opus-4-7"
});
// Session closes automatically when the block exits
```

**手動清理：**

```typescript theme={null}
import { unstable_v2_createSession } from "@anthropic-ai/claude-agent-sdk";

const session = unstable_v2_createSession({
  model: "claude-opus-4-7"
});
// ... use the session ...
session.close();
```

## API 參考

### `unstable_v2_createSession()`

為多輪對話建立新會話。

```typescript theme={null}
function unstable_v2_createSession(options: {
  model: string;
  // Additional options supported
}): SDKSession;
```

### `unstable_v2_resumeSession()`

按 ID 恢復現有會話。

```typescript theme={null}
function unstable_v2_resumeSession(
  sessionId: string,
  options: {
    model: string;
    // Additional options supported
  }
): SDKSession;
```

### `unstable_v2_prompt()`

用於單輪查詢的單次便利函數。

```typescript theme={null}
function unstable_v2_prompt(
  prompt: string,
  options: {
    model: string;
    // Additional options supported
  }
): Promise<SDKResultMessage>;
```

### SDKSession 介面

```typescript theme={null}
interface SDKSession {
  readonly sessionId: string;
  send(message: string | SDKUserMessage): Promise<void>;
  stream(): AsyncGenerator<SDKMessage, void>;
  close(): void;
}
```

## 功能可用性

V2 會話 API 不支援每個 V1 功能。以下功能需要使用 [V1 SDK](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md)：

* 會話分叉（`forkSession` 選項）
* 某些進階串流輸入模式

## 另請參閱

* [TypeScript SDK 參考（V1）](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md) - 完整的 V1 SDK 文件
* [SDK 概述](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) - 一般 SDK 概念
* [GitHub 上的 V2 範例](https://github.com/anthropics/claude-agent-sdk-demos/tree/main/hello-world-v2) - 工作程式碼範例

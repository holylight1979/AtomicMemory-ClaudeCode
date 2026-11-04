<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/agent-sdk/streaming-vs-single-mode | lastmod: 2026-10-02 | section: Agent SDK / Input and output -->
> 來源：https://code.claude.com/docs/zh-TW/agent-sdk/streaming-vs-single-mode（官方 zh-TW，lastmod 2026-10-02）｜分類：Agent SDK › Input and output｜EN 摘要：Understanding the two input modes for Claude Agent SDK and when to use each

# 串流輸入

> 了解 Claude Agent SDK 的兩種輸入模式及何時使用各種模式

## 概述

Claude Agent SDK 支援兩種不同的輸入模式來與代理互動：

* **串流輸入模式**：持久的互動式工作階段
* **單一訊息輸入**：使用工作階段狀態和恢復的一次性查詢

## 串流輸入模式（推薦）

串流輸入模式是使用 Claude Agent SDK 的**首選**方式。它提供對代理功能的完整存取，並啟用豐富的互動式體驗。

它允許代理作為長期執行的程序運作，接收使用者輸入、處理中斷、顯示權限請求，以及處理工作階段管理。

### 優點

在串流輸入模式中，您在具有這些功能的持久工作階段中工作：

* **影像上傳**：直接將影像附加到訊息中以進行視覺分析和理解
* **佇列訊息**：傳送多個訊息以順序處理，並能夠中斷
* **工具整合**：在工作階段期間完整存取所有工具和自訂 MCP 伺服器
* **即時回饋**：查看產生的回應，而不僅僅是最終結果
* **內容持久性**：自然地在多個回合中維持對話內容

### 實作範例

這些範例從工作目錄讀取名為 `diagram.png` 的影像。請先在該處建立一個，或變更檔案名稱以指向您自己的影像。

```typescript TypeScript theme={null}
import { query, type SDKUserMessage } from "@anthropic-ai/claude-agent-sdk";
import { readFile } from "fs/promises";

async function* generateMessages(): AsyncGenerator<SDKUserMessage> {
  // First message
  yield {
    type: "user",
    message: {
      role: "user",
      content: "Analyze this codebase for security issues"
    },
    parent_tool_use_id: null
  };

  // Wait for conditions or user input
  await new Promise((resolve) => setTimeout(resolve, 2000));

  // Follow-up with image
  yield {
    type: "user",
    message: {
      role: "user",
      content: [
        {
          type: "text",
          text: "Review this architecture diagram"
        },
        {
          type: "image",
          source: {
            type: "base64",
            media_type: "image/png",
            data: await readFile("diagram.png", "base64")
          }
        }
      ]
    },
    parent_tool_use_id: null
  };
}

// Process streaming responses
for await (const message of query({
  prompt: generateMessages(),
  options: {
    maxTurns: 10,
    allowedTools: ["Read", "Grep"]
  }
})) {
  if (message.type === "result" && message.subtype === "success") {
    console.log(message.result);
  }
}
```

```python Python theme={null}
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
)
import asyncio
import base64


async def streaming_analysis():
    async def message_generator():
        # First message
        yield {
            "type": "user",
            "message": {
                "role": "user",
                "content": "Analyze this codebase for security issues",
            },
        }

        # Wait for conditions
        await asyncio.sleep(2)

        # Follow-up with image
        with open("diagram.png", "rb") as f:
            image_data = base64.b64encode(f.read()).decode()

        yield {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Review this architecture diagram"},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_data,
                        },
                    },
                ],
            },
        }

    # Use ClaudeSDKClient for streaming input
    options = ClaudeAgentOptions(max_turns=10, allowed_tools=["Read", "Grep"])

    async with ClaudeSDKClient(options) as client:
        # Send streaming input
        await client.query(message_generator())

        # Process responses
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text)


asyncio.run(streaming_analysis())
```

當您執行範例時，TypeScript 版本會在每個回應完成時列印它。Python 版本的 `receive_response()` 迴圈在第一個結果訊息處結束，因此它會列印安全性分析；若要讀取兩個回應，請使用一個 `query()` 和 `receive_response()` 配對，如 [Python 參考的繼續對話範例](https://code.claude.com/docs/zh-TW/agent-sdk/python.md#example-continuing-a-conversation) 所示。

如果影像區塊的 `source` 遺失或不是物件，SDK 不會回報錯誤。Claude Code 會以一則文字說明取代該影像傳送給 Claude，例如 `[Image could not be processed: image block has no source object]`，而工作階段會繼續進行。

> [!NOTE]
>
> 在 TypeScript SDK 中，如果您的訊息產生器拋出例外，例如當它讀取的檔案遺失時，串流會以錯誤結束，該錯誤顯示為 `Claude Code process aborted by user`，而不是原始錯誤，因此當您看到該訊息時，請先檢查產生器內的程式碼。該錯誤前面也可能會有一長行的最小化捆綁 SDK 原始碼，因此請閱讀輸出末尾以取得錯誤文字。
>
> 在 Python SDK 中，產生器例外會在偵錯層級記錄，工作階段會停滯而不會引發，因此如果串流工作階段掛起且沒有輸出，請啟用偵錯記錄並檢查您的產生器。

## 單一訊息輸入

單一訊息輸入更簡單但功能更受限。

### 何時使用單一訊息輸入

在以下情況下使用單一訊息輸入：

* 您需要一次性回應
* 您不需要影像附件或中途工作階段控制方法
* 您需要在無狀態環境中運作，例如 lambda 函式

### 限制

> [!WARNING]
>
> 單一訊息輸入模式**不**支援：
>
> * 訊息中的直接影像附件
> * 動態訊息佇列
> * 即時中斷
> * 自然的多回合對話

如果查詢以錯誤結果結束，例如 `error_max_turns`，單一訊息 `query()` 呼叫會引發一個錯誤，該錯誤在產生最終結果訊息後包含失敗文字，因此如果您的程式碼需要繼續執行，請將迴圈包裝在 try 區塊中。請參閱 [處理結果](https://code.claude.com/docs/zh-TW/agent-sdk/agent-loop.md#handle-the-result) 以了解結果子類型。

### 實作範例

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

// Simple one-shot query
// query() throws after an error result, such as error_max_turns
try {
  for await (const message of query({
    prompt: "Explain the authentication flow",
    options: {
      maxTurns: 5,
      allowedTools: ["Read", "Grep"]
    }
  })) {
    if (message.type === "result" && message.subtype === "success") {
      console.log(message.result);
    }
  }
} catch (error) {
  console.error(`Query failed: ${error}`);
}

// Continue conversation with session management
try {
  for await (const message of query({
    prompt: "Now explain the authorization process",
    options: {
      continue: true,
      maxTurns: 5
    }
  })) {
    if (message.type === "result" && message.subtype === "success") {
      console.log(message.result);
    }
  }
} catch (error) {
  console.error(`Query failed: ${error}`);
}
```

```python Python theme={null}
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage
import asyncio


async def single_message_example():
    # Simple one-shot query using query() function
    # query() raises ResultError after an error result, such as error_max_turns
    try:
        async for message in query(
            prompt="Explain the authentication flow",
            options=ClaudeAgentOptions(max_turns=5, allowed_tools=["Read", "Grep"]),
        ):
            if isinstance(message, ResultMessage) and message.subtype == "success":
                print(message.result)
    except Exception as e:
        print(f"Query failed: {e}")

    # Continue conversation with session management
    try:
        async for message in query(
            prompt="Now explain the authorization process",
            options=ClaudeAgentOptions(continue_conversation=True, max_turns=5),
        ):
            if isinstance(message, ResultMessage) and message.subtype == "success":
                print(message.result)
    except Exception as e:
        print(f"Query failed: {e}")


asyncio.run(single_message_example())
```

當您執行此範例時，每個查詢都會列印其最終結果文字：首先是驗證說明，然後是授權說明。

<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/agent-sdk/cost-tracking | lastmod: 2026-11-02 | section: Agent SDK / Control and observability -->
> 來源：https://code.claude.com/docs/zh-TW/agent-sdk/cost-tracking（官方 zh-TW，lastmod 2026-11-02）｜分類：Agent SDK › Control and observability｜EN 摘要：Learn how to track token usage, estimate costs, and configure prompt caching with the Claude Agent SDK.

# 追蹤成本和使用量

> 了解如何追蹤 token 使用量、估計成本，以及使用 Claude Agent SDK 設定 prompt caching。

Claude Agent SDK 為每次與 Claude 的互動提供詳細的 token 使用量資訊。本指南說明如何正確追蹤使用量和理解成本報告，特別是在處理平行工具使用和多步驟對話時。

如需完整的 API 文件，請參閱 [TypeScript SDK 參考](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md)和 [Python SDK 參考](https://code.claude.com/docs/zh-TW/agent-sdk/python.md)。

> [!WARNING]
>
> `total_cost_usd` 和 `costUSD` 欄位是用戶端估計值，不是權威的計費資料。SDK 從在建置時捆綁的價格表在本機計算它們，除非有 [`modelPricing`](https://code.claude.com/docs/zh-TW/settings-reference#modelpricing) 表生效。當發生以下情況時，它們可能會與您實際被計費的金額不同：
>
> * 定價變更
> * 已安裝的 SDK 版本無法識別某個模型
> * 適用用戶端無法建模的計費規則
>
> SDK 確實建模的一個計費規則是[資料駐留定價](https://platform.claude.com/docs/en/about-claude/pricing#data-residency-pricing)。當回應的 `usage` 報告 `inference_geo: "us"` 時，SDK 會將該回應的 token 清單價格乘以 1.1。每個請求的費用（例如網路搜尋）不會被乘以該倍數。需要 TypeScript Agent SDK v0.3.239 或更新版本，或 Python Agent SDK v0.2.144 或更新版本。
>
> 使用這些欄位進行開發洞察和近似預算編制。如需權威計費，請參閱[管理組織的成本](https://code.claude.com/docs/zh-TW/costs.md#manage-costs-for-your-organization)。請勿向終端使用者計費或從這些欄位觸發財務決策。

## 瞭解權杖使用量

TypeScript 和 Python SDK 使用不同的欄位名稱公開相同的使用量資料：

* **TypeScript** 在每個助手訊息上提供逐步權杖細目（`message.message.id`、`message.message.usage`），透過結果訊息上的 `modelUsage` 提供每個模型的成本，以及結果訊息上的累積總計。
* **Python** 在每個助手訊息上提供逐步權杖細目，分別為 `message.usage` 和 `message.message_id`，透過結果訊息上的 `model_usage` 提供每個模型的成本，以及結果訊息上的累積總計，名稱為 `total_cost_usd`。

兩個 SDK 使用相同的基礎成本模型，並公開相同的粒度。差異在於欄位命名和逐步使用量的巢狀位置。

成本追蹤取決於瞭解 SDK 如何限定使用量資料的範圍：

* **`query()` 呼叫：** SDK 的 `query()` 函式的一次調用。單一呼叫可能涉及多個步驟：Claude 回應、使用工具、取得結果，然後再次回應。每個呼叫在結尾產生一個 [`result`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#sdkresultmessage) 訊息，除了在[串流輸入模式](https://code.claude.com/docs/zh-TW/agent-sdk/streaming-vs-single-mode.md)中，其中一個 `query()` 呼叫會進行多個使用者回合，每個回合會發出自己的 `result` 訊息。
* **步驟：** `query()` 呼叫內的單一請求/回應週期。每個步驟產生具有權杖使用量的助手訊息。
* **工作階段：** 由工作階段 ID 連結的一系列 `query()` 呼叫（使用 `resume` 選項）。已恢復呼叫的結果會報告工作階段的整體支出，而不只是該呼叫自己的支出。請參閱[跨多個呼叫累積成本](#accumulate-costs-across-multiple-calls)以瞭解總計如何結轉。

下圖顯示來自單一 `query()` 呼叫的訊息串流，在每個步驟報告權杖使用量，以及結尾的累積估計：

![Diagram showing a query producing two steps of messages. Step 1 has four assistant messages sharing the same ID and usage (count once), Step 2 has one assistant message with a new ID, and the final result message shows the estimated total\_cost\_usd.](https://mintcdn.com/claude-code/ikqp3_70mqIahteV/images/agent-sdk/message-usage-flow.svg?fit=max\&auto=format\&n=ikqp3_70mqIahteV\&q=85\&s=68497aee338e01cc745323af7aea378e)

**1. 每個步驟產生助手訊息**

當 Claude 回應時，它會傳送一個或多個助手訊息。在 TypeScript 中，每個助手訊息包含一個巢狀的 `BetaMessage`（透過 `message.message` 存取），具有 `id` 和一個包含權杖計數（`input_tokens`、`output_tokens`）的 [`usage`](https://platform.claude.com/docs/en/api/messages) 物件。在 Python 中，`AssistantMessage` 資料類別透過 `message.usage` 和 `message.message_id` 直接公開相同的資料。當 Claude 在一個回合中使用多個工具時，該回合中的所有訊息共享相同的 ID，因此請按 ID 進行重複資料刪除以避免重複計算。

**2. 結果訊息提供累積估計**

當 `query()` 呼叫完成時，SDK 會發出一個結果訊息，其中包含 `total_cost_usd` 和累積 `usage`，在 TypeScript 中輸入為 [`SDKResultMessage`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#sdkresultmessage)，在 Python 中輸入為 [`ResultMessage`](https://code.claude.com/docs/zh-TW/agent-sdk/python#resultmessage)。如果您只需要估計的總計，您可以忽略逐步使用量，並讀取此單一值。

如果您進行多個獨立的 `query()` 呼叫，每個結果只反映該個別呼叫的成本。恢復工作階段的呼叫也會計算工作階段的較早支出。

在串流輸入模式中，每個回合會發出自己的結果訊息。請參閱[在串流輸入模式中追蹤成本](#track-costs-in-streaming-input-mode)以瞭解如何在該模式中讀取呼叫總計。

## 在串流輸入模式中追蹤成本

在[串流輸入模式](https://code.claude.com/docs/zh-TW/agent-sdk/streaming-vs-single-mode.md)中，一個 `query()` 呼叫會進行多個使用者回合，每個回合都會發出自己的結果訊息。結果欄位的範圍不同：

* **`usage`**：僅涵蓋該回合，且在其中僅涵蓋主代理迴圈，不包括它執行的任何子代理。
* **`total_cost_usd` 和 `modelUsage`，或 Python 中的 `model_usage`**：攜帶迄今為止整個呼叫的執行總計，加上呼叫恢復工作階段時復原的任何支出。

在您的應用程式從不傳送 `/clear`、`/reset` 或 `/new` 的呼叫中，讀取最新結果以取得呼叫總計，而不是跨結果求和。

執行總計在您的應用程式每次傳送這三個命令之一時重新開始，在 `query()` 呼叫內，沒有其他東西會重設它們。三個結果對您的會計很重要：

* **`/clear` 回合自己的結果**：僅涵蓋自重設以來執行的內容，並攜帶新的 `session_id`。
* **之後的每個結果**：從該重設開始繼續計數。
* **每個 `/clear` 之前的最後結果**：保持自上一次重設以來的回合總計。

若要計算整個呼叫的總計，請將每個 `/clear` 之前的最後結果加上呼叫的最終結果。所有其他結果（包括 `/clear` 回合自己的結果）都被後續結果取代。

在 TypeScript 中，SDK 也會在每次重設時發出 [`SDKConversationResetMessage`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#sdkconversationresetmessage)，因此您可以從串流中偵測重設。在 Python 中，SDK 同樣會發出 `ConversationResetMessage`。在 Python SDK v0.2.137 之前，Python 迭代器會捨棄該訊息，因此在這些版本上，請從您的應用程式傳送的 `/clear` 回合自行計數重設。

`maxBudgetUsd`（TypeScript）或 `max_budget_usd`（Python）僅計算呼叫自身的支出：從恢復的工作階段復原的總計不計入其中，`/clear` 會重新開始預算。

## 取得查詢的總成本

結果訊息在 TypeScript 中被型別化為 [`SDKResultMessage`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#sdkresultmessage)，在 Python 中被型別化為 [`ResultMessage`](https://code.claude.com/docs/zh-TW/agent-sdk/python#resultmessage)，標記了 `query()` 呼叫的代理程式迴圈結束。它包含 `total_cost_usd`，即該呼叫中所有步驟的累積估計成本。恢復工作階段的呼叫也會計算工作階段的早期支出。讀取該值時適用兩項注意事項：

* 在 Python 中，該欄位被型別化為選用的，因此在讀取之前請檢查它不是 `None`。
* 成功和錯誤結果都會帶有它，儘管[工作階段當機](#recover-totals-after-a-session-crash)的最終結果可能會帶有零值。

在串流輸入模式中，按照[在串流輸入模式中追蹤成本](#track-costs-in-streaming-input-mode)中的說明讀取呼叫總計。

當代理程式產生[子代理程式](https://code.claude.com/docs/zh-TW/agent-sdk/subagents.md)時，三個結果層級欄位在計算內容上有所不同。使用 `modelUsage`，或在 Python 中使用 `model_usage`，進行整個樹狀結構的權杖計算；`usage` 欄位一旦發生巢狀就會低估。

| 欄位 | 子代理程式活動 |
| - | - |
| `usage` | 已排除。僅計算頂層代理程式迴圈，因此子代理程式內消耗的權杖不會被新增 |
| `total_cost_usd` | 已包含。計算子代理程式請求以及頂層迴圈 |
| `modelUsage` / `model_usage` | 已包含。計算子代理程式請求以及頂層迴圈，按模型細分 |

在[單一訊息輸入模式](https://code.claude.com/docs/zh-TW/agent-sdk/streaming-vs-single-mode.md#single-message-input)中，當背景子代理程式在最後一個回合結束時仍在執行時，Claude Code 會等待它們，直到[在結束時的背景工作](https://code.claude.com/docs/zh-TW/headless.md#background-tasks-at-exit)中描述的上限，然後才發出結果。結果的 `total_cost_usd`、`duration_api_ms` 和 `modelUsage`，或在 Python 中的 `model_usage`，包括在該等待期間完成的工作。

以下範例會逐一查看來自 `query()` 呼叫的訊息串流，並在 `result` 訊息到達時列印總成本：

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

try {
  for await (const message of query({ prompt: "Summarize this project" })) {
    if (message.type === "result") {
      console.log(`Total cost: $${message.total_cost_usd}`);
    }
  }
} catch (error) {
  // A single-shot query() throws after yielding an error result. If the
  // failure was an error result, it still carried total_cost_usd and the
  // branch above has already run; connection or process failures yield
  // no result message.
  console.error(`Session ended with an error: ${error}`);
}
```

```python Python theme={null}
from claude_agent_sdk import query, ResultMessage
import asyncio


async def main():
    try:
        async for message in query(prompt="Summarize this project"):
            if isinstance(message, ResultMessage):
                print(f"Total cost: ${message.total_cost_usd or 0}")
    except Exception as error:
        # A single-shot query() raises after yielding an error result. If the
        # failure was an error result, the branch above has already run;
        # connection or process failures yield no result message.
        print(f"Session ended with an error: {error}")


asyncio.run(main())
```

若要限制子代理程式可以新增到 `total_cost_usd` 的金額，請在查詢上設定[深度、並行性和支出限制](https://code.claude.com/docs/zh-TW/agent-sdk/subagents.md#cap-subagent-depth-concurrency-and-spend)。

## 追蹤每個步驟和每個模型的使用情況

本節中的範例使用 TypeScript 欄位名稱。在 Python 中，對應的欄位是 [`AssistantMessage.usage`](https://code.claude.com/docs/zh-TW/agent-sdk/python#assistantmessage) 和 `AssistantMessage.message_id` 用於每個步驟的使用情況，以及 [`ResultMessage.model_usage`](https://code.claude.com/docs/zh-TW/agent-sdk/python#resultmessage) 用於每個模型的細目。

### 追蹤每個步驟的使用情況

每個助手訊息都包含一個巢狀的 `BetaMessage`（透過 `message.message` 存取），其中包含 `id` 和具有權杖計數的 `usage` 物件。當 Claude 並行使用工具時，多個訊息共享相同的 `id` 和相同的使用資料。追蹤您已經計算過的 ID，並跳過重複項以避免總數膨脹。

> [!WARNING]
>
> 去重複後的每個步驟值對於輸入和快取權杖是準確的。每個步驟的 `output_tokens` 是預留位置，因此請[從結果訊息讀取輸出權杖](#read-output-tokens-from-the-result-message)。

以下範例累積所有步驟中的輸入權杖，只計算一次每個唯一的主迴圈訊息 ID 並跳過子代理訊息，並從結果訊息讀取輸出總計，該訊息涵蓋主迴圈：

```typescript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

const seenIds = new Set<string>();
let totalInputTokens = 0;
let resultOutputTokens = 0;

try {
  for await (const message of query({ prompt: "Summarize this project" })) {
    if (message.type === "assistant" && !message.parent_tool_use_id) {
      const msgId = message.message.id;

      // Parallel tool calls share the same ID, only count once
      if (!seenIds.has(msgId)) {
        seenIds.add(msgId);
        totalInputTokens += message.message.usage.input_tokens;
      }
    }
    if (message.type === "result") {
      // Per-step output_tokens is a placeholder; the result message
      // carries the accumulated output total.
      resultOutputTokens = message.usage.output_tokens;
    }
  }
} catch (error) {
  // A single-shot query() throws after yielding an error result, so the
  // input total below still reflects the steps that ran before the failure.
  console.error(`Session ended with an error: ${error}`);
}

console.log(`Steps: ${seenIds.size}`);
console.log(`Input tokens: ${totalInputTokens}`);
console.log(`Output tokens: ${resultOutputTokens}`);
```

### 按模型細分使用情況

結果訊息包含 [`modelUsage`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#modelusage)，這是模型名稱到每個模型權杖計數和成本的對應。當您執行多個模型（例如，子代理使用 Haiku，主代理使用 Opus）並想查看權杖流向何處時，這很有用。

每個項目的 `costBasis` 說明哪個價格表為該模型的最新請求定價：`list` 表示清單價格，`managed` 表示 [`modelPricing`](https://code.claude.com/docs/zh-TW/settings-reference#modelpricing) 表，或 `unknown` 表示兩者都不符合模型 ID。該欄位需要 Claude Code v2.1.246 或更新版本。

以下範例執行查詢並列印每個使用的模型的成本和權杖細目：

```typescript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

try {
  for await (const message of query({ prompt: "Summarize this project" })) {
    if (message.type !== "result") continue;

    for (const [modelName, usage] of Object.entries(message.modelUsage)) {
      console.log(`${modelName}: $${usage.costUSD.toFixed(4)}`);
      console.log(`  Input tokens: ${usage.inputTokens}`);
      console.log(`  Output tokens: ${usage.outputTokens}`);
      console.log(`  Cache read: ${usage.cacheReadInputTokens}`);
      console.log(`  Cache creation: ${usage.cacheCreationInputTokens}`);
    }
  }
} catch (error) {
  // A single-shot query() throws after yielding an error result. If the
  // failure was an error result, the per-model breakdown above has already
  // printed; connection or process failures yield no result message.
  console.error(`Session ended with an error: ${error}`);
}
```

## 累積多次呼叫的成本

每個 `query()` 呼叫都會在其結果上傳回 `total_cost_usd`。您如何合併這些值取決於呼叫是否共享工作階段：

* **獨立呼叫，沒有 `resume` 或 `continue` 選項**：每個結果只涵蓋其自己的呼叫，因此請自行加總，如下面的範例所示。
* **恢復相同工作階段的呼叫**：Claude Code 會在程序正常退出時將工作階段的總計儲存到其[文字記錄](https://code.claude.com/docs/zh-TW/sessions.md#where-transcripts-are-stored)，並在稍後的呼叫恢復或分叉工作階段時復原它們。每個結果已經包含工作階段的早期支出。讀取工作階段的最新結果以取得工作階段總計；加總結果會重複計算已復原的支出。在 v2.1.277 之前，您透過 SDK 或 `claude -p` 恢復的工作階段會將其總計從零開始，因此每個呼叫的結果只涵蓋該呼叫。

無論哪種方式，合併後的數字仍然是[用戶端估算值](#estimates-not-billing)。

在串流輸入模式中，如 [在串流輸入模式中追蹤成本](#track-costs-in-streaming-input-mode) 中所述讀取每個呼叫的總計。對於以當機結束的呼叫，請參閱 [在工作階段當機後復原總計](#recover-totals-after-a-session-crash)。

以下範例依序執行兩個 `query()` 呼叫，將每個呼叫的 `total_cost_usd` 加入執行中的總計，並列印每次呼叫和合併的成本：

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

// Track cumulative cost across multiple query() calls
let totalSpend = 0;

const prompts = [
  "Read the files in src/ and summarize the architecture",
  "List all exported functions in src/auth.ts"
];

for (const prompt of prompts) {
  try {
    for await (const message of query({ prompt })) {
      if (message.type === "result") {
        totalSpend += message.total_cost_usd;
        console.log(`This call: $${message.total_cost_usd}`);
      }
    }
  } catch (error) {
    // A single-shot query() throws after yielding an error result. If the
    // failure was an error result, this call's cost was already counted;
    // connection or process failures yield no result message. Continue
    // with the next prompt.
    console.error(`Call failed: ${error}`);
  }
}

console.log(`Total spend: $${totalSpend.toFixed(4)}`);
```

```python Python theme={null}
from claude_agent_sdk import query, ResultMessage
import asyncio


async def main():
    # Track cumulative cost across multiple query() calls
    total_spend = 0.0

    prompts = [
        "Read the files in src/ and summarize the architecture",
        "List all exported functions in src/auth.ts",
    ]

    for prompt in prompts:
        try:
            async for message in query(prompt=prompt):
                if isinstance(message, ResultMessage):
                    cost = message.total_cost_usd or 0
                    total_spend += cost
                    print(f"This call: ${cost}")
        except Exception as error:
            # A single-shot query() raises after yielding an error result. If
            # the failure was an error result, this call's cost was already
            # counted; connection or process failures yield no result message.
            # Continue with the next prompt.
            print(f"Call failed: {error}")

    print(f"Total spend: ${total_spend:.4f}")


asyncio.run(main())
```

## 處理錯誤、快取和輸出 token 計數

為了準確追蹤成本，需要考慮助手訊息上的預留位置輸出計數、失敗對話消耗的 token，以及快取 token 定價。

### 從結果訊息讀取輸出 token

Claude Code 從 API 在回應開始時報告的使用量建立每個助手訊息，因此訊息的 `output_tokens` 只是 API 在 `message_start` 時報告的計數，在回應生成之前。一個 API 回應可以產生多個助手訊息，每一個都帶有相同的預留位置。

API 在回應結束時報告實際輸出計數，Claude Code 將其新增到結果訊息。從結果的 `usage` 讀取輸出 token，或從 `modelUsage` 讀取每個模型的細目。

若要在串流時監看回應的輸出計數增長，請設定 `includePartialMessages`，或在 Python 中設定 `include_partial_messages`，並從每個 `message_delta` 串流事件讀取 `usage`，在 TypeScript 中型別為 [`SDKPartialAssistantMessage`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#sdkpartialassistantmessage)，在 Python 中型別為 [`StreamEvent`](https://code.claude.com/docs/zh-TW/agent-sdk/python#streamevent)。

### 追蹤失敗對話的成本

成功和錯誤結果訊息都包含 `usage` 和 `total_cost_usd`；在 Python 中兩個欄位都型別為選用，因此在讀取之前請檢查它們不是 `None`。

如果對話在中途失敗，您仍然消耗了到失敗點為止的 token。從每個結果訊息讀取成本資料，無論其 `subtype` 是 `success` 還是其中一個錯誤子型別。在某些錯誤結果上，`usage` 報告的少於呼叫花費的：

* **`error_during_execution` 在 [工作階段當機](#recover-totals-after-a-session-crash) 之後**：每個成本欄位可能被清零。
* **`error_max_budget_usd`**：`usage` 遺漏了超過預算的回應，而 `total_cost_usd` 和 `modelUsage` 包含它。

在有選擇的地方，從 `total_cost_usd` 或 `modelUsage` 而不是 `usage` 進行計帳。

### 在工作階段當機後復原總計

當 Claude Code 程序當機時，它會發出最終的 `error_during_execution` 結果並退出，在單次和串流輸入模式中都是如此。該結果可能帶有清零的 `usage`、`total_cost_usd` 和 `modelUsage`，因此從它之前到達的內容復原呼叫的總計。步驟 1 在存在較早結果時復原完整總計；步驟 2 中的備用方案只復原主迴圈的輸入和快取 token。

1. 使用當機前轉換的結果。在串流輸入模式中，它保持自呼叫開始或自上次 [`/clear`](#track-costs-in-streaming-input-mode) 以來的執行總計。當該結果無法幫助您時，改為進行步驟 2：
   * 呼叫是單次的，因此不存在較早的結果。
   * 當機發生在第一個轉換上。
   * 當機前的轉換是 `/clear` 本身，因此其結果只涵蓋重設。
2. 改為對助手訊息上的 `usage` 求和，計算每個 API 回應一次，如 [追蹤每步驟使用量](#track-per-step-usage) 範例所做。在單次模式中，對所有進行求和；在串流輸入模式中，對最後一個結果之後到達的進行求和。這給您主迴圈的輸入和快取 token。子代理使用量無法以這種方式復原，輸出 token 或美元成本也無法，因為 [每步驟 `output_tokens` 是預留位置](#read-output-tokens-from-the-result-message)。

### 追蹤快取 token

Agent SDK 自動使用 [prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) 來降低重複內容的成本。您不需要自己設定快取。使用量物件包含兩個額外的欄位用於快取追蹤：

* `cache_creation_input_tokens`：用於建立新快取項目的 token（以高於標準輸入 token 的費率計費）。
* `cache_read_input_tokens`：從現有快取項目讀取的 token（以降低的費率計費）。

將這些與 `input_tokens` 分開追蹤，以了解快取節省。在 TypeScript 中，這些欄位在 [`Usage`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#usage) 物件上型別化。在 Python 中，它們作為 [`ResultMessage.usage`](https://code.claude.com/docs/zh-TW/agent-sdk/python#resultmessage) 字典中的鍵出現（例如，`message.usage.get("cache_read_input_tokens", 0)`）。

### 將 prompt 快取 TTL 延長至一小時

您自己的轉換落在 [主對話 TTL 值區](https://code.claude.com/docs/zh-TW/prompt-caching.md#which-ttl-each-request-gets) 中，與 Claude Code 與它們內聯執行的協助程式一起。Claude Code 在該對話之外進行的請求，例如 [子代理](https://code.claude.com/docs/zh-TW/agent-sdk/subagents.md)，有 [單獨的 TTL 控制](https://code.claude.com/docs/zh-TW/prompt-caching.md#choose-the-ttl-yourself)。

當您使用 API 金鑰進行驗證或在 Amazon Bedrock、Google Cloud 的 Agent Platform、Microsoft Foundry 或 [AWS 上的 Claude Platform](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md) 上執行時，您自己的轉換的快取項目預設使用 5 分鐘 TTL。如果您的工作負載針對相同的系統提示和內容執行許多短工作階段，且它們之間的間隔超過 5 分鐘，快取會在工作階段之間過期，每個新工作階段都支付完整輸入價格。

若要在快取寫入上請求 1 小時 TTL，請設定 [`ENABLE_PROMPT_CACHING_1H`](https://code.claude.com/docs/zh-TW/env-vars) 環境變數。您可以在您的 shell 或容器環境中匯出它，或通過 `options.env` 傳遞它。

以下範例為在 Amazon Bedrock 上執行的代理啟用 1 小時 TTL。因為它設定了 `CLAUDE_CODE_USE_BEDROCK`，它需要 [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md) 的有效 AWS 認證；沒有它們查詢會失敗。

```python Python theme={null}
from claude_agent_sdk import ClaudeAgentOptions, query
import asyncio


async def main():
    options = ClaudeAgentOptions(
        env={
            "CLAUDE_CODE_USE_BEDROCK": "1",
            "ENABLE_PROMPT_CACHING_1H": "1",
        },
    )

    async for message in query(prompt="Summarize this project", options=options):
        print(message)


asyncio.run(main())
```

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

const options = {
  env: {
    ...process.env,
    CLAUDE_CODE_USE_BEDROCK: "1",
    ENABLE_PROMPT_CACHING_1H: "1",
  },
};

for await (const message of query({ prompt: "Summarize this project", options })) {
  console.log(message);
}
```

具有 1 小時 TTL 的快取寫入以高於 5 分鐘寫入的費率計費，因此啟用此功能會以更高的寫入成本換取更多快取讀取。有關詳細資訊，請參閱 [prompt caching 定價](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)。在您計畫內包含的使用量內的 Claude 訂閱上，您在自己的轉換上獲得 1 小時 TTL，以及在 Claude Code 在它們旁邊進行的某些協助程式請求上，無需設定此變數，一旦您開始使用 [使用量點數](https://support.claude.com/en/articles/12429409-extra-usage-for-paid-claude-plans)，Claude Code 會將這些轉換降低到 5 分鐘 TTL。

`ENABLE_PROMPT_CACHING_1H` 要求在兩個值區中的每個請求上使用 1 小時 TTL。若要為每個值區分別選擇 TTL，請改為使用這些控制。每個採用 `5m` 或 `1h` 並優先於 `ENABLE_PROMPT_CACHING_1H`：

* 主對話：`CLAUDE_CODE_PROMPT_CACHE_TTL` [環境變數](https://code.claude.com/docs/zh-TW/env-vars.md)，或 [`promptCacheTtl`](https://code.claude.com/docs/zh-TW/settings-reference#promptcachettl) 設定
* 其他所有內容：`CLAUDE_CODE_SUBAGENT_PROMPT_CACHE_TTL` 環境變數，或 [`subagentPromptCacheTtl`](https://code.claude.com/docs/zh-TW/settings-reference#subagentpromptcachettl) 設定

將 `promptCacheTtl` 設定為 `1h` 會在您使用使用量點數時保持主對話上的 1 小時快取。有關完整優先順序，請參閱 [選擇 TTL](https://code.claude.com/docs/zh-TW/prompt-caching.md#choose-the-ttl-yourself)。

## 相關文件

* [TypeScript SDK 參考](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md) - 完整的 API 文件
* [SDK 概述](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) - SDK 入門
* [SDK 權限](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md) - 管理工具權限

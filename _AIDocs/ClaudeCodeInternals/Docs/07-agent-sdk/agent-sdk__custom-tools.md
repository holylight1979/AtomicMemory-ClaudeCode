<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/agent-sdk/custom-tools | lastmod: 2026-10-26 | section: Agent SDK / Extend with tools -->
> 來源：https://code.claude.com/docs/zh-TW/agent-sdk/custom-tools（官方 zh-TW，lastmod 2026-10-26）｜分類：Agent SDK › Extend with tools｜EN 摘要：Define custom tools with the Claude Agent SDK's in-process MCP server so Claude can call your functions, hit your APIs, and perform domain-specific operations.

# 為 Claude 提供自訂工具

> 使用 Claude Agent SDK 的同程序 MCP 伺服器定義自訂工具，讓 Claude 可以呼叫您的函數、存取您的 API，並執行特定領域的操作。

自訂工具透過讓您定義 Claude 在對話期間可以呼叫的自己的函數來擴展 Agent SDK。使用 SDK 的同程序 MCP 伺服器，您可以讓 Claude 存取資料庫、外部 API、特定領域邏輯或應用程式需要的任何其他功能。

## 快速參考

| 如果您想要... | 執行此操作 |
| :- | :- |
| 定義工具 | 使用 [`@tool`](https://code.claude.com/docs/zh-TW/agent-sdk/python#tool)（Python）或 [`tool()`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#tool)（TypeScript），搭配名稱、描述、結構描述和處理程式。請參閱[建立自訂工具](#create-a-custom-tool)。 |
| 將參數設為選用 | 在 schema 中將其宣告為選用，並在處理程式中套用預設值。請參閱[將參數設為選用](#make-a-parameter-optional)。 |
| 向 Claude 註冊工具 | 在 `create_sdk_mcp_server` / `createSdkMcpServer` 中包裝，並傳遞至 `query()` 中的 `mcpServers`。請參閱[呼叫自訂工具](#call-a-custom-tool)。 |
| 預先核准工具 | 新增至您允許的工具。請參閱[設定允許的工具](#configure-allowed-tools)。 |
| 要求呼叫某個工具時須經核准，或封鎖該工具 | 在 TypeScript SDK 中，將該工具的 `permission_policy` 新增至 `createSdkMcpServer()` 傳回的設定物件。請參閱[要求特定工具須經核准](#require-approval-for-specific-tools)。 |
| 從 Claude 的內容中移除內建工具 | 傳遞 `tools` 陣列，僅列出您想要的內建工具。請參閱[設定允許的工具](#configure-allowed-tools)。 |
| 讓 Claude 平行呼叫工具 | 在沒有副作用的工具上設定 `readOnlyHint: true`。請參閱[新增工具註解](#add-tool-annotations)。 |
| 控制 Claude 讀取的錯誤訊息 | 傳回 `isError: true` 以組成訊息，而不是顯示原始例外狀況。請參閱[處理錯誤](#handle-errors)。 |
| 傳回影像或檔案 | 在內容陣列中使用 `image` 或 `resource` 區塊。請參閱[傳回影像和資源](#return-images-and-resources)。 |
| 傳回機器可讀的 JSON 結果 | 在結果上設定 `structuredContent`。請參閱[傳回結構化資料](#return-structured-data)。 |
| 擴展到許多工具 | 使用[工具搜尋](https://code.claude.com/docs/zh-TW/agent-sdk/tool-search.md)按需載入工具。 |

## 建立自訂工具

工具由四個部分定義，作為引數傳遞給 TypeScript 中的 [`tool()`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#tool) 輔助函式或 Python 中的 [`@tool`](https://code.claude.com/docs/zh-TW/agent-sdk/python#tool) 裝飾器：

* **名稱：** Claude 用來呼叫工具的唯一識別碼。
* **描述：** 工具的功能。Claude 讀取此項以決定何時呼叫它。
* **輸入 schema：** 工具接受的引數，依語言宣告：
  * **TypeScript**：[Zod schema](https://zod.dev/)。處理程式的 `args` 會從中取得其類型。在欄位上呼叫 `.describe()`，即可為其提供 Claude 看得到的描述。
  * **Python**：將名稱對應到類型的字典，例如 `{"latitude": float}`，SDK 會為您將其轉換為 JSON Schema。將類型包裝在 `Annotated` 中，例如 `{"latitude": Annotated[float, "Latitude coordinate"]}`，即可為欄位提供 Claude 看得到的描述。當您需要列舉、範圍、選用欄位或巢狀物件時，裝飾器也可直接接受完整的 [JSON Schema](https://json-schema.org/understanding-json-schema/about) 字典。
* **處理程式：** Claude 呼叫工具時執行的非同步函式。它接收已驗證的引數，並且必須傳回包含以下內容的物件：
  * `content`（必需）：結果區塊的陣列，每個區塊的 `type` 為 `"text"`、`"image"`、`"audio"`、`"resource"` 或 `"resource_link"`。請參閱[傳回影像和資源](#return-images-and-resources)以了解非文字區塊。
  * `structuredContent`（選用）：保存結果作為機器可讀資料的 JSON 物件，與 `content` 一起傳回。請參閱[傳回結構化資料](#return-structured-data)。
  * `isError`（選用）：設定為 `true` 以表示工具失敗，以便 Claude 可以對其做出反應。請參閱[處理錯誤](#handle-errors)。

定義工具後，使用 [`createSdkMcpServer`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#createsdkmcpserver)（TypeScript）或 [`create_sdk_mcp_server`](https://code.claude.com/docs/zh-TW/agent-sdk/python#create_sdk_mcp_server)（Python）將其包裝在伺服器中。伺服器在應用程式內部以同步程序執行，而不是作為單獨的程序。

本頁中發出 HTTP 請求的 Python 範例使用 [httpx](https://www.python-httpx.org/)。請使用專案所用的套件管理工具新增它：

> [tab] Python (uv)
>
> ```bash theme={null}
> uv add httpx
> ```

> [tab] Python (pip)
>
> ```bash theme={null}
> pip install httpx
> ```

### 天氣工具範例

此範例定義 `get_temperature` 工具並將其包裝在 MCP 伺服器中，但不將伺服器傳遞給 `query`。若要執行工具，請參閱下面的[呼叫自訂工具](#call-a-custom-tool)。

```python Python theme={null}
from typing import Annotated, Any
import httpx
from claude_agent_sdk import tool, create_sdk_mcp_server


# Define a tool: name, description, input schema, handler
@tool(
    "get_temperature",
    "Get the current temperature at a location",
    {
        "latitude": Annotated[float, "Latitude coordinate"],
        "longitude": Annotated[float, "Longitude coordinate"],
    },
)
async def get_temperature(args: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": args["latitude"],
                "longitude": args["longitude"],
                "current": "temperature_2m",
                "temperature_unit": "fahrenheit",
            },
        )
        data = response.json()

    # Return a content array - Claude sees this as the tool result
    return {
        "content": [
            {
                "type": "text",
                "text": f"Temperature: {data['current']['temperature_2m']}°F",
            }
        ]
    }


# Wrap the tool in an in-process MCP server
weather_server = create_sdk_mcp_server(
    name="weather",
    version="1.0.0",
    tools=[get_temperature],
)
```

```typescript TypeScript theme={null}
import { tool, createSdkMcpServer } from "@anthropic-ai/claude-agent-sdk";
import { z } from "zod";

// Define a tool: name, description, input schema, handler
const getTemperature = tool(
  "get_temperature",
  "Get the current temperature at a location",
  {
    latitude: z.number().describe("Latitude coordinate"), // .describe() adds a field description Claude sees
    longitude: z.number().describe("Longitude coordinate")
  },
  async (args) => {
    // args is typed from the schema: { latitude: number; longitude: number }
    const response = await fetch(
      `https://api.open-meteo.com/v1/forecast?latitude=${args.latitude}&longitude=${args.longitude}&current=temperature_2m&temperature_unit=fahrenheit`
    );
    const data: any = await response.json();

    // Return a content array - Claude sees this as the tool result
    return {
      content: [{ type: "text", text: `Temperature: ${data.current.temperature_2m}°F` }]
    };
  }
);

// Wrap the tool in an in-process MCP server
const weatherServer = createSdkMcpServer({
  name: "weather",
  version: "1.0.0",
  tools: [getTemperature]
});
```

請參閱 [`tool()`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#tool) TypeScript 參考或 [`@tool`](https://code.claude.com/docs/zh-TW/agent-sdk/python#tool) Python 參考以取得完整的參數詳細資訊，包括 JSON 綱要輸入格式和傳回值結構。

### 將參數設為選用

若要將參數設為選用，請在 schema 中將其宣告為選用，並在處理程式中套用預設值：

* **TypeScript**：將 `.optional()` 新增至 Zod 欄位。
* **Python**：字典 schema 要求每個鍵都必須提供。請使用 JSON Schema 形式，將該參數排除在 `required` 之外，並使用 `args.get()` 讀取它。若要使用具有選用鍵的型別化 schema，請參閱 [TypedDict 類別](https://code.claude.com/docs/zh-TW/agent-sdk/python.md#input-schema-options)。

[下面的 `get_precipitation_chance` 工具](#add-more-tools)顯示兩種模式。

### 呼叫自訂工具

透過 `mcpServers` 選項將您建立的 MCP 伺服器傳遞給 `query`，並在 `allowedTools` 中列出每個工具的[完全限定名稱](https://code.claude.com/docs/zh-TW/agent-sdk/mcp.md#tool-naming-convention)，以便工具執行時不會出現權限提示。該名稱為 `mcp__{server_name}__{tool_name}`，其中 `{server_name}` 是您在 `mcpServers` 中為伺服器指定的鍵。如果該鍵包含 `.` 或空格等字元，撰寫 `{server_name}` 時請將其替換為 `_`。

這些程式碼片段重複使用[天氣工具範例](#weather-tool-example)中的 `weatherServer` 來詢問 Claude 特定位置的天氣。

```python Python theme={null}
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage


async def main():
    options = ClaudeAgentOptions(
        mcp_servers={"weather": weather_server},
        allowed_tools=["mcp__weather__get_temperature"],
    )

    async for message in query(
        prompt="What's the temperature in San Francisco?",
        options=options,
    ):
        # ResultMessage is the final message after all tool calls complete
        if isinstance(message, ResultMessage) and message.subtype == "success":
            print(message.result)


asyncio.run(main())
```

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  prompt: "What's the temperature in San Francisco?",
  options: {
    mcpServers: { weather: weatherServer },
    allowedTools: ["mcp__weather__get_temperature"]
  }
})) {
  // "result" is the final message after all tool calls complete
  if (message.type === "result" && message.subtype === "success") {
    console.log(message.result);
  }
}
```

將此程式碼片段與[天氣工具範例](#weather-tool-example)中的工具和伺服器定義結合在一個檔案 `weather.py` 或 `weather.ts` 中，然後從終端機執行它：

> [tab] TypeScript
>
> ```bash theme={null}
> npx tsx weather.ts
> ```

> [tab] Python (uv)
>
> ```bash theme={null}
> uv run weather.py
> ```

> [tab] Python (pip)
>
> 啟用您安裝 SDK 的虛擬環境，然後執行：
>
> ```bash theme={null}
> python weather.py
> ```

Claude 呼叫 `get_temperature`，指令碼會列印一行答案，顯示舊金山目前的溫度。

### 新增更多工具

伺服器在其 `tools` 陣列中列出的工具數量不限。當伺服器上有多個工具時，您可以在 `allowedTools` 中個別列出每個工具，或使用萬用字元 `mcp__weather__*` 來涵蓋伺服器公開的每個工具。

下面的範例定義第二個工具 `get_precipitation_chance`，並將[天氣工具範例](#weather-tool-example)中的 `weatherServer` 定義替換為在陣列中列出兩個工具的定義。

```python Python theme={null}
# Define a second tool for the same server
@tool(
    "get_precipitation_chance",
    "Get the hourly precipitation probability for a location",
    {
        "type": "object",
        "properties": {
            "latitude": {"type": "number"},
            "longitude": {"type": "number"},
            "hours": {
                "type": "integer",
                "minimum": 1,
                "maximum": 24,
                "description": "How many hours of forecast to return",
            },
        },
        # 'hours' is left out of required, so Claude can omit it
        "required": ["latitude", "longitude"],
    },
)
async def get_precipitation_chance(args: dict[str, Any]) -> dict[str, Any]:
    # 'hours' isn't in required - read it with .get() to fall back to a default
    hours = args.get("hours", 12)
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": args["latitude"],
                "longitude": args["longitude"],
                "hourly": "precipitation_probability",
                "forecast_days": 1,
            },
        )
        data = response.json()
    chances = data["hourly"]["precipitation_probability"][:hours]

    return {
        "content": [
            {
                "type": "text",
                "text": f"Next {hours} hours: {'%, '.join(map(str, chances))}%",
            }
        ]
    }


# Rebuild the server with both tools in the array
weather_server = create_sdk_mcp_server(
    name="weather",
    version="1.0.0",
    tools=[get_temperature, get_precipitation_chance],
)
```

```typescript TypeScript theme={null}
// Define a second tool for the same server
const getPrecipitationChance = tool(
  "get_precipitation_chance",
  "Get the hourly precipitation probability for a location",
  {
    latitude: z.number(),
    longitude: z.number(),
    hours: z
      .number()
      .int()
      .min(1)
      .max(24)
      .optional() // .optional() lets Claude omit the parameter
      .describe("How many hours of forecast to return")
  },
  async (args) => {
    const hours = args.hours ?? 12; // Apply the default in the handler
    const response = await fetch(
      `https://api.open-meteo.com/v1/forecast?latitude=${args.latitude}&longitude=${args.longitude}&hourly=precipitation_probability&forecast_days=1`
    );
    const data: any = await response.json();
    const chances = data.hourly.precipitation_probability.slice(0, hours);

    return {
      content: [{ type: "text", text: `Next ${hours} hours: ${chances.join("%, ")}%` }]
    };
  }
);

// Rebuild the server with both tools in the array
const weatherServer = createSdkMcpServer({
  name: "weather",
  version: "1.0.0",
  tools: [getTemperature, getPrecipitationChance]
});
```

[工具搜尋](https://code.claude.com/docs/zh-TW/agent-sdk/tool-search.md)預設為開啟，並延遲 SDK MCP 工具：Claude 在精簡清單中看到每個工具的名稱，並按需載入其完整綱要。停用工具搜尋後，此陣列中的每個工具在每個回合都會消耗內容視窗空間。在 TypeScript 中，在 [`tool()`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#tool) 的 `extras` 引數或 [`createSdkMcpServer()`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#createsdkmcpserver) 的選項中傳遞 `alwaysLoad: true`，以在初始提示中保留工具的完整綱要。

### 新增工具註釋

[工具註釋](https://modelcontextprotocol.io/docs/concepts/tools#tool-annotations)是描述工具行為方式的選用中繼資料。在 TypeScript 中將它們作為 `tool()` 輔助函式的第五個引數傳遞，或在 Python 中透過 `@tool` 裝飾器的 `annotations` 關鍵字引數傳遞。所有提示欄位都是布林值。

| 欄位 | 預設 | 意義 |
| :- | :- | :- |
| `readOnlyHint` | `false` | 工具不會修改其環境。控制工具是否可以與其他唯讀工具並行呼叫。 |
| `destructiveHint` | `true` | 工具可能執行破壞性更新。對於任何您[標記為 `always_ask`](#require-approval-for-specific-tools) 的工具，請明確將其設定為 `true`。 |
| `idempotentHint` | `false` | 使用相同引數重複呼叫沒有額外效果。僅供參考。 |
| `openWorldHint` | `true` | 工具到達您程序外的系統。僅供參考。 |

註釋是中繼資料，不是強制執行。標記為 `readOnlyHint: true` 的工具如果處理程式執行該操作，仍然可以寫入磁碟。保持註釋與處理程式準確。

此範例將 `readOnlyHint` 新增至[天氣工具範例](#weather-tool-example)中的 `get_temperature` 工具。

```python Python theme={null}
from claude_agent_sdk import tool, ToolAnnotations


@tool(
    "get_temperature",
    "Get the current temperature at a location",
    {"latitude": float, "longitude": float},
    annotations=ToolAnnotations(
        readOnlyHint=True
    ),  # Lets Claude batch this with other read-only calls
)
async def get_temperature(args):
    return {"content": [{"type": "text", "text": "..."}]}
```

```typescript TypeScript theme={null}
import { tool } from "@anthropic-ai/claude-agent-sdk";
import { z } from "zod";

tool(
  "get_temperature",
  "Get the current temperature at a location",
  { latitude: z.number(), longitude: z.number() },
  async (args) => ({ content: [{ type: "text", text: `...` }] }),
  { annotations: { readOnlyHint: true } } // Lets Claude batch this with other read-only calls
);
```

請參閱 [TypeScript](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md#toolannotations) 或 [Python](https://code.claude.com/docs/zh-TW/agent-sdk/python.md#toolannotations) 參考中的 `ToolAnnotations`。

## 控制工具存取

[天氣工具範例](#weather-tool-example)註冊了伺服器並在 `allowedTools` 中列出工具。本節涵蓋當您有多個工具或想要限制內建工具時如何限制存取範圍。如需了解工具名稱的構成方式，請參閱[呼叫自訂工具](#call-a-custom-tool)。

### 設定允許的工具

`tools` 選項和允許/不允許清單會影響兩個層級：可用性（控制工具是否出現在 Claude 的上下文中）和權限（控制 Claude 嘗試呼叫後是否獲得批准）。`tools` 和裸名稱 `disallowedTools` 項目會變更可用性。`allowedTools` 和限定範圍的 `disallowedTools` 規則會變更權限。如果您在 `allowedTools` 中命名其中一個[任務追蹤工具](https://code.claude.com/docs/zh-TW/agent-sdk/todo-tracking.md#model-availability)，Claude Code 也會為該工作階段啟用這些工具。

| 選項 | 層級 | 效果 |
| :- | :- | :- |
| `tools: ["Read", "Grep"]` | 可用性 | 只有列出的內建工具在 Claude 的上下文中。未列出的內建工具會被移除。MCP 工具不受影響。 |
| `tools: []` | 可用性 | 所有內建工具都會被移除。Claude 只能使用您的 MCP 工具。 |
| 允許的工具 | 權限 | 列出的工具無需權限提示即可執行。其他未列出的工具仍然可用；呼叫會通過[權限流程](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md)。 |
| 不允許的工具 | 兩者 | 裸工具名稱（例如 `"Bash"`）會從 Claude 的上下文中移除工具，與從 `tools` 中省略它的效果相同。限定範圍的規則（例如 `"Bash(rm *)"`）會將工具保留在上下文中，並僅拒絕與[如所寫](https://code.claude.com/docs/zh-TW/permissions.md#bash-rule-limits)相符的呼叫。 |

若要完全移除內建工具，請從 `tools` 中省略它或在 `disallowedTools` 中列出其裸名稱（Python：`disallowed_tools`）；兩者都會將工具保留在上下文之外，以便 Claude 永遠不會嘗試它。限定範圍的 `disallowedTools` 規則會阻止相符的呼叫，但將工具保留為可見，因此 Claude 可能會浪費一個回合嘗試它。如需完整的評估順序，請參閱[設定權限](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md)。

### 要求特定工具的核准

將工具的 `permission_policy` 設為 `always_ask`，`allowedTools` 就不再核准該工具的呼叫，因此即使該工具已列出，這些呼叫仍可到達您的 [`canUseTool`](https://code.claude.com/docs/zh-TW/agent-sdk/user-input) 回呼。若改為設定 `always_deny`，[對該工具的呼叫會被拒絕](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#how-permissions-are-evaluated)，但您載入的外掛中的 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md) [仍可核准它](https://code.claude.com/docs/zh-TW/permissions.md#precedence-among-rules-hooks-and-mods)。此欄位僅適用於 TypeScript，且需要 Agent SDK v0.3.301 或更新版本。

請將政策項目放在 `createSdkMcpServer()` 傳回的設定物件上的 `tools` 陣列中，而不是放在您傳入該函式的 `tools` 選項中。此範例展開[天氣工具範例](#weather-tool-example)中的 `weatherServer`，並新增一個 `tools` 陣列，為 `get_temperature` 指定 `always_ask` 政策：

```typescript TypeScript theme={null}
options: {
  mcpServers: {
    weather: {
      ...weatherServer,
      tools: [{ name: "get_temperature", permission_policy: "always_ask" as const }]
    }
  },
  allowedTools: ["mcp__weather__get_temperature"],
  permissionMode: "default",
  canUseTool: async (toolName, input) => {
    console.log(`Approval requested for ${toolName}`);
    return { behavior: "allow", updatedInput: input };
  }
}
```

若要試用此政策，請將[呼叫自訂工具](#call-a-custom-tool)指令碼中的 `options` 替換為此範例的 `options`，然後從終端機執行該指令碼。指令碼會印出 `Approval requested for mcp__weather__get_temperature`，接著是 Claude 關於溫度的回答。如需完整的指令碼，請參閱 [TypeScript 參考](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md#mcpsdkserverconfigwithinstance)。

如果您使用 `auto` 或 `plan` [權限模式](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#permission-modes)，請在工具的[註解](#add-tool-annotations)中設定 `destructiveHint: true`，讓對該工具的呼叫仍會到達您的回呼。否則，[自動模式分類器](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)可能會在 [TypeScript 參考中列出的條件](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md#permission-modes-that-can-approve-an-always_ask-call)下核准某些 `always_ask` 呼叫，而它核准的呼叫不會到達您的回呼。請明確設定此提示，因為對於 `always_ask` 呼叫，未設定的 `destructiveHint` 會被視為 `false`，而不是預設為 `true`。

## 處理錯誤

處理程式錯誤不會停止代理迴圈。SDK 的同處理程序 MCP 伺服器會捕捉未捕捉的例外狀況，並將其作為錯誤結果返回，因此您報告錯誤的方式決定了 Claude 讀取的內容，而不是查詢是否失敗：

| 發生的情況 | 結果 |
| :- | :- |
| 處理程式拋出未捕捉的例外狀況 | MCP 伺服器將其轉換為攜帶原始例外狀況訊息的錯誤結果。Claude 看到該訊息，代理迴圈繼續。 |
| 處理程式捕捉錯誤並返回 `isError: true` (TS) / `"is_error": True` (Python) | Claude 看到您撰寫的訊息。您可以添加原始例外狀況缺乏的背景資訊，例如哪個請求失敗或應該嘗試什麼。 |

在這兩種情況下，Claude 都可以重試、嘗試不同的工具或解釋失敗。當原始例外狀況訊息不足以讓 Claude 採取行動時，請自行捕捉錯誤。

下面的範例在處理程式內捕捉兩種失敗，並撰寫 Claude 讀取的錯誤訊息。非 200 HTTP 狀態碼從回應中捕捉並作為錯誤結果返回。網路錯誤或無效的 JSON 由周圍的 `try/except` (Python) 或 `try/catch` (TypeScript) 捕捉，也作為錯誤結果返回。在這兩種情況下，Claude 都會收到描述失敗的訊息，而不是裸露的例外狀況字串。

```python Python theme={null}
import json
import httpx
from typing import Any
from claude_agent_sdk import tool


@tool(
    "fetch_data",
    "Fetch data from an API",
    {"endpoint": str},  # Simple schema
)
async def fetch_data(args: dict[str, Any]) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(args["endpoint"])
            if response.status_code != 200:
                # Return the failure as a tool result so Claude can react to it.
                # is_error marks this as a failed call rather than odd-looking data.
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"API error: {response.status_code} {response.reason_phrase}",
                        }
                    ],
                    "is_error": True,
                }

            data = response.json()
            return {"content": [{"type": "text", "text": json.dumps(data, indent=2)}]}
    except Exception as e:
        # Composes the message Claude reads. An uncaught exception would
        # reach Claude as the raw str(e) with no context.
        return {
            "content": [{"type": "text", "text": f"Failed to fetch data: {str(e)}"}],
            "is_error": True,
        }
```

```typescript TypeScript theme={null}
import { tool } from "@anthropic-ai/claude-agent-sdk";
import { z } from "zod";

tool(
  "fetch_data",
  "Fetch data from an API",
  {
    endpoint: z.string().url().describe("API endpoint URL")
  },
  async (args) => {
    try {
      const response = await fetch(args.endpoint);

      if (!response.ok) {
        // Return the failure as a tool result so Claude can react to it.
        // isError marks this as a failed call rather than odd-looking data.
        return {
          content: [
            {
              type: "text",
              text: `API error: ${response.status} ${response.statusText}`
            }
          ],
          isError: true
        };
      }

      const data = await response.json();
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(data, null, 2)
          }
        ]
      };
    } catch (error) {
      // Composes the message Claude reads. An uncaught throw would
      // reach Claude as the raw error message with no context.
      return {
        content: [
          {
            type: "text",
            text: `Failed to fetch data: ${error instanceof Error ? error.message : String(error)}`
          }
        ],
        isError: true
      };
    }
  }
);
```

## 返回影像和資源

工具結果中的 `content` 陣列接受 `text`、`image`、`audio`、`resource` 和 `resource_link` 區塊。您可以在同一個回應中混合使用它們。在 TypeScript 中，SDK 會將音訊區塊儲存到磁碟，Claude 會收到一個包含已儲存檔案路徑的文字區塊；在 Python 中，SDK 會從工具結果中移除音訊區塊並記錄警告。

Claude 會將每個資源連結區塊作為文字區塊接收，其中包含連結的名稱、URI 和描述。在 TypeScript 中，您的應用程式也會在使用者訊息的 `tool_use_result` 上以 [`resourceLinks`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#sdkmcpresourcelink) 的形式接收連結本身；在 Python 中，SDK 會在 CLI 看到結果之前將它們扁平化為文字，因此 Python [`resourceLinks` 鍵](https://code.claude.com/docs/zh-TW/agent-sdk/python#usermessage) 永遠不會針對程序內工具產生。

### 影像

影像區塊以 base64 編碼的方式內聯攜帶影像位元組。沒有 URL 欄位。若要返回位於 URL 的影像，請在處理程式中擷取它、讀取回應位元組，並在返回之前進行 base64 編碼。PNG、JPEG、GIF 或 WebP 影像會作為視覺輸入傳送給 Claude；任何其他類型的影像會儲存到磁碟，Claude 會改為收到其檔案路徑作為文字。

| 欄位 | 類型 | 備註 |
| :- | :- | :- |
| `type` | `"image"` | |
| `data` | `string` | Base64 編碼的位元組。僅限原始 base64，沒有 `data:image/...;base64,` 前綴 |
| `mimeType` | `string` | 必需。例如 `image/png`、`image/jpeg`、`image/webp`、`image/gif` |

```python Python theme={null}
import base64
import httpx
from claude_agent_sdk import tool


# Define a tool that fetches an image from a URL and returns it to Claude
@tool("fetch_image", "Fetch an image from a URL and return it to Claude", {"url": str})
async def fetch_image(args):
    async with httpx.AsyncClient() as client:  # Fetch the image bytes
        response = await client.get(args["url"])

    return {
        "content": [
            {
                "type": "image",
                "data": base64.b64encode(response.content).decode(
                    "ascii"
                ),  # Base64-encode the raw bytes
                "mimeType": response.headers.get(
                    "content-type", "image/png"
                ),  # Read MIME type from the response
            }
        ]
    }
```

```typescript TypeScript theme={null}
import { tool } from "@anthropic-ai/claude-agent-sdk";
import { z } from "zod";

tool(
  "fetch_image",
  "Fetch an image from a URL and return it to Claude",
  {
    url: z.string().url()
  },
  async (args) => {
    const response = await fetch(args.url); // Fetch the image bytes
    const buffer = Buffer.from(await response.arrayBuffer()); // Read into a Buffer for base64 encoding
    const mimeType = response.headers.get("content-type") ?? "image/png";

    return {
      content: [
        {
          type: "image",
          data: buffer.toString("base64"), // Base64-encode the raw bytes
          mimeType
        }
      ]
    };
  }
);
```

### 資源

資源區塊嵌入由 URI 識別的內容片段。實際內容位於區塊的 `text` 或 `blob` 欄位中。當您的工具產生產生的檔案或來自外部系統的記錄時，請使用此功能。

| 欄位 | 類型 | 備註 |
| :- | :- | :- |
| `type` | `"resource"` | |
| `resource.uri` | `string` | 內容的識別碼。任何 URI 配置 |
| `resource.text` | `string` | 內容（如果是文字）。提供此項或 `blob`，但不能同時提供兩者 |
| `resource.blob` | `string` | 內容 base64 編碼（如果是二進位）。僅限 TypeScript：Python SDK 會從工具結果中移除二進位資源並記錄警告 |
| `resource.mimeType` | `string` | 選用 |

此範例顯示從工具處理程式內部返回的資源區塊。SDK 不會從範例的 URI `file:///tmp/report.md` 讀取。

```typescript TypeScript theme={null}
return {
  content: [
    {
      type: "resource",
      resource: {
        uri: "file:///tmp/report.md", // Label for Claude to reference, not a path the SDK reads
        mimeType: "text/markdown",
        text: "# Report\n..." // The actual content, inline
      }
    }
  ]
};
```

```python Python theme={null}
return {
    "content": [
        {
            "type": "resource",
            "resource": {
                "uri": "file:///tmp/report.md",  # Not a path the SDK reads
                "mimeType": "text/markdown",
                "text": "# Report\n...",  # The actual content, inline
            },
        }
    ]
}
```

這些區塊形狀來自 MCP `CallToolResult` 類型。請參閱 [MCP 規格](https://modelcontextprotocol.io/specification/2025-06-18/server/tools#tool-result) 以取得完整定義。

## 返回結構化資料

`structuredContent` 是結果上的選用 JSON 物件，與 `content` 陣列分開。使用它來返回原始值，Claude 可以將其讀取為確切的欄位，而不是從文字字串或影像中解析它們。

當設定 `structuredContent` 時，Claude 會收到 JSON 加上來自 `content` 的任何影像或資源區塊。`content` 中的文字區塊不會被轉發，因為假設它們會複製結構化資料。下面的範例將圖表呈現為影像區塊，並從同一個處理程式的 `structuredContent` 中返回其背後的資料點。在程式碼片段中，`chartPngBuffer` 是一個包含已呈現 PNG 位元組的 `Buffer`。

```typescript TypeScript theme={null}
return {
  content: [
    {
      type: "image",
      data: chartPngBuffer.toString("base64"),
      mimeType: "image/png"
    }
  ],
  structuredContent: {
    series: "temperature_2m",
    unit: "fahrenheit",
    points: [62.1, 63.4, 65.0, 64.2]
  }
};
```

> [!NOTE]
>
> Python `@tool` 裝飾器只會從處理程式的返回字典中轉發 `content` 和 `is_error`。若要從 Python 返回 `structuredContent`，請改為執行[獨立 MCP 伺服器](https://code.claude.com/docs/zh-TW/agent-sdk/mcp.md)，而不是同處理程序 SDK 伺服器。

## 範例：單位轉換器

此工具在長度、溫度和重量的單位之間轉換數值。使用者可以詢問「將 100 公里轉換為英里」或「72°F 是多少攝氏度」，Claude 會從請求中選擇正確的單位類型和單位。

它展示了兩種模式：

* **Enum schemas：** `unit_type` 受限於一組固定值。在 TypeScript 中，使用 `z.enum()`。在 Python 中，dict schema 不支援 enum，因此需要完整的 JSON Schema dict。
* **不支援的輸入處理：** 當找不到轉換對時，處理程式會傳回 `isError: true`，以便 Claude 可以告訴使用者出了什麼問題，而不是將失敗視為正常結果。

```python Python theme={null}
from typing import Any
from claude_agent_sdk import tool, create_sdk_mcp_server


# z.enum() in TypeScript becomes an "enum" constraint in JSON Schema.
# The dict schema has no equivalent, so full JSON Schema is required.
@tool(
    "convert_units",
    "Convert a value from one unit to another",
    {
        "type": "object",
        "properties": {
            "unit_type": {
                "type": "string",
                "enum": ["length", "temperature", "weight"],
                "description": "Category of unit",
            },
            "from_unit": {
                "type": "string",
                "description": "Unit to convert from, e.g. kilometers, fahrenheit, pounds",
            },
            "to_unit": {"type": "string", "description": "Unit to convert to"},
            "value": {"type": "number", "description": "Value to convert"},
        },
        "required": ["unit_type", "from_unit", "to_unit", "value"],
    },
)
async def convert_units(args: dict[str, Any]) -> dict[str, Any]:
    conversions = {
        "length": {
            "kilometers_to_miles": lambda v: v * 0.621371,
            "miles_to_kilometers": lambda v: v * 1.60934,
            "meters_to_feet": lambda v: v * 3.28084,
            "feet_to_meters": lambda v: v * 0.3048,
        },
        "temperature": {
            "celsius_to_fahrenheit": lambda v: (v * 9) / 5 + 32,
            "fahrenheit_to_celsius": lambda v: (v - 32) * 5 / 9,
            "celsius_to_kelvin": lambda v: v + 273.15,
            "kelvin_to_celsius": lambda v: v - 273.15,
        },
        "weight": {
            "kilograms_to_pounds": lambda v: v * 2.20462,
            "pounds_to_kilograms": lambda v: v * 0.453592,
            "grams_to_ounces": lambda v: v * 0.035274,
            "ounces_to_grams": lambda v: v * 28.3495,
        },
    }

    key = f"{args['from_unit']}_to_{args['to_unit']}"
    fn = conversions.get(args["unit_type"], {}).get(key)

    if not fn:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Unsupported conversion: {args['from_unit']} to {args['to_unit']}",
                }
            ],
            "is_error": True,
        }

    result = fn(args["value"])
    return {
        "content": [
            {
                "type": "text",
                "text": f"{args['value']} {args['from_unit']} = {result:.4f} {args['to_unit']}",
            }
        ]
    }


converter_server = create_sdk_mcp_server(
    name="converter",
    version="1.0.0",
    tools=[convert_units],
)
```

```typescript TypeScript theme={null}
import { tool, createSdkMcpServer } from "@anthropic-ai/claude-agent-sdk";
import { z } from "zod";

const convert = tool(
  "convert_units",
  "Convert a value from one unit to another",
  {
    unit_type: z.enum(["length", "temperature", "weight"]).describe("Category of unit"),
    from_unit: z
      .string()
      .describe("Unit to convert from, e.g. kilometers, fahrenheit, pounds"),
    to_unit: z.string().describe("Unit to convert to"),
    value: z.number().describe("Value to convert")
  },
  async (args) => {
    type Conversions = Record<string, Record<string, (v: number) => number>>;

    const conversions: Conversions = {
      length: {
        kilometers_to_miles: (v) => v * 0.621371,
        miles_to_kilometers: (v) => v * 1.60934,
        meters_to_feet: (v) => v * 3.28084,
        feet_to_meters: (v) => v * 0.3048
      },
      temperature: {
        celsius_to_fahrenheit: (v) => (v * 9) / 5 + 32,
        fahrenheit_to_celsius: (v) => ((v - 32) * 5) / 9,
        celsius_to_kelvin: (v) => v + 273.15,
        kelvin_to_celsius: (v) => v - 273.15
      },
      weight: {
        kilograms_to_pounds: (v) => v * 2.20462,
        pounds_to_kilograms: (v) => v * 0.453592,
        grams_to_ounces: (v) => v * 0.035274,
        ounces_to_grams: (v) => v * 28.3495
      }
    };

    const key = `${args.from_unit}_to_${args.to_unit}`;
    const fn = conversions[args.unit_type]?.[key];

    if (!fn) {
      return {
        content: [
          {
            type: "text",
            text: `Unsupported conversion: ${args.from_unit} to ${args.to_unit}`
          }
        ],
        isError: true
      };
    }

    const result = fn(args.value);
    return {
      content: [
        {
          type: "text",
          text: `${args.value} ${args.from_unit} = ${result.toFixed(4)} ${args.to_unit}`
        }
      ]
    };
  }
);

const converterServer = createSdkMcpServer({
  name: "converter",
  version: "1.0.0",
  tools: [convert]
});
```

伺服器定義後，以與天氣範例相同的方式將其傳遞給 `query`。此範例在迴圈中發送三個不同的提示，以展示相同的工具處理不同的單位類型。對於每個回應，它檢查 `AssistantMessage` 物件（包含該輪中 Claude 進行的工具呼叫）並在列印最終 `ResultMessage` 文字之前列印每個 `ToolUseBlock`。這讓您可以看到 Claude 何時使用工具與何時從自己的知識回答。

因為 [tool search](https://code.claude.com/docs/zh-TW/agent-sdk/tool-search.md) 預設為開啟，輸出也可能包含 `ToolSearch` 呼叫，因為 Claude 載入延遲的工具 schema。

```python Python theme={null}
import asyncio
from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    ResultMessage,
    AssistantMessage,
    ToolUseBlock,
)


async def main():
    options = ClaudeAgentOptions(
        mcp_servers={"converter": converter_server},
        allowed_tools=["mcp__converter__convert_units"],
    )

    prompts = [
        "Convert 100 kilometers to miles.",
        "What is 72°F in Celsius?",
        "How many pounds is 5 kilograms?",
    ]

    for prompt in prompts:
        try:
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, ToolUseBlock):
                            print(f"[tool call] {block.name}({block.input})")
                elif isinstance(message, ResultMessage) and message.subtype == "success":
                    print(f"Q: {prompt}\nA: {message.result}\n")
        except Exception as error:
            # A single-shot query() raises after yielding an error result. Only success
            # results are printed above, so handle the failure here and continue with
            # the next prompt.
            print(f"Call failed: {error}")


asyncio.run(main())
```

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

const prompts = [
  "Convert 100 kilometers to miles.",
  "What is 72°F in Celsius?",
  "How many pounds is 5 kilograms?"
];

for (const prompt of prompts) {
  try {
    for await (const message of query({
      prompt,
      options: {
        mcpServers: { converter: converterServer },
        allowedTools: ["mcp__converter__convert_units"]
      }
    })) {
      if (message.type === "assistant") {
        for (const block of message.message.content) {
          if (block.type === "tool_use") {
            console.log(`[tool call] ${block.name}`, block.input);
          }
        }
      } else if (message.type === "result" && message.subtype === "success") {
        console.log(`Q: ${prompt}\nA: ${message.result}\n`);
      }
    }
  } catch (error) {
    // A single-shot query() throws after yielding an error result. Only success
    // results are logged above, so handle the failure here and continue with
    // the next prompt.
    console.error(`Call failed: ${error}`);
  }
}
```

## 後續步驟

您可以在同一個伺服器上混合使用本頁面的模式：單一伺服器可以同時包含資料庫工具、API 閘道工具和影像渲染器。

從這裡開始：

* 如果您的伺服器增長到數十個工具，請參閱[工具搜尋](https://code.claude.com/docs/zh-TW/agent-sdk/tool-search.md)以延遲載入它們，直到 Claude 需要它們為止。
* 若要連接到外部 MCP 伺服器（檔案系統、GitHub、Slack）而不是建立您自己的伺服器，請參閱[連接 MCP 伺服器](https://code.claude.com/docs/zh-TW/agent-sdk/mcp.md)。
* 若要控制哪些工具自動執行與需要核准，請參閱[設定權限](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md)。

<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/channels-reference | lastmod: 2026-10-28 | section: Reference / Reference -->
> 來源：https://code.claude.com/docs/zh-TW/channels-reference（官方 zh-TW，lastmod 2026-10-28）｜分類：Reference › Reference｜EN 摘要：Build an MCP server that pushes webhooks, alerts, and chat messages into a Claude Code session. Reference for the channel contract: capability declaration, notification events, reply tools, sender gating, and permission relay.

# Channels 參考

> 建立一個 MCP 伺服器，將 webhooks、警報和聊天訊息推送到 Claude Code 工作階段。頻道合約的參考：功能聲明、通知事件、回覆工具、寄件者閘道和權限中繼。

> [!NOTE]
>
> Channels 處於[研究預覽](https://code.claude.com/docs/zh-TW/channels.md#research-preview)階段。Team 和 Enterprise 組織必須[明確啟用它們](https://code.claude.com/docs/zh-TW/channels.md#enterprise-controls)。

Channel 是一個 MCP 伺服器，將事件推送到 Claude Code 工作階段，以便 Claude 可以對終端機外發生的事情做出反應。

您可以建立單向或雙向 channel。單向 channel 轉發警報、webhooks 或監控事件供 Claude 處理。雙向 channel（如聊天橋接）也會[公開回覆工具](#expose-a-reply-tool)，以便 Claude 可以傳送訊息回去。具有受信任寄件者路徑的 channel 也可以選擇加入[中繼權限提示](#relay-permission-prompts)，以便您可以遠端批准或拒絕工具使用。

本頁涵蓋：

* [概述](#overview)：channels 如何運作
* [您需要什麼](#what-you-need)：要求和一般步驟
* [範例：建立 webhook 接收器](#example-build-a-webhook-receiver)：最小單向逐步解說
* [伺服器選項](#server-options)：建構函式欄位
* [通知格式](#notification-format)：事件承載和傳遞行為
* [公開回覆工具](#expose-a-reply-tool)：讓 Claude 傳送訊息回去
* [閘道入站訊息](#gate-inbound-messages)：寄件者檢查以防止提示注入
* [中繼權限提示](#relay-permission-prompts)：將工具批准提示轉發到遠端 channels

若要使用現有 channel 而不是建立一個，請參閱 [Channels](https://code.claude.com/docs/zh-TW/channels.md)。Telegram、Discord、iMessage 和 fakechat 包含在研究預覽中。

## 概述

Channel 是在與 Claude Code 相同的機器上執行的 [MCP](https://modelcontextprotocol.io) 伺服器。Claude Code 將其作為子程序生成並透過 stdio 進行通訊。您的 channel 伺服器是外部系統和 Claude Code 工作階段之間的橋接：

* **聊天平台**（Telegram、Discord）：您的外掛程式在本機執行並輪詢平台的 API 以取得新訊息。當有人傳送 DM 給您的機器人時，外掛程式會接收訊息並將其轉發給 Claude。無需公開 URL。
* **Webhooks**（CI、監控）：您的伺服器在本機 HTTP 連接埠上監聽。外部系統 POST 到該連接埠，您的伺服器將承載推送給 Claude。

![架構圖，顯示外部系統連接到您的本機 channel 伺服器，該伺服器透過 stdio 與 Claude Code 通訊](https://mintcdn.com/claude-code/9FG0ZKj9uKYiHmbi/images/channel-architecture.svg?fit=max\&auto=format\&n=9FG0ZKj9uKYiHmbi\&q=85\&s=9a037b7da80184ae49015c0256b21a1f)

## 您需要什麼

唯一的硬性要求是 [`@modelcontextprotocol/sdk`](https://www.npmjs.com/package/@modelcontextprotocol/sdk) 套件和 Node.js 相容的執行時。[Bun](https://bun.sh)、[Node](https://nodejs.org) 和 [Deno](https://deno.com) 都可以運作。研究預覽中的預先建立外掛程式使用 Bun，但您的 channel 不一定要。

您的伺服器需要：

1. 聲明 `claude/channel` 功能，以便 Claude Code 註冊通知監聽器
2. 當發生某事時發出 `notifications/claude/channel` 事件
3. 透過 [stdio transport](https://modelcontextprotocol.io/docs/concepts/transports#standard-io) 連接

[伺服器選項](#server-options)和[通知格式](#notification-format)部分詳細涵蓋每一項。請參閱[範例：建立 webhook 接收器](#example-build-a-webhook-receiver)以取得完整逐步解說。

在研究預覽期間，自訂 channels 不在[核准允許清單](https://code.claude.com/docs/zh-TW/channels.md#supported-channels)上。使用 `--dangerously-load-development-channels` 在本機測試。請參閱[在研究預覽期間測試](#test-during-the-research-preview)以取得詳細資訊。

## 範例：建立 webhook 接收器

本逐步說明將建立一個單一檔案的伺服器，用來監聽 HTTP 請求並將其轉發至您的 Claude Code 工作階段。完成後，任何能夠傳送 HTTP POST 的來源，例如 CI 管線、監控警示或 `curl` 命令，都能將事件推送給 Claude。

此範例使用 [Bun](https://bun.sh) 作為執行環境，因為它內建 HTTP 伺服器並支援 TypeScript。您也可以改用 [Node](https://nodejs.org) 或 [Deno](https://deno.com)；唯一的需求是 [MCP SDK](https://www.npmjs.com/package/@modelcontextprotocol/sdk)。

**1. 建立專案**

[權限轉送](#relay-permission-prompts)範例會直接匯入 `zod`，因此需要與 MCP SDK 一併安裝。建立新目錄並安裝兩者：

```bash theme={null}
mkdir webhook-channel && cd webhook-channel
bun add @modelcontextprotocol/sdk zod
```

**2. 撰寫頻道伺服器**

建立名為 `webhook.ts` 的檔案。這就是完整的頻道伺服器：它透過 stdio 連線至 Claude Code，並在連接埠 8788 上監聽 HTTP POST。當請求抵達時，它會將內容主體作為頻道事件推送給 Claude。

```ts title="webhook.ts" theme={null}
#!/usr/bin/env bun
import { Server } from '@modelcontextprotocol/sdk/server/index.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'

// Create the MCP server and declare it as a channel
const mcp = new Server(
  { name: 'webhook', version: '0.0.1' },
  {
    // this key is what makes it a channel — Claude Code registers a listener for it
    capabilities: { experimental: { 'claude/channel': {} } },
    // Claude Code delivers this to Claude as context when the server connects, so it knows how to handle these events
    instructions: 'Events from the webhook channel arrive as <channel source="webhook" ...>. They are one-way: read them and act, no reply expected.',
  },
)

// Connect to Claude Code over stdio (Claude Code spawns this process)
await mcp.connect(new StdioServerTransport())

// Start an HTTP server that forwards every POST to Claude
Bun.serve({
  port: 8788,  // any open port works
  // localhost-only: nothing outside this machine can POST
  hostname: '127.0.0.1',
  async fetch(req) {
    const body = await req.text()
    await mcp.notification({
      method: 'notifications/claude/channel',
      params: {
        content: body,  // becomes the body of the <channel> tag
        // each key becomes a tag attribute, e.g. <channel path="/" method="POST">
        meta: { path: new URL(req.url).pathname, method: req.method },
      },
    })
    return new Response('ok')
  },
})
```

此檔案依序設定伺服器、透過 stdio 連線，並啟動 HTTP 監聽器：

* **伺服器設定**：建立在其 capabilities 中包含 `claude/channel` 的 MCP 伺服器，這正是告知 Claude Code 此為頻道的關鍵。伺服器連線時，Claude Code 會將 [`instructions`](#server-options) 字串作為上下文傳遞給 Claude：請告訴 Claude 預期會收到哪些事件、是否需要回覆，以及若需回覆時應如何轉送回覆。
* **Stdio 連線**：透過 stdin/stdout 連線至 Claude Code。這是任何 [MCP 伺服器](https://modelcontextprotocol.io/docs/concepts/transports#standard-io)的標準做法。
* **HTTP 監聽器**：在連接埠 8788 上啟動本機 Web 伺服器。每個 POST 內容主體都會透過 `mcp.notification()` 作為頻道事件轉發給 Claude。`content` 會成為事件主體，而每個 `meta` 項目會成為 `<channel>` 標籤上的屬性。監聽器需要存取 `mcp` 執行個體，因此它在同一個程序中執行。若是較大型的專案，您可以將其拆分為獨立的模組。

**3. 向 Claude Code 註冊您的伺服器**

將伺服器加入您的 MCP 設定，讓 Claude Code 知道如何啟動它。若是位於同一目錄中的專案層級 `.mcp.json`，請使用相對路徑。若是位於 `~/.claude.json` 的使用者層級設定，請使用完整的絕對路徑，以便從任何專案都能找到該伺服器：

```json title=".mcp.json" theme={null}
{
  "mcpServers": {
    "webhook": { "command": "bun", "args": ["./webhook.ts"] }
  }
}
```

Claude Code 會在啟動時讀取您的 MCP 設定，並將每個伺服器作為子程序啟動。

**4. 進行測試**

在研究預覽期間，自訂頻道不在允許清單中，因此請使用開發旗標啟動 Claude Code：

```bash theme={null}
claude --dangerously-load-development-channels server:webhook
```

Claude Code 會先顯示全螢幕警告對話框，列出您正在載入的開發頻道。選取 **I am using this for local development** 以繼續，或選取 **Exit** 以結束。

您第一次在此專案中啟動工作階段時，Claude Code 也會在使用 `.mcp.json` 中的新伺服器之前徵求您的同意。對話框會顯示「New MCP server found in this project: webhook」。選取 **Use this MCP server** 以繼續。

接受後，Claude Code 會將您的 `webhook.ts` 作為子程序啟動，HTTP 監聽器也會在您設定的連接埠（此範例中為 8788）上自動啟動。您不需要自行執行伺服器。

啟動橫幅下方的淡色通知會確認頻道已註冊：`Channels (experimental) messages from server:webhook inject directly in this session · restart without --dangerously-load-development-channels to stop`。

若您看到「blocked by org policy」，表示您的組織管理員需要先[啟用頻道](https://code.claude.com/docs/zh-TW/channels.md#enterprise-controls)。

在另一個終端機中，傳送附帶訊息的 HTTP POST 至您的伺服器來模擬 webhook。此範例會將 CI 失敗警示傳送至連接埠 8788（或您所設定的任何連接埠）：

```bash theme={null}
curl -X POST localhost:8788 -d "build failed on main: https://ci.example.com/run/1234"
```

payload 會以 `<channel>` 標籤的形式抵達 Claude 的上下文：

```text theme={null}
<channel source="webhook" path="/" method="POST">
build failed on main: https://ci.example.com/run/1234
</channel>
```

您的終端機會將事件呈現為單行摘要 `← webhook: build failed on main: https://ci.example.com/run/1234`，而非原始標籤。接著您會看到 Claude 開始回應：讀取檔案、執行命令，或執行訊息所要求的任何動作。這是單向頻道，因此 Claude 會在您的工作階段中採取行動，但不會透過 webhook 傳回任何內容。若要加入回覆功能，請參閱[公開回覆工具](#expose-a-reply-tool)。

若事件未抵達，診斷方式取決於 `curl` 傳回的結果：

* **`curl` 成功但沒有任何內容送達 Claude**：在您的工作階段中執行 `/mcp` 以檢查伺服器狀態。`failed` 狀態通常表示您的伺服器檔案中有相依性或匯入錯誤。若要查看 stderr 追蹤，請使用 `claude --debug --dangerously-load-development-channels server:webhook` 重新啟動，並檢查位於 `~/.claude/debug/<session-id>.txt` 的偵錯日誌。
* **`curl` 失敗並顯示「connection refused」**：表示連接埠尚未繫結，或是先前執行所遺留的程序仍佔用該連接埠。`lsof -i :<port>` 會顯示正在監聽的程序；請在重新啟動工作階段之前，先以 `kill` 終止遺留的程序。

[fakechat 伺服器](https://github.com/anthropics/claude-plugins-official/tree/main/external_plugins/fakechat)以此模式為基礎進行擴充，加入了 Web UI、檔案附件，以及用於雙向聊天的回覆工具。

## 在研究預覽期間測試

在研究預覽期間，每個 channel 都必須在[核准允許清單](https://code.claude.com/docs/zh-TW/channels.md#research-preview)上才能註冊。開發旗標在確認提示後繞過特定項目的允許清單。此範例顯示兩種項目類型：

```bash theme={null}
# 測試您正在開發的外掛程式
claude --dangerously-load-development-channels plugin:yourplugin@yourmarketplace

# 測試裸 .mcp.json 伺服器（尚無外掛程式包裝）
claude --dangerously-load-development-channels server:webhook
```

請在互動式工作階段中使用開發旗標，Claude Code 才能在其中顯示確認提示。如果您在非互動模式下透過 `-p` 或 Agent SDK 傳遞此旗標，Claude Code 會忽略該旗標，且 channel 不會註冊。

繞過是按項目進行的。將此旗標與 `--channels` 結合不會將繞過擴展到 `--channels` 項目。在研究預覽期間，您的 channel 不在核准允許清單上，因此在您建立和測試時保持在開發旗標上。

> [!NOTE]
>
> 此旗標僅跳過允許清單。`channelsEnabled` 組織政策仍然適用。不要使用它來執行來自不受信任來源的 channels。

## 伺服器選項

Channel 在 [`Server`](https://modelcontextprotocol.io/docs/learn/server-concepts) 建構函式中設定這些選項。`instructions` 和 `capabilities.tools` 欄位是[標準 MCP](https://modelcontextprotocol.io/docs/learn/server-concepts)；`capabilities.experimental['claude/channel']` 和 `capabilities.experimental['claude/channel/permission']` 是 channel 特定的新增項目：

| 欄位 | 類型 | 描述 |
| :- | :- | :- |
| `capabilities.experimental['claude/channel']` | `object` | 必需。始終為 `{}`。存在會註冊通知監聽器。 |
| `capabilities.experimental['claude/channel/permission']` | `object` 或 `false` | 選用。將其設定為 `{}` 以聲明此 channel 可以接收權限中繼要求。聲明時，Claude Code 會將工具批准提示轉發到您的 channel，以便您可以遠端批准或拒絕它們。若要選擇退出，請省略該鍵或將其設定為 `false`。在 v2.1.234 之前，Claude Code 將 `false` 視為已聲明。請參閱[中繼權限提示](#relay-permission-prompts)。 |
| `capabilities.tools` | `object` | 僅限雙向。始終為 `{}`。標準 MCP 工具功能。請參閱[公開回覆工具](#expose-a-reply-tool)。 |
| `instructions` | `string` | 建議。Claude Code 在伺服器連線時將其傳遞給 Claude 作為內容。告訴 Claude 期望什麼事件、`<channel>` 標籤屬性的含義、是否回覆，如果是，使用哪個工具以及傳遞回哪個屬性（如 `chat_id`）。 |

若要建立單向 channel，請省略 `capabilities.tools`。此範例顯示設定了 channel 功能、工具和指示的雙向設定：

```ts theme={null}
import { Server } from '@modelcontextprotocol/sdk/server/index.js'

const mcp = new Server(
  { name: 'your-channel', version: '0.0.1' },
  {
    capabilities: {
      experimental: { 'claude/channel': {} },  // 註冊 channel 監聽器
      tools: {},  // 對於單向 channels 省略
    },
    // Claude Code 在伺服器連線時將其傳遞給 Claude，以便它知道如何處理您的事件
    instructions: 'Messages arrive as <channel source="your-channel" ...>. Reply with the reply tool.',
  },
)
```

## 通知格式

您的伺服器發出 `notifications/claude/channel` 和兩個參數：

| 欄位 | 類型 | 描述 |
| :- | :- | :- |
| `content` | `string` | 事件主體。作為 `<channel>` 標籤的主體傳遞。 |
| `meta` | `Record<string, string>` | 選用。每個項目成為 `<channel>` 標籤上的屬性，用於路由上下文，如聊天 ID、寄件者名稱或警報嚴重性。金鑰必須是識別碼：僅限字母、數字和底線。包含連字號或其他字元的金鑰會被無聲地捨棄。 |

您的伺服器透過在 `Server` 實例上呼叫 `mcp.notification()` 來推送事件。此範例推送帶有兩個中繼金鑰的 CI 失敗警報：

```ts theme={null}
await mcp.notification({
  method: 'notifications/claude/channel',
  params: {
    content: 'build failed on main: https://ci.example.com/run/1234',
    meta: { severity: 'high', run_id: '1234' },
  },
})
```

事件在 Claude 的上下文中到達，包裝在 `<channel>` 標籤中。`source` 屬性從您的伺服器配置的名稱自動設定：

```text theme={null}
<channel source="your-channel" severity="high" run_id="1234">
build failed on main: https://ci.example.com/run/1234
</channel>
```

Claude Code 不會確認通知。`mcp.notification()` 上的 `await` 在訊息寫入傳輸時解決，而不是在 Claude 已處理它時。如果工作階段尚未將您的伺服器載入為 channel，或組織政策阻止它，Claude Code 會無聲地捨棄事件，不會向您的伺服器返回任何錯誤。

如果您需要傳遞確認，請在您的伺服器中追蹤事件狀態，並公開一個 [reply tool](#expose-a-reply-tool)，Claude 可以呼叫該工具來報告狀態回去。

事件排隊進入工作階段並按順序處理。如果在 Claude 忙碌時有多個通知到達，它們會在下一個轉折時一起傳遞，Claude 會將它們作為一個群組處理。若要並行處理獨立事件流，請執行單獨的工作階段。

## 公開回覆工具

如果您的 channel 是雙向的，如聊天橋接而不是警報轉發器，請公開標準 [MCP 工具](https://modelcontextprotocol.io/docs/concepts/tools)，Claude 可以呼叫該工具來傳送訊息回去。工具註冊沒有任何 channel 特定的內容。回覆工具有三個元件：

1. 您的 `Server` 建構函式功能中的 `tools: {}` 項目，以便 Claude Code 發現工具
2. 定義工具架構並實現傳送邏輯的工具處理程式
3. 您的 `Server` 建構函式中的 `instructions` 字串，告訴 Claude 何時以及如何呼叫工具

若要將這些新增到上面的 [webhook 接收器](#example-build-a-webhook-receiver)：

**1. 啟用工具發現**

在 `webhook.ts` 中的 `Server` 建構函式中，將 `tools: {}` 新增到功能，以便 Claude Code 知道您的伺服器提供工具：

```ts theme={null}
capabilities: {
  experimental: { 'claude/channel': {} },
  tools: {},  // 啟用工具發現
},
```

**2. 註冊回覆工具**

將以下內容新增到 `webhook.ts`。`import` 位於檔案頂部，與您的其他匯入一起；兩個處理程式位於 `Server` 建構函式和 `mcp.connect()` 之間。這會註冊一個 `reply` 工具，Claude 可以使用 `chat_id` 和 `text` 呼叫：

```ts theme={null}
// 在 webhook.ts 頂部新增此匯入
import { ListToolsRequestSchema, CallToolRequestSchema } from '@modelcontextprotocol/sdk/types.js'

// Claude 在啟動時查詢此項以發現您的伺服器提供什麼工具
mcp.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [{
    name: 'reply',
    description: 'Send a message back over this channel',
    // inputSchema 告訴 Claude 要傳遞什麼引數
    inputSchema: {
      type: 'object',
      properties: {
        chat_id: { type: 'string', description: 'The conversation to reply in' },
        text: { type: 'string', description: 'The message to send' },
      },
      required: ['chat_id', 'text'],
    },
  }],
}))

// Claude 想要叫用工具時呼叫此項
mcp.setRequestHandler(CallToolRequestSchema, async req => {
  if (req.params.name === 'reply') {
    const { chat_id, text } = req.params.arguments as { chat_id: string; text: string }
    // send() 是您的出站：POST 到您的聊天平台，或用於本機
    // 測試下面完整範例中顯示的 SSE 廣播。
    send(`Reply to ${chat_id}: ${text}`)
    return { content: [{ type: 'text', text: 'sent' }] }
  }
  throw new Error(`unknown tool: ${req.params.name}`)
})
```

**3. 更新指示**

更新 `Server` 建構函式中的 `instructions` 字串，以便 Claude 知道透過工具將回覆路由回去。此範例告訴 Claude 從入站標籤傳遞 `chat_id`：

```ts theme={null}
instructions: 'Messages arrive as <channel source="webhook" chat_id="...">. Reply with the reply tool, passing the chat_id from the tag.'
```

以下是具有雙向支援的完整 `webhook.ts`。出站回覆透過 `GET /events` 使用 [Server-Sent Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events) (SSE) 串流，因此 `curl -N localhost:8788/events` 可以即時觀看它們；入站聊天到達 `POST /`：

```ts title="Full webhook.ts with reply tool" expandable theme={null}
#!/usr/bin/env bun
import { Server } from '@modelcontextprotocol/sdk/server/index.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import { ListToolsRequestSchema, CallToolRequestSchema } from '@modelcontextprotocol/sdk/types.js'

// --- 出站：寫入 /events 上任何 curl -N 監聽器 ---
// 真實橋接會改為 POST 到您的聊天平台。
const listeners = new Set<(chunk: string) => void>()
function send(text: string) {
  const chunk = text.split('\n').map(l => `data: ${l}\n`).join('') + '\n'
  for (const emit of listeners) emit(chunk)
}

const mcp = new Server(
  { name: 'webhook', version: '0.0.1' },
  {
    capabilities: {
      experimental: { 'claude/channel': {} },
      tools: {},
    },
    instructions: 'Messages arrive as <channel source="webhook" chat_id="...">. Reply with the reply tool, passing the chat_id from the tag.',
  },
)

mcp.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [{
    name: 'reply',
    description: 'Send a message back over this channel',
    inputSchema: {
      type: 'object',
      properties: {
        chat_id: { type: 'string', description: 'The conversation to reply in' },
        text: { type: 'string', description: 'The message to send' },
      },
      required: ['chat_id', 'text'],
    },
  }],
}))

mcp.setRequestHandler(CallToolRequestSchema, async req => {
  if (req.params.name === 'reply') {
    const { chat_id, text } = req.params.arguments as { chat_id: string; text: string }
    send(`Reply to ${chat_id}: ${text}`)
    return { content: [{ type: 'text', text: 'sent' }] }
  }
  throw new Error(`unknown tool: ${req.params.name}`)
})

await mcp.connect(new StdioServerTransport())

let nextId = 1
Bun.serve({
  port: 8788,
  hostname: '127.0.0.1',
  idleTimeout: 0,  // 不要關閉閒置 SSE 串流
  async fetch(req) {
    const url = new URL(req.url)

    // GET /events：SSE 串流，所以 curl -N 可以即時觀看 Claude 的回覆
    if (req.method === 'GET' && url.pathname === '/events') {
      const stream = new ReadableStream({
        start(ctrl) {
          ctrl.enqueue(': connected\n\n')  // 所以 curl 立即顯示某些內容
          const emit = (chunk: string) => ctrl.enqueue(chunk)
          listeners.add(emit)
          req.signal.addEventListener('abort', () => listeners.delete(emit))
        },
      })
      return new Response(stream, {
        headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' },
      })
    }

    // POST：作為 channel 事件轉發給 Claude
    const body = await req.text()
    const chat_id = String(nextId++)
    await mcp.notification({
      method: 'notifications/claude/channel',
      params: {
        content: body,
        meta: { chat_id, path: url.pathname, method: req.method },
      },
    })
    return new Response('ok')
  },
})
```

[fakechat 伺服器](https://github.com/anthropics/claude-plugins-official/tree/main/external_plugins/fakechat)顯示了一個更完整的範例，具有檔案附件和訊息編輯。

## 閘道入站訊息

未閘道的 channel 是提示注入向量。任何可以到達您的端點的人都可以在 Claude 前面放置文字。監聽聊天平台或公開端點的 channel 在發出任何內容之前需要真正的寄件者檢查。

在呼叫 `mcp.notification()` 之前，根據允許清單檢查寄件者。此範例捨棄來自不在集合中的寄件者的任何訊息：

```ts theme={null}
const allowed = new Set(loadAllowlist())  // 從您的 access.json 或等效項

// 在您的訊息處理程式中，在發出之前：
if (!allowed.has(message.from.id)) {  // 寄件者，不是房間
  return  // 無聲地捨棄
}
await mcp.notification({ ... })
```

根據寄件者的身份而不是聊天或房間身份進行閘道：範例中的 `message.from.id`，而不是 `message.chat.id`。在群組聊天中，這些不同，根據房間進行閘道會讓允許清單群組中的任何人將訊息注入到工作階段中。

[Telegram](https://github.com/anthropics/claude-plugins-official/tree/main/external_plugins/telegram) 和 [Discord](https://github.com/anthropics/claude-plugins-official/tree/main/external_plugins/discord) channels 以相同方式根據寄件者允許清單進行閘道。它們透過[配對](https://code.claude.com/docs/zh-TW/channels.md#security)啟動清單。請參閱任一實現以取得完整配對流程。[iMessage](https://github.com/anthropics/claude-plugins-official/tree/main/external_plugins/imessage) channel 採用不同的方法：它在啟動時從 Messages 資料庫偵測使用者自己的位址並自動讓它們通過，其他寄件者按控制代碼新增。

## 中繼權限提示

當 Claude 呼叫需要批准的工具時，本機終端機對話框開啟，工作階段等待。雙向 channel 可以選擇加入以在平行接收相同提示，並將其中繼到您在另一台裝置上。兩者都保持活躍：您可以在終端機或手機上回答，Claude Code 應用先到達的答案並關閉另一個。

中繼涵蓋工具使用批准，如 `Bash`、`Write` 和 `Edit`。專案信任和 MCP 伺服器同意對話框不中繼；這些僅在本機終端機中出現。

Claude Code v2.1.234 及更新版本僅將權限要求傳送到它為工作階段註冊為 channel 的伺服器，因此中繼位於與[工作階段選擇加入和組織控制](https://code.claude.com/docs/zh-TW/channels.md#security)相同的後面。中繼也要求您使用 `--channels` 或開發旗標選擇加入伺服器，並要求伺服器聲明權限功能。

### 中繼如何運作

當權限提示開啟時，中繼迴圈有四個步驟：

1. Claude Code 生成短要求 ID 並通知您的伺服器
2. 您的伺服器將提示和 ID 轉發到您的聊天應用
3. 遠端使用者回覆是或否以及該 ID
4. 您的入站處理程式將回覆解析為判決，Claude Code 僅在 ID 符合開啟要求時應用它

本機終端機對話框在所有這一切中保持開啟。如果終端機上的某人在遠端判決到達之前回答，該答案會改為應用，待處理的遠端要求會被捨棄。

![序列圖：Claude Code 傳送 permission\_request 通知到 channel 伺服器，伺服器格式化並傳送提示到聊天應用，人類回覆判決，伺服器將該回覆解析為權限通知回到 Claude Code](https://mintcdn.com/claude-code/9FG0ZKj9uKYiHmbi/images/channel-permission-relay.svg?fit=max\&auto=format\&n=9FG0ZKj9uKYiHmbi\&q=85\&s=97d57f128f0da55f105ab1e3a7e10240)

### 權限要求欄位

來自 Claude Code 的出站通知是 `notifications/claude/channel/permission_request`。像[頻道通知](#notification-format)一樣，傳輸是標準 MCP，但方法和架構是 Claude Code 擴展。`params` 物件有四個字串欄位，您的伺服器將其格式化為出站提示：

| 欄位 | 描述 |
| - | - |
| `request_id` | 五個小寫字母，從 `a`-`z` 中抽取，不包括 `l`，因此在手機上輸入時永遠不會讀作 `1` 或 `I`。將其包含在您的出站提示中，以便可以在回覆中回顯。Claude Code 僅接受帶有其發出的 ID 的判決。本機終端機對話框不顯示此 ID，因此您的出站處理程式是了解它的唯一方式。 |
| `tool_name` | Claude 想要使用的工具的名稱，例如 `Bash` 或 `Write`。 |
| `description` | 此特定工具呼叫執行的操作的人類可讀摘要，永遠不是命令本身。對於 Bash 呼叫，這是 Claude 對命令的描述；當模型未提供描述時，欄位是常數 `Run shell command`，不包含任何命令詳細資訊。在您有空間時呈現 `input_preview`。 |
| `input_preview` | 工具的引數作為 JSON 形狀的顯示文字，以各頂層欄位為鍵。對於 Bash，這是命令；對於 Write，是檔案路徑和內容。如果您只有一行訊息的空間，請從您的提示中省略它。您的伺服器決定要顯示什麼。 |

Claude Code v2.1.211 或更新版本的用戶端在中繼前清理 `description` 和 `input_preview`。預期文字中有三個變化：

* Claude Code 中和方向覆蓋字元、不可見字元以及引號和角括號外觀相似的字元。
* Claude Code 將每個空白字元執行摺疊為單一空格。
* Claude Code 中繼文字最多 3,500 個代碼點。對於較長的值，您會收到其開始和結束，圍繞計數的 `⋯ N code points elided ⋯` 標記。長命令的結尾仍然到達批准者。

對於 `input_preview`，Claude Code 將 3,500 限制分別應用於引數的每個頂層欄位，並保留 JSON 自己的結構引號。v2.1.211 之前的用戶端中繼 `description` 原始並將 `input_preview` 切割為 200 個 UTF-16 單位，尾部省略號。

Claude Code v2.1.234 或更新版本的用戶端在 `input_preview` 欄位值位置中繼標記 `(value unserializable)`，它們無法安全序列化，例如循環結構或極大陣列。您仍然會收到欄位的鍵，預覽的其他欄位保持不變。

Claude Code v2.1.234 或更新版本的用戶端也在 `description` 和 `input_preview` 中遮罩認證。您會收到 `[REDACTED]` 代替可識別的提供者認證令牌，例如 API 金鑰或個人存取令牌。當您呈現欄位時，預期遮罩的三個效果：

* Claude Code 在 `input_preview` 內遮罩鍵名以及它們的值。您顯示的鍵名可能與輸入中的鍵名不符。
* Claude Code 永遠不會遮罩包含 shell 語法、路徑字元或 URL 字元的跨度。遮罩無法隱藏正在批准的命令、檔案路徑或目的地。
* Claude Code 不會遮罩缺乏可識別前綴的祕密，或跨越空白的祕密，例如私密金鑰區塊。兩者都到達您的伺服器未遮罩。

遮罩不會改變誰接收欄位。無論保持未遮罩的內容只進入您使用 `--channels` 或開發旗標選擇加入的伺服器。除非您控制用戶端群，否則將兩個欄位視為不受信任。

您的伺服器傳送回的判決是 `notifications/claude/channel/permission`，有兩個欄位：`request_id` 回顯上面的 ID，`behavior` 設定為 `'allow'` 或 `'deny'`。允許讓工具呼叫繼續；拒絕會拒絕它。兩個判決都不影響未來的呼叫。

### 將中繼新增到聊天橋接

將權限中繼新增到雙向 channel 需要三個元件：

1. 您的 `Server` 建構函式中 `experimental` 功能下的 `claude/channel/permission: {}` 項目，以便 Claude Code 知道轉發提示
2. `notifications/claude/channel/permission_request` 的通知處理程式，格式化提示並透過您的平台 API 傳送出去
3. 您的入站訊息處理程式中的檢查，識別 `yes <id>` 或 `no <id>` 並發出 `notifications/claude/channel/permission` 判決通知，而不是將文字轉發給 Claude

僅在您的 channel [驗證寄件者](#gate-inbound-messages)時聲明功能，因為任何可以透過您的 channel 回覆的人都可以批准或拒絕您工作階段中的工具使用。

若要將這些新增到[公開回覆工具](#expose-a-reply-tool)中組裝的雙向聊天橋接：

**1. 聲明權限功能**

在您的 `Server` 建構函式中，在 `experimental` 下的 `claude/channel` 旁邊新增 `claude/channel/permission: {}`：

```ts theme={null}
capabilities: {
  experimental: {
    'claude/channel': {},
    'claude/channel/permission': {},  // 選擇加入權限中繼
  },
  tools: {},
},
```

**2. 處理傳入要求**

在您的 `Server` 建構函式和 `mcp.connect()` 之間註冊通知處理程式。當權限對話框開啟時，Claude Code 使用[四個要求欄位](#permission-request-fields)呼叫它。您的處理程式為您的平台格式化提示，並包含使用 ID 回覆的指示：

```ts theme={null}
import { z } from 'zod'

// setNotificationHandler 透過方法欄位上的 z.literal 進行路由，
// 所以此 schema 既是驗證器又是分派鍵
const PermissionRequestSchema = z.object({
  method: z.literal('notifications/claude/channel/permission_request'),
  params: z.object({
    request_id: z.string(),     // 五個小寫字母，在您的提示中逐字包含
    tool_name: z.string(),      // 例如 "Bash"、"Write"
    description: z.string(),    // 此呼叫的摘要。視為不受信任。
    input_preview: z.string(),  // 工具引數作為 JSON 形狀的文字。視為不受信任。
  }),
})

mcp.setNotificationHandler(PermissionRequestSchema, async ({ params }) => {
  // send() 是您的出站：POST 到您的聊天平台，或用於本機
  // 測試下面完整範例中顯示的 SSE 廣播。
  send(
    `Claude wants to run ${params.tool_name}: ${params.description}\n` +
    // input_preview 攜帶實際引數；在您有空間時呈現它：對於 Bash，
    // 描述單獨可能只是「Run shell command」，沒有命令詳細資訊
    `${params.input_preview}\n\n` +
    // 指示中的 ID 是您的入站處理程式在步驟 3 中解析的內容
    `Reply "yes ${params.request_id}" or "no ${params.request_id}"`,
  )
})
```

**3. 在您的入站處理程式中攔截判決**

您的入站處理程式是接收來自您的平台的訊息的迴圈或回呼：與您[根據寄件者進行閘道](#gate-inbound-messages)和發出 `notifications/claude/channel` 以將聊天轉發給 Claude 的地方相同。在聊天轉發呼叫之前新增檢查，識別判決格式並改為發出權限通知。

正規表達式符合 Claude Code 生成的 ID 格式：五個字母，永遠不是 `l`。`/i` 旗標容許手機自動更正將回覆大寫；在傳送回之前將擷取的 ID 小寫。

```ts theme={null}
// 符合 "y abcde"、"yes abcde"、"n abcde"、"no abcde"
// [a-km-z] 是 Claude Code 使用的 ID 字母表（小寫，跳過 'l'）
// /i 容許手機自動更正；在傳送前小寫擷取
const PERMISSION_REPLY_RE = /^\s*(y|yes|n|no)\s+([a-km-z]{5})\s*$/i

async function onInbound(message: PlatformMessage) {
  if (!allowed.has(message.from.id)) return  // 首先根據寄件者進行閘道

  const m = PERMISSION_REPLY_RE.exec(message.text)
  if (m) {
    // m[1] 是判決詞，m[2] 是要求 ID
    // 改為將判決通知發出回 Claude Code，而不是聊天
    await mcp.notification({
      method: 'notifications/claude/channel/permission',
      params: {
        request_id: m[2].toLowerCase(),  // 在自動更正大寫的情況下正規化
        behavior: m[1].toLowerCase().startsWith('y') ? 'allow' : 'deny',
      },
    })
    return  // 作為判決處理，不要也轉發為聊天
  }

  // 不符合判決格式：落入正常聊天路徑
  await mcp.notification({
    method: 'notifications/claude/channel',
    params: { content: message.text, meta: { chat_id: String(message.chat.id) } },
  })
}
```

如果遠端回覆沒有作用且本機終端機對話框保持開啟，請檢查以下原因：

* **格式錯誤**：您的入站處理程式的正規表達式無法符合，因此 `approve it` 或 `yes` 之類的文字（沒有 ID）會作為正常訊息落入 Claude。
* **ID 錯誤**：您的伺服器發出判決，但 Claude Code 找不到具有該 ID 的開啟請求並無聲地捨棄它。
* **ID 已被先前的提示使用**：您的伺服器使用請求中的 ID 發出判決，但工作階段中先前的提示具有相同的 ID。一旦 ID 重複，Claude Code 會捨棄任何帶有該 ID 的頻道判決，使針對某個提示的回覆無法核准另一個提示。ID 是五個隨機字母，因此重複的情況很少見。請改為在終端機上回答。

### 完整範例

下面組裝的 `webhook.ts` 結合了本頁的所有三個擴展：回覆工具、寄件者閘道和權限中繼。如果您從這裡開始，您還需要初始逐步解說中的[專案設定和 `.mcp.json` 項目](#example-build-a-webhook-receiver)。

為了使兩個方向都可以從 curl 測試，HTTP 監聽器提供兩個路徑：

* **`GET /events`**：保持 SSE 串流開啟並將每個出站訊息推送為 `data:` 行，因此 `curl -N` 可以即時觀看 Claude 的回覆和權限提示到達。
* **`POST /`**：入站側，與之前相同的處理程式，現在在聊天轉發分支之前插入了判決格式檢查。

```ts title="Full webhook.ts with permission relay" expandable theme={null}
#!/usr/bin/env bun
import { Server } from '@modelcontextprotocol/sdk/server/index.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import { ListToolsRequestSchema, CallToolRequestSchema } from '@modelcontextprotocol/sdk/types.js'
import { z } from 'zod'

// --- 出站：寫入 /events 上任何 curl -N 監聽器 ---
// 真實橋接會改為 POST 到您的聊天平台。
const listeners = new Set<(chunk: string) => void>()
function send(text: string) {
  const chunk = text.split('\n').map(l => `data: ${l}\n`).join('') + '\n'
  for (const emit of listeners) emit(chunk)
}

// 寄件者允許清單。對於本機逐步解說，我們信任單一 X-Sender
// 標頭值 "dev"；真實橋接會檢查平台的使用者 ID。
const allowed = new Set(['dev'])

const mcp = new Server(
  { name: 'webhook', version: '0.0.1' },
  {
    capabilities: {
      experimental: {
        'claude/channel': {},
        'claude/channel/permission': {},  // 選擇加入權限中繼
      },
      tools: {},
    },
    instructions:
      'Messages arrive as <channel source="webhook" chat_id="...">. ' +
      'Reply with the reply tool, passing the chat_id from the tag.',
  },
)

// --- 回覆工具：Claude 呼叫此項以傳送訊息回去 ---
mcp.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [{
    name: 'reply',
    description: 'Send a message back over this channel',
    inputSchema: {
      type: 'object',
      properties: {
        chat_id: { type: 'string', description: 'The conversation to reply in' },
        text: { type: 'string', description: 'The message to send' },
      },
      required: ['chat_id', 'text'],
    },
  }],
}))

mcp.setRequestHandler(CallToolRequestSchema, async req => {
  if (req.params.name === 'reply') {
    const { chat_id, text } = req.params.arguments as { chat_id: string; text: string }
    send(`Reply to ${chat_id}: ${text}`)
    return { content: [{ type: 'text', text: 'sent' }] }
  }
  throw new Error(`unknown tool: ${req.params.name}`)
})

// --- 權限中繼：Claude Code（不是 Claude）在對話框開啟時呼叫此項
const PermissionRequestSchema = z.object({
  method: z.literal('notifications/claude/channel/permission_request'),
  params: z.object({
    request_id: z.string(),
    tool_name: z.string(),
    description: z.string(),
    input_preview: z.string(),
  }),
})

mcp.setNotificationHandler(PermissionRequestSchema, async ({ params }) => {
  send(
    `Claude wants to run ${params.tool_name}: ${params.description}\n` +
    `${params.input_preview}\n\n` +
    `Reply "yes ${params.request_id}" or "no ${params.request_id}"`,
  )
})

await mcp.connect(new StdioServerTransport())

// --- HTTP on :8788：GET /events 串流出站，POST 路由入站 ---
const PERMISSION_REPLY_RE = /^\s*(y|yes|n|no)\s+([a-km-z]{5})\s*$/i
let nextId = 1

Bun.serve({
  port: 8788,
  hostname: '127.0.0.1',
  idleTimeout: 0,  // 不要關閉閒置 SSE 串流
  async fetch(req) {
    const url = new URL(req.url)

    // GET /events：SSE 串流，所以 curl -N 可以即時觀看回覆和提示
    if (req.method === 'GET' && url.pathname === '/events') {
      const stream = new ReadableStream({
        start(ctrl) {
          ctrl.enqueue(': connected\n\n')  // 所以 curl 立即顯示某些內容
          const emit = (chunk: string) => ctrl.enqueue(chunk)
          listeners.add(emit)
          req.signal.addEventListener('abort', () => listeners.delete(emit))
        },
      })
      return new Response(stream, {
        headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' },
      })
    }

    // 其他所有內容都是入站：首先根據寄件者進行閘道
    const body = await req.text()
    const sender = req.headers.get('X-Sender') ?? ''
    if (!allowed.has(sender)) return new Response('forbidden', { status: 403 })

    // 在將其視為聊天之前檢查判決格式
    const m = PERMISSION_REPLY_RE.exec(body)
    if (m) {
      await mcp.notification({
        method: 'notifications/claude/channel/permission',
        params: {
          request_id: m[2].toLowerCase(),
          behavior: m[1].toLowerCase().startsWith('y') ? 'allow' : 'deny',
        },
      })
      return new Response('verdict recorded')
    }

    // 正常聊天：作為 channel 事件轉發給 Claude
    const chat_id = String(nextId++)
    await mcp.notification({
      method: 'notifications/claude/channel',
      params: { content: body, meta: { chat_id, path: url.pathname } },
    })
    return new Response('ok')
  },
})
```

在三個終端機中測試判決路徑。第一個是您的 Claude Code 工作階段，使用[開發旗標](#test-during-the-research-preview)啟動，以便它生成 `webhook.ts`：

```bash theme={null}
claude --dangerously-load-development-channels server:webhook
```

此逐步解說測試權限對話框本身，因此一旦工作階段開啟，按 `Shift+Tab` 直到狀態列顯示 `⏸ manual mode on`。在自動模式中，分類器會決定 `reply` 呼叫而不是您，遠端側不會開啟對話框來回答。

在第二個中，串流出站側，以便您可以看到 Claude 的回覆和任何權限提示在它們觸發時到達：

```bash theme={null}
curl -N localhost:8788/events
```

在第三個中，傳送一條訊息，使 Claude 嘗試執行命令：

```bash theme={null}
curl -d "list the files in this directory" -H "X-Sender: dev" localhost:8788
```

列出檔案是唯讀的，所以 Claude 執行它而不需要批准。當 Claude 呼叫 `reply` 工具以傳送其答案回去時，權限對話框開啟。本機對話框在您的 Claude Code 終端機中開啟，片刻後 `mcp__webhook__reply` 的提示出現在 `/events` 串流中，包括五字母 ID。從遠端側批准它：

```bash theme={null}
curl -d "yes <id>" -H "X-Sender: dev" localhost:8788
```

本機對話框關閉，`reply` 工具執行，Claude 的回覆落入串流中。

此檔案中的三個 channel 特定部分：

* **`Server` 建構函式中的功能**：`claude/channel` 註冊通知監聽器，`claude/channel/permission` 選擇加入權限中繼，`tools` 讓 Claude 發現回覆工具。
* **出站路徑**：`reply` 工具處理程式是 Claude 為對話回應呼叫的；`PermissionRequestSchema` 通知處理程式是 Claude Code 在權限對話框開啟時呼叫的。兩者都呼叫 `send()` 透過 `/events` 廣播，但它們由系統的不同部分觸發。
* **HTTP 處理程式**：`GET /events` 保持 SSE 串流開啟，以便 curl 可以即時觀看出站；`POST` 是入站，根據 `X-Sender` 標頭進行閘道。`yes <id>` 或 `no <id>` 主體作為判決通知進入 Claude Code，永遠不會到達 Claude；其他任何內容都作為 channel 事件轉發給 Claude。

## 打包為外掛程式

若要使您的 channel 可安裝和可共享，請將其包裝在[外掛程式](https://code.claude.com/docs/zh-TW/plugins/overview.md)中並將其發佈到[市場](https://code.claude.com/docs/zh-TW/plugins/overview.md)。使用者使用 `/plugin install` 安裝它，然後使用 `--channels plugin:<name>@<marketplace>` 按工作階段啟用它。

發佈到您自己的市場的 channel 仍然需要 `--dangerously-load-development-channels` 才能執行，因為它不在[核准允許清單](https://code.claude.com/docs/zh-TW/channels.md#supported-channels)上。預設允許清單是 `claude-plugins-official` 中的 channel 外掛程式。社群市場不在 channel 允許清單上。

如果您正在與 Anthropic 合作夥伴聯絡，請與他們聯繫以協調官方市場列表。在 Team 和 Enterprise 計劃上，管理員可以改為將您的外掛程式包含在組織自己的 [`allowedChannelPlugins`](https://code.claude.com/docs/zh-TW/channels#restrict-which-channel-plugins-can-run) 清單中，該清單取代預設 Anthropic 允許清單。

## 另請參閱

* [Channels](https://code.claude.com/docs/zh-TW/channels.md) 安裝並使用 Telegram、Discord、iMessage 或 fakechat 演示，以及為 Team 或 Enterprise 組織啟用 channels
* [工作 channel 實現](https://github.com/anthropics/claude-plugins-official/tree/main/external_plugins)以取得具有配對流程、回覆工具和檔案附件的完整伺服器程式碼
* [MCP](https://code.claude.com/docs/zh-TW/mcp.md) 用於 channel 伺服器實現的基礎協議
* [外掛程式](https://code.claude.com/docs/zh-TW/plugins/overview.md) 打包您的 channel，以便使用者可以使用 `/plugin install` 安裝它

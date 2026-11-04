<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/agent-sdk/mcp | lastmod: 2026-10-22 | section: Agent SDK / Extend with tools -->
> 來源：https://code.claude.com/docs/zh-TW/agent-sdk/mcp（官方 zh-TW，lastmod 2026-10-22）｜分類：Agent SDK › Extend with tools｜EN 摘要：Configure MCP servers to extend your agent with external tools. Covers transport types, tool search for large tool sets, authentication, and error handling.

# 使用 MCP 連接外部工具

> 配置 MCP 伺服器以擴展您的代理程式的外部工具。涵蓋傳輸類型、大型工具集的工具搜尋、身份驗證和錯誤處理。

[Model Context Protocol (MCP)](https://modelcontextprotocol.io/docs/getting-started/intro) 是一個開放標準，用於將 AI 代理程式連接到外部工具和資料來源。使用 MCP，您的代理程式可以查詢資料庫、與 Slack 和 GitHub 等 API 整合，以及連接到其他服務，而無需編寫自訂工具實現。

MCP 伺服器可以作為本地進程運行、通過 HTTP 連接或直接在您的 SDK 應用程式中執行。

> [!NOTE]
>
> 本頁涵蓋 Agent SDK 的 MCP 配置。若要將 MCP 伺服器添加到 Claude Code CLI 以便在每個項目中加載，請參閱 [MCP 安裝範圍](https://code.claude.com/docs/zh-TW/mcp.md#mcp-installation-scopes)。

## 快速開始

此範例使用 [HTTP 傳輸](#http%2Fsse-servers) 連接到 [Claude Code 文件](https://code.claude.com/docs) MCP 伺服器，並使用 [`allowedTools`](#allow-mcp-tools) 搭配萬用字元來允許來自伺服器的所有工具。

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  prompt: "Use the docs MCP server to explain what hooks are in Claude Code",
  options: {
    mcpServers: {
      "claude-code-docs": {
        type: "http",
        url: "https://code.claude.com/docs/mcp"
      }
    },
    allowedTools: ["mcp__claude-code-docs__*"]
  }
})) {
  if (message.type === "result" && message.subtype === "success") {
    console.log(message.result);
  }
}
```

```python Python theme={null}
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage


async def main():
    options = ClaudeAgentOptions(
        mcp_servers={
            "claude-code-docs": {
                "type": "http",
                "url": "https://code.claude.com/docs/mcp",
            }
        },
        allowed_tools=["mcp__claude-code-docs__*"],
    )

    async for message in query(
        prompt="Use the docs MCP server to explain what hooks are in Claude Code",
        options=options,
    ):
        if isinstance(message, ResultMessage) and message.subtype == "success":
            print(message.result)


asyncio.run(main())
```

代理程式連接到文件伺服器，搜尋有關 hooks 的資訊，並傳回結果。

## 新增 MCP 伺服器

您可以在呼叫 `query()` 時在程式碼中設定 MCP 伺服器，或在透過 [`settingSources`](#from-a-config-file) 載入的 `.mcp.json` 檔案中設定。

### 在程式碼中新增伺服器

在 `mcpServers` 選項中直接傳遞 MCP 伺服器。此範例會為 `/Users/me/projects` 啟動本機檔案系統 MCP 伺服器。請將該路徑替換為您機器上的目錄：

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  prompt: "List files in my project",
  options: {
    mcpServers: {
      filesystem: {
        command: "npx",
        args: ["-y", "@modelcontextprotocol/server-filesystem", "/Users/me/projects"]
      }
    },
    allowedTools: ["mcp__filesystem__*"]
  }
})) {
  if (message.type === "result" && message.subtype === "success") {
    console.log(message.result);
  }
}
```

```python Python theme={null}
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage


async def main():
    options = ClaudeAgentOptions(
        mcp_servers={
            "filesystem": {
                "command": "npx",
                "args": [
                    "-y",
                    "@modelcontextprotocol/server-filesystem",
                    "/Users/me/projects",
                ],
            }
        },
        allowed_tools=["mcp__filesystem__*"],
    )

    async for message in query(prompt="List files in my project", options=options):
        if isinstance(message, ResultMessage) and message.subtype == "success":
            print(message.result)


asyncio.run(main())
```

### 從設定檔新增伺服器

在您的專案根目錄建立 `.mcp.json` 檔案。當啟用 `project` 設定來源時，該檔案會被選取，預設 `query()` 選項已啟用此功能。如果您明確設定 `settingSources`，請包含 `"project"` 以便載入此檔案。請將 `/Users/me/projects` 替換為您機器上的目錄：

```json theme={null}
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/Users/me/projects"]
    }
  }
}
```

## 連線時序

Claude Code 會在工作階段開始時開始連線您的 MCP 伺服器，並在第一回合的等待（如果有的話）結束後發送 [init 訊息](#error-handling)。第一回合等待伺服器的時間長短，取決於您在何處設定該伺服器。如果您設定了 `permissionPromptToolName`，無論您在何處設定該工具的伺服器，第一回合一律會等待它，最多等待 `MCP_TIMEOUT`。

對於 `options.mcpServers` 中的伺服器，請在第一欄中找到其類型，以查看第一回合會等待它多久。

| 伺服器類型 | 延遲第一輪？ | 第一輪等待逾時 |
| :- | :- | :- |
| stdio 伺服器，或沒有快取工具清單的 HTTP/SSE 伺服器 | 是，直到連線為止 | [`MCP_TIMEOUT`](https://code.claude.com/docs/zh-TW/env-vars)，預設為 30 秒；連線在該期限失敗 |
| 具有快取工具清單的遠端伺服器，由 Claude Code 從先前的連線儲存 | 否；快取的工具從第一輪開始可用 | 無；在其第一次工具呼叫時連線，該延遲連線有其自己的逾時 |
| 同處理序 [SDK 伺服器](#sdk-mcp-servers) | 是，直到連線並列出其工具為止 | [`MCP_TIMEOUT`](https://code.claude.com/docs/zh-TW/env-vars)，預設為 30 秒，每次連線嘗試；連線在該期限失敗 |

只有在 [MCP 探索快取](https://code.claude.com/docs/zh-TW/mcp.md#server-status-detail) 開啟時，伺服器才會有快取的工具清單。

來自 [設定檔](#from-a-config-file)（例如 `.mcp.json`）或來自外掛的伺服器，通常在 init 訊息中仍顯示 `pending`。第一回合等待這些伺服器的時間長短，取決於 `options.mcpServers` 和工具搜尋：

* **`options.mcpServers` 包含 stdio、HTTP 或 SSE 伺服器**：第一回合也會等待待處理的設定檔伺服器和外掛伺服器，最多等待 `MCP_TIMEOUT`。
* **否則，當 `ANTHROPIC_BASE_URL` 指向 [閘道](https://code.claude.com/docs/zh-TW/mcp.md#tool-search-through-a-gateway) 且未設定 [`ENABLE_TOOL_SEARCH`](https://code.claude.com/docs/zh-TW/mcp#configure-tool-search) 時**：第一回合會為每個待處理的設定檔伺服器和外掛伺服器等待最多 2 秒。
* **否則，在 [工具搜尋](https://code.claude.com/docs/zh-TW/agent-sdk/tool-search.md) 開啟時（此為預設）**：第一回合最多等待 2 秒，且僅等待設定了 [`alwaysLoad: true`](https://code.claude.com/docs/zh-TW/mcp#exempt-a-server-from-deferral) 或您已[指名](#named-servers)的待處理伺服器。其餘伺服器會在背景中繼續連線，Claude 會在它們連線後[存取其工具](https://code.claude.com/docs/zh-TW/mcp.md#tool-availability)。
* **否則，在工具搜尋關閉時**：第一回合會為每個待處理的設定檔伺服器和外掛伺服器等待最多 2 秒。當您的 [`ENABLE_TOOL_SEARCH` 值或模型](https://code.claude.com/docs/zh-TW/agent-sdk/tool-search#configure-tool-search) 將工具搜尋關閉，或當您排除 `ToolSearch` 工具（例如透過 `disallowedTools`）時，工具搜尋即為關閉。

### 已指名伺服器

您可以在 [`allowedTools`](#allow-mcp-tools) 中，或在 `settings` 選項的 `permissions.allow` 規則中，列出伺服器的任一工具（例如 `mcp__github__list_issues` 或 `mcp__github__*`），藉此指名該伺服器。當您在提示提交、工具使用、權限、subagent、任務、elicitation 或 worktree 事件上設定 [`mcp_tool` hook](https://code.claude.com/docs/zh-TW/hooks#mcp-tool-hook-fields) 時，它也會指名其所呼叫的伺服器。在 v2.1.284 之前，指名伺服器對第一回合等待沒有影響。

### 自行設定第一回合等待時間

若要自行選擇第一回合等待時間，請在 [`env` 選項](https://code.claude.com/docs/zh-TW/agent-sdk/configuration#set-environment-variables) 中設定 `CLAUDE_CODE_MCP_STARTUP_WAIT_MS`，例如 `CLAUDE_CODE_MCP_STARTUP_WAIT_MS: "5000"`。無論工具搜尋是否開啟，第一回合隨後都會為待處理的設定檔伺服器和外掛伺服器等待最多該毫秒數。相同的期限也會取代 `options.mcpServers` 中 stdio、HTTP 和 SSE 伺服器的 `MCP_TIMEOUT` 等待。

無論您設定的值為何（包括 `0`），下列三種等待都會套用：

* **`permissionPromptToolName` 伺服器**：最多等待 `MCP_TIMEOUT`。
* **同處理序 [SDK 伺服器](#sdk-mcp-servers)**：每次連線嘗試最多等待 `MCP_TIMEOUT`。
* **仍在連線中的[已指名伺服器](#named-servers)**：至少等待最多 2 秒，因此低於 `2000` 的值不會縮短其等待時間。

將變數設定為 `0` 即可跳過其他所有伺服器的等待。等待結束時仍待處理的伺服器會在背景中繼續連線。`CLAUDE_CODE_MCP_STARTUP_WAIT_MS` 需要 Claude Code v2.1.274 或更新版本。

### 讓啟動等待伺服器

有兩項設定會讓啟動本身在 Claude Code 發送 init 訊息之前等待：

* **將 [`MCP_CONNECTION_NONBLOCKING`](https://code.claude.com/docs/zh-TW/env-vars) 設定為 `0`**：啟動會等待整個連線批次，預設上限為 5 秒。設定 [`MCP_CONNECT_TIMEOUT_MS`](https://code.claude.com/docs/zh-TW/env-vars)（單位為毫秒）即可變更該上限。達到上限時仍待處理的伺服器會在背景中繼續連線。
* **在伺服器的設定上使用 `alwaysLoad: true`**：啟動會為該伺服器的工具等待最多相同的上限，讓第一回合能以完整 schema 取得這些工具，並[豁免於工具搜尋延遲](https://code.claude.com/docs/zh-TW/mcp.md#exempt-a-server-from-deferral)。具有快取工具清單的遠端伺服器會在不連線、也不阻擋啟動的情況下提供這些工具。

init 訊息會報告 Claude Code 發送該訊息當下每個伺服器的狀態。

## 允許 MCP 工具

MCP 工具需要明確的許可權才能讓 Claude 使用。沒有許可權的情況下，Claude 會看到工具可用，但無法呼叫它們。

### 工具命名慣例

MCP 工具的名稱為 `mcp__<server-name>__<tool-name>`，其中 `<server-name>` 是您註冊伺服器時使用的名稱，例如它在 `mcpServers` 中的鍵。

伺服器名稱中的 `.` 和空格等字元會被替換為 `_`。下表顯示了兩個伺服器鍵下 `list_issues` 工具的完整名稱：

| `mcpServers` 中的鍵 | 完整工具名稱 |
| :- | :- |
| `github` | `mcp__github__list_issues` |
| `my.server` | `mcp__my_server__list_issues` |

請在 `allowedTools` 和 [MCP 權限規則](https://code.claude.com/docs/zh-TW/permissions.md#mcp)中使用完整的工具名稱。對於由[外掛](https://code.claude.com/docs/zh-TW/agent-sdk/plugins.md)提供的伺服器，`<server-name>` 採用[外掛範圍形式](https://code.claude.com/docs/zh-TW/mcp.md#plugin-provided-mcp-servers)，並以 `plugin_` 開頭。

### 使用 allowedTools 自動批准

使用 `allowedTools` 自動批准特定的 MCP 工具，讓 Claude 可以在不需要許可權提示的情況下使用它們：

```typescript TypeScript hidelines={1,-1} theme={null}
const _ = {
  options: {
    mcpServers: {
      // your servers
    },
    allowedTools: [
      "mcp__github__*", // All tools from the github server
      "mcp__db__query", // Only the query tool from db server
      "mcp__slack__send_message" // Only send_message from slack server
    ]
  }
};
```

```python Python theme={null}
options = ClaudeAgentOptions(
    mcp_servers={
        # your servers
    },
    allowed_tools=[
        "mcp__github__*",  # All tools from the github server
        "mcp__db__query",  # Only the query tool from db server
        "mcp__slack__send_message",  # Only send_message from slack server
    ],
)
```

萬用字元 (`*`) 讓您可以允許伺服器中的所有工具，而無需逐一列出每個工具。

> [!NOTE]
>
> **對於 MCP 存取，優先使用 `allowedTools` 而不是許可權模式。** `permissionMode: "acceptEdits"` 不會自動批准 MCP 工具（只有檔案編輯和檔案系統 Bash 命令）。`permissionMode: "bypassPermissions"` 會自動批准 MCP 工具，但也會停用大多數其他安全提示，這比必要的範圍更廣；請參閱[如何評估許可權](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#how-permissions-are-evaluated)以了解保留的提示。`allowedTools` 中的萬用字元只授予您想要的 MCP 伺服器，不會授予其他任何東西。請參閱[許可權模式](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#permission-modes)以進行完整比較。

### 探索可用工具

若要查看 MCP 伺服器提供的工具，請檢查伺服器的文件或檢查 `system` 初始化訊息中的 `tools` 陣列。MCP 工具名稱以 `mcp__` 開頭。

Claude Code 在 `options.mcpServers` 中傳遞的伺服器的[首次連線等待](#connection-timing)之後發出初始化訊息，因此 `tools` 陣列列出了到那時已連線的每個伺服器的 `mcp__` 工具，以及具有[快取工具清單](#connection-timing)的伺服器的工具，這些伺服器在首次使用時連線。任何其他尚未連線的伺服器的工具不存在；請參閱[錯誤處理](#error-handling)以讀取每個伺服器的狀態。

此篩選器會列印 MCP 工具名稱：

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

const options = {
  mcpServers: {
    // your servers
  },
};

for await (const message of query({ prompt: "...", options })) {
  if (message.type === "system" && message.subtype === "init") {
    const mcpTools = message.tools.filter((name) => name.startsWith("mcp__"));
    console.log("Available MCP tools:", mcpTools);
  }
}
```

```python Python theme={null}
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, SystemMessage


async def main():
    options = ClaudeAgentOptions(
        mcp_servers={
            # your servers
        },
    )
    async for message in query(prompt="...", options=options):
        if isinstance(message, SystemMessage) and message.subtype == "init":
            mcp_tools = [t for t in message.data.get("tools", []) if t.startswith("mcp__")]
            print("Available MCP tools:", mcp_tools)


asyncio.run(main())
```

您也可以要求 Claude 列出伺服器提供的可用工具。

## 傳輸類型

MCP 伺服器使用不同的傳輸協議與您的代理進行通訊。請查看伺服器的文件以了解它支援哪種傳輸：

* 如果文件提供您一個**要執行的命令**（例如 `npx @modelcontextprotocol/server-filesystem`），請使用 stdio
* 如果文件提供您一個 **URL**，請使用 HTTP 或 SSE
* 如果您在程式碼中建立自己的工具，請使用 SDK MCP 伺服器

### stdio 伺服器

透過 stdin/stdout 進行通訊的本機程序。將此用於在同一台機器上執行的 MCP 伺服器。對於 `.mcp.json` 形式，請使用 [從設定檔新增伺服器](#from-a-config-file) 中顯示的相同欄位。在程式碼中，傳遞命令及其引數。將 `/Users/me/projects` 替換為您機器上的目錄：

```typescript TypeScript hidelines={1,-1} theme={null}
const _ = {
  options: {
    mcpServers: {
      filesystem: {
        command: "npx",
        args: ["-y", "@modelcontextprotocol/server-filesystem", "/Users/me/projects"]
      }
    },
    allowedTools: ["mcp__filesystem__read_file", "mcp__filesystem__list_directory"]
  }
};
```

```python Python theme={null}
options = ClaudeAgentOptions(
    mcp_servers={
        "filesystem": {
            "command": "npx",
            "args": [
                "-y",
                "@modelcontextprotocol/server-filesystem",
                "/Users/me/projects",
            ],
        }
    },
    allowed_tools=["mcp__filesystem__read_file", "mcp__filesystem__list_directory"],
)
```

### HTTP/SSE 伺服器

將 HTTP 或 SSE 用於雲端託管的 MCP 伺服器和遠端 API。對於 `.mcp.json` 形式，請使用與 [HTTP headers for remote servers](#http-headers-for-remote-servers) 中的範例相同的欄位，對於 SSE 伺服器使用 `"type": "sse"`。在程式碼中，傳遞伺服器的 URL：

```typescript TypeScript hidelines={1,-1} theme={null}
const _ = {
  options: {
    mcpServers: {
      "remote-api": {
        type: "sse",
        url: "https://api.example.com/mcp/sse",
        headers: {
          Authorization: `Bearer ${process.env.API_TOKEN}`
        }
      }
    },
    allowedTools: ["mcp__remote-api__*"]
  }
};
```

```python Python theme={null}
options = ClaudeAgentOptions(
    mcp_servers={
        "remote-api": {
            "type": "sse",
            "url": "https://api.example.com/mcp/sse",
            "headers": {"Authorization": f"Bearer {os.environ['API_TOKEN']}"},
        }
    },
    allowed_tools=["mcp__remote-api__*"],
)
```

對於可串流的 HTTP 傳輸，請改用 `"type": "http"`。在 `.mcp.json` 和其他 JSON 設定檔中，`"streamable-http"` 被接受為 `"http"` 的別名。SDK 的 `McpHttpServerConfig` 類型僅宣告 `"http"`，因此對於您在程式碼中傳遞的伺服器，請使用 `"http"`。

### SDK MCP 伺服器

直接在您的應用程式程式碼中定義自訂工具，而不是執行單獨的伺服器程序。請參閱 [custom tools guide](https://code.claude.com/docs/zh-TW/agent-sdk/custom-tools.md) 以了解實作詳細資訊。

由 [`initialize` 控制請求](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#sdkcontrolinitializeresponse) 註冊的 SDK MCP 伺服器在 Claude Code 處理該請求後立即開始連接。

## MCP 工具搜尋

當您設定了許多 MCP 工具時，工具定義可能會佔用您的內容視窗的很大一部分。工具搜尋透過從內容中隱藏工具定義，並且只在每個回合中載入 Claude 需要的工具來解決這個問題。

工具搜尋預設為啟用。請參閱[工具搜尋](https://code.claude.com/docs/zh-TW/agent-sdk/tool-search.md)以了解設定選項、最佳實踐，以及如何在自訂 SDK 工具中使用工具搜尋。

## 驗證

大多數 MCP 伺服器需要驗證才能存取外部服務。透過伺服器設定中的環境變數傳遞認證資訊。

### 透過環境變數傳遞認證資訊

使用 `env` 欄位將 API 金鑰、權杖和其他認證資訊傳遞給 MCP 伺服器：

> [tab] In code
>
> ```typescript TypeScript hidelines={1,-1} theme={null}
> const _ = {
>   options: {
>     mcpServers: {
>       "api-server": {
>         command: "npx",
>         args: ["-y", "@your-org/api-mcp-server"],
>         env: {
>           API_KEY: process.env.API_KEY
>         }
>       }
>     },
>     allowedTools: ["mcp__api-server__*"]
>   }
> };
> ```
>
> ```python Python theme={null}
> options = ClaudeAgentOptions(
>     mcp_servers={
>         "api-server": {
>             "command": "npx",
>             "args": ["-y", "@your-org/api-mcp-server"],
>             "env": {"API_KEY": os.environ["API_KEY"]},
>         }
>     },
>     allowed_tools=["mcp__api-server__*"],
> )
> ```

> [tab] .mcp.json
>
> ```json theme={null}
> {
>   "mcpServers": {
>     "api-server": {
>       "command": "npx",
>       "args": ["-y", "@your-org/api-mcp-server"],
>       "env": {
>         "API_KEY": "${API_KEY}"
>       }
>     }
>   }
> }
> ```
>
> `${API_KEY}` 語法會在執行時展開環境變數。

### 遠端伺服器的 HTTP 標頭

對於 HTTP 和 SSE 伺服器，直接在伺服器設定中傳遞驗證標頭：

> [tab] In code
>
> ```typescript TypeScript hidelines={1,-1} theme={null}
> const _ = {
>   options: {
>     mcpServers: {
>       "secure-api": {
>         type: "http",
>         url: "https://api.example.com/mcp",
>         headers: {
>           Authorization: `Bearer ${process.env.API_TOKEN}`
>         }
>       }
>     },
>     allowedTools: ["mcp__secure-api__*"]
>   }
> };
> ```
>
> ```python Python theme={null}
> options = ClaudeAgentOptions(
>     mcp_servers={
>         "secure-api": {
>             "type": "http",
>             "url": "https://api.example.com/mcp",
>             "headers": {"Authorization": f"Bearer {os.environ['API_TOKEN']}"},
>         }
>     },
>     allowed_tools=["mcp__secure-api__*"],
> )
> ```

> [tab] .mcp.json
>
> ```json theme={null}
> {
>   "mcpServers": {
>     "secure-api": {
>       "type": "http",
>       "url": "https://api.example.com/mcp",
>       "headers": {
>         "Authorization": "Bearer ${API_TOKEN}"
>       }
>     }
>   }
> }
> ```
>
> `${API_TOKEN}` 語法會在執行時展開環境變數。

如需使用標頭進行驗證的遠端伺服器完整工作範例，請參閱[從儲存庫列出議題](#list-issues-from-a-repository)。

### OAuth2 驗證

[MCP 規格支援 OAuth 2.1](https://modelcontextprotocol.io/specification/2025-03-26/basic/authorization) 進行授權。SDK 不會開啟瀏覽器或執行互動式 OAuth 流程。當已設定的伺服器傳回授權挑戰，而 Claude Code 沒有可傳送的 token 時，SDK 會將該伺服器回報為 `needs-auth` 或 `failed`：

* **`needs-auth`**：Claude Code 找不到可用於該伺服器的登入資訊。請在 `headers` 中傳遞 token，或在執行前於同一台機器上[從互動式 Claude Code 工作階段登入](https://code.claude.com/docs/zh-TW/mcp.md#authenticate-with-remote-mcp-servers)。
* **`failed`**，且其 [`McpServerStatus`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#mcpserverstatus) 項目中的 `error` 以 `Couldn't read the stored credentials` 或 `A request to MCP server` 開頭：Claude Code 無法讀取其憑證儲存區。如需處理方式，請參閱 [Couldn't read the stored credentials for MCP server](https://code.claude.com/docs/zh-TW/errors.md#couldnt-read-the-stored-credentials-for-mcp-server)。在 Claude Code v2.1.307 之前，當 Mac 的登入鑰匙圈被鎖定時，狀態會改為 `needs-auth`。

無論哪種情況，agent 執行都會在沒有該伺服器工具的情況下繼續。[系統初始化訊息](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md#sdksystemmessage)的 `mcp_servers` 陣列在發出時可能仍會針對該伺服器顯示 `pending`。若要確認伺服器是否需要憑證，請在 TypeScript SDK 中輪詢 `mcpServerStatus()`，或在 Python 中輪詢 [`get_mcp_status()`](https://code.claude.com/docs/zh-TW/agent-sdk/python#methods)。

若要提供認證資訊，請在您的應用程式中完成 OAuth 流程，並在伺服器的 `headers` 中傳遞產生的存取權杖：

```typescript TypeScript theme={null}
// After completing OAuth flow in your app.
// Implement getAccessTokenFromOAuthFlow for your OAuth provider.
const accessToken = await getAccessTokenFromOAuthFlow();

const options = {
  mcpServers: {
    "oauth-api": {
      type: "http",
      url: "https://api.example.com/mcp",
      headers: {
        Authorization: `Bearer ${accessToken}`
      }
    }
  },
  allowedTools: ["mcp__oauth-api__*"]
};
```

```python Python theme={null}
# After completing OAuth flow in your app.
# Implement get_access_token_from_oauth_flow for your OAuth provider.
access_token = await get_access_token_from_oauth_flow()

options = ClaudeAgentOptions(
    mcp_servers={
        "oauth-api": {
            "type": "http",
            "url": "https://api.example.com/mcp",
            "headers": {"Authorization": f"Bearer {access_token}"},
        }
    },
    allowed_tools=["mcp__oauth-api__*"],
)
```

## 範例

### 列出儲存庫中的議題

此範例連接到遠端 [GitHub MCP 伺服器](https://github.com/github/github-mcp-server)以列出最近的議題。此範例包含除錯日誌以驗證 MCP 連接和工具呼叫。

執行前，請建立一個 [GitHub 個人存取令牌](https://github.com/settings/personal-access-tokens)，具有對您想查詢的儲存庫的讀取存取權限，並將其設定為環境變數：

```bash theme={null}
export GITHUB_TOKEN=YOUR_GITHUB_PAT
```

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  prompt: "List the 3 most recent issues in anthropics/claude-code",
  options: {
    mcpServers: {
      github: {
        type: "http",
        url: "https://api.githubcopilot.com/mcp/",
        headers: {
          Authorization: `Bearer ${process.env.GITHUB_TOKEN}`
        }
      }
    },
    allowedTools: ["mcp__github__list_issues"]
  }
})) {
  // Verify MCP server connected successfully
  if (message.type === "system" && message.subtype === "init") {
    console.log("MCP servers:", message.mcp_servers);
  }

  // Log when Claude calls an MCP tool
  if (message.type === "assistant") {
    for (const block of message.message.content) {
      if (block.type === "tool_use" && block.name.startsWith("mcp__")) {
        console.log("MCP tool called:", block.name);
      }
    }
  }

  // Print the final result
  if (message.type === "result" && message.subtype === "success") {
    console.log(message.result);
  }
}
```

```python Python theme={null}
import asyncio
import os
from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    ResultMessage,
    SystemMessage,
    AssistantMessage,
)


async def main():
    options = ClaudeAgentOptions(
        mcp_servers={
            "github": {
                "type": "http",
                "url": "https://api.githubcopilot.com/mcp/",
                "headers": {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"},
            }
        },
        allowed_tools=["mcp__github__list_issues"],
    )

    async for message in query(
        prompt="List the 3 most recent issues in anthropics/claude-code",
        options=options,
    ):
        # Verify MCP server connected successfully
        if isinstance(message, SystemMessage) and message.subtype == "init":
            print("MCP servers:", message.data.get("mcp_servers"))

        # Log when Claude calls an MCP tool
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if hasattr(block, "name") and block.name.startswith("mcp__"):
                    print("MCP tool called:", block.name)

        # Print the final result
        if isinstance(message, ResultMessage) and message.subtype == "success":
            print(message.result)


asyncio.run(main())
```

在 `MCP servers:` 行中，`github` 的 `status` 為 `connected` 確認令牌有效。如果 Claude Code 對伺服器有 [快取的工具清單](#connection-timing)，狀態可能改為 `pending`，伺服器會在首次工具呼叫時連接。如果狀態為 `failed` 或 `needs-auth`，請在信任結果前參閱 [錯誤處理](#error-handling)，因為當伺服器無法使用時，Claude 可能會回退到內建工具。

### 查詢資料庫

此範例使用 [DBHub](https://github.com/bytebase/dbhub) 查詢 Postgres 資料庫。代理程式會自動探索資料庫結構描述、撰寫 SQL 查詢並傳回結果。

DBHub 的 `execute_sql` 工具會執行代理程式發出的任何 SQL，包括寫入，除非您限制它。在 [DBHub 設定檔](https://dbhub.ai/config/toml)中設定 `readonly = true` 會使 DBHub 拒絕 `INSERT`、`UPDATE`、`DELETE` 和 DDL 陳述式，因此即使代理程式發出寫入，此範例也無法修改您的資料。DBHub 在載入設定時會從程序環境解析 `${DATABASE_URL}`，因此連接字串保持在檔案外。在您的指令碼旁邊建立此 `dbhub.toml`：

```toml dbhub.toml theme={null}
[[sources]]
id = "production"
dsn = "${DATABASE_URL}"

[[tools]]
name = "execute_sql"
source = "production"
readonly = true
```

指令碼隨後會指向 DBHub 的設定檔，而不是直接傳遞連接字串。執行前，請將 `DATABASE_URL` 環境變數設定為您的連接字串。將預留位置值替換為您自己的資料庫詳細資訊：

```bash theme={null}
export DATABASE_URL=postgresql://user:password@localhost:5432/mydb
```

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  // Natural language query - Claude writes the SQL
  prompt: "How many users signed up last week? Break it down by day.",
  options: {
    mcpServers: {
      postgres: {
        command: "npx",
        // dbhub.toml sets readonly = true, so execute_sql rejects writes
        args: ["-y", "@bytebase/dbhub", "--config", "dbhub.toml"]
      }
    },
    allowedTools: ["mcp__postgres__execute_sql"]
  }
})) {
  if (message.type === "result" && message.subtype === "success") {
    console.log(message.result);
  }
}
```

```python Python theme={null}
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage


async def main():
    options = ClaudeAgentOptions(
        mcp_servers={
            "postgres": {
                "command": "npx",
                # dbhub.toml sets readonly = true, so execute_sql rejects writes
                "args": [
                    "-y",
                    "@bytebase/dbhub",
                    "--config",
                    "dbhub.toml",
                ],
            }
        },
        allowed_tools=["mcp__postgres__execute_sql"],
    )

    # Natural language query - Claude writes the SQL
    async for message in query(
        prompt="How many users signed up last week? Break it down by day.",
        options=options,
    ):
        if isinstance(message, ResultMessage) and message.subtype == "success":
            print(message.result)


asyncio.run(main())
```

## 錯誤處理

MCP 伺服器可能因各種原因連線失敗：伺服器程序可能未安裝、認證資訊可能無效，或遠端伺服器可能無法連線。

Claude Code 在每個查詢開始時會發出一個 `system` 訊息，其子類型為 `init`。此訊息包含每個 MCP 伺服器的連線狀態。`status` 欄位可以是 `"pending"`、`"connected"`、`"failed"`、`"needs-auth"` 或 `"disabled"`。Claude Code 在 [首次轉換連線等待](#connection-timing) 之後發出 init 訊息，針對在 `options.mcpServers` 中傳遞的伺服器，因此在等待期間連線的伺服器會顯示 `"connected"`。

在 init 訊息中，不要將 `"pending"` 本身視為失敗。它可能表示以下任何情況：

* 伺服器尚未連線。請參閱 [Claude Code 在首次轉換前等待多長時間](#connection-timing)
* 伺服器的工具清單是 [從快取提供](#connection-timing)，連線在首次使用時建立
* 連線期限已過期。此類伺服器根據時序報告 `"pending"` 或 `"failed"`

檢查 `"failed"` 或 `"needs-auth"` 以偵測無法使用的伺服器：

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

try {
  for await (const message of query({
    prompt: "Process data",
    options: {
      mcpServers: {
        // Replace dataServer with your server configuration
        "data-processor": dataServer
      }
    }
  })) {
    if (message.type === "system" && message.subtype === "init") {
      const unavailableServers = message.mcp_servers.filter(
        (s) => s.status === "failed" || s.status === "needs-auth"
      );

      if (unavailableServers.length > 0) {
        console.warn("Unavailable MCP servers:", unavailableServers);
      }
    }

    if (message.type === "result" && message.subtype === "error_during_execution") {
      console.error("Execution failed");
    }
  }
} catch (error) {
  // A single-shot query() throws after yielding an error result. If the
  // failure was an error result, the error subtype branch above has
  // already run; a failure to start or reach the Claude Code process
  // yields no result message. MCP servers that fail to connect don't
  // throw: use the status check above, and note that servers still
  // "pending" at init need a later status check.
  console.log(`Session ended with an error: ${error}`);
}
```

```python Python theme={null}
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, SystemMessage, ResultMessage


async def main():
    # Replace data_server with your server configuration
    options = ClaudeAgentOptions(mcp_servers={"data-processor": data_server})

    try:
        async for message in query(prompt="Process data", options=options):
            if isinstance(message, SystemMessage) and message.subtype == "init":
                unavailable_servers = [
                    s
                    for s in message.data.get("mcp_servers", [])
                    if s.get("status") in ("failed", "needs-auth")
                ]

                if unavailable_servers:
                    print(f"Unavailable MCP servers: {unavailable_servers}")

            if (
                isinstance(message, ResultMessage)
                and message.subtype == "error_during_execution"
            ):
                print("Execution failed")
    except Exception as error:
        # A single-shot query() raises after yielding an error result. If the
        # failure was an error result, the error subtype branch above has
        # already run; a failure to start or reach the Claude Code process
        # yields no result message. MCP servers that fail to connect don't
        # raise: use the status check above, and note that servers still
        # "pending" at init need a later status check.
        print(f"Session ended with an error: {error}")


asyncio.run(main())
```

遠端伺服器的狀態在報告 `"connected"` 後也可能變更。當連線在工作階段中途中斷時，Claude Code 會在 [重新連線](https://code.claude.com/docs/zh-TW/mcp.md#automatic-reconnection) 時將伺服器移回 `"pending"`。稍後在 TypeScript 中呼叫 `mcpServerStatus()`，或在 Python 中呼叫 [`ClaudeSDKClient.get_mcp_status()`](https://code.claude.com/docs/zh-TW/agent-sdk/python#methods)，可能會針對您之前看到已連線的伺服器報告 `"pending"`，而您這一方沒有進行任何設定變更。

在五次重新連線嘗試失敗後，伺服器會報告 `"failed"`，或在需要再次授權時報告 `"needs-auth"`。處於 `"failed"` 狀態的 HTTP 或 SSE 伺服器仍可能在您未進行任何呼叫的情況下恢復為 `"connected"`，因為 Claude Code 在發生暫時性錯誤後會持續 [在背景重試](https://code.claude.com/docs/zh-TW/mcp.md#mid-session-drops-of-a-remote-server)。若要手動重試，請在 TypeScript 中呼叫 [`reconnectMcpServer()`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#methods)，或在 Python 中呼叫 [`ClaudeSDKClient.reconnect_mcp_server()`](https://code.claude.com/docs/zh-TW/agent-sdk/python#methods)。

## 故障排除

### 伺服器顯示「失敗」狀態

檢查 `init` 訊息以查看哪些伺服器連線失敗：

```typescript TypeScript theme={null}
if (message.type === "system" && message.subtype === "init") {
  for (const server of message.mcp_servers) {
    if (server.status === "failed") {
      console.error(`Server ${server.name} failed to connect`);
    }
  }
}
```

```python Python theme={null}
if isinstance(message, SystemMessage) and message.subtype == "init":
    for server in message.data.get("mcp_servers", []):
        if server.get("status") == "failed":
            print(f"Server {server['name']} failed to connect")
```

`"pending"` 狀態並不表示伺服器失敗。請參閱[錯誤處理](#error-handling)以了解它在初始化時涵蓋的情況。若要在工作階段稍後取得更新的狀態，請在 TypeScript SDK 中呼叫查詢的 `mcpServerStatus()` 方法，或在 Python 中呼叫 [`ClaudeSDKClient.get_mcp_status()`](https://code.claude.com/docs/zh-TW/agent-sdk/python#methods)。

常見原因：

* **遺漏環境變數**：確保已設定必要的權杖和認證。對於 stdio 伺服器，檢查 `env` 欄位是否符合伺服器的預期。
* **伺服器未安裝**：對於 `npx` 命令，驗證套件是否存在且 Node.js 是否在您的 PATH 中。
* **無效的連線字串**：對於資料庫伺服器，驗證連線字串格式以及資料庫是否可存取。
* **網路問題**：對於遠端 HTTP/SSE 伺服器，檢查 URL 是否可到達以及任何防火牆是否允許連線。

### 工具未被呼叫

如果 Claude 看到工具但未使用它們，請檢查您是否已使用 `allowedTools` 授予權限：

```typescript TypeScript hidelines={1,-1} theme={null}
const _ = {
  options: {
    mcpServers: {
      // your servers
    },
    allowedTools: ["mcp__servername__*"] // Auto-approve calls from this server
  }
};
```

```python Python theme={null}
options = ClaudeAgentOptions(
    mcp_servers={
        # your servers
    },
    allowed_tools=["mcp__servername__*"],  # Auto-approve calls from this server
)
```

### SDK MCP 伺服器中缺少某個工具

在 TypeScript SDK 中，當某個工具的輸入 schema 無法轉換為 JSON Schema 時，您使用 [`createSdkMcpServer()`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#createsdkmcpserver) 建立的伺服器在列出其工具時會略過該工具。SDK 會在此時發出警告。在 Node.js 下，該警告是代碼為 `CLAUDE_SDK_MCP_TOOL_SCHEMA_UNCONVERTIBLE` 的程序警告，並以下列文字開頭：

```text theme={null}
Tool "<name>" on SDK MCP server "<server>" was left out of the server's tool list, because its input schema cannot be converted to JSON Schema
```

警告的其餘部分會在轉換錯誤有訊息時提供該訊息，接著說明應檢查和變更的內容。

在 TypeScript Agent SDK v0.3.286 之前，只要有一個無法轉換的 schema，就會導致伺服器的整個工具列表失敗且不會出現此警告，因此該伺服器的所有工具都無法傳達給 Claude。

### 連線逾時

MCP 伺服器連線預設在 30 秒後逾時。若要變更執行中工具呼叫可能需要的時間，請設定 [`MCP_TOOL_TIMEOUT`](https://code.claude.com/docs/zh-TW/env-vars)。如果您的伺服器需要更長時間才能啟動，連線會失敗。使用 [`MCP_TIMEOUT`](https://code.claude.com/docs/zh-TW/env-vars) 環境變數（以毫秒為單位）提高連線限制。對於需要更多啟動時間的伺服器，也請考慮：

* 使用更輕量級的伺服器（如果可用）
* 在啟動代理程式之前預先準備伺服器
* 檢查伺服器日誌以找出緩慢初始化的原因

在 TypeScript 中，您可以透過將 [`timeout` 傳遞給 `createSdkMcpServer()`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#createsdkmcpserver) 來為單一 [SDK MCP 伺服器](#sdk-mcp-servers) 設定工具呼叫限制。

### 工具輸出超過允許的最大權杖數

SDK 應用與 Claude Code 相同的 MCP 輸出限制。當不含影像內容的成功工具結果大於 25,000 個 token 時，Claude Code 會將輸出儲存到檔案，並將工具結果替換為指出檔案路徑的錯誤訊息，以便 agent 可以分次讀取輸出。

若要變更 token 限制，請設定 [`MAX_MCP_OUTPUT_TOKENS`](https://code.claude.com/docs/zh-TW/env-vars) 環境變數。除非工具宣告了 `anthropic/maxResultSizeChars`，否則超過 50,000 個字元的成功文字結果無論 token 限制為何，都會被儲存到檔案。請參閱 [MCP 輸出限制和警告](https://code.claude.com/docs/zh-TW/mcp.md#mcp-output-limits-and-warnings)以了解完整行為，包括伺服器如何宣告該註解。

## 相關資源

* **[自訂工具指南](https://code.claude.com/docs/zh-TW/agent-sdk/custom-tools.md)**：建立您自己的 MCP 伺服器，在 SDK 應用程式中以程序內方式執行
* **[權限](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md)**：使用 `allowedTools` 和 `disallowedTools` 控制您的代理程式可以使用哪些 MCP 工具
* **[TypeScript SDK 參考](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md)**：完整的 API 參考，包括 MCP 設定選項
* **[Python SDK 參考](https://code.claude.com/docs/zh-TW/agent-sdk/python.md)**：完整的 API 參考，包括 MCP 設定選項
* **[MCP 伺服器目錄](https://github.com/modelcontextprotocol/servers)**：瀏覽適用於資料庫、API 等的可用 MCP 伺服器

<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/agent-sdk/python | lastmod: 2026-11-03 | section: Agent SDK / SDK references -->
> 來源：https://code.claude.com/docs/zh-TW/agent-sdk/python（官方 zh-TW，lastmod 2026-11-03）｜分類：Agent SDK › SDK references｜EN 摘要：Complete API reference for the Python Agent SDK, including all functions, types, and classes.

# Agent SDK 參考 - Python

> Python Agent SDK 的完整 API 參考，包括所有函數、類型和類別。

## 安裝

在虛擬環境中安裝套件。在最近的 Debian、Ubuntu 和 Homebrew Python 安裝上，針對系統 Python 執行 `pip install` 會失敗，並出現 `error: externally-managed-environment` 錯誤。

```bash theme={null}
python3 -m venv .venv
source .venv/bin/activate
pip install claude-agent-sdk
```

如需 uv、Windows PowerShell 和 API 金鑰設定，請參閱 [Agent SDK 快速入門中的設定](https://code.claude.com/docs/zh-TW/agent-sdk/quickstart.md#setup)。

## 在 `query()` 和 `ClaudeSDKClient` 之間選擇

Python SDK 提供了兩種與 Claude Code 互動的方式：

| 功能 | `query()` | `ClaudeSDKClient` |
| :- | :- | :- |
| **Session** | 預設情況下建立新 session | 重複使用相同 session |
| **Conversation** | 單一交換 | 同一上下文中的多個交換 |
| **Connection** | 自動管理 | 手動控制 |
| **Streaming Input** | ✅ 支援 | ✅ 支援 |
| **Interrupts** | ❌ 不支援 | ✅ 支援 |
| **Hooks** | ✅ 支援 | ✅ 支援 |
| **Custom Tools** | ✅ 支援 | ✅ 支援 |
| **Continue Chat** | 透過 `continue_conversation` 或 `resume` 手動進行 | ✅ 自動進行 |
| **Use Case** | 一次性任務 | 持續對話 |

針對互動式應用程式（例如聊天介面）或當下一個動作取決於 Claude 的回應時，使用 `ClaudeSDKClient`。

## 函數

> [!NOTE]
>
> 此頁面上的簽名區塊和裸露的 `async for` / `async with` 片段僅供說明之用。若要執行它們，請將主體包裝在 `async def main(): ...` 中並呼叫 `asyncio.run(main())`。

### `query()`

為每次與 Claude Code 的互動建立新 session。返回一個非同步迭代器，在消息到達時產生消息。每次呼叫 `query()` 都會重新開始，不記得先前的互動，除非您傳遞 `continue_conversation=True` 或在 [`ClaudeAgentOptions`](#claudeagentoptions) 中傳遞 `resume`。請參閱 [Sessions](https://code.claude.com/docs/zh-TW/agent-sdk/sessions.md)。

```python theme={null}
async def query(
    *,
    prompt: str | AsyncIterable[dict[str, Any]],
    options: ClaudeAgentOptions | None = None,
    transport: Transport | None = None
) -> AsyncIterator[Message]
```

#### 參數

| 參數 | 類型 | 描述 |
| :- | :- | :- |
| `prompt` | `str \| AsyncIterable[dict]` | 輸入提示，可以是字串或非同步可迭代物件（用於串流模式） |
| `options` | `ClaudeAgentOptions \| None` | 可選配置物件（如果為 None，預設為 `ClaudeAgentOptions()`） |
| `transport` | `Transport \| None` | 用於與 CLI 程序通訊的可選自訂傳輸 |

#### 返回

返回 `AsyncIterator[Message]`，從對話中產生消息。

#### 範例 - 使用選項

```python theme={null}
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions


async def main():
    options = ClaudeAgentOptions(
        system_prompt="You are an expert Python developer",
        permission_mode="acceptEdits",
    )

    async for message in query(prompt="Create a Python web server", options=options):
        print(message)


asyncio.run(main())
```

### `tool()`

用於定義具有類型安全的 MCP tools 的裝飾器。

```python theme={null}
def tool(
    name: str,
    description: str,
    input_schema: type | dict[str, Any],
    annotations: ToolAnnotations | None = None
) -> Callable[[Callable[[Any], Awaitable[dict[str, Any]]]], SdkMcpTool[Any]]
```

#### 參數

| 參數 | 類型 | 描述 |
| :- | :- | :- |
| `name` | `str` | tool 的唯一識別碼 |
| `description` | `str` | tool 功能的人類可讀描述 |
| `input_schema` | `type \| dict[str, Any]` | 定義 tool 輸入參數的架構。請參閱 [輸入架構選項](#input-schema-options) |
| `annotations` | [`ToolAnnotations`](#toolannotations)` \| None` | 可選的 MCP tool 註解，為客戶端提供行為提示 |

#### 輸入架構選項

1. **簡單類型對應**（推薦）：

   ```python theme={null}
   {"text": str, "count": int, "enabled": bool}
   ```

2. **JSON Schema 格式**（用於複雜驗證）：
   ```python theme={null}
   {
       "type": "object",
       "properties": {
           "text": {"type": "string"},
           "count": {"type": "integer", "minimum": 0},
       },
       "required": ["text"],
   }
   ```

3. **TypedDict 類別**：一種具類型的 schema，其中 `NotRequired` 鍵不會列入 `required`。

   * **Python 3.11 及更新版本**：從 `typing` 匯入 `TypedDict` 和 `NotRequired`。
   * **Python 3.10**：`typing` 沒有 `NotRequired`。請從 `typing_extensions` 匯入 `TypedDict` 和 `NotRequired`，SDK 會在 Python 3.10 上安裝此套件。

   ```python theme={null}
   from typing import Annotated, Any, NotRequired, TypedDict
   from claude_agent_sdk import tool


   class ForecastArgs(TypedDict):
       latitude: Annotated[float, "Latitude coordinate"]
       hours: NotRequired[Annotated[int, "How many hours of forecast to return"]]


   @tool("get_forecast", "Get the hourly forecast for a location", ForecastArgs)
   async def get_forecast(args: dict[str, Any]) -> dict[str, Any]:
       hours = args.get("hours", 12)
       return {"content": [{"type": "text", "text": f"{hours}-hour forecast for {args['latitude']}"}]}
   ```

在簡單對應和 TypedDict 形式中，將類型包裝在 `Annotated[type, "description"]` 中即可設定該欄位的描述。

#### 返回

一個裝飾器函數，包裝 tool 實現並返回 `SdkMcpTool` 實例。

#### 範例

```python theme={null}
from claude_agent_sdk import tool
from typing import Any


@tool("greet", "Greet a user", {"name": str})
async def greet(args: dict[str, Any]) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": f"Hello, {args['name']}!"}]}
```

#### `ToolAnnotations`

tool 的行為提示，作為 [`tool()`](#tool) 的 `annotations` 引數傳遞。`ToolAnnotations` 擴展 MCP SDK 的 `mcp.types.ToolAnnotations`，具有 `maxResultSizeChars` 欄位，您可以用 camelCase 或 snake\_case 寫入每個提示：`ToolAnnotations(readOnlyHint=True)` 和 `ToolAnnotations(read_only_hint=True)` 是等效的。若要從物件讀回提示，請使用您已安裝的 `mcp` 套件所宣告的拼寫：在 `mcp` 1.x 上使用 `.readOnlyHint`，在 2.x 上使用 `.read_only_hint`，而 `.maxResultSizeChars` 在兩者上皆可使用。您也可以在 SDK 接受註解的任何地方傳遞純 `mcp.types.ToolAnnotations`。

snake\_case 名稱和類型化的 `maxResultSizeChars` 欄位需要 Python Agent SDK 0.2.140 或更新版本。版本 0.1.31 到 0.2.139 重新匯出 `mcp.types.ToolAnnotations` 不變。在版本 0.1.55 到 0.2.139 上，您仍然可以將 `maxResultSizeChars` 作為關鍵字引數傳遞：MCP 類別接受額外欄位，SDK 將值轉發給 Claude Code。

所有欄位都是可選的。客戶端不應依賴提示進行安全決策。

| 欄位 | 類型 | 預設 | 描述 |
| :- | :- | :- | :- |
| `title` | `str \| None` | `None` | tool 的人類可讀標題 |
| `readOnlyHint` | `bool \| None` | `False` | 如果為 `True`，tool 不會修改其環境 |
| `destructiveHint` | `bool \| None` | `True` | 如果為 `True`，tool 可能執行破壞性更新（僅在 `readOnlyHint` 為 `False` 時有意義） |
| `idempotentHint` | `bool \| None` | `False` | 如果為 `True`，使用相同參數的重複呼叫沒有額外效果（僅在 `readOnlyHint` 為 `False` 時有意義） |
| `openWorldHint` | `bool \| None` | `True` | 如果為 `True`，tool 與外部實體互動（例如網路搜尋）。如果為 `False`，tool 的域是封閉的（例如記憶體 tool） |
| `maxResultSizeChars` | `int \| None` | `None` | Claude Code 將此 tool 的文字結果保持內聯在對話中而不是儲存到檔案的字元數，最多 500,000。包含影像的結果不受影響。Claude Code 設定而非 MCP 提示：SDK 在 tool 的 `_meta` 中以 `anthropic/maxResultSizeChars` 傳送它。請參閱 [提高特定 tool 的限制](https://code.claude.com/docs/zh-TW/mcp.md#raise-the-limit-for-a-specific-tool) |

```python theme={null}
from claude_agent_sdk import tool, ToolAnnotations
from typing import Any


@tool(
    "search",
    "Search the web",
    {"query": str},
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
)
async def search(args: dict[str, Any]) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": f"Results for: {args['query']}"}]}
```

### `create_sdk_mcp_server()`

建立在 Python 應用程式內執行的進程內 MCP 伺服器。

```python theme={null}
def create_sdk_mcp_server(
    name: str,
    version: str = "1.0.0",
    tools: list[SdkMcpTool[Any]] | None = None
) -> McpSdkServerConfig
```

#### 參數

| 參數 | 類型 | 預設 | 描述 |
| :- | :- | :- | :- |
| `name` | `str` | - | 伺服器的唯一識別碼 |
| `version` | `str` | `"1.0.0"` | 伺服器版本字串 |
| `tools` | `list[SdkMcpTool[Any]] \| None` | `None` | 使用 `@tool` 裝飾器建立的 tool 函數清單 |

#### 返回

返回 `McpSdkServerConfig` 物件，可以傳遞給 `ClaudeAgentOptions.mcp_servers`。

#### 範例

```python theme={null}
from claude_agent_sdk import tool, create_sdk_mcp_server, ClaudeAgentOptions


@tool("add", "Add two numbers", {"a": float, "b": float})
async def add(args):
    return {"content": [{"type": "text", "text": f"Sum: {args['a'] + args['b']}"}]}


@tool("multiply", "Multiply two numbers", {"a": float, "b": float})
async def multiply(args):
    return {"content": [{"type": "text", "text": f"Product: {args['a'] * args['b']}"}]}


calculator = create_sdk_mcp_server(
    name="calculator",
    version="2.0.0",
    tools=[add, multiply],  # Pass decorated functions
)

# Use with Claude
options = ClaudeAgentOptions(
    mcp_servers={"calc": calculator},
    allowed_tools=["mcp__calc__add", "mcp__calc__multiply"],
)
```

### `list_sessions()`

列出過去的 sessions 及其中繼資料。按專案目錄篩選或列出所有專案中的 sessions。同步；立即返回。

```python theme={null}
def list_sessions(
    directory: str | None = None,
    limit: int | None = None,
    offset: int = 0,
    include_worktrees: bool = True
) -> list[SDKSessionInfo]
```

#### 參數

| 參數 | 類型 | 預設 | 描述 |
| :- | :- | :- | :- |
| `directory` | `str \| None` | `None` | 列出 sessions 的目錄。省略時，返回所有專案中的 sessions |
| `limit` | `int \| None` | `None` | 返回的最大 sessions 數 |
| `offset` | `int` | `0` | 從排序結果開始跳過的 sessions 數。與 `limit` 搭配使用以進行分頁 |
| `include_worktrees` | `bool` | `True` | 當 `directory` 在 git 儲存庫內時，包括所有 worktrees 路徑中的 sessions |

#### 返回類型：`SDKSessionInfo`

| 屬性 | 類型 | 描述 |
| :- | :- | :- |
| `session_id` | `str` | 唯一 session 識別碼 |
| `summary` | `str` | 顯示標題：自訂標題、最近的提示、自動生成的摘要或第一個提示 |
| `last_modified` | `int` | 上次修改時間（自紀元以來的毫秒數） |
| `file_size` | `int \| None` | Session 檔案大小（以位元組為單位）（遠端儲存後端為 `None`） |
| `custom_title` | `str \| None` | 使用者設定的 session 標題 |
| `first_prompt` | `str \| None` | session 中的第一個有意義的使用者提示 |
| `git_branch` | `str \| None` | session 結束時的 Git 分支 |
| `cwd` | `str \| None` | session 的工作目錄 |
| `tag` | `str \| None` | 使用者設定的 session 標籤（見 [`tag_session()`](#tag_session)） |
| `created_at` | `int \| None` | session 建立時間（自紀元以來的毫秒數） |

#### 範例

列印專案的 10 個最近 sessions。結果按 `last_modified` 降序排序，因此第一項是最新的。省略 `directory` 以搜尋所有專案。

```python theme={null}
from claude_agent_sdk import list_sessions

for session in list_sessions(directory="/path/to/project", limit=10):
    print(f"{session.summary} ({session.session_id})")
```

### `get_session_messages()`

從過去的 session 中檢索消息。同步；立即返回。

```python theme={null}
def get_session_messages(
    session_id: str,
    directory: str | None = None,
    limit: int | None = None,
    offset: int = 0
) -> list[SessionMessage]
```

#### 參數

| 參數 | 類型 | 預設 | 描述 |
| :- | :- | :- | :- |
| `session_id` | `str` | 必需 | 要檢索消息的 session ID |
| `directory` | `str \| None` | `None` | 要查看的專案目錄。省略時，搜尋所有專案 |
| `limit` | `int \| None` | `None` | 返回的最大消息數 |
| `offset` | `int` | `0` | 從開始跳過的消息數 |

#### 返回類型：`SessionMessage`

| 屬性 | 類型 | 描述 |
| :- | :- | :- |
| `type` | `Literal["user", "assistant"]` | 消息角色 |
| `uuid` | `str` | 唯一消息識別碼 |
| `session_id` | `str` | session 識別碼 |
| `message` | `Any` | 原始消息內容 |
| `parent_tool_use_id` | `str \| None` | 對於子代理消息，是產生 `Agent` tool-use 區塊的 id。對於主 session 消息和較舊的 sessions 為 `None` |
| `parent_agent_id` | `str \| None` | 對於來自[巢狀子代理](https://code.claude.com/docs/zh-TW/sub-agents.md#let-subagents-spawn-their-own-subagents)的消息，父子代理的代理 id。對於主 session 消息、頂級子代理消息和較舊的 sessions 為 `None`。需要 Python Agent SDK 0.2.140 或更新版本 |

#### 範例

```python theme={null}
from claude_agent_sdk import list_sessions, get_session_messages

sessions = list_sessions(limit=1)
if sessions:
    messages = get_session_messages(sessions[0].session_id)
    for msg in messages:
        print(f"[{msg.type}] {msg.uuid}")
```

### `get_session_info()`

按 ID 讀取單個 session 的中繼資料，無需掃描完整專案目錄。同步；立即返回。

```python theme={null}
def get_session_info(
    session_id: str,
    directory: str | None = None,
) -> SDKSessionInfo | None
```

#### 參數

| 參數 | 類型 | 預設 | 描述 |
| :- | :- | :- | :- |
| `session_id` | `str` | 必需 | 要查詢的 session 的 UUID |
| `directory` | `str \| None` | `None` | 專案目錄路徑。省略時，搜尋所有專案目錄 |

返回 [`SDKSessionInfo`](#return-type-sdksessioninfo)，如果找不到 session，則返回 `None`。

#### 範例

查詢單個 session 的中繼資料，無需掃描專案目錄。當您已經從先前的執行中獲得 session ID 時很有用。

```python theme={null}
from claude_agent_sdk import get_session_info

info = get_session_info("550e8400-e29b-41d4-a716-446655440000")
if info:
    print(f"{info.summary} (branch: {info.git_branch}, tag: {info.tag})")
```

### `rename_session()`

通過附加自訂標題項來重新命名 session。重複呼叫是安全的；最新的標題獲勝。同步。

```python theme={null}
def rename_session(
    session_id: str,
    title: str,
    directory: str | None = None,
) -> None
```

#### 參數

| 參數 | 類型 | 預設 | 描述 |
| :- | :- | :- | :- |
| `session_id` | `str` | 必需 | 要重新命名的 session 的 UUID |
| `title` | `str` | 必需 | 新標題。去除空格後必須非空 |
| `directory` | `str \| None` | `None` | 專案目錄路徑。省略時，搜尋所有專案目錄 |

如果 `session_id` 不是有效的 UUID 或 `title` 為空，則引發 `ValueError`；如果找不到 session，則引發 `FileNotFoundError`。

#### 範例

重新命名最近的 session，以便稍後更容易找到。新標題在後續讀取時出現在 [`SDKSessionInfo.custom_title`](#return-type-sdksessioninfo) 中。

```python theme={null}
from claude_agent_sdk import list_sessions, rename_session

sessions = list_sessions(directory="/path/to/project", limit=1)
if sessions:
    rename_session(sessions[0].session_id, "Refactor auth module")
```

### `tag_session()`

標記 session。傳遞 `None` 以清除標籤。重複呼叫是安全的；最新的標籤獲勝。同步。

```python theme={null}
def tag_session(
    session_id: str,
    tag: str | None,
    directory: str | None = None,
) -> None
```

#### 參數

| 參數 | 類型 | 預設 | 描述 |
| :- | :- | :- | :- |
| `session_id` | `str` | 必需 | 要標記的 session 的 UUID |
| `tag` | `str \| None` | 必需 | 標籤字串，或 `None` 以清除。儲存前進行 Unicode 清理 |
| `directory` | `str \| None` | `None` | 專案目錄路徑。省略時，搜尋所有專案目錄 |

如果 `session_id` 不是有效的 UUID 或 `tag` 在清理後為空，則引發 `ValueError`；如果找不到 session，則引發 `FileNotFoundError`。

#### 範例

標記 session，然後在稍後的讀取中按該標籤篩選。傳遞 `None` 以清除現有標籤。

```python theme={null}
from claude_agent_sdk import list_sessions, tag_session

# Tag the most recent session
sessions = list_sessions(directory="/path/to/project", limit=1)
if sessions:
    tag_session(sessions[0].session_id, "needs-review")

# Later: find all sessions with that tag
for session in list_sessions(directory="/path/to/project"):
    if session.tag == "needs-review":
        print(session.summary)
```

### `fork_session()`

將工作階段的逐字稿複製到新的工作階段中，讓您可以將對話導向另一個方向，同時原始工作階段保持不變。若要從對話中較早的時間點分支，請傳遞 `up_to_message_id`。同步。

```python theme={null}
def fork_session(
    session_id: str,
    directory: str | None = None,
    up_to_message_id: str | None = None,
    title: str | None = None,
) -> ForkSessionResult
```

#### 參數

| 參數 | 類型 | 預設 | 描述 |
| :- | :- | :- | :- |
| `session_id` | `str` | 必需 | 要分叉的工作階段的 UUID |
| `directory` | `str \| None` | `None` | 專案目錄路徑。省略時，搜尋所有專案目錄 |
| `up_to_message_id` | `str \| None` | `None` | 複製逐字稿直到具有此 UUID 的消息為止（包含該消息），例如來自 [`get_session_messages()`](#get_session_messages) 的 `uuid`。省略時，複製整份逐字稿 |
| `title` | `str \| None` | `None` | 分叉的標題。省略時，SDK 會從原始工作階段衍生標題，並在其後加上 `(fork)` |

返回一個 `ForkSessionResult`，其 `session_id` 為新工作階段的 UUID。將其作為 [`resume`](#claudeagentoptions) 傳遞以繼續該分叉。分叉不包含原始工作階段的[檔案檢查點](https://code.claude.com/docs/zh-TW/agent-sdk/file-checkpointing.md)，因此無法將其倒回到分叉之前擷取的檢查點。

`fork_session()` 會引發：

* `ValueError`：`session_id` 或 `up_to_message_id` 不是有效的 UUID
* `ValueError`：工作階段沒有任何消息，或 `up_to_message_id` 與逐字稿中的任何消息都不相符
* `FileNotFoundError`：找不到工作階段

#### 範例

以新標題分叉最近的工作階段，然後繼續該分叉。原始工作階段保留其自身的歷史記錄。

```python theme={null}
from claude_agent_sdk import fork_session, list_sessions

sessions = list_sessions(directory="/path/to/project", limit=1)
if sessions:
    forked = fork_session(sessions[0].session_id, title="Try the OAuth approach")
    print(forked.session_id)  # pass as ClaudeAgentOptions(resume=...) to continue the fork
```

## 類別

### `ClaudeSDKClient`

**在多個交換中維持對話 session。** 這是 TypeScript SDK 的 `query()` 函數內部工作方式的 Python 等效物 - 它建立一個可以繼續對話的客戶端物件。請參閱 [與 `query()` 的比較](#choosing-between-query-and-claudesdkclient)。

```python theme={null}
class ClaudeSDKClient:
    def __init__(self, options: ClaudeAgentOptions | None = None, transport: Transport | None = None)
    async def connect(self, prompt: str | AsyncIterable[dict] | None = None) -> None
    async def query(self, prompt: str | AsyncIterable[dict], session_id: str = "default") -> None
    async def receive_messages(self) -> AsyncIterator[Message]
    async def receive_response(self) -> AsyncIterator[Message]
    async def interrupt(self) -> None
    async def set_permission_mode(self, mode: PermissionMode) -> None
    async def set_model(self, model: str | None = None) -> None
    async def rewind_files(self, user_message_id: str) -> None
    async def get_mcp_status(self) -> McpStatusResponse
    async def get_context_usage(self) -> ContextUsageResponse
    async def reconnect_mcp_server(self, server_name: str) -> None
    async def toggle_mcp_server(self, server_name: str, enabled: bool) -> None
    async def stop_task(self, task_id: str) -> None
    async def get_server_info(self) -> dict[str, Any] | None
    async def disconnect(self) -> None
```

#### 方法

| 方法 | 描述 |
| :- | :- |
| `__init__(options)` | 使用可選設定初始化客戶端 |
| `connect(prompt)` | 使用可選初始提示或訊息流連接到 Claude |
| `query(prompt, session_id)` | 以串流模式發送新請求 |
| `receive_messages()` | 以非同步迭代器接收來自 Claude 的所有訊息 |
| `receive_response()` | 接收訊息直到並包括 ResultMessage |
| `interrupt()` | 發送中斷信號（僅在串流模式下工作） |
| `set_permission_mode(mode)` | 變更目前 session 的權限模式 |
| `set_model(model)` | 變更目前 session 的模型。傳遞 `None` 以重設為 [Claude Code 的預設模型](https://code.claude.com/docs/zh-TW/model-config.md)。若新模型不支援自動模式，處於 `auto` 模式的 session 會[變更為 `default` 模式](https://code.claude.com/docs/zh-TW/agent-sdk/permissions#auto-mode-auto) |
| `rewind_files(user_message_id)` | 將檔案還原到指定使用者訊息時的狀態。需要 `enable_file_checkpointing=True`。見 [檔案 checkpointing](https://code.claude.com/docs/zh-TW/agent-sdk/file-checkpointing.md) |
| `get_mcp_status()` | 取得所有已設定 MCP 伺服器的狀態。返回 [`McpStatusResponse`](#mcpstatusresponse) |
| `get_context_usage()` | 取得按類別、skill 和工具分類的上下文視窗使用情況的詳細資訊。包含 `/context` 在互動式工作階段中顯示的資料。返回 [`ContextUsageResponse`](#contextusageresponse)。為了計算詳細資訊，Claude Code 會進行多個不出現在訊息串流中的 token 計數 API 請求；見 [這些請求如何被處理](#contextusageresponse) |
| `reconnect_mcp_server(server_name)` | 重試連接到失敗或斷開連接的 MCP 伺服器 |
| `toggle_mcp_server(server_name, enabled)` | 在 session 中途啟用或停用 MCP 伺服器。停用會移除其 tools |
| `stop_task(task_id)` | 停止執行中的背景任務。[`TaskNotificationMessage`](#tasknotificationmessage) 的狀態為 `"stopped"` 在訊息流中跟隨 |
| `get_server_info()` | 取得伺服器的初始化資訊，包括可用的指令和輸出樣式 |
| `disconnect()` | 從 Claude 斷開連接 |

#### 上下文管理器支援

客戶端可以用作非同步上下文管理器以進行自動連接管理：

```python theme={null}
import asyncio
from claude_agent_sdk import ClaudeSDKClient


async def main():
    async with ClaudeSDKClient() as client:
        await client.query("Hello Claude")
        async for message in client.receive_response():
            print(message)


asyncio.run(main())
```

> **重要：** 在迭代訊息時，避免使用 `break` 提前退出，因為這可能導致 asyncio 清理問題。相反，讓迭代自然完成或使用旗標來追蹤何時找到所需內容。

#### 範例 - 繼續對話

```python theme={null}
import asyncio
from claude_agent_sdk import ClaudeSDKClient, AssistantMessage, TextBlock, ResultMessage


async def main():
    async with ClaudeSDKClient() as client:
        # First question
        await client.query("What's the capital of France?")

        # Process response
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(f"Claude: {block.text}")

        # Follow-up question - the session retains the previous context
        await client.query("What's the population of that city?")

        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(f"Claude: {block.text}")

        # Another follow-up - still in the same conversation
        await client.query("What are some famous landmarks there?")

        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(f"Claude: {block.text}")


asyncio.run(main())
```

#### 範例 - 使用 ClaudeSDKClient 進行串流輸入

`query()` 也接受使用者訊息字典的非同步可迭代物件，因此您可以在傳送時組合提示或包含內容區塊，例如影像。Claude Code 會在第一個產生的訊息到達時立即開始回應，無需等待可迭代物件完成，而 `receive_response()` 會在結束該回應的 `ResultMessage` 處停止。將 Claude 應該在回答前讀取的所有內容放入一個訊息中，如此產生器所做的，並將每個 `query()` 呼叫與其自己的 `receive_response()` 迴圈配對。

```python theme={null}
import asyncio
from claude_agent_sdk import ClaudeSDKClient


async def message_stream():
    """Assemble the prompt at send time and yield it as one user message."""
    readings = {"Temperature": "25°C", "Humidity": "60%"}
    data = ", ".join(f"{name}: {value}" for name, value in readings.items())
    yield {
        "type": "user",
        "message": {
            "role": "user",
            "content": f"Analyze the following sensor data and describe any patterns you see: {data}",
        },
    }


async def main():
    async with ClaudeSDKClient() as client:
        # Stream input to Claude
        await client.query(message_stream())

        # Process response
        async for message in client.receive_response():
            print(message)

        # Follow-up in same session
        await client.query("Should we be concerned about these readings?")

        async for message in client.receive_response():
            print(message)


asyncio.run(main())
```

#### 範例 - 使用中斷

```python theme={null}
import asyncio
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, ResultMessage


async def interruptible_task():
    options = ClaudeAgentOptions(allowed_tools=["Bash"], permission_mode="acceptEdits")

    async with ClaudeSDKClient(options=options) as client:
        # Start a long-running task
        await client.query("Count from 1 to 100 slowly, using the bash sleep command")

        # Let it run for a bit
        await asyncio.sleep(2)

        # Interrupt the task
        await client.interrupt()
        print("Task interrupted!")

        # Drain the interrupted task's messages (including its ResultMessage)
        async for message in client.receive_response():
            if isinstance(message, ResultMessage):
                print(f"Interrupted task: terminal_reason={message.terminal_reason!r}")
                # terminal_reason is "aborted_streaming" or "aborted_tools"
                # for interrupted turns

        # Send a new command
        await client.query("Just say hello instead")

        # Now receive the new response
        async for message in client.receive_response():
            if isinstance(message, ResultMessage) and message.subtype == "success":
                print(f"New result: {message.result}")


asyncio.run(interruptible_task())
```

> [!NOTE]
>
> **中斷後的緩衝區行為：** `interrupt()` 發送停止信號但不清除訊息緩衝區。已由中斷任務產生的訊息，包括其 `ResultMessage`，保留在流中。您必須在讀取新查詢的回應之前使用 `receive_response()` 清空它們。如果您在 `interrupt()` 之後立即發送新查詢並僅呼叫一次 `receive_response()`，您將收到中斷任務的訊息，而不是新查詢的回應。

#### 範例 - 進階權限控制

```python theme={null}
import asyncio
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
from claude_agent_sdk.types import (
    PermissionResultAllow,
    PermissionResultDeny,
    ToolPermissionContext,
)


async def custom_permission_handler(
    tool_name: str, input_data: dict, context: ToolPermissionContext
) -> PermissionResultAllow | PermissionResultDeny:
    """Custom logic for tool permissions."""

    # Block writes to system directories
    if tool_name == "Write" and input_data.get("file_path", "").startswith("/system/"):
        return PermissionResultDeny(
            message="System directory write not allowed", interrupt=True
        )

    # Redirect sensitive file operations
    if tool_name in ["Write", "Edit"] and "config" in input_data.get("file_path", ""):
        safe_path = f"./sandbox/{input_data['file_path']}"
        return PermissionResultAllow(
            updated_input={**input_data, "file_path": safe_path}
        )

    # Allow everything else
    return PermissionResultAllow(updated_input=input_data)


async def main():
    # 不要同時在 allowed_tools 中列出受限 tools：allow 規則在 can_use_tool 執行前批准呼叫
    options = ClaudeAgentOptions(can_use_tool=custom_permission_handler)

    async with ClaudeSDKClient(options=options) as client:
        await client.query("Update the system config file")

        async for message in client.receive_response():
            # 將使用 sandbox 路徑代替
            print(message)


asyncio.run(main())
```

## 類型

> [!NOTE]
>
> **`@dataclass` vs `TypedDict`：** 此 SDK 使用兩種類型。以 `@dataclass` 裝飾的類別（例如 `ResultMessage`、`AgentDefinition`、`TextBlock`）在執行時是物件實例，支援屬性存取：`msg.result`。以 `TypedDict` 定義的類別（例如 `ThinkingConfigEnabled`、`McpStdioServerConfig`、`SyncHookJSONOutput`）在執行時是**純字典**，需要鍵存取：`config["budget_tokens"]`，而不是 `config.budget_tokens`。`ClassName(field=value)` 呼叫語法對兩者都有效，但只有資料類別會產生具有屬性的物件。

### `SdkMcpTool`

使用 `@tool` 裝飾器建立的 SDK MCP 工具定義。

```python theme={null}
@dataclass
class SdkMcpTool(Generic[T]):
    name: str
    description: str
    input_schema: type[T] | dict[str, Any]
    handler: Callable[[T], Awaitable[dict[str, Any]]]
    annotations: ToolAnnotations | None = None
```

| 屬性 | 類型 | 說明 |
| :- | :- | :- |
| `name` | `str` | 工具的唯一識別碼 |
| `description` | `str` | 人類可讀的說明 |
| `input_schema` | `type[T] \| dict[str, Any]` | 輸入驗證的 schema |
| `handler` | `Callable[[T], Awaitable[dict[str, Any]]]` | 處理工具執行的非同步函式 |
| `annotations` | [`ToolAnnotations`](#toolannotations)` \| None` | 選用的工具註解（例如 `readOnlyHint`、`destructiveHint`、`openWorldHint`、`maxResultSizeChars`） |

### `Transport`

自訂傳輸實作的抽象基底類別。使用此類別透過自訂通道與 Claude 程序通訊（例如，遠端連線而不是本機子程序）。

> [!WARNING]
>
> 這是低階內部 API。介面可能在未來版本中變更。自訂實作必須更新以符合任何介面變更。

```python theme={null}
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any


class Transport(ABC):
    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def write(self, data: str) -> None: ...

    @abstractmethod
    def read_messages(self) -> AsyncIterator[dict[str, Any]]: ...

    @abstractmethod
    async def close(self) -> None: ...

    @abstractmethod
    def is_ready(self) -> bool: ...

    @abstractmethod
    async def end_input(self) -> None: ...
```

| 方法 | 說明 |
| :- | :- |
| `connect()` | 連線傳輸並準備通訊 |
| `write(data)` | 將原始資料（JSON + 換行符）寫入傳輸 |
| `read_messages()` | 非同步迭代器，產生已解析的 JSON 訊息 |
| `close()` | 關閉連線並清理資源 |
| `is_ready()` | 如果傳輸可以傳送和接收，傳回 `True` |
| `end_input()` | 關閉輸入串流（例如，關閉子程序傳輸的 stdin） |

匯入：`from claude_agent_sdk import Transport`

### `ClaudeAgentOptions`

Claude Code 查詢的設定資料類別。

```python theme={null}
@dataclass
class ClaudeAgentOptions:
    tools: list[str] | ToolsPreset | None = None
    allowed_tools: list[str] = field(default_factory=list)
    system_prompt: str | SystemPromptPreset | SystemPromptCustom | SystemPromptFile | None = None
    mcp_servers: dict[str, McpServerConfig] | str | Path = field(default_factory=dict)
    strict_mcp_config: bool = False
    permission_mode: PermissionMode | None = None
    continue_conversation: bool = False
    resume: str | None = None
    session_id: str | None = None
    max_turns: int | None = None
    max_budget_usd: float | None = None
    disallowed_tools: list[str] = field(default_factory=list)
    model: str | None = None
    fallback_model: str | None = None
    betas: list[SdkBeta] = field(default_factory=list)
    output_format: dict[str, Any] | None = None
    permission_prompt_tool_name: str | None = None
    cwd: str | Path | None = None
    cli_path: str | Path | None = None
    settings: str | None = None
    add_dirs: list[str | Path] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    extra_args: dict[str, str | None] = field(default_factory=dict)
    max_buffer_size: int | None = None
    debug_stderr: Any = sys.stderr  # Deprecated
    stderr: Callable[[str], None] | None = None
    can_use_tool: CanUseTool | None = None
    hooks: dict[HookEvent, list[HookMatcher]] | None = None
    user: str | None = None
    include_partial_messages: bool = False
    include_hook_events: bool = False
    forward_subagent_text: bool = False
    verbatim_prompts: bool = False
    fork_session: bool = False
    resume_session_at: str | None = None
    resume_drops_turn: str | None = None
    agents: dict[str, AgentDefinition] | None = None
    setting_sources: list[SettingSource] | None = None
    skills: list[str] | Literal["all"] | None = None
    sandbox: SandboxSettings | None = None
    plugins: list[SdkPluginConfig] = field(default_factory=list)
    max_thinking_tokens: int | None = None  # Deprecated: use thinking instead
    thinking: ThinkingConfig | None = None
    effort: EffortLevel | None = None
    enable_file_checkpointing: bool = False
    session_store: SessionStore | None = None
    session_store_flush: SessionStoreFlushMode = "batched"
    load_timeout_ms: int = 60_000
    task_budget: TaskBudget | None = None
```

| 屬性 | 類型 | 預設值 | 說明 |
| :- | :- | :- | :- |
| `tools` | `list[str] \| ToolsPreset \| None` | `None` | 工具設定。使用 `{"type": "preset", "preset": "claude_code"}` 以取得 Claude Code 的預設工具 |
| `allowed_tools` | `list[str]` | `[]` | 無需提示即可自動核准的工具，但從[網路路徑](https://code.claude.com/docs/zh-TW/permissions.md#network-paths)讀取的操作除外。這不會限制 Claude 只使用這些工具。如果您在此處命名其中一個[任務追蹤工具](https://code.claude.com/docs/zh-TW/agent-sdk/todo-tracking.md#model-availability)，Claude Code 也會為工作階段選擇加入。其他未列出的工具會進入 `permission_mode` 和 `can_use_tool`。使用 `disallowed_tools` 來封鎖工具。請參閱[權限](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#allow-and-deny-rules) |
| `system_prompt` | `str \| SystemPromptPreset \| SystemPromptCustom \| SystemPromptFile \| None` | `None` | 系統提示詞設定。傳遞字串以取得自訂提示詞、`{"type": "preset", "preset": "claude_code"}` 以取得 Claude Code 的系統提示詞（含選用的 `"append"`）、`{"type": "custom", "prompt": "..."}` 以取得也可以設定 `"snapshot"` 的自訂提示詞，或 `{"type": "file", "path": "..."}` 以從磁碟載入大型提示詞。請參閱 [`SystemPromptPreset`](#systempromptpreset)、[`SystemPromptCustom`](#systempromptcustom) 和 [`SystemPromptFile`](#systempromptfile) |
| `mcp_servers` | `dict[str, McpServerConfig] \| str \| Path` | `{}` | MCP 伺服器設定或設定檔的路徑 |
| `strict_mcp_config` | `bool` | `False` | 當為 `True` 時，僅使用在 `mcp_servers` 中傳遞的伺服器，並忽略專案 `.mcp.json`、使用者設定、外掛提供的 MCP 伺服器和 [claude.ai 連接器](https://code.claude.com/docs/zh-TW/mcp.md#use-mcp-servers-from-claude-ai)。對應至 CLI `--strict-mcp-config` 旗標 |
| `permission_mode` | `PermissionMode \| None` | `None` | 工具使用的權限模式 |
| `continue_conversation` | `bool` | `False` | 繼續最近的對話 |
| `resume` | `str \| None` | `None` | 要繼續的工作階段 ID |
| `session_id` | `str \| None` | `None` | 使用特定的工作階段 ID 而不是自動產生的 ID。必須是有效的 UUID。除非也設定了 `fork_session`，否則無法與 `continue_conversation` 或 `resume` 結合 |
| `max_turns` | `int \| None` | `None` | 最大 agent [回合](https://code.claude.com/docs/zh-TW/agent-sdk/agent-loop.md#turns-and-messages)數 |
| `max_budget_usd` | `float \| None` | `None` | 當用戶端成本估計達到此 USD 值時停止查詢。估計值可能超過此值，因此請[預留餘裕](https://code.claude.com/docs/zh-TW/agent-sdk/agent-loop.md#budget-headroom)。僅計算呼叫本身的支出；從已繼續的工作階段恢復的總計不計算。如需準確性注意事項和重設行為，請參閱[追蹤成本和使用量](https://code.claude.com/docs/zh-TW/agent-sdk/cost-tracking.md) |
| `disallowed_tools` | `list[str]` | `[]` | 要拒絕的工具。裸名稱（例如 `"Bash"`）會從 Claude 的上下文中移除工具。範圍規則（例如 `"Bash(rm *)"`）會保留工具可用，並在每個權限模式（包括 `bypassPermissions`）中拒絕符合的呼叫，針對[如所寫](https://code.claude.com/docs/zh-TW/permissions.md#bash-rule-limits)的命令。請參閱[權限](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#allow-and-deny-rules) |
| `enable_file_checkpointing` | `bool` | `False` | 啟用檔案變更追蹤以進行倒帶。請參閱[檔案檢查點功能](https://code.claude.com/docs/zh-TW/agent-sdk/file-checkpointing.md) |
| `model` | `str \| None` | `None` | Claude 模型別名或完整模型名稱。請參閱[接受的值和提供者特定 ID](https://code.claude.com/docs/zh-TW/model-config.md#available-models) |
| `fallback_model` | `str \| None` | `None` | 主要模型失敗時使用的備援模型。接受逗號分隔的清單。如需指導，請參閱[選擇模型](https://code.claude.com/docs/zh-TW/agent-sdk/configuration.md#choose-a-model) |
| `betas` | `list[SdkBeta]` | `[]` | 要啟用的測試版功能。請參閱 [`SdkBeta`](#sdkbeta) 以取得可用選項 |
| `output_format` | `dict[str, Any] \| None` | `None` | 結構化回應的輸出格式（例如 `{"type": "json_schema", "schema": {...}}`）。請參閱[結構化輸出](https://code.claude.com/docs/zh-TW/agent-sdk/structured-outputs.md)以取得詳細資訊 |
| `permission_prompt_tool_name` | `str \| None` | `None` | 權限提示的 MCP 工具名稱 |
| `cwd` | `str \| Path \| None` | `None` | 目前的工作目錄 |
| `cli_path` | `str \| Path \| None` | `None` | Claude Code CLI 可執行檔的自訂路徑 |
| `settings` | `str \| None` | `None` | 設定檔的路徑或內嵌 JSON 字串 |
| `add_dirs` | `list[str \| Path]` | `[]` | Claude 可以存取的其他目錄。SDK 將每個項目傳遞給 Claude Code 作為 `--add-dir`，因此使用 `project` 設定來源時，Claude Code 也會[載入目錄的 skill、命令和 subagent](https://code.claude.com/docs/zh-TW/permissions.md#additional-directories-grant-file-access-not-configuration) |
| `env` | `dict[str, str]` | `{}` | 合併在繼承程序環境之上的環境變數。請參閱[環境變數](https://code.claude.com/docs/zh-TW/env-vars.md)以取得基礎 CLI 讀取的變數，以及[處理緩慢或停滯的 API 回應](#handle-slow-or-stalled-api-responses)以取得逾時相關變數。設定 `CLAUDE_AGENT_SDK_CLIENT_APP` 以在 User-Agent 標頭中識別您的應用程式 |
| `extra_args` | `dict[str, str \| None]` | `{}` | 要直接傳遞給 CLI 的其他 CLI 引數 |
| `max_buffer_size` | `int \| None` | `None` | 緩衝 CLI stdout 時的最大位元組數 |
| `debug_stderr` | `Any` | `sys.stderr` | *已棄用* - SDK 會忽略此值。使用 `stderr` 回呼以取得 CLI stderr 輸出 |
| `stderr` | `Callable[[str], None] \| None` | `None` | CLI 中 stderr 輸出的回呼函式 |
| `can_use_tool` | [`CanUseTool`](#canusetool) ` \| None` | `None` | 工具權限回呼，僅在[權限流程](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#how-permissions-are-evaluated)進入提示時叫用。不會針對由 `allowed_tools`、允許規則或 `permission_mode` 自動核准的呼叫叫用。允許規則不會預先核准[任何模式都不自動核准的動作](https://code.claude.com/docs/zh-TW/permission-modes.md#actions-no-mode-auto-approves)。請參閱 [`CanUseTool`](#canusetool) 以取得詳細資訊 |
| `hooks` | `dict[HookEvent, list[HookMatcher]] \| None` | `None` | 用於攔截事件的 hook 設定 |
| `user` | `str \| None` | `None` | 在 POSIX 平台上，Claude Code 子程序執行所在的 OS 使用者帳戶。Claude Code 保留父程序的環境（包括 `HOME`），並在 `cwd` 中執行 |
| `include_partial_messages` | `bool` | `False` | 包含部分訊息串流事件。啟用時，會產生 [`StreamEvent`](#streamevent) 訊息 |
| `include_hook_events` | `bool` | `False` | 在訊息串流中包含 hook 生命週期事件作為 `HookEventMessage` 物件 |
| `forward_subagent_text` | `bool` | `False` | 在訊息串流中轉發 subagent 文字和思考區塊。沒有此選項時，Claude Code 會省略在[前景](https://code.claude.com/docs/zh-TW/sub-agents.md#run-subagents-in-foreground-or-background)執行之 subagent 的文字和思考區塊。關於巢狀 subagent、具有 `context: fork` 的 skill，以及各自所需的 Claude Code 版本，請參閱[追蹤 subagent 訊息](https://code.claude.com/docs/zh-TW/headless.md#follow-subagent-messages)。需要 Python Agent SDK 0.2.140 或更新版本 |
| `verbatim_prompts` | `bool` | `False` | 按照所寫內容傳遞每個提示詞。SDK 會使用 `client_composed` 設定為 `True` 傳送每個使用者訊息。請參閱 [`client_composed`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#sdkusermessage) 以了解 Claude Code 在這些訊息上會跳過的內容。當您的提示詞文字包含終端使用者未輸入的內容時，請使用此選項。如需按回合控制，請將其關閉，並改為在個別串流訊息上設定 `"client_composed": True`。啟用此選項時，SDK 會覆寫您設定的任何 `client_composed` 值。需要 Python Agent SDK 0.2.158 或更新版本以及 Claude Code v2.1.248 或更新版本；與這些 SDK 版本搭配的 CLI 滿足 Claude Code 需求 |
| `fork_session` | `bool` | `False` | 使用 `resume` 繼續時，分支到新的工作階段 ID 而不是繼續原始工作階段 |
| `resume_session_at` | `str \| None` | `None` | 繼續時，僅載入對話至包括具有此 UUID 的訊息。與 `resume` 搭配使用，通常還要搭配 `fork_session`，以從較早的點分支。需要 Python Agent SDK 0.2.137 或更新版本 |
| `resume_drops_turn` | `str \| None` | `None` | `resume_session_at` 截斷所捨棄之回合的使用者提示詞 UUID。設定時，如果捨棄的範圍包含不可歸因於該回合的項目，CLI 會拒絕繼續。需要 Python Agent SDK 0.2.137 或更新版本以及 Claude Code v2.1.223 或更新版本；與這些 SDK 版本搭配的 CLI 滿足 Claude Code 需求 |
| `agents` | `dict[str, AgentDefinition] \| None` | `None` | 以程式設計方式定義的 subagent |
| `plugins` | `list[SdkPluginConfig]` | `[]` | 從本機路徑載入自訂外掛。請參閱[外掛](https://code.claude.com/docs/zh-TW/agent-sdk/plugins.md)以取得詳細資訊 |
| `sandbox` | [`SandboxSettings`](#sandboxsettings) ` \| None` | `None` | 以程式設計方式設定沙箱行為。請參閱[沙箱設定](#sandboxsettings)以取得詳細資訊 |
| `setting_sources` | `list[SettingSource] \| None` | `None`（CLI 預設值：所有來源） | 控制要載入哪些檔案系統設定。傳遞 `[]` 以停用使用者、專案和本機設定。設定 `skills` 且此欄位未設定時，僅載入使用者和專案來源。明確設定 `setting_sources` 以保留本機設定。端點管理的原則無論如何都會載入；當工作階段使用組織憑證在[合格組態](https://code.claude.com/docs/zh-TW/server-managed-settings.md#platform-availability)上進行驗證時，會擷取伺服器管理的設定。如需無論此選項如何都會讀取的輸入，請參閱[settingSources 不控制的內容](https://code.claude.com/docs/zh-TW/agent-sdk/claude-code-features.md#what-settingsources-does-not-control) |
| `skills` | `list[str] \| Literal["all"] \| None` | `None` | 工作階段可用的 skill。傳遞 `"all"` 以啟用每個發現的 skill，或傳遞 skill 名稱清單。僅傳遞確切名稱。SDK 在啟動 Claude Code 程序之前會以 `ValueError` 拒絕格式不正確和萬用字元形式的名稱；此檢查需要 Python Agent SDK 0.2.129 或更新版本。設定時，SDK 會自動將 Skill 工具新增至 `allowed_tools`。如果您也傳遞 `tools`，請在該清單中包含 `"Skill"`。請參閱 [Skill](https://code.claude.com/docs/zh-TW/agent-sdk/skills.md) |
| `max_thinking_tokens` | `int \| None` | `None` | *已棄用* - 思考區塊的最大 token 數。改用 `thinking` |
| `thinking` | [`ThinkingConfig`](#thinkingconfig) ` \| None` | `None` | 控制延伸思考行為。優先於 `max_thinking_tokens` |
| `effort` | [`EffortLevel`](#effortlevel) ` \| None` | `None` | 思考深度的 effort 等級。請參閱[調整 effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level) |
| `session_store` | [`SessionStore`](https://code.claude.com/docs/zh-TW/agent-sdk/session-storage#the-sessionstore-interface) ` \| None` | `None` | 將工作階段逐字稿鏡像到外部後端，以便另一個主機可以繼續它們。請參閱[將工作階段保存到外部儲存體](https://code.claude.com/docs/zh-TW/agent-sdk/session-storage.md) |
| `session_store_flush` | `Literal["batched", "eager"]` | `"batched"` | 何時將鏡像逐字稿項目排清到 `session_store`。`"batched"` 每回合排清一次或當緩衝區填滿時；`"eager"` 在每個框架後觸發背景排清。當 `session_store` 為 `None` 時忽略 |
| `load_timeout_ms` | `int` | `60000` | 在繼續具體化期間，`session_store.load()` 和 `list_subkeys()` 的每次呼叫逾時（以毫秒為單位） |
| `task_budget` | `TaskBudget \| None` | `None` | API 端 token 預算。使用 `task-budgets-2026-03-13` 測試版標頭作為 `output_config.task_budget` 傳送。傳遞 `{"total": <int>}`。 |

#### 處理緩慢或停滯的 API 回應

CLI 子程序讀取多個環境變數，這些變數控制 API 逾時和停滯偵測。透過 `ClaudeAgentOptions.env` 傳遞它們：

```python theme={null}
from claude_agent_sdk import ClaudeAgentOptions

options = ClaudeAgentOptions(
    env={
        "API_TIMEOUT_MS": "120000",
        "CLAUDE_CODE_MAX_RETRIES": "2",
        "CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS": "120000",
    },
)
```

* [`API_TIMEOUT_MS`](https://code.claude.com/docs/zh-TW/env-vars)：每次請求嘗試可等待回應標頭的時間（以毫秒為單位）。它不會限制標頭到達後串流回應的執行時間。預設 `600000`。適用於主迴圈和所有 subagent。
* `CLAUDE_CODE_MAX_RETRIES`：最大 API 重試次數。預設 `10`，上限為 `15`。每次重試都有自己的 `API_TIMEOUT_MS` 視窗。

  對於需要等待較長中斷的無人值守執行，設定 [`CLAUDE_CODE_RETRY_WATCHDOG=1`](https://code.claude.com/docs/zh-TW/errors#tune-retry-behavior)：它無限期重試暫時性容量錯誤，並且在 Claude Code v2.1.199 或更新版本上，將其他暫時性錯誤的預設值提高到 `300` 並移除此變數的上限。
* `CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS`：subagent 的停滯監視程式。當串流監視程式開啟時，預設值為 `CLAUDE_STREAM_IDLE_TIMEOUT_MS` 加上 5 分鐘，總計 `600000`，除非您提高該變數。關閉串流監視程式時，預設值為 `600000`。在 v2.1.257 之前，預設值始終為 `600000`。

  計時器在每個串流事件時重設。停滯時，Claude Code 會中止 subagent 並向父 agent 報告停滯。對於背景 subagent，它也會將任務標記為失敗並附加任何部分結果。
* `CLAUDE_ENABLE_STREAM_WATCHDOG` 搭配 `CLAUDE_STREAM_IDLE_TIMEOUT_MS`：串流監視程式，當標頭已到達但回應本文停止串流時中止請求。監視程式預設對所有提供者開啟；設定 `CLAUDE_ENABLE_STREAM_WATCHDOG=0` 以停用它。`CLAUDE_STREAM_IDLE_TIMEOUT_MS` 預設為 `300000` 並固定到該最小值。中止後，[自動重試](https://code.claude.com/docs/zh-TW/errors.md#automatic-retries)說明 Claude Code 會根據回應的進度採取什麼行動。

  當監視程式等待 `ANTHROPIC_BASE_URL` 後面的閘道以保活 ping 保持開啟的回應時，設定 `include_partial_messages` 的主機會繼續接收 `ping` [`StreamEvent`](#streamevent) 訊息。將這些框架讀取為活躍性，而不是在沉默時讓工作階段逾時。在 v2.1.257 之前，框架在最後一個真實串流事件後 5 分鐘停止。

### `OutputFormat`

結構化輸出驗證的設定。作為 `dict` 傳遞至 `ClaudeAgentOptions` 上的 `output_format` 欄位：

```python theme={null}
# output_format 的預期字典形狀
{
    "type": "json_schema",
    "schema": {...},  # 您的 JSON Schema 定義
}
```

| 欄位 | 必要 | 說明 |
| :- | :- | :- |
| `type` | 是 | 必須為 `"json_schema"` 以進行 JSON Schema 驗證 |
| `schema` | 是 | 用於輸出驗證的 JSON Schema 定義 |

### `SystemPromptPreset`

使用 Claude Code 的預設系統提示詞（含選用新增項目）的設定。

```python theme={null}
class SystemPromptPreset(TypedDict):
    type: Literal["preset"]
    preset: Literal["claude_code"]
    append: NotRequired[str]
    exclude_dynamic_sections: NotRequired[bool]
    snapshot: NotRequired[bool]
```

| 欄位 | 必要 | 說明 |
| :- | :- | :- |
| `type` | 是 | 必須為 `"preset"` 以使用預設系統提示詞 |
| `preset` | 是 | 必須為 `"claude_code"` 以使用 Claude Code 的系統提示詞 |
| `append` | 否 | 要附加到預設系統提示詞的其他指示 |
| `exclude_dynamic_sections` | 否 | 將每個使用者的上下文（例如自動記憶位置）從系統提示詞移至第一個使用者訊息。改善跨使用者和機器的提示快取重複使用。請參閱[修改系統提示詞](https://code.claude.com/docs/zh-TW/agent-sdk/modifying-system-prompts.md#improve-prompt-caching-across-users-and-machines) |
| `snapshot` | 否 | 設定為 `False` 以在每個請求上重建系統提示詞，而不是[重複使用工作階段在其第一個請求上記錄的提示詞](https://code.claude.com/docs/zh-TW/agent-sdk/modifying-system-prompts.md#change-the-prompt-of-an-existing-session)。需要 `claude-agent-sdk` v0.2.153 或更新版本 |

### `SystemPromptCustom`

物件形式的自訂系統提示詞，等同於傳遞字串作為 `system_prompt`，也可以設定 `snapshot`。需要 `claude-agent-sdk` v0.2.153 或更新版本。

```python theme={null}
class SystemPromptCustom(TypedDict):
    type: Literal["custom"]
    prompt: str
    snapshot: NotRequired[bool]
```

| 欄位 | 必要 | 說明 |
| :- | :- | :- |
| `type` | 是 | 必須為 `"custom"` |
| `prompt` | 是 | 系統提示詞文字。作為命令列引數傳遞給 CLI，因此[命令列長度限制](#systempromptfile)適用 |
| `snapshot` | 否 | 與 [`SystemPromptPreset.snapshot`](#systempromptpreset) 相同，套用至 `prompt` |

### `SystemPromptFile`

用於從檔案載入自訂系統提示詞（而不是以字串傳遞）的設定。SDK 將此對應至 CLI [`--system-prompt-file`](https://code.claude.com/docs/zh-TW/cli-reference#system-prompt-flags) 旗標。當提示詞很大時使用檔案形式：SDK 在 CLI 子程序 argv 上傳遞字串 `system_prompt`，在 SDK 傳送任何 API 請求之前就會受到 OS 命令列長度限制。在 Linux 上，單一引數長於大約 128 KB 會在程序生成時失敗，並出現 `Argument list too long`。在 Windows 上，整個命令列上限為大約 32 KB，因此字串形式在較低的閾值失敗。

```python theme={null}
class SystemPromptFile(TypedDict):
    type: Literal["file"]
    path: str
```

| 欄位 | 必要 | 說明 |
| :- | :- | :- |
| `type` | 是 | 必須為 `"file"` 以從磁碟載入提示詞 |
| `path` | 是 | 包含系統提示詞的檔案路徑 |

### `SettingSource`

控制 SDK 從哪些基於檔案系統的設定來源載入設定。

```python theme={null}
SettingSource = Literal["user", "project", "local"]
```

| 值 | 說明 | 位置 |
| :- | :- | :- |
| `"user"` | 全域使用者設定 | `~/.claude/settings.json` |
| `"project"` | 共用專案設定（版本控制） | `.claude/settings.json` |
| `"local"` | 本機專案設定，當 Claude Code 將設定儲存到其中時會被 gitignore | `.claude/settings.local.json` |

#### 預設行為

當 `setting_sources` 被省略或為 `None` 且 `skills` 未設定時，`query()` 載入與 Claude Code CLI 相同的檔案系統設定：使用者、專案和本機。設定 `skills` 時，[`setting_sources`](#claudeagentoptions) 列描述目前的預設值。端點管理的原則在所有情況下都會載入；當工作階段使用組織憑證在[合格組態](https://code.claude.com/docs/zh-TW/server-managed-settings.md#platform-availability)上進行驗證時，會擷取伺服器管理的設定。如需詳細資訊，請參閱[settingSources 不控制的內容](https://code.claude.com/docs/zh-TW/agent-sdk/claude-code-features.md#what-settingsources-does-not-control)。

#### 為什麼使用 setting\_sources

**停用檔案系統設定：**

```python theme={null}
# 不要從磁碟載入使用者、專案或本機設定
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions


async def main():
    async for message in query(
        prompt="Analyze this code",
        options=ClaudeAgentOptions(
            setting_sources=[]
        ),
    ):
        print(message)


asyncio.run(main())
```

> [!NOTE]
>
> 在 Python SDK 0.1.59 及更早版本中，空清單的處理方式與省略選項相同，因此 `setting_sources=[]` 未停用檔案系統設定。如果您需要空清單生效，請升級到較新版本。TypeScript SDK 不受影響。

**僅載入特定設定來源：**

```python theme={null}
# 僅載入專案設定，忽略使用者和本機
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions


async def main():
    async for message in query(
        prompt="Run CI checks",
        options=ClaudeAgentOptions(
            setting_sources=["project"]  # 僅 .claude/settings.json
        ),
    ):
        print(message)


asyncio.run(main())
```

**僅限 SDK 的應用程式：**

```python theme={null}
# 以程式設計方式定義所有內容。
# 傳遞 [] 以選擇退出檔案系統設定來源。
import asyncio
from claude_agent_sdk import AgentDefinition, ClaudeAgentOptions, query


async def main():
    async for message in query(
        prompt="Review this PR",
        options=ClaudeAgentOptions(
            setting_sources=[],
            agents={
                "code-reviewer": AgentDefinition(
                    description="Reviews code changes",
                    prompt="You are a code reviewer. Report issues in the diff.",
                ),
            },
            allowed_tools=["Read", "Grep", "Glob"],
        ),
    ):
        print(message)


asyncio.run(main())
```

若要載入 CLAUDE.md 專案指示，請在 `setting_sources` 中包含 `"project"`。請參閱[修改系統提示詞](https://code.claude.com/docs/zh-TW/agent-sdk/modifying-system-prompts.md#claude-md-files-for-project-level-instructions)以了解 CLAUDE.md 載入如何與系統提示詞選項互動。

#### 設定優先順序

載入多個來源時，設定會依此優先順序合併（從高到低）：

1. 本機設定（`.claude/settings.local.json`）
2. 專案設定（`.claude/settings.json`）
3. 使用者設定（`~/.claude/settings.json`）

程式設計選項（例如 `agents`、`allowed_tools` 和 `settings`）會覆寫使用者、專案和本機檔案系統設定。受管原則設定優先於程式設計選項。

### `AgentDefinition`

以程式設計方式定義的 subagent 設定。

```python theme={null}
@dataclass
class AgentDefinition:
    description: str
    prompt: str
    tools: list[str] | None = None
    disallowedTools: list[str] | None = None
    model: str | None = None
    skills: list[str] | None = None
    memory: Literal["user", "project", "local"] | None = None
    mcpServers: list[str | dict[str, Any]] | None = None
    initialPrompt: str | None = None
    maxTurns: int | None = None
    background: bool | None = None
    effort: EffortLevel | int | None = None
    permissionMode: PermissionMode | None = None
```

| 欄位 | 必要 | 說明 |
| :- | :- | :- |
| `description` | 是 | 何時使用此 agent 的自然語言說明 |
| `prompt` | 是 | agent 的系統提示詞 |
| `tools` | 否 | 允許的工具名稱陣列。如果省略，繼承[subagent 可用的每個工具](https://code.claude.com/docs/zh-TW/sub-agents.md#available-tools) |
| `disallowedTools` | 否 | 要從 agent 的工具集中移除的工具名稱陣列。也接受 MCP 伺服器層級的模式：`mcp__server` 或 `mcp__server__*` 移除該伺服器的每個工具，`mcp__*` 移除任何伺服器的每個 MCP 工具 |
| `model` | 否 | 此 agent 的模型覆寫。接受別名（例如 `"sonnet"`、`"opus"`、`"haiku"` 或 `"inherit"`）或完整模型 ID。省略時，Claude Code 會依[subagent 模型順序](https://code.claude.com/docs/zh-TW/sub-agents.md#choose-a-model)選擇模型 |
| `skills` | 否 | 在啟動時預先載入 agent 上下文的 skill 名稱清單。未列出的 skill 仍可透過 Skill 工具叫用 |
| `memory` | 否 | 此 agent 的記憶來源：`"user"`、`"project"` 或 `"local"` |
| `mcpServers` | 否 | 此 agent 可用的 MCP 伺服器。每個項目是伺服器名稱或內嵌 `{name: config}` 字典 |
| `initialPrompt` | 否 | 當此 agent 作為主執行緒 agent 執行時，自動提交為第一個使用者回合 |
| `maxTurns` | 否 | agent 停止前的最大 agent 回合數 |
| `background` | 否 | 叫用時以非封鎖背景任務執行此 agent |
| `effort` | 否 | 此 agent 的推理 effort 等級。接受命名等級或整數。請參閱 [`EffortLevel`](#effortlevel) |
| `permissionMode` | 否 | 此 agent 內工具執行的權限模式。[subagent 繼承規則](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#available-modes)決定何時適用。請參閱 [`PermissionMode`](#permissionmode) |

> [!NOTE]
>
> `AgentDefinition` 欄位名稱使用 camelCase，例如 `disallowedTools`、`permissionMode` 和 `maxTurns`。這些名稱直接對應至與 TypeScript SDK 共用的線路格式。這與 `ClaudeAgentOptions` 不同，後者對等頂層欄位（例如 `disallowed_tools` 和 `permission_mode`）使用 Python snake\_case。因為 `AgentDefinition` 是資料類別，傳遞 snake\_case 關鍵字會在建構時引發 `TypeError`。

### `PermissionMode`

用於控制工具執行的權限模式。

```python theme={null}
PermissionMode = Literal[
    "default",  # 標準權限行為
    "acceptEdits",  # 自動接受檔案編輯
    "plan",  # 規劃模式 - 探索而不編輯
    "dontAsk",  # 拒絕任何未預先核准的內容，而不是提示
    "bypassPermissions",  # 略過權限檢查；明確的 ask 規則仍會提示（謹慎使用）
    "auto",  # 模型分類器會審查 shell 命令和網路請求等動作
]
```

### `EffortLevel`

用於指導思考深度的 effort 等級。

```python theme={null}
EffortLevel = Literal[
    "low",  # 最少思考，最快回應
    "medium",  # 適度思考
    "high",  # 深度推理
    "xhigh",  # 延伸推理；在不支援的模型上改用「high」
    "max",  # 最大 effort
]
```

### `CanUseTool`

工具權限回呼函式的類型別名。

```python theme={null}
CanUseTool = Callable[
    [str, dict[str, Any], ToolPermissionContext], Awaitable[PermissionResult]
]
```

回呼接收：

* `tool_name`：被呼叫工具的名稱
* `input_data`：工具的輸入參數
* `context`：具有其他資訊的 `ToolPermissionContext`

傳回 `PermissionResult`（`PermissionResultAllow` 或 `PermissionResultDeny`）。

回呼是互動式權限提示的 SDK 替代品：僅在[權限評估流程](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#how-permissions-are-evaluated)解決為提示時叫用。由 `allowed_tools` 項目、設定允許規則或權限模式（例如 `acceptEdits` 或 `bypassPermissions`）預先核准的工具呼叫永遠不會叫用它。若要限制每個工具呼叫，請改用 [`PreToolUse` hook](https://code.claude.com/docs/zh-TW/agent-sdk/hooks)。

允許規則不會預先核准[任何模式都不自動核准的動作](https://code.claude.com/docs/zh-TW/permission-modes.md#actions-no-mode-auto-approves)；請參閱[權限如何評估](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#how-permissions-are-evaluated)以了解其中哪些到達回呼以及在 `dontAsk` 和 `auto` 模式中發生的情況。

### `ToolPermissionContext`

傳遞至工具權限回呼的上下文資訊。

```python theme={null}
@dataclass
class ToolPermissionContext:
    signal: Any | None = None  # 未來：中止信號支援
    suggestions: list[PermissionUpdate] = field(default_factory=list)
    tool_use_id: str | None = None
    agent_id: str | None = None
    blocked_path: str | None = None
    decision_reason: str | None = None
    title: str | None = None
    display_name: str | None = None
    description: str | None = None
```

| 欄位 | 類型 | 說明 |
| :- | :- | :- |
| `signal` | `Any \| None` | 保留供未來中止信號支援 |
| `suggestions` | `list[PermissionUpdate]` | 來自 CLI 的權限更新建議。Bash 提示包含具有 `localSettings` 目的地的建議，因此在 `updated_permissions` 中傳回它會將規則寫入 `.claude/settings.local.json` 並跨工作階段保存。 |
| `tool_use_id` | `str \| None` | 此提示所針對的特定工具呼叫的識別碼。傳遞至 `can_use_tool` 時始終填入 |
| `agent_id` | `str \| None` | 呼叫源自 subagent 時的 subagent ID；主 agent 為 `None` |
| `blocked_path` | `str \| None` | 觸發權限請求的檔案路徑（如適用）。例如，當 Bash 命令嘗試存取允許目錄外的路徑時 |
| `decision_reason` | `str \| None` | 觸發此權限請求的原因。當 PreToolUse hook 傳回 `"ask"` 時，從該 hook 的 `permissionDecisionReason` 轉發 |
| `title` | `str \| None` | 完整權限提示句子，例如 `Claude wants to read foo.txt`。存在時用作主要提示文字 |
| `display_name` | `str \| None` | 工具動作的簡短名詞片語，例如 `Read file`，適合按鈕標籤 |
| `description` | `str \| None` | 權限 UI 的人類可讀副標題 |

### `PermissionResult`

權限回呼結果的聯合類型。

```python theme={null}
PermissionResult = PermissionResultAllow | PermissionResultDeny
```

### `PermissionResultAllow`

指示應允許工具呼叫的結果。

```python theme={null}
@dataclass
class PermissionResultAllow:
    behavior: Literal["allow"] = "allow"
    updated_input: dict[str, Any] | None = None
    updated_permissions: list[PermissionUpdate] | None = None
```

| 欄位 | 類型 | 預設值 | 說明 |
| :- | :- | :- | :- |
| `behavior` | `Literal["allow"]` | `"allow"` | 必須為「allow」 |
| `updated_input` | `dict[str, Any] \| None` | `None` | 要使用的修改輸入而不是原始輸入 |
| `updated_permissions` | `list[PermissionUpdate] \| None` | `None` | 要套用的權限更新 |

如果您傳回的 `PermissionResultAllow` 在 `updated_permissions` 中包含超過 4,096 個項目，Claude Code 會將結果視為無效並拒絕該工具呼叫。每個 [`PermissionUpdate`](#permissionupdate) 計為一個項目，其 `rules` 或 `directories` 清單中的每個條目也各計為一個項目。拒絕訊息的結尾為 `updatedPermissions may hold at most 4096 updates, rules and directories in all.` 若要避免遭拒，請傳回 4,096 個或更少的項目。

### `PermissionResultDeny`

指示應拒絕工具呼叫的結果。

```python theme={null}
@dataclass
class PermissionResultDeny:
    behavior: Literal["deny"] = "deny"
    message: str = ""
    interrupt: bool = False
```

| 欄位 | 類型 | 預設值 | 說明 |
| :- | :- | :- | :- |
| `behavior` | `Literal["deny"]` | `"deny"` | 必須為「deny」 |
| `message` | `str` | `""` | 說明為什麼拒絕工具的訊息 |
| `interrupt` | `bool` | `False` | 是否中斷目前執行 |

### `PermissionUpdate`

以程式設計方式更新權限的設定。

```python theme={null}
@dataclass
class PermissionUpdate:
    type: Literal[
        "addRules",
        "replaceRules",
        "removeRules",
        "setMode",
        "addDirectories",
        "removeDirectories",
    ]
    rules: list[PermissionRuleValue] | None = None
    behavior: Literal["allow", "deny", "ask"] | None = None
    mode: PermissionMode | None = None
    directories: list[str] | None = None
    destination: (
        Literal["userSettings", "projectSettings", "localSettings", "session"] | None
    ) = None
```

| 欄位 | 類型 | 說明 |
| :- | :- | :- |
| `type` | `Literal[...]` | 權限更新操作的類型 |
| `rules` | `list[PermissionRuleValue] \| None` | 用於新增/取代/移除操作的規則 |
| `behavior` | `Literal["allow", "deny", "ask"] \| None` | 規則型操作的行為 |
| `mode` | `PermissionMode \| None` | setMode 操作的模式 |
| `directories` | `list[str] \| None` | 用於新增/移除目錄操作的目錄 |
| `destination` | `Literal[...] \| None` | 套用權限更新的位置 |

### `PermissionRuleValue`

要在權限更新中新增、取代或移除的規則。

```python theme={null}
@dataclass
class PermissionRuleValue:
    tool_name: str
    rule_content: str | None = None
```

### `ToolsPreset`

使用 Claude Code 預設工具集的預設工具設定。

```python theme={null}
class ToolsPreset(TypedDict):
    type: Literal["preset"]
    preset: Literal["claude_code"]
```

### `ThinkingConfig`

控制延伸思考行為。三個設定的聯合：

```python theme={null}
ThinkingDisplay = Literal["summarized", "omitted"]


class ThinkingConfigAdaptive(TypedDict):
    type: Literal["adaptive"]
    display: NotRequired[ThinkingDisplay]


class ThinkingConfigEnabled(TypedDict):
    type: Literal["enabled"]
    budget_tokens: int
    display: NotRequired[ThinkingDisplay]


class ThinkingConfigDisabled(TypedDict):
    type: Literal["disabled"]


ThinkingConfig = ThinkingConfigAdaptive | ThinkingConfigEnabled | ThinkingConfigDisabled
```

| 變體 | 欄位 | 說明 |
| :- | :- | :- |
| `adaptive` | `type`、`display` | Claude 自適應決定何時思考 |
| `enabled` | `type`、`budget_tokens`、`display` | 啟用具有特定 token 預算的思考 |
| `disabled` | `type` | 停用思考 |

選用的 `display` 欄位控制思考文字是否傳回 `"summarized"` 或 `"omitted"`。在 Claude Opus 4.7 及更新版本上，API 預設值為 `"omitted"`，因此設定 `"summarized"` 以在 [`ThinkingBlock`](#thinkingblock) 輸出中接收思考內容。Claude Code 不會將您的 `display` 值傳遞給部分提供者，例如 Amazon Bedrock 和 Google Cloud 的 Agent Platform。在這些提供者上，即使您將 `display` 設定為 `"summarized"`，Opus 4.7 及更新版本也會傳回空的 `ThinkingBlock` 輸出。

因為這些是 `TypedDict` 類別，它們在執行時是純字典。將它們建構為字典常值或呼叫類別作為建構函式；兩者都會產生 `dict`。使用 `config["budget_tokens"]` 存取欄位，而不是 `config.budget_tokens`：

```python theme={null}
from claude_agent_sdk import ClaudeAgentOptions, ThinkingConfigEnabled

# 選項 1：字典常值（建議，不需要匯入）
options = ClaudeAgentOptions(thinking={"type": "enabled", "budget_tokens": 20000})

# 選項 2：建構函式樣式（傳回純字典）
config = ThinkingConfigEnabled(type="enabled", budget_tokens=20000)
print(config["budget_tokens"])  # 20000
# config.budget_tokens 會引發 AttributeError
```

### `TaskBudget`

API 端任務預算（以 token 為單位），與 `ClaudeAgentOptions` 中的 `task_budget` 欄位搭配使用。

```python theme={null}
class TaskBudget(TypedDict):
    total: int
```

| 欄位 | 類型 | 說明 |
| :- | :- | :- |
| `total` | `int` | 任務的總 token 預算 |

因為這是 `TypedDict`，將其作為純字典傳遞，例如 `ClaudeAgentOptions(task_budget={"total": 50000})`。

### `SdkBeta`

SDK 測試版功能的常值類型。

```python theme={null}
SdkBeta = Literal["context-1m-2025-08-07"]
```

與 `ClaudeAgentOptions` 中的 `betas` 欄位搭配使用以啟用測試版功能。

> [!WARNING]
>
> 在 Claude API 上，`context-1m-2025-08-07` 測試版已針對 Claude Sonnet 4.5 和 Claude Sonnet 4 停用。如果您仍在使用這兩個模型之一時傳遞它，超過標準 200K token 上下文視窗的請求會傳回錯誤，因此請將其從 `betas` 中移除。若要以 1M token 上下文視窗執行工作階段，請將 `model` 設定為[預設以 1M 視窗執行](https://code.claude.com/docs/zh-TW/model-config.md#extended-context)的模型，例如 `claude-sonnet-5-5` 或 `claude-opus-5-5`。對於僅能透過其 `[1m]` 變體達到 1M 的模型，請將後綴附加到模型 ID，例如 `claude-opus-4-6[1m]`。

### `McpSdkServerConfig`

使用 `create_sdk_mcp_server()` 建立的 SDK MCP 伺服器設定。

```python theme={null}
class McpSdkServerConfig(TypedDict):
    type: Literal["sdk"]
    name: str
    instance: Any  # MCP Server instance
```

### `McpServerConfig`

MCP 伺服器設定的聯合類型。

```python theme={null}
McpServerConfig = (
    McpStdioServerConfig | McpSSEServerConfig | McpHttpServerConfig | McpSdkServerConfig
)
```

#### `McpStdioServerConfig`

```python theme={null}
class McpStdioServerConfig(TypedDict):
    type: NotRequired[Literal["stdio"]]  # 為了向後相容性為選用
    command: str
    args: NotRequired[list[str]]
    env: NotRequired[dict[str, str]]
```

#### `McpSSEServerConfig`

```python theme={null}
class McpSSEServerConfig(TypedDict):
    type: Literal["sse"]
    url: str
    headers: NotRequired[dict[str, str]]
```

#### `McpHttpServerConfig`

```python theme={null}
class McpHttpServerConfig(TypedDict):
    type: Literal["http"]
    url: str
    headers: NotRequired[dict[str, str]]
```

### `McpServerStatusConfig`

由 [`get_mcp_status()`](#methods) 報告的 MCP 伺服器設定。這是所有 [`McpServerConfig`](#mcpserverconfig) 傳輸變體加上用於透過 claude.ai 代理的伺服器的僅輸出 `claudeai-proxy` 變體的聯合。

```python theme={null}
McpServerStatusConfig = (
    McpStdioServerConfig
    | McpSSEServerConfig
    | McpHttpServerConfig
    | McpSdkServerConfigStatus
    | McpClaudeAIProxyServerConfig
)
```

`McpSdkServerConfigStatus` 是 [`McpSdkServerConfig`](#mcpsdkserverconfig) 的可序列化形式，僅包含 `type`（`"sdk"`）和 `name`（`str`）欄位；程序內 `instance` 被省略。`McpClaudeAIProxyServerConfig` 具有 `type`（`"claudeai-proxy"`）、`url`（`str`）和 `id`（`str`）欄位。

### `McpStatusResponse`

來自 [`ClaudeSDKClient.get_mcp_status()`](#methods) 的回應。在 `mcpServers` 鍵下包裝伺服器狀態清單。

```python theme={null}
class McpStatusResponse(TypedDict):
    mcpServers: list[McpServerStatus]
```

### `McpServerStatus`

連線 MCP 伺服器的狀態，包含在 [`McpStatusResponse`](#mcpstatusresponse) 中。

```python theme={null}
class McpServerStatus(TypedDict):
    name: str
    status: McpServerConnectionStatus  # "connected" | "failed" | "needs-auth" | "pending" | "disabled"
    serverInfo: NotRequired[McpServerInfo]
    error: NotRequired[str]
    config: NotRequired[McpServerStatusConfig]
    scope: NotRequired[str]
    tools: NotRequired[list[McpToolInfo]]
```

| 欄位 | 類型 | 說明 |
| :- | :- | :- |
| `name` | `str` | 伺服器名稱 |
| `status` | `str` | `"connected"`、`"failed"`、`"needs-auth"`、`"pending"` 或 `"disabled"` 之一 |
| `serverInfo` | `dict`（選用） | 伺服器名稱和版本（`{"name": str, "version": str}`） |
| `error` | `str`（選用） | 伺服器連線失敗時的錯誤訊息 |
| `config` | [`McpServerStatusConfig`](#mcpserverstatusconfig)（選用） | 伺服器設定。與 [`McpServerConfig`](#mcpserverconfig)（stdio、SSE、HTTP 或 SDK）相同的形狀，加上用於透過 claude.ai 連線的伺服器的 `claudeai-proxy` 變體 |
| `scope` | `str`（選用） | 設定範圍 |
| `tools` | `list`（選用） | 此伺服器提供的工具，每個都具有 `name`、`description` 和 `annotations` 欄位 |

### `ContextUsageResponse`

來自 [`ClaudeSDKClient.get_context_usage()`](#methods) 的回應。此回應包含 Claude Code 在互動式工作階段中為 `/context` 命令呈現的 payload。除了 token 計數外，該 payload 還帶有顯示欄位，例如 `color` 和 `gridRows`，Claude Code 使用這些欄位來繪製 `/context` 使用量網格。

Claude Code 透過向 [token 計數](https://platform.claude.com/docs/en/build-with-claude/token-counting) API 傳送多個請求來建立此 payload。這些請求不會出現在訊息串流中，因此讀取串流的成本追蹤不會看到它們。在 Anthropic API 上，token 計數不計費。

```python theme={null}
class ContextUsageResponse(TypedDict):
    categories: list[ContextUsageCategory]
    totalTokens: int
    maxTokens: int
    rawMaxTokens: int
    percentage: float
    model: str
    isAutoCompactEnabled: bool
    memoryFiles: list[dict[str, Any]]
    mcpTools: list[dict[str, Any]]
    agents: list[dict[str, Any]]
    gridRows: list[list[dict[str, Any]]]
    autoCompactThreshold: NotRequired[int]
    deferredBuiltinTools: NotRequired[list[dict[str, Any]]]
    systemTools: NotRequired[list[dict[str, Any]]]
    systemPromptSections: NotRequired[list[dict[str, Any]]]
    slashCommands: NotRequired[dict[str, Any]]
    skills: NotRequired[dict[str, Any]]  # skill usage with frontmatter breakdown
    messageBreakdown: NotRequired[dict[str, Any]]  # message tokens by type
    apiUsage: NotRequired[dict[str, Any] | None]
```

每個 `ContextUsageCategory` 項目帶有 `name`、`tokens`、`color` 和選用的 `isDeferred` 旗標。`totalTokens` 是工作階段目前的上下文使用量，`maxTokens` 是測量該使用量所依據的視窗。該視窗是模型的上下文視窗，或適用時較低的自動壓縮視窗，`rawMaxTokens` 帶有與 `maxTokens` 相同的值。`apiUsage` 保留最新 API 回應的使用量，而不是工作階段的執行總計。Claude Code 會讓選用的 `deferredBuiltinTools`、`systemTools` 和 `systemPromptSections` 鍵保持未設定，因此即使類型宣告了它們，也應該預期它們不存在。

### `SdkPluginConfig`

在 SDK 中載入外掛的設定。

```python theme={null}
class SdkPluginConfig(TypedDict):
    type: Literal["local"]
    path: str
```

| 欄位 | 類型 | 說明 |
| :- | :- | :- |
| `type` | `Literal["local"]` | 必須為 `"local"`（目前僅支援本機外掛） |
| `path` | `str` | 外掛目錄的絕對或相對路徑 |

**範例：**

```python theme={null}
plugins = [
    {"type": "local", "path": "./my-plugin"},
    {"type": "local", "path": "/absolute/path/to/plugin"},
]
```

如需建立和使用外掛的完整資訊，請參閱[外掛](https://code.claude.com/docs/zh-TW/agent-sdk/plugins.md)。

## 消息類型

### `Message`

所有可能消息的聯合類型。

```python theme={null}
Message = (
    UserMessage
    | AssistantMessage
    | SystemMessage
    | ResultMessage
    | StreamEvent
    | RateLimitEvent
    | ConversationResetMessage
)
```

### `UserMessage`

使用者輸入消息。

```python theme={null}
@dataclass
class UserMessage:
    content: str | list[ContentBlock]
    uuid: str | None = None
    parent_tool_use_id: str | None = None
    tool_use_result: dict[str, Any] | None = None
    origin: MessageOrigin | None = None
```

| 欄位 | 類型 | 描述 |
| :- | :- | :- |
| `content` | `str \| list[ContentBlock]` | 消息內容為文字或內容區塊 |
| `uuid` | `str \| None` | 唯一消息識別碼 |
| `parent_tool_use_id` | `str \| None` | 如果此消息是 tool 結果回應，則為 tool 使用 ID |
| `tool_use_result` | `dict[str, Any] \| None` | tool 結果資料（如適用） |
| `origin` | `MessageOrigin \| None` | 此消息的來源，在注入的轉（例如任務通知和對等消息）上填入。當 CLI 未歸屬時為 `None`。需要 Python Agent SDK 0.2.137 或更新版本 |

SDK 從 CLI 未修改地傳遞 `tool_use_result`。對於外部 MCP 伺服器上的 tool，其結果包含 `resource_link` 區塊，該字典具有 TypeScript [`SDKMcpResourceLink`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#sdkmcpresourcelink) 類型的鍵的 `resourceLinks` 鍵，保存字典清單。Claude 將每個連結作為 tool 結果中的一行文字接收。若要呈現伺服器返回的檔案，請讀取 `resourceLinks` 而不是解析該文字。`resourceLinks` 鍵需要 Python Agent SDK 0.2.150 或更新版本和 Claude Code v2.1.257 或更新版本；該 SDK 版本隨附的 CLI 滿足 Claude Code 要求。

CLI 在結果沒有連結時和子代理的結果上省略該鍵。CLI 每個結果最多保留 50 個連結，一旦清單達到 64 KiB 的序列化 JSON，就停止新增連結。使用 [`tool()`](#tool) 在程序中定義的 tool 永遠不會產生該鍵，因為 SDK 在 CLI 看到結果之前將其 `resource_link` 區塊扁平化為文字。

### `AssistantMessage`

具有內容區塊的助手回應消息。

```python theme={null}
@dataclass
class AssistantMessage:
    content: list[ContentBlock]
    model: str
    parent_tool_use_id: str | None = None
    error: AssistantMessageError | None = None
    usage: dict[str, Any] | None = None
    message_id: str | None = None
    stop_reason: str | None = None
    session_id: str | None = None
    uuid: str | None = None
```

| 欄位 | 類型 | 描述 |
| :- | :- | :- |
| `content` | `list[ContentBlock]` | 回應中的內容區塊清單 |
| `model` | `str` | 產生回應的模型 |
| `parent_tool_use_id` | `str \| None` | 如果這是嵌套回應，則為 tool 使用 ID |
| `error` | [`AssistantMessageError`](#assistantmessageerror) ` \| None` | 如果回應遇到錯誤，則為錯誤類型 |
| `usage` | `dict[str, Any] \| None` | 每消息令牌使用情況（與 [`ResultMessage.usage`](#resultmessage) 相同的鍵） |
| `message_id` | `str \| None` | API 消息 ID。來自一個轉的多個消息共享相同的 ID |
| `stop_reason` | `str \| None` | 來自 API 的停止原因（例如 `end_turn`、`tool_use`） |
| `session_id` | `str \| None` | 此消息所屬的 session ID |
| `uuid` | `str \| None` | session 文字記錄中的唯一消息識別碼 |

### `AssistantMessageError`

助手消息的可能錯誤類型。

```python theme={null}
AssistantMessageError = Literal[
    "authentication_failed",
    "billing_error",
    "rate_limit",
    "invalid_request",
    "server_error",
    "unknown",
]
```

基礎 CLI 程序可以發出此 Literal 未列出的錯誤類型，例如 `max_output_tokens`。SDK 未修改地傳遞該值，因此將此清單外的字串視為您對待 `unknown` 的方式。TypeScript [`SDKAssistantMessageError`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#sdkassistantmessage) 類型列出 CLI 可以發出的完整值集。

### `SystemMessage`

具有中繼資料的系統消息。

```python theme={null}
@dataclass
class SystemMessage:
    subtype: str
    data: dict[str, Any]
```

沒有專屬 dataclass 的 subtype 會以 `SystemMessage` 的形式送達。若要在回合之間追蹤工作階段，請設定 [`CLAUDE_CODE_EMIT_SESSION_STATE_EVENTS=1`](https://code.claude.com/docs/zh-TW/env-vars#variables)，並在每則 `subtype` 為 `session_state_changed` 的消息上讀取 `message.data["state"]`。[`SDKSessionStateChangedMessage`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#sdksessionstatechangedmessage) 列出它可能攜帶的狀態。請使用 `receive_messages()` 進行迭代以讀取這些消息：`receive_response()` 會在 `ResultMessage` 處停止，而 `session_state_changed` 消息可能出現在該結果之後。

### `ResultMessage`

具有成本和使用情況資訊的最終結果消息。

```python theme={null}
@dataclass
class ResultMessage:
    subtype: str
    duration_ms: int
    duration_api_ms: int
    is_error: bool
    num_turns: int
    session_id: str
    stop_reason: str | None = None
    total_cost_usd: float | None = None
    usage: dict[str, Any] | None = None
    result: str | None = None
    structured_output: Any = None
    model_usage: dict[str, ModelUsage] | None = None
    permission_denials: list[Any] | None = None
    deferred_tool_use: DeferredToolUse | None = None
    errors: list[str] | None = None
    api_error_status: int | None = None
    uuid: str | None = None
    terminal_reason: str | None = None
    origin: MessageOrigin | None = None
```

`subtype` 欄位決定了其他哪些欄位會被填入。它是 `"success"`、`"error_during_execution"`、`"error_max_turns"`、`"error_max_budget_usd"` 或 `"error_max_structured_output_retries"` 之一。Python dataclass 將所有變體扁平化為一個形狀，因此不適用於返回的 subtype 的欄位為 `None`。

多個欄位會帶有診斷詳細資訊，說明對話如何結束：

* `is_error`：當對話以錯誤狀態結束時為 `True`。在 `error_*` subtypes 上始終為 `True`。在 `subtype="success"` 上，有三種情況會為 `True`。請檢查 `stop_reason` 加以區分：
  * `"refusal"`：模型拒絕回應。請在 `result` 中讀取拒絕文字，若 `result` 為空，則在前面的 `AssistantMessage` 中讀取。
  * `"tool_deferred_unavailable"`：當您恢復工作階段時，[延遲的工具](https://code.claude.com/docs/zh-TW/hooks.md#defer-a-tool-call-for-later)已不再可用，例如因為其 MCP 伺服器未連線。在以下兩種情況中，恢復後傳送的提示詞與隨恢復一起傳遞的提示詞視為相同：
    * 沒有提示詞：該呼叫仍待處理。讓工具可用後，再次在不附提示詞的情況下恢復，該呼叫會先執行。
    * 有提示詞：Claude Code 會在沒有工具結果的情況下回答該提示詞，且延遲的呼叫會消失。如果您仍需要呼叫該工具，請傳送新的提示詞。
  * 任何其他值：該回合以 Claude Code 取代模型回應而回報的錯誤結束，例如 API 錯誤。請讀取 `terminal_reason` 以了解原因、讀取 `result` 以取得訊息，並在 API 傳回 HTTP 狀態時讀取 `api_error_status` 以取得該狀態。
* `api_error_status`：終止 API 錯誤的 HTTP 狀態碼。當轉在沒有錯誤的情況下結束時為 `None`。僅在 `subtype="success"` 上填入。
* `result`：在 `subtype="success"` 上為最終助手消息的文字，或在 `error_*` subtypes 上為 `None`。當 `subtype="success"` 且 `is_error=True` 時，如果可用，此欄位會保存 API 錯誤字串，但可能為空，因此請檢查 `api_error_status` 和前面的 `AssistantMessage` 內容以獲取詳細資訊。
* `errors`：迴圈級別的錯誤字串，例如最大轉數消息。僅在 `error_*` subtypes 上填入。
* `terminal_reason`：查詢迴圈結束的原因，例如 `"completed"`、`"max_turns"`、`"api_error"`、`"aborted_streaming"` 或 `"aborted_tools"`。`"aborted_streaming"` 或 `"aborted_tools"` 的值表示轉在完成前被中止。常見原因是 [`interrupt()`](#claudesdkclient) 和權限回呼返回 [`PermissionResultDeny`](#permissionresultdeny) 且 `interrupt=True`。在早於該欄位的 CLI 版本上為 `None`，在本地命令（例如 `/voice` 或 `/usage`）的結果上為 `None`，這些命令繞過查詢迴圈，或在 session 致命失敗時發出的合成錯誤結果上為 `None`。鏡像 TypeScript SDK 的 [`SDKResultMessage.terminal_reason`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#sdkresultmessage)，其列出完整的值集。
* `origin`：觸發此轉的使用者消息的來源。在[串流輸入模式](https://code.claude.com/docs/zh-TW/agent-sdk/streaming-vs-single-mode.md)中，檢查此項以區分您自己提示的結果（其中 `origin` 為 `None` 或 `{"kind": "human"}`）與注入轉（例如背景任務通知）的結果。需要 Python Agent SDK 0.2.137 或更新版本。

當數個背景任務在相近的時間內完成時，Claude Code 可以在一個回合中回應它們的通知，而不是每個通知各用一個回合。您仍會依序為每個通知收到一個 `ResultMessage`，每個都帶有 `kind` 為 `"task-notification"` 的 `origin`。除最後一個之外，其餘的 `num_turns` 皆設為 `0` 且 `result` 為空，而最後一個則承載回應所有通知的回合。

`usage` 字典僅涵蓋主代理迴圈，並排除子代理和其他嵌套或輔助模型呼叫。在[串流輸入模式](https://code.claude.com/docs/zh-TW/agent-sdk/streaming-vs-single-mode.md)中，值是按轉的。優先使用 `model_usage` 進行令牌和成本計算。`usage` 字典在出現時包含以下鍵：

| 鍵 | 類型 | 描述 |
| - | - | - |
| `input_tokens` | `int` | 頂層代理迴圈消耗的輸入令牌。[子代理令牌不包括在內](https://code.claude.com/docs/zh-TW/agent-sdk/cost-tracking.md#get-the-total-cost-of-a-query)；使用 `model_usage` 進行整個樹的計算。 |
| `output_tokens` | `int` | 頂層代理迴圈產生的輸出令牌。子代理令牌不包括在內。 |
| `cache_creation_input_tokens` | `int` | 用於建立新快取項目的令牌。 |
| `cache_read_input_tokens` | `int` | 從現有快取項目讀取的令牌。 |

`model_usage` 字典將模型名稱對應到每個模型的使用情況。它涵蓋透過查詢管道進行的每個模型呼叫：主迴圈、子代理和內部呼叫（例如壓縮和 Workflow 代理）。該管道外的輔助呼叫（例如權限分類器和令牌計數請求）從 `model_usage` 中排除。將 `model_usage` 視為估計值，而不是計費聲明。

在[串流輸入模式](https://code.claude.com/docs/zh-TW/agent-sdk/streaming-vs-single-mode.md)中，`model_usage` 和 `total_cost_usd` 在轉中是累積的，因此讀取最新結果而不是在結果中求和。恢復 session 的呼叫也會計算[從 session 的早期呼叫復原的總計](https://code.claude.com/docs/zh-TW/agent-sdk/cost-tracking.md#accumulate-costs-across-multiple-calls)。請參閱[在串流輸入模式中追蹤成本](https://code.claude.com/docs/zh-TW/agent-sdk/cost-tracking.md#track-costs-in-streaming-input-mode)以了解重設，以及[在 session 崩潰後復原總計](https://code.claude.com/docs/zh-TW/agent-sdk/cost-tracking.md#recover-totals-after-a-session-crash)以了解歸零結果。

`model_usage` 中的每個值都是 `ModelUsage` TypedDict，透過 `from claude_agent_sdk.types import ModelUsage` 匯入。其鍵使用 camelCase，因為 SDK 從基礎 CLI 程序未修改地傳遞該值，符合 TypeScript [`ModelUsage`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#modelusage) 類型：

| 鍵 | 類型 | 描述 |
| - | - | - |
| `inputTokens` | `int` | 此模型的輸入令牌。 |
| `outputTokens` | `int` | 此模型的輸出令牌。 |
| `cacheReadInputTokens` | `int` | 此模型的快取讀取令牌。 |
| `cacheCreationInputTokens` | `int` | 此模型的快取建立令牌。 |
| `webSearchRequests` | `int` | 此模型進行的網路搜尋請求。 |
| `thinkingTokens` | `int` | 此模型產生的思考令牌，已計入 `outputTokens`。在轉在記錄它的 Claude Code 版本上執行之前不存在，並且未在 TypedDict 上宣告，因此使用 `.get()` 讀取它。需要 Python Agent SDK 0.2.150 或更新版本，其隨附的 CLI 記錄它。 |
| `costUSD` | `float` | 此模型的估計成本（以 USD 為單位），在客戶端計算。見[追蹤成本和使用情況](https://code.claude.com/docs/zh-TW/agent-sdk/cost-tracking.md)以了解計費注意事項。 |
| `contextWindow` | `int` | 此模型的上下文視窗大小。 |
| `maxOutputTokens` | `int` | 此模型的最大輸出令牌限制。 |
| `canonicalModel` | `str` | 用於定價查詢的規範模型 ID。可能與用作項目鍵的原始模型字串不同，例如提供者特定的 ID 或別名。並非總是存在。 |
| `provider` | `str` | 提供此模型的 API 提供者，例如 `firstParty`、`bedrock`、`vertex`、`foundry`、`anthropicAws`、`mantle` 或 `gateway`。並非總是存在。 |
| `costBasis` | `str` | 為此模型最新請求定價的價格表：`list` 表示牌價，`managed` 表示 [`modelPricing`](https://code.claude.com/docs/zh-TW/settings-reference#modelpricing) 表，或當兩者皆不符合模型 ID 時為 `unknown`。並非總是存在，且未在 TypedDict 上宣告，因此使用 `.get()` 讀取它。需要 Claude Code v2.1.246 或更新版本。 |

### `StreamEvent`

用於在串流期間進行部分消息更新的串流事件。僅在 `ClaudeAgentOptions` 中 `include_partial_messages=True` 時接收。透過 `from claude_agent_sdk.types import StreamEvent` 匯入。

```python theme={null}
@dataclass
class StreamEvent:
    uuid: str
    session_id: str
    event: dict[str, Any]  # The raw Claude API stream event
    parent_tool_use_id: str | None = None
```

| 欄位 | 類型 | 描述 |
| :- | :- | :- |
| `uuid` | `str` | 此事件的唯一識別碼 |
| `session_id` | `str` | session 識別碼 |
| `event` | `dict[str, Any]` | 原始 Claude API 串流事件資料 |
| `parent_tool_use_id` | `str \| None` | 始終為 `None`。串流事件僅針對主 session 發出。如需子代理歸屬，請使用完整消息，例如 [`AssistantMessage`](#assistantmessage) |

### `RateLimitEvent`

當速率限制狀態變更時發出（例如，從 `"allowed"` 到 `"allowed_warning"`）。使用此來在使用者達到硬限制之前警告他們，或在狀態為 `"rejected"` 時退避。

```python theme={null}
@dataclass
class RateLimitEvent:
    rate_limit_info: RateLimitInfo
    uuid: str
    session_id: str
```

| 欄位 | 類型 | 描述 |
| :- | :- | :- |
| `rate_limit_info` | [`RateLimitInfo`](#ratelimitinfo) | 目前速率限制狀態 |
| `uuid` | `str` | 唯一事件識別碼 |
| `session_id` | `str` | session 識別碼 |

### `RateLimitInfo`

由 [`RateLimitEvent`](#ratelimitevent) 攜帶的速率限制狀態。

```python theme={null}
RateLimitStatus = Literal["allowed", "allowed_warning", "rejected"]
RateLimitType = Literal[
    "five_hour", "seven_day", "seven_day_opus", "seven_day_sonnet", "overage"
]


@dataclass
class RateLimitInfo:
    status: RateLimitStatus
    resets_at: int | None = None
    rate_limit_type: RateLimitType | None = None
    utilization: float | None = None
    overage_status: RateLimitStatus | None = None
    overage_resets_at: int | None = None
    overage_disabled_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
```

| 欄位 | 類型 | 描述 |
| :- | :- | :- |
| `status` | `RateLimitStatus` | 目前狀態，`"allowed"`、`"allowed_warning"` 或 `"rejected"` 之一。`"allowed_warning"` 表示接近限制；`"rejected"` 表示達到限制 |
| `resets_at` | `int \| None` | 速率限制視窗重設時的 Unix 時間戳 |
| `rate_limit_type` | `RateLimitType \| None` | 適用的速率限制視窗 |
| `utilization` | `float \| None` | 消耗的速率限制分數（0.0 到 1.0） |
| `overage_status` | `RateLimitStatus \| None` | 按使用量付費超額使用的狀態（如適用） |
| `overage_resets_at` | `int \| None` | 超額視窗重設時的 Unix 時間戳 |
| `overage_disabled_reason` | `str \| None` | 如果狀態為 `"rejected"`，為什麼超額不可用 |
| `raw` | `dict[str, Any]` | 來自 CLI 的完整原始字典，包括上面未建模的欄位 |

### `ConversationResetMessage`

在不結束連線的情況下替換對話時發出，例如在 `/clear` 之後。請參閱[在串流輸入模式中追蹤成本](https://code.claude.com/docs/zh-TW/agent-sdk/cost-tracking.md#track-costs-in-streaming-input-mode)以了解重設如何影響後續 `ResultMessage` 物件上的執行總計。需要 Python Agent SDK 0.2.137 或更新版本。

```python theme={null}
@dataclass
class ConversationResetMessage:
    new_conversation_id: str
    uuid: str
    session_id: str
```

| 欄位 | 類型 | 描述 |
| :- | :- | :- |
| `new_conversation_id` | `str` | 新對話的不透明識別碼。不是後續消息的 `session_id`；從下一條消息讀取該值 |
| `uuid` | `str` | 唯一消息識別碼 |
| `session_id` | `str` | 被重設的 session 的 ID。重設後的消息帶有新的 `session_id` |

### `TaskStartedMessage`

在背景任務啟動時發出。背景任務是在主轉之外追蹤的任何內容：背景 Bash 命令、[Monitor](#monitor) 監視、透過 Agent tool 生成的子代理或遠端代理。`task_type` 欄位告訴您是哪一個。此命名與 `Task` 到 `Agent` tool 重新命名無關。

```python theme={null}
@dataclass
class TaskStartedMessage(SystemMessage):
    task_id: str
    description: str
    uuid: str
    session_id: str
    tool_use_id: str | None = None
    task_type: str | None = None
```

| 欄位 | 類型 | 描述 |
| :- | :- | :- |
| `task_id` | `str` | 任務的唯一識別碼 |
| `description` | `str` | 任務的描述 |
| `uuid` | `str` | 唯一消息識別碼 |
| `session_id` | `str` | session 識別碼 |
| `tool_use_id` | `str \| None` | 相關聯的 tool 使用 ID |
| `task_type` | `str \| None` | 背景任務的類型：`"local_bash"` 用於背景 Bash 和 Monitor 監視，`"local_agent"` 或 `"remote_agent"` |

### `TaskUsage`

背景任務的令牌和計時資料。

```python theme={null}
class TaskUsage(TypedDict):
    total_tokens: int
    tool_uses: int
    duration_ms: int
```

### `TaskProgressMessage`

定期為執行中的背景任務發出進度更新。

```python theme={null}
@dataclass
class TaskProgressMessage(SystemMessage):
    task_id: str
    description: str
    usage: TaskUsage
    uuid: str
    session_id: str
    tool_use_id: str | None = None
    last_tool_name: str | None = None
```

| 欄位 | 類型 | 描述 |
| :- | :- | :- |
| `task_id` | `str` | 任務的唯一識別碼 |
| `description` | `str` | 目前狀態描述 |
| `usage` | `TaskUsage` | 此任務迄今為止的令牌使用情況 |
| `uuid` | `str` | 唯一消息識別碼 |
| `session_id` | `str` | session 識別碼 |
| `tool_use_id` | `str \| None` | 相關聯的 tool 使用 ID |
| `last_tool_name` | `str \| None` | 任務最後使用的 tool 名稱 |

### `TaskNotificationMessage`

在背景任務完成、失敗或停止時發出。背景任務包括 `run_in_background` Bash 命令、Monitor 監視和背景子代理。

```python theme={null}
@dataclass
class TaskNotificationMessage(SystemMessage):
    task_id: str
    status: TaskNotificationStatus  # "completed" | "failed" | "stopped"
    output_file: str
    summary: str
    uuid: str
    session_id: str
    tool_use_id: str | None = None
    usage: TaskUsage | None = None
```

| 欄位 | 類型 | 描述 |
| :- | :- | :- |
| `task_id` | `str` | 任務的唯一識別碼 |
| `status` | `TaskNotificationStatus` | `"completed"`、`"failed"` 或 `"stopped"` 之一 |
| `output_file` | `str` | 任務輸出檔案的路徑 |
| `summary` | `str` | 任務結果的摘要 |
| `uuid` | `str` | 唯一消息識別碼 |
| `session_id` | `str` | session 識別碼 |
| `tool_use_id` | `str \| None` | 相關聯的 tool 使用 ID |
| `usage` | `TaskUsage \| None` | 任務的最終令牌使用情況 |

當 CLI [將長 MCP tool 呼叫移至背景](https://code.claude.com/docs/zh-TW/mcp.md#automatic-backgrounding-of-long-tool-calls)時，該呼叫的 tool 結果僅保存佔位符，該呼叫的實際結果在此消息中到達。在此類呼叫的 `"completed"` 通知上，CLI 新增 `resource_links` 鍵，列出 tool 透過參考返回的檔案，具有與 [`UserMessage.tool_use_result`](#usermessage) 上的 `resourceLinks` 鍵相同的項目和限制。`resource_links` 鍵需要 Python Agent SDK 0.2.150 或更新版本和 Claude Code v2.1.257 或更新版本；該 SDK 版本隨附的 CLI 滿足 Claude Code 要求。

dataclass 沒有 `resource_links` 的欄位。從消息繼承自 [`SystemMessage`](#systemmessage) 的 `data` 字典讀取它：`message.data.get("resource_links")`。使用 `tool_use_id` 將通知與呼叫相符。當結果沒有連結時和不是 MCP tool 呼叫的任務的通知上，CLI 省略該鍵。

## 內容區塊類型

### `ContentBlock`

所有內容區塊的聯合類型。

```python theme={null}
ContentBlock = (
    TextBlock
    | ThinkingBlock
    | ToolUseBlock
    | ToolResultBlock
    | ServerToolUseBlock
    | ServerToolResultBlock
)
```

### `TextBlock`

文字內容區塊。

```python theme={null}
@dataclass
class TextBlock:
    text: str
```

### `ThinkingBlock`

思考內容區塊（用於具有思考能力的模型）。

```python theme={null}
@dataclass
class ThinkingBlock:
    thinking: str
    signature: str
```

### `ToolUseBlock`

工具使用請求區塊。

```python theme={null}
@dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict[str, Any]
```

### `ToolResultBlock`

工具執行結果區塊。

```python theme={null}
@dataclass
class ToolResultBlock:
    tool_use_id: str
    content: str | list[dict[str, Any]] | None = None
    is_error: bool | None = None
```

## 錯誤類型

下面的類型定義了您的程式碼捕捉的內容。如需查看與這些類型引發的錯誤訊息相關的項目、原因和修正方法，請參閱[疑難排解](https://code.claude.com/docs/zh-TW/agent-sdk/troubleshooting.md)。

### `ClaudeSDKError`

所有 SDK 錯誤的基礎例外類別。

```python theme={null}
class ClaudeSDKError(Exception):
    """Base error for Claude SDK."""
```

當單次 `query()` 以錯誤結果結束時（例如轉數限制錯誤），SDK 會引發 [`ResultError`](#resulterror)。

### `CLINotFoundError`

當 Claude Code CLI 未安裝或找不到時引發。

```python theme={null}
class CLINotFoundError(CLIConnectionError):
    def __init__(
        self, message: str = "Claude Code not found", cli_path: str | None = None
    ):
        """
        Args:
            message: Error message (default: "Claude Code not found")
            cli_path: Optional path to the CLI that was not found
        """
```

### `CLIConnectionError`

當連接到 Claude Code 失敗時引發。

```python theme={null}
class CLIConnectionError(ClaudeSDKError):
    """Failed to connect to Claude Code."""
```

### `ProcessError`

當 Claude Code 程序失敗時引發。

```python theme={null}
class ProcessError(ClaudeSDKError):
    def __init__(
        self, message: str, exit_code: int | None = None, stderr: str | None = None
    ):
        self.exit_code = exit_code
        self.stderr = stderr
```

### `ResultError`

當 Claude Code 程序因執行以錯誤的[結果訊息](#resultmessage)結束（例如轉數限制錯誤或 API 錯誤）而退出時引發。`ResultError` 是 `ProcessError` 的子類別，因此現有的 `except ProcessError` 處理程式也會捕捉它。其屬性包含該結果訊息的欄位，因此您可以根據執行失敗的原因進行分支，而無需解析訊息文字。需要 Python Agent SDK 0.2.140 或更新版本。

```python theme={null}
class ResultError(ProcessError):
    subtype: str | None  # "error_max_turns", "error_during_execution", ...; "success" when the run ended on a failed request
    errors: list[str]  # an empty list when the result message reported none
    result: str | None
    api_error_status: int | None
    terminal_reason: str | None  # "max_turns", "api_error", ...; check after data["stop_reason"], before subtype
    session_id: str | None
    data: dict[str, Any]  # the raw result message payload
```

若要區分失敗，請先檢查 `data["stop_reason"]`，接著檢查 `terminal_reason`，最後檢查 `subtype`。被拒絕的回應其 `stop_reason` 為 `"refusal"`，`subtype` 通常為 `"success"`；其 `terminal_reason` 無法將其區分出來，可能顯示為 `"completed"` 或 `"api_error"`。最終請求失敗時，`subtype` 為 `"success"`，原因則在 `terminal_reason` 中，例如 API 錯誤為 `"api_error"`。當執行達到您設定的限制（例如 `max_turns` 或 `max_budget_usd`）時，您會得到 `error_*` 子類型。

### `CLIJSONDecodeError`

當 JSON 解析失敗時引發。

```python theme={null}
class CLIJSONDecodeError(ClaudeSDKError):
    def __init__(self, line: str, original_error: Exception):
        """
        Args:
            line: The line that failed to parse
            original_error: The original JSON decode exception
        """
        self.line = line
        self.original_error = original_error
```

## Hook 類型

如需使用 hooks 的綜合指南，包括範例和常見模式，見 [Hooks 指南](https://code.claude.com/docs/zh-TW/agent-sdk/hooks.md)。

### `HookEvent`

支援的 hook 事件類型。

```python theme={null}
HookEvent = Literal[
    "PreToolUse",  # Called before tool execution
    "PostToolUse",  # Called after tool execution
    "PostToolUseFailure",  # Called when a tool execution fails
    "UserPromptSubmit",  # Called when a prompt is submitted
    "Stop",  # Called when stopping execution
    "SubagentStop",  # Called when a subagent stops
    "PreCompact",  # Called before message compaction
    "Notification",  # Called for notification events
    "SubagentStart",  # Called when a subagent starts
    "PermissionRequest",  # Called when a permission decision is needed
]
```

> [!NOTE]
>
> TypeScript SDK 支援 Python 中尚未提供的其他 hook 事件。見 [hook 可用性表](https://code.claude.com/docs/zh-TW/agent-sdk/hooks.md#available-hooks)以了解各 SDK 的支援情況。

### `HookCallback`

hook 回呼函數的類型定義。

```python theme={null}
HookCallback = Callable[[HookInput, str | None, HookContext], Awaitable[HookJSONOutput]]
```

參數：

* `input`：強類型 hook 輸入，具有基於 `hook_event_name` 的判別聯合（請參閱 [`HookInput`](#hookinput)）
* `tool_use_id`：可選 tool 使用識別碼（用於 tool 相關 hooks）
* `context`：具有其他資訊的 hook 上下文

返回 [`HookJSONOutput`](#hookjsonoutput)。

### `HookContext`

傳遞給 hook 回呼的上下文資訊。

```python theme={null}
class HookContext(TypedDict):
    signal: Any | None  # Future: abort signal support
```

### `HookMatcher`

用於將 hooks 符合到特定事件或 tools 的配置。

```python theme={null}
@dataclass
class HookMatcher:
    matcher: str | None = (
        None  # Tool name or pattern to match (e.g., "Bash", "Write|Edit")
    )
    hooks: list[HookCallback] = field(
        default_factory=list
    )  # List of callbacks to execute
    timeout: float | None = (
        None  # Timeout in seconds. When omitted, the per-event default applies:
        # 600 for most events, 30 for UserPromptSubmit
    )
    on_failure: Literal["continue", "block"] | None = (
        None  # "block" blocks the action when a callback fails
    )
```

如需判斷 `on_failure` 涵蓋的範圍，請參閱[在回呼失敗時阻止動作](https://code.claude.com/docs/zh-TW/agent-sdk/hooks.md#block-the-action-when-a-callback-fails)。

### `HookInput`

所有 hook 輸入類型的聯合類型。實際類型取決於 `hook_event_name` 欄位。

```python theme={null}
HookInput = (
    PreToolUseHookInput
    | PostToolUseHookInput
    | PostToolUseFailureHookInput
    | UserPromptSubmitHookInput
    | StopHookInput
    | SubagentStopHookInput
    | PreCompactHookInput
    | NotificationHookInput
    | SubagentStartHookInput
    | PermissionRequestHookInput
)
```

### `BaseHookInput`

所有 hook 輸入類型中存在的基礎欄位。

```python theme={null}
class BaseHookInput(TypedDict):
    session_id: str
    transcript_path: str
    cwd: str
    permission_mode: NotRequired[str]
```

| 欄位 | 類型 | 描述 |
| :- | :- | :- |
| `session_id` | `str` | 目前 session 識別碼 |
| `transcript_path` | `str` | session 記錄檔案的路徑 |
| `cwd` | `str` | 目前工作目錄 |
| `permission_mode` | `str`（可選） | 目前權限模式 |

### `PreToolUseHookInput`

`PreToolUse` hook 事件的輸入資料。

```python theme={null}
class PreToolUseHookInput(BaseHookInput):
    hook_event_name: Literal["PreToolUse"]
    tool_name: str
    tool_input: dict[str, Any]
    tool_use_id: str
    agent_id: NotRequired[str]
    agent_type: NotRequired[str]
```

| 欄位 | 類型 | 描述 |
| :- | :- | :- |
| `hook_event_name` | `Literal["PreToolUse"]` | 始終為 "PreToolUse" |
| `tool_name` | `str` | 即將執行的 tool 名稱 |
| `tool_input` | `dict[str, Any]` | tool 的輸入參數 |
| `tool_use_id` | `str` | 此 tool 使用的唯一識別碼 |
| `agent_id` | `str`（可選） | 子代理識別碼，當 hook 在子代理內觸發時出現 |
| `agent_type` | `str`（可選） | 子代理類型，當 hook 在子代理內觸發時出現 |

### `PostToolUseHookInput`

`PostToolUse` hook 事件的輸入資料。

```python theme={null}
class PostToolUseHookInput(BaseHookInput):
    hook_event_name: Literal["PostToolUse"]
    tool_name: str
    tool_input: dict[str, Any]
    tool_response: Any
    tool_use_id: str
    agent_id: NotRequired[str]
    agent_type: NotRequired[str]
```

| 欄位 | 類型 | 描述 |
| :- | :- | :- |
| `hook_event_name` | `Literal["PostToolUse"]` | 始終為 "PostToolUse" |
| `tool_name` | `str` | 已執行的 tool 名稱 |
| `tool_input` | `dict[str, Any]` | 使用的輸入參數 |
| `tool_response` | `Any` | tool 執行的回應 |
| `tool_use_id` | `str` | 此 tool 使用的唯一識別碼 |
| `agent_id` | `str`（可選） | 子代理識別碼，當 hook 在子代理內觸發時出現 |
| `agent_type` | `str`（可選） | 子代理類型，當 hook 在子代理內觸發時出現 |

### `PostToolUseFailureHookInput`

`PostToolUseFailure` hook 事件的輸入資料。在 tool 執行失敗時呼叫。

```python theme={null}
class PostToolUseFailureHookInput(BaseHookInput):
    hook_event_name: Literal["PostToolUseFailure"]
    tool_name: str
    tool_input: dict[str, Any]
    tool_use_id: str
    error: str
    is_interrupt: NotRequired[bool]
    agent_id: NotRequired[str]
    agent_type: NotRequired[str]
```

| 欄位 | 類型 | 描述 |
| :- | :- | :- |
| `hook_event_name` | `Literal["PostToolUseFailure"]` | 始終為 "PostToolUseFailure" |
| `tool_name` | `str` | 失敗的 tool 名稱 |
| `tool_input` | `dict[str, Any]` | 使用的輸入參數 |
| `tool_use_id` | `str` | 此 tool 使用的唯一識別碼 |
| `error` | `str` | 失敗執行的錯誤消息 |
| `is_interrupt` | `bool`（可選） | 當失敗作為中止而非 tool 報告的錯誤到達 Claude Code 時為真。使用 `interrupt()` 取消執行中的 tool 不會觸發此 hook；tool 結果會改為攜帶中斷消息 |
| `agent_id` | `str`（可選） | 子代理識別碼，當 hook 在子代理內觸發時出現 |
| `agent_type` | `str`（可選） | 子代理類型，當 hook 在子代理內觸發時出現 |

### `UserPromptSubmitHookInput`

`UserPromptSubmit` hook 事件的輸入資料。

```python theme={null}
class UserPromptSubmitHookInput(BaseHookInput):
    hook_event_name: Literal["UserPromptSubmit"]
    prompt: str
```

| 欄位 | 類型 | 描述 |
| :- | :- | :- |
| `hook_event_name` | `Literal["UserPromptSubmit"]` | 始終為 "UserPromptSubmit" |
| `prompt` | `str` | 提交的提示詞 |

### `StopHookInput`

`Stop` hook 事件的輸入資料。

```python theme={null}
class StopHookInput(BaseHookInput):
    hook_event_name: Literal["Stop"]
    stop_hook_active: bool
```

| 欄位 | 類型 | 描述 |
| :- | :- | :- |
| `hook_event_name` | `Literal["Stop"]` | 始終為 "Stop" |
| `stop_hook_active` | `bool` | stop hook 是否活躍 |

### `SubagentStopHookInput`

`SubagentStop` hook 事件的輸入資料。

```python theme={null}
class SubagentStopHookInput(BaseHookInput):
    hook_event_name: Literal["SubagentStop"]
    stop_hook_active: bool
    agent_id: str
    agent_transcript_path: str
    agent_type: str
```

| 欄位 | 類型 | 描述 |
| :- | :- | :- |
| `hook_event_name` | `Literal["SubagentStop"]` | 始終為 "SubagentStop" |
| `stop_hook_active` | `bool` | stop hook 是否活躍 |
| `agent_id` | `str` | 子代理的唯一識別碼 |
| `agent_transcript_path` | `str` | 子代理記錄檔案的路徑 |
| `agent_type` | `str` | 子代理的類型 |

### `PreCompactHookInput`

`PreCompact` hook 事件的輸入資料。

```python theme={null}
class PreCompactHookInput(BaseHookInput):
    hook_event_name: Literal["PreCompact"]
    trigger: Literal["manual", "auto"]
    custom_instructions: str | None
```

| 欄位 | 類型 | 描述 |
| :- | :- | :- |
| `hook_event_name` | `Literal["PreCompact"]` | 始終為 "PreCompact" |
| `trigger` | `Literal["manual", "auto"]` | 觸發壓縮的原因 |
| `custom_instructions` | `str \| None` | 壓縮的自訂指示 |

### `NotificationHookInput`

`Notification` hook 事件的輸入資料。

```python theme={null}
class NotificationHookInput(BaseHookInput):
    hook_event_name: Literal["Notification"]
    message: str
    title: NotRequired[str]
    notification_type: str
```

| 欄位 | 類型 | 描述 |
| :- | :- | :- |
| `hook_event_name` | `Literal["Notification"]` | 始終為 "Notification" |
| `message` | `str` | 通知消息內容 |
| `title` | `str`（可選） | 通知標題 |
| `notification_type` | `str` | 通知類型 |

### `SubagentStartHookInput`

`SubagentStart` hook 事件的輸入資料。

```python theme={null}
class SubagentStartHookInput(BaseHookInput):
    hook_event_name: Literal["SubagentStart"]
    agent_id: str
    agent_type: str
```

| 欄位 | 類型 | 描述 |
| :- | :- | :- |
| `hook_event_name` | `Literal["SubagentStart"]` | 始終為 "SubagentStart" |
| `agent_id` | `str` | 子代理的唯一識別碼 |
| `agent_type` | `str` | 子代理的類型 |

### `PermissionRequestHookInput`

`PermissionRequest` hook 事件的輸入資料。允許 hooks 以程式設計方式處理權限決策。

```python theme={null}
class PermissionRequestHookInput(BaseHookInput):
    hook_event_name: Literal["PermissionRequest"]
    tool_name: str
    tool_input: dict[str, Any]
    permission_suggestions: NotRequired[list[Any]]
    agent_id: NotRequired[str]
    agent_type: NotRequired[str]
```

| 欄位 | 類型 | 描述 |
| :- | :- | :- |
| `hook_event_name` | `Literal["PermissionRequest"]` | 始終為 "PermissionRequest" |
| `tool_name` | `str` | 請求權限的 tool 名稱 |
| `tool_input` | `dict[str, Any]` | tool 的輸入參數 |
| `permission_suggestions` | `list[Any]`（可選） | 來自 CLI 的建議權限更新 |
| `agent_id` | `str`（可選） | 子代理識別碼，當 hook 在子代理內觸發時出現 |
| `agent_type` | `str`（可選） | 子代理類型，當 hook 在子代理內觸發時出現 |

### `HookJSONOutput`

hook 回呼返回值的聯合類型。

```python theme={null}
HookJSONOutput = AsyncHookJSONOutput | SyncHookJSONOutput
```

#### `SyncHookJSONOutput`

具有控制和決策欄位的同步 hook 輸出。

```python theme={null}
class SyncHookJSONOutput(TypedDict):
    # Control fields
    continue_: NotRequired[bool]  # Whether to proceed (default: True)
    suppressOutput: NotRequired[bool]  # Hide stdout from transcript
    stopReason: NotRequired[str]  # Message when continue is False

    # Decision fields
    decision: NotRequired[Literal["block"]]
    systemMessage: NotRequired[str]  # Warning message for user
    reason: NotRequired[str]  # Feedback for Claude

    # Hook-specific output
    hookSpecificOutput: NotRequired[HookSpecificOutput]
```

> [!NOTE]
>
> 在 Python 程式碼中使用 `continue_`（帶下劃線）。發送到 CLI 時會自動轉換為 `continue`。

#### `HookSpecificOutput`

事件特定 `TypedDict` 輸出類型的判別聯合。`hookEventName` 欄位決定哪些欄位有效。如需每個 hook 事件的可用欄位的完整詳情，見 [使用 hook 控制執行](https://code.claude.com/docs/zh-TW/agent-sdk/hooks.md#outputs)。

```python theme={null}
class PreToolUseHookSpecificOutput(TypedDict):
    hookEventName: Literal["PreToolUse"]
    permissionDecision: NotRequired[Literal["allow", "deny", "ask", "defer"]]
    permissionDecisionReason: NotRequired[str]
    updatedInput: NotRequired[dict[str, Any]]
    additionalContext: NotRequired[str]


class PostToolUseHookSpecificOutput(TypedDict):
    hookEventName: Literal["PostToolUse"]
    additionalContext: NotRequired[str]
    updatedToolOutput: NotRequired[Any]
    updatedMCPToolOutput: NotRequired[Any]  # MCP tools only. Prefer updatedToolOutput, which works for all tools


class PostToolUseFailureHookSpecificOutput(TypedDict):
    hookEventName: Literal["PostToolUseFailure"]
    additionalContext: NotRequired[str]


class UserPromptSubmitHookSpecificOutput(TypedDict):
    hookEventName: Literal["UserPromptSubmit"]
    additionalContext: NotRequired[str]


class NotificationHookSpecificOutput(TypedDict):
    hookEventName: Literal["Notification"]
    additionalContext: NotRequired[str]


class SubagentStartHookSpecificOutput(TypedDict):
    hookEventName: Literal["SubagentStart"]
    additionalContext: NotRequired[str]


class PermissionRequestHookSpecificOutput(TypedDict):
    hookEventName: Literal["PermissionRequest"]
    decision: dict[str, Any]


HookSpecificOutput = (
    PreToolUseHookSpecificOutput
    | PostToolUseHookSpecificOutput
    | PostToolUseFailureHookSpecificOutput
    | UserPromptSubmitHookSpecificOutput
    | NotificationHookSpecificOutput
    | SubagentStartHookSpecificOutput
    | PermissionRequestHookSpecificOutput
)
```

#### `AsyncHookJSONOutput`

延遲 hook 執行的非同步 hook 輸出。

```python theme={null}
class AsyncHookJSONOutput(TypedDict):
    async_: Literal[True]  # Set to True to defer execution
    asyncTimeout: NotRequired[int]  # Timeout in milliseconds
```

> [!NOTE]
>
> 在 Python 程式碼中使用 `async_`（帶下劃線）。發送到 CLI 時會自動轉換為 `async`。

### Hook 使用範例

此範例註冊兩個 hooks：一個阻止危險的 bash 命令（如 `rm -rf /`），另一個記錄所有 tool 使用情況以進行審計。安全 hook 僅在 Bash 命令上執行（透過 `matcher`），而記錄 hook 在所有 tools 上執行。

```python theme={null}
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, HookMatcher, HookContext
from typing import Any


async def validate_bash_command(
    input_data: dict[str, Any], tool_use_id: str | None, context: HookContext
) -> dict[str, Any]:
    """Validate and potentially block dangerous bash commands."""
    if input_data["tool_name"] == "Bash":
        command = input_data["tool_input"].get("command", "")
        if "rm -rf /" in command:
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "Dangerous command blocked",
                }
            }
    return {}


async def log_tool_use(
    input_data: dict[str, Any], tool_use_id: str | None, context: HookContext
) -> dict[str, Any]:
    """Log all tool usage for auditing."""
    print(f"Tool used: {input_data.get('tool_name')}")
    return {}


options = ClaudeAgentOptions(
    hooks={
        "PreToolUse": [
            HookMatcher(
                matcher="Bash", hooks=[validate_bash_command], timeout=120
            ),  # 2 min for validation
            HookMatcher(
                hooks=[log_tool_use]
            ),  # Applies to all tools (per-event default timeout)
        ],
        "PostToolUse": [HookMatcher(hooks=[log_tool_use])],
    }
)

async def main():
    async for message in query(prompt="Analyze this codebase", options=options):
        print(message)


asyncio.run(main())
```

## 工具輸入/輸出類型

所有內建 Claude Code 工具的輸入/輸出結構描述文件。雖然 Python SDK 不會將這些匯出為類型，但它們代表訊息中工具輸入和輸出的結構。

每個顯示的輸出是您從該工具的 [`UserMessage.tool_use_result`](#usermessage) 讀取的值。鍵名完全按照 Claude Code 發出的方式出現。標註為 `| None` 且帶有「出現時」或「選擇性」註釋的鍵在不適用時會被省略。

### Agent

**工具名稱：** `Agent`。當此工具可供工作階段使用時，先前的名稱 `Task` 仍被接受為別名。

初始化 [`SystemMessage`](#systemmessage) 中的 `tools` 列表為了向後相容性將此工具報告為 `Task`。

**輸入：**

```python theme={null}
{
    "description": str,  # 任務的簡短描述（3-5 個單詞）
    "prompt": str,  # agent 要執行的任務
    "subagent_type": str | None,  # 要使用的專門 agent 類型
    "model": "sonnet" | "opus" | "haiku" | "fable" | None,  # 此 agent 的模型覆寫
    "effort": "low" | "medium" | "high" | "xhigh" | "max" | None,  # 此 agent 的推理投入程度
    "run_in_background": bool | None,  # 省略時的預設：您的主 agent 的呼叫會在背景執行新 agent，而 subagent 的呼叫會等待它
    "name": str | None,  # 生成的 agent 的名稱
    "team_name": str | None,  # 已棄用；被忽略
    "mode": "acceptEdits" | "auto" | "bypassPermissions" | "default" | "dontAsk" | "plan" | None,  # 已棄用；被忽略。subagent 繼承規則決定 subagent 的權限模式
    "isolation": "worktree" | "remote" | None,  # agent 變更的隔離模式
}
```

啟動新 agent 以自主處理複雜的多步驟任務。

當 Claude 在 `Agent` 呼叫中省略 `run_in_background` 時，預設情況下您的主 agent 不會等待新 agent，而 subagent 會等待：

* **從您的主 agent**：新 agent 在背景執行，結果具有 `status: "async_launched"`。若要讓您的主 agent 改為等待新 agent，請參閱 [選擇 Claude 是否等待 subagent](https://code.claude.com/docs/zh-TW/agent-sdk/subagents.md#choose-whether-claude-waits-for-subagents)。
* **從您的其中一個 subagent**：呼叫的 subagent [會等待新 agent](https://code.claude.com/docs/zh-TW/sub-agents.md#let-subagents-spawn-their-own-subagents)。當新 agent 的定義將 [`background`](#agentdefinition) 設定為 `True`，或當您將 `CLAUDE_CODE_FORK_SUBAGENT` 設定為 `0` 以[關閉分叉模式](https://code.claude.com/docs/zh-TW/sub-agents.md#turn-fork-mode-on-or-off)時，新 agent 改為在背景執行。

在 Python SDK v0.2.169 之前，由您的 subagent 啟動的 agent 預設也會在背景執行。該版本是第一個內含 Claude Code v2.1.302 或更新版本的版本。

**輸出（狀態：`"completed"`）：**

```python theme={null}
{
    "status": "completed",
    "agentId": str,  # 執行的 agent 的 ID
    "agentType": str | None,  # 處理任務的 subagent 類型
    "content": [  # 結果內容區塊
        {
            "type": "text",
            "text": str,
            "citations": list | None,
        }
    ],
    "resolvedModel": str | None,  # subagent 啟動時使用的模型
    "modelsUsed": list[str] | None,  # 依序使用的模型，連續重複已摺疊
    "totalToolUseCount": int,  # agent 進行的工具呼叫次數
    "totalDurationMs": int,  # 執行持續時間（毫秒）
    "totalTokens": int,  # 最終 API 請求的 token 計數，不是整個執行的計數
    "usage": {  # token 使用統計
        "input_tokens": int,
        "output_tokens": int,
        "cache_creation_input_tokens": int | None,
        "cache_read_input_tokens": int | None,
        "server_tool_use": {"web_search_requests": int, "web_fetch_requests": int} | None,
        "service_tier": str | None,
        "cache_creation": {"ephemeral_1h_input_tokens": int, "ephemeral_5m_input_tokens": int} | None,
        "inference_geo": str | None,
        "speed": str | None,
        "iterations": Any | None,
        "output_tokens_details": {"thinking_tokens": int | None} | None,
        "fallback_credit": Any | None,
    },
    "toolStats": {  # 執行的彙總工具活動
        "readCount": int,
        "searchCount": int,
        "bashCount": int,
        "editFileCount": int,
        "linesAdded": int,
        "linesRemoved": int,
        "otherToolCount": int,
        "frameCount": int | None,
    } | None,
    "prompt": str,  # agent 執行的提示詞
    "worktreePath": str | None,  # 當 Claude Code 保留 subagent 的 worktree 時出現
    "worktreeBranch": str | None,  # 當 Claude Code 使用 git 建立該 worktree 時出現
}
```

**輸出（狀態：`"async_launched"`）：**

```python theme={null}
{
    "status": "async_launched",
    "isAsync": bool | None,  # 在背景啟動時為 True
    "agentId": str,  # 啟動的 agent 的 ID
    "description": str,  # 任務描述
    "resolvedModel": str | None,  # 在背景轉換時使用的模型
    "modelsUsed": list[str] | None,  # 背景轉換前使用的模型，依序排列，連續重複已摺疊
    "prompt": str,  # agent 執行的提示詞
    "outputFile": str,  # agent 輸出寫入的檔案路徑
    "canReadOutputFile": bool | None,  # 是否可以直接讀取輸出檔案
}
```

**輸出（狀態：`"remote_launched"`）：**

```python theme={null}
{
    "status": "remote_launched",
    "taskId": str,  # 分派任務的 ID
    "sessionUrl": str,  # 雲端工作階段的連結
    "description": str,  # 任務描述
    "prompt": str,  # agent 執行的提示詞
    "outputFile": str,  # agent 輸出寫入的檔案路徑
}
```

返回來自 subagent 的結果。輸出根據 `status` 欄位進行區分：`"completed"` 用於已完成的任務，`"async_launched"` 用於背景任務，`"remote_launched"` 用於 Claude Code 分派到雲端工作階段的任務，其中 `sessionUrl` 連結到該工作階段，`taskId` 識別它。如果 Claude Code [保留了 subagent 的隔離 worktree](https://code.claude.com/docs/zh-TW/worktrees.md#isolate-subagents-with-worktrees)，`completed` 變體上的 `worktreePath` 是找到它的位置，`worktreeBranch` 是當 Claude Code 使用 git 建立 worktree 時的分支。

在 `completed` 變體上，`resolvedModel` 命名 subagent 啟動時使用的模型，當套用 [`availableModels`](https://code.claude.com/docs/zh-TW/model-config#restrict-model-selection) 或其他覆寫時，可能與請求的 `model` 輸入不同。此欄位需要 Claude Code v2.1.174 或更新版本。在 `async_launched` 變體上，`resolvedModel` 命名 agent 移至背景時使用的模型，因此在背景轉換前發生的交換會反映在那裡。兩個變體上的 `modelsUsed` 欄位依序列出使用的模型，連續重複已摺疊；只有在執行中途交換模型時才會設定。`modelsUsed` 和背景轉換時的 `resolvedModel` 行為需要 Claude Code v2.1.212 或更新版本。

Claude Code 從 subagent 的最終 API 請求填充 `usage` 和 `totalTokens`，而不是從整個執行。當存在時，`usage` 中 `output_tokens_details` 下的 `thinking_tokens` 是該請求的輸出 token 中屬於思考 token 的數量。`output_tokens_details` 鍵需要 Python SDK v0.2.136 或更新版本，其中包含 Claude Code v2.1.228。`fallback_credit` 鍵需要 Python SDK v0.2.162 或更新版本，其中包含 Claude Code v2.1.285。

### AskUserQuestion

**工具名稱：** `AskUserQuestion`

在執行期間詢問使用者澄清問題。有關使用詳情，請參閱 [處理核准和使用者輸入](https://code.claude.com/docs/zh-TW/agent-sdk/user-input.md#handle-clarifying-questions)。

**輸入：**

```python theme={null}
{
    "questions": [  # 要詢問使用者的問題（1-4 個問題）
        {
            "question": str,  # 要詢問使用者的完整問題
            "header": str,  # 顯示為晶片/標籤的非常簡短標籤（最多 12 個字元）
            "options": [  # 可用的選擇（2-4 個選項）
                {
                    "label": str,  # 此選項的顯示文字（1-5 個單詞）
                    "description": str,  # 此選項含義的說明
                    "preview": str | None,  # 當選項獲得焦點時呈現的預覽內容
                }
            ],
            "multiSelect": bool,  # 設定為 true 以允許多個選擇
        }
    ],
    "answers": dict[str, str] | None,
    # 由權限系統填充的使用者答案。多選答案
    # 是所選標籤的逗號連接字串；輸入時接受
    # 標籤列表並強制轉換為該形式
    "annotations": dict[str, dict] | None,
    # 來自使用者的每個問題註釋，以問題文字為鍵。
    # 每個值可以攜帶「preview」（所選選項的預覽
    # 內容）和「notes」（關於選擇的自由文字註釋）
    "metadata": dict | None,  # 分析中繼資料，例如 {"source": "remember"}；不向使用者顯示
}
```

**輸出：**

```python theme={null}
{
    "questions": [  # 被詢問的問題
        {
            "question": str,
            "header": str,
            "options": [{"label": str, "description": str, "preview": str | None}],
            "multiSelect": bool,
        }
    ],
    "answers": dict[str, str],  # 將問題文字對應到答案字串
    # 多選答案以逗號分隔
    "response": str | None,
    # 使用者輸入的自由形式回覆，而不是回答問題；當設定時，
    # Claude 收到「使用者回應：...」代替答案列表
    "annotations": dict[str, dict] | None,  # 來自使用者選擇的每個問題「preview」和「notes」
    "afkTimeoutMs": int | None,  # 在對話在使用者不活動此許多毫秒後自動解決時設定；使用者回答時不存在
}
```

### Bash

**工具名稱：** `Bash`

如需了解設定前景上限的內容，請參閱 [逾時和輸出限制](https://code.claude.com/docs/zh-TW/tools-reference.md#timeout-and-output-limits)。如需了解背景時間限制，請參閱 [背景命令的時間限制](https://code.claude.com/docs/zh-TW/tools-reference.md#time-limit-for-background-commands)。

**輸入：**

```python theme={null}
{
    "command": str,  # 要執行的命令
    "timeout": int | None,  # 毫秒。前景：預設上限為 600000，更高的值被限制。使用 run_in_background（Claude Code v2.1.285 或更新版本）：背景時間限制，省略時為 1800000，上限為 7200000，除非提高
    "description": str | None,  # 清晰、簡潔的描述（5-10 個單詞）
    "run_in_background": bool | None,  # 設定為 true 以在背景執行
}
```

**輸出：**

```python theme={null}
{
    "stdout": str,  # 命令的輸出；stdout 和 stderr 交錯合併到此一個流中
    "stderr": str,  # 工具本身新增的通知，不是命令的 stderr
    "interrupted": bool,  # 命令是否被中斷
    "isImage": bool | None,  # stdout 是否包含影像資料
    "backgroundTaskId": str | None,  # 如果命令在背景執行，背景任務的 ID
}
```

### Monitor

**工具名稱：** `Monitor`

執行背景來源並將每個事件傳遞給 Claude，以便它可以做出反應而無需輪詢：`command` 執行指令碼並每個 stdout 行發出一個事件，`ws` 開啟 WebSocket 並每個文字框架發出一個事件。提供 `command` 或 `ws` 中的恰好一個。

當 Monitor 執行命令時，它遵循與 Bash 相同的權限規則；WebSocket 監視會單獨提示核准。`ws` 來源需要 Claude Code v2.1.195 或更新版本。有關行為和提供者可用性，請參閱 [Monitor 工具參考](https://code.claude.com/docs/zh-TW/tools-reference.md#monitor-tool)。

**輸入：**

```python theme={null}
{
    "command": str | None,  # Shell 指令碼；每個 stdout 行是一個事件，退出結束監視
    "ws": dict | None,  # WebSocket 來源：{"url": str, "protocols": list[str] | None}；每個文字框架是一個事件
    "description": str,  # 通知中顯示的簡短描述
    "timeout_ms": int | None,  # 截止時間（毫秒）（預設 300000，最大 3600000；有效截止時間最多 1800000）
}
```

**輸出：**

```python theme={null}
{
    "taskId": str,  # 背景監視任務的 ID
    "timeoutMs": int,  # 監視的有效截止時間（毫秒）
    "persistent": bool | None,  # False：每個監視都有截止時間
}
```

### Edit

**工具名稱：** `Edit`

**輸入：**

```python theme={null}
{
    "file_path": str,  # 要修改的檔案的絕對路徑
    "old_string": str,  # 要替換的文字
    "new_string": str,  # 用來替換它的文字
    "replace_all": bool | None,  # 替換所有出現次數（預設 False）
}
```

**輸出：**

```python theme={null}
{
    "filePath": str,  # 被編輯的檔案
    "oldString": str,  # 被替換的文字
    "newString": str,  # 替換它的文字
    "originalFile": str | None,  # 編輯前的檔案內容
    "structuredPatch": [  # 變更的 Diff 區塊
        {
            "oldStart": int,
            "oldLines": int,
            "newStart": int,
            "newLines": int,
            "lines": list[str],
        }
    ],
    "userModified": bool,  # 使用者是否在接受前變更了建議的編輯
    "replaceAll": bool,  # 是否替換了所有出現次數
    "gitDiff": {  # 檔案的選擇性 git diff 摘要
        "filename": str,
        "status": "modified" | "added",
        "additions": int,
        "deletions": int,
        "changes": int,
        "patch": str,
        "repository": str | None,  # 可用時的 GitHub owner/repo
    } | None,
}
```

### Read

**工具名稱：** `Read`

**輸入：**

```python theme={null}
{
    "file_path": str,  # 要讀取的檔案的絕對路徑
    "offset": int | None,  # 開始讀取的行號
    "limit": int | None,  # 要讀取的行數
}
```

輸出根據 Claude 讀取的內容採用以下形式之一。檢查 `type` 鍵以區分它們。

**輸出（type: `"text"`）：**

```python theme={null}
{
    "type": "text",
    "file": {
        "filePath": str,  # 被讀取的檔案
        "content": str,  # 返回的內容
        "numLines": int,  # 返回內容中的行數
        "startLine": int,  # 內容開始的行號
        "totalLines": int,  # 檔案中的總行數
        "truncatedByTokenCap": bool | None,  # 當整個檔案讀取超過 token 上限且內容是第一頁時出現且為 True
    },
}
```

**輸出（type: `"image"`）：**

```python theme={null}
{
    "type": "image",
    "file": {
        "base64": str,  # Base64 編碼的影像資料
        "type": "image/jpeg" | "image/png" | "image/gif" | "image/webp",  # 影像 MIME 類型
        "originalSize": int,  # 原始檔案大小（位元組）
        "dimensions": {  # 座標對應的選擇性大小資訊
            "originalWidth": int | None,  # 選擇性；原始寬度（像素）
            "originalHeight": int | None,  # 選擇性；原始高度（像素）
            "displayWidth": int | None,  # 選擇性；調整大小後的寬度
            "displayHeight": int | None,  # 選擇性；調整大小後的高度
        } | None,
    },
}
```

**輸出（type: `"notebook"`）：**

```python theme={null}
{
    "type": "notebook",
    "file": {
        "filePath": str,  # 被讀取的筆記本
        "cells": list,  # 筆記本儲存格
    },
}
```

**輸出（type: `"pdf"`）：**

```python theme={null}
{
    "type": "pdf",
    "file": {
        "filePath": str,  # 被讀取的 PDF
        "base64": str,  # Base64 編碼的 PDF 資料
        "originalSize": int,  # 檔案大小（位元組）
    },
}
```

**輸出（type: `"parts"`）：**

```python theme={null}
{
    "type": "parts",
    "file": {
        "filePath": str,  # 被讀取的 PDF
        "originalSize": int,  # 檔案大小（位元組）
        "count": int,  # 提取為影像的頁數
        "outputDir": str,  # 包含提取的頁面影像的目錄
    },
    "firstPage": int | None,  # 選擇性；第一個提取頁面的文件頁碼
}
```

**輸出（type: `"file_unchanged"`）：**

```python theme={null}
{
    "type": "file_unchanged",  # 檔案自 Claude 在此工作階段中上次讀取以來未變更，因此內容不會重複
    "file": {
        "filePath": str,
    },
    "source": "seeded" | None,  # 當較早的副本來自在啟動時載入的 CLAUDE.md 或記憶檔案而不是 Read 呼叫時出現
}
```

### Write

**工具名稱：** `Write`

**輸入：**

```python theme={null}
{
    "file_path": str,  # 要寫入的檔案的絕對路徑
    "content": str,  # 要寫入檔案的內容
}
```

**輸出：**

```python theme={null}
{
    "type": "create" | "update",  # 寫入是建立新檔案還是覆寫現有檔案
    "filePath": str,  # 被寫入的檔案
    "content": str,  # 被寫入的內容
    "structuredPatch": [  # Diff 區塊；新檔案、未變更或 Claude Code 跳過 diff 時為空
        {
            "oldStart": int,
            "oldLines": int,
            "newStart": int,
            "newLines": int,
            "lines": list[str],
        }
    ],
    "originalFile": str | None,  # 先前的內容；新檔案時為 None 或先前內容太大而無法包含時
    "gitDiff": {  # 檔案的選擇性 git diff 摘要
        "filename": str,
        "status": "modified" | "added",
        "additions": int,
        "deletions": int,
        "changes": int,
        "patch": str,
        "repository": str | None,  # 可用時的 GitHub owner/repo
    } | None,
    "userModified": bool | None,  # 選擇性；使用者是否在接受前編輯了建議的內容
}
```

### Glob

**工具名稱：** `Glob`

**輸入：**

```python theme={null}
{
    "pattern": str,  # 要對檔案進行比對的 glob 模式
    "path": str | None,  # 要搜尋的目錄（預設為 cwd）
}
```

**輸出：**

```python theme={null}
{
    "durationMs": int,  # 執行搜尋所花的時間（毫秒）
    "numFiles": int,  # 返回的路徑數，任何截斷後
    "filenames": list[str],  # 相符的檔案路徑
    "truncated": bool,  # 結果是否在 100 檔案限制處被截斷
    "totalMatches": int | None,  # 選擇性截斷前相符檔案的總數；當 countIsComplete 為 False 時為下限
    "countIsComplete": bool | None,  # 選擇性；totalMatches 是否精確
}
```

`totalMatches` 和 `countIsComplete` 需要 Claude Code v2.1.191 或更新版本。

### Grep

**工具名稱：** `Grep`

**輸入：**

```python theme={null}
{
    "pattern": str,  # 正規表達式模式
    "path": str | None,  # 要搜尋的檔案或目錄
    "glob": str | None,  # 用於篩選檔案的 glob 模式
    "type": str | None,  # 要搜尋的檔案類型
    "output_mode": str | None,  # 「content」、「files_with_matches」或「count」
    "-i": bool | None,  # 不區分大小寫搜尋
    "-n": bool | None,  # 顯示行號
    "-B": int | None,  # 每個相符項目前顯示的行數
    "-A": int | None,  # 每個相符項目後顯示的行數
    "-C": int | None,  # 每個相符項目前後顯示的行數
    "context": int | None,  # 每個相符項目前後顯示的行數；-C 是別名
    "-o": bool | None,  # 僅列印每行的相符部分
    "head_limit": int | None,  # 將輸出限制為前 N 行/項目
    "offset": int | None,  # 在套用 head_limit 前跳過前 N 行/項目
    "multiline": bool | None,  # 啟用多行模式
}
```

**輸出：**

```python theme={null}
{
    "mode": "content" | "files_with_matches" | "count" | None,  # 使用的輸出模式
    "numFiles": int,  # 結果中的檔案數；內容模式中始終為 0
    "filenames": list[str],  # files_with_matches 模式中的相符檔案；其他模式中為空
    "content": str | None,  # 內容模式中的相符行，或計數模式中的每個檔案計數
    "numLines": int | None,  # 內容中的行數，內容模式中出現
    "numMatches": int | None,  # 總相符計數，計數模式中出現
    "totalFiles": int | None,  # 選擇性 head_limit 和 offset 前的總數，files_with_matches 模式中
    "totalLines": int | None,  # 選擇性 head_limit 和 offset 前的總數，內容模式中
    "appliedLimit": int | None,  # 當 head_limit 截斷結果時出現
    "appliedOffset": int | None,  # 當套用 offset 時出現
}
```

Grep 在每個輸出模式中返回此 dict 形狀。哪些選擇性鍵出現取決於 `output_mode`。

`totalFiles` 需要 Claude Code v2.1.208 或更新版本。`totalLines` 需要 Claude Code v2.1.210 或更新版本。

### NotebookEdit

**工具名稱：** `NotebookEdit`

**輸入：**

```python theme={null}
{
    "notebook_path": str,  # Jupyter 筆記本的絕對路徑
    "cell_id": str | None,  # 要編輯的儲存格的 ID
    "new_source": str,  # 儲存格的新來源
    "cell_type": "code" | "markdown" | None,  # 儲存格的類型
    "edit_mode": "replace" | "insert" | "delete" | None,  # 編輯操作類型
}
```

**輸出：**

```python theme={null}
{
    "new_source": str,  # 寫入儲存格的來源
    "old_source": str | None,  # 先前的儲存格來源，替換和刪除時出現
    "cell_id": str | None,  # 編輯的儲存格的 ID，可用時
    "cell_type": "code" | "markdown",  # 儲存格類型
    "language": str,  # 筆記本的程式設計語言
    "edit_mode": str,  # 使用的編輯模式
    "error": str | None,  # 操作失敗時的錯誤訊息
    "notebook_path": str,  # 筆記本檔案
    "original_file": str,  # 編輯前的筆記本內容
    "updated_file": str,  # 編輯後的筆記本內容
}
```

### WebFetch

**工具名稱：** `WebFetch`

**輸入：**

```python theme={null}
{
    "url": str,  # 要從中擷取內容的 URL
    "prompt": str,  # 要在擷取的內容上執行的提示詞
    "offset": int | None,  # 從頁面開頭略過的字元數。需要 Python Agent SDK 0.2.164 或更新版本
}
```

**輸出：**

```python theme={null}
{
    "bytes": int,  # 擷取內容的大小（位元組）
    "code": int,  # HTTP 回應代碼
    "codeText": str,  # HTTP 回應代碼文字
    "result": str,  # 透過將提示詞套用到內容而得到的處理結果
    "durationMs": int,  # 擷取和處理內容的時間（毫秒）
    "url": str,  # 被擷取的 URL
}
```

### WebSearch

**工具名稱：** `WebSearch`

**輸入：**

```python theme={null}
{
    "query": str,  # 要使用的搜尋查詢
    "allowed_domains": list[str] | None,  # 僅包含來自這些網域的結果
    "blocked_domains": list[str] | None,  # 永遠不包含來自這些網域的結果
}
```

**輸出：**

```python theme={null}
{
    "query": str,  # 搜尋查詢
    "results": list[str | {"tool_use_id": str, "content": list[{"title": str, "url": str}]}],
    "durationSeconds": float,  # 搜尋持續時間（秒）
}
```

### TodoWrite

**工具名稱：** `TodoWrite`

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
>
> 請參閱 [模型可用性](https://code.claude.com/docs/zh-TW/agent-sdk/todo-tracking.md#model-availability) 以選擇加入。

**輸入：**

```python theme={null}
{
    "todos": [
        {
            "content": str,  # 任務描述
            "status": "pending" | "in_progress" | "completed",  # 任務狀態
            "activeForm": str,  # 描述的主動形式
        }
    ]
}
```

**輸出：**

```python theme={null}
{
    "oldTodos": [  # 更新前的待辦事項列表
        {
            "content": str,
            "status": "pending" | "in_progress" | "completed",
            "activeForm": str,
        }
    ],
    "newTodos": [  # 更新後的待辦事項列表
        {
            "content": str,
            "status": "pending" | "in_progress" | "completed",
            "activeForm": str,
        }
    ],
}
```

### TaskCreate

**工具名稱：** `TaskCreate`

**輸入：**

```python theme={null}
{
    "subject": str,  # 簡短的任務標題
    "description": str,  # 詳細的任務本文
    "activeForm": str | None,  # 進行中時顯示的現在式標籤
    "metadata": dict | None,  # 任意呼叫者中繼資料
}
```

**輸出：**

```python theme={null}
{
    "task": {"id": str, "subject": str},  # 建立的任務及指派的 ID
}
```

### TaskUpdate

**工具名稱：** `TaskUpdate`

**輸入：**

```python theme={null}
{
    "taskId": str,  # 要修補的任務的 ID
    "status": Literal["pending", "in_progress", "completed", "deleted"] | None,
    "subject": str | None,
    "description": str | None,
    "activeForm": str | None,
    "addBlocks": list[str] | None,  # 此任務現在阻止的任務 ID
    "addBlockedBy": list[str] | None,  # 現在阻止此任務的任務 ID
    "owner": str | None,
    "metadata": dict | None,
}
```

**輸出：**

```python theme={null}
{
    "success": bool,
    "taskId": str,
    "updatedFields": list[str],  # 變更的欄位名稱
    "error": str | None,
    "statusChange": {"from": str, "to": str} | None,
}
```

### TaskGet

**工具名稱：** `TaskGet`

**輸入：**

```python theme={null}
{
    "taskId": str,  # 要讀取的任務的 ID
}
```

**輸出：**

```python theme={null}
{
    "task": {
        "id": str,
        "subject": str,
        "description": str,
        "status": Literal["pending", "in_progress", "completed"],
        "blocks": list[str],
        "blockedBy": list[str],
    } | None,  # 當找不到 ID 時為 None
}
```

### TaskList

**工具名稱：** `TaskList`

**輸入：**

```python theme={null}
{}
```

**輸出：**

```python theme={null}
{
    "tasks": [
        {
            "id": str,
            "subject": str,
            "status": Literal["pending", "in_progress", "completed"],
            "owner": str | None,
            "blockedBy": list[str],
        }
    ],
}
```

### TaskOutput

在 Claude Code v2.1.277 中移除。先前從執行中或已完成的背景任務擷取輸出，`BashOutput` 被接受為別名；Claude 改為使用 `Read` 讀取背景任務的輸出檔案。

`disallowed_tools` 項目或仍命名任一名稱的拒絕規則被忽略而不發出警告。

### TaskStop

**工具名稱：** `TaskStop`。您仍可在權限規則、hook matcher，以及 `tools`、`allowed_tools` 和 `disallowed_tools` 選項中使用先前的名稱 `KillShell` 和 `KillBash`。

**輸入：**

```python theme={null}
{
    "task_id": str | None,  # 要停止的背景任務的 ID
    "shell_id": str | None,  # 已棄用：改用 task_id
}
```

**輸出：**

```python theme={null}
{
    "message": str,  # 關於操作的狀態訊息
    "task_id": str,  # 被停止的任務的 ID
    "task_type": str,  # 被停止的任務的類型
    "command": str | None,  # 被停止的任務的命令或描述
}
```

### ExitPlanMode

**工具名稱：** `ExitPlanMode`

**輸入：**

```python theme={null}
{
    "plan": str  # 要呈現給使用者核准的計畫
}
```

**輸出：**

```python theme={null}
{
    "plan": str | None,  # 呈現給使用者的計畫
    "isAgent": bool,  # 當 subagent 呼叫工具時為 True
    "filePath": str | None,  # 當計畫被儲存到檔案時出現
    "hasTaskTool": bool | None,  # 選擇性；Agent 工具是否在目前內容中可用
    "planWasEdited": bool | None,  # 當使用者在核准前編輯計畫時出現且為 True
    "awaitingLeaderApproval": bool | None,  # 當隊友將計畫傳送給團隊主管核准時出現且為 True
    "requestId": str | None,  # 該核准請求的選擇性 ID
}
```

### ListMcpResources

**工具名稱：** `ListMcpResourcesTool`

**輸入：**

```python theme={null}
{
    "server": str | None  # 選擇性伺服器名稱以按其篩選資源
}
```

結果是列表而不是 dict，因此 `tool_use_result` 為此工具保留 `list`。

**輸出：**

```python theme={null}
[  # 每個資源一個項目
    {
        "uri": str,  # 資源 URI
        "name": str,  # 資源名稱
        "mimeType": str | None,  # 選擇性 MIME 類型
        "description": str | None,  # 選擇性描述
        "server": str,  # 提供此資源的伺服器
    }
]
```

### ReadMcpResource

**工具名稱：** `ReadMcpResourceTool`

**輸入：**

```python theme={null}
{
    "server": str,  # MCP 伺服器名稱
    "uri": str,  # 要讀取的資源 URI
}
```

**輸出：**

```python theme={null}
{
    "contents": [
        {
            "uri": str,  # 資源 URI
            "mimeType": str | None,  # 選擇性 MIME 類型
            "text": str | None,  # 文字內容，或關於二進位內容的註釋
            "blobSavedTo": str | None,  # 當 Claude Code 將二進位內容儲存到磁碟時出現；儲存檔案的路徑
        }
    ],
    "error": str | None,  # 當伺服器無法讀取資源時出現
}
```

## 建立持續對話介面

以下範例保持一個 `ClaudeSDKClient` 在多個回合中保持連線，因此 Claude 會記住之前的訊息。輸入 `new` 以斷開連線並重新連線以開始新的工作階段，或輸入 `exit` 以結束對話。

```python theme={null}
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
)
import asyncio


class ConversationSession:
    """Maintains a single conversation session with Claude."""

    def __init__(self, options: ClaudeAgentOptions | None = None):
        self.client = ClaudeSDKClient(options)
        self.turn_count = 0

    async def start(self):
        await self.client.connect()
        print("Starting conversation session. Claude will remember context.")
        print(
            "Commands: 'exit' to quit, 'interrupt' to stop current task, 'new' for new session"
        )

        while True:
            user_input = input(f"\n[Turn {self.turn_count + 1}] You: ")

            if user_input.lower() == "exit":
                break
            elif user_input.lower() == "interrupt":
                await self.client.interrupt()
                print("Task interrupted!")
                continue
            elif user_input.lower() == "new":
                # Disconnect and reconnect for a fresh session
                await self.client.disconnect()
                await self.client.connect()
                self.turn_count = 0
                print("Started new conversation session (previous context cleared)")
                continue

            # Send message - the session retains all previous messages
            await self.client.query(user_input)
            self.turn_count += 1

            # Process response
            print(f"[Turn {self.turn_count}] Claude: ", end="")
            async for message in self.client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            print(block.text, end="")
            print()  # New line after response

        await self.client.disconnect()
        print(f"Conversation ended after {self.turn_count} turns.")


async def main():
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Write", "Bash"], permission_mode="acceptEdits"
    )
    session = ConversationSession(options)
    await session.start()


# Example conversation:
# Turn 1 - You: "Create a file called hello.py"
# Turn 1 - Claude: "I'll create a hello.py file for you..."
# Turn 2 - You: "What's in that file?"
# Turn 2 - Claude: "The hello.py file I just created contains..." (remembers!)
# Turn 3 - You: "Add a main function to it"
# Turn 3 - Claude: "I'll add a main function to hello.py..." (knows which file!)

asyncio.run(main())
```

## 錯誤處理

以下範例將 `query()` 呼叫包裝在四個 [SDK 引發的錯誤類型](#error-types) 的處理程式中。

此範例捕捉 [`ResultError`](#resulterror)，需要 Python Agent SDK 0.2.140 或更新版本。

```python theme={null}
import asyncio

from claude_agent_sdk import (
    query,
    CLINotFoundError,
    ProcessError,
    ResultError,
    CLIJSONDecodeError,
)


async def main():
    try:
        async for message in query(prompt="Hello"):
            print(message)
    except CLINotFoundError:
        print(
            "Claude Code CLI not found. Try reinstalling: pip install --force-reinstall claude-agent-sdk"
        )
    # Catch ResultError before ProcessError, which it subclasses. Its message
    # carries the error text. A refusal and a failed final request both usually
    # arrive with subtype "success", so check stop_reason, then terminal_reason.
    except ResultError as e:
        if e.data.get("stop_reason") == "refusal":
            print(f"Model declined to respond: {e}")
        elif e.terminal_reason == "api_error":
            print(f"API request failed: {e}")
        else:
            print(f"Query ended with an error result ({e.terminal_reason or e.subtype}): {e}")
    except ProcessError as e:
        print(f"Process failed with exit code: {e.exit_code}")
    except CLIJSONDecodeError as e:
        print(f"Failed to parse response: {e}")


asyncio.run(main())
```

## 沙箱配置

### `SandboxSettings`

沙箱行為的配置。使用此來啟用命令沙箱並以程式設計方式配置網路限制。

```python theme={null}
class SandboxSettings(TypedDict, total=False):
    enabled: bool
    autoAllowBashIfSandboxed: bool
    excludedCommands: list[str]
    allowUnsandboxedCommands: bool
    network: SandboxNetworkConfig
    ignoreViolations: SandboxIgnoreViolations
    enableWeakerNestedSandbox: bool
```

| 屬性 | 類型 | 預設 | 描述 |
| :- | :- | :- | :- |
| `enabled` | `bool` | `False` | 為命令執行啟用沙箱模式 |
| `autoAllowBashIfSandboxed` | `bool` | `True` | 啟用沙箱時自動批准 bash 命令 |
| `excludedCommands` | `list[str]` | `[]` | 繞過沙箱限制的命令，例如 `["docker *"]`。這些自動執行沙箱外，無需模型參與；[`sandbox.excludedCommands`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-excludedcommands) 涵蓋何時適用項目 |
| `allowUnsandboxedCommands` | `bool` | `True` | 允許模型請求在沙箱外執行命令。當為 `True` 時，模型可以在 tool 輸入中設定 `dangerouslyDisableSandbox`，這會回退到[權限系統](#permissions-fallback-for-unsandboxed-commands) |
| `network` | [`SandboxNetworkConfig`](#sandboxnetworkconfig) | `None` | 網路特定的沙箱配置 |
| `ignoreViolations` | [`SandboxIgnoreViolations`](#sandboxignoreviolations) | `None` | 配置要忽略的沙箱違規 |
| `enableWeakerNestedSandbox` | `bool` | `False` | 啟用較弱的嵌套沙箱以相容性 |

> [!NOTE]
>
> 沙箱取決於平台支援，在 Linux 上，需要 `bubblewrap` 和 `socat` 等工具。預設情況下，當 `enabled` 為 `True` 但沙箱無法啟動時，命令會在沙箱外執行，並在 stderr 上顯示警告。此預設與 TypeScript SDK 不同，其中 `failIfUnavailable` 預設為 `true`。
>
> 在沙箱設定中設定 `"failIfUnavailable": True` 以改為停止。SDK 會將 `failIfUnavailable` 連同已宣告的 `SandboxSettings` 欄位一起轉發給 Claude Code。`query()` 接著會回報 `ResultMessage`，其中 `subtype="error_during_execution"` 且原因在 `errors` 中。因為這是單次 `query()` 呼叫，SDK 會在產生該錯誤結果後引發例外，所以請將迴圈包裝在 try 區塊中以便繼續執行。請參閱[處理結果](https://code.claude.com/docs/zh-TW/agent-sdk/agent-loop.md#handle-the-result)以了解錯誤合約。

若要防止沙箱化命令寫入某個檔案，請在沙箱設定的 [`denyWrite`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-filesystem-denywrite) 下列出其絕對路徑，例如 `"filesystem": {"denyWrite": ["/home/user/project/.env"]}`。SDK 會將 `filesystem` 連同已宣告的 `SandboxSettings` 欄位一起轉發給 Claude Code。沙箱啟動後，會封鎖對您列出的每個絕對路徑的寫入。

#### 範例使用

```python theme={null}
import asyncio

from claude_agent_sdk import query, ClaudeAgentOptions

sandbox_settings = {
    "enabled": True,
    "autoAllowBashIfSandboxed": True,
    "failIfUnavailable": True,
    "network": {"allowLocalBinding": True},
}


async def main():
    try:
        async for message in query(
            prompt="Build and test my project",
            options=ClaudeAgentOptions(sandbox=sandbox_settings),
        ):
            print(message)
    except Exception as error:
        # A single-shot query() raises after yielding an error result,
        # such as when failIfUnavailable is set and the sandbox can't start.
        print(f"Session ended with an error: {error}")


asyncio.run(main())
```

> [!WARNING]
>
> **Unix socket 安全性**：`allowUnixSockets` 選項可以授予對系統服務的存取權限，這些服務可能超出沙箱範圍。例如，允許 `/var/run/docker.sock` 實際上透過 Docker API 授予完整主機系統存取權限，繞過沙箱隔離。僅允許嚴格必要的 Unix sockets，並了解每個的安全含義。

### `SandboxNetworkConfig`

沙箱模式的網路特定配置。這些設定適用於當父 [`SandboxSettings`](#sandboxsettings) 中的 `enabled` 為 `True` 時的沙箱化 Bash 命令。它們不會限制 WebFetch 工具，該工具改用[權限規則](https://code.claude.com/docs/zh-TW/permissions.md#webfetch)。

```python theme={null}
class SandboxNetworkConfig(TypedDict, total=False):
    allowedDomains: list[str]
    deniedDomains: list[str]
    allowManagedDomainsOnly: bool
    allowUnixSockets: list[str]
    allowAllUnixSockets: bool
    allowLocalBinding: bool
    allowMachLookup: list[str]
    httpProxyPort: int
    socksProxyPort: int
```

| 屬性 | 類型 | 預設 | 描述 |
| :- | :- | :- | :- |
| `allowedDomains` | `list[str]` | `[]` | 沙箱化程序可以存取的網域名稱 |
| `deniedDomains` | `list[str]` | `[]` | 沙箱化程序無法存取的網域名稱。優先於 `allowedDomains` |
| `allowManagedDomainsOnly` | `bool` | `False` | 僅限受管設定：在受管設定中設定時，忽略 `allowedDomains` 和來自非受管設定來源的 `WebFetch(domain:...)` 允許規則。透過 SDK 選項設定時無效 |
| `allowUnixSockets` | `list[str]` | `[]` | 僅限 macOS：程序可以存取的 Unix socket 路徑，例如 Docker socket。在 Linux 上被忽略 |
| `allowAllUnixSockets` | `bool` | `False` | 允許存取所有 Unix sockets，並在 Linux 上允許存取 VM sockets（`AF_VSOCK`） |
| `allowLocalBinding` | `bool` | `False` | 允許程序繫結到本地連接埠（例如開發伺服器） |
| `allowMachLookup` | `list[str]` | `[]` | 僅限 macOS：允許的 XPC/Mach 服務名稱。支援尾部萬用字元 |
| `httpProxyPort` | `int` | `None` | 網路請求的 HTTP proxy 連接埠 |
| `socksProxyPort` | `int` | `None` | 網路請求的 SOCKS proxy 連接埠 |

> [!NOTE]
>
> 內建沙箱 proxy 根據請求的主機名稱強制執行網路允許清單，不會終止或檢查 TLS 流量，因此[網域前置](https://en.wikipedia.org/wiki/Domain_fronting)等技術可能會繞過它。有關詳細資訊，請參閱[沙箱安全限制](https://code.claude.com/docs/zh-TW/sandboxing.md#security-limitations)，以及[安全部署](https://code.claude.com/docs/zh-TW/agent-sdk/secure-deployment.md#traffic-forwarding)以配置 TLS 終止 proxy。

### `SandboxIgnoreViolations`

用於忽略特定沙箱違規的配置。

```python theme={null}
class SandboxIgnoreViolations(TypedDict, total=False):
    file: list[str]
    network: list[str]
```

| 屬性 | 類型 | 預設 | 描述 |
| :- | :- | :- | :- |
| `file` | `list[str]` | `[]` | 要忽略違規的檔案路徑模式 |
| `network` | `list[str]` | `[]` | 要忽略違規的網路模式 |

### 未沙箱化命令的權限回退

當 `allowUnsandboxedCommands` 啟用時，模型可以透過在 tool 輸入中設定 `dangerouslyDisableSandbox: True` 來請求在沙箱外執行命令。這些請求回退到現有權限系統，意味著您的 `can_use_tool` 處理程序將被呼叫，允許您實現自訂授權邏輯。

您的 `excludedCommands` 項目改為自動繞過沙箱，無需模型參與；[`sandbox.excludedCommands`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-excludedcommands) 涵蓋何時適用項目。

以下範例記錄每個未沙箱化請求，並除非您自己的授權邏輯允許，否則拒絕它：

```python theme={null}
import asyncio
from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    HookMatcher,
    PermissionResultAllow,
    PermissionResultDeny,
    ToolPermissionContext,
)


def is_command_authorized(command: str | None) -> bool:
    # Replace with your own authorization logic
    return False



async def can_use_tool(
    tool: str, input: dict, context: ToolPermissionContext
) -> PermissionResultAllow | PermissionResultDeny:
    # Check if the model is requesting to bypass the sandbox
    if tool == "Bash" and input.get("dangerouslyDisableSandbox"):
        # The model is requesting to run this command outside the sandbox
        print(f"Unsandboxed command requested: {input.get('command')}")

        if is_command_authorized(input.get("command")):
            return PermissionResultAllow()
        return PermissionResultDeny(
            message="Command not authorized for unsandboxed execution"
        )
    return PermissionResultAllow()


# Required: dummy hook keeps the stream open for can_use_tool
async def dummy_hook(input_data, tool_use_id, context):
    return {"continue_": True}


async def prompt_stream():
    yield {
        "type": "user",
        "message": {"role": "user", "content": "Deploy my application"},
    }


async def main():
    async for message in query(
        prompt=prompt_stream(),
        options=ClaudeAgentOptions(
            sandbox={
                "enabled": True,
                "allowUnsandboxedCommands": True,  # Model can request unsandboxed execution
            },
            permission_mode="default",
            can_use_tool=can_use_tool,
            hooks={"PreToolUse": [HookMatcher(matcher=None, hooks=[dummy_hook])]},
        ),
    ):
        print(message)


asyncio.run(main())
```

> [!WARNING]
>
> 使用 `dangerouslyDisableSandbox: True` 執行的命令具有完整系統存取權限。確保您的 `can_use_tool` 處理程序仔細驗證這些請求。
>
> 如果 `permission_mode` 設定為 `bypassPermissions` 且 `allowUnsandboxedCommands` 啟用，模型可以自主執行沙箱外的命令，無需批准提示，除了[任何模式都不會自動核准的動作](https://code.claude.com/docs/zh-TW/permission-modes.md#actions-no-mode-auto-approves)。此組合實際上允許模型無聲地逃脫沙箱隔離。

## 另見

* [SDK 概述](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) - 一般 SDK 概念
* [TypeScript SDK 參考](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md) - TypeScript SDK 文件
* [自訂工具](https://code.claude.com/docs/zh-TW/agent-sdk/custom-tools.md) - 為 Claude 定義可呼叫的程序內 MCP 工具
* [CLI 參考](https://code.claude.com/docs/zh-TW/cli-reference.md) - 命令列介面
* [常見工作流程](https://code.claude.com/docs/zh-TW/common-workflows.md) - 逐步指南

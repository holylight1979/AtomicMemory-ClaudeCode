<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/agent-sdk/typescript | lastmod: 2026-11-03 | section: Agent SDK / SDK references -->
> 來源：https://code.claude.com/docs/zh-TW/agent-sdk/typescript（官方 zh-TW，lastmod 2026-11-03）｜分類：Agent SDK › SDK references｜EN 摘要：Complete API reference for the TypeScript Agent SDK, including all functions, types, and interfaces.

# Agent SDK 參考 - TypeScript

> TypeScript Agent SDK 的完整 API 參考，包括所有函數、類型和介面。

## 安裝

```bash theme={null}
npm install @anthropic-ai/claude-agent-sdk
```

> [!NOTE]
>
> SDK 為您的平台捆綁了一個原生 Claude Code 二進制文件作為可選依賴項，例如 `@anthropic-ai/claude-agent-sdk-darwin-arm64`。大多數安裝不需要單獨安裝 Claude Code。SDK 版本追蹤捆綁的 Claude Code 版本。SDK v0.3.191 捆綁 Claude Code v2.1.191，因此本頁面上需要特定 Claude Code 版本的功能需要具有相同補丁號或更高版本的 SDK 版本。如果您的包管理器跳過可選依賴項，SDK 會拋出 `Native CLI binary for <platform>-<arch> not found`；改為將 [`pathToClaudeCodeExecutable`](#options) 設置為單獨安裝的 `claude` 二進制文件。
>
> 如果您的包管理器不應用 npm 的 `libc` 欄位（如 Yarn 1.x 不應用），您會在 Linux 上同時獲得 glibc 和 musl 平台包，大約使安裝大小翻倍。在 Agent SDK v0.2.141 或更高版本上，SDK 仍會啟動正確的變體。要在容器映像中回收空間，請刪除與您的應用程式運行的 libc 不匹配的平台包；對於 x64 上的 glibc 運行時，即 `rm -rf node_modules/@anthropic-ai/claude-agent-sdk-linux-x64-musl`。在開發機器上，刪除是臨時的，因為 Yarn 會在下一次依賴項更改時重新安裝該包。

### 編譯為單個可執行文件

當您使用 `bun build --compile` 將應用程式編譯為單個文件可執行文件時，SDK 無法在運行時解析捆綁的 CLI 二進制文件。`require.resolve` 在編譯後可執行文件的 `$bunfs` 虛擬文件系統內不起作用，因此 SDK 會拋出 `Native CLI binary for <platform>-<arch> not found`。

要解決此問題，請將平台二進制文件嵌入為文件資產，在啟動時使用 `extractFromBunfs()` 將其提取到真實路徑，並將該路徑傳遞給 [`pathToClaudeCodeExecutable`](#options)。

`extractFromBunfs()` 輔助函數需要 `@anthropic-ai/claude-agent-sdk` v0.3.144 或更高版本。下面的示例為 Apple Silicon 上的 macOS 構建：

```typescript theme={null}
import binPath from "@anthropic-ai/claude-agent-sdk-darwin-arm64/claude" with { type: "file" };
import { extractFromBunfs } from "@anthropic-ai/claude-agent-sdk/extract";
import { query } from "@anthropic-ai/claude-agent-sdk";

const cliPath = extractFromBunfs(binPath);

for await (const message of query({
  prompt: "Hello",
  options: { pathToClaudeCodeExecutable: cliPath },
})) {
  console.log(message);
}
```

`extractFromBunfs()` 將嵌入的二進制文件從編譯後可執行文件的虛擬文件系統複製到每個使用者的臨時目錄，並返回真實路徑。在編譯後的可執行文件外，它返回輸入路徑不變，因此相同的程式碼在開發中無需修改即可運行。

每個編譯後的可執行文件都嵌入單個平台的二進制文件。將導入中的平台包與您的 `--target` 匹配：

* 要進行交叉編譯，請安裝不匹配的平台包，例如 `npm install @anthropic-ai/claude-agent-sdk-linux-x64 --force`。
* 在 Windows 上，二進制子路徑是 `claude.exe`，例如 `@anthropic-ai/claude-agent-sdk-win32-x64/claude.exe`。

### 當您捆綁 Agent SDK 時從 `/core` 入口導入

如果您的應用程式將 Agent SDK 與其自身的依賴項一起捆綁，請從 `@anthropic-ai/claude-agent-sdk/core` 而不是包根目錄導入。`/core` 入口需要 TypeScript Agent SDK v0.3.282 或更高版本，其類型需要 TypeScript 5.0 或更高版本。

為了讓應用程式載入的程式碼保持精簡，`/core` 入口省略了部分根匯出：

* **已匯出**：與根入口相同的 `query()`、`startup()`、[`prewarm()`](#prewarm)、`tool()`、`createSdkMcpServer()` 和 `resolveSettings()`，以及重新命名、標記和刪除工作階段的函式、`AbortError`、執行階段常數和所有型別。從 `/core` 匯入 alpha 版的 `prewarm()` 需要 Agent SDK v0.3.314 或更高版本。
* **已省略**：包括 `InMemorySessionStore` 類別，以及列出、讀取、分叉、匯入和摘要工作階段的輔助函式在內的根匯出。如果您需要其中之一，請改用根入口。

根入口內聯了自己的 `zod` 和 `@modelcontextprotocol/sdk` 副本。`/core` 入口從您的 `node_modules` 按照 Agent SDK 的 `peerDependencies` 聲明的範圍導入它們，因此已經包含它們的捆綁不會攜帶第二份副本。在給定的程序中從根或 `/core` 導入，而不是兩者：它們是單獨的捆綁，加載兩者會給您兩份 Agent SDK 的類和狀態副本。

## 函式

### `query()`

與 Claude Code 互動的主要函式。建立一個非同步產生器，在訊息抵達時以串流方式傳送訊息。

```typescript theme={null}
function query({
  prompt,
  options
}: {
  prompt: string | AsyncIterable<SDKUserMessage>;
  options?: Options;
}): Query;
```

#### 參數

| 參數 | 型別 | 說明 |
| :- | :- | :- |
| `prompt` | `string \| AsyncIterable<`[`SDKUserMessage`](#sdkusermessage)`>` | 輸入提示詞，可以是字串，或用於串流模式的非同步可迭代物件 |
| `options` | [`Options`](#options) | 選用的設定物件（請參閱下方的 Options 型別） |

#### 傳回值

傳回一個 [`Query`](#query-object) 物件，它擴充了 `AsyncGenerator<`[`SDKMessage`](#sdkmessage)`, void>` 並提供額外的方法。

### `startup()`

在提示詞可用之前，先啟動 CLI 子程序並完成初始化交握，藉此預熱 CLI 子程序。傳回的 [`WarmQuery`](#warmquery) 控制代碼稍後可接受提示詞，並將其寫入已就緒的程序，因此第一次 `query()` 呼叫在解析時，不必當場負擔子程序啟動與初始化的成本。如果您還不知道工作階段的工作目錄，請改用 [`prewarm()`](#prewarm)。

```typescript theme={null}
function startup(params?: {
  options?: Options;
  initializeTimeoutMs?: number;
}): Promise<WarmQuery>;
```

#### 參數

| 參數 | 型別 | 說明 |
| :- | :- | :- |
| `options` | [`Options`](#options) | 選用的設定物件。與 `query()` 的 `options` 參數相同 |
| `initializeTimeoutMs` | `number` | 等待子程序初始化的最長時間（毫秒）。預設為 `60000`。如果初始化未在時限內完成，promise 會以逾時錯誤拒絕 |

#### 傳回值

傳回一個 `Promise<`[`WarmQuery`](#warmquery)`>`，在子程序啟動並完成初始化交握後解析。

在交握完成之前，`SessionStart` 或 `Setup` hook 所發出的 [`hook_progress`](#sdkhookprogressmessage) 訊息中，您只會收到最新的一則，其中包含該 hook 到目前為止的所有輸出。`startup()` 會保留該訊息、該 hook 的 [`hook_started`](#sdkhookstartedmessage) 訊息，以及子程序在交握完成前發出的任何其他訊息。當您對 `WarmQuery` 呼叫 `.query()` 並迭代結果時，這些保留的訊息就會傳遞給您。

#### 範例

盡早呼叫 `startup()`，例如在應用程式啟動時，然後在提示詞準備好後，對傳回的控制代碼呼叫 `.query()`。這樣可將子程序啟動與初始化移出關鍵路徑。

```typescript theme={null}
import { startup } from "@anthropic-ai/claude-agent-sdk";

// 提前支付啟動成本
const warm = await startup({ options: { maxTurns: 3 } });

// 稍後，當提示詞準備好時，這會立即執行
for await (const message of warm.query("What files are here?")) {
  console.log(message);
}
```

### `prewarm()`

*Alpha。* 在您知道要服務哪個工作階段之前，先啟動一個 Claude Code 程序作為備用，以便稍後透過 [`claim()`](#spareprocess) 將其繫結到某個工作階段。適用於在使用者選擇資料夾之前就已啟動的應用程式。需要 TypeScript Agent SDK v0.3.282 或更新版本。

`prewarm()` 會完成與 [`startup()`](#startup) 相同的初始化交握；若您設定了 `options.cwd`，程序會在該目錄中等待，否則會在您 Claude Code 設定目錄下的私有暫存目錄中等待。工作階段的工作目錄、其 `SessionStart` hook、其 stdio MCP 伺服器，以及其 CLAUDE.md 和 git 上下文，都會等到認領時才處理。備用程序在等待期間約佔用 230 到 260 MB 的記憶體。如果您的 [`spawnClaudeCodeProcess`](#options) 在另一台機器或容器中執行 Claude Code，請將 `options.cwd` 設定為該處存在的目錄，讓備用程序在其中等待。

```typescript theme={null}
function prewarm(params?: {
  options?: Options;
  initializeTimeoutMs?: number;
}): Promise<SpareProcess>;
```

`options` 和 `initializeTimeoutMs` 的意義與 `startup()` 相同，但 `options.cwd` 僅設定備用程序等待的目錄。程序完成初始化交握後，promise 會以 [`SpareProcess`](#spareprocess) 解析。如果 `options` 設定了 `resume`、`continue` 或 `forkSession`，`prewarm()` 會擲出例外，因為備用程序尚無工作階段。凡是認領時無法設定的項目，例如 `mcpServers`、`hooks`、`canUseTool`、`settingSources`、`systemPrompt` 和 `plugins`，在備用程序的整個生命週期中都是固定的，因此請為每組不同的這類選項各保留一個備用程序，並在它們變更時重新預熱。

#### 範例

在應用程式啟動時預熱，然後在使用者開始工作階段時認領備用程序：

```typescript theme={null}
import { prewarm } from "@anthropic-ai/claude-agent-sdk";

// 在應用程式啟動時，尚未得知工作階段的資料夾之前
const spare = await prewarm({ options: { maxTurns: 3 } });

// 稍後，當使用者在某個資料夾中開始工作階段時
const claimedQuery = spare.claim({
  prompt: "What files are here?",
  options: { cwd: "/path/to/project" },
});

spare.claimed.catch((error: Error) => {
  // 除非訊息以 "option_not_applied" 開頭，否則提示詞並未執行：
  // 請改用 query() 啟動此工作階段
  console.error("Claim failed:", error.message);
});

try {
  for await (const message of claimedQuery) {
    console.log(message);
  }
} catch (error) {
  // claim 遭拒後，claimed query 會在產出錯誤結果後擲出例外
  console.error(`Session ended with an error: ${error}`);
}
```

### `tool()`

建立型別安全的 MCP 工具定義，供 SDK MCP 伺服器使用。

```typescript theme={null}
function tool<Schema extends AnyZodRawShape>(
  name: string,
  description: string,
  inputSchema: Schema,
  handler: (args: InferShape<Schema>, extra: unknown) => Promise<CallToolResult>,
  extras?: { annotations?: ToolAnnotations; searchHint?: string; alwaysLoad?: boolean }
): SdkMcpToolDefinition<Schema>;
```

#### 參數

| 參數 | 型別 | 說明 |
| :- | :- | :- |
| `name` | `string` | 工具的名稱 |
| `description` | `string` | 工具功能的說明 |
| `inputSchema` | `Schema extends AnyZodRawShape` | 定義工具輸入參數的 Zod schema（同時支援 Zod 3 和 Zod 4） |
| `handler` | `(args, extra) => Promise<`[`CallToolResult`](#calltoolresult)`>` | 執行工具邏輯的非同步函式 |
| `extras` | `{ annotations?: `[`ToolAnnotations`](#toolannotations)`; searchHint?: string; alwaysLoad?: boolean }` | 選用的額外項目。`annotations` 向用戶端提供 MCP 行為提示。`searchHint` 是一行描述功能的短語，在 [tool search](https://code.claude.com/docs/zh-TW/agent-sdk/tool-search.md) 啟用時顯示於延遲載入工具清單中。`alwaysLoad: true` 會將此工具的完整 schema 保留在初始提示詞中，而不延遲載入 |

#### `ToolAnnotations`

定義於 `@modelcontextprotocol/sdk/types.js`。所有欄位都是選用的提示；用戶端不應依賴它們做出安全性決策。

| 欄位 | 型別 | 預設值 | 說明 |
| :- | :- | :- | :- |
| `title` | `string` | `undefined` | 工具的人類可讀標題 |
| `readOnlyHint` | `boolean` | `false` | 若為 `true`，工具不會修改其環境 |
| `destructiveHint` | `boolean` | `true` | 若為 `true`，工具可能執行破壞性更新。對於您標記為 [`always_ask`](#mcpservertoolpolicy) 的任何工具，請明確設定 `destructiveHint: true`，否則自動模式分類器可能會代替您的 `canUseTool` 回呼核准該工具的呼叫。僅讓 `destructiveHint` 保持未設定是不夠的，因為 Claude Code 在處理 `always_ask` 呼叫時，會將未設定的 `destructiveHint` 視為 `false`，儘管 MCP 規格的預設值為 `true` |
| `idempotentHint` | `boolean` | `false` | 若為 `true`，以相同引數重複呼叫不會產生額外效果（僅在 `readOnlyHint` 為 `false` 時有意義） |
| `openWorldHint` | `boolean` | `true` | 若為 `true`，工具會與外部實體互動（例如網路搜尋）。若為 `false`，工具的範圍是封閉的（例如記憶工具） |

```typescript theme={null}
import { tool } from "@anthropic-ai/claude-agent-sdk";
import { z } from "zod";

const searchTool = tool(
  "search",
  "Search the web",
  { query: z.string() },
  async ({ query }) => {
    return { content: [{ type: "text", text: `Results for: ${query}` }] };
  },
  { annotations: { readOnlyHint: true, openWorldHint: true } }
);
```

### `createSdkMcpServer()`

建立一個與您的應用程式在同一程序中執行的 MCP 伺服器執行個體。

```typescript theme={null}
function createSdkMcpServer(options: {
  name: string;
  version?: string;
  instructions?: string;
  tools?: Array<SdkMcpToolDefinition<any>>;
  alwaysLoad?: boolean;
  timeout?: number;
}): McpSdkServerConfigWithInstance;
```

#### 參數

| 參數 | 型別 | 說明 |
| :- | :- | :- |
| `options.name` | `string` | MCP 伺服器的名稱 |
| `options.version` | `string` | 選用的版本字串 |
| `options.instructions` | `string` | 選用的伺服器指示，從 `initialize` 傳回，並以 MCP 指示區塊的形式呈現給模型 |
| `options.tools` | `Array<SdkMcpToolDefinition>` | 使用 [`tool()`](#tool) 建立的工具定義陣列 |
| `options.alwaysLoad` | `boolean` | 若為 `true`，此伺服器的工具都會保留在初始提示詞中，而不是延遲到 [tool search](https://code.claude.com/docs/zh-TW/agent-sdk/tool-search.md) 之後才載入。可與 [`tool()`](#tool) 中個別工具的 `alwaysLoad` 搭配使用 |
| `options.timeout` | `number` | 此伺服器工具呼叫的逾時時間（毫秒）。Claude Code 會以此值取代 [`MCP_TOOL_TIMEOUT`](https://code.claude.com/docs/zh-TW/env-vars) 套用於此伺服器。請傳入至少為 1000 的整數。Claude Code 會忽略其他值。需要 TypeScript Agent SDK v0.3.248 或更新版本 |

### `listSessions()`

探索並列出過去的工作階段及其輕量中繼資料。可依專案目錄篩選，或列出所有專案中的工作階段。

```typescript theme={null}
function listSessions(options?: ListSessionsOptions): Promise<SDKSessionInfo[]>;
```

#### 參數

| 參數 | 型別 | 預設值 | 說明 |
| :- | :- | :- | :- |
| `options.dir` | `string` | `undefined` | 要列出工作階段的目錄。省略時，傳回所有專案中的工作階段 |
| `options.limit` | `number` | `undefined` | 傳回的工作階段數量上限 |
| `options.includeWorktrees` | `boolean` | `true` | 當 `dir` 位於 git 儲存庫內時，納入所有 worktree 路徑中的工作階段 |

#### 傳回型別：`SDKSessionInfo`

| 屬性 | 型別 | 說明 |
| :- | :- | :- |
| `sessionId` | `string` | 唯一的工作階段識別碼（UUID） |
| `summary` | `string` | 顯示標題：自訂標題、最近的提示詞、自動產生的摘要，或第一個提示詞 |
| `lastModified` | `number` | 上次修改時間（自 epoch 起算的毫秒數） |
| `fileSize` | `number \| undefined` | 工作階段檔案大小（位元組）。僅在使用本機 JSONL 儲存時填入 |
| `customTitle` | `string \| undefined` | 工作階段已設定的自訂標題，例如透過 `--name`、`/rename`、hook 的 `sessionTitle` 輸出或 [`renameSession()`](#renamesession) 設定。若未設定，則為 AI 產生的工作階段標題（如果工作階段有的話） |
| `firstPrompt` | `string \| undefined` | 工作階段中第一個有意義的使用者提示詞 |
| `gitBranch` | `string \| undefined` | 工作階段結束時的 Git 分支 |
| `cwd` | `string \| undefined` | 工作階段的工作目錄 |
| `tag` | `string \| undefined` | 使用者設定的工作階段標籤（請參閱 [`tagSession()`](#tagsession)） |
| `createdAt` | `number \| undefined` | 建立時間（自 epoch 起算的毫秒數），取自第一個項目的時間戳記 |

#### 範例

列印某個專案最近的 10 個工作階段。結果依 `lastModified` 遞減排序，因此第一個項目是最新的。省略 `dir` 即可搜尋所有專案。

```typescript theme={null}
import { listSessions } from "@anthropic-ai/claude-agent-sdk";

const sessions = await listSessions({ dir: "/path/to/project", limit: 10 });

for (const session of sessions) {
  console.log(`${session.summary} (${session.sessionId})`);
}
```

### `getSessionMessages()`

從過去的工作階段逐字稿中讀取使用者與助理訊息。

```typescript theme={null}
function getSessionMessages(
  sessionId: string,
  options?: GetSessionMessagesOptions
): Promise<SessionMessage[]>;
```

#### 參數

| 參數 | 型別 | 預設值 | 說明 |
| :- | :- | :- | :- |
| `sessionId` | `string` | 必填 | 要讀取的工作階段 UUID（請參閱 `listSessions()`） |
| `options.dir` | `string` | `undefined` | 用來尋找工作階段的專案目錄。省略時，搜尋所有專案 |
| `options.limit` | `number` | `undefined` | 傳回的訊息數量上限 |
| `options.offset` | `number` | `undefined` | 從開頭略過的訊息數量 |
| `options.includeSystemMessages` | `boolean` | `false` | 若為 `true`，除了使用者與助理訊息外，也會傳回系統訊息，例如壓縮邊界 |

#### 傳回型別：`SessionMessage`

| 屬性 | 型別 | 說明 |
| :- | :- | :- |
| `type` | `"user" \| "assistant" \| "system"` | 訊息角色。僅在 `options.includeSystemMessages` 為 `true` 時才會出現 `"system"` |
| `uuid` | `string` | 唯一的訊息識別碼 |
| `session_id` | `string` | 此訊息所屬的工作階段 |
| `message` | `unknown` | 來自逐字稿的原始訊息 payload |
| `parent_tool_use_id` | `string \| null` | 對於 subagent 訊息，為啟動該 subagent 的 `Agent` 或 `Skill` 工具呼叫的 `tool_use_id`。對於主工作階段訊息和較舊的工作階段為 `null` |
| `parent_agent_id` | `string \| null` | 對於來自[巢狀 subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#let-subagents-spawn-their-own-subagents) 的訊息，為產生該巢狀 subagent 的 subagent 的 `agentId`。對於主工作階段訊息、來自頂層 subagent 的訊息和較舊的工作階段為 `null`。需要 Claude Code v2.1.202 或更新版本 |

#### 範例

```typescript theme={null}
import { listSessions, getSessionMessages } from "@anthropic-ai/claude-agent-sdk";

const [latest] = await listSessions({ dir: "/path/to/project", limit: 1 });

if (latest) {
  const messages = await getSessionMessages(latest.sessionId, {
    dir: "/path/to/project",
    limit: 20
  });

  for (const msg of messages) {
    console.log(`[${msg.type}] ${msg.uuid}`);
  }
}
```

### `getSessionInfo()`

依 ID 讀取單一工作階段的中繼資料，無需掃描整個專案目錄。

```typescript theme={null}
function getSessionInfo(
  sessionId: string,
  options?: GetSessionInfoOptions
): Promise<SDKSessionInfo | undefined>;
```

#### 參數

| 參數 | 型別 | 預設值 | 說明 |
| :- | :- | :- | :- |
| `sessionId` | `string` | 必填 | 要查詢的工作階段 UUID |
| `options.dir` | `string` | `undefined` | 專案目錄路徑。省略時，搜尋所有專案目錄 |

傳回 [`SDKSessionInfo`](#return-type-sdksessioninfo)；若找不到工作階段，則傳回 `undefined`。

### `renameSession()`

透過附加一個自訂標題項目來重新命名工作階段。重複呼叫是安全的；以最新的標題為準。

```typescript theme={null}
function renameSession(
  sessionId: string,
  title: string,
  options?: SessionMutationOptions
): Promise<void>;
```

#### 參數

| 參數 | 型別 | 預設值 | 說明 |
| :- | :- | :- | :- |
| `sessionId` | `string` | 必填 | 要重新命名的工作階段 UUID |
| `title` | `string` | 必填 | 新標題。去除前後空白後不得為空 |
| `options.dir` | `string` | `undefined` | 專案目錄路徑。省略時，搜尋所有專案目錄 |

### `tagSession()`

為工作階段加上標籤。傳入 `null` 可清除標籤。重複呼叫是安全的；以最新的標籤為準。

```typescript theme={null}
function tagSession(
  sessionId: string,
  tag: string | null,
  options?: SessionMutationOptions
): Promise<void>;
```

#### 參數

| 參數 | 型別 | 預設值 | 說明 |
| :- | :- | :- | :- |
| `sessionId` | `string` | 必填 | 要加上標籤的工作階段 UUID |
| `tag` | `string \| null` | 必填 | 標籤字串，或傳入 `null` 以清除 |
| `options.dir` | `string` | `undefined` | 專案目錄路徑。省略時，搜尋所有專案目錄 |

### `forkSession()`

將工作階段的逐字稿複製到新的工作階段，讓您可以將對話導向另一個方向，同時保持原始工作階段不變。若要從對話中較早的某個時間點建立分支，請傳入 `upToMessageId`。

```typescript theme={null}
function forkSession(
  sessionId: string,
  options?: ForkSessionOptions
): Promise<ForkSessionResult>;
```

#### 參數

| 參數 | 型別 | 預設值 | 說明 |
| :- | :- | :- | :- |
| `sessionId` | `string` | 必填 | 要分叉的工作階段 UUID |
| `options.dir` | `string` | `undefined` | 專案目錄路徑。省略時，搜尋所有專案目錄 |
| `options.upToMessageId` | `string` | `undefined` | 複製逐字稿直到（並包含）具有此 `uuid` 的訊息：可以是來自 [`getSessionMessages()`](#getsessionmessages) 的值，或是您在串流傳送的 [`SDKUserMessage`](#sdkusermessage) 上設定的 `uuid`。省略時，複製整份逐字稿 |
| `options.title` | `string` | `undefined` | 分叉的標題。省略時，SDK 會從原始工作階段推導出標題，並在其後加上 `(fork)` |

傳回 `{ sessionId }`，即新工作階段的 UUID。將其作為 [`resume`](#options) 傳入即可繼續該分叉。分叉不包含原始工作階段的[檔案檢查點](https://code.claude.com/docs/zh-TW/agent-sdk/file-checkpointing.md)，因此您無法將其倒回至分叉之前擷取的檢查點。

`forkSession()` 在以下情況會擲出例外：

* `sessionId` 不是 UUID
* 找不到該工作階段，或該工作階段沒有任何訊息
* `upToMessageId` 與逐字稿中的任何訊息都不相符

### `resolveSettings()`

使用與 CLI 相同的合併引擎，為指定目錄解析實際生效的 Claude Code 設定，而不需啟動 Claude CLI。可在呼叫 `query()` 之前，用它檢查該 `query()` 呼叫將會看到哪些設定。

> [!NOTE]
>
> 此函式目前為 alpha 版，其 API 在穩定之前可能會變更。

此快照與實際執行中的 `query()` 工作階段所套用的內容有以下差異：

* **`policyHelper`**：`resolveSettings()` 會讀取 MDM 來源，包括 macOS plist 和 Windows HKLM/HKCU，但不會執行管理員設定的 `policyHelper` 子程序。
* **伺服器受管設定**：`resolveSettings()` 不會擷取[伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md#fetch-and-caching-behavior)。若要納入，請將其作為 `options.serverManagedSettings` 傳入。
* **`defaultMode`**：快照會原封不動地傳回每個層級的 `permissions.defaultMode`，因此可能包含來自專案與本機設定的 `'auto'` 和 `'bypassPermissions'` 值，而[實際執行的工作階段會忽略這些值](https://code.claude.com/docs/zh-TW/permission-modes.md#which-mode-a-session-starts-in)。

```typescript theme={null}
function resolveSettings(
  options?: ResolveSettingsOptions
): Promise<ResolvedSettings>;
```

#### 參數

`resolveSettings()` 接受單一選項物件。所有欄位皆為選用。

| 參數 | 型別 | 預設值 | 說明 |
| :- | :- | :- | :- |
| `options.cwd` | `string` | `process.cwd()` | 解析專案與本機設定時所依據的目錄 |
| `options.settingSources` | [`SettingSource`](#settingsource)`[]` | 所有來源 | 要載入的檔案系統來源。傳入 `[]` 可略過使用者、專案和本機設定。[端點受管政策](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)在任何情況下都會載入。`resolveSettings()` 僅在您傳入 `options.serverManagedSettings` 時才會納入伺服器受管設定 |
| `options.managedSettings` | `Settings` | `undefined` | 由嵌入主機提供的政策層級設定。遵循與 [`Options` 中的 `managedSettings`](#options) 相同的規則，但 `resolveSettings()` 不會執行已設定的 [`policyHelper`](https://code.claude.com/docs/zh-TW/settings-reference#policyhelper)，因此快照可能包含實際執行的工作階段會捨棄的設定 |
| `options.serverManagedSettings` | `Settings` | `undefined` | 來自 `/api/claude_code/settings` 的伺服器受管設定 payload。非限制性的鍵會不經篩選直接通過 |

#### 傳回型別：`ResolvedSettings`

`resolveSettings()` 會傳回一個物件，描述合併後的設定，以及提供每個鍵的來源。

| 屬性 | 型別 | 說明 |
| :- | :- | :- |
| `effective` | `Settings` | 依優先順序套用所有已啟用來源後的合併設定 |
| `provenance` | `Partial<Record<keyof Settings, ProvenanceEntry>>` | 針對 `effective` 中的每個頂層鍵，標示由哪個來源提供該值 |
| `sources` | `Array<{ source, settings, path?, policyOrigin? }>` | 各來源的原始設定，依優先順序由低至高排列 |

#### 範例

以下範例為專案目錄解析設定，並列印控制清理期間的來源。在沒有任何設定檔設定 `cleanupPeriodDays` 的機器上，列印出的兩行都會顯示值為 `undefined`，這是預期的輸出，而非錯誤。

```typescript theme={null}
import { resolveSettings } from "@anthropic-ai/claude-agent-sdk";

const { effective, provenance } = await resolveSettings({
  cwd: "/path/to/project",
  settingSources: ["user", "project", "local"],
});

console.log(`Cleanup period: ${effective.cleanupPeriodDays} days`);
console.log(`Set by: ${provenance.cleanupPeriodDays?.source}`);
```

## 型別

### `Options`

`query()` 函式的設定物件。

| 屬性 | 型別 | 預設值 | 說明 |
| :- | :- | :- | :- |
| `abortController` | `AbortController` | `new AbortController()` | 用於取消操作的控制器 |
| `additionalDirectories` | `string[]` | `[]` | Claude 可以存取的其他目錄。SDK 會將每個項目以 `--add-dir` 傳遞給 Claude Code，因此搭配 `project` 設定來源時，Claude Code 也會[載入該目錄的 skill、命令和 subagent](https://code.claude.com/docs/zh-TW/permissions.md#additional-directories-grant-file-access-not-configuration) |
| `agent` | `string` | `undefined` | 主執行緒的 agent 名稱。該 agent 必須在 `agents` 選項或設定中定義 |
| `agents` | `Record<string, [`AgentDefinition`](#agentdefinition)>` | `undefined` | 以程式方式定義 subagent |
| `agentProgressSummaries` | `boolean` | `false` | 設為 `true` 時，為 subagent 產生單行進度摘要，並透過 `summary` 欄位在 [`task_progress`](#sdktaskprogressmessage) 事件中轉送。適用於前景和背景 subagent |
| `allowDangerouslySkipPermissions` | `boolean` | `false` | 啟用略過權限。在啟動時或之後透過 `setPermissionMode()` 使用 `permissionMode: 'bypassPermissions'` 時為必要項目。關於它與 `permissionMode: 'plan'` 的互動方式，請參閱 [plan mode](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#plan-mode-plan) |
| `allowedTools` | `string[]` | `[]` | 無需提示即自動核准的工具，但從[網路路徑](https://code.claude.com/docs/zh-TW/permissions.md#network-paths)讀取的操作除外。這不會將 Claude 限制為只能使用這些工具。若您在此列出其中一個[任務追蹤工具](https://code.claude.com/docs/zh-TW/agent-sdk/todo-tracking.md#model-availability)，Claude Code 也會讓該工作階段啟用此功能。其他未列出的工具會交由 `permissionMode` 和 `canUseTool` 處理。使用 `disallowedTools` 封鎖工具。請參閱[權限](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#allow-and-deny-rules) |
| `betas` | [`SdkBeta`](#sdkbeta)`[]` | `[]` | 啟用 beta 功能 |
| `canUseTool` | [`CanUseTool`](#canusetool) | `undefined` | 自訂權限函式，僅在[權限流程](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#how-permissions-are-evaluated)落到提示時才會呼叫。對於由 `allowedTools`、允許規則或 `permissionMode` 自動核准的呼叫，不會呼叫此函式。允許規則不會預先核准[任何模式都不會自動核准的動作](https://code.claude.com/docs/zh-TW/permission-modes.md#actions-no-mode-auto-approves)。詳情請參閱 [`CanUseTool`](#canusetool) |
| `continue` | `boolean` | `false` | 繼續最近一次的對話 |
| `cwd` | `string` | `process.cwd()` | 目前的工作目錄 |
| `debug` | `boolean` | `false` | 為 Claude Code 程序啟用除錯模式 |
| `debugFile` | `string` | `undefined` | 將除錯日誌寫入特定檔案路徑。會隱含啟用除錯模式 |
| `disallowedTools` | `string[]` | `[]` | 要拒絕的工具。像 `"Bash"` 這樣的單純名稱會將該工具從 Claude 的上下文中移除。像 `"Bash(rm *)"` 這樣具範圍的規則會保留該工具可用，並在每種權限模式（包括 `bypassPermissions`）下拒絕符合的呼叫，比對依據是[所寫的命令內容](https://code.claude.com/docs/zh-TW/permissions.md#bash-rule-limits)。請參閱[權限](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#allow-and-deny-rules) |
| `effort` | `'low' \| 'medium' \| 'high' \| 'xhigh' \| 'max'` | `undefined` | 控制 Claude 在回應中投入多少 effort。與自適應思考搭配使用以引導思考深度。請參閱[調整 effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level) |
| `enableFileCheckpointing` | `boolean` | `false` | 啟用檔案變更追蹤以便倒回。請參閱[檔案檢查點功能](https://code.claude.com/docs/zh-TW/agent-sdk/file-checkpointing.md) |
| `env` | `Record<string, string \| undefined>` | `process.env` | 環境變數。設定後會取代子程序環境，而不是與 `process.env` 合併，因此請傳入 `{ ...process.env, YOUR_VAR: 'value' }` 以保留 `PATH` 等繼承的變數。此模式的範例請參閱[處理緩慢或停滯的 API 回應](#handle-slow-or-stalled-api-responses)，底層 CLI 讀取的變數請參閱[環境變數](https://code.claude.com/docs/zh-TW/env-vars.md)。設定 `CLAUDE_AGENT_SDK_CLIENT_APP` 以在 User-Agent 標頭中識別您的應用程式 |
| `executable` | `'bun' \| 'deno' \| 'node'` | 自動偵測 | 要使用的 JavaScript 執行環境 |
| `executableArgs` | `string[]` | `[]` | 要傳遞給執行檔的引數 |
| `extraArgs` | `Record<string, string \| null>` | `{}` | 其他引數 |
| `fallbackModel` | `string` | `undefined` | 主要模型失敗時使用的模型。接受以逗號分隔的清單。關於順序與上限，請參閱[備援模型鏈](https://code.claude.com/docs/zh-TW/model-config.md#fallback-model-chains)。相關指引請參閱[選擇模型](https://code.claude.com/docs/zh-TW/agent-sdk/configuration.md#choose-a-model) |
| `forkSession` | `boolean` | `false` | 使用 `resume` 恢復時，分支到新的工作階段 ID，而不是繼續原本的工作階段 |
| `forwardSubagentText` | `boolean` | `false` | 將 subagent 的文字和思考區塊以設定了 `parent_tool_use_id` 的 assistant 和 user 訊息轉送，讓消費端能呈現巢狀逐字稿。若未使用此選項，Claude Code 會省略在[前景](https://code.claude.com/docs/zh-TW/sub-agents.md#run-subagents-in-foreground-or-background)執行之 subagent 的文字和思考區塊。關於巢狀 subagent、使用 `context: fork` 的 skill，以及各自所需的 Claude Code 版本，請參閱[追蹤 subagent 訊息](https://code.claude.com/docs/zh-TW/headless.md#follow-subagent-messages) |
| `hooks` | `Partial<Record<`[`HookEvent`](#hookevent)`, `[`HookCallbackMatcher`](#hookcallbackmatcher)`[]>>` | `{}` | 事件的 hook 回呼 |
| `includeHookEvents` | `boolean` | `false` | 在訊息串流中以 [`SDKHookStartedMessage`](#sdkhookstartedmessage)、[`SDKHookProgressMessage`](#sdkhookprogressmessage) 和 [`SDKHookResponseMessage`](#sdkhookresponsemessage) 包含 hook 生命週期事件。`SessionStart` 和 `Setup` hook 的生命週期事件一律會包含，不需要此選項。某些 hook 事件（例如 `Notification`、`SessionEnd`、`PreCompact` 和 `PostCompact`）即使啟用此選項也永遠不會產生 `SDKHookStartedMessage`。對於這些事件，當執行超過一秒的命令 hook 產生輸出時，Claude Code 仍會發出 `SDKHookProgressMessage`，且僅在[於背景執行](https://code.claude.com/docs/zh-TW/hooks.md#run-hooks-in-the-background)的 hook 完成時才發出 `SDKHookResponseMessage` |
| `includePartialMessages` | `boolean` | `false` | 包含部分訊息事件 |
| `loadTimeoutMs` | `number` | `60000` | *Alpha。* 在恢復具體化期間，每次 `sessionStore.load()` 和 `sessionStore.listSubkeys()` 呼叫的逾時時間（毫秒）。若配接器未在此時間內完成，查詢會失敗而不是停滯。未設定 `sessionStore` 時會忽略 |
| `managedSettings` | `Settings` | `undefined` | 您的主機程序提供給所產生工作階段的政策層級設定。在具有管理員部署之受管設定的機器上，除非管理員最高優先順序的受管來源設定了 `parentSettingsBehavior: 'merge'`，否則 Claude Code 會忽略這些設定；且當 [`policyHelper`](https://code.claude.com/docs/zh-TW/settings-reference#policyhelper) 提供受管設定時，一律不會合併它們。合併的值會通過僅限收緊的篩選器；[限制上層設定](https://code.claude.com/docs/zh-TW/claude-apps-gateway#restrict-parent-settings)說明了篩選器允許的內容以及 `allowManaged*Only` 鎖定。設定了 [`CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST`](https://code.claude.com/docs/zh-TW/env-vars) 的主機則會直接從此 payload 讀取三個鍵：其[模型設定](https://code.claude.com/docs/zh-TW/model-config.md#restrict-model-selection)（Claude Code v2.1.222 或更新版本）、沒有受管來源設定時的 [`modelPricing`](https://code.claude.com/docs/zh-TW/settings-reference#modelpricing)（v2.1.246 或更新版本），以及其 `ENABLE_TOOL_SEARCH` env 項目（v2.1.247 或更新版本） |
| `maxBudgetUsd` | `number` | `undefined` | 當用戶端成本估算達到此 USD 值時停止查詢。估算值可能超過此值，因此請[保留餘裕](https://code.claude.com/docs/zh-TW/agent-sdk/agent-loop.md#budget-headroom)。僅計算該呼叫本身的花費；從恢復的工作階段還原的總額不計入。關於準確性注意事項與重設行為，請參閱[追蹤成本與用量](https://code.claude.com/docs/zh-TW/agent-sdk/cost-tracking.md) |
| `maxThinkingTokens` | `number` | `undefined` | *已淘汰：* 請改用 `thinking`。思考過程的最大 token 數 |
| `maxTurns` | `number` | `undefined` | 最大 agent [回合](https://code.claude.com/docs/zh-TW/agent-sdk/agent-loop.md#turns-and-messages)數 |
| `mcpServers` | `Record<string, [`McpServerConfig`](#mcpserverconfig)>` | `{}` | MCP 伺服器設定 |
| `model` | `string` | 來自 CLI 的預設值 | Claude 模型別名或完整模型名稱。請參閱[可接受的值與供應商特定 ID](https://code.claude.com/docs/zh-TW/model-config.md#available-models) |
| `onElicitation` | `(request: ElicitationRequest, options: { signal: AbortSignal }) => Promise<ElicitationResult>` | `undefined` | 處理 MCP elicitation 請求的回呼。當 MCP 伺服器請求使用者輸入且沒有 hook 先處理時呼叫。未提供時，未處理的 elicitation 請求會自動遭到拒絕 |
| `outputFormat` | `{ type: 'json_schema', schema: JSONSchema }` | `undefined` | 定義 agent 結果的輸出格式。詳情請參閱[結構化輸出](https://code.claude.com/docs/zh-TW/agent-sdk/structured-outputs.md) |
| `outputStyle` | `string` | `undefined` | 這不是 `Options` 欄位。請改在內嵌的 [`settings`](https://code.claude.com/docs/zh-TW/settings) 物件或設定檔中設定 `outputStyle`。請參閱[啟用輸出風格](https://code.claude.com/docs/zh-TW/agent-sdk/modifying-system-prompts.md#activate-an-output-style) |
| `pathToClaudeCodeExecutable` | `string` | 從隨附的原生二進位檔自動解析 | Claude Code 執行檔的路徑。僅在安裝時略過了選用相依套件，或您的平台不在支援清單中時才需要 |
| `permissionMode` | [`PermissionMode`](#permissionmode) | `undefined` | 工作階段的權限模式。若您省略此項且沒有其他項目設定權限模式（例如 [`permissions.defaultMode`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-defaultmode) 設定），工作階段會以 `default` 啟動。請參閱[權限模式](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#permission-modes) |
| `permissionPromptToolName` | `string` | `undefined` | 用於權限提示的 MCP 工具名稱 |
| `permissionPrompts` | `'host' \| 'none'` | `'host'` | 由誰回應權限提示：`'host'` 會將其路由到您的 [`canUseTool`](#canusetool) 回呼或 `permissionPromptToolName` 工具，而 `'none'` 會[拒絕原本會觸發提示的呼叫](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#how-permissions-are-evaluated)。需要 Claude Code v2.1.259 或更新版本 |
| `persistSession` | `boolean` | `true` | 設為 `false` 時，停用將工作階段持久化到磁碟。之後無法恢復工作階段 |
| `planModeInstructions` | `string` | `undefined` | plan mode 的自訂工作流程指令。當 `permissionMode` 為 `'plan'` 時，此字串會取代預設的 plan mode 工作流程主體。CLI 仍會以唯讀強制前言和 ExitPlanMode 協定結尾將其包覆 |
| `plugins` | [`SdkPluginConfig`](#sdkpluginconfig)`[]` | `[]` | 從本機路徑載入自訂外掛。詳情請參閱[外掛](https://code.claude.com/docs/zh-TW/agent-sdk/plugins.md) |
| `projectConfigRoot` | `string` | `undefined` | `cwd` 作為其 worktree 的受信任 checkout 的絕對路徑。Claude Code 會從此目錄而非 `cwd` 讀取專案設定、`.mcp.json`，以及專案 `.claude/` 中的命令、agent、skill、工作流程、routine 和輸出風格，並將 `CLAUDE_PROJECT_DIR` 設為此目錄。hook、`apiKeyHelper` 等輔助指令碼，以及 stdio MCP 伺服器都會以此目錄作為工作目錄啟動。`CLAUDE.md` 檔案和 `.claude/rules/` 仍從 `cwd` 載入。需要 Claude Code v2.1.275 或更新版本 |
| `promptSuggestions` | `boolean` | `false` | 啟用提示詞建議。每個回合結束後，Claude Code 會發出一則 `prompt_suggestion` 訊息，其中帶有預測的下一個使用者提示詞。某些回合 Claude Code 不會產生建議，例如當您的帳戶接近或已達用量上限時。請參閱[Claude Code 何時略過建議](https://code.claude.com/docs/zh-TW/interactive-mode.md#when-claude-code-skips-suggestions) |
| `resume` | `string` | `undefined` | 要恢復的工作階段 ID |
| `resumeDropsTurn` | `string` | `undefined` | 搭配 `resumeSessionAt`：截斷式恢復打算捨棄之回合的提示詞 UUID。當捨棄範圍內含有任何無法歸屬於該回合的內容（例如被吸收的佇列訊息或任務通知）時，Claude Code 會拒絕恢復，並在拒絕訊息中指出 `--resume-drops-turn` 旗標。只有 Agent SDK 和 print 模式的恢復會讀取這組設定。需要 Claude Code v2.1.223 或更新版本 |
| `resumeSessionAt` | `string` | `undefined` | 在特定訊息 UUID 處恢復工作階段 |
| `sandbox` | [`SandboxSettings`](#sandboxsettings) | `undefined` | 以程式方式設定沙箱行為。詳情請參閱[沙箱設定](#sandboxsettings) |
| `sessionId` | `string` | 自動產生 | 為工作階段使用特定的 UUID，而不是自動產生 |
| `sessionStore` | [`SessionStore`](https://code.claude.com/docs/zh-TW/agent-sdk/session-storage#the-sessionstore-interface) | `undefined` | 將工作階段逐字稿鏡像到外部後端，讓其他主機可以恢復它們。請參閱[將工作階段持久化到外部儲存空間](https://code.claude.com/docs/zh-TW/agent-sdk/session-storage.md) |
| `sessionStoreFlush` | `'batched' \| 'eager'` | `'batched'` | *Alpha。* `sessionStore` 的排清模式。未設定 `sessionStore` 時會忽略 |
| `settings` | `string \| Settings` | `undefined` | 內嵌的[設定](https://code.claude.com/docs/zh-TW/settings.md)物件、設定檔路徑或內嵌 JSON 字串。填入[優先順序](https://code.claude.com/docs/zh-TW/settings.md#settings-precedence)中的旗標設定層。可在執行時期以 [`applyFlagSettings()`](#applyflagsettings) 變更 |
| `settingSources` | [`SettingSource`](#settingsource)`[]` | CLI 預設值（所有來源） | 控制要載入哪些檔案系統設定。傳入 `[]` 可停用使用者、專案和本機設定。[端點受管政策](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)無論如何都會載入；當工作階段在[符合資格的設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md#platform-availability)上以組織憑證驗證時，會擷取伺服器受管設定。請參閱[使用 Claude Code 功能](https://code.claude.com/docs/zh-TW/agent-sdk/claude-code-features.md#what-settingsources-does-not-control) |
| `skills` | `string[] \| 'all'` | `undefined` | 工作階段可用的 skill。傳入 `'all'` 以啟用所有探索到的 skill，或傳入 skill 名稱清單。僅傳入確切名稱。在 Agent SDK v0.3.221 或更新版本中，SDK 會在啟動 Claude Code 程序之前以錯誤拒絕格式錯誤和萬用字元形式的名稱。設定此項時，SDK 會自動將 Skill 工具加入 `allowedTools`。若您同時傳入 `tools`，請在該清單中包含 `'Skill'`。請參閱 [Skills](https://code.claude.com/docs/zh-TW/agent-sdk/skills.md) |
| `spawnClaudeCodeProcess` | `(options: SpawnOptions) => SpawnedProcess` | `undefined` | 用於產生 Claude Code 程序的自訂函式。用於在 VM、容器或遠端環境中執行 Claude Code |
| `stderr` | `(data: string) => void` | `undefined` | stderr 輸出的回呼 |
| `strictMcpConfig` | `boolean` | `false` | 僅使用 `mcpServers` 中傳入的伺服器，並忽略專案 `.mcp.json`、使用者設定、外掛提供的 MCP 伺服器以及 [claude.ai 連接器](https://code.claude.com/docs/zh-TW/mcp.md#use-mcp-servers-from-claude-ai) |
| `systemPrompt` | `string \| string[] \| { type: 'custom'; prompt: string \| string[]; snapshot?: boolean } \| { type: 'preset'; preset: 'claude_code'; append?: string; excludeDynamicSections?: boolean; snapshot?: boolean }` | `undefined`（最簡提示詞） | 系統提示詞設定。傳入字串以使用自訂提示詞，或傳入 `{ type: 'preset', preset: 'claude_code' }` 以使用 Claude Code 的系統提示詞。傳入字串陣列，並在靜態部分與逐請求部分之間放置匯出的 `SYSTEM_PROMPT_DYNAMIC_BOUNDARY` 常數，即可[快取自訂提示詞的靜態部分](https://code.claude.com/docs/zh-TW/agent-sdk/modifying-system-prompts.md#cache-the-static-part-of-a-custom-prompt)。使用預設物件形式時，加入 `append` 以附加額外指令，並設定 `excludeDynamicSections: true` 將每個工作階段的上下文移至第一則使用者訊息，以[在不同機器間更好地重複使用提示詞快取](https://code.claude.com/docs/zh-TW/agent-sdk/modifying-system-prompts.md#improve-prompt-caching-across-users-and-machines)。設定 `snapshot: false` 可在每次請求時重新建構提示詞，而不是[重複使用工作階段在第一次請求時記錄的提示詞](https://code.claude.com/docs/zh-TW/agent-sdk/modifying-system-prompts.md#change-the-prompt-of-an-existing-session)。若要在自訂提示詞上設定 `snapshot`，請傳入 `{ type: 'custom', prompt }` 形式。`{ type: 'custom' }` 形式和 `snapshot` 欄位需要 TypeScript Agent SDK v0.3.257 或更新版本 |
| `taskBudget` | `{ total: number }` | `undefined` | *Alpha。* API 端的任務預算（以 token 計）。設定後，模型會被告知其剩餘的 token 預算，以便調整工具使用節奏並在達到上限前收尾 |
| `thinking` | [`ThinkingConfig`](#thinkingconfig) | 支援的模型為 `{ type: 'adaptive' }` | 控制 Claude 的思考／推理行為。選項請參閱 [`ThinkingConfig`](#thinkingconfig) |
| `title` | `string` | `undefined` | 工作階段的顯示標題。透過 `resume` 或 `continue` 恢復時，已恢復工作階段所持久化的標題優先；請使用 [`renameSession()`](#renamesession) 重新命名現有工作階段 |
| `toolAliases` | `Record<string, string>` | `undefined` | 將內建工具名稱對應到 MCP 工具名稱，讓 Claude 呼叫您的 MCP 實作來取代內建工具。例如 `{ Bash: 'mcp__workspace__bash' }` |
| `toolConfig` | [`ToolConfig`](#toolconfig) | `undefined` | 內建工具行為的設定。詳情請參閱 [`ToolConfig`](#toolconfig) |
| `tools` | `string[] \| { type: 'preset'; preset: 'claude_code' }` | `undefined` | 工具設定。傳入工具名稱陣列，或使用預設集以取得 Claude Code 的預設工具 |
| `verbatimPrompts` | `boolean` | `false` | 依原樣傳遞每個提示詞。SDK 會以 `client_composed: true` 傳送每則使用者訊息。關於 Claude Code 在這些訊息上會略過哪些處理，請參閱 [`client_composed`](#sdkusermessage)。當您的提示詞文字包含非終端使用者輸入的內容時，請使用此選項。若要逐回合控制，請保持關閉，並改為在個別串流訊息上設定 `client_composed`。需要 TypeScript Agent SDK v0.3.280 或更新版本以及 Claude Code v2.1.248 或更新版本；這些 SDK 版本隨附的 Claude Code 版本即符合 Claude Code 的需求 |

#### 處理緩慢或停滯的 API 回應

CLI 子程序會讀取數個控制 API 逾時和停滯偵測的環境變數。請透過 `env` 選項傳入它們：

```typescript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

const result = query({
  prompt: "Analyze this code",
  options: {
    env: {
      ...process.env,
      API_TIMEOUT_MS: "120000",
      CLAUDE_CODE_MAX_RETRIES: "2",
      CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS: "120000",
    },
  },
});
```

* [`API_TIMEOUT_MS`](https://code.claude.com/docs/zh-TW/env-vars)：每次請求嘗試可等待回應標頭的時間（毫秒）。它不會限制標頭抵達後串流回應的執行時間。預設為 `600000`。適用於主迴圈和所有 subagent。
* `CLAUDE_CODE_MAX_RETRIES`：API 重試的最大次數。預設為 `10`，上限為 `15`。每次重試都有自己的 `API_TIMEOUT_MS` 時間窗。

  對於需要撐過較長中斷時間的無人值守執行，請設定 [`CLAUDE_CODE_RETRY_WATCHDOG=1`](https://code.claude.com/docs/zh-TW/errors#tune-retry-behavior)：它會無限次重試暫時性的容量錯誤，且在 Claude Code v2.1.199 或更新版本中，會將其他暫時性錯誤的預設值提高到 `300`，並移除此變數的上限。
* `CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS`：subagent 的停滯監視器。當串流監視器開啟時，預設值為 `CLAUDE_STREAM_IDLE_TIMEOUT_MS` 加 5 分鐘，除非您提高該變數，否則為 `600000`。串流監視器關閉時，預設值為 `600000`。在 v2.1.257 之前，預設值一律為 `600000`。

  計時器會在每個串流事件時重設。發生停滯時，Claude Code 會中止該 subagent 並向上層回報停滯。對於背景 subagent，它也會將任務標記為失敗並附上任何部分結果。
* `CLAUDE_ENABLE_STREAM_WATCHDOG` 搭配 `CLAUDE_STREAM_IDLE_TIMEOUT_MS`：串流監視器，當標頭已抵達但回應主體停止串流時中止請求。此監視器對所有供應商預設開啟；設定 `CLAUDE_ENABLE_STREAM_WATCHDOG=0` 可將其停用。`CLAUDE_STREAM_IDLE_TIMEOUT_MS` 預設為 `300000`，且最小值會被限制為該值。中止後，Claude Code 會依據回應進行到的程度採取行動，詳見[自動重試](https://code.claude.com/docs/zh-TW/errors.md#automatic-retries)。

  當監視器在等待一個由 `ANTHROPIC_BASE_URL` 後方的閘道以 keep-alive ping 保持開啟的回應時，設定了 `includePartialMessages` 的主機會持續收到 `ping` [串流事件](#sdkpartialassistantmessage)，因此請將這些訊框視為存活訊號，而不要因靜默而讓工作階段逾時。在 v2.1.257 之前，這些訊框會在最後一個實際串流事件之後 5 分鐘停止。

### `Query` 物件

`query()` 函式傳回的介面。

```typescript theme={null}
interface Query extends AsyncGenerator<SDKMessage, void> {
  interrupt(): Promise<SDKControlInterruptResponse | undefined>;
  rewindFiles(
    userMessageId: string,
    options?: { dryRun?: boolean }
  ): Promise<RewindFilesResult>;
  setPermissionMode(mode: PermissionMode): Promise<void>;
  setModel(model?: string): Promise<void>;
  setMaxThinkingTokens(maxThinkingTokens: number | null): Promise<void>;
  applyFlagSettings(settings: {
    [K in keyof Settings]?: K extends 'effortLevel'
      ? 'low' | 'medium' | 'high' | 'xhigh' | 'max' | null
      : Settings[K] | null;
  }): Promise<void>;
  updateSettings(
    source: 'localSettings' | 'userSettings',
    settings: Record<string, unknown>,
  ): Promise<void>;
  initializationResult(): Promise<SDKControlInitializeResponse>;
  reinitialize(): Promise<SDKControlInitializeResponse>;
  supportedCommands(): Promise<SlashCommand[]>;
  supportedModels(): Promise<ModelInfo[]>;
  supportedAgents(): Promise<AgentInfo[]>;
  mcpServerStatus(): Promise<McpServerStatus[]>;
  getContextUsage(opts?: {
    detail?: 'summary' | 'full';
  }): Promise<SDKControlGetContextUsageResponse>;
  readFile(
    path: string,
    options?: { maxBytes?: number; encoding?: 'utf-8' | 'base64' }
  ): Promise<SDKControlReadFileResponse | null>;
  reloadPlugins(options?: {
    holdOnCacheImpact?: boolean;
    addPlugins?: SdkPluginConfig[];
  }): Promise<SDKControlReloadPluginsResponse>;
  reloadSkills(): Promise<SDKControlReloadSkillsResponse>;
  reloadOutputStyles(): Promise<SDKControlReloadOutputStylesResponse>;
  seedReadState(path: string, mtime: number): Promise<void>;
  accountInfo(): Promise<AccountInfo>;
  reconnectMcpServer(serverName: string): Promise<void>;
  toggleMcpServer(serverName: string, enabled: boolean): Promise<void>;
  setMcpServers(servers: Record<string, McpServerConfig>): Promise<McpSetServersResult>;
  setMcpPermissionModeOverride(
    serverName: string,
    mode: 'default' | 'auto' | null
  ): Promise<{ warning?: string }>;
  readMcpResource(serverName: string, uri: string): Promise<SDKControlMcpReadResourceResponse>;
  streamInput(stream: AsyncIterable<SDKUserMessage>): Promise<void>;
  stopTask(taskId: string): Promise<void>;
  backgroundTasks(toolUseId?: string): Promise<boolean>;
  close(): void;
}
```

#### 方法

| 方法 | 說明 |
| :- | :- |
| `interrupt()` | 中斷查詢。僅在串流輸入模式下可用。當 CLI 在 [`SDKSystemMessage.capabilities`](#sdksystemmessage) 中宣告 `interrupt_receipt_v1` 功能時，會以 [`SDKControlInterruptResponse`](#sdkcontrolinterruptresponse) 解析，其中列出中斷抵達時仍待處理的訊息。在 v2.1.205 之前的 CLI 上會解析為 `undefined` |
| `rewindFiles(userMessageId, options?)` | 將檔案還原到指定使用者訊息當時的狀態。傳入 `{ dryRun: true }` 以預覽變更。需要 `enableFileCheckpointing: true`。請參閱[檔案檢查點功能](https://code.claude.com/docs/zh-TW/agent-sdk/file-checkpointing.md) |
| `setPermissionMode()` | 變更權限模式（僅在串流輸入模式下可用） |
| `setModel()` | 變更模型（僅在串流輸入模式下可用）。傳入 `undefined` 或字串 `"default"` 會重設為 [Claude Code 的預設模型](https://code.claude.com/docs/zh-TW/model-config.md)。若新模型不支援自動模式，處於 `auto` 模式的工作階段會[變更為 `default` 模式](https://code.claude.com/docs/zh-TW/agent-sdk/permissions#auto-mode-auto) |
| `setMaxThinkingTokens()` | *已淘汰：* 請改用 `thinking` 選項。變更最大思考 token 數。傳入 `null` 會將思考重設為工作階段預設值：清除工作階段中途的覆寫，且對於已停用思考的工作階段，思考仍保持關閉 |
| `applyFlagSettings(settings)` | 在執行時期將設定合併到工作階段的旗標設定層（僅在串流輸入模式下可用）。請參閱 [`applyFlagSettings()`](#applyflagsettings) |
| `updateSettings(source, settings)` | 將一個允許清單中的鍵寫入專案的本機設定檔或您的使用者設定檔，讓該值在之後的工作階段中持續生效。請參閱 [`updateSettings()`](#updatesettings)。需要 TypeScript SDK v0.3.257 或更新版本，其隨附 Claude Code v2.1.257 |
| `initializationResult()` | 傳回完整的初始化結果，包括支援的命令、模型、帳戶資訊和輸出風格設定 |
| `reinitialize()` | 向執行中的 CLI 重新傳送 `initialize` 控制請求，並傳回新的結果，而不是快取的首次連線結果。在傳輸中斷之後使用，例如斷線後重新附加到工作階段，讓待處理的權限請求再次送達您的 `canUseTool` 回呼。請讓回呼對每個請求 ID 具有冪等性，因為回應遺失的請求會被再次派送。需要 Claude Code v2.1.195 或更新版本 |
| `supportedCommands()` | 傳回可用的命令。從 Agent SDK v0.3.216 起，此清單會反映工作階段中途的命令變更；請參閱 [`SDKCommandsChangedMessage`](#sdkcommandschangedmessage) |
| `supportedModels()` | 傳回可用的模型及顯示資訊 |
| `supportedAgents()` | 以 [`AgentInfo`](#agentinfo)`[]` 傳回可用的 subagent |
| `mcpServerStatus()` | 以 [`McpServerStatus`](#mcpserverstatus)`[]` 傳回已連線 MCP 伺服器的狀態 |
| `getContextUsage(opts?)` | 傳回 [`SDKControlGetContextUsageResponse`](#sdkcontrolgetcontextusageresponse)，依類別、skill 和工具細分工作階段的上下文視窗用量。使用預設的 `detail` 時，它包含 `/context` 在互動式工作階段中顯示的資料，這些資料是透過不會出現在訊息串流中的 token 計數 API 請求計算而得；請參閱[這些請求的處理方式](#sdkcontrolgetcontextusageresponse)。[`detail` 選項](#sdkcontrolgetcontextusageresponse)需要 Agent SDK v0.3.257 或更新版本 |
| `readFile(path, options?)` | 從工作階段的檔案系統讀取檔案。Claude Code 會以 `cwd` 為基準解析路徑；[`readFile()` 可以讀取的內容](#what-readfile-can-read)列出了它提供的檔案。傳入 `{ maxBytes }` 以變更讀取上限（預設 1 MB，最高 10 MB），對於圖片等二進位檔案則傳入 `{ encoding: 'base64' }`。會以 [`SDKControlReadFileResponse`](#sdkcontrolreadfileresponse) 解析，或在權限遭拒、檔案不存在或傳輸錯誤時解析為 `null`。需要 TypeScript SDK v0.2.121 或更新版本 |
| `reloadPlugins(options?)` | 從磁碟重新載入外掛，讓您在工作階段中途安裝或編輯的外掛能套用到執行中的工作階段。會以 [`SDKControlReloadPluginsResponse`](#sdkcontrolreloadpluginsresponse) 解析，其中列出工作階段的命令、subagent、外掛和 MCP 伺服器狀態。需要 Agent SDK v0.2.85 或更新版本。[`holdOnCacheImpact` 選項](#sdkcontrolreloadpluginsresponse)需要 Agent SDK v0.3.268 或更新版本。[`addPlugins` 選項](#load-more-plugin-folders-with-addplugins)需要 Agent SDK v0.3.301 或更新版本 |
| `reloadSkills()` | 從磁碟重新載入 skill，讓您在工作階段中途新增或編輯的 skill 可供執行中的工作階段使用。會以 [`SDKControlReloadSkillsResponse`](#sdkcontrolreloadskillsresponse) 解析，其中列出重新載入後可用的 skill。需要 Agent SDK v0.3.163 或更新版本 |
| `reloadOutputStyles()` | 從磁碟重新讀取[輸出風格](https://code.claude.com/docs/zh-TW/output-styles.md)，讓您在工作階段中途新增或編輯的風格檔案可供執行中的工作階段使用。會以 [`SDKControlReloadOutputStylesResponse`](#sdkcontrolreloadoutputstylesresponse) 解析，其中列出重新載入後可用的風格名稱。需要 Agent SDK v0.3.261 或更新版本 |
| `seedReadState(path, mtime)` | 將檔案標記為已讀取，讓之後的 Edit 不會因 `File has not been read yet` 而失敗。請參閱 [`seedReadState()`](#seedreadstate)。需要 TypeScript SDK v0.2.83 或更新版本 |
| `accountInfo()` | 傳回帳戶資訊 |
| `reconnectMcpServer(serverName)` | 依名稱重新連線 MCP 伺服器。若該名稱也符合 `.mcp.json` 或 `~/.claude.json` 等設定檔中的項目，Claude Code 會重新連線您透過 [`mcpServers`](#options) 或 `setMcpServers()` 設定的伺服器，而不是設定檔中的項目。此解析順序需要 Claude Code v2.1.257 或更新版本 |
| `toggleMcpServer(serverName, enabled)` | 依名稱啟用或停用 MCP 伺服器，名稱解析方式與 `reconnectMcpServer()` 相同。停用伺服器會中斷其連線並移除其工具。關於每種伺服器所需的 Claude Code 版本，請參閱 [`toggleMcpServer()`](#togglemcpserver) |
| `setMcpServers(servers)` | 取代此方法所管理的 MCP 伺服器：透過此方法新增的伺服器以及[同程序 SDK 伺服器](#createsdkmcpserver)。會以 [`McpSetServersResult`](#mcpsetserversresult) 解析，其中指出新增和移除了哪些伺服器以及任何錯誤；該章節也說明了哪些其他伺服器會保持連線 |
| `setMcpPermissionModeOverride(serverName, mode)` | 以比工作階段更嚴格的模式覆寫單一 MCP 伺服器工具的權限模式，或以 `null` 清除覆寫。僅在串流輸入模式下可用。請參閱 [`setMcpPermissionModeOverride()`](#setmcppermissionmodeoverride)。需要 TypeScript SDK v0.3.187 或更新版本 |
| `readMcpResource(serverName, uri)` | *Alpha。* 從已連線的 MCP 伺服器讀取一個 MCP Apps `ui://` 資源，讓您的應用程式能呈現工具的小工具。會以 [`SDKControlMcpReadResourceResponse`](#sdkcontrolmcpreadresourceresponse) 解析。需要 TypeScript Agent SDK v0.3.280 或更新版本 |
| `streamInput(stream)` | 將輸入訊息串流到查詢中以進行多回合對話 |
| `stopTask(taskId)` | 依 ID 停止執行中的背景任務 |
| `backgroundTasks(toolUseId?)` | 將該回合正在等待的執行中 Bash 命令和 subagent 移至背景，效果等同於在互動式終端機中按下 Ctrl+B。請參閱 [`backgroundTasks()`](#backgroundtasks)。需要 TypeScript SDK v0.2.139 或更新版本 |
| `close()` | 關閉查詢並終止底層程序。強制結束查詢並清理所有資源 |

#### `setMcpPermissionModeOverride()`

以比工作階段更嚴格的模式覆寫單一 MCP 伺服器工具的權限模式，或以 `null` 清除覆寫。當工作階段以略過逐項動作提示的模式執行，但某個伺服器的工具仍應受到審查時，請使用此方法。需要 TypeScript SDK v0.3.187 或更新版本。

傳入以下三個值之一作為 `mode`：

* `'default'`：Claude Code 會以與 [Manual 模式](https://code.claude.com/docs/zh-TW/permission-modes.md#available-modes)相同的方式評估該伺服器的工具呼叫。
* `'auto'`：Claude Code 會將該伺服器的工具呼叫交由[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)分類器處理。當分類器對工作階段不可用時，Claude Code 會拒絕此值。
* `null`：清除覆寫。

覆寫僅在工作階段處於略過逐項動作提示的模式（`bypassPermissions` 或 `auto`）時生效。在任何其他工作階段模式下，Claude Code 會忽略此覆寫，因此它永遠不會放寬工作階段允許的範圍。

當尚不知道該名稱的伺服器時，promise 會以 `{ warning }` 解析。Claude Code 仍會儲存此覆寫，並在具有完全相同名稱的伺服器連線後套用，因此此警告是用於檢查拼字錯誤，而非表示失敗。

僅在串流輸入模式下可用，限制與 `setModel()` 和 `setPermissionMode()` 相同。

#### `seedReadState()`

將檔案標記為已讀取，讓之後的 Edit 不會因 `File has not been read yet` 而失敗。當您的應用程式已從對話上下文中移除先前的 `Read` 結果，而 Claude 接下來將編輯該檔案時，請使用此方法。需要 TypeScript SDK v0.2.83 或更新版本。

將 `mtime` 傳入為先前讀取當下該檔案的修改時間，以自 epoch 起的整數毫秒表示，例如 `Math.floor(stat.mtimeMs)`。若磁碟上的檔案在該時間之後有所變更，Claude Code 會略過此標記。

無論檔案是否被標記，promise 都會解析，因此解析的 promise 無法告訴您實際發生了哪一種情況。

#### `backgroundTasks()`

將該回合正在等待的執行中 Bash 命令和 subagent 移至背景，效果等同於在互動式終端機中按下 Ctrl+B。傳入某個工具呼叫的 `toolUseId`，即可只將該呼叫所啟動的 Bash 命令或 subagent 移至背景；或省略它以將所有前景任務移至背景。需要 TypeScript SDK v0.2.139 或更新版本。

每個被移至背景的工具呼叫會立即以「正在背景執行」的結果返回給 Claude，回合會繼續進行，並在任務完成時由 Claude Code 發出 [`SDKTaskNotificationMessage`](#sdktasknotificationmessage)。

在已啟用背景任務的工作階段中，promise 會解析為布林值：

* **`true`**：已有任務被移至背景，或您省略了 `toolUseId`。
* **`false`**：您傳入的 `toolUseId` 沒有符合任何前景任務。

若工作階段已停用背景任務（例如透過 [`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS`](https://code.claude.com/docs/zh-TW/env-vars)），promise 則會被拒絕，且不會有任何任務被移至背景。

#### `applyFlagSettings()`

在不重新啟動查詢的情況下變更執行中工作階段的[設定](https://code.claude.com/docs/zh-TW/settings.md)。當沒有專用 setter 的設定需要在工作階段中途變更時使用，例如在 agent 讀取不受信任的輸入後收緊 `permissions`。`setModel()` 和 `setPermissionMode()` 是這兩個鍵的專用 setter；`applyFlagSettings()` 則是接受任意設定鍵子集的通用形式，在此傳入 `model` 的行為與 `setModel()` 相同。

只有部分鍵會在工作階段中途生效：

* **於下一個回合套用**：`ultracode`、`permissions`、`hooks`、`skillOverrides`、`fastMode`、`agent`。切換 `agent` 也會在下一個回合套用該 agent 的模型覆寫和 hook。其系統提示詞會在下一個回合套用。在[重複使用已記錄系統提示詞](https://code.claude.com/docs/zh-TW/agent-sdk/modifying-system-prompts.md#change-the-prompt-of-an-existing-session)的工作階段中，會在工作階段壓縮後套用。
* **在目前回合期間套用**：`model`。若您在 Claude 處理某個回合時切換 `model`，Claude 正在產生的回應會以舊模型完成，而該回合的其餘部分（從 Claude Code 對模型發出的下一次呼叫開始）會使用新模型。subagent 會保留自己的模型。在 v2.1.212 之前，回合中途的切換會等到下一個回合才生效。
* **最遲於下一個回合套用**：`effortLevel`。等級從 Claude Code 對模型的下一次呼叫開始套用。如果[變更 effort 會保留提示快取](https://code.claude.com/docs/zh-TW/prompt-caching.md#changing-effort-level)，例如在使用 API 金鑰或 Claude 訂閱的 Claude Opus 5.5 上，則預期會改為在下一個回合生效。
* **在工作階段中途無效**：系統提示詞選項。這些選項在啟動時只解析一次，因此即使呼叫成功，執行中的工作階段仍會保留原始值。若要變更它們，請啟動新的工作階段。

`effortLevel` 接受 [effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)名稱。它也接受 `"ultracode"`，這會在開啟 [ultracode](https://code.claude.com/docs/zh-TW/workflows.md#let-claude-decide-with-ultracode) 的情況下請求 `xhigh` effort。`applyFlagSettings()` 宣告 `effortLevel` 時未包含該值，因此在 TypeScript 中請傳入 `{ ultracode: true, effortLevel: "xhigh" }` 以獲得相同結果，或僅傳入 [`ultracode`](https://code.claude.com/docs/zh-TW/settings-reference#ultracode) 鍵，以在工作階段目前的 effort 等級下開啟 ultracode。`ultracode` 值需要 Claude Code v2.1.203 或更新版本，且只有 `applyFlagSettings()` 接受，設定檔中的 `effortLevel` 鍵不接受此值。在 v2.1.284 之前，單獨使用 `ultracode` 鍵也會將等級設為 `xhigh`。

這些值會寫入旗標設定層，並合併覆蓋在 `query()` 的內嵌 `settings` 選項於啟動時所設定的內容之上。這與[本頁優先順序章節](#settings-precedence)所稱的程式化選項是同一層級。`effortLevel` 是例外：您傳遞的等級會取代來自 `--effort` 或設定（包括受管設定）的等級，如 [effort 解析順序](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)所示。

連續呼叫會對頂層鍵進行淺層合併。第二次以 `{ permissions: {...} }` 呼叫時，會取代前一次呼叫的整個 `permissions` 物件，而不是深層合併進去。

若要清除您以 `applyFlagSettings()` 設定的鍵，請為該鍵傳入 `null`。大多數鍵接著會先退回到 `query()` 的 `settings` 選項於啟動時設定的值，再退回到優先順序較低的來源。清除的 `model` 會重設為 [Claude Code 的預設模型](https://code.claude.com/docs/zh-TW/model-config.md)，即使設定檔中設定了 `model` 也是如此。傳入 `undefined` 沒有效果，因為 JSON 序列化會將其捨棄。

除了 `model` 之外，還有三個鍵會重設工作階段狀態，而不是退回到其他值：

* `effortLevel: null` 會讓工作階段回到模型的預設 effort 等級，而不是 `query()` 的 `effort` 選項或設定檔中的 `effortLevel`。
* `agent: null` 會從下一個回合開始，讓主執行緒在沒有 agent 的情況下執行，而不是還原 `query()` 的 `agent` 選項或設定檔中的 `agent`。若被清除的 agent 曾套用自己的模型，工作階段會回到啟動時解析的模型。
* `ultracode: null` 會關閉 ultracode，效果與 `false` 相同，而不是還原設定檔中的 `ultracode` 值。工作階段會保留目前的 effort 等級，因此若要變更，請在同一次呼叫中傳入 `effortLevel`。

僅在串流輸入模式下可用，限制與 `setModel()` 和 `setPermissionMode()` 相同。

以下範例在工作階段中途切換作用中的模型，然後清除覆寫，讓模型重設為 [Claude Code 的預設模型](https://code.claude.com/docs/zh-TW/model-config.md)。

```typescript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

const q = query({ prompt: messageStream });

// Override the model for the rest of the session
await q.applyFlagSettings({ model: "claude-opus-4-6" });

// Later: clear the override; the model resets to Claude Code's default
await q.applyFlagSettings({ model: null });
```

> [!NOTE]
>
> `applyFlagSettings()` 僅適用於 TypeScript。Python SDK 並未提供對等的方法。

#### `updateSettings()`

將一個允許清單中的鍵寫入磁碟上的設定檔，讓該值在之後載入該來源的工作階段中持續生效。每個來源接受一個鍵，其值為字串：

* **`"localSettings"`**：接受 `outputStyle`，並將其合併到專案的本機設定檔 `.claude/settings.local.json`。新的風格會在工作階段的下一個請求生效。
* **`"userSettings"`**：接受 `effortLevel`，並將其儲存為工作階段目前模型的預設 [effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)，位於使用者設定檔的 [`modelSettings`](https://code.claude.com/docs/zh-TW/settings-reference#modelsettings) 之下。傳入 `max` 不會寫入任何內容，因為 `max` 僅限於工作階段。無論如何，執行中的工作階段都會保留目前的 effort 等級，因此若您也想變更它，請呼叫 [`applyFlagSettings()`](#applyflagsettings)。此來源需要 TypeScript SDK v0.3.277 或更新版本，其隨附 Claude Code v2.1.277。

當請求帶有任何其他鍵、工作階段透過遠端傳輸執行，或工作階段的 [`settingSources`](#options) 排除了您指定的來源時，呼叫會被拒絕。不支援刪除鍵。

#### `toggleMcpServer()`

停用伺服器會中斷其連線，並從工作階段中移除其工具。對於您在工作階段中途新增的伺服器以及同程序伺服器，這取決於您的 Claude Code 版本：

* 您在工作階段中途以 `setMcpServers()` 新增的 stdio、SSE 或 HTTP 伺服器：移除其工具需要 Claude Code v2.1.285 或更新版本。
* 您以 [`createSdkMcpServer()`](#createsdkmcpserver) 建立的同程序伺服器，無論您是透過 `mcpServers` 還是 `setMcpServers()` 傳入：中斷其連線並移除其工具需要 Claude Code v2.1.286 或更新版本。停用此類伺服器也會讓其仍在執行中的工具呼叫失敗，因此 Claude 會立即為每個呼叫收到錯誤結果，而不必等待您的處理常式返回。

### `WarmQuery`

由 [`startup()`](#startup) 傳回的控制代碼。子程序已經產生並初始化，因此在此控制代碼上呼叫 `query()` 會將提示詞直接寫入已就緒的程序，不會有啟動延遲。

```typescript theme={null}
interface WarmQuery extends AsyncDisposable {
  query(prompt: string | AsyncIterable<SDKUserMessage>): Query;
  close(): void;
}
```

#### 方法

| 方法 | 說明 |
| :- | :- |
| `query(prompt)` | 將提示詞傳送到預熱的子程序並傳回 [`Query`](#query-object)。每個 `WarmQuery` 只能呼叫一次 |
| `close()` | 在不傳送提示詞的情況下關閉子程序。用於捨棄不再需要的預熱查詢 |

`WarmQuery` 實作了 `AsyncDisposable`，因此可以搭配 `await using` 使用以自動清理。

### `SpareProcess`

*Alpha。* 由 [`prewarm()`](#prewarm) 傳回的控制代碼：一個已啟動但尚未綁定到工作階段、且只能被認領一次的 Claude Code 程序。需要 TypeScript Agent SDK v0.3.282 或更新版本。

```typescript theme={null}
interface SpareProcess extends AsyncDisposable {
  claim(params: {
    prompt: string | AsyncIterable<SDKUserMessage>;
    options: ClaimOptions;
  }): Query;
  readonly claimed: Promise<{ cwd: string; sessionId: string; parkedMs?: number; sdkMcpSettled: boolean }>;
  readonly exited: Promise<void>;
  close(): void;
}
```

#### 成員

| 成員 | 說明 |
| :- | :- |
| `claim({ prompt, options })` | 將備用程序綁定到 `options.cwd` 中的工作階段，並傳送其第一則訊息。與 `query()` 一樣同步傳回 [`Query`](#query-object)。只能呼叫一次 |
| `claimed` | 在 Claude Code 接受認領後，以工作階段的工作目錄和 ID 解析。當 Claude Code 拒絕認領、程序先行結束或被關閉時會被拒絕；當工作階段在沒有您要求的 `model` 或 `maxThinkingTokens` 的情況下執行時，也會以 `option_not_applied` 開頭的訊息被拒絕 |
| `exited` | 在程序結束時完成，無論是否已被認領。若備用程序在您認領前就結束，請予以替換 |
| `close()` | 終止程序。在認領之前呼叫會捨棄備用程序並拒絕 `claimed` |

`options.cwd` 為必要項目。認領時也可以設定 `additionalDirectories`、`model`、`permissionMode`、`maxThinkingTokens`、`settings` 中的旗標設定覆蓋層、`appendSystemPrompt`、`title`、`agents`，以及 `env` 中的每個工作階段 token。

Claude Code 可能會拒絕認領，例如對於不存在的資料夾，或專案設定中設定了 `env`、`agent` 或 `model` 的資料夾。遭拒後，`claim()` 已傳送的提示詞會收到文字以 `not_claimed` 開頭的錯誤結果，而傳回的查詢接著會擲出例外。請將查詢的迴圈包在 try 區塊中，以便在擲出例外後繼續執行。當 `claimed` 以 `option_not_applied` 開頭的訊息被拒絕時，表示工作階段正在沒有您要求的 `model` 或 `maxThinkingTokens` 的情況下執行。在任何其他拒絕之後，您的提示詞都尚未執行，因此請改用 `query()` 啟動工作階段。

### `SDKControlInitializeResponse`

`initializationResult()` 的傳回型別。包含工作階段初始化資料。

```typescript theme={null}
type SDKControlInitializeResponse = {
  commands: SlashCommand[];
  agents: AgentInfo[];
  output_style: string;
  available_output_styles: string[];
  models: ModelInfo[];
  account: AccountInfo;
  fast_mode_state?: "off" | "cooldown" | "on";
  fast_mode_disabled_reason?: FastModeDisabledReason;
  hooks_applied?: boolean;
  sdk_mcp_manifests_parked?: Record<
    string,
    | "parked"
    | "already_connected"
    | "protocol_version_mismatch"
    | "malformed"
    | "not_honoured"
  >;
  claude_code_version?: string;
};
```

`hooks_applied` 回報 Claude Code 是否註冊了 `initialize` 請求所帶的 `hooks`。SDK 會在工作階段啟動時傳送該請求一次，並在每次呼叫 [`reinitialize()`](#query-object) 時再次傳送。此欄位需要 Agent SDK v0.3.238 或更新版本。

當請求未帶任何 hook 時，Claude Code 會省略此欄位。當請求帶有 hook 時，其值取決於該請求是否為工作階段的第一次 initialize，以及若為重複的 initialize，則取決於它如何送達工作階段：

* `true`：Claude Code 註冊了這些 hook。工作階段的第一次 initialize 會傳回此值。透過 CLI 的 stdin 傳送的重複 initialize 也會傳回 `true`。在此情況下，新請求中的 hook 會取代先前註冊的 hook。
* `false`：Claude Code 忽略了這些 hook。傳送到遠端工作階段的重複 initialize 會傳回此值，因此加入工作階段的第二個用戶端無法取代第一個用戶端註冊的 hook。

在 Agent SDK v0.3.238 之前，回應從不帶有此欄位，且 Claude Code 在每次重複的 initialize 時都會忽略 `hooks`。

請求的 `sdkMcpServerManifests` 欄位和回應的 `sdk_mcp_manifests_parked` 欄位是供您以 [`createSdkMcpServer()`](#createsdkmcpserver) 建立的同程序 [SDK MCP 伺服器](https://code.claude.com/docs/zh-TW/agent-sdk/custom-tools.md)使用。您的應用程式不會設定或讀取這兩個欄位。

`claude_code_version` 是執行工作階段回合之程序的 Claude Code 版本。它與 [`SDKSystemMessage`](#sdksystemmessage) init 訊息所帶的值相同，因此您可以在第一個回合之前讀取 CLI 版本。

* 此欄位需要 Agent SDK v0.3.296 或更新版本，其隨附 Claude Code v2.1.296。
* 若此欄位為 `undefined` 且您設定了 `pathToClaudeCodeExecutable`，請將其指向 Claude Code v2.1.296 或更新版本。

回應一律會回報 `fast_mode_state`，而當有因素阻擋[快速模式](https://code.claude.com/docs/zh-TW/fast-mode.md)時，`fast_mode_disabled_reason` 會同時帶有原因代碼，讓您可以說明被阻擋的狀態，而不必重新推導可用性。這兩種行為都需要 Claude Code v2.1.219 或更新版本。在 v2.1.219 之前，當快速模式無法使用時，回應會省略 `fast_mode_state`，且從不帶有原因。關於原因代碼及其含義，請參閱結果訊息上的 [`fast_mode_disabled_reason`](#sdkresultmessage)。

成功的 `initialize` 的控制回應包裝器也帶有一個 `pending_permission_requests` 陣列。此欄位位於回應包裝器本身，而不在上方的 `SDKControlInitializeResponse` payload 中。每個項目都是一則完整的 `control_request` 訊息，其 `{ type: "control_request", request_id, request }` 形狀與工作階段在執行時為權限請求所串流的訊息相同。

此陣列列出這個 Claude Code 程序已發出但尚未解決的權限請求。SDK 會替您讀取此陣列，並將每個項目派送到您的 [`canUseTool`](#canusetool) 回呼，這與 [`reinitialize()`](#query-object) 在傳輸中斷後觸發的重新投遞相同。請以冪等方式處理重複的請求 ID，因為某個項目可能重複了回呼在連線中斷前已收到的請求。

此陣列一律存在於成功的 `initialize` 回應中，當此程序沒有未解決的權限請求時則為空陣列。需要 Claude Code v2.1.268 或更新版本。較早的版本可能會省略此欄位，因此若您自行解析傳輸協定，請將缺少此欄位視為較舊的 CLI，而不是沒有待處理項目的證明。

### `SDKControlInterruptResponse`

中斷回條：在 [`SDKSystemMessage.capabilities`](#sdksystemmessage) 中宣告 `interrupt_receipt_v1` 功能的 CLI 上，[`interrupt()`](#query-object) 所解析的值。需要 Claude Code v2.1.205 或更新版本。較早的 CLI 會以空的成功 payload 回應中斷，因此 `interrupt()` 會解析為 `undefined`。

```typescript theme={null}
type SDKControlInterruptResponse = {
  still_queued: string[];
  cancelled?: string[];
};
```

`still_queued` 列出中斷抵達時仍待處理之使用者訊息的 UUID：仍在佇列中的訊息，以及 Claude Code 已從佇列中取出準備用於下一個回合的任何訊息。一旦工作階段的第一個回合已經開始，除非您先取消，否則 Claude Code 會在中斷之後處理列出的訊息，且可能將多則訊息合併到一個回合中。若您在第一個回合開始之前中斷，Claude Code 會在該回合一開始就將其中止，該回合中列出的訊息不會得到回應。

請使用回條來決定是否要重新傳送任何內容。您未取消的列出訊息無論是否得到回應都會進入對話，因此重新傳送會讓 Claude 收到兩次。

解讀此清單時請注意以下事項：

* 只有以 UUID 加入佇列的訊息才會出現。空陣列並不代表沒有其他內容會執行。
* 只會列出主執行緒的訊息。傳送給 subagent 的訊息不在範圍內。
* 清單可能包含您的用戶端從未傳送過的 UUID，例如[工作階段範圍的排程任務](https://code.claude.com/docs/zh-TW/scheduled-tasks.md)觸發。請忽略您無法辨識的 UUID，而不要將其視為錯誤。

直接驅動 CLI 控制協定（而非透過 `interrupt()`）的用戶端，可以在 `interrupt` 控制請求上設定 `cancel_queued: true`。Claude Code v2.1.219 及更新版本會在 [`SDKSystemMessage.capabilities`](#sdksystemmessage) 中以 `interrupt_cancel_queued_v1` 功能宣告支援；較舊的 CLI 會忽略此欄位，並讓佇列中的訊息照常執行。這樣的中斷也會取消所有原本會列在 `still_queued` 下的訊息：回條會改將它們列在 `cancelled` 下，`still_queued` 為空，且這些訊息都不會執行。

`cancelled` 清單的注意事項與 `still_queued` 相同。`interrupt()` 方法從不傳送 `cancel_queued`，因此它所解析的回條不會帶有 `cancelled`。

回條是在處理中斷當下擷取的快照，在乾淨的中斷下，它會在被中斷回合的 [`SDKResultMessage`](#sdkresultmessage) 之前抵達。請讀取回條，而不要在該結果之後檢查佇列：迴圈會立即開始下一個佇列中的回合，因此您在結果之後檢查的佇列已經改變了。

### `SDKControlGetContextUsageResponse`

[`getContextUsage()`](#query-object) 的傳回型別。使用預設的 `detail` 時，回應會包含 Claude Code 在互動式工作階段中為 `/context` 命令呈現的 payload。除了 token 計數之外，該 payload 還帶有 `color` 和 `gridRows` 等顯示欄位，Claude Code 用它們來繪製 `/context` 用量格線。

此方法的選用 `detail` 引數用於選擇 Claude Code 如何計算各個類別。`detail` 引數需要 Agent SDK v0.3.257 或更新版本。

* **`'full'`**：預設值。Claude Code 會以 [token 計數](https://platform.claude.com/docs/en/build-with-claude/token-counting) API 請求計算每個類別。這些請求不會出現在訊息串流中，因此讀取串流的成本追蹤不會看到它們。在 Anthropic API 上，token 計數不收費。
* **`'summary'`**：傳入 `{ detail: 'summary' }` 以改從上一個回應的用量和本機估算取得答案。不會發出任何 token 計數請求，且各類別的數字為近似值。

當您以提示詞傳送 `/context` 而非呼叫此方法時，Claude Code 會將 [`SDKContextUsage`](#sdkcontextusage) payload 附加到傳遞結果之 assistant 訊息的 `context_usage` 欄位。該欄位需要 Agent SDK v0.3.232 或更新版本。

在 `SDKControlGetContextUsageResponse` 中，`categories[].id`、`mcpInstructions`，以及 `agents` 和 `skills.skillFrontmatter` 項目的 `pluginId` 和 `path` 欄位需要 Agent SDK v0.3.304 或更新版本。

```typescript theme={null}
type SDKControlGetContextUsageResponse = {
  categories: {
    id?:
      | "system_prompt"
      | "system_tools"
      | "mcp_tools"
      | "mcp_instructions"
      | "mcp_tools_deferred"
      | "system_tools_deferred"
      | "custom_agents"
      | "memory_files"
      | "skills"
      | "messages"
      | "autocompact_buffer"
      | "compact_buffer"
      | "free_space";
    name: string;
    tokens: number;
    color: string;
    isDeferred?: boolean;
    kind: "used" | "free" | "buffer" | "deferred";
  }[];
  totalTokens: number;
  maxTokens: number;
  rawMaxTokens: number;
  percentage: number;
  gridRows: {
    color: string;
    isFilled: boolean;
    categoryName: string;
    tokens: number;
    percentage: number;
    squareFullness: number;
  }[][];
  model: string;
  memoryFiles: {
    path: string;
    type: string;
    tokens: number;
  }[];
  mcpTools: {
    name: string;
    serverName: string;
    tokens: number;
    isLoaded?: boolean;
  }[];
  mcpInstructions?: {
    serverName: string;
    tokens: number;
  }[];
  deferredBuiltinTools?: {
    name: string;
    tokens: number;
    isLoaded: boolean;
  }[];
  systemTools?: {
    name: string;
    tokens: number;
  }[];
  systemPromptSections?: {
    name: string;
    tokens: number;
  }[];
  agents: {
    agentType: string;
    source: string;
    pluginId?: string;
    path?: string;
    tokens: number;
  }[];
  slashCommands?: {
    totalCommands: number;
    includedCommands: number;
    tokens: number;
  };
  skills?: {
    totalSkills: number;
    includedSkills: number;
    tokens: number;
    skillFrontmatter: {
      name: string;
      source: string;
      pluginName?: string;
      pluginId?: string;
      path?: string;
      tokens: number;
    }[];
  };
  autoCompactThreshold?: number;
  isAutoCompactEnabled: boolean;
  messageBreakdown?: {
    toolCallTokens: number;
    toolResultTokens: number;
    attachmentTokens: number;
    assistantMessageTokens: number;
    userMessageTokens: number;
    redirectedContextTokens: number;
    unattributedTokens: number;
    toolCallsByType: {
      name: string;
      callTokens: number;
      resultTokens: number;
    }[];
    attachmentsByType: {
      name: string;
      tokens: number;
    }[];
  };
  apiUsage: {
    input_tokens: number;
    output_tokens: number;
    cache_creation_input_tokens: number;
    cache_read_input_tokens: number;
  } | null;
};
```

從集合欄位讀取 token 歸屬：

* `categories` 保存各類別的總計。每個項目的 `kind` 以與 [`SDKContextUsageCategory`](#sdkcontextusagecategory) 相同的值對該列進行分類。請依據它而非顯示用的 `name` 來分類各列。此欄位需要 Agent SDK v0.3.268 或更新版本。
* `mcpTools` 和 `agents` 將 token 歸屬到個別的 MCP 工具和 subagent。
* `memoryFiles` 列出每個已載入的記憶檔案及其成本。
* `skills.skillFrontmatter` 將 skill 清單的 token 歸屬到每個包含的 skill。每個 skill 的計數衡量的是 Claude Code 實際傳送的 skill 清單項目，可能比該 skill 的完整 frontmatter 更短。比較 `skills.totalSkills` 與 `skills.includedSkills`，即可查看是否所有探索到的 skill 都進入了清單。

`totalTokens` 是工作階段目前的上下文用量，`maxTokens` 則是衡量該用量所依據的視窗。該視窗是模型的上下文視窗，或在適用時為較低的自動壓縮視窗。`rawMaxTokens` 帶有與 `maxTokens` 相同的值，而 `percentage` 是 `totalTokens` 佔該視窗的四捨五入百分比。`apiUsage` 保存最近一次 API 回應的用量，而不是工作階段的累計總額。

Claude Code 不會設定選用的 `deferredBuiltinTools`、`systemTools` 和 `systemPromptSections` 診斷欄位，因此即使型別宣告了它們，也請預期它們不存在。

#### 依 ID 尋找列、伺服器的指令 token，或項目的外掛與檔案

MCP 伺服器指令是已連線伺服器提供、並由 Claude Code 加入上下文的使用說明，而 `categories` 的 `mcp_instructions` 列會計算它們的 token。使用以下 [`getContextUsage()`](#query-object) 欄位，可依 `id` 挑出單一 `categories` 列、依伺服器拆分 `mcp_instructions` 的 token，或找出 agent 或 skill 項目背後的外掛與檔案：

| 欄位 | 所在位置 | 內容 |
| :- | :- | :- |
| `id` | 每個 `categories` 列 | 該列的識別碼，為[回應型別](#sdkcontrolgetcontextusageresponse)所列的值之一，例如 `mcp_instructions`。依 `id` 比對以挑出單一列，或依 `kind` 比對以將各列分組。較新的 Claude Code 版本可能會傳送您已安裝型別中未列出的值，因此請將無法辨識的 `id` 視為不存在 |
| `mcpInstructions` | 回應 | 每個提供指令的已連線 MCP 伺服器各有一個 `{ serverName, tokens }` 項目，若沒有任何伺服器提供則為空陣列。`tokens` 值為估算值，加總起來等於 `mcp_instructions` 列的 `tokens`。`serverName` 是 [`mcpServerStatus()`](#query-object) 為該伺服器回報的 `name` |
| `pluginId` | `agents` 和 `skills.skillFrontmatter` 項目 | 以 `name@marketplace` 形式的 ID 指出該項目來自哪個外掛；對於不是來自外掛的項目則不存在。當外掛不是來自市集時，`@` 之後的部分改為指出[其來源](https://code.claude.com/docs/zh-TW/plugins/loading.md#find-where-a-plugin-came-from)，例如透過 [`plugins`](#options) 選項載入的外掛為 `inline` |
| `path` | `agents` 和 `skills.skillFrontmatter` 項目 | 定義該 agent 或 skill 之檔案的絕對路徑，位於執行 Claude Code 的機器上。當沒有檔案定義該項目時（例如來自 [`agents`](#options) 選項的 agent 或 Claude Code 內建的 skill），此欄位不存在 |

以依 `id` 比對為例，以下範例會找出 `mcp_instructions` 列：

```typescript theme={null}
// q is the Query object that query() returned
const usage = await q.getContextUsage();
// undefined if no connected server supplies instructions
const row = usage.categories.find((c) => c.id === "mcp_instructions");
```

### `SDKControlReadFileResponse`

[`readFile()`](#query-object) 的回傳型別。

```typescript theme={null}
type SDKControlReadFileResponse = {
  contents: string;
  absPath: string;
  truncated?: boolean;
  encoding?: 'base64';
};
```

`contents` 存放檔案文字，或在您請求 `encoding: 'base64'` 時存放 base64 資料；在此情況下，回應的 `encoding` 欄位會設為 `'base64'`。`absPath` 是解析後的絕對路徑。當檔案長度超過 `maxBytes` 上限且內容在該限制處被截斷時，會設定 `truncated`。

#### `readFile()` 可以讀取的內容

`readFile()` 提供的檔案範圍比 Read 工具更窄：

* 位於工作階段某個工作目錄（例如 `cwd` 和 `additionalDirectories`）內的一般檔案
* 該工作階段中 Claude Code 本身的少數檔案，例如工具結果

`Read` 的拒絕與詢問規則仍會封鎖相符的路徑，而廣泛的 `Read` 允許規則並不會讓 `readFile()` 存取檔案系統的其餘部分。對於其他任何內容，呼叫會以 `null` 解析。

### `SDKControlReloadPluginsResponse`

[`reloadPlugins()`](#query-object) 的回傳型別。

```typescript theme={null}
type SDKControlReloadPluginsResponse = {
  commands: SlashCommand[];
  agents: AgentInfo[];
  plugins: {
    name: string;
    path: string;
    source?: string;
    version?: string;
  }[];
  mcpServers: McpServerStatus[];
  error_count: number;
  held?: boolean;
  cache_impact?: {
    mcp_servers_added: string[];
    mcp_servers_removed: string[];
    lsp_tool_change: ("adds" | "may-add" | "removes" | "may-remove") | null;
  };
};
```

集合欄位描述呼叫後的工作階段狀態：

* `commands`、`agents` 和 `mcpServers`：工作階段的命令、subagent 和 MCP 伺服器狀態，其形狀與 `supportedCommands()`、`supportedAgents()` 和 `mcpServerStatus()` 的回傳相同。`supportedAgents()` 會持續回傳初始化時擷取的清單，因此若要取得重新載入後的集合，請讀取此處的 `agents`
* `plugins`：每個已載入的外掛及其 `name` 和安裝 `path`。`version` 重複外掛 manifest 所宣告的內容，且由外掛作者控制，因此在信任它之前請先驗證。當 manifest 未宣告時則省略
* `error_count`：載入外掛時發生的錯誤數量

將 `{ holdOnCacheImpact: true }` 傳給 `reloadPlugins()`，即可暫緩會使對話的提示快取失效的重新載入，而不是套用它。Claude Code 會執行互動式 `/reload-plugins` 命令在[警告快取成本](https://code.claude.com/docs/zh-TW/prompt-caching.md#enabling-or-disabling-a-plugin)之前所做的檢查。此選項需要 Agent SDK v0.3.268 或更新版本。早於 v2.1.268 的 Claude Code 執行檔（例如您以 `pathToClaudeCodeExecutable` 指定的執行檔）會忽略此選項並套用重新載入。

傳入此選項時，請讀取 `held` 以了解發生了什麼：

* `true`：未套用重新載入，集合欄位描述的是工作階段目前的狀態。`cache_impact` 說明套用後會改變什麼。若仍要套用，請不帶此選項再次呼叫 `reloadPlugins()`。
* `false`：檢查發現沒有快取影響，並已套用重新載入。
* 不存在：您未傳入此選項，或 Claude Code 執行檔早於 v2.1.268 並已套用重新載入。

`cache_impact` 只會與 `held: true` 一起出現。`mcp_servers_added` 和 `mcp_servers_removed` 以帶範圍的 `plugin:<plugin>:<server>` 名稱列出重新載入會註冊或移除的外掛 MCP 伺服器。這些名稱由外掛作者撰寫，因此在顯示之前請先驗證。`lsp_tool_change` 說明套用後是否會新增或移除 LSP 工具，若兩者皆否則為 `null`。`may-` 形式表示檢查無法完整看見待處理的外掛集合。

#### 使用 `addPlugins` 載入更多外掛資料夾

若要載入啟動時不在 [`plugins`](#options) 選項中的外掛資料夾，請將它們以 `addPlugins` 傳給 `reloadPlugins()`，這是一個 [`SdkPluginConfig`](#sdkpluginconfig) 項目清單，其 `path` 為絕對路徑。Claude Code 會在單次處理中載入新資料夾並重新載入工作階段現有的外掛。每個新增外掛的 MCP 伺服器也會連線，除非您在該資料夾的項目上設定 [`skipMcpDiscovery`](#sdkpluginconfig)。需要 Agent SDK v0.3.301 或更新版本，以及 Claude Code v2.1.301 或更新版本。

此範例將一個資料夾新增到執行中的查詢 `q`，並在呼叫回傳時印出工作階段已載入的每個外掛的安裝路徑：

```typescript theme={null}
const result = await q.reloadPlugins({
  addPlugins: [{ type: "local", path: "/opt/my-app/plugins/reports" }]
});

console.log(result.plugins.map((plugin) => plugin.path));
```

如果資料夾已載入，印出的清單會包含 `/opt/my-app/plugins/reports`，且該外掛的命令和 subagent 會出現在 `result.commands` 和 `result.agents` 中。

新增的資料夾會持續成為工作階段的一部分。當您再次呼叫 `reloadPlugins()` 時，Claude Code 會將它與其他外掛一起重新載入，您不需要再次在 `addPlugins` 中傳入它。

##### 當 `reloadPlugins()` 未載入 `addPlugins` 資料夾時

如果 `reloadPlugins()` 被拒絕，則不會新增任何 `addPlugins` 資料夾，因此重試時請再次在 `addPlugins` 中傳入它們。當拒絕是由以下原因之一造成時，工作階段會保留它原本已有的外掛：

* **相對的 `path` 或格式錯誤的項目**：錯誤訊息為 `add_plugins must be a list of { type: "local", path } entries with absolute paths`。Claude Code 會因為一個錯誤項目而拒絕整個清單，因此請將每個項目都以 `{ type: "local", path }` 傳入，並使用絕對 `path`
* **管理員已在您的受管設定中開啟 [`disableSideloadFlags`](https://code.claude.com/docs/zh-TW/settings-reference#disablesideloadflags)**：訊息為 `reload_plugins add_plugins is disabled by managed settings (disableSideloadFlags)`。若要載入該資料夾，請要求該管理員移除此設定
* **無法重建[沙箱](https://code.claude.com/docs/zh-TW/sandboxing.md)**：在[沙箱機制](#sandboxsettings)開啟時，Claude Code 會重建沙箱設定，使沙箱化的 shell 命令無法寫入您新增的資料夾。訊息為 `the sandbox could not be rebuilt to keep shell commands out of this folder`。請檢查您的[沙箱設定](#sandboxsettings)是否仍構成有效的設定

如果您傳入 `holdOnCacheImpact` 且呼叫以 [`held: true`](#sdkcontrolreloadpluginsresponse) 解析，則不會新增 `addPlugins` 資料夾。若仍要新增，請使用相同的 `addPlugins` 清單且不帶 `holdOnCacheImpact` 再次呼叫 `reloadPlugins()`。

當呼叫未以 `held: true` 解析，但某個資料夾仍未出現在 `result.plugins` 中時，請先檢查以下原因：

* **資料夾不存在或其外掛載入失敗**：`result.error_count` 為 `1` 或更高。即使如此，該資料夾仍會是工作階段的一部分。修正資料夾後，請再次呼叫 `reloadPlugins()` 以載入它，這次不需要在 `addPlugins` 中列出它
* **Claude Code 執行檔早於 v2.1.301**：早於 v2.1.301 的執行檔會忽略 `addPlugins`，只重新載入工作階段原本已有的外掛。請檢查 [init 訊息](#sdksystemmessage)上的 `claude_code_version`，並執行 v2.1.301 或更新版本的執行檔

### `SDKControlReloadSkillsResponse`

[`reloadSkills()`](#query-object) 的回傳型別。

```typescript theme={null}
type SDKControlReloadSkillsResponse = {
  skills: SlashCommand[];
};
```

`skills` 列出重新載入後可用的 skill，其 [`SlashCommand`](#slashcommand) 形狀與 `supportedCommands()` 的回傳相同。

### `SDKControlReloadOutputStylesResponse`

[`reloadOutputStyles()`](#query-object) 的回傳型別。

```typescript theme={null}
type SDKControlReloadOutputStylesResponse = {
  available_output_styles: string[];
};
```

`available_output_styles` 列出重新載入後可用的內建與自訂輸出風格名稱。

### `SDKControlMcpReadResourceResponse`

[`readMcpResource()`](#query-object) 的回傳型別，攜帶 MCP 伺服器的 `resources/read` 結果。需要 TypeScript Agent SDK v0.3.280 或更新版本。

```typescript theme={null}
type SDKControlMcpReadResourceResponse = {
  contents: {
    uri: string;
    mimeType?: string;
    text?: string;
    blob?: string;
    _meta?: Record<string, unknown>;
  }[];
};
```

請將 `mcpServerStatus()` 所回報的伺服器名稱以及一個 `ui://` URI 傳給 `readMcpResource()`，例如工具在其 [`_meta`](#mcpserverstatus) 中宣告的 `ui.resourceUri`。對於任何其他 URI 配置、由您的應用程式自行託管的 [SDK MCP 伺服器](#createsdkmcpserver)，以及未連線的伺服器，呼叫都會被拒絕。當 init 訊息的 [`capabilities`](#sdksystemmessage) 包含 `mcp_read_resource_v1` 時即可使用。

每個 `contents` 項目都是伺服器傳送的一個內容項目，但會移除 `com.anthropic/` 前綴下的任何 `_meta` 鍵，該前綴保留給 Claude Code 使用。`blob` 存放二進位項目的 base64 資料，而 `_meta` 是該項目本身的 `_meta`，MCP Apps 伺服器會在其中放置資源的 `ui.csp` 和 `ui.permissions`。

這些內容是不受信任的第三方 HTML，因此請在沙箱中呈現它們。

### `AgentDefinition`

以程式方式定義的 subagent 設定。

```typescript theme={null}
type AgentDefinition = {
  description: string;
  tools?: string[];
  disallowedTools?: string[];
  prompt: string;
  model?: string;
  mcpServers?: AgentMcpServerSpec[];
  skills?: string[];
  initialPrompt?: string;
  maxTurns?: number;
  autoCompactWindow?: number;
  background?: boolean;
  omitClaudeMd?: boolean;
  memory?: "user" | "project" | "local";
  effort?: "low" | "medium" | "high" | "xhigh" | "max" | number;
  permissionMode?: PermissionMode;
  criticalSystemReminder_EXPERIMENTAL?: string;
};
```

| 欄位 | 必要 | 說明 |
| :- | :- | :- |
| `description` | 是 | 以自然語言描述何時使用此 agent |
| `tools` | 否 | 允許的工具名稱陣列。若省略，則繼承所有[可供 subagent 使用的工具](https://code.claude.com/docs/zh-TW/sub-agents.md#available-tools)。若要將 Skills 預先載入 agent 的上下文，請使用 `skills` 欄位，而不是在此列出 `'Skill'` |
| `disallowedTools` | 否 | 要為此 agent 明確禁止的工具名稱陣列。也接受 MCP 伺服器層級的模式：`mcp__server` 或 `mcp__server__*` 會移除該伺服器的所有工具，而 `mcp__*` 會移除任何伺服器的所有 MCP 工具 |
| `prompt` | 是 | agent 的系統提示詞 |
| `model` | 否 | 此 agent 的模型覆寫。接受別名，例如 `'fable'`、`'opus'`、`'sonnet'`、`'haiku'`、`'inherit'`，或完整的模型 ID。`'inherit'` 使用主模型。省略時，Claude Code 會依照 [subagent 模型順序](https://code.claude.com/docs/zh-TW/sub-agents.md#choose-a-model)選擇模型 |
| `mcpServers` | 否 | 此 agent 的 MCP 伺服器規格 |
| `skills` | 否 | 要預先載入 agent 上下文的 skill 名稱陣列 |
| `initialPrompt` | 否 | 當此 agent 作為主執行緒 agent 執行時，會自動提交為第一個使用者回合 |
| `maxTurns` | 否 | 停止前的最大 agentic 回合數（API 往返次數） |
| `autoCompactWindow` | 否 | 當此 agent 作為 subagent 執行時，將其[自動壓縮視窗](https://code.claude.com/docs/zh-TW/sub-agents.md#subagent-auto-compact-window)降低至 `100000` 到 `1000000` 的 token 數。需要 TypeScript Agent SDK v0.3.296 或更新版本 |
| `background` | 否 | 被叫用時，將此 agent 作為非阻塞的背景任務執行 |
| `omitClaudeMd` | 否 | 將使用者、專案和本機 CLAUDE.md 檔案排除在此 agent 的初始上下文之外；受管政策檔案仍會載入。適用於從 Agent 工具提示詞取得所需一切的 agent。當此 agent 作為主執行緒 agent 執行時會被忽略。需要 TypeScript Agent SDK v0.3.271 或更新版本 |
| `memory` | 否 | 此 agent 的記憶來源：`'user'`、`'project'` 或 `'local'` |
| `effort` | 否 | 此 agent 的推理 effort 等級。接受具名等級或整數 |
| `permissionMode` | 否 | 此 agent 內工具執行的權限模式。由 [subagent 繼承規則](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#available-modes)決定何時套用。請參閱 [`PermissionMode`](#permissionmode) |
| `criticalSystemReminder_EXPERIMENTAL` | 否 | 實驗性：加入系統提示詞的關鍵提醒 |

### `AgentMcpServerSpec`

指定 subagent 可用的 MCP 伺服器。可以是伺服器名稱（參照父層 `mcpServers` 設定中伺服器的字串），或是將伺服器名稱對應到設定的內嵌伺服器設定記錄。

```typescript theme={null}
type AgentMcpServerSpec = string | Record<string, McpServerConfigForProcessTransport>;
```

其中 `McpServerConfigForProcessTransport` 為 `McpStdioServerConfig | McpSSEServerConfig | McpHttpServerConfig | McpSdkServerConfig`。

### `SettingSource`

控制 SDK 從哪些基於檔案系統的設定來源載入設定。

```typescript theme={null}
type SettingSource = "user" | "project" | "local";
```

| 值 | 說明 | 位置 |
| :- | :- | :- |
| `'user'` | 全域使用者設定 | `~/.claude/settings.json` |
| `'project'` | 共享的專案設定（納入版本控制） | `.claude/settings.json` |
| `'local'` | 本機專案設定，當 Claude Code 將設定儲存至其中時會加入 gitignore | `.claude/settings.local.json` |

#### 預設行為

當 `settingSources` 被省略或為 `undefined` 時，`query()` 會載入與 Claude Code CLI 相同的檔案系統設定：使用者、專案和本機。關於無論此選項為何都會讀取的輸入以及如何停用它們，請參閱 [settingSources 不控制的內容](https://code.claude.com/docs/zh-TW/agent-sdk/claude-code-features.md#what-settingsources-does-not-control)。

#### 為何使用 settingSources

**停用檔案系統設定：**

```typescript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

// Do not load user, project, or local settings from disk
const result = query({
  prompt: "Analyze this code",
  options: { settingSources: [] }
});
```

**僅載入特定的設定來源：**

```typescript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

// Load only project settings, ignore user and local
const result = query({
  prompt: "Run CI checks",
  options: {
    settingSources: ["project"] // Only .claude/settings.json
  }
});
```

若要載入 CLAUDE.md 專案指令，請在 `settingSources` 中包含 `"project"`。關於 CLAUDE.md 載入如何與系統提示詞選項互動，請參閱[修改系統提示詞](https://code.claude.com/docs/zh-TW/agent-sdk/modifying-system-prompts.md#claude-md-files-for-project-level-instructions)。

#### 設定優先順序

當載入多個來源時，設定會依下列優先順序合併（由高至低）：

1. 本機設定（`.claude/settings.local.json`）
2. 專案設定（`.claude/settings.json`）
3. 使用者設定（`~/.claude/settings.json`）

`agents`、`allowedTools` 與 `settings` 等程式化選項會覆寫使用者、專案與本機檔案系統設定。若受管政策設定與程式化選項設定了相同的鍵，則套用受管值，但有例外，例如傳給 [`applyFlagSettings()`](#applyflagsettings) 的 `effortLevel`。

### `PermissionMode`

```typescript theme={null}
type PermissionMode =
  | "default" // Standard permission behavior
  | "acceptEdits" // Auto-accept file edits
  | "bypassPermissions" // Bypass permission checks; explicit ask rules still prompt
  | "plan" // Planning mode - explore without editing
  | "dontAsk" // Don't prompt for permissions, deny if not pre-approved
  | "auto"; // A model classifier reviews actions such as shell commands and network requests
```

### `CanUseTool`

用於控制工具使用的自訂權限函式型別。

此函式是 SDK 對互動式權限提示的替代：只有在[權限評估流程](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#how-permissions-are-evaluated)解析為提示時才會被叫用。已由 `allowedTools` 項目、設定中的允許規則或權限模式（例如 `acceptEdits` 或 `bypassPermissions`）核准的工具呼叫，永遠不會叫用它。若要把關每一個工具呼叫，請改用 [`PreToolUse` hook](https://code.claude.com/docs/zh-TW/agent-sdk/hooks)。

允許規則不會預先核准[任何模式都不會自動核准的動作](https://code.claude.com/docs/zh-TW/permission-modes.md#actions-no-mode-auto-approves)；關於其中哪些會到達回呼，以及在 `dontAsk` 和 `auto` 模式下會發生什麼，請參閱[權限如何評估](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#how-permissions-are-evaluated)。

```typescript theme={null}
type CanUseTool = (
  toolName: string,
  input: Record<string, unknown>,
  options: {
    signal: AbortSignal;
    suggestions?: PermissionUpdate[];
    blockedPath?: string;
    mcpServer?: { name: string; source: string };
    decisionReason?: string;
    defaultToNo?: boolean;
    suppressAlwaysAllowRule?: boolean;
    toolUseID: string;
    agentID?: string;
    requestId: string;
  }
) => Promise<PermissionResult | null>;
```

| 選項 | 型別 | 說明 |
| :- | :- | :- |
| `signal` | `AbortSignal` | 若操作應中止則會發出訊號 |
| `suggestions` | [`PermissionUpdate`](#permissionupdate)`[]` | 建議的權限更新，讓使用者不會再次被詢問此工具。Bash 提示包含一個 `localSettings` [目的地](#permissionupdatedestination)的建議，因此在 `updatedPermissions` 中回傳它會將規則寫入 `.claude/settings.local.json`，並跨工作階段保留。 |
| `blockedPath` | `string` | 觸發權限請求的檔案路徑（如適用） |
| `mcpServer` | `{ name: string; source: string }` | 對於 `mcp__*` 工具，提供該工具的 MCP 伺服器及該伺服器定義的來源，欄位與 [`McpServerProvenance`](#mcpserverprovenance) 相同。其他工具則不存在。需要 Agent SDK v0.3.274 或更新版本 |
| `decisionReason` | `string` | 說明為何觸發此權限請求 |
| `defaultToNo` | `boolean` | 當為 `true` 時，單一誤觸的按鍵不得核准此請求：請讓您的提示停在拒絕選項上、不要預先選取核准，也不要提供單鍵核准的快捷鍵。需要 Agent SDK v0.3.268 或更新版本 |
| `suppressAlwaysAllowRule` | `boolean` | 當為 `true` 時，不要為此請求提供持續性的「永遠允許」選項。需要 Agent SDK v0.3.268 或更新版本 |
| `toolUseID` | `string` | 助理訊息中此特定工具呼叫的唯一識別碼 |
| `agentID` | `string` | 若在 sub-agent 中執行，則為該 sub-agent 的 ID |
| `requestId` | `string` | `control_request` 封包的 `request_id`。您的應用程式在 SDK 之外傳送的 `control_response`（例如已簽署的 HTTP POST）必須回傳此值，Claude Code 程序才能將回覆與請求配對 |

回呼通常透過回傳 [`PermissionResult`](#permissionresult) 來解決請求，SDK 會將其作為 `control_response` 透過其傳輸寫回。只有在您的應用程式已透過自己的管道為此請求傳送 `control_response`（並回傳 `requestId`）時，才回傳 `null`；SDK 隨後會略過將回應寫入其傳輸。在任何其他情況下回傳 `null`，都會使工具呼叫無限期封鎖，因為永遠不會傳送 `control_response`，且權限提示不會逾時。

`requestId` 選項和 `null` 回傳值需要 Claude Code v2.1.199 或更新版本。

### `PermissionResult`

權限檢查的結果。

```typescript theme={null}
type PermissionResult =
  | {
      behavior: "allow";
      updatedInput?: Record<string, unknown>;
      updatedPermissions?: PermissionUpdate[];
      toolUseID?: string;
    }
  | {
      behavior: "deny";
      message: string;
      interrupt?: boolean;
      toolUseID?: string;
    };
```

如果您回傳 `allow` 且 `updatedPermissions` 中有超過 4,096 個項目，Claude Code 會將結果視為無效並拒絕該工具呼叫。每個更新計為一個項目，其 `rules` 或 `directories` 清單中的每個條目也各計為一個項目。拒絕訊息的結尾為 `updatedPermissions may hold at most 4096 updates, rules and directories in all.` 若要讓呼叫被允許，請回傳 4,096 個或更少的項目。

### `ToolConfig`

內建工具行為的設定。

```typescript theme={null}
type ToolConfig = {
  askUserQuestion?: {
    previewFormat?: "markdown" | "html";
  };
};
```

| 欄位 | 型別 | 說明 |
| :- | :- | :- |
| `askUserQuestion.previewFormat` | `'markdown' \| 'html'` | 啟用 [`AskUserQuestion`](https://code.claude.com/docs/zh-TW/agent-sdk/user-input#question-format) 選項上的 `preview` 欄位並設定其內容格式。未設定時，Claude 不會產生預覽 |

### `McpServerConfig`

MCP 伺服器的設定。

```typescript theme={null}
type McpServerConfig =
  | McpStdioServerConfig
  | McpSSEServerConfig
  | McpHttpServerConfig
  | McpSdkServerConfigWithInstance;
```

#### `McpStdioServerConfig`

```typescript theme={null}
type McpStdioServerConfig = {
  type?: "stdio";
  command: string;
  args?: string[];
  env?: Record<string, string>;
};
```

#### `McpSSEServerConfig`

```typescript theme={null}
type McpSSEServerConfig = {
  type: "sse";
  url: string;
  headers?: Record<string, string>;
};
```

#### `McpHttpServerConfig`

```typescript theme={null}
type McpHttpServerConfig = {
  type: "http";
  url: string;
  headers?: Record<string, string>;
};
```

#### `McpSdkServerConfigWithInstance`

程序內 MCP 伺服器的設定。它是 [`createSdkMcpServer()`](#createsdkmcpserver) 的回傳值，再加上您新增的選用 [`McpServerToolPolicy`](#mcpservertoolpolicy) 項目 `tools` 清單。

```typescript theme={null}
type McpSdkServerConfigWithInstance = {
  type: "sdk";
  name: string;
  timeout?: number;
  tools?: McpServerToolPolicy[];
  instance: McpServer;
};
```

若要讓伺服器某個工具的呼叫需要核准或拒絕它們，請新增一個指名該工具的政策項目。將 `createSdkMcpServer()` 的回傳值展開到 `mcpServers` 下的一個物件中，並將該項目放在該物件上的 `tools` 清單中，因為該函式的 `tools` 選項接受的是工具定義，而不是政策項目。政策清單需要 Agent SDK v0.3.301 或更新版本，[`McpServerToolPolicy`](#mcpservertoolpolicy) 說明每個 `permission_policy` 值的作用。

在此指令碼中，`allowedTools` 萬用字元預先核准了 `records` 伺服器上的每個工具，但 `delete_record` 被標記為 `always_ask`，因此對它的呼叫仍會送到 `canUseTool`。有了 `destructiveHint: true` 註解，即使工作階段以 `auto` 模式執行，呼叫仍會到達回呼，否則自動模式的[分類器](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)可能會核准它。

```typescript theme={null}
import { query, tool, createSdkMcpServer } from "@anthropic-ai/claude-agent-sdk";
import { z } from "zod";

const deleteRecord = tool(
  "delete_record",
  "Delete a customer record by ID",
  { id: z.string() },
  async ({ id }) => ({ content: [{ type: "text", text: `Deleted record ${id}` }] }),
  { annotations: { destructiveHint: true } }
);

const records = createSdkMcpServer({ name: "records", tools: [deleteRecord] });

for await (const message of query({
  prompt: "Delete customer record 42",
  options: {
    mcpServers: {
      // Spread the returned config and add the policy list beside it
      records: {
        ...records,
        tools: [{ name: "delete_record", permission_policy: "always_ask" as const }]
      }
    },
    allowedTools: ["mcp__records__*"],
    canUseTool: async (toolName, input) => {
      console.log(`Approval requested for ${toolName}`);
      return { behavior: "allow", updatedInput: input };
    }
  }
})) {
  if (message.type === "result" && message.subtype === "success") {
    console.log(message.result);
  }
}
```

當 Claude 呼叫 `delete_record` 時，指令碼會印出 `Approval requested for mcp__records__delete_record`。

若要在工作階段執行期間變更或解除工具的政策，請將帶有新 `tools` 值的伺服器設定傳給 [`setMcpServers()`](#mcpsetserversresult)。您傳入的 `tools` 值會從 Claude 下一次呼叫該伺服器的工具時開始生效：

* **含有項目的清單**：這些項目會取代目前的政策
* **空清單**：清除伺服器上的所有政策
* **沒有 `tools` 鍵**：保留目前的政策

請在該呼叫中包含您的其他程序內伺服器，以及先前 `setMcpServers()` 呼叫所新增的任何伺服器，否則該呼叫會中斷它們的連線。

#### `McpServerToolPolicy`

[`McpSdkServerConfigWithInstance`](#mcpsdkserverconfigwithinstance) 的 `tools` 清單中的一個項目，指名伺服器的某個工具，並為對該工具的呼叫設定權限政策。此清單需要 Agent SDK v0.3.301 或更新版本，以及 Claude Code v2.1.301 或更新版本。較舊的 Claude Code 執行檔（例如您以 `pathToClaudeCodeExecutable` 指定的執行檔）會忽略此清單。此時 `always_ask` 和 `always_deny` 不會被強制執行，每個呼叫都會經過[權限流程](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#how-permissions-are-evaluated)。

```typescript theme={null}
type McpServerToolPolicy = {
  name: string;
  permission_policy?: "always_allow" | "always_ask" | "always_deny";
  org_max_permission?: "allow" | "ask" | "blocked";
};
```

| 欄位 | 型別 | 說明 |
| :- | :- | :- |
| `name` | `string` | 傳給 [`tool()`](#tool) 的工具原始名稱，不含 `mcp__<server>__` 前綴 |
| `permission_policy` | `'always_allow' \| 'always_ask' \| 'always_deny'` | 工具呼叫的核准政策，[`always_ask` 或 `always_deny`](#permission-policy-values)。`always_allow` 在程序內伺服器上會被忽略：若要預先核准工具，請改為在 [`allowedTools`](#options) 中列出它 |
| `org_max_permission` | `'allow' \| 'ask' \| 'blocked'` | 由組織管理員設定的每個工具上限。在程序內伺服器上會被忽略，因此請勿設定 |

##### `permission_policy` 值

選擇 `always_ask` 以自行核准每個呼叫，或選擇 `always_deny` 以直接封鎖該工具：

* **`always_ask`**：對該工具的每個呼叫都[需要核准](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#how-permissions-are-evaluated)，即使有 `allowedTools` 項目或允許規則涵蓋它。呼叫會送到您的 `canUseTool` 回呼或 [`permissionPromptToolName`](#options) 工具，除非它先被處理。您載入的外掛中的 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md) [可以先核准它](https://code.claude.com/docs/zh-TW/permissions.md#precedence-among-rules-hooks-and-mods)。否則，在 `dontAsk` 模式下會被拒絕，而在 [`auto`、`plan` 和 `bypassPermissions` 模式](#permission-modes-that-can-approve-an-always_ask-call)下，它可能在到達您的回呼之前就被核准
* **`always_deny`**：對該工具的呼叫在每種權限模式下都[會被拒絕](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#how-permissions-are-evaluated)，包括 `bypassPermissions`，但您載入的外掛中的 mod [仍然可以核准它](https://code.claude.com/docs/zh-TW/permissions.md#precedence-among-rules-hooks-and-mods)

如果您既未傳入 `canUseTool` 也未傳入 `permissionPromptToolName`，或將 [`permissionPrompts`](#options) 設為 `'none'`，則未先被處理的 `always_ask` 呼叫會被拒絕，除非有 [`PermissionRequest` hook](https://code.claude.com/docs/zh-TW/hooks#permissionrequest) 允許它。

##### 可以核准 `always_ask` 呼叫的權限模式

在 `auto`、`plan` 和 `bypassPermissions` 模式下，對標記為 [`always_ask`](#permission-policy-values) 的工具的呼叫，可能在到達您的 `canUseTool` 回呼之前就被核准。

* **`auto`**：自動模式[分類器](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)會審查該呼叫並可能允許它。若要讓 `auto` 模式下的每個呼叫都到達您的回呼，請在工具的[註解](#toolannotations)中設定 `destructiveHint: true`
* **`plan`**：當[自動模式可供](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)工作階段使用時，對註解為 `readOnlyHint: true` 的 `always_ask` 工具的呼叫會送到自動模式分類器，分類器可能允許它們。對其他 `always_ask` 工具的呼叫會到達您的回呼。若要讓唯讀工具的呼叫也到達您的回呼，請在該工具的註解中於 `readOnlyHint: true` 之外加上 `destructiveHint: true`。或者，將 [`useAutoModeDuringPlan`](https://code.claude.com/docs/zh-TW/settings-reference#useautomodeduringplan) 設為 `false`，以在規劃期間關閉分類器
* **`bypassPermissions`**：當 [`CLAUDE_CODE_REMOTE`](https://code.claude.com/docs/zh-TW/env-vars#variables) 環境變數為 `true` 時（如同在[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)中），無論工具的註解為何，呼叫都會在不經過您的回呼的情況下被核准。在其他任何地方，呼叫都會到達您的回呼。若要讓它在雲端工作階段中也到達您的回呼，請改以 `default` 或 `acceptEdits` 模式執行工作階段

在 `auto` 和 `plan` 模式下，請明確將 `destructiveHint` 設為 `true`。對於 `always_ask` 呼叫，Claude Code 會將未設定的 `destructiveHint` 視為 `false`，儘管 [`ToolAnnotations`](#toolannotations) 下列出的預設值為 `true`。

#### `McpClaudeAIProxyServerConfig`

```typescript theme={null}
type McpClaudeAIProxyServerConfig = {
  type: "claudeai-proxy";
  url: string;
  id: string;
};
```

### `SdkPluginConfig`

在 SDK 中載入外掛的設定。

```typescript theme={null}
type SdkPluginConfig = {
  type: "local";
  path: string;
  skipMcpDiscovery?: boolean;
};
```

| 欄位 | 型別 | 說明 |
| :- | :- | :- |
| `type` | `'local'` | 必須為 `'local'`（目前僅支援本機外掛） |
| `path` | `string` | 外掛目錄的路徑。相對路徑會在工作階段啟動時相對於 [`cwd`](#options) 選項解析。當您在工作階段中途以 [`addPlugins`](#load-more-plugin-folders-with-addplugins) 載入外掛時，路徑必須是絕對路徑 |
| `skipMcpDiscovery` | `boolean` | 當為 `true` 時，SDK 會從此外掛載入 skill、hook、agent 和命令，但不會讀取其 `.mcp.json` 或 manifest 的 `mcpServers`。當您的應用程式自行管理外掛的 MCP 連線時，請設定此項。 |

**範例：**

```typescript theme={null}
plugins: [
  { type: "local", path: "./my-plugin" },
  { type: "local", path: "/absolute/path/to/plugin" }
];
```

如需建立和使用外掛的完整資訊，請參閱[外掛](https://code.claude.com/docs/zh-TW/agent-sdk/plugins.md)。

## 訊息類型

### `SDKMessage`

查詢傳回的所有可能訊息的聯合類型。

```typescript theme={null}
type SDKMessage =
  | SDKAssistantMessage
  | SDKUserMessage
  | SDKUserMessageReplay
  | SDKResultMessage
  | SDKSystemMessage
  | SDKPartialAssistantMessage
  | SDKCompactBoundaryMessage
  | SDKStatusMessage
  | SDKLocalCommandOutputMessage
  | SDKHookStartedMessage
  | SDKHookProgressMessage
  | SDKHookResponseMessage
  | SDKPluginInstallMessage
  | SDKToolProgressMessage
  | SDKAuthStatusMessage
  | SDKTaskNotificationMessage
  | SDKTaskStartedMessage
  | SDKTaskProgressMessage
  | SDKTaskUpdatedMessage
  | SDKBackgroundTasksChangedMessage
  | SDKThinkingTokensMessage
  | SDKSessionStateChangedMessage
  | SDKWorkerShuttingDownMessage
  | SDKCommandsChangedMessage
  | SDKNotificationMessage
  | SDKFilesPersistedEvent
  | SDKToolUseSummaryMessage
  | SDKMemoryRecallMessage
  | SDKRateLimitEvent
  | SDKElicitationCompleteMessage
  | SDKPermissionDeniedMessage
  | SDKPromptSuggestionMessage
  | SDKAPIRetryMessage
  | SDKControlRequestProgressMessage
  | SDKModelRefusalFallbackMessage
  | SDKModelRefusalNoFallbackMessage
  | SDKMirrorErrorMessage
  | SDKInformationalMessage
  | SDKConversationResetMessage;
```

此聯集中有三種訊息用於回報控制請求進度與模型拒絕。每一種都具有 `type: "system"`，因此請依各項所列的 `subtype` 加以區分：

* `SDKControlRequestProgressMessage`，`subtype: "control_request_progress"`：回報您的用戶端所送出之長時間執行控制請求的進度。`request_id` 將訊息對應至該請求，`status` 為 `"started"` 或 `"api_retry"`。需要 Agent SDK v0.3.203 或更新版本。
* `SDKModelRefusalFallbackMessage`，`subtype: "model_refusal_fallback"`：當模型以拒絕結束串流，且該回合改在備援模型上重試時發出。帶有 `original_model` 與 `fallback_model`。需要 Agent SDK v0.3.170 或更新版本。
* `SDKModelRefusalNoFallbackMessage`，`subtype: "model_refusal_no_fallback"`：當模型以拒絕結束串流且未執行任何重試時發出，例如因為未設定備援模型。帶有 `original_model`。需要 Agent SDK v0.3.193 或更新版本。

### `SDKAssistantMessage`

助手回應訊息。

```typescript theme={null}
type SDKAssistantMessage = {
  type: "assistant";
  uuid: UUID;
  session_id: string;
  message: BetaMessage; // From Anthropic SDK
  parent_tool_use_id: string | null;
  error?: SDKAssistantMessageError;
  aborted?: true;
  agent_id?: string;
  timestamp?: string;
  context_usage?: SDKContextUsage;
  usage_report?: SDKUsageReport;
  user_message_uuid?: string;
  user_message_uuids?: string[];
  resume_reason?: string;
};
```

`message` 欄位是來自 Anthropic SDK 的 [`BetaMessage`](https://platform.claude.com/docs/en/api/messages/create)。它包含 `id`、`content`、`model`、`stop_reason` 和 `usage` 等欄位。

`SDKAssistantMessageError` 是以下其中之一：`'authentication_failed'`、`'oauth_org_not_allowed'`、`'account_on_hold'`、`'billing_error'`、`'rate_limit'`、`'overloaded'`、`'invalid_request'`、`'model_not_found'`、`'server_error'`、`'max_output_tokens'`、`'cloud_credential_error'` 或 `'unknown'`。其中四個值的含義超出其名稱所表示的內容：

* `'model_not_found'`：選定的模型不存在或無法供您的帳戶或部署使用
* `'overloaded'`：API 傳回 529，因為伺服器已滿載，與 `'rate_limit'` 相對，後者是針對您配額的 429
* `'account_on_hold'`：[您的帳戶已被暫停](https://code.claude.com/docs/zh-TW/errors.md#your-account-is-on-hold)
* `'cloud_credential_error'`：Claude Code 無法在其執行的機器上取得可用的 AWS 或 Google Cloud 憑證，因此沒有請求到達雲端提供者。通常的原因是雲端登入已過期或從未在該機器上完成，但暫時無法連線的憑證服務也會回報相同的值。請參閱[無法載入 AWS 或 Google Cloud 憑證](https://code.claude.com/docs/zh-TW/errors.md#could-not-load-aws-or-google-cloud-credentials)。需要 TypeScript Agent SDK v0.3.267 或更新版本，其中包含 Claude Code v2.1.267

當中斷或中止在串流完成前截斷助手訊息時，`aborted` 為 `true`：訊息沒有 `stop_reason`，內容可能在詞的中間結束。該欄位在正常完成的訊息上不存在。它需要 Agent SDK v0.3.214 或更新版本。

`agent_id` 識別產生該訊息的 subagent，主執行緒訊息不含此欄位。其值等於該 subagent 的 [`task_started`](#sdktaskstartedmessage) 及其他任務事件上的 `task_id`，且在 subagent [恢復](https://code.claude.com/docs/zh-TW/agent-sdk/subagents.md#resume-subagents)時保持不變。在來自[巢狀 subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#let-subagents-spawn-their-own-subagents) 的訊息上，它指的是該巢狀 subagent，而非產生它的 subagent。此欄位需要 Agent SDK v0.3.292 或更新版本。

請依 `agent_id` 將 subagent 的訊息與其任務事件配對，而不是將訊息的 `parent_tool_use_id` 與任務事件的 `tool_use_id` 配對。當工具呼叫恢復 subagent 時，任務事件會帶有該呼叫的 `tool_use_id`，而訊息則保留最初啟動該 subagent 之工具呼叫的 `parent_tool_use_id`，因此兩者將不再相符。

Claude Code 會在符合 [`user_message_uuid`](#user_message_uuid) 所述條件時，於該回合的第一則助理訊息上設定 `user_message_uuid` 和 `user_message_uuids`。當該回合是接續因重新啟動而中斷的回合時，帶有這些欄位的助理訊息也會帶有 [`resume_reason`](#resume_reason)。

`timestamp` 是訊息內容在產生它的程序上完成生成的 ISO 8601 時間。該值來自該機器的時鐘，因此僅用於顯示，不要依其排序訊息。一個 API 回合可以產生多個共用同一 `message.id` 的助手訊息，每個都有自己的 `timestamp`。當欄位不存在時，請改用您收到訊息的時間。

`context_usage` 是 `/context` 報告的結構化副本，類型為 [`SDKContextUsage`](#sdkcontextusage)，需要 Agent SDK v0.3.232 或更新版本。當您以提示詞形式傳送 `/context` 時，Claude Code 會將報告作為助手訊息傳遞，其 `message.content` 包含 markdown 表格，並將 `context_usage` 附加到同一訊息。Claude Code 不會在任何其他助手訊息上設定該欄位，較早的版本傳遞 `/context` 表格時也不會帶有它，因此當欄位存在時從欄位讀取明細，不存在時則改用 markdown 文字。

`usage_report` 是 `/usage` 報告的結構化副本，類型為 [`SDKUsageReport`](#sdkusagereport)，需要 Agent SDK v0.3.273 或更新版本。當您將 `/usage` 作為提示詞送出時，Claude Code 會以一則助理訊息傳遞報告，其 `message.content` 包含文字。只有在工作階段符合下列所有條件時，它才會將 `usage_report` 附加到同一則訊息上：

* 工作階段使用 claude.ai 憑證進行身分驗證
* 該憑證顯示已知的方案類型，或帶有 `user:profile` 範圍
* 該帳戶並非採用依用量計費

以 `CLAUDE_CODE_OAUTH_TOKEN` 傳入的 `claude setup-token` token 預設不符合條件，因為它只帶有 `user:inference` 範圍。其他工作階段（例如 API 金鑰工作階段）傳遞的文字不含此欄位，較早的版本也是如此。當欄位存在時請從中讀取報告，不存在時則改用文字。

### `SDKUserMessage`

使用者輸入訊息。

```typescript theme={null}
type SDKUserMessage = {
  type: "user";
  uuid?: UUID;
  session_id?: string;
  agent_id?: string;
  message: MessageParam; // From Anthropic SDK
  pasted_content?: MessageParam["content"][];
  parent_tool_use_id: string | null;
  isSynthetic?: boolean;
  shouldQuery?: boolean;
  client_composed?: true;
  tool_use_result?: unknown;
  priority?: "now" | "next" | "later";
  origin?: SDKMessageOrigin;
  inline_pastes?: string[];
};
```

設定 `pasted_content` 以傳送使用者貼上到您提示詞 UI 中（而非輸入）的內容，每次貼上一個項目，每個項目都是字串或內容區塊陣列。Claude Code 會依序將每個項目的文字附加在輸入的文字之後，並可能將每次貼上的內容包裝在 `<pasted_content>` 標籤中。文字以外的區塊會被忽略，因此請在 `message.content` 中傳送圖片和文件。需要 Agent SDK v0.3.277 或更新版本。

設定 `inline_pastes` 以告訴 Claude Code `message.content` 中哪些部分是使用者貼上而非輸入的，每次貼上對應一個字串。提示詞文字會保留在使用者放置的位置。Claude Code 可能會就地將每個列出的貼上內容包在 `<pasted_content>` 標籤中，讓 Claude 能區分貼上的素材與使用者自己的文字。只有提示詞最後一個文字區塊中的貼上內容會被包裝。需要 TypeScript Agent SDK v0.3.280 或更新版本。

每個貼上欄位都有大小限制：

* `pasted_content`：若項目加上其中的內容區塊總數超過 1,000，Claude Code 會忽略整個欄位。
* `inline_pastes`：Claude Code 使用前 100 個非空白項目，並忽略其餘項目。

設定 `shouldQuery`、`client_composed` 或 `priority`，以變更 Claude Code 處理您所傳送訊息的方式：

* `shouldQuery`：設定為 `false` 以將訊息附加到逐字稿，而不觸發助手回合。訊息會被保留，並合併到下一個會觸發回合的使用者訊息中。使用此方式注入上下文，例如您在頻外執行之命令的輸出，而不必為此花費一次模型呼叫。
* `client_composed`：設定為 `true` 以讓 Claude Code 依原文傳遞訊息文字。Claude Code 將不會展開 `@path` 或 [`@server:resource`](https://code.claude.com/docs/zh-TW/mcp#use-mcp-resources) 提及，也不會將以 `/` 開頭的文字作為命令執行。當 [`verbatimPrompts`](#options) 選項開啟時，SDK 會在每則訊息上設定該欄位。需要 TypeScript Agent SDK v0.3.280 或更新版本以及 Claude Code v2.1.248 或更新版本。
* `priority`：控制您在回合執行期間傳送的訊息何時送達 Claude：
  * `'next'` 或無 `priority` 欄位：Claude 會在同一回合中讀取訊息，時間點為其正在執行的工具呼叫完成之後。若回合先結束，該訊息會開始下一個回合。
  * `'later'`：Claude Code 會保留訊息直到回合結束，再將其作為新回合傳送。
  * `'now'` 搭配 [`origin: { kind: "human" }`](#sdkmessageorigin)：在 Claude Code v2.1.286 或更新版本上，可在背景繼續進行的工作會移至背景，且 Claude 會在同一回合中讀取訊息。可移動的工作包括 shell 命令、subagent 與 MCP 工具呼叫。在 v2.1.287 或更新版本上，還包括 WebFetch 與 WebSearch 呼叫。當 Claude 只是在撰寫回應，或其正在執行的工作無法移動時，Claude Code 會改為中斷回合，Claude 接著讀取訊息。
  * `'now'` 但未搭配該 origin：Claude Code 會中斷回合，Claude 接著讀取訊息。

以下這則在回合執行期間傳送的訊息，會要求 Claude 改變方向，同時不會遺失仍在執行中的 shell 命令：

```typescript theme={null}
const message: SDKUserMessage = {
  type: "user",
  message: { role: "user", content: "Skip the integration tests and summarize what you have so far" },
  parent_tool_use_id: null,
  priority: "now",
  origin: { kind: "human" },
};
```

subagent 產生的使用者訊息（例如其自身某個工具呼叫的 `tool_result`）會帶有 `agent_id`。請參閱 [`SDKAssistantMessage`](#sdkassistantmessage)，其中定義了此欄位及其版本需求。

在帶有 `tool_result` 區塊的訊息上，`tool_use_result` 是工具的結構化輸出物件，而非傳送給模型的文字。其形狀取決於對應 `tool_use` 區塊所指名的工具，因此此欄位的型別為 `unknown`；內建形狀列於[工具輸出類型](#tool-output-types)。下列結果需要超出其所列形狀的處理：

* `Agent` 工具：`tool_use_result` 為 [`AgentOutput`](#agent-2)。請依據它來呈現，而非剖析 `tool_result` 文字。`completed` 結果的 `content` 包含 subagent 的報告；對於透過 `SubagentHandback` 工具呼叫交回報告的 subagent，則是以一段關於該交回的簡短說明取代報告。在 Claude Code v2.1.271 或更新版本的[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)中，每個產生 `completed` 結果的 subagent 都會以這種方式回報，除非它是 [fork](https://code.claude.com/docs/zh-TW/sub-agents.md#fork-the-current-conversation)，且 Claude 會以來自 subagent 的獨立訊息接收報告。
* Claude Code 為了傳遞 `'now'` 訊息而移至背景的 WebFetch 或 WebSearch 呼叫：帶有該呼叫之 `tool_result` 的使用者訊息，其 `tool_use_result` 設為 `{ detachedToolCall: true }`。該呼叫仍在執行中，Claude 會在其完成後接收結果。該 `tool_use_id` 之後不會再有第二個 `tool_result`，因此若您的應用程式為每個工具呼叫繪製一列，請在此訊息到達時將該列標示為已移至背景。需要 Claude Code v2.1.287 或更新版本。
* 結果包含 `resource_link` 區塊的 MCP 工具：`tool_use_result` 是一個物件，含有由 [`SDKMcpResourceLink`](#sdkmcpresourcelink) 項目組成的 `resourceLinks` 陣列。Claude 會在 `tool_result` 區塊中以一行文字接收每個連結，因此請讀取 `resourceLinks` 來呈現伺服器回傳的檔案，而非剖析該文字。當結果沒有連結時，以及在來自 subagent 的結果上，Claude Code 會省略 `resourceLinks`；每個結果最多保留 50 個連結，且當陣列的序列化 JSON 達到 64 KiB 時便停止新增連結。`resourceLinks` 需要 Agent SDK v0.3.257 或更新版本。
* 回傳 [`structuredContent`](#calltoolresult) 的 MCP 工具：`tool_use_result` 是一個物件，其 `structuredContent` 成員包含伺服器傳送的內容，`content` 成員則包含 [`McpOutput`](#mcpoutput) 值。來自 subagent 的結果不帶有 `structuredContent`。
* `structuredContent` 序列化後超過 1,048,576 個字元 JSON 的 MCP 工具：Claude Code 會在 `tool_use_result` 中省略 `structuredContent`，並以 `structuredContentOmitted: true` 取代，讓您的應用程式能區分被捨棄的物件與未傳送物件的工具。其他成員（例如 `content` 和 `resourceLinks`）會保留，Claude 收到的內容也不變。Claude Code v2.1.287 或更新版本會套用此上限。有兩類工具不同：
  * 來自[程序內 SDK 伺服器](https://code.claude.com/docs/zh-TW/agent-sdk/custom-tools.md)的工具不受此限，會完整傳遞物件。
  * `tools/list` 項目宣告了 [MCP Apps `ui://` 資源](#mcpserverstatus)的工具，在 Claude Code v2.1.295 或更新版本上的上限為 8,388,608 個字元，而 v2.1.295 之前的版本則不對其設限。

### `SDKUserMessageReplay`

具有必要 UUID 的重播使用者訊息。

```typescript theme={null}
type SDKUserMessageReplay = {
  type: "user";
  uuid: UUID;
  session_id: string;
  message: MessageParam;
  parent_tool_use_id: string | null;
  isSynthetic?: boolean;
  client_composed?: true;
  tool_use_result?: unknown;
  origin?: SDKMessageOrigin;
  isReplay: true;
};
```

從工作階段外部注入的使用者回合（其 [`origin`](#sdkmessageorigin) kind 為 `peer` 或 `channel`），無論是在進行中的回合期間傳遞，還是在工作階段閒置時啟動新回合，都會作為重播到達串流。在 v2.1.207 之前，於工作階段閒置時傳遞的注入回合不會在串流上產生訊息，只會在您重新讀取逐字稿時出現。

### `SDKResultMessage`

最終結果訊息。

```typescript theme={null}
type SDKResultMessage =
  | {
      type: "result";
      subtype: "success";
      uuid: UUID;
      session_id: string;
      duration_ms: number;
      duration_api_ms: number;
      is_error: boolean;
      api_error_status?: number | null;
      num_turns: number;
      result: string;
      stop_reason: string | null;
      ttft_ms?: number;
      ttft_stream_ms?: number;
      time_to_request_ms?: number;
      user_message_uuid?: string;
      user_message_uuids?: string[];
      resume_reason?: string;
      local_command?: string;
      request_sent_wall_ms?: number;
      first_content_frame_ms?: number;
      first_stream_post_ms?: number;
      first_stream_post_ack_ms?: number;
      first_stream_post_queue_wait_ms?: number;
      first_stream_post_queued_behind?: "durable_post" | "ephemeral_post" | "retry_backoff" | "hold" | "none";
      first_stream_post_wall_ms?: number;
      first_text_post_ms?: number;
      first_text_post_queue_wait_ms?: number;
      first_text_post_queued_behind?: "durable_post" | "ephemeral_post" | "retry_backoff" | "hold" | "none";
      first_text_post_wall_ms?: number;
      total_cost_usd: number;
      usage: NonNullableUsage;
      modelUsage: { [modelName: string]: ModelUsage };
      permission_denials: SDKPermissionDenial[];
      queued_turn_count?: number;
      structured_output?: unknown;
      deferred_tool_use?: { id: string; name: string; input: Record<string, unknown> };
      terminal_reason?: TerminalReason;
      result_index?: number;
      fast_mode_state?: FastModeState;
      fast_mode_disabled_reason?: FastModeDisabledReason;
      origin?: SDKMessageOrigin;
    }
  | {
      type: "result";
      subtype:
        | "error_max_turns"
        | "error_during_execution"
        | "error_max_budget_usd"
        | "error_max_structured_output_retries";
      uuid: UUID;
      session_id: string;
      duration_ms: number;
      duration_api_ms: number;
      is_error: boolean;
      num_turns: number;
      stop_reason: string | null;
      total_cost_usd: number;
      usage: NonNullableUsage;
      modelUsage: { [modelName: string]: ModelUsage };
      permission_denials: SDKPermissionDenial[];
      queued_turn_count?: number;
      errors: string[];
      startup_failure_reason?: SDKStartupFailureReason;
      user_message_uuid?: string;
      user_message_uuids?: string[];
      resume_reason?: string;
      terminal_reason?: TerminalReason;
      result_index?: number;
      fast_mode_state?: FastModeState;
      fast_mode_disabled_reason?: FastModeDisabledReason;
      origin?: SDKMessageOrigin;
    };
```

結果上的多個欄位除了 `subtype` 之外還提供診斷詳細資訊：

* `api_error_status`：終止對話的 API 錯誤的 HTTP 狀態碼。當回合在沒有 API 錯誤的情況下結束時，不存在或為 `null`。
* `ttft_ms`：首個 token 的時間（毫秒），在第一個完整助手訊息到達時測量。僅在成功分支上存在。
* `ttft_stream_ms`：直到第一個 `message_start` 串流事件（即回應串流開啟時）的時間（毫秒）。低於 `ttft_ms`；兩者之間的差距是串流第一個訊息所花費的時間。僅在成功分支上存在。
* `time_to_request_ms`：從回合開始到 Claude Code 傳送 API 請求的時間，以毫秒計。僅出現在成功分支上。需要 Claude Code v2.1.162 或更新版本。
* `user_message_uuid`：此回合所回答的、您傳送之訊息的 `uuid`。請參閱 [`user_message_uuid`](#user_message_uuid) 以了解哪些結果會攜帶它。
* `user_message_uuids`：Claude Code 在此回合中回答的、您傳送之每則訊息的 `uuid`。請參閱 [`user_message_uuids`](#user_message_uuids)。
* `resume_reason`：此回合為何接續因重新啟動而中斷的回合。出現在兩個分支上。請參閱 [`resume_reason`](#resume_reason)。
* `local_command`：回合所分派之命令的名稱，出現在由命令完成、未進入 agent 迴圈之回合的成功結果上，例如 `/compact`。名稱會轉為小寫字母和底線，因此 `/reload-plugins` 回報為 `reload_plugins`。由 MCP 伺服器提供的命令以及內建的 `/mcp` 回報為 `mcp`。您自行定義的命令回報為 `custom`。引數永遠不會包含在內。在每個進入 agent 迴圈的回合上，以及在未執行任何命令的傳送上，此欄位不存在。需要 Agent SDK v0.3.268 或更新版本。
* `request_sent_wall_ms`：Claude Code 分派 API 請求時的紀元毫秒，用於與伺服器端時間戳記進行對照。僅與 [`user_message_uuid`](#user_message_uuid) 一起存在，出現在 `is_error` 為 false、且其回合傳送了 API 請求的成功結果上。
* `first_content_frame_ms`：直到第一個 `content_block_start` 或 `content_block_delta` 串流事件的時間（毫秒），思考區塊也計為內容。僅在成功分支上、`is_error` 為 false 時存在。需要 Agent SDK v0.3.260 或更新版本。
* `first_stream_post_ms`、`first_stream_post_ack_ms`、`first_stream_post_wall_ms`：上傳回合第一個串流事件的計時。Claude Code 僅在它串流到 claude.ai 的工作階段中記錄這些值，例如[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)，`query()` 產生的結果不會攜帶它們。需要 Agent SDK v0.3.260 或更新版本。
* `usage`：僅限主 agent 迴圈。排除 subagent 和輔助模型呼叫，且在串流輸入工作階段中按回合計算。token/成本會計請優先使用 `modelUsage`。
* `modelUsage`：在此 `query()` 呼叫期間，透過查詢管線進行之每個模型呼叫的各模型總計，包括主迴圈、subagent，以及壓縮和 Workflow agent 等內部呼叫。該管線之外的輔助呼叫，例如權限分類器和 token 計數請求，不計入。恢復工作階段的呼叫也會計入[從工作階段較早呼叫還原的各模型總計](https://code.claude.com/docs/zh-TW/agent-sdk/cost-tracking.md#accumulate-costs-across-multiple-calls)。在串流輸入工作階段中，總計會跨回合累積，因此請讀取最新結果，而不是加總所有結果。請參閱[在串流輸入模式中追蹤成本](https://code.claude.com/docs/zh-TW/agent-sdk/cost-tracking.md#track-costs-in-streaming-input-mode)以了解重設，以及[在工作階段當機後恢復總計](https://code.claude.com/docs/zh-TW/agent-sdk/cost-tracking.md#recover-totals-after-a-session-crash)以了解歸零的結果。
* `total_cost_usd`：累積的估計成本（美元），涵蓋與 `modelUsage` 相同的呼叫，並在相同時間點重設。恢復工作階段的呼叫也會計入[從工作階段較早呼叫還原的總計](https://code.claude.com/docs/zh-TW/agent-sdk/cost-tracking.md#accumulate-costs-across-multiple-calls)。這是估計值，不是帳單。請參閱[追蹤成本和使用情況](https://code.claude.com/docs/zh-TW/agent-sdk/cost-tracking.md)以了解準確性注意事項。
* `queued_turn_count`：您以 `origin: { kind: "human" }` 傳送、在 Claude Code 產生結果時仍在等待的訊息數量。請參閱 [`queued_turn_count`](#queued_turn_count) 以了解 `0` 和不存在的欄位代表什麼。
* `result_index`：此結果在執行之傳遞順序中的位置，從 0 開始，涵蓋程序寫入的每個結果。在兩個分支上都存在。寫入失敗的結果仍會消耗其編號，因此序列中出現間隙即表示有結果遺失。需要 Agent SDK v0.3.268 或更新版本。
* `startup_failure_reason`：Claude Code 拒絕啟動的原因，出現在它因已知啟動失敗而結束前寫入的 `error_during_execution` 結果上。請參閱 [`startup_failure_reason`](#startup_failure_reason) 以了解其值以及哪些失敗會攜帶它。需要 Agent SDK v0.3.274 或更新版本。
* `terminal_reason`：迴圈結束的原因。為 `"completed"`、`"max_turns"`、`"tool_deferred"`、`"aborted_streaming"`、`"aborted_tools"`、`"hook_stopped"`、`"stop_hook_prevented"`、`"background_requested"`、`"blocking_limit"`、`"rapid_refill_breaker"`、`"prompt_too_long"`、`"image_error"`、`"model_error"`、`"api_error"`、`"malformed_tool_use_exhausted"`、`"budget_exhausted"`、`"structured_output_retry_exhausted"`、`"tool_deferred_unavailable"` 或 `"turn_setup_failed"` 之一。
* `fast_mode_state`：`"on"`、`"off"` 或 `"cooldown"` 之一。
* `fast_mode_disabled_reason`：[快速模式](https://code.claude.com/docs/zh-TW/fast-mode.md)目前無法使用的原因。當沒有任何因素阻止快速模式時不存在，但請求仍可能以標準速度執行。在快速模式速率限制後的冷卻期間，Claude Code 會回報 `fast_mode_state: "cooldown"` 而不附原因代碼，並在冷卻期結束時重新啟用快速模式。需要 Claude Code v2.1.219 或更新版本。

使用原因代碼在您自己的 UI 中說明快速模式為何關閉，而不是重新推導可用性。每個代碼指名阻止快速模式的檢查：

| 原因代碼 | 含義 |
| - | - |
| `free` | 帳戶沒有快速模式所需的付費訂閱或用量點數 |
| `preference` | 組織已停用快速模式 |
| `extra_usage_disabled` | 帳戶的用量點數已關閉 |
| `network_error` | [可用性檢查](https://code.claude.com/docs/zh-TW/fast-mode.md#use-fast-mode-behind-proxies-and-llm-gateways)無法連線到 `api.anthropic.com` |
| `unknown` | Claude Code 無法判斷可用性 |
| `not_first_party` | 工作階段使用 Anthropic API 以外的提供者 |
| `disabled_by_env` | 已設定 [`CLAUDE_CODE_DISABLE_FAST_MODE`](https://code.claude.com/docs/zh-TW/env-vars) |
| `model_not_allowed` | 快速模式的 Opus 模型不在組織的 [`availableModels`](https://code.claude.com/docs/zh-TW/model-config#restrict-model-selection) 允許清單中 |
| `sdk_opt_in_required` | 工作階段尚未選擇加入快速模式：請在 [`settings`](#options) 選項中或透過 [`applyFlagSettings()`](#applyflagsettings) 傳遞 `fastMode: true` |
| `pending` | 可用性檢查尚未完成 |

相同的這對欄位也出現在 [`SDKSystemMessage`](#sdksystemmessage) 和 [`SDKControlInitializeResponse`](#sdkcontrolinitializeresponse) 上，因此您可以在第一個回合之前讀取快速模式狀態。

`origin` 欄位會轉送觸發此結果之使用者訊息的 [`SDKMessageOrigin`](#sdkmessageorigin)。帶有 `origin: { kind: "task-notification" }` 的結果包括：

* **合成的後續回合**：當 SDK 注入合成的後續回合時（例如針對已完成的背景任務），產生的 `SDKResultMessage` 會帶有此 kind
* **已觸發的排程任務和來自其他工作階段的訊息**：觸發條件已觸發的雲端排程任務，以及來自您其他工作階段且經伺服器驗證的訊息，也會以此 kind 到達，各自帶有 [Task-notification 子類型](#task-notification-subkinds)中所述的 `subkind`

在路由或抑制結果之前，請檢查 `kind` 以區分回應您提示詞的結果與注入的後續結果。若您的應用程式[宣告了排程執行](#declare-a-scheduled-run)，其結果也會帶有 `kind: "task-notification"`，因此不要僅依 `kind` 進行抑制。

當多個背景任務完成事件一起排入佇列時，Claude Code 可以在一個回合中回答它們，而不是每個一個回合。每個完成事件仍會產生自己帶有此 origin 的結果。在 Claude Code 一併回答的完成事件中，除最後一個之外，其餘都會依序產生 `num_turns: 0` 的空結果，而最後一個的結果則攜帶回答所有事件的那個回合。

對於在任何使用者回合之前發出的結果（例如啟動錯誤），該欄位不存在。

當 `PreToolUse` hook 傳回 `permissionDecision: "defer"` 時，結果會帶有 `stop_reason: "tool_deferred"`，且 `deferred_tool_use` 攜帶待處理工具的 `id`、`name` 和 `input`。讀取此欄位以在您自己的 UI 中呈現請求，然後使用相同的 `session_id` 恢復以繼續。請參閱[延後工具呼叫以供稍後處理](https://code.claude.com/docs/zh-TW/hooks.md#defer-a-tool-call-for-later)以了解完整的往返流程。

#### `user_message_uuid`

回合所回答之 [`SDKUserMessage`](#sdkusermessage) 的 `uuid`，回傳此值以便您將 Claude Code 的回覆與您傳送的訊息對應起來。只有在您於訊息上設定了 `uuid` 時，Claude Code 才會回傳它。該欄位在 `SDKUserMessage` 上是選用的，而傳遞給 `query()` 的字串提示詞不會攜帶任何 uuid。

回合所回答的是您的哪則訊息，取決於回合的啟動方式：

* **您傳送的一般訊息**，即不帶 `isSynthetic: true` 的訊息：回合在整個執行過程中都回答該訊息。當您在短時間內傳送多則訊息時，Claude Code 可以將它們合併為一個回合，此時該欄位僅攜帶最後一則訊息的 `uuid`。若要將回覆與任何一則被合併的訊息對應，請使用 [`user_message_uuids`](#user_message_uuids)。
* **您以 `isSynthetic: true` 傳送的訊息**：回合一開始回答該訊息。如果 Claude Code 在工具呼叫之間接收到您的一般訊息，回合從那時起改為回答所接收的訊息。回傳合成訊息的 `uuid` 需要 Agent SDK v0.3.265 或更新版本；較早的版本在合成回合上不會回傳任何內容。
* **Claude Code 在 [`CLAUDE_CODE_RESUME_INTERRUPTED_TURN`](https://code.claude.com/docs/zh-TW/env-vars) 下為接續中斷回合而產生的提示詞**：當中斷回合的最後一個提示詞是您傳送的一般訊息時（無論它是開啟了該回合，或是 Claude Code 在回合中接收的），接續的回合一開始回答該訊息。[`resume_reason`](#resume_reason) 可區分接續回合的框架與中斷嘗試的框架。當最後一個提示詞不是您的一般訊息時，接續的回合一開始不回答您的任何訊息。若 Claude Code 在工具呼叫之間接收了您的一般訊息，回合從那時起便回答所接收的訊息。回傳中斷回合的提示詞需要 Agent SDK v0.3.268 或更新版本。
* **Claude Code 自行產生的任何其他提示詞**：回合一開始不回答您的任何訊息，其框架不攜帶任何回傳值。如果 Claude Code 在工具呼叫之間接收到您的一般訊息，回合從那時起回答該訊息。接收時的回傳需要 Agent SDK v0.3.265 或更新版本；較早的版本在這些回合上不會回傳任何內容。

Claude Code 會在三種框架上回傳所回答訊息的 `uuid`：

* **結果**：回答了您所傳送訊息之回合的每個結果。在 Agent SDK v0.3.265 或更新版本上，每個此類結果都攜帶它。在 v0.3.265 之前，由一般訊息啟動之回合的成功結果，若該回合未傳送 API 請求或以延後的工具呼叫結束，則缺少此欄位。在 v0.3.246 之前，錯誤結果也缺少此欄位，而在 v0.3.216 之前，每個結果都缺少此欄位。
* **回合的第一個回覆**：第一個[助手訊息](#sdkassistantmessage)，以及在使用 `includePartialMessages` 時，第一個 `event.type` 不是 `ping` 的[串流事件](#sdkpartialassistantmessage)，讓您可以在結果到達之前對應回覆。第一個回覆的回傳需要 Agent SDK v0.3.246 或更新版本。在 v0.3.269 之前，使用 `includePartialMessages` 時，Claude Code 只會在該第一個串流事件上設定此欄位，或在回合未串流任何內容時設定在第一個助手訊息上。當回合所回答的訊息在回合中途變更時，變更後的第一個回覆也會攜帶該欄位，這在 Agent SDK v0.3.265 或更新版本上適用；較早的版本在每個回合只會於一個回覆框架上設定它。
* **回合的每個 [`thinking_tokens`](#sdkthinkingtokensmessage) 框架**：讓您無需等待回合的第一個回覆，就能將思考進度歸屬到您傳送的訊息。需要 Agent SDK v0.3.260 或更新版本。

在下列情況中，Claude Code 會省略該欄位：

* 上述第一個回覆以外的回覆框架
* Subagent 框架
* 不回答您任何訊息的回合，或回答您傳送之不帶 `uuid` 訊息的回合
* 不回答您所傳送任何訊息的結果，例如工作程序當機後歸零的結果

當 [`UserPromptSubmit`](https://code.claude.com/docs/zh-TW/hooks#userpromptsubmit) hook 封鎖一則開始其自身回合的訊息，或以 `continue: false` 停止它時，您仍會收到該訊息的結果。這是一個 `is_error: false` 且 `num_turns: 0` 的成功結果，其 `result` 為[封鎖訊息](https://code.claude.com/docs/zh-TW/hooks.md#what-a-blocked-prompt-leaves-behind)或[停止訊息](https://code.claude.com/docs/zh-TW/hooks.md#json-output)，並依照與任何其他結果相同的規則回傳該訊息的 `uuid`。該結果沒有 `terminal_reason`，且除了 `result` 文字外，結果上沒有任何內容表明是 hook 結束了該回合。在另一個回合執行期間被 hook 封鎖的訊息可能不會有結果：請參閱 [`user_message_uuids`](#user_message_uuids)。

#### `user_message_uuids`

Claude Code 在此回合中回答的、您所傳送之每則訊息的 `uuid`。當您在短時間內傳送多則訊息時，Claude Code 可以將它們合併為一個回合，此時 `user_message_uuid` 只會指名其中的最後一則。若要將回覆與任何一則被合併的訊息對應，請在此清單中任何位置尋找該訊息的 `uuid`。需要 Agent SDK v0.3.259 或更新版本。

Claude Code 會在每個攜帶 `user_message_uuid` 的回覆框架以及結果上，將此清單與該欄位一併設定。關於回傳所回答訊息之 `uuid` 的完整回合框架集合，以及各自所需的版本，請參閱 [`user_message_uuid`](#user_message_uuid)。清單一定包含 `user_message_uuid`，且最多保留 64 個項目。

當 Claude Code 接收您在回合執行期間送出的一般訊息時，會將該訊息的 `uuid` 加入結果的清單中。當 [`UserPromptSubmit`](https://code.claude.com/docs/zh-TW/hooks#userpromptsubmit) hook 在接收時封鎖該訊息，Claude Code 會改為捨棄它：該訊息永遠不會送達 Claude，也不會保留到之後的回合。您不會收到它的結果，其 `uuid` 也不會出現在任何結果的清單中。如果 hook 可能封鎖訊息，請為等待列出您在回合執行期間所送出訊息的結果設定逾時。

上述情況適用於 hook 的輸出僅為封鎖時。如果輸出設定了 `continue: false`（即使與 `decision: "block"` 並存），或該 hook 是以 [`ok: false`](https://code.claude.com/docs/zh-TW/hooks#response-schema) 回答且未帶 `continueOnBlock: true` 的提示詞 hook，Claude Code 會停止該訊息而非捨棄它。該訊息會等待其自身的回合，您會收到它的結果，且其文字會保留在對話中，因此 Claude 會在下一個回合看到它。

當第一個回覆或結果攜帶 `user_message_uuid` 但沒有清單時，表示它來自較早的 Claude Code 版本，因此請改用該單一欄位。

#### `resume_reason`

此回合為何接續因重新啟動而中斷的回合。Claude Code 會在 [`CLAUDE_CODE_RESUME_INTERRUPTED_TURN`](https://code.claude.com/docs/zh-TW/env-vars) 下接續中斷回合的回合上設定此欄位，讓您能區分接續回合的回覆和結果與中斷嘗試的回覆和結果。需要 Agent SDK v0.3.268 或更新版本。

Claude Code 會在兩種框架上設定此欄位：

* **接續回合的結果**：成功和錯誤分支皆然，無論結果是否帶有 `user_message_uuid`。
* **接續回合的回覆框架**：帶有 [`user_message_uuid`](#user_message_uuid) 的那些框架。

其值是一個簡短的小寫 token，例如 `interrupted_turn`。

#### `queued_turn_count`

您以 [`origin: { kind: "human" }`](#sdkmessageorigin) 傳送、在 Claude Code 產生結果時仍在命令佇列中等待的訊息數量。需要 Agent SDK v0.3.242 或更新版本。

`0` 和不存在的欄位代表什麼：

* **`0`**：Claude Code 不會計算您未以該 `origin` 傳送的訊息，也不計算任務通知，因此仍可能有後續回合。
* **不存在**：Claude Code 在當機或致命啟動錯誤後發出的最終結果會省略該欄位，且[可能攜帶歸零的總計](https://code.claude.com/docs/zh-TW/agent-sdk/cost-tracking.md#recover-totals-after-a-session-crash)。

#### `startup_failure_reason`

Claude Code 拒絕啟動的原因，讓您的應用程式可以提供修正方式而非重試。Claude Code 會在因已知啟動失敗而結束前寫入的 `error_during_execution` 結果上設定它。該結果攜帶歸零的總計，其 `errors` 陣列攜帶與 stderr 相同的文字。在所有其他結果上，此欄位不存在。需要 Agent SDK v0.3.274 或更新版本。

在 [`env`](#options) 中將 `CLAUDE_CODE_STARTUP_FAILURE_RESULTS` 設定為 `1`，即可針對每個 `SDKStartupFailureReason` 值接收此結果。若未設定該變數，Claude Code 僅會針對下列失敗寫入結果，其餘失敗則以 stderr 輸出、非零結束代碼且無結果訊息的方式結束：

* Claude Code 因[無法將工作階段帶回其 worktree](https://code.claude.com/docs/zh-TW/worktrees.md#the-session-resumes-outside-its-worktree) 而停止的恢復，帶有 `worktree_unverified` 或 `worktree_resume_refused`。該章節說明哪個錯誤攜帶哪個值。
* 對背景工作階段所持有之對話的 [`continue`](#options) 遭拒，帶有 `session_held_by_background`。對於此類對話的 [`resume`](#options) 遭拒，Claude Code 僅在設定了該變數時才會寫入結果。
* 因 [`failIfUnavailable`](#sandboxsettings) 開啟且沙箱無法啟動而被 Claude Code 拒絕的啟動，帶有 `sandbox_required_unavailable`。

`SDKStartupFailureReason` 型別列出 `startup_failure_reason` 可持有的值：

```typescript theme={null}
type SDKStartupFailureReason =
  | "org_pin_api_key_conflict"
  | "provider_not_allowed"
  | "org_verify_failed"
  | "org_pin_mismatch"
  | "managed_settings_invalid"
  | "remote_settings_required_unavailable"
  | "gateway_signin_required"
  | "gateway_access_denied"
  | "proxy_invalid"
  | "temp_dir_unusable"
  | "cwd_unavailable"
  | "shell_tool_missing"
  | "session_held_by_background"
  | "worktree_resume_refused"
  | "worktree_unverified"
  | "cli_version_too_old"
  | "bypass_root"
  | "org_config_required_unavailable"
  | "org_config_refused"
  | "sandbox_required_unavailable";
```

每個值指名一種拒絕：

| 值 | 停止工作階段的原因 |
| :- | :- |
| `org_pin_api_key_conflict` | 受管設定[要求第一方或 Cloud 閘道登入](https://code.claude.com/docs/zh-TW/authentication.md#restrict-login-to-your-organization)，但設定的卻是 Anthropic API 金鑰、驗證 token 或 `apiKeyHelper` |
| `provider_not_allowed` | 受管設定[列出此機器可使用的 API 提供者](https://code.claude.com/docs/zh-TW/settings-reference.md#allowedproviders)，而工作階段設定的提供者不在清單中，或設定的端點未被這些設定固定。需要 Claude Code v2.1.285 或更新版本 |
| `org_verify_failed` | 無法依據 pin 驗證登入的組織，例如因為網路故障或 token 已撤銷 |
| `org_pin_mismatch` | 登入屬於 pin 不允許的組織 |
| `managed_settings_invalid` | 無法讀取受管原則設定、pin 未指名任何組織，或[受管模型限制](https://code.claude.com/docs/zh-TW/errors.md#managed-settings-block-the-default-model)導致預設選項沒有任何允許的模型 |
| `remote_settings_required_unavailable` | 無法載入組織要求的受管設定 |
| `gateway_signin_required` | [Cloud 閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)結束了此登入 |
| `gateway_access_denied` | 對 Cloud 閘道的受管設定請求傳回 403，閘道的[疑難排解表](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#troubleshooting)涵蓋了此情況 |
| `proxy_invalid` | 代理伺服器設定不是完整的 URL |
| `temp_dir_unusable` | 每位使用者的暫存目錄不安全或無法建立 |
| `cwd_unavailable` | 工作目錄已被刪除、移動或無法讀取 |
| `shell_tool_missing` | 在 Windows 上沒有可用的 shell 工具：Git Bash 不存在，而 PowerShell 不存在或已透過 `CLAUDE_CODE_USE_POWERSHELL_TOOL` 關閉 |
| `session_held_by_background` | 要恢復或繼續的對話正作為[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)執行 |
| `worktree_resume_refused` | 工作階段的 worktree 未通過安全檢查，或恢復是從其內部啟動的。`errors` 會說明再次執行相同的恢復是否會在沒有 worktree 的情況下繼續 |
| `worktree_unverified` | 目前無法驗證工作階段的 worktree，重試可能會成功 |
| `cli_version_too_old` | 此 Claude Code 版本低於 Anthropic 要求的最低版本 |
| `bypass_root` | 以 root 身分執行時請求了略過權限模式 |
| `org_config_required_unavailable` | 工作階段在啟動前需要組織的原則和受管設定，但無法載入它們，例如因為網路失敗或 Anthropic 伺服器錯誤。需要 Agent SDK v0.3.293 或更新版本 |
| `org_config_refused` | Anthropic 拒絕為此登入提供組織的原則和受管設定，例如因為登入已過期或已被撤銷，或組織不允許此帳戶使用 Claude Code。需要 Agent SDK v0.3.293 或更新版本 |
| `sandbox_required_unavailable` | [`failIfUnavailable`](#sandboxsettings) 已開啟且沙箱無法啟動。`errors` 中的文字以 `Set sandbox.failIfUnavailable=false to allow unsandboxed execution.` 結尾。需要 Agent SDK v0.3.314 或更新版本 |

### `SDKSystemMessage`

系統初始化訊息。

```typescript theme={null}
type SDKSystemMessage = {
  type: "system";
  subtype: "init";
  uuid: UUID;
  session_id: string;
  agents?: string[];
  apiKeySource: ApiKeySource;
  betas?: string[];
  claude_code_version: string;
  cwd: string;
  tools: string[];
  mcp_servers: {
    name: string;
    status: string;
    source?: string;
  }[];
  model: string;
  permissionMode: PermissionMode;
  slash_commands: string[];
  terminal_slash_commands?: string[];
  output_style: string;
  skills: string[];
  plugins: { name: string; path: string }[];
  plugin_errors?: {
    plugin: string;
    type: string;
    message: string;
    path?: string;
  }[];
  fast_mode_state?: FastModeState;
  fast_mode_disabled_reason?: FastModeDisabledReason;
  effort?: "low" | "medium" | "high" | "xhigh" | "max" | null;
  capabilities?: string[];
};
```

`fast_mode_state` 回報工作階段的[快速模式](https://code.claude.com/docs/zh-TW/fast-mode.md)狀態。當有因素阻止快速模式時，`fast_mode_disabled_reason` 會指名阻止它的檢查；該欄位需要 Claude Code v2.1.219 或更新版本。關於原因代碼及其含義，請參閱結果訊息上的 [`fast_mode_disabled_reason`](#sdkresultmessage)。

`terminal_slash_commands` 指名 `slash_commands` 中介面綁定於本機終端機的項目，例如 `exit`。您可以像傳送 `slash_commands` 中的任何其他項目一樣傳送它們；此欄位的存在是為了讓遠端或行動用戶端能將它們從命令選單中隱藏。此欄位僅在非空時存在，需要 Agent SDK v0.3.229 或更新版本。

* 每個 `mcp_servers` 項目上的 `source`：伺服器定義的來源，其值與 [`McpServerStatus`](#mcpserverstatus) 的 `source` 相同。需要 Agent SDK v0.3.274 或更新版本。
* `effort`：為工作階段下一個回合設定的 [effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)，或在 Claude Code 未送出任何等級時為 `null`。Claude Code 只在其傳送給 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 用戶端的 init 訊息上設定此欄位，並在您的應用程式讀取的 init 訊息中省略它。需要 Agent SDK v0.3.234 或更新版本。

`capabilities` 陣列指名此 CLI 實作的協定行為，讓您可以進行功能偵測，而不是比較 `claude_code_version` 字串。這是一個開放集合：請忽略您不認識的值，並檢查您所依賴之行為對應的特定功能。此欄位需要 Claude Code v2.1.205 或更新版本，在較早的 CLI 上不存在。

| 功能 | 含義 |
| - | - |
| `interrupt_receipt_v1` | [`interrupt()`](#query-object) 會以 [`SDKControlInterruptResponse`](#sdkcontrolinterruptresponse) 收據解析，其中列出中斷到達時仍待處理的訊息 |
| `interrupt_cancel_queued_v1` | `interrupt` 控制請求會遵循 `cancel_queued: true`，取消收據原本會列在 `still_queued` 下的訊息，並改為列在 `cancelled` 下。請參閱 [`SDKControlInterruptResponse`](#sdkcontrolinterruptresponse)。需要 Claude Code v2.1.219 或更新版本 |
| `sdk_mcp_manifests` | `initialize` 控制請求接受 `sdkMcpServerManifests`，即從您程序內 [SDK MCP 伺服器](https://code.claude.com/docs/zh-TW/agent-sdk/custom-tools.md)擷取的 MCP 交握結果。Claude Code 在 v2.1.286 或更新版本中宣告此 capability |
| `sdk_mcp_tools_list_changed` | 來自 [SDK MCP 伺服器](https://code.claude.com/docs/zh-TW/agent-sdk/custom-tools.md)的 `tools/list_changed` 通知會讓 Claude Code 重新列出該伺服器的工具，因此伺服器在工作階段中途新增的工具能送達 Claude。Claude Code 在 v2.1.286 或更新版本中宣告此 capability |

`plugin_errors` 陣列列出外掛載入失敗。項目描述的可能是未載入且不在 `plugins` 中的外掛，或是載入時缺少其中某部分（例如其 hooks 檔案）的外掛。沒有任何失敗時，會省略此鍵。`SDKSystemMessage` 在 Agent SDK v0.3.283 或更新版本中宣告 `plugin_errors`。

當您 [`plugins` 選項](#options)中的目錄或封存檔本身無法載入時，項目的 `plugin` 欄位會保存位置標籤（例如 `inline[0]`），而不是外掛名稱。例如，當路徑不存在或 manifest 無效時，就會發生這種情況。請透過其 `path` 欄位將此類項目與您的選項對應。

下表列出每個 `plugin_errors` 項目的欄位。

| 欄位 | 類型 | 描述 |
| - | - | - |
| `plugin` | `string` | 失敗外掛的 ID；當外掛目錄或封存檔本身無法載入時，則為位置標籤，例如 `inline[0]` |
| `type` | `string` | 來自開放集合的錯誤類別，例如 `path-not-found` 或 `manifest-validation-error`。請將您不認識的值視為一般失敗 |
| `message` | `string` | 描述失敗的顯示文字 |
| `path` | `string` | 僅當外掛目錄或封存檔本身無法載入時存在。為其絕對路徑，您 `plugins` 選項中的相對路徑會以 [`cwd`](#options) 選項為基準解析 |

### `SDKPartialAssistantMessage`

串流部分訊息（僅在 `includePartialMessages` 為 true 時）。

`parent_tool_use_id` 欄位一律為 `null`：串流事件僅針對主工作階段發出。若要歸屬 subagent，請使用完整訊息（其帶有 [`agent_id`](#sdkassistantmessage) 和 `parent_tool_use_id`），或啟用 [`forwardSubagentText`](#options) 以完整訊息形式接收 subagent 的文字和思考內容。

```typescript theme={null}
type SDKPartialAssistantMessage = {
  type: "stream_event";
  event: BetaRawMessageStreamEvent; // From Anthropic SDK
  parent_tool_use_id: string | null;
  uuid: UUID;
  session_id: string;
  ttft_ms?: number; // Time to first token in ms, present only on message_start events
  user_message_uuid?: string;
  user_message_uuids?: string[];
  resume_reason?: string;
};
```

Claude Code 會在符合 [`user_message_uuid`](#user_message_uuid) 所述條件時，於回合中第一個非 ping 的串流事件上設定 `user_message_uuid` 和 `user_message_uuids`，並在回合所回答的訊息改變時再次設定。當該回合是接續因重新啟動而中斷的回合時，帶有這些欄位的串流事件也會帶有 [`resume_reason`](#resume_reason)。

### `SDKCompactBoundaryMessage`

表示對話壓縮邊界的訊息。

```typescript theme={null}
type SDKCompactBoundaryMessage = {
  type: "system";
  subtype: "compact_boundary";
  uuid: UUID;
  session_id: string;
  compact_metadata: {
    trigger: "manual" | "auto";
    pre_tokens: number;
  };
};
```

### `SDKInformationalMessage`

由迴圈發出的通用文字橫幅。攜帶 Claude Code 提出的警告、通知和其他非錯誤狀態行，以及 hook 回饋，例如 `UserPromptSubmit` hook 的封鎖原因。

在 Claude Code v2.1.227 或更新版本上，hook 的 [`systemMessage`](https://code.claude.com/docs/zh-TW/hooks#json-output) 可能以此訊息到達，每一行都會加上 hook 名稱作為前綴，例如 `PostToolUse:Bash says:`。hooks 頁面上每個[事件的章節](https://code.claude.com/docs/zh-TW/hooks.md#hook-events)會說明輸出如何呈現。

請以給定的 `level` 將 `content` 呈現為純文字。

```typescript theme={null}
type SDKInformationalMessage = {
  type: "system";
  subtype: "informational";
  content: string;
  level: "info" | "notice" | "suggestion" | "warning";
  tool_use_id?: string;
  prevent_continuation?: boolean;
  tag?: string;
  uuid: UUID;
  session_id: string;
};
```

### `SDKWorkerShuttingDownMessage`

在工作程序正常關閉時發出，讓遠端用戶端可以顯示工作程序結束的原因，而不必等待心跳逾時。`reason` 是由主機 CLI 設定的簡短 snake\_case 字串，例如 `"host_exit"` 或 `"remote_control_disabled"`。僅在即時串流時據此採取動作。恢復的工作階段會重播此訊息過去的實例，因此在這種情況下請忽略它們。

```typescript theme={null}
type SDKWorkerShuttingDownMessage = {
  type: "system";
  subtype: "worker_shutting_down";
  reason: string;
  uuid: UUID;
  session_id: string;
};
```

### `SDKPluginInstallMessage`

外掛安裝進度事件。在設定 [`CLAUDE_CODE_SYNC_PLUGIN_INSTALL`](https://code.claude.com/docs/zh-TW/env-vars) 時發出，讓您的 Agent SDK 應用程式可以在第一個回合之前追蹤市集外掛的安裝。`started` 和 `completed` 狀態標示整體安裝的開始與結束。`installed` 和 `failed` 狀態回報個別市集，並包含 `name`。

```typescript theme={null}
type SDKPluginInstallMessage = {
  type: "system";
  subtype: "plugin_install";
  status: "started" | "installed" | "failed" | "completed";
  name?: string;
  error?: string;
  uuid: UUID;
  session_id: string;
};
```

### `SDKPermissionDeniedMessage`

當權限系統在沒有互動式權限提示的情況下拒絕工具呼叫時發出的串流事件。使用它在您的 UI 中即時呈現拒絕，而不是只觀察隨後的 `is_error` 工具結果。它回報哪些拒絕，取決於執行如何處理權限提示：

* **使用 [`canUseTool`](#canusetool) 回呼**且採用預設的 [`permissionPrompts: 'host'`](#options)：權限提示會交給您的回呼，此事件回報 Claude Code 不呼叫回呼而自行決定的拒絕。
* **兩者皆無**：單純的 `-p` 執行，或未設定 `canUseTool` 也未設定 `permissionPromptToolName` 的 `query()`，會拒絕任何本應提示的工具呼叫，除非 [`PermissionRequest` hook](https://code.claude.com/docs/zh-TW/hooks-guide#limitations) 允許它；此事件會回報這些拒絕以及 Claude Code 自行決定的拒絕。在 v2.1.223 之前，Claude Code 在沒有回呼的執行中不會發出此事件。
* **使用 MCP 提示工具**（透過 `permissionPromptToolName` 或 [`--permission-prompt-tool`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 旗標設定）且採用預設的 `permissionPrompts: 'host'`：Claude Code 完全不會發出此事件，即使是它自行決定的規則拒絕也不會。
* **使用 [`permissionPrompts: 'none'`](#options)**：即使同時設定了 `canUseTool` 或 MCP 提示工具，Claude Code 仍會拒絕原本會提示的呼叫，此事件會回報這些拒絕以及 Claude Code 自行決定的拒絕。需要 Claude Code v2.1.259 或更新版本。

在任何設定下，此事件都會略過在 `PreToolUse` hook 路徑上決定的拒絕，無論是 hook 本身拒絕了呼叫，還是拒絕規則覆寫了 hook 的允許或詢問決定。此事件也是盡力而為：Claude Code 偶爾會記錄拒絕而不發出此事件，因此[結果訊息](#sdkresultmessage)上的 `permission_denials` 才是權威記錄。

```typescript theme={null}
type SDKPermissionDeniedMessage = {
  type: "system";
  subtype: "permission_denied";
  tool_name: string;
  tool_use_id: string;
  agent_id?: string;
  decision_reason_type?: string;
  decision_reason?: string;
  message: string;
  uuid: UUID;
  session_id: string;
};
```

| 欄位 | 類型 | 描述 |
| - | - | - |
| `tool_name` | `string` | 被拒絕之工具的名稱 |
| `tool_use_id` | `string` | 此拒絕所回應之 `tool_use` 區塊的 ID |
| `agent_id` | `string` | 當被拒絕的呼叫源自 subagent 內部時，該 subagent 的 ID。對應 `can_use_tool` 上的欄位，以便在主機端進行路由 |
| `decision_reason_type` | `string` | 做出決定之元件的判別值，例如 `"rule"`、`"mode"`、`"classifier"` 或 `"asyncAgent"` |
| `decision_reason` | `string` | 做出決定之元件提供的人類可讀原因（若有） |
| `message` | `string` | 在 `tool_result` 中傳回給模型的拒絕訊息 |

### `SDKPermissionDenial`

關於被拒絕之工具使用的資訊。

```typescript theme={null}
type SDKPermissionDenial = {
  tool_name: string;
  tool_use_id: string;
  tool_input: Record<string, unknown>;
};
```

### `SDKContextUsage`

`/context` 報告的結構化形式，以 `context_usage` 攜帶在傳遞 `/context` 結果的 [`SDKAssistantMessage`](#sdkassistantmessage) 上。Agent SDK v0.3.232 及更新版本會匯出此類型。與 [`SDKControlGetContextUsageResponse`](#sdkcontrolgetcontextusageresponse) 不同，它只攜帶呈現使用情況明細所需的資料，不含 `color` 和 `gridRows` 等顯示欄位。Claude Code 使用不會出現在訊息串流中的 token 計數 API 請求來計算報告；請參閱[這些請求的處理方式](#sdkcontrolgetcontextusageresponse)。

```typescript theme={null}
type SDKContextUsage = {
  model: string;
  total_tokens: number;
  raw_max_tokens: number;
  percentage: number;
  over_limit?: {
    tokens_over: number;
    kind: "hard_limit" | "compaction_window";
  };
  categories: SDKContextUsageCategory[];
  mcp_tools: {
    name: string;
    server_name: string;
    tokens: number;
  }[];
  memory_files: {
    path: string;
    type: string;
    tokens: number;
  }[];
  agents: {
    agent_type: string;
    source: string;
    tokens: number;
  }[];
  skills?: {
    name: string;
    source: string;
    plugin_name?: string;
    tokens: number;
  }[];
};
```

下表列出 Claude Code 在每個欄位中放入的內容。從 `model` 到 `over_limit` 的欄位描述整個工作階段，集合欄位則將 token 歸屬到個別項目。

| 欄位 | 類型 | 描述 |
| - | - | - |
| `model` | `string` | Claude Code 據以計算使用情況的主迴圈模型，而非 subagent 的模型 |
| `total_tokens` | `number` | Claude Code 對使用中 token 的估計。不受視窗限制，因此當工作階段超過上限時可能超過 `raw_max_tokens` |
| `raw_max_tokens` | `number` | 模型的上下文視窗，或在適用時採用較低的[自動壓縮視窗](https://code.claude.com/docs/zh-TW/model-config.md#context-window-and-auto-compaction)，例如您設定的視窗，或 Claude Code 對某些具有 1M token 視窗之模型套用的 200K 邊界。Claude Code 以此視窗衡量 `total_tokens` |
| `percentage` | `number` | `total_tokens` 佔 `raw_max_tokens` 的四捨五入百分比，因此當工作階段超過上限時可能超過 100 |
| `over_limit` | `object` | 僅當 `total_tokens` 超過 `raw_max_tokens` 時存在。`tokens_over` 是超出的數量，`kind` 說明 Claude Code 如何判定視窗 |
| `categories` | [`SDKContextUsageCategory`](#sdkcontextusagecategory)`[]` | 依類別之使用情況明細中的每一列各一個項目 |
| `mcp_tools` | `object[]` | 歸屬於每個 MCP 工具的 token，附上其傳輸名稱（例如 `mcp__linear__create_issue`）及其 `server_name` |
| `memory_files` | `object[]` | 歸屬於每個已載入記憶檔案的 token，附上其 `path`，以及 `type` 中的來源標籤，例如 `Project` 或 `User` |
| `agents` | `object[]` | 歸屬於每個自訂 subagent 定義的 token，附上來源識別碼，例如 `projectSettings`、`userSettings` 或 `plugin`。不列出內建 subagent |
| `skills` | `object[]` | 歸屬於 skill 清單中每個 skill 的 token，附上來源識別碼；對於外掛 skill，`plugin_name` 中為外掛名稱。沒有任何 skill 佔用 token 時不存在 |

`over_limit.kind` 記錄 Claude Code 如何判定視窗，而不是 API 是否接受下一個請求：

* `hard_limit`：視窗是 Claude Code 認定的模型本身上限，超過後 API 會拒絕請求
* `compaction_window`：視窗是壓縮原則所用的視窗，可能與模型的上限一致，也可能不一致

Claude Code 以增量方式演進此類型，以選用欄位加入新資料，而不是重塑現有欄位。請讀取您已知的欄位，並忽略任何您不認識的欄位。

### `SDKContextUsageCategory`

`/context` 依類別之使用情況明細中的一列。

```typescript theme={null}
type SDKContextUsageCategory = {
  name: string;
  tokens: number;
  kind: "used" | "free" | "buffer" | "deferred";
};
```

下表列出 Claude Code 在一列之每個欄位中放入的內容。

| 欄位 | 類型 | 描述 |
| - | - | - |
| `name` | `string` | 該列的顯示名稱，與 `/context` 列印的相同，例如 `Messages`。請依 `kind` 而非名稱分類各列 |
| `tokens` | `number` | 該列的 token 數量。列的 token 數可以為零 |
| `kind` | `string` | 該列代表的內容：`used`、`free`、`buffer` 或 `deferred` |

每個 `kind` 值說明該列的 token 是什麼：

* `used`：佔用上下文視窗的內容
* `free`：剩餘的視窗
* `buffer`：壓縮保留空間
* `deferred`：Claude Code 保留在視窗之外、不計入使用情況計算的工具 schema，僅列出供您參考

### `SDKUsageReport`

`/usage` 報告的結構化形式，以 `usage_report` 的形式帶在傳遞 `/usage` 結果的 [`SDKAssistantMessage`](#sdkassistantmessage) 上。Agent SDK v0.3.273 及更新版本會匯出此類型。此類型為實驗性：其形狀可能會變更。

```typescript theme={null}
type SDKUsageReport = {
  session: {
    total_cost_usd: number;
    total_api_duration_ms: number;
    total_duration_ms: number;
    total_lines_added: number;
    total_lines_removed: number;
    model_usage: { [modelName: string]: ModelUsage };
  };
  rate_limits: {
    limits:
      | {
          kind: string;
          group: string;
          percent: number;
          resets_at: string | null;
          scope?: {
            model?: { display_name: string } | null;
            surface?: { display_name: string } | null;
          } | null;
          severity: string;
          is_active: boolean;
        }[]
      | null;
    extra_usage?: {
      is_enabled: boolean;
      monthly_limit: number | null;
      used_credits: number | null;
      utilization: number | null;
      currency?: string | null;
    } | null;
  } | null;
};
```

頂層欄位為 `session` 和 `rate_limits`：

* `session`：Claude Code 持續累計的成本與用量總計，讀取自與 [`SDKResultMessage`](#sdkresultmessage) 上的 `total_cost_usd` 和 `modelUsage` 相同的帳本。每個 `model_usage` 項目都是一個 [`ModelUsage`](#modelusage)。
* `rate_limits`：`limits` 中的方案用量列，以及 `extra_usage` 中的用量點數支出。當 Claude Code 無法取得方案用量時（例如工作階段的 OAuth token 缺少 `user:profile` 範圍），此欄位為 `null`。

Claude Code 依據 token 數在本機計算 `session.total_cost_usd`，因此它是估算值，而非您方案的計費金額。伺服器回報的用量點數支出是另外的 `extra_usage` 區塊。關於準確度的注意事項，請參閱[追蹤成本與用量](https://code.claude.com/docs/zh-TW/agent-sdk/cost-tracking.md)。

`limits` 依伺服器傳送的原樣包含伺服器的用量列：適用哪些計量、其範圍、標籤、嚴重程度和順序都由伺服器決定，因此請依原樣呈現各列。

* 空陣列表示伺服器未回報任何計量。
* `null` 表示 Claude Code 沒有可回報的列。

`limits` 的每一列描述一個用量計量：

| 欄位 | 類型 | 說明 |
| - | - | - |
| `kind` | `string` | 伺服器的計量種類，例如 `session`、`weekly_all` 或 `weekly_scoped`。請依此分類列，絕不要依標籤分類 |
| `group` | `string` | 伺服器的列群組，例如 `session` 或 `weekly`。各列會依伺服器的順序分組呈現於其下 |
| `percent` | `number` | 視窗已使用的比例，0-100 |
| `resets_at` | `string \| null` | 視窗重設時的 ISO 8601 時間戳記 |
| `scope` | `object \| null` | 選用。有範圍的列所針對的對象，即模型或使用介面，並帶有伺服器的顯示標籤 |
| `severity` | `string` | 伺服器對該列的判讀，用於計量的顏色，例如 `normal`、`warning` 或 `critical` |
| `is_active` | `boolean` | 在伺服器選定供單一值指示器顯示的列上為 `true` |

在 Agent SDK v0.3.277 之前，此類型將 `severity` 和 `is_active` 宣告為選用且可為 null，列可能在不帶這兩個欄位的情況下抵達。

`extra_usage` 是伺服器回報之該計費期間的[用量點數](https://support.claude.com/en/articles/12429409-extra-usage-for-paid-claude-plans)支出與上限，當方案有用量點數時存在。金額以 `currency` 的最小單位表示，美元為美分。

* 當此帳戶沒有自己的支出上限時，`monthly_limit` 為 `null`。在 Team 和 Enterprise 方案上，請勿將 `null` 呈現為無限制。
* 當用量點數無法支付請求時，`is_enabled` 為 `false`。

### `SDKMessageOrigin`

使用者角色訊息的來源。它在 [`SDKUserMessage`](#sdkusermessage) 上以 `origin` 出現，並會轉送到對應的 [`SDKResultMessage`](#sdkresultmessage)，讓您可以得知是什麼觸發了某個回合。

```typescript theme={null}
type SDKMessageOrigin =
  | { kind: "human" }
  | { kind: "channel"; server: string }
  | {
      kind: "peer";
      from: string;
      fromMode?: "bypass" | "prompting";
      name?: string;
      fromSession?: string;
      senderTaskId?: string;
      body?: string;
      verifiedPeerPid?: number;
    }
  | {
      kind: "task-notification";
      subkind?: "scheduled-trigger" | "peer-send-message";
      fireReason?: string;
      runId?: string;
    }
  | { kind: "coordinator" }
  | { kind: "auto-continuation" }
  | { kind: "unclassified" };
```

| `kind` | 含義 |
| - | - |
| `human` | 來自最終使用者的直接輸入。如果您的應用程式將使用者輸入的內容轉送為使用者訊息，請明確將其 `origin` 設定為 `{ kind: "human" }`：Claude Code 會將沒有 `origin` 的使用者訊息視為未歸屬，而需要人類輸入之提示詞的檢查（例如 [`ultracode` 工作流程關鍵字](https://code.claude.com/docs/zh-TW/workflows#ask-for-a-workflow-in-your-prompt)）不會接受它。在 v2.1.210 之前，Claude Code 將使用者訊息上不存在的 `origin` 視為人類輸入。 |
| `channel` | 在[頻道](https://code.claude.com/docs/zh-TW/channels.md)上到達的訊息。`server` 是來源 MCP 伺服器名稱。 |
| `peer` | 來自另一個 agent 的訊息：程序內的[隊員](https://code.claude.com/docs/zh-TW/agent-teams.md)，或[跨工作階段對等端](https://code.claude.com/docs/zh-TW/cross-session-messaging.md)，也就是您的另一個 Claude Code 工作階段。請參閱[對等來源欄位](#peer-origin-fields)以了解各欄位的語意和信任模型。 |
| `task-notification` | 為沒有新使用者提示詞的傳遞而注入的合成回合，例如已完成的背景任務；請參閱 [`SDKTaskNotificationMessage`](#sdktasknotificationmessage) 以了解該分支。您的應用程式[宣告為排程執行](#declare-a-scheduled-run)的提示詞也攜帶此 kind。選用的 `subkind` 標示引發通知的來源。請參閱[任務通知子類型](#task-notification-subkinds)。 |
| `coordinator` | 來自 [agent team](https://code.claude.com/docs/zh-TW/agent-teams.md) 中團隊協調者的訊息。 |
| `auto-continuation` | 當工作階段在沒有新使用者輸入的情況下繼續時注入的合成回合，例如觸發後續提示詞的命令結果。 |
| `unclassified` | 無法判定來源的注入回合。需要 Claude Code v2.1.223 或更新版本。當 Claude Code 收到帶有 `isSynthetic: true` 的 [`SDKUserMessage`](#sdkusermessage)，且無法將其歸類為任何其他 `kind` 時，會在訊息到達時設定此 kind，並向模型將該回合表述為非使用者來源，而不是將其視為人類輸入。您的應用程式不應設定此值。 |

### 任務通知子類型

當 Claude Code 將任務通知傳遞到工作階段時，若 Anthropic 伺服器已驗證該通知的來源，它會在通知的 `origin` 上設定 `subkind`。當您的應用程式自行[將訊息宣告為排程執行](#declare-a-scheduled-run)時，它也會設定 `subkind`，這需要 TypeScript Agent SDK v0.3.280 或更新版本。`subkind` 需要 Claude Code v2.1.213 或更新版本，其值為下列兩者之一：

* `scheduled-trigger`：該通知是[雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md)所儲存的提示詞，因任務的某個觸發條件觸發而傳遞：其排程、其 [API 觸發器](https://code.claude.com/docs/zh-TW/routines.md#add-an-api-trigger)、其 [GitHub 觸發器](https://code.claude.com/docs/zh-TW/routines.md#add-a-github-trigger)，或 **Run now**。您的應用程式[宣告為排程執行](#declare-a-scheduled-run)的提示詞也會帶有此值。Claude Code 會向模型將其表述為工作階段被指派的任務，其附帶的通知與[其他任務通知所附帶的通知](#sdktasknotificationmessage)不同。
* `peer-send-message`：通知是您的另一個工作階段使用伺服器端 `send_message` 工具傳送的訊息，此工具是[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)彼此傳訊所用，而非[跨工作階段 `SendMessage` 工具](https://code.claude.com/docs/zh-TW/cross-session-messaging)，且 Anthropic 伺服器已驗證兩個工作階段屬於同一個私人工作階段群組。需要 Claude Code v2.1.224 或更新版本。未經伺服器以此方式驗證的 `send_message` 傳遞不會有 subkind。

其他所有任務通知都沒有 `subkind`。這包括傳遞到工作階段的 [PR 活動](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#how-claude-responds-to-pr-activity)，以及已完成任務之類的背景事件。來自[跨工作階段 `SendMessage` 工具](https://code.claude.com/docs/zh-TW/cross-session-messaging)的訊息根本不是任務通知：無論它們來自同一台機器上的工作階段，還是透過 Anthropic 伺服器來自另一台機器，Claude Code 都會給予它們 `kind: "peer"` 和[對等來源欄位](#peer-origin-fields)。

`fireReason` 說明 `scheduled-trigger` 通知觸發的原因，以簡短的小寫 token 表示，例如 `scheduled`、`manual`、`retry`、`catch_up` 或 `api`。Anthropic 伺服器會在[雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md)的傳遞上設定此值，您的應用程式在宣告排程執行時也會設定此值。若兩者皆未傳送，則此欄位不存在。需要 TypeScript Agent SDK v0.3.280 或更新版本。

一個背景任務可以在同一個 `task_id` 下執行多次，例如當 Claude [繼續執行 subagent](https://code.claude.com/docs/zh-TW/agent-sdk/subagents.md#resume-subagents) 時。每次執行都有其自己的 [`run_id`](#sdktaskstartedmessage)。當某次執行的通知以使用者訊息的形式送達您的工作階段時，該訊息 `task-notification` origin 上的 `runId` 會保有相同的值。通知可能在任務的下一次執行開始後才送達，但它仍帶有較早那次執行的 ID。若要判斷某個回合屬於哪次執行，請比較 `runId`，而非 `task_id`。需要 TypeScript Agent SDK v0.3.292 或更新版本。

#### 宣告排程執行

如果您的應用程式依自己的排程執行提示詞，請宣告每次執行，讓 Claude Code 向模型將該回合表述為排程任務，而不是來自使用者的即時輸入。請在 [`env`](#options) 中將 `CLAUDE_CODE_HOST_SCHEDULED_RUN` 設定為 `1` 來啟動工作階段，然後以 `origin: { kind: "task-notification", subkind: "scheduled-trigger", fireReason: "scheduled" }` 且不帶 `isSynthetic` 傳送該次執行的 [`SDKUserMessage`](#sdkusermessage)。在未設定該變數而啟動的程序中，Claude Code 會忽略此宣告。在環境中帶有 [`CLAUDECODE`](https://code.claude.com/docs/zh-TW/env-vars) 或 `CLAUDE_CODE_CHILD_SESSION` 的程序中，也會忽略它。只有當值為 1 到 32 個小寫字母或底線時，Claude Code 才會保留 `fireReason`。需要 TypeScript Agent SDK v0.3.280 或更新版本。

### 對等來源欄位

`peer` 來源用於識別是哪個 agent 傳送了訊息：以 `SendMessage` 傳送給 `main` 的程序內[隊員](https://code.claude.com/docs/zh-TW/agent-teams.md)，或[跨工作階段對等端](https://code.claude.com/docs/zh-TW/cross-session-messaging.md)，即您的另一個 Claude Code 工作階段。在 macOS 和 Linux 上，跨工作階段對等端需要 Claude Code v2.1.224 或更新版本；原生 Windows 的需求請參閱[跨工作階段訊息的可用性](https://code.claude.com/docs/zh-TW/cross-session-messaging.md#availability)。跨工作階段對等端可以在同一台機器上執行，或者當其訊息透過 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 抵達時，在[您的另一台機器](https://code.claude.com/docs/zh-TW/cross-session-messaging.md#message-sessions-on-other-machines)上執行。

* `from`：隊員的名稱，或跨工作階段對等端的傳送者位址。對於[單向跨機器訊息](https://code.claude.com/docs/zh-TW/cross-session-messaging.md#message-sessions-on-other-machines)，傳送者沒有回覆位址，`from` 為 `"unknown"`。此值由傳送者撰寫；`verifiedPeerPid` 才是經驗證的身分。
* `fromMode`：傳送端工作階段的權限類別，`bypass` 或 `prompting`，由在您的工作階段之間轉送對等訊息的主機宣告，例如[桌面應用程式](https://code.claude.com/docs/zh-TW/desktop.md#work-across-sessions)。Claude Code 會在接收端工作階段套用[傳入控制](https://code.claude.com/docs/zh-TW/cross-session-messaging.md#control-inbound-messages)時讀取它。需要 Agent SDK v0.3.234 或更新版本。
* `senderTaskId`：隊員的任務 ID。對於跨工作階段對等端不存在。
* `name`：傳送者的顯示名稱，經 Claude Code 正規化：它會移除 Unicode 控制、格式、代理（surrogate）以及行或段落分隔符號的碼位，然後修剪結果，並將其限制在 64 個碼位內，超出時加上省略號。需要 Claude Code v2.1.205 或更新版本。
* `body`：已移除 peer 信封的解碼訊息本文，與模型所見內容逐位元組一致。單一隊員訊息時存在，多則訊息合併時不存在；對於跨工作階段對等端，僅在回合恰好是一個由 Claude Code 形成的 peer 信封時存在。請直接呈現 `name` 和 `body`，而非重新剖析訊息文字。在 v2.1.299 之前，合併的訊息會保留第一則訊息的 `body`。需要 Claude Code v2.1.205 或更新版本。
* `fromSession`：傳送者可由主機開啟的工作階段 ID，由傳送者的主機設定，讓您的 UI 可以連結回傳送端工作階段。與 `from` 一樣，它是傳送者自行宣稱的：僅將其用作導覽目標，不要將其視為傳送者身分的證明。需要 Claude Code v2.1.216 或更新版本。
* `verifiedPeerPid`：連線到此工作階段之跨工作階段傳訊 socket 的程序的程序 ID，由核心驗證，並從連線本身讀取，絕不從 payload 讀取。請使用它而非 `from` 來識別傳送者：同一使用者的任何程序都能偽造 `from`。當 Claude Code 無法驗證時，此欄位不存在，例如在 Windows 上或非 socket 的傳入途徑，因此值不存在即表示傳送者未經驗證。對於轉送的流量，它識別的是轉送者而非訊息的作者，且程序 ID 可能被重複使用，因此請將其視為來源資訊，而不是驗證 token。需要 Claude Code v2.1.216 或更新版本。

## Hook 類型

有關使用 hook 的綜合指南，包括示例和常見模式，見 [Hooks 指南](https://code.claude.com/docs/zh-TW/agent-sdk/hooks.md)。

### `HookEvent`

可用的 hook 事件。

```typescript theme={null}
type HookEvent =
  | "PreToolUse"
  | "PostToolUse"
  | "PostToolUseFailure"
  | "PostToolBatch"
  | "Notification"
  | "UserPromptSubmit"
  | "UserPromptExpansion"
  | "SessionStart"
  | "SessionEnd"
  | "Stop"
  | "StopFailure"
  | "SubagentStart"
  | "SubagentStop"
  | "PreCompact"
  | "PostCompact"
  | "PreModelSwitch"
  | "PostModelSwitch"
  | "PermissionRequest"
  | "PermissionDenied"
  | "Setup"
  | "TeammateIdle"
  | "TaskCreated"
  | "TaskCompleted"
  | "Elicitation"
  | "ElicitationResult"
  | "ConfigChange"
  | "DirectoryAdded"
  | "WorktreeCreate"
  | "WorktreeRemove"
  | "InstructionsLoaded"
  | "CwdChanged"
  | "FileChanged"
  | "MessageDisplay";
```

### `HookCallback`

Hook 回調函數類型。

```typescript theme={null}
type HookCallback = (
  input: HookInput, // 所有 hook 輸入類型的聯合
  toolUseID: string | undefined,
  options: { signal: AbortSignal }
) => Promise<HookJSONOutput>;
```

### `HookCallbackMatcher`

帶有可選匹配器的 Hook 配置。

```typescript theme={null}
interface HookCallbackMatcher {
  matcher?: string;
  hooks: HookCallback[];
  timeout?: number; // 此 matcher 中所有 hook 的逾時時間（秒）
  onFailure?: "continue" | "block"; // 當回呼失敗時，"block" 會阻止該動作
}
```

若要判斷 `onFailure` 涵蓋哪些情況，請參閱[在回呼失敗時阻止動作](https://code.claude.com/docs/zh-TW/agent-sdk/hooks.md#block-the-action-when-a-callback-fails)。

### `HookInput`

所有 hook 輸入類型的聯合類型。

```typescript theme={null}
type HookInput =
  | PreToolUseHookInput
  | PostToolUseHookInput
  | PostToolUseFailureHookInput
  | PostToolBatchHookInput
  | PermissionDeniedHookInput
  | NotificationHookInput
  | UserPromptSubmitHookInput
  | UserPromptExpansionHookInput
  | SessionStartHookInput
  | SessionEndHookInput
  | StopHookInput
  | StopFailureHookInput
  | SubagentStartHookInput
  | SubagentStopHookInput
  | PreCompactHookInput
  | PostCompactHookInput
  | PreModelSwitchHookInput
  | PostModelSwitchHookInput
  | PermissionRequestHookInput
  | SetupHookInput
  | TeammateIdleHookInput
  | TaskCreatedHookInput
  | TaskCompletedHookInput
  | ElicitationHookInput
  | ElicitationResultHookInput
  | ConfigChangeHookInput
  | InstructionsLoadedHookInput
  | DirectoryAddedHookInput
  | WorktreeCreateHookInput
  | WorktreeRemoveHookInput
  | CwdChangedHookInput
  | FileChangedHookInput
  | MessageDisplayHookInput;
```

### `BaseHookInput`

所有 hook 輸入類型擴展的基本介面。

```typescript theme={null}
type BaseHookInput = {
  session_id: string;
  transcript_path: string;
  cwd: string;
  prompt_id?: string;
  permission_mode?: string;
  effort?: { level: string };
  agent_id?: string;
  agent_type?: string;
};
```

`prompt_id` 欄位是一個 UUID，用於識別目前正在處理的使用者提示。它與 [OpenTelemetry 事件上的 `prompt.id` 屬性](https://code.claude.com/docs/zh-TW/monitoring-usage#event-correlation-attributes)相符，在第一個使用者輸入之前不存在。需要 Claude Code v2.1.196 或更新版本。

#### `PreToolUseHookInput`

```typescript theme={null}
type PreToolUseHookInput = BaseHookInput & {
  hook_event_name: "PreToolUse";
  tool_name: string;
  tool_input: unknown;
  tool_use_id: string;
  mcp_server?: McpServerProvenance;
};
```

當工具來自 MCP 伺服器時，`mcp_server` 會出現；見 [`McpServerProvenance`](#mcpserverprovenance)。`PostToolUse`、`PostToolUseFailure`、`PermissionRequest` 和 `PermissionDenied` 輸入攜帶相同的欄位。此欄位需要 Agent SDK v0.3.274 或更新版本。

#### `PostToolUseHookInput`

```typescript theme={null}
type PostToolUseHookInput = BaseHookInput & {
  hook_event_name: "PostToolUse";
  tool_name: string;
  tool_input: unknown;
  tool_response: unknown;
  tool_use_id: string;
  duration_ms?: number;
  mcp_server?: McpServerProvenance;
};
```

#### `PostToolUseFailureHookInput`

```typescript theme={null}
type PostToolUseFailureHookInput = BaseHookInput & {
  hook_event_name: "PostToolUseFailure";
  tool_name: string;
  tool_input: unknown;
  tool_use_id: string;
  error: string;
  is_interrupt?: boolean;
  duration_ms?: number;
  mcp_server?: McpServerProvenance;
};
```

#### `PostToolBatchHookInput`

在批次中的每個工具呼叫都已解決後、下一個模型請求之前觸發一次。`tool_response` 攜帶序列化的 `tool_result` 內容，模型會看到；其形狀與 `PostToolUseHookInput` 的結構化 `Output` 物件不同。

```typescript theme={null}
type PostToolBatchHookInput = BaseHookInput & {
  hook_event_name: "PostToolBatch";
  tool_calls: PostToolBatchToolCall[];
};

type PostToolBatchToolCall = {
  tool_name: string;
  tool_input: unknown;
  tool_use_id: string;
  tool_response?: unknown;
};
```

#### `PermissionDeniedHookInput`

```typescript theme={null}
type PermissionDeniedHookInput = BaseHookInput & {
  hook_event_name: "PermissionDenied";
  tool_name: string;
  tool_input: unknown;
  tool_use_id: string;
  reason: string;
  mcp_server?: McpServerProvenance;
};
```

#### `NotificationHookInput`

```typescript theme={null}
type NotificationHookInput = BaseHookInput & {
  hook_event_name: "Notification";
  message: string;
  title?: string;
  notification_type: string;
};
```

#### `UserPromptSubmitHookInput`

```typescript theme={null}
type UserPromptSubmitHookInput = BaseHookInput & {
  hook_event_name: "UserPromptSubmit";
  prompt: string;
  session_title?: string;
};
```

#### `UserPromptExpansionHookInput`

```typescript theme={null}
type UserPromptExpansionHookInput = BaseHookInput & {
  hook_event_name: "UserPromptExpansion";
  expansion_type: "slash_command" | "mcp_prompt";
  command_name: string;
  command_args: string;
  command_source?: string;
  prompt: string;
};
```

#### `SessionStartHookInput`

```typescript theme={null}
type SessionStartHookInput = BaseHookInput & {
  hook_event_name: "SessionStart";
  source: "startup" | "resume" | "clear" | "compact" | "fork";
  agent_type?: string;
  model?: string;
  session_title?: string;
};
```

#### `SessionEndHookInput`

```typescript theme={null}
type SessionEndHookInput = BaseHookInput & {
  hook_event_name: "SessionEnd";
  reason: ExitReason; // EXIT_REASONS 陣列中的字串
};
```

#### `StopHookInput`

```typescript theme={null}
type StopHookInput = BaseHookInput & {
  hook_event_name: "Stop";
  stop_hook_active: boolean;
  last_assistant_message?: string;
  background_tasks?: BackgroundTaskSummary[];
  session_crons?: SessionCronSummary[];
};
```

#### `StopFailureHookInput`

```typescript theme={null}
type StopFailureHookInput = BaseHookInput & {
  hook_event_name: "StopFailure";
  error: SDKAssistantMessageError;
  error_details?: string;
  last_assistant_message?: string;
};
```

#### `SubagentStartHookInput`

```typescript theme={null}
type SubagentStartHookInput = BaseHookInput & {
  hook_event_name: "SubagentStart";
  agent_id: string;
  agent_type: string;
};
```

#### `SubagentStopHookInput`

```typescript theme={null}
type SubagentStopHookInput = BaseHookInput & {
  hook_event_name: "SubagentStop";
  stop_hook_active: boolean;
  agent_id: string;
  agent_transcript_path: string;
  agent_type: string;
  last_assistant_message?: string;
  background_tasks?: BackgroundTaskSummary[];
  session_crons?: SessionCronSummary[];
};

type BackgroundTaskSummary = {
  id: string;
  type: string;
  status: string;
  description: string;
  command?: string;
  agent_type?: string;
  server?: string;
  tool?: string;
  name?: string;
};

type SessionCronSummary = {
  id: string;
  schedule: string;
  recurring: boolean;
  prompt: string;
};
```

#### `PreCompactHookInput`

```typescript theme={null}
type PreCompactHookInput = BaseHookInput & {
  hook_event_name: "PreCompact";
  trigger: "manual" | "auto";
  custom_instructions: string | null;
};
```

#### `PostCompactHookInput`

```typescript theme={null}
type PostCompactHookInput = BaseHookInput & {
  hook_event_name: "PostCompact";
  trigger: "manual" | "auto";
  compact_summary: string;
};
```

#### `PreModelSwitchHookInput`

在請求的模型切換生效之前觸發。`context_tokens` 和其後的欄位估計重新傳送對話到新模型的成本。如需完整的欄位說明和阻止語義，見 [PreModelSwitch](https://code.claude.com/docs/zh-TW/hooks.md#premodelswitch)。

```typescript theme={null}
type PreModelSwitchHookInput = BaseHookInput & {
  hook_event_name: "PreModelSwitch";
  from_model: string;
  to_model: string;
  requested_model: string | null;
  source: "command" | "picker" | "sdk";
  context_tokens: number;
  prompt_cache_warm: boolean;
  cache_ttl: "5m" | "1h";
  estimated_cache_write_usd: number;
  pricing: "configured" | "catalog" | "default";
};
```

#### `PostModelSwitchHookInput`

在工作階段的模型變更後觸發。它攜帶與 `PreModelSwitchHookInput` 相同的欄位，加上兩個額外的 `source` 值。見 [PostModelSwitch](https://code.claude.com/docs/zh-TW/hooks.md#postmodelswitch)。

```typescript theme={null}
type PostModelSwitchHookInput = BaseHookInput & {
  hook_event_name: "PostModelSwitch";
  from_model: string;
  to_model: string;
  requested_model: string | null;
  source: "command" | "picker" | "sdk" | "auto" | "resume";
  context_tokens: number;
  prompt_cache_warm: boolean;
  cache_ttl: "5m" | "1h";
  estimated_cache_write_usd: number;
  pricing: "configured" | "catalog" | "default";
};
```

#### `PermissionRequestHookInput`

```typescript theme={null}
type PermissionRequestHookInput = BaseHookInput & {
  hook_event_name: "PermissionRequest";
  tool_name: string;
  tool_input: unknown;
  permission_suggestions?: PermissionUpdate[];
  mcp_server?: McpServerProvenance;
};
```

#### `SetupHookInput`

```typescript theme={null}
type SetupHookInput = BaseHookInput & {
  hook_event_name: "Setup";
  trigger: "init" | "maintenance";
};
```

#### `TeammateIdleHookInput`

```typescript theme={null}
type TeammateIdleHookInput = BaseHookInput & {
  hook_event_name: "TeammateIdle";
  teammate_name: string;
  /** @deprecated 自 v2.1.178 起已棄用。攜帶工作階段衍生的團隊名稱；將被移除。 */
  team_name: string;
};
```

#### `TaskCreatedHookInput`

```typescript theme={null}
type TaskCreatedHookInput = BaseHookInput & {
  hook_event_name: "TaskCreated";
  task_id: string;
  task_subject: string;
  task_description?: string;
  teammate_name?: string;
  /** @deprecated 自 v2.1.178 起已棄用。攜帶工作階段衍生的團隊名稱；將被移除。 */
  team_name?: string;
};
```

#### `TaskCompletedHookInput`

```typescript theme={null}
type TaskCompletedHookInput = BaseHookInput & {
  hook_event_name: "TaskCompleted";
  task_id: string;
  task_subject: string;
  task_description?: string;
  teammate_name?: string;
  /** @deprecated 自 v2.1.178 起已棄用。攜帶工作階段衍生的團隊名稱；將被移除。 */
  team_name?: string;
};
```

#### `ElicitationHookInput`

```typescript theme={null}
type ElicitationHookInput = BaseHookInput & {
  hook_event_name: "Elicitation";
  mcp_server_name: string;
  message: string;
  mode?: "form" | "url";
  url?: string;
  elicitation_id?: string;
  requested_schema?: Record<string, unknown>;
};
```

#### `ElicitationResultHookInput`

```typescript theme={null}
type ElicitationResultHookInput = BaseHookInput & {
  hook_event_name: "ElicitationResult";
  mcp_server_name: string;
  elicitation_id?: string;
  mode?: "form" | "url";
  action: "accept" | "decline" | "cancel";
  content?: Record<string, unknown>;
};
```

#### `ConfigChangeHookInput`

```typescript theme={null}
type ConfigChangeHookInput = BaseHookInput & {
  hook_event_name: "ConfigChange";
  source:
    | "user_settings"
    | "project_settings"
    | "local_settings"
    | "policy_settings"
    | "skills";
  file_path?: string;
};
```

#### `InstructionsLoadedHookInput`

```typescript theme={null}
type InstructionsLoadedHookInput = BaseHookInput & {
  hook_event_name: "InstructionsLoaded";
  file_path: string;
  memory_type: "User" | "Project" | "Local" | "Managed";
  load_reason:
    | "session_start"
    | "nested_traversal"
    | "path_glob_match"
    | "include"
    | "compact";
  globs?: string[];
  trigger_file_path?: string;
  parent_file_path?: string;
};
```

#### `DirectoryAddedHookInput`

```typescript theme={null}
type DirectoryAddedHookInput = BaseHookInput & {
  hook_event_name: "DirectoryAdded";
  directory: string;
  source: "slash_command" | "register_repo_root";
};
```

`directory` 是被新增目錄的絕對路徑。`source` 是 `"slash_command"`（當 `/add-dir` 新增時）或 `"register_repo_root"`（當 SDK 控制請求執行時）。

#### `WorktreeCreateHookInput`

```typescript theme={null}
type WorktreeCreateHookInput = BaseHookInput & {
  hook_event_name: "WorktreeCreate";
  name: string;
};
```

#### `WorktreeRemoveHookInput`

```typescript theme={null}
type WorktreeRemoveHookInput = BaseHookInput & {
  hook_event_name: "WorktreeRemove";
  worktree_path: string;
};
```

#### `CwdChangedHookInput`

```typescript theme={null}
type CwdChangedHookInput = BaseHookInput & {
  hook_event_name: "CwdChanged";
  old_cwd: string;
  new_cwd: string;
};
```

#### `FileChangedHookInput`

```typescript theme={null}
type FileChangedHookInput = BaseHookInput & {
  hook_event_name: "FileChanged";
  file_path: string;
  event: "change" | "add" | "unlink";
};
```

#### `MessageDisplayHookInput`

```typescript theme={null}
type MessageDisplayHookInput = BaseHookInput & {
  hook_event_name: "MessageDisplay";
  turn_id: string;
  message_id: string;
  index: number;
  final: boolean;
  delta: string;
};
```

### `HookJSONOutput`

Hook 返回值。

```typescript theme={null}
type HookJSONOutput = AsyncHookJSONOutput | SyncHookJSONOutput;
```

#### `AsyncHookJSONOutput`

```typescript theme={null}
type AsyncHookJSONOutput = {
  async: true;
  asyncTimeout?: number;
};
```

#### `SyncHookJSONOutput`

```typescript theme={null}
type SyncHookJSONOutput = {
  continue?: boolean;
  suppressOutput?: boolean;
  stopReason?: string;
  decision?: "approve" | "block";
  systemMessage?: string;
  /**
   * 終端逸出序列（例如 OSC 9 / OSC 777 桌面通知）
   * 供 Claude Code 代表您發出。僅允許通知/標題 OSCs
   * （0、1、2、9、99、777）和 BEL；包含
   * 其他任何內容的值會被整體忽略。僅互動式 CLI 會發出
   * 它；SDK 會忽略此欄位。
   */
  terminalSequence?: string;
  reason?: string;
  hookSpecificOutput?:
    | {
        hookEventName: "PreToolUse";
        permissionDecision?: "allow" | "deny" | "ask" | "defer";
        permissionDecisionReason?: string;
        updatedInput?: Record<string, unknown>;
        additionalContext?: string;
      }
    | {
        hookEventName: "UserPromptSubmit";
        additionalContext?: string;
        sessionTitle?: string;
        /** 當決定為 "block" 時，從阻止訊息中省略原始提示。 */
        suppressOriginalPrompt?: boolean;
      }
    | {
        hookEventName: "UserPromptExpansion";
        additionalContext?: string;
      }
    | {
        hookEventName: "SessionStart";
        additionalContext?: string;
        initialUserMessage?: string;
        sessionTitle?: string;
        watchPaths?: string[];
        /**
         * SessionStart hooks 完成後重新掃描 skill 和命令目錄，
         * 以便 hook 安裝的 skills 在同一工作階段中可用。
         */
        reloadSkills?: boolean;
      }
    | {
        hookEventName: "Setup";
        additionalContext?: string;
      }
    | {
        hookEventName: "PreModelSwitch";
        /**
         * 與 PreToolUse 相同的合約："allow" 繼續、"deny" 取消
         * 切換、"ask" 要求使用者確認。僅互動式工作階段中的 /model
         * 顯示該提示；其他所有表面（包括 set_model 請求）
         * 將 "ask" 視為拒絕。
         */
        permissionDecision?: "allow" | "deny" | "ask";
        permissionDecisionReason?: string;
      }
    | {
        hookEventName: "PostModelSwitch";
        /** 透過新模型提供的下一個請求到達模型。 */
        additionalContext?: string;
      }
    | {
        hookEventName: "SubagentStart";
        additionalContext?: string;
      }
    | {
        hookEventName: "PostToolUse";
        additionalContext?: string;
        /**
         * 關於此工具呼叫結果的簡短說明，供自動模式
         * 權限分類器使用。上限為 2000 個字元，在回應
         * 同一呼叫的所有 hooks 中共享；僅在同步
         * hook 回應上受尊重。不要將不受信任的工具輸出複製到其中。
         */
        classifierContext?: string;
        updatedToolOutput?: unknown;
        /** @deprecated 使用 `updatedToolOutput`，適用於所有工具。 */
        updatedMCPToolOutput?: unknown;
      }
    | {
        hookEventName: "PostToolUseFailure";
        additionalContext?: string;
      }
    | {
        hookEventName: "PostToolBatch";
        additionalContext?: string;
      }
    | {
        hookEventName: "Stop";
        additionalContext?: string;
      }
    | {
        hookEventName: "SubagentStop";
        additionalContext?: string;
      }
    | {
        hookEventName: "PermissionDenied";
        retry?: boolean;
      }
    | {
        hookEventName: "Notification";
        additionalContext?: string;
      }
    | {
        hookEventName: "PermissionRequest";
        decision:
          | {
              behavior: "allow";
              updatedInput?: Record<string, unknown>;
              updatedPermissions?: PermissionUpdate[];
            }
          | {
              behavior: "deny";
              message?: string;
              interrupt?: boolean;
            };
      }
    | {
        hookEventName: "Elicitation";
        action?: "accept" | "decline" | "cancel";
        content?: Record<string, unknown>;
      }
    | {
        hookEventName: "ElicitationResult";
        action?: "accept" | "decline" | "cancel";
        content?: Record<string, unknown>;
      }
    | {
        hookEventName: "CwdChanged";
        watchPaths?: string[];
      }
    | {
        hookEventName: "FileChanged";
        watchPaths?: string[];
      }
    | {
        hookEventName: "WorktreeCreate";
        worktreePath: string;
      }
    | {
        hookEventName: "MessageDisplay";
        /** 用來代替 delta 顯示的文字。省略（或返回 delta 不變）以顯示原始內容。 */
        displayContent?: string;
      };
};
```

## 工具輸入類型

內建 Claude Code 工具的輸入 schema 文件。這些類型從 `@anthropic-ai/claude-agent-sdk/sdk-tools` 匯出，可用於類型安全的工具互動。

`StructuredOutput` 工具在此沒有類型：Claude Code 會根據您傳遞給 `outputFormat` 的 schema 建置其輸入 schema，因此沒有固定的內容可匯出。如需了解該呼叫在訊息串流中的樣貌，詳見[辨識 StructuredOutput 工具呼叫](https://code.claude.com/docs/zh-TW/agent-sdk/structured-outputs.md#recognize-the-structuredoutput-tool-call)。

### `ToolInputSchemas`

從 `@anthropic-ai/claude-agent-sdk/sdk-tools` 匯出的工具輸入類型的聯合；成員包括：

```typescript theme={null}
type ToolInputSchemas =
  | AgentInput
  | ArtifactInput
  | AskUserQuestionInput
  | BashInput
  | CronCreateInput
  | CronDeleteInput
  | CronListInput
  | EnterPlanModeInput
  | EnterWorktreeInput
  | ExitPlanModeInput
  | ExitWorktreeInput
  | FileEditInput
  | FileReadInput
  | FileWriteInput
  | GlobInput
  | GrepInput
  | ListMcpResourcesInput
  | McpInput
  | MonitorInput
  | NotebookEditInput
  | ProjectsInput
  | PushNotificationInput
  | ReadMcpResourceDirInput
  | ReadMcpResourceInput
  | RefreshMcpToolsInput
  | RemoteTriggerInput
  | ReportFindingsInput
  | ScheduleWakeupInput
  | ShowOnboardingRolePickerInput
  | TaskCreateInput
  | TaskGetInput
  | TaskListInput
  | TaskStopInput
  | TaskUpdateInput
  | TodoWriteInput
  | WebFetchInput
  | WebSearchInput
  | WorkflowInput;
```

### Agent

**工具名稱：** `Agent`。當此工具可供工作階段使用時，先前的名稱 `Task` 仍被接受為別名。

[`SDKSystemMessage`](#sdksystemmessage) 初始化訊息中的 `tools` 陣列為了向後相容性將此工具列為 `Task`。

> [!NOTE]
>
> `mode` 欄位在 Claude Code v2.1.212 或更新版本上已棄用且被忽略。subagent 在父工作階段的權限模式或其定義的 [`permissionMode`](#agentdefinition) 中執行，[subagent 繼承規則](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#available-modes) 決定使用哪一個。

```typescript theme={null}
type AgentInput = {
  description: string;
  prompt: string;
  subagent_type?: string;
  model?: "sonnet" | "opus" | "haiku" | "fable";
  effort?: "low" | "medium" | "high" | "xhigh" | "max";
  run_in_background?: boolean;
  name?: string;
  team_name?: string; // Deprecated; ignored
  mode?: "acceptEdits" | "auto" | "bypassPermissions" | "default" | "dontAsk" | "plan"; // Deprecated; ignored. The subagent inheritance rules decide a subagent's permission mode
  isolation?: "worktree" | "remote";
};
```

啟動新 agent 以自主處理複雜的多步驟任務。

### AskUserQuestion

**工具名稱：** `AskUserQuestion`

```typescript theme={null}
type AskUserQuestionInput = {
  questions: Array<{
    question: string;
    header: string;
    options: Array<{ label: string; description: string; preview?: string }>;
    multiSelect: boolean;
  }>;
  answers?: Record<string, string>;
  annotations?: Record<string, { preview?: string; notes?: string }>;
  metadata?: { source?: string };
};
```

在執行期間詢問使用者澄清問題。詳見[處理核准和使用者輸入](https://code.claude.com/docs/zh-TW/agent-sdk/user-input.md#handle-clarifying-questions)以了解使用詳情。

### Bash

**工具名稱：** `Bash`

```typescript theme={null}
type BashInput = {
  command: string;
  timeout?: number; // milliseconds. Foreground: capped at 600000 by default, higher values are clamped. With run_in_background (Claude Code v2.1.285 or later): the background time limit, 1800000 when omitted, capped at 7200000 unless raised
  description?: string;
  run_in_background?: boolean;
  dangerouslyDisableSandbox?: boolean;
};
```

執行 Bash 命令，支援選擇性逾時和背景執行。工作目錄在命令之間保持不變，包括多回合工作階段後續回合中執行的命令；shell 狀態（例如匯出的環境變數）則不會保持。如需了解哪些目錄變更會保留，詳見[命令之間保持的內容](https://code.claude.com/docs/zh-TW/tools-reference.md#what-persists-between-commands)。如需了解前景上限的設定方式，詳見[逾時和輸出限制](https://code.claude.com/docs/zh-TW/tools-reference.md#timeout-and-output-limits)。如需了解背景命令的時間限制，詳見[背景命令的時間限制](https://code.claude.com/docs/zh-TW/tools-reference.md#time-limit-for-background-commands)。

### Monitor

**工具名稱：** `Monitor`

```typescript theme={null}
type MonitorInput = {
  description: string;
  timeout_ms: number;
  command?: string;
  ws?: {
    url: string;
    protocols?: string[];
  };
};
```

執行背景來源並將每個事件傳遞給 Claude，使其可以做出反應而無需輪詢：`command` 執行指令碼並每行 stdout 發出一個事件，`ws` 開啟 WebSocket 並每個文字框架發出一個事件。恰好提供 `command` 或 `ws` 其中之一。`ws` 來源需要 Claude Code v2.1.195 或更新版本。

`timeout_ms` 是監視的截止時間（毫秒）。預設為 300000，接受最多 3600000 的值。有效截止時間最多為 1800000，即 30 分鐘，因此較大的接受值會縮短至該值。在截止時間時監視結束，Claude 收到一個通知，以便在仍需要時啟動新監視。

匯出的類型將 `timeout_ms` 標記為必需，因為 schema 會填入預設值；省略它的呼叫會驗證通過。

當 Monitor 執行命令時，它遵循與 Bash 相同的權限規則；WebSocket 監視會單獨提示核准。詳見[Monitor 工具參考](https://code.claude.com/docs/zh-TW/tools-reference.md#monitor-tool)以了解行為和提供者可用性。

### TaskOutput

在 Claude Code v2.1.277 中移除，連同其 `TaskOutputInput` 類型一起移除。先前用於擷取執行中或已完成的背景任務的輸出；Claude 改用 `Read` 讀取背景任務的輸出檔案。

`disallowedTools` 項目或仍命名 `TaskOutput` 的拒絕規則會被忽略而不發出警告。

### Edit

**工具名稱：** `Edit`

```typescript theme={null}
type FileEditInput = {
  file_path: string;
  old_string: string;
  new_string: string;
  replace_all?: boolean;
};
```

在檔案中執行精確的字串替換。

### Read

**工具名稱：** `Read`

```typescript theme={null}
type FileReadInput = {
  file_path: string;
  offset?: number;
  limit?: number;
  pages?: string;
  allow_large?: boolean;
};
```

從本機檔案系統讀取檔案，包括文字、影像、PDF 和 Jupyter 筆記本。

* 使用 `pages` 指定 PDF 頁面範圍（例如 `"1-5"`）。
* `allow_large` 讓 Claude 在工作階段的上下文視窗仍有空間時，讀取超過[一般大小限制](https://code.claude.com/docs/zh-TW/tools-reference.md#large-files)的文字檔案。需要 Agent SDK v0.3.296 或更新版本，該版本內含 Claude Code v2.1.296。

對於 PDF，Claude 在 Read 呼叫的 `tool_result` 內容中接收檔案的內容。傳回 `pdf` [輸出](#tool-output-types)的讀取會帶有摘要 `text` 區塊，後面跟著 `document` 區塊。傳回 `parts` 輸出的讀取會帶有摘要 `text` 區塊，後面跟著每個擷取頁面的一個區塊：`image` 區塊，或當 Claude Code 無法將其呈現為影像時命名頁面的 `text` 區塊。在 Agent SDK v0.3.242 之前，Claude Code 在工具結果後將檔案的內容作為單獨的 `user` 訊息傳遞。

### Write

**工具名稱：** `Write`

```typescript theme={null}
type FileWriteInput = {
  file_path: string;
  content: string;
};
```

將檔案寫入本機檔案系統，如果存在則覆蓋。

### Glob

**工具名稱：** `Glob`

```typescript theme={null}
type GlobInput = {
  pattern: string;
  path?: string;
};
```

快速檔案模式匹配，適用於任何程式碼庫大小。

### Grep

**工具名稱：** `Grep`

```typescript theme={null}
type GrepInput = {
  pattern: string;
  path?: string;
  glob?: string;
  type?: string;
  output_mode?: "content" | "files_with_matches" | "count";
  "-i"?: boolean;
  "-o"?: boolean; // print only the matched parts of each line; requires output_mode: "content"
  "-n"?: boolean;
  "-B"?: number;
  "-A"?: number;
  "-C"?: number;
  context?: number;
  head_limit?: number;
  offset?: number;
  multiline?: boolean;
};
```

以 ripgrep 為基礎的搜尋工具，支援正規表達式。

### TaskStop

**工具名稱：** `TaskStop`

```typescript theme={null}
type TaskStopInput = {
  task_id?: string;
  shell_id?: string; // Deprecated: use task_id
};
```

按 ID 停止執行中的背景任務或 shell。自 v2.1.198 起，`task_id` 也接受 agent team 隊友，或依 agent ID 或名稱指定的具名背景 agent。

### NotebookEdit

**工具名稱：** `NotebookEdit`

```typescript theme={null}
type NotebookEditInput = {
  notebook_path: string;
  cell_id?: string;
  new_source: string;
  cell_type?: "code" | "markdown";
  edit_mode?: "replace" | "insert" | "delete";
};
```

編輯 Jupyter 筆記本檔案中的儲存格。

### WebFetch

**工具名稱：** `WebFetch`

```typescript theme={null}
type WebFetchInput = {
  url: string;
  prompt: string;
  offset?: number;
};
```

從 URL 擷取內容並使用 AI 模型進行處理。

`offset` 是從頁面開頭略過的字元數。Claude 會設定它以繼續閱讀較長的頁面。此欄位需要 Agent SDK v0.3.290 或更新版本。

### WebSearch

**工具名稱：** `WebSearch`

```typescript theme={null}
type WebSearchInput = {
  query: string;
  allowed_domains?: string[];
  blocked_domains?: string[];
};
```

搜尋網路並傳回格式化的結果。

### Workflow

**工具名稱：** `Workflow`

```typescript theme={null}
type WorkflowInput = {
  script?: string;
  name?: string;
  scriptPath?: string;
  args?: unknown; // any JSON value; the published typings render this as an object map
  resumeFromRunId?: string;
  title?: string; // ignored; the script's meta block sets the title
  description?: string; // ignored; the script's meta block sets the description
};
```

執行[動態工作流程](https://code.claude.com/docs/zh-TW/workflows.md)：在背景中協調許多 subagent 並傳回一個統一結果的指令碼。`Workflow` 工具在 Agent SDK v0.3.149 及更新版本中可用。至少需要 `script`、`name` 或 `scriptPath` 其中之一。

| 欄位 | 類型 | 描述 |
| - | - | - |
| `script` | `string` | 內嵌工作流程指令碼。必須以 `export const meta = { name, description }` 作為字面值開始，後面跟著使用 `agent()`、`parallel()`、`pipeline()` 和 `phase()` 的指令碼主體。`meta` 中的選擇性 `phases` 陣列在進度檢視中將 agent 分組到具名階段下 |
| `name` | `string` | 內建工作流程的名稱或儲存在 `.claude/workflows/` 中的工作流程名稱。解析為指令碼 |
| `scriptPath` | `string` | 磁碟上工作流程指令碼檔案的路徑，例如先前執行所傳回的 `scriptPath`。優先於 `script` 和 `name`。當工作階段的工具不包含 `Read` 時，Claude Code 會以錯誤拒絕 `scriptPath` |
| `args` | `unknown` | 輸入值，作為全域 `args` 公開給指令碼，用於參數化的具名工作流程，例如研究問題或檔案路徑清單。將陣列和物件作為實際 JSON 值傳遞，而不是 JSON 編碼的字串 |
| `resumeFromRunId` | `string` | 先前 `Workflow` 呼叫的執行 ID 以繼續。具有未變更輸入的已完成 `agent()` 呼叫通常傳回快取結果；其餘的執行即時。[暫停後繼續](https://code.claude.com/docs/zh-TW/workflows.md#resume-after-a-pause)涵蓋哪些已完成的呼叫會重新執行。僅限同一工作階段 |
| `title` | `string` | 被忽略；指令碼的 `meta` 區塊設定標題 |
| `description` | `string` | 被忽略；指令碼的 `meta` 區塊設定描述 |

### TodoWrite

**工具名稱：** `TodoWrite`

```typescript theme={null}
type TodoWriteInput = {
  todos: Array<{
    content: string;
    status: "pending" | "in_progress" | "completed";
    activeForm: string;
  }>;
};
```

建立和管理結構化任務清單以追蹤進度。

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
> 詳見[模型可用性](https://code.claude.com/docs/zh-TW/agent-sdk/todo-tracking.md#model-availability)以選擇加入。

### TaskCreate

**工具名稱：** `TaskCreate`

```typescript theme={null}
type TaskCreateInput = {
  subject: string;
  description: string;
  activeForm?: string;
  metadata?: Record<string, unknown>;
};
```

建立單一任務並傳回其指派的 ID。

### TaskUpdate

**工具名稱：** `TaskUpdate`

```typescript theme={null}
type TaskUpdateInput = {
  taskId: string;
  status?: "pending" | "in_progress" | "completed" | "deleted";
  subject?: string;
  description?: string;
  activeForm?: string;
  addBlocks?: string[];
  addBlockedBy?: string[];
  owner?: string;
  metadata?: Record<string, unknown>;
};
```

按 ID 修補一個任務。將 `status` 設定為 `"deleted"` 以移除它。

### TaskGet

**工具名稱：** `TaskGet`

```typescript theme={null}
type TaskGetInput = {
  taskId: string;
};
```

傳回一個任務的完整詳情，或在找不到 ID 時傳回 `null`。

### TaskList

**工具名稱：** `TaskList`

```typescript theme={null}
type TaskListInput = {};
```

傳回目前清單中所有任務的快照。

### ExitPlanMode

**工具名稱：** `ExitPlanMode`

```typescript theme={null}
type ExitPlanModeInput = {
  /** Deprecated: no longer used. */
  allowedPrompts?: Array<{
    tool: "Bash";
    prompt: string;
  }>;
  [k: string]: unknown;
};
```

退出 plan mode。`allowedPrompts` 欄位已棄用且被忽略；Claude Code 仍接受它以便現有呼叫者和逐字稿驗證通過。在 v2.1.205 之前，它請求基於提示詞的 Bash 權限以實作計畫。

### ListMcpResources

**工具名稱：** `ListMcpResourcesTool`

```typescript theme={null}
type ListMcpResourcesInput = {
  server?: string;
};
```

列出來自已連接伺服器的可用 MCP 資源。

### ReadMcpResource

**工具名稱：** `ReadMcpResourceTool`

```typescript theme={null}
type ReadMcpResourceInput = {
  server: string;
  uri: string;
};
```

從伺服器讀取特定 MCP 資源。

### EnterWorktree

**工具名稱：** `EnterWorktree`

```typescript theme={null}
type EnterWorktreeInput = {
  name?: string;
  path?: string;
};
```

建立並進入臨時 git worktree 以進行隔離工作。傳遞 `path` 以切換到現有 worktree，而不是建立新的。首次進入時，目標必須是目前儲存庫的已註冊 worktree，或在多儲存庫工作區中，位於其中嵌套的儲存庫；從 worktree 工作階段內，它必須位於工作階段儲存庫的 `.claude/worktrees/` 下。`name` 和 `path` 互斥。

### ExitWorktree

**工具名稱：** `ExitWorktree`

```typescript theme={null}
type ExitWorktreeInput = {
  action: "keep" | "remove";
  discard_changes?: boolean;
};
```

退出目前 git worktree 並返回原始工作目錄。`keep` 動作將 worktree 和分支保留在磁碟上，而 `remove` 刪除兩者。當移除具有未提交檔案或未合併提交的 worktree 時，`discard_changes` 必須為 `true`。

### EnterPlanMode

**工具名稱：** `EnterPlanMode`

```typescript theme={null}
type EnterPlanModeInput = {};
```

進入 plan mode，Claude 在其中研究並在進行變更前提出計畫。

### CronCreate

**工具名稱：** `CronCreate`

```typescript theme={null}
type CronCreateInput = {
  cron: string;
  prompt: string;
  recurring?: boolean;
  durable?: boolean;
};
```

在本機時間的 5 欄位 cron 排程上排程提示詞執行。將 `recurring` 設定為 `false` 以在下一個符合時單次觸發。工作預設為工作階段範圍，使用 `--resume` 或 `--continue` 繼續時會還原尚未過期的工作。詳見[工作階段範圍的排程任務](https://code.claude.com/docs/zh-TW/scheduled-tasks.md)。

將 `durable` 設定為 `true` 以請求持久化至 `.claude/scheduled_tasks.json`，使工作在重新啟動後存活。並非每個工作階段都提供持久排程：當不提供時，Claude Code 接受 `durable: true` 但建立工作為僅工作階段。讀取輸出的 `durable` 欄位以查看工作是否已持久化。

### CronDelete

**工具名稱：** `CronDelete`

```typescript theme={null}
type CronDeleteInput = {
  id: string;
};
```

按 `CronCreate` 傳回的 ID 刪除排程的 cron 工作。

### CronList

**工具名稱：** `CronList`

```typescript theme={null}
type CronListInput = {};
```

列出排程的 cron 工作：來自 `.claude/scheduled_tasks.json` 的持久工作和來自目前工作階段的僅工作階段工作。

### ScheduleWakeup

**工具名稱：** `ScheduleWakeup`

```typescript theme={null}
type ScheduleWakeupInput = {
  delaySeconds?: number;
  reason?: string;
  prompt?: string;
  noop?: boolean;
  stop?: boolean;
};
```

排程一次性喚醒，在延遲後觸發給定的提示詞。此工具支援自步調 `/loop` 命令。執行時間將 `delaySeconds` 限制在 60 到 3600 秒之間。除非 `stop` 為 true，否則 `delaySeconds`、`reason`、`prompt` 和 `noop` 欄位為必需。`noop: true` 報告沒有任何變更的喚醒。設定 `stop: true` 會取消待處理的喚醒並結束自步調 `/loop`。`stop` 欄位需要 Claude Code v2.1.202 或更新版本。詳見[工具參考中的 ScheduleWakeup 列](https://code.claude.com/docs/zh-TW/tools-reference.md)。

### RemoteTrigger

**工具名稱：** `RemoteTrigger`

```typescript theme={null}
type RemoteTriggerInput = {
  action:
    | "list"
    | "get"
    | "create"
    | "update"
    | "run"
    | "create_webhook_trigger"
    | "list_runs"
    | "get_run_log";
  trigger_id?: string;
  session_id?: string;
  cursor?: string;
  body?: {
    [k: string]: unknown;
  };
};
```

管理[雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md)（先前稱為 routines）：在雲端託管的排程和觸發 Claude Code 執行。此工具支援 `/schedule` 命令。`trigger_id` 對於 `get`、`update`、`run` 和 `list_runs` 動作為必需。`body` 對於 `create`、`update` 和 `create_webhook_trigger` 為必需，對於 `run` 為選擇性。

`create_webhook_trigger`、`list_runs` 和 `get_run_log` 各自需要最低的 Claude Code 版本：

* **`create_webhook_trigger`**：將事件來源附加到現有排程任務，例如觸發它的 [GitHub 事件](https://code.claude.com/docs/zh-TW/routines.md#add-a-github-trigger)。`body` 命名來源、事件和要觸發的任務。需要 Claude Code v2.1.225 或更新版本。
* **`list_runs` 和 `get_run_log`**：`list_runs` 列出排程任務的最近執行，`get_run_log` 讀取一個執行的日誌。`session_id` 命名要讀取的執行（來自 `list_runs` 結果），`cursor` 分頁任一動作的結果。兩個動作都需要 Claude Code v2.1.227 或更新版本。

此工具僅在工作階段使用已啟用雲端排程任務方案的 claude.ai 帳戶進行驗證時可用。當您的組織政策停用[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)時，此工具不存在。在 Claude Code v2.1.227 或更新版本上，當擁有者[為組織關閉排程任務](https://code.claude.com/docs/zh-TW/routines.md#routines-are-disabled-by-your-organizations-policy)時，工具也不存在。

### PushNotification

**工具名稱：** `PushNotification`

```typescript theme={null}
type PushNotificationInput = {
  message: string;
  status: "proactive";
};
```

向使用者傳送主動推播通知。將 `message` 保持在 200 個字元以下，因為行動作業系統會截斷較長的文字。詳見[工具參考中的 PushNotification 列](https://code.claude.com/docs/zh-TW/tools-reference.md)以了解提供者可用性；推播傳遞通過 Anthropic 託管的基礎設施進行，該基礎設施無法從 Amazon Bedrock、AWS 上的 Claude Platform、Google Cloud 的 Agent Platform 或 Microsoft Foundry 存取。

### REPL

在 v2.1.275 中移除。直到 v2.1.274，實驗性 `REPL` 工具可以通過在[`env` 選項](#options)中設定 `CLAUDE_CODE_REPL=1` 來開啟。

### ReportFindings

**工具名稱：** `ReportFindings`

```typescript theme={null}
type ReportFindingsInput = {
  level?: "low" | "medium" | "high" | "xhigh" | "max";
  findings: Array<{
    file: string;
    line?: number;
    summary: string;
    failure_scenario: string;
    short_summary?: string;
    category?: string;
    verdict?: "CONFIRMED" | "PLAUSIBLE";
    outcome?: "fixed" | "skipped" | "no_change_needed";
  }>;
};
```

將程式碼審查發現報告為結構化清單，以便 Claude Code 可以呈現它們而不是將其列印為文字。發現按最嚴重優先排序，每次呼叫最多 32 個，當沒有發現存活時陣列為空。需要 Claude Code v2.1.196 或更新版本。

`level` 為選擇性欄位，保存 Claude 為此審查回報的 effort 等級。Claude Code 不會將其與審查實際執行時的等級進行比較，因此兩者可能不同。

每個發現包含這些欄位：

* `file`：發現所在的儲存庫相對路徑。選擇性 `line` 是它錨定到的 1 索引行。
* `summary`：缺陷的單句陳述。`failure_scenario` 描述導致錯誤輸出或當機的具體輸入和狀態。
* `short_summary`：選擇性壓縮標籤，最多 60 個字元用於緊湊顯示。需要 Claude Code v2.1.212 或更新版本。
* `category`：選擇性短 kebab-case 發現類型的 slug，例如 `correctness` 或 `test-coverage`。需要 Claude Code v2.1.199 或更新版本。
* `verdict`：在驗證通過執行時設定；在僅內嵌審查上不存在。
* `outcome`：僅在應用修復後重新報告時設定。

### Artifact

**工具名稱：** `Artifact`

```typescript theme={null}
type ArtifactInput = {
  action?: "publish" | "list";
  file_path?: string;
  favicon?: string;
  icon?: string;
  limit?: number;
  scope?: "mine" | "shared" | "all";
  title?: string;
  description?: string;
  label?: string;
  url?: string;
  force?: boolean;
  capabilities?: Record<string, unknown>;
  contract?: "latest" | string;
};
```

將本機 `.html` 或 `.md` 檔案發佈為託管 artifact 頁面，或列出使用者的已發佈 artifact。省略 `action` 或傳遞 `"publish"` 以發佈 `file_path`，這對於發佈動作為必需。以下每個欄位適用於發佈：

* `icon`：artifact 瀏覽器標籤圖示的一個短通用詞，例如 `chart` 或 `map`。Claude 在首次發佈時包含它，在更新時省略它，這保留 artifact 的儲存圖示。
* `favicon`：已棄用，Claude 省略它。
* `title`：在瀏覽器標籤和圖庫中命名已發佈頁面，當 HTML 檔案沒有 `<title>` 標籤時。
* `url`：目標是現有 artifact 以就地更新，而不是建立新的。

`force` 是最後手段覆蓋，丟棄另一個工作階段發佈的較新版本。在衝突時，失敗的發佈傳回較新的內容；Claude 將其變更合併到該內容上，或重新讀取 artifact，並再次發佈。僅當使用者明確要求丟棄該版本時傳遞 `force`。

傳遞 `"list"` 以列舉使用者的已發佈 artifact；僅 `limit` 和 `scope` 可能伴隨它。`scope` 預設為 `"mine"`，列出使用者擁有的 artifact；`"shared"` 列出其他人與使用者共享的 artifact，`"all"` 列出兩者。

`limit` 設定列表傳回的 artifact 數量上限，範圍為 1 到 200。`limit` 大於 50 需要 Agent SDK v0.3.292 或更新版本。未指定 `limit` 時，列表最多傳回 25 個。

* `capabilities`：已發佈頁面使用的執行時功能，以功能名稱為鍵，例如[頁面可能呼叫的連接器](https://code.claude.com/docs/zh-TW/artifacts.md#pull-live-data-with-mcp-connectors)。artifact 服務會驗證宣告，並拒絕指定了帳戶無法使用的功能或為某功能提供無效設定的發佈。傳遞 `{}` 以清除儲存的宣告，在重新部署時省略欄位以保留它。需要 Agent SDK v0.3.235 或更新版本。
* `contract`：已發佈頁面執行的執行時版本。省略它以保留 artifact 的目前版本，傳遞 `"latest"` 以升級，或傳遞特定版本以釘選或回滾。需要 Agent SDK v0.3.235 或更新版本。

類型已匯出，但工具在 Agent SDK 工作階段中預設為關閉。發佈也需要[artifact 可用性表](https://code.claude.com/docs/zh-TW/artifacts.md#availability)中的每個條件，使用 API 金鑰驗證的工作階段不符合。

### Projects

**工具名稱：** `Projects`

```typescript theme={null}
type ProjectsInput = {
  method:
    | "project_info"
    | "project_read"
    | "project_search"
    | "project_write"
    | "project_delete";
  path?: string;
  content?: string;
  local_path?: string;
  present_to_user?: boolean;
  query?: string;
  n?: number;
};
```

讀取和寫入附加到工作階段的 claude.ai 專案。按 `method` 分派：

* `project_info`：傳回專案中繼資料和文件清單。
* `project_read`：按 `path` 讀取一個文件。
* `project_search`：使用 `query` 查詢專案的知識庫。`n` 限制點擊數並預設為 `5`。
* `project_write`：在 `path` 建立或替換文件，恰好來自 `content`（帶有內嵌文字）或 `local_path`（命名工作目錄內的檔案）其中之一。`present_to_user: true` 將寫入的文件標記為使用者需要查看的可交付成果。
* `project_delete`：按 `path` 刪除文件。

### ReadMcpResourceDir

**工具名稱：** `ReadMcpResourceDirTool`

```typescript theme={null}
type ReadMcpResourceDirInput = {
  server: string;
  uri: string;
};
```

列出 MCP 伺服器上目錄資源的直接子項。僅可用於已宣告支援目錄列表的伺服器；列表不是遞迴的。並非每個工作階段都啟用目錄列表：當關閉時，呼叫傳回空 `resources` 清單，`error` 欄位報告目錄列表未啟用。

### RefreshMcpTools

**工具名稱：** `RefreshMcpTools`

```typescript theme={null}
type RefreshMcpToolsInput = {
  server?: string; // refresh only this server; omit to refresh all connected servers
};
```

重新查詢已連接 MCP 伺服器的工具清單並應用任何變更。類型已匯出，但 Claude Code 僅在您在[`env` 選項](#options)中設定 `CLAUDE_CODE_ENABLE_REFRESH_MCP_TOOLS=1` 時註冊工具，且僅在至少有一個 MCP 伺服器的工作階段中。需要 Claude Code v2.1.211 或更新版本。

### ShowOnboardingRolePicker

**工具名稱：** `ShowOnboardingRolePicker`

```typescript theme={null}
type ShowOnboardingRolePickerInput = {};
```

在 Cowork 上線期間呈現可點擊的角色選擇器晶片列，以便使用者可以選擇其角色並取得相符的外掛程式安裝。不帶引數；角色清單由用戶端定義。呼叫會阻止直到使用者回應。

### McpInput

**工具名稱：** `mcp__<server>__<tool>` 形式的動態 MCP 工具名稱

```typescript theme={null}
type McpInput = {
  [k: string]: unknown;
};
```

MCP 工具引數是開放物件：每個伺服器定義其自己的參數，因此類型對欄位名稱或值不施加任何限制。請查閱伺服器自己的工具 schema 以了解特定工具接受的欄位。

## 工具輸出類型

內建 Claude Code 工具的輸出 schema 文件。這些類型從 `@anthropic-ai/claude-agent-sdk/sdk-tools` 匯出，代表每個工具傳回的實際回應資料。

### `ToolOutputSchemas`

從 `@anthropic-ai/claude-agent-sdk/sdk-tools` 匯出的工具輸出類型聯合；成員包括：

```typescript theme={null}
type ToolOutputSchemas =
  | AgentOutput
  | ArtifactOutput
  | AskUserQuestionOutput
  | BashOutput
  | CronCreateOutput
  | CronDeleteOutput
  | CronListOutput
  | EnterPlanModeOutput
  | EnterWorktreeOutput
  | ExitPlanModeOutput
  | ExitWorktreeOutput
  | FileEditOutput
  | FileReadOutput
  | FileWriteOutput
  | GlobOutput
  | GrepOutput
  | ListMcpResourcesOutput
  | McpOutput
  | MonitorOutput
  | NotebookEditOutput
  | ProjectsOutput
  | PushNotificationOutput
  | ReadMcpResourceDirOutput
  | ReadMcpResourceOutput
  | RefreshMcpToolsOutput
  | RemoteTriggerOutput
  | ReportFindingsOutput
  | ScheduleWakeupOutput
  | ShowOnboardingRolePickerOutput
  | TaskCreateOutput
  | TaskGetOutput
  | TaskListOutput
  | TaskStopOutput
  | TaskUpdateOutput
  | TodoWriteOutput
  | WebFetchOutput
  | WebSearchOutput
  | WorkflowOutput;
```

### Agent

**工具名稱：** `Agent`。當此工具可供工作階段使用時，先前的名稱 `Task` 仍被接受為別名。

```typescript theme={null}
type AgentOutput =
  | {
      status: "completed";
      agentId: string;
      agentType?: string;
      content: Array<{ type: "text"; text: string; citations?: unknown[] | null }>;
      resolvedModel?: string;
      modelsUsed?: string[];
      totalToolUseCount: number;
      totalDurationMs: number;
      totalTokens: number;
      usage: {
        input_tokens: number;
        output_tokens: number;
        cache_creation_input_tokens: number | null;
        cache_read_input_tokens: number | null;
        server_tool_use: {
          web_search_requests: number;
          web_fetch_requests: number;
        } | null;
        service_tier: string | null;
        cache_creation: {
          ephemeral_1h_input_tokens: number;
          ephemeral_5m_input_tokens: number;
        } | null;
        inference_geo?: string | null;
        speed?: string | null;
        iterations?: unknown;
        output_tokens_details?: {
          thinking_tokens?: number | null;
        } | null;
        fallback_credit?: unknown;
      };
      toolStats?: {
        readCount: number;
        searchCount: number;
        bashCount: number;
        editFileCount: number;
        linesAdded: number;
        linesRemoved: number;
        otherToolCount: number;
        frameCount?: number;
      };
      prompt: string;
      worktreePath?: string;
      worktreeBranch?: string;
    }
  | {
      status: "async_launched";
      isAsync?: true;
      agentId: string;
      description: string;
      resolvedModel?: string;
      modelsUsed?: string[];
      prompt: string;
      outputFile: string;
      canReadOutputFile?: boolean;
    }
  | {
      status: "remote_launched";
      taskId: string;
      sessionUrl: string;
      description: string;
      prompt: string;
      outputFile: string;
    };
```

傳回 subagent 的結果。根據 `status` 欄位進行區分：`"completed"` 表示已完成的工作，`"async_launched"` 表示背景任務，`"remote_launched"` 表示 Claude Code 分派到雲端工作階段的工作，其中 `sessionUrl` 連結到該工作階段，`taskId` 識別它。

在 `completed` 變體上，`resolvedModel` 命名 subagent 啟動時使用的模型，當套用 [`availableModels`](https://code.claude.com/docs/zh-TW/model-config#restrict-model-selection) 或其他覆寫時，可能與請求的 `model` 輸入不同。此欄位需要 Claude Code v2.1.174 或更新版本。在 `async_launched` 上，它命名工作移至背景時使用的模型。

`modelsUsed` 列出 subagent 使用的模型，按順序排列。此欄位僅在發生中途交換時出現，當執行交換回該模型時，模型會再次出現。在 `async_launched` 上，列表涵蓋背景化前使用的模型。`modelsUsed` 和 `resolvedModel` 的背景化行為都需要 Claude Code v2.1.212 或更新版本。

如果 Claude Code [保留了 subagent 的隔離 worktree](https://code.claude.com/docs/zh-TW/worktrees.md#isolate-subagents-with-worktrees)，`completed` 結果上的 `worktreePath` 是找到它的位置。`worktreeBranch` 是其分支，當 Claude Code 使用 git 建立 worktree 時出現。

Claude Code 從 subagent 的最終 API 請求填充 `usage` 和 `totalTokens`，而不是從整個執行，所以 `usage.service_tier` 是 API 在該請求上報告的服務層級字串。當存在時，`usage.output_tokens_details.thinking_tokens` 是該請求的輸出 token 中作為思考 token 的數量。`output_tokens_details` 欄位需要 TypeScript SDK v0.3.228 或更新版本，該版本包含 Claude Code v2.1.228。`fallback_credit` 欄位需要 TypeScript SDK v0.3.285 或更新版本，該版本包含 Claude Code v2.1.285。

`usage.output_tokens_details` 在意義上與 [`Usage.output_tokens_details`](#usage) 相符，範圍限於該最終請求，但其每個層級都是選擇性的。保護物件和欄位，例如 `usage.output_tokens_details?.thinking_tokens ?? 0`，而不是直接讀取它。

在 v2.1.207 之前，發佈的類型更窄。它省略了 `worktreePath`、`worktreeBranch`、`citations`、`toolStats.frameCount` 和 `inference_geo`、`speed` 和 `iterations` 使用欄位，並將 `service_tier` 類型化為 `"standard" | "priority" | "batch"`。類型標記為選擇性的欄位可能在較早版本記錄的結果中不存在。

### AskUserQuestion

**工具名稱：** `AskUserQuestion`

```typescript theme={null}
type AskUserQuestionOutput = {
  questions: Array<{
    question: string;
    header: string;
    options: Array<{ label: string; description: string; preview?: string }>;
    multiSelect: boolean;
  }>;
  answers: Record<string, string>;
  response?: string;
  annotations?: Record<string, { preview?: string; notes?: string }>;
  afkTimeoutMs?: number;
};
```

傳回提出的問題和使用者的答案。當使用者輸入自由格式回覆而不是回答結構化問題時，`response` 會被設定；當存在時，Claude 會收到「使用者回應：…」而不是每個問題的答案清單。

### Bash

**工具名稱：** `Bash`

```typescript theme={null}
type BashOutput = {
  stdout: string;
  stderr: string;
  rawOutputPath?: string;
  interrupted: boolean;
  isImage?: boolean;
  backgroundTaskId?: string;
  backgroundedByUser?: boolean;
  timedOutAfterMs?: number;
  backgroundCwdHint?: string;
  backgroundEndsWithFinalResponse?: true;
  dangerouslyDisableSandbox?: boolean;
  returnCodeInterpretation?: string;
  noOutputExpected?: boolean;
  structuredContent?: unknown[];
  persistedOutputPath?: string;
  persistedOutputSize?: number;
  staleReadFileStateHint?: string;
  ghRateLimitHint?: string;
  gitOperation?: {
    commit?: { sha: string; kind: "committed" | "amended" | "cherry-picked"; branch?: string };
    push?: { branch: string };
    branch?: { ref: string; action: "merged" | "rebased" };
    pr?: {
      number: number;
      url?: string;
      action: "created" | "edited" | "merged" | "commented" | "closed" | "reopened" | "ready" | "draft" | "auto-merge-enabled" | "auto-merge-disabled";
    };
  };
};
```

`stdout`、`stderr` 和 `backgroundTaskId` 欄位攜帶：

| 欄位 | 它攜帶的內容 |
| - | - |
| `stdout` | 命令的 stdout 和 stderr，合併為一個交錯流 |
| `stderr` | 工具本身新增的通知，例如 shell 工作目錄重設，不是命令的 stderr |
| `backgroundTaskId` | 對於背景命令存在 |

`timedOutAfterMs` 是逾時（以毫秒為單位），當命令達到其逾時並移至背景而不是明確從那裡開始時設定。`backgroundCwdHint` 在背景化命令包含目錄變更內建函式（例如 `cd`、`pushd`、`popd` 或 `chdir`）時設定，並注意工作階段工作目錄未變更。兩個欄位都需要 Claude Code v2.1.210 或更新版本。

當在前景執行的 subagent 擁有背景化命令時，該命令[在該 subagent 的執行結束時結束](https://code.claude.com/docs/zh-TW/tools-reference.md#when-a-background-command-stops)。Claude Code 在此類命令上將 `backgroundEndsWithFinalResponse` 設定為 `true`，並在命令存活該回合時省略欄位，如主對話或背景 subagent 啟動的命令一樣。此欄位需要 Claude Code v2.1.227 或更新版本。

Claude Code 將 `gitOperation.commit.branch` 設定為 git 提交摘要行中命名的分支，並對在分離 HEAD 上進行的提交省略它。此欄位需要 Agent SDK v0.3.227 或更新版本。Claude Code 將 `gh pr reopen` 命令報告為 `reopened` PR 動作，需要 Agent SDK v0.3.234 或更新版本。

### Monitor

**工具名稱：** `Monitor`

```typescript theme={null}
type MonitorOutput = {
  taskId: string;
  timeoutMs: number;
  persistent?: boolean;
};
```

傳回執行中監視器的背景任務 ID。使用此 ID 搭配 `TaskStop` 以提前取消監視。

### Edit

**工具名稱：** `Edit`

```typescript theme={null}
type FileEditOutput = {
  filePath: string;
  oldString: string;
  newString: string;
  originalFile: string | null;
  structuredPatch: Array<{
    oldStart: number;
    oldLines: number;
    newStart: number;
    newLines: number;
    lines: string[];
  }>;
  userModified: boolean;
  replaceAll: boolean;
  gitDiff?: {
    filename: string;
    status: "modified" | "added";
    additions: number;
    deletions: number;
    changes: number;
    patch: string;
    repository?: string | null;
  };
};
```

傳回編輯操作的結構化差異。

### Read

**工具名稱：** `Read`

```typescript theme={null}
type FileReadOutput =
  | {
      type: "text";
      file: {
        filePath: string;
        content: string;
        numLines: number;
        startLine: number;
        totalLines: number;
        /** 當整個檔案讀取因超過 token 上限而自動分頁時為真（內容是部分第一頁）。 */
        truncatedByTokenCap?: boolean;
      };
    }
  | {
      type: "image";
      file: {
        base64: string;
        type: "image/jpeg" | "image/png" | "image/gif" | "image/webp";
        originalSize: number;
        dimensions?: {
          originalWidth?: number;
          originalHeight?: number;
          displayWidth?: number;
          displayHeight?: number;
        };
      };
    }
  | {
      type: "notebook";
      file: {
        filePath: string;
        cells: unknown[];
      };
    }
  | {
      type: "pdf";
      file: {
        filePath: string;
        base64: string;
        originalSize: number;
      };
    }
  | {
      type: "parts";
      file: {
        filePath: string;
        originalSize: number;
        count: number;
        outputDir: string;
      };
      /** 第一個提取頁面的文件頁碼；標記工具結果內容中的頁面影像。 */
      firstPage?: number;
      /** 僅在程序中：頁面影像位元組作為影像區塊在工具結果內容中傳遞，不會保留在發出的 tool_use_result 上，所以此鍵在那裡不存在。 */
      pages?: {
        base64: string;
        mediaType: "image/jpeg" | "image/png" | "image/gif" | "image/webp";
        error?: string;
      }[];
    }
  | {
      type: "file_unchanged";
      file: {
        filePath: string;
      };
      /** 當重複資料刪除符合啟動時播種的項目（CLAUDE.md / 巢狀記憶）而不是先前的 Read tool_result 時設定。 */
      source?: "seeded";
    };
```

以適合檔案類型的格式傳回檔案內容。根據 `type` 欄位進行區分。

### Write

**工具名稱：** `Write`

```typescript theme={null}
type FileWriteOutput = {
  type: "create" | "update";
  filePath: string;
  content: string;
  structuredPatch: Array<{
    oldStart: number;
    oldLines: number;
    newStart: number;
    newLines: number;
    lines: string[];
  }>;
  originalFile: string | null;
  gitDiff?: {
    filename: string;
    status: "modified" | "added";
    additions: number;
    deletions: number;
    changes: number;
    patch: string;
    repository?: string | null;
  };
  userModified?: boolean;
};
```

傳回寫入結果及結構化差異資訊。`originalFile` 和 `structuredPatch` 持有的內容取決於寫入：

* 對於新建立的檔案，`originalFile` 為 null，`structuredPatch` 為空
* 在覆寫檔案時，`originalFile` 攜帶先前的內容，除非該內容大於約 10 MB：Claude Code 會跳過差異並傳回 `originalFile` null 和 `structuredPatch` 空
* 當寫入未變更任何內容或差異逾時時，`structuredPatch` 也為空

### Glob

**工具名稱：** `Glob`

```typescript theme={null}
type GlobOutput = {
  durationMs: number;
  numFiles: number;
  filenames: string[];
  truncated: boolean;
  totalMatches?: number;
  countIsComplete?: boolean;
};
```

傳回符合 glob 模式的檔案路徑，按修改時間排序。

`totalMatches` 和 `countIsComplete` 需要 Claude Code v2.1.191 或更新版本。`totalMatches` 報告截斷前的符合檔案數。當 `countIsComplete` 為 false 時，`totalMatches` 是下限，因為基礎搜尋截斷了自己的輸出。

### Grep

**工具名稱：** `Grep`

```typescript theme={null}
type GrepOutput = {
  mode?: "content" | "files_with_matches" | "count";
  numFiles: number;
  filenames: string[];
  content?: string;
  numLines?: number;
  numMatches?: number;
  totalFiles?: number;
  totalLines?: number;
  appliedLimit?: number;
  appliedOffset?: number;
};
```

傳回搜尋結果。形狀因 `mode` 而異：檔案清單、包含符合的內容或符合計數。在 `count` 模式中，`numFiles` 和 `numMatches` 是完整結果集上的總計，不是分頁切片。在 v2.1.208 之前，截斷列出項目的 `head_limit` 或 `offset` 也會截斷這些總計。

`totalFiles` 需要 Claude Code v2.1.208 或更新版本，並在 `files_with_matches` 模式中報告 `head_limit` 和 `offset` 分頁前的結果總數。`totalLines` 需要 Claude Code v2.1.210 或更新版本，並在 `content` 模式中報告分頁前的行總數。

### TaskStop

**工具名稱：** `TaskStop`

```typescript theme={null}
type TaskStopOutput = {
  message: string;
  task_id: string;
  task_type: string;
  command?: string;
};
```

傳回停止背景任務後的確認。

### NotebookEdit

**工具名稱：** `NotebookEdit`

```typescript theme={null}
type NotebookEditOutput = {
  new_source: string;
  old_source?: string;
  cell_id?: string;
  cell_type: "code" | "markdown";
  language: string;
  edit_mode: string;
  error?: string;
  notebook_path: string;
  original_file: string;
  updated_file: string;
};
```

傳回筆記本編輯的結果及原始和更新的檔案內容。

### WebFetch

**工具名稱：** `WebFetch`

```typescript theme={null}
type WebFetchOutput = {
  bytes: number;
  code: number;
  codeText: string;
  result: string;
  durationMs: number;
  url: string;
  artifactRead?: {
    slug: string;
    ver?: string;
    seeded?: false;
  };
};
```

傳回提取的內容及 HTTP 狀態和中繼資料。

`artifactRead` 是 Claude Code 自己的 artifact 讀取記錄，僅當 Claude 提取工作階段可以發佈的 artifact 時出現。Claude Code 在工作階段恢復時讀取它回來，以便稍後發佈基於正確版本；您的程式碼不需要對其採取行動。`slug` 命名 artifact，`ver` 是讀取記錄的版本，當它未記錄任何內容時不存在，`seeded: false` 標記其完整來源未到達 Claude 的讀取。`seeded` 欄位需要 Agent SDK v0.3.239 或更新版本。

### WebSearch

**工具名稱：** `WebSearch`

```typescript theme={null}
type WebSearchOutput = {
  query: string;
  results: Array<
    | {
        tool_use_id: string;
        content: Array<{ title: string; url: string }>;
      }
    | string
  >;
  durationSeconds: number;
  searchCount?: number;
};
```

傳回來自網路的搜尋結果。

### Workflow

**工具名稱：** `Workflow`

```typescript theme={null}
type WorkflowOutput = {
  status: "async_launched" | "remote_launched";
  taskId: string;
  taskType?: "local_workflow" | "remote_agent";
  workflowName?: string;
  runId?: string;
  summary?: string;
  transcriptDir?: string;
  scriptPath?: string;
  sessionUrl?: string; // 當工作流程作為雲端工作階段啟動時設定
  warning?: string;
  error?: string;
};
```

在工具接受呼叫後立即傳回。最終結果稍後作為工作完成到達。在將執行視為已啟動之前檢查 `error`：語法檢查失敗的指令碼傳回 `status: "async_launched"` 並設定 `error`，且永遠不會執行。

| 欄位 | 類型 | 描述 |
| - | - | - |
| `status` | `"async_launched" \| "remote_launched"` | 工具接受了呼叫。`"async_launched"` 用於程序內執行，`"remote_launched"` 用於分派到雲端工作階段而不是在程序內執行的執行 |
| `taskId` | `string` | 執行的背景任務識別碼 |
| `taskType` | `"local_workflow" \| "remote_agent"` | 已註冊背景任務的任務類型，符合 `status` 分支 |
| `workflowName` | `string` | 工作流程指令碼中的 `meta.name` |
| `runId` | `string` | 工作流程執行識別碼，在稍後呼叫時作為 `resumeFromRunId` 傳遞。對於 `remote_launched` 執行不存在，其中雲端工作階段 URL 是恢復控制代碼 |
| `summary` | `string` | 工作流程功能的單行描述 |
| `transcriptDir` | `string` | 執行期間寫入 subagent 逐字稿的目錄 |
| `scriptPath` | `string` | 此執行的持久化工作流程指令碼路徑。編輯它並作為 `scriptPath` 傳回以重新執行而不重新傳送指令碼 |
| `sessionUrl` | `string` | 雲端工作階段 URL，當 `status` 為 `"remote_launched"` 時設定 |
| `warning` | `string` | 非阻止性提醒，例如本機 git 狀態與雲端工作階段將複製的推送分支不同 |
| `error` | `string` | 當指令碼語法檢查失敗時設定。當存在時，儘管啟動狀態，執行未啟動 |

### TodoWrite

**工具名稱：** `TodoWrite`

```typescript theme={null}
type TodoWriteOutput = {
  oldTodos: Array<{
    content: string;
    status: "pending" | "in_progress" | "completed";
    activeForm: string;
  }>;
  newTodos: Array<{
    content: string;
    status: "pending" | "in_progress" | "completed";
    activeForm: string;
  }>;
};
```

傳回先前和更新的工作清單。

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
> 請參閱[模型可用性](https://code.claude.com/docs/zh-TW/agent-sdk/todo-tracking.md#model-availability)以選擇加入。

### TaskCreate

**工具名稱：** `TaskCreate`

```typescript theme={null}
type TaskCreateOutput = {
  task: {
    id: string;
    subject: string;
  };
};
```

傳回建立的工作及其指派的 ID。

### TaskUpdate

**工具名稱：** `TaskUpdate`

```typescript theme={null}
type TaskUpdateOutput = {
  success: boolean;
  taskId: string;
  updatedFields: string[];
  error?: string;
  statusChange?: {
    from: string;
    to: string;
  };
};
```

傳回更新結果，包括哪些欄位已變更。

### TaskGet

**工具名稱：** `TaskGet`

```typescript theme={null}
type TaskGetOutput = {
  task: {
    id: string;
    subject: string;
    description: string;
    status: "pending" | "in_progress" | "completed";
    blocks: string[];
    blockedBy: string[];
  } | null;
};
```

傳回完整工作記錄，或當找不到 ID 時傳回 `null`。

### TaskList

**工具名稱：** `TaskList`

```typescript theme={null}
type TaskListOutput = {
  tasks: Array<{
    id: string;
    subject: string;
    status: "pending" | "in_progress" | "completed";
    owner?: string;
    blockedBy: string[];
  }>;
};
```

傳回目前清單中所有工作的快照。

### ExitPlanMode

**工具名稱：** `ExitPlanMode`

```typescript theme={null}
type ExitPlanModeOutput = {
  plan: string | null;
  isAgent: boolean;
  filePath?: string;
  hasTaskTool?: boolean;
  planWasEdited?: boolean;
  awaitingLeaderApproval?: boolean;
  requestId?: string;
};
```

傳回退出 plan mode 後的計畫狀態。

### ListMcpResources

**工具名稱：** `ListMcpResourcesTool`

```typescript theme={null}
type ListMcpResourcesOutput = Array<{
  uri: string;
  name: string;
  mimeType?: string;
  description?: string;
  server: string;
}>;
```

傳回可用 MCP 資源的陣列。

### ReadMcpResource

**工具名稱：** `ReadMcpResourceTool`

```typescript theme={null}
type ReadMcpResourceOutput = {
  contents: Array<{
    uri: string;
    mimeType?: string;
    text?: string;
    blobSavedTo?: string;
  }>;
  error?: string;
};
```

傳回請求的 MCP 資源的內容。

### EnterWorktree

**工具名稱：** `EnterWorktree`

```typescript theme={null}
type EnterWorktreeOutput = {
  worktreePath: string;
  worktreeBranch?: string;
  message: string;
};
```

傳回關於 git worktree 的資訊。

### ExitWorktree

**工具名稱：** `ExitWorktree`

```typescript theme={null}
type ExitWorktreeOutput = {
  action: "keep" | "remove";
  originalCwd: string;
  worktreePath: string;
  worktreeBranch?: string;
  tmuxSessionName?: string;
  discardedFiles?: number;
  discardedCommits?: number;
  message: string;
};
```

傳回採取的動作和已退出 worktree 的詳細資訊。

### EnterPlanMode

**工具名稱：** `EnterPlanMode`

```typescript theme={null}
type EnterPlanModeOutput = {
  message: string;
};
```

傳回進入 plan mode 的確認。

### CronCreate

**工具名稱：** `CronCreate`

```typescript theme={null}
type CronCreateOutput = {
  id: string;
  humanSchedule: string;
  recurring: boolean;
  durable?: boolean; // 當持久化到 .claude/scheduled_tasks.json 時為真；當僅限工作階段時為假
  nextFireAt?: number;
};
```

傳回工作 ID、人類可讀的排程以及下次執行時間。`nextFireAt` 以紀元毫秒表示該時間，且已套用[抖動](https://code.claude.com/docs/zh-TW/scheduled-tasks.md#jitter)，因此它就是工作設定執行的時間。此欄位需要 TypeScript Agent SDK v0.3.299 或更新版本以及 Claude Code v2.1.299 或更新版本。

### CronDelete

**工具名稱：** `CronDelete`

```typescript theme={null}
type CronDeleteOutput = {
  id: string;
};
```

傳回已刪除工作的 ID。

### CronList

**工具名稱：** `CronList`

```typescript theme={null}
type CronListOutput = {
  jobs: {
    id: string;
    cron: string;
    humanSchedule: string;
    prompt: string;
    recurring?: boolean;
    durable?: boolean;
    nextFireAt?: number;
  }[];
};
```

傳回排程的 cron 工作：來自 `.claude/scheduled_tasks.json` 的持久化工作和來自目前工作階段的僅限工作階段工作。僅限工作階段的工作攜帶 `durable: false`；從磁碟讀取的工作省略欄位。

`nextFireAt` 是工作的下次執行時間（以紀元毫秒表示），已包含[抖動](https://code.claude.com/docs/zh-TW/scheduled-tasks.md#jitter)。任何值都不會早於 `CronList` 呼叫的時間：時間已[過去但未執行](https://code.claude.com/docs/zh-TW/scheduled-tasks.md#how-scheduled-tasks-run)的工作會攜帶該呼叫的時間。此欄位需要 TypeScript Agent SDK v0.3.299 或更新版本以及 Claude Code v2.1.299 或更新版本。

### ScheduleWakeup

**工具名稱：** `ScheduleWakeup`

```typescript theme={null}
type ScheduleWakeupOutput = {
  scheduledFor: number;
  clampedDelaySeconds: number;
  wasClamped: boolean;
  stopped?: boolean;
  cancelledWakeups?: number;
};
```

傳回喚醒將觸發的時間（作為紀元毫秒時間戳記）、實際使用的延遲以及請求的延遲是否被限制。`stopped` 欄位在呼叫以 `stop: true` 結束迴圈時為 `true`。它需要 Claude Code v2.1.202 或更新版本。`cancelledWakeups` 欄位計算 `stop: true` 呼叫取消了多少個待處理喚醒。值 0 表示沒有待處理，重複 `/loop` cron 不會被 `stop: true` 取消。它需要 Claude Code v2.1.206 或更新版本。

### RemoteTrigger

**工具名稱：** `RemoteTrigger`

```typescript theme={null}
type RemoteTriggerOutput = {
  status: number;
  json: string;
  summary?: string;
};
```

傳回觸發操作的 API 回應狀態和本體。

### PushNotification

**工具名稱：** `PushNotification`

```typescript theme={null}
type PushNotificationOutput = {
  message: string;
  pushSent?: boolean;
  localSent?: boolean;
  disabledReason?: "config_off" | "user_present" | "no_transport";
  sentAt?: string;
};
```

傳回傳遞詳細資訊，包括是否傳送了推送或本機通知以及為什麼跳過傳遞。

### ReportFindings

**工具名稱：** `ReportFindings`

```typescript theme={null}
type ReportFindingsOutput = {
  count: number;
  level?: "low" | "medium" | "high" | "xhigh" | "max";
  findings: Array<{
    file: string;
    line?: number;
    summary: string;
    failure_scenario: string;
    short_summary?: string;
    category?: string;
    verdict?: "CONFIRMED" | "PLAUSIBLE";
    outcome?: "fixed" | "skipped" | "no_change_needed";
  }>;
};
```

傳回報告的發現數、Claude 傳遞的 `level` 值以及為結果本體回顯的發現。需要 Claude Code v2.1.196 或更新版本。回顯的 `short_summary` 欄位需要 Claude Code v2.1.212 或更新版本。

### Artifact

**工具名稱：** `Artifact`

```typescript theme={null}
type ArtifactOutput =
  | {
      url: string;
      path: string;
      title?: string;
      version?: string;
      capabilities?: unknown;
      stored?: {
        contract: string;
        capabilities?: Record<string, unknown>;
      };
      warnings?: string[];
      contract?: string;
      updated?: boolean;
      liveSubscription?: string;
    }
  | {
      artifacts: Array<{
        title: string;
        url: string;
        updatedAt?: string;
        rel?: "mine" | "shared";
      }>;
      truncated?: boolean;
      total?: number;
      total_at_least?: true;
      scope?: "shared" | "all";
    };
```

傳回已發佈頁面的 `url` 和為發佈動作發佈的本機 `path`，當發佈重新部署現有 artifact 時 `updated` 設定為 true，`warnings` 攜帶任何發佈時間建議。清單動作改為傳回 `artifacts` 列，當存在超過請求限制的 artifact 時 `truncated` 設定。在其範圍不是 `"mine"` 的清單上，每列攜帶 `rel` 標記使用者是否擁有 artifact 或與他們共享，輸出的 `scope` 記錄哪個非預設範圍產生清單；兩者在預設清單上不存在。

清單結果也會報告 `total`，即符合所列範圍的 artifact 數量，包括超出 `limit` 的項目。當設定 `total_at_least` 時，該數字為下限，可能還有更多 artifact 存在。兩個欄位都需要 Agent SDK v0.3.292 或更新版本。

### Projects

**工具名稱：** `Projects`

```typescript theme={null}
type ProjectsOutput =
  | {
      method: "project_info";
      notice?: string;
      name: string;
      description: string;
      instructions: string;
      docs: Array<{ path: string; created_at: string | null }>;
      files?: Array<{
        path: string;
        file_kind: string;
        created_at: string | null;
      }>;
      sync_sources?: Array<{
        type: string | null;
        config: Record<string, unknown>;
      }>;
      knowledge: {
        knowledge_size: number;
        max_knowledge_size: number;
      };
    }
  | {
      method: "project_read";
      notice?: string;
      path: string;
      file_kind?: string;
      content?: string;
      local_file?: string;
      created_at: string | null;
    }
  | {
      method: "project_search";
      notice?: string;
      rag: boolean;
      hits?: Array<{ name?: string; doc_uuid?: string; text?: string }>;
      docs?: string[];
    }
  | {
      method: "project_write";
      notice?: string;
      path: string;
      doc_uuid: string;
      replaced: boolean;
      present_to_user?: boolean;
      local_path?: string;
    }
  | {
      method: "project_delete";
      notice?: string;
      path: string;
      deleted: boolean;
    };
```

根據 `method` 欄位進行區分，鏡像輸入。`project_read` 在 `content` 中內聯傳回小文字文件，並改為將較大文件寫入 `local_file` 路徑；`project_search` 當專案的索引可用時傳回 RAG `hits` 並設定 `rag: true`，否則回退到 `docs` 路徑清單。

### ReadMcpResourceDir

**工具名稱：** `ReadMcpResourceDirTool`

```typescript theme={null}
type ReadMcpResourceDirOutput = {
  resources: Array<{
    uri: string;
    name: string;
    mimeType?: string;
  }>;
  error?: string;
};
```

傳回目錄資源的直接子項。子目錄以 mimeType `"inode/directory"` 出現；`error` 在伺服器無法列出目錄時攜帶人類可讀的訊息。

### RefreshMcpTools

**工具名稱：** `RefreshMcpTools`

```typescript theme={null}
type RefreshMcpToolsOutput = Array<{
  server: string;
  status: "refreshed" | "error" | "not_connected";
  toolCount?: number; // 此伺服器現在可用的工具
  added?: string[]; // 此重新整理新增的工具名稱
  removed?: string[]; // 此重新整理移除的工具名稱
  error?: string; // 重新整理失敗或伺服器無法使用的原因
}>;
```

傳回每個伺服器一個項目：`refreshed` 表示已套用重新查詢的工具清單，`error` 表示重新查詢失敗且保留了先前的工具集，`not_connected` 表示伺服器沒有即時連線可查詢。

### ShowOnboardingRolePicker

**工具名稱：** `ShowOnboardingRolePicker`

```typescript theme={null}
type ShowOnboardingRolePickerOutput = {
  role?: string;
  dismissed?: boolean;
};
```

傳回使用者的選擇：當他們選擇角色晶片或輸入一個時為 `role`，當他們關閉選擇器時為 `dismissed: true`。空物件表示使用者批准了呼叫而未選擇角色。

### McpOutput

**工具名稱：** 形式為 `mcp__<server>__<tool>` 的動態 MCP 工具名稱

```typescript theme={null}
type McpOutput =
  | string
  | {
      type: string;
      [k: string]: unknown;
    }[]
  | {
      [k: string]: unknown;
    };
```

MCP 工具結果根據伺服器傳回為字串或內容區塊陣列。匯出類型中的尾部純物件分支是 schema 產生過程的副產物。對於同時攜帶 `structuredContent` 或資源連結的結果，請參閱 [`tool_use_result`](#sdkusermessage)，它在其 `content` 成員中持有此值。在執行時值也可能是 `undefined`，儘管匯出的類型不對此進行建模。

## 權限類型

### `PermissionUpdate`

用於更新權限的操作。

```typescript theme={null}
type PermissionUpdate =
  | {
      type: "addRules";
      rules: PermissionRuleValue[];
      behavior: PermissionBehavior;
      destination: PermissionUpdateDestination;
    }
  | {
      type: "replaceRules";
      rules: PermissionRuleValue[];
      behavior: PermissionBehavior;
      destination: PermissionUpdateDestination;
    }
  | {
      type: "removeRules";
      rules: PermissionRuleValue[];
      behavior: PermissionBehavior;
      destination: PermissionUpdateDestination;
    }
  | {
      type: "setMode";
      mode: PermissionMode;
      destination: PermissionUpdateDestination;
    }
  | {
      type: "addDirectories";
      directories: string[];
      destination: PermissionUpdateDestination;
    }
  | {
      type: "removeDirectories";
      directories: string[];
      destination: PermissionUpdateDestination;
    };
```

### `PermissionBehavior`

```typescript theme={null}
type PermissionBehavior = "allow" | "deny" | "ask";
```

### `PermissionUpdateDestination`

```typescript theme={null}
type PermissionUpdateDestination =
  | "userSettings" // 全域使用者設定
  | "projectSettings" // 每個目錄的專案設定
  | "localSettings" // 本機專案設定
  | "session" // 僅限目前工作階段
  | "cliArg"; // CLI 引數
```

### `PermissionRuleValue`

```typescript theme={null}
type PermissionRuleValue = {
  toolName: string;
  ruleContent?: string;
};
```

## 其他類型

### `ApiKeySource`

工作階段請求的 API 金鑰來源，在 [`SDKSystemMessage`](#sdksystemmessage) 初始化訊息上報告為 `apiKeySource`。

```typescript theme={null}
type ApiKeySource =
  | "ANTHROPIC_API_KEY"
  | "apiKeyHelper"
  | "/login managed key"
  | "none"
  | "user"
  | "project"
  | "org"
  | "temporary"
  | "oauth";
```

Claude Code 報告四個值之一：

| 值 | 使用中的金鑰 |
| - | - |
| `ANTHROPIC_API_KEY` | `ANTHROPIC_API_KEY` 環境變數中的金鑰 |
| `apiKeyHelper` | 您的 [`apiKeyHelper`](https://code.claude.com/docs/zh-TW/settings-reference#apikeyhelper) 命令傳回的金鑰 |
| `/login managed key` | 當您使用 [Claude Console 帳戶](https://code.claude.com/docs/zh-TW/authentication.md#claude-console-authentication) 登入時，Claude Code 儲存的金鑰 |
| `none` | 沒有 API 金鑰。工作階段以其他方式進行驗證，例如 claude.ai 登入、bearer token 或雲端提供者 |

Agent SDK v0.3.234 及更新版本在類型中列出這四個值。該類型也保留 `user`、`project`、`org`、`temporary` 和 `oauth`，以便舊程式碼仍能編譯，而 Claude Code 不報告它們。

### `SdkBeta`

可透過 `betas` 選項啟用的可用測試版功能。如需詳細資訊，請參閱 [Beta headers](https://platform.claude.com/docs/en/api/beta-headers)。

```typescript theme={null}
type SdkBeta = "context-1m-2025-08-07";
```

> [!WARNING]
>
> 在 Claude API 上，`context-1m-2025-08-07` 測試版已針對 Claude Sonnet 4.5 和 Claude Sonnet 4 停用。如果您仍對任一模型傳遞此值，超過標準 200K token 上下文視窗的請求會傳回錯誤，因此請將其從 `betas` 中移除。若要以 1M token 上下文視窗執行工作階段，請將 `model` 設定為[預設以 1M 視窗執行](https://code.claude.com/docs/zh-TW/model-config.md#extended-context)的模型，例如 `claude-sonnet-5-5` 或 `claude-opus-5-5`。對於僅能透過其 `[1m]` 變體達到 1M 的模型，請將後綴附加至模型 ID，例如 `claude-opus-4-6[1m]`。

### `SlashCommand`

有關可用命令的資訊。

```typescript theme={null}
type SlashCommand = {
  name: string;
  description: string;
  argumentHint: string;
  aliases?: string[];
  builtin?: boolean;
};
```

`builtin` 在命令是 Claude Code 自身且輸入 `/name` 會執行它的列上為 `true`。對於由使用者、專案、外掛或 MCP 伺服器定義的命令，以及被其中之一[按名稱取代](https://code.claude.com/docs/zh-TW/skills.md#resolve-skills-that-share-a-name)的內建捆綁命令，此欄位不存在。需要 Agent SDK v0.3.277 或更新版本。

### `ModelInfo`

有關可用模型的資訊。

```typescript theme={null}
type ModelInfo = {
  value: string;
  resolvedModel?: string;
  displayName: string;
  description: string;
  supportsEffort?: boolean;
  supportedEffortLevels?: ("low" | "medium" | "high" | "xhigh" | "max")[];
  supportsAdaptiveThinking?: boolean;
  supportsFastMode?: boolean;
  supportsAutoMode?: boolean;
};
```

| 欄位 | 類型 | 說明 |
| :- | :- | :- |
| `value` | `string` | 在 API 呼叫中傳遞的模型識別碼 |
| `resolvedModel` | `string \| undefined` | 此項目的 `value` 所解析成的模型 ID，例如 `sonnet` 別名項目解析為 `claude-sonnet-5-5`。需要 Claude Code v2.1.197 或更新版本。 |
| `displayName` | `string` | 人類可讀的顯示名稱 |
| `description` | `string` | 模型功能的說明 |
| `supportsEffort` | `boolean \| undefined` | 此模型是否支援 effort 等級 |
| `supportedEffortLevels` | `("low" \| "medium" \| "high" \| "xhigh" \| "max")[] \| undefined` | 此模型接受的 effort 等級 |
| `supportsAdaptiveThinking` | `boolean \| undefined` | 此模型是否支援自適應思考，其中 Claude 決定何時以及思考多少 |
| `supportsFastMode` | `boolean \| undefined` | 此模型是否支援快速模式 |
| `supportsAutoMode` | `boolean \| undefined` | 此模型是否支援自動模式 |

### `AgentInfo`

有關可透過 Agent 工具叫用的可用 subagent 的資訊。

```typescript theme={null}
type AgentInfo = {
  name: string;
  description: string;
  model?: string;
};
```

| 欄位 | 類型 | 說明 |
| :- | :- | :- |
| `name` | `string` | agent 類型識別碼（例如 `"Explore"`、`"general-purpose"`） |
| `description` | `string` | 何時使用此 agent 的說明 |
| `model` | `string \| undefined` | 此 agent 使用的模型：別名或模型 ID，或 `'inherit'` 表示父代的模型。當為 `undefined` 時，Claude Code 會依 [subagent 模型順序](https://code.claude.com/docs/zh-TW/sub-agents.md#choose-a-model) 選擇模型 |

### `McpServerProvenance`

提供 `mcp__*` 工具的 MCP 伺服器，以及該伺服器定義的來源。[`PreToolUse`](#pretoolusehookinput)、`PostToolUse`、`PostToolUseFailure`、`PermissionRequest` 和 `PermissionDenied` hook 輸入將其作為 `mcp_server` 攜帶，[`CanUseTool`](#canusetool) 選項將其作為 `mcpServer` 攜帶。對於不來自 MCP 伺服器的工具，兩者都省略它。

```typescript theme={null}
type McpServerProvenance = {
  name: string;
  source: string;
};
```

| 欄位 | 類型 | 說明 |
| :- | :- | :- |
| `name` | `string` | 伺服器註冊時使用的名稱，與 [`mcpServerStatus()`](#query-object) 為其報告的值相同 |
| `source` | `string` | 伺服器定義的來源：`sdk`、`plugin` 或設定範圍 |

`source` 採用以下值之一。該集合是開放的，因此將您不認識的值視為已設定的來源，絕不視為 `sdk`：

* **`sdk`**：您的應用程式註冊的進程內伺服器。只有 SDK 主機應用程式可以註冊此類伺服器，因此已設定的伺服器絕不報告 `sdk`，無論其名稱如何。
* **`plugin`**：[外掛](https://code.claude.com/docs/zh-TW/agent-sdk/plugins.md) 提供的伺服器。其 `name` 是 [外掛提供的 MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md#plugin-provided-mcp-servers) 下所述的範圍化 `plugin:<plugin-name>:<server-name>` 形式。
* **設定範圍**：`user`、`project`、`local`、`dynamic`、`managed`、`enterprise`、`claudeai` 或 `agent`。`.mcp.json` 伺服器報告 `project`，[MCP 安裝範圍](https://code.claude.com/docs/zh-TW/mcp.md#mcp-installation-scopes) 定義 `local`、`project` 和 `user`。您的應用程式在 [`mcpServers` 選項](#options) 中傳遞的伺服器（除了進程內 SDK 伺服器外）報告 `dynamic`。

基於 `source` 而非 `name` 或 `mcp__<server>__` 工具名稱前綴做出信任決定。對於除 `sdk` 以外的任何來源，`name` 是不受信任的文字：在顯示前逸出它。

`McpServerProvenance` 和攜帶它的欄位需要 Agent SDK v0.3.274 或更新版本。

### `McpServerStatus`

已連線 MCP 伺服器的狀態。

```typescript theme={null}
type McpServerStatus = {
  name: string;
  status: "connected" | "failed" | "needs-auth" | "pending" | "disabled";
  serverInfo?: {
    name: string;
    version: string;
  };
  error?: string;
  config?: McpServerStatusConfig;
  scope?: string;
  source?: string;
  tools?: {
    name: string;
    description?: string;
    annotations?: {
      readOnly?: boolean;
      destructive?: boolean;
      openWorld?: boolean;
    };
    _meta?: Record<string, unknown>;
  }[];
};
```

使用 `source` 決定對伺服器的信任程度，並使用每個 `tools` 項目上的 `_meta` 找出伺服器附加到該工具的 UI 資源：

* **`source`**：伺服器定義的來源，其值與 [`McpServerProvenance`](#mcpserverprovenance) 上的 `source` 相同。請根據 `source` 而非 `name` 做出信任決定，因為只有您自己的進程內伺服器會報告 `sdk`，無論任何其他伺服器以何種名稱註冊。如果您不認識某個 `source` 值，請以對待任何 `source` 不是 `sdk` 之伺服器的方式對待該伺服器。需要 Agent SDK v0.3.274 或更新版本
* **`_meta`**：來自伺服器為該工具宣告之 `_meta` 的 `ui` 物件和 `ui/resourceUri` 字串。Claude Code 會扣留所有其他 `_meta` 鍵。`ui/resourceUri` 是 `ui.resourceUri` 較舊的頂層寫法。當伺服器將 [MCP Apps UI 資源](https://code.claude.com/docs/zh-TW/mcp.md#reference-mcp-resources) 附加到工具時，`ui.resourceUri` 或 `ui/resourceUri` 會保存該資源的 `ui://` URI。使用 [`readMcpResource()`](#query-object) 擷取該 URI，並在您的應用程式中呈現該資源。需要 Agent SDK v0.3.280 或更新版本

Claude Code 僅在 subtype 為 `init` 的 `system` 訊息之 [`capabilities`](#sdksystemmessage) 陣列列出 `mcp_tool_ui_meta_v1` 時才傳送 `_meta`。您無需自行開啟 `mcp_tool_ui_meta_v1`。

#### 當工具的 `_meta.ui` 僅包含 `visibility` 時

如果您的伺服器為工具宣告了 `ui.resourceUri`，但您的應用程式收到的 `_meta.ui` 僅包含 `visibility`，表示伺服器傳送的 `ui` 物件未通過 Claude Code 的某項檢查。請將您伺服器 `tools/list` 回應中的 `_meta` 與每個鍵的檢查進行比較：

* **`ui`**：若三項檢查全部通過，會原封不動地送達您的應用程式，包括 `resourceUri` 和 `visibility` 以外的任何成員：

  * `resourceUri` 不存在，或是以 `ui://` 開頭的字串
  * `visibility` 不存在，或僅列出 `"model"` 和 `"app"`
  * 整個物件序列化為 JSON 時最多 4,096 個字元

  如果任何一項檢查失敗，您的應用程式最多只會收到一個 `ui`，其唯一成員是包含伺服器所列 `"model"` 和 `"app"` 項目的 `visibility` 陣列。
* **`ui/resourceUri`**：若它是以 `ui://` 開頭且最多 4,096 個字元的字串，就會送達您的應用程式。否則 Claude Code 會將其捨棄

當 Claude Code 沒有剩下任何可傳送的 `ui` 成員或 `ui/resourceUri` 字串時，該 `tools` 項目完全沒有 `_meta`。

### `McpServerStatusConfig`

由 `mcpServerStatus()` 報告的 MCP 伺服器的設定。這是所有 MCP 伺服器傳輸類型的聯合。

```typescript theme={null}
type McpServerStatusConfig =
  | McpStdioServerConfig
  | McpSSEServerConfig
  | McpHttpServerConfig
  | McpSdkServerConfig
  | McpClaudeAIProxyServerConfig;
```

如需每個傳輸類型的詳細資訊，請參閱 [`McpServerConfig`](#mcpserverconfig)。

### `AccountInfo`

已驗證使用者的帳戶資訊。

```typescript theme={null}
type AccountInfo = {
  email?: string;
  organization?: string;
  subscriptionType?: string;
  tokenSource?: string;
  apiKeySource?: string;
};
```

### `ModelUsage`

結果訊息中傳回的每個模型使用統計資訊。`costUSD` 值是用戶端估計。如需計費注意事項，請參閱 [追蹤成本和使用](https://code.claude.com/docs/zh-TW/agent-sdk/cost-tracking.md)。

```typescript theme={null}
type ModelUsage = {
  inputTokens: number;
  outputTokens: number;
  thinkingTokens?: number;
  cacheReadInputTokens: number;
  cacheCreationInputTokens: number;
  webSearchRequests: number;
  costUSD: number;
  contextWindow: number;
  maxOutputTokens: number;
  canonicalModel?: string;
  provider?: string;
  costBasis?: 'list' | 'managed' | 'unknown';
};
```

`thinkingTokens` 計算此模型產生的思考 token。`outputTokens` 已包含它們，因此不要將兩者相加。在某個回合於會記錄它的 Claude Code 版本上執行之前，該欄位不存在，因此在較早版本上開始的已恢復工作階段會報告部分計數。`thinkingTokens` 需要 Agent SDK v0.3.257 或更新版本。

`canonicalModel` 和 `provider` 欄位需要 Claude Code v2.1.218 或更新版本。`canonicalModel` 是定價查詢使用的規範模型 ID；它可能與作為項目鍵的原始模型字串不同，例如當該字串是提供者特定 ID 或別名時。

`provider` 命名提供模型的 API 後端，例如 `firstParty`、`bedrock`、`vertex`、`foundry`、`anthropicAws`、`mantle` 或 `gateway`。

`costBasis` 命名為模型最新請求定價的價格表：`list` 表示清單價格，`managed` 表示 [`modelPricing`](https://code.claude.com/docs/zh-TW/settings-reference#modelpricing) 表，或 `unknown` 表示模型 ID 都不符合時。該欄位需要 Claude Code v2.1.246 或更新版本。

### `ConfigScope`

```typescript theme={null}
type ConfigScope = "local" | "user" | "project";
```

### `NonNullableUsage`

[`Usage`](#usage) 的版本，除了 `fallback_credit`（仍可為 `null`）之外，所有可為空的欄位都變為不可為空。

```typescript theme={null}
type NonNullableUsage = {
  [K in keyof Usage]: K extends "fallback_credit"
    ? Usage[K]
    : NonNullable<Usage[K]>;
};
```

### `Usage`

token 使用統計資訊。這是來自 `@anthropic-ai/sdk` 的 `BetaUsage` 類型。

```typescript theme={null}
type Usage = {
  input_tokens: number;
  output_tokens: number;
  cache_creation_input_tokens: number | null;
  cache_read_input_tokens: number | null;
  cache_creation: {
    ephemeral_5m_input_tokens: number;
    ephemeral_1h_input_tokens: number;
  } | null;
  server_tool_use: BetaServerToolUsage | null;
  service_tier: "standard" | "priority" | "batch" | null;
  speed: "standard" | "fast" | null;
  inference_geo: string | null;
  iterations: BetaIterationsUsage | null;
  output_tokens_details: BetaOutputTokensDetails | null;
  fallback_credit: BetaFallbackCreditUsage | null;
};
```

`BetaServerToolUsage`、`BetaIterationsUsage`、`BetaOutputTokensDetails` 和 `BetaFallbackCreditUsage` 在 `@anthropic-ai/sdk` 中定義。

`output_tokens_details` 按類別分解計費輸出。它目前攜帶一個欄位 `thinking_tokens: number`，計算模型作為內部推理產生的輸出 token，包括思考區塊分隔符。`output_tokens_details` 欄位需要 TypeScript SDK v0.3.228 或更新版本，該版本捆綁 Claude Code v2.1.228。

* **計費**：讀取分解以進行可觀測性，而非計費。`output_tokens` 保持為權威總計，`output_tokens - thinking_tokens` 近似非推理輸出。
* **計數涵蓋的內容**：模型產生的原始推理，可能比回應正文中傳回的思考文字更長。API 透過重新 token 化該原始文字來計算它，因此它可能與模型的確切生成計數相差幾個 token。
* **串流**：在串流助手訊息上，此分解（如 `output_tokens`）是 `message_start` 預留位置，不攜帶實際計數，因此從結果訊息的 `usage` 讀取它，如 [從結果訊息讀取輸出 token](https://code.claude.com/docs/zh-TW/agent-sdk/cost-tracking.md#read-output-tokens-from-the-result-message) 所述。在結果訊息上，當模型或提供者不報告分解時，`thinking_tokens` 讀取 `0`。
* **`null` 情況**：`output_tokens_details` 本身在 Claude Code 合成的助手訊息上為 `null`，例如 API 錯誤訊息。

`Usage` 是否攜帶 `fallback_credit` 取決於您安裝的 `@anthropic-ai/sdk`，該套件於 0.115.0 中新增此欄位。

### `CallToolResult`

MCP 工具結果類型（來自 `@modelcontextprotocol/sdk/types.js`）。`structuredContent` 是可與 `content` 一起傳回的 JSON 物件，包括影像區塊。請參閱 [傳回結構化資料](https://code.claude.com/docs/zh-TW/agent-sdk/custom-tools.md#return-structured-data)。

```typescript theme={null}
type CallToolResult = {
  content: Array<{
    type: "text" | "image" | "audio" | "resource" | "resource_link";
    // Additional fields vary by type
  }>;
  structuredContent?: Record<string, unknown>;
  isError?: boolean;
};
```

### `SDKMcpResourceLink`

MCP 工具透過參考傳回的一個檔案。Claude Code 從工具結果中的 `resource_link` 區塊建立每個項目，並將清單作為 [`SDKUserMessage.tool_use_result`](#sdkusermessage) 上的 `resourceLinks` 傳遞，或在呼叫在背景完成時作為 [`SDKTaskNotificationMessage`](#sdktasknotificationmessage) 上的 `resource_links` 傳遞。需要 Agent SDK v0.3.257 或更新版本。

```typescript theme={null}
type SDKMcpResourceLink = {
  uri: string;
  name: string;
  title?: string;
  description?: string;
  mimeType?: string;
  size?: number;
  annotations?: Record<string, unknown>;
};
```

Claude Code 會捨棄 `uri` 或 `name` 不是字串的區塊，並省略其值不是列出類型的可選欄位。

| 欄位 | 類型 | 說明 |
| :- | :- | :- |
| `uri` | `string` | 資源的 URI，如伺服器傳回的 |
| `name` | `string` | 伺服器給予資源的名稱 |
| `title` | `string \| undefined` | 顯示標題，當伺服器設定時 |
| `description` | `string \| undefined` | 說明，當伺服器設定時 |
| `mimeType` | `string \| undefined` | MIME 類型，當伺服器設定時 |
| `size` | `number \| undefined` | 大小（以位元組為單位），當伺服器設定時 |
| `annotations` | `Record<string, unknown> \| undefined` | 區塊的 MCP 註解物件，當伺服器設定時 |

### `ThinkingConfig`

控制 Claude 的思考/推理行為。優先於已棄用的 `maxThinkingTokens`。

```typescript theme={null}
type ThinkingDisplay = "summarized" | "omitted";

type ThinkingConfig =
  | { type: "adaptive"; display?: ThinkingDisplay } // The model determines when and how much to reason (Opus 4.6+)
  | { type: "enabled"; budgetTokens?: number; display?: ThinkingDisplay } // Fixed thinking token budget
  | { type: "disabled" }; // No extended thinking
```

可選的 `display` 欄位控制思考文字是否以 `"summarized"` 或 `"omitted"` 傳回。在 Claude Opus 4.7 及更新版本上，API 預設為 `"omitted"`，因此設定 `"summarized"` 以在 `thinking` 區塊中接收思考內容。Claude Code 不會將您的 `display` 值傳遞給某些提供者，例如 Amazon Bedrock 和 Google Cloud 的 Agent Platform。在這些提供者上，Opus 4.7 及更新版本即使在您將 `display` 設定為 `"summarized"` 時也會傳回空 `thinking` 區塊。

### `SpawnedProcess`

自訂程序生成的介面（與 `spawnClaudeCodeProcess` 選項搭配使用）。`ChildProcess` 已滿足此介面。

```typescript theme={null}
interface SpawnedProcess {
  stdin: Writable;
  stdout: Readable;
  readonly killed: boolean;
  readonly exitCode: number | null;
  kill(signal: NodeJS.Signals): boolean;
  on(
    event: "exit",
    listener: (code: number | null, signal: NodeJS.Signals | null) => void
  ): void;
  on(event: "error", listener: (error: Error) => void): void;
  once(
    event: "exit",
    listener: (code: number | null, signal: NodeJS.Signals | null) => void
  ): void;
  once(event: "error", listener: (error: Error) => void): void;
  off(
    event: "exit",
    listener: (code: number | null, signal: NodeJS.Signals | null) => void
  ): void;
  off(event: "error", listener: (error: Error) => void): void;
}
```

### `SpawnOptions`

傳遞至自訂生成函式的選項。

```typescript theme={null}
interface SpawnOptions {
  command: string;
  args: string[];
  cwd?: string;
  env: Record<string, string | undefined>;
  signal: AbortSignal;
}
```

> [!NOTE]
>
> `signal` 欄位告訴您的生成函式何時拆除程序。將其作為 `signal` 選項傳遞至 Node 的 `spawn()`，或將其傳遞至您的 VM 或容器拆除處理程式。
>
> 此信號不會在 [`Options.abortController`](#options) 中止時立即觸發。SDK 首先關閉程序的 stdin 並等待約兩秒，以便 CLI 可以乾淨地關閉，然後中止此信號。若要在呼叫者中止時立即做出反應，請在您自己的 `Options.abortController.signal` 上監聽，您的生成函式可以從其封閉範圍參考。

### `McpSetServersResult`

`setMcpServers()` 操作的結果。

```typescript theme={null}
type McpSetServersResult = {
  added: string[];
  removed: string[];
  errors: Record<string, string>;
};
```

`setMcpServers()` 的 promise 會在新增的 stdio、HTTP 和 SSE 伺服器連線或失敗後解決，因此來自已連線伺服器的工具在下一回合可用。

當您呼叫 `setMcpServers()` 時，Claude Code 應用這些規則：

* **呼叫未命名的伺服器**：在[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)之外，Claude Code 會中斷先前 `setMcpServers()` 呼叫所新增的伺服器以及進程內 SDK 伺服器的連線，並在 `removed` 中列出它們。其他伺服器會持續執行，且不會列在 `removed` 中，其中包括來自 [`mcpServers`](#options) 選項的 stdio、HTTP 和 SSE 伺服器、來自設定檔的伺服器，以及外掛提供的伺服器。
* **先前 `setMcpServers()` 呼叫所新增的 stdio、HTTP 和 SSE 伺服器**：在雲端工作階段之外，您以相同設定再次命名的伺服器會保留其連線和工具。它既不會出現在 `added` 中，也不會出現在 `removed` 中。如果您傳遞變更後的設定，Claude Code 會使用該設定重新連線該伺服器，並將其列在 `added` 中，而非 `removed` 中。
* **呼叫所命名、但先前沒有任何呼叫新增的 stdio、HTTP 和 SSE 伺服器**：在雲端工作階段之外，Claude Code 會新增該伺服器並將其列在 `added` 中；若拒絕該伺服器，則列在 `errors` 中。
* **呼叫所命名的進程內 SDK 伺服器**：已透過 `mcpServers` 或先前呼叫註冊的伺服器會保留其執行中的實例和逾時。如果您為其傳遞 [`tools` 政策清單](#mcpsdkserverconfigwithinstance)，即使是空清單，也會取代其政策；否則政策保持不變。若要在雲端工作階段之外執行新實例，請在一次呼叫中省略該伺服器，並在下一次呼叫中命名它。
* **CLI 在啟動時啟動的內建伺服器**：如果呼叫命名一個，Claude Code 會捨棄該項目並在 `errors` 中報告它。
* **與 MCP 安裝範圍（例如 `.mcp.json`）中的伺服器同名的 stdio、HTTP 或 SSE 伺服器**：在該名稱下，工作階段會使用您的伺服器的工具，而非[安裝範圍伺服器](https://code.claude.com/docs/zh-TW/mcp.md#mcp-installation-scopes)的工具。在 Claude Code v2.1.305 之前，當您的應用程式[重新載入外掛](#query-object)時，Claude Code 可能會中斷您的伺服器連線，改為連線至安裝範圍伺服器。

`added` 列出 Claude Code 新增或替換的伺服器，無論它們是否連線。未能連線的伺服器同時出現在 `added` 和 `errors` 中，失敗文字在 `errors` 下，`failed` 列在 [`mcpServerStatus()`](#methods) 中。在 Claude Code v2.1.257 之前，連線嘗試拋出的伺服器僅在 `errors` 下報告。

以 `Blocked by enterprise` 開頭的 `errors` 值表示政策拒絕了該伺服器，而非連線失敗：

* `Blocked by enterprise policy (allowedMcpServers/deniedMcpServers)`：該伺服器不在 `added` 中。有 [`deniedMcpServers`](https://code.claude.com/docs/zh-TW/managed-mcp#policy-based-control-with-allowlists-and-denylists) 項目與其相符，或已設定 `allowedMcpServers` 清單但未包含它。如果該清單位於您透過 [`settingSources`](#options) 載入的設定檔中，請編輯該檔案。如果它位於受管設定中，請要求您的管理員變更它。
* `Blocked by enterprise managed policy`：該伺服器在 `added` 中，並在 `mcpServerStatus()` 中有一個 `failed` 列。請詢問管理員是哪項政策封鎖了它。

### `RewindFilesResult`

`rewindFiles()` 操作的結果。

```typescript theme={null}
type RewindFilesResult = {
  canRewind: boolean;
  error?: string;
  filesChanged?: string[];
  insertions?: number;
  deletions?: number;
  skippedLinks?: number;
};
```

`skippedLinks` 計算倒帶為確保連結安全而拒絕恢復或刪除的追蹤路徑：追蹤路徑上的符號連結、硬連結或其他非常規檔案，不再解析為檢查點建立時指向的位置的父目錄，或無法安全讀取的備份。該欄位需要 Claude Code v2.1.216 或更新版本。使用 `rewindFiles(userMessageId, { dryRun: true })` 的預覽呼叫永遠不會設定它。

### `SDKStatusMessage`

狀態更新訊息（例如壓縮）。

```typescript theme={null}
type SDKStatusMessage = {
  type: "system";
  subtype: "status";
  status: "compacting" | null;
  permissionMode?: PermissionMode;
  uuid: UUID;
  session_id: string;
};
```

### `SDKTaskNotificationMessage`

背景工作完成、失敗或停止時的通知。背景工作包括 `run_in_background` Bash 命令、[Monitor](#monitor) 監視和背景 subagent。如需 `run_id` 和 `ambient` 欄位，請參閱 [`SDKTaskStartedMessage`](#sdktaskstartedmessage)，它定義了這些欄位及其版本要求。

```typescript theme={null}
type SDKTaskNotificationMessage = {
  type: "system";
  subtype: "task_notification";
  task_id: string;
  run_id?: string;
  tool_use_id?: string;
  status: "completed" | "failed" | "stopped";
  reason?: "worker_restart";
  output_file: string;
  summary: string;
  ambient?: boolean;
  usage?: {
    total_tokens: number;
    tool_uses: number;
    duration_ms: number;
  };
  resource_links?: SDKMcpResourceLink[];
  uuid: UUID;
  session_id: string;
};
```

`reason` 會在工作因其自身完成、失敗或停止以外的原因結束時設定，需要 Agent SDK v0.3.273 或更新版本。Claude Code 僅在透過 claude.ai 連線的工作階段中設定它：雲端工作階段（包括在自我託管執行器上的工作階段）以及 Remote Control 工作階段。本機 `query()` 呼叫永遠不會設定它。其唯一的值 `worker_restart` 表示正在執行該工作的 Claude Code 程序已重新啟動。該通知帶有狀態 `"stopped"`，因此請將該工作視為既未完成也未失敗。

當 Claude Code [將長 MCP 工具呼叫移至背景](https://code.claude.com/docs/zh-TW/mcp.md#automatic-backgrounding-of-long-tool-calls) 時，該呼叫的 `tool_result` 區塊僅保留預留位置，呼叫的實際結果在此通知中到達。使用 `tool_use_id` 將通知與呼叫進行比對。在 `completed` 通知上，`resource_links` 以 [`SDKMcpResourceLink`](#sdkmcpresourcelink) 項目列出工具透過參考傳回的檔案，具有與 [`tool_use_result.resourceLinks`](#sdkusermessage) 相同的 50 連結和 64 KiB 限制。Claude Code 在結果沒有連結時省略 `resource_links`，在不是 MCP 工具呼叫的工作通知上也會省略。`resource_links` 需要 Agent SDK v0.3.257 或更新版本。

Claude Code 在傳送給模型的每個工作通知前面加上通知，除了帶有 [`scheduled-trigger` 子類型](#task-notification-subkinds) 戳記的傳遞外，它們改為攜帶指派工作框架。通知指出沒有發生人類輸入，因此模型不會將通知視為使用者指令或核准。

若要偵測工作通知回合，請在 [`SDKUserMessage`](#sdkusermessage) 或 [`SDKResultMessage`](#sdkresultmessage) 上檢查 `origin.kind === "task-notification"`，而不是在通知文字上進行比對。如果您需要知道引發它的內容，請從同一欄位讀取 `subkind`。在 v2.1.205 之前，Claude Code 在工作階段閒置時到達的通知上省略通知。

### `SDKToolUseSummaryMessage`

對話中工具使用的摘要。

```typescript theme={null}
type SDKToolUseSummaryMessage = {
  type: "tool_use_summary";
  summary: string;
  preceding_tool_use_ids: string[];
  uuid: UUID;
  session_id: string;
};
```

### `SDKHookStartedMessage`

在 hook 開始執行時發出。

Claude Code 將此訊息、[`SDKHookProgressMessage`](#sdkhookprogressmessage) 和 [`SDKHookResponseMessage`](#sdkhookresponsemessage) 立即傳遞至訊息串流，包括在工作階段啟動期間 `SessionStart` 或 `Setup` hook 仍在執行時。Claude Code v2.1.169 至 v2.1.203 在 `SessionStart` 或 `Setup` hook 完成後以一個批次傳遞這些訊息；v2.1.204 恢復了即時傳遞。

如果您使用 [`startup()`](#startup) 啟動工作階段，這些訊息會在您呼叫 `.query()` 並反覆運算結果後送達。

```typescript theme={null}
type SDKHookStartedMessage = {
  type: "system";
  subtype: "hook_started";
  hook_id: string;
  hook_name: string;
  hook_event: string;
  uuid: UUID;
  session_id: string;
};
```

### `SDKHookProgressMessage`

在 hook 執行時發出，帶有 stdout/stderr 輸出。

```typescript theme={null}
type SDKHookProgressMessage = {
  type: "system";
  subtype: "hook_progress";
  hook_id: string;
  hook_name: string;
  hook_event: string;
  stdout: string;
  stderr: string;
  output: string;
  uuid: UUID;
  session_id: string;
};
```

### `SDKHookResponseMessage`

在 hook 完成執行時發出。

```typescript theme={null}
type SDKHookResponseMessage = {
  type: "system";
  subtype: "hook_response";
  hook_id: string;
  hook_name: string;
  hook_event: string;
  output: string;
  stdout: string;
  stderr: string;
  exit_code?: number;
  outcome: "success" | "error" | "cancelled";
  uuid: UUID;
  session_id: string;
};
```

### `SDKToolProgressMessage`

在工具執行時定期發出，以指示進度。

```typescript theme={null}
type SDKToolProgressMessage = {
  type: "tool_progress";
  tool_use_id: string;
  tool_name: string;
  parent_tool_use_id: string | null;
  elapsed_time_seconds: number;
  task_id?: string;
  heartbeat?: boolean;
  subagent_type?: string;
  subagent_retry?: {
    agent_id: string;
    attempt: number;
    max_retries: number;
    retry_delay_ms: number;
    error_status: number | null;
    error_category: string;
  };
  uuid: UUID;
  session_id: string;
};
```

當工具呼叫在主對話中執行時，Claude Code 每 30 秒發出一個 `tool_progress` 訊息，帶有 `heartbeat: true`。每個心跳攜帶工具名稱和經過的秒數，因此您可以區分長執行呼叫和停滯工作階段。Claude Code 不為 subagent 內的工具呼叫發出心跳。`heartbeat` 欄位需要 Agent SDK v0.3.214 或更新版本。在 v2.1.257 之前，Claude Code 也不為前景 Agent 工具呼叫發出心跳。

在除心跳外的 Agent 工具的 `tool_progress` 訊息上，`subagent_type` 命名執行中的 subagent 類型，例如 `general-purpose`。`subagent_retry` 在該 subagent 等待 API 錯誤退避（例如速率限制或過載）時存在，每次重試嘗試一個訊息。兩個欄位都需要 Agent SDK v0.3.214 或更新版本。

若要從 `subagent_retry` 呈現重試指示器：

* 按 `parent_tool_use_id` 追蹤指示器，它對每個 subagent 是唯一的。`tool_use_id` 由來自一個助手回合的平行 subagent 共享，因此按它追蹤會讓一個 subagent 的更新清除另一個的指示器。
* 當同一 `parent_tool_use_id` 的稍後 `tool_progress` 到達且既不帶 `subagent_retry` 也不帶 `heartbeat: true` 時，或當工具的結果訊息到達時，清除指示器。帶 `heartbeat: true` 的框架僅報告活躍性，因此在此類框架到達時保持指示器。`attempt` 可能在持續重試下超過 `max_retries`，因此不要從計數器衍生清除。
* 將 `error_category` 視為選擇您自己訊息文字的 token，而非顯示文字。值為 `rate_limit`、`overloaded`、`authentication_failed`、`server_error`、`cloud_credential_error` 和 `unknown`。處理您不認識的值的方式與處理 `unknown` 的方式相同，因為稍後的版本可以新增值。

### `SDKAuthStatusMessage`

在身分驗證流程期間發出。

```typescript theme={null}
type SDKAuthStatusMessage = {
  type: "auth_status";
  isAuthenticating: boolean;
  output: string[];
  error?: string;
  uuid: UUID;
  session_id: string;
};
```

### `SDKTaskStartedMessage`

在工作開始時發出。`task_type` 欄位對 Bash 命令和 [Monitor](#monitor) 監視為 `"local_bash"`，對 subagent 為 `"local_agent"`，或 `"remote_agent"`。

```typescript theme={null}
type SDKTaskStartedMessage = {
  type: "system";
  subtype: "task_started";
  task_id: string;
  run_id?: string;
  tool_use_id?: string;
  description: string;
  task_type?: string;
  is_backgrounded?: boolean;
  spawn_depth?: number;
  parent_task_id?: string;
  ambient?: boolean;
  uuid: UUID;
  session_id: string;
};
```

`run_id` 識別工作的一次執行。當工作以相同的 `task_id` 再次執行時，例如 [Claude 恢復的 subagent](https://code.claude.com/docs/zh-TW/agent-sdk/subagents.md#resume-subagents)，新的執行會取得新的 `run_id`。該欄位需要 Agent SDK v0.3.292 或更新版本。使用它來區分同一工作的各次執行：

* **將訊息與執行進行比對**：同一次執行的 `task_started`、[`task_progress`](#sdktaskprogressmessage)、[`task_updated`](#sdktaskupdatedmessage) 和 [`task_notification`](#sdktasknotificationmessage) 訊息攜帶相同的 `run_id`。每個 [`SDKBackgroundTasksChangedMessage`](#sdkbackgroundtaskschangedmessage) 中該執行的項目也攜帶它，傳遞該執行通知的使用者訊息之 origin 上的 [`runId`](#task-notification-subkinds) 也是如此。
* **偵測延遲到達的訊息**：以純字串比較時，同一工作的執行 ID 會依各次執行開始的順序排序，因此 `run_id` 排在您正在顯示的執行之前的訊息來自較早的執行。除了該比較之外，請將此值視為不透明值。
* **退回使用 `task_id`**：當訊息未攜帶 `run_id` 時，例如已恢復的工作階段為關閉先前程序所啟動的工作而發出的 `task_notification`，請依 `task_id` 歸屬該訊息。

例如，以下三則訊息（已刪減為其識別欄位）來自 Claude 恢復過一次的背景 subagent。兩則 `task_started` 訊息共用同一個 `task_id`，而結束第一次執行的通知攜帶第一次執行的 ID：

```json theme={null}
{"subtype": "task_started", "task_id": "a5c2e8f41b09d7a36", "run_id": "0mubbs7i8-6f0c2d41"}
{"subtype": "task_notification", "task_id": "a5c2e8f41b09d7a36", "run_id": "0mubbs7i8-6f0c2d41", "status": "completed"}
{"subtype": "task_started", "task_id": "a5c2e8f41b09d7a36", "run_id": "0mubc18m1-b7719e05"}
```

`ambient` 對不屬於工作階段工作的工作為 `true`，例如 Claude Code 為其自身運作而執行的工作。即時更新監視器也是環境工作，包括使用者要求的監視器。從活動指示器中排除環境工作。該欄位需要 Agent SDK v0.3.247 或更新版本。

`ambient` 也出現在 [`SDKTaskNotificationMessage`](#sdktasknotificationmessage) 和 [`SDKBackgroundTasksChangedMessage`](#sdkbackgroundtaskschangedmessage) 項目上。

`is_backgrounded` 和 `spawn_depth` 描述 Claude Code 如何啟動工作。兩個欄位都需要 Agent SDK v0.3.238 或更新版本。

* `is_backgrounded`：Claude Code 在 `"local_agent"` 和 `"local_bash"` 工作上設定它。`true` 表示工作在背景執行。`false` 表示工作在前景執行，啟動它的工具呼叫保持阻止，直到工作完成或移至背景。
* `spawn_depth`：Claude Code 僅在 `"local_agent"` 工作上設定它。主執行緒生成的 subagent 的深度為 `1`。深度 `1` subagent 生成的 subagent 的深度為 `2`，以此類推。

[已恢復的 subagent](https://code.claude.com/docs/zh-TW/agent-sdk/subagents.md#resume-subagents) 始終報告 `is_backgrounded: true`，因為 Claude Code 在背景執行每個已恢復的 subagent。當前景工作稍後移至背景時，Claude Code 在 [`task_updated`](#sdktaskupdatedmessage) 訊息中報告新的 `is_backgrounded` 值，而不是傳送第二個 `task_started`。

`parent_task_id` 保存啟動此工作的 subagent 的 `task_id`。使用它將每個工作歸類到啟動它的 subagent 之下。Claude Code 在 subagent、Bash 和 [Monitor](#monitor) 工作上設定它。該欄位需要 Agent SDK v0.3.292 或更新版本。在下列情況下，該欄位不存在：

* 主執行緒啟動了該工作
* Claude Code 不再追蹤父工作
* [隊員](https://code.claude.com/docs/zh-TW/agent-teams.md)或工作流程內的 agent 啟動了該工作

父工作可能是前景工作或已結束的工作，因此請將您不認識的 ID 視為沒有父工作。

### `SDKTaskProgressMessage`

在 subagent 或背景工作執行時定期發出。如需 `run_id` 欄位，請參閱 [`SDKTaskStartedMessage`](#sdktaskstartedmessage)，它定義了該欄位及其版本要求。

對於 subagent 工作，`summary` 欄位攜帶模型產生的進度摘要，僅在啟用 [`agentProgressSummaries`](#options) 時填入。對於 [背景化的 MCP 工具呼叫](https://code.claude.com/docs/zh-TW/mcp.md#automatic-backgrounding-of-long-tool-calls)，`summary` 攜帶 MCP 伺服器最新報告的進度，不依賴該選項。

```typescript theme={null}
type SDKTaskProgressMessage = {
  type: "system";
  subtype: "task_progress";
  task_id: string;
  run_id?: string;
  tool_use_id?: string;
  description: string;
  subagent_type?: string;
  usage: {
    total_tokens: number;
    tool_uses: number;
    duration_ms: number;
  };
  last_tool_name?: string;
  summary?: string;
  uuid: UUID;
  session_id: string;
};
```

### `SDKTaskUpdatedMessage`

在背景工作的狀態變更時發出，例如當它從 `running` 轉換為 `completed` 時。將 `patch` 合併到以 `task_id` 為鍵的本機工作對應表中。`end_time` 欄位是 Unix 紀元時間戳記（以毫秒為單位），可與 `Date.now()` 比較。如需 `run_id` 欄位，請參閱 [`SDKTaskStartedMessage`](#sdktaskstartedmessage)，它定義了該欄位及其版本要求。

```typescript theme={null}
type SDKTaskUpdatedMessage = {
  type: "system";
  subtype: "task_updated";
  task_id: string;
  run_id?: string;
  patch: {
    status?: "pending" | "running" | "completed" | "failed" | "killed";
    description?: string;
    end_time?: number;
    total_paused_ms?: number;
    error?: string;
    is_backgrounded?: boolean;
  };
  uuid: UUID;
  session_id: string;
};
```

### `SDKBackgroundTasksChangedMessage`

每當即時背景工作集變更時發出：工作啟動、完成或被終止；前景 agent 被背景化；或工作的 `description`、`ambient` 或 `parent_task_id` 欄位變更。如需每個項目上的 `run_id` 和 `parent_task_id` 欄位，請參閱 [`SDKTaskStartedMessage`](#sdktaskstartedmessage)，它定義了這些欄位及其版本要求。

`tasks` 陣列是完整的即時集。用每個 payload 替換任何快取集，而不是配對 `task_started` 和 `task_notification` 事件，如此下一個成員資格變更會更正您遺漏的任何事件。

當工作結束時，其 [`task_updated`](#sdktaskupdatedmessage) 和 [`task_notification`](#sdktasknotificationmessage) 會在將其從清單中移除的 `background_tasks_changed` 之前到達。除此之外，相對於每個工作事件的順序未指定。

啟動時不發出任何內容。每當工作階段的 CLI 程序啟動或重新啟動時重設為空集，並讓下一個成員資格變更重新填入它。

當您向執行中的工作階段傳送重複的 `initialize` 控制請求時，例如在傳輸中斷後使用 [`reinitialize()`](#query-object)，Claude Code 在回應後接著傳送目前即時集的快照，即使它是空的。因此重新連線的主機可以了解執行中的內容，而無需等待下一個成員資格變更。在 Agent SDK v0.3.239 之前，Claude Code 在重複 `initialize` 後沒有傳送快照。

需要 Claude Code v2.1.203 或更新版本。

```typescript theme={null}
type SDKBackgroundTasksChangedMessage = {
  type: "system";
  subtype: "background_tasks_changed";
  tasks: {
    task_id: string;
    run_id?: string;
    task_type: string;
    subagent_type?: string;
    description: string;
    parent_task_id?: string;
    ambient?: boolean;
  }[];
  uuid: UUID;
  session_id: string;
};
```

`subagent_type` 在 [`task_type`](#sdktaskstartedmessage) 為 `"local_agent"` 的項目上命名 subagent 類型，例如 `general-purpose` 或自訂 subagent 的名稱。該欄位需要 Agent SDK v0.3.293 或更新版本。

### `SDKThinkingTokensMessage`

在 Claude 產生思考區塊時發出，包括經過編輯的區塊。`estimated_tokens` 是目前區塊中迄今為止產生的思考 token 的累計估計，`estimated_tokens_delta` 是此框架攜帶的增量。使用這些估計進行進度顯示。

當模型或提供者報告分解時，頂層 agent 迴圈的最終計數是結果訊息的 [`usage.output_tokens_details.thinking_tokens`](#usage)，[不包括 subagent token](https://code.claude.com/docs/zh-TW/agent-sdk/cost-tracking.md#get-the-total-cost-of-a-query)。

需要 Claude Code v2.1.153 或更新版本。

```typescript theme={null}
type SDKThinkingTokensMessage = {
  type: "system";
  subtype: "thinking_tokens";
  estimated_tokens: number;
  estimated_tokens_delta: number;
  user_message_uuid?: string;
  uuid: UUID;
  session_id: string;
};
```

### `SDKSessionStateChangedMessage`

當 Claude Code 報告工作階段的狀態時發出。若要接收這些訊息，請設定 [`CLAUDE_CODE_EMIT_SESSION_STATE_EVENTS=1`](https://code.claude.com/docs/zh-TW/env-vars#variables)。Claude Code 可能多次報告相同的狀態，因此請將訊息視為工作階段的目前狀態，而非狀態轉換。

`state` 欄位攜帶下列值之一：

* `running`：工作階段正在運作。
* `idle`：Claude Code 正在等待您的下一個提示詞。
* `requires_action`：工作階段因等待其傳送給您主機的請求之回答而受阻，例如權限提示。

回合的 `idle` 訊息與其 `result` 訊息可能以任一順序到達。若要變更 `idle` 是否等待背景工作（例如背景 subagent 或 [工作流程](https://code.claude.com/docs/zh-TW/workflows.md) 執行），請參閱 [`CLAUDE_CODE_BG_TASKS_REPORT_RUNNING`](https://code.claude.com/docs/zh-TW/env-vars#variables)。

```typescript theme={null}
type SDKSessionStateChangedMessage = {
  type: "system";
  subtype: "session_state_changed";
  state: "idle" | "running" | "requires_action";
  uuid: UUID;
  session_id: string;
};
```

### `SDKFilesPersistedEvent`

在檔案檢查點持久化至磁碟時發出。

```typescript theme={null}
type SDKFilesPersistedEvent = {
  type: "system";
  subtype: "files_persisted";
  files: { filename: string; file_id: string }[];
  failed: { filename: string; error: string }[];
  processed_at: string;
  uuid: UUID;
  session_id: string;
};
```

### `SDKRateLimitEvent`

當工作階段遇到速率限制時發出。

```typescript theme={null}
type SDKRateLimitEvent = {
  type: "rate_limit_event";
  rate_limit_info: {
    status: "allowed" | "allowed_warning" | "rejected";
    resetsAt?: number;
    utilization?: number;
    errorCode?: "credits_required";
    canUserPurchaseCredits?: boolean;
    hasChargeableSavedPaymentMethod?: boolean;
  };
  uuid: UUID;
  session_id: string;
};
```

當 `errorCode` 為 `"credits_required"` 時，拒絕來自其內含用量已耗盡的 claude.ai 訂閱，工作階段在使用者購買用量點數之前無法繼續。`canUserPurchaseCredits` 指示已驗證的使用者是否可以為帳戶購買點數，`hasChargeableSavedPaymentMethod` 指示是否已儲存付款方式。在不是需要點數之拒絕的速率限制事件上，這三個欄位都不存在。需要 Claude Code v2.1.181 或更新版本。

### `SDKLocalCommandOutputMessage`

Claude Code 不發出此訊息類型。當您傳送命令（例如 `/context` 或 `/usage`）作為提示詞時，其輸出作為 [`SDKAssistantMessage`](#sdkassistantmessage) 到達。

```typescript theme={null}
type SDKLocalCommandOutputMessage = {
  type: "system";
  subtype: "local_command_output";
  content: string;
  uuid: UUID;
  session_id: string;
};
```

### `SDKCommandsChangedMessage`

當可用命令集在工作階段中途變更時發出，例如當 Claude Code 在 agent 進入子目錄時發現 skill。`commands` 陣列是完整的更新清單，因此用此 payload 替換任何快取命令清單。在此訊息後呼叫 [`supportedCommands()`](#query-object) 會傳回相同的更新清單，因為該方法追蹤最新推送；這需要 Agent SDK v0.3.216 或更新版本。在較早的 SDK 版本中，`supportedCommands()` 傳回在初始化時擷取的快照，永遠不會反映工作階段中途的變更。

Claude Code 也在 MCP 伺服器的 [prompts](https://code.claude.com/docs/zh-TW/mcp.md#use-mcp-prompts-as-commands) 加入或離開清單時發出此訊息，例如當伺服器在工作階段啟動後完成連線時。這需要 Claude Code v2.1.281 或更新版本。

```typescript theme={null}
type SDKCommandsChangedMessage = {
  type: "system";
  subtype: "commands_changed";
  commands: SlashCommand[];
  uuid: UUID;
  session_id: string;
};
```

### `SDKPromptSuggestionMessage`

在啟用 [`promptSuggestions`](#options) 且 Claude Code 為該回合產生建議時，於回合後發出。包含預測的下一個使用者提示詞。對於未取得任何建議的回合，請參閱 [Claude Code 何時跳過建議](https://code.claude.com/docs/zh-TW/interactive-mode.md#when-claude-code-skips-suggestions)。

```typescript theme={null}
type SDKPromptSuggestionMessage = {
  type: "prompt_suggestion";
  suggestion: string;
  uuid: UUID;
  session_id: string;
};
```

### `SDKConversationResetMessage`

在工作階段的對話被替換而不結束工作階段時發出。在 `query()` 呼叫中，只有 `/clear` 及其別名產生此訊息。在 `new_conversation_id` 下掛載空逐字稿，並捨棄任何快取的工作階段標題。

```typescript theme={null}
type SDKConversationResetMessage = {
  type: "conversation_reset";
  new_conversation_id: UUID;
  uuid: UUID;
  session_id: string;
  trigger?: "clear" | "plan_mode_exit" | "fresh_session" | "onboarding";
  user_message_uuid?: string;
  timestamp?: string;
};
```

可選欄位描述重設：

* `trigger`：什麼捨棄了對話。在每個 `conversation_reset` 訊息上重設您的逐字稿，包括此欄位不存在或攜帶您不認識的值的訊息。
* `user_message_uuid`：攜帶 `/clear` 的使用者訊息的 `uuid`。使用它將重設與該訊息進行比對。
* `timestamp`：重設發生的時間，作為 UTC 中的 ISO 8601 字串。使用它進行顯示，而非排序訊息。

`trigger`、`user_message_uuid` 和 `timestamp` 欄位需要 Claude Code v2.1.281 或更新版本。

SDK 的已發佈類型在 Claude Code v2.1.203 及更新版本中宣告 `SDKConversationResetMessage`。在 v2.1.203 之前，`SDKMessage` 參考該類型而不宣告它，因此當 `skipLibCheck` 被停用時，在 `type === "conversation_reset"` 上縮小範圍無法通過類型檢查。

### `BUILTIN_TOOL_NAMES` 和 `LEGACY_TOOL_NAME_ALIASES`

使用這兩個常數檢查您的應用程式使用者輸入的工具名稱。兩者拼寫每個名稱的方式，都與您在權限規則、hook matcher 以及 `tools` 和 `disallowedTools` 選項中撰寫的方式相同。從 `@anthropic-ai/claude-agent-sdk` 或 `@anthropic-ai/claude-agent-sdk/core` 匯入它們。它們需要 Agent SDK v0.3.301 或更新版本，且為 alpha 版。

SDK 的類型宣告為 `BUILTIN_TOOL_NAMES` 提供唯讀 tuple 類型，為 `LEGACY_TOOL_NAME_ALIASES` 提供字串對字串的 record 類型：

```typescript theme={null}
const BUILTIN_TOOL_NAMES: readonly ["Agent", /* ...more names... */ "Write"];
const LEGACY_TOOL_NAME_ALIASES: Readonly<Record<string, string>>;
```

* **`BUILTIN_TOOL_NAMES`**：Claude Code 內建工具的名稱，依字母順序排列，例如 `Agent`、`Bash` 和 `Read`。不包括 MCP 工具名稱。由於該類型是字串常值的 tuple，`(typeof BUILTIN_TOOL_NAMES)[number]` 會提供這些名稱的聯合類型
* **`LEGACY_TOOL_NAME_ALIASES`**：權限規則、hook matcher 以及 `tools` 和 `disallowedTools` 選項仍接受的較早工具名稱。每個鍵是較早的名稱，其值是目前的名稱：例如，`Task` 對應至 `Agent`，`KillShell` 和 `KillBash` 對應至 `TaskStop`

您可以用兩種測試中的任一種確認名稱：`BUILTIN_TOOL_NAMES` 包含它，或 `Object.hasOwn(LEGACY_TOOL_NAME_ALIASES, name)` 傳回 `true`。兩項測試都未通過的名稱仍可能有效，因為 `BUILTIN_TOOL_NAMES` 未列入 MCP 工具和某些內建工具。如果您從 `BUILTIN_TOOL_NAMES` 建立拒絕清單，Claude 仍可使用該常數未列入的工具。若要拒絕所有工具，請改為設定 [`disallowedTools: ["*"]`](https://code.claude.com/docs/zh-TW/agent-sdk/permissions#allow-and-deny-rules)。

在 `BUILTIN_TOOL_NAMES` 中找到某個名稱，並不代表工作階段具有該工具：`TodoWrite` 雖然[預設為停用](https://code.claude.com/docs/zh-TW/tools-reference.md)，仍列於其中。若要查看工作階段具有哪些工具，請讀取其 [`SDKSystemMessage`](#sdksystemmessage) 的 `tools` 陣列。該陣列包含 MCP 工具，並將 Agent 工具列為 `Task`，因此在與 `BUILTIN_TOOL_NAMES` 比較之前，請先透過 `LEGACY_TOOL_NAME_ALIASES` 對應每個名稱。

### `AbortError`

中止操作的自訂錯誤類別。

```typescript theme={null}
class AbortError extends Error {}
```

`AbortError` 是 SDK 類型化 API 中唯一的錯誤類別。其他失敗，例如 Claude Code 程序退出或無法啟動，會以沒有 SDK 類別可比對的錯誤拒絕訊息反覆運算。[疑難排解](https://code.claude.com/docs/zh-TW/agent-sdk/troubleshooting.md) 按訊息列出這些錯誤，並提供每個錯誤的原因和修正方式。

## Sandbox 設定

### `SandboxSettings`

Sandbox 行為的設定。使用此設定以程式設計方式啟用命令 sandboxing 並設定網路限制。

```typescript theme={null}
type SandboxSettings = {
  enabled?: boolean;
  failIfUnavailable?: boolean;
  autoAllowBashIfSandboxed?: boolean;
  excludedCommands?: string[];
  allowUnsandboxedCommands?: boolean;
  network?: SandboxNetworkConfig;
  filesystem?: SandboxFilesystemConfig;
  ignoreViolations?: Record<string, string[]>;
  enableWeakerNestedSandbox?: boolean;
  allowNestedUserNamespaces?: boolean;
  ripgrep?: { command: string; args?: string[] };
};
```

| 屬性 | 類型 | 預設值 | 說明 |
| :- | :- | :- | :- |
| `enabled` | `boolean` | `false` | 為命令執行啟用 sandbox 模式 |
| `failIfUnavailable` | `boolean` | `true` | 如果 `enabled` 為 `true` 但 sandbox 無法啟動，則在啟動時停止。設定為 `false` 以回退到未 sandboxed 的執行，並在 stderr 上顯示警告 |
| `autoAllowBashIfSandboxed` | `boolean` | `true` | 當 sandbox 啟用時自動核准 Bash 命令 |
| `excludedCommands` | `string[]` | `[]` | 繞過 sandbox 限制的命令，例如 `['docker *']`。這些命令會自動以未 sandboxed 的方式執行，無需模型參與；[`sandbox.excludedCommands`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-excludedcommands) 涵蓋何時適用項目 |
| `allowUnsandboxedCommands` | `boolean` | `true` | 允許模型要求在 sandbox 外執行命令。當為 `true` 時，模型可以在工具輸入中設定 `dangerouslyDisableSandbox`，這會回退到[權限系統](#permissions-fallback-for-unsandboxed-commands) |
| `network` | [`SandboxNetworkConfig`](#sandboxnetworkconfig) | `undefined` | 網路特定的 sandbox 設定 |
| `filesystem` | [`SandboxFilesystemConfig`](#sandboxfilesystemconfig) | `undefined` | 檔案系統特定的 sandbox 設定，用於讀取/寫入限制 |
| `ignoreViolations` | `Record<string, string[]>` | `undefined` | 命令子字串或 `*`（適用於每個命令）對應到要忽略的違規文字子字串的對應，例如 `{ "*": ['/etc/hosts'] }`；請參閱 [`sandbox.ignoreViolations`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-ignoreviolations) |
| `enableWeakerNestedSandbox` | `boolean` | `false` | 啟用較弱的巢狀 sandbox 以相容性 |
| `allowNestedUserNamespaces` | `boolean` | `false` | 讓 Linux 和 WSL2 上的 sandboxed 命令建立使用者命名空間。在將其設定為 `true` 之前，請閱讀 [`sandbox.allowNestedUserNamespaces`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-allownestedusernamespaces)，其中說明了需要此設定的工具，以及您會因此關閉的安全邊界。需要 Claude Code v2.1.305 或更新版本 |
| `ripgrep` | `{ command: string; args?: string[] }` | `undefined` | Sandbox 環境的自訂 ripgrep 二進位設定 |

> [!NOTE]
>
> Sandbox 取決於平台支援，在 Linux 上，需要 `bubblewrap` 和 `socat` 等工具。當 `enabled` 為 `true` 且 sandbox 無法啟動時，`query()` 會報告一個 `result` 訊息，其中 `subtype: "error_during_execution"` 且原因在 `errors` 中。對於單一訊息 `query()` 呼叫，SDK 會在產生該錯誤結果後拋出，因此請將迴圈包裝在 try 區塊中以繼續執行。請參閱[處理結果](https://code.claude.com/docs/zh-TW/agent-sdk/agent-loop.md#handle-the-result)以了解錯誤合約。
>
> 若要改為以未 sandboxed 的方式執行，請設定 `failIfUnavailable: false`。

#### 使用範例

```typescript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

try {
  for await (const message of query({
    prompt: "Build and test my project",
    options: {
      sandbox: {
        enabled: true,
        autoAllowBashIfSandboxed: true,
        network: {
          allowLocalBinding: true
        }
      }
    }
  })) {
    if ("result" in message) console.log(message.result);
  }
} catch (error) {
  // A single-shot query() throws after yielding an error result,
  // such as when the sandbox can't start (failIfUnavailable defaults to true).
  console.log(`Session ended with an error: ${error}`);
}
```

> [!WARNING]
>
> **Unix socket 安全性：** `allowUnixSockets` 選項可以授予存取權限給可以到達 sandbox 外的系統服務。例如，允許 `/var/run/docker.sock` 實際上會透過 Docker API 授予完整的主機系統存取權限，繞過 sandbox 隔離。只允許嚴格必要的 Unix socket，並了解每個 socket 的安全含義。

### `SandboxNetworkConfig`

Sandbox 模式的網路特定設定。當父 [`SandboxSettings`](#sandboxsettings) 中的 `enabled` 為 `true` 時，這些設定適用於 sandboxed Bash 命令。它們不會限制 WebFetch 工具，該工具改為使用[權限規則](https://code.claude.com/docs/zh-TW/permissions.md#webfetch)。

```typescript theme={null}
type SandboxNetworkConfig = {
  allowedDomains?: string[];
  deniedDomains?: string[];
  strictAllowlist?: boolean;
  allowManagedDomainsOnly?: boolean;
  allowLocalBinding?: boolean;
  allowUnixSockets?: string[];
  allowAllUnixSockets?: boolean;
  httpProxyPort?: number;
  socksProxyPort?: number;
};
```

| 屬性 | 類型 | 預設值 | 說明 |
| :- | :- | :- | :- |
| `allowedDomains` | `string[]` | `[]` | Sandboxed 程序可以存取的網域名稱 |
| `deniedDomains` | `string[]` | `[]` | Sandboxed 程序無法存取的網域名稱。優先於 `allowedDomains` |
| `strictAllowlist` | `boolean` | `false` | 拒絕 sandboxed 命令存取[網路允許清單](https://code.claude.com/docs/zh-TW/sandboxing.md#network-isolation)外的主機，而不是提示。僅對 sandboxed 命令強制執行；WebFetch 等程序內工具不受其限制。僅從使用者、受管理或 CLI `--settings` 設定中接受；專案設定會被忽略。需要 Claude Code v2.1.219 或更新版本 |
| `allowManagedDomainsOnly` | `boolean` | `false` | 僅受管理設定。在[受管理設定](https://code.claude.com/docs/zh-TW/managed-settings.md)中設定時，只有 `allowedDomains` 項目和來自受管理設定的 `WebFetch(domain:...)` 允許規則會被接受，來自使用者、專案或本機設定的允許項目會被忽略。透過 SDK，透過 [`managedSettings`](#options) 選項傳遞它 |
| `allowLocalBinding` | `boolean` | `false` | 允許程序繫結到本機連接埠（例如用於開發伺服器） |
| `allowUnixSockets` | `string[]` | `[]` | 程序可以存取的 Unix socket 路徑（例如 Docker socket） |
| `allowAllUnixSockets` | `boolean` | `false` | 允許存取所有 Unix socket，並在 Linux 上允許存取 VM socket（`AF_VSOCK`） |
| `httpProxyPort` | `number` | `undefined` | 用於網路請求的 HTTP proxy 連接埠 |
| `socksProxyPort` | `number` | `undefined` | 用於網路請求的 SOCKS proxy 連接埠 |

> [!NOTE]
>
> 內建的 sandbox proxy 根據請求的主機名稱強制執行 `allowedDomains`，不會終止或檢查 TLS 流量，因此[網域前置](https://en.wikipedia.org/wiki/Domain_fronting)等技術可能會繞過它。請參閱 [Sandbox 安全限制](https://code.claude.com/docs/zh-TW/sandboxing.md#security-limitations)以了解詳細資訊，以及[安全部署](https://code.claude.com/docs/zh-TW/agent-sdk/secure-deployment.md#traffic-forwarding)以設定 TLS 終止 proxy。

### `SandboxFilesystemConfig`

Sandbox 模式的檔案系統特定設定。

```typescript theme={null}
type SandboxFilesystemConfig = {
  allowWrite?: string[];
  denyWrite?: string[];
  denyRead?: string[];
};
```

| 屬性 | 類型 | 預設值 | 說明 |
| :- | :- | :- | :- |
| `allowWrite` | `string[]` | `[]` | 允許寫入存取的檔案路徑模式 |
| `denyWrite` | `string[]` | `[]` | 拒絕寫入存取的檔案路徑模式。若要封鎖 sandboxed 命令寫入工作階段工作目錄中的檔案，請列出其絕對路徑。 |
| `denyRead` | `string[]` | `[]` | 拒絕讀取存取的檔案路徑模式 |

### 未 Sandboxed 命令的權限回退

當 `allowUnsandboxedCommands` 啟用時，模型可以透過在工具輸入中設定 `dangerouslyDisableSandbox: true` 來要求在 sandbox 外執行命令。這些請求會回退到現有的權限系統，這表示您的 `canUseTool` 處理程式會被呼叫，允許您實現自訂授權邏輯。

您的 `excludedCommands` 項目改為自動繞過 sandbox，無需模型參與；[`sandbox.excludedCommands`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-excludedcommands) 涵蓋何時適用項目。

在下面的範例中，`isCommandAuthorized` 代表您定義的授權檢查。

```typescript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  prompt: "Deploy my application",
  options: {
    sandbox: {
      enabled: true,
      allowUnsandboxedCommands: true // Model can request unsandboxed execution
    },
    permissionMode: "default",
    canUseTool: async (tool, input) => {
      // Check if the model is requesting to bypass the sandbox
      if (tool === "Bash" && input.dangerouslyDisableSandbox) {
        // The model is requesting to run this command outside the sandbox
        console.log(`Unsandboxed command requested: ${input.command}`);

        if (isCommandAuthorized(input.command)) {
          return { behavior: "allow" as const, updatedInput: input };
        }
        return {
          behavior: "deny" as const,
          message: "Command not authorized for unsandboxed execution"
        };
      }
      return { behavior: "allow" as const, updatedInput: input };
    }
  }
})) {
  if ("result" in message) console.log(message.result);
}
```

> [!WARNING]
>
> 使用 `dangerouslyDisableSandbox: true` 執行的命令具有完整的系統存取權限。確保您的 `canUseTool` 處理程式仔細驗證這些請求。
>
> 如果 `permissionMode` 設定為 `bypassPermissions` 且 `allowUnsandboxedCommands` 啟用，模型可以自主執行 sandbox 外的命令，無需核准提示，除了[任何模式都不會自動核准的動作](https://code.claude.com/docs/zh-TW/permission-modes.md#actions-no-mode-auto-approves)。此組合實際上允許模型以無聲方式逃脫 sandbox 隔離。

## 另請參閱

* [SDK 概觀](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) - 一般 SDK 概念
* [Python SDK 參考](https://code.claude.com/docs/zh-TW/agent-sdk/python.md) - Python SDK 文件
* [CLI 參考](https://code.claude.com/docs/zh-TW/cli-reference.md) - 命令列介面
* [常見工作流程](https://code.claude.com/docs/zh-TW/common-workflows.md) - 逐步指南

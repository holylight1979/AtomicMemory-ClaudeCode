<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/plugins/mods/api | lastmod: 2026-11-02 | section: Plugins / Mods -->
> 來源：https://code.claude.com/docs/zh-TW/plugins/mods/api（官方 zh-TW，lastmod 2026-11-02）｜分類：Plugins › Mods｜EN 摘要：Call the mods API from a Claude Code mod to add commands and tools, call a model, run work on a timer, message other sessions, and reach files and the network.

# 使用 mods API

> 從 Claude Code mod 呼叫 mods API 以新增命令和工具、呼叫模型、在計時器上執行工作、向其他工作階段傳送訊息，以及存取檔案和網路。

mods API 是 mod 呼叫以執行動作的方法集合：新增命令和工具、呼叫模型、在事件之間執行工作，以及存取檔案系統、程序和網路。每個 hook 都會將其作為第一個引數 `$` 接收，方法分組在命名空間中，例如 `$.ui` 和 `$.fs`。[事件](https://code.claude.com/docs/zh-TW/plugins/mods/events.md)決定何時執行 hook，mods API 是 hook 執行後呼叫的內容。

在開始之前，請先建立您的[第一個 mod](https://code.claude.com/docs/zh-TW/plugins/mods/create.md)。對於每個方法，請參閱 [mods API 方法](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#mods-api-methods)或閱讀[您的建置類型](https://code.claude.com/docs/zh-TW/plugins/mods/create.md#get-the-types-for-your-build)。

## 新增命令或工具

mod 可以新增供使用者執行的命令和供 Claude 呼叫的工具。在 [`session.start`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#session) hook 中註冊兩者。Claude Code 在第一個提示之前等待該 hook，因此您註冊的內容從第一個回合開始就可用。

### 新增命令

命令是供使用者使用的。註冊它，然後為其名稱處理 [`command.run`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#commands-and-configuration)。此範例新增了一個 `/standup` 命令，該命令採用可選的天數：

```javascript theme={null}
on('session.start', async ($, e, next) => {
  // 將 /standup 新增到命令列表，並附上使用者在該處看到的描述
  await $.command.register({ name: 'standup', description: 'Summarize what changed today', argumentHint: '[days]' })
  return next(e)
})

// 匹配器將 hook 限制為 /standup，因此其他命令不會到達它
on('command.run', { command: 'standup' }, async ($, e) => {
  // e.args 是在命令名稱後輸入的文字，或空字串
  return { text: 'Summary for the last ' + (e.args || '1') + ' day(s): ...' }
})
```

工作階段開始後，`/standup` 會與其描述一起出現在您輸入 `/` 時看到的列表中。`argumentHint` 在您輸入命令和空格後顯示在提示中，如 `/standup [days]`。當您執行 `/standup 3` 時，第二個 hook 會傳回 `Summary for the last 3 day(s): ...`，並且文字記錄會在外掛程式名稱後顯示該文字。hook 永遠不會呼叫 `next`，因為命令除了您的行為外沒有其他行為。

您傳回的 `text` 會列印在文字記錄中，Claude 會讀取它。若要不列印任何內容，如只開啟[窗格](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md#pick-where-to-draw)的命令，請傳回 `{}`。若要讓命令在 Claude 工作時執行，請將 `immediate: true` 新增到註冊中。

選擇沒有內建命令使用的名稱。在工作階段中輸入 `/` 以查看它們。`$.command.register` 會針對已佔用的名稱擲回，並顯示類似 `"/focus" refused: it is the built-in /focus` 的訊息。擲回的 hook 會被跳過，因此該 `session.start` hook 的其餘部分也不會執行。在該 hook 中最後註冊命令，或將呼叫包裝在 `try` 和 `catch` 中。

### 新增工具

工具是供 Claude 使用的。使用名稱、Claude 讀取的描述和其輸入的 JSON Schema 來註冊它。Claude 會在由 `mcp__`、您的外掛程式名稱、兩個底線和您註冊的名稱組成的較長名稱下看到它。您在 [`tool.call`](https://code.claude.com/docs/zh-TW/plugins/mods/events#guard-or-change-a-tool-call) hook 中處理其呼叫，該 hook 已篩選為該完整名稱。此範例來自名為 `my-mod` 的外掛程式，註冊 `ticket`，因此完整名稱是 `mcp__my-mod__ticket`。它為 Claude 提供了一個在問題追蹤器中查詢票證的工具：

```javascript theme={null}
on('session.start', async ($, e, next) => {
  await $.tool.register({
    name: 'ticket',
    // Claude 根據此描述決定何時呼叫工具
    description: 'Look up a ticket by its id and return its title and status',
    // Claude 必須傳送的引數：一個名為 id 的必需字串
    inputSchema: { type: 'object', properties: { id: { type: 'string' } }, required: ['id'] },
  })
  return next(e)
})

// 完整工具名稱是 mcp__、外掛程式名稱和已註冊名稱
on('tool.call', { tool: 'mcp__my-mod__ticket' }, async ($, e) => {
  // 工具的引數是 e 的欄位，因此 id 是 e.id
  const response = await $.http.fetch('https://tickets.example.com/api/' + encodeURIComponent(e.id))
  // 無論如何都傳回結果，以便 Claude 了解查詢何時失敗
  return { result: response.ok ? response.text : 'Lookup failed with status ' + response.status }
})
```

當您詢問票證時，Claude 可以使用其 id 呼叫 `mcp__my-mod__ticket`。第二個 hook 會擷取票證並傳回回應本文，Claude 會將其讀取為工具的結果。當伺服器以錯誤狀態回答時，Claude 會讀取 `Lookup failed with status` 和數字。

> [!TIP]
>
> 當 [MCP Tool Search](https://code.claude.com/docs/zh-TW/mcp.md#scale-with-mcp-tool-search) 延遲載入已註冊的工具時，Claude 會看到其名稱，但在搜尋該工具之前看不到其描述。若 Claude 應在每個回合都考慮此工具，請在註冊中新增 [`isDeferred: false`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#tools)，以[預先載入完整工具](https://code.claude.com/docs/zh-TW/mcp.md#exempt-a-server-from-deferral)。此欄位需要 Claude Code v2.1.293 或更新版本，較早的版本會忽略它。

## 呼叫模型

mod 可以向模型發送自己的請求，用於分類或摘要文字等小工作。`$.model.complete` 會單獨發送您的提示詞，而 `$.model.fork({ prompt })` 則會發送目前的對話，並將您的提示詞附加在最後。

下表比較每種請求所包含的內容：

| 請求中的內容 | `$.model.complete` | `$.model.fork` |
| :- | :- | :- |
| 模型 | 您傳入的 `model` | 工作階段的模型 |
| 系統提示詞 | 一段簡短的[歸屬區塊](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md#system-prompt-attribution-block)，若您有傳入 `system`，則接著是您的 `system` | 工作階段的系統提示詞 |
| 訊息 | 一則使用者訊息，即您的 `prompt` | 目前為止的對話，接著是作為使用者訊息的您的 `prompt` |
| CLAUDE.md 及其他專案脈絡 | 不包含 | 包含，與對話最後一次請求相同 |
| 工具 | 無 | Claude 的工具，但模型無法呼叫 |

fork 會重複對話的最後一次請求，因此在對話仍在快取中時，Claude API 會從[提示快取](https://code.claude.com/docs/zh-TW/prompt-caching.md)提供大部分內容。

這兩種呼叫都使用工作階段的憑證，因此會計費至使用者的方案、API 金鑰或雲端供應商。[您的建置類型](https://code.claude.com/docs/zh-TW/plugins/mods/create.md#get-the-types-for-your-build)記載了每個 `$.model` 方法。

### 發送單一提示詞

將 `model` 和 `prompt` 傳給 `$.model.complete`。`prompt` 會成為使用者訊息。若要給模型指令，例如角色或輸出格式，請同時傳入 `system`，它會成為系統提示詞。

此 hook 透過要求小型模型標記在其後輸入的文字來回答 `/triage` 命令（[註冊為命令](#add-a-command)）：

```javascript theme={null}
on('command.run', { command: 'triage' }, async ($, e) => {
  const r = await $.model.complete({
    model: 'haiku',
    // The system prompt sets the job, and the prompt carries the text to label
    system: 'Reply with one word: bug, feature, or question.',
    prompt: e.args,
    // One word needs few tokens, and the call gives up after 15 seconds
    maxTokens: 20,
    timeoutMs: 15000,
  })
  // r.text exists only when the model answered, so check r.isAnswered first
  const label = r.isAnswered ? r.text.trim() : 'unknown'
  return { text: 'Label: ' + label }
})
```

當您執行 `/triage the export button does nothing` 時，mod 會將該文字傳送給模型並列印其答案，例如 `Label: bug`。當模型沒有回答時，標籤為 `unknown`。

Claude API 失敗不會拒絕呼叫，因此請檢查 `r.isAnswered`，當其為 `false` 時請讀取 `r.reason`。呼叫會因為 Claude Code 不會傳送的請求而被拒絕，例如您的組織封鎖的模型。

[您的建置類型](https://code.claude.com/docs/zh-TW/plugins/mods/create.md#get-the-types-for-your-build)列出其他選項，例如 `effort`，而[限制](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#limits)提供 `maxTokens` 預設值。

### 使用提示快取

`$.model.complete` 支援 Claude API 的[提示快取](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)。API 會快取請求的開頭部分（稱為前綴），直到您設定的[快取斷點](https://platform.claude.com/docs/en/build-with-claude/prompt-caching#explicit-cache-breakpoints)為止。當每次呼叫都以相同的冗長靜態內容開頭時，例如指令或參考資料，請在該內容的結尾設定斷點。之後的呼叫便會從快取讀取該內容，而不必為其支付完整的輸入費用。

若要設定斷點，請將 `prompt` 以 `{ text }` 區塊陣列的形式傳入，而非字串，並在靜態內容的最後一個區塊加上 `cache: true`。Claude Code 會以 API 的 `cache_control` 欄位發送該區塊。`system` 也接受相同的陣列形式。若要決定使用哪一個，請參閱[在 `prompt` 與 `system` 之間選擇](#choose-between-prompt-and-system)。

> [!NOTE]
>
> 區塊陣列需要 Claude Code v2.1.292 或更新版本。較早的版本會拒絕 `prompt` 中的陣列，並顯示以 `takes { model, prompt } (host check)` 結尾的錯誤，且會將 `system` 中的陣列排除在請求之外。

此版本的 [`/triage` hook](#send-one-prompt) 會在要標記的文字之前發送一長串標記規則，並在規則之後設定斷點。`RULES` 是您自己的字串：

```javascript theme={null}
on('command.run', { command: 'triage' }, async ($, e) => {
  const r = await $.model.complete({
    model: 'haiku',
    prompt: [
      // Identical on every call, so it forms the cached prefix
      { text: RULES, cache: true },
      // Changes on every call, so it goes after the breakpoint
      { text: e.args },
    ],
  })
  return { text: 'Label: ' + (r.isAnswered ? r.text.trim() : 'unknown') }
})
```

TTL 與斷點數量有以下限制：

* **TTL**：快取項目在最後一次使用後會保留五分鐘。TTL 來自使用者的 Claude Code 設定，而非來自呼叫。若要設為一小時，請將 [`subagentPromptCacheTtl`](https://code.claude.com/docs/zh-TW/prompt-caching#choose-the-ttl-yourself) 設為 `1h`。
* **每個請求的斷點數**：API 接受[最多四個](https://platform.claude.com/docs/en/build-with-claude/prompt-caching#when-to-use-multiple-breakpoints)，再多一個則會在 `r.reason` 中以 `api-error` 傳回

#### 在 `prompt` 與 `system` 之間選擇

除非您確定您的請求會直接送往 Claude API，否則請將呼叫共用的靜態內容放在 `prompt` 的開頭：

* **直接送往 Claude API，使用 API 金鑰或 Claude 訂閱**：兩個欄位皆可
* **透過 [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md)、[Claude Platform on AWS](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md)、[Google Cloud's Agent Platform](https://code.claude.com/docs/zh-TW/google-vertex-ai.md)、[Microsoft Foundry](https://code.claude.com/docs/zh-TW/microsoft-foundry.md) 或 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)**：請使用 `prompt`。Claude Code 會以一段[歸屬區塊](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md#system-prompt-attribution-block)作為系統提示詞的開頭，其指紋來自使用者訊息的開頭。`api.anthropic.com` 端點會在快取前移除該區塊。其他端點則會將其作為提示詞的一部分接收，因此當 `prompt` 的開頭不同時，`system` 中的斷點可能無法命中。
* **在其他人執行的 mod 中**：請使用 `prompt`，因為您無法選擇他們的供應商

在前綴中，`system` 位於 `prompt` 之前，因此 `prompt` 中的斷點也會涵蓋 `system`，而使用不同 `system` 的呼叫將無法命中快取。

#### 檢查快取命中

`$.model.complete` 的結果包含一個 `usage` 物件，其中有 API 的[快取欄位](https://platform.claude.com/docs/en/build-with-claude/prompt-caching#tracking-cache-performance)。`usage.cache_creation_input_tokens` 計算呼叫寫入快取的 token 數，而 `usage.cache_read_input_tokens` 計算從快取讀取的 token 數。預期第一次呼叫會寫入，而在 TTL 內的後續呼叫會讀取。

如果每次呼叫都寫入而從未讀取，表示各次呼叫的前綴不同，或呼叫之間的間隔超過 TTL。關於前綴不同的情況，請參閱[在 `prompt` 與 `system` 之間選擇](#choose-between-prompt-and-system)。

如果在模型有回答的呼叫中，兩個欄位都維持為零，表示沒有任何內容被快取。請逐一檢查以下原因：

* **前綴太短**：API 不會快取短於模型[最小長度](https://platform.claude.com/docs/en/build-with-claude/prompt-caching#cache-limitations)的前綴，且不會傳回錯誤
* **提示快取已停用**：當 [`DISABLE_PROMPT_CACHING` 變數](https://code.claude.com/docs/zh-TW/prompt-caching#disable-prompt-caching)套用於該模型時，Claude Code 會移除斷點，並以未快取的方式發送文字
* **您的閘道移除了 `cache_control`**：閘道可能會[移除該欄位但仍傳回成功](https://code.claude.com/docs/zh-TW/prompt-caching.md#where-the-cache-lives)
* **另一個 mod 改寫了文字的開頭**：此時 Claude Code 會[在沒有斷點的情況下發送](#what-a-model-complete-hook-receives)

### `model.complete` hook 接收的內容

如果您 hook [`model.complete`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#mods-api-calls) 事件以檢查或變更其他 mod 的請求，請從以下欄位讀取文字：

* **`e.prompt`**：一律為字串。當呼叫者傳入陣列時，它是各區塊文字依序串接的結果。
* **`e.system`**：以相同方式建構的字串，若呼叫者未傳入 `system` 則不存在
* **`e.promptBlocks` 和 `e.systemBlocks`**：呼叫者的陣列，各自在呼叫者為該欄位傳入陣列時存在

Claude Code 會發送您的 hook 傳給 `next` 的字串，並使用您一併傳入的陣列來放置[快取斷點](#use-prompt-caching)。它會保留仍與字串開頭相符的前導區塊及其斷點，並在沒有斷點的情況下發送字串的其餘部分。例如，`next({ ...e, prompt: e.prompt + NOTE })` 會保留呼叫者的斷點，而變更 `prompt` 開頭的 hook 則會移除這些斷點。

## 在背景執行工作

超越一個事件的工作，例如每分鐘檢查一次，在您從 `session.start` 啟動的計時器上執行。hook 本身為一個事件執行，並對其自身的執行時間有[時間限制](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#limits)。在 `next` 或 mods API 呼叫上花費的時間不計算，除了 `$.clock.sleep`。`$.clock.every` 和 `$.clock.after` 取代 `setInterval` 和 `setTimeout`，延遲以毫秒為單位首先：`$.clock.after(5000, fn)` 在五秒後呼叫 `fn` 一次。每個都傳回一個具有 `cancel()` 方法的計時器，而 `await $.clock.now()` 給出以毫秒為單位的時間。

此 hook 每分鐘查詢一次提取請求的檢查，並在提示下方顯示結果。`summarize` 是您自己的函式，將命令的 JSON 輸出轉換為幾個單詞：

```javascript theme={null}
on('session.start', async ($, e, next) => {
  // 每 60,000 毫秒呼叫一次函式，從現在開始一分鐘後開始
  $.clock.every(60_000, async () => {
    const status = await $.process.run(['gh', 'pr', 'checks', '--json', 'state'])
    // 用最新摘要取代提示下方的行
    $.ui.status('checks: ' + summarize(status.stdout))
  })
  // 傳回而不等待計時器，以便工作階段立即開始
  return next(e)
})
```

工作階段照常開始。一分鐘後，提示下方會出現一行，其中包含 `⚠`、mod 的名稱，然後是 `checks:` 和您的摘要。之後每分鐘會被取代一次。計時器的回呼在任何事件之外執行，因此它在回合之間保持執行，不會啟動一個。如果回呼擲回，錯誤會進入[偵錯日誌](https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot.md#read-the-debug-log)，計時器在下一個間隔再次執行。

### 顯示某些內容而不啟動回合

背景工作可以向使用者顯示某些內容而不啟動回合。這些呼叫中的每一個都將文字放在不同的位置：

| 呼叫 | 使用者看到的內容 |
| :- | :- |
| `$.ui.status(text)` | 提示下方的一行，保持到您變更它為止。它以 `⚠` 和 mod 的名稱開頭，如 `⚠ my-mod: checks: 3 passing`。 |
| `$.ui.toast(text)` | 帶有 mod 名稱的快顯通知，幾秒後消失。在[全螢幕渲染](https://code.claude.com/docs/zh-TW/fullscreen.md)中，它是右上角的一個方框；在傳統渲染器中，它是提示下方右側的一行。 |
| `$.ui.log(text)` | 文字記錄中的一條暗線，Claude 不讀取。它以 `●` 和 mod 的名稱開頭，如 `● my-mod: build finished`。 |
| `$.ui.notify(text)` | 來自使用者終端機的通知，位於 Claude Code 之外，依照其 [`preferredNotifChannel`](https://code.claude.com/docs/zh-TW/settings-reference#preferrednotifchannel) 設定所指定的方式傳送。除非您傳入非空的 `{ title }`，否則 mod 的名稱即為其標題；若有傳入，則會依您提供的內容顯示。 |

`$.ui.notify` 是其中唯一會回應的呼叫。當使用者的通道將通知寫入其終端機時，它會解析為 `{ isSent: true, channel }`。`channel` 是傳送該通知的設定值，例如 `kitty` 或 `terminal_bell`。`terminal_bell` 通道會響鈴，既不顯示您的文字，也不顯示標題。

否則，呼叫會解析為 `{ isSent: false, reason }`：

| `reason` | 意義 |
| :- | :- |
| `disabled` | 使用者將 `preferredNotifChannel` 設為 `notifications_disabled` |
| `no-channel` | 設定為 `auto`，且使用者的終端機沒有 Claude Code 可傳送的通知 |
| `no-surface` | 工作階段沒有終端機，例如 `-p` 執行、Agent SDK、桌面應用程式、VS Code 擴充功能或雲端工作階段。在工作階段開始前（您的 mod 正在載入時）進行的呼叫，以及在 Claude Code 結束時進行的呼叫，也會得到此回應 |
| `refused` | 另一個 mod 在 `ui.notify` 上的 hook 代替 Claude Code 回應，且未傳送 |

當 `text` 不是字串、另一個 mod 在 `ui.notify` 上的 hook 傳回 `{ deny }`，或寫入終端機失敗時，呼叫會拒絕而非解析。

您的 mod 無法選擇通道，且 Claude Code 不會限制 mod 傳送通知的頻率。使用者的設定是唯一的開關。

當呼叫抵達執行中的工作階段時，使用者的 [`Notification` hook](https://code.claude.com/docs/zh-TW/hooks#notification) 會以類型 `plugin_notification` 執行。即使回應為 `disabled`，以及在沒有終端機、回應為 `no-surface` 的工作階段中，它們也會執行。在工作階段開始前或 Claude Code 結束時進行的呼叫，則不會執行任何 hook。您的 mod 從中呼叫 `$.ui.notify` 的 hook 會被排除在該次執行之外，因此會傳送通知的 `classic.Notification` hook 不會因其自身的通知而再次被呼叫。

終端機不會回報是否已顯示通知，因此 `isSent: true` 代表通知已傳送，而非使用者已看到。

此範例會在主要對話的回合未經中斷而結束時傳送通知，並在沒有帶文字的通知送出時改用快顯通知。它不會等待通知完成才將事件傳遞下去，因為使用者的 `Notification` hook 會先執行，且可能需要一段時間：

```javascript theme={null}
on('turn.complete', ($, e, next) => {
  const isMainTurn = e.agentId === undefined && !e.isAborted
  const fallBack = () => $.ui.toast('Turn finished')
  if (isMainTurn) {
    $.ui.notify('Turn finished').then(sent => {
      const hasText = sent.isSent && sent.channel !== 'terminal_bell'
      if (!hasText) fallBack()
    }, fallBack)
  }
  return next(e)
})
```

在 [VS Code 擴充功能](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md#draw-in-the-vs-code-extension)中，狀態列和快顯通知改為顯示在提示詞輸入框上方，而日誌行則顯示在對話中。

### 從背景工作啟動回合

當背景工作發現需要 Claude 注意的內容時，它可以透過使用 `$.prompt.submit({ text })` 提交提示來啟動回合。Claude 讀取文字後面有一句話，該句話將您的 mod 命名為寄件者。若要將其作為使用者自己的話語傳送，不帶該句話，請新增 `asUser: true`。呼叫會等待直到工作階段閒置，然後啟動新回合。它在該回合啟動時解析，因此不要在 Claude 工作時執行的處理程式中 `await` 它。

### 停止背景工作

模組重新載入後，計時器會停止。對於 hook 內的長時間執行工作，[`next.signal`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#the-hook-function) 是一個 `AbortSignal`，當您的 hook 正在處理的事件被放棄時中止，例如當使用者中斷時。請將其傳遞給任何長時間執行的內容。

### 使用者中斷回合後的呼叫與背景工作

結果或錯誤中的原因 `the session was stopped and nobody has sent input since` 表示使用者停止了正在執行的回合，例如使用 Esc 或 **Stop**。在該中斷之後，會在工作階段中啟動新工作的呼叫將被拒絕，直到使用者的下一次輸入為止，例如在提示處輸入的訊息。

除了 `$.prompt.submit` 和 `$.command.run` 之外，這種中斷後對呼叫與背景工作的處理方式需要 Claude Code v2.1.304 或更新版本。

#### 重試被拒絕或被捨棄的呼叫

從 [`turn.complete`](https://code.claude.com/docs/zh-TW/plugins/mods/events#follow-a-turn) hook 再次進行被拒絕或被捨棄的呼叫。呼叫會持續被拒絕直到使用者的下一次輸入，且不會有任何機制替您將其排入佇列或重複執行。

當呼叫的結果或錯誤包含下列其中一個字串時，請保留其引數以供稍後重試：

* **`the session was stopped and nobody has sent input since`**：呼叫被拒絕
* **`was removed from the queue before it ran`**：提示詞或命令在執行前離開佇列而被捨棄，例如當使用者停止回合時

在此範例中，請從您的背景工作呼叫 `submitPrompt`，以取代 [`$.prompt.submit`](#start-a-turn-from-a-background-job)。請將 `pendingText` 變數和 `submitPrompt` 函式放在 [`register`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#files) 上方，並將 `turn.complete` hook 放在其內部，因為[驗證](https://code.claude.com/docs/zh-TW/plugins/mods/create.md#check-what-claude-code-reads-from-your-mod)會拒絕傳遞給在 `register` 內宣告之函式的 `$`。當結果或錯誤帶有上述其中一個字串時，`submitPrompt` 會將文字保留在 `pendingText` 中，供 `turn.complete` hook 再次提交：

```javascript theme={null}
// 最後一個被拒絕或被捨棄的提示詞文字，或 null
let pendingText = null

async function submitPrompt($, text) {
  let reason
  try {
    const result = await $.prompt.submit({ text })
    reason = result?.drop ?? ''
  } catch (error) {
    reason = String(error?.message ?? error)
  }
  if (reason.includes('the session was stopped and nobody has sent input since') ||
      reason.includes('was removed from the queue before it ran')) {
    pendingText = text
  }
  // 其他任何結果或錯誤都不會重試
}

on('turn.complete', async ($, e, next) => {
  if (pendingText !== null) {
    const text = pendingText
    // 在重試前清空 pendingText，讓此 hook 的第二次執行
    // 不會提交相同的文字。
    pendingText = null
    // 不使用 await：否則 hook 會保持開啟直到新回合開始
    submitPrompt($, text)
  }
  return next(e)
})
```

在使用者的下一次輸入之前，`turn.complete` 可能會為被中斷的回合本身以及 subagent 的回合觸發，而在此時進行的呼叫會再次被拒絕。在這種情況下，`submitPrompt` 會保留文字，留待之後的 `turn.complete` 使用。

對於會拒絕（reject）的呼叫，例如 `$.command.run`，請捕捉錯誤，並以 `submitPrompt` 測試 `reason` 的方式測試其訊息。

#### 被拒絕的呼叫會傳回什麼

在結果中，`<reason>` 代表呼叫被拒絕的原因。在中斷之後，該原因為 `the session was stopped and nobody has sent input since`。關於其他原因，請參閱[在 `claude -p` 執行與 Agent SDK 工作階段中被拒絕的呼叫](#calls-refused-in-non-interactive-runs)。

| 部分被拒絕的呼叫 | 結果 |
| :- | :- |
| `$.prompt.submit` | 以 `{ drop: '<reason>' }` 解析，且不會將任何提示詞排入佇列 |
| `$.command.run` | 以訊息結尾為 `<reason>` 的錯誤拒絕 |
| [`$.agent.spawn`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#mods-api-methods) | 以 `{ deny: '<reason>' }` 解析，且不會啟動任何 subagent |
| 對已完成的 subagent 使用 `$.session.send` | 以 `{ isDelivered: false, reason: 'Agent "<id>" was not resumed: <reason>.' }` 解析，其中 `<id>` 是 subagent 的 id。仍在執行中的 subagent 會收到訊息。 |
| 對 [agent team](https://code.claude.com/docs/zh-TW/agent-teams.md) 隊員使用 `$.session.send` | 以 `{ isDelivered: false, reason: 'Teammate "<name>" was not messaged: <reason>.' }` 解析，其中 `<name>` 是隊員的名稱 |
| 以 [`$.tool.call`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#mods-api-methods) 呼叫帶有 `run_in_background: true` 的 Bash、Monitor 或 CronCreate | 以 `{ deny: '<tool> was not run: it starts background work, a schedule or a goal, and <reason>' }` 解析，其中 `<tool>` 是工具的名稱 |

當其中某個 `$.session.send` 或 `$.tool.call` 呼叫在互動式工作階段中因中斷而被拒絕時，使用者可能會看到 [`Stopped:` 快顯通知](https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot#stopped-type-a-message-to-continue)。

#### 您的 mod 在中斷前已啟動的工作

在使用者停止正在執行的回合之後，例如使用 Esc，您的 mod 已啟動的部分工作會被捨棄，部分則會等待使用者的下一次輸入。

| 工作 | 直到使用者下一次輸入前會發生什麼 | 該怎麼做 |
| :- | :- | :- |
| 來自 `$.prompt.submit` 且仍在佇列中的提示詞 | 被捨棄。呼叫以 `{ drop: 'the prompt was removed from the queue before it ran' }` 解析。 | 依照[重試被拒絕或被捨棄的呼叫](#retry-a-refused-or-dropped-call)所示再次提交 |
| 來自 `$.command.run` 且仍在佇列中的命令 | 被捨棄。呼叫以訊息包含 `the command was removed from the queue before it ran` 的錯誤拒絕。 | 依照[重試被拒絕或被捨棄的呼叫](#retry-a-refused-or-dropped-call)所示再次執行 |
| 使用 CronCreate 等工具排程、並在使用者下一次輸入前到期的一次性工作 | 當時不會啟動回合，並在該輸入之後執行 | 無需任何動作 |
| 使用 CronCreate 等工具排程、並在使用者下一次輸入前到期的週期性工作 | 當時不會啟動回合。該工作會失去那一次執行，並保留其排程。 | 無需任何動作 |
| 來自您的 mod 所啟動之監視器的事件 | 監視器會持續執行。監視器在使用者下一次輸入前產生的事件會被捨棄，但監視器結束的通知除外，該通知會在該輸入之後送達。 | 無法採取任何動作 |
| 您的 mod 產生、之後以 `$.session.send` 恢復，並在使用者下一次輸入前完成的 subagent | 其完成通知會等待，並在該輸入之後進入對話 | 無需任何動作 |
| 來自 `$.tool.call`、在使用者停止回合時已在執行，並在使用者下一次輸入前達到其逾時的前景 Bash 或 PowerShell 命令 | 在逾時時被停止，而非[移至背景](https://code.claude.com/docs/zh-TW/tools-reference.md#foreground-commands-that-move-to-the-background)。呼叫以設定了 `isError` 的結果解析，且輸出包含這一行 `Ended instead of moving to the background: plugins' input is held, by a Stop or by the host's limits.` | 在使用者下一次輸入之後，依照[重試被拒絕或被捨棄的呼叫](#retry-a-refused-or-dropped-call)所示再次執行 |

當排程工作到期或監視器在使用者下一次輸入前產生事件時，使用者可能會看到 [`Stopped:` 快顯通知](https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot#stopped-type-a-message-to-continue)。

### 在 `claude -p` 執行與 Agent SDK 工作階段中被拒絕的呼叫

在 `claude -p` 執行或 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 工作階段中，諸如 `{ drop: 'the run reached its --max-turns limit' }` 的結果表示該次執行拒絕了您的 mod 的呼叫。

被拒絕的 `$.prompt.submit` 會以 `{ drop: '<reason>' }` 解析。其他被拒絕的呼叫，例如 `$.command.run` 和 `$.agent.spawn`，會產生[被拒絕的呼叫會傳回什麼](#what-refused-calls-return)中所示的結果，並以該原因取代 `<reason>`。請在下方找到您的 `<reason>`，了解該如何處理：

* **`the run reached its --max-turns limit`**：來自您的 mod 的提示詞以及其產生之 subagent 的回合，都會計入 [`--max-turns`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 或 Agent SDK 的[回合限制](https://code.claude.com/docs/zh-TW/agent-sdk/configuration.md#limit-turns-and-spend)。若需要更多回合，請以更高的限制啟動該次執行。若無法這麼做，請讓您的 mod 停止進行被拒絕的呼叫。若該次執行接收到來自使用者或 SDK 應用程式的另一個提示詞，回合計數會重設，且該次執行會再次接受呼叫。
* **`the run is past its --max-budget-usd limit`**：請以更高的 `--max-budget-usd` 啟動該次執行，或提高 Agent SDK 的[支出限制](https://code.claude.com/docs/zh-TW/agent-sdk/configuration.md#limit-turns-and-spend)。若無法這麼做，請讓您的 mod 停止進行被拒絕的呼叫。此限制適用於該次執行至今的總成本。當該次執行接收另一個提示詞時，總成本會持續累加，因此重試會傳回相同的原因。
* **`the host has ended its input`**：例如，SDK 應用程式結束了其[串流輸入](https://code.claude.com/docs/zh-TW/agent-sdk/streaming-vs-single-mode.md)，或以 [`--input-format stream-json`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 啟動的執行中 stdin 已關閉。該次執行正在結束，不再接受任何輸入，因此重試會傳回相同的原因。請讓您的 mod 停止進行被拒絕的呼叫。若該次執行由您自己啟動，下次請保持該輸入開啟，直到您的 mod 不再需要進行任何呼叫為止。
* **`the session was stopped and nobody has sent input since`**：該次執行已被[中斷](#calls-and-background-work-after-the-user-interrupts-a-turn)，例如透過 Agent SDK 的 [`interrupt()`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#query-object)。若要在使用者或 SDK 應用程式的下一則訊息之後再次進行呼叫，請依照[重試被拒絕或被捨棄的呼叫](#retry-a-refused-or-dropped-call)操作。

### 載入您的 mod 的 `claude -p` 執行永遠不會結束

若您的 mod 在每個回合結束時都提交提示詞，每個提示詞都會啟動另一個回合。若沒有 [`--max-turns`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 或 `--max-budget-usd`，載入該 mod 的 `claude -p` 執行會持續進行，直到您自行停止為止。

若要讓該次執行自行結束，請在您的 shell 中於命令加上其中任一旗標。若由其他人啟動該次執行，請讓您的 mod 在工作完成後停止提交提示詞。此命令加上了 `--max-turns`：

```bash theme={null}
claude -p "find the TODOs" --max-turns 5
```

一旦該次執行達到該限制，mod 的下一個提示詞會被[拒絕](#calls-refused-in-non-interactive-runs)而不會啟動回合，且該次執行會結束。

若該次執行仍超過限制，請在您的 shell 中執行 `claude --version`，若您的版本早於 v2.1.304，請[更新 Claude Code](https://code.claude.com/docs/zh-TW/setup.md#update-claude-code)。從 v2.1.299 起，mod 的提示詞會在達到限制時被拒絕。若您的 mod 會產生 subagent，從 v2.1.304 起，它們的回合會計入 `--max-turns`。

## 在工作階段之間傳送和接收訊息

mod 可以向您的另一個工作階段、此工作階段的某個 subagent，或其 [agent team](https://code.claude.com/docs/zh-TW/agent-teams.md) 中的隊員傳送純文字訊息。它也可以觀察到達和離開的訊息。

若要傳送訊息，請呼叫 `$.session.send({ to, text })`，它會進行與 SendMessage 工具相同的傳遞。依據接收訊息的對象設定 `to`：

* **您的另一個工作階段**：`{ sessionId }`
* **subagent 或隊員**：`{ agentId }`，使用來自 `$.agent.list()` 的 id
* **您所收到訊息的寄件者**：該訊息來源的字串位址

呼叫在訊息排入佇列後解析，返回 `{ isDelivered: true }`。當沒有任何內容被傳遞時，它會以 `{ isDelivered: false, reason }` 解析，`reason` 說明原因。

此 hook 透過詢問您在其後輸入的 id 的工作階段的狀態，來回答 `/ping` 命令（[註冊為命令](#add-a-command)）：

```javascript theme={null}
on('command.run', { command: 'ping' }, async ($, e) => {
  // e.args is the session id typed after /ping
  const sent = await $.session.send({ to: { sessionId: e.args }, text: 'Status? One line.' })
  // The call resolves either way, so check isDelivered to learn what happened
  if (!sent.isDelivered) $.ui.toast('Not delivered: ' + sent.reason)
  // An empty result prints nothing in this session's transcript
  return {}
})
```

當訊息排隊時，您的工作階段中不會出現任何內容，另一個工作階段的 Claude 會讀取 `Status? One line.`。當沒有任何內容被傳遞時，toast 通知會顯示原因。

`session.receive` 和 `session.send` 讓 mod 觀察訊息。從兩者都返回 `next(e)` 以不變地傳遞每個訊息：

| 事件 | 何時觸發 | 有用的欄位 |
| :- | :- | :- |
| `session.receive` | 訊息到達此工作階段，在 Claude 讀取之前 | `e.text` 和 `e.origin.kind`，例如另一個工作階段或代理的 `peer` 或 `peer-send-message`、`task-notification` 或 `scheduled-trigger`。返回 `{ consumed: reason }` 以防止 Claude 讀取。 |
| `session.send` | 訊息即將離開，來自 SendMessage 工具或 mod | `e.to`、`e.text` 和 `e.origin.kind`，即 `model` 或 `plugin` |

設定為[拒絕入站訊息](https://code.claude.com/docs/zh-TW/cross-session-messaging.md#control-inbound-messages)的工作階段在 `session.receive` 觸發之前拒絕訊息，因此 hook 永遠不會看到它。為您的批准而保留的訊息首先到達 hook，因此 mod 可以讀取您尚未批准的訊息。hook 的 `next(e)` 在訊息未被傳遞時拒絕。

接收訊息上的寄件者名稱是寄件者寫的任何內容，因此不要基於它做出決定。

## 存取檔案、程序和網路

mod 透過 mods API 存取檔案系統、程序和網路，具有與執行 Claude Code 的使用者相同的權限。hook 模組本身沒有 Node.js API、沒有計時器全域變數（例如 `setTimeout`），也沒有自己的網路或檔案存取。標準 JavaScript 和網路 API（例如 `URL`、`TextEncoder`、`AbortController` 和 `crypto.subtle`）可用。下面的每個命名空間涵蓋一種存取：

| 命名空間 | 它的作用 |
| :- | :- |
| `$.fs` | `read(path)`、`write(path, text)`、`exists(path)`、`stat(path)` 和 `list(path)` 在檔案和目錄上工作 |
| `$.process` | `run(['git', 'status'])` 啟動命令並在其退出時解析。`spawn` 串流長時間執行命令的輸出。 |
| `$.http` | `fetch(url, init)` 透過 `http` 或 `https`。它在讀取本文後解析為 `{ status, ok, headers, text }`。 |
| `$.store` | 您外掛自己的 JSON 鍵值存放區，在工作階段之間保留 |
| `$.env` | `get` 和 `set` 環境變數。將名稱寫為文字字串。 |
| `$.settings` | `read()` 解析為所有設定，合併為一個物件。搭配 `{ source }` 或 `{ key }` 時，它改為解析為[單一來源的設定或單一設定鍵的值](#read-one-source-or-one-key)。 |
| `$.session` | `messages()` 將逐字稿傳回為 `{ role, text, toolUses }` 的列表。也是工作目錄、模型等。[`usage()`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#mods-api-methods) 傳回上下文視窗使用和計畫限制。 |
| `$.mcp` | `call` 連接的 MCP 伺服器上的工具 |

檔案、程序和請求有幾個自己的規則：

* **路徑**：相對路徑會相對於工作階段的工作目錄解析，或相對於該 hook 正在處理其事件的 subagent 的工作目錄解析
* **`$.fs.list`**：將一個目錄的項目傳回為 `{ name, kind, size, isLink }`，不會遞迴
* **`$.process.run`**：採用引數列表，不使用 shell。無論退出碼如何，它都解析為 `{ exitCode, stdout, stderr }`。如果程式無法啟動或在逾時時仍在執行，它會拒絕，預設為 30 秒，因此將其包裝在 `try` 和 `catch` 中。
* **`$.http.fetch`**：最多追蹤五次重新導向。當重新導向至不同的來源時，它只會保留您設定的 `accept`、`accept-language`、`content-type` 和 `user-agent` 請求標頭，並捨棄其餘標頭，因此依賴其他標頭（例如 `Authorization`）的請求可能會在該重新導向之後失敗。[限制](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#limits)列出了它的逾時和本文大小。

這些呼叫中的每一個本身都是一個事件，以其命名空間和方法命名，不帶 `$.`，例如 `$.fs.read` 的 `fs.read`。鏈中[較早的](https://code.claude.com/docs/zh-TW/plugins/mods/events.md#the-order-mods-run-in) mod 可以觀察、重寫或拒絕您的呼叫，這是組織限制 mod 到達的方式。

mod 可以在命令已產生輸出或已退出之後拒絕您的 `$.process.spawn` 呼叫，而命令已執行的任何動作都不會被復原。此時該呼叫會以一則訊息拒絕，訊息結尾為下列其中一個字串以及拒絕的 mod 所給的原因：

* **`$.process.spawn started, and a plugin withheld its result:`**：拒絕的 mod 尚未將命令的輸出讀取到結尾。如果命令仍在執行，Claude Code 會將其停止。
* **`$.process.spawn ran, and a plugin withheld its result:`**：拒絕的 mod 已將命令的輸出讀取到結尾，因此命令已經退出

### 讀取所有設定、單一來源或單一設定鍵

`$.settings.read()` 解析為一個物件，其中包含所有使用中來源的設定，並依[優先順序](https://code.claude.com/docs/zh-TW/settings.md#settings-precedence)合併。傳入 `{ source }` 可改為讀取單一來源，傳入 `{ key }` 可讀取單一設定鍵，也可兩者都傳入：

| 呼叫 | 解析為 |
| :- | :- |
| `$.settings.read()` | 合併後的設定，作為一個物件。其頂層鍵與 `settings.json` 檔案的頂層鍵相同，例如 `permissions` 和 `hooks`。 |
| `$.settings.read({ source: 'policy' })` | 該單一來源的設定，作為一個物件；當該來源不包含任何設定時則為 `{}` |
| `$.settings.read({ key: 'spinnerTipsEnabled' })` | 該設定鍵在合併後設定中的值；當該設定鍵未設定時則為 `undefined` |
| `$.settings.read({ key: 'spinnerTipsEnabled', source: 'user' })` | 該設定鍵在該單一來源中的值；當該來源未設定它時則為 `undefined` |

對於 `source`，請傳入要讀取的單一設定來源名稱：

* **`user`**：`~/.claude/settings.json`
* **`project`**：`.claude/settings.json`
* **`local`**：`.claude/settings.local.json`
* **`flag`**：您透過 `--settings` 傳入的內容，以及 SDK 的內嵌設定
* **`policy`**：[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)

對於 `key`，請傳入單一頂層鍵的確切名稱，而不是指向巢狀物件的點分路徑。`key` 引數需要 Claude Code v2.1.304 或更新版本。

## 後續步驟

* [對事件做出反應](https://code.claude.com/docs/zh-TW/plugins/mods/events.md)：hook 工具呼叫、提示和回合
* [在介面中繪製](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md)：在窗格或提示上方顯示您的 mod 收集的內容
* [測試 mod](https://code.claude.com/docs/zh-TW/plugins/mods/test.md)：在測試中存根這些呼叫中的任何一個
* [Mods 參考](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md)：事件、mods API 方法和限制

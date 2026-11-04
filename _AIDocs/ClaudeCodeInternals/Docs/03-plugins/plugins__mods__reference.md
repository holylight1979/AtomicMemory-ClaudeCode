<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/plugins/mods/reference | lastmod: 2026-11-04 | section: Plugins / Mods -->
> 來源：https://code.claude.com/docs/zh-TW/plugins/mods/reference（官方 zh-TW，lastmod 2026-11-04）｜分類：Plugins › Mods｜EN 摘要：Complete reference for Claude Code mods: hooks module layout, events, mods API methods, render sites, elements by surface, limits, and settings.

# Mods 參考資料

> Claude Code mod 的完整參考資料：hook 模組配置、事件、mods API 方法、轉譯位置、各使用介面的元素、限制與設定。

查詢 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md) 可處理的任何事件、可呼叫的任何 mods API 方法，或可繪製的任何轉譯位置。各項目涵蓋 v2.1.290 版起的 Claude Code CLI 與 Desktop 應用程式，以及 v2.1.299 版起的 VS Code 擴充功能。每個項目皆提供名稱與一行說明，若有對應的指南章節，亦會連結至該處。

> [!NOTE]
>
> 完整的參考資料是 Claude Code 的 [mod TypeScript 宣告](https://github.com/anthropics/claude-code/blob/main/mods/types/claude-code.d.ts)，其中以範例描述每個事件、方法與元素。GitHub 上的副本可能比您安裝的 Claude Code 版本更舊。兩者不一致時，請以 [Claude Code 為您的版本寫入的副本](https://code.claude.com/docs/zh-TW/plugins/mods/create.md#get-the-types-for-your-build)為準。

## 檔案

mod 是包含下列檔案的外掛目錄：

| 檔案 | 必要 | 內容 |
| :- | :- | :- |
| `.claude-plugin/plugin.json` | 是 | 外掛[資訊清單](https://code.claude.com/docs/zh-TW/plugins/manifest-reference.md)。mod 不會新增任何必要欄位。 |
| `hooks/hooks.json` | 是 | `modules`：一個陣列，內含一個相對於此檔案、指向 hook 模組的路徑，例如 `"modules": ["./register.js"]`。也可以在 `hooks` 下存放[設定 hook](https://code.claude.com/docs/zh-TW/hooks.md)。 |
| hook 模組，例如 [`hooks/register.js`](https://code.claude.com/docs/zh-TW/plugins/mods/create#write-a-mod-yourself) | 是 | mod 的進入點。匯出 `register(on, options)`。檔名為 `.js`、`.mjs`、`.cjs`、`.jsx`、`.ts`、`.mts`、`.cts` 或 `.tsx`。為 ES 模組。 |
| [`types/index.d.ts`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#declare-the-values)，除非資訊清單中的 `types` 指定了其他路徑 | 當 mod 使用 `$.state` 或在 mods API 中新增命名空間時 | 宣告 `PluginState` 值以及 mod 新增的任何命名空間。若要在資訊清單中省略 `types`，需要 v2.1.299 或更新版本。 |
| 檔名以 `.test.ts` 或 `.test.tsx` 結尾的檔案 | 否 | [`claude plugin test`](https://code.claude.com/docs/zh-TW/plugins/mods/test#write-a-test) 執行的測試 |

`register` 會接收 `on` 與 `options`。`options` 存放資訊清單所宣告之 [`userConfig`](https://code.claude.com/docs/zh-TW/plugins/components#user-configuration) 欄位的值，並已填入預設值。

## hook 函式

mod 透過在 `register` 內呼叫 `on` 來註冊其每個 hook（即事件處理常式）。`on` 接受事件名稱、選用的 [matcher](https://code.claude.com/docs/zh-TW/plugins/mods/events.md#filter-which-events-a-hook-handles)（針對事件欄位的篩選條件），以及 hook 本身，例如 `on('tool.call', { tool: 'Bash' }, async ($, e, next) => next(e))`。`on` 會回傳一個只有一個方法 `.catch(handler)` 的註冊物件，用來設定 hook 的[錯誤處理常式](https://code.claude.com/docs/zh-TW/plugins/mods/events.md#handle-a-hook-that-fails)。

| 引數 | 說明 |
| :- | :- |
| [`$`](https://code.claude.com/docs/zh-TW/plugins/mods/events#how-a-hook-handles-an-event) | mods API：[mods API 方法](#mods-api-methods)中的每個方法。每次呼叫請完整寫出，先命名空間再方法，例如 `$.fs.read('notes.md')`。 |
| [`e`](https://code.claude.com/docs/zh-TW/plugins/mods/events#how-a-hook-handles-an-event) | 事件的輸入，為深度凍結的純資料。若要變更，請將副本傳給 `next`。 |
| [`next(e)`](https://code.claude.com/docs/zh-TW/plugins/mods/events#how-a-hook-handles-an-event) | 下一個處理常式，如同中介軟體。會執行此 hook 之後的 hook，接著執行 Claude Code 的行為。解析為事件的結果。 |
| [`next.signal`](https://code.claude.com/docs/zh-TW/plugins/mods/api#stop-background-work) | 一個 `AbortSignal`，在事件被放棄時中止 |
| `next.origin` | 觸發事件者的 `{ plugin, tier }`。Claude Code 本身為 `{ plugin: 'engine', tier: 'core' }`。mod 的 `tier` 是它在 [mod 執行順序](https://code.claude.com/docs/zh-TW/plugins/mods/events.md#the-order-mods-run-in)中的優先群組：`prepend`、`user`、`append` 或 `builtin`。 |
| `next.budget` | hook 的時間限制（毫秒）：`next.budget.ms` 為整體限制，`next.budget.remainingMs` 為目前剩餘時間 |
| `next.to(e, tier)` | 跳至較後面的層級，即 `append`、`builtin` 或 `core`。`next.to(e, 'append')` 會略過使用者安裝的 mod。只有 `prependPlugins` 或 `appendPlugins` 中的 mod 可以呼叫它。 |
| `next.error` | 僅限 `.catch` 處理常式中。當 hook 失敗時，`kind` 為 `throw` 或 `timeout`，`message` 為錯誤文字。當 hook 因事件來自該 hook 或您的 mod 在其 hook 之外的程式碼所發出的 mods API 呼叫內部而被略過時，`kind` 為 `re-entry`。`re-entry` 需要 Claude Code v2.1.292 或更新版本。 |
| `next.error.cause` | 僅在 `kind` 為 `re-entry` 時設定。若 `tool.call` 或 [`PreToolUse`](https://code.claude.com/docs/zh-TW/hooks#pretooluse) hook 變更了事件來源的 mods API 呼叫，或 `agent.spawn` hook 變更了由該呼叫啟動的 agent，則為 `rewritten`。若觸發該事件的是另一個 mod 新增至 mods API 的方法，則為 `lent`，除非同時符合 `rewritten` 的情況。`lent` 需要 Claude Code v2.1.292 或更新版本，`rewritten` 需要 v2.1.300 或更新版本。 |
| `next.called` | 僅限 `.catch` 處理常式中。當 hook 曾呼叫 `next` 時為 `true`。 |

## 事件

事件依其相關內容分組，並列出每個事件的觸發時機，以及其上的 hook 可回傳的內容。`turn.step` 與 `process.spawn` 上的 hook 是非同步產生器，其他 hook 則是非同步函式。

每個表格的最後一欄使用簡寫。`next(e)` 會將事件原封不動地傳遞下去。`next({ ...e, text })` 會傳遞變更了指定欄位的副本，例如 `next({ ...e, text: e.text.trim() })`。物件會在不呼叫 `next` 的情況下回應事件，而 `reason` 之類的詞代表您撰寫的字串，例如 `{ deny: 'Use the file tools.' }`。

### 工具

工具事件在 Claude 發出的每個工具呼叫前後觸發，從 Claude 讀取的說明，到是否執行該呼叫的決定：

| 事件 | 觸發時機 | hook 可回傳 |
| :- | :- | :- |
| [`tool.call`](https://code.claude.com/docs/zh-TW/plugins/mods/events#guard-or-change-a-tool-call) | 工具即將執行時 | `next(e)`、`{ deny: reason }` 或 `{ result }` |
| [`tool.check`](https://code.claude.com/docs/zh-TW/plugins/mods/events#where-settings-hooks-run-in-the-order) | Claude Code 在 `tool.call` 與 `PreToolUse` hook 之後，決定工具呼叫是否可以執行時。`next(e)` 會解析為規則、權限模式與這些 hook 所得出的決定。 | `next(e)` 或 `{ decision }`，其中 `decision` 設為 `allow`、`ask` 或 `deny`，並可選擇附上 `reason` |
| `tool.describe` | 每個工具一次，在其說明首次傳送給 Claude 時。當 Claude 透過[工具搜尋](https://code.claude.com/docs/zh-TW/mcp.md#scale-with-mcp-tool-search)載入 MCP 工具時會再觸發一次，此時 `e.description` 設為 Claude 針對已載入工具所讀取的文字。 | `{ description }`，可選擇將 `isDeferred` 設為 `true` 以將該工具置於工具搜尋之後，或設為 `false` 以預先載入 |

#### `tool.check` 上的 agent 與組織欄位

在 `tool.check` hook 中，讀取這些欄位即可區分 subagent 的呼叫與主對話的呼叫，並查看您的組織是否要求連接器工具須經核准：

* **`e.agentId`**：由 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 或[同程序隊員](https://code.claude.com/docs/zh-TW/agent-teams.md#choose-a-display-mode)發出呼叫時設定，由主對話發出時則不存在
* **`e.ceiling`**：對於您的組織設為 `ask` 的連接器工具，其值為 `ask`，適用於[該設定會傳達至 Claude Code 的工作階段](https://code.claude.com/docs/zh-TW/mcp.md#organization-controls-on-connector-tools)

在 `tool.check` 上，`e.agentId` 與 `e.ceiling` 需要 Claude Code v2.1.290 或更新版本。

#### `tool.check` 上的 `e.isReadOnly` 欄位

在 `tool.check` hook 中，當工具回報此呼叫為唯讀時，`e.isReadOnly` 為 `true`。否則該欄位不存在，而非 `false`。此值是工具自身的回報，因此在僅依據此欄位核准呼叫之前，請先閱讀[檢查工具呼叫是否為唯讀](https://code.claude.com/docs/zh-TW/plugins/mods/events.md#check-whether-a-tool-call-is-read-only)。

在 `tool.check` 上，`e.isReadOnly` 需要 Claude Code v2.1.304 或更新版本。

### 提示詞與 Claude 讀取的內容

提示詞事件涵蓋使用者輸入的文字，以及 Claude Code 自行傳送給 Claude 的文字，例如系統提示詞與提醒：

| 事件 | 觸發時機 | hook 可回傳 |
| :- | :- | :- |
| [`prompt.submit`](https://code.claude.com/docs/zh-TW/plugins/mods/events#rewrite-or-add-to-a-prompt) | 提交提示詞時 | `next({ ...e, text })`、`next({ ...e, context })` 或 `{ drop: reason }` |
| `prompt.fill`、`prompt.suggest` | 文字即將以草稿或淡色建議的形式放入提示詞輸入框時 | 變更了文字的 `next(e)` |
| `prompt.edit` | 使用者編輯提示詞輸入框時 | `next(e)` |
| `prompt.autocomplete` | 使用者在提示詞輸入框中輸入，且有一個字詞在游標處結束時。`e.token` 即為該字詞。Claude Code 不會等待此 hook：其自身的自動完成列會先顯示。 | `{ suggestions }`，即顯示在 Claude Code 自身列下方的 `{ text, label, description }` 列清單。選擇某一列會以其 `text` 覆寫該字詞。 |
| `prompt.compose` | Claude Code 轉譯系統提示詞時 | `{ sections }`，即依傳送順序排列的 `{ id, text, scope }` 清單 |
| [`prompt.section`](https://code.claude.com/docs/zh-TW/plugins/mods/events#rewrite-or-add-to-a-prompt) | 系統提示詞的每個具名區段各一次。`e.name` 是該區段在 `prompt.compose` 中的 `id`。 | `{ text }`，或以 `{ text: null }` 省略該區段 |
| [`prompt.context`](https://code.claude.com/docs/zh-TW/plugins/mods/events#rewrite-or-add-to-a-prompt) | 每個對話一次，針對隨第一則訊息傳送的上下文 | `{ blocks }` |
| `prompt.attachment` | Claude Code 為 Claude 新增一則自己的訊息時，例如提醒。`e.type` 指出種類，對於型別有宣告的種類，`e.detail` 存放撰寫該文字所依據的事實。 | `{ text }`，或以 `{ text: null }` 省略 |
| `prompt.mention` | Claude Code 即將讀取提示詞以 @ 提及的檔案時。需要 Claude Code v2.1.290 或更新版本。 | 以 `next({ ...e, path })` 改為讀取其他檔案，或 `{ deny: reason }` |
| [`skill.prompt`](https://code.claude.com/docs/zh-TW/plugins/mods/events#rewrite-or-add-to-a-prompt) | skill 的文字為 Claude 展開時 | `{ text }` |
| `attribution.text` | Claude Code 撰寫提交或 pull request 的歸屬文字時 | `{ text }` |

#### `skill.prompt` 上的來源與 frontmatter 欄位

在 `skill.prompt` hook 中，除了 `e.skill` 中的 skill 名稱與 `e.text` 中 Claude 讀取的文字之外，您還可以讀取這些欄位：

| 欄位 | 型別 | 內容 |
| :- | :- | :- |
| `e.source` | string | 提供該 skill 的來源：對於位於企業、個人或專案[位置](https://code.claude.com/docs/zh-TW/skills.md#where-skills-live)的 skill，分別為 `policySettings`、`userSettings` 或 `projectSettings`。其他來源則提供 `plugin`、`mcp`、`syncedSkills` 或 `built-in` 之類的詞。 |
| `e.pluginName` | string | 對於 `e.source` 為 `plugin` 的 skill，為外掛的名稱 |
| `e.path` | string | skill 的 `SKILL.md` 檔案的絕對路徑；若 skill 是以[命令檔案](https://code.claude.com/docs/zh-TW/skills.md#where-skills-live)撰寫，則為其 `.md` 檔案的絕對路徑。當 skill 在此機器上沒有檔案時（例如內建 skill）則不存在。 |
| `e.frontmatter` | object | skill 檔案的 frontmatter，以純資料形式呈現 |
| `e.frontmatterProblem` | string | `e.frontmatter` 缺少檔案的 frontmatter 或其中某個鍵的原因，例如 `is a list or a single value, not a table`。當 `e.frontmatter` 包含完整的 frontmatter，或 skill 沒有 frontmatter 時則不存在。 |

hook 可以將變更後的 `text` 或 `frontmatter` 傳遞給 `next`：其後的 hook 會讀取兩者，而 Claude 會讀取最終的 `text`。變更任何其他欄位的 hook 會[失敗](https://code.claude.com/docs/zh-TW/plugins/mods/events.md#handle-a-hook-that-fails)。

在 `skill.prompt` 上，`e.source`、`e.pluginName`、`e.path`、`e.frontmatter` 與 `e.frontmatterProblem` 需要 Claude Code v2.1.299 或更新版本。

### 命令與設定

| 事件 | 觸發時機 | hook 可回傳 |
| :- | :- | :- |
| [`command.run`](https://code.claude.com/docs/zh-TW/plugins/mods/api#add-a-command) | 命令即將執行時 | `{ text }`、`{}` 或 `next(e)` |
| `command.describe` | 每個命令一次，用於命令清單 | `{ description, argumentHint, isHidden }` |
| `config.set` | `/config` 列即將變更時 | `next({ ...e, value })` 或 `{ deny: reason }` |
| `config.describe` | 每個 `/config` 列一次 | `{ label, description, isHidden }` |
| [`settings.read`](https://code.claude.com/docs/zh-TW/plugins/mods/events#settings-read-hook) | mod 呼叫 [`$.settings.read`](https://code.claude.com/docs/zh-TW/plugins/mods/api#reach-files-processes-and-the-network)，或 Claude Code 建置工作階段的合併設定時。Claude Code 自身的讀取與 `e.layers` 需要 Claude Code v2.1.304 或更新版本 | `next(e)`、`{ value }` 或 `{ deny: reason }` |

#### `settings.read` 上的 `e.layers` 與 `e.source`

* **`e.layers`**：每個使用中且包含設定的來源各一個 `{ source, settings }` 物件，[優先順序](https://code.claude.com/docs/zh-TW/settings.md#settings-precedence)最低者排在最前。請參閱[`settings.read` hook 接收的內容](https://code.claude.com/docs/zh-TW/plugins/mods/events#settings-read-receives)。
* **`e.source`**：mod 所要求的單一來源，例如 `$.settings.read({ source: 'policy' })`。在 Claude Code 自身的讀取，以及對合併設定的讀取中則不存在

### 回合

回合事件從頭到尾追蹤一次回答，包括其中每個對模型的請求：

| 事件 | 觸發時機 | hook 可回傳 |
| :- | :- | :- |
| [`turn.start`](https://code.claude.com/docs/zh-TW/plugins/mods/events#follow-a-turn) | 回合開始時 | `next(e)` |
| [`turn.step`](https://code.claude.com/docs/zh-TW/plugins/mods/events#follow-a-turn) | 一個請求即將傳送給模型時 | `yield* next(e)`，或 `next({ ...e, model })`、`next({ ...e, effort })` |
| [`turn.complete`](https://code.claude.com/docs/zh-TW/plugins/mods/events#follow-a-turn) | 回合結束時 | `next(e)`，或以 `{ text }` 在回答下方顯示一行 |

### 工作階段

工作階段事件標示工作階段的開始、結束、壓縮，以及與其他工作階段交換訊息：

| 事件 | 觸發時機 | hook 可回傳 |
| :- | :- | :- |
| [`session.start`](https://code.claude.com/docs/zh-TW/plugins/mods/api#add-a-command-or-a-tool) | 每個已載入的 mod 一次，在第一個提示詞之前，並在該 mod 重新載入後再次觸發。`/clear`、`/resume` 或 `/branch` 之後不會觸發。 | `next(e)` |
| `session.end` | 工作階段結束，或執行 `/clear`、`/resume` 或 `/branch` 時。`e.reason` 為 `clear`、`resume`、`logout`、`prompt_input_exit` 或 `other`。`/branch` 會回報 `resume`。 | `next(e)` |
| `session.compact` | 對話即將被壓縮時 | `{ skip: reason }` |
| [`session.receive`](https://code.claude.com/docs/zh-TW/plugins/mods/api#send-and-receive-messages-between-sessions)、[`session.send`](https://code.claude.com/docs/zh-TW/plugins/mods/api#send-and-receive-messages-between-sessions) | 訊息從另一個 agent 或工作階段送達，或即將傳送至另一個 agent 或工作階段時。請參閱[在工作階段之間傳送與接收訊息](https://code.claude.com/docs/zh-TW/plugins/mods/api.md#send-and-receive-messages-between-sessions)。 | `receive` 為 `{ consumed: reason }`，`send` 為 `{ isDelivered: false, reason }` |
| `session.append` | 對話保留的每一列各一次，例如提示詞、回應區塊、工具結果或通知，在其儲存之前 | 以 `next({ ...e, message })` 搭配變更後的 `message.content`，改寫該列的文字區塊，或其中 `tool_result` 區塊的 `content` |
| `session.attach`、`session.detach` | 另一個應用程式連線至工作階段或與其中斷連線時 | `next(e)` |
| `session.measure` | 每個回合之後，以及方案限制的使用百分比變更時 | `next(e)` |

### Subagent

subagent 事件在 subagent 類型提供給 Claude 時，以及 subagent 或 agent team 隊員即將啟動時觸發：

| 事件 | 觸發時機 | hook 可回傳 |
| :- | :- | :- |
| `agent.offer` | subagent 類型提供給 Claude 時 | 以 `{ isOffered: false }` 保留不提供 |
| `agent.spawn` | subagent 或 [agent team](https://code.claude.com/docs/zh-TW/agent-teams.md) 隊員即將啟動，或已完成或已停止的 subagent 即將再次執行時。對於隊員，`e.isTeammate` 為 `true`。對於恢復的執行，會設定 `e.resume`。 | 以 `next({ ...e, model })` 選擇正在啟動者的模型，或 `{ deny: reason }` |

當已完成或已停止的 subagent 即將再次執行時，例如 Claude 使用 [`SendMessage`](https://code.claude.com/docs/zh-TW/sub-agents#resume-subagents) 工具傳送訊息給它時，您的 `agent.spawn` hook 也會執行。在該事件上，`e.resume` 為 `{ agentId }`。若您的 hook 會計算 subagent 數量，請略過設定了 `e.resume` 的事件，以免恢復的 subagent 被重複計算。

回傳 `{ deny: reason }` 即可拒絕恢復的執行。該執行不會開始，subagent 會維持原狀。當該執行是由 `SendMessage` 呼叫所要求時，Claude 會讀取 `a plugin declined the resume:` 後接您的原因，作為該呼叫的結果。若您針對恢復的執行將變更後的事件傳遞給 `next`，例如不同的 `model`，Claude Code 會忽略該變更。

> [!NOTE]
>
> 恢復執行的事件需要 Claude Code v2.1.299 或更新版本。在 v2.1.299 之前，subagent 恢復時您的 `agent.spawn` hook 不會執行。在這些版本上，若要拒絕恢復 subagent 的 `SendMessage` 呼叫，請在 [`tool.call`](https://code.claude.com/docs/zh-TW/plugins/mods/events#guard-or-change-a-tool-call) hook 中比對該工具。

### 介面

介面事件在 Claude Code 繪製轉譯位置時，以及使用者使用 mod 所繪製的控制項時觸發。[在介面中繪製](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md)說明 `ui.render` hook 回傳的內容：

| 事件 | 觸發時機 |
| :- | :- |
| [`ui.render`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#pick-where-to-draw) | [轉譯位置](#render-sites)即將被繪製時 |
| `ui.resolve` | mod 載入時，每個應用程式、轉譯位置與 mod 各一次。結果是 `$.ui.resolve(e)` 讀取的元素表。 |
| [`ui.press`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#respond-to-presses-and-typing)、[`ui.input`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#respond-to-presses-and-typing)、[`ui.select`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#respond-to-presses-and-typing) | mod 所繪製的 `Button`、`Input` 或 `Select` 被使用時 |
| `ui.focus`、`ui.scroll` | 焦點所在的控制項，或窗格或橫帶的捲動位置即將變更時 |
| `ui.close` | 窗格即將關閉時。`e.id` 為該窗格，`e.origin.kind` 為 `plugin`、`person` 或 `unload`。 |
| [`ui.message`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#build-a-tree-from-elements) | `Client` 元素將資料傳送給其 mod 時 |
| [`ui.fault`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#redraw-when-something-changes) | 您的 mod 所繪製的 `Client` 元素無法載入、繪製或執行時。`e.phase` 為 `load`、`render` 或 `run`，`e.reason` 為錯誤訊息。需要 Claude Code v2.1.289 或更新版本。 |

### 其他 mod

這些事件讓 mod 能在其他 mod 載入時對其採取行動，例如拒絕某個 mod，或變更它所接收的 mods API：

| 事件 | 觸發時機 | hook 可回傳 |
| :- | :- | :- |
| [`plugin.register`](https://code.claude.com/docs/zh-TW/plugins/mods/admin#enforce-a-policy-with-a-mod-of-your-own) | hook 模組即將載入時。`e.uses` 列出其事件、mods API 呼叫、環境變數與狀態，與 `claude plugin validate` 印出的內容相同。每個呼叫都不含 `$.` 前綴，例如 `fs.read`。 | `{ refuse: reason }` |
| `engine.create` | 正在為此 mod 建置 mods API 時 | 變更後的 mods API，用以新增命名空間。`user` [層級](#the-hook-function)以外的 mod 也可以保留不提供某個命名空間。 |

當其他 mod 的 hook 呼叫您在 `engine.create` 中新增之命名空間上的方法時，您的方法所發出的 `$` 呼叫會在該 hook 的上下文中執行，直到該事件上的每個 hook 都回傳為止。例如，相對路徑會以該 hook 的工作目錄為基準解析，而在回合正等待該 hook 時，`$.prompt.submit` 會被拒絕。在那之後您的方法所發出的呼叫，則會在您的 mod 自己的上下文中執行。

### 遙測

遙測事件針對 Claude Code 記錄的使用紀錄觸發：

| 事件 | 觸發時機 | hook 可回傳 |
| :- | :- | :- |
| `telemetry.log`、`telemetry.mark` | 遙測紀錄即將被記錄，或標記某項功能的一次使用時。在您安裝的 mod 中，請為遙測 hook 加上篩選條件 `{ to: 'collector' }`，例如 `on('telemetry.log', { to: 'collector' }, hook)`。若沒有此篩選條件，該 mod 將無法通過 `claude plugin validate`。`*` 不會比對這些事件。 | `next(e)` 或 `{ deny: reason }` |

### 設定 hook 事件

每個[設定 hook 事件](https://code.claude.com/docs/zh-TW/hooks.md#hook-events)都是名為 `classic.<Event>` 的事件，例如 `classic.Stop` 或 `classic.PostToolUse`。`e` 是該 hook 的 stdin JSON。

### mods API 呼叫

每個 [mods API 方法](#mods-api-methods)也是一個事件，以其命名空間與方法命名，例如 `fs.read`、`model.complete` 或 `ui.open`。其上的 hook 會攔截在它之後執行之 mod 的呼叫，並可回傳 `next(e)`、`{ deny: reason }` 或 `{ value }`。

## Mods API 方法

mods API 是每個 hook 接收的 `$` 引數。其方法依命名空間分組，例如 `$.ui`。此表依名稱列出每個命名空間的方法，因此 `$.ui` 列中的 `open` 即為呼叫 `$.ui.open(...)`。指南會示範常用方法的用法，而[您建置版本的型別](https://code.claude.com/docs/zh-TW/plugins/mods/create.md#get-the-types-for-your-build)則以範例記錄每個方法。

| 命名空間 | 方法 |
| :- | :- |
| `$.plugin` | `name`、`root`：此外掛的名稱與目錄 |
| [`$.ui`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#pick-where-to-draw) | `resolve`、`invalidate`、`open`、`close`、`panes`、`focus`、`scroll`、`toast`、`notify`、`status`、`log`、`notice`、`ask`、`copy`、`selection`、`blit` |
| [`$.command`](https://code.claude.com/docs/zh-TW/plugins/mods/api#add-a-command) | `register`、`run`、`list` |
| [`$.tool`](https://code.claude.com/docs/zh-TW/plugins/mods/api#add-a-tool) | `register`、`call`、`check`、`list` |
| `$.agent` | `register`、`spawn`、`list`。`list()` 會回傳此工作階段的 subagent 與隊友，每個都帶有 `status`，其值為 `pending`、`running`、`waiting`、`idle`、`completed`、`failed` 或 `killed`，其中 `idle` 與 `waiting` 需要 Claude Code v2.1.289 或更新版本。 |
| [`$.model`](https://code.claude.com/docs/zh-TW/plugins/mods/api#call-a-model) | `complete`、`fork`、`classify` |
| [`$.prompt`](https://code.claude.com/docs/zh-TW/plugins/mods/api#start-a-turn-from-a-background-job) | `submit`、`read`、`fill`、`suggest`、`compose`。Claude 會在一個指明您的 mod 為傳送者的句子之後，讀取來自 `submit({ text })` 的文字。`submit({ text, asUser: true })` 會將文字當作使用者本人的話傳送，不附帶該句子。 |
| `$.turn` | `abort` |
| [`$.session`](https://code.claude.com/docs/zh-TW/plugins/mods/api#send-and-receive-messages-between-sessions) | `messages`、`cwd`、`root`、`model`、`turns`、`id`、`repo`、`surfaces`、`usage`、`version`、`compact`、`send`、`append`、`authorize`。`usage()` 回傳 `{ startedAt, context, rateLimits, cost }`：`context` 包含 `tokens`、`window` 與 `percent`，`rateLimits` 是 `{ kind, percentUsed, resetsAt }` 的清單。 |
| `$.config` | `list`、`set` |
| [`$.settings`](https://code.claude.com/docs/zh-TW/plugins/mods/api#reach-files-processes-and-the-network) | `read` |
| [`$.env`](https://code.claude.com/docs/zh-TW/plugins/mods/api#reach-files-processes-and-the-network) | `get`、`set` |
| [`$.fs`](https://code.claude.com/docs/zh-TW/plugins/mods/api#reach-files-processes-and-the-network) | `read`、`write`、`list`、`exists`、`stat`、`ancestors`。`write` 不是不可分割的操作：它會就地取代檔案內容，因此其他程序可能讀到寫入一半的檔案。多個工作階段都會變更的資料，請存放在 `$.store` 中。 |
| [`$.store`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#keep-state) | `get`、`set`、`delete`、`keys`。由機器上每個工作階段共用的鍵值儲存區。請參閱[從多個工作階段儲存](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md#save-from-more-than-one-session)。 |
| [`$.state`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#keep-a-value-in-\$-state) | 反應式狀態：`get`、`set`，以及從 `claude-code` 匯入的輔助函式 `atom`、`read`、`update`、`derive` 與 `memberOf` |
| [`$.clock`](https://code.claude.com/docs/zh-TW/plugins/mods/api#run-work-in-the-background) | `now`、`sleep`、`after`、`every` |
| [`$.http`](https://code.claude.com/docs/zh-TW/plugins/mods/api#reach-files-processes-and-the-network) | `fetch` |
| [`$.process`](https://code.claude.com/docs/zh-TW/plugins/mods/api#reach-files-processes-and-the-network) | `run`、`spawn` |
| [`$.mcp`](https://code.claude.com/docs/zh-TW/plugins/mods/api#reach-files-processes-and-the-network) | `call`、`connect`。`connect(server)` 會連線至您自己外掛的資訊清單所列出的 MCP 伺服器。 |
| `$.audio` | `play`、`speak` |
| `$.telemetry` | `log`、`mark`。只有當 Claude Code 或內建 mod 發出呼叫時，才會傳送紀錄。 |

## 轉譯位置

轉譯位置是 Claude Code 介面中的擴充點。每一列都是 `ui.render` hook 中 `e.component` 的一個值，並列出 `e.props` 的欄位以及轉譯它的應用程式。`e.surface` 指出正在繪製的應用程式，例如 `terminal`、`desktop` 或 `vscode`。[變更 Claude Code 既有的繪製內容](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md#change-what-claude-code-already-draws)說明 hook 能在某個位置做什麼，並為每種選擇提供範例。

在 VS Code 擴充功能中進行轉譯，需要擴充功能版本 2.1.299 或更新版本。[不擷取功能旗標](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)的工作階段則需要 2.1.304 或更新版本。[在 VS Code 擴充功能中繪製](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md#draw-in-the-vs-code-extension)列出該擴充功能在繪製上的不同之處。

| 位置 | `e.props` | `e.requestId` | 轉譯於 |
| :- | :- | :- | :- |
| [`Pane`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#pick-where-to-draw) | `title`、`isFocused`、`bodyColumns`、`placement`、`scroll`、`view` | 窗格的 `id` | 終端機、Desktop、VS Code |
| [`AbovePrompt`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#pick-where-to-draw) | `hasSurvey`、`isWorking`、`maxRows`、`bodyColumns`、`scroll`、`view` | 單一實例 | 終端機、Desktop |
| `UserMessage` | `text`、`origin`、`isExpanded`，以及依來源而定的 `task` 或 `from` | 訊息 id | 終端機、Desktop、VS Code |
| `AssistantMessage` | 回覆的文字 | 訊息 id | 終端機、Desktop、VS Code |
| `ToolUse`、`ToolResult`、`ToolGroup` | 工具的名稱、輸入與結果 | 工具呼叫 id | 終端機、Desktop、VS Code |
| `CommandOutput` | `command`、`text` | 訊息 id | 終端機、Desktop |
| [`AskUserQuestion`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#change-what-claude-code-already-draws) | 問題與選項 | 工具呼叫 id | 終端機、Desktop、VS Code |
| `ToolProgress` | `kind` | 工具呼叫 id | 終端機 |
| [`Spinner`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#change-what-claude-code-already-draws) | `word`、`message`、`suffix`、`mode` | agent id | 終端機、Desktop、VS Code |
| `TurnDuration` | `word`、`durationMs` | 訊息 id | 終端機 |
| `InfoNotice` | `text`、`command` | 訊息 id | 終端機 |
| `SessionMode` | `modes` | 單一實例 | 終端機、Desktop |
| `PromptHint` | `isDraft`、`isWorking`、`hint` | 單一實例 | 終端機、Desktop |

`e.viewport` 存放 `columns`、`rows` 與 `isFullscreen`。在終端機與 Desktop 應用程式中，在應用程式量測其視窗之前，它不會存在。在這些環境中，其 `rows` 是整個視窗的高度，而非您窗格的高度。在 VS Code 擴充功能中，它一律存在。

若要讓樹狀結構符合其位置，請在 hook 中讀取下列 prop：

* **`Pane` 或橫帶的寬度**：依 `e.props.bodyColumns` 繪製
* **逐字稿旁 `Pane` 的高度**：當 `e.props.placement` 為 `'dock'` 時，`e.props.scroll.bodyRows` 是窗格可供您的樹狀結構使用的列數
* **提示詞上方 `Pane` 的高度**：當 `e.props.placement` 為 `'inline'` 時，窗格會隨您的樹狀結構增高，直到上限為止，而 `bodyRows` 即為該上限。若要要求不同的上限，請參閱 [`$.ui.open` 的 `rows` 欄位](https://code.claude.com/docs/zh-TW/plugins/mods/interface#open-a-pane-at-the-right-time)。

高於窗格的樹狀結構會整體捲動。

## 元素

元素是 `ui.render` hook 所回傳樹狀結構的建構區塊，您可以從 `$.ui.resolve(e)` 取得。[從元素建立樹狀結構](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md#build-a-tree-from-elements)會展示常用元素以及終端機如何繪製它們，[介面圖庫](https://code.claude.com/docs/zh-TW/plugins/mods/gallery.md)則提供大多數元素的螢幕截圖。勾號表示該應用程式可以繪製此元素。

| 元素 | 主要 prop | 終端機 | Desktop | VS Code |
| :- | :- | :-: | :-: | :-: |
| [`Box`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#build-a-tree-from-elements) | `key`、flex 版面配置、[`gap`、`padding`、`margin`](#box-spacing-steps)、`width`、`height`、`minWidth`、`minHeight`、[`borderStyle`](#box-border-styles)、`borderColor`、`borderDimColor`、`backgroundColor`、`position`、`top`、`left`、`right`、`bottom`、`overflow`、`display`、`hover` | ✓ | ✓ | ✓ |
| [`Text`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#build-a-tree-from-elements) | `color`、`backgroundColor`、[`bold`](#text-bold)、`italic`、`underline`、`strikethrough`、`dimColor`、`inverse`、`wrap`、[`size`、`weight`、`mono`、`tabular`](#text-typography)、`hover` | ✓ | ✓ | ✓ |
| [`Button`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#respond-to-presses-and-typing) | `key`、`label`、`children`、`onPress`、`hotkey`、`plain`、`dimColor`、`autoFocus`、`action`、`variant`、`role`、`hover` | ✓ | ✓ | ✓ |
| [`Link`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#link-in-the-desktop-app) | `href`、`label`。請參閱[限制](#limits)。 | ✓ | ✓ | ✓ |
| [`Code`](https://code.claude.com/docs/zh-TW/plugins/mods/gallery#show-code-and-changes) | `source`、`language`、`path`、`startLine`、`format`、`wrap` | ✓ | ✓ | ✓ |
| `Markdown` | `text`、`key`、`dimColor`、`onLinkPress`、`pressableLinks` | ✓ | ✓ | ✓ |
| [`Input`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#take-typed-input-and-draw-a-row-for-each-item) | `key`、`label`、`placeholder`、`value`、`submitLabel`、[`rows`](https://code.claude.com/docs/zh-TW/plugins/mods/gallery#input)、`onSubmit`、`onInput`、`autoFocus` | ✓ | ✓ | ✓ |
| `Select` | `key`、`label`、`options`、`value`、`onSelect`、`autoFocus` | ✓ | ✓ | ✓ |
| `Svg` | 最多 131,072 個字元的 SVG 標記 `source`、`alt` 文字、`width`、`height` 和 `isInteractive` | | ✓ | ✓ |
| [`Client`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#build-a-tree-from-elements) | `module`、`key`、`props`、`width`、`height`、`flexGrow` | ✓ | ✓ | |
| [`Raster`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#draw-a-grid-of-colored-cells) | `key`、最多 512 的 `columns`、最多 256 的 `rows`、`cells`。請參閱[繪製彩色儲存格網格](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md#draw-a-grid-of-colored-cells)。 | ✓ | | |
| `Image` | `key`、`source`（例如最多 2 MiB 的 PNG 或 RGBA 位元組，或檔案路徑）、最多 255 的 `columns` 和 `rows`，以及 `alt` 文字。請參閱[哪些終端機會繪製它](https://code.claude.com/docs/zh-TW/plugins/mods/gallery.md#image-and-client)。 | ✓ | | |

更多 `Button` 規則：

* **`action`**：指定 Claude Code 本身的某個[快捷鍵動作](https://code.claude.com/docs/zh-TW/keybindings.md)，當使用者對該動作的綁定為組合鍵或修飾鍵時，該綁定會按下此按鈕
* **橫帶上的數字 hotkey**：橫帶中按鈕上的數字 `hotkey`，在使用者於空白提示詞中單獨輸入該數字並停頓時也會觸發
* **收合的橫帶**：當橫帶處於[收合](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md#when-the-user-collapses-the-band)狀態時，`action` 綁定和 hotkey 都不會按下其中的按鈕
* **兩個按鈕使用同一個 hotkey**：當同一次繪製中有兩個按鈕指定相同的 `hotkey` 時，由後者取得
* **`variant`**：`primary` 或 `secondary`，其他任何值都會拋出錯誤。在終端機中，`primary` 按鈕會以強調色繪製，除非它是 `plain`。
* **`role`**：`dismiss` 將按鈕標記為關閉按鈕，其他任何值都會拋出錯誤。請在您的 `onPress` 中執行關閉動作。在包含文字和一列按鈕的橫帶中，Desktop 應用程式可以將該列的第一個 `dismiss` 按鈕繪製為其專屬的關閉控制項。終端機則會以如同未設定 `role` 的方式繪製該按鈕。

`Button` 可以用 `children` 取代 `label`：

* **children 可以是什麼**：字串和 `Text` 元素，例如名稱後接淡色的細節，或是彩色標籤。Claude Code 會拒絕 `Button` 內的其他任何元素。
* **為按鈕命名**：`label` 為按鈕命名，預設為其 children 的文字。若按鈕的 children 不是單一字串，請為其指定 `key` 或 `label`。
* **在終端機中**：children 會繪製在 label 原本的位置，在其上任何位置按下都算作一次按下，因此您可以將清單的每一列做成單一按鈕
* **在 Desktop 應用程式和 VS Code 擴充功能中**：按鈕會繪製其 `label`

> [!NOTE]
>
> children 不是單一字串的 `Button` 需要 Claude Code v2.1.295 或更新版本。

`autoFocus` 在任何控制項上都只接受 `true`，因此若要關閉，請省略此 prop。

VS Code 擴充功能會忽略部分元素 prop，並以如同您省略這些 prop 的方式繪製元素：

* **`Box`**：`position` 及其 `top`、`left`、`right` 和 `bottom`、`alignSelf`、`borderDimColor` 和 `hover`
* **`Text`**：`size`、`mono`、`tabular` 和 `hover`
* **`Button`**：`hotkey`、`plain`、`autoFocus`、`action` 和 `hover`，因此使用者在該處要透過點擊按下按鈕，或在按鈕取得焦點後按 Enter。擴充功能也會忽略 `variant` 和 `role`。
* **`Code`**：`language`、`path`、`startLine`、`format` 和 `wrap`，因此程式碼繪製時不會有色彩或行號，而 `format: 'diff'` 區塊會顯示差異的原始文字
* **`Input` 和 `Select`**：`autoFocus`，以及 `Input` 上的 `rows`
* **`Svg`**：`isInteractive`

### `Box` 框線樣式

若要在 `Box` 周圍繪製框線，請將其 `borderStyle` 設為下列其中一個名稱，例如 `borderStyle: 'round'`。每一列說明終端機針對該名稱所繪製的內容，並顯示框線的上緣。

| `borderStyle` | 終端機繪製的內容 | 上緣 |
| :- | :- | :- |
| `'single'` | 直角的細線 | `┌──┐` |
| `'double'` | 雙線 | `╔══╗` |
| `'round'` | 圓角的細線 | `╭──╮` |
| `'bold'` | 粗線 | `┏━━┓` |
| `'singleDouble'` | 上下為細線，左右兩側為雙線 | `╓──╖` |
| `'doubleSingle'` | 上下為雙線，左右兩側為細線 | `╒══╕` |
| `'classic'` | ASCII 字元 `+`、`-` 和 `\|` | `+--+` |
| `'arrow'` | 指向 `Box` 內部的箭頭 | `↘↓↓↙` |
| `'dashed'` | 轉角留白的虛線 | `╌╌` |
| `'quote'` | 左側一條豎條 `▎`，其他三側為空白儲存格 | 空白 |

若 `Box` 的 `borderStyle` 指定為其他任何名稱，例如 `'rounded'`，則繪製時不會有框線。

### `Box` 間距級距

`Box` 的間距 prop 包括 `gap`、`columnGap`、`rowGap`、`padding`、`margin`，以及 `padding` 和 `margin` 的單側與單軸形式，例如 `paddingX` 和 `marginTop`。每個 prop 都接受以終端機儲存格為單位的數字，例如 `gap: 1`，或是級距名稱，例如 `gap: 'md'`。在終端機和 VS Code 擴充功能中，每個級距對應的儲存格數如下：

| 級距 | 橫向儲存格數 | 縱向儲存格數 |
| :- | :- | :- |
| `'xs'` | 1 | 0 |
| `'sm'` | 1 | 0 |
| `'md'` | 2 | 1 |
| `'lg'` | 3 | 1 |
| `'xl'` | 4 | 2 |

若您將 `gap`、`padding` 或 `margin` 設為某個級距，該級距會同時套用於橫向與縱向。例如，在終端機和 VS Code 擴充功能中，`padding: 'md'` 表示左右兩側各兩個儲存格，上下各一列。

級距名稱需要 Claude Code v2.1.299 或更新版本。在較早的版本中，使用級距名稱的樹狀結構不會繪製。

### `Text` 字體排版 prop

在 `Text` 上設定 `size`、`weight`、`mono` 或 `tabular`，即可要求繪製您樹狀結構的應用程式使用特定文字大小、字重、等寬字體或等寬數字。在依賴某個 prop 之前，請先確認終端機和 VS Code 擴充功能如何處理它。若應用程式忽略您設定的 prop，您的樹狀結構仍會在該處繪製，文字則如同您省略該 prop 一樣。

| Prop | 值 | 在終端機中 | 在 VS Code 擴充功能中 |
| :- | :- | :- | :- |
| `size` | `'caption'`、`'footnote'`、`'body'`、`'heading'` 或 `'title'` | 忽略：終端機只有一種文字大小 | 忽略 |
| `weight` | `'regular'`、`'medium'`、`'semibold'` 或 `'bold'` | `semibold` 和 `bold` 會繪製為粗體文字 | `semibold` 和 `bold` 會繪製為粗體文字 |
| `mono` | `true`，要求使用應用程式的等寬字體 | 忽略：終端機一律為等寬 | 忽略，因此文字保留擴充功能本身的字體 |
| `tabular` | `true`，要求使用等寬數字，讓就地更新的數字或一欄數字保持對齊 | 忽略：終端機的數字本來就是一個儲存格寬 | 忽略 |

這四個 prop 需要 Claude Code v2.1.299 或更新版本。在較早的版本中，設定了 `size`、`weight`、`mono` 或 `tabular` 的樹狀結構不會繪製。

#### 以 `weight` 取代 `bold`

`Text` 上的 `bold` 已棄用，改用 `weight`，但仍可正常運作。若要在未設定 `weight` 的 `Text` 上取代它，請將 `bold: true` 改為 `weight: 'semibold'`，即可在 Claude Code v2.1.299 或更新版本上獲得相同結果。

在早於 v2.1.299 的版本中，設定了 `weight` 的樹狀結構不會繪製。若您在 `Text` 上同時設定 `bold` 和 `weight`，則 `bold` 不會有任何作用。

## 限制

hook 與 mods API 呼叫都在時間與大小限制下執行。Claude Code 會略過超過時間限制的 hook。超過巢狀層數、元素數、`Raster` 儲存格數或 `Image` 位元組數限制的樹狀結構[不會被繪製](https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot.md#a-pane-or-band-is-empty)。

| 限制 | 值 |
| :- | :- |
| hook 針對單一事件本身的執行時間，不計入 `next` 內部或 `$.clock.sleep` 以外之 mods API 呼叫內部的時間 | 10 秒，`prompt.edit` hook 則為 50 毫秒 |
| `.catch` 處理常式的執行時間 | 1 秒 |
| 所有 `session.end` hook 合計 | 與 [SessionEnd hook 預算](https://code.claude.com/docs/zh-TW/hooks.md#sessionend-input)相同，除非您變更，否則為 1.5 秒，自您設定中的 `SessionEnd` hook 完成時起算 |
| `$.process.run` 逾時 | 預設 30 秒，最多 10 分鐘 |
| `$.process.run` `stdout` 與 `stderr` | 各 4 MiB。當其中之一被截斷時，`isStdoutTruncated` 或 `isStderrTruncated` 為 `true`。 |
| `$.model.complete` `maxTokens` | 預設 1024，最多 64,000 或模型的輸出上限 |
| `$.fs.read` 與 `$.fs.write` | 單一檔案 4 MiB |
| `$.http.fetch` 請求本文 | 4 MiB，以字元計算。本文較大的呼叫會被拒絕。 |
| `$.http.fetch` 回應本文 | 4 MiB。`text` 保存前 4 MiB，其餘部分不會被讀取。當 `Content-Length` 標頭宣告的大小超過此值時，呼叫會改為被拒絕，原因以 `is over the 4194304-byte limit` 結尾，但經過任何重新導向後的最後一個請求使用 `HEAD` 方法時除外。`HEAD` 豁免需要 Claude Code v2.1.296 或更新版本。 |
| 單一 `$.http.fetch` 呼叫，包含重新導向與本文 | 30 秒 |
| 單一 `$.http.fetch` 呼叫會跟隨的重新導向次數 | 5 |
| hook 的 `drop` 原因或 `config.set` `deny` 原因 | 4,096 個字元。較長原因的結尾會被截斷，drop 或 deny 仍會生效。截斷需要 Claude Code v2.1.292 或更新版本，在較早的版本中，hook 則會改為[失敗](https://code.claude.com/docs/zh-TW/plugins/mods/events.md#handle-a-hook-that-fails)。 |
| 單一樹狀結構中的文字 | 只繪製前 100,000 個字元 |
| `Code` 的 `language` 或 `path`、`Select` 選項的 `value`，或 `Client` 的 `module` | 10,000 個字元。若其中任一項較長，傳回它的 `ui.render` hook 會[失敗](https://code.claude.com/docs/zh-TW/plugins/mods/events.md#handle-a-hook-that-fails)。 |
| `Link` 的 `href` | 2,048 個字元。若其較長，傳回它的 `ui.render` hook 會[失敗](https://code.claude.com/docs/zh-TW/plugins/mods/events.md#handle-a-hook-that-fails)。 |
| 單一樹狀結構的巢狀深度 | 根元素以下 32 層 |
| 單一樹狀結構中的元素與文字子項 | 20,000 |
| 單一樹狀結構中的 `Raster` 儲存格，即每個 `Raster` 的 `columns` 乘以其 `rows` | 262,144 |
| 單一樹狀結構中所有 `Image` 的 PNG 或 RGBA 位元組 | 2 MiB |
| `$.store` | 總計 4 MiB 的 JSON |
| `$.session.messages()` | 最新的 4,096 個項目 |
| `$.ui.invalidate('ui.render')` 重新繪製 | 節流為每秒 10 次，在終端機中針對可見窗格、展開的橫帶與提示詞下方的提示行則為每秒 30 次。更早到來的呼叫會被合併。 |
| `$.ui.toast` | 顯示 4 秒，除非您傳入 `{ timeoutMs }`。在[傳統轉譯器](https://code.claude.com/docs/zh-TW/fullscreen.md#enable-fullscreen-rendering)中，mod 較新的 toast 可能會[取代其較舊的 toast](https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot.md#a-toast-doesn’t-appear)，無論後者正在顯示或正等待顯示。 |
| 未經使用者要求而開啟的窗格 | 自 144 個終端機欄寬起放置，使用者開啟過一次後則為 110 |
| mods API 呼叫之引數的巢狀深度 | 28,000 層。超過此深度時，呼叫會被拒絕，訊息以 `nesting deeper than 28000 levels is not supported` 結尾。需要 Claude Code v2.1.299 或更新版本。 |
| 傳給 `next` 的已變更事件之巢狀深度，[非同步產生器 hook](#events)（例如 `turn.step` 上的 hook）除外 | 28,000 層。超過此深度時，`next` 會被拒絕，訊息以 `nesting deeper than 28000 levels is not supported` 結尾。需要 Claude Code v2.1.299 或更新版本。 |
| hook 傳回值的巢狀深度，`ui.render`、`ui.resolve` 與非同步產生器 hook 除外 | 28,000 層。超過此深度時，hook 的結果會被拒絕，而[回報此情況的通知](https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot.md#find-out-why-a-mod-does-nothing)會包含 `nesting deeper than 28000 levels is not supported`。需要 Claude Code v2.1.299 或更新版本。 |
| 在 hook 模組的單一檔案中彼此巢狀的作用域，例如函式、區塊與迴圈 | 2,000 |
| 命令、工具、subagent 類型與窗格名稱 | 字母、數字、`_` 與 `-`，最多 64 個字元 |
| 單一 `claude plugin test` 測試 | 5 秒，除非測試設定了 `timeoutMs` |

## 設定與環境變數

以下是影響 mod 的設定與環境變數。「位置」欄說明每一項是從哪個設定檔或環境讀取：

| 名稱 | 位置 | 作用 |
| :- | :- | :- |
| `CLAUDE_CODE_PLUGIN_DIRS` | 環境，或 `~/.claude/settings.json` 中的 `env` | 以 `--plugin-dir` 的方式載入的外掛目錄，供無法傳入旗標的應用程式使用。以 `:` 分隔的絕對路徑，在 Windows 上則以 `;` 分隔。 |
| `CLAUDE_CODE_PLUGIN_DIR_WATCH` | 環境 | `1` 會讓長時間執行的非互動式工作階段在儲存時重新載入 `--plugin-dir` mod |
| `prependPlugins`、`appendPlugins` | 受管設定。僅在沒有受管設定的機器上、且工作階段的憑證不是 Team 或 Enterprise `/login` 時，才可使用使用者設定。 | 外掛 id 的清單，例如 `acme-guard@acme-tools`。`prependPlugins` 中的 mod 會在使用者安裝的每個 mod 之前執行，`appendPlugins` 中的 mod 則在之後執行，並依列出的順序。請參閱 [mod 執行順序](https://code.claude.com/docs/zh-TW/plugins/mods/events.md#the-order-mods-run-in)。 |
| `allowManagedModsOnly` | 受管設定，作為[內建防護的選項](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md#set-options-on-the-built-in-guard) | 只有[屬於您組織的](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md#install-your-organizations-mods) mod，以及內建於 Claude Code 的 mod，會執行其 hook。使用者的設定 hook 會繼續執行。 |
| `allowModsToOverrideDenyRules` | 受管設定，作為[內建防護的選項](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md#set-options-on-the-built-in-guard) | 允許使用者安裝的 mod 核准遭 `deny` 規則拒絕的工具呼叫 |
| `allowManagedHooksOnly` | 受管設定 | 封鎖不屬於您組織的 hook 與已安裝的 mod。請參閱[哪些會繼續執行](https://code.claude.com/docs/zh-TW/settings-reference.md#what-runs-under-allowmanagedhooksonly)。 |
| `disableAllHooks` | 任何設定檔 | 在受管設定中，已安裝外掛的任何 mod 或 hook 都不會執行。在您自己的設定中，您組織所管理的內容會繼續執行。請參閱 [`disableAllHooks`](https://code.claude.com/docs/zh-TW/settings-reference#disableallhooks)。 |
| `disableSideloadFlags` | 受管設定 | 在啟動時拒絕 `--plugin-dir` 與 `--plugin-url` |
| `pluginConfigs` | 使用者或受管設定 | 存放 mod 的 `userConfig` 值，以外掛 id 為鍵，例如 `acme-guard@acme-tools`；若是以 `--plugin-dir` 載入的外掛，則以其名稱加上 `@inline` 為鍵，例如 `first-mod@inline` |

`sec-default@builtin` 是內建於 Claude Code 的防護，在 `/plugin` 與偵錯日誌中列為 `cc-plugin-sec-default`。在具有受管設定的機器上，或在憑證為 Team 或 Enterprise [`/login`](https://code.claude.com/docs/zh-TW/authentication#authentication-precedence) 的工作階段中，它會在使用者安裝的每個 mod 之前載入。若設定了受管 `prependPlugins`，則只有在該清單列出此防護時才會載入，並位於所列的位置。

其原始碼位於 [Claude Code 儲存庫的 `mods/sec-default` 目錄](https://github.com/anthropics/claude-code/tree/main/mods/sec-default)。

## 命令

這些命令與旗標用於載入、檢查與測試 mod。`claude` 命令在您的 shell 中執行，`/` 命令則在 Claude Code 提示詞輸入處執行。表格中的 `<directory>` 代表您輸入的路徑，例如 `claude plugin validate ./first-mod`。方括號表示選用的引數。

| 命令 | 作用 |
| :- | :- |
| [`/plugin`](https://code.claude.com/docs/zh-TW/plugins/mods/overview#see-which-mods-a-session-loaded) | 當非內建的 mod 已載入時，在其分頁下方顯示如 `1 mod active · first-mod` 的一行 |
| [`claude plugin validate <directory>`](https://code.claude.com/docs/zh-TW/plugins/mods/create#check-what-claude-code-reads-from-your-mod) | 讀取外掛的資訊清單與 hook 模組，並回報錯誤、其處理的事件，以及其發出的 mods API 呼叫。`--strict` 會將警告視為錯誤，`--json` 會印出機器可讀的報告。 |
| [`claude plugin test [directory]`](https://code.claude.com/docs/zh-TW/plugins/mods/test#write-a-test) | 執行該目錄下（未指定時則為目前目錄）所有檔名以 `.test.ts` 或 `.test.tsx` 結尾的檔案。測試失敗時以狀態 1 結束。 |
| [`claude --plugin-dir <directory>`](https://code.claude.com/docs/zh-TW/plugins/mods/create#write-a-mod-yourself) | 為單一工作階段載入外掛目錄，並在您儲存時重新載入其 hook 模組。重複使用此旗標可載入多個目錄。 |
| `/reload-plugins` | 在您執行時重新載入外掛 |

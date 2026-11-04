<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/plugins/mods/interface | lastmod: 2026-11-02 | section: Plugins / Mods -->
> 來源：https://code.claude.com/docs/zh-TW/plugins/mods/interface（官方 zh-TW，lastmod 2026-11-02）｜分類：Plugins › Mods｜EN 摘要：Draw panes, a band above the prompt, buttons, and text fields from a Claude Code mod, handle presses and input, and keep state between redraws and sessions.

# 使用 mod 在介面中繪製

> 從 Claude Code mod 繪製窗格、提示上方的帶狀區域、按鈕和文字欄位，處理按下和輸入，並在重新繪製和工作階段之間保持狀態。

mod 可以在 Claude Code 中繪製自己的介面，並更改 Claude Code 已經繪製的介面部分。mod 可以繪製的每個位置稱為[渲染位置](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#render-sites)，例如窗格、提示上方的帶狀區域或微調器。Claude Code 在即將繪製渲染位置時會引發 [`ui.render`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#interface) 事件，而您對該事件的 hook 會回傳要在那裡繪製的內容。

此地圖顯示 mod 可以在終端機工作階段中的繪製位置：

![Claude Code 終端機工作階段在全螢幕轉譯模式下的地圖。mod 可以在右側新增窗格作為側邊欄、在逐字稿右上角新增快顯通知、在逐字稿中新增日誌行、在提示上方新增帶狀區域，以及在提示下方新增狀態列。mod 可以重新繪製訊息、工具呼叫列和微調器。提示是 Claude Code 自己的。](https://mintcdn.com/claude-code/dgiVO_Od1X1faduV/images/mods-screen-map.svg?fit=max\&auto=format\&n=dgiVO_Od1X1faduV\&q=85\&s=5fda26b6609c62b68c6f9e528c1590ea)

在較窄的終端機中，窗格位於提示上方而不是逐字稿旁邊。

在開始之前，請先建立您的[第一個 mod](https://code.claude.com/docs/zh-TW/plugins/mods/create.md)。從已完成的範例開始，該範例建立一個具有兩個標籤和計數器的窗格，然後閱讀您想要更改的每個部分的對應章節。

> [!NOTE]
>
> 若要查詢一個屬性或限制，請參閱[參考](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#render-sites)。

## 建立具有標籤的窗格

在本部分中，您將建立一個 mod，該 mod 新增 `/hello-tabs` 命令，該命令會開啟一個窗格。窗格是在寬全螢幕終端機中逐字稿旁邊的側邊欄，或在其他情況下是提示上方的框架區域。此窗格顯示兩個標籤，第二個標籤有一個按鈕，可將計數器加一。重新啟動 Claude Code 後，計數仍然存在。

完成的 mod 看起來像這樣。錄製會開啟窗格、切換到第二個標籤、按幾次按鈕，然後返回第一個標籤：

<video autoPlay muted loop playsInline controls src="https://mintcdn.com/claude-code/dgiVO_Od1X1faduV/images/mods-hello-tabs-light.mp4?fit=max&auto=format&n=dgiVO_Od1X1faduV&q=85&s=49d520094d87b5b44bfe50fa49677f06" aria-label="在 Claude Code 提示處輸入 /hello-tabs 命令，一個框架窗格在其上方開啟，頂部有「1: One」和「2: Two」，以及文字「This is the first tab.」。第二個標籤顯示「Add one」按鈕，旁邊是「Count: 1」，計數上升到 3。窗格然後返回第一個標籤。" />

標籤是一列中的兩個按鈕。mod 會追蹤哪一個是作用中的，並在列下方繪製該標籤的內容。

**1. 建立外掛**

mod 是一個具有清單、指向您的程式碼的 `hooks.json` 和程式碼檔案的外掛。[建立 mod](https://code.claude.com/docs/zh-TW/plugins/mods/create.md#write-a-mod-yourself) 說明了每一個。建立一個名為 `hello-tabs` 的目錄，其中包含 `.claude-plugin` 和 `hooks` 目錄，然後儲存前兩個檔案。

將清單儲存為 `hello-tabs/.claude-plugin/plugin.json`：

```json hello-tabs/.claude-plugin/plugin.json theme={null}
{
  "name": "hello-tabs",
  "version": "0.1.0",
  "description": "Opens a pane with two tabs and a counter",
  "author": { "name": "Your Name" }
}
```

在 `hello-tabs/hooks/hooks.json` 中命名您的進入點：

```json hello-tabs/hooks/hooks.json theme={null}
{
  "modules": ["./register.js"]
}
```

**2. 編寫程式碼**

此清單依照各 hook 在程式碼中出現的順序，說明每個 hook 的作用：

* 新增 `/hello-tabs` 命令，並載入較早的工作階段儲存的計數
* 執行該命令時開啟窗格
* 繪製窗格的內容：標籤列和開啟的標籤的主體

兩個模組級變數 `tab` 和 `count` 保持窗格的狀態。

將此儲存為 `hello-tabs/hooks/register.js`：

```javascript hello-tabs/hooks/register.js theme={null}
// 窗格的 id，用於開啟窗格並在繪製時識別它
const PANE = 'hello-tabs'

// 窗格顯示的內容：哪個標籤是開啟的，以及計數器的值
let tab = 'one'
let count = 0

export function register(on) {
  // 在您的第一個提示詞之前執行，並在重新載入後再次執行
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'hello-tabs', description: 'Open the hello-tabs pane' })
    // 載入較早的工作階段儲存的計數（如果有的話）
    const saved = await $.store.get('count')
    if (typeof saved === 'number') count = saved
    return next(e)
  })

  // 當您輸入 /hello-tabs 時執行
  on('command.run', { command: 'hello-tabs' }, async ($) => {
    // 開啟窗格，給它鍵盤焦點，並讓 Esc 關閉它
    await $.ui.open({ id: PANE, title: 'Hello tabs', focus: true, closeOnEscape: true })
    // 在逐字稿中不列印任何內容
    return {}
  })

  // 每次 Claude Code 繪製窗格時執行
  on('ui.render', { component: 'Pane' }, async ($, e, next) => {
    // 不理會其他 mod 的窗格
    if (e.requestId !== PANE) return next(e)
    // 取得此應用程式可以繪製的元素
    const { Box, Text, Button } = $.ui.resolve(e)
    // 要求 Claude Code 再次執行此 hook
    const redraw = () => $.ui.invalidate('ui.render')

    // 一個標籤：一個按鈕，按下時切換到其標籤
    const tabButton = (name, label, hotkey) =>
      Button({
        key: 'tab-' + name,
        label,
        hotkey,
        plain: true,
        // 調暗不是開啟的標籤
        dimColor: tab !== name,
        onPress: () => {
          tab = name
          redraw()
        },
      })

    // 根據開啟的標籤，在標籤下方顯示的內容
    const body =
      tab === 'one'
        ? [Text({ children: ['This is the first tab.'] })]
        : [
            Box({
              flexDirection: 'row',
              columnGap: 2,
              children: [
                Button({
                  key: 'more',
                  label: 'Add one',
                  hotkey: 'a',
                  onPress: async () => {
                    count += 1
                    redraw()
                    // 儲存計數，以便在重新啟動後仍然存在
                    await $.store.set('count', count)
                  },
                }),
                Text({ children: ['Count: ' + count] }),
              ],
            }),
          ]

    // 整個窗格：標籤列、空白行，然後是主體
    return Box({
      flexDirection: 'column',
      children: [
        Box({
          flexDirection: 'row',
          columnGap: 3,
          children: [tabButton('one', 'One', '1'), tabButton('two', 'Two', '2')],
        }),
        Text({ children: [' '] }),
        ...body,
      ],
    })
  })
}
```

每個 hook 也執行程式碼沒有明確說明的事情：

* **[`session.start`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#session)** 也從 [`$.store`](#keep-state) 讀取儲存的計數，這是一個在工作階段之間持續的鍵值存放區。
* **[`command.run`](https://code.claude.com/docs/zh-TW/plugins/mods/api#add-a-command)** 只告訴 Claude Code 窗格存在。開啟窗格本身不會繪製任何內容：Claude Code 然後引發 `ui.render` 以詢問其中應該放什麼。
* **`ui.render`** 返回元素樹，一個包含其他框、文字和按鈕的 `Box`，並每次從 `tab` 和 `count` 重新建立它。

按下按鈕會執行其 `onPress` 回呼，該回呼會更改變數並呼叫 `redraw`。Claude Code 然後再次執行 `ui.render` hook，該 hook 從新值建立新樹。每個互動式繪製都使用該渲染週期：回呼更改狀態，hook 從新狀態重新渲染。

**3. 開啟窗格**

在您的 shell 中，使用 `claude --plugin-dir ./hello-tabs` 啟動 Claude Code。在 Claude Code 提示處，執行 `/hello-tabs`。一個窗格會開啟，頂部有 `1: One` 和 `2: Two`。按 `2`，然後按 `a`（**Add one** 的快捷鍵）幾次。計數上升。

**4. 檢查計數是否已儲存**

按 Esc 關閉窗格，然後退出工作階段。在您的 shell 中，使用相同的 `claude --plugin-dir ./hello-tabs` 命令再次啟動 Claude Code，並在 Claude Code 提示處執行 `/hello-tabs`。計數在您留下的地方。

若要清除計數，請讓 mod 呼叫 `$.store.delete('count')`。[保持狀態](#keep-state)涵蓋每種值持續多長時間。

## 選擇繪製位置

`ui.render` hook 為每個渲染位置執行，除非您將其縮小到您想要繪製的位置。若要選擇渲染位置，請傳遞一個稱為 [matcher](https://code.claude.com/docs/zh-TW/plugins/mods/events.md#filter-which-events-a-hook-handles) 的篩選器作為 `on` 的第二個引數。`{ component: 'Pane' }` 只為窗格執行 hook。在 hook 中，`e.component` 命名位置，`e.surface` 說明哪個應用程式在繪製，`e.props` 保持位置自己的資料。對於窗格，`e.requestId` 是您用來開啟它的 `id`。

窗格和帶狀區域在 mod 填充它們之前是空的。選擇一個標籤以查看每個位置是什麼以及如何在其中繪製：

> [tab] Pane
>
> 窗格是在寬全螢幕終端機中逐字稿旁邊的側邊欄，或在其他情況下是提示詞上方的框架區域。開啟多個窗格時，每個窗格都會獲得一個顯示其標題的標籤。
>
> 當您的 mod 使用您選擇的 `id` 呼叫 `$.ui.open` 時，窗格會出現，如 `$.ui.open({ id: 'hello-tabs' })`。[在正確的時間開啟窗格](#open-a-pane-at-the-right-time)涵蓋其他欄位以及窗格何時等待更寬的終端機。
>
> 若要在您的窗格中繪製，請篩選 `{ component: 'Pane' }` 並檢查 `e.requestId` 是否為您的 `id`。

> [tab] Band above the prompt
>
> 帶狀區域是直接在提示詞輸入上方的條帶。它始終存在，每個 mod 都共享它。
>
> 您的 hook 返回一棵樹以在帶狀區域中顯示某些內容，或返回 `next(e)` 以不顯示任何內容。樹會替換 mod [在您之後](https://code.claude.com/docs/zh-TW/plugins/mods/events.md#the-order-mods-run-in)在那裡繪製的內容。若要保持他們的內容，請將 `await next(e)` 的結果放在您樹中 [`Box`](#build-a-tree-from-elements) 的子項中。
>
> 若要在帶狀區域中繪製，請篩選 `{ component: 'AbovePrompt' }`。

### 更改 Claude Code 已經繪製的內容

Claude Code 自己繪製大部分介面：訊息、工具呼叫列、微調器等。這些部分中的每一個也是一個渲染位置，因此 mod 可以重新設定樣式或替換它。若要更改一個，請在 `ui.render` hook 上篩選此表中的其名稱：

| 位置 | 它是什麼 |
| :- | :- |
| `UserMessage`, `AssistantMessage` | 逐字稿中的訊息 |
| `ToolUse`, `ToolResult`, `ToolGroup` | 工具呼叫的列、其結果和折疊的呼叫群組 |
| `CommandOutput` | 命令列印的列 |
| `AskUserQuestion` | Claude 開啟以詢問您問題的對話框 |
| `Spinner`, `ToolProgress`, `TurnDuration` | 回合的狀態列：在 Claude 工作時動畫的行、執行中工具的即時進度行，以及關閉回合的行 |
| `InfoNotice`, `SessionMode`, `PromptHint` | 標誌下的狀態列、頁尾中的模式標籤，以及提示詞下方的提示行 |

`Pane`、`AskUserQuestion`、`Spinner`、`UserMessage`、`AssistantMessage` 和工具呼叫位置在終端機、Desktop 應用程式和 VS Code 擴充功能中都有效。[轉譯位置表](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#render-sites)列出其他每個位置的引發位置。

在 Claude Code 已經繪製的位置，您的 hook 可以更改詳細資訊、替換繪製或不理會。選擇一個標籤以查看每個應用於微調器的選項。範例讀取另一個 hook 計數的 `calls` 變數，如[教學 mod](https://code.claude.com/docs/zh-TW/plugins/mods/create.md#write-a-mod-yourself) 中所示。

> [tab] Change a detail
>
> 若要保持 Claude Code 的繪製並更改其一部分，請將 `next` 傳遞事件的副本，其中 `props` 已更改。此 hook 更改微調器單詞後的文字：
>
> ```javascript theme={null}
> on('ui.render', { component: 'Spinner' }, async ($, e, next) => {
>   // 保持 Claude Code 的微調器，並更改其單詞後的文字
>   return next({ ...e, props: { ...e.props, suffix: ' · tool calls: ' + calls + '…' } })
> })
> ```
>
> 微調器保持其動畫和單詞，您的文字跟隨單詞：
>
> ```text theme={null}
> Thinking · tool calls: 2…
> ```

> [tab] Replace the drawing
>
> 若要在位置的位置繪製您自己的內容，請返回樹並不呼叫 `next`。此 hook 在微調器所在的位置繪製一行文字：
>
> ```javascript theme={null}
> on('ui.render', { component: 'Spinner' }, async ($, e) => {
>   const { Text } = $.ui.resolve(e)
>   // 沒有呼叫 next，所以此行在微調器的位置繪製
>   return Text({ children: ['Claude has made ' + calls + ' tool calls'] })
> })
> ```
>
> 當 Claude 工作時，您的行會顯示，Claude Code 的微調器不會：
>
> ```text theme={null}
> Claude has made 2 tool calls
> ```

> [tab] Leave it alone
>
> 若要將位置保留為 Claude Code 繪製的方式，請返回 `next(e)`。hook 通常對某些事件執行此操作，對其他事件則不執行。此 hook 在沒有要計數的呼叫之前保留微調器：
>
> ```javascript theme={null}
> on('ui.render', { component: 'Spinner' }, async ($, e, next) => {
>   // 還沒有要顯示的內容，所以不變地傳遞事件
>   if (calls === 0) return next(e)
>   return next({ ...e, props: { ...e.props, suffix: ' · tool calls: ' + calls + '…' } })
> })
> ```
>
> 在第一個工具呼叫之前，微調器看起來就像沒有 mod 的方式：
>
> ```text theme={null}
> Thinking…
> ```

在這些位置，`next(e)` 會返回對 Claude Code 繪製內容的參照 `{ type: 'engine', ref }`，除非在您之後執行的 mod 返回了它自己的樹。若要更改該繪製中的內容，請將帶有不同 props 的事件副本傳遞給 `next`，如 **Change a detail** 標籤所示。您可以原樣返回該參照，或將其放在 `Box` 中，與您自己的元素並列：

```javascript theme={null}
on('ui.render', { component: 'Spinner' }, async ($, e, next) => {
  const { Box, Text } = $.ui.resolve(e)
  const theirs = await next(e)
  return Box({ flexDirection: 'column', children: [theirs, Text({ children: ['under the spinner'] })] })
})
```

當 Claude 工作時，微調器會像之前一樣顯示動畫，而 `under the spinner` 會出現在其下方。

權限提示不是渲染位置，因此 mod 無法更改其顯示的內容。問題對話框 `AskUserQuestion` 是渲染位置，因此 mod 可以更改它。對話框的樹必須恰好包含該參照一次，並將您的元素放在其上方。否則，Claude Code 會繪製它自己的對話框。

### 在正確的時間開啟窗格

窗格只在您的 mod 開啟它時出現。您如何以及何時開啟它決定了它是否獲得鍵盤焦點、它請求多少空間，以及它是否在狹窄的終端機中顯示。

若要開啟窗格，請使用您選擇的 `id` 呼叫 [`$.ui.open`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#mods-api-methods)。`id` 是窗格的名稱：您的 `ui.render` hook 檢查它，您再次傳遞它以關閉窗格。

```javascript theme={null}
await $.ui.open({ id: 'hello-tabs', title: 'Hello tabs', focus: true })
```

若要關閉窗格，請使用您用來開啟它的 `id` 呼叫 `$.ui.close`：

```javascript theme={null}
await $.ui.close({ id: 'hello-tabs' })
```

除了 `id`，`$.ui.open` 還採用這些可選欄位：

| 欄位 | 它執行的操作 |
| :- | :- |
| `title` | 開啟多個窗格時窗格的標籤標籤 |
| `focus` | 請求[鍵盤焦點](#know-which-keys-your-mod-can-receive) |
| `closeOnEscape` | 使 Esc 關閉窗格 |
| `holdToasts` | 在終端機中，當此窗格是正在顯示的窗格時保留快顯通知。請參閱[在對話框後方保留快顯通知](#hold-toasts-behind-a-dialog)。 |
| `rows` | 當窗格位於提示詞上方時請求的高度。預設值是空間的三分之一。 |
| `columns` | 當窗格位於逐字稿旁邊時請求的寬度，最多為終端機寬度的 45%。一旦使用者在此工作階段或先前的工作階段中調整過逐字稿旁邊窗格的大小，之後在該處開啟的窗格就會改用使用者設定的寬度。該寬度同樣適用 45% 的上限。 |

[VS Code 擴充功能](#draw-in-the-vs-code-extension)會忽略 `rows` 和 `columns`，並自行決定窗格的大小。

`focus`、`closeOnEscape` 和 `holdToasts` 是可選的，只接受 `true`。若要省略其中一個，請將其省略。傳遞 `false` 會擲回錯誤，例如 `ui.open: focus is true or left out`。若要有條件地設定其中一個，請只在條件成立時新增欄位。此呼叫只在 `items` 不為空時請求鍵盤焦點：

```javascript theme={null}
const pane = { id: 'hello-tabs', title: 'Hello tabs' }
await $.ui.open(items.length > 0 ? { ...pane, focus: true } : pane)
```

若要讓命令在 Claude 工作時開啟窗格，請在[註冊命令](https://code.claude.com/docs/zh-TW/plugins/mods/api.md#add-a-command)時新增 `immediate: true`。沒有它，在回合期間輸入的命令會等待回合結束。

#### 在對話框後方保留快顯通知

當窗格是使用者回答後即離開的對話框時，請將 `holdToasts: true` 傳遞給 `$.ui.open`，讓快顯通知不會在使用者做決定時出現。在終端機中，保留會在該窗格是正在顯示的窗格期間持續，而在此期間引發的快顯通知會等到保留結束才出現。

Claude Code 會保留其他 mod 的快顯通知及它自己的短暫通知，也會保留您的 mod 透過 [`$.ui.toast`](https://code.claude.com/docs/zh-TW/plugins/mods/api#show-something-without-starting-a-turn) 引發的通知。對於保持開啟的窗格，請不要設定此欄位，讓使用者能持續看到這些通知。

#### 當窗格等待更寬的終端機時

您的 mod 開啟的窗格（未被請求）不會在狹窄的終端機中出現，因此它無法接管小螢幕。它是否出現取決於開啟它的內容：

* **由使用者執行的操作開啟**，例如他們執行的命令或他們按下的按鈕，窗格在任何寬度出現
* **由您的 mod 自行開啟**，例如從計時器或 [`turn.start`](https://code.claude.com/docs/zh-TW/plugins/mods/events#follow-a-turn) hook，窗格只在至少 144 列寬的終端機中出現。使用者自己開啟該窗格一次後，110 列就足夠了。

當窗格出現時，`$.ui.open` 解析為 `{ isPlaced: true }`。當窗格在等待時，`isPlaced` 是 `false`，`reason` 是說明原因的字串。當使用者開啟窗格或加寬終端機時，等待的窗格會出現。若要說明某些內容可用而不開啟窗格，請呼叫 `$.ui.toast('Your message')`，它會顯示快顯通知。

### 在 VS Code 擴充功能中繪製

在 VS Code 擴充功能中，mod 繪製的內容會出現在聊天面板中，需要擴充功能版本 2.1.299 或更新版本。[不會擷取功能旗標](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)的工作階段（例如在 Amazon Bedrock 上的工作階段）需要 2.1.304 或更新版本。在面板的 `ui.render` hook 中，`e.surface` 為 `vscode`。若要查看面板會繪製哪些位置和元素，以及會忽略哪些 prop，請參閱[轉譯位置](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#render-sites)和[元素](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#elements)表格。

若要讓 mod 在面板和終端機中都能運作，請考量以下差異：

* **窗格**：在寬度 800 像素以上的面板中，窗格會停駐在對話旁邊，`e.props.placement` 為 `'dock'`，且 `e.viewport.isFullscreen` 為 `true`。在較窄的面板中，窗格會繪製在提示詞輸入框上方，`placement` 為 `'inline'`，且窗格在捲動前會顯示 12 列。
* **快顯通知和狀態列**：這些會位於提示詞輸入框正上方的同一個堆疊中，面板較窄時窗格也在其中，每個 mod 有一個狀態列。當權限請求或對話框顯示時，此堆疊會隱藏。
* **標籤**：面板會為 mod 繪製或改寫的內容加上框架，並以外掛的名稱標示，例如 **From the token-chart plugin** 或 **Edited by the token-chart plugin**。
* **鍵盤**：按鈕沒有快速鍵，因此使用者需點擊按鈕，或在按鈕取得焦點後按下 Enter。
* **鍵盤焦點**：只有在面板具有焦點、Claude 處於閒置且沒有等待中的問題，並且提示詞輸入框為空時，面板才會接受窗格的 `focus: true` 請求。
* **問題對話框**：在 `AskUserQuestion`，面板會保留自己的問題卡片，並在其上方繪製您的元素。您傳遞給 `next` 的 props 不會更改該卡片。
* **提示詞建議**：`$.prompt.suggest` 會以 `isShown: false` 解析且不顯示任何內容，因為面板會將提示詞輸入框中的淡色建議文字保留給 Claude 自己的建議。
* **文字限制**：面板會將狀態列截斷為 200 個字元或兩列，並將快顯通知截斷為 500 個字元。

## 從元素建立樹

`ui.render` hook 返回的是元素樹：對要繪製的內容的描述，由相互嵌套的框、文字和控制項組成。您描述繪製，Claude Code 會在使用者開啟的任何應用程式中呈現它：終端機、桌面應用程式或 VS Code 擴充功能。

若要取得元素，請在您的 hook 中呼叫 `$.ui.resolve(e)`，如 `const { Box, Text, Button } = $.ui.resolve(e)`。每個元素都是一個函式。您傳遞它屬性，並將應該在其中的元素和字串放在 `children` 中。

選擇一個標籤以查看每個最常見的元素以及終端機如何繪製它：

> [tab] Text
>
> `Text` 繪製一個字串，具有可選的樣式，例如 `bold` 和 `color`：
>
> ```javascript theme={null}
> Text({ children: ['This is the first tab.'] })
> ```
>
> ```text theme={null}
> This is the first tab.
> ```

> [tab] Box
>
> `Box` 排列其中的內容，在列或行中。此項將按鈕和文字行並排放置，相隔兩列：
>
> ```javascript theme={null}
> Box({
>   flexDirection: 'row',
>   columnGap: 2,
>   children: [
>     Button({ key: 'more', label: 'Add one', onPress: addOne }),
>     Text({ children: ['Count: 0'] }),
>   ],
> })
> ```
>
> ```text theme={null}
> [ Add one ]  Count: 0
> ```

> [tab] Button
>
> `Button` 是使用者可以按下的控制項。它執行您的 `onPress` 回呼。使用 `plain: true` 時，它沒有括號並顯示其快捷鍵：
>
> ```javascript theme={null}
> Button({ key: 'more', label: 'Add one', onPress: addOne })
> Button({ key: 'tab-one', label: 'One', hotkey: '1', plain: true, onPress: showTabOne })
> ```
>
> ```text theme={null}
> [ Add one ]
> 1: One
> ```

> [tab] Input
>
> `Input` 是一個文字欄位。當使用者按 Enter 時，它使用文字執行您的 `onSubmit` 回呼：
>
> ```javascript theme={null}
> Input({
>   key: 'new-note',
>   label: 'Note',
>   placeholder: 'Type a note and press Enter',
>   value: '',
>   submitLabel: 'add',
>   onSubmit: addNote,
> })
> ```
>
> ```text theme={null}
> Note: Type a note and press Enter
> ```
>
> 將 `rows` 設為 2 或以上，即可取得[容納多行的欄位](https://code.claude.com/docs/zh-TW/plugins/mods/gallery.md#input)。

[介面圖庫](https://code.claude.com/docs/zh-TW/plugins/mods/gallery.md)提供大多數元素的範例和螢幕截圖。此表列出每個元素：

| 元素 | 它繪製的內容 | 位置 |
| :- | :- | :- |
| `Box` | 彈性容器。採用佈局 prop，例如 `flexDirection`、[`borderStyle`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#box-border-styles) 和 `width`。`columnGap` 和 `padding` 等間距 prop 採用數字，或從 `'xs'` 到 `'xl'` 的[級距名稱](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#box-spacing-steps)。 | 到處 |
| `Text` | 樣式文字。採用 `color`、`bold`、`dimColor`、`italic`、`wrap`，以及 [`weight`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#text-typography) 等其他 prop。`color` 是主題鍵或顏色，例如 `'red'`。`wrap` 是 `'wrap'`、`'truncate'`、`'truncate-start'`、`'truncate-middle'` 或 `'truncate-end'`。 | 到處 |
| `Button` | 呼叫 `onPress` 的控制項 | 到處 |
| `Link`, `Code`, `Markdown` | 具有 `href` 和可選 `label` 的連結、程式碼區塊和格式化為 Claude 回覆方式的文字。`Markdown` 在 `text` 屬性中而不是在 `children` 中採用其內容，並在您傳遞 `onLinkPress` 時需要 `key`。 | 到處 |
| `Input`, `Select` | 文字欄位和下拉式選單 | 終端機、桌面、VS Code |
| `Svg` | SVG 文件 | 桌面、VS Code |
| `Client` | 由您的第二個檔案繪製的區域，用於動畫和指標輸入。該檔案不取得 mods API。它透過發佈資料到達您的 hook，該資料作為 `ui.message` 事件到達。如果它無法載入、繪製或執行，您的 hook 會收到 [`ui.fault`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#interface) 事件。 | 終端機、桌面 |
| `Raster`, `Image` | [彩色儲存格網格](#draw-a-grid-of-colored-cells)和圖片 | 終端機 |

如果您的模組是 `.tsx` 或 `.jsx` 檔案，您可以將樹寫成 JSX。請先從 `$.ui.resolve(e)` 解構元素。

如果您的繪製沒有顯示，請檢查其樹中是否有元素不採用的 prop，或在不該有子項的位置放置了子項。傳回這種樹的 hook 會[失敗](https://code.claude.com/docs/zh-TW/plugins/mods/events.md#handle-a-hook-that-fails)，而一行 [`hook skipped` 訊息](https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot#a-pane-or-band-is-empty)會指出您的 mod 以及該樹違反的規則。對於窗格中具有名為 `bogusProp` 之 prop 的 `Text`，該行內容如下：

```text theme={null}
my-mod: ui.render hook skipped: returned the wrong shape (a tree Pane refuses: Text prop "bogusProp" is not allowed)
```

### 桌面應用程式和 VS Code 中的 `Link`

在桌面應用程式和 VS Code 擴充功能中，除非 `Link` 的 `href` 符合下列要求，否則會繪製為純文字：

* **協定與主機**：`https:` URL，或 `http://localhost` URL，例如 `http://localhost:3000`
* **不含 `@`**：在路徑或查詢字串中將 `@` 寫成 `%40`
* **寫法**：與 `new URL(href).href` 傳回的結果相同，但可以缺少主機後面的 `/`。這會排除大寫的主機、空格，以及 `https:` URL 上的 `:443`。

在終端機中，這些要求不適用。

### 當 `Client` 失敗時

在終端機中，當 `Client` 執行的檔案失敗時，會有一行變暗的文字（例如 `my-mod: Client client/spinner.js: boom`）取代 `Client` 的位置，而您繪製的其餘部分仍會顯示。

如果您的 mod 處理 [`ui.fault`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#interface)，Claude Code 接著會[再次繪製該位置](#when-claude-code-redraws-without-being-asked)。

### 繪製彩色儲存格網格

對於熱力圖、迷你圖或終端機中的遊戲板，繪製一個 `Raster` 而不是每個儲存格一個 `Box`。`Raster` 採用 `key`、其大小（以 `columns` 和 `rows` 為單位）以及 `cells`，這是一個打包了每個儲存格的 base64 字串。每個儲存格是三個數字：字元的程式碼點、其顏色和其背景顏色。顏色是以十六進位表示的 24 位元 RGB 值，例如 `0xc62828` 表示紅色。值 `0x01000000` 比該範圍大一，表示終端機的預設值。

終端機以外的應用程式沒有 `Raster`，因此請檢查 `e.surface` 並在那裡繪製文字。此窗格主體繪製一個三乘二的熱力圖：

```javascript theme={null}
// 表示「使用終端機的預設顏色」的值
const DEFAULT_COLOR = 0x01000000

// 將 [character, color] 對的列打包到 Raster 採用的一個字串中
// 一個儲存格是三個數字：字元的程式碼點、其顏色和其背景
function cellsOf(rows) {
  const numbers = rows.flat().flatMap(([char, color]) => [char.codePointAt(0), color, DEFAULT_COLOR])
  return new Uint8Array(Uint32Array.from(numbers).buffer).toBase64()
}

on('ui.render', { component: 'Pane' }, async ($, e, next) => {
  // 只在使用 id 'heat' 開啟的窗格中繪製
  if (e.requestId !== 'heat') return next(e)
  const { Box, Text, Raster } = $.ui.resolve(e)
  // 三個儲存格的兩列，每個都是一個區塊字元及其顏色
  const rows = [
    [['█', 0x2e7d32], ['█', 0xf9a825], ['█', 0xc62828]],
    [['█', 0x2e7d32], ['█', 0x2e7d32], ['█', 0xf9a825]],
  ]
  if (e.surface !== 'terminal') {
    return Text({ children: ['The heat map needs the terminal.'] })
  }
  return Box({
    flexDirection: 'column',
    children: [Raster({ key: 'grid', columns: 3, rows: 2, cells: cellsOf(rows) })],
  })
})
```

在終端機中，窗格顯示網格：

![終端機中的窗格，其中包含一個小的彩色區塊網格，兩列三個。頂列是綠色、琥珀色和紅色。底列是綠色、綠色和琥珀色。](https://mintcdn.com/claude-code/dgiVO_Od1X1faduV/images/mods-heat-map.svg?fit=max\&auto=format\&n=dgiVO_Od1X1faduV\&q=85\&s=b91bcce3bad74bc851149133d4acc5d5)

`rows` 陣列是您要更改的部分，`cellsOf` 將其轉換為打包的字串。hook 只在 `id` 為 `heat` 的窗格中繪製，因此請從命令使用 `$.ui.open({ id: 'heat' })` 開啟一個，如同 [`hello-tabs` 範例](#build-a-pane-with-tabs)開啟其窗格的方式。

每個字元必須是一個儲存格寬。若要動畫已在螢幕上的 `Raster`，請使用窗格的 `id` 作為 `requestId`、`Raster` 的 `key`、相同的大小和新儲存格呼叫 `$.ui.blit`。對於此範例，這是 `$.ui.blit({ requestId: 'heat', key: 'grid', columns: 3, rows: 2, cells: cellsOf(newRows) })`。它重新繪製該一個元素，而不再次執行您的 `ui.render` hook。

## 回應按下和輸入

當使用者按下按鈕、輸入欄位或從您的 mod 繪製的清單中選擇時，Claude Code 會呼叫該控制項的回呼，並在您的模組中執行。每個控制項採用其自己的回呼：

* **`Button`**：採用 `onPress(e)`，其中 `e.surface` 是按下來自的應用程式
* **`Input`**：採用 `onSubmit(value)` 和 `onInput(value)`
* **`Select`**：採用 `onSelect(value)` 及其 `options` 中的選擇，至少一個具有唯一值的選擇清單，例如 `[{ value: 'sm', label: 'Small' }, { value: 'lg', label: 'Large' }]`

### 哪些控制項需要 `key`

為每個 `Input` 和 `Select` 提供一個 `key` prop，例如 `key: 'size'`。當 `Button` 具有 `label` prop 或單一字串子元素時，可以不提供 `key`。此時它的鍵即為 `label` 值或該字串。

測試和其他 mod 透過控制項的鍵來識別它：

* **測試**：[測試](https://code.claude.com/docs/zh-TW/plugins/mods/test.md#test-a-drawing)透過控制項的鍵按下或輸入到該控制項。
* **其他 mod**：Claude Code 在執行控制項的回呼之前，會引發 [`ui.press`、`ui.input` 或 `ui.select`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#interface)，其中 `e.element` 中包含控制項的鍵。另一個 mod 針對該事件的 hook 會看到使用者輸入到您的 `Input` 中的內容，並可以更改該文字或阻止您的回呼執行。mods API 沒有提供該 mod 按下您按鈕的方法。

如果訊息顯示 `needs a key` 或 `is drawn twice`，請[依據該訊息找出原因](https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot.md#needs-a-key)。

### 鍵盤焦點和快捷鍵

您的 mod 永遠不會自己讀取鍵盤。使用者按下一個鍵，Claude Code 決定它是為您的哪個控制項，該控制項的回呼執行。除了[帶狀區域上的數字快捷鍵或 `action` 綁定](https://code.claude.com/docs/zh-TW/plugins/mods/reference#elements)外，這只在您的窗格或帶狀區域具有鍵盤焦點時發生。其餘時間，按鍵會進入提示詞輸入區。

在 [VS Code 擴充功能](#draw-in-the-vs-code-extension)中，按鈕沒有快捷鍵：使用者點擊按鈕或在其上按 Enter，並在欄位中輸入。

#### 窗格如何獲得鍵盤焦點

窗格在以下情況下獲得鍵盤焦點：

* 您的 mod 使用 `focus: true` 從命令或按下開啟它
* 使用者按 Ctrl+X 然後 Tab
* 使用者點擊它，這在終端機中需要[全螢幕渲染](https://code.claude.com/docs/zh-TW/fullscreen.md)

Claude Code 只在提示詞輸入區為空且沒有其他內容具有鍵盤焦點時授予 `focus: true`。在使用者輸入時開啟的窗格不會接收他們的按鍵。

#### 每個鍵執行的操作

此表列出當您的窗格或帶狀區域具有鍵盤焦點時鍵執行的操作：

| 鍵 | 它執行的操作 |
| :- | :- |
| Tab | 移動到下一個控制項 |
| 向上和向下 | 在您的繪製適合時在控制項之間移動。當窗格或帶狀區域的列數超過它可以顯示的列數時，它們會滾動它。在終端機的 `Input` 中，它們會[在欄位的各列之間移動](https://code.claude.com/docs/zh-TW/plugins/mods/gallery.md#input)，而從欄位的第一列或最後一列，它們會移動到其前一個或後一個控制項。 |
| Enter | 按下焦點 `Button`、提交焦點 `Input` 或在 `Select` 中選擇 |
| 按鈕的快捷鍵 | 按下該按鈕。當 `Input` 具有焦點時，每個可列印鍵都進入欄位。 |
| Page Up、Page Down、Home 和 End | 當您的窗格或帶狀區域的列數超過它可以顯示的列數時，滾動它 |
| Ctrl+X 然後方向鍵 | 調整您的窗格大小。向左或向上會給它更多空間，向右或向下則會歸還空間。位於逐字稿旁的窗格在達到終端機寬度的 45% 時會停止加寬。 |
| Ctrl+X 然後 X | 關閉您的窗格，即使它的某個欄位具有焦點 |
| Ctrl+X 然後 Ctrl+A | 當 mod 在帶狀區域中繪製時，[將帶狀區域收合](#when-the-user-collapses-the-band)為一列，或再次展開它。這些按鍵在提示詞輸入區具有焦點時也有效。 |
| Esc | 將鍵盤焦點返回到提示詞輸入區。使用 `closeOnEscape: true` 時，它也會關閉窗格。 |

mod 無法將 Tab 或箭頭鍵綁定到其他任何內容，因此遊戲使用 `w`、`a`、`s` 和 `d` 進行轉向。

#### 設定快捷鍵和第一個焦點

* **`hotkey`**：若要讓使用者使用一個鍵按下 `Button`，請給它一個 `hotkey` 的一位數字或一個小寫字母，如 `hotkey: 'a'`
* **`autoFocus`**：若要選擇窗格開啟時哪個控制項具有焦點，請將 `autoFocus: true` 新增到它。在 [VS Code 擴充功能](#draw-in-the-vs-code-extension)中，`autoFocus` 不起作用：控制項的繪製方式就如同您省略了它，您不需要更改任何內容。此 prop 僅接受 `true`，因此請在其他控制項上省略它。

快捷鍵的顯示方式取決於按鈕和應用程式：

| 按鈕 | 在終端機中 | 在桌面應用程式中 | 在 VS Code 擴充功能中 |
| :- | :- | :- | :- |
| 帶括號，預設值 | `[ Add one ]`，沒有顯示快捷鍵 | 標籤旁邊有一個小鍵 | 標籤，快捷鍵不起作用 |
| 使用 `plain: true` | `1: One` | 標籤旁邊有一個小鍵 | 標籤，快捷鍵不起作用 |

在終端機中，在括號按鈕的標籤中命名鍵，或使用 `plain: true`，以便使用者可以看到要按什麼。[元素參考](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#elements)有其他 `Button` 規則：`action`、帶狀區域上的數字快捷鍵，以及一個快捷鍵上的兩個按鈕。

#### 使用者收合帶狀區域時

在終端機中，當 mod 在帶狀區域中繪製時，使用者可以將帶狀區域收合為一列，使其不礙事：

* **點擊 `[-]`**：帶狀區域展開時，Claude Code 會在其第一列的右端繪製此標記。在[全螢幕渲染](https://code.claude.com/docs/zh-TW/fullscreen.md)中，使用者點擊它即可收合帶狀區域。
* **按 Ctrl+X 然後 Ctrl+A**：無論是提示詞輸入區、帶狀區域或窗格具有鍵盤焦點，此操作都有效。使用者可以透過 `abovePrompt:toggle` 動作將[其他按鍵綁定](https://code.claude.com/docs/zh-TW/keybindings.md#above-prompt-actions)到它。

收合的帶狀區域會隱藏 mod 在其中繪製的所有內容，並改為顯示一個暗色列，其中依照使用者的綁定列出展開它的按鍵：

```text theme={null}
▸ plugin panel hidden · ctrl+x ctrl+a or click to show
```

相同的按鍵，或在全螢幕渲染中點擊該列，會再次展開帶狀區域。在此之前，沒有任何方式能按下其中的按鈕：沒有快捷鍵、沒有在空白提示詞輸入區中輸入的數字，也沒有按鈕 [`action`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#elements) 的快捷鍵。如果使用者收合帶狀區域時它具有鍵盤焦點，焦點會返回提示詞輸入區，且在收合期間 Ctrl+X 然後 Tab 會略過帶狀區域。

帶狀區域會保持收合，直到使用者展開它，即使在 `/clear` 之後也是如此，並會在下次 Claude Code 啟動時再次展開。您的 mod 無法展開它，也無法得知它已收合：`ui.render` hook 會持續執行，`e.props` 中也沒有任何內容表明這一點。請勿讓帶狀區域成為您的 mod 顯示使用者必須回應之內容的唯一位置。

### 取得輸入的文字並為每個項目繪製一列

許多窗格是一個文字欄位，下面有一個清單。本部分中的範例是一個筆記窗格：您輸入一個筆記並按 Enter 新增它，每個筆記都有一個 `x` 按鈕來刪除它。新增兩個筆記後，終端機會以這種方式繪製窗格：

```text theme={null}
╭────────────────────────────────────────────────────────✕─╮
│ Note: Type a note and press Enter ⏎ add                  │
│ x buy milk │
│ x call bob │
╰──────────────────────────────────────────────────────────╯
```

頂部邊框上的 `✕` 是 Claude Code 本身用於關閉窗格的標記。

範例使用以下技術：

* **取得輸入的文字**：`Input` 在使用者按 Enter 時使用欄位的文字呼叫 `onSubmit(value)`，並在每次更改時呼叫 `onInput(value)`
* **繪製清單**：將您的資料對應到每個一列，並給每列的按鈕其自己的 `key`

此 hook 繪製窗格的內容：

```javascript theme={null}
// 窗格繪製的清單
let notes = []

on('ui.render', { component: 'Pane' }, async ($, e, next) => {
  // 只在使用 id 'notes' 開啟的窗格中繪製
  if (e.requestId !== 'notes') return next(e)
  const { Box, Text, Button, Input } = $.ui.resolve(e)
  const redraw = () => $.ui.invalidate('ui.render')

  return Box({
    flexDirection: 'column',
    children: [
      Input({
        key: 'new-note',
        label: 'Note',
        placeholder: 'Type a note and press Enter',
        // 欄位起始時的文字
        value: '',
        submitLabel: 'add',
        autoFocus: true,
        // 當您在欄位中按 Enter 時執行
        onSubmit: async (value) => {
          // 忽略空行
          if (!value.trim()) return
          notes = [...notes, value.trim()]
          redraw()
          await $.store.set('notes', notes)
        },
      }),
      // 每個筆記一列：刪除按鈕，然後是筆記的文字
      ...notes.map((note, i) =>
        Box({
          flexDirection: 'row',
          columnGap: 1,
          children: [
            Button({
              // 它自己的鍵，所以每列的按鈕可以區分
              key: 'delete-' + i,
              label: 'x',
              plain: true,
              onPress: async () => {
                notes = notes.filter((_, j) => j !== i)
                redraw()
                await $.store.set('notes', notes)
              },
            }),
            Text({ children: [note] }),
          ],
        }),
      ),
    ],
  })
})
```

若要嘗試窗格：

* **新增筆記**：輸入一行並按 Enter。該行作為新列出現，欄位清空。
* **刪除筆記**：按 Tab 直到筆記的 `x` 按鈕具有焦點，然後按 Enter。`x` 是按鈕的標籤，而不是快捷鍵，因此輸入字母不會按下它。

每個更改都遵循與 `hello-tabs` 相同的渲染週期：回呼更改 `notes`、呼叫 `redraw` 並將清單儲存到 `$.store`。如果您的 hook 在使用者輸入筆記時再次繪製窗格，只要 hook 每次傳入相同的 `value`，欄位就會保留使用者的文字。若要以您自己的文字取代使用者的文字，請傳入不同的 `value`。

範例儲存筆記但不載入它們。若要在下一個工作階段中將它們帶回，請在 `session.start` hook 中讀取它們，就像 `hello-tabs` 讀取 `count` 的方式一樣。

這些屬性組成欄位的行，`Note: Type a note and press Enter ⏎ add`：

| 屬性 | 在範例中 | 它是什麼 |
| :- | :- | :- |
| `label` | `Note` | 欄位前的文字。終端機在其後繪製 `: `。 |
| `placeholder` | `Type a note and press Enter` | 欄位為空時顯示的暗文字 |
| `value` | `''` | 欄位起始時的文字。此處為空，因此會顯示 placeholder。 |
| `submitLabel` | `add` | `⏎` 後的單詞，說明 Enter 執行的操作 |

提交 `Input` 不會啟動回合，除非您的回呼呼叫 [`$.prompt.submit`](https://code.claude.com/docs/zh-TW/plugins/mods/api#start-a-turn-from-a-background-job)。

## 重新繪製位置

繪製是快照：它顯示您的 `ui.render` hook 上次執行時返回的內容。若要顯示新內容，hook 必須再次執行。Claude Code 為某些更改再次執行它，您的 mod 要求其餘的。

### 當 Claude Code 在未被要求時重新繪製

當位置的 prop 更改或終端機的寬度更改時，Claude Code 會再次執行您的 `ui.render` hook。當位置中的 `Client` 失敗，且您的 mod 處理 [`ui.fault`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#interface) 時，Claude Code 會在您的 `ui.fault` hook 返回後再執行一次該 hook，讓您的 `ui.render` hook 可以略過該 `Client`。它不會在計時器上執行 hook，也無法判斷您的模組中的變數何時更改。

### 當您的資料更改時重新繪製

若要在您自己的資料更改後重新繪製您的位置，請呼叫 `$.ui.invalidate('ui.render')`。此窗格計數按下。按鈕的回呼更改 `count`，然後要求重新繪製：

```javascript theme={null}
let count = 0

on('ui.render', { component: 'Pane' }, async ($, e, next) => {
  if (e.requestId !== 'counter') return next(e)
  const { Box, Text, Button } = $.ui.resolve(e)
  return Box({
    flexDirection: 'row',
    columnGap: 2,
    children: [
      Button({
        key: 'more',
        label: 'Add one',
        onPress: () => {
          count += 1
          // 資料已更改，因此要求 Claude Code 再次繪製窗格
          $.ui.invalidate('ui.render')
        },
      }),
      Text({ children: ['Count: ' + count] }),
    ],
  })
})
```

每次按下都會提高窗格中的數字。[`hello-tabs` 範例](#build-a-pane-with-tabs)將相同的呼叫包裝在其 `redraw` 函式中。

您在 [`$.state`](#keep-a-value-in-\$-state) 中保持的值不需要呼叫，因為寫入值會重新繪製讀取它的位置。

### 在計時器上重新繪製

若要保持時鐘、倒計時或來自工作階段外部的值為最新，請按計劃重新繪製。在模組的 `session.start` hook 中啟動計時器。如果模組已經有一個，如 `hello-tabs` 所做的，請將 [`$.clock.every`](https://code.claude.com/docs/zh-TW/plugins/mods/api#run-work-in-the-background) 行新增到它：

```javascript theme={null}
on('session.start', async ($, e, next) => {
  // 每 1000 毫秒，要求 Claude Code 再次繪製您的位置
  $.clock.every(1000, () => $.ui.invalidate('ui.render'))
  return next(e)
})
```

Claude Code 現在每秒執行您的 `ui.render` hook 一次。計時器會在模組重新載入後停止，模組的新執行個體會啟動自己的計時器。

### 位置可以重新繪製的頻率

Claude Code 限制位置重新繪製的頻率，因此您的 mod 可以在其資料更改時經常呼叫 `$.ui.invalidate`。關於每個位置可以重新繪製的頻率，請參閱[限制表](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#limits)。

比限制更快到達的呼叫會合併為一次重新繪製。該重新繪製執行您的 hook 一次，hook 在該時刻讀取您的資料，因此最新值顯示，介於兩者之間的值不顯示。動畫無法比限制更快執行。

## 保持狀態

mod 將值保存在何處，決定了該值持續多長時間：直到模組重新載入、直到工作階段結束，或從一個工作階段延續到下一個工作階段。根據值必須持續多長時間來選擇：

| 將其保持在 | 它持續到 | 用於 |
| :- | :- | :- |
| 模組級變數 | 模組重新載入，這在開發期間每次儲存檔案時發生 | 您可以丟失的值，如 `hello-tabs` 中的 `tab` |
| `$.state` | 工作階段結束，或使用者執行 `/clear`、`/resume` 或 `/branch` | 繪製依賴的值，應該在重新載入後存活 |
| `$.store` | 您的 mod 刪除它，或沒有工作階段在 [`cleanupPeriodDays`](https://code.claude.com/docs/zh-TW/settings-reference#cleanupperioddays) 內讀取或寫入存放區。存放區是一個鍵值存放區，儲存為您外掛程式自己的 JSON 檔案，位於 `~/.claude/plugins/store/` 下。 | 設定、歷史記錄、使用者期望下次找到的任何內容 |

`$.store.get(key)` 解析為值或 `undefined`，`$.store.set(key, value)` 採用任何 JSON 值。

### 在 `$.state` 中保持值

`$.state` 為工作階段的長度保持值，並為您重新繪製。它是反應式狀態：讀取值的 `ui.render` hook 會訂閱它，因此 Claude Code 每次您寫入值時都會重新繪製該位置，您不需呼叫 `$.ui.invalidate`。`$.state` 中的值也在模組重新載入後存活，變數則不會。

若要設定它，請宣告您的值、將您的清單指向宣告，然後定義並使用每個值。範例將 `hello-tabs` 中的 `count` 移動到 `$.state`。

#### 宣告值

在類型宣告檔案中宣告值。外部鍵是您的外掛程式的名稱，其下的每個項目是一個值及其類型。將此儲存為 `hello-tabs/types/index.d.ts`：

```typescript hello-tabs/types/index.d.ts theme={null}
declare module 'claude-code' {
  interface PluginState {
    'hello-tabs': {
      tab: 'one' | 'two'
      count: number
    }
  }
}
```

#### 將清單指向宣告

若要讓 `claude plugin validate` 根據該檔案檢查您的程式碼，請將 `types` 欄位新增到清單及其路徑：

```json hello-tabs/.claude-plugin/plugin.json theme={null}
{
  "name": "hello-tabs",
  "version": "0.1.0",
  "description": "Opens a pane with two tabs and a counter",
  "author": { "name": "Your Name" },
  "types": "./types/index.d.ts"
}
```

#### 定義、讀取和寫入值

在您的模組中，使用預設值定義每個值，在繪製時讀取它，並從回呼寫入它。`atom` 命名值及其預設值，`read` 返回它，`update` 寫入它。三個幫助程式為您呼叫 `$.state.get` 和 `$.state.set`：

```javascript theme={null}
import { atom, read, update } from 'claude-code'

// 在模組的頂部：命名值並給出其預設值
const count = atom({ plugin: 'hello-tabs', key: 'count' }, 0)

// 在 ui.render hook 中：讀取值以繪製它
const n = await read($, count)

// 在按鈕中：從舊值寫入新值
onPress: () => update($, count, (value) => value + 1)
```

因為 `ui.render` hook 讀取 `count`，Claude Code 每次按鈕寫入它時都會再次執行該 hook。

以下規則適用於程式碼：

* **將 `plugin` 和 `key` 寫成文字字串**：`claude plugin validate` 從您的來源讀取它們
* **將每個 `atom` 呼叫的結果保存在 `const` 中**：如果您使用 `let` 宣告 `count`，驗證會失敗，出現 `takes a source the scan can read`
* **在類型宣告檔案中宣告每個值**：否則驗證失敗，出現 `hello-tabs.count is not declared`
* **從回呼或另一個事件的 hook 寫入**：`ui.render` hook 可以讀取狀態，無法寫入它，因此從 `onPress`、`onSubmit` 或另一個事件的 hook 寫入

#### 將 `hello-tabs` 更改為使用 `$.state`

若要將 `hello-tabs` 中的 `count` 移動到 `$.state`，請更改使用它的每一行：

* **在模組的頂部**：新增 `import` 行，並將 `let count = 0` 替換為 `atom` 行
* **在 `ui.render` hook 中**：在 `tabButton` 之前新增 `read` 行，並在 `Text` 中繪製 `'Count: ' + n`
* **在 Add one 按鈕中**：將 `onPress` 替換為[從多個工作階段儲存](#save-from-more-than-one-session)中的按鈕，該按鈕儲存計數以及寫入它
* **在 `session.start` hook 中**：將讀取 `saved` 的兩行替換為[在 `/clear` 後再次載入儲存的值](#load-a-saved-value-again-after-clear)中的 `loadCount` 呼叫

保持 `redraw` 用於標籤按鈕，因為 `tab` 仍然是變數。

### 在 `/clear` 後再次載入儲存的值

如果您的 mod 在 `session.start` 時將儲存的值從 `$.store` 複製到 `$.state`，則必須在 `/clear`、`/resume` 或 `/branch` 後再次複製它。這些命令會將每個 `$.state` 值重設為其預設值，且 `session.start` 不會再次引發。[`classic.SessionStart`](https://code.claude.com/docs/zh-TW/plugins/mods/events#hook-the-settings-hook-events) 則會在每個命令之後引發，`e.source` 設定為 `clear`、`resume` 或 `fork`，因此請在其 hook 中再次複製值。否則您的繪製會顯示預設值，而儲存 `$.state` 值的回呼會以預設值覆蓋您儲存的內容。

此程式碼從兩個 hook 載入 `count`。它建立在 `hello-tabs` 的 `$.state` 版本上，其中 `count` 是原子，`update` 被匯入。將 `loadCount` 放在 `register` 上方，並將 `loadCount` 呼叫新增到您已經擁有的 `session.start` hook。`classic.SessionStart` 也在啟動和壓縮後引發，這不會重設 `$.state`，因此 `source` 上的篩選將該 hook 限制在三種重設：

```javascript theme={null}
// 將儲存的計數從 $.store 複製到 $.state，如果沒有儲存任何內容，則為 0
async function loadCount($) {
  const saved = Number((await $.store.get('count')) ?? 0)
  await update($, count, () => saved)
}

// 在您的第一個提示詞之前執行，並在重新載入後再次執行
on('session.start', async ($, e, next) => {
  await loadCount($)
  return next(e)
})

// 在 /clear、/resume 和 /branch 後再次執行，/branch 報告為 fork
on('classic.SessionStart', { source: ['clear', 'resume', 'fork'] }, async ($, e, next) => {
  await loadCount($)
  return next(e)
})
```

兩個 hook 就位後，窗格在 `/clear` 後顯示儲存的計數，而不是 `0`，下一次按 **Add one** 會新增到儲存的計數。

`loadCount` 將儲存的值寫入 `$.state` 中的值，`session.start` 每次模組重新載入時都會再次引發。若要保持存放區不落後，請在每次更改時儲存，如 **Add one** 按鈕所做的。

若要在沒有工作階段的情況下檢查重新載入，請[在 `/clear` 後測試繪製](https://code.claude.com/docs/zh-TW/plugins/mods/test#test-a-drawing-after-clear)。

### 從多個工作階段儲存

您機器上執行您的 mod 的每個工作階段都共享一個 `$.store`。`get` 後跟 `set` 不是原子的。當兩個工作階段各自讀取值、更改它並寫回時，它們會競爭，第二次寫入會替換第一次。

若要降低這種情況發生的可能性：

* **給每個項目其自己的鍵**：`set` 只更改其自己的鍵，因此寫入不同鍵的工作階段不會相互覆蓋
* **在寫入之前緊接著再次讀取**：對於多個工作階段更改的值，在回呼中 `get` 鍵並從該值建立新值，而不是從您在 `session.start` 時載入的副本。如果另一個工作階段的寫入落在您的 `get` 和 `set` 之間，仍然會丟失。

此按鈕將存放區目前保存的任何值加一，然後更新繪製：

```javascript theme={null}
onPress: async () => {
  // 讀取存放區現在保持的內容，另一個工作階段可能已更改
  const saved = Number((await $.store.get('count')) ?? 0)
  // 儲存新計數，然後顯示它
  await $.store.set('count', saved + 1)
  await update($, count, () => saved + 1)
}
```

如果第二個工作階段自此工作階段啟動以來按下了其自己的按鈕三次，此按下會顯示並儲存包含這三次的計數。

## 後續步驟

* [回應事件](https://code.claude.com/docs/zh-TW/plugins/mods/events.md)：從工具呼叫和輪次提供您的繪製
* [使用 mod API](https://code.claude.com/docs/zh-TW/plugins/mods/api.md)：從計時器和模型呼叫提供您的繪製
* [測試繪製](https://code.claude.com/docs/zh-TW/plugins/mods/test.md#test-a-drawing)：從測試按下您的按鈕，在多個表面上
* [渲染位置](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#render-sites)和[元素](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#elements)：每個位置的屬性和每個元素的屬性

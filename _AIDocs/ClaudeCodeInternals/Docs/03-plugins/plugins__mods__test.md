<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/plugins/mods/test | lastmod: 2026-10-26 | section: Plugins / Mods -->
> 來源：https://code.claude.com/docs/zh-TW/plugins/mods/test（官方 zh-TW，lastmod 2026-10-26）｜分類：Plugins › Mods｜EN 摘要：Write automated tests for a Claude Code mod that fire events, stub Claude Code's answers, and press buttons, with no session, sign-in, or network.

# 測試 mod

> 為 Claude Code mod 編寫自動化測試，該測試會觸發事件、存根 Claude Code 的答案並按下按鈕，無需工作階段、登入或網路。

您可以為 mod 編寫自動化測試，並使用 [`claude plugin test`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#commands) 從您的 shell 執行它們。測試會觸發您的 hook 處理的事件，並檢查 hook 執行了什麼，以便在問題到達工作階段之前捕捉它。第一個範例測試來自[建立 mod](https://code.claude.com/docs/zh-TW/plugins/mods/create.md) 的 mod。

## 編寫測試

測試會載入您的 mod，透過其 hooks 傳送事件，就像 Claude Code 會做的那樣，並檢查 hooks 執行了什麼，無需工作階段、登入或網路。您可以使用 `claude plugin test` 從 shell 執行測試，每個測試檔案都會匯入測試套件，這是 `claude-code/testing` 模組中的測試庫。

給每個測試檔案一個以 `.test.ts` 結尾的名稱，例如 `first-mod.test.ts`，並將其保存在 plugin 目錄中的任何位置。每個測試檔案至少需要一個 `test()`，否則執行會失敗，並顯示 `declares no test(): nothing ran`。測試檔案可以匯入您的 mod 自己的檔案和同級 `.ts` 幫助程式，因此您可以對純函數進行單元測試，例如遊戲的規則，而無需使用套件。

此測試會觸發兩個工具呼叫，執行來自 [Create a mod](https://code.claude.com/docs/zh-TW/plugins/mods/create.md) 的 `/tally` 命令，並檢查回覆是否計算了兩者。其第一行是一個 [stub](#stub-what-claude-code-would-answer)，它代替 Claude Code 回答工具呼叫。將其保存為 `first-mod/tests/first-mod.test.ts`：

```typescript first-mod/tests/first-mod.test.ts theme={null}
import { expect, test } from 'claude-code/testing'

test('/tally reports the tool calls the mod has seen', async ($, on) => {
  // Answer each tool call in Claude Code's place, so no tool runs
  on('tool.call', () => ({ result: 'ok' }))

  // Fire two tool calls, which the mod's tool.call hook counts
  await $.tool.call({ tool: 'Bash', command: 'ls' })
  await $.tool.call({ tool: 'Read', file_path: 'README.md' })

  // Run /tally and check the text its hook returns
  const answer = await $.command.run({ command: 'tally', args: '' })
  expect(answer.text).toBe('Claude has made 2 tool calls since this mod loaded')
})
```

在您的 shell 中，從 `first-mod` 目錄執行測試：

```bash theme={null}
claude plugin test
```

輸出會列出每個測試及其是否通過，以及每次執行都會變化的計時：

```text theme={null}
tests/first-mod.test.ts:
(pass) /tally reports the tool calls the mod has seen [22.87ms]

 1 pass
 0 fail
Ran 1 test across 1 file. [0.19s]
```

每個 `$.tool.call` 都經過了 mod 的 [`tool.call`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#tools) hook，該 hook 將其計數加一，並將呼叫傳遞給 stub。沒有 `ls` 執行，也沒有檔案被讀取。`$.command.run` 隨後進入 mod 的 [`command.run`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#commands-and-configuration) hook，`answer` 是該 hook 返回的物件。

當測試失敗時，命令會以狀態 1 退出，因此它在 CI 中有效。如果您自己的 mods 無法在執行它的 shell 中載入，它會列印一行以 `claude plugin test: hooks modules are turned off` 開頭的行，並顯示原因，然後以狀態 1 退出。

### 存根 Claude Code 會回答的內容

在測試中沒有模型、存儲或工具執行，因此無論您的 mod 期望 Claude Code 回答的地方，測試都會使用 stub 提供答案。測試函數為此接收兩個引數：

* **`$`**：測試自己的 `$`，它代替 Claude Code。它不是 hook 接收的 [mods API](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#mods-api-methods)。它的每個方法都會觸發相同名稱的事件，透過您的 mod 的 hooks 傳送它，並解析為結果：`$.tool.call({ tool: 'Bash', command: 'ls' })` 觸發 `tool.call`。`$.command.run`、`$.prompt.submit`、`$.session.start` 和 `$.turn.complete` 的工作方式相同，`$.classic.Stop` 和其他 `$.classic` 方法會觸發 [settings hook 事件](https://code.claude.com/docs/zh-TW/plugins/mods/events.md#hook-the-settings-hook-events)。測試無法直接觸發 mods API 呼叫，例如 `ui.close`。透過您的 mod 觸發它，例如按下關閉窗格的按鈕。
* **`on`**：呼叫它來註冊 stubs，這些是代替 Claude Code 回答的 hooks。為 mods API 呼叫命名 stub 時不要使用 `$.`，因此註冊為 `store.get` 的 stub 會回答您的 mod 的 `$.store.get`。當您的 mod 呼叫 [`$.model.complete`](https://code.claude.com/docs/zh-TW/plugins/mods/api#call-a-model) 或 [`$.store.get`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#keep-state) 時，stub 會提供答案。

此範例存根一個模型呼叫。該 hook 屬於名為 `grader` 的 mod，並處理一個 `/grade` 命令，該命令將句子發送到模型並報告回覆是否以 `PASS` 開頭。該檔案只包含正在測試的 hook，因此 mod 還需要 `plugin.json` 和 `hooks.json`，如 [Create a mod](https://code.claude.com/docs/zh-TW/plugins/mods/create.md#write-a-mod-yourself) 中所示。要在工作階段中輸入 `/grade`，mod 還必須 [register the command](https://code.claude.com/docs/zh-TW/plugins/mods/api.md#add-a-command)：

```javascript grader/hooks/register.js theme={null}
export function register(on) {
  on('command.run', { command: 'grade' }, async ($, e) => {
    // e.args is the text typed after /grade
    const reply = await $.model.complete({
      model: 'haiku',
      system: 'Grade the sentence. Start your reply with PASS or FAIL.',
      prompt: e.args,
    })
    const passed = reply.isAnswered && reply.text.startsWith('PASS')
    return { text: passed ? 'Passed' : 'Try again' }
  })
}
```

此測試存根模型呼叫以檢查 hook 對通過回覆的處理：

```typescript grader/tests/grader.test.ts theme={null}
import { expect, test } from 'claude-code/testing'

test('a passing grade is reported', async ($, on) => {
  // Answer the mod's $.model.complete call with a fixed reply, so no model runs
  on('model.complete', () => ({
    value: {
      isAnswered: true,
      text: 'PASS\nNice sentence.',
      usage: { input_tokens: 10, output_tokens: 5, cache_read_input_tokens: 0, cache_creation_input_tokens: 0 },
    },
  }))

  // Run /grade, which makes the mod call the model
  const answer = await $.command.run({ command: 'grade', args: 'The cat sat on the mat.' })
  expect(answer.text).toBe('Passed')
})
```

測試通過是因為 hook 的 `reply` 是 `value` 下的物件，其 `text` 以 `PASS` 開頭。要檢查另一個分支，請新增第二個測試，其 stub 返回以 `FAIL` 開頭的 `text`，並期望 `Try again`。

mods API 呼叫的 stub 返回一個具有 `value` 欄位的物件，該欄位保存呼叫在您的 mod 中解析的內容：`{ value: 7 }` 使 `$.store.get` 解析為 `7`。Claude Code 事件（例如 [`turn.step`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#turns) 或 `tool.call`）的 stub 返回該事件自己的結果，例如 `{ result: 'ok' }`。`$.session.send` 和 `$.prompt.fill` 也採用其事件的結果，如表所示。[Look up what a stub returns](#look-up-what-a-stub-returns) 顯示每個常見名稱採用的形式。這些錯誤表示 stub 有誤或遺漏。失敗的測試的輸出包括一個以 `the engine reported:` 開頭的區塊，每個錯誤都出現在那裡：

* `returned neither { value } nor { deny }`：mods API 呼叫的 stub 返回了一個裸值，這會使測試失敗
* `no implementation for` 後跟一個名稱：您的 mod 進行了該呼叫，沒有 stub 回答它

該套件還匯出了現成的 mock，用於時鐘、存儲、環境變數，以及附加到對話中的列：

* **`mock.clock(on)`**：回答 [`$.clock`](https://code.claude.com/docs/zh-TW/plugins/mods/api#run-work-in-the-background)，並返回一個由您的測試推進的模擬時鐘，因此計時器測試不會等待。
* **`mock.store(on, { count: 7 })`**：從以這些項目開始的存儲中回答 `$.store`。它不返回任何內容，因此要檢查您的 mod 保存了什麼，請自己編寫兩個 `store` stub，如 [drawing test](#test-a-drawing) 所做的那樣。
* **`mock.env(on, { CI: 'true' })`**：從這些變數中回答 `$.env.get`。
* **`mock.session(on)`**：返回一個模擬工作階段，其 `appended()` 方法會列出您的 mod 透過 [`$.session.append`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#session) 新增的列，由舊到新排列；需要 Claude Code v2.1.293 或更新版本。

### 遵循測試套件的規則

測試套件有一些自己的規則，違反其中一個會產生新測試作者首先遇到的錯誤：

* **在測試首次呼叫 `$` 之前註冊每個 stub。** 在此之後呼叫 `on` 會拋出錯誤，例如 `on("ui.render") after the test first called $`。

* **[`session.start`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#session) 不會自行執行。** 每個測試都以您的模組新鮮載入開始，其 hooks 都未被呼叫，因此模組級變數保持其初始值。如果 hook 依賴於 `session.start` 設定的內容，請先觸發它：

  ```typescript theme={null}
  // Answer the event after your hook passes it on with next(e)
  on('session.start', () => ({ cwd: '/work' }))
  // Answer the $.command.register call your hook makes
  on('command.register', () => ({ value: undefined }))
  // Fire the event, which runs your session.start hook
  await $.session.start({ surface: 'terminal', isInteractive: true, cwd: '/work' })
  ```

  第二個 stub 回答 `session.start` hook（例如 [tutorial's](https://code.claude.com/docs/zh-TW/plugins/mods/create.md#write-a-mod-yourself)）進行的 `$.command.register` 呼叫。沒有它，該呼叫會以 `no implementation for command.register` 拒絕，套件會跳過您的 hook，因此 hook 中呼叫之後的任何內容都不會執行。測試在該點不會失敗。只有當稍後的檢查失敗時，跳過的 hook 才會在 `the engine reported:` 下列出。

* **返回 `next(e)` 的 hook 需要 stub 來回答。** 例如，當您的 [`ui.render`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#interface) hook 返回 `next(e)` 時，為了在 Claude 閒置時不繪製任何內容，[mounting it](#test-a-drawing) 會失敗，並顯示 `no implementation for ui.render`。註冊一個返回元素作為純資料的 stub：

  ```typescript theme={null}
  // Stands for what Claude Code would draw at the site
  on('ui.render', () => ({ type: 'Text', props: {}, children: ['drawn by Claude Code'] }))
  ```

  註冊 stub 後，掛載成功，每當您的 hook 返回 `next(e)` 時，`ui.find({ type: 'Text' })` 都會返回該元素。

* **`turn.step` 的 stub 是一個非同步生成器**，測試會讀取流直到結束以獲得結果：

  ```typescript theme={null}
  on('turn.step', async function* ($, e) {
    // Each yield is one piece of the model's streamed reply
    yield { kind: 'text', index: 0, text: 'ok' }
    // The return value is the result of the whole request
    return { turnId: e.turnId, index: e.index, answer: 'ok', toolUses: [], stopReason: 'end_turn', usage: null }
  })

  // Fire one request to the model, which runs your turn.step hook
  const stream = $.turn.step({ turnId: 't', index: 0, model: 'claude-test', messageCount: 1 })
  // Read every piece until the stream says it's done
  let step = await stream.next()
  while (step.done !== true) step = await stream.next()
  const result = step.value
  ```

  當迴圈結束時，`result` 是 stub 返回的物件，在您的 `turn.step` hook 有機會更改它之後。這裡 `result.answer` 是 `'ok'`。

* **使用工具的名稱和引數作為欄位來觸發工具呼叫**，例如 `await $.tool.call({ tool: 'Bash', command: 'ls' })`，並註冊一個返回 `{ result }` 的 `tool.call` stub。

### 查詢 stub 返回的內容

您的 mod 在測試中進行的每個 mods API 呼叫都需要一個代替 Claude Code 回答的 stub，除了套件自己回答的少數幾個：[`$.ui.invalidate`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#redraw-when-something-changes)、[`$.state`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#keep-state) 和 `$.session.append` 呼叫。對於 `$.clock` 呼叫，使用 `mock.clock(on)`，否則您的 mod 的 `$.clock.now()` 會失敗，並顯示 `no implementation for clock.now`。

此表列出了 mods 最常使用的。第一列是您的 mod 進行的呼叫或它使用 `next(e)` 傳遞的事件。第二列是傳遞給該名稱下的 `on` 的函數，因此 `$.store.get` 列變成 `on('store.get', ($, e) => ({ value: saved.get(e.key) }))`。stub 中的 `'...'` 標記您要填入的文字：

| 您的 mod 呼叫或傳遞 | Stub |
| :- | :- |
| `$.command.register`、`$.tool.register`、`$.ui.toast`、`$.ui.log`、`$.ui.status`、`$.ui.close`、`$.store.set` | `() => ({ value: undefined })`。對於 `ui.toast` 和 `ui.log`，文字是 `e.text`。 |
| `$.store.get` | `($, e) => ({ value: saved.get(e.key) })` |
| `$.fs.read` | `($, e) => ({ value: e.path.endsWith('notes.md') ? '# Notes' : '' })`。`e.path` 作為絕對路徑到達，因此與 `endsWith` 比較。 |
| `$.ui.open` | `() => ({ value: { isPlaced: true } })` |
| `$.ui.ask` | 一個 `tool.call` stub，因為問題作為對 `AskUserQuestion` 工具的呼叫到達它：`($, e) => ({ result: { answers: { [e.questions[0].question]: 'Run it' } } })`。如果您的 mod 傳遞其他工具呼叫，請先檢查 `e.tool`。 |
| `$.model.complete` | `() => ({ value: { isAnswered: true, text: '...', usage } })` |
| `$.process.run` | `($, e) => ({ value: { exitCode: 0, stdout: '...', stderr: '' } })`。`e.argv` 是引數列表，`e.init` 保存 `cwd` 和 `timeoutMs`。 |
| 任何應該失敗的 mods API 呼叫 | `() => ({ deny: 'the reason' })`，這使呼叫在您的 mod 中拒絕。拋出的 stub 會被跳過。 |
| `session.start` | `() => ({ cwd: '/work' })` |
| `turn.start` | `($, e) => ({ turnId: e.turnId })` |
| `tool.call` | `() => ({ result: '...' })` |
| `turn.complete` | `() => ({ text: '' })`。使用 `$.turn.complete({ turnId, answer, durationMs, isAborted: false, usage: null })` 觸發它。 |
| `prompt.submit` | `($, e) => ({ text: e.text })` |
| `prompt.fill` | `() => ({ isFilled: true })` |
| `$.prompt.read` | `() => ({ value: { text: '...', cursor: 0 } })` |
| `$.ui.copy` | `() => ({ value: { isCopied: true } })` |
| `$.ui.notify` | `() => ({ value: { isSent: true, channel: 'terminal_bell' } })`。文字是 `e.text`，標題是 `e.title`。 |
| `$.session.messages` | `() => ({ value: [{ role: 'assistant', text: '...', toolUses: [] }] })` |
| `$.session.id`、`$.agent.list` | `() => ({ value: 'abc123' })`、`() => ({ value: [] })` |
| `session.send` | `() => ({ isDelivered: true })`。`e.to` 作為字串到達，即使您的 mod 傳遞了 `{ sessionId }`。 |
| `session.receive` | `($, e) => ({ text: e.text })`。使用 `$.session.receive({ origin: { kind: 'peer-send-message' }, text })` 觸發它。 |
| `ui.render` | `() => ({ type: 'Text', props: {}, children: ['...'] })` |

`expect` 有斷言 `toBe`、`toEqual`、`toMatch`、`toMatchObject`、`toContain`、`toBeDefined`、`toBeUndefined` 和 `toThrow`，以及任何斷言之前的 `.not`。

當 `expect` 在您以一般函數（而非非同步生成器）傳給 `on` 的 stub 或 hook 內失敗時，測試會失敗。引擎會跳過該 hook，失敗輸出會指出它，例如 `in the test's store.set hook`。

## 測試計時器

在計時器上執行工作的 mod 需要測試控制的時鐘，因此測試可以向前移動時間而不是等待。`const clock = mock.clock(on)` 返回一個從 `0` 開始的模擬時鐘，只有在您的測試移動它時才會移動。要從另一個時間開始，請以毫秒為單位傳遞它，如 `mock.clock(on, { now: 5000 })`。時鐘有這些方法：

| 方法 | 它做什麼 |
| :- | :- |
| `await clock.advance(1000)` | 將時間向前移動該毫秒數，並執行每個到期的計時器 |
| `await clock.set(5000)` | 將時間向前移動到該值，如 `advance` 會做的那樣 |
| `clock.now()` | 返回時間，這是您的 mod 的 `$.clock.now()` 解析的內容 |
| `await clock.settle()` | 執行已經到期的計時器，例如一系列零延遲 `$.clock.after` 呼叫，而不移動時間 |
| `await clock.sleep(2000)` | 在 stub 內，使該 stub 只有在測試推進到那麼遠時才回答，這是您模擬緩慢模型或程序的方式 |

此 hook 屬於名為 `countdown` 的 mod，並處理一個 `/countdown` 命令，該命令接受秒數，啟動一個一秒的 `$.clock.every` 計時器，並在零時顯示 toast。與 `grader` 一樣，該檔案只包含正在測試的 hook，不註冊命令：

```javascript countdown/hooks/register.js theme={null}
export function register(on) {
  on('command.run', { command: 'countdown' }, async ($, e) => {
    // e.args is the text typed after /countdown
    let left = Number(e.args)
    const timer = $.clock.every(1000, () => {
      left -= 1
      if (left === 0) {
        timer.cancel()
        $.ui.toast('Time is up')
      }
    })
    // Print nothing in the transcript
    return {}
  })
}
```

此測試執行 `/countdown 3` 並移動模擬時鐘，因此它檢查三秒的行為而無需等待三秒：

```typescript countdown/tests/countdown.test.ts theme={null}
import { expect, mock, test } from 'claude-code/testing'

test('the countdown ends with a toast', async ($, on) => {
  // Answer every $.clock call from a clock the test controls
  const clock = mock.clock(on)
  // Collect the text of each toast the mod shows
  const toasts: string[] = []
  on('ui.toast', ($, e) => {
    toasts.push(e.text)
    return { value: undefined }
  })

  await $.command.run({ command: 'countdown', args: '3' })
  // After two seconds the timer has fired twice, and no toast is due
  await clock.advance(2000)
  expect(toasts).toEqual([])
  // The third second brings the count to zero
  await clock.advance(1000)
  expect(toasts).toEqual(['Time is up'])
})
```

第一個 `expect` 顯示 toast 不會提前出現，第二個顯示它出現一次。每個 `advance` 在到期的計時器執行後解析，因此下一行的檢查會看到它們的效果。

## 測試繪圖

測試可以繪製您的 mod 的 [render sites](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#render-sites) 之一，然後按下、輸入並找到它繪製的元素。`$.ui.mount` 透過您的 mod 的 `ui.render` hook 繪製該網站，並返回一個具有每個方法的句柄。要在一個測試中涵蓋多個應用程式，請將 `surface` 設定為要繪製的應用程式。此測試打開來自 [Build a pane with tabs](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md#build-a-pane-with-tabs) 的窗格，切換標籤，按下按鈕，並檢查終端和桌面應用程式中的計數：

```typescript hello-tabs/tests/hello-tabs.test.ts theme={null}
import { expect, test } from 'claude-code/testing'

// What Claude Code passes to a ui.render hook for this pane, apart from the app
const PANE = {
  plugin: 'hello-tabs',
  component: 'Pane',
  requestId: 'hello-tabs',
  viewport: { columns: 100, rows: 30 },
  props: {
    title: 'Hello tabs',
    isFocused: true,
    bodyColumns: 60,
    placement: 'inline',
    scroll: { offset: 0, bodyRows: 10 },
    view: {},
  },
} as const

test('the second tab counts presses and saves the count', async ($, on) => {
  // Stub $.store with a Map, so the test can read what the mod saved
  const saved = new Map<string, unknown>()
  on('store.get', ($, e) => ({ value: saved.get(e.key) }))
  on('store.set', ($, e) => {
    saved.set(e.key, e.value)
    return { value: undefined }
  })

  // Draw the pane once for each app
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...PANE, surface })
    // Press the buttons by the key the mod gave them
    await ui.press({ key: 'tab-two' })
    await ui.press({ key: 'more' })
    // The second tab's count line is in the drawing
    expect(await ui.find({ type: 'Text', text: /^Count: \d+$/ })).toBeDefined()
    await ui.unmount()
  }

  // One press in each app makes two
  expect(saved.get('count')).toBe(2)
})
```

在您的 shell 中，從 `hello-tabs` 目錄執行 `claude plugin test`。當兩個應用程式都繪製計數行且 mod 已保存 `2` 時，測試通過。計數從第一個應用程式延續到第二個應用程式，因為兩個掛載都使用相同的載入模組。

`$.ui.mount` 返回的句柄有這些方法，它們透過您給它們的 `key` 來定址元素：

| 方法 | 它做什麼 |
| :- | :- |
| `press({ key: 'more' })` | 按下具有該 key 的 `Button` |
| `input({ key: 'new-note', text: 'buy milk' })` | 將文字輸入到具有該 key 的 `Input` 中並按 Enter。新增 `kind: 'change'` 以輸入而不提交。對於具有 `rows` 的欄位，文字可以包含 `\n`。 |
| `select({ key: 'size', value: 'large' })` | 在具有該 key 的 `Select` 中選擇具有該值的選項 |
| `find({ key: 'more' })` 或 `find({ type: 'Text', text: 'Count: 2' })` | 返回第一個匹配的元素作為 `{ type, props, children }`，或 `undefined`。`text` 可以是字串或正規表達式。 |
| `unmount()` | 移除繪圖 |

每個方法在您的處理程式完成後解析，因此您可以在下一行檢查結果。將 `props` 設定為 Claude Code 為該網站傳遞的內容。[render sites table](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#render-sites) 列出每個網站的 props，[your build 的類型](https://code.claude.com/docs/zh-TW/plugins/mods/create.md#get-the-types-for-your-build) 有它們的類型。

若要找出對您在 `surface` 中指定的應用程式無效的[元素樹](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md#build-a-tree-from-elements)，請使用 `find` 檢查您的 hook 新增的元素。測試不會檢查應用程式如何繪製樹，因此也請在真實工作階段中查看新佈局。

### 在 `/clear` 之後測試繪圖

每個測試都以每個 `$.state` 值在其預設值開始，這是 `/clear` 留下它們的方式。要測試您的 mod 接下來做什麼，請跳過 `session.start`，使用 `source: 'clear'` 觸發 `classic.SessionStart`，並檢查您的 mod 繪製的內容。

此測試檢查來自 [Load a saved value again after `/clear`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#load-a-saved-value-again-after-clear) 的模組。將其新增到 [Test a drawing](#test-a-drawing) 中的檔案，其中定義了 `PANE`。該檔案的第一個測試期望按鈕保存計數，如 [Save from more than one session](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md#save-from-more-than-one-session) 中的按鈕所做的那樣：

```typescript hello-tabs/tests/hello-tabs.test.ts theme={null}
test('the saved count comes back after /clear', async ($, on) => {
  // The store already holds a count of 7
  on('store.get', () => ({ value: 7 }))
  // Answer the event after your hook passes it on with next(e)
  on('classic.SessionStart', () => ({}))

  // Fire the event that follows /clear, which runs your hook
  await $.classic.SessionStart({ source: 'clear' })

  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.press({ key: 'tab-two' })
  // The pane shows the stored count, not the default of 0
  expect(await ui.find({ type: 'Text', text: 'Count: 7' })).toBeDefined()
})
```

當您的 `classic.SessionStart` hook 在窗格繪製之前將儲存的 `7` 複製到 `$.state` 時，測試通過。如果您的模組中沒有該 hook，窗格會繪製 `Count: 0`，`find` 返回 `undefined`，測試在 `toBeDefined` 處失敗。

## 測試策略 mod

您的組織在 [`prependPlugins`](https://code.claude.com/docs/zh-TW/plugins/mods/admin) 中列出的 mod 可以在另一個 mod 載入之前拒絕它。要測試一個，請設定您的 mod 的層級，並給測試第二個 mod 供您的 mod 允許或拒絕：

* **`tier`**：在測試檔案的頂部呼叫它一次，如 `tier('prepend')`，以將您的 mod 載入為 `prepend`、`append` 或 `builtin`，其在 [order mods run in](https://code.claude.com/docs/zh-TW/plugins/mods/events.md#the-order-mods-run-in) 中的位置。沒有它，您的 mod 會載入為 `user`。
* **`plugins`**：在測試主體之前將 `test` 傳遞一個選項物件。其 `plugins` 陣列保存您內聯編寫的 mods，每個都有 `name` 和 `register` 函數。要在 `user` 以外的位置載入一個，請將 `tier` 新增到它。

此測試檔案首先載入[管理頁面中的策略 mod](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md#enforce-a-policy-with-a-mod-of-your-own)。它檢查策略 mod 是否拒絕啟動程序的 mod，並允許不啟動程序的 mod：

```typescript acme-guard/tests/guard.test.ts theme={null}
import { expect, test, tier } from 'claude-code/testing'

// Load the mod under test ahead of every other mod
tier('prepend')

// A second mod whose code calls $.process.run, which the policy blocks
const runner = {
  name: 'runner',
  register(on) {
    on('tool.call', async ($, e, next) => {
      await $.process.run(['ls'])
      return { result: 'runner answered' }
    })
  },
}

// A second mod that calls nothing the policy blocks
const reader = {
  name: 'reader',
  register(on) {
    on('tool.call', async ($, e, next) => {
      return { result: 'reader answered' }
    })
  },
}

test('refuses a mod that starts a process', { plugins: [runner] }, async ($, on) => {
  on('tool.call', () => ({ result: 'claude code answered' }))
  let message = ''
  try {
    // The first call on $ loads the mods, so the refusal is thrown here
    await $.tool.call({ tool: 'Bash', command: 'ls' })
  } catch (error) {
    message = error.message
  }
  expect(message).toBe('runner: refused by acme-guard: Acme policy: mods may not call process.run')
})

test('admits a mod that starts no process', { plugins: [reader] }, async ($, on) => {
  on('tool.call', () => ({ result: 'claude code answered' }))
  const out = await $.tool.call({ tool: 'Bash', command: 'ls' })
  // The answer comes from reader, which shows that it loaded
  expect(out).toEqual({ result: 'reader answered' })
})
```

在您的 shell 中，從 `acme-guard` 目錄執行 `claude plugin test`。當策略 mod 如管理頁面所示時，兩個測試都通過。

該套件在測試首次呼叫 `$` 時載入每個 mod。當您的 mod 拒絕一個時，該呼叫會拋出，消息會命名被拒絕的 mod、拒絕它的 mod 和您的原因。在第二個測試中，沒有任何內容被拒絕，因此 `reader` 在到達 stub 之前回答工具呼叫。

## 後續步驟

* [Troubleshoot a mod](https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot.md)：找出為什麼 mod 在工作階段中不執行任何操作
* [Mods reference](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md)：每個事件的輸入和結果，用於編寫 stubs

<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/plugins/mods/create | lastmod: 2026-10-25 | section: Plugins / Mods -->
> 來源：https://code.claude.com/docs/zh-TW/plugins/mods/create（官方 zh-TW，lastmod 2026-10-25）｜分類：Plugins › Mods｜EN 摘要：Have Claude write a Claude Code mod from a description, or write one yourself that counts tool calls and adds a command. Learn the reload and validate loop.

# 建立 mod

> 讓 Claude 從描述中寫出 Claude Code mod，或自己寫一個來計算工具呼叫並新增命令。學習重新載入和驗證迴圈。

Mod 是一個 Claude Code [外掛](https://code.claude.com/docs/zh-TW/plugins/overview.md)，具有一個進入檔案，稱為 hooks module：一個 JavaScript 或 TypeScript 檔案，其函數在事件發生時由 Claude Code 呼叫。若要建立 mod：

* **要求 Claude 寫它**：在 Claude Code 工作階段中[描述你想要的](#ask-claude-for-a-mod)
* **自己寫**：[按照教學](#write-a-mod-yourself)學習 mod 程式碼的運作方式。你不需要 Node.js、bundler 或建置步驟，因為 Claude Code 直接載入 `.js` 和 `.ts` 檔案。

如果你還沒決定 mod 是否是正確的工具，請先閱讀[概述上的比較](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md#compare-mods-settings-hooks-skills-and-mcp-servers)。

> [!NOTE]
>
> 請使用 Claude Code v2.1.287 或更新版本。在您的 shell 中，執行 `claude --version` 來檢查。若要查看 mod 是否可以為您載入，請參閱[檢查 mod 是否可以載入](https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot.md#check-whether-mods-can-load)。

## 要求 Claude 寫 mod

在互動式 Claude Code 工作階段中描述你想要的 mod，Claude 會寫出來。Claude 使用名為 `plugin-authoring` 的內建 [skill](https://code.claude.com/docs/zh-TW/skills.md)，它告訴 Claude 在哪裡寫 mod、你的版本有哪些事件和方法，以及 mod 如何被載入。當你要求 mod 時，Claude 可以載入該 skill，或者你可以在 Claude Code 提示符處執行 `/plugin-authoring` 來自己載入它。

mod 在你批准後執行，除了在[mod Claude 寫的無法載入的工作階段](#sessions-that-skip-the-approval)中。

**1. 描述 mod**

用你自己的話要求 mod，例如 `make a mod that shows the current git branch above the prompt`。Claude 在工作階段的 mod 資料夾中的自己的目錄中寫 mod，該資料夾是 `~/.claude/dev-mods/` 後跟工作階段的 ID。mod 的完整路徑看起來像 `~/.claude/dev-mods/3f2a9c1e-5b7d-4e8a-9c21-6d0f4b8a7e13/git-branch/`。

> [!NOTE]
>
> 在 `default` 和 `acceptEdits` [權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md)中，Claude Code 會在 Claude 建立 mod 的每個檔案之前請您批准，因為 mod 資料夾是[受保護的路徑](https://code.claude.com/docs/zh-TW/permission-modes.md#protected-paths)。請在每個檔案出現時逐一批准。

**2. 批准 mod**

當 Claude 儲存第一個檔案時，Claude Code 詢問是否為工作階段啟用熱重新載入。熱重新載入執行此工作階段中 Claude 寫的 mod，並在每個稍後變更它們的轉向結束時選擇每個變更。

選擇以下其中一個答案：

* **為此工作階段啟用**：工作階段的 mod 資料夾中的 mod 在轉向結束時載入，並在每個變更它們的轉向結束時重新載入。你的答案在工作階段期間持續，包括在你恢復它之後。
* **暫時不要**：現在什麼都不載入。檔案保留在 Claude 寫的地方，mod 在該工作階段下次啟動時載入。若要防止 mod 永遠載入，請刪除其目錄。

**3. 檢查 mod 是否已載入**

在 Claude Code 提示符處執行 `/plugin`，然後按 Tab 直到選擇**已安裝**標籤。它列出 mod，你可以在那裡關閉它。

**4. 試試 mod**

使用您所要求的功能。以範例提示詞而言，目前的分支名稱會出現在提示詞輸入框上方。如果 mod 沒有達到您想要的效果，請告訴 Claude 要修改什麼。mod 會在每個變更其檔案的回合結束時重新載入，因此您可以在 Claude 完成後立即試用變更。

如果逐字稿中有一行以 mod 名稱開頭，並指出[變更未能載入](https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot.md#this-mods-change-didnt-load)，請在下一則訊息要求 Claude 修正時貼上該行。除非您貼上，否則 Claude 看不到該行。

### 在其他工作階段中使用 mod

Claude 寫的 mod 只在建立它的工作階段中載入，Claude Code 在該工作階段的 mod 資料夾比 [`cleanupPeriodDays`](https://code.claude.com/docs/zh-TW/settings-reference#cleanupperioddays) 更舊後刪除它。若要保留 mod，將其目錄複製出 mod 資料夾到你自己的地方，例如 `~/mods/git-branch`。然後選擇如何載入它：

* **在你啟動的工作階段中**：在你的 shell 中，執行 `claude --plugin-dir ~/mods/git-branch`
* **對於其他人**：[將其新增到市場](#share-your-mod)，以便他們可以安裝它

### Claude 寫的 mod 無法載入的工作階段

Claude 寫的 mod 只在你批准後載入，在允許 mod 執行的受信任工作區中。在這些工作階段中它不會載入：

* **沒有人在那裡批准**：工作階段無法向你顯示提示，如在 `claude -p` 執行或 [`dontAsk` mode](https://code.claude.com/docs/zh-TW/permission-modes) 中
* **工作區不受信任**：你還沒有接受目錄的信任提示
* **Mod 已停用**：您以 `--safe-mode` 或 `--bare` 啟動、設定了 `disableAllHooks`，或您組織的[受管設定封鎖了它](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md#choose-how-much-to-allow)

## 自己寫 mod

在本教學中，你建立一個名為 `first-mod` 的 mod，它計算 Claude 進行的工具呼叫，在 Claude 工作時在微調器旁邊顯示計數，並新增一個 `/tally` 命令來列印它。然後你讀取 Claude Code 在 mod 旁邊寫的型別宣告，並執行 `claude plugin validate`。它們一起向你展示你的版本提供的事件和方法，以及 Claude Code 從你的程式碼中讀取的內容。

此錄製顯示完成的 mod。微調器計算工具呼叫，`/tally` 列印計數，程式碼的編輯在工作階段執行時生效：

<video autoPlay muted loop playsInline controls src="https://mintcdn.com/claude-code/dgiVO_Od1X1faduV/images/mods-first-mod-light.mp4?fit=max&auto=format&n=dgiVO_Od1X1faduV&q=85&s=eb561134afa90375777408453ba51c77" aria-label="In a Claude Code session, the prompt 'list the files here and read the README' is typed and sent. The spinner reads 'Thinking · tool calls: 1' and the count rises as Claude works. The /tally command prints 'first-mod: Claude has made 3 tool calls since this mod loaded'. A line says first-mod reloaded and lists its four hooks. On the next prompt the spinner reads 'Thinking · tools used: 1'." />

你寫三個檔案：

```text theme={null}
first-mod/
├── .claude-plugin/
│   └── plugin.json
└── hooks/
    ├── hooks.json
    └── register.js
```

* **`plugin.json`**：plugin 的[清單](https://code.claude.com/docs/zh-TW/plugins/manifest-reference.md)
* **`hooks.json`**：[指向你的程式碼檔案](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#files)
* **`register.js`**：你的程式碼，稱為 hooks module

**1. 建立 plugin 目錄**

建立保存檔案的兩個目錄：

> [tab] Bash or Zsh
>
> ```bash theme={null}
> mkdir -p first-mod/.claude-plugin first-mod/hooks
> ```

> [tab] PowerShell
>
> ```powershell theme={null}
> New-Item -ItemType Directory -Force first-mod\.claude-plugin, first-mod\hooks
> ```

**2. 寫清單**

Mod 是一個 plugin，mod 需要一個[清單](https://code.claude.com/docs/zh-TW/plugins/manifest-reference.md)。此 mod 的清單沒有特殊欄位。將此儲存為 `first-mod/.claude-plugin/plugin.json`：

```json first-mod/.claude-plugin/plugin.json theme={null}
{
  "name": "first-mod",
  "version": "0.1.0",
  "description": "Counts Claude's tool calls, shows the count beside the spinner, and adds a /tally command",
  "author": { "name": "Your Name" }
}
```

**3. 告訴 Claude Code 你的程式碼在哪裡**

當 Claude Code 載入 plugin 時，它讀取 plugin 的 `hooks/hooks.json`。該檔案中的 `modules` 鍵給出你的程式碼的路徑，擁有它是使 plugin 成為 mod 的原因。列出一個路徑，相對於 `hooks.json`。這裡它指向 `register.js`，你在下一步中寫它。

將此儲存為 `first-mod/hooks/hooks.json`：

```json first-mod/hooks/hooks.json theme={null}
{
  "description": "The first-mod hooks module",
  "modules": ["./register.js"]
}
```

**4. 寫程式碼**

此檔案是 mod 的程式碼，稱為 hooks module。當 mod 載入時，Claude Code 呼叫檔案匯出的 `register` 函數，並傳遞一個名為 [`on`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#the-hook-function) 的函數。每次呼叫 `on` 都會為它命名的事件註冊一個事件處理程式，稱為 hook。

將此儲存為 `first-mod/hooks/register.js`：

```javascript first-mod/hooks/register.js theme={null}
// The count, shared by the hooks below
let calls = 0

// Claude Code calls this once when the mod loads
export function register(on) {
  // Runs when the session starts, before your first prompt
  on('session.start', async ($, e, next) => {
    // Add the /tally command
    await $.command.register({
      name: 'tally',
      description: 'Show how many tool calls Claude has made',
    })
    // Let the session start as usual
    return next(e)
  })

  // Runs each time Claude is about to use a tool
  on('tool.call', async ($, e, next) => {
    calls += 1
    // Ask Claude Code to draw the interface again, so the new count shows
    $.ui.invalidate('ui.render')
    // Let the tool run as usual
    return next(e)
  })

  // Runs when you type /tally, and only then, because of the matcher
  on('command.run', { command: 'tally' }, async () => {
    // The text to print in the transcript
    return { text: 'Claude has made ' + calls + ' tool calls since this mod loaded' }
  })

  // Runs each time Claude Code draws the spinner
  on('ui.render', { component: 'Spinner' }, async ($, e, next) => {
    // Keep Claude Code's spinner, with the count added after its word
    return next({ ...e, props: { ...e.props, suffix: ' · tool calls: ' + calls + '…' } })
  })
}
```

檔案在 `calls` 中保留計數，並註冊四個 hook：

* **[`session.start`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#session)** 在工作階段啟動時執行，在你的第一個提示之前，以及每次 mod 重新載入時。它將 `/tally` 命令新增到 Claude Code。
* **[`tool.call`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#tools)** 每次 Claude 即將使用工具時執行。它將一個加到 `calls` 並要求 Claude Code 再次繪製介面。
* **[`command.run`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#commands-and-configuration)** 當你輸入 `/tally` 時執行。它返回要列印的文字。
* **[`ui.render`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#interface)** 每次 Claude Code 繪製微調器時執行。它在微調器的單詞後新增計數。

[範例 mod 如何運作](#how-the-example-mod-works)解釋了每個 hook 採用的三個引數以及每個引數返回的內容。

**5. 載入 mod**

使用 `--plugin-dir` 旗標啟動 Claude Code，它為一個工作階段載入 plugin 目錄而不安裝它：

```bash theme={null}
claude --plugin-dir ./first-mod
```

**6. 試試 mod**

要求 Claude 做一些需要幾個工具呼叫的事情，例如 `list the files here and read the README`。當 Claude 工作時，微調器的單詞後跟一個上升的計數，如 `Thinking · tool calls: 2…`。當 Claude 完成時，輸入 `/tally` 並按 Enter。文字記錄顯示 `first-mod: Claude has made 2 tool calls since this mod loaded`，帶有你自己的計數。Claude Code 將 plugin 的名稱放在命令的文字前面。

若要在非互動模式下檢查命令，請執行它：

```bash theme={null}
claude -p "/tally" --plugin-dir ./first-mod
```

```text theme={null}
first-mod: Claude has made 0 tool calls since this mod loaded
```

如果 `/tally` 不在命令列表中，模組沒有載入。請參閱[找出為什麼 mod 什麼都不做](https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot.md#find-out-why-a-mod-does-nothing)。

**7. 在工作階段執行時變更程式碼**

保持工作階段開啟。在 `register.js` 中，在 `ui.render` hook 中將 `' · tool calls: '` 變更為 `' · tools used: '` 並儲存。突出顯示的行是變更的行：

```javascript first-mod/hooks/register.js {4} theme={null}
  // Runs each time Claude Code draws the spinner
  on('ui.render', { component: 'Spinner' }, async ($, e, next) => {
    // Keep Claude Code's spinner, with the count added after its word
    return next({ ...e, props: { ...e.props, suffix: ' · tools used: ' + calls + '…' } })
  })
```

文字記錄中的一行說 `first-mod` 重新載入並列出其 hook，下一個微調器使用新文字，如 `Thinking · tools used: 1…`。

### 範例 mod 如何運作

你傳遞給 `on` 的每個函數都是一個 hook，這是一個事件處理程式。Claude Code 將相同的三個引數傳遞給每個 hook：

* **Mod API**，名為 `$`：mod 可以呼叫以到達自身外部的每個方法，在[命名空間](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#mods-api-methods)中，例如 `$.ui` 和 `$.command`
* **事件**，名為 `e`：[事件的輸入](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#events)作為純資料，例如工具呼叫的名稱和引數
* **下一個處理程式**，名為 [`next`](https://code.claude.com/docs/zh-TW/plugins/mods/events#how-a-hook-handles-an-event)：一個函數，將事件傳遞給其他 mod，然後傳遞給 Claude Code 自己的行為，並返回結果

`first-mod` 中的 hook 以下列方式處理其事件：

* **觀察**：`session.start` hook 註冊命令，`tool.call` hook 計算呼叫並要求重新繪製。兩者都返回 `next(e)`，所以工作階段啟動，工具照常執行。
* **回答**：`command.run` hook 返回自己的結果，永遠不呼叫 `next`。`on` 的第二個引數 `{ command: 'tally' }` 是一個篩選器，稱為[匹配器](https://code.claude.com/docs/zh-TW/plugins/mods/events.md#filter-which-events-a-hook-handles)，所以 hook 只對 `/tally` 執行。
* **重寫**：`ui.render` hook 呼叫 `next` 並複製 `e`，其 `suffix` 保留計數，所以 Claude Code 繪製其通常的微調器，你的文字在單詞後面

Claude Code 會監看使用 `--plugin-dir` 載入的目錄，並在其中的檔案變更時熱重新載入 hooks module。每次重新載入都會再次執行 `register`，因此 `calls` 會重設為 `0`，`/tally` 會重新開始計數。若要在重新載入之間保留值，請參閱[保留狀態](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md#keep-state)。

## 繼續處理 mod

一旦 mod 載入，你可以讓 Claude 變更它，根據你版本的型別定義檢查你的程式碼，列出 Claude Code 在其中找到的事件和呼叫，並測試它。

### 使用 Claude 變更 mod

若要變更你已經有的 mod，使用 `--plugin-dir` 指向 mod 的目錄啟動工作階段，以便 Claude 寫的內容在同一工作階段中載入：

```bash theme={null}
claude --plugin-dir ./first-mod
```

然後要求變更，例如 `add a /tally-reset command to this mod that sets the tally back to zero`。Claude 編輯 hooks module，執行 `claude plugin validate`，並修復它報告的內容。你使用 `--plugin-dir` 載入的目錄是[受保護的路徑](https://code.claude.com/docs/zh-TW/permission-modes.md#protected-paths)，所以在 `default` 和 `acceptEdits` 模式中，你被要求批准 Claude 對 mod 的每個編輯。受保護的路徑表給出其他 permission 模式的結果。

Claude 在其轉向期間儲存的檔案在轉向結束時重新載入，所以你可以在 Claude 完成後立即試試 `/tally-reset`。

### 取得你版本的型別定義

當 Claude Code 在互動式工作階段中從 `--plugin-dir` 載入 mod，或載入 [Claude 為您撰寫的](#ask-claude-for-a-mod) mod 時，它會將 TypeScript 宣告檔案寫入 mod 的 `.claude-plugin/types/` 目錄。這些檔案描述您所執行的 Claude Code 版本中確切的事件、mods API 方法和元素，讓您的編輯器可以對您的 hook 進行自動完成和型別檢查。該目錄包含以下檔案：

| 路徑 | 它宣告的內容 |
| :- | :- |
| `claude-code/index.d.ts` | 每個事件及其輸入和結果、每個 mod API 命名空間和方法，以及每個表面可以繪製的元素 |
| `claude-code-tools/index.d.ts` | 內建工具的輸入和結果，以便檢查 `e.tool === 'Bash'` 縮小 `e` |
| `claude-code-mcp/index.d.ts` | 上次你在 mod 中儲存檔案時連接的 MCP 工具的輸入 |
| 以 plugin 命名的目錄中的 `index.d.ts` | 該 plugin 新增到 mod API 的內容。你的 `plugin.json` 在 `dependencies` 下列出的每個 plugin 都有一個目錄。 |
| `tsconfig.json` | 適合 hooks module 的編譯器選項 |

如果你的 mod 沒有自己的 `tsconfig.json`，Claude Code 在 mod 的根目錄新增一個，擴展生成的，所以你的編輯器和 `tsc -p ./first-mod` 型別檢查 mod 而無需更多設定。

事件和方法可以在版本之間變更，所以當它們不同意時，信任這些檔案而不是任何頁面，包括這個。

`claude-code/index.d.ts` 是你的建置的最完整參考，每個 mod API 方法都有註解和範例。若要查找某些內容，在檔案中搜尋其名稱，例如 `'tool.call'`。

### 檢查 Claude Code 從你的 mod 讀取的內容

若要看到 Claude Code 看到的 mod 的方式，而不執行你的程式碼或啟動工作階段，請使用 `claude plugin validate`。它檢查清單，並在 hooks module 的來源上執行相同的靜態分析，Claude Code 在載入 mod 時執行。在你的 shell 中，在 mod 的目錄上執行它：

```bash theme={null}
claude plugin validate ./first-mod
```

對於 `first-mod`，輸出包括這些行。

```text theme={null}
  ❯ ./register.js hooks: session.start, tool.call, command.run{command=tally}, ui.render{component=Spinner}
  ❯ ./register.js calls: $.command.register, $.ui.invalidate

✔ Validation passed
```

請查看 `hooks:` 行，確認您的模組 hook 的事件，每個事件的篩選器都列在大括號中；並查看 `calls:` 行，確認它呼叫的每個 mod API 方法。如果您的模組會讀取或設定環境變數，也請留意 `env reads:` 和 `env writes:` 行；若使用了 [`$.state`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#keep-state)，則請留意 `state reads:` 和 `state writes:`。對於每個可以拒絕動作的 hook，您也會看到一行，例如 `gating hook without .catch: tool.call`，說明該 hook 是否具有 [`.catch` 處理常式](https://code.claude.com/docs/zh-TW/plugins/mods/events#handle-a-hook-that-fails)。

如果您想處理的事件沒有出現在第一行中，Claude Code 也不會呼叫該 hook。常見原因是事件名稱拼寫錯誤，命令會將其回報為錯誤，例如 `"tool.calls" is not an event`。

遵循這些規則，以便靜態分析可以找到每個 hook 和呼叫：

* 完整寫出每個 mods API 呼叫：`$`、命名空間，然後是方法，如 `$.store.get('notes')`。您可以將 `$` 傳遞給在同一檔案頂層宣告的函式；若您的函式名為 `loadNotes`，`calls:` 行就會顯示 `$.store.get (via loadNotes)`。將 `$` 傳遞給方法、在 hook 內定義的函式，或您從自己的另一個檔案匯入的函式，都會導致驗證失敗。[`$.state`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#keep-state) 使用的 `read` 和 `update` 函式是可以接收它的匯入。不要將 `$` 或其命名空間之一指派給變數、對其解構，或以計算名稱對其進行索引。`const ui = $.ui` 會失敗，並出現 `$.ui is used as a value`。
* 在每個 `on` 呼叫中將事件名稱寫為字串文字，例如 `'tool.call'`。變數或名稱列表上的迴圈失敗，出現 `the event name passed to on() is not a string literal`。
* 在 `register` 內，不要宣告名為 `on` 的第二個變數或引數。驗證失敗，出現 `"on" is declared again (shadowed)`。
* 僅從 plugin 目錄內的檔案匯入，按相對路徑。允許的唯一裸匯入是 `claude-code`，用於型別和一些幫助程式。
* 在檔案頂部使用 `import` 宣告，如 `import { name } from './file.js'`。動態 `import()` 失敗，出現 `a dynamic import(); a hooks module imports its own files with an import declaration`。
* 將每個檔案寫為 ES 模組，使用 `import` 而不是 `require`。[參考](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#files)列出 Claude Code 載入的檔案副檔名。

### 測試 mod

您可以為 mod 撰寫自動化測試，並使用 `claude plugin test` 從您的 shell 執行，無需工作階段、登入或網路。測試會觸發您的 hook 處理的事件，並檢查 hook 做了什麼。

此測試觸發兩個工具呼叫、執行 `/tally`，並檢查回覆是否計入兩者。將其儲存為 `first-mod/tests/first-mod.test.ts`：

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

在你的 shell 中，從 `first-mod` 目錄執行測試：

```bash theme={null}
claude plugin test
```

輸出命名每個測試及其是否通過，時間從執行到執行變化：

```text theme={null}
tests/first-mod.test.ts:
(pass) /tally reports the tool calls the mod has seen [22.87ms]

 1 pass
 0 fail
Ran 1 test across 1 file. [0.19s]
```

[測試 mod](https://code.claude.com/docs/zh-TW/plugins/mods/test.md)涵蓋模擬模型呼叫或存放區，以及測試計時器和繪製。

## 分享你的 mod

mod 就是一個外掛，因此您在清單中為其設定版本，其他人則使用 `/plugin` 命令來安裝和更新它。分享方式取決於對象：

* **少數幾個人**：將外掛的目錄或其 `.zip` 檔案傳送給對方。請參閱[不透過市集分享外掛](https://code.claude.com/docs/zh-TW/plugins/publish.md#share-a-plugin-without-a-marketplace)
* **您的團隊**：將其列在[您自己的市集](https://code.claude.com/docs/zh-TW/plugins/publish.md#publish-through-your-own-marketplace)中，例如每個外掛各有一個目錄的私人儲存庫。若要為在某個儲存庫中工作的所有人新增該市集，請[在儲存庫的設定中註冊它](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md#register-the-marketplace-for-everyone-in-a-repository)
* **您的整個組織**：管理員可以透過受管設定[安裝您組織的 mod](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md#install-your-organizations-mods)
* **任何人**：將您市集的儲存庫設為公開，或[將外掛提交至 Anthropic 的目錄](https://code.claude.com/docs/zh-TW/plugins/publish.md#submit-to-anthropics-directory)

在你這樣做之前，檢查 plugin 的 `name`：`claude plugin validate` 失敗一個[看起來像 Anthropic 自己的](https://code.claude.com/docs/zh-TW/plugins/manifest-reference.md#name)名稱，例如以 `claude-` 開頭的名稱。事件和方法可以在版本之間變更，所以你的 README 是說明你測試的 Claude Code 版本的地方。

請使用 `--plugin-dir` 針對目錄繼續開發，而不是針對已安裝的副本。Claude Code 會按版本快取已安裝的外掛，因此在您提高版本並再次安裝之前，您的編輯不會反映到已安裝的副本。

## 後續步驟

* [在介面中繪製](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md)：開啟窗格、在提示上方繪製，以及新增按鈕和文字欄位
* [對事件做出反應](https://code.claude.com/docs/zh-TW/plugins/mods/events.md)：hook 工具呼叫、提示和轉向
* [使用 mod API](https://code.claude.com/docs/zh-TW/plugins/mods/api.md)：新增命令和工具、呼叫模型，以及在計時器上執行工作
* [測試 mod](https://code.claude.com/docs/zh-TW/plugins/mods/test.md)：模擬 Claude Code 會回答的內容，以及測試計時器和繪製
* [對 mod 進行故障排除](https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot.md)：mod 什麼都不做的原因，以及偵錯日誌
* [讀取內建 mod 的來源](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md#read-the-source-of-built-in-mods)：完整的 plugin，每個都有其 hooks module 和測試

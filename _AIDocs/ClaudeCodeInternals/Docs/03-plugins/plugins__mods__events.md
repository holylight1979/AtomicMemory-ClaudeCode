<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/plugins/mods/events | lastmod: 2026-10-27 | section: Plugins / Mods -->
> 來源：https://code.claude.com/docs/zh-TW/plugins/mods/events（官方 zh-TW，lastmod 2026-10-27）｜分類：Plugins › Mods｜EN 摘要：Handle Claude Code events from a mod: observe, rewrite, or answer tool calls, prompts, and turns, filter which events a hook handles, and plan for other mods.

# 使用 mod 回應事件

> 從 mod 處理 Claude Code 事件：觀察、重寫或回答工具呼叫、提示和回合，篩選 hook 處理哪些事件，並為其他 mod 進行規劃。

hook 是一個事件處理程式：一個函式，Claude Code 在命名事件發生時執行。Claude Code 在每個即將採取行動的地方觸發事件，例如當它執行工具、提交提示、向模型發送請求或啟動或結束工作階段時。您的 hook 在 Claude Code 採取行動之前執行，因此它可以觀察事件、重寫事件或代替 Claude Code 回答事件。您使用 [`on(eventName, handler)`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#the-hook-function) 註冊 hook。

在開始之前，請先建立您的[第一個 mod](https://code.claude.com/docs/zh-TW/plugins/mods/create.md)。對於每個事件及其確切欄位，請參閱[參考資料](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#events)或閱讀[您的建置類型](https://code.claude.com/docs/zh-TW/plugins/mods/create.md#get-the-types-for-your-build)。

## hook 如何處理事件

hook 位於事件和 Claude Code 對其採取的行動之間，因此它可以觀察事件、重寫事件或自己回答事件。它接收三個引數：[mods API](https://code.claude.com/docs/zh-TW/plugins/mods/api.md) 作為 `$`、事件作為 `e`，以及下一個處理程式作為 `next`。事件的處理程式形成中介軟體鏈。`next(e)` 呼叫下一個處理程式，這是另一個 mod 的 hook 或在鏈的末端是 Claude Code 自己的行為，它解析為結果。您的 hook 對 `next` 的處理決定了它執行以下三項中的哪一項。

### 觀察事件

若要觀察事件而不改變它，請執行您的工作並傳回 `next(e)`。此 hook 記錄 Claude 即將使用的每個工具：

```javascript theme={null}
on('tool.call', async ($, e, next) => {
  // 在工具執行之前執行
  $.ui.log('Claude is about to use ' + e.tool)
  // 將事件原封不動地傳遞
  return next(e)
})
```

在每個工具執行之前，會在文字記錄中出現一行暗淡的行，例如 `● my-mod: Claude is about to use Bash`，其中 `my-mod` 是您的外掛程式名稱。工具的執行方式與沒有 mod 時相同。

若要在事件後採取行動，請 `await next(e)`、執行您的工作，然後傳回結果。此 hook 在每個工具執行後記錄它：

```javascript theme={null}
on('tool.call', async ($, e, next) => {
  // 讓工具執行，並等待其結果
  const result = await next(e)
  // 在工具執行後執行
  $.ui.log(e.tool + ' finished')
  // 將結果原封不動地傳回
  return result
})
```

該行現在出現在每個工具完成後。Claude 讀取相同的結果，因為 hook 傳回 `next(e)` 解析的內容。

### 重寫事件

若要變更 Claude Code 作用的內容，例如提示詞的文字，請使用修改後的事件副本呼叫 `next`。事件本身是不可變的：它在每個深度都被凍結，分配給欄位會擲回。此 hook 在傳送前修剪每個提示詞：

```javascript theme={null}
on('prompt.submit', async ($, e, next) => {
  // 傳遞事件的副本，其文字已變更
  return next({ ...e, text: e.text.trim() })
})
```

稍後的處理程式和 Claude Code 會收到修剪後的提示，永遠看不到原始提示。您也可以變更結果：`await next(e)`，然後傳回結果的副本，其中欄位已替換。

### 回答事件

若要自己處理事件，請傳回結果而不呼叫 `next`。這會短路鏈，因此稍後的 mod 和 Claude Code 自己的行為不會執行。此 hook 拒絕每個 Bash 命令：

```javascript theme={null}
on('tool.call', { tool: 'Bash' }, async () => {
  // 沒有呼叫 next，所以命令永遠不會執行
  return { deny: 'Bash is turned off in this project. Use the file tools.' }
})
```

當 Claude 嘗試 Bash 命令時，命令不會執行，Claude 會將 `deny` 文字讀取為工具的結果。每個事件都有自己的結果形狀，[事件參考資料](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#events)會列出。

### 篩選 hook 處理哪些事件

若要僅針對某些事件執行 hook，請將篩選器作為第二個引數傳遞給 `on`。Claude Code 將篩選器稱為 matcher。它是一個物件，其欄位與事件的欄位進行比較，只有當每個欄位都符合時，hook 才會執行。欄位可以是值、允許值的陣列或正規表達式。

此範例中的每一行都為較窄的工具呼叫集合註冊相同的函式 `hook`：

```javascript theme={null}
// 字串符合一個值：僅限 Bash 呼叫
on('tool.call', { tool: 'Bash' }, hook)
// 陣列符合其中任何值：Edit 呼叫和 Write 呼叫
on('tool.call', { tool: ['Edit', 'Write'] }, hook)
// 正規表達式按模式符合：一個 MCP 伺服器的每個工具
on('tool.call', { tool: /^mcp__github__/ }, hook)
```

`hook` 針對 Bash、Edit 或 Write 呼叫執行一次，並針對名稱以 `mcp__github__` 開頭的工具呼叫執行一次。對任何其他工具（例如 Read）的呼叫不符合這三個中的任何一個，因此 `hook` 不會針對它執行。

事件名稱可以是萬用字元。`'classic.*'` 符合每個[設定 hook 事件](#hook-the-settings-hook-events)。`'*'` 符合除[遙測事件](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#telemetry)之外的每個事件，遙測事件需使用其自身的名稱以及 `{ to: 'collector' }` 篩選器。

為每個 matcher 註冊一次事件。如果您為 `session.start` 呼叫 `on` 兩次而沒有 matcher，模組將無法載入，並出現 `on("session.start") is registered twice without a matcher`。將您的 mod 在工作階段開始時執行的所有操作放在一個 hook 中。

## 對 Claude 正在執行的動作設定 hook

處理這些事件，即可在工具呼叫、提示詞、回合或設定讀取發生時檢視或變更它們。如需所有事件以及 hook 可傳回的內容，請參閱[事件參考](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#events)。

### 防護或變更工具呼叫

`tool.call` hook 會看到 Claude 即將使用的每個工具，因此可以拒絕該呼叫、變更其引數，或讓它通過。`tool.call` 會在 Claude Code 即將執行工具時觸發，包括 subagent 發出的呼叫以及對 MCP 工具的呼叫。`e.tool` 是工具的名稱，而工具的引數則是 `e` 的欄位，例如 Bash 的 `e.command`。當您呼叫 `next(e)` 時，Claude Code 會執行權限檢查，然後執行工具。

此 hook 會拒絕執行 force push 的 Bash 命令，並告訴 Claude 原因：

```javascript theme={null}
// The matcher limits the hook to Bash calls, so e.command is the shell command
on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
  if (/git push .*--force/.test(e.command)) {
    // Returning without calling next answers the event, so the command never runs
    return { deny: 'Force pushes are not allowed in this repository. Push to a new branch instead.' }
  }
  // Every other command goes on to the permission check and then to Bash
  return next(e)
})
```

當 Claude 嘗試執行 `git push --force` 時，命令不會執行，也不會出現權限提示，因為 hook 從未呼叫 `next`。Claude 會將 `deny` 文字當作工具的結果來讀取，因此請將其撰寫為 Claude 可據以行動的指令。其他所有 Bash 命令的執行方式都與沒有 mod 時相同。

如果此 hook 擲出例外或逾時，Claude Code 會略過它，而命令會如同沒有 mod 時一樣繼續執行。若要改為拒絕該命令，請為此 hook [加入 `.catch` 處理常式](#handle-a-hook-that-fails)。

若要在工具執行後採取動作，請 `await next(e)`、執行您的工作，然後傳回 `next` 給您的內容。此 hook 會使用 [`$.ui.log`](https://code.claude.com/docs/zh-TW/plugins/mods/api#show-something-without-starting-a-turn) 記錄 Claude 變更的每個 `.mdx` 檔案，該函式會在逐字稿中加入一行 Claude 不會讀取的淡色文字：

```javascript theme={null}
on('tool.call', { tool: ['Edit', 'Write'] }, async ($, e, next) => {
  // Wait for the permission check and the tool, and keep what they produced
  const result = await next(e)
  // A refused call comes back as { deny }, and a failed one has isError set
  const changed = !result.deny && !result.isError
  if (changed && e.file_path.endsWith('.mdx')) $.ui.log('Claude changed ' + e.file_path)
  // Return the result as it came, so Claude reads what the tool returned
  return result
})
```

在 Claude 編輯或寫入 `.mdx` 檔案後，逐字稿中會出現一行淡色文字，標示該檔案名稱。對於其他類型的檔案，或是遭拒絕或失敗的呼叫，則不會記錄任何內容。Claude 對該呼叫的認知不會改變，因為 hook 傳回的是它所收到的結果。

您的 hook 也可以變更呼叫、重試呼叫、自行回應呼叫，或隱藏其結果：

* **變更呼叫**：將變更後的引數傳給 `next`。
* **重試呼叫**：再次呼叫 `next(e)`。在第一個結果上看到 `isError` 的 hook 可以再次執行工具，並傳回該結果。
* **自行回應呼叫**：在不呼叫 `next` 的情況下傳回具有 `result` 欄位的物件；若為內建工具，請讓 `result` 符合該工具本身的結果在[您建置版本的型別](https://code.claude.com/docs/zh-TW/plugins/mods/create.md#get-the-types-for-your-build)中的形狀。不會出現權限提示，工具也不會執行，因此您傳回的結果就是 Claude 對所發生事情的全部了解。
* **對 Claude 隱藏結果**：在 `await next(e)` 之後傳回 `{ deny: reason }`。Claude 會讀取您的原因，而非 `next` 傳回的內容。當工具已執行時，deny 會讓 Claude 看不到其結果，但不會復原工具所做的任何事。當工具已執行且成功時，原因會接在如 `Bash ran, and a plugin withheld its result:` 之類的註記之後。

您組織的[受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)中的 hook 會在任何 mod 的 `tool.call` hook 之前執行。當受管 hook 封鎖該呼叫時，任何 mod 的 `tool.call` hook 都不會針對該呼叫執行。

#### 暫停工具呼叫，直到使用者做出決定

hook 可以暫停工具呼叫，並在其繼續之前詢問使用者該怎麼做。`tool.call` hook 可以在呼叫 `next` 或傳回之前先 `await`，而工具呼叫會保持等待狀態直到那時。若要向使用者提出問題，請呼叫 `$.ui.ask`。它會在 Claude 用來詢問您的對話框中，於您的選項編號清單上方顯示您的問題，並解析為使用者所選的標籤。在您的選項之後，對話框會加入一列供輸入其他答案，以及一列 **Chat about this**。

此範例中的 `RISKY` 模式會比對 `rm -r`、`rm -rf`、`git reset --hard` 以及帶有 `--force` 的 `git push`，但會漏掉其他寫法，例如 `git push -f`。此模組會在執行符合該模式的 Bash 命令前先詢問：

```javascript theme={null}
const RISKY = /\brm\s+-rf?\b|\bgit\s+reset\s+--hard\b|\bgit\s+push\b.*--force/

export function register(on) {
  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    // Let every other command through without a question
    if (!RISKY.test(e.command)) return next(e)
    // Start from the safe answer, so a question nobody answers refuses the command
    let answer = 'Refuse'
    try {
      // The tool call waits here until the user picks one of the two labels
      answer = await $.ui.ask('Run this command? ' + e.command, ['Run it', 'Refuse'])
    } catch {
      // The user dismissed the question, or this is a claude -p run with nobody to ask
    }
    if (answer !== 'Run it') {
      // Answer without calling next, so the command doesn't run
      return { deny: 'The user declined this command. Ask before trying a different approach.' }
    }
    return next(e)
  })
}
```

當 Claude 嘗試執行如 `rm -rf build` 之類的命令時，會出現包含該命令的問題，而命令會等待答案：

* **使用者選擇 Run it**：hook 會呼叫 `next(e)`，之後一般的權限檢查仍會執行
* **使用者選擇 Refuse**：命令不會執行，Claude 會讀取 `deny` 文字
* **使用者輸入答案**：`$.ui.ask` 會解析為輸入的文字。hook 會將其與 `Run it` 比較，因此任何其他文字都會拒絕該命令。
* **沒有人回答**：當使用者關閉問題或選擇 **Chat about this** 時，以及在 `claude -p` 執行中，`$.ui.ask` 會拒絕（reject），因此 `catch` 區塊會讓答案維持為 `Refuse`

請將等待保留在如 `$.ui.ask` 之類的 mods API 呼叫中，因為這段時間不會計入 hook 的[時間限制](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#limits)。等待您自己的 promise 所花費的時間則會計入。

Claude Code 會略過逾時的 hook，因此被暫停的命令將會執行。若要改為拒絕該命令，請在 `on` 傳回的註冊上串接[一個 `.catch` 處理常式](#handle-a-hook-that-fails)。該處理常式與 hook 內部的 `catch` 區塊是分開的。

#### 在詢問使用者之前核准或拒絕工具呼叫

若要決定工具呼叫是否可以執行，請處理 [`tool.check`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#tools)，這是 Claude Code 做出該決定的事件。

對於固定的命令或路徑，請使用[權限規則](https://code.claude.com/docs/zh-TW/permissions.md#permission-rule-syntax)，例如 `Bash(npm test)`，不需要撰寫程式碼。當決定取決於當下的狀況時，例如目前的 Git 分支或另一個 hook 記錄的值，請處理 `tool.check`。

* **要傳回的內容**：若要自行決定該呼叫，請傳回您自己的物件，例如 `{ decision: 'allow' }` 或 `{ decision: 'deny', reason }`。若要保留原有的決定，請傳回 `await next(e)` 給您的內容。
* **`await next(e)` 給您的內容**：Claude Code 本身的決定，為一個 `decision` 為 `allow`、`ask` 或 `deny` 的物件。`next(e)` 執行期間不會出現權限提示。
* **引數**：`e.input` 保存工具的引數，例如 Bash 的 `command`
* **`tool.check` 觸發時機**：在 [`PreToolUse` hook](https://code.claude.com/docs/zh-TW/hooks#pretooluse) 執行之後，且在權限提示、[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)的分類器或 [`PermissionRequest`](https://code.claude.com/docs/zh-TW/hooks#permissionrequest) hook 之前

此 hook 會在目前分支為 `main` 時拒絕 `git push`：

```javascript theme={null}
on('tool.check', { tool: 'Bash' }, async ($, e, next) => {
  // Claude Code's own decision
  const decided = await next(e)
  if (!e.input.command.includes('git push')) return decided
  const branch = await $.process.run(['git', 'branch', '--show-current'])
  if (branch.stdout.trim() !== 'main') return decided
  return { decision: 'deny', reason: 'Push from a branch other than main' }
})
```

此 hook 會在 `main` 上拒絕 `git push`，並讓其他所有呼叫通過：

* **在 `main` 上**：即使有規則允許 `git push`，hook 仍會傳回 `deny`
* **在其他分支上，以及對於其他命令**：該呼叫會得到與沒有 mod 時相同的決定
* **hook 擲出例外或逾時**：該呼叫同樣會得到與沒有 mod 時相同的決定。若要改為拒絕該呼叫，請[加入一個 `.catch` 處理常式](#handle-a-hook-that-fails)，讓它傳回 `{ decision: 'deny', reason: 'the reason' }`。

此 hook 比對的是命令的文字，因此請將其視為給 Claude 的提醒。若要對所有人封鎖推送至 `main`，請在您的 Git 主機上保護該分支。

> [!NOTE]
>
> `tool.check` hook 也可以傳回 `allow` 或 `ask`。在 [plan mode](https://code.claude.com/docs/zh-TW/permissions.md#hook-approvals-in-plan-mode) 中，對於非唯讀的呼叫（例如檔案編輯），您的 hook 可以收緊 `next(e)` 傳回的決定，但無法放寬它。如需您的 hook 的 `allow` 無法取代的權限規則和 `PreToolUse` hook 決定，請參閱[使用 hook 擴充權限](https://code.claude.com/docs/zh-TW/permissions.md#precedence-among-rules-hooks-and-mods)。

#### 檢查工具呼叫是否為唯讀

在 [`tool.check`](#approve-or-refuse-a-tool-call-before-the-user-is-asked) hook 中，當工具回報該呼叫為唯讀時，`e.isReadOnly` 為 `true`。否則該欄位不存在，而非 `false`。`e.isReadOnly` 需要 Claude Code v2.1.304 或更新版本。

某些工具（例如 Read、Grep、Glob 和 WebSearch）會將每個呼叫都回報為唯讀。Bash 和 MCP 工具會在以下情況將呼叫回報為唯讀：

* **Bash**：命令通過 Claude Code 內建的[唯讀命令檢查](https://code.claude.com/docs/zh-TW/permissions.md#read-only-commands)
* **MCP 工具**：伺服器將該工具的 `readOnlyHint` 註解設為 `true`

此值是工具本身的回報，因此請勿僅憑此欄位就核准呼叫。例如，WebFetch 和 Agent 呼叫會回報為唯讀，但 [WebFetch](https://code.claude.com/docs/zh-TW/tools-reference.md#webfetch-tool-behavior) 會請求 URL，而 [Agent](https://code.claude.com/docs/zh-TW/tools-reference.md#agent-tool-behavior) 會啟動一個執行自己工具的 subagent。

此 hook 會針對每個非唯讀且尚未被拒絕的 `mcp__github__` 呼叫傳回 `ask`：

```javascript theme={null}
on('tool.check', { tool: /^mcp__github__/ }, async ($, e, next) => {
  const decided = await next(e)
  // Read-only calls and denied calls pass through unchanged
  if (e.isReadOnly || decided.decision === 'deny') return decided
  return { decision: 'ask', reason: 'This tool can change the GitHub repository' }
})
```

#### 依呼叫是否為唯讀篩選 `tool.check` hook

若要依 [`e.isReadOnly`](#check-whether-a-tool-call-is-read-only) 限制您的 hook 所處理的呼叫，請針對唯讀呼叫使用 [matcher](#filter-which-events-a-hook-handles)，其餘則在 hook 主體中處理：

* **僅限唯讀呼叫**：在 matcher 中加入 `isReadOnly: true`，例如 `on('tool.check', { tool: 'Bash', isReadOnly: true }, hook)`
* **非唯讀的呼叫**：在 hook 主體中測試 `e.isReadOnly`，如 [`mcp__github__` 範例](#check-whether-a-tool-call-is-read-only)所示。如果您在 matcher 中放入 `isReadOnly: false`，您的 hook 將永遠不會執行。

### 改寫或補充提示詞

`prompt.submit` hook 會在回合開始之前看到每個提示詞，因此可以改寫文字或加入內容。`e.text` 是輸入的內容。

| 若要執行此操作 | 請傳回 |
| :- | :- |
| 改寫提示詞。逐字稿和您的[提示詞歷史記錄](https://code.claude.com/docs/zh-TW/interactive-mode.md#command-history)會顯示新文字。 | `next({ ...e, text: newText })` |
| 在提示詞之後加入只有 Claude 會讀取的文字 | `next({ ...e, context: [...(e.context ?? []), extraText] })` |
| 阻止送出提示詞 | `{ drop: 'the reason' }` |

每當提示詞提及 pull request 時，此 hook 就會為 Claude 加入目前的分支名稱：

```javascript theme={null}
on('prompt.submit', async ($, e, next) => {
  // Pass on a prompt that doesn't mention a pull request as it is
  if (!/\bPR\b|pull request/i.test(e.text)) return next(e)
  const git = await $.process.run(['git', 'branch', '--show-current'])
  // Outside a git repository the command fails, so there's no branch to add
  if (git.exitCode !== 0) return next(e)
  // Keep any context an earlier hook added, and add one more line for Claude
  return next({ ...e, context: [...(e.context ?? []), 'Current branch: ' + git.stdout.trim()] })
})
```

當您送出如 `open a PR for this change` 之類的提示詞時，您的訊息在逐字稿中看起來不變，而 Claude 還會在其後讀到如 `Current branch: feature/auth` 之類的一行。未提及 pull request 的提示詞會原封不動地通過，且不會執行 `git`。

若要阻止提示詞，請在不呼叫 `next` 的情況下傳回 `{ drop: 'the reason' }`。文字會回到使用者的提示詞輸入欄中，而使用者會看到 `Prompt dropped by a hook:` 後接您的原因，因此請以使用者為對象撰寫原因。在以下情況中，提示詞仍會送出：

* **您的 hook 在其 `next(e)` 呼叫已讓提示詞通過之後才傳回 `drop`**：回合仍會執行，且該 hook 會[失敗](#handle-a-hook-that-fails)，並顯示包含 `a drop after its next() was answered` 的訊息
* **您的 hook 擲出例外或逾時**：Claude Code 會略過它並送出提示詞。請[加入 `.catch` 處理常式](#handle-a-hook-that-fails)，以免失敗時送出 hook 原本會阻止的提示詞。

[其他事件](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#prompts-and-what-claude-reads)涵蓋 Claude 讀取的其餘內容：`prompt.section` 用於系統提示詞的每個區段，`prompt.context` 用於隨第一則訊息送出的上下文，而 `skill.prompt` 用於 skill 的文字。來自這些 hook、且在請求之間有所變動的文字，會[使提示快取失效](https://code.claude.com/docs/zh-TW/prompt-caching.md)。在 `skill.prompt` hook 中，您也可以讀取[該 skill 來自哪個外掛或檔案](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#skill-prompt-fields)。

### 追蹤回合

回合是 Claude 為回應一個提示詞所做的一切。處理 `turn.start`、`turn.step` 和 `turn.complete` 即可追蹤回合：

| 事件 | 觸發時機 | hook 可以做什麼 |
| :- | :- | :- |
| `turn.start` | 回合開始時 | 觀察。`e.turnId` 會在另外兩個事件中識別該回合。 |
| `turn.step` | Claude Code 即將向模型送出一個請求時。包含工具呼叫的回合會有多個請求。subagent 的請求會設定 `e.agentId`。 | 讀取每個請求的 token 使用量、使用 `next({ ...e, model })` 將其送往不同的模型，或在不呼叫模型的情況下自行回應 |
| `turn.complete` | 回合結束時，包括使用者中斷的回合，此時 `e.isAborted` 為 `true`。`e.answer` 是 Claude 的最終文字，`e.durationMs` 是所花費的時間，`e.usage` 是該回合的 token 總數。subagent 的回合觸發此事件時會設定 `e.agentId`。 | 觀察，或傳回具有 `text` 欄位的物件（例如 `{ text: 'Done in 12 seconds' }`），以在答案下方顯示一行文字 |

請將 `turn.step` hook 撰寫為非同步產生器（async generator），因為此事件是串流的。`yield* next(e)` 會在串流時轉送回應，並求值為最終結果。此 hook 會記錄每個請求中有多少是由 Claude API 從[提示快取](https://code.claude.com/docs/zh-TW/prompt-caching.md)提供：

```javascript theme={null}
// function* makes the hook a generator, which can pass the response on piece by piece
on('turn.step', async function* ($, e, next) {
  // Send the request, forward each piece as it arrives, and keep the finished result
  const result = yield* next(e)
  // Skip a result that reports no token counts
  if (result.usage) {
    $.ui.log('cache read ' + result.usage.cache_read_input_tokens + ' · wrote ' + result.usage.cache_creation_input_tokens)
  }
  // Return the result unchanged, so the turn continues as usual
  return result
})
```

Claude 的回應會像沒有 mod 時一樣串流至畫面。每個請求完成後，逐字稿中會出現一行淡色文字，列出從快取讀取的 token 數量以及寫入快取的 token 數量。包含工具呼叫的回合會有多個請求，因此會加入多行。

`result.usage` 保存 Claude API 為請求回報的 token 計數，以及回應的 `model`：`input_tokens`、`output_tokens`、`cache_read_input_tokens` 和 `cache_creation_input_tokens`。此 hook 也會針對 subagent 的請求執行，因此若您只想要主要對話，請檢查 `e.agentId`。

若要查看 API 在請求期間自行執行的工具呼叫，例如對 [advisor 工具](https://code.claude.com/docs/zh-TW/advisor.md)的呼叫，請讀取 `result.serverToolUses`。Claude Code 不會執行這些呼叫，因此不會針對它們觸發任何 `tool.call` 或 `tool.check` hook。當回應中沒有此類呼叫時，該欄位不會存在，且此欄位需要 Claude Code v2.1.290 或更新版本。

#### 將請求送往不同的模型

如果 `turn.step` 請求在 `model` 為別名（例如 `haiku`）時因模型錯誤而失敗，請更新至 Claude Code v2.1.309 或更新版本，或使用完整的模型 ID。在 v2.1.309 之前，別名會按原樣送出。

若要將請求送往不同的模型，請將變更了 `model` 的事件傳給 `next`，例如 `yield* next({ ...e, model: 'haiku' })`。

### 變更或拒絕設定讀取

使用 `settings.read` hook 來變更或拒絕設定讀取，無論是 mod 的讀取還是 Claude Code 本身的讀取：

* **mod 的讀取**：mod 呼叫 [`$.settings.read`](https://code.claude.com/docs/zh-TW/plugins/mods/api#read-one-source-or-one-key)。
* **Claude Code 本身的讀取**：您的 hook 會在 Claude Code 合併工作階段的設定時首次執行，此時工作階段的 mod 已載入完成。當設定或已載入的外掛變更時，您的 hook 會再次執行。

請檢查哪些 mod 會收到此事件，以及您的 Claude Code 版本：

* **內建防護**：在有受管設定，或以 Team 或 Enterprise [`/login`](https://code.claude.com/docs/zh-TW/authentication#authentication-precedence) 作為工作階段的憑證時，[內建防護](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md#know-what-happens-by-default)可能會在您安裝或以 `--plugin-dir` 載入的 mod 中略過此 hook。若要檢查，請在[偵錯日誌](https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot.md#read-the-debug-log)中搜尋 `settings.read bypassed by cc-plugin-sec-default`。如果含有該文字的某一行指名了您的 mod，請要求您組織的管理員[將該 mod 安裝為組織的 mod 之一](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md#install-your-organizations-mods)。
* **版本**：此事件在 Claude Code 本身的讀取時觸發，以及 `e.layers` 欄位，需要 Claude Code v2.1.304 或更新版本。

#### `settings.read` hook 收到的內容

| 欄位 | 型別 | 保存的內容 |
| :- | :- | :- |
| `e.layers` | 陣列 | 每個使用中且保存設定的來源各一個 `{ source, settings }` 物件，依[優先順序](https://code.claude.com/docs/zh-TW/settings.md#settings-precedence)由低至高排列：`plugin`、`user`、`project`、`local`、`flag`、`policy`。在 `claude plugin test` 中為空。 |
| `e.source` | 字串 | mod 所要求的單一來源，例如 `$.settings.read({ source: 'policy' })`。此時 `e.layers` 只保存該層。在 Claude Code 本身的讀取以及任何其他合併設定的讀取中不存在。 |

在 `e.layers` 中，`plugin` 保存已啟用外掛所提供的設定，且僅為層名稱，而非可傳給 `$.settings.read` 的 `source`。`flag` 保存以 `--settings` 傳入的設定，`policy` 則保存受管設定。

#### 區分 Claude Code 本身的讀取與 mod 的讀取

請檢查 [`next.origin`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#the-hook-function)：

* **Claude Code 本身的讀取**：`{ plugin: 'engine', tier: 'core' }`
* **mod 的讀取**：`plugin` 為發出呼叫的 mod 名稱

#### `settings.read` hook 可傳回的內容

原封不動地傳回 [`next(e)`](#settings-read-next) 的結果即可維持讀取不變，或傳回下列其中一項：

| 傳回 | 在 [Claude Code 本身的讀取](#settings-read-hook)中 | 在 mod 的讀取中 |
| :- | :- | :- |
| `{ value }` | 對於每個變更的鍵，若您的值[符合該鍵的 schema](https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot.md#settings-read-key-refused)，您會取代工作階段合併設定中該鍵的整個值 | 該 mod 的呼叫會解析為您的 `value`，或解析為從您的 `value` 中取出、它所要求的 `key`，因此請傳回完整物件，而非陣列 |
| `{ deny: reason }` | 工作階段會保留在任何 hook 回應之前所合併的設定，且[偵錯日誌會記錄您的 `reason`](https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot#settings-read-refused) | 該 mod 的呼叫會以 `<calling mod>: $.settings.read: <reason>` 拒絕 |

在 Claude Code 本身的讀取中，請以 [`next(e)` 的 `value`](#settings-read-next) 為基礎建立您的 `{ value }`，因為您遺漏的鍵會變成未設定。對於 Claude Code 從各來源分別讀取的鍵（例如 `env`），在您的 `value` 中變更它[不會有任何效果](https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot.md#settings-read-key-no-effect)。

#### `next(e)` 給 `settings.read` hook 的內容

`next(e)` 會解析為 `{ value }` 或 `{ deny }`：

* **`{ value }`**：`value` 是合併的設定，或在設定了 [`e.source`](#settings-read-receives) 時為單一來源的設定。如果[在您的 hook 之後執行](#the-order-mods-run-in)的 hook 傳回了自己的 `{ value }`，您會改為取得該 hook 的 `value`。
* **`{ deny }`**：在您的 hook 之後執行的 hook 拒絕了該讀取。請原封不動地傳回該 `{ deny }`。

#### 從 `settings.read` hook 變更單一設定

請先檢查[哪些 mod 會收到此事件，以及從哪個版本開始](#settings-read-hook)。

若要變更單一鍵，請展開 [`next(e)`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#the-hook-function) 的 `value` 並設定該鍵，如此 hook 對 [`spinnerTipsEnabled`](https://code.claude.com/docs/zh-TW/settings-reference#spinnertipsenabled) 所做的那樣。此 hook 不檢查 [`next.origin`](#settings-read-origin)，因此它會在 [Claude Code 本身的讀取](#settings-read-hook)和 mod 的合併讀取中同樣變更該鍵：

```javascript theme={null}
on('settings.read', async ($, e, next) => {
  const read = await next(e)
  // Pass through a read of one source, so that only the merged settings change.
  // Pass through a { deny } from a later hook too: it has no value.
  if (e.source || !read.value) return read
  // Keep every other key and change this one
  return { value: { ...read.value, spinnerTipsEnabled: false } }
})
```

在 Claude Code 本身的讀取中，如果您的 hook 傳回超出該鍵 schema 的值（例如字串），則只有該鍵會保留在任何 hook 回應之前所合併的值。偵錯日誌接著會顯示 [`the answer for <key> is no value the key can hold`](https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot#settings-read-key-refused)。如果您的值符合 schema，但該鍵仍未變更，請參閱[為何鍵沒有生效](https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot.md#settings-read-key-no-effect)。

### 處理設定 hook 事件

設定 hook 是您在設定檔中設定的 command、HTTP、prompt 和 agent hook。每個[設定 hook 事件](https://code.claude.com/docs/zh-TW/hooks.md#hook-events)，例如 `Stop`、`SessionEnd` 或 `PostToolUse`，也是一個名為 `classic.` 後接該設定 hook 事件名稱的事件，例如 `classic.Stop`。`e` 是設定 hook 在 stdin 上收到的 JSON，包括 `transcript_path`。在會載入[內建防護](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md#know-what-happens-by-default)的環境中，[您安裝的 mod 中針對這些事件的 hook 不會執行](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md#hooks-the-guard-passes-over)。

此 hook 使用在 Claude 完成回應時觸發的 `Stop`，來記錄工作階段逐字稿的儲存位置：

```javascript theme={null}
on('classic.Stop', async ($, e, next) => {
  // e has the same fields a Stop hook in a settings file reads from stdin
  $.ui.log('Transcript saved at ' + e.transcript_path)
  // Pass the event on, so Stop hooks in your settings files still run
  return next(e)
})
```

每次 Claude 完成回應時，逐字稿中會出現一行淡色文字，列出逐字稿檔案的路徑。此 hook 傳回 `next(e)`，因此它只觀察事件，不會改變回合結束的方式。

## 與其他 mod 並行執行

多個 mod 可以處理相同的事件，其中任何一個都可能失敗。如果您的 mod 阻止工具呼叫，請檢查其在鏈中的位置以及其 hook 失敗時會發生什麼。

### mod 執行的順序

相同事件上的 hook 形成一個中介軟體鏈。每個 mod 的 `next` 呼叫以下 mod 的 hook，最後一個 `next` 到達 Claude Code 自己的行為。第一個 mod 是最外層的：它在其他 mod 之前看到事件，在它們之後看到結果，並決定其他 mod 是否執行。稍後的 mod 無法阻止較早的 mod 看到事件。

Claude Code 按每個 mod 的來源順序排列鏈：

1. 內建防護 `sec-default@builtin`，一個內建於 Claude Code 的 mod，`/plugin` 列為 `cc-plugin-sec-default`，其中[它載入](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md#know-what-happens-by-default)，您的組織在 [`prependPlugins`](https://code.claude.com/docs/zh-TW/plugins/mods/admin#install-your-organizations-mods) 中列出的 mod，然後是任何其他計為您的組織的 mod，且不在 `appendPlugins` 中
2. 您安裝的 mod
3. 您的組織在 `appendPlugins` 中列出的 mod
4. 內建於 Claude Code 的其他 mod

在您安裝的 mod 中，mod 在其清單中的 `dependencies` 下列出的 mod 之前執行。在一個模組中，hook 按 `register` 呼叫 `on` 的順序執行。

#### 設定 hook 在順序中執行的位置

在設定檔中設定的 `PreToolUse` hook 也在工具呼叫期間執行，在 mod 鏈中的固定點：

* **來自受管設定的 `PreToolUse` hook**：在第一個 mod 的 `tool.call` hook 之前執行。當受管 hook 封鎖呼叫時，該呼叫不會執行任何 mod 的 `tool.call` hook。
* **來自每個其他設定檔和外掛程式 `hooks/hooks.json` 的 `PreToolUse` hook**：在最後一個 mod 呼叫 `next` 後執行，作為 Claude Code 自己行為的一部分。回答 `tool.call` 而不呼叫 `next` 的 mod 會阻止它們執行，呼叫 `next` 的 mod 會在它傳回的結果中看到它們的決定。

[`tool.check`](#approve-or-refuse-a-tool-call-before-the-user-is-asked) 會在 `PreToolUse` hook 執行完畢後才觸發。若要了解 `tool.check` hook 的 `allow` 無法取代哪些權限規則與 `PreToolUse` hook 決定，請參閱[使用 hook 擴充權限](https://code.claude.com/docs/zh-TW/permissions.md#precedence-among-rules-hooks-and-mods)。

### 處理失敗的 hook

失敗的 hook 不會破壞工作階段，您可以決定接下來會發生什麼。當沒有 `.catch` 處理程式的 hook 擲回、逾時或傳回錯誤形狀的結果時，接下來會發生什麼取決於它是否已呼叫 `next`：

* **它在呼叫 `next` 之前失敗**：Claude Code 跳過它，下一個處理程式代替執行
* **它在 `next` 解析後失敗**：該結果成立，沒有任何東西執行第二次

一行命名 mod、事件和原因，例如 `my-mod: tool.call hook skipped: threw Error: boom`。您讀取它的位置取決於工作階段，如[找出 mod 為什麼不執行任何操作](https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot.md#find-out-why-a-mod-does-nothing)所列。[樹狀結構未通過驗證](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md#build-a-tree-from-elements)的 `ui.render` hook，會被視為傳回錯誤形狀結果的 hook。

若要使阻止呼叫的 hook 失敗關閉，請新增 `.catch` 錯誤處理程式以代替回答。此處，`guard` 是您的 hook 函式，處理程式會檢查 [`next.called`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#the-hook-function)，以判斷 `guard` 失敗時是否已呼叫 `next`：

```javascript theme={null}
// on 傳回註冊，.catch 將處理程式附加到該 hook
on('tool.call', { tool: 'Bash' }, guard).catch(async ($, e, next) => {
  // guard 已呼叫 next，因此傳回所得到的結果
  if (next.called) return next(e)
  // next.error.kind 說明呼叫處理程式的原因，例如 'throw' 或 'timeout'
  return { deny: 'The command guard failed, so this command was not run: ' + next.error.kind }
})
```

當 `guard` 在 Bash 呼叫上擲回或逾時時，Claude Code 使用相同的事件呼叫處理程式：

* **`guard` 在呼叫 `next` 之前失敗**：命令不會執行，Claude 讀取末尾帶有該種類的 `deny` 文字
* **`guard` 在呼叫 `next` 之後失敗**：處理程式的 `next(e)` 會解析為 `guard` 的呼叫所產生的結果，而不會再次執行命令，Claude 讀取該結果

處理程式有其自己較短的[時間限制](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#limits)。如果處理程式本身擲回或逾時，Claude Code 會跳過該 hook，如同它沒有處理程式一樣。若 `guard` 尚未呼叫 `next`，命令接著會如同沒有該 mod 時一樣繼續執行。

相同的處理程式形式也適用於 `prompt.submit` 或 `config.set` 上的防護。當 `next.called` 為 false 時，傳回[事件參考](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#events)針對該事件列出的拒絕：`prompt.submit` 為 `{ drop: 'the reason' }`，`config.set` 為 `{ deny: 'the reason' }`。

在 `tool.check` 和 `plugin.register`，於 `next` 解析後傳回的拒絕仍然有效，因此直接傳回它，無需檢查 `next.called`：

* **`tool.check`**：傳回 `{ decision: 'deny', reason: 'the reason' }`
* **`plugin.register`**：傳回 `{ refuse: 'the reason' }`，如[在檢查失敗時拒絕 mod](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md#refuse-mods-when-your-check-fails) 所示

在 `tool.call`，於 `next` 解析後傳回的 `deny` 會[對 Claude 隱藏結果](#guard-or-change-a-tool-call)。

## 後續步驟

* [使用 mods API](https://code.claude.com/docs/zh-TW/plugins/mods/api.md)：新增命令和工具、呼叫模型，以及在計時器上執行工作
* [在介面中繪製](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md)：在窗格或提示上方顯示您的 hook 收集的內容
* [測試 mod](https://code.claude.com/docs/zh-TW/plugins/mods/test.md)：從測試中引發任何這些事件
* [Mods 參考資料](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md)：每個事件、每個 mods API 方法和限制

<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot | lastmod: 2026-11-03 | section: Plugins / Mods -->
> 來源：https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot（官方 zh-TW，lastmod 2026-11-03）｜分類：Plugins › Mods｜EN 摘要：Find out why a Claude Code mod does nothing: match the symptom or message to its cause, look up refusal messages, and read the debug log.

# 排除 mod 的故障

> 找出 Claude Code mod 為什麼沒有作用：將症狀或訊息與其原因相符，查詢拒絕訊息，並閱讀偵錯日誌。

當 mod 的模組或其中一個 hook 失敗時，Claude Code 會跳過它，工作階段會繼續進行，因此損壞的 mod 看起來可能像沒有作用的 mod。首先檢查 Claude Code 從您的 mod 讀取了什麼，以及它在哪裡報告問題，然後找到您遇到的症狀或訊息。

## 找出 mod 為什麼沒有作用

當 mod 沒有作用時，請檢查 Claude Code 從 mod 的檔案讀取的內容，以及它在跳過某些內容時寫入的那一行。對於第一項，在您的 shell 中執行 [`claude plugin validate`](https://code.claude.com/docs/zh-TW/plugins/mods/create#check-what-claude-code-reads-from-your-mod)，並使用 mod 的目錄，例如 `claude plugin validate ./first-mod`。它會捕捉拼寫錯誤的事件、不良的資訊清單和 Claude Code 無法讀取的模組，而無需啟動工作階段。

當模組未載入、hook 被跳過或另一個 mod 拒絕您的 mod 時，Claude Code 會寫入一行，其中命名您的 mod。您讀取該行的位置取決於工作階段：

* **熱重新載入 plugin 目錄的工作階段**：文字記錄中的暗淡行。這是您使用 `--plugin-dir` 啟動的互動式工作階段，或您[為 Claude 編寫的 mod 啟用熱重新載入](https://code.claude.com/docs/zh-TW/plugins/mods/create.md#ask-claude-for-a-mod)的工作階段。
* **任何其他互動式工作階段，例如執行您從市場安裝的 mod 的工作階段**：[偵錯日誌](#read-the-debug-log)只有。若要取得一個，請使用 `claude --debug` 啟動工作階段。
* **`claude -p` 執行 `--plugin-dir`**：stderr，採用預設文字輸出格式。另一個 mod 的拒絕只會進入偵錯日誌。

## 檢查 mod 是否可以載入

若要檢查您的設定是否允許 mod 載入，而無需安裝一個，請在您的 shell 中執行 `claude plugin test`，從不包含 mod 的目錄執行。您不需要工作階段。它列印的訊息會告訴您狀態：

| 訊息包含 | 這表示什麼 |
| :- | :- |
| `no hooks module to load` | Mod 可以載入。該命令在此目錄中找不到要測試的 mod。 |
| `hooks modules are turned off here` | 設定正在阻止您的 mod：您自己設定中的 `disableAllHooks`，或您的組織的原則 |
| `hooks modules are turned off in this process: the rollout switch served off` | Anthropic 已遠端關閉已安裝的 mod。 |
| `hooks modules are turned off in this process: the rollout switch was saved off by an earlier session` | 該命令使用了先前工作階段儲存的值，該值可能已過時。請啟動 `claude` 一次以重新整理它，然後再次執行該命令。 |

組織也可以設定 `allowManagedModsOnly` 以僅允許其自己的 mod，此命令不會報告。在這種情況下，Claude Code 會拒絕您安裝的 mod，並且[訊息會說明原因](https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot.md#messages-from-the-built-in-guard)。

## mod 不載入

mod 新增的任何內容都不會出現：沒有命令、沒有繪圖，也沒有行為變化。

### 您的版本太舊

請參閱[應使用哪個版本以及如何檢查您的版本](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md#turn-mods-on-or-off)。

### `mods active` 行不命名 mod

mod 新增的任何內容都不會出現，並且 `/plugin` 中的 [`mods active` 行](https://code.claude.com/docs/zh-TW/plugins/mods/overview#see-which-mods-a-session-loaded)不命名它。hooks 模組未載入。當 Claude Code 拒絕它時，偵錯日誌有一行以 `hooks module`、mod 的名稱和 `not loaded:` 開頭，例如 `hooks module first-mod@inline not loaded: disableAllHooks in managed settings`，用於使用 `--plugin-dir` 載入的 mod。

讀取冒號後的原因。[拒絕訊息](#refusal-messages)部分列出每一個。如果日誌沒有這樣的行，請逐一檢查此群組中的其他項目。

部分設定會停用 mod，但讓其外掛的其餘部分繼續運作。[開啟或關閉 mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md#turn-mods-on-or-off) 列出了這些設定。

### `claude -p` 執行列印 `hooks module not loaded`

該行以 mod 的名稱開頭，並進入 stderr。hooks 模組被拒絕。非互動式執行沒有文字記錄，因此訊息進入 stderr。

讀取冒號後的原因。[拒絕訊息](#refusal-messages)部分列出每一個。

### 拒絕訊息

每一個都遵循偵錯日誌中的 `hooks module`、mod 的名稱和 `not loaded:`。

| 訊息開頭為 | 這表示什麼 |
| :- | :- |
| `hooks modules are turned off for installed plugins in this process: the rollout switch served off` | Anthropic 已遠端關閉已安裝的 mod。 |
| `hooks modules are turned off for installed plugins in this process: the rollout switch was saved off by an earlier session` | 該工作階段使用了先前工作階段儲存的值，該值可能已過時。請重新啟動 Claude Code 以重新整理它。 |
| `disableAllHooks in managed settings` | 您的組織關閉了已安裝 plugin 的 hooks |
| `only managed plugins and built-in plugins run` | 設定了 `allowManagedHooksOnly`，或在受管設定以外的設定檔中設定了 `disableAllHooks` |
| `installed plugins that are not managed load no hooks module in this mode (--bare)` | 您使用 `--bare` 啟動了 Claude Code |
| `another plugin of that name loads first` | 另一個已啟用的外掛與您的 mod 同名，並[佔有該名稱](https://code.claude.com/docs/zh-TW/plugins/loading.md#hooks-when-two-enabled-plugins-share-a-name)，因此您的 hook 模組不會載入 |

### 來自內建防護的訊息

在具有受管設定的機器上，或在憑證為 Team 或 Enterprise `/login` 的工作階段中，[內建防護](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md#know-what-happens-by-default)可以拒絕 mod 或其中一個答案。每條訊息都命名您的組織管理員設定以變更規則的選項。

| 訊息包含 | 這表示什麼 | 它出現在哪裡 |
| :- | :- | :- |
| `mods are limited to your organization's by policy (allowManagedModsOnly)` | 您的組織僅允許[其自己的 mod](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md#install-your-organizations-mods)，因此您的 mod 被拒絕 | 偵錯日誌，以及[熱重新載入外掛目錄的工作階段](#find-out-why-a-mod-does-nothing)中的逐字稿 |
| `tried to lift a deny rule in your settings` | 您的 mod 的 [`tool.check`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#tools) hook 批准了 `deny` 規則拒絕的呼叫。呼叫保持被拒絕。 | 文字記錄和偵錯日誌，每個工作階段中的每個 mod 一次。在 `claude -p` 執行中，僅偵錯日誌。 |
| `the deny rules in your settings could not be checked for this call, so it is refused` | 防護在檢查 mod 批准的呼叫時失敗，因此它拒絕了呼叫 | Claude 為被拒絕的呼叫讀取的原因 |

### `validate` 通過且不列出 `hooks` 行

`hooks/hooks.json` 沒有 `modules` 鍵，或鍵拼寫錯誤。

新增 `"modules": ["./register.js"]`。

### `hooks module did not load`

該行以 mod 的名稱開頭，然後是 `hooks module did not load:` 和一個原因，當問題在您的程式碼中時，該原因會給出檔案和行。Claude Code 無法載入模組，例如因為其頂級程式碼拋出。

修復原因命名的錯誤。

如果原因以 `; the version loaded before is unloaded` 結尾，表示目前沒有任何版本的 mod 正在執行。修復錯誤後，請在工作階段中執行 [`/reload-plugins`](https://code.claude.com/docs/zh-TW/plugins/cli-reference#reload-plugins) 以再次載入 mod。如果該 mod 是您安裝而非您撰寫的，請要求其作者修復錯誤。

### `options do not fit plugin.json userConfig`

該行以 mod 的名稱開頭，然後是 `hooks module did not load: options do not fit plugin.json userConfig:` 和一個原因。選項未通過其 [`userConfig`](https://code.claude.com/docs/zh-TW/plugins/components#user-configuration) 欄位的驗證，例如高於欄位 `max` 的數字，或必填欄位沒有值。

設定或變更值。該行的末尾命名其在 `settings.json` 中的 `pluginConfigs` 項目。

### `code nested too deep to scan: more than 2000 scopes`

該行以 mod 的名稱開頭，然後是 `hooks module did not load:`、檔案，以及 `code nested too deep to scan: more than 2000 scopes`。hook 模組中的檔案不能將作用域（例如函式、區塊和迴圈）巢狀超過 [2,000 層](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#limits)。[`claude plugin validate`](https://code.claude.com/docs/zh-TW/plugins/mods/create#check-what-claude-code-reads-from-your-mod) 會回報相同的原因。

重寫程式碼，以減少其作用域的巢狀深度。

### `the engine ran out of stack linking the file and its imports`

hook 模組中的程式碼巢狀過深，或其匯入鏈過長，導致 Claude Code 無法載入。該行以 mod 的名稱和 `hooks module did not load:` 開頭，然後給出某個檔案的名稱以及此原因。

在該檔案及其匯入所觸及的檔案中，找出巢狀層級最深的程式碼並加以改寫以減少巢狀層級，或縮短匯入鏈。如果該 mod 並非由您撰寫，請要求其作者修正。

### `the parser stopped` 或 `the engine ran out of stack loading the file`

hook 模組中某個檔案的程式碼巢狀過深，導致 Claude Code 在讀取時耗盡堆疊。該行以 mod 的名稱和 `hooks module did not load:` 開頭，然後給出該檔案的名稱以及下列其中一個原因：

* `code nested too deep to scan (the parser stopped: <message>)`
* `the engine ran out of stack loading the file (code nested too deep): <message>`

該原因不提供行號，也不說明巢狀的是哪種程式碼，因此請自行檢查該檔案，找出巢狀最深的部分。重寫該部分以減少巢狀。如果該 mod 是您安裝而非您撰寫的，請要求其作者進行修改。

### 沒有 mod 在您首次開啟的目錄中載入

您尚未回答該目錄的信任提示。

使用 `claude` 在該目錄中啟動互動式工作階段，並接受它開啟的信任提示。

### 沒有已安裝的 plugin 載入

您使用 `--safe-mode` 啟動了 Claude Code。

啟動時不使用該旗標。

### Claude Code 不再詢問是否啟用熱重新載入

Claude 在互動式工作階段中撰寫 mod，但沒有任何內容載入，而且 Claude Code 不再詢問[是否啟用熱重新載入](https://code.claude.com/docs/zh-TW/plugins/mods/create.md#ask-claude-for-a-mod)。如果該問題有三次在未選擇答案的情況下結束，熱重新載入會保持關閉。例如，當您設定了 [`askUserQuestionTimeout`](https://code.claude.com/docs/zh-TW/settings-reference#askuserquestiontimeout)，且在您回答之前時間已到，問題就會以這種方式結束。該設定在此適用，是因為 Claude Code 是在[與 `AskUserQuestion` 相同的問題對話框](https://code.claude.com/docs/zh-TW/tools-reference#question-auto-continue-timeout)中詢問。您自行關閉的問題不計入這三次。

若要執行該 mod，請[將其目錄從 mods 資料夾複製出來](https://code.claude.com/docs/zh-TW/plugins/mods/create.md#use-the-mod-in-other-sessions)，然後在 shell 中使用 `--plugin-dir` 啟動新的工作階段，例如 `claude --plugin-dir ~/mods/git-branch`。

## hook 被跳過或 mod 被卸載

mod 已載入，然後 Claude Code 跳過了其中一個 hook 或卸載了它。

### `hook skipped`

該行命名 mod 和事件，然後說 `hook skipped:` 和一個原因，例如 `first-mod: tool.call hook skipped: threw Error: boom`。hook 拋出、執行超過其[時間限制](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#limits)，或返回了錯誤形狀的結果。該行針對每個事件和失敗類型出現一次，直到 mod 重新載入。

修復錯誤。偵錯日誌對每次發生都有一行。

### `no command.run hook answered it`

您執行 mod 新增的命令，回覆命名 mod 和命令，例如 `first-mod registered /tally but no command.run hook answered it`，然後告訴您新增 hook。Claude Code 在命令到達鏈的末端且沒有答案時列印該回覆，這在兩種情況下發生：

* **沒有 hook 回答命令**：模組沒有 `command.run` hook、hook 的[篩選器](https://code.claude.com/docs/zh-TW/plugins/mods/events.md#filter-which-events-a-hook-handles)命名不同的命令，或 hook 返回 `next(e)`
* **Claude Code 跳過了 hook**：[`hook skipped`](#hook-skipped) 列出了原因。將 `focus: false` 傳遞給 [`$.ui.open`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#open-a-pane-at-the-right-time) 是到達那裡的一種方式。

如果模組已經有回覆描述的 hook，請尋找命名 `command.run` 的 `hook skipped` 行，它會給出原因。執行命令的[測試](https://code.claude.com/docs/zh-TW/plugins/mods/test.md)會因相同原因失敗。

### `it crashed the hooks worker`

該行以 mod 的名稱開頭，例如 `first-mod was unloaded: it crashed the hooks worker`。已安裝的 mod 共享一個工作執行緒。工作執行緒停止回應或崩潰，Claude Code 將其追蹤到此 mod 並卸載了它。阻止執行緒的 hook（例如永不等待的迴圈）是一個原因。

修復 hook。

### `its session.start ran again in a fresh copy`

該行以 mod 的名稱開頭，並命名一個 `$.prompt.submit`、`$.command.run` 或 `$.agent.spawn` 呼叫，例如 `first-mod: its session.start ran again in a fresh copy; the $.prompt.submit call it had already made was not made again`。Claude Code 再次載入了 mod 的模組，例如在 hook 工作執行緒崩潰並被取代之後，而新副本的 [`session.start`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#session) hook 執行了。該行命名的呼叫以其第一次執行的結果解析，而不是再次執行，因此您的 mod 不會重複提交提示詞、執行命令或啟動 subagent。hook 的其餘部分照常執行。

無需修復任何內容。

在 v2.1.292 之前，該呼叫會執行第二次，因此提示詞會被提交兩次、命令會被執行兩次，或 subagent 會被啟動兩次。

### `This mod's change didn't load` 或 `the earlier version is no longer running`

對[Claude 在此工作階段中撰寫的 mod](https://code.claude.com/docs/zh-TW/plugins/mods/create.md#ask-claude-for-a-mod) 所做的變更無法載入。逐字稿中的該行以 mod 的名稱開頭，並以原因結尾：

* `This mod's change didn't load, so the earlier version is still running: <reason>.`
* `This mod didn't load, and the earlier version is no longer running: <reason>.`

Claude 看不到此行，因此當您請 Claude 修復時，請將其貼到您的下一則訊息中。

### `$.agent.register refused: the hooks module that made the call is no longer loaded`

該行以您的 mod 名稱開頭，例如 `first-mod: $.agent.register refused: the hooks module that made the call is no longer loaded (it was reloaded or removed)`，且該 agent 不會被註冊。您的 mod 在此呼叫之前已被重新載入或卸載。重新載入會載入 hook 模組的新副本，而此呼叫來自仍在舊副本中執行的程式碼，例如尚未返回的 hook。

如果該 hook 未捕捉此拒絕，它會失敗，Claude Code 會[跳過它](#hook-skipped)。若要讓保持載入的副本註冊該 agent，請在您的 [`session.start`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#session) hook 中進行呼叫，該 hook 會在重新載入後於每個新副本中再次執行。

### `mods that run in the hooks worker are off for this session`

該行讀取 `hooks: mods that run in the hooks worker are off for this session: it crashed 3 times`。工作執行緒停止了三次，Claude Code 無法將停止追蹤到一個 mod，因此它卸載了每個不是內建的 mod，包括您的組織安裝的 mod。此行到達每個互動式工作階段中的文字記錄。

執行 `/reload-plugins` 以再次載入它們。

## 工具呼叫被拒絕

mod 已載入，其 hook 執行，它接觸的工具呼叫被拒絕。

### `a hook changed this call's input after the model wrote it`

在自動模式中，被拒絕的工具呼叫會給出此原因。hook 在[伺服器端分類器](https://code.claude.com/docs/zh-TW/permission-modes.md#server-side-classifier-review)檢查後變更了工具呼叫的輸入，因此該檢查不涵蓋將執行的內容。hook 可以是 mod 的 [`tool.call`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#tools) 或 [`turn.step`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#turns) hook，或 [`PreToolUse`](https://code.claude.com/docs/zh-TW/hooks#pretooluse) 設定 hook。訊息不會說明是哪一個。

訊息告訴 Claude 再次發出記錄的呼叫。如果也被拒絕，hook 每次都會變更輸入，因此關閉 mod 或 hook，或離開自動模式並自己批准呼叫。

> [!NOTE]
>
> 在[部分互動式終端機工作階段與 VS Code 工作階段](https://code.claude.com/docs/zh-TW/hooks.md#pretooluse-updatedinput-in-auto-mode)中，相同的拒絕會給出原因 `a hook changed this call's input after auto mode reviewed it`。在那裡重複的呼叫會帶有 mod 的第一次變更，且 `tool.call` hook 仍會在其上執行，但進一步的變更會被捨棄。除非 Claude 在其回覆中告訴您[自動模式無法檢查該呼叫](https://code.claude.com/docs/zh-TW/errors.md#hook-changed-input-after-review)，否則無需變更您的 mod。

### 關於您設定中的拒絕規則的訊息

`tried to lift a deny rule in your settings` 和 `the deny rules in your settings could not be checked for this call, so it is refused` 都來自內建防護。

在[來自內建防護的訊息](#messages-from-the-built-in-guard)中查詢它們。

## 回合停止後出現提示訊息

### `Stopped: type a message to continue; a mod cannot resume work after Stop`

此提示訊息表示在您停止回合之後（例如按下 Esc），某個 mod 嘗試自行開始工作，而 Claude Code 未允許它這麼做。無需修正任何問題。在您傳送下一則訊息後，mod 即可再次開始工作，而[部分工作會自行恢復](https://code.claude.com/docs/zh-TW/plugins/mods/api.md#work-your-mod-started-before-the-interruption)。如果您預期該 mod 產生的結果沒有恢復，請再次提出要求，或再次執行該 mod 的命令。

如果您是該 mod 的作者，請參閱[使用者中斷回合後的呼叫與背景工作](https://code.claude.com/docs/zh-TW/plugins/mods/api.md#calls-and-background-work-after-the-user-interrupts-a-turn)。

## 繪圖不出現或不回應

mod 已載入，其窗格、帶狀、toast 或控制項的行為不符合您的預期。

### 顯示的是另一個 mod 的帶狀，而不是您的

提示詞上方只有一個帶狀，所有 mod 共用。在[您的 mod 之前](https://code.claude.com/docs/zh-TW/plugins/mods/events.md#the-order-mods-run-in)執行的 mod，若返回的樹中不包含 `next(e)` 的結果，就會取代您的帶狀。若要同時顯示兩個帶狀，請修改該 mod 的 hook，或請其作者修改：

* **保留其後的帶狀**：將 `await next(e)` 的結果放在其樹中某個 `Box` 的子元素之間，如[選擇繪製位置](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md#pick-where-to-draw)中「提示詞上方的帶狀」分頁所示
* **保持樹有效**：不要為該 `Box` 或其外圍的任何 `Box` 指定 `width`、`height`、`minWidth`、`minHeight`、`position`、`top`、`left`、`right`、`bottom`、`display` 或 `overflow` prop

若要找出該 mod，請[寫入偵錯日誌](#read-the-debug-log)，並在其中搜尋 `answered ui.render without next()`。像 `other-mod (user) answered ui.render without next()` 這樣的行會指出某個未呼叫 `next(e)` 就返回其樹的 mod。該行不會指出[轉譯位置](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#render-sites)，因此僅使用窗格的 mod 也可能出現。呼叫了 `next(e)` 但捨棄其結果的 mod 不會產生任何行，因此也請檢查在您之前的 hook。

當某個 mod 自身的 hook 返回的樹未通過驗證時，該 mod 的帶狀也會消失，而其他 mod 的帶狀則會保留。若要找出是哪個 mod 以及原因，請[寫入偵錯日誌](#read-the-debug-log)，並在其中搜尋 [`ui.render hook skipped`](#a-pane-or-band-is-empty)。

### 窗格或帶狀為空或顯示 Claude Code 的常見內容

您的 hook 返回的[樹](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md#build-a-tree-from-elements)未通過驗證。[逐字稿或偵錯日誌中](#find-out-why-a-mod-does-nothing)的 [`hook skipped`](#hook-skipped) 行會指出您的 mod 與原因，例如以下這行是針對窗格中的 `Box`：

```text theme={null}
first-mod: ui.render hook skipped: returned the wrong shape (a tree Pane refuses: Box prop "flexDirection" must be one of row, column, row-reverse, column-reverse)
```

修正原因所指出的問題。若原因被截斷，請[寫入偵錯日誌](#read-the-debug-log)，並在其中搜尋 `a hook returned a tree that does not validate` 以讀取其餘內容。

若該行在位置名稱之後緊接著顯示 `refused:`，例如 `ui.render (Pane) refused:`，請參閱 [`ui.render` 行顯示 `refused`](#ui-render-refused)。

### `ui.render` 行顯示 `refused`

`ui.render (<site>) refused:`，或[偵錯日誌](#read-the-debug-log)中的 `ui.render (<site>): the chain settled on a tree that does not validate`，表示該位置的[樹](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md#build-a-tree-from-elements)超出了[大小限制](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#limits)。這兩行都會先指出[轉譯位置](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#render-sites)，接著是原因，而原因會指出該限制。

請修改在該位置繪製的 mod，使其 [`ui.render`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#interface) hook 返回較小的樹，或請其作者修改。若逐字稿行以 `hooks` 開頭，表示有多個已載入的 mod 具有該位置的 `ui.render` hook，因此請檢查每個 mod 的樹。當多個 mod 在提示詞上方的帶狀巢狀組成超過 32 層深的樹時，該行如下：

```text theme={null}
hooks: ui.render (AbovePrompt) refused: deeper than 32; nothing was drawn
```

在 v2.1.307 之前，任何位置的 `refused:` 行都會回報任何未通過驗證的樹，且對於 `Pane` 與 `AbovePrompt`，其結尾為 `; the engine drew its own`。在這些版本中，請修正原因所指出的問題。

### `needs a key`、`is drawn twice` 或 `key each once`

您的 `ui.render` hook 返回的樹中，某個元素沒有有效的 [`key`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#which-controls-need-a-key)，或兩個元素共用同一個 key。請找出您收到的訊息：

* **`<Input> needs a key` 或 `<Select> needs a key`**：該元素沒有 `key` prop，或其 `key` 為空或不是字串，例如 `key: 3`。請為其指定非空字串作為 `key`。
* **`<Button> needs a key`**：請為按鈕指定非空字串作為其 `key`
* **`is drawn twice; each takes its own key`**：訊息所指種類的兩個元素具有相同的 `key`，例如 `Input "size" is drawn twice; each takes its own key`。請為每個元素指定各自的 `key`。
* **[測試](https://code.claude.com/docs/zh-TW/plugins/mods/test.md#test-a-drawing)中 `press` 產生的 `key each once`**：繪圖中有多個按鈕使用您傳入的 key。具有相同標籤且沒有 `key` prop 的按鈕會共用該標籤作為其 key。請為每個按鈕指定各自的 `key`。

### `ui.render` 行顯示 `threw while drawn`

該行會指出[轉譯位置](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#render-sites)，接著顯示 `threw while drawn:` 與錯誤，例如 `first-mod: ui.render (ToolUse) threw while drawn: <error>; the engine drew its own`。Claude Code 在繪製您的 [`ui.render`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#interface) hook 返回的樹時，或在根據[您的 hook 傳給 `next` 的 `props`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#change-what-claude-code-already-draws) 繪製該位置時，遇到了該錯誤。結尾的 `the engine drew its own` 表示該位置顯示 Claude Code 的常見內容。

讀取該錯誤，並修正您的 hook 中導致錯誤的值。

在 v2.1.289 之前，逐字稿列中的此錯誤會以 [`Claude Code exited after an unrecoverable interface error`](https://code.claude.com/docs/zh-TW/errors#exited-after-an-unrecoverable-interface-error) 結束工作階段。

### `the module failed without a message`

某個 [`Client`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#when-a-client-fails) 因沒有訊息的錯誤而失敗，例如 `throw new Error()`。在其位置顯示的那一行類似 `my-mod: Client client/spinner.js: the module failed without a message`。

在您的 `Client` 程式碼中找到該 throw，並為錯誤加上訊息。該行隨後便會顯示該訊息。

在 v2.1.289 之前，該行會改為顯示 `Error` 作為原因。

### `$.ui.open` 執行且沒有窗格出現

呼叫不是來自使用者所做的操作，並且終端機的寬度小於[該窗格所需的寬度](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md#when-a-pane-waits-for-a-wider-terminal)。

從命令或按鈕開啟窗格，或檢查呼叫的 `isPlaced` 結果。請參閱[在正確的時間開啟窗格](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md#open-a-pane-at-the-right-time)。

### toast 未出現

您的 mod 在互動式終端機工作階段中呼叫 [`$.ui.toast`](https://code.claude.com/docs/zh-TW/plugins/mods/api#show-something-without-starting-a-turn)，但您沒有看到 toast。若要確認該呼叫已執行，請在[偵錯日誌](#read-the-debug-log)中尋找包含您的 mod 名稱與 toast 文字的行，例如 `$.ui.toast (first-mod): build finished`。接著檢查以下可能原因：

* **缺少該呼叫的行**：尋找說明 Claude Code 拒絕該呼叫原因的行，例如 `first-mod: $.ui.toast dropped: timeoutMs is a whole number of ms, 1 to 60000`。
* **有窗格正在保留 toast**：您的 mod 或其他 mod 在開啟目前顯示的窗格時傳入了 [`holdToasts`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#hold-toasts-behind-a-dialog)。關閉該窗格即可結束保留。如果該窗格是您的，且應保持開啟，請從其 `$.ui.open` 呼叫中移除 `holdToasts`，然後重新開啟窗格。
* **toast 位於提示詞下方**：在[傳統轉譯器](https://code.claude.com/docs/zh-TW/fullscreen.md#enable-fullscreen-rendering)中，請查看提示詞下方的右側。該處的 toast 是以 mod 名稱開頭的一行文字，而不是右上角的方框。
* **您的 mod 發出了較新的 toast**：在傳統轉譯器中，您的 mod 發出的較新 toast 可能會取代正在顯示或等待顯示的 toast。偵錯日誌中會有較舊 toast 的另一行，若該 toast 正在顯示，結尾為 `gave way, cut short`；若從未出現，結尾為 `gave way, unseen`。若要同時顯示兩則訊息，請將它們放在同一個 toast 中。
* **toast 在繪製前逾時**：在全螢幕轉譯中，Claude Code 一次最多繪製三個 toast，因此 toast 可能在繪製前就已逾時。偵錯日誌中會有該 toast 的另一行，結尾為 `left the stack, never drawn`。當您的 mod 同時發出多個 toast 時，請將訊息放在同一個 toast 中。

在 v2.1.290 之前，Claude Code 會捨棄在其為您的 mod 顯示上一個 toast 後兩秒內發出的 toast，且被捨棄 toast 的偵錯日誌行會顯示 `within 2000ms of the last; dropped`。

### 帶狀顯示 `plugin panel hidden`

帶狀已[收合](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md#when-the-user-collapses-the-band)。當您按下 Ctrl+X 然後 Ctrl+A，或您綁定以取代它們的按鍵時，帶狀會收合；在[全螢幕轉譯](https://code.claude.com/docs/zh-TW/fullscreen.md)中，按一下其第一列的 `[-]` 時也會收合。帶狀會保持收合，直到您將其展開或重新啟動 Claude Code，在此期間，任何快捷鍵或 `action` 綁定都不會按下其中的按鈕。

若要展開帶狀，請按該列所指出的按鍵（預設為 Ctrl+X 然後 Ctrl+A），或在全螢幕轉譯中按一下該列。

### 快捷鍵沒有作用

您的窗格或帶狀沒有鍵盤焦點、您的按鈕位於已收合的帶狀中，或繪圖位於 VS Code 擴充功能中，而該處的按鈕沒有快捷鍵。請執行相符的操作：

* **沒有鍵盤焦點**：按 Ctrl+X 然後 Tab，或在[全螢幕轉譯](https://code.claude.com/docs/zh-TW/fullscreen.md)中按一下窗格或帶狀。若要讓窗格在開啟時取得焦點，請從命令以 `focus: true` 開啟它。
* **按鈕位於已收合的帶狀中**：帶狀會顯示一列以 `▸ plugin panel hidden` 開頭的暗色列。按該列所指出的按鍵（預設為 Ctrl+X 然後 Ctrl+A）即可[將其展開](#plugin-panel-hidden)。
* **在 VS Code 擴充功能中**：按一下按鈕，或在按鈕取得焦點後按 Enter

### 繪圖在終端機中有效，但在 Desktop 應用程式或 VS Code 中無效

可能是該應用程式不繪製該位置或元素，或是該工作階段屬於 VS Code 擴充功能不會為 mod 繪製任何內容的情況。mod 的其他 hook 仍會執行。請檢查以下原因：

* **該位置或元素未在該應用程式中繪製**：在[轉譯位置](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#render-sites)表中查詢您的位置，並在[元素](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#elements)表中查詢您的元素。對於該應用程式缺少的元素，請在 hook 中檢查 `e.surface`，並返回該應用程式可繪製的樹。
* **VS Code 擴充功能版本早於 2.1.299**：聊天面板從[擴充功能版本](https://code.claude.com/docs/zh-TW/vs-code.md#install-the-extension) 2.1.299 起會為 mod 繪製內容。請在 VS Code 的 Extensions 檢視中檢查版本，並在該處更新擴充功能。
* **擴充功能版本早於 2.1.304 且工作階段不擷取功能旗標**：請更新擴充功能，或改為在 VS Code 的整合式終端機中執行 `claude`。在 Amazon Bedrock、Google Cloud 的 Agent Platform 或 Microsoft Foundry 上的工作階段會略過此擷取。對於其他會略過擷取的工作階段，例如 [Claude apps 閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)工作階段，請參閱[需要擷取功能旗標的功能](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)。

## 編輯或值遺失

mod 執行，您所做的變更或它保留的值不存在。

### 您的編輯不生效

您正在編輯您安裝的 plugin。Claude Code 執行已安裝版本的快取副本。

使用指向您的工作副本的 `--plugin-dir` 進行開發，例如 `claude --plugin-dir ./first-mod`，它在您儲存時重新載入。

### 模組重新載入時值重設

模組級變數在每次重新載入時重新初始化。

[將值保留在 `$.state` 或 `$.store`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#keep-state)。

### `/clear`、`/resume` 或 `/branch` 後值重設

值重設，或儲存的值被其預設值取代。這些命令中的每一個都將 `$.state` 重設為其預設值，並且 `session.start` 不會再次觸發。

[在 `classic.SessionStart` hook 中再次載入儲存的值](https://code.claude.com/docs/zh-TW/plugins/mods/interface#load-a-saved-value-again-after-clear)。

### 您的 `settings.read` hook 傳回的設定鍵未生效

若您在 [Claude Code 本身的讀取](https://code.claude.com/docs/zh-TW/plugins/mods/events.md#settings-read-hook)中傳回權限規則或 `env`，這些規則不會在工具呼叫時受到檢查，且 `env` 項目不會成為環境變數。請針對兩者使用[設定檔](https://code.claude.com/docs/zh-TW/settings.md)，或針對 `env` 使用 [`$.env.set`](https://code.claude.com/docs/zh-TW/plugins/mods/api#reach-files-processes-and-the-network)。

若是其他設定鍵，請查看[哪些 mod 會收到 `settings.read` 以及從哪個版本開始](https://code.claude.com/docs/zh-TW/plugins/mods/events#settings-read-hook)，然後在[偵錯日誌](#read-the-debug-log)中搜尋 `settings.read`，並尋找下列其中一行：

| 日誌行 | 意義與步驟 |
| :- | :- |
| `settings.read hook skipped`，位於您的 mod 名稱之後 | 您的 hook 失敗。[修正該行回報的錯誤](#hook-skipped)。 |
| `settings.read bypassed by cc-plugin-sec-default`，出現在於其前方列出您的 mod 名稱的行上 | [內建防護](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md#know-what-happens-by-default)略過了您的 hook。請您組織的管理員[將該 mod 安裝為組織的 mod 之一](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md#install-your-organizations-mods)。 |
| `settings.read: the answer for <key> is no value the key can hold` | Claude Code 拒絕了某個 hook 針對該設定鍵傳回的值。該 hook 可能是您的，也可能是其他 mod 的。請依照[適用於您情況的步驟](#settings-read-key-refused)進行。 |
| `settings.read: the merge never settles for <key>` | 該行列出的設定鍵會保留設定來源的值。請在設定檔中設定它們。 |
| `answered settings.read without next()`，位於某個 mod 名稱之後 | 若該 mod [於您的 mod 之前執行](https://code.claude.com/docs/zh-TW/plugins/mods/events.md#the-order-mods-run-in)，您的 hook 就會受到影響。此時您的 hook 未在該次讀取中執行。[關閉該 mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md#turn-mods-on-or-off)，或者若是您的組織部署了它，請其管理員關閉。 |
| `settings.read: refused to the engine` | 由於 Claude Code 本身的讀取遭到拒絕，您的值未生效。[找出拒絕的來源](#settings-read-refused)。 |

若沒有任何一行能解釋該設定鍵，請檢查在您的 mod 之前執行的 mod 中，是否有[變更該設定鍵](https://code.claude.com/docs/zh-TW/plugins/mods/events.md#settings-read-example)的 `settings.read` hook。關閉該 mod，或請您組織的管理員關閉。若沒有任何 hook 變更它，請在設定檔中設定該設定鍵。

### `the answer for <key> is no value the key can hold`

此[偵錯日誌](#read-the-debug-log)行表示 Claude Code 拒絕了某個 [`settings.read`](https://code.claude.com/docs/zh-TW/plugins/mods/events#settings-read-hook) hook 針對所列設定鍵傳回的值，且僅限該設定鍵：

```text theme={null}
settings.read: the answer for <key> is no value the key can hold; the settings' own value stands
```

針對所列設定鍵傳回的值不符合該設定鍵的 schema，例如在型別或範圍上不符。

* **您的值不符合該設定鍵的 schema**：請傳回該設定鍵的[設定參考](https://code.claude.com/docs/zh-TW/settings-reference.md)項目所允許的值。
* **您的值符合**：不符合的值來自其他 mod 的 `settings.read` hook。若要找出該 mod，請依照[逐一關閉 mod 的步驟](#settings-read-refused)進行。在每個新日誌中搜尋此行，而非 `refused to the engine`。

在該值不符合期間，該設定鍵會保留在任何 hook 回應之前從設定來源合併而來的值。該行將其稱為設定本身的值。

### `settings.read: refused to the engine`

當 [Claude Code 本身的讀取](https://code.claude.com/docs/zh-TW/plugins/mods/events.md#settings-read-hook)遭到拒絕時，您會在[偵錯日誌](#read-the-debug-log)中看到此行，且 Claude Code 會捨棄所有 hook 的值。當某個 `settings.read` hook 以 [`{ deny: reason }`](https://code.claude.com/docs/zh-TW/plugins/mods/events#settings-read-returns) 拒絕該讀取時，該行會帶有該 hook 的原因：

```text theme={null}
settings.read: refused to the engine (engine: $.settings.read: <reason>); the settings' own values stand
```

在您的程式碼中搜尋括號內的原因：

* **您的程式碼中有此文字**：您的 hook 拒絕了該讀取。請讓它在 [`next.origin`](https://code.claude.com/docs/zh-TW/plugins/mods/events#settings-read-origin) 顯示為 Claude Code 本身的讀取時傳回 `{ value }`。
* **您的程式碼中沒有此原因**：逐一[關閉](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md#turn-mods-on-or-off)您的其他 mod。若某個 mod 是您的組織部署的，請其管理員將其關閉。每關閉一個後：
  1. 從您的 shell 以 `claude --debug-file ./settings-read-2.log` 啟動工作階段，並在後面加上原本啟動時使用的旗標。每次都使用新的路徑。
  2. 在該檔案中搜尋 `refused to the engine`。若該行存在，請關閉下一個 mod。若不存在，則您最後關閉的 mod 拒絕了該讀取，請保持其關閉。

若沒有其他 mod 可關閉而該行仍然存在，請在[設定檔](https://code.claude.com/docs/zh-TW/settings.md)中設定您的 hook 傳回的設定鍵。在讀取遭到拒絕期間，其值仍然有效。

## 讀取偵錯日誌

偵錯日誌對 Claude Code 載入或拒絕的每個模組、失敗的每個 hook 和它拒絕的每個結果都有一行，因此當逐字稿顯示沒有內容時，這是要查看的地方。若要寫入一個，在您的 shell 中使用 `--debug` 啟動 Claude Code，或使用 `--debug-file <path>` 選擇它的位置：

```bash theme={null}
claude --debug-file ./mod-debug.log --plugin-dir ./first-mod
```

在另一個終端機中，跟蹤檔案並篩選您的 mod 的名稱：

```bash theme={null}
tail -f ./mod-debug.log | grep first-mod
```

已載入的 mod 有一行，其命名它並列出它處理的事件。使用 `--plugin-dir` 載入的 mod 出現在其名稱後跟 `@inline` 下：

```text theme={null}
hooks module first-mod@inline loaded (worker, environment 2, tier user); events: session.start,tool.call,command.run,ui.render
```

若要在日誌中寫入您自己的行，請呼叫 [`$.ui.log`](https://code.claude.com/docs/zh-TW/plugins/mods/api#show-something-without-starting-a-turn)，並帶有第二個引數，例如 `$.ui.log('message', { to: 'debug' })`。沒有第二個引數，`$.ui.log` 會在逐字稿中新增暗淡行。

當您編輯使用 `--plugin-dir` 載入的 mod 時，逐字稿會為每次重新載入顯示一行，其命名 mod 並列出其 hook。如果儲存破壞了模組，該行說 `reload failed, the previous version stays loaded:` 並帶有原因，最後一個可運作的版本會保持執行，直到 Claude Code 下次重新載入外掛為止，例如當您執行 `/reload-plugins` 時。

## 後續步驟

* [測試 mod](https://code.claude.com/docs/zh-TW/plugins/mods/test.md)：在問題到達工作階段之前捕捉它們
* [排除 plugin 的故障](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md)：安裝和載入 plugin 的問題，不特定於 mod

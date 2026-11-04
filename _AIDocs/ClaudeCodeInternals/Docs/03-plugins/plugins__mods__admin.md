<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/plugins/mods/admin | lastmod: 2026-10-26 | section: Plugins / Manage plugins for your organization -->
> 來源：https://code.claude.com/docs/zh-TW/plugins/mods/admin（官方 zh-TW，lastmod 2026-10-26）｜分類：Plugins › Manage plugins for your organization｜EN 摘要：Control Claude Code mods with managed settings: stop user-installed mods, allow only your own, review what a mod can do, and enforce policy with your own mod.

# 為您的組織管理 mods

> 使用受管設定控制 Claude Code mods：停止使用者安裝的 mods、僅允許您自己的 mods、檢查 mod 可以執行的操作，以及使用您自己的 mod 強制執行政策。

[mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md) 是在 Claude Code 內執行程式碼的外掛程式，具有安裝它的使用者的權限。Mods 不是沙箱化的。透過[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)，您可以決定 mods 是否在使用者的機器上執行、執行哪些 mods，以及執行順序。您也可以安裝自己的 mod，用來監視或拒絕其他 mods 的操作。

此頁面適用於為 Claude Code 部署受管設定的人員，無論是作為檔案、透過 MDM 或從 claude.ai 管理員主控台部署。在 Claude Code v2.1.286 及更新版本中，mod 預設為開啟。從與您要執行的操作相符的部分開始：

* **排除使用者自己的 mods，無論是否有您自己的 mods**：[停止使用者安裝的 mods 載入](#stop-user-installed-mods-from-loading)
* **查看當您不做任何更改時使用者會獲得什麼**：[了解預設情況下會發生什麼](#know-what-happens-by-default)
* **保持 mods 開啟並設定其他限制**：[選擇允許的程度](#choose-how-much-to-allow)

> [!NOTE]
>
> 這些情況在其他頁面上涵蓋：
>
> * **您之前未部署過受管設定**：從[部署受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)開始
> * **您想控制使用者可以安裝哪些外掛程式**：請參閱[為您的組織管理外掛程式](https://code.claude.com/docs/zh-TW/plugins/org.md)

## 停止使用者安裝的 mod 載入

若要防止使用者帶來的每個 mod 執行其 hook，請在[內建防護](#know-what-happens-by-default)上設定 `allowManagedModsOnly` 選項，這是一個原則 mod，Claude Code 會在使用者安裝的每個 mod 之前載入它。該選項位於受管設定中的 `pluginConfigs` 下，以 `cc-plugin-sec-default@builtin` 為鍵：

```json managed-settings.json theme={null}
{
  "pluginConfigs": {
    "cc-plugin-sec-default@builtin": {
      "options": {
        "allowManagedModsOnly": true
      }
    }
  }
}
```

在受管設定中設定此選項後：

* **使用者帶來的任何 mod 都不會執行其 hook**：這涵蓋使用者安裝的外掛中的 mod、使用 `--plugin-dir` 載入的 mod，以及 [Claude 在工作階段期間編寫的 mod](https://code.claude.com/docs/zh-TW/plugins/mods/create.md#ask-claude-for-a-mod)
* **您組織的 mod 仍會執行**：[計為您組織的](#install-your-organizations-mods) mod 不會被檢查。所有其他 mod 都計為使用者的 mod，並會遭到拒絕。這包括您從 GitHub 或其他遠端市集啟用的外掛中的 mod，以及您的組織為其成員在 claude.ai 上開啟的 mod。如果沒有任何 mod 計為您的，則不會有任何已安裝的 mod 執行其 hook。
* **使用者無法撤銷它**：防護只從受管設定讀取選項，因此使用者、專案或本機設定檔中的相同項目，或使用 `--settings` 傳遞的檔案中的項目，不會改變任何內容
* **檔案或 MDM 原則涵蓋每個提供者**：當您以檔案或透過 MDM 方式提供選項時，它在 Amazon Bedrock、Google Cloud 的 Agent Platform 和 Microsoft Foundry 上的運作方式相同。如需從 claude.ai 管理員主控台進行交付，請參閱[平台可用性](https://code.claude.com/docs/zh-TW/server-managed-settings.md#platform-availability)
* **使用者的其他自訂設定保持有效**：他們[設定檔中的 hook](https://code.claude.com/docs/zh-TW/hooks.md) 以及外掛 `hooks/hooks.json` 中的 hook、狀態列和 `/goal` 不受影響
* **內建 mod 保持執行**：內建於 Claude Code 的 mod（例如 `AGENTS.md` 支援）各有[自己的開關](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md#mods-built-into-claude-code)

若要確認使用者機器上的選項，請使用 `--plugin-dir` 和包含 mod 的目錄路徑（例如 `claude --plugin-dir ./first-mod`）在該處啟動 Claude Code。mod 的 hook 不會執行，逐字稿和偵錯日誌中會有[防護的訊息](https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot.md#messages-from-the-built-in-guard)，其中會指出該 mod 和 `allowManagedModsOnly`。如果沒有出現該訊息，請參閱[檢查原則是否有效](https://code.claude.com/docs/zh-TW/managed-settings.md#check-that-a-policy-is-in-force)和[決定選項是否生效的規則](#set-options-on-the-built-in-guard)。

如果您在早期存取期間將 `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` 設定為 `0`，請用此選項替換它。Claude Code v2.1.287 及更新版本在任何值下都會忽略該變數，因此其中的 `0` 會讓 mod 保持開啟。

## 了解預設情況下會發生什麼

如果您沒有自己的 mod 設定，這就是您的使用者會獲得的：

* **Mods 已開啟。** 使用者可以安裝包含來自您的外掛程式設定允許的任何市場的 mod 的外掛程式，或使用 `--plugin-dir` 從目錄載入一個。
* **內建防護首先執行。** Claude Code 在使用者安裝的每個 mod 之前載入名為 `sec-default@builtin` 的內建 mod。使用者無法將其關閉。`/plugin` 和偵錯日誌將其列為 `cc-plugin-sec-default`。防護在以下任一情況為真時載入：

  * 機器有受管設定
  * 工作階段使用 Team 或 Enterprise 計畫的 [`/login` 憑證](https://code.claude.com/docs/zh-TW/authentication#authentication-precedence)執行

  使用 API 金鑰進行身分驗證的使用者，或透過 Amazon Bedrock、Google Cloud 的 Agent Platform 或 Microsoft Foundry 進行身分驗證的使用者，只有在具有受管設定的機器上才能獲得防護。使用長期 [`CLAUDE_CODE_OAUTH_TOKEN`](https://code.claude.com/docs/zh-TW/authentication#generate-a-long-lived-token) 執行的工作階段也不算是該登入，即使機器上儲存了 Team 或 Enterprise 登入也是如此。
* **防護保護您管理的內容。** 使用者的 mod 無法更改您的受管 hooks 接收或決定的內容、系統提示、您的受管 `CLAUDE.md` 和其他受管指示、任何 mod 讀取的設定內容，或您的受管 MCP 伺服器的工具和描述。
* **在您管理的範圍之外，使用者的 mod 以該使用者的身分運作。** mod 保有該使用者的權限：它仍然可以讀取和寫入檔案、啟動程序，以及發出網路請求。它也可以重寫工具呼叫和提示詞、拒絕工具呼叫，以及在介面中繪製。
* **權限規則和 `PreToolUse` hook 優先於使用者的 mod。** 防護載入時，預設情況下，使用者的 mod 無法核准 `deny` 規則拒絕的呼叫或 `ask` 規則會提示確認的呼叫，無論哪個設定檔持有該規則。mod 也無法核准任何 `PreToolUse` hook 所封鎖的呼叫。

  權限規則和 `PreToolUse` hook 適用於 Claude 的工具呼叫，而不適用於 mod 的 [`$.fs` 和 `$.process` 呼叫](https://code.claude.com/docs/zh-TW/plugins/mods/api#reach-files-processes-and-the-network)。拒絕 `Read(.env)` 後，mod 仍然可以使用 `$.fs.read` 讀取該檔案，或啟動執行該操作的程式。若要限制 mod 自己的 `$.fs` 和 `$.process` 呼叫，請[防止 mod 載入](#stop-user-installed-mods-from-loading)，或在[原則 mod](#enforce-a-policy-with-a-mod-of-your-own) 中處理這些呼叫。
* **使用者的 mod 仍然可以略過某些提示。** 在[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)下，mod 核准的呼叫執行時不進行分類器檢查，除非防護已載入，且工作階段使用 [`--permission-prompt-tool`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 或 Agent SDK [`canUseTool` 回呼](https://code.claude.com/docs/zh-TW/agent-sdk/user-input#handle-tool-approval-requests)執行。在這種情況下，分類器會先檢查該呼叫。如需了解 mod 的核准不會略過的提示，請參閱[使用 hook 擴充權限](https://code.claude.com/docs/zh-TW/permissions.md#precedence-among-rules-hooks-and-mods)。

防護的來源在 [Claude Code 儲存庫的 `mods/sec-default` 目錄](https://github.com/anthropics/claude-code/tree/main/mods/sec-default)中是公開的。

### 了解哪些控制仍然適用

Mods 不會取代您已有的控制：

* **設定 hook 保持有效。** 設定檔和外掛程式 `hooks/hooks.json` 中的命令、HTTP、提示詞和 agent hook 像以前一樣執行，與 mod 並行。
* **拒絕規則在防護載入的地方優先。** 使用者的 mod 無法批准 `deny` 規則拒絕的呼叫，除非您設定 [`allowModsToOverrideDenyRules`](#set-options-on-the-built-in-guard)。
* **受管 hook 首先執行。** 受管設定中的 `PreToolUse` hook 在任何 mod 的 [`tool.call`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#tools) hook 之前執行，當該受管 hook 封鎖工具呼叫時，不會有任何 mod 的 `tool.call` hook 針對該呼叫執行。如果呼叫繼續進行且 mod 重寫了它，您的受管 hook 會在重寫的呼叫上再次執行，因此仍然可以封鎖它。

  來自其他設定檔和外掛的 `PreToolUse` hook 在最後一個 mod 之後執行。如果 mod 自行回應工具呼叫，工具就不會執行，這些 hook 也不會執行。請參閱 [mod 執行的順序](https://code.claude.com/docs/zh-TW/plugins/mods/events.md#the-order-mods-run-in)。
* **網路政策涵蓋 `$.http.fetch`。**

  * **您組織的政策不允許 WebFetch**：Claude Code 也會拒絕每個 mod 的 `$.http.fetch` 請求。請參閱 [WebFetch 可用性](https://code.claude.com/docs/zh-TW/tools-reference.md#webfetch-availability)。
  * **您在受管設定或任何其他設定檔中，使用 [`CLAUDE_CODE_DISABLE_WEB_FETCH`](https://code.claude.com/docs/zh-TW/env-vars#variables) 或 `WebFetch` [拒絕規則](https://code.claude.com/docs/zh-TW/permissions.md#tool-specific-permission-rules)關閉 WebFetch 工具**：mod 仍然可以發出 `$.http.fetch` 請求。

    若要對使用者安裝的每個 mod 阻止這些請求，請[防止使用者安裝的 mod 載入](#stop-user-installed-mods-from-loading)，或在[原則 mod](#enforce-a-policy-with-a-mod-of-your-own) 中 hook `http.fetch` 並拒絕來自使用者 mod 的請求。請為該 hook 提供同樣會拒絕的 [`.catch` 處理常式](https://code.claude.com/docs/zh-TW/plugins/mods/events#handle-a-hook-that-fails)，因為 Claude Code 會略過失敗的 hook，請求便會繼續進行。如果您只[限制使用者可以安裝哪些外掛程式](https://code.claude.com/docs/zh-TW/plugins/org.md#restrict-what-users-can-install)，載入的 mod 會變少，但您允許的 mod 仍然可以發出這些請求。
  * **您設定了 [`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`](https://code.claude.com/docs/zh-TW/env-vars)**：您或您的使用者安裝的 mod 仍然可以發出這些請求。此變數只會阻止 [Claude Code 內建的 mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md#mods-built-into-claude-code)，以及任何攜帶工作階段 Anthropic 憑證的 `$.http.fetch` 請求。在 v2.1.288 之前，此變數會阻止每個 mod 的 `$.http.fetch` 請求。

  這些都不涵蓋 mod 使用 `$.process.run` 啟動的程式，該程式會以使用者自己的存取權限連上網路。
* **外掛程式控制涵蓋 mods。** Mod 是外掛程式，因此[限制使用者可以安裝的設定](https://code.claude.com/docs/zh-TW/plugins/org.md#restrict-what-users-can-install)（例如 `strictKnownMarketplaces`）決定是否可以安裝它。
* **Mods 無法更改權限提示。** Mod 可以重新設定 Claude Code 介面的大部分，但不能重新設定權限提示，因此無法更改提示顯示的內容。Mod 仍然可以在提示出現之前批准或拒絕工具呼叫，如[了解預設情況下會發生什麼](#know-what-happens-by-default)所述。
* **信任提示優先。** 在使用者尚未信任的目錄中的互動工作階段中，在他們回答信任提示之前，沒有 mod 載入。
* **`--safe-mode` 關閉已安裝的 mods，包括您的。** 使用 `claude --safe-mode` 啟動工作階段以檢查 mod 是否導致問題。

這些控制都不會沙箱化 mod。您允許的 mod 以使用者身份執行，具有使用者對檔案、程序和網路的存取權限。

### 了解使用者 mod 的哪些 hook 不會執行

在[內建防護](#know-what-happens-by-default)載入的地方，使用者的 mod 在下列任一事件上註冊的 hook 永遠不會執行，而 `/plugin` 會以一則說明告知該使用者。在 [`session.append`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#session) 各列中，`door` 是該 hook 所篩選的儲存列類型。

| Hook 所在事件 | 事件內容 |
| :- | :- |
| [`classic.<Event>`](https://code.claude.com/docs/zh-TW/plugins/mods/events#hook-the-settings-hook-events)，例如 `classic.Stop` | [設定 hook 事件](https://code.claude.com/docs/zh-TW/hooks.md#hook-events) |
| [`prompt.compose`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#prompts-and-what-claude-reads) | 系統提示詞的區段清單 |
| `prompt.section` | 系統提示詞的單一區段 |
| `prompt.context` | 隨對話第一則訊息一起傳送的上下文 |
| `prompt.attachment` | Claude Code 為 Claude 加入的訊息，例如提醒 |
| `skill.prompt` | skill 為 Claude 展開時的文字 |
| `attribution.text` | 提交或 pull request 的署名文字 |
| [`session.compact`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#session) | 對話的壓縮 |
| `settings.read` | 對設定的讀取，例如 mod 的 `$.settings.read` 呼叫 |
| `session.append{door=attachment}` | Claude Code 為 Claude 加入之訊息的儲存列 |
| `session.append{door=hook-context}` | 來自設定 hook 之上下文的儲存列 |
| `session.append{door=compaction}` | 壓縮摘要與邊界的儲存列 |

防護在其他某些情況下也會略過使用者的 hook，例如 [`tool.describe`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#tools) 上您組織工具的描述，以及 skill 文字的儲存列。`/plugin` 對這些情況不會顯示說明。如果其他事件上的 hook 沒有任何作用，請參閱[找出 mod 沒有作用的原因](https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot.md#find-out-why-a-mod-does-nothing)。

該說明會出現在外掛程式的詳細資料中，以及 `/plugin` 的 **Errors** 分頁中。此功能需要 Claude Code v2.1.299 或更新版本。說明會依 mod 註冊時的名稱列出表格中的每個 hook，如下例所示：

```text theme={null}
Its hooks on classic.Stop, prompt.section do not run here: where an organization manages Claude Code, these events pass over the plugins you install
Only a plugin that counts as your organization's own runs hooks on these events. An administrator sets that up in managed settings
```

若要讓這些 hook 執行，請以下列兩種方式之一變更受管設定：

* **將 mod 作為您組織的 mod 執行**：[安裝該 mod，使其算作您組織自己的](#install-your-organizations-mods)。其在這些事件上的 hook 隨後便會執行，而防護對其他所有 mod 仍保持載入。該 mod 會對所有收到這些設定的人開啟，且必須位於您放置在每台機器上的目錄中。如果您將其列在 `prependPlugins` 中，請在清單中保留 `sec-default@builtin`。
* **移除防護**：在 `prependPlugins` 中省略 `sec-default@builtin`。空清單 `"prependPlugins": []` 即已足夠。您失去的是整個防護，而不只是這些事件。使用者的 mod 便可以做到[防護原本會阻止的事](#know-what-happens-by-default)，且[防護的選項](#set-options-on-the-built-in-guard)也不再適用。

如果您透過[伺服器管理的設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md#fetch-and-caching-behavior)傳送不含防護的清單，防護會保持載入，直到伺服器為該工作階段確認設定為止。若要在執行 v2.1.299 或更新版本的機器上確認任一變更，請在該機器的工作階段中開啟 `/plugin`，並確認說明已消失。

沒有 `door` 篩選條件的 `session.append` hook 仍會執行且不會顯示說明，但表格中的儲存列不會傳到它。

## 決定是否保持 mods 開啟

Mod 可以做的比外掛程式的其他部分更多，因為它在 Claude Code 內執行。它看到每個提示和工具呼叫，可以更改它們，並可以在權限提示出現之前允許或拒絕工具呼叫。

使用者可以載入為 mod 的內容取決於您已有的外掛程式控制：

| 您今天的外掛程式控制 | 使用者可以載入為 mod 的內容 |
| :- | :- |
| 無 | 來自任何市場、任何目錄（使用 `--plugin-dir`）或 Claude 在工作階段期間編寫的 mod |
| 市場允許清單 | 來自您允許的市場的 mod，或來自任何目錄（使用 `--plugin-dir`）的 mod。Claude 在工作階段期間編寫的 mod 只有在允許清單[包含 `skills-dir`](https://code.claude.com/docs/zh-TW/plugins/org#keep-skills-directory-plugins-loading) 時才會載入。 |
| 市場允許清單和 `disableSideloadFlags` | 來自您允許的市場的 mod |

[為您的組織管理外掛程式](https://code.claude.com/docs/zh-TW/plugins/org.md)列出外掛程式載入的每種方式和控制每種方式的設定。

若要在使用者安裝市場中的 mods 之前檢查它們，請參閱[檢查 mod 可以執行的操作](#review-what-a-mod-can-do)。若要在您完成此操作之前排除使用者的 mods，請參閱[停止使用者安裝的 mods 載入](#stop-user-installed-mods-from-loading)。

### 檢查 mod 可以執行的操作

您可以看到 mod 能夠執行的操作而無需執行它。在您的 shell 中，在外掛程式的目錄上執行 `claude plugin validate`：

```bash theme={null}
claude plugin validate ./some-mod
```

輸出中的 `hooks:` 和 `calls:` 行描述 mod 的程式碼：

```text theme={null}
  ❯ ./register.js hooks: session.start, tool.call, ui.render{component=Pane}
  ❯ ./register.js calls: $.fs.read, $.http.fetch, $.store.set, $.ui.open
```

`hooks:` 行列出 mod 接收的事件。`calls:` 行列出其程式碼呼叫的 mods API 方法。[mods API](https://code.claude.com/docs/zh-TW/plugins/mods/api.md)（在 mod 的程式碼中寫為 `$`）是 mod 到達檔案、程序和網路的方式。Claude Code 拒絕載入以此命令無法讀取的方式使用 mods API 的 mod。

查看 `calls:` 行以了解這些：

| 呼叫 | 它的意思 |
| :- | :- |
| `$.fs.read`, `$.fs.write` | 讀取或寫入使用者可以存取的任何地方的檔案 |
| `$.process.run`, `$.process.spawn` | 以使用者身份啟動程式 |
| `$.http.fetch` | 發出網路請求 |
| `$.env.get`, `$.settings.read` | 讀取環境變數和設定，可以保存 API 金鑰。輸出中的 `env reads:` 行命名每個變數。 |
| `$.env.set` | 為 Claude Code 和它啟動的每個命令和 MCP 伺服器設定環境變數，可以更改這些程式執行的內容。`env writes:` 行命名每個變數。 |
| `$.mcp.call` | 在連接的 MCP 伺服器上呼叫工具，受工作階段的權限規則約束 |
| `$.model.complete` | 使用使用者的計畫或 API 金鑰進行模型呼叫 |
| `$.prompt.submit` | 提交提示，可以將其作為使用者自己的話語發送 |
| `$.session.send` | 發送另一個工作階段、subagent 或[隊員](https://code.claude.com/docs/zh-TW/agent-teams.md)的 Claude 讀取的訊息 |

在 `hooks:` 行中，[`tool.call`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#tools) 和 [`prompt.submit`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#prompts-and-what-claude-reads) 表示 mod 看到每個工具呼叫和每個提示詞，並可以更改它們。[`session.append`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#session) 表示 mod 可以在儲存前重寫對話的每一行，但[防護機制略過的行](#hooks-the-guard-passes-over)除外。[`ui.render{component=AskUserQuestion}`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#change-what-claude-code-already-draws) 表示 mod 可以重繪 Claude 用來詢問使用者問題的對話框。`tool.check` 表示 mod 可以在權限提示出現之前批准或拒絕工具呼叫。[了解預設情況下會發生什麼](#know-what-happens-by-default)列出您的哪些規則和 hook 優先於其答案。

## 選擇允許的程度

Mod 政策的範圍從根本沒有已安裝的 mod 到使用者選擇的任何 mod，以及您自己的 mod 檢查其他 mod，每一個都是幾個受管設定。在第一列中找到您想要的政策，並設定第二列命名的內容。[部署受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)涵蓋受管設定的位置。

| 您想要的 | 設定 |
| :- | :- |
| 不執行任何已安裝的 mod，設定 hook 不受影響 | 設定 [`allowManagedModsOnly`](#set-options-on-the-built-in-guard) 並且不部署您自己的 mod |
| 沒有已安裝的 mod 和根本沒有 hook，包括您的受管 hook | 將 `disableAllHooks` 設定為 `true` |
| 僅您組織的 mod | 設定防護的 [`allowManagedModsOnly` 選項](#stop-user-installed-mods-from-loading)，並[安裝您的 mod](#install-your-organizations-mods) 使其計為您的 |
| 來自您批准的市集的任何 mod | 保持您的[市集限制](https://code.claude.com/docs/zh-TW/plugins/org.md#restrict-what-users-can-install)，並將 `disableSideloadFlags` 設定為 `true` |
| 任何 mod，您自己的 mod 檢查其他 mod | [安裝您的 mod](#install-your-organizations-mods)，並在 `prependPlugins` 中與 `sec-default@builtin` 一起列出它 |

每個設定的作用：

* **`allowManagedModsOnly`**：內建防護上的選項。Claude Code 會拒絕使用者自己的 mod，因此他們的 hook 都不會執行。使用者的設定 hook、狀態列和 `/goal` 保持有效。[停止使用者安裝的 mod 載入](#stop-user-installed-mods-from-loading)列出它涵蓋的內容。
* **`allowManagedHooksOnly`**：更廣泛的設定。只有[您組織的 mod](#install-your-organizations-mods) 和內建於 Claude Code 的 mod 載入。使用者自己安裝的 mod 不會。該設定也會阻止使用者自己設定檔中的 hook。在設定之前，請閱讀[在 `allowManagedHooksOnly` 下執行的內容](https://code.claude.com/docs/zh-TW/settings-reference#what-runs-under-allowmanagedhooksonly)。
* **`disableAllHooks`**：最廣泛的設定。在受管設定中，它停止每個已安裝外掛中的 mod，包括您的，並關閉設定檔中的每個 hook，因此您受管設定中的 `PreToolUse` hook 不再阻止任何內容。自訂狀態列和 `/goal` 也停止工作。在設定之前，請閱讀 [`disableAllHooks`](https://code.claude.com/docs/zh-TW/settings-reference#disableallhooks)。
* **`disableSideloadFlags`**：在啟動時拒絕 `--plugin-dir` 和 `--plugin-url`，並防止 Claude 在工作階段期間編寫的 mod 載入。該設定也拒絕 `--agents` 和 `--mcp-config`。在設定之前，請閱讀 [`disableSideloadFlags`](https://code.claude.com/docs/zh-TW/settings-reference#disablesideloadflags)。

內建於 Claude Code 的 mod（例如 `AGENTS.md` 支援）不受這些設定影響。每個都有[自己的開關](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md#mods-built-into-claude-code)。

mod 遭到拒絕或未載入的使用者，可在其偵錯日誌中找到原因。[拒絕訊息](https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot.md#refusal-messages)列出 `allowManagedHooksOnly` 和 `disableAllHooks` 的行，[來自內建防護的訊息](https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot.md#messages-from-the-built-in-guard)有 `allowManagedModsOnly` 的行。

### 僅允許您組織的 mod

若要執行您組織的 mod 並阻止使用者帶來的 mod，請部署[政策表格](#choose-how-much-to-allow)中 **僅您組織的 mod** 一列的設定，再加上 `disableSideloadFlags`。使用這份完整的 `managed-settings.json`，Claude Code 會拒絕使用者自己的 mod，因此他們的 hook 都不會執行，而您的原則 mod 會在其他 mod 之前執行：

```json managed-settings.json theme={null}
{
  "extraKnownMarketplaces": {
    "acme-tools": {
      "source": { "source": "directory", "path": "/opt/acme/claude-plugins" }
    }
  },
  "enabledPlugins": { "acme-guard@acme-tools": true },
  "prependPlugins": ["acme-guard@acme-tools", "sec-default@builtin"],
  "pluginConfigs": {
    "cc-plugin-sec-default@builtin": {
      "options": { "allowManagedModsOnly": true }
    }
  },
  "disableSideloadFlags": true
}
```

每組鍵各負責一項工作：

* **`extraKnownMarketplaces`、`enabledPlugins` 和 `prependPlugins`**：安裝您的 mod 使其計為您的，並讓它最先執行，防護在其後執行。[安裝您組織的 mod 並設定順序](#install-your-organizations-mods)涵蓋這些鍵所指向的目錄。
* **`pluginConfigs`**：設定防護的 `allowManagedModsOnly` 選項，使 Claude Code 拒絕使用者自己的 mod。他們的設定 hook、狀態列和 `/goal` 保持有效。
* **`disableSideloadFlags`**：請參閱 [`disableSideloadFlags`](https://code.claude.com/docs/zh-TW/settings-reference#disablesideloadflags) 了解它在啟動時拒絕的旗標

若要在測試機器上確認政策，請在您的 shell 中以 `claude --debug` 啟動工作階段並閱讀偵錯日誌：

* **您的 mod**：其 `hooks module` 行含有 `tier prepend`
* **使用者安裝的 mod**：有一行顯示 `refused by cc-plugin-sec-default: mods are limited to your organization's by policy (allowManagedModsOnly)`。較早的一行會顯示該 mod 的 hook 模組為 `loaded`，因此請尋找拒絕訊息。
* **外掛目錄**：`claude --plugin-dir ./any-mod` 會結束並顯示以 `--plugin-dir is disabled by your organization's managed settings (disableSideloadFlags)` 開頭的訊息

若也要限制使用者可以新增哪些市集，請將此檔案與您的[市集限制](https://code.claude.com/docs/zh-TW/plugins/org.md#restrict-what-users-can-install)結合使用。

### 將您的外掛控制套用至 mod

Mod 是一種外掛，因此您[為組織管理外掛](https://code.claude.com/docs/zh-TW/plugins/org.md)的方式也適用於包含 mod 的外掛：

* **查看您整個機群中載入了哪些外掛**：[稽核與審查](https://code.claude.com/docs/zh-TW/plugins/org.md#audit-and-review)
* **決定您審查過的外掛何時可以更新**：[設定更新政策](https://code.claude.com/docs/zh-TW/plugins/org.md#set-update-policy)
* **為某個群組（例如試行群組）提供不同的政策**：[為受管設定無法強制執行的部分做規劃](https://code.claude.com/docs/zh-TW/plugins/org.md#plan-for-what-managed-settings-can’t-enforce)
* **檢查哪些應用程式和工作階段類型會套用外掛鍵**：[各使用介面何時套用外掛鍵](https://code.claude.com/docs/zh-TW/plugins/org.md#when-each-surface-applies-the-plugin-keys)
* **設定 CI 和容器**：[預先配置容器和 CI](https://code.claude.com/docs/zh-TW/plugins/org.md#seed-containers-and-ci)
* **提供使用者可以安裝的 mod**：[託管市集](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md)。Claude Code 從 GitHub、git、URL 或 npm 來源複製的 mod 會計為使用者的，而不是[您組織的](#install-your-organizations-mods)。

### 在內建防護上設定選項

內建防護接受選項。在受管設定中的 `pluginConfigs` 下設定它們，以 `cc-plugin-sec-default@builtin` 為鍵，如[停止使用者安裝的 mod 載入](#stop-user-installed-mods-from-loading)中的範例所示。

下表列出每個選項未設定和設定為 `true` 時，您的使用者會得到的結果：

| 選項 | 未設定 | `true` |
| :- | :- | :- |
| `allowManagedModsOnly` | 使用者自己的 mod 會執行 | 只有[您組織的 mod](#install-your-organizations-mods) 和內建於 Claude Code 的 mod 會執行其 hook。Claude Code 拒絕所有其他 mod，包括使用者安裝的或使用 `--plugin-dir` 命名的。 |
| `allowModsToOverrideDenyRules` | 拒絕規則優先於使用者的 mod | 批准工具呼叫的使用者 mod 可以批准 `deny` 規則拒絕的呼叫 |

這些規則決定選項是否生效：

* **id 在這裡只有一種形式**：Claude Code 只在 `cc-plugin-sec-default@builtin` 下讀取選項。`prependPlugins` 也接受 `sec-default@builtin`，而 `pluginConfigs` 不接受。
* **只有受管設定才算數**：使用者、專案或本機設定檔中的相同項目，或使用 `--settings` 傳遞的檔案中的項目，既不會設定選項，也不會放寬選項
* **防護必須載入**：如果您設定 `prependPlugins`，請[在清單中列出防護](#install-your-organizations-mods)。防護未載入之處，兩個選項都不適用。
* **防護採失敗即關閉**：如果防護無法讀取受管設定，它會在載入時拒絕每個使用者的 mod。如果它無法針對使用者的 mod 所批准的呼叫檢查拒絕規則，它會拒絕該呼叫。

[來自內建防護的訊息](https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot.md#messages-from-the-built-in-guard)是您的使用者在任一選項適用時看到的內容。

## 執行您組織自己的 mod

您可以將您自己的 mod 部署到每個使用者，選擇它們相對於使用者 mod 的執行位置，並使用一個來強制執行原則。

### 安裝您組織的 mod 並設定順序

您組織的 mod 在使用者 mod 不載入的地方載入，並可以在它們之前執行，因此 Claude Code 必須能夠判斷 mod 來自您。它只在以下所有條件都成立時才將 mod 視為您組織的：

* 受管 `enabledPlugins` 將 mod 的外掛設定為 `true`
* 受管設定以絕對路徑將外掛的[市集](https://code.claude.com/docs/zh-TW/plugins/create-marketplace.md)指定為使用者機器上的目錄。`extraKnownMarketplaces` 項目可做到這一點，並同時為使用者註冊該市集。
* 市集以相對路徑列出外掛，因此 Claude Code [從該目錄就地載入它](https://code.claude.com/docs/zh-TW/plugins/loading.md#in-place-and-copied-plugins)

為了滿足這些條件，請讓您的裝置管理將市集目錄複製到每台機器上的相同路徑。使該目錄及其上方的每個目錄只能由管理員寫入，如同受管設定檔一樣。任何可以在那裡寫入的人都可以重寫您的 mod。您從 claude.ai 管理員主控台交付的受管設定可以攜帶這些設定鍵，但無法將目錄放到機器上。

該目錄包含市集的清單檔和外掛：

```text theme={null}
/opt/acme/claude-plugins/
├── .claude-plugin/
│   └── marketplace.json
└── plugins/
    └── acme-guard/
        ├── .claude-plugin/
        │   └── plugin.json
        └── hooks/
            ├── hooks.json
            └── register.js
```

清單檔以相對於該目錄的路徑列出外掛：

```json /opt/acme/claude-plugins/.claude-plugin/marketplace.json theme={null}
{
  "name": "acme-tools",
  "owner": { "name": "Acme" },
  "plugins": [
    { "name": "acme-guard", "source": "./plugins/acme-guard", "description": "Acme policy mod" }
  ]
}
```

Claude Code 複製到其快取中的外掛會被視為使用者的，即使受管 `enabledPlugins` 啟用了它。這涵蓋來自 GitHub、git、URL 或 npm 來源的每個外掛。其 mod 在使用者的 mod 之間執行，`prependPlugins` 和 `appendPlugins` 會跳過它，`allowManagedModsOnly` 會拒絕它，而 `allowManagedHooksOnly` 會使它無法載入。使用者的偵錯日誌中會有一行以外掛的 id 和 `is enabled by managed settings, but` 開頭。

Claude Code 每次即將採取行動（例如執行工具）時都會引發事件，並依次將其傳遞給每個 mod。被視為您的 mod [會在使用者的 mod 之前執行](https://code.claude.com/docs/zh-TW/plugins/mods/events.md#the-order-mods-run-in)，即使您在任何地方都沒有列出它。若要設定其位置，請在兩個設定之一中列出其 id。id 是外掛的名稱、`@` 和市集的名稱，例如 `acme-guard@acme-tools`。

* **`prependPlugins`**：您的 mod 在任何使用者的 mod 之前看到每個事件，並在之後看到每個結果。它可以更改事件、拒絕它或跳過使用者的 mod。
* **`appendPlugins`**：您的 mod 在每個使用者的 mod 之後執行，因此它只看到這些 mod 傳遞的事件，以及它們傳遞的形式

此範例在 `/opt/acme/claude-plugins` 宣告 `acme-tools` 市集，從中啟用 `acme-guard`，並首先執行該 mod，內建防護在其後：

```json managed-settings.json theme={null}
{
  "extraKnownMarketplaces": {
    "acme-tools": {
      "source": { "source": "directory", "path": "/opt/acme/claude-plugins" }
    }
  },
  "enabledPlugins": { "acme-guard@acme-tools": true },
  "prependPlugins": ["acme-guard@acme-tools", "sec-default@builtin"]
}
```

每個設定鍵負責一項工作：

* **`extraKnownMarketplaces`**：指定包含 `acme-tools` 市集的目錄。`path` 是包含 `.claude-plugin/marketplace.json` 的目錄的絕對路徑。
* **`enabledPlugins`**：為接收這些受管設定的每個使用者開啟 `acme-guard`
* **`prependPlugins`**：將 `acme-guard` 放在首位，內建防護放在第二位，兩者都在使用者安裝的任何 mod 之前。Claude Code 遵循您列出的順序。

若要確認使用者的機器收到了設定，請參閱[檢查原則是否有效](https://code.claude.com/docs/zh-TW/managed-settings.md#check-that-a-policy-is-in-force)。

若要確認 mod 執行的位置，請在該機器上使用 `claude --debug` 啟動工作階段，並在[偵錯日誌](https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot.md#read-the-debug-log)中搜尋 mod 的 id：

* **`hooks module acme-guard@acme-tools loaded`，帶有 `tier prepend`**：mod 被視為您組織的並首先執行
* **相同的行帶有 `tier user`**：Claude Code 將其視為使用者的 mod。第二行 `prependPlugins names acme-guard@acme-tools, which is not an enabled managed plugin with a hooks module; skipped` 表示清單跳過了它。

這些規則決定兩個清單中的哪些 id 生效：

* **清單取代預設值**：當您在受管設定中設定 `prependPlugins` 時，請在其中列出 `sec-default@builtin` 以保留內建防護。防護是內建的，不需要 `enabledPlugins` 項目。
* **您自己的 id 必須被視為您的**：在受管設定中，Claude Code 會跳過其外掛不符合組織 mod 條件的 id
* **儲存庫無法設定它們**：Claude Code 從受管設定讀取這兩個設定，從不從儲存庫的設定檔讀取。使用者只有在沒有受管設定的機器上，且工作階段的憑證不是 Team 或 Enterprise 的 `/login` 時，才能在 `~/.claude/settings.json` 中設定它們以排序自己的 mod。在其他任何情況下，Claude Code 會忽略使用者設定中的這兩個設定鍵。那裡的清單既不會加入也不會移除內建防護。

### 使用您自己的 mod 強制執行原則

若要排除每個使用者的 mod，您不需要自己的 mod。請設定 [`allowManagedModsOnly`](#stop-user-installed-mods-from-loading)。當您想要允許某些使用者的 mod 並拒絕其他的，或記錄 mod 執行的操作時，請編寫原則 mod。

每次另一個 mod 即將載入時，您的 mod 會在名為 [`plugin.register`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#other-mods) 的事件中接收 `claude plugin validate` 列印的清單。`prependPlugins` 中的 mod 可以讀取該清單並拒絕該 mod。它也可以[按名稱處理任何 mods API 呼叫](https://code.claude.com/docs/zh-TW/plugins/mods/api.md#reach-files-processes-and-the-network)，以記錄或拒絕所有其他 mod 的該呼叫。名稱是不含 `$.` 的方法，因此 `fs.write` 上的 hook 會看到每個 `$.fs.write` 呼叫。

此原則 mod 會拒絕任何自身程式碼呼叫 `$.process.run` 或 `$.process.spawn` 的使用者 mod。它也會保留稽核日誌，將每個工具呼叫和每個 mod 寫入的檔案寫入偵錯日誌。因為它首先執行，日誌會在任何使用者的 mod 更改之前記錄所請求的內容。將其儲存為 `acme-guard/hooks/register.js`：

```javascript acme-guard/hooks/register.js theme={null}
// The methods no user's mod may call, each spelled namespace.method
const BLOCKED_CALLS = ['process.run', 'process.spawn']

export function register(on) {
  // Runs each time another mod is about to load
  on('plugin.register', async ($, e, next) => {
    // Keep the calls in that mod's code that are on the blocked list
    const blocked = e.uses.calls.filter((call) => BLOCKED_CALLS.includes(call))
    if (e.tier === 'user' && blocked.length > 0) {
      // Returning refuse keeps the mod from loading, and the text is the reason
      return { refuse: 'Acme policy: mods may not call ' + blocked.join(', ') }
    }
    // Let every other mod load
    return next(e)
  })

  // Record each tool call, then let it go ahead unchanged
  on('tool.call', async ($, e, next) => {
    $.ui.log('audit tool.call ' + e.tool, { to: 'debug' })
    return next(e)
  })

  // Record which mod wrote a file, then the path, quoted because the mod chose it
  on('fs.write', async ($, e, next) => {
    $.ui.log('audit fs.write by ' + next.origin.plugin + ' ' + JSON.stringify(e.path), { to: 'debug' })
    return next(e)
  })
}
```

該檔案註冊三個 hook：

* **`plugin.register`**：決定另一個 mod 是否載入。它拒絕呼叫被封鎖方法的使用者 mod，並放行所有其他 mod。
* **`tool.call`**：為每個工具呼叫寫入一行（例如 `audit tool.call Bash`）到偵錯日誌，且不改變任何內容
* **`fs.write`**：為另一個 mod 發出的每個 `$.fs.write` 呼叫寫入一行（例如 `audit fs.write by reader "/tmp/notes.md"`），且不改變任何內容。mod 的名稱在前，路徑加上引號，因此 mod 選擇的路徑無法偽裝成該行的另一個欄位。

`plugin.register` hook 讀取事件的兩個欄位：

* **`e.tier`**：mod 將執行的位置，為 `prepend`、`user`、`append` 或 `builtin` 之一。使用者安裝的每個 mod 都是 `user`。
* **`e.uses.calls`**：mod 呼叫的 mods API 方法，每個寫成 `namespace.method`（例如 `process.run`），不帶 `claude plugin validate` 列印的 `$.`

當使用者安裝呼叫 `$.process.run` 的 mod 時，該 mod 不會載入，其偵錯日誌中會有一行以 `refused by acme-guard:` 和您的原因結尾。在[熱重新載入外掛目錄的工作階段](https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot.md#find-out-why-a-mod-does-nothing)中，拒絕訊息也會出現在逐字稿中。若要封鎖某個呼叫而不拒絕整個 mod，請從該呼叫名稱上的 hook 傳回 `{ deny: 'your reason' }`。

若要將稽核行傳送到偵錯日誌以外的地方，請從相同的 hook 呼叫 `$.http.fetch`。

工作階段可能在沒有您的 mod 的情況下執行。如果執行已安裝 mod 的工作執行緒[當機三次](https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot.md#mods-that-run-in-the-hooks-worker-are-off-for-this-session)，Claude Code 會卸載所有非內建的 mod（包括您的），直到使用者執行 `/reload-plugins` 或啟動新工作階段。而使用 `--safe-mode` 啟動 Claude Code 的使用者，會在沒有已安裝 mod 的情況下執行，包括您的。

[建立 mod](https://code.claude.com/docs/zh-TW/plugins/mods/create.md) 涵蓋 mod 需要的檔案。[測試原則 mod](https://code.claude.com/docs/zh-TW/plugins/mods/test.md#test-a-mod-that-judges-other-mods) 提供此原則 mod 的測試檔案。

#### 當您的檢查失敗時拒絕 mod

如果您的 `plugin.register` hook 拋出例外或超過其時間限制，Claude Code 會跳過該 hook，因此檢查會以開放方式失敗，正在檢查的 mod 會載入。若要以關閉方式失敗並拒絕使用者的 mod，請將檢查移到具名函式中，並加入傳回拒絕的 `.catch` 處理程式。此版本的檔案僅顯示 `plugin.register` hook，因此請在 `register` 中保留第一個版本的兩個稽核 hook：

```javascript acme-guard/hooks/register.js theme={null}
const BLOCKED_CALLS = ['process.run', 'process.spawn']

// The same check as before, moved into a function of its own
async function checkMod($, e, next) {
  const blocked = e.uses.calls.filter((call) => BLOCKED_CALLS.includes(call))
  if (e.tier === 'user' && blocked.length > 0) {
    return { refuse: 'Acme policy: mods may not call ' + blocked.join(', ') }
  }
  return next(e)
}

export function register(on) {
  // The handler runs only when checkMod throws or exceeds its time limit
  on('plugin.register', checkMod).catch(async ($, e, next) => {
    // Let your organization's mods and built-in mods load
    if (e.tier !== 'user') return next(e)
    // Refuse the user's mod that couldn't be checked
    return { refuse: 'Acme policy check failed, so this mod was not loaded' }
  })
}
```

處理程式就位後，在檢查拋出例外或逾時時正在被檢查的 mod 不會載入，拒絕行會帶有第二個原因，如 `refused by acme-guard: Acme policy check failed, so this mod was not loaded`。處理程式將 `user` 層以外的每個 mod 傳遞給 `next(e)`，因此失敗的檢查不會阻止您組織列出的 mod。[處理失敗的 hook](https://code.claude.com/docs/zh-TW/plugins/mods/events.md#handle-a-hook-that-fails) 涵蓋其他事件的 `.catch`。

## 後續步驟

* [外掛程式安全性](https://code.claude.com/docs/zh-TW/plugins/security.md)：任何外掛程式在使用者機器上可以執行的操作，以及如何在安裝前檢查一個
* [Mods 概述](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md)：什麼是 mod 以及它與 hooks、skills 和 MCP 伺服器的比較
* [mods 執行的順序](https://code.claude.com/docs/zh-TW/plugins/mods/events.md#the-order-mods-run-in)：`prependPlugins` 和 `appendPlugins` 如何與使用者 mods 配合
* [設定和環境變數](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#settings-and-environment-variables)：此頁面上命名的每個設定在一個表格中

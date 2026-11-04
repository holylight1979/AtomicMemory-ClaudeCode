<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/plugins/mods/overview | lastmod: 2026-10-20 | section: Plugins / Mods -->
> 來源：https://code.claude.com/docs/zh-TW/plugins/mods/overview（官方 zh-TW，lastmod 2026-10-20）｜分類：Plugins › Mods｜EN 摘要：Add panes, commands, and tool call rules to Claude Code with a mod. See what a mod can do, how to make or install one, and where mods run.

# Mods 概覽

> 透過 mod 為 Claude Code 新增窗格、命令與工具呼叫規則。了解 mod 能做什麼、如何製作或安裝 mod，以及 mod 在何處執行。

mod 是一種會改變 Claude Code 外觀與行為的[外掛](https://code.claude.com/docs/zh-TW/plugins/overview.md)。它由 JavaScript 或 TypeScript 事件處理常式組成：當事件發生時（例如工具呼叫、提交提示詞，或繪製介面的某個部分），Claude Code 會呼叫對應的處理常式，而處理常式可以監看該事件、變更它，或完全接管它。您可以使用 mod 為 Claude Code 新增自己的功能，例如一個在每次請求後以圖表呈現 context 使用量的窗格。如需了解 mod 中包含的檔案以及完整範例，請參閱 [mod 的運作方式](#how-a-mod-works)。

> [!NOTE]
>
> Claude Code 既有的 [hooks](https://code.claude.com/docs/zh-TW/hooks.md) 也會在事件發生時執行，其形式是您在設定檔中設定的 shell 命令、HTTP 請求或提示詞。相對地，mod 的處理常式則是在 Claude Code 內部執行的函式，而非上述形式。Claude Code 將這兩種都稱為 hook：在這些頁面中，「hook」指的是 mod 的處理常式，而設定檔中的那種則稱為「設定 hook」。

## Mod 可以做什麼

設定 hooks、skills、狀態行和 MCP 伺服器從 Claude Code 外部運作：每一個都執行指令碼，或為 Claude 提供文字或工具。Mod 在 Claude Code 內執行，因此它可以做他們無法做的事情：

* **繪製您可以使用的介面**：文字記錄旁邊的窗格或提示上方的帶狀區域，具有標籤、按鈕和文字欄位。請參閱[在介面中繪製](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md)。
* **重新繪製 Claude Code 自己的介面**：取代或重新設定 Claude Code 自己繪製的部分，例如工具呼叫的列、微調器或 Claude 提出問題的對話框。請參閱[變更 Claude Code 已繪製的內容](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md#change-what-claude-code-already-draws)。
* **進入工具呼叫或請求**：例如，在您詢問使用者問題時保留工具呼叫、在不執行工具的情況下回答，或將一個請求傳送到不同的模型。請參閱[保護或變更工具呼叫](https://code.claude.com/docs/zh-TW/plugins/mods/events.md#guard-or-change-a-tool-call)和[跟隨一個回合](https://code.claude.com/docs/zh-TW/plugins/mods/events.md#follow-a-turn)。
* **在命令上執行您自己的程式碼**：一個 `/command`，立即執行您的函式，沒有 Claude 回合，即使 Claude 正在工作。請參閱[新增命令或工具](https://code.claude.com/docs/zh-TW/plugins/mods/api.md#add-a-command-or-a-tool)。
* **在 hooks 之間共享資料**：mod 的 hooks 共享其檔案中的變數，因此一個 hook 記錄的內容，另一個可以顯示。例如，一個 hook 可以計算工具呼叫，而另一個在微調器旁邊顯示計數，或一個可以讀取每個請求的權杖使用量，而另一個在窗格中繪製它。請參閱[對事件做出反應](https://code.claude.com/docs/zh-TW/plugins/mods/events.md)。

Mod 可在 Claude Code CLI、Claude Desktop 應用程式的 Code 標籤以及 VS Code 擴充功能中運作。請參閱[mod 執行的位置](#where-mods-run)以了解它們在其他地方的行為，例如在 `claude -p` 和雲端工作階段中。如果設定 hook、skill 或 MCP 伺服器已經做了您需要的事情，在您編寫 mod 之前[比較它們](#compare-mods-settings-hooks-skills-and-mcp-servers)。若要為組織管理 mod，請參閱[為您的組織管理 mod](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md)。

## 取得 mod

若要開始使用 mod：

* **使用您已經擁有的**：Claude Code 的某些功能是 mods，例如 `/diff`。請參閱[內建於 Claude Code 的 Mods](#mods-built-into-claude-code)。
* **建立一個**：在 Claude Code 工作階段中描述您想要的內容，Claude 會編寫 mod。請參閱[向 Claude 要求 mod](https://code.claude.com/docs/zh-TW/plugins/mods/create.md#ask-claude-for-a-mod)。若要了解 mod 程式碼的運作方式，[自己編寫一個](https://code.claude.com/docs/zh-TW/plugins/mods/create.md#write-a-mod-yourself)。
* **安裝一個**：請參閱[安裝或更新 mod](#install-or-update-a-mod)，或[試用範例 mod](#try-a-sample-mod)

### 安裝或更新 mod

> [!WARNING]
>
> Mod 是使用您的權限執行的程式碼。它可以讀取和寫入您的檔案、啟動程序和發出網路請求。僅從您信任的作者和市集安裝 mods。請參閱[決定是否信任 mod](#decide-whether-to-trust-a-mod)。

Mod 作為外掛程式從市集安裝。提供外掛程式的名稱、`@` 和市集的名稱。這些範例從名為 `your-org` 的市集安裝名為 `token-chart` 的外掛程式：

* 在 Claude Code 工作階段中，執行 `/plugin install token-chart@your-org`。
* 在您的 shell 中，執行 `claude plugin install token-chart@your-org`。

[安裝外掛程式](https://code.claude.com/docs/zh-TW/plugins/install.md)涵蓋市集、範圍、VS Code 擴充功能和 Desktop 應用程式，以及[保持外掛程式更新](https://code.claude.com/docs/zh-TW/plugins/install.md#keep-plugins-updated)，所有這些都適用於包含 mod 的外掛程式，無需變更。

如果您在工作階段開啟時從 shell 安裝或更新 mod，請在該工作階段中執行 `/reload-plugins` 以載入它。否則，它會在您下次啟動 Claude Code 時載入。

### 試用範例 mod

Anthropic 在 [`claude-code-playground` 儲存庫的 `claude-code/mods` 目錄](https://github.com/anthropics/claude-code-playground/tree/main/claude-code/mods)中分享範例 mods。每一個都是完整的外掛程式，其 README 說明了它的建構方式。該儲存庫按原樣分享這些範例，不提供支援。

* [`token-weather`](https://github.com/anthropics/claude-code-playground/tree/main/claude-code/mods/token-weather)：在提示詞上方繪製您上下文視窗的預報
* [`blast-radius`](https://github.com/anthropics/claude-code-playground/tree/main/claude-code/mods/blast-radius)：暫停有風險的 shell 命令（例如 `rm -rf` 或強制推送），並顯示它會變更的內容，附有繼續或取消的按鈕
* [`replay-theater`](https://github.com/anthropics/claude-code-playground/tree/main/claude-code/mods/replay-theater)：新增 `/replay` 命令，逐步檢視 Claude 在上一個回合中所做的檔案編輯

範例 mod 會使用您的權限執行。若要在載入之前了解它的作用，請[列出它的 hook 和呼叫](#list-what-a-mod-does-before-you-install-one)。

若要試用，請複製該儲存庫，並使用 `--plugin-dir` [在單一工作階段中載入 mod 的目錄](https://code.claude.com/docs/zh-TW/plugins/create.md#load-a-directory-or-archive-for-one-session)。若要確認 mod 已載入，請[檢查工作階段載入了哪些 mods](#see-which-mods-a-session-loaded)。

若要保留它，請[將複製的 `claude-code/mods` 目錄新增為市集](https://code.claude.com/docs/zh-TW/plugins/install#add-a-marketplace)，然後從 `claude-code-playground-mods` 安裝該 mod。該市集指向您的複製，因此如果您移動或刪除它，mod 就會停止載入。

## 決定是否信任 mod

Mod 是使用您的權限在 Claude Code 內執行的程式碼。僅從您信任的作者和[市集](https://code.claude.com/docs/zh-TW/plugins/security.md)安裝 mods。

### Mod 可以存取什麼

Mod 使用您的權限執行，因此在您安裝一個之前，請了解它可以存取什麼。載入後，mod 可以：

* **在您的機器上以您的身份行動**：讀取和寫入您的使用者帳戶可以存取的任何地方的檔案、啟動程式和發出網路請求
* **讀取您的機密**：環境變數和設定檔，包括您保留在任一個中的 API 金鑰
* **查看您的工作階段**：您傳送的每個提示詞和 Claude 進行的每個工具呼叫
* **變更您的工作階段**：重寫提示詞或工具呼叫、提交提示詞，就像您輸入的一樣，或傳送訊息到您的另一個工作階段
* **在不詢問您的情況下行動**：在詢問您之前核准工具呼叫
* **花費您的使用量**：在您的計畫或 API 金鑰上呼叫模型

Mods 不在沙箱中執行。如果您開啟[沙箱機制](https://code.claude.com/docs/zh-TW/sandboxing.md)，沙箱會隔離 Claude 執行的 Bash 命令，而 mod 啟動的程序則會在沙箱之外執行。

當工作階段使用[受管設定](https://code.claude.com/docs/zh-TW/settings.md#check-what-your-organization-enforces)，或以 Team 或 Enterprise [`/login`](https://code.claude.com/docs/zh-TW/authentication#authentication-precedence) 作為工作階段的憑證時，預設情況下，mod 的核准無法讓呼叫繞過您的 `ask` 規則或 `PreToolUse` hook。若兩者皆無，mod 可以核准 `ask` 規則會提示的呼叫，或您的 `PreToolUse` hook 阻止的呼叫。若要確認 mod 何時也能核准 `deny` 規則拒絕的呼叫，請參閱[使用 hook 擴展權限](https://code.claude.com/docs/zh-TW/permissions.md#precedence-among-rules-hooks-and-mods)。

Mod 可以重新設定 Claude Code 介面的大部分，但不能重新設定權限提示。它無法變更提示顯示給您的內容。

### 在安裝 mod 之前列出它的功能

在您安裝 mod 之前，您可以列出它處理的事件以及它要求 Claude Code 執行的操作，例如讀取檔案或發出網路請求，而無需執行它。首先取得外掛程式的檔案，例如透過複製其儲存庫。然後，在您的 shell 中，在外掛程式的目錄上執行 `claude plugin validate`：

```bash theme={null}
claude plugin validate ./some-mod
```

輸出中的 `hooks:` 和 `calls:` 行列出 mod 處理的事件以及它要求 Claude Code 執行的操作。[檢查 mod 可以做什麼](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md#review-what-a-mod-can-do)顯示輸出以及要查找的呼叫。

## 開啟或關閉 mods

mod 預設為開啟。在終端機中，請使用 Claude Code v2.1.287 或更新版本。Desktop 應用程式內含自己的 Claude Code 副本，mod 從 v2.1.286 起即可在其中運作。請在您使用 mod 的地方檢查版本：

* **終端機**：在您的 shell 中執行 `claude --version`。如果您的版本較舊，請[更新 Claude Code](https://code.claude.com/docs/zh-TW/setup.md#update-claude-code)。
* **Desktop 應用程式**：在 Code 標籤的本機工作階段中，輸入 `/status` 並查看 **Claude Code** 列，其中會顯示版本，例如 `2.1.286`。如果您的版本較舊，請[更新 Desktop 應用程式](https://code.claude.com/docs/zh-TW/desktop.md#claude-code-version-in-the-code-tab)。

若要關閉 mods，請選擇要停止多少個，以及停止多長時間。若要將它們重新開啟，請撤銷相同的變更：

* **一個 mod**：從[`/plugin` 中的**已安裝**標籤](https://code.claude.com/docs/zh-TW/plugins/install#manage-installed-plugins)停用或解除安裝其外掛程式
* **每個已安裝的 mod，一個工作階段**：使用 [`--safe-mode`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 啟動 Claude Code，這也會停用您的其他自訂
* **您安裝的每個 mod，在每個工作階段中**：在 `~/.claude/settings.json` 中設定 [`"disableAllHooks": true`](https://code.claude.com/docs/zh-TW/settings-reference#disableallhooks)。您的設定 hook 和自訂狀態列也會停止。您的組織管理的內容會繼續執行。

如果您透過組織使用 Claude Code，管理員也可以限制哪些 mods 載入。管理員從[停止使用者安裝的 mods 載入](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md#stop-user-installed-mods-from-loading)開始。

`disableAllHooks` 和您組織的 `allowManagedModsOnly` 會停止 mod，並保留其外掛的其餘部分：外掛會維持安裝狀態，其 skill、命令、agent 和 MCP 伺服器都會載入。其他設定和旗標的影響範圍更廣。[`disableAllHooks`](https://code.claude.com/docs/zh-TW/settings-reference#disableallhooks) 和[在 `allowManagedHooksOnly` 下執行的內容](https://code.claude.com/docs/zh-TW/settings-reference#what-runs-under-allowmanagedhooksonly)列出了每一項對外掛及其設定 hook 的影響。

若要了解 mods 是否可以為您載入，請參閱[檢查 mods 是否可以載入](https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot.md#check-whether-mods-can-load)。

> [!NOTE]
>
> 如果您在早期存取期間設定了 `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS`，請移除它。Claude Code v2.1.287 及更新版本會忽略它，因此將其設定為 `0` 不會保持 mods 關閉。

### 查看工作階段載入了哪些 mods

若要查看終端機工作階段載入了哪些 mods，請在 Claude Code 提示處執行 `/plugin`。標籤下的暗行提供計數和名稱，例如 `1 mod active · first-mod`。如果您安裝的 mod 未在那裡命名，請參閱[找出為什麼 mod 不執行任何操作](https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot.md#find-out-why-a-mod-does-nothing)。

## Mod 的運作方式

Mod 是一個[外掛程式](https://code.claude.com/docs/zh-TW/plugins/overview.md)，其程式碼註冊事件處理程式，稱為 hook。Claude Code 在其事件發生時執行 hook，例如當 Claude 呼叫工具或繪製微調器時。一個小 mod 有三個檔案：

```text theme={null}
first-mod/
├── .claude-plugin/
│   └── plugin.json
└── hooks/
    ├── hooks.json
    └── register.js
```

* **`plugin.json`**：外掛程式的[清單](https://code.claude.com/docs/zh-TW/plugins/manifest-reference.md)
* **`hooks.json`**：[指向您的程式碼檔案](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#files)
* **`register.js`**：[您的程式碼](https://code.claude.com/docs/zh-TW/plugins/mods/create.md#write-a-mod-yourself)，稱為 hook 模組。它告訴 Claude Code 在哪些事件上執行您的函式。

這是一個完整的 `register.js`。它計算 Claude 進行的工具呼叫，並在 Claude 工作時在微調器旁邊顯示計數，如 `Thinking · tool calls: 3…`。

```javascript hooks/register.js theme={null}
// The count, shared by the two hooks below
let calls = 0

// Claude Code calls this once when the mod loads
export function register(on) {
  // Runs each time Claude is about to use a tool
  on('tool.call', async ($, e, next) => {
    calls += 1
    // Ask Claude Code to draw the interface again, so the new count shows
    $.ui.invalidate('ui.render')
    // Let the tool run as usual
    return next(e)
  })

  // Runs each time Claude Code draws the spinner
  on('ui.render', { component: 'Spinner' }, async ($, e, next) => {
    // Keep Claude Code's spinner, with the count added after its word
    return next({ ...e, props: { ...e.props, suffix: ' · tool calls: ' + calls + '…' } })
  })
}
```

該檔案註冊了兩個 hook，兩者都使用頂部的 `calls` 變數：

* **[`tool.call`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#tools) hook** 在 Claude 即將使用工具時執行。它將 `calls` 加一，要求 Claude Code 再次繪製介面，並讓工具照常執行。
* **[`ui.render`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#interface) hook** 在 Claude Code 繪製微調器時執行。它保留 Claude Code 自己的微調器，並在單詞後面新增計數。

此錄影顯示 mod 的運作。觀看提示詞輸入框上方的微調器行：當 Claude 列出目錄並讀取兩個檔案時，它顯示 `Thinking · tool calls: 1…`，然後 `2…`，然後 `3…`。

<video autoPlay muted loop playsInline controls src="https://mintcdn.com/claude-code/dgiVO_Od1X1faduV/images/mods-overview-light.mp4?fit=max&auto=format&n=dgiVO_Od1X1faduV&q=85&s=00a18aa0743b59a700f0275ce226e6d1" aria-label="In a Claude Code session, the prompt 'list the files here and read the README' is typed and sent. While Claude works, the spinner reads 'Thinking · tool calls: 1', then 2, then 3, as Claude lists the files and reads two of them." />

### Hook 可以對事件做什麼

Claude Code 在對事件採取行動之前執行您的 hook，因此 hook 決定接下來會發生什麼。它可以：

* **觀察**：注意正在發生的事情並讓它繼續不變，如範例中的 `tool.call` hook 所做的
* **重寫**：在事件繼續之前變更事件，如 `ui.render` hook 在將計數新增到微調器時所做的
* **回答**：自己處理事件，因此通常的行為不會執行，例如拒絕命令

若要在其自己的程式碼之外執行任何操作，例如繪製、新增命令、呼叫模型、讀取檔案、啟動程序或發出網路請求，hook 會呼叫 mods API。Hook 沒有其他方式來執行這些操作，這就是為什麼 Claude Code 可以在您安裝之前[列出 mod 的功能](#list-what-a-mod-does-before-you-install-one)。

如需每個選擇背後的程式碼，請參閱[對事件做出反應](https://code.claude.com/docs/zh-TW/plugins/mods/events.md#how-a-hook-handles-an-event)。如需 hook 可以呼叫的內容，請參閱[使用 mods API](https://code.claude.com/docs/zh-TW/plugins/mods/api.md)。

### Mods 執行的位置

Mod 的 hook 在載入外掛程式的每種工作階段中執行，無論由哪個供應商提供模型，包括 Amazon Bedrock、Google Cloud 的 Agent Platform 和 Microsoft Foundry。繪製的範圍較窄：mod 繪製的內容會出現在終端機、Desktop 應用程式和 VS Code 擴充功能中。此表列出您可能執行 Claude Code 的每個位置：

| 您執行 Claude Code 的位置 | Hook 執行 | Mod 繪製的內容出現 |
| :- | :- | :- |
| 終端機中的 `claude`，包括編輯器的整合終端機和 JetBrains 外掛程式 | 是 | 是 |
| Desktop 應用程式的 Code 標籤，除了 WSL 工作階段外 | 是 | 是，除了[元素表](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#elements)標記為僅限終端機的元素 |
| Desktop 應用程式中的 [WSL 工作階段](https://code.claude.com/docs/zh-TW/desktop-wsl.md) | 否，因為外掛程式在 WSL 工作階段中不可用 | 否 |
| VS Code 擴充功能的聊天面板 | 是 | 是，需使用擴充功能版本 2.1.299 或更新版本。[不擷取功能旗標](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)的工作階段（例如在 Amazon Bedrock 上的工作階段）需要 2.1.304 或更新版本。[轉譯位置](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#render-sites)和[元素](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#elements)表標示了面板會繪製的內容。 |
| `claude -p` 和 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) | 是 | 否 |
| 從 claude.ai 或行動應用程式使用的 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) | 是，在您機器上的工作階段中 | 在您機器上的終端機中 |
| [雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md) | 是，對於[到達雲端工作階段](https://code.claude.com/docs/zh-TW/cloud-environments.md#what-carries-over-from-your-setup)的外掛程式 | 否 |

會繪製內容的 mod 可以檢查它在哪個應用程式中執行，並在無法繪製的地方改為在逐字稿中顯示一行文字或使用命令的文字回覆。

## 為您的組織控制 mods

管理員透過[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)決定 mods 是否執行以及哪些執行。[為您的組織管理 mods](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md)涵蓋預設情況、如何檢查 mod 以及如何使用您自己的 mod 強制執行原則。

## 比較 mods、設定 hook、skills 和 MCP 伺服器

Mods、設定 hook、skills 和 MCP 伺服器的功能有所重疊。此表顯示每一個是什麼以及何時選擇它。

| | Mod | 設定 hook | Skill | MCP 伺服器 |
| :- | :- | :- | :- | :- |
| 它是什麼 | Claude Code 在其自己的程序中呼叫的外掛程式中的函式 | Claude Code 在生命週期事件上執行的 shell 命令、HTTP 請求或提示詞 | Claude 讀取的 `SKILL.md` 檔案指令 | 提供 Claude 工具的外部程序或服務 |
| 它可以變更什麼 | 工具呼叫、提示詞、命令、回合以及介面繪製的內容 | 工具呼叫或提示詞是否繼續進行、工具呼叫的引數和結果，以及為 Claude 新增的內容 | Claude 知道和執行的內容 | Claude 擁有的工具 |
| 它可以在介面中繪製嗎 | 是 | 否 | 否 | 否 |
| 您編寫什麼 | JavaScript 或 TypeScript | 指令碼和 `settings.json` 項目 | Markdown | 任何語言的伺服器 |
| 在以下情況下選擇它 | 您想要窗格、提示詞上方的帶狀區域、自訂命令或重寫事件 | 您想要使用您已經擁有的指令碼來阻止、允許或記錄事件 | 您不斷將相同的指令貼到聊天中 | Claude 需要存取外部系統 |

其他每一個都有自己的頁面：[Hooks](https://code.claude.com/docs/zh-TW/hooks.md)、[Skills](https://code.claude.com/docs/zh-TW/skills.md) 和 [MCP](https://code.claude.com/docs/zh-TW/mcp.md)。外掛程式可以包含上述所有項目，因此 mod 可以與 skill 和 MCP 伺服器一起在同一個外掛程式中發布。

## 內建於 Claude Code 的 Mods

Claude Code 的某些功能是 mods。若要查看您的工作階段擁有的功能，請在 Claude Code 提示處執行 `/plugin` 並前往**已安裝**標籤，該標籤在**內建**下列出它們。您無法更新或解除安裝內建 mod，表格的最後一欄說明如何關閉每一個。[`mods active` 行](#see-which-mods-a-session-loaded)排除內建 mods。

此表按 `/plugin` 顯示的名稱列出每個項目：

| `/plugin` 中的名稱 | 它的功能 | 它在哪裡開啟 | 如何關閉它 |
| :- | :- | :- | :- |
| `cc-plugin-agents-md` | 將 `AGENTS.md` 載入為專案指令 | 每個工作階段，除了[無法讀取 `AGENTS.md` 的工作階段](https://code.claude.com/docs/zh-TW/memory#when-agents-md-support-is-unavailable) | 在 `/plugin` 中停用它，或[選擇哪些指令檔案載入](https://code.claude.com/docs/zh-TW/memory.md#choose-which-instruction-files-load) |
| `cc-plugin-diff` | 接管 [`/diff`](https://code.claude.com/docs/zh-TW/interactive-mode#review-changes-with-%2Fdiff) 並繪製其窗格 | 互動式終端機工作階段 | 在 `/plugin` 中停用它。`/diff` 保留，Claude Code 的內建版本的命令回答它。 |
| `cc-plugin-plugin-authoring` | 為 Claude 提供[`plugin-authoring` skill](https://code.claude.com/docs/zh-TW/plugins/mods/create#ask-claude-for-a-mod)以編寫 mods。它保留 skill 且沒有 mod 程式碼。 | 除非 Anthropic 已遠端關閉已安裝的 mods | 在 `/plugin` 中停用它 |
| `cc-plugin-sec-default` | 保護您的組織管理的內容免受使用者安裝的 mods | [保護載入的位置](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md#know-what-happens-by-default) | 您無法。管理員在受管設定中[設定順序](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md#install-your-organizations-mods) |
| `cc-plugin-telemetry` | 傳送 Claude Code 及其內建 mods 記錄的分析記錄 | 無論 Claude Code 自己的分析在哪裡開啟 | 在 `/plugin` 中停用它，或關閉分析，例如使用 [`DISABLE_TELEMETRY`](https://code.claude.com/docs/zh-TW/env-vars) |
| `cc-plugin-you-should-know` | [You should know](https://code.claude.com/docs/zh-TW/interactive-mode.md#you-should-know-suggestions)：當側邊 agent 發現您可能錯過的內容時，會在提示上方顯示一則備註 | 保持關閉，直到您[將其開啟](https://code.claude.com/docs/zh-TW/interactive-mode.md#you-should-know-suggestions) | 在 `/plugin` 中停用它 |

停止已安裝 mods 的設定和旗標，例如 `disableAllHooks`、`--bare` 和 `--safe-mode`，不會停止內建 mods。

### 讀取內建 mods 的來源

這些 mods 中部分 mod 的來源在 [Claude Code 儲存庫的 `mods` 目錄](https://github.com/anthropics/claude-code/tree/main/mods)中是公開的。每一個都是一個完整的外掛程式，具有其 hooks 模組和測試：

* [`diff`](https://github.com/anthropics/claude-code/tree/main/mods/diff)：`/diff` 窗格，具有綁定到鍵盤動作的按鈕和 mod 自己處理的捲動
* [`agents-md`](https://github.com/anthropics/claude-code/tree/main/mods/agents-md)：將 `AGENTS.md` 載入為專案指令，具有 [`userConfig`](https://code.claude.com/docs/zh-TW/plugins/components#user-configuration) 選項
* [`sec-default`](https://github.com/anthropics/claude-code/tree/main/mods/sec-default)：[了解預設情況下會發生什麼](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md#know-what-happens-by-default)中描述的保護，強制執行原則的 mod 的模型
* [`telemetry`](https://github.com/anthropics/claude-code/tree/main/mods/telemetry)：新增其他 mods 可以呼叫的方法，並發送其類型

## 後續步驟

* [建立 mod](https://code.claude.com/docs/zh-TW/plugins/mods/create.md)：建立一個計算工具呼叫、在微調器旁邊顯示計數並新增命令的 mod，並了解編輯和重新載入迴圈
* [在介面中繪製](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md)：窗格、提示詞上方的帶狀區域、按鈕、文字欄位和狀態
* [對事件做出反應](https://code.claude.com/docs/zh-TW/plugins/mods/events.md)：工具呼叫、提示詞、回合以及 mods 執行的順序
* [使用 mods API](https://code.claude.com/docs/zh-TW/plugins/mods/api.md)：命令、工具、模型呼叫、計時器和檔案
* [測試 mod](https://code.claude.com/docs/zh-TW/plugins/mods/test.md)：在沒有工作階段的情況下執行的自動化測試
* [對 mod 進行故障排除](https://code.claude.com/docs/zh-TW/plugins/mods/troubleshoot.md)：mod 不執行任何操作的原因以及偵錯日誌
* [為您的組織管理 mods](https://code.claude.com/docs/zh-TW/plugins/mods/admin.md)：預設值、受管設定、檢查 mod 和原則 mods
* [Mods 參考](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md)：事件、方法、元素和限制

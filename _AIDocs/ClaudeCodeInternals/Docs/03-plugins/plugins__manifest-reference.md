<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/plugins/manifest-reference | lastmod: 2026-11-04 | section: Plugins / Reference -->
> 來源：https://code.claude.com/docs/zh-TW/plugins/manifest-reference（官方 zh-TW，lastmod 2026-11-04）｜分類：Plugins › Reference｜EN 摘要：Complete reference for plugin.json: every field with its type and default, accepted path forms, and the userConfig and environment variable schemas.

# Plugin manifest 參考

> plugin.json 的完整參考：每個欄位的類型和預設值、接受的路徑形式，以及 userConfig 和環境變數架構。

Plugin manifest 是位於 plugin 的 `.claude-plugin/` 目錄中的 `plugin.json` 檔案。它包含 plugin 的中繼資料和 Claude Code 提示使用者輸入的 [`userConfig`](#user-configuration) 值。它也宣告任何您內聯定義或保留在其[預設位置](#standard-layout)之外的元件。

本參考適用於 plugin 建立者，以及將元件欄位放在 marketplace 項目中的 marketplace 擁有者。

> [!NOTE]
>
> 這些情況涵蓋在其他頁面上：
>
> * **學習建立 plugin**：從[建立 plugin](https://code.claude.com/docs/zh-TW/plugins/create.md)開始
> * **每個元件在執行時的作用**：請參閱 [Plugin 元件](https://code.claude.com/docs/zh-TW/plugins/components.md)

從符合您要查詢內容的部分開始：

* 一個欄位：[欄位表](#fields)提供每個欄位的類型、是否必需、其預設值和接受的內容。[路徑規則](#path-rules)涵蓋 `./` 前綴和每個元件路徑的包含
* 一個 `userConfig` 選項或一個 `channels` 項目：[使用者設定](#user-configuration)和[頻道](#channels)架構
* `${CLAUDE_PLUGIN_ROOT}` 或 plugin 可以參考的另一個變數：[環境變數](#environment-variables)
* 每個元件的檔案位置：[標準配置](#standard-layout)
* 來自 `claude plugin validate` 的訊息：[疑難排解頁面](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md)列出每條訊息及其修正，並連結到本頁的相關部分

## Manifest 檔案

manifest 是選用的。沒有它，Claude Code 會載入它在[標準配置](#standard-layout)中找到的元件。然後 plugin 名稱來自 marketplace 項目，或在您使用 `--plugin-dir` 載入 plugin 時來自目錄名稱。

當您想要中繼資料、預設目錄外的元件、`userConfig` 或內聯元件定義時，請寫入 manifest。

將 manifest 儲存在 plugin 根目錄下的 `.claude-plugin/plugin.json`。將所有其他 plugin 檔案放在 plugin 根目錄，而不是 `.claude-plugin/` 內。這包括 `skills/`、`commands/` 和 `hooks/`。

以下範例設定[欄位表](#fields)中的大多數鍵。它在包含每個參考路徑的 plugin 目錄中通過驗證。

```json theme={null}
{
  "name": "deploy-tools",
  "displayName": "Deploy Tools",
  "version": "1.2.0",
  "description": "Deployment commands, a review agent, and a status monitor",
  "author": {
    "name": "Example Team",
    "email": "dev@example.com",
    "url": "https://example.com"
  },
  "homepage": "https://example.com/docs/deploy-tools",
  "repository": "https://github.com/example/deploy-tools",
  "license": "MIT",
  "keywords": ["deployment", "ci"],
  "defaultEnabled": true,
  "dependencies": ["secrets-vault"],
  "metadata": { "catalogId": "cat-123" },
  "skills": ["./extra-skills/"],
  "commands": {
    "status": {
      "source": "./commands/status.md",
      "description": "Show the current deployment status"
    },
    "about": {
      "content": "Explain what the deploy-tools plugin provides.",
      "description": "Describe this plugin"
    }
  },
  "agents": ["./agents/reviewer.md"],
  "hooks": "./config/extra-hooks.json",
  "mcpServers": {
    "deploy-api": {
      "command": "node",
      "args": ["${CLAUDE_PLUGIN_ROOT}/server.js"]
    }
  },
  "lspServers": "./.lsp.json",
  "outputStyles": "./styles/",
  "experimental": {
    "themes": "./themes/",
    "monitors": "./config/monitors.json"
  },
  "userConfig": {
    "api_token": {
      "type": "string",
      "title": "API token",
      "description": "Token for the deployment API",
      "sensitive": true
    }
  }
}
```

### 無法識別的欄位

無法識別的頂層鍵會被移除，而 `userConfig` 選項、`channels` 項目、`lspServers` 設定或 `monitors` 項目內無法識別的鍵會被拒絕：

* **頂層欄位**：欄位被移除，plugin 載入。`claude plugin validate` 將每個無法識別的頂層欄位報告為警告
* **嚴格物件**：`userConfig` 選項、`channels` 項目、`lspServers` 設定和 `monitors` 項目是嚴格的。其中的未知鍵是錯誤，plugin 不會載入

### 驗證 manifest

`claude plugin validate` 是 manifest 的權威檢查。從您的 shell 針對 plugin 目錄執行它：

```bash theme={null}
claude plugin validate ./my-plugin
```

該命令報告以下結果之一：

* **`Validation passed`**：manifest 載入
* **`Validation passed with warnings`**：manifest 載入，但驗證器發現需要修正的內容，例如 Claude Code 移除的未知頂層欄位、不是 kebab-case 的 `name`，或缺少 `version`、`description` 或 `author`。傳遞 `--strict` 以在 CI 中將警告轉換為失敗
* **`Validation failed`**：manifest 有類型不匹配、缺少或逃逸 plugin 根目錄的路徑，或 `userConfig` 選項、`channels` 項目、`lspServers` 設定或 `monitors` 項目內的未知鍵。Claude Code 在載入 plugin 時報告相同的問題

該命令也會檢查 plugin 在 `.mcp.json` 中宣告的每個 MCP 伺服器項目、在 [`mcpServers`](#mcpservers) 命名的 `.json` 檔案中，或在 `plugin.json` 中內聯。這些 MCP 檢查需要 Claude Code v2.1.281 或更新版本，並包括：

* **錯誤**：Claude Code 在載入 plugin 時會捨棄的項目、對 manifest 未宣告的選項的 `${user_config.KEY}` 參考，以及不是有效絕對 URL 的遠端 `url`
* **警告**：對非迴圈主機的 `http://` 或 `ws://` URL，以及看起來像字面認證的標頭值

## 欄位

表格列出 `plugin.json` 中的頂層鍵。`name` 是唯一必需的鍵。其中欄位名稱是連結的地方，連結的部分有其完整規則。

對於元件鍵（例如 `commands` 和 `hooks`），[元件路徑形式](#component-path-forms)顯示每個接受的形式及範例，每個路徑都遵循 `./` 前綴、副檔名和包含的[路徑規則](#path-rules)。

| 欄位 | 類型 | 說明 |
| :- | :- | :- |
| `$schema` | String | JSON Schema URL 用於編輯器自動完成。Claude Code 在載入時忽略它 |
| [`name`](#name) | String | Plugin 識別碼，必需。使用 kebab-case。每個元件都在其下命名空間 |
| [`displayName`](#displayname) | String | 在 UI 中顯示的名稱，代替 `name` |
| [`version`](#version) | String | 版本字串。設定它會將使用者保留在該版本，直到您變更它 |
| `description` | String | plugin 提供內容的簡短說明 |
| `author` | Object | `name`（必需），加上選用的 `email` 和 `url` |
| `homepage` | String | 文件 URL。必須解析為 URL，否則 plugin 無法載入 |
| `repository` | String | 來源儲存庫 URL。未驗證 |
| `license` | String | SPDX 識別碼，例如 `MIT` 或 `Apache-2.0` |
| `keywords` | Array of strings | 探索標籤 |
| [`metadata`](#metadata) | Object | 您自己資料的自由形式物件。Claude Code 不讀取它 |
| [`icon`](#directory-listing-fields) | String | plugin 在 Anthropic 目錄中列表的圖示。Claude Code 不讀取它 |
| [`documentationUrl`](#directory-listing-fields) | String | plugin 在 Anthropic 目錄中列表的文件連結。Claude Code 不讀取它 |
| [`supportUrl`](#directory-listing-fields) | String | plugin 在 Anthropic 目錄中列表的支援連結。Claude Code 不讀取它 |
| [`privacyPolicyUrl`](#directory-listing-fields) | String | plugin 在 Anthropic 目錄中列表的隱私權政策連結。Claude Code 不讀取它 |
| [`termsOfServiceUrl`](#directory-listing-fields) | String | plugin 在 Anthropic 目錄中列表的服務條款連結。Claude Code 不讀取它 |
| [`defaultEnabled`](#defaultenabled) | Boolean | 當使用者未設定時，plugin 是否在啟用時啟動。預設為 `true` |
| [`dependencies`](#dependencies) | Array of strings or objects | 此 plugin 運作所必須啟用的其他 plugin |
| [`settings`](#settings) | Object | Claude Code 在 plugin 啟用時應用的設定。只有 `agent` 和 `subagentStatusLine` 生效 |
| [`userConfig`](#user-configuration) | Object | Claude Code 在 plugin 啟用時提示使用者輸入的值 |
| `types` | Path | 宣告 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#files) 的 `$.state` 值和 `$` 名詞的 `.d.ts` 檔案 |
| [`channels`](#channels) | Array of objects | plugin 提供的訊息頻道，每個繫結到其 MCP 伺服器之一 |
| `skills` | Path, or array of paths | 要掃描的目錄以尋找 skills，每個目錄都是 `<name>/SKILL.md` 資料夾或直接保存 `SKILL.md` 的資料夾。`"."` 命名 plugin 根目錄。新增到預設 `skills/` 掃描 |
| [`commands`](#commands) | Path, array of paths, or object | 平面 `.md` 命令檔案、它們的目錄，或命令名稱到 `source` 或 `content` 的物件對應。取代預設 `commands/` 掃描 |
| `agents` | Path, or array of paths | Agent `.md` 檔案。不接受目錄。取代預設 `agents/` 掃描 |
| [`hooks`](#hooks) | Path, object, or array of either | `.json` hook 檔案或內聯 hook 設定。與 `hooks/hooks.json` 一起載入 |
| [`mcpServers`](#mcpservers) | Path, object, or array of either | `.json` MCP 設定檔案、`.mcpb` 或 `.dxt` 套件，或以名稱為鍵的內聯伺服器設定。與 `.mcp.json` 一起載入；稍後宣告的伺服器名稱取代較早的名稱 |
| [`lspServers`](#lspservers) | Path, object, or array of either | `.json` LSP 設定檔案或以名稱為鍵的內聯伺服器設定。與 `.lsp.json` 一起載入 |
| `outputStyles` | Path, or array of paths | 輸出樣式檔案或目錄。取代預設 `output-styles/` 掃描 |
| `workflows` | Path, or array of paths | [Workflow](https://code.claude.com/docs/zh-TW/workflows.md#distribute-a-workflow-in-a-plugin) `.js` 檔案或目錄。取代預設 `workflows/` 掃描 |
| `experimental` | Object | `themes`、`monitors` 和 `evals` 的容器，其 manifest 形式可能仍會變更 |
| `experimental.themes` | Path, or array of paths | 主題檔案或目錄。取代預設 `themes/` 掃描。頂層 `themes` 鍵仍會載入，並帶有 `claude plugin validate` 警告 |
| [`experimental.monitors`](#monitors) | Path, or inline array | 保存 monitors 陣列的 `.json` 檔案，或陣列本身。預設為 `monitors/monitors.json`。頂層 `monitors` 鍵仍會載入，並帶有 `claude plugin validate` 警告。Monitors [在使用 `-p` 旗標時不會啟動](https://code.claude.com/docs/zh-TW/plugins/components#monitors) |
| `experimental.evals` | Path, or array of paths | 當它不是預設 `evals/` 時，保存 plugin 的 [eval 案例](https://code.claude.com/docs/zh-TW/plugin-evals.md#use-a-different-eval-directory)的目錄。`claude plugin eval --eval-dir` 覆蓋它 |

在「類型」欄中，路徑是相對於 plugin 根目錄的字串，例如 `"./custom/commands"`。

### `name`

Plugin 識別碼。它必須非空，沒有空格、`@`、`:`、路徑分隔符、控制字元或雙向格式化字元；使用 kebab-case。

Claude Code 在其下命名空間每個元件，因此 plugin `deploy-tools` 中的 agent `reviewer` 顯示為 `deploy-tools:reviewer`。

`claude plugin validate` 也會檢查名稱是否通過 Anthropic 自己的 plugin 之一。檢查會忽略大小寫，並將任何分隔符的執行視為一個：

| 名稱 | 結果 |
| :- | :- |
| 以 `claude-`、`anthropic-`、`anthropics-` 或 `cc-plugin-` 開頭 | 錯誤 |
| 是 `claude`、`anthropic`、`anthropics`、`claude-code` 或 `claude-mods` | 錯誤 |
| 將 `official` 放在 `claude` 或 `anthropic` 旁邊，例如 `official-claude-tools` | 錯誤 |
| 在其他地方將 `claude`、`anthropic` 或 `anthropics` 作為整個單詞，例如 `mcp-for-claude` | 警告 |

錯誤讀作 `Plugin name "<name>" is reserved: it passes as one of Anthropic's own`，警告讀作 `Plugin name "<name>" reads as one of Anthropic's own`。`claude plugin init` 和 `claude plugin tag` 會拒絕引發該錯誤的名稱。Claude Code 仍會安裝並載入名稱遭它們拒絕的 plugin。

### `displayName`

在 UI 中顯示的名稱，代替 `name`。它可能包含空格和任何大小寫，它不用於命名空間或查詢。

對於 marketplace 安裝的 plugin，[marketplace 項目](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#plugin-entries)上的 `displayName` 優先於此值。

### `version`

版本字串，不根據 semver 檢查。設定它會將 plugin 固定到該版本，直到您變更它；請參閱[版本和更新](https://code.claude.com/docs/zh-TW/plugins/loading.md#versions-and-updates)。具有[`command` 來源](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference)的 plugin、來自[託管在 claude.ai 上的 marketplace](https://code.claude.com/docs/zh-TW/plugins/install.md#add-from-claude-ai) 的 plugin，以及[就地載入](https://code.claude.com/docs/zh-TW/plugins/loading.md#find-plugins-on-disk)的 plugin（來自從本機路徑新增的 marketplace）不受此欄位固定。

### `metadata`

您自己資料的自由形式物件，例如目錄或權利欄位。Claude Code 不讀取它。需要 Claude Code v2.1.222 或更新版本。

### 目錄列表欄位

當您[提交 plugin](https://code.claude.com/docs/zh-TW/plugins/publish.md#submit-to-anthropics-directory) 時，Anthropic 的目錄會從 `plugin.json` 讀取 `icon`、`documentationUrl`、`supportUrl`、`privacyPolicyUrl` 和 `termsOfServiceUrl` 欄位，用於您 plugin 的列表。Claude Code 在載入時忽略它們。僅在 `plugin.json` 中設定它們。在 [marketplace 項目](#marketplace-entries-and-the-manifest)中，`claude plugin validate` 會將每個欄位報告為未知欄位。

將 `icon` 設定為 plugin 內圖片檔案的路徑，例如 `./logo.png`，並將四個 URL 欄位各自設定為 `https://` URL。

> [!NOTE]
>
> 在 Claude Code v2.1.281 或更新版本上，`claude plugin validate` 不會將 `plugin.json` 中的這些欄位報告為未知欄位。較早版本會為每個欄位印出 `Unknown field` 警告，因此 `--strict` 執行在這些版本上會失敗。

### `defaultEnabled`

當使用者未在 [`enabledPlugins`](https://code.claude.com/docs/zh-TW/settings-reference#enabledplugins) 中設定時，plugin 是否在啟用時啟動。預設為 `true`。啟用的 plugin 所依賴的 plugin 無論如何都會啟用。marketplace 項目中的相同欄位覆蓋此欄位。

一旦寫入使用者的 `enabledPlugins` 項目，它會在 plugin 更新中持續存在，因此在稍後版本中變更 `defaultEnabled` 不會變更現有使用者的設定。

### `dependencies`

此 plugin 運作所必須啟用的其他 plugin。每個項目是 `"name"`、`"name@marketplace"` 或 `{ "name": "...", "marketplace": "...", "version": "..." }`。裸名稱針對此 plugin 自己的 marketplace 解析。請參閱[依賴性約束](https://code.claude.com/docs/zh-TW/plugins/dependencies.md)。

### `settings`

Claude Code 在 plugin 啟用時應用的設定。只有 `agent` 和 `subagentStatusLine` 生效；其他鍵在載入時被丟棄。plugin 根目錄的 `settings.json` 優先於此鍵。請參閱[預設設定](https://code.claude.com/docs/zh-TW/plugins/components.md#default-settings)。

## 元件路徑形式

每個元件鍵接受相對於 plugin 根目錄的路徑。`hooks`、`mcpServers`、`lspServers` 和 `experimental.monitors` 也接受內聯設定，`commands` 也接受物件對應，`mcpServers` 也接受 MCP 套件路徑和 URL。以下範例各顯示一次每個接受的形式。有關每個元件在執行時的作用，請參閱 [Plugin 元件](https://code.claude.com/docs/zh-TW/plugins/components.md)。

### 僅路徑欄位

`agents`、`skills`、`outputStyles`、`workflows` 和 `experimental.themes` 採用一個路徑或路徑陣列。`agents` 項目必須是 `.md` 檔案，`skills` 項目必須是目錄。其他三個接受目錄或檔案。

```json theme={null}
{
  "agents": ["./custom-agents/reviewer.md", "./custom-agents/tester.md"],
  "skills": ["./extra-skills/", "."],
  "outputStyles": "./styles/"
}
```

### `commands`

`commands` 採用路徑、路徑陣列或物件對應。路徑命名平面 `.md` 命令檔案或目錄。在物件對應中，每個鍵在 plugin 前綴後成為命令名稱。例如，plugin `deploy-tools` 中的 `"about"` 執行為 `/deploy-tools:about`。

每個值恰好設定 `source` 或 `content` 之一，設定兩者或都不設定的項目無法驗證。此表中的其他欄位是選用的：

| 欄位 | 類型 | 說明 |
| :- | :- | :- |
| `source` | string | 命令的 Markdown 檔案路徑，相對於 plugin 根目錄 |
| `content` | string | 命令主體的內聯 Markdown，而不是 `source` |
| `description` | string | 為命令顯示的說明 |
| `argumentHint` | string | 命令名稱後顯示的引數提示，例如 `[file]` |
| `model` | string | 命令的預設模型 |
| `allowedTools` | array of strings | 命令可以使用而無需提示的工具 |

此對應宣告一個來自檔案的命令和一個來自內聯內容的命令：

```json theme={null}
{
  "commands": {
    "status": { "source": "./commands/status.md", "argumentHint": "[env]" },
    "about": { "content": "Explain what this plugin provides." }
  }
}
```

### `hooks`

`hooks` 採用 `.json` 檔案路徑、與 [`settings.json` 中的 `hooks`](https://code.claude.com/docs/zh-TW/hooks#configuration) 相同形式的內聯 hooks 物件，或混合兩者的陣列。有關 hook 事件和處理程式欄位，請參閱 [hooks 參考](https://code.claude.com/docs/zh-TW/hooks.md#hook-events)。

hooks 檔案會將事件對應包裝在頂層 `"hooks"` 鍵中，也就是 [`hooks/hooks.json`](https://code.claude.com/docs/zh-TW/plugins/components#hooks) 所使用的形式。僅包含事件對應而沒有該包裝的檔案將無法載入。內聯物件本身就是事件對應，不需要包裝。

Claude Code 在該檔案存在時將您宣告的內容與 `hooks/hooks.json` 合併。此陣列載入一個 hooks 檔案，並宣告一個內聯 `PostToolUse` hook：

```json theme={null}
{
  "hooks": [
    "./config/extra-hooks.json",
    {
      "PostToolUse": [
        {
          "matcher": "Write|Edit",
          "hooks": [
            { "type": "command", "command": "\"${CLAUDE_PLUGIN_ROOT}\"/scripts/format.sh" }
          ]
        }
      ]
    }
  ]
}
```

該陣列所指名的檔案會以 `"hooks"` 包裝其自身的事件對應：

```json config/extra-hooks.json theme={null}
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "\"${CLAUDE_PLUGIN_ROOT}\"/scripts/check-command.sh" }
        ]
      }
    ]
  }
}
```

### `mcpServers`

`mcpServers` 採用 `.json` 檔案路徑、MCP 套件路徑或 URL、內聯對應，或混合它們的陣列。有關伺服器設定欄位，請參閱 [plugin 提供的 MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md#plugin-provided-mcp-servers)。

Claude Code 首先載入 plugin 根目錄的 `.mcp.json`，然後按順序載入每個宣告的形式。稍後宣告的伺服器名稱取代較早的名稱。

`mcpServers` 值採用以下形式之一：

| 形式 | 範例值 | Claude Code 的作用 |
| :- | :- | :- |
| `.json` 檔案路徑 | `"./mcp/servers.json"` | 將檔案讀取為 `mcpServers` 對應 |
| MCP 套件路徑 | `"./bundle.mcpb"` | 將 `.mcpb` 或 `.dxt` 套件提取到 plugin 根目錄下的 `.mcpb-cache/` 並讀取其伺服器設定 |
| MCP 套件 URL | `"https://example.com/server.mcpb"` | 將套件下載到 `.mcpb-cache/`，然後讀取它 |
| 內聯對應 | `{ "deploy-api": { "command": "node", "args": ["${CLAUDE_PLUGIN_ROOT}/server.js"] } }` | 使用對應作為以名稱為鍵的伺服器設定 |

套件路徑或 URL 必須以 `.mcpb` 或 `.dxt` 結尾。任何其他副檔名無法驗證。

### `lspServers`

`lspServers` 採用 `.json` 檔案路徑、伺服器名稱到設定的內聯對應，或兩者的陣列。

Claude Code 首先載入 plugin 根目錄的 `.lsp.json`，然後按順序載入每個宣告的設定。稍後宣告的伺服器名稱取代較早的名稱。

每個伺服器設定是具有這些欄位的嚴格物件。未知鍵無法驗證。

| 欄位 | 必需 | 說明 |
| :- | :- | :- |
| `command` | Yes | Language server 二進位檔。除非值以 `/` 開頭，否則沒有空格；將引數放在 `args` 中 |
| `extensionToLanguage` | Yes | 檔案副檔名到 LSP 語言 ID 的對應，至少一個項目。鍵以點開頭，例如 `".go"` |
| `args` | No | 傳遞給伺服器的引數 |
| `transport` | No | 通訊傳輸：`stdio`（預設）或 `socket`。Claude Code 接受 `socket` 但在 stdio 上執行每個伺服器，因此 stdout 協定規則適用於所有伺服器 |
| `env` | No | 伺服器程序的環境變數 |
| `initializationOptions` | No | 在初始化請求中傳送的選項 |
| `settings` | No | 由 `workspace/didChangeConfiguration` 傳送的設定 |
| `workspaceFolder` | No | 伺服器的工作區資料夾路徑 |
| `startupTimeout` | No | 等待啟動的毫秒數，正整數 |
| `shutdownTimeout` | No | 等待正常關閉的毫秒數，正整數。當逾時經過時，Claude Code 終止伺服器程序。未設定時，不適用逾時 |
| `requestTimeout` | No | 等待伺服器回應請求的毫秒數，正整數。預設為 `60000`，因此伺服器從未回應的請求會在 60 秒後失敗。需要 v2.1.288 或更新版本 |
| `restartOnCrash` | No | 伺服器崩潰後是否重新啟動。預設為 `true`。設定為 `false` 以保持崩潰的伺服器停止而不是重新啟動 |
| `maxRestarts` | No | 放棄前的重新啟動嘗試，零或更多 |
| `diagnostics` | No | 編輯後是否將診斷推送到上下文。預設為 `true` |

此內聯設定為 `.go` 檔案執行 `gopls`：

```json theme={null}
{
  "lspServers": {
    "go": {
      "command": "gopls",
      "args": ["serve"],
      "extensionToLanguage": { ".go": "go" }
    }
  }
}
```

有關 Anthropic 發佈為 plugin 的語言伺服器以及伺服器在執行時的行為，請參閱[程式碼智慧](https://code.claude.com/docs/zh-TW/plugins/code-intelligence.md)。

### `monitors`

`experimental.monitors` 採用 `.json` 檔案路徑或內聯陣列。當您省略鍵時，Claude Code 會載入 `monitors/monitors.json`（如果存在）。

每個項目是具有這些欄位的嚴格物件。

| 欄位 | 必需 | 說明 |
| :- | :- | :- |
| `name` | Yes | 在 plugin 內唯一的識別碼 |
| `command` | Yes | Claude Code 在工作階段工作目錄中作為持續背景程序執行的 Shell 命令 |
| `description` | Yes | 在工作面板和通知摘要中顯示的簡短摘要 |
| `when` | No | 使用 `"always"`（預設），monitor 在工作階段啟動和 plugin 重新載入時啟動。使用 `"on-skill-invoke:<skill>"`，它在該 skill 首次執行時啟動 |

此內聯陣列宣告一個 monitor，在 `deploy` skill 首次執行時啟動：

```json theme={null}
{
  "experimental": {
    "monitors": [
      {
        "name": "deploy-status",
        "command": "\"${CLAUDE_PLUGIN_ROOT}\"/scripts/poll-deploy.sh",
        "description": "Deployment status changes",
        "when": "on-skill-invoke:deploy"
      }
    ]
  }
}
```

Monitor `command` 無法參考 `${user_config.*}`。請參閱[通過 shell 執行的欄位](#fields-that-run-through-a-shell)。

## 路徑規則

manifest 中的每個元件路徑相對於 plugin 根目錄，必須以 `./` 開頭。路徑（例如 `commands/foo.md`）無法驗證。`skills` 和 `mcpServers` 各接受該規則外的一種形式：

* **`skills`**：也接受 `"."`。`"."` 和 `"./"` 都表示 plugin 根目錄。在 v2.1.221 之前，`"."` 無法通過 manifest 驗證，因此當 plugin 必須在較早版本上載入時使用 `"./"`
* **`mcpServers`**：也接受 `https://` 套件 URL

`experimental.evals` 不是元件路徑，因此本節的規則不涵蓋它，而是由 `claude plugin eval` 在執行時檢查該值。它指定外掛根目錄下的一個目錄，例如 `"quality/evals"`，可帶或不帶 `./` 前綴。若為陣列，則僅使用第一個項目。關於該值接受的內容以及無法使用的值會發生什麼情況，請參閱[使用不同的 eval 目錄](https://code.claude.com/docs/zh-TW/plugin-evals.md#use-a-different-eval-directory)。

### 包含和存在

每個元件路徑必須解析到 plugin 根目錄內並且必須存在。`claude plugin validate` 檢查每個元件鍵下的路徑：

* **包含**：解析到 plugin 根目錄外的路徑不會載入，`/plugin` **Errors** 標籤顯示 `<component> path escapes plugin directory: <path>`。包含 `..` 的路徑是常見情況，`claude plugin validate` 將其報告為 `Path contains ".." which could be a path traversal attempt`
* **存在**：不存在的路徑不會載入，`/plugin` **Errors** 標籤顯示 `<component> path not found: <path>`。`claude plugin validate` 將其報告為 `Path not found`

對於 `outputStyles`、`lspServers`、`monitors` 和 `themes` 路徑，`claude plugin validate` 檢查需要 Claude Code v2.1.283 或更新版本。

### 每個鍵如何與其預設位置結合

每個元件鍵要麼取代其預設位置，要麼新增到它，要麼與它合併：

* **取代預設**：`commands`、`agents`、`outputStyles`、`workflows`、`experimental.themes`、`experimental.monitors`。當您設定 `commands` 時，預設 `commands/` 目錄不會被掃描。要保留預設並新增更多，明確列出它：`"commands": ["./commands/", "./extras/"]`
* **新增到預設**：`skills`。`skills/` 目錄仍會被掃描，列出的目錄與它一起載入
* **合併**：`hooks`、`mcpServers`、`lspServers`。預設檔案首先載入，manifest 宣告的內容合併到它中，如[元件路徑形式](#component-path-forms)下所述

如果 plugin 有預設資料夾（例如 `commands/`）並且也設定了取代它的 manifest 鍵，Claude Code 會載入 manifest 路徑而不是資料夾。`claude plugin list` 和 `/plugin` 介面然後顯示警告 `Default <folder>/ folder is ignored because the manifest sets "<key>"`。

要避免警告，將鍵設定為該資料夾內的路徑：`"commands": ["./commands/deploy.md"]` 命名預設資料夾中的檔案，不會產生警告。

## 使用者設定

`userConfig` 宣告當外掛程式啟用時 Claude Code 提示使用者輸入的值，讓使用者不需要自行編輯 `settings.json`。

鍵是由字母、數字和底線組成的識別碼，且不能以數字開頭。

每個值都是一個嚴格的物件，包含以下欄位。未知的鍵會導致驗證失敗。

| 欄位 | 必需 | 說明 |
| :- | :- | :- |
| `type` | 是 | `string`、`number`、`boolean`、`directory` 或 `file` 之一 |
| `title` | 是 | 在設定對話框中顯示的標籤 |
| `description` | 是 | 在欄位下方顯示的說明文字 |
| `required` | 否 | 如果為 `true`，設定對話框不接受空值 |
| `default` | 否 | 當使用者未提供任何值時使用的值：字串、數字、布林值或字串陣列 |
| `options` | 否 | 對於 `string`，欄位接受的值，在 `/config` 中顯示為選擇器。請參閱[將欄位限制為固定選項](#limit-a-field-to-fixed-options)。需要 Claude Code v2.1.271 或更新版本 |
| `multiple` | 否 | 對於 `string`，允許字串陣列 |
| `sensitive` | 否 | 如果為 `true`，會遮蔽輸入並將值儲存在安全儲存空間中，而不是 `settings.json` |
| `min` / `max` | 否 | `number` 的邊界 |

每個已啟用外掛程式的每個選項也會在 `/config` 面板中顯示為一列，除了 `sensitive` 選項和 `multiple` 清單。`/config` 列需要 Claude Code v2.1.269 或更新版本。

此 `userConfig` 宣告一個端點和一個遮蔽的權杖：

```json theme={null}
{
  "userConfig": {
    "api_endpoint": {
      "type": "string",
      "title": "API endpoint",
      "description": "Your team's API endpoint"
    },
    "api_token": {
      "type": "string",
      "title": "API token",
      "description": "API authentication token",
      "sensitive": true
    }
  }
}
```

### 將欄位限制為固定選項

在 `userConfig` 欄位上設定 `options`，讓使用者從固定清單中選擇其值。

若要將 `tone` 欄位限制為三個選項，請在 `options` 中列出它們，並將 `default` 設定為其中之一：

```json theme={null}
{
  "userConfig": {
    "tone": {
      "type": "string",
      "title": "Tone",
      "description": "Voice for generated replies",
      "options": ["neutral", "warm", "formal"],
      "default": "neutral"
    }
  }
}
```

如果您在任何欄位上宣告 `options`，使用 Claude Code v2.1.271 之前版本的使用者將無法載入外掛程式。

`options` 適用於不是 `multiple` 或 `sensitive` 的 `string` 欄位。將 `default` 設定為列出的值之一，或設定 `required: true` 讓使用者必須選擇一個。每個選項是 1 到 64 個字元的純標籤，您在殼層中執行的 `claude plugin validate` 會報告它拒絕的任何其他內容。選項違反這些規則的外掛程式將無法載入。

### 值的儲存位置

非敏感值會儲存在使用者 `settings.json` 中的 [`pluginConfigs`](https://code.claude.com/docs/zh-TW/settings-reference#pluginconfigs) 下。敏感值則改為儲存在平台的安全認證存放區中。[設定頁面](https://code.claude.com/docs/zh-TW/settings-reference.md#pluginconfigs)列出了讀取 `pluginConfigs` 的設定檔。

### 參考已儲存的值

在外掛程式需要的地方參考已儲存的值，有以下兩種形式：

* **`${user_config.KEY}`**：在 MCP 伺服器設定、LSP 伺服器設定、[exec 形式](https://code.claude.com/docs/zh-TW/hooks.md#exec-form-and-shell-form) hook `args` 和技能與代理程式內容中替換。在技能和代理程式內容中，只有非敏感值會被替換，敏感值會變成預留位置
* **`CLAUDE_PLUGIN_OPTION_<KEY>`**：匯出到每個選項的 hook 程序，其中 `<KEY>` 為大寫。shell 形式的 hook 會讀取 `$CLAUDE_PLUGIN_OPTION_API_TOKEN` 以取得 `api_token`

### 通過殼層執行的欄位

Shell 形式的 hook 命令、監視命令和 MCP [`headersHelper`](https://code.claude.com/docs/zh-TW/mcp#use-dynamic-headers-for-custom-authentication) 拒絕 `${user_config.*}`。在這些欄位之一中參考它的元件會因[錯誤](https://code.claude.com/docs/zh-TW/errors.md#plugin-command-references-user-config)而失敗，而不是執行，因為欄位的值會傳遞到會重新解析替換值的殼層。

下表顯示該值如何可以到達這些欄位。

| 欄位 | 值如何到達它 |
| :- | :- |
| Shell 形式的 hook 命令 | 使用[exec 形式](https://code.claude.com/docs/zh-TW/hooks.md#exec-form-and-shell-form)搭配 `args`，或從 hook 的環境中讀取 `CLAUDE_PLUGIN_OPTION_<KEY>` |
| 監視命令 | 不通過 Claude Code。監視程序不會接收 `CLAUDE_PLUGIN_OPTION_<KEY>`，所以監視指令碼必須自行取得該值 |
| MCP `headersHelper` | 不通過 Claude Code。協助程式的環境包含 `CLAUDE_PLUGIN_ROOT`、`CLAUDE_CODE_MCP_SERVER_NAME` 和 `CLAUDE_CODE_MCP_SERVER_URL`，但沒有選項值，所以協助程式指令碼必須自行取得該值 |

## 頻道

`channels` 宣告 plugin 提供的訊息頻道，例如到聊天應用程式的橋接。當您宣告一個時，Claude Code 可以在 plugin 啟用時提示頻道的設定。有關伺服器如何注入訊息，請參閱[頻道參考](https://code.claude.com/docs/zh-TW/channels-reference.md#package-as-a-plugin)。

每個項目是繫結到 plugin 的 MCP 伺服器之一的嚴格物件，具有這些欄位：

| 欄位 | 必需 | 說明 |
| :- | :- | :- |
| `server` | Yes | 此 plugin 的 `mcpServers` 中頻道繫結到的 MCP 伺服器的鍵 |
| `displayName` | No | 在設定對話方塊標題中顯示的名稱。預設為伺服器名稱 |
| `userConfig` | No | 要提示的選項，形式與[頂層 `userConfig`](#user-configuration) 相同。儲存的值替換到伺服器 `env` 中的 `${user_config.KEY}` 參考 |

此 manifest 將頻道繫結到 plugin 的 `telegram` MCP 伺服器，並提示替換到伺服器 `env` 中的機器人令牌：

```json theme={null}
{
  "mcpServers": {
    "telegram": {
      "command": "node",
      "args": ["${CLAUDE_PLUGIN_ROOT}/server.js"],
      "env": { "BOT_TOKEN": "${user_config.bot_token}" }
    }
  },
  "channels": [
    {
      "server": "telegram",
      "displayName": "Telegram",
      "userConfig": {
        "bot_token": {
          "type": "string",
          "title": "Bot token",
          "description": "Telegram bot token",
          "sensitive": true
        }
      }
    }
  ]
}
```

## 環境變數

Claude Code 為 plugin 元件提供三個路徑變數。在[每個變數解析的位置](#where-each-variable-resolves)下列出的欄位中將它們參考為 `${NAME}`，並在接收它們的程序中將它們讀取為環境變數。

| 變數 | 解析為 | 用途 |
| :- | :- | :- |
| `${CLAUDE_PLUGIN_ROOT}` | plugin 已安裝版本的絕對路徑 | 與 plugin 捆綁的指令碼、二進位檔和設定檔案 |
| `${CLAUDE_PLUGIN_DATA}` | `~/.claude/plugins/data/<id>/`，在首次參考時建立並在 plugin 更新中保留。`<id>` 是 plugin 識別碼，其中除字母、數字、`_` 或 `-` 外的每個字元都被 `-` 取代 | 已安裝的依賴項（例如 `node_modules`）、產生的程式碼和快取 |
| `${CLAUDE_PROJECT_DIR}` | 專案根目錄 | 專案本機指令碼和設定檔案 |

`${CLAUDE_PLUGIN_ROOT}` 在 plugin 更新時變更，因此不要在那裡寫入狀態。有關根目錄移動的位置和舊目錄何時被清理，請參閱[載入頁面](https://code.claude.com/docs/zh-TW/plugins/loading.md)。

當您從最後安裝 plugin 的地方卸載它時，Claude Code 預設會刪除 `${CLAUDE_PLUGIN_DATA}` 目錄。有關 `--keep-data` 和其他保留它的情況，請參閱 [plugin 卸載](https://code.claude.com/docs/zh-TW/plugins/cli-reference.md#plugin-uninstall)。

### 每個變數解析的位置

在每個 plugin 元件中，`${...}` 參考在特定欄位中內聯解析，某些元件也在其程序環境中接收變數：

| Plugin 元件 | `${...}` 解析的欄位 | 匯出到程序 |
| :- | :- | :- |
| Hook 命令 | 在 `command` 和 `args` 中的任何位置 | `CLAUDE_PLUGIN_ROOT`、`CLAUDE_PLUGIN_DATA`、`CLAUDE_PROJECT_DIR` 和 `CLAUDE_PLUGIN_OPTION_<KEY>` |
| Monitor 命令 | 在 `command` 中的任何位置 | 未匯出 |
| MCP `stdio` 伺服器 | `command`、`args`、`env` | `CLAUDE_PLUGIN_ROOT`、`CLAUDE_PLUGIN_DATA`、`CLAUDE_PROJECT_DIR` |
| MCP `http`、`sse`、`ws` 伺服器 | `url`、`headers`、`headersHelper` | 不適用 |
| LSP 伺服器 | `command`、`args`、`env`、`workspaceFolder` | `CLAUDE_PLUGIN_ROOT`、`CLAUDE_PLUGIN_DATA`、`CLAUDE_PROJECT_DIR` |
| Skill、command 和 agent 內容 | Markdown 主體中的任何位置 | 不適用 |

變數不存在於 Claude 通過 Bash 工具在主工作階段或子代理中執行的命令環境中。在 skill、command 和 agent 內容中，在 Markdown 主體中寫入 `${...}` 參考，Claude Code 在載入內容時內聯替換路徑。

### 引用和路徑分隔符

保持每個替換的路徑為單一引數：

* **Hook 命令**：使用[exec 形式](https://code.claude.com/docs/zh-TW/hooks.md#exec-form-and-shell-form)與 `args` 以便每個路徑是一個沒有引用的引數
* **Shell 形式 hooks 和 monitor 命令**：用雙引號包裝變數，以便帶有空格的路徑保持為一個字

如果您在 hooks 檔案中的 shell 形式命令中將這些變數之一留在引號外，`claude plugin validate` 會發出警告，除非 hook 將 [`shell`](https://code.claude.com/docs/zh-TW/hooks#command-hook-fields) 設定為 `"powershell"`。

此 shell 形式 hook 執行與 plugin 捆綁的指令碼：

```json theme={null}
{
  "hooks": {
    "PostToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"${CLAUDE_PLUGIN_ROOT}\"/scripts/process.sh"
          }
        ]
      }
    ]
  }
}
```

在 Windows 上，大多數替換的路徑使用正斜線，例如 `C:/Users/you/...`。在 [exec 形式 hook](https://code.claude.com/docs/zh-TW/hooks.md#exec-form-and-shell-form) 中，以及透過 PowerShell 執行的 hook 中，這些路徑會保留原生的反斜線；當未安裝 Git Bash 時，PowerShell 是 Windows 上的預設 shell。

## 標準配置

每個元件類型在 plugin 根目錄下有預設位置，當 manifest 不指向其他位置時使用。

| 元件 | 預設位置 | 內容 |
| :- | :- | :- |
| Manifest | `.claude-plugin/plugin.json` | Plugin 中繼資料和設定。選用 |
| Skills | `skills/` | 每個 skill 一個 `<name>/SKILL.md`。具有其根目錄的 `SKILL.md`、沒有 `skills/` 和沒有 `skills` 鍵的 plugin 作為單一 skill 載入 |
| Commands | `commands/` | 平面 Markdown 命令檔案。對於新 plugin 偏好 `skills/` |
| Agents | `agents/` | Agent Markdown 檔案。子資料夾是[代理名稱](https://code.claude.com/docs/zh-TW/plugins/components.md#agents)的一部分 |
| Hooks | `hooks/hooks.json` | Hook 設定 |
| MCP 伺服器 | `.mcp.json` | MCP 伺服器定義 |
| LSP 伺服器 | `.lsp.json` | LSP 伺服器設定 |
| 輸出樣式 | `output-styles/` | 輸出樣式 Markdown 檔案 |
| Workflows | `workflows/` | Workflow `.js` 檔案 |
| 主題 | `themes/` | 主題 JSON 檔案 |
| Monitors | `monitors/monitors.json` | Monitors 陣列 |
| 可執行檔 | `bin/` | 此處的檔案在 plugin 啟用時位於 Bash 工具的 `PATH` 上，因此 Claude 將它們作為裸命令執行。claude.ai 和 Cowork 不安裝具有此目錄的 plugin，包括您[通過 claude.ai 組織設定分發](https://claude.com/docs/plugins/org-sync#keep-executables-out-of-the-top-level-bin-directory)的 plugin |
| 設定 | `settings.json` | 在 plugin 啟用時應用的 `agent` 和 `subagentStatusLine` 預設值 |

使用每個預設位置的 plugin，加上其 hooks 呼叫的 `scripts/` 資料夾，配置如下：

```text theme={null}
deploy-tools/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   └── deploy/
│       └── SKILL.md
├── commands/
│   └── status.md
├── agents/
│   └── reviewer.md
├── hooks/
│   └── hooks.json
├── monitors/
│   └── monitors.json
├── output-styles/
│   └── terse.md
├── themes/
│   └── dracula.json
├── workflows/
│   └── release-audit.js
├── bin/
│   └── deploy-tool
├── scripts/
│   └── format.sh
├── settings.json
├── .mcp.json
└── .lsp.json
```

要點擊此配置並讀取每個檔案的作用，請開啟 [plugin 探索器](https://code.claude.com/docs/zh-TW/plugins/components.md#explore-the-plugin-directory)。

plugin 根目錄的 `CLAUDE.md` 不作為上下文載入，`claude plugin validate` 在找到一個時發出警告。要包含載入到 Claude 上下文中的指示，請將它們放在 skill 中。

## Marketplace 項目和 manifest

[市集項目](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md)接受[其自己的欄位](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#plugin-entries)（包括 `strict`），以及此頁面上除了[目錄列表欄位](#directory-listing-fields)以外的每個欄位。

`strict` 欄位決定項目是否可以將元件新增到具有自己 `plugin.json` 的 plugin。它預設為 `true`。

### 項目欄位如何與 `plugin.json` 結合

項目要麼作為 manifest，要麼將元件新增到它，要麼與它衝突：

* **沒有 `plugin.json`**：項目是 manifest，無論 `strict` 如何。項目 `hooks` 僅以內聯物件形式載入。對於檔案路徑或陣列，`/plugin` **Errors** 標籤顯示 `not yet supported in a marketplace entry` 錯誤
* **`plugin.json` 存在，`strict` 未設定或 `true`**：Claude Code 載入 manifest 並將項目的 `commands`、`agents`、`skills`、`outputStyles` 和 `themes` 附加到它。對於 `hooks`，項目的事件匹配器取代 manifest 對該相同事件的匹配器，只有 manifest 宣告的事件保留其
* **`plugin.json` 存在，`strict: false`**：宣告 `commands`、`agents`、`skills`、`hooks`、`outputStyles` 或 `themes` 的項目是衝突，plugin 無法載入，出現 `Plugin <name> has conflicting manifests`

當[其 `source` 是 marketplace 根目錄的 marketplace 項目](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference)列出特定 `skills` 子目錄時，只有這些子目錄載入，plugin 的預設 `skills/` 目錄不會被掃描。manifest 中的 `skills` 鍵改為[新增到預設](#how-each-key-combines-with-its-default-location)。

### 中繼資料優先順序

某些中繼資料欄位有固定的優先順序，無論 `strict` 如何：

* **`defaultEnabled` 和顯示欄位**：項目的 `defaultEnabled` 和其[顯示欄位](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#entry-and-plugin-json)（例如 `displayName`）覆蓋 manifest 的
* **`version`**：manifest 的 `version` 覆蓋項目的
* **`name`**：當項目在與 manifest 不同的 `name` 下列出 plugin 時，`enabledPlugins` 使用項目名稱，元件在 manifest 名稱下命名空間

有關完整優先順序表，請參閱[嚴格模式](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md)。

## 後續步驟

* [將元件新增到 plugin](https://code.claude.com/docs/zh-TW/plugins/components.md)：每個元件在執行時的作用，以及驗證的範例
* [Marketplace 參考](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md)：marketplace 可以為您的 plugin 設定的項目欄位
* [Plugin 命令參考](https://code.claude.com/docs/zh-TW/plugins/cli-reference.md#plugin-validate)：`claude plugin validate` 旗標和輸出
* [疑難排解 plugin](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#claude-plugin-validate-reports-errors)：每條驗證訊息及其修正

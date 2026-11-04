<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/mcp | lastmod: 2026-11-02 | section: Build with Claude Code / MCP -->
> 來源：https://code.claude.com/docs/zh-TW/mcp（官方 zh-TW，lastmod 2026-11-02）｜分類：Build with Claude Code › MCP｜EN 摘要：Learn how to connect Claude Code to your tools with the Model Context Protocol.

# 透過 MCP 將 Claude Code 連接到工具

> 了解如何使用 Model Context Protocol 將 Claude Code 連接到您的工具。

Claude Code 可以透過 [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) 連接到數百個外部工具和資料來源，這是一個開源標準，用於 AI 工具整合。MCP servers 讓 Claude Code 能夠存取您的工具、資料庫和 API。

當您發現自己從另一個工具（例如問題追蹤器或監控儀表板）複製資料到聊天中時，請連接一個 server。連接後，Claude 可以直接讀取和操作該系統，而不是根據您貼上的內容進行工作。

如果您是第一次連接 server，請從 [MCP 快速入門](https://code.claude.com/docs/zh-TW/mcp-quickstart.md) 開始，以取得逐步說明。本頁面是完整參考。

## 使用 MCP 可以做什麼

使用連接的 MCP servers，您可以要求 Claude Code：

* **從問題追蹤器實現功能**："新增 JIRA 問題 ENG-4521 中描述的功能，並在 GitHub 上建立 PR。"
* **分析監控資料**："檢查 Sentry 和 Statsig，以檢查 ENG-4521 中描述的功能使用情況。"
* **查詢資料庫**："根據我們的 PostgreSQL 資料庫，找到 10 個使用功能 ENG-4521 的隨機使用者的電子郵件。"
* **整合設計**："根據在 Slack 中發佈的新 Figma 設計更新我們的標準電子郵件範本"
* **自動化工作流程**："建立 Gmail 草稿，邀請這 10 個使用者參加關於新功能的回饋會議。"
* **回應外部事件**：MCP server 也可以充當 [channel](https://code.claude.com/docs/zh-TW/channels.md)，將訊息推送到您的 session 中，因此當您不在時，Claude 可以回應 Telegram 訊息、Discord 聊天或 webhook 事件。

## 尋找並建立 MCP servers

在 [Anthropic Directory](https://claude.ai/directory) 中瀏覽已審核的連接器。Directory 連接器使用與 Claude Code 相同的 MCP 基礎設施，因此您可以使用 `claude mcp add` 新增任何列在其中的遠端伺服器。

> [!WARNING]
>
> 在連接伺服器之前，請驗證您信任每個伺服器。取得外部內容的伺服器可能會使您面臨[提示注入風險](https://code.claude.com/docs/zh-TW/security.md#protect-against-prompt-injection)。

若要建立您自己的伺服器，請參閱 [MCP server 指南](https://modelcontextprotocol.io/docs/develop/build-server) 以了解協議基礎知識，以及 [Claude 連接器建立文件](https://claude.com/docs/connectors/building) 以了解身份驗證、測試和 Directory 提交。

您也可以使用官方的 [`mcp-server-dev` plugin](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/mcp-server-dev) 讓 Claude 為您建立伺服器。

**1. 安裝外掛**

在 VS Code 擴充功能或桌面應用程式中，請改為依照[安裝外掛](https://code.claude.com/docs/zh-TW/plugins/install.md#install-a-plugin)操作，而非執行此步驟。在終端機中，執行 `claude` 啟動 Claude Code，然後在其提示字元輸入以下內容：

```
/plugin install mcp-server-dev@claude-plugins-official
```

如果安裝失敗，請符合 Claude Code 報告的訊息：

* `Marketplace "claude-plugins-official" not found`：使用 `/plugin marketplace add anthropics/claude-plugins-official` 新增市集，然後重試安裝。
* `Plugin "<name>" not found in marketplace "claude-plugins-official"`：您本機的市集目錄副本可能已過時。請使用 `/plugin marketplace update claude-plugins-official` 重新整理，然後重試安裝。如果重試後顯示相同的訊息，請參閱 [Plugin not found in marketplace](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#plugin-not-found-in-marketplace)。

如果安裝摘要報告 `Run /reload-plugins to apply.`，Claude Code 會為您執行該重新載入。如果重新載入警告您的下一則訊息會重新讀取對話，請執行 `/reload-plugins --force`。

**2. 執行建立 skill**

```
/mcp-server-dev:build-mcp-server
```

Claude 會詢問您的使用案例，並建立遠端 HTTP 或本機 stdio 伺服器。

## 安裝 MCP 伺服器

MCP 伺服器可依您的需求以多種方式設定：

### 選項 1：新增遠端 HTTP 伺服器

HTTP 伺服器是連線至遠端 MCP 伺服器的建議選項。這是雲端服務支援最廣泛的傳輸方式。

```bash theme={null}
# Basic syntax
claude mcp add --transport http <name> <url>

# Real example: Connect to Notion
claude mcp add --transport http notion https://mcp.notion.com/mcp

# Example with Bearer token
claude mcp add --transport http secure-api https://api.example.com/mcp \
  --header "Authorization: Bearer your-token"
```

透過 `.mcp.json`、`~/.claude.json` 或 `claude mcp add-json` 中的 JSON 設定 MCP 伺服器時，`type` 欄位接受 `streamable-http` 作為 `http` 的別名。MCP 規格使用 `streamable-http` 這個名稱來稱呼此傳輸方式，因此從伺服器文件複製的設定無需修改即可運作。

具有 `url` 但沒有 `type` 的 JSON 項目屬於設定錯誤，因為 Claude Code 會將沒有 `type` 的項目視為 stdio 伺服器。Claude Code 會略過該伺服器並回報 `MCP server "<name>" has a "url" but no "type"; add "type": "http" (or "sse" / "ws") to this entry`。

只有 SDK 主機應用程式，例如 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/mcp.md) 應用程式或[桌面應用程式](https://code.claude.com/docs/zh-TW/desktop.md)，才能註冊行程內的 `"type": "sdk"` 伺服器。Claude Code 會略過 `.mcp.json`、`~/.claude.json` 或設定中的 `"type": "sdk"` 項目，並回報 `Skipped — MCP server "<name>" declares type "sdk", which only an SDK host application can register`。

> [!NOTE]
>
> 在 `--output-format stream-json` 執行中，Claude Code 也會在 `system/init` 事件的 [`mcp_server_errors` 欄位](https://code.claude.com/docs/zh-TW/headless#stream-responses)中回報被略過的 `--mcp-config` 項目，讓指令碼能偵測到該伺服器從未載入。

### 選項 2：新增遠端 SSE 伺服器

> [!WARNING]
>
> SSE（Server-Sent Events）傳輸方式已棄用。若可行，請改用 HTTP 伺服器。

有些服務仍只提供 SSE 端點。請使用與 [HTTP 伺服器](#option-1-add-a-remote-http-server)相同的 `claude mcp add --transport http <name> <url>` 命令來新增這類伺服器。Claude Code 會先嘗試 HTTP 傳輸方式，並在伺服器不接受時切換為 SSE。自動切換需要 Claude Code v2.1.265 或更新版本。

若使用較早的版本，或要直接透過 SSE 連線，請改為傳入 `--transport sse`：

```bash theme={null}
# Basic syntax
claude mcp add --transport sse <name> <url>

# Real example: Connect to Asana
claude mcp add --transport sse asana https://mcp.asana.com/sse

# Example with authentication header
claude mcp add --transport sse private-api https://api.company.com/sse \
  --header "X-API-Key: your-key-here"
```

### 選項 3：新增本機 stdio 伺服器

Stdio 伺服器以本機程序的形式在您的電腦上執行。它們非常適合需要直接存取系統的工具或自訂指令碼。

Claude Code 會在所啟動伺服器的環境中將 `CLAUDE_PROJECT_DIR` 設為專案根目錄，讓您的伺服器能解析相對於專案的路徑，而不必依賴工作目錄。這與 hook 在其 `CLAUDE_PROJECT_DIR` 變數中收到的目錄相同。請在伺服器程序內讀取它，例如在 Node 中使用 `process.env.CLAUDE_PROJECT_DIR`，或在 Python 中使用 `os.environ["CLAUDE_PROJECT_DIR"]`。

`CLAUDE_PROJECT_DIR` 是固定的專案根目錄，在工作階段中途新增或移除工作目錄時不會改變。若伺服器要將自身的檔案系統存取限制在一組允許的目錄內，應改為實作 MCP `roots/list` 請求。Claude Code 會以工作階段的啟動目錄，加上您透過 `--add-dir`、`/add-dir` 或 `additionalDirectories` 設定授予的每個[額外工作目錄](https://code.claude.com/docs/zh-TW/permissions.md#working-directories)來回應 `roots/list`。當該集合變更時，Claude Code 會傳送 `notifications/roots/list_changed`。

此變數設定在伺服器的環境中，而非 Claude Code 本身的環境中，因此若要在專案範圍 `.mcp.json` 項目，或 `~/.claude.json` 中本機或使用者範圍伺服器項目的 `command` 或 `args` 中透過 `${VAR}` 展開來參照它，需要提供預設值，例如 `${CLAUDE_PROJECT_DIR:-.}`。外掛提供的 MCP 設定會直接替換 `${CLAUDE_PROJECT_DIR}`，不需要預設值。

```bash theme={null}
# Basic syntax
claude mcp add [options] <name> -- <command> [args...]

# Real example: Add Airtable server
claude mcp add --env AIRTABLE_API_KEY=YOUR_KEY --transport stdio airtable \
  -- npx -y airtable-mcp-server
```

> [!NOTE]
>
> 對於 stdio 伺服器，`--`（雙破折號）會將 Claude 本身的選項（例如 `--transport`、`--env` 和 `--scope`）與執行伺服器的命令和引數分隔開來。`--` 之後的所有內容都會原封不動地傳遞給伺服器。
>
> 例如：
>
> * `claude mcp add --transport stdio myserver -- npx server` → 執行 `npx server`
> * `claude mcp add --env KEY=value --transport stdio myserver -- python server.py --port 8080` → 在環境中帶有 `KEY=value` 的情況下執行 `python server.py --port 8080`
>
> 若沒有 `--`，Claude Code 會嘗試將伺服器的旗標（例如上方的 `--port`）當作自己的選項來解析。
>
> `--env` 接受多個 `KEY=value` 配對。若伺服器名稱直接接在 `--env` 之後，CLI 會將該名稱讀取為另一個配對並予以拒絕，因此請在 `--env` 與伺服器名稱之間至少放置一個其他選項，例如 `--transport stdio`。

#### Claude Code 如何停止 stdio 伺服器

當 Claude Code 中斷與 stdio 伺服器的連線時（例如工作階段結束時），它會向伺服器程序發送訊號，並短暫等待其結束，然後才強制停止。若您的伺服器會在關閉時儲存狀態或移除鎖定檔案，請處理您平台的訊號，並在該時間內完成：

* **在 macOS 和 Linux 上**：Claude Code 會傳送 `SIGINT`，若 100 毫秒後程序仍在執行則傳送 `SIGTERM`，再過 400 毫秒後傳送 `SIGKILL`。
* **在 Windows 上**：Claude Code 會關閉伺服器的 stdin，若 300 毫秒後程序仍在執行，則結束伺服器的程序樹。

在 v2.1.296 之前，Windows 上的 Claude Code 會立即結束伺服器的程序樹，而不會先關閉 stdin 或等待。

### 選項 4：新增遠端 WebSocket 伺服器

WebSocket 伺服器會維持持久的雙向連線，適合會主動向 Claude 推送事件的遠端 MCP 伺服器。若您的伺服器只回應請求，請改用 HTTP，因為 HTTP 支援 OAuth 和 `claude mcp add --transport` 旗標，而 WebSocket 兩者皆不支援。

請在 `.mcp.json` 中或使用 `claude mcp add-json` 設定 WebSocket 伺服器：

```bash theme={null}
claude mcp add-json events-server \
  '{"type":"ws","url":"wss://mcp.example.com/socket","headers":{"Authorization":"Bearer YOUR_TOKEN"}}'
```

`type: "ws"` 項目接受與 `http` 相同的 `url`、`headers`、`headersHelper`、`timeout` 和 `alwaysLoad` 欄位。身分驗證僅透過標頭進行，因此請在 `headers` 中傳入靜態 token，或在連線時使用 [`headersHelper`](#use-dynamic-headers-for-custom-authentication) 產生 token。`claude mcp add --transport` 旗標不接受 `ws`。

### 從為其他用戶端撰寫的設定說明新增伺服器

MCP 伺服器並非 Claude Code 專屬，因此伺服器的設定說明可能是為 Claude Desktop、Cursor 或其他 MCP 用戶端撰寫，且未提供 `claude mcp add` 命令。若仍要新增該伺服器，請在這些說明中尋找 URL、啟動命令或 JSON 區塊：

* **URL**，例如 `https://mcp.example.com/mcp`：伺服器位於遠端。
* **啟動命令**，例如 `npx -y @example/mcp-server`：伺服器在您的電腦上執行。
* **`mcpServers` JSON 區塊**：為其他用戶端的設定檔撰寫的設定。

每一種都是[安裝 MCP 伺服器](#installing-mcp-servers)中四個選項所接受的輸入之一。請在下方找到您所擁有的形式，將其轉換為 Claude Code 接受的命令。除非您加上 `--scope project` 或 `--scope user`，否則每個命令都會寫入[本機範圍](#local-scope)。

#### 從 URL 新增伺服器

URL 表示伺服器位於遠端。對於 `https://` 端點，請使用 `--transport http` 新增；若說明指出端點使用 SSE，則依照[選項 2](#option-2-add-a-remote-sse-server) 操作。對於 `wss://` 端點，請改用[選項 4](#option-4-add-a-remote-websocket-server)，因為 `--transport` 不接受 `ws`：

```bash theme={null}
claude mcp add --transport http example https://mcp.example.com/mcp
```

若說明還提供了 API 金鑰或 token 標頭，請如[選項 1](#option-1-add-a-remote-http-server) 所示，使用 `--header` 傳入。

#### 從 `npx`、`uvx` 或二進位檔命令新增伺服器

啟動命令表示伺服器以本機 stdio 程序的形式執行。請將整個命令放在 `--` 之後，讓 Claude Code 將 `-y` 等旗標傳遞給啟動伺服器的命令，而不是將其讀取為自己的選項。請在伺服器名稱之後、`--` 之前，使用 `--env` 傳入說明要求的任何環境變數：

```bash theme={null}
claude mcp add example --env API_KEY=your-key -- npx -y @example/mcp-server
```

[選項 3](#option-3-add-a-local-stdio-server) 完整說明了 `--` 分隔符號。

#### 從 `mcpServers` JSON 區塊新增伺服器

為其他 MCP 用戶端（例如 Claude Desktop）撰寫的 `mcpServers` 區塊，使用的是 Claude Code 可讀取的包裝鍵與項目形式。請將 `mcpServers` 內部的物件（而非包裝層）傳給 `claude mcp add-json`。有兩種項目需要先修正：

* **有 `url` 但沒有 `type`**：依端點加上 `"type": "http"`、`"type": "sse"` 或 `"type": "ws"`。Claude Code 會將沒有 `type` 的項目視為 stdio 伺服器，因此沒有 `type` 的 `url` 項目會失敗。
* **鍵包含字母、數字、連字號和底線以外的字元**：請選擇只使用這些字元的伺服器名稱。否則，該鍵即為伺服器名稱。

例如，這個區塊：

```json theme={null}
{
  "mcpServers": {
    "example": {
      "command": "npx",
      "args": ["-y", "@example/mcp-server"]
    }
  }
}
```

會變成這個命令：

```bash theme={null}
claude mcp add-json example '{"command":"npx","args":["-y","@example/mcp-server"]}'
```

[從 JSON 設定新增 MCP 伺服器](#add-mcp-servers-from-json-configuration)說明了 shell 跳脫處理以及 `add-json` 的 `--scope` 旗標。若要改為與團隊共用該伺服器，請加上 `--scope project`，或將該項目新增至專案根目錄中 `.mcp.json` 的 `mcpServers` 下並提交。[專案範圍](#project-scope)說明了 Claude Code 如何載入及核准該檔案。

每個 `claude mcp add` 和 `claude mcp add-json` 命令成功時都會印出一行 `Added ...`。若要確認 Claude Code 已連線，請執行 `claude mcp get <name>`；[伺服器狀態](#server-status)說明了它所顯示的狀態，以及 `.mcp.json` 伺服器的核准步驟。

### 管理您的伺服器

設定完成後，您可以使用以下命令管理 MCP 伺服器：

```bash theme={null}
# List all configured servers
claude mcp list

# Get details for a specific server
claude mcp get notion

# Remove a server
claude mcp remove notion

# (within Claude Code) Check server status
/mcp
```

當您移除遠端伺服器時，Claude Code 也會刪除為該伺服器儲存的 OAuth token 與用戶端註冊資訊。Claude Code 不會在核發這些 token 的授權伺服器上撤銷它們。若授權伺服器支援撤銷，要在該處撤銷 token，請在 `claude mcp remove <name>` 之前，於 shell 中執行 [`claude mcp logout <name>`](#authenticate-from-the-command-line)。

#### 伺服器狀態

`claude mcp add` 會印出一行 `Added ...` 以確認新增成功，這表示設定已寫入。若命令改為印出 `was not saved` 訊息，請參閱 [MCP server was not saved or removed](https://code.claude.com/docs/zh-TW/errors.md#mcp-server-was-not-saved-or-removed)；若為 `may not have been saved` 訊息，請參閱 [MCP server may not have been saved or removed](https://code.claude.com/docs/zh-TW/errors.md#mcp-server-may-not-have-been-saved-or-removed)。

`claude mcp list` 會在列出的每個伺服器旁顯示健康狀態，例如 `✔ Connected`、`! Needs authentication` 或 `✘ Failed to connect`。失敗狀態表示 Claude Code 無法連線至該伺服器，而不是 list 命令失敗。

以下清單中的狀態回報的是設定上的決定，而非連線嘗試，因此 Claude Code 會在不連線至伺服器的情況下印出它們：

* ``⏸ Pending approval (run `claude` to approve)``：來自 `.mcp.json`、您尚未核准的專案範圍伺服器。Claude Code 會在 `claude mcp list` 和 `claude mcp get <name>` 中都顯示此狀態。請以互動方式執行 `claude` 來檢閱並核准它。
* `✘ Rejected (see disabledMcpjsonServers in settings)`：被 [`disabledMcpjsonServers`](https://code.claude.com/docs/zh-TW/settings-reference#disabledmcpjsonservers) 項目拒絕的 `.mcp.json` 伺服器。Claude Code 只會在 `claude mcp get <name>` 中顯示它。
* `⊘ Disabled for this project (re-enable via /mcp)`：專案的 [`disabledMcpServers`](#disable-a-server-without-removing-it) 清單中列出的伺服器。Claude Code 會在 `claude mcp list` 和 `claude mcp get <name>` 中都顯示它。請從 `/mcp` 面板重新啟用該伺服器。
* `✘ Blocked by enterprise managed policy`：被您組織的某項政策拒絕的伺服器。Claude Code 會在 `claude mcp list` 和 `claude mcp get <name>` 中都顯示此狀態。被[受管 MCP 設定](https://code.claude.com/docs/zh-TW/managed-mcp.md#how-restrictions-appear-to-users)中的允許清單、拒絕清單或其他限制封鎖的伺服器，會在兩個命令中都被隱藏，而不是以此狀態顯示。請詢問您的管理員是哪項政策封鎖了該伺服器。

#### 專案伺服器核准與工作區信任

在您於工作區中執行 `claude` 並接受工作區信任對話框以信任該工作區之前，`claude mcp list` 和 `claude mcp get` 只會從未簽入儲存庫的設定檔讀取 `.mcp.json` 核准。複製下來的儲存庫無法核准自己的伺服器：在未受信任的資料夾中，提交至專案 `.claude/settings.json` 的 [`enableAllProjectMcpServers`](https://code.claude.com/docs/zh-TW/settings-reference#enableallprojectmcpservers) 或 [`enabledMcpjsonServers`](https://code.claude.com/docs/zh-TW/settings-reference#enabledmcpjsonservers) 會被忽略，伺服器會停留在 `⏸ Pending approval`，而不會被連線並進行健康檢查。

來自以下來源的核准在未受信任的資料夾中仍然適用：

* 您的使用者 `~/.claude/settings.json`
* 受管設定
* 透過 `--settings` 傳入的設定

Claude Code 也會套用來自未追蹤的 `.claude/settings.local.json` 的核准，但它會執行 git 來檢查該檔案是否被追蹤，而且只會在[受信任的資料夾](https://code.claude.com/docs/zh-TW/permissions.md#project-allow-rules-and-workspace-trust)中執行該檢查。在您從未信任過的資料夾中，Claude Code 會等待信任對話框後才套用該檔案的核准，除非該資料夾是您自己的設定主目錄：也就是您的家目錄，或其 `.claude` 已被您設為 [`CLAUDE_CONFIG_DIR`](https://code.claude.com/docs/zh-TW/env-vars) 的目錄。在 v2.1.207 之前，即使在您從未信任過的資料夾中，Claude Code 也會套用來自未追蹤的 `.claude/settings.local.json` 的核准。

任何設定檔中的 `disabledMcpjsonServers` 項目仍會拒絕該伺服器。

#### 伺服器狀態詳細資訊

在 `/mcp`（包括其中的伺服器選單）以及 [`/plugin`](https://code.claude.com/docs/zh-TW/plugins/install) 管理器中，您先前使用過的遠端 HTTP 或 SSE 伺服器可能會顯示 `cached` 狀態，例如 `cached 2h ago · connects on first use · 5 tools`。Claude Code 是從先前工作階段儲存的探索快取中載入伺服器的工具清單，而非在啟動時連線，並會在 Claude 第一次呼叫該伺服器的某個工具時連線該伺服器。這些工具從您的第一則訊息開始就可使用，因此您無需執行任何操作。探索快取及其 `cached` 狀態需要 Claude Code v2.1.221 或更新版本。

除非逐步推出已為您的帳戶啟用，否則探索快取預設為關閉。設定 [`MCP_DISCOVERY_CACHE=1`](https://code.claude.com/docs/zh-TW/env-vars) 可將其開啟，或設為 `0` 以在推出已啟用時仍保持關閉。在 v2.1.238 之前，快取預設為開啟。

當您從 `/mcp` 中伺服器的選單選取 **Disable** 或 **Clear authentication** 時，Claude Code 也會捨棄該伺服器的快取項目。對已連線或失敗的伺服器，**Reconnect** 也會捨棄它；對 `cached` 伺服器，**Reconnect** 會立即連線伺服器並保留該項目。捨棄項目後，Claude Code 下次連線至該伺服器時，會從伺服器而非快取擷取工具清單。

##### 連線失敗與未設定的伺服器

當伺服器的狀態為 `✘ Failed to connect` 時，`claude mcp list` 會將失敗詳細資訊附加在該狀態行後，而 `claude mcp get <name>` 會在 `Issue:` 行中顯示它。詳細資訊為 HTTP 狀態或錯誤碼，加上伺服器傳回的任何錯誤文字。`/mcp` 中伺服器的詳細檢視會在其 `Issue:` 列中包含相同的伺服器回報文字。

Claude Code 會從這些詳細資訊中遮蔽類似憑證的文字，且永遠不會包含展開後的伺服器 URL，因為其中可能帶有機密資訊。Claude Code 不會在 `✘ Connection error` 狀態後附加任何詳細資訊，因為它在該處會印出的例外文字可能內嵌該 URL。

當您從 `/mcp` 完成身分驗證，但連線仍因 HTTP 狀態或傳輸錯誤代碼而失敗時，Claude Code 會在嘗試後印出的訊息中加入該代碼以及伺服器 URL 的來源。來源是指通訊協定與主機，若 URL 有指定連接埠則加上連接埠，例如 `https://mcp.example.com`。

* 該訊息中絕不會出現路徑與查詢字串。
* 對於本機、專案或使用者[範圍](#mcp-installation-scopes)中或受管 MCP 設定中的伺服器，來源會顯示該設定中所寫的主機，因此主機中的 `${VAR}` 參照不會在訊息中展開。
* 對於沒有狀態或錯誤代碼的失敗，Claude Code 會顯示錯誤文字，但不含來源。

設定中 `url` 為空的遠端伺服器，在 `/mcp`、`claude mcp list` 和 [`/plugin`](https://code.claude.com/docs/zh-TW/plugins/install) 管理器中會顯示為 `not configured`，且 Claude Code 不會嘗試連線至它。外掛可以為您稍後設定的連接器加入這類預留項目，因此 Claude Code 不會將其回報為錯誤或設定問題。`/mcp` 中該伺服器的詳細資訊檢視會顯示 `No URL configured for this server`；請設定該項目的 `url` 以進行連線。

#### 設定警告

Claude Code 會針對以下設定問題發出警告。每個項目都說明了 Claude Code 檢查的內容以及如何清除警告：

* **隱藏的空白字元**：當 MCP 設定值帶有隱藏的前導或尾隨空白字元時，Claude Code 會發出警告，這通常來自貼上帶有尾隨換行字元的 token。Claude Code 會檢查 `command`、`url`、每個 `args` 項目，以及 `env` 和 `headers` 下的值與鍵名稱。Claude Code 會在 `claude mcp list` 輸出和 `/mcp` 中顯示警告，列出受影響的欄位但不顯示其值，例如 `Leading or trailing whitespace in: headers.Authorization`。Claude Code 不會修剪空白字元，而是完全依照所寫的內容使用這些值，因此請編輯設定將其移除。
* **同一名稱存在於多個範圍**：若您在多個[範圍](#mcp-installation-scopes)中以不同端點定義了相同的伺服器名稱，Claude Code 會在 `claude mcp list` 輸出和 `/mcp` 中警告此衝突。Claude Code 會依端點儲存 OAuth 登入，因此當您為在某個專案中載入的定義進行身分驗證後，在載入不同定義的專案中仍需另外登入。請保留您要的端點，並使用 `claude mcp remove <name> --scope <scope>` 移除其他端點。在警告中，Claude Code 會引用您設定中所寫的每個範圍的端點，其中的 [`${VAR}` 參照](#environment-variable-expansion-in-mcp-json)不會展開，因此絕不會顯示 API 金鑰等已解析的值。
* **保留名稱**：Claude Code 保留了其內建伺服器的名稱，包括 `workspace`、`claude-in-chrome`、`computer-use`、`Claude Preview` 和 `Claude Browser`。若您的設定定義了使用保留名稱的伺服器，Claude Code 會在載入時略過它，並顯示警告要求您重新命名。`claude mcp add` 會以錯誤拒絕保留名稱。`Claude Preview` 和 `Claude Browser` 都是指 [Claude Code 桌面應用程式預覽窗格](https://code.claude.com/docs/zh-TW/desktop.md#preview-your-app)所使用的內建伺服器。
* **缺少環境變數**：若伺服器設定中的 [`${VAR}` 參照](#environment-variable-expansion-in-mcp-json)指名了一個未設定且沒有 `:-default` 的變數，Claude Code 會在 `claude mcp list` 輸出和 `/mcp` 中發出警告並指出該變數，並仍以未展開的 `${VAR}` 文字載入伺服器。請設定該變數或加上 `${VAR:-default}` 備援值。在遠端伺服器的 `url` 和 `headers` 中，某些憑證變數則會[讀取為空值](#credential-variables-that-read-as-empty)，且不會發出警告。

#### 工具可用性

`/mcp` 面板會在每個已連線伺服器旁顯示工具數量，並標示出宣告具備工具能力但未公開任何工具的伺服器。

若您的請求需要來自仍在背景連線中的伺服器的工具，Claude 會等待該伺服器後再繼續。等待的方式取決於您的設定：

* **使用[工具搜尋](#scale-with-mcp-tool-search)（預設）**：等待發生在 `ToolSearch` 呼叫內。
* **不使用工具搜尋**：Claude 改為使用 `WaitForMcpServers` 工具。不使用工具搜尋的設定包括 `ENABLE_TOOL_SEARCH=false`，以及在 Google Cloud 的 Agent Platform 上使用早於 Claude Opus 4.5、Claude Sonnet 4.5 和 Claude Haiku 4.5 的模型。關於 `ANTHROPIC_BASE_URL` 閘道，請參閱[透過 LLM 閘道使用工具搜尋](#tool-search-through-a-gateway)。
* **在 Microsoft Foundry [託管於 Azure 的部署](https://platform.claude.com/docs/en/build-with-claude/claude-in-microsoft-foundry#hosting-options)上**：Claude 會從工具搜尋路徑開始，而非使用 `WaitForMcpServers`，因為 Claude Code 只能從 API 得知該部署在伺服器端的拒絕。在 Claude Code 將該部署切換為[預先載入](#scale-with-mcp-tool-search)後，來自完成連線之伺服器的工具會在 Claude 的下一個請求中變為可用。

啟用工具搜尋時，若伺服器在 Claude 工作期間完成連線，Claude Code 會在同一回合中 Claude 的下一個請求裡，向 Claude 列出該伺服器的工具名稱。Claude 隨後即可搜尋並呼叫這些工具，而無需等待您的下一則訊息。

在您恢復工作階段後，Claude 可能會在某工具的 MCP 伺服器仍在連線時，呼叫已儲存對話中的該工具。當伺服器正在進行第一次連線嘗試時，Claude Code 會將呼叫保留最多 10 秒，並在工具可用時執行它。若伺服器未及時連線，或已在[失敗嘗試後重試中](#automatic-reconnection)，該呼叫會以 `No such tool available` [工具錯誤](https://code.claude.com/docs/zh-TW/errors.md#no-such-tool-available)失敗。

### 停用伺服器而不移除它

在 `/mcp` 面板中關閉伺服器，可阻止 Claude Code 連線至該伺服器，而不會遺失其設定。Claude Code 仍會在 `/mcp` 中列出該伺服器，並標示為已停用。

當您切換伺服器時，Claude Code 會依專案將您的選擇記錄在 `~/.claude.json` 中的兩個清單之一，這兩個清單涵蓋互不重疊的伺服器集合：

* `disabledMcpServers`：選擇退出清單，適用於使用者設定的伺服器、外掛伺服器、您的組織[透過受管設定提供的伺服器](https://code.claude.com/docs/zh-TW/managed-mcp.md#provide-servers-through-managed-settings)、Claude Code [自行擷取](#how-connectors-reach-claude-code)的 claude.ai 連接器，以及預設開啟的內建伺服器。Claude Code 不會連線至您列在此處的伺服器。當您使用[停用 claude.ai 連接器](#disable-claude-ai-connectors)中所述的各專案 `/mcp` 切換開關停用 claude.ai 連接器時，Claude Code 會以其顯示名稱將其寫入此清單，例如 `claude.ai Slack`。
* `enabledMcpServers`：選擇加入清單，適用於預設關閉的內建伺服器，例如 `computer-use`。Claude Code 只有在您將預設關閉的伺服器列在此處時才會連線至它。

Claude Code 對每個伺服器只會查閱兩個清單中的其中一個，因此任一清單都不會覆寫另一個。若您將一般伺服器加入 `enabledMcpServers`，或將預設關閉的內建伺服器加入 `disabledMcpServers`，Claude Code 會忽略該項目。

`disabledMcpServers` 和 `enabledMcpServers` 與 [`enabledMcpjsonServers`](https://code.claude.com/docs/zh-TW/settings-reference#enabledmcpjsonservers) 及 [`disabledMcpjsonServers`](https://code.claude.com/docs/zh-TW/settings-reference#disabledmcpjsonservers) 無關，後兩者控制的是專案 `.mcp.json` 檔案中所定義伺服器的核准。

### MCP 用戶端執行環境

Claude Code 透過兩種用戶端執行環境之一連線至 MCP 伺服器。v1 執行環境建置於 MCP TypeScript SDK 1.x 之上。v2 執行環境是建置於 [MCP TypeScript SDK 2.0](https://ts.sdk.modelcontextprotocol.io/v2/) 之上的相同程式碼，並加入了 MCP 協定修訂版 2026-07-28。本頁其餘內容同時適用於兩種執行環境，除非某節指明為 v2 執行環境。

Claude Code 每次啟動時都會選擇一種執行環境，並持續使用直到您結束。在會[擷取功能旗標](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)的工作階段中，Claude Code v2.1.232 或更新版本會使用 v2 執行環境。

在不擷取功能旗標的工作階段中，Claude Code v2.1.274 或更新版本預設使用 v2 執行環境：

* 在 Amazon Bedrock、Claude Platform on AWS、Google Cloud 的 Agent Platform 或 Microsoft Foundry 上的工作階段，除非內嵌 Claude Code 的主機平台設定了 [`CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST`](https://code.claude.com/docs/zh-TW/env-vars)
* 透過 [Claude apps 閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)登入的工作階段
* 您關閉遙測或功能旗標擷取的工作階段，例如使用 `DISABLE_TELEMETRY`

在 v2 上，Claude Code 還會：

* 詢問 HTTP、stdio 和 claude.ai 連接器伺服器是否支援較新的修訂版，並與支援的伺服器使用該修訂版。這包括雲端和 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 工作階段的連接器。Claude Code 會以與 v1 相同的方式連線至其他所有伺服器。
* 透過[保持開啟的串流](#notification-streams-on-the-v2-runtime)，從使用較新修訂版的伺服器接收 `list_changed` 通知。
* 不會註冊以較新修訂版連線的[頻道](#push-messages-with-channels)伺服器，因為該修訂版無法承載頻道訊息。
* 當[MCP OAuth 登入](#authenticate-with-remote-mcp-servers)的授權回應指名了非預期的發行者時，使登入失敗。
* 只將 [MCP OAuth](#authenticate-with-remote-mcp-servers) 憑證傳送至透過 HTTPS 提供服務，或位於 `localhost`、`127.0.0.1` 或 `::1` 的 token 端點。對於 token 端點在其他任何位置使用純 `http://` 的伺服器（例如您本機網路上的裝置），登入會失敗。請參閱 [Refusing to send credentials to non-https token endpoint](https://code.claude.com/docs/zh-TW/errors.md#refusing-to-send-credentials-to-non-https-token-endpoint)。

Anthropic 可以透過 Claude Code 擷取的功能旗標，讓特定伺服器維持使用較早的協定，或不使用該串流。

若要自行選擇執行環境，請將 [`MCP_SDK_GENERATION`](https://code.claude.com/docs/zh-TW/env-vars) 設為 `v1` 或 `v2`。若要決定 Claude Code 是否詢問，請將 [`MCP_PROTOCOL_NEGOTIATION`](https://code.claude.com/docs/zh-TW/env-vars) 設為 `auto` 或 `legacy`。

### 動態工具更新

MCP 伺服器可以在連線期間變更其提供的工具、提示詞或資源，並傳送 `list_changed` 通知。收到通知時：

* **在互動式終端機工作階段中**，Claude Code 會從該伺服器擷取更新後的清單，因此您無需重新連線。
* **在使用 `-p` 旗標的[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)及 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 中**，Claude Code 收到這些通知時只會重新整理工具清單。

若重新整理請求失敗，Claude Code 會保留該伺服器先前探索到的工具、提示詞和資源，直到之後的重新整理成功為止。

#### v2 執行環境上的通知串流

在 [v2 執行環境](#mcp-client-runtimes)上，Claude Code 會透過保持開啟的串流，從使用較新協定修訂版的伺服器接收 `list_changed` 通知。串流關閉時，Claude Code 會重新開啟它，但有兩項限制：

* **串流在 10 秒內再次關閉**：Claude Code 最多重新開啟三次，之後對該連線停止重新開啟。
* **串流保持開啟超過 10 秒後才關閉**（連至無伺服器主機的串流通常如此）：在一小時內重新開啟五次後，Claude Code 會等待約六小時才進行下一次。

在串流重新開啟之前，您會保留該伺服器最後擷取的工具、提示詞和資源。若要更快取得其變更，請從 `/mcp` 重新連線該伺服器。

### 自動重新連線

Claude Code 會重新連線在工作階段中途斷線的遠端伺服器，並在發生暫時性錯誤後重試 HTTP 或 SSE 伺服器的第一次連線。關於 stdio 伺服器，請參閱[結束或無法啟動的 stdio 伺服器](#stdio-servers-that-exit-or-fail-to-start)。

#### 遠端伺服器在工作階段中途斷線

Claude Code 會先以指數退避嘗試重新連線斷線的遠端伺服器最多五次，從一秒延遲開始，每次加倍：

* **在互動式工作階段中**：Claude Code 重新連線時，`/mcp` 會將該伺服器顯示為擱置中。五次嘗試都失敗後，Claude Code 會將該伺服器標示為失敗，或在伺服器需要重新授權時標示為需要身分驗證。標示為失敗時，您會看到 `MCP server "<name>" disconnected · open /mcp to reconnect` 通知。您可以從 `/mcp` 手動重試。
* **在 [`claude -p`](https://code.claude.com/docs/zh-TW/headless) 執行和 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 工作階段中**：Claude Code 會進行相同的五次嘗試，但沒有 `/mcp` 面板可顯示。若五次都失敗，執行會在沒有該伺服器工具的情況下繼續：
  * **在暫時性錯誤之後，例如 5xx 回應或逾時**：Claude Code 會在背景持續重試 HTTP 或 SSE 伺服器。重試最多持續約半小時，當其中一次連線成功時，該伺服器的工具會再次變為可用。在此之前，Agent SDK 工作階段會回報[狀態](https://code.claude.com/docs/zh-TW/agent-sdk/mcp.md#error-handling) `failed`，而您的程式碼可以[重新連線該伺服器](https://code.claude.com/docs/zh-TW/agent-sdk/mcp.md#error-handling)。若要在 `claude -p` 中重新連線，請重新開始執行。
  * **當伺服器[需要您重新登入](#authenticate-with-remote-mcp-servers)時**：Claude Code 會停止重試，Agent SDK 工作階段會將該伺服器的狀態回報為 `needs-auth`。請在您的 shell 中使用 [`claude mcp login <name>`](#authenticate-from-the-command-line) 登入。然後重新開始執行，或在 Agent SDK 工作階段中改為[重新連線該伺服器](https://code.claude.com/docs/zh-TW/agent-sdk/mcp.md#error-handling)。

#### 第一次連線失敗

當 HTTP 或 SSE 伺服器的第一次連線因暫時性錯誤（例如 5xx 回應、連線被拒或逾時）而失敗時，Claude Code 最多會重試三次。若連線仍然失敗，Claude Code 會將該伺服器標示為失敗。

這些重試在以下情況不適用：

* stdio 伺服器的第一次連線。若要再試一次，請參閱[結束或無法啟動的 stdio 伺服器](#stdio-servers-that-exit-or-fail-to-start)
* WebSocket 伺服器的第一次連線。若要在互動式終端機工作階段中再試一次，請從 `/mcp` 中該伺服器的選單選取 **Reconnect**
* 身分驗證或找不到的錯誤，因為這需要變更設定才能解決。當 [`headersHelper`](#use-dynamic-headers-for-custom-authentication) 是伺服器 `Authorization` 標頭的唯一來源時，Claude Code 仍會重試身分驗證錯誤，因為它在每次嘗試時都會重新執行該 helper，並可能取得新的憑證

#### 結束或無法啟動的 stdio 伺服器

若要重新啟動 stdio 伺服器，請閱讀符合其發生情況的欄位。請依您執行 Claude Code 的方式找到對應的列：互動式工作階段、`claude -p` 執行或 Agent SDK 工作階段。

| 您執行 Claude Code 的方式 | 伺服器程序在工作階段中途結束 | 伺服器的第一次連線失敗 |
| - | - | - |
| 互動式工作階段 | Claude Code 將該伺服器標示為失敗。若要重新啟動，請從 `/mcp` 中該伺服器的選單選取 **Reconnect** | Claude Code 將該伺服器標示為失敗。若要重新啟動，請從 `/mcp` 中該伺服器的選單選取 **Reconnect** |
| `claude -p` 執行 | Claude Code 會在 Claude 下次呼叫該伺服器的某個工具時重新啟動伺服器，並在伺服器連線後執行該呼叫 | 執行會在沒有該伺服器工具的情況下繼續。若要讓 Claude Code 再次嘗試連線，請重新開始執行。當伺服器由外掛提供時，新的執行會在失敗後 15 分鐘內略過連線，因此請先等待這段時間，或[更早重試](https://code.claude.com/docs/zh-TW/errors.md#skipping-connection-recent-failure-cached) |
| Agent SDK 工作階段 | Claude Code 會在 Claude 下次呼叫該伺服器的某個工具時重新啟動伺服器，並在伺服器連線後執行該呼叫 | 工作階段會在沒有該伺服器工具的情況下繼續。您的程式碼可以[重新連線該伺服器](https://code.claude.com/docs/zh-TW/agent-sdk/mcp.md#error-handling) |

#### 探索請求失敗

伺服器連線後，Claude Code 會向其傳送能力探索請求，例如 `tools/list`、`prompts/list` 和 `resources/list`。發生暫時性網路或伺服器錯誤後，Claude Code 會以短暫退避重試這些請求最多三次。它不會重試身分驗證錯誤、4xx 回應或請求逾時。

#### 自行重試失敗的伺服器

若要重試每個失敗或需要身分驗證的伺服器，請在互動式終端機工作階段的 Claude Code 提示字元執行 `/mcp reconnect all`。這需要 Claude Code v2.1.284 或更新版本。較早的版本會印出 `MCP server "all" not found`。

#### Claude 如何得知伺服器失敗

Claude Code 是否會告知 Claude 某個已設定的伺服器連線失敗，取決於[工具搜尋](#scale-with-mcp-tool-search)，該功能預設為開啟：

* 使用工具搜尋時，Claude Code 會告知 Claude 哪個伺服器失敗及其連線錯誤，因此 Claude 會在其回應中回報連線失敗。Claude Code 也會在找不到相符工具的 `ToolSearch` 結果中包含相同的資訊。
* 在任何[不使用工具搜尋的設定](#configure-tool-search)中，Claude Code 不會向 Claude 回報失敗的伺服器連線。

### 使用頻道推送訊息

MCP 伺服器也可以直接將訊息推送到您的工作階段中，讓 Claude 能對外部事件做出反應，例如 CI 結果、監控警示或聊天訊息。若要啟用此功能，您的伺服器需宣告 `claude/channel` 能力，並由您在啟動時以 `--channels` 旗標選擇加入。請參閱[頻道](https://code.claude.com/docs/zh-TW/channels.md)以使用官方支援的頻道，或參閱[頻道參考](https://code.claude.com/docs/zh-TW/channels-reference.md)以建立您自己的頻道。

在 [v2 執行環境](#mcp-client-runtimes)上，協商使用 MCP 協定修訂版 2026-07-28 的頻道伺服器無法傳遞頻道訊息，因此 Claude Code 不會將其註冊為頻道。不支援該修訂版的頻道伺服器會以較早的交握方式連線，並如往常一樣註冊。

Claude Code 預設會向 stdio 伺服器要求該修訂版。若要讓 stdio 頻道伺服器維持使用較早的交握方式，請將 [`MCP_PROTOCOL_NEGOTIATION`](https://code.claude.com/docs/zh-TW/env-vars) 設為 `legacy`，這會讓所有伺服器都維持使用較早的交握方式。

> [!TIP]
>
> 提示：
>
> * 使用 `-s` 或 `--scope` 旗標指定設定的儲存位置：
>   * `local`（預設）：僅在目前專案中供您使用
>   * `project`：透過 `.mcp.json` 檔案與專案中的所有人共用
>   * `user`：在所有專案中供您使用
> * 使用 `-e` 或 `--env` 旗標設定環境變數（例如 `-e KEY=value`）
> * `--transport` 和 `--header` 旗標也接受 `-t` 和 `-H` 簡寫形式
> * 使用 `MCP_TIMEOUT` 環境變數設定 MCP 伺服器啟動逾時（例如 `MCP_TIMEOUT=10000 claude` 會設定 10 秒逾時）
> * 在該伺服器的 `.mcp.json` 項目中加入以毫秒為單位的 `timeout` 欄位，即可為個別伺服器設定工具執行逾時，例如 `"timeout": 600000` 代表十分鐘。這只會針對該伺服器覆寫 `MCP_TOOL_TIMEOUT` 環境變數
> * 當 MCP 工具輸出超過 10,000 個 token 時，Claude Code 會顯示警告，且預設將輸出限制在 25,000 個 token。若要變更 token 限制，請設定 `MAX_MCP_OUTPUT_TOKENS` 環境變數，例如 `MAX_MCP_OUTPUT_TOKENS=50000`。警告閾值是固定的。除非伺服器提高了工具本身的限制，否則超過 50,000 個字元的成功文字結果無論此變數為何都會儲存至檔案。請參閱 [MCP 輸出限制與警告](#mcp-output-limits-and-warnings)
> * 使用 `/mcp` 向需要 OAuth 2.0 身分驗證的遠端伺服器進行身分驗證

### MCP 工具呼叫的時間限制

若要限制 MCP 工具呼叫可執行的時間長度：

* **個別伺服器**：在該伺服器的設定項目中加入以毫秒為單位的 `timeout` 欄位
* **所有伺服器**：設定 [`MCP_TOOL_TIMEOUT`](https://code.claude.com/docs/zh-TW/env-vars)

個別伺服器的 `timeout` 是每次工具呼叫的硬性實際時間限制，伺服器的進度通知不會延長它。低於 1000 的值會被忽略，並改用 `MCP_TOOL_TIMEOUT`，若該變數未設定，則改用其約 28 小時的預設值。對於 HTTP、SSE 或 [claude.ai 連接器](https://code.claude.com/docs/zh-TW/mcp.md#use-mcp-servers-from-claude-ai)伺服器，還有第二個針對每個請求的計時器，涵蓋每個請求直到收到伺服器的第一個回應位元組為止。Claude Code 會將該計時器設為三個值中的最大值：60 秒、適用於該伺服器的工具逾時，以及 `MCP_TIMEOUT`。未設定 `MCP_TOOL_TIMEOUT` 時的 28 小時預設值不會納入該比較，且低於 60 秒的值不會縮短該計時器。Stdio 和 WebSocket 伺服器沒有針對每個請求的計時器。

至少為 1000 的個別伺服器 `timeout` 也會作為下述閒置逾時的下限：Claude Code 絕不會比個別伺服器的 `timeout` 更早因閒置而中止該伺服器的工具呼叫。

若 MCP 伺服器在閒置時間範圍內沒有傳送任何回應或進度通知，對其的工具呼叫會以錯誤中止，而不是等到實際時間限制。閒置逾時適用於 IDE 伺服器和 SDK 行程內伺服器以外的所有伺服器類型。閒置時間範圍預設為：HTTP、SSE、WebSocket 和 [claude.ai 連接器](#use-mcp-servers-from-claude-ai)伺服器為五分鐘，stdio 伺服器為 30 分鐘。

請以毫秒為單位設定 [`CLAUDE_CODE_MCP_TOOL_IDLE_TIMEOUT`](https://code.claude.com/docs/zh-TW/env-vars) 環境變數來變更閒置時間範圍，或將其設為 `0` 以停用此檢查。

這些逾時限制的是呼叫可以執行多久，而不一定是它會阻擋工作階段多久：執行超過兩分鐘的主要對話呼叫會先移至背景任務。請參閱[長時間工具呼叫的自動背景化](#automatic-backgrounding-of-long-tool-calls)。

### 長時間工具呼叫的自動背景化

若背景呼叫在 [`/tasks`](https://code.claude.com/docs/zh-TW/commands#all-commands) 中的詳細資訊檢視顯示 `runs on the server; survives exiting this session`，請參閱[在伺服器上執行的 MCP 任務](#mcp-tasks-that-run-on-the-server)。

主要對話中的 MCP 工具呼叫若在兩分鐘後仍在執行，會移至背景任務，而不會阻擋工作階段。Claude 會立即收到任務 ID 並繼續工作，呼叫結束時，結果會以任務通知的形式送達。

該任務會出現在 [`/tasks`](https://code.claude.com/docs/zh-TW/commands#all-commands) 中，您也可以在那裡停止它，且它不會在結束工作階段後延續。任務的項目會顯示伺服器回報的最新進度。若您停止任務，Claude Code 會取消呼叫並告知 Claude 不會有結果。停止並不保證伺服器會停止：它可能已完成部分工作，或仍可能完成它。

呼叫在背景執行時，每次呼叫的限制仍然適用：由個別伺服器 `timeout` 或 [`MCP_TOOL_TIMEOUT`](https://code.claude.com/docs/zh-TW/env-vars) 設定的實際時間限制，以及由 [`CLAUDE_CODE_MCP_TOOL_IDLE_TIMEOUT`](https://code.claude.com/docs/zh-TW/env-vars) 設定的閒置逾時。

若要變更或關閉自動背景化：

* 以毫秒為單位設定 [`CLAUDE_CODE_MCP_AUTO_BACKGROUND_MS`](https://code.claude.com/docs/zh-TW/env-vars) 環境變數來變更閾值，或將其設為 `0` 以關閉自動背景化。設為 `0` 時，Claude 在互動式工作階段中也會[等待 MCP 任務](#make-claude-wait-for-the-result-of-an-mcp-task)
* 將 [`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS`](https://code.claude.com/docs/zh-TW/env-vars) 設為 `1`，可關閉自動背景化和[背景命令](https://code.claude.com/docs/zh-TW/tools-reference.md#background-commands)

有些呼叫永遠不會移至背景：

* 來自 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 的呼叫；Claude Code 只會將主要對話的呼叫背景化
* 對 IDE 伺服器的呼叫
* [非互動模式](https://code.claude.com/docs/zh-TW/headless.md)中的呼叫，除非 `CLAUDE_AUTO_BACKGROUND_TASKS` 設為 `1`，因為單次執行可能在結果送達前就結束

等待開啟中之[引導對話框](#respond-to-mcp-elicitation-requests)的呼叫，在對話框開啟期間不會被背景化；伺服器是在等待您的輸入，而不是速度慢，因此 Claude Code 會將移動延後至對話框關閉為止。

### 在伺服器上執行的 MCP 任務

MCP 任務是 MCP 伺服器使用 [MCP tasks 擴充功能](https://modelcontextprotocol.io/extensions/tasks/overview)自行執行的長時間工作，例如報表匯出或建置。伺服器一接受該工作，Claude 的工具呼叫就會返回，因此除非您[讓 Claude 等待](#make-claude-wait-for-the-result-of-an-mcp-task)，否則 Claude 會繼續工作。工作結束時，逐字稿會顯示此情況，而 Claude 會取得結果。請向 Claude 詢問結果。

在此期間，頁尾會顯示如 `1 MCP task` 的計數，而 Claude Code 會透過向伺服器檢查其狀態來追蹤該任務。遠端伺服器上的任務在您結束後仍會繼續執行。若要再次追蹤它，請[恢復同一個工作階段](#exit-clear-or-resume-while-an-mcp-task-runs)。

> [!NOTE]
>
> MCP 任務在 Claude Code CLI 中處於公開測試版階段，需要 Claude Code v2.1.304 或更新版本。[呼叫成為 MCP 任務的條件](#requirements-for-mcp-tasks)列出了可使用它們的工作階段與伺服器。

#### 停止 MCP 任務或取得其結果

若要停止執行中的任務，請在 [`/tasks`](https://code.claude.com/docs/zh-TW/commands#all-commands) 中選取它並按下 `x`，或請 Claude 停止它。Claude Code 會停止追蹤該任務並要求伺服器取消它，但伺服器仍可能完成它。請先從 `/mcp` 重新連線已中斷連線的伺服器，否則不會送出取消請求，且 Claude Code 會遺忘該任務而無法再次追蹤它。按下 `Esc` 不會停止背景任務。

任務結束時，逐字稿中會出現如下的一行：

```text theme={null}
MCP task <server task id> (<server>/<tool>) completed.
```

結果會傳給 Claude，而不是寫入逐字稿，因此請向 Claude 詢問結果。若結果送達時 Claude 處於閒置狀態，Claude 會主動開始處理它。

#### 回答來自 MCP 任務的問題

執行中的任務可以開啟[引導對話框](#respond-to-mcp-elicitation-requests)來要求您輸入。當 `/tasks` 開啟時，對話框會保持隱藏，因此請關閉 `/tasks` 以作答。拒絕或按下 `Esc` 也是對伺服器的一種回答，伺服器隨後會決定任務是否繼續。

在[非互動](https://code.claude.com/docs/zh-TW/headless.md)工作階段中，Claude Code 會要求伺服器取消要求輸入的任務，而不會執行您的 [`Elicitation` hook](https://code.claude.com/docs/zh-TW/hooks#elicitation) 或呼叫 Agent SDK 的 `onElicitation` 回呼。

#### 在 MCP 任務執行期間結束、清除或恢復

遠端伺服器上的任務在您結束後仍會繼續執行。stdio 伺服器的程序會在 Claude Code 結束時停止，儘管其任務在 `/tasks` 中顯示 `runs on the server; survives exiting this session`。除非該伺服器的文件表示工作會在程序結束後延續，否則請先讓這些任務完成，或在 `/tasks` 中停止它們。

| 情況 | 任務會發生什麼事 | 您可以做什麼 |
| - | - | - |
| 您執行 `/clear` 或 `/branch`，或 `/resume` 另一個工作階段 | 只要 Claude Code 保持開啟，結果就會送達您目前的對話 | 結束之後，使用 `claude --resume` 恢復任務開始時所在的工作階段 |
| 您結束 Claude Code | 沒有任何結束選項會取消遠端伺服器的任務，即使結束對話框將其列在 `The following will stop when you exit:` 之下 | 先在 `/tasks` 中停止它，或稍後恢復同一個工作階段 |
| 您以互動方式回到任務的工作階段：`claude --resume`、`claude --continue` 或 `/resume` | 伺服器連線後，Claude Code 會再次追蹤該任務；若任務在此期間已完成且伺服器仍知道它，Claude 會取得結果 | 保持伺服器的名稱和連線設定不變 |
| 您在單次 `claude -p "<prompt>"` 執行中使用 `--resume` 或 `--continue` 恢復任務的工作階段 | 該執行不會追蹤該任務 | 以互動方式恢復，或使用 `--input-format stream-json` 恢復 |
| 您開始新的工作階段或使用 `--fork-session` | 新的工作階段不會追蹤該任務 | 恢復啟動該任務的工作階段 |

#### 呼叫成為 MCP 任務的條件

只有在以下所有條件都成立時，工具呼叫才會成為 MCP 任務：

* 伺服器支援任務
* 伺服器是以[協定修訂版 2026-07-28](#mcp-client-runtimes) 連線的 HTTP、stdio 或 claude.ai 連接器伺服器。設定 [`MCP_SDK_GENERATION=v1` 或 `MCP_PROTOCOL_NEGOTIATION=legacy`](https://code.claude.com/docs/zh-TW/env-vars) 會排除此情況
* 工作階段會[擷取功能旗標](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)，因此不能在 Amazon Bedrock 等第三方供應商上，也不能關閉遙測或旗標擷取
* Anthropic 已為您這類工作階段開啟 MCP 任務。在 v2.1.304 或更新版本上，這涵蓋終端機 CLI 工作階段、[Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 工作階段和 [GitHub Actions](https://code.claude.com/docs/zh-TW/github-actions.md) 執行。其他使用介面，例如 [VS Code 擴充功能](https://code.claude.com/docs/zh-TW/vs-code.md)和[桌面應用程式](https://code.claude.com/docs/zh-TW/desktop.md)，沒有 MCP 任務
* 呼叫來自主要對話，而非來自 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md)
* 工作階段是互動式的，或者 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 工作階段或讀取 `--input-format stream-json` 的 `claude -p` 執行具備：
  * [`CLAUDE_AUTO_BACKGROUND_TASKS`](https://code.claude.com/docs/zh-TW/env-vars) 為 `1`
  * `CLAUDE_CODE_DISABLE_MCP_TASK_BACKGROUND` 不為 `1`
  * `CLAUDE_CODE_MCP_AUTO_BACKGROUND_MS` 不為 `0`

其他任何呼叫都是一般的工具呼叫，而[長時間工具呼叫的自動背景化](#automatic-backgrounding-of-long-tool-calls)說明了其中哪些會移至背景。

請保持 Agent SDK 或 stream-json 工作階段的輸入開啟，因為輸入關閉後，執行[不會等待 MCP 任務](https://code.claude.com/docs/zh-TW/headless.md#mcp-work-when-a-non-interactive-run-ends)。單次 `claude -p "<prompt>"` 執行不會取得 MCP 任務。

#### MCP 任務上的狀態訊息

這些訊息出現在任務的 `/tasks` 項目或其結束的逐字稿行中，表示 Claude Code 無法連繫到伺服器或任務。當其中一則顯示在 `/tasks` 中時，該工作可能仍在執行：Claude Code 不會干預它，並持續檢查。`300s` 和設定相關的訊息即使在恢復聯繫後仍會保留在項目上。

| 訊息 | 發生了什麼事 | 您可以做什麼 |
| - | - | - |
| `reconnecting…` | 恢復後伺服器尚未回應，或狀態檢查沒有得到回應 | 若持續顯示，請從 `/mcp` 重新連線 |
| `needs a sign-in to <server>` | 伺服器拒絕了狀態檢查 | 從 `/mcp` 登入 |
| `status requests come back with errors; retrying…` | 伺服器或其前方的代理伺服器以錯誤回應狀態檢查 | 在 Claude Code 重試時等待 |
| `server '<name>' did not reconnect within 300s` | 五分鐘內沒有任何得到回應的檢查，例如連線中斷或伺服器已停用 | 從 `/mcp` 重新連線 |
| `server '<name>' asked for a sign-in, and none was accepted within 300s` | 五分鐘後伺服器仍要求登入 | 從 `/mcp` 登入 |
| `status requests to server '<name>' came back with errors, and none succeeded in 300s` | 五分鐘內都是錯誤回應 | 檢查伺服器本身的健康狀態或日誌 |
| `server '<name>' is not configured in this session; the task may still be running on it` | 工作階段中沒有該名稱的伺服器，例如它已被移除、重新命名或未包含在 `--mcp-config` 中，或 claude.ai 連接器仍在載入 | 以相同名稱還原該伺服器，然後再次恢復工作階段。若是載入中的連接器，則無需任何操作：連接器出現後，Claude Code 就會追蹤該任務 |
| 以 `server '<name>' was reconfigured to a different transport since this task was created` 開頭的訊息 | 存在該名稱的伺服器，但其連線設定自任務開始後已變更，例如其 URL、command、args、env、headers 或 timeout | 還原先前的設定，然後再次恢復工作階段 |
| `the server rejected this task's id; asking again…` | 伺服器表示它不認識該任務 ID。Claude Code 會持續詢問最多五分鐘 | 等待：若伺服器再次識別該 ID，訊息就會清除，否則接著會出現 `outcome unknown.` 行 |
| 以 `outcome unknown.` 結尾的逐字稿行，其中一種形式為 `expired on the server: outcome unknown.` | 伺服器拒絕了該 ID 或以其他永久性錯誤拒絕，且 Claude Code 已停止追蹤該任務 | 第二次呼叫可能會重複該工作。再次呼叫該工具之前，請向伺服器確認已完成的內容，例如請 Claude 使用該伺服器的其他工具 |

#### MCP 任務的時間限制

預設情況下，背景中的任務沒有 Claude Code 時間限制。[工具呼叫時間限制](#time-limits-on-mcp-tool-calls)（包括實際時間限制和閒置逾時）在伺服器以任務回應該呼叫之前適用。若您[讓 Claude 等待](#make-claude-wait-for-the-result-of-an-mcp-task)，這些限制會在整個任務期間適用。得到回應的狀態檢查會計為閒置逾時的活動。

#### 讓 Claude 等待 MCP 任務的結果

若要讓 Claude 在互動式工作階段中等待任務的結果，請設定以下兩個環境變數之一，例如在 [`settings.json`](https://code.claude.com/docs/zh-TW/settings) 的 `env` 區塊中：

* **[`CLAUDE_CODE_MCP_AUTO_BACKGROUND_MS`](https://code.claude.com/docs/zh-TW/env-vars) 設為 `0`**：Claude 會等待每個 MCP 工具呼叫直到呼叫結束
* **[`CLAUDE_CODE_DISABLE_MCP_TASK_BACKGROUND`](https://code.claude.com/docs/zh-TW/env-vars) 設為 `1`**：Claude 會等待任務的結果。當[自動背景化](#automatic-backgrounding-of-long-tool-calls)開啟時，它預設會在兩分鐘後移動該呼叫，因此短任務會就地完成，長任務則不會阻擋您。被移動的呼叫是一般的背景呼叫，而非 MCP 任務。它不會在結束工作階段後延續

在 Claude 等待期間，按下 `Esc` 或達到[實際時間限制或閒置逾時](#time-limits-on-mcp-tasks)都會結束該呼叫，且 Claude Code 會要求伺服器取消該任務。

若您將 `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS` 設為 `1` 或以 [bare 模式](https://code.claude.com/docs/zh-TW/headless.md#start-faster-with-bare-mode)啟動，僅此並不會讓 Claude 等待 MCP 任務。此範例將 `CLAUDE_CODE_MCP_AUTO_BACKGROUND_MS` 設為 `0`，因此 Claude 會等待每個 MCP 工具呼叫：

```json settings.json theme={null}
{
  "env": {
    "CLAUDE_CODE_MCP_AUTO_BACKGROUND_MS": "0"
  }
}
```

### 供伺服器作者參考的 MCP 任務

若您建置 MCP 伺服器，可以用任務來回應長時間執行的 `tools/call`。[MCP tasks 擴充功能](https://modelcontextprotocol.io/extensions/tasks/overview)定義了您要傳送的訊息。在[協定修訂版 2026-07-28](#mcp-client-runtimes) 連線上，每個請求都會在 `params._meta["io.modelcontextprotocol/clientCapabilities"]` 攜帶 Claude Code 的用戶端能力，並在 `extensions` 下包含 `"io.modelcontextprotocol/tasks": {}`。[無法成為任務](#requirements-for-mcp-tasks)的 `tools/call` 請求會省略該擴充功能。

#### 以任務回應呼叫

只有在請求攜帶該擴充功能時才以任務回應，否則 Claude 會收到工具錯誤 `Unsupported result type 'task' for tools/call`。當缺少 `taskId`、`status`、`createdAt`、`lastUpdatedAt` 或 `ttlMs` 時，Claude 也會收到相同的錯誤。任務物件是您 `tools/call` 回應的 JSON-RPC `result`，不需要 `content` 陣列，此處包含了選用的 `statusMessage` 和 `pollIntervalMs`：

```json theme={null}
{
  "resultType": "task",
  "taskId": "build-7f3a9c2e",
  "status": "working",
  "statusMessage": "Compiling, 40 of 212 files done",
  "createdAt": "2026-10-22T14:03:07Z",
  "lastUpdatedAt": "2026-10-22T14:03:07Z",
  "ttlMs": null,
  "pollIntervalMs": 5000
}
```

| 欄位 | Claude Code 如何處理 |
| - | - |
| `resultType` | 設為 `"task"` 以將回覆標示為任務。若沒有此欄位，Claude Code 會將回覆讀取為一般結果 |
| `taskId` | 必要。最多 128 個可列印的 ASCII 字元且不含空格，否則 Claude 會收到以 `MCP server "<name>" returned a malformed task handle for tool "<tool>"` 開頭的工具錯誤。請讓該 ID 在不同連線間都能被回應，因為恢復後 Claude Code 會在新的連線上詢問它 |
| `status` | 必要。為 `working`、`input_required`、`completed`、`failed` 或 `cancelled` 之一。其他值會產生 `Unsupported result type` 錯誤 |
| `createdAt`、`lastUpdatedAt`、`ttlMs` | 必要，且 `ttlMs` 可以是 `null`。Claude Code 不會因為任務的 `ttlMs` 已過而捨棄該任務 |
| `pollIntervalMs` | 選用，但不可為 `null`。`tasks/get` 請求之間的毫秒數，會被限制在 250 到 30000 之間。若缺少此欄位，Claude Code 會使用 2000，並從每個 `tasks/get` 回應中重新讀取該值 |
| `statusMessage` | 選用。`/tasks` 會顯示您最新 `tasks/get` 回應中的值，而非這第一個回應中的值，且省略此欄位的回應會將其清除。[Claude Code 的狀態訊息](#status-messages-on-an-mcp-task)可能會取代它 |

在 HTTP 或 claude.ai 連接器伺服器上，任務回應必須在[每個請求的計時器](#time-limits-on-mcp-tool-calls)內開始，因此請先接受工作並回應，然後再執行工作。

#### 回報狀態、結果與問題

在任務回應之後，Claude Code 會立即傳送帶有 `{ "taskId": ... }` 的 `tasks/get`，然後每個輪詢間隔重複一次。tasks 擴充功能要求您的回應攜帶 `"resultType": "complete"`，以及 `taskId`、`status`、`createdAt`、`lastUpdatedAt` 和 `ttlMs`。`ttlMs` 可以是 `null`，而 `statusMessage` 和 `pollIntervalMs` 為選用。此範例回報建置已完成：

```json theme={null}
{
  "resultType": "complete",
  "taskId": "build-7f3a9c2e",
  "status": "completed",
  "createdAt": "2026-10-22T14:03:07Z",
  "lastUpdatedAt": "2026-10-22T14:09:41Z",
  "ttlMs": null,
  "result": {
    "content": [{ "type": "text", "text": "Build succeeded: 212 files, 0 warnings" }]
  }
}
```

| 狀態、方法或回應 | Claude Code 如何處理 |
| - | - |
| `working` | 持續輪詢 |
| `completed` | 將頂層 `result` 物件中的一般 `tools/call` 結果提供給 Claude。其中的 `isError: true` 會回報為失敗 |
| `failed` | 將頂層 `error` 物件 `{ code, message, data }` 的 `message` 告知 Claude，tasks 擴充功能要求失敗的任務必須包含此物件。若沒有該 `message`，Claude 會改為收到 `statusMessage`，否則為 `Task failed` |
| `cancelled` | 將 `statusMessage` 告知 Claude，否則為 `Task was cancelled by the server` |
| `input_required` | 讀取 `inputRequests`，這是一個將您選擇的鍵對應至 `{ method, params }` 的物件。Claude Code 會透過帶有 `{ taskId, inputResponses }` 的 `tasks/update` 對每個鍵回答一次，其中 `inputResponses` 會將相同的鍵對應至該請求的結果。每個任務超過 16 個的鍵會被忽略 |
| `inputRequests` 中的方法 | `elicitation/create` 只在互動式終端機工作階段中提供服務，`roots/list` 則在所有地方都提供。當 Claude Code 無法處理某個請求時，它會要求伺服器取消該任務 |
| 其他 `status` 值 | Claude Code 會要求伺服器取消該任務，並向 Claude 回報為失敗 |
| JSON-RPC 錯誤 `-32602` | 讀取為未知的任務 ID。對於背景中的任務，Claude Code 會持續詢問最多五分鐘，然後向 Claude 回報結果未知 |
| `tasks/cancel` | 例如當 Claude 或使用者在伺服器連線期間停止任務時傳送。結束時不會傳送 |
| `tasks/result`、`tasks/list`、`notifications/tasks` | 不會使用，因此請將結果放在您的 `tasks/get` 回應中 |

### 外掛提供的 MCP 伺服器

[外掛](https://code.claude.com/docs/zh-TW/plugins/overview.md)可以捆綁 MCP 伺服器，在您啟用外掛時提供工具與整合功能。

**外掛 MCP 伺服器的運作方式**：

* 外掛在外掛根目錄的 `.mcp.json` 中定義 MCP 伺服器，或內嵌於 `plugin.json` 中
* 當您啟用外掛時，Claude Code 會自動啟動其 MCP 伺服器
* Claude Code 會將外掛 MCP 工具與手動設定的 MCP 工具一併提供
* 外掛伺服器的新增與移除是透過安裝或解除安裝外掛來完成，而非使用 `/mcp` 命令。您仍可在 `/mcp` 中[將已安裝的外掛伺服器切換為關閉](#disable-a-server-without-removing-it)，這會讓 Claude Code 停止連線至該伺服器，而不會移除外掛

**外掛 MCP 設定範例**：

在外掛根目錄的 `.mcp.json` 中：

```json theme={null}
{
  "mcpServers": {
    "database-tools": {
      "command": "${CLAUDE_PLUGIN_ROOT}/servers/db-server",
      "args": ["--config", "${CLAUDE_PLUGIN_ROOT}/config.json"],
      "env": {
        "DB_URL": "${DB_URL}"
      }
    }
  }
}
```

或內嵌於 `plugin.json` 中：

```json theme={null}
{
  "name": "my-plugin",
  "mcpServers": {
    "plugin-api": {
      "command": "${CLAUDE_PLUGIN_ROOT}/servers/api-server",
      "args": ["--port", "8080"]
    }
  }
}
```

**外掛 MCP 功能**：

* **自動生命週期**：伺服器會在以下時間點連線與中斷連線：
  * 在工作階段啟動時，Claude Code 會自動連線已啟用外掛的伺服器。在 `/mcp` 中，您先前使用過的遠端（HTTP 或 SSE）外掛伺服器可能會改為顯示 [`cached` 狀態](#server-status-detail)；Claude Code 會在 Claude 首次呼叫其中一個工具時連線該伺服器。當 stdio 外掛伺服器的連線在不到 15 分鐘前失敗時，Claude Code 會[略過該連線](https://code.claude.com/docs/zh-TW/errors.md#skipping-connection-recent-failure-cached)
  * 如果您在工作階段期間啟用或停用外掛，Claude Code 會在變更套用時連線或中斷其 MCP 伺服器。[無需重新啟動即可套用外掛變更](https://code.claude.com/docs/zh-TW/plugins/cli-reference.md#reload-plugins)說明了套用的時機。在沒有互動式終端機的工作階段中，`/reload-plugins` 不會連線或中斷外掛 MCP 伺服器；這些變更會在您的下一個工作階段生效
  * 當您重新載入時，Claude Code 會保留設定未變更之外掛伺服器的現有連線；當您從 Agent SDK [取代工作階段的 MCP 伺服器清單](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md#mcpsetserversresult)而未指名這些伺服器時，也會如此處理
  * 當您在 v2.1.246 或更新版本中[使用 `/cd` 移動工作階段](https://code.claude.com/docs/zh-TW/permissions#move-the-session-to-another-directory)時，Claude Code 會連線新目錄設定所啟用之外掛的伺服器，並中斷不再啟用之外掛的伺服器，因此移動後您不需要執行 `/reload-plugins`
  * 在[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)中，對尚未連線之外掛伺服器的 MCP 呼叫（例如在閒置的工作階段剛喚醒後）會依需求啟動該伺服器，並等待其連線
* **路徑預留位置**：`${CLAUDE_PLUGIN_ROOT}` 會解析為外掛的安裝目錄，`${CLAUDE_PLUGIN_DATA}` 會解析為其[持久狀態](https://code.claude.com/docs/zh-TW/plugins/components.md#path-variables-and-persistent-data)目錄，而 `${CLAUDE_PROJECT_DIR}` 會解析為穩定的專案根目錄。替換適用於：
  * `stdio` 伺服器：`command`、`args`、`env`
  * `http`、`sse` 和 `ws` 伺服器：`url`、`headers` 和 `headersHelper`
* **使用者環境存取**：可存取與手動設定之伺服器相同的環境變數
* **多種傳輸類型**：支援 stdio、SSE、HTTP 和 WebSocket 傳輸，但傳輸支援可能因伺服器而異

外掛伺服器會顯示在 `/mcp` 中，並附有表示其來自外掛的標示。

`claude mcp get` 會隱藏為外掛之 stdio 或 WebSocket 伺服器設定的值，因為這些值可能包含憑證：

* **stdio 伺服器**：會輸出 `Command: stdio`、一行空白的 `Args:`，並將每個環境變數輸出為 `NAME=[REDACTED]`
* **WebSocket 伺服器**：會輸出 `URL: ws`，並將每個標頭輸出為 `<name>: [REDACTED]`，而 `claude mcp list` 會以 `ws` 取代 URL 顯示

若要查看外掛設定的內容，請[在磁碟上找到該外掛](https://code.claude.com/docs/zh-TW/plugins/loading.md#find-plugins-on-disk)，並閱讀其 `.mcp.json` 或 `plugin.json`。

**外掛 MCP 工具名稱**：

來自外掛捆綁之 MCP 伺服器的工具，其可呼叫名稱同時包含外掛名稱與伺服器鍵。完整形式為 `mcp__plugin_<plugin-name>_<server-name>__<tool-name>`，其中 `A-Z`、`a-z`、`0-9`、`_` 和 `-` 以外的任何字元都會被替換為 `_`。以名為 `my-plugin` 之外掛中捆綁的 `database-tools` 伺服器為例，`query` 工具的呼叫名稱為：

```
mcp__plugin_my-plugin_database-tools__query
```

在[權限規則](https://code.claude.com/docs/zh-TW/permissions.md)、skill 的 `allowed-tools` 清單、[subagent 的 `tools` 欄位](https://code.claude.com/docs/zh-TW/sub-agents#available-tools)或 [hook matcher](https://code.claude.com/docs/zh-TW/hooks.md#match-mcp-tools) 中參照該工具時，請使用此完整名稱。針對單純伺服器鍵撰寫的 hook matcher（例如 `mcp__database-tools__.*`）永遠不會對外掛捆綁的伺服器觸發。

伺服器本身會以範圍名稱 `plugin:<plugin-name>:<server-name>` 註冊，例如 `plugin:my-plugin:database-tools`。在需要已設定之伺服器名稱的地方請使用該名稱，例如 [`mcp_tool` hook 的 `server` 欄位](https://code.claude.com/docs/zh-TW/hooks#mcp-tool-hook-fields)。

如需在外掛中捆綁 MCP 伺服器的詳細資訊，請參閱[外掛元件參考](https://code.claude.com/docs/zh-TW/plugins/components.md#mcp-servers)。

## MCP 安裝範圍

MCP 伺服器可以在三種範圍中設定。您選擇的範圍決定伺服器會在哪些專案中載入，以及該設定是否與團隊共享。管理員也可以透過[受管設定](#managed-mcp-configuration)為每位使用者部署或提供伺服器。

| 範圍 | 載入於 | 與團隊共享 | 儲存位置 |
| - | - | - | - |
| [Local](#local-scope) | 僅目前專案 | 否 | `~/.claude.json` |
| [Project](#project-scope) | 僅目前專案 | 是，透過版本控制 | 專案根目錄中的 `.mcp.json` |
| [User](#user-scope) | 您的所有專案 | 否 | `~/.claude.json` |

### Local 範圍

Local 範圍是預設值。Local 範圍的伺服器只會在您新增它的專案中載入，且僅限您私人使用。Claude Code 會將其儲存在 `~/.claude.json` 中該專案路徑之下，因此同一個伺服器不會出現在您的其他專案中。請將 local 範圍用於個人開發伺服器、實驗性設定，或含有您不希望放入版本控制之憑證的伺服器。

> [!NOTE]
>
> MCP 伺服器的「local 範圍」一詞與一般的本機設定不同。MCP local 範圍的伺服器儲存在 `~/.claude.json`（您的家目錄）中，而一般的本機設定則使用 `.claude/settings.local.json`（位於專案目錄中）。如需設定檔位置的詳細資訊，請參閱[設定](https://code.claude.com/docs/zh-TW/settings.md#where-settings-live)。

```bash theme={null}
# Add a local-scoped server (default)
claude mcp add --transport http stripe https://mcp.stripe.com

# Explicitly specify local scope
claude mcp add --transport http stripe --scope local https://mcp.stripe.com
```

此命令會將伺服器寫入 `~/.claude.json` 中您目前專案的項目。以下範例顯示從 `/path/to/your/project` 執行時的結果：

```json theme={null}
{
  "projects": {
    "/path/to/your/project": {
      "mcpServers": {
        "stripe": {
          "type": "http",
          "url": "https://mcp.stripe.com"
        }
      }
    }
  }
}
```

### Project 範圍

Project 範圍的伺服器會將設定儲存在專案根目錄的 `.mcp.json` 檔案中，以實現團隊協作。當您新增 project 範圍的伺服器時，Claude Code 會自動建立或更新此檔案，並套用適當的設定結構。請將 `.mcp.json` 提交至版本控制，讓團隊中的每個人都能取得相同的 MCP 工具與服務。

```bash theme={null}
# Add a project-scoped server
claude mcp add --transport http shared-server --scope project https://example.com/mcp
```

產生的 `.mcp.json` 檔案遵循標準化格式：

```json theme={null}
{
  "mcpServers": {
    "shared-server": {
      "type": "http",
      "url": "https://example.com/mcp"
    }
  }
}
```

基於安全考量，Claude Code 在互動式工作階段中使用 `.mcp.json` 檔案中的 project 範圍伺服器之前，會提示您核准。若要重設這些核准選擇，請執行 `claude mcp reset-project-choices`。

在 `claude -p` 執行、[Agent SDK](https://code.claude.com/docs/zh-TW/headless.md) 工作階段，以及位於[專案](https://code.claude.com/docs/zh-TW/claude-projects.md#what-threads-pick-up-from-your-repositories)討論串之外的[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)中，Claude Code 無法顯示該提示：它會直接載入 project 範圍的伺服器而不詢問。若您在使用者設定或受管設定中設定了 [`skipDangerousModePermissionPrompt`](https://code.claude.com/docs/zh-TW/settings-reference#skipdangerousmodepermissionprompt)，並以 `bypassPermissions` 模式啟動工作階段，Claude Code 也會略過該提示。若仍要排除某個伺服器：

* 將其加入 [`disabledMcpjsonServers`](https://code.claude.com/docs/zh-TW/settings-reference#disabledmcpjsonservers)，這會在每種權限模式中封鎖它。
* 使用 [`--setting-sources`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 或 SDK 的 `settingSources` 選項完全排除專案設定。
* 使用 [`--strict-mcp-config`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 啟動工作階段。Claude Code 隨後只會使用您透過 `--mcp-config` 傳入的 MCP 伺服器。對於 Claude Code 未載入的 project 範圍伺服器略過核准提示，需要 Claude Code v2.1.246 或更新版本；在 v2.1.246 之前，strict 工作階段仍會等待這些伺服器的核准，導致背景工作階段在啟動時停滯等待。如需此旗標在受管 MCP 檔案下的作用，請參閱[使用 managed-mcp.json 進行獨佔控制](https://code.claude.com/docs/zh-TW/managed-mcp.md#exclusive-control-with-managed-mcp-json)。

[Project 伺服器核准與工作區信任](#project-server-approvals-and-workspace-trust)說明提交至儲存庫的核准如何與工作區信任互動。

### User 範圍

User 範圍的伺服器儲存在 `~/.claude.json` 中，提供跨專案的存取能力，使其可在您電腦上的所有專案中使用，同時僅限您的使用者帳戶私人使用。此範圍適用於個人工具伺服器、開發工具，或您在不同專案中經常使用的服務。

```bash theme={null}
# Add a user server
claude mcp add --transport http hubspot --scope user https://mcp.hubspot.com/anthropic
```

### 範圍階層與優先順序

當同一個伺服器在多個位置中定義時，Claude Code 只會連線一次，並使用優先順序最高之來源的定義。系統會使用該來源的完整伺服器項目；欄位不會跨範圍合併。

1. Local 範圍
2. Project 範圍
3. User 範圍
4. [外掛提供的伺服器](https://code.claude.com/docs/zh-TW/plugins/components.md#mcp-servers)
5. [claude.ai 連接器](#use-mcp-servers-from-claude-ai)

Claude Code 依名稱比對三種範圍之間的重複項目。外掛與連接器則依端點比對，因此若其指向的 URL 或命令與上方某個已啟用伺服器相同，即視為重複。

當兩種 URL 寫法的差異僅在於通訊協定（scheme）或主機名稱的大小寫、通訊協定的預設連接埠（例如 `https` 上的 `:443`），或結尾斜線時，它們會被視為同一個端點。若路徑、查詢字串、userinfo 或非預設連接埠不同，則視為兩個伺服器。

您的組織透過 [`managedMcpServers`](https://code.claude.com/docs/zh-TW/managed-mcp#provide-servers-through-managed-settings) 受管設定提供的伺服器，其優先順序高於上述所有來源，因此當其中任一來源與之重複時，Claude Code 會連線至組織的定義。需要 Claude Code v2.1.259 或更新版本。

若您在 [Desktop 應用程式的 Code 分頁](https://code.claude.com/docs/zh-TW/desktop.md#mcp-servers-from-the-claude-desktop-chat-app)中開啟本機工作階段，且 `~/.claude.json` 的最上層（user 範圍）與 `.mcp.json` 中有相同名稱的 stdio 伺服器，Code 分頁會使用 `~/.claude.json` 的定義。

### `.mcp.json` 中的環境變數展開

Claude Code 支援在 `.mcp.json` 檔案中展開環境變數，讓團隊能夠共享設定，同時保有針對特定機器路徑與 API 金鑰等敏感值的彈性。

您可以在伺服器的 `command`、`args`、`env`、`url` 或 `headers` 值中參照環境變數，形式有以下兩種：

* `${VAR}`：展開為環境變數 `VAR` 的值
* `${VAR:-default}`：若已設定 `VAR`，則展開為 `VAR` 的值；若未設定，則展開為 `default`

#### 變數展開範例

在此伺服器項目中，URL 為 `API_BASE_URL` 的值後接 `/mcp`，並以 `https://api.example.com` 作為預設值，而 API 金鑰則來自 `API_KEY`：

```json theme={null}
{
  "mcpServers": {
    "api-server": {
      "type": "http",
      "url": "${API_BASE_URL:-https://api.example.com}/mcp",
      "headers": {
        "Authorization": "Bearer ${API_KEY}"
      }
    }
  }
}
```

#### 未設定且沒有預設值的變數

若參照的環境變數未設定且沒有預設值，設定仍會載入：Claude Code 會在 `claude mcp list` 輸出中針對該伺服器回報缺少變數的警告，並直接使用未展開的 `${VAR}` 文字。請設定該變數或加入 `:-default` 備援值，讓伺服器以您預期的值啟動。在遠端伺服器的 `url` 與 `headers` 中，某些憑證變數則會[讀取為空值](#credential-variables-that-read-as-empty)，且不會有警告。

#### 設定為空字串的變數

若您將變數設定為空字串，該變數會被視為已設定，因此 `${VAR:-default}` 參照會展開為空字串，而非 `default`。以[範例伺服器](#example-with-variable-expansion)為例，若您將 `API_BASE_URL` 設定為空字串，其 `url` 會變成 `/mcp`，而 `claude mcp list` 會回報 `'url' is not a valid URL`。若要使用預設值，請取消設定該變數，而非將其設定為空字串。

#### 讀取為空值的憑證變數

在遠端伺服器的 `url` 與 `headers` 中，Claude Code 會將環境中的憑證變數讀取為空值，而不會展開它們。這可防止專案的 `.mcp.json` 或外掛將您的 Claude Code 或雲端供應商憑證傳送至其指定的伺服器。若您寫入 `Bearer ${ANTHROPIC_AUTH_TOKEN}`，伺服器會收到不含憑證的 `Bearer `，並拒絕該請求，通常會回傳 `401`。Claude Code 會將其回報為連線失敗。

涵蓋的名稱包括：

* Claude Code 本身的憑證，例如 `ANTHROPIC_API_KEY` 與 `ANTHROPIC_AUTH_TOKEN`
* 您雲端供應商的憑證，例如 `AWS_BEARER_TOKEN_BEDROCK`
* 您環境中攜帶的其他憑證，例如 `HTTPS_PROXY` 與 `NPM_TOKEN`

無論您是否已設定該變數，涵蓋的名稱都會讀取為空值，且其上的 `:-default` 備援值會被忽略。供應商基礎 URL（例如 `ANTHROPIC_BASE_URL`）仍會展開，因此 `"url": "${ANTHROPIC_BASE_URL}/mcp"` 可正常運作，除非該 URL 的值本身嵌入了憑證，例如使用者名稱與密碼。

不在此集合中的名稱（例如 `API_KEY`）會依原樣展開。若要將其中一項涵蓋的憑證提供給伺服器，請將其複製到您自行命名的變數中，並改為參照該名稱。

當遠端伺服器的 `url` 或 `headers` 參照了您已設定的涵蓋變數時，Claude Code 會在一行除錯日誌中列出其名稱。若要查看該行，請執行 `claude --debug-file /tmp/claude-debug.log`，並在該檔案中搜尋 `never expanded toward a remote server`。

#### 參照在 `/mcp` 與 CLI 輸出中的顯示方式

對於位於 local、project 或 user [範圍](#mcp-installation-scopes)的伺服器，以下使用介面會以名稱顯示 `${VAR}` 參照，而非其解析後的值：

* 伺服器 `/mcp` 詳細資訊檢視中的 URL 或命令列
* `claude mcp list` 與 `claude mcp get` 輸出

`/mcp` 詳細資訊檢視在 Claude Code v2.1.268 或更新版本中會以此方式顯示參照。

對於您的組織透過 `managedMcpServers` 設定提供的伺服器，這些使用介面只會顯示 [URL 的主機名稱](https://code.claude.com/docs/zh-TW/managed-mcp.md#what-users-can-see-and-change)。

若要查看連線失敗時 `claude mcp list`、`claude mcp get` 與 `/mcp` 顯示的內容，請參閱[伺服器狀態詳細資訊](#server-status-detail)。

## 實用範例

### 範例：連接到 GitHub 進行程式碼審查

GitHub 的遠端 MCP server 使用作為標頭傳遞的 GitHub 個人存取 token 進行驗證。若要取得一個，請開啟您的 [GitHub token 設定](https://github.com/settings/personal-access-tokens)，產生一個新的細粒度 token，具有對您希望 Claude 使用的儲存庫的存取權，然後新增 server：

```bash theme={null}
claude mcp add --transport http github https://api.githubcopilot.com/mcp/ \
  --header "Authorization: Bearer YOUR_GITHUB_PAT"
```

將 `YOUR_GITHUB_PAT` 替換為您的個人存取 token。`claude mcp add` 命令會儲存設定而不驗證憑證，因此此處接受預留位置值，但伺服器稍後會無法連接。若要驗證連接，請執行 `/mcp` 並檢查該伺服器的列是否顯示核取記號。具有錯誤憑證的伺服器則會顯示 ✘，其[失敗詳細資訊](#server-status-detail)包括伺服器傳回的 HTTP 狀態，例如 401。

然後使用 GitHub：

```text wrap theme={null}
審查 PR #456 並建議改進
```

```text wrap theme={null}
為我們剛發現的錯誤建立新問題
```

```text wrap theme={null}
顯示所有指派給我的開放 PRs
```

### 範例：查詢您的 PostgreSQL 資料庫

[DBHub](https://github.com/bytebase/dbhub)，`@bytebase/dbhub` 套件，是一個 MCP server，可將 Claude 連接到您在 `--dsn` 中傳遞的連接字串的關聯式資料庫。在連接字串中使用唯讀資料庫使用者，以便 Claude 執行的查詢無法修改資料：

```bash theme={null}
claude mcp add --transport stdio db -- npx -y @bytebase/dbhub \
  --dsn "postgresql://readonly:pass@prod.db.com:5432/analytics"
```

若要確認伺服器已啟動，請執行 `/mcp` 並檢查 `db` 列是否顯示核取記號。

然後自然地查詢您的資料庫：

```text wrap theme={null}
本月我們的總收入是多少？
```

```text wrap theme={null}
顯示 orders 表的 schema
```

```text wrap theme={null}
找到 90 天內未進行購買的客戶
```

## 使用遠端 MCP 伺服器進行身分驗證

許多雲端 MCP 伺服器需要身分驗證。Claude Code 支援 OAuth 2.0 以進行安全連線。

當伺服器回應 `401 Unauthorized` 或 `403 Forbidden` 時，Claude Code 會將遠端伺服器標記為需要身分驗證。Claude Code 顯示的內容取決於伺服器：

* 對於您尚未登入的伺服器，任一狀態碼都會在 `/mcp` 中標記它，以便您完成 OAuth 流程。
* 對於 [claude.ai 連接器](#use-mcp-servers-from-claude-ai)，由 claude.ai 拒絕您的工作階段 token 導致的 `401` 不會標記連接器，因為重新授權連接器無法修復您的登入。Claude Code 改為顯示 [工作階段 token 被拒絕狀態](https://code.claude.com/docs/zh-TW/errors.md#claude-ai-rejected-the-session-token)。
* 對於您在 `headers` 中或透過 [`headersHelper`](#use-dynamic-headers-for-custom-authentication) 設定 `Authorization` 標頭的伺服器，連線時的 `401` 或 `403` 不會標記伺服器，因為要修復的憑證是您設定的憑證。Claude Code 改為報告連線失敗。如果您從 `${VAR}` 參考設定該標頭，請檢查該變數是否是 Claude Code [讀取為空](#credential-variables-that-read-as-empty) 的變數之一。
* 對於 [傳遞到雲端工作階段的連接器](#how-connectors-reach-claude-code)，Claude Code 不會執行登入流程，因為工作階段的代理伺服器使用您在 claude.ai 中授予的授權向連接器進行身分驗證。當那裡的連接器需要再次授權時，請在 [claude.ai/customize/connectors](https://claude.ai/customize/connectors) 重新連接它，而不是從工作階段進行。

當您已登入的 OAuth 伺服器以 `401 Unauthorized` 拒絕您儲存的 token 時，Claude Code 會在使用或不使用新 token 的情況下重新連接：

* **您儲存的登入資訊有重新整理 token**：它會重新整理該 token、重新連接並重試請求一次。只有在該重試也失敗時，伺服器才會在 `/mcp` 中被標記。
* **您儲存的登入資訊沒有重新整理 token**：它會在不使用該 token 的情況下連接一次。如果伺服器有回應，其工具會在您登出狀態下運作，且被拒絕的 token 會被刪除。如果伺服器也拒絕該連線，`/mcp` 會顯示該伺服器需要身分驗證。

在 macOS 上的 `claude -p` 或 Agent SDK 執行中，Claude Code 在無法讀取您儲存的 token 時所傳送的請求，會以 [儲存的憑證錯誤](https://code.claude.com/docs/zh-TW/errors.md#couldnt-read-the-stored-credentials-for-mcp-server) 失敗。

當伺服器拒絕儲存的重新整理 token 時，Claude Code 會立即顯示指向 `/mcp` 的通知。開啟 `/mcp` 並在伺服器上選擇 **Re-authenticate** 以在下一個工具呼叫失敗之前再次登入。

傳回指向其授權伺服器的 `WWW-Authenticate` 標頭的自訂伺服器會獲得與任何其他遠端伺服器相同的自動探索。

當一個或多個已設定的伺服器需要身分驗證時，Claude Code 也會顯示啟動通知，因此您不必開啟 `/mcp` 來探索哪些伺服器需要登入。該通知只計算您可以從 Claude Code 登入的伺服器。在 v2.1.218 之前，它也計算在 claude.ai 中未連接的 [claude.ai 連接器](#use-mcp-servers-from-claude-ai)，您只能從 claude.ai 設定進行連接。

該通知會宣佈每個伺服器一次，並在後續啟動時將其排除在計數之外，直到該伺服器已連接並再次需要登入。`/mcp` 仍會列出每個需要登入的伺服器。

`claude -p` 或 Agent SDK 執行沒有 `/mcp` 面板，因此 Claude Code 無法在其中執行 OAuth 流程。若要使用需要身分驗證的伺服器，請先從互動式工作階段完成登入：在工作階段中執行 `/mcp`，或在您的 shell 中執行 `claude mcp login <name>`。當已設定的伺服器在啟用 [工具搜尋](#scale-with-mcp-tool-search) 的 `claude -p` 或 Agent SDK 執行期間需要身分驗證時，Claude Code 會告訴 Claude 該伺服器的工具在您授權之前無法使用。

如果您為伺服器設定了 `headers.Authorization` 且伺服器拒絕該標頭，Claude Code 會報告連線失敗，而不是回退到 OAuth。檢查 token 對 MCP 端點是否有效，或移除標頭以使用 OAuth 流程。

**1. 新增需要身分驗證的伺服器**

如果您已在 [MCP 快速入門](https://code.claude.com/docs/zh-TW/mcp-quickstart.md#connect-a-server-that-requires-sign-in) 中新增了 `sentry` 伺服器，請跳過此步驟：在相同範圍使用相同伺服器名稱再次執行 `claude mcp add` 會失敗，並顯示 `MCP server sentry already exists in local config`。否則，執行：

```bash theme={null}
claude mcp add --transport http sentry https://mcp.sentry.dev/mcp
```

**2. 在 Claude Code 中使用 /mcp 命令**

在 Claude Code 中，使用命令：

```text wrap theme={null}
/mcp
```

然後按照瀏覽器中的步驟登入。

> [!TIP]
>
> 提示：
>
> * 身分驗證 token 會安全地儲存並自動重新整理
> * 使用 `/mcp` 功能表中的「Clear authentication」撤銷存取權
> * 如果瀏覽器未自動開啟，請複製提供的 URL 並手動開啟
> * 如果瀏覽器重新導向在驗證後因連線錯誤而失敗，請將瀏覽器位址列中的完整回呼 URL 貼到 Claude Code 中出現的 URL 提示中
> * OAuth 身分驗證適用於 HTTP 伺服器

### 從命令列進行身分驗證

`claude mcp login <name>` 命令直接從您的 shell 執行已設定伺服器的 OAuth 流程，因此您不需要在工作階段內開啟 `/mcp` 面板。對於 claude.ai 連接器，請按照 [從您的 shell 再次授權連接器](https://code.claude.com/docs/zh-TW/remote-control.md#authorize-a-connector-again-from-your-shell) 操作。

```bash theme={null}
claude mcp login sentry
```

若要稍後清除儲存的憑證，請執行 `claude mcp logout <name>`。

`claude mcp login` 會偵測何時沒有本機瀏覽器可用（例如在 SSH 工作階段期間或在沒有顯示伺服器的 Linux 上），並列印授權 URL，而不是嘗試開啟瀏覽器。在您的本機機器上開啟 URL，然後將瀏覽器位址列中的完整重新導向 URL 貼回提示。該命令需要互動式終端機進行貼上步驟，因此請使用 `ssh -t` 連接。傳遞 `--no-browser` 以強制 URL 提示，即使偵測到本機瀏覽器。

```bash theme={null}
claude mcp login sentry --no-browser
```

### 使用固定的 OAuth 回呼連接埠

某些 MCP 伺服器需要預先註冊的特定重新導向 URI。根據預設，Claude Code 為 OAuth 回呼選擇隨機可用連接埠。使用 `--callback-port` 固定連接埠，使其符合 `http://localhost:PORT/callback` 形式的預先註冊重新導向 URI。如果在 Claude Code v2.1.229 上登入因重新導向 URI 不符而失敗，請參閱 [使用預先設定的 OAuth 憑證](#use-pre-configured-oauth-credentials) 下的版本說明。

您可以單獨使用 `--callback-port`（使用動態用戶端註冊）或與 `--client-id` 一起使用（使用預先設定的憑證）。

```bash theme={null}
# Fixed callback port with dynamic client registration
claude mcp add --transport http \
  --callback-port 8080 \
  my-server https://mcp.example.com/mcp
```

### 使用預先設定的 OAuth 憑證

某些 MCP 伺服器不支援透過動態用戶端註冊進行自動 OAuth 設定。如果您看到類似「Incompatible auth server: does not support dynamic client registration」的錯誤，伺服器需要預先設定的憑證。Claude Code 也支援使用用戶端 ID 中繼資料文件 (CIMD) 而不是動態用戶端註冊的伺服器，並自動探索這些伺服器。如果自動探索失敗，請先透過伺服器的開發人員入口網站註冊 OAuth 應用程式，然後在新增伺服器時提供憑證。

**1. 使用伺服器註冊 OAuth 應用程式**

透過伺服器的開發人員入口網站建立應用程式，並記下您的用戶端 ID 和用戶端密碼。

如果註冊表單要求重新導向 URI，請選擇任何可用連接埠並輸入 `http://localhost:PORT/callback`（使用該連接埠）。您將在下一步中使用相同的連接埠。

在 v2.1.229 中，Claude Code 改為傳送 `http://127.0.0.1:PORT/callback`，而精確符合已註冊重新導向 URI 的伺服器會因重新導向 URI 不符而拒絕登入。Claude Code v2.1.231 恢復了 `localhost` 形式。若要在 v2.1.229 上復原，請升級 Claude Code，或暫時將 `http://127.0.0.1:PORT/callback` 形式新增到伺服器的已註冊重新導向 URI。

**2. 使用您的憑證新增伺服器**

這些標籤涵蓋兩個命令：`claude mcp add` 將您的用戶端 ID 和回呼連接埠作為旗標，`claude mcp add-json` 在 `oauth` 物件中採用它們。如果您註冊了重新導向 URI，請將回呼連接埠設定為該 URI 中的連接埠。

> [tab] claude mcp add
>
> 使用 `--client-id` 傳遞您應用程式的用戶端 ID。`--client-secret` 旗標會以遮罩輸入提示輸入密碼：
>
> ```bash theme={null}
> claude mcp add --transport http \
>   --client-id your-client-id --client-secret --callback-port 8080 \
>   my-server https://mcp.example.com/mcp
> ```

> [tab] claude mcp add-json
>
> 在 JSON 設定中包含 `oauth` 物件，並將 `--client-secret` 作為單獨的旗標傳遞：
>
> ```bash theme={null}
> claude mcp add-json my-server \
>   '{"type":"http","url":"https://mcp.example.com/mcp","oauth":{"clientId":"your-client-id","callbackPort":8080}}' \
>   --client-secret
> ```

> [tab] claude mcp add-json (僅回呼連接埠)
>
> 若要僅固定回呼連接埠並讓 Claude Code 自動註冊用戶端，請單獨設定 `callbackPort`：
>
> ```bash theme={null}
> claude mcp add-json my-server \
>   '{"type":"http","url":"https://mcp.example.com/mcp","oauth":{"callbackPort":8080}}'
> ```

> [tab] CI / 環境變數
>
> 透過環境變數設定密碼以跳過互動式提示：
>
> ```bash theme={null}
> MCP_CLIENT_SECRET=your-secret claude mcp add --transport http \
>   --client-id your-client-id --client-secret --callback-port 8080 \
>   my-server https://mcp.example.com/mcp
> ```

**3. 在 Claude Code 中進行身分驗證**

在 Claude Code 中執行 `/mcp` 並按照瀏覽器登入流程。

> [!TIP]
>
> 提示：
>
> * 用戶端密碼安全地儲存在您的系統鑰匙圈 (macOS) 或憑證檔案中，而不是在您的設定中
> * 您只能在新增伺服器時設定用戶端密碼。當您使用 `claude mcp login` 或從 `/mcp` 進行身分驗證時，Claude Code 會使用儲存的密碼，不會提示輸入密碼或讀取 `MCP_CLIENT_SECRET`
> * 若要稍後新增或變更密碼，請使用 `claude mcp remove <name>` 移除伺服器，然後使用 `--client-secret` 和相同的 `--scope` 再次新增它
> * 如果伺服器使用沒有密碼的公開 OAuth 用戶端，請僅使用 `--client-id` 而不使用 `--client-secret`
> * 這些旗標僅適用於 HTTP 和 SSE 傳輸。它們對 stdio 伺服器沒有影響
> * 使用 `claude mcp get <name>` 驗證為伺服器設定了 OAuth 憑證

### 覆寫 OAuth 中繼資料探索

將 Claude Code 指向特定的 OAuth 授權伺服器中繼資料 URL 以繞過預設探索鏈。當 MCP 伺服器的標準端點出錯時，或當您想透過內部代理伺服器路由探索時，設定 `authServerMetadataUrl`。根據預設，Claude Code 首先檢查 `/.well-known/oauth-protected-resource` 的 RFC 9728 受保護資源中繼資料，然後回退到 `/.well-known/oauth-authorization-server` 的 RFC 8414 授權伺服器中繼資料。

在 `.mcp.json` 中您伺服器設定的 `oauth` 物件中設定 `authServerMetadataUrl`：

```json theme={null}
{
  "mcpServers": {
    "my-server": {
      "type": "http",
      "url": "https://mcp.example.com/mcp",
      "oauth": {
        "authServerMetadataUrl": "https://auth.example.com/.well-known/openid-configuration"
      }
    }
  }
}
```

URL 必須使用 `https://`。中繼資料 URL 的 `scopes_supported` 會覆寫上游伺服器公告的範圍。

### 限制 OAuth 範圍

設定 `oauth.scopes` 以固定 Claude Code 在授權流程期間請求的範圍。這是當上游授權伺服器公告的範圍超過您想授予的範圍時，將 MCP 伺服器限制為安全團隊批准的子集的支援方式。該值是單個空格分隔的字串，符合 RFC 6749 §3.3 中的 `scope` 參數格式。

```json theme={null}
{
  "mcpServers": {
    "slack": {
      "type": "http",
      "url": "https://mcp.slack.com/mcp",
      "oauth": {
        "scopes": "channels:read chat:write search:read"
      }
    }
  }
}
```

`oauth.scopes` 優先於 `authServerMetadataUrl` 和伺服器在 `/.well-known` 探索的範圍。將其保留為未設定以讓 MCP 伺服器決定請求的範圍集。

當未設定 `oauth.scopes` 時，Claude Code 不會請求自動探索的授權伺服器中繼資料中的完整 `scopes_supported` 目錄。從已設定的 `authServerMetadataUrl` 擷取的中繼資料仍會將其 `scopes_supported` 作為請求的範圍提供。

如果授權伺服器在 `scopes_supported` 中公告 `offline_access`，Claude Code 會將其附加到固定範圍，以便可以在不進行新瀏覽器登入的情況下重新整理存取 token。

如果伺服器稍後為工具呼叫傳回 403 `insufficient_scope`，該呼叫會失敗，並顯示 [`needs additional permissions`](https://code.claude.com/docs/zh-TW/errors#mcp-server-needs-you-to-sign-in-again) 訊息，該訊息指出伺服器請求的範圍。伺服器在 `/mcp` 中顯示為需要身分驗證。

如果該範圍不在您的固定 `oauth.scopes` 中，請新增它，然後執行 `/mcp` 並再次驗證伺服器。Claude Code 請求固定範圍而不是伺服器指出的範圍，因此如果您在不新增它的情況下再次驗證，您獲得的 token 仍然缺少它。

### 對位於需驗證之代理伺服器後方的伺服器使用 OAuth

如果您的 MCP 伺服器位於會檢查其自身標頭的代理伺服器或閘道後方並使用 OAuth，當 OAuth 請求未附帶該標頭時，登入會失敗。透過代理伺服器登入需要 Claude Code v2.1.299 或更新版本，且標頭和登入都必須設定：

* **代理伺服器的標頭**：使用 [`--header`](#option-1-add-a-remote-http-server)、`headers` 欄位或 [`headersHelper`](#use-dynamic-headers-for-custom-authentication) 傳遞，並使用代理伺服器讀取的名稱
* **OAuth 登入**：不要將 `Authorization` 放入已設定的標頭中，然後在您的 shell 中使用 `claude mcp login <name>` 登入。如果您設定了 `Authorization` 標頭，Claude Code 會將其作為伺服器的憑證，不會為該伺服器回退到 OAuth。

### 使用動態標頭進行自訂身分驗證

當 Kerberos、短期 token 或內部 SSO 等身分驗證需要在連線時產生標頭時，請將伺服器的 `headersHelper` 設定為一個命令。Claude Code 會在連線時執行它，並將其輸出合併到它傳送的標頭中。此範例使用指令碼：

```json theme={null}
{
  "mcpServers": {
    "internal-api": {
      "type": "http",
      "url": "https://mcp.internal.example.com",
      "headersHelper": "/opt/bin/get-mcp-auth-headers.sh"
    }
  }
}
```

該命令也可以是內聯的：

```json theme={null}
{
  "mcpServers": {
    "internal-api": {
      "type": "http",
      "url": "https://mcp.internal.example.com",
      "headersHelper": "echo '{\"Authorization\": \"Bearer '\"$(get-token)\"'\"}'"
    }
  }
}
```

**需求：**

* 命令必須將字串鍵值對的 JSON 物件寫入 stdout
* Claude Code 在 shell 中執行命令，並在 10 秒後放棄
* Claude Code 根據 [您設定伺服器的位置](#where-the-helper-runs) 選擇命令的工作目錄，因此請將指令碼作為絕對路徑提供或將其放在 `PATH` 上
* 動態標頭會覆寫任何具有相同名稱的靜態 `headers`

一旦 [專案和本機範圍伺服器的信任規則](#trust-a-folder-before-its-headershelper-runs) 允許 helper 執行，Claude Code 會在每次連線時（工作階段開始和重新連接時）重新執行 helper。它不會快取結果，因此您的指令碼負責任何 token 重用。

如果工具呼叫傳回 `401 Unauthorized` 或 `403 Forbidden`，Claude Code 會自動在相同規則下重新執行 helper、使用新標頭重新連接並重試呼叫一次。Claude Code 只有在該重試也失敗時才會在 `/mcp` 中將伺服器標記為需要身分驗證。

當 helper 的輸出包含 `Authorization` 標頭時，Claude Code 會使用該憑證作為伺服器的身分驗證，不會為該伺服器回退到 OAuth。

如果伺服器在連線時拒絕 helper 的憑證，Claude Code 會報告連線失敗，而不是將伺服器標記為需要身分驗證。修復您的 helper 傳回的憑證，然後從 `/mcp` 重新連接以重新執行 helper。

Claude Code 在執行 helper 時設定這些環境變數：

| 變數 | 值 |
| :- | :- |
| `CLAUDE_CODE_MCP_SERVER_NAME` | MCP 伺服器的名稱 |
| `CLAUDE_CODE_MCP_SERVER_URL` | MCP 伺服器的 URL |
| `CLAUDE_PLUGIN_ROOT` | 外掛程式的根目錄。僅當 [外掛程式](https://code.claude.com/docs/zh-TW/plugins/components.md#mcp-servers) 提供伺服器時設定 |

使用這些來編寫為多個 MCP 伺服器服務的單個 helper 指令碼。

外掛程式提供的 `headersHelper` 無法參考外掛程式的 [`${user_config.*}`](https://code.claude.com/docs/zh-TW/plugins/manifest-reference#user-configuration) 值，因為命令透過 shell 執行。Claude Code 報告伺服器設定錯誤，並顯示 [錯誤](https://code.claude.com/docs/zh-TW/errors.md#plugin-command-references-user-config)，不會替換該值。改為將 `${user_config.KEY}` 放在伺服器的 `headers` 欄位中，該欄位不會進行 shell 解析，或讓 helper 指令碼從設定檔讀取該值。在 v2.1.207 之前，`headersHelper` 會替換 `${user_config.*}` 值。

#### Helper 執行的位置

Claude Code 從宣告伺服器的設定中選擇 `headersHelper` 命令的工作目錄。Claude 在 Bash 中執行的 `cd` 不會移動它，[`/cd`](https://code.claude.com/docs/zh-TW/permissions#move-the-session-to-another-directory) 僅對從工作階段主要工作目錄執行的伺服器移動它。下表中的每一行給出您的 `headersHelper` 命令中相對路徑解析的目錄。

| 您設定伺服器的位置 | 工作目錄 |
| :- | :- |
| [外掛程式](https://code.claude.com/docs/zh-TW/plugins/components.md#mcp-servers) | 外掛程式的根目錄 |
| 專案 `.mcp.json` 或 [本機範圍](#local-scope) 伺服器 | 宣告伺服器的專案目錄 |
| 您專案中的 agent 檔案、來自 SDK 的 `mcpServers` 選項或 `setMcpServers()` 方法的伺服器，或 [`--mcp-config`](https://code.claude.com/docs/zh-TW/cli-reference) | 工作階段的 [主要工作目錄](https://code.claude.com/docs/zh-TW/permissions.md#working-directories) |
| [使用者範圍](#user-scope)、[受管 MCP](https://code.claude.com/docs/zh-TW/managed-mcp.md)、[claude.ai 連接器](#use-mcp-servers-from-claude-ai)，或來自您專案外的 agent 檔案，包括來自 `--add-dir` 目錄的檔案 | 您的設定目錄，`~/.claude`，除非您設定 [`CLAUDE_CONFIG_DIR`](https://code.claude.com/docs/zh-TW/env-vars) |

在 v2.1.238 之前，Claude Code 也從您啟動它的目錄執行使用者範圍、受管和 claude.ai 連接器伺服器的 helper，以及來自您專案外的 agent 檔案的 helper。

#### Helper 可以讀取哪些變數

儲存庫或外掛程式提供的 `headersHelper` 是您未編寫的命令，因此 Claude Code 執行它時不會從您的環境中提供憑證變數，例如 `ANTHROPIC_API_KEY`。您設定伺服器的位置決定是否適用：

* **已移除**：專案 `.mcp.json` 或外掛程式中的伺服器，以及來自您專案或 `--add-dir` 目錄的 agent 檔案中的內聯伺服器
* **未移除**：[使用者](#user-scope) 或 [本機範圍](#local-scope) 的伺服器、[受管 MCP](https://code.claude.com/docs/zh-TW/managed-mcp.md) 中的伺服器、來自 [claude.ai 連接器](#use-mcp-servers-from-claude-ai) 的伺服器、由 SDK 或 [`--mcp-config`](https://code.claude.com/docs/zh-TW/cli-reference) 提供的伺服器，以及來自 `~/.claude/agents/`、受管設定或使用 `--agents` 傳遞的 agent 檔案中的內聯伺服器

除了 Git 的 `GIT_CONFIG_KEY_<n>` 變數外，Claude Code 會從您的環境中移除名稱看起來像憑證的每個變數，例如名稱中包含 `TOKEN`、`SECRET`、`PASSWORD`、`KEY` 或 `AUTH` 的名稱（無論大小寫），因此 `ANTHROPIC_API_KEY` 和 `MY_REGISTRY_TOKEN` 都會被移除。Claude Code 也會移除名稱不遵循該模式的固定憑證變數清單，例如 `ANTHROPIC_CUSTOM_HEADERS`。

當這適用於您的 helper 時，讓指令碼從檔案或憑證存放區讀取其憑證。如果伺服器的 `url` [帶有這些變數之一的即時值](#environment-variable-expansion-in-mcp-json)，例如 `MY_REGISTRY_TOKEN`，helper 接收的 `CLAUDE_CODE_MCP_SERVER_URL` 值也會將該部分替換為 `REDACTED`。

#### 在 headersHelper 執行之前信任資料夾

Claude Code 將 `headersHelper` 作為任意 shell 命令執行。對於專案 `.mcp.json` 中或 [本機範圍](#local-scope) 的伺服器，它只在您接受宣告伺服器的專案目錄的 [信任對話方塊](https://code.claude.com/docs/zh-TW/permissions.md#project-allow-rules-and-workspace-trust) 後執行 helper。在 v2.1.238 之前，`claude -p` 或 SDK 工作階段執行這些 helper 而不檢查信任，互動式工作階段在您信任父資料夾後執行它們。

* **不計算的信任**：父資料夾的信任，以及 `claude -p` 或 SDK 工作階段為 [設定檔中的 hook](https://code.claude.com/docs/zh-TW/permissions.md#what-runs-before-you-trust-a-folder) 獲得的自動信任
* **直到您信任資料夾**：Claude Code 僅使用其靜態 `headers` 連接伺服器。在 `claude -p` 或 SDK 工作階段中，它也會為每個伺服器將一行 [`headersHelper not run`](https://code.claude.com/docs/zh-TW/errors#headershelper-not-run) 列印到 stderr，告訴您如何授予信任。
* **無對話方塊的信任**：在 `~/.claude.json` 中將 `projects["<path>"].hasTrustDialogAccepted` 設定為 `true`。`<path>` 是 [專案允許規則和工作區信任](https://code.claude.com/docs/zh-TW/permissions.md#project-allow-rules-and-workspace-trust) 所說明 Claude Code 用來作為信任鍵的資料夾。

Claude Code 將相同規則應用於在 [agent 檔案](https://code.claude.com/docs/zh-TW/sub-agents.md#scope-mcp-servers-to-a-subagent) 中內聯宣告的伺服器，檢查該 agent 檔案來自何處：您的專案（對於其 `.claude/agents/` 目錄中的檔案）或 `--add-dir` 目錄。直到您 [信任該專案或目錄本身](https://code.claude.com/docs/zh-TW/permissions.md#what-runs-before-you-trust-a-folder)，Claude Code 完全不會載入伺服器，因此其 helper 也永遠不會執行。

### 登入位於需要標頭之閘道後方的 MCP 伺服器

當閘道需要某個標頭（例如 `X-API-Key`），而 Claude Code 未傳送該標頭時，MCP 伺服器的 OAuth 登入會失敗。若要讓 Claude Code 傳送該標頭，請將其新增到伺服器的設定中，並使用 Claude Code v2.1.299 或更新版本：

* **您可以編輯其[設定](#mcp-installation-scopes)的伺服器**：在 [`headers`](#example-with-variable-expansion) 中設定它，或從 [`headersHelper`](#use-dynamic-headers-for-custom-authentication) 傳回它
* **由[受管 MCP](https://code.claude.com/docs/zh-TW/managed-mcp.md) 或[外掛](#plugin-provided-mcp-servers)提供的伺服器**：請您的管理員或外掛作者將該標頭新增到伺服器的項目中

接著，Claude Code 會將除 `Authorization` 以外的已設定標頭加入它傳送到伺服器來源的登入、token 重新整理和 token 撤銷請求中。伺服器的來源是其 `url` 中的協定、主機和連接埠。需要該標頭的閘道仍可能在授權頁面或位於其他來源的授權伺服器處阻擋登入：

* **授權頁面**：您在瀏覽器中於此頁面登入，而瀏覽器不會傳送已設定的標頭。如果您的瀏覽器收到的是閘道的錯誤而非該頁面，請要求閘道的管理者讓該頁面在沒有標頭的情況下通過。
* **位於其他來源的授權伺服器**：如果該伺服器前方的閘道也需要該標頭，登入會在那裡失敗。請要求該閘道的管理者讓 OAuth 請求在沒有標頭的情況下通過。

## 從 JSON 配置新增 MCP servers

如果您有 MCP server 的 JSON 配置，您可以直接新增它：

**1. 從 JSON 新增 MCP server**

```bash theme={null}
# 基本語法
claude mcp add-json <name> '<json>'

# 範例：使用 JSON 配置新增 HTTP server
claude mcp add-json weather-api '{"type":"http","url":"https://api.weather.com/mcp","headers":{"Authorization":"Bearer token"}}'

# 範例：使用 JSON 配置新增 stdio server
claude mcp add-json local-weather '{"type":"stdio","command":"/path/to/weather-cli","args":["--api-key","abc123"],"env":{"CACHE_DIR":"/tmp"}}'

# 範例：使用預先配置的 OAuth 認證新增 HTTP server
claude mcp add-json my-server '{"type":"http","url":"https://mcp.example.com/mcp","oauth":{"clientId":"your-client-id","callbackPort":8080}}' --client-secret
```

**2. 驗證 server 已新增**

```bash theme={null}
claude mcp get weather-api
```

> [!TIP]
>
> 提示：
>
> * 確保 JSON 在您的 shell 中正確逸出
> * JSON 必須符合 MCP server 配置架構
> * 您可以使用 `--scope user` 將 server 新增到您的使用者配置，而不是專案特定的配置

## 從 Claude Desktop 匯入 MCP servers

如果您已在 Claude Desktop 中配置了 MCP servers，您可以匯入它們：

**1. 從 Claude Desktop 匯入 servers**

```bash theme={null}
# 基本語法 
claude mcp add-from-claude-desktop 
```

**2. 選擇要匯入的 servers**

執行命令後，您會看到一個互動式對話框，允許您選擇要匯入的 servers。

**3. 驗證 servers 已匯入**

```bash theme={null}
claude mcp list 
```

透過 `claude mcp` 命令新增的伺服器名稱只能包含字母、數字、連字號和底線。Claude Desktop 不會套用該限制，因此名稱包含任何其他字元（例如空格）的 Claude Desktop 伺服器無法匯入。匯入會報告它拒絕的每個名稱，並仍會匯入您選擇的其他伺服器。

> [!TIP]
>
> 提示：
>
> * 此功能僅適用於 macOS 和 Windows Subsystem for Linux (WSL)
> * 它從這些平台上的標準位置讀取 Claude Desktop 配置檔案
> * 使用 `--scope user` 旗標將 servers 新增到您的使用者配置
> * 匯入的 servers 將具有與 Claude Desktop 中相同的名稱（當名稱只包含字母、數字、連字號和底線時）。Claude Code 會報告名稱包含任何其他字元的伺服器並跳過它
> * 如果已存在相同名稱的 servers，它們將獲得數字尾碼（例如，`server_1`）

## 使用來自 claude.ai 的 MCP 伺服器

如果您已使用 [claude.ai](https://claude.ai) 帳戶登入 Claude Code，您在 claude.ai 中新增的 MCP 伺服器（稱為 [connectors](https://claude.com/docs/connectors)）會自動在 Claude Code 中可用：

**1. 在 claude.ai 中設定 MCP 伺服器**

在 [claude.ai/customize/connectors](https://claude.ai/customize/connectors) 新增伺服器。在 Team 和 Enterprise 方案上，只有管理員可以新增伺服器。

**2. 驗證 MCP 伺服器**

在 claude.ai 中完成任何必要的驗證步驟。

**3. 在 Claude Code 中檢視和管理伺服器**

在 Claude Code 中，使用命令：

```text wrap theme={null}
/mcp
```

來自 claude.ai 的伺服器會出現在清單中，並有指示器顯示它們來自 claude.ai。

Anthropic 也自行提供一些 connectors，無需您或管理員新增。在可使用 [Claude Docs](https://code.claude.com/docs/zh-TW/artifacts.md#write-a-document-with-claude-docs) 的帳戶上，`/mcp` 會列出 `claude.ai Claude Docs`，無需設定，當您要求建立供他人使用的文件時，Claude 會使用它。若要僅關閉此 connector，請參閱 [停用 claude.ai connectors](#disable-claude-ai-connectors)。

當您的組織在 claude.ai 中管理其驗證時，Claude Code 會在 `/mcp` 和 [`/plugin`](https://code.claude.com/docs/zh-TW/plugins/install) 管理員中將 connector 標記為 `managed`。Managed 狀態不會改變 Claude Code 連接到 connector 的方式，也不會改變您組織的 [工具控制](#organization-controls-on-connector-tools) 的應用方式。

您從未登入過的 Connectors 會在 claude.ai 區段末尾的 `Show unused connectors` 列後面摺疊，因此組織佈建的清單不會填滿面板。選擇該列以展開它們。您之前登入過的 connector 即使目前需要重新驗證，仍會保持可見。

Connectors 來自 claude.ai 時，只有在您的作用中 [驗證方法](https://code.claude.com/docs/zh-TW/authentication.md#authentication-precedence) 是 claude.ai 訂閱登入時才會擷取。即使您之前執行過 `/login`，在以下情況下也不會載入：

* `ANTHROPIC_API_KEY`、`ANTHROPIC_AUTH_TOKEN` 或 `apiKeyHelper` 處於作用中
* Amazon Bedrock 或 Google Cloud 的 Agent Platform 等第三方提供者處於作用中
* `ANTHROPIC_PROFILE`、federation 變數或作用中的 [Anthropic 設定檔](https://code.claude.com/docs/zh-TW/authentication.md#anthropic-profiles-and-federation-credentials) 提供認證
* `CLAUDE_CODE_OAUTH_TOKEN` 持有來自 [`claude setup-token`](https://code.claude.com/docs/zh-TW/authentication#generate-a-long-lived-token) 的權杖，該權杖只能進行模型請求

如果 `/mcp` 未列出您新增的 connector，請執行 `/status` 以確認哪個驗證方法處於作用中。取消設定該環境變數、移除 `apiKeyHelper` 設定，或 [關閉設定檔](https://code.claude.com/docs/zh-TW/authentication.md#anthropic-profiles-and-federation-credentials)，然後執行 `/login` 以選擇您的 claude.ai 帳戶。

如果暫時性網路問題導致您的工作階段啟動時無法載入 connector 清單，Claude Code 會在背景中重試擷取最多三次，一旦重試成功，connectors 就會出現。如果它們仍未出現，請重新啟動 Claude Code 以再次擷取清單。

如果 `/mcp` 顯示 connector 為 `session token rejected`，或其詳細檢視顯示 [`claude.ai rejected the session token`](https://code.claude.com/docs/zh-TW/errors#claude-ai-rejected-the-session-token)，則 claude.ai 拒絕了來自您 Claude Code 登入的權杖。再次授權 connector 不會清除此狀態，因為被拒絕的不是 connector 在 claude.ai 中的授權。若要清除它：

1. 執行 `/login` 以再次登入。
2. 從 `/mcp` 重新連接 connector。

在 v2.1.222 之前，Claude Code 將 connectors 標記為需要驗證，授權它們無法解決此問題。

您在 Claude Code 中新增的伺服器會 [優先於](#scope-hierarchy-and-precedence) 指向相同 URL 的 claude.ai connector。發生這種情況時，`/mcp` 會將 connector 列為隱藏，並顯示如何移除重複項（如果您寧願使用 connector）。

某些 Anthropic 託管的 connectors（例如 Microsoft 365、Gmail 和 Google Calendar）不支援來自 Claude Code 的本機 OAuth，因為上游身分識別提供者只接受 claude.ai 註冊的重新導向 URL。當您使用 `claude mcp add` 或在 `.mcp.json` 中新增的伺服器指向這些主機之一，且您從 `/mcp` 或使用 `claude mcp login` 登入時，Claude Code 會顯示 [`is Anthropic-hosted and doesn't support local OAuth`](https://code.claude.com/docs/zh-TW/errors#anthropic-hosted-and-doesnt-support-local-oauth)，指導您改為在 [claude.ai/customize/connectors](https://claude.ai/customize/connectors) 連接服務。

在您使用 `claude mcp remove <name>` 移除您的項目並在 claude.ai 上連接服務後，connector 會自動出現在 Claude Code 中。

### Connectors 如何到達 Claude Code

哪些設定控制 claude.ai connector 取決於您的工作階段在何處執行，因為只有某些工作階段本身從 claude.ai 擷取 connectors。下表中的每一列命名 connectors 在一種工作階段中的到達方式及其控制方式。桌面應用程式的 WSL 工作階段沒有列，因為 connectors [仍在逐步推出至這些工作階段](https://code.claude.com/docs/zh-TW/desktop-wsl.md#check-for-the-terminal-and-connectors)。

| 工作階段執行位置 | Connectors 如何到達 | 控制它們的因素 |
| :- | :- | :- |
| Terminal、[VS Code](https://code.claude.com/docs/zh-TW/vs-code.md)、[JetBrains](https://code.claude.com/docs/zh-TW/jetbrains.md) 和 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/claude-code-features.md) 工作階段 | Claude Code 從 claude.ai 擷取它們 | 本節中的設定和 [managed MCP 設定](https://code.claude.com/docs/zh-TW/managed-mcp.md) |
| [Cloud 工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md) | 雲端主機傳入它們 | 您的 claude.ai 組織設定，加上到達工作階段的 [allowlist 和 denylist](https://code.claude.com/docs/zh-TW/managed-mcp.md#policy-based-control-with-allowlists-and-denylists) 設定，以及執行它的主機上的任何 `managed-mcp.json` |
| [桌面應用程式](https://code.claude.com/docs/zh-TW/desktop.md) 的本機和 SSH 工作階段 | 桌面應用程式在程序中傳遞它們 | 您組織的 [connector 工具控制](#organization-controls-on-connector-tools) 中的 `blocked` 項目 |

[`disableClaudeAiConnectors`](#disable-claude-ai-connectors)、`ENABLE_CLAUDEAI_MCP_SERVERS` 和 [`allowAllClaudeAiMcps`](https://code.claude.com/docs/zh-TW/settings-reference#allowallclaudeaimcps) 只作用於第一列，Claude Code 本身擷取的 connectors。其他兩列在以下方面與其不同：

* **Cloud 工作階段**：到達工作階段的 `allowedMcpServers` 和 `deniedMcpServers` 項目（例如透過 [server-managed 設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)）也會篩選傳遞的 connectors。工作階段的代理會重寫每個 connector 的 URL，因此為 connector 自己的 URL 編寫的 `serverUrl` 模式不會符合它。若要在自託管環境中的 URL allowlist 旁邊允許傳遞的 connectors，請新增 [Connector 流量離開您的網路](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#connector-traffic-leaves-your-network) 下列出的 `serverUrl` 項目。當執行工作階段的主機上存在 `managed-mcp.json` 時（例如 [self-hosted runner 主機](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#mcp-servers)），Claude Code 會捨棄傳遞的 connectors，無論您是否設定 `allowAllClaudeAiMcps`。
* **桌面應用程式本機和 SSH 工作階段**：桌面應用程式將 connectors 註冊為程序內 `type: "sdk"` 伺服器，沒有 MCP 設定或 `managed-mcp.json` 到達它們。使用者可以透過在 [claude.ai/customize/connectors](https://claude.ai/customize/connectors) 斷開連接來將 connector 排除在自己的工作階段之外。組織可以阻止 connector 的 [工具](#organization-controls-on-connector-tools) 或完全 [關閉桌面應用程式中的 Claude Code](https://code.claude.com/docs/zh-TW/desktop.md#admin-console-controls)。

### 組織對 connector 工具的控制

您的組織可以在 [claude.ai connectors](https://claude.com/docs/connectors) 上設定每個工具的控制。Claude Code 在啟動時讀取這些設定並在本機強制執行，除了桌面應用程式的 [本機和 SSH 工作階段](#how-connectors-reach-claude-code)。在那裡，桌面應用程式在傳遞 connector 之前會隱藏 `blocked` 工具，`ask` 設定不會到達 Claude Code，因此它會將工作階段的普通 [權限規則](https://code.claude.com/docs/zh-TW/permissions.md) 應用於這些工具，而不是在每次呼叫時提示。在 Claude Code 本身擷取 connectors 的工作階段中，執行 `/mcp` 以查看哪個設定適用於 connector 上的每個工具。

* **工具設定為 `ask`**：Claude Code 會在每次呼叫時提示，原因為 `Your organization requires approval for this tool`。即使在 `acceptEdits`、`auto` 和 `bypassPermissions` [權限模式](https://code.claude.com/docs/zh-TW/permissions.md#permission-modes) 中，提示也會出現。在終端機中，提示沒有記住您選擇的選項。符合工具的 [Allow 規則](https://code.claude.com/docs/zh-TW/permissions.md) 也不會跳過提示。在 `dontAsk` 模式中（永遠不提示），Claude Code 會改為拒絕呼叫。
* **工具設定為 `blocked`**：Claude Code 在 Claude 看到它之前會篩選出工具，因此它永遠不會出現在工具清單中。在 Claude Code 本身擷取 connectors 的工作階段中，`/mcp` 工具清單仍會顯示工具，標記為 `disabled by your organization`。

桌面應用程式和 claude.ai 聊天應用相同的 `blocked` 設定，因此 Claude 也無法在那裡使用工具，您無法從桌面應用程式的工作階段中隱藏工具，同時在聊天中保持可用。桌面應用程式會跳過所有工具都被阻止的 connector。

### 停用 claude.ai connectors

Claude Code 只將 [`disableClaudeAiConnectors`](https://code.claude.com/docs/zh-TW/settings-reference#disableclaudeaiconnectors) 應用於它 [本身擷取](#how-connectors-reach-claude-code) 的 connectors，而不是雲端主機或桌面應用程式傳遞的 connectors。若要關閉它擷取的 connectors，請在任何設定範圍中將設定設為 `true`：

```json theme={null}
{
  "disableClaudeAiConnectors": true
}
```

此設定使用任何來源為真的語義：任何設定來源中的 `true` 優先。簽入的專案 `.claude/settings.json` 可以選擇退出 Claude Code 本身擷取的 connectors，但專案層級的 `false` 無法重新啟用使用者或原則層級 `true` 已停用的 connectors。透過 `--mcp-config` 明確傳遞的伺服器不受影響。

您也可以將 `ENABLE_CLAUDEAI_MCP_SERVERS` 環境變數設為 `false`，這對目前的 shell 工作階段有相同的效果：

```bash theme={null}
ENABLE_CLAUDEAI_MCP_SERVERS=false claude
```

若要阻止個別 claude.ai connectors 而不是全部，請按名稱或 URL 模式將它們新增至 [`deniedMcpServers`](https://code.claude.com/docs/zh-TW/managed-mcp)。例如，`"claude.ai Slack"` 的 `serverName` 項目會阻止 Slack connector。您也可以執行 `/mcp` 以針對目前專案切換 Claude Code 擷取的任何 connector。

## 將 Claude Code 用作 MCP 伺服器

您可以將 Claude Code 本身用作 MCP 伺服器，其他應用程式可以連接到它：

```bash theme={null}
# Start Claude as a stdio MCP server
claude mcp serve
```

該命令在啟動時不會列印任何內容。stdio MCP 伺服器透過 stdin 和 stdout 進行通訊，因此沉默、被阻止的終端機表示伺服器正在執行並等待用戶端連接。

您可以透過將此設定新增到 claude\_desktop\_config.json 在 Claude Desktop 中使用它：

```json theme={null}
{
  "mcpServers": {
    "claude-code": {
      "type": "stdio",
      "command": "claude",
      "args": ["mcp", "serve"],
      "env": {}
    }
  }
}
```

> [!WARNING]
>
> **設定可執行檔路徑**：`command` 欄位必須參考 Claude Code 可執行檔。如果 `claude` 命令不在您系統的 PATH 中，您需要指定可執行檔的完整路徑。
>
> 若要找到完整路徑：
>
> ```bash theme={null}
> which claude
> ```
>
> 然後在您的設定中使用完整路徑：
>
> ```json theme={null}
> {
>   "mcpServers": {
>     "claude-code": {
>       "type": "stdio",
>       "command": "/full/path/to/claude",
>       "args": ["mcp", "serve"],
>       "env": {}
>     }
>   }
> }
> ```
>
> 沒有正確的可執行檔路徑，您會遇到像 `spawn claude ENOENT` 這樣的錯誤。

> [!TIP]
>
> 提示：
>
> * 在 Claude Desktop 中，嘗試要求 Claude 讀取目錄中的檔案、進行編輯等。
> * 此 MCP 伺服器只向您的 MCP 用戶端公開 Claude Code 的工具，因此您自己的用戶端負責為個別工具呼叫實施使用者確認。

### 以 MCP 用戶端身分讀取背景命令的輸出

當 `claude mcp serve` 傳回的 Bash 或 PowerShell 結果中包含 `backgroundOutputPath` 欄位時，表示該呼叫讓其命令[在背景](https://code.claude.com/docs/zh-TW/tools-reference.md#background-commands)中持續執行。當您的用戶端在呼叫中設定 `run_in_background: true` 時，命令會在背景中執行。前景命令在達到逾時時間時，也可能[移至背景](https://code.claude.com/docs/zh-TW/tools-reference.md#foreground-commands-that-move-to-the-background)。

此欄位位於結果的 JSON 文字中，並保存該命令輸出檔案的路徑。

* **若要讀取目前為止的輸出**：從您的用戶端開啟該路徑的檔案，或將該路徑作為 `file_path` 傳遞給伺服器的 [`Read`](https://code.claude.com/docs/zh-TW/tools-reference#read-tool-behavior) 工具
* **若要得知命令何時完成**：在 `command` 值後附加一個輸出固定字串的 `echo`，例如 `npm test; echo DONE`。當該字串出現在檔案中時，命令即已完成。若沒有該字串，就沒有任何標記表示結束，因為 Claude Code 不會在檔案中加入結尾行，也不會通知您的用戶端。
* **若要讀取長輸出的結尾**：僅使用 `file_path` 呼叫 `Read` 會傳回[第一頁](https://code.claude.com/docs/zh-TW/tools-reference.md#large-files)，或在檔案超過大小限制時失敗。請同時傳遞 `offset` 和 `limit`，這在任何檔案大小下皆可運作：
  1. 呼叫 `Read`，並將 `offset` 和 `limit` 皆設為 `1`，然後從結果中取得 `totalLines`
  2. 再次呼叫 `Read`，將 `offset` 設為 `totalLines` 減九，並將 `limit` 設為 `10`
  3. 在第二次呼叫傳回的最後十行中尋找您的 `echo` 字串

`backgroundOutputPath` 欄位需要 Claude Code v2.1.295 或更新版本。

## MCP 輸出限制和警告

當 MCP 工具產生大量輸出時，Claude Code 會幫助管理 token 使用量，以防止淹沒您的對話上下文：

* **輸出警告閾值**：當任何 MCP 工具輸出超過 10,000 個 token 時，Claude Code 會顯示警告
* **可設定的限制**：您可以使用 `MAX_MCP_OUTPUT_TOKENS` 環境變數調整允許的最大 MCP 輸出 token 數
* **預設限制**：預設最大值為 25,000 個 token
* **範圍**：環境變數適用於未聲明自己限制的工具。設定 [`anthropic/maxResultSizeChars`](#raise-the-limit-for-a-specific-tool) 的工具會針對文字內容使用該值，無論 `MAX_MCP_OUTPUT_TOKENS` 設定為何。傳回影像資料的工具仍受 `MAX_MCP_OUTPUT_TOKENS` 限制
* **超過限制**：當沒有影像內容的成功結果超過 token 限制時，Claude Code 會將其儲存到檔案，並在對話中用命名檔案路徑的訊息取代它，以便 Claude 在需要內容時讀取該檔案。該檔案位於 [`~/.claude/projects/`](https://code.claude.com/docs/zh-TW/claude-directory#cleaned-up-automatically) 下的工作階段 `tool-results` 目錄中。
* **來自 HTTP 和 SSE 伺服器的回應大小**：當來自 [HTTP](#option-1-add-a-remote-http-server) 或 [SSE](#option-2-add-a-remote-sse-server) 伺服器的回應超過 16 MiB 時，Claude Code 會停止讀取該回應，且請求會失敗。此限制適用於解壓縮後的單一 JSON 回應主體或事件串流中的單一事件。如果您負責維護該伺服器，請減少每個回應傳回的資料量以維持在限制之內，例如將結果分頁
* **來自 WebSocket 伺服器的訊息大小**：當 [WebSocket](#option-4-add-a-remote-websocket-server) 伺服器傳送單一超過 16 MiB 的訊息時，Claude Code 會[關閉連線](#mid-session-drops-of-a-remote-server)，且該伺服器上進行中的呼叫會失敗。如果您負責維護該伺服器，請減少每則訊息傳回的資料量以維持在限制之內

Claude Code 已[移至背景任務](#automatic-backgrounding-of-long-tool-calls)的呼叫會透過任務通知回報其結果。對於在前景完成的呼叫，另有兩項限制適用：

* **文字結果的字元限制**：對於未聲明 [`anthropic/maxResultSizeChars`](#raise-the-limit-for-a-specific-tool) 的工具，沒有影像內容的成功結果一旦超過 50,000 個字元，無論其 token 數為何，Claude Code 都會將其儲存到檔案。設定 `MAX_MCP_OUTPUT_TOKENS` 不會改變此閾值
* **錯誤結果**：當工具傳回標記為 `isError: true` 的結果時，Claude 會將該結果的文字作為工具的錯誤訊息接收。超過約 11,000 個字元的錯誤文字只會保留其前 5,000 個和後 5,000 個字元，中間會有一個標記說明移除了多少字元

若要變更 token 限制，請在啟動 Claude Code 之前於 shell 中設定 `MAX_MCP_OUTPUT_TOKENS`：

```bash theme={null}
export MAX_MCP_OUTPUT_TOKENS=50000
claude
```

### 提高特定工具的限制

如果您正在建置 MCP 伺服器，可以透過在工具的 `tools/list` 回應項目中設定 `_meta["anthropic/maxResultSizeChars"]`，允許個別工具傳回超過預設持久化到磁碟閾值 50,000 個字元的結果。Claude Code 會將該工具的閾值提高到註解值，最高可達 500,000 個字元的硬性上限。

這對於傳回本質上很大但必要的輸出的工具很有用，例如資料庫 schema 或完整檔案樹。沒有註解的情況下，超過預設閾值的成功結果會被持久化到磁碟，並在對話中被檔案參考取代。

```json theme={null}
{
  "name": "get_schema",
  "description": "Returns the full database schema",
  "_meta": {
    "anthropic/maxResultSizeChars": 200000
  }
}
```

該註解對文字內容獨立於 `MAX_MCP_OUTPUT_TOKENS` 應用，因此使用者不需要為聲明它的工具提高環境變數。傳回影像資料的工具仍受 token 限制。

### 工具結果中的影像

當 MCP 工具傳回 PNG、JPEG、GIF 或 WebP 影像時，Claude 會在對話中內嵌看到該影像。內嵌副本可能會縮小或壓縮以符合模型的影像大小限制。Claude Code 也會將原始位元組儲存到 [`~/.claude/projects/`](https://code.claude.com/docs/zh-TW/claude-directory#cleaned-up-automatically) 下的工作階段 `tool-results` 目錄中的檔案，並提供 Claude 路徑。Claude 隨後可以使用 Bash 等工具裁剪、轉換或重複使用完整解析度檔案。

如果您使用 [`--no-session-persistence`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 或 [`CLAUDE_CODE_SKIP_PROMPT_HISTORY`](https://code.claude.com/docs/zh-TW/env-vars) 停用工作階段持久性，Claude Code 不會寫入影像檔案，Claude 只會收到內嵌副本。

將 MCP 影像結果儲存到檔案需要 Claude Code v2.1.283 或更新版本。

## 具有根層級組合器的工具輸入綱要

某些 MCP 伺服器將工具的輸入綱要宣告為 JSON Schema 聯合，在綱要的最上層使用 `anyOf`、`oneOf` 或 `allOf`。Claude API 不接受這些關鍵字在綱要根層級。它確實接受嵌套在 `properties` 內的組合器，Claude Code 會原封不動地傳送這些組合器。

具有根層級組合器的工具仍然可用。在將工具傳送到 API 之前，Claude Code 會將綱要平坦化為單一物件，並在工具的描述前面加上一句話，告訴 Claude 哪些參數群組屬於一起：

* `allOf`：來自每個分支的屬性會被合併，每個分支的 `required` 清單仍然適用
* `anyOf` 和 `oneOf`：來自每個分支的屬性會被合併，每個分支的 `required` 清單會在工具描述中說明，而不是由綱要強制執行

您的伺服器會接收 Claude 選擇的任何引數，因此請繼續在伺服器端驗證組合。

當 Claude Code 無法產生 API 接受的綱要，或在未收到啟用重寫的遠端設定的部署上時，它會跳過該工具，在伺服器的日誌中記錄原因，並讓伺服器的其他工具保持可用。

## 具有無效輸入綱要的工具

> [!NOTE]
>
> 如果您的工作階段因按位置指名工具的 400 錯誤而失敗，請依照[工具輸入 schema 無效](https://code.claude.com/docs/zh-TW/errors.md#tool-input-schema-is-invalid)中的步驟操作。

如果您的 MCP 伺服器中某個工具的輸入 schema 違反了 API 強制執行的兩項規則之一，Claude Code 會排除該工具。伺服器的其他工具不受影響。Claude Code 在載入伺服器的工具時會檢查這兩項規則：

* 頂層屬性名稱必須為 1 到 64 個字元長，且只能使用 ASCII 字母和數字、`_`、`.` 和 `-`
* 綱要必須對 JSON Schema draft 2020-12 元綱要有效。Claude Code 會對未宣告 `$schema` 的綱要和宣告 draft 2020-12 的綱要套用此檢查。宣告任何其他方言的綱要會跳過此檢查，但上述屬性名稱檢查仍然適用

當 Claude Code 排除一個工具時，它會在伺服器的日誌中記錄原因，並告訴 Claude 它排除了哪些工具以及原因，以便您可以詢問 Claude 為什麼工具遺失。如果您修復伺服器上的綱要，下次 Claude Code 載入伺服器的工具時，該工具就會恢復。

當[功能旗標取得](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)關閉或旗標從未到達時（例如在隔離的機器上），違反規則的工具不會被排除：

* Claude 會取得未經變更的工具，而伺服器的日誌會針對該工具記錄 `input schema would be rejected by the Anthropic API`
* 如果 API 隨後拒絕該 schema，請參閱 [API 拒絕其輸入 schema 的工具](#tools-whose-input-schema-the-api-refuses)

在 v2.1.216 之前，沒有部署執行這些檢查。

[根層級組合子處理](#tool-input-schemas-with-a-root-level-combinator)是獨立的，當旗標取得關閉或旗標從未到達時，會保持自己的行為。

### API 拒絕其輸入 schema 的工具

如果除錯日誌中的某一行包含 `the API refused this tool's input schema`，該行指名的是 API 在請求中拒絕其 schema 的工具。Claude Code 會以不帶參數的方式宣告該工具，並重新傳送該請求。

* **如果您的工作階段因按位置指名工具的 400 錯誤而失敗**：請依照[工具輸入 schema 無效](https://code.claude.com/docs/zh-TW/errors.md#tool-input-schema-is-invalid)中的步驟操作
* **如果您使用該伺服器**：您不需要執行任何操作。Claude 仍然可以呼叫該工具，但看不到其參數
* **如果您維護該伺服器**：請在伺服器上修復該工具的輸入 schema。日誌行以 `The API said:` 及 API 拒絕該 schema 的原因結尾。請驗證伺服器收到的引數，因為 Claude 是在看不到其參數的情況下呼叫該工具

在 v2.1.300 之前，每個包含被拒絕 schema 的回合都會因[按位置指名工具的 400 錯誤](https://code.claude.com/docs/zh-TW/errors.md#tool-input-schema-is-invalid)而失敗。

## 名稱超過 128 個字元的工具

如果 `/mcp` 列出了 Claude 無法呼叫的工具，請檢查該工具的完整名稱是否超過 128 個字元。在工作階段中執行 `/mcp` 並選取該工具，即可查看其完整名稱，例如 `mcp__<server>__<tool>`。當 MCP 工具的完整名稱超過 128 個字元時，Claude Code 會將其排除在傳送給 Claude 的工具之外。Claude API 會拒絕包含此類工具的請求，因此排除該工具可讓伺服器的其他工具正常運作。

如需指出該工具名稱的訊息，以及縮短其完整名稱的方法，請參閱 [MCP 工具名稱超過 128 個字元](https://code.claude.com/docs/zh-TW/errors.md#mcp-tool-name-over-128-characters)。

## 要求特定工具的核准

如果您正在建立 MCP 伺服器，可以透過在工具的 `tools/list` 回應項目中將 `_meta["anthropic/requiresUserInteraction"]` 設定為 `true`，來標記工具在每次呼叫時都需要明確核准。該值必須是 JSON 布林值 `true`；任何其他值都會被忽略。

Claude Code 會在每次呼叫時顯示該工具的權限提示，即使在 `acceptEdits`、`auto` 和 `bypassPermissions` [權限模式](https://code.claude.com/docs/zh-TW/permissions.md#permission-modes)中也是如此，並且不會為其提供「不再詢問」選項。與該工具相符的[允許規則](https://code.claude.com/docs/zh-TW/permissions.md#permission-rule-syntax)也不會跳過提示。在 `dontAsk` 模式中（從不提示），Claude Code 會改為拒絕該呼叫。

提示必須到達一個人。在非互動模式下使用 [`--permission-prompt-tool`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags)，來自提示工具的 `allow` 結果對於標記的工具會被轉換為拒絕，並顯示訊息 `MCP tool requires user interaction; not supported via --permission-prompt-tool`。Agent SDK 的 [`canUseTool` 回呼](https://code.claude.com/docs/zh-TW/agent-sdk/permissions)確實會接收這些呼叫並可以核准它們，因為您的 SDK 應用程式應該會將它們顯示給使用者。

將此用於權限提示本身就是重點的工具，例如同意或存取授予步驟，其中自動核准意味著沒有人類曾經同意。來自同一伺服器的其他工具保持其正常的權限行為。

以下 `tools/list` 項目將一個工具標記為始終需要核准。

```json theme={null}
{
  "name": "grant_access",
  "description": "Requests access to a protected resource",
  "_meta": {
    "anthropic/requiresUserInteraction": true
  }
}
```

某些使用介面，例如 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 和基於 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 建立的應用程式，通常允許您透過一次點擊來核准工具呼叫。對於使用此註解標記的工具，Claude Code 會隱藏一次點擊動作並改為顯示工具的完整權限提示，因此核准仍然來自於回答提示的人，而不是點擊。

Claude Code 對於任何只有終端機對話框才能完整呈現的權限請求（例如包含安全警告或遠端使用介面無法顯示的始終允許選項的請求），也會以相同方式隱藏一次點擊核准。您在終端機對話框中回答該請求，而不是從 Remote Control 回答。

## 標記可安全呼叫兩次的工具

如果您建立 MCP 伺服器，請標記可安全呼叫兩次的工具，讓 Claude Code 能夠重複執行在連線關閉時仍處於待處理狀態的呼叫。對於 HTTP 伺服器或 [claude.ai 連接器](#use-mcp-servers-from-claude-ai)，Claude Code 可以在新的連線上重複執行此類呼叫一次。Claude Code 未重複執行的呼叫可能會因 [`connection closed before the tool call was answered`](https://code.claude.com/docs/zh-TW/errors#connection-closed-before-the-tool-call-was-answered) 而失敗。

若要標記工具，請在其 `tools/list` 項目中將下列其中一個 `annotations` 設為 `true`：

* **`idempotentHint`**：該工具可能會變更某些內容，且使用相同引數再次呼叫它是安全的
* **`readOnlyHint`**：該工具不會變更任何內容。Claude Code 也會將該工具的呼叫與其他唯讀呼叫平行執行。

例如，`tools/list` 項目中的下列欄位會將 `set_issue_status` 工具標記為可安全重複執行：

```json theme={null}
{
  "name": "set_issue_status",
  "annotations": {
    "idempotentHint": true
  }
}
```

## 回應 MCP 徵詢請求

MCP 伺服器可以在任務進行中使用徵詢功能向您請求結構化輸入。當伺服器需要無法自行取得的資訊時，Claude Code 會在終端機中顯示互動式對話框，並將您的回應傳回給伺服器。您無需進行任何設定：當伺服器請求徵詢對話框時，它們會自動出現。

伺服器可以透過兩種方式請求輸入：

* **表單模式**：Claude Code 顯示一個對話框，其中包含伺服器定義的表單欄位（例如，使用者名稱和密碼提示）。填入欄位並提交。
* **URL 模式**：Claude Code 詢問是否在您的瀏覽器中開啟連結。伺服器使用此模式進行在終端機外完成的流程，例如登入。

在 URL 模式中，Claude Code 會將 URL 作為命令列引數傳遞給您系統的 URL 處理程式，並限制該引數的長度。當 URL 經過命令列轉義後超過該限制時，您只能拒絕請求。每個需要轉義的字元，例如 `%` 或 `&`，都會計為上限的四倍：其本身的字元加上三個轉義字元。沒有這些字元的 URL 在約 8,000 個字元時達到上限。主要由百分比轉義組成的 URL，其中每三個字元中有一個是 `%`，在大約 4,000 個字元時達到上限。

若要自動回應徵詢請求而不顯示對話框，請使用 [`Elicitation` hook](https://code.claude.com/docs/zh-TW/hooks#elicitation)。

如果您正在建置使用徵詢功能的 MCP 伺服器，請參閱 [MCP 徵詢規格](https://modelcontextprotocol.io/docs/learn/client-concepts#elicitation)以了解協定詳細資訊和結構描述範例。

### 在雲端工作階段中回應徵詢請求

當 Claude 在您雲端工作階段中的任務正在等待 MCP 伺服器的請求時，表示該伺服器需要您提供某些內容，例如某個值或登入。如果請求以卡片形式出現在 claude.ai/code 或 Desktop 應用程式的 **Code** 分頁中，請在卡片上回應：

* **表單模式**：填入欄位，然後按一下 **Submit**
* **URL 模式**：按一下 **Open link**，完成其開啟的流程，然後在卡片上按一下 **I’m done, continue**

若要拒絕請求，請按一下 **Decline**。伺服器回應後，Claude 便會繼續。

如果在這兩處都看不到卡片，則無法在那裡回應該請求。在您自己的工作階段中，請在該處按一下停止按鈕以結束此回合。

### Claude Code 宣告的徵詢模式

如果您建置 MCP 伺服器，Claude Code 在連線時傳送的用戶端功能會告訴您的伺服器它可以請求哪些徵詢模式。Claude Code 在下列連線上宣告 `elicitation: {form: {}, url: {}}`，因此其中任何連線上的伺服器都可以請求這兩種模式：

* 使用 [protocol revision 2026-07-28](#mcp-client-runtimes) 的連線
* 在較早協定修訂版本（2025-11-25 及更舊版本）上，連線至使用者 Claude Code MCP 設定中的 stdio、`sse`、`http` 和 `ws` 伺服器的連線。需要 Claude Code v2.1.287 或更新版本

在較早修訂版本上的其他連線中，例如連線至 [claude.ai 連接器](#use-mcp-servers-from-claude-ai)，Claude Code 宣告的是單純的 `elicitation: {}`，這僅允許表單模式的徵詢請求。

以 Java MCP SDK 0.17.0 或更早版本建置的伺服器，可能會拒絕包含 `form` 和 `url` 的宣告。請參閱 [MCP server rejected the elicitation capability](https://code.claude.com/docs/zh-TW/errors.md#mcp-server-rejected-the-elicitation-capability)。

## 使用 MCP 資源

MCP 伺服器可以公開資源，您可以使用 @ 提及來參考這些資源，類似於您參考檔案的方式。

### 參考 MCP 資源

**1. 列出可用資源**

在您的提示中輸入 `@` 以查看來自所有已連接 MCP 伺服器的可用資源。資源會與檔案一起出現在自動完成選單中。

**2. 參考特定資源**

使用格式 `@server:protocol://resource/path` 來參考資源：

```text wrap theme={null}
Can you analyze @github:issue://123 and suggest a fix?
```

```text wrap theme={null}
Please review the API documentation at @docs:file://api/authentication
```

**3. 多個資源參考**

您可以在單一提示中參考多個資源：

```text wrap theme={null}
Compare @postgres:schema://users with @docs:file://database/user-model
```

> [!TIP]
>
> 提示：
>
> * 資源在被參考時會自動擷取並作為附件包含
> * 資源路徑在 @ 提及自動完成中可進行模糊搜尋
> * Claude Code 會在伺服器支援時自動提供列出和讀取 MCP 資源的工具
> * 資源可以包含 MCP 伺服器提供的任何類型的內容（文字、JSON、結構化資料等）

MCP Apps UI 資源是具有 `ui://` URI 或 `text/html;profile=mcp-app` 媒體類型的項目：供主應用程式呈現的頁面，而不是供 Claude 讀取的內容。它們不會出現在 `@` 建議或資源列表工具的結果中，而且只提供 UI 資源的伺服器會顯示空的資源列表。按其 URI 讀取 UI 資源仍然有效。

## 使用 MCP 工具搜尋進行擴展

工具搜尋透過延遲工具定義直到 Claude 需要時才載入，來保持 MCP 上下文使用量較低。只有工具名稱和伺服器指令在工作階段開始時載入，因此新增更多 MCP 伺服器對您的上下文視窗影響最小。Claude Code 不會對每個伺服器施加固定的工具上限；實際限制是您的上下文視窗預算。

> [!NOTE]
>
> 工具搜尋在 Microsoft Foundry [部署於 Azure 的部署](https://platform.claude.com/docs/en/build-with-claude/claude-in-microsoft-foundry#hosting-options)上不受支援，該部署在伺服器端拒絕它：Claude Code 偵測到拒絕並改為對該部署預先載入 MCP 工具。[`ENABLE_TOOL_SEARCH`](#configure-tool-search) 無法覆寫此設定，因為拒絕來自部署本身。

### 針對 MCP 伺服器作者的工具搜尋

如果您正在建立 MCP 伺服器，啟用工具搜尋時伺服器指令欄位會變得更有用。伺服器指令幫助 Claude 瞭解何時搜尋您的工具，類似於 [skills](https://code.claude.com/docs/zh-TW/skills.md) 的運作方式。

新增清晰、描述性的伺服器指令，說明：

* 您的工具處理的任務類別
* Claude 應何時搜尋您的工具
* 您的伺服器提供的關鍵功能

Claude Code 會截斷超過下列預設限制的工具描述或伺服器指令，Claude 只會看到截斷點之前的文字：

* **伺服器指令，以及預先載入之工具的描述**：4,096 個字元
* **Claude 透過工具搜尋載入之工具的描述**：16,384 個字元

請保持描述和指令簡潔，並將關鍵詳細資訊放在開頭。當工具搜尋將 Claude 的查詢與工具描述比對時，只會讀取較短限制內的部分，因此也請將 Claude 會搜尋的字詞放在開頭附近。只要工具未被延遲，就會預先載入並適用較短的限制，例如當[工具搜尋關閉](#configure-tool-search)、工具[被標記為預先載入](#per-tool-alwaysload)，或其伺服器[豁免延遲](#exempt-a-server-from-deferral)時。

在 v2.1.296 之前，較短的限制為 2,048 個字元；在 v2.1.295 之前，該限制適用於每個工具描述，包括透過工具搜尋載入的描述。

#### 變更描述長度限制

若要為工作階段中的 MCP 伺服器變更 4,096 和 16,384 個字元的[預設限制](#for-mcp-server-authors)，請將 [`CLAUDE_CODE_MAX_MCP_DESCRIPTION_LENGTH`](https://code.claude.com/docs/zh-TW/env-vars#variables) 設定為字元數。Claude Code 會將該數字同時用於這兩個限制。例如，設定為 `8192` 時，會提高伺服器指令和預先載入之工具描述的 4,096 字元限制，並降低透過工具搜尋載入之工具描述的 16,384 字元限制。此變數需要 Claude Code v2.1.280 或更新版本。

Anthropic 在 `api.anthropic.com` 託管的部分 MCP 伺服器，其描述和指令會完整傳送給 Claude，設定此變數也不會截斷它們。

#### 標記工具為預先載入或保持延遲

若要控制伺服器中某個工具的載入方式，請在該工具的 `_meta` 物件中設定 `"anthropic/alwaysLoad"`。將您的伺服器新增到 Claude Code 的人也可以在其設定中為整個伺服器設定 [`alwaysLoad`](#exempt-a-server-from-deferral)，而其設定可以覆寫您的設定：

| 您的工具的值 | 結果 |
| :- | :- |
| `true` | 該工具會預先載入。啟動不會因為此值而等待您的伺服器。設定您伺服器的人仍可以[延遲其所有工具](#defer-a-servers-tools) |
| `false` | 當對方的設定指定 `"alwaysLoad": true` 時，該工具仍保持延遲。這適用於您的伺服器透過 [`--mcp-config`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 傳入、由 [Agent SDK 應用程式](https://code.claude.com/docs/zh-TW/agent-sdk/mcp.md#in-code)提供，或由[外掛](#plugin-provided-mcp-servers)提供的情況。在其他伺服器上，該工具會預先載入。需要 Claude Code v2.1.285 或更新版本 |

以下 `tools/list` 項目要求某個工具預先載入：

```json theme={null}
{
  "name": "search_tickets",
  "description": "Searches the ticket tracker by keyword",
  "_meta": {
    "anthropic/alwaysLoad": true
  }
}
```

### 設定工具搜尋

工具搜尋預設為啟用：MCP 工具被延遲並按需發現。

設定 [`CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS`](https://code.claude.com/docs/zh-TW/env-vars) 會保持工具搜尋關閉。您無法透過自己設定 `ENABLE_TOOL_SEARCH` 來覆寫它。在 Claude Code v2.1.227 或更新版本上，您的組織可以透過[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)在此變數之下保持工具搜尋開啟。在[套用 HIPAA 設定](https://code.claude.com/docs/zh-TW/hipaa-setup.md#check-how-developers-sign-in-and-connect)的工作階段中，工具搜尋會關閉，且 `ENABLE_TOOL_SEARCH` 和受管設定都無法將其重新開啟。[停用預發行功能](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md#disable-pre-release-capabilities) 涵蓋覆寫適用的位置以及變數移除的內容。

Claude Code 在 Claude Opus 4、Claude Sonnet 4、Claude Haiku 4.5 及更新的模型上使用工具搜尋，在 Google Cloud 的 Agent Platform 上則為 Opus 4.5、Sonnet 4.5、Haiku 4.5 及更新的模型。在較早的模型上，Claude Code 會預先載入所有 MCP 工具，且 `ENABLE_TOOL_SEARCH=true` 不會覆寫此行為。

在 Google Cloud 的 Agent Platform 上，Claude Code 按模型世代決定：

* **Claude Opus 4.5、Sonnet 4.5、Haiku 4.5 及更新版本**：工具搜尋預設為開啟，與 Anthropic API 上相同。
* **較早的 Agent Platform 模型**：Claude Code 預先載入所有 MCP 工具，因為它們的服務堆疊拒絕所需的測試版標頭。`ENABLE_TOOL_SEARCH=true` 不會覆寫此設定。

在 v2.1.221 之前，Claude Code 在 Google Cloud 的 Agent Platform 上對所有模型停用工具搜尋，除非您設定 `ENABLE_TOOL_SEARCH=true`。

使用 `ENABLE_TOOL_SEARCH` 環境變數控制工具搜尋行為：

| 值 | 行為 |
| :- | :- |
| (未設定) | 所有 MCP 工具延遲並按需載入。在早於 Opus 4 和 Sonnet 4 的模型上、在[較早的 Agent Platform 模型](#configure-tool-search)上，以及在部署於 Azure 的 Microsoft Foundry 部署上，改為預先載入 |
| `true` | MCP 工具延遲載入，備援情況與（未設定）時相同 |
| `auto` | 閾值模式。原本會被延遲的工具，在其定義總計少於上下文視窗的 10% 時會預先載入。達到 10% 或以上時，工具搜尋會開啟，且即使總計之後降到 10% 以下，這些工具仍可能[保持延遲](#tools-that-stay-deferred-below-the-threshold) |
| `auto:N` | 具有自訂百分比的閾值模式，其中 `N` 是 0-100。例如，`auto:5` 表示 5% |
| `false` | 所有 MCP 工具預先載入，無延遲 |

```bash theme={null}
# Use a custom 5% threshold
ENABLE_TOOL_SEARCH=auto:5 claude

# Disable tool search entirely
ENABLE_TOOL_SEARCH=false claude
```

或在您的 [settings.json `env` 欄位](https://code.claude.com/docs/zh-TW/settings-reference#env)中設定值。

您也可以特別停用 `ToolSearch` 工具：

```json theme={null}
{
  "permissions": {
    "deny": ["ToolSearch"]
  }
}
```

如果您拒絕 `ToolSearch` 或未將其納入 [`--tools`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags)，MCP 工具會改為預先載入，但請求仍可能帶有一個佔位的 `defer_loading` 項目。如果閘道拒絕該項目，請參閱[透過 LLM 閘道使用工具搜尋](#tool-search-through-a-gateway)。

#### 透過 LLM 閘道使用工具搜尋

> [!NOTE]
>
> 以下情況在其他地方說明：
>
> * **您已設定 `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS`**：請參閱[它如何影響工具搜尋](#configure-tool-search)
> * **請求失敗，且錯誤中提及 `defer_loading` 或 `tool_reference`**：請參閱 [Extra inputs are not permitted](https://code.claude.com/docs/zh-TW/errors.md#extra-inputs-are-not-permitted)

當 `ANTHROPIC_BASE_URL` 指向閘道時，Claude Code 預期閘道會[連同 `anthropic-beta` 標頭](https://code.claude.com/docs/zh-TW/llm-gateway-protocol#beta-header-and-body-field-pairs)一起轉發 `defer_loading` 工具欄位和 `tool_reference` 區塊。透過閘道時工具搜尋預設為開啟，因此 MCP 工具會被[延遲](#scale-with-mcp-tool-search)，且請求會包含這些欄位和區塊。在 v2.1.304 之前，透過閘道時工具搜尋為關閉，除非 `ENABLE_TOOL_SEARCH` 為 `true`、`auto` 或 `auto:N`。

在 v2.1.305 或更新版本上，發生 `400` 或 `422` 之後，Claude Code 可以[不使用工具搜尋重試請求](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md#retry-without-tool-search)。重試成功時，畫面上不會顯示任何內容，您也不需要採取任何動作：MCP 工具會改為預先載入。Claude Code 稍後會再次嘗試工具搜尋，代價是多一次被拒絕的請求。

#### 低於 `ENABLE_TOOL_SEARCH=auto` 閾值時仍保持延遲的工具

如果 [`/context`](https://code.claude.com/docs/zh-TW/commands#all-commands) 將工具標示為 `(deferred)` 或 `(loaded on-demand)`，但其定義總計低於 `auto` 閾值，表示工具搜尋在此對話中已經開啟並保持開啟。總計可能在之後下降，例如在您恢復工作階段後 MCP 伺服器重新連線期間。您不需要採取任何動作：當任務需要時，Claude 會載入這些工具中的每一個。

### 豁免伺服器不延遲

如果伺服器的工具應始終對 Claude 可見而無需搜尋步驟，請在該伺服器的設定中將 `alwaysLoad` 設定為 `true`。該伺服器的工具隨後會載入到上下文中，無論 `ENABLE_TOOL_SEARCH` 設定如何。對於 Claude 在每個回合都需要的少量工具使用此設定，因為每個預先載入的工具會消耗原本可用於您的對話的上下文。

以下 `.mcp.json` 項目豁免一個 HTTP 伺服器，同時保持其他伺服器延遲：

```json theme={null}
{
  "mcpServers": {
    "core-tools": {
      "type": "http",
      "url": "https://mcp.example.com/mcp",
      "alwaysLoad": true
    }
  }
}
```

`alwaysLoad` 欄位在所有伺服器類型上都可用。

設定 `alwaysLoad: true` 也會使啟動等待伺服器的工具，上限為標準 5 秒連線逾時，因為它們必須在建立第一個提示詞時存在。具有有效 [`cached` 項目](#server-status-detail)的遠端伺服器從快取提供其工具而無需連線，因此它不會延遲啟動。其他伺服器預設在背景連線；設定 [`MCP_CONNECTION_NONBLOCKING=0`](https://code.claude.com/docs/zh-TW/env-vars) 也使啟動等待它們。

### 延遲伺服器的工具

若要讓伺服器的所有工具都透過工具搜尋載入，請在 MCP 設定中該伺服器的項目裡設定 `"alwaysLoad": false`。這包括伺服器作者已[標記為預先載入](#per-tool-alwaysload)的工具。如果您省略 `alwaysLoad`，這些被標記的工具會預先載入。需要 Claude Code v2.1.287 或更新版本。

## 使用 MCP 提示作為命令

MCP 伺服器可以公開提示，這些提示在 Claude Code 中成為可用的命令。

來自名為 `anthropic-skills` 的伺服器的提示不會出現，因為 Claude Code [保留該名稱](https://code.claude.com/docs/zh-TW/skills.md#names-reserved-for-synced-skills)用於從 claude.ai 同步的技能。伺服器的工具仍然有效。在您的 MCP 設定中重新命名伺服器以列出其提示。

### 執行 MCP 提示

**1. 探索可用的提示**

輸入 `/` 以查看您可用的命令，包括來自 MCP 伺服器的命令。Claude Code 將每個 MCP 提示列為 `/servername:promptname (MCP)`。輸入 `/mcp__servername__promptname` 也會執行它。

**2. 執行沒有引數的提示**

```text wrap theme={null}
/mcp__github__list_prs
```

**3. 執行帶有引數的提示**

許多提示接受引數。在命令後以空格分隔的方式傳遞它們。Claude Code 在空白處分割引數，因此每個引數是單一令牌：

```text wrap theme={null}
/mcp__github__pr_review 456
```

```text wrap theme={null}
/mcp__jira__create_issue login-bug high
```

> [!TIP]
>
> 提示：
>
> * MCP 提示從連接的伺服器動態探索
> * 引數根據提示的定義參數進行解析
> * 提示結果直接注入到對話中
> * 在 `/mcp__servername__promptname` 形式中，Claude Code 將伺服器名稱中 `A-Z`、`a-z`、`0-9`、`_` 和 `-` 之外的任何字元替換為 `_`，並使用伺服器聲明的提示名稱

## Managed MCP 設定

對於需要集中控制使用者可以連接哪些 MCP 伺服器的組織，請參閱 [Managed MCP 設定](https://code.claude.com/docs/zh-TW/managed-mcp.md)。它涵蓋使用 `managed-mcp.json` 部署固定伺服器集、使用 `managedMcpServers` 為每個使用者提供伺服器、使用 `allowedMcpServers` 和 `deniedMcpServers` 限制伺服器，以及當伺服器被阻止時使用者看到的內容。

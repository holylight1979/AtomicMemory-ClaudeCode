<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/mcp-quickstart | lastmod: 2026-10-28 | section: Build with Claude Code / MCP -->
> 來源：https://code.claude.com/docs/zh-TW/mcp-quickstart（官方 zh-TW，lastmod 2026-10-28）｜分類：Build with Claude Code › MCP｜EN 摘要：Add an MCP server to Claude Code, verify the connection, and find the configuration on disk.

# 連接到 MCP 伺服器

> 將 MCP 伺服器新增至 Claude Code、驗證連接，並在磁碟上找到設定。

[Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) 讓 Claude Code 使用超越其內建工具集的工具，例如搜尋問題追蹤器、查詢資料庫或控制網頁瀏覽器。這些工具來自 MCP 伺服器，可在您的機器上執行或作為託管服務運行。

本指南將逐步引導您透過 Claude Code CLI 端對端連接一個 MCP 伺服器。完成後，您將擁有一個已連接且正在回應的伺服器、知道其設定在磁碟上的位置，以及知道如何修復最常見的連接錯誤。

> [!NOTE]
>
> 您也可以從其他介面新增 MCP 伺服器，包括桌面應用程式、VS Code 和網頁版。請參閱[從其他介面連接](#connect-from-other-surfaces)。

如需在 Claude Code 中連接和設定 MCP 伺服器的所有方式，請參閱 [MCP 參考](https://code.claude.com/docs/zh-TW/mcp.md)。

## 開始之前

確保您擁有：

* [已安裝](https://code.claude.com/docs/zh-TW/quickstart.md)並驗證 Claude Code
* 在專案目錄中開啟的終端機。任何目錄都可以，包括空目錄。

## 新增並驗證伺服器

下面的範例連接到 [Claude Code 文件 MCP 伺服器](https://code.claude.com/docs/mcp)，這是一個託管伺服器，具有對 Claude Code 文件的全文搜尋功能。它不需要驗證或任何特殊設定，因此它非常適合作為測試設定流程的第一個伺服器。

步驟對任何伺服器都相同：新增它、檢查連接狀態，然後在工作階段中使用它，最後可選擇清理步驟。某些伺服器會新增一個步驟，例如瀏覽器登入，如 [其他 MCP 伺服器範例](#additional-mcp-server-examples) 所示。如需更多伺服器連接，請瀏覽 [Anthropic 目錄](https://code.claude.com/docs/zh-TW/mcp.md#find-and-build-mcp-servers)。

**1. 新增 MCP 伺服器**

向 Claude Code 註冊伺服器。在您的終端機中執行此命令，而不是在 `claude` 工作階段內：您在啟動對話之前設定伺服器。

```bash theme={null}
claude mcp add --transport http claude-code-docs https://code.claude.com/docs/mcp
```

命令的各部分：

* `claude mcp add`：向 Claude Code 註冊伺服器。
* `--transport http`：伺服器託管在 URL 上，而不是作為本機程序執行。
* `claude-code-docs`：您自己建立的名稱。將同一伺服器稱為 `docs` 會完全相同。Claude Code 使用您選擇的任何名稱在 Claude 的輸出中標記伺服器的工具，並在 `claude mcp remove` 等命令中引用伺服器。
* `https://code.claude.com/docs/mcp`：伺服器託管的 URL。

該命令列印確認訊息，如 `Added HTTP MCP server claude-code-docs with URL: https://code.claude.com/docs/mcp to local config`，後面跟著 `File modified:` 行，顯示它寫入的設定檔。`local config` 部分表示伺服器已向您註冊，在此專案中：如果您在不同的專案中啟動 Claude Code，此伺服器在那裡不活躍。若要為所有專案註冊一次伺服器，請在使用者範圍新增它，詳見[變更伺服器範圍](#change-server-scope)。

**2. 檢查連接狀態**

確認伺服器出現在您的伺服器清單中並檢查其狀態：

```bash theme={null}
claude mcp list
```

伺服器出現時帶有狀態指示器：

| 狀態 | 含義 |
| :- | :- |
| `✔ Connected` | 準備就緒。這是您應該為 `claude-code-docs` 看到的 |
| `! Connected · tools fetch failed` | 伺服器已連接但無法列出其工具。執行 `claude mcp get <name>` 以取得錯誤詳細資訊 |
| `! Needs authentication` | 伺服器可到達但需要瀏覽器登入，或使用 `--header` 傳遞的令牌。請參閱[連接需要登入的伺服器](#connect-a-server-that-requires-sign-in) |
| `✘ Failed to connect` | 伺服器未回應。請參閱[疑難排解](#troubleshooting) |
| `✘ Connection error` | 連接嘗試拋出錯誤。請參閱[疑難排解](#troubleshooting) |
| ``⏸ Pending approval (run `claude` to approve)`` | 您尚未批准的專案範圍伺服器。請參閱[直接編輯 .mcp.json](#edit-mcp-json-directly) |
| `⊘ Disabled for this project (re-enable via /mcp)` | 由專案的 `disabledMcpServers` 清單為此專案關閉的伺服器。請參閱[停用伺服器而不移除它](https://code.claude.com/docs/zh-TW/mcp.md#disable-a-server-without-removing-it) |
| `✘ Blocked by enterprise managed policy` | 您組織的某項原則封鎖了此伺服器，因此 Claude Code 不會連接。請詢問您的管理員是哪一項原則。請參閱[伺服器狀態](https://code.claude.com/docs/zh-TW/mcp.md#server-status) |

某些舊版 Windows 主控台，例如 Windows 10 上的預設主控台，不支援這些 Unicode 字形，並顯示 `√` 和 `×` 代替 `✔` 和 `✘`。

**3. 使用伺服器**

啟動工作階段並要求 Claude 按名稱使用新伺服器：

```bash theme={null}
claude
```

```text wrap theme={null}
Use the claude-code-docs server to look up what MCP_TIMEOUT does
```

> [!NOTE]
>
> 您通常不需要在提示中命名伺服器，因為 Claude 會自動選擇相關工具。在此命名它可保證演示透過新伺服器而不是另一個工具（例如網頁擷取）進行，該工具可能回答相同問題。

如果 Claude Code 在 Claude 第一次呼叫伺服器時要求許可，請批准它。Claude 輸出中的工具呼叫會標記伺服器名稱，這是您確認答案來自 MCP 伺服器而不是 Claude 內建知識的方式。

**4. 移除伺服器**

此步驟是可選的。當您完成實驗時，您可以移除伺服器：

```bash theme={null}
claude mcp remove claude-code-docs
```

該命令確認為 `Removed MCP server "claude-code-docs" from local config`，並顯示 `File modified:` 行，顯示它更新的檔案。

> [!NOTE]
>
> 每個已連接的伺服器在 [Claude 的內容視窗](https://code.claude.com/docs/zh-TW/how-claude-code-works.md#the-context-window)中佔用一些空間，因為其工具名稱和伺服器指令會載入到每個工作階段中。移除您不再使用的伺服器可保持該空間空閒。

## 伺服器的儲存位置

`claude mcp add` 命令將伺服器的詳細資訊寫入設定檔。預設情況下，它在 `local` 範圍註冊伺服器：僅限您私人使用，僅在目前專案中活躍。傳遞 `--scope user` 以為所有專案註冊一次，或傳遞 `--scope project` 以與隊友共享。[變更伺服器範圍](#change-server-scope)會逐步說明兩者。

> [!NOTE]
>
> `claude mcp add` 在每個 shell 中的工作方式相同，包括 PowerShell 和命令提示字元。在 `claude` 工作階段內，使用 `/mcp` 命令檢查和管理您已新增的伺服器。

還有其他方式新增伺服器，每種都在本頁稍後涵蓋：

* [新增本機伺服器](#add-a-local-server)：在您的機器上執行程式，而不是連接到 URL。
* [直接編輯 `.mcp.json`](#edit-mcp-json-directly)：自己寫入 JSON 項目，而不是使用命令。
* [連接需要登入的伺服器](#connect-a-server-that-requires-sign-in)：新增需要瀏覽器登入才能使其工具工作的託管伺服器。

### 在磁碟上找到您的設定

`claude mcp add` 命令根據 `--scope` 旗標，將伺服器寫入三個範圍之一，儲存在兩個檔案中。您不需要直接編輯這些檔案，但知道它們的位置有助於除錯和版本控制。

| 範圍 | 檔案 | 可用於 |
| :- | :- | :- |
| `local` | `~/.claude.json`，在此專案的項目下 | 僅限您，僅限此專案。預設值 |
| `project` | 您的專案根目錄中的 `.mcp.json` | 複製專案的所有人 |
| `user` | `~/.claude.json`，在頂層 `mcpServers` 鍵下 | 僅限您，所有專案 |

在 Windows 上，`~/.claude.json` 解析為 `%USERPROFILE%\.claude.json`，通常為 `C:\Users\YourName\.claude.json`。如果您已設定 [`CLAUDE_CONFIG_DIR`](https://code.claude.com/docs/zh-TW/env-vars)，Claude Code 會改為從該目錄內讀取 `.claude.json`。

執行 `claude mcp get claude-code-docs` 以查看哪個範圍保存伺服器的定義。如需當同一伺服器在多個範圍中定義時範圍如何互動，請參閱 [MCP 安裝範圍](https://code.claude.com/docs/zh-TW/mcp.md#mcp-installation-scopes)。

## 變更伺服器範圍

伺服器的範圍在您新增時是固定的，因此變更範圍意味著移除項目並在新範圍重新新增。下面兩種情況都從移除第一個逐步說明中的本機項目開始，因此伺服器只有一個定義。如果您已在該逐步說明結束時移除它，請跳過此命令：

```bash theme={null}
claude mcp remove claude-code-docs --scope local
```

### 在所有專案中使用伺服器

在 `user` 範圍重新新增伺服器，使其在您開啟的每個專案中活躍，仍然僅限您私人使用：

```bash theme={null}
claude mcp add --scope user --transport http claude-code-docs https://code.claude.com/docs/mcp
```

### 與您的團隊共享伺服器

在 `project` 範圍重新新增伺服器，它寫入專案根目錄中的 `.mcp.json`：

```bash theme={null}
claude mcp add --scope project --transport http claude-code-docs https://code.claude.com/docs/mcp
```

將 `.mcp.json` 提交到版本控制。複製儲存庫並啟動 Claude Code 的隊友會看到批准伺服器的提示，然後它也會為他們連接。

## 其他 MCP 伺服器範例

第一個逐步說明使用了無需任何登入即可連接的託管伺服器。下面的範例涵蓋其他兩種常見形式，具有相同的新增、檢查、使用流程。

### 新增本機伺服器

本機 stdio 伺服器是 Claude Code 在您的機器上作為子程序啟動的程式，而不是它透過 URL 到達的服務。將其用於需要存取本機資源（例如瀏覽器、您的檔案系統或資料庫通訊端）的工具。

[Playwright MCP 伺服器](https://github.com/microsoft/playwright-mcp)是一個很好的嘗試：它為 Claude 提供可以導航、點擊和讀取的瀏覽器，並且不需要帳戶。它透過 `npx` 執行，因此需要 [Node.js](https://nodejs.org/en/download) 18 或更高版本。

**1. 新增 Playwright 伺服器**

向伺服器註冊 Claude Code 應執行以啟動它的命令：

```bash theme={null}
claude mcp add playwright -- npx -y @playwright/mcp@latest
```

此命令與託管範例在三個方面不同：

* 沒有 `--transport` 旗標，因為本機伺服器使用預設 `stdio` 傳輸。
* `--` 分隔符之後的所有內容都是 Claude Code 執行以啟動伺服器的命令。
* `-y` 告訴 `npx` 安裝套件而不提示。

該命令會列印確認訊息，例如 `Added stdio MCP server playwright with command: npx -y @playwright/mcp@latest to local config`，後面跟著 `File modified:` 行，顯示它寫入的設定檔。

Playwright 驅動您機器上已安裝的任何 Chrome。若要使用不同的瀏覽器，請在 `@playwright/mcp@latest` 之後附加 `--browser` 和瀏覽器名稱，例如 `--browser firefox`。

**2. 檢查連接**

`Added` 確認表示項目已儲存，而不是命令執行。檢查連接：

```bash theme={null}
claude mcp list
```

第一次檢查可能在 `npx` 下載套件時顯示 `✘ Failed to connect`，因此請稍候片刻並再次執行。下載完成後，狀態變為 `✔ Connected`。如果在重試幾次後仍顯示 `✘ Failed to connect`，請參閱[疑難排解](#troubleshooting)。

**3. 使用瀏覽器**

給 Claude 一個需要瀏覽器的任務：

```text wrap theme={null}
Use playwright to open https://example.com and tell me the page title
```

瀏覽器視窗開啟，以便您可以觀看它工作，Claude 輸出中的工具呼叫會標記伺服器名稱和動作，例如 `browser_navigate`。

嘗試將其指向您的本機開發伺服器，以檢查頁面在變更後是否仍呈現，或讓它逐步完成錯誤報告。

### 連接需要登入的伺服器

Sentry、Linear 和 Notion 等託管服務在 OAuth 後面執行其 MCP 伺服器：您新增伺服器的 URL，然後透過瀏覽器登入。

下面的步驟使用 Sentry 作為範例。若要連接不同的服務，請替換其 URL，您可以在 [Anthropic 目錄](https://code.claude.com/docs/zh-TW/mcp.md#find-and-build-mcp-servers)或服務的文件中找到。

**1. 新增伺服器**

`add` 命令與文件伺服器相同，使用 Sentry 的 URL：

```bash theme={null}
claude mcp add --transport http sentry https://mcp.sentry.dev/mcp
```

新增後，`claude mcp list` 顯示伺服器為 `! Needs authentication`。這是預期的：下一步完成登入。

**2. 在瀏覽器中驗證**

啟動 Claude Code 工作階段並開啟 MCP 面板：

```text wrap theme={null}
/mcp
```

從清單中選擇 `sentry`，按 Enter，然後選擇 `Authenticate`。您的瀏覽器開啟到 Sentry 的登入頁面。在那裡批准連接。

回到 Claude Code，伺服器的狀態變為已連接。如果登入失敗或瀏覽器未開啟，請參閱[疑難排解](#troubleshooting)。

**3. 使用伺服器**

詢問 Claude 需要該服務的內容，例如 `What Sentry projects do I have access to?`，並在其輸出中尋找標記為 `sentry` 伺服器名稱的工具呼叫。

使用靜態令牌而不是 OAuth 進行驗證的伺服器在新增時使用 `--header "Authorization: Bearer <token>"` 取得令牌。請參閱 [GitHub 範例](https://code.claude.com/docs/zh-TW/mcp.md#example-connect-to-github-for-code-reviews)以取得已完成的版本。

## 直接編輯 .mcp.json

[範圍表](#find-your-configuration-on-disk)中的每個檔案對伺服器項目使用相同的 JSON 格式。本節編輯 `.mcp.json`，即專案範圍檔案。它最值得手寫，因為它被簽入儲存庫，在那裡它也充當您團隊的設定即程式碼。

在您的專案根目錄中建立 `.mcp.json`。下面的範例定義本指南中的兩個伺服器，透過 HTTP 到達的託管文件伺服器和作為本機 `stdio` 程序的 Playwright 伺服器：

```json theme={null}
{
  "mcpServers": {
    "claude-code-docs": {
      "type": "http",
      "url": "https://code.claude.com/docs/mcp"
    },
    "playwright": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@playwright/mcp@latest"]
    }
  }
}
```

欄位因伺服器類型而異：

* 對於 HTTP 伺服器，`url` 是 Claude Code 連接到的端點。
* 對於 stdio 伺服器，`command` 和 `args` 是它執行的程式。

儲存檔案後，在專案中啟動新的 Claude Code 工作階段。Claude Code 在啟動時讀取 `.mcp.json`。

Claude Code 第一次看到專案範圍伺服器時，它會要求您批准它。提示存在是為了讓您複製的儲存庫無法在您同意的情況下在您的機器上啟動程序。批准提示，或如果您錯過了，執行 `/mcp` 稍後批准。

批准後，執行 `/mcp` 並檢查伺服器是否顯示為已連接。如果其中一個顯示錯誤，請參閱[疑難排解](#troubleshooting)。

## 從其他介面連接

本指南使用 `claude mcp` CLI 命令，但每個 Claude Code 介面都可以連接到 MCP 伺服器：

* **Claude Code 桌面應用程式**：透過[連接器 UI](https://code.claude.com/docs/zh-TW/desktop.md#connect-external-tools) 新增伺服器。
* **Claude Desktop 聊天應用程式**：與 Claude Code 不同的應用程式。若要將其 `claude_desktop_config.json` 中的伺服器複製到 CLI，請在 macOS 或 WSL 上執行 `claude mcp add-from-claude-desktop`。
* **VS Code**：請參閱[使用 MCP 連接到外部工具](https://code.claude.com/docs/zh-TW/vs-code.md#connect-to-external-tools-with-mcp)。
* **雲端工作階段**：在[專案](https://code.claude.com/docs/zh-TW/claude-projects.md#what-threads-pick-up-from-your-repositories)的對話串之外，將 `.mcp.json` 提交到您的儲存庫；載入一個儲存庫的工作階段會載入它。專案中的雲端對話串則會改用您的 claude.ai 連接器。請參閱[直接編輯 .mcp.json](#edit-mcp-json-directly) 和[您的設定中有哪些會保留](https://code.claude.com/docs/zh-TW/cloud-environments.md#what-carries-over-from-your-setup)。
* **Claude.ai**：您在 [claude.ai/customize/connectors](https://claude.ai/customize/connectors) 新增的連接器在您使用該帳戶登入時自動載入 CLI。請參閱[從 Claude.ai 使用 MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md#use-mcp-servers-from-claude-ai)。

## 疑難排解

如果伺服器未連接，請在工作階段內使用 `/mcp` 或從您的 shell 使用 `claude mcp list` 檢查其狀態，然後匹配下面的症狀。`/mcp` 面板也讓您無需離開工作階段即可重新連接或驗證。

> [accordion] /mcp 顯示 No MCP servers configured
>
> Claude Code 未找到目前目錄的任何伺服器。最常見的原因：
>
> * 您從不同的專案執行了 `claude mcp add`。本機範圍伺服器與您新增它們的專案相關聯：儲存庫根目錄，或如果您不在 git 儲存庫中，則為確切目錄。從您現在所在的專案重新新增伺服器，或使用 `--scope user` 新增它，使其不與專案相關聯。
> * 您在錯誤的路徑編輯了設定檔。正確的檔案是 `~/.claude.json` 和 `<project>/.mcp.json`。Claude Code 不讀取 `~/.claude/.mcp.json`、`~/.claude/config/mcp.json`、`~/.claude/mcp.json` 或 `%APPDATA%\Claude\mcp.json` 等路徑。對於使用者範圍伺服器，執行 `claude mcp add --scope user`，它會寫入 `~/.claude.json` 中的 `mcpServers` 鍵；對於專案範圍伺服器，編輯專案根目錄的 `.mcp.json`。
> * 您在 `.mcp.json` 中寫入了格式不正確的項目。Claude Code 會跳過該項目並仍然載入其他項目。從您的 shell 執行 `claude mcp list` 並尋找解析警告，它會命名有問題的欄位。

> [accordion] 狀態顯示 Failed to connect 或 Connection error
>
> 兩種狀態都表示伺服器未啟動或 URL 未回應。它們也可能出現在您在 `headers.Authorization` 中設定的 token 被 HTTP 伺服器拒絕的情況下；需要您未設定之 token 的伺服器會改為顯示 `! Needs authentication`，在[連接需要登入的伺服器](#connect-a-server-that-requires-sign-in)中涵蓋。
>
> 您的第一步取決於您看到的狀態：
>
> * `Failed to connect`：從狀態本身的失敗詳細資訊開始。`claude mcp list` 和 `claude mcp get <name>` 顯示 HTTP 狀態或錯誤代碼以及伺服器返回的任何錯誤文字，通常直接命名問題，例如缺少標頭或被拒絕的 token。在 v2.1.219 之前，`Failed to connect` 只顯示裸露狀態，您需要本節稍後的 curl 和命令檢查來找到原因。
> * `Connection error`：Claude Code 在任何版本上都不會將詳細資訊附加到此狀態，因此請直接進行本節稍後的 curl 和命令檢查。
>
> 如果詳細資訊指向憑證或 URL，也請檢查 `claude mcp list` 輸出中的警告。Claude Code 會標記具有隱藏的前導或尾隨空白的設定值，這是貼上 token 後驗證失敗的常見原因。
>
> 如果 HTTP 伺服器返回 `404 Not Found`，當您在 `/mcp` 中選擇伺服器時，Claude Code 會顯示 `MCP endpoint not found at <origin>. Check the URL in your MCP config.`。該訊息命名 URL 的來源，例如 `https://mcp.example.com`，不含其路徑，因此執行 `claude mcp get <name>` 以查看您設定的完整 URL。將其路徑與伺服器文件中記載的 MCP 端點路徑進行比較，然後執行 `claude mcp remove <name>` 並使用正確的 URL 重新新增。在 v2.1.219 之前，該訊息也包含 URL 的路徑，在 v2.1.191 之前，`404` 顯示通用的 `Error POSTing to endpoint` 訊息，不含 URL。
>
> 對於 HTTP 伺服器，確認 URL 可從您的機器到達：
>
> ```bash theme={null}
> curl -I https://mcp.sentry.dev/mcp
> ```
>
> 在 PowerShell 中，使用 `curl.exe` 而不是 `curl`，以便請求進入真實 curl 二進位檔而不是 `Invoke-WebRequest` 別名。
>
> 回應告訴您您有哪種問題：
>
> * `404` 或 `405`：伺服器已啟動。許多 MCP 端點僅回答 POST 請求，因此這仍然確認 URL 可從您的機器到達。
> * `401` 或 `403`：伺服器已啟動，您需要驗證。使用[連接需要登入的伺服器](#connect-a-server-that-requires-sign-in)中的瀏覽器登入，或對於接受 token 的伺服器（例如 GitHub 的），使用 `claude mcp add` 命令上的 `--header "Authorization: Bearer <token>"` 傳遞它。
> * 完全沒有回應：檢查 URL 和您的網路。
>
> 對於 stdio 伺服器，直接在您的終端機中執行設定的命令以查看基礎錯誤。對於本指南中的 Playwright 伺服器，執行：
>
> ```bash theme={null}
> npx -y @playwright/mcp@latest
> ```
>
> 接下來發生的情況告訴您問題在哪裡：
>
> * 命令啟動並等待輸入：伺服器本身有效。
>
>   執行 `claude mcp get <name>` 並確認那裡顯示的命令與您剛執行的相符。如果顯示的命令與您輸入的不同，您可能省略了伺服器命令前的 `--` 分隔符。移除伺服器並使用 `--` 重新新增。如果您手寫了 `.mcp.json`，檢查其語法和位置。在 v2.1.285 之前，`claude mcp get` 對於保存時沒有 `type` 欄位的 stdio 項目（例如手寫的 `.mcp.json` 項目）不列印 `Command` 行。在這些版本上，執行 `claude mcp list` 代替，它無論如何都會列印命令行。
> * 命令錯誤：訊息命名缺少的內容，例如 Node.js 或瀏覽器。

> [accordion] 連接在啟動時逾時
>
> 伺服器花費的時間超過預設 30 秒啟動逾時。stdio 伺服器的第一次執行在 `npx` 下載套件時可能很慢。使用 [`MCP_TIMEOUT`](https://code.claude.com/docs/zh-TW/env-vars) 環境變數（以毫秒為單位）增加限制：
>
> ```bash theme={null}
> MCP_TIMEOUT=60000 claude
> ```
>
> 在 PowerShell 中，在同一行上的命令前設定變數：
>
> ```powershell theme={null}
> $env:MCP_TIMEOUT = "60000"; claude
> ```
>
> 在 v2.1.299 之前，部分連至已啟動之 HTTP 伺服器的連接會在啟動時逾時，不論 `MCP_TIMEOUT` 的值為何。如果您使用的是這些版本之一，且已啟動的 HTTP 伺服器在您提高限制後仍然逾時，請[更新 Claude Code](https://code.claude.com/docs/zh-TW/setup.md#update-claude-code)。

> [accordion] 伺服器已存在
>
> 您已在同一範圍新增了具有該名稱的伺服器。要麼先移除現有項目，要麼選擇不同的名稱：
>
> ```bash theme={null}
> claude mcp remove claude-code-docs
> ```
>
> 如果名稱存在於多個範圍，`remove` 報告 `exists in multiple scopes`。傳遞 `--scope` 以選擇要刪除的副本，例如 `claude mcp remove claude-code-docs --scope local`。

> [accordion] 伺服器連接但沒有工具出現
>
> 在工作階段內執行 `/mcp` 並選擇伺服器以查看其工具清單。如果清單為空，伺服器已啟動但未註冊任何工具，這通常意味著它缺少必需的環境變數，例如 API 金鑰。
>
> 使用 `claude mcp add` 上的 `--env KEY=value` 傳遞變數，或在伺服器的 `.mcp.json` 項目的 `env` 欄位中傳遞。伺服器的文件列出它需要的變數。
>
> 在 v2.1.302 之前，對於使用[協定修訂版 2026-07-28](https://code.claude.com/docs/zh-TW/mcp.md#mcp-client-runtimes) 且在回覆中省略 `resultType`、`ttlMs` 或 `cacheScope` 的伺服器，`/mcp` 會顯示狀態 `tools fetch failed`。如果您使用的是這些版本之一，且伺服器顯示該狀態，請[更新 Claude Code](https://code.claude.com/docs/zh-TW/setup.md#update-claude-code)。

> [accordion] .mcp.json 的變更不生效
>
> Claude Code 在工作階段啟動時讀取 `.mcp.json`。編輯檔案後退出並重新啟動工作階段。
>
> 如果您的伺服器仍未出現，執行 `claude mcp list` 並尋找解析警告。Claude Code 跳過格式不正確的項目並在那裡顯示有問題的欄位。
>
> 如果您之前在提示時拒絕了伺服器，重設專案核准：
>
> ```bash theme={null}
> claude mcp reset-project-choices
> ```

> [accordion] OAuth 登入失敗或瀏覽器未開啟
>
> 執行 `/mcp`，選擇伺服器，然後再次選擇 `Authenticate`。如果瀏覽器未自動開啟，複製終端機中顯示的 URL 並手動開啟。請參閱[使用遠端 MCP 伺服器驗證](https://code.claude.com/docs/zh-TW/mcp.md#authenticate-with-remote-mcp-servers)以取得固定回呼連接埠和預先設定的憑證。

## 後續步驟

連接一個伺服器後，探索 MCP 啟用的其餘功能：

* [尋找更多 MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md#find-and-build-mcp-servers)在 Anthropic 目錄中
* [與您的團隊共享伺服器](https://code.claude.com/docs/zh-TW/mcp.md#mcp-installation-scopes)使用安裝範圍
* [為組織管理 MCP 存取](https://code.claude.com/docs/zh-TW/managed-mcp.md)使用受管設定和原則控制
* [在提示中參考 MCP 資源](https://code.claude.com/docs/zh-TW/mcp.md#use-mcp-resources)使用 @ 提及
* [從 `/` 功能表執行 MCP 提示作為命令](https://code.claude.com/docs/zh-TW/mcp#use-mcp-prompts-as-commands)
* [使用 MCP SDK 建立您自己的伺服器](https://modelcontextprotocol.io/quickstart/server)

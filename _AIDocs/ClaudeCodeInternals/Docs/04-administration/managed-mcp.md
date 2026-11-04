<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/managed-mcp | lastmod: 2026-10-28 | section: Administration / Setup and access -->
> 來源：https://code.claude.com/docs/zh-TW/managed-mcp（官方 zh-TW，lastmod 2026-10-28）｜分類：Administration › Setup and access｜EN 摘要：Restrict which MCP servers users can add or connect to, or provide servers to every user, with managed configuration files, managed settings, allowlists, and denylists.

# 控制組織的 MCP 伺服器存取

> 使用受管設定檔、受管設定、允許清單和拒絕清單，限制使用者可以新增或連線的 MCP 伺服器，或為每位使用者提供伺服器。

根據預設，任何執行 Claude Code 的人都可以連線他們選擇的任何 [MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md)。Anthropic 在將連接器新增至 [Anthropic 目錄](https://claude.ai/directory)之前，會根據其[列表標準](https://claude.com/docs/connectors/building/review-criteria)審查連接器，但不會對任何 MCP 伺服器進行安全稽核或管理。作為管理員，您可以限制在組織中執行的伺服器，從部署固定的已核准集合到完全停用 MCP，並且您可以為每位使用者提供伺服器。

這些限制涵蓋 Claude Code 自行載入的伺服器，包括它從 claude.ai 擷取的連接器。桌面應用程式傳遞給其本機和 SSH 工作階段的連接器會以程序內方式到達，並由您的 claude.ai 組織設定進行管理；[連接器如何到達 Claude Code](https://code.claude.com/docs/zh-TW/mcp.md#how-connectors-reach-claude-code) 顯示哪些控制項適用於每種工作階段（包括雲端工作階段）中的連接器。

本頁涵蓋如何：

* [選擇符合您需要的控制程度的模式](#choose-a-pattern)
* [使用 `managed-mcp.json` 部署固定伺服器集合](#exclusive-control-with-managed-mcp-json)，包括如何[完全停用 MCP](#disable-mcp-entirely)
* [透過受管設定提供伺服器](#provide-servers-through-managed-settings)，同時使用者保留自己的伺服器
* [使用允許清單和拒絕清單控制伺服器](#policy-based-control-with-allowlists-and-denylists)
* [告知使用者限制阻止伺服器時的預期情況](#how-restrictions-appear-to-users)
* [監控組織實際使用的伺服器](#monitor-mcp-usage)

> [!NOTE]
>
> [安全性](https://code.claude.com/docs/zh-TW/security.md)頁面涵蓋 MCP 威脅模型以及如何在核准伺服器前進行評估。[決定要強制執行的項目](https://code.claude.com/docs/zh-TW/admin-setup.md#decide-what-to-enforce)涵蓋 MCP 限制以及其他管理控制項。

## 選擇一個模式

Claude Code 支援一系列限制級別。每個模式使用以下一個或多個機制：`managed-mcp.json` 用於部署固定集合、`managedMcpServers` 受管設定用於提供伺服器以及使用者新增的伺服器，以及 `allowedMcpServers`/`deniedMcpServers` 用於篩選使用者設定的內容。

| 模式 | 功能 | 設定 |
| :- | :- | :- |
| **停用 MCP** | 沒有伺服器載入，除了 [在獨佔控制下載入的少數伺服器](#exclusive-control-with-managed-mcp-json) | `managed-mcp.json` 搭配空白伺服器對應 |
| **固定部署** | 每個使用者都取得相同的伺服器，無法新增其他伺服器 | `managed-mcp.json` 搭配您想要的伺服器 |
| **提供的伺服器** | 每個使用者都取得您列出的遠端伺服器，並保留他們自己的伺服器 | 受管設定中的 `managedMcpServers` |
| **已核准的目錄** | 發佈已核准伺服器的清單；使用者新增他們想要的伺服器，其他任何伺服器都會被封鎖 | `allowedMcpServers` + `allowManagedMcpServersOnly: true` |
| **僅限外掛程式伺服器** | 使用者無法透過 `~/.claude.json` 或 `.mcp.json` 新增伺服器；[skills 目錄外掛](https://code.claude.com/docs/zh-TW/plugins/loading.md#skills-directory-plugins-blocked-by-managed-settings) 不再以外掛形式載入，而來自其他外掛的伺服器仍會載入 | [`strictPluginOnlyCustomization`](https://code.claude.com/docs/zh-TW/settings-reference#strictpluginonlycustomization) 搭配清單中的 `mcp` |
| **軟性允許清單** | 強制執行允許清單，使用者可以在他們自己的設定中擴展 | `allowedMcpServers` 不搭配 `allowManagedMcpServersOnly` |
| **僅限拒絕清單** | 封鎖已知的不良伺服器，允許其他所有伺服器 | `deniedMcpServers` |
| **無限制** | 使用者新增任何伺服器 | 不部署任何受管 MCP 設定 |

> [!NOTE]
>
> Claude Code 沒有內建的 MCP 伺服器登錄，使用者可以從中瀏覽和安裝。對於已核准的目錄模式，請在使用者會找到的地方（例如內部 wiki）分享已核准的清單及其 `claude mcp add` 命令，或透過 [受管外掛程式市集](https://code.claude.com/docs/zh-TW/plugins/org.md#restrict-what-users-can-install) 將伺服器分發為外掛程式，以便使用者可以從 `/plugin` 瀏覽和安裝它們。

## 使用 managed-mcp.json 進行獨佔控制

當您部署 `managed-mcp.json` 檔案時，Claude Code 只會載入以下伺服器：

* 該檔案定義的伺服器
* 您[透過 `managedMcpServers` 提供的伺服器](#provide-servers-through-managed-settings)
* 啟動工作階段的應用程式註冊的同處理程序伺服器，例如 VS Code 擴充功能自己的伺服器或[桌面應用程式提供的連接器](https://code.claude.com/docs/zh-TW/mcp.md#how-connectors-reach-claude-code)
* 內建的[Chrome 中的 Claude](https://code.claude.com/docs/zh-TW/chrome.md) 伺服器，如果您[允許它與受管集合並存](#allow-claude-in-chrome-alongside-the-managed-set)

使用者無法新增、修改或使用任何其他 MCP 伺服器，包括外掛程式提供的伺服器和透過 [`--mcp-config` CLI 旗標](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags)傳遞的伺服器。該檔案也會抑制 Claude Code 自行擷取的 claude.ai 連接器，除非您[允許它們與受管集合並存](#allow-claude-ai-connectors-alongside-the-managed-set)。

### 部署 managed-mcp.json

`managed-mcp.json` 是一個獨立檔案，因此無法透過[伺服器管理的設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)傳遞。若要透過受管設定傳遞伺服器而不進行獨佔控制，請改用 [`managedMcpServers`](#provide-servers-through-managed-settings)。

任何可以寫入具有管理員權限的系統路徑的程序都可以部署該檔案。在整個機隊中，這通常是透過裝置管理工具進行，例如 macOS 上的 Jamf 或設定檔、Windows 上的群組原則或 Intune，或您在 Linux 上選擇的機隊管理工具。Claude Code 會在以下其中一個路徑中尋找該檔案：

| 平台 | 路徑 |
| :- | :- |
| macOS | `/Library/Application Support/ClaudeCode/managed-mcp.json` |
| Linux 和 WSL | `/etc/claude-code/managed-mcp.json` |
| Windows | `C:\Program Files\ClaudeCode\managed-mcp.json` |

該檔案使用與專案 [`.mcp.json`](https://code.claude.com/docs/zh-TW/mcp#project-scope) 檔案相同的格式：

```json theme={null}
{
  "mcpServers": {
    "github": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp/"
    },
    "sentry": {
      "type": "http",
      "url": "https://mcp.sentry.dev/mcp"
    },
    "company-internal": {
      "type": "stdio",
      "command": "/usr/local/bin/company-mcp-server",
      "args": ["--config", "/etc/company/mcp-config.json"],
      "env": {
        "COMPANY_API_URL": "https://internal.example.com"
      }
    }
  }
}
```

### 使用個別使用者認證進行驗證

機器上的任何使用者都可以讀取此檔案，因此請勿在 `env` 區塊中儲存 API 金鑰或其他認證。改用以下其中一種方式傳遞個別使用者認證：

* [從每個使用者的環境讀取機密的 `${VAR}` 擴展](https://code.claude.com/docs/zh-TW/mcp#environment-variable-expansion-in-mcp-json)。
* [OAuth 或個別使用者標頭](https://code.claude.com/docs/zh-TW/mcp.md#authenticate-with-remote-mcp-servers)，以便每個使用者以自己的身份進行驗證。
* [`headersHelper`](https://code.claude.com/docs/zh-TW/mcp#use-dynamic-headers-for-custom-authentication) 在連線時產生認證。

### 透過 `--mcp-config` 或 `--strict-mcp-config` 傳遞的伺服器

當工作階段在部署 `managed-mcp.json` 時透過 `--mcp-config` 接收伺服器時，使用者看到的內容在工作站和雲端工作階段之間有所不同：

* 在工作站上，Claude Code 在啟動時以 `You cannot dynamically configure MCP servers when an enterprise MCP config is present` 結束。
* 在部署該檔案的主機上的[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)中，例如[自託管執行器](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#mcp-servers)，Claude Code 僅使用受管伺服器啟動，並跳過 claude.ai 連接器和雲端主機透過 `--mcp-config` 傳遞的其他伺服器。工作階段中沒有任何內容告訴使用者哪些伺服器被遺漏。Claude Code 在其 stderr 上的警告中命名它們，自託管執行器會在 `debug` 日誌級別記錄。

`--strict-mcp-config` 旗標要求取代受管集合。如果使用者在部署此類檔案時傳遞它，Claude Code 在工作站和雲端工作階段上都會在啟動時結束。

### 允許清單和拒絕清單如何應用於受管集合

拒絕清單可以進一步篩選 `managed-mcp.json` 中的伺服器：

* `deniedMcpServers` 也適用於受管伺服器，因此與項目相符的受管伺服器將不會載入。
* 使用者自己的 `deniedMcpServers` 會從其設定中合併，因此使用者可以為自己封鎖受管伺服器。

`managed-mcp.json` 中的伺服器不需要 `allowedMcpServers` 項目，但有一個例外：當伺服器在 `env` 以外使用 [`${VAR}` 擴展](https://code.claude.com/docs/zh-TW/mcp#environment-variable-expansion-in-mcp-json)時，Claude Code 會檢查該伺服器是否符合允許清單。在 v2.1.305 之前，Claude Code 也會檢查僅在 `env` 中使用 `${VAR}` 擴展的伺服器；而在 v2.1.259 之前，只要設定了允許清單，就會檢查每個受管伺服器。請參閱[伺服器如何被評估](#how-a-server-is-evaluated)以了解哪些欄位觸發 `${VAR}` 檢查和完整的檢查順序。

如果您使用 `allowedMcpServers` 防止您的某些 `managed-mcp.json` 伺服器載入，請在使用者升級之前，為它們新增 `deniedMcpServers` 項目，或為每個群組部署單獨的 `managed-mcp.json`。除非這些伺服器在 `env` 以外使用 `${VAR}` 擴展，否則它們會在每個使用者首次啟動不再檢查它們的版本時開始載入，沒有任何提示或通知。

### 驗證設定

若要確認檔案生效，請在受管機器上執行兩項檢查：

1. `claude mcp list` 只顯示 `managed-mcp.json` 中的伺服器，加上您透過 `managedMcpServers` 提供的任何伺服器。兩個其他結果表示出現問題：
   * 如果使用者自己的伺服器仍然出現，Claude Code 未讀取該檔案，因此請檢查其路徑和其父目錄的權限。
   * 如果檔案的伺服器未出現，且 `MCP config diagnostics` 部分將企業設定標記為無法解析失敗，Claude Code 無法讀取或解析該檔案。修正該部分命名的錯誤，然後讓使用者重新啟動 Claude Code。
2. `claude mcp add --transport http test https://example.com/mcp` 失敗，並顯示 `Cannot add MCP server: enterprise MCP configuration is active and has exclusive control over MCP servers`。URL 不需要是真實伺服器，因為原則檢查會在聯絡任何內容之前拒絕該命令。

### 完全停用 MCP

部署包含空伺服器對應的 `managed-mcp.json` 以封鎖除[在獨佔控制下載入的伺服器](#exclusive-control-with-managed-mcp-json)之外的每個 MCP 伺服器：

```json theme={null}
{
  "mcpServers": {}
}
```

`claude mcp add` 失敗，並顯示上述企業原則錯誤。使用者之前設定的伺服器在下次啟動工作階段時停止載入，沒有警告說明原則是原因。您透過 `managedMcpServers` 提供的伺服器和您允許與受管集合並存的任何其他內容仍在空對應下載入，因此請保持那些金鑰未設定以完全停用 MCP。

### 允許 claude.ai 連接器與受管集合並存

根據預設，部署 `managed-mcp.json` 會抑制 Claude Code 自行擷取的 [claude.ai 連接器](https://code.claude.com/docs/zh-TW/mcp.md#use-mcp-servers-from-claude-ai)，包括管理員在 claude.ai 管理主控台中為組織設定的連接器。若要將這些連接器與 `managed-mcp.json` 中的伺服器一起載入，請在[受管設定來源](https://code.claude.com/docs/zh-TW/admin-setup.md#decide-how-settings-reach-devices)中設定 `"allowAllClaudeAiMcps": true`。

啟用該設定後，Claude Code 會載入如果未部署 `managed-mcp.json` 時會載入的相同 claude.ai 連接器。[允許清單和拒絕清單](#policy-based-control-with-allowlists-and-denylists)仍適用於這些連接器，因此您可以使用 `deniedMcpServers` 封鎖特定連接器。該設定僅影響 Claude Code 自行擷取的 claude.ai 連接器；外掛程式提供的伺服器保持被抑制。

雲端工作階段和桌面應用程式的本機和 SSH 工作階段以另一種方式接收連接器，如[連接器如何到達 Claude Code](https://code.claude.com/docs/zh-TW/mcp.md#how-connectors-reach-claude-code) 中所述。執行雲端工作階段的主機上的 `managed-mcp.json`（例如[自託管執行器主機](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#mcp-servers)）會抑制該工作階段的連接器，無論您是否設定 `allowAllClaudeAiMcps`。沒有 `managed-mcp.json` 到達桌面應用程式傳遞給其本機和 SSH 工作階段的連接器。

Claude Code 只從管理員控制的原則層級讀取 `allowAllClaudeAiMcps`：伺服器管理的設定、MDM 部署的 plist 或 HKLM 登錄機碼，或系統 `managed-settings.json` 檔案。將其放在使用者或專案設定中無效，因此使用者無法重新啟用獨佔控制抑制的連接器。

### 允許 Claude in Chrome 與受管集合並存

根據預設，當您部署 `managed-mcp.json` 時，Claude Code 會在終端機工作階段中封鎖內建的 [Claude in Chrome](https://code.claude.com/docs/zh-TW/chrome.md) 伺服器。使用者不會收到[擴充功能安裝提示](https://code.claude.com/docs/zh-TW/chrome.md#install-the-extension-when-claude-asks)，且[預設啟用 Chrome](https://code.claude.com/docs/zh-TW/chrome.md#enable-chrome-by-default) 的使用者啟動的工作階段會在沒有 Chrome 的情況下啟動，並且不會列印任何警告。如果原本可以執行 Claude in Chrome 的使用者啟動 `claude --chrome`，Claude Code 在啟動時會以命名 `allowClaudeInChromeWithManagedMcp` 設定的錯誤結束。

若要讓使用者在受管集合之外同時執行 Claude in Chrome，請在裝置自己的受管設定中設定 `"allowClaudeInChromeWithManagedMcp": true`。將其放在 MDM 部署的 plist、HKLM 登錄機碼或系統 `managed-settings.json` 檔案中，以 Claude Code 在該裝置上[選擇](https://code.claude.com/docs/zh-TW/managed-settings.md#precedence-within-the-managed-tier)的那一個為準。需要 Claude Code v2.1.282 或更新版本。即使[伺服器管理的設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)傳遞您的其餘原則，Claude Code 也只會從這些裝置來源讀取該設定。即使啟用該設定，針對 `claude-in-chrome` 的 [`deniedMcpServers`](#policy-based-control-with-allowlists-and-denylists) 項目仍會封鎖該伺服器。

## 透過受管設定提供伺服器

若要在不獨佔控制 MCP 的情況下為每位使用者提供一組遠端 MCP 伺服器，請在[受管設定來源](https://code.claude.com/docs/zh-TW/admin-setup.md#decide-how-settings-reach-devices)中的 `managedMcpServers` 下列出它們：伺服器受管設定、[Claude 應用程式閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#what-goes-in-cli)原則、MDM 設定檔或登錄原則，或 `managed-settings.json`。使用者保留他們自己新增的伺服器，並額外接收您的伺服器。需要 Claude Code v2.1.259 或更新版本。較早的用戶端會忽略此金鑰。

該值是一個以伺服器名稱為鍵的物件。每個項目的形狀與專案 [`.mcp.json`](https://code.claude.com/docs/zh-TW/mcp#project-scope) 檔案中的 HTTP 或 SSE 伺服器相同，包括[使用遠端 MCP 伺服器進行驗證](https://code.claude.com/docs/zh-TW/mcp.md#authenticate-with-remote-mcp-servers)中描述的選用 `headers` 和 `oauth` 成員。此範例提供一個搜尋伺服器，每位使用者可使用 OAuth 登入，以及一個記錄伺服器，會傳送您的組織簽發的標頭：

```json theme={null}
{
  "managedMcpServers": {
    "search": {
      "type": "http",
      "url": "https://search.example.com/mcp"
    },
    "records": {
      "type": "http",
      "url": "https://records.example.com/mcp",
      "headers": {
        "X-Records-Key": "key-issued-for-all-claude-code-users"
      }
    }
  }
}
```

任何能夠讀取機器上受管設定的人（包括使用者）都可以讀取您在此設定的標頭值。使用為整個受眾簽發的認證，或省略 `headers` 並讓每位使用者使用 OAuth 登入。

### 項目可以包含的內容

Claude Code 只在通過以下每項檢查時才會載入項目。它會捨棄未通過檢查的項目，記錄您可以使用 `/status` 讀取的通知，並仍然載入其他項目：

* `type` 是 `http` 或 `sse`。如同在 `.mcp.json` 中，`streamable-http` 被接受為 `http` 的別名。
* `url` 是 `https://` URL。Claude Code 拒絕純 `http://` URL，包括指向 `localhost` 的 URL。
* 該項目沒有 `command`、`args`、`env` 或 `headersHelper` 成員，因此受管設定文件永遠不會命名要在使用者機器上執行的程式。
* 沒有值包含 `${VAR}` 參考。Claude Code 不會在這些項目中展開環境變數，因此請寫入字面值。
* 伺服器名稱只包含字母、數字、連字號和底線，且沒有金鑰或值包含控制或隱形格式字元。

Claude Desktop 有一個同名的受管設定，其值是不同項目形狀的陣列，因此不要將一個複製到另一個。Claude Code 不接受陣列形式，而是記錄通知而不是載入它。

Claude 應用程式閘道在啟動時執行相同的檢查；請參閱[原則中的 MCP 伺服器](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#mcp-servers-in-a-policy)。

### 提供的伺服器如何載入

這些規則決定當提供的伺服器與另一個伺服器定義或此頁面上的另一個設定重疊時會載入什麼：

* 提供的伺服器優先於本機、專案或使用者範圍中同名的伺服器，以及優先於指向相同 URL 的外掛程式伺服器或 claude.ai 連接器。
* 如果您也部署 `managed-mcp.json`，Claude Code 會一起載入其伺服器和提供的伺服器，當兩者都定義名稱時，檔案的項目優先。
* 當 [`strictPluginOnlyCustomization`](https://code.claude.com/docs/zh-TW/settings-reference#strictpluginonlycustomization) 鎖定 `mcp` 表面時，提供的伺服器會繼續載入。
* `deniedMcpServers` 適用於提供的伺服器，包括來自使用者自己設定的項目，因此使用者可以為自己封鎖一個。提供的伺服器不需要 `allowedMcpServers` 項目。

當您也沒有部署 `managed-mcp.json` 時，每次執行的旗標保留其含義：

* 使用者使用 `--mcp-config` 以相同名稱傳遞的伺服器會取代該次執行的提供伺服器，並根據 `allowedMcpServers` 進行檢查。
* `--strict-mcp-config` 將提供的伺服器與所有其他已設定的伺服器一起排除。

部署 `managed-mcp.json` 後，兩個旗標的行為如[使用 managed-mcp.json 的獨佔控制](#exclusive-control-with-managed-mcp-json)所述。

### 使用者可以看到和更改的內容

使用者無法編輯或移除提供的伺服器：

* `claude mcp remove` 報告伺服器由組織提供。
* 當您也沒有部署 `managed-mcp.json` 時，使用者在相同名稱下新增的項目會被儲存但在您的項目存在時不會被使用。
* 使用者仍然可以在 [`/mcp`](https://code.claude.com/docs/zh-TW/mcp#disable-a-server-without-removing-it) 中為自己關閉提供的伺服器，該頁面在**受管 MCPs** 下列出提供的伺服器。

`claude mcp get` 和 `/mcp` 將提供的伺服器的 URL 顯示為其主機名稱，例如 `https://mcp.example.com/…`，而 `claude mcp get` 顯示其標頭名稱而不顯示其值。

### `managedMcpServers` 適用的位置

Claude Code 從它在[Claude Code 如何組合受管來源](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)下選擇的受管來源讀取 `managedMcpServers`。當該來源將 [`managedSourcesBehavior`](https://code.claude.com/docs/zh-TW/settings-reference#managedsourcesbehavior) 設定為 `"merge"` 時，Claude Code 改為提供來自每個管理員來源的伺服器，當兩個來源定義相同名稱時，較高排名來源的項目整體適用。它永遠不會從使用者可寫的 HKCU 登錄、從[嵌入主機供應的父設定](https://code.claude.com/docs/zh-TW/managed-settings.md#parent-settings-from-embedding-hosts)或從使用者、專案或本機設定檔案讀取金鑰，它會在那裡以警告方式捨棄金鑰。

Claude Code 不會在第三方部署中的 Claude Desktop 應用程式的 Code 標籤中或在應用程式的 Cowork 工作階段中讀取金鑰，因為 Claude Desktop 自己供應並鎖定這些工作階段的 MCP 伺服器。當您的受管設定在那裡帶有金鑰時，`/status` 和 `claude doctor` 會說明這一點。

### 提供的伺服器何時連接

當 `managedMcpServers` 透過伺服器受管設定到達時，其時序遵循[擷取和快取行為](https://code.claude.com/docs/zh-TW/server-managed-settings.md#fetch-and-caching-behavior)：

* 在具有快取設定的機器上，Claude Code 會保留此金鑰的快取副本，直到伺服器確認工作階段的設定，並在確認前等待該確認才載入 MCP 伺服器。如果確認失敗，工作階段會在沒有提供的伺服器的情況下繼續，`/status` 會說它們被保留。
* 在機器的首次啟動時，還沒有快取任何內容，在設定到達前啟動的互動式工作階段會在設定到達時立即連接提供的伺服器，而已經啟動的 `claude -p` 執行可以在沒有它們的情況下完成。

使用[閘道登入](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#precedence-with-other-managed-sources)，Claude Code 在工作階段啟動前載入原則，因此兩種情況都不會延遲或跳過提供的伺服器。

已在執行的互動式工作階段會套用您對金鑰的編輯：

* **新增伺服器**：Claude Code 在更新的設定到達時連接它，無需重新啟動。
* **變更伺服器的項目**：這些工作階段使用新定義重新連接到它。
* **移除伺服器**：執行中的互動式工作階段在讀取變更的設定後會將其中斷連接。非互動式 (`-p`) 執行會保留它直到結束。

## 使用允許清單和拒絕清單進行基於政策的控制

允許清單和拒絕清單會篩選允許載入哪些已設定的伺服器。它們不是登錄表：伺服器仍然必須由使用者、外掛程式或您的組織新增，才能讓任一清單對其適用。

您的組織透過 `managedMcpServers` 提供的伺服器會在沒有允許清單項目的情況下載入，而[跳過允許清單檢查的伺服器](#servers-that-skip-the-allowlist-check)涵蓋 `managed-mcp.json` 伺服器。拒絕清單適用於每個伺服器，無論其來自何處，除了程序內 `type: "sdk"` 項目外。

若要將伺服器部署給使用者，請使用 [`managed-mcp.json`](#exclusive-control-with-managed-mcp-json) 或 [`managedMcpServers`](#provide-servers-through-managed-settings)。兩個清單也會篩選使用 [`--mcp-config` CLI 旗標](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags)傳遞的伺服器，除了進程內 `type: "sdk"` 項目外；`--strict-mcp-config` 限制哪些設定檔會載入，不會繞過任一清單。

若要使允許清單具有權威性，請在[受管設定來源](https://code.claude.com/docs/zh-TW/admin-setup.md#decide-how-settings-reach-devices)（例如伺服器受管設定或已部署的 `managed-settings.json` 檔案）中同時設定 `allowedMcpServers` 和 `allowManagedMcpServersOnly: true`。

鎖定適用於每個由管理員控制的受管來源，因此已部署檔案中的鎖定仍然適用於同時使用不提及 MCP 的伺服器受管設定時。當鎖定開啟時，受管允許清單來自設定允許清單的最高排名管理員來源。跨來源讀取鎖定和允許清單需要 Claude Code v2.1.273 或更新版本。

[將允許清單限制為僅受管設定](#restrict-the-allowlist-to-managed-settings-only)顯示設定。

沒有 `allowManagedMcpServersOnly`，來自每個設定範圍的允許清單會合併，包括使用者自己的 `~/.claude/settings.json`，因此使用者可以擴大您的允許清單允許的內容。拒絕清單無論如何都會從每個範圍合併。

> [!NOTE]
>
> `allowManagedMcpServersOnly` 與 `allowManagedPermissionRulesOnly` 分開，後者鎖定[權限規則](https://code.claude.com/docs/zh-TW/permissions.md#managed-settings)。設定該旗標不會強制執行 MCP 允許清單。

### 按 URL、命令或名稱比對伺服器

`allowedMcpServers` 和 `deniedMcpServers` 是項目清單。每個項目是一個物件，具有單一鍵，可按其 URL、命令或名稱識別伺服器：

| 鍵 | 比對 | 用於 |
| :- | :- | :- |
| `serverUrl` | 遠端伺服器 URL，精確或使用 `*` 萬用字元 | HTTP 和 SSE 伺服器 |
| `serverCommand` | 啟動 stdio 伺服器的確切命令和引數 | Stdio 伺服器 |
| `serverName` | 使用者指派的標籤。僅精確比對；萬用字元不會展開 | 任一類型，但請參閱 [`serverName` 項目如何比對](#how-servername-entries-match) |

將 `allowedMcpServers` 保留未設定與將其設定為空陣列不同：

| 設定 | 未設定（預設） | 空陣列 `[]` | 已填入 |
| :- | :- | :- | :- |
| `allowedMcpServers` | 允許所有伺服器 | 不允許任何伺服器，除了[那些跳過允許清單檢查的](#servers-that-skip-the-allowlist-check)外 | 僅允許比對的伺服器，除了[那些跳過允許清單檢查的](#servers-that-skip-the-allowlist-check)外 |
| `deniedMcpServers` | 沒有伺服器被阻止 | 沒有伺服器被阻止 | 比對的伺服器被阻止 |

請參閱[受管設定中的無效項目](https://code.claude.com/docs/zh-TW/managed-settings.md#invalid-entries-in-managed-settings)，了解項目未通過結構描述驗證時會發生什麼。

#### `serverName` 項目如何比對

`serverName` 項目會精確比對使用者指派的標籤，不支援萬用字元。

> [!WARNING]
>
> 任一清單中的 `serverName` 項目不是安全控制。名稱是使用者在執行 `claude mcp add` 或編輯設定檔時指派的標籤，而不是基礎伺服器，因此使用者可以呼叫任何伺服器 `github`。對於 claude.ai 連接器，名稱是 claude.ai 傳回的顯示名稱，可能會變更。若要強制執行實際執行的伺服器，請新增 `serverCommand` 或 `serverUrl` 項目。

`serverName` 驗證在兩個清單之間有所不同：

* 在 `deniedMcpServers` 中，`serverName` 接受任何非空字串，不含前導或尾隨空白，因此您可以按其顯示名稱阻止 [claude.ai 連接器](https://code.claude.com/docs/zh-TW/mcp.md#use-mcp-servers-from-claude-ai)。例如，`{ "serverName": "claude.ai Slack" }` 會阻止 Slack 連接器。當您需要拒絕對重新命名具有魯棒性時，或當連接器名稱衝突並獲得 ` (N)` 尾碼時，偏好使用 `serverUrl` 項目。
* 在 `allowedMcpServers` 中，`serverName` 限制為字母、數字、連字號和底線。使用 `serverUrl` 來允許列出 Claude Code 自行擷取的 claude.ai 連接器；對於雲端主機提供給自託管工作階段的連接器，請改用[連接器流量離開您的網路](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#connector-traffic-leaves-your-network)下列出的項目。

若要關閉 Claude Code 自行擷取的所有 claude.ai 連接器，請參閱 [`disableClaudeAiConnectors`](https://code.claude.com/docs/zh-TW/mcp#disable-claude-ai-connectors)。

#### `serverCommand` 項目如何比對

`serverCommand` 項目將命令及其引數保存為一個陣列，例如 `{ "serverCommand": ["npx", "-y", "server"] }`。Claude Code 會將該陣列與伺服器設定中的命令和引數進行比較：

* **命令精確比對。** 每個引數，按順序。`["npx", "-y", "server"]` 不比對 `["npx", "server"]` 或 `["npx", "-y", "server", "--flag"]`。
* **不比較 `env` 區塊。** `["node", "server.js"]` 會比對以任何 `env` 值執行該命令的伺服器。某些環境變數會變更 `node` 在啟動時載入的內容。若要自行設定 `env` 值，請在 [`managed-mcp.json`](#exclusive-control-with-managed-mcp-json) 中定義伺服器。

#### `serverUrl` 項目如何比對

URL 支援 `*` 萬用字元，包括以 `*` 作為整個 scheme。主機名稱比對不區分大小寫，並忽略尾隨 FQDN 點，因此 `https://Mcp.Example.com/*` 比對 `https://mcp.example.com/api`。路徑保持區分大小寫。如果未指定連接埠，主機名稱的寫法會決定模式僅比對該 scheme 的預設連接埠，還是比對每個連接埠：

* **完整寫出的主機名稱**：僅限預設連接埠，`https` 為 443，`http` 為 80
* **包含 `*` 的主機名稱**：每個連接埠

下表顯示常見模式允許的內容：

| 模式 | 允許 |
| :- | :- |
| `https://mcp.example.com/*` | 特定網域上的所有路徑，僅限連接埠 443 |
| `https://mcp.example.com` | 也允許該網域上的所有路徑，僅限連接埠 443。沒有路徑的模式比對任何路徑 |
| `https://mcp.example.com:8443/*` | 該網域上的所有路徑，僅限連接埠 8443 |
| `https://mcp.example.com:*/*` | 該網域上的所有路徑，任何連接埠，包括 443 |
| `https://*.example.com/*` | `example.com` 的任何子網域，任何連接埠 |
| `http://localhost:*/*` | localhost 上的任何連接埠 |
| `*://mcp.example.com/*` | 透過任何 scheme 連線到特定網域，每個 scheme 僅限其預設連接埠 |

`deniedMcpServers` 中的項目以相同方式比對連接埠，因此請根據您需要阻止的連接埠和 scheme，為 `staging.example.com` 選擇項目：

* `https://staging.example.com/*`：僅阻止該主機上連接埠 443 的 `https` 伺服器，因此不會阻止位於 `https://staging.example.com:8443/api` 的伺服器
* `https://staging.example.com:*/*`：阻止該主機上所有連接埠的 `https` 伺服器
* `*://staging.example.com:*/*`：阻止該主機的任何 scheme 及任何連接埠

#### `serverCommand` 和 `serverUrl` 項目中的環境變數

`serverCommand` 和 `serverUrl` 值在比對前展開。政策項目和伺服器的已設定值都會經過 [`${VAR}` 和 `${VAR:-default}` 展開](https://code.claude.com/docs/zh-TW/mcp#environment-variable-expansion-in-mcp-json)，因此寫成 `["${HOME}/bin/server"]` 的項目會比對使用相同參考或展開路徑的伺服器設定。`serverName` 值按字面比對，永遠不會展開。

兩側讀取不同的環境：

* **伺服器的已設定值**：從即時程序環境展開，就像 `.mcp.json` 的其餘部分一樣
* **政策項目**：從固定環境展開，因此由專案或使用者設定檔設定的變數無法變更允許清單項目的含義

因為政策項目仍然取決於啟動 shell 對其參考的任何變數的值，請對您依賴以進行強制執行的項目使用字面 URL 和命令。

在 Windows 上，請參考在該處設定的環境變數，例如 `${USERPROFILE}` 而不是 `${HOME}`。

兩個清單的展開方式不同：

| 項目清單 | 展開自 | 會變更 URL 項目的配置、主機或路徑範圍的展開 |
| - | - | - |
| `allowedMcpServers` | Claude Code 啟動時的環境，加上來自受管設定的 `env` 值 | Claude Code 忽略項目 |
| `deniedMcpServers` | 相同，以及沒有啟動值且沒有 `:-default` 的變數從存放庫外的設定檔（例如使用者或受管設定）填入，這只會擴大項目比對的內容 | 項目仍然比對 |

固定環境和此表中的規則需要 Claude Code v2.1.219 或更新版本。

### 伺服器如何被評估

在載入伺服器之前（包括來自 `managed-mcp.json` 的伺服器），Claude Code 會按順序執行以下三項檢查。當使用者重新連接伺服器或在 `/mcp` 中開啟已停用的伺服器時，它會再次執行它們。程序內 `type: "sdk"` 伺服器（由[啟動工作階段的應用程式註冊](https://code.claude.com/docs/zh-TW/mcp.md#how-connectors-reach-claude-code)）會跳過全部三項。

1. **合併清單。** 來自每個設定範圍的允許清單和拒絕清單項目合併為一個允許清單和一個拒絕清單。當 `allowManagedMcpServersOnly` 為 `true` 時，僅保留受管允許清單；拒絕清單始終從每個範圍合併。當存在多個受管來源時，[從每個管理員來源讀取的鍵](https://code.claude.com/docs/zh-TW/managed-settings.md#keys-read-from-every-admin-source)說明其中哪些提供受管範圍的清單。
2. **檢查拒絕清單。** 與任何拒絕清單項目比對的伺服器（按 URL、命令或名稱）會被阻止。沒有任何東西會覆寫拒絕清單比對。
3. **檢查允許清單。** [某些伺服器會跳過此檢查](#servers-that-skip-the-allowlist-check)。如果 `allowedMcpServers` 未在任何地方設定，每個通過拒絕清單的伺服器都會載入。如果已設定，伺服器必須比對的內容取決於其類型，如下表所示。

| 伺服器類型 | 比對時允許 |
| :- | :- |
| 遠端（HTTP 或 SSE） | 一個 `serverUrl` 項目。當允許清單不包含 `serverUrl` 項目時，`serverName` 比對才計數 |
| Stdio | 一個 `serverCommand` 項目。當允許清單不包含 `serverCommand` 項目時，`serverName` 比對才計數 |

#### 跳過允許清單檢查的伺服器

除了跳過[全部三項檢查](#how-a-server-is-evaluated)的程序內 `type: "sdk"` 伺服器之外，還有三組伺服器會跳過允許清單檢查：

* 組織自己的伺服器：每個 `managedMcpServers` 項目，以及任何 `managed-mcp.json` 項目，其值在 `env` 之外不使用 `${VAR}` 展開。
* 內建伺服器，例如 Chrome 中的 Claude、Claude Code 在執行中的 VS Code 或 JetBrains IDE 中連接的 `ide` 伺服器，以及 CLI 本身設定的伺服器。
* [Claude Tag](https://code.claude.com/docs/zh-TW/claude-tag.md) 工作階段的 Slack 工具：它用來讀取執行緒和發佈回覆的伺服器會在沒有允許清單項目的情況下載入。

在其命令、引數、URL 或標頭中使用 `${VAR}` 展開的 `managed-mcp.json` 伺服器仍會被檢查。Claude Code 也會檢查使用者、外掛程式或 claude.ai 新增的每個伺服器，以及使用者使用 `--mcp-config` 傳遞的每個伺服器。關於變更了哪些 `managed-mcp.json` 伺服器會被檢查的版本，以及如何防止某個伺服器載入，請參閱[允許清單和拒絕清單如何套用於受管集合](#how-allowlists-and-denylists-apply-to-the-managed-set)。

### 範例設定

以下設定設定了具有拒絕清單的硬允許清單。反白顯示的行會變更如何評估清單的其餘部分，區塊後的標註說明每一行：

```json {3,5,11} theme={null}
{
  "allowedMcpServers": [
    { "serverUrl": "https://api.githubcopilot.com/*" },
    { "serverUrl": "https://mcp.sentry.dev/*" },
    { "serverCommand": ["npx", "-y", "@modelcontextprotocol/server-filesystem", "."] },
    { "serverCommand": ["python", "/usr/local/bin/approved-server.py"] },
    { "serverUrl": "https://mcp.example.com/*" },
    { "serverUrl": "https://*.internal.example.com/*" }
  ],
  "deniedMcpServers": [
    { "serverName": "dangerous-server" },
    { "serverCommand": ["npx", "-y", "unapproved-package"] },
    { "serverUrl": "https://*.untrusted.example.com/*" }
  ]
}
```

* **第 3 行**：第一個 `serverUrl` 項目。一旦存在，每個遠端伺服器都必須比對 URL 模式，因此使用者無法透過給予它允許的名稱來取得未列出的遠端伺服器。
* **第 5 行**：第一個 `serverCommand` 項目。對 stdio 伺服器的效果相同，因此每個本機伺服器都必須精確比對列出的命令。
* **第 11 行**：拒絕清單中的 `serverName` 項目。拒絕清單項目始終適用，因此任何名為 `dangerous-server` 的伺服器都會被阻止，無論其 URL 或命令如何。

此允許清單中的 `serverName` 項目永遠不會比對任何內容，因為兩種傳輸類型都已有更嚴格的項目。

下面的摺疊式選單會逐步說明如何針對其他允許清單和拒絕清單組合評估伺服器。

> [accordion] 僅限 URL 的允許清單
>
> ```json theme={null}
> {
>   "allowedMcpServers": [
>     { "serverUrl": "https://mcp.example.com/*" },
>     { "serverUrl": "https://*.internal.example.com/*" }
>   ]
> }
> ```
>
> | 伺服器 | 結果 |
> | :- | :- |
> | `https://mcp.example.com/api` 上的 HTTP 伺服器 | 允許：比對 URL 模式 |
> | `https://api.internal.example.com/mcp` 上的 HTTP 伺服器 | 允許：比對萬用字元子網域 |
> | `https://external.example.com/mcp` 上的 HTTP 伺服器 | 阻止：不比對任何 URL 模式 |
> | 具有任何命令的 Stdio 伺服器 | 阻止：沒有名稱或命令項目可比對 |

> [accordion] 僅限命令的允許清單
>
> ```json theme={null}
> {
>   "allowedMcpServers": [
>     { "serverCommand": ["npx", "-y", "approved-package"] }
>   ]
> }
> ```
>
> | 伺服器 | 結果 |
> | :- | :- |
> | 具有 `["npx", "-y", "approved-package"]` 的 Stdio 伺服器 | 允許：比對命令 |
> | 具有 `["node", "server.js"]` 的 Stdio 伺服器 | 阻止：不比對命令 |
> | 名為 `my-api` 的 HTTP 伺服器 | 阻止：沒有名稱項目可比對 |

> [accordion] 混合名稱和命令允許清單
>
> ```json theme={null}
> {
>   "allowedMcpServers": [
>     { "serverName": "github" },
>     { "serverCommand": ["npx", "-y", "approved-package"] }
>   ]
> }
> ```
>
> | 伺服器 | 結果 |
> | :- | :- |
> | 名為 `local-tool` 且具有 `["npx", "-y", "approved-package"]` 的 Stdio 伺服器 | 允許：比對命令 |
> | 名為 `local-tool` 且具有 `["node", "server.js"]` 的 Stdio 伺服器 | 阻止：命令項目存在但不比對 |
> | 名為 `github` 且具有 `["node", "server.js"]` 的 Stdio 伺服器 | 阻止：stdio 伺服器在命令項目存在時必須比對命令 |
> | 名為 `github` 的 HTTP 伺服器 | 允許：比對名稱 |
> | 名為 `other-api` 的 HTTP 伺服器 | 阻止：名稱不比對 |

> [accordion] 僅限名稱的允許清單
>
> ```json theme={null}
> {
>   "allowedMcpServers": [
>     { "serverName": "github" },
>     { "serverName": "internal-tool" }
>   ]
> }
> ```
>
> | 伺服器 | 結果 |
> | :- | :- |
> | 名為 `github` 且具有任何命令的 Stdio 伺服器 | 允許：沒有命令限制 |
> | 名為 `internal-tool` 且具有任何命令的 Stdio 伺服器 | 允許：沒有命令限制 |
> | 名為 `github` 的 HTTP 伺服器 | 允許：比對名稱 |
> | 任何名為 `other` 的伺服器 | 阻止：名稱不比對 |

> [accordion] 具有拒絕清單覆蓋的允許清單
>
> ```json theme={null}
> {
>   "allowedMcpServers": [
>     { "serverUrl": "https://*.example.com/*" }
>   ],
>   "deniedMcpServers": [
>     { "serverUrl": "https://staging.example.com/*" }
>   ]
> }
> ```
>
> | 伺服器 | 結果 |
> | :- | :- |
> | `https://mcp.example.com/api` 上的 HTTP 伺服器 | 允許：比對允許清單 URL 模式，沒有拒絕清單比對 |
> | `https://staging.example.com/api` 上的 HTTP 伺服器 | 阻止：兩者都比對，但拒絕清單優先 |
> | `https://staging.example.com:8443/api` 上的 HTTP 伺服器 | 允許：比對允許清單 URL 模式，[此連接埠上沒有拒絕清單比對](#how-serverurl-entries-match) |
> | `https://other.com/mcp` 上的 HTTP 伺服器 | 阻止：不比對允許清單 |

### 將允許清單限制為僅受管設定

若要使受管允許清單成為唯一適用的清單，請在受管設定檔中設定 `allowManagedMcpServersOnly`：

```json theme={null}
{
  "allowManagedMcpServersOnly": true,
  "allowedMcpServers": [
    { "serverUrl": "https://api.githubcopilot.com/*" },
    { "serverUrl": "https://*.internal.example.com/*" }
  ]
}
```

當 `allowManagedMcpServersOnly` 為 `true` 時，來自使用者、專案和本機設定的允許清單會被忽略。拒絕清單仍然從每個設定範圍合併，因此使用者可以始終為自己阻止伺服器。

## 限制如何向使用者呈現

關於已部署 `managed-mcp.json` 且工作階段同時具有 `--mcp-config` 伺服器時，使用者在啟動時會看到的內容，請參閱[使用 managed-mcp.json 進行專屬控制](#exclusive-control-with-managed-mcp-json)。請使用下表辨識其他回報情況，並在推出變更之前告知使用者可預期的結果：

| 限制 | 使用者看到的內容 |
| :- | :- |
| `managed-mcp.json` 存在，且使用者執行 `claude mcp add` | `Cannot add MCP server: enterprise MCP configuration is active and has exclusive control over MCP servers` |
| `managed-mcp.json` 存在，且原本可以執行 Claude in Chrome 的使用者執行 `claude --chrome` | Claude Code 在啟動時結束並顯示 `Claude in Chrome is blocked by your organization's managed MCP configuration (managed-mcp.json). An administrator can allow it with allowClaudeInChromeWithManagedMcp in device policy.` |
| 該伺服器位於拒絕清單中，且使用者執行 `claude mcp add` | `Cannot add MCP server "<name>": server is explicitly blocked by enterprise policy` |
| 該伺服器不在允許清單中，且使用者執行 `claude mcp add` | `Cannot add MCP server "<name>": not allowed by enterprise policy` |
| [`strictPluginOnlyCustomization`](https://code.claude.com/docs/zh-TW/settings-reference#strictpluginonlycustomization) 為 `true` 或包含 `mcp`，且使用者執行 `claude mcp add` | [`Cannot add MCP server: your organization's managed settings allow only MCP servers that plugins provide`](https://code.claude.com/docs/zh-TW/errors#cannot-add-mcp-server-when-managed-settings-allow-only-plugin-servers) |
| 使用者對來自 `managedMcpServers` 的伺服器執行 `claude mcp remove` | `MCP server "<name>" is provided by your organization (managed settings) and cannot be removed locally.` |
| 先前已設定的伺服器現在被政策封鎖 | 該伺服器會從 `/mcp` 和 `claude mcp list` 中消失 |
| 伺服器在工作階段執行期間遭到封鎖，且使用者在 `/mcp` 中選取 **Reconnect** 或將其重新開啟 | [`MCP server <name> is blocked by enterprise managed policy`](https://code.claude.com/docs/zh-TW/errors#mcp-server-is-blocked-by-enterprise-managed-policy) |

當伺服器無聲無息地消失時，使用者不會收到任何訊號得知原因是政策所致，因此在推出新限制時，請告知受影響的使用者哪些伺服器已被封鎖。

## 監控 MCP 使用

當您配置 [OpenTelemetry 匯出](https://code.claude.com/docs/zh-TW/monitoring-usage.md) 時，Claude Code 可以記錄使用者呼叫的 MCP 伺服器和工具。設定 `OTEL_LOG_TOOL_DETAILS=1` 以在工具事件和 [成本和權杖計數器](https://code.claude.com/docs/zh-TW/monitoring-usage.md#cost-counter) 中包含 MCP 伺服器和工具名稱，然後在您的收集器中聚合它們以查看您的使用者實際連接到的伺服器。請參閱 [監控](https://code.claude.com/docs/zh-TW/monitoring-usage.md) 以設定匯出器和完整事件架構。

## 配置摘要

本頁涵蓋的每個檔案和設定、它控制的內容以及如何傳遞它：

| 表面 | 控制的內容 | 位置 | 傳遞方式 |
| :- | :- | :- | :- |
| `managed-mcp.json` | 固定伺服器集合、獨佔控制 | 系統路徑：`/Library/Application Support/ClaudeCode/`、`/etc/claude-code/` 或 `C:\Program Files\ClaudeCode\` | MDM、GPO、艦隊管理或任何具有管理員權限的程序。無法通過伺服器受管設定設定 |
| `managedMcpServers` | 提供給每個使用者的遠端伺服器，與他們自己的伺服器一起 | 僅受管設定來源；該設定在其他地方無效 | [受管設定來源](https://code.claude.com/docs/zh-TW/admin-setup.md#decide-how-settings-reach-devices)：伺服器受管設定、閘道原則、`managed-settings.json`、MDM 設定檔或 HKLM 登錄 |
| `allowedMcpServers` | 允許的伺服器允許清單 | 任何 [設定範圍](https://code.claude.com/docs/zh-TW/settings.md#where-settings-live)；[伺服器如何被評估](#how-a-server-is-evaluated) 說明來自多個範圍和受管來源的清單如何組合 | 為了強制執行，[受管設定來源](https://code.claude.com/docs/zh-TW/admin-setup.md#decide-how-settings-reach-devices)：伺服器受管設定、`managed-settings.json`、MDM 設定檔或登錄 |
| `deniedMcpServers` | 被阻止的伺服器拒絕清單 | 任何設定範圍；[伺服器如何被評估](#how-a-server-is-evaluated) 說明來自多個範圍和受管來源的清單如何組合 | 與 `allowedMcpServers` 相同 |
| `allowManagedMcpServersOnly` | 將允許清單鎖定為僅受管來源 | 僅受管設定來源；[從每個管理來源讀取的金鑰](https://code.claude.com/docs/zh-TW/managed-settings.md#keys-read-from-every-admin-source) 說明哪些受管來源可以開啟它。該設定在其他範圍無效 | 與 `allowedMcpServers` 相同 |
| `allowClaudeInChromeWithManagedMcp` | 讓內建的 Claude in Chrome 伺服器與 `managed-mcp.json` 一起執行 | 裝置上的受管設定：MDM 設定檔、HKLM 登錄或 `managed-settings.json`。伺服器受管設定和使用者可寫入來源無效 | MDM、GPO、艦隊管理或任何具有管理員權限的程序 |
| `allowAllClaudeAiMcps` | 在 `managed-mcp.json` 旁邊載入 Claude Code 自行擷取的 claude.ai 連接器。[在執行雲端工作階段的主機上的 `managed-mcp.json` 仍會抑制該工作階段的連接器](#allow-claude-ai-connectors-alongside-the-managed-set) | 僅受管設定來源；該設定在其他地方無效 | 與 `allowedMcpServers` 相同 |

## 相關資源

* [決定要強制執行的內容](https://code.claude.com/docs/zh-TW/admin-setup.md#decide-what-to-enforce)：MCP 限制以及權限規則、沙箱和其他管理控制
* [通過 MCP 將 Claude Code 連接到工具](https://code.claude.com/docs/zh-TW/mcp.md)：完整的 MCP 參考，包括傳輸、範圍和身份驗證
* [設定](https://code.claude.com/docs/zh-TW/settings.md)：設定層次結構以及受管設定如何優先
* [伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)：從 claude.ai 管理控制台傳遞 `allowedMcpServers` 和 `deniedMcpServers`
* [安全](https://code.claude.com/docs/zh-TW/security.md)：這些控制防禦的威脅模型
* [Claude Enterprise Administrator Guide](https://claude.com/resources/tutorials/claude-enterprise-administrator-guide)：SSO、SCIM、座位管理和推出劇本

<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/jetbrains | lastmod: 2026-11-03 | section: Getting started / Platforms and integrations -->
> 來源：https://code.claude.com/docs/zh-TW/jetbrains（官方 zh-TW，lastmod 2026-11-03）｜分類：Getting started › Platforms and integrations｜EN 摘要：Use Claude Code with JetBrains IDEs including IntelliJ, PyCharm, WebStorm, and more

# JetBrains IDEs

> 使用 Claude Code 與 JetBrains IDEs（包括 IntelliJ、PyCharm、WebStorm 等）整合

Claude Code 透過專用外掛程式與 JetBrains IDEs 整合，提供互動式差異檢視、選擇內容共享等功能。

## 支援的 IDEs

Claude Code 外掛程式適用於大多數 JetBrains IDEs，包括：

* IntelliJ IDEA
* PyCharm
* Android Studio
* WebStorm
* PhpStorm
* GoLand

## 功能

* **快速啟動**：使用 `Cmd+Esc`（Mac）或 `Ctrl+Esc`（Windows/Linux）直接從編輯器開啟 Claude Code，或點擊 UI 中的 Claude Code 按鈕
* **差異檢視**：Claude Code 會在 IDE 差異檢視器中開啟程式碼變更，而不是在終端機中；可透過 `/config` 中的 **Diff tool** 設定來變更此行為
* **選擇內容共享**：IDE 中的目前選擇或分頁會自動與 Claude Code 共享。[`Read` 拒絕規則](https://code.claude.com/docs/zh-TW/permissions#read-and-edit)會阻止此共享以符合檔案
* **檔案參考快捷方式**：使用 `Cmd+Option+K`（Mac）或 `Alt+Ctrl+K`（Linux/Windows）插入檔案參考，例如 `@src/auth.ts#L1-99`
* **診斷共享**：Claude 會透過呼叫 [`getDiagnostics` tool](#the-built-in-ide-mcp-server) 來讀取 IDE 的檢查診斷，例如 lint 和語法錯誤；Claude Code 在編輯後不會自行向外掛程式要求診斷

## 安裝

該外掛程式在您的 IDE 整合終端機中執行 `claude` 命令並連接到它。它不包含自己的 CLI 副本，因此請安裝兩個部分：

**1. 安裝 Claude Code CLI**

如果您還未安裝 CLI，請按照[快速入門](https://code.claude.com/docs/zh-TW/quickstart.md)進行安裝。當 `claude` 不在您的 PATH 中時，外掛程式會顯示'無法啟動 Claude Code'通知。

**2. 安裝 JetBrains 外掛程式**

從 JetBrains Marketplace 安裝 [Claude Code 外掛程式](https://plugins.jetbrains.com/plugin/27310-claude-code-beta-)，然後重新啟動您的 IDE。

> [!NOTE]
>
> JetBrains Marketplace 是第三方軟體，Anthropic 並未為其背書、維護或稽核。Anthropic 會將 Claude Code 外掛程式提交至 JetBrains Marketplace 以供發布。

如果 `claude` 安裝在您的 IDE 找不到的位置，請在外掛程式的 [Claude 命令設定](#general-settings)中設定完整路徑。

Claude Code 適用於任何付費 Claude 訂閱（Pro、Max、Ultra、Team 或 Enterprise）或 Claude Console 帳戶，無需 API 金鑰。當您第一次執行 `claude` 時，系統會提示您[登入](https://code.claude.com/docs/zh-TW/authentication.md#log-in-to-claude-code) Claude Code。

## 使用方式

### 從您的 IDE 執行 Claude Code

從 IDE 的整合終端機執行 `claude`，所有整合功能將處於活躍狀態。

### 從外部終端機連接

在任何外部終端機中使用 `/ide` 命令，將 Claude Code 連接到您的 JetBrains IDE 並啟動所有功能：

```bash theme={null}
claude
```

```text theme={null}
/ide
```

當連接成功時，Claude Code 會確認並顯示類似 `Connected to IntelliJ IDEA.` 的訊息。

如果您希望 Claude 能夠存取與 IDE 相同的檔案，請從與 IDE 專案根目錄相同的目錄啟動 Claude Code。

## 設定

### Claude Code 設定

透過 Claude Code 的設定來設定 IDE 整合：

1. 執行 `claude`
2. 輸入 `/config` 命令
3. 將 **Diff tool** 設定為 `auto` 以在 IDE 中顯示差異，或設定為 `terminal` 以在終端機中保留差異

**Diff tool** 項目只有在 Claude Code 連接到 IDE 時才會出現在 `/config` 中，因此請從 JetBrains 終端機執行 `claude`，或先從外部終端機執行 [`/ide`](https://code.claude.com/docs/zh-TW/commands)。請參閱 [`diffTool`](https://code.claude.com/docs/zh-TW/settings-reference#difftool) 以了解基礎設定。

### 外掛程式設定

透過前往 **Settings → Tools → Claude Code \[Beta]** 來設定 Claude Code 外掛程式：

#### 一般設定

* **Claude 命令**：指定自訂命令以執行 Claude，例如 `claude`、`/usr/local/bin/claude` 或 `npx @anthropic-ai/claude-code`
* **抑制找不到 Claude 命令的通知**：略過有關找不到 Claude 命令的通知
* **啟用使用 Option+Enter 進行多行提示**：僅限 macOS。啟用時，Option+Enter 會在 Claude Code 提示中插入新行。如果遇到 Option 鍵被意外捕獲的問題，請停用此選項。需要終端機重新啟動。
* **啟用自動更新**：自動檢查並安裝外掛程式更新，在重新啟動時套用

> [!TIP]
>
> 對於 WSL 使用者：將 `wsl -d Ubuntu -- bash -lic "claude"` 設定為您的 Claude 命令（將 `Ubuntu` 替換為您的 WSL 發行版名稱）

#### ESC 鍵設定

如果 ESC 鍵無法在 JetBrains 終端機中中斷 Claude Code 操作：

1. 前往 **Settings → Tools → Terminal**
2. 執行下列其中一項：
   * 取消勾選「使用 Escape 將焦點移至編輯器」，或
   * 點擊「設定終端機快捷鍵」並刪除「切換焦點至編輯器」快捷方式
3. 套用變更

這將允許 ESC 鍵正確中斷 Claude Code 操作。

## 特殊設定

### 遠端開發

> [!WARNING]
>
> 使用 JetBrains 遠端開發時，您必須透過 **Settings → Plugin (Host)** 在遠端主機上安裝外掛程式，而不是在您的本機用戶端機器上。

### WSL 設定

如果您在 WSL2 上使用 Claude Code 搭配 JetBrains IDE，並看到「未偵測到可用的 IDEs」，原因通常是 WSL2 的 NAT 網路或 Windows 防火牆阻止了 WSL2 與在 Windows 主機上執行的 IDE 之間的連線。WSL1 直接使用主機的網路，不受影響。

#### 允許 WSL2 流量通過 Windows 防火牆

這是建議的修復方式，因為它保持您現有的 WSL2 網路模式。

**1. 尋找您的 WSL2 IP 位址**

從您的 WSL shell 內執行：

```bash theme={null}
hostname -I
```

記下您的子網路：取得位址的前兩個區段，並在其後加上 `.0.0/16`。例如，如果位址是 `172.21.123.45`，您的子網路是 `172.21.0.0/16`。

**2. 建立防火牆規則**

以系統管理員身份開啟 PowerShell 並執行以下命令，調整 IP 範圍以符合您的子網路：

```powershell theme={null}
New-NetFirewallRule -DisplayName "Allow WSL2 Internal Traffic" -Direction Inbound -Protocol TCP -Action Allow -RemoteAddress 172.21.0.0/16 -LocalAddress 172.21.0.0/16
```

**3. 重新啟動您的 IDE 和 Claude Code**

關閉並重新開啟兩者，以使新規則生效。

#### 將 WSL2 切換為鏡像網路

鏡像網路需要 Windows 11 22H2 或更新版本。如果您使用 Windows 10，請改用上述防火牆規則。

將以下內容新增到您 Windows 使用者目錄中的 `.wslconfig`：

```ini theme={null}
[wsl2]
networkingMode=mirrored
```

然後從 PowerShell 使用 `wsl --shutdown` 重新啟動 WSL。

## 疑難排解

### 外掛程式無法運作

如果外掛程式已安裝但 Claude Code 功能未出現在您的 IDE 中：

* 確保您從專案根目錄執行 Claude Code
* 檢查 JetBrains 外掛程式在 IDE 設定中是否已啟用
* 完全重新啟動 IDE（您可能需要執行多次）
* 對於遠端開發，確保外掛程式已安裝在遠端主機上

### IDE 未被偵測

如果執行 `/ide` 命令顯示「未偵測到可用的 IDEs」：

* 驗證外掛程式已安裝並啟用
* 完全重新啟動 IDE
* 如果您預期在執行 `/ide` 時自動連線，請檢查您是否從 IDE 的整合終端機啟動 `claude`
* 對於 WSL 使用者，請參閱上方的 [WSL 設定](#wsl-configuration)

### 找不到命令

如果點擊 Claude 圖示顯示「找不到命令」：

1. 透過在終端機中執行 `claude --version` 驗證 Claude Code 已安裝
2. 在外掛程式設定中設定 Claude 命令路徑
3. 對於 WSL 使用者，使用設定部分中提到的 WSL 命令格式

## 安全考量

當 Claude Code 在 JetBrains IDE 中以 [`acceptEdits` 權限模式](https://code.claude.com/docs/zh-TW/permission-modes#auto-approve-file-edits-with-acceptedits-mode)執行時，它可能能夠修改 IDE 設定檔，這些檔案可能會被您的 IDE 自動執行。這可能會增加在 `acceptEdits` 模式中執行 Claude Code 的風險，並允許繞過 Claude Code 對 Bash 執行的權限提示。

在 JetBrains IDE 中執行時，請考慮：

* 對編輯使用手動模式，因為 `acceptEdits` 和自動模式都會批准您工作目錄內的編輯而不詢問，除了在[受保護的路徑](https://code.claude.com/docs/zh-TW/permission-modes.md#protected-paths)中
* 特別小心確保 Claude 僅與受信任的提示一起使用
* 注意 Claude Code 有權限修改哪些檔案

如需 IDE 外部的 Claude Code 安裝或登入問題，請參閱[疑難排解安裝和登入](https://code.claude.com/docs/zh-TW/troubleshoot-install.md)。

### 內建的 IDE MCP 伺服器

當外掛程式處於活動狀態時，它會執行一個本機 MCP 伺服器，CLI 會自動連接到該伺服器。這是 CLI 在 IDE 的原生差異檢視器中開啟差異、讀取您目前的 `@`-提及選擇，以及讓 Claude 讀取檢查診斷的方式。

伺服器名稱為 `ide`，並且從 `/mcp` 隱藏，因為沒有任何要設定的內容。不過，如果您的組織使用 [`PreToolUse` hook](https://code.claude.com/docs/zh-TW/hooks#pretooluse) 來允許列表 MCP 工具，您需要知道它存在。

**選擇和開啟檔案的內容。** 連接時，CLI 會在您傳送的每個提示上包含您目前的編輯器選擇和活動檔案的路徑作為內容。當發生這種情況時，文字記錄會顯示一行 `⧉ Selected N lines from <file>`。

如果您[在 Claude 工作時佇列訊息](https://code.claude.com/docs/zh-TW/interactive-mode.md#queue-messages-while-claude-works)，它會保留您按下 `Enter` 時的選擇，無論您之後選擇什麼。

若要排除敏感檔案（例如 `.env`），請為其路徑新增[`Read` 拒絕規則](https://code.claude.com/docs/zh-TW/permissions#read-and-edit)。相符的拒絕規則會防止該檔案的選定文字和開啟檔案通知到達 Claude。

**傳輸和驗證。** 伺服器在作業系統指派的暫時連接埠上接聽，該連接埠不可設定。傳輸是未加密的 `ws://`；在迴圈介面上，任何可以擷取流量的程序也可以從鎖定檔案讀取權杖，因此 TLS 不會對本機攻擊者增加保護。每次 IDE 啟動都會產生一個新的隨機驗證權杖，將其寫入 `~/.claude/ide/<port>.lock` 的鎖定檔案，CLI 必須將其作為 `X-Claude-Code-Ide-Authorization` 標頭呈現才能連接。如果設定了 `CLAUDE_CONFIG_DIR`，鎖定檔案會改為寫入 `$CLAUDE_CONFIG_DIR/ide/`。

**向模型公開的工具。** 伺服器裝載多個工具，但只有一個對模型可見。其餘的是 CLI 用於自己的 UI 的內部 RPC，例如開啟差異和讀取選擇，在工具清單到達 Claude 之前會被篩選出來。

| 工具名稱（如 hooks 所見） | 它的作用 | 唯讀 |
| - | - | - |
| `mcp__ide__getDiagnostics` | 傳回 IDE 的檢查診斷，即編輯器中顯示的錯誤和警告。每次呼叫涵蓋一個檔案：Claude 指定的檔案，或如果 Claude 未指定檔案，則為您的活動編輯器中的檔案。 | 是 |

JetBrains 外掛程式不會向模型公開程式碼執行工具。

**接聽介面。** 伺服器繫結到哪個網路介面由**設定 → 工具 → Claude Code \[Beta] → 網路（進階）**下的**接受來自所有網路介面的連接**控制。停用此設定時，伺服器僅在 `127.0.0.1` 上接聽，無法從其他主機到達。啟用時，連接埠可從您的本機網路到達。此設定適用於 CLI 無法透過迴圈介面到達 IDE 的情況，例如具有預設 NAT 網路的 WSL2 或遠端 IDE 設定；請參閱[WSL 設定](#wsl-configuration)以了解該情況。

> [!WARNING]
>
> 啟用**接受來自所有網路介面的連接**會使 IDE MCP 連接埠可從您的本機網路到達。連接仍需要來自鎖定檔案的驗證權杖，但由於傳輸是未加密的 `ws://`，當設定開啟時，工作階段流量和該權杖都會以明文形式跨越網路。僅在迴圈介面無法運作時才開啟它。對於 WSL2，偏好[鏡像網路](#switch-wsl2-to-mirrored-networking)，以便 Windows 迴圈介面與 Linux VM 共享，且通訊端可以保持在迴圈介面上。

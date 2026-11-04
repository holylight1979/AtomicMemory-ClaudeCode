<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/troubleshoot-install | lastmod: 2026-10-30 | section: Build with Claude Code / Troubleshooting -->
> 來源：https://code.claude.com/docs/zh-TW/troubleshoot-install（官方 zh-TW，lastmod 2026-10-30）｜分類：Build with Claude Code › Troubleshooting｜EN 摘要：Fix command not found, PATH, permission, network, and authentication errors when installing or signing in to Claude Code.

# 排除安裝和登入問題

> 修復安裝或登入 Claude Code 時的 command not found、PATH、權限、網路和身分驗證錯誤。

如果安裝失敗或無法登入，請在下方找到您的錯誤。如需 Claude Code 正常運作後的執行時問題，請參閱[疑難排解](https://code.claude.com/docs/zh-TW/troubleshooting.md)。如需設定問題（例如設定未套用或 hook 未觸發），請參閱[偵錯您的設定](https://code.claude.com/docs/zh-TW/debug-your-config.md)。

## 找到您的錯誤

將您看到的錯誤訊息或症狀與修復方案相符：

| 您看到的內容 | 解決方案 |
| :- | :- |
| `command not found: claude` 或 `'claude' is not recognized` | [修復您的 PATH](#command-not-found-claude-after-installation) |
| `Native installation exists but ... is not in your PATH` | [將安裝目錄新增到您的 PATH](#verify-your-path) |
| `where.exe claude` 傳回 `INFO: Could not find files for the given pattern(s).` | [檢查是否已安裝 Claude Code](#check-for-conflicting-installations) |
| `zsh: permission denied: /Users/you/.zshrc` 或 `bash: /home/you/.bashrc: Permission denied` | [讓您的 shell 設定檔可寫入](#permission-denied-when-adding-to-your-path) |
| `syntax error near unexpected token '<'` | [安裝指令碼傳回 HTML](#install-script-returns-html-instead-of-a-shell-script) |
| CMD 中出現 `< was unexpected at this time` | [安裝指令碼傳回 HTML](#install-script-returns-html-instead-of-a-shell-script) |
| `The term 'System.Xml.XmlDocument' is not recognized` | [安裝指令碼傳回 HTML](#install-script-returns-html-instead-of-a-shell-script) |
| `curl: (22) The requested URL returned error: 403` | [安裝指令碼傳回 403](#install-script-returns-html-instead-of-a-shell-script) |
| `curl: (23)` 或 `curl: (56) Failure writing output to destination` | [檢查連線或使用替代安裝程式](#curl-56-failure-writing-output-to-destination) |
| Linux 上安裝期間出現 `Killed` | [釋放記憶體或新增交換空間](#install-killed-on-low-memory-linux-servers) |
| `Installation was killed before it could finish` | [釋放記憶體，然後重新執行安裝程式](#installation-was-killed-before-it-could-finish) |
| `Raw mode is not supported` 安裝期間 | [重新執行安裝程式](#raw-mode-is-not-supported-during-install) |
| 安裝期間出現 `EACCES: permission denied` | [修復安裝目錄的權限](#permission-errors-during-installation) |
| `TLS connect error` 或 `SSL/TLS secure channel` | [更新 CA 憑證](#tls-or-ssl-connection-errors) |
| `CRYPT_E_NO_REVOCATION_CHECK` 或 `CRYPT_E_REVOCATION_OFFLINE` | [因應遭封鎖的撤銷檢查](#tls-or-ssl-connection-errors) |
| `Failed to fetch version` 或無法連線到下載伺服器 | [檢查網路和代理伺服器設定](#check-network-connectivity) |
| `The connection dropped while downloading the update` 或 `Download timed out: exceeded the total deadline` | [再次執行更新或設定您的代理伺服器](#the-connection-dropped-while-downloading-the-update) |
| `Release verification failed for Claude Code` | [再次執行 `claude update` 或 `claude install`](#release-verification-failed) |
| 工作階段頁尾以紅色顯示 `Auto-update failed · Run claude doctor` | [從您的 shell 執行 `claude update`](#auto-update-failed) |
| `irm is not recognized` 或 `The token '&&' is not a valid statement separator` | [在您的 shell 上使用正確的命令](#wrong-install-command-on-windows) |
| `Cask 'claude-code' is unavailable: No Cask with this name exists` | [更新 Homebrew](#homebrew-cask-unavailable-or-outdated) |
| `Cask 'claude-code@latest' is not installed` | [升級您安裝的 cask](#cask-is-not-installed) |
| `'bash' is not recognized as the name of a cmdlet` | [使用 Windows 安裝程式命令](#wrong-install-command-on-windows) |
| `A parameter cannot be found that matches parameter name 'fsSL'` | [使用 Windows 安裝程式命令](#wrong-install-command-on-windows) |
| `Claude Code on Windows requires either Git for Windows (for bash) or PowerShell` | [安裝 shell](#claude-code-on-windows-requires-either-git-for-windows-for-bash-or-powershell) |
| `Claude Code does not support 32-bit Windows` | [開啟 Windows PowerShell，而非 x86 項目](#claude-code-does-not-support-32-bit-windows) |
| `The process cannot access the file ... because it is being used by another process` | [清除下載資料夾並重試](#the-process-cannot-access-the-file-during-windows-install) |
| `Error loading shared library` | [您的系統的二進位變體錯誤](#linux-musl-or-glibc-binary-mismatch) |
| `Illegal instruction` | [架構或 CPU 指令集不相符](#illegal-instruction) |
| WSL 中的 `cannot execute binary file: Exec format error` | [WSL1 原生二進位回歸](#exec-format-error-on-wsl1) |
| 工作階段執行期間出現 `Bus error` 或 `oh no: Bun has crashed` | [保持可執行檔可讀取](#bus-error-while-a-session-is-running) |
| PowerShell 安裝程式完成但找不到 `claude` 或顯示舊版本 | [新增安裝目錄到您的 PATH](#verify-your-path)，然後開啟新的終端機 |
| macOS 上的 `dyld: Symbol not found`、`dyld: cannot load` 或 `Abort trap` | [二進位不相容](#dyld-cannot-load-on-macos) |
| `claude update` 在 `Checking for updates` 後掛起，或 `claude doctor` 掛起且無輸出 | [移動 shell 設定路徑上的目錄](#claude-update-or-claude-doctor-hangs) |
| `Invoke-Expression` 或 `iex` 解析錯誤引用 HTML 標籤或 CSS，或 `ParserError` 搭配 `ParseException` | [安裝指令碼傳回 HTML](#install-script-returns-html-instead-of-a-shell-script) |
| `running scripts is disabled on this system` 或 `PSSecurityException` | [允許 npm shims 執行](#running-scripts-is-disabled-on-this-system) |
| `Error: claude native binary not installed` | [完成 npm 安裝](#native-binary-not-found-after-npm-install) |
| `npm error code ENOTEMPTY` 在更新或重新安裝期間 | [移除剩餘的套件目錄](#npm-enotempty-during-update-or-reinstall) |
| `'claude' is not recognized` 在 Windows 上更新後立即出現 | [從其備份還原 `claude.exe`](#claude-exe-missing-after-an-update-on-windows) |
| 在 Windows 上，安裝命令列印指令碼文字且未安裝任何內容 | [執行完整的安裝命令](#wrong-install-command-on-windows) |
| `App unavailable in region` | Claude Code 在您的國家/地區不可用。請參閱[支援的國家/地區](https://www.anthropic.com/supported-countries)。 |
| `unable to get local issuer certificate` | [設定公司 CA 憑證](#tls-or-ssl-connection-errors) |
| `OAuth error` 或 `403 Forbidden` | [修復身分驗證](#login-and-authentication) |
| `Claude Code access has not been granted for this account` | [取得包含 Claude Code 的角色](#claude-code-access-has-not-been-granted-for-this-account) |
| 設定期間 `Unable to connect to Anthropic services` | 請參閱錯誤參考中的 [Unable to connect to Anthropic services](https://code.claude.com/docs/zh-TW/errors.md#unable-to-connect-to-anthropic-services) |
| `Could not load the default credentials` 或 `Could not load credentials from any providers` | [Amazon Bedrock、Google Cloud 的 Agent Platform 或 Microsoft Foundry 憑證](#bedrock-agent-platform-or-foundry-credentials-not-loading) |
| `ChainedTokenCredential authentication failed` 或 `CredentialUnavailableError` | [Amazon Bedrock、Google Cloud 的 Agent Platform 或 Microsoft Foundry 憑證](#bedrock-agent-platform-or-foundry-credentials-not-loading) |
| `API Error: 500`、`529 Overloaded`、`429` 或上面未列出的其他 4xx 和 5xx 錯誤 | 請參閱[錯誤參考](https://code.claude.com/docs/zh-TW/errors.md) |

如果您的問題未列出，請執行下面的診斷檢查以縮小原因範圍。

> [!TIP]
>
> 如果您寧願完全跳過終端機，[Claude Code Desktop 應用程式](https://code.claude.com/docs/zh-TW/desktop-quickstart.md)可讓您透過圖形介面安裝和使用 Claude Code。下載適用於 [macOS](https://claude.ai/api/desktop/darwin/universal/dmg/latest/redirect?utm_source=claude_code\&utm_medium=docs) 或 [Windows](https://claude.com/download?utm_source=claude_code\&utm_medium=docs) 的版本，無需任何命令列設定即可開始編碼。在 Linux 上，請按照 [Linux 安裝說明](https://code.claude.com/docs/zh-TW/desktop-linux.md)使用 apt 安裝應用程式。

## 執行診斷檢查

### 檢查網路連線

安裝程式從 `downloads.claude.ai` 下載。驗證您可以連線到它：

> [tab] macOS/Linux
>
> ```bash theme={null}
> curl -sI https://downloads.claude.ai/claude-code-releases/latest
> ```

> [tab] Windows PowerShell
>
> ```powershell theme={null}
> curl.exe -sI https://downloads.claude.ai/claude-code-releases/latest
> ```
>
> PowerShell 將 `curl` 別名設定為 `Invoke-WebRequest`，它會拒絕 `-sI` 旗標，所以要明確呼叫 `curl.exe`。

如果第一行顯示 `200` 狀態，表示您已連線到伺服器。在 macOS 和 Linux 上您會看到 `HTTP/2 200`，而 Windows 隨附的 `curl.exe` 會顯示 `HTTP/1.1 200 OK`。其他結果指向原因：

* `403`：通常是代理伺服器或網路篩選器阻止該主機，或 Claude Code [在您的地區不可用](https://www.anthropic.com/supported-countries)
* `5xx`：通常是暫時性服務問題；等待幾分鐘後重試

如果您看不到任何輸出、`Could not resolve host` 或連線逾時，您的網路正在阻止連線。常見原因：

* 公司防火牆或代理伺服器阻止 `downloads.claude.ai`
* 地區網路限制：嘗試使用 VPN 或替代網路
* TLS/SSL 問題：更新您系統的 CA 憑證，或檢查是否設定了 `HTTPS_PROXY`

如果您在公司代理伺服器後面，在安裝前設定 `HTTPS_PROXY` 和 `HTTP_PROXY` 為您代理伺服器的位址。如果您不知道代理伺服器 URL，請詢問您的 IT 團隊，或檢查您瀏覽器的代理伺服器設定。

此範例設定兩個代理伺服器變數，然後透過您的代理伺服器執行安裝程式：

> [tab] macOS/Linux
>
> ```bash theme={null}
> export HTTP_PROXY=http://proxy.example.com:8080
> export HTTPS_PROXY=http://proxy.example.com:8080
> curl -fsSL https://claude.ai/install.sh | bash
> ```

> [tab] Windows PowerShell
>
> ```powershell theme={null}
> $env:HTTP_PROXY = 'http://proxy.example.com:8080'
> $env:HTTPS_PROXY = 'http://proxy.example.com:8080'
> irm https://claude.ai/install.ps1 | iex
> ```

### 驗證您的 PATH

如果安裝成功但執行 `claude` 時收到 `command not found` 或 `not recognized` 錯誤，安裝目錄不在您的 PATH 中。您的 shell 會在 PATH 中列出的目錄中搜尋程式，安裝程式在 macOS/Linux 上將 `claude` 放在 `~/.local/bin/claude`，或在 Windows 上放在 `%USERPROFILE%\.local\bin\claude.exe`。

安裝程式會偵測到這種情況，並在其輸出的 `Setup notes:` 下回報：在 macOS 和 Linux 上為 `Native installation exists but ~/.local/bin is not in your PATH.`，在 Windows 上則為 `Native installation exists but C:\Users\you\.local\bin is not in your PATH.`。它會隨該說明列印修正方式，但不會自行變更 PATH。

> [!NOTE]
>
> [VS Code 擴充功能](https://code.claude.com/docs/zh-TW/vs-code.md)不會在此位置放置 `claude`。它在擴充功能目錄內為其自己的聊天面板捆綁了 CLI 的私人副本，並且不會將其新增到 PATH。如果您只安裝了擴充功能，`~/.local/bin/claude` 將不存在。執行[獨立安裝](https://code.claude.com/docs/zh-TW/setup.md)以從終端機使用 `claude`，然後繼續下面的步驟。

首先檢查程式是否確實存在，然後檢查其資料夾是否在您的 PATH 中。PATH 的修正是永久性的，因此只需套用一次。選擇您平台的分頁並在對應環境中執行其命令：在 macOS 和 Linux 上於終端機中執行，在 Windows 上則於 PowerShell 或命令提示字元中執行。

> [tab] macOS/Linux
>
> 檢查安裝程式是否已將程式放置到位：
>
> ```bash theme={null}
> ls -la ~/.local/bin/claude
> ```
>
> * **`No such file or directory`**：沒有原生安裝。如果您尚未以其他方式（例如透過 npm、Homebrew 或 Linux 套件管理員）安裝 Claude Code，請[安裝 Claude Code](https://code.claude.com/docs/zh-TW/setup.md#install-claude-code)。如果您以其他方式安裝，請參閱[檢查衝突的安裝](#check-for-conflicting-installations)。
> * **顯示該檔案的列表**：程式已存在。接下來檢查您的 PATH。
>
> 列出您的 PATH 項目並篩選安裝資料夾：
>
> ```bash theme={null}
> echo $PATH | tr ':' '\n' | grep -Fx "$HOME/.local/bin"
> ```
>
> 如果這列印出 `/Users/you/.local/bin` 或 `/home/you/.local/bin`，該目錄在您的 PATH 中，您可以跳到[檢查衝突的安裝](#check-for-conflicting-installations)。如果沒有輸出，請使用適用於您 shell 的兩個命令將其新增到您的 shell 設定。`echo` 命令會為每個新的終端機儲存此設定，而 `source` 會將其套用到您目前所在的視窗。`echo` 命令成功時不會列印任何內容。
>
> 對於 Zsh（macOS 上的預設值）：
>
> ```bash theme={null}
> echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
> source ~/.zshrc
> ```
>
> 對於 Linux 上的 Bash（在大多數發行版上是預設值）：
>
> ```bash theme={null}
> echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
> source ~/.bashrc
> ```
>
> 對於 macOS 上的 Bash，改為將該行新增到 `~/.bash_profile`。macOS 上的終端機以登入 shell 的形式啟動 Bash，它會忽略 `~/.bashrc` 並只讀取存在的 `~/.bash_profile`、`~/.bash_login` 或 `~/.profile` 中的第一個。如果您已經有 `~/.bash_login` 或 `~/.profile` 且沒有 `~/.bash_profile`，請將該行放在該檔案中，而不是建立 `~/.bash_profile`：
>
> ```bash theme={null}
> echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bash_profile
> source ~/.bash_profile
> ```
>
> 或者，關閉並重新開啟您的終端機。
>
> 如果 `echo` 命令列印 `permission denied`，請參閱[新增到 PATH 時出現 `permission denied`](#permission-denied-when-adding-to-your-path)。
>
> 對於其他 shell（例如 fish 或 Nushell），使用您的 shell 自己的設定語法將 `~/.local/bin` 新增到您的 PATH，然後重新啟動您的終端機。
>
> 驗證修復是否有效：
>
> ```bash theme={null}
> claude --version
> ```
>
> 如果仍然找不到 `claude`，請檢查以下原因：
>
> * **終端機是在變更之前開啟的**：已經開啟的視窗會保留其舊的 PATH，而編輯器內的終端機會從編輯器取得其 PATH。請開啟新視窗，或結束並重新開啟編輯器。
> * **該行未儲存**：執行 `grep -n '.local/bin' ~/.zshrc`，並使用您 shell 的檔案名稱。如果該行存在，它會列印該行及其行號。如果沒有列印任何內容，請再次執行這兩個 PATH 命令。
> * **該行被寫入另一個 shell 的檔案**：執行 `echo $0` 查看您的 shell，然後執行適用於該 shell 的兩個 PATH 命令。

> [tab] Windows PowerShell
>
> 檢查安裝程式是否已將程式放置到位：
>
> ```powershell theme={null}
> Test-Path "$env:USERPROFILE\.local\bin\claude.exe"
> ```
>
> * **`False`**：沒有原生安裝。如果您尚未以其他方式（例如透過 npm 或 WinGet）安裝 Claude Code，請[安裝 Claude Code](https://code.claude.com/docs/zh-TW/setup.md#install-claude-code)。如果您以其他方式安裝，請參閱[檢查衝突的安裝](#check-for-conflicting-installations)。
> * **`True`**：程式已存在。接下來檢查您的 PATH。
>
> 列出您的 PATH 項目並篩選安裝資料夾：
>
> ```powershell theme={null}
> $env:PATH -split ';' | Select-String '\.local\\bin'
> ```
>
> 如果這列印出 `C:\Users\you\.local\bin`，該目錄在您的 PATH 中，您可以跳到[檢查衝突的安裝](#check-for-conflicting-installations)。如果沒有輸出，將安裝目錄新增到您的使用者 PATH：
>
> ```powershell theme={null}
> $currentPath = [Environment]::GetEnvironmentVariable('PATH', 'User')
> [Environment]::SetEnvironmentVariable('PATH', "$currentPath;$env:USERPROFILE\.local\bin", 'User')
> ```
>
> 重新啟動您的終端機以使變更生效。
>
> 驗證修復是否有效：
>
> ```powershell theme={null}
> claude --version
> ```
>
> 如果在新的終端機中仍然找不到 `claude`，請檢查以下原因：
>
> * **終端機在編輯器內執行**：它會從編輯器取得其 PATH，因此請結束並重新開啟編輯器。
> * **變更未儲存**：執行 `[Environment]::GetEnvironmentVariable('PATH', 'User')`，並在其列印的 PATH 中尋找 `.local\bin`。如果不存在，請再次執行這兩個命令。

> [tab] Windows CMD
>
> 檢查安裝程式是否已將程式放置到位：
>
> ```batch theme={null}
> dir "%USERPROFILE%\.local\bin\claude.exe"
> ```
>
> * **`File Not Found` 或 `The system cannot find the path specified.`**：沒有原生安裝。如果您尚未以其他方式（例如透過 npm 或 WinGet）安裝 Claude Code，請[安裝 Claude Code](https://code.claude.com/docs/zh-TW/setup.md#install-claude-code)。如果您以其他方式安裝，請參閱[檢查衝突的安裝](#check-for-conflicting-installations)。
> * **顯示 `claude.exe` 的列表**：程式已存在。接下來檢查您的 PATH。
>
> 列出您的 PATH 項目並篩選安裝資料夾：
>
> ```batch theme={null}
> echo %PATH% | findstr /i "local\bin"
> ```
>
> 如果沒有輸出，開啟系統設定，前往環境變數，並將 `%USERPROFILE%\.local\bin` 新增到您的使用者 PATH 變數。重新啟動您的終端機。
>
> 驗證修復是否有效：
>
> ```batch theme={null}
> claude --version
> ```
>
> 如果在新的終端機中仍然找不到 `claude`，由於編輯器內的終端機會從編輯器取得其 PATH，因此也請結束並重新開啟編輯器。

### 檢查衝突的安裝

多個 Claude Code 安裝可能會導致版本不匹配或非預期的行為。檢查已安裝的內容：

> [tab] macOS/Linux
>
> 列出在您的 PATH 中找到的所有 `claude` 二進位檔：
>
> ```bash theme={null}
> which -a claude
> ```
>
> 如果這列印出 `claude not found`、`no claude in` 行，或沒有列印任何內容，表示您的 PATH 上沒有 `claude`。接下來的檢查會顯示是否有安裝任何 `claude`。
>
> 檢查 `claude` 二進位檔可能來自的三個位置。`~/.local/bin/claude` 是原生安裝程式，`~/.claude/local/` 是由舊版 Claude Code 建立的舊版本地 npm 安裝，npm 全域清單顯示 `-g` 安裝：
>
> ```bash theme={null}
> ls -la ~/.local/bin/claude
> ```
>
> 原生安裝顯示進入 `~/.local/share/claude/versions/` 的符號連結。您在此路徑自己建立的指令碼或符號連結是自訂啟動程式，[自動更新會將其保留在原位](https://code.claude.com/docs/zh-TW/setup.md#auto-updates)。
>
> 如果任一 `ls` 命令列印 `No such file or directory`，這不是錯誤。這表示該位置沒有安裝任何內容，所以繼續進行下一個檢查。
>
> ```bash theme={null}
> ls -la ~/.claude/local/
> ```
>
> ```bash theme={null}
> npm -g ls @anthropic-ai/claude-code 2>/dev/null
> ```
>
> 如果 `ls -la ~/.local/bin/claude` 列印 `No such file or directory`，表示沒有原生安裝。如果您尚未以其他方式（例如透過 npm、Homebrew 或 Linux 套件管理員）安裝 Claude Code，請[安裝 Claude Code](https://code.claude.com/docs/zh-TW/setup.md#install-claude-code)。如果 `~/.local/bin/claude` 存在但 `which -a claude` 沒有列出它，表示該資料夾不在您的 PATH 中：請參閱[驗證您的 PATH](#verify-your-path)。

> [tab] Windows PowerShell
>
> 列出在您的 PATH 中找到的所有 `claude` 二進位檔：
>
> ```powershell theme={null}
> where.exe claude
> ```
>
> 如果這列印出 `INFO: Could not find files for the given pattern(s).`，表示您的 PATH 上沒有 `claude`。
>
> 檢查原生安裝程式是否放置了二進位檔：
>
> ```powershell theme={null}
> Test-Path "$env:USERPROFILE\.local\bin\claude.exe"
> ```
>
> * **`True`**：原生安裝存在。如果 `where.exe` 沒有找到任何內容，表示其資料夾不在您的 PATH 中：請參閱[驗證您的 PATH](#verify-your-path)。
> * **`False`**：沒有原生安裝。如果您尚未以其他方式（例如透過 npm 或 WinGet）安裝 Claude Code，請[安裝 Claude Code](https://code.claude.com/docs/zh-TW/setup.md#install-claude-code)。

如果您找到多個安裝，只保留一個。在 macOS/Linux 上的 `~/.local/bin/claude` 或 Windows 上的 `%USERPROFILE%\.local\bin\claude.exe` 的原生安裝是建議的。移除額外的：

解除安裝 npm 全域安裝：

```bash theme={null}
npm uninstall -g @anthropic-ai/claude-code
```

移除舊版本地 npm 安裝：

> [tab] macOS/Linux
>
> ```bash theme={null}
> rm -rf ~/.claude/local
> ```

> [tab] Windows PowerShell
>
> ```powershell theme={null}
> Remove-Item -Recurse -Force "$env:USERPROFILE\.claude\local"
> ```

在 macOS 上移除 Homebrew 安裝。如果您安裝了 `claude-code@latest` cask，替換該名稱：

```bash theme={null}
brew uninstall --cask claude-code
```

在 Windows 上移除 WinGet 安裝：

```powershell theme={null}
winget uninstall Anthropic.ClaudeCode
```

### 檢查目錄權限

因權限而失敗的安裝會指出它無法建立或寫入的路徑。在 Windows 上，安裝會寫入 `%USERPROFILE%` 下，預設情況下您的使用者可以寫入，所以此部分在那裡很少適用。

在 macOS 和 Linux 上，安裝會寫入以下位置：

* `~/.claude/downloads/`：安裝命令放置下載的二進位檔的位置
* `~/.local/bin/`：`claude` 啟動程式
* `~/.local/share/claude/`：它下載的每個版本
* `~/.local/state/claude/`：其鎖定檔案
* `~/.cache/claude/`：暫存的下載
* [`~/.claude.json`](https://code.claude.com/docs/zh-TW/claude-directory)：您的全域設定檔，安裝程式會在其中記錄安裝方式

如果您設定了 `XDG_DATA_HOME`、`XDG_STATE_HOME` 或 `XDG_CACHE_HOME`，安裝會改用這些位置來取代 `~/.local/share`、`~/.local/state` 和 `~/.cache`。如果您設定了 [`CLAUDE_CONFIG_DIR`](https://code.claude.com/docs/zh-TW/env-vars)，全域設定檔會位於該目錄下，而不是您的家目錄。

檢查目錄是否可寫入：

```bash theme={null}
test -w ~/.local/bin && echo "writable" || echo "not writable"
test -w ~/.claude && echo "writable" || echo "not writable"
```

如果任一目錄不可寫入，建立安裝目錄並將您的使用者設定為擁有者：

```bash theme={null}
sudo mkdir -p ~/.local/bin
sudo chown -R $(whoami) ~/.local
```

### 驗證二進位檔是否有效

如果 `claude --version` 列印版本但 `claude` 在啟動時當機或掛起，執行這些檢查以縮小原因範圍。如果 `claude --version` 說命令未找到，先前往[驗證您的 PATH](#verify-your-path)；下面的命令假設 `claude` 在您的 PATH 上。

確認二進位檔存在且可執行：

> [tab] macOS/Linux
>
> ```bash theme={null}
> ls -la "$(command -v claude)"
> ```

> [tab] Windows PowerShell
>
> ```powershell theme={null}
> Get-Command claude | Select-Object Source
> ```

在 Linux 上，檢查遺失的共用程式庫。如果 `ldd` 顯示遺失的程式庫，您可能需要安裝系統套件。在 Alpine Linux 和其他 musl 型發行版上，請參閱 [Alpine Linux 設定](https://code.claude.com/docs/zh-TW/setup.md#alpine-linux-and-musl-based-distributions)。

```bash theme={null}
ldd "$(command -v claude)" | grep "not found"
```

確認二進位檔可以執行：

```bash theme={null}
claude --version
```

## 常見安裝問題

這些是最常見的安裝問題及其解決方案。

### 安裝指令碼傳回 HTML 而非 shell 指令碼

當下載到的內容不是安裝指令碼時，安裝命令會因以下其中一個錯誤而失敗。

**Bash 或 Zsh**：錯誤會引用傳回頁面的第一行。

```text theme={null}
bash: line 1: syntax error near unexpected token `<'
bash: line 1: `<!DOCTYPE html>'
```

**PowerShell，解析錯誤**：錯誤指向傳回的頁面，`iex` 嘗試將 HTML 和 CSS 當作 PowerShell 執行。

```text theme={null}
iex : At line:1 char:2310
+ ... igin="anonymous"/><script type="text/javascript">!function(o,c){var n ...
Missing argument in parameter list.
...
```

措辭因 PowerShell 版本和系統語言而異：您可能會看到 `Missing expression after unary operator '--'` 或帶有 `ParseException` 的 `ParserError`。引用文字中的 HTML 標籤或 CSS 識別此失敗。如果您改用 `-OutFile install.ps1` 下載，保存的檔案是相同的網頁，所以這也無法幫助。

**PowerShell，`System.Xml.XmlDocument`**：錯誤會指出此型別名稱，而非引用頁面內容。

```text theme={null}
System.Xml.XmlDocument : The term 'System.Xml.XmlDocument' is not recognized as the name of a cmdlet, function, script
file, or operable program.
```

當 `irm` 能將回應解析為 XML 時，它會傳回 XML 物件而非文字，接著 `iex` 會嘗試將該物件的型別名稱當作命令執行。安裝指令碼是 PowerShell 程式碼，無法解析為 XML，因此此錯誤同樣表示回應並非指令碼。型別名稱周圍的措辭因 PowerShell 版本和系統語言而異，但 `System.Xml.XmlDocument` 本身保持不變，因此請以型別名稱比對。

**CMD**：您會看到此錯誤，後面接著傳回頁面的 HTML。

```text theme={null}
< was unexpected at this time.

C:\Users\you><!DOCTYPE html>...
```

第一行會以您的系統語言顯示，因此請尋找其後的 HTML。

**沒有頁面的 403**：根據請求的路由方式，curl 會報告 403 狀態且沒有 HTML 主體。

```text theme={null}
curl: (22) The requested URL returned error: 403
```

這些都表示安裝 URL 傳回了網頁、XML 文件或錯誤狀態，而非安裝指令碼。如果錯誤輸出引用了「App unavailable in region」，Claude Code 在您的國家/地區不可用。請參閱[支援的國家/地區](https://www.anthropic.com/supported-countries)。

沒有主體的單純 403 通常有相同的原因，但也可能來自公司代理伺服器或防火牆阻止下載。如果您在支援的國家/地區但仍然看到 403，在嘗試下面的替代安裝程式前，請先完成[檢查網路連線](#check-network-connectivity)，因為這些會連線到相同的主機。

否則，這可能由於網路問題、區域路由或暫時服務中斷而發生。

**解決方案：**

1. **幾分鐘後重試**：問題通常是暫時的。等待並再次嘗試原始命令。

2. **使用替代安裝方法**：與原生安裝不同，Homebrew 或 WinGet 安裝[預設不會自動更新](https://code.claude.com/docs/zh-TW/setup.md#auto-updates)。

   在 macOS 上，透過 Homebrew 安裝：

   ```bash theme={null}
   brew install --cask claude-code
   ```

   在 Windows 上，透過 WinGet 安裝：

   ```powershell theme={null}
   winget install Anthropic.ClaudeCode
   ```

   然後執行 `claude --version` 以確認：命令列印版本號，例如 `2.1.211 (Claude Code)`。如果 shell 報告找不到 `claude`，開啟新的終端機視窗並重試：您安裝的工作階段保留其舊的 `PATH`。

### 安裝後 `command not found: claude`

安裝完成但 `claude` 無法運作。確切的錯誤因平台而異：

| 平台 | 錯誤訊息 |
| :- | :- |
| macOS | `zsh: command not found: claude` |
| Linux | `bash: claude: command not found` |
| Windows CMD | `'claude' is not recognized as an internal or external command` |
| PowerShell | `claude : The term 'claude' is not recognized as the name of a cmdlet` |

在 Windows 上，如果錯誤是在 Claude Code 更新後立即開始出現，請參閱[從備份還原 `claude.exe`](#claude-exe-missing-after-an-update-on-windows)。

否則，請參閱[驗證您的 PATH](#verify-your-path) 以取得每個平台上的修復。

### 新增至 PATH 時出現 `permission denied`

如果將 `~/.local/bin` 新增到 PATH 的 `echo` 命令列印 `zsh: permission denied: /Users/you/.zshrc` 或 `bash: /home/you/.bashrc: Permission denied`，表示您的使用者無法寫入該檔案，且沒有任何內容被儲存。在終端機中檢查該檔案的擁有者，並以您 shell 的檔案名稱取代 `~/.zshrc`：

```bash theme={null}
ls -l ~/.zshrc
```

輸出的第三個欄位是擁有者。

* **擁有者是其他使用者，例如 `root`**：使用 `sudo chown $(whoami) ~/.zshrc` 取得擁有權，這需要管理員權限。
* **擁有者是您**：該檔案為唯讀。使用 `chmod u+w ~/.zshrc` 使其可寫入。

然後再次執行[驗證您的 PATH](#verify-your-path) 中適用於您 shell 的兩個 PATH 命令。

### `curl: (56) Failure writing output to destination`

`curl ... | bash` 命令下載指令碼並將其傳送到 Bash 以執行。此錯誤以及相關的 `curl: (23) Failure writing output to destination` 表示 Bash 未收到完整的指令碼。退出碼 56 表示下載本身被中斷，退出碼 23 表示 curl 無法將其收到的內容寫入管道，通常是因為 Bash 提前結束。

測試您是否可以連線到 `downloads.claude.ai`，請參閱[檢查網路連線](#check-network-connectivity)中的檢查。如果您連線到伺服器，原始失敗可能是間歇性的；重試安裝命令。您也可以[嘗試替代安裝方法](https://code.claude.com/docs/zh-TW/setup.md#install-claude-code)。

### Homebrew cask 無法使用或已過時

Homebrew 報告 `Error: Cask 'claude-code' is unavailable: No Cask with this name exists` 當您的 Homebrew cask 索引本機副本早於 cask 的發佈時間。重新整理索引並重試：

```bash theme={null}
brew update
brew install --cask claude-code
```

如果 Homebrew 安裝的 Claude Code 版本比您預期的舊，通常是相同的過時索引導致的。`claude-code` cask 追蹤穩定通道，通常比最新版本晚約一週；若要取得最新版本，請改為執行 `brew install --cask claude-code@latest`。請參閱[設定發布通道](https://code.claude.com/docs/zh-TW/setup.md#configure-release-channel) 以了解兩個 cask 之間的差異。

### `Cask 'claude-code@latest' is not installed`

Homebrew 提供兩個 cask：`claude-code` 和 `claude-code@latest`。當已安裝的不是該 cask 時執行 `brew upgrade --cask claude-code@latest`，會列印 `Error: Cask 'claude-code@latest' is not installed.`。若要查看您安裝的是哪個 cask，請在終端機中執行：

```bash theme={null}
brew list --cask | grep claude-code
```

升級它所列印的 cask。如果沒有列印任何內容，表示兩個 cask 都未安裝。

### TLS 或 SSL 連線錯誤

以下這類錯誤表示 TLS 握手失敗：

* `curl: (35) TLS connect error`
* `schannel: next InitializeSecurityContext failed`
* PowerShell 的 `Could not create SSL/TLS secure channel`
* PowerShell 的 `Could not establish trust relationship for the SSL/TLS secure channel`

若為 `CRYPT_E_NO_REVOCATION_CHECK` 或 `CRYPT_E_REVOCATION_OFFLINE`，請跳至步驟 4。

**解決方案：**

1. **更新您的系統 CA 憑證**：

   在 Ubuntu/Debian 上：

   ```bash theme={null}
   sudo apt-get update && sudo apt-get install ca-certificates
   ```

   在 macOS 上，系統 curl 使用 Keychain 信任存放區；更新 macOS 本身會更新根憑證。

2. **在 Windows PowerShell 5.1 中，啟用 TLS 1.2**：
   ```powershell theme={null}
   [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
   ```
   然後在同一視窗中執行安裝程式：
   ```powershell theme={null}
   irm https://claude.ai/install.ps1 | iex
   ```

3. **檢查代理伺服器或防火牆干擾**：執行 TLS 檢查的公司代理伺服器可能導致這些錯誤，包括 `unable to get local issuer certificate` 和 `SELF_SIGNED_CERT_IN_CHAIN`。對於安裝步驟，使 install 下載信任您的公司代理伺服器的 CA：

   > [tab] macOS/Linux
   >
   > ```bash theme={null}
   > curl --cacert /path/to/corporate-ca.pem -fsSL https://claude.ai/install.sh | bash
   > ```

   > [tab] Windows PowerShell
   >
   > PowerShell 安裝程式透過 .NET 下載，該 .NET 針對 Windows 憑證存放區驗證 TLS。如果代理伺服器的 CA 憑證尚未在 Windows 存放區中，請要求您的 IT 團隊新增它，然後執行安裝程式：
   >
   > ```powershell theme={null}
   > irm https://claude.ai/install.ps1 | iex
   > ```

   對於安裝後的 Claude Code 本身，設定 `NODE_EXTRA_CA_CERTS` 以便 API 請求信任相同的套件：

   > [tab] macOS/Linux
   >
   > ```bash theme={null}
   > export NODE_EXTRA_CA_CERTS=/path/to/corporate-ca.pem
   > ```

   > [tab] Windows PowerShell
   >
   > ```powershell theme={null}
   > $env:NODE_EXTRA_CA_CERTS = 'C:\path\to\corporate-ca.pem'
   > ```

   如果您沒有憑證檔案，請詢問您的 IT 團隊。您也可以嘗試直接連線以確認代理伺服器是原因。

4. **在 Windows 上，解決被阻止的撤銷檢查**。錯誤 `CRYPT_E_NO_REVOCATION_CHECK (0x80092012)` 和 `CRYPT_E_REVOCATION_OFFLINE (0x80092013)` 表示 curl 已連線到伺服器，但您的網路阻止了憑證撤銷查詢，這在公司防火牆後面很常見。如果失敗的命令是下載 `install.cmd` 的 `curl`，從命令提示字元重新執行它，並新增 `--ssl-revoke-best-effort`：
   ```batch theme={null}
   curl --ssl-revoke-best-effort -fsSL https://claude.ai/install.cmd -o install.cmd && install.cmd && del install.cmd
   ```
   當指令碼自己的下載遇到相同的錯誤時，它會自動使用最佳努力撤銷檢查重試它們，因此旗標僅在您自己執行的命令上需要。最佳努力檢查容許無法連線的撤銷伺服器，但仍然拒絕已知被撤銷的憑證，符合瀏覽器處理撤銷的方式。您也可以透過從 PowerShell 執行 PowerShell 安裝程式來完全避免 curl 的撤銷檢查，該程式透過 .NET 下載，當撤銷伺服器無法連線時不會失敗：
   ```powershell theme={null}
   irm https://claude.ai/install.ps1 | iex
   ```
   您也可以使用 `winget install Anthropic.ClaudeCode` 安裝，這完全避免了 curl。

### `Failed to fetch version from downloads.claude.ai`

安裝程式無法連線到下載伺服器。這通常表示 `downloads.claude.ai` 在您的網路上被阻止。請參閱[檢查網路連線](#check-network-connectivity)。

### The connection dropped while downloading the update

在 `claude install` 或 `claude update` 擷取 Claude Code 二進位檔時，與下載伺服器的連線關閉，且重試未能恢復。當連線中斷、傳輸停滯，或下載的檔案未通過檢查碼驗證時，Claude Code 會重試下載，總共最多三次嘗試。已完成的 HTTP 錯誤（例如 404）不會重試，因為伺服器已經回應。在 v2.1.202 之前，單次連線中斷會立即以單純的錯誤 `aborted` 使下載失敗，而不會重試。

```text theme={null}
The connection dropped while downloading the update (attempt 3/3: aborted). Check your network — proxies sometimes cut off large downloads.
```

括號中的文字指出哪一次嘗試失敗以及底層的網路錯誤。`claude update` 會在 stderr 上於此訊息之前顯示 `Error: Failed to install native update`。

保持連線但未在 10 分鐘內完成的下載，會改以 `Download timed out: exceeded the total deadline` 失敗。Claude Code 不會重試逾時的下載，因為慢到無法在期限內完成的連線，立即重試也同樣無法完成。以下步驟適用於這兩種訊息。

代理伺服器或閘道可能在長時間傳輸完成前將其關閉，而 Claude Code 二進位檔是大型下載。

**處理方式：**

* 再次執行 `claude update`。在其他方面正常的網路上，下載通常會在下一次執行時成功。若為逾時訊息，請從速度較快或較少限流的網路再次執行。
* 如果您的網路需要代理伺服器，請在執行安裝程式或 `claude update` 之前設定 `HTTPS_PROXY`。請參閱[檢查網路連線](#check-network-connectivity)。
* 如果公司代理伺服器持續關閉傳輸，請要求您的網路團隊允許從 `downloads.claude.ai` 進行完整下載。請參閱[網路存取需求](https://code.claude.com/docs/zh-TW/network-config.md#network-access-requirements)。
* 從您的 shell 執行 `claude doctor` 以取得安裝診斷

### Release verification failed for Claude Code

來自 `claude update` 或 `claude install` 的此訊息表示 Claude Code 無法確認即將安裝的版本是否為真實版本，因此未安裝任何內容。您已擁有的任何版本都會繼續運作。

```text theme={null}
Release verification failed for Claude Code <version> (<reason>). The update was not installed.
```

請依照訊息中括號內的值採取對應的步驟：

* **以 `sidecar_fetch_` 開頭的值**：從您的 shell 再次執行相同的命令。如果 `claude update` 列印以 `Successfully updated from` 開頭的行，表示已成功；如果 `claude install` 列印 `Claude Code successfully installed!`，表示已成功。
* **任何其他值**：稍後再次嘗試相同的命令

無論值為何，如果訊息重複出現，請[回報問題](#still-stuck)並附上完整訊息。

### 工作階段頁尾中的 `Auto-update failed · Run claude doctor`

這行紅色文字表示 Claude Code 嘗試在背景自行更新，但更新未能安裝。您無需執行任何動作即可繼續工作。

此行會引導您執行 `claude doctor`，但其 `Last update attempt: failed (install_failed)` 行只提供日期，不提供原因。若要完成更新或查看失敗原因，請改為在您的 shell 中執行 `claude update`。如果該安裝也失敗，請在[找出您的錯誤](#find-your-error)中尋找 `claude update` 列印的錯誤。

### Windows 上的錯誤安裝命令

如果您看到 `'irm' is not recognized`、`The token '&&' is not a valid statement separator`、`A parameter cannot be found that matches parameter name 'fsSL'` 或 `'bash' is not recognized as the name of a cmdlet`，您複製了不同 shell 或作業系統的安裝命令。如果命令列印指令碼的文字而不是安裝任何東西，您只執行了它的一部分。

* **`irm` 未被識別**：您在 CMD 中，而非 PowerShell。您有兩個選項：

  透過在開始功能表中搜尋「PowerShell」開啟 PowerShell，然後執行原始安裝命令：

  ```powershell theme={null}
  irm https://claude.ai/install.ps1 | iex
  ```

  或留在 CMD 中並改用 CMD 安裝程式：

  ```batch theme={null}
  curl -fsSL https://claude.ai/install.cmd -o install.cmd && install.cmd && del install.cmd
  ```

* **`&&` 不是有效的陳述式分隔符號**：您在 PowerShell 中但執行了 CMD 安裝程式命令。使用 PowerShell 安裝程式：
  ```powershell theme={null}
  irm https://claude.ai/install.ps1 | iex
  ```

* **`A parameter cannot be found that matches parameter name 'fsSL'`**：您在 Windows PowerShell 中執行了 macOS/Linux `curl -fsSL ... | bash` 安裝程式，其中 `curl` 是 `Invoke-WebRequest` 的別名，會拒絕 `-fsSL` 旗標。改用 PowerShell 安裝程式：
  ```powershell theme={null}
  irm https://claude.ai/install.ps1 | iex
  ```

* **`bash` 未被識別**：您在 Windows 上執行了 macOS/Linux 安裝程式。改用 PowerShell 安裝程式：
  ```powershell theme={null}
  irm https://claude.ai/install.ps1 | iex
  ```

* **命令列印指令碼文字而不是安裝**：您執行了命令的下載部分，但沒有執行它的部分。`irm https://claude.ai/install.ps1` 單獨會將下載的指令碼列印到終端機。將其傳送到 `iex` 以執行它：

  ```powershell theme={null}
  irm https://claude.ai/install.ps1 | iex
  ```

  在 CMD 中，`curl -fsSL https://claude.ai/install.cmd` 沒有 `-o` 會列印批次指令碼而不是保存它。執行完整命令：

  ```batch theme={null}
  curl -fsSL https://claude.ai/install.cmd -o install.cmd && install.cmd && del install.cmd
  ```

無論您使用哪個安裝程式，確認它有效：開啟新的終端機並執行 `claude --version`，它列印版本號，例如 `2.1.211 (Claude Code)`。

### `running scripts is disabled on this system`

在 Windows 上透過 npm 安裝或執行 Claude Code 可能因 `SecurityError` 而失敗：

```text theme={null}
npm : File C:\Program Files\nodejs\npm.ps1 cannot be loaded because running scripts is disabled on this system. For more information, see about_Execution_Policies at https:/go.microsoft.com/fwlink/?LinkID=135170.
...
    + CategoryInfo          : SecurityError: (:) [], PSSecurityException
```

當您在 npm 安裝後執行 `claude` 時，相同的錯誤名稱 `claude.ps1`。PowerShell 的執行原則正在阻止 npm 為其命令建立的 `.ps1` 啟動器指令碼。該原則適用於指令碼檔案，因此它不影響 PowerShell 安裝程式 `irm https://claude.ai/install.ps1 | iex`，它直接執行下載的文字。

**解決方案：**

1. **允許您的使用者本機建立的指令碼**，然後重試：
   ```powershell theme={null}
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```
2. **改為呼叫 `.cmd` 啟動器**：`npm.cmd` 和 `claude.cmd` 做相同的工作，該原則不涵蓋它們。
3. **改用 [PowerShell 安裝程式](https://code.claude.com/docs/zh-TW/setup.md#install-claude-code)**，而不是 npm。它安裝二進位檔而不是 `.ps1` 指令碼。

### Windows 安裝期間的 `The process cannot access the file`

如果 PowerShell 安裝程式因 `Failed to download binary: The process cannot access the file ... because it is being used by another process` 而失敗，安裝程式無法寫入 `%USERPROFILE%\.claude\downloads`。這通常表示先前的安裝嘗試仍在執行，或防毒軟體正在掃描該資料夾中部分下載的二進位檔。

關閉任何其他執行安裝程式的 PowerShell 視窗，並等待防毒軟體掃描釋放該檔案。然後刪除下載資料夾並再次執行安裝程式：

```powershell theme={null}
Remove-Item -Recurse -Force "$env:USERPROFILE\.claude\downloads"
irm https://claude.ai/install.ps1 | iex
```

### Windows 上更新後 `claude.exe` 遺失

如果您的終端機在 Claude Code 在 Windows 上更新後報告 `'claude' is not recognized`，請檢查 `%USERPROFILE%\.local\bin` 是否仍然包含 `claude.exe`。如果該目錄根本不在您的 PATH 上，請改為參閱[驗證您的 PATH](#verify-your-path)。若要在 Windows 上更新，Claude Code 會將現有的 `claude.exe` 重新命名為備份，並將新版本移動到其位置。如果將新版本移動到位置失敗，Claude Code 也無法重新命名備份，該目錄會保留備份但沒有 `claude.exe`。

備份是同一目錄中的檔案，其名稱以 `claude.exe.old.` 開頭，後跟數字時間戳。在 PowerShell 中執行以下命令，將最新的備份重新命名回 `claude.exe`：

```powershell theme={null}
Get-ChildItem "$env:USERPROFILE\.local\bin\claude.exe.old.*" | Sort-Object Name | Select-Object -Last 1 | Rename-Item -NewName claude.exe
```

然後執行 `claude --version` 以確認修復。已還原的 `claude.exe` 列印版本號。

如果沒有 `claude.exe.old.*` 檔案，或 `claude` 在重新命名後仍然失敗，改為重新安裝：

```powershell theme={null}
irm https://claude.ai/install.ps1 | iex
```

在 v2.1.281 之前，Claude Code 可能在 `claude.exe` 仍然遺失時刪除備份。

### 低記憶體 Linux 伺服器上安裝被終止

在安裝期間出現 `Killed` 訊息通常表示 Linux 記憶體不足 (OOM) 殺手終止了 `claude install` 步驟，因為系統用盡了可用記憶體。這在小型 VPS 和雲端執行個體上很常見。安裝指令碼報告原因並以代碼 137 結束。在此範例中，行號和程序 ID 因版本和執行而異：

```text theme={null}
Setting up Claude Code...
bash: line 183: 34803 Killed    "$binary_path" install ${TARGET:+"$TARGET"}
Installation was killed before it could finish (exit code 137). This usually means the system ran out of memory.
Claude Code needs roughly 512MB of free memory to install. Free up memory, then run this script again.
```

安裝需要大約 512 MB 的可用記憶體，執行 Claude Code 需要更多。請參閱[系統需求](https://code.claude.com/docs/zh-TW/setup.md#system-requirements)。

**解決方案：**

1. **新增交換空間**（如果您的伺服器 RAM 有限）。交換使用磁碟空間作為溢出記憶體，讓安裝即使在低物理 RAM 的情況下也能完成。

   建立 2 GB 交換檔案並啟用它：

   ```bash theme={null}
   sudo fallocate -l 2G /swapfile
   sudo chmod 600 /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   ```

   然後重試安裝：

   ```bash theme={null}
   curl -fsSL https://claude.ai/install.sh | bash
   ```

2. **在安裝前關閉其他程序**以釋放記憶體。

3. **如果可能，使用更大的執行個體**。Claude Code 需要至少 4 GB 的 RAM。

### Installation was killed before it could finish

當 `claude install` 步驟被訊號終止時，安裝指令碼會回報。在 Linux 上，退出碼 137 表示程序收到 SIGKILL，而在低記憶體主機上，這通常是核心的記憶體不足 (OOM) 殺手。指令碼會列印此說明並以代碼 137 結束：

```text theme={null}
Installation was killed before it could finish (exit code 137). This usually means the system ran out of memory.
Claude Code needs roughly 512MB of free memory to install. Free up memory, then run this script again.
```

對於任何其他致命訊號，以及 macOS 上的退出碼 137，指令碼會列印 `Installation was killed before it could finish (exit code <N>)` 並附上實際的退出碼，且省略記憶體不足的說明。此訊息來自 macOS 和 Linux 使用的安裝指令碼，該指令碼也涵蓋 WSL 內的安裝；原生 Windows 安裝指令碼永遠不會列印此訊息。在 v2.1.200 之前，指令碼結束時只有 shell 單純的 `Killed` 行。

**處理方式：**

* 停止其他程序以釋放記憶體，然後重新執行安裝程式
* 新增交換空間或改用更大的執行個體。如需交換檔案命令，請參閱[低記憶體 Linux 伺服器上安裝被終止](#install-killed-on-low-memory-linux-servers)。

### Docker 中安裝掛起

在 Docker 容器中安裝 Claude Code 時，以 root 身份安裝到 `/` 可能導致掛起。

**解決方案：**

1. **在執行安裝程式前設定工作目錄**。在 `/` 執行時，安裝程式掃描整個檔案系統，導致過度的記憶體使用。設定 `WORKDIR` 將掃描限制在小目錄：
   ```dockerfile theme={null}
   WORKDIR /tmp
   RUN curl -fsSL https://claude.ai/install.sh | bash
   ```

2. **如果使用 Docker Desktop，請增加 Docker 記憶體**。建置容器共享分配給 Docker Desktop 虛擬機器的記憶體，因此開啟 Docker Desktop 中的 **Settings > Resources**，提高記憶體限制，然後重新執行建置。

### 安裝期間的 `Raw mode is not supported`

當您的組織的[伺服器管理的設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)包含需要[安全性核准](https://code.claude.com/docs/zh-TW/server-managed-settings.md#security-approval-dialogs)的變更時，Claude Code 2.1.246 之前的版本嘗試在 `claude install` 期間顯示核准對話方塊。對話方塊需要 stdin 上的終端機。當安裝程式從管道執行 `claude install` 時，如 `curl -fsSL https://claude.ai/install.sh | bash` 所做的，stdin 是管道而不是終端機，因此安裝因包含 `Raw mode is not supported` 的錯誤而失敗。

Claude Code v2.1.246 及更新版本在 `claude install` 或 `claude update` 期間不顯示對話方塊。命令使用您上次核准的設定執行，Claude Code 在您的下一個互動工作階段中顯示對話方塊。如果您的組織的啟動設定[等待設定擷取](https://code.claude.com/docs/zh-TW/server-managed-settings.md#enforce-fail-closed-startup)，例如當它設定 `forceRemoteSettingsRefresh` 時，對話方塊仍會在這些命令期間出現，從管道執行的安裝仍會失敗。

在每個其他設定中，重新執行安裝程式會超過此錯誤，因為即使您要求它安裝舊版本，指令碼也會執行最新版本的 `install` 命令。為您的平台重新執行命令：

> [tab] macOS/Linux
>
> ```bash theme={null}
> curl -fsSL https://claude.ai/install.sh | bash
> ```

> [tab] Windows PowerShell
>
> ```powershell theme={null}
> irm https://claude.ai/install.ps1 | iex
> ```

`claude --version` 列印重新執行安裝的版本。

### `claude update` 或 `claude doctor` 掛起

`claude update` 和 `claude doctor` 掃描您的 shell 設定檔以尋找過時的 `claude` 別名：`~/.zshrc`、`~/.bashrc` 和 `~/.config/fish/config.fish`，加上在 macOS 上存在的 `~/.bash_profile`、`~/.bash_login` 或 `~/.profile` 中的第一個。如果您設定 `ZDOTDIR`，Zsh 檔案是 `$ZDOTDIR/.zshrc`。當這些路徑之一是目錄時，Claude Code 會跳過它，兩個命令都正常完成。在 v2.1.214 之前，這些路徑之一的目錄使兩個命令掛起，並使 `/status` 的系統診斷部分保持空白。`claude doctor` 掛起且沒有輸出；`claude update` 在列印 `Checking for updates` 後立即掛起。

如果您在較早版本上遇到掛起，請找到目錄。在此命令的輸出中，以 `d` 開頭的行將該路徑標記為目錄。`No such file or directory` 行表示該路徑上沒有任何內容，不是原因：

```bash theme={null}
ls -ld ~/.zshrc ~/.bashrc ~/.bash_profile ~/.bash_login ~/.profile ~/.config/fish/config.fish
```

將目錄移到一邊，或更新到 v2.1.214 或更新版本。由於 `claude update` 在受影響的版本上掛起，改為透過重新執行[安裝指令碼](https://code.claude.com/docs/zh-TW/setup.md#install-claude-code)進行更新。

### Claude Desktop 在 Windows 上覆寫 `claude` 命令

如果您安裝了舊版本的 Claude Desktop，它可能在 `WindowsApps` 目錄中註冊 `Claude.exe`，其 PATH 優先級高於 Claude Code CLI。執行 `claude` 會開啟 Desktop 應用程式而非 CLI。

更新 Claude Desktop 到最新版本以修復此問題。

### Windows 上的 Claude Code 需要 Git for Windows（用於 bash）或 PowerShell

Git for Windows 是選用的。Claude Code 在缺少 Git Bash 時使用 [PowerShell 工具](https://code.claude.com/docs/zh-TW/tools-reference.md#powershell-tool)，因此此錯誤表示找不到任何一個 shell。

**如果 PowerShell 不在您的 PATH 中**，其預設位置是 `C:\Windows\System32\WindowsPowerShell\v1.0\`。將該目錄新增到您的 `PATH`，或安裝 [PowerShell 7](https://aka.ms/powershell)，它提供 `pwsh`。

**若要改為安裝 Git for Windows**，請從 [git-scm.com/downloads/win](https://git-scm.com/downloads/win) 下載。在設定期間，選擇「Add to PATH」。安裝後重新啟動您的終端機。安裝它會啟用 Bash 工具，在使用基於 Bash 的指令碼和工具時很有用。

**如果 Git 已安裝**但 Claude Code 找不到它，請比較其位置與 Claude Code 檢查的位置。當 `CLAUDE_CODE_GIT_BASH_PATH` 未設定時，Claude Code 按此順序尋找 `bash.exe`：

1. 預設安裝位置 `C:\Program Files\Git` 和 `C:\Program Files (x86)\Git`。
2. 您的 `PATH` 上的 `git`，使用該 Git 安裝中的 `bin\bash.exe`。

在步驟 2 中，Claude Code 跳過位於您啟動 Claude Code 的資料夾中的 `git`，或在包含 `node_modules` 或虛擬環境資料夾（例如 `.venv` 或 `env`）的路徑下方，例如當您從 `C:\dev\env\myproject` 啟動時的 `C:\dev\env\myproject\Git`。這可防止 Claude Code 執行專案放在那裡的可執行檔。如果您的 Git 在這樣的位置，請將 `CLAUDE_CODE_GIT_BASH_PATH` 指向它。

**若要將 Claude Code 指向特定的 Git 安裝**，透過在 PowerShell 中執行 `where.exe git` 找到它，然後在您的 [settings.json 檔案](https://code.claude.com/docs/zh-TW/settings.md)中將該安裝中的 `bin\bash.exe` 路徑設定為 `CLAUDE_CODE_GIT_BASH_PATH`：

```json theme={null}
{
  "env": {
    "CLAUDE_CODE_GIT_BASH_PATH": "C:\\Program Files\\Git\\bin\\bash.exe"
  }
}
```

**如果 `CLAUDE_CODE_GIT_BASH_PATH` 設定為正確的路徑且檔案存在**但 Claude Code 仍然不使用它，請先檢查檔案的名稱。Claude Code 僅接受名為 `bash.exe`、`sh.exe`、`bash` 或 `sh` 的檔案；使用任何其他名稱（例如 Git for Windows 的 `git-bash.exe` 啟動器），它會忽略變數並自動偵測 Git Bash，就像它未設定一樣，記錄可透過 `--debug` 看到的警告。不存在的路徑會得到相同的備援和警告。在 v2.1.219 之前，Claude Code 使用任何現有檔案作為 shell，而不檢查其名稱，當路徑不存在時在啟動時以 `Claude Code was unable to find CLAUDE_CODE_GIT_BASH_PATH path` 結束。

如果檔案的名稱正確，端點安全軟體（例如 AppLocker、群組原則軟體限制原則或 EDR agent）可能正在干擾。要求您的 IT 團隊在您的端點保護原則中將 `claude.exe` 和它生成的程序（包括 `cmd.exe` 和 `bash.exe`）加入允許清單。

### Claude Code 不支援 32 位元 Windows

Windows 在開始功能表中包含兩個 PowerShell 項目：`Windows PowerShell` 和 `Windows PowerShell (x86)`。x86 項目以 32 位元程序執行，即使在 64 位元機器上也會觸發此錯誤。要檢查您在哪種情況下，請在產生錯誤的同一視窗中執行此命令：

```powershell theme={null}
[Environment]::Is64BitOperatingSystem
```

如果這列印 `True`，您的作業系統沒問題。關閉視窗，開啟不帶 x86 後綴的 `Windows PowerShell`，然後再次執行安裝命令。

如果這列印 `False`，您在 32 位元版本的 Windows 上。Claude Code 需要 64 位元作業系統。請參閱[系統需求](https://code.claude.com/docs/zh-TW/setup.md#system-requirements)。

### Linux musl 或 glibc 二進位不相符

如果在安裝後看到有關遺失共用程式庫的錯誤，如 `libstdc++.so.6` 或 `libgcc_s.so.1`，安裝程式可能為您的系統下載了錯誤的二進位變體。

```text theme={null}
Error loading shared library libstdc++.so.6: No such file or directory
```

這可能發生在已安裝 musl 交叉編譯套件的基於 glibc 的系統上，導致安裝程式將系統誤檢測為 musl。

**解決方案：**

1. **檢查您的系統使用哪個 libc**：
   ```bash theme={null}
   ldd --version 2>&1 | head -1
   ```
   提及 `GNU libc` 或 `GLIBC` 的輸出表示 glibc。提及 `musl` 的輸出表示 musl。

2. **如果您在 glibc 上但得到了 musl 二進位檔**，移除安裝並重新安裝。您也可以使用 `https://downloads.claude.ai/claude-code-releases/{VERSION}/manifest.json` 上的清單手動下載正確的二進位檔。使用 `ldd --version` 和 `ls /lib/libc.musl*` 的輸出提交 [GitHub 問題](https://github.com/anthropics/claude-code/issues)。

3. **如果您實際上在 musl 上**，例如 Alpine Linux，請安裝所需的套件：
   ```bash theme={null}
   apk add libgcc libstdc++ ripgrep
   ```
   在 Alpine 上，`ripgrep` 在社群儲存庫中。如果 `apk` 報告套件遺失，請參閱 [Alpine Linux 設定](https://code.claude.com/docs/zh-TW/setup.md#alpine-linux-and-musl-based-distributions)。

### `Illegal instruction`

如果執行 `claude` 或安裝程式列印 `Illegal instruction`，原生二進位檔使用您的處理器不支援的 CPU 指令。有兩個不同的原因。

**架構不相符。** 安裝程式下載了錯誤的二進位檔，例如在 ARM 伺服器上的 x86。在 macOS 或 Linux 上使用 `uname -m` 檢查，或在 PowerShell 中使用 `$env:PROCESSOR_ARCHITECTURE`。如果結果與您收到的二進位檔不相符，[提交 GitHub 問題](https://github.com/anthropics/claude-code/issues)並附上輸出。

**遺失 AVX 指令集。** 如果您的架構正確但仍然看到 `Illegal instruction`，您的 CPU 可能缺少 AVX 或二進位檔需要的其他指令。這影響大約 2013 年之前的 Intel 和 AMD 處理器，以及超管理程式不將 AVX 傳遞給客體的虛擬機器。

在 VPS 或 VM 上，執行 `grep -m1 -ow avx /proc/cpuinfo`；空結果表示 AVX 對客體不可用。

沒有原生二進位檔解決方法；追蹤[問題 #50384](https://github.com/anthropics/claude-code/issues/50384) 以取得狀態，並在報告時包含您的 CPU 型號，從 Linux 上的 `grep -m1 "model name" /proc/cpuinfo` 或 macOS 上的 `sysctl -n machdep.cpu.brand_string`。

替代安裝方法下載相同的原生二進位檔，不會解決任一原因。

### macOS 上的 `dyld: cannot load`

如果在安裝期間看到 `dyld: Symbol not found`、`dyld: cannot load` 或 `Abort trap: 6`，二進位檔與您的 macOS 版本或硬體不相容。

參考 `libicucore` 的 `Symbol not found` 錯誤表示您的 macOS 版本比二進位檔支援的版本更舊：

```text theme={null}
dyld: Symbol not found: _ubrk_clone
  Referenced from: claude-darwin-x64 (which was built for Mac OS X 13.0)
  Expected in: /usr/lib/libicucore.A.dylib
```

載入器可以改為拒絕二進位檔的載入命令，這也表示您的 macOS 版本太舊：

```text theme={null}
dyld: cannot load 'claude-2.1.42-darwin-x64' (load command 0x80000034 is unknown)
Abort trap: 6
```

**解決方案：**

1. **檢查您的 macOS 版本**：Claude Code 需要 macOS 13.0 或更新版本。開啟 Apple 功能表並選擇「關於本機」以檢查您的版本。

2. **更新 macOS**（如果您在舊版本上）。二進位檔使用舊 macOS 版本不支援的載入命令和系統程式庫。Homebrew 等替代安裝方法下載相同的二進位檔，不會解決此錯誤。

### 工作階段執行期間出現 `Bus error`

如果正在執行的工作階段結束，且您的 shell 列印 `Bus error`，其中一個原因是 Claude Code 無法再從磁碟讀取其自身的可執行檔。例如，該檔案在工作階段執行期間被截斷，或在網路儲存空間上被刪除。

在 shell 的訊息之前，Claude Code 的執行階段可能會列印一份當機報告，其中包含 `panic(main thread): Bus error at address` 和 `oh no: Bun has crashed. This indicates a bug in Bun, not your code.`。當可執行檔變得無法讀取時，當機來自無法讀取的檔案，而非 Bun 中的錯誤。如果執行階段也無法讀取列印報告的程式碼，報告也可能不會出現。

啟動新的工作階段以繼續。如果 Claude Code 安裝在網路儲存空間上，請遵循[在網路儲存空間上安裝](https://code.claude.com/docs/zh-TW/setup.md#install-on-network-storage)，讓升級不會移除執行中的工作階段仍需要的二進位檔。

### WSL1 上的 `Exec format error`

如果在 WSL 中執行 `claude` 列印 `cannot execute binary file: Exec format error`，您在 WSL1 上並遇到[問題 #38788](https://github.com/anthropics/claude-code/issues/38788) 中追蹤的已知原生二進位檔回歸。二進位檔的程式頭以 WSL1 的載入器無法處理的方式改變。

最簡潔的修復是從 PowerShell 將您的發行版轉換為 WSL2：

```powershell theme={null}
wsl --set-version <DistroName> 2
```

如果您需要留在 WSL1 上，透過動態連結器叫用二進位檔。將此函數新增到 WSL 內的 `~/.bashrc`，如果您的家目錄不同，請替換路徑：

```bash theme={null}
claude() {
  /lib64/ld-linux-x86-64.so.2 "$(readlink -f "$HOME/.local/bin/claude")" "$@"
}
```

然後執行 `source ~/.bashrc` 並重試 `claude`。

### WSL 中的 npm 安裝錯誤

如果您在 WSL 內使用 `npm install -g` 安裝了 Claude Code，這些問題適用。如果您使用了[原生安裝程式](https://code.claude.com/docs/zh-TW/setup.md)，請跳過此部分。在 npm 12 上，請依照[修正 npm 12 安裝](#fix-an-npm-12-install)中的說明進行安裝。

**OS 或平台偵測問題。** 如果 npm 在安裝期間報告平台不相符，WSL 可能正在使用 Windows `npm`。首先執行 `npm config set os linux`，然後使用 `npm install -g @anthropic-ai/claude-code --force` 安裝。不要使用 `sudo`。

**執行 `claude` 時的 `exec: node: not found`。** 您的 WSL 環境可能使用 Windows 安裝的 Node.js。使用 `which npm` 和 `which node` 確認：以 `/mnt/c/` 開頭的路徑是 Windows 二進位檔，而 Linux 路徑以 `/usr/` 開頭。要修復此問題，請透過您的 Linux 發行版的套件管理器或透過 [`nvm`](https://github.com/nvm-sh/nvm) 安裝 Node。

**nvm 版本衝突。** 如果您在 WSL 和 Windows 中都安裝了 nvm，在 WSL 中切換 Node 版本可能會中斷，因為 WSL 預設匯入 Windows PATH，Windows nvm 優先。最常見的原因是 nvm 未在您的 shell 中載入。將 nvm 載入器新增到 `~/.bashrc` 或 `~/.zshrc`：

```bash theme={null}
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"
```

或在您的目前工作階段中載入它：

```bash theme={null}
source ~/.nvm/nvm.sh
```

如果 nvm 已載入但 Windows 路徑仍優先，明確地預先設定您的 Linux Node 路徑：

```bash theme={null}
export PATH="$HOME/.nvm/versions/node/$(node -v)/bin:$PATH"
```

> [!WARNING]
>
> 避免透過 `appendWindowsPath = false` 停用 Windows PATH 匯入，因為這會破壞從 WSL 呼叫 Windows 可執行檔的能力。同樣，如果您在 Windows 開發中使用 Node.js，請避免從 Windows 解除安裝它。

### 安裝期間的權限錯誤

如果原生安裝程式因權限錯誤而失敗，目標目錄可能不可寫入。請參閱[檢查目錄權限](#check-directory-permissions)。

如果您之前使用 npm 安裝並遇到 npm 特定的權限錯誤，請切換到原生安裝程式：

```bash theme={null}
curl -fsSL https://claude.ai/install.sh | bash
```

### npm 安裝後找不到原生二進位檔

`@anthropic-ai/claude-code` npm 套件以每個平台的可選相依性（如 `@anthropic-ai/claude-code-darwin-arm64`）下載原生二進位檔。在 `@anthropic-ai/claude-code` 套件的 postinstall 步驟執行並以該二進位檔取代佔位符之前，`claude` 是佔位符指令碼。如果下載或 postinstall 步驟被跳過，佔位符保留在位置，在 macOS 和 Linux 上執行 `claude` 列印：

```text theme={null}
Error: claude native binary not installed.

Either postinstall did not run (--ignore-scripts, some pnpm configs)
or the platform-native optional dependency was not downloaded
(--omit=optional).

Run the postinstall manually (adjust path for local vs global install):
  node node_modules/@anthropic-ai/claude-code/install.cjs

Or reinstall without --ignore-scripts / --omit=optional.
```

在 Windows 上，`bin/claude.exe` 是相同的 shell 指令碼佔位符而不是真實可執行檔，因此 PowerShell 和 CMD 報告他們無法執行檔案，而不是列印此訊息。

檢查以下原因：

* **npm 12 預設會跳過 postinstall 步驟。** 當您使用 npm 12 安裝或更新 Claude Code 時，npm 仍會完成安裝，但不會執行該步驟。請參閱[修正 npm 12 安裝](#fix-an-npm-12-install)。
* **可選相依性已停用。** 從您的 npm 安裝命令中移除 `--omit=optional`、從 pnpm 移除 `--no-optional` 或從 yarn 移除 `--ignore-optional`，並檢查 `.npmrc` 是否未設定 `optional=false`。然後重新安裝。原生二進位檔僅作為可選相依性提供，因此如果跳過它，沒有 JavaScript 備援，重新執行 `install.cjs` 無法放置從未下載的二進位檔。
* **安裝指令碼已停用。** `--ignore-scripts` 和某些 pnpm 設定跳過 postinstall 步驟，但仍然下載平台套件。執行 `node node_modules/@anthropic-ai/claude-code/install.cjs`，如訊息所建議，或不使用旗標重新安裝。如果 postinstall 根本無法在您的環境中執行，`node node_modules/@anthropic-ai/claude-code/cli-wrapper.cjs` 找到下載的套件並啟動它，代價是每次啟動時額外的 Node 程序。如果包裝器改為列印 `Could not find native binary package`，平台套件從未下載，因此首先修復上面的可選相依性原因。
* **不支援的平台。** 預建二進位檔針對 `darwin-arm64`、`darwin-x64`、`linux-x64`、`linux-arm64`、`linux-x64-musl`、`linux-arm64-musl`、`win32-x64` 和 `win32-arm64` 發佈。Claude Code 不為其他平台提供二進位檔；請參閱[系統需求](https://code.claude.com/docs/zh-TW/setup.md#system-requirements)。在 FreeBSD 上，安裝程式報告平台為不支援。在 v2.1.205 之前，它將 FreeBSD 視為 Linux 並下載了無法執行的二進位檔。
* **公司 npm 鏡像缺少平台套件。** 確保您的登錄鏡像除了元套件外，還鏡像所有八個 `@anthropic-ai/claude-code-*` 平台套件。

#### 修正 npm 12 安裝

如果 `claude` 在 npm 安裝或更新後列印 `Error: claude native binary not installed.`，或在 Windows 上 shell 無法執行它，請執行 `npm --version`。以 `12` 開頭的版本表示，除非您的 npm 設定允許，否則 npm 已跳過 Claude Code 的 postinstall 步驟，而該步驟負責將二進位檔放到位置。若為其他任何版本，請檢查[其他原因](#native-binary-not-found-after-npm-install)。

若要修正 npm 12 安裝，請切換到原生安裝程式或允許該步驟：

* **切換到原生安裝程式**：[使用原生安裝程式安裝](https://code.claude.com/docs/zh-TW/setup.md#install-claude-code)，然後[解除安裝 npm 套件](https://code.claude.com/docs/zh-TW/setup.md#uninstall-with-npm)。之後更新不會使用 npm，因此錯誤不會再出現。
* **繼續使用 npm**：對於全域 npm 安裝，請將 Claude Code 新增至您使用者 npm 設定中的 `allow-scripts`。之後 npm 會在每次後續的安裝和更新時執行 Claude Code 的安裝指令碼，在 `package.json` 未設定 `allowScripts` 的專案安裝中也會執行。

  對於位於 `~/.claude/local` 的本機安裝，請使用原生安裝程式。如果您的 `package.json` 指令碼會呼叫 `npm install`，而您使用 pnpm 9、pnpm 10、Yarn 1 或其他會將此設定傳遞給它們的工具來執行這些指令碼，也請使用原生安裝程式。在 npm 12.1 及更新版本上，一旦儲存此設定，這些安裝可能會以 `EALLOWSCRIPTS` 失敗。

  1. 如果 `npm --version` 列印 12.0.x，請將 npm 更新到 12.1 或更新版本，例如使用 `npm install -g npm@latest`。在 12.0.x 上，一旦儲存此設定，由 `npx` 工具或 `npm run` 指令碼啟動的專案安裝可能會以 `EALLOWSCRIPTS` 失敗。

  2. 執行 `npm config get allow-scripts` 並記下它列出的任何套件，因為下一個命令會取代整個值。儲存設定時將這些套件放在引號內，例如 `"allow-scripts=@anthropic-ai/claude-code,<package>"`：

     ```bash theme={null}
     npm config set "allow-scripts=@anthropic-ai/claude-code" --location=user
     ```

  3. 重新安裝：

     ```bash theme={null}
     npm install -g @anthropic-ai/claude-code
     ```

     如果此步驟或步驟 1 以 `EACCES` 失敗，請切換到原生安裝程式，而不是使用 `sudo` 重新執行。Claude Code 自行更新時會在不使用 `sudo` 的情況下執行 npm，因此自動更新也會以相同方式失敗。

  4. 如果 `claude --version` 未列印版本號，請檢查[其他原因](#native-binary-not-found-after-npm-install)。

  若要復原，請重新設定不含 `@anthropic-ai/claude-code` 的清單，或使用 `npm config delete allow-scripts --location=user` 移除整個清單。在 npm 12 上，錯誤會在您下次更新後再次出現。

### npm `ENOTEMPTY` 錯誤在更新或重新安裝期間

當您在現有安裝上執行 `npm install -g @anthropic-ai/claude-code` 時，npm 在移動舊套件目錄時可能失敗：

```text theme={null}
npm error code ENOTEMPTY
npm error syscall rename
npm error path /home/you/.nvm/versions/node/v22.13.1/lib/node_modules/@anthropic-ai/claude-code
npm error dest /home/you/.nvm/versions/node/v22.13.1/lib/node_modules/@anthropic-ai/.claude-code-tVWAnUUt
npm error errno -39
npm error ENOTEMPTY: directory not empty, rename '...'
```

`npm error path` 行命名 npm 無法移動的目錄。刪除該目錄和其旁邊的任何剩餘 `.claude-code-*` 目錄，較早中斷的執行可能會留下。下面的命令使用 `npm root -g` 找到您的全域套件目錄；如果 `npm error path` 行命名的目錄不在 `npm root -g` 列印的目錄下，例如因為您使用 nvm 切換了 Node 版本，改為刪除錯誤命名的目錄：

> [tab] macOS/Linux
>
> ```bash theme={null}
> rm -rf "$(npm root -g)/@anthropic-ai/claude-code"
> ```
>
> 然後移除任何剩餘的臨時目錄。如果 Zsh 列印 `no matches found`，沒有要移除的：
>
> ```bash theme={null}
> rm -rf "$(npm root -g)/@anthropic-ai/.claude-code-"*
> ```

> [tab] Windows PowerShell
>
> ```powershell theme={null}
> Remove-Item -Recurse -Force "$(npm root -g)/@anthropic-ai/claude-code", "$(npm root -g)/@anthropic-ai/.claude-code-*"
> ```

然後重新安裝。在 npm 12 上，請遵循[修正 npm 12 安裝](#fix-an-npm-12-install)。否則，請執行：

```bash theme={null}
npm install -g @anthropic-ai/claude-code
```

使用 `claude --version` 確認，它列印版本號，例如 `2.1.211 (Claude Code)`。

## 登入和身分驗證

這些部分涉及登入失敗、OAuth 錯誤和 token 問題。

### 重設您的登入

當登入失敗且原因不明顯時，乾淨的重新身分驗證可解決大多數情況：

1. 執行 `/logout` 以完全登出
2. 關閉 Claude Code
3. 使用 `claude` 重新啟動並再次完成身分驗證程序

如果瀏覽器在登入期間未自動開啟，按 `c` 將 OAuth URL 複製到您的剪貼簿，然後手動將其貼到瀏覽器中。當 URL 在狹窄或 SSH 終端機中跨行換行且無法直接點擊時，這也有效。

### OAuth 錯誤：無效代碼

如果您看到 `OAuth error: Invalid code. Please make sure the full code was copied`，登入代碼已過期或在複製貼上期間被截斷。

**解決方案：**

* 在瀏覽器開啟後按 Enter 以重試並快速完成登入
* 如果瀏覽器未自動開啟，輸入 `c` 複製完整 URL
* 如果使用遠端/SSH 工作階段，瀏覽器可能在錯誤的機器上開啟。複製終端機中顯示的 URL 並在您的本地瀏覽器中開啟它。

### 登入後 403 Forbidden

如果您在登入後看到 `API Error: 403 Request not allowed`：

* **Claude Pro/Max/Ultra 使用者**：在 [claude.ai/settings](https://claude.ai/settings) 驗證您的訂閱是否有效
* **Anthropic Console 使用者**：確認您的帳戶具有「Claude Code」或「Developer」角色。管理員在 Console 的「成員」頁面 [platform.claude.com/settings/members](https://platform.claude.com/settings/members) 指派此角色。
* **位於代理伺服器後方**：公司代理伺服器可能干擾 API 請求。請參閱[網路設定](https://code.claude.com/docs/zh-TW/network-config.md)以取得代理伺服器設定。

### Claude Code 存取權未授予此帳戶

如果登入頁面在您從 Claude Code 登入後顯示 `Authorization failed`，並顯示訊息 `Claude Code access has not been granted for this account. Contact your administrator.`，您的 Claude Enterprise 組織已將您的角色設定為「自訂」，且指派給您的群組的任何[自訂角色](https://support.claude.com/en/articles/13930452)都未授予 Claude Code。在「自訂」角色上，您只能從這些自訂角色取得存取權，因此您在 Claude Code 中進行的任何變更都無法解決此錯誤。

要取得存取權：

1. 要求您的 Claude 組織的擁有者將授予 Claude Code 存取權的自訂角色指派給您的其中一個群組，或將您的角色從「自訂」變更為標準角色（例如「使用者」）。擁有者在組織的[角色設定](https://claude.ai/admin-settings/roles)中管理角色。
2. 擁有者進行變更後，執行 `claude` 並再次登入。

### 此組織已停用，但有有效的訂閱

如果您看到 `API Error: 400 ... "This organization has been disabled"`，儘管有有效的 Claude 訂閱，`ANTHROPIC_API_KEY` 環境變數正在覆蓋您的訂閱。這通常發生在舊 API 金鑰（來自先前的雇主或專案）仍在您的 shell 設定檔中時。

當 `ANTHROPIC_API_KEY` 存在且您已核准它時，Claude Code 使用該金鑰而非您訂閱的 OAuth 憑證。在使用 `-p` 旗標的非互動模式下，當存在時始終使用該金鑰。請參閱[身分驗證優先順序](https://code.claude.com/docs/zh-TW/authentication.md#authentication-precedence)以取得完整的解決順序。

要改用您的訂閱，請取消設定環境變數並從您的 shell 設定檔中移除它：

> [tab] macOS/Linux
>
> ```bash theme={null}
> unset ANTHROPIC_API_KEY
> claude
> ```

> [tab] Windows PowerShell
>
> ```powershell theme={null}
> Remove-Item Env:ANTHROPIC_API_KEY
> claude
> ```

檢查 `~/.zshrc`、`~/.bashrc` 或 `~/.profile` 中的 `export ANTHROPIC_API_KEY=...` 行並移除它們以永久進行變更。在 Windows 上，檢查您在 `$PROFILE` 的 PowerShell 設定檔和您的使用者環境變數中的 `ANTHROPIC_API_KEY`。在 Claude Code 內執行 `/status` 以確認哪個身分驗證方法是有效的。

### WSL2、SSH 或容器中的 OAuth 登入失敗

如果沒有開啟瀏覽器，或瀏覽器讓您登入後顯示 `localhost` 位址的連線錯誤，您無需修正這兩個問題中的任何一個即可完成登入。請改為透過終端機在其貼上提示上方顯示的另一個登入 URL 登入：

**1. 複製登入 URL**

在互動式登入提示時，按 `c` 複製 URL，或在終端機中選取它。若使用 `claude auth login`，請複製它列印的 URL。

**2. 透過該 URL 登入**

在您本地機器上的瀏覽器中開啟該 URL 並登入。瀏覽器隨後會顯示代碼，而不是返回 `localhost`。

**3. 貼上代碼**

將該代碼貼到終端機中以 `Paste code here` 開頭的提示。

如果將代碼貼到互動式提示中沒有任何反應，您的終端機的貼上繫結可能無法到達輸入欄位。嘗試您的終端機的替代貼上快捷鍵，通常在 Windows Terminal 中是右鍵點擊或 Shift+Insert，或改用 `claude auth login`，它從標準輸入讀取貼上的代碼：

```bash theme={null}
claude auth login
```

此備援方式也適用於原生 Windows 或任何將代碼貼到互動式提示失敗的終端機。

在 WSL2 上，如果沒有開啟瀏覽器，您也可以將 `BROWSER` 環境變數設定為您的 Windows 瀏覽器路徑，讓 Claude Code 下次開啟該瀏覽器：

```bash theme={null}
export BROWSER="/mnt/c/Program Files/Google/Chrome/Application/chrome.exe"
claude
```

### 未登入或 token 已過期

如果 Claude Code 在工作階段後提示您再次登入，您的 OAuth token 可能已過期。

執行 `/login` 以重新身分驗證。如果這經常發生，請檢查您的系統時鐘是否準確，因為 token 驗證取決於正確的時間戳。

一台機器上的平行工作階段共享已儲存的登入，並協調其更新，以便一次只有一個程序重新整理 token。若要了解您在其中一個工作階段重新登入後其他工作階段會如何處理，請參閱[未登入](https://code.claude.com/docs/zh-TW/errors.md#not-logged-in)。

在 v2.1.211 之前，從睡眠喚醒機器可能導致兩個工作階段使用相同 token 進行更新，這會撤銷已儲存的登入，並提示每個開啟的工作階段立即再次登入。

在 macOS 上，Claude Code 將憑證儲存到登入 Keychain。當 Keychain 拒絕寫入時，例如當它在 SSH 工作階段中被鎖定或其密碼與您的帳戶密碼不同步時，Claude Code 改為將您的登入儲存到純文字 `~/.claude/.credentials.json` 檔案。建立 API 金鑰的 Console 登入會失敗，直到 Keychain 再次可寫入。

要使 Keychain 再次可寫入並將您的登入移回加密的 Keychain：

**1. 檢查 Keychain 存取**

執行 `claude doctor` 以檢查 Keychain 存取。當 Keychain 拒絕寫入時，報告會列出以 `macOS Keychain is not writable` 開頭的警告，後面跟著建議的修正。當報告未列出 Keychain 警告時，Keychain 可寫入，您可以跳到最後一步。

**2. 解鎖 Keychain**

```bash theme={null}
security unlock-keychain ~/Library/Keychains/login.keychain-db
```

當命令要求時輸入您的 Keychain 密碼，然後再次執行 `claude doctor`。當解鎖成功時，報告不再列出 Keychain 警告。

**3. 如果解鎖無幫助，請重新同步 Keychain 密碼**

開啟 Keychain Access，選擇 `login` keychain，並選擇「編輯」>「變更 Keychain 'login' 的密碼」以將其與您的帳戶密碼重新同步。然後再次執行 `claude doctor`。一旦報告不再列出 Keychain 警告，請繼續下一步。

**4. 登出並重新登入**

一旦 Keychain 再次可寫入，Claude Code 會在下次寫入憑證時將憑證移回。要立即強制執行，請執行 `/logout`，然後執行 `/login`。登出會移除所有已儲存的憑證，包括純文字檔案的內容、已儲存的 MCP 伺服器登入和外掛敏感值，因此預期之後需要重新授權 MCP 伺服器和重新輸入外掛祕密。再次登入會將您的登入儲存在 Keychain 中。

### Bedrock、Agent Platform 或 Foundry 憑證未載入

如果您設定了 Claude Code 以使用雲端提供者，並在 Amazon Bedrock 上看到 `Could not load credentials from any providers`、在 Google Cloud 的 Agent Platform 上看到 `Could not load the default credentials` 或在 Microsoft Foundry 上看到 `ChainedTokenCredential authentication failed`，您的雲端提供者 CLI 可能在目前 shell 中未進行身分驗證。

對於 Amazon Bedrock，確認您的 AWS 憑證有效：

```bash theme={null}
aws sts get-caller-identity
```

對於 Google Cloud 的 Agent Platform，確認 `ANTHROPIC_VERTEX_PROJECT_ID` 和 `CLOUD_ML_REGION` 在您的 shell 中設定，然後設定應用程式預設憑證：

```bash theme={null}
gcloud auth application-default login
```

對於 Microsoft Foundry，確認 `ANTHROPIC_FOUNDRY_API_KEY` 已設定，或使用 Azure CLI 登入，以便預設憑證鏈可以找到您的帳戶：

```bash theme={null}
az login
```

如果憑證在您的終端機中有效但在 VS Code 或 JetBrains 擴充功能中無效，IDE 程序可能未繼承您的 shell 環境。在 IDE 自己的設定中設定提供者環境變數，或從已匯出它們的終端機啟動 IDE。

請參閱 [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md)、[Google Cloud 的 Agent Platform](https://code.claude.com/docs/zh-TW/google-vertex-ai.md) 或 [Microsoft Foundry](https://code.claude.com/docs/zh-TW/microsoft-foundry.md) 以取得完整的提供者設定。

## 仍然卡住

如果上述任何方法都無法解決您的問題：

1. 檢查 [GitHub 儲存庫](https://github.com/anthropics/claude-code/issues)以了解已知問題，或使用您的作業系統、您執行的安裝命令和完整錯誤輸出開啟新問題
2. 如果 `claude --version` 有效但其他內容有問題，執行 `claude doctor` 以取得自動診斷報告
3. 如果您可以啟動工作階段，請在 Claude Code 內使用 `/feedback` 報告問題
4. 如果問題與您的帳戶而非安裝有關，例如登入迴圈、無法識別的訂閱或已停用的組織，請聯絡 Anthropic 支援：登入 [claude.ai](https://claude.ai)（Console 使用者：[platform.claude.com](https://platform.claude.com)），點擊左下角的您的首字母縮寫，然後選擇**取得協助**。請參閱[如何取得支援](https://support.claude.com/en/articles/9015913-how-to-get-support)以了解完整流程。

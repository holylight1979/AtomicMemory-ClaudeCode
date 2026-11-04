<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/sandboxing | lastmod: 2026-11-04 | section: Configuration / Permissions and sandboxing -->
> 來源：https://code.claude.com/docs/zh-TW/sandboxing（官方 zh-TW，lastmod 2026-11-04）｜分類：Configuration › Permissions and sandboxing｜EN 摘要：Restrict the files and network hosts Claude Code's shell commands can reach with the built-in sandbox. Turn it on, set the boundary, and fix what it breaks.

# 設定沙箱化的 Bash 工具

> 使用內建沙箱限制 Claude Code 的 shell 命令可存取的檔案與網路主機。啟用沙箱、設定邊界，並修正它所造成的問題。

Bash 沙箱是作業系統在 Claude 於您的電腦上執行的 shell 命令周圍所強制實施的邊界。您可以設定這些命令能存取哪些檔案和網路網域，這些限制適用於 Bash、PowerShell 和 Monitor 命令，以及它們所啟動的程序。由於作業系統會在命令執行期間套用這些限制，Claude Code 可以[執行沙箱化的命令而無需詢問您](#sandbox-modes)是否核准每一個命令。

沙箱僅涵蓋 shell 命令。Claude 的檔案工具、MCP 伺服器和 hook [在沙箱之外執行](#what-runs-outside-the-sandbox)。

沙箱可在 macOS、Linux 和 WSL2 上執行。在原生 Windows 上，Claude Code 會以非沙箱化的方式執行命令。若要在 Windows 電腦上使用沙箱，請在 WSL2 發行版中執行 Claude Code。

> [!NOTE]
>
> 本頁說明您自己電腦上 shell 命令周圍的沙箱。其他頁面涵蓋相關問題：
>
> * 關於雲端工作階段如何被隔離，請參閱[安全性與隔離](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#security-and-isolation)
> * 若要比較其他隔離方式，例如 dev container、自訂容器和虛擬機器，請參閱[沙箱環境](https://code.claude.com/docs/zh-TW/sandbox-environments.md)
> * 若要減少 Bash 以外工具的權限提示，請參閱[權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md)

## 沙箱限制的範圍

啟用沙箱時，Claude 執行的 shell 命令會在其邊界內啟動，這些命令所啟動的程序也是如此。沙箱預設為關閉。若要啟用，請如[開始使用](#get-started)所示，在工作階段中執行 `/sandbox`，或在[設定檔](https://code.claude.com/docs/zh-TW/settings.md)（例如 `~/.claude/settings.json`）中將 [`sandbox.enabled`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-enabled) 設為 `true`。

下表列出沙箱化命令預設可存取的範圍，以及可變更各項預設值的設定。

| 存取 | 預設 | 變更方式 |
| :- | :- | :- |
| 寫入 | 工作目錄、每位使用者專屬的暫存目錄，以及[您新增的目錄](https://code.claude.com/docs/zh-TW/permissions.md#additional-directories-grant-file-access-not-configuration)。[受保護路徑](#protected-paths)仍維持禁止寫入 | [`filesystem.allowWrite`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-filesystem-allowwrite)、[`filesystem.denyWrite`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-filesystem-denywrite) |
| 讀取 | 機器上的大部分內容，包括 `~/.ssh` 和 `~/.aws/credentials` 等憑證檔案 | [`filesystem.denyRead`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-filesystem-denyread)、[`credentials`](#protect-credentials) |
| 網路 | 沒有直接對外的路徑。連線會經過您機器上的代理伺服器，由其將每個主機與您允許的網域（初始為空）進行比對。您的權限模式決定[其他主機會如何處理](#hosts-outside-your-allowed-domains) | [`network.allowedDomains`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-network-alloweddomains)、[`network.deniedDomains`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-network-denieddomains) |
| 環境變數 | 繼承自 Claude Code，包括其環境中的任何機密 | [`credentials`](#protect-credentials)、[`CLAUDE_CODE_SUBPROCESS_ENV_SCRUB`](https://code.claude.com/docs/zh-TW/env-vars) |

Claude Code 的沙箱建置於開放原始碼套件 [`@anthropic-ai/sandbox-runtime`](https://github.com/anthropics/sandbox-runtime) 之上。

### 在沙箱外執行的項目

沙箱包覆的是 shell 命令。以下工具和程序會在沙箱外執行：

* **內建檔案與網頁工具**：Read、Edit、Write、WebFetch 和 WebSearch 等工具改為遵循[權限規則](https://code.claude.com/docs/zh-TW/permissions.md)。`denyRead` 項目不會阻止 Read 工具，`allowedDomains` 也不會限制 WebFetch
* **Claude Code 啟動的其他程序**：命令 [hook](https://code.claude.com/docs/zh-TW/hooks.md)、本機 [MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md)、[外掛監視器](https://code.claude.com/docs/zh-TW/plugins/components.md#monitors)、[LSP 伺服器](https://code.claude.com/docs/zh-TW/tools-reference.md#lsp-tool-behavior)，以及您的[狀態列](https://code.claude.com/docs/zh-TW/statusline.md)命令和 `apiKeyHelper` 等輔助命令，都會以您的完整存取權限執行

視您的設定而定，部分 shell 命令也會在沙箱外執行：

* **您自行輸入的命令**：在大多數工作階段中，您在 [`!` shell 模式提示字元](https://code.claude.com/docs/zh-TW/interactive-mode#shell-mode-with-prefix)輸入的命令會在沙箱外執行。[嚴格沙箱模式](#turn-off-the-retry-with-strict-sandbox-mode)列出了您輸入的命令會在沙箱內執行的工作階段
* **排除的命令**：符合 [`excludedCommands`](#run-commands-outside-the-sandbox-with-excludedcommands) 的命令會在沙箱外執行
* **非沙箱重試**：Claude 可以[要求在沙箱外執行命令](#the-unsandboxed-retry-escape-hatch)，通常是在命令於沙箱中失敗之後

若要將本節中的工具、程序和命令置於同一個邊界之後，請在[容器、虛擬機器或沙箱執行環境](https://code.claude.com/docs/zh-TW/sandbox-environments.md)中執行 Claude Code 程序本身。

## 開始使用

沙箱內建於 Claude Code 中。需要安裝的內容取決於您的平台：

* **macOS**：沙箱機制使用內建的 Seatbelt 框架，因此可以直接進行下列步驟
* **Linux 和 WSL2**：沙箱依賴 `bubblewrap` 和 `socat`，請參閱[設定 Linux 和 WSL2](#set-up-linux-and-wsl2)。即使尚未安裝它們，也可以先執行 `/sandbox`，因為其面板會顯示是否有任何缺少的項目

**1. 執行 /sandbox**

啟動 Claude Code 工作階段並執行 `/sandbox` 命令：

```text theme={null}
/sandbox
```

這會開啟包含三個分頁的沙箱面板；在 Linux 上，若缺少選用的 seccomp 篩選器，還會多出一個 Dependencies 分頁：

* **Mode**：選擇沙箱化命令的核准方式，詳見下一步
* **Overrides**：選擇在沙箱中失敗的命令是否可以退回以非沙箱方式執行。這就是 [`allowUnsandboxedCommands`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-allowunsandboxedcommands) 設定
* **Config**：檢視解析後的沙箱設定

如果面板只顯示 Dependencies 分頁，表示沙箱目前還無法啟動。請依照[設定 Linux 和 WSL2](#set-up-linux-and-wsl2) 中的說明修正該分頁回報的問題，重新啟動 Claude Code，然後再次執行 `/sandbox`。

**2. 選擇模式**

在 Mode 分頁上，選擇 auto-allow 或一般權限。Auto-allow 會執行沙箱化命令而不提示，一般權限則即使命令已沙箱化，仍會保留一般的權限提示。關於在 auto-allow 模式下哪些命令仍會提示，請參閱[沙箱模式](#sandbox-modes)。

**3. 執行 Bash 命令**

請 Claude 執行一個命令，例如建置或測試套件。預設情況下，沙箱內的命令可以寫入工作目錄、[每位使用者的暫存目錄](https://code.claude.com/docs/zh-TW/env-vars.md)，以及透過 `--add-dir`、`/add-dir` 或 `permissions.additionalDirectories` [新增的任何目錄](https://code.claude.com/docs/zh-TW/permissions.md#additional-directories-grant-file-access-not-configuration)。

當命令首次需要新的網路網域時，Claude Code 會提示您核准；在[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)中，Claude 則會[在命令本身上](#per-command-allowed-domains-in-auto-mode)列出該命令所需的主機，供分類器一併審查。

若要擴大或縮小沙箱允許的範圍，請參閱[設定沙箱機制](#configure-sandboxing)。

如果沙箱化命令在容器內因 `Operation not permitted` 而失敗，請參閱[Bubblewrap 無法在容器內啟動](#bubblewrap-fails-to-start-inside-a-container)。

當您在面板中選擇模式時，Claude Code 會將其儲存到專案的本機設定 `.claude/settings.local.json`，該設定適用於目前的專案。Claude Code 在該檔案中儲存設定時，會將其加入您的全域 gitignore。若要在所有專案中啟用沙箱，請在 `~/.claude/settings.json` 的使用者設定中將 [`sandbox.enabled`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-enabled) 設為 `true`。若要對組織中的每位開發人員強制執行沙箱機制，請使用[受管設定](#enforce-sandboxing-with-managed-settings)。

若要在不寫入設定檔的情況下變更單一工作階段的沙箱，請使用 [`--settings`](https://code.claude.com/docs/zh-TW/settings#change-a-setting-for-one-session) 啟動 Claude Code。例如，下列命令會啟動一個沙箱化工作階段，在其中 Claude 無法在沙箱外重試被封鎖的命令：

```bash theme={null}
claude --settings '{"sandbox": {"enabled": true, "allowUnsandboxedCommands": false}}'
```

> [!WARNING]
>
> 預設情況下，當平台不支援沙箱或啟動時的相依性檢查失敗時，Claude Code 會在沒有沙箱機制的情況下執行命令。若要讓 Claude Code 改為在啟動時結束，請將 [`sandbox.failIfUnavailable`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-failifunavailable) 設為 `true`。需要將沙箱機制作為安全關卡的受管部署可以使用此設定。

### 確認命令在沙箱內執行

若要檢查沙箱是否正常運作，請 Claude 執行表格中的每一行。您在 [`!` 提示字元](#what-runs-outside-the-sandbox)輸入的內容通常會在沙箱外執行，因此自行輸入這些命令並不能測試沙箱。

| 命令 | 在沙箱內的結果 |
| :- | :- |
| `touch ~/sandbox-probe` | 在 macOS 上因 `Operation not permitted` 而失敗，在 Linux 和 WSL2 上因 `Read-only file system` 而失敗 |
| `curl --noproxy '*' https://example.com` | 因 `Could not resolve host` 而失敗，因為該命令沒有繞過沙箱代理伺服器的路由 |

如果 Claude 要求在沙箱外重試失敗的命令，請拒絕重試。如果 `touch` 成功，且您的家目錄不屬於沙箱允許命令寫入的目錄之一，請刪除 `~/sandbox-probe`。接著執行 `/sandbox`，檢查沙箱是否已開啟且其相依套件已安裝。

### 設定 Linux 和 WSL2

在 Linux 和 WSL2 上，沙箱依賴下列套件：

* [`bubblewrap`](https://github.com/containers/bubblewrap)：強制執行檔案系統隔離的非特權沙箱工具
* [`socat`](http://www.dest-unreach.org/socat/)：用來將網路流量導向沙箱代理伺服器的中繼程式

使用您發行版的套件管理員安裝它們：

> [tab] Ubuntu/Debian
>
> ```bash theme={null}
> sudo apt-get install bubblewrap socat
> ```

> [tab] Fedora
>
> ```bash theme={null}
> sudo dnf install bubblewrap socat
> ```

當缺少相依套件時，`/sandbox` 中的 Dependencies 分頁會列出您的平台缺少 `ripgrep`、`bubblewrap`、`socat` 和 seccomp 篩選器中的哪些項目。如果在安裝並重新啟動 Claude Code 後沒有看到該分頁，表示所有相依套件都已就緒。

Ripgrep 隨附於原生 Claude Code 二進位檔中。seccomp 篩選器為選用項目，可增加 Unix domain socket 封鎖功能。如果缺少，請使用 `npm install -g @anthropic-ai/sandbox-runtime` 安裝。

* **Dependencies 是唯一的分頁**：沙箱無法啟動。請安裝該分頁列為缺少的項目；如果它回報 Ubuntu 的 AppArmor 限制，請[為 bubblewrap 新增 AppArmor 設定檔](#add-an-apparmor-profile-for-bubblewrap)
* **Dependencies 與其他分頁一起顯示**：該分頁列出了缺少的選用項目，例如 seccomp 篩選器。沙箱在沒有它的情況下仍可啟動，因此只有在您需要它所增加的功能時才需安裝

相依性檢查會在啟動時執行，因此安裝套件後請重新啟動 Claude Code，讓 `/sandbox` 偵測到它們。

> [accordion] WSL2 注意事項
>
> 在 PowerShell 中使用 `wsl -l -v` 檢查您的 WSL 版本。如果看到 `Sandboxing requires WSL2`，表示您的發行版正在執行 WSL1。請將其升級到 WSL2，或在沒有沙箱機制的情況下執行 Claude Code。
>
> 在 WSL2 上，WSL 會透過 Unix socket 將 Windows 二進位檔（例如 `cmd.exe`、`powershell.exe` 或 `/mnt/c/` 下的任何程式）的啟動交給 Windows 主機處理，因此沙箱化命令能否啟動這類程式取決於沙箱的 [Unix socket 設定](https://code.claude.com/docs/zh-TW/settings-reference.md#sandbox-network-allowunixsockets)：必須先安裝選用的 seccomp 篩選器，才能封鎖該 socket。若要允許這些啟動，請設定 `allowAllUnixSockets`，這會向沙箱化命令開放所有 Unix socket。

#### 為 bubblewrap 新增 AppArmor 設定檔

如果 Claude Code 執行的是 `/usr/bin/bwrap`，且發生下列任一情況，請新增此設定檔：

* Claude Code [回報 Ubuntu 對使用者命名空間的 AppArmor 限制](#apparmor-restriction-stops-bubblewrap)
* 在[該限制開啟](#bwrap-uid-map-permission-denied)期間，沙箱化命令因 `bwrap: setting up uid map: Permission denied` 或 `bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted` 而失敗

Claude Code 會執行 `PATH` 上的第一個 `bwrap`，除非受管設定在 [`sandbox.bwrapPath`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-bwrappath) 中指定了一個。若要查看哪個 `bwrap` 排在第一，請在您啟動 Claude Code 的 shell 中執行 `which bwrap`。如果 Claude Code 執行的是 `/usr/bin/bwrap` 以外的任何路徑，請改為[使用 `sysctl` 解除該限制](#apparmor-restriction-stops-bubblewrap)。

若要為 `/usr/bin/bwrap` 新增設定檔，請執行下列命令：

```bash theme={null}
sudo tee /etc/apparmor.d/bwrap > /dev/null <<'EOF'
abi <abi/4.0>,
include <tunables/global>

profile bwrap /usr/bin/bwrap flags=(unconfined) {
  userns,
  include if exists <local/bwrap>
}
EOF
```

重新載入 AppArmor 以套用它：

```bash theme={null}
sudo systemctl reload apparmor
```

接著重新啟動 Claude Code，並[確認沙箱正常運作](#confirm-commands-run-inside-the-sandbox)。

### 沙箱模式

Claude Code 提供兩種沙箱模式。在這兩種模式中，沙箱都會強制執行相同的檔案系統和網路限制；差異僅在於沙箱化命令是自動核准還是需要明確的權限。

#### Auto-allow 模式

當命令在沙箱內執行時，Claude Code 會自動核准該命令，不會提示。當命令因為符合 [`excludedCommands`](#run-commands-outside-the-sandbox-with-excludedcommands) 或因為 Claude [以非沙箱方式重試](#the-unsandboxed-retry-escape-hatch)而在沙箱外執行時，該命令會經過一般的[權限流程](https://code.claude.com/docs/zh-TW/permissions.md)。

連線到您尚未允許之主機的沙箱化命令仍會留在沙箱中。[允許網域以外的主機](#hosts-outside-your-allowed-domains)說明了由誰決定該連線是否放行。

即使在 auto-allow 模式下，下列規則仍然適用：

* 採用 `Bash` 拒絕規則所能比對之[形式](https://code.claude.com/docs/zh-TW/permissions.md#bash-rule-limits)的命令仍會被封鎖
* 經辨識為以[關鍵路徑](https://code.claude.com/docs/zh-TW/permission-modes.md#which-paths-are-critical)為目標的 `rm` 或 `rmdir` 命令仍會經過一般的權限流程
* 以內容為範圍的[詢問規則](https://code.claude.com/docs/zh-TW/permissions.md)（例如 `Bash(git push *)`）即使對沙箱化命令仍會強制提示
* 單純的 `Bash` 詢問規則，或等效的 `Bash(*)` 形式，對於以沙箱方式執行的命令會被略過；對於在沙箱外執行的命令則仍然適用。在 [plan mode](https://code.claude.com/docs/zh-TW/permission-modes.md#analyze-before-you-edit-with-plan-mode) 中，該規則不會被略過：它也會對沙箱化命令（包括唯讀命令）提示
* [Monitor 工具](https://code.claude.com/docs/zh-TW/tools-reference.md#monitor-tool)的命令不會自動核准，但仍會在沙箱中執行。若要略過提示，請新增與該命令相符的[允許規則](https://code.claude.com/docs/zh-TW/permissions.md#bash)，例如 `Bash(npm run *)`

有些沙箱化命令也會經過一般的[權限流程](https://code.claude.com/docs/zh-TW/permissions.md)，而不是自動核准。這種情況會發生在 `FOO=bar npm test` 之類的命令（在命令前設定的變數可能會改變實際執行的程式），以及 `make CC=clang` 或 `eval "ls"`。此時由您的允許規則和權限模式決定是否顯示提示，而該命令仍會在沙箱內執行。

對於這三個命令，與命令相符的[允許規則](https://code.claude.com/docs/zh-TW/permissions.md#bash)可以避免重複出現提示。下列規則示範了此模式：

* `Bash(make *)` 會核准 `make CC=clang`
* `Bash(FOO=bar npm *)` 會核准 `FOO=bar npm test`。當命令以變數指派開頭時，請在規則中包含該指派
* `Bash(eval "ls")` 會核准 `eval "ls"`。萬用字元規則（例如 `Bash(eval *)`）無法避免此提示，因此請撰寫與整個命令相符的規則

與命令相符的允許規則也會核准該命令的[非沙箱重試](#the-unsandboxed-retry-escape-hatch)，因此該命令可以在沙箱外執行而不提示。

> [!NOTE]
>
> Auto-allow 模式獨立於您的權限模式設定運作，但有三個例外：[plan mode](https://code.claude.com/docs/zh-TW/permission-modes.md#analyze-before-you-edit-with-plan-mode)、帶有[每個命令允許網域](#per-command-allowed-domains-in-auto-mode)的自動模式命令，以及自動模式中對沙箱化命令的[伺服器端分類器審查](https://code.claude.com/docs/zh-TW/permission-modes.md#how-the-classifier-evaluates-actions)。即使您不在「accept edits」模式中，啟用 auto-allow 時沙箱化的 Bash 命令也會自動執行。這表示在沙箱邊界內修改檔案的 Bash 命令會在不提示的情況下執行，即使在檔案編輯工具會提示的 Manual 模式中也是如此。
>
> 在 plan mode 中，auto-allow 不會擴大核准範圍；關於 Claude Code 在您規劃時如何管控命令，請參閱 [plan mode](https://code.claude.com/docs/zh-TW/permission-modes.md#analyze-before-you-edit-with-plan-mode)。

#### 一般權限模式

所有 Bash 命令都會經過一般的權限流程，即使已沙箱化也是如此。這提供了更多控制，但需要更多核准。

#### 非沙箱重試的緊急出口

非沙箱重試是為在沙箱內失敗的命令（例如與沙箱不相容的工具）所設的緊急出口。當沙箱封鎖網路連線時，Claude Code 會在命令的結果中指出被拒絕的主機，讓 Claude 看到被封鎖的內容。Claude 會分析失敗原因，並可能使用 `dangerouslyDisableSandbox` 參數重試該命令。

重試的命令會以非沙箱方式執行。在互動式終端機工作階段中，由誰核准取決於您的權限模式：

* **`bypassPermissions` 模式**：重試會在不提示的情況下執行
* **Manual 模式和 `acceptEdits` 模式**：您會收到標題為「Bash command (unsandboxed)」的提示
* **[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)**：由另一個分類器模型評估底層命令
* **`dontAsk` 模式**：Claude Code 會拒絕重試
* **Plan mode**：請參閱 [Claude Code 在您規劃時如何管控命令](https://code.claude.com/docs/zh-TW/permission-modes.md#analyze-before-you-edit-with-plan-mode)

下列規則和設定會改變由誰核准重試：

* **相符的允許規則**：如果允許規則（例如 `Bash(curl *)`）與命令相符，它也會核准重試，因此命令會在沙箱外執行而不提示
* **針對該參數的詢問規則**：為 `Bash(dangerouslyDisableSandbox:true)` 新增一條[詢問規則](https://code.claude.com/docs/zh-TW/permissions.md#match-by-input-parameter)，即可在 Bash 重試時收到提示。在自動模式和 `bypassPermissions` 模式中您也會收到提示，且該規則優先於相符的允許規則
* **[`permissions.blockReadsOutsideWorkingDirectories`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-blockreadsoutsideworkingdirectories)**：[任何模式都不會自動核准的動作](https://code.claude.com/docs/zh-TW/permission-modes.md#actions-no-mode-auto-approves)說明了此設定開啟時會提示的重試

當命令因 [`Sandbox is required` 訊息](#commands-refused-with-sandbox-is-required)而遭拒時，Claude Code 會忽略 `dangerouslyDisableSandbox` 參數，並同樣拒絕重試。

#### 使用嚴格沙箱模式關閉重試

您可以在[沙箱設定](https://code.claude.com/docs/zh-TW/settings-reference.md#sandbox-settings)中設定 `"allowUnsandboxedCommands": false` 來停用非沙箱重試。停用重試後，Claude Code 會忽略 `dangerouslyDisableSandbox` 參數。在沙箱執行期間，Claude 執行的命令除非符合 `excludedCommands` 項目，否則都會被沙箱化。若要在沙箱無法啟動時防止 Claude Code 以非沙箱方式執行命令，請同時設定 [`failIfUnavailable`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-failifunavailable)。`/sandbox` 的 **Overrides** 分頁會將此設定顯示為 **Strict sandbox mode**。

在您的使用者設定、`--settings` 或受管設定中的 `false`，即使專案的設定設為 `true` 也會維持有效。使用者設定中的 `false` 不會讓沙箱成為管理員強制要求，因此專案的其他沙箱設定仍然適用。在 v2.1.285 之前，專案的 `true` 會覆寫您使用者設定中的 `false`。

如果您或您的管理員在受管設定中或透過 `--settings` 旗標停用重試，沙箱就會成為管理員強制要求。Claude Code 接著會忽略儲存庫檔案中放寬沙箱的設定，包括 `excludedCommands` 項目。[管理員強制要求沙箱下的儲存庫設定](#repository-settings-under-an-admin-required-sandbox)列出了這些設定。

嚴格沙箱模式適用於 Claude 執行的命令。您自行在 [`!` shell 模式提示字元](https://code.claude.com/docs/zh-TW/interactive-mode#shell-mode-with-prefix)輸入的命令會在沙箱外執行，除非工作階段屬於下列情況之一：

* **[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)**：嚴格沙箱模式也涵蓋 shell 模式命令
* **設定了 [`CLAUDE_CODE_SUBPROCESS_ENV_SCRUB`](https://code.claude.com/docs/zh-TW/env-vars#variables) 的 Linux 工作階段**：每個命令都會以沙箱方式執行，包括 shell 模式命令

在 v2.1.260 之前，嚴格沙箱模式會在每個工作階段中將 shell 模式命令沙箱化。

#### 暫存目錄

預設情況下，除了工作目錄之外，每位使用者的暫存目錄在沙箱內也是可寫入的。除非您[停用檔案系統隔離](#disable-filesystem-isolation)，否則 Claude Code 會為沙箱化命令將 `$TMPDIR` 設為此目錄，讓寫入暫存檔案的工具無需額外設定即可運作。

非沙箱命令在您的 shell 設定了 `$TMPDIR` 時會繼承該值，因此在檔案系統隔離開啟期間，沙箱化與非沙箱命令會將 `$TMPDIR` 解析為不同的目錄。如果您的 shell 未設定 `$TMPDIR` 或其值為空，引用 `$TMPDIR` 的非沙箱命令會收到您的 [`CLAUDE_CODE_TMPDIR`](https://code.claude.com/docs/zh-TW/env-vars) 覆寫值；若您尚未設定覆寫值或覆寫值是過長的路徑，則會收到作業系統的暫存目錄，因此該變數不會展開為空字串。若要在兩者之間傳遞暫存檔案，請改為將其寫入工作目錄下。

## 設定沙箱機制

透過 `settings.json` 檔案自訂沙箱行為。完整的設定參考請參閱[設定](https://code.claude.com/docs/zh-TW/settings-reference.md#sandbox-settings)。

預設情況下，沙箱化的命令可以寫入目前的工作目錄、每位使用者專屬的暫存目錄，以及任何透過 `--add-dir`、`/add-dir` 或 `permissions.additionalDirectories` [新增的目錄](https://code.claude.com/docs/zh-TW/permissions.md#additional-directories-grant-file-access-not-configuration)。如果 `kubectl`、`terraform` 或 `npm` 等子程序命令需要寫入這些目錄以外的位置，請使用 `sandbox.filesystem.allowWrite` 授予特定路徑的存取權：

```json theme={null}
{
  "sandbox": {
    "enabled": true,
    "filesystem": {
      "allowWrite": ["~/.kube", "/tmp/build"]
    }
  }
}
```

這些路徑在作業系統層級強制執行，因此所有在沙箱內執行的命令（包括其子程序）都會遵守這些路徑。當某個工具需要特定位置的寫入權限時，建議採用此方法，而不是使用 `excludedCommands` 將該工具完全排除在沙箱之外。

當您在多個[設定範圍](https://code.claude.com/docs/zh-TW/settings.md#settings-precedence)中定義相同的檔案系統陣列時，Claude Code 會將它們合併，結合每個範圍中的路徑，而不是以某個範圍的陣列取代另一個範圍的陣列。當[防止開發人員擴大政策](#keep-developers-from-widening-the-policy)中所述的鎖定涵蓋某個項目時，Claude Code 會將該項目排除在合併之外。

如果您在 CLI 上使用 [`--setting-sources`](https://code.claude.com/docs/zh-TW/cli-reference) 或在 Agent SDK 中使用 [`settingSources`](https://code.claude.com/docs/zh-TW/agent-sdk/claude-code-features#control-filesystem-settings-with-settingsources) 排除某個來源，Claude Code 在建置沙箱設定時會忽略該來源的 `sandbox.filesystem` 項目、其 `Edit` 權限規則，以及其 `Read` 拒絕規則。需要 Claude Code v2.1.246 或更新版本。

當您在工作階段期間編輯這些檔案系統清單時，Claude Code 會[將變更套用至執行中的工作階段](https://code.claude.com/docs/zh-TW/settings.md#when-edits-take-effect)，因此下一個沙箱化命令會在新路徑下執行。

沙箱檔案系統路徑使用標準慣例：`/tmp/build` 是絕對路徑，`~/.kube` 則相對於您的家目錄。這與 [Read 和 Edit 權限規則](https://code.claude.com/docs/zh-TW/permissions.md#read-and-edit)不同，後者使用 `//path` 表示絕對路徑，使用 `/path` 表示相對於專案的路徑。關於相對路徑、結尾斜線和萬用字元，請參閱[沙箱路徑前綴](https://code.claude.com/docs/zh-TW/settings-reference.md#sandbox-path-prefixes)。

您也可以使用 `sandbox.filesystem.denyWrite` 和 `sandbox.filesystem.denyRead` 拒絕寫入或讀取存取，並使用 `sandbox.filesystem.allowRead` 在被拒絕的區域內重新允許特定路徑。當讀取規則重疊時，套用路徑較窄的規則：

| 範例規則 | 結果 |
| :- | :- |
| `"denyRead": ["~/"]` 搭配 `"allowRead": ["~/projects"]` | `~/projects` 可讀取，家目錄的其餘部分仍被封鎖。較窄的允許規則會重新開放被拒絕區域中的該部分 |
| `"allowRead": ["~/"]` 搭配 `"denyRead": ["~/.env"]` | `~/.env` 仍被封鎖，家目錄的其餘部分可讀取。拒絕規則在較寬的允許規則內仍然有效，因此廣泛的允許規則無法在不知不覺中重新暴露機密 |
| `"allowRead": ["~/"]` 搭配 `"denyRead": ["~/**/.env"]` | 家目錄下的每個 `.env` 都仍被封鎖，其餘部分可讀取。[萬用字元拒絕規則](https://code.claude.com/docs/zh-TW/settings-reference.md#sandbox-path-prefixes)在較寬的允許規則內同樣有效，與精確路徑相同 |

以下範例封鎖從整個家目錄讀取，同時仍允許從目前專案讀取。請將其放在專案的 `.claude/settings.json` 中，因為只有當設定位於專案設定中時，相對路徑 `.` 才會解析為專案根目錄：

```json theme={null}
{
  "sandbox": {
    "enabled": true,
    "filesystem": {
      "denyRead": ["~/"],
      "allowRead": ["."]
    }
  }
}
```

如果您將相同的設定放在 `~/.claude/settings.json` 中，`.` 會改為解析為 `~/.claude`，而專案檔案將仍被 `denyRead` 規則封鎖。

若要拒絕沙箱化命令讀取家目錄和掛載的磁碟區，同時保持工作目錄可讀取，請設定 [`permissions.blockReadsOutsideWorkingDirectories`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-blockreadsoutsideworkingdirectories)，而不是撰寫路徑規則。

### 使用 `excludedCommands` 在沙箱外執行命令

在 [`sandbox.excludedCommands`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-excludedcommands) 中列出命令模式，即可在沙箱外執行相符的命令，這表示沒有檔案系統限制，也沒有網路代理伺服器。請將其用於無法在沙箱內運作、且您信任其擁有您完整存取權的工具。若某個工具只需要多一個目錄或多一個主機，或許可以使用 `allowWrite` 或 `allowedDomains` 運作，這兩者會讓命令保持在沙箱中。

此範例將 `docker compose` 命令移出沙箱。將其儲存在 `~/.claude/settings.json` 中即可套用至您的所有專案：

```json theme={null}
{
  "sandbox": {
    "enabled": true,
    "excludedCommands": ["docker compose *"]
  }
}
```

Claude Code 會將您的項目與每個 Bash 和 Monitor 呼叫進行比對。一個呼叫是 Claude 傳送的完整命令列，其中可以串接多個命令。以下規則決定呼叫是否離開沙箱：

* **以 ` *` 結束模式**：項目使用與 `Bash(...)` [權限規則](https://code.claude.com/docs/zh-TW/permissions.md#permission-rule-syntax)相同的語法，其中不含萬用字元的模式為精確比對。`docker` 只比對不帶引數的 `docker`。`docker *` 比對帶或不帶引數的 `docker`
* **呼叫中的每個命令都必須相符**：`npm ci && docker compose build` 會保持在沙箱中，除非另有項目涵蓋 `npm ci`
* **Claude Code 比對的是呼叫的文字**：在內部呼叫 `docker` 的指令碼或 `make` 目標不會相符，`/usr/local/bin/docker` 也不會相符
* **某些呼叫會保持在沙箱中**：重新導向至檔案、`cd`，或如 `$(...)` 的命令替換，會讓整個呼叫保持在沙箱中。[參考項目](https://code.claude.com/docs/zh-TW/settings-reference.md#sandbox-excludedcommands)列出了更多會保持在沙箱中的呼叫
* **`git clone` 需要使用相對路徑**：您的項目不涵蓋指定絕對路徑、以 `~` 開頭的路徑，或含有 `..` 區段之路徑的 clone。如果 clone 可以放在您的工作目錄內，請要求 Claude 使用不含 `..` 區段的相對路徑，例如 `vendor/lib`
* **項目的儲存位置可能有影響**：當沙箱為[管理員要求](#repository-settings-under-an-admin-required-sandbox)時，Claude Code 會忽略 `.claude/settings.json` 和 `.claude/settings.local.json` 中的項目

被排除的命令會經過一般的權限流程：

* [唯讀命令](https://code.claude.com/docs/zh-TW/permissions.md#read-only-commands)以及您的允許規則涵蓋的命令會在不顯示提示的情況下執行
* 在自動模式中，分類器會審查其他被排除的命令
* 在 `bypassPermissions` 模式中，被排除的命令會在不顯示提示的情況下執行，除非有 ask 規則與之相符

若要確認項目是否相符，請切換至 Manual 模式，並要求 Claude 執行會變更內容的相符命令，例如 `docker compose up -d`。權限提示的標題為「Bash command (unsandboxed)」。

> [!WARNING]
>
> 被排除的命令會以您的完整存取權執行。像 `docker *` 這樣廣泛的項目涵蓋了該工具能做的一切。如果您撰寫的模式涵蓋了直譯器、工作目錄內的指令碼，或作用於該目錄中檔案的工具（就像 `docker compose` 作用於其 compose 檔案一樣），Claude 就可以寫入該檔案，然後在沙箱外執行它。較窄的模式會讓 Claude 能在沙箱外執行的內容更少。

### 停用檔案系統隔離

將 `sandbox.filesystem.disabled` 設為 `true`，即可略過檔案系統隔離，同時保留網路隔離。以下範例關閉檔案系統隔離，同時保留網路網域的允許清單：

```json theme={null}
{
  "sandbox": {
    "enabled": true,
    "filesystem": {
      "disabled": true
    },
    "network": {
      "allowedDomains": ["github.com", "*.npmjs.org"]
    }
  }
}
```

沙箱有兩個獨立的層：[檔案系統隔離](#filesystem-isolation)控制沙箱化命令可以讀取和寫入哪些路徑，[網路隔離](#network-isolation)控制它們可以連線到哪些網域。關閉檔案系統層後，沙箱化命令會取得對主機檔案系統不受限制的讀取和寫入存取權，而其網路輸出流量仍限制在您允許的網域內。當您使用沙箱是為了控制命令連線至何處，而非它們寫入什麼內容時，請關閉此層。

`sandbox.filesystem.disabled` 預設為 `false`。

> [!WARNING]
>
> 在關閉檔案系統隔離且命令自動允許的情況下，沙箱化命令可以寫入之後的命令會執行或讀取的檔案，例如 shell 啟動檔案、`$PATH` 上的可執行檔或 `~/.claude/settings.json`，並利用它們在下次執行時擴大自身的存取權。請僅針對您信任不會自行提升存取權的工作負載，將 `filesystem.disabled` 設為 `true`。使用 [`allowManagedDomainsOnly`](#keep-developers-from-widening-the-policy) 鎖定網路網域可降低風險，但無法消除風險，因為該鎖定僅適用於在沙箱內執行的命令。

#### 哪些設定可以停用它

由於關閉檔案系統隔離會擴大沙箱化命令能做的事，Claude Code 僅接受來自以下設定來源的 `filesystem.disabled`：

* 使用者設定、受管設定和 `--settings` CLI 旗標可以設定它。`.claude/settings.json` 和 `.claude/settings.local.json` 中的專案設定則不行，因此簽出的專案無法關閉檔案系統隔離。
* 當受管設定有設定任何 `sandbox.filesystem`，或列出任何 `"mode": "deny"` 的 `sandbox.credentials.files` 項目時，只有受管設定可以設定此鍵。這可防止開發人員在此類部署中關閉檔案系統隔離；若要為所有人關閉檔案系統隔離，請在受管設定中設定 `"disabled": true`。
* 當設定了 [`CLAUDE_CODE_SUBPROCESS_ENV_SCRUB`](https://code.claude.com/docs/zh-TW/env-vars) 時，Claude Code 會忽略來自所有來源（包括受管設定）的 `filesystem.disabled`，並保持檔案系統隔離開啟。

[有效的](https://code.claude.com/docs/zh-TW/settings-reference.md#invalid-credential-entries-in-managed-settings) `mask` 項目不會鎖定此鍵，即使 Claude Code 在啟動時對其[退回 `deny`](#mask-credential-files) 也是如此。請將無法遮罩的路徑（例如憑證目錄）在受管設定中列為明確的 `deny` 項目，這樣會鎖定此鍵。

#### 關閉檔案系統隔離時的變化

設定 `filesystem.disabled` 會解除檔案系統層本身強制執行的保護。其他層強制執行的保護則持續適用：

| 保護 | 關閉檔案系統隔離時 |
| - | - |
| `filesystem.denyRead` 和 [`credentials.files`](#protect-credentials) `deny` 讀取封鎖 | 不強制執行。兩者皆由檔案系統層套用 |
| `credentials.envVars` `deny` 和 `mask` 項目 | 強制執行。環境變數清除獨立於檔案系統層 |
| 以遮罩方式套用的 [`credentials.files` `mask` 項目](#mask-credential-files) | 強制執行：遮罩獨立於檔案系統層。[退回 `deny`](#mask-credential-files) 的項目則不強制執行，與任何 `deny` 項目相同 |

另有兩項變化：

* 沙箱化命令會繼承您 shell 的 `$TMPDIR`，而非每位使用者專屬的暫存目錄，因為每個暫存目錄都可寫入，Claude Code 不再將命令重新導向至每位使用者專屬的暫存目錄。

  在 Linux 上，此變數在父 shell 中通常未設定。Bash 工具指引會告知 Claude 使用 `mktemp -d` 建立暫用目錄，而不是依賴 `$TMPDIR`。
* [`autoAllowBashIfSandboxed`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-autoallowbashifsandboxed) 仍預設為 `true`，因此沙箱化命令會持續在不顯示提示的情況下執行。將其設為 `false` 即可針對沙箱化命令顯示提示。

### 保護憑證

`sandbox.credentials` 設定宣告要保護、使其不受沙箱化命令存取的憑證檔案和環境變數。每個項目指定一個檔案路徑或環境變數，以及一個 `mode`。專用的 `credentials` 區塊讓憑證規則集中在一起，並與一般檔案系統規則分開。

對於 `"mode": "deny"` 的項目，檔案路徑在沙箱內會被拒絕讀取，這與 `filesystem.denyRead` 套用的限制相同；環境變數則會在每個沙箱化命令執行前取消設定。檔案保護屬於檔案系統層，因此如果您[停用檔案系統隔離](#disable-filesystem-isolation)，檔案保護便不適用；環境變數保護則仍然適用。

以下範例封鎖讀取 AWS 憑證檔案和 SSH 目錄，並從沙箱化命令的環境中移除 `GITHUB_TOKEN` 和 `NPM_TOKEN`：

```json theme={null}
{
  "sandbox": {
    "enabled": true,
    "credentials": {
      "files": [
        { "path": "~/.aws/credentials", "mode": "deny" },
        { "path": "~/.ssh", "mode": "deny" }
      ],
      "envVars": [
        { "name": "GITHUB_TOKEN", "mode": "deny" },
        { "name": "NPM_TOKEN", "mode": "deny" }
      ]
    }
  }
}
```

環境變數項目和檔案項目也接受 `"mode": "mask"`，詳見[遮罩憑證](#mask-credentials)。

檔案路徑遵循與 `sandbox.filesystem.*` 設定相同的[前綴規則](https://code.claude.com/docs/zh-TW/settings-reference.md#sandbox-path-prefixes)。

Claude Code 會合併工作階段載入的每個[設定範圍](https://code.claude.com/docs/zh-TW/settings.md#settings-precedence)中的 `deny` 項目。`deny` 項目只會縮小存取範圍，因此任何範圍都可以新增，但沒有任何範圍可以移除其他範圍新增的項目。

當您[排除某個設定來源](#configure-sandboxing)時：

* **專案或本機設定**：Claude Code 不會套用其任何 `credentials` 項目。需要 Claude Code v2.1.246 或更新版本。
* **使用者設定**：Claude Code 仍會套用 `~/.claude/settings.json` 中的 `deny` 項目，並將其[檔案 `mask` 項目](#mask-credential-files)保留為限制，但這些項目不再授權代理伺服器替換真實值；同時會捨棄其[環境變數 `mask` 項目](#mask-environment-variables)。

沒有內建的憑證拒絕清單，因此只有您列出的檔案和變數會受到限制。

`sandbox.credentials` 僅影響沙箱化的 Bash 命令。若要無論是否使用沙箱都從所有子程序中移除憑證，請設定 [`CLAUDE_CODE_SUBPROCESS_ENV_SCRUB`](https://code.claude.com/docs/zh-TW/env-vars)。

### 遮罩憑證

當您遮罩憑證時，Claude Code 會向沙箱化命令顯示一個每個工作階段專屬的預留位置，稱為哨兵值，而[沙箱代理伺服器](#network-isolation)會在傳送至您允許之主機的外送請求中換入真實值。[保護憑證](#protect-credentials)中的 `deny` 項目則會改為封鎖憑證。對於 macOS 上的檔案，Claude Code 會[改為封鎖該檔案](#mask-credential-files)，而非加以遮罩。[`sandbox.credentials`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-credentials) 參考列出了每個欄位。

遮罩需要以下條件：

* **TLS 終止**：代理伺服器會在請求內容中替換真實值，因此必須能看到請求內容。請設定 [`network.tlsTerminate`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-network-tlsterminate)，讓代理伺服器自行終止 TLS。若未設定，遮罩會失敗但不會洩漏任何內容：命令仍只看到哨兵值，但哨兵值會原封不動地送達伺服器，導致身分驗證失敗。若要檢查此設定錯誤，請在終端機中執行 `claude doctor`，並查看是否出現 `TLS termination is unavailable` 警告。
* **允許的目的地**：每個 `mask` 項目可以列出 `injectHosts`，即允許真實值送達的主機。代理伺服器只會在[網域允許清單](#network-isolation)允許的連線上注入，因此每個 `injectHosts` 主機也必須能透過 `network.allowedDomains` 連線到。對於沒有 `injectHosts` 的 `mask` 項目，代理伺服器會在傳送至 `network.allowedDomains` 中每個主機的請求中替換真實值。
* **受信任的設定範圍**：遮罩會授權代理伺服器將您的真實憑證傳送至某處，因此 Claude Code 只接受來自使用者設定、受管設定和 `--settings` 旗標的 `mask` 項目、`network.tlsTerminate`、[`credentials.allowPlaintextInject`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-credentials-allowplaintextinject)、`awsPairs` 和 `sigv4`。它會忽略儲存庫的 `.claude/settings.json` 或 `.claude/settings.local.json` 中的這些設定。當您的管理員透過伺服器管理的設定提供 `mask` 項目、`network.tlsTerminate` 或 `credentials.allowPlaintextInject` 時，這些會被視為[需要核准的設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md#security-approval-dialogs)。

#### 遮罩環境變數

若要遮罩環境變數，請在其 `credentials.envVars` 項目上設定 `"mode": "mask"`。命令及其記錄的任何日誌永遠不會持有真實憑證，但其請求仍能通過身分驗證。當同一個變數在任何範圍中以 `deny` 列出時，`deny` 優先。

以下範例遮罩兩個 token。`GH_TOKEN` 只會在傳送至 `api.github.com` 的請求中替換，而 `NPM_TOKEN` 沒有 `injectHosts`，因此會在傳送至 `network.allowedDomains` 中每個主機的請求中替換：

```json theme={null}
{
  "sandbox": {
    "enabled": true,
    "network": {
      "tlsTerminate": {},
      "allowedDomains": ["*.github.com", "registry.npmjs.org"]
    },
    "credentials": {
      "envVars": [
        { "name": "GH_TOKEN", "mode": "mask", "injectHosts": ["api.github.com"] },
        { "name": "NPM_TOKEN", "mode": "mask" }
      ]
    }
  }
}
```

遮罩預設會取代整個值。對於具有結構的值，例如 `DATABASE_URL` 連線字串或 JWT，請使用 [`extract`、`decode`、`maskClaims` 和 `onExtractNoMatch` 欄位](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-credentials-envvars)，讓剖析該值的工具持續運作。

對於 IPv6 目的地，請在兩個清單中以不同方式書寫位址：

* **`network.allowedDomains`**：方括號形式，例如 `"[::1]"`
* **`injectHosts`**：標準壓縮形式的純位址，例如 `"::1"`

代理伺服器會將每個 `injectHosts` 項目與連線的純目的地位址進行比對，並忽略連接埠，因此帶方括號、帶區域 ID 或以不同方式壓縮的寫法永遠不會相符。`claude doctor` 會以警告 `Sandbox credential injectHosts entries can never match their destination` 標示永遠無法相符的項目。此檢查需要 Claude Code v2.1.229 或更新版本。

#### 重新簽署 AWS 請求

AWS 請求帶有針對請求內容的 SigV4 簽章，因此請同時遮罩 `AWS_ACCESS_KEY_ID` 和 `AWS_SECRET_ACCESS_KEY`。代理伺服器會透過存取金鑰的[哨兵值](#mask-credentials)偵測 SigV4 請求，並以真實值重新簽署請求，此功能需要 Claude Code v2.1.221 或更新版本。如果您只遮罩密鑰，請求會以代理伺服器無法偵測的預留位置簽署，因此會在 AWS 端失敗。

當您遮罩慣用的 `AWS_ACCESS_KEY_ID`、`AWS_SECRET_ACCESS_KEY` 和 `AWS_SESSION_TOKEN` 變數的完整值時，Claude Code 會自動將它們連結為單一憑證。如果您的 AWS 憑證存放在其他名稱的變數中，請使用 [`credentials.awsPairs`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-credentials-awspairs) 將它們分組，此功能需要 Claude Code v2.1.224 或更新版本。

串流上傳、預先簽署的 URL 和 SigV4A 請求帶有代理伺服器無法重新計算的簽章。當此類請求以已遮罩配對的預留位置簽署時，代理伺服器會讓它失敗，而不是轉送損壞的簽章。以未遮罩憑證簽署的請求不受影響。使用 [`credentials.sigv4`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-credentials-sigv4)（需要 Claude Code v2.1.224 或更新版本）可改為轉送這些請求形式之一。AWS 仍會拒絕該請求，因此呼叫的工具會收到 AWS 本身的拒絕回應，而非代理伺服器錯誤。

#### 遮罩憑證檔案

若要遮罩憑證檔案，請在其 `credentials.files` 項目上設定 `"mode": "mask"`。遮罩檔案需要 Claude Code v2.1.221 或更新版本。沙箱化命令看到的內容取決於平台：

* **Linux 和 WSL2**：沙箱化命令讀取的是檔案的[哨兵值](#mask-credentials)副本，而代理伺服器會在外送請求中替換真實值。
* **macOS**：沙箱化命令完全無法讀取該檔案。Claude Code 不會建置哨兵副本，因此使用該檔案進行身分驗證的工具無法在沙箱內運作，效果與 `deny` 相同。即使您[停用檔案系統隔離](#disable-filesystem-isolation)，讀取封鎖仍然有效。

以下範例遮罩存放在 `~/.config/gh/hosts.yml` 中的 GitHub token。`extract` 模式會標示檔案的哪個部分是密鑰，因此在 Linux 和 WSL2 上，`gh` 仍能剖析其設定的其餘部分：

```json theme={null}
{
  "sandbox": {
    "enabled": true,
    "network": {
      "tlsTerminate": {},
      "allowedDomains": ["*.github.com"]
    },
    "credentials": {
      "files": [
        {
          "path": "~/.config/gh/hosts.yml",
          "mode": "mask",
          "extract": "oauth_token:\\s*(\\S+)",
          "injectHosts": ["api.github.com"]
        }
      ]
    }
  }
}
```

若要確認遮罩已生效，請要求 Claude 在沙箱化命令中執行 `cat ~/.config/gh/hosts.yml`。在 Linux 和 WSL2 上，輸出會顯示哨兵值來取代 token；在 macOS 上，讀取則會失敗。

若未使用 `extract` 或 `decode`，Claude Code 會以單一哨兵值取代整個檔案，這適用於只存放單一純密鑰的檔案。請使用 [`extract`、`decode`、`maskClaims`、`onExtractNoMatch` 和 `maskDuplicates` 欄位](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-credentials-files)來控制部分遮罩，以及模式未相符任何內容時的行為。

> [!WARNING]
>
> 當比對找不到任何可遮罩的內容時，預設的 `onExtractNoMatch` 值 `warn` 會略過該項目，因此沙箱化命令可以讀取未遮罩的真實檔案。在 macOS 上，只要檔案系統隔離開啟，Claude Code 就會在模式執行前將 `mask` 項目以 `deny` 套用，因此無相符結果只有在[檔案系統隔離關閉](#disable-filesystem-isolation)時才會在 macOS 上生效。預設值適用於可能合理不存在的憑證。如果密鑰可能存在但模式可能遺漏它，請使用 [`deny`](https://code.claude.com/docs/zh-TW/settings-reference#mask-fields-for-files)。

`mask` 適用於單一檔案，因此請個別列出每個憑證檔案。對於無法安全遮罩的 `mask` 項目，Claude Code 會退回 `deny`：目錄路徑、glob 模式、大於 8 MiB 的檔案，或非 UTF-8 文字的檔案。

## 沙箱機制的運作方式

### 檔案系統隔離

沙箱化的 Bash 工具會將檔案系統存取限制在特定目錄：

* **預設寫入行為**：對目前工作目錄及其子目錄、以 `--add-dir`、`/add-dir` 或 [`permissions.additionalDirectories`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-additionaldirectories) 新增的任何目錄，以及 `$TMPDIR` 所指向的每位使用者暫存目錄，具有讀取和寫入權限
* **預設讀取行為**：對整台電腦具有讀取權限，但某些被拒絕的目錄除外。此預設仍允許讀取憑證檔案，因此請[保護憑證](#protect-credentials)，避免命令讀取您不希望其讀取的憑證。
* **讀取封鎖**：開啟 [`permissions.blockReadsOutsideWorkingDirectories`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-blockreadsoutsideworkingdirectories) 後，沙箱化命令也會失去對您的家目錄及其他存放使用者檔案之目錄的讀取權限，但[封鎖下的沙箱化命令](https://code.claude.com/docs/zh-TW/settings-reference.md#sandboxed-commands-under-the-block)所列出的路徑除外。該章節也說明了這部分封鎖何時不適用。
* **Git worktree**：當工作目錄是[連結的 git worktree](https://code.claude.com/docs/zh-TW/worktrees.md) 時，沙箱也允許寫入主儲存庫共用的 `.git` 目錄，讓 `git commit` 等命令可以更新 refs 和 index。對該目錄內 `hooks/` 和 `config` 的寫入仍會被拒絕。

若要完全略過檔案系統隔離，同時保留網路隔離，請設定 [`sandbox.filesystem.disabled`](#disable-filesystem-isolation)。

### 受保護的路徑

在沙箱化命令可以寫入的目錄中，沙箱仍會拒絕寫入 Claude Code 載入設定和程式碼的檔案。能夠編輯這些檔案的命令可能會自行授予權限，或新增由 Claude Code 在沙箱外執行的 hook 或 MCP 伺服器。權限系統有其自己的[受保護路徑](https://code.claude.com/docs/zh-TW/permission-modes.md#protected-paths)，用來控制 Claude Code 在工具執行前核准的內容；沙箱的清單則適用於已在執行中的命令。它涵蓋四組路徑：

* **在您的工作目錄及其上層目錄中**：`.claude` 設定檔、`.claude/skills`、`.claude/agents`、`.claude/commands` 和 `.claude/hooks` 目錄、`.mcp.json`，以及 Claude Code 自行執行的檔案，例如 `.claude/workflows` 和 `.claude/scheduled_tasks.json`
* **僅在您的工作目錄中**：shell 啟動檔案，例如 `.bashrc` 和 `.zshrc`、`.gitconfig`、`.vscode` 和 `.idea` 目錄，以及 `.git` 內的 `hooks` 和 `config`
* **會將您的工作目錄變成 bare git 儲存庫的檔案**：頂層的 `HEAD`、`objects` 和 `refs`，以及當旁邊有 `HEAD` 檔案或符號連結時，該處既有的 `config` 和 `hooks` 項目。名為 `config` 的檔案即使沒有 `HEAD` 也會被拒絕。[之後才出現的 `HEAD`、`objects` 或 `refs` 可能會被刪除](#when-the-sandbox-deletes-head-objects-or-refs)。在 Linux 和 WSL2 上，沙箱化命令可以在原本不存在這類項目的位置建立一個。
* **在 `~/.claude` 或 `CLAUDE_CONFIG_DIR` 所指向的目錄中**：其大部分內容，加上 `~/.claude.json` 和 `.credentials.json` 憑證儲存區

如果在工作階段期間，受保護設定檔的路徑上出現符號連結，沙箱也會從下一個命令開始，拒絕寫入該符號連結所指向的檔案。

如果您新增涵蓋其中某個路徑的 `allowWrite` 項目或 `Edit` 允許規則，保護仍然適用。若要關閉保護，請設定 [`filesystem.disabled`](#disable-filesystem-isolation)，這也會關閉其餘的檔案系統隔離。

> [!WARNING]
>
> 如果您在 Linux 或 WSL2 上將 [`allowNestedUserNamespaces`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-allownestedusernamespaces) 設為 `true`，請勿依賴受保護的路徑：來自沙箱化命令的程式碼最終可能會在沙箱外執行。

若要查看這些路徑在您電腦上解析後的大部分結果，請執行 `/sandbox` 並開啟 **Config** 分頁，其中會將它們列在 **Denied within allowed** 下，並與您自己的 `denyWrite` 項目混在一起。

如果 `git merge` 或 `git checkout` 在其中某個路徑上因 `unable to unlink old` 而失敗，請參閱[git 命令因 `unable to unlink old` 而失敗](#a-git-command-fails-with-unable-to-unlink-old)。

#### 沙箱何時會刪除 `HEAD`、`objects` 或 `refs`

沙箱化命令結束後，您工作目錄中較新的頂層 `HEAD`、`objects` 或 `refs` 項目會被刪除，除非它是含有內容的資料夾。「較新」是指沙箱上次建構其設定時該項目並不存在：也就是在工作階段開始時，或在 [`/cd`](https://code.claude.com/docs/zh-TW/commands) 等變更之後。

如果沙箱上次建構其設定時已有 `HEAD` 檔案或符號連結存在，含有內容的較新 `objects` 或 `refs` 資料夾也會連同其內容一起被刪除。若要保留資料夾，請參閱[命令執行後名為 `objects` 或 `refs` 的資料夾消失](#a-folder-named-objects-or-refs-disappears-after-a-command)。

#### 經過符號連結的被拒絕路徑

在 macOS 上，當被拒絕的路徑經過符號連結時（例如 `~/.claude` 是連結到 dotfiles 儲存庫的符號連結），沙箱也會拒絕該路徑的實際位置。這涵蓋沙箱本身的拒絕項目，以及您以字面形式寫下的 `denyWrite` 和 `denyRead` 項目。

包含 `*`、`?` 或 `[` 的 `denyWrite` 項目，當這些字元中第一個出現者之前的某個資料夾是符號連結時，也同樣涵蓋在內。例如，`~/.claude/*.json` 也會在 `~/.claude` 的實際位置下被拒絕。

### 網路隔離

沙箱化命令沒有直接連到網路的路徑：

* **Linux 和 WSL2**：命令會在一個與您的網路沒有連線的獨立網路命名空間中執行
* **macOS**：Seatbelt 沙箱框架預設會封鎖除了連到沙箱代理伺服器以外的連線

Claude Code 會在您的電腦上、沙箱之外執行沙箱代理伺服器，並透過 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY` 及相關環境變數將命令導向它。代理伺服器會根據您允許和拒絕的網域檢查每個連線的主機名稱。

工具可以連到哪裡，取決於它是否使用代理伺服器：

* **會讀取代理伺服器變數的工具**：`curl`、`npm`、透過 HTTPS 的 `git` 及類似工具，在其主機被允許後即可連線。沒有指定連接埠的 `allowedDomains` 項目會允許該主機上的所有連接埠
* **會忽略代理伺服器變數的工具**：純 `ssh`、大多數資料庫驅動程式及類似工具無法連線，即使是連到被允許的主機也一樣。請參閱[資料庫用戶端或其他非 HTTP 工具無法連到被允許的主機](#a-database-client-or-other-non-http-tool-fails-to-reach-an-allowed-host)
* **任何非 TCP 的流量**：UDP、透過 QUIC 的 HTTP/3，以及 `ping` 等 ICMP 工具都無法離開沙箱

下列設定和行為控制代理伺服器允許哪些主機：

* **網域限制**：您允許的網域一開始是空的。[您允許網域以外的主機](#hosts-outside-your-allowed-domains)說明了命令第一次需要新網域時會發生什麼事。
* **核准選擇**：如果您在出現提示時選擇 Yes，Claude Code 會在目前工作階段的剩餘時間內允許該主機。如果您選擇「Yes, and don't ask again」，Claude Code 會將 `WebFetch(domain:...)` 允許規則儲存到您的[本機設定](https://code.claude.com/docs/zh-TW/permissions.md#permission-system)，讓該主機在未來的工作階段中仍被允許。當沙箱為[管理員強制](#repository-settings-under-an-admin-required-sandbox)時，Claude Code 會將規則儲存到您的使用者設定，並套用於每個專案。
* **預先允許的網域**：使用 [`allowedDomains`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-network-alloweddomains) 預先允許網域，即可完全避免提示。Claude Code 也會預先允許來自 `WebFetch(domain:...)` 允許規則的網域，如[權限規則](#permission-rules)所述。
* **嚴格允許清單**：如果您在使用者設定、受管設定或 CLI `--settings` 設定中將 [`strictAllowlist`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-network-strictallowlist) 設為 `true`，Claude Code 會拒絕沙箱化命令存取允許清單以外的任何主機，而不是顯示提示。允許清單為 `allowedDomains` 加上來自 `WebFetch(domain:...)` 允許規則的網域；若設定了 `allowManagedDomainsOnly`，則僅為受管設定中的項目。[不需管理員強制沙箱即可套用的鎖定](#locks-that-apply-without-an-admin-required-sandbox)說明了儲存庫的項目。Claude Code 僅對沙箱化命令強制執行此設定；`WebFetch` 等程序內工具仍遵循其[權限規則](#permission-rules)。在儲存庫的 `.claude/settings.json` 或 `.claude/settings.local.json` 中設定此項目沒有作用。需要 Claude Code v2.1.219 或更新版本。
* **受管鎖定**：如果在受管設定中設定了 [`allowManagedDomainsOnly`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-network-allowmanageddomainsonly)，未被允許的網域會自動被封鎖，而不是顯示提示，且僅會採用受管設定中的 `allowedDomains` 和 `WebFetch(domain:...)` 允許規則。
* **企業代理伺服器**：當您的網路要求對外流量必須經過企業代理伺服器時，請依照[代理伺服器設定](https://code.claude.com/docs/zh-TW/network-config.md#proxy-configuration)的說明設定 `HTTPS_PROXY`、`HTTP_PROXY` 和 `NO_PROXY`，設定位置可以是您設定中的 `env` 區塊（讓[背景 agent](https://code.claude.com/docs/zh-TW/network-config.md#set-network-variables-in-settings-not-the-shell) 也能取得），或是您啟動 Claude Code 的環境。Claude Code 會強制執行網域允許清單，然後將被允許的連線透過該上游代理伺服器建立通道。`http://` 和 `https://` 代理伺服器 URL 皆可使用，如有需要，可在 URL 中加入基本身分驗證。

在 `WebFetch(domain:...)` 規則中，沙箱支援兩種萬用字元形式：開頭的 `*.`（例如 `*.example.com`）以及單獨的 `*`。單獨的 `*` 形式需要 Claude Code v2.1.186 或更新版本。位於其他位置的萬用字元（例如 `WebFetch(domain:example.*)`）仍會比對擷取請求，但對沙箱化命令沒有作用。

> [!NOTE]
>
> 內建代理伺服器會根據所請求的主機名稱強制執行允許清單，且預設不會終止或檢查 TLS 流量。實驗性的 [`network.tlsTerminate`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-network-tlsterminate) 設定會讓內建代理伺服器自行終止 TLS，這是 [`mask` 憑證項目](#mask-credentials)所必需的。關於預設行為的影響，請參閱[安全性限制](#security-limitations)；如果您的威脅模型需要 TLS 檢查，請參閱[自訂代理伺服器設定](#custom-proxy-configuration)。

#### 您允許網域以外的主機

當沙箱化命令連線到不在您允許網域中的主機時，命令會留在沙箱中並等待決定。在互動式終端機工作階段中，決定取決於您的權限模式：

| 權限模式 | 連線會如何處理 |
| :- | :- |
| `bypassPermissions` 模式，以及[可使用略過權限](https://code.claude.com/docs/zh-TW/permission-modes.md#skip-all-checks-with-bypasspermissions-mode)時的 plan mode | 不經提示即允許 |
| 手動模式、`acceptEdits` 模式，以及其他情況下的 plan mode | 您會收到提示 |
| 自動模式 | 除非命令[列出了該主機](#per-command-allowed-domains-in-auto-mode)且分類器核准了該清單，否則拒絕 |
| `dontAsk` 模式 | 拒絕 |

開啟 [`strictAllowlist`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-network-strictallowlist) 或 [`allowManagedDomainsOnly`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-network-allowmanageddomainsonly) 時，內建沙箱代理伺服器在每種權限模式下都會拒絕該連線。在 `bypassPermissions` 模式中，除非開啟了其中之一，否則您允許網域以外的主機都會被允許。[非沙箱重試的逃生口](#the-unsandboxed-retry-escape-hatch)說明了命令在該模式下何時可以離開沙箱。連到 [`deniedDomains`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-network-denieddomains) 中主機的連線，在每種權限模式下也都會被拒絕。

#### 解析為本機位址的主機名稱

主機名稱通過允許清單後，沙箱代理伺服器會解析它，並在該名稱僅解析為本機位址時拒絕連線。本機位址包括 `127.0.0.1` 等迴路位址、`169.254.169.254` 雲端中繼資料端點等鏈路本機位址，以及指派給您自己電腦的位址。名稱 `localhost` 和 `*.localhost` 可以解析為迴路位址。

被允許的內部網路主機名稱若解析為 `10.0.0.0/8` 等私有範圍，則可以連線。若要讓某個名稱解析為會被拒絕的位址，請將該 IP 位址加入 `allowedDomains`，例如 `"127.0.0.1:8080"`。

此檢查適用於主機名稱。連到 IP 位址的連線由您允許的網域和權限模式決定。對於透過上游企業代理伺服器送出的連線，代理伺服器也會略過此檢查，因為由該代理伺服器解析名稱。

#### 自動模式中的每個命令允許網域

在開啟沙箱機制的[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)中，Claude 會在命令本身上指名該命令所需的主機，而不是為每個連線觸發網路核准。每個在沙箱中執行的 Bash、PowerShell 或 [Monitor](https://code.claude.com/docs/zh-TW/tools-reference.md#monitor-tool) 命令，都可以攜帶一份超出沙箱允許清單的主機清單：例如 `registry.npmjs.org` 這樣的網域、`*.pythonhosted.org` 這樣的萬用字元，或 IP 位址，每一項都可以選擇性加上 `:port`。分類器會將這些主機與命令一起審查。需要 Claude Code v2.1.271 或更新版本。

獲得核准的清單只會在該單一命令執行期間為其開放這些主機。不會將任何內容加入您工作階段的允許主機或您的設定；下一個命令會指名它自己的主機。

攜帶主機的命令會交由分類器處理，而不是由權限規則或沙箱的[自動允許模式](#sandbox-modes)核准。如果 [ask 規則](https://code.claude.com/docs/zh-TW/permissions.md#manage-permissions)強制對該命令顯示提示，您終端機中的權限對話框會在命令旁列出這些主機，在該處核准即同時涵蓋兩者。

每個命令的清單只會放寬沙箱預設拒絕的內容。[`deniedDomains`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-network-denieddomains) 項目仍會封鎖。當 [`strictAllowlist`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-network-strictallowlist) 或 [`allowManagedDomainsOnly`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-network-allowmanageddomainsonly) 鎖定允許清單時，Claude Code 會拒絕每個命令的清單。

當每個命令的清單生效時，Claude Code 會拒絕連到任何未被已核准命令列出的主機，且不會顯示提示或進行分類器檢查。拒絕訊息會在命令結果中指名該主機，Claude 會將該主機加入後重新執行命令。

#### 網域清單中的 IPv6 位址

若要在 `allowedDomains`、`deniedDomains` 或 `WebFetch(domain:...)` 規則中比對 IPv6 位址，請將位址寫在方括號中：`"[::1]"` 會比對該位址的所有連接埠，而 `"[::1]:443"` 只會比對其連接埠 443。方括號形式需要 Claude Code v2.1.229 或更新版本。

未加方括號的項目（例如 `::1:443`）具有歧義，既可能是一個位址，也可能是一個加上連接埠的位址：

* **拒絕清單**：Claude Code 會拒絕該項目可解析出的每一種解讀，因此無論您想要的是哪一種解讀都會被封鎖。對於無法解析出任何解讀的項目，Claude Code 不會封鎖任何內容
* **允許清單**：Claude Code 絕不會允許超出您所寫的內容。當有歧義的項目可以乾淨地解析為主機加連接埠的解讀時，Claude Code 會將其改寫為該解讀，並且可能會完全捨棄該項目，而不是放寬允許清單

若要找出有歧義的項目，請在您的終端機中執行 `claude doctor`，並尋找 `Sandbox network domain entries have unreliable spellings` 警告。將每個有歧義的項目改寫為方括號形式。

### 作業系統層級的強制執行

沙箱化的 Bash 工具使用作業系統的安全原語：

* **macOS**：使用 Seatbelt 強制執行沙箱
* **Linux**：使用 [bubblewrap](https://github.com/containers/bubblewrap) 進行隔離
* **WSL2**：使用 bubblewrap，與 Linux 相同

您也可以單獨執行 [`@anthropic-ai/sandbox-runtime`](https://github.com/anthropics/sandbox-runtime) 套件來包裝 Claude Code 程序。請參閱[沙箱執行環境](https://code.claude.com/docs/zh-TW/sandbox-environments.md#sandbox-runtime)。

## 沙箱隔離如何與權限和權限模式相關

沙箱隔離、[權限規則](https://code.claude.com/docs/zh-TW/permissions.md)和[權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md)是互補的層級。下面的章節涵蓋沙箱隔離如何與每一個互動。

### 權限規則

權限規則和沙箱隔離控制不同的事項：

* **權限規則**控制 Claude Code 可以使用哪些工具，並在任何工具執行前進行評估。它們適用於每個工具：Bash、Read、Edit、WebFetch、MCP 和其他工具，除了拒絕或詢問規則無法阻止 [`EndConversation`](https://code.claude.com/docs/zh-TW/tools-reference#endconversation-tool-behavior)，而其他任何工具仍然存在。
* **沙箱機制**提供作業系統層級的強制執行，限制 shell 命令在檔案系統和網路層級可以存取的內容。它適用於 Bash、PowerShell 和 [Monitor](https://code.claude.com/docs/zh-TW/tools-reference.md#monitor-tool) 工具命令及其子程序。

這兩個層級在強制執行方式上也有所不同。Claude Code 在命令執行前根據命令字串評估權限決定，在自動模式下，還會根據單獨分類器對命令是否安全的判斷。作業系統在執行中的程序上強制執行沙箱邊界，因此無論模型選擇執行什麼，即使允許的命令執行的操作超出其名稱所示，它都會保持有效。

檔案系統和網路限制通過沙箱設定和權限規則進行配置：

| 設定或規則 | 功能 |
| :- | :- |
| `sandbox.filesystem.allowWrite` | 授予子程序對工作目錄外路徑的寫入存取權限 |
| `sandbox.filesystem.denyWrite` 和 `sandbox.filesystem.denyRead` | 阻止子程序存取特定路徑 |
| `sandbox.filesystem.allowRead` | 重新允許讀取 `denyRead` 區域內的特定路徑 |
| [`sandbox.filesystem.disabled`](#disable-filesystem-isolation) | 完全關閉檔案系統層級，同時保持網路隔離 |
| `Edit` 允許規則 | 授予對特定路徑的寫入存取權限，與 `sandbox.filesystem.allowWrite` 的方式相同 |
| `Read` 和 `Edit` 拒絕規則 | 阻止存取特定檔案或目錄 |
| `WebFetch(domain:...)` 允許和拒絕規則 | 控制網域存取 |
| 沙箱 `allowedDomains` | 控制 Bash 命令可以到達哪些網域 |
| 沙箱 `deniedDomains` | 阻止特定網域，即使更廣泛的 `allowedDomains` 萬用字元原本會允許它們 |

來自沙箱設定和權限規則的路徑和網域會合併到最終的沙箱配置中。

[claude-code 儲存庫的範例目錄](https://github.com/anthropics/claude-code/tree/main/examples/settings)包含常見部署場景的入門設定配置，包括沙箱特定的範例。使用這些作為起點，並根據您的需求進行調整。

### 權限模式

`/sandbox` 不是[權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md)。權限模式決定工具呼叫是否執行以及是否先提示您，而沙箱限制 Bash 命令執行後可以存取的內容。它們在控制的內容和替代每個動作提示的內容上有所不同：

| | 控制的內容 | 替代提示的內容 |
| :- | :- | :- |
| `/sandbox` | Bash 命令執行後可以存取的內容 | 沙箱邊界本身，在[自動允許模式](#sandbox-modes)中 |
| [自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode) | 每個工具呼叫是否執行 | 檢查動作的分類器 |
| `--dangerously-skip-permissions` | 每個工具呼叫是否執行 | 無。[受保護路徑](https://code.claude.com/docs/zh-TW/permission-modes.md#protected-paths)檢查也會被跳過；[任何模式都不會自動核准的動作](https://code.claude.com/docs/zh-TW/permission-modes.md#actions-no-mode-auto-approves)仍然適用 |

沙箱的[自動允許模式](#sandbox-modes)與[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)分開：自動允許因為沙箱邊界包含它們而核准 Bash 命令，而自動模式使用分類器檢查動作。這兩者獨立運作，可以結合使用，但[沙箱模式](#sandbox-modes)下列出的例外情況除外。若要為無人值守執行選擇隔離邊界，請參閱[沙箱環境](https://code.claude.com/docs/zh-TW/sandbox-environments.md#how-isolation-relates-to-permission-modes)。如需常見權限模式和沙箱配對的表格以及啟動每個配對的旗標，請參閱[常見設定](https://code.claude.com/docs/zh-TW/permission-modes.md#common-setups)。

## 為您的組織設定沙箱

管理員可以為每個使用者要求沙箱機制，防止開發人員擴大策略，並透過公司代理伺服器路由沙箱流量。

### 使用受管設定強制執行沙箱化

若要為每個開發人員要求沙箱，請透過[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)傳遞 `sandbox` 鍵，可以是由您的 MDM 管理的檔案，也可以是透過 claude.ai 上的[伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)。

以下受管設定組態會啟用沙箱，在平台不受支援或缺少相依性時拒絕啟動 Claude Code，並防止模型在沙箱外重試命令：

```json theme={null}
{
  "sandbox": {
    "enabled": true,
    "failIfUnavailable": true,
    "allowUnsandboxedCommands": false
  }
}
```

除了 `enabled` 之外的兩個鍵控制沙箱無法執行命令時會發生什麼：

* **`failIfUnavailable`**：當平台不支援沙箱，或啟動時的相依性檢查失敗時，Claude Code 會拒絕啟動，而不是回退到未沙箱化執行
* **`allowUnsandboxedCommands: false`**：Claude Code 會忽略 `dangerouslyDisableSandbox` 逃生艙，因此當命令在沙箱下失敗時，Claude 無法在未沙箱化的情況下重試

請考慮同時加入以下項目：

* 為任何必須在沒有隔離的情況下執行的組織核准工具新增 `excludedCommands`，因為此設定[會阻止儲存庫的設定將命令移出沙箱](#repository-settings-under-an-admin-required-sandbox)
* 為憑證目錄（例如 `~/.aws` 和 `~/.ssh`）和祕密環境變數新增 [`sandbox.credentials`](#protect-credentials) 項目，因為預設讀取策略仍允許這些

此設定會將 Claude 執行的命令沙箱化。開發人員仍然可以在 [`!` shell 模式提示字元](https://code.claude.com/docs/zh-TW/interactive-mode#shell-mode-with-prefix)輸入命令並在沙箱外執行，具有與他們在 Claude Code 外任何終端機中已有的相同存取權限。請參閱[嚴格沙箱模式](#turn-off-the-retry-with-strict-sandbox-mode)，了解輸入的命令在沙箱中執行的工作階段。

沙箱無法在原生 Windows 上執行，因此設定 `failIfUnavailable` 時，Claude Code 會在這些機器上於啟動時結束。如果您的機隊包括 Windows 主機，您可以：

* **依作業系統傳遞設定**：僅在 macOS 和 Linux 機器上透過您的 MDM 或以[受管設定檔](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)部署。[伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md#current-limitations)會套用至組織中的所有使用者
* **將 Windows 使用者移至受支援的環境**：讓他們在 WSL2 或容器內執行 Claude Code

### 防止開發人員擴大策略

當受管設定設定了布林鍵（例如 `enabled` 或 `failIfUnavailable`）時，Claude Code 會使用受管值並忽略開發人員在本機設定的任何內容。對於陣列鍵（例如 `allowRead`），Claude Code 會合併來自工作階段載入之範圍的項目，因此除非有鎖定涵蓋該鍵，否則開發人員可以附加擴大策略的項目。

除非受管設定已設定這些鍵，否則開發人員的使用者設定或 `--settings` 可以開啟下列鍵。儲存庫的 `.claude/settings.json` 也可以，除非沙箱是[管理員要求的](#repository-settings-under-an-admin-required-sandbox)。每一個鍵都會削弱沙箱，因此如果您不希望使用它，請在受管設定中將其設定為 `false`：

* [`enableWeakerNestedSandbox`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-enableweakernestedsandbox)
* [`enableWeakerNetworkIsolation`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-enableweakernetworkisolation)
* [`network.allowAllUnixSockets`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-network-allowallunixsockets)
* [`network.allowLocalBinding`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-network-allowlocalbinding)
* [`allowAppleEvents`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-allowappleevents)，儲存庫無法開啟此鍵
* [`allowNestedUserNamespaces`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-allownestedusernamespaces)，儲存庫無法開啟此鍵

在受管設定中將 `allowManagedReadPathsOnly` 設定為 `true`，以便只有來自受管設定的 `allowRead` 項目被尊重。這防止開發人員擴大讀取存取超過組織核准的路徑。若要以相同方式將網路網域鎖定到受管值，請設定 [`allowManagedDomainsOnly`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-network-allowmanageddomainsonly)。開啟 `allowManagedDomainsOnly` 後，只有受管設定可以設定[代理伺服器連接埠](#custom-proxy-configuration)。

當受管設定設定 `sandbox.filesystem` 或列出任何具有 `"mode": "deny"` 的 `sandbox.credentials.files` 項目時，只有受管設定可以設定 [`filesystem.disabled`](#disable-filesystem-isolation)，因此開發人員無法使用該鍵關閉檔案系統隔離。[有效的](https://code.claude.com/docs/zh-TW/settings-reference.md#invalid-credential-entries-in-managed-settings) `mask` 項目不會鎖定該鍵。請參閱[哪些設定可以停用它](#which-settings-can-disable-it)。

#### 管理員要求沙箱時的儲存庫設定

當下列任一設定生效時，沙箱即為管理員要求的：

* [`allowUnsandboxedCommands`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-allowunsandboxedcommands) 在受管設定中設定為 `false`，或透過 `--settings` 旗標設定為 `false`（除非受管設定將其設定為 `true`）
* [`allowManagedDomainsOnly`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-network-allowmanageddomainsonly) 在受管設定中設定為 `true`

這些設定不會開啟沙箱，因此也請設定 `enabled`。

當沙箱為管理員要求時，Claude Code 只會從受管設定、`--settings` 旗標以及每位開發人員的 `~/.claude/settings.json` 採用放寬沙箱的設定。它會忽略儲存庫的 `.claude/settings.json` 和 `.claude/settings.local.json` 中的這些設定：

| 儲存庫設定 | Claude Code 忽略的內容 |
| :- | :- |
| `excludedCommands`、`ignoreViolations`、`network.allowedDomains`、`network.allowUnixSockets`、`network.allowMachLookup`、`network.httpProxyPort`、`network.socksProxyPort` | 每個項目 |
| `filesystem.allowWrite`、`Edit(...)` 允許規則、`permissions.additionalDirectories` | 每個項目為沙箱化命令提供的寫入存取權限。Claude 的檔案工具仍會遵循 `Edit(...)` 規則和額外目錄 |
| `WebFetch(domain:...)` 允許規則 | 每條規則新增至沙箱允許清單的主機。WebFetch 工具仍會遵循該規則 |
| `enableWeakerNestedSandbox`、`enableWeakerNetworkIsolation`、`network.allowAllUnixSockets`、`network.allowLocalBinding` | `true`。`false` 仍會套用 |
| `enabled`、`failIfUnavailable` | `false`，當開發人員的 `~/.claude/settings.json` 設定為 `true` 時 |
| `filesystem.allowRead` | 位於受管設定、`--settings` 或使用者設定拒絕讀取的路徑或其下的項目，或可能與其相符的 glob |

當沙箱為管理員要求時，這些設定仍會套用：

* **在儲存庫的檔案中**：拒絕項目和 `autoAllowBashIfSandboxed` 值。在受管設定中設定該鍵，以防止儲存庫變更它
* **在開發人員自己的設定中**：表格中的設定仍會從 `~/.claude/settings.json` 或 `--settings` 套用，除非有僅限受管的鎖定（例如 `allowManagedDomainsOnly`）涵蓋它們。其中大多數（例如 `excludedCommands` 和 `filesystem.allowWrite`）沒有僅限受管的鎖定

[使用受管設定強制執行沙箱化](#enforce-sandboxing-with-managed-settings)下的設定會使沙箱成為管理員要求的。請將您核准的工具所需的 `excludedCommands`、`allowWrite` 和通訊端項目新增至受管設定，因為儲存庫無法提供它們。

需要 Claude Code v2.1.285 或更新版本。從 v2.1.282 到 v2.1.284，相同的設定會使 Claude Code 忽略儲存庫的 `excludedCommands` 項目。

#### 不需管理員要求沙箱即套用的鎖定

某些設定會使 Claude Code 忽略直接覆寫某項限制的儲存庫鍵，即使沙箱不是管理員要求的。每個設定只有在您於其所在列指名的檔案中設定時才有此效果，且儲存庫的其他沙箱設定仍會套用。需要 Claude Code v2.1.285 或更新版本。

| 設定 | 設定位置 | Claude Code 在儲存庫設定中忽略的內容 |
| :- | :- | :- |
| `network.deniedDomains` 或 `WebFetch(domain:...)` 拒絕規則 | 受管設定、`--settings` | `httpProxyPort` 和 `socksProxyPort` |
| `network.strictAllowlist` | 受管設定、`--settings`、使用者設定 | 代理伺服器連接埠、`allowedDomains` 和 `WebFetch(domain:...)` 允許規則 |
| `filesystem.denyRead`、`Read(...)` 拒絕規則或 `credentials.files` 項目 | 受管設定、`--settings` | 位於受管設定、`--settings` 或使用者設定拒絕讀取的路徑或其下的 `allowRead`、`allowWrite`、`Edit(...)` 允許或 `additionalDirectories` 項目，或可能與其相符的 glob |

這些鎖定會改變沙箱化命令可以存取的範圍。WebFetch 工具和 Claude 的檔案工具仍會遵循儲存庫的規則和額外目錄。

### 自訂代理伺服器設定

若要使用您自己的工具檢查、過濾沙箱流量或將其記錄至日誌，請以您在同一台機器上執行的代理伺服器取代內建的沙箱代理伺服器。

若要透過網路上其他位置的公司代理伺服器路由沙箱流量，請改為設定 `HTTPS_PROXY`，如[網路隔離](#network-isolation)下的**公司代理伺服器**項目所述。如此一來，Claude Code 的允許清單仍會套用。

若要將沙箱化命令導向您的代理伺服器，請在[沙箱設定](https://code.claude.com/docs/zh-TW/settings-reference.md#sandbox-settings)中設定其監聽的 localhost 連接埠：

```json theme={null}
{
  "sandbox": {
    "network": {
      "httpProxyPort": 8080,
      "socksProxyPort": 8081
    }
  }
}
```

如果您設定了連接埠，同時也設定了 `HTTPS_PROXY` 或 `HTTP_PROXY`，Claude Code 不會將沙箱化命令傳送至您代理伺服器的內容再轉送至這些變數所指名的代理伺服器。若要連線至公司代理伺服器，請設定您自己的代理伺服器轉送至該伺服器。

哪些檔案可以設定連接埠取決於您的其他沙箱設定。適用第一個符合的情況：

* **`allowManagedDomainsOnly` 已開啟**：僅限受管設定
* **沙箱是[管理員要求的](#repository-settings-under-an-admin-required-sandbox)，或套用了[較窄的網路鎖定](#locks-that-apply-without-an-admin-required-sandbox)**：受管設定、`--settings` 和使用者設定
* **其他情況**：任何設定檔

Claude Code 會忽略在其他任何位置設定的連接埠。在 v2.1.285 之前，任何設定檔都可以設定連接埠。

> [!WARNING]
>
> 一旦任一連接埠生效，您的代理伺服器就負責過濾傳送至它的所有內容。Claude Code 自身的網路控制（例如 `allowedDomains`、`deniedDomains`、`strictAllowlist`、核准提示和[本機位址檢查](#hostnames-that-resolve-to-local-addresses)）將不再套用於該流量。沙箱化命令可以連線至任一代理伺服器，因此如果您只設定一個連接埠，Claude Code 在另一個代理伺服器上的網域清單並不會限制該命令透過您的代理伺服器所能存取的內容。

## 疑難排解

某些命令在沙箱內會失敗，即使它們在沙箱外可以正常運作。請找出與您的症狀或錯誤訊息相符的標題。

如果您組織的沙箱是[管理員強制要求的](#repository-settings-under-an-admin-required-sandbox)，Claude Code 會忽略專案設定檔中這些修正所提到的設定，因此請將它們儲存在 `~/.claude/settings.json` 中，這樣它們會套用於每個專案。如果某項修正仍然沒有效果，可能是您組織的受管設定設定了該設定鍵。

新增 `excludedCommands` 模式的修正，會讓該模式所比對的命令脫離沙箱。請參閱[被排除的命令可以做什麼](#run-commands-outside-the-sandbox-with-excludedcommands)。

### 命令因主機不允許錯誤而失敗

許多 CLI 工具需要連線到特定主機。在出現提示時核准該主機，或將其新增到 [`allowedDomains`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-network-alloweddomains)。如果您的組織使用 `allowManagedDomainsOnly` 鎖定允許清單，則不會出現提示，因此請要求您的管理員新增該主機。

### `jest` 掛起或失敗

`watchman` 與沙箱不相容。改為執行 `jest --no-watchman`。

### Go 型 CLI 在 macOS 上 TLS 驗證失敗

`gh`、`gcloud` 和 `terraform` 等工具在 [Seatbelt](#os-level-enforcement) 下可能無法通過 TLS 驗證。若要在沙箱外執行這些工具，請為每個工具新增一個模式（例如 `gh *`）到 [`excludedCommands`](#run-commands-outside-the-sandbox-with-excludedcommands)。該工具隨後會以您的完整存取權限及其已儲存的憑證執行。如果您將 `httpProxyPort` 與 MITM 代理伺服器和自訂 CA 搭配使用，請改為將 [`enableWeakerNetworkIsolation`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-enableweakernetworkisolation) 設定為 `true`。

### `open`、`osascript` 或瀏覽器型驗證流程在 macOS 上因錯誤 `-600` 而失敗

沙箱預設會阻止 Apple Events。在您的使用者、受管理或 CLI 設定中將 [`allowAppleEvents`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-allowappleevents) 設定為 `true` 以允許它們。Claude Code 會忽略專案設定中的此設定鍵。

啟用 `allowAppleEvents` 會移除程式碼執行隔離，因為沙箱化命令之後可以在未經沙箱化且無使用者提示的情況下啟動其他應用程式，並向執行中的應用程式傳送 AppleScript 命令，受限於 macOS 自動化同意提示 (TCC)。或者，將 `open *` 之類的模式新增到 [`excludedCommands`](#run-commands-outside-the-sandbox-with-excludedcommands)。這樣每次 `open` 呼叫都會經過權限流程，而 `open` 可以啟動任何檔案或應用程式，包括 Claude 所寫的檔案或應用程式。

### `docker` 命令失敗

`docker` 與沙箱不相容。使用 `excludedCommands` 模式（例如 `docker compose *`）將您需要的 `docker` 命令移出沙箱。[使用 `excludedCommands` 在沙箱外執行命令](#run-commands-outside-the-sandbox-with-excludedcommands)說明被排除的 `docker` 命令可以存取什麼。範圍較窄的模式會讓較少的命令脫離沙箱。

### Chromium 或 rootless Podman 在 Linux 上於沙箱內失敗

在 Linux 和 WSL2 上，沙箱中的命令預設無法建立使用者命名空間，因此依賴它們的工具會失敗：

* Chromium 結束並顯示 `No usable sandbox!`
* `unshare -U true` 印出 `unshare: unshare failed: Operation not permitted`。開啟 [`allowAllUnixSockets`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-network-allowallunixsockets) 時，可能改為印出 `No space left on device`
* Rootless Podman 印出 `cannot clone: Operation not permitted`，或在更早的階段於其自身的某個資料夾上因 `read-only file system` 而停止

在將 [`CLAUDE_CODE_SUBPROCESS_ENV_SCRUB`](https://code.claude.com/docs/zh-TW/env-vars#variables) 設定為 `1` 的工作階段中，請使用 `--no-sandbox` 啟動 Chromium 或 Electron，並在 Claude Code 之外自行執行任何其他工具。在該工作階段中，[每個命令都會在沙箱中執行](#turn-off-the-retry-with-strict-sandbox-mode)，而下方其他修正所提到的設定都沒有效果。

每項修正都適用於其所指名的工具，並會犧牲部分隔離：

* 對於 Chromium 或 Electron，請使用 `--no-sandbox` 啟動瀏覽器。Claude Code 沙箱維持不變，但瀏覽器會在沒有其自身沙箱的情況下執行網頁內容。
* 對於 rootless Podman、Buildah，或執行瀏覽器或 `unshare` 的指令碼或測試命令，請新增一個模式到 [`sandbox.excludedCommands`](#run-commands-outside-the-sandbox-with-excludedcommands)，例如 `podman *`。相符的命令會以您的完整存取權限在沙箱外執行，而 Claude 可以在執行前編輯您工作目錄中的指令碼。該模式必須與 Claude 所執行的命令相符，因此對於瀏覽器，請比對測試命令，而非瀏覽器本身。
* 若要保留 Chromium 或 Electron 自身的沙箱，或執行巢狀的 bubblewrap 或 `unshare`，請在 `~/.claude/settings.json`（而非專案的 `.claude/settings.json`）中將 [`sandbox.allowNestedUserNamespaces`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-allownestedusernamespaces) 設定為 `true`。需要 Claude Code v2.1.305 或更新版本。以 `unshare` 開頭的命令無論您列出什麼 `excludedCommands` 模式，都會保持在沙箱中，因為 `unshare` 可以啟動任何其他程式。僅靠此設定不足以支援 rootless Podman 或 Buildah，因為沙箱也會以其他方式阻止它們。

> [!WARNING]
>
> 如果您將 `allowNestedUserNamespaces` 設定為 `true`，就會關閉一道安全邊界：來自沙箱化命令的程式碼最終可能在沙箱外執行。
>
> 請勿依賴沙箱的任何限制（包括[受保護路徑](#protected-paths)和 [`credentials.files`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-credentials-files) 項目）來阻止惡意命令。在[自動允許模式](#auto-allow-mode)下，該命令可以在沒有權限提示的情況下執行。如果您的組織有安全團隊，請在開啟此設定之前先與他們確認。

### `pbcopy`、`xclip` 或 `wl-copy` 不會更新剪貼簿

`pbcopy`、`xclip` 和 `wl-copy` 剪貼簿公用程式可能無法從沙箱內到達系統剪貼簿，在這種情況下，傳送給它們的文字不會到達。

若要將 Claude 的輸出放在您的剪貼簿上，請要求 Claude 在其回應中列印它，然後執行 [`/copy`](https://code.claude.com/docs/zh-TW/commands)。`/copy` 從 Claude Code 程序而不是從沙箱化命令寫入剪貼簿。

當 Claude 將文字傳送給這些工具之一時，將工具新增到 [`excludedCommands`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-excludedcommands) 本身不會將該呼叫從沙箱中取出。

### git 命令因 `unable to unlink old` 而失敗

`git merge`、`git checkout` 和類似命令在需要取代沙箱拒絕寫入的檔案時，會因 `unable to unlink old` 而失敗。在 Linux 和 WSL2 上，錯誤以 `Read-only file system` 結尾。該檔案可能位於以下其中一處：

* 在[受保護路徑](#protected-paths)下，例如 `.claude/skills`
* 在您的 `denyWrite` 項目之一下
* 完全在沙箱允許命令寫入的目錄之外

失敗後，Claude 可能會[提供在沙箱外重新執行命令](#the-unsandboxed-retry-escape-hatch)。核准該重試，或在另一個終端機中自己執行 git 命令。如果您已將 `allowUnsandboxedCommands` 設定為 `false`，Claude 無法提供重試，因此請自己執行命令。

### 名為 `objects` 或 `refs` 的資料夾在命令執行後消失

在工作階段期間出現的頂層 `objects` 或 `refs` 資料夾，可能會[在沙箱化命令結束後被刪除](#when-the-sandbox-deletes-head-objects-or-refs)。無論該資料夾是由命令、Claude 還是您所建立的，都是如此。若要保留資料夾，請在其中留下一些內容。如果在工作階段期間頂層曾有 `HEAD` 檔案或符號連結，請將其移走，然後重新啟動在該處開啟的每個 Claude Code 工作階段。

在 v2.1.307 之前，即使資料夾中有內容且沒有 `HEAD`，該資料夾仍會被刪除。若您使用的是較早的版本，請[更新 Claude Code](https://code.claude.com/docs/zh-TW/setup.md#update-claude-code)。

### Bubblewrap 在容器內啟動失敗

在無特權容器中，[bubblewrap](#os-level-enforcement) 無法掛載新的 `/proc` 檔案系統，因此沙箱化命令失敗，出現 `bwrap` 錯誤，例如 `Can't mount proc on /newroot/proc: Operation not permitted`。將 [`enableWeakerNestedSandbox`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-enableweakernestedsandbox) 設定為 `true`，以便沙箱改為綁定掛載容器的現有 `/proc`。僅在外部容器已提供您需要的隔離邊界時使用此設定，因為此設定會向沙箱化命令公開新的 `/proc` 掛載原本會隱藏的程序資訊。

### Ubuntu 的 AppArmor 限制阻止 bubblewrap

在 Linux 和 WSL2 上，訊息 `Ubuntu's AppArmor restriction on user namespaces stops bubblewrap here` 表示 Ubuntu 的 AppArmor 限制使沙箱無法啟動。

若要讓沙箱啟動，請以下列兩種方式之一解除此限制：

* 如果 Claude Code 執行的是 `/usr/bin/bwrap`，請[為 bubblewrap 新增 AppArmor 設定檔](#add-an-apparmor-profile-for-bubblewrap)
* 在您的 shell 中執行 `sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0`，這會為機器上的每個程式解除此限制，並持續到您重新開機為止

然後重新啟動 Claude Code 並[確認沙箱正常運作](#confirm-commands-run-inside-the-sandbox)。

在您解除此限制之前，命令會在一般權限流程下不經沙箱執行；如果 [`sandbox.failIfUnavailable`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-failifunavailable) 為 `true`，Claude Code 則會拒絕啟動。

### 沙箱化命令因 `bwrap: setting up uid map: Permission denied` 而失敗

在 Linux 和 WSL2 上，此錯誤或 `bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted` 可能表示 Ubuntu 對使用者命名空間的 AppArmor 限制正在阻止 bubblewrap。若要檢查，請在您的 shell 中執行 `sysctl kernel.apparmor_restrict_unprivileged_userns`：

* `kernel.apparmor_restrict_unprivileged_userns = 1`：此限制已開啟。如果 Claude Code 執行的是 `/usr/bin/bwrap`，請[新增 AppArmor 設定檔](#add-an-apparmor-profile-for-bubblewrap)，或執行 `sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0`，這會為每個程式解除此限制，直到您重新開機為止。然後重新啟動 Claude Code 並[確認沙箱正常運作](#confirm-commands-run-inside-the-sandbox)
* 任何其他輸出：此限制並非原因。若要回報此失敗，請在 Claude Code 提示字元執行 [`/feedback`](https://code.claude.com/docs/zh-TW/commands#all-commands)

在 v2.1.310 之前，Claude Code 不會在啟動時檢查此限制，因此 `/sandbox` 不會回報它。

### 0 位元組唯讀檔案出現在 `.claude` 設定路徑，且「是，不要再問」不會儲存

在 Linux 和 WSL2 上，沙箱在沙箱化命令執行時透過在該處建立 0 位元組唯讀預留位置來保持對尚不存在的檔案的寫入拒絕。沙箱在之後移除預留位置。

在下列情況中，預留位置會被留下：

* 工作階段在該清理執行之前被終止，例如透過 SIGKILL
* 工作階段在沙箱化命令仍在執行時結束，例如背景命令

稍後的工作階段在每次啟動時再次將這些預留位置綁定為唯讀，因此設定寫入（例如儲存權限選擇）會在仍留有預留位置的路徑上失敗。

在您的終端機中執行 `claude doctor` 以列出剩餘的預留位置檔案。[`Sandbox mask files left behind at write-deny paths`](https://code.claude.com/docs/zh-TW/errors#stale-sandbox-mask-files-left-by-a-killed-session) 警告會列出其中一部分，並計算其餘的數量。在該專案中沒有其他 Claude Code 工作階段執行時，使用 `rm` 刪除每個檔案。在 v2.1.257 之前，Claude Code 在工作階段被終止時會留下相同的預留位置，而不會標記它們。

### 啟用沙箱時透過 SSH 執行 `git` 失敗

在 macOS 上，針對 SSH 遠端執行的 `git fetch`、`git pull` 和 `git push` 即使在主機已被允許的情況下，也會在沙箱內失敗。在 Linux 和 WSL2 上，只要主機被允許，它們就能正常運作。Claude Code 會透過[沙箱代理伺服器](#network-isolation)為 git 的 SSH 連線建立通道，而 macOS 的通道無法向該代理伺服器進行身分驗證。

在 Linux 和 WSL2 上，如果連線仍然失敗，請檢查以下項目：

* **主機在連接埠 22 上被允許**：不含連接埠的 `allowedDomains` 項目（例如 `"git.example.com"`）即涵蓋此情況
* **您的企業代理伺服器允許連接埠 22**：如果您的網路需要上游代理伺服器，通道也會經過它
* **金鑰可以作為檔案讀取**：沙箱可能會封鎖 `ssh-agent` socket，而針對 `~/.ssh` 的 `denyRead` 或 `credentials` 項目會隱藏您的金鑰檔案

在 macOS 上，請將遠端切換為 HTTPS，這需要 HTTPS 憑證，例如個人存取 token：

```bash theme={null}
git remote set-url origin https://git.example.com/example-org/example-repo.git
```

如果您必須保留 SSH 遠端，請使用 [`excludedCommands`](#run-commands-outside-the-sandbox-with-excludedcommands) 將 git 的網路命令移出沙箱：

```json theme={null}
{
  "sandbox": {
    "excludedCommands": ["git fetch *", "git pull *", "git push *"]
  }
}
```

這些項目會比對 `git push origin main`。加上 `cd`、使用 `git -C` 或包含命令替換的呼叫會保持在沙箱中。被排除的 git 命令可以連線到任何主機，而不僅限於 `allowedDomains` 中的主機。

透過 SSH 執行的一般 `ssh`、`scp` 和 `rsync` 失敗的原因，與[資料庫用戶端項目](#a-database-client-or-other-non-http-tool-fails-to-reach-an-allowed-host)所述的原因相同。

### 資料庫用戶端或其他非 HTTP 工具無法連線到允許的主機

忽略代理伺服器環境變數的工具無法從沙箱內進行連線，即使目標是 `allowedDomains` 中的主機也一樣。沙箱化命令[沒有直接通往網路的路徑](#network-isolation)，因此自行開啟連線的工具會失敗。大多數資料庫驅動程式、一般的 `ssh`，以及使用 UDP 的工具都是如此。

此失敗看起來像是網路或名稱解析錯誤：

* **macOS**：`Operation not permitted`，或名稱解析錯誤，例如 `Could not resolve host`
* **Linux 和 WSL2**：`Network is unreachable`，或名稱解析錯誤，例如 `Temporary failure in name resolution`

使用代理伺服器的工具在其主機未被允許時，會以不同的方式失敗。您會收到網路提示，或者工具會收到來自代理伺服器的 `403` 回應。

若要讓工具能夠連線，請使用 [`excludedCommands`](#run-commands-outside-the-sandbox-with-excludedcommands) 在沙箱外執行需要它的命令。此範例排除了一個指令碼，並新增一條 [ask 規則](https://code.claude.com/docs/zh-TW/permissions.md)，讓您核准每次執行：

```json theme={null}
{
  "sandbox": {
    "excludedCommands": ["python scripts/load_orders.py *"]
  },
  "permissions": {
    "ask": ["Bash(python scripts/load_orders.py *)"]
  }
}
```

該指令碼會以您的完整存取權限執行，而 Claude 可以編輯位於您工作目錄內的指令碼，因此請在提示出現時檢查它。

### 命令無法連線到 localhost 上的伺服器

預設情況下，沙箱化命令無法直接連線到在您機器上、於沙箱外執行的伺服器，例如開發伺服器或容器中的資料庫。您可以變更的內容取決於您的平台：

* **macOS**：將 [`network.allowLocalBinding`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-network-allowlocalbinding) 設定為 `true`。沙箱化命令之後就可以在網路連接埠上監聽，並連線到 localhost 上的任何連接埠，包括在該處監聽的所有其他服務。不需要身分驗證的 localhost 服務（例如偵錯工具）就可以在沙箱外代替該命令執行動作，而在非 loopback 位址上監聽的命令會接受來自其他機器的連線
* **Linux 和 WSL2**：沙箱化命令的 `localhost` 為該命令所私有。該命令可以在連接埠上監聽，並連線到它自己啟動的伺服器。直接連線到 `localhost` 或 `127.0.0.1` 無法到達主機上的伺服器，且 `allowLocalBinding` 沒有效果。請使用 [`excludedCommands`](#run-commands-outside-the-sandbox-with-excludedcommands) 在沙箱外執行需要主機伺服器的命令，在那裡它不受任何檔案系統或網路限制。關於經過沙箱代理伺服器的連線，請參閱[解析為本機位址的主機名稱](#hostnames-that-resolve-to-local-addresses)

此範例為 macOS 開啟該設定：

```json theme={null}
{
  "sandbox": {
    "network": {
      "allowLocalBinding": true
    }
  }
}
```

針對 `localhost` 的 `allowedDomains` 項目適用於經過代理伺服器的連線，因此不會改變直接連線。Claude Code 會為沙箱化命令設定 `NO_PROXY`，讓它們直接連線到 `localhost`，而不是經過代理伺服器。該項目也會將您機器 localhost 上的每個連接埠公開給確實使用代理伺服器的命令。關於指向 `127.0.0.1` 的開發用主機名稱，請參閱[允許的主機名稱因 `resolved to a loopback address` 而被拒絕](#an-allowed-hostname-is-refused-with-resolved-to-a-loopback-address)。

### 允許的主機名稱因 `resolved to a loopback address` 而被拒絕

沙箱代理伺服器會拒絕[解析為本機位址](#hostnames-that-resolve-to-local-addresses)的允許主機名稱，這會影響指向 `127.0.0.1` 的開發用名稱，例如 `myapp.test`。命令會看到一個 `403` 回應，其內文會指出位址的類型，例如 `Connection to myapp.test blocked: resolved to a loopback address`。

請在 `allowedDomains` 中將該名稱所解析到的 IP 位址與主機名稱一併新增，並各自附上您伺服器所監聽的連接埠：

```json theme={null}
{
  "sandbox": {
    "network": {
      "allowedDomains": ["myapp.test:3000", "127.0.0.1:3000"]
    }
  }
}
```

不含連接埠的 IP 位址項目會讓沙箱化命令能夠連線到在該位址上監聽的每個服務。

在 v2.1.284 之前，代理伺服器會連線到允許的主機名稱所解析到的任何位址。

### 命令因 `Sandbox is required` 而被拒絕

如果您使用 [`sandbox.failIfUnavailable`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-failifunavailable) 要求使用沙箱，而沙箱在 Claude Code 啟動後以下列其中一種方式失敗，Claude 執行的每個沙箱化命令都會被拒絕，並顯示所列的訊息。工作階段會繼續執行，而被拒絕的命令不會在沙箱外執行：

* **`Sandbox is required but failed to initialize: <reason>`**：Claude Code 已啟動，但沙箱隨後初始化失敗。請採取訊息所提供的步驟：`Restart to retry.` 或 `Fix the sandbox settings to retry`。
* **`Sandbox is required (sandbox.failIfUnavailable) and stopped being available in this session: <reason>`**：在 Linux 或 WSL2 上，沙箱已啟動，之後 Claude Code 發現缺少某個相依套件。請修正原因所指出的問題，例如[安裝缺少的相依套件](#set-up-linux-and-wsl2)，然後重新啟動 Claude Code。

被排除的命令和您自行輸入的命令會繼續執行，而 Claude 無法在沙箱外重試被拒絕的命令：

* **被排除的命令**：符合 [`excludedCommands`](#run-commands-outside-the-sandbox-with-excludedcommands) 項目的命令會繼續在沙箱外執行。當其中一個命令寫入您工作目錄外的 [`filesystem.allowWrite`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-filesystem-allowwrite) 路徑時，該寫入會經過一般的權限流程。在[管理員強制要求的沙箱](#repository-settings-under-an-admin-required-sandbox)下，Claude Code 會忽略來自儲存庫設定的項目
* **您在 [`!` shell 模式提示字元](https://code.claude.com/docs/zh-TW/interactive-mode#shell-mode-with-prefix)輸入的命令**：會繼續在沙箱外執行。在[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)中，它們也會被拒絕
* **非沙箱重試**：Claude Code 會忽略[非沙箱重試](#the-unsandboxed-retry-escape-hatch)的 `dangerouslyDisableSandbox` 參數

在設定了 `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB` 的 Linux 工作階段中，每個命令都會在沙箱中執行，因此被排除的命令和您輸入的命令也會被拒絕。

### `/sandbox` 因 `Sandbox settings are overridden by a higher-priority configuration` 而失敗

當較高的[設定層級](https://code.claude.com/docs/zh-TW/settings.md#settings-precedence)設定了 `sandbox.enabled`、`sandbox.autoAllowBashIfSandboxed` 或 `sandbox.allowUnsandboxedCommands` 時，`/sandbox` 會印出 `Error: Sandbox settings are overridden by a higher-priority configuration and cannot be changed locally.`，而不會開啟其面板。該面板會將您的選擇儲存到 `.claude/settings.local.json`，而儲存在那裡的值無法覆寫那些層級。

受管設定和 `--settings` 的優先順序高於本機設定。若要查看此工作階段載入了哪些設定，請執行 `/status` 並閱讀 `Setting sources` 這一行：

* **`Command line arguments`**：如果您使用 [`--settings`](https://code.claude.com/docs/zh-TW/settings#change-a-setting-for-one-session) 啟動 Claude Code，請檢查您傳入的檔案或 JSON 是否設定了上述其中一個設定鍵。如果是，請在那裡變更該值，或在不使用這些設定鍵的情況下重新啟動 Claude Code。
* **`Enterprise managed settings`**：已載入您組織的受管設定。如果它們設定了上述其中一個設定鍵，您就無法從 `/sandbox` 或從您所控制的任何設定檔變更該設定鍵，因此請詢問您的管理員。

### `/sandbox` 印出 `Sandbox settings not changed`

此行表示 `/sandbox` 無法將您在其面板中所做的選擇儲存到專案的 `.claude/settings.local.json`：

```text theme={null}
✗ Sandbox settings not changed: /home/you/project/.claude/settings.local.json couldn't be updated (EACCES). Start Claude Code in a project folder you can write to.
```

如果括號中的原因是 `EACCES`、`EPERM` 或 `EROFS`，請在您可以寫入的專案資料夾中啟動 Claude Code，然後在該工作階段中再次執行 `/sandbox`。如果原因以 `Invalid JSON syntax in settings file` 開頭，請修正專案 `.claude/settings.local.json` 中的 JSON，然後再次執行 `/sandbox`。

如果您沒有可寫入的專案資料夾，請改為從您的使用者設定開啟沙箱。將以下內容新增到 `~/.claude/settings.json`：

```json theme={null}
{
  "sandbox": {
    "enabled": true
  }
}
```

這會開啟[自動允許模式](#sandbox-modes)。若要使用一般權限模式，請同時將 [`sandbox.autoAllowBashIfSandboxed`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-autoallowbashifsandboxed) 設定為 `false`。此變更會在 Claude 執行下一個 shell 命令時於您執行中的工作階段生效，之後 `/sandbox` 的 **Mode** 分頁會標示目前生效的模式。

## 限制

沙箱機制可降低風險，但不是完整的隔離邊界。在依賴它作為硬安全控制之前，請檢查下面的限制。

### 安全限制

* **網路過濾**：沙箱限制程序可以連接的域名。預設情況下，內建代理伺服器不終止或檢查出站流量上的 TLS，因此加密連接的內容不被檢查。實驗性的 [`network.tlsTerminate`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-network-tlsterminate) 設定在代理伺服器處終止 TLS 以進行 [`mask` 憑證替換](#mask-credentials)，但不添加內容過濾。您負責確保只有受信任的域名在您的策略中被允許。

> [!WARNING]
>
> 允許廣泛域名（例如 `github.com`）可能會為資料洩露建立路徑。因為代理伺服器根據用戶端提供的主機名進行允許決定而不檢查 TLS，在沙箱內執行的程式碼可能可以使用 [domain fronting](https://en.wikipedia.org/wiki/Domain_fronting) 或類似技術到達允許清單外的主機。如果您的威脅模型需要更強的保證，請設定 [custom proxy](#custom-proxy-configuration)，它終止 TLS 並檢查流量，並在沙箱內安裝其 CA 憑證。更強的 TLS 感知網路隔離是一個活躍的開發領域。

* **通過 Unix 套接字的特權提升**：`allowUnixSockets` 設定可能會無意中授予對系統服務的存取，這可能導致沙箱繞過。例如，允許存取 `/var/run/docker.sock` 有效地通過 Docker 套接字授予對主機系統的存取。仔細考慮您通過沙箱允許的任何 Unix 套接字。
* **檔案系統權限提升**：過於寬泛的檔案系統寫入權限可能導致特權提升攻擊。允許寫入包含 `$PATH` 中可執行檔案的目錄、系統設定目錄或使用者 shell 設定檔（例如 `.bashrc` 或 `.zshrc`）可能導致當其他使用者或系統程序存取這些檔案時在不同安全上下文中執行程式碼。
* **Linux 沙箱強度**：Linux 實現提供強大的檔案系統和網路隔離，但包含一個 `enableWeakerNestedSandbox` 模式，使其能夠在 Docker 環境中工作而無需特權命名空間。此選項大大削弱了安全性，應僅在其他隔離被強制執行時使用。
* **macOS 上的 Apple Events**：macOS 沙箱預設阻止 Apple Events。`allowAppleEvents` 設定解除此限制，使 `open` 和 `osascript` 等工具能夠運作，但它移除了程式碼執行隔離：沙箱化命令可以啟動其他應用程式而不進行沙箱化，無需使用者提示，並可以向執行中的應用程式傳送 AppleScript 命令，受限於每個應用程式的 macOS 自動化同意提示 (TCC)。它僅從使用者、受管或 CLI 設定中被接受。專案設定無法啟用它。
* **macOS 上的 Mach 和 XPC 服務**：沙箱化命令可以連到沙箱外您在 [`network.allowMachLookup`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-network-allowmachlookup) 中列出的每個服務，而沙箱不會限制這些服務為這些命令所做的事情。
* **Linux 和 WSL2 上的使用者命名空間**：預設情況下，沙箱化命令無法建立使用者命名空間。如果您將 [`allowNestedUserNamespaces`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-allownestedusernamespaces) 設為 `true`，就會關閉一道安全邊界：來自沙箱化命令的程式碼可能最終在沙箱外執行。在開啟此設定之前，請閱讀[在 Linux 上 Chromium 或 rootless Podman 於沙箱內失敗](#chromium-or-rootless-podman-fails-inside-the-sandbox-on-linux)中的警告。

### 範圍

沙箱隔離 shell 命令及其子程序。[在沙箱外執行的內容](#what-runs-outside-the-sandbox)列出了它未涵蓋的工具和輔助程序。電腦使用和 subagents 與沙箱的關係如下：

* **電腦使用**：當 Claude 打開應用程式並控制您的螢幕時，它在您的實際桌面上執行，而不是在隔離環境中。每個應用程式的權限提示控制每個應用程式。請參閱 [CLI 中的電腦使用](https://code.claude.com/docs/zh-TW/computer-use.md) 或 [Desktop 中的電腦使用](https://code.claude.com/docs/zh-TW/desktop.md#let-claude-use-your-computer)。
* **Subagents**：[subagents](https://code.claude.com/docs/zh-TW/sub-agents.md) 在與父工作階段相同的程序中執行，並使用相同的沙箱設定。當在父工作階段中啟用沙箱機制時，subagent 內的 Bash 命令會被沙箱化。
* **背景工作階段**：[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)在其自己的程序中執行，當[其設定](https://code.claude.com/docs/zh-TW/agent-view.md#settings-and-provider)啟用沙箱機制時，其 Bash 命令會被沙箱化。
* **圍繞整個程序的邊界**：若也要將[在沙箱外執行的內容](#what-runs-outside-the-sandbox)中的程序置於邊界之內，請在 [sandbox runtime](https://code.claude.com/docs/zh-TW/sandbox-environments.md#sandbox-runtime) 內執行 Claude Code（本機模式），並將網路允許清單限制為您核准的主機，或在附帶防火牆指令碼的 [dev container](https://code.claude.com/docs/zh-TW/devcontainer.md) 中執行。關於背景服務及其託管的工作階段，請參閱[在企業啟動器後方執行 Claude Code](https://code.claude.com/docs/zh-TW/corporate-launcher.md)。
* **Mods**：[mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md) 是在 Claude Code 內執行其自有程式碼的外掛，而 mod 啟動的程序會在沙箱外執行。請參閱 [mod 可以存取的範圍](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md#what-a-mod-can-reach)。

> [!WARNING]
>
> 有效的沙箱機制需要同時進行檔案系統和網路隔離。沒有網路隔離，受損的 agent 可能會洩露敏感檔案，如 SSH 金鑰。沒有檔案系統隔離，無論是來自寬鬆的策略還是來自 [disabling the filesystem layer](#disable-filesystem-isolation)，受損的 agent 可能會後門系統資源以獲得網路存取。當您擴大預設值時，檢查 `allowWrite` 路徑、廣泛的 `allowedDomains` 項目或 `excludedCommands` 例外是否不會撤銷另一側的限制。

## 另請參閱

* [Sandbox environments](https://code.claude.com/docs/zh-TW/sandbox-environments.md)：比較內建沙箱與開發容器、容器和虛擬機
* [Security](https://code.claude.com/docs/zh-TW/security.md)：安全功能和最佳實踐
* [Permissions](https://code.claude.com/docs/zh-TW/permissions.md)：權限配置和存取控制
* [All settings](https://code.claude.com/docs/zh-TW/settings-reference.md)：每個設定鍵
* [CLI reference](https://code.claude.com/docs/zh-TW/cli-reference.md)：命令列選項

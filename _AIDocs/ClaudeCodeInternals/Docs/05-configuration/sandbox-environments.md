<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/sandbox-environments | lastmod: 2026-10-25 | section: Configuration / Permissions and sandboxing -->
> 來源：https://code.claude.com/docs/zh-TW/sandbox-environments（官方 zh-TW，lastmod 2026-10-25）｜分類：Configuration › Permissions and sandboxing｜EN 摘要：Compare Claude Code sandbox options: the built-in sandboxed Bash tool, sandbox runtime, dev containers, Docker, and VMs. Choose the right isolation for your threat model.

# 選擇沙箱環境

> 比較 Claude Code 沙箱選項：內建的沙箱化 Bash 工具、sandbox runtime、dev containers、Docker 和虛擬機。為您的威脅模型選擇適當的隔離。

隔離 Claude Code 會限制一個會話可以讀取、寫入和在網路上存取的內容。當您讓 Claude 在較少的權限提示下工作、無人值守地執行它，或將其指向您不完全信任的程式碼時，這一點最為重要。

Claude Code 可以在多種隔離環境中執行，範圍從輕量級的每個命令沙箱到完全獨立的虛擬機。本頁涵蓋如何比較它們隔離的內容和所需條件，幫助您為威脅模型選擇一個，並展示如何在整個組織中強制執行該選擇。

> [!NOTE]
>
> 有關更廣泛的安全模型，請參閱 [安全性](https://code.claude.com/docs/zh-TW/security.md)。有關 Agent SDK 部署，請參閱 [安全部署](https://code.claude.com/docs/zh-TW/agent-sdk/secure-deployment.md)。

## 比較沙箱方法

下表中的前兩種方法在主機作業系統上執行，不使用容器。其餘的方法將 Claude Code 放在容器或虛擬機內。

| 方法 | 隔離的內容 | 需要 Docker | 設定工作量 |
| :- | :- | :- | :- |
| [Sandboxed Bash tool](#sandboxed-bash-tool) | Bash、PowerShell 和 Monitor 工具命令及其子程序 | 否 | macOS 上最少；Linux 和 WSL2 上較少 |
| [Sandbox runtime](#sandbox-runtime) | 整個 Claude Code 進程，包括檔案工具、MCP 伺服器和 hooks | 否 | 較少 |
| [Dev container](#dev-containers) | 完整開發環境 | 是 | 中等 |
| [Custom container](#custom-container) | 完整開發環境 | 是 | 中等到高 |
| [Virtual machine](#virtual-machine) | 完整作業系統 | 否 | 高 |
| [Cloud sessions](#cloud-sessions) | 完整作業系統，由 Anthropic 託管 | 否 | 無；需要 Claude 訂閱和已連接的 GitHub 帳戶，除非您使用 `claude --cloud` 啟動 |

[Sandboxed Bash tool](https://code.claude.com/docs/zh-TW/sandboxing.md) 內建於 Claude Code 中，僅限制 Bash 命令。內建檔案工具、MCP 伺服器和 hooks 仍直接在您的主機上執行。表中的所有其他方法都將整個 Claude Code 進程放在隔離邊界內，因此檔案工具、MCP 伺服器和 hooks 也受到限制。

> [!WARNING]
>
> 沙箱隔離可減少違規的影響，但不能消除風險。任何允許網路出站的方法仍然可能洩露代理可以讀取的資料，任何以可寫方式掛載您的專案目錄的方法仍然可以修改該程式碼。在依賴沙箱作為硬控制之前，請查看 [security limitations](https://code.claude.com/docs/zh-TW/sandboxing.md#security-limitations)。
>
> 隔離也不會改變發送到模型的內容。您的提示和 Claude 讀取的檔案無論是否使用沙箱，都會傳輸到 Anthropic API 或您配置的提供者。有關 Claude Code 發送的內容以及如何減少它，請參閱 [Data usage](https://code.claude.com/docs/zh-TW/data-usage.md)。

## 選擇一個方法

將您的目標與下方的一列相符，然後閱讀隨後的詳細部分。

| 您想要 | 開始使用 |
| :- | :- |
| 在您自己的機器上減少日常工作中的權限提示 | [沙箱化 Bash 工具](https://code.claude.com/docs/zh-TW/sandboxing.md)，使用 `/sandbox` 設定 |
| 讓 Claude 使用 `--dangerously-skip-permissions` 或自動模式無人值守工作 | 預先設定的 [開發容器](https://code.claude.com/docs/zh-TW/devcontainer.md)、任何容器或虛擬機，或 [沙箱執行時](#sandbox-runtime) |
| 隔離 MCP 伺服器和 hooks 以及 Bash，無需 Docker | 沙箱執行時 |
| 在不受信任的儲存庫上工作 | 專用虛擬機，或 [雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)（如果您有 Claude 訂閱）；使用 `claude --cloud` 啟動時不需要 GitHub |
| 在團隊中標準化沙箱化環境 | 預先設定的 [開發容器](https://code.claude.com/docs/zh-TW/devcontainer.md)，複製到您的儲存庫中 |
| 從沒有本機設定的裝置使用 Claude Code | [雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)，需要 Claude 訂閱和已連接的 GitHub 帳戶 |
| 為組織中的每位開發人員要求隔離 | [在整個組織中強制隔離](#enforce-isolation-across-an-organization) |
| 在原生 Windows 主機上工作 | 容器或虛擬機，或在 WSL2 內執行 Bash 沙箱 |

### 隔離如何與權限模式相關

[權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md)決定工具呼叫是否執行以及是否先提示您。隔離限制命令執行後可以存取的內容。兩者協同工作：當權限模式允許動作在不詢問您的情況下執行時，隔離邊界限制這些動作可以到達的內容。

當您傳遞 `--dangerously-skip-permissions` 時，Claude 在不先詢問您的情況下執行動作。[任何模式都不會自動核准的動作](https://code.claude.com/docs/zh-TW/permission-modes.md#actions-no-mode-auto-approves)仍然適用。

沒有提示來捕捉錯誤，您選擇的隔離邊界是保護您系統的因素。始終在容器、虛擬機或 [沙箱執行時](#sandbox-runtime)內執行 `--dangerously-skip-permissions` 工作階段，以便檔案工具、MCP 伺服器和 hooks 也在邊界內。在 Linux 和 macOS 上，Claude Code 在以 root 身份執行時拒絕使用此旗標啟動，因此請以非 root 使用者身份執行容器、虛擬機或沙箱執行時。

[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)將提示替換為檢查動作的分類器。分類器是按動作的控制，而不是隔離邊界，因此隔離邊界仍為無人值守執行增加深度防禦，並且不像 `--dangerously-skip-permissions` 那樣是必需的。

[沙箱化 Bash 工具](#sandboxed-bash-tool)本身只限制 shell 命令，因此對於任一模式中的完全無人值守執行都不夠。您可以分層方法：在容器或虛擬機內執行沙箱化 Bash 工具可在外部環境邊界之上為您提供作業系統級命令限制。有關 Bash 沙箱本身如何與權限規則和權限模式互動的詳細資訊，請參閱 [沙箱化如何與權限和權限模式相關](https://code.claude.com/docs/zh-TW/sandboxing.md#how-sandboxing-relates-to-permissions-and-permission-modes)。

## Sandboxed Bash tool

> [!NOTE]
>
> 此選項不支援原生 Windows。在 Windows 主機上，使用 WSL2 或下面的容器或虛擬機方法之一。

Sandboxed Bash tool 內建於 Claude Code 中。它使用作業系統原語來限制 Claude 執行的 Bash、PowerShell 和 Monitor 工具命令的檔案系統和網路存取。

執行 `/sandbox` 命令以開啟沙箱面板並選擇一個模式。[Sandboxing](https://code.claude.com/docs/zh-TW/sandboxing.md) 指南涵蓋批准模式、預設邊界以及如何擴大或縮小它。

每個命令沙箱不涵蓋在會話中執行的所有內容：

* 其他 [built-in tools](https://code.claude.com/docs/zh-TW/tools-reference.md)（如 Read、Edit 和 WebFetch）在 Claude Code 進程內執行，不會生成任意程式碼。[Permission rules](https://code.claude.com/docs/zh-TW/permissions.md) 用於路徑或域來控制它們。
* [MCP](https://code.claude.com/docs/zh-TW/mcp.md) 伺服器、[command hook](https://code.claude.com/docs/zh-TW/hooks.md#command-hook-fields) 和[外掛監視器](https://code.claude.com/docs/zh-TW/plugins/components.md#monitors)是在主機上不受限制執行的獨立程序。關於以此方式執行的其他程序，請參閱[在沙箱外執行的內容](https://code.claude.com/docs/zh-TW/sandboxing.md#what-runs-outside-the-sandbox)。

要將內建工具、MCP 伺服器和 hooks 全部放在一個作業系統邊界後面，請在 [sandbox runtime](#sandbox-runtime)、[dev container](#dev-containers) 或 [custom container](#custom-container) 內執行整個 Claude Code 進程。

## Sandbox runtime

[`@anthropic-ai/sandbox-runtime`](https://github.com/anthropics/sandbox-runtime) 套件將整個程序包裝在內建 Bash 沙箱使用的相同 Seatbelt 或 bubblewrap 隔離中。透過該 runtime 執行 Claude Code 會限制工作階段的工具、hook 和 MCP 伺服器，以及 shell 命令。該 runtime 是測試版研究預覽，其設定格式可能會隨著套件的發展而改變。

本節涵蓋您設定的內容以及 runtime 自行強制執行的內容。有關在 Agent SDK 應用程式中部署 runtime，請參閱[安全部署指南](https://code.claude.com/docs/zh-TW/agent-sdk/secure-deployment.md#sandbox-runtime)。

### 設定和啟動 runtime

在 Linux 和 WSL2 上，runtime 依賴於內建沙箱使用的相同 `bubblewrap` 和 `socat` 套件，加上 `ripgrep`，Claude Code 會捆綁但獨立 runtime 從您的 PATH 解析。按照[設定 Linux 和 WSL2](https://code.claude.com/docs/zh-TW/sandboxing.md#set-up-linux-and-wsl2) 中的說明安裝 `bubblewrap` 和 `socat`，並從您的發行版套件管理員安裝 `ripgrep`。在 macOS 上，您不需要任何額外的套件。runtime 在那裡使用內建的 Seatbelt 沙箱。

預設情況下，runtime 拒絕網路存取並將寫入限制在一小組內建 runtime 路徑，因此在透過它啟動 Claude Code 之前先設定它。將您的設定放在 `~/.srt-settings.json` 中，或在您使用 `--settings` 傳遞的檔案中。套件 [README](https://github.com/anthropics/sandbox-runtime) 記錄了設定 schema。

至少允許寫入存取：

* 您的專案目錄。
* Claude Code 的設定路徑 `~/.claude` 和 `~/.claude.json`。
* Claude Code 寫入 runtime 檔案的目錄。除非您設定 [`CLAUDE_CODE_TMPDIR`](https://code.claude.com/docs/zh-TW/env-vars)，否則該目錄為：
  * **Linux 和 WSL2**：`/tmp`
  * **macOS**：`/private/tmp`。`/tmp` 是指向該目錄的符號連結，而 Seatbelt 會檢查解析後的路徑。

允許您的工作階段需要的網路網域：

* `api.anthropic.com`，或您設定的提供者的端點。在第三方提供者上，也保留 `api.anthropic.com`：WebFetch 網域安全檢查預設仍會呼叫它，除非您設定 `skipWebFetchPreflight: true`。
* `claude.ai` 和 `platform.claude.com`，[OAuth 登入和 token 重新整理](https://code.claude.com/docs/zh-TW/network-config.md#network-access-requirements)需要這些。使用 API 金鑰進行身分驗證的執行可以捨棄這兩個。

在 Linux 和 WSL2 上，runtime 僅將寫入授予應用於已存在的路徑。在全新環境中，在首次啟動前建立 Claude Code 的設定路徑：

```bash theme={null}
mkdir -p ~/.claude && { [ -f ~/.claude.json ] || echo '{}' > ~/.claude.json; }
```

以全域方式安裝 runtime，並將其安裝在位於所有允許寫入路徑之外的前綴下：

```bash theme={null}
npm install -g @anthropic-ai/sandbox-runtime
```

設定檔就位後，從您的專案目錄透過 runtime 啟動 Claude Code：

```bash theme={null}
srt claude
```

Claude Code 在沙箱內啟動，具有您設定的檔案系統和網路邊界。相同的 `srt` 命令適用於沙箱化獨立 MCP 伺服器或其他輔助程序。

### Runtime 自行阻止的內容

runtime 在沒有您任何設定的情況下阻止最高風險的寫入：

* `denyWrite` 優先於 `allowWrite`。
* 在專案根目錄，runtime 拒絕 `.git/hooks`，除非您設定 `filesystem.allowGitConfig: true` 否則拒絕 `.git/config`，並拒絕 `.mcp.json`、`.claude/commands`、`.claude/agents` 和 shell 啟動檔案。
* 在 macOS 上，這些拒絕在寫入發生時被檢查，因此它們也涵蓋巢狀檔案和在工作階段期間建立的儲存庫。
* 在 Linux 和 WSL2 上，runtime 在啟動時建立拒絕清單一次。它可靠地涵蓋專案根目錄，對當時存在的巢狀副本進行盡力而為的淺層掃描，並不涵蓋工作階段稍後建立的任何內容，例如 `git init`、`git clone` 或腳手架。README 的 `mandatoryDenySearchDepth` 部分描述了掃描的確切語義。
* 如果 `~/.srt-settings.json` 不存在且您沒有傳遞 `--settings`，runtime 仍然啟動。它阻止網路存取並將寫入限制在內建 runtime 路徑，例如 `/tmp/claude`、`~/.npm/_logs` 和 `~/.claude/debug`。不要將乾淨啟動視為您的設定已載入的證明。
* 如果設定檔存在但為空、無法讀取或無效，runtime 拒絕啟動，無論是 `~/.srt-settings.json` 還是您使用 `--settings` 傳遞的檔案。如果 `--settings` 檔案不存在，它也拒絕啟動。

您的寫入授予仍然包括 Claude Code 載入設定的其他路徑，因此使用 `denyWrite` 拒絕這些路徑。可以寫入它們的沙箱化工作階段可以持久化 hook、權限規則或 MCP 伺服器，這些在您下次啟動 Claude Code 時以未沙箱化的方式執行。

### 無人值守執行後

檢查您保持可寫入的路徑。在 Linux 和 WSL2 上，也檢查工作階段建立的任何內容。

## Dev containers

Dev container 在 VS Code 或相容編輯器管理的 Docker 容器內執行 Claude Code，您的專案掛載在其中。您可以在您的儲存庫中使用 `.devcontainer/` 目錄定義您自己的。

claude-code 儲存庫發佈了一個 [example dev container](https://code.claude.com/docs/zh-TW/devcontainer.md)，其中包含預設拒絕 iptables 防火牆作為起點。將其複製到您的儲存庫中，並調整防火牆允許清單、基礎映像和固定的 Claude Code 版本以適應您的環境。因為防火牆阻止未批准的出站流量，像這樣的配置支援使用 `--dangerously-skip-permissions` 執行 Claude Code 進行無人值守工作。

## Custom container

您可以在任何 Docker 或 OCI 容器映像中執行 Claude Code，具有您自己的網路策略、掛載的卷和 seccomp 設定檔。這是具有現有容器基礎設施或 CI 執行器的組織最常見的路徑。

多個託管沙箱和遠端執行服務可以為您託管容器。與您操作的任何容器相同的檢查清單適用：審查掛載為可寫的內容、容器內可到達的認證和令牌，以及網路出站策略允許的內容。

您可以在容器內分層內建 Bash 沙箱以進行每個命令的限制。無特權容器需要 `enableWeakerNestedSandbox`，相關說明請參閱 [Bubblewrap 無法在容器內啟動](https://code.claude.com/docs/zh-TW/sandboxing.md#bubblewrap-fails-to-start-inside-a-container)。

## Virtual machine

專用虛擬機提供最強的分離，具有自己的核心，在雲或 microVM 部署中，具有自己的虛擬化硬體。選項包括雲實例、本地虛擬機管理程式和 microVM（如 Firecracker）。當您評估不受信任的程式碼、當您的安全策略要求代理和主機之間的核心級分離，或當沒有主機級方法滿足您的合規要求時，使用此方法。

[Docker Sandboxes](https://docs.docker.com/ai/sandboxes/) 提供了一個具有自己的 Docker daemon 和工作區同步的 microVM，可以在任何安裝了 Docker Sandboxes 的主機上執行 Claude Code。它是來自 Docker 的免費獨立產品，不需要 Docker Desktop。

## 雲端會話

[雲端會話](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)在隔離的、由 Anthropic 管理的虛擬機中執行。網路代理強制執行預設允許清單，單獨的代理在沙箱外保持您的 GitHub 令牌，同時在其內部為儲存庫存取發出範圍限定的認證。您的組織路由到[自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)的會話在您配置的基礎設施上執行，其中隔離、出站控制和 git 認證是您部署的責任。

當您想要完整的虛擬機隔離而無需自己配置基礎設施，或當您從沒有本地開發環境的設備委派任務時，使用此方法。它需要 Claude 訂閱。除非您從 CLI 啟動，否則您還需要連接的 GitHub 帳戶，以便沙箱可以複製您的儲存庫。當您使用 `--cloud` 從 CLI 啟動時，Claude Code 可以[捆綁並上傳您的本地儲存庫](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#send-local-repositories-without-github)。有關計劃可用性和 GitHub 身份驗證選項，請參閱[在雲端使用 Claude Code](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)。

## 在整個組織中強制執行隔離

個別開發人員可以選擇本頁面上的任何 sandboxing 方法。組織可以強制執行的內容以及使用哪些工具取決於方法：

* **Built-in Bash sandbox**：唯一 Claude Code 本身強制執行的方法。通過 [managed settings](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms) 傳遞 `sandbox` 設定鍵，可以是由您的 MDM 管理的檔案，也可以通過 Claude.ai 上的 [server-managed settings](https://code.claude.com/docs/zh-TW/server-managed-settings.md)。有關要部署的鍵以及如何防止開發人員擴大策略，請參閱 [Enforce sandboxing with managed settings](https://code.claude.com/docs/zh-TW/sandboxing.md#enforce-sandboxing-with-managed-settings)。
* **Dev containers**：將 [example dev container](https://code.claude.com/docs/zh-TW/devcontainer.md) 提交到您的儲存庫以標準化整個團隊的環境。這是一個約定而不是強制邊界，因為 Claude Code 不需要容器。如果開發人員不應該能夠在其外部執行 Claude Code，請使用您組織的設備管理或軟體允許清單工具強制執行。
* **Custom containers and VMs**：通過批准的映像分發 Claude Code，並使用您組織的設備管理或軟體允許清單工具防止在其外部安裝。

## 另請參閱

這些頁面涵蓋上述方法的配置和策略詳細資訊。

* [Sandboxing](https://code.claude.com/docs/zh-TW/sandboxing.md)：配置內建沙箱化 Bash 工具
* [Dev container](https://code.claude.com/docs/zh-TW/devcontainer.md)：預配置的 Docker 開發容器
* [安全性](https://code.claude.com/docs/zh-TW/security.md)：完整的 Claude Code 安全模型
* [安全部署](https://code.claude.com/docs/zh-TW/agent-sdk/secure-deployment.md)：Agent SDK 應用程式的隔離指南
* [設定](https://code.claude.com/docs/zh-TW/settings-reference.md#sandbox-settings)：所有沙箱設定鍵，包括受管設定傳遞

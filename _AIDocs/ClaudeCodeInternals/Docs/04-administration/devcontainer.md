<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/devcontainer | lastmod: 2026-10-28 | section: Administration / Deployment -->
> 來源：https://code.claude.com/docs/zh-TW/devcontainer（官方 zh-TW，lastmod 2026-10-28）｜分類：Administration › Deployment｜EN 摘要：Run Claude Code inside a dev container for consistent, isolated environments across your team.

# 開發容器

> 在開發容器中執行 Claude Code，為您的團隊提供一致、隔離的環境。

[開發容器](https://containers.dev/)（或 dev container）讓您定義一個相同的隔離環境，您的團隊中的每位工程師都可以執行。安裝 Claude Code 在該容器中後，Claude 執行的命令會在容器內執行，而不是在主機上執行，同時對您的專案檔案的編輯會在您工作時出現在本地儲存庫中。

本頁涵蓋[在開發容器中安裝 Claude Code](#add-claude-code-to-your-dev-container)，然後是一組獨立的配置主題：在重新構建時保持身份驗證、強制執行組織政策、限制網路出站流量，以及無需權限提示即可執行。請閱讀與您的設定相符的主題。

> [!WARNING]
>
> 雖然開發容器提供了大量保護，但沒有任何系統完全免疫所有攻擊。
> 當使用 `--dangerously-skip-permissions` 執行時，開發容器不會阻止惡意專案從容器內可存取的任何內容（包括儲存在 [`~/.claude`](https://code.claude.com/docs/zh-TW/claude-directory) 中的 Claude Code 認證）進行資料外洩。
> 僅在使用受信任的儲存庫進行開發時使用開發容器，並監控 Claude 的活動。
> 避免將主機祕密（例如 `~/.ssh` 或雲端認證檔案）掛載到容器中；優先使用儲存庫範圍或短期有效的令牌。

> [accordion] 開發容器如何與您的編輯器配合使用
>
> ![顯示主機上的編輯器連接到 Docker 開發容器的圖表。Claude Code、終端和構建工具在容器內執行。主機儲存庫被綁定掛載到容器中作為工作區。](https://mintcdn.com/claude-code/YvJyjZfd9yMihr0i/images/devcontainer-architecture.svg?fit=max\&auto=format\&n=YvJyjZfd9yMihr0i\&q=85\&s=9017b1d16a446c6cc37ba562f35b9aae)
>
> 開發容器作為 Docker 容器執行，可以在您的機器上或雲端主機（例如 GitHub Codespaces）上執行。支援 Dev Containers 規範的編輯器（例如 VS Code、GitHub Codespaces、JetBrains IDE 或 Cursor）連接到該容器：您在編輯器中照常瀏覽和編輯檔案，但整合終端、語言伺服器和構建工具都在容器內執行，而不是在您的主機上。不支援開發容器的編輯器（例如純 Vim）不是此工作流程的一部分。
>
> Claude Code 在容器內執行，因此它看到與您的專案工具鏈其餘部分相同的檔案、依賴項和工具。在 VS Code 中，您可以使用 [Claude Code 擴充功能面板](https://code.claude.com/docs/zh-TW/vs-code.md) 或在整合終端中執行 `claude`；兩者都在容器內執行並共享相同的 `~/.claude` 配置。

## 在開發容器中新增 Claude Code

Claude Code 透過 [Claude Code Dev Container Feature](https://github.com/anthropics/devcontainer-features/tree/main/src/claude-code) 安裝到任何開發容器中。

這些設定適用於任何支援 Dev Containers 規範的工具，例如 VS Code、GitHub Codespaces 或 JetBrains IDE。下面的步驟以 VS Code 為例。

當您在 VS Code 或 Codespaces 中開啟容器時，該功能還會新增 Claude Code VS Code 擴充功能；其他編輯器會忽略該部分。

> [!TIP]
>
> 初次接觸開發容器？[VS Code Dev Containers 教程](https://code.visualstudio.com/docs/devcontainers/tutorial)會逐步介紹安裝 Docker、擴充功能和開啟您的第一個容器。如需更完整的強化示例（包含防火牆和持久磁碟區），請參閱[試用參考容器](#try-the-reference-container)。

**1. 建立或更新 devcontainer.json**

將以下內容儲存為儲存庫中的 `.devcontainer/devcontainer.json`，或將 `features` 區塊新增到您現有的檔案中。

末尾的版本標籤（例如 `:1.0`）會固定功能的安裝指令碼，而不是 Claude Code 版本。該功能會安裝最新的 Claude Code，Claude Code 預設會在容器內自動更新。

若要固定 CLI 版本或停用自動更新，請參閱[強制執行組織政策](#enforce-organization-policy)。

```json .devcontainer/devcontainer.json theme={null}
{
  "image": "mcr.microsoft.com/devcontainers/base:ubuntu",
  "features": {
    "ghcr.io/anthropics/devcontainer-features/claude-code:1.0": {}
  }
}
```

將 `image` 行替換為您的專案的基礎映像，或如果您現有的檔案使用 Dockerfile，則將其移除。

Claude Code 功能會在基礎映像未提供 Node.js 時自行安裝。如果該安裝失敗且構建停止並顯示 `Failed to install Node.js and npm`，請將 `"ghcr.io/devcontainers/features/node:1": {}` 新增到上述 `features` 區塊中 Claude Code 功能的上方，然後重新構建。

**2. 重新構建容器**

在 Mac 上使用 `Cmd+Shift+P` 或在 Windows 和 Linux 上使用 `Ctrl+Shift+P` 開啟 VS Code 命令面板，並執行 **Dev Containers: Rebuild Container**。

對於其他工具，請遵循該工具的重新構建操作：請參閱 [GitHub Codespaces 中的重新構建](https://docs.github.com/en/codespaces/developing-in-a-codespace/rebuilding-the-container-in-a-codespace)、[Dev Containers CLI](https://github.com/devcontainers/cli) 或您的 IDE 的開發容器文件。

**3. 登入 Claude Code**

在重新構建的容器中開啟終端並執行 `claude`，然後按照身份驗證提示進行操作。

您在身份驗證提示中看到的內容取決於您的提供者：

* **Anthropic**：透過瀏覽器使用您的 Claude 或 Anthropic Console 帳戶登入
* **[Amazon Bedrock、Google Cloud 的 Agent Platform 或 Microsoft Foundry](https://code.claude.com/docs/zh-TW/third-party-integrations.md)**：Claude Code 使用您的雲端提供者認證，無需瀏覽器提示

對於雲端提供者，透過 `containerEnv`、Codespaces 祕密或您的雲端的工作負載身份（而不是從主機掛載認證檔案）將認證傳遞到容器中。請參閱 [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md)、[Google Cloud 的 Agent Platform](https://code.claude.com/docs/zh-TW/google-vertex-ai.md) 或 [Microsoft Foundry](https://code.claude.com/docs/zh-TW/microsoft-foundry.md) 以了解 Claude Code 讀取的認證鏈。

請參閱[選擇您的 API 提供者](https://code.claude.com/docs/zh-TW/admin-setup.md#choose-your-api-provider)以決定哪條路徑適合您的組織。

> [!NOTE]
>
> 對於 Anthropic 登入：如果沒有開啟瀏覽器，或瀏覽器完成登入後顯示 `localhost` 連線錯誤，請使用終端機貼上提示上方顯示的登入 URL。將其複製到瀏覽器中並在那裡登入，然後將瀏覽器顯示的代碼貼上到該提示處。如果貼上沒有任何作用，請參閱[在 WSL2、SSH 或容器中 OAuth 登入失敗](https://code.claude.com/docs/zh-TW/troubleshoot-install.md#oauth-login-fails-in-wsl2-ssh-or-containers)。

## 在重新構建時保持身份驗證和設定

預設情況下，容器的家目錄在重新構建時會被丟棄，因此工程師必須每次都重新登入。Claude Code 將其身分驗證 token、使用者設定和工作階段歷史記錄儲存在 [`~/.claude`](https://code.claude.com/docs/zh-TW/claude-directory) 目錄下。它將您的帳戶詳細資訊、個人 MCP 伺服器和每個專案的信任設定儲存在該目錄外的一個單獨檔案中：[`~/.claude.json`](https://code.claude.com/docs/zh-TW/settings-reference#global-config-settings)。

若要保留該目錄和該檔案，請在 `~/.claude` 掛載一個命名磁碟區，並將 [`CLAUDE_CONFIG_DIR`](https://code.claude.com/docs/zh-TW/env-vars) 設定為相同路徑，以便 Claude Code 在磁碟區內寫入 `.claude.json`。以下範例為 `remoteUser` 為 `node` 的容器掛載磁碟區並設定 `CLAUDE_CONFIG_DIR`：

```json devcontainer.json theme={null}
"mounts": [
  "source=claude-code-config,target=/home/node/.claude,type=volume"
],
"containerEnv": {
  "CLAUDE_CONFIG_DIR": "/home/node/.claude"
}
```

將 `/home/node` 替換為您的容器的 `remoteUser` 的主目錄。如果您已經設定了 `containerEnv`，例如在[強制執行組織政策](#enforce-organization-policy)中，請將 `CLAUDE_CONFIG_DIR` 新增到該物件，而不是新增第二個物件。

> [!NOTE]
>
> 如果儘管已掛載磁碟區，Claude Code 在每次重新構建後仍重複執行首次啟動設定，請檢查 `devcontainer.json` 中的 `containerEnv` 是否將 `CLAUDE_CONFIG_DIR` 設定為磁碟區的掛載路徑。若未設定 `CLAUDE_CONFIG_DIR`，`~/.claude.json` 會留在家目錄中，並在重新構建時連同您已完成設定的記錄一起被丟棄。

若要隔離每個專案的狀態，而不是在所有儲存庫中共享一個磁碟區，請在來源名稱中包含 `${devcontainerId}` 變數。[參考配置](https://github.com/anthropics/claude-code/blob/main/.devcontainer/devcontainer.json)為此目的使用 `source=claude-code-config-${devcontainerId}`。

在 GitHub Codespaces 中，`~/.claude` 在停止和啟動 codespace 時會保持，但在重新構建容器時仍會被清除，因此上面的配置也適用於此。

若要在 codespace 之間進行身份驗證，請將 `ANTHROPIC_API_KEY` 或來自 [`claude setup-token`](https://code.claude.com/docs/zh-TW/authentication#generate-a-long-lived-token) 的 `CLAUDE_CODE_OAUTH_TOKEN` 儲存為 [Codespaces 祕密](https://docs.github.com/en/codespaces/managing-your-codespaces/managing-your-account-specific-secrets-for-github-codespaces)。Codespaces 會自動將祕密作為環境變數提供給容器內。

## 強制執行組織政策

開發容器是應用組織政策的便利場所，因為相同的映像和配置在每位工程師的機器上執行。

Claude Code 在 Linux 上讀取 `/etc/claude-code/managed-settings.json` 並在[設定層級結構](https://code.claude.com/docs/zh-TW/settings.md#settings-precedence)中以最高優先級應用它，因此那裡的值會覆蓋工程師在 `~/.claude` 或專案的 `.claude/` 目錄中設定的任何內容。從您的 Dockerfile 複製檔案到位置：

```dockerfile Dockerfile theme={null}
RUN mkdir -p /etc/claude-code
COPY managed-settings.json /etc/claude-code/managed-settings.json
```

因為 Dockerfile 存在於儲存庫中，任何具有寫入存取權限的人都可以更改或移除此步驟。對於工程師無法透過編輯儲存庫檔案來繞過的政策，請透過[伺服器管理的設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)或您的 MDM 提供託管設定。請參閱[託管設定檔案](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)以了解可用的鍵和其他傳遞路徑。

若要設定適用於容器中每個 Claude Code 工作階段的[環境變數](https://code.claude.com/docs/zh-TW/env-vars.md)，請將它們新增到您的 `devcontainer.json` 中的 `containerEnv`。以下示例選擇退出遙測和錯誤報告，並防止 Claude Code 在安裝後自動更新：

```json devcontainer.json theme={null}
"containerEnv": {
  "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
  "DISABLE_AUTOUPDATER": "1"
}
```

`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` 也會停用[遠端控制](https://code.claude.com/docs/zh-TW/remote-control.md#requirements)和其他[需要功能旗標擷取的功能](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)所依賴的功能旗標評估，因此容器中的工作階段無法使用它們。

Dev Container Feature 始終安裝最新的 Claude Code 版本。若要為可重現的構建固定特定的 Claude Code 版本，請從您的 Dockerfile 使用 `npm install -g @anthropic-ai/claude-code@X.Y.Z` 安裝它，而不是使用該功能，並在 `containerEnv` 中設定 `DISABLE_AUTOUPDATER` 為 `1`。

如需完整的政策控制清單（包括權限規則、工具限制和 MCP 伺服器允許清單），請參閱[為您的組織設定 Claude Code](https://code.claude.com/docs/zh-TW/admin-setup.md)。

若要在容器內提供 [MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md)，請在儲存庫根目錄的 `.mcp.json` 檔案中以[專案範圍](https://code.claude.com/docs/zh-TW/mcp.md#mcp-installation-scopes)定義它們，以便它們與您的開發容器配置一起簽入。在您的 Dockerfile 中安裝本地 stdio 伺服器所依賴的任何二進位檔案，並將遠端伺服器網域新增到您的網路允許清單。

## 限制網路出站流量

您可以將容器的出站流量限制為僅 Claude Code 需要的網域。請參閱[網路存取要求](https://code.claude.com/docs/zh-TW/network-config.md#network-access-requirements)以了解推理和身份驗證網域，以及[遙測服務](https://code.claude.com/docs/zh-TW/data-usage.md#telemetry-services)以了解可選的遙測和錯誤報告連接以及如何停用它們。

參考容器包含一個 [`init-firewall.sh`](https://github.com/anthropics/claude-code/blob/main/.devcontainer/init-firewall.sh) 指令碼，該指令碼會限制出站流量僅限於指令碼允許的目的地。在容器內執行防火牆需要額外的權限，因此參考透過 `runArgs` 新增 `NET_ADMIN` 和 `NET_RAW` 功能。防火牆指令碼和這些功能對 Claude Code 本身不是必需的：您可以將它們省略並改為依賴您自己的網路控制。

## 無需權限提示即可執行

因為容器以非 root 使用者身份執行 Claude Code 並將命令執行限制在容器內，您可以傳遞 `--dangerously-skip-permissions` 以進行無人值守操作。當以 root 身份啟動時，CLI 會拒絕此標誌，因此請確認 `remoteUser` 設定為非 root 帳戶。

跳過權限提示會移除您在工具呼叫執行前進行審查的機會。Claude 仍然可以修改綁定掛載工作區中的任何檔案（該檔案直接出現在您的主機上），並到達容器的網路政策允許的任何內容。將此標誌與上面的[網路出站流量限制](#restrict-network-egress)配對，以限制繞過的工作階段可以到達的內容。

如果您想要更少的提示而不停用安全檢查，請考慮改為[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)，該模式具有在執行前審查操作的分類器。若要完全防止工程師使用 `--dangerously-skip-permissions`，請在[託管設定](https://code.claude.com/docs/zh-TW/settings-reference.md#permission-settings)中將 `permissions.disableBypassPermissionsMode` 設定為 `"disable"`。

## 試用參考容器

[`anthropics/claude-code`](https://github.com/anthropics/claude-code/tree/main/.devcontainer) 儲存庫包含一個示例開發容器，該容器結合了 CLI、出站防火牆、持久磁碟區和基於 Zsh 的 shell。它作為工作示例而不是維護的基礎映像提供；在將它們應用到您自己的配置之前，使用它來查看這些部分如何組合在一起。

**1. 安裝先決條件**

安裝 VS Code 和 [Dev Containers 擴充功能](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)。

**2. 複製參考**

複製 [Claude Code 儲存庫](https://github.com/anthropics/claude-code)並在 VS Code 中開啟它。

**3. 在容器中重新開啟**

出現提示時，點擊 **Reopen in Container**，或從命令面板執行 **Dev Containers: Reopen in Container**。

**4. 啟動 Claude Code**

容器完成構建後，使用 `` Ctrl+` `` 開啟終端並執行 `claude` 以登入並啟動您的第一個工作階段。

若要將此配置用於您自己的專案，請將 `.devcontainer/` 目錄複製到您的儲存庫中並根據您的工具鏈調整 Dockerfile，或返回[在開發容器中新增 Claude Code](#add-claude-code-to-your-dev-container) 以僅將功能新增到您已有的設定中。

參考配置由三個檔案組成。當您透過功能將 Claude Code 新增到您自己的開發容器時，這些都不是必需的，但它們展示了一種組合這些部分的方式。

| 檔案 | 目的 |
| - | - |
| [`devcontainer.json`](https://github.com/anthropics/claude-code/blob/main/.devcontainer/devcontainer.json) | 磁碟區掛載、`runArgs` 功能、VS Code 擴充功能和 `containerEnv` |
| [`Dockerfile`](https://github.com/anthropics/claude-code/blob/main/.devcontainer/Dockerfile) | 基礎映像、開發工具和 Claude Code 安裝 |
| [`init-firewall.sh`](https://github.com/anthropics/claude-code/blob/main/.devcontainer/init-firewall.sh) | 阻止除允許的網域外的所有出站網路流量 |

## 後續步驟

Claude Code 在您的開發容器中執行後，下面的頁面涵蓋組織推出的其餘部分：選擇身份驗證路徑、在儲存庫外提供託管政策、監控使用情況以及了解 Claude Code 儲存和傳送的內容。

* [為您的組織設定 Claude Code](https://code.claude.com/docs/zh-TW/admin-setup.md)：選擇身份驗證提供者、決定政策如何到達裝置以及規劃推出
* [伺服器管理的設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)：從 claude.ai 管理員控制台提供託管政策，以便工程師無法透過編輯儲存庫檔案來繞過它
* [監控使用情況和審計活動](https://code.claude.com/docs/zh-TW/monitoring-usage.md)：匯出 OpenTelemetry 指標並審查您的團隊正在執行的內容
* [網路存取要求](https://code.claude.com/docs/zh-TW/network-config.md#network-access-requirements)：代理和防火牆的完整網域允許清單
* [遙測服務和選擇退出](https://code.claude.com/docs/zh-TW/data-usage.md#telemetry-services)：Claude Code 預設傳送的內容以及停用它的環境變數
* [探索 `.claude` 目錄](https://code.claude.com/docs/zh-TW/claude-directory)：磁碟區掛載包含的內容，包括認證、設定和工作階段歷史記錄
* [沙箱環境](https://code.claude.com/docs/zh-TW/sandbox-environments.md)：比較開發容器與內建 Bash 沙箱、自訂容器和虛擬機器
* [安全模型](https://code.claude.com/docs/zh-TW/security.md)：Claude Code 的權限系統、沙箱和提示注入保護如何組合在一起
* [Permission modes](https://code.claude.com/docs/zh-TW/permission-modes.md)：從 Plan Mode 到 auto mode 到 bypass 的完整範圍，以及何時使用每種模式

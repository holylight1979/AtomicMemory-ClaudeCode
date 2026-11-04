<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/github-enterprise-server | lastmod: 2026-10-28 | section: Getting started / Code review and pull requests -->
> 來源：https://code.claude.com/docs/zh-TW/github-enterprise-server（官方 zh-TW，lastmod 2026-10-28）｜分類：Getting started › Code review and pull requests｜EN 摘要：Connect Claude Code to your self-hosted GitHub Enterprise Server instance for cloud sessions, code review, and plugin marketplaces.

# Claude Code 與 GitHub Enterprise Server

> 將 Claude Code 連接到您自託管的 GitHub Enterprise Server 實例，以進行雲端會話、代碼審查和插件市場。

> [!NOTE]
>
> GitHub Enterprise Server 支持適用於 Team 和 Enterprise 計劃。

GitHub Enterprise Server (GHES) 支持讓您的組織使用 Claude Code 與託管在自管理 GitHub 實例上的存儲庫，而不是 github.com。一旦 Owner 連接您的 GHES 實例，開發人員可以運行雲端會話和獲得自動化代碼審查，無需任何按存儲庫的配置。您實例上託管的插件市場也受支持；憑證要求因表面而異，如 [GHES 上的插件市場](#plugin-marketplaces-on-ghes) 中所述。

對於 github.com 上的存儲庫，請參閱 [在雲端使用 Claude Code](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md) 和 [代碼審查](https://code.claude.com/docs/zh-TW/code-review.md)。要在您自己的 CI 基礎設施中運行 Claude，請參閱 [GitHub Actions](https://code.claude.com/docs/zh-TW/github-actions.md)。

## GitHub Enterprise Server 支持的功能

下表顯示了 Claude Code 的哪些功能支持 GHES，以及與 github.com 行為的任何差異。

| 功能 | GHES 支持 | 備註 |
| :- | :- | :- |
| 雲端工作階段 | ✅ 支援 | 擁有者只需連接 GHES 執行個體一次；開發人員使用 `claude --cloud` 或 [claude.ai/code](https://claude.ai/code) |
| Code Review | ✅ 支持 | 與 github.com 相同的自動化 PR 審查 |
| Claude Security | ✅ 支持 | 在 Enterprise 計劃的公開測試版中提供，位於 [claude.ai/security](https://claude.ai/security) |
| Teleport sessions | ✅ 支持 | 使用 `--teleport` 在雲端和終端之間移動會話 |
| Plugin marketplaces | ✅ 支持 | 認證要求因介面而異。請參閱 [GHES 上的 Plugin marketplaces](#plugin-marketplaces-on-ghes) |
| Contribution metrics | ❌ 不支援 | 需要託管在 github.com 上的儲存庫。[分析儀表板](https://code.claude.com/docs/zh-TW/analytics.md)仍會顯示 GHES 儲存庫中工作的使用量指標 |
| GitHub Actions | ✅ 支持 | 需要手動工作流設置；`/install-github-app` 僅適用於 github.com |
| GitHub MCP server | ❌ 不支持 | GitHub MCP server 不適用於 GHES 實例 |

## 管理員設定

擁有者只需將您的 GHES 執行個體連接到 Claude Code 一次。您需要在 Claude 組織中擁有擁有者或主要擁有者角色，以及在 GHES 執行個體上建立 GitHub Apps 的權限。

引導式設定會產生 GitHub App 資訊清單，並將您重新導向到 GHES 執行個體以一鍵建立應用程式。如果您的環境阻止重新導向流程，可以使用[替代手動設定](#manual-setup)。

**1. 開啟 Git 提供者設定**

前往 [**組織設定 > Git 提供者**](https://claude.ai/admin-settings/source-control#github-enterprise) 並找到 GitHub Enterprise 部分。

**2. 開始引導式設定**

點擊**連接**，若已連接執行個體則點擊**新增執行個體**，然後選擇**自動設定**。輸入最多 20 個字元的連接顯示名稱和您的 GHES 主機名稱，例如 `github.example.com`。如果您的 GHES 執行個體使用自簽署或私人憑證授權單位，請將 CA 憑證貼到選用欄位中。

**3. 建立 GitHub App**

點擊**繼續到 GitHub Enterprise**。您的瀏覽器會重新導向到您的 GHES 執行個體，並顯示預先填入的應用程式資訊清單。檢閱設定並點擊**建立 GitHub App**。GHES 會將您重新導向回 Claude，應用程式憑證會自動儲存。

**4. 在您的儲存庫上安裝應用程式**

從 GHES 執行個體上的 GitHub App 頁面，在您希望 Claude 存取的儲存庫或組織上安裝應用程式。您可以先從子集開始，稍後再新增更多。

**5. 啟用 Code Review**

前往 [claude.ai/admin-settings/claude-code](https://claude.ai/admin-settings/claude-code) 並為您的 GHES 儲存庫啟用 [Code Review](https://code.claude.com/docs/zh-TW/code-review-setup.md)，使用與 github.com 相同的設定。

### GitHub App 權限

資訊清單使用下列權限和 webhook 事件設定 GitHub App，這些權限和事件共同涵蓋雲端工作階段、Code Review、Claude Security 和外掛市集：

| 權限 | 存取 | 用途 |
| :- | :- | :- |
| Contents | 讀取和寫入 | 複製儲存庫和推送分支 |
| Pull requests | 讀取和寫入 | 建立 PR 和發佈審查評論 |
| Issues | 讀取和寫入 | 回應問題提及 |
| Checks | 讀取和寫入 | 發佈 Code Review 檢查執行 |
| Actions | 讀取 | 讀取自動修復的 CI 狀態 |
| Commit statuses | 讀取 | 從報告提交狀態而非檢查執行的提供者讀取 CI 狀態 |
| Repository hooks | 讀取和寫入 | 在 [**組織設定 > Plugins & skills**](https://claude.ai/admin-settings/skills?tab=marketplaces) 中為市集開啟**自動同步**時，在外掛市集儲存庫上建立 webhook |
| Metadata | 讀取 | GitHub 要求所有應用程式必須具備 |
| Organization members | 讀取 | 符合 github.com 上的 Claude GitHub App，用於在連結安裝時檢查連接使用者的組織角色 |

應用程式訂閱 `pull_request`、`issue_comment`、`pull_request_review_comment`、`pull_request_review`、`check_run` 和 `status` 事件。

GitHub 只在建立應用程式時套用資訊清單，因此從較早版本資訊清單建立的應用程式會保留建立時的權限和事件。如果您的應用程式缺少上述任何權限或事件，請在 GHES 執行個體上的應用程式設定中新增它們。GitHub 隨後會要求每個安裝的擁有者核准新權限，安裝會保留其舊權限，直到他們核准為止。

### 手動設定

如果您的網路設定阻止引導式重新導向流程，請點擊**連接**或**新增執行個體**，然後選擇**手動新增**而不是**自動設定**。在 GHES 執行個體上使用[上述權限和事件](#github-app-permissions)建立 GitHub App，然後在表單中輸入連接詳細資訊：顯示名稱、GHES 主機名稱和選用連接埠，以及應用程式 ID、用戶端 ID、用戶端密碼、webhook 密碼和私密金鑰。表單也接受選用的自訂 CA 憑證和讀取複本主機名稱。

Claude 在您儲存連接時產生應用程式的 webhook URL。在您點擊**新增設定**後，開啟連接的**更多選項**功能表，選擇**複製 webhook URL**，並將 URL 貼到 GHES 執行個體上應用程式的 webhook 設定中。使用您在表單中輸入的相同 webhook 密碼。

### 網路需求

對於 Anthropic 代管的工作階段，您的 GHES 執行個體必須可從 Anthropic 基礎結構存取，以便 Claude 可以複製儲存庫和發佈審查評論。如果您的 GHES 執行個體位於防火牆後面，請將 Anthropic 的[出站 IP 位址](https://platform.claude.com/docs/en/api/ip-addresses#outbound-ip-addresses)加入允許清單。[自我代管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#configure-git)中的工作階段會從您的網路內部複製，除非執行者選擇加入 [Anthropic git 代理伺服器](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#use-the-anthropic-git-proxy)，該代理伺服器從 Anthropic 端擷取並需要相同的可達性。

代管的前置工作階段流程（例如儲存庫選擇器）在工作階段開始前在 Anthropic 端執行。即使工作階段在自我代管環境中執行，它們也需要您的 GHES 執行個體可從 Anthropic 基礎結構存取。[SCM 連接器](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference.md#scm-connector-flags)無法使用，因此這些流程無法存取僅在內部可路由的 GHES 主機。

## 開發者工作流程

Claude Code 會自動從您工作目錄中的 git remote 偵測您的 GHES 主機名稱。

從您的 GHES 執行個體複製儲存庫，方式與平常相同，將 `github.example.com` 和儲存庫路徑替換為您的 GHES 主機名稱和儲存庫：

```bash theme={null}
git clone git@github.example.com:platform/api-service.git
cd api-service
```

然後啟動雲端工作階段。Claude 會從您的 git remote 偵測 GHES 主機，並透過您組織設定的執行個體路由工作階段：

```bash theme={null}
claude --cloud "Add retry logic to the payment webhook handler"
```

工作階段會從 GHES 複製您的儲存庫，並將變更推送回分支。在 [claude.ai/code](https://claude.ai/code) 監控進度。請參閱 [在雲端使用 Claude Code](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md) 以了解完整的雲端工作階段工作流程，包括差異檢閱、自動修復和雲端排程任務。

### 將 Teleport 工作階段傳送到您的終端機

使用 `claude --teleport` 將雲端工作階段拉入您的本機終端機。Teleport 會驗證您是否在相同 GHES 儲存庫的簽出中，然後再擷取分支並載入工作階段歷史記錄。請參閱 [teleport requirements](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#teleport-requirements) 以了解詳細資訊。

## GHES 上的插件市場

在您的 GHES 實例上託管插件市場，以在您的組織中分發內部工具。市場結構與 github.com 託管的市場相同，但安裝方式取決於您在何處新增市場，且認證在不同介面上有所不同：

| 介面 | 安裝方式 | 每個使用者需要什麼 |
| :- | :- | :- |
| Claude Code CLI 和桌面應用 | Claude Code 使用機器現有的 git 認證複製市場存儲庫 | 從其機器對您的 GHES 主機的 Git 存取權 |
| 託管設定 (`extraKnownMarketplaces`) | Claude Code 註冊該項目並使用機器現有的 git 認證複製存儲庫 | 從其機器對您的 GHES 主機的 Git 存取權 |
| claude.ai 組織插件設定 | 擁有者選擇 GHES 實例作為來源；Anthropic 的後端使用來自 [管理員設定](#admin-setup) 的 GitHub App 擷取並同步存儲庫 | 新增後每個使用者無需任何操作。新增它的擁有者需要連接自己的 GitHub Enterprise 帳戶作為存取檢查，且 GitHub App 必須安裝在市場存儲庫上 |
| claude.ai 使用者設定 | Anthropic 的後端使用提交使用者的 GitHub Enterprise 連接擷取存儲庫 | 連接到 Claude 的自己的 GitHub Enterprise 帳戶 |
| Cloud sessions | Cloud sessions 在工作階段沙箱內複製市場。沙箱只有在工作階段的存儲庫位於同一實例上時，才能到達您的 GHES 實例，且其 git 認證的範圍限於工作階段的存儲庫 | 對於 GHES 託管的市場不可靠：與工作階段存儲庫不同的主機無法到達，即使是同一實例的安裝也可能失敗。請改用 CLI、託管設定或 claude.ai |

> [!WARNING]
>
> 當從使用者設定新增市場時，claude.ai 上的 GitHub Enterprise 連接是按使用者的。[管理員設定](#admin-setup) 將您的 GHES 實例連接到您的組織，但它不連接個別使用者帳戶：每個從自己的設定新增 GHES 市場的使用者必須先連接自己的 GitHub Enterprise 帳戶，且一個使用者的連接（包括擁有者的）不涵蓋任何其他人。由擁有者在組織插件設定中新增的市場不會對使用者施加此要求，因為持續的擷取使用組織的 GitHub App。新增市場的擁有者仍然需要在新增時連接自己的 GitHub Enterprise 帳戶。

### 添加 GHES 市場

`owner/repo` 簡寫始終解析為 github.com。對於 GHES 託管的市場，請使用完整的 git URL，將 `github.example.com` 和存儲庫路徑替換為您自己的。建議使用 HTTPS URL：

```bash theme={null}
/plugin marketplace add https://github.example.com/platform/claude-plugins.git
```

如果機器已經信任您的 GHES 主機，SSH URL 也可以工作：

```bash theme={null}
/plugin marketplace add git@github.example.com:platform/claude-plugins.git
```

Claude Code 以非互動方式執行 git，並拒絕連接到不在機器 `known_hosts` 檔案中的主機的 SSH 連接。帶有 git 認證幫助程式的 HTTPS URL 可以避免 `known_hosts` 要求。

有關構建市場的完整指南，請參閱 [建立和分發插件市場](https://code.claude.com/docs/zh-TW/plugins/create-marketplace.md)。

### 使用託管設定預先註冊 GHES 市場

`extraKnownMarketplaces` 設定預先註冊市場，以便開發人員無需手動設定即可獲得它。它可以從 [任何設定檔案](https://code.claude.com/docs/zh-TW/settings-reference.md#extraknownmarketplaces) 工作，包括存儲庫的 `.claude/settings.json`；託管設定可以組織範圍內傳遞它：

```json theme={null}
{
  "extraKnownMarketplaces": {
    "internal-tools": {
      "source": {
        "source": "git",
        "url": "https://github.example.com/platform/claude-plugins.git"
      }
    }
  }
}
```

Claude Code 在本地安裝這些市場：它註冊每個項目並使用機器現有的 git 認證複製存儲庫。此路徑不經過 claude.ai，因此不需要按使用者的 GitHub Enterprise 連接。為了成功推出：

* **使用完整的 git URL。** `owner/repo` 簡寫始終解析為 github.com，無法參考 GHES 主機。
* **偏好 HTTPS URL。** SSH 複製在不已信任您的 GHES 主機金鑰的機器上失敗。帶有您組織標準 git 認證幫助程式的 HTTPS URL 可在任何配置了認證的機器上工作。
* **確認每台機器都可以從您的 GHES 主機複製。** 如果機器缺少認證，市場已註冊但永遠不會安裝，其插件報告為未找到而不是提示輸入認證。
* **確認設定到達每台機器。** 託管設定檔案只對部署到的機器生效，例如透過您的裝置管理系統。有關檔案位置，請參閱 [Deploy managed settings](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)。

### 在託管設定中將 GHES 市場列入白名單

如果您的組織使用 [託管設定](https://code.claude.com/docs/zh-TW/settings.md) 來限制開發人員可以添加的市場，請使用 `hostPattern` 源類型來允許來自您的 GHES 實例的所有市場，而無需列舉每個存儲庫。有關每個平台上的檔案位置，請參閱 [Delivery mechanisms](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)。將 JSON 新增到您的 `managed-settings.json` 檔案或等效的 MDM 政策：

```json theme={null}
{
  "strictKnownMarketplaces": [
    {
      "source": "hostPattern",
      "hostPattern": "^github\\.example\\.com$"
    }
  ]
}
```

有關完整的架構，請參閱 [strictKnownMarketplaces](https://code.claude.com/docs/zh-TW/settings-reference.md#strictknownmarketplaces) 和 [extraKnownMarketplaces](https://code.claude.com/docs/zh-TW/settings-reference.md#extraknownmarketplaces) 設定參考。

## 限制

一些功能在 GHES 上的行為與 github.com 上不同。[功能表](#what-works-with-github-enterprise-server) 總結了支持；本部分涵蓋了解決方案。

* **`/install-github-app` 命令**：改為遵循 claude.ai 上的 [管理員設置](#admin-setup) 流程。如果您還想在 GHES 上使用 GitHub Actions 工作流，請手動調整 [示例工作流](https://github.com/anthropics/claude-code-action/blob/main/examples/claude.yml)。
* **GitHub MCP server**：改為使用為您的 GHES 主機配置的 `gh` CLI。運行 `gh auth login --hostname github.example.com` 進行身份驗證，然後 Claude 可以在會話中使用 `gh` 命令。

## 故障排除

### 雲端會話無法克隆存儲庫

如果 `claude --cloud` 因克隆錯誤而失敗，請驗證 Owner 已完成您的 GHES 實例的設置，並且 GitHub App 已安裝在您正在使用的存儲庫上。與連接該實例的 Owner 確認在 Claude 設置中註冊的主機名與您的 git 遠端中的主機名匹配。

如果工作階段停止並顯示「Authentication failed while accessing the repository」，您可能尚未連接自己的 GitHub Enterprise 帳戶。請從 [claude.ai/code](https://claude.ai/code) 上的儲存庫選擇器連接帳戶，然後啟動新的工作階段。

### 市場添加因策略錯誤而失敗

如果 `/plugin marketplace add` 因您的 GHES URL 而被阻止，您的組織已限制市場源。要求您的管理員在 [託管設置](#allowlist-ghes-marketplaces-in-managed-settings) 中為您的 GHES 主機名添加 `hostPattern` 條目。

### claude.ai 上的市場添加因 GitHub 存取錯誤而失敗

如果從您的使用者設置添加 GHES 市場失敗並出現通用錯誤（例如「無法添加市場」），請先檢查您的 GitHub Enterprise 連接。這是當您自己的 GitHub Enterprise 帳戶未連接到 Claude 時出現的情況，即使您的組織的 GHES 實例已配置且其他使用者已連接。該對話框不會指向 GitHub Enterprise 連接流程，而「瀏覽」標籤上的「連接到 GitHub」選項會登入 github.com，這不會授予對 GHES 存儲庫的存取權限。

請在下列其中一處連接您的 GitHub Enterprise 帳戶，然後再次新增市集：

* **儲存庫選擇器**：在 [claude.ai/code](https://claude.ai/code) 上，儲存庫選擇器會為每個已設定的 GHES 實例提供連接選項。
* **Git 提供者頁面**：如果您是 Owner，請前往 [**Organization settings > Git providers**](https://claude.ai/admin-settings/source-control) 的 GitHub 區段並點擊 **Connect**，或在已連接帳戶後點擊 **Add organization**。在 **GitHub instance** 下選擇 GHES 主機名，然後點擊 **Connect**。

或者，要求 Owner 在組織外掛設定中新增市集，這樣可以消除每個使用者的連接要求。

在其他 claude.ai 表面上，GHES 市場上的「找不到存儲庫。如果是私有的，需要 GitHub 存取」錯誤通常表示相同的缺失連接。通過上述路徑之一連接您的 GitHub Enterprise 帳戶，然後重試。

### GHES 實例無法訪問

如果審查或 Anthropic 託管的雲端會話超時，您的 GHES 實例可能無法從 Anthropic 基礎設施訪問。確認您的防火牆允許來自 Anthropic 的[出站 IP 位址](https://platform.claude.com/docs/en/api/ip-addresses#outbound-ip-addresses)的入站連接。[自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)中的會話從您的網路內部訪問 GHES，因此當其中一個無法克隆時，請改為檢查執行器自身的網路路徑。對於存儲庫選擇器和其他託管的預會話流程，請參閱[網路要求](#network-requirements)。

### 連線測試通過，但第二項測試失敗

第二項測試會以 Anthropic 託管的雲端工作階段所使用的方式連線到您的 GHES 實例。請找到您看到的訊息，以判斷應檢查防火牆還是重試：

* **`Connection test passed, but a second test failed.`**：如果您的實例位於防火牆之後，請允許 Anthropic 的所有[輸出 IP 位址](https://platform.claude.com/docs/en/api/ip-addresses#outbound-ip-addresses)，因為即使您的防火牆封鎖了其中部分位址，連線測試仍可能通過。您也可以在幾分鐘後重試。
* **`Connection test passed, but a second test could not run.`**：請在幾分鐘後重試。

若要再次測試，請在 [**Organization settings > Git providers**](https://claude.ai/admin-settings/source-control#github-enterprise) 中開啟該連線的 **More options** 選單，然後選擇 **Test connection**。

### 會話啟動失敗，出現 `Unable to get organization UUID`

Claude Code 無法從您的認證中讀取 claude.ai 組織。使用 `/login` 以您的 Team 或 Enterprise 組織中的帳戶登入，因為 GitHub Enterprise Server 支援僅限於這些方案。請參閱[無法取得組織 UUID](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#unable-to-get-organization-uuid)以了解原因和此狀態產生的其他訊息。

## 相關資源

這些頁面更深入地涵蓋了本指南中引用的功能：

* [在雲端使用 Claude Code](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)：在雲基礎設施上運行 Claude Code 會話
* [Code Review](https://code.claude.com/docs/zh-TW/code-review.md)：自動化 PR 審查
* [Plugin marketplaces](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md)：構建和分發插件目錄
* [Analytics](https://code.claude.com/docs/zh-TW/analytics.md)：追蹤整個組織的 Claude Code 使用情況
* [Managed settings](https://code.claude.com/docs/zh-TW/settings.md)：組織範圍的策略配置
* [Network configuration](https://code.claude.com/docs/zh-TW/network-config.md)：防火牆和 IP 白名單要求

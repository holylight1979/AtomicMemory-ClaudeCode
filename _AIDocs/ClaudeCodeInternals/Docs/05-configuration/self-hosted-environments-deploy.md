<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy | lastmod: 2026-11-03 | section: Configuration / Environments -->
> 來源：https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy（官方 zh-TW，lastmod 2026-11-03）｜分類：Configuration › Environments｜EN 摘要：Run self-hosted runners in production: security hardening, network egress control, git credentials, Kubernetes and Compose recipes, and troubleshooting.

# 將自託管環境部署到生產環境

> 在生產環境中執行自託管執行器：安全強化、網路出站流量控制、Git 認證、Kubernetes 和 Compose 配方，以及故障排除。

> [!NOTE]
>
> 自託管環境在 Team 和 Enterprise 方案上處於公開測試版；[可用性和限制](https://code.claude.com/docs/zh-TW/self-hosted-environments#availability-and-limitations)涵蓋啟用路徑。本頁面涵蓋在生產環境中執行執行器群；請參閱[快速入門](https://code.claude.com/docs/zh-TW/self-hosted-environments-quickstart.md)以了解您的第一個執行器和工作階段。

[自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)在您部署在網路內的執行器上執行 Claude Code [雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)，在生產環境中，這些工作階段代表所有可以向環境分派工作階段的人執行模型導向的程式碼。本頁面適用於將正常運作的環境帶入生產環境的操作員。它按部署順序進行：在連接真實系統之前要鎖定什麼、執行器群需要的出站流量、工作階段如何向您的 Git 主機進行身份驗證、部署配方本身，以及當工作階段出現故障時要檢查什麼。

## 強化您的部署

自託管執行器代表所有可以向其環境分派工作階段的人在您的基礎設施上執行任意的、模型導向的程式碼。這是您 Anthropic 組織的任何成員，以及任何可以在所有者路由到環境的範圍內啟動 [Claude Tag](https://claude.com/docs/claude-tag/overview) 頻道工作階段的人。在將環境連接到生產系統之前，請逐項進行：

* **臨時的、每個工作階段的容器**：在新鮮容器或 VM 中執行每個執行器程序，該容器或 VM 在程序退出時被銷毀，使用 `--capacity 1` 和預設的 `--drain-grace-sec 0`，以便每個容器恰好服務一個工作階段。在更高的容量或正的清空寬限期下，一個容器服務來自同一[鎖定所有者](https://code.claude.com/docs/zh-TW/self-hosted-environments#key-concepts)的多個工作階段；請參閱[執行器生命週期](https://code.claude.com/docs/zh-TW/self-hosted-environments#runner-lifecycle)。不要在執行器重新啟動之間重複使用檔案系統，除非在刻意的[預熱簽出](#reuse-a-pre-warmed-checkout)設定中，並且永遠不要跨所有者。
  * 當執行器停止工作階段時，它不會向在其 shell 命令結束後仍在執行的程序傳送任何訊號，例如已轉為常駐程式（daemonized）的服務。銷毀容器或 VM 會結束該程序。
* **映像中沒有廣泛的憑證**：不要包含長期的 SSH 金鑰、雲端提供商憑證，或授予超過工作階段所需權限的個人存取 token。工作階段期間使用的憑證，例如推送或 API token，應從您的[包裝器指令碼](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#wrapper-scripts)按工作階段產生。初始複製會在包裝器執行之前發生，因此請使用 [`checkout` 生命週期 hook](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration#checkout) 處理，或在工作階段的所有儲存庫都位於 github.com 上時使用 [`--use-anthropic-git-proxy`](#use-the-anthropic-git-proxy)。關於這兩者，請參閱[設定 git](#configure-git)。
* **讓工作階段無法接觸主機的 GitHub 憑證**：Claude 可以使用工作階段能讀取的任何 GitHub 憑證，並擁有該憑證所授予的任何存取權。請將執行器主機本身範圍廣泛的 GitHub 憑證排除在工作階段可讀取的任何位置之外。此類憑證可能是個人存取 token、`gh auth login` 為您的帳戶儲存的 token，或執行器環境中的 `GH_TOKEN`。
  * **使用 [Anthropic 管理的 git](#use-the-anthropic-git-proxy) 時**：若有此類憑證，Claude 會直接連線到 GitHub，而不是透過 Anthropic 管理的 git。
  * **不使用 Anthropic 管理的 git 時**：如果您依照[在映像中提供 git 設定](#ship-git-config-in-your-image)所述嚴格限制其範圍，複製憑證可以保留在映像中。
* **將環境祕密保留在執行工作階段的主機之外**：環境祕密可以註冊執行器並拾取在環境上排隊的任何工作階段。在固定群中，它存在於每個執行器主機上，任何工作階段的程式碼都可以讀取祕密檔案。優先使用[按需執行器](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#on-demand-runners)，其中祕密保留在協調器主機上，該主機永遠不執行使用者程式碼，每個執行器接收單次使用的工作單據，該單據恰好註冊一個執行器。在固定群中，將環境祕密檔案視為可由每個工作階段讀取，並在任何懷疑的工作階段洩露後輪換祕密。
* **預設拒絕網路出站流量**：在每個環境上限制執行器和工作階段容器的出站流量在您自己的網路邊界；[預設拒絕出站流量](#default-deny-egress)涵蓋允許什麼以及為什麼。
* **最小權限主機 IAM**：附加到執行器主機的計算身份，例如執行個體設定檔或節點服務帳戶，應僅授予執行器本身需要的內容。工作階段應通過您的包裝器指令碼而不是繼承主機的身份來獲得自己的認證。
* **阻止工作階段的雲端中繼資料端點**：將工作階段保留在主機身份之外需要阻止它們對雲端中繼資料端點的存取，子網級出站流量原則不會攔截連結本地中繼資料流量，因此在容器本身中阻止它：

  * IMDSv2，跳數限制為 1
  * GKE Workload Identity，具有中繼資料隱藏
  * 工作階段容器網路命名空間中 `169.254.169.254` 的明確拒絕

  該阻止也適用於您的包裝器指令碼和生命週期鉤子，因為它們共享容器。使用[工作階段 JWT](https://code.claude.com/docs/zh-TW/self-hosted-environments-identity.md)對您自己的令牌服務進行身份驗證，通過允許列表出站流量，或使用基於檔案的 Web 身份，例如 Amazon EKS 上的 IAM Roles for Service Accounts (IRSA)。
* **每個執行器的檔案系統隔離**：每個執行器程序獲得自己的工作目錄，主機上沒有其他程序可以讀取或寫入。使 `--hooks-dir`、包裝器指令碼和主機的 `~/.claude/` 對工作階段唯讀，無論是內置在映像中還是以唯讀方式掛載。
* **分派沒有每個環境的存取控制**：您 Anthropic 組織的任何成員都可以向其任何環境分派工作階段。如果所有者[將 Claude Tag 頻道路由到環境](https://code.claude.com/docs/zh-TW/cloud-environments.md#set-the-environment-a-claude-tag-channel-uses)，[Claude Tag 存取設定](https://claude.com/docs/claude-tag/admins/restrict-access#restrict-who-can-use-claude)允許的任何人都可以啟動在那裡執行的頻道工作階段。預設情況下，這是連接的 Slack 工作區中的任何人，無論是否有 Claude 帳戶。將每個執行器主機視為可由所有可以向其分派的人進行程式碼執行，並且只在執行器主機上放置所有這些人都被允許讀取的資料和認證。[`--lock-to-account`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags)限制給定主機執行哪個帳戶的工作階段，但它不會縮小誰可以分派到環境中。要使自託管環境成為唯一的選擇器選項，[所有者](https://code.claude.com/docs/zh-TW/cloud-environments.md#organization-shared-environments)可以從[**雲端環境**頁面](https://claude.ai/admin-settings/cloud-environments)隱藏整個組織的 Anthropic 託管環境。
* **強制執行儲存庫設定防護**：使用 [`--confine-repo-settings`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags)選擇防護模式。預設的 `warn` 記錄違規並仍然生成工作階段，`enforce` 拒絕工作階段，`off` 禁用掃描。執行器掃描每個儲存庫的已提交設定以查找：

  * 在該工作階段自己的工作區之外解析的授予：`additionalDirectories` 項目、`permissions.allow` 中的 `Edit`、`Write` 或 `NotebookEdit` 規則，或 `sandbox.filesystem.allowWrite` 或 `allowRead` 項目
  * 非空的 `env` 塊
  * 操作員姿態覆蓋，例如 `sandbox.enabled: false`

  防護無論 [`--trust-workspace`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags)如何都會執行，並且不涵蓋儲存庫鉤子、`.mcp.json` 或 Bash 規則；請參閱[權限和工具批准](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#permissions-and-tool-approval)以了解這些授予應該在哪裡。

> [!NOTE]
>
> 如果您的組織已啟用 [IP 允許清單](https://support.claude.com/en/articles/13200993-restrict-access-to-claude-with-ip-allowlisting)，請在啟動執行器和工作階段容器之前，將它們的公用出站位址加入允許清單。如果您執行[按需執行器](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#on-demand-runners)，也請加入協調器主機的位址。不要依賴允許清單作為執行器或工作階段流量的網路控制，而應改為在您自己的網路邊界套用預設拒絕出站流量。

## 網路要求

執行器及其生成的工作階段子項進行出站連接到以下主機。將工作階段容器出站流量限制為這些主機和工作階段需要到達的特定內部服務；[預設拒絕出站流量](#default-deny-egress)涵蓋如何以及為什麼。

這些主機始終是必需的：

| 主機 | 連接埠 | 用途 |
| :- | :- | :- |
| `api.anthropic.com` | 443、HTTPS；WSS 用於 [Anthropic 管理的 Git](#use-the-anthropic-git-proxy) | 執行器控制平面和工作階段串流、模型推理、功能旗標、產品分析、[JWKS](https://code.claude.com/docs/zh-TW/self-hosted-environments-identity.md) 金鑰提取、提交簽名，以及設定 `--use-anthropic-git-proxy` 時的 Anthropic 管理的 Git |
| 您的 Git 主機，例如 `github.com` 或您的 GitHub Enterprise 主機 | 443 或 22 | 在執行器工作階段所使用的每個 Git 主機上複製和推送儲存庫。對於使用 [`--use-anthropic-git-proxy`](#use-the-anthropic-git-proxy) 的執行器，請參閱[何時仍需要 `github.com` 路徑](#github-com-egress-with-the-anthropic-git-proxy)。 |

使用 [`--use-anthropic-git-proxy`](#use-the-anthropic-git-proxy) 的執行器會將其 `github.com` Git 流量路由通過 `api.anthropic.com`，因此不需要 `github.com` 的 Git 主機路徑。如果您設定了 `--push-outcome-on-release` 或從 `post-session` hook 推送，則仍需要該路徑。

這些主機是否需要取決於您的配置：

| 主機 | 連接埠 | 何時需要 |
| :- | :- | :- |
| `api.github.com` | 443 | 無論是否使用 `--use-anthropic-git-proxy`，當執行器映像包含 [GitHub CLI](#github-api-access-with-the-github-cli) 且您為工作階段提供 github.com 憑證（例如 `GH_TOKEN`）時 |
| `downloads.claude.ai` | 443 | 在安裝時，當您使用原生安裝程式在主機上安裝或更新 Claude Code 時；`install.sh` 指令碼本身是從 `claude.ai` 提供的。在工作階段執行時，僅當工作階段從官方 Anthropic 市場安裝外掛程式時。 |
| `storage.googleapis.com` | 443 | 在工作階段執行時，用於 `/plugin` 中顯示的外掛程式安裝計數和中繼資料。 |
| `code.claude.com` 和 `claude.com` | 443 | 內置 claude-code-guide 代理的文件查詢和工作階段期間預先批准的 WebFetch 請求。阻止這些主機只會影響文件查詢。 |
| `*.frame.claudeusercontent.com` | 443 | 僅當[工件工具](https://code.claude.com/docs/zh-TW/artifacts.md#availability)對您組織中的工作階段可用時；預設值因方案而異，根據那裡的可用性表。在執行器上設定 `CLAUDE_CODE_DISABLE_ARTIFACT=1` 以保持工具禁用，無論組織設定如何。 |
| `registry.npmjs.org` | 443 | 當工作階段安裝外掛程式時，用於提取 npm 源外掛程式套件和安裝外掛程式的 Node.js 依賴項，或當 `npx` 啟動的 MCP 伺服器執行時 |
| 您的建置所使用之套件登錄的內部鏡像，或套件登錄本身 | 443，或您鏡像的連接埠 | 當工作階段安裝相依套件以建置或測試您的儲存庫時 |
| `http-intake.logs.us5.datadoghq.com` | 443 | Anthropic 操作指標。僅當設定 `CLAUDE_CODE_BYOC_ENABLE_DATADOG=1` 時；在自託管環境中預設關閉。 |
| `browser-intake-us5-datadoghq.com` | 443 | Anthropic 錯誤報告上傳，僅在為工作階段帳戶啟用[錯誤報告](https://code.claude.com/docs/zh-TW/data-usage.md#telemetry-services)時發送。由 `DISABLE_ERROR_REPORTING=1` 或 `DISABLE_TELEMETRY=1` 抑制。 |
| 您的雲端供應商用於模型請求、模型查詢和更新憑證的端點，例如 `bedrock-runtime.us-east-1.amazonaws.com` 或 `aiplatform.googleapis.com` | 443 | 僅當執行器[將模型請求傳送至 Amazon Bedrock 或 Google Cloud 的 Agent Platform](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#send-model-requests-to-bedrock-or-agent-platform) 時 |

您不需要為執行器或工作階段流量將這些主機加入允許清單：

* **`statsig.anthropic.com`、`*.sentry.io`、`claude.ai` 和 `platform.claude.com`**：這些主機出現在一些較舊的企業網路檢查清單中，但執行器不會連線到它們。功能旗標提取會前往 `api.anthropic.com`，而執行器使用環境祕密而非互動式 OAuth 進行身分驗證。
* **`mcp-proxy.anthropic.com`**：自託管工作階段不使用它。當您的組織啟用連接器傳遞時，您組織的 claude.ai 連接器會透過 `api.anthropic.com` 到達工作階段。請參閱 [MCP 伺服器](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#mcp-servers)。

以下主機端流程確實會連線到 `claude.ai`，因此請從出站流量允許連線到它的主機執行這些流程，而不是擴大工作階段容器的出站流量：

* **單行安裝程式**：在安裝時從 `claude.ai` 提取 `install.sh`。
* **互動式 `claude auth login`**：透過 `claude.ai`、`claude.com` 和 `platform.claude.com` 登入。[引導式設定](https://code.claude.com/docs/zh-TW/self-hosted-environments-quickstart.md#run-the-guided-setup)、`doctor` 的已登入模式和 [CI 分派](https://code.claude.com/docs/zh-TW/self-hosted-environments-testing.md#authenticate-from-ci)會使用它。您用來登入的瀏覽器也會從 `hcaptcha.com`、`*.hcaptcha.com` 和 `challenges.cloudflare.com` 載入 claude.ai 登入頁面的瀏覽器檢查。如果您的組織使用單一登入，該瀏覽器也可能會透過 `sso.claude.com` 重新導向。

### 預設拒絕出站流量

在網路區段或命名空間中部署執行器和工作階段容器，其出站流量限制為[網路要求表](#network-requirements)中的主機、您的 Git 主機和工作階段需要到達的特定內部服務。該產品無法驗證或強制執行此操作，因此在每個環境上的您自己的網路邊界應用它。工作階段程式碼是模型導向的，可以嘗試連接到任意主機；網路層的預設拒絕出站流量限制這些嘗試可以到達的位置。這無論權限模式如何都適用：預設預先批准的工具集已包括 `Bash`，因此 shell 出站流量在沒有[自動模式](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#permissions-and-tool-approval)的情況下執行而不提示。

有關每個工作階段發出的遙測詳細資訊以及如何關閉它，請參閱[遙測](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference.md#telemetry)。

### 向出站代理進行身份驗證

某些企業出站代理在每個連接上需要 `Proxy-Authorization` 標頭。該標頭中的令牌通常輪換得太快，無法寫入您在 `HTTPS_PROXY` 中設定的代理 URL。像往常一樣將 `HTTPS_PROXY` 或 `HTTP_PROXY` 設定為您的代理 URL，然後設定 `--proxy-authorization-command` 或 `--proxy-authorization-file` 以告訴執行器從何處讀取標頭值。兩個旗標都需要 Claude Code v2.1.238 或更新版本。

#### 選擇 `Proxy-Authorization` 值的來源

選擇與您如何產生 `Proxy-Authorization` 令牌相符的旗標：

* **[`--proxy-authorization-command <command>`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags)**：為您按需生成的令牌選擇此項。執行器執行 shell 命令並使用其修剪的 stdout 作為標頭值，例如 `Bearer <token>`。
* **[`--proxy-authorization-file <path>`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags)**：為另一個程序在原位輪換的令牌選擇此項。執行器讀取檔案並使用其修剪的內容作為標頭值。

#### 執行器拒絕啟動的配置

每個旗標也有環境變數形式，在[執行器 CLI 旗標參考](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference.md#runner-cli-flags)中列在其旁邊。在執行器聯繫您的代理或控制平面之前，它檢查旗標及其變數，並在三種情況下拒絕啟動：

* **兩個旗標都設定**：一個旗標加上另一個旗標的環境變數計為設定兩個。
* **沒有代理 URL**：`HTTPS_PROXY` 和 `HTTP_PROXY` 都不包含 `http://` 或 `https://` URL。執行器以大寫或小寫讀取兩個變數，不查詢 `ALL_PROXY`。
* **任一旗標傳遞給協調器子命令**：`self-hosted-runner orchestrator` 不接受旗標或其環境變數。改為將旗標傳遞給協調器啟動的每個執行器。

#### 設定代理授權旗標時執行器更改的內容

設定任一旗標後，執行器啟動自己的偵聽器並通過該偵聽器發送來自自己、其生命週期鉤子和其工作階段的代理流量。偵聽器在前往您的代理的途中添加 `Proxy-Authorization` 標頭。

* **偵聽器**：偵聽器是 `127.0.0.1` 上的轉發代理。執行器在向控制平面註冊之前啟動偵聽器，如果偵聽器無法啟動則在啟動時退出。
* **代理變數**：執行器重寫您設定的 `HTTPS_PROXY` 和 `HTTP_PROXY` 中的任一個，使其指向偵聽器。該重寫的值到達執行器本身、其生命週期鉤子和它執行的每個工作階段。
* **令牌輪換**：輪換的令牌無需重新啟動即可生效。對於偵聽器打開到您的代理的每個連接，執行器再次執行您的命令或讀取您的檔案並將結果添加為標頭。
* **工作階段環境**：工作階段僅通過偵聽器到達您的代理。在每個工作階段的環境中，執行器移除 `ALL_PROXY`、移除您未設定的 `HTTPS_PROXY` 或 `HTTP_PROXY` 的任何拼寫，並將 `NO_PROXY` 固定到執行器自己的值。
* **日誌**：執行器永遠不會記錄標頭值。

## 配置 Git

執行器管理儲存庫簽出但預設不配置 Git 身份或認證。您控制執行器的映像和程序環境，因此您控制 Git 配置。選擇兩種方法之一：

* **讓執行器配置 Git**：使用 `--configure-git` 啟動執行器，以使其寫入 Anthropic 託管工作階段使用的相同身份和提交簽名配置
* **在映像中提供 Git 配置**：自己設定身份和推送認證，例如在您自己的機器人身份下提交

對於 github.com 上的儲存庫，您也可以使用 [`--use-anthropic-git-proxy`](#use-the-anthropic-git-proxy) 啟動執行器，或設定 `CLAUDE_RUNNER_USE_GIT_PROXY=1`，請 Anthropic 為執行器的工作階段提供 Git 服務。

執行器主機上的 Git 版本下限：[`--configure-git`](#let-the-runner-configure-git) SSH 提交簽名需要 Git 2.34 或更新版本，[`--use-anthropic-git-proxy`](#use-the-anthropic-git-proxy) 需要 2.32 或更新版本，從 [`--push-outcome-on-release`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags) 推送的分支恢復工作階段需要 2.29 或更新版本。如果您省略所有三個並自己管理 Git 身份，Git 2.24 就足夠了。

### 讓執行器配置 Git

使用 `--configure-git` 啟動執行器，或設定 `SELF_HOSTED_RUNNER_CONFIGURE_GIT=1`，以使其在啟動時寫入全域 Git 配置：

* `user.name = Claude` 和 `user.email = noreply@anthropic.com`，與 Anthropic 託管工作階段相符
* SSH 格式提交和標籤簽名，通過執行器管理的填充程式路由，該填充程式使用工作階段自己的認證通過 Anthropic 的簽名服務簽名每個提交。簽名可在 GitHub 上針對 Anthropic 的已發佈 SSH 簽名金鑰進行驗證。
* `push.negotiate = true`，因此 Git 在打包推送之前詢問您的 Git 主機它已經擁有哪些提交。需要 Claude Code v2.1.257 或更新版本。
* `core.hooksPath` 指向執行器管理的 hook 目錄。其 `commit-msg` 和 `prepare-commit-msg` hook 會為每個提交加上工作階段建立者的 `Co-authored-by:` trailer。該 trailer 由 [`CCR_SESSION_ACCOUNT_EMAIL`](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration#wrapper-scripts) 中的電子郵件建立，當該變數未設定時則省略。如果您的映像已設定 `core.hooksPath`，且執行器未使用 [Anthropic 管理的 Git](#use-the-anthropic-git-proxy)，執行器會保留您的設定、跳過安裝這些 hook，並列印 `[runner:git]` 警告。

提交簽名需要 Git 2.34 或更新版本；執行器在啟動時檢查並在您的 Git 較舊時以錯誤退出。此旗標不配置推送認證，您仍在映像中提供。

在 v2.1.280 或更新版本的執行器上，您從 `checkout` 或 `post-session` 生命週期 hook 所建立的提交也會以工作階段身分簽署，但不會加上 `Co-authored-by:` trailer。[生命週期 hook 內的 Git 設定](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#git-configuration-inside-lifecycle-hooks)說明了執行器在這些 hook 內固定的 Git 設定。

無論是否使用 `--configure-git`，Claude Code 都會指示 Claude 在提交訊息結尾加上 `Claude-Session: <url>` trailer，並在 pull request 描述結尾加上工作階段的 URL。若要省略兩者，請在執行器主機的 [`~/.claude/settings.json`](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration#how-each-session’s-config-is-assembled) 中將 [`attribution.sessionUrl`](https://code.claude.com/docs/zh-TW/settings-reference#attribution-sessionurl) 設為 `false`，然後重新啟動執行器。

### 在映像中提供 Git 配置

Git 身份對任何提交都是必需的。在您的 Dockerfile 中系統範圍設定它，以便配置無論執行器程序以哪個使用者身份執行都適用：

```dockerfile theme={null}
RUN git config --system user.name "Claude" && \
    git config --system user.email "noreply@anthropic.com"
```

沒有身份，`git commit` 失敗並顯示 `Please tell me who you are`，工作階段無法取得進展。您可以改用自己的機器人身份；執行器不會覆蓋這些值。

請勿將長期或範圍廣泛的推送憑證內建到共用的執行器映像中：映像中的憑證可供該映像執行的每個工作階段使用，無論是誰啟動的。請改為從您的[包裝指令碼](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#wrapper-scripts)為每個工作階段產生短期、最小範圍的 token，並使用從工作階段 JWT 解碼出的工作階段建立者身分。搭配每個工作階段專用的臨時容器（這需要 `--capacity 1`），使任何憑證都不會比產生它的工作階段存活更久；請參閱[強化部分](#harden-your-deployment)。

如果您必須在映像級別配置推送認證，例如對於唯讀部署金鑰，請盡可能緊密地限制它們：

* SSH 部署金鑰限制為一個儲存庫，帶有 `url.<base>.insteadOf` 重寫
* 傳回最小範圍 token 的 `credential.helper`
* 指向範圍狹小之金鑰的 `GIT_SSH_COMMAND`

您設定的任何機制都必須無需提示即可運作，因為執行器的內建複製和提取會停用 Git、SSH 和 Git Credential Manager 原本會顯示的提示：

* 執行器設定 `GIT_TERMINAL_PROMPT=0`，因此 Git 不會要求使用者名稱或密碼。
* 執行器使用 `BatchMode=yes` 執行 SSH，附加到您的 `GIT_SSH_COMMAND`（如果您設定了），因此 SSH 不會要求密碼短語或主機確認。
* 執行器設定 `GCM_INTERACTIVE=never`，因此 Git Credential Manager 不會打開登入對話框。在 v2.1.229 之前，儲存庫準備可能會卡在 Git Credential Manager 的提示上。
* 執行器清除 `core.askPass`，因此如果您使用 askpass 幫助程式，請改為通過 `GIT_ASKPASS` 環境變數設定它。

如果您的 Git 主機拒絕認證，或您沒有配置認證，執行器會重試幾次，然後失敗儲存庫準備當儲存庫是工作階段推送結果的儲存庫時。對於工作階段僅從中讀取的儲存庫，[Troubleshooting](#troubleshooting) 涵蓋執行器何時改為跳過它。執行器不會將這些設定傳遞到工作階段的環境中。

保持您在 `GIT_SSH_COMMAND` 或 `GIT_ASKPASS` 中命名的任何程式，工作階段無法寫入它，就像[強化檢查清單](#harden-your-deployment)要求鉤子目錄和包裝器指令碼的方式一樣。該程式命令行上的任何金鑰或檔案也是如此。執行器自己的 Git 在複製或提取時執行該程式。

如果簽出目錄由與執行器程序不同的 uid 擁有，Git 拒絕對其進行操作；添加 `safe.directory`：

```dockerfile theme={null}
RUN git config --system --add safe.directory '*'
```

### 使用 Anthropic Git 代理

使用 Anthropic Git 代理伺服器（也稱為 Anthropic 管理的 Git）時，執行器映像不需要為工作階段本身準備任何 SSH 金鑰、憑證輔助程式、`.netrc` 或其他 Git 憑證。執行器會改為請 Anthropic 為其工作階段提供 Git 服務。對於 Anthropic 所服務的使用者工作階段，執行器的複製以及工作階段自己的提取和推送都會經過 Anthropic，Anthropic 使用為工作階段建立者儲存的 GitHub OAuth token。[Anthropic 如何為工作階段提供 Git 服務](#how-anthropic-serves-git-for-a-session)說明了機器人和 agent 工作階段的情況。

除非您[將其開啟](#turn-the-anthropic-git-proxy-on)，否則 Git 代理伺服器是關閉的。以自己的憑證連線到 Git 主機的執行器不需要它，其 Git 可搭配任何 Git 主機運作。

相對地，Git 代理伺服器會限制執行器支援的範圍，並改變執行器所需的條件：

* **僅限 github.com**：只有當工作階段的所有儲存庫都位於 github.com 時，Anthropic 才會服務該工作階段，且 Git 代理伺服器目前尚不支援 GitHub Enterprise Server。在使用 Git 代理伺服器的執行器上，含有其他 Git 主機儲存庫的工作階段[無法啟動](#when-anthropic-doesnt-serve-a-session)。
* **僅提供工作階段儲存庫的憑證**：Anthropic 只會為屬於該工作階段的儲存庫提供 Git 憑證，而不會為同一 Git 主機上的其他儲存庫提供。私有 submodule、套件管理員透過 Git 擷取的相依套件，或位於其他儲存庫中的外掛市集，都無法從 Anthropic 取得憑證。請建立工作階段的人在建立時[加入工作階段所需的每個儲存庫](https://code.claude.com/docs/zh-TW/web-quickstart.md#start-a-task)。

  [雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md)的每次執行都是一個包含該任務儲存庫的工作階段，因此請每個任務的擁有者[加入其執行所需的每個儲存庫](https://code.claude.com/docs/zh-TW/routines.md#edit-and-control-routines)。
* **僅限分支推送**：刪除分支的推送會失敗，推送到任何其他類型的 ref（例如標籤）也會失敗。關於推送可以更新哪些分支，請參閱 [GitHub 代理伺服器](https://code.claude.com/docs/zh-TW/cloud-environments.md#github-proxy)。
* **已連結的 GitHub 帳戶**：請每位以儲存庫建立使用者工作階段的人[連結 GitHub](https://code.claude.com/docs/zh-TW/web-quickstart.md#connect-github)。若沒有自己的連結，這些工作階段[無法啟動](#creator-has-no-github-connection)。
* **`--capacity 1`**：Git 代理伺服器要求每個執行器程序只處理一個工作階段，因此請執行更多副本以實現平行處理。[開啟 Anthropic Git 代理伺服器](#turn-the-anthropic-git-proxy-on)列出了相關要求。
* **取代全域 Git 設定**：執行器會[刪除並取代其執行身分使用者的全域 Git 設定](#git-proxy-replaces-global-git-config)。請以專用使用者身分或在容器中執行它。
* **主機推送使用主機憑證**：執行器的 [`--push-outcome-on-release`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags) 推送，以及您的 [`post-session` hook](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration#post-session) 所做的任何推送，仍會使用執行器主機自己的 Git 憑證及其[到 `github.com` 的網路路徑](#github-com-egress-with-the-anthropic-git-proxy)。請將這些憑證保存在[全域 Git 設定](#git-proxy-replaces-global-git-config)之外，並參閱[在映像中提供 Git 設定](#ship-git-config-in-your-image)以了解提供這些憑證的方式。
* **逐一工作階段決定**：Anthropic 會針對執行器上的每個工作階段決定是否為其提供 Git 服務，未被服務的工作階段將無法啟動。[在使用 Git 代理伺服器的執行器上工作階段無法啟動時](#when-anthropic-doesnt-serve-a-session)說明了原因。

> [!WARNING]
>
> 設定 `--use-anthropic-git-proxy` 時，執行器會刪除並取代其執行身分使用者的全域 Git 設定，且不保留任何備份。它會在啟動時以及每個工作階段之前執行此操作。您保存在那裡的登入資訊或憑證輔助程式將會遺失。[`--configure-git`](#let-the-runner-configure-git) 寫入的設定則會保留。請以專用使用者身分或在容器中執行執行器，切勿以您自己的使用者身分執行。

請將非機密的 Git 設定（例如身分和 `safe.directory`）保存在系統 Git 設定中。

#### 開啟 Anthropic Git 代理伺服器

在使用 `--use-anthropic-git-proxy` 啟動執行器之前，請確認執行器主機符合以下每項要求。當容量或 Git 要求未滿足時，執行器會拒絕啟動：

* **Claude Code v2.1.267 或更新版本**：較早的版本接受該旗標，但不會回報請 Anthropic 提供 Git 服務的請求，也不會列印 `Registering as opted in` 行，因此 Anthropic 不會服務其工作階段。
* **`--capacity 1`（預設值）**：每個執行器程序一次處理一個工作階段，因此請執行更多副本以實現平行處理。
* **Git 2.32 或更新版本**：較舊的 Git 會忽略執行器為 Git 代理伺服器設定的每個工作階段 Git 設定。

> [!WARNING]
>
> 本頁上的 [Kubernetes](#kubernetes) 和 [Docker Compose](#docker-compose) 配方使用 `--capacity 4`。如果您在不將容量更改為 `1` 的情況下將 `--use-anthropic-git-proxy` 或 `CLAUDE_RUNNER_USE_GIT_PROXY=1` 添加到其中之一，每次您的協調器重新啟動執行器時，執行器都會在啟動時退出。設定 `--capacity 1` 並執行更多副本以實現並行性。[When the runner exits](#when-the-runner-exits) 顯示執行器列印的行。

若要開啟 Git 代理伺服器，請在執行器的命令中加入 `--use-anthropic-git-proxy`，或在執行器的環境中設定 `CLAUDE_RUNNER_USE_GIT_PROXY=1`。以下命令在執行器主機的 shell 中執行，會以開啟 Git 代理伺服器的方式啟動[快速入門](https://code.claude.com/docs/zh-TW/self-hosted-environments-quickstart.md#set-up-manually)中的執行器：

```bash theme={null}
claude self-hosted-runner --environment-secret-file '/etc/claude/environment-secret' --base-dir '<writable-dir>' --use-anthropic-git-proxy
```

啟動時，執行器會列印 `Registering as opted in to Anthropic-managed git (--use-anthropic-git-proxy)`。接著 Anthropic 會針對該執行器上的每個工作階段決定是否為其提供 Git 服務。對於每個被服務的工作階段，執行器會記錄一行包含 `governed git ACTIVE` 的 `[runner:session]`。如果工作階段反而無法啟動，請參閱[在使用 Git 代理伺服器的執行器上工作階段無法啟動時](#when-anthropic-doesnt-serve-a-session)。

#### Anthropic 如何為工作階段提供 Git 服務

對於 Anthropic 所服務的工作階段，執行器的複製以及工作階段自己的提取和推送都會經過 Anthropic，並以工作階段自己的短期 token 進行身分驗證：

* **使用者工作階段**：Anthropic 使用為工作階段建立者儲存的 GitHub OAuth token。
* **機器人和 agent 工作階段**：Anthropic 使用您組織的 GitHub App 安裝 token。
* **URL 重寫**：`--git-host-rewrite` 和 `--git-ssh-rewrite` 對 Git 代理伺服器所服務的儲存庫沒有作用。

#### 在使用 Git 代理伺服器的執行器上工作階段無法啟動時

在以 `--use-anthropic-git-proxy` 啟動的執行器上，當 Anthropic 不為工作階段提供 Git 服務時，該工作階段將無法啟動。請在執行器的日誌中尋找指出包含 `/git_proxy/` 之 `api.anthropic.com` 位址的 Git 錯誤。

對於每個工作階段，Claude Code v2.1.267 或更新版本的執行器也會記錄以下其中一行：當 Anthropic 服務該工作階段的 Git 時，記錄一行包含 `governed git ACTIVE` 的 `[runner:session]`；若未服務，則記錄一行包含 `the server withheld Anthropic-managed git for this session` 的 `[runner:warn]`。請在以下情況中找出您看到的那一行：

* **既沒有 `governed git ACTIVE` 也沒有 `withheld` 行**：早於 Claude Code v2.1.267 的執行器兩行都不會記錄，且 Anthropic 不會服務其工作階段。請依照[固定版本](#pin-the-version)將執行器更新至 v2.1.267 或更新版本。
* **`withheld` 行**：Anthropic 未服務該工作階段。先前可搭配 Git 代理伺服器運作的執行器，也可能在您這邊沒有任何變更的情況下以這種方式失敗。
  * **有儲存庫不在 github.com 上**：只要工作階段中有任何一個儲存庫位於其他 Git 主機（例如 GitHub Enterprise Server），該工作階段就不會被服務，包括其 github.com 儲存庫在內。請為該環境的執行器[關閉 Anthropic Git 代理伺服器](#turn-the-anthropic-git-proxy-off)。
  * **所有儲存庫都在 github.com 上**：請將此失敗連同 `withheld` 行中的工作階段 ID 回報給[您的 Anthropic 客戶團隊](#report-an-issue)。Anthropic 會在其端記錄原因。
* **包含 `remote: access denied by the git proxy` 的行**：即使是 Anthropic 所服務的工作階段仍可能被拒絕，例如當組織政策拒絕該工作階段的 Git 存取，或該工作階段未獲授權存取該儲存庫時。此時執行器的日誌會顯示一行包含 `remote: access denied by the git proxy` 的內容，該行其餘部分會說明原因。
* **`GitHub authentication required`**：當工作階段建立者在 claude.ai 上沒有可用的 GitHub 連結時會出現此訊息。工作階段的複製會失敗，Git 錯誤訊息為 `GitHub authentication required. Please reconnect your GitHub account.` 請該使用者在其 claude.ai 設定中連結或重新連結 GitHub。

修正原因後，請重新啟動失敗的工作階段。

#### 關閉 Anthropic Git 代理伺服器

如果某個環境中的工作階段使用位於 github.com 以外 Git 主機（例如 GitHub Enterprise Server）上的儲存庫，請為該環境的執行器關閉 `--use-anthropic-git-proxy`。

**1. 移除旗標**

從執行器的命令中移除 `--use-anthropic-git-proxy`。如果您在執行器的環境中（例如 pod spec 或 Compose 檔案）設定了 `CLAUDE_RUNNER_USE_GIT_PROXY`，請在該處將其移除。在 shell 中，請取消設定它：

```bash theme={null}
unset CLAUDE_RUNNER_USE_GIT_PROXY
```

**2. 為執行器提供 Git 憑證**

為執行器工作階段使用的每個 Git 主機（包括 github.com）提供無需提示即可運作的憑證。執行器使用者全域 Git 設定中原有的任何憑證都已消失，因為在設定 `--use-anthropic-git-proxy` 期間，執行器已刪除該設定。請[在映像中提供憑證](#ship-git-config-in-your-image)，或使用 [`checkout` 生命週期 hook](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration#checkout)。

**3. 開放網路路徑**

允許執行器透過連接埠 443 或 22 連線到執行器工作階段使用的每個 Git 主機。請參閱[網路需求](#network-requirements)中的 Git 主機列。

**4. 重新啟動執行器**

重新啟動執行器，讓它們在不使用 Git 代理伺服器的情況下註冊。然後重新啟動每個失敗的工作階段。

#### 不使用 GitHub CLI 存取 GitHub API

如果您的執行器映像不包含 GitHub CLI，Claude Code 可以提供內建的 `gh`，讓 Claude 仍能開啟 pull request、留言以及讀取 CI 結果。內建的 `gh` 適用於使用 Anthropic 管理之 Git 的執行器。它支援一個命令 `gh api`，用於呼叫 GitHub 的 REST API。執行器映像中需要 Claude Code v2.1.287 或更新版本。

以下命令會開啟 pull request，取代 `gh pr create`。內建的 `gh` 會為目前的儲存庫填入 `{owner}` 和 `{repo}`：

```bash theme={null}
gh api repos/{owner}/{repo}/pulls -f title='Fix' -f head='my-branch' -f base='main'
```

* **憑證**：內建的 `gh` 透過 Anthropic 管理的 Git 傳送其 REST 請求，由 Anthropic 端提供 GitHub 憑證，因此映像不需要為此準備 GitHub token
* **哪些工作階段會取得它**：Anthropic 會針對每個工作階段決定是否由 Anthropic 管理的 Git 提供該工作階段的 `gh`。若有提供，執行器為該工作階段記錄的 `[runner:session] governed git ACTIVE` 行會顯示 `gh_path_shim=true`。若沒有提供，該工作階段就沒有 `gh`
* **`jq`**：如果您希望 `--jq` 能運作，請在映像中安裝 `jq`
* **[`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`](https://code.claude.com/docs/zh-TW/env-vars)**：如果工作階段環境設定了它，Claude Code 不會提供內建的 `gh`，該工作階段就沒有 `gh`

#### 使用 GitHub CLI 存取 GitHub API

如果您的執行器映像包含供工作階段使用的 GitHub CLI，請讓您的[包裝指令碼](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#provision-credentials-scoped-to-the-session-creator)為每個工作階段替工作階段建立者產生短期、最小範圍的 `GH_TOKEN`。當 `gh` 位於 Claude Code 啟動時的 `PATH` 上，工作階段會使用該 `gh`，而不會有[內建的 `gh`](#github-api-access-without-the-github-cli)。有了該 token，該 `gh` 會以 token 授予的任何存取權連線到 GitHub，且不經過 Anthropic 管理的 Git，因此請允許 [`api.github.com`](#network-requirements)。

使用 Anthropic 管理的 Git 時，請將 GitHub CLI 排除在映像之外，以改用內建的 `gh`。

#### 使用 Anthropic 管理的 Git 信任私有憑證授權單位

如果您在執行器的環境中設定 `GIT_SSL_CAINFO` 或 `GIT_SSL_NO_VERIFY`，其工作階段使用 Anthropic 管理的 Git，本部分適用。它描述的處理需要執行器執行 Claude Code v2.1.283 或更新版本。

當執行器上的 Git 必須信任私有憑證授權單位 (CA)（例如 TLS 檢查代理簽署的憑證授權單位）時，通常的方法如下所示：

* **系統憑證存放區**：在執行器主機的系統憑證存放區中安裝您的 CA，Git 無需任何變數即可信任它。
* **`GIT_SSL_CAINFO`**：將其設定為您的 CA 的 PEM 檔案，例如 `GIT_SSL_CAINFO=/etc/ssl/corp-ca.pem`。
* **`GIT_SSL_NO_VERIFY`**：在重新簽署代理後沒有幫助。執行器自己通過 Anthropic 管理的 Git 複製檢查憑證，即使設定了變數，因此複製失敗直到 Git 通過其他兩種方法之一信任您的 CA。

對於將工作階段令牌傳遞到 Anthropic 管理的 Git 的 Git 連線，執行器應用這兩個變數如下。[`command` 鉤子](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration#command)以工作階段的環境開始，因此它獲得 Git 在工作階段內獲得的內容：

* **`GIT_SSL_CAINFO`**：Git 以何者檢查 Anthropic 管理的 Git，取決於 Git 執行的位置：
  * **執行器自己的複製和提取**：在不使用該變數的情況下執行，並以執行器寫入的每個工作階段憑證檔案檢查 Anthropic 管理的 Git。執行器會以執行器主機的系統 CA 套件和您檔案中的憑證建立該檔案。
  * **工作階段內的 Git**：取得以 `http.sslCAInfo` 設定指定您的檔案來取代該變數，另外還有 `http.<url>.sslCAInfo` 項目，以每個工作階段檔案檢查 Anthropic 管理的 Git。
  * **`checkout` 和 `post-session` hook**：原封不動地繼承該變數。
* **`GIT_SSL_NO_VERIFY`**：哪些憑證檢查保持關閉取決於 Git 執行的位置：
  * **執行器自己的複製和提取**：執行時不使用變數，並檢查它們呈現的憑證。
  * **工作階段內的 Git**：獲得 `http.sslVerify=false` 配置代替變數，因此檢查對其他主機保持關閉。它也獲得 `http.<url>.sslVerify=true` 項目，為 Anthropic 管理的 Git 保持檢查開啟。
  * **`checkout` 和 `post-session` 鉤子**：當工作階段在 Anthropic 管理的 Git 上有儲存庫時，獲得 `http.sslVerify=false` 配置代替變數。它們也獲得 `http.<url>.sslVerify=true` 項目，為 Anthropic 管理的 Git 保持檢查開啟。

每個工作階段憑證檔案需要在執行器主機上的 `/etc/ssl/certs/ca-certificates.crt` 或 `/etc/pki/tls/certs/ca-bundle.crt` 處的系統 CA 套件。它也需要執行器的使用者可以讀取的 `GIT_SSL_CAINFO` 檔案，保存 PEM `CERTIFICATE` 區塊，最多 1 MiB。當執行器無法建立每個工作階段檔案時，它記錄包含 `did not build the certificate file` 和原因的 `[runner:warn]` 行。Git 隨後按原樣為 Anthropic 管理的 Git 使用您的檔案。修復該行命名的內容。

對於使用 Anthropic 管理的 Git 的每個工作階段，執行器也記錄以 `governed git: GIT_SSL_CAINFO is set` 或 `governed git: GIT_SSL_NO_VERIFY is set` 開始的 `[runner:warn]` 行。該行說明執行器對其自己的 Git、工作階段內的 Git 和您的生命週期鉤子對該變數所做的操作。它以您是否需要更改任何內容結束。

### 將 github.com 儲存庫加入 Claude Tag 頻道工作階段

如果 Claude 無法將 github.com 儲存庫加入 Claude Tag 頻道工作階段，即使您的執行器可以複製該儲存庫，也請確認該頻道具有其存取權。該存取權來自 GitHub 上及您 Claude 組織中的設定，而非來自執行器的 Git 憑證。

**1. 安裝 Claude GitHub App**

在擁有該儲存庫的 GitHub 組織或帳戶上安裝 [Claude GitHub App](https://github.com/apps/claude)，並在安裝中包含該儲存庫。

**2. 連結 GitHub 組織或帳戶**

在 [**Organization settings > Git providers**](https://claude.ai/admin-settings/source-control) 中，將該組織或帳戶連結到您的 Claude 組織。同時也擁有該 GitHub 組織的 Claude 組織 Owner 可以進行連結。請參閱[連結您的 GitHub 組織](https://claude.com/docs/claude-tag/admins/configure-github#link-your-github-organization)。

**3. 授予儲存庫**

在 [Claude Tag 管理設定](https://claude.ai/admin-settings/claude-tag)中，將該儲存庫授予該頻道，或授予包含該頻道的更大範圍：其 Slack 工作區或整個 Slack。具有 Owner 角色或 Claude Tag Admin 權限的人可以授予。如果頻道管理員的 GitHub 帳戶是該儲存庫的管理員，頻道管理員也可以將其加入自己的頻道。請參閱[授予儲存庫存取權](https://claude.com/docs/claude-tag/admins/configure-github#grant-repository-access)。

然後在頻道中開始新的討論串，並在您的第一則訊息中[指明該儲存庫](https://claude.com/docs/claude-tag/admins/configure-github#how-granted-repositories-reach-a-session)。

如果 Claude 仍無法加入該儲存庫，請參閱[如果 Claude 無法存取儲存庫](https://claude.com/docs/claude-tag/admins/configure-github#if-claude-can%E2%80%99t-reach-a-repository)，了解應在何處檢查 GitHub 連結和儲存庫授權。

### 為私有網路重寫 Git URL

儲存庫 URL 從控制平面以 HTTPS 形式傳來，並帶有您 Git 主機的主機名稱；對於 GitHub Enterprise，這是您在 claude.ai 上為 [GitHub Enterprise 整合](https://code.claude.com/docs/zh-TW/github-enterprise-server.md)設定的主機名稱。兩個可重複使用的旗標會在複製之前重寫這些 URL：

* `--git-host-rewrite <from>=<to>`：用於分割視界 DNS，其中 Anthropic 通過外部主機名到達您的 Git 主機，但執行器必須使用內部主機名
* `--git-ssh-rewrite <host>`：用於僅接受 SSH 的 Git 主機，或僅有 SSH 金鑰的執行器主機。例如，若要透過 SSH 複製 github.com 儲存庫，請在執行器命令中加入 `--git-ssh-rewrite github.com`。執行器隨後會將 `https://github.com/owner/repo` 重寫為 `git@github.com:owner/repo`。SSH 必須[無需提示即可連線](#git-must-work-without-a-prompt)。

主機重寫首先執行，因此如果您需要兩者，請在 `--git-ssh-rewrite` 中列出內部主機名。為了完全控制簽出，使用 [`checkout` 生命週期鉤子](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration#checkout)。

### 在 GitHub 以外的儲存庫上啟動工作階段

若要在 GitHub 以外 Git 主機的儲存庫上執行工作階段，請從您的終端機，在該儲存庫的簽出中啟動工作階段。首先請檢查執行器的 Git 憑證、網路和 Git 代理伺服器、儲存庫的位址，以及您的分支：

* **Git 憑證和網路**：為 `https://<host>/<owner>/<name>`（執行器複製的位址）[提供](#ship-git-config-in-your-image)[無需提示即可運作](#git-must-work-without-a-prompt)的憑證，並讓執行器能夠連線到您的 Git 主機，如[網路需求](#network-requirements)所列。對於僅接受 SSH 的 Git 主機，請參閱 [`--git-ssh-rewrite`](#rewrite-git-urls-for-private-networks)。
* **Git 代理伺服器**：如果該環境的執行器使用 Anthropic Git 代理伺服器，請[將其關閉](#turn-the-anthropic-git-proxy-off)。
* **儲存庫位址**：檢查簽出的 `origin` remote。其主機必須是網域名稱，例如 `git.example.com`，且其路徑必須為 `<owner>/<name>` 的形式。巢狀路徑（例如 `group/subgroup/name`）無法通過。
* **分支**：將您目前所在的分支推送到您的 Git 主機，因為執行器會複製該分支。

在簽出中，依照[從 CI 進行身分驗證](https://code.claude.com/docs/zh-TW/self-hosted-environments-testing.md#authenticate-from-ci)所述登入 claude.ai 後，使用 [`--environment`](https://code.claude.com/docs/zh-TW/self-hosted-environments-testing#run-the-test-loop) 和您環境的 `ccpool_...` ID 執行 `claude -p`：

```bash theme={null}
claude -p "Fix the login bug" --environment ccpool_abc123 --output-format json
```

建立工作階段後，命令會列印一行以 `{"ok":true` 開頭的 JSON。如果 `origin` remote 不符合要求，命令會失敗並顯示 `requires a git source, but no GitHub remote was detected`。

請在您的 Git 主機上審查並合併工作階段所[推送](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#prompt-sessions-to-push-their-work)的分支。

## 構建執行器映像

Anthropic 不發佈預構建的執行器映像。在 `claude` 二進位檔案周圍構建您自己的，分層您的儲存庫需要的任何工具鏈：語言執行時、編譯器、套件管理器和 [MCP](https://code.claude.com/docs/zh-TW/mcp.md) 邊車。

下面的配方使用 `--capacity 4`，因此一個容器服務來自同一鎖定所有者的最多四個並發工作階段。這不提供[強化部分](#harden-your-deployment)中的每個工作階段容器隔離：在將環境連接到生產系統之前，要麼以 `--capacity 1` 執行配方，每個工作階段一個容器，要麼使用[按需執行器](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#on-demand-runners)，它也將環境祕密保留在執行工作階段的主機之外。如果您將[Anthropic git 代理](#use-the-anthropic-git-proxy)新增至其中一個配方，也請將 `--capacity` 變更為 `1`。

此 Dockerfile 是一個最小的起點。它安裝 `python3`，因為 [Anthropic 控制平面提供](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#how-each-session’s-config-is-assembled)給 Claude Tag 工作階段的 hook（包括讓 Claude 在 Slack 中發佈回覆的 hook）會執行 `python3`。在任何服務 Claude Tag 工作階段的映像中，請將 `python3` 保留在 `PATH` 上：

```dockerfile theme={null}
FROM debian:bookworm-slim
ARG CLAUDE_CODE_VERSION
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates openssh-client jq python3 \
 && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL "https://downloads.claude.ai/claude-code-releases/${CLAUDE_CODE_VERSION:?set with --build-arg CLAUDE_CODE_VERSION}/linux-x64/claude" \
      -o /usr/local/bin/claude && chmod +x /usr/local/bin/claude
RUN git config --system user.name "Claude" \
 && git config --system user.email "noreply@anthropic.com" \
 && git config --system --add safe.directory '*'
ENTRYPOINT ["claude"]
```

如果您的節點是 ARM，將 `linux-x64` 交換為 `linux-arm64`，或在 Alpine 等 musl 基礎映像上交換為 `linux-x64-musl` 或 `linux-arm64-musl`；請參閱 [Alpine Linux 設定](https://code.claude.com/docs/zh-TW/setup.md#alpine-linux-and-musl-based-distributions)以了解 musl 映像需要的額外套件。URL 是標準 Claude Code 發佈位置，因此您可以根據[二進位檔案完整性和程式碼簽名](https://code.claude.com/docs/zh-TW/setup.md#binary-integrity-and-code-signing)中描述的發佈的已簽名清單驗證下載的二進位檔案。執行器需要 Claude Code 版本 2.1.224 或更新版本，若要服務 Claude Tag 工作階段則需要 2.1.229 或更新版本。建置映像，然後將其推送到您的登錄檔並在下面的配方中引用它：

```bash theme={null}
docker build \
  --build-arg CLAUDE_CODE_VERSION="$(curl -fsSL https://downloads.claude.ai/claude-code-releases/stable)" \
  -t <your-registry>/claude-runner:latest .
```

命令替換會查詢目前的 `stable` 發佈號碼，並將其作為構建引數傳遞，因此在新的穩定版本發佈後執行相同的命令會使用較新的二進位檔案重新構建下載層。若要為可重現的構建固定特定版本，請直接將版本號碼作為 `CLAUDE_CODE_VERSION` 傳遞。當您需要比穩定通道更新的版本（例如[新推出的模型所需的版本](https://code.claude.com/docs/zh-TW/model-config.md)）時，在查詢 URL 中將 `stable` 替換為 `latest`。

## 為工作階段調整 CPU 和記憶體大小

為執行器執行的工作階段而不是執行器程序本身調整執行器的容器或主機大小。執行器本身輪詢工作、準備每個工作階段的簽出、執行您的[生命週期鉤子](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#lifecycle-hooks)，以及啟動和監督工作階段程序。負載來自工作階段：每個都是 Claude Code 程序加上它啟動的任何內容，例如構建、測試套件、套件安裝和 [MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md)。

對於一個工作階段，從以下值開始，表示為 Kubernetes 請求和限制或您的平台的等效項，並將它們視為起點而不是要求：

* **記憶體**：請求和限制各 4 GiB，滿足 Claude Code [系統要求](https://code.claude.com/docs/zh-TW/setup.md#system-requirements)中的 4 GB 最小值。保持兩者相等，以便調度器考慮容器的完整記憶體。當容器達到其記憶體限制時，核心會殺死其中的程序，這可能會結束工作階段中途。
* **CPU**：2 個 CPU 的請求和 4 個 CPU 的限制，因此工作階段可以在構建期間突發超過請求。核心在其 CPU 限制處限制容器，而不是殺死其中的程序，因此限制處的工作階段執行速度較慢但保持執行。

在 Kubernetes 容器規格中，使用以下 `resources` 塊設定這些起始值：

```yaml theme={null}
resources:
  requests:
    cpu: "2"
    memory: 4Gi
  limits:
    cpu: "4"
    memory: 4Gi
```

構建和測試通常是工作階段負載中最大和最可變的部分，因此執行您的儲存庫的代表性構建，測量其峰值 CPU 和記憶體，並提高任何在該峰值之上沒有為 Claude Code 程序留下空間的起始值。

執行器使用 `--capacity` 來限制它一次執行多少個工作階段。它不在它們之間分割 CPU 或記憶體，因此執行器上的工作階段共享容器的 CPU 和記憶體。為了避免一個工作階段的記憶體使用量結束其他工作階段，請每個執行器只執行一個工作階段，並為其設定[專屬的記憶體限制](#give-each-session-its-own-memory-limit)。

* **每個執行器一個工作階段**：給每個容器一個工作階段的值。在 `--capacity 1` 使用此調整大小，[強化部分](#harden-your-deployment)推薦，以及[按需執行器](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#on-demand-runners)，您在工作流程的 [`spawn-runner` 鉤子](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration#the-spawn-runner-hook)提交的工作負載上設定值，例如 Kubernetes Job 的 pod 範本。
* **每個執行器多個工作階段**：在 `--capacity` 高於 1 時，將一個工作階段的值乘以容量，因為最多那麼多工作階段可以在容器中同時執行。[Kubernetes](#kubernetes) 和 [Docker Compose](#docker-compose) 配方執行 `--capacity 4`，沒有 CPU 或記憶體限制，因此添加為您執行的容量調整大小的限制。
* **一台主機上多個執行器容器**：依執行器容量的總和調整主機大小，因為每個執行器只將自己的工作階段計入 `--capacity`：

  * **記憶體**：將一個工作階段的記憶體乘以該總和，再加上主機本身程序使用的記憶體
  * **CPU**：將一個工作階段的 CPU 請求乘以該總和。若要讓每個工作階段同時突發，請改為乘以其 CPU 限制。

  為每個執行器提供專屬的容器。在每個容器中使用[相同的 `--base-dir` 路徑](#keep-the-base-directory-and-capacity-identical-across-runners)，並放在沒有其他執行器容器掛載的儲存空間上，讓每個執行器都有[自己的工作目錄](#harden-your-deployment)。

### 為每個工作階段提供專屬的記憶體限制

為了避免記憶體耗盡時一個工作階段結束其他工作階段，請讓每個執行器以 `--capacity 1` 在專屬的記憶體限制下執行，並將該限制設為一個工作階段的記憶體：

* **在容器中**：每個容器執行一個執行器，並設定容器的記憶體限制，例如 Kubernetes 上的 `limits.memory`、Docker 上的 `--memory`，或 Compose 檔案中的 `mem_limit`。請讓各容器限制的總和低於主機的記憶體，因為當主機本身耗盡記憶體時，核心可能會終止主機上任何位置的程序。
* **在 systemd 下且不使用容器**：在執行器的 unit 上設定 `MemoryMax`，並且每台主機執行一個執行器，因為在同一檔案系統上[使用相同 `--base-dir`](#keep-the-base-directory-and-capacity-identical-across-runners) 的執行器會共享在那裡複製的儲存庫。例如，在 `--capacity 1` 且沒有 `checkout` hook 的情況下，它們在同一個儲存庫上的工作階段可能會同時在同一個簽出中工作。若要在一台主機上執行多個執行器，請為每個執行器提供一個容器。

當容器或 unit 達到其記憶體限制時，核心只會終止其中的程序。如果您將 `--capacity` 設定為高於 1，工作階段會共享同一個限制。當它們達到該限制時，核心不會依工作階段選擇要終止哪些程序，因此一個工作階段的記憶體使用量可能會結束其他工作階段。

在 Kubernetes 上，無論 kubelet 的 `singleProcessOOMKill` 設定為哪個值，都無法將工作階段分隔開來。您也無法在[包裝器指令碼](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#wrapper-scripts)中使用記憶體 `ulimit` 來限制工作階段的總記憶體。核心會將 `ulimit -v` 之類的值分別套用至每個程序。

### 在程序和執行緒限制下保留空間

若要決定程序和執行緒限制的大小，請測量一個工作階段所需的數量，並乘以共享該限制的工作階段數。當這些工作階段達到限制時，核心會拒絕新的程序和執行緒，因此其中任何一個工作階段中的命令、建置和測試都可能失敗。被拒絕的呼叫會傳回 `EAGAIN`，其標準訊息為 `Resource temporarily unavailable`。

假設一個工作階段的峰值為 300 個程序和執行緒，且有四個工作階段共享該限制。它們合計需要 1,200，而將限制設為 2,400 時，您就為需要兩倍數量的建置保留了空間。

#### 在何處設定各項限制

此表中的每項限制都同時計算執行緒和程序，而 `pids.max` 是存放 cgroup 限制的檔案：

| 限制 | 設定位置 | 共享者 |
| :- | :- | :- |
| Kubernetes 上的 `pids.max` | 執行執行器之節點的 kubelet 設定中的 `podPidsLimit`。您無法在 Pod 規格中設定它。 | 一個 Pod 的容器 |
| Docker 上的 `pids.max` | `--pids-limit`，或 Compose 檔案中的 `pids_limit` | 一個容器 |
| systemd 下的 `pids.max` | 執行器 unit 上的 `TasksMax` | 一個 unit |
| `ulimit -u` | 啟動執行器的 shell 或服務 | 主機上以執行器使用者 ID 執行的所有內容。對 root 不強制執行。 |

當您未設定 `TasksMax` 時，systemd 會套用 `DefaultTasksMax`，其預設值為 `kernel.pid_max`、`kernel.threads-max` 和根 cgroup 的 `pids.max` 三者中最低值的 15%。

#### 測量一個工作階段的峰值

若要取得您自己執行器的數值，請在其主機（在 Kubernetes 上即為節點）上測量一個工作階段：

**1. 單獨啟動一個執行器**

以 `--capacity 1` 啟動一個執行器，其容器或 systemd unit 中沒有其他內容，並且在其主機和環境中都是唯一的：

* **其主機**：使用沒有執行其他執行器的主機。這樣您就能在下一步中找出它的程序。
* **其環境**：讓它成為該環境中唯一的執行器，例如在您[為測試建立](https://code.claude.com/docs/zh-TW/self-hosted-environments-quickstart.md#set-up-manually)的環境中。工作階段會被路由到環境，而不是路由到執行器。

先不要啟動工作階段，因為您需要在建置開始之前取得下一步中的目錄。

**2. 找出執行器的 cgroup 目錄**

在主機上（而不是在容器內）找出執行器的程序 ID，例如使用 `ps`。讀取該 ID 的 `/proc/<pid>/cgroup`：

* **某一行包含 `:pids:`**：主機使用 cgroup v1，目錄為 `/sys/fs/cgroup/pids` 後接 `:pids:` 之後的文字
* **唯一的一行以 `0::` 開頭**：主機使用 cgroup v2，目錄為 `/sys/fs/cgroup` 後接 `0::` 之後的文字

**3. 執行代表性建置並記錄峰值**

讓一個工作階段執行代表性建置，並從執行器的 cgroup 目錄取得峰值：

* **目錄中有 `pids.peak`**：在建置完成後讀取該檔案
* **目錄中沒有 `pids.peak`**：在建置執行期間每秒讀取一次 `pids.current`，並保留最高值。兩次讀取之間的峰值不會被觀察到，因此請將該值視為偏低的估計值。

**4. 乘以共享該限制的工作階段數**

* **一個執行器的 Pod、容器或 unit**：將峰值乘以執行器的 `--capacity`
* **多個執行器共享的限制**：將峰值乘以它們容量的總和

然後加上共享該限制的其他任何內容的峰值，例如 Pod 中的另一個容器。

**5. 將限制設定為高於結果**

限制較高時，您可以為較重的建置保留空間；限制較低時，您可以更快阻止 fork bomb。

#### 檢查 `pids.max` 限制

* **檢查是否已達到 `pids.max`**：搜尋主機的核心日誌（例如使用 `dmesg`），尋找包含 `cgroup: fork rejected by pids controller in` 和 cgroup 路徑的行。核心只會在第一次拒絕該 cgroup 中的程序或執行緒時記錄此訊息，因此請搜尋整個日誌。
* **查看生效中的限制**：讀取執行器 cgroup 目錄及其上層每個目錄中的 `pids.max`。最低的值即為生效中的限制，而 `max` 表示該層級沒有限制。

## Kubernetes

執行器預設在連接埠 8080 上提供 `GET /healthz`，可使用 `--health-port` 配置，因此 Kubernetes 探針無需額外設定即可工作。端點在程序活著時返回 `200`，因此下面的探針檢測死程序，而不是卡住的程序；要捕捉停止輪詢的執行器，請在 [`/metrics`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#prometheus-metrics) 的 `last_poll_age_seconds` 系列上發出警報。下面的 Deployment 從 Kubernetes Secret 掛載環境祕密，將活躍度和就緒探針指向 `/healthz`，並設定 90 秒的終止寬限期。請參閱[關閉時序](#shutdown-timing)以了解為什麼寬限期很重要。

清單在執行器容器上設定沒有 CPU 或記憶體 `resources`。添加為您執行的容量調整大小的塊，如[為工作階段調整 CPU 和記憶體大小](#size-cpu-and-memory-for-sessions)所述。

```yaml theme={null}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: claude-runner
  namespace: claude-runners
spec:
  replicas: 3
  selector:
    matchLabels:
      app: claude-runner
  template:
    metadata:
      labels:
        app: claude-runner
        app.kubernetes.io/part-of: claude-code-self-hosted-runner
    spec:
      terminationGracePeriodSeconds: 90
      containers:
        - name: runner
          image: <your-registry>/claude-runner:latest
          args:
            - self-hosted-runner
            - --environment-secret-file
            - /etc/claude/environment-secret
            - --capacity
            - "4"
            - --base-dir
            - /workspace
          volumeMounts:
            - name: environment-secret
              mountPath: /etc/claude
              readOnly: true
          ports:
            - name: health
              containerPort: 8080
          readinessProbe:
            httpGet:
              path: /healthz
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /healthz
              port: 8080
            initialDelaySeconds: 30
            periodSeconds: 30
      volumes:
        - name: environment-secret
          secret:
            secretName: claude-runner-environment-secret
```

上面的 Deployment 位於 `claude-runners` 命名空間中。首先建立命名空間：

```bash theme={null}
kubectl create namespace claude-runners
```

從保存您在管理 UI 的[**複製環境金鑰**步驟](https://code.claude.com/docs/zh-TW/self-hosted-environments-quickstart.md#set-up-manually)中複製的值的本地檔案建立支持 Secret，以便祕密永遠不會出現在您的 shell 歷史記錄中。執行 `(umask 077 && cat > ./environment-secret)`，貼上祕密，按 Enter，然後按 Ctrl-D。然後建立 Secret 並刪除檔案：

```bash theme={null}
kubectl create secret generic claude-runner-environment-secret -n claude-runners --from-file=environment-secret=./environment-secret
```

## Docker Compose

下面的 Compose 服務會在執行器退出時重新啟動它，這涵蓋了崩潰和正常排空後的退出。Docker 重新啟動原則會使用其可寫層保持完整的方式重新啟動同一個容器，因此執行器會在重複使用的檔案系統上恢復，而不是[強化部署](#harden-your-deployment)建議的全新檔案系統；請使用此配方進行評估，而對於生產環境，請每次執行時重新建立容器，或使用執行協調器。

Docker 在容器不斷退出時，會在每次重新啟動之前等待更長的時間，直到達到上限，因此無法啟動的執行器在此配方下不會在緊密迴圈中持續重新啟動。[當執行器退出時](#when-the-runner-exits)描述了發生這種情況時要檢查的內容。

```yaml theme={null}
services:
  claude-runner:
    image: <your-registry>/claude-runner:latest
    command:
      - self-hosted-runner
      - --environment-secret-file
      - /run/secrets/environment-secret
      - --capacity
      - "4"
      - --base-dir
      - /workspace
    secrets:
      - environment-secret
    restart: always
    stop_grace_period: 90s

secrets:
  environment-secret:
    file: ./environment-secret
```

## 關閉時序

> [!NOTE]
>
> 這些時序適用於執行器。`claude self-hosted-runner orchestrator` 程序有其自己的時序：請參閱[調整 `--shutdown-drain-sec` 與協調器的停止逾時](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration#size-shutdown-drain-sec-and-the-supervisors-stop-timeout-for-the-orchestrator)。

在啟動時，每個執行器都會記錄它在 `SIGTERM` 之後乾淨地關閉其工作階段可能需要多長時間，例如在預設設定下為 `This runner needs up to 80s`。您的停止逾時是程序監督器在 `SIGTERM` 之後、終止執行器之前等待的時間。請將其設定為至少該記錄的時間：

* **Kubernetes**：`terminationGracePeriodSeconds`。Kubernetes 預設為 30 秒，因此若沒有此設定，它可能會在執行器完成之前就停止 pod。
* **Docker Compose**：`stop_grace_period`

收到 `SIGTERM` 時，執行器會停止接受新的工作階段。接著它會開始正常關閉（稱為清空），除非您設定 [`--defer-shutdown-max-min`](#defer-the-drain-past-the-first-signal) 來延遲它。清空包含三個步驟：

1. 執行器等待最多 [`--drain-wait-sec`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags) 秒（預設為 `0`），讓仍在執行的回合完成。
2. 它終止每個工作階段的程序樹，包括 Claude 仍在執行的任何命令，但不包括[在其 shell 命令結束後仍在執行的程序](#processes-a-stopped-session-leaves)。
3. 它執行 [`post-session` 生命週期 hook](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration#post-session)。

執行器在整個清空過程中持續輪詢 Anthropic。這會讓其工作階段保持指派給它，因此在您的 `post-session` hook 仍在儲存未提交的工作時，其他執行器不會接手這些工作階段。

記錄的時間是以下各值的總和：

* 步驟 1 的 `--drain-wait-sec`，預設為 0 秒
* 步驟 2 的 [`--session-stop-grace-sec`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags)，預設為 5 秒
* 步驟 3 的 [`--post-session-hook-timeout-sec`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags)，預設為 60 秒
* 固定 15 秒的餘裕
* 設定 [`--push-outcome-on-release`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags) 時再加 30 秒

在預設設定下，總計為 0 + 5 + 60 + 15 = 80 秒。較高的 `--capacity` 不會增加此時間，因為執行器會同時清空其所有工作階段。

如果您設定以下任一旗標，請預留更多時間：

* **使用 [`--retire-at`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags)**：在退休時間與主機停止時間之間保留足夠的時間，以涵蓋典型回合完成所需的時間、加上[執行器生命週期](https://code.claude.com/docs/zh-TW/self-hosted-environments#runner-lifecycle)所述的背景任務等待時間、再加上記錄的時間。請在每次啟動時計算退休時間，例如 `date +%s` 加上執行器的預期生命週期。
* **使用 [`--defer-shutdown-max-min`](#defer-the-drain-past-the-first-signal)**：停止逾時還必須涵蓋您設定的分鐘數，以及清空開始前的額外等待時間（預設設定下為 75 秒）。[延遲清空超過第一個信號](#defer-the-drain-past-the-first-signal)會說明這兩者。執行器也會在啟動時記錄這個較長的時間。

### 在重新啟動前讓執行中的回合完成

若要在滾動重新啟動前讓執行中的回合完成，請設定 `--drain-wait-sec`，並將停止逾時提高至至少該等待時間加 80 秒。在預設等待時間 `0` 下，重新啟動會中斷任何仍在執行的回合，而工作階段會在另一個執行器上恢復，但不包含其[未推送的工作](#resumed-sessions-lose-unpushed-work)。

* **`--drain-wait-sec`**：大約設為您想讓其完成的回合與背景任務所需的時間。這是上限：若它們提前完成，等待就會提早結束。
* **您的停止逾時**：Kubernetes 中的 `terminationGracePeriodSeconds`、Docker Compose 中的 `stop_grace_period`。例如，使用 `--drain-wait-sec 120` 時，請將 [Kubernetes](#kubernetes) 或 [Docker Compose](#docker-compose) 配方中的 `90` 替換為 `200`。
* **如果您變更了其他關閉設定**：80 秒是針對預設設定。請以您的旗標啟動一個執行器，並至少使用其啟動行 `This runner needs up to` 中的數字，該數字已包含等待時間。若設定了 [`--defer-shutdown-max-min`](#defer-the-drain-past-the-first-signal)，請使用下一個啟動行中 `Size the stop timeout to at least` 之後較大的數字。[關閉時序](#shutdown-timing)列出了會增加這些數字的項目。

> [!WARNING]
>
> 如果停止逾時在等待期間用完，主機會在工作仍在執行時終止執行器。其工作階段不會執行 `post-session` hook。執行器也不會取消註冊，因此控制平面可能需要幾分鐘，有時甚至更久，才會重新排隊這些工作階段。

### 在重新啟動前發布狀態訊息

在會中斷工作階段的重新啟動之前，請讓[擁有者](https://code.claude.com/docs/zh-TW/cloud-environments.md#organization-shared-environments)從 [**Cloud environments** 管理頁面](https://claude.ai/admin-settings/cloud-environments)在該環境上發布狀態訊息。在 [claude.ai/code](https://claude.ai/code)，成員會在該環境中的工作階段裡看到此訊息。請讓擁有者在發布時設定到期時間，或在執行器恢復運作後移除該訊息。

### 延遲清空超過第一個信號

如果您想要重新啟動的執行器繼續服務它持有的工作階段最多 `n` 分鐘，而不是在第一個信號上清空它們，請設定 [`--defer-shutdown-max-min <n>`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags)。在第一個 `SIGTERM` 或 `SIGINT` 上，執行器停止接受新工作並繼續服務它持有的工作階段。它保持輪詢，以便控制平面不會重新排隊這些工作階段。需要 Claude Code v2.1.238 或更新版本。

#### 第一個信號後執行器持有的工作階段會發生什麼

在信號後的前兩個階段中，執行器釋放工作階段，釋放的工作階段在其使用者發送下一條訊息時在新執行器上恢復。從第一個信號開始計數，執行器通過三個階段移動：

* **在前 `n` 分鐘內**：執行器正常服務其工作階段並繼續強制執行 `--startup-timeout-min` 和 `--kill-session-after-min`。如果您也設定 [`--release-idle-session-min`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags)，執行器會釋放任何使用者已閒置該長時間的工作階段，除非您[保留該工作階段](#keep-an-idle-session-while-its-processes-run)。若未設定此旗標，閒置工作階段會保留在執行器上。
* **當 `n` 分鐘用完時**：執行器釋放它仍然持有的每個工作階段，閒置或不閒置。執行器等待中途轉向的轉向結束，並為該轉向的背景任務再等待最多 60 秒，然後釋放該工作階段。
* **當發佈後寬限期用完時**：執行器清空它仍然持有的任何工作階段，控制平面立即將每個清空的工作階段重新排隊到另一個執行器。發佈後寬限期在 `n` 分鐘用完時開始，預設值為 75 秒。如果您將 `--drain-wait-sec` 設定為 60 秒以上，發佈後寬限期改為 `--drain-wait-sec` 加 15 秒。

在任何階段，執行器在不持有任何工作階段時立即以 0 退出。第二個信號縮短階段：執行器立即清空，就像在沒有 `--defer-shutdown-max-min` 的第一個信號上一樣。一旦清空進行中，下一個信號強制退出執行器。這無論第二個信號還是發佈後寬限期用完啟動清空。

#### 調整停止超時大小

給您的主機停止逾時至少三個部分的總和：您設定的 `n` 分鐘、釋放後寬限期，以及[關閉時序](#shutdown-timing)所述的清空。在預設設定下，釋放後寬限期為 75 秒，清空最多需要 80 秒，因此請預留 `n` 分鐘加 155 秒。每當設定 `--defer-shutdown-max-min` 時，執行器都會在啟動時列印此總和。

如果停止逾時在執行器完成之前用完，它仍然持有的工作階段不會執行 `post-session` hook。執行器不會取消註冊，因此控制平面可能需要幾分鐘，有時甚至更久，才會重新排隊這些工作階段。如果您無法給停止逾時該總和，請保留 `--defer-shutdown-max-min` 不設定，讓執行器改為在第一個信號時清空。

### 什麼到達執行中的 post-session 鉤子

`post-session` 鉤子和 Claude 工作階段子項各自在自己的 POSIX 程序組中執行，與執行器的分開，因此停止機制以不同方式到達它們：

* **執行器已在清空時的 `SIGTERM`**：立即強制退出執行器，跳過清空的任何剩餘部分。若沒有 [`--defer-shutdown-max-min`](#defer-the-drain-past-the-first-signal)，這就是執行器收到的第二個 `SIGTERM`。沒有任何信號會送達執行中途的 `post-session` hook，因此在由 init 程序收養孤兒程序的裸主機上，它會自行完成，但不受監督：其逾時預算不再適用，寫入已關閉的日誌管道可能會以 `SIGPIPE` 終止它，因此需要在該處撐過強制退出的 hook 應將其自己的輸出重新導向到檔案。在此頁面的容器配方中，執行器是容器的 PID 1，其退出會結束容器；而在 systemd 的預設 `KillMode=control-group` 下，cgroup 範圍的終止也會到達 hook，如**Cgroup 範圍的終止**項目所述；在這兩種情況下，請將強制退出視為對 hook 致命，並改為依賴寬限期。
* **程序組範圍的信號**，例如包裝器指令碼中的 `kill -- -<pid>`、shell 工作控制或組範圍的看門狗：到達執行器和中途 `checkout` 鉤子子程序，該子程序故意保持組附加，但不是中途執行的 `post-session` 鉤子或工作階段子項。
* **Cgroup 範圍的終止**，例如 systemd 的預設 `KillMode=control-group`，或 `terminationGracePeriodSeconds` 到期時 Kubernetes 傳遞到整個容器的 `SIGKILL`：會到達所有內容，包括 hook。程序群組隔離無法防範這些情況，這就是為什麼寬限期必須涵蓋整個清空過程。
* **鉤子自己的超時**：當鉤子超過 `--post-session-hook-timeout-sec` 時，執行器向鉤子的整個程序組發送 `SIGTERM`，然後 2 秒後發送 `SIGKILL`，因此鉤子分叉的工作者（例如 tar、rsync 或 git）與包裝器 shell 一起終止，而不是作為孤兒存活。執行器的監督在鉤子的 stdio 關閉後結束：重定向其自己的輸出到檔案並超過 `SIGTERM` 階段的工作者超出執行器的範圍。

當清空開始時，以及在強制退出時，執行器記錄仍在執行多少 `post-session` 鉤子，因此您可以區分安靜清空和中途快照的清空。

## 在執行器之間保持基本目錄和容量相同

如果執行器在工作階段中途死亡，伺服器重新排隊工作階段，環境中的另一個執行器拾取它。該執行器從其自己的 `--base-dir` 和 `--capacity` 派生簽出路徑：`--capacity 1` 直接在 `--base-dir` 下簽出，`--capacity` 高於 `1` 改用每個工作階段的 worktree。當同一環境中的執行器對任一旗標使用不同的值時，恢復的工作階段的工作目錄會更改，agent 之前記錄的絕對路徑（在編輯、工具呼叫或其自己的筆記中）指向不再存在的位置。

在環境中的每個執行器上使用相同的 `--base-dir` 和 `--capacity`，並且不要使用每個主機的值，例如執行個體 ID 或主機名。請如 [Kubernetes](#kubernetes) 和 [Docker Compose](#docker-compose) 範例所示，明確傳遞這兩個旗標，使兩個值都不依賴預設值。

基本目錄預設為 `/workspace`，除了 [`--base-dir` 參考行](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags)記錄的例外。執行器需要對其的寫入存取。在啟動時，在註冊之前，執行器建立目錄並確認它可以寫入它，當它無法時以 `cannot create or write to base directory` 退出。以 root 身份啟動的執行器自己建立預設 `/workspace`。對於非 root 執行器，在啟動執行器之前建立目錄並給執行器的使用者所有權，或將 `--base-dir` 指向該使用者已擁有的目錄。

## 重複使用預熱簽出

對於大型儲存庫，複製可能主導工作階段啟動。要跳過冷複製，請自行在執行器保存其自身複製的路徑上提供一個複製。在沒有 [`checkout` hook](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration#checkout) 的情況下，執行器在 `<base-dir>/<repo-owner>/<repo>` 為每個儲存庫保持一個規範複製，並在工作階段之間重複使用它：

* **在 `--capacity 1` 時**：執行器提取請求的 ref、分離 `HEAD` 並硬重置為它，當變化不多時幾乎是瞬間的。
* **在 `--capacity` 大於一時**：執行器提取到該複製中，然後為每個工作階段從中簽出一個單獨的 worktree。預熱複製可節省下載，但無法節省簽出。

在映像中或在持久卷上提供複製：

* **在映像中複製**：在該路徑將複製構建到您的執行器映像中。每個新容器然後以預熱複製啟動，而不重複使用磁碟。
* **在持久卷上複製**：在您使用 [`--lock-to-account`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags) 預鎖定到一個使用者帳戶的執行器上，將 `--base-dir` 指向持久卷，因此磁碟只服務該帳戶。預鎖定的執行器永遠不會拾取 Claude Tag 頻道工作階段，因此此選項不適用於服務它們的執行器。

重複使用路徑做什麼和不保證什麼：

* **複製深度**：建置複製時不要使用 `--depth`，可搭配或不搭配 `--single-branch`。執行器在提取到具有 `origin` 遠端的複製時永遠不會傳遞 `--depth`，即使您設定了 [`CLAUDE_RUNNER_FETCH_DEPTH`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#environment-variable-only-settings) 也是如此。使用完整複製時，每個工作階段只會下載複製所缺少的提交。使用淺複製時，若工作階段所在的分支是在複製最舊的提交之前分叉出來的，該工作階段會下載該分支的完整歷史記錄。
* **追蹤的變化重置，未追蹤的檔案持續**：在 `--capacity 1` 時，每個工作階段從硬重置開始，該重置擦除前一個工作階段的追蹤修改，但執行器永遠不執行 `git clean`，因此鎖定所有者的早期工作階段的未追蹤檔案保留在樹中。
* **每工作階段目錄也持續**：在簽出旁邊，執行器在 `<base-dir>/_sessions/` 下為它執行的每個工作階段建立每工作階段項目。工作階段的 Claude 設定目錄保存對話記錄的本地副本。在它旁邊是工作階段的上傳檔案，當工作階段有任何時。工作階段目錄也坐在那裡：它在工作階段執行時保存任何每工作階段 worktrees 和 `checkout` 鉤子簽出，並保持 Claude 在其中寫入的任何其他內容。

  預設情況下，執行器在工作階段結束時將這些留在原地，因此在超越執行器程序的磁碟上它們會累積。每個工作階段都以執行器自己的使用者身份執行，因此該磁碟服務的任何後續工作階段都可以讀取它們。如果您保持持久 `--base-dir`，請為該增長調整卷的大小。相同的適用於任何在相同檔案系統上重新啟動執行器的設定，包括 [Docker Compose 配方](#docker-compose)。
* **使用 `--remove-session-state`，每工作階段目錄不持續**：使用 [`--remove-session-state`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags) 啟動執行器，以便在工作階段結束時刪除每個工作階段的每工作階段目錄。刪除是盡力而為：當執行器在其清理執行之前被殺死時，目錄保留。規範複製和工作階段在主機上其他地方寫入的檔案，例如臨時目錄，無論如何都保留。
* **使用 Git 代理伺服器，重置變成簽出**：使用 [`--use-anthropic-git-proxy`](#use-the-anthropic-git-proxy)，執行器在每個工作階段之前清理複製的 `.git/`。它保留物件儲存區和淺狀態，並刪除索引。沒有索引，每個工作階段都從完整的工作樹簽出開始，而不是幾乎瞬間的重置。執行器仍會提取到現有複製中，而不是重新複製儲存庫。子模組預熱在代理伺服器下不受支援。
* **使用 Git 代理伺服器時，`reftable` 預熱會遺失其 refs**：當執行器在每個工作階段之前清理 `.git/` 時，它會保留 `.git/refs/` 並移除 `.git/reftable/` 目錄。以 Git 的 `reftable` ref 格式預熱的複製會因此遺失其 refs，因此請改以 Git 的 `files` ref 格式預熱複製。
* **長複製不需要解決方法**：執行器使用 120 秒無進度看門狗和 30 分鐘硬上限限制每個 Git 操作，而不是平面超時，因此保持報告進度的慢冷複製完成。

### 確認執行器使用您的複製

若要確認執行器使用您的複製，請使用 [`--log-level debug`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags) 啟動執行器，並在該儲存庫上啟動工作階段。執行器會在日誌中記錄 `Prefetched repo found at` 以及複製的路徑。如果它改為記錄 `No prefetched repo, fresh init at`，表示它在該行所列的路徑上找不到可用的複製。請檢查您的複製是否位於該路徑、由執行器的使用者擁有，並具有名為 `origin` 的遠端。

如果執行器找到您的複製，但工作階段仍然啟動緩慢，請檢查該複製是否為淺複製。

## 固定版本

根據預設，每個工作階段的子程序會執行執行器自己的二進位檔案，且執行器會在它生成的工作階段內關閉自動更新。在此預設下，每個工作階段都會執行您在主機上安裝或建置到映像中的版本。主機級更新在執行器下次啟動時生效。

選擇您的工作階段執行哪個版本，以及何時變更：

* **在固定版本之前**：針對工作階段使用的每個模型，檢查[模型所需的 Claude Code 版本](https://code.claude.com/docs/zh-TW/model-config.md#available-models)。如果某個模型需要比工作階段執行的版本更新的版本，伺服器會以 [Claude Code 不支援此模型](https://code.claude.com/docs/zh-TW/errors.md#claude-code-does-not-support-this-model) 拒絕該模型的請求。
* **將群保持在一個版本上**：使用固定版本構建映像，或在裸主機上安裝特定版本並[禁用自動更新](https://code.claude.com/docs/zh-TW/setup.md#disable-auto-updates)
* **升級固定機群**：閱讀從您目前版本到要安裝版本之間的 [changelog](https://code.claude.com/docs/en/changelog.md) 項目，然後安裝較新版本或重新建置映像，並重新啟動執行器
* **升級隨需執行器**：閱讀從您目前版本到要安裝版本之間的 [changelog](https://code.claude.com/docs/en/changelog.md) 項目，然後變更您的 [`spawn-runner` hook](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration#the-spawn-runner-hook) 所啟動的映像。每個新的執行器都會取得新版本。已在執行中的執行器，包括由 [`--min-idle`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#orchestrator-cli-flags) 啟動的待命執行器，會保留其版本直到結束。請勿重新啟動它，因為其工作指令只能使用一次。
* **如果工作階段啟動不同的二進位檔案**：如果您使用 [`--exec-path`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags) 或 [`command` hook](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration#command) 來啟動執行器自身以外的 Claude Code 二進位檔案，工作階段會執行該二進位檔案的版本。更新執行器時，請一併更新該二進位檔案。
* **外掛程式**：外掛程式市場也不自動更新；在執行器的環境中設定 `FORCE_AUTOUPDATE_PLUGINS=1` 以讓外掛程式自動更新，同時二進位檔案保持固定

## 擴展群

您的協調器決定何時添加或移除執行器。由於[每個執行器一個所有者鎖](https://code.claude.com/docs/zh-TW/self-hosted-environments#runner-lifecycle)，最小副本計數是您期望同時活躍的使用者和 Claude Tag 代理的數量；`--capacity` 控制一個所有者的工作階段內的並行性，而不是跨所有者。

有兩種擴展方法可用：

* **固定群**：執行靜態執行器副本集並在每個執行器服務的 [Prometheus 指標](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference.md#prometheus-metrics)上擴展
* **按需執行器**：執行 `claude self-hosted-runner orchestrator` 子命令，它輪詢 Anthropic 以查找沒有可用執行器排隊的工作階段，並調用您的 `spawn-runner` 鉤子為每個工作階段啟動一個。請參閱[按需執行器](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#on-demand-runners)。

### 在固定群上釋放閒置工作階段

如果在每個執行器都在線的情況下，固定群上的工作階段仍持續排隊，原因可能是閒置工作階段。預設情況下，工作階段在其回合結束後仍會保留其槽位，而其執行器會持續鎖定於該工作階段的[所有者](https://code.claude.com/docs/zh-TW/self-hosted-environments#key-concepts)。其他所有者的工作階段無法使用該執行器的空閒槽位。如果您團隊的[雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md)在每次執行時都會啟動新的工作階段，其閒置工作階段可能會佔滿所有槽位。

若要檢查，請讀取每個執行器的 [Prometheus 指標](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference.md#prometheus-metrics)中的 `claude_code_self_hosted_runner_session_idle_seconds`。執行器持有的每個工作階段都有其各自的序列：工作階段忙碌時為 `0`，否則為其進入閒置狀態以來的秒數。選擇您允許的閒置時間：要長於人們在任務進行中的暫停時間，並且短到足以讓每次執行在排程任務的下一次執行開始之前被釋放。將這些序列與該時間進行比較。

* **序列高於該時間，例如 30 分鐘的 `1800`**：閒置工作階段佔用了這些槽位，因此請設定 `--release-idle-session-min`
* **每個序列都低於該時間**：沒有任何工作階段閒置那麼久。請添加執行器，或針對[從不進入閒置狀態的工作階段](#some-sessions-don’t-count-as-idle)設定 [`--kill-session-after-min`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags)。
* **沒有序列的執行器**：沒有任何工作階段持有它。請參閱[疑難排解](#troubleshooting)下的 **Sessions stay queued**。
* **指標沒有回應的執行器**：其程序可能已經結束。請參閱[當執行器結束時](#when-the-runner-exits)下的 **An environment that looks healthy**。

若要釋放閒置工作階段，請使用 [`--release-idle-session-min`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags) 並搭配以分鐘為單位的該時間來啟動每個執行器，例如 `--release-idle-session-min 30`。執行器隨後會釋放任何閒置達該時間的工作階段，無論是由排程任務還是由人員啟動的，除非您[為其留下仍在執行的程序而保留它](#keep-an-idle-session-while-its-processes-run)。

* **未推送的工作**：已釋放的工作階段會在其下一則訊息時恢復，但不包含其尚未推送的工作。若要保留其提交，請參閱[恢復的工作階段會遺失未推送的工作](#resumed-sessions-lose-unpushed-work)。
* **執行器結束**：釋放其最後一個工作階段的執行器會開始[正常結束](#when-the-runner-exits)。請讓您的監督程式在全新的檔案系統上重新啟動它，如[強化您的部署](#harden-your-deployment)所述。
* **從不進入閒置狀態的工作階段**：也請設定 [`--kill-session-after-min`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags)，因為[某些工作階段不被視為閒置](#some-sessions-don’t-count-as-idle)

### 在程序執行期間保留閒置工作階段

若要保留閒置工作階段，直到其在您主機上留下的程序（例如 `nohup` 工作）完成為止，請使用 [`--hold-idle-file`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags) 啟動執行器，並持續從主機 touch 該檔案。需要 Claude Code v2.1.311 或更新版本。

這些步驟假設主機上的執行器以非 root 身分執行。如果您的執行器以 `root` 身分執行，其工作階段可以自行 touch 該檔案，因此請先以專用使用者身分執行它。

**1. 為檔案選擇路徑**

選擇一個本機一般檔案，例如 `/var/lib/claude-hold/hold-idle`，並將其放在工作階段無法寫入的目錄中（包括上層目錄），使工作階段無法寫入該檔案。執行器及其工作階段共用同一個作業系統使用者，因此請先建立該目錄，由另一個使用者（例如 `root`）擁有，模式為 `755`。

**2. 啟動執行器**

從您的 shell 使用 `--hold-idle-file`、`--release-idle-session-min` 和 [`--max-hold-min`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags) 啟動執行器；`--max-hold-min` 是保留的上限，從工作階段進入閒置狀態時開始計算。若未設定，上限為一天。請將其設定為高於 `--release-idle-session-min`，否則不會保留任何工作階段。請依照[快速入門](https://code.claude.com/docs/zh-TW/self-hosted-environments-quickstart.md#set-up-manually)中的說明替換 `<writable-dir>`。此範例會在 30 分鐘後釋放閒置工作階段，並在被保留的工作階段進入閒置狀態後最多 4 小時釋放它：

```bash theme={null}
claude self-hosted-runner \
  --environment-secret-file /etc/claude/environment-secret \
  --base-dir '<writable-dir>' \
  --release-idle-session-min 30 \
  --hold-idle-file /var/lib/claude-hold/hold-idle \
  --max-hold-min 240
```

**3. 在程序執行期間 touch 該檔案**

在程序執行期間，以該目錄擁有者的身分從主機 `touch` 該檔案，頻率須高於每三分鐘一次。第一次 `touch` 會建立該檔案。例如，將以下這行加入 `root` 的 crontab：

```text theme={null}
* * * * * pgrep -x nightly-build > /dev/null && touch /var/lib/claude-hold/hold-idle
```

這行每分鐘執行一次，並在任何名為 `nightly-build` 的程序執行期間 touch 該檔案，因此啟動此類程序的工作階段會持續被保留，直到達到上限為止。請將 `pgrep` 檢查替換為您主機用來找出工作階段所留下執行中程序的任何方式。

當這些程序結束時，檢查必須停止比對成功，否則該執行器上的每個閒置工作階段都會被保留直到達到上限。

**4. 確認保留**

在程序執行期間，檢查該檔案的修改時間是否一直保持在三分鐘以內。當工作階段的閒置時間用盡時，請在執行器的日誌中尋找 `idle release held`。如果沒有出現此行，請讀取執行器在啟動時記錄的 `watchdog config` 行中的 `leftover-hold=`，它會顯示檔案和上限，或說明為何沒有保留任何工作階段。

在最後一次 `touch` 的三分鐘後，保留即會結束。再過大約一分鐘內，日誌會顯示 `idle release no longer held`，執行器隨即釋放該工作階段。

即使檔案持續變更，保留仍可能結束，例如以下情況：

* **超過上限**：`--max-hold-min` 用盡。若要保留更久，請提高此值
* **強制釋放**：您設定了 [`--retire-at`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags)、[`--defer-shutdown-max-min`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags) 或 [`--kill-session-after-min`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags)，且該限制已到。若要保留更久，請設定更晚的限制

## 已知問題和限制

以下是此版本中的限制，其中存在解決方法。

### 連接器流量離開您的網路

Anthropic 從其自己的基礎設施而不是從您的執行器呼叫連接器工具。連接器工具是 claude.ai 連接器，例如 GitHub、Slack 和 Linear。當 Claude 在自託管工作階段中使用連接器時，該流量通過 `api.anthropic.com` 而不是源自您的網路邊界內。

要將連接器保留在自託管工作階段之外，使用 [`allowedMcpServers` 和 `deniedMcpServers` 原則設定](https://code.claude.com/docs/zh-TW/managed-mcp#policy-based-control-with-allowlists-and-denylists)進行篩選。Claude Code 將這些設定應用於 Anthropic 傳遞的連接器以及您從執行器主機播種的伺服器和使用者添加的伺服器，因此如果您為其他伺服器部署允許列表，Claude Code 也會阻止傳遞的連接器。要在 URL 型允許列表旁邊保持連接器可用，添加與傳遞連接器的 Anthropic 代理路徑相符的項目：

* `https://api.anthropic.com/v2/ccr-sessions/*`
* `https://api.anthropic.com/v1/code/sessions/*`
* `https://api.anthropic.com/v1/code/mcp/*`

如果工具流量必須保留在您的網路內，改為在執行器映像上執行等效工具作為本地 MCP 伺服器。請參閱 [MCP 伺服器](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#mcp-servers)。

### 某些工作階段不計為閒置

持有持續執行中的背景任務的工作階段不計為閒置，因此 `--release-idle-session-min` 不會釋放該工作階段的插槽。等待從執行中工具呼叫內部請求的核准的工作階段也不計為閒置。請將 `--kill-session-after-min` 與其一起設定作為硬性後擋。

`--kill-session-after-min` 是失控工作階段的後擋。在 v2.1.260 或更新版本上的執行器上，達到限制的工作階段不會立即終止。執行器給它一個寬限窗口，預設 15 分鐘，您可以使用 [`SELF_HOSTED_RUNNER_MAX_LIFETIME_GRACE_MS`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#environment-variable-only-settings) 更改：

* 如果工作階段等待其使用者，執行器會釋放它。如果其轉向已結束並且它僅持有背景任務，執行器會等待最多 60 秒讓這些任務完成，然後釋放它。當其使用者發送下一條訊息時，工作階段會恢復。
* 如果轉向仍在執行，執行器等待轉向完成，或工作階段下一次等待其使用者，然後釋放它。
* 如果工作階段在寬限窗口結束時仍在執行器上，執行器終止它，任何執行中轉向的工作都會丟失。等待從執行中工具呼叫內部請求的批准的轉向是工作階段超過窗口的一種方式。

釋放的工作階段從新複製恢復，因此它未推送的工作無論如何都消失了；請參閱[恢復的工作階段遺失未推送的工作](#resumed-sessions-lose-unpushed-work)。在 v2.1.260 之前，執行器在限制處終止每個工作階段，最多等待寬限窗口以完成執行中的回合。

將該旗標設定為高於您預期的最長工作階段時間，例如 `--kill-session-after-min 480` 為 8 小時。要從進入閒置的對話中釋放插槽，改用 `--release-idle-session-min`。

### 恢復的工作階段遺失未推送的工作

在新的執行器上恢復的工作階段會遺失其尚未推送的工作，因為該執行器會從其起始分支再次複製儲存庫。

若要保留已提交的工作，請在環境中的每個執行器上設定 [`--push-outcome-on-release`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags)。具有此旗標的執行器會在釋放之前盡力推送工作階段的結果分支，恢復的工作階段便會從這些提交開始。沒有此旗標的執行器會從其起始分支恢復工作階段。推送會使用執行器主機本身的 git 憑證，包括在使用 [Anthropic 管理的 git](#use-the-anthropic-git-proxy) 的執行器上。

> [!WARNING]
>
> 設定此旗標之前，請限制誰可以推送到來源遠端上的 `claude/*` refs。在恢復時，執行器會提取先前推送的分支，而不驗證是誰推送的。

即使已設定此旗標，仍請以其他方式保存以下工作：

* **未提交的變更**：這些仍會遺失。請參閱[提示工作階段推送其工作](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#prompt-sessions-to-push-their-work)。
* **透過 [`checkout` 生命週期 hook](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration#checkout) 簽出的儲存庫**：這些不會被推送。請從 [`post-session` hook](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration#post-session) 建立它們的快照。
* **有人封存或刪除的工作階段中的提交，或有人從工作階段選單釋放其執行器的工作階段中的提交**：不要依賴此旗標的推送。若要保存它們，請從 [`post-session` hook](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration#post-session) 將 `HEAD` 推送到救援分支。該處的範例只會在建立快照提交之後才推送，因此請讓您的版本在沒有任何未提交變更時也進行推送。

### 其他限制

* **因執行器遺失而中斷的命令可能會再次執行**：當工作階段在另一個執行器上恢復時，Claude 會看到被中斷的工具呼叫，其結果表示該呼叫的結果未知。
* **工作階段中途新增的儲存庫可能無法複製**：Claude 透過 HTTPS 使用 `git clone` 複製它。在未使用 [`--use-anthropic-git-proxy`](#use-the-anthropic-git-proxy) 的執行器上，如果主機上沒有任何項目能讀取該儲存庫，複製會因 git 身分驗證錯誤而失敗。在可行的情況下，請在建立工作階段時選擇工作階段需要的每個儲存庫。
  * **工作階段恢復時**：[`checkout` hook](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration#checkout) 也會針對新增的儲存庫執行，且 [`CLAUDE_RUNNER_REPO_REF`](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration#checkout) 為空，因此請讓您的 hook 能處理此情況。
* **某些連接器不出現在自託管工作階段中**：您在 claude.ai Settings 中尚未連接的連接器不在自託管工作階段中列出，工作階段不會提示您連接它。首先在 Settings 中連接它，然後啟動新工作階段。將連接器添加到已執行的工作階段也不會使其工具可用於 Claude；啟動新工作階段以拾取新添加的連接器。

### 報告問題

對於自託管環境的問題，請聯繫您的 Anthropic 帳戶團隊。

## 疑難排解

如需引導式診斷，請在 runner 主機上執行 doctor 子命令。doctor 子命令會啟動一個互動式 Claude Code 工作階段，並附上 runner 的日誌與狀態。請先在該主機上以 `claude auth login` 登入，讓工作階段能查詢您的環境、其 runner 以及其排隊中的工作階段。若未登入，例如主機以 API 金鑰進行身分驗證時，它只能使用本機健康狀態端點、指標以及 runner 的日誌，而且只有在您以 `--log-file` 啟動 runner 時才會讀取該日誌。

```bash theme={null}
claude self-hosted-runner doctor
```

常見問題：

* **Runner 未出現在環境中**：請確認主機能透過 HTTPS 連線至 `api.anthropic.com`，且環境密鑰為最新。身分驗證失敗時，runner 會記錄 `[runner:fatal]` 並附上拒絕原因。
* **Runner 在啟動時以 `cannot create or write to base directory` 結束**：runner 無法建立或寫入 `--base-dir`，其預設值為 `/workspace`。請修正該目錄的擁有權，或將 `--base-dir` 指向可寫入的路徑，如[讓所有 runner 的基礎目錄與容量保持一致](#keep-the-base-directory-and-capacity-identical-across-runners)中所述。如果 runner 改為記錄指出基礎目錄檢查逾時的 `[runner:fatal]`，則該目錄位於停擺的 NFS 或 CSI 掛載上。請檢查掛載的健康狀態，而非權限。Runner 會在開啟 `--log-file` 之前將這兩種啟動失敗輸出至 stderr，因此請在終端機或您平台的容器日誌中尋找，而非在日誌檔中。在 v2.1.225 之前，runner 不會在啟動時檢查基礎目錄，這種設定錯誤會改為在接收工作階段後導致工作階段失敗。
* **Runner 在啟動時以 `RegisterRunner failed:` 及 TLS 憑證錯誤結束**：錯誤可能是 `self signed certificate in certificate chain` 等。Runner 不信任其收到之憑證背後的憑證授權單位（CA），這種情況會發生在執行 TLS 檢查的代理伺服器後方。請在 runner 的環境中將 [`NODE_EXTRA_CA_CERTS`](https://code.claude.com/docs/zh-TW/network-config#custom-ca-certificates) 設為包含代理伺服器根 CA 的 PEM 檔案。

  您不需要為工作階段再次設定，工作階段會繼承它。Git 不會讀取它：若要透過該代理伺服器進行 clone，也請設定 [`GIT_SSL_CAINFO`](#trust-a-private-certificate-authority-with-anthropic-managed-git)。
* **您的啟動腳本輸出包含 `Resource temporarily unavailable` 的寫入錯誤並結束**：您的腳本與其所啟動的 `claude self-hosted-runner` 或 [orchestrator](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#on-demand-runners) 程序共用 stdout 或 stderr，而該程序已將此共用的管道或 socket 切換為非阻塞模式。當管道已滿時，您腳本的寫入會以此作業系統錯誤失敗，而不是等待，且在 `set -e` 下腳本會結束。

  若要消除此錯誤，請將 runner 或 orchestrator 的輸出導向您腳本的使用者能夠建立的檔案。在啟動它的命令後附加 `>> "$HOME/claude-runner.log" 2>&1`，並置於任何將其移至背景執行的 `&` 之前，並依[快速入門](https://code.claude.com/docs/zh-TW/self-hosted-environments-quickstart.md#set-up-manually)中的說明取代 `<writable-dir>`：

  ```bash theme={null}
  claude self-hosted-runner --environment-secret-file /etc/claude/environment-secret --base-dir '<writable-dir>' >> "$HOME/claude-runner.log" 2>&1
  ```

  您腳本本身的輸出仍會送往原本的位置，而 runner 寫入 stdout 與 stderr 的內容（包括其啟動錯誤）則會送往該檔案。請使用此 shell 重新導向，而非僅使用 [`--log-file`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags)，後者會在 runner 持續寫入 stdout 與 stderr 的同時，將日誌鏡像寫入檔案。如果您已傳入 `--log-file`，也請保留它，因為重新導向不會改變該檔案所接收的內容。
* **Orchestrator 記錄 `poll failed:` 及 TLS 憑證錯誤並持續重試**：orchestrator 不信任其收到之憑證背後的 CA，這種情況會發生在執行 TLS 檢查的代理伺服器後方。請在 orchestrator 的環境中將 [`NODE_EXTRA_CA_CERTS`](https://code.claude.com/docs/zh-TW/network-config#custom-ca-certificates) 設為包含代理伺服器根 CA 的 PEM 檔案。也請為您的 `spawn-runner` hook 所啟動的 runner 設定它。

  例如，某行可能以 `poll failed: self signed certificate in certificate chain — retrying in 1s` 結尾，冒號與破折號之間是 TLS 函式庫的訊息。若要確認修正是否生效，請檢查 orchestrator 的 [`/healthz`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#health-endpoint) 回應本文中 `connected` 是否為 `true`。
* **工作階段持續排隊中**：每個線上 runner 可能都已鎖定給不同的擁有者。請檢查每個 runner 的 `claude_code_self_hosted_runner_locked_account` [指標](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference.md#prometheus-metrics)或其 `[runner:health]` 日誌行的 `locked_account` 欄位，以查看由誰持有。兩者都只有在 runner 取得帶有 `act.email` claim 的工作階段 token 後才會顯示擁有者的電子郵件，而 Claude Tag agent 的工作階段從不帶有此 claim。沒有此 claim 時，runner 不會輸出 `locked_account` 序列，並記錄 `locked_account=yes`，這只能告訴您 runner 已鎖定，但無法得知鎖定給哪個擁有者。請增加副本，或等待現有 runner 排空並重新啟動。如果環境使用隨需 runner，請改為檢查 orchestrator；請參閱[隨需 runner](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#on-demand-runners)。
* **工作階段在接收後立即失敗**：在 claude.ai/code 中開啟該工作階段以查看錯誤。如果錯誤顯示 git 無法進行身分驗證，請檢查 runner 的 [git 憑證](#configure-git)。在以 `--use-anthropic-git-proxy` 啟動的 runner 上，請參閱[當工作階段無法在使用 git 代理伺服器的 runner 上啟動時](#when-anthropic-doesnt-serve-a-session)。

  無法寫入的基礎目錄會讓 runner 在啟動時就停止，而不是讓工作階段失敗。請參閱本清單中的 **Runner 在啟動時以 `cannot create or write to base directory` 結束**項目。
* **工作階段已被接收，但 Claude 從未回覆其第一則訊息**：如果您的 runner 透過代理伺服器連線至 `api.anthropic.com`，請設定代理伺服器在工作階段的 `/worker/events/stream` 回應抵達時即將其傳遞出去。提高 runner 的逾時並無幫助。若要在 runner 的日誌中確認原因，請參閱[工作階段已被接收，但 Claude 從未回覆其第一則訊息](#when-a-sessions-first-message-is-never-answered)。
* **工作階段無法在設定了 `--use-anthropic-git-proxy` 的 runner 上啟動**：請在 runner 的日誌中尋找 `access denied by the git proxy`，或是指名包含 `/git_proxy/` 之 `api.anthropic.com` 位址的 git 錯誤。若要判斷 Anthropic 是否已服務該工作階段並修正原因，請參閱[當工作階段無法在使用 git 代理伺服器的 runner 上啟動時](#when-anthropic-doesnt-serve-a-session)。
* **工作階段無法透過需要身分驗證的輸出代理伺服器連線至網路**：當您以 [`--proxy-authorization-command` 或 `--proxy-authorization-file`](#authenticate-to-an-egress-proxy) 設定的來源失敗、在 30 秒後逾時，或產生空值時，runner 會對該連線回應 `502 Bad Gateway` 並記錄原因。Runner 會在該日誌中遮蔽（redact）命令的 stderr 內容，且絕不會記錄標頭值。使用 `--proxy-authorization-command` 時，請在主機上自行執行該命令，確認它會在 stdout 上輸出完整的標頭值。如果 runner 改為在啟動時以 `could not start the proxy-authorization listener` 結束，表示它無法開啟其 loopback 監聽器。
* **Runner 記錄包含 `rejecting the malformed poll response` 的 `Poll failed` 行**：runner 收到的工作輪詢回應本文並非佇列預期的 JSON。其中一個原因是攔截式代理伺服器或強制入口網頁以其自己的頁面作出回應。如果 runner 透過代理伺服器連線，請設定代理伺服器，讓來自 `api.anthropic.com` 的回應原封不動地通過。

  Runner 會拒絕該格式錯誤的回應，將其計入 `claude_code_self_hosted_runner_poll_errors_total` [指標](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference.md#prometheus-metrics)的 `transport` 類別，並依照[工作階段生命週期](https://code.claude.com/docs/zh-TW/self-hosted-environments#session-lifecycle)中所述的輪詢失敗排程重試。Runner 會繼續服務其進行中的工作階段。在 v2.1.246 之前，runner 會將這類回應讀作空的工作佇列，這可能會結束其進行中的工作階段或使其結束。
* **工作階段以 `no longer exists on the remote` 或 `couldn't find remote ref` 失敗**：runner 會將 git 的 `couldn't find remote ref` 解讀為分支已刪除。但該分支可能仍然存在。請在您的 git 主機上以訊息中的確切名稱尋找該分支，然後檢查每個符合的原因：

  * **分支已不存在**：請依訊息的要求還原分支。
  * **分支存在，且您不是 runner 的管理員**：將完整訊息傳送給 runner 的管理員，並告知該分支存在。
  * **分支存在，且 runner 有 `checkout` hook**：您 hook 中的 git 命令可能會在 hook 以非零值結束之前，將 `couldn't find remote ref` 輸出至 stderr。請找出該命令，並修正其請求的 ref 或其擷取來源的遠端。Runner 會以 [`CLAUDE_RUNNER_REPO_REF`](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration#checkout) 將工作階段所要求的修訂版本傳遞給您的 hook。
  * **分支存在，且 runner 沒有 `checkout` hook**：runner 會自行擷取分支。如果有 [`--git-host-rewrite`](#rewrite-git-urls-for-private-networks) 套用於該儲存庫，請確認其改寫後的目標主機上有同名的分支，若沒有，請將分支推送至該處。
  * **分支存在，且 runner 早於 v2.1.301**：請依[固定版本](#pin-the-version)中所述升級 runner，讓其他失敗能顯示其自身的錯誤。在 v2.1.301 之前，錯誤輸出中包含 `couldn't find remote ref` 的其他失敗也會被回報為分支已刪除。

  Runner 升級或原因修正後，請重試該工作階段或啟動新的工作階段。如果以上檢查都找不到原因，請[回報問題](#report-an-issue)。

  對於工作階段推送結果的來源，已刪除的分支會使工作階段失敗。對於工作階段只讀取的 git 來源，runner 會略過該來源並繼續處理其餘來源。當略過會使工作階段完全沒有儲存庫時，runner 會使工作階段失敗。在 v2.1.228 之前，這類工作階段會在空目錄中啟動。
* **Claude Tag 有時不會在 Slack 中張貼其回覆**：回覆提醒是[控制平面所提供的 hook](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#how-each-session’s-config-is-assembled)。請以 `claude --version` 確認 runner 為 Claude Code v2.1.229 或更新版本，因為較舊的 runner 會忽略所提供的 hook；確認 `python3 --version` 能在 runner 映像中成功執行，因為這些 hook 會執行 `python3`；並確認沒有任何設定檔關閉 hook，無論是 `managed-settings.json`、runner 使用者的 `~/.claude/settings.json`，或儲存庫的 `.claude/settings.json` 或 `.claude/settings.local.json` 中的 `disableAllHooks`，或是受管設定中的 `allowManagedHooksOnly` 或涵蓋 hook 的 [`strictPluginOnlyCustomization`](https://code.claude.com/docs/zh-TW/settings-reference#strictpluginonlycustomization)。
* **工作階段啟動時缺少其中一個儲存庫**：在沒有 [`checkout` hook](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration#checkout) 的 runner 上，git 主機可能會拒絕 runner 對工作階段只讀取之儲存庫的存取檢查。Runner 接著會略過該儲存庫，記錄一行指名該拒絕的 `[runner:warn] could not access context source`，並以其餘儲存庫啟動工作階段。

  使用其自身的 git 憑證時，若主機回應找不到儲存庫、git 找不到該主機的憑證，或身分驗證失敗，runner 可以略過該儲存庫。

  使用 [`--use-anthropic-git-proxy`](#use-the-anthropic-git-proxy) 時，當 git 代理伺服器以 `access denied by the git proxy` 拒絕某個儲存庫，runner 會略過它。此時日誌行會顯示 `blocked by the git proxy`。如需要檢查的原因，請參閱[當工作階段無法在使用 git 代理伺服器的 runner 上啟動時](#when-anthropic-doesnt-serve-a-session)中的 `remote: access denied by the git proxy` 情況。

  網路故障、逾時或任何其他 HTTP `403` 仍會使工作階段啟動失敗，對工作階段推送結果之儲存庫的拒絕也是如此。對於略過會使其完全沒有儲存庫的工作階段，runner 仍會使其失敗。

  每次工作階段在 runner 上啟動時，存取檢查都會再次執行，因此一旦 runner 的 git 身分擁有讀取權限，下次啟動時就會 clone 該儲存庫。在 v2.1.274 之前，這些拒絕都會使工作階段啟動失敗。
* **日誌顯示 `could not read context source`**：此行與 `could not access context source` 不同，表示 git 主機持續回應 HTTP `429`，或您安裝為 `git` 的包裝程式持續以 `75` 結束。Runner 已略過該儲存庫。若要重試，請啟動新的工作階段。每次此工作階段在 runner 上啟動時，runner 也會再次嘗試該儲存庫。

  在沒有 `checkout` hook 的情況下，runner 可以略過工作階段只讀取的儲存庫，除非該儲存庫是工作階段的儲存庫中的第一個。在 v2.1.311 之前，工作階段啟動會失敗。
* **工作階段啟動失敗並顯示 `This runner couldn't read`**：runner 以其 [git 憑證](#configure-git)向 git 主機請求儲存庫，並收到找不到的回應。該儲存庫不存在，或這些憑證無法存取該儲存庫。
  * **如果您管理該 runner**：為其 git 憑證授予該儲存庫的讀取權限，然後啟動新的工作階段。
  * **如果您是啟動該工作階段的人**：如果儲存庫不存在，請以正確的儲存庫啟動新的工作階段。如果 runner 無法存取該儲存庫，請要求 runner 的管理員授予存取權，然後啟動新的工作階段。
* **工作階段需要數分鐘才能啟動或恢復**：其中一個原因是全新的 clone。在每個 runner 都以空磁碟啟動且沒有 [`checkout` hook](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration#checkout) 的叢集上，runner 會在啟動 Claude Code 之前重新 clone 工作階段的儲存庫。在空磁碟上恢復的工作階段也會再次等待相同的 clone。

  若要略過全新的 clone，請提供[預熱的 checkout](#reuse-a-pre-warmed-checkout)。如果您已提供，請[確認 runner 有使用它](#confirm-that-the-runner-uses-your-clone)。若由 runner 自行進行 clone 並在一個工作階段後結束，請將 [`CLAUDE_RUNNER_FETCH_DEPTH`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#environment-variable-only-settings) 從預設的 50 個提交調低，以擷取較少的歷史記錄。

  如果您使用 hook，它會取代 runner 的 clone 執行，因此請改為檢查您的 hook 所做的事。請觀察 `claude_code_self_hosted_runner_session_init_duration_seconds` [指標](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference.md#prometheus-metrics)，以查看啟動所需的時間。
* **回合因 401 失敗**：當回合以來自 Anthropic API 的 401 或 403 結束時，runner 會從 Anthropic 取得新的 [`CLAUDE_CODE_OAUTH_TOKEN`](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration#wrapper-scripts) 並傳遞給工作階段。失敗的回合不會重試。此 token 的效期很短，runner 會透過工作階段的 stdin 輪換它。

  當取得失敗時，runner 會記錄一行 `inference_token refresh failed`，說明何時會重試，並在工作階段執行期間持續重試。

  如果每個呼叫在工作階段開始約 30 分鐘後都開始失敗，很可能是包裝腳本切斷了工作階段的 stdin，導致 token 輪換無法送達；請參閱[保持 stdin 與檔案描述元 3 連接](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#keep-stdin-and-file-descriptor-3-attached)。

  在 v2.1.274 之前，runner 在幾次嘗試後就會停止重試失敗的取得，並等待下一次排定的取得。失敗的回合不會觸發取得，因此在下一次排定的取得之前，每個回合都會以 401 失敗。
* **回合在 claude.ai/code 中以 `This model needs a newer version of Claude Code` 失敗**：您的 runner 用來啟動工作階段的 Claude Code 版本比工作階段的模型所要求的版本舊，因此 API [拒絕了該請求](https://code.claude.com/docs/zh-TW/errors.md#claude-code-does-not-support-this-model)。請將 runner 升級至訊息要求的版本或更新版本，如[固定版本](#pin-the-version)中所述。在此之前，使用者可以在工作階段中選擇其他模型。
* **Pod 在排空過程中被終止**：請將 `terminationGracePeriodSeconds` 提高至至少 runner 在啟動時記錄的值。請參閱[關閉時序](#shutdown-timing)。
* **Runner 記錄以 `was paused or too slow` 結尾的 `[runner:log]` 行**：runner 仍持續執行，不需要重新啟動。在該行所指名的 stdout 或 stderr 串流再次被讀取之前，runner 會捨棄該串流中除最新 256 KiB 以外的所有行。如果您傳入了 [`--log-file`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags)，請在該處尋找被捨棄的行。
* **Runner 記錄 `Nobody can read this process's stdout anymore`**：原本讀取 runner stdout 的對象已不存在，因此 runner 在其剩餘的執行期間會停止寫入該處，並繼續執行。只要 stderr 仍開啟，此行以及 runner 後續的狀態行（包括 `[runner:fatal]` 行）都會送往 stderr，因此請在該處閱讀。

日誌初始化後，runner 會將其生命週期日誌（包括 `[runner:fatal]` 行）寫入 stdout，並將偵錯輸出寫入 stderr，全部都是純文字行而非 JSON。上述疑難排解項目中所述的基礎目錄失敗會在此之前輸出至 stderr。請使用 `--log-file`（它也能讓 `self-hosted-runner doctor` 追蹤這些輸出）或您平台的日誌收集功能擷取兩個串流。

每個工作階段的子程序會寫入獨立的偵錯日誌。失敗時，runner 會在 claude.ai/code 中將該日誌的結尾與工作階段一併呈現。除非您以 [`--remove-session-state`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags) 啟動 runner，否則它也會將失敗工作階段的日誌保留在磁碟上，並在 runner 日誌中輸出其路徑。

### 當 runner 結束時

請勿重新啟動[隨需 runner](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#on-demand-runners)，因為其工作單是一次性的。啟動後隨即結束的 runner，與因其他原因結束的 runner，需要不同的處理方式。

* **正常結束**：runner 已完成其工作階段並排空、達到其退役時間，或被告知停止。請重新啟動它，讓環境再次擁有容量。[Runner 生命週期](https://code.claude.com/docs/zh-TW/self-hosted-environments#runner-lifecycle)說明了這些結束情況。
* **啟動失敗**：runner 無法以所提供的設定或主機啟動，因此在啟動後幾秒內就結束，而且每次重新啟動時都以相同方式結束。更快地重新啟動並無幫助。需要有人閱讀其輸出並修正原因。
* **失去聯繫**：無法連線至 Anthropic 的時間超過其[租約](https://code.claude.com/docs/zh-TW/self-hosted-environments#session-lifecycle)的 runner（例如在其主機休眠期間）可能會從環境中移除。被移除的 runner 重新連線時會結束。其日誌可能會顯示包含 `runner record gone server-side` 的 `[runner:fatal]` 行，或在較長的中斷後顯示 [`poll auth failed`](https://code.claude.com/docs/zh-TW/self-hosted-environments-quickstart#set-up-an-environment-and-runner)。Runner 不會自行重新註冊，因此請重新啟動它。

請設定您的監管程式在 runner 每次結束時重新啟動它、在 runner 持續於啟動後隨即結束時拉長重新啟動之間的等待時間，並在這種情況持續發生時通知相關人員。

在正式環境中，請讓您的監管程式在全新的磁碟上（於新的容器或 VM 中）重新啟動 runner，如[強化您的部署](#harden-your-deployment)中所建議。

#### 辨識啟動失敗

當 runner 無法啟動時，它會輸出一行說明原因，然後結束。對於大多數原因，該行包含 `[runner:fatal]`。對於某些原因，該行改以 `error:` 開頭，包括 runner 無法解析其旗標、無法讀取環境密鑰，或無法建立或寫入基礎目錄的情況。接下來的一行會指向 `--help`。

大多數日誌行以時間戳記和 `[self-hosted-runner]` 開頭，下方範例省略了這部分。例如，以 Anthropic git 代理伺服器及大於一的容量啟動的 runner 會輸出類似這樣的一行：

```text theme={null}
[runner:fatal] --use-anthropic-git-proxy requires --capacity 1 (the proxy URL is per-session and linked worktrees share origin). Omit --use-anthropic-git-proxy or set --capacity 1.
```

請在 runner 的標準輸出與標準錯誤、您平台的容器日誌，或您以 [`--log-file`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags) 設定的檔案中尋找該行。Runner 會在開啟日誌檔之前輸出 `error:` 行，因此請在終端機或您的容器日誌中尋找，如[疑難排解](#troubleshooting)中所述。

以下各點也有助於解讀啟動失敗：

* **完全沒有任何一行**：被主機終止的 runner 兩種行都不會輸出。如果輸出結束時既沒有 `[runner:fatal]` 行也沒有 `error:` 行，請檢查主機或您的 orchestrator 是否停止了該程序，例如因超出記憶體限制。
* **退出碼**：runner 不會為每次啟動都重複出現的錯誤保留專屬的退出碼。對於設定錯誤（例如不支援的旗標組合）以及可能自行排除的失敗（例如在 runner 自身的重試期間 API 一直無法連線），它都以相同的代碼結束。請根據 runner 結束的速度來決定是否拉長等待時間，並閱讀 runner 的輸出以了解原因。
* **看似健康的環境**：有些啟動步驟會在 runner 向您的環境註冊之後才執行，例如 [`--configure-git`](#let-the-runner-configure-git) 以及 Anthropic git 代理伺服器的憑證設定。如果其中某個步驟失敗，在程序結束後的幾分鐘內，環境仍可能繼續列出該 runner，而 **Cloud environments** 頁面可能顯示 **Healthy**，但實際上沒有 runner 在接收工作。如果工作階段在看似健康的環境中持續排隊，請檢查您的監管程式是否正在重新啟動 runner。

#### 以逐漸拉長的等待時間重新啟動

如何取得逐漸拉長的等待時間取決於您的監管程式。

* **Kubernetes**：本頁的 [Deployment](#kubernetes) 不需要修改。容器結束後，kubelet 預設會在重新啟動容器之前等待，且每次重新啟動時等待時間都會拉長，直到上限。容器在未結束的情況下執行一段時間後，等待時間會重新計算。

  當容器只執行短暫時間就正常結束時，kubelet 也會套用相同的等待時間。因此經常排空的 runner 也可能顯示 `CrashLoopBackOff` 狀態，所以在斷定 runner 無法啟動之前，請先閱讀輸出。下方命令會從 Deployment 的其中一個 pod 讀取上一次執行的輸出：

  ```bash theme={null}
  kubectl logs --previous -n claude-runners deploy/claude-runner
  ```

  當上一次執行是啟動失敗時，`[runner:fatal]` 或 `error:` 行會出現在輸出的最後幾行之中。若要讀取其他 pod 的上一次執行，請以該 pod 的名稱取代 `deploy/claude-runner`。
* **Docker 與 Docker Compose**：本頁的 [Compose 範例](#docker-compose)不需要修改。使用 `restart: always` 時，Docker 會在每次重新啟動持續結束的容器之前等待更長的時間，直到上限。請在下方命令中以容器名稱取代 `<container>`，此命令會讀取 Docker 重新啟動該容器的次數：

  ```bash theme={null}
  docker inspect --format '{{.RestartCount}}' <container>
  ```

  此命令會輸出一個數字。持續攀升的數字表示 Docker 一直在重新啟動 runner。
* **systemd unit**：systemd 預設在每次重新啟動前等待相同的 `RestartSec`，且不會拉長，因此設有 `Restart=always` 的 unit 每次都會以相同的間隔重新啟動無法啟動的 runner。當啟動速度快到達到 unit 的啟動速率限制（預設為 10 秒內五次啟動）時，systemd 會停止重新啟動該 unit。該 unit 會保持停止狀態，直到有人再次啟動它，而 systemd 會在速率限制的間隔過後或執行 `systemctl reset-failed` 之後允許這麼做。由於 `RestartSec` 適用於每次重新啟動，較長的值也會延遲正常結束後的重新啟動。請選擇能兼顧兩者的值，並針對 unit 的重新啟動次數設定警示。
* **shell 迴圈或您自己的監管程式**：請自行套用相同的規則。從五秒的等待時間開始。每次執行在一分鐘內結束後，將下次重新啟動的等待時間加倍，最多五分鐘。執行持續一分鐘或以上後，恢復為五秒。

#### 檢查 runner 持續結束的原因

當 runner 已連續數次在啟動後隨即結束時，請先停止並檢查以下各項，再重新啟動它。

* **最後一行 `[runner:fatal]` 或 `error:`**：它會說明 runner 停止的原因。[疑難排解](#troubleshooting)列出了常見原因。
* **旗標組合**：[Anthropic git 代理伺服器](#use-the-anthropic-git-proxy)需要 `--capacity 1`。本頁的範例使用較高的容量，因此當您將代理伺服器加入其中之一時，請降低容量。
* **服務環境可存取的內容**：如果 runner 手動啟動正常，但在您的監管程式下失敗，請比較使用者、家目錄、`PATH` 以及記憶體限制。`--configure-git` 與 Anthropic git 代理伺服器需要 `PATH` 上有 git，以及可寫入的 `~/.gitconfig`。
* **環境密鑰**：如果您已撤銷密鑰或輸入錯誤，runner 會輸出包含 `RegisterRunner auth failed` 的一行。
* **環境的 Activity 分頁**：開啟環境並選取 **Activity**。如果該處不斷出現新的 runner，且沒有任何 runner 接收工作，表示您的監管程式正在重新啟動 runner。

如需在 runner 主機上進行引導式診斷，請執行 [doctor 子命令](#troubleshooting)。

### 工作階段已被接收，但 Claude 從未回覆其第一則訊息

如果 runner 接收了工作階段，但 Claude 從未回覆第一則訊息，而您的 runner 透過代理伺服器連線至 `api.anthropic.com`，原因可能出在代理伺服器。Anthropic 會透過一個保持開啟的串流回應將訊息傳送給工作階段。如果您的代理伺服器緩衝了該回應，或在傳遞任何內容之前就將其結束，第一則訊息就永遠不會抵達。工作階段的其他請求仍會成功。

若要修正此問題，請變更代理伺服器處理此請求的方式：

```text theme={null}
GET https://api.anthropic.com/v1/code/sessions/<session-id>/worker/events/stream
```

* **不要緩衝回應**：在回應抵達時即將其傳遞出去。其內容類型為 `text/event-stream`。
* **讓回應保持開啟**：它最多可保持開啟一小時。如果代理伺服器設有閒置逾時，請將其設定為遠高於 15 秒，因為 Anthropic 預設至少每隔這段時間就會傳送一次 keep-alive。

接著啟動新的工作階段，並確認 Claude 有回覆。提高 runner 的逾時並無幫助：您只會在 runner 停止工作階段之前等待更久。

#### 在 runner 的日誌中確認原因

這些步驟適用於 Claude Code v2.1.287 或更新版本、使用預設 `--log-level info` 的 runner。較舊的 runner 會較晚記錄這些行，或完全不記錄。

1. 等待 [`--startup-timeout-min`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags) 經過，預設為 15 分鐘。Runner 接著會停止工作階段，並記錄一行包含 `no child output for` 且以 `— releasing` 結尾的內容。
2. 在 runner 的日誌中搜尋 `SDKStartup: SSE`。這些行出現在 `finished: interrupted` 行之後，位於步驟 1 那一行之後的幾行。大多數沒有時間戳記，因此日誌收集器可能會將它們顯示在其他位置。
3. 在下表中找到該行：

| 日誌行包含 | 處理方式 |
| :- | :- |
| `SSE connect failed (no response in 30s)` 或 `SSE liveness timeout` | 請確認代理伺服器有轉送該請求、在回應的標頭與資料抵達時即將其傳遞出去，且不會中斷連線 |
| `SSE connect failed (HTTP` 及狀態碼 | 請檢查代理伺服器本身的日誌。如果是代理伺服器自行回應了該請求，請讓該請求通過代理伺服器。 |
| `SSE connect failed (` 及任何其他文字 | 括號中的文字即為錯誤。請在代理伺服器本身的日誌中尋找同一個連線。 |
| `SSE stream ended by server`，一再出現 | 請檢查代理伺服器對長時間回應的時間限制。單獨一行這樣的內容屬於正常。 |
| `SSE reconnected after` | 請在其後尋找其他行之一。這一行並不表示有任何內容送達工作階段。 |

如果日誌中沒有上述任何一行，或代理伺服器的日誌顯示沒有任何問題，請[回報問題](#report-an-issue)。

#### 阻止工作階段再次嘗試

工作階段會保留該訊息為待處理狀態，而能服務該工作階段擁有者的 runner 會再次接收該工作階段。在您變更代理伺服器之前，工作階段每次都會以相同方式等待。若要停止這種情況，請在 claude.ai/code 中封存該工作階段。

## 下一步

* [自訂工作階段](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md)：包裝器指令碼、生命週期鉤子、按需執行器、MCP 伺服器和權限
* [端到端測試](https://code.claude.com/docs/zh-TW/self-hosted-environments-testing.md)：在推廣新執行器映像之前從 CI 驗證它
* [參考](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference.md)：每個 CLI 旗標、環境變數和指標

<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/self-hosted-environments | lastmod: 2026-10-30 | section: Configuration / Environments -->
> 來源：https://code.claude.com/docs/zh-TW/self-hosted-environments（官方 zh-TW，lastmod 2026-10-30）｜分類：Configuration › Environments｜EN 摘要：Run Claude Code cloud sessions on infrastructure you control: set up a self-hosted environment, deploy runners, and route sessions to your own compute.

# 自託管環境

> 在您控制的基礎設施上執行 Claude Code 雲端工作階段：設定自託管環境、部署執行器，並將工作階段路由到您自己的運算資源。

> [!NOTE]
>
> 自託管環境在 Team 和 Enterprise 方案上處於公開測試版，預設為關閉。請參閱[可用性和限制](#availability-and-limitations)以了解啟用路徑和排除項目。

自託管環境在您的組織運營的基礎設施上執行 Claude Code 雲端工作階段。[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)是指在開發者機器以外的任何地方執行的工作階段。開發者可以從 claude.ai、行動和桌面應用程式、終端機（使用 [`claude --cloud`](https://code.claude.com/docs/zh-TW/claude-code-on-the-web#from-terminal-to-cloud)）以及[雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md)啟動這些工作階段。預設情況下，雲端工作階段在 Anthropic 的基礎設施上執行。

在自託管環境中，這些相同的工作階段在您的網路內執行。除了[可用性和限制](#availability-and-limitations)中的差異以及部署頁面的[已知問題](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#known-issues-and-limitations)之外，開發者體驗在其他方面完全相同。

* 如果您的團隊不使用雲端工作階段，這裡沒有任何需要設定的內容：終端機或 IDE 中的工作階段始終在開發者自己的機器上執行
* 如果您想在自己的常駐機器上執行 Claude Code 並從其他裝置驅動它，請使用 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md)，該功能也可在 Pro、Max 和 Ultra 方案上使用
* 當您準備好設定時，請直接前往[快速入門](https://code.claude.com/docs/zh-TW/self-hosted-environments-quickstart.md)；如果您想先檢查安全狀況，請從[部署到生產環境](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md)開始

若要了解自託管的運作方式以及何時選擇它，請閱讀[自託管環境的運作方式](#how-self-hosted-environments-work)和[為何選擇自託管](#why-self-host)。

## 自託管環境的工作原理

自託管有三個部分：

* **環境**：雲端工作階段可以被發送到的命名目的地。您的組織在 claude.ai 管理設定中建立環境，每個環境都會分組一組執行器。
* **執行器**：在您網路內的主機上執行的程式。執行器執行工作階段；其概念與自託管 CI 執行器相同。
* **工作階段**：開發者啟動的一個 Claude Code 任務。

當開發者啟動雲端工作階段時，工作階段啟動 UI 會顯示一個環境選擇器，列出 Anthropic 託管的環境以及您的組織建立的任何環境。如果他們選擇您的環境，Anthropic 的控制平面會將工作階段放在您環境的佇列上，執行器會認領它、複製開發者選擇的儲存庫，並在您的主機上啟動 Claude Code 程序來執行它。執行器使用您設定的憑證向您的 git 主機進行身份驗證；[設定 git](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#configure-git) 涵蓋了各種選項。工作階段從您網路內部到達您的內部服務，當 git 主機是內部的時，也以相同方式到達您的 git 主機；到 Anthropic 的流量（佇列輪詢、工作階段的事件流，以及預設情況下的模型推理）是對 `api.anthropic.com` 的出站 HTTPS，工作階段可以到達的其他主機的簡短清單列於[網路需求](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#network-requirements)中。Anthropic 永遠不會連接到您的網路。

![自託管環境的架構圖：您的網路邊界包含一個執行器、其內部的兩個 Claude Code 工作階段程序和您的 git 主機，外部有 api.anthropic.com 持有佇列、工作階段流和推理。執行器輪詢佇列並到達 git 主機，每個工作階段程序開啟自己的流、推理和 git 連接，每個連接都是從您的網路出站，沒有入站。](https://mintcdn.com/claude-code/Y0sJ2uDoOVbOVZrQ/images/self-hosted-network-paths.svg?fit=max\&auto=format\&n=Y0sJ2uDoOVbOVZrQ\&q=85\&s=8056103fc1c5564c7f0ef219d260b99d)

圖表中的兩個 Claude Code 方塊是工作階段程序：一個執行器同時執行兩個工作階段，達到其設定的容量。執行器一次為一個[擁有者](#key-concepts)服務，並在認領其第一個工作階段時鎖定到該擁有者，因此簽出的程式碼永遠不會在擁有者之間混合；[執行器生命週期](#runner-lifecycle)涵蓋了該規則。

您可以自己啟動執行器並保持它們執行，或執行[自動擴展協調器](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#on-demand-runners)，這是您託管的第二個程序，它會在工作階段排入佇列時啟動執行器。無論哪種方式，您都只需設定一次環境，它就會出現在每個支援的使用介面上的選擇器中。

## 可用性和限制

在規劃推出之前，請檢查這些內容：

* **方案**：Team 和 Enterprise 組織的公開測試版。自託管環境預設為關閉；[擁有者](https://code.claude.com/docs/zh-TW/cloud-environments.md#organization-shared-environments)在[**雲端環境**管理頁面](https://claude.ai/admin-settings/cloud-environments)上開啟**允許自託管環境**，這需要為組織啟用[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)。
* **零資料保留和 HIPAA**：對於啟用了[零資料保留](https://code.claude.com/docs/zh-TW/zero-data-retention.md)或套用了 [HIPAA 設定](https://code.claude.com/docs/zh-TW/hipaa-setup.md)的組織不可用。
* **模型推理**：除非您將執行器設定為[將模型請求傳送至 Amazon Bedrock 或 Google Cloud 的 Agent Platform](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#send-model-requests-to-bedrock-or-agent-platform)，否則工作階段會使用 Anthropic API。在這兩種情況下，工作階段內容都會傳送至 Anthropic。在以此方式設定的執行器上，[伺服器管理的設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)和來自 claude.ai 的組織政策不會套用到工作階段。
* **使用介面**：從 [claude.ai/code](https://claude.ai/code)、行動和桌面應用程式、[雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md)和終端機啟動的工作階段，使用 [`claude --cloud`](https://code.claude.com/docs/zh-TW/claude-code-on-the-web#from-terminal-to-cloud) 或 [`--environment` 分派](https://code.claude.com/docs/zh-TW/self-hosted-environments-testing#run-the-test-loop)，可以在自託管環境中執行。[Claude Tag](https://claude.com/docs/claude-tag/overview) 工作階段也可以在其中執行，但 Claude 在這些工作階段中還無法使用[存取套件](https://claude.com/docs/claude-tag/concepts/glossary#access-bundle)。[Claude Security](https://code.claude.com/docs/zh-TW/claude-security.md) 和 [Code Review](https://code.claude.com/docs/zh-TW/code-review.md) 工作階段還沒有路由到它們。對這兩個使用介面的支援將單獨跟進。
* **儲存庫**：工作階段從 GitHub 或 GitHub Enterprise Server 簽出儲存庫。使用 `--environment` 分派啟動的工作階段也可以使用其他 Git 主機：
  * **GitHub**：請參閱 [GitHub 身分驗證選項](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#github-authentication-options)。
  * **GitHub Enterprise Server**：請參閱其[網路需求](https://code.claude.com/docs/zh-TW/github-enterprise-server.md#network-requirements)。
  * **其他 Git 主機**：請參閱[使用 `--environment` 啟動工作階段的需求](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy#start-a-session-on-a-repository-outside-github)。
* **計費**：自託管環境中的工作階段消耗您組織的 Claude Code 使用量，與 Anthropic 託管環境中的工作階段相同。

## 為什麼要自託管

大多數團隊最好由 Anthropic 託管的環境服務，這些環境不需要基礎設施來執行或維護。自託管適用於網路、工具或合規要求要求在其控制的基礎設施上保持工作階段執行的團隊。如果是這樣，請為其帶來的操作所有權做好計劃：您構建和維護執行器映像、操作艦隊並控制其網路。

作為交換，自託管為您提供網路存取、自訂工具和合規控制：

* **網路存取**：工作階段在您的網路內執行，可以到達內部服務、資料庫和登錄，而無需將它們暴露給公網
* **自訂工具**：在執行器映像中預先安裝編譯器、SDK 和內部 CLI，以便每個工作階段都準備好構建
* **合規**：儲存庫簽出和建置產物保留在您控制的基礎設施上。工作階段內容仍然會發送到 `api.anthropic.com`。

## 環境、執行器和工作階段

環境在 claude.ai 管理設定中的**雲端環境**頁面上進行管理；執行器是您在自己的基礎設施上啟動和管理的程序。

### 關鍵概念

這些術語在整個自託管頁面中出現：

| 術語 | 它是什麼 |
| :- | :- |
| 環境 | 您的執行器的命名分組，在 claude.ai 設定中建立。工作階段被路由到環境，而不是單個執行器。 |
| 環境祕密 | 執行器用來向環境進行身份驗證和註冊的單一共享認證。在環境建立時顯示一次，在管理 UI 中標記為**環境金鑰**。 |
| 執行器 | 您部署的長期程序。執行器向環境註冊、接收執行器令牌並輪詢工作階段。 |
| 工作階段 | 一個 Claude Code 任務，從 claude.ai、行動應用程式或其他 Anthropic 使用介面（例如排程任務或 agent）啟動。每個工作階段作為執行器生成的子 Claude Code 程序執行。 |

在 API 欄位、令牌聲明和度量名稱中，環境顯示為 `pool`，環境 ID 是 `pool_id`。[參考](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference.md)映射了兩種拼寫，包括已棄用的 `pool` 標誌名稱。

執行器一次為一個擁有者服務。執行器認領的第一個工作階段將執行器鎖定到該工作階段的擁有者，執行器隨後只為該擁有者執行工作階段，達到設定的容量。擁有者是誰取決於工作階段如何啟動：

* **使用者啟動的工作階段**：擁有者是該使用者的帳戶。
* **Claude Tag 頻道工作階段**：Claude 執行它們時沒有附加使用者帳戶，因此擁有者是啟動工作階段的 [Claude Tag 代理](https://claude.com/docs/claude-tag/concepts/glossary#agent-identity)。該代理啟動的每個頻道工作階段都有相同的擁有者，無論誰發送了 Slack 訊息，因此當您以 `--capacity` 大於 1 或正 `--drain-grace-sec` 執行它時，鎖定到它的執行器為不同人員啟動的工作階段服務。

因此，最小艦隊大小是您預期同時活躍的擁有者數量，計算使用者和 Claude Tag 代理。

### 工作階段生命週期

當開發者啟動工作階段並選擇您的環境時，Anthropic 的控制平面將工作階段放在環境的佇列上。從那裡：

1. 具有可用容量的執行器認領工作階段並持有其租約。
2. 執行器將儲存庫複製到其工作目錄並生成子 Claude Code 程序。
3. 子程序在執行器保持輪詢時透過 HTTPS 流回事件；每次輪詢都會刷新租約並充當心跳。
4. 如果執行器停止輪詢，其租約會在約 60 秒後失效。之後伺服器可能需要幾分鐘，有時甚至更久，才會將工作階段重新佇列給另一個執行器。

執行器為每個輪詢請求提供 10 秒。當請求超時、丟失或執行器無法解析的回應時，執行器會繼續為其活躍工作階段服務，並在一兩秒後重試，而不是等待下一個排程的輪詢。例如，用自己的頁面回答輪詢的攔截代理會產生執行器無法解析的回應。每次另一個請求以其中一種方式失敗時，執行器會將下一次重試前的間隔加倍，最多 20 秒，並在租約即將過期時縮短間隔。

### 執行器生命週期

執行器認領的第一個工作階段將執行器鎖定到該工作階段的擁有者，執行器為該擁有者執行最多 `--capacity` 個並行工作階段。當執行器有活躍工作階段且未收到關閉信號或達到其退休時間時，執行器會繼續認領鎖定擁有者的佇列工作。一旦它們完成會發生什麼取決於 [`--drain-grace-sec`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags)：

* **在預設值 `0` 時**：執行器在其活躍工作階段完成後立即退出，無需輪詢更多工作，因此您部署它的協調器（例如 Kubernetes）可以使用新磁碟重新啟動它，準備為任何擁有者服務。
* **在正值時**：執行器在退出前繼續輪詢鎖定擁有者的佇列那麼多秒。

此生命週期隔離每個擁有者的簽出程式碼，無需執行器在擁有者之間刪除磁碟狀態。

您的基礎設施停止執行器的方式決定您是否需要 `--retire-at`。傳遞 `SIGTERM` 的終止不需要標誌：執行器按照[關閉時序](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#shutdown-timing)所述進行排水，或當您設定 [`--defer-shutdown-max-min`](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy#defer-the-drain-past-the-first-signal) 時保持為其已持有的工作階段服務。如果您的基礎設施改為在已知的掛鐘時間銷毀主機而不發送信號，或寬限期太短而無法排水，例如沙箱生命週期上限或現貨實例回收，請傳遞 `--retire-at <epoch-seconds>` 設定為該時間前幾分鐘。在退休時間：

1. 執行器停止接受新工作。
2. 執行器透過 [`--release-idle-session-min`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags) 旗標使用的相同發佈路徑發佈每個活躍工作階段，因此當使用者發送下一條訊息時，工作階段在新執行器上恢復。執行器何時發佈每個工作階段取決於其狀態：
   * 對於處於回合進行中的工作階段，執行器會在該回合完成後發佈它。執行器會先等待工作階段的程序向 Anthropic 回報該回合的結束，等待時間不超過 [`SELF_HOSTED_RUNNER_POST_TURN_SETTLE_MS`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#environment-variable-only-settings)。在 v2.1.280 之前，執行器會在回合完成後立即發佈工作階段。
   * 當回合完成並留下執行中的背景任務時，執行器最多等待 60 秒，然後發佈工作階段，即使它們仍在執行中。如果任務已完成但讀取其結果的後續回合尚未執行，執行器會保持工作階段直到該回合完成，並等待不超過 [`SELF_HOSTED_RUNNER_BG_RESULT_GRACE_MS`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#environment-variable-only-settings) 以便該回合開始。
3. 執行器在所有工作階段都被發佈後以 0 退出。

超過終止的輪次仍然會丟失；[關閉時序](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#shutdown-timing)涵蓋了調整邊距的大小。沒有 `--retire-at`，無信號主機終止與崩潰無法區分：控制平面記錄丟失的工作者而不是乾淨的發佈，工作階段重新佇列到另一個執行器。

### 網路路徑

執行器及其工作階段進行多種出站連接，不需要來自 Anthropic 的入站連接：

* **控制平面**：執行器輪詢 `api.anthropic.com` 以獲取工作並發佈設定進度和失敗事件，全部出站 HTTPS。輪詢充當執行器的心跳。
* **Git**：執行器透過 HTTPS 或 SSH 從您的 git 主機複製和推送，使用您的部署提供的憑證進行身份驗證。請參閱[設定 git](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#configure-git) 以了解各種選項，包括每個工作階段鑄造的憑證。使用 [Anthropic git 代理伺服器](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#use-the-anthropic-git-proxy)時，github.com 上儲存庫的 git 流量會改為經由 `api.anthropic.com`。
* **工作階段子程序**：子 Claude Code 程序持有工作階段到 `api.anthropic.com` 的事件串流，並為模型推理和工作階段期間執行的 git 命令進行自己的出站呼叫。在使用 [Anthropic 管理的 git](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#use-the-anthropic-git-proxy) 的工作階段中，子程序會開啟到 `api.anthropic.com` 的 WebSocket 連接，承載來自 `git` 和 `gh` 的 github.com 流量。
* **SCM 連接器**：可選的協調器 [SCM 連接器](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference.md#scm-connector-flags)無法使用，因此其隧道不會開啟。該隧道是到 `api.anthropic.com` 的 WebSocket 連接。

請參閱[網路需求](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#network-requirements)以取得完整的出站清單。[上面的圖表](#how-self-hosted-environments-work)顯示了這些路徑，除了可選的 SCM 連接器和 Anthropic 管理的 git 連接。

預設情況下，模型推理使用 Anthropic API。控制平面將 API 端點傳遞給每個工作階段，工作階段使用 Anthropic 發行的、工作階段範圍的 OAuth token 進行身份驗證。若要改為將模型請求傳送到您自己的雲端帳戶，請參閱[將模型請求傳送到 Bedrock 或 Agent Platform](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#send-model-requests-to-bedrock-or-agent-platform)。

支援公司出站代理。執行器和可選的[自動擴展協調器](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#on-demand-runners)遵守[網路設定](https://code.claude.com/docs/zh-TW/network-config.md)中描述的代理和 mTLS 環境變數，例如 `HTTPS_PROXY` 和 `NO_PROXY`；在每個程序的環境中設定它們。這些變數涵蓋控制平面呼叫、協調器的 [SCM 連接器](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference.md#scm-connector-flags) WebSocket 和 HTTPS 遠端的內建複製，工作階段從執行器繼承它們。工作階段流使用透過 HTTPS 的伺服器發送事件，因此路徑中的代理不得緩衝回應。

* **代理伺服器身分驗證**：如果您的代理伺服器還需要 `Proxy-Authorization` 標頭，執行器可以將其新增到它開啟到代理伺服器的每個連接；請參閱[向出站代理伺服器進行身分驗證](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#authenticate-to-an-egress-proxy)。
* **長時間存續的回應**：如果執行器認領了工作階段，但 Claude 從未回答其第一則訊息，原因可能出在您的代理伺服器。請參閱[工作階段已被認領，但 Claude 從未回答其第一則訊息](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#when-a-sessions-first-message-is-never-answered)。

## 保留在您的基礎設施上的內容

儲存庫簽出、建置產物、祕密和工作階段建立或修改的任何檔案都保留在您佈建的機器上。對話本身，包括提示詞、回應和工具結果，會發送到 `api.anthropic.com`，Anthropic 會儲存工作階段逐字稿，以便您可以從另一個[支援的使用介面](#availability-and-limitations)恢復工作階段。當執行器[將模型請求發送到 Amazon Bedrock 或 Google Cloud 的 Agent Platform](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#send-model-requests-to-bedrock-or-agent-platform) 時，對話仍會在工作階段的事件串流中發送到 `api.anthropic.com`。

自託管環境將工作階段執行移到您的網路中。控制平面仍然是 Anthropic 託管的：工作階段協調、佇列和 claude.ai 介面繼續在 Anthropic 的基礎設施上執行。

## 開始使用

自託管環境頁面按您正在做的事情組織：

* [快速入門](https://code.claude.com/docs/zh-TW/self-hosted-environments-quickstart.md)：安裝 Claude Code、建立環境、啟動執行器並路由您的第一個工作階段
* [部署到生產環境](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md)：安全強化、網路出站、git 認證、Kubernetes 和 Compose 配方、已知問題和故障排除
* [自訂工作階段](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md)：每個工作階段認證的包裝器指令碼、生命週期掛鉤、按需執行器、MCP 伺服器和權限
* [端到端測試](https://code.claude.com/docs/zh-TW/self-hosted-environments-testing.md)：CI 煙霧測試，在您推廣執行器映像之前驗證它
* [參考](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference.md)：每個 CLI 標誌、環境變數、度量和健康端點
* [驗證工作階段身份](https://code.claude.com/docs/zh-TW/self-hosted-environments-identity.md)：在授予存取權限之前，從您自己的服務驗證工作階段令牌

<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy | lastmod: 2026-11-02 | section: Administration / Gateways -->
> 來源：https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy（官方 zh-TW，lastmod 2026-11-02）｜分類：Administration › Gateways｜EN 摘要：Register the gateway with your IdP, build the container, deploy on Kubernetes or Cloud Run, and operate it: health checks, secret rotation, upgrades, and security.

# Claude 應用程式閘道部署和運營

> 向您的身份提供者註冊閘道、建置容器、在 Kubernetes 或 Cloud Run 上部署，並運營它：健康檢查、祕密輪換、升級和安全性。

> [!NOTE]
>
> **先規劃閘道的網路。** 登入時，Claude Code 會拒絕主機名稱解析為公用 IP 位址的 Claude 應用程式閘道，即使該位址無法從網際網路存取也一樣。
>
> Claude 應用程式閘道可以將設定推送到使用者的機器，包括執行 shell 命令的 hook。此檢查有助於防止使用者意外登入公用網際網路上的惡意閘道。也請讓您自己的閘道遠離網際網路。
>
> 在選擇閘道的執行位置之前，請先選擇閘道的位址。通常這是使用者在您的內部網路上或透過 VPN 存取的私人位址。如果您的內部網路使用公用 IPv4 範圍，您可以列出一個同時包含閘道和使用者機器的範圍。Claude Code 會將該相符結果視為閘道位於您內部網路上的跡象。請參閱[為閘道選擇位址](#choose-an-address-for-the-gateway)。如果兩者都不適合您的網路，請聯絡您的 Anthropic 客戶團隊。

本頁涵蓋執行 [Claude 應用程式閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway) 的運營方面：在您的身份提供者 (IdP) 中註冊 OAuth 用戶端、將閘道部署為容器，以及日常運營。關於閘道在啟動時讀取的 `gateway.yaml` 檔案中的每個選項，請參閱 [設定參考](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md)。

生產部署按順序遵循四個步驟，下面的章節與之相符。前兩個是您做出選擇的地方；後兩個是一旦運行時要查閱的參考資料。

1. [設定您的身份提供者](#identity-provider-setup)：註冊 OAuth 用戶端並檢查 Okta、Entra 和 Google 的各個 IdP 說明
2. [部署閘道](#deployment)：建置固定版本的容器映像並在 Kubernetes、Cloud Run 或您自己的平台上執行。本章節也涵蓋成本、繞過、多閘道和無伺服器決策
3. [設定運營](#operations)：日誌、健康探針、中斷行為、祕密輪換和升級。當您連接監控和運行手冊時的參考資料
4. [檢查安全態勢](#security)：資料流向何處、威脅模型和合規性答案。用於安全審查的參考資料

如果沿途簽入或啟動失敗，請直接前往 [故障排除](#troubleshooting)，該部分根據您看到的錯誤進行索引。

## 身份提供者設定

註冊一個機密 OAuth/OpenID Connect (OIDC) 網路應用程式，使用單一重新導向 URI `https://<gateway>/oauth/callback`，並將其分配給應該有閘道存取權限的使用者或群組。閘道使用該註冊的用戶端密碼向 IdP 進行身分驗證；如果您的 IdP 改用[憑證式憑證](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#certificate-client-authentication)，則使用您上傳至該註冊的憑證進行身分驗證。

任何 OIDC 相容的 IdP 都可以使用：Okta、Microsoft Entra ID、Google Workspace、Keycloak、Dex、PingFederate 等。IdP 必須滿足三個要求：

* 在生產環境中透過 HTTPS 提供 `/.well-known/openid-configuration`；閘道接受 [`http://` 發行者](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#oidc)，環回發行者另外需要 `CLAUDE_GATEWAY_ALLOW_LOOPBACK=1`
* 支援授權碼流程。PKCE（代碼交換的證明金鑰）預設開啟；對於不支援它的 IdP，使用 `oidc.use_pkce: false` 停用它
* 在 id\_token 中傳回 `email` 和可選的 `groups`，或使用 `oidc.userinfo_fallback: true` 從 userinfo 端點提供它們

對於私有 PKI，設定 `oidc.ca_cert_pem`。

一些提供者以不同方式處理電子郵件和群組聲明：

* **Okta**：位於 `https://example.okta.com` 的組織授權伺服器傳回省略 `email` 和 `groups` 的簡化 id\_token，因此當您將其用作 `issuer` 時設定 `oidc.userinfo_fallback: true`。包含 id\_token 中 `email` 和可選 `groups` 的自訂授權伺服器（例如 `https://example.okta.com/oauth2/default`）直接發出它們，不需要回退。Okta 只在 `oidc.scopes` 中請求 `groups` 範圍且應用程式的群組聲明篩選器允許時才發出 `groups`；`userinfo_fallback` 無法填充 IdP 未被要求的聲明。
* **Microsoft Entra ID**：`issuer` = `https://login.microsoftonline.com/<tenant-id>/v2.0`。Entra 發出群組物件 ID 而不是名稱，因此在 `managed.policies.match.groups` 中使用 GUID，或使用應用程式角色以獲得人類可讀的名稱。如果您的租戶在 `roles` 而不是 `groups` 下發出角色，設定 `oidc.groups_claim: roles`。
* **Google Workspace**：`issuer` = `https://accounts.google.com`。Google 的 id\_token 不包含群組。要將基於群組的 `allowed_groups` 或 `managed.policies` 與 Google 作為 IdP 一起使用，請配置 [`oidc.google_groups`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#oidc)，它使用具有網域範圍委派的服務帳戶透過 Admin SDK Directory API 查詢每個使用者的群組。沒有它，使用 `oidc.allowed_email_domains` 進行成員資格閘道和 `managed.policies.match.email_domain` 進行原則分配。Google 也忽略標準 `offline_access` 範圍。對於重新整理令牌，設定 `oidc.scopes: [openid, profile, email]` 和 `oidc.extra_auth_params: { access_type: offline, prompt: consent }`。

> [!WARNING]
>
> 重新整理令牌讓閘道無聲地更新開發人員的會話，無需將開發人員送回瀏覽器。它們也驅動取消配置，因為當 IdP 停用使用者時，下一次重新整理失敗，會話在 `ttl_hours` 內結束。閘道預設請求 `offline_access` 以獲取重新整理令牌。如果您的 IdP 需要明確同意離線存取，請配置 OAuth 用戶端以允許它。
>
> 如果您的 IdP 根本無法發出重新整理令牌，閘道仍然可以工作，但沒有無聲更新，因此開發人員在會話過期時重新執行瀏覽器登入。為了防止每小時發生一次，將 [`session.ttl_hours`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#session) 提高到 `8` 或 `12`。權衡是取消配置延遲，因為沒有重新整理令牌，被停用的使用者在更長的 TTL 經過之前保持存取權限。

## 部署

閘道是單一無狀態 Linux 二進位檔案，透過 Postgres 進行協調，因此以您在環境中部署任何其他無狀態服務的方式部署它。將其保持在您的網路內，讓您的開發人員可以透過 HTTPS 到達它，且它可以到達您的 IdP，並將其視為任何持有生產憑證的服務。

除了它執行的位置之外，還有一些決策塑造部署：

* **成本**：沒有單獨的許可證或按座位費用。閘道是 `claude` 二進位檔案的一部分，因此您透過現有的承諾為推理付費，加上它執行的計算。
* **繞過**：閘道不強制執行通往模型的唯一路由必須通過它。具有自己認證的開發人員仍然可以直接呼叫提供者，因此關閉該路徑是網路原則決策，例如阻止到 `api.anthropic.com` 的出口，除了來自閘道。阻止該出口也會破壞 [WebFetch 網域安全檢查](https://code.claude.com/docs/zh-TW/data-usage.md#webfetch-domain-safety-check)，它從每個開發人員的機器呼叫 `api.anthropic.com`。在受管原則中設定 `skipWebFetchPreflight: true` 以停用它。
* **多個閘道**：每個是一個單獨的部署，具有自己的設定，CLI 按閘道主機名儲存信任和認證，因此團隊可以使用不同的閘道而不會衝突。要提供多個 OIDC 發行者，請執行單獨的實例。
* **無伺服器**：Cloud Run 可以工作，如果您設定 `min-instances: 1` 以避免冷 OIDC 發現。Lambda 和 Cloud Functions 不行，因為閘道是長時間執行的 HTTP 伺服器。

此處的每個生產拓撲都在純 HTTP 副本前面放置 L7 代理，例如 Ingress、Cloud Run 的前端或 ALB。設定 [`listen.trusted_proxies`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#listen) 為代理的來源範圍，以便閘道從 `X-Forwarded-For` 讀取用戶端 IP。閘道只在 TCP 對等體受信任時才遵守標頭。[Google Cloud](https://code.claude.com/docs/zh-TW/claude-apps-gateway-on-gcp.md) 和 [AWS](https://code.claude.com/docs/zh-TW/claude-apps-gateway-on-aws.md) 實際工作範例為每個拓撲提供具體值。沒有受信任的代理，每個請求似乎都來自代理的 IP，這會將按 IP 速率限制摺疊為一個共享桶，並在審計事件中記錄代理的 IP。

不要將請求重新導向到閘道的裝置授權和權杖端點，例如使用 HTTP 到 HTTPS 或主機規範化重寫在 Ingress 處。Claude Code 不會在這些請求上跟隨重新導向，因此重新導向它們的 Ingress 規則會破壞登入和權杖重新整理。

給代理任何閒置逾時時間長於閘道的保活間隔，這取決於上游：

* 在除了 `provider: anthropic` 之外的每個上游上，一旦串流沉默約 15 秒，閘道就會寫入 SSE `ping`。
* 在 `provider: anthropic` 上，閘道將回應原封不動地傳遞，包括 Anthropic API 自己的 ping。

預設值（例如 ALB 的 60 秒）足以保持安靜的串流開啟。[AWS 實際工作範例](https://code.claude.com/docs/zh-TW/claude-apps-gateway-on-aws.md#troubleshooting)無論如何將其提高到一小時，其故障排除列涵蓋早於 v2.1.229 的閘道，它在現在獲得 ping 的上游上的安靜期間沒有發送任何內容。

### 為閘道選擇位址

Claude Code 以下列兩種方式之一接受閘道的位址：

* **私有位址**：將閘道放在內部負載平衡器或 VPN 後方，並使用僅解析為私有位址（例如 RFC 1918 或 CGNAT `100.64.0.0/10`）的主機名稱。使用者的機器可以使用任何位址。[私有網路先決條件](https://code.claude.com/docs/zh-TW/claude-apps-gateway#prerequisites)列出接受的範圍。
* **宣告的區塊**：如果您的內部網路使用您組織擁有的公用 IPv4 空間，請在 `gatewayInternalNetworks` 受管設定中列出該區塊。閘道與使用者的機器都必須位於該區塊內。請參閱[允許位於您擁有的公用位址空間上的閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway#allow-a-gateway-on-public-address-space-you-own)。

如果沒有任何單一區塊同時包含兩者，請改為給閘道一個私有位址。

### 容器映像

圍繞標準 Claude Code 版本中的原生 `claude` 二進位檔案建置您自己的映像：

1. 從固定版本下載您的映像架構的 Linux 建置；請參閱 [安裝特定版本](https://code.claude.com/docs/zh-TW/setup.md#install-a-specific-version) 以取得下載 URL。
2. 根據 [二進位完整性和代碼簽名](https://code.claude.com/docs/zh-TW/setup.md#binary-integrity-and-code-signing) 中所述，根據版本的 GPG 簽名 `manifest.json` 驗證它。
3. 將其複製到建置上下文中。

如果您的建置無法到達版本主機，請將版本鏡像到您的內部登錄中，並固定您的機隊執行的版本。

除了二進位檔案，映像還需要：

* **基於 glibc 的映像**：glibc 建置的唯一動態依賴項是 glibc 庫。基於 Musl 的映像需要 `linux-x64-musl` 或 `linux-arm64-musl` 建置加上額外套件；請參閱 [Alpine Linux 設定](https://code.claude.com/docs/zh-TW/setup.md#alpine-linux-and-musl-based-distributions)。
* **可寫入的狀態目錄**：閘道以任何使用者身份執行，但最小映像沒有可寫入的主目錄。將 `CLAUDE_CONFIG_DIR` 設定為可寫入的路徑，例如 `/tmp/.claude`。
* **容器命令**：`claude gateway --config /etc/claude/gateway.yaml`，設定檔案以唯讀方式掛載，祕密作為環境變數提供；閘道在 `listen.port` 上監聽，預設為 `8080`。

### Kubernetes

將閘道作為 Deployment 執行，就像任何無狀態服務一樣：

* 從 ConfigMap 掛載設定，從 Secret 掛載祕密；透過 `${file:/path/to/secret}` 或作為環境變數在 YAML 中參考祕密
* 在 Ingress 處終止 TLS 並將 `listen.public_url` 設定為 Ingress 主機名
* 將就緒探針指向 `GET /readyz`，將活躍探針指向 `GET /healthz`

如需 AWS 上的完整實際工作範例，涵蓋 ECS Fargate 或 EKS、Amazon RDS 和 AWS Secrets Manager，請參閱 [在 AWS 上部署](https://code.claude.com/docs/zh-TW/claude-apps-gateway-on-aws.md)。

優先選擇平台的工作負載身份而不是靜態金鑰；[`upstreams` 參考](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#upstreams)有各平台設定詳情。對於跨雲配對，例如 GKE 上的 Amazon Bedrock 上游，在上游的 `auth` 區塊中設定明確認證。

### Cloud Run

按如下方式設定服務：

* 將 `listen.port` 保留在預設值 `8080`，這與 Cloud Run 的預設 `PORT` 相符，或設定 `port: ${PORT}`
* 將 `public_url` 設定為外部可到達的來源。對於生產，這通常是內部負載平衡器的主機名，因為 `/login` [拒絕公開地址](https://code.claude.com/docs/zh-TW/claude-apps-gateway#prerequisites)，而 `*.run.app` URL 解析為一個，所以單獨的 Cloud Run URL 僅適用於 `curl` 或瀏覽器煙霧測試。例外是一個網路，其中 `*.run.app` 透過 Private Service Connect 和 Cloud DNS 私有區域私下解析；在該拓撲中，Cloud Run URL 是有效的 `public_url`。[Google Cloud 實際工作範例](https://code.claude.com/docs/zh-TW/claude-apps-gateway-on-gcp.md#deploy-the-gateway)涵蓋兩者。
* 將設定掛載為祕密卷
* 設定 `min-instances: 1` 以避免首次請求時的冷 OIDC 發現

如需 Google Cloud 上的完整實際工作範例，涵蓋 Cloud Run 或 GKE、Cloud SQL 和 Secret Manager，請參閱 [在 Google Cloud 上部署](https://code.claude.com/docs/zh-TW/claude-apps-gateway-on-gcp.md)。

### 將閘道 URL 推送到開發人員機器

一旦閘道開始提供服務，透過受管設定，經由 MDM 或直接寫入各個 OS 的 `managed-settings.json`，將 `forceLoginMethod`、`forceLoginGatewayUrl` 和 `parentSettingsBehavior: "merge"` 推送到每個開發人員的機器。

一旦您部署金鑰，Claude Code 就會停止在機器上使用剩餘的 API 金鑰或 claude.ai 登入，因此請將推送與您的登入指示一起規劃。[管理員原則需要 Cloud 閘道登入](https://code.claude.com/docs/zh-TW/errors.md#administrator-policy-requires-a-cloud-gateway-sign-in)描述開發人員看到的訊息。

請參閱 [每個機制儲存原則的位置](https://code.claude.com/docs/zh-TW/managed-settings.md#where-each-mechanism-stores-the-policy) 以取得檔案路徑，以及 [用戶端受管設定](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#client-side-managed-settings) 以取得 Claude Desktop `bootstrapUrl` 等效項。

### 大規模推出

登入按用戶端 IP 地址進行速率限制，預設值適合小型團隊。每個地址在每 10 分鐘內獲得 30 次登入開始和 10 次代碼提交。向數千名開發人員的推出可能在第一個早上達到這些限制，原因有兩個：

* **閘道無法看到您的負載平衡器之外。** 沒有 [`listen.trusted_proxies`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#listen)，每個開發人員似乎都來自負載平衡器的地址並共享一個限制。首先設定它。閘道在第一次忽略 `X-Forwarded-For` 標頭時記錄警告。
* **許多開發人員共享幾個 NAT 或 VPN 出口地址。** 即使 `trusted_proxies` 正確，他們也共享這些地址的限制。提高 [`rate_limits`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#http-tuning) 以適應。

要調整 `max`，將開發人員數除以他們共享的出口地址。估計在一個 `window_seconds` 期間內有多少人登入，預設為 10 分鐘。然後將其加倍以涵蓋重試和登入到 Claude Code 和 Claude Desktop 的開發人員。

例如，10,000 名開發人員在 4 個出口地址後面在一小時內均勻登入。這是每個地址 2,500 名開發人員，每 10 分鐘約 420 名，您將其加倍並四捨五入到 1,000。下面的範例將兩個限制都設定為 1,000：

```yaml theme={null}
rate_limits:
  device_authorization: { max: 1000, window_seconds: 600 }
  device_verify: { max: 1000, window_seconds: 600 }
```

`device_verify` 是阻止某人猜測另一個開發人員登入代碼的原因，因此只在您的估計需要的範圍內提高它。即使在這些限制下，代碼也是來自 20 字元字母表的 8 個字元，並在 10 分鐘後過期，因此猜測仍然不切實際；請參閱 [使用者代碼暴力破解抵抗](#user-code-brute-force-resistance)。

當您的 IdP 發行重新整理權杖時，Claude Code 會無聲地更新會話，因此您可以在推出後將限制放回。沒有重新整理權杖，開發人員每 [`session.ttl_hours`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#session) 再次登入。同時調整兩個限制的大小以適應該穩定速率，並保持提高。

當達到限制時，Claude Code v2.1.274 或更新版本顯示 `The gateway is limiting sign-in attempts right now`。v2.1.274 或更新版本的閘道在驗證頁面上顯示 `Too many attempts came from your network address`，並提供要檢查的設定。它還寫入 `sign-in refused` 日誌行，命名要變更的設定。

## 操作

一旦閘道開始提供流量，日常操作包括讀取其日誌、探測其健康狀態，以及按照您的排程輪換其密鑰。以下小節涵蓋每一項，以及 Postgres 保存的內容，以及升級和回滾的行為方式。

### 日誌

閘道向 stderr 寫入兩個串流，兩者都是 JSON 友善的：

* **稽核事件**：每個安全相關事件一行 JSON。將 stderr 導管到您的日誌聚合器。

  發出的事件包括 `config.load`、`session.mint`、`session.refresh`、`device.authorize`、`device.verify`、`device.callback`、`auth.denied`、`access.denied`、`access.public_client`、`inference`、`managed.serve`、`desktop_bootstrap.serve`、`desktop_bootstrap.denied`、`spend.blocked`、`admin.denied`、`admin.limit.upsert` 和 `admin.limit.delete`。欄位因事件而異：

  * 成功的 mint 和 refresh 事件攜帶 `sub`、`email`、`client_ip` 和結果
  * `auth.denied` 和 `access.denied` 攜帶原因和用戶端 IP，加上 `auth.denied` 的請求路徑，因為在這些拒絕時不存在使用者身份。兩個 `access.denied` 原因改變事件攜帶的內容：
    * `xff_unparseable`：事件也攜帶無法讀取的 `X-Forwarded-For` 項目
    * `client_ip_unknown`：事件不攜帶用戶端 IP，因為連線沒有對等位址，而 `access_control` 清單已設定
  * `access.public_client` 攜帶每個程序中第一個從公開位址到達的請求的用戶端 IP，同時 `access_control.allow_cidrs` 為空。閘道照常提供請求；事件表示閘道可能可從公開網際網路到達。請參閱 [`access_control` 參考](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#http-tuning)，了解什麼算作公開以及建議的允許清單。
  * `inference` 記錄哪個上游提供了請求以及回應狀態
  * `desktop_bootstrap.denied` 記錄被拒絕的 Claude Desktop bootstrap 擷取，包含原因（`not_configured`、`policy_not_opted_in` 或 `no_policy_matched`）和使用者的身份
  * `guardrail.trace` 記錄[觸發了哪個篩選器](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#log-which-guardrail-filter-fired)，不包含相符的文字
  * `admin.denied` 記錄被拒絕的管理員 API 驗證嘗試，包含用戶端 IP、方法、路徑和原因，不包含呈現的金鑰資料：當呈現了 `x-api-key` 但未與任何已設定的金鑰相符時為 `invalid_key`，當僅呈現了 `Authorization` 標頭且其未驗證為 `admin.admin_groups` 中的閘道工作階段時為 `bearer_rejected`，或當兩個標頭都未呈現時為 `no_credentials`
* **操作日誌**：人類可讀的 `[gateway]` 前綴行，用於啟動、警告和上游錯誤。`CLAUDE_GATEWAY_LOG_LEVEL` 環境變數控制詳細程度，接受 `debug`、`info`、`warn` 或 `error`，預設為 `info`。在 `debug` 時，每個登入和重新整理也會記錄 id\_token 中的宣告名稱（而非值），加上當 `userinfo_fallback` 提供任何時的 userinfo 宣告名稱，因此您可以診斷 `email_claim` 和 `groups_claim` 設定，而不記錄個人識別資訊。它不影響稽核事件，稽核事件始終被發出。

### 健康狀態

閘道提供 `GET /healthz` 作為活躍性探測，`GET /readyz` 作為就緒性探測。`/readyz` 驗證存放區是否可到達。如果您設定了 [`store.readiness_grace_seconds`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#store)，`/readyz` 在存放區停止應答後最多繼續報告就緒達該秒數。

兩者都豁免於 `access_control.allow_cidrs`，因此探測在鎖定的接聽程式上保持運作。

`/.well-known/oauth-authorization-server` 的 OAuth 探索文件也只在設定載入、OIDC 探索、上游用戶端建構和 Postgres 遷移全部成功後才傳回 `200`，因此它也可作為端對端啟動檢查。

### 並行上游請求

預設情況下，每個閘道複本同時最多向上游傳送 256 個請求。串流回應在串流結束前計入限制。

在複本達到限制時到達的請求在閘道內等待空閒插槽。開發人員看到回應開始緩慢或似乎掛起。在 `provider: anthropic` 上游上，等待時間超過 [`timeouts.upstream_ttfb_ms`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#http-tuning) 的請求放棄該上游，當沒有後續上游提供它時失敗並返回 502。

包含 `upstream requests:` 的啟動日誌行顯示有效的限制。當複本的開啟請求數超過限制時，它也會記錄最多每分鐘一次包含 `client requests are open` 的警告。

要同時提供更多請求，您有兩個選項：

* 新增複本。
* 提高每個複本上的限制。在閘道容器上設定 `BUN_CONFIG_MAX_HTTP_REQUESTS` 環境變數為 1 到 65535 之間的整數，然後重新啟動容器。

複本以約限制除以請求保持開啟的平均秒數的請求速率填滿其限制。例如，如果請求平均保持開啟 10 秒，預設限制為 256 的複本以約每秒 26 個請求的速率填滿它。

如果您在 CPU 上自動擴展，達到限制的複本會佇列請求而不觸發橫向擴展，因此將目標設定在複本在記錄 `client requests are open` 警告時顯示的 CPU 級別以下。

> [!WARNING]
>
> 每個開啟的請求在串流時和等待插槽時在閘道程序中保持記憶體。如果您將限制保持在 256，過載複本上的記憶體仍會增長，因為等待的請求保持其請求本體。根據尖峰時開啟的請求數調整容器的記憶體大小，並在您變更限制時監視記憶體。記憶體不足的複本被殺死並丟棄它保持的每個串流。

### 將 `API_TIMEOUT_MS` 保持在閘道的首位元組時間以上

如果您降低 [`API_TIMEOUT_MS`](https://code.claude.com/docs/zh-TW/network-config#streaming-idle-watchdogs) 以便更快重試未獲回應的請求，請將其保持在閘道傳送串流回應前幾個位元組所需的時間以上。等待更久的請求會逾時，每次等待同樣久的重試也會逾時，直到該回合以 `Request timed out` 結束，除非[首位元組期限](#retry-an-unanswered-request-sooner-with-the-first-byte-deadline)先將其結束。

* **`provider: anthropic`**：將 `API_TIMEOUT_MS` 設定為高於您的上游傳送其第一個事件所需的最長時間。
* **其他所有上游**：將其設定為比您的上游傳回回應標頭所需的最長時間多出 20 秒以上。閘道會在這些標頭之後約 15 秒傳送其第一個 [keepalive `ping`](#deployment)，除非上游的第一個事件更早到達。早於 v2.1.229 的閘道不會傳送 ping，因此在該情況下請使用 `provider: anthropic` 的規則。

在該時間之外，還要預留任何[等待空閒插槽](#concurrent-upstream-requests)的時間，以及在[容錯移轉](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#multiple-upstreams)前等待已停擺上游的時間。也請將該值保持在最長的[非串流請求](https://code.claude.com/docs/zh-TW/network-config.md#streaming-idle-watchdogs)時間以上。

### 使用首位元組期限更快重試未獲回應的請求

若要讓 Claude Code 更快重試未獲回應的串流請求，請在開發人員的機器上設定 [`CLAUDE_STREAM_FIRST_BYTE_TIMEOUT_MS`](https://code.claude.com/docs/zh-TW/env-vars)，為其提供首位元組期限。此期限會限制第一次嘗試等待回應標頭的時間。若未設定，該嘗試可能會等待 5 到 6 分鐘。需要開發人員機器上的 Claude Code v2.1.307 或更新版本。

請將此變數設定為以毫秒為單位的正整數，可在[閘道原則的 `env` 區塊](#deliver-the-value-in-a-policy)或開發人員的 shell 中設定。請將該值保持在閘道最長的[首位元組時間](#keep-api_timeout_ms-above-the-gateways-time-to-first-byte)以上，否則 Claude Code 可能會中止並重新傳送標頭耗時較長的正常請求。以下範例在開發人員的 shell 中設定 60 秒：

```bash theme={null}
export CLAUDE_STREAM_FIRST_BYTE_TIMEOUT_MS=60000
```

未獲回應的重新傳送可能會等待 5 到 6 分鐘，直到[本體閒置逾時](https://code.claude.com/docs/zh-TW/network-config.md#streaming-idle-watchdogs)將其結束，並由 Claude Code 在[重試預算](https://code.claude.com/docs/zh-TW/errors.md#tune-retry-behavior)內重試。如果您降低 `API_TIMEOUT_MS` 只是為了更快重試，請移除該值，否則一次未獲回應的重新傳送就可能以 [No response from API](https://code.claude.com/docs/zh-TW/errors.md#no-response-from-api) 結束該回合。

若要確認期限已觸發，請讓開發人員以[偵錯日誌](https://code.claude.com/docs/zh-TW/network-config.md#verify-your-configuration)啟動 Claude Code，然後在日誌中搜尋 `[first-byte] no response headers`。

### 中斷行為

如果 Postgres 宕機，閘道本身繼續提供已登入的開發人員，新登入失敗。開發人員是否實際繼續工作取決於您的協調器如何處理就緒性：

* **現有工作階段**：持有人令牌使用 JWT 密鑰在本地驗證，工作階段重新整理不接觸存放區，閘道程序仍可提供推論
* **新登入**：失敗直到 Postgres 恢復，因為裝置流及其速率限制計數器存在於 Postgres
* **[支出限制強制執行](https://code.claude.com/docs/zh-TW/claude-apps-gateway-spend-limits.md#postgres-availability)**：在中斷期間預設失敗開啟，因此推論仍流動；如果您寧願阻止而不是無計量執行，請將其翻轉為失敗關閉
* **就緒性**：預設情況下，`/readyz` 在 Postgres 無法到達時立即報告未就緒，因此每個複本同時失敗其就緒性檢查。在流量僅到達通過檢查的複本的地方，所有流量（包括閘道仍可提供的推論）在 Postgres 恢復前失敗。`/healthz` 上的活躍性探測在整個過程中保持通過。

如果您的 IdP 宕機，現有工作階段工作直到 `ttl_hours`，新登入失敗。工作階段重新整理獲得重試答案並在 IdP 恢復後成功。如果您的 IdP 有頻繁的維護視窗，請設定更長的 `ttl_hours`。

#### 就緒性寬限期

要在短 Postgres 中斷（例如資料庫容錯移轉）期間保持已登入的開發人員工作，請將 [`store.readiness_grace_seconds`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#store) 設定為比容錯移轉耗時更長，例如 `300`。在支出限制開啟且預設失敗開啟行為下，通過保持就緒的複本的請求在 Postgres 恢復前無計量，因此將值保持為低至涵蓋您的容錯移轉。如果您設定了 [`enforcement.fail_closed_on_error: true`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#enforcement)，閘道拒絕已登入開發人員的推論，並返回 `429` `spend limit unavailable` 訊息，直到 Postgres 恢復，即使複本仍通過其就緒性檢查。

該設定需要閘道伺服器上的 Claude Code v2.1.282 或更新版本。較早的閘道在找到該金鑰時拒絕啟動，因此在新增它之前升級每個複本。[升級](#upgrades)涵蓋回滾。

如果您改為將就緒性探測指向 `/healthz`，複本也在中斷期間保持通過它，但 `/healthz` 永遠不報告未就緒，因此 Postgres 連線未恢復的複本保持通過。

### JWT 密鑰輪換

分階段輪換簽署密鑰，以便現有工作階段保持有效：

1. 產生新密鑰。將其前置到 `session.jwt_secret` 陣列。
2. 推出部署。新令牌使用新密鑰簽署；舊令牌仍驗證。
3. 在 `ttl_hours` 加上邊際後，移除舊密鑰並再次推出。

輪換也是在過期前強制工作階段退出的唯一方式：持有人令牌針對 JWT 密鑰在本地驗證，因此不存在每個工作階段的撤銷。直接替換密鑰，不在陣列中保持舊密鑰，立即使每個未完成的工作階段失效。對於個別離職，在您的 IdP 中取消配置使用者；其工作階段在 `ttl_hours` 內結束。

### Postgres

閘道將其狀態儲存在 PostgreSQL 資料庫中：

* **資料庫**：PostgreSQL 本身，自行託管或受管理皆可，需為[最低版本](https://code.claude.com/docs/zh-TW/claude-apps-gateway#prerequisites)或更新版本。僅實作 Postgres 協定的資料庫（例如分散式 SQL 資料庫）不受支援。
* **位址**：`store.postgres_url` 接受一個主機。如果資料庫有多個節點，請使用位於它們前方的位址，例如您的受管理服務的端點、負載平衡器或虛擬 IP。設定比容錯移轉耗時更長的[就緒性寬限期](#readiness-grace-period)。

閘道保持五個資料表加上 `_migrations` 表，全部由其啟動時遷移建立：

| 表 | 內容 | 保留 |
| - | - | - |
| `kv` | 裝置授予（10 分鐘 TTL）和速率限制計數器 | 每行 TTL |
| `spend` | 每個主體期間至今支出計數器，以美分計 | `admin.spend_retention_months`，預設 13 |
| `spend_limits` | 已設定的支出上限 | 直到透過 API 刪除 |
| `admin_audit` | 管理員 API 變更軌跡 | `admin.audit_retention_days`，預設 365 |
| `principal_emails` | 每個主體的最後看到的電子郵件、顯示名稱和 IdP 群組。包含個人識別資訊。 | `admin.identity_retention_days` 自上次活動起，預設 90 |

30 秒迴圈過期 `kv` 行超過其 TTL，每小時掃描在支出表上強制保留視窗，因此沒有任何東西無限增長。沒有[支出限制](https://code.claude.com/docs/zh-TW/claude-apps-gateway-spend-limits.md)已設定，只有 `kv` 被寫入。閘道在啟動和每次升級時應用其自己的架構遷移，因此其資料庫角色需要建立和更改表的權限。將其指向專用於閘道的資料庫或架構，以保持該授予狹窄。

使用支出限制，遺失的資料庫意味著遺失支出追蹤和上限，不僅是開發人員重新登入，因此執行定期備份。要立即清除一個已離職的開發人員而不是等待保留，直接執行 `DELETE FROM principal_emails WHERE principal = '<sub>'`；這移除唯一保持其電子郵件、名稱和群組的表。`spend` 和 `admin_audit` 行僅參考假名 OIDC `sub`。

#### 調整連線集區大小

每個複本最多開啟 [`store.max_connections`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#store) 個 Postgres 連線，預設為五個。請將複本數 × `store.max_connections` 保持在資料庫為閘道剩餘的連線數以下（含）：

* **複本**：計算同時執行的最大數量。從您的自動擴展上限開始（若未自動擴展，則為您的複本數），再加上滾動更新在停止舊複本前啟動的額外複本。在使用預設設定的 Amazon ECS 上以及在 Cloud Run 上，額外複本可能與原數量一樣多。
* **剩餘連線**：取資料庫的 `max_connections`，再減去資料庫保留的連線以及其他用戶端佔用的連線。PostgreSQL 保留 `superuser_reserved_connections`，預設為三個。受管理服務可能保留更多，請查閱其文件。

例如，假設自動擴展上限為六、滾動更新最多啟動兩個額外複本，且使用預設的五個連線集區。這需要 (6 + 2) × 5 = 40 個連線。`max_connections` 為 50 且有兩個連線由其他用戶端佔用的資料庫剩餘 50 − 3 − 2 = 45 個，因此總數符合。

如果您的總數不符合，請變更以下其中一項：

* **資料庫**：提高其 `max_connections`
* **複本**：減少執行數量，或讓您的協調器在滾動更新中啟動較少的額外複本
* **集區**：降低 `store.max_connections`，但在開啟[支出限制](https://code.claude.com/docs/zh-TW/claude-apps-gateway-spend-limits.md)時，請保持其足以應付每個複本的負載。否則支出檢查可能在等待連線時[逾時](https://code.claude.com/docs/zh-TW/claude-apps-gateway-spend-limits.md#postgres-availability)，且閘道會記錄 `spend check failed: spend precheck timed out`。

### 升級

複本是無狀態的，因此滾動重新啟動不會遺失閘道狀態。閘道在啟動時執行架構遷移，這意味著部署新二進位檔案自動遷移資料庫。並行複本在 Postgres 諮詢鎖上序列化，因此只有一個應用每個遷移。

當您的協調器使用 `SIGTERM` 停止複本時，如在滾動重新啟動或縮減中，閘道停止接受新連線並讓已在進行中的請求和串流在退出前完成。它等待最多 25 秒，稱為排放視窗，然後關閉仍然開啟的任何東西。`SIGINT`（例如終端中的 Ctrl+C）啟動相同的排放，排放期間的第二個信號關閉開啟的請求並立即退出。排放需要閘道 v2.1.274 或更新版本。

長代代可以串流數分鐘。在 Kubernetes 和 Amazon ECS 上，將這兩者一起提高以給予這些串流更多時間：

* **排放視窗**：在閘道容器上設定 `CLAUDE_GATEWAY_DRAIN_TIMEOUT_MS` 環境變數為正整數毫秒數，例如 `120000`。閘道忽略任何其他形式的值，例如 `120s`，並保持 25 秒預設
* **您的協調器的寬限期**：Kubernetes 上的 `terminationGracePeriodSeconds`，或 Amazon ECS 上的 `stopTimeout`

寬限期在兩個平台上預設為 30 秒。將其保持至少比排放視窗長 5 秒，否則協調器在排放完成前殺死閘道。在 Kubernetes 上，也新增任何 `preStop` 鉤子的持續時間，因為寬限期在鉤子執行前開始計數，而不是當閘道接收 `SIGTERM` 時。

您的平台也可能限制排放可以執行多長時間：

* **Amazon ECS on Fargate**：`stopTimeout` 最多允許 120 秒
* **Cloud Run**：在 `SIGTERM` 後 10 秒停止實例，因此開啟的串流在那裡最多獲得 10 秒，無論排放視窗是什麼

當排放視窗結束時仍有開啟的請求，閘道記錄包含 `drain window over after` 的警告，計數它切割的請求，並命名兩個要提高的設定。

遷移是僅附加的，因此回滾到知道較少遷移的先前二進位檔案是安全的；它忽略額外的行。回滾也針對較舊二進位檔案的架構重新驗證 YAML，因此採用由較新版本引入的金鑰的設定在較舊版本上啟動失敗。在回滾前移除新金鑰。

> [!WARNING]
>
> 僅從上游移除 `groups` 金鑰會使該上游對每位開發人員開放。請參閱[回滾前要移除的內容](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#roll-back-a-gateway-that-uses-groups)。

因為您在自己的映像中固定閘道的版本，新 Claude Code 版本中的修復（包括安全修復）僅在您更新固定並重新部署時到達您的部署。將閘道包含在您用於保持生產認證的其他服務的相同修補排程中。

## 安全

本章節回答安全審查提出的問題：什麼資料流經閘道以及它流向何處、設計防禦的攻擊，以及哪些答案屬於合規性問卷。

### 資料流

| 資料 | 路徑 | 由閘道發送給 Anthropic |
| - | - | - |
| 推理（提示、完成） | CLI → 閘道 → 您的上游 | 只有在 Anthropic API 是配置的上游時 |
| 遙測（OTLP 指標，加上 [選擇加入日誌和追蹤](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#telemetry)） | CLI → 閘道 → 您的收集器 | 從不 |
| 身份（電子郵件、群組、sub） | IdP → 閘道 → CLI；CLI 在 OTLP 匯出上標記它。如果您開啟 [`forward_user_identity`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#per-user-identity-headers-for-a-proxy-you-run)，閘道也會將開發人員的電子郵件和 IdP 主體作為標頭發送到您的代理 | 從不 |
| 受管設定 | 您的閘道 YAML → CLI | 從不 |
| 審計日誌 | 閘道 stderr → 您的聚合器 | 從不 |

### 威脅模型摘要

閘道位於您的網路周邊內，但個別開發人員筆記型電腦不被視為受信任。設計以三種方式考慮這一點：

* 開發人員持有短期 JWT 而不是原始上游金鑰。CLI 到閘道的腿使用 RFC 8628 設備授予，閘道與 IdP 的授權碼交換在預設配置中執行 PKCE，因此攔截的 IdP 授權碼是無用的。
* 設備驗證頁面強制執行同源 POST 和根據 RFC 8628 §5.1 的每 IP 速率限制。請參閱 [使用者代碼暴力破解抵抗](#user-code-brute-force-resistance)。
* 閘道對您的 IdP、您的 OTLP 收集器和 `provider: anthropic` 上游的請求通過伺服器端請求偽造 (SSRF) 防護，解析 DNS、阻止連結本地和雲端中繼資料地址加上預設環回，並將連接固定到解析的 IP，因此操作員影響的 URL 無法重新導向到雲端中繼資料端點。RFC 1918 私有範圍被刻意允許，因為 IdP 和 OTLP 收集器通常存在於私有 IP 上。對於其他提供者，閘道在載入配置時拒絕命名這些地址或中繼資料主機名的 `base_url`，提供者的 SDK 隨後連接而不進行 DNS 檢查。

  如果您開啟 [僅代理出口](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#proxy-only-egress)，該地址檢查會移至您的轉發代理：閘道交付主機名，代理的允許清單必須拒絕這些目的地。

  只有當閘道必須到達的東西合法地存在於環回上時，才在閘道的環境中設定 `CLAUDE_GATEWAY_ALLOW_LOOPBACK=1`，例如本地開發 IdP 或 `localhost` 上的邊車 OTLP 收集器。該變數放寬每個操作員配置的 URL 的環回阻止，也跳過啟動時檢查 pod 是否可以到達雲端中繼資料端點的警告，因此偏好為收集器提供自己的內部地址。

如果您新增自己的出口控制，閘道必須在使用工作負載身份等實例中繼資料認證時到達中繼資料伺服器。

兩個威脅超出範圍，因為它們是您的基礎設施要保護的：

* **受損的閘道主機**：主機既持有上游認證，又向每個連接的開發人員分發 [受管設定](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#managed)，因此對閘道配置的控制與對您的 MDM 的控制相當。CLI 的 [批准對話框](https://code.claude.com/docs/zh-TW/server-managed-settings.md#approval-memory) 用於殼層功能設定限制無聲變更，但不替代主機安全。
* **惡意 OIDC 提供者**：提供者簽署閘道信任的 id\_token，因此它可以聲稱任何身份。審查和保護您的 IdP 是您的責任。

### 使用者代碼暴力破解抵抗

開發人員在 `/device` 驗證頁面中輸入的 `user_code` 是從 20 字元字母表中抽取的 8 個字元，產生 20⁸ 或約 2.56×10¹⁰ 個組合，並在 10 分鐘後過期。

閘道在設備授予端點上應用按 IP 速率限制，可透過 [`rate_limits`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#http-tuning) 配置。如果許多開發人員從單一共享公司 NAT 地址簽入，請提高限制。[大規模推出](#large-rollouts) 顯示如何調整它們的大小。限制僅適用於簽入流程，不適用於推理。

### 合規性態勢

* **資料駐留**：閘道自己的資料平面不向 Anthropic 發送任何東西，除非 Anthropic API 是配置的上游；當它是時，您現有的資料處理協議適用於推理路徑。遙測、審計、身份和設定只流向您配置的目的地。
* **主機程序流量**：主機程序是 Claude Code CLI。`claude gateway` 在與 Amazon Bedrock 和 Google Cloud 的 Agent Platform 部署相同的第三方規則下執行，不向 Anthropic 發送任何東西。在 v2.1.227 之前，主機程序發送啟動遙測，例如產品版本和平台，設定容器環境中的 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` 會關閉。這些版本也在啟動時發送一個 `HEAD` 請求，沒有正文或認證，到 `https://api.anthropic.com` 上的 `/api/hello`，或在環境設定時到 `ANTHROPIC_BASE_URL`，除非環境也設定代理變數（例如 `HTTPS_PROXY`）或 mTLS 用戶端憑證。它們忽略回應，因此在出口防火牆阻止該請求不會影響閘道。
* **用戶端分析**：CLI 在簽入到閘道時停用自己的使用分析和錯誤報告。在第一次簽入之前，CLI 仍然向 Anthropic 發送啟動事件，包括在受管設定強制閘道簽入的機器上。要也關閉這些，在強制閘道簽入的相同 [用戶端側受管設定](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#client-side-managed-settings) 中傳遞 [`DISABLE_TELEMETRY`](https://code.claude.com/docs/zh-TW/managed-settings#turn-telemetry-off-for-your-organization)。
* **錯誤報告**：每當 CLI 的模型請求流向 Anthropic 的第一方 API 以外的任何端點（例如 Amazon Bedrock 或自訂 `ANTHROPIC_BASE_URL`）時，CLI 會關閉錯誤報告。
* **用戶端機器**：開發人員的 CLI 仍然向 Anthropic 發送 WebFetch 主機名檢查和版本檢查，除非設定 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` 和 `skipWebFetchPreflight: true`。[外掛市集請求](#plugin-marketplace-requests) 有各自的關閉開關。請參閱 [資料使用](https://code.claude.com/docs/zh-TW/data-usage.md)。
* **調查評分**：在簽入到閘道時，CLI 停用 Anthropic 綁定評分上傳以及分析串流，因此不向 Anthropic 發送評分。
* **記錄單共享**：在調查的記錄單共享提示上選擇「是」會在 `~/.claude/feedback-bundles/` 下寫入本地檔案，而不是上傳到 Anthropic。
* **用戶端更新**：更新檢查與閘道流量分開。透過您自己的分發固定版本，如果筆記型電腦不得提取版本，設定 `DISABLE_UPDATES`。`DISABLE_AUTOUPDATER` 只停止背景更新，而 `claude update` 仍然有效。
* **TLS**：在生產中透過 HTTPS 提供 `public_url`，要麼從閘道自己的監聽器透過 `listen.tls`，要麼從 TLS 終止 ingress 在純 HTTP 副本前面，在兩種情況下都設定 `listen.public_url`。閘道不拒絕純 HTTP。IdP 必須在生產中提供 HTTPS，Postgres 支援 `?sslmode=require`。在您的 ingress 設定 `Strict-Transport-Security`。
* **漏洞披露**：遵循 [報告安全問題](https://code.claude.com/docs/zh-TW/security.md#reporting-security-issues)

### 外掛市集請求

Claude Code 直接從每位開發人員的機器擷取外掛市集，而非透過閘道。[網路存取需求](https://code.claude.com/docs/zh-TW/network-config.md#network-access-requirements) 列出了這些主機。

開發人員首次啟動互動式終端機工作階段時，Claude Code 會註冊官方市集 `claude-plugins-official`。它會從 `downloads.claude.ai` 下載目錄，若失敗，則從 `github.com` 複製。[哪些市集和外掛會自動更新](https://code.claude.com/docs/zh-TW/plugins/loading.md#which-marketplaces-and-plugins-auto-update) 說明後續的重新整理。

`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` 不會阻止首次註冊。以下任一受管設定可以做到：

* **市集清單**：將該市集排除在外的 [`strictKnownMarketplaces`](https://code.claude.com/docs/zh-TW/plugins/org#allowlist-with-strictknownmarketplaces) 允許清單，或指名該市集的 [`blockedMarketplaces`](https://code.claude.com/docs/zh-TW/plugins/org#blocklist-with-blockedmarketplaces) 項目
* **環境變數**：在受管 [`env` 區塊](https://code.claude.com/docs/zh-TW/plugins/org#turn-updates-off-for-the-whole-fleet) 中將 `CLAUDE_CODE_DISABLE_OFFICIAL_MARKETPLACE_AUTOINSTALL` 設為 `"1"`

首次註冊可能在開發人員簽入閘道之前執行，此時尚未收到任何閘道政策。為涵蓋首次啟動，請在 [用戶端側受管設定](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#client-side-managed-settings) 以及閘道政策的 [`cli` 或 `code` 區塊](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#what-goes-in-cli) 中都傳遞您的選擇。

## 疑難排解

如有問題和意見回饋，請使用 [Claude Code 支援](https://support.claude.com/en/collections/14445694-claude-code)，或在 [Claude Code GitHub 儲存庫](https://github.com/anthropics/claude-code/issues)上開啟議題。您也可以聯絡您的 Anthropic 客戶團隊。回報問題時，請包含：

* **Gateway 問題**：gateway 的 stderr（針對相關視窗）、您的 `gateway.yaml`（已隱蔽機密）、gateway 版本（顯示在 `/` 的登陸頁面和 `/managed/settings` 上的 `x-cc-gateway-version` 回應標頭中），以及最近有什麼變更
* **登入問題**：開發者執行 `claude --debug-file ./claude-debug.txt`、重現問題，然後傳送該檔案加上 gateway 針對同一視窗的稽核日誌
* **推論問題**：請求的模型、設定的上游，以及 gateway 針對該請求的稽核日誌，其中記錄了哪個上游提供了該請求以及回應狀態

gateway 的 stderr 包含稽核事件串流，稽核日誌記錄開發者身分，除錯檔案記錄來自開發者機器的 hook 和 MCP 伺服器輸出。在發佈到公開議題之前，請檢查並隱蔽這些內容。

| 症狀 | 原因 | 修正 |
| - | - | - |
| 開發者的 `/login` 顯示標準帳戶選擇器，而不是 **Cloud gateway** 畫面 | 該機器上的受管設定中未設定 `forceLoginMethod` 或 `forceLoginGatewayUrl` | 將[受管設定檔](https://code.claude.com/docs/zh-TW/claude-apps-gateway#set-the-gateway-url)部署到裝置；`/login` 從該處讀取 gateway URL |
| 開發者的請求失敗，顯示 `Not signed in to the Cloud gateway — run /login.` | 機器的受管設定設定了 `forceLoginMethod: "gateway"` 或 `forceLoginGatewayUrl`，且工作階段沒有 gateway 登入。遺留的 claude.ai 登入不符合要求。 | 讓開發者執行 `/login` 並完成 gateway 登入。另請參閱[系統管理員原則要求 Cloud gateway 登入](https://code.claude.com/docs/zh-TW/errors.md#administrator-policy-requires-a-cloud-gateway-sign-in)。 |
| Claude Desktop 報告其啟動設定無法擷取 | `/user/bootstrap` 傳回 404：符合使用者的原則不包含 `desktop` 金鑰，或沒有原則符合。gateway 的稽核日誌將每次拒絕記錄為 `desktop_bootstrap.denied`，並附上原因。 | 將 `desktop` 區塊新增到符合使用者的原則，或新增到 `match: {}` 基礎層；空的 `desktop: {}` 即可。請參閱 [Claude Desktop 覆蓋層](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#claude-desktop-overlay)。 |
| 稽核日誌在 `/v1/logs` 或 `/v1/metrics` 上顯示 `auth.denied`，並附帶 `reason: invalid_token` | 您在機器的受管設定中設定了 [`otelHeadersHelper`](https://code.claude.com/docs/zh-TW/settings-reference#otelheadershelper)。在該機器上的 Claude Desktop 工作階段中，Claude Code 會將來自該 helper 的 `Authorization` 標頭傳送到 gateway 的遙測中繼，以取代工作階段 token。若 Claude Desktop 內建的 Claude Code 早於 v2.1.307，當您在這些設定中於 `OTEL_EXPORTER_OTLP_HEADERS` 或其個別訊號形式中設定 `Authorization` 標頭時，也會遇到相同的拒絕。 | 從這些設定中移除該 helper。若 Claude Desktop 內建的 Claude Code 早於 v2.1.307，請移除該變數。 |
| 啟動顯示 `Gateway login is configured in managed settings, but this Claude Code build does not include Cloud gateway support.` | 已安裝的 Claude Code 建置早於 gateway 支援 | 讓開發者將 Claude Code 更新到包含 Cloud gateway 支援的版本 |
| 啟動結束，顯示 `Administrator policy requires a Cloud gateway sign-in on this machine` | 開發者的環境設定了 `ANTHROPIC_API_KEY` 或 `ANTHROPIC_AUTH_TOKEN`、其設定中指定了 [`apiKeyHelper`](https://code.claude.com/docs/zh-TW/settings-reference#apikeyhelper)，或來自較早 Claude Console 登入的 API 金鑰仍然被儲存 | 讓開發者清除每個適用的項目：取消設定變數、移除 `apiKeyHelper` 項目，或執行 `claude auth logout` 以移除已儲存的金鑰。之後，使用 `CLAUDE_CODE_USE_*` 選擇雲端供應商的工作階段會在不登入的情況下啟動；對於其他所有工作階段，請讓他們啟動 `claude` 並使用 `/login` 登入。另請參閱[系統管理員原則要求 Cloud gateway 登入](https://code.claude.com/docs/zh-TW/errors.md#administrator-policy-requires-a-cloud-gateway-sign-in)。 |
| 啟動或 `/login` 在受管設定載入時出現 403 後報告 `Claude Code may not be enabled for your organization` | gateway 或其前面的某個東西以 403 回應了 `/managed/settings` 請求。gateway 自己的設定路由永遠不會回應 403。狀態來自 [`access_control`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#http-tuning) IP 檢查或來自 gateway 前面的代理伺服器或 WAF。稽核日誌將 IP 檢查拒絕記錄為 `access.denied`，並附上原因。開發者保持登入狀態。 | 檢查稽核日誌中失敗時的 `access.denied`，並修正 `access_control` 清單或前端，然後讓開發者再次啟動 `claude` |
| CLI `/login`：`The gateway is limiting sign-in attempts right now`，或在較舊版本上 `Request failed with status code 429`。`/device` 頁面可能對尚未嘗試過的開發者顯示 `Too many attempts` | 達到了每個 IP 的登入速率限制。要麼 `listen.trusted_proxies` 不涵蓋負載平衡器，所以每個開發者共享其位址，要麼許多開發者共享 NAT 或 VPN 出口位址。具有 `result: rate_limited` 的稽核事件顯示相同的一個或幾個 `client_ip` 值。 | 首先將 `listen.trusted_proxies` 設定為負載平衡器的來源範圍，然後如果開發者仍然共享位址，請提高 `rate_limits`。請參閱[大規模推出](#large-rollouts)。 |
| CLI `/login`：`Gateway hosts must be on your organization's private network; <host> resolves to the public (or unrecognized) address <ip>` | gateway 主機名稱解析為至少一個公開 IP 位址。Claude Code 檢查每個已解析的位址，並要求每個位址都是私有的。常見原因是雙堆疊名稱，其中一個系列解析為公開位址，包括 AWS 內部雙堆疊負載平衡器，它們傳回公開範圍的 AAAA 位址。 | 讓 gateway 名稱在開發者機器上只解析為私有位址。對於雙堆疊名稱，請刪除公開範圍記錄或提供單獨的僅限內部 DNS 名稱。請參閱[私有網路先決條件](https://code.claude.com/docs/zh-TW/claude-apps-gateway#prerequisites)。如果位址是您的組織擁有並在內部使用的公開空間，請改為[宣告該區塊](https://code.claude.com/docs/zh-TW/claude-apps-gateway#allow-a-gateway-on-public-address-space-you-own)。 |
| CLI `/login`：`Gateway login would go through proxy <proxy>, which is not on a private network` | `HTTPS_PROXY` 或 `HTTP_PROXY` 適用於 gateway 主機，且代理伺服器的主機名稱解析為公開位址。主機名稱只解析為私有位址的代理伺服器是允許的，不會觸發此錯誤 | 在開發者的機器上將 gateway 主機新增到 `NO_PROXY`，以便連線是直接的，或使用主機名稱解析為私有位址的代理伺服器。訊息會命名要新增的確切 `NO_PROXY` 項目 |
| CLI `/login`：`Claude Code only signs in to <host> from inside its declared network <block> (managed settings), and this machine is connecting from <ip>, outside it` | gateway 位於 [`gatewayInternalNetworks`](https://code.claude.com/docs/zh-TW/claude-apps-gateway#allow-a-gateway-on-public-address-space-you-own) 中宣告的區塊上，開發者的機器從該區塊外的位址到達它：VPN 位址池、容器或 WSL2 NAT 區段，或不是您的網路 | 讓開發者從您網路上的主機 OS 執行 `/login`。如果顯示的位址也是您組織自己的公開空間，請將 gateway 的項目替換為涵蓋兩者的區塊，最多 `/8`；第二個重疊項目會被拒絕。如果沒有區塊能涵蓋兩者，請參閱[為 gateway 選擇位址](#choose-an-address-for-the-gateway) |
| CLI `/login`：`Every address for gateway host <host> must be inside its declared network <block>, and it also resolves to <ip>` | gateway 的名稱解析為 [`gatewayInternalNetworks`](https://code.claude.com/docs/zh-TW/claude-apps-gateway#allow-a-gateway-on-public-address-space-you-own) 中宣告的區塊外的位址：第二個網站，或雙堆疊名稱上的 IPv6 記錄。在宣告的區塊下，每條記錄都必須在該一個 IPv4 區塊內，包括私有和 IPv6 位址 | 在開發者機器上的 gateway 名稱只發佈區塊內的記錄，或提供單獨的僅限內部名稱 |
| CLI `/login`：`<host> is on the declared network <block>, which Claude Code checks over a direct connection, not through an HTTP proxy` | `HTTPS_PROXY` 或 `HTTP_PROXY` 適用於宣告區塊上的 gateway | 在開發者的機器上，新增訊息命名的 `NO_PROXY` 項目 |
| CLI `/login`：訊息開頭為 `gatewayInternalNetworks in managed settings` | 該值違反了[驗證規則](https://code.claude.com/docs/zh-TW/claude-apps-gateway#allow-a-gateway-on-public-address-space-you-own)之一，訊息會命名哪一個。在您修正它之前，Claude Code 拒絕機器上的每個新 gateway `/login`，包括私有位址上的 gateway；現有登入保持工作 | 在您部署的受管設定來源中，更正訊息命名的項目，然後重新執行 `/login` |
| CLI `/login`：`Could not resolve the configured HTTP proxy` | `HTTPS_PROXY` 或 `HTTP_PROXY` 中的主機名稱無法從開發者的機器解析，通常是因為它未連線到公司網路 | 讓開發者連線到您的網路或 VPN 並重試，或修正代理伺服器 URL |
| CLI `/login`：`Could not resolve gateway host <host>` | 機器無法解析 gateway 的內部 DNS 名稱，通常是因為它不在公司網路上 | 讓開發者連線到您的網路或 VPN，然後重試 `/login` |
| 啟動結束，顯示命名 `store.postgres_url` 的設定驗證錯誤 | 未設定 Postgres；gateway 需要 Postgres | 設定 `store.postgres_url`。對於本機開發，請使用一次性容器：`docker run --rm -p 5432:5432 -e POSTGRES_HOST_AUTH_METHOD=trust postgres`。 |
| 啟動結束：`store.postgres_url in <path> is not a URL the gateway can read`，或在 v2.1.290 之前僅顯示 `Invalid URL` 或 `URI error` | 無法剖析該 URL，例如因為它列出了多個主機，或其密碼含有未編碼的 `/`、`?`、`#` 或 `%` | 只指定[一個主機](#postgres)，並將密碼移至 [`store.password`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#store) |
| 啟動結束：`requires the native binary` | 在 Node 下執行而不是原生二進位檔 | 使用其中一種[獨立安裝方法](https://code.claude.com/docs/zh-TW/setup.md)安裝 Claude Code |
| 啟動結束，在 `config.load` 後出現 OIDC 探索錯誤 | `oidc.issuer` 無法到達，或 TLS 鏈不受信任 | 檢查發行者是否可從 pod 到達並提供 `/.well-known/openid-configuration`。為私有 PKI 設定 `ca_cert_pem`。如果 pod 只能透過轉送代理伺服器到達 IdP，請設定 [`oidc.use_proxy: true`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#idp-requests-through-a-forward-proxy)；在 v2.1.227 之前的版本上，改為給 pod 一條到 IdP 每個端點的直接路由。如果 pod 也無法解析 IdP 的主機名稱，或代理伺服器拒絕 `CONNECT` 到 IP 位址，請參閱[僅透過代理伺服器的出口](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#proxy-only-egress)，這需要 v2.1.277 或更新版本。 |
| 啟動結束，出現 Postgres 權限錯誤 | 資料庫角色在其 schema 上缺少 DDL 權限 | 授予角色在 gateway schema 上的 `CREATE` 權限，以便它可以在啟動時建立和更改其表格 |
| 日誌：來自 PostgreSQL 的 `remaining connection slots are reserved` 或 `sorry, too many clients already`。它會出現在執行中副本的 `postgres connection closed` 警告中，或出現在新副本的啟動日誌中。在啟動日誌中，`remaining connection slots are reserved` 可能接在 `attempt 1 of 3` 之後，且副本仍可能啟動。 | 副本要求的連線數多於資料庫為 gateway 剩餘的連線數，PostgreSQL 會拒絕多出的連線 | 依照[調整連線集區大小](#size-the-connection-pool)的說明，讓總數符合上限：執行較少的副本、降低 `store.max_connections`，或提高資料庫的 `max_connections`。如果總數除了滾動更新期間之外都符合上限，且您的協調器支援，您也可以改讓協調器在啟動新副本之前先停止舊副本。 |
| 日誌：`could not connect to Postgres at boot, attempt 1 of 3`，且原因不是 `remaining connection slots are reserved` | 當 gateway 啟動時資料庫無法到達，例如在冷執行個體上，其網路仍在啟動中 | 如果 gateway 隨後完成啟動，則無需採取任何行動。當資料庫無法到達時，gateway 在結束前嘗試連線三次，間隔兩秒。如果它結束時顯示 `could not connect to Postgres`，請檢查 `store.postgres_url`（包括確認它只指定一個主機）以及到資料庫的網路路徑。如果嘗試逾時而不是被拒絕，請提高 [`store.connect_timeout_seconds`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#store) 以給每個嘗試更長的時間。 |
| 日誌：`Postgres <version> is below the supported floor` | 資料庫執行的 PostgreSQL 版本比您的 gateway 版本所支援的版本還舊。gateway 會繼續執行。 | 升級資料庫。若使用 PostgreSQL 11、12 或 13，您也可以改為升級 gateway，以符合 [PostgreSQL 需求](https://code.claude.com/docs/zh-TW/claude-apps-gateway#prerequisites)。 |
| `/oauth/callback` 顯示「Sign-in could not be completed」 | 電子郵件網域被拒絕、id\_token 驗證失敗，或 `email_verified` 明確為 `false`，gateway 始終拒絕且無法覆寫 | 檢查 `allowed_email_domains` 以及 IdP 是否傳回已驗證的 `email` 宣告。對於 `email_verified: false`，修正 IdP 端驗證。如果您的 IdP 在不同的宣告名稱下發出電子郵件，請設定 `oidc.email_claim`。 |
| 日誌：`token exchange failed request_id=<id>: id_token missing email claim` | IdP 預設不在 id\_token 中包含 `email`。此拒絕僅在設定 `allowed_email_domains` 時觸發；沒有它，遺漏的電子郵件會建立沒有電子郵件的工作階段 | 設定 IdP 在 id\_token 中發出 `email`。Okta：將 `email` 新增到自訂授權伺服器的 ID token 宣告。Entra：在應用程式註冊上新增 `email` 作為選用宣告。PingFederate：啟用發出 `email` 的 OpenID Connect 原則。如果 IdP 從 userinfo 端點提供 `email` 但不會在 id\_token 中包含它，例如 Okta 組織授權伺服器，請設定 `oidc.userinfo_fallback: true`。 |
| 日誌：`refresh failed request_id=<id>: invalid_token (…) (at userinfo_no_id_token, …)`，開發者每 `session.ttl_hours` 看到 `Cloud gateway session expired` | IdP 接受了重新整理 token 但沒有隨之傳回 id\_token，所以 gateway 詢問了 IdP 的 userinfo 端點以取得使用者的宣告。IdP 在那裡拒絕了重新整理的存取 token。gateway 回應 `temporarily_unavailable`，所以 Claude Code 保留重新整理 token 但無法更新工作階段。v2.1.260 之前的 gateway 版本記錄相同的行，但沒有 `(at …)` 詳細資訊。 | 設定 [`oidc.scope_on_refresh: true`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#oidc)（在 gateway v2.1.260 或更新版本中可用），以便重新整理請求再次要求 `openid`。某些 IdP（例如 Okta）僅在被要求時才在重新整理時傳回 id\_token。在 PingFederate 上，改為在 **Applications > OAuth > OpenID Connect Policy Management** 下啟用 **Return ID Token On Refresh Grant**。該金鑰不會改變 PingFederate 的行為。對於仍然省略它的其他 IdP，檢查 userinfo 端點是否接受由重新整理發出的存取 token。作為臨時解決方案，提高 [`session.ttl_hours`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#session)。請參閱[身分提供者設定](#identity-provider-setup)以了解取消佈建權衡。 |
| 開發者登入後，該工作階段的每個請求都失敗並出現 `431` 錯誤 | 每個請求的 `Authorization` 標頭中的工作階段 token 會列出開發者的 IdP 群組，因此對於屬於許多群組的開發者，標頭總計可能超過 gateway 接受的大小 | 請參閱[登入後請求標頭過大](#request-headers-too-large-after-sign-in)，了解適用的限制以及需要變更的內容 |
| 每個 Amazon Bedrock 請求都傳回 502；日誌顯示 `Could not load credentials from any providers` | 在 EC2 上，IMDSv2 的預設躍點限制為 1 會阻止來自容器內的執行個體中繼資料請求。啟動和 `/readyz` 仍然通過，因為 AWS SDK 在第一個請求時解析執行個體憑證，而不是在用戶端建構時 | 使用 `aws ec2 modify-instance-metadata-options --instance-id <id> --http-put-response-hop-limit 2` 提高躍點限制，或在啟動範本中設定它。變更適用於執行個體上的每個容器。在可用的地方優先使用 ECS 工作角色，它們從 ECS 容器憑證端點讀取憑證並完全避免變更，或在專用 gateway 執行個體上應用變更以限制暴露。 |
| 在尖峰負載時，回應開始緩慢或似乎掛起，或在上游健康時失敗，顯示 502 `all upstreams failed` | 副本開啟的請求比它一次傳送到上游的請求多，所以額外的請求在 gateway 內等待。在 `provider: anthropic` 上游上，等待時間超過 `timeouts.upstream_ttfb_ms` 的請求會放棄該上游，當沒有後來的上游提供它時會產生 502。日誌顯示包含 `client requests are open` 的警告。 | 新增副本，或提高每個副本上的限制。請參閱[並行上游請求](#concurrent-upstream-requests)。 |
| 在 `provider: anthropic` 以外的上游上，思考停頓較長的回合失敗。gateway 前面的代理伺服器記錄了一個保持開啟約 12.5 分鐘的請求，接著是一連串 `504` 錯誤 | Claude Code 結束了一個已傳送第一個回應事件、之後只帶有 keepalive ping 的串流。它在不使用串流的情況下重新傳送請求，而每個回覆所需的時間都超過代理伺服器的逾時。 | 為您的開發者提高 `CLAUDE_STREAM_IDLE_TIMEOUT_MS`。請參閱[長時間思考以代理伺服器逾時告終](#long-thinking-ends-in-proxy-timeouts)。 |
| 在 `provider: anthropic` 上，思考停頓較長的回合失敗。代理伺服器記錄了一個開啟約 20 分鐘的請求，接著是 `502` 或 `504` 錯誤 | Claude Code 結束了一個已傳送第一個回應事件、之後只帶有 keepalive ping 的串流。它在不使用串流的情況下重新傳送請求，而每個回覆所需的時間都超過 gateway 對上游的等待時間 `timeouts.upstream_ttfb_ms`，或超過代理伺服器的逾時。 | 為您的開發者提高 `CLAUDE_STREAM_IDLE_TIMEOUT_MS`。請參閱[在 Anthropic API 上游上的長時間思考](#long-thinking-on-an-anthropic-api-upstream)。 |
| 開發者的請求失敗，顯示 `API Error: 400 you aren't in a group that can use this gateway. Ask your administrator to add you to one` | 每個上游都有 [`groups` 清單](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#what-happens-when-a-developer-is-in-no-listed-group)，而開發者的工作階段不帶有任何列出的群組。 | 在您的 IdP 中將開發者新增到列出的群組，或將一個沒有 `groups` 的上游列在最後，以服務其他所有人。gateway 會在開發者下次重新整理 token 時再次讀取群組。如果 IdP 省略了群組，而其 userinfo 端點會傳回群組，請設定 [`oidc.userinfo_fallback: true`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#oidc)。 |
| IdP 錯誤：unknown or unsupported scope | IdP 拒絕它不認識的範圍 | 將 `oidc.scopes` 設定為您的 IdP 接受的確切清單；它必須包含 `openid`。預設值為 `openid profile email offline_access`。 |
| 設定 `oidc.scopes` 後工作階段不會無聲地更新 | `offline_access` 已從覆寫中刪除 | 如果您的 IdP 支援，請新增 `offline_access` 回來。沒有重新整理 token，開發者每 `session.ttl_hours` 重新執行瀏覽器登入。 |
| 瀏覽器顯示「This request came from another site and was blocked」 | 跨網站表單 POST，被阻止作為 CSRF 保護。嵌入或透過代理伺服器的頁面的預期行為 | 直接開啟驗證連結 |
| Chrome 使用「Refused to send form data … violates … Content Security Policy directive: form-action」阻止「Approve」按鈕，但相同頁面在 Safari 或 Firefox 中工作 | Chrome 對整個重新導向鏈強制執行 `form-action`。您的 IdP 重新導向到未列入允許清單的第二個主機。 | 將重新導向鏈中的每個其他來源新增到 `oidc.form_action_origins`。在「Approve」頁面上開啟 Chrome DevTools → Console 以查看哪個來源被阻止。 |
| 登入在 IdP 完成但回呼失敗，Chrome 中出現 CSP 錯誤或 Safari 中出現「this sign-in link has expired」 | IdP 通過 `response_mode=form_post` 傳回代碼，它通過 POST 自動提交到 `/oauth/callback`。Chrome 在嚴格 CSP 下阻止該操作；Safari 允許提交但回呼只讀取查詢字串。 | 確保您的 IdP 遵守 `response_mode=query`，gateway 明確要求它以便回呼是純重新導向 |
| 登入在本機工作但在 ALB 後面失敗 | `public_url` 仍然命名本機或內部 `http://` 來源，所以 IdP 獲得錯誤的 `redirect_uri` | 將 `listen.public_url` 設定為外部 `https://` 來源，並向 IdP 註冊 `<public_url>/oauth/callback` |
| 開發者重複看到信任提示 | TLS 憑證按副本或按請求輪換 | 在入口使用穩定憑證，或終止 TLS 一次並在內部通過純 HTTP 執行副本 |
| CLI `/login`：「Could not verify the gateway's TLS certificate」或 `SELF_SIGNED_CERT_IN_CHAIN` | gateway 的 TLS 鏈由 CLI 主機信任存放區中沒有的私有 CA 簽署 | Claude Code 在原生二進位檔上預設讀取 OS 信任存放區，在 Node 22.15 或更新版本上；[`CLAUDE_CODE_CERT_STORE`](https://code.claude.com/docs/zh-TW/network-config#ca-certificate-store)控制此行為。如果 CA 安裝在 OS 信任存放區中，請確保開發者使用目前執行時。否則在啟動前將 `NODE_EXTRA_CA_CERTS` 設定為 CA 憑證 PEM。首次連線指紋提示仍然適用。 |
| CLI `/login` 完成瀏覽器登入，然後工作階段結束，顯示 `Cloud gateway sign-in was not completed` 和 TLS 憑證不符 | 登入後的第一個請求上，gateway 提供了與 Claude Code 釘選的指紋不符的憑證，所以 Claude Code 沒有保留任何 gateway 憑證。常見原因是一個位址後面的副本提供不同的憑證，或網路路徑上的某個東西攔截 TLS。 | 為主機名稱提供一個憑證，例如在入口終止 TLS 一次，然後讓開發者再次執行 `/login`。如果該憑證與釘選的不同，Claude Code 會再次顯示[信任提示](https://code.claude.com/docs/zh-TW/claude-apps-gateway#connect-developers)，並警告憑證已變更。 |
| CLI `/login` 停止，顯示 `The gateway's TLS certificate changed during sign-in: it no longer matches the one you trusted` | 登入請求到達了一個憑證與開發者在 `/login` 開始時接受的憑證不符的伺服器：一個位址後面的副本提供不同的憑證、路徑上的 TLS 攔截，或登入進行中的憑證輪換。 | 為主機名稱提供一個憑證，然後讓開發者再次開始登入並在[信任提示](https://code.claude.com/docs/zh-TW/claude-apps-gateway#connect-developers)上檢查新憑證。 |

`Cloud gateway sign-in was not completed` 訊息會命名 gateway 主機名稱。當 Claude Code 同時具有釘選指紋和呈現的指紋時，訊息也會顯示每個的前 16 個字元。

如果 Claude Code 在 gateway 登入後報告 `couldn't load your organization's managed settings`，Claude Code 會命名原因、就地重新啟動並繼續對話。如果 Claude Code 無法重新啟動（例如在背景工作階段中），Claude Code 會結束工作階段並保留登入。

### 登入後請求標頭過大

當開發者屬於許多 IdP 群組時，其請求可能在登入後失敗並出現 `431` 錯誤。

當請求的標頭總計超過 256 KiB，或超過 [`limits.max_request_header_bytes`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#http-tuning)（若您有設定）時，gateway 會回應 `431`。它不會為這些請求寫入任何日誌行或稽核事件。v2.1.284 之前的 gateway 版本在超過 16 KiB 時即回應 `431`。

請從以下第一個適用於您 gateway 的項目開始：

* **早於 v2.1.284 的 gateway**：升級 gateway
* **已設定 `limits.max_request_header_bytes`**：提高該值或移除該設定鍵
* **以上皆不適用，或之後仍出現 `431`**：讓您的 IdP 發出較少的群組。[身分提供者設定](#identity-provider-setup)說明 Okta、Microsoft Entra ID 和 Google Workspace 如何提供群組

精簡群組宣告時，請保留您在以下設定中指定的群組，這些設定決定開發者的存取權、原則、上游和支出上限：

* **[`oidc.allowed_groups`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#oidc)**：決定誰可以登入
* **[`admin.admin_groups`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#admin)**：決定誰可以使用其 gateway 工作階段呼叫管理 API
* **[`managed.policies`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#managed) 中的 `match.groups`**：決定哪個原則適用於開發者
* **[上游](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#send-each-team-to-its-own-upstream)上的 `groups`**：決定哪些上游為開發者提供服務
* **`rbac_group` [支出上限](https://code.claude.com/docs/zh-TW/claude-apps-gateway-spend-limits.md)**：決定哪些群組上限適用於開發者

### 長時間思考以代理伺服器逾時告終

如果您的上游是 `provider: anthropic`，請改用[在 Anthropic API 上游上的長時間思考](#long-thinking-on-an-anthropic-api-upstream)：在該處您同樣要提高 `CLAUDE_STREAM_IDLE_TIMEOUT_MS`，但時間和錯誤有所不同。

如果回合在長時間思考後失敗，且您的代理伺服器記錄了一個開啟約 12.5 分鐘的請求，接著是一連串 `504` 錯誤，請在 gateway 原則中提高 [`CLAUDE_STREAM_IDLE_TIMEOUT_MS`](https://code.claude.com/docs/zh-TW/env-vars)。例如，若代理伺服器的閒置逾時為 240 秒，這一連串錯誤就是 10 個請求，每個都在 240 秒時被切斷。

* **第一個請求**：一個傳送了第一個回應事件 `message_start`，之後在 Claude 思考期間只傳送 ping 的串流。在預設設定下，Claude Code 會在約 12.5 分鐘後結束該串流。
* **其他 10 個**：同一個請求，[不使用串流](https://code.claude.com/docs/zh-TW/errors.md#streaming-response-ended-before-any-complete-data-was-received)傳送後再重試，預設總共傳送 10 次。這些請求不會收到 ping，因此回覆較慢時就會觸及代理伺服器的逾時。

此修正不需要延長代理伺服器的逾時。如果您只提高代理伺服器的逾時，一旦回覆所需時間超過 Claude Code 本身的等待時間（預設為 300 秒），不使用串流的請求仍會失敗。

#### 確認原因

讓開發者使用 `claude --debug-file ./claude-debug.txt` 重現失敗，然後在該檔案中搜尋這一行：

```text theme={null}
Error streaming, falling back to non-streaming mode: Stream idle timeout - no chunks received
```

如果您的開發者已將 [`CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK`](https://code.claude.com/docs/zh-TW/env-vars) 設定為 `1`，您不會看到不使用串流的請求，且回合會以 `API Error: Stream idle timeout - no chunks received` 結束。同樣的修正適用。

#### 選擇值

選擇一個第二欄能涵蓋您最長思考停頓的 `CLAUDE_STREAM_IDLE_TIMEOUT_MS` 值；如果您不知道最長停頓為多久，請從 `1800000` 開始。串流僅靠 ping 維持的時間，可比該值長約 7.5 分鐘：

| `CLAUDE_STREAM_IDLE_TIMEOUT_MS` | 串流僅靠 ping 可維持的時間 |
| - | - |
| `300000`，預設值 | 約 12.5 分鐘 |
| `900000` | 約 22.5 分鐘 |
| `1800000` | 約 37.5 分鐘 |

如果上游停止回應而 gateway 持續傳送 ping，您的開發者也會等待這麼久，Claude Code 才會放棄該串流。完全沒有任何資料的連線仍會在 5 到 6 分鐘後結束，因為[本文閒置逾時](https://code.claude.com/docs/zh-TW/network-config.md#streaming-idle-watchdogs)不受此變數影響。

#### 在原則中提供該值

將 `env` 項目新增到 `gateway.yaml` 中每個已向您要涵蓋的開發者提供 Claude Code 設定的原則。將它放在該原則既有的 `code`、`cli` 或 `settings` 鍵下。若要先試用該值，請從符合單一群組的原則開始。請參閱 [`managed`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#managed) 了解原則如何比對與繼承。此範例將該項目新增到以 `cli` 為鍵的 `match: {}` 原則：

```yaml theme={null}
managed:
  policies:
    - match: {}
      cli:
        env:
          CLAUDE_STREAM_IDLE_TIMEOUT_MS: "1800000"
```

使用 `cli` 鍵時，您會涵蓋終端機、IDE 擴充功能和 Agent SDK 工作階段。關於 Claude Desktop 的 Code 分頁，請參閱[選擇 `cli` 或 `code`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#choose-cli-or-code)。

重新啟動 gateway，使其讀取編輯後的檔案。然後讓開發者重新啟動 Claude Code 以取得 `CLAUDE_STREAM_IDLE_TIMEOUT_MS`。

### 在 Anthropic API 上游上的長時間思考

如果 `provider: anthropic` 是該模型唯一的上游，且您的代理伺服器記錄了一個開啟約 20 分鐘的請求，接著是 `502` 或 `504` 錯誤，請在 gateway 原則中提高 [`CLAUDE_STREAM_IDLE_TIMEOUT_MS`](https://code.claude.com/docs/zh-TW/env-vars)。

* **長時間的請求**：一個傳送了 `message_start`，之後在 Claude 思考期間只傳送 ping 的串流。在預設設定下，Claude Code 會在約 20 分鐘後結束它；提高該變數後則會更晚結束。
* **錯誤**：Claude Code 接著[不使用串流](https://code.claude.com/docs/zh-TW/errors.md#streaming-response-ended-before-any-complete-data-was-received)傳送的請求。每個請求都會以 gateway 的 `502` 失敗，或者若代理伺服器的逾時比 gateway 的等待時間短，則以代理伺服器的 `504` 失敗。該等待時間是 [`timeouts.upstream_ttfb_ms`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#http-tuning)，此修正不需要提高它。

若要確認原因，請參閱[確認原因](#confirm-the-cause)。

選擇時間足以涵蓋您最長思考停頓的值：預設值約為 20 分鐘，`900000` 約為 30 分鐘，`1800000` 約為 45 分鐘。然後依照[在原則中提供該值](#deliver-the-value-in-a-policy)進行。

## 相關

* [Claude 應用程式閘道概述](https://code.claude.com/docs/zh-TW/claude-apps-gateway)：快速入門和開發人員連接
* [設定參考](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md)：每個 `gateway.yaml` 選項

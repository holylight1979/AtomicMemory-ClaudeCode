<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/claude-apps-gateway | lastmod: 2026-11-02 | section: Administration / Gateways -->
> 來源：https://code.claude.com/docs/zh-TW/claude-apps-gateway（官方 zh-TW，lastmod 2026-11-02）｜分類：Administration › Gateways｜EN 摘要：Run Claude Code through Amazon Bedrock, Claude Platform on AWS, Google Cloud, or Microsoft Foundry behind a self-hosted gateway with SSO sign-in, per-group model access, and OTLP telemetry.

# Amazon Bedrock、Claude Platform on AWS、Google Cloud 和 Microsoft Foundry 的 Claude 應用程式閘道

> 透過自託管閘道在 Amazon Bedrock、Claude Platform on AWS、Google Cloud 或 Microsoft Foundry 上執行 Claude Code，具備 SSO 登入、按群組模型存取和 OTLP 遙測功能。

> [!NOTE]
>
> Claude 應用程式閘道是為必須或偏好透過自己的雲端提供商路由推論的組織而設計的，例如為了滿足[資料駐留](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#compliance-posture)要求。如果您沒有此要求，並且想要存取其他功能，例如 SCIM 佈建或 Claude Code 網頁和行動版本，Claude Enterprise 可能更適合。請參閱[功能可用性](https://code.claude.com/docs/zh-TW/feature-availability.md)頁面，以取得所有部署方法的完整比較。
>
> Claude Code 一次只使用一種登入：閘道登入會取代 Claude for Teams 或 Enterprise 登入。閘道工作階段不會擷取您在 claude.ai 管理主控台中設定的[伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)，因此請從閘道的 [`managed` 區塊](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#managed)提供這些設定。請勿在該區塊中加入 `forceLoginMethod` 和 `forceLoginOrgUUID`，否則[部分已登入的工作階段會在啟動時結束](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#client-side-managed-settings)。請參閱[可用性和限制](#availability-and-limitations)，了解閘道工作階段會失去哪些功能。

Claude 應用程式閘道是一個自託管服務，位於開發人員的 Claude Code 用戶端和模型提供商之間。開發人員使用您的企業身份提供商 (IdP) 登入，而不是持有 API 金鑰或雲端認證。閘道持有上游認證，按 IdP 群組強制執行模型存取和[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)，並將使用情況遙測轉發到您自己的可觀測性堆疊。

它包含在 `claude` 二進位檔中，因此在筆記型電腦上執行 Claude Code 的相同可執行檔可以使用 `claude gateway --config gateway.yaml` 執行閘道伺服器。

本頁涵蓋：

* [為什麼使用 Claude 應用程式閘道](#why-claude-apps-gateway)、它相比自行執行增加了什麼，以及何時其他解決方案更合適
* 一個[快速入門](#quickstart)，包含[先決條件](#prerequisites)，可將閘道從零開始設定為已登入的開發人員
* [連接開發人員](#connect-developers)，包括透過受管設定設定閘道 URL
* [可用性和限制](#availability-and-limitations)，涵蓋哪些 Claude Code 功能可透過閘道運作，以及伺服器支援什麼

相關頁面會更深入地介紹。[配置參考](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md)涵蓋快速入門寫入的 YAML 檔案中的每個選項，[部署指南](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md)涵蓋每個 IdP 的設定、Kubernetes 和 Cloud Run 部署，以及操作。

## 為什麼使用 Claude 應用程式閘道

[閘道概述](https://code.claude.com/docs/zh-TW/gateways.md)涵蓋閘道的功能以及為什麼要執行一個。Claude 應用程式閘道是 Anthropic 自己的閘道，內建於 `claude` 二進位檔中，並與每個 Claude Code 版本一起測試，因此它會轉發 Claude Code 發送的 `anthropic-beta` 值和請求欄位，無需操作員維護單獨的允許清單。部署後，它為您提供：

* **憑證**：上游 API 金鑰或雲端憑證僅存在於您的基礎設施中。開發人員使用公司 SSO 進行身分驗證並接收短期的持有人 token，因此離職處理在您的 IdP 中進行。取消佈建使用者後，其閘道存取會在工作階段生命週期內過期，預設為一小時。
* **存取控制**：您的 IdP 群組對應到模型允許清單、[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)原則和[上游](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#send-each-team-to-its-own-upstream)。閘道在伺服器端強制執行模型存取，拒絕非授予模型的請求，並選擇每個群組的受管設定原則，CLI 在[受管設定層級](https://code.claude.com/docs/zh-TW/settings.md#settings-precedence)套用該原則。不同的團隊獲得不同的模型、工具和權限，開發人員無法覆寫其原則鎖定的內容。
* **設定傳遞**：閘道本身將受管設定傳遞給已登入的用戶端，取代來自 claude.ai 管理員主控台的[伺服器管理設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)。
* **遙測**：每個設定的目的地接收[OpenTelemetry Protocol (OTLP) 指標](https://code.claude.com/docs/zh-TW/monitoring-usage.md)，預設包含 token 計數、模型、使用者身分和延遲，日誌和追蹤則可按目的地選擇加入。
* **上游路由**：用戶端向閘道使用 Anthropic Messages API，閘道為每個上游進行轉換，無論是 Amazon Bedrock、[AWS 上的 Claude Platform](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md)、Google Cloud 的 Agent Platform、Microsoft Foundry 或 Anthropic API，並在它們之間進行故障轉移。您可以變更區域、提供商或故障轉移順序，而開發人員無需察覺或重新設定。

![圖表顯示 Claude Code 用戶端和 Claude Desktop 透過 HTTPS 和持有人 token 連接到您基礎設施內的自行託管 Claude 應用程式閘道，該閘道透過您的 IdP 讓使用者登入，在 PostgreSQL 中儲存身分驗證狀態，將遙測中繼到您的 OTLP 收集器，並將推理轉發到 Amazon Bedrock、AWS 上的 Claude Platform、Google Cloud、Microsoft Foundry 或 Anthropic API](https://mintcdn.com/claude-code/VbyXug8hBU9UK6oT/images/claude-gateway-architecture.svg?fit=max\&auto=format\&n=VbyXug8hBU9UK6oT\&q=85\&s=9e4f1190fc56718144190a3db61c63af)

> [!NOTE]
>
> 閘道自己的資料平面不會向 Anthropic 基礎設施發送任何內容，除非 Anthropic API 是設定的上游。您控制遙測、稽核日誌、受管設定和開發人員的 IdP 身分去向，閘道不會將它們中的任何一個發送給 Anthropic。對於 CLI 程序可能發送的其餘流量以及如何關閉它，請參閱[合規性態勢](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#compliance-posture)。

有關哪些 Claude Code 功能可透過閘道運作以及伺服器本身支援什麼，請參閱下面的[可用性和限制](#availability-and-limitations)。有關成本、繞過、執行多個閘道和無伺服器平台等決策，請參閱[部署指南](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#deployment)。

### 其他閘道實現

如果您已經執行滿足您需求的 LLM 閘道或 API 閘道，請繼續使用它；[其他 LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)涵蓋如何針對它設定 Claude Code。

[閘道相容性指南](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md)記錄了 Claude Code 對任何閘道的期望：它呼叫的端點、要轉發的標頭和正文欄位，以及當它們被剝離時停止運作的內容。執行中的 Claude 應用程式閘道也在 `GET /protocol` 提供其自己的協定參考，其中描述了它向 Claude Code 用戶端公開的端點：SSO 登入、推理、受管設定傳遞、模型探索和遙測。使用 `curl https://claude-gateway.internal.example.com/protocol` 從任何已部署的閘道（例如下面[快速入門](#quickstart)產生的閘道）取得它。

協定的重大變更會提前宣佈，但不保證無限期的向後相容性。

> [!NOTE]
>
> 閘道登入 token 識別的是核准該登入的開發人員，而非使用它的程式。Claude Code 登入時沒有自己的用戶端 ID 或密碼，因此閘道無法驗證是哪個程式在登入。任何用戶端都可以設定 `User-Agent` 和其他請求欄位，因此請將它們用於路由或指標，而非作為請求來自 Claude Code 的證明。

## 快速入門

本快速入門將帶您走過最精簡的路徑：在您的 IdP 中註冊 OAuth 用戶端、撰寫 `gateway.yaml`、使用 Docker Compose 將閘道與 Postgres 一起執行，並端對端驗證登入流程。本文使用 Amazon Bedrock 上游；Claude Platform on AWS、Google Cloud 的 Agent Platform、Microsoft Foundry 與 Anthropic API 也同樣受支援，只需依照[設定參考](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#upstreams)所示替換 `upstreams` 區塊即可。完成後，您將擁有一個開發人員可以透過 `/login` 登入的閘道。

> [!NOTE]
>
> **部署於您的私人網路上。** Claude Code 只會連線到位址為私人位址的閘道。這是一項安全防護措施，因為受信任的閘道可以推送在開發人員機器上執行命令的設定。請將閘道置於內部負載平衡器或 VPN 之後，並為其指定僅解析為私人 IP 的主機名稱。如果您的內部網路使用組織所擁有的公用 IPv4 位址空間進行編號，請參閱[允許閘道位於您擁有的公用位址空間](#allow-a-gateway-on-public-address-space-you-own)。

### 先決條件

開始之前，請先準備好以下項目：

| 您需要 | 詳細資訊 |
| - | - |
| Claude Code v2.1.195 或更新版本 | `claude gateway` 子命令與閘道登入流程隨 v2.1.195 推出。較早的公開建置版本不包含這些功能。執行閘道伺服器的機器以及每位開發人員的機器都必須使用 v2.1.195 或更新版本；請執行 `claude update` 以取得最新版本。[Claude Platform on AWS 上游](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#claude-platform-on-aws)需要閘道伺服器上的 Claude Code 為 v2.1.198 或更新版本。 |
| OpenID Connect (OIDC) 身分識別提供者 | Okta、Microsoft Entra ID、Google Workspace、Keycloak 或 Dex，或任何其他符合 OIDC 規範的 IdP，例如 PingFederate。閘道會對其執行標準的 OIDC 探索與授權碼流程。不支援 SAML 與 LDAP。 |
| PostgreSQL 11 或更新版本 | 支援裝置登入流程與速率限制計數器。受管理的 PostgreSQL 服務亦可使用，包括最小的方案；請參閱[支援哪些資料庫](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#postgres)。搭配[支出上限](https://code.claude.com/docs/zh-TW/claude-apps-gateway-spend-limits.md)使用時，它也會保存應備份的持久性支出、稽核與身分資料表。建議透過 `?sslmode=require` 使用 TLS。PostgreSQL 11、12 與 13 需要閘道伺服器上的 Claude Code 為 v2.1.290 或更新版本。PostgreSQL 專案已不再維護這些版本，因此請盡可能使用較新的版本。 |
| 模型上游 | Amazon Bedrock 憑證、Claude Platform on AWS 憑證、Google Cloud 憑證、Microsoft Foundry 資源或 Anthropic API 金鑰。支援具備容錯移轉的多個上游。 |
| HTTPS | 開發人員的筆記型電腦以及用於登入的任何瀏覽器都必須能透過 `https://` 連線到閘道；閘道會在同一個接聽程式上提供裝置驗證頁面。請透過 `listen.tls` 提供 TLS 憑證，或在終止 TLS 的 ingress 之後執行，兩種情況下都請將 `listen.public_url` 設為外部來源。在 `/login` 時，只有當閘道主機為迴路位址（`localhost`、`127.0.0.1` 或 `::1`）時，Claude Code 才接受純 `http://` 來源。 |
| 私人網路位址 | 在 `/login` 時，Claude Code 要求閘道的主機名稱或 IP 位址僅解析為私人位址：RFC 1918、鏈路本機、CGNAT `100.64.0.0/10`、IPv6 ULA `fc00::/7` 或迴路位址。對於您自行託管的閘道，任何不在您所宣告區塊內的公用位址都會遭到拒絕；請參閱部署指南中的[威脅模型](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#threat-model-summary)。如果開發人員機器透過公司代理伺服器路由 HTTPS，登入時也要求代理伺服器主機解析為私人位址；若非如此，請將閘道主機加入 `NO_PROXY`，讓 CLI 直接連線。如果您的內部網路使用組織所擁有的公用 IPv4 位址空間進行編號，請[宣告這些區塊](#allow-a-gateway-on-public-address-space-you-own)，讓 `/login` 接受位於該處的閘道。 |
| Linux 執行環境 | 閘道伺服器只能在原生 Linux 二進位檔上執行。macOS 可用於本機開發。不支援以 Windows 作為伺服器平台。 |

### 步驟

**1. 在您的 IdP 中註冊 OAuth 用戶端**

請先決定閘道的主機名稱，因為重新導向 URI 必須與其相符。建立新的 OIDC Web 應用程式，並將重新導向 URI 設為 `https://claude-gateway.<your-domain>/oauth/callback`，其中主機與您在步驟 3 中設定為 [`listen.public_url`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#listen) 的值相同。記下 `client_id` 與 `client_secret`。各 IdP 的說明請參閱[身分識別提供者設定](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#identity-provider-setup)。

**2. 佈建 PostgreSQL 資料庫**

請使用 PostgreSQL 11 或更新版本。最小的受管理方案即已足夠。閘道會在開機時執行自己的 schema 遷移，因此資料庫角色需要建立與變更資料表的權限；請參閱 [`store`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#store)。

**3. 撰寫 gateway.yaml**

機密資訊透過 `${ENV_VAR}` 展開讀取，因此檔案本身可以放在版本控制中。請使用在您網路上解析為私人 IP 的 `public_url` 主機名稱，因為 `/login` 會拒絕公用位址。最精簡的設定包含五個區段，其他所有欄位皆有預設值：

```yaml gateway.yaml theme={null}
listen:
  host: 0.0.0.0
  port: 8080
  # Required unless host is a loopback address. Used for the IdP
  # redirect_uri and the discovery document.
  public_url: https://claude-gateway.internal.example.com

oidc:
  issuer: https://login.example.com        # must serve /.well-known/openid-configuration
  client_id: 0oa1example2
  client_secret: ${OIDC_CLIENT_SECRET}
  allowed_email_domains: [example.com]        # reject id_tokens outside your org
  userinfo_fallback: true                  # for IdPs whose id_token omits email/groups; harmless otherwise

session:
  jwt_secret: ${GATEWAY_JWT_SECRET}        # openssl rand -base64 32
  ttl_hours: 1                             # also bounds revocation latency on IdP deprovision

store:
  postgres_url: ${GATEWAY_POSTGRES_URL}    # add ?sslmode=require for managed Postgres

upstreams:
  - provider: bedrock
    region: us-east-1
    auth: {} # empty: AWS default credential chain
# (IRSA, EC2/ECS task role, env vars, ~/.aws)

# Models are translated per upstream automatically. The built-in catalog
# maps claude-opus-4-8 to us.anthropic.claude-opus-4-8 and so on for every
# Bedrock-supported Claude model. Set false and add a `models:` list to
# expose only specific models.
auto_include_builtin_models: true
```

此設定足以搭配預設的 Amazon Bedrock 模型目錄建立可運作的登入流程。執行後，您可以透過 [`managed.policies`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#managed) 新增各群組的 RBAC 與受管設定，透過 [`telemetry`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#telemetry) 新增遙測分送，並透過 [`models`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#models) 新增多上游容錯移轉、佈建輸送量 ARN 或非美國區域。

> [!NOTE]
>
> Amazon Bedrock 上游需要一個 AWS 主體，該主體須對 `inference-profile/us.anthropic.*` ARN 及其底層的 `foundation-model/anthropic.*` ARN 都具備 `bedrock:InvokeModel` 與 `bedrock:InvokeModelWithResponseStream` 權限。此外，也需要從 Bedrock 主控台的 Model catalog 為該帳戶提交 Anthropic 的一次性使用案例表單。
>
> 請透過 EKS 上的 IRSA、ECS 任務角色或 EC2 執行個體設定檔提供憑證，而非使用靜態金鑰。[`upstreams` 參考](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#upstreams)包含完整的 IAM 詳細資訊、跨雲端憑證對照表，以及其他提供者的 `auth` 區塊。

**4. 執行**

以 `claude` 二進位檔建置符合[映像檔需求](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#container-image)的容器映像檔，然後將其與 Postgres 一起執行。Compose 檔案將映像檔參照為 `registry.example.com/claude-gateway:2.1.198`；請替換為您自己的 registry 與映像檔標籤：

```yaml docker-compose.yaml theme={null}
services:
  gateway:
    image: registry.example.com/claude-gateway:2.1.198
    ports: ["8080:8080"]
    volumes: ["./gateway.yaml:/etc/claude/gateway.yaml:ro"]
    environment:
      OIDC_CLIENT_SECRET: ${OIDC_CLIENT_SECRET}
      GATEWAY_JWT_SECRET: ${GATEWAY_JWT_SECRET}
      GATEWAY_POSTGRES_URL: postgres://gw:pw@postgres/gateway
      # AWS credentials: in production, omit these and use an instance
      # role. For local Compose testing, pass through your own:
      AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID}
      AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY}
      AWS_SESSION_TOKEN: ${AWS_SESSION_TOKEN}
    depends_on:
      postgres:
        condition: service_healthy
  postgres:
    image: postgres:16-alpine
    environment: { POSTGRES_USER: gw, POSTGRES_PASSWORD: pw, POSTGRES_DB: gateway }
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U gw"]
      interval: 5s
    volumes: ["pgdata:/var/lib/postgresql/data"]
volumes: { pgdata: }
```

閘道是單一的 Linux 二進位檔，它會讀取設定、連線到 Postgres 並套用其 schema 遷移、對您的 IdP 執行 OIDC 探索、建置上游用戶端，然後開始接聽。

對於設定、Postgres 連線、OIDC 探索與上游用戶端建構，開機採取失敗即關閉（fail-closed）的方式。如果其中任何一項無法連線或設定錯誤，閘道會以錯誤結束，而不會在降級狀態下提供流量。

成功開機並不代表推論路徑已通過驗證，因為 Amazon Bedrock 與 Google Cloud 的 Agent Platform 執行個體憑證是在第一個請求時解析，而非在開機時。

請觀察 stderr 中的開機順序。日誌行使用 `[gateway] <timestamp> <level> <message>` 格式，稽核事件為帶有 `evt` 欄位的單行 JSON，而啟動橫幅（以下省略）會印在遷移行與接聽行之間。全新的資料庫會為每個 schema 遷移印出一行 `migration N applied`；已完成遷移的資料庫則不會印出。您應該會依序看到：

```text theme={null}
{"ts":"2026-06-10T17:03:21.114Z","evt":"config.load","path":"/etc/claude/gateway.yaml","sha256":"…"}
[gateway] 2026-06-10T17:03:21.395Z info waiting for migration lock (another replica may be migrating; check pg_locks for key 6775156 if this persists)
[gateway] 2026-06-10T17:03:21.408Z info migration 1 applied
…
[gateway] 2026-06-10T17:03:21.431Z info migration 6 applied
[gateway] 2026-06-10T17:03:21.512Z info claude gateway listening on http://0.0.0.0:8080
```

閘道也會記錄一則 `access_control.allow_cidrs` 為空的警告。在此情況下這是預期的，因為在您設定允許清單之前，不會限制閘道服務哪些用戶端位址。[`access_control` 參考](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#http-tuning)列出了建議的範圍。

如果開機在 `claude gateway listening on` 行之前就結束，stderr 的最後一行會指出問題所在：

* 無法連線的 Postgres
* 沒有 DDL 權限的 Postgres 角色
* 無法連線或無效的 OIDC 探索文件
* 違反設定 schema，並附上有問題的欄位路徑

修正後重新啟動即可。

如果您已經有終止 TLS 的 ingress，請略過 Compose，直接以 `claude gateway --config gateway.yaml` 執行二進位檔。將 `public_url` 設為 ingress 來源，並將 `listen` 繫結至迴路位址或叢集內部位址。

**5. 驗證身分驗證使用介面**

在與開發人員分享閘道之前，透過三項檢查確認閘道能夠驗證真實使用者的身分。

範例使用閘道的公用 URL；對於沒有 ingress 的本機 Compose 設定，請在前兩項檢查中替換為 `http://localhost:8080`。第三項檢查會開啟由 `public_url` 建構的 `verification_uri_complete`，因此對於本機 Compose，請在 `gateway.yaml` 中設定 `public_url: http://localhost:8080`，並在步驟 1 的 OAuth 用戶端上將 `http://localhost:8080/oauth/callback` 新增為第二個重新導向 URI，因為閘道會從 `public_url` 建構 IdP 的 `redirect_uri`。接著驗證連結便會在您的本機瀏覽器中開啟。

在 Windows PowerShell 中，請執行 `curl.exe`；單純的 `curl` 是 `Invoke-WebRequest` 的別名，會拒絕這些旗標。

首先，擷取探索文件，以確認閘道已啟動、設定有效，且所有開機檢查皆已通過：

```bash theme={null}
curl -s https://claude-gateway.internal.example.com/.well-known/oauth-authorization-server | jq
```

```json theme={null}
{
  "issuer": "https://claude-gateway.internal.example.com",
  "device_authorization_endpoint": "…/oauth/device_authorization",
  "token_endpoint": "…/oauth/token",
  "grant_types_supported": ["urn:ietf:params:oauth:grant-type:device_code", "refresh_token"]
}
```

回應還包含其他欄位，例如 `response_types_supported` 與 `scopes_supported`。

其次，請求裝置授權，以確認裝置登入流程可以運作，且 Postgres 可連線並可寫入：

```bash theme={null}
curl -s -X POST https://claude-gateway.internal.example.com/oauth/device_authorization | jq
```

```json theme={null}
{
  "device_code": "…",
  "user_code": "WDJB-MJHT",
  "verification_uri": "https://claude-gateway.internal.example.com/device",
  "verification_uri_complete": "https://claude-gateway.internal.example.com/device?user_code=WDJB-MJHT",
  "expires_in": 600,
  "interval": 5
}
```

第三，在瀏覽器中開啟 `verification_uri_complete` 並確認代碼，以測試瀏覽器環節。您應該會被重新導向至 IdP 的登入頁面，登入後再回到閘道並看到已登入的確認畫面。

請以第一個失敗的檢查來定位問題：

* **第一項檢查失敗**：開機未完成；請檢查 stderr
* **第二項檢查失敗**：閘道無法連線到 Postgres，或角色無法寫入；請檢查連線字串與授權
* **第三項檢查未到達 IdP**：請檢查 IdP 的重新導向 URI 是否與 `https://<gateway>/oauth/callback` 完全相符
* **第三項檢查到達 IdP 但帶著錯誤被退回**：請查看閘道的稽核日誌，其中會記錄每次身分驗證遭拒的原因，例如 `email domain not allowed`

**6. 讓開發人員登入**

最後這個步驟是在開發人員的機器上進行，而非在伺服器上。在該機器的[受管設定檔](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)中，將 `forceLoginMethod` 設為 `"gateway"`、將 `forceLoginGatewayUrl` 設為閘道的 `public_url`，並將 `parentSettingsBehavior` 設為 `"merge"`，然後執行 `/login`，在 **Cloud gateway** 畫面上按下 Enter，並完成瀏覽器登入。下方的[設定閘道 URL](#set-the-gateway-url) 說明了這三個設定鍵，以及如何將其分發到每位開發人員的機器。

## 連接開發人員

開發人員只需從自己的筆記型電腦透過一次瀏覽器登入，即可使用公司工作帳戶進行連接。他們不需要 claude.ai 帳戶、API 金鑰或訂閱，因為對模型的請求會透過閘道並使用組織的上游憑證傳送。連接由您透過 MDM 推送的[用戶端受管設定](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#client-side-managed-settings)驅動，本節說明管理員需要設定的內容。

CLI 會在首次連接時擷取閘道 TLS 末端憑證的指紋，並依主機名稱將其釘選。它會在登入期間、靜默的工作階段更新時，以及擷取受管設定時再次檢查該釘選，而推論請求則使用標準 TLS 驗證，不檢查釘選。透過 HTTPS 代理伺服器路由的請求會略過釘選檢查，因此請將閘道主機加入 `NO_PROXY`，讓這些請求直接連線。

請將預期的 SHA-256 指紋與閘道 URL 一起公布，讓開發人員有可比對的依據。`/login` 提示會以小寫十六進位、不含冒號的形式顯示指紋的前 16 個字元。若要從憑證檔案以該形式列印完整指紋，請執行：

```bash theme={null}
openssl x509 -noout -fingerprint -sha256 -in cert.pem | cut -d= -f2 | tr -d : | tr 'A-F' 'a-f'
```

憑證輪替時，每位開發人員都會再次看到信任提示，因此請將輪替視為計畫中的事件，並重新公布指紋。如果您的閘道原則包含[需要核准的設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md#security-approval-dialogs)，開發人員在接受新憑證後也會再次看到該核准對話方塊，因為 Claude Code 會將[核准記憶](https://code.claude.com/docs/zh-TW/server-managed-settings.md#approval-memory)與釘選的憑證綁定。

閘道可以在其 token 回應中傳回選用的 `email` 欄位，以指出登入所使用的帳戶。若有傳回，開發人員會在 Claude Code 儲存憑證前確認該帳戶。確認登入後，`/status` 會顯示該帳戶。

此確認需要開發人員電腦上的 Claude Code v2.1.275 或更新版本；低於該版本的用戶端會忽略此欄位。`claude` 二進位檔中的閘道伺服器不會傳回此欄位，因此其登入會在不經確認的情況下完成。

開發人員登入後，[模型選擇器](https://code.claude.com/docs/zh-TW/model-config.md)會顯示其 `availableModels` 允許清單中的模型。受管設定會在啟動時套用並每小時更新，遙測則會路由至您的收集器。

工作階段會在 `ttl_hours` 到期前靜默更新。當 IdP 取消佈建後更新失敗時，Claude Code 會提示開發人員重新登入。

### 設定閘道 URL

有三個鍵要放在您透過 MDM 或直接在磁碟上部署的各作業系統[受管設定檔](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)中。對於沒有受管設定的電腦，請改參閱[在使用者設定中設定閘道 URL](#set-the-gateway-url-in-user-settings)。`forceLoginMethod` 和 `forceLoginGatewayUrl` 會讓 `/login` 直接開啟 **Cloud gateway** 畫面並填入 URL，而 `parentSettingsBehavior: "merge"` 則讓 Claude Desktop 能將閘道的對外連線允許清單傳遞給它所啟動的 Claude Code 工作階段，詳見[將原則傳遞給 Claude Desktop 工作階段](#deliver-policy-to-claude-desktop-sessions)：

```json theme={null}
{
  "forceLoginMethod": "gateway",
  "forceLoginGatewayUrl": "https://claude-gateway.internal.example.com",
  "parentSettingsBehavior": "merge"
}
```

開發人員按下 Enter 即可連接。[首次連接的 TLS 指紋提示](#connect-developers)仍會出現。檔案部署到電腦上之後，尚未完成閘道登入的開發人員會看到 [Administrator policy requires a Cloud gateway sign-in](https://code.claude.com/docs/zh-TW/errors.md#administrator-policy-requires-a-cloud-gateway-sign-in) 中所述的其中一則訊息。透過 `CLAUDE_CODE_USE_BEDROCK` 等環境變數選擇雲端供應商的開發人員不需要閘道登入。

登入選擇器中沒有閘道選項，而在受管設定中只設定 `forceLoginMethod` 而不設定 URL，會讓開發人員停留在「Contact your IT administrator」訊息。登入相關的鍵應放在您推送到電腦的檔案中，而非閘道的 `managed.policies[].cli` 區塊，因為後者只會送達已連接的用戶端。

#### 在使用者設定中設定閘道 URL

在沒有受管設定的電腦上，請讓每位開發人員將 `forceLoginMethod` 和 `forceLoginGatewayUrl` 加入自己的使用者設定檔 `~/.claude/settings.json`。這需要開發人員電腦上的 Claude Code v2.1.295 或更新版本。此範例指定位於 `claude-gateway.internal.example.com` 的閘道：

```json theme={null}
{
  "forceLoginMethod": "gateway",
  "forceLoginGatewayUrl": "https://claude-gateway.internal.example.com"
}
```

當開發人員在 Claude Code 提示字元執行 `/login` 時，**Cloud gateway** 畫面會以該位址開啟，開發人員按下 Enter 即可連接。[首次連接的 TLS 指紋提示](#connect-developers)仍會出現。以此方式設定的鍵有以下限制：

* **僅限使用者設定**：Claude Code 只從 `~/.claude/settings.json` 讀取這兩個鍵，不會從專案的 `.claude/settings.json` 或 `.claude/settings.local.json` 讀取。
* **受管設定會停用它們**：一旦管理員的設定透過受管設定檔、macOS plist 或 Windows HKLM 原則，或[原則輔助程式](https://code.claude.com/docs/zh-TW/settings-reference.md#policyhelper)送達電腦，Claude Code 就會忽略使用者設定中指定的閘道。

### 允許位於您所擁有公用位址空間上的閘道

有些組織以自己擁有的公用 IPv4 區塊為內部網路編號，例如電信業者自有的位址空間或舊有的 `/8`，因此其閘道沒有私人位址。請在 `gatewayInternalNetworks` 受管設定中列出這些區塊。如此一來，當開發人員的電腦從某個已列出區塊內的位址連線到同一區塊內的閘道時，`/login` 便會接受該閘道。這需要開發人員電腦上的 Claude Code v2.1.268 或更新版本；較早的版本會忽略此鍵並套用私人位址規則。

> [!WARNING]
>
> `gatewayInternalNetworks` 適用於恰好以公用位址空間編號的內部網路。它並不會讓將閘道暴露在網際網路上變得安全：受信任的閘道可以推送在開發人員電腦上執行命令的設定。
>
> 請透過防火牆或負載平衡器規則，讓閘道無法從您的網路外部存取。將閘道的 [`access_control.allow_cidrs`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#http-tuning) 設定為您在此宣告的相同區塊，讓閘道本身拒絕來自其他任何地方的用戶端。若位於負載平衡器或 ingress 之後，也請將 `listen.trusted_proxies` 設定為該前端，否則閘道會以前端本身的位址而非開發人員的位址來比對 `allow_cidrs`。

請將此鍵加入與登入鍵相同的受管設定來源：受管設定檔、MDM 設定描述檔或登錄原則。Claude Code 會忽略使用者、專案及伺服器受管設定中的此鍵。

此範例宣告一個區塊。請將 `203.0.113.0/24` 替換為您自己的區塊。這是文件用的範圍，Claude Code 會拒絕此類範圍。

```json theme={null}
{
  "gatewayInternalNetworks": ["203.0.113.0/24"]
}
```

Claude Code 會在 `/login` 聯繫任何閘道之前驗證該清單：

* 每個項目都是一個 IPv4 區塊，以其第一個位址加上 `/8` 到 `/32` 的前置長度表示。
* 清單最多包含四個區塊，且任兩個區塊都不能重疊。
* 任何區塊都不能與私人位址空間重疊：`10.0.0.0/8`、`172.16.0.0/12`、`192.168.0.0/16`、`127.0.0.0/8`、`169.254.0.0/16` 和 `100.64.0.0/10`。`/login` 已經會接受位於這些空間中的閘道，無須此鍵。
* 任何區塊都不能與絕不會是組織網路的空間重疊：VPN 和 NAT64 用戶端作為本機位址使用的 `198.18.0.0/15` 和 `192.0.0.0/24`；文件用範圍 `192.0.2.0/24`、`198.51.100.0/24` 和 `203.0.113.0/24`；以及保留範圍 `0.0.0.0/8`、`192.88.99.0/24` 和多點傳送 `224.0.0.0/4`。您可以宣告位於 `240.0.0.0/4` 內的區塊，部分大型網路將其作為內部單點傳送空間使用。

來自 `managed-settings.json` 及其 `managed-settings.d/` 附加檔案的區塊會合併成一份清單，上述限制適用於合併後的清單。若要縮小某個區塊，請替換其項目，而不是在附加檔案中新增第二個重疊的項目；`/login` 會拒絕重疊。

如果某個項目違反規則，或值不是字串清單，Claude Code 會拒絕該電腦上所有新的閘道登入，並在訊息中指出問題。登入位於私人位址上的閘道也會失敗，而現有的登入則會繼續運作。部署前請先在一台電腦上試用此值。Claude Code 也會將型別錯誤的值列在[它回報的無效受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md#keys-that-fail-closed)之中。

在清單有效的情況下，`/login` 會對位址位於已列出區塊內的閘道套用三項檢查：

* 閘道主機名稱解析出的每個位址都位於該同一區塊內。若名稱也有位於區塊外的記錄（包括私人位址與 IPv6 位址），Claude Code 會拒絕該名稱。
* 開發人員的電腦從同一區塊內連線。Claude Code 會拒絕位於 NAT 之後、容器或 WSL2 內，或其位址池位於區塊外之 VPN 上的電腦，並指出該電腦連線時所用的位址。
* 連線為直接連線。如果 `HTTPS_PROXY` 適用於閘道主機，`/login` 會拒絕並指出要新增的 `NO_PROXY` 項目。

三項檢查都通過時，[信任提示](#connect-developers)會新增一行，列出該電腦的位址、閘道的位址，以及同時包含兩者的已宣告區塊。

此鍵不會改變其他閘道的行為：登入位於私人位址上的閘道會像以前一樣運作，而登入位於所有已列出區塊之外的公用位址上的閘道，也會像以前一樣被拒絕。

已宣告的區塊會縮小可登入的範圍，但無法證明電腦位於何處，因此請只宣告您組織所控制的位址空間。與其他租用戶共用的區塊（例如雲端供應商的公用範圍）會讓其中的任何人都通過同樣的檢查。

### 將原則傳遞給 Claude Desktop 工作階段

Claude Desktop 的 Cowork 和 Code 分頁，以及啟用時的 Chat，皆在內嵌的 Claude Code 工作階段上執行，並透過閘道傳送其模型請求。它會將原則傳遞給每個工作階段，這些原則是根據閘道在 `/user/bootstrap` 提供給它的設定所建構而成：包括從所符合原則的 `cli` 或 `code` 區塊衍生而來的模型允許清單、已停用的工具及輸出允許清單，以及 [`desktop` 覆蓋設定](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#claude-desktop-overlay)。

該區塊的其他鍵，例如 hook、`env`，以及 `Bash(npm *)` 這類有範圍限定的權限規則，會送達透過 `/login` 登入的用戶端。在 `code` 之下時，當 [Code 分頁的條件](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#apply-code-settings-in-the-code-tab)成立，它們也會送達 Code 分頁的工作階段。它們不會送達 Cowork 或 Chat 工作階段。Claude Desktop 從自己的受管設定讀取閘道 URL，並以自己的流程登入，與[設定閘道 URL](#set-the-gateway-url) 中的 `forceLoginMethod` 和 `forceLoginGatewayUrl` 鍵分開。

由啟動程序傳遞的設定稱為父設定。在任何具有管理員部署之受管來源的電腦上，Claude Code 都會忽略父設定，除非[傳遞原則的來源](https://code.claude.com/docs/zh-TW/managed-settings.md#which-managed-source-claude-code-uses)設定了 `parentSettingsBehavior: "merge"`。

#### 哪些電腦需要選擇加入

只執行 Claude Desktop 的電腦需要選擇加入。Claude Desktop 會自行將模型清單與停用工具清單套用到內嵌工作階段，但對外連線允許清單只會以父設定的形式送達它們，也就是 `WebFetch` 網域規則和沙箱網路規則。若未選擇加入，這些工作階段會在沒有對外連線限制的情況下執行，而且不會有任何警告。閘道仍會拒絕原則未授權之模型的推論請求。

外掛市集允許清單同樣只會以父設定的形式送達內嵌工作階段。當您在 Claude Desktop 的受管設定中關閉使用者新增的外掛市集時，Claude Desktop 2.16120.0 或更新版本會隱藏您組織未佈建的市集，並拒絕從這些市集安裝。為了阻止內嵌工作階段載入已從這些市集安裝的外掛，它會以父設定的形式傳送 `strictKnownMarketplaces` 清單給它們。若未選擇加入，Claude Code 會忽略該清單，這些外掛也會繼續載入。

開發人員透過 `/login` 登入的電腦不需要選擇加入；每個 Claude Code 工作階段都會從閘道擷取其原則。

由 [`policyHelper`](https://code.claude.com/docs/zh-TW/settings-reference#policyhelper) 提供受管設定的機群無法使用此選項：Claude Code 在這些機群上絕不會合併父設定，因為它只從輔助程式的輸出讀取受管設定。

#### 設定選擇加入

部署[設定閘道 URL](#set-the-gateway-url) 中的受管設定片段，將其同步到任何優先順序高於該檔案的用戶端來源，然後進行驗證。

**1. 在受管設定檔中部署選擇加入**

[上方的片段](#set-the-gateway-url)已包含 `parentSettingsBehavior: "merge"`，因此您推送到電腦的檔案會帶有此設定。

**2. 將片段同步到任何優先順序高於該檔案的來源**

Claude Code 只從[所選來源](https://code.claude.com/docs/zh-TW/managed-settings.md#which-managed-source-claude-code-uses)讀取 `parentSettingsBehavior`。在某個來源中新增任何原則鍵，都可能讓該來源成為所選來源，因此在用戶端來源中，請同步整個片段，而不是只同步 `parentSettingsBehavior`。[用戶端受管設定](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#client-side-managed-settings)說明透過群組原則或設定描述檔傳遞原則的機群。macOS 上的 managed-preferences plist 或 Windows 上的 HKLM 原則優先順序高於 `managed-settings.json` 檔案，而閘道自身的遠端受管設定優先順序又高於兩者，因此在登入閘道的電腦上，也請在閘道原則的 [`cli` 或 `code` 區塊](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#managed)中設定 `parentSettingsBehavior`。

**3. 檢查所選來源**

在只執行 Claude Desktop 的電腦上，呼叫 Agent SDK 的 [`resolveSettings()`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#resolvesettings)，並讀取其 `sources` 清單中 `managed` 項目上的 `policyOrigin`。該值會指出所選的用戶端來源：`plist`、`hklm` 或 `file`，也就是必須帶有該片段的來源。

Cowork 和 Chat 工作階段不會擷取閘道原則，因此閘道的區塊不是它們的所選來源。

當原則的設定位於 `code` 之下，且 [Code 分頁的條件](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#apply-code-settings-in-the-code-tab)成立時，Code 分頁工作階段會擷取閘道原則。此時閘道的 `code` 設定便是該工作階段的所選來源。

### 限制父設定

一旦部署 `parentSettingsBehavior: "merge"`，任何啟動 Claude Code 的主機程序都可以提供父設定，不僅是 Claude Desktop，也包括 Agent SDK 應用程式或 IDE 擴充功能。

Claude Code 會以限制性鍵的允許清單篩選父設定，但部分允許的鍵可能會授予存取權而非加以限制。除非您設定了 `allowManaged*Only` 鎖定，否則主機提供的權限允許規則和沙箱允許清單仍會套用。無論如何，您原則中的拒絕與詢問規則都會持續生效；[它們會在任何允許規則之前評估](https://code.claude.com/docs/zh-TW/permissions.md#manage-permissions)。

Claude Code 會以精簡形式轉送父程序提供的 [`sandbox.credentials`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-credentials) 項目：

* **`deny` 項目**：只轉送其 `path` 或 `name` 以及模式。
* **具有 [`mode: mask`](https://code.claude.com/docs/zh-TW/sandboxing#mask-credential-files) 的檔案項目**：僅以哨兵值形式轉送，作為 `injectHosts` 為空清單的整檔遮罩，因此在任何平台上，代理伺服器都不會以真實值替換父程序提供的項目。所有結構化遮罩欄位也都會被捨棄，因此父程序提供的擷取模式無法取代其他來源為同一路徑設定的更嚴格遮罩。
* **具有 `mode: mask` 的 `envVars` 項目**：不轉送。`deny` 是父通道透過 `envVars` 項目唯一能表達的限制。
* **[`awsPairs` 和 `sigv4`](https://code.claude.com/docs/zh-TW/sandboxing#re-sign-aws-requests)**：僅以限制形式轉送。`sigv4` 中只保留 `deny` 值，而只要父程序定義了 `sigv4` 區塊，就會將 `streaming`、`presigned` 和 `sigv4a` 這三種請求形式全部固定為 `deny`。`awsPairs` 配對絕不會以能重新簽署的形式轉送；指定慣用 AWS 變數之一的配對會被替換為無作用的項目，以持續抑制 `AWS_ACCESS_KEY_ID`、`AWS_SECRET_ACCESS_KEY` 和 `AWS_SESSION_TOKEN` 的自動配對。

#### 部署鎖定

若要讓父設定盡可能接近篩選器所支援的僅限制狀態，請將全部五個 `allowManaged*Only` 鎖定及其所管理的允許清單，加入與合併選擇加入相同的來源：

```json theme={null}
{
  "forceLoginMethod": "gateway",
  "forceLoginGatewayUrl": "https://claude-gateway.internal.example.com",
  "parentSettingsBehavior": "merge",
  "allowManagedPermissionRulesOnly": true,
  "allowManagedMcpServersOnly": true,
  "allowManagedHooksOnly": true,
  "allowedMcpServers": [{ "serverUrl": "https://mcp.internal.example.com/*" }],
  "sandbox": {
    "network": {
      "allowManagedDomainsOnly": true,
      "allowedDomains": ["github.com", "*.npmjs.org"]
    },
    "filesystem": {
      "allowManagedReadPathsOnly": true,
      "denyRead": ["~/"],
      "allowRead": ["~/projects"]
    }
  }
}
```

作業系統原則（例如 HKLM 登錄原則或 managed-preferences plist）的優先順序高於此檔案，因此請改透過它傳遞整個片段，而非透過檔案。閘道的遠端受管設定優先順序高於作業系統原則與檔案來源，但只會送達已連接的用戶端。請將鎖定、允許清單與合併選擇加入同步到原則的 [`cli` 或 `code` 區塊](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#managed)，並持續部署此檔案，因為從未連接的電腦只會從檔案取得其原則。

#### 跨來源的鎖定行為

設定一個鎖定並不會限制其他鎖定；每個鍵都記載於[設定參考](https://code.claude.com/docs/zh-TW/settings-reference.md#all-settings)中。

來自優先順序低於勝出來源之管理來源的兩個沙箱鎖定仍會套用，而 `allowManagedPermissionRulesOnly` 仍會阻擋父程序提供的允許規則和 `additionalDirectories`。在 Claude Code v2.1.273 或更新版本上，MCP 伺服器鎖定也會從優先順序低於勝出來源的來源套用，且在其開啟期間，受管的 `allowedMcpServers` 清單來自設定該清單之優先順序最高的管理來源。

hook 鎖定，以及 `allowManagedPermissionRulesOnly` 對開發人員自身規則的作用，預設需要來自勝出來源；在 [Claude Code 如何合併受管來源](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)中所述的 `managedSourcesBehavior` 合併選擇加入下，Claude Code 會為每個鎖定套用任何來源所設定的最嚴格值。在 [`policyHelper`](https://code.claude.com/docs/zh-TW/settings-reference#policyhelper) 機群上，Claude Code 只從輔助程式的輸出讀取鎖定。

每個鎖定都會讓 Claude Code 忽略開發人員自己針對該設定的項目，因此請在鎖定旁邊加入您組織的允許清單：

* **網路網域**：以空的受管網域清單鎖定，會封鎖所有沙箱化的對外流量。
* **MCP 伺服器**：若任何管理來源或父程序提供的設定中都沒有 `allowedMcpServers` 就鎖定，會載入所有未被 `deniedMcpServers` 封鎖的伺服器。
* **讀取路徑**：`allowRead` 項目只會重新允許 `denyRead` 區域內的路徑，因此請將它們與受管的 `denyRead` 搭配使用。

#### 鎖定未涵蓋的設定

即使設定了全部五個鎖定，下列父程序提供的設定仍會通過篩選器：

* **`forceLoginOrgUUID`**：當 Claude Code 套用的受管設定未設定組織 UUID 時，Claude Code 會採用父程序提供的值。閘道登入不會檢查此鍵。Claude Code 所套用受管設定中的組織 UUID 會阻擋父程序的值，並成為 Claude Code 強制執行的組織 UUID。如果您的機群釘選了某個 Anthropic 組織，請參閱[哪個受管來源提供登入鍵](https://code.claude.com/docs/zh-TW/managed-settings.md#which-managed-source-supplies-login-keys)，了解應在何處設定 `forceLoginOrgUUID`。
* **`allowedMcpServers`**：當沒有管理清單生效時，Claude Code 會採用父程序提供的允許清單。`allowManagedMcpServersOnly` 不會阻擋它，因為此鎖定會強制執行勝出作為受管值的任何清單，包括在沒有管理來源提供清單時由父程序提供的清單。優先順序最高之管理來源中的清單會阻擋父程序的清單，並成為 Claude Code 強制執行的清單，因此請在該處、鎖定旁邊設定 `allowedMcpServers`。在 v2.1.223 之前，任何管理來源中只要有這兩個鍵之一的值，就會阻擋父程序的值。
* **`availableModels`**：當勝出的受管來源未設定模型清單時，Claude Code 會採用父程序提供的模型清單。如果您的機群限制了模型，請在勝出來源中設定 `availableModels`。
* **`allowedProviders`**：當勝出的受管來源未設定時，Claude Code 會採用父程序提供的 API 供應商允許清單。如果您的機群限制開發人員可使用的 API 供應商，請在勝出來源中設定 `allowedProviders`。需要 Claude Code v2.1.285 或更新版本。
* **`strictKnownMarketplaces`**：當勝出的受管來源未設定時，Claude Code 會採用父程序提供的外掛市集允許清單。當 Claude Desktop 2.16120.0 或更新版本的受管設定關閉使用者新增的外掛市集時，它會傳送此清單。如果您的機群限制了市集，請在勝出來源中設定 `strictKnownMarketplaces`。需要 Claude Code v2.1.282 或更新版本。
* **`blockedMarketplaces`**：父程序提供的市集封鎖清單會通過篩選器，並加入任何受管來源所設定的封鎖清單，因為封鎖清單只能進一步加以限制。需要 Claude Code v2.1.282 或更新版本。
* **`strictPluginOnlyCustomization`**：無論設定了任何鎖定，此鍵都會通過篩選器，並讓 Claude Code 忽略開發人員自己的自訂內容，包括保護性的 hook。沒有任何鎖定能阻擋它。

如果您將 `managedSourcesBehavior` 設為 `"merge"`，請查看[每種鍵套用哪個來源的值](https://code.claude.com/docs/zh-TW/managed-settings.md#compose-every-managed-source)。

#### 父設定中的 hook 與 skill 鍵如何生效

您的應用程式在 Agent SDK 的 [`managedSettings`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#options) 選項中傳遞的鍵屬於父設定。在管理員部署了受管設定的電腦上，除非管理員[允許內嵌主機新增原則](https://code.claude.com/docs/zh-TW/managed-settings.md#let-an-embedding-host-add-policy)，否則 Claude Code 會忽略父設定。

如果您在 `managedSettings` 中傳遞 [`disableAllHooks: true`](https://code.claude.com/docs/zh-TW/settings-reference#disableallhooks)：

* **停止**：使用者、專案及本機 hook，以及在 agent frontmatter 或 SDK 的 [`settings` 選項](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#options)中宣告的 hook。
* **繼續執行**：您應用程式的 [SDK hook 回呼](https://code.claude.com/docs/zh-TW/agent-sdk/hooks.md)，以及管理員在受管設定中的 hook。您的應用程式無法關閉管理員的 hook。

| 您傳遞的內容 | 結果 |
| :- | :- |
| `hooks`，或含有項目的 `allowedHttpHookUrls` 或 `httpHookAllowedEnvVars` | Claude Code 會忽略此鍵。請改用 SDK 的 `settings` 選項。 |
| `allowedHttpHookUrls: []` | 除非管理員定義了 `hooks` 或啟用了外掛，否則會生效。不會執行任何 HTTP hook，但其他設定來源列出的 URL 除外。 |
| `httpHookAllowedEnvVars: []` | 除非管理員定義了 `hooks` 或啟用了外掛，否則會生效。HTTP hook 標頭只能包含其他設定來源列出的環境變數。 |
| [`disableSkillShellExecution: true`](https://code.claude.com/docs/zh-TW/settings-reference#disableskillshellexecution) | 生效。 |

在 `managedSettings` 中傳遞這些鍵需要 Claude Code v2.1.309 或更新版本，或 TypeScript Agent SDK v0.3.309 或更新版本。

### 連接 Claude Desktop

[Claude Desktop](https://code.claude.com/docs/zh-TW/desktop.md) 透過不同的 MDM 鍵連接到同一個閘道：在 Claude Desktop 的[受管設定](https://claude.com/docs/third-party/claude-desktop/configuration)中將 `bootstrapUrl` 設為 `<listen.public_url>/user/bootstrap`，並以 `desktop` 鍵讓使用者的原則選擇加入。[Claude Desktop 覆蓋層](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#claude-desktop-overlay)涵蓋這兩部分。需要閘道伺服器上的 Claude Code v2.1.203 或更新版本。

Claude Desktop 會透過閘道的身分識別提供者，以相同的瀏覽器 SSO 步驟讓開發人員登入，然後從閘道而非 Anthropic 擷取其設定。模型存取與原則遵循與 CLI 相同的各群組規則。同時使用 CLI 和 Claude Desktop 的開發人員需分別登入兩者；兩者之間不共用閘道工作階段。

連接後，Claude Desktop 會透過閘道傳送每個已啟用分頁的模型請求。預設會顯示 Cowork 和 Code 分頁。若也要讓 Chat 可用，請在執行 Claude Code v2.1.227 或更新版本的閘道上，於原則的 [`desktop` 區塊](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#claude-desktop-overlay)中將 `chatTabEnabled` 設為 `true`。開啟 Cowork 時，Claude Desktop 便會在同一個分頁中一併顯示 Chat 和 Cowork。

### CI 管線與遠端電腦

目前沒有供無人值守管線使用的服務 token 流程。閘道登入一律執行瀏覽器裝置流程，因此沒有開發人員可核准登入的 CI 工作無法完成身分驗證；請將這些工作直接設定為使用您的供應商。請將 `forceLoginMethod` 和 `forceLoginGatewayUrl` 部署到開發人員電腦上，而不要部署到 CI 執行器上。在受管設定中設定了這些鍵的電腦上，以 `ANTHROPIC_API_KEY`、`ANTHROPIC_AUTH_TOKEN` 或 `apiKeyHelper` 進行身分驗證的工作階段會[在啟動時結束](https://code.claude.com/docs/zh-TW/errors.md#administrator-policy-requires-a-cloud-gateway-sign-in)。

開發人員登入後，該電腦上的每個 Claude Code 工作階段都會使用閘道工作階段，包括非互動式的 `claude -p` 執行，以及由 Agent SDK 啟動的工作階段。Claude Code 會對每個工作階段套用[閘道原則](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#managed)。

裝置流程將進行輪詢的 CLI 與進行核准的瀏覽器分開，因此沒有顯示器的遠端開發機器也能運作：開發人員透過 SSH 在遠端電腦上執行 `/login`，然後在自己筆記型電腦的瀏覽器中開啟驗證連結。

### 對開發人員強制執行的項目

這些保證適用於每個透過 `/login` 登入的工作階段。Claude Desktop 啟動的內嵌工作階段會依[將原則傳遞給 Claude Desktop 工作階段](#deliver-policy-to-claude-desktop-sessions)中所述的方式取得其原則，而遙測項目則說明了其匯出資料的去向。

* **模型存取**：對原則未授權之模型的請求會傳回 400，且 `/model` 選擇器會篩選為原則的 `availableModels` 允許清單。這也包括開發人員選擇模型之前工作階段啟動時所用的模型；請參閱[讓工作階段以原則允許的模型啟動](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#start-sessions-on-a-model-the-policy-allows)。
* **遙測目的地**：在透過 `/login` 登入的工作階段中，CLI 會將其 OTLP/HTTP 匯出資料傳送到閘道，而非本機設定的 `OTEL_EXPORTER_OTLP_ENDPOINT`，除非原則[將您的收集器指定為端點](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#export-directly-to-your-collector)。閘道會將收到的匯出資料轉送至 [`telemetry.forward_to`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#telemetry) 中的目的地。
  * 在 [Claude Desktop 啟動](#connect-claude-desktop)的內嵌工作階段中，CLI 會將其匯出資料傳送到已設定的 `OTEL_EXPORTER_OTLP_ENDPOINT`。只有當該端點指向閘道本身時，CLI 才會將閘道工作階段 token 附加到這些匯出資料上。
  * 若某個訊號沒有設定目的地，閘道會接受並捨棄它。
  * 如果您已直接收集 Claude Code 遙測，請將您的收集器新增為 `forward_to` 目的地，或在原則中指定它以略過轉送。
* **憑證**：閘道 token 是工作階段唯一的憑證。登入期間會忽略 [Anthropic 設定檔](https://code.claude.com/docs/zh-TW/authentication.md#anthropic-profiles-and-federation-credentials)和任何先前的 claude.ai 登入，因此開發人員不需要先登出 claude.ai。關於已設定的 `ANTHROPIC_API_KEY`、`ANTHROPIC_AUTH_TOKEN` 或 `apiKeyHelper` 憑證，或先前 Claude Console 登入所儲存的 API 金鑰，請參閱 [Administrator policy requires a Cloud gateway sign-in](https://code.claude.com/docs/zh-TW/errors.md#administrator-policy-requires-a-cloud-gateway-sign-in)。
* **受管設定**：鎖定的鍵無法在本機覆寫。CLI 會在啟動時套用原則，並在每小時輪詢時套用變更，但[僅在下次啟動時套用的變更](https://code.claude.com/docs/zh-TW/server-managed-settings.md#fetch-and-caching-behavior)除外。
* **閘道無法連線時的啟動**：已登入的工作階段會在約 10 秒後以錯誤結束啟動，而不會在沒有其設定的情況下啟動。
* **閘道結束工作階段後的啟動**：請參閱[強制執行失敗即關閉的啟動](https://code.claude.com/docs/zh-TW/server-managed-settings.md#enforce-fail-closed-startup)，了解哪些啟動會以登出閘道的狀態開啟，以及哪些啟動會在閘道以 `401` 回應時結束。
* **取消佈建**：使用者在 IdP 中被停用的工作階段，會在下次更新失敗時於 `ttl_hours` 內到期。
* **登出**：`/logout` 會從開發人員的電腦刪除閘道憑證。
  * 當閘道的探索文件在與閘道 URL 本身相同的 scheme、主機和連接埠上公告 `revocation_endpoint` 時，`/logout` 也會將儲存的 token 傳送到該端點，讓閘道能在其端結束工作階段。此請求為盡力而為，因此無論端點是否回應，開發人員電腦上的登出都會完成。撤銷需要開發人員電腦上的 Claude Code v2.1.275 或更新版本。
  * `claude` 二進位檔中的閘道伺服器不會公告任何撤銷端點，因此從它登出只會結束開發人員電腦上的工作階段。若要在伺服器端強制讓工作階段登出，請參閱 [JWT 密鑰輪替](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#jwt-secret-rotation)。

### 組織可以看到的內容

使用遙測會將開發人員的身分、token 數量、模型和延遲傳送到組織的收集器。閘道不會記錄或儲存提示詞或完成內容。是否收集更豐富的遙測（例如日誌和追蹤，其中可能包含命令和檔案路徑），由組織[依目的地自行選擇](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#telemetry)。

## 可用性和限制

該表涵蓋當開發人員透過閘道連接時哪些 Claude Code 功能有效，以及閘道伺服器本身支援什麼。如果不支援某些內容，「備註」欄提供替代方案。

閘道傳遞 CLI 發送到每個上游的 [`anthropic-beta`](https://platform.claude.com/docs/en/api/beta-headers) 值，因此操作員不維護測試版允許清單。對於 Amazon Bedrock（忽略標頭），閘道將值移到請求正文的 `anthropic_beta` 欄位；其他上游接收按發送方式發送的標頭。

| 功能 | 狀態 | 備註 |
| - | - | - |
| 推理轉發 (Amazon Bedrock、Claude Platform on AWS、Google Cloud 的 Agent Platform、Microsoft Foundry、Anthropic) | 可用 | 具有按上游模型轉換和故障轉移。Amazon Bedrock 上游使用 `bedrock-runtime` 端點和 AWS 預設憑證鏈。[Amazon Bedrock Mantle 上游](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#amazon-bedrock-mantle-endpoint)需要閘道伺服器上的 Claude Code v2.1.283 或更新版本，而 [Claude Platform on AWS 上游](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#claude-platform-on-aws)需要 v2.1.198 或更新版本。 |
| 1M token 上下文視窗 | 可用 | Fable 模型、Sonnet 5 及更新版本，以及 Opus 4.7 及更新版本預設以 1M 視窗執行；請參閱[擴展上下文](https://code.claude.com/docs/zh-TW/model-config.md#extended-context)。Fable 和 Opus 模型的 1M 預設需要開發人員機器上的 Claude Code v2.1.287 或更新版本 |
| 按 IdP 群組的模型存取和受管設定 | 可用 | 模型存取在伺服器端強制執行；受管設定按 IdP 群組傳遞，由 CLI 在[受管設定層級](https://code.claude.com/docs/zh-TW/settings.md#settings-precedence)應用 |
| Claude Desktop | 可用（需要選擇加入） | 一旦原則[使用 `desktop` 金鑰選擇加入](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#claude-desktop-overlay)，閘道便會在 `/user/bootstrap` 提供 Claude Desktop 的設定，而 Claude Desktop 會透過閘道發送其模型請求。若要開啟 Chat，請參閱[連接 Claude Desktop](#connect-claude-desktop)。需要閘道伺服器上的 Claude Code v2.1.203 或更新版本。 |
| 遙測扇出 (OTLP/HTTP) | 可用 | 按匯出標識戳記；protobuf 和 JSON 編碼 |
| OIDC 身份提供者 | 可用 | 任何符合 OIDC 的 IdP；閘道執行標準 OIDC 探索和授權碼流程。請參閱[身份提供者設定](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#identity-provider-setup)以了解各 IdP 的設定 |
| 按使用者和按群組支出限制 | 可用 | 請參閱[支出限制](https://code.claude.com/docs/zh-TW/claude-apps-gateway-spend-limits.md) |
| 伺服器端網路搜尋 | 不可用 | CLI 無法看到閘道路由到的上游提供商，因此無法驗證網路搜尋支援並在閘道工作階段上禁用 WebSearch |
| [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) | 不可用 | CLI 顯示[命名閘道的錯誤](https://code.claude.com/docs/zh-TW/errors.md#remote-control-requires-the-anthropic-api) |
| [`/design-sync`](https://code.claude.com/docs/zh-TW/commands#all-commands) 和 `/design-login` | 不可用 | 兩者都需要 claude.ai，CLI 在閘道工作階段上不聯絡，因此兩個命令都不會出現 |
| 需要功能旗標擷取的功能，例如 `/import` 和 `claude import` | 不可用 | CLI 在閘道工作階段上跳過旗標擷取。[需要功能旗標擷取的功能](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)列出關閉的內容 |
| 標準提示快取 | 可用 | 閘道將 `cache_control` 斷點轉發到每個上游。[快取位置](https://code.claude.com/docs/zh-TW/prompt-caching.md#where-the-cache-lives)涵蓋 CLI 標記的區塊，包括它在對話中途附加的系統內容 |
| 1 小時快取 TTL | 可用（需要選擇加入） | CLI 在閘道工作階段上預設使用 5 分鐘 TTL。若要請求 1 小時 TTL，請[在原則中](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#one-hour-prompt-cache)設定。僅當您的上游為閘道提供的每個模型都提供 1 小時 TTL 時才設定，因為若有上游拒絕該 TTL，請求便會失敗 |
| 自動模式 | 可用 | 遵循[第三方提供商規則](https://code.claude.com/docs/zh-TW/permission-modes.md#enable-auto-mode-on-bedrock-agent-platform-or-foundry)：只有第三方提供商上符合條件的模型可以使用它。在 v2.1.207 之前，閘道工作階段上的自動模式需要設定 `CLAUDE_CODE_ENABLE_AUTO_MODE=1`，可透過受管原則 `env` 區塊傳遞 |
| 僅限第一方的最佳化，例如全域快取範圍和令牌高效工具 | 不可用 | CLI 在閘道工作階段上不啟用它們；請參閱上面的測試版標頭備註 |
| OTLP/gRPC | 不支援 | 僅 OTLP over HTTP |
| SAML、LDAP 和其他非 OIDC 身份驗證 | 不支援 | 僅 OIDC。如果需要，使用 OIDC 橋接 |
| 多租戶（多個 OIDC 發行者） | 不支援 | 每個閘道一個發行者。執行單獨的執行個體 |
| Windows 伺服器 | 不支援 | 在 Linux 上部署。僅本地開發的 macOS |
| Helm chart | 不可用 | 閘道作為標準無狀態 Deployment 執行；請參閱[部署指南](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#kubernetes) |
| 管理員 UI | 不可用 | 設定是 YAML 檔案；重新部署以更改它 |

## 後續步驟

快速入門讓您在 Docker Compose 下執行最小配置。要進一步進行：

* 擴展 `gateway.yaml` 超越最小配置，例如新增按群組 RBAC、多上游故障轉移或遙測目的地。[配置參考](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md)涵蓋每個選項。
* 從 Compose 移動到 Kubernetes 或 Cloud Run 上的生產部署，正確設定您的 IdP，並檢查安全模型。[部署和操作指南](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md)涵蓋每個 IdP 的設定、容器映像要求、健康探針和故障排除。
* 對個別開發人員或群組設定支出上限，以便失控的工作負載無法消耗您的整個承諾。[支出限制](https://code.claude.com/docs/zh-TW/claude-apps-gateway-spend-limits.md)涵蓋管理員 API 以及強制執行的工作方式。
* 有關 AWS 上的完整實踐示例，包括 ECS Fargate 或 EKS、Amazon RDS 和 Secrets Manager，請參閱[在 AWS 上部署](https://code.claude.com/docs/zh-TW/claude-apps-gateway-on-aws.md)。
* 有關 Google Cloud 上的完整實踐示例，包括 Cloud Run、Cloud SQL 和 Secret Manager，請參閱[在 Google Cloud 上部署](https://code.claude.com/docs/zh-TW/claude-apps-gateway-on-gcp.md)。

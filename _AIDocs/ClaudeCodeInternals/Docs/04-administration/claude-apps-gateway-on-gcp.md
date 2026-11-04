<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/claude-apps-gateway-on-gcp | lastmod: 2026-10-22 | section: Administration / Gateways -->
> 來源：https://code.claude.com/docs/zh-TW/claude-apps-gateway-on-gcp（官方 zh-TW，lastmod 2026-10-22）｜分類：Administration › Gateways｜EN 摘要：A worked example of running Claude apps gateway on Google Cloud: Cloud Run or GKE, Cloud SQL for PostgreSQL, Secret Manager, and service-account auth to Google Cloud's Agent Platform.

# 在 Google Cloud 上部署 Claude 應用程式閘道

> 在 Google Cloud 上執行 Claude 應用程式閘道的實際範例：Cloud Run 或 GKE、Cloud SQL for PostgreSQL、Secret Manager，以及對 Google Cloud 的 Agent Platform 的服務帳戶驗證。

> [!NOTE]
>
> 本頁面介紹在 Google Cloud 上執行 Claude 應用程式閘道的一種方式。此配置是客戶管理基礎設施的工作範例，而非受支援的生產部署；使用它來了解各個部分如何組合在一起，然後再根據您自己的環境進行調整。如需平台無關的需求，請參閱[部署指南](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md)。

此範例在 Google Cloud 上配置 Claude 應用程式閘道，使用 Google Cloud 的 Agent Platform 作為模型上游，並使用 Cloud Run 或 GKE 進行運算。Google Workspace 是範例身分提供者 (IdP)，但任何符合 OpenID Connect (OIDC) 的 IdP 都可以使用；只有 `oidc` 區塊會改變。如需各個 IdP 的詳細資訊，請參閱[身分提供者設定](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#identity-provider-setup)。

## 您將建立的內容

![Google Cloud 上 Claude 應用程式閘道的圖表：Claude Code 用戶端透過 HTTPS 連接到閘道（Cloud Run 或 GKE），閘道在 VPC 內執行，旁邊有一個私有 IP Cloud SQL 資料庫用於工作階段狀態。閘道透過 OIDC 針對 Google Workspace 簽署使用者，從 Secret Manager 讀取配置和祕密，將模型請求轉發到 Google Cloud 的 Agent Platform，並在部署時從 Artifact Registry 提取其映像。](https://mintcdn.com/claude-code/-uq-4JE0W_JO5Er5/images/claude-gateway-gcp-architecture.svg?fit=max\&auto=format\&n=-uq-4JE0W_JO5Er5\&q=85\&s=cb705151c69128ac0da235852d5600ab)

部署包含：

* 執行閘道容器的 **Cloud Run** 服務或 **GKE** Deployment
* 用於閘道映像的 **Artifact Registry** 儲存庫
* **Cloud SQL for PostgreSQL** 執行個體，僅限私有 IP，用於閘道的[儲存](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#store)
* **Secret Manager** 祕密，用於 `gateway.yaml`、JWT 簽署金鑰、OIDC 用戶端祕密和 Postgres URL
* **服務帳戶**，具有 `roles/aiplatform.user`，直接附加到 Cloud Run 或透過 GKE 上的 Workload Identity 繫結
* **HTTPS 前端**，由您提供：Cloud Run 前面的內部應用程式負載平衡器（本逐步解說會為其設定閘道，但不會建立），或在 GKE 上使用 `gce-internal` 類別的內部 **GKE Ingress**

## 先決條件

* 啟用計費的 GCP 專案，以及建立上述資源的權限
* `gcloud` CLI（使用 `gcloud auth login` 驗證）和本機安裝的 Docker
* 對於 GKE 路徑：`kubectl` 和在下面逐步解說中建立的 VPC 上的 GKE 叢集
* 在 Model Garden 中存取您需要的 Claude 模型，在發佈這些模型的區域中
* Google Workspace OAuth 2.0 網路應用程式用戶端，重新導向 URI 為 `https://<gateway-host>/oauth/callback`；請參閱[身分提供者設定](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#identity-provider-setup)
* 閘道的 TLS 主機名稱，通常是指向負載平衡器的內部 DNS 名稱

設定專案和區域一次：

```bash theme={null}
export PROJECT_ID=<your-project>
export REGION=us-east5   # a region where the Claude models you need are published in Model Garden
gcloud config set project "$PROJECT_ID"
```

## 部署閘道

以下步驟使用 `gcloud` 命令佈建完整部署。

**1. 啟用 API**

啟用本逐步解說使用的服務 API：

```bash theme={null}
gcloud services enable \
  aiplatform.googleapis.com \
  artifactregistry.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  iamcredentials.googleapis.com \
  iam.googleapis.com \
  compute.googleapis.com \
  servicenetworking.googleapis.com \
  run.googleapis.com \
  container.googleapis.com
```

您需要的 API 取決於部署路徑：

* `compute` 和 `servicenetworking`：私有 IP Cloud SQL 路徑所需
* `run`：僅限 Cloud Run
* `container`：僅限 GKE

**2. 建立服務帳戶並授予 IAM**

閘道以專用服務帳戶身份執行，具有呼叫 Google Cloud 的 Agent Platform 的權限。它透過 VPC 使用密碼使用者連接到 Cloud SQL，因此不需要 Cloud SQL IAM 角色：

```bash theme={null}
gcloud iam service-accounts create claude-gateway --display-name="Claude apps gateway"
SA="claude-gateway@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA}" --role="roles/aiplatform.user" --condition=None
```

然後在 Model Garden 中為專案啟用 Claude 模型；模型發佈到特定區域，因此請檢查每個模型卡。

**3. 建置映像並推送到 Artifact Registry**

根據[容器映像需求](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#container-image)建置映像，使用 `linux-x64` glibc 二進位檔，並推送它：

```bash theme={null}
gcloud artifacts repositories create claude-gateway \
  --repository-format=docker --location="$REGION"
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# Cloud Run 需要 linux/amd64。--provenance=false 避免 buildx OCI
# 映像索引，Cloud Run 會拒絕。
docker build --platform=linux/amd64 --provenance=false \
  -t "${REGION}-docker.pkg.dev/${PROJECT_ID}/claude-gateway/gateway:<version>" .
docker push "${REGION}-docker.pkg.dev/${PROJECT_ID}/claude-gateway/gateway:<version>"
```

**4. 佈建 Cloud SQL for PostgreSQL**

透過 Private Services Access 在 VPC 上建立執行個體，使其沒有公用 IP；這也滿足強制執行 `constraints/sql.restrictPublicIp` 的專案：

```bash theme={null}
VPC=cc-gateway-vpc
gcloud compute networks create "$VPC" --subnet-mode=custom
gcloud compute networks subnets create cc-gateway-subnet \
  --network="$VPC" --region="$REGION" --range=10.0.0.0/24

# Private Services Access：每個 VPC 一次
gcloud compute addresses create "google-managed-services-${VPC}" \
  --global --purpose=VPC_PEERING --prefix-length=16 --network="$VPC"
gcloud services vpc-peerings connect \
  --service=servicenetworking.googleapis.com \
  --ranges="google-managed-services-${VPC}" --network="$VPC"

gcloud sql instances create claude-gateway-db \
  --database-version=POSTGRES_16 --tier=db-g1-small --region="$REGION" \
  --network="projects/${PROJECT_ID}/global/networks/${VPC}" --no-assign-ip
gcloud sql databases create claude_gateway --instance=claude-gateway-db
PGPASS="$(openssl rand -hex 24)"
gcloud sql users create gateway --instance=claude-gateway-db --password="$PGPASS"

PRIVATE_IP="$(gcloud sql instances describe claude-gateway-db \
  --format='value(ipAddresses[0].ipAddress)')"
GATEWAY_POSTGRES_URL="postgres://gateway:${PGPASS}@${PRIVATE_IP}:5432/claude_gateway?sslmode=require"
```

Cloud Run 或 GKE 執行階段必須在此 VPC 上或路由到此 VPC。

**5. 撰寫 gateway.yaml**

`upstreams` 區塊使用 `auth: {}` 指向 Google Cloud 的 Agent Platform，因此閘道透過執行階段服務帳戶的應用程式預設認證進行驗證。請參閱[設定參考](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md)以了解每個欄位。

兩個 `listen` 欄位描述什麼在閘道前面：

* `public_url`：外部 `https://` 來源，任何非迴圈繫結都需要；請參閱 [`listen` 參考](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#listen)。閘道僅從此值建置 IdP `redirect_uri` 和其探索文件，絕不從 `X-Forwarded-*` 標頭建置。
* `trusted_proxies`：前端的來源範圍。閘道僅在 TCP 對等在此清單中時才接受 `X-Forwarded-For`，然後走過受信任的躍點鏈，因此每個 IP 登入速率限制和稽核事件會記錄開發人員 IP 而不是負載平衡器的。

設定 `trusted_proxies` 以符合您的前端。`gce` 類別的外部 GKE Ingress 未列出：它佈建公用轉送規則位址，`/login` [私人網路檢查](https://code.claude.com/docs/zh-TW/claude-apps-gateway#prerequisites)會拒絕。

| 前端 | `trusted_proxies` |
| - | - |
| 直接到達的 Cloud Run，無負載平衡器 | `[169.254.0.0/16]` |
| Cloud Run 前面的內部應用程式負載平衡器 | `169.254.0.0/16` 加上您的僅代理子網路 CIDR |
| GKE 內部 Ingress，類別 `gce-internal` | 您的僅代理子網路 CIDR |

下面的範例使用內部負載平衡器在 Cloud Run 前面的值。

```yaml gateway.yaml theme={null}
listen:
  host: 0.0.0.0
  port: 8080
  public_url: https://claude-gateway.internal.example.com
  trusted_proxies: [169.254.0.0/16, <your-proxy-only-subnet-cidr>]

oidc:
  issuer: https://accounts.google.com
  client_id: <your-oauth-client-id>
  client_secret: ${OIDC_CLIENT_SECRET}           # GKE: ${file:/secrets/oidc-client-secret}
  allowed_email_domains: [example.com]
  # Google 忽略 offline_access；這些會產生重新整理權杖：
  scopes: [openid, profile, email]
  extra_auth_params: { access_type: offline, prompt: consent }

session:
  jwt_secret: ${GATEWAY_JWT_SECRET}              # GKE: ${file:/secrets/jwt-secret}

store:
  postgres_url: ${GATEWAY_POSTGRES_URL}          # GKE: ${file:/secrets/postgres-url}
  # readiness_grace_seconds: 300                 # 在 Cloud SQL 容錯移轉期間
# 保持通過就緒探針

upstreams:
  - provider: vertex
    region: <your-region>                        # 必須符合 $REGION
    project_id: <your-project>
    auth: {} # 透過執行階段服務帳戶的 ADC
```

> [!NOTE]
>
> Google id\_tokens 不包含 `groups` 宣告。若要在 [`managed.policies`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#managed) 中使用基於群組的原則，並以 Google Workspace 作為 IdP，請設定 [`oidc.google_groups`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#oidc)，它使用具有網域範圍委派的服務帳戶透過 Admin SDK Directory API 查詢每個使用者的群組。沒有它，改為符合 `email_domain`。

**6. 在 Secret Manager 中儲存祕密**

建立四個祕密並授予 `roles/secretmanager.secretAccessor` 給 `claude-gateway` 服務帳戶：

| 祕密 | 來源 |
| - | - |
| `gateway-jwt-secret` | `openssl rand -base64 32` |
| `gateway-oidc-client-secret` | Google Cloud Console → OAuth 用戶端 |
| `gateway-postgres-url` | Cloud SQL 步驟中的 `$GATEWAY_POSTGRES_URL` |
| `gateway-config` | 前一步驟中的完整 `gateway.yaml` |

祕密到達容器的方式因軌道而異：

* 在 GKE 上，它們透過 Secret Manager CSI 驅動程式掛載為檔案，`gateway.yaml` 參考 `${file:/secrets/...}`。
* 在 Cloud Run 上，無法將多個祕密掛載到一個目錄，`gateway.yaml` 掛載為檔案，其他三個注入為環境變數，因此 `gateway.yaml` 改為參考 `${GATEWAY_JWT_SECRET}`、`${OIDC_CLIENT_SECRET}` 和 `${GATEWAY_POSTGRES_URL}`。

**7. 部署**

> [tab] Cloud Run
>
> 下面的命令在內部負載平衡器後面部署用於生產。
>
> ```bash theme={null}
> gcloud run deploy claude-gateway \
>   --image="${REGION}-docker.pkg.dev/${PROJECT_ID}/claude-gateway/gateway:<version>" \
>   --region="$REGION" \
>   --service-account="claude-gateway@${PROJECT_ID}.iam.gserviceaccount.com" \
>   --min-instances=1 \
>   --max-instances=8 \
>   --timeout=3600 \
>   --ingress=internal \
>   --network="$VPC" --subnet=cc-gateway-subnet --vpc-egress=private-ranges-only \
>   --set-secrets=/etc/claude/gateway.yaml=gateway-config:latest,GATEWAY_JWT_SECRET=gateway-jwt-secret:latest,OIDC_CLIENT_SECRET=gateway-oidc-client-secret:latest,GATEWAY_POSTGRES_URL=gateway-postgres-url:latest \
>   --no-invoker-iam-check
> ```
>
> 直接 VPC 出口，透過 `--network`、`--subnet` 和 `--vpc-egress=private-ranges-only`，讓服務直接到達 Cloud SQL 私有 IP。公用出口到 Google Cloud 的 Agent Platform 端點和 `accounts.google.com` 直接進入網際網路，而不是透過 VPC，因此不需要 Cloud NAT。
>
> > [!NOTE]
> >
> > 每個執行個體最多持有 [`store.max_connections`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#store) 個 Postgres 連線，預設為五個。請使用[調整連線池大小](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#size-the-connection-pool)，對照您的資料庫剩餘可供閘道使用的連線數檢查 `--max-instances=8`，並將滾動更新所啟動的額外執行個體納入計算。
>
> 調用者 IAM 檢查必須開啟或停用。閘道執行自己的 OIDC，其用戶端不攜帶 GCP 權杖，因此 Cloud Run 的調用者檢查必須允許未驗證的請求。閘道的 OIDC 登入在請求到達容器後驗證請求，使用 `allowed_email_domains` 限制哪些網域可以登入。
>
> 兩個旗標允許未驗證的請求：
>
> * `--no-invoker-iam-check`：停用檢查，無需管理 `allUsers` 繫結，並在網域限制共用下工作
> * `--allow-unauthenticated`：授予 `allUsers` `run.invoker` 角色；如果您的組織不允許 `--no-invoker-iam-check`，請使用它
>
> 透過 `--ingress` 的入口限制是與調用者檢查分開的獨立層；保持設定以將服務限制在您的公司網路。
>
> 預設情況下，Cloud Run `*.run.app` URL 解析為公用位址，`/login` [私人網路檢查](https://code.claude.com/docs/zh-TW/claude-apps-gateway#prerequisites)會拒絕。兩個拓撲為開發人員提供私人可解析的主機名稱，Cloud Run 都不為您佈建：
>
> * **內部應用程式負載平衡器**，此頁面的 `gateway.yaml` 假設的拓撲：在服務前面佈建內部應用程式負載平衡器，具有內部 DNS 名稱和憑證，並將 `listen.public_url` 設定為該主機名稱。`internal` 入口設定已允許來自內部應用程式負載平衡器的流量；`internal-and-cloud-load-balancing` 另外允許外部應用程式負載平衡器，其公用位址 `/login` 私人網路檢查會拒絕，因此此頁面上的拓撲都不需要它。
> * **僅限內部入口，無負載平衡器**：保持部署命令原樣，將 `listen.public_url` 保留為 `*.run.app` URL，下面[參考資產](#terraform-reference)中的預設值。為了讓 `*.run.app` 私人解析，您的網路團隊必須已經為 Google API 運作 Private Service Connect 端點、解析 `*.run.app` 到它的 Cloud DNS 私人區域，以及到該端點的內部部署路由。
>
> Google 的 [Cloud Run 私人網路指南](https://cloud.google.com/run/docs/securing/private-networking)涵蓋兩個選項都需要的基礎結構。一旦閘道在私人主機名稱上提供服務，請驗證登入；在此之前，從 Cloud Run 中的日誌確認容器已啟動。
>
> 在第一次登入前，將 OAuth 用戶端的授權重新導向 URI 更新為 `<public_url>/oauth/callback`。變更 `public_url` 後重新部署，因為閘道僅從該設定建置其公用來源，並忽略 `X-Forwarded-Host` 和 `X-Forwarded-Proto`。`X-Forwarded-For` 僅在設定 `listen.trusted_proxies` 時才被接受用於用戶端 IP。

> [tab] GKE
>
> 叢集必須在 Cloud SQL 步驟中建立的 `$VPC` 上，以便 Pod 可以到達資料庫的私有 IP；VPC 對等單獨不起作用，因為 Cloud SQL 私有 IP 本身是對等網路，對等是非傳遞的。若要在該 VPC 上建立新叢集，請將 `--network="$VPC" --subnetwork=cc-gateway-subnet` 傳遞給 `gcloud container clusters create`。
>
> 在叢集及其節點池上啟用 Workload Identity，然後將 Google 服務帳戶繫結到 Kubernetes 服務帳戶，以便 Pod 繼承其認證：
>
> ```bash theme={null}
> gcloud container clusters update <cluster> --region="$REGION" \
>   --workload-pool="${PROJECT_ID}.svc.id.goog"
> # 在標準叢集上，現有節點池也需要 GKE_METADATA；
> # Autopilot 預設啟用此功能。
> gcloud container node-pools update <pool> --cluster=<cluster> \
>   --region="$REGION" --workload-metadata=GKE_METADATA
>
> kubectl create namespace claude-gateway
> kubectl create serviceaccount gateway -n claude-gateway
>
> gcloud iam service-accounts add-iam-policy-binding \
>   "claude-gateway@${PROJECT_ID}.iam.gserviceaccount.com" \
>   --role roles/iam.workloadIdentityUser \
>   --member "serviceAccount:${PROJECT_ID}.svc.id.goog[claude-gateway/gateway]"
>
> kubectl annotate serviceaccount gateway -n claude-gateway \
>   iam.gke.io/gcp-service-account="claude-gateway@${PROJECT_ID}.iam.gserviceaccount.com"
> ```
>
> 將閘道部署為標準 Deployment 加上 Service 和內部 Ingress，類別 `gce-internal`，如 [Kubernetes 部署](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#kubernetes)中所述，具有：
>
> * `serviceAccountName: gateway`
> * Secret Manager CSI 驅動程式在 `/secrets` 掛載祕密
> * 就緒探針指向 `GET /readyz`
>
> 將具有提高 `timeoutSec` 的 BackendConfig 附加到閘道 Service：GKE Ingress 後面的負載平衡器後端服務預設為 30 秒超時，這會切斷長串流回應。
>
> 不要在 Workload Identity 叢集上應用阻止 `169.254.169.254` 的出口 NetworkPolicy；Pod 必須到達中繼資料伺服器以取得認證。閘道的內建 [SSRF 防護](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#threat-model-summary)是那裡的防禦。
>
> 閘道記錄啟動警告，中繼資料端點可到達，並建議應用出口 NetworkPolicy。在 Workload Identity 下，該警告是預期的，因為 Pod 需要端點。

**8. 將閘道 URL 推送到開發人員機器**

閘道現在正在執行，但開發人員無法從 `/login` 到達它，直到閘道 URL 在他們的機器上。透過 MDM 將完整的[受管設定片段](https://code.claude.com/docs/zh-TW/claude-apps-gateway#set-the-gateway-url)部署到每個裝置，具有 `forceLoginMethod`、`forceLoginGatewayUrl` 和 `parentSettingsBehavior: "merge"` 選擇加入。登入選擇器中沒有閘道選項供開發人員手動選擇。

## Terraform 參考

[參考部署資產](https://github.com/anthropics/claude-code/tree/main/examples/gateway/gcp)自動化本頁面上的 Cloud Run 路徑；配置和映像資產適用於兩個路徑：

* `setup.sh`：一個冪等 `gcloud` 配置程式，遍歷完整的 Cloud Run 路徑，從啟用 API 到第一次部署
* `terraform/`：相同的部署作為基礎設施即程式碼，用於綠地部署：針對性應用以建立 Artifact Registry 儲存庫，然後建立和推送映像，然後完整應用
* `gateway.yaml.example` 和用於 distroless 執行時映像的 `Dockerfile`

工件預設 Cloud Run 入口為 `internal`，符合本頁面上的部署命令；該設定適用於在服務前面有或沒有內部 Application Load Balancer 的情況，工件也不會建立負載平衡器。工件也預設呼叫者層為 `allUsers` `run.invoker` 授予，而不是 `--no-invoker-iam-check`，與本頁面逐步解說相反；兩者都有效，選擇取決於您的組織的原則限制。

資產作為工作範例提供，而非受支援的生產工件；檢查並根據您的環境調整它們。

## 疑難排解

如需閘道啟動和登入錯誤，請參閱平台無關的[疑難排解表](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#troubleshooting)。下面的項目特定於 Google Cloud。

| 症狀 | 原因 | 修正 |
| - | - | - |
| Cloud Run 在到達容器之前返回 `403 Forbidden` | 呼叫者 IAM 檢查仍然啟用 | 使用 `--no-invoker-iam-check` 部署，或使用 `--allow-unauthenticated` 授予 `allUsers` `run.invoker` 角色 |
| `--no-invoker-iam-check` 被拒絕，出現 `invoker_iam_disabled is not currently available` | 被 `constraints/run.managed.requireInvokerIam` 阻止 | 使用 `--allow-unauthenticated`。如果透過 `constraints/iam.allowedPolicyMemberDomains` 的網域受限共用也阻止了它，請使用 GKE 路徑，它在網路層公開閘道，無需 `allUsers` 繫結。 |
| 部署時 `Container manifest type … must support amd64/linux` | 映像在非 amd64 主機上建立，或 buildx 發出了 OCI 映像索引 | 使用 `--platform=linux/amd64 --provenance=false` 建立 |
| 閘道啟動在 Cloud Run 上以 Postgres 連線逾時錯誤退出 | 服務未附加到 VPC，或 Cloud SQL 在該 VPC 上沒有私有 IP | 使用 `--network` 和 `--subnet` 部署以進行直接 VPC 出口，並使用 `--no-assign-ip` 和指向相同 VPC 的 `--network` 建立 Cloud SQL 執行個體 |
| Google Cloud 的 Agent Platform 請求返回 `403 PERMISSION_DENIED` | 執行時未使用 `claude-gateway` 服務帳戶，或模型未在 Model Garden 中為專案啟用 | 在 Cloud Run 上設定 `--service-account` 或在 GKE 上繫結 Workload Identity，並在 Model Garden 中為目標區域啟用每個 Claude 模型 |
| 串流回應在固定持續時間後切斷 | 前端請求超時：GKE Ingress 後面的負載平衡器後端服務預設為 30 秒，Cloud Run 預設為 300 秒 | 在 GKE 上附加具有提高 `timeoutSec` 的 BackendConfig，或在 Cloud Run 上使用 `--timeout=3600` 部署 |

## 後續步驟

* [配置參考](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md)：每個 `gateway.yaml` 選項，包括 `managed.policies` 和 `telemetry`
* [部署和操作](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md)：IdP 設定、健康檢查、JWT 祕密輪換、升級和安全模型
* [Claude 應用程式閘道概述](https://code.claude.com/docs/zh-TW/claude-apps-gateway)：快速入門和連接開發人員

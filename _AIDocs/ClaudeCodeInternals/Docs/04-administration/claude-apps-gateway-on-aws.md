<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/claude-apps-gateway-on-aws | lastmod: 2026-11-02 | section: Administration / Gateways -->
> 來源：https://code.claude.com/docs/zh-TW/claude-apps-gateway-on-aws（官方 zh-TW，lastmod 2026-11-02）｜分類：Administration › Gateways｜EN 摘要：A worked example of running Claude apps gateway on AWS: ECS Fargate or EKS, Amazon RDS for PostgreSQL, AWS Secrets Manager, and IAM-role auth to Amazon Bedrock.

# 在 AWS 上部署 Claude apps gateway

> 在 AWS 上執行 Claude apps gateway 的實際範例：ECS Fargate 或 EKS、Amazon RDS for PostgreSQL、AWS Secrets Manager 和 IAM 角色驗證至 Amazon Bedrock。

> [!NOTE]
>
> 本頁面介紹在 AWS 上執行 Claude apps gateway 的一種方式。此設定是客戶管理基礎設施的實際運作範例，而非受支援的生產部署；在將其調整至您自己的環境之前，請使用它來了解各個部分如何組合在一起。如需平台無關的需求，請參閱[部署指南](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md)。

此範例在 AWS 上佈建 Claude apps gateway，使用 Amazon Bedrock 作為模型上游，並使用 [Amazon ECS](https://aws.amazon.com/ecs/) on [AWS Fargate](https://aws.amazon.com/fargate/) 或 [Amazon EKS](https://aws.amazon.com/eks/) 進行計算。[Okta](https://www.okta.com/) 是範例身份提供者 (IdP)，但任何符合 OpenID Connect (OIDC) 的 IdP 都可以使用；有關各個 IdP 的詳細資訊，請參閱[身份提供者設定](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#identity-provider-setup)。

> [!NOTE]
>
> Bedrock 不是 AWS 上唯一的 Claude 上游。gateway 也支援 Claude Platform on AWS，這是 Anthropic 營運的 Claude API，具有 AWS 驗證和 AWS Marketplace 計費，可以代替 Bedrock 或與其並行使用。其上游項目、認證和 IAM 權限與本頁面的 Bedrock 範圍的不同；[Claude Platform on AWS 上游參考](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#claude-platform-on-aws)涵蓋了哪些內容會改變，本頁面的其餘部分保持不變。

## 架構

![AWS 上 Claude apps gateway 的圖表：Claude Code 客戶端透過 HTTPS 連接到內部應用程式負載平衡器，該平衡器位於 gateway（ECS Fargate 或 EKS）前面，gateway 在私有子網中執行，旁邊是用於工作階段狀態的 Amazon RDS for PostgreSQL 實例。gateway 透過 OIDC 讓使用者登入公司 IdP，從 AWS Secrets Manager 讀取機密，使用其 IAM 角色將模型請求轉發至 Amazon Bedrock，並在部署時從 Amazon ECR 提取其映像。](https://mintcdn.com/claude-code/PHweeRmDUYEKff49/images/claude-gateway-aws-architecture.svg?fit=max\&auto=format\&n=PHweeRmDUYEKff49\&q=85\&s=8599cc34aa28522cde208ee831439bb4)

範例架構，以 Amazon Bedrock 作為模型上游。Claude Platform on AWS 上游佔據相同位置。

gateway 在您的網路上作為私有 HTTPS 端點執行，開發人員透過您的 IdP 登入。他們的 Claude Code 工作階段透過 gateway 的 IAM 角色到達 Amazon Bedrock 上的 Claude 模型，因此沒有模型認證會落在開發人員機器上。參考設定佈建：

* **Amazon ECS on AWS Fargate** 服務或 **Amazon EKS** Deployment 執行 gateway 容器
* **Amazon ECR** 儲存庫用於 gateway 映像
* **Amazon RDS for PostgreSQL** 實例在私有子網中，不可公開存取，用於 gateway 的[儲存](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#store)
* **AWS Secrets Manager** 機密用於 JWT 簽署金鑰、OIDC 客戶端機密和 Postgres URL
* **IAM 角色**具有 `bedrock:InvokeModel`、`bedrock:InvokeModelWithResponseStream` 和 `bedrock:CountTokens`，附加為 ECS 任務角色或透過 EKS 上的 IAM Roles for Service Accounts (IRSA) 綁定
* **內部應用程式負載平衡器**用於 HTTPS

## 先決條件

此逐步解說建立 gateway 自己的資源，但它建立在您已經擁有的網路和身份基礎設施之上。在開始之前，您需要：

* 具有建立[上述資源](#architecture)權限的 AWS 帳戶
* 已安裝並[驗證](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-authentication.html)的 [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)，以及在本地安裝的 [Docker](https://docs.docker.com/get-started/get-docker/)
* 一個[VPC](https://docs.aws.amazon.com/vpc/latest/userguide/what-is-amazon-vpc.html)，至少有兩個[私有子網](https://docs.aws.amazon.com/vpc/latest/userguide/configure-subnets.html)在不同的可用區中，透過[NAT 閘道](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-nat-gateway.html)具有出站網際網路存取；內部負載平衡器需要兩個 AZ 中的子網，gateway 需要到 Bedrock 和您的 IdP 的出站流量
* 一個 Okta OIDC Web 應用程式，重新導向 URI 為 `https://<gateway-host>/oauth/callback`；請參閱[身份提供者設定](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#identity-provider-setup)
* gateway 的 TLS 主機名稱，通常是[Route 53 私有託管區域](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/hosted-zones-private.html)中的內部 DNS 名稱，指向負載平衡器，具有該名稱的 [ACM 憑證](https://docs.aws.amazon.com/acm/latest/userguide/gs.html)，由[AWS Private CA](https://docs.aws.amazon.com/privateca/latest/userguide/PcaWelcome.html)匯入或簽發

### 設定您的環境變數

此頁面上的每個命令都從您的 shell 讀取四個值：`AWS_REGION`、`ACCOUNT_ID`、`VPC_ID` 和 `PRIVATE_SUBNETS`。

選擇一個 Bedrock 提供您需要的 Claude 模型的美國區域。此逐步解說依賴 gateway 的內建模型目錄，該目錄解析為 `us.anthropic.*` 推論設定檔，IAM 原則授予這些 ARN。在非美國區域中，新增一個[`models:` 區塊](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#models)，其中包含該地理位置的推論設定檔 ID，並將 IAM 原則的 ARN 前綴更改為相符。

如果您手邊沒有 VPC ID，請使用 `aws ec2 describe-vpcs` 列出您的 VPC，然後列出該 VPC 的子網以找到兩個不同可用區中的私有子網：

```bash theme={null}
aws ec2 describe-subnets --filters "Name=vpc-id,Values=<your-vpc-id>" \
  --query 'Subnets[].{ID:SubnetId,AZ:AvailabilityZone,CIDR:CidrBlock}' --output table
```

在繼續之前匯出所有四個：

```bash theme={null}
export AWS_REGION=us-east-1   # Bedrock 提供您需要的 Claude 模型的美國區域
export ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
export VPC_ID=<your-vpc-id>
export PRIVATE_SUBNETS="<subnet-id-a> <subnet-id-b>"
```

## 部署 gateway

下面的步驟使用 `aws` 命令佈建完整部署。

**1. 建立安全群組**

三個安全群組鏈接流量路徑：您的公司網路在 443 上到達負載平衡器，負載平衡器在 8080 上到達 gateway，gateway 在 5432 上到達 Postgres。沒有其他任何東西是可到達的。您如何附加它們取決於計算軌道：

* 在 ECS Fargate 上，部署步驟將 `$ALB_SG` 附加到負載平衡器，將 `$GW_SG` 附加到服務。
* 在 EKS 上，AWS Load Balancer Controller 為 ALB 建立自己的前端安全群組，因此 `$ALB_SG` 和 `$GW_SG` 未使用：部署步驟的 `inbound-cidrs` 註釋將監聽器限制為您的公司網路，資料庫安全群組允許叢集的安全群組而不是 `$GW_SG`。

```bash theme={null}
ALB_SG="$(aws ec2 create-security-group --group-name claude-gateway-alb \
  --description "Claude gateway ALB" --vpc-id "$VPC_ID" \
  --query GroupId --output text)"
GW_SG="$(aws ec2 create-security-group --group-name claude-gateway-svc \
  --description "Claude gateway service" --vpc-id "$VPC_ID" \
  --query GroupId --output text)"
DB_SG="$(aws ec2 create-security-group --group-name claude-gateway-db \
  --description "Claude gateway Postgres" --vpc-id "$VPC_ID" \
  --query GroupId --output text)"

aws ec2 authorize-security-group-ingress --group-id "$ALB_SG" \
  --protocol tcp --port 443 --cidr <your-corporate-cidr>
aws ec2 authorize-security-group-ingress --group-id "$GW_SG" \
  --protocol tcp --port 8080 --source-group "$ALB_SG"
aws ec2 authorize-security-group-ingress --group-id "$DB_SG" \
  --protocol tcp --port 5432 --source-group "$GW_SG"
```

**2. 建立 IAM 角色並提交使用案例表單**

gateway 使用專用任務角色執行，其唯一權限是在 Bedrock 上叫用 Claude 模型。根據 [Bedrock 上游參考](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#amazon-bedrock)，原則必須涵蓋跨區域推論設定檔 ARN 和基礎基礎模型 ARN：

```bash theme={null}
cat > bedrock-invoke.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream", "bedrock:CountTokens"],
    "Resource": [
      "arn:aws:bedrock:${AWS_REGION}:${ACCOUNT_ID}:inference-profile/us.anthropic.*",
      "arn:aws:bedrock:*::foundation-model/anthropic.*"
    ]
  }]
}
EOF
cat > ecs-trust.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Service": "ecs-tasks.amazonaws.com" },
    "Action": "sts:AssumeRole"
  }]
}
EOF

aws iam create-role --role-name claude-gateway-task \
  --assume-role-policy-document file://ecs-trust.json
aws iam put-role-policy --role-name claude-gateway-task \
  --policy-name bedrock-invoke --policy-document file://bedrock-invoke.json
```

ECS 也需要執行角色，ECS agent 本身使用它從 ECR 提取映像並注入稍後建立的 Secrets Manager 值。它與 gateway 的 AWS SDK 在執行時使用的任務角色分開：

```bash theme={null}
aws iam create-role --role-name claude-gateway-execution \
  --assume-role-policy-document file://ecs-trust.json
aws iam attach-role-policy --role-name claude-gateway-execution \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
cat > secrets-read.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"],
    "Resource": [
      "arn:aws:secretsmanager:${AWS_REGION}:${ACCOUNT_ID}:secret:gateway-jwt-secret-??????",
      "arn:aws:secretsmanager:${AWS_REGION}:${ACCOUNT_ID}:secret:gateway-oidc-client-secret-??????",
      "arn:aws:secretsmanager:${AWS_REGION}:${ACCOUNT_ID}:secret:gateway-postgres-url-??????"
    ]
  }]
}
EOF
aws iam put-role-policy --role-name claude-gateway-execution \
  --policy-name read-gateway-secrets --policy-document file://secrets-read.json
```

原則按名稱一個 ARN 而不是裸 `gateway-*` 萬用字元，在共享帳戶中也會符合不相關的機密；尾部的 `-??????` 完全符合 Secrets Manager 附加到每個機密 ARN 的隨機六字元後綴。尾部的 `-*` 將是純前綴 glob，也會符合更長的名稱，例如 `gateway-postgres-url-prod`。

IAM 原則授予 gateway 呼叫 Bedrock 的權限，Bedrock 在商業區域中預設啟用模型存取。剩餘的帳戶級別閘道是 Anthropic 的一次性使用案例表單：如果您帳戶中沒有人提交過，請開啟 [Amazon Bedrock 主控台](https://console.aws.amazon.com/bedrock/)，從模型目錄中選擇 Anthropic 模型，並完成表單。提交後立即授予存取權；有關 AWS Organizations 表單和提交者需要的 IAM 權限，請參閱 [Claude Code on Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#1-submit-use-case-details)。

EKS 軌道改為在 IRSA 角色上重複使用兩個原則文件，而不是兩個 ECS 角色；請參閱部署步驟。

**3. 佈建 Amazon RDS for PostgreSQL**

實例在私有子網中執行 Postgres 16，沒有公開地址，儲存加密已開啟。

首先，建立將資料庫放在私有子網中的子網群組，以及具有 `rds.force_ssl=1` 的參數群組，以便伺服器拒絕純文字連接。引擎版本固定一次，因為參數群組的系列必須與實例執行的引擎主要版本相符：

```bash theme={null}
aws rds create-db-subnet-group --db-subnet-group-name claude-gateway-db \
  --db-subnet-group-description "Claude gateway" --subnet-ids $PRIVATE_SUBNETS

PG_VERSION=16
PG_FAMILY="postgres${PG_VERSION}"
aws rds create-db-parameter-group --db-parameter-group-name claude-gateway-db \
  --db-parameter-group-family "$PG_FAMILY" \
  --description "Claude gateway - require TLS on every connection"
aws rds modify-db-parameter-group --db-parameter-group-name claude-gateway-db \
  --parameters "ParameterName=rds.force_ssl,ParameterValue=1,ApplyMethod=immediate"
```

然後使用生成的主密碼建立實例：

```bash theme={null}
PGPASS="$(openssl rand -hex 24)"
aws rds create-db-instance --db-instance-identifier claude-gateway-db \
  --engine postgres --engine-version "$PG_VERSION" \
  --db-instance-class db.t4g.micro \
  --allocated-storage 20 --db-name claude_gateway \
  --master-username gateway --master-user-password "$PGPASS" \
  --db-subnet-group-name claude-gateway-db \
  --db-parameter-group-name claude-gateway-db \
  --vpc-security-group-ids "$DB_SG" \
  --no-publicly-accessible --storage-encrypted
```

字面 `--master-user-password` 引數在命令執行時在程序表和稽核/EDR 日誌中可見，與機密步驟的註釋涵蓋的相同曝露。在共享或受監控的主機上，改為從 `0600` 檔案透過 `--cli-input-json` 傳遞密碼，就像套件的 `setup.sh` 所做的那樣。

等待實例啟動，這可能需要幾分鐘，然後讀取其私有端點並組合 gateway 將使用的連接字串：

```bash theme={null}
aws rds wait db-instance-available --db-instance-identifier claude-gateway-db
DB_HOST="$(aws rds describe-db-instances --db-instance-identifier claude-gateway-db \
  --query 'DBInstances[0].Endpoint.Address' --output text)"
GATEWAY_POSTGRES_URL="postgres://gateway:${PGPASS}@${DB_HOST}:5432/claude_gateway?sslmode=verify-full"
```

`sslmode=verify-full` 使 gateway 驗證 RDS 伺服器憑證的鏈和主機名稱，不僅加密。信任錨是 [AWS RDS 憑證套件](https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem)，映像建置步驟下面將其複製到 `/etc/claude/rds-global-bundle.pem` 並透過 `NODE_EXTRA_CA_CERTS` 信任。不要將 libpq 風格的 `sslrootcert=` 參數附加到 URL：gateway 的驅動程式只從查詢字串讀取 `sslmode`，並會將 `sslrootcert` 轉發給 Postgres 作為啟動參數，伺服器會拒絕。

ECS 服務或 EKS pod 必須在此 VPC 中執行，以便它們可以到達實例的私有端點，`claude-gateway-db` 安全群組只允許 gateway 的安全群組。

**4. 寫入 gateway.yaml**

`upstreams` 區塊使用 `auth: {}` 指向 Bedrock，因此 gateway 透過 ECS 上的任務角色或 EKS 上的 IRSA 角色從 AWS 預設憑證鏈進行驗證。有關每個欄位，請參閱[設定參考](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md)。

兩個 `listen` 欄位描述什麼位於 gateway 前面：

* `public_url`：外部 `https://` 來源，非環回繫結時必需；請參閱 [`listen` 參考](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#listen)。gateway 僅從此值建置 IdP `redirect_uri` 和其發現文件，絕不從 `X-Forwarded-*` 標頭建置。
* `trusted_proxies`：前端的來源範圍。gateway 僅當 TCP 對等體在此清單中時才接受 `X-Forwarded-For`，然後在受信任的躍點之後遍歷鏈，因此每 IP 登入速率限制和稽核事件記錄開發人員 IP 而不是負載平衡器的。

在兩個軌道上，前端都是內部 ALB，無論是直接建立還是由 AWS Load Balancer Controller 建立，ALB 的節點從其附加到的子網中取得地址，因此將 `trusted_proxies` 設定為這些子網的 CIDR。這信任這些子網中的每個主機作為代理伺服器。保持 ALB 的入站來源（您的公司 CIDR）不與它們重疊，並且不要與可能透過 `X-Forwarded-For` 欺騙客戶端 IP 的不受信任的工作負載共享子網。

ALB 的客戶端連接埠保留屬性 `routing.http.xff_client_port.enabled` 可以保持任一設定：開啟時，ALB 將客戶端寫為 `203.0.113.7:54321` 或 `[2001:db8::1]:54321`，gateway 讀取兩者並刪除連接埠。

```yaml gateway.yaml theme={null}
listen:
  host: 0.0.0.0
  port: 8080
  public_url: https://claude-gateway.internal.example.com
  trusted_proxies: [<your-alb-subnet-cidrs>]

oidc:
  issuer: https://example.okta.com
  client_id: 0oa1example2
  client_secret: ${OIDC_CLIENT_SECRET}           # EKS: ${file:/secrets/oidc-client-secret}
  allowed_email_domains: [example.com]
  # Okta org 授權伺服器傳回省略電子郵件和群組的精簡 id_token；
  # gateway 從 /userinfo 填充它們。
  userinfo_fallback: true
  # Okta 僅在要求 `groups` 範圍且應用程式的群組宣告篩選器允許時才發出群組。
  scopes: [openid, profile, email, offline_access, groups]

session:
  jwt_secret: ${GATEWAY_JWT_SECRET}              # EKS: ${file:/secrets/jwt-secret}
  ttl_hours: 8 # 限制取消佈建延遲；降低
# 朝向 1 以獲得更緊密的撤銷

store:
  postgres_url: ${GATEWAY_POSTGRES_URL}          # EKS: ${file:/secrets/postgres-url}
  # readiness_grace_seconds: 300                 # 保持通過 RDS 容錯移轉
# 的健康檢查

upstreams:
  - provider: bedrock
    region: <your-region>                        # 符合 $AWS_REGION 以便 IAM
# 原則的 ARN 涵蓋它
    auth: {} # AWS 預設憑證鏈：
# ECS 任務角色，或 EKS 上的 IRSA
```

> [!NOTE]
>
> 只有 `oidc` 區塊是 Okta 特定的。若要改為使用 Microsoft Entra ID，請將 `issuer` 設定為 `https://login.microsoftonline.com/<tenant-id>/v2.0`，刪除 `userinfo_fallback` 和 `groups` 範圍，並注意 Entra 發出群組物件 ID 而不是名稱，因此 [`managed.policies`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#managed) 必須符合 GUID，或使用 `oidc.groups_claim: roles` 的應用程式角色。請參閱[身份提供者設定](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#identity-provider-setup)。

**5. 在 AWS Secrets Manager 中儲存機密**

建立三個機密；IAM 步驟中的執行角色已經可以讀取它們：

```bash theme={null}
aws secretsmanager create-secret --name gateway-jwt-secret \
  --secret-string "$(openssl rand -base64 32)"
aws secretsmanager create-secret --name gateway-oidc-client-secret \
  --secret-string '<your-okta-client-secret>'
aws secretsmanager create-secret --name gateway-postgres-url \
  --secret-string "$GATEWAY_POSTGRES_URL"
```

注意每個呼叫列印的 ARN；ECS 任務定義按 ARN 參考機密。

> [!NOTE]
>
> 字面 `--secret-string` 引數在每個命令執行時在程序表和稽核/EDR 日誌中可見。在共享或受監控的主機上，將值放在 `0600` 檔案中，改為傳遞 `--secret-string file://<path>`。套件的 `setup.sh` 以相同方式將機密值保持在程序 argv 之外，將 `0600` 臨時檔案傳遞給 `--cli-input-json`。

與機密不同，`gateway.yaml` 本身不包含機密值，因為每個憑證在啟動時透過 [`${VAR}` 或 `${file:...}` 擴展](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#secret-expansion)解析。一切如何到達容器因軌道而異：

* 在 ECS 上，下一步的建置將 `gateway.yaml` 複製到映像中的 `/etc/claude/gateway.yaml`，任務定義透過其 `secrets` 欄位將三個機密注入為環境變數，因此 YAML 參考 `${GATEWAY_JWT_SECRET}`、`${OIDC_CLIENT_SECRET}` 和 `${GATEWAY_POSTGRES_URL}`。
* 在 EKS 上，從 ConfigMap 掛載 `gateway.yaml` 和機密作為 `/secrets` 中的檔案，參考為 `${file:/secrets/...}`。使用 External Secrets Operator 或 Secrets Store CSI 驅動程式的 AWS 提供者從 Secrets Manager 來源 Kubernetes Secrets，或使用 `kubectl` 直接建立它們。

**6. 建置映像並推送到 Amazon ECR**

根據[容器映像需求](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#container-image)建置映像，將 `linux-x64` glibc 二進位檔案放在建置上下文中的 `./claude`。編寫您自己的 Dockerfile 根據這些需求或從套件的 [`Dockerfile`](https://github.com/anthropics/claude-code/blob/main/examples/gateway/aws/Dockerfile) 開始，它將填充的 `gateway.yaml` 從前面的步驟複製到映像中的 `/etc/claude/gateway.yaml`。在 ECS 上，該嵌入副本是設定到達容器的方式，這就是為什麼建置在檔案寫入後進行。EKS 軌道改為在部署時從 ConfigMap 掛載 `gateway.yaml`，因此嵌入副本在那裡未使用。

映像也攜帶 AWS RDS 憑證套件作為連接字串的 `sslmode=verify-full` 的信任錨，因此首先將其下載到建置上下文中。AWS 輪換套件（新的區域 CA 被附加），因此每次建置時下載它，而不是固定校驗和或提交它：

```bash theme={null}
curl -fL --proto '=https' -o rds-global-bundle.pem \
  https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem
```

容器映像需求不涵蓋套件，因此如果您編寫自己的 Dockerfile，新增複製和信任它的兩行；套件的 `Dockerfile` 已經包含兩者：

```dockerfile theme={null}
COPY rds-global-bundle.pem /etc/claude/rds-global-bundle.pem
ENV NODE_EXTRA_CA_CERTS=/etc/claude/rds-global-bundle.pem
```

建立 ECR 儲存庫並將 Docker 登入到它。不可變標籤意味著部署步驟固定的 `<version>` 標籤之後無法無聲地重新指向不同的映像：

```bash theme={null}
aws ecr create-repository --repository-name claude-gateway \
  --image-tag-mutability IMMUTABLE \
  --image-scanning-configuration scanOnPush=true
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin \
    "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
```

建置並推送映像。下面的任務定義執行 `linux/amd64`，因此平台必須在此處相符；對於 Fargate on ARM64 (Graviton)，使用 `linux-arm64` 二進位檔案建置 `linux/arm64` 並改為將 `cpuArchitecture` 設定為 `ARM64`：

```bash theme={null}
docker build --platform=linux/amd64 \
  -t "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/claude-gateway:<version>" .
docker push "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/claude-gateway:<version>"
```

**7. 部署**

> [tab] ECS Fargate
>
> 建立叢集和 gateway 的日誌群組，用於其 stderr，其中包含其稽核事件和操作日誌。保留期是單獨的呼叫，若不設定，CloudWatch 會永遠保留日誌；將 90 天與您的稽核保留原則對齊：
>
> ```bash theme={null}
> aws ecs create-cluster --cluster-name claude-gateway
> aws logs create-log-group --log-group-name /ecs/claude-gateway
> aws logs put-retention-policy --log-group-name /ecs/claude-gateway \
>   --retention-in-days 90
> ```
>
> 寫入任務定義。任務角色攜帶 Bedrock 權限，執行角色注入機密；使用 Secrets Manager 步驟中的機密 ARN：
>
> ```json claude-gateway-task.json theme={null}
> {
>   "family": "claude-gateway",
>   "networkMode": "awsvpc",
>   "requiresCompatibilities": ["FARGATE"],
>   "cpu": "1024",
>   "memory": "2048",
>   "runtimePlatform": { "cpuArchitecture": "X86_64", "operatingSystemFamily": "LINUX" },
>   "executionRoleArn": "arn:aws:iam::<account-id>:role/claude-gateway-execution",
>   "taskRoleArn": "arn:aws:iam::<account-id>:role/claude-gateway-task",
>   "containerDefinitions": [
>     {
>       "name": "gateway",
>       "image": "<account-id>.dkr.ecr.<region>.amazonaws.com/claude-gateway:<version>",
>       "portMappings": [{ "containerPort": 8080 }],
>       "secrets": [
>         { "name": "GATEWAY_JWT_SECRET",   "valueFrom": "<gateway-jwt-secret ARN>" },
>         { "name": "OIDC_CLIENT_SECRET",   "valueFrom": "<gateway-oidc-client-secret ARN>" },
>         { "name": "GATEWAY_POSTGRES_URL", "valueFrom": "<gateway-postgres-url ARN>" }
>       ],
>       "logConfiguration": {
>         "logDriver": "awslogs",
>         "options": {
>           "awslogs-group": "/ecs/claude-gateway",
>           "awslogs-region": "<region>",
>           "awslogs-stream-prefix": "gateway"
>         }
>       }
>     }
>   ]
> }
> ```
>
> 註冊它：
>
> ```bash theme={null}
> aws ecs register-task-definition --cli-input-json file://claude-gateway-task.json
> ```
>
> 在前面放置內部 ALB，具有對 gateway 進行健康檢查的目標群組。`--ip-address-type ipv4` 很重要：內部雙堆疊 ALB 發佈公開範圍 AAAA 記錄，`/login` 私有網路檢查拒絕：
>
> ```bash theme={null}
> ALB_ARN="$(aws elbv2 create-load-balancer --name claude-gateway \
>   --scheme internal --type application --ip-address-type ipv4 \
>   --subnets $PRIVATE_SUBNETS --security-groups "$ALB_SG" \
>   --query 'LoadBalancers[0].LoadBalancerArn' --output text)"
>
> TG_ARN="$(aws elbv2 create-target-group --name claude-gateway \
>   --protocol HTTP --port 8080 --vpc-id "$VPC_ID" --target-type ip \
>   --health-check-path /readyz \
>   --query 'TargetGroups[0].TargetGroupArn' --output text)"
> ```
>
> 新增 HTTPS 監聽器。`--ssl-policy` 固定現代 TLS 下限，因為省略它會回到舊版 `ELBSecurityPolicy-2016-08` 預設值，仍然接受 TLS 1.0/1.1。
>
> ALB 預設在 60 秒後沒有資料的連接關閉。gateway 的保活 ping 保持串流在該預設值內，因此提高逾時在 ping 頻率上方增加邊距；[疑難排解](#troubleshooting)行關於掉落的串流涵蓋機制和較舊的 gateway。下面的命令新增監聽器並提高逾時：
>
> ```bash theme={null}
> aws elbv2 create-listener --load-balancer-arn "$ALB_ARN" \
>   --protocol HTTPS --port 443 \
>   --ssl-policy ELBSecurityPolicy-TLS13-1-2-2021-06 \
>   --certificates CertificateArn=<your-acm-certificate-arn> \
>   --default-actions Type=forward,TargetGroupArn="$TG_ARN"
>
> aws elbv2 modify-load-balancer-attributes --load-balancer-arn "$ALB_ARN" \
>   --attributes Key=idle_timeout.timeout_seconds,Value=3600
> ```
>
> 建立服務。部署斷路器將其任務持續失敗的部署（來自不良映像或無法啟動的設定）回滾到最後穩定狀態，而不是永遠重新啟動失敗的任務：
>
> ```bash theme={null}
> aws ecs create-service --cluster claude-gateway --service-name claude-gateway \
>   --task-definition claude-gateway --desired-count 1 --launch-type FARGATE \
>   --deployment-configuration "deploymentCircuitBreaker={enable=true,rollback=true}" \
>   --health-check-grace-period-seconds 60 \
>   --network-configuration "awsvpcConfiguration={subnets=[$(echo $PRIVATE_SUBNETS | tr ' ' ',')],securityGroups=[$GW_SG],assignPublicIp=DISABLED}" \
>   --load-balancers "targetGroupArn=$TG_ARN,containerName=gateway,containerPort=8080"
> ```
>
> 60 秒的寬限期給冷任務時間拉取映像、連接到儲存並在 ECS 開始計算針對部署的失敗之前回答其第一個健康檢查。
>
> 目標群組在 `GET /readyz` 上的健康檢查驗證儲存是否可到達，因此無法到達 Postgres 的任務永遠不會進入輪換。為了保持任務通過短資料庫中斷（例如 RDS 容錯移轉）的健康檢查，請設定 `store.readiness_grace_seconds`，如[中斷行為](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#outage-behavior)所述，其中也涵蓋 `/healthz` 替代方案。
>
> 任務在沒有公開 IP 的私有子網中執行，因此所有出站流量（到 Bedrock、您的 IdP、Secrets Manager、ECR 和 CloudWatch Logs）都透過 NAT 閘道。為了保持 Bedrock 流量不走公開路徑，建立 `bedrock-runtime` 介面 VPC 端點並將上游的 `base_url` 指向它，如 [Bedrock 上游參考](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#amazon-bedrock)所示；IdP 仍然需要網際網路出站。
>
> 完成方式是給開發人員一個私有可解析的主機名稱：在 Route 53 私有託管區域中，將 gateway 的內部 DNS 名稱別名到 ALB，並將 `listen.public_url` 設定為該主機名稱。ALB 自己的 `*.elb.amazonaws.com` 名稱解析為內部 ALB 上的私有地址，但它無法攜帶您的 ACM 憑證，因此使用您自己的名稱。
>
> 在第一次登入之前，將 OAuth 客戶端的授權重新導向 URI 更新為 `<public_url>/oauth/callback`。更改 `public_url` 後，在新標籤下重建並推送映像，註冊新任務定義修訂版本，然後重新部署。在 ECS 上，設定位於映像的嵌入 `gateway.yaml` 中，gateway 僅從該設定建置其公開來源，忽略 `X-Forwarded-Host` 和 `X-Forwarded-Proto`。`X-Forwarded-For` 僅在設定 `listen.trusted_proxies` 時才被接受用於客戶端 IP。

> [tab] EKS
>
> 此軌道需要在本地安裝 `kubectl` 和 `eksctl`，以及具有 IAM OIDC 提供者和已安裝 AWS Load Balancer Controller 的現有 EKS 叢集。叢集必須在 `$VPC_ID` 上，以便 pod 可以到達 RDS 私有端點，`claude-gateway-db` 安全群組必須允許叢集的 pod 或節點安全群組而不是 `$GW_SG`。
>
> 在 EKS 上，gateway 透過 IRSA 而不是 ECS 角色取得其 Bedrock 憑證。IAM 步驟中的 `ecs-tasks.amazonaws.com` 信任原則在此不適用；IRSA 需要一個信任原則在叢集的 OIDC 提供者上聯合的角色，範圍為 `system:serviceaccount:claude-gateway:gateway`。`eksctl create iamserviceaccount` 在一個步驟中建立該角色、附加原則並使用角色 ARN 註釋 Kubernetes 服務帳戶。將 IAM 步驟中的兩個原則文件轉換為它可以附加的受管原則：
>
> ```bash theme={null}
> BEDROCK_POLICY_ARN="$(aws iam create-policy --policy-name claude-gateway-bedrock-invoke \
>   --policy-document file://bedrock-invoke.json --query Policy.Arn --output text)"
> SECRETS_POLICY_ARN="$(aws iam create-policy --policy-name claude-gateway-secrets-read \
>   --policy-document file://secrets-read.json --query Policy.Arn --output text)"
>
> kubectl create namespace claude-gateway
> eksctl create iamserviceaccount --cluster <your-cluster> --region "$AWS_REGION" \
>   --namespace claude-gateway --name gateway --role-name claude-gateway \
>   --attach-policy-arn "$BEDROCK_POLICY_ARN" \
>   --attach-policy-arn "$SECRETS_POLICY_ARN" \
>   --approve
> ```
>
> 機密原則僅在 pod 自己讀取 Secrets Manager 時才需要，如 Secrets Store CSI 驅動程式的 AWS 提供者使用掛載 pod 的服務帳戶所做的那樣；如果您以其他方式建立 Kubernetes Secrets，請刪除它。提供者需要原則的兩個動作：它在協調輪換的機密時呼叫 `DescribeSecret`，因此僅 `GetSecretValue` 授予在第一次部署時掛載但停止拾取輪換。
>
> 將 gateway 部署為標準 Deployment 加上 Service 和 Ingress，如[Kubernetes 部署](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#kubernetes)所述，具有：
>
> * `serviceAccountName: gateway`
> * 從 ConfigMap 掛載的 `gateway.yaml` 和掛載在 `/secrets` 的機密
> * 就緒探針指向 `GET /readyz`
>
> 對於前端，由 AWS Load Balancer Controller 管理的 Ingress 佈建內部 ALB。使用以下註釋進行註釋：
>
> * `alb.ingress.kubernetes.io/scheme: internal` 和 `alb.ingress.kubernetes.io/target-type: ip`
> * `alb.ingress.kubernetes.io/ip-address-type: ipv4`，因此不會發佈會被 `/login` [私有網路檢查](https://code.claude.com/docs/zh-TW/claude-apps-gateway#prerequisites)拒絕的公開範圍 AAAA 記錄
> * `alb.ingress.kubernetes.io/inbound-cidrs: <your-corporate-cidr>`，因此控制器管理的前端安全群組僅允許您的公司網路代替其 `0.0.0.0/0` 預設值
> * `alb.ingress.kubernetes.io/certificate-arn` 與 ACM 憑證
> * `alb.ingress.kubernetes.io/ssl-policy: ELBSecurityPolicy-TLS13-1-2-2021-06`，因此監聽器不會回到接受 TLS 1.0 和 1.1 的舊版預設原則
> * `alb.ingress.kubernetes.io/load-balancer-attributes: idle_timeout.timeout_seconds=3600`，在 gateway 的串流保活上方的邊距；請參閱[疑難排解](#troubleshooting)
>
> 使用 IRSA，AWS SDK 讀取投影的服務帳戶權杖並與 AWS STS 交換它，因此 pod 永遠不需要 EC2 實例中繼資料服務；出站 NetworkPolicy 可能會為 gateway pod 阻止 `169.254.169.254`。下面[疑難排解](#troubleshooting)中的節點躍點限制問題僅適用於跳過 IRSA 並依賴節點實例角色的叢集。

**8. 將 gateway URL 推送到開發人員機器**

gateway 現在正在執行，但開發人員無法從 `/login` 到達它，直到 gateway URL 在他們的機器上。透過 MDM 將完整的[受管設定片段](https://code.claude.com/docs/zh-TW/claude-apps-gateway#set-the-gateway-url)部署到每個裝置，其中包含 `forceLoginMethod`、`forceLoginGatewayUrl` 以及 `parentSettingsBehavior: "merge"` 選擇加入設定。登入選擇器中沒有 gateway 選項供開發人員手動選擇。

## Terraform 參考

[`examples/gateway/aws`](https://github.com/anthropics/claude-code/tree/main/examples/gateway/aws) 中的配套套件將此頁面打包為程式碼：

* **`setup.sh`** 使用相同的 `aws` 命令在 ECS Fargate 軌道上編寫佈建逐步解說。它是冪等的：現有資源被檢測並跳過，因此重新執行它是安全的，任何預設值都可以透過環境變數覆蓋。您仍然自己建立 Okta OIDC 客戶端機密和 ACM 憑證：沒有它們的執行會跳過 ECS/ALB 部署，命名缺失的輸入，並列印 `create-secret` 命令；建立兩者並重新執行。Bedrock 使用案例表單和 Route 53 別名列印為下一步而不是自動執行，客戶端 MDM 推送保持此頁面的手動步驟。
* **`gateway.yaml.example`** 是 gateway.yaml 步驟中的設定範本，包含可選金鑰註釋掉。將其複製到 `gateway.yaml` 並在建置前替換每個 `REPLACE_ME`。
* **`Dockerfile`** 從預建的 `linux-x64` 二進位檔案建置執行時映像，並將您填充的 `gateway.yaml` 複製到 `/etc/claude/gateway.yaml`，加上錨定儲存的 `sslmode=verify-full` 的 AWS RDS 憑證套件。`setup.sh` 僅在建置上下文中尚不存在時下載套件；刪除檔案並在新標籤下重建以拾取 AWS CA 輪換。設定檔不包含機密值，因為每個認證在啟動時透過 `${VAR}` 擴展解析。因此，設定編輯意味著在新標籤下重建；`setup.sh` 透過使用檔案的雜湊標記映像來自動化此操作。
* **`terraform/`** 聲明性地佈建相同的 ECS Fargate 範圍：安全群組、IAM 角色、ECR 儲存庫、RDS 實例、Secrets Manager 機密和內部 ALB 後面的 ECS 服務。VPC 和私有子網保持先決條件，作為變數傳入。Terraform 建立 ECR 儲存庫但不建置映像，服務定義參考映像，因此應用是兩個通過：儲存庫的目標應用，然後建置和推送，然後完整應用。套件的 `terraform/README.md` 涵蓋變數、遠端狀態和拆除。

像此頁面一樣，套件是客戶管理基礎設施的實際運作範例，而非受支援的生產部署；在依賴它之前，檢查並將其調整至您自己的環境。

## 故障排除

如需 gateway 啟動和登入錯誤，請參閱平台無關的[故障排除表](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#troubleshooting)。下面的項目特定於 AWS。

| 症狀 | 原因 | 修復 |
| - | - | - |
| CLI `/login`：`Gateway hosts must be on your organization's private network; <host> resolves to the public (or unrecognized) address <ip>` | gateway 名稱解析為至少一個公開地址。雙堆疊內部 ALB 發佈公開範圍 AAAA 記錄，[私有網路檢查](https://code.claude.com/docs/zh-TW/claude-apps-gateway#prerequisites)要求每個解析的地址都是私有的 | 使用 `--ip-address-type ipv4` 建立 ALB，或提供沒有公開 AAAA 記錄的單獨內部 DNS 名稱 |
| 每個 Bedrock 請求都傳回 502；日誌顯示 `Could not load credentials from any providers` | 任務在沒有任務角色的 ECS EC2 啟動類型上執行，或 pod 在沒有 IRSA 的 EKS 節點上執行，因此認證來自實例中繼資料，IMDSv2 的預設躍點限制 1 在容器內停止。此頁面上的兩個軌道都不受影響：Fargate 任務角色和 IRSA 不使用實例中繼資料 | 偏好任務角色和 IRSA。在實例認證不可避免的地方，使用 `aws ec2 modify-instance-metadata-options --instance-id <id> --http-put-response-hop-limit 2` 提高躍點限制；[平台無關表](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#troubleshooting)涵蓋權衡 |
| Bedrock 請求傳回 `403 AccessDeniedException` | 帳戶尚未提交 Anthropic 的一次性使用案例表單，自動 AWS Marketplace 訂閱在帳戶的第一次叫用時啟動尚未完成，或任務角色的原則缺少推論設定檔或基礎模型 ARN | 從 Bedrock 主控台的模型目錄提交使用案例表單；如果剛剛提交或這是帳戶的第一次叫用，請在幾分鐘後重試。在兩個 ARN 系列上授予 `bedrock:InvokeModel` 和 `bedrock:InvokeModelWithResponseStream`。 |
| Bedrock 傳回 `ValidationException` 說不支援按需輸送量 | 自訂 `models:` 項目對應到區域僅透過推論設定檔提供的裸基礎模型 ID | 改為將模型對應到其跨區域推論設定檔 ID (`us.anthropic.*`)；內建目錄已經這樣做 |
| ECS 任務在 gateway 記錄任何內容之前停止，出現 `ResourceInitializationError` | 執行角色無法讀取 Secrets Manager 機密，或私有子網沒有到 Secrets Manager 或 ECR 的路徑 | 在三個 `gateway-` 機密的 ARN 上授予 `secretsmanager:GetSecretValue` 給執行角色，並透過 NAT 閘道提供出站，或沒有一個，Secrets Manager、ECR 和 CloudWatch Logs 的介面端點，`awslogs` 驅動程式在同一階段需要，加上 S3 閘道端點 |
| Gateway 啟動退出，出現 Postgres 連接逾時錯誤 | 資料庫安全群組不允許 gateway 的安全群組在 5432 上，或服務在資料庫的 VPC 外執行 | 在資料庫的安全群組上允許來自 gateway 安全群組的 5432，並在與 DB 子網群組相同的 VPC 中執行服務 |
| Gateway 啟動退出，出現 Postgres TLS 憑證驗證錯誤 | 連接字串設定 `sslmode=verify-full` 但映像不信任 RDS CA 套件：套件未複製到映像中，或 `NODE_EXTRA_CA_CERTS` 不指向它 | 新增建置步驟的兩個 Dockerfile 行，複製套件並設定 `NODE_EXTRA_CA_CERTS`，然後重建、在新標籤下推送並重新部署 |
| 串流回應在安靜期間中途掉落 | v2.1.229 之前的 gateway 在 Bedrock 或 Claude Platform on AWS 上游上在上游安靜時不發送任何內容，例如沒有串流輸出的擴展思考。ALB 預設在 60 秒後沒有資料的連接關閉，因此它在該間隙處切斷串流。v2.1.229 及更新版本的 gateway 在該逾時下保持安靜串流：在這些上游上，gateway 在大約 15 秒後沒有串流資料時發出 SSE `ping` 事件，在 Anthropic API 上游上它中繼 API 自己的 ping | 將 gateway 更新到 v2.1.229 或更新版本，或透過 `modify-load-balancer-attributes` 或 EKS 上的 `load-balancer-attributes` Ingress 註釋將 `idle_timeout.timeout_seconds` 屬性設定為 `3600` |

## 遙測

閘道為您提供每位開發者的使用指標，無需任何每台機器的 OTEL 設定。Claude Code 發出 OpenTelemetry (OTLP) 指標、日誌和選擇性追蹤；[監控使用情況](https://code.claude.com/docs/zh-TW/monitoring-usage.md)涵蓋 CLI 報告的所有內容。在透過 `/login` 登入的工作階段中，CLI 會使用已驗證的 IdP 身分屬性 `user.id`、`user.email` 和 `user.groups` [為每個匯出加上戳記](https://code.claude.com/docs/zh-TW/monitoring-usage.md#standard-attributes)，因此使用情況會按開發者彙總。

閘道本身是一個已驗證的 OTLP 中繼。將 [`telemetry.forward_to`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#telemetry) 與 `listen.public_url` 一起設定，它會將 OTEL 匯出器設定推送到每個連接的用戶端，並將其 OTLP 流量逐字轉發到您列出的每個目的地。每個目的地獨立選擇加入指標、日誌和追蹤，預設值為僅限指標；請參閱 [`telemetry` 參考](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#telemetry)以了解每個信號欄位及其敏感性權衡。閘道不會緩衝、彙總或儲存遙測，因此資料最終位置完全由收集器的匯出器設定決定。

用戶端遙測預設為關閉；設定 `telemetry.forward_to` 是為連接的開發者開啟它的方式，每個互動式用戶端都會顯示推送設定的安全核准對話框，如[設定參考](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#telemetry)中所述。在 AWS 上，每個信號對應到目的地如下。

### 用戶端指標、日誌和追蹤

將 `telemetry.forward_to` 指向 OpenTelemetry 收集器，例如 [AWS Distro for OpenTelemetry (ADOT) 收集器](https://aws-otel.github.io/)，並從那裡匯出到 Amazon CloudWatch、Amazon Managed Service for Prometheus 或任何 OTLP 後端。

將收集器作為其自己的內部服務執行，可透過 `https://` 存取；[`telemetry` 參考](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#telemetry)涵蓋迴圈例外和 `CLAUDE_GATEWAY_ALLOW_LOOPBACK`。

### 閘道日誌

在 ECS Fargate 上，無需額外設定：`awslogs` 驅動程式將閘道的 stderr（包含其稽核事件和操作日誌）傳遞到上面建立的 `/ecs/claude-gateway` 日誌群組。在 EKS 上，Pod 日誌預設不會到達 CloudWatch，因此稽核軌跡會遺失，直到您安裝日誌收集：啟用容器日誌擷取的 Amazon CloudWatch Observability 附加元件，或 Fluent Bit DaemonSet。在任一軌跡上，使用 CloudWatch Logs Insights 查詢日誌，並從指標篩選器驅動警報。

### 容器指標

在叢集上啟用 Container Insights，使用 `aws ecs update-cluster-settings --cluster claude-gateway --settings name=containerInsights,value=enabled` 以取得每個工作的 CPU、記憶體和網路。在 EKS 上，安裝 Amazon CloudWatch Observability 附加元件。

### 支出

遙測顯示事後使用情況；[支出限制](https://code.claude.com/docs/zh-TW/claude-apps-gateway-spend-limits.md)是閘道的即時每位開發者檢視和強制執行。

## 成本歸屬

閘道使用其自身的主體（ECS 任務角色或 EKS IRSA 角色）簽署每個 Bedrock 請求，因此預設情況下 AWS 會在一個 IAM 主體下看到所有支出。有兩種方式可以在 AWS 的計費資料中分割它，並且它們可以結合使用。

### 使用 `assume_role` 按開發人員

建立第二個 IAM 角色，該角色持有 Bedrock 權限並信任閘道的主體，授予該主體對其的 `sts:AssumeRole` 權限，並在 Bedrock 上游上設定 [`assume_role`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#per-developer-aws-cost-attribution)，其中 `session_name: email`。閘道隨後每小時為每個開發人員假設該角色一次，並將工作階段名稱設定為其電子郵件，並使用結果簽署其請求。需要執行 Claude Code v2.1.281 或更新版本的閘道。該角色也可以在另一個 AWS 帳戶中：請參閱[另一個 AWS 帳戶中的 Bedrock](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#bedrock-in-another-aws-account)。在 Terraform 中，在 [Terraform 參考](#terraform-reference)中的任務角色旁邊：

```hcl theme={null}
resource "aws_iam_role" "bedrock_user" {
  name = "claude-gateway-bedrock-user"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { AWS = aws_iam_role.task.arn } }]
  })
}
resource "aws_iam_role_policy" "bedrock_user_invoke" {   # same Bedrock policy as the task role's
  role   = aws_iam_role.bedrock_user.id
  policy = aws_iam_role_policy.bedrock_invoke.policy
}
resource "aws_iam_role_policy" "task_assume_bedrock_user" {
  role   = aws_iam_role.task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Resource = aws_iam_role.bedrock_user.arn }]
  })
}
```

設定 `assume_role` 後，閘道會使用假設角色的認證簽署每個 Bedrock 呼叫，包括用於支出計量的免費 `CountTokens` 呼叫，因此閘道的主體只需要針對沒有 `assume_role` 的上游擁有自己的 Bedrock 策略。

因為閘道在請求時呼叫 STS，私有子網需要到 `sts.<region>.amazonaws.com` 的路徑。先決條件中的 NAT 閘道提供了一個，STS 介面 VPC 端點也提供了一個，該端點回應該主機名稱。每個活躍開發人員每小時每個閘道副本成本為一個 STS 呼叫。

每個開發人員的請求以主體 `arn:aws:sts::<account>:assumed-role/<role>/<email>` 的身份到達 AWS。若要查看每個主體的支出，請使用包含 IAM 主體資料的計費匯出；AWS 的 [IAM 主體成本分配](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/iam-principal-cost-allocation.html)頁面涵蓋如何啟用它以及哪些計費工具顯示它。

### 使用應用程式推論設定檔按團隊

此路由僅使用 [`models`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#models) 和 [`managed`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#managed) 部分。為每個團隊和模型建立一個 Bedrock [應用程式推論設定檔](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-profiles-create.html)，使用團隊標記每個設定檔，並啟用該標記作為成本分配標記。然後在 `gateway.yaml` 中為每個團隊提供其自己的模型 ID，並將每個 IdP 群組固定到其團隊的 ID：

```yaml theme={null}
models:
  # Include the served model's id, such as claude-opus-4-8, in each id so the gateway's spend meter can price it.
  - id: platform-claude-opus-4-8
    upstream_model:
      bedrock: arn:aws:bedrock:us-east-1:123456789012:application-inference-profile/abc123
  - id: data-claude-opus-4-8
    upstream_model:
      bedrock: arn:aws:bedrock:us-east-1:123456789012:application-inference-profile/def456
managed:
  policies:
    - match: {groups: [team-platform]}
      cli: {availableModels: [platform-claude-opus-4-8], enforceAvailableModels: true}
    - match: {groups: [team-data]}
      cli: {availableModels: [data-claude-opus-4-8], enforceAvailableModels: true}
    - match: {}
      cli: {availableModels: [claude-opus-4-8, claude-sonnet-4-6], enforceAvailableModels: true}
```

告訴固定團隊中的開發人員使用 `--model platform-claude-opus-4-8` 啟動 Claude Code，使用其團隊的 ID，因為在沒有它的情況下啟動的工作階段會執行預設模型，閘道會為他們拒絕該模型。

閘道在每個請求上強制執行 `availableModels`，不僅在模型選擇器中，AWS 計費會按您啟用的標記對支出進行分組。如果沒有 `match: {}` 全部捕捉，與任何策略都不匹配的開發人員會獲得目錄中的每個模型，並可以計費任一團隊的設定檔。

成本：

* 設定會隨著團隊乘以模型而增長
* 簽署此上游 Bedrock 請求的角色也必須被允許呼叫 `application-inference-profile/*` ARN。該角色是閘道的主體，或者使用 `assume_role` 時是它假設的角色。

請參閱[請求如何定價](https://code.claude.com/docs/zh-TW/claude-apps-gateway-spend-limits.md#how-requests-are-priced)以了解閘道自身的支出計量如何為這些 ID 定價。

#### 讓開發人員選擇要計費的團隊

若要讓同時為兩個團隊工作的開發人員選擇每個工作階段要計費給哪個團隊，請為這對團隊提供專屬的 IdP 群組和策略。

**1. 為這對團隊新增群組**

在您的 IdP 中，將該開發人員新增至新群組，例如 `team-platform-and-data`。如果他們已經登入，請讓他們再次執行 `/login`，或等待下一次[靜默重新整理](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#managed)，讓閘道看到新群組。

**2. 將其策略列在最前面**

將該群組的策略放在單一團隊策略之上，並在其中允許兩個團隊的 ID。複製兩個團隊策略所設定的任何其他設定。

```yaml theme={null}
managed:
  policies:
    - match: {groups: [team-platform-and-data]}
      cli: {availableModels: [platform-claude-opus-4-8, data-claude-opus-4-8], enforceAvailableModels: true}
    - match: {groups: [team-platform]}
      cli: {availableModels: [platform-claude-opus-4-8], enforceAvailableModels: true}
    - match: {groups: [team-data]}
      cli: {availableModels: [data-claude-opus-4-8], enforceAvailableModels: true}
    - match: {}
      cli: {availableModels: [claude-opus-4-8, claude-sonnet-4-6], enforceAvailableModels: true}
```

**3. 以團隊的 ID 啟動每個工作階段**

讓開發人員傳入該工作所屬團隊的 ID，例如 `claude --model data-claude-opus-4-8`。

預設情況下，閘道會套用[第一個符合的策略](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#managed)，因此僅屬於兩個團隊群組的開發人員會取得 `team-platform` 策略。他們以資料團隊 ID 啟動的工作階段會失敗並顯示 `is not in your role's availableModels allowlist`，其中指名的是 Claude Code 的預設模型，而非他們輸入的 ID。如果您改為在一個策略的 `groups` 中列出兩個團隊群組，則任一團隊中的每個人都可以計費任一團隊的設定檔。

在閘道自身的[支出限制](https://code.claude.com/docs/zh-TW/claude-apps-gateway-spend-limits.md#set-a-cap)中，無論工作階段使用哪個 ID，該開發人員在每個期間都只有一個總額和一個上限，預設為其所屬群組上限中的最低值。若要避免某個團隊較低的上限阻礙另一個團隊的工作，請為該開發人員設定個別使用者上限。

## 後續步驟

* [設定參考](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md)：每個 `gateway.yaml` 選項，包括 `managed.policies` 和 `telemetry`
* [部署和操作](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md)：IdP 設定、健康檢查、JWT 機密輪換、升級和安全模型
* [Claude apps gateway 概述](https://code.claude.com/docs/zh-TW/claude-apps-gateway)：快速入門和連接開發人員
* [Claude apps gateway 的 AWS 範例](https://github.com/aws-samples/anthropic-on-aws/tree/main/claude-apps-gateway)：AWS 維護的部署範例，涵蓋一系列客戶環境

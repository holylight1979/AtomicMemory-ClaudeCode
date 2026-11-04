<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/gitlab-ci-cd | lastmod: 2026-09-10 | section: Getting started / Code review and pull requests -->
> 來源：https://code.claude.com/docs/zh-TW/gitlab-ci-cd（官方 zh-TW，lastmod 2026-09-10）｜分類：Getting started › Code review and pull requests｜EN 摘要：Learn about integrating Claude Code into your development workflow with GitLab CI/CD

# Claude Code GitLab CI/CD

> 了解如何將 Claude Code 整合到您的開發工作流程中，使用 GitLab CI/CD

> [!NOTE]
>
> Claude Code for GitLab CI/CD 目前處於測試版。隨著我們改進體驗，功能和功能可能會演變。
>
> 此整合由 GitLab 維護。如需支援，請參閱以下 [GitLab issue](https://gitlab.com/gitlab-org/gitlab/-/issues/573776)。

> [!NOTE]
>
> 此整合建立在 [Claude Code CLI and Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 之上，可在您的 CI/CD 工作和自訂自動化工作流程中以程式設計方式使用 Claude。

## 為什麼要在 GitLab 中使用 Claude Code？

* **即時 MR 建立**：描述您需要的內容，Claude 會提出完整的 MR，包括變更和說明
* **自動化實現**：使用單一命令或提及將問題轉變為可運作的程式碼
* **專案感知**：Claude 遵循您的 `CLAUDE.md` 指南和現有程式碼模式
* **簡單設定**：在 `.gitlab-ci.yml` 中新增一個工作和一個遮罩 CI/CD 變數
* **企業就緒**：選擇 Claude API、Amazon Bedrock 或 Google Cloud 的 Agent Platform 以滿足資料駐留和採購需求
* **預設安全**：在您的 GitLab runners 中執行，具有您的分支保護和核准

## 運作方式

Claude Code 使用 GitLab CI/CD 在隔離的工作中執行 AI 任務，並透過 MR 將結果提交回去：

1. **事件驅動的編排**：GitLab 監聽您選擇的觸發器（例如，在問題、MR 或審查執行緒中提及 `@claude` 的評論）。該工作從執行緒和儲存庫收集上下文，從該輸入建立提示，並執行 Claude Code。

2. **提供者抽象化**：使用適合您環境的提供者：
   * Claude API (SaaS)
   * Amazon Bedrock (基於 IAM 的存取、跨區域選項)
   * Google Cloud 的 Agent Platform (GCP 原生、Workload Identity Federation)

3. **沙箱執行**：每次互動都在具有嚴格網路和檔案系統規則的容器中執行。Claude Code 強制執行工作區範圍的權限以限制寫入。每項變更都透過 MR 流動，以便審查者看到差異並且核准仍然適用。

選擇區域端點以減少延遲並滿足資料主權要求，同時使用現有的雲端協議。

## Claude 可以做什麼？

在 GitLab 管道中，Claude Code 可以：

* 從議題描述或評論建立和更新 MR
* 分析效能迴歸並提出最佳化建議
* 直接在分支中實現功能，然後開啟 MR
* 修復由測試或評論識別的錯誤和迴歸
* 回應後續評論以反覆進行所要求的變更

## 設定

### 快速設定

開始使用的最快方式是在您的 `.gitlab-ci.yml` 中新增一個最小化的工作，並將您的 API 金鑰設定為遮罩變數。

1. **新增遮罩 CI/CD 變數**
   * 前往 **Settings** → **CI/CD** → **Variables**
   * 新增 `ANTHROPIC_API_KEY`（遮罩，視需要保護）

2. **在 `.gitlab-ci.yml` 中新增 Claude 工作**

```yaml theme={null}
stages:
  - ai

claude:
  stage: ai
  image: node:24-alpine3.21
  # 調整規則以符合您想要觸發工作的方式：
  # - 手動執行
  # - 合併請求事件
  # - 當評論包含 '@claude' 時的網頁/API 觸發
  rules:
    - if: '$CI_PIPELINE_SOURCE == "web"'
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
  variables:
    GIT_STRATEGY: fetch
  before_script:
    - apk update
    - apk add --no-cache git curl bash
    - curl -fsSL https://claude.ai/install.sh | bash
    # 安裝程式將 claude 放在 ~/.local/bin，在此映像中不在 PATH 上
    - export PATH="$HOME/.local/bin:$PATH"
  script:
    # 選用：如果您的設定提供 GitLab MCP 伺服器，請啟動它
    - /bin/gitlab-mcp-server || true
    # 透過包含內容承載的網頁/API 觸發時使用 AI_FLOW_* 變數
    - echo "$AI_FLOW_INPUT for $AI_FLOW_CONTEXT on $AI_FLOW_EVENT"
    - >
      claude
      -p "${AI_FLOW_INPUT:-'Review this MR and implement the requested changes'}"
      --permission-mode acceptEdits
      --allowedTools "Bash Read Edit Write mcp__gitlab"
      --debug
```

新增工作和 `ANTHROPIC_API_KEY` 變數後，可以從 **CI/CD** → **Pipelines** 手動執行工作進行測試，或從 MR 觸發它，讓 Claude 在分支中提議更新並在需要時開啟 MR。

> [!NOTE]
>
> 若要在 Amazon Bedrock 或 Google Cloud 的 Agent Platform 上執行而不是使用 Claude API，請參閱下方的[使用 Amazon Bedrock 和 Google Cloud](#using-with-amazon-bedrock-and-google-cloud) 部分，了解驗證和環境設定。

### 手動設定（建議用於生產環境）

如果您偏好更受控的設定或需要企業提供者：

1. **設定提供者存取**：
   * **Claude API**：建立並將 `ANTHROPIC_API_KEY` 儲存為遮罩 CI/CD 變數
   * **Amazon Bedrock**：**設定 GitLab** → **AWS OIDC** 並為 Amazon Bedrock 建立 IAM 角色
   * **Google Cloud 的 Agent Platform**：**為 GitLab 設定工作負載身分識別聯盟** → **GCP**

2. **為 GitLab API 操作新增專案認證**：
   * 預設使用 `CI_JOB_TOKEN`，或建立具有 `api` 範圍的專案存取權杖
   * 如果使用 PAT，將其儲存為 `GITLAB_ACCESS_TOKEN`（遮罩）

3. **在 `.gitlab-ci.yml` 中新增 Claude 工作**：使用 Claude API 的[快速設定](#quick-setup)工作，或來自[設定範例](#configuration-examples)的提供者工作

4. **（選用）啟用提及驅動的觸發**：
   * 為「評論（備註）」新增專案 webhook 至您的事件接聽程式（如果您使用的話）
   * 當評論包含 `@claude` 時，讓接聽程式使用 `AI_FLOW_INPUT` 和 `AI_FLOW_CONTEXT` 等變數呼叫管道觸發 API

## 使用案例範例

### 將議題轉換為 MR

在議題評論中：

```text wrap theme={null}
@claude implement this feature based on the issue description
```

Claude 分析議題和程式碼庫，在分支中寫入變更，並開啟 MR 供審查。

### 取得實作協助

在 MR 討論中：

```text wrap theme={null}
@claude suggest a concrete approach to cache the results of this API call
```

Claude 提出變更建議，新增具有適當快取的程式碼，並更新 MR。

### 快速修復錯誤

在議題或 MR 評論中：

```text wrap theme={null}
@claude fix the TypeError in the user dashboard component
```

Claude 定位錯誤，實作修復，並更新分支或開啟新的 MR。

## 搭配 Amazon Bedrock 和 Google Cloud 使用

針對企業環境，您可以在自己的雲端基礎設施上完全執行 Claude Code，並享有相同的開發者體驗。

> [tab] Amazon Bedrock
>
> ### 先決條件
>
> 在使用 Amazon Bedrock 設定 Claude Code 之前，您需要：
>
> 1. 一個 AWS 帳戶，具有 Amazon Bedrock 對所需 Claude 模型的存取權限
> 2. 在 AWS IAM 中將 GitLab 設定為 OIDC 身分提供者
> 3. 一個具有 Amazon Bedrock 權限的 IAM 角色，以及限制於您的 GitLab 專案/參考的信任政策
> 4. 用於角色假設的 GitLab CI/CD 變數：
>    * `AWS_ROLE_TO_ASSUME`（角色 ARN）
>    * `AWS_REGION`（Amazon Bedrock 區域）
>
> ### 設定說明
>
> 設定 AWS 以允許 GitLab CI 工作透過 OIDC 假設 IAM 角色（無靜態金鑰）。
>
> **必要設定：**
>
> 1. 啟用 Amazon Bedrock 並要求存取您的目標 Claude 模型
> 2. 如果尚未存在，請為 GitLab 建立 IAM OIDC 提供者
> 3. 建立由 GitLab OIDC 提供者信任的 IAM 角色，限制於您的專案和受保護的參考
> 4. 為 Amazon Bedrock 叫用 API 附加最小權限
>
> 使用 [Amazon Bedrock 工作範例](#configuration-examples)在執行時交換工作的 OIDC 令牌以取得暫時 AWS 認證。

> [tab] Google Cloud's Agent Platform
>
> ### 先決條件
>
> 在使用 Google Cloud's Agent Platform 設定 Claude Code 之前，您需要：
>
> 1. 一個 Google Cloud 專案，具有：
>    * 已啟用 Google Cloud's Agent Platform API
>    * 已設定工作負載身分聯盟以信任 GitLab OIDC
> 2. 一個專用服務帳戶，僅具有所需的 Google Cloud's Agent Platform 角色
> 3. GitLab CI/CD 變數：
>    * `GCP_WORKLOAD_IDENTITY_PROVIDER`（提供者資源名稱，不含 `//iam.googleapis.com/` 前綴，例如 `projects/123456789/locations/global/workloadIdentityPools/my-pool/providers/my-provider`）
>    * `GCP_SERVICE_ACCOUNT`（服務帳戶電子郵件）
>    * `GCP_PROJECT_ID`（Google Cloud 專案 ID）
>
> ### 設定說明
>
> 設定 Google Cloud 以允許 GitLab CI 工作透過工作負載身分聯盟模擬服務帳戶。
>
> **必要設定：**
>
> 1. 啟用 IAM 認證 API、STS API 和 Google Cloud's Agent Platform API
> 2. 為 GitLab OIDC 建立工作負載身分池和提供者
> 3. 建立具有 Google Cloud's Agent Platform 角色的專用服務帳戶
> 4. 授予 WIF 主體權限以模擬服務帳戶
>
> 使用 [Agent Platform 工作範例](#configuration-examples)進行驗證，無需儲存金鑰。

## 設定範例

以下是您可以調整以適應您的管道的現成程式碼片段。

### Amazon Bedrock 工作範例 (OIDC)

**先決條件：**

* Amazon Bedrock 已啟用，可存取您選擇的 Claude 模型
* GitLab OIDC 已在 AWS 中設定，具有信任您的 GitLab 專案和 refs 的角色
* 具有 Amazon Bedrock 權限的 IAM 角色（建議最小權限）

**必需的 CI/CD 變數：**

* `AWS_ROLE_TO_ASSUME`：用於 Amazon Bedrock 存取的 IAM 角色 ARN
* `AWS_REGION`：Amazon Bedrock 區域（例如 `us-west-2`）

GitLab 從 `id_tokens:` 區塊鑄造工作的 OIDC 令牌，並將其公開為 `GITLAB_OIDC_TOKEN`。將 `aud` 設定為您在 AWS 的 IAM OIDC 身分提供者上設定的對象值，例如您的 GitLab 執行個體 URL。

```yaml theme={null}
stages:
  - ai

claude-bedrock:
  stage: ai
  image: node:24-alpine3.21
  rules:
    - if: '$CI_PIPELINE_SOURCE == "web"'
  id_tokens:
    GITLAB_OIDC_TOKEN:
      aud: https://gitlab.example.com
  before_script:
    - apk add --no-cache bash curl jq git aws-cli
    - curl -fsSL https://claude.ai/install.sh | bash
    # The installer places claude in ~/.local/bin, which isn't on PATH in this image
    - export PATH="$HOME/.local/bin:$PATH"
    # Exchange the job's OIDC token for AWS credentials
    - export AWS_WEB_IDENTITY_TOKEN_FILE="/tmp/oidc_token"
    - printf "%s" "$GITLAB_OIDC_TOKEN" > "$AWS_WEB_IDENTITY_TOKEN_FILE"
    - >
      aws sts assume-role-with-web-identity
      --role-arn "$AWS_ROLE_TO_ASSUME"
      --role-session-name "gitlab-claude-$(date +%s)"
      --web-identity-token "file://$AWS_WEB_IDENTITY_TOKEN_FILE"
      --duration-seconds 3600 > /tmp/aws_creds.json
    - export AWS_ACCESS_KEY_ID="$(jq -r .Credentials.AccessKeyId /tmp/aws_creds.json)"
    - export AWS_SECRET_ACCESS_KEY="$(jq -r .Credentials.SecretAccessKey /tmp/aws_creds.json)"
    - export AWS_SESSION_TOKEN="$(jq -r .Credentials.SessionToken /tmp/aws_creds.json)"
  script:
    - /bin/gitlab-mcp-server || true
    - >
      claude
      -p "${AI_FLOW_INPUT:-'Implement the requested changes and open an MR'}"
      --permission-mode acceptEdits
      --allowedTools "Bash Read Edit Write mcp__gitlab"
      --debug
  variables:
    AWS_REGION: "us-west-2"
    CLAUDE_CODE_USE_BEDROCK: "1"
```

> [!NOTE]
>
> Amazon Bedrock 的模型 ID 包含區域特定的前綴（例如 `us.anthropic.claude-sonnet-4-6`）。如果您的工作流程支援，請透過您的工作設定或提示傳遞所需的模型。

### Agent Platform 工作範例（工作負載身分聯盟）

**先決條件：**

* Google Cloud 的 Agent Platform API 已在您的 GCP 專案中啟用
* 工作負載身分聯盟已設定為信任 GitLab OIDC
* 具有 Google Cloud Agent Platform 權限的服務帳戶

**必需的 CI/CD 變數：**

* `GCP_WORKLOAD_IDENTITY_PROVIDER`：提供者資源名稱，不含 `//iam.googleapis.com/` 前綴，例如 `projects/123456789/locations/global/workloadIdentityPools/my-pool/providers/my-provider`
* `GCP_SERVICE_ACCOUNT`：服務帳戶電子郵件
* `GCP_PROJECT_ID`：Google Cloud 專案 ID
* `CLOUD_ML_REGION`：Google Cloud Agent Platform 區域（例如 `us-east5`）

GitLab 從 `id_tokens:` 區塊鑄造工作的 OIDC 令牌，並將其公開為 `GITLAB_OIDC_TOKEN`。將 `aud` 設定為您在工作負載身分池提供者上設定的對象值，例如您的 GitLab 執行個體 URL。工作將令牌寫入檔案，認證設定的 `credential_source` 項目告訴 Google 的驗證程式庫從該處讀取它。將 `GOOGLE_APPLICATION_CREDENTIALS` 設定為認證設定檔案使其可透過[應用程式預設認證](https://code.claude.com/docs/zh-TW/google-vertex-ai.md#3-configure-gcp-credentials)供 Claude Code 使用。

```yaml theme={null}
stages:
  - ai

claude-vertex:
  stage: ai
  image: gcr.io/google.com/cloudsdktool/google-cloud-cli:slim
  rules:
    - if: '$CI_PIPELINE_SOURCE == "web"'
  id_tokens:
    GITLAB_OIDC_TOKEN:
      aud: https://gitlab.example.com
  before_script:
    - apt-get update && apt-get install -y git && apt-get clean
    - curl -fsSL https://claude.ai/install.sh | bash
    # The installer places claude in ~/.local/bin, which isn't on PATH in this image
    - export PATH="$HOME/.local/bin:$PATH"
    # Write the job's OIDC token where credential_source expects it
    - printf "%s" "$GITLAB_OIDC_TOKEN" > /tmp/oidc_token
    # Write the WIF credential configuration to a file (no downloaded keys)
    - |
      cat > /tmp/cred.json <<EOF
      {
        "type": "external_account",
        "audience": "//iam.googleapis.com/${GCP_WORKLOAD_IDENTITY_PROVIDER}",
        "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
        "token_url": "https://sts.googleapis.com/v1/token",
        "credential_source": {
          "file": "/tmp/oidc_token"
        },
        "service_account_impersonation_url": "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/${GCP_SERVICE_ACCOUNT}:generateAccessToken"
      }
      EOF
    # Expose the credentials to Claude Code via Application Default Credentials
    - export GOOGLE_APPLICATION_CREDENTIALS=/tmp/cred.json
    # Authenticate the gcloud CLI with the same credential configuration
    - gcloud auth login --cred-file=/tmp/cred.json
    - gcloud config set project "$GCP_PROJECT_ID"
  script:
    - /bin/gitlab-mcp-server || true
    - >
      CLOUD_ML_REGION="${CLOUD_ML_REGION:-us-east5}"
      claude
      -p "${AI_FLOW_INPUT:-'Review and update code as requested'}"
      --permission-mode acceptEdits
      --allowedTools "Bash Read Edit Write mcp__gitlab"
      --debug
  variables:
    CLOUD_ML_REGION: "us-east5"
    CLAUDE_CODE_USE_VERTEX: "1"
    ANTHROPIC_VERTEX_PROJECT_ID: "$GCP_PROJECT_ID"
```

> [!NOTE]
>
> 使用工作負載身分聯盟，您不需要儲存服務帳戶金鑰。使用存放庫特定的信任條件和最小權限服務帳戶。

## 最佳實踐

### CLAUDE.md 設定

在儲存庫根目錄建立 `CLAUDE.md` 檔案，以定義編碼標準、審查條件和專案特定規則。Claude 在執行期間會讀取此檔案，並在提出變更時遵循您的慣例。

### 安全考量

**絕不將 API 金鑰或雲端認證提交到您的儲存庫**。請務必使用 GitLab CI/CD 變數：

* 將 `ANTHROPIC_API_KEY` 新增為遮罩變數（如需要可保護它）
* 盡可能使用提供者特定的 OIDC（無長期金鑰）
* 限制工作權限和網路出口
* 像審查任何其他貢獻者一樣審查 Claude 的 MR

### 最佳化效能

* 保持 `CLAUDE.md` 專注且簡潔
* 提供清晰的議題/MR 描述以減少迭代
* 在執行器中盡可能快取 npm 和套件安裝

### CI 成本

使用 Claude Code 搭配 GitLab CI/CD 時，請注意相關成本：

* **GitLab Runner 時間**：
  * Claude 在您的 GitLab 執行器上執行，並消耗計算分鐘數
  * 請參閱您的 GitLab 方案的執行器計費詳細資訊

* **API 成本**：
  * 每次 Claude 互動根據提示和回應大小消耗權杖
  * 權杖使用量因任務複雜性和程式碼庫大小而異
  * 詳細資訊請參閱 [Anthropic 定價](https://platform.claude.com/docs/en/about-claude/pricing)

* **成本最佳化提示**：
  * 使用特定的 `@claude` 命令以減少不必要的回合
  * 設定適當的 `--max-turns` 和工作 `timeout` 值
  * 限制並行以控制平行執行

## 疑難排解

### Claude 未回應 @claude 指令

* 驗證您的管道是否被觸發（手動、MR 事件或透過筆記事件監聽器/webhook）
* 確保您的 `ANTHROPIC_API_KEY` 或雲端提供者變數存在
* 檢查評論是否包含 `@claude`（不是 `/claude`），以及您的提及觸發器是否已設定

### 工作無法寫入評論或開啟 MR

* 確保 `CI_JOB_TOKEN` 對專案具有足夠的權限，或使用具有 `api` 範圍的專案存取令牌
* 檢查 `mcp__gitlab` 工具是否在 `--allowedTools` 中啟用
* 確認工作在 MR 的上下文中執行，或透過 `AI_FLOW_*` 變數有足夠的上下文

### 驗證錯誤

* **針對 Claude API**：確認 `ANTHROPIC_API_KEY` 有效且未過期
* **針對 Amazon Bedrock 或 Google Cloud 的 Agent Platform**：驗證 OIDC/WIF 設定、角色模擬和密碼名稱；確認區域和模型可用性

## 進階設定

### 常見參數和變數

使用這些 CLI 旗標、GitLab 關鍵字和變數來控制您工作中的 Claude Code 執行：

* `-p`：提供內聯指示，例如 `claude -p "Review this MR"`
* `--max-turns`：限制往返迭代的次數
* `timeout`：使用 GitLab 的工作層級 `timeout` 關鍵字限制總工作執行時間，例如 `timeout: 30m`
* `ANTHROPIC_API_KEY`：Claude API 所需（不用於 Amazon Bedrock 或 Google Cloud 的 Agent Platform）
* 提供者特定環境：`AWS_REGION`、Google Cloud 的 Agent Platform 的專案/區域變數

> [!NOTE]
>
> 確切的旗標和參數可能因 `@anthropic-ai/claude-code` 的版本而異。在您的工作中執行 `claude --help` 以查看支援的選項。

### 自訂 Claude 的行為

您可以透過兩種主要方式引導 Claude：

1. **CLAUDE.md**：定義編碼標準、安全性需求和專案慣例。Claude 在執行期間讀取此檔案並遵循您的規則。
2. **自訂提示**：透過工作中的 `-p` 傳遞特定任務的指示。為不同的工作使用不同的提示（例如，審查、實作、重構）。

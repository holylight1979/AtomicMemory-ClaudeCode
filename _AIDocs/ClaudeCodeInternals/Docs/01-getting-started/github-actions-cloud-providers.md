<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/github-actions-cloud-providers | lastmod: 2026-09-17 | section: Getting started / Code review and pull requests -->
> 來源：https://code.claude.com/docs/zh-TW/github-actions-cloud-providers（官方 zh-TW，lastmod 2026-09-17）｜分類：Getting started › Code review and pull requests｜EN 摘要：Run Claude Code GitHub Actions through Amazon Bedrock, Google Cloud's Agent Platform, or Microsoft Foundry instead of the Claude API

# 使用 Claude Code GitHub Actions 搭配雲端提供者

> 透過 Amazon Bedrock、Google Cloud 的 Agent Platform 或 Microsoft Foundry 執行 Claude Code GitHub Actions，而不是使用 Claude API

[Claude Code GitHub Actions](https://code.claude.com/docs/zh-TW/github-actions.md) 預設會呼叫 Claude API。若要改為透過您自己的雲端帳戶路由推論，請設定 Claude Code GitHub Action 的 provider 輸入，並設定您的雲端以信任工作流程的 OpenID Connect (OIDC) 權杖。工作流程會使用該權杖進行驗證，因此您無需在儲存庫中儲存長期的雲端認證。

> [!NOTE]
>
> 本頁面以 [GitHub Actions 設定](https://code.claude.com/docs/zh-TW/github-actions.md#setup) 為基礎。它假設您已經熟悉工作流程檔案和 `anthropics/claude-code-action` 步驟，僅涵蓋雲端提供者所變更的部分。

## 選擇您的提供者

Claude Code GitHub Action 支援三個提供者，以下設定步驟僅在雲端側設定上有所不同。請使用您的組織已經擁有 Claude 模型存取權的提供者。您可以在 `anthropics/claude-code-action` 步驟的 `with:` 區塊中使用一個輸入來告訴 Claude Code GitHub Action 要使用哪個提供者：

* **Amazon Bedrock**：`use_bedrock: "true"`
* **Google Cloud 的 Agent Platform**：`use_vertex: "true"`
* **Microsoft Foundry**：`use_foundry: "true"`

[設定整合](#set-up-the-integration) 下的完整工作流程範例已經包含了每個提供者的輸入。

## 先決條件

在開始之前，您需要：

* 對執行 Claude Code GitHub Action 的儲存庫的管理員存取權，以安裝 GitHub App 並新增密鑰
* 在您的雲端帳戶中建立身分識別資源的權限：AWS 上的 IAM 角色和 OIDC 身分識別提供者、Google Cloud 上的 Workload Identity Federation 資源和服務帳戶，或 Azure 上的 Microsoft Entra 應用程式
* 在您的提供者上擁有 Claude 模型存取權：
  * **Amazon Bedrock**：已授予 Claude 模型的存取權。跨區域推論設定檔（例如本頁面範例中的 `us.` 模型 ID）需要在其區域群組的每個區域中授予存取權。請參閱 [Amazon Bedrock 上的 Claude Code](https://code.claude.com/docs/zh-TW/amazon-bedrock.md)
  * **Google Cloud 的 Agent Platform**：已啟用 Agent Platform API 的專案以及對 Claude 模型的存取權。請參閱 [Google Cloud 的 Agent Platform 上的 Claude Code](https://code.claude.com/docs/zh-TW/google-vertex-ai.md)
  * **Microsoft Foundry**：具有 Claude 模型部署的 Foundry 資源。請參閱 [Microsoft Foundry 上的 Claude Code](https://code.claude.com/docs/zh-TW/microsoft-foundry.md)

## 設定整合

除了先決條件外，您需要建立四項內容：Claude Code GitHub Action 的 GitHub 身分識別、雲端側信任設定、儲存庫密鑰和工作流程檔案。以下步驟將逐一說明每一項。

**1. 選擇 GitHub 身分識別**

Claude Code GitHub Action 透過 GitHub 身分識別推送提交並發佈評論。[快速設定](https://code.claude.com/docs/zh-TW/github-actions.md#quick-setup) 會為此安裝官方 Claude GitHub App。使用雲端提供者時，您可以自己選擇身分識別：

* **官方 [Claude GitHub App](https://github.com/apps/claude)**：在儲存庫上安裝它，或如果已經安裝，請跳到下一步
* **自訂 GitHub App**：當您只想要 Claude Code GitHub Action 使用的三個權限，而不是[官方應用程式的完整集合](https://code.claude.com/docs/zh-TW/github-actions.md#github-app-permissions)時，建立您自己的應用程式
* **GitHub 的自動 `GITHUB_TOKEN`**：無需建立或安裝應用程式，但 GitHub 不會在使用它進行的提交上觸發您的 CI 工作流程

第四步中的工作流程範例使用自訂應用程式進行驗證。該步驟也說明了其他兩個選項要變更的內容。

若要建立自訂應用程式，請[註冊新的 GitHub App](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app)，並停用 Webhook，因為此整合不使用它們。授予它三個儲存庫權限：

* **Contents**：讀取和寫入
* **Issues**：讀取和寫入
* **Pull requests**：讀取和寫入

註冊應用程式後，產生私密金鑰並保留下載的 `.pem` 檔案，從應用程式的設定頁面記下應用程式 ID，並在執行 Claude Code GitHub Action 的儲存庫上[安裝應用程式](https://docs.github.com/en/apps/using-github-apps/installing-your-own-github-app)。您將在第三步中將金鑰和 ID 新增為密鑰。

**2. 設定雲端驗證**

設定您的雲端以信任 GitHub 向工作流程發出的 OIDC 權杖，以便每次工作流程執行都能獲得短期的雲端認證。每個標籤中的項目符號總結了要建立的內容，每個標籤都連結到雲端廠商自己的主控台級步驟指南。

> [tab] Amazon Bedrock
>
> 按照 [AWS 建立 OIDC 身分識別提供者指南](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html)，在您的 AWS 帳戶中建立信任設定：
>
> * 新增 GitHub OIDC 身分識別提供者，提供者 URL 為 `https://token.actions.githubusercontent.com`，對象為 `sts.amazonaws.com`
> * 建立由該提供者信任的 IAM 角色作為網路身分識別，並附加來自 [IAM 設定](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#iam-configuration) 的範圍調用原則，該原則授予 `bedrock:InvokeModel`、`bedrock:InvokeModelWithResponseStream`、`bedrock:ListInferenceProfiles` 和 `bedrock:GetInferenceProfile`，以及兩個 `aws-marketplace` 訂閱動作
> * 使用主體條件（例如 `repo:your-org/your-repo:*`）將角色的信任原則限制在您的儲存庫。請參閱 [GitHub 的 OIDC 強化指南](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)以了解聲明格式
>
> 記下角色的 ARN。您將在下一步中將其新增為密鑰。

> [tab] Google Cloud 的 Agent Platform
>
> 按照 [Workload Identity Federation 文件](https://cloud.google.com/iam/docs/workload-identity-federation)，在您的 Google Cloud 專案中建立聯盟資源：
>
> * 啟用三個 API：IAM Credentials、Security Token Service (STS) 和 Agent Platform API，其服務名稱為 `aiplatform.googleapis.com`
> * 建立 Workload Identity Pool，其中包含 GitHub OIDC 提供者，其簽發者為 `https://token.actions.githubusercontent.com`，並新增將池限制在您的儲存庫的屬性條件
> * 建立專用服務帳戶，僅具有 `Vertex AI User` 角色（即 `roles/aiplatform.user`），並允許池模擬它
>
> 記下提供者的完整資源名稱和服務帳戶的電子郵件地址。您將在下一步中將它們新增為密鑰。

> [tab] Microsoft Foundry
>
> 按照 [Microsoft 從 GitHub Actions 驗證指南](https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure-openid-connect)，建立具有儲存庫聯盟認證的 Microsoft Entra 應用程式：
>
> * 註冊 Microsoft Entra 應用程式並新增聯盟身分識別認證，該認證信任 GitHub 向您的儲存庫發出的權杖。使用者指派的受管身分識別可以代替應用程式。兩者都有您在下面記下的用戶端 ID
> * 在您的 Foundry 資源上為應用程式指派 `Azure AI User` 角色。請參閱 [Azure RBAC 設定](https://code.claude.com/docs/zh-TW/microsoft-foundry.md#azure-rbac-configuration)以了解更窄的自訂角色
>
> 記下應用程式的用戶端 ID、您的租用戶 ID 和您的訂閱 ID。您將在下一步中將它們新增為密鑰。

**3. 新增儲存庫密鑰**

在執行 Claude Code GitHub Action 的儲存庫中，為您的提供者新增密鑰，如果您在第一步中建立了自訂 GitHub App，還要新增兩個應用程式密鑰。請參閱 GitHub 的 [在 GitHub Actions 中使用密鑰](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions)指南。

| 密鑰 | 需要用於 | 值 |
| - | - | - |
| `AWS_ROLE_TO_ASSUME` | Amazon Bedrock | IAM 角色的 ARN |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | Google Cloud 的 Agent Platform | 提供者的完整資源名稱 |
| `GCP_SERVICE_ACCOUNT` | Google Cloud 的 Agent Platform | 服務帳戶的電子郵件地址 |
| `AZURE_CLIENT_ID` | Microsoft Foundry | Entra 應用程式的用戶端 ID |
| `AZURE_TENANT_ID` | Microsoft Foundry | 您的 Microsoft Entra 租用戶 ID |
| `AZURE_SUBSCRIPTION_ID` | Microsoft Foundry | 您的 Azure 訂閱 ID |
| `APP_ID` | 自訂 GitHub App | GitHub App 的 ID |
| `APP_PRIVATE_KEY` | 自訂 GitHub App | `.pem` 私密金鑰檔案的內容 |

**4. 建立工作流程檔案**

為您的提供者建立工作流程檔案，例如 `.github/workflows/claude.yml`。每個範例都會回應 `@claude` 提及，使用自訂應用程式向 GitHub 進行驗證，並包含 `id-token: write` 權限，GitHub 需要此權限來發出 OIDC 權杖，您的雲端提供者可以將其交換為認證。

如果您在第一步中選擇了不同的 GitHub 身分識別，請調整範例：

* **官方 Claude GitHub App**：刪除「產生 GitHub App 權杖」步驟和 `github_token` 行
* **GitHub 的自動權杖**：刪除權杖產生步驟，並將 `github_token` 行變更為 `github_token: ${{ secrets.GITHUB_TOKEN }}`

> [!WARNING]
>
> 在公開儲存庫上，任何使用者的包含觸發短語的評論都會啟動此工作流程。認證步驟在 Claude Code GitHub Action 檢查評論者的寫入存取權之前執行，因此該動作僅在工作流程產生應用程式權杖並登入您的雲端提供者後才拒絕未授權的使用者，這會留下稽核日誌項目並消耗 Actions 分鐘數。為了避免這些執行，請新增一個步驟，在認證步驟之前驗證評論者的寫入存取權。

> [tab] Amazon Bedrock
>
> 將 `aws-region` 值替換為您自己的值。認證步驟會將其匯出為 `AWS_REGION`，供工作的其餘部分使用。
>
> ```yaml theme={null}
> name: Claude PR Action
>
> permissions:
>   contents: write
>   pull-requests: write
>   issues: write
>   id-token: write
>
> on:
>   issue_comment:
>     types: [created]
>   pull_request_review_comment:
>     types: [created]
>   issues:
>     types: [opened]
>
> jobs:
>   claude-pr:
>     if: |
>       (github.event_name == 'issue_comment' && contains(github.event.comment.body, '@claude')) ||
>       (github.event_name == 'pull_request_review_comment' && contains(github.event.comment.body, '@claude')) ||
>       (github.event_name == 'issues' && (contains(github.event.issue.body, '@claude') || contains(github.event.issue.title, '@claude')))
>     runs-on: ubuntu-latest
>     steps:
>       - name: Checkout repository
>         uses: actions/checkout@v6
>
>       - name: Generate GitHub App token
>         id: app-token
>         uses: actions/create-github-app-token@v2
>         with:
>           app-id: ${{ secrets.APP_ID }}
>           private-key: ${{ secrets.APP_PRIVATE_KEY }}
>
>       - name: Configure AWS Credentials (OIDC)
>         uses: aws-actions/configure-aws-credentials@v4
>         with:
>           role-to-assume: ${{ secrets.AWS_ROLE_TO_ASSUME }}
>           aws-region: us-west-2
>
>       - uses: anthropics/claude-code-action@v1
>         with:
>           github_token: ${{ steps.app-token.outputs.token }}
>           use_bedrock: "true"
>           claude_args: '--model us.anthropic.claude-sonnet-4-6'
> ```
>
> > [!TIP]
> >
> > Bedrock 模型 ID 包含跨區域推論設定檔前綴，例如 `us.`。使用您授予模型存取權的區域群組的前綴。

> [tab] Google Cloud 的 Agent Platform
>
> 將 `CLOUD_ML_REGION` 值替換為您自己的值。您無需硬編碼專案 ID，因為工作流程會從 `auth` 步驟的輸出中讀取它。
>
> ```yaml theme={null}
> name: Claude PR Action
>
> permissions:
>   contents: write
>   pull-requests: write
>   issues: write
>   id-token: write
>
> on:
>   issue_comment:
>     types: [created]
>   pull_request_review_comment:
>     types: [created]
>   issues:
>     types: [opened]
>
> jobs:
>   claude-pr:
>     if: |
>       (github.event_name == 'issue_comment' && contains(github.event.comment.body, '@claude')) ||
>       (github.event_name == 'pull_request_review_comment' && contains(github.event.comment.body, '@claude')) ||
>       (github.event_name == 'issues' && (contains(github.event.issue.body, '@claude') || contains(github.event.issue.title, '@claude')))
>     runs-on: ubuntu-latest
>     steps:
>       - name: Checkout repository
>         uses: actions/checkout@v6
>
>       - name: Generate GitHub App token
>         id: app-token
>         uses: actions/create-github-app-token@v2
>         with:
>           app-id: ${{ secrets.APP_ID }}
>           private-key: ${{ secrets.APP_PRIVATE_KEY }}
>
>       - name: Authenticate to Google Cloud
>         id: auth
>         uses: google-github-actions/auth@v2
>         with:
>           workload_identity_provider: ${{ secrets.GCP_WORKLOAD_IDENTITY_PROVIDER }}
>           service_account: ${{ secrets.GCP_SERVICE_ACCOUNT }}
>
>       - uses: anthropics/claude-code-action@v1
>         with:
>           github_token: ${{ steps.app-token.outputs.token }}
>           use_vertex: "true"
>           claude_args: '--model claude-sonnet-5'
>         env:
>           ANTHROPIC_VERTEX_PROJECT_ID: ${{ steps.auth.outputs.project_id }}
>           CLOUD_ML_REGION: us-east5
> ```

> [tab] Microsoft Foundry
>
> 將 `your-resource-name` 替換為您的 Foundry 資源名稱。Claude Code 會從中建立端點 URL。`azure/login` 步驟使用工作流程的 OIDC 權杖登入，Claude Code 透過 Azure [預設認證鏈](https://learn.microsoft.com/en-us/azure/developer/javascript/sdk/authentication/credential-chains#defaultazurecredential-overview)取得認證。
>
> ```yaml theme={null}
> name: Claude PR Action
>
> permissions:
>   contents: write
>   pull-requests: write
>   issues: write
>   id-token: write
>
> on:
>   issue_comment:
>     types: [created]
>   pull_request_review_comment:
>     types: [created]
>   issues:
>     types: [opened]
>
> jobs:
>   claude-pr:
>     if: |
>       (github.event_name == 'issue_comment' && contains(github.event.comment.body, '@claude')) ||
>       (github.event_name == 'pull_request_review_comment' && contains(github.event.comment.body, '@claude')) ||
>       (github.event_name == 'issues' && (contains(github.event.issue.body, '@claude') || contains(github.event.issue.title, '@claude')))
>     runs-on: ubuntu-latest
>     steps:
>       - name: Checkout repository
>         uses: actions/checkout@v6
>
>       - name: Generate GitHub App token
>         id: app-token
>         uses: actions/create-github-app-token@v2
>         with:
>           app-id: ${{ secrets.APP_ID }}
>           private-key: ${{ secrets.APP_PRIVATE_KEY }}
>
>       - name: Authenticate to Azure
>         uses: azure/login@v2
>         with:
>           client-id: ${{ secrets.AZURE_CLIENT_ID }}
>           tenant-id: ${{ secrets.AZURE_TENANT_ID }}
>           subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
>
>       - uses: anthropics/claude-code-action@v1
>         with:
>           github_token: ${{ steps.app-token.outputs.token }}
>           use_foundry: "true"
>           claude_args: '--model claude-sonnet-5'
>         env:
>           ANTHROPIC_FOUNDRY_RESOURCE: your-resource-name
> ```
>
> > [!TIP]
> >
> > 使用與您的 Foundry 資源中 Claude 部署相符的模型 ID。請參閱 [Microsoft Foundry 上的 Claude Code](https://code.claude.com/docs/zh-TW/microsoft-foundry.md)，了解模型設定和版本固定。

使用任何提供者，您可以透過將 `--max-turns` 新增到 `claude_args` 來限制執行長度和成本。請參閱[管理成本](https://code.claude.com/docs/zh-TW/github-actions.md#manage-costs)。

**5. 測試設定**

在問題或 PR 評論中提及 `@claude`，然後在儲存庫的 Actions 標籤中觀看執行。Claude 會在同一問題或 PR 上的評論中回覆。

## 疑難排解

失敗的執行通常會在以下兩個地方之一中斷：

* **驗證錯誤**：通常是 OIDC 設定錯誤。檢查工作流程是否包含 `id-token: write` 權限、信任設定的儲存庫條件是否與您的儲存庫完全相符，以及工作流程中的密鑰名稱是否與您新增的名稱相符
* **觸發和 CI 問題**：這些的行為與 Claude Code GitHub Action 呼叫 Claude API 時相同。請參閱主頁的[疑難排解部分](https://code.claude.com/docs/zh-TW/github-actions.md#troubleshooting)和 Claude Code GitHub Action 的 [FAQ](https://github.com/anthropics/claude-code-action/blob/main/docs/faq.md)

## 接下來

* [Claude Code GitHub Actions](https://code.claude.com/docs/zh-TW/github-actions.md)，了解範例、參數和最佳實踐
* [Amazon Bedrock 上的 Claude Code](https://code.claude.com/docs/zh-TW/amazon-bedrock.md)，了解 Bedrock 模型 ID 和區域
* [Google Cloud 的 Agent Platform 上的 Claude Code](https://code.claude.com/docs/zh-TW/google-vertex-ai.md)，了解 Agent Platform 模型 ID 和區域
* [Microsoft Foundry 上的 Claude Code](https://code.claude.com/docs/zh-TW/microsoft-foundry.md)，了解 Foundry 模型和端點設定

<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/claude-platform-on-aws | lastmod: 2026-10-28 | section: Administration / Deployment -->
> 來源：https://code.claude.com/docs/zh-TW/claude-platform-on-aws（官方 zh-TW，lastmod 2026-10-28）｜分類：Administration › Deployment｜EN 摘要：Configure Claude Code to use the Anthropic-operated Claude API with AWS authentication, IAM access control, and AWS Marketplace billing.

# AWS 上的 Claude Platform 上的 Claude Code

> 設定 Claude Code 以使用 Anthropic 營運的 Claude API，搭配 AWS 驗證、IAM 存取控制和 AWS Marketplace 計費。

AWS 上的 Claude Platform 是 Anthropic 營運的 Claude API，具有 AWS 驗證、IAM 存取控制和 AWS Marketplace 計費。請求直接到達 Anthropic 的 API，因此您可以獲得與 [Claude API](https://platform.claude.com/docs) 相同的模型和 API 功能，並遵循相同的發佈時程表。您使用 AWS 認證或工作區 API 金鑰進行驗證，並透過 AWS Marketplace 付款。

Claude Code 透過 Anthropic 的功能旗標服務啟用的用戶端功能預設為關閉，且 [advisor 工具](https://code.claude.com/docs/zh-TW/advisor.md) 無法使用。請參閱 [功能可用性矩陣](https://code.claude.com/docs/zh-TW/feature-availability.md#summary-by-provider) 以取得完整清單。

使用本指南將 Claude Code 指向您已透過 AWS 上的 Claude Platform 佈建的工作區。有關在此之前的 AWS 訂閱和工作區設定，請參閱 [AWS 上的 Claude Platform 文件](https://platform.claude.com/docs/en/build-with-claude/claude-platform-on-aws)。

> [!NOTE]
>
> 透過 AWS Marketplace 訂閱會佈建一個與您的 AWS 帳戶相關聯的新 Anthropic 組織。此組織與您已有的任何 Anthropic 組織分開，認證不會在它們之間轉移。使用來自 AWS 連結組織的工作區 ID 和 API 金鑰，而不是來自預先存在的 Claude Console 帳戶。

## 先決條件

在設定 Claude Code 之前，您需要：

* 透過 AWS Marketplace 的有效 AWS 上的 Claude Platform 訂閱
* 您的 AWS 連結 Anthropic 組織中的工作區，及其工作區 ID
* 具有叫用 Anthropic 服務權限的 IAM 主體，或限定於工作區的 API 金鑰
* 您環境中的 AWS 認證、`~/.aws/credentials` 中的認證，或來自附加 IAM 角色的認證（如果您想要 SigV4 驗證）。AWS CLI 僅在 SSO 登入流程中需要。

## 設定

### 設定 AWS 憑證

Claude Code 支援兩種用於 Claude Platform on AWS 的身分驗證方式。請選擇符合團隊存取管理方式的方法：

* [使用 SigV4 的 AWS 憑證](#use-aws-credentials-with-sigv4)：以 IAM 主體進行身分驗證，憑證來自標準 AWS 憑證鏈
* [工作區 API 金鑰](#use-a-workspace-api-key)：使用您在 AWS Console 中產生的長期金鑰進行身分驗證

#### 使用 SigV4 的 AWS 憑證

Claude Code 使用標準 AWS 憑證鏈以 SigV4 簽署請求：環境變數、`~/.aws/credentials` 中的共用憑證、IAM 角色、AWS SSO 工作階段，以及 AWS SDK 支援的任何其他來源。

在本機使用時，請在啟動 Claude Code 之前使用 AWS CLI 登入。以下範例使用 SSO 設定檔，但任何能在標準位置產生憑證的方法皆可使用。

```bash theme={null}
aws sso login --profile my-profile
export AWS_PROFILE=my-profile
```

針對 CI 與自動化，請為執行器提供具有呼叫 Anthropic 服務權限的 IAM 角色，並設定 `AWS_REGION`。憑證鏈會自動取得該角色。

如果您的 SSO 憑證在工作階段中途過期，請設定 [`awsAuthRefresh`](https://code.claude.com/docs/zh-TW/amazon-bedrock#advanced-credential-configuration)，讓 Claude Code 重新執行您的登入命令並重試，而不是直接失敗。將該命令新增至您的[設定檔](https://code.claude.com/docs/zh-TW/settings.md)，例如 `~/.claude/settings.json`：

```json theme={null}
{
  "awsAuthRefresh": "aws sso login --profile my-profile"
}
```

當 Claude Code 無法驗證您現有的 AWS 憑證時，也會在啟動時執行此命令，並在 `Authentication` 面板中顯示該命令的輸出，直到登入完成為止。

設定 `awsAuthRefresh` 後，執行 `/login`，選取 **3rd-party platform**，然後在 **Using 3rd-party platforms** 下選取 **Claude Platform on AWS · refresh credentials**。Claude Code 會執行所設定的命令，並在不需重新啟動的情況下重新讀取您的 AWS 憑證。

#### 使用工作區 API 金鑰

工作區 API 金鑰是一種長期有效的密鑰，適用於您不想管理聯合 AWS 憑證的情況。請在 AWS Console 的 **Claude Platform on AWS → API keys** 下產生金鑰，並將其設定為 `ANTHROPIC_AWS_API_KEY`：

```bash theme={null}
export ANTHROPIC_AWS_API_KEY=sk-ant-xxxxx
```

金鑰會以 `x-api-key` 傳送，且優先於 SigV4，因此您環境中的任何 AWS 憑證都會被忽略。來自另一個 Claude Console 組織的 API 金鑰在此無法使用。

請像對待任何其他正式環境憑證一樣對待工作區 API 金鑰。[使用者設定檔](https://code.claude.com/docs/zh-TW/settings.md)中的 `env` 區塊是將金鑰範圍限定於您的電腦、而不必全域匯出的便利方式。

> [!NOTE]
>
> `/login` 和 `/logout` 命令不會為 Claude Platform on AWS 登入 claude.ai 訂閱。身分驗證是透過您的 AWS 憑證或工作區 API 金鑰進行。

### 設定 Claude Code

設定環境變數，讓 Claude Code 透過 Claude Platform on AWS 路由，而非預設的 Anthropic API。

```bash theme={null}
export CLAUDE_CODE_USE_ANTHROPIC_AWS=1
export ANTHROPIC_AWS_WORKSPACE_ID=wrkspc_01ABCDEFGHIJKLMN
export AWS_REGION=us-east-1
```

`ANTHROPIC_AWS_WORKSPACE_ID` 為必要項目。Claude Code 會在每個請求中以 `anthropic-workspace-id` 標頭傳送它。請將範例值 `wrkspc_01ABCDEFGHIJKLMN` 替換為您在 Claude Platform on AWS 設定中取得的工作區 ID。

Claude Code 會根據 AWS 區域將基礎 URL 計算為 `https://aws-external-anthropic.{region}.api.aws`，而 AWS 區域的解析方式與 [Amazon Bedrock 的優先順序相同](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#3-configure-claude-code)。若要直接覆寫 URL，請設定 `ANTHROPIC_AWS_BASE_URL`。

即使您的環境中存在 AWS 憑證，Claude Platform on AWS 仍需主動選擇啟用。在提供者路由中，Amazon Bedrock 和 Microsoft Foundry 具有較高的優先順序，因此如果已設定 `CLAUDE_CODE_USE_BEDROCK` 和 `CLAUDE_CODE_USE_FOUNDRY`，請將其取消設定。

### 固定模型版本

Claude Platform on AWS 使用與直接 Claude API 相同的模型 ID。

預設別名 `fable`、`opus`、`sonnet` 和 `haiku` 會解析為 Claude Code 針對 Claude Platform on AWS 的內建預設值，這些預設值可能落後於最新版本。若未設定 `ANTHROPIC_DEFAULT_OPUS_MODEL`，`opus` 別名會解析為 Opus 5.5。在 v2.1.280 之前，自 v2.1.219 起它會解析為 Opus 5。

如果您將 Claude Code 部署給團隊，請明確固定模型 ID，以免新版本發布時所有人同時被切換：

```bash theme={null}
export ANTHROPIC_DEFAULT_FABLE_MODEL=claude-fable-5
export ANTHROPIC_DEFAULT_OPUS_MODEL=claude-opus-4-8
export ANTHROPIC_DEFAULT_SONNET_MODEL=claude-sonnet-5
export ANTHROPIC_DEFAULT_HAIKU_MODEL=claude-haiku-4-5
```

如需完整的模型 ID 與別名清單，請參閱[模型概覽](https://platform.claude.com/docs/en/about-claude/models/overview)。如需其他與模型相關的變數，請參閱[模型設定](https://code.claude.com/docs/zh-TW/model-config.md)。

[提示快取](https://code.claude.com/docs/zh-TW/prompt-caching.md)會自動啟用。若要請求 1 小時的快取 TTL 而非預設的 5 分鐘，請設定 `ENABLE_PROMPT_CACHING_1H=1`。API 對 1 小時快取寫入的計費費率較高。費率請參閱[提示快取定價](https://platform.claude.com/docs/en/build-with-claude/prompt-caching#pricing)。

若要為主要對話以及 Claude Code 在主要對話之外發出的請求設定不同的 TTL，請參閱[自行選擇 TTL](https://code.claude.com/docs/zh-TW/prompt-caching.md#choose-the-ttl-yourself)。

### 啟動並驗證

啟動 Claude Code 並確認路由：

```bash theme={null}
claude
```

當提供者處於啟用狀態時，啟動橫幅會顯示 `Claude Platform on AWS`。執行 `/status` 以檢查詳細資訊：`API provider` 一行會顯示 `Claude Platform on AWS`，輸出內容包括您的 `Workspace ID`、`AWS region`，以及（若您設定了覆寫）`Claude Platform on AWS base URL`。

## 使用 Agent SDK

[Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 讀取與 CLI 相同的環境變數，因此任何產生 Claude Code 子程序的程式都可以透過在呼叫前匯出 `CLAUDE_CODE_USE_ANTHROPIC_AWS`、`ANTHROPIC_AWS_WORKSPACE_ID` 和 `ANTHROPIC_AWS_API_KEY` 或 AWS 認證來針對 AWS 上的 Claude Platform。

```typescript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

process.env.CLAUDE_CODE_USE_ANTHROPIC_AWS = "1";
process.env.ANTHROPIC_AWS_WORKSPACE_ID = "wrkspc_01ABCDEFGHIJKLMN";
process.env.AWS_REGION = "us-east-1";

for await (const msg of query({ prompt: "What's in this repo?" })) {
  console.log(msg);
}
```

此範例依賴環境 AWS 認證鏈進行 SigV4。若要改用工作區 API 金鑰進行驗證，請以相同方式設定 `ANTHROPIC_AWS_API_KEY`。有關更廣泛的 Agent SDK 表面，請參閱 [Agent SDK 概述](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md)。

## 透過公司代理路由

若要透過代理或 [LLM gateway](https://code.claude.com/docs/zh-TW/llm-gateway) 路由流量，請將 `ANTHROPIC_AWS_BASE_URL` 設定為代理的位址。Claude Code 將請求傳送至該 URL，並使用相同的工作區和驗證標頭，因此任何轉發它們不變的閘道都有效。

```bash theme={null}
export CLAUDE_CODE_USE_ANTHROPIC_AWS=1
export ANTHROPIC_AWS_WORKSPACE_ID=wrkspc_01ABCDEFGHIJKLMN
export ANTHROPIC_AWS_BASE_URL=https://anthropic-proxy.example.com
```

如果您的閘道自行簽署請求，請設定 `CLAUDE_CODE_SKIP_ANTHROPIC_AWS_AUTH=1`，以便 Claude Code 傳送未簽署的請求，並讓閘道在轉發到 AWS 之前新增 SigV4 標頭。如果閘道需要自己的權杖，請在 `ANTHROPIC_AUTH_TOKEN` 中設定它。

```bash theme={null}
export CLAUDE_CODE_USE_ANTHROPIC_AWS=1
export CLAUDE_CODE_SKIP_ANTHROPIC_AWS_AUTH=1
export ANTHROPIC_AWS_WORKSPACE_ID=wrkspc_01ABCDEFGHIJKLMN
export ANTHROPIC_AWS_BASE_URL=https://anthropic-proxy.example.com
```

## Troubleshooting

執行 `/status` 以查看已解析的提供者和任何明確設定的工作區 ID、區域、基礎 URL 覆寫和驗證跳過設定。這是確認 Claude Code 是否完全針對 AWS 上的 Claude Platform 的最快方式。

### `403 Forbidden` 或 `AccessDenied` 在每個請求上

Claude Code 解析的 IAM 主體可能缺少在您的工作區中叫用 Anthropic 服務的權限。檢查附加到您的 AWS 設定檔或啟動 Claude Code 的執行器的角色，並驗證它具有 [IAM 動作參考](https://platform.claude.com/docs/zh-TW/api/claude-platform-on-aws-iam-actions)中記錄的 `aws-external-anthropic` 動作。

如果您設定了 `ANTHROPIC_AWS_API_KEY`，金鑰優先於 SigV4，過期的金鑰會產生相同的錯誤。在 AWS Console 中的 **Claude Platform on AWS → API keys** 下重新產生金鑰，或取消設定變數以回退到您的 AWS 認證。

### 請求失敗，出現遺失工作區錯誤

`ANTHROPIC_AWS_WORKSPACE_ID` 可能未設定或為空。每個 AWS 上的 Claude Platform 請求都必須包含工作區 ID。它不是由您的 AWS 認證隱含的。在您的 Claude Platform on AWS 設定中找到 ID，並在啟動 Claude Code 之前匯出它。

### 請求仍然轉到 `api.anthropic.com`

`CLAUDE_CODE_USE_ANTHROPIC_AWS` 可能未設定或設定為不解析為真值的值。將其設定為 `1` 並執行 `/status` 以確認已解析的提供者。如果也設定了 `CLAUDE_CODE_USE_BEDROCK` 或 `CLAUDE_CODE_USE_FOUNDRY`，那些優先於 AWS 上的 Claude Platform。

## 其他資源

設定 Claude Code 之前的 AWS 上的 Claude Platform 訂閱、工作區和 IAM 設定涵蓋在平台文件中：

* [AWS 上的 Claude Platform 概述](https://platform.claude.com/docs/zh-TW/build-with-claude/claude-platform-on-aws)：訂閱、工作區設定和產品參考
* [IAM 動作參考](https://platform.claude.com/docs/zh-TW/api/claude-platform-on-aws-iam-actions)：權限和受管原則

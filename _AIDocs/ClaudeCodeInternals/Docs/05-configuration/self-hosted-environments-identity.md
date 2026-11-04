<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/self-hosted-environments-identity | lastmod: 2026-10-29 | section: Configuration / Environments -->
> 來源：https://code.claude.com/docs/zh-TW/self-hosted-environments-identity（官方 zh-TW，lastmod 2026-10-29）｜分類：Configuration › Environments｜EN 摘要：Verify the CLAUDE_CODE_SESSION_ACCESS_TOKEN JWT so services on your network can trust requests from sessions in your self-hosted environment.

# 在自託管環境中驗證工作階段身分

> 驗證 CLAUDE_CODE_SESSION_ACCESS_TOKEN JWT，以便您網路上的服務可以信任來自自託管環境中工作階段的請求。

> [!NOTE]
>
> 自託管環境在 Team 和 Enterprise 方案上處於公開測試版；[擁有者](https://code.claude.com/docs/zh-TW/cloud-environments.md#organization-shared-environments)可以在[**雲端環境**管理頁面](https://claude.ai/admin-settings/cloud-environments)上開啟**允許自託管環境**來啟用它們。本頁面涵蓋工作階段身分驗證；請參閱[快速入門](https://code.claude.com/docs/zh-TW/self-hosted-environments-quickstart.md)以了解設定，以及[部署到生產環境](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md)以了解艦隊配方。

[自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)讓 Claude Code [雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)在您操作的基礎設施上執行，而不是在 Anthropic 的基礎設施上執行。由於工作階段在您的網路內執行，Claude 可以直接呼叫您的內部服務。這些服務需要一種方式來確認請求來自您環境中的 Claude Code 工作階段，並識別建立該工作階段的使用者或服務身分。

自託管環境中的每個工作階段都會在 `CLAUDE_CODE_SESSION_ACCESS_TOKEN` 環境變數中收到一個簽署的 JSON Web Token (JWT)。工作階段會像任何持有人認證一樣呈現令牌；例如，Claude 執行的指令碼可以使用 `curl -H "Authorization: Bearer $CLAUDE_CODE_SESSION_ACCESS_TOKEN"` 呼叫您的服務。Anthropic 簽署令牌並在公開 JWKS 端點發佈驗證金鑰。您的服務會擷取這些金鑰、驗證簽章，並讀取宣告以決定要授予什麼存取權限。

## 工作階段令牌

在您編寫驗證程式碼之前，請了解令牌建立的內容以及您的 JWT 程式庫將看到的形狀。

### 令牌證明的內容

有效的令牌建立了一些事實，並刻意不建立其他事實：

* **證明**：Anthropic 為特定環境中的特定工作階段簽發了令牌，以及工作階段的建立方式：由您組織中的使用者建立，或由您組織的服務身份建立，這是 [Claude Tag 頻道工作階段](https://claude.com/docs/claude-tag/concepts/agent-identity)的啟動方式
* **不證明**：執行者主機上的哪個程序呈現它。令牌位於工作階段內的環境變數中，因此 Claude 執行的任何程式碼以及工作階段啟動的任何工具或 MCP 伺服器都可以讀取並呈現它。

對您的服務有兩個後果：

* 根據您的環境 ID（在[**雲端環境**管理頁面](https://claude.ai/admin-settings/cloud-environments)上與您的環境一起顯示的 `ccpool_...` 值）驗證 `aud` 聲明，以拒絕簽發給任何其他組織環境的令牌。
* 將您從令牌衍生的認證範圍限制在單個編碼工作階段應該能夠執行的操作，而不是工作階段建立者可以執行的所有操作。請參閱[範圍衍生認證](#scope-derived-credentials)。

### 令牌格式

`CLAUDE_CODE_SESSION_ACCESS_TOKEN` 的值具有 `sk-ant-cc-` 前綴，後面跟著標準的三部分 JWT：

```text theme={null}
sk-ant-cc-<base64url header>.<base64url payload>.<base64url signature>
```

在將值傳遞給 JWT 程式庫之前，請移除前綴。簽發給 Anthropic 託管雲端工作階段的令牌改為帶有 `sk-ant-si-` 前綴，並由不同的金鑰集簽署，因此拒絕任何不以 `sk-ant-cc-` 開頭的值。

簽名演算法是 `ES256`，這是 P-256 曲線上的 ECDSA，使用 SHA-256。令牌標頭帶有一個 `kid`，用於識別 JWKS 中的哪個金鑰簽署了它。

## 驗證令牌

驗證在兩個地方之一執行。您網路上的服務根據 Anthropic 發佈的金鑰對令牌進行密碼學驗證，工作階段內的包裝指令碼可以改為使用執行者二進位檔案的內建解碼器。

### 從您的服務驗證令牌

Anthropic 在公開、未經驗證的端點發佈驗證金鑰：

```text theme={null}
https://api.anthropic.com/v1/code/.well-known/jwks.json
```

回應是標準的 [JSON Web Key Set](https://www.rfc-editor.org/rfc/rfc7517)。Anthropic 定期輪換簽署金鑰，輪換前的金鑰會在集合中保留足夠長的時間，以便它們簽署的令牌繼續驗證，因此不要固定單個金鑰。端點設定 `Cache-Control: public, max-age=300`，因此快取金鑰集並每五分鐘重新取得一次是安全的。

根據這些檢查驗證每個傳入令牌：

**1. 檢查前綴**

如果值不以 `sk-ant-cc-` 開頭，則拒絕該值，然後移除該前綴。其餘部分是標準的緊湊 JWT。

**2. 驗證簽名**

取得 JWKS，選擇其 `kid` 與 token 標頭相符的金鑰，並驗證 `ES256` 簽名。拒絕其 `alg` 標頭不是 `ES256` 的 token。如果 token 到達時帶有您快取的金鑰集中沒有的 `kid`，在拒絕它之前重新取得 JWKS 一次：輪換後，新 token 使用您快取的集合還沒有的金鑰簽署。

**3. 驗證簽發者**

如果 `iss` 不完全是 `ccr`，則拒絕 token。

**4. 根據您的環境驗證對象**

`aud` 聲明是一個陣列。除非它包含您的環境 ID（形式為 `ccpool_...`），否則拒絕 token。環境 ID 顯示在[**雲端環境**管理頁面](https://claude.ai/admin-settings/cloud-environments)上您環境的詳細對話框中，並在任何環境的工作階段 token 中顯示為 `ccr:pool_id` 聲明。此檢查是將 token 範圍限制在您的環境並拒絕簽發給其他組織的 token 的內容。

**5. 驗證角色**

如果 `ccr:role` 不完全是 `session_worker`，則拒絕 token。為自託管環境簽發的其他 token（例如環境祕密、執行者 token 和工作訂單）由相同的金鑰集簽署，但帶有不同的角色。

**6. 驗證過期**

如果 `exp` 在過去，則拒絕 token。Anthropic 預設簽發工作階段 token 的生命週期為四小時，最多八小時。執行者在過期前重新整理 token，並將新值推送到工作階段，因此 Claude 在重新整理後啟動的子程序會繼承它。因此，一個工作階段在其生命週期內可以向您的服務呈現多個不同的有效 token。

**7. 讀取身份**

建立使用者的身份在 `act` 聲明中。`act.sub` 是他們的 Anthropic 使用者 ID，採用前綴形式 `user:<id>`，而 `act.email`（當建立的使用介面記錄了一個時）是他們的電子郵件地址。您組織的服務身份建立的工作階段改為帶有 `agent:` 主體。只有當 `act.sub` 帶有 `user:` 前綴時，才將工作階段視為使用者建立的，而不是測試身份聲明是否不存在。

請參閱[聲明參考](#claims-reference)以了解完整結構和平面重複聲明。

這些檢查直接對應到標準 JWT 程式庫。下面的範例使用 [`jose`](https://www.npmjs.com/package/jose) 在 Node.js 中實現完整序列，它處理 JWKS 取得、快取和 `kid` 選擇，以及在 Python 中使用 [`PyJWT`](https://pyjwt.readthedocs.io/) 及其內建 JWKS 用戶端。

> [tab] Node.js (jose)
>
> ```typescript theme={null}
> import { createRemoteJWKSet, jwtVerify } from "jose";
>
> const JWKS = createRemoteJWKSet(
>   new URL("https://api.anthropic.com/v1/code/.well-known/jwks.json")
> );
>
> const PREFIX = "sk-ant-cc-";
> const EXPECTED_POOL_ID = "ccpool_...";
>
> export async function verifySessionToken(raw: string) {
>   if (!raw.startsWith(PREFIX)) {
>     throw new Error("not a self-hosted runner session token");
>   }
>   const jwt = raw.slice(PREFIX.length);
>
>   const { payload } = await jwtVerify(jwt, JWKS, {
>     issuer: "ccr",
>     audience: EXPECTED_POOL_ID,
>     algorithms: ["ES256"],
>   });
>
>   if (payload["ccr:role"] !== "session_worker") {
>     throw new Error("token is not a session_worker token");
>   }
>
>   const act = payload.act as { email?: string; sub?: string };
>   return {
>     sessionId: payload["ccr:session_id"] as string,
>     poolId: payload["ccr:pool_id"] as string,
>     orgId: payload["ccr:org_id"] as string,
>     creatorEmail: act?.email,
>     creatorSub: act?.sub,
>   };
> }
> ```

> [tab] Python (PyJWT)
>
> ```python theme={null}
> import jwt
> from jwt import PyJWKClient
>
> JWKS_URL = "https://api.anthropic.com/v1/code/.well-known/jwks.json"
> PREFIX = "sk-ant-cc-"
> EXPECTED_POOL_ID = "ccpool_..."
>
> jwks = PyJWKClient(JWKS_URL)
>
>
> def verify_session_token(raw: str) -> dict:
>     if not raw.startswith(PREFIX):
>         raise ValueError("not a self-hosted runner session token")
>     token = raw.removeprefix(PREFIX)
>
>     signing_key = jwks.get_signing_key_from_jwt(token)
>     payload = jwt.decode(
>         token,
>         signing_key.key,
>         algorithms=["ES256"],
>         issuer="ccr",
>         audience=EXPECTED_POOL_ID,
>     )
>
>     if payload.get("ccr:role") != "session_worker":
>         raise ValueError("token is not a session_worker token")
>
>     act = payload.get("act") or {}
>     return {
>         "session_id": payload["ccr:session_id"],
>         "pool_id": payload["ccr:pool_id"],
>         "org_id": payload["ccr:org_id"],
>         "creator_email": act.get("email"),
>         "creator_sub": act.get("sub"),
>     }
> ```

### 在工作階段內驗證令牌

[包裝指令碼](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#wrapper-scripts)在工作階段內執行，在 Claude 啟動之前。它們可以執行執行者二進位檔案的 `self-hosted-runner decode-token` 子命令，而不是呼叫 JWT 程式庫。子命令從位置引數、`CLAUDE_CODE_SESSION_ACCESS_TOKEN` 或管道 stdin 讀取令牌（按該順序），然後移除前綴、根據 JWKS 端點驗證簽名、檢查過期，並將聲明列印為 JSON。子命令僅執行簽名和過期檢查；它不檢查 `iss`、`aud` 或 `ccr:role`。當您的包裝器的驗證決定取決於這些聲明時，從列印的 JSON 讀取它們並明確比較它們。

此命令提取建立者身份，優先選擇電子郵件地址，然後是建立者的 `act.sub` 主體 `user:<id>` 或 `agent:<id>`：

```bash theme={null}
"$CLAUDE_RUNNER_CLAUDE_BIN" self-hosted-runner decode-token | jq -re '.act.email // .act.sub'
```

包裝器在 `CLAUDE_RUNNER_CLAUDE_BIN` 中接收執行者自身二進位檔案的絕對路徑；使用該路徑而不是 PATH 解析的 `claude`，以便解碼在執行者本身使用的相同二進位檔案上執行。

使用 `jq -re` 而不是 `jq -r`，以便遺漏的聲明導致非零退出。僅使用 `-r`，遺漏的聲明會列印字面字串 `null` 並以零退出，這會無聲地將壞值傳遞到下游。

如果 `decode-token` 無法從 JWKS 端點取得金鑰或無法驗證 token，它會將原因列印到 stderr，不列印任何聲明，並以代碼 1 退出。僅當 JWKS 端點無法到達的離線檢查時，才將 `--no-verify` 傳遞給 `decode-token`。

## 聲明參考

從 `ccr:*` 命名空間和 `act` 鏈讀取身份；平面 `account_email`、`organization_uuid` 和 `account_uuid` 聲明是可能被移除的向後相容性重複項。您組織的服務身份建立的工作階段在 `act.sub` 中帶有 `agent:` 主體，並省略 `act.email`、`ccr:account_id`、`account_email` 和 `account_uuid`。

兩個電子郵件聲明對於使用者建立的工作階段也是可選的。Anthropic 僅在建立請求的憑證帶有電子郵件時才在工作階段建立時記錄它們，從 CLI 分派的工作階段可能兩者都缺少。請根據 `act.sub` 或 `ccr:account_id` 而不是電子郵件來識別身份。Token 也可以帶有超出此表的其他聲明；忽略您不認識的聲明。下表列出了與驗證相關的工作階段 token 聲明。

| 聲明 | 類型 | 描述 |
| :- | :- | :- |
| `iss` | 字串 | 始終為 `ccr`。 |
| `sub` | 字串 | `ccr:session:<session_id>`。 |
| `aud` | 字串陣列 | 始終包含 `anthropic-api`。對於自託管環境中的工作階段，陣列也包含您的環境 ID，例如 `ccpool_...`。驗證環境 ID，而不是 `anthropic-api`。 |
| `exp` | 數字 | 過期時間為 Unix 時間戳。四小時預設生命週期，八小時最大值。 |
| `iat` | 數字 | 簽發時間為 Unix 時間戳。 |
| `jti` | 字串 | 唯一令牌識別碼。 |
| `ccr:role` | 字串 | 對於工作階段令牌始終為 `session_worker`。 |
| `ccr:session_id` | 字串 | `cse_...` 形式的工作階段 ID。與 `sub` 的後綴相同的值，且與 [`CLAUDE_CODE_REMOTE_SESSION_ID`](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration#wrapper-scripts) 為相同字串。若要將其與[生命週期 hook](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#lifecycle-hooks) 收到的 `CLAUDE_RUNNER_SESSION_ID` 比對，請將 `cse_` 前綴替換為 `session_`。 |
| `ccr:pool_id` | 字串 | 您的環境 ID。與出現在 `aud` 中的值相同。 |
| `ccr:org_id` | 字串 | 您的 Anthropic 組織 ID。 |
| `ccr:account_id` | 字串 | 建立使用者的 Anthropic 帳戶 ID：`act.sub` 的值，不帶 `user:` 前綴，一個標記的 `user_...` ID。與 [spawn-runner hook](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#the-spawn-runner-hook) 的 `CLAUDE_RUNNER_ACCOUNT_ID` 帶有的值相同，以及 [`--lock-to-account`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags) 接受的值，因此三者作為相等的字串進行比較。 |
| `account_email` | 字串 | `act.email` 的重複；每當 `act.email` 不存在時就不存在。 |
| `organization_uuid` | 字串 | 您的 Anthropic 組織 UUID。 |
| `account_uuid` | 字串 | 建立使用者的 Anthropic 帳戶 UUID。 |
| `act` | 物件 | [RFC 8693](https://www.rfc-editor.org/rfc/rfc8693) 委派鏈。請參閱 [The `act` chain](#the-act-chain)。 |

### The `act` chain

`act` 聲明記錄了從建立工作階段的使用者或服務身份到[環境](https://code.claude.com/docs/zh-TW/self-hosted-environments#key-concepts)（其祕密允許執行者）以及建立該祕密的身份的完整委派路徑。建立者是最外層的參與者，因此 `act.sub` 直接識別他們。

| 路徑 | 描述 |
| :- | :- |
| `act.sub` | 建立使用者的 Anthropic 使用者 ID，形式為 `user:<id>`，或當您組織的服務身份建立工作階段時為 `agent:<id>`。 |
| `act.email` | 建立使用者的電子郵件地址，當在工作階段建立時記錄了一個時。不要要求它；根據 `act.sub` 識別。 |
| `act.attested_by` | 保留給上游身份提供者對建立使用者的證明。預期此欄位不存在，且不要依賴它。根據 `act.sub` 識別。若您需要地址，請在 `act.email` 存在時讀取它。 |
| `act.act` | 生成工作階段的執行者。`act.act.sub` 是 `ccr:runner:<runner_id>`。 |
| `act.act.act` | 環境。`act.act.act.sub` 是 `ccr:pool:<pool_id>`。 |
| `act.act.act.act` | 建立執行者註冊的環境祕密的身份。鏈在此結束。 |

## 範圍衍生認證

工作階段令牌識別建立工作階段的使用者或服務身份，但不要將其視為等同於該建立者直接登入。令牌位於工作階段內的環境變數中，因此 Claude 執行的任何程式碼以及工作階段啟動的任何工具或 MCP 伺服器都可以讀取並呈現它。

驗證也是離線的：根據 JWKS 驗證的令牌在其 `exp` 之前保持有效，無論自那時以來工作階段發生了什麼，Anthropic 不會為工作階段令牌發佈撤銷源。相應地綁定您從令牌衍生的任何內容。

當您的服務將令牌交換為內部認證時，簽發範圍限制在一個編碼工作階段應該到達的內容的認證：

* **限制功能**：授予工作階段編碼任務所需的資源的讀取和寫入存取權限，而不是建立者在其他地方持有的管理功能。
* **限制生命週期**：將衍生認證綁定到令牌的 `exp` 或更短。
* **作為工作階段進行審計**：記錄 `ccr:session_id` 和 `jti` 以及建立者身份，以便您可以將操作追蹤回特定工作階段。

## 相關環境變數

建立者身份也以純環境變數的形式出現在兩個永遠不驗證令牌的表面上：

* **[`spawn-runner` hook](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration#the-spawn-runner-hook)，在協調器上**：hook 在任何執行者存在於佇列工作階段之前執行，並在 `CLAUDE_RUNNER_ACCOUNT_EMAIL` 和 `CLAUDE_RUNNER_ACCOUNT_ID` 等變數中接收建立者身份。協調器從工作訂單（授權生成一個執行者的簽署單次使用令牌）讀取它們，而不驗證工作訂單的簽名本身；聲明是受信任的，因為工作訂單通過協調器與 Anthropic 的連線到達，環境祕密對其進行驗證。
* **[包裝指令碼](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#wrapper-scripts)，在工作階段內**：包裝器接收 `CCR_SESSION_ACCOUNT_EMAIL`，建立者的電子郵件從令牌預先提取，無需簽名驗證。該變數適合用於標籤，例如提交預告片，而不是用於驗證決定。

使用純變數進行協調器端決定，例如選擇機器映像。當下游服務需要獨立的密碼學證明而不是信任執行者的環境時，使用 `CLAUDE_CODE_SESSION_ACCESS_TOKEN`。

## 接下來

* [自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)：環境、執行者和工作階段模型；[快速入門](https://code.claude.com/docs/zh-TW/self-hosted-environments-quickstart.md)和[部署到生產環境](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md)包含設定和操作
* [自訂工作階段](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md)：使用令牌的包裝指令碼，以及 `spawn-runner` hook
* [參考](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference.md)：CLI 旗標、環境變數和指標

<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/claude-apps-gateway-config | lastmod: 2026-11-04 | section: Administration / Gateways -->
> 來源：https://code.claude.com/docs/zh-TW/claude-apps-gateway-config（官方 zh-TW，lastmod 2026-11-04）｜分類：Administration › Gateways｜EN 摘要：Reference for every gateway.yaml option: listener and TLS, OIDC, session, Postgres store, Amazon Bedrock, Claude Platform on AWS, Google Cloud's Agent Platform, and Microsoft Foundry upstreams, model routing, managed policies, and telemetry.

# Claude 應用程式閘道設定

> 每個 gateway.yaml 選項的參考資料：監聽器和 TLS、OIDC、工作階段、Postgres 存放區、Amazon Bedrock、Claude Platform on AWS、Google Cloud 的 Agent Platform 和 Microsoft Foundry 上游、模型路由、受管原則和遙測。

Claude 應用程式閘道部署由一個 YAML 檔案設定，按慣例稱為 `gateway.yaml`。該檔案定義閘道執行的所有操作：它在哪裡監聽、開發人員如何登入、推論去往何處，以及哪些原則和遙測適用。本頁是該檔案中每個選項的參考資料。若要撰寫您的第一個，請從[快速入門](https://code.claude.com/docs/zh-TW/claude-apps-gateway#quickstart)開始，它會建立最小的工作設定並執行它；一旦您有了滿意的設定，[部署指南](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md)涵蓋將其容器化並在 Kubernetes、Cloud Run 或您自己的平台上託管。

閘道在啟動時使用 `claude gateway --config /path/to/gateway.yaml` 讀取該檔案一次。每個選項都在啟動時根據架構進行驗證，因此格式不正確的設定會在啟動時失敗，並出現欄位級錯誤，而不是在首次使用時失敗。

本頁末尾的[完整範例](#complete-example)涵蓋每個部分。

## 檔案結構

五個部分是[必需的](#required-sections)。其他所有部分都是[選擇性的](#optional-sections)，省略的部分會採用其預設值。未知的鍵會導致啟動失敗，因此打字錯誤會顯示為具名錯誤，而不是被無聲地忽略的設定。

**必需部分：**

* [`listen`](#listen)：繫結位址、公開 URL、TLS 終止
* [`oidc`](#oidc)：您的身分識別提供者 (IdP)，包括簽發者、用戶端、宣告對應，以及誰可以登入
* [`session`](#session)：閘道器鑄造的持有人令牌，包括祕密和生命週期
* [`store`](#store)：PostgreSQL，用於裝置授權和速率限制計數器
* [`upstreams`](#upstreams)：推論的去向，無論是 Anthropic、Amazon Bedrock、AWS 上的 Claude Platform、Google Cloud 的 Agent Platform，還是 Microsoft Foundry

**選擇性部分：**

* [`admin`](#admin)：Admin API 驗證和支出限制的保留期
* [`enforcement`](#enforcement)：支出限制失敗開放或失敗關閉行為
* [`pricing`](#pricing)：合約費率以及支出計量和開發人員看到的成本數字的乘數
* [`models`](#models) 和 `auto_include_builtin_models`：管理員策劃的模型清單和每個上游的 ID
* [`managed`](#managed)：按 IdP 群組的受管設定原則
* [`telemetry`](#telemetry)：OTLP 轉發到您的可觀測性堆疊
* [`access_control`、`limits`、`timeouts`、`rate_limits`](#http-tuning)：IP 允許/拒絕、請求大小上限、上游首位元組時間，以及每個 IP 的登入限制
* [`load_test_mode`](#load_test_mode)：在不呼叫模型提供者的情況下對閘道器進行負載測試

## 祕密擴展

不要直接在 `gateway.yaml` 中寫入祕密，例如 `client_secret`、`jwt_secret` 或 `postgres_url`。使用下列其中一種形式參考它們，閘道會在啟動時從環境變數或檔案解析該值：

| 形式 | 解析為 | 用於 |
| - | - | - |
| `${VAR}` | 環境變數 `VAR`。如果未定義，啟動失敗。 | 容器環境變數、透過環境注入的 AWS Secrets Manager |
| `${file:/path}` | 該絕對路徑處檔案的內容，已修剪。參考必須是欄位的整個值：不同於 `${VAR}`，它不會在較長的字串內展開，因此對於資料庫密碼，請設定 `store.password` 而不是將其嵌入 `postgres_url`。 | Kubernetes Secret 卷掛載、Vault Agent、SOPS |

## 必需部分

### `listen`

`listen` 區塊控制閘道服務的位置：繫結位址和連接埠、外部可見的來源，以及選用的 TLS 終止。

| 欄位 | 必需 | 說明 |
| - | - | - |
| `host` | 否 | 繫結位址。預設 `0.0.0.0`。 |
| `port` | 否 | 繫結連接埠。預設 `8080`。 |
| `public_url` | 除非 `host` 是環回 | 外部可見的 `https://` 來源，用於建立 IdP `redirect_uri` 和發現中繼資料。在 `host` 不是環回位址時為必需，無論 TLS 是在代理伺服器（例如 ALB、Ingress 或 Cloud Run）還是在閘道本身透過 `tls` 終止，因為閘道永遠不會從 `X-Forwarded-*` 標頭衍生自己的來源；它們是用戶端可偽造的。沒有它啟動會失敗。下面的 `trusted_proxies` 僅控制用戶端 IP 解析。啟用[遙測](#telemetry)時也是必需的，因為閘道從此 URL 建立它推送給用戶端的 OTLP 端點。 |
| `tls.cert` / `tls.key` | 否 | 如果閘道自己終止 TLS，則為 PEM 路徑 |
| `trusted_proxies` | 否 | 閘道前面的負載平衡器的 CIDR 或 IP。設定時，閘道僅信任來自這些對等方的 `X-Forwarded-For`，並記錄真實用戶端 IP 以進行每 IP 速率限制和稽核。等同於 nginx `set_real_ip_from`。`X-Forwarded-For` 項目寫成 `ipv4:port` 或 `[ipv6]:port`（如某些負載平衡器所做），會以連接埠被刪除的方式讀取。附加連接埠且沒有括號的 IPv6 位址可能被讀取為不同位址或根本不被讀取，因此在任何寫入該形式的代理伺服器上關閉連接埠選項。 |

### `oidc`

`oidc` 區塊將閘道連接到您的身分識別提供者，並決定誰可以登入。它命名簽發者和 OAuth 用戶端、對應攜帶電子郵件和群組的宣告，並按電子郵件網域或群組限制登入。

OpenID Connect (OIDC) 是閘道與您的身分識別提供者一起使用的 SSO 協定；請參閱[身分識別提供者設定](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#identity-provider-setup)以了解在 IdP 端註冊的內容。

| 欄位 | 必需 | 說明 |
| - | - | - |
| `issuer` | 是 | OIDC 發現基礎。必須在 `/.well-known/openid-configuration` 提供發現。在生產環境中使用 HTTPS；閘道接受 `http://` 簽發者。環回簽發者（例如 `http://localhost:8081`）會被[SSRF 防護](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#threat-model-summary)拒絕，除非在閘道的環境中設定了 `CLAUDE_GATEWAY_ALLOW_LOOPBACK=1`。 |
| `client_id` | 是 | 來自您的 OAuth 用戶端註冊 |
| `client_secret` | 除非 `token_endpoint_auth_method` 為 `private_key_jwt` | 來自您的 OAuth 用戶端註冊。使用[憑證用戶端身分驗證](#certificate-client-authentication)時請省略。 |
| `allowed_email_domains` | 否 | 拒絕 `email` 宣告不在這些網域之一中的 id\_token，不區分大小寫。針對多租戶 IdP 誤設定的深度防禦。獨立於此設定，`email_verified` 宣告明確為 `false` 的 id\_token 始終被拒絕。 |
| `allowed_groups` | 否 | 限制登入為這些 IdP 群組的成員，與 `groups_claim` 相符。允許電子郵件網域中但不在這些群組中的使用者被拒絕。需要 IdP 發出群組宣告。匹配是針對該宣告中值的精確、區分大小寫的字串比較，閘道不展開嵌套群組：若要允許子群組的成員，請在此列出子群組或設定 IdP 以發出扁平化成員資格。 |
| `groups_claim` | 否 | 哪個 id\_token 宣告攜帶群組成員資格。預設 `groups`。Microsoft Entra 在 `roles` 下發出應用程式角色。接受平面鍵或 RFC 6901 JSON 指標，例如 `/resource_access/gateway/roles` 用於嵌套宣告。 |
| `google_groups` | 否 | 透過 Google Workspace Admin SDK Directory API 查詢已登入使用者的群組，因為 Google 的 id\_token 不攜帶群組宣告。將 `service_account_json_path` 設定為具有 `https://www.googleapis.com/auth/admin.directory.group.readonly` 範圍的網域範圍委派的服務帳戶金鑰檔案，並將 `admin_email` 設定為服務帳戶模擬的 Workspace 管理員；Directory API 需要真實的管理員主體。每個使用者的群組電子郵件地址成為其群組宣告，因此 `allowed_groups` 和 `managed.policies.match.groups` 與群組電子郵件相符。 |
| `email_claim` | 否 | 哪個 id\_token 宣告攜帶使用者的電子郵件。預設 `email`。某些 IdP（例如 ADFS 和 Entra B2C）改為發出 `upn` 或 `preferred_username`。接受平面鍵、JSON 指標或備援鍵清單，其中使用第一個存在的鍵。 |
| `scopes` | 否 | 完整覆寫閘道請求的 OIDC 範圍。預設 `[openid, profile, email, offline_access]`。當您的 IdP 拒絕它不識別的範圍或需要自訂範圍來發出群組或電子郵件時設定。必須包含 `openid`。刪除 `offline_access` 會停用重新整理 token，因此開發人員每 `session.ttl_hours` 重新執行瀏覽器登入。請參閱[身分識別提供者設定](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#identity-provider-setup)以了解每個 IdP 範圍配方，例如 Google 的重新整理 token 流程。 |
| `scope_on_refresh` | 否 | 當閘道交換重新整理 token 時，也傳送 `scope`，具有與登入請求相同的清單。預設 `false`：重新整理請求省略 `scope`。大多數 IdP 在每次重新整理時返回 id\_token，不需要這個。當您的 IdP 僅在再次請求 `openid` 時才在重新整理時返回 id\_token 時設定 `true`，Okta 為其重新整理授權記錄了這一點。沒有 id\_token，每次重新整理都取決於 IdP 的 userinfo 端點接受重新整理的存取 token。如果您在登入或匹配原則上閘控群組，且您的 IdP 的重新整理時間 id\_token 省略它們，也設定 `userinfo_fallback: true`，以便閘道從 userinfo 端點填補它們。授予的範圍少於請求的 IdP 可以使用 `invalid_scope` 拒絕重新整理，包括現有工作階段（如果您在此開啟時將項目新增到 `scopes`）。如果在設定後重新整理開始在 `token_endpoint` 失敗，請取消設定此鍵。需要閘道伺服器上的 Claude Code v2.1.260 或更新版本。 |
| `extra_auth_params` | 否 | 附加到 IdP 授權請求的額外查詢參數，逐字。這是 IdP 特定行為的覆寫機制，例如 Google 重新整理 token 的 `access_type: offline`、某些 Entra 租戶的 `domain_hint` 或逐步提升流程的 `acr_values`。無法覆寫閘道管理的協定參數：`state`、`nonce`、`redirect_uri`、PKCE、`scope`、`response_type`、`response_mode` 和 `client_id`。 |
| `userinfo_fallback` | 否 | 當 id\_token 省略電子郵件或群組時，從 `/userinfo` 擷取它們。Keycloak 輕量級存取 token、Okta 組織伺服器和 ADFS 最小 token 需要。id\_token 保持權威；userinfo 僅填補空白。預設 `false`。 |
| `use_pkce` | 否 | 在授權請求上傳送 PKCE (S256) 挑戰。預設 `true`。僅當您的 IdP 為此機密用戶端拒絕 PKCE 時設定 `false`。 |
| `clock_skew_seconds` | 否 | 驗證 id\_token 時間宣告時容許時鐘漂移。預設 `0`，這是嚴格的。如果您在登入後立即看到「token 已過期/尚未有效」錯誤，請提高以應對主機/IdP 時鐘偏差。 |
| `token_endpoint_auth_method` | 否 | 閘道向 IdP 的 token 端點進行身分驗證的方式：`client_secret_basic`、`client_secret_post`，或用於[憑證用戶端身分驗證](#certificate-client-authentication)的 `private_key_jwt`。預設情況下，閘道會根據 IdP 公告的內容，從兩種 `client_secret` 方法中選擇一種。 |
| `client_assertion` | 使用 `private_key_jwt` 時 | 包含 `private_key_pem` 和 `certificate_pem` 的區塊：用於[憑證用戶端身分驗證](#certificate-client-authentication)的私密金鑰和憑證。需要 v2.1.284 或更新版本。 |
| `id_token_signed_response_alg` | 否 | 預期的 id\_token 簽署演算法。預設 `RS256`。為使用 ES256、PS256 或 EdDSA 簽署的 IdP 設定。 |
| `additional_authorized_parties` | 否 | 除了 `client_id` 之外要接受的額外 `azp` 值，用於 Keycloak 仲介和 token 交換流程 |
| `discovery_url` | 否 | 從此 URL 擷取發現文件，而不是從 `issuer` 衍生，用於位於重寫簽發者主機的代理伺服器後面的 IdP。路徑必須包含 `/.well-known/`。 |
| `use_proxy` | 否 | 透過 `HTTPS_PROXY` 或 `HTTP_PROXY` 中的轉發代理伺服器傳送閘道自己的 IdP 請求，遵守 `NO_PROXY`。`false` 保持這些請求直接。需要 v2.1.227 或更新版本；請參閱下面的[透過轉發代理伺服器的 IdP 請求](#idp-requests-through-a-forward-proxy)。 |
| `form_action_origins` | 否 | `/device` 頁面的 `Content-Security-Policy: form-action` 指令的其他來源。閘道已允許 `'self'` 和發現的 `authorization_endpoint` 來源，但 Chrome 對整個重新導向鏈強制執行 `form-action`。如果您的 IdP 透過第二個主機重新導向，例如 Azure AD 聯合到 ADFS、中樞輪輻 Okta 或公司 SSO 攔截器，列出授權請求可能重新導向的每個來源。 |
| `ca_cert_pem` | 否 | PEM 編碼的 CA 憑證本身，而不是檔案的路徑。它僅替換 IdP 請求的系統信任存放區。若要載入掛載的檔案，請寫入 `${file:/etc/gateway/idp-ca.pem}`。用於公司 PKI 後面的 Keycloak 或 Dex。 |

#### 憑證用戶端身分驗證

如果您的身分識別提供者使用憑證而非用戶端密碼來驗證 OAuth 用戶端（如 Microsoft Entra 使用憑證的方式），請設定 `token_endpoint_auth_method: private_key_jwt`。需要閘道伺服器上的 Claude Code v2.1.284 或更新版本。

使用此設定時，閘道不會傳送任何密碼。當開發人員登入時，以及每次閘道重新整理其工作階段時，閘道都會使用以憑證私密金鑰簽署的短期 JWT 向 IdP 的 token 端點進行身分驗證。該 JWT 以 RS256 簽署，並透過 `x5t` 和 `x5t#S256` 指紋標頭（而非 `kid`）識別憑證。您的 IdP 必須能夠依指紋找到已註冊的憑證。

**1. 建立金鑰和憑證**

建立至少 2048 位元、採用 PKCS#8 或 PKCS#1 PEM 格式的未加密 RSA 私密金鑰，並為其建立憑證。閘道會拒絕以任何不符合這些條件的金鑰啟動。此 `openssl` 命令會建立這樣的金鑰，以及有效期為一年的自我簽署憑證：

```bash theme={null}
openssl req -x509 -newkey rsa:2048 -nodes -keyout idp-client.key -out idp-client.crt -days 365 -subj "/CN=claude-gateway"
```

它會將 `idp-client.key` 和 `idp-client.crt` 寫入目前目錄。將這兩個檔案複製或掛載到閘道可讀取的位置。步驟 3 中的範例使用 `/etc/gateway/`。

**2. 將憑證上傳到 IdP**

將憑證（而非私密金鑰）上傳到 IdP 上閘道的應用程式註冊。

**3. 將金鑰和憑證新增到 gateway.yaml**

在 `client_assertion` 區塊中提供私密金鑰和憑證給閘道。省略 `client_secret`，因為當它與 `private_key_jwt` 一起設定時，閘道會拒絕啟動。此 `oidc` 區塊使用憑證讓閘道向 Microsoft Entra 租戶進行身分驗證：

```yaml theme={null}
oidc:
  issuer: https://login.microsoftonline.com/<tenant-id>/v2.0
  client_id: <application-id>
  token_endpoint_auth_method: private_key_jwt
  client_assertion:
    private_key_pem: ${file:/etc/gateway/idp-client.key}
    certificate_pem: ${file:/etc/gateway/idp-client.crt}
```

這兩個值都是 PEM 內容，而不是檔案路徑，因此請如範例所示使用 `${file:/path}` 載入掛載的檔案。除非 `certificate_pem` 是單一 PEM 憑證（不含其鏈的其餘部分），且其公開金鑰與 `private_key_pem` 相符，否則閘道會拒絕啟動。

**4. 重新啟動閘道並檢查啟動日誌**

重新啟動閘道，並在啟動日誌中找到此行：

```text theme={null}
[gateway] 2026-10-01T23:07:40.512Z info oidc: client authentication private_key_jwt; certificate CN=claude-gateway, SHA-1 thumbprint DE92821854EE8BAA1D98C758FAA04AABE80B9F57, expires Oct  1 23:07:31 2027 GMT
```

將 SHA-1 指紋與 IdP 針對您上傳的憑證所顯示的指紋進行比較。如果憑證已過期或尚未生效，閘道仍會啟動，但會記錄一則警告，指出在您替換憑證之前，登入和重新整理都會失敗。若要確認 IdP 接受該憑證，請讓一位開發人員透過閘道登入。

#### 輪換用戶端憑證

閘道僅在啟動時讀取一次金鑰和憑證，因此變更的檔案僅在重新啟動後才會生效。請依照以下順序輪換，以確保沒有任何 token 請求出示 IdP 沒有的憑證：

1. 將新憑證上傳到 IdP，與舊憑證並存。
2. 替換 `gateway.yaml` 載入的金鑰和憑證檔案，然後重新啟動閘道。如果您執行多個副本，可以使用[滾動重新啟動](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#upgrades)，因為在您移除舊憑證之前，IdP 同時擁有兩個憑證。
3. 在每個副本都重新啟動後，從 IdP 移除舊憑證。

#### 透過轉發代理伺服器的 IdP 請求

推論上游在每個版本上都遵守 `HTTPS_PROXY` 和 `HTTP_PROXY`。閘道自己對 IdP 的請求（發現、JWKS、token 和 userinfo）直接進行，除非您設定 `oidc.use_proxy: true`，這需要 v2.1.227 或更新版本。當代理伺服器變數被設定、`use_proxy` 未設定且簽發者未被 `NO_PROXY` 涵蓋時，閘道保持這些請求直接並在啟動時記錄通知，請您做出選擇；`use_proxy: false` 保持它們直接並隱藏通知。

使用 `use_proxy: true` 時，Pod 自己解析每個 IdP 端點的主機名稱，並請代理伺服器 `CONNECT` 到解析的 IP 位址，因此代理伺服器必須接受 `CONNECT` 到發現文件命名的每個主機的 IP 位址，而不僅僅是簽發者。使用 `http://` 代理伺服器 URL。`ca_cert_pem` 和[SSRF 防護](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#threat-model-summary)也適用於經代理伺服器的路徑。

[Proxy-only egress](#proxy-only-egress) 改變這兩者：當它處於活動狀態時，IdP 請求遵循代理伺服器，除非您設定 `use_proxy: false`，且閘道將每個 IdP 主機名稱交給代理伺服器，而不先解析它。

#### Proxy-only egress

當 Pod 僅透過該轉發代理伺服器到達其他主機且無法自己解析公開 DNS 名稱時，或當代理伺服器拒絕 `CONNECT` 到 IP 位址時，在閘道的環境中於 `HTTPS_PROXY` 旁邊設定 `CLAUDE_GATEWAY_PROXY_IS_EGRESS_BOUNDARY=1`。需要 v2.1.277 或更新版本。它是環境變數而不是 `gateway.yaml` 設定鍵，因此設定檔中的任何內容都無法放寬閘道的位址檢查。

```bash theme={null}
export HTTPS_PROXY=http://proxy.corp.example.com:3128
export NO_PROXY=
export no_proxy=
export CLAUDE_GATEWAY_PROXY_IS_EGRESS_BOUNDARY=1
```

當 proxy-only egress 處於活動狀態時，閘道在啟動時記錄一個 `network:` 行。

下面的每一列是設定了 `HTTPS_PROXY` 的閘道上一類出站請求，分別列出預設情況下和 proxy-only egress 處於活動狀態時的行為。

| 出站請求 | 預設 | Proxy-only egress 處於活動狀態 |
| - | - | - |
| `provider: anthropic` 上游、Workload Identity Federation token 交換、`telemetry.forward_to` 匯出 | 在本地解析和檢查，然後透過代理伺服器 `CONNECT` 到檢查的 IP 位址。列在 `NO_PROXY` 中的遙測收集器改為直接到達 | 主機名稱交給代理伺服器 |
| IdP 發現、JWKS、token 和 userinfo | 直接，除非 [`oidc.use_proxy: true`](#idp-requests-through-a-forward-proxy)，然後 `CONNECT` 到檢查的 IP 位址 | 主機名稱交給代理伺服器，除非 `oidc.use_proxy: false` 保持內部 IdP 直接 |
| Amazon Bedrock、Claude Platform on AWS、Google Cloud 的 Agent Platform 和 Microsoft Foundry 上游；Google 群組查詢 | 主機名稱交給代理伺服器 | 未更改 |

Proxy-only egress 保持關閉，除非閘道的環境滿足所有這三個條件：

* `HTTPS_PROXY` 或 `HTTP_PROXY` 被設定。
* `NO_PROXY` 和 `no_proxy` 為空。如果您的平台將任一個注入 Pod，在閘道容器上將兩者設定為空值。在 `NO_PROXY` 中列出遙測收集器會使 proxy-only egress 保持關閉。
* `CLAUDE_GATEWAY_ALLOW_LOOPBACK` 未開啟。Pod 自己環回上的收集器或 IdP 無法與 proxy-only egress 結合，因為交給代理伺服器的環回位址將是代理伺服器主機自己的，因此請改為給這些服務一個代理伺服器可以到達的位址。出於相同原因，當 proxy-only egress 處於活動狀態時，閘道完全拒絕 `localhost` 風格的名稱。

當其中一個條件未滿足時，閘道在啟動時記錄警告，命名阻止它的變數，並保持預設行為。

一旦 proxy-only egress 處於活動狀態，請在代理伺服器中允許每個目的地，包括內部收集器和任何由 IP 位址設定的主機。您仍然可以使用 [`oidc.use_proxy: false`](#idp-requests-through-a-forward-proxy) 保持內部 IdP 直接。

> [!WARNING]
>
> 僅當代理伺服器的允許清單至少與閘道自己的檢查一樣嚴格時才開啟此功能。代理伺服器必須拒絕雲中繼資料端點（例如 `169.254.169.254` 和 `metadata.google.internal`）、連結本地位址和代理伺服器主機自己的環回，並且必須按名稱解析到的位址拒絕它們，而不僅僅是按名稱，因為閘道不再攔截解析到其中之一的主機名稱。連接到任何被要求之處的代理伺服器會移除閘道對這些請求的[SSRF 防護](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#threat-model-summary)。

### `session`

`session` 區塊塑造閘道在登入後鑄造的持有人 token：簽署它們的祕密和它們的生命週期。

| 欄位 | 必需 | 說明 |
| - | - | - |
| `jwt_secret` | 是 | 至少 32 位元組的熵，例如來自 `openssl rand -base64 32`。簽署閘道的 HS256 持有人 token。接受單一字串或用於輪換的陣列：索引 0 簽署，所有項目驗證。若要輪換，前置新祕密，等待 `ttl_hours`，然後刪除舊祕密。 |
| `ttl_hours` | 否 | 閘道持有人 token 生命週期。預設 `1`。當 IdP 發出重新整理 token 時，CLI 在過期前無聲地重新整理。較短的生命週期會更快地取消佈建；較長的生命週期會減少 IdP 往返次數。如果您的 IdP 因為 `offline_access` 不可用而無法發出重新整理 token，則沒有無聲重新整理，因此將其提高到 `8` 或 `12` 以避免每小時將開發人員送回瀏覽器登入。 |

### `store`

`store` 區塊將閘道指向其 PostgreSQL 資料庫，該資料庫保存裝置授權和速率限制計數器。

| 欄位 | 必需 | 說明 |
| - | - | - |
| `postgres_url` | 是 | 僅含一個主機的 `postgres://` 或 `postgresql://` URL，而不是以逗號分隔的清單。閘道在啟動時和升級時執行自己的 schema 遷移，因此角色需要在目標 schema 上建立和更改資料表的權限。請參閱[升級](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#upgrades)和 [Postgres](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#postgres)。 |
| `username` | 否 | 覆寫 `postgres_url` 中的使用者 |
| `password` | 否 | 資料庫憑證。在此設定它而不是在 `postgres_url` 中，以便憑證保持在 URL 之外。接受任何字元並優先於 URL 中的憑證。 |
| `max_connections` | 否 | 每個副本的 Postgres 連線池大小。預設 `5`，這是保守的且對共享資料庫友善。啟用[支出限制](#admin)後，閘道每個推論請求會執行幾次資料庫操作，因此在負載下為專用資料庫提高它，但不超過[調整連線池大小](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#size-the-connection-pool)所允許的範圍。 |
| `connect_timeout_seconds` | 否 | 閘道開啟 Postgres 連線時等待的秒數。從 `1` 到 `60` 的整數，預設 `5`。如果新閘道執行個體啟動時連線嘗試逾時，請提高它。需要閘道伺服器上的 Claude Code v2.1.274 或更新版本。較早的版本在設定此鍵時拒絕啟動。 |
| `readiness_grace_seconds` | 否 | Postgres 停止回答後 `/readyz` 保持報告就緒的秒數。從 `0` 到 `3600` 的整數，預設 `0`。請參閱[中斷行為](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#outage-behavior)以了解如何選擇值。需要閘道伺服器上的 Claude Code v2.1.282 或更新版本。較早的版本在設定此鍵時拒絕啟動。 |

對於本地開發，將 `postgres_url` 指向一次性 Postgres 容器，例如 `docker run --rm -p 5432:5432 -e POSTGRES_HOST_AUTH_METHOD=trust postgres`。

### `upstreams`

`upstreams` 是有序清單。閘道會將推論轉送到第一個能解析所請求模型的上游，並略過任何其 [`groups` 清單](#send-each-team-to-its-own-upstream)不包含該開發人員的上游。

在 `5xx`、`429`、`401`、`403`、`404` 或逾時時，閘道會故障轉移到下一個上游；其他 `4xx` 不會，因為這些錯誤可歸因於請求而不是上游。`401` 或 `403` 表示上游拒絕了閘道使用的憑證，或拒絕其存取，例如存取所請求的模型。`404` 表示該上游不服務所請求的模型，因此清單中稍後的上游仍然可以。

如果您在上游上設定 `forward_user_identity: true`，它返回給攜帶開發人員電子郵件的請求的 `429` 不會故障轉移。請參閱[每個使用者限制拒絕如何到達開發人員](#per-user-identity-headers-for-a-proxy-you-run)。

在 `404` 時故障轉移需要閘道 v2.1.198 或更新版本。較早的版本即使清單中稍後的上游服務該模型，也會將第一個 `404` 返回給用戶端。

相同提供者的多個上游必須設定不同的 `name:`。

Amazon Bedrock、Claude Platform on AWS、Google Cloud 的 Agent Platform 和 Microsoft Foundry 用戶端在啟動時建立一次，其 SDK 在內部重新整理憑證，因此輪換雲憑證不需要重新啟動。靜態 Anthropic API 金鑰和持有人 token 在啟動時讀取；請參閱 [Anthropic API](#anthropic-api)。

#### 上游錯誤訊息

閘道返回一個上游的錯誤回應，或其自己的 `502`，取決於上游如何回答：

* **上游返回閘道不[故障轉移](#multiple-upstreams)的狀態**：該上游的回應。閘道不嘗試進一步的上游。
* **閘道嘗試的每個上游都以會[觸發容錯移轉](#multiple-upstreams)的方式失敗**：回傳最後一個 `429`。若沒有任何上游回傳 `429`，閘道會依序優先採用最後一個 `401` 或 `403`、最後一個 `404`，以及最後一個 `501`。若這些都沒有，則回傳閘道自己的 `502`，`all upstreams failed (N attempted)`。N 計算的是您的 [`upstreams`](#upstreams) 項目數（包括被略過的項目），減去其 [`groups`](#send-each-team-to-its-own-upstream) 清單不包含該開發人員的項目。

當閘道返回上游的回應時，它保持上游的狀態碼。它是否保持上游的訊息取決於提供者。Anthropic API 上游的錯誤正文未經更改地到達開發人員。

Amazon Bedrock、Claude Platform on AWS、Google Cloud 的 Agent Platform 和 Microsoft Foundry 上游可能在其錯誤文字中命名您的帳戶 ID、角色 ARN 和專案 ID。閘道在[操作日誌](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#logs)中記錄該完整文字。開發人員從這些上游看到的內容取決於拒絕：

* Anthropic 標準錯誤信封中的 `400` 或 `413`：上游自己的訊息，例如 `prompt is too long`。Claude Platform on AWS、Agent Platform 和 Microsoft Foundry 為模型 API 拒絕返回此信封。
* 提供者自己形狀中的 `400` 或 `413`：`capability_rejected:` token。當閘道無法分類拒絕時，`400` 上為 `upstream rejected the request`，`413` 上為 `request too large for this upstream`。
* 任何其他狀態：通用的每狀態文字，例如 `429` 上的 `upstream rate limit exceeded`。

例如，閘道將 Amazon Bedrock 的 `Input is too long for requested model.` 替換為 `capability_rejected: prompt_too_long`。Claude Code 在收到該 token 時會[自動壓縮](https://code.claude.com/docs/zh-TW/errors.md#prompt-is-too-long)，就像它對 `prompt is too long` 所做的那樣。

保持雲上游的 `400` 或 `413` 訊息，或將其替換為 `capability_rejected:` token，需要閘道 v2.1.233 或更新版本。

#### Anthropic API

最小的 Anthropic 上游是來自 [Claude Console](https://platform.claude.com) 的 API 金鑰：

```yaml theme={null}
upstreams:
  - provider: anthropic
    auth:
      api_key: ${ANTHROPIC_API_KEY}
    # 或 OAuth 持有人 token（例如工作負載身分識別聯合交換的 token）：
    #   oauth_token: ${file:/var/run/secrets/anthropic-oauth-token}
    # base_url: https://api.anthropic.com   # 預設；覆寫以使用轉發代理伺服器
```

兩種憑證形式在它們傳送的標頭中有所不同：

* **`api_key`**：傳送 `x-api-key`。在 Claude Console 中輪換它並更新環境變數。
* **`oauth_token`**：傳送 `Authorization: Bearer`。當您的組織發出短期 token 而不是長期 API 金鑰時使用持有人形式。持有人 token 在啟動時讀取一次，因此透過重新掛載祕密和重新啟動來重新整理。

除了靜態金鑰或持有人 token，您可以使用工作負載身分識別聯合。按照[工作負載身分識別聯合指南](https://platform.claude.com/docs/en/manage-claude/workload-identity-federation)建立聯合規則，然後將您的工作負載的 OIDC JWT 掛載為檔案，例如 Kubernetes 投影服務帳戶 token 或 CI 平台的 id-token。閘道將 JWT 交換為短期持有人 token 並自動重新整理它。token 檔案在每次交換時重新讀取，因此輪換的投影 token 無需重新啟動即可被拾取。

```yaml theme={null}
upstreams:
  - provider: anthropic
    auth:
      federation_rule_id: ${ANTHROPIC_FEDERATION_RULE_ID}
      organization_id: ${ANTHROPIC_ORGANIZATION_ID}
      identity_token_file: /var/run/secrets/anthropic/id-token
      # workspace_id: wrkspc_...       # 如果規則涵蓋 >1 個工作區，則為必需
      # service_account_id: svac_...   # 選用的預期目標檢查
```

##### 針對您執行的代理伺服器的每個使用者身分識別標頭

您可以將 `provider: anthropic` 上游的 `base_url` 指向您執行的代理伺服器，而不是 Anthropic API。若要告訴該代理伺服器哪個開發人員傳送了每個請求，請在該上游上設定 `forward_user_identity: true`。代理伺服器然後可以按開發人員歸因支出。需要在閘道伺服器上執行 Claude Code v2.1.233 或更新版本。

例如，對於位於 `upstream-gateway.internal.example.com` 的代理伺服器：

```yaml theme={null}
upstreams:
  - provider: anthropic
    base_url: https://upstream-gateway.internal.example.com
    auth:
      api_key: ${PROXY_KEY}
    forward_user_identity: true        # default false
```

閘道將這些標頭新增到它轉發到該上游的每個請求。

| 標頭 | 值 |
| - | - |
| `x-litellm-end-user-id` | 開發人員的電子郵件，當 IdP 提供時。 |
| `x-claude-gateway-user-id` | 開發人員的 IdP 主體，來自 token 的 `sub` 宣告。 |
| `x-claude-gateway-user-email` | 開發人員的電子郵件，當 IdP 提供時。 |

當 IdP token 不攜帶電子郵件時，閘道僅傳送 `x-claude-gateway-user-id` 並省略兩個電子郵件標頭。如果您的 IdP 將電子郵件放在不同的宣告中，請將 [`oidc.email_claim`](#oidc) 設定為該宣告。

您的代理伺服器不會收到 Claude Code 傳送的 [`x-claude-code-*` 標頭](https://code.claude.com/docs/zh-TW/llm-gateway-protocol#request-headers)，例如 `x-claude-code-session-id`。閘道不會將它們傳遞給任何上游，因此請使用上表中的標頭依開發人員將請求分組。

當您的代理伺服器對攜帶開發人員電子郵件的請求答覆 `429` 時，閘道將該回應原樣返回給開發人員，而不是故障轉移到下一個上游，因此您的代理伺服器的每個使用者預算或速率限制得以維持。代理伺服器的其他回應遵循一般的[故障轉移規則](#upstreams)。如果開發人員的 IdP token 不攜帶電子郵件，閘道轉發其請求而不帶電子郵件標頭，因此對其中一個請求的 `429` 計為上游容量並故障轉移。在閘道伺服器上的 v2.1.267 之前，每個 `429` 都故障轉移。

僅在 `base_url` 是您操作的代理伺服器的上游上設定 `forward_user_identity`。閘道將開發人員電子郵件傳送到該 `base_url` 命名的任何伺服器。如果 `base_url` 是 Anthropic API（預設），閘道拒絕啟動。

> [!NOTE]
>
> 如果您在 Amazon Bedrock 上游上設定 `forward_user_identity`，閘道會在啟動時以 `Unrecognized key(s) in object: 'forward_user_identity'` 結束。如果您的代理伺服器位於 Bedrock 前面，請改為將其列為 `provider: anthropic` 上游。閘道會以 Anthropic Messages 格式傳送請求給該上游，因此您的代理伺服器必須[為 Bedrock 轉譯請求](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md#format-mismatch-with-the-upstream)。若要改為向 AWS 指明每位開發人員，請參閱[每個開發人員 AWS 成本歸因](#per-developer-aws-cost-attribution)。

#### Amazon Bedrock

對於閘道替換或前置的用戶端 Amazon Bedrock 部署，請參閱 [Claude Code on Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md)。閘道端上游：

```yaml theme={null}
upstreams:
  - provider: bedrock
    region: us-east-1
    auth: {}                           # preferred: AWS default credential chain
    # OR explicit credentials:
    # auth:
    #   aws_access_key_id: ${AWS_AKID}
    #   aws_secret_access_key: ${AWS_SK}
    #   aws_session_token: ${AWS_ST}
    # OR a Bedrock API bearer token:
    # auth:
    #   aws_bearer_token: ${AWS_BEARER_TOKEN}
    # Override the bedrock-runtime endpoint for FIPS or VPC-endpoint deployments:
    # base_url: https://bedrock-runtime-fips.us-east-1.amazonaws.com
```

空的 `auth` 區塊使用 AWS SDK 的預設憑證鏈：環境變數、`~/.aws/credentials`、ECS 任務角色、EC2 執行個體中繼資料或 EKS 上的 IRSA。在生產環境中，給予閘道 Pod 一個 IAM 角色，而不是在容器映像中嵌入靜態金鑰。

明確憑證必須完整：當 `aws_access_key_id` 和 `aws_secret_access_key` 未一起設定時，或當 `aws_session_token` 在沒有它們的情況下設定時，閘道在啟動時失敗。在 v2.1.207 之前，部分 `auth:` 區塊會通過驗證。

| 設定 | 方式 |
| - | - |
| IAM 權限 | 在推論設定檔 ARN 和底層基礎模型 ARN 上授予閘道的主體 `bedrock:InvokeModel` 和 `bedrock:InvokeModelWithResponseStream`。對於美國地區的內建目錄：`arn:aws:bedrock:<region>:<account>:inference-profile/us.anthropic.*` 和 `arn:aws:bedrock:*::foundation-model/anthropic.*`。也授予基礎模型 ARN 上的 `bedrock:CountTokens`。閘道使用它（免費）來計算用戶端放棄的請求的輸入 token，因此[支出限制](#admin)保持準確。沒有它，閘道會改用一個 token 的 Bedrock 請求來取得該計數。 |
| 模型存取 | Amazon Bedrock 在商業地區預設啟用模型存取。剩餘的帳戶級閘控是 Anthropic 的一次性使用案例表單：如果您的 AWS 帳戶中沒有人提交過，請開啟 Amazon Bedrock 主控台，從模型目錄中選擇 Anthropic 模型，並完成表單。請參閱[提交使用案例詳細資訊](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#1-submit-use-case-details)以了解 AWS Organizations 表單和提交者需要的權限。 |
| EKS (IRSA) | 建立具有上述原則和針對您叢集的 OIDC 提供者的信任原則的 IAM 角色，範圍限於閘道的服務帳戶。使用 `eks.amazonaws.com/role-arn: arn:aws:iam::<acct>:role/claude-gateway` 註釋服務帳戶。`auth: {}` 會拾取它。 |
| ECS / EC2 | 將 IAM 角色附加到任務定義或執行個體設定檔。`auth: {}` 會拾取它。 |
| 其他任何地方 | 透過 `AWS_ACCESS_KEY_ID`、`AWS_SECRET_ACCESS_KEY` 和 `AWS_SESSION_TOKEN` 環境變數傳遞憑證，或在 `auth:` 中使用 `${VAR}` 擴展明確設定它們 |
| 地區 | `region:` 是 API 端點地區。跨地區推論設定檔無論您選擇哪一個，都會跨地理位置 (US、EU、APAC) 路由。對於非美國地區或佈建輸送量 ARN，新增具有正確每上游 ID 的 [`models:`](#models) 區塊。 |

##### 應用 Amazon Bedrock 防護欄

若要將 Amazon Bedrock 防護欄應用於閘道透過 Bedrock 上游傳送的每個推論請求，請將 `guardrail` 區塊新增到該上游。需要閘道伺服器上的 Claude Code v2.1.281 或更新版本。

```yaml theme={null}
upstreams:
  - provider: bedrock
    region: us-east-1
    auth: {}
    guardrail:
      id: gr-abc123                    # guardrail ID or full ARN
      version: "1"                     # a published version number, or DRAFT
 # keep the quotes: a bare 1 fails at boot
```

也將該防護欄上的 `bedrock:ApplyGuardrail` 授予簽署此上游請求的主體：閘道的 AWS 主體，或使用 [`assume_role`](#bedrock-in-another-aws-account) 時 `role_arn` 中命名的角色。

在每個 `bedrock` 上游上都設定 `guardrail`，或都不設定。閘道在混合設定時拒絕啟動，因為[故障轉移](#multiple-upstreams)可能會將請求傳送到沒有防護欄的 Bedrock 上游。

防護欄僅涵蓋 Bedrock 上游。如果您在 `upstreams` 中列出另一個提供者，閘道將請求傳送到該提供者而不帶防護欄；如果該提供者是 [`mantle`](#amazon-bedrock-mantle-endpoint)，則閘道拒絕啟動。

當 `/v1/messages` 請求的正文攜帶 `amazon-bedrock-*` 欄位（例如 `amazon-bedrock-guardrailConfig`）到達設定了 `guardrail` 的 Bedrock 上游時，閘道答覆 400 而不是轉發它。

> [!WARNING]
>
> 閘道預設不會為提示詞加入輸入標籤，因此 Amazon Bedrock 只對已標記輸入套用的 guardrail 篩選器，不會在經由閘道的流量上執行。若要加入標籤，請設定 [`input_tagging`](#add-guardrail-input-tags)。關於哪些篩選器依賴輸入標籤，請參閱 Amazon Bedrock 文件中的[輸入標籤](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-tagging.html)。

##### 加入 guardrail 輸入標籤

若要讓閘道加入 Amazon Bedrock guardrail 之[提示詞攻擊篩選器](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-prompt-attack.html)所需的輸入標籤，請在 `guardrail` 區塊中設定 `input_tagging`，然後重新啟動閘道。請在每個 `bedrock` 上游設定相同的值，否則閘道會拒絕啟動。需要閘道伺服器上的 Claude Code v2.1.316 或更新版本。不支援此鍵之版本的閘道會在啟動時以 `Unrecognized key(s) in object: 'input_tagging'` 結束。

> [!WARNING]
>
> 根據 [Amazon Bedrock 的文件](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-tagging.html)，一旦請求帶有輸入標籤，guardrail 中的每個篩選器都會停止評估未標記的內容。在開發者使用的閘道上設定 `input_tagging` 之前，請先在測試閘道上試用。

`input_tagging` 接受下列其中一個值：

| `input_tagging` | 閘道標記文字的位置 | guardrail 封鎖提示詞之後 |
| :- | :- | :- |
| `last_message` | 自 Claude 上次回覆以來的 `user` 訊息 | 在 Claude Code 中，下一個提示詞可能通過，而 Claude 隨後會在對話中收到被封鎖的提示詞 |
| `user_messages` | `user` 訊息 | 工作階段中後續的提示詞也可能被封鎖，直到開發者移除被封鎖的提示詞為止 |
| `all_messages` | `user` 與 `assistant` 訊息 | 與 `user_messages` 相同 |
| `all_messages_and_system` | 系統提示詞與每則訊息，包括[對話中途的系統訊息](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md#feature-pass-through) | 與 `user_messages` 相同 |

採用 `last_message` 時，若自 Claude 上次回覆以來的 `user` 訊息中沒有可標記的文字，閘道會改為標記自該回覆以來的對話中途系統訊息。工具呼叫也算是一次回覆。

Amazon Bedrock 對提示詞攻擊篩選器的建議是[標記使用者輸入，以排除系統提示詞](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-prompt-attack.html)。若您設定 `all_messages_and_system`，會標記 Claude Code 自身系統提示詞的篩選器可能會封鎖請求。

下列範例會標記每則 `user` 訊息中的文字：

```yaml theme={null}
upstreams:
  - provider: bedrock
    region: us-east-1
    auth: {}
    guardrail:
      id: gr-abc123
      version: "1"
      input_tagging: user_messages
```

`user` 訊息也可能包含 Claude Code 加入的文字，例如[系統提醒](https://code.claude.com/docs/zh-TW/glossary.md#system-reminder)，因此請在測試閘道上確認一般請求不會被封鎖。

在 Anthropic 的測試中，已標記的工作階段在各提示詞之間保留了[提示快取](https://code.claude.com/docs/zh-TW/prompt-caching.md)讀取，且標籤沒有增加任何輸入 token。

##### 輸入標籤未涵蓋的內容

沒有任何 `input_tagging` 值能阻止刻意將文字放在無標籤位置的開發者。請勿期待 guardrail 會評估請求的下列部分：

* **閘道不會標記的內容**：您的 `input_tagging` 值所排除的訊息、工具定義、工具呼叫輸入、圖片與 PDF 等。除非您設定 `all_messages_and_system`，否則系統提示詞也不會被標記。
* **工具結果**：這些是 Claude 的工具所回傳的內容，例如檔案內容與網頁。在 Anthropic 的測試中，無論有無標籤，字詞篩選器都不會評估它們。

若您的 AWS 帳戶或組織強制執行 guardrail，關於該 guardrail 如何處理輸入標籤，請參閱 [Amazon Bedrock 的文件](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-enforcements.html)。

##### 記錄觸發了哪個 guardrail 篩選器

若要找出是哪個 Amazon Bedrock guardrail 篩選器封鎖了開發人員的請求，請在 Bedrock 上游設定 `guardrail_trace: true`、重新啟動閘道，並請開發人員再次傳送請求。然後在[稽核日誌](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#logs)中找到該請求的 `guardrail.trace` 事件。閘道伺服器需要 Claude Code v2.1.314 或更新版本。較早的閘道發現 `guardrail_trace` 時會拒絕啟動。

```yaml theme={null}
upstreams:
  - provider: bedrock
    region: us-east-1
    auth: {}
    guardrail:
      id: gr-abc123
      version: "1"
    guardrail_trace: true              # default false; beside guardrail, not inside it
```

當篩選器觸發或 guardrail 的動作為 `INTERVENED` 時，閘道會寫入一個不含相符文字的 `guardrail.trace` 事件。請依 `email` 或 `sub` 找出開發人員的事件。一個串流請求可能產生多個事件，其中一個可能具有空的 `filters` 清單，因此請讀取具有相同 `request_id` 的每個事件：

| 欄位 | 內容 |
| - | - |
| `request_id` | 請求的 ID |
| `sub`, `email` | 開發人員的使用者 ID 與電子郵件 |
| `upstream` | 回覆來自的上游 |
| `action` | guardrail 的動作，例如 `INTERVENED` |
| `filters` | 觸發的篩選器。AWS 未傳送篩選器詳細資料時，清單為空 |
| `filters[].side` | `input` 或 `output` |
| `filters[].guardrail` | guardrail 的 ID |
| `filters[].policy` | Bedrock 政策與清單，例如 `contentPolicy.filters` 或 `sensitiveInformationPolicy.piiEntities` |
| 其他 `filters[]` 欄位 | 項目也可能帶有 `action`、`name`、`type`、`confidence`、`filterStrength`、`score` 與 `threshold` 等欄位 |

事件不包含篩選器比對到的文字，包括 Bedrock 追蹤中的 `match` 欄位。開發人員不會收到 Bedrock 的追蹤資料，因為閘道會從每個回覆中移除它，無論是否為串流。

若用戶端在 `/v1/messages` 請求內容中傳送 `amazon-bedrock-*` 欄位，閘道會在設定了 `guardrail_trace` 的上游上回應 400。

##### 另一個 AWS 帳戶中的 Bedrock

在 Bedrock 上游上設定 `assume_role`，閘道僅使用其自己的 AWS 身分識別來呼叫您命名的角色上的 `sts:AssumeRole`，該角色可以在與閘道不同的 AWS 帳戶中。該上游的每個 Bedrock 請求都使用 STS 返回的一小時憑證簽署，因此沒有長期存取金鑰跨帳戶。

需要執行 Claude Code v2.1.281 或更新版本的閘道。較早的閘道在找到此鍵時拒絕啟動。

```yaml theme={null}
upstreams:
  - name: bedrock-isolated
    provider: bedrock
    region: us-east-1
    auth: {}                           # the gateway's own role: it only calls STS
    assume_role:
      role_arn: arn:aws:iam::222222222222:role/claude-gateway-bedrock
      # external_id: ${BEDROCK_ROLE_EXTERNAL_ID}   # when the role's trust policy requires one
```

`assume_role` 區塊採用三個鍵：

| 鍵 | 意義 |
| - | - |
| `role_arn` | 閘道擔任的 IAM 角色，作為 `arn:aws:iam::` 或 `arn:aws-us-gov:iam::` ARN。給予它此上游需要的 [Bedrock 權限](#amazon-bedrock)，包括 `bedrock:CountTokens`，以及當上游設定 `guardrail` 時的 `bedrock:ApplyGuardrail`。 |
| `external_id` | 選用。在每個 `sts:AssumeRole` 呼叫上傳送為外部 ID。當角色的信任原則需要時設定它，如果它全是數字則加上引號。 |
| `session_name` | 選用。`email` 或 `sub` 給每個開發人員自己的工作階段：請參閱[每個開發人員 AWS 成本歸因](#per-developer-aws-cost-attribution)。未設定時，每個請求使用一個名為 `claude-apps-gateway` 的工作階段。 |

角色的信任原則命名閘道自己的主體，例如其 IRSA 或 ECS 任務角色。該主體需要角色上的 `sts:AssumeRole`，自身不需要任何 Bedrock 權限。如果您未設定 `external_id`，請刪除 `Condition`。

```json theme={null}
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "AWS": "arn:aws:iam::111111111111:role/claude-gateway" },
    "Action": "sts:AssumeRole",
    "Condition": { "StringEquals": { "sts:ExternalId": "your-external-id" } }
  }]
}
```

* 如果 STS 拒絕或無法到達，閘道不會使用上游自己的憑證傳送請求。它記錄 STS 錯誤以及要檢查的內容，然後嘗試您列出的下一個上游。[上游錯誤訊息](#upstream-error-messages)涵蓋當沒有上游成功時用戶端接收的內容。沒有 `assume_role` 的稍後上游會使用其自己的憑證服務請求，因此僅在這是您想要的情況下才列出這樣的上游。
* 閘道呼叫區域 STS 端點 `sts.<region>.amazonaws.com`，其網路必須能到達。對於 FIPS 端點，在閘道的環境中設定 `AWS_USE_FIPS_ENDPOINT=true`，而不是在 AWS 設定檔中設定 `use_fips_endpoint`。
* `assume_role` 需要 SigV4 來源憑證：若它與 `aws_bearer_token` 同時設定，閘道會拒絕啟動。
* 若沒有 [`groups` 清單](#send-each-team-to-its-own-upstream)，閘道允許的每位開發人員都可以使用此上游。若要限制開發人員可使用的模型，請在 [`managed`](#managed) 政策中設定 `availableModels`。
* 若要讓透過該角色提供的模型不會同時由另一個帳戶提供，請為其指定一個自訂 id，且其 `upstream_model` 對應只包含此上游的名稱。對於這樣的 id，閘道會略過所有其他上游，因此無論是請求本身，還是中止請求的 token 計數，都不會容錯移轉到另一個帳戶。
* 對內建模型名稱的請求仍可能[送達此上游](#multiple-upstreams)，且閘道會以同一角色簽署。除非其帳戶也應提供這些模型，否則請將此上游列在最後。

此範例給一個模型一個僅由隔離上游服務的自訂 id：

```yaml theme={null}
models:
  - id: restricted-claude-opus-4-8      # a custom id, not a built-in model name
    upstream_model:
      bedrock-isolated: us.anthropic.claude-opus-4-8   # the only upstream that serves it
```

##### 每個開發人員 AWS 成本歸因

預設情況下，閘道使用一個憑證簽署每個 Bedrock 請求，因此 AWS 在單個 IAM 主體下看到所有開發人員的請求。將 `session_name: email` 新增到 [`assume_role`](#bedrock-in-another-aws-account)，閘道會為每個開發人員每小時呼叫一次 `sts:AssumeRole`，工作階段名稱設定為該開發人員的電子郵件，並使用返回的憑證簽署其請求，因此每個開發人員的請求以其自己的擔任角色工作階段到達 AWS。角色可以在閘道自己的帳戶中。

需要執行 Claude Code v2.1.281 或更新版本的閘道。[AWS 上的成本歸因](https://code.claude.com/docs/zh-TW/claude-apps-gateway-on-aws.md#cost-attribution)涵蓋 IAM 角色以及 AWS 計費顯示工作階段的位置。

```yaml theme={null}
upstreams:
  - provider: bedrock
    region: us-east-1
    auth: {}                           # the gateway's own role: it only calls STS
    assume_role:
      role_arn: arn:aws:iam::123456789012:role/claude-gateway-bedrock-user
      session_name: email              # or sub
```

`session_name` 選擇哪個已驗證宣告成為 AWS `RoleSessionName`：`email` 或 `sub`。閘道將 ASCII 字母、數字和 `_+,.@-` 以外的任何字元寫成 `=XX` 十六進位（每 UTF-8 位元組），並將長於 64 字元的結果縮短為前置詞加雜湊，因此每個開發人員的工作階段名稱保持有效且唯一。來自 token 缺少該宣告的開發人員的請求不會透過此上游傳送，操作員日誌會提示切換到 `sub` 或設定 [`oidc.email_claim`](#oidc)。

一位活躍開發人員每小時在每個閘道副本上花費一個 STS 呼叫，且並行的首次請求共享一個呼叫。

閘道也在此角色上進行一個自己的呼叫：用戶端放棄的請求的 token 計數，以使[支出限制](https://code.claude.com/docs/zh-TW/claude-apps-gateway-spend-limits.md)保持準確。該計數及其[一個 token 的備援請求](#amazon-bedrock)由共享的 `claude-apps-gateway` 工作階段簽署，因此 AWS 將該備援請求歸因於 `claude-apps-gateway` 而不是開發人員。

對於嚴格的每個開發人員歸因，在您列出的每個 Bedrock 上游上設定 `assume_role` 與 `session_name`。沒有它的上游使用其自己的憑證簽署它服務的請求。

#### Amazon Bedrock Mantle 端點

`mantle` 提供者將推論傳送到 Amazon Bedrock 的 [Mantle 端點](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#use-the-mantle-endpoint)。它需要閘道伺服器上的 Claude Code v2.1.283 或更新版本。較早的閘道版本會在啟動時拒絕它，因此請在新增之前升級每個副本。

下面的範例將 Mantle 放在第一位，其後接一個 Amazon Bedrock 上游，以服務 `models` 欄位未列出的每個模型：

```yaml theme={null}
upstreams:
  - provider: mantle
    region: us-east-1
    models: [claude-opus-4-7, claude-haiku-4-5]   # required
    auth: {}                           # AWS default credential chain
  - provider: bedrock
    region: us-east-1
    auth: {}
```

下表列出 `mantle` 上游特有的欄位。

| 欄位 | 必需 | 說明 |
| - | - | - |
| `region` | 是 | AWS 地區。閘道將端點衍生為 `https://bedrock-mantle.<region>.api.aws/anthropic`。 |
| `models` | 是 | 您的 AWS 帳戶在 Mantle 上已獲授權的模型，以用戶端傳送的名稱命名，例如 `claude-haiku-4-5`。只有這些模型會送往此上游，其他每個模型都會跳到下一個上游。 |
| `auth` | 否 | 採用與 [Amazon Bedrock](#amazon-bedrock) 上游的 `auth` 區塊相同的鍵，並遵循相同規則。 |
| `assume_role` | 否 | 此上游的請求所經由的角色，鍵與[在 `bedrock` 上游上](#bedrock-in-another-aws-account)相同，包括用於[個別開發人員歸屬](#per-developer-aws-cost-attribution)的 `session_name`。請授與該角色 Mantle 的 IAM 動作。閘道需執行 Claude Code v2.1.318 或更新版本。較早的閘道會在啟動時以 `Unrecognized key(s) in object: 'assume_role'` 結束。 |
| `base_url` | 否 | 覆寫衍生的端點。請在結尾保留 `/anthropic` 路徑。 |

授予上游的 AWS 身分識別 Mantle 自己用於推論和 token 計數的 IAM 動作，這些動作列於[使用 Mantle 端點](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#use-the-mantle-endpoint)中。

對於閘道不認識的 Mantle 模型 ID，請在頂層 [`models:`](#models) 區塊中新增一個項目，其 `upstream_model` 將此上游的名稱對應到該 ID。然後也將該項目的 `id` 放入此上游的 `models` 欄位。

`bedrock` 上游的 `guardrail` 和 `assume_role` 設定不會延伸到 Mantle 服務的請求：

* **`guardrail`**：閘道不對其傳送到 Mantle 的請求套用任何 [Bedrock 防護欄](#apply-an-amazon-bedrock-guardrail)，因此當列出 `mantle` 上游且任何 `bedrock` 上游設定了 `guardrail` 時，閘道拒絕啟動。
* **`assume_role`**：請在 `mantle` 上游本身設定。若未設定，Mantle 處理的請求會以 `mantle` 上游自身的 `auth` 憑證傳送。

關於 Mantle 自己的錯誤回應的意義，請參閱 [Mantle 端點錯誤](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#mantle-endpoint-errors)。

#### Claude Platform on AWS

Claude Platform on AWS 在 AWS 基礎設施上於 `aws-external-anthropic.<region>.api.aws` 服務第一方 Anthropic API。它使用第一方模型 ID，按原樣接受 `anthropic-beta` 標頭，並服務 `count_tokens`，因此 Bedrock 特定的轉譯都不適用。`anthropicAws` 提供者需要 Claude Code v2.1.198 或更新版本；較早的閘道版本在啟動時拒絕它。

對於相同平台的用戶端部署，請參閱 [Claude Code on Claude Platform on AWS](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md)。閘道端上游：

```yaml theme={null}
upstreams:
  - provider: anthropicAws
    region: us-east-1
    workspace_id: wrkspc_...
    auth:
      api_key: ${ANTHROPIC_AWS_API_KEY}   # sent as x-api-key
    # OR SigV4 via the AWS default credential chain:
    # auth: {}
    # OR explicit SigV4 credentials:
    # auth:
    #   aws_access_key_id: ${AWS_ACCESS_KEY_ID}
    #   aws_secret_access_key: ${AWS_SECRET_ACCESS_KEY}
    # Override the derived endpoint:
    # base_url: https://aws-external-anthropic.us-east-1.api.aws
```

該平台在與 Amazon Bedrock 不同的 AWS 帳戶中執行，並為其自己的服務名稱 `aws-external-anthropic` 簽署 SigV4 請求，因此 Bedrock 範圍的 IAM 角色不會授權它。`auth.api_key` 中的 API 金鑰在同時設定 SigV4 憑證時優先。空的 `auth` 區塊使用 AWS SDK 的預設憑證鏈，與 [Amazon Bedrock](#amazon-bedrock) 上游使用的相同鏈。

| 欄位 | 必需 | 說明 |
| - | - | - |
| `region` | 是 | AWS 地區，小寫字母、數字和連字號。閘道將端點衍生為 `https://aws-external-anthropic.<region>.api.aws`。 |
| `workspace_id` | 是 | 在每個請求上傳送為標頭；平台需要它 |
| `auth.api_key` | 否 | 平台的 API 金鑰，作為 `x-api-key` 傳送。不是持有人 token：兩種驗證模式是 API 金鑰或 SigV4。 |
| `auth.aws_access_key_id` / `auth.aws_secret_access_key` | 否 | 明確的 SigV4 憑證。設定其中一個而不設定另一個在啟動時失敗。`auth.aws_session_token` 可與它們一起使用。 |
| `base_url` | 否 | 覆寫衍生的端點 |

因為平台解析第一方模型 ID，內建目錄無需 [`models:`](#models) 區塊即可路由到它。當您策劃 `models:` 清單時，使用第一方 ID 作為 `anthropicAws:` 項目的值。

#### Google Cloud Agent Platform

對於等效的用戶端設定，請參閱 [Claude Code on Google Cloud](https://code.claude.com/docs/zh-TW/google-vertex-ai.md)。閘道端上游：

```yaml theme={null}
upstreams:
  - provider: vertex
    region: us-east5
    project_id: example-prod
    auth: {}                           # preferred: Application Default Credentials
    # OR a service account key file:
    # auth: { service_account_json: /secrets/sa.json }
    # Override the aiplatform endpoint for Private Service Connect:
    # base_url: https://us-east5-aiplatform.p.googleapis.com
```

空的 `auth` 區塊使用應用程式預設憑證：`GOOGLE_APPLICATION_CREDENTIALS`、GCE 中繼資料或 GKE 工作負載身分識別。支援服務帳戶 JSON 金鑰檔案但不建議；請使用工作負載身分識別或將服務帳戶附加到 GCE 或 Cloud Run 執行個體。

設定 `region: global` 以使用 [Google Cloud 的 Agent Platform 全域端點](https://cloud.google.com/vertex-ai/generative-ai/docs/learn/locations)而不是區域端點。Google 然後將每個請求路由到可用的地區，因此您不需追蹤每個地區的模型可用性。設定特定地區會將每個請求固定到該地區。

| 設定 | 方式 |
| - | - |
| IAM 權限 | 授予閘道的服務帳戶在專案上的 `roles/aiplatform.user`，或具有 `aiplatform.endpoints.predict` 的自訂角色。啟用 Google Cloud 的 Agent Platform API (`aiplatform.googleapis.com`)。 |
| 模型存取 | 在 Model Garden 中，為您的專案啟用 Claude 模型。它們發佈到特定地區；檢查模型卡以了解支援的地區。 |
| GKE (工作負載身分識別) | 將 GCP 服務帳戶繫結到閘道的 Kubernetes 服務帳戶，並使用 `iam.gke.io/gcp-service-account: claude-gateway@<proj>.iam.gserviceaccount.com` 註釋 KSA。`auth: {}` 會拾取它。 |
| Cloud Run / GCE | 將服務的服務帳戶設定為具有 `roles/aiplatform.user` 的帳戶。`auth: {}` 會拾取它。 |
| 其他任何地方 | `auth: { service_account_json: /secrets/sa.json }`，掛載為祕密的 JSON 金鑰檔案的路徑。該欄位採用檔案路徑，而不是金鑰內容，因此不涉及 `${file:…}` 擴展。 |

#### Microsoft Foundry

對於用戶端 Microsoft Foundry 部署，請參閱 [Claude Code on Microsoft Foundry](https://code.claude.com/docs/zh-TW/microsoft-foundry.md)。閘道端上游：

```yaml theme={null}
upstreams:
  - provider: foundry
    resource: example-foundry              # https://example-foundry.services.ai.azure.com
    auth: { use_azure_ad: true }        # preferred: DefaultAzureCredential / Managed Identity
    # OR an API key:
    # auth:
    #   api_key: ${FOUNDRY_API_KEY}
```

`use_azure_ad: true` 透過 `DefaultAzureCredential` 解析：AKS、ACI 或 App Service 上的受管身分識別；Azure CLI；或環境憑證。API 金鑰有效但是專案範圍的，且不會自動輪換。Microsoft Foundry 的端點衍生自 `resource:`；設定選用的 `base_url` 以針對主權雲（例如 Azure Government）覆寫它。

| 設定 | 方式 |
| - | - |
| RBAC | 授予閘道的身分識別在 Microsoft Foundry 資源上的 `Azure AI User` 或 `Cognitive Services User` |
| 部署 | Microsoft Foundry 使用管理員選擇的部署名稱，而不是規範模型 ID。新增 [`models:`](#models) 區塊，將每個規範 ID 對應到您的部署名稱。 |
| AKS (工作負載身分識別) | 將使用者指派的受管身分識別與叢集的 OIDC 簽發者聯合，並將其繫結到閘道的服務帳戶。`use_azure_ad: true` 透過 `WorkloadIdentityCredential` 拾取它。 |
| ACI / App Service | 在資源上啟用系統指派或使用者指派的受管身分識別。`use_azure_ad: true` 會拾取它。 |
| 其他任何地方 | `auth: { api_key: "${FOUNDRY_API_KEY}" }`。在 `{ }` 內為 `${…}` 加上引號。 |

#### 上游請求上的靜態標頭

若要將固定標頭新增到閘道傳送到某一個上游的請求，請在該上游上設定 `headers:`。當您在提供者前面執行的代理伺服器透過標頭路由或歸因流量時使用它。

`headers:` 需要閘道伺服器上的 Claude Code v2.1.277 或更新版本。較早的閘道在找到此鍵時拒絕啟動。在新增此鍵之前升級每個副本，並在回滾到較早版本之前移除此鍵。

標頭會送往 `base_url` 命名的伺服器，或當 `base_url` 未設定時送往提供者自己的端點。提供者也會收到它們，除非您的代理伺服器移除它們。

此範例透過位於 `upstream-proxy.internal.example.com` 的代理伺服器到達 `provider: vertex` 上游。它設定代理伺服器讀取的 `x-source` 標頭，並將來自 `PROXY_TOKEN` 環境變數的 token 作為 `x-proxy-token` 傳送：

```yaml theme={null}
upstreams:
  - provider: vertex
    region: us-east5
    project_id: example-prod
    base_url: https://upstream-proxy.internal.example.com
    auth: {}
    headers:
      x-source: claude-apps-gateway
      x-proxy-token: ${PROXY_TOKEN}
```

值是可列印的 ASCII 文字，兩端沒有空格。為數字、`true` 或 `false` 加上引號，以便 YAML 將其讀取為文字。

若要將祕密保持在設定檔之外，請使用[祕密擴展](#secret-expansion)，透過 `${VAR}` 從環境變數或透過 `${file:/path}` 從檔案載入值。解析為空值的 `${VAR}` 會使閘道無法啟動。

`headers:` 適用於每個提供者，且每個上游僅傳送自己的標頭。

並非閘道傳送到上游的每個請求都攜帶它們：

| 閘道傳送到此上游的請求 | 攜帶 `headers:` |
| - | - |
| `/v1/messages`（串流或非串流），以及 `/v1/messages/count_tokens` | 是 |
| 從另一個上游故障轉移而來的請求 | 是，僅此上游的 `headers:` |
| Amazon Bedrock 針對用戶端放棄的請求進行的 `CountTokens` 呼叫 | 否 |
| Workload Identity Federation token 交換 | 否 |

在使用 AWS SigV4 簽署請求的 Amazon Bedrock 或 Claude Platform on AWS 上游上，這些標頭是簽章的一部分，因此您的代理伺服器必須原樣傳遞它們。

如果您使用閘道保留的名稱，它會拒絕啟動，且啟動錯誤會指出該標頭。保留名稱包括：

* `authorization` 和 `x-api-key`
* `host`、`content-type` 和 `user-agent`
* 任何以 `anthropic-`、`x-goog-`、`x-amz-` 或 `x-amzn-` 開頭的名稱

#### 多個上游

相同的提供者可以出現多次，具有不同的 `name:`。這涵蓋不同的地區、透過不同憑證鏈的不同帳戶、佈建輸送量與隨需，以及跨提供者備援。

閘道按順序嘗試上游。`5xx`、`429`、`401`、`403`、`404`、逾時和遺漏端點 (`501`) 會故障轉移；其他 `4xx` 不會。

`429` 代表每個上游的容量，因此佈建輸送量 (PT) 耗盡會故障轉移到隨需。如果您在上游上設定 [`forward_user_identity: true`](#per-user-identity-headers-for-a-proxy-you-run)，對攜帶開發人員電子郵件的請求的 `429` 則是每個使用者的拒絕，不會故障轉移。

請求只會在以下情況略過某個上游：

* 該上游已失敗
* 該上游不提供所請求的模型
* 該上游的 [`groups` 清單](#send-each-team-to-its-own-upstream)未包含該開發人員

閘道不保留失敗上游的記錄，因此當上游關閉時，到達它的每個請求仍然會嘗試它，並等待它失敗後再繼續。

閘道等待回應開始的時間如下：

* **`provider: anthropic` 上游**：[`timeouts.upstream_ttfb_ms`](#http-tuning)，預設為 120 秒
* **其他提供者**：最多一小時。若要縮短串流請求的等待時間，請在閘道 v2.1.295 或更新版本上設定 `timeouts.upstream_ttfb_ms`。非串流模型請求無論如何都最多等待一小時

`404` 代表每個上游的模型可用性，因此未啟用模型的上游不會阻止清單中稍後服務它的上游。無法解析所請求模型的上游會被跳過，無需網路往返。

此範例首先路由佈建輸送量 Amazon Bedrock 配額，溢出到隨需和第二個帳戶，最後改用 Anthropic API：

```yaml theme={null}
upstreams:
  # 主要：您主區域中的佈建輸送量。
  - name: bedrock-pt
    provider: bedrock
    region: us-east-1
    auth: {}
  # 溢出：隨需跨地區。
  - name: bedrock-od
    provider: bedrock
    region: us-west-2
    auth: {}
  # 不同帳戶：透過靜態金鑰的單獨 Bedrock 配額。
  - name: bedrock-acct2
    provider: bedrock
    region: us-east-1
    auth:
      aws_access_key_id: ${ACCT2_AKID}
      aws_secret_access_key: ${ACCT2_SK}
  # 最後手段：直接 Anthropic API。
  - name: anthropic-fallback
    provider: anthropic
    auth:
      api_key: ${ANTHROPIC_API_KEY}

# 每個上游模型 ID 以上游的 `name:` 為鍵。
models:
  - id: claude-opus-4-8
    label: Claude Opus 4.8
    upstream_model:
      bedrock-pt: arn:aws:bedrock:us-east-1:111111111111:provisioned-model/abcdef
      bedrock-od: us.anthropic.claude-opus-4-8
      bedrock-acct2: us.anthropic.claude-opus-4-8
      anthropic-fallback: claude-opus-4-8
```

| 槓桿 | 方式 |
| - | - |
| 不同地區 | 每個地區一個 Amazon Bedrock 上游，每個都有自己的 `region:`。使用 [`auto_include_builtin_models: true`](#models)，跨地區推論設定檔會自動路由；對於地區固定部署，使用 `models:` 區塊。 |
| 不同帳戶 | 每個帳戶一個 Amazon Bedrock 上游。預設鏈 (`auth: {}`) 使用 Pod 的身分識別；對於第二個帳戶，新增 [`assume_role`](#bedrock-in-another-aws-account) 以透過短期憑證到達它，或在 `auth:` 中設定明確憑證或持有人 token。 |
| 不同團隊 | 為每個團隊的上游設定 `groups` 清單，讓只有這些 IdP 群組中的開發人員能存取。請參閱[將每個團隊送往各自的上游](#send-each-team-to-its-own-upstream)。 |
| 佈建輸送量 | 在 `models:` 中將該上游名稱下的模型對應到佈建輸送量 ARN。其他上游保持隨需 ID，因此 PT 容量在故障轉移前耗盡。 |
| VPC / FIPS 端點 | 在上游上將 `base_url:` 設定為您的 VPC 端點或 FIPS 端點 URL |
| 依模型範圍路由 | 自訂模型 `id`（非內建 Claude 模型者）會略過其 `upstream_model:` 對應中沒有的上游。具有 `models` 清單的上游（[`mantle` 上游](#amazon-bedrock-mantle-endpoint)必須具備此清單）只會針對這些模型進行嘗試。 |
| 內建模型路由 | 在沒有 `models` 或 `groups` 清單的上游上，閘道會依序嘗試內建模型，並在 `upstream_model:` 對應中沒有項目時使用提供者的預設 ID。對於提供者具有預設 ID 的內建模型，此對應改變的是上游收到哪個 ID，而非是否嘗試該上游。拒絕該 ID 的上游會遵循與其他上游錯誤相同的[容錯移轉規則](#upstreams)。 |

在雲提供者之間故障轉移，或故障轉移到直接 Anthropic API，會改變哪些協議、地理位置和其他條款管理該請求。

無論哪個上游服務給定請求，CLI 對閘道都應用相同的功能閘控，因此預設情況下故障轉移不會傳送上游會拒絕的正文欄位。如果您在原則中設定了[一小時快取 TTL](#one-hour-prompt-cache)，它會傳送到清單中的每個上游，因此僅在所有上游都接受它時才設定。

#### 將每個團隊送往各自的上游

若要將每個團隊的請求送往各自的 AWS 帳戶或 Google Cloud 專案，請為每個團隊列出一個上游，並為每個上游設定 `groups` 清單。只有所列 IdP 群組中的開發人員能存取該上游，無論是首次嘗試或[容錯移轉](#multiple-upstreams)時皆是如此。每個提供者都接受 `groups`。閘道伺服器需要 Claude Code v2.1.314 或更新版本。

此範例為 `payments-eng` 與 `search-eng` 群組各提供一個 AWS 帳戶，並新增一個沒有 `groups` 清單、所有開發人員皆可使用的上游：

```yaml theme={null}
upstreams:
  - name: bedrock-payments
    provider: bedrock
    region: us-east-1
    auth: {}
    assume_role:
      role_arn: arn:aws:iam::111111111111:role/claude-gateway-bedrock
    groups: [payments-eng]
  - name: bedrock-search
    provider: bedrock
    region: us-east-1
    auth: {}
    assume_role:
      role_arn: arn:aws:iam::222222222222:role/claude-gateway-bedrock
    groups: [search-eng]
  - name: bedrock-shared               # no groups: open to everyone, so listed last
    provider: bedrock
    region: us-east-1
    auth: {}
```

使用此範例設定時，每位開發人員的請求會從其所在列的第一個上游開始，並在容錯移轉時移至下一個：

| 開發人員的群組 | 上游（依序） |
| - | - |
| `payments-eng` | `bedrock-payments`，然後 `bedrock-shared` |
| `search-eng` | `bedrock-search`，然後 `bedrock-shared` |
| `payments-eng` 與 `search-eng` | `bedrock-payments`，然後 `bedrock-search`，然後 `bedrock-shared` |
| 皆非 | `bedrock-shared` |

當團隊的上游以 `403` 拒絕所請求的模型時，閘道會嘗試該團隊所在列中下一個提供該模型的上游。若要讓團隊只使用一個上游，請為每個上游設定 `groups` 清單，並確保沒有其他上游列出該團隊開發人員所屬的群組。如此一來，該團隊便沒有容錯移轉，而不屬於任何所列群組的開發人員所發出的請求會[以 `400` 失敗](#what-happens-when-a-developer-is-in-no-listed-group)。

若要讓每位開發人員抵達您預期的上游，請撰寫完全相符的項目，並將開放的上游放在最後：

* **項目**：請完全依照您的 IdP 在 [groups 宣告](#oidc)中傳送的內容撰寫每個群組，[`match.groups`](#managed) 也會讀取該宣告。閘道發現空清單或空項目時會拒絕啟動。它不會對照您的 IdP 檢查項目，因此不符合任何人的項目不會產生警告。
* **順序**：將沒有 `groups` 清單的上游放在最後。它為所有人提供服務，因此若列在較前面，會在團隊自己的上游之前接走該團隊的請求。

> [!WARNING]
>
> 早於 v2.1.314 的閘道發現 `groups` 時會拒絕啟動，因此請在新增它之前升級每個副本。
>
> 在回復之前，請移除每個具有 `groups` 清單的上游，以及每個指名它的 `upstream_model` 鍵或價格覆寫，並至少保留一個上游。若只移除 `groups` 鍵，該上游會對所有開發人員開放。仍指名已移除上游的鍵或覆寫會使閘道無法啟動，並顯示 `references unknown upstream`。

##### 當開發人員不屬於任何所列群組時會發生什麼事

若每個上游都有 `groups` 清單，不屬於任何這些群組的開發人員會看到此錯誤，且閘道不會聯絡任何提供者：

```text theme={null}
API Error: 400 you aren't in a group that can use this gateway. Ask your administrator to add you to one
```

請在您的 IdP 中將該開發人員加入所列的群組，或新增一個沒有 `groups` 清單的上游。

閘道會在每次 token 重新整理時再次讀取開發人員的群組。若您的 IdP 在重新整理時未包含群組，該開發人員便沒有任何群組：

* **已設定 [`oidc.allowed_groups`](#oidc)**：閘道會拒絕重新整理，工作階段隨即結束
* **否則，若有上游沒有 `groups` 清單**：該開發人員的請求會移至該上游
* **否則，若每個上游都有 `groups` 清單**：該開發人員的請求會以該錯誤失敗

若您 IdP 的 userinfo 端點會回傳 groups 宣告，且未設定 `oidc.google_groups`，請將 [`oidc.userinfo_fallback`](#oidc) 設為 `true`，以從該處填入群組。

## 選用區段

### `admin`

選用。啟用 `/v1/organizations/spend_limits`，其鏡像 Anthropic 的公開 Admin API，以及在 `/v1/messages` 上的每位開發者支出強制執行。請參閱[支出限制](https://code.claude.com/docs/zh-TW/claude-apps-gateway-spend-limits.md)以了解如何設定和強制執行上限；本節涵蓋啟用該功能並調整它的 `gateway.yaml` 金鑰。

```yaml theme={null}
admin:
  # 用於 admin 端點的具名靜態 API 金鑰，以 x-api-key 形式傳送。
  # id 在稽核日誌中顯示為 admin-key:<id>，因此每個金鑰都
  # 可追蹤。陣列用於輪換：新增新金鑰、滾動用戶端、
  # 移除舊金鑰。
  write_keys:
    - { id: terraform, key: "${GATEWAY_ADMIN_WRITE_KEY_TF}" }
    - { id: ci,        key: "${GATEWAY_ADMIN_WRITE_KEY_CI}" }
  read_keys:
    - { id: reporting, key: "${GATEWAY_ADMIN_READ_KEY}" }
  # 透過一般 gateway JWT（無 API 金鑰）授予完整 admin 的 IdP 群組。
  admin_groups: [platform-finops]
  blocked_message: request an increase at https://go.example.com/claude-limits
```

| 欄位 | 必需 | 說明 |
| - | - | - |
| `write_keys` | 否 | `{id, key}` 的陣列。符合其中一個的 `x-api-key` 可以列出、設定和刪除支出限制。金鑰值必須至少 32 個字元；`id` 在 `read_keys` 和 `write_keys` 中必須唯一。 |
| `read_keys` | 否 | `{id, key}` 的陣列。唯讀：每個 `GET` 端點，包括列出上限、按 ID 擷取一個，以及讀取 [`/effective`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-spend-limits#%2Feffective) 和 [`/audit`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-spend-limits#%2Faudit)。 |
| `admin_groups` | 否 | IdP 群組名稱。gateway JWT 的 `groups` 聲明包含其中一個的具有完整 admin 存取權（讀取和寫入），並稽核為 `oidc:<sub>`。將此用於人類 admin；將 API 金鑰用於機器。此清單中的空項目會在啟動時停止 gateway。請參閱[在啟動時停止 gateway 的 matcher 值](#matcher-values-that-stop-the-gateway-at-boot)。 |
| `blocked_message` | 否 | 逐字附加到被阻止的開發者看到的 `429 billing_error`。寫入完整指示，例如 URL 或 Slack 頻道。未設定時，gateway 只傳送預設訊息。請參閱[強制執行如何運作](https://code.claude.com/docs/zh-TW/claude-apps-gateway-spend-limits.md#how-enforcement-works)。 |
| `audit_retention_days` | 否 | 預設 `365`。較舊的 `admin_audit` 列會被清除。 |
| `spend_retention_months` | 否 | 預設 `13`。早於此時間的 `spend` 計數器列會被清除。預設值保留完整年份加上當月部分月份，用於年度比較報告。 |
| `identity_retention_days` | 否 | 預設 `90`。`principal_emails` 列的最後一次看到 TTL，其中保存每位開發者的電子郵件、顯示名稱和群組（PII）。刻意比支出保留期短，因此已取消佈建的身分會在其匿名支出計數器保留時過期。 |
| `group_limit_mode` | 否 | `min`（預設）或 `max`。當開發者在多個具有上限的群組中時，`min` 強制執行最嚴格的，`max` 強制執行最寬鬆的。由強制執行和 `/effective` 使用。 |

### `enforcement`

`enforcement` 區塊控制當存放區不可用時支出限制檢查的行為。

| 欄位 | 必需 | 說明 |
| - | - | - |
| `fail_closed_on_error` | 否 | 預設為 `false`。Postgres 中斷時，支出強制執行會以開放方式失敗，讓推論持續運作。設為 `true` 則改為封閉式失敗：超過上限的開發人員會被封鎖，但若儲存區無法連線，其他所有人也會被封鎖。需要 [`admin:`](#admin) 區塊：支出強制執行只在設定了 `admin` 時才會執行，若您將此項設為 `true` 卻沒有該區塊，閘道會拒絕啟動。 |

### `pricing`

`pricing` 區塊告訴支出計量器要收費的金額而不是美元清單價格，因此上限和 [`/effective`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-spend-limits#%2Feffective) 反映您的合約費率。金額保持為美元，並保持為估計值，而非發票。兩個先決條件：

* gateway 伺服器上的 Claude Code v2.1.227 或更新版本。較早版本在啟動時拒絕未知金鑰。
* [`admin:`](#admin) 區塊或在 v2.1.268 或更新版本中，至少有一個原則的 [`managed:`](#managed) 區塊。gateway 會拒絕在設定 `pricing` 且沒有任何區塊的情況下啟動，因為沒有任何東西會讀取它。

```yaml theme={null}
pricing:
  multiplier: 0.85
  overrides:
    - upstream: bedrock-eu
      model: claude-sonnet-4-6
      input: 3.30
      output: 16.50
      cache_read: 0.33
      cache_write: 4.125
```

| 欄位 | 必需 | 說明 |
| - | - | - |
| `multiplier` | 否 | 預設 `1`。計量器將每個計量金額乘以此值，無論是清單價格還是覆寫，因此 `0.85` 計費 85% 的價格。必須大於 0 且最多 10，大於 1 的值是[標記價格上升](#mark-prices-up)。 |
| `overrides` | 否 | `{upstream, model, input, output, cache_read, cache_write}` 的列，單位為美元每百萬個 token。所有四個費率都是必需的。每個必須大於 0 且最多 10000。 |

計量器如何匹配覆寫列：

* 列替換 `upstream`（[`upstreams[].name`](#upstreams)）為 `model` 提供的請求的清單價格。這包括更高的[快速模式](https://code.claude.com/docs/zh-TW/fast-mode.md#understand-the-cost-tradeoff)費率，因此快速和標準請求以相同的四個費率計量。
* 內建 ID（例如 `claude-sonnet-4-6`）匹配方式類似 [`models[].id`](#models)，涵蓋計量器定價為該模型的每個日期形式、區域 Amazon Bedrock 形式或 Google Cloud 的 Agent Platform 形式。任何其他字串（例如別名或推論設定檔 ARN）匹配用戶端傳送的 ID 或上游傳送的字串，不區分大小寫。
* 當列重疊時，計量器選擇最具體的列而不是第一列：其 `model` 是上游傳送的確切模型字串的列，然後是匹配用戶端傳送的確切 ID 的列，然後是命名內建模型的列。
* 未知的上游名稱會導致啟動失敗，一個上游的兩列命名相同模型也會導致啟動失敗，包括一個內建模型的兩個拼寫。gateway 在啟動時警告沒有可請求模型可以使用的列。
* Web 搜尋請求保持在 \$0.01 清單價格；乘數仍適用於它們。

對於每個區域費率，為每個區域提供自己的具名上游和每個上游一列。

#### 標記價格上升

使用 gateway 伺服器上的 v2.1.271 或更新版本，您可以將 `multiplier` 設定為大於 1，最多 10，以計量超過提供者收費的金額，例如內部退款費率。此範例以 120% 的價格計量每個請求：

```yaml theme={null}
pricing:
  multiplier: 1.2
```

使用 [`admin:`](#admin) 區塊，標記也適用於支出限制。計量器計算 120% 的價格，因此開發者更快達到其上限。gateway 在啟動時記錄警告，說明這一點。

乘數不會改變上游提供者對請求的收費。

如果 gateway 也[將費率傳送給已登入的用戶端](#send-the-rates-to-signed-in-clients)，開發者需要 Claude Code v2.1.271 或更新版本才能看到標記。較早的用戶端忽略大於 1 的 `multiplier` 並顯示不含標記的成本。

早於 v2.1.271 的 gateway 伺服器會拒絕在您設定大於 1 的 `multiplier` 時啟動。

#### 將費率傳送給已登入的用戶端

在閘道伺服器上使用 v2.1.268 或更新版本時，閘道也會將 `pricing` 中的費率放入其提供的 [`managed`](#managed) 政策中，作為 [`modelPricing`](https://code.claude.com/docs/zh-TW/settings-reference#modelpricing) 受管設定。

與政策相符的開發人員便會在 `/usage`、狀態列和 OpenTelemetry 中看到 `pricing` 的費率。不符合任何政策的開發人員不會收到受管設定，因此其數字仍維持定價。用戶端在 Claude Code v2.1.242 或更新版本中套用此設定。

* gateway 新增的內容：除非原則的 `cli` 區塊已設定 `modelPricing`，gateway 新增 `multiplier` 和，對於用戶端可以請求的每個模型 ID，提供該 ID 的第一個上游的覆寫列。只有故障轉移上游收費的費率保持在 gateway 上。
* 具有 [`groups` 清單](#send-each-team-to-its-own-upstream)的上游：當其為提供某模型 ID 的第一個上游時，閘道不會為該 ID 新增資料列。開發人員接著會看到 Claude Code 自身對該 ID 的費率（當 Claude Code 能識別該 ID 時，即為該模型的標準費率）乘以 `multiplier`。
* 選擇一個原則退出：在該原則的 `cli` 區塊中將 `modelPricing` 設定為 `{}`，其開發者保持在清單價格。
* 保留原則自己的費率：其 `cli` 區塊使用自己的 `multiplier` 或 `overrides` 設定 `modelPricing` 的原則保留該 `modelPricing` 完整，gateway 不向其新增自己的費率。

### `models`

`models` 區塊是選用的 admin 策劃模型清單，在 `/v1/models` 提供，用於按上游轉譯模型 ID。對於非美國 Amazon Bedrock 區域、Amazon Bedrock 佈建輸送量 ARN 和 Microsoft Foundry 部署名稱是必需的。

```yaml theme={null}
auto_include_builtin_models: true   # false: expose only the list below
models:
  - id: claude-opus-4-8
    label: Claude Opus 4.8
    # description: optional text shown in clients that surface it
    upstream_model:
      anthropic: claude-opus-4-8
      bedrock: us.anthropic.claude-opus-4-8   # or an inference-profile ARN
      foundry: your-opus-deployment-name
```

`upstream_model` 下的每個金鑰必須符合已設定上游的 `name`，預設為提供者名稱。不符合任何上游的金鑰會導致啟動失敗，因此省略您不使用的提供者的列。

### `managed`

`managed` 區塊定義以 IdP 群組或電子郵件網域為鍵的角色型存取政策。政策會依序評估；預設會選取第一個符合的政策，然後合併到 `match: {}` 全包式基礎上。符合兩項角色政策的使用者只會取得第一項，因此除非您 [套用每一項符合的政策](#apply-every-matching-policy)，否則第二項政策的拒絕規則不會生效。政策會依使用者在 `GET /managed/settings` 提供，並使用 ETag/304 快取。

```yaml theme={null}
managed:
  policies:
    # 特定群組優先。
    - match: { groups: [eng-contractors] }
      cli:
        availableModels: [claude-sonnet-4-6]
        permissions: { deny: ["WebFetch", "WebSearch"] }
    # 預設全部捕捉最後：匹配每個已驗證的使用者。
    - match: {}
      cli:
        availableModels: [claude-opus-4-8, claude-sonnet-4-6, claude-haiku-4-5]
        # 讓 /model 中的 Default 選項在每個原則的
        # 清單內解析。eng-contractors 原則繼承 enforceAvailableModels。
        enforceAvailableModels: true
```

`match: {}` 全部捕捉（按慣例列在最後）被視為基礎層。每個其他原則從全部捕捉繼承它未設定的任何金鑰，因此每個角色項目只需列出與組織預設不同的內容。合併規則取決於金鑰類型：

* **允許清單**：`availableModels` 和 `permissions.allow`。特定原則的清單完全替換基礎的。
* **拒絕清單與 hook 陣列**：`permissions.deny`、`permissions.ask`、`disabledMcpjsonServers`、`deniedMcpServers`、`blockedMarketplaces`、`deniedModels`，以及每個 `hooks` 事件類型陣列。這些會取基礎與政策的聯集，因此全組織的拒絕規則或稽核 hook 不會因各角色的覆寫而被意外移除。
* **記錄類型金鑰**：`env`、`modelOverrides` 和 `skillOverrides`。這些淺合併，因此每個角色 `env` 區塊覆寫它設定的金鑰並從基礎繼承其餘的。

`availableModels` 也在 `/v1/messages` 伺服器端強制執行，因此被拒絕的模型返回 `400`，無論用戶端傳送什麼。空清單會拒絕每個模型。此檢查也涵蓋開發者選擇模型之前工作階段啟動時所使用的模型，因此請[讓工作階段從原則允許的模型啟動](#start-sessions-on-a-model-the-policy-allows)。

gateway 在轉發請求之前驗證 `model` 值本身，因此格式不正確的值永遠不會到達上游。它在兩種情況下以 `400` 拒絕請求：

* 當值缺失或為空時，gateway 以訊息 `model is required` 拒絕請求。該檢查需要執行 Claude Code v2.1.228 或更新版本的 gateway。
* 當值存在但不是字串時，gateway 以訊息 `model must be a string` 拒絕請求。需要執行 Claude Code v2.1.221 或更新版本的 gateway。

| Matcher | 行為 |
| - | - |
| `match: {}` | 匹配每個已驗證的使用者。從其中一個開始，稍後在其上方新增群組範圍的原則。 |
| `match: { groups: [a, b] }` | 如果 JWT 的 `groups` 聲明包含任何列出的群組，則匹配。區分大小寫：群組必須符合 IdP 的確切大小寫。 |
| `match: { email_domain: example.com }` | 匹配 JWT 的 `email` 聲明中最後一個 `@` 之後的部分，不區分大小寫。每個原則接受一個網域。 |
| `match: { groups: [a], email_domain: example.com }` | 兩個條件都必須匹配 |

與任何原則不匹配的已驗證使用者獲得 gateway 的預設值，這意味著目錄中的每個模型和沒有受管設定。如果您想要保證的預設原則，請在最後新增 `match: {}` 全部捕捉。

請將全組織的拒絕規則放在 `match: {}` 政策中，因為群組政策的規則只有在使用者的 token 帶有該群組時才會生效。

> [!NOTE]
>
> gateway 不保留自己的使用者目錄。它從使用者的 IdP token 授權每個請求，從 token 的 `groups` 聲明讀取群組成員資格，並根據它評估原則。沒有名冊可列舉，沒有帳戶可預先建立，因此沒有 SCIM 端點，因為沒有任何東西可供 SCIM 同步到。
>
> 在真實來源（即您的 IdP 的原生 SCIM 佈建或專用身分治理平台）執行使用者和群組生命週期管理。那裡管理的成員資格和取消佈建透過 token 自動流入 gateway。如果您想要 Claude 帳戶本身的 SCIM 佈建，那是[適用於企業的 Claude](https://code.claude.com/docs/zh-TW/admin-setup.md) 功能。
>
> 兩個傳播時鐘適用：
>
> * **原則內容**：編輯原則並重新部署在連接的 Claude Code 用戶端的下一個受管設定輪詢時到達，在一小時內，除了[只在下一次啟動時適用的變更](https://code.claude.com/docs/zh-TW/server-managed-settings.md#fetch-and-caching-behavior)
> * **群組成員資格**：變更使用者的群組成員資格會變更哪個原則匹配他們。這在下一個工作階段重新鑄造時生效，意味著下一個無聲重新整理，受 `session.ttl_hours` 限制。
>
> Claude Desktop 依循[其自己的排程](#when-a-policy-change-reaches-claude-desktop)。

#### 套用每一項符合的政策

符合多項角色政策的使用者只會取得第一項，除非您在 `policies` 旁設定 `policy_mode: layered`。使用 `layered` 時，每一項符合使用者的政策都會套用，直到第一個 `match: {}` 政策為止。

`policy_mode` 需要閘道伺服器上為 Claude Code v2.1.316 或更新版本。若閘道版本不支援此鍵，發現該鍵時會拒絕啟動。請在新增此鍵之前升級每個副本，並在回復到較早版本之前移除此鍵。此範例有一個失去 `WebFetch` 的群組，以及一個獲得 Opus 的群組：

```yaml theme={null}
managed:
  policy_mode: layered
  policies:
    - match: { groups: [no-web] }
      cli:
        permissions: { deny: ["WebFetch"] }
    - match: { groups: [opus-users] }
      cli:
        availableModels: [opus, sonnet]
    - match: {}
      cli:
        availableModels: [sonnet]
        enforceAvailableModels: true
```

下表顯示同時屬於 `no-web` 與 `opus-users` 的使用者，在預設的 `first_match` 與 `layered` 之下分別會收到什麼。

| 設定 | `first_match` | `layered` |
| - | - | - |
| `availableModels` | `sonnet` | `opus`、`sonnet` |
| `enforceAvailableModels` | `true` | `true` |
| `permissions.deny` | `WebFetch` | `WebFetch` |

閘道會將每項符合的政策合併到列在其下方的政策上，使用與基礎層相同的 [合併規則](#managed)：

* **允許清單、單一值，以及 `sandbox` 之類的區塊**：每一項都完整取自第一個設定它的符合政策（依列出順序），因此兩個群組的 `availableModels` 清單不會相加。
* **拒絕清單與 hook 陣列**：這些會在每項符合的政策之間相加，因此屬於兩個群組的使用者會取得兩個群組的拒絕規則。
* **`env`、`modelOverrides` 與 `skillOverrides`**：項目依名稱合併，第一個設定某名稱的符合政策（依列出順序）提供其值。
* **`desktop` 鍵**：這些依 [基礎 `desktop` 區塊的規則](#how-a-role-policy-inherits-the-base-desktop-block) 合併。

> [!WARNING]
>
> 多項政策加總後，可能產生比任何單一政策都更寬鬆的規則。例如，`match: {}` 政策設定 `sandbox.enabled: true`，一個群組的政策設定 `permissions.allow: ["Bash"]`，另一個群組的政策設定 `sandbox.enabled: false`。同時屬於這兩個群組的使用者，會在沙箱關閉的情況下獲得允許 `Bash`。在這種情況下，請將允許 `Bash` 的政策列在最前面，並將 `match: {}` 政策的整個 `sandbox` 區塊複製到其中。

使用 `layered` 時，閘道會在某些設定上拒絕啟動，包括以下幾項：

* **`!` 模式**：任何政策（包括 `match: {}` 政策）的 `permissions.deny` 或 `permissions.ask` 清單中，`Read` 或 `Edit` 規則裡的 [`!` 否定](https://code.claude.com/docs/zh-TW/permissions#special-characters-and-negation)
* **全包式政策以外的 hook 限制**：在 `match: {}` 以外的任何政策中設定 `disableAllHooks`、`allowedHttpHookUrls` 或 `httpHookAllowedEnvVars`

#### 讓工作階段從原則允許的模型啟動

如果 `availableModels` 未包含 Claude Code 的預設模型，工作階段會收到 `400` 回應，直到開發者選擇列出的模型（例如使用 `/model`）。在 gateway 工作階段中，預設模型是 `opus` 別名解析到的 Opus 模型，而單獨設定 `availableModels` 不會變更它。

要修正此問題，請在相同的 `cli` 區塊中設定 [`enforceAvailableModels: true`](https://code.claude.com/docs/zh-TW/model-config#enforce-the-allowlist-for-the-default-model)，然後檢查清單包含哪種項目：

* **別名（例如 `sonnet`）或內建 ID（例如 `claude-sonnet-4-6`）**：工作階段會從其中一個模型啟動，且 `/model` 中的 Default 選項會解析到該模型
* **清單中沒有別名或內建 ID**：工作階段可能仍會從內建預設模型啟動，因此也請在該原則的 `cli` 區塊中將 [`model`](https://code.claude.com/docs/zh-TW/model-config#control-the-model-users-run-on) 設定為其中一個列出的 ID

此原則列出一個由 [`models`](#models) 定義的自訂 ID，並讓工作階段從該 ID 啟動：

```yaml theme={null}
managed:
  policies:
    - match: { groups: [restricted-projects] }
      cli:
        availableModels: [restricted-claude-opus-4-8]
        enforceAvailableModels: true
        model: restricted-claude-opus-4-8
        env:
          ANTHROPIC_DEFAULT_OPUS_MODEL: restricted-claude-opus-4-8   # opus and Default resolve to the ID too
```

#### 在啟動時停止 gateway 的 matcher 值

在啟動時，gateway 檢查每個原則的 `match` 區塊和 [`admin_groups`](#admin) 清單。這些值中的任何一個都會停止 gateway，並出現命名該欄位的錯誤：

* 空的 `groups` 清單
* `groups` 或 `admin_groups` 中的空項目
* 空的 `email_domain`
* 包含 `@`、空格或逗號的 `email_domain`。gateway 修剪值並在此檢查之前移除一個前導 `@`。寫入一個裸網域，例如 `example.com`。

在 v2.1.232 之前，gateway 以這些值啟動。每個值有此效果：

* 空的 `email_domain`：gateway 跳過網域檢查，因此具有空 `email_domain` 和沒有 `groups` 清單的原則匹配每個已驗證的使用者
* 空的 `groups` 清單：原則不匹配任何人
* 包含 `@`、空格或逗號的 `email_domain`：原則不匹配任何人
* `groups` 或 `admin_groups` 中的空項目：項目只在該使用者的 IdP `groups` 聲明也包含空項目時匹配使用者。在 `admin_groups` 中，該匹配授予 admin 存取權。如果您的 `admin_groups` 清單從未包含空項目，沒有人以此方式獲得 admin 存取權。

#### 選擇 `cli` 或 `code`

> [!WARNING]
>
> 當原則使用 `code` 鍵時，下列每一項都會使閘道無法啟動：
>
> * **閘道版本**：`code` 需要閘道伺服器上為 Claude Code v2.1.296 或更新版本。較早的閘道發現此鍵時會拒絕啟動。請在加入此鍵之前升級每個副本，並在回復到較早版本之前將 `code` 改回 `cli`。
> * **混用鍵**：同時含有 `code` 與 `cli`（或其較早的寫法 `settings`）的檔案會使閘道在啟動時停止。請在一次編輯中將所有區塊放在同一個鍵下。

政策的 Claude Code 設定（例如拒絕讀取 `.env` 檔案的規則）放在 `cli` 或 `code` 鍵之下的區塊中。`code` 是建議使用的鍵，`cli` 是舊版鍵。兩個鍵接受相同的內容。鍵決定設定在哪裡執行：

* **`cli`**：終端機、VS Code 與 JetBrains 擴充功能，以及 Agent SDK。使用 `cli` 時，Claude Desktop 的 Code 分頁會取得[衍生設定](#claude-desktop-overlay)，因此像 `Read(./.env)` 這類有範圍的規則在那裡不會阻止使用者。
* **`code`**：相同的位置，並且也可以涵蓋 Claude Desktop 的 Code 分頁。

使用 `cli` 的檔案會照舊運作；若閘道在具有 [`desktop`](#claude-desktop-overlay) 鍵的政策中發現 `cli`，會在啟動時發出警告並照常啟動。請切換為 `code`，讓設定也能涵蓋 Code 分頁。

切換之前，請先閱讀[在 Code 分頁中套用 `code` 設定](#apply-code-settings-in-the-code-tab)。原則需要 `desktop` 鍵，且使用者的電腦需要先完成設定，設定才會在那裡生效，而且 Claude Desktop 中的網路搜尋會被關閉。

此原則將拒絕規則放在 `code` 下，並附上空的 `desktop` 鍵：

```yaml theme={null}
managed:
  policies:
    - match: {}
      code:
        permissions: { deny: ["Read(./.env)"] }
      desktop: {}
```

切換時，請在重新命名區塊的同一次編輯中刪除任何 `serve_to_desktop` 行。凡是說明中指名 `cli` 區塊之處，請使用您的 `code` 區塊。

`serve_to_desktop: true` 是將政策的 `cli` 設定提供給 Code 分頁的舊版方式。當 Claude Desktop 透過 [`bootstrapUrl`](#claude-desktop-overlay) 連線時，它沒有作用。當您的政策使用 `cli` 時，指出此鍵的啟動警告代表這些設定並未送達 Code 分頁：

* **若要涵蓋 Code 分頁**：在使用者的機器符合[在 Code 分頁中套用 `code` 設定](#apply-code-settings-in-the-code-tab)中的條件後，切換為 `code`
* **若要維持使用 `cli`**：在政策中於 `cli` 旁設定 `serve_to_desktop: false` 以消除警告

#### `cli` 中的內容

每個 `code` 或 `cli` 值都是一份完整的 Claude Code `managed-settings.json` 文件，與您透過 MDM 或 `/etc/claude-code/managed-settings.json` 部署的 schema 相同，只是在此以 YAML 表示。CLI 會在受管層級套用所傳送的文件，位於使用者與專案設定之上，並取代伺服器受管設定。因此它會忽略[僅限 OS 層級原則來源](https://code.claude.com/docs/zh-TW/server-managed-settings.md#current-limitations)的設定，例如 `policyHelper` 與 `wslInheritsWindowsSettings`。

gateway 在啟動時根據 CLI 的設定 schema 驗證每個文件，因此無法識別的頂層金鑰會導致啟動失敗，並出現命名每個違規金鑰的錯誤。schema 的刻意開放部分仍接受任意值，因為較新的用戶端可能識別 gateway schema 不識別的項目。這些開放金鑰包括 `env`、`pluginConfigs` 和 `permissions` 下的巢狀金鑰。

因為驗證使用與 gateway 已安裝版本捆綁的 schema，將較新 Claude Code 版本引入的頂層設定金鑰放入受管設定需要先升級 gateway。在一個用戶端上煙霧測試新原則，然後再推出。

完整金鑰參考在[Claude Code 設定](https://code.claude.com/docs/zh-TW/settings-reference.md#all-settings)中。運營者首先尋求的金鑰：

```yaml theme={null}
managed:
  policies:
    - match: {}
      cli:
        # Model access (also enforced server-side at /v1/messages)
        availableModels: [claude-opus-4-8, claude-sonnet-4-6, claude-haiku-4-5]
        enforceAvailableModels: true              # Default resolves inside the list

        # Permission policy
        permissions:
          deny:
            - "WebFetch"
            - "Read(./.env)"
            - "Read(./secrets/**)"
          disableBypassPermissionsMode: disable   # blocks --dangerously-skip-permissions
        allowManagedPermissionRulesOnly: true     # ignore user/project permission rules

        # Environment pushed into the CLI process. DISABLE_UPDATES blocks
        # background and manual updates; DISABLE_AUTOUPDATER stops only
        # background updates.
        env:
          DISABLE_UPDATES: "1"                    # pin versions via your own distribution

        # Org-wide hooks. Hook commands run on developer machines, not the
        # gateway, so the path must exist on every client OS in the policy.
        hooks:
          PostToolUse:
            - matcher: "Edit|Write"
              hooks:
                - { type: command, command: /usr/local/bin/audit-edit.sh }
```

| 金鑰 | 由以下強制執行 | 效果 |
| - | - | - |
| `availableModels` | Gateway + CLI | 模型允許清單。也在 `/v1/messages` 檢查，因此修補的用戶端無法繞過它。 |
| [`deniedModels`](https://code.claude.com/docs/zh-TW/settings-reference#deniedmodels)、[`availableModelsMatch`](https://code.claude.com/docs/zh-TW/settings-reference#availablemodelsmatch) | 閘道 + CLI | [封鎖特定模型或版本](https://code.claude.com/docs/zh-TW/model-config.md#block-specific-models-or-versions)，即使 `availableModels` 原本會允許它們。遭封鎖的模型會在 `/v1/messages` 以 `400` 拒絕，並從 `/v1/models` 中排除。閘道自身的檢查需要閘道伺服器上為 Claude Code v2.1.299 或更新版本。CLI 的檢查需要用戶端上為 v2.1.283 或更新版本，較早的用戶端會忽略這兩個鍵。 |
| `permissions.allow` / `.deny` | CLI | 工具與命令規則。請參閱[權限](https://code.claude.com/docs/zh-TW/permissions.md)與 [Bash 規則不會比對的內容](https://code.claude.com/docs/zh-TW/permissions.md#bash-rule-limits)。 |
| `permissions.disableBypassPermissionsMode` | CLI | 設定為 `disable` 以阻止 [`bypassPermissions`](https://code.claude.com/docs/zh-TW/permission-modes#skip-all-checks-with-bypasspermissions-mode)，跳過權限提示的模式，以及 `--dangerously-skip-permissions` 旗標 |
| `allowManagedPermissionRulesOnly` | CLI | 當 `true` 時，受管設定成為權限規則的唯一設定來源。[`allowManagedPermissionRulesOnly`](https://code.claude.com/docs/zh-TW/settings-reference#allowmanagedpermissionrulesonly) 項目列出 Claude Code 隨後忽略的每個來源。 |
| `env` | CLI | 合併到 CLI 程序的環境變數。用於遙測、自動更新和模型名稱覆寫。 |
| `hooks` | CLI | 組織範圍的 [hooks](https://code.claude.com/docs/zh-TW/hooks.md) |
| `managedMcpServers` | CLI | 遠端 MCP 伺服器[提供給每個匹配的開發者](https://code.claude.com/docs/zh-TW/managed-mcp.md#provide-servers-through-managed-settings)以及他們自己新增的伺服器，僅限 `http` 和 `sse`。請參閱[原則中的 MCP 伺服器](#mcp-servers-in-a-policy)。需要 gateway 伺服器和用戶端上的 Claude Code v2.1.259 或更新版本。較早的用戶端忽略金鑰。 |

因為這些設定透過網路到達，CLI 在應用下面列出的設定之前向每位開發者顯示安全核准對話框：

* `hooks`
* 需要開發者核准的 `env` 變數，例如代理伺服器和基礎 URL 變數
* shell 執行設定，例如 `apiKeyHelper` 和 `statusLine`
* 沙箱二進位設定 `sandbox.bwrapPath`、`sandbox.socatPath` 和 `sandbox.ripgrep`
* 攔截流量、注入憑證或削弱隔離的沙箱設定，例如 `sandbox.network.tlsTerminate` 和代理伺服器連接埠設定。[安全核准對話框](https://code.claude.com/docs/zh-TW/server-managed-settings.md#security-approval-dialogs)列出所有。

[核准記憶](https://code.claude.com/docs/zh-TW/server-managed-settings.md#approval-memory)涵蓋核准持續多長時間以及何時再次出現對話框。

Claude Code 會套用某些傳送來的 `env` 變數而不向開發人員顯示核准對話方塊，例如模型選擇設定與數值限制。其他傳送來的變數可能需要開發人員核准；非空的代理伺服器、基礎 URL 或 `OTEL_EXPORTER_OTLP_ENDPOINT` 值一律需要。當傳送來的變數需要核准時，對話方塊會指名該變數。[環境變數與核准對話方塊](https://code.claude.com/docs/zh-TW/server-managed-settings.md#environment-variables-and-the-approval-dialog)提供詳細資訊，包括四個隱私切換開關，其傳送的值決定是否需要核准。

gateway 的[遙測](#telemetry)設定推送 `OTEL_EXPORTER_OTLP_ENDPOINT`，因此設定 `telemetry.forward_to` 在每個互動式用戶端上觸發對話框。對話框保護開發者的機器免受受損或敵對 gateway 的影響，而不是保護組織免受開發者的影響。

[非互動式執行](https://code.claude.com/docs/zh-TW/server-managed-settings.md#security-approval-dialogs)（例如 `claude -p`、Agent SDK 工作階段，或 Claude Desktop Code 分頁中的工作階段）無法顯示對話方塊。它只會在該次執行中套用推送的設定，且不會將其記錄為已核准，因此開發人員的下一個互動式工作階段仍會顯示對話方塊。

如果開發者拒絕，Claude Code 會退出該工作階段，而不是應用原則。當您推送新 hook 或任何觸發對話框的 env 變數到廣泛原則時，每個匹配的開發者因此在其互動式工作階段中看到對話框。執行中的互動式工作階段在下一個每小時輪詢時顯示它，否則它在開發者的下一個互動式啟動時出現。

`cli` 鍵在較早的版本中名為 `settings`，閘道仍接受該寫法作為別名。新部署請使用 [`code`](#choose-cli-or-code)。

#### 在部署前測試政策

若要測試政策變更，請以一個可拋棄的 Postgres 資料庫啟動閘道。閘道會先連線到 Postgres 並套用其 schema 遷移，然後才檢查 `cli`、`code` 與 `desktop` 區塊的內容。當它無法連線到資料庫時，啟動會停在 `could not connect to Postgres`，不會回報這些區塊內容的任何資訊。

#### 終端機工作階段中的上下文視窗

透過 `/login` 登入的終端機工作階段，對 Opus 4.7 及更新版本、Sonnet 5 及更新版本，以及 Fable 模型使用 1M 上下文視窗。模型 ID 不需要 `[1m]` 後綴，工作階段會在約 967K 個 token 時壓縮。在開發者機器上的 Claude Code v2.1.287 之前，除非模型 ID 以 `[1m]` 結尾，否則 Claude Code 將 Opus 和 Fable 模型視為具有 200K 視窗。

若要讓終端機工作階段改為在 200K 邊界壓縮，請在原則的 `env` 中設定[自動壓縮視窗](https://code.claude.com/docs/zh-TW/model-config.md#set-the-auto-compact-window)：

```yaml theme={null}
managed:
  policies:
    - match: {}
      cli:
        env:
          CLAUDE_CODE_AUTO_COMPACT_WINDOW: "200000"
```

Claude Code 會套用此變數，而不向開發者顯示核准對話框。此變數適用於每個模型，包括以 `[1m]` 結尾的模型 ID。

若要改為關閉 1M 上下文，請在相同的 `env` 區塊中設定 [`CLAUDE_CODE_DISABLE_1M_CONTEXT: "1"`](https://code.claude.com/docs/zh-TW/model-config#extended-context)。Claude Code 隨後會將每個模型視為具有 200K 視窗。在互動式工作階段中，每位開發者會在[核准對話框](#what-goes-in-cli)中核准此變數，之後才會生效。

#### 一小時提示快取

若要請求一小時的[提示快取 TTL](https://code.claude.com/docs/zh-TW/prompt-caching.md#cache-lifetime)，而非預設的五分鐘，請將下列鍵新增到原則現有的 [`code`、`cli` 或 `settings` 區塊](#choose-cli-or-code)，然後重新啟動閘道。這些鍵需要閘道伺服器與用戶端上皆為 Claude Code v2.1.242 或更新版本。

`promptCacheTtl` 涵蓋主要對話。`subagentPromptCacheTtl` 為選用，涵蓋 subagent、工作流程及背景請求。以下範例將兩者都新增到以 `cli` 為鍵的 `match: {}` 原則：

```yaml theme={null}
managed:
  policies:
    - match: {}
      cli:
        promptCacheTtl: 1h
        subagentPromptCacheTtl: 1h
```

> [!WARNING]
>
> 只有在您的上游為閘道提供的每個模型都支援一小時 TTL 時，才設定這些鍵。若上游拒絕該 TTL，請求就會失敗，而閘道與 Claude Code 都不會以五分鐘 TTL 重試。對於 Amazon Bedrock，請查看[支援的模型、區域與限制](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html#prompt-caching-models)。

若要確認 `promptCacheTtl`，請以符合該原則的使用者身分登入閘道，並[檢查您的快取寫入使用了哪個 TTL](https://code.claude.com/docs/zh-TW/prompt-caching.md#choose-the-ttl-yourself)。傳入 `--model` 以針對閘道提供的每個模型重複此檢查。

一小時的快取寫入[成本較高](https://code.claude.com/docs/zh-TW/prompt-caching.md#cache-lifetime)於五分鐘的寫入。若要讓[支出限制](https://code.claude.com/docs/zh-TW/claude-apps-gateway-spend-limits.md#how-requests-are-priced)計入該較高費率，閘道伺服器上需要 v2.1.286 或更新版本。

#### 原則中的 MCP 伺服器

要將 MCP 伺服器提供給原則匹配的 Claude Code 用戶端，在該原則的 `cli` 區塊中設定 [`managedMcpServers`](https://code.claude.com/docs/zh-TW/managed-mcp#provide-servers-through-managed-settings)。您需要 gateway 伺服器和用戶端上的 Claude Code v2.1.259 或更新版本。

gateway 在啟動時使用 [Claude Code 在用戶端應用的相同規則](https://code.claude.com/docs/zh-TW/managed-mcp.md#what-an-entry-can-contain)檢查每個項目，如果項目未通過檢查，gateway 會拒絕啟動並命名項目。

如果您在 `gateway.yaml` 中寫入 `${VAR}` 參考，gateway 在啟動時透過[秘密擴展](#secret-expansion)從其環境解析它，然後執行項目檢查，因此每個匹配的用戶端接收字面值並可以讀取它。[提供伺服器的標頭指導](https://code.claude.com/docs/zh-TW/managed-mcp.md#provide-servers-through-managed-settings)適用於擴展值。

gateway 拒絕 `cli` 區塊中的 `.mcp.json` 拼寫 `mcpServers`，其啟動錯誤命名 `managedMcpServers` 為要使用的金鑰。在 v2.1.259 之前，gateway 拒絕 `cli` 區塊中的任何 MCP 伺服器定義。

#### Claude Desktop 疊加層

如果您的組織也部署[Claude Desktop](https://code.claude.com/docs/zh-TW/desktop.md)，相同的 gateway 為兩個用戶端提供服務。在 Claude Desktop 的[受管設定](https://claude.com/docs/third-party/claude-desktop/configuration)中指向 `bootstrapUrl` 到 `<listen.public_url>/user/bootstrap`。Claude Desktop 從該 URL 衍生 OAuth 發行者，針對此 gateway 執行相同的裝置代碼登入，並從回應擷取其設定。

> [!NOTE]
>
> 需要 gateway 伺服器上的 Claude Code v2.1.203 或更新版本，以及明確的選擇加入：除非匹配使用者的原則攜帶 `desktop` 金鑰，否則 `/user/bootstrap` 返回 404。空的 `desktop: {}` 選擇加入原則，`match: {}` 基礎層上的 `desktop` 金鑰選擇加入每個繼承它的原則。稽核日誌將每個請求記錄為 `desktop_bootstrap.serve` 或 `desktop_bootstrap.denied`。

如果您不部署 Claude Desktop，完全從您的原則中省略 `desktop`；gateway 隨後為每個使用者從 `/user/bootstrap` 返回 404。

##### gateway 為 Claude Desktop 衍生的設定

閘道會從符合原則的 `cli` 或 `code` 區塊以及頂層閘道設定衍生出大部分的 bootstrap 回應：

* 模型清單，來自 `availableModels`。清單會排除政策以 [`deniedModels` 或 `availableModelsMatch: exact`](#what-goes-in-cli) 封鎖的模型。此篩選需要閘道伺服器上為 Claude Code v2.1.299 或更新版本。[Claude Desktop 中的延伸上下文](#extended-context-in-claude-desktop)說明每個模型的 1M 上下文選項
* 禁用的工具，來自裸工具名稱 `permissions.deny` 項目。如果您在原則的 `desktop` 區塊中設定 `disabledBuiltinTools`，gateway 提供您的值和衍生清單的聯集，因此您可以透過此方式禁用更多工具，但無法重新啟用您透過 `permissions.deny` 禁用的工具
* 輸出允許清單，來自 `sandbox.network.allowedDomains`。若您在原則的 `desktop` 區塊中設定 `coworkEgressAllowedHosts`，閘道會改用該值，而非衍生清單。若閘道提供的允許清單包含 `*`，且閘道未同時提供 Claude Desktop 的 [`allowedWorkspaceFolders`](https://claude.com/docs/third-party/claude-desktop/code#applied-as-managed-policy)，Claude Desktop 就不會在 Code 分頁中開啟 [Bash 沙箱](https://code.claude.com/docs/zh-TW/sandboxing.md)
* 指向 gateway 本身的 OTLP 端點，以及已登入使用者的身分屬性。gateway 轉發它在該端點接收的匯出到您的 `forward_to` 目的地。當您同時設定 [`telemetry.forward_to`](#telemetry) 和 `listen.public_url` 時，它包括端點和屬性。

  Claude Desktop 以一種編碼匯出每個信號：`http/protobuf`，或當您在原則的 `env` 中設定 `OTEL_EXPORTER_OTLP_PROTOCOL` 或其每個信號變體為 `http/json` 時為 `http/json`。在 gateway 伺服器上的 Claude Code v2.1.261 之前，回應設定 `http/json` 無論如何，因此只接受 protobuf 的收集器拒絕 Claude Desktop 的匯出

要在原則的 `desktop` 區塊中設定 `disabledBuiltinTools`、`coworkEgressAllowedHosts` 或 Claude Desktop 自己的 `managedMcpServers` 設定，您需要 gateway 伺服器上的 Claude Code v2.1.232 或更新版本。Claude Desktop 的 `managedMcpServers` 採用陣列值而不是物件。

gateway 省略沒有 Claude Desktop 等效項的金鑰，例如 `hooks` 和範圍權限規則（如 `Bash(npm *)`），來自啟動回應。

##### 在 Code 分頁中套用 `code` 設定

當下列條件全部成立時，原則在其 [`code`](#choose-cli-or-code) 鍵下保存的 Claude Code 設定會在 Claude Desktop 的 Code 分頁中套用：

* 原則也具有 `desktop` 鍵，空的 `desktop: {}` 也算
* Claude Desktop 為 2.9939.2 或更新版本
* 電腦上的 Claude Code 受管設定[指名此閘道](#client-side-managed-settings)
* 該電腦透過私人網路以 HTTPS 連線到閘道

最後兩個條件適用於為該工作階段執行 Claude Code 的電腦。對於本機工作階段，那是使用者自己的電腦。對於透過 SSH 的 Code 分頁工作階段，則是遠端主機。

在將 `cli` 重新命名為 `code` 之前，請先將[用戶端受管設定](#client-side-managed-settings)部署到這些電腦。當前兩個條件成立但後兩個之一不成立時，原則所符合的使用者會得到下列其中一種結果：

* **透過 HTTPS，且 Claude Desktop 內附 Claude Code v2.1.296 或更新版本**：Code 分頁不會啟動，對使用者提示詞的回覆會說明原因
* **透過 HTTPS，且 Claude Desktop 內附較早版本**：Code 分頁會在沒有您的 `code` 設定的情況下啟動，工作階段中不會有任何提示
* **透過純 HTTP**：無論 Claude Desktop 內附哪個版本，Code 分頁都會在沒有您的 `code` 設定的情況下啟動

當閘道前方的代理伺服器以自己的 404 回應 `/managed/settings` 時，Code 分頁也會在沒有您的 `code` 設定的情況下啟動，即使在符合全部四個條件的電腦上也是如此。

在具有 `desktop` 鍵的原則中，保存設定的 `code` 區塊會在 Cowork、Chat 與 Code 分頁中關閉 WebSearch 工具。關於 MCP 伺服器，請參閱 [`managedMcpServers` 的套用位置](https://code.claude.com/docs/zh-TW/managed-mcp#where-managedmcpservers-applies)。

##### 直接設定 Claude Desktop 設定

在 `cli` 旁邊新增選用的 `desktop` 區塊以直接設定 Claude Desktop 設定。從 Claude Desktop 的[受管設定參考](https://claude.com/docs/third-party/claude-desktop/configuration)寫入設定為平面金鑰名稱。省略 Claude Desktop 只從 MDM 或本機檔案讀取的金鑰，例如 `bootstrapUrl`；gateway 在啟動時拒絕它們。

此範例為 `eng-contractors` 群組設定三個 Claude Desktop 金鑰，並搭配其 `cli` 設定：

```yaml theme={null}
managed:
  policies:
    - match: { groups: [eng-contractors] }
      cli:
        availableModels: [claude-sonnet-4-6]
        enforceAvailableModels: true
      desktop:
        isLocalDevMcpEnabled: false
        disableAutoUpdates: true
        banner: { text: "Contractor build: internal use only" }
```

每個金鑰都是選用的；Claude Desktop 為您省略的任何金鑰應用自己的預設值。

##### gateway 在啟動時拒絕的內容

gateway 在啟動時根據 Claude Desktop 本身使用的設定 schema 驗證每個 `desktop` 區塊，因此錯誤會在 gateway 啟動時顯示為命名金鑰的錯誤，而不是到達每個連接的桌面。當區塊包含以下內容時，gateway 在啟動時失敗：

* 未知金鑰
* 已識別的金鑰，其值 Claude Desktop 會拒絕或無聲丟棄，例如空值或巢狀項目內的拼寫錯誤的子金鑰。在 v2.1.260 之前，gateway 無聲丟棄 `managedMcpServers` 或 `orgPluginSettings` 項目的巢狀物件內的拼寫錯誤欄位，而不是在啟動時失敗。
* gateway 自己計算的金鑰：推論連接、模型清單和 OTLP 轉發。透過 [`upstreams`](#upstreams)、[`models`](#models) 和 [`telemetry`](#telemetry) 區塊的 `forward_to` 設定這些。
* 目前金鑰的舊版別名。在啟動錯誤中，gateway 命名規範金鑰以寫入。

如果您使用已棄用的值或項目形狀，例如沒有 `transport` 的 `managedMcpServers` 項目，gateway 啟動並記錄命名替換的警告。

在 v2.1.232 之前，gateway 接受固定的 11 個功能閘道金鑰清單，例如 `chatTabEnabled` 和 `disableAutoUpdates`，並在啟動時拒絕每個其他金鑰。在 v2.1.227 之前，gateway 也在啟動時拒絕 `chatTabEnabled` 和 `chatAdvancedFileAnalysisEnabled`。

##### 需要較新 gateway 或 Claude Desktop 版本的金鑰

gateway 根據與其安裝版本捆綁的 schema 驗證 `desktop` 區塊，如同 `cli` 區塊。要傳遞較新 Claude Desktop 版本引入的設定，請先升級 gateway。例如，`userPluginMarketplacesEnabled` 和 `userPluginUploadsEnabled` 需要 gateway 伺服器上的 Claude Code v2.1.260 或更新版本以及成員機器上的 Claude Desktop 1.37937.0 或更新版本。

`blockReadsOutsideWorkingDirectories`、`disableBypassPermissionsMode`、`configRecheckIntervalMinutes` 和 `sshClientPath` 需要 gateway 伺服器上的 Claude Code v2.1.281 或更新版本。Microsoft 365 `managedMcpServers` 項目的 `microsoftAuthBroker` 的 `required` 值和 `continuousAccessEvaluation` 欄位也是如此。早於 `required` 值的 Claude Desktop 版本將其讀取為 `disabled`，因此只在每個成員的 Claude Desktop 支援它之後設定 `required`。Claude Desktop 的[受管設定參考](https://claude.com/docs/third-party/claude-desktop/configuration)列出首次讀取每個金鑰的版本。

> [!NOTE]
>
> [`sshTransport`](https://claude.com/docs/third-party/claude-desktop/configuration#sshtransport) 需要閘道伺服器上為 Claude Code v2.1.293 或更新版本。

如果您在原則的 `desktop` 區塊中設定 `orgPluginSettings`，gateway 以 Claude Desktop 1.15200.0 及更新版本讀取的陣列形式提供它。較舊的桌面忽略陣列並強制執行沒有外掛工具原則，因此在依賴它之前將成員更新到 1.15200.0 或更新版本。

##### 角色原則如何繼承基礎 `desktop` 區塊

對於原則的 `desktop` 區塊未設定的金鑰，gateway 從 `match: {}` 全部捕捉的 `desktop` 區塊填入，與它從基礎填入原則 `cli` 區塊的方式相同。如果您在基礎和角色原則中都設定 `disabledBuiltinTools` 或 `builtinToolPolicy`，gateway 保留基礎的限制：

* `disabledBuiltinTools`：gateway 使用基礎清單和原則清單的聯集
* `builtinToolPolicy`：如果您在基礎中將工具設定為 `allow` 以外的值，gateway 保留該值，即使您在角色原則中為相同工具設定 `allow`

對於每個其他金鑰，如果您在角色原則中設定它，gateway 使用角色原則的值。gateway 整體替換陣列或巢狀物件（例如 `banner`），因此如果您在角色原則中設定 `banner.text`，gateway 丟棄基礎的 `banner.backgroundColor`。

##### Claude Desktop 何時套用原則變更

在您以變更後的原則重新部署 gateway 後，Claude Desktop 大多數設定只會在下次啟動時套用：

* **已關閉**：Claude Desktop 在啟動時擷取啟動回應，因此變更從下次啟動開始套用
* **已開啟**：Claude Desktop 預設每 10 分鐘檢查一次回應是否變更，並在不重新啟動的情況下套用少數設定。對於其餘設定，例如 [`skillCreationEnabled`](https://claude.com/docs/third-party/claude-desktop/configuration#skillcreationenabled)，使用者會在側邊欄看到 **Relaunch Claude Desktop** 卡片，並保留先前的設定，直到重新啟動應用程式為止。預設 24 小時後，Claude Desktop 會顯示重新啟動對話框，並在閒置 2 分鐘後自行重新啟動

若要縮短這 24 小時，請在原則的 `desktop` 區塊中設定 [`relaunchEnforcementHours`](https://claude.com/docs/third-party/claude-desktop/configuration#relaunchenforcementhours)。您需要 gateway 伺服器上的 Claude Code v2.1.260 或更新版本，以及成員機器上的 Claude Desktop 1.40609.0 或更新版本。設為 `0` 時，Claude Desktop 一發現變更就會顯示對話框。

#### Claude Desktop 中的延伸上下文

如果您從 gateway 提供 [Claude Desktop](#claude-desktop-overlay)，其模型選擇器會為每個可以使用 1M 上下文視窗執行的列出模型提供 1M 上下文選項。這些包括 Claude Opus 4.6 及更新版本、Claude Sonnet 4.6 及更新版本，以及 Fable 模型。該選項是模型的 `[1m]` 變體，[延伸上下文](https://code.claude.com/docs/zh-TW/model-config.md#extended-context)中有說明。您需要 gateway 伺服器上的 Claude Code v2.1.284 或更新版本。

[`models`](#models) 項目在以下情況下不會獲得 1M 選項：

* 可以提供該項目的上游將其對應到不支援 1M 的模型，包括 gateway 只在故障轉移時才會連到的上游
* 其 `id` 和任何 `upstream_model` 值都未命名 Claude 模型，例如路由到應用程式推論設定檔 ARN 的自訂別名

要變更選擇器提供的內容，請使用以下其中一種方式：

* **讓使用者從 1M 選項開始**：在原則的 `desktop` 區塊中設定 `modelPrefer1mContext: true`。尚未選擇模型的使用者，在第一個列出的模型具有 1M 選項時，會從 1M 選項開始。已選擇模型的使用者保留其選擇。
* **手動提供選項**：如果您的 gateway 伺服器執行早於 v2.1.284 的版本，或項目未命名任何 Claude 模型，請這樣做。在 `models` 中列出該模型兩次，一次使用其純 ID，一次附加 `[1m]`，兩者使用相同的 `upstream_model` 對應。Claude Desktop 將這一對顯示為一個具有 1M 選項的模型。gateway 提供 `[1m]` 項目時不會檢查它，因此只為您的上游以 1M 提供的模型新增此類項目。

此範例為路由到應用程式推論設定檔的自訂別名手動提供選項，並讓新使用者從該選項開始：

```yaml theme={null}
models:
  - id: corp-sonnet
    upstream_model:
      bedrock: arn:aws:bedrock:us-east-2:123456789012:application-inference-profile/sonnet-5-prod
  - id: corp-sonnet[1m]
    upstream_model:
      bedrock: arn:aws:bedrock:us-east-2:123456789012:application-inference-profile/sonnet-5-prod

managed:
  policies:
    - match: {}
      desktop:
        modelPrefer1mContext: true
```

##### 移除 1M 選項

要從選擇器中移除該選項，請在原則 `cli` 金鑰下的 `env` 區塊中設定 `CLAUDE_CODE_DISABLE_1M_CONTEXT: "1"`。如果您也列出了 `id` 以 `[1m]` 結尾的項目，gateway 仍會提供它，因此也請刪除該項目。

該變數也會傳到原則匹配的開發者的終端機工作階段。關於它在那裡變更的內容，請參閱[延伸上下文](https://code.claude.com/docs/zh-TW/model-config.md#extended-context)。

#### 與其他受管來源的優先順序

如果裝置也有 MDM 傳遞的原則或本機 `managed-settings.json`，gateway 傳遞的設定排名第一。[受管層級內的優先順序](https://code.claude.com/docs/zh-TW/managed-settings.md#precedence-within-the-managed-tier)在受管設定頁面上說明本機來源何時適用，並有[Claude Code 從每個 admin 來源讀取的金鑰](https://code.claude.com/docs/zh-TW/managed-settings.md#keys-read-from-every-admin-source)，無論它選擇哪個來源，例如沙箱鎖定金鑰、`forceRemoteSettingsRefresh` 和每個變數 `env` 合併。在 MDM 設定檔或受管設定檔案中設定的 [`policyHelper`](https://code.claude.com/docs/zh-TW/settings-reference#policyhelper) 只在 gateway 傳遞沒有設定時執行；項目說明其輸出替換什麼。

嵌入主機（例如 [Claude Desktop](https://code.claude.com/docs/zh-TW/desktop.md)）可以透過 SDK `managedSettings` 選項提供原則。[來自嵌入主機的父設定](https://code.claude.com/docs/zh-TW/managed-settings.md#parent-settings-from-embedding-hosts)說明 Claude Code 何時應用它，以及[限制父設定](https://code.claude.com/docs/zh-TW/claude-apps-gateway#restrict-parent-settings)列出哪些允許方向設定仍在沒有 `allowManaged*Only` 鎖的情況下適用。

gateway 原則適用於機器上的每個 Claude Code 呼叫，包括非互動式 `claude -p` 執行和 Agent SDK 衍生的工作階段。如果 gateway 在啟動時無法到達，已登入的工作階段會以錯誤退出，而不是在沒有其原則的情況下執行。

### `telemetry`

CLI 將指標、日誌和（啟用時）追蹤傳送到 gateway，gateway 逐字轉發到每個已設定的目的地。匯出使用 OpenTelemetry Protocol (OTLP) over HTTP。要跳過轉發並讓工作階段直接匯出到您的收集器，[在原則中命名收集器](#export-directly-to-your-collector)。請參閱[監控使用](https://code.claude.com/docs/zh-TW/monitoring-usage.md)以了解 CLI 發出的指標和事件。

在透過 `/login` 登入的工作階段中，CLI 會為每筆匯出標記已驗證使用者的身分，這些身分讀取自閘道簽發的 JWT：`user.id`、`user.email` 與 `user.groups` 屬性。因此，每位開發人員的成本與使用量歸屬無需開發人員端的任何設定即可運作。Claude Code 在開發人員登入前記錄的事件[不帶有此身分](https://code.claude.com/docs/zh-TW/monitoring-usage.md#standard-attributes)。若要了解哪個屬性會跟隨開發人員群組的變更，請參閱[開啟中工作階段期間的群組變更](#group-changes-during-an-open-session)。

[Claude Desktop](#claude-desktop-overlay) 和透過 gateway 登入的 Cowork 工作階段使用 `user.email` 和 `user.groups` 以及 `enduser.id` 戳記其遙測，因此您可以使用一個 `user.email` 或 `user.groups` 查詢涵蓋終端機、Desktop 和 Cowork 使用。`user.groups` 是逗號分隔的 IdP 群組清單。

Desktop 和 Cowork 遙測也攜帶 `enduser.sub`，您的身分提供者為使用者發行的 `sub` 聲明，當使用者的電子郵件變更時保持相同。終端機工作階段在 `user.id` 下戳記相同值，因此匹配 `enduser.sub` 對終端機 `user.id` 的查詢涵蓋一個使用者的終端機、Desktop 和 Cowork 使用。在 Desktop 和 Cowork 匯出上，`user.id` 是匿名識別碼，而不是主體。

像來自 Claude Code 的所有 OpenTelemetry 資料一樣，這些屬性只進入您的組織設定的目的地，永遠不進入 Anthropic。

如果使用者的群組清單在百分比編碼後超過 255 個字元，或群組名稱包含逗號或等號，gateway 從該使用者的 Desktop 和 Cowork 遙測中省略 `user.groups`，而不是截斷它。該使用者的終端機工作階段仍攜帶完整清單。

當主體在百分比編碼後超過 255 個字元，或包含空格、可列印 ASCII 外的字元或 `,` `;` `=` `\` `"` `%` 之一時，gateway 從 Desktop 和 Cowork 遙測中省略 `enduser.sub`。該使用者的 Desktop 和 Cowork 遙測保留其他屬性。

您需要 gateway 伺服器上的 Claude Code v2.1.265 或更新版本才能在 Desktop 和 Cowork 遙測上使用 `user.email` 和 `user.groups`，以及每位開發者機器上的 Claude Desktop 1.24012 或更新版本才能使用 `user.groups`。

您需要 gateway 伺服器上的 Claude Code v2.1.274 或更新版本才能使用 `enduser.sub`。

```yaml theme={null}
telemetry:
  forward_to:
    - url: https://otel-collector.internal.example.com
      headers:
        Authorization: ${OTLP_TOKEN}
      # 每個信號選擇加入。預設：僅指標。
      metrics: true
      logs: false
      traces: false
    - url: https://api.datadoghq.com/api/v2/otlp
      headers:
        DD-API-KEY: ${DD_API_KEY}
```

> [!WARNING]
>
> 每個目的地獨立選擇加入 `metrics`、`logs` 和 `traces`，預設為僅指標。信號在敏感性上有所不同：
>
> * **指標**：聚合計數器，例如 token 計數、請求計數和延遲
> * **日誌和追蹤**：可以攜帶完整 Bash 命令、工具輸入和檔案路徑，涵蓋 Claude Code 在開發者機器上執行的任何操作
>
> 只在具有該資料保證的存取控制和保留原則的目的地啟用日誌和追蹤。

每個 `forward_to` URL 必須使用 `https://`，有一個例外，用於 gateway 自己的環回介面上的收集器：

* `http://localhost:<port>` 通過設定驗證，但[SSRF 防護](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#threat-model-summary)除非您在 gateway 的環境中設定 `CLAUDE_GATEWAY_ALLOW_LOOPBACK=1`，否則會阻止每個匯出，出現 `ECONNREFUSED_SSRF`
* `http://127.0.0.1:<port>` 或 `http://[::1]:<port>` 除非設定該變數，否則啟動失敗

對於叢集內收集器，在其自己的內部位址上公開 HTTPS，或將其作為邊車執行，並設定變數。

當設定 `HTTPS_PROXY` 時，gateway 透過該代理伺服器傳送匯出。

要直接到達內部收集器，透過主機名稱或具有前導點的網域（例如 `.internal.example.com`）將其新增到 `NO_PROXY`，這需要 gateway 伺服器上的 Claude Code v2.1.277 或更新版本。確保 gateway 可以在沒有代理伺服器的情況下到達收集器。沒有前導點的項目只匹配該確切名稱，不匹配其下的名稱。CIDR 範圍不匹配。

啟用[僅代理伺服器出口](#proxy-only-egress)後，改為在代理伺服器中允許收集器，因為任何 `NO_PROXY` 項目會關閉僅代理伺服器出口。

遙測在 CLI 中預設關閉。當您同時設定 `telemetry.forward_to` 和 `listen.public_url` 時，gateway 透過 `/managed/settings` 推送六個環境變數來為連接的用戶端啟用它：

* `CLAUDE_CODE_ENABLE_TELEMETRY=1`
* `OTEL_METRICS_EXPORTER`、`OTEL_LOGS_EXPORTER` 和 `OTEL_TRACES_EXPORTER`，如果至少一個 `forward_to` 目的地啟用該信號，則每個設定為 `otlp`，否則設定為 `none`
* `OTEL_EXPORTER_OTLP_ENDPOINT=<public_url>`
* `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf`

當您[新增自己的標籤](#add-your-own-labels)時，gateway 也推送 `OTEL_RESOURCE_ATTRIBUTES`。

在 gateway 伺服器上的 Claude Code v2.1.265 之前，gateway 推送所有三個匯出器選擇器為 `otlp`，包括沒有目的地選擇加入的信號。

推送的端點是從公開 URL 建立的，因此指標和日誌不需要開發者或原則的 OTEL 設定。

透過 `/login` 登入的開發者無法使用自己的 OTEL 設定重新導向匯出：

* **本機設定的變數**：Claude Code 在受管層級應用推送的變數，因此每個變數覆寫開發者本機設定的值。
* **本機設定的端點**：啟用 OTLP/HTTP 匯出後，CLI 忽略任何本機設定的端點，無論 gateway 是否推送遙測變數。其匯出進入 gateway，除非原則[將您的收集器命名為端點](#export-directly-to-your-collector)。

沒有信號的 `forward_to` 目的地，gateway 接受並丟棄它。如果開發者已經將 Claude Code 遙測匯出到您的其中一個收集器，將其新增為 `forward_to` 目的地，如果他們匯出那些，則啟用日誌或追蹤，因此在他們登入後它繼續接收其資料。要改為跳過轉發，[在原則中命名收集器](#export-directly-to-your-collector)。

[追蹤](https://code.claude.com/docs/zh-TW/monitoring-usage.md#traces-beta)也需要每個用戶端上的 `CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1`。在受管原則的 `env` 區塊中設定它，因為 gateway 不推送它。開發者在已經觸發推送端點的相同[安全核准對話框](#managed)中核准它。

只在您想要追蹤的群組的原則中將其設定為 `1`。不設定它的原則從您的 `match: {}` 全部捕捉原則繼承值（如果該原則設定一個），根據[合併規則](#managed)。要防止群組的用戶端傳送追蹤，即使開發者本機設定變數，在該群組的原則中將其設定為 `0`。

protobuf 和 JSON OTLP 編碼都被轉發，任何 OpenTelemetry 相容後端都可作為目的地。

#### 傳送累積指標

如果您的收集器只接受累積指標，請將 [`OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE`](https://code.claude.com/docs/zh-TW/monitoring-usage#common-configuration-variables) 設為 `cumulative`。Claude Code 預設傳送差值指標，閘道轉送時不會進行轉換。請在每種工作階段讀取該變數的位置設定它：

* **終端機工作階段**：在政策 [`cli` 或 `code` 鍵](#choose-cli-or-code)下的 `env` 區塊中
* **[在使用者機器上執行](https://code.claude.com/docs/zh-TW/managed-settings.md#where-and-when-a-policy-applies)的 Cowork 工作階段**：在該機器上[用戶端受管設定](#client-side-managed-settings)的 `env` 區塊中
* **`code` 政策下的 Code 分頁工作階段**：在符合[套用 `code` 設定的條件](#apply-code-settings-in-the-code-tab)後，於政策的 `env` 區塊中
* **`cli` 政策下的 Code 分頁工作階段**：在執行該工作階段之機器上用戶端受管設定的 `env` 區塊中。透過 SSH 時，那是遠端主機。

如果您將此變數加入機器的受管設定，也請在該機器上優先順序最高的來源中設定 [`parentSettingsBehavior: "merge"`](https://code.claude.com/docs/zh-TW/claude-apps-gateway#set-the-opt-in)。否則，Cowork 工作階段以及 `cli` 政策下的 Code 分頁工作階段執行時，將不會有 Claude Desktop 以父設定形式傳給它們的輸出允許清單和其他政策。

#### 新增自己的標籤

要在透過 gateway 登入的工作階段的遙測上放置固定標籤（例如 `service.namespace` 或 `deployment.environment.name`），設定 `telemetry.resource_attributes`。每個標籤是 OpenTelemetry 資源屬性，每個目的地接收相同的標籤。

工作階段只在您也設定 `telemetry.forward_to` 和 `listen.public_url` 時獲得標籤。此範例新增兩個標籤：

```yaml theme={null}
telemetry:
  forward_to:
    - url: https://otel-collector.internal.example.com
  resource_attributes:
    service.namespace: claude
    deployment.environment.name: prod
```

當標籤違反這些規則之一時，gateway 會拒絕啟動，啟動錯誤會命名標籤：

* 名稱只使用字母、數字、`.`、`_` 和 `-`
* 名稱不是保留的。以任何字母大小寫比較，保留名稱是以 `user.`、`enduser.` 或 `identity.` 開頭的所有內容，加上 `service.name`、`service.version`、`claude.deployment_mode`、`host.arch`、`os.type`、`os.version` 和 `wsl.version`
* 值是非空可列印 ASCII，沒有空格和 `, ; = \ " %` 中的任何一個
* 值在 gateway 在百分比編碼後計算時最多 255 個字元，因此 `/`、`:` 和 `@` 各計為三個
* 值是文字，因此引用數字、`true` 或 `false`

您需要 gateway 伺服器上的 Claude Code v2.1.281 或更新版本才能設定 `telemetry.resource_attributes`。較早的 gateway 在找到金鑰時會拒絕啟動。在新增金鑰之前升級每個複本，並在回滾到較早版本之前移除金鑰。

透過 `/login` 登入的終端機工作階段接收標籤作為 `OTEL_RESOURCE_ATTRIBUTES`，與其他[遙測變數](#telemetry)一起推送。如果您在原則的 `env` 區塊中設定 `OTEL_RESOURCE_ATTRIBUTES`，該原則匹配的終端機工作階段獲得該值而不是標籤。Claude Desktop 從 gateway 接收標籤以及 `user.email` 和其他身分屬性。

Claude Code 也將每個標籤複製到每個指標資料點，因此您可以在不索引資源屬性的後端中按它篩選指標。要關閉該複製，請參閱[指標基數控制](https://code.claude.com/docs/zh-TW/monitoring-usage.md#metrics-cardinality-control)。

#### 開啟中工作階段期間的群組變更

終端機工作階段會將 `user.groups` 放在 OTLP 資源上，並再次放在每個指標資料點與事件上。若開發人員的群組在工作階段開啟期間變更，下一次[靜默重新整理](#session)之後的使用量所對應的資料點與事件會帶有新的群組。資源會保留舊的群組，直到開發人員重新啟動 Claude Code 為止，因此請依資料點或事件上的屬性進行分組。

若您在 OpenTelemetry Collector 的 Prometheus remote write 匯出器中開啟 `resource_to_telemetry_conversion`，匯出器會以資源的 `user.groups` 取代每個資料點的 `user.groups`，因此每個資料點都會顯示舊的群組。若要保留資料點的值，請在該匯出器之前從資源中刪除 `user.groups`。

以下 OpenTelemetry Collector `resource` 處理器會在列出它的管線中刪除該屬性：

```yaml theme={null}
processors:
  resource/drop-user-groups:
    attributes:
      - key: user.groups
        action: delete
```

將 `resource/drop-user-groups` 新增至指標管線的 `processors` 後，每個序列都會帶有來自其自身資料點的 `user_groups` 標籤。

#### 直接匯出到您的收集器

要讓透過 `/login` 登入的工作階段直接將遙測傳送到您的收集器而不是透過轉發，在[受管原則](#managed)的 `env` 區塊中將 `OTEL_EXPORTER_OTLP_ENDPOINT` 設定為收集器的 `https://` 基礎 URL。Claude Code 將 `/v1/metrics`、`/v1/logs` 或 `/v1/traces` 附加到您設定的 URL，例如 `https://otel-collector.example.com:4318`，並在那裡透過 OTLP/HTTP 匯出每個信號。需要每位開發者機器上的 Claude Code v2.1.265 或更新版本。較早的用戶端透過轉發匯出。

要驗證到收集器，在相同的 `env` 區塊中設定 `OTEL_EXPORTER_OTLP_HEADERS`。工作階段永遠不會將開發者的 gateway 工作階段 token 傳送到以此方式命名的收集器。

當您在原則中新增或變更此端點時，Claude Code 會在[安全核准對話框](#managed)中請每位開發者核准它，然後在互動式工作階段中應用它。

Claude Code 在直接匯出信號之前檢查端點，並在檢查失敗時將該信號保留在轉發上。檢查包括：

* 端點來自 gateway 本身。如果您在 MDM 設定檔或本機 `managed-settings.json` 中設定相同變數，匯出保留在轉發上。
* URL 使用 `https://`，或 `http://` 到環回位址
* URL 解析為以 `/v1/<signal>` 結尾的路徑，沒有查詢或片段。Claude Code 從通用變數自己建立該路徑。它使用每個信號變數（例如 `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT`）如寫入，因此在那裡包括完整路徑。
* URL 不是 gateway 自己的主機。尋址到 gateway 的端點保留轉發路徑和其工作階段 token。
* 您和開發者都未在任何設定來源中設定 [`otelHeadersHelper`](https://code.claude.com/docs/zh-TW/settings-reference#otelheadershelper)。設定了助手，每個信號保留在轉發上。

您命名的端點只改變匯出的去向。您仍然使用 `OTEL_*_EXPORTER` 選擇器選擇哪些信號匯出。

端點本身不啟用匯出，因此也設定執行此操作的變數，除非 gateway 已推送它們：

* 如果 gateway 已[推送遙測變數](#telemetry)，它們涵蓋啟用、選擇器和協議，您的明確端點覆寫推送的 `<public_url>` 值。只為沒有 `forward_to` 目的地啟用的信號自己設定 `OTEL_*_EXPORTER` 選擇器為 `otlp`。
* 如果它沒有，也設定 `CLAUDE_CODE_ENABLE_TELEMETRY=1`、`OTEL_*_EXPORTER` 選擇器和 `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf`。

當開發者登出或登入不同的 gateway 時，對收集器的匯出停止，Claude Code 丟棄每個剩餘批次，而不是傳送它。

#### 當目的地失敗時

gateway 不緩衝、重試或儲存遙測，因此未到達目的地的匯出被丟棄，而不是晚期傳遞。每個目的地獨立成功或失敗，匯出用戶端無論如何都接收成功回應，因此失敗的傳遞只出現在 gateway 的日誌中。

在連續 5 次失敗傳遞到目的地後，gateway 在 30 秒的拉伸中暫停轉發到它，記錄每個暫停，直到傳遞成功。任何錯誤回應、逾時或連接錯誤計為失敗傳遞，除了 `400`、`413`、`415`、`422` 和 `431`，這意味著收集器拒絕該匯出的 payload 為格式不正確或太大。

被拒絕的 payload 既不推進也不重設失敗計數：gateway 繼續轉發到目的地並記錄警告，命名它和狀態，在目的地的第一次拒絕和之後每一百次。

### HTTP 調整

四個選用的頂層區塊 `access_control`、`limits`、`timeouts` 和 `rate_limits` 調整 HTTP 表面。預設值適合大多數部署。

| 區塊 | 金鑰 | 預設 | 說明 |
| - | - | - | - |
| `access_control` | `allow_cidrs` / `deny_cidrs` | 空 | 按用戶端位址的入站 IP 允許/拒絕，在 `trusted_proxies` 解析後。`deny_cidrs` 首先檢查；符合它的用戶端被拒絕，即使 `allow_cidrs` 也匹配。如果 `allow_cidrs` 非空，gateway 是預設拒絕。`/healthz` 和 `/readyz` 豁免於 `allow_cidrs`。當受信任代理伺服器傳送不是 IP 位址的 `X-Forwarded-For` 項目時，真實用戶端未知，gateway 記錄一次警告，命名要檢查的內容。其中任一清單適用於請求，它以 `403` 和稽核原因 `xff_unparseable` 拒絕它。其中都不適用，它提供請求並使用代理伺服器自己的位址作為用戶端 IP，用於每 IP 速率限制和稽核。 |
| `limits` | `max_request_bytes` | 32 MiB | 最大入站請求本體；超大小請求在本體被緩衝之前獲得 `413`。為大型檔案或影像請求提高。 |
| `limits` | `max_request_header_bytes` | 未設定 | 降低 gateway 對請求標頭總大小的 256 KiB 限制。超過限制的請求返回 `431`，高於 256 KiB 的值沒有作用。如果開發者在登入後收到 `431`，請參閱[登入後請求標頭過大](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#request-headers-too-large-after-sign-in)。 |
| `limits` | `max_url_length` | 未設定 | 設定時，過長 URL 返回 `414` |
| `timeouts` | `upstream_ttfb_ms` | 120000 | 等待上游回應標頭的上限（首位元組時間）。之後回應主體會以串流傳送，沒有實際時間上限。若未設定此鍵，預設值適用於 `provider: anthropic` 上游；對於其他所有供應商，閘道最多會等待一小時讓回應開始。若要縮短此等待時間，請參閱[多個上游](#multiple-upstreams)。 |
| `rate_limits` | `device_authorization.max` / `.window_seconds` | 30 / 600 | 未驗證裝置授權端點上的每 IP 速率限制。為共享出口 IP 或 NAT 後的大型組織提高。[大型推出](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#large-rollouts)顯示如何調整大小。這些限制只適用於裝置授予登入流程，不適用於 `/v1/messages` 推論。請參閱[使用者代碼暴力破解抵抗](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#user-code-brute-force-resistance)。 |
| `rate_limits` | `device_verify.max` / `.window_seconds` | 10 / 600 | 在 `/device` 上 `user_code` 提交的每 IP 速率限制。這是阻止某人猜測另一位開發者代碼的原因。[大型推出](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#large-rollouts)顯示提高多遠。 |

如果您將兩個 `access_control` 清單都留空（預設值），gateway 為任何用戶端位址提供服務，因此只有您的網路限制誰可以到達它。這很重要，因為 gateway 可以推送[受管設定](#managed)，在開發者機器上執行命令。

當 `allow_cidrs` 為空時，gateway 在兩個地方警告，不改變它如何回答任何請求：

* **在啟動時**：操作日誌中的警告建議只允許私有範圍 `10.0.0.0/8`、`172.16.0.0/12`、`192.168.0.0/16`、`100.64.0.0/10`、`127.0.0.0/8`、`::1/128` 和 `fc00::/7`，加上開發者連接的任何其他內部範圍。如果您將 gateway 綁定到環回位址，且 `trusted_proxies` 和 `public_url` 都不設定，如本機開發，警告不出現。
* **在執行時**：第一次請求從私有範圍外的位址到達時，gateway 記錄警告並發出 [`access.public_client` 稽核事件](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy#logs)，攜帶用戶端 IP。兩者每個程序執行一次。連結本機位址 `169.254.0.0/16` 和 `fe80::/10` 不計為公開。gateway 在此檢查執行之前回答 `/healthz` 和 `/readyz`，因此來自公開範圍的健康探測不觸發它。

兩個信號都使用 gateway 解析的用戶端位址。如果負載平衡器、連接埠轉發或隧道轉發流量且未列在 `listen.trusted_proxies` 中，gateway 看到轉發位址，通常是私有的，因此執行時警告和私有允許清單都不捕捉透過它轉發的流量。

在這樣的前端後面，首先設定 [`listen.trusted_proxies`](#listen)，以便 gateway 看到真實用戶端位址，並無論如何保持 gateway 和其前面的所有東西無法從公開網際網路到達。

### `load_test_mode`

`load_test_mode` 區塊讓您負載測試 gateway，而不呼叫模型提供者。啟用時，gateway 建立和簽署每個提供者請求如常，丟棄它而不是傳送它，並透過其一般回應路徑流式傳輸罐裝回覆。回覆是填充文字，以說明它是罐裝的句子開始。

需要 gateway 伺服器上的 Claude Code v2.1.282 或更新版本。較早的 gateway 在找到金鑰時會拒絕啟動。在新增區塊之前升級每個複本，並在回滾之前移除區塊。

下面的範例以預設值啟用模式，大約 750 個 token 的文字回覆，在大約 10 秒內流式傳輸：

```yaml theme={null}
load_test_mode:
  enabled: true
  reply_tokens: 750     # roughly how many tokens of text each canned reply carries
  reply_seconds: 9.5    # how long a streamed reply takes
```

| 欄位 | 必需 | 說明 |
| - | - | - |
| `enabled` | 是 | `true` 啟用模式。`false` 在模式關閉的情況下將您的數字保留在檔案中。如果區塊存在而沒有它，gateway 會拒絕啟動。 |
| `reply_tokens` | 否 | 預設 `750`。大約每個罐裝回覆攜帶多少 token 的文字，1 到 100000 的整數。 |
| `reply_seconds` | 否 | 預設 `9.5`。流式回覆需要多長時間，從 0 到 600。`0` 一次傳送整個回覆。對非流式請求的回覆總是一次回來。 |

此模式中的負載測試涵蓋 gateway、您的 Postgres 和 gateway 前面的所有東西。它不涵蓋提供者的限制、速度或網路路徑。

沒有模型請求傳送到提供者，因此複本的每個請求 CPU 是估計值，讀取低於生產，生產也加密其到提供者的流量。使用小型試驗對真實提供者確認複本計數。在 v2.1.283 之前，估計值讀取低得多。

啟用模式時，請求可以攜帶 `x-load-test-user` 標頭，保存最多七位數的整數。gateway 將每個數字計為單獨的開發者，具有請求附帶的 token 的開發者的電子郵件和群組。

為負載測試部署提供自己的空資料庫，因為 gateway 會拒絕在任何開發者已經花費任何東西的資料庫上啟動模式。

> [!WARNING]
>
> 永遠不要為開發者使用的 gateway 啟用此功能。每個請求獲得罐裝回覆，沒有模型被呼叫。gateway 在啟動時記錄 `load_test_mode is on` 警告，並在模式啟用時使用 `load_test: true` 標記每個 `inference` [稽核事件](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#logs)。

## 完整範例

此完整參考設定涵蓋每個核心部分；[HTTP 調整區塊](#http-tuning)保持其預設值。複製它，刪除您不需要的內容，並填入您的值。[快速入門](https://code.claude.com/docs/zh-TW/claude-apps-gateway#quickstart)中的設定是此的最小版本。

```yaml gateway.yaml theme={null}
# 執行方式：
#   claude gateway --config gateway.yaml
#
# 操作日誌詳細程度由 CLAUDE_GATEWAY_LOG_LEVEL
# 環境變數控制（debug | info | warn | error；預設 info）。debug
# 也會記錄每個 id_token 中的宣告名稱，用於 groups_claim 診斷。
# 它不影響稽核事件，始終發出。

listen:
  host: 0.0.0.0
  port: 8080
  public_url: https://claude-gateway.internal.example.com
  # 在 TLS 終止入口後面執行時省略 tls 區塊。
  # tls:
  #   cert: /certs/gateway.crt
  #   key: /certs/gateway.key
  # trusted_proxies:
  #   - 10.0.0.0/8

oidc:
  issuer: https://example.okta.com
  client_id: 0oa1example2
  client_secret: ${OIDC_CLIENT_SECRET}
  allowed_email_domains:
    - example.com
  # 當簽發者是 Okta 組織伺服器時需要，其 id_tokens
  # 可以省略電子郵件和群組；閘道從 /userinfo 填充它們。
  userinfo_fallback: true
  # allowed_groups: [claude-code-users]
  # Okta 僅在請求 `groups` 範圍且
  # 應用程式的群組宣告篩選允許它們時發出群組。下面的承包商原則
  # 符合群組，因此此處請求範圍。
  scopes: [openid, profile, email, offline_access, groups]
  # extra_auth_params: { access_type: offline, prompt: consent }  # Google
  # groups_claim: groups          # Entra 應用程式角色：使用 `roles`
  # email_claim: email

session:
  jwt_secret: ${GATEWAY_JWT_SECRET}   # openssl rand -base64 32
  # ttl_hours: 1

store:
  postgres_url: ${GATEWAY_POSTGRES_URL}
  # max_connections: 5
  # connect_timeout_seconds: 5
  # readiness_grace_seconds: 300   # 在資料庫容錯移轉期間保持通過整備檢查

# 啟用 /v1/organizations/spend_limits（鏡像 Anthropic Admin API）
# 和 /v1/messages 上的每個開發人員支出強制執行。省略以停用。
# 上限本身透過 admin API 設定，而不是此處。
# admin:
#   write_keys:
#     - { id: terraform, key: "${GATEWAY_ADMIN_WRITE_KEY_TF}" }
#   read_keys:
#     - { id: reporting, key: "${GATEWAY_ADMIN_READ_KEY}" }
#   admin_groups: [platform-finops]
#   blocked_message: request an increase at https://go.example.com/claude-limits
#   # audit_retention_days: 365
#   # spend_retention_months: 13
#   # identity_retention_days: 90
#   # group_limit_mode: min

# enforcement:
#   fail_closed_on_error: false

# 在不呼叫模型提供者的情況下負載測試此部署。絕不在開發人員使用的
# 閘道上執行：每個請求都會獲得預先錄製的回覆。
# load_test_mode:
#   enabled: true
#   # reply_tokens: 750
#   # reply_seconds: 9.5

# 以合約費率而非美元標價計費。需要 admin: 或
# managed: 原則。使用 managed:，相同費率也會傳送給已登入的用戶端。
# 下面的費率是佔位符，不是真實合約價格。
# pricing:
#   multiplier: 0.85
#   overrides:
#     - { upstream: anthropic, model: claude-sonnet-4-6, input: 3.30, output: 16.50, cache_read: 0.33, cache_write: 4.125 }

upstreams:
  - provider: anthropic
    auth:
      api_key: ${ANTHROPIC_API_KEY}

  # - provider: bedrock
  #   region: us-east-1
  #   auth: {}

  # - provider: mantle
  #   region: us-east-1
  #   models: [claude-opus-4-8, claude-opus-4-7, claude-haiku-4-5]
  #   auth: {}

  # - provider: anthropicAws
  #   region: us-east-1
  #   workspace_id: wrkspc_...
  #   auth:
  #     api_key: ${ANTHROPIC_AWS_API_KEY}

  # - provider: vertex
  #   region: us-east5
  #   project_id: example-prod
  #   auth: {}

  # - provider: foundry
  #   resource: example-foundry
  #   auth: { use_azure_ad: true }

auto_include_builtin_models: true
models:
  - id: claude-opus-4-8
    label: Claude Opus 4.8
    upstream_model:
      anthropic: claude-opus-4-8
      # bedrock: us.anthropic.claude-opus-4-8
      # mantle: anthropic.claude-opus-4-8
      # anthropicAws: claude-opus-4-8
      # vertex: claude-opus-4-8
      # foundry: <your-opus-deployment-name>
  - id: claude-sonnet-4-6
    label: Claude Sonnet 4.6
    upstream_model:
      anthropic: claude-sonnet-4-6
  - id: claude-haiku-4-5
    label: Claude Haiku 4.5
    upstream_model:
      anthropic: claude-haiku-4-5

managed:
  policies:
    - match: { groups: [contractors] }
      cli:
        availableModels: [claude-haiku-4-5]
        # allow 自動批准這些工具；它不阻止其餘的。
        # 新增 deny 規則以限制工具。
        permissions: { allow: [Read, Grep] }
    - match: {}
      cli:
        availableModels: [claude-opus-4-8, claude-sonnet-4-6, claude-haiku-4-5]
        # 將預設選擇器選項限制為每個原則的 availableModels，
        # 而不是內建預設，因此任何角色都不會在預設上獲得 400。
        # 承包商原則會繼承此鍵。
        enforceAvailableModels: true
        permissions:
          allow: [Read, Grep, Edit]
          deny: ["WebFetch"]
        env: { HTTP_PROXY: http://proxy.example.com:8080 }

telemetry:
  forward_to:
    - url: https://otel.internal.example.com:4318
      headers:
        Authorization: Bearer ${OTEL_TOKEN}
```

## 用戶端受管設定

以上所有內容都是在設定閘道伺服器。您需要在每部裝置上，透過 Claude Code 的[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)另外將開發人員的電腦指向閘道。閘道本身無法推送登入金鑰，因為正是這些金鑰告訴用戶端閘道的位置。

對於 CLI，請在各作業系統的 `managed-settings.json` 中設定這些金鑰。兩個登入金鑰會將每位開發人員的 `/login` 導向您的閘道：

```json theme={null}
{
  "forceLoginMethod": "gateway",
  "forceLoginGatewayUrl": "https://claude-gateway.internal.example.com",
  "parentSettingsBehavior": "merge"
}
```

`parentSettingsBehavior: "merge"` 可讓 Claude Desktop 持續將輸出允許清單傳遞給其內嵌的 Claude Code 工作階段；[將原則傳遞至 Claude Desktop 工作階段](https://code.claude.com/docs/zh-TW/claude-apps-gateway#deliver-policy-to-claude-desktop-sessions)說明了其運作機制，以及選擇加入設定必須放在何處。

若要防止開發人員使用雲端供應商變數或自行設定的 `ANTHROPIC_BASE_URL` 繞過閘道，請在同一個檔案中加入 `"allowedProviders": ["gateway"]`。Claude Code 隨後會拒絕該電腦上所有未設定為 Cloud 閘道的工作階段，且僅接受 `forceLoginGatewayUrl` 所指定的閘道，或是其 URL 由該檔案的 `env` 區塊設定為 `ANTHROPIC_BASE_URL` 的閘道。`claude gateway` 會拒絕在設定了此清單的電腦上執行，因此請勿在閘道主機上設定此金鑰。請參閱設定參考中的 [`allowedProviders`](https://code.claude.com/docs/zh-TW/settings-reference#allowedproviders) 項目。需要 Claude Code v2.1.285 或更新版本。

將 `managed-settings.json` 檔案部署到每部裝置，通常是透過您的 MDM 平台。檔案路徑因平台而異。請參閱[各機制儲存原則的位置](https://code.claude.com/docs/zh-TW/managed-settings.md#where-each-mechanism-stores-the-policy)。

根據預設，Windows 上的登錄原則或 macOS 上的受管偏好設定 plist 會取代 `managed-settings.json` 檔案，而非與其合併，但[上述的例外金鑰與跨來源檢查](#precedence-with-other-managed-sources)除外。此程式碼片段中的三個金鑰都遵循最高優先順序來源規則，因此透過群組原則或設定描述檔傳遞原則的裝置群，必須改為在該機制中設定這三個金鑰。

對於 Claude Desktop，請在 Claude Desktop 本身的[受管設定](https://claude.com/docs/third-party/claude-desktop/configuration)中，將 `bootstrapUrl` 金鑰設為 `<listen.public_url>/user/bootstrap`。一旦原則在伺服器端以 `desktop` 金鑰選擇加入，登入流程與各群組原則便會與 CLI 的一致；若未選擇加入，`/user/bootstrap` 會傳回 404。伺服器端的部分請參閱 [Claude Desktop 覆蓋設定](#claude-desktop-overlay)。

Claude Code 會採用來自電腦上受管來源的 [`forceLoginGatewayUrl`](https://code.claude.com/docs/zh-TW/settings-reference#forcelogingatewayurl)、[`gatewayInternalNetworks`](https://code.claude.com/docs/zh-TW/settings-reference#gatewayinternalnetworks)，以及 [`forceLoginMethod`](https://code.claude.com/docs/zh-TW/settings-reference#forceloginmethod) 的 `"gateway"` 值：這些受管來源包括 `managed-settings.json`、macOS plist 或 Windows HKLM 登錄，或原則輔助程式。在閘道 payload 中設定這些金鑰並不會設定閘道登入。若要使用開發人員自己的 `~/.claude/settings.json`，請參閱[在使用者設定中設定閘道 URL](https://code.claude.com/docs/zh-TW/claude-apps-gateway#set-the-gateway-url-in-user-settings)。

請勿將 `forceLoginMethod` 與 `forceLoginOrgUUID` 放入 payload 中。Claude Code 在啟動時的憑證檢查仍會從 payload 讀取這兩個金鑰，因此若開發人員在電腦上保留了 Anthropic 核發的憑證，即使登入後，仍會遇到 [Administrator policy requires a Cloud gateway sign-in](https://code.claude.com/docs/zh-TW/errors.md#administrator-policy-requires-a-cloud-gateway-sign-in) 中所述的啟動時結束情形。

## 相關

* [Claude 應用程式閘道概述](https://code.claude.com/docs/zh-TW/claude-apps-gateway)：快速入門和開發人員連接
* [部署指南](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md)：IdP 設定、容器映像、Kubernetes 和 Cloud Run，以及操作
* [支出限制](https://code.claude.com/docs/zh-TW/claude-apps-gateway-spend-limits.md)：每個開發人員上限和 Admin API
